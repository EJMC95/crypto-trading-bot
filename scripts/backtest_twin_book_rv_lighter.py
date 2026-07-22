#!/usr/bin/env python3
"""
scripts/backtest_twin_book_rv_lighter.py — ⚔️ GENGHIS KHAN: relative value
between Lighter books that track the SAME underlying.

THE STRUCTURAL IDEA
  Lighter lists more than one perp on a single underlying: SPY / US500 / SPX are
  all S&P 500; QQQ / US100 are both Nasdaq 100; XAU / PAXG are both gold. Same
  venue, same margin, same funding clock, SEPARATE order books. When two books on
  one underlying drift apart, closing the gap is a dollar-neutral trade with no
  market exposure and no regime dependence — which matters here because every
  directional verdict on this venue is contaminated by a single falling regime
  (CLAUDE.md item-18 / D5). A twin spread has nothing to launder.

WHAT RECON ALREADY KILLED — do not put these back
  * SPY/SPX and US500/SPX: SPX is the THINNEST book on the venue ($0.02M/day,
    8.96bps half-spread); its marks wander ~10%, which is a dead book, not an arb.
  * WTI/BRENTOIL: genuinely different commodities with a real macro spread. Not
    a twin; a 98h half-life confirms it.
  * XAU/PAXG: reverts +4.3bps by t+6 against a 6.0bps round trip — REAL but does
    not clear its costs. PAXG is a gold-backed TOKEN with its own basis, not a
    gold twin. Dead on economics, not on statistics.

WHY THIS SURVIVED ITS KILLER OBJECTION (recon, 60d hourly)
  The obvious refutation is STALE PRINTS: if book A last traded at :05 and B at
  :55, the hourly closes are sampled at different instants and the "deviation" is
  an artifact. A ~1.7h reversion half-life is exactly what that would look like.
  Three tests said otherwise:
    T1 print density — SPY 0.5% zero-volume hours, US500 1.2%, US100 2.8%.
    T2 synchrony     — mean|dev| in hours where BOTH books are active vs hours
                       where either is thin: ratio 0.94 (SPY/US500), 1.00
                       (QQQ/US100). An artifact would be LARGER in thin hours.
    T3 capturability — after |dev|>p90, mean signed reversion by t+6 was
                       +5.1bps (SPY/US500, t=+9.0) and +8.7bps (QQQ/US100,
                       t=+7.7), n=144 events each.
  Cost coverage: SPY/US500 2.4x, QQQ/US100 1.6x. Thin, and that is the risk.

PRE-REGISTERED DECISION RULE (written BEFORE the first run, not adjusted after)
  G1. full > 0 AND h1 > 0 AND h2 > 0, net of costs and funding.
  G2. MIRROR < 0 — the inverted book (momentum: chase the divergence instead of
      fading it) must LOSE. If both directions win, the "edge" is a cost artifact.
  G3. PLATEAU — >=4 of the 9 (entry z, exit z) cells pass, contiguously. Not one
      sweet spot. This is the gate that killed the non-crypto funding book.
  G4. maxDD < 15% of gross deployed (the fleet go-live gate).
  G5. SURVIVES 2x friction in BOTH halves. NOT 3x: measured cost coverage is only
      1.6-2.4x, so demanding 3x would reject on arithmetic before evidence. 2x is
      the honest bar and this deviation from the usual 3x is DECLARED, not hidden.
  G6. Per-pair, not pooled: SPY/US500 and QQQ/US100 must each stand alone. Two
      pairs is not a portfolio and pooling would hide a single-pair fluke.

  WINDOW HONESTY: US500/US100 carry only ~63d of tape, so this is a SHORT study.
  63d cannot support a strong claim. A pass here means "worth a shadow book",
  never "worth real money".

COSTS
  Per-book measured half-spread (live book walk), charged on BOTH legs at entry
  AND exit. Lighter perp fees are zero, so the crossed spread is the whole cost.
  Settled funding on both legs is accrued hourly and NETTED — a dollar-neutral
  twin pair is nearly funding-flat, but "nearly" is measured here, not assumed.

╔══════════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-22, 63d hourly, SPY/US500 + QQQ/US100)                      ║
║ **DEAD — NOT CAPTURABLE. The deviation and its reversion are the SAME PRINT.**║
║ Passes every pre-registered gate at lag 0 and dies at ONE HOUR of lag.       ║
╚══════════════════════════════════════════════════════════════════════════════╝
  AT LAG 0 it looks superb — and this is exactly why lag 0 is not a result:
      SPY/US500   9/9 cells   full +2.0%  h1 +0.7 / h2 +0.7  dd 0.0%  mirror −3.5%
      QQQ/US100   9/9 cells   full +3.7%  h1 +0.3 / h2 +2.7  dd 0.1%  mirror −5.8%
      both green at 2x friction; lookback plateau positive at every window 3d-21d.

  WITH EXECUTION LAG IMPLEMENTED CORRECTLY (signal from prices at t, FILLS at
  prices at t+k) the whole thing inverts:
      pair          lag0     lag1     lag2     lag3     lag6
      SPY/US500    +1.61    -0.70    -0.99    -1.03    -0.97
      QQQ/US100    +2.97    -1.54    -1.82    -0.95    -1.57
      at 2x friction, lag1: -1.81 and -3.32.

  THE DIAGNOSTIC THAT SETTLES IT: at lag 1 the MIRROR IS ALSO NEGATIVE
  (−3.00% / −4.67%). Fading loses AND chasing loses => at one hour of lag there
  is ZERO directional information left, only cost. No threshold, no lookback and
  no hold rule recovers information that is not there. Do not re-grid this.

  WHY THE RECON WAS MISLEADING — the objection had a SECOND FORM I did not test.
  The staleness control (T2: is the deviation bigger in thin hours? ratio 0.94 /
  1.00) ruled out one mechanism — dead-hour print artifacts — and I wrongly
  concluded the idea had "survived its killer objection". It had not. The deeper
  failure is that the deviation is real WITHIN a bar and gone by the next one, so
  the T3 event study (|dev| shrinking from close t to close t+k, t=+9.0) measured
  a reversion that cannot be reached: capturing it requires transacting at the
  very print used to detect it. **A statistically overwhelming effect (t=+9.0)
  and an uncapturable one are entirely compatible.** Always test execution lag
  before believing an intrabar effect.

  ALSO NOTE — the first lag test I wrote was a NO-OP (it shifted the signal and
  the fill series together, so no lag was ever introduced) and returned +1.98,
  +1.98, +1.97, +1.96 across lags 0-3. Flat output across a parameter that MUST
  matter is the fingerprint of a broken test, not of a robust strategy. That
  near-miss is the reason this banner exists.

  WHAT WOULD CHANGE THIS: only sub-bar execution — a market-making/quoting system
  reacting inside the hour. That is a different engineering problem (sub-minute
  loop, quote management, adverse selection) from anything this fleet runs, the
  books are ~$0.4M/day, and it is not tested here. Do NOT read this verdict as
  "worth building fast infrastructure for" — it is untested at that cadence.

  Already killed at recon, keep them dead: SPY/SPX + US500/SPX (SPX is the
  venue's thinnest book, $0.02M/day, marks wander ~10%), WTI/BRENTOIL (different
  commodities, 98h half-life), XAU/PAXG (+4.3bps reversion vs a 6.0bps round
  trip — real but under water; PAXG is a gold-backed TOKEN with its own basis).

Read-only: public Lighter endpoints only. No bot, no DB, no orders.
Usage:
    .venv/bin/python3 scripts/backtest_twin_book_rv_lighter.py
"""
import argparse
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(__file__))
from backtest_funding_lighter import _get, fetch_candles, fetch_fundings  # noqa: E402

PAIRS = [("SPY", "US500"), ("QQQ", "US100")]
NOTIONAL = 250.0          # per leg; 2 legs = $500 gross per open pair
HOURS_PER_YEAR = 24 * 365
MAX_HOLD_H = 24
Z_GRID = [(2.0, 0.5), (2.0, 0.0), (2.0, -0.5),
          (2.5, 0.5), (2.5, 0.0), (2.5, -0.5),
          (3.0, 0.5), (3.0, 0.0), (3.0, -0.5)]
WIN = 24 * 7              # trailing window for the spread mean/sd (7d hourly)


def half_spread_bps(mid):
    try:
        r = _get("/api/v1/orderBookOrders", market_id=mid, limit=1)
        a = float((r.get("asks") or [{}])[0].get("price", 0))
        b = float((r.get("bids") or [{}])[0].get("price", 0))
        if a > b > 0:
            return (a - b) / ((a + b) / 2) * 1e4 / 2.0
    except Exception:  # noqa: BLE001
        pass
    return None


def simulate(ts, ra, rb, fa, fb, z_in, z_out, cost_bps, invert=False):
    """Fade (or, inverted, chase) the twin spread. Dollar-neutral, 1 pair at a
    time. Returns (pnl$, trips, wins, maxDD$, funding$)."""
    pos = None          # (side, i_open, entry_ratio)  side=+1 long A short B
    cash = fundpnl = 0.0
    eq, peak, dd = [], 0.0, 0.0
    trips = wins = 0
    for i in range(WIN, len(ts)):
        r = ra[i] / rb[i]
        w = [ra[j] / rb[j] for j in range(i - WIN, i)]
        mu, sd = st.mean(w), st.pstdev(w)
        if sd <= 0:
            eq.append(cash); continue
        z = (r - mu) / sd
        if pos is not None:
            side, i0, entry = pos
            # funding on both legs, netted (long pays, short receives)
            f = (-side * (fa.get(ts[i]) or 0.0) + side * (fb.get(ts[i]) or 0.0))
            f = f / HOURS_PER_YEAR * NOTIONAL
            cash += f; fundpnl += f
            hit = (side > 0 and z >= -z_out) or (side < 0 and z <= z_out)
            if hit or (i - i0) >= MAX_HOLD_H:
                # spread return: long A short B earns the ratio moving up
                pnl = side * (r / entry - 1.0) * NOTIONAL - 2 * cost_bps / 1e4 * NOTIONAL
                cash += pnl; trips += 1; wins += 1 if pnl > 0 else 0
                pos = None
        if pos is None:
            if z <= -z_in:
                pos = (+1, i, r); cash -= 2 * cost_bps / 1e4 * NOTIONAL
            elif z >= z_in:
                pos = (-1, i, r); cash -= 2 * cost_bps / 1e4 * NOTIONAL
            if invert and pos is not None:      # chase instead of fade
                s, i0, e = pos
                pos = (-s, i0, e)
        eq.append(cash)
        peak = max(peak, cash); dd = max(dd, peak - cash)
    return cash, trips, wins, dd, fundpnl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    a = ap.parse_args()

    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    ids = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}
    need = sorted({s for p in PAIRS for s in p})
    px, fu, sp = {}, {}, {}
    for s in need:
        if s not in ids:
            print(f"  {s}: NOT LISTED"); continue
        px[s] = {t: v[3] for t, v in fetch_candles(ids[s], a.days).items()}
        fu[s] = fetch_fundings(ids[s], a.days)
        sp[s] = half_spread_bps(ids[s]) or 3.0
        print(f"  {s:7s} {len(px[s]):5d}h  half-spread {sp[s]:5.2f}bps")

    overall = {}
    for A, B in PAIRS:
        if A not in px or B not in px:
            continue
        ts = sorted(set(px[A]) & set(px[B]))
        if len(ts) < WIN + 24 * 20:
            print(f"\n{A}/{B}: too little paired history ({len(ts)}h)"); continue
        ra = [px[A][t] for t in ts]
        rb = [px[B][t] for t in ts]
        cost = sp[A] + sp[B]         # one side of one round trip, both legs
        gross = 2 * NOTIONAL
        half = len(ts) // 2
        print(f"\n{'='*94}\n{A}/{B}  {len(ts)}h ({(ts[-1]-ts[0])/86400:.0f}d)   "
              f"cost {cost:.2f}bps/side/pair   gross ${gross:.0f}\n{'='*94}")
        print(f"{'z_in':>5} {'z_out':>6} | {'full%':>7} {'h1%':>7} {'h2%':>7} "
              f"{'dd%':>6} {'trips':>6} {'win%':>6} {'fund$':>7} | {'mirror%':>8} | verdict")
        print("-" * 94)
        passes = []
        for z_in, z_out in Z_GRID:
            res = {}
            for name, sl in (("full", slice(None)), ("h1", slice(0, half)),
                             ("h2", slice(half, None))):
                c, tr, w, dd, fp = simulate(ts[sl], ra[sl], rb[sl],
                                            fu[A], fu[B], z_in, z_out, cost)
                res[name] = (100 * c / gross, tr, w, 100 * dd / gross, fp)
            mc, _, _, _, _ = simulate(ts, ra, rb, fu[A], fu[B], z_in, z_out,
                                      cost, invert=True)
            ok = (res["full"][0] > 0 and res["h1"][0] > 0 and res["h2"][0] > 0
                  and 100 * mc / gross < 0 and res["full"][3] < 15)
            if ok:
                passes.append((z_in, z_out))
            f = res["full"]
            print(f"{z_in:>5.1f} {z_out:>6.1f} | {f[0]:>7.1f} {res['h1'][0]:>7.1f} "
                  f"{res['h2'][0]:>7.1f} {f[3]:>6.1f} {f[1]:>6} "
                  f"{100*f[2]/max(1,f[1]):>6.1f} {f[4]:>7.2f} | "
                  f"{100*mc/gross:>8.1f} | {'PASS' if ok else 'FAIL'}")
        print(f"  -> {len(passes)}/9 cells pass: {passes}")
        overall[(A, B)] = passes

        if passes:
            z_in, z_out = passes[0]
            print(f"  2x FRICTION STRESS on {passes[0]} (G5, declared 2x not 3x):")
            for m in (1, 2):
                c, tr, w, dd, fp = simulate(ts, ra, rb, fu[A], fu[B], z_in, z_out,
                                            cost * m)
                c1, *_ = simulate(ts[:half], ra[:half], rb[:half], fu[A], fu[B],
                                  z_in, z_out, cost * m)
                c2, *_ = simulate(ts[half:], ra[half:], rb[half:], fu[A], fu[B],
                                  z_in, z_out, cost * m)
                print(f"    {m}x ({cost*m:5.2f}bps): full {100*c/gross:+6.1f}%  "
                      f"h1 {100*c1/gross:+6.1f}%  h2 {100*c2/gross:+6.1f}%  "
                      f"{'green' if c>0 and c1>0 and c2>0 else '**NEGATIVE**'}")

    print("\n" + "=" * 94)
    print("G6 — each pair must stand ALONE (pooling would hide a single-pair fluke)")
    print("=" * 94)
    for k, v in overall.items():
        print(f"  {k[0]}/{k[1]}: {len(v)}/9 cells pass "
              f"{'-> PLATEAU (G3 ok)' if len(v) >= 4 else '-> FAILS G3 (needs >=4)'}")


if __name__ == "__main__":
    main()
