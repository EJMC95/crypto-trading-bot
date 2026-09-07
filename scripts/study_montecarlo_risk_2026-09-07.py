#!/usr/bin/env python3
"""MONTE CARLO RISK AUDIT + BENCHMARK SHOOTOUT — what the fleet's own ledger
says about drawdown, ruin, and whether the books beat doing nothing.

**Eamon, 7-Sep:** *"Explain whether the bot adds genuine value."*

THIS FILE MOVES NOTHING. It reads the published feed, grades, simulates and
prints. It writes no lever, publishes no key, takes no trade — asserted by
`--selftest` (an AST walk of its own call sites, the (yk) shape: a page-wide
substring scan is not a structural claim).

WHY IT EXISTS. The fleet has fourteen instruments that ask *"is this book's
edge real?"* and, until now, **none that asks "what does this book's own
record say about the worst case?"** `golive_readiness` grades a realised
drawdown against a 15% bar over ONE realised path — the single sample the
book happened to walk. A path is not a distribution: 🎫 the taker's 5.4%
observed maxDD is one draw from a distribution whose 95th percentile this
file measures at more than twice that, and the gate cannot see the difference
between a book that is safe and a book that got a benign ordering.

THE CALIBRATION GATE IS THE POINT — `(gx)`'s rule, applied to itself: a
harness that cannot reproduce what DID happen may not say what WOULD have.
`calibrate()` recomputes every book's grade from the raw ledger and compares
it to the LIVE `golive-readiness` payload field by field. Beyond tolerance it
**REFUSES** — exit 2, no simulation printed, no benchmark table — because a
Monte Carlo built on a sample the grader would not recognise is a confident
number about a book nobody runs.

EVERY OWNER IS IMPORTED, NEVER RE-IMPLEMENTED ((hj): a second copy of a rule
is a second rule):

  * the era             -> `golive_readiness.era_rows`
  * the six bars        -> `golive_readiness.stats` / `grade` / `bar_map`
  * the critical value  -> `fleet_allocation.t_crit`   (never a fixed 1.28)
  * the lower bound     -> `fleet_allocation.lower_bound`
  * losing-streak chance-> `golive_readiness.expected_streak` / `loss_run_cdf`
  * the quarantine      -> `bot_pnl_store.is_quarantined` / `is_non_economic`
  * the phantom filter  -> `golive_readiness.is_phantom_close`
  * the cluster window  -> `golive_readiness.CLUSTER_WINDOW_S`

THE ONE THING IT OWNS is the resampling, and the care there is dependence.
The public feed is per-LEG; this fleet's books close baskets in one instant
(⚖️ Counterweight's ten legs; 👩 mum's flatten), so an i.i.d. bootstrap over
legs treats one decision as ten and understates every tail it reports. The
default resampler draws **decision batches** (legs grouped by
`CLUSTER_WINDOW_S`, the fleet's own definition), and `--iid` is offered only
so the two can be compared — the gap between them is itself a finding.

ARMS

    --calibrate     the gate alone (what any other arm runs first)
    --mc            drawdown / streak / ruin / target / reserve
    --bench         buy-and-hold, SMA, random-entry, vol-only, cash
    --splits        chronological train/val/test + walk-forward
    --corr          portfolio correlation, N_eff, drawdown overlap
    --all           every arm
    --selftest      the moves-nothing proof + the estimator checks

    --book <id>     restrict to one book (default: every graded book)
    --iid           i.i.d. legs instead of decision batches (comparison only)
    --draws N       simulation paths (default 20000)
    --refresh       re-fetch the feed instead of using the local cache
"""
import argparse
import ast
import bisect
import collections
import datetime as dt
import json
import math
import os
import random
import statistics
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import golive_readiness as G          # noqa: E402
import fleet_allocation as A          # noqa: E402
import bot_pnl_store as S             # noqa: E402
from experiment_judge import parse_ts  # noqa: E402

#: THE OPEN-STAMP PARSER, IMPORTED. `in_era` compares `parse(open_ts)` against
#: a float epoch, so a parser returning a `datetime` raises inside its own
#: `except` and the row is EXCLUDED — fail-closed, silent, and total. The
#: first draft of this file passed a datetime parser and every era-scoped
#: sample came back EMPTY; the gate reported eight books "ungradeable" rather
#: than eight books mis-graded, which is the fail-closed design working. This
#: is `_era_parse`'s own warning, met by importing the fleet's one owner of
#: "when did this trade open" instead of writing a second adapter.
_EPOCH = parse_ts

FEED = os.environ.get(
    "PNL_FEED", "https://pnl-dashboard-production-858c.up.railway.app")
CACHE = os.environ.get(
    "MC_CACHE", os.path.join(HERE, ".mc_cache"))

#: Measured Lighter friction, not assumed (STUDY_MEASURED_FRICTION_2026-08-05).
#: Venue taker/maker fee is 0.0000 on all 203 active books; the whole cost is
#: slippage. Median round trip: Farmer 0.58bps, 🎫 taker 10.2bps (n=67);
#: ~25bps around p90. The STRESS band is the p90 read — used to price every
#: arm identically, the bot included, so no arm is charged a cost its rival
#: escapes.
RT_BPS_MEDIAN = 10.2
RT_BPS_P90 = 25.0

#: Tolerances for the calibration gate. `n` must match EXACTLY — a differing
#: close count means a differing sample, and every other number is then about
#: a different book. The rest are the feed's own published rounding.
CAL_TOL = {"mean_pct": 0.006, "t": 0.02, "h1": 0.02, "h2": 0.02,
           "net_usd": 0.02, "days": 0.11, "win_pct": 0.06}

#: A book must clear this to be simulated at all. Below it a bootstrap is
#: resampling noise and reporting it as a risk estimate — `fleet_allocation`'s
#: own computability floor, imported rather than re-chosen.
MIN_N_SIM = A.MIN_N


# --------------------------------------------------------------------------
# feed
# --------------------------------------------------------------------------
def _get(url, path, refresh=False, timeout=90):
    """Fetch-once-cache. Fail-safe toward a LIVE fetch, never toward {}."""
    if not refresh and os.path.exists(path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception:  # noqa: BLE001
            pass
    req = urllib.request.Request(url, headers={"User-Agent": "mc-risk/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        blob = json.loads(r.read().decode())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(blob, fh)
    except Exception:  # noqa: BLE001
        pass
    return blob


def load_feed(refresh=False):
    trades = _get(f"{FEED}/trades.json?source=paper&limit=5000",
                  os.path.join(CACHE, "trades.json"), refresh)
    bus = _get(f"{FEED}/bus.json?hours=200",
               os.path.join(CACHE, "bus.json"), refresh)
    rows = trades.get("trades") if isinstance(trades, dict) else trades
    rows = rows or []
    # (qz): a count equal to the cap is a TRUNCATION SIGNATURE, not a result.
    if len(rows) >= 5000:
        raise SystemExit(
            "REFUSED: /trades.json returned exactly its 5000-row cap — the "
            "ledger is truncated and every sample below would be a silent "
            "subsample. Page the feed before trusting this run.")
    return rows, (bus or {})


def _parse(s):
    """The feed serves two stamp forms; both appear in one response."""
    if not s:
        return None
    t = str(s).strip()
    try:
        if t.endswith(" UTC"):
            return dt.datetime.strptime(t[:-4], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=dt.timezone.utc)
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def normalise(rows, as_of=None):
    """Ledger -> per-book rows in THE PUBLISHER'S OWN 7-TUPLE SHAPE.

    The public `/trades.json?source=paper` feed does **not** apply
    `LEDGER_QUARANTINE` — CLAUDE.md says so in as many words — so an outside
    consumer that grades from it grades a sample the gate refuses. Measured on
    the day this shipped: 🧘 douglas n=83 raw vs n=81 graded.

    THE ROW SHAPE IS LOAD-BEARING AND THE GATE PROVED IT. `era_rows` derives
    the policy boundary from each close's own `extra.policy`, which rides at
    index **[4]**; the first draft of this file passed 4-tuples, so every
    stamp was invisible, every book fell back to its DECLARED era, and 🎫 the
    taker graded **262 closes against the live 184** — a 42% wider sample, in
    the flattering direction, on the one book the fleet has ever called READY.
    Nothing in the arithmetic was wrong; the harness was simply grading a
    different book. That is the whole argument for the calibration gate.

    `as_of` truncates the ledger to the published payload's own timestamp. A
    close that landed between the grader's publish and this fetch is not a
    disagreement, and letting it in makes every book off by one for a reason
    that is not a defect.
    """
    books = collections.defaultdict(list)
    dropped = collections.Counter()
    for r in rows:
        bot, pair = r.get("bot"), r.get("pair")
        ca, oa = _parse(r.get("closed_at")), _parse(r.get("opened_at"))
        if not bot or ca is None:
            dropped["unparseable"] += 1
            continue
        if as_of is not None and ca > as_of:
            dropped["after_payload"] += 1
            continue
        if S.is_quarantined(bot, pair, r.get("closed_at")):
            dropped["quarantined"] += 1
            continue
        if S.is_non_economic(r.get("pnl_abs"), r.get("entry_price"),
                             r.get("extra")):
            dropped["non_economic"] += 1
            continue
        if G.is_phantom_close(r):
            dropped["phantom"] += 1
            continue
        # [(xq)] adopted legs too — a position the book took over mid-life,
        # whose entry basis and hold are fictions of the takeover instant.
        if G.is_adopted_close(r):
            dropped["adopted"] += 1
            continue
        pct, abs_ = r.get("pnl_pct"), r.get("pnl_abs")
        if not isinstance(pct, (int, float)):
            dropped["no_pct"] += 1
            continue
        # The publisher's shape exactly: profit_ratio, profit_abs, close dt,
        # open stamp, extra[4], enter_tag[5], pair[6] — plus the raw row at
        # [7] for the benchmark arms, appended so the owners' [0..6] indexing
        # is untouched.
        books[bot].append((float(pct), float(abs_ or 0.0), ca,
                           r.get("opened_at"), r.get("extra"),
                           r.get("reason"), r.get("pair"), r))
        _ = oa
    for b in books:
        # The publisher sorts on the close STAMP with a stable sort, so ties
        # keep feed order; matched here rather than re-invented.
        books[b].sort(key=lambda x: str(x[7].get("closed_at") or ""))
    return books, dropped


def graded(books, sleeve_retired=None):
    """{bot: {'rows': era-scoped 3-tuples, 'full': era-scoped full rows, ...}}"""
    out = {}
    sr = sleeve_retired or {}
    for bot, rs in books.items():
        # [(nk)] COMPOSITION BEFORE TIME — a retired sleeve's trades are not
        # this book's record, so they leave before the era boundary is derived.
        rs2, _ = G.drop_retired_sleeves(rs, sr.get(bot))
        det = G.era_rows(bot, rs2, parse=_EPOCH, detail=True)
        out[bot] = {"rows": det["scoped"], "full": det["scoped_rows"],
                    "all_time": det["all_time"], "era_iso": det["iso"],
                    "stats": G.stats(det["scoped"]) if len(det["scoped"]) >= 2
                    else {"n": len(det["scoped"])}}
    return out


# --------------------------------------------------------------------------
# THE CALIBRATION GATE
# --------------------------------------------------------------------------
def halves_tie_ambiguous(rows):
    """Does the h1/h2 split boundary fall INSIDE a tied close batch?

    `stats()` splits at `mid = n // 2` over rows sorted by close stamp. When
    `rows[mid-1]` and `rows[mid]` share that stamp to the microsecond, which
    legs land in which half is decided by the sort's STABILITY — i.e. by the
    order Postgres happened to return — and not by anything about the book.

    THIS IS NOT A HARNESS QUIRK, IT IS A PROPERTY OF THE GATE. "Both halves
    positive" is one of the six go-live bars. Measured on 🙏 avo's LIVE arm,
    7-Sep: five legs close on the single instant 2026-08-28T16:22:46.174888
    (a daily-loss flatten), the median boundary lands among them, and moving
    TRX (+$0.387) past XAU (-$7.30) inside that tie shifts **$7.69 across the
    boundary** — h1 reads $17.36 or $9.67 depending on row order alone. Both
    are still positive here, so no verdict moves today; a book whose h1 sat
    near zero would have the bar decided by the database.

    Reported by the gate as a DECLARED, REASONED exemption rather than
    absorbed into a wider tolerance: the feed cannot reproduce the DB's
    intra-tie order, so h1/h2 are genuinely unknowable here, and pretending
    otherwise by loosening `CAL_TOL` would blind the gate to a real h1/h2
    disagreement on every other book.
    """
    n = len(rows)
    if n < 4:
        return False
    mid = n // 2
    return rows[mid - 1][2] == rows[mid][2]


def calibrate(gr, grades, verbose=True):
    """Reproduce the LIVE published grade, or refuse.

    Returns (ok, checked, [failure, ...]). `ok=False` means every downstream
    number in this file is about a sample the fleet's own grader does not
    recognise, and the caller must exit non-zero WITHOUT printing them.
    """
    live = (gr or {}).get("books") or {}
    fails, checked, excused = [], 0, []
    for bot, want in sorted(live.items()):
        got = (grades.get(bot) or {}).get("stats")
        if not got or got.get("n", 0) < 2:
            if want.get("n", 0) >= 2:
                fails.append(f"{bot}: live n={want.get('n')} · local ungradeable")
            continue
        pay = G.book_payload(got)
        if pay.get("n") != want.get("n"):
            fails.append(f"{bot}: n live={want.get('n')} local={pay.get('n')}")
            continue
        checked += 1
        tie = halves_tie_ambiguous((grades.get(bot) or {}).get("rows") or [])
        for k, tol in CAL_TOL.items():
            a, b = want.get(k), pay.get(k)
            if a is None or b is None:
                continue
            if abs(float(a) - float(b)) > tol:
                if k in ("h1", "h2") and tie:
                    excused.append(
                        f"{bot}.{k}: live={a} local={b} — the h1/h2 boundary "
                        f"falls inside a TIED close batch; intra-tie order is "
                        f"the DB's and is not reproducible from the feed")
                    continue
                fails.append(f"{bot}.{k}: live={a} local={b} (tol {tol})")
    ok = checked >= 5 and not fails
    if verbose:
        print("=" * 78)
        print("CALIBRATION GATE — reproduce the live golive-readiness grade")
        print("=" * 78)
        stamp = (gr or {}).get("updated") or (gr or {}).get("updated_at")
        print(f"  live payload   : {stamp}")
        print(f"  books compared : {checked} of {len(live)}")
        if fails:
            print(f"  MISMATCHES     : {len(fails)}")
            for f in fails[:12]:
                print(f"     - {f}")
        else:
            print("  MISMATCHES     : none — every compared field inside tolerance")
        if excused:
            print(f"  EXCUSED        : {len(excused)} (declared, with a reason "
                  f"— see `halves_tie_ambiguous`)")
            for e in excused:
                print(f"     ~ {e}")
        print(f"  VERDICT        : {'PASS' if ok else 'REFUSE'}")
        print()
    return ok, checked, fails


# --------------------------------------------------------------------------
# resampling
# --------------------------------------------------------------------------
def batches(rows, window_s=None):
    """Group legs into DECISIONS by close proximity — the fleet's own rule.

    `golive_readiness.cluster_se` already treats closes inside
    `CLUSTER_WINDOW_S` as one decision, because a basket book closes ten legs
    on one instant's move. Resampling legs i.i.d. would treat that decision as
    ten independent draws and understate every tail below.
    """
    w = G.CLUSTER_WINDOW_S if window_s is None else window_s
    out, cur, anchor = [], [], None
    for r in rows:
        ts = r[2]
        if anchor is not None and (ts - anchor).total_seconds() > w:
            out.append(cur)
            cur = []
            anchor = None
        if anchor is None:
            anchor = ts
        cur.append(r)
    if cur:
        out.append(cur)
    return out


def _path_stats(seq, start_equity):
    """Equity path -> (final, max_dd_frac, longest_loss_run, min_equity).

    THE DENOMINATOR IS `start_equity`, NOT THE RUNNING PEAK — because that is
    what `golive_readiness.stats` does (`max_dd_frac = abs(dd) / book_usd`),
    and a Monte Carlo whose drawdown is defined differently from the bar it is
    being compared against is not comparing anything. Dividing by the running
    peak would report a SMALLER number on a book that has grown, which is the
    (yr) "drawdown denominator that halved real money's hole" defect, and
    adopting it here would import that defect into the risk estimate.
    """
    eq = peak = start_equity
    dd = 0.0
    lo = eq
    run = mx = 0
    for x in seq:
        eq += x
        peak = max(peak, eq)
        lo = min(lo, eq)
        dd = max(dd, peak - eq)
        if x <= 0:
            run += 1
            mx = max(mx, run)
        else:
            run = 0
    return eq, (dd / start_equity if start_equity > 0 else 0.0), mx, lo


def simulate(units, n_draw, draws, start_equity, rng, edge_mult=1.0,
             cost_per_leg=0.0):
    """Resample `units` (each a list of per-leg dollar P&Ls) with replacement.

    `edge_mult` scales the MEAN while holding the dispersion — the "varied
    win/loss assumption" arm. Scaling every return would scale sd too and
    leave `t` invariant (I22's leverage arithmetic), which tests nothing.
    """
    flat = [x for u in units for x in u]
    mu = statistics.fmean(flat) if flat else 0.0
    shift = mu * (edge_mult - 1.0)
    finals, dds, runs, lows = [], [], [], []
    k = len(units)
    for _ in range(draws):
        seq = []
        for _ in range(n_draw):
            for x in units[rng.randrange(k)]:
                seq.append(x + shift - cost_per_leg)
        f, d, m, lo = _path_stats(seq, start_equity)
        finals.append(f)
        dds.append(d)
        runs.append(m)
        lows.append(lo)
    return {"final": finals, "dd": dds, "run": runs, "low": lows}


def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


# --------------------------------------------------------------------------
# position sizing / ruin
# --------------------------------------------------------------------------
def notional_of(row):
    """The book's OWN clip for this trade: pnl_abs / pnl_pct.

    Derived from the ledger rather than read from a config, so a book whose
    clip moved mid-sample reports the mixture it actually traded.
    """
    pct_, abs_ = row[0], row[1]
    if not pct_ or abs(pct_) < 1e-9:
        return None
    return abs(abs_ / pct_)


def sizing(full_rows, book_usd=1000.0):
    ns = [n for n in (notional_of(r) for r in full_rows) if n and n > 0]
    if not ns:
        return None
    med = statistics.median(ns)
    return {"clip_usd": med, "clip_frac": med / book_usd,
            "n_priced": len(ns),
            "clip_lo": min(ns), "clip_hi": max(ns)}


def concurrency(full_rows, parse=None):
    """How many of this book's positions were genuinely OPEN at once.

    Reconstructed from the ledger's own open/close stamps as a sweep line, so
    it is the book's realised behaviour rather than its configured cap.

    THIS IS NOT A DETAIL, IT IS THE DOMINANT FACT for a sizing table. Measured
    7-Sep: 🎫 the taker holds a **mean of 4.92** positions and **97% of its
    legs opened while others were already held**; 👩 mum's live arm 6.92; and
    ⚖️ Counterweight 13.43 against a configured cap of 10. A model that
    compounds those legs SEQUENTIALLY is pricing a book that essentially never
    exists — one that holds a single position at a time.

    Returns {mean, p90, peak, overlap_frac, n}.
    """
    p = parse or _parse
    ev = []
    for r in full_rows:
        o = p(r[7].get("opened_at")) if len(r) > 7 else None
        c = r[2]
        if o is None or c is None or c < o:
            continue
        ev.append((o, 1))
        ev.append((c, -1))
    if not ev:
        return None
    ev.sort()
    cur = peak = 0
    at_open = []
    for _, d in ev:
        cur += d
        peak = max(peak, cur)
        if d == 1:
            at_open.append(cur)
    if not at_open:
        return None
    s = sorted(at_open)
    return {"mean": statistics.fmean(at_open),
            "p90": s[min(len(s) - 1, int(0.9 * len(s)))],
            "peak": peak, "n": len(at_open),
            "overlap_frac": sum(1 for x in at_open if x > 1) / len(at_open)}


def ruin_curve(units, n_draw, draws, rng, ruin_levels, fracs, k_joint=1,
               block=None):
    """P(equity ever touches `level`) as the position fraction `f` varies.

    `units` hold per-trade returns ON THE POSITION'S NOTIONAL (`pnl_pct`).
    The ACCOUNT return of that trade is `f * pnl_pct`, where `f` is the
    fraction of equity the position represents. Compounded, never additive: a
    book that has halved cannot lose the same dollars again, and an additive
    path overstates ruin at exactly the sizes this table exists to compare.

    THE `f` IS THE WHOLE SCALE, AND THE FIRST DRAFT GOT IT WRONG. It used
    `scale = f / clip_frac`, which at the shipped size collapses to 1.0 and
    therefore compounds RAW per-trade returns as if every trade risked the
    entire account. On 🎫 the taker that read a median **6.51x** on a book
    whose record is **+15.9%**, and on ⚖️ Counterweight **P(-50%) = 96.4%**
    on a book that is down 3.5%. Both are absurd on inspection, and neither
    was caught by the grade-reproduction gate — that gate reads the ledger,
    not the simulator. `calibrate_ruin` below is the check that does, and it
    is the reason this docstring can be trusted.

    `k_joint` IS THE SECOND CORRECTION, AND IT MATTERS MORE THAN THE FIRST.
    At `k_joint=1` the legs compound SEQUENTIALLY — one bet resolves before
    the next is taken. That is not this fleet. Measured 7-Sep from the
    ledger's own open/close stamps (`concurrency`): 🎫 the taker holds a mean
    of **4.92** positions with **97%** of its legs opening while others are
    already held; 👩 mum's live arm **6.92**; ⚖️ Counterweight **13.43**
    against a configured cap of 10. `k_joint` draws that many legs and applies
    their SUMMED return as ONE equity step — what "every open position moves
    against you at once" actually costs.

    THE FIRST PUBLISHED VERSION OF THIS TABLE WAS WRONG IN THE DIRECTION THAT
    LOSES MONEY. Sequentially it read `P(-50%) = 0.0%` and a still-RISING
    `E[log]` at f=40% on 🎫 the taker — an invitation to raise size 8x on the
    fleet's only READY book. At that book's measured concurrency, f=40% is
    ~197% of equity deployed. A conservative model is a fine thing for a risk
    table to be; this was the opposite, and that is the one direction a sizing
    model must never err in.

    THE THIRD CORRECTION, AND IT IS WHY `block` EXISTS. Applying `kj` legs
    together but DRAWING them independently captures the timing of joint
    exposure and not the CORRELATION of joint outcomes — and concurrent legs
    in this fleet are anything but independent: same lens, same side, same
    market move. Independent draws cancel, so the joint tail comes out far too
    thin. Measured on 🎫 the taker at f=40%: independent-joint reads
    `P(-50%) = 0.0%` and an E[log] still rising, i.e. *"size up 8x"*; drawing
    the same legs as a CONTIGUOUS BLOCK of the book's own open-ordered
    timeline — so they carry the co-movement they actually had — is the
    honest version. `block` is that open-ordered leg sequence; without it this
    falls back to independent draws and SAYS SO in the caller.
    """
    out = {}
    kj = max(1, int(k_joint))
    blk = [x for x in (block or []) if isinstance(x, (int, float))]
    for f in fracs:
        hits = {lv: 0 for lv in ruin_levels}
        finals = []
        # HOW MANY ROUNDS does the book cycle through its own capacity? With
        # `kj` legs live at once and `len(blk)` legs in the sample, that is
        # len(blk)//kj — counted in LEGS. The first cut of this used
        # `n_draw // kj`, mixing units: `n_draw` counts close-BATCHES, so on
        # ⚖️ Counterweight (47 batches, 155 legs, kj=13) it ran **3** rounds
        # instead of 12 and reported LESS ruin than the sequential model it
        # was correcting. A unit mix-up in the denominator of a risk table
        # flatters it by exactly the factor nobody checks.
        steps = max(1, (len(blk) // kj) if (kj > 1 and len(blk) > kj)
                    else n_draw // kj)
        for _ in range(draws):
            eq = 1.0
            low = 1.0
            for _ in range(steps):
                joint = 0.0                # the whole book moving at once
                if kj > 1 and len(blk) > kj:
                    i = rng.randrange(len(blk) - kj)
                    joint = sum(blk[i:i + kj])
                else:
                    for _ in range(kj):
                        for leg in units[rng.randrange(len(units))]:
                            joint += leg
                eq *= (1.0 + joint * f)
                low = min(low, eq)
                if eq <= 0.0:
                    eq = 1e-9
                    low = 0.0
                    break
            finals.append(eq)
            for lv in ruin_levels:
                if low <= lv:
                    hits[lv] += 1
        out[round(f, 4)] = {
            "p_ruin": {lv: hits[lv] / draws for lv in ruin_levels},
            "median_final": pct(finals, 0.5), "p05_final": pct(finals, 0.05),
            "p95_final": pct(finals, 0.95),
            "mean_log": statistics.fmean([math.log(max(x, 1e-9)) for x in finals]),
        }
    return out


def calibrate_ruin(units, n_draw, clip_frac, realised_usd, book_usd=1000.0,
                   draws=1500, tol=0.35, seed=909):
    """THE SECOND GATE: at the SHIPPED size, does the simulator reproduce the
    book's own account return?

    A grade-reproduction gate proves the SAMPLE is right. It says nothing
    about the SIMULATOR, and the two failures above lived entirely in the
    simulator while the first gate stayed green — the (po) lesson exactly: a
    receipt for fidelity is not a receipt for correctness.

    Returns (ok, sim_median_return, book_return). Tolerance is deliberately
    wide (35% relative): a median of a resampled distribution need not equal
    one realised path, and a tight bar here would fail on ordinary sampling
    noise. It is a SANITY bound, sized to catch an order-of-magnitude error —
    which is the class that actually occurred.
    """
    if not clip_frac or clip_frac <= 0:
        return True, None, None
    rc = ruin_curve(units, n_draw, draws, random.Random(seed), [0.5],
                    [clip_frac])
    sim = rc[round(clip_frac, 4)]["median_final"] - 1.0
    book = realised_usd / book_usd
    if abs(book) < 0.005:                 # a flat book cannot calibrate a ratio
        return abs(sim) < 0.05, sim, book
    return abs(sim - book) <= tol * max(abs(book), 0.02) + 0.02, sim, book


# --------------------------------------------------------------------------
# splits / walk-forward
# --------------------------------------------------------------------------
def split_stats(rows, cuts=(0.5, 0.75)):
    n = len(rows)
    a, b = int(n * cuts[0]), int(n * cuts[1])
    parts = {"train": rows[:a], "valid": rows[a:b], "test": rows[b:]}
    out = {}
    for k, v in parts.items():
        out[k] = G.stats(v) if len(v) >= 2 else {"n": len(v)}
    return out


def walk_forward(rows, folds=5, min_train=20):
    """Expanding-window walk-forward: train on everything before the fold,
    report the fold's OUT-OF-SAMPLE mean. No parameter is fitted here — the
    books are already shipped — so this measures STABILITY, which is the only
    thing a walk-forward can honestly say about a live rule."""
    n = len(rows)
    if n < min_train + folds:
        return []
    edges = [int(min_train + (n - min_train) * i / folds) for i in range(folds + 1)]
    out = []
    for i in range(folds):
        lo, hi = edges[i], edges[i + 1]
        if hi - lo < 2:
            continue
        tr = G.stats(rows[:lo]) if lo >= 2 else {"n": lo}
        te = G.stats(rows[lo:hi])
        out.append({"fold": i + 1, "train_n": tr.get("n"),
                    "train_mean": tr.get("mean_pct"),
                    "test_n": te.get("n"), "test_mean": te.get("mean_pct"),
                    "test_t": te.get("t"),
                    "from": rows[lo][2].date().isoformat(),
                    "to": rows[hi - 1][2].date().isoformat()})
    return out


# --------------------------------------------------------------------------
# benchmarks
# --------------------------------------------------------------------------
def price_tape(all_rows):
    """A per-coin price series built from the fleet's OWN executed prices.

    The venue's `/api/v1/candlesticks` is 403 from every egress outside the
    container ([[lighter-tape-fetch-throttle]] neighbours), so bars are not
    reachable here. What IS reachable is better in one respect and worse in
    another, and both are stated: every (pair, stamp, price) below is a price
    THIS FLEET ACTUALLY TRANSACTED AT on this venue — no vendor mid, no
    cross-venue proxy — but the series is IRREGULAR, sampled only when some
    book opened or closed. So it can price a hold between two observations and
    it cannot walk a bracket. Benchmarks that need a bracket say so and are
    withheld rather than approximated.
    """
    tape = collections.defaultdict(list)
    for r in all_rows:
        pair = (r.get("pair") or "").split("/")[0]
        for stamp, px in ((r.get("opened_at"), r.get("entry_price")),
                          (r.get("closed_at"), r.get("exit_price"))):
            t = _parse(stamp)
            if t is None or not isinstance(px, (int, float)) or px <= 0:
                continue
            tape[pair].append((t, float(px)))
    for k in tape:
        tape[k].sort()
    return tape


def price_at(tape, pair, when, max_gap_h=36.0):
    """Nearest observation within `max_gap_h`, else None. Never extrapolates —
    an unknown price is None, and a benchmark leg with no price is DROPPED and
    counted, never filled with the last one seen (the (yq) rule: an unfillable
    order is not a zero-cost fill)."""
    ser = tape.get(pair)
    if not ser:
        return None
    ts = [t for t, _ in ser]
    i = bisect.bisect_left(ts, when)
    best, bestgap = None, None
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(ser):
            gap = abs((ser[j][0] - when).total_seconds()) / 3600.0
            if bestgap is None or gap < bestgap:
                best, bestgap = ser[j][1], gap
    if best is None or bestgap > max_gap_h:
        return None
    return best


#: A buy-and-hold arm priced from the fleet's own fills is only worth printing
#: when most of the book's coins are actually priceable at BOTH ends. Below
#: this it is a 2-of-16 subsample dressed as a benchmark — the (qz) shape, a
#: truncated search reading as an exhaustive one.
BH_MIN_COVERAGE = 0.60
BH_MAX_GAP_H = 12.0


def bench_buy_hold(tape, pairs, t0, t1, rt_bps):
    """Equal-weighted buy-and-hold of the book's OWN traded coins over the
    book's OWN window, charged the same round trip.

    REFUSES below `BH_MIN_COVERAGE`. The first run of this arm printed
    "+113.142% per asset (2 priced, 22 unpriceable)" for 🌾 carry and
    "+39.062% (2 priced, 14 unpriceable)" for 🔮 georgia — numbers driven
    entirely by which two coins happened to have a fill near both endpoints,
    presented with the authority of a benchmark. A coverage floor turns that
    from a misleading number into an honest absence.
    """
    rets, missing = [], 0
    for p in sorted(pairs):
        a = price_at(tape, p, t0, BH_MAX_GAP_H)
        b = price_at(tape, p, t1, BH_MAX_GAP_H)
        if a is None or b is None:
            missing += 1
            continue
        rets.append(b / a - 1.0 - rt_bps / 1e4)
    total = len(rets) + missing
    cov = len(rets) / total if total else 0.0
    if not rets or cov < BH_MIN_COVERAGE:
        return {"withheld": True, "coverage": cov, "n_assets": len(rets),
                "missing": missing}
    return {"withheld": False, "mean_ret": statistics.fmean(rets),
            "n_assets": len(rets), "missing": missing, "coverage": cov,
            "median_ret": statistics.median(rets)}


def bench_random_entry(tape, full_rows, rng, rt_bps, draws=400):
    """The (hm) null in the form this data supports: hold a RANDOM OTHER coin
    over the SAME window as each real trade, same side, same cost.

    DECLARED LIMIT, because it changes what the number means: this does not
    walk the bot's bracket — no tp, no sl, no trailing — so it is the
    *entry-timing* null, not the *whole-rule* null. It answers "was there
    anything special about this coin at this moment?" and not "would a random
    entry through the same exits have earned the same?".
    """
    coins = [c for c, s in tape.items() if len(s) >= 12]
    if len(coins) < 8:
        return None
    means = []
    for _ in range(draws):
        rs = []
        for r in full_rows:
            raw = r[7]
            o, c = _parse(raw.get("opened_at")), _parse(raw.get("closed_at"))
            if o is None or c is None:
                continue
            own = (raw.get("pair") or "").split("/")[0]
            for _try in range(6):
                cand = coins[rng.randrange(len(coins))]
                if cand == own:
                    continue
                a, b = price_at(tape, cand, o), price_at(tape, cand, c)
                if a is None or b is None:
                    continue
                ret = b / a - 1.0
                if str(raw.get("side") or "").lower().startswith("short"):
                    ret = -ret
                rs.append(ret - rt_bps / 1e4)
                break
        if rs:
            means.append(statistics.fmean(rs))
    if not means:
        return None
    return {"mean_ret": statistics.fmean(means), "p05": pct(means, 0.05),
            "p95": pct(means, 0.95), "draws": len(means), "_dist": means}


def null_p(dist, observed):
    """P(random >= observed) — the (hm) statistic, and the only honest read of
    this null.

    Comparing the book's mean to the null's 95th percentile answers a
    different question and rounds to a verdict; the fraction of null draws
    that beat the book is the number `(hm)` actually reports ("six independent
    runs put P(coin flip >= taker) at 0.55-0.84").
    """
    if not dist:
        return None
    return sum(1 for m in dist if m >= observed) / len(dist)


def marks_series(bus_hist):
    """{coin: [(ts, mark)]} from the scout's own `lighter-market` snapshots."""
    out = collections.defaultdict(list)
    for e in bus_hist or []:
        if e.get("key") != "lighter-market":
            continue
        p = e.get("payload")
        if isinstance(p, str):
            try:
                p = ast.literal_eval(p)
            except Exception:  # noqa: BLE001
                continue
        t = _parse(e.get("ts"))
        if t is None or not isinstance(p, dict):
            continue
        for c, m in (p.get("marks") or {}).items():
            if isinstance(m, (int, float)) and m > 0:
                out[c].append((t, float(m)))
    for k in out:
        out[k].sort()
    return out


def common_window(series, min_pts=200, cover=0.95):
    """The widest span the mark tape supports, and the coins that cover it.

    Taking `max(start), min(end)` across every coin collapses the window to
    whatever the youngest listing supports — the first run of this arm read
    **1.0 day** out of an 8.3-day tape because one new coin truncated all 195.
    The window is instead the tape's own full extent, and a coin JOINS the
    benchmark only if its own series covers `cover` of it. A coin that cannot
    be held for the whole window is not a buy-and-hold candidate for it.
    """
    spans = [(s[0][0], s[-1][0]) for s in series.values() if len(s) >= min_pts]
    if not spans:
        return None, None, {}
    t0 = min(a for a, _ in spans)
    t1 = max(b for _, b in spans)
    need = (t1 - t0).total_seconds() * cover
    keep = {c: s for c, s in series.items()
            if len(s) >= min_pts
            and (s[-1][0] - s[0][0]).total_seconds() >= need
            and (s[0][0] - t0).total_seconds() <= (t1 - t0).total_seconds() * (1 - cover)}
    return t0, t1, keep


def bench_sma_and_vol(series, fast=12, slow=48, rt_bps=RT_BPS_MEDIAN,
                      min_pts=200):
    """SMA-cross and inverse-vol benchmarks on the scout's 5-min mark tape.

    Both are charged a round trip per position change. The SMA arm is the
    canonical simple trend rule; the vol arm holds every coin inverse to its
    own realised volatility with no directional view at all — the "volatility
    only" benchmark, i.e. what risk management alone earns.
    """
    sma_rets, bh_rets, vols, turns = [], [], [], []
    for c, ser in series.items():
        px = [p for _, p in ser]
        if len(px) < min_pts:
            continue
        rets = [px[i] / px[i - 1] - 1.0 for i in range(1, len(px))]
        sd = statistics.pstdev(rets) if len(rets) > 2 else 0.0
        if sd <= 0:
            continue
        pos, eq, flips = 0, 1.0, 0
        for i in range(slow, len(px)):
            f = statistics.fmean(px[i - fast:i])
            s = statistics.fmean(px[i - slow:i])
            want = 1 if f > s else 0
            if want != pos:
                eq *= (1.0 - rt_bps / 1e4)
                flips += 1
                pos = want
            if pos:
                eq *= px[i] / px[i - 1]
        sma_rets.append(eq - 1.0)
        bh_rets.append(px[-1] / px[0] - 1.0 - rt_bps / 1e4)
        vols.append((c, sd, px[-1] / px[0] - 1.0))
        turns.append(flips)
    if not sma_rets:
        return None
    inv = [(1.0 / sd, r) for _, sd, r in vols if sd > 0]
    wsum = sum(w for w, _ in inv) or 1.0
    volret = sum(w * r for w, r in inv) / wsum - rt_bps / 1e4
    return {"n_assets": len(sma_rets),
            "sma_mean": statistics.fmean(sma_rets),
            "sma_median": statistics.median(sma_rets),
            "sma_flips_median": statistics.median(turns) if turns else 0,
            "bh_mean": statistics.fmean(bh_rets),
            "bh_median": statistics.median(bh_rets),
            "volonly_ret": volret}


# --------------------------------------------------------------------------
# risk ratios
# --------------------------------------------------------------------------
def ratios(rows):
    """Sharpe and Sortino on the book's PER-TRADE return series, plus the
    annualised read at the book's own close RATE.

    PER-TRADE FIRST, ANNUALISED SECOND, AND THE ORDER MATTERS. Annualising by
    `sqrt(trades/year)` rewards a book purely for trading more often, which is
    the denominator-shrinkage trap `(hl)` measured across 25 of 30 throughput
    candidates. The per-trade figure is the one to compare between books; the
    annualised one is there because it is what an outside reader expects, and
    it is labelled as the derived quantity it is.

    Sortino's denominator is downside deviation about ZERO (not about the
    mean) — the convention that answers "how much of the dispersion actually
    hurts?" rather than flattering a book with a high mean.
    """
    pct = [r[0] for r in rows if isinstance(r[0], (int, float))]
    n = len(pct)
    if n < 3:
        return None
    mu = statistics.fmean(pct)
    sd = statistics.pstdev(pct)
    down = [x for x in pct if x < 0]
    dd = math.sqrt(sum(x * x for x in down) / n) if down else 0.0
    days = (rows[-1][2] - rows[0][2]).total_seconds() / 86400.0
    per_yr = (n / days * 365.0) if days > 0 else 0.0
    sharpe = (mu / sd) if sd > 0 else None
    sortino = (mu / dd) if dd > 0 else None
    k = math.sqrt(per_yr) if per_yr > 0 else 0.0
    return {"n": n, "mean": mu, "sd": sd, "downside_dev": dd,
            "sharpe_trade": sharpe, "sortino_trade": sortino,
            "sharpe_ann": (sharpe * k) if sharpe is not None else None,
            "sortino_ann": (sortino * k) if sortino is not None else None,
            "trades_per_yr": per_yr, "days": days,
            # Gross profit / gross loss — the one ratio that is invariant to
            # both clip and trade count, so it cannot be gamed by turnover.
            "profit_factor": (sum(x for x in pct if x > 0) /
                              abs(sum(down)) if down else None)}


def regime_split(rows, btc=None, lookback_h=24.0):
    """Split the book's own closes by market regime at the close.

    TWO SOURCES, PREFERRED IN ORDER, AND THE FALLBACK EXISTS BECAUSE THE FIRST
    IS EMPTY. `extra.btc_regime_up` is stamped on the books' *summary rows*
    and is NOT on their *trade* rows — measured across all 14 graded books,
    coverage is **0%**, so a per-close regime attribution simply cannot be
    made from the ledger. That is a real observability gap, reported rather
    than papered over.

    The fallback derives regime from the scout's own BTC marks: a close is
    "BTC-up" when BTC rose over the `lookback_h` before it. It only covers the
    span of the mark tape, so `coverage` is published and a split below half
    is not printed — a regime finding on 4 of 184 rows is a decoration (I6).
    """
    up, dn, unknown = [], [], 0
    for r in rows:
        v = None
        ex = r[4] if len(r) > 4 else None
        if isinstance(ex, dict) and isinstance(ex.get("btc_regime_up"), bool):
            v = ex["btc_regime_up"]
        elif btc:
            then = price_at(btc, "BTC", r[2] - dt.timedelta(hours=lookback_h),
                            max_gap_h=2.0)
            now = price_at(btc, "BTC", r[2], max_gap_h=2.0)
            if then and now:
                v = now > then
        if v is True:
            up.append(r)
        elif v is False:
            dn.append(r)
        else:
            unknown += 1
    out = {"coverage": (len(up) + len(dn)) / len(rows) if rows else 0.0,
           "n_up": len(up), "n_down": len(dn), "unknown": unknown}
    for k, v in (("up", up), ("down", dn)):
        out[k] = (G.stats(v) if len(v) >= 2 else None)
    return out


# --------------------------------------------------------------------------
# correlation
# --------------------------------------------------------------------------
def daily_pnl(full_rows):
    d = collections.defaultdict(float)
    for r in full_rows:
        d[r[2].date()] += r[1]
    return d


def corr(a, b):
    ks = sorted(set(a) & set(b))
    if len(ks) < 8:
        return None, len(ks)
    x = [a[k] for k in ks]
    y = [b[k] for k in ks]
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sx = math.sqrt(sum((v - mx) ** 2 for v in x))
    sy = math.sqrt(sum((v - my) ** 2 for v in y))
    if sx <= 0 or sy <= 0:
        return None, len(ks)
    return sum((x[i] - mx) * (y[i] - my) for i in range(len(ks))) / (sx * sy), len(ks)


def n_eff(cmat, names):
    """Correlation-aware effective bet count — NEVER a count of distinct rows.

    `fleet_risk` publishes `1/HHI` over distinct symbols and so reports 9.0 for
    nine correlated longs (I22, measured). This is the eigenvalue form: for an
    equal-weighted book of k arms with mean pairwise rho, N_eff = k / (1 +
    (k-1)*rho).
    """
    k = len(names)
    if k < 2:
        return k, 0.0
    vals = [cmat[(a, b)] for i, a in enumerate(names) for b in names[i + 1:]
            if cmat.get((a, b)) is not None]
    if not vals:
        return k, 0.0
    rho = statistics.fmean(vals)
    denom = 1.0 + (k - 1) * rho
    return (k / denom if denom > 0 else float(k)), rho


# --------------------------------------------------------------------------
# selftest — the moves-nothing proof + estimator checks
# --------------------------------------------------------------------------
_FORBIDDEN = {"write_levers", "get_lever", "market_open", "publish",
              "publish_paper_trade", "set_state", "write_state",
              "claim_writer", "snapshot_equity"}


def _selftest():
    with open(os.path.abspath(__file__)) as _fh:
        src = _fh.read()
    tree = ast.parse(src)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, "attr", None) or getattr(f, "id", None)
            if name:
                called.add(name)
    bad = called & _FORBIDDEN
    assert not bad, f"this file must move nothing; found call(s): {sorted(bad)}"

    # `batches` must group a basket close into ONE decision and keep distinct
    # decisions apart. A mutation that returns one batch per leg (the i.i.d.
    # error this exists to prevent) reddens here.
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    rs = [(0.0, 1.0, t0, t0), (0.0, 1.0, t0 + dt.timedelta(seconds=5), t0),
          (0.0, 1.0, t0 + dt.timedelta(hours=3), t0)]
    bs = batches(rs)
    assert [len(b) for b in bs] == [2, 1], [len(b) for b in bs]

    # A path with a known drawdown must report it, on the GATE's denominator:
    # peak 110, trough 104, book 100 -> 6/100 = 6%. Dividing by the running
    # peak instead would say 5.45% and quietly disagree with the 15% bar.
    f, d, run, lo = _path_stats([10.0, -6.0, 2.0], 100.0)
    assert abs(f - 106.0) < 1e-9 and abs(d - 0.06) < 1e-9, (f, d)
    # `lo` is the low-water mark of the whole path, START INCLUDED — a book
    # that never dips below its opening balance has a low of that balance, and
    # excluding the start would report a trough it never reached.
    assert run == 1 and abs(lo - 100.0) < 1e-9, (run, lo)
    # ...and it must agree with `golive_readiness.stats` on the same rows,
    # which is the only check that makes the paragraph above enforceable.
    _t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    _rs = [(0.01, 10.0, _t0), (-0.006, -6.0, _t0 + dt.timedelta(hours=1)),
           (0.002, 2.0, _t0 + dt.timedelta(hours=2))]
    _s = G.stats(_rs, book_usd=100.0)
    assert abs(_s["max_dd_frac"] - d) < 1e-9, (_s["max_dd_frac"], d)

    # `simulate`'s edge_mult must move the MEAN and leave the SPREAD alone —
    # a mutation that scales every return instead reddens on the sd check.
    rng = random.Random(7)
    units = [[0.05], [-0.03], [0.02], [-0.01]]
    base = simulate(units, 200, 300, 0.0, random.Random(7))
    up = simulate(units, 200, 300, 0.0, rng, edge_mult=2.0)
    assert statistics.fmean(up["final"]) > statistics.fmean(base["final"])
    sd_b = statistics.pstdev(base["final"])
    sd_u = statistics.pstdev(up["final"])
    assert abs(sd_u - sd_b) / max(sd_b, 1e-9) < 0.35, (sd_b, sd_u)

    # ruin must be MONOTONE in position size on a losing book, and the
    # compounding must bound equity below at zero.
    losers = [[-0.05]] * 3 + [[0.04]]
    rc = ruin_curve(losers, 60, 300, random.Random(3), [0.5], [0.05, 0.20])
    assert rc[0.2]["p_ruin"][0.5] >= rc[0.05]["p_ruin"][0.5], rc
    assert rc[0.2]["p05_final"] >= 0.0

    # THE SIZING SCALE. `f` is the equity fraction, so a book of +1%/trade
    # positions held at f=10% must compound at ~0.1%/trade, NOT 1%. The
    # original defect returned the f=clip case unscaled and read 6.5x on a
    # book that made 16%; this pins the scale directly.
    flat = [[0.01]] * 100
    r10 = ruin_curve(flat, 50, 40, random.Random(5), [0.5], [0.10])[0.1]
    assert abs(r10["median_final"] - 1.001 ** 50) < 1e-6, r10["median_final"]
    r20 = ruin_curve(flat, 50, 40, random.Random(5), [0.5], [0.20])[0.2]
    assert r20["median_final"] > r10["median_final"]

    # ...and the second gate must REFUSE a simulator that disagrees with the
    # book by an order of magnitude, while passing one that agrees.
    ok_good, _, _ = calibrate_ruin([[0.01]] * 40, 40, 0.10, 4.9, 1000.0,
                                   draws=60)
    assert ok_good, "an agreeing simulator must pass"
    ok_bad, _, _ = calibrate_ruin([[0.01]] * 40, 40, 0.10, 400.0, 1000.0,
                                  draws=60)
    assert not ok_bad, "a 10x disagreement must be REFUSED"

    # price_at must REFUSE beyond the gap rather than extrapolate.
    tape = {"X": [(t0, 100.0), (t0 + dt.timedelta(hours=1), 110.0)]}
    assert price_at(tape, "X", t0 + dt.timedelta(minutes=30)) in (100.0, 110.0)
    assert price_at(tape, "X", t0 + dt.timedelta(days=30)) is None

    # n_eff must collapse correlated arms — nine perfectly correlated books
    # are ONE bet, and a symbol count would say nine.
    names = [f"b{i}" for i in range(9)]
    cm = {(a, b): 1.0 for i, a in enumerate(names) for b in names[i + 1:]}
    ne, rho = n_eff(cm, names)
    assert abs(ne - 1.0) < 1e-6 and abs(rho - 1.0) < 1e-9, (ne, rho)

    # the halves-tie detector must fire ONLY when the boundary is genuinely
    # inside a tie. A mutation that always returns True would excuse a real
    # h1/h2 disagreement on every book, which is the gate going blind.
    _a = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    _b = _a + dt.timedelta(hours=1)
    tied = [(0, 0, _a), (0, 0, _b), (0, 0, _b), (0, 0, _b)]        # mid=2
    clear = [(0, 0, _a), (0, 0, _a), (0, 0, _b), (0, 0, _b)]       # mid=2
    assert halves_tie_ambiguous(tied) is True
    assert halves_tie_ambiguous(clear) is False
    assert halves_tie_ambiguous([(0, 0, _a)]) is False

    # the owners are IMPORTED, not copied: pin by identity (the (hj) rule).
    assert G.horizon_crit(30) == A.t_crit(30)
    assert MIN_N_SIM is A.MIN_N
    print("selftest OK — moves nothing; estimators pinned; owners by identity")


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def _f(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def report_mc(bot, gr_live, g, args, rng, caps=None):
    rows, full = g["rows"], g["full"]
    st = g["stats"]
    n = st.get("n", 0)
    if n < MIN_N_SIM:
        print(f"  {bot}: n={n} < {MIN_N_SIM} — NOT SIMULATED "
              f"(a bootstrap here resamples noise; {A.MIN_N} is "
              f"fleet_allocation's own computability floor)")
        return None
    units = ([[r[1]] for r in rows] if args.iid
             else [[x[1] for x in b] for b in batches(rows)])
    n_draw = len(units)
    sz = sizing(full)
    live = (gr_live.get("books") or {}).get(bot) or {}
    max_open = (caps or {}).get(bot)
    book_usd = 1000.0
    base = simulate(units, n_draw, args.draws, book_usd, rng)
    obs_dd = abs(st.get("max_dd_usd", 0.0)) / book_usd
    obs_run = (st.get("shape") or {}).get("streak_max")
    lb = A.lower_bound([r[0] for r in rows])

    print(f"\n  {bot}")
    print(f"    sample        n={n} legs · {len(units)} decisions · "
          f"{_f(st.get('days'),1)}d · era {g['era_iso']}")
    print(f"    grade         mean {_f(100*st['mean_pct'],3)}%/trade · "
          f"t {_f(st['t'],2)} · t_crit(n) {_f(A.t_crit(n),3)} · "
          f"lower bound {_f(100*lb,3)}%/trade")
    print(f"    realised      net ${_f(st.get('realised_usd'),2)} · "
          f"maxDD {_f(100*obs_dd,2)}% (gate reads "
          f"{live.get('max_dd_pct')}% incl. MTM)")
    print(f"    DRAWDOWN      observed {_f(100*obs_dd,2)}%  |  "
          f"sim p50 {_f(100*pct(base['dd'],.5),2)}%  "
          f"p90 {_f(100*pct(base['dd'],.9),2)}%  "
          f"p95 {_f(100*pct(base['dd'],.95),2)}%  "
          f"p99 {_f(100*pct(base['dd'],.99),2)}%")
    over = sum(1 for d in base["dd"] if d > G.GOLIVE_MAX_DD) / len(base["dd"])
    print(f"    P(maxDD > {100*G.GOLIVE_MAX_DD:.0f}% gate bar) = {100*over:.1f}%"
          f"   [the bar is graded on ONE path; this is the distribution]")
    print(f"    STREAK        observed {obs_run} losses  |  "
          f"sim p50 {pct(base['run'],.5)}  p95 {pct(base['run'],.95)}  "
          f"p99 {pct(base['run'],.99)}  max {max(base['run'])}")
    ch = st.get("shape", {}).get("streak_chance") or {}
    print(f"                  chance for this hit rate: p50 {ch.get('p50')} "
          f"p95 {ch.get('p95')}  (golive_readiness.expected_streak)")
    p_loss = sum(1 for f in base["final"] if f < book_usd) / len(base["final"])
    print(f"    P&L           P(book below start after {len(units)} decisions) "
          f"= {100*p_loss:.1f}%")
    for tgt in (1.10, 1.25, 1.50):
        p = sum(1 for f in base["final"] if f >= book_usd * tgt) / len(base["final"])
        print(f"                  P(reach +{100*(tgt-1):.0f}%) = {100*p:.1f}%")
    res95 = book_usd * pct(base["dd"], 0.95)
    res99 = book_usd * pct(base["dd"], 0.99)
    print(f"    RESERVE       to survive p95 drawdown: ${res95:.0f} "
          f"({100*pct(base['dd'],.95):.1f}% of book) · "
          f"p99: ${res99:.0f} ({100*pct(base['dd'],.99):.1f}%)")
    if sz:
        print(f"    SIZING        median clip ${sz['clip_usd']:.2f} = "
              f"{100*sz['clip_frac']:.1f}% of a $1,000 book "
              f"(range ${sz['clip_lo']:.0f}–${sz['clip_hi']:.0f})")
    print("    VARIED EDGE   (mean scaled, dispersion held — leverage is "
          "mean+sd alike and would say nothing, I22)")
    for m in (0.0, 0.5, 0.75, 1.0):
        s = simulate(units, n_draw, max(2000, args.draws // 4), book_usd,
                     random.Random(101), edge_mult=m)
        pl = sum(1 for f in s["final"] if f < book_usd) / len(s["final"])
        print(f"        edge x{m:<4} P(loss) {100*pl:5.1f}%  "
              f"dd p95 {100*pct(s['dd'],.95):5.2f}%  "
              f"median final ${pct(s['final'],.5):,.0f}")
    stress = simulate(units, n_draw, max(2000, args.draws // 4), book_usd,
                      random.Random(202),
                      cost_per_leg=(RT_BPS_P90 - RT_BPS_MEDIAN) / 1e4
                      * (sz["clip_usd"] if sz else 100.0))
    print(f"        +p90 slip  P(loss) "
          f"{100*sum(1 for f in stress['final'] if f<book_usd)/len(stress['final']):5.1f}%"
          f"  median final ${pct(stress['final'],.5):,.0f}"
          f"   [{RT_BPS_MEDIAN}->{RT_BPS_P90}bps rt, measured band]")

    if sz and sz["clip_frac"] > 0:
        pctu = ([[r[0]] for r in rows] if args.iid
                else [[x[0] for x in b] for b in batches(rows)])
        cf = round(sz["clip_frac"], 4)
        conc = concurrency(full)
        kj = max(1, int(round(conc["mean"]))) if conc else 1
        # the book's own OPEN-ordered leg returns: a contiguous slice of this
        # is a set of legs that were genuinely live together, carrying the
        # co-movement they actually had.
        _bo = sorted(full, key=lambda r: str(r[7].get("opened_at") or ""))
        blockseq = [r[0] for r in _bo]
        cal_ok, sim_r, book_r = calibrate_ruin(
            pctu, n_draw, cf, st.get("realised_usd", 0.0), book_usd)
        if not cal_ok:
            print(f"    RISK OF RUIN  WITHHELD — at the shipped f={100*cf:.1f}% "
                  f"the simulator returns {100*sim_r:+.1f}% against the book's "
                  f"own {100*book_r:+.1f}%. A sizing model that cannot "
                  f"reproduce the book's realised return may not price its "
                  f"ruin ((gx), applied to the simulator).")
            return base
        fr = sorted(set(round(x, 4) for x in
                        [0.02, 0.05, 0.10, cf, 0.25, 0.40]))
        rc = ruin_curve(pctu, n_draw, max(2000, args.draws // 5),
                        random.Random(303), [0.5, 0.25], fr, k_joint=kj,
                        block=blockseq)
        rc_seq = ruin_curve(pctu, n_draw, max(2000, args.draws // 5),
                            random.Random(303), [0.5, 0.25], fr, k_joint=1)
        if conc:
            print(f"    CONCURRENCY   mean {conc['mean']:.2f} open · p90 "
                  f"{conc['p90']} · peak {conc['peak']} · cap "
                  f"{max_open or '?'} · {100*conc['overlap_frac']:.0f}% of legs "
                  f"opened while others were held")
        print(f"    RISK OF RUIN  (f = equity fraction PER POSITION; gross = "
              f"f x {kj} concurrent; calibrated sim {100*sim_r:+.1f}% vs book "
              f"{100*book_r:+.1f}%)")
        print(f"        {'f':>7s} {'gross':>7s} {'P(-50%)':>9s} {'P(-75%)':>9s} "
              f"{'median':>9s} {'E[log]':>9s}   {'[seq P(-50%)]':>14s}")
        for f, v in sorted(rc.items()):
            mark = "  <- shipped" if abs(f - cf) < 1e-4 else ""
            sq = rc_seq[f]["p_ruin"][0.5]
            print(f"        {100*f:6.1f}% {100*f*kj:6.0f}% "
                  f"{100*v['p_ruin'][0.5]:8.1f}% {100*v['p_ruin'][0.25]:8.1f}% "
                  f"{v['median_final']:9.2f}x {v['mean_log']:9.4f}   "
                  f"{100*sq:13.1f}%{mark}")
        print(f"        The last column is the SEQUENTIAL model this file "
              f"published first. Where it reads 0.0% beside a real number, it "
              f"was inviting a size it cannot price.")
    return base


def main():
    ap = argparse.ArgumentParser()
    for a in ("calibrate", "mc", "bench", "splits", "corr", "ratios", "all",
              "selftest", "iid", "refresh"):
        ap.add_argument(f"--{a}", action="store_true")
    ap.add_argument("--book", default=None)
    ap.add_argument("--draws", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20260907)
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return 0
    if args.all:
        args.mc = args.bench = args.splits = args.corr = True
        args.ratios = True
    if not (args.mc or args.bench or args.splits or args.corr or args.ratios):
        args.calibrate = True

    rng = random.Random(args.seed)
    raw, bus = load_feed(args.refresh)
    gr = bus.get("golive_readiness") or {}
    as_of = _parse(gr.get("updated") or gr.get("updated_at"))
    # [(nk)] the retired-sleeve map, read from the books' OWN payloads exactly
    # as the publisher reads it — never a list here.
    sleeves, caps = {}, {}
    for b in (_get(f"{FEED}/pnl.json", os.path.join(CACHE, "pnl.json"),
                   args.refresh).get("bots") or []):
        rs = G.retired_sleeves(b.get("extra"))
        if rs:
            sleeves[str(b.get("bot"))] = rs
        ex = b.get("extra")
        if isinstance(ex, dict) and isinstance(ex.get("max_open"), int):
            caps[str(b.get("bot"))] = ex["max_open"]
    books, dropped = normalise(raw, as_of=as_of)
    grades = graded(books, sleeve_retired=sleeves)

    ok, checked, fails = calibrate(gr, grades)
    print(f"  ledger        {len(raw)} rows fetched · dropped "
          + " · ".join(f"{k}={v}" for k, v in sorted(dropped.items()))
          + f" · {len(books)} books\n")
    if not ok:
        print("REFUSED: this harness cannot reproduce the live grade, so it "
              "may not speak about what would have happened ((gx)).")
        return 2
    if args.calibrate and not (args.mc or args.bench or args.splits
                               or args.corr or args.ratios):
        return 0

    live_books = set((gr.get("books") or {}).keys())
    sel = [b for b in sorted(grades) if b in live_books]
    if args.book:
        sel = [b for b in sel if args.book in b]

    if args.mc:
        print("=" * 78)
        print(f"MONTE CARLO — {args.draws:,} paths · resampling "
              f"{'i.i.d. LEGS' if args.iid else 'DECISION BATCHES'} "
              f"(cluster window {G.CLUSTER_WINDOW_S:.0f}s)")
        print("=" * 78)
        for b in sel:
            report_mc(b, gr, grades[b], args, rng, caps=caps)
        print()

    if args.ratios:
        print("=" * 78)
        print("RISK-ADJUSTED RETURN + REGIME  (per-trade first; annualised is "
              "derived at the book's own close rate)")
        print("=" * 78)
        print(f"  {'book':32s} {'n':>4s} {'mean%':>7s} {'Sharpe':>7s} "
              f"{'Sortino':>8s} {'ShrpAnn':>8s} {'SortAnn':>8s} {'PF':>6s} "
              f"{'ddP95%':>7s} {'obsDD%':>7s}")
        print("  " + "-" * 96)
        for b in sel:
            g = grades[b]
            rows = g["rows"]
            rr = ratios(rows)
            if not rr:
                continue
            st = g["stats"]
            units = [[x[1] for x in bt] for bt in batches(rows)]
            sim = simulate(units, len(units), 4000, 1000.0, random.Random(11))
            obs = abs(st.get("max_dd_usd", 0.0)) / 1000.0
            print(f"  {b:32s} {rr['n']:4d} {100*rr['mean']:+7.3f} "
                  f"{_f(rr['sharpe_trade'],3):>7s} {_f(rr['sortino_trade'],3):>8s} "
                  f"{_f(rr['sharpe_ann'],2):>8s} {_f(rr['sortino_ann'],2):>8s} "
                  f"{_f(rr['profit_factor'],2):>6s} "
                  f"{100*pct(sim['dd'],.95):7.2f} {100*obs:7.2f}")
        _btc = {"BTC": (marks_series(bus.get("history") or []).get("BTC") or [])}
        print(f"\n  REGIME — derived from the scout's own BTC marks over the "
              f"tape's {len(_btc['BTC'])} snapshots. Per-close "
              f"`extra.btc_regime_up` coverage in the ledger is 0%: the flag "
              f"rides the SUMMARY row, never the trade.")
        _any = False
        for b in sel:
            rs = regime_split(grades[b]["rows"], btc=_btc)
            if rs["coverage"] < 0.5:
                continue
            _any = True
            up, dn = rs["up"], rs["down"]
            print(f"    {b:32s} coverage {100*rs['coverage']:3.0f}%  "
                  f"BTC-up n={rs['n_up']:3d} mean "
                  f"{(f'{100*up[chr(109)+chr(101)+chr(97)+chr(110)+chr(95)+chr(112)+chr(99)+chr(116)]:+.3f}%' if up else '   n/a '):>8s}"
                  f"   BTC-down n={rs['n_down']:3d} mean "
                  f"{(f'{100*dn[chr(109)+chr(101)+chr(97)+chr(110)+chr(95)+chr(112)+chr(99)+chr(116)]:+.3f}%' if dn else '   n/a '):>8s}")
        if not _any:
            print("    (no book has >=50% of its era closes inside the "
                  "8.3-day mark tape — regime attribution is NOT AVAILABLE "
                  "for the graded eras, and no split is invented)")
        print()

    if args.splits:
        print("=" * 78)
        print("CHRONOLOGICAL SPLITS + WALK-FORWARD (out-of-sample stability)")
        print("=" * 78)
        for b in sel:
            rows = grades[b]["rows"]
            if len(rows) < 24:
                continue
            sp = split_stats(rows)
            print(f"\n  {b}")
            for k in ("train", "valid", "test"):
                s = sp[k]
                if s.get("n", 0) < 2:
                    print(f"    {k:6s} n={s.get('n')}  (too thin)")
                    continue
                print(f"    {k:6s} n={s['n']:4d}  mean {100*s['mean_pct']:+7.3f}%"
                      f"  t {s['t']:+6.2f}  net ${s['realised_usd']:+8.2f}")
            wf = walk_forward(rows)
            if wf:
                pos = sum(1 for f in wf if (f["test_mean"] or 0) > 0)
                print(f"    walk-forward folds: {len(wf)} · positive OOS "
                      f"{pos}/{len(wf)} · OOS means "
                      + ", ".join(f"{100*(f['test_mean'] or 0):+.2f}%" for f in wf))
        print()

    if args.corr:
        print("=" * 78)
        print("PORTFOLIO CORRELATION — are these separate bets?")
        print("=" * 78)
        series = {b: daily_pnl(grades[b]["full"]) for b in sel
                  if len(grades[b]["full"]) >= 12}
        names = sorted(series)
        cm = {}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                c, k = corr(series[a], series[b])
                cm[(a, b)] = c
        ne, rho = n_eff(cm, names)
        print(f"  books with a usable daily series : {len(names)}")
        print(f"  mean pairwise correlation        : {_f(rho,3)}")
        print(f"  effective independent bets N_eff : {_f(ne,2)} of {len(names)}")
        top = sorted(((v, a, b) for (a, b), v in cm.items() if v is not None),
                     reverse=True)[:8]
        print("  most-correlated pairs:")
        for v, a, b in top:
            print(f"     {v:+.3f}  {a}  ~  {b}")
        # drawdown overlap: do the books lose on the SAME days?
        alld = collections.defaultdict(float)
        for b in names:
            for d, v in series[b].items():
                alld[d] += v
        days = sorted(alld)
        worst = sorted(days, key=lambda d: alld[d])[:5]
        print("  worst FLEET days (all selected books summed):")
        for d in worst:
            contrib = sorted(((series[b].get(d, 0.0), b) for b in names))[:3]
            print(f"     {d}  ${alld[d]:+8.2f}   led by "
                  + ", ".join(f"{b.split('-')[0]} ${v:+.2f}" for v, b in contrib))
        print()

    if args.bench:
        print("=" * 78)
        print("BENCHMARKS — identical window, identical assets, identical costs")
        print("=" * 78)
        tape = price_tape(raw)
        mk_all = marks_series(bus.get("history") or [])
        wstart, wend, mk = common_window(mk_all)
        sv = bench_sma_and_vol(mk)
        print(f"  price tape: {len(tape)} coins from the fleet's own executed "
              f"fills · {len(mk_all)} coins from the scout's 5-min marks")
        if sv:
            span = ((wend - wstart).total_seconds() / 86400.0
                    if wstart and wend else None)
            print(f"\n  VENUE-WIDE, scout mark tape ({sv['n_assets']} of "
                  f"{len(mk_all)} coins cover the full span, "
                  f"{_f(span,1)} days — the ONLY window with regular bars):")
            print(f"    buy & hold        mean {100*sv['bh_mean']:+7.2f}%  "
                  f"median {100*sv['bh_median']:+7.2f}%")
            print(f"    SMA {12}/{48} cross    mean {100*sv['sma_mean']:+7.2f}%  "
                  f"median {100*sv['sma_median']:+7.2f}%  "
                  f"(median {sv['sma_flips_median']:.0f} flips, "
                  f"{RT_BPS_MEDIAN}bps each)")
            print(f"    volatility-only   {100*sv['volonly_ret']:+7.2f}%  "
                  f"(inverse-vol weights, no directional view)")
            print(f"    cash / stablecoin   +0.00%  "
                  f"(Lighter pays no yield on collateral — exact, not modelled)")
        # ---- ARM A: every benchmark on ONE window, ONE tape ----------------
        if mk and wstart and wend:
            print(f"\n  MATCHED WINDOW — {wstart:%d-%b} to {wend:%d-%b} "
                  f"({(wend-wstart).total_seconds()/86400:.1f}d), the only "
                  f"span with REGULAR bars for every arm. Each book's own\n"
                  f"  realised return over that identical window, beside the "
                  f"passive alternatives on the same coins and the same "
                  f"{RT_BPS_MEDIAN}bps round trip:")
            print(f"    {'arm':34s} {'return':>9s}  basis")
            print(f"    {'-'*34} {'-'*9}  {'-'*40}")
            for b in sel:
                w = [r for r in grades[b]["rows"] if wstart <= r[2] <= wend]
                if len(w) < 3:
                    continue
                tot = sum(r[1] for r in w) / 1000.0
                print(f"    {b:34s} {100*tot:+8.2f}%  {len(w)} closes, its own "
                      f"ledger, $1,000 book")
            print(f"    {'BENCHMARK buy & hold':34s} {100*sv['bh_mean']:+8.2f}%"
                  f"  equal-weight, {sv['n_assets']} coins")
            print(f"    {'BENCHMARK SMA 12/48':34s} {100*sv['sma_mean']:+8.2f}%"
                  f"  same coins, {sv['sma_flips_median']:.0f} median flips")
            print(f"    {'BENCHMARK volatility-only':34s} "
                  f"{100*sv['volonly_ret']:+8.2f}%  inverse-vol weights, no view")
            print(f"    {'BENCHMARK cash / stablecoin':34s} {0.0:+8.2f}%"
                  f"  Lighter pays no yield on collateral")

        # ---- ARM B: the per-book null over each book's FULL window ---------
        print("\n  PER-BOOK, each over its OWN full window:")
        for b in sel:
            g = grades[b]
            rows, full = g["rows"], g["full"]
            if len(rows) < MIN_N_SIM:
                continue
            st = g["stats"]
            t0, t1 = rows[0][2], rows[-1][2]
            pairs = {(r[6] or "").split("/")[0] for r in full}
            bh = bench_buy_hold(tape, pairs, t0, t1, RT_BPS_MEDIAN)
            re_ = bench_random_entry(tape, full, rng, RT_BPS_MEDIAN, draws=400)
            print(f"\n  {b}   ({_f(st.get('days'),1)}d, {len(pairs)} coins traded)")
            print(f"    THE BOOK          {100*st['mean_pct']:+7.3f}%/trade   "
                  f"net ${st['realised_usd']:+.2f} on $1,000")
            if bh and bh.get("withheld"):
                print(f"    buy & hold        WITHHELD — only "
                      f"{100*bh['coverage']:.0f}% of its coins are priceable at "
                      f"both endpoints (floor {100*BH_MIN_COVERAGE:.0f}%); a "
                      f"{bh['n_assets']}-of-{bh['n_assets']+bh['missing']} "
                      f"subsample is not a benchmark")
            elif bh:
                print(f"    buy & hold        {100*bh['mean_ret']:+7.3f}% per "
                      f"asset over the window ({bh['n_assets']} priced, "
                      f"{100*bh['coverage']:.0f}% coverage)")
            if re_:
                edge = st["mean_pct"] - re_["mean_ret"]
                p = null_p(re_["_dist"], st["mean_pct"])
                print(f"    random entry      {100*re_['mean_ret']:+7.3f}%/trade "
                      f"[p05 {100*re_['p05']:+.3f}% p95 {100*re_['p95']:+.3f}%, "
                      f"{re_['draws']} draws]")
                print(f"    EXCESS over random{100*edge:+7.3f}%/trade   "
                      f"P(random >= book) = {p:.3f}  "
                      f"{'-> edge SURVIVES the null' if p <= 0.05 else '-> NOT distinguishable from a random entry on the same coins'}")
            print(f"    cash               +0.000%/trade")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
