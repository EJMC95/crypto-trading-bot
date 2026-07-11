#!/usr/bin/env python3
"""
lighter_trend_bot.py — Tide Rider on LIGHTER (1x long PERP trend follower).

WHAT / WHY (2026-07-10)
  Tide Rider (crypto-trend-daily) is a daily 50/200 EMA golden-cross trend
  follower, validated LONG-ONLY on Kraken SPOT (+52% basket / 2.7yr on the 6
  majors). Lighter is perps-only, so here it runs as a 1x LONG PERP: identical
  price exposure, zero trading fee — but a long perp PAYS funding, and this bot
  holds long for weeks during uptrends. Re-validated with that drag
  (scripts/backtest_tide_rider_perp.py): basket +52% spot -> +40% perp over
  ~2.7yr; the funding drag (~13pp) is real and erodes the down-trend protection,
  so the Lighter version is viable but weaker than the Kraken-spot original.

  Signal (matches ImprovedStrategyV4): LONG while EMA50 > EMA200 (golden cross),
  CLOSE on the death cross. A catastrophic hard stop (CATASTROPHIC_STOP) is a
  seatbelt only — the death cross is the real exit. 1x, no leverage.

EXECUTION / SAFETY — the venue layer (venues/), same path the perps bots go live on:
  VENUE=hl_paper       (default) paper sim on HL data — offline smoke.
  VENUE=lighter_shadow model fills on the LIVE Lighter book; MODELS the funding
                       drag so shadow P&L is honest; logs venue_orders; sends nothing.
  VENUE=lighter_live   REAL 1x long perps. venues/safety.py REFUSES to start unless
                       REAL_MONEY_KILL=DISARMED_I_UNDERSTAND and a per-bot notional
                       cap are set. Keys/disarm/deposit are the operator's — not here.

Usage:
    python lighter_trend_bot.py            # dry-run forever
    python lighter_trend_bot.py --once      # single scan then exit (smoke test)
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import marks, venue_context

BOT = "crypto-trend-daily"          # venue layer suffixes -lshadow / -lighter
H = 24 * 365

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
COINS = os.environ.get("TREND_COINS", "BTC,ETH,SOL,BNB,XRP,TRX").split(",")
EMA_FAST = int(os.environ.get("TREND_EMA_FAST", "50"))
EMA_SLOW = int(os.environ.get("TREND_EMA_SLOW", "200"))
CANDLE_INTERVAL = os.environ.get("TREND_INTERVAL", "1d")
ORDER_USD = float(os.environ.get("TREND_ORDER_USD", "50"))
MAX_OPEN_POSITIONS = int(os.environ.get("TREND_MAX_OPEN", "6"))
# When slots/margin can't hold every golden major, admit ENTRIES lowest-funding
# first (a long pays funding; high funding = crowded, frothy, prone to dump).
# Walk-forward validated to beat first-come list order at 2-3 slots. OFF by default:
# with 6 coins / 6 slots (or ample margin) it never binds and behaviour is identical.
RANK_BY_FUNDING = os.environ.get("TREND_RANK_BY_FUNDING", "0").lower() in ("1", "true", "yes")
CATASTROPHIC_STOP = float(os.environ.get("TREND_CATASTROPHIC_STOP", "0.35"))  # seatbelt
DAILY_LOSS_LIMIT = float(os.environ.get("TREND_DAILY_LOSS", "0.10"))
LOOP_SECONDS = int(os.environ.get("TREND_LOOP_SECONDS", "3600"))  # daily signal, hourly poll

LOG_FILE = os.environ.get("TREND_LOG_FILE", "lighter_trend_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def ema(values, span):
    k = 2.0 / (span + 1.0)
    out = values[0]
    for v in values[1:]:
        out = v * k + out * (1 - k)
    return out


def closes_from_candles(candles):
    """Robustly pull the close series from venue-native candle records
    (dicts with 'c', or bare numbers). Returns a float list oldest->newest."""
    out = []
    for c in candles:
        if isinstance(c, dict):
            v = c.get("c", c.get("close"))
        else:
            v = c
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def golden(closes):
    """(is_golden, ema_fast, ema_slow) or None if not enough history."""
    if len(closes) < EMA_SLOW + 2:
        return None
    ef = ema(closes[-(EMA_SLOW * 3):], EMA_FAST)
    es = ema(closes[-(EMA_SLOW * 3):], EMA_SLOW)
    return (ef > es, ef, es)


def fresh_mid(ctx, coin):
    """Live-book mid, or None. Never a stale funding-map mark (the catastrophic
    stop must see a real price). Shared impl: venues/marks.py (also sorts the
    unsorted REST-snapshot fallback, which this local copy did not)."""
    return marks.fresh_mid(ctx.venue, coin)


def _record_close(bot, coin, ent_px, ent_ts, exit_px, price_pnl, fund_pnl, reason,
                  order_usd=ORDER_USD, venue=None, shadow=None):
    pnl = float(price_pnl) + float(fund_pnl)
    pnl_pct = (pnl / (order_usd or 1.0)) if ent_px else None
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=pnl, pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            reason="long_" + reason, venue=venue, shadow=shadow)
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description="Tide Rider — Lighter 1x long trend")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    global _SUPERVISOR_BOT_ID
    ctx = venue_context(bot=BOT, default_hl_net="mainnet",
                        paper_start=START_EQUITY, live_flag=("--live" in sys.argv))
    bot_id = ctx.bot_id
    _SUPERVISOR_BOT_ID = bot_id
    broker = ctx.broker
    dry_run = ctx.dry_run
    order_usd = ctx.order_usd(ORDER_USD)
    max_open = ctx.max_open_positions(MAX_OPEN_POSITIONS)
    venue_tag = None if ctx.mode == "hl_paper" else "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # bot_id 'crypto-trend-daily' (unsuffixed in hl_paper) is ALSO the id the live
    # Freqtrade Kraken Tide Rider publishes under (freqtrade_pnl_poller.py). hl_paper
    # is only an offline smoke here; refuse it as a daemon so we never clobber that
    # live row. lighter_shadow/live get a -lshadow/-lighter suffix (distinct rows).
    if ctx.mode == "hl_paper" and not args.once:
        raise SystemExit(
            "hl_paper is offline-smoke only for this bot (bot_id 'crypto-trend-daily' "
            "collides with the live Freqtrade Tide Rider row). Use --once, or "
            "VENUE=lighter_shadow / lighter_live for a suffixed id.")

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:
        pass

    meta = {}          # coin -> {entry, opened_ts, accrued}  (accrued funding, <=0 for a long)
    fund_realized = 0.0

    if dry_run:
        _saved = store.load_state(bot_id)
        if _saved and broker is not None and broker.restore_state(_saved.get("broker") or {}):
            meta = {str(k): v for k, v in (_saved.get("meta") or {}).items()}
            fund_realized = float(_saved.get("fund_realized") or 0.0)
            log.info("restored paper state: equity $%.2f, %d open", broker.equity(),
                     broker.open_count())
    else:
        meta = {str(k): v for k, v in ((store.load_state(bot_id + ":live") or {})
                                       .get("meta") or {}).items()}
    live_baseline = (store.load_state(bot_id + ":live") or {}).get("initial_equity") \
        if not dry_run else None

    log.info("=" * 64)
    log.info("Tide Rider (Lighter 1x LONG trend) | venue=%s (%s) | coins=%s",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS", COINS)
    log.info("%d/%d EMA golden cross (long) / death cross (exit) | catastrophic stop %.0f%% "
             "| $%.0f x max %d | loop=%ds", EMA_FAST, EMA_SLOW, CATASTROPHIC_STOP * 100,
             order_usd, max_open, LOOP_SECONDS)
    log.info("LONG-ONLY 1x perp — pays funding (drag modelled in shadow); NOT delta-neutral.")
    log.info("=" * 64)

    def account_value():
        return broker.equity() if dry_run else ctx.venue.account_value()

    def positions():
        if dry_run:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        return ctx.venue.positions()

    def _flatten_all(reason):
        nonlocal n_closed, n_wins
        try:
            live_pos = ctx.venue.positions()
        except Exception as e:
            log.error("flatten scan failed: %s", e)
            return
        for c in list(live_pos):
            held = (live_pos.get(c, {}) or {}).get("size", 0.0) or 0.0
            if not held:
                continue
            m = meta.get(c) or {}
            entry = m.get("entry") or (live_pos.get(c, {}) or {}).get("entry") or 0.0
            opened_ts = m.get("opened_ts") or time.time()
            px = fresh_mid(ctx, c) or entry
            try:
                ctx.venue.market_close(c)
            except Exception as e:
                log.error("flatten %s: %s", c, e)
                continue
            price_pnl = abs(held) * (px - entry)
            n_closed += 1
            n_wins += 1 if price_pnl > 0 else 0
            _record_close(bot_id, c, entry, opened_ts, px, price_pnl, m.get("accrued", 0.0),
                          reason, order_usd=order_usd, venue=venue_tag, shadow=shadow_tag)
            # Mirror the emergency exit into venue_orders (close_long does this for
            # normal exits). _flatten_all only runs in funded modes, so this row is
            # the real forced-close leg; keep it non-fatal to the flatten loop.
            if venue_tag and not shadow_tag:
                try:
                    store.publish_venue_order(
                        bot_id, venue="lighter", shadow=shadow_tag, coin=c,
                        side="sell", size=abs(held), px_decision=px, px_fill=px,
                        raw={"reason": reason, "leg": "close"})
                except Exception:
                    pass
            meta.pop(c, None)

    def close_long(coin, reason, px, held, entry, opened_ts, m):
        """Close one long + full bookkeeping (ledger, counters, meta pop). Returns
        True if closed (False only if a live market_close raised)."""
        nonlocal realized, n_closed, n_wins, fund_realized
        fund_pnl = m.get("accrued", 0.0)
        if dry_run:
            price_pnl = broker.close(coin, px)
            fund_realized += fund_pnl
        else:
            try:
                ctx.venue.market_close(coin)
            except Exception as e:
                log.error("close %s failed: %s — retry next loop", coin, e)
                return False
            price_pnl = abs(held) * (px - entry)
        realized += (price_pnl + fund_pnl) if dry_run else 0.0
        n_closed += 1
        n_wins += 1 if (price_pnl + fund_pnl) > 0 else 0
        log.info("CLOSE %s long | price %+.2f funding %+.2f [%s]",
                 coin, price_pnl, fund_pnl, reason)
        _record_close(bot_id, coin, entry, opened_ts, px, price_pnl, fund_pnl,
                      reason, order_usd=order_usd, venue=venue_tag, shadow=shadow_tag)
        # Funded lighter modes only (shadow's ShadowBroker already logged the honest
        # fill; hl_paper must not write the live-id ledger).
        if venue_tag and not shadow_tag:
            try:
                store.publish_venue_order(
                    bot_id, venue="lighter", shadow=shadow_tag, coin=coin,
                    side="sell", size=abs(held), px_decision=px, px_fill=px,
                    raw={"reason": reason, "leg": "close"})
            except Exception:
                pass
        meta.pop(coin, None)
        return True

    try:
        day_start_equity = account_value()
    except Exception as e:
        log.warning("account value unreadable (%s); loss-limit waits.", e)
        day_start_equity = None
    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    # [2026-07-11 DURABLE HALT] a tripped daily-loss halt survives restarts —
    # the memory-only flag meant a same-day redeploy silently resumed trading.
    _halt = store.load_daily_halt(bot_id, cur_day.isoformat())
    if _halt:
        halted_today = True
        day_start_equity = _halt.get("day_start_equity") or day_start_equity
        log.warning("daily-loss halt restored from state — halted for the rest of today.")
    last_ts = time.time()

    while True:
        t0 = time.time()
        # [2026-07-12 GO-GREEN] loop-top liveness touch — see bot_pnl_store.heartbeat
        store.heartbeat(bot_id)
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            try:
                day_start_equity = account_value()
            except Exception:
                pass

        if not dry_run and ctx.rails.kill_check():
            log.error("REAL_MONEY_KILL armed mid-run — flatten + halt.")
            halted_today = True
            _flatten_all("kill_switch")

        try:
            equity = account_value()
        except Exception as e:
            log.warning("account value unavailable: %s", e)
            equity = None
        # [2026-07-11 LATE BASELINE] if the boot/day-roll capture failed (venue
        # down, or the equity guard vetoed a dislocated print) the rail used to
        # stay OFF all day. Adopt the first credible read instead.
        if day_start_equity is None and equity is not None:
            day_start_equity = equity
            log.warning("day-start equity adopted late: %.2f", equity)

        _fleet_loss = (not dry_run and ctx.rails.daily_loss_hit(day_start_equity, equity))
        if (not halted_today and equity is not None and day_start_equity
                and (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT) or _fleet_loss)):
            # [2026-07-11 RAIL DEBOUNCE] one dislocated equity print sold the
            # book into the dislocation (-5.9% real). Confirm on a second read
            # (SafetyRails.confirm_daily_loss — shared, FAIL-SAFE: unreadable
            # confirm counts as confirmed). Adopt the fresher read either way
            # so a phantom print can't leak into published equity or the
            # persisted live P&L baseline.
            _confirmed, equity = ctx.rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT, account_value)
            if _confirmed:
                log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f). Flatten + halt.",
                            equity, day_start_equity)
                halted_today = True
                store.save_daily_halt(bot_id, cur_day.isoformat(), day_start_equity)
                if not dry_run:
                    _flatten_all("daily_loss")

        if halted_today:
            log.info("halted for today; sleeping.")
            # [2026-07-11 HALT HEARTBEAT] keep the dashboard row fresh while
            # halted — the early `continue` skipped the publish below, so a
            # halted bot looked DEAD (stale row) instead of HALTED.
            if ctx.mode != "hl_paper":
                try:
                    if dry_run:
                        _open_fund = sum((meta.get(c) or {}).get("accrued", 0.0)
                                         for c in meta)
                        _hb_eq = broker.equity() + fund_realized + _open_fund
                        _hb_pnl = _hb_eq - START_EQUITY
                    else:
                        _hb_eq = equity
                        _hb_pnl = (equity - live_baseline) if (equity is not None
                                                               and live_baseline is not None) else None
                    store.publish(
                        bot_id, status="halted",
                        equity=_hb_eq, pnl_abs=_hb_pnl,
                        closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                        extra={"mode": ctx.mode, "venue": ctx.mode,
                               "style": "trend-1x-long",
                               "held": sorted(meta.keys()), "coins": COINS})
                except Exception:
                    pass
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            fund = ctx.venue.funding_map()
        except Exception:
            fund = {}
        try:
            pos = positions()
        except Exception as e:
            log.warning("positions unreadable: %s", e)
            if not dry_run:
                if args.once:
                    break
                time.sleep(LOOP_SECONDS)
                continue
            pos = {}

        dt_h = (t0 - last_ts) / 3600.0
        last_ts = t0
        end = int(time.time() * 1000)
        start = end - (EMA_SLOW * 3 + 5) * 86400 * 1000
        open_now = sum(1 for v in pos.values() if (v.get("size") if isinstance(v, dict) else v))

        # Entry-admission order. Default = COINS list order (byte-identical to before).
        # RANK_BY_FUNDING sorts lowest-funding-first so that when open_now hits the cap
        # / margin runs out, the cheapest-to-carry golden majors get the slots. Only the
        # admission order changes; per-coin management (stops/exits) is order-independent.
        scan_coins = COINS
        if RANK_BY_FUNDING:
            scan_coins = sorted(
                COINS, key=lambda c: (fund.get(c) or {}).get("rate")
                if (fund.get(c) or {}).get("rate") is not None else 1e9)

        for coin in scan_coins:
            if not ctx.supports(coin):
                continue
            # State FIRST so the catastrophic-stop seatbelt works even if candles fail.
            held = pos.get(coin, {}).get("size", 0.0)
            m = meta.get(coin) or {}
            entry = m.get("entry") or pos.get(coin, {}).get("entry") or 0.0
            opened_ts = m.get("opened_ts") or t0
            rate = (fund.get(coin) or {}).get("rate")
            px = fresh_mid(ctx, coin)

            # Accrue the funding drag on an open long in BOTH modes (a LONG pays when
            # rate>0 -> accrued goes negative). Live equity already carries real
            # funding, so accrued only feeds the ledger/win-count; equity double-count
            # stays dry_run-guarded in the publish block. Mark the paper broker.
            if held and px:
                if dry_run:
                    broker.mark(coin, px)
                if rate is not None:
                    m["accrued"] = m.get("accrued", 0.0) - rate * abs(held) * px * dt_h
                meta[coin] = {**m, "entry": entry, "opened_ts": opened_ts}

            # Candles for the cross. DROP the still-forming current-day candle so the
            # signal is on CLOSED bars only (match the validated backtest; a partial
            # bar folded into the EMAs can flicker is_golden and whipsaw).
            closes = None
            try:
                candles = ctx.venue.candles(coin, CANDLE_INTERVAL, start, end)
                if candles and CANDLE_INTERVAL.endswith("d"):
                    candles = candles[:-1]
                closes = closes_from_candles(candles)
            except Exception as e:
                log.error("%s candle error: %s", coin, e)
            g = golden(closes) if closes else None

            # Seatbelt: without the signal we can't judge the trend, but the
            # catastrophic stop must still fire off a live price (candle-independent).
            if g is None:
                if held and px and entry and (px - entry) / entry <= -CATASTROPHIC_STOP:
                    if close_long(coin, "catastrophic_stop", px, held, entry, opened_ts, m):
                        open_now -= 1
                elif not held:
                    log.info("%-4s insufficient daily history; skip.", coin)
                continue
            is_golden, ef, es = g

            if not px:
                px = closes[-1] if closes else 0.0
            if not px:
                continue

            # ----- manage an open long -----
            if held:
                draw = (px - entry) / entry if entry else 0.0     # -ve = underwater
                reason = "death_cross" if not is_golden else (
                    "catastrophic_stop" if draw <= -CATASTROPHIC_STOP else None)
                if reason and close_long(coin, reason, px, held, entry, opened_ts, m):
                    open_now -= 1
                continue

            # ----- flat: enter long on a golden cross -----
            if is_golden and open_now < max_open:
                size = round(order_usd / px, 6)
                if not dry_run:
                    # open_now is the live counter (grows with same-loop opens); the
                    # once-captured `pos` snapshot would miss them. max_open=floor(cap/
                    # clip) is the primary cap — notional_ok is the belt-and-suspenders.
                    open_ntl = open_now * order_usd
                    if not ctx.rails.notional_ok(open_ntl, order_usd):
                        log.info("%s NOTIONAL_CAP_SKIP", coin)
                        continue
                try:
                    if dry_run:
                        broker.open(coin, True, size, px)
                    else:
                        ctx.venue.market_open(coin, True, size)
                except Exception as e:
                    log.error("open %s failed: %s", coin, e)
                    continue
                meta[coin] = {"entry": px, "opened_ts": t0, "accrued": 0.0}
                open_now += 1
                log.info("OPEN %s long $%.0f | ema%d %.4g > ema%d %.4g | px %.6g",
                         coin, order_usd, EMA_FAST, ef, EMA_SLOW, es, px)
                # Funded lighter modes (live/testnet) only: the main loop is the sole
                # venue_orders writer there. In shadow the ShadowBroker already logs the
                # honest crossed-spread fill — a px_fill=px row here would corrupt the
                # slippage evidence; in hl_paper we don't touch the live-id ledger.
                if venue_tag and not shadow_tag:
                    try:
                        store.publish_venue_order(
                            bot_id, venue="lighter", shadow=shadow_tag, coin=coin,
                            side="buy", size=size, px_decision=px, px_fill=px,
                            raw={"signal": "golden_cross", "leg": "open"})
                    except Exception:
                        pass

        # ---- publish ----
        if dry_run:
            open_fund = sum((meta.get(c) or {}).get("accrued", 0.0) for c in meta)
            pub_equity = broker.equity() + fund_realized + open_fund
            pub_open = broker.open_count()
            pub_pnl = pub_equity - START_EQUITY
        else:
            pub_equity = equity
            pub_open = sum(1 for v in pos.values()
                           if (v.get("size") if isinstance(v, dict) else v))
            if live_baseline is None and equity is not None:
                live_baseline = equity
            pub_pnl = (equity - live_baseline) if (equity is not None
                                                   and live_baseline is not None) else None
        # hl_paper is offline-smoke-only for this bot and its UNSUFFIXED id collides
        # with the live Freqtrade Tide Rider row — never publish it. shadow/live use
        # suffixed ids (-lshadow/-lighter) and publish normally.
        if ctx.mode != "hl_paper":
            try:
                store.publish(
                    bot_id, status="halted" if halted_today else "online",
                    equity=pub_equity, pnl_abs=pub_pnl, open_trades=pub_open,
                    closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                    extra={"mode": ctx.mode, "venue": ctx.mode, "style": "trend-1x-long",
                           "held": sorted(meta.keys()), "coins": COINS})
            except Exception:
                pass
        try:
            if dry_run:
                store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                          "fund_realized": fund_realized})
            elif live_baseline is not None:
                store.save_state(bot_id + ":live", {"initial_equity": live_baseline,
                                                    "meta": meta})
        except Exception:
            pass

        log.info("scan ok | held: %s | realized $%+.2f",
                 ", ".join(sorted(meta.keys())) or "none", realized)
        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


_SUPERVISOR_BOT_ID = None


def _supervised():
    """[2026-07-12 GO-GREEN] an unhandled exception used to crash-loop the
    container silently (stale row, no explanation). Log it, mark the row
    ERROR, back off, restart — state re-hydrates from Postgres on re-init.
    SystemExit (boot refusals) and Ctrl-C pass through untouched."""
    while True:
        try:
            main()
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            log.exception("unhandled exception — marking row ERROR, restarting in 60s")
            try:
                store.set_status(_SUPERVISOR_BOT_ID or BOT, "error")
            except Exception:  # noqa: BLE001
                pass
            time.sleep(60)


if __name__ == "__main__":
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
