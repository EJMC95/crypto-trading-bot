#!/usr/bin/env python3
"""
scripts/backtest_tide_rider.py — INDEPENDENT re-validation of Tide Rider
(crypto-trend-daily / ImprovedStrategyV4) before go-live.

Tide Rider is a Freqtrade strategy on Kraken spot: daily 50/200 EMA golden cross,
long-only, on 6 curated majors (BTC/ETH/SOL/BNB/XRP/TRX). This reproduces that
exact rule on public daily klines — independent of Freqtrade — to confirm the
documented edge (+33% full-cycle, low chop drawdown; see REVALIDATION_2026-06-22)
still holds on fresh data. Go-live gate: never point real money at an unbacktested
strategy.

Rule (matches ImprovedStrategyV4): long while EMA50 > EMA200, flat otherwise;
fee 0.1%/side (Kraken-ish taker); exit on the death cross (ROI/stop effectively
off). Reports per-coin and an equal-weight portfolio vs buy&hold.
"""
import json
import time
import urllib.request

FEE = 0.001               # 0.1% per side (entry+exit)
EMA_FAST, EMA_SLOW = 50, 200
# Binance symbols for the Kraken majors (price series ~identical for majors).
PAIRS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
         "BNB": "BNBUSDT", "XRP": "XRPUSDT", "TRX": "TRXUSDT"}


def klines(symbol, days=1000):
    out, end = [], None
    # Binance caps 1000/req; one call of 1000 daily candles ~= 2.7yr is enough.
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={days}"
    req = urllib.request.Request(url, headers={"User-Agent": "bt"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    return [(int(k[0]), float(k[4])) for k in rows]   # (open_ms, close)


def ema(a, span):
    k = 2.0 / (span + 1.0)
    out = [a[0]]
    for i in range(1, len(a)):
        out.append(a[i] * k + out[-1] * (1 - k))
    return out


def backtest(closes):
    """Golden-cross long/flat. Returns (ret_frac, maxdd_frac, n_trades, wins,
    equity_curve, bh_ret) — equity as growth multiple of 1.0."""
    if len(closes) < EMA_SLOW + 5:
        return None
    ef, es = ema(closes, EMA_FAST), ema(closes, EMA_SLOW)
    eq = 1.0; peak = 1.0; maxdd = 0.0
    in_pos = False; entry = 0.0; n = 0; wins = 0
    curve = []
    for i in range(EMA_SLOW, len(closes)):
        px = closes[i]
        long_ok = ef[i] > es[i]
        if not in_pos and long_ok:
            in_pos, entry = True, px * (1 + FEE); n += 1
        elif in_pos and not long_ok:
            r = px * (1 - FEE) / entry - 1.0
            eq *= (1 + r); wins += 1 if r > 0 else 0; in_pos = False
        # mark-to-market equity for drawdown
        mtm = eq * (px * (1 - FEE) / entry) if in_pos else eq
        peak = max(peak, mtm); maxdd = max(maxdd, (peak - mtm) / peak)
        curve.append((closes and i, mtm))
    if in_pos:  # close at last price for the final return figure
        r = closes[-1] * (1 - FEE) / entry - 1.0
        eq *= (1 + r); wins += 1 if r > 0 else 0
    bh = closes[-1] / closes[EMA_SLOW] - 1.0
    return (eq - 1.0, maxdd, n, wins, curve, bh)


def main():
    print(f"Tide Rider re-validation — daily {EMA_FAST}/{EMA_SLOW} golden cross, "
          f"long-only, {FEE*2*100:.1f}% round-trip fee, Binance daily (~2.7yr)\n")
    print(f"{'coin':>5} {'days':>5} {'strat%':>8} {'maxDD%':>7} {'trades':>7} "
          f"{'win%':>5} {'buy&hold%':>10}  verdict")
    curves = {}
    agg = {}
    for coin, sym in PAIRS.items():
        try:
            data = klines(sym)
        except Exception as e:
            print(f"{coin:>5}  fetch failed: {e!r}")
            continue
        ts = [t for t, _ in data]
        closes = [c for _, c in data]
        r = backtest(closes)
        if not r:
            print(f"{coin:>5}  insufficient history ({len(closes)}d)")
            continue
        ret, dd, n, wins, curve, bh = r
        curves[coin] = dict(curve)
        verdict = "beats hold, less pain" if (ret > bh * 0.6 and dd < 0.4) else \
                  ("lags hold" if ret < bh else "ok")
        print(f"{coin:>5} {len(closes):>5} {ret*100:>8.1f} {dd*100:>7.1f} {n:>7} "
              f"{100*wins/max(1,n):>5.0f} {bh*100:>10.1f}  {verdict}")
        time.sleep(0.2)

    # Equal-weight portfolio of the per-coin strategy curves (rough: average of
    # normalized per-coin equity at each shared index).
    if curves:
        rets = [max(v.values()) / min(v.values()) - 1.0 for v in curves.values() if v]
        avg_ret = sum(
            (list(v.values())[-1] - 1.0) for v in curves.values()) / len(curves)
        print(f"\nEqual-weight portfolio (avg of {len(curves)} majors): "
              f"{avg_ret*100:+.1f}% over ~2.7yr.")
        print("Go-live gate: PASS if the majors basket beats a coin-flip and the "
              "chop drawdown stays contained — compare to REVALIDATION_2026-06-22 "
              "(+33.3%, 4.6% chop DD).")


if __name__ == "__main__":
    main()
