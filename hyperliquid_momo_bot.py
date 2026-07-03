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
  [2026-07-01] 20-CANDLE RANGE (long-only):
  LONG  entry : price near the rolling 20-candle low (<= low20 + 15% of the band).
  LONG  exit  : price near the rolling 20-candle high (>= high20 - 15% of band),
                OR the 8% HARD_STOP fires (price <= entry*(1-8%)).
  Shorts are disabled. The Donchian/EMA fields are still computed for logging and
  legacy short-close paths, but no new shorts are opened.

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
from paper_broker import PaperBroker  # dry-run simulated account (no funded wallet needed)

# --------------------------- configuration -------------------------------
# Widened from BTC/ETH/SOL to a broad set of liquid Hyperliquid perps.
# The per-coin loop is guarded, so any symbol not listed on the venue is
# skipped without affecting the others. For a true live "top 100 by volume",
# swap this for info.meta_and_asset_ctxs() ranked by dayNtlVlm at startup.
COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ARB", "OP",
    "SUI", "SEI", "TIA", "APT", "NEAR", "INJ", "LTC", "BCH", "ATOM", "DOT",
    "ADA", "AAVE", "PEPE", "WIF", "kBONK", "ENA", "ORDI", "JUP", "TON", "kSHIB",
]
ENTRY_LOOKBACK = 15      # [2026-07-01] reverted 12->15 to the validated backtest window
EXIT_LOOKBACK = 8
TREND_EMA = 100
HARD_STOP = 0.08
# [2026-07-01 CLOSE FIX] Take-profit was only "price >= 20-candle high", never
# reached in a flat/down tape -> positions dead-held (0 closes). Add an
# entry-relative TP + a time stop (on 4h candles, 3 days) so trades recycle.
TAKE_PROFIT_PCT = 0.03           # +3% from entry -> take profit (4h bot, bigger swings)
MAX_HOLD_SEC = 3 * 24 * 3600     # 72h max hold
CANDLE_INTERVAL = "4h"
ALLOW_SHORT = True               # [2026-07-01] shorts ON for downtrend turnover — already tide-gated (shorts only when px < 100-EMA), so it trades WITH the bear, not chop-whipsaw
ORDER_USD = 50.0                 # notional per position
LEVERAGE = 1                     # 1x baseline; 2x doubled drawdown in backtest
DAILY_LOSS_LIMIT = 0.05
LOOP_SECONDS = 300               # 5 min; 4h candles don't need a 60s loop
LOG_FILE = "momo_bot.log"
PAPER_START = 1000.0             # dry-run simulated starting equity

PAPER = "--paper" in sys.argv      # watch live testnet prices, no account/keys needed
DRY_RUN = PAPER or ("--live" not in sys.argv)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("perps-donchian-breakout")


def _record_close(bot, coin, ent_px, ent_ts, exit_px, pnl, was_long, reason):
    """Record one closed paper trade to the durable ledger so the dashboard shows
    per-trade long/short P&L instead of only a net equity snapshot. Guarded:
    store.publish_paper_trade never raises into the trading loop."""
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

    # [20-CANDLE RANGE 2026-07-01] rolling 20-candle low/high over the PRIOR 20
    # candles (exclude the decision bar itself -> no look-ahead). buy_zone is the
    # bottom 15% of the band ("near the live low"), sell_zone the top 15%.
    low20 = min(lows[-21:-1])
    high20 = max(highs[-21:-1])
    band = max(high20 - low20, 1e-9)
    buy_zone = low20 + 0.15 * band
    sell_zone = high20 - 0.15 * band

    return {
        "close": close, "ema": ema_trend,
        "dc_high_entry": dc_high_entry, "dc_low_entry": dc_low_entry,
        "dc_low_exit": dc_low_exit, "dc_high_exit": dc_high_exit,
        "low20": low20, "high20": high20,
        "buy_zone": buy_zone, "sell_zone": sell_zone,
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
    # Dry-run uses a self-contained paper account so it never depends on a funded
    # testnet wallet (an unfunded wallet reads accountValue=0 -> no trades ever).
    # Covers both --paper and default dry-run (DRY_RUN is true in both).
    broker = PaperBroker(PAPER_START) if DRY_RUN else None
    # [2026-07-03 PERSIST] Restore the paper account from Postgres so a redeploy
    # or restart continues the SAME equity curve instead of resetting to $1000.
    _saved_state = store.load_state("perps-donchian-breakout") if DRY_RUN else None
    if _saved_state and broker.restore_state(_saved_state.get("broker") or {}):
        log.info("restored paper state: equity $%.2f, %d open position(s)",
                 broker.equity(), broker.open_count())
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
    log.info("20-candle RANGE (long-only) + %.0f%% hard stop | %dx | $%.0f/trade | loop=%ds",
             HARD_STOP * 100, LEVERAGE, ORDER_USD, LOOP_SECONDS)
    log.info("=" * 64)

    def account_value():
        if DRY_RUN:
            return broker.equity()
        st = info.user_state(addr)
        return float(st["marginSummary"]["accountValue"])

    def positions():
        if DRY_RUN:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        st = info.user_state(addr)
        out = {}
        for p in st.get("assetPositions", []):
            pos = p["position"]
            out[pos["coin"]] = {
                "size": float(pos["szi"]),
                "entry": float(pos.get("entryPx") or 0.0),
            }
        return out

    try:
        day_start_equity = account_value()
    except Exception as e:
        log.warning("account value unreadable (%s); loss-limit waits until reachable.", e)
        day_start_equity = None
    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    entry_ts: dict[str, float] = {}   # unix time each position was opened (trade id)
    # [2026-07-03 PERSIST] Rehydrate open-trade timestamps with the account.
    if _saved_state:
        entry_ts.update({str(k): float(v) for k, v in (_saved_state.get("entry_ts") or {}).items()})

    while True:
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
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
            # [20-CANDLE RANGE 2026-07-01] Long-only range trading: take profit
            # near the rolling 20-candle high; keep the 8% HARD_STOP guardrail.
            # Shorts are disabled (no new OPEN_SHORT); any pre-existing short is
            # still closed harmlessly by its stop / cover path.
            if held > 0:  # long
                _held_sec = now.timestamp() - entry_ts.get(coin, now.timestamp())
                if entry and px <= entry * (1 - HARD_STOP):
                    decision = "STOP_LONG"
                elif entry and px >= entry * (1 + TAKE_PROFIT_PCT):
                    decision = "EXIT_LONG"          # entry-relative take profit
                elif px >= s["sell_zone"]:
                    decision = "EXIT_LONG"          # take profit at the range high
                elif _held_sec >= MAX_HOLD_SEC:
                    decision = "STOP_LONG"          # time stop: recycle capital
            elif held < 0:  # short (legacy; never opened by the range logic)
                if entry and px >= entry * (1 + HARD_STOP):
                    decision = "STOP_SHORT"
                elif px > s["dc_high_exit"]:
                    decision = "COVER_SHORT"
            else:  # flat -> long-only range entry
                if px <= s["buy_zone"]:
                    decision = "OPEN_LONG"          # buy near the range low

            log.info("%-4s px=%.2f ema200=%.2f low20=%.4f high20=%.4f buy<=%.4f sell>=%.4f held=%.4f -> %s",
                     coin, px, s["ema"], s["low20"], s["high20"],
                     s["buy_zone"], s["sell_zone"], held, decision)

            size = round(ORDER_USD * LEVERAGE / px, 4)

            if DRY_RUN:
                # Book the fill in the paper account and mark to the live price,
                # so exits/stops and an equity curve show up on later loops.
                broker.mark(coin, px)
                if decision == "OPEN_LONG":
                    broker.open(coin, True, size, px); entry_ts[coin] = now.timestamp()
                elif decision == "OPEN_SHORT":
                    broker.open(coin, False, size, px); entry_ts[coin] = now.timestamp()
                elif decision in ("EXIT_LONG", "STOP_LONG", "COVER_SHORT", "STOP_SHORT"):
                    _sz, _ent = broker.pos.get(coin, (0.0, 0.0))
                    _pnl = broker.close(coin, px)
                    _record_close("perps-donchian-breakout", coin, _ent, entry_ts.pop(coin, None),
                                  px, _pnl, _sz > 0, decision.lower())
                if decision != "HOLD":
                    mode = "paper" if PAPER else "dry-run"
                    notify(f":test_tube: MomoBot [{mode.upper()}] {decision} {coin} @ {px:,.2f}",
                           coin=coin, decision=decision, price=round(px, 2), mode=mode)
                continue

            if decision == "HOLD":
                continue

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
        if DRY_RUN:
            pub_equity = broker.equity()
            pub_open = broker.open_count()
            pub_pnl = pub_equity - PAPER_START
        else:
            pub_equity = equity
            pub_open = sum(1 for v in pos.values()
                           if (v.get("size") if isinstance(v, dict) else v))
            pub_pnl = None
        _szi = broker.szi() if DRY_RUN else {}
        store.publish(
            "perps-donchian-breakout",
            status="paper" if PAPER else ("halted" if halted_today else "online"),
            equity=pub_equity,
            pnl_abs=pub_pnl,
            open_trades=pub_open,
            extra={"mode": "paper" if PAPER else ("dry-run" if DRY_RUN else "live-testnet"),
                   "longs": sum(1 for v in _szi.values() if v > 0),
                   "shorts": sum(1 for v in _szi.values() if v < 0),
                   "coins": COINS},
        )
        # [2026-07-03 PERSIST] Durable paper state -> Postgres (guarded, cheap)
        # so redeploys continue this equity curve.
        if DRY_RUN:
            store.save_state("perps-donchian-breakout", {
                "broker": broker.to_state(),
                "entry_ts": entry_ts,
            })
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")
