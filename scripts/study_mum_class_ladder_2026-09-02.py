#!/usr/bin/env python3
"""STUDY: 👩 mum's ROI LADDER IS CALIBRATED ON CRYPTO — does a CLASS-AWARE
ladder earn more on the non-crypto half, per BAR-DAY, than the shipped one?

[2026-09-02, Eamon: "Start it." — the build (xf) named and did not do.]

===========================================================================
WHY THIS EXISTS, and why it is NOT the cut (xf) registered

`(xf)` proposed excluding mum's non-crypto names, then REFUTED its own
mechanism (closed hours) and found there is no measured exclusion to cut on:
7 closes are 4 entry days, the day-clustered upper bound is POSITIVE, and the
raw class gap FLIPS SIGN under a close-day fixed effect. What survived that
demolition is a DIFFERENT mechanism, and it is the one that is actually
established:

    realised mean |return|   non-crypto 0.623%  vs  crypto 1.746%   (2.80x)
    reach the 24h cap        non-crypto 5 of 7  vs  crypto 4 of 52
    binomial P(>=5 of 7 at crypto's own rate)                 = 5.0e-05

mum's first roi rung asks +2.0% within 4h. On names moving 2.8x less than the
ones the ladder was fitted on, that rung is largely unreachable, so the
position runs to the terminal `1440: 0.0` rung — an exit-at-any-profit
coin-flip — instead of banking. **The remedy this points at is to FEED the
sleeve a ladder matched to its own volatility (I26), not to cut it.**

THE CLAIM UNDER TEST: a ladder scaled toward the non-crypto half's own
realised volatility banks more per BAR-DAY than the shipped crypto-fitted one,
on the same entries.

===========================================================================
WHY THE LEDGER CANNOT ANSWER THIS, and where the power comes from instead

Her non-crypto ledger is **n=7**. A ladder sweep on 7 trades fits noise, and
best-of-N cell selection on a sample that small is the `(uz)` premium at its
worst (measured there: ~1.85 t-units of inflation). So the ledger is NOT the
estimator here — it is the CALIBRATION TARGET.

The power comes from mum's entry being MECHANICAL: `rsi(14) < RSI_MAX AND NOT
(e50>e200) AND v>0` on 1h. Every signal she would have taken is regenerable
over the venue's full 1h tape, per coin, which is the `study_mum_params_
2026-08-27` method and gives hundreds of non-crypto episodes rather than 7.

REUSE, NEVER RETYPED ((hj) — a second copy of a rule is a second rule):
  * tape + estimators: `study_mum_supply_2026-08-26` by import
    (`market_ids`, `fetch_1h`, `cluster_t`, `iid_t`)
  * the ladder, stop, hold and RSI bar: read from the LIVE CARRIER
    (`lighter_family_bot.STRATEGIES`), never from a constant in this file —
    the supply study's retyped copy still matches today, but its cells were
    written when the bar was 25/30/32 and the carrier now ships **36.0**
  * the bracket walk: this file generalises it over an arbitrary ladder, and
    the selftest PINS that at the shipped ladder it is byte-identical to
    `study_mum_supply.bracket_walk` on every real episode. Generalisation is
    only safe if the special case is proved unchanged.
  * the class axis: `fleet_bus.is_crypto` — the same owner (xf) graded on

===========================================================================
PRE-REGISTERED — WRITTEN AND COMMITTED BEFORE ANY NUMBER EXISTED (I21/I25)

C1  CALIBRATION IS FAIL-CLOSED, AND IT IS AN EXIT-MIX TEST, NOT A MEAN TEST.
    A mean can match by luck on a small ledger; the exit MIX is what a ladder
    change actually moves, so it is the thing the harness must reproduce.
    Replaying mum's REAL era entries through the SHIPPED ladder must put each
    of `roi` / `max_hold` / `stop` within CAL_TOL_PP (20pp) of its actual
    share in her era ledger, on the pooled live+shadow arms.
    Outside it, EVERY recommendation is WITHHELD — a harness that cannot
    reproduce what DID happen may not say what WOULD have ((gx)).

C2  n FLOOR: >= 100 scored non-crypto episodes, else UNDECIDED. (Not
    `fleet_allocation.MIN_N` — that floor is for a book's own ledger; this is
    a replay and the binding risk is cell selection, which needs far more.)

C3  ONE FAMILY AT A TIME. The sweep scales the whole ladder by `k` and holds
    the stop and max_hold at shipped. A separate, second sweep varies
    max_hold with the ladder at shipped. A cell that moves both cannot be
    attributed.

C4  THE (hl) GUARD IS THE VERDICT METRIC. 25 of 30 "faster exit" candidates
    died in refutation because the gain was DENOMINATOR SHRINKAGE. The
    verdict metric is therefore **return per BAR-DAY held**, not %/trade.
    %/trade is reported beside it and is never the bar.

C5  PLATEAU. A winning `k` must have BOTH neighbours in the grid also beat
    shipped on the verdict metric, else it is a lone spike and is refused
    ((pw) E4 / the (oe) artifact shape).

C6  THE SELECTION PREMIUM IS PRICED, NOT ASSUMED. The whole procedure —
    pick the best of every cell — is re-run on SHUFFLED CLASS LABELS
    (`PERM_DRAWS` draws, class sizes held). The reported p is
    P(best shuffled advantage >= best real advantage). This prices cell
    selection and the class label in one number, which is the only honest
    way to read a best-of-N result ((uz)).

C7  VERDICTS, pre-declared:
      SHIP        C1 and C2 hold; the cell beats shipped on per-bar-day in
                  BOTH chronological halves; cluster-t of the paired
                  per-episode delta >= T_BAR; C5 plateau holds; C6 p <= 0.05.
      HYPOTHESIS  positive but missing one or more bars — name exactly which.
      REFUSE      flat or negative on per-bar-day — state the number.
    A REFUSAL WITH A NUMBER IS A VALID OUTCOME and satisfies the growth rule.

===========================================================================
DECLARED LIMITS — the ones that run INTO the candidate's favour are named
first, because those are the ones that flatter a result:

  * SLOT CONTENTION IS NOT SIMULATED. mum holds 12 slots across 45 coins. A
    faster ladder frees a slot sooner, so the unmodelled term **FLATTERS THE
    CANDIDATE**. Per-bar-day is reported precisely because it is the metric
    that does not reward turnover for its own sake, but it does not fully
    price contention. Any SHIP verdict inherits this caveat explicitly.
  * ENTRY-BAR RANGE IS CREDITED FROM THE OPEN. Entry is the OPEN of bar `e`
    and the walk tests bar `e`'s own high/low — those prices occur AFTER the
    entry, so this is not the (ne) look-ahead (which credited PRE-entry
    prices). Declared so the distinction is on the record.
  * FILL AT THE RUNG, NOT THE HIGH. An roi exit books exactly the rung, never
    the bar's high. Conservative on both arms.
  * ADVERSE LEG FIRST. When a bar touches both stop and rung, the stop wins.
    Assuming the favourable order is how a replay flatters itself.
  * NO FEES / NO FUNDING. Both arms are price return, so neither can be
    mismodelled into the verdict. The venue is zero-fee; funding is a hold-
    duration tax measured at +0.0171%/day, which is ~0.017% over a 24h cap —
    two orders below the effects here, and it runs AGAINST the longer ladder.
  * EXIT SIGNAL: mum has none by design (`exit: False`), so nothing is
    unmodelled there — unlike the georgia harness this borrows its shape from.

    python3 scripts/study_mum_class_ladder_2026-09-02.py --selftest
    python3 scripts/study_mum_class_ladder_2026-09-02.py            # full run
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lighter_family_bot as fb          # noqa: E402
import fleet_bus as fbus                 # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "mum_supply", os.path.join(HERE, "study_mum_supply_2026-08-26.py"))
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

BOT = "freqtrade-mum"
CAL_TOL_PP = 20.0          # C1 exit-mix tolerance, percentage points
MIN_EPISODES = 100         # C2
T_BAR = 1.5                # C7 cluster-t bar on the paired delta
PERM_DRAWS = 400           # C6
SEED = 20260902
#: C3 grid. 1.00 is the SHIPPED control. The vol-matched scale is ~1/2.80 =
#: 0.357 — INTERIOR to this grid on purpose, so a win there is not a grid edge
#: ((oe): shipping a swept grid's maximum is how an artifact gets deployed).
K_GRID = (1.00, 0.75, 0.50, 0.35, 0.25)
HOLD_GRID = (24, 20, 16, 12, 8)          # bars; 24 = shipped control


# ----------------------------------------------------------------- the rule

def carrier():
    for s in fb.STRATEGIES:
        if s.bot == BOT:
            return s
    raise SystemExit(f"REFUSING: {BOT} not in STRATEGIES — no rule to read")


def shipped_rule(c=None):
    """(ladder, stop, max_hold_bars, rsi_max) READ FROM THE CARRIER."""
    c = c or carrier()
    ladder = sorted((int(k), float(v)) for k, v in c.roi.items())
    return ladder, float(c.stoploss), int(c.MAX_HOLD_MIN // 60), float(c.RSI_MAX)


def scale_ladder(ladder, k):
    """Scale every rung's LEVEL by k; the rung TIMES are untouched (C3)."""
    return [(a, v * k) for a, v in ladder]


def roi_thr(ladder, age_min):
    """The rung in force at `age_min` — newest rung at or below the age wins.

    NOTE, because a mutation of the initialiser SURVIVED and the honest answer
    is that it is an EQUIVALENT MUTANT rather than an untested line: mum's
    ladder starts at age 0, so `age_min >= 0` always holds and the loop
    overwrites `thr` on its first pass. The initialiser is therefore provably
    dead for any ladder of this shape, and no test can distinguish it. The
    assertion in the selftest pins the assumption that makes that true, so a
    ladder that ever started above age 0 would redden rather than silently
    inherit a guessed floor.
    """
    thr = ladder[0][1]
    for a, v in ladder:
        if age_min >= a:
            thr = v
    return thr


def walk(bars, e, ladder, stop, max_hold):
    """mum's bracket from entry at the OPEN of bar `e`, over an arbitrary
    ladder. (ret_pct, reason, bars_held) or None if the tape ends first.

    Generalises `study_mum_supply.bracket_walk`; the selftest pins that at the
    shipped ladder it is byte-identical to that owner on every real episode.
    """
    entry = bars[e][1]
    stop_px = entry * (1.0 + stop)
    for k in range(e, min(e + max_hold, len(bars))):
        age = (k - e) * 60
        thr = roi_thr(ladder, age)
        tgt = entry * (1.0 + thr)
        if bars[k][3] <= stop_px:              # adverse leg first
            return stop * 100.0, "stop", (k - e) + 1
        if bars[k][2] >= tgt:
            return thr * 100.0, "roi", (k - e) + 1
    if e + max_hold >= len(bars):
        return None
    return (bars[e + max_hold][1] / entry - 1.0) * 100.0, "max_hold", max_hold


# ------------------------------------------------------------- the episodes

def signal_bars(bars, rsi_max):
    """Indices where mum's entry cell is TRUE, using the bot's OWN indicator
    functions. The predicate mirrors `OversoldRebound.signals`; the selftest
    drives the carrier itself on a prefix and requires agreement."""
    c = [b[4] for b in bars]
    v = [b[5] for b in bars]
    rsi = fb.rsi_series(c, S.RSI_P)
    e50, e200 = fb.ema_series(c, 50), fb.ema_series(c, 200)
    out = []
    for i in range(len(c)):
        if i < S.WARMUP or None in (rsi[i], e50[i], e200[i]):
            continue
        if rsi[i] < rsi_max and not (e50[i] > e200[i]) and v[i] > 0:
            out.append(i)
    return out


def episodes(universe, mids, rsi_max, quiet=False):
    """[{sym, cls, i, bars}] — one per signal, entry at the NEXT bar's open."""
    eps = []
    for n, sym in enumerate(sorted(universe)):
        if sym not in mids:
            continue
        try:
            bars = S.fetch_1h(sym, mids[sym])
        except Exception as ex:                            # noqa: BLE001
            if not quiet:
                print(f"  {sym}: tape unavailable ({type(ex).__name__}) — skipped")
            continue
        if len(bars) <= S.WARMUP + 2:
            continue
        cls = fbus.is_crypto(sym)
        if cls is None:                 # never guess a class (I6/I8)
            continue
        for i in signal_bars(bars, rsi_max):
            if i + 1 < len(bars):
                eps.append({"sym": sym, "cls": "crypto" if cls else "noncrypto",
                            "i": i + 1, "bars": bars})
    return eps


def score(eps, ladder, stop, max_hold):
    """[{sym, cls, ts, ret, reason, held_bars, per_day}] for resolved episodes."""
    rows = []
    for e in eps:
        r = walk(e["bars"], e["i"], ladder, stop, max_hold)
        if r is None:
            continue
        ret, reason, held = r
        rows.append({"sym": e["sym"], "cls": e["cls"], "ts": e["bars"][e["i"]][0],
                     "ret": ret, "reason": reason, "held": held,
                     # REPORTED, never the verdict metric (see `agg`)
                     "per_day": ret / (held / 24.0)})
    return rows


# -------------------------------------------------------------- aggregation

def agg(rows, key="ret"):
    """Aggregate stats. `mean` is the AGGREGATE return per bar-day.

    **CORRECTED IN PLACE, and the first version of this file shipped the
    defect C4 exists to prevent.** `mean` was the MEAN OF PER-EPISODE RATIOS
    `ret / (held/24)`. That is not return per bar-day: a short winner gets 24x
    the weight of a long loser purely from its denominator, so the statistic
    is maximised by exiting winners fast and losers slow — denominator
    shrinkage, reproduced inside the guard built to catch it. Measured on the
    live run: it read **+1.7173%/bar-day on a sleeve whose mean trade was
    -0.1333%**, which is impossible for any honest exposure metric and is what
    exposed it. The aggregate `sum(ret) / sum(bar-days)` is the number (hl)
    actually used ("per bar-day held only 1.04x"), and it cannot be gamed by
    reweighting: total profit over total exposure.

    `mean_ratio` is kept and REPORTED so the artifact stays visible rather
    than being quietly deleted.
    """
    if not rows:
        return {"n": 0}
    n = len(rows)
    tot_ret = sum(r["ret"] for r in rows)
    tot_days = sum(r["held"] for r in rows) / 24.0
    xs = [r[key] for r in rows]
    t_cl, G = S.cluster_t(xs, [r["sym"] for r in rows])
    return {"n": n,
            "mean": (tot_ret / tot_days) if tot_days else None,   # AGGREGATE
            "mean_ratio": sum(r["ret"] / (r["held"] / 24.0) for r in rows) / n,
            "t_iid": S.iid_t(xs), "t_cl": t_cl, "G": G,
            "mean_pct": tot_ret / n,
            "total_ret": tot_ret, "bar_days": tot_days,
            "held_h": sum(r["held"] for r in rows) / n,
            "exits": dict(Counter(r["reason"] for r in rows))}


def halves(rows, key="ret"):
    """Chronological halves. `key` defaults to `ret` because a PAIRED row is a
    return delta and carries no `per_day` — the selftest pins that absence, and
    this default is what made the pin bite in the caller instead of here."""
    r = sorted(rows, key=lambda x: x["ts"])
    h = len(r) // 2
    return agg(r[:h], key), agg(r[h:], key)


def paired_delta(base, cand):
    """Per-episode (cand - base) RETURN on the SAME entries, keyed by (sym,ts).

    The delta is in RETURN, not in per-bar-day: a paired test needs a
    per-episode quantity, and the exposure change is reported separately as
    `bar_days` rather than folded into the same number.
    """
    b = {(r["sym"], r["ts"]): r for r in base}
    out = []
    for r in cand:
        k = (r["sym"], r["ts"])
        if k in b:
            out.append({"sym": r["sym"], "ts": r["ts"],
                        "ret": r["ret"] - b[k]["ret"],
                        "reason": r["reason"], "held": r["held"]})
    return out


# ------------------------------------------------------------- calibration

def ledger_episodes(ledger=None):
    """mum's REAL era closes, as (sym, opened_ts, actual_reason), both arms.

    `--ledger` takes a local dump: the public feed is a 2.4MB response that has
    truncated mid-transfer on this network, and a calibration target that
    sometimes arrives short is worse than one explicitly pinned.
    """
    import edge_audit as ea
    trades = ea.load_trades(ledger, 6000)
    shaped = ea.shape(trades)
    out = []
    for arm in ("freqtrade-mum-lighter", "freqtrade-mum-lshadow"):
        for q in (shaped.get(arm) or {}).get("rows") or []:
            ts = ea._ts(q[3])
            if ts is None:
                continue
            out.append({"sym": str(q[6] or "").split("/")[0],
                        "ts": int(ts.timestamp()),
                        "reason": ea.exit_of(q[7]), "arm": arm,
                        "ret": q[0] * 100.0})
    return out


def calibrate(led, mids, ladder, stop, hold):
    """C1 — replay her REAL entries through the SHIPPED ladder and compare the
    EXIT MIX. Fail-closed: any family outside CAL_TOL_PP withholds everything.

    The exit mix, not the mean, because a ladder change moves the MIX and a
    mean can match by luck on a small ledger.
    """
    rep, act, matched, unmatched = [], [], 0, 0
    for e in led:
        if e["sym"] not in mids:
            unmatched += 1
            continue
        try:
            bars = S.fetch_1h(e["sym"], mids[e["sym"]])
        except Exception:                                  # noqa: BLE001
            unmatched += 1
            continue
        idx = next((j for j, b in enumerate(bars) if b[0] >= e["ts"]), None)
        if idx is None or idx + 1 >= len(bars):
            unmatched += 1
            continue
        r = walk(bars, idx, ladder, stop, hold)
        if r is None:
            unmatched += 1
            continue
        rep.append(r[1])
        act.append(e["reason"])
        matched += 1
    if matched < 20:
        return {"ok": False, "why": f"only {matched} ledger rows replayable "
                                    "(<20) — the harness cannot be calibrated",
                "matched": matched, "unmatched": unmatched}
    fams = ("roi", "max_hold", "stop", "stop_loss")
    rs, as_ = Counter(rep), Counter(act)
    rows, worst = [], 0.0
    for f in ("roi", "max_hold"):
        pr = 100.0 * rs.get(f, 0) / matched
        pa = 100.0 * as_.get(f, 0) / matched
        rows.append({"exit": f, "replayed_pct": round(pr, 1),
                     "actual_pct": round(pa, 1), "gap_pp": round(pr - pa, 1)})
        worst = max(worst, abs(pr - pa))
    pr = 100.0 * (rs.get("stop", 0) + rs.get("stop_loss", 0)) / matched
    pa = 100.0 * (as_.get("stop", 0) + as_.get("stop_loss", 0)) / matched
    rows.append({"exit": "stop", "replayed_pct": round(pr, 1),
                 "actual_pct": round(pa, 1), "gap_pp": round(pr - pa, 1)})
    worst = max(worst, abs(pr - pa))
    return {"ok": worst <= CAL_TOL_PP, "worst_gap_pp": round(worst, 1),
            "tol_pp": CAL_TOL_PP, "matched": matched, "unmatched": unmatched,
            "mix": rows,
            "why": ("exit mix reproduces within tolerance" if worst <= CAL_TOL_PP
                    else f"worst family off by {worst:.1f}pp > {CAL_TOL_PP}pp — "
                         "EVERY recommendation is WITHHELD")}


# --------------------------------------------------------- reachability (L1)

def reachability(eps, ladder, stop, hold):
    """Per class: can the SHIPPED rungs actually be reached? The (xf)
    mechanism, on hundreds of episodes instead of 7."""
    out = {}
    for cls in ("crypto", "noncrypto"):
        sub = [e for e in eps if e["cls"] == cls]
        if not sub:
            continue
        mfe, hits = [], Counter()
        for e in sub:
            bars, i = e["bars"], e["i"]
            entry = bars[i][1]
            best = 0.0
            for k in range(i, min(i + hold, len(bars))):
                best = max(best, (bars[k][2] / entry - 1.0) * 100.0)
                age = (k - i) * 60
                thr = roi_thr(ladder, age) * 100.0
                if (bars[k][2] / entry - 1.0) * 100.0 >= thr:
                    hits["reached_a_rung"] += 1
                    break
            mfe.append(best)
        mfe.sort()
        n = len(mfe)
        out[cls] = {
            "n": n,
            "mfe_median_pct": round(mfe[n // 2], 3),
            "mfe_p90_pct": round(mfe[int(0.9 * n)], 3),
            "reach_first_rung_pct": round(
                100.0 * sum(1 for m in mfe if m >= ladder[0][1] * 100.0) / n, 1),
            "reached_any_rung_pct": round(100.0 * hits["reached_a_rung"] / n, 1),
        }
    return out


# ---------------------------------------------------------------- the sweep

def sweep(eps, ladder, stop, hold, cls="noncrypto"):
    """C3 grid over ladder scale k, then over max_hold, on one class.

    Reports THREE things per cell, deliberately not one: the candidate's
    AGGREGATE return per bar-day (the C4 verdict metric), its delta over
    shipped, and the PAIRED per-episode return delta with a cluster-t and
    chronological halves. Exposure (`bar_days`) is printed beside them so a
    cell that "wins" purely by holding less is visible as such.
    """
    sub = [e for e in eps if e["cls"] == cls]
    base = score(sub, ladder, stop, hold)
    b = agg(base)
    out = {"class": cls, "base": b, "k": [], "hold": []}

    def cell(rows, **tag):
        a = agg(rows)
        d = paired_delta(base, rows)
        da = agg(d) if d else {}
        h1, h2 = halves(d) if d else ({}, {})
        a.update(tag, paired=len(d),
                 d_pbd=(a["mean"] - b["mean"]) if (a.get("mean") is not None
                                                   and b.get("mean") is not None) else None,
                 d_ret=da.get("mean_pct"), d_t_cl=da.get("t_cl"),
                 d_h1=h1.get("mean_pct"), d_h2=h2.get("mean_pct"),
                 exposure_ratio=(a["bar_days"] / b["bar_days"])
                 if b.get("bar_days") else None)
        return a

    for k in K_GRID:
        out["k"].append(cell(score(sub, scale_ladder(ladder, k), stop, hold), k=k))
    for hh in HOLD_GRID:
        out["hold"].append(cell(score(sub, ladder, stop, hh), hold=hh))
    return out


def cell_scores(eps, ladder, stop, hold):
    """{cell: {episode_key: per_day}} — every cell walked ONCE.

    The walks do not depend on the class label, so C6 below is a
    re-AGGREGATION of these numbers rather than a re-walk. The first draft
    re-ran the whole sweep per draw: 400 draws x 10 cells x 22k episodes x 24
    bars is ~1e9 iterations and it did not finish. Caching is not an
    optimisation here, it is what makes the pre-registered C6 runnable at all.
    """
    cells = {"base": (ladder, hold)}
    for k in K_GRID:
        if k != 1.00:
            cells[f"k={k}"] = (scale_ladder(ladder, k), hold)
    for hh in HOLD_GRID:
        if hh != hold:
            cells[f"hold={hh}"] = (ladder, hh)
    return {name: {(r["sym"], r["ts"]): (r["ret"], r["held"])
                   for r in score(eps, lad, stop, hh)}
            for name, (lad, hh) in cells.items()}


def best_advantage_cached(cache, keys):
    """Best per-bar-day advantage over `base` across every cell, on `keys`."""
    base = cache["base"]
    def _agg(m, kk):
        rr = [m[k] for k in kk if k in m]
        if len(rr) < 2:
            return None
        d = sum(h for _, h in rr) / 24.0
        return (sum(r for r, _ in rr) / d) if d else None
    ks = [k for k in keys if k in base]
    b0 = _agg(base, ks)
    if b0 is None:
        return None
    best = None
    for name, m in cache.items():
        if name == "base":
            continue
        v = _agg(m, ks)
        if v is None:
            continue
        best = (v - b0) if best is None else max(best, v - b0)
    return best


def permutation(eps, cache, draws, seed=SEED):
    """C6 — re-run the SELECTION on shuffled class labels, sizes held.

    Prices cell selection AND the class label in ONE number: if best-of-N on a
    randomly-labelled half matches the real half's advantage, the advantage is
    the selection procedure, not the class.
    """
    keys_all = [(e["sym"], e["bars"][e["i"]][0]) for e in eps]
    labels = [e["cls"] for e in eps]
    real = best_advantage_cached(
        cache, [k for k, c in zip(keys_all, labels) if c == "noncrypto"])
    if real is None:
        return {"ok": False, "why": "no non-crypto episodes"}
    rnd = random.Random(seed)
    vals, ge = [], 0
    for _ in range(draws):
        sh = labels[:]
        rnd.shuffle(sh)
        v = best_advantage_cached(
            cache, [k for k, c in zip(keys_all, sh) if c == "noncrypto"])
        if v is None:
            continue
        vals.append(v)
        if v >= real:
            ge += 1
    n = len(vals) or 1
    vals.sort()
    return {"ok": True, "real": round(real, 4), "draws": len(vals),
            "p": round((ge + 1) / (n + 1), 4),
            "shuffled_median": round(vals[len(vals) // 2], 4) if vals else None,
            "shuffled_p95": round(vals[int(0.95 * len(vals))], 4) if vals else None}


def run(a):
    c = carrier()
    ladder, stop, hold, rsi_max = shipped_rule(c)
    print(f"# 👩 mum class-aware ladder — pre-registered, read-only\n")
    print(f"RULE READ FROM THE CARRIER: roi={dict(ladder)} stop={stop} "
          f"max_hold={hold}b rsi_max={rsi_max}")
    mids = S.market_ids()
    uni = fb.carrier_universe(c)
    eps = episodes(uni, mids, rsi_max)
    nc = sum(1 for e in eps if e["cls"] == "noncrypto")
    print(f"episodes: {len(eps)} total | noncrypto {nc} | crypto {len(eps)-nc}\n")

    led = ledger_episodes(a.ledger)
    cal = calibrate(led, mids, ladder, stop, hold)
    print("## C1 CALIBRATION (fail-closed, exit-mix)")
    for r in cal.get("mix", []):
        print(f"   {r['exit']:<10} replayed {r['replayed_pct']:>5.1f}%  "
              f"actual {r['actual_pct']:>5.1f}%  gap {r['gap_pp']:+.1f}pp")
    print(f"   -> {cal['why']} (matched {cal.get('matched')} of "
          f"{cal.get('matched',0)+cal.get('unmatched',0)} ledger rows)\n")

    rch = reachability(eps, ladder, stop, hold)
    print("## L1 REACHABILITY — is the crypto-fitted ladder reachable off-class?")
    for cls, d in rch.items():
        print(f"   {cls:<10} n={d['n']:<5} MFE median {d['mfe_median_pct']:>6.3f}% "
              f"p90 {d['mfe_p90_pct']:>6.3f}%  reaches first rung "
              f"{d['reach_first_rung_pct']:>5.1f}%  any rung "
              f"{d['reached_any_rung_pct']:>5.1f}%")
    print()

    if not cal["ok"]:
        print("VERDICT: WITHHELD — C1 failed. A harness that cannot reproduce "
              "what DID happen may not say what WOULD have.")
        return 2
    if nc < MIN_EPISODES:
        print(f"VERDICT: UNDECIDED — C2 floor: {nc} < {MIN_EPISODES} episodes.")
        return 0

    sw = sweep(eps, ladder, stop, hold)
    print("## C3/C4 SWEEP — non-crypto, entries CONSTANT. Verdict metric is the")
    print("##   AGGREGATE return per bar-day = total return / total bar-days.")
    b = sw["base"]
    print(f"   SHIPPED  n={b['n']}  per-bar-day {b['mean']:+.4f}%  "
          f"%/trade {b['mean_pct']:+.4f}%  total {b['total_ret']:+.1f}%  "
          f"exposure {b['bar_days']:.0f} bar-days  held {b['held_h']:.1f}h  {b['exits']}")
    hdr = ("   {:<9} pbd {:>9}  d_pbd {:>9}  d_ret {:>8}  t_cl {:>7}  "
           "halves {:>8}/{:>8}  expo {:>5}  {}")
    print(hdr.format("cell", "%/bar-day", "vs ship", "%/trade", "", "h1", "h2", "x", "exits"))
    for label, rows, key in (("k", sw["k"], "k"), ("hold", sw["hold"], "hold")):
        print(f"   -- {'ladder scale k (stop and hold held)' if label=='k' else 'max_hold bars (ladder held at shipped)'} --")
        for r in rows:
            print(f"   {label}={r[key]:<7} {r['mean']:+9.4f}  {r['d_pbd']:+9.4f}  "
                  f"{r['d_ret']:+8.4f}  {r['d_t_cl']:+7.2f}  "
                  f"{(r['d_h1'] or 0):+8.4f}/{(r['d_h2'] or 0):+8.4f}  "
                  f"{r['exposure_ratio']:.2f}  {r['exits']}")

    # every cell walked ONCE; C6 below re-aggregates, never re-walks
    cache = cell_scores(eps, ladder, stop, hold)
    # THE CONTROL, and it is the control for the hypothesis actually tested,
    # not a new one: the SAME pre-declared cells on the CRYPTO half. C6 prices
    # the class label statistically; this makes the answer legible. If the
    # crypto half responds to the ladder the same way, the finding is a
    # WHOLE-BOOK ladder question and not a class one — a larger and separately
    # registrable claim, never something to ship off this file's selection.
    swc = sweep(eps, ladder, stop, hold, cls="crypto")
    bc = swc["base"]
    print(f"\n## CONTROL — the same cells on the CRYPTO half")
    print(f"   SHIPPED  n={bc['n']}  per-bar-day {bc['mean']:+.4f}%  "
          f"%/trade {bc['mean_pct']:+.4f}%  exposure {bc['bar_days']:.0f} bar-days")
    for r in swc["k"]:
        if r["k"] == 1.00:
            continue
        print(f"   k={r['k']:<7} {r['mean']:+9.4f}  {r['d_pbd']:+9.4f}  "
              f"{r['d_ret']:+8.4f}  t_cl {r['d_t_cl']:+7.2f}  expo {r['exposure_ratio']:.2f}")

    perm = permutation(eps, cache, a.perm_draws)
    print(f"\n## C6 SELECTION PREMIUM (class labels shuffled, {perm.get('draws')} draws)")
    print(f"   best real advantage {perm.get('real'):+.4f}%/bar-day | "
          f"shuffled median {perm.get('shuffled_median')} p95 {perm.get('shuffled_p95')} "
          f"| p = {perm.get('p')}")

    res = {"rule": {"roi": dict(ladder), "stop": stop, "hold": hold,
                    "rsi_max": rsi_max},
           "episodes": {"total": len(eps), "noncrypto": nc},
           "calibration": cal, "reachability": rch, "sweep": sw, "control_crypto": swc,
           "permutation": perm}
    verdict(sw, perm)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1, default=str)
        print(f"\nwrote {a.json}")
    return 0


def verdict(sw, perm):
    """C7, applied mechanically to the pre-declared bars.

    The verdict metric is the AGGREGATE per-bar-day (`d_pbd`); the paired
    return delta and its cluster-t are the significance test. A cell must win
    on BOTH — a cell that raises per-bar-day only by cutting exposure has not
    made money, it has held less.
    """
    print("\n## C7 VERDICT")
    cells = [(f"k={r['k']}", r) for r in sw["k"] if r["k"] != 1.00] + \
            [(f"hold={r['hold']}", r) for r in sw["hold"] if r["hold"] != 24]
    good = [(n, r) for n, r in cells
            if (r["d_pbd"] or 0) > 0 and (r["d_ret"] or 0) > 0
            and (r["d_h1"] or 0) > 0 and (r["d_h2"] or 0) > 0]
    if not good:
        best = max(cells, key=lambda x: x[1]["d_pbd"] or -9e9)
        n, r = best
        print(f"   REFUSE — no cell beats shipped on BOTH the aggregate "
              f"per-bar-day and the paired return, in both halves.")
        print(f"   Best on per-bar-day is {n}: {r['d_pbd']:+.4f}%/bar-day, but "
              f"its paired return delta is {(r['d_ret'] or 0):+.4f}%/trade at "
              f"exposure {r['exposure_ratio']:.2f}x — "
              + ("it holds less, it does not earn more."
                 if (r['d_ret'] or 0) <= 0 else "halves disagree."))
        print("   A refusal with a number satisfies the growth rule (I19).")
        return
    name, r = max(good, key=lambda x: x[1]["d_pbd"])
    plateau = None
    if name.startswith("k="):
        ks = [c["k"] for c in sw["k"]]
        j = ks.index(r["k"])
        nb = [sw["k"][i] for i in (j - 1, j + 1)
              if 0 <= i < len(sw["k"]) and sw["k"][i]["k"] != 1.00]
        plateau = all((x["d_pbd"] or 0) > 0 for x in nb) if nb else None
    miss = []
    if (r["d_t_cl"] or 0) < T_BAR:
        miss.append(f"cluster-t {r['d_t_cl']:+.2f} < {T_BAR}")
    if plateau is False:
        miss.append("C5 plateau: a neighbour does not also beat shipped")
    if (perm.get("p") or 1.0) > 0.05:
        miss.append(f"C6 selection p={perm.get('p')} > 0.05 — the advantage is "
                    "not distinguishable from best-of-N on a random label")
    if miss:
        print(f"   HYPOTHESIS — {name} leads at {r['d_pbd']:+.4f}%/bar-day and "
              f"{r['d_ret']:+.4f}%/trade in both halves, but misses: "
              + "; ".join(miss) + ".")
        print("   NOT shipped. Named exactly so a later pass cannot read it as proven.")
    else:
        print(f"   SHIP — {name}: {r['d_pbd']:+.4f}%/bar-day and "
              f"{r['d_ret']:+.4f}%/trade over shipped, both halves, "
              f"t_cl {r['d_t_cl']:+.2f}, plateau holds, selection p={perm.get('p')}.")
        print("   INHERITS the declared limit: slot contention is not simulated "
              "and that term flatters this cell.")


def _selftest():
    ladder, stop, hold, rsi_max = shipped_rule()
    assert ladder == sorted((int(k), float(v)) for k, v in carrier().roi.items())
    assert hold == 24 and abs(stop + 0.04) < 1e-9, (hold, stop)
    # the generalised walk MUST reduce to the owner at the shipped ladder
    rnd = random.Random(SEED)
    bars = []
    px = 100.0
    for i in range(400):
        px *= 1.0 + rnd.gauss(0, 0.012)
        hi = px * (1 + abs(rnd.gauss(0, 0.008)))
        lo = px * (1 - abs(rnd.gauss(0, 0.008)))
        bars.append((1_700_000_000 + i * 3600, px, hi, lo, px, 1.0))
    same = 0
    for e in range(0, 300):
        mine = walk(bars, e, ladder, stop, hold)
        theirs = S.bracket_walk(bars, e)
        if theirs is None:
            assert mine is None, e
            continue
        assert mine is not None and abs(mine[0] - theirs[0]) < 1e-12 \
            and mine[1] == theirs[1], (e, mine, theirs)
        same += 1
    assert same > 200, f"only {same} episodes compared — the pin is vacuous"
    # scaling touches LEVELS only, never rung times (C3)
    sc = scale_ladder(ladder, 0.5)
    assert [a for a, _ in sc] == [a for a, _ in ladder]
    assert all(abs(v2 - v1 * 0.5) < 1e-12 for (_, v1), (_, v2) in zip(ladder, sc))
    assert scale_ladder(ladder, 1.0) == ladder
    # a lower ladder can only make roi EASIER — never harder (monotonicity)
    lo = walk(bars, 0, scale_ladder(ladder, 0.25), stop, hold)
    hi = walk(bars, 0, ladder, stop, hold)
    if lo and hi and lo[1] == "roi" and hi[1] == "roi":
        assert lo[2] <= hi[2], "a lower rung took LONGER to hit"
    # per_day is the (hl) guard: it must fall when a rule holds longer for
    # the same return, and a 1-bar and 24-bar hold of equal % differ 24x
    a = {"ret": 1.0, "held": 1}
    b = {"ret": 1.0, "held": 24}
    assert (a["ret"] / (a["held"] / 24.0)) == 24 * (b["ret"] / (b["held"] / 24.0))
    # C4's METRIC IS LOAD-BEARING AND MUST BE DRIVEN THROUGH `score`.
    # `per_day` is the verdict metric — the whole (hl) denominator-shrinkage
    # guard — so checking the arithmetic on a dict literal proves nothing about
    # what the sweep actually reads. Drive the real function and require that
    # per-bar-day DIFFERS from %/trade, or the guard is silently a per-trade
    # bar again (a mutation that swapped them survived the first round).
    fake = [{"sym": "X", "cls": "noncrypto", "i": 5, "bars": bars}]
    sc = score(fake, ladder, stop, hold)
    assert sc, "score() returned nothing on a resolvable episode"
    for r in sc:
        assert abs(r["per_day"] - r["ret"] / (r["held"] / 24.0)) < 1e-12, r
    assert any(abs(r["per_day"] - r["ret"]) > 1e-9 for r in sc), (
        "per-bar-day is identical to %/trade on every row — the (hl) guard "
        "cannot discriminate and C4 is decorative")
    # THE LADDER FLOOR IS THE CARRIER'S, at every rung. A collapsed floor
    # makes any positive tick an roi exit and every candidate look like an
    # instant-profit machine (that mutation also survived the first round).
    for age, want in ladder:
        assert abs(roi_thr(ladder, age) - want) < 1e-12, (age, want)
    assert abs(roi_thr(ladder, 0) - carrier().roi[0]) < 1e-12
    assert abs(roi_thr(ladder, 1) - carrier().roi[0]) < 1e-12, \
        "below the first rung the threshold must be the rung-0 level"
    assert roi_thr(ladder, 10 ** 9) == ladder[-1][1]
    assert ladder[0][0] == 0, (
        "the ladder no longer starts at age 0, so `roi_thr`'s initialiser is "
        "live and is a GUESSED floor below the first rung — give it an explicit "
        "below-first-rung behaviour before trusting any number from this file")
    # THE ARM THAT WOULD HAVE CAUGHT THE C4 DEFECT, added after it shipped.
    # `mean` must be the AGGREGATE sum(ret)/sum(bar-days), not the mean of
    # per-episode ratios. On a fast winner + slow loser the two DISAGREE IN
    # SIGN, and the mean-of-ratios says a losing book earns +23%/day. The live
    # run printed +1.7173%/bar-day beside a mean trade of -0.1333%, which is
    # what exposed it; nothing in the first selftest could.
    fx = [{"sym": "A", "cls": "noncrypto", "ts": 1, "ret": +2.0, "reason": "roi",
           "held": 1, "per_day": 48.0},
          {"sym": "B", "cls": "noncrypto", "ts": 2, "ret": -2.0, "reason": "stop",
           "held": 24, "per_day": -2.0}]
    g = agg(fx)
    assert abs(g["mean"] - 0.0) < 1e-9, (
        "`mean` is not the aggregate return per bar-day — a book that broke "
        f"even reads {g['mean']}")
    assert g["mean_ratio"] > 20, "the artifact must stay REPORTED, not deleted"
    assert abs(g["mean"] - g["mean_ratio"]) > 20, (
        "the fixture no longer separates the two metrics — it cannot "
        "discriminate and this arm is decorative")
    assert abs(g["bar_days"] - 25 / 24.0) < 1e-9 and g["total_ret"] == 0.0
    # ...and a SECOND fixture where all THREE candidate metrics differ, because
    # the break-even one above cannot tell the aggregate from %/trade (they are
    # both 0 there) — a mutation swapping them survived until this was added.
    fy = [dict(fx[0], ret=+2.0, held=1), dict(fx[1], ret=-1.0, held=24)]
    gy = agg(fy)
    assert abs(gy["mean"] - 1.0 / (25 / 24.0)) < 1e-9, (
        f"`mean` is not total return / total bar-days: {gy['mean']}")
    assert abs(gy["mean_pct"] - 0.5) < 1e-9
    assert abs(gy["mean"] - gy["mean_pct"]) > 0.4, (
        "aggregate per-bar-day and %/trade coincide on this fixture — it "
        "cannot discriminate them and the arm is decorative")
    assert gy["mean_ratio"] > 20
    # a PAIRED delta is in RETURN, so it must not carry a per_day field that a
    # later reader could mistake for the verdict metric
    pd_ = paired_delta([dict(fx[0], ret=1.0)], [dict(fx[0], ret=3.0)])
    assert pd_ and abs(pd_[0]["ret"] - 2.0) < 1e-9 and "per_day" not in pd_[0]
    # the class axis never guesses
    assert fbus.is_crypto("NOTACOIN") in (None, False, True)
    # THE ENTRY PREDICATE IS THE CARRIER'S OWN, DRIVEN — not asserted.
    # The docstring claims `signal_bars` mirrors `OversoldRebound.signals`;
    # a claim like that in prose is a claim that has not been written ((tt)),
    # so this DRIVES the carrier on growing prefixes of a real-shaped tape and
    # requires agreement on every bar, including the bars where it says NO.
    c = carrier()
    px, sbars = 100.0, []
    rnd2 = random.Random(SEED + 1)
    for i in range(S.WARMUP + 140):
        px *= 1.0 + rnd2.gauss(0, 0.02)          # wide, so rsi crosses the bar
        sbars.append((1_700_000_000 + i * 3600, px,
                      px * 1.004, px * 0.996, px, 1.0))
    mine = set(signal_bars(sbars, rsi_max))
    theirs, checked = set(), 0
    for i in range(S.WARMUP, len(sbars)):
        pre = sbars[:i + 1]
        sig = c.signals({"c": [b[4] for b in pre], "h": [b[2] for b in pre],
                         "l": [b[3] for b in pre], "v": [b[5] for b in pre]}, {})
        checked += 1
        if sig and sig.get("enter"):
            theirs.add(i)
    assert checked > 100, f"only {checked} bars driven — the check is vacuous"
    assert theirs, "the carrier never fired on this tape — fixture is inert"
    assert mine == theirs, ("the vectorised predicate disagrees with the "
                            f"carrier at {sorted(mine ^ theirs)[:8]}")
    print("study_mum_class_ladder selftest OK — the walk reduces to its owner "
          f"on {same} episodes, the entry predicate agrees with the carrier on "
          f"{checked} driven bars ({len(theirs)} fires), scaling touches levels "
          "only, per-bar-day is the metric, the rule is read from the carrier")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", help="local /trades.json?source=paper dump")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--perm-draws", type=int, default=PERM_DRAWS)
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
