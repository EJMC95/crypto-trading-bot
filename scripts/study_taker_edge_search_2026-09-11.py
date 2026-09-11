#!/usr/bin/env python3
"""🎫 THE TICKET TAKER — THE PRE-REGISTERED ENTRY-CELL EDGE SEARCH.

**Eamon, 11-Sep:** *"widen metrics and parameters until you find an edge for
it."* He is right to ask. This is that search run HONESTLY: every cell
declared before a single result exists, every cell PRINTED, and the bar for
calling one an edge stated in advance so a null result cannot be re-dressed
as a finding afterwards.

WHAT IS BEING ASKED, precisely. The book reads READY 6-of-6 — but on this
venue a random entry earns +0.2 to +1.1%/trade for free ((hm)), so the unit
here is the **paired difference against a matched-random entry**, never the
raw mean:

    d_i = x_i - mu_i      x_i = the ledger's own realised %/trade (I14)
                          mu_i = mean of K matched-random entries on the SAME
                                 coin, SAME window, that close's OWN stamped
                                 bracket, through the taker's own exit

THE HONEST FRAME, STATED BEFORE THE RUN (§4). At sd ~6.44%/trade the smallest
effect an n=130 cell can detect at 80% power is ~1.4pp/trade, and the book's
ENTIRE mean is +1.38%/trade. **In every cell smaller than ~n=130 this search
can only detect effects larger than the whole book's mean.** A null result is
the EXPECTED outcome and is not a failure of the search. Any cell small
enough to look like a discovery is already too small to prove one.

THE REGISTRATION IS EXECUTABLE, NOT PROSE ((tt): a defense that lives only in
prose is a defense that has not been written). The cell rule, m, the seeds,
the tolerances and the bar live in `scripts/PREREG_TAKER_CELLS_2026-09-11.json`;
this module recomputes that file's sha256 and **exits 2 if it does not match
`PREREG_SHA` below**. A cell set that can be edited mid-run is not
pre-declared. `ENTRY_FEATURES` is a hard-coded allowlist and `mae_ret`,
`give_back` and `peak_ret` are absent from it — outcome-conditioned families
never reach the referee (I21), and a registration naming one refuses the run.

OWNERS IMPORTED, NEVER RE-IMPLEMENTED ((hj): a second copy of a rule is a
second rule):
  * quarantine + row shape .... `bot_pnl_store.normalize_paper_row`
  * phantom / adopted closes .. `golive_readiness.is_phantom_close`,
                                `.is_adopted_close`
  * the era ................... `golive_readiness.era_rows` (DERIVED from the
                                ledger's own policy stamps — not a constant)
  * clustered SE .............. `golive_readiness.cluster_se`
  * power ..................... `golive_readiness._mde80`, `._power`
  * the critical value ........ `fleet_allocation.t_crit`
  * the n floor ............... `fleet_allocation.MIN_N`
  * multiplicity + t p-value .. `winners_docket.bh_survivors`, `.t_sf`
  * exits and routing ......... `lighter_ticket_taker.exit_reason` via
                                `tt.bull_exit`, max-hold GRAFTED from each
                                close's own `extra.bars` (`tt.pos_bars`)
  * the null machinery ........ `study_taker_random_null_2026-09-10`:
                                `routing`, `walk`, `fetch_tape`, `replay_real`,
                                `CALIB_TOL_PP`, `lens_of`, `family_of`

RE-IMPLEMENTED HERE, AND WHY — the two places importing was not possible:
  1. **The sample loader.** The null module's `load_era` filters with
     `store.is_quarantined` + `is_phantom_close` against a HARD-CODED
     `ERA_SINCE` constant. This protocol requires the fuller owner chain
     (`normalize_paper_row`, which is the one owner of the quarantine AND the
     row shape; plus `is_adopted_close`) and the era DERIVED by `era_rows`
     rather than asserted. `load_era_rows()` below is that stricter chain; it
     reproduces the same 349 -> 304 -> 208 and cross-checks its derived era
     against the null module's `ERA_SINCE` constant, refusing on disagreement.
  2. **The shift placebo** (§3) does not exist in the null module. It is new.
  Everything else — the walk, the routing, the tape, the calibration arm — is
  the null module's, called.

ONE PERFORMANCE CHANGE, AND IT IS EXACT, NOT AN APPROXIMATION. Rather than
walking a fresh random entry per draw, this precomputes each close's **outcome
curve**: `nul.walk` run from EVERY valid entry index on that close's own coin
under that close's own bracket. A random draw and a shifted draw are then
lookups into that curve. Identical arithmetic (the same `nul.walk`, the same
`nul.routing`), memoised by (coin, side, bars, trail) — which is why B=2000
shift placebos over 152 cells is affordable at all.

MUTATES NO PROCESS ENV. The prior design in this family did
`os.environ.setdefault("TT_BULL_MODE", "on")` at import and reddened three
unrelated selftests. This asks `tt.bull_exit` and REFUSES (exit 2) when the
answer says this process cannot reproduce the era's routing, telling the
caller to put `TT_BULL_MODE=on` in the COMMAND.

THE CALIBRATION GATE REFUSES — it does not report ((gx)). Four arms: the
replayed real entries vs the ledger mean; the recomputed era vs the LIVE
`/bus.json` payload (fail-CLOSED on a dark feed — an expectation that cannot
be checked is not a gate); the routing; and the tape coverage plus the null's
own Monte-Carlo noise. On any refusal NO cell table is printed: a partial
table is a result, and results leak.

AND THE PIPELINE IS ITSELF CALIBRATED (§9, I3 applied to the search). A
POSITIVE CONTROL (+2.00pp planted in a sha256-parity cell that cannot be an
edge) MUST fire, or the run exits 2 — a gate that never opens is trivially
stable and useless. A PLACEBO (the book replaced by a held-out null draw,
20 seeds) must NOT fire, or the run exits 2 — a pipeline that manufactures
significance has uncalibrated p-values, and without this a null result is
indistinguishable from a broken harness.

DECLARED, so it bounds what a survivor could ever buy: `LIVE_SIDES` admits
`divergence/short` only, so a `long-breakoutup` survivor buys a SHADOW-lane
filter — never a live change. Editing `LIVE_SIDES` is out of scope.

WHAT THE FIRST REGISTERED RUN MEASURED (2026-09-11, recorded here because a
registration that fails its own calibration is the finding, not a bug):
**the §9 POSITIVE CONTROL FAILED and the run REFUSED.** A planted +2.00pp on
an n=110 parity cell reads t=+2.91, p=3.03e-03 and CLEARS the selection
premium (p_max 0.0195) — and still dies on the BH rank-1 threshold of
3.27e-04. That cell's own multiplicity-adjusted detection floor is
**3.35pp/trade**; across the 144 judgeable registered cells the smallest is
**3.10pp/trade**, against a whole-book mean of +1.38%/trade.

So the honest answer to "widen metrics and parameters until you find an edge"
is arithmetic, not attitude: **widening is what destroys the power.** Every
cell added raises the threshold every cell must clear, and at m=152 the floor
is already more than twice the book's entire mean. There is no width of this
search at which an edge of a plausible size could be found — a narrower,
genuinely pre-registered single hypothesis graded FORWARD is the only
instrument that can answer the question, which is the (tt)/I21 shape.

`--diagnostic` downgrades that refusal to a stamped line so the cell
LANDSCAPE is visible. Nothing printed under it can be called an edge.

Exit: 0 verdict printed · 2 refused.
"""
import argparse
import bisect
import collections
import datetime as _dt
import hashlib
import importlib
import itertools
import json
import math
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot_pnl_store as store              # noqa: E402
import fleet_allocation as alloc           # noqa: E402
import golive_readiness as gr              # noqa: E402
import lighter_ticket_taker as tt          # noqa: E402
import winners_docket as wd                # noqa: E402

nul = importlib.import_module("study_taker_random_null_2026-09-10")

BASE = nul.BASE
BOT = nul.BOT

HERE = os.path.dirname(os.path.abspath(__file__))
PREREG_PATH = os.path.join(HERE, "PREREG_TAKER_CELLS_2026-09-11.json")

#: sha256 of the registration AS FROZEN. A cell set that can be edited
#: mid-run is not pre-declared — mismatch is a REFUSAL, never a warning.
PREREG_SHA = "daa496cd38c7c7bc70d4ca66c04bcc753b9b91fdec1ad65251f1e029055edbbc"

#: HARD-CODED ADMISSIBILITY ALLOWLIST (I21). Every feature a registration may
#: name. `mae_ret`, `give_back` and `peak_ret` are DELIBERATELY ABSENT: they
#: are derived from the trade's own path, so a cell built on one is an
#: outcome-conditioned family and wins BY CONSTRUCTION. They may be REPORTED;
#: they may never gate.
ENTRY_FEATURES = ("vol_m", "apr_pct", "chg_pct", "prem_bps", "range_pos",
                  "brk_quality", "up_strength", "hour_utc", "weekday",
                  "bars_tp", "bars_hold", "coin")

#: The LIVE published grade this run must reproduce. Read from /bus.json —
#: these are the FALLBACK only for the selftest's offline fixture, never a
#: substitute for the feed (fail-CLOSED, §6.2).
EXPECT = {"n": 208, "t": 2.12, "h1": 46.06, "h2": 70.59}


# --------------------------------------------------------------- utilities
def _ts(v):
    return nul._ts(v)


def _get(url, tries=3):
    return nul._get(url, tries)


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def sd(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def quantile(xs, q):
    """Linear-interpolation quantile. Sorted copy; empty -> None."""
    s = sorted(xs)
    if not s:
        return None
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def load_prereg(path=PREREG_PATH, expect_sha=PREREG_SHA):
    """The frozen registration, hash-checked. -> (dict, sha) or (None, sha).

    Returns None rather than raising so the caller owns the exit code, and so
    the selftest can drive the REFUSAL branch, which is the branch that
    matters."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None, None
    got = hashlib.sha256(raw).hexdigest()
    if expect_sha and got != expect_sha:
        return None, got
    try:
        return json.loads(raw.decode("utf-8")), got
    except ValueError:
        return None, got


def admissible(pre):
    """Every feature the registration names must be on the hard-coded
    allowlist. -> (ok, offending). This is the I21 structural guard: an
    outcome-conditioned family cannot reach the referee even if someone edits
    the JSON and re-stamps the hash."""
    named = list(pre.get("features") or [])
    named += [b[0] for b in (pre.get("bracket_cells") or [])]
    bad = [f for f in named
           if f not in ENTRY_FEATURES
           and f not in ("tp", "max_hold_h")]   # bracket field names
    return (not bad), bad


# ------------------------------------------------------------- the sample
def load_era_rows(rows_json=None):
    """Era closes through the repo's OWN owners, in order.

    RE-IMPLEMENTED (declared in the module docstring): the null module's
    `load_era` uses `is_quarantined` + a hard-coded era constant. This uses
    `normalize_paper_row` (the one owner of BOTH the quarantine and the row
    shape), `is_phantom_close`, `is_adopted_close`, then `era_rows` — so the
    era is DERIVED from the ledger's own policy stamps, never asserted.

    -> (era_rows, all_kept, era_detail) with each row a dict carrying the
    normalised fields plus `_open`, `_closed`, `_raw`."""
    if rows_json is None:
        raw = _get(BASE + "/trades.json?limit=5000&source=paper")
        if raw is None:
            return [], [], None
        rows_json = (raw if isinstance(raw, list)
                     else raw.get("trades", raw.get("data", [])))
    kept = []
    for r in rows_json:
        if not isinstance(r, dict) or r.get("bot") != BOT:
            continue
        if r.get("side") == "skip":          # a gate log, not a trade
            continue
        n = store.normalize_paper_row(
            r.get("bot"), r.get("pair"), r.get("pnl_abs"), r.get("pnl_pct"),
            r.get("opened_at"), r.get("closed_at"), r.get("reason"),
            r.get("extra"), None, r.get("entry_price"), r.get("exit_price"),
            r.get("tag"))
        if n is None:                        # LEDGER_QUARANTINE
            continue
        if gr.is_phantom_close(n) or gr.is_adopted_close(n):
            continue
        n["_open"] = _ts(n.get("open_ts"))
        n["_closed"] = _ts(n.get("close_ts"))
        n["_raw"] = r
        if n["_open"] is None or n["_closed"] is None:
            continue
        kept.append(n)
    kept.sort(key=lambda n: n["_closed"])
    shaped = [(float(n["profit_ratio"]), float(n["profit_abs"] or 0.0),
               n["_closed"], n["open_ts"], n["extra"]) for n in kept]
    det = gr.era_rows(BOT, shaped, detail=True)
    keys = {(round(s[0], 9), s[2]) for s in det["scoped"]}
    era = [n for n in kept
           if (round(float(n["profit_ratio"]), 9), n["_closed"]) in keys]
    return era, kept, det


def pct_of(row):
    """The ledger's realised return in PERCENTAGE POINTS. The record decides."""
    return float(row["profit_ratio"]) * 100.0


def feat(row, name):
    """An ENTRY-TIME feature off the close's own `extra` stamp, or None.

    Refuses anything off the allowlist, so a caller cannot reach an
    outcome-conditioned field by passing a string."""
    if name not in ENTRY_FEATURES:
        raise ValueError(f"{name!r} is not an admissible entry-time feature")
    ex = row.get("extra") or {}
    if name == "hour_utc":
        return row["_open"].hour
    if name == "weekday":
        return row["_open"].weekday()
    if name == "coin":
        return str(row.get("pair") or "").split("/")[0]
    bars = ex.get("bars") or {}
    if name == "bars_tp":
        v = bars.get("tp")
        return float(v) if v is not None else None
    if name == "bars_hold":
        v = bars.get("max_hold_h")
        return float(v) if v is not None else None
    v = ex.get(name)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------- the outcome curve (exact)
def curve_for(sym, is_long, bars, trail, series):
    """`nul.walk` from EVERY valid entry index on `series`.

    -> ([entry_epoch...], [return_pct...]) — the exact set a random draw
    samples from, so a draw and a shift are both O(1) lookups. The walk, the
    exit rule and the routing are the taker's own; nothing here re-implements
    a decision."""
    ts, rets = [], []
    for i in range(0, max(0, len(series) - 2)):
        t_open, px = series[i]
        w = nul.walk(px, t_open, is_long, bars, trail, series[i + 1:])
        if w:
            ts.append(t_open)
            rets.append(w[0] * 100.0)
    return ts, rets


def build_curves(rows, tape):
    """Attach an outcome curve to every era row whose coin the tape covers.

    -> (with_curve, missing) ; each kept row gains `_curve` (ts, rets),
    `_idx` (its own real open's index in that curve) and `_key`."""
    cache, out, missing = {}, [], []
    for r in rows:
        sym = str(r.get("pair") or "").split("/")[0]
        s = tape.get(sym)
        if not s or len(s) < 30:
            missing.append(r)
            continue
        stamped = tt.pos_bars({"bars": (r.get("extra") or {}).get("bars")})
        # the lens comes from the OWNER-normalised tag ('long-breakoutup'),
        # which `normalize_paper_row` already resolved from the stored `tag`
        # column in preference to the reason prefix. `nul.lens_of` reads a
        # `tag`/`reason` key, so it is handed one rather than a normalised
        # dict whose keys it would silently miss and return '' for.
        rt = nul.routing(nul.lens_of({"tag": r["enter_tag"]}), stamped)
        if rt is None:
            return None, None                  # routing unreproducible
        bars, trail = rt
        is_long = str(r.get("enter_tag") or "").startswith("long")
        key = (sym, is_long, bars, trail)
        if key not in cache:
            cache[key] = curve_for(sym, is_long, bars, trail, s)
        ts, rets = cache[key]
        if len(rets) < 30:
            missing.append(r)
            continue
        r["_curve"] = (ts, rets)
        r["_key"] = key
        r["_idx"] = min(bisect.bisect_left(ts, int(r["_open"].timestamp())),
                        len(ts) - 1)
        out.append(r)
    return out, missing


def draw_mu(rows, k, seed, held_out=0):
    """K matched-random entries per close -> (mu, mc_se, held).

    The construction is `nul.draw_null`'s, read off the precomputed curve:
    one rng, consumed in close order, `randrange` over that coin's own
    entry positions. `held_out` extra draws per close are returned separately
    and are EXCLUDED from mu, so the §9 placebo's book is independent of the
    baseline it is differenced against."""
    rng = random.Random(seed)
    mus, ses, held = [], [], []
    for r in rows:
        _ts_, rets = r["_curve"]
        got = [rets[rng.randrange(0, len(rets))] for _ in range(k)]
        extra = [rets[rng.randrange(0, len(rets))] for _ in range(held_out)]
        m = mean(got)
        mus.append(m)
        ses.append(sd(got) / math.sqrt(len(got)) if len(got) > 1 else 0.0)
        held.append(extra)
    return mus, ses, held


def shift_book(rows, shift_s):
    """One SHIFT PLACEBO: every close re-entered on its OWN coin `shift_s`
    later, wrapped into that coin's tape span.

    A single global offset preserves the real book's within-day and
    cross-coin co-occurrence structure, which independent per-close draws
    destroy — an iid run-null is too TIGHT and therefore anti-conservative."""
    out = []
    for r in rows:
        ts, rets = r["_curve"]
        t0, t1 = ts[0], ts[-1]
        span = max(1, t1 - t0)
        tgt = t0 + ((int(r["_open"].timestamp()) - t0 + shift_s) % span)
        i = min(bisect.bisect_left(ts, tgt), len(rets) - 1)
        out.append(rets[i])
    return out


# ------------------------------------------------------------------- cells
def build_cells(pre, base, primary, secondary):
    """The m pre-declared cells, from the registration's RULE.

    Every cell is (name, family_label, index_list_or_None, note). A cell that
    cannot be computed (a duplicate cut point, an empty or degenerate slice)
    is returned with `None` indices — it is COUNTED IN m and can never
    survive; m does not shrink because a cell turned out uncomputable, and it
    cannot grow because someone thought of a new cut mid-run ((tt))."""
    cells = []
    feats = list(pre["features"])
    eps = float(pre["duplicate_cut_eps"])
    idx_primary = list(range(len(primary)))

    def vals(f):
        return [feat(primary[i], f) for i in idx_primary]

    # ---- stage 1a: 7 features x 4 quantiles x 2 directions = 56
    for f in feats:
        v = vals(f)
        cuts = []
        for q in pre["marginal_quantiles"]:
            cuts.append(quantile([x for x in v if x is not None], q))
        for j, q in enumerate(pre["marginal_quantiles"]):
            cut = cuts[j]
            dup = any(abs(cut - c) < eps for c in cuts[:j]) if cut is not None \
                else False
            for d in pre["directions"]:
                name = f"{f} {'>=' if d == 'ge' else '<='} p{int(q*100)}"
                if cut is None or dup:
                    cells.append((name, "long-breakoutup", None,
                                  "UNCOMPUTABLE: duplicate cut point"))
                    continue
                sel = [i for i in idx_primary
                       if v[i] is not None
                       and (v[i] >= cut if d == "ge" else v[i] <= cut)]
                note = f"cut={cut:.4g}"
                if len(sel) == len(idx_primary) or not sel:
                    note = f"DEGENERATE (admits {len(sel)}/{len(idx_primary)})"
                cells.append((name, "long-breakoutup", sel, note))

    # ---- stage 1b: 4 UTC six-hour blocks
    for a, b in pre["time_blocks"]:
        sel = [i for i in idx_primary if a <= feat(primary[i], "hour_utc") < b]
        cells.append((f"hour_utc [{a:02d},{b:02d})", "long-breakoutup", sel,
                      "UTC six-hour block"))

    # ---- stage 1c: weekday / weekend
    for lab in pre["weekday_cells"]:
        sel = [i for i in idx_primary
               if (feat(primary[i], "weekday") < 5) == (lab == "weekday")]
        cells.append((lab, "long-breakoutup", sel, "calendar"))

    # ---- stage 1d: the 4 stamped-bracket regimes
    for field, want in pre["bracket_cells"]:
        key = "bars_tp" if field == "tp" else "bars_hold"
        sel = [i for i in idx_primary
               if feat(primary[i], key) is not None
               and abs(feat(primary[i], key) - float(want)) < 1e-9]
        cells.append((f"bars.{field}=={want:g}", "long-breakoutup", sel,
                      "stamped bracket regime"))

    # ---- stage 2: 21 pairs x 4 sign combos at p50 = 84
    med = {}
    for f in feats:
        med[f] = quantile([x for x in vals(f) if x is not None],
                          pre["conjunction_quantile"])
    for fa, fb in itertools.combinations(feats, 2):
        va, vb = vals(fa), vals(fb)
        for sa, sb in (("ge", "ge"), ("ge", "le"), ("le", "ge"), ("le", "le")):
            name = (f"{fa}{'>=' if sa == 'ge' else '<='}p50 & "
                    f"{fb}{'>=' if sb == 'ge' else '<='}p50")
            if med[fa] is None or med[fb] is None:
                cells.append((name, "long-breakoutup", None,
                              "UNCOMPUTABLE: no median"))
                continue
            sel = [i for i in idx_primary
                   if va[i] is not None and vb[i] is not None
                   and (va[i] >= med[fa] if sa == "ge" else va[i] <= med[fa])
                   and (vb[i] >= med[fb] if sb == "ge" else vb[i] <= med[fb])]
            cells.append((name, "long-breakoutup", sel, "conjunction @p50"))

    # ---- the 2 family-level cells (over the FULL base, not the primary set)
    n_p = len(primary)
    cells.append(("FAMILY long-breakoutup (whole)", "long-breakoutup",
                  idx_primary, "family"))
    cells.append(("FAMILY short-divergence (whole)", "short-divergence",
                  list(range(n_p, n_p + len(secondary))),
                  "REPORT-ONLY: mde80 ~2.5pp exceeds the whole book's mean"))
    return cells


def t_for_p(p, df, lo=0.0, hi=40.0):
    """The t value whose one-sided tail is `p` at `df`, by bisection on the
    OWNER's `winners_docket.t_sf` — never a second copy of the distribution."""
    if df < 1 or not (0.0 < p < 1.0):
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if wd.t_sf(mid, df) > p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def mde_bh(se_cr, df, alpha):
    """The per-trade excess this cell would need at 80% power to clear a
    MULTIPLICITY-ADJUSTED threshold `alpha` — the honest detection floor of a
    search of this width.

    Same shape as `golive_readiness._mde80` (critical value + the 0.80
    quantile, times the SE), with the CLUSTERED SE and the BH rank-1
    threshold substituted, because those are what the test actually uses.
    This is the number that makes "widen the search" measurable: every cell
    added raises it, so widening costs detection."""
    t_req = t_for_p(alpha, df)
    if t_req is None or not se_cr:
        return None
    return (t_req + gr._t_crit(0.8416212, df)) * se_cr


def eval_cell(idx, d, keys, coins, min_n):
    """One cell's statistics on the paired differences.

    Day-clustered one-sided t is THE statistic: df = G-1, never n-1 —
    clustering costs degrees of freedom, and a pooled t over overlapping
    windows measures sampling density, not edge ((uf)). The iid t is context
    and can never promote a cell."""
    out = {"n": len(idx) if idx is not None else 0}
    if idx is None:
        out["status"] = "UNCOMPUTABLE"
        out["p"] = 1.0
        return out
    if not idx:
        out["status"] = "EMPTY"
        out["p"] = 1.0
        return out
    dv = [d[i] for i in idx]
    out["mean_d"] = mean(dv)
    out["sd_d"] = sd(dv)
    se_cr, g, gmax = gr.cluster_se(dv, [keys[i] for i in idx])
    se_coin, gc, _ = gr.cluster_se(dv, [coins[i] for i in idx])
    out["G"] = g
    out["gmax"] = gmax
    out["G_coin"] = gc
    se_iid = out["sd_d"] / math.sqrt(len(dv)) if out["sd_d"] > 0 else 0.0
    out["t_iid"] = out["mean_d"] / se_iid if se_iid > 0 else 0.0
    out["mde80_iid"] = gr._mde80(out["sd_d"], len(dv))
    if len(dv) < min_n:
        out["status"] = "THIN"
        out["p"] = 1.0
    elif se_cr is None:
        out["status"] = "UNDECIDABLE"      # cluster_se fails CLOSED ((kg))
        out["p"] = 1.0
    else:
        out["status"] = "ok"
        out["t"] = out["mean_d"] / se_cr
        out["p"] = wd.t_sf(out["t"], g - 1)
        if out["mde80_iid"] and se_iid > 0:
            out["mde80_cluster"] = out["mde80_iid"] * (se_cr / se_iid)
        out["se_cr"] = se_cr
        out["t_coin"] = (out["mean_d"] / se_coin) if se_coin else None
        out["p_coin"] = (wd.t_sf(out["t_coin"], gc - 1)
                         if out["t_coin"] is not None else 1.0)
        for e in (1.0, 2.0):
            out[f"power_{e:g}"] = gr._power(e, out["sd_d"], len(dv))
    return out


def cell_ts(cells, d, keys, min_n):
    """Day-clustered t per cell, for the max-statistic. `-inf` where the cell
    cannot be judged, so an uncomputable cell never sets the maximum."""
    out = []
    for _name, _fam, idx, _note in cells:
        if not idx or len(idx) < min_n:
            out.append(float("-inf"))
            continue
        dv = [d[i] for i in idx]
        se, g, _ = gr.cluster_se(dv, [keys[i] for i in idx])
        out.append(mean(dv) / se if se else float("-inf"))
    return out


def concentration(idx, d, coins, days, pre):
    """§7 — a claimed winner must survive its own tails. -> (ok, [reasons])."""
    c = pre["concentration"]
    dv = sorted(((d[i], coins[i], days[i]) for i in idx), key=lambda z: -z[0])
    fails = []
    n = len(dv)
    tot = sum(x for x, _, _ in dv)
    for k in (1, max(2, math.ceil(c["drop_best_k_frac"] * n))):
        rest = dv[k:]
        if len(rest) < 3:
            fails.append(f"drop-best-{k}: fewer than 3 rows left")
            continue
        vals_ = [x for x, _, _ in rest]
        se, g, _ = gr.cluster_se(vals_, [z[2] for z in rest])
        t = (mean(vals_) / se) if se else None
        if mean(vals_) <= 0 or t is None or t < c["drop_best_t_floor"]:
            fails.append(f"drop-best-{k}: mean {mean(vals_):+.3f}pp "
                         f"t {t if t is None else round(t, 2)}")
    # leave-one-coin-out
    allc = sorted({z[1] for z in dv})
    pos, worst = 0, None
    for cc in allc:
        rest = [z for z in dv if z[1] != cc]
        if len(rest) < 3:
            continue
        vals_ = [x for x, _, _ in rest]
        se, g, _ = gr.cluster_se(vals_, [z[2] for z in rest])
        t = (mean(vals_) / se) if se else None
        pos += 1 if mean(vals_) > 0 else 0
        if t is not None and (worst is None or t < worst):
            worst = t
    if allc and pos / len(allc) < c["loo_coin_positive_frac"]:
        fails.append(f"leave-one-coin-out: {pos}/{len(allc)} positive")
    if worst is not None and worst < c["loo_worst_t_floor"]:
        fails.append(f"leave-one-coin-out: worst t {worst:+.2f}")
    # leave-one-day-out
    alld = sorted({z[2] for z in dv})
    posd = 0
    for dd in alld:
        rest = [z for z in dv if z[2] != dd]
        if len(rest) < 3:
            continue
        posd += 1 if mean([x for x, _, _ in rest]) > 0 else 0
    if alld and posd / len(alld) < c["loo_coin_positive_frac"]:
        fails.append(f"leave-one-day-out: {posd}/{len(alld)} positive")
    # share
    if tot > 0:
        if dv[0][0] / tot > c["share_best_max"]:
            fails.append(f"share: best close {dv[0][0]/tot:.1%} of sum d")
        if sum(x for x, _, _ in dv[:3]) / tot > c["share_top3_max"]:
            fails.append("share: top-3 over 80% of sum d")
    else:
        fails.append("share: sum d is not positive")
    return (not fails), fails


# ------------------------------------------------------------------ report
def report(argv):                                           # noqa: C901
    pre, got = load_prereg()
    print("🎫 THE TICKET TAKER — PRE-REGISTERED ENTRY-CELL EDGE SEARCH\n")
    if pre is None:
        print(f"REFUSED — the registration does not match its frozen hash.\n"
              f"  expected {PREREG_SHA}\n  got      {got}\n"
              "A cell set that can be edited mid-run is not pre-declared.")
        return 2
    ok, bad = admissible(pre)
    if not ok:
        print(f"REFUSED — registration names non-entry-time feature(s): {bad}. "
              "Outcome-conditioned families never reach the referee (I21).")
        return 2
    print(f"registration {os.path.basename(PREREG_PATH)}  sha256 {got[:16]}…  "
          f"m={pre['m']}  FDR={pre['fdr']}")
    print(f"BAR: {pre['bar']}\n")

    k = argv.draws or int(pre["draws_k"])
    B = argv.shifts or int(pre["shift_b"])
    min_n = alloc.MIN_N
    print(f"K={k} null draws/close (seed {pre['null_seed']})  ·  "
          f"B={B} shift placebos (seed {pre['shift_seed']})  ·  "
          f"n floor = fleet_allocation.MIN_N = {min_n}  ·  "
          f"t_crit(30) = {alloc.t_crit(30):.4f}")
    if k != int(pre["draws_k"]) or B != int(pre["shift_b"]):
        print("  !! RUN DEVIATES FROM THE REGISTRATION (--draws/--shifts "
              "overridden) — this is a diagnostic run, not the registered one.")
    print()

    # ---------------------------------------------------- sample + era gate
    era, kept, det = load_era_rows()
    if len(era) < 30:
        print(f"REFUSED — only {len(era)} era closes read (dark feed?).")
        return 2
    print(f"ledger  {len([1 for _ in kept]):>4} kept after quarantine/phantom/"
          f"adopted  ->  era n={len(era)}  since {det['iso']} ({det['source']})")
    if det["iso"] and _ts(det["iso"]) != _ts(nul.ERA_SINCE):
        print(f"REFUSED — derived era {det['iso']} disagrees with the null "
              f"harness's own constant {nul.ERA_SINCE}.")
        return 2
    fam = collections.Counter(r["enter_tag"] for r in era)
    print(f"families {dict(fam)}")
    print(f"LIVE_SIDES = "
          f"{dict((a, sorted(b)) for a, b in tt.LIVE_SIDES.items())}"
          "   <- a long-breakoutup survivor can only buy a SHADOW-lane filter\n")

    # §6.2 — reproduce the LIVE published grade, fail-CLOSED
    bus = _get(BASE + "/bus.json")
    book = (((bus or {}).get("golive_readiness") or {}).get("books")
            or {}).get(BOT)
    if not isinstance(book, dict) or book.get("n") is None:
        print("REFUSED — /bus.json carries no golive-readiness grade for this "
              "book. An expectation that cannot be checked is not a gate.")
        return 2
    st = gr.stats(det["scoped"])
    mine = {"n": len(det["scoped"]), "t": round(st.get("t") or 0.0, 2),
            "h1": round(st.get("h1") or 0.0, 2),
            "h2": round(st.get("h2") or 0.0, 2)}
    theirs = {kk: book.get(kk) for kk in ("n", "t", "h1", "h2")}
    agree = all(mine[kk] == theirs[kk] for kk in mine)
    print(f"era reproduction  mine {mine}  vs published {theirs}  "
          f"-> {'MATCH' if agree else 'DISAGREE'}")
    if not agree:
        print("\nREFUSED — the recomputed era does not reproduce the published "
              "grade. No cell table printed.")
        return 2

    # §6.3 — routing
    if nul.routing("breakoutup", (0.04, -0.03, 48.0)) is None:
        print("\nREFUSED — BULL_MODE is OFF in this process while the graded "
              "era ran bull=True, so `bull_exit` cannot reproduce the era's "
              "exit routing. Re-run with TT_BULL_MODE=on in the COMMAND "
              "(this module mutates no environment).")
        return 2

    primary_all = [r for r in era if r["enter_tag"] == pre["primary_family"]]
    with_feats = [r for r in primary_all
                  if all(feat(r, f) is not None for f in pre["features"])]
    print(f"\n{pre['primary_family']}  era n={len(primary_all)}  "
          f"carrying all {len(pre['features'])} entry features: "
          f"{len(with_feats)}  (floor {pre['min_feature_rows']})")
    if len(with_feats) < int(pre["min_feature_rows"]):
        print("REFUSED — the feature-carrying subset is a different population "
              "from the one the calibration reproduces.")
        return 2

    # ------------------------------------------------------------- the tape
    coins = {str(r.get("pair") or "").split("/")[0] for r in era}
    t0 = int(min(r["_open"] for r in era).timestamp()) - 3 * 86400
    t1 = int(time.time()) // 86400 * 86400        # day-rounded: stable cache
    print(f"\ntape  {len(coins)} coins, {(t1 - t0)/86400:.0f}d "
          f"(cache {nul.CACHE}) …")
    tape = nul.fetch_tape(coins, t0, t1, cache=not argv.no_cache)
    cov = len(tape) / len(coins) if coins else 0.0
    print(f"  covers {len(tape)}/{len(coins)} coins ({cov:.0%}, floor "
          f"{pre['tape_coverage_min']:.0%})")
    if cov < float(pre["tape_coverage_min"]):
        print("REFUSED — a null on a biased subset of coins is not a null.")
        return 2

    # §6.1 — the calibration arm: the taker's OWN entries through the walk
    # `nul.replay_real` takes the RAW feed shape (opened_at/pnl_pct/
    # entry_price/tag) — the normalised rows carry the owner's names, so the
    # raw row rides along at `_raw` precisely for this call. Handing it the
    # normalised dict is the "consumer tested against a hand-written fixture"
    # shape; it was caught by driving the real publisher's rows through it.
    real, used = nul.replay_real([r["_raw"] for r in era], tape)
    if not real:
        print("REFUSED — the calibration replay produced nothing.")
        return 2
    led = [float(r["pnl_pct"]) * 100.0 for r in used
           if r.get("pnl_pct") is not None]
    drift = abs(mean(real) - mean(led))
    print(f"\ncalibration  replayed {mean(real):+.3f}%/trade vs ledger "
          f"{mean(led):+.3f}% on the SAME {len(real)} closes "
          f"(|drift| {drift:.3f}pp, tol {nul.CALIB_TOL_PP:.2f}pp)")
    if drift > nul.CALIB_TOL_PP:
        print("\nREFUSED — a harness that cannot reproduce what DID happen may "
              "not say what WOULD have. No cell table printed.")
        return 2
    print("calibration OK")

    # ------------------------------------------------------------ the null
    primary, sec = with_feats, [r for r in era
                                if r["enter_tag"] == pre["report_only_family"]]
    t_c = time.time()
    base, missing = build_curves(primary + sec, tape)
    if base is None:
        print("REFUSED — routing could not be reproduced for every close.")
        return 2
    primary = [r for r in base if r["enter_tag"] == pre["primary_family"]]
    sec = [r for r in base if r["enter_tag"] == pre["report_only_family"]]
    base = primary + sec
    print(f"\noutcome curves  {len(base)} closes "
          f"({len(missing)} dropped: coin absent from the tape)  "
          f"{time.time() - t_c:.1f}s")

    mus, mcses, held = draw_mu(base, k, int(pre["null_seed"]),
                               held_out=int(pre["placebo_seeds"]))
    med_se = sorted(mcses)[len(mcses) // 2]
    print(f"null  K={k} draws/close  median MC SE of mu_i = {med_se:.3f}pp "
          f"(ceiling {pre['mc_se_max_pp']}pp)")
    if med_se > float(pre["mc_se_max_pp"]):
        print("REFUSED — a baseline too noisy to subtract destroys power "
              "silently; reporting 'no edge' off it is (gx) in the null arm.")
        return 2

    x = [pct_of(r) for r in base]
    d = [x[i] - mus[i] for i in range(len(base))]
    days = [r["_open"].date() for r in base]
    coin_of = [str(r.get("pair") or "").split("/")[0] for r in base]
    print(f"paired unit  d_i = x_i - mu_i   "
          f"book {mean(x):+.3f}%/trade  null {mean(mus):+.3f}%/trade  "
          f"excess {mean(d):+.3f}pp")

    cells = build_cells(pre, base, primary, sec)
    if len(cells) != int(pre["m"]):
        print(f"\nREFUSED — built {len(cells)} cells, registration says "
              f"m={pre['m']}. m cannot move at run time.")
        return 2

    # ----------------------------------------- §3 the shift-placebo max stat
    t_s = time.time()
    rng = random.Random(int(pre["shift_seed"]))
    span = max(1, int((max(days) - min(days)).days) * 86400)
    # The §9 positive control is judged against ITS OWN multiplicity burden:
    # the planted cell is an EXTRA hypothesis (m+1), so its null max statistic
    # is taken over the same m+1 cells. Both maxima come out of one pass —
    # the shift placebo does not depend on the observed book, so the same
    # replicates serve the real table and the control.
    par = [i for i in range(len(base))
           if int(hashlib.sha256(str(base[i]["_raw"].get("trade_id")
                                     or i).encode()).hexdigest(), 16) % 2 == 0]
    cells_ctl = cells + [("CONTROL sha256-parity", pre["primary_family"], par,
                          "planted; cannot be an edge")]
    Ms, Ms_ctl = [], []
    for _b in range(B):
        xb = shift_book(base, rng.randrange(3600, span + 3600))
        db = [xb[i] - mus[i] for i in range(len(base))]
        ts_b = cell_ts(cells_ctl, db, days, min_n)
        Ms.append(max(ts_b[:-1]))
        Ms_ctl.append(max(ts_b))
    Ms_ctl.sort()
    Ms.sort()
    m_med = Ms[len(Ms) // 2]
    m_p95 = Ms[int(0.95 * (len(Ms) - 1))]
    print(f"\nselection premium  B={B} shift placebos: null max-t median "
          f"{m_med:+.2f}, p95 {m_p95:+.2f}  ({time.time() - t_s:.1f}s)")
    print("  (a cell must beat that BEFORE it means anything — the already-"
          "measured premium on this book was ~+0.96 to +1.17 z-units)")

    def p_max(t):
        return (1 + sum(1 for v in Ms if v >= t)) / (B + 1)

    # ------------------------------------------- §9 positive control + placebo
    print("\n§9 PIPELINE CALIBRATION — run BEFORE the real table; failure "
          "REFUSES.")
    def p_max_ctl(t):
        return (1 + sum(1 for v in Ms_ctl if v >= t)) / (B + 1)

    jc = len(cells_ctl) - 1
    ctl_fired = False
    for eff, gating in ((float(pre["control_effect_pp"]), True),
                        (float(pre["control_graded_pp"]), False)):
        dc = list(d)
        for i in par:
            dc[i] += eff
        ts_c = cell_ts(cells_ctl, dc, days, min_n)
        pv = []
        for j, (_nm, _f, idx, _o) in enumerate(cells_ctl):
            g = gr.cluster_se([dc[i] for i in idx], [days[i] for i in idx])[1] \
                if idx and len(idx) >= min_n else 0
            pv.append((j, wd.t_sf(ts_c[j], g - 1) if g > 1 else 1.0))
        surv = wd.bh_survivors(pv, fdr=float(pre["fdr"]))
        fires = (jc in surv) and p_max_ctl(ts_c[jc]) <= 0.05
        if gating:
            ctl_fired = fires
        print(f"  positive control +{eff:.2f}pp planted on a sha256-parity "
              f"cell (n={len(par)}, an EXTRA hypothesis so it carries the "
              f"m+1={len(cells_ctl)} burden): t {ts_c[jc]:+.2f}, p "
              f"{pv[jc][1]:.2e}, p_max {p_max_ctl(ts_c[jc]):.4f}, post-BH "
              f"survivors {len(surv)} -> "
              f"{'FIRES' if fires else 'does not fire'}"
              f"{'  [GATING]' if gating else '  [reported, not gating]'}")
        if gating and not fires:
            se_c, g_c, _ = gr.cluster_se([dc[i] for i in par],
                                         [days[i] for i in par])
            floor_c = mde_bh(se_c, g_c - 1,
                             float(pre["fdr"]) / len(cells_ctl))
            print(f"\n  the control cell's own MULTIPLICITY-ADJUSTED "
                  f"detection floor is "
                  f"{(f'{floor_c:.2f}pp' if floor_c else 'uncomputable')}"
                  f"/trade (n={len(par)}, G={g_c} day clusters, BH rank-1 "
                  f"threshold {float(pre['fdr'])/len(cells_ctl):.2e}) — "
                  f"a search this WIDE cannot see +{eff:.2f}pp on a cell "
                  f"this size, whatever is in the data.")
            if not argv.diagnostic:
                print("\nREFUSED — the pipeline's real power is below its "
                      "own bar: a planted +2.00pp effect does not survive "
                      "BH at m+1. A gate that never opens is trivially "
                      "stable and useless, and a null result off it would be "
                      "indistinguishable from a broken harness. THIS IS NOT "
                      "A BUG IN THE HARNESS — it is the registration's own "
                      "§4 arithmetic arriving: the multiplicity burden of "
                      "m=152 pre-declared cells puts the detection floor "
                      "above any effect this book could plausibly carry. "
                      "Re-run with --diagnostic to SEE the cell table; "
                      "nothing in it can be called an edge.")
                return 2
            print("  !! --diagnostic: the control failure is DOWNGRADED to a "
                  "reported line. Everything below is a LANDSCAPE, not a "
                  "test. NO cell printed after this point can be called an "
                  "edge, whatever its p-value, because the pipeline has just "
                  "FAILED its own positive control at this width.")

    pl = []
    for s in range(int(pre["placebo_seeds"])):
        dp = [held[i][s] - mus[i] for i in range(len(base))]
        ts_p = cell_ts(cells, dp, days, min_n)
        pv = []
        for j, (nm, _f, idx, _o) in enumerate(cells):
            g = gr.cluster_se([dp[i] for i in idx], [days[i] for i in idx])[1] \
                if idx and len(idx) >= min_n else 0
            pv.append((j, wd.t_sf(ts_p[j], g - 1) if g > 1 else 1.0))
        pl.append(len(wd.bh_survivors(pv, fdr=float(pre["fdr"]))))
    pl.sort()
    pl_med = pl[len(pl) // 2]
    print(f"  placebo (book replaced by a held-out null draw, "
          f"{len(pl)} seeds): post-BH survivors per seed {pl} -> median "
          f"{pl_med} of {pre['m']} (ceiling "
          f"{pre['placebo_max_post_bh_survivors']})")
    if pl_med > int(pre["placebo_max_post_bh_survivors"]):
        print("\nREFUSED — the pipeline manufactures significance; its "
              "p-values are not calibrated and a null result off it would be "
              "indistinguishable from a broken harness.")
        return 2
    if ctl_fired:
        print("  pipeline calibration OK — the gate can open, and does not "
              "open on noise.\n")
    else:
        print("  pipeline calibration: the placebo arm is CLEAN (it does not "
              "open on noise) but the POSITIVE CONTROL FAILED — so the gate "
              "does not open on a real +2.00pp effect either. Only one half "
              "of the calibration passed, and it is the half that cannot "
              "license a finding.\n")

    # ------------------------------------------------------- the real table
    ev = [eval_cell(idx, d, days, coin_of, min_n)
          for _n, _f, idx, _o in cells]
    pvals = [(j, ev[j]["p"]) for j in range(len(cells))]
    surv = wd.bh_survivors(pvals, fdr=float(pre["fdr"]))
    ranked = sorted(range(len(cells)), key=lambda j: ev[j]["p"])
    bh_thr = {}
    for rank, j in enumerate(ranked, start=1):
        bh_thr[j] = rank / len(cells) * float(pre["fdr"])

    print("=" * 162)
    print("EVERY PRE-DECLARED CELL (all m, not just survivors — a sweep that "
          "prints only the winner is the artifact)")
    print("=" * 162)
    hdr = (f"{'#':>3} {'cell':<38} {'n':>4} {'G':>3} {'book%':>8} "
           f"{'null%':>8} {'excess':>8} {'t_day':>7} {'t_iid':>7} "
           f"{'p':>8} {'BHthr':>8} {'BH':>3} {'mde80c':>7} {'mdeBH':>7} {'pmax':>7} {'note'}")
    print(hdr)
    print("-" * 162)
    for j, (nm, famlab, idx, note) in enumerate(cells):
        e = ev[j]
        n = e["n"]
        if idx:
            bk = mean([x[i] for i in idx])
            nu = mean([mus[i] for i in idx])
        else:
            bk = nu = float("nan")
        t_d = e.get("t")
        pm = p_max(t_d) if t_d is not None else None
        mde = e.get("mde80_cluster")
        flag = "YES" if j in surv else "-"
        s_td = f"{t_d:+.2f}" if t_d is not None else "--"
        t_ii = e.get("t_iid")
        s_ti = f"{t_ii:+.2f}" if t_ii is not None else "--"
        s_md = f"{mde:.2f}" if mde else "--"
        mbh = (mde_bh(e.get("se_cr"), e.get("G", 1) - 1,
                      float(pre["fdr"]) / len(cells))
               if e.get("se_cr") and e.get("G", 0) > 1 else None)
        s_bh = f"{mbh:.2f}" if mbh else "--"
        s_pm = f"{pm:.4f}" if pm is not None else "--"
        s_md_ = e.get("mean_d")
        s_ex = f"{s_md_:+.3f}" if s_md_ is not None else "--"
        print(f"{j+1:>3} {nm[:38]:<38} {n:>4} {e.get('G', 0):>3} "
              f"{bk:>+8.3f} {nu:>+8.3f} {s_ex:>8} "
              f"{s_td:>7} {s_ti:>7} "
              f"{e['p']:>8.4f} {bh_thr[j]:>8.5f} {flag:>3} "
              f"{s_md:>7} {s_bh:>7} {s_pm:>7} "
              f"{e.get('status','')} {note}")
    print("-" * 150)

    # ------------------------------------------------------------ the verdict
    live = [j for j in range(len(cells)) if ev[j].get("t") is not None]
    best_j = max(live, key=lambda j: ev[j]["t"]) if live else None
    edges = []
    for j in sorted(surv, key=lambda j: ev[j]["p"]):
        e, (nm, _f, idx, _o) = ev[j], cells[j]
        why = []
        if e.get("t") is None:
            continue
        if p_max(e["t"]) > 0.05:
            why.append(f"selection premium: p_max {p_max(e['t']):.4f} > 0.05")
        if not (e.get("p_coin", 1.0) <= float(pre["fdr"])):
            why.append(f"coin-clustering: p {e.get('p_coin', 1.0):.4f}")
        okc, cf = concentration(idx, d, coin_of, days, pre)
        if not okc:
            why.append("concentration: " + "; ".join(cf))
        if not (e.get("mde80_cluster") and
                e["mean_d"] > e["mde80_cluster"]):
            why.append(f"excess {e['mean_d']:+.3f}pp does not exceed its own "
                       f"mde80_cluster "
                       f"{e.get('mde80_cluster') or float('nan'):.2f}pp")
        (edges.append(j) if not why
         else print(f"NOT AN EDGE — {nm}: " + " | ".join(why)))

    print()
    mdes = [ev[j]["mde80_cluster"] for j in live
            if ev[j].get("mde80_cluster")]
    floor = min(mdes) if mdes else None
    if edges:
        print("EDGE(S) FOUND — and each ships only as a SHADOW-lane "
              "restriction with a pre-registered forward read:")
        for j in edges:
            e = ev[j]
            print(f"  {cells[j][0]}  n={e['n']} excess {e['mean_d']:+.3f}pp "
                  f"t_day {e['t']:+.2f} p {e['p']:.5f} "
                  f"p_max {p_max(e['t']):.4f}")
        return 0

    print("VERDICT: REFUSAL — no cell meets the pre-declared bar.")
    if best_j is not None:
        e = ev[best_j]
        print(f"  best cell: {cells[best_j][0]}  n={e['n']}  excess "
              f"{e['mean_d']:+.3f}pp  t_day {e['t']:+.2f}  p {e['p']:.4f}  "
              f"p_max {p_max(e['t']):.4f}  (BH needed p <= "
              f"{float(pre['fdr'])/len(cells):.6f} at rank 1)")
    bhs = [mde_bh(ev[j].get("se_cr"), ev[j].get("G", 1) - 1,
                  float(pre["fdr"]) / len(cells))
           for j in live if ev[j].get("se_cr") and ev[j].get("G", 0) > 1]
    bhs = [v for v in bhs if v]
    if floor:
        print(f"  No admissible entry-time cell of this book detectably beats "
              f"a coin flip at any effect below {floor:.2f}pp/trade, where "
              f"that is the smallest cluster-adjusted mde80 across the "
              f"{len(mdes)} judgeable cells.")
    if bhs:
        print(f"  And at the width actually searched (m={len(cells)}), the "
              f"smallest MULTIPLICITY-ADJUSTED detection floor is "
              f"{min(bhs):.2f}pp/trade — against a whole-book mean of "
              f"+1.38%/trade. Widening the search RAISES that floor. That is "
              f"the measured answer to 'widen until you find an edge': the "
              f"widening is what destroys the power.")
    print("  This names what could NOT have been seen. It does NOT claim the "
          "book has no edge: the family's own one-sided upper bound is "
          "positive, so nothing is excluded either (I26 — a refusal needs a "
          "MEASURED harm, and 'unproven' is not one).")
    print(f"\n{pre['refusal']}")
    return 0


# ---------------------------------------------------------------- selftest
def selftest():
    """Offline, pure, FAST — no network, no env mutation, nothing heavy.
    Everything expensive lives in `report()`; a registered selftest running
    against a hard 120s cap is the failure this file must not reproduce."""
    # the registration is hash-checked, and the REFUSAL branch is the one
    # that matters — a gate that cannot refuse is not a gate.
    pre, got = load_prereg()
    assert pre is not None, f"registration hash drifted: {got}"
    assert got == PREREG_SHA
    assert load_prereg(expect_sha="0" * 64)[0] is None
    assert load_prereg(path=PREREG_PATH + ".nope")[0] is None

    # m is the registration's, and the breakdown must add up to it
    assert sum(pre["m_breakdown"].values()) == pre["m"] == 152
    assert (len(pre["features"]) * len(pre["marginal_quantiles"])
            * len(pre["directions"])) == pre["m_breakdown"]["marginals"]
    npair = len(pre["features"]) * (len(pre["features"]) - 1) // 2
    assert npair * 4 == pre["m_breakdown"]["conjunctions"], npair

    # I21 STRUCTURAL GUARD: an outcome-conditioned feature cannot be admitted
    for banned in ("mae_ret", "give_back", "peak_ret"):
        assert banned not in ENTRY_FEATURES
        assert admissible({"features": [banned]})[0] is False
        try:
            feat({"extra": {banned: 1.0}}, banned)
            raise AssertionError(f"{banned} must be unreachable through feat()")
        except ValueError:
            pass
    assert admissible(pre)[0] is True

    # quantiles, and the duplicate-cut detection they feed
    assert abs(quantile([1, 2, 3, 4, 5], 0.5) - 3.0) < 1e-9
    assert abs(quantile([0, 10], 0.2) - 2.0) < 1e-9
    assert quantile([], 0.5) is None

    # the cell builder produces EXACTLY m cells on a synthetic base, marks a
    # degenerate/duplicate cut UNCOMPUTABLE rather than dropping it (m may not
    # shrink), and never lets an uncomputable cell set the maximum.
    day = _dt.datetime(2026, 8, 1, tzinfo=_dt.timezone.utc)
    rows = []
    for i in range(40):
        ex = {f: float(i % 7) + 0.1 * i for f in pre["features"]}
        ex["bars"] = {"tp": 0.04, "sl": -0.03, "max_hold_h": 48.0}
        rows.append({"enter_tag": "long-breakoutup", "pair": f"C{i%4}/USDC",
                     "extra": ex, "profit_ratio": 0.001 * (i - 20),
                     "_open": day + _dt.timedelta(hours=i * 7),
                     "_raw": {"trade_id": f"t{i}", "side": "long"}})
    sec = [dict(rows[0], enter_tag="short-divergence") for _ in range(12)]
    cells = build_cells(pre, rows + sec, rows, sec)
    assert len(cells) == pre["m"], len(cells)
    # a feature that is CONSTANT has four identical cut points -> duplicates
    flat = []
    for i in range(40):
        ex = {f: 1.0 for f in pre["features"]}
        ex["bars"] = {"tp": 0.04, "sl": -0.03, "max_hold_h": 48.0}
        flat.append(dict(rows[i], extra=ex))
    fc = build_cells(pre, flat + sec, flat, sec)
    assert len(fc) == pre["m"]
    assert any(c[2] is None and "duplicate" in c[3] for c in fc), \
        "a duplicate cut point must be UNCOMPUTABLE and still counted in m"

    # eval_cell: the FLOOR and the fail-CLOSED paths never produce a survivor
    d = [0.5] * 40
    days = [r["_open"].date() for r in rows]
    coins = [r["pair"] for r in rows]
    e = eval_cell(None, d, days, coins, alloc.MIN_N)
    assert e["status"] == "UNCOMPUTABLE" and e["p"] == 1.0
    e = eval_cell(list(range(3)), d, days, coins, alloc.MIN_N)
    assert e["status"] == "THIN" and e["p"] == 1.0, e
    # a perfectly constant d cancels inside every cluster -> cluster_se fails
    # CLOSED ((kg)) and the cell is UNDECIDABLE, never t=infinity
    e = eval_cell(list(range(40)), d, days, coins, alloc.MIN_N)
    assert e["status"] == "UNDECIDABLE" and e["p"] == 1.0, e
    # ...and a real signal IS judged, with df = G-1 (clusters), not n-1
    d2 = [0.5 + 0.01 * (i % 5) for i in range(40)]
    e = eval_cell(list(range(40)), d2, days, coins, alloc.MIN_N)
    assert e["status"] == "ok" and e["t"] > 0 and 0 < e["p"] < 1, e
    assert e["G"] == len(set(days)), e
    assert e["p"] == wd.t_sf(e["t"], e["G"] - 1)
    assert e["mde80_cluster"] and e["power_1"] and e["power_2"]
    # the iid t is CONTEXT and is not the statistic the p-value is built on
    assert abs(e["t"] - e["t_iid"]) > 1e-9

    # t_for_p inverts the OWNER's own tail, and mde_bh is monotone in the
    # width of the search — the property the whole "widen it" answer rests on
    for df_ in (5, 20, 100):
        for pq in (0.05, 0.001):
            tq = t_for_p(pq, df_)
            assert abs(wd.t_sf(tq, df_) - pq) < 1e-6, (df_, pq, tq)
    assert t_for_p(0.05, 0) is None and t_for_p(1.5, 10) is None
    wide = mde_bh(0.5, 30, 0.05 / 500)
    narrow = mde_bh(0.5, 30, 0.05 / 10)
    assert wide > narrow > 0, (wide, narrow)
    assert mde_bh(None, 30, 0.01) is None

    # cell_ts: an uncomputable or thin cell contributes -inf, so the
    # max-statistic can never be set by a cell that cannot be judged
    ts = cell_ts([("a", "f", None, ""), ("b", "f", list(range(3)), ""),
                  ("c", "f", list(range(40)), "")], d2, days, alloc.MIN_N)
    assert ts[0] == float("-inf") and ts[1] == float("-inf") and ts[2] > 0

    # the shift placebo wraps INSIDE the coin's own tape span and is a pure
    # lookup into the precomputed curve
    r = {"_curve": ([0, 3600, 7200, 10800], [1.0, 2.0, 3.0, 4.0]),
         "_open": _dt.datetime.fromtimestamp(3600, _dt.timezone.utc)}
    assert shift_book([r], 3600) == [3.0]
    assert shift_book([r], 3600 * 100)[0] in (1.0, 2.0, 3.0, 4.0)

    # draw_mu holds its held-out draws OUT of the baseline: the placebo book
    # must be independent of the mean it is differenced against
    r2 = {"_curve": ([0, 1, 2, 3, 4], [0.0, 1.0, 2.0, 3.0, 4.0])}
    mus, ses, held = draw_mu([r2], k=50, seed=7, held_out=3)
    assert len(held[0]) == 3 and ses[0] > 0
    mus2, _s, _h = draw_mu([r2], k=50, seed=7, held_out=0)
    assert abs(mus[0] - mus2[0]) < 1e-12, \
        "held-out draws must not enter mu — the same seed must give the same mu"

    # concentration REFUSES a cell carried by one close
    idx = list(range(40))
    dcon = [0.0] * 40
    dcon[0] = 50.0
    ok, fails = concentration(idx, dcon, coins, days, pre)
    assert not ok and any("share" in f for f in fails), fails

    # the outcome curve is the taker's own walk at every index, and it is a
    # real exit (not tape_end) on a tape that trips the bracket
    ser = [(i * 3600, 100.0 - i) for i in range(0, 60)]
    _saved = tt.BULL_MODE
    try:
        tt.BULL_MODE = True
        ts_c, rets = curve_for("X", True, (0.04, -0.03, 48.0), 0.0, ser)
        assert len(rets) == len(ser) - 2 and all(v < -2.0 for v in rets), \
            (len(rets), rets[:3])
    finally:
        tt.BULL_MODE = _saved

    print("study_taker_edge_search selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=0,
                    help="override K (DEVIATES from the registration)")
    ap.add_argument("--shifts", type=int, default=0,
                    help="override B (DEVIATES from the registration)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--diagnostic", action="store_true",
                    help="downgrade the §9 positive-control REFUSAL to a "
                         "reported line so the cell LANDSCAPE is printed. "
                         "Nothing printed under it can be called an edge.")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return report(a)


if __name__ == "__main__":
    raise SystemExit(main())
