#!/usr/bin/env python3
"""
study_grimes_gate_2026-08-16.py — FIXING 📐 GRIMES'S GATE, MEASURED FIRST.

    .venv/bin/python3 scripts/study_grimes_gate_2026-08-16.py
    .venv/bin/python3 scripts/study_grimes_gate_2026-08-16.py --selftest

THE DEFECT (oe). 📐 book-grimes ships a setup ROSTER behind a rolling replay
gate — its entire thesis is the DISCIPLINE of that gate, not any setup. The
gate replays `resolve_universe()`, the set it will actually trade, which is a
top-18-BY-VOLUME ranking. That set CHURNS, and at n~100 with a true effect near
zero the churn dominates the statistic:

  * on a FIXED 18-coin universe, trailing-126d keltner `t` never crosses the
    0.5 bar in 90 days: range [-2.09, +0.09], 0 of 31 retests open;
  * changing ONLY the coin set at a FIXED as-of moves `t` across **3.82**
    (-2.55 .. +1.27) and opens the gate in 4 of 12 nine-coin draws;
  * the live gate is nonetheless OPEN at t=+0.53 against a 0.5 bar.

So the gate cannot distinguish "this setup's edge changed" from "the coin list
changed", and it is currently open on the second.

WHAT A FIX MUST DO — both halves, or it is not a fix:
  1. **STABLE**: the verdict must not flip because a different plausible
     universe was drawn.
  2. **STILL ABLE TO FIRE**: a gate that never opens is trivially stable and
     useless — it would starve the book into an I17 retirement by construction.
     Every candidate is therefore run against a POSITIVE CONTROL (real trades
     with a constant edge added). A candidate that cannot open on a real edge
     is REJECTED however stable it looks. This is I3 applied to a gate.

CANDIDATES (pre-declared):
  base    the shipped gate: n>=20, net>0, t>=0.5 on the graded universe
  fixed   grade the book's OWN measured DEFAULT_COINS set, always. The set the
          founding study used; it does not churn. Trading is unchanged.
  sub80   subsample-stable: draw R sub-universes, open only if >=80% clear the
          bar. Targets the instability directly rather than the universe.
  win240  double the window to 240d (more n, less churn sensitivity)
  tbar10  raise the bar to t>=1.0 on the churning universe (the crude option,
          included so "just move the bar" is measured rather than dismissed)

HONEST ABOUT WHAT THIS CANNOT DO: point-in-time volume is not reconstructable
from the venue's API, so the churn is SIMULATED by resampling the measured
18-coin set. That is a proxy for real membership drift, not a replay of it.
Stated rather than buried — it is the same survivorship caveat the founding
study carries.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    "books_cohort", os.path.join(HERE, "study_books_cohort_2026-08-13.py"))
BC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BC)

CLIP, CAP = 80.0, 2
GATE_MIN_N, GATE_MIN_T = 20, 0.5
WINDOW_D = 126.0
SETUPS = ("pullback", "failtest", "keltner")


def load_tape():
    c4 = json.load(open(os.path.join(BC.CACHE, "candles_4h.json")))
    cd = json.load(open(os.path.join(BC.CACHE, "candles_1d.json")))
    return c4, cd


def _signals(c4t, cdt, setup):
    at = {s: BC.atr_series(r, 14) for s, r in c4t.items()}
    e20 = {s: BC.ema_series([r[4] for r in c4t[s]], 20) for s in c4t}
    e50 = {s: BC.ema_series([r[4] for r in c4t[s]], 50) for s in c4t}
    dtr = {}
    for s in c4t:
        if s not in cdt:
            continue
        dcl = [r[4] for r in cdt[s]]
        d20, d50 = BC.ema_series(dcl, 20), BC.ema_series(dcl, 50)
        dtr[s] = {cdt[s][j][0] // 86400 + 1:
                  (0 if (d20[j] is None or d50[j] is None)
                   else (1 if d20[j] > d50[j] else -1))
                  for j in range(len(cdt[s]))}

    def trend(s, i):
        d = dtr.get(s, {}).get(c4t[s][i][0] // 86400)
        return d if d in (-1, 1) else None      # (ml) fail-closed on no-claim

    sigs = {}
    for s, rows in c4t.items():
        out = []
        for i in range(56, len(rows) - 1):
            a = at[s][i]
            if not a:
                continue
            _, o, h, l, c = rows[i][:5]
            if setup == "pullback":
                xf, xs = e20[s][i], e50[s][i]
                d = trend(s, i)
                if not (xf and xs) or d is None:
                    continue
                if d > 0 and xf > xs and l <= xf and c > xf:
                    out.append((i, "long", 1.5 * a, 4.5 * a, 20, None))
                elif d < 0 and xf < xs and h >= xf and c < xf:
                    out.append((i, "short", 1.5 * a, 4.5 * a, 20, None))
            elif setup == "failtest":
                if i < 22:
                    continue
                hh = max(r[2] for r in rows[i - 20:i])
                ll = min(r[3] for r in rows[i - 20:i])
                if l < ll and c > ll:
                    out.append((i, "long", 1.0 * a, 2.0 * a, 12, None))
                elif h > hh and c < hh:
                    out.append((i, "short", 1.0 * a, 2.0 * a, 12, None))
            else:                                     # keltner
                xf = e20[s][i]
                d = trend(s, i)
                if not xf or d is None:
                    continue
                if c > xf * (1 + 2.25 * a) and d <= 0:
                    out.append((i, "short", 1.5 * a, 2.25 * a, 20, None))
                elif c < xf * (1 - 2.25 * a) and d >= 0:
                    out.append((i, "long", 1.5 * a, 2.25 * a, 20, None))
        sigs[s] = out
    return sigs, at


def record(c4, cd, asof, coins, setup, win_d=WINDOW_D, edge=0.0):
    """The trailing record for one setup on one coin set. `edge` adds a
    constant to every trade's return — the POSITIVE CONTROL."""
    cut = asof - win_d * 86400
    c4t = {s: [r for r in c4[s] if cut <= r[0] <= asof]
           for s in coins if s in c4}
    c4t = {s: r for s, r in c4t.items() if len(r) > 100}
    if not c4t:
        return None
    cdt = {s: [r for r in cd[s] if cut - 60 * 86400 <= r[0] <= asof]
           for s in c4t if s in cd}
    sigs, at = _signals(c4t, cdt, setup)
    closed = BC.run_portfolio(sigs, c4t, CAP, 14400, at)
    rets = [c["ret"] + edge for c in closed]
    n = len(rets)
    if n < 3:
        return dict(n=n, net=0.0, t=0.0)
    return dict(n=n, net=sum(rets) * CLIP, t=BC.t_stat(rets))


def _clears(rec, min_t=GATE_MIN_T):
    return bool(rec and rec["n"] >= GATE_MIN_N and rec["net"] > 0
                and rec["t"] >= min_t)


# ------------------------------------------------------------- candidates
def gate(kind, c4, cd, asof, traded, fixed_set, setup, edge=0.0, rng=None):
    """Each candidate returns True/False for 'may this setup enter now?'"""
    if kind == "base":
        return _clears(record(c4, cd, asof, traded, setup, edge=edge))
    if kind == "fixed":
        return _clears(record(c4, cd, asof, fixed_set, setup, edge=edge))
    if kind == "win240":
        return _clears(record(c4, cd, asof, traded, setup, win_d=240.0,
                              edge=edge))
    if kind == "tbar10":
        return _clears(record(c4, cd, asof, traded, setup, edge=edge),
                       min_t=1.0)
    if kind == "sub80":
        rng = rng or random.Random(0)
        pool = sorted(traded)
        k = max(6, int(len(pool) * 0.7))
        ok = 0
        draws = 10
        for _ in range(draws):
            sub = rng.sample(pool, min(k, len(pool)))
            if _clears(record(c4, cd, asof, sub, setup, edge=edge)):
                ok += 1
        return ok >= 0.8 * draws
    raise ValueError(kind)


CANDIDATES = ("base", "fixed", "sub80", "win240", "tbar10")


def main():
    c4, cd = load_tape()
    universe = sorted(c4)
    fixed_set = list(universe)                  # the book's DEFAULT_COINS set
    last = max(r[-1][0] for r in c4.values())
    rng = random.Random(20260816)

    print(f"tape: {len(universe)} coins; as-of "
          f"{time.strftime('%Y-%m-%d', time.gmtime(last))}\n")

    # ---- 1. STABILITY: does the verdict survive a different plausible draw?
    print("1. VERDICT STABILITY — 12 simulated universes (12 of 18 coins), "
          "keltner, fixed as-of.")
    print("   A fix must give the SAME answer regardless of which draw it sees.")
    draws = [rng.sample(universe, 12) for _ in range(12)]
    stab = {}
    for kind in CANDIDATES:
        verdicts = [gate(kind, c4, cd, last, d, fixed_set, "keltner",
                         rng=random.Random(7)) for d in draws]
        opens = sum(verdicts)
        agree = max(opens, len(verdicts) - opens) / len(verdicts)
        stab[kind] = agree
        print(f"   {kind:<8} open in {opens:>2}/12 draws   agreement "
              f"{agree*100:>5.1f}%")

    # ---- 2. CAN IT STILL FIRE? the positive control ----------------------
    print("\n2. POSITIVE CONTROL — the same trades with a constant edge added.")
    print("   A gate that cannot open on a REAL edge is not a fix, it is a"
          " starved book (I3).")
    print(f"   {'cand':<8}" + "".join(f"{f'+{e*100:.2f}%':>10}"
                                      for e in (0.0, 0.0025, 0.005, 0.01)))
    fires = {}
    for kind in CANDIDATES:
        row, opened = [], False
        for e in (0.0, 0.0025, 0.005, 0.01):
            v = gate(kind, c4, cd, last, universe, fixed_set, "keltner",
                     edge=e, rng=random.Random(7))
            row.append("OPEN" if v else "closed")
            opened = opened or (v and e > 0)
        fires[kind] = opened
        print(f"   {kind:<8}" + "".join(f"{x:>10}" for x in row))

    # ---- 3. OPEN-RATE OVER TIME on the churning universe -----------------
    print("\n3. OPEN RATE over 90d (every 10d, keltner, simulated churn each "
          "retest)")
    for kind in CANDIDATES:
        opens = 0
        steps = list(range(9, -1, -1))
        for k in steps:
            asof = last - k * 10 * 86400
            traded = rng.sample(universe, 12)
            if gate(kind, c4, cd, asof, traded, fixed_set, "keltner",
                    rng=random.Random(7)):
                opens += 1
        print(f"   {kind:<8} open at {opens}/{len(steps)} retests")

    # ---- verdict ---------------------------------------------------------
    print("\n" + "=" * 68)
    print("VERDICT — a fix must be BOTH stable and able to fire")
    print("=" * 68)
    for kind in CANDIDATES:
        ok = stab[kind] >= 0.95 and fires[kind]
        print(f"  {kind:<8} stability {stab[kind]*100:>5.1f}%  "
              f"fires-on-edge {str(fires[kind]):<5}  "
              f"{'PASS' if ok else 'fail'}")
    return 0


def _selftest():
    c4, cd = load_tape()
    uni = sorted(c4)
    last = max(r[-1][0] for r in c4.values())
    r = record(c4, cd, last, uni, "keltner")
    assert r and r["n"] > 20, r
    # the positive control must actually move the record, or it tests nothing
    r2 = record(c4, cd, last, uni, "keltner", edge=0.01)
    assert r2["net"] > r["net"] + 50, (r["net"], r2["net"])
    assert r2["t"] > r["t"], (r["t"], r2["t"])
    # the fixed candidate must ignore the traded set it is handed
    a = gate("fixed", c4, cd, last, uni[:8], uni, "keltner")
    b = gate("fixed", c4, cd, last, uni[8:], uni, "keltner")
    assert a == b, "the fixed gate must not depend on the traded universe"
    # ...and the base candidate must NOT ignore it (or the test is vacuous)
    ra = record(c4, cd, last, uni[:8], "keltner")
    rb = record(c4, cd, last, uni[8:], "keltner")
    assert abs(ra["t"] - rb["t"]) > 0.05, (ra["t"], rb["t"])
    print("study_grimes_gate selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
