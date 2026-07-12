#!/usr/bin/env python3
"""
scripts/backtest_breakout_perp.py — GO-SHADOW GATE for 🚀 Breakout Hunter on
LIGHTER ("everyone on the same page", 12 Jul 2026).

MomoBreakoutV1 is the ONLY surviving spot core that is POSITIVE on the 12-Jul
tagged replay (+$202 / +20% over 3.5y Binance; breakout leg, 603 trades). To
run it as a Lighter 1x LONG PERP twin (like Tide Rider's) the funding drag
must be quantified first — breakouts hold ~6 days through exactly the hot
uptrends when longs PAY funding (the Tide Rider precedent cost -13pp).

SIGNAL (exact live strategy, defaults from user_data/strategies/
MomoBreakoutV1.py — entry_lookback 20, exit_lookback 15, trend EMA 200,
stop -12%, no ROI ladder):
  enter LONG on a closed 4h bar: close > max(high of prior 20 bars)
                                 AND close > EMA200(4h);
  exit on close < min(low of prior 15 bars), or intrabar -12% hard stop.

TWO WINDOWS, both with real funding:
  A: ~1000d Binance 4h klines (fetched, cached) x DAILY HL funding from
     scripts/.tiderider_scanner_cache.json — 19 Lighter-listed coins;
  B: 150d, resampled 4h from scripts/.dirfund_cache.json (hourly OHLC +
     hourly funding, 25 Lighter-listed coins) — the recent-regime check.

GATE: basket perp return (spot minus funding paid) POSITIVE IN BOTH HALVES
of BOTH windows at 5bps/side; drag reported honestly; 15bps stress on top.

VERDICT (12 Jul 2026): FAIL — no Lighter twin; do NOT re-test.
  Window A (1000d, 19 coins): spot +74.6% full BUT h1 +71.6% / h2 -27.0% —
  the entire edge is the 2023-24 bull half; funding drag another 25.3pp.
  Window B (150d, 25 coins): spot -20.7%, h1 -19.4% — the recent regime is
  hostile to 4h breakouts across the whole Lighter universe.
  IMPLICATION beyond the twin: the spot bot's "+20% positive core" from the
  12-Jul tagged replay was a FULL-WINDOW number — split in halves it is
  front-loaded regime dependence (the Trail Blazer failure shape). The spot
  Breakout Hunter's slot is now flagged for the same retire-or-keep decision
  as the day trader; its recent-half record does not clear the bar that
  retired its siblings.

Usage:  python3 scripts/backtest_breakout_perp.py
"""
import json
import os
import sys
import time
import urllib.request

CACHE = os.path.join(os.path.dirname(__file__), ".breakout_perp_cache.json")
SCANNER = os.path.join(os.path.dirname(__file__), ".tiderider_scanner_cache.json")
DIRFUND = os.path.join(os.path.dirname(__file__), ".dirfund_cache.json")

COINS_A = ["BTC", "ETH", "SOL", "BNB", "XRP", "TRX", "DOGE", "ADA", "AVAX",
           "LINK", "DOT", "LTC", "NEAR", "APT", "ARB", "OP", "SUI", "TIA",
           "AAVE"]
DAYS_A = 1000
ENTRY_N, EXIT_N, EMA_N = 20, 15, 200
STOP = 0.12
SLIP = 0.0005          # per side; Lighter fee is zero
CLIP = 20.0
BARS_H = 4


def binance_4h(sym, days):
    out = []
    end = int(time.time() * 1000)
    start = end - days * 86400000
    cur = start
    while cur < end:
        url = (f"https://api.binance.com/api/v3/klines?symbol={sym}USDT"
               f"&interval=4h&startTime={cur}&limit=1000")
        rows = json.loads(urllib.request.urlopen(url, timeout=30).read())
        if not rows:
            break
        for r in rows:
            out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                        float(r[4])])
        cur = rows[-1][0] + 1
        time.sleep(0.15)
    return out


def load_a():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    data = {}
    for c in COINS_A:
        try:
            data[c] = binance_4h(c, DAYS_A)
            print(f"  fetched {c}: {len(data[c])} bars")
        except Exception as e:  # noqa: BLE001
            print(f"  {c} fetch failed: {e}")
    json.dump(data, open(CACHE, "w"))
    return data


def ema(vals, span):
    k = 2.0 / (span + 1.0)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(out[-1] + k * (v - out[-1]))
    return out


def run_coin(bars, fund_at, slip=SLIP):
    """bars: [[ts,o,h,l,c]]; fund_at(ts_ms_start, ts_ms_end, notional) -> drag $.
    Returns (spot_pnl, perp_pnl, trades, wins) on CLIP notional, long-only."""
    if len(bars) < EMA_N + ENTRY_N + 5:
        return 0.0, 0.0, 0, 0
    closes = [b[4] for b in bars]
    e200 = ema(closes, EMA_N)
    spot = perp = 0.0
    trades = wins = 0
    pos = None
    for i in range(max(ENTRY_N, EXIT_N) + 1, len(bars)):
        ts, o, h, l, c = bars[i]
        if pos is None:
            hh = max(b[2] for b in bars[i - ENTRY_N:i])
            if c > hh and c > e200[i]:
                pos = {"entry": c * (1 + slip), "ts": ts}
            continue
        # intrabar hard stop first (pessimistic)
        stop_px = pos["entry"] * (1 - STOP)
        exit_px = None
        if l <= stop_px:
            exit_px = stop_px
        else:
            ll = min(b[3] for b in bars[i - EXIT_N:i])
            if c < ll:
                exit_px = c
        if exit_px is not None:
            exit_px *= (1 - slip)
            pnl = (exit_px / pos["entry"] - 1.0) * CLIP
            drag = fund_at(pos["ts"], ts, CLIP)
            spot += pnl
            perp += pnl - drag
            trades += 1
            wins += 1 if pnl - drag > 0 else 0
            pos = None
    if pos is not None:
        ts, _, _, _, c = bars[-1]
        pnl = (c * (1 - slip) / pos["entry"] - 1.0) * CLIP
        drag = fund_at(pos["ts"], ts, CLIP)
        spot += pnl
        perp += pnl - drag
        trades += 1
        wins += 1 if pnl - drag > 0 else 0
    return spot, perp, trades, wins


def report(name, coin_bars, mk_fund, slip=SLIP):
    """coin_bars: {coin: bars}. Prints basket table; returns halves dict."""
    out = {}
    for label, frac in (("full", (0, 1)), ("h1", (0, 0.5)), ("h2", (0.5, 1))):
        s_tot = p_tot = tr_tot = w_tot = 0.0
        for coin, bars in coin_bars.items():
            a, b = int(len(bars) * frac[0]), int(len(bars) * frac[1])
            s, p, tr, w = run_coin(bars[a:b], mk_fund(coin), slip)
            s_tot += s
            p_tot += p
            tr_tot += tr
            w_tot += w
        cap = len(coin_bars) * CLIP
        out[label] = dict(spot=100 * s_tot / cap, perp=100 * p_tot / cap,
                          trades=int(tr_tot),
                          winp=100 * w_tot / tr_tot if tr_tot else 0)
    r = out
    print(f"  {name}: spot {r['full']['spot']:+7.1f}%  perp "
          f"{r['full']['perp']:+7.1f}%  (drag "
          f"{r['full']['spot']-r['full']['perp']:.1f}pp)  "
          f"h1 {r['h1']['perp']:+6.1f}%  h2 {r['h2']['perp']:+6.1f}%  "
          f"trades {r['full']['trades']}  win {r['full']['winp']:.0f}%")
    return out


def main():
    # ---- window A: 1000d Binance 4h + daily HL funding ----
    print("window A: ~1000d, 19 Lighter-listed coins, 4h bars, daily funding")
    bars_a = load_a()
    sc = json.load(open(SCANNER))

    def mk_fund_a(coin):
        f = {int(t): v for t, v in sc.get(coin, {}).get("f", {}).items()}

        def fund_at(ts0, ts1, notional):
            d0, d1 = ts0 // 86400000 * 86400000, ts1 // 86400000 * 86400000
            drag = 0.0
            d = d0
            while d <= d1:
                drag += f.get(d, 0.0) * notional
                d += 86400000
            return drag
        return fund_at

    ra = report("A(1000d)", {c: b for c, b in bars_a.items() if b}, mk_fund_a)

    # ---- window B: 150d dirfund cache resampled to 4h + hourly funding ----
    print("\nwindow B: 150d, 25 Lighter-listed coins (dirfund cache), 4h bars")
    raw = json.load(open(DIRFUND))
    skip = {"INJ", "RUNE", "STX", "GALA", "W"}
    bars_b, funds_b = {}, {}
    for coin, d in raw.items():
        if coin in skip:
            continue
        ks = sorted((int(t), v) for t, v in d["k"].items())
        rb = []
        for i in range(0, len(ks) - 3, BARS_H):
            chunk = ks[i:i + BARS_H]
            rb.append([chunk[0][0], chunk[0][1][0],
                       max(x[1][1] for x in chunk),
                       min(x[1][2] for x in chunk), chunk[-1][1][3]])
        bars_b[coin] = rb
        funds_b[coin] = {int(int(t) // 3600000 * 3600000): v
                         for t, v in d["f"].items()}

    def mk_fund_b(coin):
        f = funds_b[coin]

        def fund_at(ts0, ts1, notional):
            drag = 0.0
            t = ts0 // 3600000 * 3600000
            while t <= ts1:
                drag += f.get(t, 0.0) * notional
                t += 3600000
            return drag
        return fund_at

    rb_ = report("B(150d) ", bars_b, mk_fund_b)
    print("\n  B stress 15bps/side:")
    rs = report("B(stress)", bars_b, mk_fund_b, slip=0.0015)

    ok = all(r[h]["perp"] > 0 for r in (ra, rb_) for h in ("h1", "h2")) \
        and rs["full"]["perp"] > 0
    verdict = "PASS — perp positive in both halves of both windows" if ok \
        else "FAIL"
    print("\nGATE: " + verdict)


if __name__ == "__main__":
    main()
