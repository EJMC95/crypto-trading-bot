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
from venues import venue_context  # [2026-07-09 LIGHTER GATE-0] venue abstraction

# --------------------------- configuration -------------------------------
# Widened from BTC/ETH/SOL to a broad set of liquid Hyperliquid perps.
# The per-coin loop is guarded, so any symbol not listed on the venue is
# skipped without affecting the others. For a true live "top 100 by volume",
# swap this for info.meta_and_asset_ctxs() ranked by dayNtlVlm at startup.
COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ARB", "OP",
    "SUI", "SEI", "TIA", "APT", "NEAR", "INJ", "LTC", "BCH", "ATOM", "DOT",
    "ADA", "AAVE", "PEPE", "WIF", "kBONK", "ENA", "ORDI", "JUP", "TON", "kSHIB",
    # [2026-07-07 COVERAGE] HL top-30 liquidity the web lacked: HYPE was the
    # #4 perp by 24h notional ($359M, SOL-tier) with zero fleet coverage.
    "HYPE", "ZEC", "TAO",
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
# [2026-07-09 CONCENTRATION CAP — pre-live blocker] Same global cap pattern
# Bounce Catcher got on Jul-5: this bot had NO position limit and held 15
# concurrent longs alone on Jul-8 (fleet budget is 20). Cap total open
# positions and the per-loop open rate; a valid buy blocked by the cap logs
# CAP_SKIP (expected, not a fault). In lighter modes the cap is derived from
# the per-bot notional cap instead (venues/safety.py).
MAX_OPEN_POSITIONS = 8           # global cap on concurrent open positions
MAX_NEW_PER_LOOP = 2             # smooth one-loop bursts into a correlated dip

PAPER = "--paper" in sys.argv      # watch live testnet prices, no account/keys needed
DRY_RUN = PAPER or ("--live" not in sys.argv)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("perps-donchian-breakout")


def _record_close(bot, coin, ent_px, ent_ts, exit_px, pnl, was_long, reason,
                  venue=None, shadow=None):
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
        venue=venue, shadow=shadow,
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
    # [2026-07-09 LIGHTER GATE-0] All venue plumbing (HL info/exchange, Lighter
    # client, paper vs shadow broker, kill switch, notional rails) now lives in
    # venues/. VENUE unset -> hl_paper -> exactly the pre-refactor behaviour:
    # HL testnet market data + PaperBroker fills.
    ctx = venue_context(bot="perps-donchian-breakout", default_hl_net="testnet",
                        paper_start=PAPER_START, live_flag=not DRY_RUN)
    bot_id = ctx.bot_id
    broker = ctx.broker
    dry_run = ctx.dry_run
    order_usd = ctx.order_usd(ORDER_USD)
    max_open = ctx.max_open_positions(MAX_OPEN_POSITIONS)
    venue_tag = None if ctx.mode == "hl_paper" else "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # [2026-07-03 PERSIST] Restore the paper account from Postgres so a redeploy
    # or restart continues the SAME equity curve instead of resetting to $1000.
    _saved_state = store.load_state(bot_id) if dry_run else None
    if _saved_state and broker.restore_state(_saved_state.get("broker") or {}):
        log.info("restored paper state: equity $%.2f, %d open position(s)",
                 broker.equity(), broker.open_count())
    if PAPER:
        log.info("PAPER mode: no account or keys needed. Reading LIVE prices and "
                 "simulating fills in memory. No orders sent, no real balances.")

    log.info("=" * 64)
    log.info("MomoBreakout PERPS bot | venue=%s (%s) | coins=%s",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS", COINS)
    log.info("20-candle RANGE (long-only) + %.0f%% hard stop | %dx | $%.0f/trade | "
             "cap %d open / %d new-per-loop | loop=%ds",
             HARD_STOP * 100, LEVERAGE, order_usd, max_open, MAX_NEW_PER_LOOP,
             LOOP_SECONDS)
    log.info("=" * 64)

    def account_value():
        if dry_run:
            return broker.equity()
        return ctx.venue.account_value()

    def positions():
        if dry_run:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        return ctx.venue.positions()

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

    # [2026-07-10] Live P&L baseline: measure live-account P&L from the STARTING
    # collateral (recorded once, persisted), not the $1000 paper start — so an
    # untraded live account reads $0, not -$935. Restore any saved baseline.
    live_baseline = (store.load_state(bot_id + ":live") or {}).get("initial_equity") \
        if not dry_run else None

    while True:
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            try:
                day_start_equity = account_value()
            except Exception:
                pass

        # [2026-07-09 GATE-0 RAIL] kill switch re-checked EVERY loop in funded
        # modes — flipping it mid-run flattens and halts, not just at boot.
        if not dry_run and ctx.rails.kill_check():
            log.error("REAL_MONEY_KILL armed mid-run — flatten + halt.")
            halted_today = True
            for c in COINS:
                try:
                    ctx.venue.market_close(c)
                except Exception as e:
                    log.error("flatten %s: %s", c, e)

        try:
            equity = account_value()
        except Exception as e:
            log.warning("account value unavailable: %s", e)
            equity = None

        _fleet_loss = (not dry_run and ctx.rails.daily_loss_hit(day_start_equity, equity))
        if (not halted_today and equity is not None and day_start_equity
                and (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT) or _fleet_loss)):
            log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f%s). Flatten + halt for today.",
                        equity, day_start_equity,
                        ", $-rail" if _fleet_loss else "")
            halted_today = True
            if not dry_run:
                for c in COINS:
                    try:
                        ctx.venue.market_close(c)
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
        opened_this_loop = 0
        for coin in COINS:
            if not ctx.supports(coin):
                continue  # not listed on this venue (logged once)
            try:
                candles = ctx.venue.candles(coin, CANDLE_INTERVAL, start, end)
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
                    # [2026-07-09 CONCENTRATION CAP] live open count, like
                    # Bounce Catcher: broker in dry-run, else the fetched
                    # snapshot + this loop's opens (snapshot goes stale mid-scan).
                    open_now = (broker.open_count() if dry_run
                                else sum(1 for v in pos.values()
                                         if v.get("size")) + opened_this_loop)
                    if open_now >= max_open or opened_this_loop >= MAX_NEW_PER_LOOP:
                        decision = "CAP_SKIP"       # valid buy blocked by the cap
                    else:
                        decision = "OPEN_LONG"      # buy near the range low

            log.info("%-4s px=%.2f ema200=%.2f low20=%.4f high20=%.4f buy<=%.4f sell>=%.4f held=%.4f -> %s",
                     coin, px, s["ema"], s["low20"], s["high20"],
                     s["buy_zone"], s["sell_zone"], held, decision)

            size = round(order_usd * LEVERAGE / px, 4)

            if dry_run:
                # Book the fill in the paper account and mark to the live price,
                # so exits/stops and an equity curve show up on later loops.
                # (ShadowBroker fills these against the live Lighter book and
                # logs every order to the venue_orders ledger.)
                broker.mark(coin, px)
                if decision == "OPEN_LONG":
                    broker.open(coin, True, size, px); entry_ts[coin] = now.timestamp()
                    opened_this_loop += 1
                elif decision == "OPEN_SHORT":
                    broker.open(coin, False, size, px); entry_ts[coin] = now.timestamp()
                elif decision in ("EXIT_LONG", "STOP_LONG", "COVER_SHORT", "STOP_SHORT"):
                    _sz, _ent = broker.pos.get(coin, (0.0, 0.0))
                    _pnl = broker.close(coin, px)
                    _record_close(bot_id, coin, _ent, entry_ts.pop(coin, None),
                                  px, _pnl, _sz > 0, decision.lower(),
                                  venue=venue_tag, shadow=shadow_tag)
                if decision not in ("HOLD", "CAP_SKIP"):
                    mode = "shadow" if shadow_tag else ("paper" if PAPER else "dry-run")
                    notify(f":test_tube: MomoBot [{mode.upper()}] {decision} {coin} @ {px:,.2f}",
                           coin=coin, decision=decision, price=round(px, 2), mode=mode)
                continue

            if decision in ("HOLD", "CAP_SKIP"):
                continue

            try:
                _raw = None                 # exchange response, for the ledger
                _closed = None              # (coin, entry, signed_size, was_long, reason)
                if decision in ("EXIT_LONG", "STOP_LONG", "COVER_SHORT", "STOP_SHORT"):
                    _ent = pos.get(coin, {}).get("entry") or 0.0
                    _sz = pos.get(coin, {}).get("size") or 0.0
                    _raw = ctx.venue.market_close(coin)
                    _closed = (coin, _ent, _sz, _sz > 0, decision)
                elif decision in ("OPEN_LONG", "OPEN_SHORT"):
                    # [2026-07-09 GATE-0 RAIL] adapter-level notional cap: the
                    # live book may never exceed the per-bot env cap.
                    open_notional = sum(1 for v in pos.values()
                                        if v.get("size")) * order_usd
                    if not ctx.rails.notional_ok(open_notional, order_usd):
                        log.info("%s NOTIONAL_CAP_SKIP (open ~$%.0f + $%.0f > cap)",
                                 coin, open_notional, order_usd)
                        continue
                    _raw = ctx.venue.market_open(coin, decision == "OPEN_LONG", size)
                    entry_ts[coin] = now.timestamp()   # [fix] live time-stop needs this
                    opened_this_loop += 1
                log.info("ORDER SENT %s %s", decision, coin)
                notify(f":chart_with_upwards_trend: MomoBot [{ctx.mode.upper()}] {decision} "
                       f"{coin} @ {px:,.2f} (size {size})",
                       coin=coin, decision=decision, price=round(px, 2),
                       size=size, mode=ctx.mode)
                # [2026-07-10] LIVE trade ledger — record every real open/close to
                # venue_orders (+ paper_trades on close) so the live card shows
                # trade history, win/loss and per-trade P&L, same as the paper
                # bots. Guarded SEPARATELY so a ledger hiccup never looks like a
                # failed order.
                try:
                    if _closed is not None:
                        _c, _e, _s, _wl, _dec = _closed
                        _pnl = (abs(_s) * (px - _e)) if _wl else (abs(_s) * (_e - px))
                        _record_close(bot_id, _c, _e, entry_ts.pop(_c, None), px,
                                      (_pnl if _e else 0.0), _wl, _dec.lower(),
                                      venue="lighter", shadow=False)
                        store.publish_venue_order(
                            bot_id, venue="lighter", shadow=False, coin=_c,
                            side=("sell" if _wl else "buy"), size=abs(_s),
                            px_decision=px, px_fill=px, raw=_raw)
                    elif decision in ("OPEN_LONG", "OPEN_SHORT"):
                        store.publish_venue_order(
                            bot_id, venue="lighter", shadow=False, coin=coin,
                            side=("buy" if decision == "OPEN_LONG" else "sell"),
                            size=size, px_decision=px, px_fill=px, raw=_raw)
                except Exception as _le:  # noqa: BLE001
                    log.warning("live-order ledger write failed %s: %s", coin, _le)
            except Exception as e:
                log.error("order failed %s %s: %s", decision, coin, e)
                notify(f":warning: MomoBot ORDER FAILED {decision} {coin}: {e}",
                       coin=coin, decision=decision, mode="error")

        # Publish a snapshot for the live dashboard (guarded; never raises).
        if dry_run:
            pub_equity = broker.equity()
            pub_open = broker.open_count()
            pub_pnl = pub_equity - PAPER_START
        else:
            pub_equity = equity
            pub_open = sum(1 for v in pos.values()
                           if (v.get("size") if isinstance(v, dict) else v))
            # [2026-07-10] record the starting collateral once, then P&L = equity
            # - baseline (0 until the first trade moves the account).
            if live_baseline is None and equity is not None:
                live_baseline = equity
                store.save_state(bot_id + ":live", {"initial_equity": equity})
            pub_pnl = (equity - live_baseline) if (equity is not None
                                                   and live_baseline is not None) else None
        _szi = broker.szi() if dry_run else {}
        store.publish(
            bot_id,
            status="paper" if PAPER else ("halted" if halted_today else "online"),
            equity=pub_equity,
            pnl_abs=pub_pnl,
            open_trades=pub_open,
            extra={"mode": ctx.mode if ctx.mode != "hl_paper"
                   else ("paper" if PAPER else ("dry-run" if dry_run else "live-testnet")),
                   "venue": ctx.mode,
                   "longs": sum(1 for v in _szi.values() if v > 0),
                   "shorts": sum(1 for v in _szi.values() if v < 0),
                   "coins": COINS},
        )
        # [2026-07-03 PERSIST] Durable paper state -> Postgres (guarded, cheap)
        # so redeploys continue this equity curve.
        if dry_run:
            store.save_state(bot_id, {
                "broker": broker.to_state(),
                "entry_ts": entry_ts,
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
