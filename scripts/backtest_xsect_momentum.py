#!/usr/bin/env python3
"""
scripts/backtest_xsect_momentum.py — CROSS-SECTIONAL momentum, market-neutral,
as a Lighter perp book. Doctrine gate for a NEW shadow bot ("Top Dog").

WHY THIS STRATEGY: the 12-Jul fleet audit found the fleet is saturated with
TIME-SERIES signals on individual coins (trend cluster: tide_50_200, donchian,
trendmomo, regime-switch; dip-buy cluster: rsi-meanrev, swing-daily, intraday —
plus two REJECTED dip-buyers, Trail Blazer & Bounce Catcher). Nothing anywhere
in the fleet ranks coins AGAINST EACH OTHER. Cross-sectional momentum is the
classic orthogonal factor: long the strongest N coins vs short the weakest N,
equal notional → market-neutral (fleet is long-heavy, this adds a zero-beta
book), and the driver is RELATIVE strength, not market direction or funding.

METHOD (mirrors what the live/shadow bot will do — doctrine rule 1):
  * every REB hours, rank the 30-coin Lighter-tradeable universe by trailing
    LOOKBACK-day return (optionally skipping the most recent SKIP day — the
    classic short-term-reversal guard), decided on CLOSED hourly bars;
  * long top-K / short bottom-K at ORDER_USD notional each; coins already held
    on the correct side are KEPT (turnover cost only on basket changes);
  * hourly: mark to close, accrue REAL funding with position sign
    (long pays when rate>0, short receives — exactly as live);
  * friction = SLIP per side on every open/close (Lighter perp fee is zero).

DOCTRINE GATES (all four must hold before any shadow bot ships):
  1. >=150d of real data                      — 150d HL hourly (arb'd vs Lighter)
  2. positive in BOTH sample halves           — halves simmed independently
  3. mirror test: inverted ranking (long losers / short winners) must score
     symmetrically NEGATIVE on price P&L — if both directions win it's noise
  4. robustness: a PLATEAU across lookback/K/rebalance neighbours, not one
     sweet spot; verdict picks the robust setting, not the flashiest

VERDICT (12 Jul 2026, 150d ending 10 Jul):  REJECTED — do NOT re-test.
  Only 2/40 configs pass all gates (5d/K5/24h/skip0: +14.6% / h1 +7.0 / h2
  +7.7; 21d/K5/48h/skip1: +11.8 / +0.7 / +21.6) and BOTH are isolated sweet
  spots — every parameter neighbour fails both-halves (10d is negative
  everywhere; 21d/30d full-window positives are all H1-negative, i.e. one
  trending half carrying the return). That is precisely the sweet-spot trap
  doctrine rule 4 exists to catch. The script's "CHOSEN" printout is the
  best of a rejected family, not an approval.
  The USEFUL by-product: the mirror column is strongly POSITIVE at short
  lookbacks (5d skip-1 mirror +22..+28%) — the short-term REVERSAL lead.
  That factor (and low-vol, and funding-rank) was then gated properly in
  scripts/backtest_xsect_factor_lab.py: reversal + low-vol also REJECTED;
  FUNDING-RANK passed with a real plateau and shipped as ⚖️ Counterweight
  (lighter_funding_spread_bot.py). See that script's header for numbers.

Reuses scripts/.dirfund_cache.json (150d hourly klines + funding, 30 coins).
Run scripts/backtest_directional_funding.py first if the cache is absent.
Usage:  python3 scripts/backtest_xsect_momentum.py
"""
import json
import os
import sys

CACHE = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")
ORDER_USD = 20.0          # matches live Funding Farmer clip
SLIP = 0.0005             # 5bps per side; Lighter fee is zero
HOURS_DAY = 24

LOOKBACKS_D = [5, 10, 14, 21, 30]
KS = [3, 5]
REBS_H = [24, 48]
SKIPS_D = [0, 1]


def load():
    if not os.path.exists(CACHE):
        sys.exit("cache missing — run scripts/backtest_directional_funding.py first")
    raw = json.load(open(CACHE))
    out = {}
    for coin, d in raw.items():
        ks = sorted((int(t), v) for t, v in d["k"].items())
        ts = [t for t, _ in ks]
        close = [v[3] for _, v in ks]
        fund = {}
        for t, r in d["f"].items():
            fund[int(int(t) // 3600000 * 3600000)] = r
        out[coin] = {"ts": ts, "close": close, "fund": fund}
    return out


def align(data):
    """Common hourly timeline across coins that span the whole window."""
    sets = [set(d["ts"]) for d in data.values()]
    common = sorted(set.intersection(*sets))
    coins = sorted(data.keys())
    px = {c: {} for c in coins}
    for c in coins:
        m = dict(zip(data[c]["ts"], data[c]["close"]))
        for t in common:
            px[c][t] = m[t]
    return coins, common, px


def simulate(coins, ts, px, fund, lookback_h, k, reb_h, skip_h, invert=False,
             slip=SLIP):
    """Returns (total_pnl, price_pnl, fund_pnl, max_dd_pct, n_round_trips, wins)."""
    book = {}                     # coin -> {"side": +1/-1, "entry": px, "pnl0": accum}
    cash = 0.0                    # realised pnl
    equity_hist = []
    trips = wins = 0
    gross = 2.0 * k * ORDER_USD
    price_pnl = fund_pnl = 0.0

    def mtm(t):
        u = 0.0
        for c, p in book.items():
            u += p["side"] * (px[c][t] / p["entry"] - 1.0) * ORDER_USD
        return u

    start = lookback_h + skip_h
    for i in range(start, len(ts)):
        t = ts[i]
        # hourly funding accrual on open book
        for c, p in book.items():
            r = fund[c].get(t)
            if r is not None:
                cash_flow = -p["side"] * r * ORDER_USD
                cash += cash_flow
                fund_pnl += cash_flow
        # rebalance on schedule
        if (i - start) % reb_h == 0:
            j_hi = i - skip_h
            j_lo = j_hi - lookback_h
            mom = {}
            for c in coins:
                a, b = px[c][ts[j_lo]], px[c][ts[j_hi]]
                if a > 0:
                    mom[c] = b / a - 1.0
            ranked = sorted(mom, key=mom.get, reverse=not invert)
            want = {c: +1 for c in ranked[:k]}
            want.update({c: -1 for c in ranked[-k:]})
            # close what's no longer wanted (or wrong side)
            for c in list(book):
                if want.get(c) != book[c]["side"]:
                    p = book.pop(c)
                    pnl = p["side"] * (px[c][t] / p["entry"] - 1.0) * ORDER_USD
                    pnl -= slip * ORDER_USD          # exit slip
                    cash += pnl
                    price_pnl += pnl
                    trips += 1
                    wins += 1 if pnl > 0 else 0
            # open the new ones
            for c, side in want.items():
                if c not in book:
                    cash -= slip * ORDER_USD          # entry slip
                    price_pnl -= slip * ORDER_USD
                    book[c] = {"side": side, "entry": px[c][t]}
        equity_hist.append(cash + mtm(t))

    # liquidate at end
    t = ts[-1]
    for c, p in book.items():
        pnl = p["side"] * (px[c][t] / p["entry"] - 1.0) * ORDER_USD - slip * ORDER_USD
        cash += pnl
        price_pnl += pnl
        trips += 1
        wins += 1 if pnl > 0 else 0
    equity_hist.append(cash)

    peak = 0.0
    max_dd = 0.0
    for e in equity_hist:
        peak = max(peak, e)
        max_dd = max(max_dd, peak - e)
    return cash, price_pnl, fund_pnl, 100.0 * max_dd / gross, trips, wins, gross


def pct(x, gross):
    return 100.0 * x / gross


def run_config(coins, ts, px, fund, lb_d, k, reb_h, skip_d, slip=SLIP):
    lb_h, skip_h = lb_d * HOURS_DAY, skip_d * HOURS_DAY
    half = len(ts) // 2
    res = {}
    for name, seg in (("full", ts), ("h1", ts[:half]), ("h2", ts[half:])):
        c, pp, fp, dd, tr, w, g = simulate(coins, seg, px, fund, lb_h, k, reb_h,
                                           skip_h, slip=slip)
        res[name] = dict(ret=pct(c, g), price=pct(pp, g), fund=pct(fp, g),
                         dd=dd, trips=tr, wins=w)
    c, pp, fp, dd, tr, w, g = simulate(coins, ts, px, fund, lb_h, k, reb_h,
                                       skip_h, invert=True, slip=slip)
    res["mirror"] = dict(ret=pct(c, g), price=pct(pp, g))
    return res


def main():
    data = load()
    fund = {c: d["fund"] for c, d in data.items()}
    coins, ts, px = align(data)
    days = (ts[-1] - ts[0]) / 3600000 / 24
    print(f"universe {len(coins)} coins, {len(ts)} hourly bars ({days:.0f}d), "
          f"clip ${ORDER_USD:.0f}, slip {SLIP*1e4:.0f}bps/side\n")
    hdr = (f"{'lb':>3} {'k':>2} {'reb':>4} {'skip':>4} | {'full%':>7} {'h1%':>7} "
           f"{'h2%':>7} {'dd%':>5} {'trips':>5} | {'mirror%':>8} {'fund_pp':>7} | verdict")
    print(hdr)
    print("-" * len(hdr))
    plateau = []
    for lb in LOOKBACKS_D:
        for k in KS:
            for reb in REBS_H:
                for skip in SKIPS_D:
                    r = run_config(coins, ts, px, fund, lb, k, reb, skip)
                    both = r["h1"]["ret"] > 0 and r["h2"]["ret"] > 0
                    mir_ok = r["mirror"]["price"] < 0
                    ok = both and r["full"]["ret"] > 0 and mir_ok
                    if ok:
                        plateau.append((lb, k, reb, skip, r))
                    print(f"{lb:>3} {k:>2} {reb:>4} {skip:>4} | "
                          f"{r['full']['ret']:>7.1f} {r['h1']['ret']:>7.1f} "
                          f"{r['h2']['ret']:>7.1f} {r['full']['dd']:>5.1f} "
                          f"{r['full']['trips']:>5} | {r['mirror']['ret']:>8.1f} "
                          f"{r['full']['fund']:>7.1f} | "
                          f"{'PASS' if ok else ('both-halves FAIL' if not both else 'mirror FAIL')}")
    print(f"\n{len(plateau)} / {len(LOOKBACKS_D)*len(KS)*len(REBS_H)*len(SKIPS_D)} "
          f"configs pass all gates")
    if plateau:
        # robust choice: config whose NEIGHBOURS also pass (plateau centre),
        # then highest min(h1,h2) — durability over flash
        keyset = {(lb, k, reb, s) for lb, k, reb, s, _ in plateau}

        def neighbours(lb, k, reb, s):
            li = LOOKBACKS_D.index(lb)
            n = 0
            for dli in (-1, 1):
                if 0 <= li + dli < len(LOOKBACKS_D) and \
                        (LOOKBACKS_D[li + dli], k, reb, s) in keyset:
                    n += 1
            return n

        best = max(plateau, key=lambda x: (neighbours(*x[:4]),
                                           min(x[4]["h1"]["ret"], x[4]["h2"]["ret"])))
        lb, k, reb, skip, r = best
        print(f"\nCHOSEN (plateau-centred): lookback {lb}d, K={k}, reb {reb}h, "
              f"skip {skip}d")
        print(f"  full {r['full']['ret']:+.1f}%  h1 {r['h1']['ret']:+.1f}%  "
              f"h2 {r['h2']['ret']:+.1f}%  maxDD {r['full']['dd']:.1f}%  "
              f"mirror(price) {r['mirror']['price']:+.1f}%")
        rs = run_config(coins, ts, px, fund, lb, k, reb, skip, slip=2 * SLIP)
        print(f"  2x-slip stress (10bps/side): full {rs['full']['ret']:+.1f}%  "
              f"h1 {rs['h1']['ret']:+.1f}%  h2 {rs['h2']['ret']:+.1f}%  "
              f"-> {'still PASS' if rs['h1']['ret'] > 0 and rs['h2']['ret'] > 0 else 'FAILS under stress'}")


if __name__ == "__main__":
    main()
