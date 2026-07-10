#!/usr/bin/env python3
"""
lighter_funding_bot.py — Yield Harvester (Lighter, DIRECTIONAL funding capture).

WHAT THIS IS — AND HONESTLY IS NOT (2026-07-10)
  Lighter is a perp-only venue, so there is NO same-coin hedge on it: a single
  venue cannot run a delta-neutral funding carry. This bot therefore captures
  funding DIRECTIONALLY — it takes the funding-RECEIVING side of a hot perp
  (SHORT when funding is positive / longs are crowded, LONG when negative) and
  collects Lighter's (zero-fee) funding while it stays hot. That means it carries
  PRICE RISK the hedge would have removed. The thesis that makes it more than a
  coin-flip: extreme funding marks crowded positioning that tends to mean-revert,
  so the funding-receiving side is also the contrarian side. The thesis that
  could break it: a strong trend runs the position over before funding pays.

  Because it is directional, the NON-NEGOTIABLE risk control is a HARD PRICE STOP
  on every position (HARD_STOP), evaluated against a FRESH live-book mid (never a
  stale mark). Supporting controls: a book-spread liquidity gate at entry (thin
  Lighter perps — WEN cost 870bps round-trip in the shadow evidence — are kept
  out), a post-stop cooldown (no instant re-entry in a trend), small clips, a
  funding-decay exit, and the fleet's notional / daily-loss / kill-switch rails.

EXECUTION / SAFETY — reuses the venue layer (venues/), same path Trail Blazer and
Bounce Catcher go live on:
  VENUE=hl_paper        (default) paper sim on HL data — offline-safe smoke.
  VENUE=lighter_shadow  models fills on the LIVE Lighter book, logs venue_orders,
                        NEVER sends an order — the validation mode.
  VENUE=lighter_live    REAL orders on Lighter. venues/safety.py REFUSES to start
                        unless REAL_MONEY_KILL=DISARMED_I_UNDERSTAND and a per-bot
                        notional cap env are BOTH set; the kill switch is re-checked
                        every loop and flattens on arm. Keys/disarm/deposit are the
                        operator's — this file never sets them.

Usage:
    python lighter_funding_bot.py           # dry-run forever
    python lighter_funding_bot.py --once     # single scan then exit (smoke test)
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context

BOT = "perps-funding-lighter"
H = 24 * 365

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
ORDER_USD = float(os.environ.get("FUNDING_ORDER_USD", "25"))   # small: directional
MAX_OPEN_POSITIONS = int(os.environ.get("FUNDING_MAX_OPEN", "6"))
MAX_NEW_PER_LOOP = int(os.environ.get("FUNDING_MAX_NEW_PER_LOOP", "2"))

ENTER_APR = float(os.environ.get("FUNDING_ENTER_APR", "0.40"))  # enter when |apr|>=40%
EXIT_APR = float(os.environ.get("FUNDING_EXIT_APR", "0.15"))    # leave when it cools
PERSIST_H = float(os.environ.get("FUNDING_PERSIST_H", "4"))     # hot this long first
MAX_HOLD_H = float(os.environ.get("FUNDING_MAX_HOLD_H", "72"))  # recycle after 3d
MIN_VOL = float(os.environ.get("FUNDING_MIN_VOL", "5e6"))       # 24h turnover floor
MAX_SPREAD_BPS = float(os.environ.get("FUNDING_MAX_SPREAD_BPS", "50"))  # book-spread gate

# Directional risk controls — the hard price stop is the load-bearing one.
HARD_STOP = float(os.environ.get("FUNDING_HARD_STOP", "0.05"))      # 5% adverse -> out
TAKE_PROFIT = float(os.environ.get("FUNDING_TAKE_PROFIT", "0.04"))  # 4% favourable -> lock
DAILY_LOSS_LIMIT = float(os.environ.get("FUNDING_DAILY_LOSS", "0.05"))
STOP_COOLDOWN_H = float(os.environ.get("FUNDING_STOP_COOLDOWN_H", "12"))  # quarantine after a stop
BLIND_STOP_MISSES = int(os.environ.get("FUNDING_BLIND_STOP_MISSES", "3"))  # live fail-safe

LOOP_SECONDS = int(os.environ.get("FUNDING_LOOP_SECONDS", "300"))

LOG_FILE = os.environ.get("FUNDING_LOG_FILE", "funding_lighter_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fresh_mid(ctx, coin):
    """Current mid from the LIVE book, or None if unavailable. NEVER falls back to
    the funding-map mark — that is a last-trade price frozen at client construction
    and using it on the stop path would silently freeze the stop while the real
    price runs away. Callers MUST treat None as 'cannot evaluate risk here'."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:
        return None
    if book and book.get("bids") and book.get("asks"):
        bid, ask = book["bids"][0][0], book["asks"][0][0]
        if bid and ask:
            return (bid + ask) / 2.0
    return None


def book_spread_bps(ctx, coin):
    """Top-of-book spread in bps from the live book, or None if unavailable."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:
        return None
    if book and book.get("bids") and book.get("asks"):
        bid, ask = book["bids"][0][0], book["asks"][0][0]
        mid = (bid + ask) / 2.0 if (bid and ask) else 0.0
        if mid:
            return (ask - bid) / mid * 1e4
    return None


def _record_close(bot, coin, ent_px, ent_ts, exit_px, price_pnl, fund_pnl, was_long,
                  reason, order_usd=ORDER_USD, venue=None, shadow=None):
    """Mirror a realized directional funding trade to the paper_trades ledger.
    pnl_abs = price P&L + funding accrued; pnl_pct is on the deployed clip."""
    pnl = float(price_pnl) + float(fund_pnl)
    pnl_pct = (pnl / (order_usd or 1.0)) if ent_px else None
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=pnl, pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            reason=("long_" if was_long else "short_") + reason,
            venue=venue, shadow=shadow)
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description="Yield Harvester — Lighter directional funding")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    ctx = venue_context(bot=BOT, default_hl_net="mainnet",
                        paper_start=START_EQUITY, live_flag=("--live" in sys.argv))
    bot_id = ctx.bot_id
    broker = ctx.broker
    dry_run = ctx.dry_run
    order_usd = ctx.order_usd(ORDER_USD)
    max_open = ctx.max_open_positions(MAX_OPEN_POSITIONS)
    venue_tag = None if ctx.mode == "hl_paper" else "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # Cumulative realized P&L survives restarts via the ledger.
    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:
        pass

    # Per-open bookkeeping the venue doesn't hold: is_short, entry, opened_ts,
    # accrued funding. Persisted so a redeploy doesn't reset the max-hold clock.
    meta = {}          # coin -> {is_short, entry, opened_ts, accrued}
    hot_since = {}     # coin -> ts |apr| first >= ENTER_APR
    cooldown = {}      # coin -> ts until which re-entry is blocked (post-stop)
    miss = {}          # coin -> consecutive fresh-price misses (live fail-safe)
    fund_realized = 0.0  # dry_run only: cumulative realized funding (price P&L is in broker)

    if dry_run:
        _saved = store.load_state(bot_id)
        if _saved and broker is not None and broker.restore_state(_saved.get("broker") or {}):
            meta = {str(k): v for k, v in (_saved.get("meta") or {}).items()}
            fund_realized = float(_saved.get("fund_realized") or 0.0)
            log.info("restored paper state: equity $%.2f, %d open", broker.equity(),
                     broker.open_count())
    else:
        # Live: restore open-position meta so opened_ts (max-hold clock) survives
        # a redeploy instead of resetting to now.
        _live = store.load_state(bot_id + ":live") or {}
        meta = {str(k): v for k, v in (_live.get("meta") or {}).items()}
    live_baseline = (store.load_state(bot_id + ":live") or {}).get("initial_equity") \
        if not dry_run else None

    log.info("=" * 64)
    log.info("Yield Harvester (Lighter DIRECTIONAL funding) | venue=%s (%s)",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS")
    log.info("enter |apr|>=%.0f%% persist %.0fh, exit<%.0f%% | HARD STOP %.0f%% / TP %.0f%% "
             "| $%.0f x max %d | vol>=$%.0fM spread<=%.0fbps | loop=%ds", ENTER_APR * 100,
             PERSIST_H, EXIT_APR * 100, HARD_STOP * 100, TAKE_PROFIT * 100, order_usd,
             max_open, MIN_VOL / 1e6, MAX_SPREAD_BPS, LOOP_SECONDS)
    log.info("DIRECTIONAL — not delta-neutral; price risk bounded by the hard stop.")
    log.info("=" * 64)

    def account_value():
        return broker.equity() if dry_run else ctx.venue.account_value()

    def positions():
        if dry_run:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        return ctx.venue.positions()

    def _flatten_all(reason):
        """Emergency flatten that MIRRORS normal-close bookkeeping (ledger + counters
        + meta pop) so forensic reconstruction stays consistent with account equity."""
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
            is_short = m.get("is_short", held < 0)
            entry = m.get("entry") or (live_pos.get(c, {}) or {}).get("entry") or 0.0
            opened_ts = m.get("opened_ts") or time.time()
            px = fresh_mid(ctx, c) or entry
            try:
                ctx.venue.market_close(c)
            except Exception as e:
                log.error("flatten %s: %s", c, e)
                continue
            price_pnl = abs(held) * ((px - entry) if not is_short else (entry - px))
            n_closed += 1
            n_wins += 1 if price_pnl > 0 else 0
            _record_close(bot_id, c, entry, opened_ts, px, price_pnl, m.get("accrued", 0.0),
                          was_long=not is_short, reason=reason, order_usd=order_usd,
                          venue=venue_tag, shadow=shadow_tag)
            try:
                store.publish_venue_order(
                    bot_id, venue=("lighter" if venue_tag else "hl"), shadow=shadow_tag,
                    coin=c, side=("buy" if is_short else "sell"), size=abs(held),
                    px_decision=px, px_fill=px, raw={"reason": reason, "leg": "close"})
            except Exception:
                pass
            meta.pop(c, None)
            hot_since.pop(c, None)

    try:
        day_start_equity = account_value()
    except Exception as e:
        log.warning("account value unreadable (%s); loss-limit waits.", e)
        day_start_equity = None
    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    last_ts = time.time()

    while True:
        t0 = time.time()
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            try:
                day_start_equity = account_value()
            except Exception:
                pass

        # kill switch (live) — flatten every held coin and halt on arm.
        if not dry_run and ctx.rails.kill_check():
            log.error("REAL_MONEY_KILL armed mid-run — flatten + halt.")
            halted_today = True
            _flatten_all("kill_switch")

        try:
            equity = account_value()
        except Exception as e:
            log.warning("account value unavailable: %s", e)
            equity = None

        _fleet_loss = (not dry_run and ctx.rails.daily_loss_hit(day_start_equity, equity))
        if (not halted_today and equity is not None and day_start_equity
                and (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT) or _fleet_loss)):
            log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f). Flatten + halt.",
                        equity, day_start_equity)
            halted_today = True
            if not dry_run:
                _flatten_all("daily_loss")

        if halted_today:
            log.info("halted for today; sleeping.")
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            fund = ctx.venue.funding_map()
        except Exception as e:
            log.warning("funding fetch failed (%s); retry next loop.", e)
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            pos = positions()
        except Exception as e:
            log.warning("positions unreadable: %s", e)
            if not dry_run:
                # Acting on a phantom-empty set would zero open_now AND the cap
                # input, defeating max_open and the notional cap — skip the loop.
                if args.once:
                    break
                time.sleep(LOOP_SECONDS)
                continue
            pos = {}

        dt_h = (t0 - last_ts) / 3600.0
        last_ts = t0

        # ---- manage open positions (held coins may no longer be hot) ----
        held_coins = set(pos) | set(meta)
        opened_this_loop = 0
        for coin in list(held_coins):
            held = pos.get(coin, {}).get("size", 0.0)
            if not held:
                meta.pop(coin, None)
                continue
            f = fund.get(coin) or {}
            rate = f.get("rate")
            apr = (rate * H) if rate is not None else None
            m = meta.get(coin) or {}
            is_short = m.get("is_short", held < 0)
            entry = m.get("entry") or pos.get(coin, {}).get("entry") or 0.0
            opened_ts = m.get("opened_ts") or t0

            px = fresh_mid(ctx, coin)
            if px is None:
                # No live book -> the hard stop cannot be evaluated. Never pretend
                # with a stale mark. Log; in live, fail-safe flatten after N misses.
                miss[coin] = miss.get(coin, 0) + 1
                log.warning("%s: no live book (%d) — hard stop unverifiable", coin, miss[coin])
                if not dry_run and miss[coin] >= BLIND_STOP_MISSES:
                    log.error("%s: stop unverifiable %dx — fail-safe flatten", coin, miss[coin])
                    try:
                        ctx.venue.market_close(coin)
                        _record_close(bot_id, coin, entry, opened_ts, entry, 0.0,
                                      m.get("accrued", 0.0), was_long=not is_short,
                                      reason="stop_blind", order_usd=order_usd,
                                      venue=venue_tag, shadow=shadow_tag)
                        n_closed += 1
                        meta.pop(coin, None)
                        hot_since.pop(coin, None)
                        miss.pop(coin, None)
                    except Exception as e:
                        log.error("fail-safe close %s: %s", coin, e)
                continue
            miss.pop(coin, None)
            if dry_run:
                broker.mark(coin, px)   # feed the live mid so paper equity tracks open P&L
            notional = abs(held) * px

            if rate is not None:
                # Accrue modeled funding in BOTH modes: dry_run adds it to equity;
                # live uses it only for the per-trade ledger + win count (the real
                # funding is already in account_value, so open_fund/realized stay
                # dry_run-guarded to avoid double-counting).
                accr = (1.0 if is_short else -1.0) * rate * notional * dt_h
                m["accrued"] = m.get("accrued", 0.0) + accr
            meta[coin] = {**m, "is_short": is_short, "entry": entry, "opened_ts": opened_ts}

            held_h = (t0 - opened_ts) / 3600.0
            raw = (px - entry) / entry if entry else 0.0        # +ve = price rose
            # A SHORT loses when price rises (+raw is against us); a LONG loses
            # when price falls (so its adverse is -raw). +ve adverse == against us.
            adverse = raw if is_short else -raw
            favour = -adverse
            flipped = (apr is not None) and ((is_short and apr < 0) or (not is_short and apr > 0))

            decision = None
            if adverse >= HARD_STOP:
                decision = "stop"
            elif favour >= TAKE_PROFIT:
                decision = "take_profit"
            elif flipped:
                decision = "flip"
            elif apr is not None and abs(apr) < EXIT_APR:
                decision = "decay"
            elif held_h >= MAX_HOLD_H:
                decision = "max_hold"
            if decision is None:
                continue

            fund_pnl = m.get("accrued", 0.0)
            if dry_run:
                price_pnl = broker.close(coin, px)   # realizes price P&L in broker
                fund_realized += fund_pnl
            else:
                try:
                    ctx.venue.market_close(coin)
                except Exception as e:
                    log.error("close %s failed: %s — leaving position, retry next loop", coin, e)
                    continue
                price_pnl = (abs(held) * (px - entry)) if not is_short \
                    else (abs(held) * (entry - px))
            realized += (price_pnl + fund_pnl) if dry_run else 0.0
            n_closed += 1
            n_wins += 1 if (price_pnl + fund_pnl) > 0 else 0
            log.info("CLOSE %s %s after %.1fh | price %+.2f funding %+.2f [%s]",
                     coin, "short" if is_short else "long", held_h, price_pnl,
                     fund_pnl, decision)
            _record_close(bot_id, coin, entry, opened_ts, px, price_pnl, fund_pnl,
                          was_long=not is_short, reason=decision, order_usd=order_usd,
                          venue=venue_tag, shadow=shadow_tag)
            try:
                store.publish_venue_order(
                    bot_id, venue=("lighter" if venue_tag else "hl"),
                    shadow=shadow_tag, coin=coin,
                    side=("buy" if is_short else "sell"), size=abs(held),
                    px_decision=px, px_fill=px, raw={"reason": decision, "leg": "close"})
            except Exception:
                pass
            meta.pop(coin, None)
            hot_since.pop(coin, None)      # force a fresh persistence wait — no instant re-entry
            if decision == "stop":
                cooldown[coin] = t0 + STOP_COOLDOWN_H * 3600.0   # quarantine after a stop

        # ---- persistence clock over the whole funding map ----
        for c, f in fund.items():
            r = f.get("rate")
            if r is not None and abs(r * H) >= ENTER_APR:
                hot_since.setdefault(c, t0)
            else:
                hot_since.pop(c, None)

        # ---- scan for new entries ----
        open_now = sum(1 for v in pos.values() if (v.get("size") if isinstance(v, dict) else v))
        if open_now < max_open:
            cands = []
            for c, f in fund.items():
                if c in meta or c in pos:
                    continue
                if c in cooldown and t0 < cooldown[c]:
                    continue
                r = f.get("rate")
                if r is None:
                    continue
                apr = r * H
                if abs(apr) < ENTER_APR or (f.get("vol") or 0.0) < MIN_VOL:
                    continue
                if (t0 - hot_since.get(c, t0)) / 3600.0 < PERSIST_H:
                    continue
                if not ctx.supports(c):
                    continue
                cands.append((c, f, apr))
            cands.sort(key=lambda x: -abs(x[2]))
            for coin, f, apr in cands:
                if open_now >= max_open or opened_this_loop >= MAX_NEW_PER_LOOP:
                    break
                # book-spread liquidity gate — keeps thin traps (WEN 870bps) out.
                sp = book_spread_bps(ctx, coin)
                if sp is None or sp > MAX_SPREAD_BPS:
                    log.info("%s SPREAD_SKIP (%.0fbps)", coin, sp if sp is not None else -1)
                    continue
                is_short = apr > 0                 # funding>0 -> longs pay -> we SHORT
                px = fresh_mid(ctx, coin)
                if px is None:
                    continue
                size = round(order_usd / px, 6)
                if not dry_run:
                    open_ntl = sum(1 for v in pos.values()
                                   if (v.get("size") if isinstance(v, dict) else v)) * order_usd
                    if not ctx.rails.notional_ok(open_ntl, order_usd):
                        log.info("%s NOTIONAL_CAP_SKIP", coin)
                        continue
                try:
                    if dry_run:
                        broker.open(coin, not is_short, size, px)
                    else:
                        ctx.venue.market_open(coin, not is_short, size)
                except Exception as e:
                    log.error("open %s failed: %s", coin, e)
                    continue
                meta[coin] = {"is_short": is_short, "entry": px, "opened_ts": t0,
                              "accrued": 0.0}
                open_now += 1
                opened_this_loop += 1
                log.info("OPEN %s %s $%.0f | funding %+.1f%% APR | px %.6g | spread %.0fbps",
                         coin, "short" if is_short else "long", order_usd, apr, px, sp)
                try:
                    store.publish_venue_order(
                        bot_id, venue=("lighter" if venue_tag else "hl"),
                        shadow=shadow_tag, coin=coin,
                        side=("sell" if is_short else "buy"), size=size,
                        px_decision=px, px_fill=px,
                        raw={"apr": round(apr, 3), "spread_bps": round(sp, 1), "leg": "open"})
                except Exception:
                    pass

        # ---- publish snapshot ----
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
        top = sorted(((c, f.get("rate") or 0.0) for c, f in fund.items()),
                     key=lambda cr: -abs(cr[1]))[:3]
        try:
            store.publish(
                bot_id, status="paper" if ctx.mode == "hl_paper" and dry_run
                else ("halted" if halted_today else "online"),
                equity=pub_equity, pnl_abs=pub_pnl, open_trades=pub_open,
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": ctx.mode, "venue": ctx.mode, "style": "directional-funding",
                       "held": {c: ("S" if (meta.get(c) or {}).get("is_short") else "L")
                                for c in meta},
                       "hottest_apr": {c: f"{r*H:+.0%}" for c, r in top}})
        except Exception:
            pass
        # persist state (dry_run: full paper account; live: baseline + open meta)
        try:
            if dry_run:
                store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                          "fund_realized": fund_realized})
            elif live_baseline is not None:
                store.save_state(bot_id + ":live", {"initial_equity": live_baseline,
                                                    "meta": meta})
        except Exception:
            pass

        held = ", ".join(f"{c}({'S' if (meta.get(c) or {}).get('is_short') else 'L'})"
                         for c in meta) or "none"
        log.info("scan ok | %d perps | held: %s | realized $%+.2f", len(fund), held, realized)

        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


if __name__ == "__main__":
    main()
