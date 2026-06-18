#!/usr/bin/env python3
"""
hyperliquid_perps_bot.py
------------------------
Live (testnet) perpetuals trading bot that mirrors the Torin video setup:
  - Connects to the Hyperliquid TESTNET via the official Python SDK.
  - RSI(14) placeholder strategy: long when RSI < 30, short when RSI > 70.
  - Loops every LOOP_SECONDS (default 60s) and logs every decision.
  - Position sizing per trade + a 5% daily loss limit that halts trading.

This is the SAME placeholder logic the video uses. The included backtest
(perps_backtest.py) shows this strategy is NOT profitable on historical BTC/ETH
— treat this purely as a framework to plug a real strategy into, and run it on
TESTNET only.

SETUP (do this yourself — the bot never handles your keys for you):
  1. pip install -r requirements_perps.txt
  2. On Hyperliquid: deposit >= $10 on mainnet, then open the testnet, claim the
     $1,000 mock USDC faucet, and create an API wallet (More -> API).
  3. Copy .env.perps.example to .env.perps and paste your TESTNET API wallet
     private key. NEVER commit or share that key.
  4. python hyperliquid_perps_bot.py            # dry-run by default
     python hyperliquid_perps_bot.py --live     # actually place testnet orders

Safety: defaults to DRY_RUN (no orders sent). Pass --live to send testnet orders.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timezone

import numpy as np

# --------------------------- configuration -------------------------------
COINS = ["BTC", "ETH", "SOL"]     # top perps to trade
RSI_PERIOD = 14
OVERSOLD = 40                    # LOOSENED: was 30, now 40 (more long entries)
OVERBOUGHT = 60                  # LOOSENED: was 70, now 60 (more short entries)
LOOP_SECONDS = 60
CANDLE_INTERVAL = "1h"            # indicator timeframe
ORDER_USD = 50.0                 # notional per position (position sizing)
LEVERAGE = 1                     # keep low; 3x+ liquidated fast in backtest
DAILY_LOSS_LIMIT = 0.05          # 5% — halts trading for the day
LOG_FILE = "perps_bot.log"

DRY_RUN = "--live" not in sys.argv

# --------------------------- logging -------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("perps-bot")


def load_env(path=".env.perps"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def rsi(closes, period=14):
    closes = np.asarray(closes, dtype=float)
    if len(closes) < period + 1:
        return 50.0
    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # Wilder's smoothing
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    for i in range(period, len(delta)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


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

    secret = os.environ.get("HL_API_PRIVATE_KEY", "").strip()
    account_address = os.environ.get("HL_ACCOUNT_ADDRESS", "").strip()
    if not secret:
        log.error("HL_API_PRIVATE_KEY not set. Copy .env.perps.example -> .env.perps "
                  "and add your TESTNET API wallet key.")
        sys.exit(1)

    wallet = eth_account.Account.from_key(secret)
    base_url = constants.TESTNET_API_URL          # TESTNET ONLY
    info = Info(base_url, skip_ws=True)
    exchange = Exchange(wallet, base_url, account_address=account_address or None)

    log.info("=" * 60)
    log.info("Hyperliquid PERPS bot starting | %s | coins=%s | %s",
             "DRY-RUN" if DRY_RUN else "LIVE-TESTNET", COINS,
             f"RSI({RSI_PERIOD}) {OVERSOLD}/{OVERBOUGHT}")
    log.info("base_url=%s  order=$%.0f  lev=%dx  loop=%ds  loss-limit=%.0f%%",
             base_url, ORDER_USD, LEVERAGE, LOOP_SECONDS, DAILY_LOSS_LIMIT * 100)
    log.info("=" * 60)

    def account_value():
        st = info.user_state(account_address or wallet.address)
        return float(st["marginSummary"]["accountValue"])

    try:
        day_start_equity = account_value()
    except Exception as e:
        log.warning("Could not read account value (%s); loss-limit disabled until reachable.", e)
        day_start_equity = None
    cur_day = datetime.now(timezone.utc).date()
    halted_today = False

    while True:
        now = datetime.now(timezone.utc)

        # daily reset of the loss limit
        if now.date() != cur_day:
            cur_day = now.date()
            halted_today = False
            try:
                day_start_equity = account_value()
            except Exception:
                pass

        try:
            equity = account_value()
        except Exception as e:
            log.warning("account value unavailable: %s", e)
            equity = None

        if (not halted_today and equity is not None and day_start_equity
                and equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)):
            log.warning("DAILY LOSS LIMIT HIT (equity %.2f <= %.2f). Halting new trades, "
                        "flattening. No revenge trades.", equity, day_start_equity)
            halted_today = True
            if not DRY_RUN:
                for c in COINS:
                    try:
                        exchange.market_close(c)
                    except Exception as e:
                        log.error("flatten %s failed: %s", c, e)

        if halted_today:
            log.info("halted for today; sleeping.")
            time.sleep(LOOP_SECONDS)
            continue

        # current open positions keyed by coin -> signed size
        try:
            state = info.user_state(account_address or wallet.address)
            pos = {p["position"]["coin"]: float(p["position"]["szi"])
                   for p in state.get("assetPositions", [])}
        except Exception as e:
            log.warning("could not read positions: %s", e)
            pos = {}

        end = int(time.time() * 1000)
        start = end - 60 * 24 * 3600 * 1000      # ~60 days of 1h candles
        for coin in COINS:
            try:
                candles = info.candles_snapshot(coin, CANDLE_INTERVAL, start, end)
                closes = [float(c["c"]) for c in candles]
                price = closes[-1]
                r = rsi(closes, RSI_PERIOD)
            except Exception as e:
                log.error("%s data error: %s", coin, e)
                continue

            held = pos.get(coin, 0.0)
            decision = "HOLD"
            if r < OVERSOLD and held <= 0:
                decision = "OPEN_LONG"
            elif r > OVERBOUGHT and held >= 0:
                decision = "OPEN_SHORT"

            log.info("%-4s price=%.2f RSI=%.1f held=%.4f -> %s",
                     coin, price, r, held, decision)

            if decision == "HOLD" or DRY_RUN:
                continue

            size = round(ORDER_USD * LEVERAGE / price, 4)
            try:
                if decision == "OPEN_LONG":
                    if held < 0:
                        exchange.market_close(coin)
                    exchange.market_open(coin, True, size)
                elif decision == "OPEN_SHORT":
                    if held > 0:
                        exchange.market_close(coin)
                    exchange.market_open(coin, False, size)
                log.info("ORDER SENT %s %s size=%s", decision, coin, size)
            except Exception as e:
                log.error("order failed %s %s: %s", decision, coin, e)

        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")

