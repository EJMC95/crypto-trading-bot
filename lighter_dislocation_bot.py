#!/usr/bin/env python3
"""
lighter_dislocation_bot.py — 🧲 Snap Back (Lighter dislocation harvester).

WHAT / WHY (2026-07-11)
  On 11 Jul a Lighter mark printed ~25% away from Binance/HL for minutes and a
  bot on the WRONG side of it (Trail Blazer's loss rail) paid $3.85. This bot
  is the other side of that trade: when a Lighter book dislocates from a deep
  independent reference (Hyperliquid mainnet mids), take the reconvergence —
  BUY Lighter when it prints cheap, SHORT when it prints rich, exit when the
  gap closes. Thin new venue + zero fees + small clips is precisely the niche
  where small capital has an edge big money can't be bothered with.

  UNVALIDATED. This bot's first job is EVIDENCE, not profit: a census of every
  dislocation >= PRE_BPS (frequency, size, depth, duration) plus honest
  modelled fills (entry at the clip's book VWAP — the price you'd REALLY pay).
  VENUE=lighter_live REFUSES to start in v1; go-live is a separate decision on
  the shadow record, like every bot before it (see GO_LIVE_LIGHTER.md).

RISK MODEL (why each gate exists)
  * Ghost prints: a "dislocation" with no real depth can't be traded — entry
    requires the clip's VWAP within MAX_ENTRY_SLIP_BPS of touch, and the
    signal must persist CONFIRM_LOOPS consecutive loops before entry.
  * Real repricing: if Lighter is right (news) the gap never closes — hard
    price stop (HARD_STOP) + MAX_HOLD_S cap the bet; no averaging down.
  * Reference-blind: no HL mids -> no signal -> do nothing (never trade
    against a reference we can't see).
  * Fleet furniture: kill switch re-checked every loop, durable daily-loss
    halt (SafetyRails.confirm_daily_loss debounce), halted heartbeat, all
    fills ledgered to venue_orders with px_decision vs px_fill.

Usage:
    VENUE=lighter_shadow python lighter_dislocation_bot.py          # daemon
    VENUE=lighter_shadow python lighter_dislocation_bot.py --once   # smoke
"""
import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context

BOT = "lighter-dislocation"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
COINS = os.environ.get(
    "DISLOC_COINS",
    "BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,SUI,LTC,ADA,DOT,AAVE,HYPE,NEAR,BCH"
).split(",")
ORDER_USD = float(os.environ.get("DISLOC_ORDER_USD", "10"))
MAX_OPEN_POSITIONS = int(os.environ.get("DISLOC_MAX_OPEN", "3"))

PRE_BPS = float(os.environ.get("DISLOC_PRE_BPS", "50"))       # census floor
ENTER_BPS = float(os.environ.get("DISLOC_ENTER_BPS", "150"))  # tradeable gap
EXIT_BPS = float(os.environ.get("DISLOC_EXIT_BPS", "40"))     # converged
CONFIRM_LOOPS = int(os.environ.get("DISLOC_CONFIRM_LOOPS", "2"))
MAX_ENTRY_SLIP_BPS = float(os.environ.get("DISLOC_MAX_ENTRY_SLIP_BPS", "30"))
HARD_STOP = float(os.environ.get("DISLOC_HARD_STOP", "0.05"))
MAX_HOLD_S = float(os.environ.get("DISLOC_MAX_HOLD_S", "7200"))
# [2026-07-16 ZOMBIE GUARD] a held coin whose HL reference vanished, whose
# Lighter book went dark, or that got delisted skipped even the HARD STOP
# (`continue` before the manage block). Give up at the last usable exit
# price after this long unmanageable — but only while the reference feed
# itself is alive (a whole-feed outage must never flatten the book).
DELIST_GIVEUP_H = float(os.environ.get("DISLOC_DELIST_GIVEUP_H", "6"))
DAILY_LOSS_LIMIT = float(os.environ.get("DISLOC_DAILY_LOSS", "0.05"))

LOOP_SECONDS = int(os.environ.get("DISLOC_LOOP_SECONDS", "90"))
HL_INFO = "https://api.hyperliquid.xyz/info"

LOG_FILE = os.environ.get("DISLOC_LOG_FILE", "lighter_dislocation_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def hl_mids():
    """Independent reference: HL mainnet mids for EVERY coin in one call.
    Returns {coin: mid} or {} — {} means reference-blind, callers must skip."""
    try:
        body = json.dumps({"type": "allMids"}).encode()
        req = urllib.request.Request(
            HL_INFO, data=body, headers={"Content-Type": "application/json"})
        raw = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return {c: float(v) for c, v in raw.items() if float(v) > 0}
    except Exception as e:  # noqa: BLE001
        log.warning("HL reference mids unavailable: %s", e)
        return {}


def book_view(ctx, coin, clip_usd):
    """One read of the live Lighter book -> dict with mid, spread_bps and the
    clip's buy/sell VWAP + slip vs touch. None = unreadable (skip the coin).
    Levels are sorted here — the REST snapshot fallback returns them unsorted."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:  # noqa: BLE001
        return None
    if not book:
        return None
    bids = sorted([(p, s) for p, s in (book.get("bids") or []) if p > 0 and s > 0],
                  reverse=True)
    asks = sorted([(p, s) for p, s in (book.get("asks") or []) if p > 0 and s > 0])
    if not bids or not asks:
        return None
    mid = (bids[0][0] + asks[0][0]) / 2.0
    spread_bps = (asks[0][0] - bids[0][0]) / mid * 1e4

    def vwap(levels, usd):
        want = usd
        cost = qty = 0.0
        for px, sz in levels:
            take_usd = min(want, px * sz)
            cost += take_usd
            qty += take_usd / px
            want -= take_usd
            if want <= 1e-9:
                break
        if want > 1e-9 or qty <= 0:
            return None          # book too thin for the clip
        return cost / qty

    buy_vwap = vwap(asks, clip_usd)
    sell_vwap = vwap(bids, clip_usd)
    return {
        "mid": mid, "spread_bps": spread_bps,
        "buy_vwap": buy_vwap, "sell_vwap": sell_vwap,
        "buy_slip_bps": ((buy_vwap / asks[0][0] - 1) * 1e4
                         if buy_vwap else None),
        "sell_slip_bps": ((1 - sell_vwap / bids[0][0]) * 1e4
                          if sell_vwap else None),
    }


def _record_close(bot, coin, ent_px, ent_ts, exit_px, pnl, was_long, reason,
                  venue=None, shadow=None):
    pnl_pct = None
    if ent_px:
        pnl_pct = ((exit_px - ent_px) / ent_px) if was_long else ((ent_px - exit_px) / ent_px)
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=float(pnl), pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            reason=("long_" if was_long else "short_") + reason,
            venue=venue, shadow=shadow)
    except Exception:  # noqa: BLE001
        pass


def main():
    p = argparse.ArgumentParser(description="Snap Back — Lighter dislocation harvester")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    # [2026-07-16 AUDIT] a lost Railway VENUE var silently booted hl_paper:
    # unsuffixed row id (the -lshadow row went stale) + HL reference data
    # under a Lighter-named bot (dev≈0 forever). The sniper already guards
    # itself this way; this bot is Lighter-shadow by definition.
    os.environ.setdefault("VENUE", "lighter_shadow")
    ctx = venue_context(bot=BOT, default_hl_net="mainnet",
                        paper_start=START_EQUITY, live_flag=False)
    # [v1 GATE] UNVALIDATED — the census + shadow ledger must earn a separate,
    # explicit go-live first (own sub-account, like every bot before it).
    if ctx.mode == "lighter_live":
        raise SystemExit("lighter-dislocation is UNVALIDATED — v1 refuses "
                         "lighter_live. Run VENUE=lighter_shadow to build the "
                         "evidence; go-live is a separate decision.")
    bot_id = ctx.bot_id
    broker = ctx.broker
    order_usd = ctx.order_usd(ORDER_USD, own=True)   # backtested $10 clip
    # [2026-07-16 AUDIT] the bot's own cap stays senior: floor(cap/clip) can
    # exceed DISLOC_MAX_OPEN when a notional-cap env is set (the sniper
    # already min()s — this didn't).
    max_open = min(MAX_OPEN_POSITIONS, ctx.max_open_positions(MAX_OPEN_POSITIONS))
    shadow_tag = ctx.mode == "lighter_shadow"

    meta = {}            # coin -> {is_long, entry, opened_ts, ref_at_entry}
    census = {}          # coin -> {count, max_bps, last_iso}
    pend = {}            # coin -> consecutive loops the entry signal has held
    _saved = store.load_state(bot_id)
    if _saved:
        if broker is not None and broker.restore_state(_saved.get("broker") or {}):
            meta = {str(k): v for k, v in (_saved.get("meta") or {}).items()}
            log.info("restored shadow state: equity $%.2f, %d open",
                     broker.equity(), broker.open_count())
        census = {str(k): v for k, v in (_saved.get("census") or {}).items()}

    n_closed, n_wins = 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            n_closed, n_wins = agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    log.info("=" * 64)
    log.info("Snap Back (Lighter DISLOCATION harvester) | venue=%s | %d coins",
             ctx.mode, len(COINS))
    log.info("census>=%.0fbps | enter>=%.0fbps x%d confirms | exit<=%.0fbps | "
             "clip-slip<=%.0fbps | stop %.0f%% | max hold %.0fmin | $%.0f x %d | loop=%ds",
             PRE_BPS, ENTER_BPS, CONFIRM_LOOPS, EXIT_BPS, MAX_ENTRY_SLIP_BPS,
             HARD_STOP * 100, MAX_HOLD_S / 60, order_usd, max_open, LOOP_SECONDS)
    log.info("EVIDENCE-FIRST: shadow fills modelled at the clip's real book "
             "VWAP; every event ledgered. lighter_live REFUSED in v1.")
    log.info("=" * 64)

    def account_value():
        return broker.equity()

    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    _halt = store.load_daily_halt(bot_id, cur_day.isoformat())
    if _halt:
        halted_today = True
        log.warning("daily-loss halt restored from state — halted for the rest of today.")
    day_start_equity = account_value()

    while True:
        now = datetime.now(timezone.utc)
        t0 = time.time()
        # [2026-07-12 GO-GREEN] loop-top liveness touch — see bot_pnl_store.heartbeat
        store.heartbeat(bot_id)
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            day_start_equity = account_value()

        equity = account_value()
        if (not halted_today and equity is not None and day_start_equity
                and equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)):
            # [2026-07-11 RAIL DEBOUNCE] shared fail-safe confirm (see safety.py)
            _confirmed, equity = ctx.rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT, account_value)
            if _confirmed:
                log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f). Close all + halt.",
                            equity, day_start_equity)
                halted_today = True
                store.save_daily_halt(bot_id, cur_day.isoformat(), day_start_equity)
                for c in list(meta):
                    bv = book_view(ctx, c, order_usd)
                    px = (bv and (bv["sell_vwap"] if meta[c]["is_long"] else bv["buy_vwap"])) \
                        or meta[c]["entry"]
                    pnl = broker.close(c, px)
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    _record_close(bot_id, c, meta[c]["entry"], meta[c]["opened_ts"],
                                  px, pnl, meta[c]["is_long"], "rail_flatten",
                                  venue="lighter", shadow=shadow_tag)
                    meta.pop(c, None)

        if halted_today:
            log.info("halted for today; sleeping.")
            try:
                store.publish(bot_id, status="halted", equity=broker.equity(),
                              pnl_abs=broker.equity() - START_EQUITY,
                              closed_trades=n_closed, wins=n_wins,
                              losses=n_closed - n_wins,
                              extra={"mode": ctx.mode, "venue": ctx.mode,
                                     "style": "dislocation"})
            except Exception:  # noqa: BLE001
                pass
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        ref = hl_mids()
        # [2026-07-11 INSTRUMENT-FIRST] market-context snapshot (market_context.py)
        # rides along on census events + entry ledger rows — the dislocation<->
        # liquidation correlation is this bot's core hypothesis to validate.
        try:
            _mctx = store.load_state("market-context") or {}
        except Exception:  # noqa: BLE001
            _mctx = {}

        def _mctx_slice(coin):
            c = (_mctx.get("coins") or {}).get(coin) or {}
            return {"heat": _mctx.get("heat_mean_apr"),
                    "btc_vol": _mctx.get("btc_vol_1h"),
                    "oi_chg_1h": c.get("oi_chg_1h"),
                    "liq_5m": c.get("liq_5m"), "liq_1h": c.get("liq_1h")}

        events_this_loop = 0
        managed = set()   # held coins the manage block could actually price
        if ref:
            for coin in COINS:
                r = ref.get(coin)
                if not r or not ctx.supports(coin):
                    continue
                bv = book_view(ctx, coin, order_usd)
                if bv is None:
                    continue
                dev_bps = (bv["mid"] / r - 1) * 1e4
                held = meta.get(coin)

                # ---- census: every observed dislocation is evidence ----
                if abs(dev_bps) >= PRE_BPS:
                    events_this_loop += 1
                    rec = census.setdefault(coin, {"count": 0, "max_bps": 0.0,
                                                   "last_iso": None})
                    rec["count"] += 1
                    rec["max_bps"] = max(rec["max_bps"], abs(dev_bps))
                    # [2026-07-14] Count ENTRY-GRADE events separately — the
                    # promotion review needs tradeable DENSITY, and count/max
                    # alone can't say how many prints cleared the entry gate.
                    if abs(dev_bps) >= ENTER_BPS:
                        rec["count_enter"] = int(rec.get("count_enter") or 0) + 1
                    rec["last_iso"] = now.isoformat()
                    rec["last_mctx"] = _mctx_slice(coin)
                    log.info("DISLOC %-5s %+7.1fbps mid=%.6g ref=%.6g "
                             "spread=%.0fbps slip(b/s)=%s/%s%s",
                             coin, dev_bps, bv["mid"], r, bv["spread_bps"],
                             f"{bv['buy_slip_bps']:.0f}" if bv["buy_slip_bps"] is not None else "-",
                             f"{bv['sell_slip_bps']:.0f}" if bv["sell_slip_bps"] is not None else "-",
                             " [held]" if held else "")

                # ---- manage an open position ----
                if held:
                    is_long = held["is_long"]
                    ent = held["entry"]
                    exit_px = bv["sell_vwap"] if is_long else bv["buy_vwap"]
                    if exit_px is None:
                        continue
                    managed.add(coin)
                    held.pop("no_px_since", None)   # priceable — reset clock
                    held["last_px"] = exit_px
                    reason = None
                    if abs(dev_bps) <= EXIT_BPS:
                        reason = "converged"
                    elif (is_long and exit_px <= ent * (1 - HARD_STOP)) or \
                         (not is_long and exit_px >= ent * (1 + HARD_STOP)):
                        reason = "stop"      # repricing, not dislocation
                    elif time.time() - held["opened_ts"] >= MAX_HOLD_S:
                        reason = "max_hold"
                    if reason:
                        pnl = broker.close(coin, exit_px)
                        n_closed += 1
                        n_wins += 1 if pnl > 0 else 0
                        log.info("CLOSE %s %s $%+.3f [%s] dev now %+.0fbps",
                                 coin, "long" if is_long else "short", pnl,
                                 reason, dev_bps)
                        _record_close(bot_id, coin, ent, held["opened_ts"],
                                      exit_px, pnl, is_long, reason,
                                      venue="lighter", shadow=shadow_tag)
                        try:
                            store.publish_venue_order(
                                bot_id, venue="lighter", shadow=True, coin=coin,
                                side=("sell" if is_long else "buy"),
                                size=order_usd / exit_px,
                                px_decision=bv["mid"], px_fill=exit_px,
                                spread_bps=bv["spread_bps"],
                                slippage_bps=abs(exit_px / bv["mid"] - 1) * 1e4,
                                raw={"leg": "close", "reason": reason,
                                     "dev_bps": dev_bps})
                        except Exception:  # noqa: BLE001
                            pass
                        meta.pop(coin, None)
                    continue

                # ---- entry: confirmed, deep, tradeable dislocation ----
                tradeable = abs(dev_bps) >= ENTER_BPS
                pend[coin] = pend.get(coin, 0) + 1 if tradeable else 0
                if not tradeable or pend[coin] < CONFIRM_LOOPS:
                    continue
                if broker.open_count() >= max_open:
                    continue
                is_long = dev_bps < 0            # Lighter cheap -> buy the snap back
                fill = bv["buy_vwap"] if is_long else bv["sell_vwap"]
                slip = bv["buy_slip_bps"] if is_long else bv["sell_slip_bps"]
                if fill is None or slip is None or slip > MAX_ENTRY_SLIP_BPS:
                    log.info("SKIP %s %+.0fbps — ghost print (clip slip %s > %.0fbps)",
                             coin, dev_bps, f"{slip:.0f}" if slip is not None else "n/a",
                             MAX_ENTRY_SLIP_BPS)
                    continue
                size = order_usd / fill
                broker.open(coin, is_long, size, fill)
                meta[coin] = {"is_long": is_long, "entry": fill,
                              "opened_ts": time.time(), "ref_at_entry": r}
                pend[coin] = 0
                log.info("OPEN %s %s $%.0f @ %.6g (dev %+.0fbps, slip %.0fbps)",
                         coin, "LONG" if is_long else "SHORT", order_usd, fill,
                         dev_bps, slip)
                try:
                    store.publish_venue_order(
                        bot_id, venue="lighter", shadow=True, coin=coin,
                        side=("buy" if is_long else "sell"), size=size,
                        px_decision=bv["mid"], px_fill=fill,
                        spread_bps=bv["spread_bps"], slippage_bps=slip,
                        raw={"leg": "open", "dev_bps": dev_bps,
                             "ref": r, "confirms": CONFIRM_LOOPS,
                             "mctx": _mctx_slice(coin)})
                except Exception:  # noqa: BLE001
                    pass
            # [2026-07-16 ZOMBIE GUARD] held coins the loop above could not
            # manage this pass (ref gone for THIS coin / unsupported / book
            # dark / removed from COINS). Runs only inside `if ref:` so a
            # whole-feed outage never advances the clocks.
            for coin in [c for c in list(meta) if c not in managed]:
                held = meta.get(coin) or {}
                first = held.get("no_px_since")
                if not isinstance(first, (int, float)):
                    held["no_px_since"] = time.time()
                    meta[coin] = held
                    continue
                if (time.time() - first) / 3600.0 < DELIST_GIVEUP_H:
                    continue
                ent = held.get("entry") or 0.0
                zpx = float(held.get("last_px") or ent or 0.0)
                if not zpx:
                    continue
                pnl = broker.close(coin, zpx)
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                _record_close(bot_id, coin, ent, held.get("opened_ts"), zpx,
                              pnl, held.get("is_long", True), "delisted",
                              venue="lighter", shadow=shadow_tag)
                meta.pop(coin, None)
                log.warning("DELIST GIVE-UP CLOSE %s @ %.6g", coin, zpx)
        else:
            log.info("reference-blind (no HL mids) — no signals this loop.")

        # ---- publish + persist ----
        try:
            store.publish(
                bot_id, status="online",
                equity=broker.equity(),
                pnl_abs=broker.equity() - START_EQUITY,
                open_trades=broker.open_count(),
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": ctx.mode, "venue": ctx.mode, "style": "dislocation",
                       "held": sorted(meta.keys()),
                       "census_events": sum(c["count"] for c in census.values()),
                       "census_max_bps": round(max((c["max_bps"] for c in census.values()),
                                                   default=0.0), 1)})
        except Exception:  # noqa: BLE001
            pass
        try:
            store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                      "census": census})
        except Exception:  # noqa: BLE001
            pass

        log.info("scan ok | %d coins | held: %s | census: %d events, max %.0fbps",
                 len(COINS), ", ".join(sorted(meta)) or "none",
                 sum(c["count"] for c in census.values()),
                 max((c["max_bps"] for c in census.values()), default=0.0))
        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _supervised():
    """[2026-07-12 GO-GREEN] unhandled exception -> log, mark row ERROR,
    restart in 60s (state re-hydrates). SystemExit/Ctrl-C pass through."""
    while True:
        try:
            main()
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            log.exception("unhandled exception — marking row ERROR, restarting in 60s")
            try:
                store.set_status(BOT + "-lshadow", "error")
            except Exception:  # noqa: BLE001
                pass
            time.sleep(60)


if __name__ == "__main__":
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
