#!/usr/bin/env python3
"""
scripts/backtest_overdrive.py — LEVERAGE gate for the funding-spread book
("⚡ Overdrive": the high-leverage operator built on the fleet's one PASSING
cross-sectional edge, 12 Jul 2026).

CONTEXT: the intraday-breakout leverage operator was REJECTED the same day
(backtest_leverage_operator.py — 1/32 marginal survivor that fails 2x-slip
stress; do not re-test). Doctrine-clean alternative: apply leverage to the
ALREADY-VALIDATED funding-LEVEL rank book (backtest_xsect_factor_lab.py
FACTOR B, shipped shadow as ⚖️ Counterweight — 72h/K5/24h plateau centre).
A market-neutral carry book is the textbook use of perp leverage: returns
scale ~linearly with gear; the NEW physics to gate is (a) per-leg
LIQUIDATION risk (a single coin ripping against one side before the daily
rebalance) and (b) whether the halves survive slip stress at size.

METHOD: replay the exact factor-lab book (rank by 72h mean funding, LONG
bottom-5 / SHORT top-5, 24h rebalance) but track each position's INTRABAR
max adverse excursion (hourly OHLC, not closes) from entry to exit. A
position liquidates if adverse >= 0.9/lev (isolated margin), closed at the
liq price with a 25bps penalty. Returns/dd are reported on the MARGIN
(equity) basis: margin = gross/lev, so ret_equity = ret_gross * lev.
NOTE this replay uses hourly closes for fills (5bps/side base) like the
factor lab, so gross-basis numbers differ slightly from the lab's (which
had no intrabar tracking); the gates are re-run here, not inherited.

GATES: both halves positive at the chosen lev; ZERO liquidations at the
chosen lev (and still zero at 15bps stress); equity-basis maxDD <= ~40%;
positive at 15bps/side slip stress in BOTH halves.

VERDICT (12 Jul 2026, 150d ending 10 Jul): REJECTED at every gear — do NOT
  re-test. The intrabar replay exposed what the close-only factor lab could
  not: the short leg (structurally short crowded-funding coins) carries
  SQUEEZE-BLOWUP tail risk — one position saw a ~90% adverse intrabar
  excursion inside a single 24h hold (a liq even at 1x isolated margin!),
  5 liq events at 3x, 20 at 5x; and 15bps slip stress turns h1 negative at
  every lev >= 2. Adding the Farmer-standard 10% hard stop (pre-declared)
  removes ALL liqs but KILLS the edge: h1 goes negative at every gear
  (even 1x: -0.4%) — the stops whipsaw the book out of the mean-reverting
  positions whose recovery pays the carry (413 vs 347 trips; ~66 stop-outs
  ate the thin first-half edge).
  CONCLUSION (structural, not tuning): the funding-spread edge is
  compensation for tail risk. Levered, you either eat the tail (liq) or
  pay the insurance (stops) that costs more than the levered carry earns.
  The book is only safe UNLEVERED without stops — which is exactly what
  ⚖️ Counterweight already runs ($200 gross on $1000 shadow equity).
  Corollary for [[lighter-go-live-decision]]: if Counterweight ever goes
  live, its collateral must be sized so gross <= ~1x equity, and NEVER
  add stops to "protect" it — both knobs are now evidence-rejected.

Usage:  python3 scripts/backtest_overdrive.py
"""
import json
import os
import sys

CACHE = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")
ORDER_USD = 20.0          # gross clip per leg (margin = ORDER_USD/lev)
K = 5
LOOKBACK_H = 72
REB_H = 24
SLIP = 0.0005
LIQ_FRAC = 0.90
LIQ_PENALTY = 0.0025
LEVS = [1, 2, 3, 5]


def load():
    if not os.path.exists(CACHE):
        sys.exit("cache missing — run scripts/backtest_directional_funding.py first")
    raw = json.load(open(CACHE))
    out = {}
    for coin, d in raw.items():
        ks = sorted((int(t), v) for t, v in d["k"].items())
        out[coin] = {
            "ts": [t for t, _ in ks],
            "h": [v[1] for _, v in ks], "l": [v[2] for _, v in ks],
            "c": [v[3] for _, v in ks],
            "f": {int(int(t) // 3600000 * 3600000): r
                  for t, r in d["f"].items()},
        }
    return out


def simulate(data, coins, common, idx, lev, slip=SLIP, stop_frac=None):
    """Funding-spread book with intrabar liq tracking. Gross clip ORDER_USD;
    margin basis = gross/lev. Returns %, on the margin basis."""
    book = {}       # coin -> {side(+1 long), entry}
    cash = fund_pnl = 0.0
    trips = wins = liqs = 0
    eq = []
    gross = 2.0 * K * ORDER_USD
    margin = gross / lev

    def close(coin, px, why):
        nonlocal cash, trips, wins, liqs
        p = book.pop(coin)
        pnl = p["side"] * (px / p["entry"] - 1.0) * ORDER_USD - slip * ORDER_USD
        cash += pnl
        trips += 1
        wins += 1 if pnl > 0 else 0
        if why == "liq":
            liqs += 1

    start = LOOKBACK_H + 1
    for j in range(start, len(common)):
        t = common[j]
        # funding + liq check each hour
        for coin in list(book):
            p = book[coin]
            d = data[coin]
            i = idx[coin][t]
            r = d["f"].get(t)
            if r is not None:
                cf = -p["side"] * r * ORDER_USD
                cash += cf
                fund_pnl += cf
            liq_px = p["entry"] * (1 - p["side"] * LIQ_FRAC / lev)
            lo, hi = d["l"][i], d["h"][i]
            if (p["side"] > 0 and lo <= liq_px) or \
                    (p["side"] < 0 and hi >= liq_px):
                close(coin, liq_px * (1 - p["side"] * LIQ_PENALTY), "liq")
                continue
            # [PRE-DECLARED] Farmer-standard hard stop, intrabar-checked —
            # cuts the short-squeeze tail long before the liq price.
            if stop_frac:
                st_px = p["entry"] * (1 - p["side"] * stop_frac)
                if (p["side"] > 0 and lo <= st_px) or \
                        (p["side"] < 0 and hi >= st_px):
                    close(coin, st_px, "stop")
        # daily rebalance
        if (j - start) % REB_H == 0:
            floor_j = j - LOOKBACK_H
            scores = {}
            for coin in coins:
                rs = [data[coin]["f"].get(common[x])
                      for x in range(floor_j, j)]
                rs = [x for x in rs if x is not None]
                if len(rs) >= LOOKBACK_H // 2:
                    scores[coin] = sum(rs) / len(rs)
            if len(scores) >= 2 * K:
                ranked = sorted(scores, key=scores.get)
                want = {c: +1 for c in ranked[:K]}
                want.update({c: -1 for c in ranked[-K:]})
                for coin in list(book):
                    if want.get(coin) != book[coin]["side"]:
                        close(coin, data[coin]["c"][idx[coin][t]], "reb")
                for coin, side in want.items():
                    if coin not in book:
                        px = data[coin]["c"][idx[coin][t]]
                        cash -= slip * ORDER_USD
                        book[coin] = {"side": side, "entry": px}
        u = sum(p["side"] * (data[c]["c"][idx[c][t]] / p["entry"] - 1.0)
                * ORDER_USD for c, p in book.items())
        eq.append(cash + u)
    for coin in list(book):
        close(coin, data[coin]["c"][idx[coin][common[-1]]], "eod")
    eq.append(cash)
    peak = dd = 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, peak - e)
    return dict(ret=100 * cash / margin, fund=100 * fund_pnl / margin,
                dd=100 * dd / margin, trips=trips, liqs=liqs,
                winp=100 * wins / trips if trips else 0)


def main():
    data = load()
    coins = sorted(data.keys())
    sets = [set(d["ts"]) for d in data.values()]
    common = sorted(set.intersection(*sets))
    idx = {}
    for c in coins:
        m = dict(zip(data[c]["ts"], range(len(data[c]["ts"]))))
        idx[c] = {t: m[t] for t in common}
    half = len(common) // 2
    print(f"funding-spread book 72h/K{K}/24h, {len(coins)} coins, "
          f"{len(common)} bars, clip ${ORDER_USD:.0f}/leg gross "
          f"${2*K*ORDER_USD:.0f}\n")
    hdr = (f"{'lev':>4} {'slip':>5} | {'full%':>8} {'h1%':>8} {'h2%':>8} "
           f"{'dd%':>6} {'liqs':>4} {'fund_pp':>8} {'trips':>5} | verdict")
    print(hdr)
    print("-" * len(hdr))
    for label, stop in [("no-stop", None), ("stop10", 0.10)]:
        print(f"\n--- {label} ---")
        for lev in LEVS:
            for s_mult in ([1] if lev == 1 else [1, 2, 3]):
                s = SLIP * s_mult
                rf = simulate(data, coins, common, idx, lev, s, stop)
                r1 = simulate(data, coins, common[:half], idx, lev, s, stop)
                r2 = simulate(data, coins, common[half:], idx, lev, s, stop)
                ok = (r1["ret"] > 0 and r2["ret"] > 0 and rf["liqs"] == 0
                      and r1["liqs"] == 0 and r2["liqs"] == 0
                      and rf["dd"] <= 40)
                print(f"{lev:>4} {s*1e4:>4.0f}b | {rf['ret']:>8.1f} "
                      f"{r1['ret']:>8.1f} {r2['ret']:>8.1f} {rf['dd']:>6.1f} "
                      f"{rf['liqs']:>4} {rf['fund']:>8.1f} {rf['trips']:>5} | "
                      f"{'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
