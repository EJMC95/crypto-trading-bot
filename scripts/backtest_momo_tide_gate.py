#!/usr/bin/env python3
"""Backtest: MomoBreakoutV1 rules on Kraken 4h data, with/without market-regime gates.

Rules replicated from user_data/strategies/MomoBreakoutV1.py:
  entry: close > dc_high(20, shift1) AND close > EMA200  -> enter next bar open
  exit:  close < dc_low(15, shift1)                      -> exit next bar open
  stop:  -12% catastrophe (intrabar low check, exit at stop price)
  fee:   0.26%/side (Kraken taker)

Gate variants (evaluated at the SIGNAL bar):
  A baseline          - as-is
  B btc_tide          - require BTC close > BTC EMA200(4h)
  C breadth50         - require >=50% of majors above own EMA200(4h)
  D btc_tide_halfsize - entries allowed, but 0.5x stake when gate B fails
"""
import json, os, math
import pandas as pd, numpy as np

SP = os.path.dirname(os.path.abspath(__file__)) + "/ohlc"
MAJORS = ["XBTUSD","ETHUSD","SOLUSD","XRPUSD","ADAUSD","DOTUSD","AVAXUSD","LINKUSD",
          "LTCUSD","ATOMUSD","NEARUSD","TRXUSD","DOGEUSD","ALGOUSD","AAVEUSD"]
V7 = MAJORS + ["BCHUSD","XLMUSD","UNIUSD","ETCUSD","FILUSD","APTUSD","SUIUSD","INJUSD",
               "OPUSD","TIAUSD","ARBUSD","WIFUSD","BONKUSD","PEPEUSD"]
FEE = 0.0026
STOP = -0.12

def load(pair, tf="4h"):
    p = f"{SP}/{pair}_{tf}.json"
    if not os.path.exists(p): return None
    rows = json.load(open(p))
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","vwap","vol","cnt"])
    for c in ["open","high","low","close","vol"]: df[c] = df[c].astype(float)
    df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    return df.set_index("ts")

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

# --- market context -------------------------------------------------------
btc = load("XBTUSD"); btc["ema200"] = ema(btc["close"], 200)
btc_up = (btc["close"] > btc["ema200"])
breadth = pd.DataFrame(index=btc.index)
for m in MAJORS:
    d = load(m)
    if d is None: continue
    d["ema200"] = ema(d["close"], 200)
    breadth[m] = (d["close"] > d["ema200"]).reindex(btc.index)
breadth_frac = breadth.mean(axis=1)

def run(gate):  # gate: None | 'btc' | 'breadth' | ('half','btc')
    trades = []
    for pair in V7:
        df = load(pair)
        if df is None or len(df) < 260: continue
        df["ema200"] = ema(df["close"], 200)
        df["dc_high"] = df["high"].rolling(20).max().shift(1)
        df["dc_low"]  = df["low"].rolling(15).min().shift(1)
        df["btc_up"] = btc_up.reindex(df.index).ffill()
        df["breadth"] = breadth_frac.reindex(df.index).ffill()
        pos = None
        rows = df.reset_index().to_dict("records")
        for i in range(210, len(rows)-1):
            r, nxt = rows[i], rows[i+1]
            if pos is None:
                sig = r["close"] > r["dc_high"] and r["close"] > r["ema200"]
                if not sig: continue
                g_ok = True
                if gate == "btc": g_ok = bool(r["btc_up"])
                elif gate == "breadth": g_ok = (r["breadth"] or 0) >= 0.5
                size = 1.0
                if isinstance(gate, tuple) and gate[0] == "half":
                    size = 1.0 if bool(r["btc_up"]) else 0.5
                elif not g_ok:
                    continue
                pos = {"entry": nxt["open"], "ts": nxt["ts"], "size": size, "pair": pair}
            else:
                stop_price = pos["entry"] * (1 + STOP)
                if r["low"] <= stop_price:
                    ret = (stop_price/pos["entry"]) * (1-FEE)**2 - 1
                    trades.append({**pos, "exit_ts": r["ts"], "ret": ret, "reason": "stop"})
                    pos = None; continue
                if r["close"] < r["dc_low"]:
                    ret = (nxt["open"]/pos["entry"]) * (1-FEE)**2 - 1
                    trades.append({**pos, "exit_ts": nxt["ts"], "ret": ret, "reason": "dc_exit"})
                    pos = None
        # open positions marked to last close
        if pos is not None:
            ret = (rows[-1]["close"]/pos["entry"]) * (1-FEE)**2 - 1
            trades.append({**pos, "exit_ts": rows[-1]["ts"], "ret": ret, "reason": "open_mtm"})
    return pd.DataFrame(trades)

def stats(t, label):
    if t.empty:
        print(f"{label:22} no trades"); return
    t = t.copy(); t["w_ret"] = t["ret"] * t["size"]
    n = len(t); w = (t["ret"] > 0).sum()
    gp = t.loc[t["w_ret"]>0, "w_ret"].sum(); gl = -t.loc[t["w_ret"]<0, "w_ret"].sum()
    pf = gp/gl if gl > 0 else math.inf
    print(f"{label:22} n={n:3} win={100*w/n:4.1f}% sum_ret={100*t['w_ret'].sum():+7.1f}% "
          f"avg={100*t['w_ret'].mean():+5.2f}% PF={pf:4.2f} stops={(t['reason']=='stop').sum()} open={(t['reason']=='open_mtm').sum()}")
    return t

span = f"{btc.index[210].date()} -> {btc.index[-1].date()}"
print(f"Window (post-warmup): {span}  | fee 0.26%/side | 30 v7 pairs\n")
a = stats(run(None),            "A baseline")
b = stats(run("btc"),           "B btc_tide gate")
c = stats(run("breadth"),       "C breadth>=50% gate")
d = stats(run(("half","btc")),  "D half-size off-tide")
# recent-window check: does baseline reproduce the live July bleed?
if a is not None:
    rec = a[a["ts"] >= "2026-07-01"]
    print(f"\nbaseline Jul-1..14 only: n={len(rec)} win={100*(rec['ret']>0).mean() if len(rec) else 0:.0f}% sum={100*rec['ret'].sum():+.1f}%")
    recb = b[b["ts"] >= "2026-07-01"] if b is not None else None
    print(f"btc_tide Jul-1..14 only: n={len(recb)} sum={100*recb['ret'].sum():+.1f}%" if recb is not None and len(recb) else "btc_tide Jul-1..14: no trades")
