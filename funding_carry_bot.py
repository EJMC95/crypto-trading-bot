#!/usr/bin/env python3
"""
funding_carry_bot.py — DRY-RUN Hyperliquid funding-rate carry harvester.

WHY THIS BOT EXISTS (2026-07-03)
  The fleet's trend bots are (correctly) flat in risk-off chop, so nothing
  earns while the tide is out. Funding carry is the classic all-weather
  income strategy: perp funding is paid every hour by the crowded side of
  the book, and a DELTA-NEUTRAL position (perp on one side, hedge on the
  other) collects it without directional exposure. In extreme-fear regimes
  funding often runs hot on the short side — exactly when the trend bots
  sit out.

MODEL (paper, deliberately explicit about what is and is not simulated)
  - Reads REAL hourly funding rates from Hyperliquid mainnet public info
    (no keys, read-only, no orders ever).
  - When a liquid coin's funding annualizes above ENTER_APR, "open" a carry:
    funding > 0 (longs pay shorts)  -> short perp + long spot hedge
    funding < 0 (shorts pay longs)  -> long perp + short spot hedge
  - While open, accrue funding on the notional at the LIVE hourly rate each
    loop (rates decay — accrual follows them down, no entry-rate anchoring).
  - Costs: perp taker both sides + hedge-leg fees/spread both sides, charged
    half at open, half at close (HEDGE_COST covers that the hedge lives on
    another venue/spot book).
  - Close when annualized funding decays below EXIT_APR, flips against the
    position, or MAX_HOLD_H passes.
  NOT modelled: basis drift between perp and hedge venue, hedge borrow cost
  for the short-spot case, and liquidation risk (delta-neutral at 1x has
  none in practice). Treat results as the honest-but-favourable case.

  Realized episodes are mirrored into the shared Postgres paper_trades
  ledger (same scheme as the sniper) so cumulative P&L survives restarts.

Usage:
    python funding_carry_bot.py            # dry-run forever (the only mode)
    python funding_carry_bot.py --once     # single scan then exit (smoke test)
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)
from venues import venue_context  # [2026-07-09 LIGHTER GATE-0] venue abstraction

BOT = "perps-funding-carry"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
NOTIONAL = 300.0          # quote notional per carry position [2026-07-06 raised from $200]
MAX_POSITIONS = 8         # at most 8 concurrent carries [2026-07-06 raised from 5]
MIN_DAY_VOLUME = 2e6      # only coins with >= $2M 24h notional volume [2026-07-06 lowered from $5M to capture hot-rate coins like ME/MINA]

# Funding thresholds, ANNUALIZED (hourly rate * 24 * 365). Hyperliquid's
# baseline funding is ~0.0000125/h ~= 11%/yr; we want clearly-hot funding.
ENTER_APR = 0.40          # open when |annualized funding| >= 40% [2026-07-06 raised from 20% to avoid fee bleed on fast-decaying rates]
EXIT_APR = 0.15           # close when it decays below 15% [2026-07-06 raised from 8% to exit before fees eat accrual]
MAX_HOLD_H = 14 * 24      # recycle capital after 2 weeks [2026-07-06 extended from 7d to let high-rate carries compound]
# [2026-07-16 ZOMBIE GUARD] close a carry whose coin has been continuously
# absent from the funding map this long (delisted): the position could never
# expire and its fees dragged equity forever.
DELIST_GIVEUP_H = float(os.environ.get("CARRY_DELIST_GIVEUP_H", "24"))

# [2026-07-07 EXIT REBUILD] 0W/28L root cause: decay-exits realized fees before
# funding could pay them back (round-trip 29bps needs ~64h at 40% APR; spiky alt
# funding mean-reverts in hours). Decay alone NO LONGER closes a position:
#   * flip persisting >= FLIP_GRACE_H  (we are now PAYING funding — get out)
#   * decay only AFTER fee payback     (net after all fees >= FEE_PAYBACK_MARGIN)
#   * MAX_HOLD_H expiry                (capital recycling, unchanged)
#   * bleed stop                       (catastrophic guard on adverse holds)
# Entries additionally require the rate to have stayed hot >= PERSIST_H — the
# research-backed filter: persistent funding pays carries, spikes pay fees.
PERSIST_H = 6.0            # hours a coin must hold >= ENTER_APR before entry
FLIP_GRACE_H = 1.0         # hours of adverse funding before a flip-close
FEE_PAYBACK_MARGIN = 0.10  # $ net (after ALL fees incl. close) for a decay-close
BLEED_STOP_FRAC = 0.02     # close if net drops below -2% of notional

# Round-trip friction, as fractions of notional per SIDE of the round trip.
PERP_FEE = 0.00045        # HL taker per perp fill (conservative base tier)
HEDGE_COST = 0.0010       # hedge-leg fee + spread per fill (other venue/spot)
OPEN_COST = PERP_FEE + HEDGE_COST    # charged at open; same again at close

LOOP_SECONDS = 300        # funding is hourly; 5-min polling is plenty

HOURS_PER_YEAR = 24 * 365


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _perp_leg_fill(ctx, bot_id, coin, is_buy, notional, mark, publish=True):
    """Cost ($) of executing the Lighter perp leg of a carry (+ the fill price).

    [2026-07-10 SHADOW EXEC] The whole reason funding-carry belongs on Lighter is
    that the perp fee is ZERO — so the only perp-leg cost is the crossed-spread
    SLIPPAGE. In shadow mode we MEASURE it against the real live book instead of
    guessing, and write one venue_orders evidence row per fill (shadow=True). That
    accumulating evidence is what tells us whether real slippage on hot-funding
    coins lands near the backtest's optimistic 3bps (both-perp) or the 20bps
    (CEX-hedge) assumption — the number the go-live decision hinges on.

    The slippage reference is the LIVE-BOOK MID from the same snapshot as the
    fill — NOT the funding-map `mark`, which is a last-trade price frozen at
    LighterClient construction and never refreshed (it would inject unbounded
    drift into the evidence over a long run). `mark` is used only to seed the
    fallback when no book is available.

    Modes:
      hl_paper       : no venue/order path — model the leg with the flat PERP_FEE
                       constant exactly as before (zero behaviour change).
      lighter_shadow : walk the LIVE Lighter book via the same fill model the
                       ShadowBroker uses; ADVERSE slippage only (a fill worse than
                       the mid) is charged — price improvement is floored to 0
                       (conservative). A thin/absent book -> zero measured slippage
                       and a levels_used=0 row that flags the illiquidity for
                       later analysis rather than silently pretending we filled.
    `publish=False` measures without writing an evidence row — used by the decay
    close-gate to check the MEASURED exit cost before committing to a close.
    Funded modes never reach here (main() refuses them — no naked-perp path).
    """
    if ctx.mode == "hl_paper":
        return PERP_FEE * notional, mark
    from venues.shadow import fill_from_book  # local import: only lighter modes need it
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:
        book = None
    # Reference = live book mid (fresh); fall back to the funding-map mark only
    # when the book is unavailable (illiquidity — measured cost is then 0).
    ref = mark or 0.0
    spread_bps = None
    if book and book.get("bids") and book.get("asks"):
        bid, ask = book["bids"][0][0], book["asks"][0][0]
        mid = (bid + ask) / 2.0
        if mid:
            ref, spread_bps = mid, (ask - bid) / mid * 1e4
    if not ref or ref <= 0:
        return PERP_FEE * notional, mark   # no price to size/measure -> model it
    size = notional / ref
    fill = fill_from_book(book, is_buy, size) if book else None
    fill_px = fill[0] if fill else ref
    levels = fill[1] if fill else 0
    slip = (fill_px - ref) * (1.0 if is_buy else -1.0)   # >0 == adverse
    cost = max(0.0, slip) * size
    slip_bps = (slip / ref * 1e4) if ref else None
    if publish:
        try:
            store.publish_venue_order(
                bot_id, venue="lighter", shadow=True, coin=coin,
                side="buy" if is_buy else "sell", size=size,
                px_decision=ref, px_fill=fill_px,
                spread_bps=spread_bps, slippage_bps=slip_bps,
                raw={"leg": "perp", "levels_used": levels,
                     "notional": round(notional, 2), "ts": time.time()})
        except Exception:
            pass
    return cost, fill_px


def main():
    p = argparse.ArgumentParser(description="DRY-RUN funding-carry harvester")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    # [2026-07-10 SHADOW EXEC] Funded modes are REFUSED. Funding-carry is
    # delta-neutral by construction (perp leg + hedge leg); a perp-only venue
    # like Lighter has no automated hedge, so a funded run would place a NAKED
    # perp and silently book its price P&L as if it were neutral — the opposite
    # of the strategy. Shadow is the supported live mode: it runs the full loop
    # on real Lighter data and MEASURES perp-leg slippage without sending orders.
    # A live harvest needs a hedge venue (CEX spot, or a correlated Lighter perp)
    # built + backtested first. See docs/lighter.md and memory
    # funding-carry-structural-edge-lighter.
    # Fail-safe ALLOWLIST (not a blocklist): only the two order-less modes are
    # permitted. Any other / future / unknown VENUE refuses, so a new funded mode
    # added to venues.MODES can never silently run this hedge-less bot naked.
    _mode = os.environ.get("VENUE", "hl_paper").strip() or "hl_paper"
    if _mode not in ("hl_paper", "lighter_shadow"):
        raise SystemExit(
            f"VENUE={_mode}: funding-carry (Yield Harvester) has NO automated "
            "delta-neutral hedge leg yet — refusing to run in any order-sending "
            "mode (would place a naked Lighter perp). Only hl_paper and "
            "lighter_shadow are allowed; the latter accumulates live-book "
            "slippage evidence without sending orders.")

    # [2026-07-09 LIGHTER GATE-0] Funding reads go through the venue layer.
    # VENUE unset -> hl_paper -> Hyperliquid MAINNET meta_and_asset_ctxs, the
    # exact pre-refactor source. VENUE=lighter_shadow reads Lighter's own
    # funding (which natively carries binance/bybit/hyperliquid benchmark rows
    # per market — the cross-venue carry evidence for wave 2). This bot never
    # constructs an order path and cannot place orders on ANY venue.
    ctx = venue_context(bot=BOT, default_hl_net="mainnet", paper_start=START_EQUITY)
    bot_id = ctx.bot_id
    venue_tag = None if ctx.mode == "hl_paper" else "lighter"
    shadow_tag = ctx.mode == "lighter_shadow"

    # Cumulative realized P&L survives restarts via the Postgres ledger.
    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:
        pass

    positions = {}  # coin -> dict(side, notional, opened_ts, accrued, fees, entry_apr)
    hot_since = {}  # coin -> ts when |APR| first held >= ENTER_APR [2026-07-07]

    # [2026-07-03 PERSIST] Restore open carries from Postgres so a redeploy keeps
    # accrued funding + entry levels (realized already restores from the ledger
    # above). Saved after every published loop below.
    try:
        _saved = store.load_state(bot_id)
        if _saved and isinstance(_saved.get("positions"), dict) and _saved["positions"]:
            positions = _saved["positions"]
        if _saved and isinstance(_saved.get("hot_since"), dict):
            hot_since = {str(k): float(v) for k, v in _saved["hot_since"].items()}
            print(f"[{now_iso()}] restored {len(positions)} open carry position(s) "
                  f"from saved state")
    except Exception:
        pass

    print(f"[{now_iso()}] funding-carry DRY-RUN start | enter>={ENTER_APR:.0%} APR "
          f"exit<{EXIT_APR:.0%} | ${NOTIONAL:.0f} x max {MAX_POSITIONS} | "
          f"friction {2*OPEN_COST*1e4:.0f}bps round-trip | realized so far "
          f"${realized:+.2f} ({n_closed} closed)")

    # [2026-07-16 AUDIT FIX] restore the accrual clock: it reset to
    # boot time on every redeploy, so funding during the gap was never
    # accrued (systematic undercount of the drag/credit this book
    # measures). Gap bounded to 48h so ancient state can't over-accrue.
    try:
        _lt = float((_saved or {}).get("last_ts") or 0)
    except Exception:  # noqa: BLE001 — incl. unbound saved-state
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()
    while True:
        t0 = time.time()
        try:
            fund = ctx.venue.funding_map()
        except Exception as e:
            print(f"[{now_iso()}] funding fetch failed ({e!r}); retrying next loop")
            fund = None

        if fund:
            dt_h = (t0 - last_ts) / 3600.0
            last_ts = t0

            # ---- manage open carries ------------------------------------
            for coin in list(positions):
                pos = positions[coin]
                f = fund.get(coin)
                if f is None:
                    # [2026-07-16 ZOMBIE GUARD] a coin that leaves the funding
                    # map used to pause EVERYTHING including max-hold — the
                    # carry could never expire and its open fees dragged
                    # equity forever. Delta-neutral, so the harm is slot +
                    # fees; give up after DELIST_GIVEUP_H continuously absent
                    # (modelled close cost — the live book is gone).
                    first = pos.setdefault("missing_since", t0)
                    if (t0 - first) / 3600.0 < DELIST_GIVEUP_H:
                        continue
                    pos["fees"] += OPEN_COST * pos["notional"] + \
                        HEDGE_COST * pos["notional"]
                    pnl = pos["accrued"] - pos["fees"]
                    realized += pnl
                    n_closed += 1
                    n_wins += 1 if pnl > 0 else 0
                    held_h = (t0 - pos["opened_ts"]) / 3600.0
                    print(f"[{now_iso()}] CLOSE {coin} {pos['side']} after "
                          f"{held_h:.1f}h | accrued {pos['accrued']:+.2f} fees "
                          f"{pos['fees']:.2f} | pnl {pnl:+.2f} [delisted] "
                          f"| realized {realized:+.2f}")
                    try:
                        store.publish_paper_trade(
                            bot_id, trade_id=f"{coin}:{pos['opened_ts']:.0f}",
                            pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=coin,
                            opened_at=datetime.fromtimestamp(
                                pos["opened_ts"], timezone.utc).isoformat(),
                            closed_at=datetime.now(timezone.utc).isoformat(),
                            reason="delisted", venue=venue_tag, shadow=shadow_tag)
                    except Exception:  # noqa: BLE001
                        pass
                    del positions[coin]
                    continue
                pos.pop("missing_since", None)   # back in the map — reset clock
                rate = f["rate"]
                apr = rate * HOURS_PER_YEAR
                # Accrue at the LIVE rate: we receive |funding| while it keeps
                # our sign, and PAY it if the rate flips before we exit.
                sign = -1.0 if pos["side"] == "short_perp" else 1.0
                pos["accrued"] += (-sign) * rate * dt_h * pos["notional"]
                held_h = (t0 - pos["opened_ts"]) / 3600.0

                flipped_now = (pos["side"] == "short_perp" and apr < 0) or \
                              (pos["side"] == "long_perp" and apr > 0)
                # [2026-07-07 EXIT REBUILD] flip grace + fee-payback decay + bleed stop.
                if flipped_now:
                    pos.setdefault("flipped_since", t0)
                else:
                    pos.pop("flipped_since", None)
                # Cheap MODELLED estimate first (no per-loop book read): drives
                # the flip/expire/bleed backstops and the decay pre-filter.
                close_fee_est = OPEN_COST * pos["notional"]
                net_if_closed = pos["accrued"] - (pos["fees"] + close_fee_est)
                flipped = flipped_now and \
                    (t0 - pos["flipped_since"]) / 3600.0 >= FLIP_GRACE_H
                expired = held_h >= MAX_HOLD_H
                bleeding = net_if_closed <= -BLEED_STOP_FRAC * pos["notional"]
                # Decay-close only when funding has cooled AND closing still nets
                # positive after the MEASURED (not modelled) exit cost — else a
                # thin-book exit could realize a loss the fee-payback gate treated
                # as a win. Measured lazily: only once the cheap modelled gate
                # already wants to close (no book read every loop for every pos).
                closing_short = pos["side"] == "short_perp"
                decayed = False
                if abs(apr) < EXIT_APR and net_if_closed >= FEE_PAYBACK_MARGIN:
                    _pc, _ = _perp_leg_fill(
                        ctx, bot_id, coin, is_buy=closing_short,
                        notional=pos["notional"], mark=(f.get("mark") or 0.0),
                        publish=False)
                    net_meas = pos["accrued"] - (
                        pos["fees"] + _pc + HEDGE_COST * pos["notional"])
                    decayed = net_meas >= FEE_PAYBACK_MARGIN
                if not (flipped or decayed or expired or bleeding):
                    continue

                # Realized closing friction: MEASURE the perp exit leg on the live
                # book (closing a short_perp is a BUY-back, a long_perp a SELL) +
                # the modelled hedge leg. Publishes the evidence row.
                perp_close_cost, _ = _perp_leg_fill(
                    ctx, bot_id, coin, is_buy=closing_short,
                    notional=pos["notional"], mark=(f.get("mark") or 0.0))
                pos["fees"] += perp_close_cost + HEDGE_COST * pos["notional"]
                pnl = pos["accrued"] - pos["fees"]
                reason = ("flip" if flipped else "decay_paid" if decayed
                          else "max_hold" if expired else "bleed_stop")
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                print(f"[{now_iso()}] CLOSE {coin} {pos['side']} after {held_h:.1f}h "
                      f"| accrued {pos['accrued']:+.2f} fees {pos['fees']:.2f} "
                      f"| pnl {pnl:+.2f} [{reason}] | realized {realized:+.2f}")
                try:
                    store.publish_paper_trade(
                        bot_id, trade_id=f"{coin}:{pos['opened_ts']:.0f}",
                        pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=coin,
                        opened_at=datetime.fromtimestamp(
                            pos["opened_ts"], timezone.utc).isoformat(),
                        closed_at=datetime.now(timezone.utc).isoformat(),
                        reason=reason, venue=venue_tag, shadow=shadow_tag)
                except Exception:
                    pass
                del positions[coin]

            # ---- persistence bookkeeping [2026-07-07] --------------------
            # Track how long each coin has held >= ENTER_APR. First-seen coins
            # start their clock now, so nothing enters before PERSIST_H.
            for c, f in fund.items():
                if abs(f["rate"] * HOURS_PER_YEAR) >= ENTER_APR:
                    hot_since.setdefault(c, t0)
                else:
                    hot_since.pop(c, None)

            # ---- scan for new carries ------------------------------------
            if len(positions) < MAX_POSITIONS:
                candidates = sorted(
                    ((c, f) for c, f in fund.items()
                     if c not in positions and f["vol"] >= MIN_DAY_VOLUME
                     and abs(f["rate"] * HOURS_PER_YEAR) >= ENTER_APR
                     and (t0 - hot_since.get(c, t0)) >= PERSIST_H * 3600.0),
                    key=lambda cf: -abs(cf[1]["rate"]))
                for coin, f in candidates[:MAX_POSITIONS - len(positions)]:
                    apr = f["rate"] * HOURS_PER_YEAR
                    side = "short_perp" if f["rate"] > 0 else "long_perp"
                    # Perp leg: short_perp opens with a SELL, long_perp with a BUY.
                    # In shadow this MEASURES the real book slippage (+logs it); in
                    # hl_paper it returns the modelled PERP_FEE. The hedge leg is
                    # always the modelled HEDGE_COST (it lives off-venue).
                    perp_open_cost, _ = _perp_leg_fill(
                        ctx, bot_id, coin, is_buy=(side == "long_perp"),
                        notional=NOTIONAL, mark=(f.get("mark") or 0.0))
                    positions[coin] = {
                        "side": side, "notional": NOTIONAL, "opened_ts": t0,
                        "accrued": 0.0,
                        "fees": perp_open_cost + HEDGE_COST * NOTIONAL,
                        "entry_apr": apr,
                    }
                    print(f"[{now_iso()}] OPEN {coin} {side} ${NOTIONAL:.0f} "
                          f"| funding {apr:+.1%} APR "
                          f"| hot {(t0 - hot_since.get(coin, t0)) / 3600.0:.1f}h "
                          f"| perp-leg cost ${perp_open_cost:.3f} "
                          f"({'measured' if ctx.mode != 'hl_paper' else 'modelled'})")

            # ---- publish snapshot ----------------------------------------
            open_pnl = sum(p["accrued"] - p["fees"] for p in positions.values())
            top = sorted(fund.items(), key=lambda cf: -abs(cf[1]["rate"]))[:3]
            try:
                store.publish(
                    bot_id, status="online",
                    equity=START_EQUITY + realized + open_pnl,
                    pnl_abs=realized,
                    open_trades=len(positions),
                    closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                    extra={"mode": "dry-run", "open_pnl": round(open_pnl, 2),
                           # NOT "positions": the dashboard reserves that key for
                           # the stock bots' list-of-dicts holdings format.
                           "carries": {c: f"{p['side']}@{p['entry_apr']:+.0%}"
                                       for c, p in positions.items()},
                           "hottest_funding_apr": {
                               c: f"{f['rate']*HOURS_PER_YEAR:+.1%}" for c, f in top}},
                )
            except Exception:
                pass

            # [2026-07-03 PERSIST] Durable open-carry state -> Postgres.
            try:
                store.save_state(bot_id, {"positions": positions, "hot_since": hot_since,
                                           "last_ts": last_ts})
            except Exception:
                pass

            held = ", ".join(f"{c}({p['side'][0]})" for c, p in positions.items()) or "none"
            print(f"[{now_iso()}] scan ok | {len(fund)} perps | open: {held} "
                  f"| open_pnl {open_pnl:+.2f} | realized {realized:+.2f}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


if __name__ == "__main__":
    main()
