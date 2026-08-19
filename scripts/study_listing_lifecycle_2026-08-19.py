#!/usr/bin/env python3
"""
study_listing_lifecycle_2026-08-19.py — the listing-lifecycle retrospective.
Growth study #3 admitted at (qa): "72 crypto birth events on the venue's own
`created_at` history vs 🎯 the sniper's n=1-per-listing problem."

QUESTION
  Does a newly listed crypto book drift in a tradeable direction over its
  first days — i.e. does the sniper's founding thesis (n=1 in its whole
  life) have any measurable edge behind it, on either side?

DATA — Lighter ONLY: venue `created_at` from /api/v1/orderBookDetails (the
  same field the (30-Jul) sniper fix reads), hourly candles + settled
  fundings via backtest_funding_lighter's fetchers, cached.

DECLARED BIAS — SURVIVORSHIP, and the read is pre-registered asymmetric:
  the population is crypto books that EXIST in today's orderBookDetails.
  Books born and since DELISTED are invisible, which inflates the long
  side. Therefore: a NEGATIVE long-side verdict is decisive (bias runs the
  other way); a POSITIVE long-side verdict is only an upper bound and would
  need a delisting-inclusive re-run before anything acts on it.

PRE-REGISTERED RULES:
  L1 event: crypto book with created_at inside the last 180d and >= 2
     candle-hours of history. Entry at the close of the book's FIRST full
     hour bar (hour-1 close — the listing print itself is not tradeable
     at a 15-min sniper loop). One event per book.
  L2 outcomes at H in {24, 72, 168}h: LONG net = price return + funding
     received - 2 x p90 tier friction (14.77bps/side, (pw)); SHORT net
     reported beside it (= -price + funding-received-on-short - friction).
  L3 null ((hm)): 300 draws of the same n (coin, hour) entries from the
     SAME coins at age > 14d, long side, same H, same friction.
  L4 ESTABLISHED requires: n >= 30, mean > 0 at p90, t >= 2.0, both halves
     positive, P_null <= 0.05, top-3 share <= 50% ((nu)/(oj)). A positive
     that clears everything is STILL only an upper bound per the bias note.
"""

import json
import math
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_funding_lighter import _get, fetch_fundings, fetch_candles  # noqa: E402
from fleet_bus import is_crypto  # noqa: E402

DAYS = 180
H_GRID = [24, 72, 168]
FRICT = 14.77e-4
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sqz_cache")
SEED = 20260819


def cached_series(kind, sym, mid):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{kind}_{sym}_{DAYS}.json")
    if os.path.exists(p):
        return {int(k): v for k, v in json.load(open(p)).items()}
    v = (fetch_fundings if kind == "f" else fetch_candles)(mid, DAYS)
    json.dump({str(k): val for k, val in v.items()}, open(p, "w"))
    return v


def net(cand, fund, t0, side, H):
    c0, c1 = cand.get(t0), cand.get(t0 + H * 3600)
    if not c0 or not c1:
        return None
    px = side * (c1[3] / c0[3] - 1.0)
    acc = sum((-side) * (fund[t0 + k * 3600] / (24 * 365))
              for k in range(H) if (t0 + k * 3600) in fund)
    return px + acc - 2 * FRICT


def tstat(xs):
    if len(xs) < 2:
        return None
    sd = statistics.stdev(xs)
    return statistics.mean(xs) / (sd / math.sqrt(len(xs))) if sd > 0 else None


def main():
    rng = random.Random(SEED)
    now = time.time()
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    births = []
    for o in obs:
        sym, mid = o.get("symbol"), o.get("market_id")
        ca = o.get("created_at")
        if not sym or ca is None or not is_crypto(sym):
            continue
        try:
            ts = float(ca)
            if ts > 1e12:
                ts /= 1000.0
        except Exception:
            continue
        age_d = (now - ts) / 86400
        if 0 < age_d <= DAYS:
            births.append((sym, mid, ts, age_d))
    births.sort(key=lambda b: b[3])
    print(f"crypto births in last {DAYS}d visible today: {len(births)}")
    for sym, _, _, age in births:
        print(f"  {sym:12s} age {age:6.1f}d")

    data = {}
    for sym, mid, ts, _ in births:
        try:
            c = cached_series("c", sym, mid)
            f = cached_series("f", sym, mid)
            if c:
                data[sym] = {"c": c, "f": f, "born": ts}
        except Exception as e:
            print(f"  ! {sym}: {e}")

    events = []
    for sym, d in data.items():
        hours = sorted(d["c"])
        if len(hours) < 3:
            continue
        t0 = hours[1]  # close of the first FULL hour bar (L1)
        events.append((sym, t0))
    print(f"events priceable: {len(events)}")

    # aged pool for the null
    pool = []
    for sym, d in data.items():
        for t in sorted(d["c"]):
            if t - d["born"] > 14 * 86400:
                pool.append((sym, t))
    print(f"aged null pool: {len(pool)}")

    for H in H_GRID:
        for side, name in ((1, "LONG"), (-1, "SHORT")):
            rows = [(s, t, net(data[s]["c"], data[s]["f"], t, side, H))
                    for s, t in events]
            rows = [(s, t, r) for s, t, r in rows if r is not None]
            if not rows:
                print(f"H={H:3d}h {name}: no priceable events")
                continue
            vals = [r for _, _, r in rows]
            tot, n = sum(vals), len(vals)
            ts_sorted = sorted(t for _, t, _ in rows)
            med = ts_sorted[n // 2]
            h1 = sum(r for _, t, r in rows if t <= med)
            h2 = sum(r for _, t, r in rows if t > med)
            top3 = sum(sorted(vals, reverse=True)[:3])
            conc = (top3 / tot * 100) if tot > 0 else float("inf")
            beats = 0
            if pool and side == 1:
                for _ in range(300):
                    draw = [pool[rng.randrange(len(pool))] for _ in range(n)]
                    dv = [net(data[s]["c"], data[s]["f"], t, 1, H)
                          for s, t in draw]
                    dv = [x for x in dv if x is not None]
                    if dv and statistics.mean(dv) >= tot / n:
                        beats += 1
            P = beats / 300 if (pool and side == 1) else None
            est = (side == 1 and n >= 30 and tot / n > 0
                   and (tstat(vals) or 0) >= 2.0 and h1 > 0 and h2 > 0
                   and P is not None and P <= 0.05 and conc <= 50)
            print(f"H={H:3d}h {name}: n={n:3d} mean={tot/n*100:+.3f}% "
                  f"tot={tot*100:+8.2f}%-clip t={tstat(vals) and round(tstat(vals),2)} "
                  f"h1/h2={h1*100:+.1f}/{h2*100:+.1f} top3={conc:.0f}% "
                  f"P_null={P}"
                  f"{'  << clears L4 (UPPER BOUND ONLY - survivorship)' if est else ''}")

    print("\nDONE — survivorship bias declared: negative long verdicts are "
          "decisive, positive ones are upper bounds only.")


if __name__ == "__main__":
    main()
