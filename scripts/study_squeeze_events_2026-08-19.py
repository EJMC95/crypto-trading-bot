#!/usr/bin/env python3
"""
study_squeeze_events_2026-08-19.py — the funding-extreme SQUEEZE event study.
Growth study #2 admitted at (qa): "the price leg the fleet only ever EATS
(the ~90% adverse intrabar excursion the leverage study measured; the
Farmer's LIT stops). Unlike the retired knife-catchers, a squeeze-long is
PAID to wait (-50% apr ~= 0.11%/day received). ~4-6 tradeable candidates at
any moment."

QUESTION
  After a FRESH funding extreme on a crypto book, does taking the RECEIVING
  side for 24-72h earn positive expectancy net of friction — price leg plus
  funding accrual — or is the "paid to wait" carry eaten by the drift the
  extreme is pricing?

DATA — Lighter ONLY (the venue we trade is the venue we measure): settled
  /api/v1/fundings + /api/v1/candles via backtest_funding_lighter's own
  fetchers (the verified basis; one owner). Universe: every crypto book
  (fleet_bus.is_crypto) present in orderBookDetails, tiered by CURRENT
  daily volume — point-in-time volume is not reconstructable ((ny)), so tier
  membership is a DECLARED drifting label, never a verdict input.

PRE-REGISTERED RULES — written before any result existed:
  S1 event: hourly settled TRUE apr |a_t| >= E (grid E in {0.5, 1.0, 2.0})
     AND median |a| over the prior 24h < E/2 (a FRESH extreme, not a
     continuation), AND the coin has candles at entry and entry+H.
     Dedup: one event per coin per 72h (first wins).
  S2 side: the receiving side of the current rate (a_t < 0 -> LONG receives;
     a_t > 0 -> SHORT receives).
  S3 outcome over H in {24, 48, 72}h: side * close-to-close price return
     + sum of hourly settled funding received over the hold (sign per side)
     - friction, at BOTH tier-median 5.12bps and p90 14.77bps per-side
     ((pw)'s measured tier friction; 2 sides charged).
  S4 ESTABLISHED requires ALL of: n >= 30 events; mean net > 0 at p90
     friction; t >= 2.0; both time halves positive; beats the S5 null at
     P <= 0.05. Anything less is REPORTED, never established.
  S5 null ((hm) — grade a directional idea against random, never zero):
     300 draws; each draw takes the same NUMBER of (coin, hour) entries
     sampled from the same coins and window at NON-event hours
     (|apr| < E/2), receiving side of the current rate, same H, same
     friction. P = fraction of draws >= the event mean.
  S6 tier split reported: [1e5,2e6) / [2e6,1e7) / >=1e7 by current volume.
  S7 concentration: top-3 events' share of total net; > 50% => the
     (nu)/(oj) undecidable-by-tail shape — refused regardless of t.
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

DAYS = int(os.environ.get("SQZ_DAYS", "180"))
E_GRID = [0.5, 1.0, 2.0]
H_GRID = [24, 48, 72]
FRICTION = {"median": 5.12e-4, "p90": 14.77e-4}  # per-side, (pw) tier table
MIN_VOL = 1e5
NULL_DRAWS = 300
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sqz_cache")
SEED = 20260819  # deterministic null


def load_universe():
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    out = []
    for o in obs:
        sym = o.get("symbol")
        vol = float(o.get("daily_quote_token_volume") or 0)
        if not sym or vol < MIN_VOL or not is_crypto(sym):
            continue
        out.append((sym, o["market_id"], vol))
    out.sort(key=lambda x: -x[2])
    return out


def cached_series(kind, sym, mid):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{kind}_{sym}_{DAYS}.json")
    if os.path.exists(p):
        return {int(k): v for k, v in json.load(open(p)).items()}
    v = (fetch_fundings if kind == "f" else fetch_candles)(mid, DAYS)
    json.dump({str(k): val for k, val in v.items()}, open(p, "w"))
    return v


def tier_of(vol):
    if vol < 2e6:
        return "[0.1M,2M)"
    if vol < 1e7:
        return "[2M,10M)"
    return ">=10M"


def outcome(cand, fund, t0, side, H, frict):
    """side: +1 long, -1 short. Net fractional return on the clip."""
    c0 = cand.get(t0)
    c1 = cand.get(t0 + H * 3600)
    if not c0 or not c1:
        return None
    px = side * (c1[3] / c0[3] - 1.0)
    acc = 0.0
    for k in range(H):
        a = fund.get(t0 + k * 3600)
        if a is None:
            continue
        # a is signed TRUE apr; positive apr: longs pay shorts. Receiving is
        # -side * a / (24*365) per hour... expressed directly:
        acc += (-side) * (a / (24 * 365))
    return px + acc - 2 * frict


def halves(vals_ts):
    if not vals_ts:
        return 0.0, 0.0
    ts_sorted = sorted(t for t, _ in vals_ts)
    med = ts_sorted[len(ts_sorted) // 2]
    h1 = sum(v for t, v in vals_ts if t <= med)
    h2 = sum(v for t, v in vals_ts if t > med)
    return h1, h2


def tstat(xs):
    n = len(xs)
    if n < 2:
        return None
    m = statistics.mean(xs)
    sd = statistics.stdev(xs)
    return m / (sd / math.sqrt(n)) if sd > 0 else None


def main():
    rng = random.Random(SEED)
    uni = load_universe()
    print(f"universe: {len(uni)} crypto books >= ${MIN_VOL:,.0f} daily vol; {DAYS}d")

    data = {}
    for i, (sym, mid, vol) in enumerate(uni):
        try:
            f = cached_series("f", sym, mid)
            c = cached_series("c", sym, mid)
            if f and c:
                data[sym] = {"f": f, "c": c, "vol": vol}
        except Exception as e:
            print(f"  ! {sym}: {e}")
        if i % 20 == 19:
            print(f"  fetched {i+1}/{len(uni)}")

    print(f"data for {len(data)} coins")

    # ---- event extraction (S1) --------------------------------------------
    events = {E: [] for E in E_GRID}
    nonevent_pool = {E: [] for E in E_GRID}
    for sym, d in data.items():
        hours = sorted(d["f"])
        seen_until = {E: 0 for E in E_GRID}
        for t in hours:
            a = d["f"][t]
            prior = [abs(d["f"][t - k * 3600]) for k in range(1, 25)
                     if (t - k * 3600) in d["f"]]
            if len(prior) < 18:
                continue
            med_prior = statistics.median(prior)
            for E in E_GRID:
                if abs(a) >= E and med_prior < E / 2 and t >= seen_until[E]:
                    events[E].append((sym, t, a))
                    seen_until[E] = t + 72 * 3600
                elif abs(a) < E / 2:
                    nonevent_pool[E].append((sym, t, a))

    for E in E_GRID:
        print(f"E={E}: {len(events[E])} events, pool {len(nonevent_pool[E])}")

    # ---- outcomes + verdicts ----------------------------------------------
    for E in E_GRID:
        evs = events[E]
        if not evs:
            continue
        print(f"\n=== E = {E} ({E*100:.0f}% TRUE apr) ===")
        for H in H_GRID:
            for fname, fr in FRICTION.items():
                rows = []
                for sym, t, a in evs:
                    side = 1 if a < 0 else -1
                    r = outcome(data[sym]["c"], data[sym]["f"], t, side, H, fr)
                    if r is not None:
                        rows.append((sym, t, r))
                if not rows:
                    print(f" H={H} {fname}: no priceable events")
                    continue
                vals = [r for _, _, r in rows]
                tot = sum(vals)
                n = len(vals)
                t_ = tstat(vals)
                h1, h2 = halves([(t, v) for _, t, v in rows])
                top3 = sum(sorted(vals, reverse=True)[:3])
                conc = (top3 / tot * 100) if tot > 0 else float("inf")
                # S5 null
                pool = nonevent_pool[E]
                beats = 0
                mean_ev = tot / n
                for _ in range(NULL_DRAWS):
                    draw = [pool[rng.randrange(len(pool))] for _ in range(n)]
                    dv = []
                    for sym, tt, aa in draw:
                        side = 1 if aa < 0 else -1
                        r = outcome(data[sym]["c"], data[sym]["f"], tt, side, H, fr)
                        if r is not None:
                            dv.append(r)
                    if dv and statistics.mean(dv) >= mean_ev:
                        beats += 1
                P = beats / NULL_DRAWS
                est = (n >= 30 and mean_ev > 0 and fname == "p90"
                       and (t_ or 0) >= 2.0 and h1 > 0 and h2 > 0
                       and P <= 0.05 and conc <= 50)
                print(f" H={H:2d}h {fname:6s}: n={n:4d} mean={mean_ev*100:+.3f}% "
                      f"tot={tot*100:+8.2f}%-clip t={t_ if t_ is None else round(t_,2)} "
                      f"h1/h2={h1*100:+.1f}/{h2*100:+.1f} top3={conc:.0f}% "
                      f"P_null={P:.3f}{'  << ESTABLISHED' if est else ''}")

        # tier split (S6) at H=48, p90
        print(" tier split (H=48h, p90):")
        for tier in ("[0.1M,2M)", "[2M,10M)", ">=10M"):
            rows = []
            for sym, t, a in evs:
                if tier_of(data[sym]["vol"]) != tier:
                    continue
                side = 1 if a < 0 else -1
                r = outcome(data[sym]["c"], data[sym]["f"], t, side, 48,
                            FRICTION["p90"])
                if r is not None:
                    rows.append(r)
            if rows:
                print(f"   {tier:10s}: n={len(rows):4d} "
                      f"mean={statistics.mean(rows)*100:+.3f}% "
                      f"tot={sum(rows)*100:+8.2f}%-clip")

    print("\nDONE — apply S4/S7 by reading the tables; tier labels are "
          "CURRENT volume (declared drifting).")


if __name__ == "__main__":
    main()
