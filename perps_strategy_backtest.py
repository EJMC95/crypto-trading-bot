#!/usr/bin/env python3
"""
perps_strategy_backtest.py
--------------------------
Replaces the losing RSI 30/70 placeholder with a REAL strategy: a perps port of
MomoBreakoutV1 (your validated momentum/breakout swing trader), and asks the only
question that matters — does it beat buy-and-hold?

Strategy (ported from strategies/MomoBreakoutV1.py, native 4h):
  LONG  entry : close breaks above the highest high of the last 30 bars (Donchian)
                AND close > 200-EMA (uptrend filter).
  LONG  exit  : close breaks below the lowest low of the last 15 bars (trailing
                Donchian stop), OR a -12% catastrophe stop.
  Perps adds an optional symmetric SHORT side (only enabled in the long_short
  variant): mirror the rules in a downtrend (close < 30-bar low AND close <
  200-EMA; cover on close > 15-bar high or -12% adverse move).

Execution realism:
  - Signal computed at a bar's close, FILLED at the next bar's open (no lookahead).
  - Intrabar -12% stop and Donchian-exit checks use the bar high/low.
  - Costs: TAKER_FEE + SLIPPAGE per side. Funding NOT modelled.

Data: local Binance 1h feather resampled to 4h (offline, no network).
"""

import os
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

# strategy params (from MomoBreakoutV1 defaults)
ENTRY_LOOKBACK = 30
EXIT_LOOKBACK = 15
TREND_EMA = 200
HARD_STOP = 0.12                 # -12% catastrophe stop

# costs / account
TAKER_FEE = 0.00045
SLIPPAGE = 0.0005
START_EQUITY = 1000.0

MARKETS = [
    ("BTC", "binance/BTC_USDT-1h.feather"),
    ("ETH", "binance/ETH_USDT-1h.feather"),
]
LEVERAGES = [1, 2]
VARIANTS = ["long_only", "long_short"]


def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()


def to_4h(df):
    df = df.set_index("date").sort_index()
    o = df["open"].resample("4h").first()
    h = df["high"].resample("4h").max()
    l = df["low"].resample("4h").min()
    c = df["close"].resample("4h").last()
    v = df["volume"].resample("4h").sum()
    out = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v}).dropna()
    return out.reset_index()


def prep(df):
    df = df.copy()
    df["ema_trend"] = ema(df["close"], TREND_EMA)
    df["dc_high_entry"] = df["high"].rolling(ENTRY_LOOKBACK).max().shift(1)
    df["dc_low_exit"] = df["low"].rolling(EXIT_LOOKBACK).min().shift(1)
    df["dc_low_entry"] = df["low"].rolling(ENTRY_LOOKBACK).min().shift(1)   # for shorts
    df["dc_high_exit"] = df["high"].rolling(EXIT_LOOKBACK).max().shift(1)   # cover shorts
    return df


def backtest(df, leverage, allow_short):
    df = prep(df).reset_index(drop=True)
    equity = START_EQUITY
    peak = START_EQUITY
    max_dd = 0.0

    pos = 0            # +1 long, -1 short, 0 flat
    entry = 0.0
    entry_eq = 0.0
    trades = []
    cost_side = TAKER_FEE + SLIPPAGE

    def close_at(price):
        nonlocal equity, pos, entry, entry_eq
        if pos == 0:
            return
        raw = (price - entry) / entry
        net = raw * pos * leverage - 2 * cost_side * leverage
        pnl = entry_eq * net
        equity += pnl
        trades.append({"dir": "L" if pos == 1 else "S", "ret": net * 100, "pnl": pnl})
        pos, entry, entry_eq = 0, 0.0, 0.0

    for i in range(len(df) - 1):
        row = df.iloc[i]
        nxt_open = df.iloc[i + 1]["open"]
        bar_high = df.iloc[i + 1]["high"]
        bar_low = df.iloc[i + 1]["low"]

        if pd.isna(row["ema_trend"]) or pd.isna(row["dc_high_entry"]):
            continue

        # ---- manage an open position on the NEXT bar (stops/exits intrabar) ----
        if pos == 1:
            stop_px = entry * (1 - HARD_STOP)
            if bar_low <= stop_px:
                close_at(stop_px)
            elif row["close"] < row["dc_low_exit"]:
                close_at(nxt_open)
        elif pos == -1:
            stop_px = entry * (1 + HARD_STOP)
            if bar_high >= stop_px:
                close_at(stop_px)
            elif row["close"] > row["dc_high_exit"]:
                close_at(nxt_open)

        # ---- entries (only if flat) ----
        if pos == 0:
            long_sig = row["close"] > row["dc_high_entry"] and row["close"] > row["ema_trend"]
            short_sig = (allow_short and row["close"] < row["dc_low_entry"]
                         and row["close"] < row["ema_trend"])
            if long_sig:
                pos, entry, entry_eq = 1, nxt_open, equity
            elif short_sig:
                pos, entry, entry_eq = -1, nxt_open, equity

        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    if pos != 0:
        close_at(df.iloc[-1]["close"])

    n = len(trades)
    wins = [t for t in trades if t["ret"] > 0]
    gross_win = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    return {
        "trades": n,
        "win_rate": (len(wins) / n * 100) if n else 0.0,
        "total_ret": (equity / START_EQUITY - 1) * 100,
        "final": equity,
        "max_dd": max_dd * 100,
        "pf": pf,
    }


def main():
    print("=" * 84)
    print("PERPS STRATEGY BACKTEST — MomoBreakoutV1 port (4h Donchian 30/15 + EMA200 + 12% stop)")
    print(f"fee={TAKER_FEE*100:.3f}%/side  slip={SLIPPAGE*100:.3f}%/side  start=${START_EQUITY:.0f}")
    print("=" * 84)

    results = []
    for label, rel in MARKETS:
        path = os.path.join(DATA_DIR, rel)
        if not os.path.exists(path):
            print(f"\n{label}: MISSING {rel}")
            continue
        raw = pd.read_feather(path)[["date", "open", "high", "low", "close", "volume"]].dropna()
        df = to_4h(raw)
        bh = (df.iloc[-1]["close"] / df.iloc[0]["close"] - 1) * 100
        print(f"\n{label}  ({df['date'].min().date()} → {df['date'].max().date()}, "
              f"{len(df)} 4h bars)   BUY & HOLD: {bh:+.1f}%")
        for variant in VARIANTS:
            for lev in LEVERAGES:
                m = backtest(df, lev, allow_short=(variant == "long_short"))
                beat = "✓BEATS B&H" if m["total_ret"] > bh else "  "
                print(f"  {variant:<11} {lev}x | trades={m['trades']:>3} "
                      f"win%={m['win_rate']:4.0f} PF={m['pf']:4.2f} "
                      f"return={m['total_ret']:+8.1f}% maxDD={m['max_dd']:4.0f}% "
                      f"final=${m['final']:8.0f}  {beat}")
                results.append((label, variant, lev, m, bh))

    print("\n" + "-" * 84)
    print("Reference (spot, from MomoBreakoutV1.py header, 0.1% fee):")
    print("  BTC: strat +82.7% vs B&H +122.9% | ETH: strat +125.5% vs B&H -8.4%")
    print("Engine validation: long_only 1x here should land in the same ballpark.")
    print("Funding not modelled. Past performance is not indicative of future results.")


if __name__ == "__main__":
    main()
