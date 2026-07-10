#!/usr/bin/env python3
"""
hyperliquid_perps_bot.py
------------------------
Live (testnet) perpetuals trading bot that mirrors the Torin video setup:
  - Connects to the Hyperliquid TESTNET via the official Python SDK.
  - [2026-07-01] 20-CANDLE RANGE strategy (long-only): buy when price is near the
    rolling 20-candle low (bottom 15% of the band), take profit when price reaches
    the rolling 20-candle high (top 15%). Shorts are disabled. RSI/EMA are still
    computed for logging but no longer drive the decision.
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
from venues import venue_context  # [2026-07-09 LIGHTER GATE-0] venue abstraction

# --------------------------- configuration -------------------------------
# Widened from BTC/ETH/SOL to a broad set of liquid Hyperliquid perps.
# Per-coin loop is guarded; unavailable symbols are skipped. For a true live
# "top 100 by volume", rank info.meta_and_asset_ctxs() by dayNtlVlm at startup.
COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ARB", "OP",
    "SUI", "SEI", "TIA", "APT", "NEAR", "INJ", "LTC", "BCH", "ATOM", "DOT",
    "ADA", "AAVE", "PEPE", "WIF", "kBONK", "ENA", "ORDI", "JUP", "TON", "kSHIB",
    # [2026-07-07 COVERAGE] HL top-30 liquidity the web lacked: HYPE was the
    # #4 perp by 24h notional ($359M, SOL-tier) with zero fleet coverage.
    "HYPE", "ZEC", "TAO",
]
RSI_PERIOD = 14
# REVERTED 45->30 / 55->70 (2026-06-25). The 45/55 relaxation 6x'd the trade
# count and made the bot WORSE in backtest (-93.1% vs -89.8% at 30/70; the chop
# window flipped from +9.4% to -56.6%) — it was pure fee bleed. See
# REVALIDATION_2026-06-22.md "Why the losers lose".
OVERSOLD = 30      # long only when deeply oversold (kept strict — longs stay rare in a bear)
OVERBOUGHT = 60    # [2026-07-01] 70->60: short rallies in a downtrend for turnover. Still tide-gated (shorts only fire when price is BELOW the 50-EMA), with 3% stop + 4h cooldown to limit fee churn.
# TREND FILTER (2026-06-25). Root cause of the structural loss was mean-reversion
# with NO trend filter: it longed falling knives and shorted bull rallies. Now we
# only buy oversold dips that are still ABOVE the trend EMA, and only short
# overbought rips that are BELOW it — i.e. trade WITH the tide.
TREND_EMA = 50                   # EMA period on the 1h candles used as regime gate
# PER-TRADE STOP (2026-06-25). The bot previously had NO stop-loss — only a 5%
# daily ACCOUNT limit — so a single bad position could ride all the way down.
STOP_PCT = 0.03                  # 3% adverse move closes the position
# [2026-07-01 CLOSE FIX] The only take-profit was "price >= 20-candle high" which,
# after buying near the low in a flat/down tape, is never reached — so positions
# sat open indefinitely (0 closes). This entry-relative TP guarantees a close on
# any real bounce and clears the ~0.05-0.09% perp round-trip fee with wide margin.
TAKE_PROFIT_PCT = 0.02           # +2% from entry -> take profit
# Hard time stop: close anything held longer than this so capital recycles instead
# of dead-holding a position that neither hits TP nor the stop.
MAX_HOLD_SEC = 24 * 3600         # 24h max hold
# COOLDOWN (2026-06-25). After closing/opening a coin, wait before re-entering it
# to stop the bot churning the same coin every loop.
REENTRY_COOLDOWN_SEC = 4 * 3600  # 4h between actions on the same coin
LOOP_SECONDS = 60
CANDLE_INTERVAL = "1h"            # indicator timeframe
ORDER_USD = 50.0                 # notional per position (position sizing)
# [2026-07-05 CONCENTRATION CAP] The bot had NO global position limit — only a
# per-coin 4h cooldown — so a single market-wide dip let it open 14 concurrent
# longs ($700 = 70% of the $1,000 book) in one correlated direction, then give
# back ~$6 of a +$17 gain. Cap total open positions and the per-loop open rate.
# 6 x $50 = $300 = 30% of book; 4h per-coin cooldown still spaces re-entries.
MAX_OPEN_POSITIONS = 6           # global cap on concurrent open positions
MAX_NEW_PER_LOOP = 2             # smooth one-loop bursts into a correlated dip
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
log = logging.getLogger("perps-rsi-meanrev")


def _record_close(bot, coin, ent_px, ent_ts, exit_px, pnl, was_long, reason,
                  venue=None, shadow=None):
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
        venue=venue, shadow=shadow,
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
    # [2026-07-09 LIGHTER GATE-0] Venue plumbing (HL info/exchange, Lighter
    # client, paper vs shadow broker, kill switch, notional rails) moved to
    # venues/. VENUE unset -> hl_paper -> exactly the pre-refactor behaviour:
    # HL testnet market data + PaperBroker fills. NOTE: the old code exited
    # without HL_API_PRIVATE_KEY even in dry-run (it built an Exchange it
    # never used); dry-run now runs keyless, same as the momo bot.
    ctx = venue_context(bot="perps-rsi-meanrev", default_hl_net="testnet",
                        paper_start=PAPER_START, live_flag=not DRY_RUN)
    bot_id = ctx.bot_id
    broker = ctx.broker
    dry_run = ctx.dry_run
    order_usd = ctx.order_usd(ORDER_USD)
    max_open = ctx.max_open_positions(MAX_OPEN_POSITIONS)
    venue_tag = None if ctx.mode == "hl_paper" else "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    log.info("=" * 60)
    log.info("Hyperliquid PERPS bot starting | venue=%s (%s) | coins=%s | %s",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS", COINS,
             f"RSI({RSI_PERIOD}) {OVERSOLD}/{OVERBOUGHT}")
    log.info("order=$%.0f  lev=%dx  loop=%ds  loss-limit=%.0f%%  cap=%d/%d-per-loop",
             order_usd, LEVERAGE, LOOP_SECONDS, DAILY_LOSS_LIMIT * 100,
             max_open, MAX_NEW_PER_LOOP)
    log.info("=" * 60)

    # [2026-07-03 PERSIST] Restore the paper account from Postgres so a redeploy
    # or restart continues the SAME equity curve instead of resetting to $1000.
    # (Saved at the end of every loop; table bot_state via bot_pnl_store.)
    _saved_state = store.load_state(bot_id) if dry_run else None
    if _saved_state and broker.restore_state(_saved_state.get("broker") or {}):
        log.info("restored paper state: equity $%.2f, %d open position(s)",
                 broker.equity(), broker.open_count())

    def account_value():
        if dry_run:
            return broker.equity()
        return ctx.venue.account_value()

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

    # [2026-07-03 PERSIST] Rehydrate per-trade risk state alongside the account
    # (stops need entry prices; re-entry cooldowns need last-action times).
    if _saved_state:
        entries.update({str(k): float(v) for k, v in (_saved_state.get("entries") or {}).items()})
        entry_ts.update({str(k): float(v) for k, v in (_saved_state.get("entry_ts") or {}).items()})
        last_action.update({str(k): float(v) for k, v in (_saved_state.get("last_action") or {}).items()})

    # [2026-07-10] Live P&L baseline — measure from starting collateral, not the
    # $1000 paper start (see hyperliquid_momo_bot.py). Untraded live acct = $0.
    live_baseline = (store.load_state(bot_id + ":live") or {}).get("initial_equity") \
        if not dry_run else None

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

        # [2026-07-09 GATE-0 RAIL] kill switch re-checked EVERY loop in funded
        # modes — flipping it mid-run flattens and halts, not just at boot.
        if not dry_run and ctx.rails.kill_check():
            log.error("REAL_MONEY_KILL armed mid-run — flatten + halt.")
            halted_today = True
            for c in COINS:
                try:
                    ctx.venue.market_close(c)
                except Exception as e:
                    log.error("flatten %s failed: %s", c, e)

        _fleet_loss = (not dry_run and ctx.rails.daily_loss_hit(day_start_equity, equity))
        if (not halted_today and equity is not None and day_start_equity
                and (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT) or _fleet_loss)):
            log.warning("DAILY LOSS LIMIT HIT (equity %.2f <= %.2f%s). Halting new trades, "
                        "flattening. No revenge trades.", equity, day_start_equity,
                        ", $-rail" if _fleet_loss else "")
            halted_today = True
            if not dry_run:
                for c in COINS:
                    try:
                        ctx.venue.market_close(c)
                    except Exception as e:
                        log.error("flatten %s failed: %s", c, e)

        if halted_today:
            log.info("halted for today; sleeping.")
            time.sleep(LOOP_SECONDS)
            continue

        # current open positions keyed by coin -> signed size
        if dry_run:
            pos = broker.szi()
        else:
            try:
                pos = {c: v["size"] for c, v in ctx.venue.positions().items()}
            except Exception as e:
                log.warning("could not read positions: %s", e)
                pos = {}

        end = int(time.time() * 1000)
        start = end - 60 * 24 * 3600 * 1000      # ~60 days of 1h candles
        # [2026-07-05 CONCENTRATION CAP] count how many NEW opens this loop has
        # booked so one correlated dip can't fill the book in a single pass. The
        # global cap is checked against a LIVE open count at each entry (below),
        # not the once-per-loop `pos` snapshot which goes stale mid-scan.
        opened_this_loop = 0
        for coin in COINS:
            if not ctx.supports(coin):
                continue  # not listed on this venue (logged once)
            try:
                candles = ctx.venue.candles(coin, CANDLE_INTERVAL, start, end)
                closes = [float(c["c"]) for c in candles]
                highs = [float(c["h"]) for c in candles]
                lows = [float(c["l"]) for c in candles]
                price = closes[-1]
                r = rsi(closes, RSI_PERIOD)
            except Exception as e:
                log.error("%s data error: %s", coin, e)
                continue

            # [20-CANDLE RANGE 2026-07-01] Long-only range trading: buy near the
            # rolling 20-candle low, take profit near the rolling 20-candle high.
            # Exclude the current/forming bar (index -1) so the band has no
            # look-ahead. Need >=21 candles (20 prior + the current) to compute it.
            if len(candles) < 21:
                log.info("%-4s insufficient candle history; skipping.", coin)
                continue
            low20 = min(lows[-21:-1])
            high20 = max(highs[-21:-1])
            band = max(high20 - low20, 1e-9)
            buy_zone = low20 + 0.15 * band
            sell_zone = high20 - 0.15 * band

            held = pos.get(coin, 0.0)
            now_ts = now.timestamp()

            decision = "HOLD"

            # 1) Per-trade stop-loss (UNCHANGED): close any held position whose
            #    adverse move exceeds STOP_PCT. Downside protection guardrail.
            entry = entries.get(coin)
            if held != 0 and entry:
                adverse = ((price - entry) / entry) if held > 0 else ((entry - price) / entry)
                if adverse <= -STOP_PCT:
                    decision = "STOP_CLOSE"

            # 1b) [2026-07-01] Entry-relative take-profit + time stop so longs
            #     actually close. The 20-candle-high target below is often never
            #     reached in a flat/down tape; these guarantee the trade recycles.
            if decision == "HOLD" and held > 0 and entry:
                gain = (price - entry) / entry
                held_sec = now_ts - entry_ts.get(coin, now_ts)
                if gain >= TAKE_PROFIT_PCT:
                    decision = "RANGE_CLOSE"          # booked as a take-profit win
                elif held_sec >= MAX_HOLD_SEC:
                    decision = "STOP_CLOSE"           # time stop: recycle capital

            # 2) Range decisions (long-only), after the per-coin cooldown:
            #    FLAT + price <= buy_zone  -> OPEN_LONG (buy near the live low)
            #    LONG + price >= sell_zone -> RANGE_CLOSE (take profit at the high)
            #    Shorts are disabled (long-only range strategy).
            if decision == "HOLD":
                cooling = (now_ts - last_action.get(coin, 0.0)) < REENTRY_COOLDOWN_SEC
                # [2026-07-05 CONCENTRATION CAP] Live open count (broker in dry-run;
                # the fetched `pos` snapshot + this loop's opens in live). `broker`
                # is None when not DRY_RUN, so never call it there.
                open_now = (broker.open_count() if dry_run
                            else sum(1 for v in pos.values() if v) + opened_this_loop)
                if held > 0 and price >= sell_zone:
                    decision = "RANGE_CLOSE"
                elif not cooling and held == 0 and price <= buy_zone:
                    if open_now >= max_open or opened_this_loop >= MAX_NEW_PER_LOOP:
                        decision = "CAP_SKIP"        # valid buy blocked by the risk cap
                    else:
                        decision = "OPEN_LONG"

            log.info("%-4s price=%.2f RSI=%.1f low20=%.4f high20=%.4f buy<=%.4f sell>=%.4f held=%.4f -> %s",
                     coin, price, r, low20, high20, buy_zone, sell_zone, held, decision)

            size = round(order_usd * LEVERAGE / price, 4)

            if dry_run:
                # Book the fill in the paper account and mark to the live price.
                # (ShadowBroker fills these against the live Lighter book and
                # logs every order to the venue_orders ledger.)
                broker.mark(coin, price)
                if decision in ("STOP_CLOSE", "RANGE_CLOSE"):
                    _sz = broker.pos.get(coin, (0.0,))[0]
                    _pnl = broker.close(coin, price)
                    _record_close(bot_id, coin, entries.get(coin),
                                  entry_ts.get(coin), price, _pnl, _sz > 0,
                                  "stop" if decision == "STOP_CLOSE" else "range_high",
                                  venue=venue_tag, shadow=shadow_tag)
                    entries.pop(coin, None); entry_ts.pop(coin, None)
                    last_action[coin] = now_ts
                elif decision == "OPEN_LONG":
                    # If flipping an existing position, realise + record it first.
                    if coin in broker.pos:
                        _sz = broker.pos.get(coin, (0.0,))[0]
                        _pnl = broker.close(coin, price)
                        _record_close(bot_id, coin, entries.get(coin),
                                      entry_ts.get(coin), price, _pnl, _sz > 0, "flip",
                                      venue=venue_tag, shadow=shadow_tag)
                    broker.open(coin, True, size, price)
                    entries[coin] = price; entry_ts[coin] = now_ts
                    last_action[coin] = now_ts
                    opened_this_loop += 1
                continue

            if decision in ("HOLD", "CAP_SKIP"):
                continue

            try:
                if decision in ("STOP_CLOSE", "RANGE_CLOSE"):
                    ctx.venue.market_close(coin)
                    entries.pop(coin, None)
                    last_action[coin] = now_ts
                    log.info("%s %s @ %.2f",
                             "STOP-LOSS CLOSE" if decision == "STOP_CLOSE" else "RANGE-HIGH CLOSE",
                             coin, price)
                elif decision == "OPEN_LONG":
                    # [2026-07-09 GATE-0 RAIL] adapter-level notional cap: the
                    # live book may never exceed the per-bot env cap.
                    open_notional = sum(1 for v in pos.values() if v) * order_usd
                    if not ctx.rails.notional_ok(open_notional, order_usd):
                        log.info("%s NOTIONAL_CAP_SKIP (open ~$%.0f + $%.0f > cap)",
                                 coin, open_notional, order_usd)
                        continue
                    if held < 0:
                        ctx.venue.market_close(coin)
                    ctx.venue.market_open(coin, True, size)
                    entries[coin] = price
                    last_action[coin] = now_ts
                    opened_this_loop += 1
                    log.info("ORDER SENT %s %s size=%s", decision, coin, size)
            except Exception as e:
                log.error("order failed %s %s: %s", decision, coin, e)

        # Publish a snapshot for the live dashboard (guarded; never raises).
        if dry_run:
            pub_equity = broker.equity()
            pub_open = broker.open_count()
            pub_pnl = pub_equity - PAPER_START
        else:
            pub_equity = equity
            pub_open = sum(1 for v in pos.values() if v)
            if live_baseline is None and equity is not None:
                live_baseline = equity
                store.save_state(bot_id + ":live", {"initial_equity": equity})
            pub_pnl = (equity - live_baseline) if (equity is not None
                                                   and live_baseline is not None) else None
        _szi = broker.szi() if dry_run else {}
        store.publish(
            bot_id,
            status="halted" if halted_today else "online",
            equity=pub_equity,
            pnl_abs=pub_pnl,
            open_trades=pub_open,
            extra={"mode": ctx.mode if ctx.mode != "hl_paper"
                   else ("dry-run" if dry_run else "live-testnet"),
                   "venue": ctx.mode,
                   "longs": sum(1 for v in _szi.values() if v > 0),
                   "shorts": sum(1 for v in _szi.values() if v < 0),
                   "coins": COINS},
        )
        # [2026-07-03 PERSIST] Durable paper state -> Postgres (guarded, cheap:
        # one small JSONB upsert per loop) so redeploys continue this curve.
        if dry_run:
            store.save_state(bot_id, {
                "broker": broker.to_state(),
                "entries": entries,
                "entry_ts": entry_ts,
                "last_action": last_action,
            })
        if os.environ.get("ONE_CYCLE"):
            # parity/smoke harness: one full decision pass then exit cleanly
            log.info("ONE_CYCLE set — exiting after one pass.")
            break
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")
