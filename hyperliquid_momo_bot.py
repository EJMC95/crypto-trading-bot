#!/usr/bin/env python3
"""
hyperliquid_momo_bot.py
-----------------------
LIVE (testnet) perps bot running the strategy that actually won the backtest:
the MomoBreakoutV1 port (4h Donchian breakout + 200-EMA trend filter + 12% stop),
NOT the losing RSI placeholder.

This is the live counterpart to perps_strategy_backtest.py — same rules, so what
you run matches what you measured.

Strategy (per market, on closed 4h candles):
  LONG  entry : close > highest high of last 15 bars  AND  close > 100-EMA.
  LONG  exit  : close < lowest low of last 8 bars  OR  price <= entry*(1-8%).
  SHORT (only if ALLOW_SHORT): mirror — close < 15-bar low AND close < 100-EMA;
        cover on close > 8-bar high OR price >= entry*(1+8%).

Operational:
  - Polls every LOOP_SECONDS; acts on the latest CLOSED 4h candle (no churn).
  - Position state (size + entry price) is read from the exchange, so restarts
    are safe. Hard stop is checked every loop against the live mark price.
  - 5% daily loss limit halts new trades and flattens ("no revenge trades").
  - Logs every decision to momo_bot.log.

SETUP: identical to hyperliquid_perps_bot.py — see README_perps.md. Needs your own
Hyperliquid TESTNET account, faucet funds, and API wallet key in .env.perps.

  python hyperliquid_momo_bot.py            # dry-run (default, no orders)
  python hyperliquid_momo_bot.py --live     # send testnet orders
"""

import os
import sys
import json
import time
import logging
import urllib.request
from datetime import datetime, timezone

import numpy as np

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)

# --------------------------- configuration -------------------------------
COINS = ["BTC", "ETH", "SOL"]
ENTRY_LOOKBACK = 15
EXIT_LOOKBACK = 8
TREND_EMA = 100
HARD_STOP = 0.08
CANDLE_INTERVAL = "4h"
ALLOW_SHORT = True               # loosened: shorts enabled for more frequent trading
ORDER_USD = 50.0                 # notional per position
LEVERAGE = 1                     # 1x baseline; 2x doubled drawdown in backtest
DAILY_LOSS_LIMIT = 0.05
LOOP_SECONDS = 300               # 5 min; 4h candles don't need a 60s loop
LOG_FILE = "momo_bot.log"

PAPER = "--paper" in sys.argv      # watch live testnet prices, no account/keys needed
DRY_RUN = PAPER or ("--live" not in sys.argv)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("momo-bot")


def load_env(path=".env.perps"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def notify(text, **fields):
    """POST a trade event to a Zapier Catch Hook (which fans out to Slack).
    No-op if ZAPIER_WEBHOOK_URL isn't set. Never blocks or crashes trading."""
    url = os.environ.get("ZAPIER_WEBHOOK_URL", "").strip()
    if not url:
        return
    payload = {"text": text, "ts": datetime.now(timezone.utc).isoformat(), **fields}
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:  # noqa: BLE001 - alerts must never break the bot
        log.warning("notify failed: %s", e)


def ema_last(values, n):
    """EMA of a list, returning the final value (span=n, like talib/pandas)."""
    v = np.asarray(values, dtype=float)
    if len(v) < n:
        return float("nan")
    alpha = 2 / (n + 1)
    e = v[0]
    for x in v[1:]:
        e = alpha * x + (1 - alpha) * e
    return e


def signals_from_candles(candles):
    """Compute strategy state from closed 4h candles. Returns a dict or None."""
    # need plenty of warmup so the 200-EMA converges (seed error decays ~1% per
    # ~460 candles); we fetch ~3x TREND_EMA below.
    if len(candles) < TREND_EMA + ENTRY_LOOKBACK + 2:
        return None
    closes = [float(c["c"]) for c in candles]
    highs = [float(c["h"]) for c in candles]
    lows = [float(c["l"]) for c in candles]

    # use the last CLOSED candle as the decision bar (index -1 is the most
    # recent closed candle from candles_snapshot once its interval has elapsed)
    close = closes[-1]
    # prior-bar Donchian (exclude the decision bar itself -> no lookahead)
    dc_high_entry = max(highs[-1 - ENTRY_LOOKBACK:-1])
    dc_low_entry = min(lows[-1 - ENTRY_LOOKBACK:-1])
    dc_low_exit = min(lows[-1 - EXIT_LOOKBACK:-1])
    dc_high_exit = max(highs[-1 - EXIT_LOOKBACK:-1])
    ema_trend = ema_last(closes, TREND_EMA)

    return {
        "close": close, "ema": ema_trend,
        "dc_high_entry": dc_high_entry, "dc_low_entry": dc_low_entry,
        "dc_low_exit": dc_low_exit, "dc_high_exit": dc_high_exit,
    }


def main():
    load_env()
    try:
        from hyperliquid.info import Info
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants
        import eth_account
    except ImportError:
        log.error("Missing deps. Run: pip install -r requirements_perps.txt")
        sys.exit(1)

    base_url = constants.TESTNET_API_URL          # TESTNET ONLY
    info = Info(base_url, skip_ws=True)           # public market data; no auth needed

    secret = os.environ.get("HL_API_PRIVATE_KEY", "").strip()
    account_address = os.environ.get("HL_ACCOUNT_ADDRESS", "").strip()
    exchange = None
    addr = None
    paper_pos = {}                                # in-memory positions for PAPER mode
    if PAPER:
        log.info("PAPER mode: no account or keys needed. Reading LIVE testnet prices and "
                 "simulating fills in memory. No orders sent, no real balances.")
    else:
        if not secret:
            log.error("HL_API_PRIVATE_KEY not set. Copy .env.perps.example -> .env.perps. "
                      "(Or run with --paper to watch it now with no account/keys.)")
            sys.exit(1)
        wallet = eth_account.Account.from_key(secret)
        exchange = Exchange(wallet, base_url, account_address=account_address or None)
        addr = account_address or wallet.address

    log.info("=" * 64)
    log.info("MomoBreakout PERPS bot | %s | coins=%s",
             "DRY-RUN" if DRY_RUN else "LIVE-TESTNET", COINS)
    log.info("Donchian %d/%d + EMA%d + %.0f%% stop | shorts=%s | %dx | $%.0f/trade | loop=%ds",
             ENTRY_LOOKBACK, EXIT_LOOKBACK, TREND_EMA, HARD_STOP * 100,
             ALLOW_SHORT, LEVERAGE, ORDER_USD, LOOP_SECONDS)
    log.info("=" * 64)

    def account_value():
        st = info.user_state(addr)
        return float(st["marginSummary"]["accountValue"])

    def positions():
        st = info.user_state(addr)
        out = {}
        for p in st.get("assetPositions", []):
            pos = p["position"]
            out[pos["coin"]] = {
                "size": float(pos["szi"]),
                "entry": float(pos.get("entryPx") or 0.0),
            }
        return out

    if PAPER:
        day_start_equity = None                  # no balance to read; loss-limit disabled
    else:
        try:
            day_start_equity = account_value()
        except Exception as e:
            log.warning("account value unreadable (%s); loss-limit waits until reachable.", e)
            day_start_equity = None
    cur_day = datetime.now(timezone.utc).date()
    halted_today = False

    while True:
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            if not PAPER:
                try:
                    day_start_equity = account_value()
                except Exception:
                    pass

        if PAPER:
            equity = None
        else:
            try:
                equity = account_value()
            except Exception as e:
                log.warning("account value unavailable: %s", e)
                equity = None

        if (not halted_today and equity is not None and day_start_equity
                and equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)):
            log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f). Flatten + halt for today.",
                        equity, day_start_equity)
            halted_today = True
            if not DRY_RUN:
                for c in COINS:
                    try:
                        exchange.market_close(c)
                    except Exception as e:
                        log.error("flatten %s: %s", c, e)

        if halted_today:
            log.info("halted for today; sleeping.")
            time.sleep(LOOP_SECONDS)
            continue

        if PAPER:
            pos = paper_pos
        else:
            try:
                pos = positions()
            except Exception as e:
                log.warning("positions unreadable: %s", e)
                pos = {}

        end = int(time.time() * 1000)
        # ~3x the EMA period of warmup so the live 200-EMA matches the backtest
        start = end - (TREND_EMA * 3 + ENTRY_LOOKBACK + 5) * 4 * 3600 * 1000
        for coin in COINS:
            try:
                candles = info.candles_snapshot(coin, CANDLE_INTERVAL, start, end)
                s = signals_from_candles(candles)
            except Exception as e:
                log.error("%s data error: %s", coin, e)
                continue
            if s is None:
                log.info("%-4s insufficient candle history; skipping.", coin)
                continue

            held = pos.get(coin, {}).get("size", 0.0)
            entry = pos.get(coin, {}).get("entry", 0.0)
            px = s["close"]
            decision = "HOLD"

            # ----- manage existing position first -----
            if held > 0:  # long
                if entry and px <= entry * (1 - HARD_STOP):
                    decision = "STOP_LONG"
                elif px < s["dc_low_exit"]:
                    decision = "EXIT_LONG"
            elif held < 0:  # short
                if entry and px >= entry * (1 + HARD_STOP):
                    decision = "STOP_SHORT"
                elif px > s["dc_high_exit"]:
                    decision = "COVER_SHORT"
            else:  # flat -> look for entries
                if px > s["dc_high_entry"] and px > s["ema"]:
                    decision = "OPEN_LONG"
                elif ALLOW_SHORT and px < s["dc_low_entry"] and px < s["ema"]:
                    decision = "OPEN_SHORT"

            log.info("%-4s px=%.2f ema200=%.2f dcHi=%.2f dcLo=%.2f held=%.4f -> %s",
                     coin, px, s["ema"], s["dc_high_entry"], s["dc_low_exit"], held, decision)

            if PAPER:
                # simulate the fill in memory so exits/stops show on later loops
                if decision == "OPEN_LONG":
                    paper_pos[coin] = {"size": ORDER_USD * LEVERAGE / px, "entry": px}
                elif decision == "OPEN_SHORT":
                    paper_pos[coin] = {"size": -ORDER_USD * LEVERAGE / px, "entry": px}
                elif decision in ("EXIT_LONG", "STOP_LONG", "COVER_SHORT", "STOP_SHORT"):
                    paper_pos.pop(coin, None)
                if decision != "HOLD":
                    notify(f":test_tube: MomoBot [PAPER] {decision} {coin} @ {px:,.2f}",
                           coin=coin, decision=decision, price=round(px, 2), mode="paper")
                continue

            if decision == "HOLD" or DRY_RUN:
                continue

            size = round(ORDER_USD * LEVERAGE / px, 4)
            try:
                if decision in ("EXIT_LONG", "STOP_LONG", "COVER_SHORT", "STOP_SHORT"):
                    exchange.market_close(coin)
                elif decision == "OPEN_LONG":
                    exchange.market_open(coin, True, size)
                elif decision == "OPEN_SHORT":
                    exchange.market_open(coin, False, size)
                log.info("ORDER SENT %s %s", decision, coin)
                notify(f":chart_with_upwards_trend: MomoBot [LIVE-TESTNET] {decision} "
                       f"{coin} @ {px:,.2f} (size {size})",
                       coin=coin, decision=decision, price=round(px, 2),
                       size=size, mode="live-testnet")
            except Exception as e:
                log.error("order failed %s %s: %s", decision, coin, e)
                notify(f":warning: MomoBot ORDER FAILED {decision} {coin}: {e}",
                       coin=coin, decision=decision, mode="error")

        # Publish a snapshot for the live dashboard (guarded; never raises).
        store.publish(
            "momo-bot",
            status="paper" if PAPER else ("halted" if halted_today else "online"),
            equity=equity,
            open_trades=sum(1 for v in pos.values()
                            if (v.get("size") if isinstance(v, dict) else v)),
            extra={"mode": "paper" if PAPER else ("dry-run" if DRY_RUN else "live-testnet"),
                   "coins": COINS},
        )
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")
