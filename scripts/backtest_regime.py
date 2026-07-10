#!/usr/bin/env python3
"""
scripts/backtest_regime.py — does a regime/trend gate give Trail Blazer a REAL
edge? Compares the current strategy (buy any dip to the 20-candle low) against
gated variants that only buy the dip when the trend agrees, and validates
OUT-OF-SAMPLE (rank/choose on the old half, test on the recent half).

Gates tested:
  above_ema200  : enter only if close > 200-EMA (dip within an uptrend)
  ema200_rising : enter only if the 200-EMA slope (3 bars) is up
  both          : both conditions

Gate is the ONLY change; entry zone / exits / slippage are identical to live.
Fetches extra history so the 200-EMA is warm across the whole test window.
"""
import json
import time
import urllib.request
import numpy as np

HARD_STOP = 0.08
TAKE_PROFIT_PCT = 0.03
MAX_HOLD_BARS = 18
SLIP = 0.0005
ORDER_USD = 5.0
COLLATERAL = 65.0
FETCH_DAYS = 300           # extra history for 200-EMA warmup
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ADA", "LTC",
         "DOT", "NEAR", "SUI", "HYPE", "AAVE", "WIF", "JUP", "OP", "ARB", "TIA"]
HL = "https://api.hyperliquid.xyz/info"


def candles(coin):
    start = int((time.time() - FETCH_DAYS * 86400) * 1000)
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin,
                       "interval": "4h", "startTime": start}}).encode()
    req = urllib.request.Request(HL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    return [(float(c["h"]), float(c["l"]), float(c["c"]), int(c["t"])) for c in rows]


def ema(a, span):
    k = 2.0 / (span + 1.0); out = np.empty(len(a)); out[0] = a[0]
    for i in range(1, len(a)):
        out[i] = a[i] * k + out[i - 1] * (1 - k)
    return out


def replay(cs, gate):
    if len(cs) < 210:
        return []
    h = np.array([c[0] for c in cs]); l = np.array([c[1] for c in cs])
    c_ = np.array([c[2] for c in cs]); t = [c[3] for c in cs]
    e200 = ema(c_, 200)
    out = []; pos = None
    for i in range(205, len(cs)):
        low20 = l[i - 21:i - 1].min(); high20 = h[i - 21:i - 1].max()
        band = max(high20 - low20, 1e-9)
        buy_zone = low20 + 0.15 * band; sell_zone = high20 - 0.15 * band
        close = c_[i]
        if pos is None:
            if close <= buy_zone:
                ok = True
                if gate == "above_ema200": ok = close > e200[i]
                elif gate == "loose(-3%)": ok = close > e200[i] * 0.97   # dips up to 3% below trend
                elif gate == "loose(-5%)": ok = close > e200[i] * 0.95
                elif gate == "ema200_rising": ok = e200[i] > e200[i - 3]
                elif gate == "both": ok = close > e200[i] and e200[i] > e200[i - 3]
                if ok:
                    pos = (close * (1 + SLIP), i)
        else:
            ent, ei = pos
            reason = None
            if close <= ent * (1 - HARD_STOP): reason = "stop"
            elif close >= ent * (1 + TAKE_PROFIT_PCT): reason = "tp"
            elif close >= sell_zone: reason = "range_high"
            elif (i - ei) >= MAX_HOLD_BARS: reason = "time"
            if reason:
                out.append((t[i], (close - ent) / ent - SLIP))
                pos = None
    return out


def main():
    data = {}
    for coin in COINS:
        try:
            data[coin] = candles(coin)
        except Exception as e:
            print(f"  {coin}: fetch failed {e!r}")
        time.sleep(0.2)
    now = time.time() * 1000
    w30 = now - 30 * 86400 * 1000
    split = now - 90 * 86400 * 1000     # out-of-sample: old vs recent 90d
    print(f"\n{'gate':>14} {'trades':>7} {'180d%':>8} {'30d%':>7} "
          f"{'OOS-recent%':>12}  note")
    for gate in (None, "above_ema200", "ema200_rising", "both"):
        allt = []
        for coin in data:
            allt += replay(data[coin], gate)
        if not allt:
            continue
        ret180 = sum(r for _, r in allt) * ORDER_USD / COLLATERAL * 100
        ret30 = sum(r for ts, r in allt if ts >= w30) * ORDER_USD / COLLATERAL * 100
        oos = sum(r for ts, r in allt if ts >= split) * ORDER_USD / COLLATERAL * 100
        note = "CURRENT (no gate)" if gate is None else ""
        print(f"{str(gate):>14} {len(allt):>7} {ret180:>8.1f} {ret30:>7.1f} "
              f"{oos:>12.1f}  {note}")


if __name__ == "__main__":
    print("Regime-gate backtest — Trail Blazer, 4h, real candles, 1x")
    main()
