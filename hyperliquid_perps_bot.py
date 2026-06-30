#!/usr/bin/env python3
"""
hyperliquid_perps_bot.py
------------------------
Live (testnet) perpetuals trading bot that mirrors the Torin video setup:
  - Connects to the Hyperliquid TESTNET via the official Python SDK.
  - RSI(14) mean-reversion, but trend-gated (2026-06-25): long oversold dips only
    while price is ABOVE the 50-EMA, short overbought rips only while BELOW it.
  - Per-trade 3% stop-loss + a 4h per-coin re-entry cooldown to stop fee churn.
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

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)
from paper_broker import PaperBroker  # dry-run simulated account (no funded wallet needed)

# --------------------------- configuration -------------------------------
# Widened from BTC/ETH/SOL to a broad set of liquid Hyperliquid perps.
# Per-coin loop is guarded; unavailable symbols are skipped. For a true live
# "top 100 by volume", rank info.meta_and_asset_ctxs() by dayNtlVlm at startup.
COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ARB", "OP",
    "SUI", "SEI", "TIA", "APT", "NEAR", "INJ", "LTC", "BCH", "ATOM", "DOT",
    "ADA", "AAVE", "PEPE", "WIF", "kBONK", "ENA", "ORDI", "JUP", "TON", "kSHIB",
]
RSI_PERIOD = 14
# REVERTED 45->30 / 55->70 (2026-06-25). The 45/55 relaxation 6x'd the trade
# count and made the bot WORSE in backtest (-93.1% vs -89.8% at 30/70; the chop
# window flipped from +9.4% to -56.6%) — it was pure fee bleed. See
# REVALIDATION_2026-06-22.md "Why the losers lose".
OVERSOLD = 30      # long only when deeply oversold
OVERBOUGHT = 70    # short only when deeply overbought
# TREND FILTER (2026-06-25). Root cause of the structural loss was mean-reversion
# with NO trend filter: it longed falling knives and shorted bull rallies. Now we
# only buy oversold dips that are still ABOVE the trend EMA, and only short
# overbought rips that are BELOW it — i.e. trade WITH the tide.
TREND_EMA = 50                   # EMA period on the 1h candles used as regime gate
# PER-TRADE STOP (2026-06-25). The bot previously had NO stop-loss — only a 5%
# daily ACCOUNT limit — so a single bad position could ride all the way down.
STOP_PCT = 0.03                  # 3% adverse move closes the position
# COOLDOWN (2026-06-25). After closing/opening a coin, wait before re-entering it
# to stop the bot churning the same coin every loop.
REENTRY_COOLDOWN_SEC = 4 * 3600  # 4h between actions on the same coin
LOOP_SECONDS = 60
CANDLE_INTERVAL = "1h"            # indicator timeframe
ORDER_USD = 50.0                 # notional per position (position sizing)
LEVERAGE = 1                     # keep low; 3x+ liquidated fast in backtest
DAILY_LOSS_LIMIT = 0.05          # 5% — halts trading for the day
LOG_FILE = "perps_bot.log"
PAPER_START = 1000.0             # dry-run simulated starting equity

DRY_RUN = "--live" not in sys.argv

# --------------------------- logging -------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("hl-perps-rsi")


def _record_close(bot, coin, ent_px, ent_ts, exit_px, pnl, was_long, reason):
    """Record one closed paper trade to the durable ledger so the dashboard shows
    per-trade long/short P&L — previously only a net equity snapshot was published,
    so we were blind to whether the SHORT side actually earns in a downtrend.
    Guarded: store.publish_paper_trade never raises into the trading loop."""
    pnl_pct = None
    if ent_px:
        pnl_pct = ((exit_px - ent_px) / ent_px) if was_long else ((ent_px - exit_px) / ent_px)
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    store.publish_paper_trade(
        bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=float(pnl), pnl_pct=pnl_pct,
        pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
        reason=("long_" if was_long else "short_") + reason,
    )


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


def ema(closes, period):
    """Last value of an exponential moving average over `closes`."""
    closes = np.asarray(closes, dtype=float)
    if len(closes) == 0:
        return None
    if len(closes) < period:
        return float(closes.mean())
    k = 2.0 / (period + 1.0)
    e = float(closes[0])
    for c in closes[1:]:
        e = c * k + e * (1 - k)
    return e


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

    # Dry-run uses a self-contained paper account so it never depends on a funded
    # testnet wallet (an unfunded wallet reads accountValue=0 -> no trades ever).
    broker = PaperBroker(PAPER_START) if DRY_RUN else None

    def account_value():
        if DRY_RUN:
            return broker.equity()
        st = info.user_state(account_address or wallet.address)
        return float(st["marginSummary"]["accountValue"])

    try:
        day_start_equity = account_value()
    except Exception as e:
        log.warning("Could not read account value (%s); loss-limit disabled until reachable.", e)
        day_start_equity = None
    cur_day = datetime.now(timezone.utc).date()
    halted_today = False

    # Per-trade risk state (2026-06-25): entry price per coin for stop-loss, and
    # the unix time of the last open/close per coin for the re-entry cooldown.
    entries: dict[str, float] = {}
    entry_ts: dict[str, float] = {}   # unix time each position was opened (trade id)
    last_action: dict[str, float] = {}

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
        if DRY_RUN:
            pos = broker.szi()
        else:
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
            ema_trend = ema(closes, TREND_EMA)
            uptrend = ema_trend is not None and price > ema_trend
            downtrend = ema_trend is not None and price < ema_trend
            now_ts = now.timestamp()

            decision = "HOLD"

            # 1) Per-trade stop-loss: close any held position whose adverse move
            #    exceeds STOP_PCT. This is the downside protection the bot never
            #    had — previously only a 5% daily ACCOUNT limit existed, so one
            #    position could ride all the way down.
            entry = entries.get(coin)
            if held != 0 and entry:
                adverse = ((price - entry) / entry) if held > 0 else ((entry - price) / entry)
                if adverse <= -STOP_PCT:
                    decision = "STOP_CLOSE"

            # 2) Entries only WITH the trend, and only after the per-coin cooldown.
            #    Long oversold dips ABOVE the trend EMA; short overbought rips
            #    BELOW it. This is the trend filter that turns "long falling
            #    knives / short rallies" into "trade with the tide".
            if decision == "HOLD":
                cooling = (now_ts - last_action.get(coin, 0.0)) < REENTRY_COOLDOWN_SEC
                if not cooling:
                    if r < OVERSOLD and held <= 0 and uptrend:
                        decision = "OPEN_LONG"
                    elif r > OVERBOUGHT and held >= 0 and downtrend:
                        decision = "OPEN_SHORT"

            log.info("%-4s price=%.2f RSI=%.1f ema%d=%s held=%.4f -> %s",
                     coin, price, r, TREND_EMA,
                     f"{ema_trend:.2f}" if ema_trend is not None else "na",
                     held, decision)

            size = round(ORDER_USD * LEVERAGE / price, 4)

            if DRY_RUN:
                # Book the fill in the paper account and mark to the live price.
                broker.mark(coin, price)
                if decision == "STOP_CLOSE":
                    _sz = broker.pos.get(coin, (0.0,))[0]
                    _pnl = broker.close(coin, price)
                    _record_close("hl-perps-rsi", coin, entries.get(coin),
                                  entry_ts.get(coin), price, _pnl, _sz > 0, "stop")
                    entries.pop(coin, None); entry_ts.pop(coin, None)
                    last_action[coin] = now_ts
                elif decision in ("OPEN_LONG", "OPEN_SHORT"):
                    # If flipping an existing position, realise + record it first.
                    if coin in broker.pos:
                        _sz = broker.pos.get(coin, (0.0,))[0]
                        _pnl = broker.close(coin, price)
                        _record_close("hl-perps-rsi", coin, entries.get(coin),
                                      entry_ts.get(coin), price, _pnl, _sz > 0, "flip")
                    broker.open(coin, decision == "OPEN_LONG", size, price)
                    entries[coin] = price; entry_ts[coin] = now_ts
                    last_action[coin] = now_ts
                continue

            if decision == "HOLD":
                continue

            try:
                if decision == "STOP_CLOSE":
                    exchange.market_close(coin)
                    entries.pop(coin, None)
                    last_action[coin] = now_ts
                    log.info("STOP-LOSS CLOSE %s @ %.2f", coin, price)
                elif decision == "OPEN_LONG":
                    if held < 0:
                        exchange.market_close(coin)
                    exchange.market_open(coin, True, size)
                    entries[coin] = price
                    last_action[coin] = now_ts
                    log.info("ORDER SENT %s %s size=%s", decision, coin, size)
                elif decision == "OPEN_SHORT":
                    if held > 0:
                        exchange.market_close(coin)
                    exchange.market_open(coin, False, size)
                    entries[coin] = price
                    last_action[coin] = now_ts
                    log.info("ORDER SENT %s %s size=%s", decision, coin, size)
            except Exception as e:
                log.error("order failed %s %s: %s", decision, coin, e)

        # Publish a snapshot for the live dashboard (guarded; never raises).
        if DRY_RUN:
            pub_equity = broker.equity()
            pub_open = broker.open_count()
            pub_pnl = pub_equity - PAPER_START
        else:
            pub_equity = equity
            pub_open = sum(1 for v in pos.values() if v)
            pub_pnl = None
        _szi = broker.szi() if DRY_RUN else {}
        store.publish(
            "hl-perps-rsi",
            status="halted" if halted_today else "online",
            equity=pub_equity,
            pnl_abs=pub_pnl,
            open_trades=pub_open,
            extra={"mode": "dry-run" if DRY_RUN else "live-testnet",
                   "longs": sum(1 for v in _szi.values() if v > 0),
                   "shorts": sum(1 for v in _szi.values() if v < 0),
                   "coins": COINS},
        )
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")
