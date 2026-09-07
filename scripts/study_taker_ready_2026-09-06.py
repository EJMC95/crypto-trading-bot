#!/usr/bin/env python3
"""🎫 THE FIRST BOOK EVER TO PASS THE GO-LIVE GATE — STRESSED BEFORE IT MOVES MONEY.

On 2026-09-06 `golive-readiness` returned the fleet's **first-ever `ready:
True`**: `lighter-ticket-taker-lshadow`, 6 of 6 bars, n=183 in-era,
+1.195%/trade, t=2.63, maxDD 5.4%, window 37.1d. Go-live is Eamon's explicit
act and nothing here takes it. What this instrument does is ask the question
this repo's own doctrine puts in front of that act:

**(hm), 30-Jul: GRADE A DIRECTIONAL BOOK AGAINST A RANDOM-ENTRY BENCHMARK,
NEVER AGAINST ZERO.** On this venue a random short earned +0.2% to +1.1% per
trade for free, and when (hm) ran that null ON THIS BOOK, six independent runs
put P(coin flip >= taker) at **0.55-0.84** — random BEAT it. That reading is
PRE-ERA (the current era starts 2026-07-30T11:09:46Z on a policy stamp) and
was taken on a far smaller sample, so it does not settle today's verdict. It
does mean the verdict is not settled by the six bars alone.

**WHAT THIS INSTRUMENT CAN AND CANNOT DO, stated first because the limit is
the finding's boundary.** The full (hm) null needs a price tape over the whole
era. It is NOT available from this egress:

  * the venue's `/api/v1/candlesticks` returns **403 from every egress outside
    the production containers** (measured 19-Aug from this container and from
    GitHub Actions runners, every market_id — recorded in
    `study_mum_autopsy_2026-08-19`), and substituting another venue's tape is
    refused outright by the venue-purity rule;
  * the fleet's own recorded tape — the scout's 5-min `marks` snapshots on
    `/bus.json?hours=` — is capped at **~2,357 snapshots = 8.3 days**, i.e.
    **22% of the 38-day era**. `DATABASE_URL` would reach further through
    `bot_pnl_store.fetch_state_history`; this session has none.

So the full null is NOT RUN and is NOT CLAIMED. What IS run is exact, needs no
tape, and speaks directly to the alternative (hm) actually names — **drift**:

  1. **THE SIDE SPLIT.** Drift is directional by definition. A tape that pays
     longs must charge shorts. A book earning on BOTH sides cannot have drift
     as its explanation, and one earning on a single side is exactly what (hm)
     warns about. This is the sharpest candle-free test of the hypothesis and
     it runs on the whole era.
  2. **THE LENS SPLIT**, because the book is five books wearing one row.
  3. **CLUSTER-ROBUST t** ((kw)/(ky)): the taker opens several positions per
     cycle off one ticket sweep, so closes are not independent draws and the
     naive t overstates. Clustered by UTC day AND by the open instant.
  4. **CONCENTRATION** ((po)'s undecidable-by-tail check): the top-3 share and
     the ex-top-3 reading. `t` assumes an approximately normal mean.
  5. **BREAK-EVEN COST**: how much round-trip friction the mean absorbs before
     it is zero — this venue is zero-fee, so the number that matters is slippage.

**CALIBRATION GATE (the `(gx)` rule, and it REFUSES).** A harness that cannot
reproduce what DID happen may not say what WOULD have. This reproduces the
live `golive-readiness` grade — n, mean, t — from the public ledger through
the grader's OWN owners (`era_rows`, `stats`, `is_phantom_close`,
`is_quarantined`) and **exits 2 without printing a verdict** if it disagrees
beyond tolerance.

Usage:
  python3 scripts/study_taker_ready_2026-09-06.py
  python3 scripts/study_taker_ready_2026-09-06.py --bot freqtrade-mum-lshadow
  python3 scripts/study_taker_ready_2026-09-06.py --selftest
"""
import argparse
import json
import math
import os
import statistics as st
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import golive_readiness as G                                   # noqa: E402
import bot_pnl_store as store                                  # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
BOT = "lighter-ticket-taker-lshadow"
#: the ledger cap `/trades.json` enforces. A returned count EQUAL to this is a
#: truncation signature ((qz)) and this instrument refuses on it.
FEED_LIMIT = 5000
#: calibration tolerance against the live grade. Tight on purpose — the two
#: samples should be IDENTICAL, so anything above rounding is a real
#: disagreement about which rows describe the book.
TOL_MEAN_PP = 0.02
TOL_T = 0.05


def _get(url, timeout=90):
    r = subprocess.run(["curl", "-fsS", "--max-time", str(timeout), url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"fetch failed: {url}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def _ts(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def load_rows(bot):
    """The book's closes from the public feed, filtered EXACTLY as the grader
    filters them: quarantine, then phantom, then era — each through its owner.

    `/trades.json` serves RAW column names and does NOT apply
    `LEDGER_QUARANTINE` ((wo)), so both filters are applied here. `stats`
    wants `(pnl_pct, pnl_abs, closed_at)`; `era_rows` wants the open appended.
    """
    d = _get(f"{DASH}/trades.json?source=paper&limit={FEED_LIMIT}")
    raw = d if isinstance(d, list) else (d.get("trades") or d.get("rows") or [])
    if len(raw) >= FEED_LIMIT:
        raise RuntimeError(f"feed returned {len(raw)} == the {FEED_LIMIT} cap "
                           f"— truncated, refusing to grade a sampled ledger")
    keep = []
    for r in raw:
        if r.get("bot") != bot:
            continue
        if store.is_quarantined(bot, r.get("pair"), r.get("closed_at")):
            continue
        if G.is_phantom_close(r):
            continue
        pct, ab = r.get("pnl_pct"), r.get("pnl_abs")
        c, o = _ts(r.get("closed_at")), _ts(r.get("opened_at"))
        if not isinstance(pct, (int, float)) or c is None:
            continue
        # [5] is the feed row (the splits read side/lens off it); [5]["extra"]
        # is what `stamped_policy_boundary` needs — see era_scope.
        keep.append((100.0 * float(pct), ab, c, o, r))
    keep.sort(key=lambda x: x[2])
    return keep


def era_scope(bot, keep):
    """-> (in_era_rows, era_detail). `era_rows` is the ONE owner and it is
    asked for `detail=True` so this reads its own `scoped_rows` back instead
    of re-deriving the predicate — the (hq) rule that importing the scoring
    while re-deriving the sample is how two consumers disagree about a book.

    **The row must be a 5-TUPLE with the feed row's `extra` at [4]**: that is
    where `stamped_policy_boundary` reads `extra.policy`. Passing a 4-tuple
    is not an error — the boundary simply derives NOTHING and the grade falls
    back to the DECLARED era. Caught here by the calibration gate on its first
    run: 261 rows from 17-Jul against the live grade's 183 from the 30-Jul
    policy stamp. A silent widening of a real-money book's graded sample, from
    one missing tuple element.
    """
    # `policy_signature` is handed the row's `extra` DICT, not the row. Passing
    # the feed row itself derives nothing and falls back to the declared era —
    # the second half of the same defect the gate caught on the first run.
    shaped = [(r[0] / 100.0, r[1], r[2], r[3], (r[4] or {}).get("extra"))
              for r in keep]
    d = G.era_rows(bot, shaped, detail=True)
    by = {(round(x[0], 12), x[2]): True for x in d["scoped_rows"]}
    out = [r for r in keep if (round(r[0] / 100.0, 12), r[2]) in by]
    return out, d


def _t(xs):
    n = len(xs)
    if n < 2:
        return None, None, n
    m = st.mean(xs)
    sd = st.pstdev(xs) or 1e-12
    return m, m / (sd / math.sqrt(n)), n


def cluster_t(rows, key):
    """Cluster-robust t over `key(row)` groups — the (kw)/(ky) correction.

    The taker opens several positions in one ticket sweep, so its closes are
    not independent draws; the naive t treats them as if they were. This is the
    grader's own `cluster_stats` idea applied to an arbitrary grouping.
    """
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r[0])
    means = [st.mean(v) for v in g.values()]
    if len(means) < 2:
        return None, None, len(means)
    m = st.mean(means)
    sd = st.pstdev(means) or 1e-12
    return m, m / (sd / math.sqrt(len(means))), len(means)


def intraclass(rows, key):
    """(ICC, n_groups, mean_group_size) — how much of the variance in these
    returns is BETWEEN groups rather than within them.

    Why it is here: choosing a cluster is an analyst's free parameter, and
    (uf) measured that a pooled t over overlapping windows "measures sampling
    density, not edge". So the day-cluster is not asserted — the ICC says how
    dependent same-day closes actually are, and the design effect
    `1 + (m-1)*ICC` converts that into the effective sample size the t bar
    should be reading. ICC <= 0 means the day carries no shared component and
    the iid t is the honest one.
    """
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r[0])
    groups = [v for v in g.values() if v]
    if len(groups) < 2:
        return None, len(groups), 0.0
    n = sum(len(v) for v in groups)
    m = n / len(groups)
    grand = sum(sum(v) for v in groups) / n
    ms_b = sum(len(v) * (st.mean(v) - grand) ** 2 for v in groups) / (len(groups) - 1)
    within_df = n - len(groups)
    if within_df <= 0:
        return None, len(groups), m
    ms_w = sum(sum((x - st.mean(v)) ** 2 for x in v) for v in groups) / within_df
    denom = ms_b + (m - 1) * ms_w
    if denom <= 0:
        return None, len(groups), m
    return (ms_b - ms_w) / denom, len(groups), m


def lens_of(r):
    """`<side>-<lens>_<exit>` — the taker's own close tag."""
    parts = str((r[4].get("reason") or "")).split("_")[0].split("-")
    return parts[1] if len(parts) > 1 else "?"


def exit_of(r):
    reason = str(r[4].get("reason") or "")
    return reason.split("_", 1)[1] if "_" in reason else "?"


def side_of(r):
    s = r[4].get("side")
    if s in ("long", "short"):
        return s
    return str((r[4].get("reason") or "")).split("-")[0] or "?"


def calibrate(bot, era, live, as_of=None):
    """REFUSE unless this sample reproduces the live grade. -> (ok, detail).

    `as_of` is the live payload's OWN `updated` stamp. `golive-readiness`
    publishes on a 6-hourly loop, so by the time this runs the ledger has
    usually moved on — measured on the first clean run: n=184 here against 183
    published, with mean and t both inside tolerance. Calibrating on the full
    fresher sample would then refuse for being RIGHT. Trimming to the closes
    the published grade could actually have seen makes the comparison exact,
    and the verdict below is still reported over the whole era.
    """
    if as_of is not None:
        era = [r for r in era if r[2] <= as_of]
    s = G.stats([(r[0] / 100.0, r[1], r[2]) for r in era])
    # `stats` returns the mean as a FRACTION; the payload publishes
    # `round(100 * st["mean_pct"], 3)`. Comparing the two raw is a unit error
    # of exactly 100x — the shape this fleet has already paid for once.
    mine = {"n": s.get("n"),
            "mean_pct": (None if s.get("mean_pct") is None
                         else round(100.0 * s["mean_pct"], 3)),
            "t": (None if s.get("t") is None else round(s["t"], 3))}
    if not live:
        return False, {"why": "no live grade to calibrate against", "mine": mine}
    d_mean = abs((mine["mean_pct"] or 0) - (live.get("mean_pct") or 0))
    d_t = abs((mine["t"] or 0) - (live.get("t") or 0))
    ok = (mine["n"] == live.get("n")
          and d_mean <= TOL_MEAN_PP and d_t <= TOL_T)
    return ok, {"mine": mine, "live": {k: live.get(k) for k in ("n", "mean_pct", "t")},
                "d_mean_pp": round(d_mean, 4), "d_t": round(d_t, 4),
                "tol": {"mean_pp": TOL_MEAN_PP, "t": TOL_T}}


def report(bot=BOT):
    live_all = _get(f"{DASH}/bus.json").get("golive_readiness") or {}
    live = (live_all.get("books") or {}).get(bot) or {}
    keep = load_rows(bot)
    era, det = era_scope(bot, keep)
    era_iso = det["iso"]
    as_of = _ts(live_all.get("updated"))
    ok, cal = calibrate(bot, era, live, as_of=as_of)
    cal["as_of"] = live_all.get("updated")
    cal["n_now"] = len(era)
    print(f"=== {bot} — the READY verdict, stressed ===")
    print(f"  live grade : ready={live.get('ready')} n={live.get('n')} "
          f"mean={live.get('mean_pct')} t={live.get('t')} "
          f"dd={live.get('max_dd_pct')} bars={live.get('bars')}")
    print(f"  era        : {era_iso}  source={det['source']}  "
          f"({len(keep)} rows fetched, {len(era)} in era)")
    print(f"  calibration: {'PASS' if ok else 'REFUSE'}  {json.dumps(cal)}")
    if not ok:
        print("\n  REFUSING to interpret a sample that does not reproduce the "
              "live grade — a harness that cannot reproduce what DID happen "
              "may not say what WOULD have ((gx)).")
        return 2

    xs = [r[0] for r in era]
    m, t, n = _t(xs)
    print(f"\n  -- the whole era --")
    print(f"     n={n}  mean={m:+.3f}%/trade  t={t:+.2f}  "
          f"win={100.0*sum(1 for x in xs if x > 0)/n:.1f}%")

    print(f"\n  -- (hm)'s alternative: is this DRIFT? a tape that pays longs "
          f"must charge shorts --")
    by = defaultdict(list)
    for r in era:
        by[side_of(r)].append(r[0])
    for s in sorted(by):
        mm, tt, nn = _t(by[s])
        print(f"     {s:6s} n={nn:4d}  mean={mm:+.3f}%/trade  t={tt:+.2f}"
              if mm is not None else f"     {s:6s} n={nn} — too thin")
    both = [s for s in by if (_t(by[s])[0] or 0) > 0 and len(by[s]) >= 10]
    print(f"     -> sides earning at n>=10: {sorted(both) or 'none'}")

    print(f"\n  -- by lens (five books wearing one row) --")
    bl = defaultdict(list)
    for r in era:
        bl[lens_of(r)].append(r[0])
    for k in sorted(bl, key=lambda k: -len(bl[k])):
        mm, tt, nn = _t(bl[k])
        print(f"     {k:12s} n={nn:4d}  mean={mm:+.3f}%  t={tt:+.2f}"
              if mm is not None else f"     {k:12s} n={nn} — too thin")

    print(f"\n  -- by exit --")
    be = defaultdict(list)
    for r in era:
        be[exit_of(r)].append(r[0])
    for k in sorted(be, key=lambda k: -len(be[k])):
        mm, tt, nn = _t(be[k])
        print(f"     {k:12s} n={nn:4d}  mean={mm:+.3f}%  t={tt:+.2f}"
              if mm is not None else f"     {k:12s} n={nn} — too thin")

    print(f"\n  -- cluster-robust t ((kw)/(ky)): the taker opens several "
          f"positions per sweep --")
    for label, key in (("UTC day", lambda r: r[2].date().isoformat()),
                       ("open instant", lambda r: (r[3] or r[2]).isoformat()),
                       ("coin", lambda r: str(r[4].get("pair")))):
        mm, tt, k = cluster_t(era, key)
        print(f"     by {label:13s} clusters={k:4d}  mean={mm:+.3f}%  t={tt:+.2f}"
              if mm is not None else f"     by {label}: too few clusters")

    print(f"\n  -- IS THE DAY THE RIGHT CLUSTER? measured, not asserted --")
    icc, g, avg = intraclass(era, lambda r: r[2].date().isoformat())
    print(f"     intraclass correlation of same-UTC-day closes: "
          f"{'n/a' if icc is None else f'{icc:+.3f}'}  "
          f"({g} days, {avg:.1f} closes/day)")
    print(f"     design effect 1+(m-1)*ICC = "
          f"{'n/a' if icc is None else f'{1 + (avg - 1) * icc:.2f}'}"
          f"  -> n_eff ~ {'n/a' if icc is None else f'{len(era) / max(1e-9, 1 + (avg - 1) * icc):.0f}'}"
          f" of {len(era)}")
    print(f"     the grader's OWN cluster read groups closes within "
          f"{G.CLUSTER_WINDOW_S:.0f}s (built for a basket book that closes 10")
    print(f"     legs at once); this book holds for hours, so that window "
          f"finds no batches and its t is the iid one.")

    print(f"\n  -- the era's policy declares 5 lenses. which produced closes? --")
    declared = sorted(((det.get('policy') or {}).get('lenses')) or [])
    seen = sorted({lens_of(r) for r in era})
    print(f"     declared: {declared}")
    print(f"     produced closes: {seen}")
    silent = [x for x in declared if x not in seen]
    print(f"     SILENT for the whole {len(era)}-close era: {silent or 'none'}")

    print(f"\n  -- concentration ((po)'s undecidable-by-tail check) --")
    tot = sum(r[1] or 0 for r in era)
    top = sorted(era, key=lambda r: -(r[1] or 0))[:3]
    tsum = sum(r[1] or 0 for r in top)
    rest = [r[0] for r in era if r not in top]
    rm, rt, rn = _t(rest)
    print(f"     realised ${tot:+.2f} | top-3 ${tsum:+.2f} = "
          f"{(100.0*tsum/tot if tot else float('nan')):.1f}% of it")
    print(f"     ex-top-3  n={rn}  mean={rm:+.3f}%  t={rt:+.2f}")
    print(f"     top-3: " + ", ".join(
        f"{r[4].get('pair')} {r[0]:+.2f}% ({r[4].get('reason')})" for r in top))

    print(f"\n  -- break-even friction (this venue is zero-FEE; the cost is "
          f"slippage) --")
    print(f"     the mean absorbs {abs(m)*100:.1f} bps of round-trip cost "
          f"before it is zero")

    print(f"\n  -- WHAT IS NOT ANSWERED HERE --")
    print("     the (hm) random-entry null over the FULL era. The venue's")
    print("     candlesticks endpoint is 403 from this egress and the fleet's")
    print("     own recorded tape on /bus.json reaches 8.3 of the era's 38")
    print("     days. Running it needs DATABASE_URL (bot_pnl_store.")
    print("     fetch_state_history) or a production container. NOT RUN, NOT")
    print("     CLAIMED — and it is the one test that stands between a book")
    print("     passing six bars and a directional edge being established.")
    return 0


def _selftest():
    """The detector must be seen to produce a POSITIVE before its silence
    means anything ((po))."""
    class R(dict):
        pass
    def row(pct, ab, day, side, lens, exit_, pair="X/USDC", hour=0):
        c = datetime(2026, 8, day, hour, tzinfo=timezone.utc)
        return (pct, ab, c, c, {"side": side, "pair": pair,
                                "reason": f"{side}-{lens}_{exit_}"})
    rows = [row(1.0, 1.0, 1, "long", "dip", "tp"),
            row(-1.0, -1.0, 1, "short", "dip", "sl"),
            row(3.0, 3.0, 2, "long", "momo", "tp"),
            row(-1.0, -1.0, 2, "short", "momo", "sl")]
    assert side_of(rows[0]) == "long" and side_of(rows[1]) == "short"
    assert lens_of(rows[0]) == "dip" and exit_of(rows[0]) == "tp"
    m, t, n = _t([r[0] for r in rows])
    assert n == 4 and abs(m - 0.5) < 1e-9, (m, n)
    cm, ct, k = cluster_t(rows, lambda r: r[2].date().isoformat())
    assert k == 2 and abs(cm - 0.5) < 1e-9, (cm, k)

    # THE POSITIVE CONTROL, and it is deliberately the CORRELATED fixture:
    # when the rows inside a cluster move together, clustering SHRINKS t,
    # which is the whole reason (kw)/(ky) exist. Note the honest converse,
    # measured on the fixture above: with large WITHIN-cluster spread and
    # small BETWEEN-cluster spread, clustering can RAISE t (0.60 -> 1.41).
    # Clustering is the right denominator, not a conservative one — a guard
    # that assumed it only ever shrinks would be wrong half the time.
    corr = [row(2.0, 2.0, 1, "long", "dip", "tp"),
            row(2.0, 2.0, 1, "long", "dip", "tp"),
            row(-1.0, -1.0, 2, "short", "dip", "sl"),
            row(-1.0, -1.0, 2, "short", "dip", "sl")]
    _m2, t2, _n2 = _t([r[0] for r in corr])
    _cm2, ct2, k2 = cluster_t(corr, lambda r: r[2].date().isoformat())
    assert k2 == 2 and abs(ct2) < abs(t2), (ct2, t2)
    # ICC: the correlated fixture must read POSITIVE and the independent one
    # must not — a dependence estimator that cannot tell them apart is the
    # (po) vacuous check.
    icc_c, gc, _mc = intraclass(corr, lambda r: r[2].date().isoformat())
    assert gc == 2 and icc_c is not None and icc_c > 0.5, (icc_c, gc)
    indep = [row(1.0, 1.0, 1, "long", "dip", "tp"),
             row(-1.0, -1.0, 1, "long", "dip", "sl"),
             row(1.0, 1.0, 2, "long", "dip", "tp"),
             row(-1.0, -1.0, 2, "long", "dip", "sl")]
    icc_i, _gi, _mi = intraclass(indep, lambda r: r[2].date().isoformat())
    assert icc_i is not None and icc_i < 0, icc_i

    # calibration REFUSES on a disagreement and PASSES on a match
    era = [(1.0, 1.0, datetime(2026, 8, 1, tzinfo=timezone.utc), None, {}),
           (3.0, 3.0, datetime(2026, 8, 2, tzinfo=timezone.utc), None, {})]
    s = G.stats([(r[0] / 100.0, r[1], r[2]) for r in era])
    good = {"n": s["n"], "mean_pct": round(100.0 * s["mean_pct"], 3),
            "t": round(s["t"], 3)}
    assert calibrate("x", era, good)[0] is True
    assert calibrate("x", era, dict(good, n=99))[0] is False
    assert calibrate("x", era, dict(good, t=(good["t"] or 0) + 1))[0] is False
    assert calibrate("x", era, {})[0] is False
    print("study_taker_ready selftest OK (side/lens/exit parse, naive vs "
          "cluster t, calibration refuses on n / t / a missing live grade)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", default=BOT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    else:
        sys.exit(report(a.bot))
