#!/usr/bin/env python3
"""
lighter_perp_sniper.py — Lighter-native NEW-PERP-LISTING sniper.

The spiritual analog of the spot Launch Sniper, but for a perps DEX: instead of
brand-new spot pairs across 100 CCXT exchanges, it snipes brand-new PERP MARKETS
the moment Lighter lists them. Built 2026-07-09 at Eamon's request to replace the
spot sniper (which can't run on a fixed-market perps venue) — UNVALIDATED, so it
runs SHADOW-FIRST and only trades real money once he explicitly disarms the kill
switch (venues/safety.py). There is no historical edge to point to here; the
shadow ledger is how we find out whether one exists.

DETECTION (deterministic — the source of truth):
  Diff the current set of active Lighter perp markets against a persisted
  baseline. A symbol present now but not in the baseline = a fresh listing. The
  first run SEEDS the baseline with all current markets and buys nothing (so it
  never snipes the existing 215). AnnouncementApi text is attached as CONTEXT
  only (e.g. "New RWA Perp Listing — $WEN"), never trusted as the trigger.

TRADE (long-biased new-listing pop, tight risk):
  On a new market: open one LONG clip (LIGHTER_ORDER_USD, default $20), then
  manage with take-profit / stop-loss / max-hold. One position per new market,
  global cap, adapter-level notional cap + daily-loss halt from venues/safety.py.

MODES (venues layer): Lighter-only. Defaults to lighter_shadow; refuses hl_paper.
    VENUE=lighter_shadow  (default) live books, modelled fills, ledger, no send
    VENUE=lighter_testnet real order lifecycle on testnet (faucet funds)
    VENUE=lighter_live    real money — refuses to boot unless REAL_MONEY_KILL
                          is explicitly disarmed (default ARMED)

Usage:
    python lighter_perp_sniper.py            # shadow forever
    python lighter_perp_sniper.py --once     # single scan then exit (smoke)
"""
import argparse
import os
import sys
import time
import logging
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context

BOT = "lighter-perp-sniper"

# --------------------------- configuration ----------------------------------
PAPER_START = 1000.0
TAKE_PROFIT_PCT = 0.15      # +15%: new listings pop hard or not at all
STOP_LOSS_PCT = 0.10       # -10% hard stop
MAX_HOLD_SEC = 6 * 3600    # 6h — snipe the debut move, don't marry it
MAX_OPEN = 4               # global cap on concurrent snipes
LOOP_SECONDS = 60          # poll the market list every minute
DIRECTION_LONG = os.environ.get("SNIPER_DIRECTION", "long").lower() != "short"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("lighter_perp_sniper.log"),
              logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def _mid(book):
    """Mid price from a {bids,asks} book, or None if a side is empty."""
    if book and book.get("bids") and book.get("asks"):
        return (book["bids"][0][0] + book["asks"][0][0]) / 2
    return None


def _announcement_tag(anns, symbol):
    """Return a short context string if a recent announcement mentions `symbol`."""
    for a in anns or []:
        blob = f"{a.get('title', '')} {a.get('content', '')}"
        if symbol in blob or f"${symbol}" in blob:
            return (a.get("title") or "announced").strip()[:60]
    return None


def main():
    ap = argparse.ArgumentParser(description="Lighter new-perp-listing sniper")
    ap.add_argument("--once", action="store_true", help="single scan then exit")
    args = ap.parse_args()

    # Lighter-only: default to shadow, and refuse the hl_paper default outright —
    # sniping Lighter listings on a Hyperliquid client makes no sense.
    os.environ.setdefault("VENUE", "lighter_shadow")
    ctx = venue_context(bot=BOT, paper_start=PAPER_START)
    if ctx.mode == "hl_paper":
        log.error("lighter_perp_sniper is Lighter-only. Set VENUE=lighter_shadow"
                  " | lighter_testnet | lighter_live.")
        sys.exit(2)
    bot_id = ctx.bot_id
    broker = ctx.broker
    dry_run = ctx.dry_run
    order_usd = ctx.order_usd(20.0)
    max_open = min(MAX_OPEN, ctx.max_open_positions(MAX_OPEN))
    venue_tag = "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # Restore paper account + baseline + open snipes from Postgres.
    entry_ts = {}
    baseline = set()
    _saved = store.load_state(bot_id) if dry_run else None
    if _saved:
        if dry_run and broker.restore_state(_saved.get("broker") or {}):
            log.info("restored paper state: equity $%.2f, %d open",
                     broker.equity(), broker.open_count())
        baseline = set(_saved.get("baseline") or [])
        entry_ts = {str(k): float(v) for k, v in (_saved.get("entry_ts") or {}).items()}

    log.info("=" * 64)
    log.info("Lighter NEW-PERP sniper | venue=%s (%s) | dir=%s | clip $%.0f | "
             "TP +%.0f%% SL -%.0f%% hold %.0fh | cap %d",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS",
             "long" if DIRECTION_LONG else "short", order_usd,
             TAKE_PROFIT_PCT * 100, STOP_LOSS_PCT * 100, MAX_HOLD_SEC / 3600, max_open)
    log.info("=" * 64)

    def record_close(coin, ent_px, ent_ts, exit_px, pnl, was_long, reason):
        pnl_pct = None
        if ent_px:
            pnl_pct = ((exit_px - ent_px) / ent_px) if was_long else ((ent_px - exit_px) / ent_px)
        oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
        store.publish_paper_trade(
            bot_id, trade_id=f"{coin}:{ent_ts}", pnl_abs=float(pnl), pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            reason=("long_" if was_long else "short_") + reason,
            venue=venue_tag, shadow=shadow_tag)

    realized_seeded = False
    while True:
        now = datetime.now(timezone.utc)
        try:
            markets = ctx.venue.refresh_markets()
        except Exception as e:  # noqa: BLE001
            log.warning("market refresh failed: %s; retry next loop", e)
            if args.once:
                return
            time.sleep(LOOP_SECONDS)
            continue

        active = {s for s, m in markets.items() if m.get("status") == "active"}

        # First ever run: SEED the baseline, snipe nothing (never buy the 215).
        if not baseline:
            baseline = set(active)
            store.save_state(bot_id, {"baseline": sorted(baseline),
                                      "broker": broker.to_state() if dry_run else None,
                                      "entry_ts": entry_ts})
            log.info("seeded baseline with %d active markets — sniping only NEW "
                     "listings from here.", len(baseline))
            if args.once:
                return
            time.sleep(LOOP_SECONDS)
            continue

        new_listings = sorted(active - baseline)
        if new_listings:
            anns = ctx.venue.announcements()
            for sym in new_listings:
                tag = _announcement_tag(anns, sym) or "market-set diff"
                log.info("NEW LISTING DETECTED: %s (%s)", sym, tag)

        # ----- open snipes on genuinely new markets -----
        open_now = broker.open_count() if dry_run else len(ctx.venue.positions())
        for sym in new_listings:
            if open_now >= max_open:
                log.info("%s: cap %d reached — skip snipe", sym, max_open)
                break
            try:
                book = ctx.venue.orderbook(sym)
            except Exception as e:  # noqa: BLE001
                log.warning("%s book unavailable (%s); will retry next loop", sym, e)
                continue
            px = _mid(book)
            if not px:
                log.info("%s: no two-sided book yet; wait", sym)
                continue
            size = round(order_usd / px, 6)
            if dry_run:
                broker.mark(sym, px)
                broker.open(sym, DIRECTION_LONG, size, px)
                entry_ts[sym] = now.timestamp()
            else:
                open_notional = len(ctx.venue.positions()) * order_usd
                if not ctx.rails.notional_ok(open_notional, order_usd):
                    log.info("%s NOTIONAL_CAP_SKIP", sym)
                    continue
                try:
                    ctx.venue.market_open(sym, DIRECTION_LONG, size)
                    entry_ts[sym] = now.timestamp()
                except Exception as e:  # noqa: BLE001
                    log.error("snipe order failed %s: %s", sym, e)
                    continue
            open_now += 1
            log.info("SNIPED %s %s @ %.6f size %.4f ($%.0f)",
                     sym, "LONG" if DIRECTION_LONG else "SHORT", px, size, order_usd)

        # A market is sniped once: fold new listings into the baseline now.
        baseline |= set(new_listings)

        # ----- manage open snipes (TP / SL / max-hold) -----
        held = (broker.szi() if dry_run
                else {c: v["size"] for c, v in ctx.venue.positions().items()})
        for coin, sz in list(held.items()):
            if not sz:
                continue
            try:
                px = _mid(ctx.venue.orderbook(coin))
            except Exception:  # noqa: BLE001
                px = None
            if not px:
                continue
            was_long = sz > 0
            ent_px = broker.pos.get(coin, (0.0, 0.0))[1] if dry_run else \
                ctx.venue.positions().get(coin, {}).get("entry", 0.0)
            if dry_run:
                broker.mark(coin, px)
            gain = ((px - ent_px) / ent_px) if (ent_px and was_long) else \
                   ((ent_px - px) / ent_px) if ent_px else 0.0
            held_sec = now.timestamp() - entry_ts.get(coin, now.timestamp())
            reason = None
            if gain >= TAKE_PROFIT_PCT:
                reason = "tp"
            elif gain <= -STOP_LOSS_PCT:
                reason = "sl"
            elif held_sec >= MAX_HOLD_SEC:
                reason = "max_hold"
            if reason:
                if dry_run:
                    _sz, _ent = broker.pos.get(coin, (0.0, 0.0))
                    pnl = broker.close(coin, px)
                    record_close(coin, _ent, entry_ts.pop(coin, None), px, pnl,
                                 _sz > 0, reason)
                else:
                    try:
                        ctx.venue.market_close(coin)
                        entry_ts.pop(coin, None)
                    except Exception as e:  # noqa: BLE001
                        log.error("close failed %s: %s", coin, e)
                        continue
                log.info("CLOSED %s [%s] gain %.1f%%", coin, reason, gain * 100)

        # ----- publish + persist -----
        if dry_run:
            pub_equity = broker.equity()
            pub_open = broker.open_count()
            pub_pnl = pub_equity - PAPER_START
        else:
            _pos = ctx.venue.positions()
            pub_equity = None
            pub_open = len(_pos)
            pub_pnl = None
        try:
            store.publish(bot_id, status="online", equity=pub_equity, pnl_abs=pub_pnl,
                          open_trades=pub_open,
                          extra={"mode": ctx.mode, "venue": ctx.mode,
                                 "watching": len(baseline),
                                 "dir": "long" if DIRECTION_LONG else "short"})
        except Exception:  # noqa: BLE001
            pass
        if dry_run:
            store.save_state(bot_id, {"baseline": sorted(baseline),
                                      "broker": broker.to_state(),
                                      "entry_ts": entry_ts})

        if args.once:
            log.info("--once complete: watching %d markets, %d open.",
                     len(baseline), pub_open)
            return
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")
