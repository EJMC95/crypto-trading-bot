#!/usr/bin/env python3
"""
scripts/backtest_funding_tail_raid_lighter.py — 🏹 TAMERLANE: raid the EXTREME
funding prints. Take the RECEIVING side when a Lighter book pays a huge rate.

THE THESIS
  Lighter's books throw enormous funding tails — measured 22-Jul across 37 books
  with paired funding+price history, |TRUE apr| percentiles are:
      p50 10.5%   p90 35.0%   p99 401.2%   p99.9 1397.2%   max 4380.0%
  (p50 = 10.5% is the venue's PINNED crypto resting constant, not a market rate —
  see [[venue-resting-defaults-trap]].) The Funding Farmer harvests crypto
  funding behind a gate; nobody harvests the tails, and especially not on the
  non-crypto books. Conqueror-shaped: strike hard at the extremes.

THE LAG IS FORCED BY THE DATA, WHICH IS THE POINT
  Settled funding is PUBLISHED AFTER IT IS PAID, so a raid on the print at t can
  only be entered at t+1. There is no lag-0 version of this test to fool myself
  with — which matters, because a lag-0 fantasy is exactly what killed the twin-
  book idea the same day ([[test-execution-lag-before-believing-intrabar-edges]]).

╔══════════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-22, 150d, 37 books, 5 thresholds x 5 holds = 25 cells)      ║
║ **DEAD IN ALL 25 CELLS — and NOT because of costs. Even at ZERO friction the ║
║ best cell is t=+1.6.** The carry is real; it is a fee for standing in front  ║
║ of a stampede, not a gift.                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
  THE FUNDING IS GENUINELY COLLECTABLE and scales exactly as theory predicts —
  at threshold 500% apr held 24h you collect **+56.9bps** of funding. That half
  of the thesis is confirmed.

  THE PRICE LEG EATS IT, AND THE ADVERSE SELECTION SCALES WITH THE EXTREMITY —
  this is the mechanism, visible straight down the table (price P&L on the
  RECEIVING side, bps):
      threshold      hold 1h     hold 8h    hold 24h
      0.30 (30%)       -0.3        -2.2        -3.0
      1.00 (100%)      -1.3       -15.7       -14.8
      2.00 (200%)      -3.3       -22.9       -24.9
      5.00 (500%)      -4.8       -10.4       -25.8
  The hotter the print, the harder the market moves against whoever receives it.
  Funding spikes BECAUSE the crowd is positioned and price is running. Same
  lesson as 🏆 Stock Leaders' crowded-long drag ([[stock-leaders-funding-adverse-selection]]).

  NET OF EVERYTHING, NOTHING IS SIGNIFICANT:
      * short holds (1-8h) are RELIABLY NEGATIVE — t = -8.9, -6.5, -5.3, -4.0 …
        (significantly losing, not merely unprofitable)
      * long holds (24h) turn slightly positive but t = +0.2 .. +1.1 — the 24h
        price variance swamps the carry entirely
      * best cell (th 5.00 / hold 24h): funding +56.9, price -25.8, net +31.1,
        net-of-10bps-cost +21.1, **t = +1.1**. Back out the cost assumption
        entirely and it is still only **t = +1.6**.
  **Cost is not the blocker — variance is.** That is worth stating precisely,
  because almost every other verdict in this fleet turns on an unmeasured
  friction constant and this one does not. No cost measurement can rescue it.

  DO NOT RE-TEST by moving thresholds or holds: 25 cells span 30%-500% apr and
  1h-24h, the sign pattern is monotone and mechanical, and the failure is in the
  variance of the price leg, which no gate on the funding side can address.

Read-only: consumes the cached Lighter tape. No bot, no DB, no orders.
"""
import json
import math
import os
import statistics as st
import sys

HPY = 24 * 365
THRESHOLDS = [0.30, 0.50, 1.00, 2.00, 5.00]
HOLDS = [1, 2, 4, 8, 24]


def evaluate(books, cost_bps):
    """books: {sym: (ts, funding{ts->apr}, price{ts->close})}. Entry FORCED at t+1."""
    rows = []
    for th in THRESHOLDS:
        for hold in HOLDS:
            F, P, N, bset = [], [], [], set()
            for s, (ts, f, p) in books.items():
                for i in range(len(ts) - hold - 2):
                    r = f[ts[i]]
                    if abs(r) < th:
                        continue
                    side = -1.0 if r > 0 else 1.0        # receive the funding
                    acc = 0.0
                    for j in range(i + 1, i + 1 + hold):
                        rj = f.get(ts[j])
                        if rj is not None:
                            acc += -side * rj / HPY
                    pi, po = p.get(ts[i + 1]), p.get(ts[i + 1 + hold])
                    if not pi or not po:
                        continue
                    pp = side * (po / pi - 1.0)
                    F.append(acc * 1e4); P.append(pp * 1e4)
                    N.append((acc + pp) * 1e4); bset.add(s)
            if len(N) < 30:
                continue
            mn = st.mean(N)
            se = st.pstdev(N) / math.sqrt(len(N))
            rows.append(dict(th=th, hold=hold, n=len(N), books=len(bset),
                             fund=st.mean(F), price=st.mean(P), net=mn,
                             se=se, t=(mn - cost_bps) / se if se else 0.0))
    return rows


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else None
    if not cache or not os.path.exists(cache):
        sys.exit("usage: backtest_funding_tail_raid_lighter.py <cached_tape.json>\n"
                 "(tape = {sym: {'f': {ts: apr}, 'p': {ts: close}}} from\n"
                 " backtest_funding_lighter.fetch_fundings / fetch_candles)")
    raw = json.load(open(cache))
    books = {}
    for s, d in raw.items():
        f = {int(k): v for k, v in d["f"].items()}
        p = {int(k): v for k, v in d["p"].items()}
        ts = sorted(set(f) & set(p))
        if len(ts) >= 24 * 30:
            books[s] = (ts, f, p)
    print(f"{len(books)} books\n")
    hdr = (f"{'thresh':>7} {'hold':>5} {'events':>7} | {'funding':>8} {'price':>9} "
           f"{'NET':>9} {'t@10bps':>8} {'t@0bps':>8} | verdict")
    print(hdr); print("-" * len(hdr))
    for r in evaluate(books, 10.0):
        t0 = r["net"] / r["se"] if r["se"] else 0.0
        v = "RAIDABLE" if r["t"] > 3 else "marginal" if r["t"] > 2 else "dead"
        print(f"{r['th']:>7.2f} {r['hold']:>5} {r['n']:>7} | {r['fund']:>+8.1f} "
              f"{r['price']:>+9.1f} {r['net']:>+9.1f} {r['t']:>+8.1f} "
              f"{t0:>+8.1f} | {v}")
    print("\nt@0bps is the t-stat with the cost assumption removed entirely — it")
    print("is what proves this is edge-blocked, not cost-blocked.")


if __name__ == "__main__":
    main()
