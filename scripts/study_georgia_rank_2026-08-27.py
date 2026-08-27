#!/usr/bin/env python3
"""STUDY: 🔮 georgia — THE ENTRY-RANK AXIS, on an UNCENSORED population.
[2026-08-27, Eamon: "Raise the cap, adjust axis to meet where's only left to
look in terms of optimising her."]

WHY THIS IS THE LAST AXIS. Diversification is unavailable `(uu)` (57 of 60 live
closes are crypto; n_eff ~ 1.0 is structural). Exits are refused `(uw)`: 48
configurations over her OWN 212 entries, ZERO with a positive mean, ZERO with
both halves positive. Entry SUPPLY was worked 22-Aug (40.9 signals/day against
4.53 opens). What is left is entry SELECTION — WHICH of the available signals
she takes — and the within-hour rank is the knob that decides it.

**THE MEASUREMENT PROBLEM THAT MAKES THIS WORTH RUNNING: the cap censors the
very data needed to judge the cap.** `MAX_ENTRIES_PER_HOUR = 3` means her
ledger holds n=3 at rank 3 and NOTHING above it, so "is the marginal entry any
good?" cannot be answered from the record — the record is the thing the cap
truncated. Two prior readings disagree about the direction, which is exactly
what a censored sample produces: 22-Aug measured rank2 (+0.656%) > rank1
(+0.023%) and RAISED the cap 2 -> 3; `(uv)` measured rank1 −0.443%, rank2
+0.828%, rank3 **−7.752% on n=3**.

So this grades rank on the REPLAY population, which has no throttle and no
slot cap — ~1,800 entries across all ranks instead of 3 at the margin.

DATA + FIDELITY are `(uw)`'s, unchanged and already calibrated to −0.079pp on
her own entries: her real ATR-ratchet trail `min(mult x ATR14/px, 5%)`, the
bot's own within-bar check order, close-only triggers (the bot polls a MARK),
the `range_top` veto on `trend_breakout`, `live_vol` on the signal exit, and
the live `CandleCache`'s own 300-bar window. Rank is assigned the way
`Book.throttle_ok` assigns it: PER BOOK (not per coin), 1-based, within the
UTC clock hour.

===========================================================================
WHAT IS REPORTED
  1. Dose-response by rank: n, mean %/trade, cluster-t, both halves.
  2. Book-at-cap-K for K in 1..8 and uncapped — the number that actually
     decides a cap, because a cap is not a claim about rank K, it is a claim
     about the BOOK that keeps ranks 1..K.
  3. DAYS-TO-GATE at each cap. This is the point of the whole exercise and it
     is why "more trades" is not automatically wrong here: her binding go-live
     bar is `t >= 2.0`, and `t` grows with sqrt(n). A cap that lowers the mean
     slightly while raising the rate can still reach the gate SOONER —
     `n_req = n*(2/t)^2`, days = n_req / rate. Rates are scaled to her OWN
     observed closes/day so the replay's uncapped throughput cannot flatter it.

VERDICT, PRE-DECLARED. Recommend raising the cap to K only if ALL of:
    (a) book mean at cap K   > 0
    (b) BOTH chronological halves positive at cap K
    (c) days-to-gate at K    < days-to-gate at the shipped cap 3
    (d) rank K itself has n >= 30 — no cap is set on a handful of trades,
        which is the whole defect this study exists to repair.
Otherwise REFUSE and print (a)-(d). A refusal is a first-class outcome.

Usage: .venv/bin/python3 scripts/study_georgia_rank_2026-08-27.py
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
SHIPPED_ROI = [(0, 0.018), (180, 0.012), (360, 0.008), (720, 0.005)]
STOPLOSS = -0.05
BAR_MIN = 15
HOLD = 96
SHIPPED_CAP = 3
SHIPPED_MULT = {"trend_breakout": 3.5, "bounce_pullback": 3.5, "range_on": 2.5}
MIN_RANK_N = 30
DAYS = 90


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


def iid_t(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) or 1e-12
    return m / (sd / math.sqrt(n))


def halves(xs):
    if len(xs) < 4:
        return None, None
    m = len(xs) // 2
    return sum(xs[:m]) / m, sum(xs[m:]) / (len(xs) - m)


def roi_thr(age):
    t = SHIPPED_ROI[0][1]
    for a, v in SHIPPED_ROI:
        if age >= a:
            t = v
    return t


def walk(bars, atr, zones, e, mult, sleeve):
    entry = bars[e][1]
    stop_px = 0.0
    for k in range(e, min(e + HOLD, len(bars))):
        _t, _o, _hi, _lo, c, v = bars[k]
        age = (k - e) * BAR_MIN
        profit = c / entry - 1.0
        a = atr[k]
        if a and c:
            stop_px = max(stop_px, c * (1.0 - min(mult * a / c, abs(STOPLOSS))))
        if stop_px and c <= stop_px:
            return profit * 100.0, "trail"
        if profit <= STOPLOSS:
            return profit * 100.0, "stop"
        if profit >= roi_thr(age):
            return profit * 100.0, "roi"
        if k > e and v > 0 and sleeve != "trend_breakout":
            z = zones.get(k)
            if z is not None and c >= z:
                return profit * 100.0, "range_top"
    if e + HOLD >= len(bars):
        return None
    return (bars[e + HOLD][4] / entry - 1.0) * 100.0, "max_hold"


def main():
    S = [x for x in fb.STRATEGIES if x.bot == "freqtrade-georgia"][0]
    MIN, SPAN = S.min_bars, fb.CandleCache.SPAN_BARS["15m"]
    import bisect

    btc = [tuple(r) for r in json.load(open(os.path.join(CACHE, "c4h_BTC.json")))]
    c4 = [x[4] for x in btc]
    e50, e200 = fb.ema_series(c4, 50), fb.ema_series(c4, 200)
    reg = {btc[i][0]: bool(e50[i] and e200[i] and e50[i] > e200[i])
           for i in range(len(btc))}
    rts = sorted(reg)

    def regime_at(ts):
        i = bisect.bisect_right(rts, ts - 14400) - 1
        return reg[rts[i]] if i >= 0 else False

    ents = []
    nsym = 0
    for f in sorted(os.listdir(CACHE)):
        if not f.startswith("c15m_"):
            continue
        sym = f[5:-5]
        b = [tuple(r) for r in json.load(open(os.path.join(CACHE, f)))]
        if len(b) < 400:
            continue
        nsym += 1
        h = [x[2] for x in b]
        lo = [x[3] for x in b]
        c = [x[4] for x in b]
        v = [x[5] for x in b]
        atr = fb.atr_series(h, lo, c, 14)
        zones, prev = {}, None
        for i in range(MIN, len(b) - HOLD - 2):
            a = max(0, i + 1 - SPAN)
            sig = S.signals({"c": c[a:i + 1], "h": h[a:i + 1],
                             "l": lo[a:i + 1], "v": v[a:i + 1]},
                            {"btc_regime_up": regime_at(b[i][0])})
            rh = fb.roll_max(h[a:i + 1], 14, i - a - 1)
            rl = fb.roll_min(lo[a:i + 1], 14, i - a - 1)
            if rh is not None and rl is not None:
                zones[i] = rl + 0.78 * max(rh - rl, 1e-9)
            tag = (sig or {}).get("enter")
            if tag and tag != prev:
                ents.append((b[i + 1][0], sym, i, tag, b, atr, zones))
            prev = tag
    print(f"tape: {nsym} symbols · {DAYS}d · uncensored entries: {len(ents)}")

    ents.sort(key=lambda x: x[0])
    rows, bucket, n_in = [], None, 0
    for ts, sym, i, tag, b, atr, zones in ents:
        hb = int(ts // 3600)
        if hb != bucket:
            bucket, n_in = hb, 0
        n_in += 1
        r = walk(b, atr, zones, i + 1, SHIPPED_MULT.get(tag, 2.5), tag)
        if r:
            rows.append((n_in, r[0], (sym, ts // 86400), ts, tag, r[1]))
    print(f"walked: {len(rows)}\n")

    print("DOSE-RESPONSE BY WITHIN-HOUR RANK (uncensored):")
    print(f"  {'rank':>4} {'n':>5} {'mean%':>8} {'t_cl':>7} {'halves':>17}")
    maxr = max(r[0] for r in rows)
    for k in range(1, min(maxr, 9) + 1):
        v = [r for r in rows if r[0] == k]
        if len(v) < 5:
            continue
        xs = [r[1] for r in v]
        h1, h2 = halves(xs)
        print(f"  {k:>4} {len(xs):5d} {sum(xs)/len(xs):+8.3f} "
              f"{cluster_t(xs,[r[2] for r in v]):+7.2f} "
              f"{h1:+8.3f}/{h2:+8.3f}")

    # her OWN observed rate, so the replay's throughput cannot flatter a cap
    import psycopg2
    cur = psycopg2.connect(open(os.environ["GEO_DBURL"]).read().strip()).cursor()
    cur.execute("""SELECT count(*), min(opened_at::timestamptz),
                          max(opened_at::timestamptz) FROM paper_trades
                   WHERE bot='freqtrade-georgia-lshadow' AND pnl_pct IS NOT NULL""")
    n_real, t0, t1 = cur.fetchone()
    real_rate = n_real / max(1e-9, (t1 - t0).total_seconds() / 86400)
    cap3_n = len([r for r in rows if r[0] <= SHIPPED_CAP])
    print(f"\nher OWN observed rate: {real_rate:.2f} closes/day "
          f"(n={n_real}); replay at cap {SHIPPED_CAP}: {cap3_n} over {DAYS}d")
    scale = real_rate / (cap3_n / DAYS)
    print(f"rate scale factor (replay -> her book): {scale:.3f}")

    print("\nBOOK AT CAP K  (the number that decides a cap):")
    print(f"  {'cap':>4} {'n':>5} {'mean%':>8} {'t_cl':>7} {'iid_t':>7} "
          f"{'halves':>17} {'/day':>6} {'days_to_t2':>11}")
    out = {}
    for K in list(range(1, min(maxr, 8) + 1)) + [999]:
        v = [r for r in rows if r[0] <= K]
        if len(v) < 30:
            continue
        xs = [r[1] for r in v]
        m = sum(xs) / len(xs)
        ti = iid_t(xs)
        h1, h2 = halves(xs)
        rate = (len(v) / DAYS) * scale
        if m > 0 and ti and ti == ti and ti > 0:
            n_req = len(xs) * (2.0 / ti) ** 2
            days = n_req / max(1e-9, rate)
        else:
            days = float("inf")
        out[K] = (m, cluster_t(xs, [r[2] for r in v]), ti, h1, h2, rate, days,
                  len(xs))
        lab = "none" if K == 999 else str(K)
        print(f"  {lab:>4} {len(xs):5d} {m:+8.3f} "
              f"{out[K][1]:+7.2f} {ti:+7.2f} {h1:+8.3f}/{h2:+8.3f} "
              f"{rate:6.2f} {days:11.0f}")

    print("\nVERDICT (a) mean>0 (b) both halves + (c) days_to_gate < cap-3's "
          f"(d) rank K has n>={MIN_RANK_N}:")
    base = out.get(SHIPPED_CAP)
    if not base:
        print("  UNGRADED — the shipped cap produced too few closes")
        return 0
    print(f"  shipped cap {SHIPPED_CAP}: mean {base[0]:+.3f}%  "
          f"halves {base[3]:+.3f}/{base[4]:+.3f}  days_to_gate {base[6]:.0f}")
    adm = []
    for K, r in sorted(out.items()):
        if K <= SHIPPED_CAP:
            continue
        rk = [x for x in rows if x[0] == K] if K != 999 else rows
        a, b_, c_ = r[0] > 0, (r[3] > 0 and r[4] > 0), r[6] < base[6]
        d = len(rk) >= MIN_RANK_N or K == 999
        lab = "none" if K == 999 else str(K)
        ok = a and b_ and c_ and d
        if ok:
            adm.append((K, r))
        print(f"  cap {lab:>4}: {'ADMIT' if ok else 'REFUSE'} — "
              f"(a) mean {r[0]:+.3f} {'OK' if a else 'NO'} · "
              f"(b) {r[3]:+.3f}/{r[4]:+.3f} {'OK' if b_ else 'NO'} · "
              f"(c) {r[6]:.0f}d vs {base[6]:.0f}d {'OK' if c_ else 'NO'} · "
              f"(d) rank n={len(rk)} {'OK' if d else 'NO'}")
    if not adm:
        print("\n  => RAISING THE CAP IS REFUSED on this measurement. "
              "The shipped cap stands.")
    else:
        best = min(adm, key=lambda kv: kv[1][6])
        lab = "none" if best[0] == 999 else best[0]
        print(f"\n  => RAISE THE CAP TO {lab}: mean {best[1][0]:+.3f}%/trade, "
              f"halves {best[1][3]:+.3f}/{best[1][4]:+.3f}, "
              f"days-to-gate {best[1][6]:.0f} vs {base[6]:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
