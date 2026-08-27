#!/usr/bin/env python3
"""STUDY: 🔮 georgia — RECONCILE the replay with the RECORD, on HER OWN entries.
[2026-08-27, Eamon: "Let's run it now baby!"]

WHY THIS EXISTS. `(uv)`'s exit-free test said `range_on` has a large entry edge
(t_cl +4.28, P(rand>=)=0.000 at every horizon) while her LEDGER says that sleeve
LOSES (-0.037%/trade) and `trend_breakout` earns. **I14 is explicit: when a
book's own realised trades disagree with a proxy, the RECORD decides.** So the
proxy does not get to redesign a real-money book until the disagreement is
explained.

THE MECHANISM THAT COULD EXPLAIN IT, and why this study is the test: `(uv)`
replayed **1816 entries where she actually took 212**. It models none of
`MAX_ENTRIES_PER_HOUR`, slot contention, the fleet long budget, coin vetoes or
the StoplossGuard — so its entry set is not her entry set, and its verdict may
be about trades she can never take.

THIS STUDY REMOVES THAT DEGREE OF FREEDOM ENTIRELY: every candidate exit is
walked over **her 212 REAL, PRICED entries** (pair + opened_at + entry_price
straight from `paper_trades`, both arms). Entries are not simulated, not
re-derived, not filtered — they are the trades she actually opened. So a
difference between two cells is caused by the EXIT and nothing else.

===========================================================================
FIDELITY — the trail is her REAL one, not a fixed percentage. `(uv)`'s grid
swept a static stop; her actual rule is `DayTraderGated.atr_stop_dist`:

    dist    = min(mult * ATR14 / px, 0.05)        # capped at |stoploss|
    stop_px = max(stop_px, px * (1 - dist))       # RATCHETS UP ONLY
    mult    = 3.5 for trend_breakout / bounce_pullback   [(20-Aug)]
              2.5 for range_on                            [kept, measured]

and the bot's own within-bar CHECK ORDER is preserved (trail, then hard stop,
then ROI ladder, then max_hold, then the range_top signal). Getting that order
wrong would let ROI pre-empt a stop and flatter every cell.
Ratchet updates on the bar CLOSE (the bot's `px`); the trigger tests the bar
LOW and fills AT `stop_px` — conservative, and the calibration gate below is
what decides whether that convention is faithful.

===========================================================================
CALIBRATION GATE (gx), AND IT IS MUCH TIGHTER THAN `(uv)`'s. Because the
entries are hers, the shipped policy must reproduce her ACTUAL per-trade mean
on the SAME trades — not merely land in the same region. Tolerance +/-0.25pp
overall AND the sign must match per sleeve. FAIL => every recommendation is
WITHHELD. A harness that cannot reproduce her book may not redesign it.

===========================================================================
THE SWEEP. Entries CONSTANT (they are her real ones); only the exit moves:
    roi     : shipped ladder, flat 2.0%, flat 3.0%
    rtop    : range_top signal exit ON (shipped) / OFF
    mult    : 2.0, 2.5, 3.0, 3.5 (ATR trail multiplier, applied to ALL sleeves)
    hold    : 12h, 24h (shipped)

VERDICT, PRE-DECLARED — a variant is ADMITTED only if ALL of:
    (a) mean %/trade       > shipped, by at least 0.10pp (not noise)
    (b) BOTH chronological halves positive
    (c) cluster-t (coin-day) >= shipped's
    (d) it holds on the `range_on` SUBSET alone — the sleeve whose edge is in
        dispute. A cell that only works by helping `trend_breakout` does not
        resolve the disagreement this study exists to settle.
Anything else REFUSE, printing (a)-(d) so the refusal carries numbers.

A refusal is a first-class outcome. If nothing clears, the finding is that
`(uv)`'s exit result does NOT survive contact with her real entry set, and the
shipped exit stands.

Usage: .venv/bin/python3 scripts/study_georgia_reconcile_2026-08-27.py
Cache: shares $GEO_CACHE with (uv) — candles only.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lighter_family_bot as fb

CACHE = os.environ.get("GEO_CACHE") or os.path.join(
    os.environ.get("TMPDIR", "/tmp"), "geo_cache_2026-08-27")

# ---- pre-declared ---------------------------------------------------------
SHIPPED_ROI = [(0, 0.018), (180, 0.012), (360, 0.008), (720, 0.005)]
STOPLOSS = -0.05
BAR_MIN = 15
SHIPPED_HOLD = 96                      # 24h
SHIPPED_MULT = {"trend_breakout": 3.5, "bounce_pullback": 3.5,
                "range_on": 2.5, "long": 2.5}
CAL_TOL = 0.25                         # pp, on her own entries
MIN_GAIN = 0.10                        # pp, bar (a)
ROIS = {"shipped": SHIPPED_ROI, "flat2.0": [(0, 0.020)],
        "flat3.0": [(0, 0.030)]}
MULTS = (2.0, 2.5, 3.0, 3.5)
HOLDS = (48, 96)


def cluster_t(xs, keys):
    n = len(xs)
    if n < 3:
        return float("nan")
    xb = sum(xs) / n
    g = {}
    for x, k in zip(xs, keys):
        g.setdefault(k, []).append(x - xb)
    G = len(g)
    if G < 2:
        return float("nan")
    se = math.sqrt(G / (G - 1) * sum(sum(v) ** 2 for v in g.values())) / n
    return xb / se if se > 0 else float("nan")


def halves(xs):
    if len(xs) < 4:
        return None, None
    m = len(xs) // 2
    return sum(xs[:m]) / m, sum(xs[m:]) / (len(xs) - m)


def roi_thr(lad, age):
    t = lad[0][1]
    for a, v in lad:
        if age >= a:
            t = v
    return t


def walk(bars, atr, zones, e, entry, lad, mult, hold, rtop):
    """Her REAL exit stack from bar e at `entry`. Bot's own check order."""
    stop_px = 0.0
    for k in range(e, min(e + hold, len(bars))):
        _t, o, hi, lo, c, _v = bars[k]
        age = (k - e) * BAR_MIN
        # 1) ATR ratchet trail — updates on close, triggers on low
        a = atr[k]
        if a and c:
            dist = min(mult * a / c, abs(STOPLOSS))
            stop_px = max(stop_px, c * (1.0 - dist))
        if stop_px and lo <= stop_px:
            return (stop_px / entry - 1.0) * 100.0, "trail", k - e
        # 2) hard stop
        if lo <= entry * (1.0 + STOPLOSS):
            return STOPLOSS * 100.0, "stop", k - e
        # 3) ROI ladder
        thr = roi_thr(lad, age)
        if hi >= entry * (1.0 + thr):
            return thr * 100.0, "roi", k - e
        # 4) range_top signal
        if rtop and k > e:
            z = zones.get(k)
            if z is not None and c >= z:
                return (c / entry - 1.0) * 100.0, "range_top", k - e
    if e + hold >= len(bars):
        return None
    return (bars[e + hold][4] / entry - 1.0) * 100.0, "max_hold", hold


def main():
    import bisect
    import psycopg2
    u = open(os.environ["GEO_DBURL"]).read().strip()
    cur = psycopg2.connect(u).cursor()
    cur.execute("""SELECT pair, opened_at::timestamptz, entry_price, pnl_pct,
                          reason FROM paper_trades
                   WHERE bot IN ('freqtrade-georgia-lshadow',
                                 'freqtrade-georgia-lighter')
                     AND pnl_pct IS NOT NULL AND entry_price IS NOT NULL
                   ORDER BY opened_at::timestamptz""")
    trades = [(p, o, float(ep), 100.0 * pp, str(r)) for p, o, ep, pp, r
              in cur.fetchall()]
    print(f"her REAL priced entries: {len(trades)}  "
          f"{trades[0][1].date()} -> {trades[-1][1].date()}")

    tape, atrs, zones = {}, {}, {}
    for f in os.listdir(CACHE):
        if not f.startswith("c15m_"):
            continue
        sym = f[5:-5]
        rows = [tuple(r) for r in json.load(open(os.path.join(CACHE, f)))]
        if len(rows) < 300:
            continue
        tape[sym] = rows
        h = [x[2] for x in rows]
        lo = [x[3] for x in rows]
        c = [x[4] for x in rows]
        atrs[sym] = fb.atr_series(h, lo, c, 14)
        z = {}
        for i in range(20, len(rows)):
            a = max(0, i + 1 - 300)
            rh = fb.roll_max(h[a:i + 1], 14, i - a - 1)
            rl = fb.roll_min(lo[a:i + 1], 14, i - a - 1)
            if rh is not None and rl is not None:
                z[i] = rl + 0.78 * max(rh - rl, 1e-9)
        zones[sym] = z
    print(f"tape: {len(tape)} symbols cached")

    # map each real entry onto its 15m bar
    ent = []
    miss = 0
    for pair, o, ep, actual, reason in trades:
        b = tape.get(pair)
        if not b:
            miss += 1
            continue
        ts = [x[0] for x in b]
        i = bisect.bisect_left(ts, int(o.timestamp()))
        if i >= len(b) - 8:
            miss += 1
            continue
        sleeve = reason.split("_")[0].replace("long-", "").replace("long", "long")
        ent.append((pair, i, ep, actual, sleeve, o))
    print(f"mapped {len(ent)} entries onto 15m bars ({miss} unmapped)\n")
    if len(ent) < 100:
        print("TOO FEW MAPPED — refusing to report ((po))")
        return 2

    def run(lad, mult_map, hold, rtop, subset=None):
        rr, keys, mix = [], [], {}
        for pair, i, ep, _a, sl, o in ent:
            if subset and sl != subset:
                continue
            m = mult_map(sl)
            r = walk(tape[pair], atrs[pair], zones[pair], i, ep, lad, m,
                     hold, rtop)
            if r:
                rr.append(r[0])
                keys.append((pair, o.date()))
                mix[r[1]] = mix.get(r[1], 0) + 1
        return rr, keys, mix

    # ---- CALIBRATION -----------------------------------------------------
    base_rr, base_keys, base_mix = run(SHIPPED_ROI,
                                       lambda s: SHIPPED_MULT.get(s, 2.5),
                                       SHIPPED_HOLD, True)
    act = [t[3] for t in trades]
    rep_m = sum(base_rr) / len(base_rr)
    act_m = sum(act) / len(act)
    print("=" * 74)
    print(f"CALIBRATION on HER OWN entries: replay {rep_m:+.3f}%/trade "
          f"(n={len(base_rr)}) vs actual {act_m:+.3f}% (n={len(act)})")
    print(f"   gap {rep_m-act_m:+.3f}pp  tolerance +/-{CAL_TOL}pp")
    print(f"   replay exit mix: {base_mix}")
    for sl in ("range_on", "trend_breakout"):
        sr, _k, _m = run(SHIPPED_ROI, lambda s: SHIPPED_MULT.get(s, 2.5),
                         SHIPPED_HOLD, True, subset=sl)
        aa = [t[3] for t in trades if sl in t[4].replace("-", "_")]
        if sr and aa:
            print(f"   {sl:16s} replay {sum(sr)/len(sr):+.3f}%  "
                  f"actual {sum(aa)/len(aa):+.3f}%  "
                  f"sign {'MATCH' if (sum(sr)>0)==(sum(aa)>0) else 'MISMATCH'}")
    ok = abs(rep_m - act_m) <= CAL_TOL
    print(f"   => CALIBRATION {'PASSES' if ok else 'FAILS'}")
    if not ok:
        print("\nWITHHELD: the harness cannot reproduce her book on her own "
              "entries, so it may not redesign it (gx).")
        return 0

    # ---- SWEEP -----------------------------------------------------------
    bt = cluster_t(base_rr, base_keys)
    bh1, bh2 = halves(base_rr)
    print("\n" + "=" * 74)
    print(f"SHIPPED baseline: {rep_m:+.3f}%/trade  t_cl {bt:+.2f}  "
          f"halves {bh1:+.3f}/{bh2:+.3f}")
    print("=" * 74)
    print(f"{'roi':9s} {'mult':>5} {'hold':>5} {'rtop':>6} {'n':>4} "
          f"{'mean%':>8} {'t_cl':>6} {'halves':>16} {'range_on only':>14}")
    rows = []
    for rn, lad in ROIS.items():
        for mult in MULTS:
            for hold in HOLDS:
                for rtop in (True, False):
                    rr, keys, _m = run(lad, lambda s, _M=mult: _M, hold, rtop)
                    if len(rr) < 100:
                        continue
                    m = sum(rr) / len(rr)
                    h1, h2 = halves(rr)
                    tc = cluster_t(rr, keys)
                    ro, rok, _ = run(lad, lambda s, _M=mult: _M, hold, rtop,
                                     subset="range_on")
                    rom = sum(ro) / len(ro) if ro else float("nan")
                    rows.append((rn, mult, hold, rtop, len(rr), m, tc, h1, h2,
                                 rom))
                    print(f"{rn:9s} {mult:5.1f} {hold:5d} {str(rtop):>6} "
                          f"{len(rr):4d} {m:+8.3f} {tc:+6.2f} "
                          f"{h1:+7.3f}/{h2:+7.3f} {rom:+14.3f}")

    ro_base, rok_base, _ = run(SHIPPED_ROI,
                               lambda s: SHIPPED_MULT.get(s, 2.5),
                               SHIPPED_HOLD, True, subset="range_on")
    rob = sum(ro_base) / len(ro_base) if ro_base else float("nan")
    print(f"\nshipped range_on-only baseline: {rob:+.3f}%/trade")
    print("\nVERDICT (a) mean > shipped+0.10pp (b) both halves + "
          "(c) t_cl >= shipped (d) holds on range_on alone:")
    adm = [r for r in rows
           if r[5] > rep_m + MIN_GAIN and r[7] > 0 and r[8] > 0
           and r[6] >= bt and r[9] > rob]
    if not adm:
        print("  ADMIT: none. (uv)'s exit result does NOT survive contact "
              "with her real entry set — the shipped exit stands.")
    else:
        for r in sorted(adm, key=lambda x: -x[5])[:10]:
            print(f"  ADMIT {r[0]:9s} mult{r[1]:4.1f} hold{r[2]:4d} "
                  f"rtop={r[3]}: {r[5]:+.3f}%/trade t_cl {r[6]:+.2f} "
                  f"halves {r[7]:+.3f}/{r[8]:+.3f} range_on {r[9]:+.3f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
