#!/usr/bin/env python3
"""
lighter_dislocation_bot.py — 🧲 Snap Back (Lighter dislocation harvester).

WHAT / WHY (2026-07-11)
  On 11 Jul a Lighter mark printed ~25% away from Binance/HL for minutes and a
  bot on the WRONG side of it (Trail Blazer's loss rail) paid $3.85. This bot
  is the other side of that trade: when a Lighter book dislocates from a deep
  independent reference, take the reconvergence — BUY Lighter when it prints
  cheap, SHORT when it prints rich, exit when the gap closes. Thin new venue +
  zero fees + small clips is precisely the niche where small capital has an
  edge big money can't be bothered with.

  THE REFERENCE IS LIGHTER'S OWN INDEX PRICE (changed 2026-07-17, operator:
  "i only want things running on lighter"). It was Hyperliquid mainnet mids.
  Lighter publishes index_price for every active book on the same endpoint the
  market scout already reads, and it is the price Lighter MARKS and LIQUIDATES
  against — i.e. the gap this bot bets on closing is the one the venue's own
  funding and liquidation machinery pulls closed. Measured 17-Jul, the two
  references agree to a median 3.8 bps (vs a 150 bps entry gate) but the index
  residual is systematically tighter: `book/hl_mid - 1` was charging Lighter
  for HYPERLIQUID's basis. See reference_prices() for the numbers.

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
  * Reference-blind: no Lighter index -> no signal -> do nothing (never trade
    against a reference we can't see). An EMPTY parse counts as blind too.
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

# [2026-07-30] Growth rail + the shared scout read. Guarded like every optional
# organ: dark imports leave the operator's env defaults and the configured coin
# list in force. Both COPYs land in Dockerfile.dislocation in this same commit.
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

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

# [2026-07-30 ADAPTIVE GATE] `ENTER_BPS` was a FIXED 150bps against a measured
# median residual of 3.8bps — roughly 40x the middle of its own signal, which
# is why this book has ~10 closes. The constant is an inheritance from the era
# when the reference was Hyperliquid's mid (the 17-Jul switch to Lighter's own
# `index_price` made the residual systematically TIGHTER and the gate was never
# re-based). It is now a PERCENTILE of the live residual distribution, so the
# bar tracks the venue instead of a number from a different reference series.
#
# BE CLEAR ABOUT WHAT THIS DOES AND DOES NOT DO. It is floored at
# `EXIT_BPS * ENTER_FLOOR_MULT` — entering closer than that to the exit bar
# would book a capture smaller than the round trip that earns it, which is a
# losing trade dressed as a signal. On today's tape that floor will USUALLY
# BIND, so the practical effect is 150bps -> ~60bps, not "the gate follows the
# median down". The percentile matters on the days the venue is genuinely
# dislocated, which are the days this book exists for.
ENTER_PCT = float(os.environ.get("DISLOC_ENTER_PCT", "0.98"))
ENTER_FLOOR_MULT = float(os.environ.get("DISLOC_ENTER_FLOOR_MULT", "1.5"))
ENTER_MIN_N = int(os.environ.get("DISLOC_ENTER_MIN_N", "20"))
# Widen the 16-name hand list with the scout's most-liquid books: dislocations
# are MORE common in thin books, which is exactly where the hand list had no
# coverage. 0 disables the widening and restores the configured list.
UNIVERSE_N = int(os.environ.get("DISLOC_UNIVERSE_N", "40"))
UNIVERSE_MIN_VOL_M = float(os.environ.get("DISLOC_UNIVERSE_MIN_VOL_M", "0.5"))
CONFIRM_LOOPS = int(os.environ.get("DISLOC_CONFIRM_LOOPS", "2"))
MAX_ENTRY_SLIP_BPS = float(os.environ.get("DISLOC_MAX_ENTRY_SLIP_BPS", "30"))
HARD_STOP = float(os.environ.get("DISLOC_HARD_STOP", "0.05"))
MAX_HOLD_S = float(os.environ.get("DISLOC_MAX_HOLD_S", "7200"))
# [2026-07-16 ZOMBIE GUARD] a held coin whose reference vanished, whose
# Lighter book went dark, or that got delisted skipped even the HARD STOP
# (`continue` before the manage block). Give up at the last usable exit
# price after this long unmanageable — but only while the reference feed
# itself is alive (a whole-feed outage must never flatten the book).
DELIST_GIVEUP_H = float(os.environ.get("DISLOC_DELIST_GIVEUP_H", "6"))
DAILY_LOSS_LIMIT = float(os.environ.get("DISLOC_DAILY_LOSS", "0.05"))

LOOP_SECONDS = int(os.environ.get("DISLOC_LOOP_SECONDS", "90"))
# [2026-07-17 LIGHTER-ONLY] was HL_INFO = "https://api.hyperliquid.xyz/info".
# The reference is now Lighter's own index price off this base — see
# reference_prices(). Same host the venue layer already trades against.
LIGHTER_API = os.environ.get("LIGHTER_API_BASE",
                             "https://mainnet.zklighter.elliot.ai")

LOG_FILE = os.environ.get("DISLOC_LOG_FILE", "lighter_dislocation_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def index_from_books(books):
    """orderBookDetails rows -> {coin: index_price} for ACTIVE books. Pure:
    no network, no clock — the self-test drives the REAL parse. Junk skipped."""
    out = {}
    for b in books or []:
        try:
            if b.get("status") != "active":
                continue
            sym = b.get("symbol")
            idx = float(b.get("index_price") or 0.0)
            if sym and idx > 0.0:
                out[sym] = idx
        except (TypeError, ValueError):
            continue
    return out


def reference_prices():
    """Independent reference: LIGHTER'S OWN INDEX PRICE for every active book.
    Returns {coin: index} or {} — {} means reference-blind, callers must skip.

    [2026-07-17 LIGHTER-ONLY — operator: "i only want things running on
    lighter"] This was hl_mids(): a POST to api.hyperliquid.xyz for HL mainnet
    mids. Replacing it is not merely rule-compliance, it is a better reference,
    for three measured reasons:

      * HL's mid carries HL'S OWN basis, so `book/hl_mid - 1` measured Lighter's
        dislocation PLUS Hyperliquid's deviation — foreign noise entering as
        signal. Measured head-to-head on live books 17-Jul: the two references
        agree to a median 3.8 bps (max 8.6 across 13 coins) — negligible against
        this bot's 150 bps entry gate, so the swap is signal-neutral where it
        decides — but the index residual is SYSTEMATICALLY TIGHTER (SUI -5.7 vs
        -14.3 bps, LTC -7.4 vs -14.9, LINK -9.8 vs -15.6). The excess was HL's.
      * The index is what Lighter itself MARKS and LIQUIDATES against, so it is
        the gap that funding and liquidation actually pull the book back toward.
        A reconvergence bet against a foreign venue's mid has no such mechanism.
      * It costs one fewer venue: no HL outage can blind us (the old comment
        "no HL mids -> do nothing" was a real, regular hole), no cross-venue
        symbol mapping, one clock. It also covers books HL does not list at all
        (Lighter's equity perps + XAU), though the COINS universe is
        deliberately UNCHANGED here — one variable at a time.

    Same endpoint the market scout has used since it shipped, same raw urllib +
    browser UA: the generated SDK omits index_price/mark_price from its model
    AND its default UA trips Lighter's CloudFront WAF (405 -> captcha), so the
    raw read is the proven path, not a shortcut.
    """
    try:
        req = urllib.request.Request(
            LIGHTER_API + "/api/v1/orderBookDetails",
            headers={"User-Agent": "Mozilla/5.0"})
        raw = json.loads(urllib.request.urlopen(req, timeout=15).read())
        ref = index_from_books(raw.get("order_book_details"))
        if not ref:
            log.warning("Lighter index reference came back EMPTY — treating as "
                        "reference-blind (no trades this loop)")
        return ref
    except Exception as e:  # noqa: BLE001
        log.warning("Lighter index reference unavailable: %s", e)
        return {}


def adaptive_enter_bps(devs, pct, exit_bps, floor_mult, fallback, min_n):
    """The entry bar for the NEXT loop: the `pct` percentile of |residual|
    across every book scanned this loop, floored so a trade always clears its
    own round trip.

    Pure — the caller supplies the sample. Contract:
      * fewer than `min_n` observations -> `fallback` (the configured constant).
        A thin sample cannot describe a distribution, and guessing low here
        would open trades on noise.
      * the result is never below `exit_bps * floor_mult`: entering nearer the
        exit bar than that books a capture smaller than the spread+slip that
        earns it. This floor is what stops an adaptive gate from chasing a
        calm venue all the way down to the median.
      * never above `fallback` — this change is a re-basing DOWNWARD from a
        stale constant, not a licence to widen past the operator's number.
    """
    try:
        xs = sorted(abs(float(d)) for d in devs if d is not None)
    except (TypeError, ValueError):
        return float(fallback)
    if len(xs) < int(min_n):
        return float(fallback)
    p = min(max(float(pct), 0.0), 1.0)
    # nearest-rank; index is clamped so p=1.0 selects the max, not an overrun
    idx = min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))
    val = xs[idx]
    return float(min(max(val, float(exit_bps) * float(floor_mult)),
                     float(fallback)))


def prune_dead(coins, supports):
    """Drop configured symbols the venue does not actually list.

    [2026-07-30 SCOPE HYGIENE] Measured against the live venue: 5 of this
    book's 30 configured names (INJ, RUNE, STX, GALA, W) and 2 of the family
    bot's 15 (ATOM, ALGO) are NOT LISTED on Lighter. They were typed when the
    venue carried a different set and never re-checked. Dead names cost a
    backfill call each, make `len(COINS)` a lie in every log line, and — on a
    book that needs `2*K` rankable coins to rebalance at all — can be the
    difference between rebalancing and skipping.

    `supports` is injected (the venue's own `ctx.supports`) so this is pure and
    offline-testable. A supports() that RAISES keeps the coin: an unreachable
    venue must never silently empty a book's universe.
    """
    live, dead = [], []
    for c in coins:
        try:
            ok = bool(supports(c))
        except Exception:  # noqa: BLE001
            ok = True                 # venue unreachable -> keep, never prune blind
        (live if ok else dead).append(c)
    return live, dead


def resolve_universe(configured, width, min_vol_m, current_time=None):
    """Configured coins first (the validated core, order preserved), then the
    scout's most-liquid books up to `width`. A dark/stale scout, a raising
    bus, a born-dark import or `width <= 0` all return the configured list
    UNCHANGED — the widening is an enhancement, never a dependency."""
    out = list(dict.fromkeys(str(c).strip().upper() for c in configured if str(c).strip()))
    if not width or int(width) <= 0 or fleet_bus is None:
        return out
    try:
        extra = fleet_bus.scout_universe(min_vol_m=min_vol_m,
                                         current_time=current_time)
    except Exception:  # noqa: BLE001
        return out
    have = set(out)
    for sym in extra:
        if len(out) >= int(width):
            break
        s = str(sym).strip().upper()
        if s and s not in have:
            out.append(s)
            have.add(s)
    return out


# [2026-07-30 AUTO-REVERT FIX] The operator's env defaults, snapshotted at
# IMPORT. apply_tuning() must hand THESE to get_lever, never the current
# global: get_lever returns its `default` when the lever is absent, expired
# or quarantined, so passing the already-moved value made the rail a ONE-WAY
# RATCHET — a widened lever could never revert, and auto-revert-on-expiry is
# the growth rail's central safety property ("levers EXPIRE back to defaults
# on their own, so auto-revert is the resting state"). Shipped broken in
# (fz); it was inert only because nothing authored the lane yet.
# [2026-07-30 (gu)] EXIT_BPS added HERE too, not just to the loop above.
# `apply_tuning` reads `_ENV_DEFAULTS[attr]`, and a missing key raises a
# KeyError that the loop's own `except Exception: continue` swallows — so
# the lever would be registered, consumed-looking, and silently INERT.
# Same shape as the (fz) auto-revert ratchet: the snapshot is what makes an
# expired lever revert to the operator default instead of ratcheting.
_ENV_DEFAULTS = {"ENTER_PCT": ENTER_PCT, "UNIVERSE_N": UNIVERSE_N,
                 "EXIT_BPS": EXIT_BPS}


def apply_tuning():
    """Growth-rail levers over the env defaults; {} when the rail is dark."""
    # [2026-07-30 (gu)] EXIT_BPS joins the consumed set — the fleet's first
    # exit lever. It governs BOTH sides on this book: the convergence target
    # AND, via ENTER_FLOOR_MULT, the floor of the adaptive entry gate. Measured
    # live: the floor (EXIT_BPS * 1.5 = 60bps) sat above the p90 (21.8bps) of
    # the residual distribution the gate adapts to, so the adaptation could
    # only descend to a bound set by a stale constant. Registering it changes
    # nothing by itself (default unchanged at 40); it makes the constant
    # reachable by the organ that measures the distribution.
    global ENTER_PCT, UNIVERSE_N, EXIT_BPS
    if tuning is None:
        return {}
    moved = {}
    for lever, attr in (("disloc.enter_pct", "ENTER_PCT"),
                        ("disloc.universe_n", "UNIVERSE_N"),
                        ("disloc.exit_bps", "EXIT_BPS")):
        cur = globals()[attr]
        try:
            val = tuning.get_lever(lever, _ENV_DEFAULTS[attr])
        except Exception:  # noqa: BLE001
            continue
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


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
            # [2026-07-30 (gr)] EXIT TELEMETRY — these were computed two lines
            # above (for pnl_pct) and then THROWN AWAY. publish_paper_trade has
            # accepted them since 17-Jul, the DB column exists, the reader
            # SELECTs them and /trades.json exposes them: 8 of 9 bots simply
            # never filled the pipe. Without the prices no exit rule can be
            # counterfactually tested, because the price PATH cannot be joined
            # to the trade. Telemetry only — no gate moves.
            entry_price=ent_px, exit_price=exit_px,
            venue=venue, shadow=shadow)
    except Exception:  # noqa: BLE001
        pass


def main():
    global COINS          # widened from the scout below
    p = argparse.ArgumentParser(description="Snap Back — Lighter dislocation harvester")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    # [2026-07-16 AUDIT] a lost Railway VENUE var silently booted hl_paper:
    # unsuffixed row id (the -lshadow row went stale) + a Hyperliquid book
    # under a Lighter-named bot (dev≈0 forever). The sniper already guards
    # itself this way; this bot is Lighter-shadow by definition.
    # (The REFERENCE is Lighter's own index as of 17-Jul; this guard is about
    # the BOOK the bot reads and prices against, which must be Lighter's.)
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
    noconv = {}          # coin -> ts of a max_hold (non-converged) close;
                         # entry-embargoed until |dev| first dips below
                         # EXIT_BPS (21-Jul: the APEX 6-round-trip lesson)
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

    # [2026-07-30] Levers BEFORE the universe (UNIVERSE_N is itself a lever),
    # and the entry bar starts at the operator's constant — the adaptive value
    # only takes over once a loop has actually measured a distribution.
    _moved = apply_tuning()
    COINS = resolve_universe(COINS, UNIVERSE_N, UNIVERSE_MIN_VOL_M)
    COINS, _dead = prune_dead(COINS, ctx.supports)
    if _dead:
        log.warning("pruned %d symbol(s) the venue does not list: %s",
                    len(_dead), ", ".join(_dead))
    enter_bps_eff = ENTER_BPS
    log.info("universe: %d coins | entry gate starts at %.0fbps "
             "(adaptive p%.1f, floored at %.0fbps)%s",
             len(COINS), enter_bps_eff, ENTER_PCT * 100,
             EXIT_BPS * ENTER_FLOOR_MULT,
             f" | levers {_moved}" if _moved else "")

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
                                     "style": "dislocation",
                                     "caps": {"enter_pct": ENTER_PCT,
                                              "universe": len(COINS)}})
            except Exception:  # noqa: BLE001
                pass
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        ref = reference_prices()
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
        devs_this_loop = []
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
                # [2026-07-30] the sample the NEXT loop's adaptive gate is
                # computed from — every book we could actually see this loop.
                devs_this_loop.append(dev_bps)

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
                    if abs(dev_bps) >= enter_bps_eff:
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
                        # [2026-07-21 AUDIT FIX] a max_hold close means the
                        # dislocation did NOT converge inside the hold — a
                        # PERSISTENT basis, not a fade opportunity. The old
                        # code re-armed pend[] immediately (dev still >=
                        # ENTER_BPS every loop), so the bot round-tripped
                        # the same standing basis over and over: measured
                        # 20-21 Jul, SIX consecutive APEX max_hold cycles in
                        # 16h, 5 losses, re-entry ~3.5min after each exit.
                        # The coin now sits out until its deviation first
                        # falls back BELOW EXIT_BPS (proof the basis
                        # actually cleared) — the same shape as the taker's
                        # post-stop cooldown, expressed in the bot's own
                        # signal domain.
                        if reason == "max_hold":
                            noconv[coin] = time.time()
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
                # [2026-07-21] non-convergence quarantine: after a max_hold
                # close the coin is only eligible again once |dev| has been
                # seen BELOW EXIT_BPS (the basis cleared) — see the close
                # path above.
                if coin in noconv:
                    if abs(dev_bps) <= EXIT_BPS:
                        noconv.pop(coin, None)   # basis cleared — re-armed
                    else:
                        pend[coin] = 0
                        continue
                tradeable = abs(dev_bps) >= enter_bps_eff
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
            log.info("reference-blind (no Lighter index) — no signals this loop.")

        # ---- publish + persist ----
        try:
            store.publish(
                bot_id, status="online",
                equity=broker.equity(),
                pnl_abs=broker.equity() - START_EQUITY,
                open_trades=broker.open_count(),
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": ctx.mode, "venue": ctx.mode, "style": "dislocation",
                       "caps": {"enter_pct": ENTER_PCT,
                                "universe": len(COINS)},
                       # [2026-07-30 SIGN BUG] was `sorted(meta.keys())` — a
                       # bare LIST, which fleet_risk's held_items() maps to
                       # side "" and classifies as LONG (correct for the
                       # long-only publishers of that shape, wrong here: this
                       # book is TWO-SIDED, `is_long = dev_bps < 0`). Its
                       # SHORTS were therefore counted as longs in the
                       # per-symbol pileup cap, which is published
                       # mode=enforce and consumed by the family bot — so a
                       # Snap Back short could veto a family LONG entry on the
                       # same symbol. Latent while this book held nothing;
                       # the 30-Jul gate/universe widening is exactly what
                       # activates it. Same dict contract Counterweight and
                       # the sniper already publish.
                       "held": {c: ("L" if m.get("is_long") else "S")
                                for c, m in meta.items()},
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
        # [2026-07-30] Re-base the entry bar from THIS loop's measured
        # residual distribution, for the NEXT loop. Computed after the scan
        # (never mid-scan) so every coin in one pass is judged against the
        # same bar — a bar that moved between coins would make the book's own
        # census unreadable. Levers are re-read here too, so a TTL expiry
        # reverts the percentile without a restart.
        apply_tuning()
        _prev_gate = enter_bps_eff
        enter_bps_eff = adaptive_enter_bps(
            devs_this_loop, ENTER_PCT, EXIT_BPS, ENTER_FLOOR_MULT,
            ENTER_BPS, ENTER_MIN_N)
        if abs(enter_bps_eff - _prev_gate) >= 1.0:
            log.info("entry gate %.0f -> %.0fbps (p%.1f of %d residuals, "
                     "floor %.0f, cap %.0f)", _prev_gate, enter_bps_eff,
                     ENTER_PCT * 100, len(devs_this_loop),
                     EXIT_BPS * ENTER_FLOOR_MULT, ENTER_BPS)
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


def selftest():
    """[2026-07-17] Offline checks for the reference swap (HL mids -> Lighter's
    own index). No network, no DB. This bot had NO selftest before the swap;
    the reference is the one input the whole strategy is denominated in, so it
    gets pinned now.
    """
    print("Running Snap Back offline self-test...\n")

    # ---- the happy parse
    books = [{"symbol": "BTC", "status": "active", "index_price": "62800.2"},
             {"symbol": "ETH", "status": "active", "index_price": 1827.34}]
    assert index_from_books(books) == {"BTC": 62800.2, "ETH": 1827.34}

    # ---- NEGATIVE FIXTURES: every shape that must NOT become a reference.
    # A bad reference is worse than none: `dev_bps = mid/ref - 1` turns a junk
    # ref into a fake ~10,000 bps dislocation, which clears the 150 bps entry
    # gate by 60x. Each of these must be ABSENT from the map, so the coin is
    # simply skipped (`if not r: continue`) rather than traded against garbage.
    for bad, why in [
        ({"symbol": "X", "status": "inactive", "index_price": "5"}, "inactive book"),
        ({"symbol": "X", "status": "active", "index_price": 0}, "zero index"),
        ({"symbol": "X", "status": "active", "index_price": None}, "null index"),
        ({"symbol": "X", "status": "active"}, "missing index"),
        ({"symbol": "X", "status": "active", "index_price": "abc"}, "junk index"),
        ({"symbol": "X", "status": "active", "index_price": -5.0}, "negative index"),
        ({"symbol": None, "status": "active", "index_price": "5"}, "no symbol"),
        ({"status": "active", "index_price": "5"}, "no symbol key"),
    ]:
        assert "X" not in index_from_books([bad]), f"{why} must NOT yield a reference"
    # ...and one junk row must not poison its healthy neighbours
    assert index_from_books([{"symbol": "A", "status": "active", "index_price": "x"},
                             {"symbol": "B", "status": "active", "index_price": "2"}]) \
        == {"B": 2.0}

    # ---- reference-blind contract: empty/none in -> empty out. main() only
    # signals `if ref:`, so {} is the fail-safe (do nothing), never a default.
    assert index_from_books([]) == {} and index_from_books(None) == {}

    # ---- the gap maths this reference feeds, at the REAL gates. A reference
    # 3.8 bps different (the measured HL-vs-index median, 17-Jul) cannot move a
    # decision at ENTER_BPS=150; that is why the swap is signal-neutral.
    mid, ref = 100.0, 100.0
    assert abs((mid / ref - 1) * 1e4) < PRE_BPS                    # no signal
    assert ((101.6 / 100.0 - 1) * 1e4) >= ENTER_BPS                # +160bps rich
    assert ((98.4 / 100.0 - 1) * 1e4) <= -ENTER_BPS                # -160bps cheap
    _drift = (100.038 / 100.0 - 1) * 1e4                           # 3.8 bps
    assert _drift < PRE_BPS and _drift < EXIT_BPS, _drift

    # ---- the reference must come from LIGHTER, asserted on the CALL the
    # function makes rather than on its source text (the docstring names
    # api.hyperliquid.xyz to record what it replaced — grepping source would
    # trip on the history it is important to keep). Drive it with a stubbed
    # transport and pin the host it actually dials.
    assert "zklighter" in LIGHTER_API, LIGHTER_API
    _calls = []

    class _Resp:
        def read(self):
            return json.dumps({"order_book_details": [
                {"symbol": "BTC", "status": "active", "index_price": "7"}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    _real_open = urllib.request.urlopen
    try:
        urllib.request.urlopen = lambda req, *a, **k: (
            _calls.append(req.full_url), _Resp())[1]
        assert reference_prices() == {"BTC": 7.0}, "live parse path broken"
        assert len(_calls) == 1, _calls
        assert "zklighter" in _calls[0], f"reference must dial LIGHTER: {_calls[0]}"
        assert "hyperliquid" not in _calls[0].lower(), _calls[0]
        assert "orderBookDetails" in _calls[0], _calls[0]
        # a transport failure must be reference-BLIND, never a partial map
        urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("503"))
        assert reference_prices() == {}, "a dead reference feed must return {}"
    finally:
        urllib.request.urlopen = _real_open

    # [2026-07-30 ADAPTIVE GATE] the bar must track the venue but never fall
    # below the round trip that earns the capture, and a thin sample must
    # never be treated as a distribution.
    _many = [1.0] * 99 + [500.0]            # p98 of this sample is 1.0
    assert adaptive_enter_bps(_many, 0.98, 40.0, 1.5, 150.0, 20) == 60.0, \
        "a CALM venue floors at EXIT_BPS*mult (60), never chases the median"
    _wide = [80.0] * 50 + [400.0] * 50       # p98 lands in the 400s
    assert adaptive_enter_bps(_wide, 0.98, 40.0, 1.5, 150.0, 20) == 150.0, \
        "a DISLOCATED venue is capped at the operator constant, never above"
    _mid = [90.0] * 100
    assert adaptive_enter_bps(_mid, 0.98, 40.0, 1.5, 150.0, 20) == 90.0, \
        "between floor and cap the percentile itself is the bar"
    assert adaptive_enter_bps([200.0] * 5, 0.98, 40.0, 1.5, 150.0, 20) == 150.0, \
        "n below the floor -> the configured constant (never guess low)"
    assert adaptive_enter_bps([], 0.98, 40.0, 1.5, 150.0, 20) == 150.0
    assert adaptive_enter_bps([None, "x"], 0.98, 40.0, 1.5, 150.0, 20) == 150.0, \
        "junk sample -> the configured constant"
    assert adaptive_enter_bps([-90.0] * 100, 0.98, 40.0, 1.5, 150.0, 20) == 90.0, \
        "the gate is on |residual| — a CHEAP book counts like a rich one"
    # universe widening: adds to the core, never replaces or shrinks it
    _savedb = globals().get("fleet_bus")
    try:
        class _FB:
            out = ["SOL", "BTC"]

            @staticmethod
            def scout_universe(min_vol_m=0.0, current_time=None):
                return _FB.out

        globals()["fleet_bus"] = _FB
        assert resolve_universe(["BTC"], 3, 0.5) == ["BTC", "SOL"], "adds, dedups"
        assert resolve_universe(["BTC"], 0, 0.5) == ["BTC"], "0 = revert switch"
        _FB.out = []
        assert resolve_universe(["BTC"], 9, 0.5) == ["BTC"], "dark scout never shrinks"
        globals()["fleet_bus"] = None
        assert resolve_universe(["BTC"], 9, 0.5) == ["BTC"], "born-dark is safe"
    finally:
        globals()["fleet_bus"] = _savedb

    print("All Snap Back self-tests passed (Lighter index parses; inactive/"
          "zero/null/junk/negative refs are SKIPPED not traded; empty stays "
          "reference-blind; 3.8bps reference drift cannot move a 150bps gate; "
          "adaptive gate floors/caps/thin-sample; universe widening).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        try:
            _supervised()
        except KeyboardInterrupt:
            log.info("stopped by user.")
