#!/usr/bin/env python3
"""
scripts/backtest_leverage.py — leverage sweep for the LIVE Trail Blazer strategy
(the 20-candle range bot, hyperliquid_momo_bot.py), on real 4h candles.

Replays the EXACT live decision logic per coin (no look-ahead — acts on closed
bars, fills at the decision bar's close + slippage), aggregates trades into a
time-ordered equity curve, and reports return / max-drawdown / win-rate /
worst-trade / LIQUIDATIONS at each leverage.

Key structural fact this tests: in the live code `size = order_usd * L / px`,
so notional = order_usd * L and margin = order_usd. Leverage therefore SCALES
per-trade $ P&L and $ drawdown ~linearly — it is a pure risk dial, not a free
lunch — until the -8% hard stop can no longer fire before liquidation
(adverse move >= 1/L), which happens around L >= 12.5. This quantifies that.
"""
import json
import time
import urllib.request
import numpy as np

# Exact live-strategy params (hyperliquid_momo_bot.py)
HARD_STOP = 0.08
TAKE_PROFIT_PCT = 0.03
MAX_HOLD_BARS = 18          # 72h on 4h candles
SLIP = 0.0005              # 5 bps entry+exit slippage; Lighter fees are ZERO
ORDER_USD = 5.0            # live clip
COLLATERAL = 65.0
LEVERAGES = [1, 2, 3, 5, 8, 12, 20]
DAYS = 180
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ADA",
         "LTC", "DOT", "NEAR", "SUI", "HYPE", "AAVE", "WIF", "JUP"]
HL = "https://api.hyperliquid.xyz/info"


def candles(coin):
    start = int((time.time() - DAYS * 86400) * 1000)
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin,
                       "interval": "4h", "startTime": start}}).encode()
    req = urllib.request.Request(HL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    return [(float(c["o"]), float(c["h"]), float(c["l"]), float(c["c"]), int(c["t"])) for c in rows]


def trades_for(coin):
    """Replay the live range strategy on one coin. Returns list of
    (exit_ts, ret_frac, reason, worst_adverse_frac) per closed trade — leverage
    applied later so we sweep without re-simulating."""
    cs = candles(coin)
    if len(cs) < 25:
        return []
    o = np.array([c[0] for c in cs]); h = np.array([c[1] for c in cs])
    l = np.array([c[2] for c in cs]); c_ = np.array([c[3] for c in cs]); t = [c[4] for c in cs]
    out = []
    pos = None  # (entry_px, entry_i)
    for i in range(21, len(cs)):
        low20 = l[i - 21:i - 1].min(); high20 = h[i - 21:i - 1].max()
        band = max(high20 - low20, 1e-9)
        buy_zone = low20 + 0.15 * band; sell_zone = high20 - 0.15 * band
        close = c_[i]
        if pos is None:
            if close <= buy_zone:
                pos = (close * (1 + SLIP), i)   # fill at close + slippage
        else:
            ent, ei = pos
            worst = (l[i] - ent) / ent       # intrabar low — for liquidation only
            # The live bot acts on the CLOSED 4h candle and checks the CLOSE
            # against every exit — a wick that recovers by close does NOT stop it.
            reason = None
            if close <= ent * (1 - HARD_STOP):
                reason = "stop"
            elif close >= ent * (1 + TAKE_PROFIT_PCT):
                reason = "tp"
            elif close >= sell_zone:
                reason = "range_high"
            elif (i - ei) >= MAX_HOLD_BARS:
                reason = "time"
            if reason:
                ret = (close - ent) / ent - SLIP   # realized on the actual close
                out.append((t[i], ret, reason, worst))
                pos = None
    return out


def sweep():
    all_tr = []
    for coin in COINS:
        try:
            tr = trades_for(coin)
            all_tr += [(coin, *x) for x in tr]
            print(f"  {coin}: {len(tr)} trades")
        except Exception as e:
            print(f"  {coin}: fetch failed ({e!r})")
        time.sleep(0.25)
    all_tr.sort(key=lambda x: x[1])   # by exit time -> equity curve
    print(f"\nTotal trades: {len(all_tr)}  (over ~{DAYS}d, {len(COINS)} coins)\n")
    print(f"{'lev':>4} {'ret%':>8} {'maxDD%':>8} {'win%':>6} {'worst$':>8} "
          f"{'liq':>4} {'ret/DD':>7}  note")
    base = None
    for L in LEVERAGES:
        notional = ORDER_USD * L
        eq = COLLATERAL; peak = eq; maxdd = 0.0; wins = 0; worst = 0.0; liq = 0
        for (_coin, _ts, ret, _reason, adverse) in all_tr:
            # liquidation: adverse move eats the whole margin before the 8% stop
            # can act (only possible when 1/L < HARD_STOP, i.e. L > 12.5)
            if adverse <= -1.0 / L and (1.0 / L) < HARD_STOP:
                pnl = -ORDER_USD                 # lose the full margin
                liq += 1
            else:
                pnl = ret * notional             # leverage scales $ P&L
            eq += pnl
            wins += 1 if pnl > 0 else 0
            worst = min(worst, pnl)
            peak = max(peak, eq); maxdd = max(maxdd, (peak - eq) / peak)
        retpct = (eq - COLLATERAL) / COLLATERAL * 100
        r_dd = (retpct / (maxdd * 100)) if maxdd > 0 else float("inf")
        note = "LIQUIDATIONS" if liq else ("baseline" if L == 1 else "")
        print(f"{L:>4} {retpct:>8.1f} {maxdd*100:>8.1f} "
              f"{100*wins/len(all_tr):>6.0f} {worst:>8.2f} {liq:>4} {r_dd:>7.2f}  {note}")


if __name__ == "__main__":
    print(f"Leverage sweep — live Trail Blazer strategy, {DAYS}d 4h candles, "
          f"${ORDER_USD} clip, ${COLLATERAL} collateral\n")
    sweep()
