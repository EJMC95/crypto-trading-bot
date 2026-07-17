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

  A detected symbol stays PENDING (retried every loop) until a snipe actually
  opens a position, or until a bounded, logged give-up. Only those two outcomes
  fold it into the baseline — see the 2026-07-17 RETRY FIX below.

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
# [2026-07-16 ZOMBIE GUARD] a pulled/delisted book used to mean "hold
# forever" (`if not px: continue` skipped even max-hold) — the most likely
# fate for a fresh listing. Give up after this long continuously
# unpriceable; close at the last seen mid (entry if none).
DELIST_GIVEUP_SEC = float(os.environ.get("SNIPER_DELIST_GIVEUP_SEC", str(6 * 3600)))
MAX_OPEN = 4               # global cap on concurrent snipes
LOOP_SECONDS = 60          # poll the market list every minute
DIRECTION_LONG = os.environ.get("SNIPER_DIRECTION", "long").lower() != "short"
# [2026-07-17 RETRY FIX] `baseline |= set(new_listings)` used to run
# UNCONDITIONALLY after the snipe loop, outside every failure path inside it.
# A listing that skipped (one-sided book, book fetch raised, notional cap,
# order failed) was still folded into the baseline, and since detection is
# `active - baseline` it could never surface again. The "will retry next loop"
# comment and the "wait" log were both false: there was no retry, ever. It bit
# exactly when it mattered — `_mid` returns None if EITHER side is empty, and a
# one-sided book is the MOST likely state for a brand-new perp. Measured
# 17-Jul: 0 trades since 9-Jul; FOLKS and SKHY (both listed 14-Jul, after the
# seed) sit in the baseline having never been traded.
# A symbol is now folded in only when a position OPENS, or on a bounded, logged
# give-up. At LOOP_SECONDS=60 the two bounds coincide at ~2h: attempts bound a
# fast loop, age bounds a restart-churn case (first_seen persists, attempts do
# not). Past the debut window a snipe is just a stale random long, so giving up
# is deliberate — but it is LOUD, never silent absorption.
PENDING_MAX_ATTEMPTS = int(os.environ.get("SNIPER_PENDING_MAX_ATTEMPTS", "120"))
PENDING_MAX_AGE_SEC = float(os.environ.get("SNIPER_PENDING_MAX_AGE_SEC", str(2 * 3600)))
# Boot state reads to attempt before refusing to run — see the SEED GUARD below.
STATE_READ_TRIES = int(os.environ.get("SNIPER_STATE_READ_TRIES", "3"))

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


def _snipe_price(orderbook_fn, sym):
    """(price, None) if the book is snipeable, else (None, why-not).

    Split out of the snipe loop so the self-test drives the REAL `_mid`
    semantics — a one-sided debut book is the case that broke this bot.
    """
    try:
        book = orderbook_fn(sym)
    except Exception as e:  # noqa: BLE001
        return None, f"book unavailable ({e})"
    px = _mid(book)
    if not px:
        return None, "no two-sided book yet"
    return px, None


def run_snipe_pass(*, candidates, pending, baseline, now_ts, open_now, max_open,
                   try_snipe, is_held=lambda s: False,
                   max_attempts=PENDING_MAX_ATTEMPTS,
                   max_age_sec=PENDING_MAX_AGE_SEC):
    """One snipe pass over `candidates`. Mutates `pending` and `baseline`.

    `try_snipe(sym)` does the I/O and returns True only if a position actually
    OPENED; any retryable skip returns False. This function owns the one rule
    the old code got wrong: a symbol enters `baseline` on exactly two routes —
    a snipe that opened, or a bounded give-up — and on nothing else.

    `is_held(sym)` is the DOUBLE-OPEN guard. The old unconditional fold was, by
    accident, also a "snipe each market at most once" latch; retrying without
    replacing it would let an order that landed-but-failed-to-ack be sent twice
    (live: a second clip; shadow: PaperBroker.open silently FLIPS the position,
    realising P&L with no record_close). A held symbol is by definition sniped.

    Returns (open_now, sniped, abandoned).
    """
    sniped, abandoned = [], []
    for sym in candidates:
        if is_held(sym):
            pending.pop(sym, None)
            baseline.add(sym)
            log.info("%s: already held — folding into baseline (snipe landed)", sym)
            continue
        rec = pending.setdefault(sym, {"first_seen": now_ts, "attempts": 0})
        age = now_ts - rec["first_seen"]
        # Deliberate abandonment: the ONLY non-success route into the baseline.
        # Checked first and uniformly, so a symbol blocked purely by the cap
        # still ages out instead of sitting pending forever.
        if rec["attempts"] >= max_attempts or age >= max_age_sec:
            pending.pop(sym, None)
            baseline.add(sym)
            abandoned.append(sym)
            log.warning("%s: GIVING UP after %d attempts / %.0f min unsnipeable"
                        " — folding into baseline; it will NOT be retried.",
                        sym, rec["attempts"], age / 60)
            continue
        if open_now >= max_open:
            # The cap is the fleet's state, not this listing's fault: stay
            # pending and burn no retry budget, so a freed slot still gets it.
            log.info("%s: cap %d reached — stays pending (age %.0f min)",
                     sym, max_open, age / 60)
            continue
        if try_snipe(sym):
            pending.pop(sym, None)
            baseline.add(sym)
            sniped.append(sym)
            open_now += 1
            continue
        rec["attempts"] += 1
    return open_now, sniped, abandoned


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
    pending = {}          # sym -> {"first_seen": ts, "attempts": n} — detected, not yet sniped
    no_px_since = {}      # coin -> first ts the book was unpriceable (zombie clock)
    last_px = {}          # coin -> last seen mid (zombie exit price)
    # [2026-07-17 SEED GUARD] The seed below (`if not baseline`) absorbs every
    # active market by design — correct on a true first run, catastrophic on a
    # Postgres blip, because load_state() returns None for BOTH. That path would
    # silently re-create the very absorption bug this file was fixed for, so an
    # unreadable state is a REFUSAL, not an empty one: crash-loop loudly (Railway
    # restarts us, the watchdog sees it) rather than poison the baseline.
    # No DB AT ALL is the same poison arriving by a different road, and it is not
    # hypothetical: a Railway env var went missing on 16-Jul (see f44e3eb). With
    # no persistence this bot re-seeds every boot, absorbs every listing, and
    # publishes a healthy row while sniping nothing — the exact silent-zero this
    # file was fixed for. Retrying cannot help (an unset var will not appear), so
    # say the real cause and refuse now rather than after 3 misleading tries.
    _saved, _ok = None, True
    if dry_run and not os.environ.get("DATABASE_URL", "").strip():
        log.error("DATABASE_URL is not set. This sniper's correctness DEPENDS on a"
                  " durable baseline: with no persistence every boot re-seeds and"
                  " absorbs every live listing, so it would look online and snipe"
                  " nothing. Refusing to run.")
        sys.exit(3)
    if dry_run:
        for _try_n in range(1, STATE_READ_TRIES + 1):
            _ok, _saved = store.load_state_checked(bot_id)
            if _ok:
                break
            log.error("state read FAILED (try %d/%d) — NOT seeding: an unreadable"
                      " state is indistinguishable from a fresh bot, and seeding"
                      " now would absorb every live listing forever.",
                      _try_n, STATE_READ_TRIES)
            if _try_n < STATE_READ_TRIES:
                time.sleep(LOOP_SECONDS)
        if not _ok:
            log.error("state unreadable after %d tries — exiting rather than "
                      "seeding a false baseline.", STATE_READ_TRIES)
            sys.exit(3)
    if _saved:
        if dry_run and broker.restore_state(_saved.get("broker") or {}):
            log.info("restored paper state: equity $%.2f, %d open",
                     broker.equity(), broker.open_count())
        baseline = set(_saved.get("baseline") or [])
        entry_ts = {str(k): float(v) for k, v in (_saved.get("entry_ts") or {}).items()}
        # [2026-07-17 RETRY FIX] persist the retry budget: first_seen must
        # survive a restart or a give-up could never be reached across a
        # deploy loop. A dropped pending entry is self-healing (the symbol
        # isn't in the baseline, so it re-detects), just with a fresh clock.
        for k, v in (_saved.get("pending") or {}).items():
            try:
                # A missing/zero first_seen must NOT default to 0.0 — that is an
                # age of ~55 years, an instant give-up, i.e. the absorption bug
                # again. An unknown clock starts NOW.
                pending[str(k)] = {"first_seen": float(v.get("first_seen") or time.time()),
                                   "attempts": int(v.get("attempts") or 0)}
            except Exception:  # noqa: BLE001
                continue
        if pending:
            log.info("restored %d pending listing(s) awaiting a snipeable book: %s",
                     len(pending), ", ".join(sorted(pending)))

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

    def open_snipe(sym, now_ts):
        """Attempt ONE snipe. True only if a position actually opened.

        Every False is a retryable skip — the caller keeps the symbol pending
        rather than folding it into the baseline.
        """
        px, why = _snipe_price(ctx.venue.orderbook, sym)
        if not px:
            log.info("%s: %s — staying pending, will retry next loop", sym, why)
            return False
        size = round(order_usd / px, 6)
        if size <= 0:
            # PaperBroker.open() silently no-ops on size<=0 and market_open would
            # send a zero clip: returning True here would log a phantom "SNIPED"
            # and fold the symbol into the baseline with no position — the exact
            # absorption this file was fixed for. Refuse instead.
            log.error("%s: clip $%.2f at px %.6f rounds to size 0 — NOT sniping"
                      " (check LIGHTER_ORDER_USD); staying pending",
                      sym, order_usd, px)
            return False
        if dry_run:
            broker.mark(sym, px)
            broker.open(sym, DIRECTION_LONG, size, px)
            if sym not in broker.pos:
                log.error("%s: broker.open did not materialise a position — "
                          "staying pending", sym)
                return False
            entry_ts[sym] = now_ts
        else:
            open_notional = len(ctx.venue.positions()) * order_usd
            if not ctx.rails.notional_ok(open_notional, order_usd):
                log.info("%s NOTIONAL_CAP_SKIP — staying pending", sym)
                return False
            try:
                ctx.venue.market_open(sym, DIRECTION_LONG, size)
                entry_ts[sym] = now_ts
            except Exception as e:  # noqa: BLE001
                log.error("snipe order failed %s: %s — staying pending", sym, e)
                return False
        log.info("SNIPED %s %s @ %.6f size %.4f ($%.0f)",
                 sym, "LONG" if DIRECTION_LONG else "SHORT", px, size, order_usd)
        return True

    # [2026-07-16 AUDIT FIX] seed W/L from the durable ledger — this bot
    # published NULL counts every loop (the dashboard row showed no record),
    # and `realized_seeded` was assigned but never used (the seeding it
    # promised was never written).
    n_closed, n_wins = 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            n_closed, n_wins = agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass
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
                                      "entry_ts": entry_ts, "pending": pending})
            log.info("seeded baseline with %d active markets — sniping only NEW "
                     "listings from here.", len(baseline))
            if args.once:
                return
            time.sleep(LOOP_SECONDS)
            continue

        # A pending symbol is NOT in the baseline, so it stays in new_listings
        # until it is sniped or given up on — that IS the retry.
        new_listings = sorted(active - baseline)
        # Pulled before we could get in. KEEP the retry clock while it's inside
        # the give-up window: popping the record would reset first_seen/attempts
        # on its return, so a symbol flapping in and out of `active` — exactly
        # what a fresh listing's status does around its debut — would never
        # reach the give-up and could be sniped days late. Drop it only once
        # it's past the bound, and never into the baseline: an inactive market
        # that re-lists later is a genuinely new listing.
        for sym in [s for s in pending if s not in active]:
            if now.timestamp() - pending[sym]["first_seen"] >= PENDING_MAX_AGE_SEC:
                pending.pop(sym, None)
                log.info("%s: inactive past the give-up window — dropped from "
                         "pending (never sniped)", sym)
        fresh = [s for s in new_listings if s not in pending]
        if fresh:
            anns = ctx.venue.announcements()
            for sym in fresh:
                tag = _announcement_tag(anns, sym) or "market-set diff"
                log.info("NEW LISTING DETECTED: %s (%s)", sym, tag)

        # ----- open snipes on genuinely new markets -----
        open_now = broker.open_count() if dry_run else len(ctx.venue.positions())
        _held_now = set(broker.pos) if dry_run else set(ctx.venue.positions())
        open_now, _sniped, _abandoned = run_snipe_pass(
            candidates=new_listings, pending=pending, baseline=baseline,
            now_ts=now.timestamp(), open_now=open_now, max_open=max_open,
            try_snipe=lambda s: open_snipe(s, now.timestamp()),
            is_held=lambda s: s in _held_now)

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
            was_long = sz > 0
            ent_px = broker.pos.get(coin, (0.0, 0.0))[1] if dry_run else \
                ctx.venue.positions().get(coin, {}).get("entry", 0.0)
            zombie = False
            if not px:
                # [2026-07-16 ZOMBIE GUARD] unpriceable book: start the clock;
                # past the give-up, value at the last seen mid (entry if none)
                first = no_px_since.setdefault(coin, now.timestamp())
                if now.timestamp() - first < DELIST_GIVEUP_SEC:
                    continue
                px = last_px.get(coin) or ent_px
                if not px:
                    continue             # nothing to value it at — keep waiting
                zombie = True
            else:
                no_px_since.pop(coin, None)
                last_px[coin] = px
            if dry_run:
                broker.mark(coin, px)
            gain = ((px - ent_px) / ent_px) if (ent_px and was_long) else \
                   ((ent_px - px) / ent_px) if ent_px else 0.0
            held_sec = now.timestamp() - entry_ts.get(coin, now.timestamp())
            reason = None
            if zombie:
                reason = "delisted"
            elif gain >= TAKE_PROFIT_PCT:
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
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    no_px_since.pop(coin, None)
                    last_px.pop(coin, None)
                else:
                    try:
                        ctx.venue.market_close(coin)
                        entry_ts.pop(coin, None)
                        no_px_since.pop(coin, None)
                        last_px.pop(coin, None)
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
                          closed_trades=n_closed, wins=n_wins,
                          losses=n_closed - n_wins,
                          extra={"mode": ctx.mode, "venue": ctx.mode,
                                 "watching": len(baseline),
                                 # [2026-07-17 RETRY FIX] `watching` alone is
                                 # NOT a health signal — the old unconditional
                                 # fold drove it to the active count whether or
                                 # not a snipe ever landed, so a broken bot and
                                 # a healthy one looked identical. These two say
                                 # what the baseline count cannot.
                                 "pending": len(pending),
                                 "gave_up": sorted(_abandoned),
                                 "dir": "long" if DIRECTION_LONG else "short",
                                 # [2026-07-15 GAP FIX] position detail so the
                                 # fleet exposure/concentration view can see
                                 # this book (it was sym_uncovered before).
                                 "held": {c: ("L" if DIRECTION_LONG else "S")
                                          for c in sorted(broker.pos)}})
        except Exception:  # noqa: BLE001
            pass
        if dry_run:
            store.save_state(bot_id, {"baseline": sorted(baseline),
                                      "broker": broker.to_state(),
                                      "entry_ts": entry_ts,
                                      "pending": pending})

        if args.once:
            log.info("--once complete: watching %d markets, %d pending, %d open.",
                     len(baseline), len(pending), pub_open)
            return
        time.sleep(LOOP_SECONDS)


def selftest():
    print("Running Lighter perp sniper offline self-test...\n")
    t0 = 1_000_000.0
    never = lambda s: False       # noqa: E731 — every snipe skips
    always = lambda s: True       # noqa: E731 — every snipe opens

    # ---- _mid: a one-sided book has NO price. This is why the bug bit a
    # brand-new listing specifically — a fresh perp's debut book is the most
    # likely book in the fleet to have an empty side.
    assert _mid({"bids": [[10.0, 1]], "asks": [[10.2, 1]]}) == 10.1
    assert _mid({"bids": [[10.0, 1]], "asks": []}) is None
    assert _mid({"bids": [], "asks": [[10.2, 1]]}) is None
    assert _mid({"bids": [], "asks": []}) is None
    assert _mid(None) is None

    # ---- _snipe_price surfaces both non-snipeable shapes as retryable
    def _boom(sym):
        raise RuntimeError("503")
    px, why = _snipe_price(_boom, "X")
    assert px is None and "unavailable" in why, (px, why)
    px, why = _snipe_price(lambda s: {"bids": [[5.0, 1]], "asks": []}, "X")
    assert px is None and "two-sided" in why, (px, why)
    px, why = _snipe_price(lambda s: {"bids": [[5.0, 1]], "asks": [[5.2, 1]]}, "X")
    assert px == 5.1 and why is None, (px, why)

    # ---- NEGATIVE FIXTURE — the 2026-07-17 defect, pinned.
    # A new listing whose FIRST orderbook read is one-sided must NOT be
    # absorbed into the baseline: it must survive as pending and still be
    # sniped on a later loop. Under the old `baseline |= set(new_listings)`
    # this fails at loop 2 — the symbol is gone from `active - baseline`
    # forever and `opened` stays empty.
    books = {1: {"bids": [[5.0, 10]], "asks": []},                # debut: bids only
             2: {"bids": [[5.0, 10]], "asks": []},                # still one-sided
             3: {"bids": [[5.0, 10]], "asks": [[5.2, 10]]}}       # two-sided at last
    loop, opened = {"n": 0}, []

    def _try(sym):
        px, _why = _snipe_price(lambda s: books[loop["n"]], sym)
        if not px:
            return False
        opened.append((sym, px))
        return True

    baseline, pending = {"OLD"}, {}
    for n in (1, 2):
        loop["n"] = n
        assert sorted({"OLD", "NEW"} - baseline) == ["NEW"], \
            f"loop {n}: a one-sided book absorbed the listing — the 17-Jul bug"
        run_snipe_pass(candidates=sorted({"OLD", "NEW"} - baseline), pending=pending,
                       baseline=baseline, now_ts=t0 + n * LOOP_SECONDS,
                       open_now=len(opened), max_open=4, try_snipe=_try)
        assert "NEW" not in baseline, f"loop {n}: unsniped listing must stay OUT"
        assert pending["NEW"]["attempts"] == n, pending
        assert opened == [], opened
    loop["n"] = 3
    run_snipe_pass(candidates=sorted({"OLD", "NEW"} - baseline), pending=pending,
                   baseline=baseline, now_ts=t0 + 3 * LOOP_SECONDS,
                   open_now=len(opened), max_open=4, try_snipe=_try)
    assert opened == [("NEW", 5.1)], f"the retry must land the snipe: {opened}"
    assert "NEW" in baseline and "NEW" not in pending, (baseline, pending)

    # ---- a snipe that OPENS folds in immediately (the only success route)
    baseline, pending = {"OLD"}, {}
    open_now, sniped, abandoned = run_snipe_pass(
        candidates=["S1"], pending=pending, baseline=baseline, now_ts=t0,
        open_now=0, max_open=4, try_snipe=always)
    assert sniped == ["S1"] and not abandoned and open_now == 1
    assert "S1" in baseline and not pending

    # ---- the cap must NOT absorb, and must burn no retry budget
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["N1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=4, max_open=4, try_snipe=always)
    assert "N1" not in baseline and pending["N1"]["attempts"] == 0, (baseline, pending)
    # ...and a mid-list cap hit leaves the rest pending, not lost (was `break`)
    baseline, pending = {"OLD"}, {}
    _o, sniped, _a = run_snipe_pass(candidates=["B1", "B2"], pending=pending,
                                    baseline=baseline, now_ts=t0, open_now=3,
                                    max_open=4, try_snipe=always)
    assert sniped == ["B1"] and "B2" not in baseline and "B2" in pending

    # ---- a raising orderbook must NOT absorb either
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["X1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=0, max_open=4,
                   try_snipe=lambda s: bool(_snipe_price(_boom, s)[0]))
    assert "X1" not in baseline and pending["X1"]["attempts"] == 1

    # ---- give-up is BOUNDED by attempts (age pinned) ...
    baseline, pending = {"OLD"}, {}
    for _ in range(PENDING_MAX_ATTEMPTS):
        run_snipe_pass(candidates=["Z1"], pending=pending, baseline=baseline,
                       now_ts=t0, open_now=0, max_open=4, try_snipe=never)
    assert "Z1" not in baseline and pending["Z1"]["attempts"] == PENDING_MAX_ATTEMPTS
    _o, _s, abandoned = run_snipe_pass(candidates=["Z1"], pending=pending,
                                       baseline=baseline, now_ts=t0, open_now=0,
                                       max_open=4, try_snipe=never)
    assert abandoned == ["Z1"] and "Z1" in baseline and "Z1" not in pending

    # ---- ... and independently by AGE (attempts pinned at 1)
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["A1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=0, max_open=4, try_snipe=never)
    assert "A1" not in baseline
    _o, _s, abandoned = run_snipe_pass(candidates=["A1"], pending=pending,
                                       baseline=baseline,
                                       now_ts=t0 + PENDING_MAX_AGE_SEC, open_now=0,
                                       max_open=4, try_snipe=never)
    assert abandoned == ["A1"] and "A1" in baseline and "A1" not in pending

    # ---- a cap-blocked listing still ages out (never pends forever)
    baseline, pending = {"OLD"}, {}
    run_snipe_pass(candidates=["C1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=4, max_open=4, try_snipe=always)
    _o, _s, abandoned = run_snipe_pass(candidates=["C1"], pending=pending,
                                       baseline=baseline,
                                       now_ts=t0 + PENDING_MAX_AGE_SEC, open_now=4,
                                       max_open=4, try_snipe=always)
    assert abandoned == ["C1"] and "C1" in baseline

    # ---- DOUBLE-OPEN GUARD: an order that landed but failed to ack must not be
    # sent twice. The old unconditional fold was an accidental once-only latch;
    # removing it without this guard is a real-money regression (and in shadow
    # PaperBroker.open FLIPS the position, realising P&L with no record_close).
    baseline, pending = {"OLD"}, {}
    sends = []
    run_snipe_pass(candidates=["D1"], pending=pending, baseline=baseline, now_ts=t0,
                   open_now=0, max_open=4,
                   try_snipe=lambda s: sends.append(s) or False)   # landed, ack failed
    assert sends == ["D1"] and "D1" not in baseline and pending["D1"]["attempts"] == 1
    run_snipe_pass(candidates=["D1"], pending=pending, baseline=baseline,
                   now_ts=t0 + LOOP_SECONDS, open_now=1, max_open=4,
                   try_snipe=lambda s: sends.append(s) or False,
                   is_held=lambda s: s == "D1")                    # ack caught up
    assert sends == ["D1"], f"a held symbol must NEVER be re-sent: {sends}"
    assert "D1" in baseline and "D1" not in pending, (baseline, pending)

    # ---- PaperBroker.open contract (why open_snipe must verify, not assume):
    # it silently no-ops on size<=0, and FLIPS an existing position (a close
    # with no record_close). Both make a bare `return True` a phantom SNIPED.
    from venues.shadow import PaperBroker
    _b = PaperBroker(start_equity=1000.0)
    _b.open("Q", True, 0.0, 5.0)
    assert "Q" not in _b.pos, "size<=0 no-ops silently — open_snipe must check"
    _b.open("Q", True, 1.0, 5.0)
    assert "Q" in _b.pos
    _b.open("Q", True, 1.0, 6.0)          # re-open == flip: closes the old side
    assert _b.realized != 0.0, "re-opening a held symbol realises P&L silently"

    # ---- SEED GUARD: load_state_checked must distinguish "definitely no row"
    # from "I could not find out". A false seed absorbs every live market
    # durably, so an unreadable state must never look empty.
    import bot_pnl_store as _st
    assert hasattr(_st, "load_state_checked"), "the seed guard needs the checked read"
    _ok, _state = _st.load_state_checked("no-such-bot")
    assert _ok is False and _state is None, \
        "no DATABASE_URL must report ok=False (cannot confirm emptiness), not (True, None)"
    assert _st.load_state("no-such-bot") is None, "load_state must still delegate unchanged"

    print("All perp sniper self-tests passed (one-sided debut book RETRIES and "
          "still snipes; cap/exception/skip never absorb; give-up bounded by "
          "attempts AND age; held symbols never double-open; an unreadable "
          "state never looks empty).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        try:
            main()
        except KeyboardInterrupt:
            log.info("stopped by user.")
