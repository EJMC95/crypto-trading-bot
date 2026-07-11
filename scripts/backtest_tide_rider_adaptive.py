#!/usr/bin/env python3
"""
scripts/backtest_tide_rider_adaptive.py — SPEC + walk-forward backtest of an
ADAPTIVE dual-mode Tide Rider (trend + range) for Lighter. "Just in case" it helps.

WHY: Tide Rider (50/200 golden-cross long) sits in CASH whenever no major is trending
(right now: 5 of 6 idle). The standing goal is bots that trade in EVERY regime. This
specs + tests a complementary RANGE mode that fills only the idle (non-golden) time,
WITHOUT touching the proven trend mode.

SPEC (per coin, daily, causal — position decided at close t, held day t+1):
  regime by EMA50 vs EMA200:
    * GOLDEN (ema50>ema200)  -> TREND mode: long. IDENTICAL to the live incumbent.
    * not golden, sep>=-dtrend -> RANGE mode: mean-revert around SMA20.
        z = (close-SMA20)/std20.  z<-z_in -> long (oversold); z>+z_in -> SHORT
        (overbought). Exit when z crosses back through 0, or regime flips, or stop.
    * not golden, sep<-dtrend (strong downtrend) -> FLAT (like the incumbent).
  Perp funding is directional: a long PAYS funding, a SHORT RECEIVES it (so the
  range short has a funding tailwind, opposite the trend long's drag). Hard stop
  bounds mean-reversion-into-a-trend. use_range=False reduces EXACTLY to the incumbent.

HONESTY: this fleet already RETIRED a standalone RSI-perp mean-reversion bot, and 5
prior "optimize Tide Rider" attempts were all mirages. So it's WALK-FORWARD OOS only
(tune the range knobs on TRAIN, score on the UNSEEN TEST window). The range mode earns
a build ONLY if adaptive beats trend-only OUT OF SAMPLE on return AND risk (ret/maxDD),
not just by trading more. Reuses the shootout engine's majors cache + funding/fee model.

Usage:  python scripts/backtest_tide_rider_adaptive.py
"""
import importlib.util
import math
import os

_spec = importlib.util.spec_from_file_location(
    "shoot", os.path.join(os.path.dirname(__file__), "backtest_strategy_shootout.py"))
S = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(S)
FEE = S.FEE


def rstd(c, n):
    out = [None] * len(c)
    for i in range(n - 1, len(c)):
        w = c[i - n + 1:i + 1]
        m = sum(w) / n
        out[i] = math.sqrt(sum((x - m) ** 2 for x in w) / n)
    return out


def adaptive_positions(c, z_in=1.5, stop=0.10, dtrend=0.05, use_range=True, side="both"):
    """Signed target position per day (+1 long / -1 short / 0 flat). use_range=False
    reduces to the incumbent (long iff golden, else flat). side restricts the RANGE
    mode to 'long' (oversold bounces only) or 'short' (overbought fades only)."""
    e50, e200 = S.ema(c, 50), S.ema(c, 200)
    m20, s20 = S.sma(c, 20), rstd(c, 20)
    pos = 0; entry = 0.0; tgt = [0] * len(c)
    for i in range(len(c)):
        if i < 200:
            continue
        golden = e50[i] > e200[i]
        sep = (e50[i] - e200[i]) / e200[i]
        z = (c[i] - m20[i]) / s20[i] if (m20[i] and s20[i]) else 0.0
        if pos != 0 and entry and (c[i] - entry) / entry * pos <= -stop:
            pos = 0                                   # hard stop
        if golden:
            if pos <= 0:
                pos = 1; entry = c[i]                 # trend long (incumbent)
        elif not use_range or sep < -dtrend:
            pos = 0                                    # strong downtrend / range off -> flat
        else:
            if pos == 1:                               # trend just ended -> drop the long
                pos = 0
            if pos == 0:
                if z < -z_in and side in ("both", "long"):
                    pos = 1; entry = c[i]              # oversold bounce (long)
                elif z > z_in and side in ("both", "short"):
                    pos = -1; entry = c[i]             # overbought fade (short, funding tailwind)
            elif pos == 1 and z >= 0:
                pos = 0
            elif pos == -1 and z <= 0:
                pos = 0
        tgt[i] = pos
    return tgt


def signed_curve(c, t, f, tgt, lo, hi):
    """Daily-compounded perp equity for a SIGNED position path. step = s*(r - fund):
    a long (s=+1) pays funding, a short (s=-1) receives it. Fee on turnover |s-prev|."""
    eq = 1.0; curve = []; prev = 0; inmkt = 0; days = 0
    for i in range(max(201, lo), hi):
        s = tgt[i - 1]                                # decided yesterday, held today
        r = c[i] / c[i - 1] - 1.0
        fund = f.get(t[i], 0.0)
        step = s * (r - fund) - FEE * abs(s - prev)
        eq *= (1 + step); prev = s
        curve.append(eq); days += 1; inmkt += 1 if s != 0 else 0
    return curve, (inmkt / max(1, days))


def basket(data, params, lo, hi):
    curves = []; inm = []
    for c in data:
        d = data[c]
        tgt = adaptive_positions(d["c"], **params)
        cur, im = signed_curve(d["c"], d["t"], d["f"], tgt, lo, hi)
        if cur:
            curves.append(cur); inm.append(im)
    if not curves:
        return None
    n = min(len(x) for x in curves)
    beq = [sum(x[k] for x in curves) / len(curves) for k in range(n)]
    peak = beq[0]; mdd = 0.0
    for v in beq:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1.0)
    return {"ret": beq[-1] - 1.0, "mdd": mdd, "inmkt": sum(inm) / len(inm)}


def wf(warm, N, k=3):
    start = warm + 1; span = N - start
    q = [start + span * i // (k + 1) for i in range(k + 2)]
    return [(start, q[i + 1], q[i + 1], q[i + 2]) for i in range(k)]


def main():
    data = S.load_majors()
    N = min(len(d["c"]) for d in data.values())
    folds = wf(200, N, 3)
    print(f"Adaptive Tide Rider (trend+range) — walk-forward OOS, 6 majors 1x perp, {N}d")
    print(f"test windows {[(lo, hi) for _, _, lo, hi in folds]}\n")

    incumbent = {"use_range": False}
    grid = [{"z_in": z, "stop": st, "dtrend": dt, "use_range": True}
            for z in (1.0, 1.5, 2.0) for st in (0.08, 0.12) for dt in (0.04, 0.08)]

    def oos(family_grid):
        eq = 1.0; per = []; inm = []
        for (trlo, trhi, telo, tehi) in folds:
            best = None
            for p in family_grid:
                tr = basket(data, p, trlo, trhi)
                if tr and (best is None or tr["ret"] > best[0]):
                    best = (tr["ret"], p)
            p = best[1]
            te = basket(data, p, telo, tehi)
            per.append((te["ret"], te["mdd"], p)); inm.append(te["inmkt"]); eq *= (1 + te["ret"])
        return eq - 1.0, per, sum(inm) / len(inm)

    def grid_side(sd):
        return [{"z_in": z, "stop": st, "dtrend": dt, "use_range": True, "side": sd}
                for z in (1.0, 1.5, 2.0) for st in (0.08, 0.12) for dt in (0.04, 0.08)]

    fams = [("trend-only (incumbent)", [incumbent]),
            ("adaptive both-side", grid_side("both")),
            ("adaptive long-only", grid_side("long")),
            ("adaptive short-only", grid_side("short"))]
    b_oos = None
    print(f"{'family':>22} | {'OOS%':>7} {'avg maxDD%':>10} {'%in-mkt':>8} | per-fold OOS%")
    print("-" * 82)
    for label, fg in fams:
        o, per, inm = oos(fg)
        if b_oos is None:
            b_oos, b_per, b_inm = o, per, inm
        print(f"{label:>22} | {o*100:>7.1f} "
              f"{sum(m for _, m, _ in per)/len(per)*100:>10.1f} {inm*100:>7.0f}% | "
              f"{' '.join(f'{r*100:+5.1f}' for r, _, _ in per)}")
        if label == "adaptive both-side":
            a_oos, a_per, a_inm = o, per, inm
    print("-" * 82)
    picks = "; ".join(f"z{p['z_in']}/stop{p['stop']}/dt{p['dtrend']}" for _, _, p in a_per)
    print(f"\nadaptive(both) picked per fold: {picks}")
    verdict = ("ADDS EDGE — worth building" if (a_oos > b_oos + 0.03 and
               sum(m for _, m, _ in a_per) >= sum(m for _, m, _ in b_per) - 0.02)
               else "does NOT beat trend-only OOS — do not build (idle-in-chop is the honest cost)")
    print(f"VERDICT: {verdict}. adaptive OOS {a_oos*100:+.1f}% vs incumbent {b_oos*100:+.1f}%; "
          f"the range mode lifted time-in-market {b_inm*100:.0f}%->{a_inm*100:.0f}% — the question "
          f"is whether that extra activity was PROFIT or just churn+risk.")


if __name__ == "__main__":
    main()
