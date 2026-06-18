#!/usr/bin/env python3
"""
perps_backtest.py
-----------------
Backtest of the "Torin video" RSI placeholder strategy, adapted for PERPETUAL
futures (long + short) so we can judge how it would perform before risking a
testnet/live run.

Strategy (mirrors the video's placeholder, extended for perps):
  - Indicator: RSI(14) on hourly closes.
  - Entry long  when RSI crosses *below* 30  (oversold bounce).
  - Entry short when RSI crosses *above* 70  (overbought fade).
  - An opposite signal closes the current position and flips.
  - Risk guard rail (video's "loss limit"): if realised PnL within a single
    UTC day drops more than DAILY_LOSS_LIMIT (5%) below the equity at the start
    of that day, trading halts for the rest of that day ("no revenge trades").

Costs modelled:
  - Taker fee per side (TAKER_FEE), applied on entry and exit.
  - Slippage per side (SLIPPAGE).
  - Funding is NOT modelled (noted in the report).

Data: local Freqtrade feather files under ./data (no network needed).
"""

import os
import sys
import pandas as pd
import numpy as np

# ----------------------------- config ------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

RSI_PERIOD = 14
OVERSOLD = 30
OVERBOUGHT = 70
DAILY_LOSS_LIMIT = 0.05          # 5% — the video's loss limit
TAKER_FEE = 0.00045              # 0.045% per side (typical perp taker)
SLIPPAGE = 0.0005                # 0.05% per side
START_EQUITY = 1000.0            # matches the $1,000 testnet faucet

# markets to test: (label, relative path to 1h feather)
MARKETS = [
    ("BTC", "binance/BTC_USDT-1h.feather"),
    ("ETH", "binance/ETH_USDT-1h.feather"),
]
LEVERAGES = [1, 3]               # compare unlevered vs 3x


# --------------------------- indicators ----------------------------------
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


# --------------------------- backtest core -------------------------------
def backtest(df: pd.DataFrame, leverage: int):
    """Run the long/short RSI strategy on one market. Returns metrics + trades."""
    df = df.copy().reset_index(drop=True)
    df["rsi"] = rsi(df["close"], RSI_PERIOD)
    df["rsi_prev"] = df["rsi"].shift(1)

    equity = START_EQUITY
    peak_equity = START_EQUITY
    max_dd = 0.0

    position = 0          # +1 long, -1 short, 0 flat
    entry_price = 0.0
    entry_equity = 0.0    # equity locked into the position notional base

    trades = []           # list of realised-pnl % per trade (on equity)
    equity_curve = []

    # daily loss-limit tracking
    cur_day = None
    day_start_equity = equity
    halted_today = False

    def close_position(price, ts):
        nonlocal equity, position, entry_price, entry_equity
        if position == 0:
            return
        # gross return of the move in the trade's direction
        raw = (price - entry_price) / entry_price
        gross = raw * position * leverage
        # costs: fee+slippage on both entry and exit, scaled by leverage notional
        cost = 2 * (TAKER_FEE + SLIPPAGE) * leverage
        net = gross - cost
        pnl = entry_equity * net
        equity += pnl
        trades.append({
            "time": ts, "dir": "LONG" if position == 1 else "SHORT",
            "entry": entry_price, "exit": price,
            "ret_pct": net * 100, "pnl": pnl, "equity_after": equity,
        })
        position = 0
        entry_price = 0.0
        entry_equity = 0.0

    for _, row in df.iterrows():
        ts = row["date"]
        price = row["close"]
        r, rp = row["rsi"], row["rsi_prev"]

        # --- daily reset of the loss limit ---
        day = pd.Timestamp(ts).date()
        if day != cur_day:
            cur_day = day
            day_start_equity = equity
            halted_today = False

        # mark-to-market peak / drawdown on realised equity
        peak_equity = max(peak_equity, equity)
        dd = (peak_equity - equity) / peak_equity
        max_dd = max(max_dd, dd)
        equity_curve.append((ts, equity))

        # --- loss-limit check: if today's realised loss > 5%, stop & flatten ---
        if not halted_today and equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT):
            close_position(price, ts)
            halted_today = True
            continue
        if halted_today:
            continue

        if np.isnan(rp):
            continue

        long_signal = rp >= OVERSOLD and r < OVERSOLD       # crossed below 30
        short_signal = rp <= OVERBOUGHT and r > OVERBOUGHT   # crossed above 70

        if long_signal:
            if position == -1:
                close_position(price, ts)
            if position == 0:
                position = 1
                entry_price = price
                entry_equity = equity
        elif short_signal:
            if position == 1:
                close_position(price, ts)
            if position == 0:
                position = -1
                entry_price = price
                entry_equity = equity

    # close any open position at the last price
    if position != 0:
        close_position(df.iloc[-1]["close"], df.iloc[-1]["date"])

    # metrics
    n = len(trades)
    wins = [t for t in trades if t["ret_pct"] > 0]
    win_rate = (len(wins) / n * 100) if n else 0.0
    total_ret = (equity / START_EQUITY - 1) * 100
    rets = np.array([t["ret_pct"] for t in trades]) / 100 if n else np.array([])
    sharpe = (rets.mean() / rets.std() * np.sqrt(n)) if n > 1 and rets.std() > 0 else 0.0

    span_days = (df["date"].max() - df["date"].min()).days or 1

    return {
        "trades": n, "win_rate": win_rate, "total_ret": total_ret,
        "final_equity": equity, "max_dd": max_dd * 100, "sharpe": sharpe,
        "span_days": span_days, "trade_log": trades,
    }


def fmt(m):
    return (f"  trades={m['trades']:>4}  win%={m['win_rate']:5.1f}  "
            f"return={m['total_ret']:8.2f}%  final=${m['final_equity']:9.2f}  "
            f"maxDD={m['max_dd']:5.1f}%  sharpe={m['sharpe']:5.2f}")


def main():
    print("=" * 78)
    print("RSI 30/70 PERPS BACKTEST  (video placeholder strategy, long+short)")
    print(f"RSI({RSI_PERIOD})  fee={TAKER_FEE*100:.3f}%/side  slip={SLIPPAGE*100:.3f}%/side"
          f"  daily loss-limit={DAILY_LOSS_LIMIT*100:.0f}%  start=${START_EQUITY:.0f}")
    print("=" * 78)

    summary = []
    for label, rel in MARKETS:
        path = os.path.join(DATA_DIR, rel)
        if not os.path.exists(path):
            print(f"\n{label}: MISSING {rel} — skipped")
            continue
        df = pd.read_feather(path)
        df = df[["date", "open", "high", "low", "close", "volume"]].dropna()
        print(f"\n{label}  ({df['date'].min().date()} → {df['date'].max().date()}, "
              f"{len(df)} hourly candles)")
        # buy & hold benchmark
        bh = (df.iloc[-1]["close"] / df.iloc[0]["close"] - 1) * 100
        print(f"  buy & hold spot return: {bh:+.2f}%")
        for lev in LEVERAGES:
            m = backtest(df, lev)
            print(f"  [{lev}x]" + fmt(m))
            summary.append((label, lev, m, bh))

    # combined portfolio (equal split across markets) per leverage
    print("\n" + "-" * 78)
    print("PORTFOLIO (equal-weight across markets):")
    for lev in LEVERAGES:
        rows = [s for s in summary if s[1] == lev]
        if not rows:
            continue
        avg_ret = np.mean([r[2]["total_ret"] for r in rows])
        avg_dd = np.mean([r[2]["max_dd"] for r in rows])
        tot_trades = sum(r[2]["trades"] for r in rows)
        avg_win = np.mean([r[2]["win_rate"] for r in rows])
        print(f"  [{lev}x]  avg return={avg_ret:+7.2f}%  avg maxDD={avg_dd:4.1f}%  "
              f"avg win%={avg_win:4.1f}  total trades={tot_trades}")
    print("-" * 78)
    print("Note: funding payments are NOT modelled and would reduce returns on")
    print("positions held through funding intervals. Past performance != future.")


if __name__ == "__main__":
    main()
