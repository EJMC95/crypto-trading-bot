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

# [2026-07-30] growth rail; Dockerfile.trendlighter already COPYs fleet_tuning.
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None
# [2026-07-30 (hk)] THE VENUE'S UNIVERSE. `(fz)` claimed five books were widened
# off the scout; only TWO consumers ever shipped (dislocation, funding-spread).
# This book was named in the changelog, in CLAUDE.md and in fleet_bus' own
# docstring and got NOTHING: no import here, and no `fleet_bus.py` in
# Dockerfile.trendlighter. It has ranked 6 of 220 markets the whole time.
# Measured on the live bus the day this shipped: `scout_universe(min_vol_m=1)`
# returns 32 books, FIVE of them golden right now (HYPE, ZEC, LIT, NVDA, TRX)
# — the book could see exactly one of the five. A ranked selector cannot pick
# a winner it never sees. The COPY lands in the SAME commit as this import;
# split across two, it ships born-dark (audit_image_imports enforces).
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None
import funding_basis
from venues import marks, venue_context
from venues.safety import open_notional

BOT = "crypto-trend-daily"          # venue layer suffixes -lshadow / -lighter
H = funding_basis.periods_per_year('lighter')   # [2026-07-17 BASIS FIX]

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
# [2026-07-30 CONNECT IT TO THE PROVEN EDGE — default 0 -> 1] Every
# profitable book in this fleet is a funding book; every purely directional
# one is flat or negative on this one-regime tape. This book ranks its
# candidates; ranking them by funding costs nothing, changes no entry gate,
# and points the one free choice it makes at the signal class that actually
# earns here. Registry-bounded lever `trend.rank_by_funding` (0/1).
RANK_BY_FUNDING = os.environ.get("TREND_RANK_BY_FUNDING", "1").lower() in ("1", "true", "yes")
# [2026-07-30 (hk)] The scout-fed widening. UNIVERSE_N is the TOTAL ceiling
# (configured core first, order preserved, then the scout's most-liquid books).
# 24 is deliberate and not the venue's whole list: `golden()` needs EMA_SLOW+2
# = 202 CLOSED daily bars, so a young book returns None and is skipped as
# "insufficient daily history" — correct, but it costs a candle fetch per loop
# per coin. 24 buys ~4x the candidates the six majors gave at a bounded REST
# cost, and `trend.universe_n` can walk it further on measured evidence.
# MIN_VOL_M is the scout-side liquidity floor: a 1x long that holds for WEEKS
# must be exitable, and the fleet has already been burned by one-sided debut
# books (see the sniper's YOUNG_MIN_VOL_M).
UNIVERSE_N = int(os.environ.get("TREND_UNIVERSE_N", "24"))
MIN_VOL_M = float(os.environ.get("TREND_MIN_VOL_M", "3.0"))
# [2026-07-30 (hk)] THE WIDENING CHANGES WHAT KIND OF BOOK THIS IS — say so.
# The scout ranks the whole venue by turnover, and measured on the live bus the
# ten books it adds are XAU, HYPE, SKHYNIXUSD, SNDK, MU, WTI, LIT, SPCX, XAG,
# SOXL: NINE of the ten are tokenised equities/commodities. A book whose row id
# is `crypto-trend-daily` becomes a venue-wide trend follower.
#
# KEPT ON, deliberately, and the reasons are specific rather than "more is
# better": (1) the signal is per-coin EMA50/200 computed from THAT COIN'S OWN
# candles, so it is per-asset by construction and does NOT breach the item-18
# prerequisite (never BTC's gate for SPY/XAU/WTI) — the defect that rule exists
# to prevent cannot occur here; (2) item 18 wants exactly this: the venue's
# non-crypto books are the fleet's ONLY source of a regime that is not
# falling-BTC; (3) the 202-closed-bar floor in golden() admits only books with
# real history. TREND_ALLOW_TRADFI=0 reverts to crypto-only in one env var.
#
# HONEST SCOPE: the 2.7yr +52% validation behind this bot is SIX CRYPTO MAJORS
# on Kraken spot. It says nothing about XAU or SOXL. Those sleeves are
# unvalidated and are here to be GRADED, on a $1k shadow book — that is the
# whole point of widening a book that had produced zero closes in 20 days.
ALLOW_TRADFI = os.environ.get("TREND_ALLOW_TRADFI", "1").lower() not in (
    "0", "false", "no", "off")
# Tokenised non-crypto bases, mirroring lighter_ticket_taker.TRADFI_BASES'
# LOCAL-and-env-driven pattern (a cross-import would drag pandas into this
# lean image — the born-dark trap). Only consulted when ALLOW_TRADFI is off.
TRADFI_BASES = {s.strip().upper() for s in os.environ.get(
    "TREND_TRADFI_BASES",
    "SPY,QQQ,IWM,US100,US500,SOXL,AMD,MU,HOOD,RKLB,TSLA,NVDA,AAPL,MSFT,META,"
    "GOOGL,GOOG,AMZN,COIN,MSTR,PLTR,TSM,INTC,SKHYNIX,SKHYNIXUSD,AMAT,EWY,LITE,"
    "CRCL,BMNR,SNDK,NBIS,MRVL,ASML,BABA,DELL,ORCL,QCOM,AVGO,ARM,SMCI,SPCX,"
    "ZHIPU,CBRS,WTI,BRENTOIL,NATGAS,USOIL,XAU,XAG,XCU,XPD,XPT,PAXG,WHEAT,CORN,"
    "USDJPY,AUDUSD,EURUSD,GBPUSD,USDCNH").split(",") if s.strip()}
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


# [2026-07-30 (hk)] THE EXIT PREDICATES, lifted out of the loop so a test can
# bind the CODE THAT RUNS instead of a copy of it. My first cut of the exit
# selftest re-implemented these three inline; mutation-testing showed it stayed
# GREEN when the production death cross was disabled — a test of my own
# reasoning, not of the bot. Same class as the four publisher/consumer defects
# this repo logged on 30-Jul. Extracting them is the fix; the logic is
# unchanged, byte for byte, from what the loop did before.
def exit_reason(is_golden, draw):
    """'death_cross' | 'catastrophic_stop' | None for a HELD long.

    Death cross is checked FIRST and unconditionally: the trend rule is the
    real exit and the stop is only a seatbelt, so a coin that has both flipped
    bearish AND blown the stop exits as a death cross.
    """
    if not is_golden:
        return "death_cross"
    if draw <= -CATASTROPHIC_STOP:
        return "catastrophic_stop"
    return None


def seatbelt_hit(px, entry):
    """The candle-independent stop. When candles fail there is no trend signal,
    but a live price is still enough to honour the seatbelt."""
    return bool(px and entry and (px - entry) / entry <= -CATASTROPHIC_STOP)


def skip_coin(supported, held):
    """True to skip this coin entirely this cycle.

    A HELD coin is NEVER skipped: `supports()` answers an ENTRY question, and
    skipping a held position on a delist or a venue blip removed its exit, its
    stop and its seatbelt in one line.
    """
    return (not supported) and not held


def fresh_mid(ctx, coin):
    """Live-book mid, or None. Never a stale funding-map mark (the catastrophic
    stop must see a real price). Shared impl: venues/marks.py (also sorts the
    unsorted REST-snapshot fallback, which this local copy did not)."""
    return marks.fresh_mid(ctx.venue, coin)


# [2026-07-17] The cap rule now lives on the RAIL that enforces it
# (venues.safety.open_notional) — this bot and lighter_funding_bot each carried
# their own code-identical copy with DIFFERENT selftests (this one never
# covered the short-at-own-entry case), and the Ticket Taker's live path would
# have been the third. Re-exported under the original private name so every
# call site and _selftest_notional() below are unchanged.
_open_notional = open_notional


def resolve_universe(configured, width, min_vol_m, current_time=None):
    """Configured coins first (the validated majors, order preserved), then the
    scout's most-liquid books up to `width`.

    CONTRACT, identical to the sibling books: a dark/stale scout, a raising bus,
    a born-dark import or `width <= 0` all return the configured list UNCHANGED.
    The widening is an ENHANCEMENT, never a DEPENDENCY — no organ outage may
    shrink this book's universe. It is additive only; it can never DROP a
    configured coin, which is what makes `scan_universe`'s orphan rule below a
    backstop rather than the primary defence.
    """
    out = list(dict.fromkeys(str(c).strip().upper() for c in configured
                             if str(c).strip()))
    if not width or int(width) <= 0 or fleet_bus is None:
        return out
    try:
        extra = fleet_bus.scout_universe(min_vol_m=min_vol_m,
                                         current_time=current_time)
    except Exception:  # noqa: BLE001
        return out
    have = set(out)
    for sym in extra or ():
        if len(out) >= int(width):
            break
        s = str(sym).strip().upper()
        # The tradfi filter applies to SCOUT-ADDED books only — a configured
        # coin is the operator's choice and is never filtered out by it.
        if not ALLOW_TRADFI and s in TRADFI_BASES:
            continue
        if s and s not in have:
            out.append(s)
            have.add(s)
    return out


def scan_universe(configured, held, width, min_vol_m, current_time=None):
    """The coins this loop will actually look at = the resolved universe PLUS
    every coin currently HELD.

    [2026-07-30 (hk)] THIS IS THE PREREQUISITE FOR THE WIDENING, not a nicety.
    The scan loop evaluates exits ONLY for coins it iterates, and this book has
    no orphan reconciliation of its own: `_flatten_all` is the only sweeper and
    it is `not dry_run`-gated, so the SHADOW arm has none at all. Before this,
    a coin that left the configured list — an env edit, a lever step, a scout
    reshuffle — kept its position with no exit path, no stop and no seatbelt,
    permanently. Making the universe DYNAMIC is exactly what turns that latent
    trap into a live one, so the two land together.

    Held coins are appended, never inserted: admission order (and therefore who
    wins a scarce slot) is unchanged for the configured core.
    """
    out = resolve_universe(configured, width, min_vol_m, current_time)
    have = set(out)
    for c in held or ():
        s = str(c).strip().upper()
        if s and s not in have:
            out.append(s)
            have.add(s)
    return out


def _record_close(bot, coin, ent_px, ent_ts, exit_px, price_pnl, fund_pnl, reason,
                  order_usd=ORDER_USD, venue=None, shadow=None):
    pnl = float(price_pnl) + float(fund_pnl)
    # pnl_pct on the ENTRY clip (callers pass meta['clip']) so a mid-hold
    # growth-rail clip change can't distort the per-trade return.
    pnl_pct = (pnl / (order_usd or 1.0)) if ent_px else None
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=pnl, pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            # [2026-07-30 (gr)] EXIT TELEMETRY — computed above for pnl_pct,
            # then discarded. publish_paper_trade has accepted these since
            # 17-Jul, the DB column exists, the reader SELECTs them and
            # /trades.json exposes them: 8 of 9 bots never filled the pipe.
            # Without the prices no exit rule can be counterfactually
            # tested — the price PATH cannot be joined to the trade.
            # Telemetry only; no gate moves.
            entry_price=ent_px, exit_price=exit_px,
            reason="long_" + reason, venue=venue, shadow=shadow)
    except Exception:  # noqa: BLE001
        # [2026-07-30 (hk)] WAS `pass`, with no log. Never raise out of a close
        # — a ledger write must not abort the trading loop — but never swallow
        # it silently either: `n_closed` re-seeds from the ledger at boot
        # (fetch_paper_aggregate), so a lost row disappears from the ledger AND
        # from the counter, and the book reads as "never closed". On a rule that
        # produces a handful of closes a year that is a large share of the whole
        # evidence base, and it is indistinguishable from the (correct) "the
        # signal has not flipped" state this book spent 20 days in.
        log.exception("LEDGER WRITE FAILED for %s close (%s) — the trade "
                      "HAPPENED; this row is lost. pnl %+.4f on clip %s",
                      coin, reason, pnl, order_usd)


# [2026-07-30 AUTO-REVERT FIX] see the sibling books.
_ENV_DEFAULT_RANK = 1 if RANK_BY_FUNDING else 0
# [2026-07-30 (hk)] The operator's env defaults snapshotted at IMPORT, so an
# expired/quarantined lever reverts to the OPERATOR's number rather than the
# already-moved global. Passing the current value is the one-way ratchet (gc)
# had to fix on all six books; the snapshot is what prevents it here.
_ENV_DEFAULTS = {"UNIVERSE_N": UNIVERSE_N, "MIN_VOL_M": MIN_VOL_M,
                 "MAX_OPEN_POSITIONS": MAX_OPEN_POSITIONS}


def apply_tuning():
    """Growth-rail levers over the env defaults; {} when the rail is dark."""
    global RANK_BY_FUNDING, UNIVERSE_N, MIN_VOL_M
    if tuning is None:
        return {}
    moved = {}
    cur = 1 if RANK_BY_FUNDING else 0
    try:
        # the ENV default, never the current global — see the auto-revert
        # note in the sibling books: passing `cur` makes the rail a one-way
        # ratchet, because get_lever returns its default on expiry.
        val = tuning.get_lever("trend.rank_by_funding", _ENV_DEFAULT_RANK)
    except Exception:  # noqa: BLE001
        return {}
    if int(val) != cur:
        RANK_BY_FUNDING = bool(int(val))
        moved["trend.rank_by_funding"] = int(val)
    # [(hk)] the two levers that can actually move this book's TRADE RATE.
    # `trend.rank_by_funding` never could: it only reorders admission, and it
    # is documented-inert while candidates <= slots — measured, the maximum
    # number of simultaneously-golden coins over 192 aligned days was ONE,
    # against six slots. A book whose only lever cannot change what it trades
    # has no growth rail at all, which is precisely the (fz) failure class one
    # level up. Each is refreshed EVERY loop so a TTL expiry reverts by the
    # same path that applied it.
    for lever, attr, cast in (("trend.universe_n", "UNIVERSE_N", int),
                              ("trend.min_vol_m", "MIN_VOL_M", float),
                              ("trend.max_open", "MAX_OPEN_POSITIONS", int)):
        try:
            v = cast(tuning.get_lever(lever, _ENV_DEFAULTS[attr]))
        except Exception:  # noqa: BLE001
            continue
        if v != globals()[attr]:
            globals()[attr] = v
            moved[lever] = v
    return moved


def main():
    p = argparse.ArgumentParser(description="Tide Rider — Lighter 1x long trend")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    global _SUPERVISOR_BOT_ID
    # [2026-07-17 VENUE MUST BE EXPLICIT — real money] The hl_paper refusal below
    # was written when hl_paper was the DEFAULT: it catches a lost $VENUE landing
    # on the unsuffixed live-colliding id. The default is now lighter_shadow
    # (ff5cd43), so that guard no longer covers the lost-var case at all — a lost
    # VENUE sails past it into "crypto-trend-daily-lshadow", the id the
    # tide-rider-lighter-shadow service already publishes (online, $999.76). Two
    # writers, one row, no page, while THIS service's real positions go unmanaged.
    # Both services set VENUE explicitly, so this is inert for them.
    if not os.environ.get("VENUE", "").strip() and not args.once:
        raise SystemExit(
            "VENUE is unset. This bot's identity — and whether it trades REAL "
            "MONEY — comes from it, and every mode's id collides with a row some "
            "other service already publishes. An inherited default must never "
            "decide that. Set VENUE=lighter_live or VENUE=lighter_shadow "
            "explicitly (or pass --once for an offline smoke).")
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

    # [(hr)] bound BEFORE the branch: the accrual-clock restore below reads it

    # in BOTH paths, and relying on a NameError to mean 'no state' is a guard

    # that works by accident.

    _saved = None

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

    def _real_exit(coin, fallback):
        """[2026-07-16 FILL RECON] REAL exit fill (venue trades read; this
        bot is long-only, so a close always SELLS -> is_ask=True) or the
        decision price. Entry fills are already venue-real via the manage
        pass's avg_entry_price rebuild."""
        if dry_run:
            return fallback
        try:
            fl = getattr(ctx.venue, "last_fill", None)
            real = fl(coin, is_ask=True,
                      since_ts=time.time() - 180) if fl else None
        except Exception:  # noqa: BLE001
            real = None
        if real:
            log.info("%s exit fill (venue): %.6g (decision %.6g)", coin, real,
                     fallback or 0.0)
        return real or fallback

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
            px = _real_exit(c, px)
            price_pnl = abs(held) * (px - entry)
            n_closed += 1
            n_wins += 1 if price_pnl > 0 else 0
            _record_close(bot_id, c, entry, opened_ts, px, price_pnl, m.get("accrued", 0.0),
                          reason, order_usd=float((m or {}).get("clip") or order_usd),
                          venue=venue_tag, shadow=shadow_tag)
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
            px = _real_exit(coin, px)
            price_pnl = abs(held) * (px - entry)
        realized += (price_pnl + fund_pnl) if dry_run else 0.0
        n_closed += 1
        n_wins += 1 if (price_pnl + fund_pnl) > 0 else 0
        log.info("CLOSE %s long | price %+.2f funding %+.2f [%s]",
                 coin, price_pnl, fund_pnl, reason)
        _record_close(bot_id, coin, entry, opened_ts, px, price_pnl, fund_pnl,
                      reason, order_usd=float((m or {}).get("clip") or order_usd),
                      venue=venue_tag, shadow=shadow_tag)
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
    # [2026-07-31 (hr)] RESTORE THE FUNDING-ACCRUAL CLOCK. It reset to boot time
    # on every redeploy, so the funding accrued during the gap was never counted
    # — a systematic UNDERCOUNT of the drag this 1x-long book pays, and this
    # book holds for WEEKS. 📊 Index Rider fixed exactly this on 16-Jul at :505
    # and 🌊 was left behind; today it deployed 3 times, so the loss is not
    # theoretical (TRX alone has accrued +$1.05 on a ~$30 notional).
    # Gap bounded to 48h so ancient state cannot over-accrue in one tick.
    try:
        _lt = float((_saved or {}).get("last_ts") or 0)
    except Exception:  # noqa: BLE001 — incl. unbound saved-state
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()
    _last_universe = list(COINS)

    while True:
        t0 = time.time()
        # [2026-07-12 GO-GREEN] loop-top liveness touch — see bot_pnl_store.heartbeat
        store.heartbeat(bot_id)
        # [2026-07-30] growth rail, every loop (TTL expiry reverts by the
        # same path that applied the lever).
        _lv = apply_tuning()
        if _lv:
            log.info("levers applied %s", _lv)
        # [2026-07-15 GROWTH RAIL] live clip re-read each loop: the evidence
        # board's bounded live.clip_scale lever applies to NEW entries only
        # (open positions untouched); reverts with the lever's own expiry.
        _clip = ctx.order_usd(ORDER_USD)
        if _clip != order_usd:
            log.info("growth rail: clip %s -> %s (max_open recomputed)",
                     order_usd, _clip)
            order_usd = _clip
        # [2026-07-30 (hk)] max_open is recomputed EVERY loop, not only when the
        # clip moves. `trend.max_open` steps MAX_OPEN_POSITIONS, and under the
        # old code that new value reached `max_open` only if the clip happened
        # to change in the same cycle — so the capacity lever would have been
        # registered, consumed-looking and INERT for as long as the clip held
        # still. That is the precise failure `(ge)` found on fundspread.k.
        _mo = ctx.max_open_positions(MAX_OPEN_POSITIONS)
        if _mo != max_open:
            log.info("growth rail: max_open %s -> %s", max_open, _mo)
            max_open = _mo
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
            # [2026-07-16 AUDIT FIX] retry the daily-loss flatten every halted
            # loop — it used to run exactly ONCE at the halt transition, so a
            # single failed close left that position with NO stop until the
            # day rolled. Idempotent once flat; skip when the kill-switch path
            # just flattened this same loop.
            if not dry_run and not ctx.rails.kill_check():
                _flatten_all("daily_loss")
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
                               "held": sorted(meta.keys()),
                               # [(hk)] the RESOLVED universe, not the hand-typed core —
                               # publishing COINS is why this row read `universe: 6` for
                               # 20 days while the widening was believed shipped.
                               "coins": list(_last_universe),
                               "caps": {"rank_by_funding": RANK_BY_FUNDING,
                                        "universe": len(_last_universe),
                                        "universe_n": UNIVERSE_N,
                                        "min_vol_m": MIN_VOL_M,
                                        "configured": len(COINS)}})
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

        # [2026-07-15 GAP FIX] L2 fleet long-budget veto — Tide Rider was the
        # only real-money LONG book counted BY the light that never CHECKED
        # it (the 15-Jul consumption audit). Same contract as the family bot
        # and taker: fresh payload + mode=enforce + budget full -> skip NEW
        # entries this cycle; exits/stops untouched; anything missing/stale
        # fails OPEN (a fleet_risk outage must never stop the live book).
        # Kill switch stays central: FLEET_RISK_MODE=advisory.
        fleet_long_veto = False
        try:
            _fr = store.load_state("fleet-risk") or {}
            _age = (now - datetime.fromisoformat(
                str(_fr.get("updated")).replace("Z", "+00:00"))).total_seconds()
            _lb = _fr.get("long_budget")
            _lb = 10**9 if _lb is None else int(_lb)   # 0 is a REAL budget
            if (_age <= float(_fr.get("ttl_sec") or 900)
                    and _fr.get("mode") == "enforce"
                    and (_fr.get("long_positions") or 0) >= _lb):
                fleet_long_veto = True
                log.info("FLEET LONG-BUDGET VETO — %s/%s directional longs; "
                         "no new entries this cycle (exits unaffected)",
                         _fr.get("long_positions"), _fr.get("long_budget"))
        except Exception:  # noqa: BLE001 — fail-safe open
            fleet_long_veto = False

        # Entry-admission order. Default = COINS list order (byte-identical to before).
        # RANK_BY_FUNDING sorts lowest-funding-first so that when open_now hits the cap
        # / margin runs out, the cheapest-to-carry golden majors get the slots. Only the
        # admission order changes; per-coin management (stops/exits) is order-independent.
        # [2026-07-30 (hk)] The universe is now the scout's, not a hand-typed
        # six — plus every HELD coin, unconditionally, so a universe that moves
        # under an open position can never strand it (scan_universe).
        _held_now = [c for c, p in (pos or {}).items()
                     if (p or {}).get("size", 0.0)]
        scan_coins = scan_universe(COINS, _held_now, UNIVERSE_N, MIN_VOL_M)
        if scan_coins != _last_universe:
            _added = [c for c in scan_coins if c not in _last_universe]
            _gone = [c for c in _last_universe if c not in scan_coins]
            log.info("universe %d -> %d (+%s -%s)", len(_last_universe),
                     len(scan_coins), ",".join(_added) or "-",
                     ",".join(_gone) or "-")
            _last_universe = list(scan_coins)
        # [2026-07-30 (hl)] THE SKIP CENSUS. The row published `universe: 16`
        # while SIX of those 16 are STRUCTURALLY MUTE — golden() needs 202
        # closed daily bars and SPCX (47.9d), SOXL (48.8d), MU (90.8d),
        # SKHYNIX (112.5d), WTI (161.7d) and SNDK (170.6d) cannot produce a
        # signal at all. The payload overstated the signal-capable universe by
        # >=60%, which is the difference between "this book sees 16 books" and
        # "this book can act on 10". Counted here, published below.
        census = {"short_history": 0, "candle_err": 0, "unsupported": 0,
                  "fleet_veto": 0, "signal_capable": 0}
        if RANK_BY_FUNDING:
            scan_coins = sorted(
                scan_coins, key=lambda c: (fund.get(c) or {}).get("rate")
                if (fund.get(c) or {}).get("rate") is not None else 1e9)

        for coin in scan_coins:
            # [(hk)] A HELD coin is NEVER skipped here. `supports()` is an
            # ENTRY question; skipping a held position on a delist, a venue
            # blip or an unreachable market took away its exit, its stop and
            # its seatbelt in one line — the zombie the sibling books each
            # carry an explicit guard for. Flat coins still skip as before.
            if skip_coin(ctx.supports(coin),
                         (pos.get(coin, {}) or {}).get("size", 0.0)):
                census["unsupported"] += 1
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
                    # [2026-07-17 BASIS FIX] 8h quote accrued per hour = 8x
                    m["accrued"] = (m.get("accrued", 0.0)
                                    - funding_basis.to_hourly(rate, "lighter")
                                    * abs(held) * px * dt_h)
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
                census["candle_err"] += 1
                log.error("%s candle error: %s", coin, e)
            g = golden(closes) if closes else None

            # Seatbelt: without the signal we can't judge the trend, but the
            # catastrophic stop must still fire off a live price (candle-independent).
            if g is None:
                if held and seatbelt_hit(px, entry):
                    if close_long(coin, "catastrophic_stop", px, held, entry, opened_ts, m):
                        open_now -= 1
                elif not held:
                    census["short_history"] += 1
                    log.info("%-4s insufficient daily history (%d/%d bars); skip.",
                             coin, len(closes or ()), EMA_SLOW + 2)
                continue
            is_golden, ef, es = g
            census["signal_capable"] += 1

            if not px:
                px = closes[-1] if closes else 0.0
            if not px:
                continue

            # ----- manage an open long -----
            if held:
                draw = (px - entry) / entry if entry else 0.0     # -ve = underwater
                reason = exit_reason(is_golden, draw)
                if reason and close_long(coin, reason, px, held, entry, opened_ts, m):
                    open_now -= 1
                continue

            # ----- flat: enter long on a golden cross -----
            if is_golden and open_now < max_open:
                if fleet_long_veto:
                    census["fleet_veto"] += 1
                    continue      # L2: fleet directional-long budget is full
                size = round(order_usd / px, 6)
                if not dry_run:
                    # [2026-07-15 AUDIT FIX v2] real deployed notional (held at
                    # their own clips + this loop's opens), NOT open_now*clip —
                    # which breaches the cap when the growth rail moved the clip.
                    open_ntl = _open_notional(pos, meta, open_now, order_usd)
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
                meta[coin] = {"entry": px, "opened_ts": t0, "accrued": 0.0,
                              "clip": order_usd}   # deployed clip (notional + pnl_pct)
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
                           "held": sorted(meta.keys()),
                           # [(hk)] the RESOLVED universe, not the hand-typed core —
                           # publishing COINS is why this row read `universe: 6` for
                           # 20 days while the widening was believed shipped.
                           "coins": list(_last_universe),
                           "caps": {"rank_by_funding": RANK_BY_FUNDING,
                                    "universe": len(_last_universe),
                                    "universe_n": UNIVERSE_N,
                                    "min_vol_m": MIN_VOL_M,
                                    "max_open": max_open,
                                    "configured": len(COINS),
                                    # [(hl)] what the universe COUNT hides:
                                    # signal_capable is the only number that
                                    # says how many books this loop could act
                                    # on. Measured 6 of 16 were mute.
                                    **census}})
                # [(hl)] MTM equity series — the go-live drawdown bar reads
                # REALISED P&L only, and this book holds for weeks, so most of
                # its drawdown is open and invisible. Publish-only; the grader
                # is unchanged until there is history to read.
                store.snapshot_equity(bot_id, pub_equity, pub_open, realized)
            except Exception:
                pass
        try:
            if dry_run:
                store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                          "fund_realized": fund_realized,
                                          # [(hr)] the accrual clock — see the
                                          # restore note below.
                                          "last_ts": last_ts})
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


def _selftest_notional():
    """Same breach scenario as the funding bot: held-at-own-clip beats
    open_now*order_usd once the growth rail has moved the clip."""
    pos = {c: {"size": 1.0, "entry": 30.0} for c in "ABCDE"}
    meta = {c: {"clip": 30.0, "entry": 30.0} for c in "ABCDE"}
    assert _open_notional(pos, meta, 5, 22.50) == 150.0
    assert _open_notional(pos, {}, 5, 22.50) == 150.0          # venue-entry fallback
    assert _open_notional({c: {"size": 1.0} for c in "ABCDE"}, {}, 5, 22.50) == 112.5
    assert _open_notional(pos, meta, 7, 22.50) == 195.0
    print("lighter_trend_bot _selftest_notional OK")


def _selftest_universe():
    """[2026-07-30 (hk)] The widening's contract, and the orphan rule that has
    to hold before the universe is allowed to move at all."""
    global fleet_bus, UNIVERSE_N, MIN_VOL_M
    core = ["BTC", "ETH", "SOL", "BNB", "XRP", "TRX"]
    _real = fleet_bus

    class _Bus:
        def __init__(self, out): self.out, self.calls = out, []
        def scout_universe(self, min_vol_m=0.0, current_time=None):
            self.calls.append(min_vol_m)
            if isinstance(self.out, Exception):
                raise self.out
            return list(self.out)

    try:
        # --- FAIL-SAFE: any doubt keeps the configured list, never shrinks ---
        # This is the contract clause that matters. A dark organ must not be
        # able to take this book's universe away — the widening is an
        # ENHANCEMENT, never a DEPENDENCY.
        fleet_bus = None
        assert resolve_universe(core, 24, 5.0) == core, "born-dark must keep the list"
        fleet_bus = _Bus([])
        assert resolve_universe(core, 24, 5.0) == core, "empty scout must keep the list"
        fleet_bus = _Bus(RuntimeError("bus down"))
        assert resolve_universe(core, 24, 5.0) == core, "raising bus must keep the list"
        fleet_bus = _Bus(["HYPE", "ZEC"])
        assert resolve_universe(core, 0, 5.0) == core, "width 0 must keep the list"
        assert resolve_universe(core, -3, 5.0) == core

        # --- ADDITIVE, ordered, deduped, and capped by width ---
        fleet_bus = _Bus(["HYPE", "ZEC", "LIT", "NVDA"])
        got = resolve_universe(core, 24, 5.0)
        assert got[:6] == core, f"configured core must lead, in order: {got}"
        assert got == core + ["HYPE", "ZEC", "LIT", "NVDA"], got
        assert resolve_universe(core, 8, 5.0) == core + ["HYPE", "ZEC"], "width caps"
        assert resolve_universe(core, 6, 5.0) == core, "width == len(core) adds none"
        # a scout echoing a configured coin must not duplicate it
        fleet_bus = _Bus(["btc", "TRX", "HYPE"])
        assert resolve_universe(core, 24, 5.0) == core + ["HYPE"]
        # the liquidity floor is PASSED THROUGH, not ignored
        b = _Bus(["HYPE"]); fleet_bus = b
        resolve_universe(core, 24, 12.5)
        assert b.calls == [12.5], b.calls

        # --- the tradfi switch, both ways, and its blast radius ---
        global ALLOW_TRADFI
        _at = ALLOW_TRADFI
        try:
            fleet_bus = _Bus(["HYPE", "XAU", "SOXL", "ZEC"])
            ALLOW_TRADFI = True
            assert resolve_universe(core, 24, 5.0) == core + ["HYPE", "XAU",
                                                              "SOXL", "ZEC"]
            ALLOW_TRADFI = False
            assert resolve_universe(core, 24, 5.0) == core + ["HYPE", "ZEC"], \
                "tradfi off must drop scout-added XAU/SOXL and keep crypto"
            # ...and it must NEVER drop a CONFIGURED coin, even a tradfi one:
            # the operator's list is the operator's decision.
            assert resolve_universe(["XAU", "BTC"], 24, 5.0)[:2] == ["XAU", "BTC"]
        finally:
            ALLOW_TRADFI = _at

        # --- THE ORPHAN RULE: a HELD coin is scanned no matter what ---
        # Without this, making the universe dynamic strands any position whose
        # coin leaves the list: exits are only evaluated for scanned coins, and
        # this book's only sweeper (_flatten_all) is `not dry_run`-gated, so the
        # SHADOW arm has none at all. The widening is not allowed to ship
        # without it.
        fleet_bus = _Bus([])
        assert scan_universe(["BTC"], ["DOGE"], 24, 5.0) == ["BTC", "DOGE"]
        assert scan_universe([], ["DOGE"], 24, 5.0) == ["DOGE"]
        # held coins APPEND — admission order for the core is unchanged
        assert scan_universe(core, ["DOGE"], 24, 5.0) == core + ["DOGE"]
        # an already-in-universe holding is not duplicated
        assert scan_universe(core, ["TRX"], 24, 5.0) == core
        assert scan_universe(core, ["trx"], 24, 5.0) == core, "case-folded"
        # and it survives every degraded bus, because that is when it matters
        fleet_bus = _Bus(RuntimeError("bus down"))
        assert scan_universe(core, ["DOGE"], 24, 5.0) == core + ["DOGE"]
        fleet_bus = None
        assert scan_universe(core, ["DOGE"], 0, 5.0) == core + ["DOGE"]
        assert scan_universe(core, [], 24, 5.0) == core
        assert scan_universe(core, None, 24, 5.0) == core
    finally:
        fleet_bus = _real
    print("lighter_trend_bot _selftest_universe OK")


def _selftest_exits():
    """[2026-07-30 (hk)] The EXIT PREDICATES. Mutation-proven gap: disabling all
    three production exits left the old `--selftest` green, because it covered
    only notional arithmetic. These pin the rules themselves.

    The book spent 20 days with zero closes and that was CORRECT — the signal
    never flipped. A test suite that cannot tell 'correctly holding' from
    'exit is broken' is what made that impossible to assert."""
    # golden() needs EMA_SLOW + 2 CLOSED bars, else None (insufficient history).
    assert golden([1.0] * (EMA_SLOW + 1)) is None, "short series must be None"
    assert golden([]) is None
    # A rising series is golden; a falling one is not. This is the entry gate
    # AND the exit gate — `not is_golden` on a held coin is the death cross.
    rising = [100.0 + i for i in range(EMA_SLOW * 2)]
    falling = [100.0 + (EMA_SLOW * 2 - i) for i in range(EMA_SLOW * 2)]
    g_up, g_dn = golden(rising), golden(falling)
    assert g_up and g_up[0] is True, g_up
    assert g_dn and g_dn[0] is False, g_dn
    assert g_up[1] > g_up[2], "golden means fast ABOVE slow"
    assert g_dn[1] < g_dn[2], "death cross means fast BELOW slow"

    # THE PRODUCTION predicates — imported, not re-implemented. A local copy
    # here is what let a disabled death cross pass this very test.
    _reason = exit_reason
    assert _reason(False, 0.10) == "death_cross", "death cross beats a winner"
    assert _reason(False, -0.99) == "death_cross", "death cross is checked FIRST"
    assert _reason(True, -CATASTROPHIC_STOP) == "catastrophic_stop", "boundary is inclusive"
    assert _reason(True, -CATASTROPHIC_STOP - 1e-9) == "catastrophic_stop"
    assert _reason(True, -CATASTROPHIC_STOP + 1e-9) is None, "just inside the stop holds"
    assert _reason(True, 0.0) is None and _reason(True, 5.0) is None
    # The seatbelt when candles fail (g is None): stop only, off a live price.
    _seatbelt = seatbelt_hit
    assert _seatbelt(65.0, 100.0) is True      # -35% == the stop
    assert _seatbelt(66.0, 100.0) is False
    assert _seatbelt(0.0, 100.0) is False and _seatbelt(65.0, 0.0) is False
    # A held coin must never be skipped by the supports() gate — the one-line
    # change that gave a delisted holding no exit, no stop and no seatbelt.
    _skip = skip_coin
    assert _skip(False, 0.0) is True, "flat + unsupported: skip, as before"
    assert _skip(False, 1.0) is False, "HELD + unsupported must NOT be skipped"
    assert _skip(True, 0.0) is False and _skip(True, 1.0) is False
    print("lighter_trend_bot _selftest_exits OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest_notional()
        _selftest_universe()
        _selftest_exits()
        sys.exit(0)
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
