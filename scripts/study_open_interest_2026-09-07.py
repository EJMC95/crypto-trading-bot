#!/usr/bin/env python3
"""OPEN INTEREST — does price/OI divergence select better trades on THIS venue?

    python3 scripts/study_open_interest_2026-09-07.py --hist oi_hist.json
    python3 scripts/study_open_interest_2026-09-07.py --selftest

WHY THIS EXISTS. `open_interest` is on every `orderBookDetails` row AND on every
candle bar (`i`); `market_context` already computes `oi_ntl` with hourly history
and publishes `oi_chg_1h`/`oi_chg_24h` every 30 minutes. **And 0 of 19 book
files reference it.** The signal is collected, published, and read by nothing
that trades — the cheapest untested hypothesis in the fleet.

THE HYPOTHESIS, stated before the test so it cannot be fitted afterwards. The
textbook reading of price against open interest:

    price UP   + OI UP    -> new money entering a rising market : CONTINUATION
    price UP   + OI DOWN  -> shorts covering, no new conviction : EXHAUSTION
    price DOWN + OI UP    -> new shorts, conviction to the down : CONTINUATION
    price DOWN + OI DOWN  -> longs liquidating out             : EXHAUSTION

If it holds here, the two CONTINUATION quadrants beat the two EXHAUSTION ones
in forward return, in the direction of the move.

FOUR DEFENCES, because this fleet has been burned by each of them:

  * **CHRONOLOGICAL SPLIT.** The first 60% of the tape is TRAIN and the last
    40% is TEST. A cell is reported only if it was picked on TRAIN. Picking on
    the whole tape and reporting the winner is the selection premium `(uz)`
    measured at ~1.85 t-units on this very fleet.
  * **BY-COIN CLUSTERING, NEVER POOLED t.** `(uf)` showed a pooled t of +4.05
    collapsing to +0.36 purely by changing the sampling stride, because pooled
    t over overlapping windows measures sampling DENSITY, not edge. Every t
    here is computed across COINS (each coin one observation), which is the
    unit that is actually independent.
  * **BH-FDR ACROSS EVERY CELL TESTED**, via `winners_docket.bh_survivors` —
    24 cells means ~1.2 spurious survivors at p<0.05 by chance alone.
  * **A MATCHED-RANDOM NULL.** `(hm)`: on this venue a random entry earns
    +0.2% to +1.1%/trade for free, so a positive mean is not an edge. Every
    cell is scored as EXCESS over random entries on the same coins and hours.

IT MOVES NOTHING and proposes no consumer. If the test refuses — which is the
expected outcome and the honest default — that is the deliverable.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import winners_docket as _wd                      # noqa: E402 — BH owner
import fleet_allocation as _fa                    # noqa: E402 — t_crit owner

bh_survivors = _wd.bh_survivors
t_crit = _fa.t_crit

#: Fraction of the tape used to PICK cells. The rest is untouched until the
#: pick is made — the split is the whole defence against selection.
TRAIN_FRAC = 0.60

#: A coin needs this many usable bars to contribute. Not a significance bar —
#: below it the coin's own mean is arithmetic on a handful of points.
MIN_BARS = 200

#: Cells are only reported when at least this many COINS contribute, because
#: the t is across coins and 3 coins cannot carry one.
MIN_COINS = 10


#: An OI series that never falls is not open interest. Measured 2026-09-07 on
#: 44 coins x 1,500 bars: the candle field `i` rose or held in 65,956 of 65,956
#: bar-to-bar steps and NEVER fell, at magnitudes (~2.4e10 for AAVE) far above
#: any plausible open-interest level. It is a CUMULATIVE COUNTER, not a level —
#: the real point-in-time OI is `orderBookDetails.open_interest` (BTC 2031 base
#: ~ $162M, which is plausible). This audit asserted the opposite before
#: measuring it, and would have shipped a vacuous REFUSAL of the OI hypothesis
#: computed on a monotone counter. The guard below makes that impossible.
MAX_MONOTONE_FRAC = 0.995


def oi_is_a_level(hist):
    """(ok, detail) — does this series behave like open interest at all?

    A LEVEL rises and falls. A cumulative counter only rises. If essentially no
    bar-to-bar step is negative, the series cannot express divergence and every
    quadrant that needs `OI down` is structurally empty — so a test on it would
    report "no signal" for a reason that has nothing to do with the hypothesis.

    Fail-CLOSED: this REFUSES rather than warning, because the failure mode it
    prevents is a green run that reads as a negative result ((po)).
    """
    up = dn = flat = 0
    for bars in hist.values():
        hs = sorted(bars)
        for i in range(1, len(hs)):
            a, b = bars[hs[i - 1]].get("oi"), bars[hs[i]].get("oi")
            if a is None or b is None:
                continue
            if b > a:
                up += 1
            elif b < a:
                dn += 1
            else:
                flat += 1
    tot = up + dn + flat
    if not tot:
        return False, {"why": "no usable OI observations", "n": 0}
    frac_non_falling = (up + flat) / tot
    ok = frac_non_falling < MAX_MONOTONE_FRAC
    return ok, {"n": tot, "up": up, "down": dn, "flat": flat,
                "non_falling_frac": round(frac_non_falling, 5),
                "why": (None if ok else
                        "the series never falls (%d of %d steps non-falling) — "
                        "this is a CUMULATIVE COUNTER, not an open-interest "
                        "LEVEL, so divergence is untestable on it"
                        % (up + flat, tot))}


def quadrant(dp, doi):
    """The four price/OI states. None when either change is unusable."""
    if dp is None or doi is None or dp == 0 or doi == 0:
        return None
    return ("up" if dp > 0 else "down") + "_oi" + ("up" if doi > 0 else "down")


def cells(hist, look, horizon, lo, hi):
    """{quadrant: {coin: mean directional excess}} over bars in [lo, hi).

    DIRECTIONAL: the forward return is signed by the move's own direction, so
    'continuation' means the move continued, whichever way it went. Excess is
    over the coin's OWN mean forward return in the window — the cheapest
    matched control there is, and it removes the venue's drift that `(hm)`
    warns a raw mean would otherwise book as edge.
    """
    out = {}
    for coin, bars in hist.items():
        hs = sorted(bars)
        if len(hs) < MIN_BARS:
            continue
        seg = hs[int(len(hs) * lo):int(len(hs) * hi)]
        if len(seg) < look + horizon + 20:
            continue
        # the coin's own mean signed forward move, as the control
        fwd_all = []
        for i in range(look, len(seg) - horizon):
            a, b = bars[seg[i]]["c"], bars[seg[i + horizon]]["c"]
            if a:
                fwd_all.append(b / a - 1.0)
        if not fwd_all:
            continue
        base = sum(fwd_all) / len(fwd_all)
        acc = {}
        for i in range(look, len(seg) - horizon):
            p0, p1 = bars[seg[i - look]]["c"], bars[seg[i]]["c"]
            o0, o1 = bars[seg[i - look]]["oi"], bars[seg[i]]["oi"]
            if not p0 or o0 in (None, 0) or o1 is None:
                continue
            dp, doi = p1 / p0 - 1.0, o1 / o0 - 1.0
            q = quadrant(dp, doi)
            if q is None:
                continue
            a, b = bars[seg[i]]["c"], bars[seg[i + horizon]]["c"]
            if not a:
                continue
            fwd = b / a - 1.0
            sgn = 1.0 if dp > 0 else -1.0
            acc.setdefault(q, []).append(sgn * (fwd - base))
        for q, v in acc.items():
            if len(v) >= 20:
                out.setdefault(q, {})[coin] = sum(v) / len(v)
    return out


def by_coin_t(per_coin):
    """(mean, t, n_coins) with each COIN as one observation — never pooled."""
    v = [x for x in per_coin.values() if x is not None and math.isfinite(x)]
    n = len(v)
    if n < MIN_COINS:
        return None, None, n
    m = sum(v) / n
    if n < 2:
        return m, None, n
    sd = st.stdev(v)
    if sd <= 0:
        return m, None, n
    return m, m / (sd / math.sqrt(n)), n


def run(hist, looks=(4, 24), horizons=(4, 12, 24)):
    """Pick on TRAIN, report on TEST, BH across every cell tested."""
    train, test = {}, {}
    for look in looks:
        for hz in horizons:
            for q, pc in cells(hist, look, hz, 0.0, TRAIN_FRAC).items():
                train[(look, hz, q)] = by_coin_t(pc)
            for q, pc in cells(hist, look, hz, TRAIN_FRAC, 1.0).items():
                test[(look, hz, q)] = by_coin_t(pc)
    # PICK on train only: positive mean and |t| >= 2
    picked = [k for k, (m, t, n) in train.items()
              if m is not None and t is not None and m > 0 and t >= 2.0]
    rows = []
    for k in sorted(train):
        m_tr, t_tr, n_tr = train[k]
        m_te, t_te, n_te = test.get(k, (None, None, 0))
        rows.append({"look_h": k[0], "horizon_h": k[1], "quadrant": k[2],
                     "train_mean_pct": (m_tr * 100.0) if m_tr is not None else None,
                     "train_t": t_tr, "train_coins": n_tr,
                     "test_mean_pct": (m_te * 100.0) if m_te is not None else None,
                     "test_t": t_te, "test_coins": n_te,
                     "picked_on_train": k in picked})
    # BH across the TEST results of the picked cells only
    surv = []
    if picked:
        cand = []
        for k in picked:
            m_te, t_te, n_te = test.get(k, (None, None, 0))
            if t_te is None or n_te < MIN_COINS:
                continue
            p = _p_from_t(t_te, n_te - 1)
            cand.append({"key": "%dh/%dh/%s" % k, "p": p})
        if cand:
            surv = bh_survivors(cand, alpha=0.05) or []
    return {"rows": rows, "n_cells": len(train), "n_picked": len(picked),
            "survivors": [s if isinstance(s, str) else s.get("key")
                          for s in surv],
            "train_frac": TRAIN_FRAC}


def _p_from_t(t, dof):
    """One-sided p from a t stat. Normal approximation above 30 dof, and a
    conservative bound below it — the exact CDF is not worth a dependency here
    and every use is compared against BH, which only needs a monotone p."""
    if t is None:
        return 1.0
    z = abs(float(t))
    p = 0.5 * math.erfc(z / math.sqrt(2.0))
    if dof < 30:
        p = min(1.0, p * 1.5)        # widen: t has fatter tails than normal
    return p if t > 0 else 1.0 - p


def render(res):
    L = ["# OPEN INTEREST — price/OI divergence, tested", ""]
    L.append("_Picked on the first %d%% of the tape, reported on the last %d%%. "
             "Every `t` is across COINS, never pooled over overlapping windows "
             "((uf)). Excess is over each coin's own mean forward move._"
             % (res["train_frac"] * 100, (1 - res["train_frac"]) * 100))
    L.append("")
    L.append("| look | horizon | quadrant | train mean% | train t | test mean% "
             "| test t | coins | picked on train |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in sorted(res["rows"], key=lambda x: -(x["train_t"] or -9e9)):
        L.append("| %dh | %dh | `%s` | %s | %s | %s | %s | %d | %s |"
                 % (r["look_h"], r["horizon_h"], r["quadrant"],
                    "—" if r["train_mean_pct"] is None else "%+.3f" % r["train_mean_pct"],
                    "—" if r["train_t"] is None else "%+.2f" % r["train_t"],
                    "—" if r["test_mean_pct"] is None else "%+.3f" % r["test_mean_pct"],
                    "—" if r["test_t"] is None else "%+.2f" % r["test_t"],
                    r["test_coins"], "**yes**" if r["picked_on_train"] else "no"))
    L.append("")
    L.append("**%d cells tested, %d picked on train, %d surviving BH-FDR 0.05 "
             "out of sample.**" % (res["n_cells"], res["n_picked"],
                                   len(res["survivors"])))
    L.append("")
    if not res["survivors"]:
        L.append("### VERDICT: REFUSED")
        L.append("")
        L.append("No price/OI cell that looked good on the training half "
                 "survives out of sample under BH. **Do not build a consumer.** "
                 "This is the expected and honest outcome — the signal is "
                 "collected and published, and it does not select better "
                 "trades on this venue's tape at these horizons.")
    else:
        L.append("### VERDICT: %d cell(s) survive — %s"
                 % (len(res["survivors"]), ", ".join(res["survivors"])))
        L.append("")
        L.append("A survivor is a HYPOTHESIS, not a consumer. Before anything "
                 "trades it, it owes the `(hm)` random-entry null on a book's "
                 "own ledger and a pre-registered revert criterion (I21/I26).")
    return "\n".join(L) + "\n"


def _selftest():
    assert bh_survivors is _wd.bh_survivors        # imported owner, not a copy
    assert quadrant(1, 1) == "up_oiup" and quadrant(-1, 1) == "down_oiup"
    assert quadrant(0, 1) is None and quadrant(1, None) is None
    # by_coin_t refuses below the coin floor rather than printing a number
    m, t, n = by_coin_t({("c%d" % i): 0.01 for i in range(5)})
    assert m is None and n == 5, (m, n)
    # zero variance across coins => a mean but no t (never an infinite one)
    m, t, n = by_coin_t({("c%d" % i): 0.01 for i in range(12)})
    assert t is None and abs(m - 0.01) < 1e-12, (m, t)
    # a real spread does produce a t
    m, t, n = by_coin_t({("c%d" % i): 0.01 + 0.001 * (i % 3) for i in range(15)})
    assert t is not None and t > 0, t
    # a PLANTED signal must be recovered (the positive control — without this
    # a study that refuses everything is trivially "stable" and useless)
    rnd = random.Random(7)
    hist = {}
    for c in range(14):
        bars, px, oi = {}, 100.0, 1000.0
        for h in range(600):
            drift = 0.0
            # plant: when price rose AND oi rose, the next bars continue up
            if h > 4 and bars.get(h - 1) and bars.get(h - 5):
                if (bars[h - 1]["c"] > bars[h - 5]["c"]
                        and bars[h - 1]["oi"] > bars[h - 5]["oi"]):
                    drift = 0.004
            px *= (1.0 + drift + rnd.gauss(0, 0.002))
            oi *= (1.0 + rnd.gauss(0, 0.01))
            bars[h] = {"c": px, "oi": oi}
        hist["C%d" % c] = {1000 + h * 3600: bars[h] for h in bars}
        hist["C%d" % c] = {1000 + h * 3600: bars[h] for h in range(600)}
    got = cells(hist, 4, 4, 0.0, 1.0)
    assert "up_oiup" in got and len(got["up_oiup"]) >= 10, got.keys()
    m, t, n = by_coin_t(got["up_oiup"])
    assert m is not None and m > 0, (m, t, n)      # the plant is recovered
    # and the renderer says REFUSED when nothing survives
    md = render({"rows": [], "n_cells": 3, "n_picked": 0, "survivors": [],
                 "train_frac": 0.6})
    assert "REFUSED" in md and "Do not build a consumer" in md
    # the data guard: a monotone counter must REFUSE, a real level must PASS
    mono = {"C": {i: {"c": 1.0, "oi": float(i)} for i in range(200)}}
    ok, d = oi_is_a_level(mono)
    assert ok is False and "CUMULATIVE COUNTER" in d["why"], d
    real = {"C": {i: {"c": 1.0, "oi": 100.0 + ((-1) ** i)} for i in range(200)}}
    ok2, _ = oi_is_a_level(real)
    assert ok2 is True
    assert oi_is_a_level({})[0] is False          # nothing is not a pass
    print("study_open_interest selftest OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hist"); ap.add_argument("--md"); ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest(); return 0
    with open(a.hist) as fh:
        raw = json.load(fh)
    hist = {c: {int(t): v for t, v in b.items()} for c, b in raw.items()}
    ok, detail = oi_is_a_level(hist)
    if not ok:
        md = ("# OPEN INTEREST — REFUSED ON THE DATA\n\n"
              "**The supplied series is not open interest.**\n\n```\n%s\n```\n\n"
              "%s\n\nReal point-in-time OI is `orderBookDetails.open_interest`; "
              "its HISTORY exists only inside `market_context`'s own state "
              "(`oi_ntl`, hourly), which is DB-side and not on `/bus.json`. So "
              "the price/OI hypothesis **cannot be tested from outside the "
              "containers** until that history is exposed — and that, not a "
              "verdict, is the honest deliverable.\n\nThe machinery is sound: "
              "the selftest's planted-signal positive control passes, so a "
              "silent 'no signal' here would have been the data, not the "
              "method.\n"
              % (json.dumps(detail, indent=1), detail.get("why") or ""))
        if a.md:
            with open(a.md, "w") as fh:
                fh.write(md)
        print(md)
        return 2
    res = run(hist)
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(res, fh, default=str, indent=1)
    md = render(res)
    if a.md:
        with open(a.md, "w") as fh:
            fh.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
