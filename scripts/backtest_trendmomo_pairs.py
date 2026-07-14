#!/usr/bin/env python3
"""Backtest: TrendMomoV1 rules per-pair on Kraken 1d data (mum's 15-pair whitelist).

Rules from user_data/strategies/TrendMomoV1.py:
  entry: sma10 > sma40 AND close > sma40   -> enter next open
  exit:  sma10 crosses below sma40         -> exit next open
  stop:  -15% intrabar
  fee:   0.26%/side
"""
import json, os, math
import pandas as pd

SP = os.path.dirname(os.path.abspath(__file__)) + "/ohlc"
PAIRS = ["XBTUSD","ETHUSD","SOLUSD","XRPUSD","ADAUSD","DOTUSD","AVAXUSD","LINKUSD",
         "LTCUSD","ATOMUSD","NEARUSD","TRXUSD","DOGEUSD","ALGOUSD","AAVEUSD"]
FEE = 0.0026
STOP = -0.15

def load(pair):
    rows = json.load(open(f"{SP}/{pair}_1d.json"))
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","vwap","vol","cnt"])
    for c in ["open","high","low","close"]: df[c] = df[c].astype(float)
    df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    return df

print(f"{'pair':9} {'n':>3} {'win%':>5} {'sum_ret%':>9} {'PF':>5}  window")
tot = []
for pair in PAIRS:
    df = load(pair)
    df["sma_f"] = df["close"].rolling(10).mean()
    df["sma_s"] = df["close"].rolling(40).mean()
    rows = df.to_dict("records")
    pos, trades = None, []
    for i in range(45, len(rows)-1):
        r, nxt = rows[i], rows[i+1]
        if pos is None:
            if r["sma_f"] > r["sma_s"] and r["close"] > r["sma_s"]:
                pos = {"entry": nxt["open"]}
        else:
            stop_price = pos["entry"] * (1 + STOP)
            if r["low"] <= stop_price:
                trades.append((stop_price/pos["entry"]) * (1-FEE)**2 - 1); pos = None; continue
            prev = rows[i-1]
            if r["sma_f"] < r["sma_s"] and prev["sma_f"] >= prev["sma_s"]:
                trades.append((nxt["open"]/pos["entry"]) * (1-FEE)**2 - 1); pos = None
    if pos is not None:
        trades.append((rows[-1]["close"]/pos["entry"]) * (1-FEE)**2 - 1)
    n = len(trades); w = sum(1 for t in trades if t > 0)
    gp = sum(t for t in trades if t > 0); gl = -sum(t for t in trades if t < 0)
    pf = gp/gl if gl > 0 else math.inf
    s = 100*sum(trades)
    tot.append((pair, s, n))
    print(f"{pair:9} {n:3} {100*w/max(1,n):5.1f} {s:+9.1f} {pf:5.2f}  {df['ts'].iloc[0].date()}->{df['ts'].iloc[-1].date()}")
pos_pairs = [p for p,s,n in tot if s > 0]
print(f"\nsum over all 15: {sum(s for _,s,_ in tot):+.1f}% | positive pairs: {pos_pairs}")
print(f"BTC+ETH only:    {sum(s for p,s,_ in tot if p in ('XBTUSD','ETHUSD')):+.1f}%")
