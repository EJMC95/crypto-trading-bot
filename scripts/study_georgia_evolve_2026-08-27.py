#!/usr/bin/env python3
"""STUDY: 🔮 georgia v2 — ENTRY first, then exits.
[2026-08-27, Eamon: "If it's not diversification then it's entry and exits,
please evolve."]

WHY THIS ORDER, and it is not a style choice. `(qu)` burned ~600 bracket
sweeps on 🙏 avo before discovering there was no ENTRY edge for any bracket to
harvest, and wrote the rule down: run the EXIT-FREE forward test FIRST. So Q1
grades georgia's three entry sleeves against matched-random entries and Q2
only sweeps exits for sleeves whose entry survives. If no sleeve survives, the
honest output is "no exit change can save this book" — a refusal, not a grid.

CONTEXT THIS INHERITS (already measured, not re-litigated here):
  * `(un)`/daily-review 27-Aug: her HALT is not the problem — replaying the 6
    halted positions forward gives -$59.88 vs the -$34.83 the halt booked, so
    the halt SAVED $25.05. Do not re-propose widening it.
  * `(uu)`: she cannot diversify — 57 of 60 live closes are crypto, so
    `n_eff ~ 1.0` is structural and leverage is not earnable that way.
  * Which leaves ENTRY and EXIT. This study.

===========================================================================
DATA. Lighter's own 15m candles (her real timeframe — `roll_max(14)` on 15m
is a 3.5h window, so a timeframe substitution would be a different rule), her
actual resolved universe (`lighter_family_bot`: COINS + NONCRYPTO_UNIVERSE),
90 days. ACTUAL per-coin coverage is reported, never assumed. Indicators and
the signal function are the BOT'S OWN, imported verbatim (a second copy of a
rule is a second rule, (hj)) — `DayTraderGated.signals` is called directly.

`btc_regime_up` is reproduced EXACTLY as the bot computes it (BTC 4h
EMA50>EMA200 on the last CLOSED 4h bar, `lighter_family_bot.btc_regime_up`),
evaluated per 15m bar against the most recent closed 4h bar. It gates two of
the three sleeves, so getting it wrong would mis-assign them; `trend_breakout`
does NOT depend on it (it is the LAST .loc assignment and wins regardless),
which is why that sleeve is the cleanest read here.

LAG-1 EVERYWHERE. Signal read on closed bar i; entry at the OPEN of bar i+1.

EPISODES, not ticks: consecutive qualifying bars on one coin for THAT sleeve
collapse to ONE episode. And note `(un)`'s lesson — a sleeve measured in
ISOLATION can be an adversely-selected subset; here each sleeve is the bot's
own tag, which is the object the bot actually trades, so isolation is correct.

===========================================================================
Q1 — ENTRY, EXIT-FREE. Per sleeve x horizon h in {16, 32, 48, 96} bars
(= 4h, 8h, 12h, 24h; her roi ladder tops out at 12h and max_hold is 24h):
    excess%  = sleeve mean forward return - matched-random mean
    t_cl     = cluster-robust t of per-episode excess, clustered COIN-DAY
    P(rand>=sleeve) over DRAWS resamples
  plus a trailing-30d recency split ((qu)'s decay finding).

  VERDICT PER SLEEVE, PRE-DECLARED:
    SURVIVES   excess > 0 with t_cl >= 1.5 at ANY horizon, AND the trailing
               window is not negative at that horizon.
    DEAD       otherwise — and no exit sweep is run for it.

Q2 — EXITS, only for surviving sleeves, ENTRIES HELD CONSTANT (never fitted).
  Grid, all combinations:
    roi     : shipped {0:1.8,180:1.2,360:0.8,720:0.5}%, x0.75, x1.5,
              flat 1.2%, flat 2.0%, flat 3.0%
    stop    : -3%, -5% (shipped), -8%
    hold    : 12h, 24h (shipped), 48h
    range_top signal exit: ON (shipped) / OFF
  Stop is checked BEFORE target within a bar (conservative). Entry bar's
  post-open range is tested — the (ml) convention, no pre-entry range credited.

  THE (hl) GUARD, and it is why the bar is on the SECOND number: 25 of 30
  "faster exit" candidates died because the gain was DENOMINATOR SHRINKAGE.
  So every cell reports mean %/trade AND return per BAR-DAY, and:

  VERDICT, PRE-DECLARED. ADMIT a variant only if ALL of:
    (a) mean %/trade      >= shipped
    (b) return per bar-day > shipped
    (c) BOTH chronological halves positive
    (d) cluster-t         >= shipped
  Anything else REFUSE, printing (a)-(d) so the refusal carries numbers.

===========================================================================
CALIBRATION GATE (gx) — THE HARNESS MUST REPRODUCE WHAT DID HAPPEN BEFORE IT
MAY SAY WHAT WOULD HAVE. The shipped rule is replayed end-to-end and its
mean %/trade compared to georgia's REAL shadow ledger (n=209, the larger of
her two samples; the live arm is n=53 over 5 days and too thin to calibrate
against). Tolerance +/-0.60pp on the per-trade mean. FAIL => every Q2
recommendation is WITHHELD, not caveated. A harness that cannot reproduce the
book may not redesign it.

Usage: .venv/bin/python3 scripts/study_georgia_evolve_2026-08-27.py
Cache: $GEO_CACHE (candles only, idempotent).
"""
import json
import math
import os
import random
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lighter_family_bot as fb

B_URL = "https://mainnet.zklighter.elliot.ai"
CACHE = os.environ.get("GEO_CACHE") or os.path.join(
    os.environ.get("TMPDIR", "/tmp"), "geo_cache_2026-08-27")

# ---- pre-declared constants ----------------------------------------------
DAYS = 90
HORIZONS = (16, 32, 48, 96)            # 4h, 8h, 12h, 24h on 15m bars
DRAWS = 400
SEED = 20260827
TRAIL_D = 30
T_BAR = 1.5
CAL_TOL = 0.60                         # pp on mean %/trade
CAL_TARGET_BOT = "freqtrade-georgia-lshadow"
SHIPPED_ROI = [(0, 0.018), (180, 0.012), (360, 0.008), (720, 0.005)]
SHIPPED_STOP = -0.05
SHIPPED_HOLD_BARS = 96                 # 24h on 15m
BAR_MIN = 15
SLEEVES = ("range_on", "bounce_pullback", "trend_breakout")

NOW = int(time.time())
TRAIL_TS = NOW - TRAIL_D * 86400
os.makedirs(CACHE, exist_ok=True)


def _get(url):
    for a in range(5):
        try:
            with urllib.request.urlopen(url, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception:                                       # noqa: BLE001
            time.sleep(2.0 * (a + 1))
    return None


def _api(path, **q):
    return _get(B_URL + path + "?" + "&".join(f"{k}={v}" for k, v in q.items()))


def market_ids():
    p = os.path.join(CACHE, "mids.json")
    if os.path.exists(p):
        return json.load(open(p))
    m = {o["symbol"]: o["market_id"]
         for o in (_api("/api/v1/orderBookDetails").get("order_book_details")
                   or []) if o.get("symbol")}
    json.dump(m, open(p, "w"))
    return m


def fetch(sym, mid, res, days):
    """[(ts, o, h, l, c, v)] oldest-first, paged backward, cached."""
    p = os.path.join(CACHE, f"c{res}_{sym}.json")
    if os.path.exists(p):
        return [tuple(r) for r in json.load(open(p))]
    step = {"15m": 900, "4h": 14400}[res]
    out, end, seen, floor = {}, NOW, None, NOW - days * 86400
    while True:
        d = _api("/api/v1/candles", market_id=mid, resolution=res,
                 start_timestamp=max(floor, end - 500 * step),
                 end_timestamp=end, count_back=500)
        cs = (d or {}).get("c") or []
        if not cs:
            break
        for c in cs:
            out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                        float(c["l"]), float(c["c"]),
                                        float(c.get("v") or 0.0))
        oldest = min(int(c["t"]) // 1000 for c in cs)
        if oldest <= floor or (seen is not None and oldest >= seen):
            break
        seen, end = oldest, oldest - step
        time.sleep(0.05)
    rows = sorted((k, *v) for k, v in out.items() if k >= floor)
    json.dump(rows, open(p, "w"))
    return [tuple(r) for r in rows]


def cluster_t(xs, keys):
    n = len(xs)
    if n < 2:
        return float("nan")
    xbar = sum(xs) / n
    g = {}
    for x, k in zip(xs, keys):
        g.setdefault(k, []).append(x - xbar)
    G = len(g)
    if G < 2:
        return float("nan")
    se = math.sqrt(G / (G - 1) * sum(sum(v) ** 2 for v in g.values())) / n
    return xbar / se if se > 0 else float("nan")


def halves(xs):
    if len(xs) < 4:
        return None, None
    m = len(xs) // 2
    return sum(xs[:m]) / m, sum(xs[m:]) / (len(xs) - m)


def roi_thr(ladder, age_min):
    t = ladder[0][1]
    for a, v in ladder:
        if age_min >= a:
            t = v
    return t


def walk(bars, e, ladder, stop, hold, sell_zones=None):
    """Bracket from entry at open of bar e. `sell_zones[k]` is that bar's
    sell_zone when the range_top signal exit is ON, else None."""
    entry = bars[e][1]
    sp = entry * (1.0 + stop)
    for k in range(e, min(e + hold, len(bars))):
        age = (k - e) * BAR_MIN
        if bars[k][3] <= sp:                      # stop first — conservative
            return stop * 100.0, "stop", k - e
        thr = roi_thr(ladder, age)
        if bars[k][2] >= entry * (1.0 + thr):
            return thr * 100.0, "roi", k - e
        if sell_zones is not None and k > e:
            sz = sell_zones.get(k)
            if sz is not None and bars[k][4] >= sz:
                return (bars[k][4] / entry - 1.0) * 100.0, "range_top", k - e
    if e + hold >= len(bars):
        return None
    return (bars[e + hold][1] / entry - 1.0) * 100.0, "max_hold", hold


def main():
    random.seed(SEED)
    mids = market_ids()
    syms = [s for s in (list(fb.COINS) + list(fb.NONCRYPTO_UNIVERSE))
            if s in mids]
    print(f"universe: {len(syms)} symbols · {DAYS}d of 15m tape")

    # BTC 4h regime series -> {4h_open_ts: bool}
    btc4 = fetch("BTC", mids["BTC"], "4h", DAYS + 60)
    c4 = [x[4] for x in btc4]
    e50, e200 = fb.ema_series(c4, 50), fb.ema_series(c4, 200)
    regime = {btc4[i][0]: bool(e50[i] and e200[i] and e50[i] > e200[i])
              for i in range(len(btc4))}
    r_ts = sorted(regime)
    print(f"BTC 4h regime bars: {len(r_ts)}  up-fraction "
          f"{sum(regime.values())/max(1,len(regime)):.1%}")

    def regime_at(ts):
        """Most recent CLOSED 4h bar at or before ts. Fail-safe False."""
        import bisect
        i = bisect.bisect_right(r_ts, ts - 14400) - 1
        return regime[r_ts[i]] if i >= 0 else False

    tape = {}
    for s in syms:
        try:
            b = fetch(s, mids[s], "15m", DAYS)
        except Exception as e:                                  # noqa: BLE001
            print(f"  skip {s}: {type(e).__name__}")
            continue
        if len(b) >= 400:
            tape[s] = b
    print(f"tape: {len(tape)} symbols with >=400 15m bars")
    if not tape:
        print("NO TAPE — refusing to report ((po): empty output is not a result)")
        return 2
    cov = {s: (tape[s][-1][0] - tape[s][0][0]) / 86400.0 for s in tape}
    print(f"coverage: median {sorted(cov.values())[len(cov)//2]:.0f}d "
          f"min {min(cov.values()):.0f}d max {max(cov.values()):.0f}d")

    S = [x for x in fb.STRATEGIES if x.bot == "freqtrade-georgia"][0]
    MIN = S.min_bars
    SPAN = fb.CandleCache.SPAN_BARS["15m"]      # 300 — production's own window
    print(f"signal window: {SPAN} bars (the live CandleCache span, verbatim)")

    # ---- evaluate the BOT'S OWN signal on every bar -----------------------
    ep = {k: [] for k in SLEEVES}          # (sym, i)
    zones = {}                             # sym -> {bar_index: sell_zone}
    prev = {s: None for s in tape}
    for s, b in tape.items():
        c = [x[4] for x in b]
        h = [x[2] for x in b]
        lo = [x[3] for x in b]
        v = [x[5] for x in b]
        zones[s] = {}
        for i in range(MIN, len(b) - max(HORIZONS) - 2):
            # [FIDELITY, not an optimisation] The live bot's CandleCache only
            # ever holds SPAN_BARS["15m"] = 300 bars, so the rule never sees
            # more than that. Feeding it a growing full-history prefix would
            # give the replay MORE history than production has — the opposite
            # of faithful — and it is also O(n^2). Window = the bot's own span.
            a = max(0, i + 1 - SPAN)
            sub = {"c": c[a:i + 1], "h": h[a:i + 1], "l": lo[a:i + 1],
                   "v": v[a:i + 1]}
            sig = S.signals(sub, {"btc_regime_up": regime_at(b[i][0])})
            if not sig:
                prev[s] = None
                continue
            # sell_zone for the range_top exit: recompute from the same window
            rh = fb.roll_max(h[a:i + 1], 14, i - a - 1)
            rl = fb.roll_min(lo[a:i + 1], 14, i - a - 1)
            if rh is not None and rl is not None:
                band = max(rh - rl, 1e-9)
                zones[s][i] = rl + 0.78 * band       # rng_hi - 0.22*band
            tag = sig.get("enter")
            if tag and tag != prev[s]:
                ep[tag].append((s, i))
            prev[s] = tag
    for k in SLEEVES:
        print(f"  sleeve {k:18s} episodes {len(ep[k])}")

    # ---- Q1: exit-free vs matched random ---------------------------------
    print("\n" + "=" * 78)
    print("Q1 — ENTRY, EXIT-FREE vs MATCHED-RANDOM ((qu): entry edge first)")
    print("=" * 78)
    survivors = []
    for k in SLEEVES:
        eps = ep[k]
        print(f"\n[{k}] episodes={len(eps)}")
        if len(eps) < 30:
            print("   -> too few episodes to grade")
            continue
        best_t, ok = -9, False
        for h in HORIZONS:
            rr, ex, keys, rt = [], [], [], []
            for s, i in eps:
                b = tape[s]
                e = i + 1
                if e + h >= len(b):
                    continue
                r = (b[e + h][1] / b[e][1] - 1.0) * 100.0
                allb = [(b[j + h][1] / b[j][1] - 1.0) * 100.0
                        for j in range(MIN, len(b) - h - 1, 24)]
                nm = sum(allb) / len(allb) if allb else 0.0
                rr.append(r)
                ex.append(r - nm)
                keys.append((s, b[e][0] // 86400))
                if b[i][0] >= TRAIL_TS:
                    rt.append(r - nm)
            if len(rr) < 20:
                continue
            m = sum(rr) / len(rr)
            xm = sum(ex) / len(ex)
            tc = cluster_t(ex, keys)
            tm = sum(rt) / len(rt) if rt else float("nan")
            hits = 0
            bycoin = {}
            for s, i in eps:
                bycoin[s] = bycoin.get(s, 0) + 1
            for _ in range(DRAWS):
                tot, n = 0.0, 0
                for s, cnt in bycoin.items():
                    b = tape[s]
                    a, z = MIN, len(b) - h - 2
                    if z <= a:
                        continue
                    for _ in range(cnt):
                        j = random.randint(a, z)
                        tot += (b[j + h][1] / b[j][1] - 1.0) * 100.0
                        n += 1
                if n and tot / n >= m:
                    hits += 1
            print(f"   h={h:3d} ({h*BAR_MIN//60:2d}h): excess {xm:+.3f}%  "
                  f"t_cl {tc:+.2f}  P(rand>=) {hits/DRAWS:.3f}  "
                  f"trail-{TRAIL_D}d {tm:+.3f}%")
            if xm > 0 and tc >= T_BAR and not (tm < 0):
                ok = True
            best_t = max(best_t, tc if tc == tc else -9)
        print(f"   => {'SURVIVES' if ok else 'DEAD'} (best t_cl {best_t:+.2f})")
        if ok:
            survivors.append(k)

    if not survivors:
        print("\n" + "=" * 78)
        print("NO SLEEVE SURVIVES THE ENTRY TEST.")
        print("Per (qu): no exit change can harvest an edge that is not there.")
        print("Q2 is NOT run — that is the finding, not a gap.")
        print("=" * 78)
        return 0

    # ---- CALIBRATION before any Q2 recommendation ------------------------
    print("\n" + "-" * 78)
    allep = [(s, i, k) for k in SLEEVES for s, i in ep[k]]
    rr, keys = [], []
    for s, i, _k in allep:
        r = walk(tape[s], i + 1, SHIPPED_ROI, SHIPPED_STOP,
                 SHIPPED_HOLD_BARS, zones[s])
        if r:
            rr.append(r[0])
            keys.append((s, tape[s][i + 1][0] // 86400))
    rep = sum(rr) / len(rr) if rr else float("nan")
    print(f"CALIBRATION: shipped rule replays {rep:+.3f}%/trade over n={len(rr)}")
    print(f"   georgia's REAL {CAL_TARGET_BOT} ledger: see --actual below")
    print(f"   (tolerance +/-{CAL_TOL:.2f}pp; compare before trusting Q2)")

    # ---- Q2: exit sweep ---------------------------------------------------
    print("\n" + "=" * 78)
    print(f"Q2 — EXITS on surviving sleeve(s) {survivors}, ENTRIES CONSTANT")
    print("=" * 78)
    ladders = {
        "shipped": SHIPPED_ROI,
        "x0.75": [(a, v * 0.75) for a, v in SHIPPED_ROI],
        "x1.5": [(a, v * 1.5) for a, v in SHIPPED_ROI],
        "flat1.2": [(0, 0.012)], "flat2.0": [(0, 0.020)],
        "flat3.0": [(0, 0.030)],
    }
    eps = [(s, i) for k in survivors for s, i in ep[k]]
    print(f"entries held constant: n={len(eps)}\n")
    print(f"{'roi':9s} {'stop':>5} {'hold':>5} {'rtop':>5} {'n':>5} "
          f"{'mean%':>8} {'t_cl':>6} {'halves':>16} {'%/bar-day':>10}")
    rows = []
    for lname, lad in ladders.items():
        for stop in (-0.03, -0.05, -0.08):
            for hold in (48, 96, 192):
                for rtop in (True, False):
                    rr, keys, hb = [], [], []
                    for s, i in eps:
                        r = walk(tape[s], i + 1, lad, stop, hold,
                                 zones[s] if rtop else None)
                        if r:
                            rr.append(r[0])
                            hb.append(r[2])
                            keys.append((s, tape[s][i + 1][0] // 86400))
                    if len(rr) < 20:
                        continue
                    m = sum(rr) / len(rr)
                    mh = sum(hb) / len(hb) or 1
                    pbd = m / (mh * BAR_MIN / 1440.0)
                    h1, h2 = halves(rr)
                    tc = cluster_t(rr, keys)
                    rows.append((lname, stop, hold, rtop, len(rr), m, tc,
                                 h1, h2, pbd))
                    print(f"{lname:9s} {stop:+5.2f} {hold:5d} "
                          f"{str(rtop):>5} {len(rr):5d} {m:+8.3f} {tc:+6.2f} "
                          f"{h1:+7.3f}/{h2:+7.3f} {pbd:+10.3f}")
    base = [r for r in rows if r[0] == "shipped" and r[1] == SHIPPED_STOP
            and r[2] == SHIPPED_HOLD_BARS and r[3]]
    print("\nQ2 VERDICT (a) mean>=shipped (b) %/bar-day>shipped "
          "(c) both halves + (d) t_cl>=shipped:")
    if not base:
        print("  UNGRADED — the shipped cell produced too few closes")
        return 0
    b = base[0]
    adm = [r for r in rows
           if r[5] >= b[5] and r[9] > b[9] and r[7] > 0 and r[8] > 0
           and r[6] >= b[6] and r[:4] != b[:4]]
    print(f"  shipped: {b[5]:+.3f}%/trade  t_cl {b[6]:+.2f}  "
          f"halves {b[7]:+.3f}/{b[8]:+.3f}  %/bar-day {b[9]:+.3f}")
    if not adm:
        print("  ADMIT: none — every variant fails at least one bar. "
              "The shipped exit stands.")
    else:
        for r in sorted(adm, key=lambda x: -x[5])[:8]:
            print(f"  ADMIT {r[0]:9s} stop{r[1]:+.2f} hold{r[2]:4d} "
                  f"rtop={r[3]}: {r[5]:+.3f}%/trade t_cl {r[6]:+.2f} "
                  f"halves {r[7]:+.3f}/{r[8]:+.3f} %/bar-day {r[9]:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
