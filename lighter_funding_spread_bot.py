#!/usr/bin/env python3
"""
lighter_funding_spread_bot.py — ⚖️ Counterweight (cross-sectional funding-spread
factor book, market-neutral, Lighter).

WHAT / WHY (2026-07-12)
  Born from the 12-Jul fleet strategy audit: the fleet is saturated with
  time-series signals on individual coins (two bots literally converged on the
  identical 20-candle-range entry), while NOTHING ranks coins against each
  other. Four cross-sectional factors were pushed through the validation
  doctrine (scripts/backtest_xsect_momentum.py + backtest_xsect_factor_lab.py):
  price momentum, short-term reversal and low-vol all REJECTED (isolated
  sweet spots, one regime carrying the return). FUNDING RANK passed with a
  real plateau: 8/12 configs green in BOTH halves, the whole 72h-lookback row
  green, mirrors negative everywhere, and it survives 3x modelled slippage.

  The book: every REBALANCE_H hours rank the universe by TRAILING MEAN hourly
  funding (LOOKBACK_H window). LONG the K most-NEGATIVE-funding coins (longs
  RECEIVE), SHORT the K most-POSITIVE (shorts RECEIVE) — funding income on
  both legs, ~zero net market exposure. Chosen config = the plateau centre,
  not the flashiest cell: 72h / K=5 / 24h rebalance ($20 clips -> $200 gross):
  full +13.7%, h1 +5.7%, h2 +8.9%, maxDD 11.9%, funding +6.8pp of it.

  Distinct from the live Funding Farmer (threshold-gated |APR|>=40% entries,
  directional, stops/TP, slope gate): Counterweight is ALWAYS-IN, balanced
  long/short by construction, and trades the rank, not the level. Kinship is
  the funding driver — book overlap vs the Farmer is published every loop
  (extra.ff_overlap) so the census can quantify how different it really is.

  UNVALIDATED LIVE. Shadow fills on the real book via ShadowBroker; funding
  accrued hourly from the venue's own funding map, exactly as the backtest.

  GO-LIVE [2026-07-31 (ia)] — PREPARED, NOT ARMED. v1 refused `lighter_live`
  outright; v2 has a live path that needs THREE independent conditions, and
  the default with no env set is still to exit:
    1. VENUE=lighter_live       — the deployment choice
    2. FUNDSPREAD_GOLIVE=1      — a deliberate second act, this bot only
    3. the PUBLISHED go-live gate says READY for this book
  (3) is what makes this preparation rather than a switch: the code cannot get
  ahead of the evidence even with both env vars set. FAIL-CLOSED — a dark or
  stale gate REFUSES, against this file's usual degrade-to-default habit,
  because here the cost of a wrong default is unsupervised real money.
  The live arm is PINNED to the validated config (K=5, $20/leg -> $200 gross)
  and takes NO capacity lever; see GOLIVE_K and `apply_tuning(live=True)`.
  Go-live remains an explicit operator act (see GO_LIVE_LIGHTER.md).

  STATUS at ship: 3/6 bars (window 13.0d, n=28, t=1.23), equity $984.61 —
  realised +$7.29 on 48 closes against -$22.68 OPEN on 24 legs. NOT READY, and
  the gate above is what enforces that.

RISK MODEL (why each gate exists)
  * No per-position stop — the BACKTESTED book has none (positions turn over
    at rebalance; adding unbacktested stops would violate replay fidelity).
    Risk is bounded by balance (long$ == short$), clip size, and the fleet
    daily-loss rail (restrict-only: rails may CUT, never widen).
  * Thin books: fills are the clip's real book VWAP (ShadowBroker crosses the
    spread); the 15bps/side stress case stays positive in both halves.
  * Warm boot: ranking needs LOOKBACK_H of funding history — backfilled from
    LIGHTER'S OWN SETTLED series (/api/v1/fundings), converted into the same
    per-period basis as the live funding_map() samples, and replaced by those
    samples as they accumulate. It used to backfill from HL's hourly
    fundingHistory, which put 8x-apart units in one window AND ranked a Lighter
    book on a foreign venue's cross-section (17-Jul; the venue was the real
    defect — see lighter_backfill()).
  * Fleet furniture: durable daily-loss halt (debounced), loop heartbeat,
    every fill ledgered to venue_orders, round-trips to paper_trades.

Usage:
    VENUE=lighter_shadow python lighter_funding_spread_bot.py          # daemon
    VENUE=lighter_shadow python lighter_funding_spread_bot.py --once   # smoke
"""
import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis
from venues import venue_context
from venues.symbol_map import to_lighter

# [2026-07-30] Growth rail + the shared scout read. Guarded like every
# optional organ — a dark import leaves the operator's env defaults and the
# configured coin list in force, never a crash inside a trading loop. Both
# COPYs land in Dockerfile.fundspread in this same commit (a guarded import
# with a missing COPY is the born-dark failure mode this fleet has shipped
# three times).
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "perps-funding-spread"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
# [2026-07-30 FULL UNIVERSE] `UNIVERSE_N` is how many of the venue's most
# liquid books the scout may add to the hand-list below. This book is a
# CROSS-SECTIONAL RANK — it longs the K most-negative and shorts the K
# most-positive funders — and a cross-sectional rank over 30 of the venue's
# 202 books (15%) is a weak version of itself. Widening the candidate set
# does not loosen the selection rule at all: it still takes exactly top-K
# and bottom-K, just from a real cross-section. Registry-bounded [20, 90];
# 0 disables the widening and restores the hand-list exactly.
# [2026-08-04 REVERTED 60 -> 30 with K (see the K note below).] The
# pre-registered criterion names the CROSS-SECTION as the culprit on this
# exact outcome — "the wider cross-section is worse than the hand list" —
# and both validations ranked the HAND LIST only (the (ia) re-run's header:
# "the faithful test of the live book, not a fresh universe" — the wide
# set pulled in non-crypto books whose funding dispersion is ~9x crypto's,
# so it changed which legs the book HELD, not just what it saw). Width 30 ==
# the 30-name configured list, so no scout book is added: the cage-safe
# equivalent of the 0 switch ([20,90] cannot hold 0 and audit_lever_bounds
# requires the default inside the cage).
UNIVERSE_N = int(os.environ.get("FUNDSPREAD_UNIVERSE_N", "30"))
# Minimum 24h $M turnover for a scout-added book. Kept well above dust: this
# book always holds BOTH sides, so an illiquid leg it cannot exit is a real
# cost, unlike the Farmer's single-sided carry.
UNIVERSE_MIN_VOL_M = float(os.environ.get("FUNDSPREAD_UNIVERSE_MIN_VOL_M", "1.0"))

COINS = os.environ.get(
    "FUNDSPREAD_COINS",
    "BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,ADA,LTC,DOT,NEAR,SUI,HYPE,AAVE,WIF,"
    "JUP,OP,ARB,TIA,ENA,SEI,APT,INJ,RUNE,STX,GALA,JTO,PYTH,W").split(",")
# [2026-07-30 SLOT-BOUND — 5 -> 8] Measured AT its structural cap: 10 open
# positions = exactly K=5 x 2 legs. Every rebalance it graded a full
# cross-section and could act on only the five extremes per side. K=8 with a
# widened universe keeps the same selectivity RATIO while deploying the book
# it already has. Registry-bounded [3, 12] (`fundspread.k`).
# [2026-08-04 REVERTED 8 -> 5 per the widening's OWN pre-registered criterion]
# SIX_BOOKS_BASELINE_2026-07-30.md item 2: "If n rises and t *falls*, the
# wider cross-section is worse than the hand list and the widening should be
# reverted." Measured 4-Aug: in-era t=-0.44 and falling (baseline t=0.65),
# mean -0.361%/trade, halves +6.19/-9.88, book -$16.01 MTM at 16 open —
# fleet-worst. K=5/$200 is the config BOTH validations actually cleared
# (the HL lab and the 31-Jul (ia) Lighter re-run: +13.7%, maxDD 9.6%); the
# K=8 / wide-universe book has NO backtest behind it. Operator decision
# 4-Aug (OPERATOR_QUEUE "Counterweight — early revert", option A) — this is
# the OPERATOR-DEFAULT route, not a hand-set lever: no fundspread.* lever
# was open on the bus (the (hs) ratchet lapsed), so the widening lived HERE.
K = int(os.environ.get("FUNDSPREAD_K", "5"))
LOOKBACK_H = int(os.environ.get("FUNDSPREAD_LOOKBACK_H", "72"))
REBALANCE_H = float(os.environ.get("FUNDSPREAD_REBALANCE_H", "24"))
ORDER_USD = float(os.environ.get("FUNDSPREAD_ORDER_USD", "20"))
DAILY_LOSS_LIMIT = float(os.environ.get("FUNDSPREAD_DAILY_LOSS", "0.05"))
LOOP_SECONDS = int(os.environ.get("FUNDSPREAD_LOOP_SECONDS", "300"))
SAMPLE_SECONDS = 3300           # ~hourly funding samples (one per venue period)
MIN_COVERAGE = LOOKBACK_H // 2  # doctrine: rank only with >=half-window history
# [2026-07-17 BASIS FIX] Lighter quotes an 8h rate — was annualised as hourly
# (8x). Logging-only here, but a log that lies is how the fleet believed the
# venue's floor was 28% apr for four days. See funding_basis.py.
H = funding_basis.periods_per_year('lighter')   # rate -> TRUE APR (logging)
LIGHTER_API = "https://mainnet.zklighter.elliot.ai"
# Hours per Lighter QUOTED funding period (24/3 == 8), asked of the basis
# authority rather than hardcoded. The SETTLED series is %/HOUR; the live
# funding_map() quote is a fraction per PERIOD. This is the factor that puts
# them in ONE basis — the whole point of the 17-Jul backfill swap.
HOURS_PER_PERIOD = 24.0 / funding_basis.periods_per_day('lighter')

LOG_FILE = os.environ.get("FUNDSPREAD_LOG_FILE", "lighter_funding_spread_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def lighter_market_ids():
    """{lighter symbol: market_id}. One call; {} on failure (caller degrades to
    no backfill, which is honest — the book simply cannot rank until it has
    sampled MIN_COVERAGE hours of real Lighter funding)."""
    try:
        with urllib.request.urlopen(
                LIGHTER_API + "/api/v1/orderBookDetails", timeout=20) as r:
            obs = json.loads(r.read()).get("order_book_details") or []
        return {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}
    except Exception as e:  # noqa: BLE001
        log.warning("lighter market list failed: %s", e)
        return {}


# [2026-07-30 AUTO-REVERT FIX] The operator's env defaults, snapshotted at
# IMPORT. apply_tuning() must hand THESE to get_lever, never the current
# global: get_lever returns its `default` when the lever is absent, expired
# or quarantined, so passing the already-moved value made the rail a ONE-WAY
# RATCHET — a widened lever could never revert, and auto-revert-on-expiry is
# the growth rail's central safety property ("levers EXPIRE back to defaults
# on their own, so auto-revert is the resting state"). Shipped broken in
# (fz); it was inert only because nothing authored the lane yet.
_ENV_DEFAULTS = {"K": K, "UNIVERSE_N": UNIVERSE_N}

# ---------------------------------------------------------------------------
# GO-LIVE [2026-07-31 (ia)]
# ---------------------------------------------------------------------------
#: THE VALIDATED CONFIG, and the live arm is PINNED to it regardless of levers.
#: The backtest that earned this book its existence is the plateau CENTRE:
#: 72h lookback / K=5 / 24h rebalance / $20 clips -> $200 gross (full +13.7%,
#: h1 +5.7%, h2 +8.9%, maxDD 11.9%, survives 3x modelled slippage). The SHADOW
#: arm has been running K=8-12 -> $320-480 gross, i.e. ABOVE what any evidence
#: covers — (hs) found the growth rail had ratcheted it to the cage ceiling on
#: a losing book. Real money starts at the number that was actually validated;
#: widening it live is a new decision needing new evidence.
GOLIVE_K = 5
GOLIVE_ORDER_USD = 20.0
#: The published verdict this bot trusts, and how stale it may be. 25h because
#: the grader publishes 6-hourly: four missed cycles is an outage, not a blip.
GOLIVE_KEY = "golive-readiness"
GOLIVE_MAX_AGE_S = float(os.environ.get("FUNDSPREAD_GOLIVE_MAX_AGE_S", "90000"))


def golive_blocker(bot, state=None, now=None):
    """-> None if this book may trade REAL money, else the reason it may not.

    FAIL-CLOSED: every uncertainty returns a refusal. A dark bus, a stale
    payload, a missing book, an unparseable verdict and an unset opt-in all
    read as "no". The only path to None is an explicit opt-in PLUS a fresh
    published verdict that says this book is READY.
    """
    if os.environ.get("FUNDSPREAD_GOLIVE", "").strip() != "1":
        return "FUNDSPREAD_GOLIVE is not set to 1 (deliberate second act)"
    try:
        if state is None:
            state = store.load_state(GOLIVE_KEY)
    except Exception as e:                       # noqa: BLE001
        return f"go-live gate unreadable ({e})"
    if not isinstance(state, dict) or not state:
        return f"go-live gate '{GOLIVE_KEY}' is dark"
    # freshness: the payload's own stamp, honoured the way fleet_bus does it
    stamp = state.get("updated") or state.get("updated_at")
    ts = _parse_iso(stamp)
    if ts is None:
        return f"go-live gate has no readable 'updated' stamp ({stamp!r})"
    age = (float(now if now is not None else time.time()) - ts)
    if age > GOLIVE_MAX_AGE_S:
        return f"go-live gate is STALE ({age / 3600.0:.1f}h old)"
    book = ((state.get("books") or {}).get(bot))
    if not isinstance(book, dict):
        return f"go-live gate has no entry for {bot}"
    if book.get("ready") is not True:
        bars = book.get("bars") or {}
        missing = sorted(k for k, v in bars.items() if v is not True)
        return (f"{bot} is NOT ready ({book.get('bars_passed')}/6 bars"
                + (f", failing {'+'.join(missing)}" if missing else "") + ")")
    return None


def _parse_iso(s):
    """Epoch seconds from an ISO stamp, or None. Never raises."""
    if not s:
        return None
    try:
        txt = str(s).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return None


def apply_tuning(live=False):
    """Growth-rail levers over the env defaults. Bounded by the fleet_tuning
    registry; expired/absent/quarantined levers leave the defaults intact.
    Returns {lever: value} of whatever actually moved.

    [2026-07-31 (ia)] THE LIVE ARM TAKES NO CAPACITY LEVER. `fundspread.k`
    sizes real exposure (gross = 2 * K * clip), and the growth rail is
    authored by the evidence board on SHADOW evidence — (hs) measured it
    ratcheting this very lever 5 -> 8 -> 12 (the cage ceiling) on a book at
    -$27.75. A lane that can do that must not reach real money. `universe_n`
    still applies live: it widens what the book can SEE, not what it holds,
    so it cannot change exposure.
    """
    global K, UNIVERSE_N
    if tuning is None:
        return {}
    moved = {}
    if live:
        K = GOLIVE_K                      # pinned, not merely defaulted
    for lever, attr in (("fundspread.k", "K"),
                        ("fundspread.universe_n", "UNIVERSE_N")):
        if live and attr == "K":
            continue                      # see the docstring: capacity is not
                                          # lever-controlled on real money
        cur = globals()[attr]
        try:
            val = tuning.get_lever(lever, _ENV_DEFAULTS[attr])
        except Exception:  # noqa: BLE001
            continue
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


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
    """The coin list this book ranks: the CONFIGURED names first (order
    preserved — they are the validated core), then the scout's most-liquid
    books until `width` is reached.

    Pure and offline-testable; the scout read is the caller's, injected as
    `_scout_syms` in tests. Contract, deliberately:
      * a dark or stale scout returns [] from the accessor, so this returns
        the configured list UNCHANGED — widening is an enhancement, never a
        dependency, and this book must not shrink because an organ is down;
      * `width <= 0` disables the widening entirely (the revert switch);
      * configured names are NEVER dropped, even when the scout ranks them
        below the cut — they are the backtested core and their exclusion
        would silently change what the book is.
    """
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


def lighter_backfill(market_id, hours):
    """Bootstrap the ranking window from LIGHTER'S OWN SETTLED funding series
    (/api/v1/fundings) — the venue this book actually trades and earns on.

    [2026-07-17] REPLACES an api.hyperliquid.xyz backfill. Two measured reasons,
    and note the second is the one that matters:
      * UNITS — HL quotes per 1h, Lighter per 8h, and BOTH landed in this one
        `fund_hist` list, so the rebalance averaged rows whose units differ 8x.
      * VENUE — rescaling the HL rows by 8 does NOT fix it. Measured: it makes
        the cold-start ranking WORSE (fidelity 7.88 -> 5.38 /10, control closer
        in 16/16 boots), because a raw HL row is ~8x SMALLER and acts as
        near-zero filler worth ~6% of the score; x8 re-weights a FOREIGN
        cross-section to a full THIRD of the ranking. The contaminant was the
        VENUE, not the scale. See scripts/study_fundspread_basis_mixing.py.
    Doctrine agrees (CLAUDE.md "BACKTEST ON LIGHTER ONLY"), audit_venue_purity
    flagged this file, and the factor is now validated on exactly THIS tape
    (scripts/backtest_xsect_funding_lighter.py: 72h row 4/4 green).

    UNITS, carefully. The settled row is
        {timestamp, rate PERCENT-PER-HOUR, direction long|short, value}
    — an UNSIGNED rate plus a direction (unlike /funding-rates, which IS signed).
    Returns [(epoch_s, rate_per_period)] in the SAME basis as funding_map()'s
    `rate`, so the merged window is unit-PURE and the persisted state (already
    in that basis) stays valid — no migration. VERIFIED against the live quote:
    median ratio 1.00 across the majors (ETH/DOGE/LTC exactly 1.00).
    """
    try:
        q = urllib.parse.urlencode({"market_id": market_id, "resolution": "1h",
                                    "start_timestamp": 0,
                                    "end_timestamp": int(time.time()),
                                    "count_back": 0})
        with urllib.request.urlopen(
                LIGHTER_API + "/api/v1/fundings?" + q, timeout=25) as r:
            rows = json.loads(r.read()).get("fundings") or []
        cut = time.time() - hours * 3600
        out = {}
        for f in rows or []:
            t = int(f["timestamp"])
            if t < cut:
                continue
            sign = 1.0 if f.get("direction") == "long" else -1.0
            hourly = float(f["rate"]) / 100.0          # %/hr -> fraction per hr
            out[(t // 3600) * 3600] = sign * hourly * HOURS_PER_PERIOD
        return sorted(out.items())
    except Exception as e:  # noqa: BLE001
        log.warning("lighter backfill market %s failed: %s", market_id, e)
        return []


def fresh_mid(ctx, coin):
    """Live book mid; None = unreadable (skip — never mark on a stale print)."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:  # noqa: BLE001
        return None
    bids = [p for p, s in (book or {}).get("bids") or [] if p > 0 and s > 0]
    asks = [p for p, s in (book or {}).get("asks") or [] if p > 0 and s > 0]
    if not bids or not asks:
        return None
    return (max(bids) + min(asks)) / 2.0


def _record_close(bot, coin, ent_px, ent_ts, exit_px, total_pnl, was_long,
                  reason, shadow):
    pnl_pct = None
    if ent_px:
        pnl_pct = ((exit_px - ent_px) / ent_px) if was_long \
            else ((ent_px - exit_px) / ent_px)
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=float(total_pnl),
            pnl_pct=pnl_pct, pair=coin, opened_at=oa,
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason=("long_" if was_long else "short_") + reason,
            # [2026-08-05 (kf)] the direction is already used to build `reason`
            # on the line above; stamping it as a first-class field means a
            # grader does not have to parse prose to know which way a LEG ran.
            side=("long" if was_long else "short"),
            # [2026-07-30 (gr)] EXIT TELEMETRY — computed above for pnl_pct,
            # then discarded. publish_paper_trade has accepted these since
            # 17-Jul, the DB column exists, the reader SELECTs them and
            # /trades.json exposes them: 8 of 9 bots never filled the pipe.
            # Without the prices no exit rule can be counterfactually
            # tested — the price PATH cannot be joined to the trade.
            # Telemetry only; no gate moves.
            entry_price=ent_px, exit_price=exit_px,
            venue="lighter", shadow=shadow)
    except Exception:  # noqa: BLE001
        pass


def main():
    p = argparse.ArgumentParser(
        description="Counterweight — cross-sectional funding-spread factor book")
    p.add_argument("--once", action="store_true", help="Single loop then exit.")
    args = p.parse_args()

    # [2026-07-16 AUDIT] a lost Railway VENUE var silently booted hl_paper
    # (unsuffixed row, HL data under a Lighter-named book). Lighter-shadow
    # is this bot's identity — default to it like the sniper does.
    os.environ.setdefault("VENUE", "lighter_shadow")
    ctx = venue_context(bot=BOT, default_hl_net="mainnet",
                        paper_start=START_EQUITY, live_flag=False)
    # [v2 GATE, 2026-07-31 (ia)] — operator: "prepare Counterweight to go live".
    # v1 refused `lighter_live` unconditionally. That is replaced by a live path
    # that is PREPARED but not ARMED, and which cannot be armed by accident.
    # DEFAULT BEHAVIOUR IS UNCHANGED: with no env set, this still exits.
    #
    # THREE INDEPENDENT CONDITIONS, all required, checked in this order:
    #   1. VENUE=lighter_live            — the operator's deployment choice
    #   2. FUNDSPREAD_GOLIVE=1           — a deliberate second act, this bot
    #                                      only; no shared switch can arm it
    #   3. the PUBLISHED go-live gate says READY for this book
    #
    # (3) IS THE POINT, and it is why this is preparation rather than a switch.
    # Measured 31-Jul, the day this shipped: ⚖️ Counterweight is 3/6 bars
    # (window 13.0d, n=28, t=1.23) with equity $984.61 — realised +$7.29 on 48
    # closes against -$22.68 of OPEN loss on 24 legs. Its realised maxDD reads
    # 0.2% against a 15% bar because it is ALWAYS-IN and its losses sit in
    # positions it has not closed. On trajectory it passes all six bars in late
    # August; (ia)'s MTM drawdown is what stops that being a green light on a
    # book below $1,000. Wiring the gate in HERE means the code cannot get
    # ahead of the evidence even if someone sets both env vars.
    #
    # FAIL-CLOSED, deliberately and against this file's usual habit: a dark
    # bus, a stale payload or an unreadable verdict REFUSES. Everywhere else in
    # this bot an organ outage degrades to the operator's configured behaviour,
    # because the cost is a missed shadow trade. Here the cost is unsupervised
    # real money, so absence of evidence must never read as permission.
    if ctx.mode == "lighter_live":
        _why = golive_blocker(BOT)
        if _why:
            raise SystemExit(f"perps-funding-spread REFUSES lighter_live: {_why}. "
                             "Run VENUE=lighter_shadow to keep building the "
                             "record; go-live stays an explicit operator act.")
        log.warning("LIVE ARMED — gate READY, FUNDSPREAD_GOLIVE=1. Trading REAL "
                    "money at the VALIDATED config (K=%d, $%.0f/leg).",
                    GOLIVE_K, GOLIVE_ORDER_USD)
    bot_id = ctx.bot_id
    broker = ctx.broker
    # [2026-07-31 (ia)] BOTH TERMS OF THE EXPOSURE ARE PINNED LIVE. Gross is
    # 2 * K * clip; pinning K alone would leave the clip free to reopen the
    # same hole from the other side.
    order_usd = ctx.order_usd(
        GOLIVE_ORDER_USD if ctx.mode == "lighter_live" else ORDER_USD,
        own=True)   # backtested $20/leg clip
    shadow_tag = ctx.mode == "lighter_shadow"

    # [2026-07-30] Levers first, THEN the universe — UNIVERSE_N is itself a
    # lever, so resolving the universe before applying them would use last
    # boot's width. The configured list is always kept; the scout only ever
    # ADDS, and a dark scout leaves this exactly as it was.
    global COINS
    _is_live = ctx.mode == "lighter_live"
    _moved = apply_tuning(live=_is_live)
    COINS = resolve_universe(COINS, UNIVERSE_N, UNIVERSE_MIN_VOL_M)
    COINS, _dead = prune_dead(COINS, ctx.supports)
    if _dead:
        log.warning("pruned %d symbol(s) the venue does not list: %s",
                    len(_dead), ", ".join(_dead))
    log.info("universe: %d coins (K=%d per side, width %d)%s",
             len(COINS), K, UNIVERSE_N,
             f" | levers {_moved}" if _moved else "")

    meta = {}            # coin -> {is_short, entry, opened_ts, accrued}
    fund_hist = {}       # coin -> [[epoch_s, hourly_rate], ...] (rolling window)
    fund_realized = 0.0
    next_reb = None
    # [2026-08-04 SEED GUARD] the CHECKED read — load_state() collapses "no
    # row" and "READ FAILED" into one None, and this restore is exactly the
    # seed-on-failed-read caller its docstring warns about: a Postgres blip at
    # boot would start a fresh book over this book's open legs' meta, and the
    # loop's save_state below would then overwrite the durable record with the
    # empty one. Degrade per the sniper's 17-Jul fix: bounded retry, then
    # REFUSE (crash-loop loudly; a blip clears, so the loop self-heals). No
    # DATABASE_URL keeps the old fresh-boot behavior — with no DB the write
    # path cannot overwrite anything either.
    _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
    if _saved:
        if broker is not None and broker.restore_state(_saved.get("broker") or {}):
            meta = {str(k): v for k, v in (_saved.get("meta") or {}).items()}
            log.info("restored shadow state: equity $%.2f, %d open",
                     broker.equity(), broker.open_count())
        fund_hist = {str(k): [list(x) for x in v]
                     for k, v in (_saved.get("fund_hist") or {}).items()}
        fund_realized = float(_saved.get("fund_realized") or 0.0)
        next_reb = _saved.get("next_reb")

    n_closed, n_wins = 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            n_closed, n_wins = agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    log.info("=" * 64)
    log.info("Counterweight (x-sect FUNDING-SPREAD book) | venue=%s | %d coins",
             ctx.mode, len(COINS))
    log.info("rank=%dh mean funding | LONG bottom-%d / SHORT top-%d | reb every "
             "%.0fh | $%.0f/leg (gross $%.0f) | no per-pos stop (as backtested) "
             "| daily rail %.0f%% | loop=%ds",
             LOOKBACK_H, K, K, REBALANCE_H, order_usd, 2 * K * order_usd,
             DAILY_LOSS_LIMIT * 100, LOOP_SECONDS)
    log.info("doctrine: scripts/backtest_xsect_factor_lab.py (72/5/24 plateau "
             "centre). lighter_live REFUSED in v1.")
    log.info("=" * 64)

    # ---- warm boot: make the ranking possible from loop one ----------------
    # [2026-07-17] Backfill is LIGHTER'S OWN settled series now, not HL's. A
    # coin Lighter does not list gets NO backfill (bf=[]) instead of 78 rows of
    # a foreign venue's funding — those coins are filtered by ctx.supports()
    # below anyway, so the window loses nothing it was entitled to.
    now_s = time.time()
    mids = lighter_market_ids()
    for coin in COINS:
        have = fund_hist.get(coin) or []
        cov = sum(1 for t, _ in have if t >= now_s - LOOKBACK_H * 3600)
        if cov < MIN_COVERAGE:
            sym, _ = to_lighter(coin)
            mid = mids.get(sym)
            bf = lighter_backfill(mid, LOOKBACK_H + 6) if mid is not None else []
            seen = {int(t) for t, _ in have}
            merged = have + [[t, r] for t, r in bf if t not in seen]
            merged.sort()
            fund_hist[coin] = merged[-(LOOKBACK_H + 24):]
    log.info("funding history ready: %d/%d coins with >=%dh coverage",
             sum(1 for c in COINS
                 if sum(1 for t, _ in fund_hist.get(c, [])
                        if t >= now_s - LOOKBACK_H * 3600) >= MIN_COVERAGE),
             len(COINS), MIN_COVERAGE)

    def account_value():
        open_accr = sum((meta.get(c) or {}).get("accrued", 0.0) for c in meta)
        return broker.equity() + fund_realized + open_accr

    cur_day = datetime.now(timezone.utc).date()
    halted_today = False
    if store.load_daily_halt(bot_id, cur_day.isoformat()):
        halted_today = True
        log.warning("daily-loss halt restored from state — halted for today.")
    day_start_equity = account_value()
    # [2026-07-16 AUDIT FIX] restore the accrual clock: it reset to
    # boot time on every redeploy, so funding during the gap was never
    # accrued (systematic undercount of the drag/credit this book
    # measures). Gap bounded to 48h so ancient state can't over-accrue.
    try:
        _lt = float((_saved or {}).get("last_ts") or 0)
    except Exception:  # noqa: BLE001 — incl. unbound saved-state
        _lt = 0.0
    last_ts = max(_lt, time.time() - 48 * 3600) if _lt else time.time()
    last_sample = 0.0

    def close_position(coin, reason, px=None):
        nonlocal fund_realized, n_closed, n_wins
        m = meta.get(coin) or {}
        px = px or fresh_mid(ctx, coin) or m.get("entry") or 0.0
        price_pnl = broker.close(coin, px)
        accr = m.get("accrued", 0.0)
        fund_realized += accr
        total = price_pnl + accr
        n_closed += 1
        n_wins += 1 if total > 0 else 0
        log.info("CLOSE %s %s $%+.3f (price %+.3f, funding %+.3f) [%s]",
                 coin, "short" if m.get("is_short") else "long", total,
                 price_pnl, accr, reason)
        _record_close(bot_id, coin, m.get("entry"), m.get("opened_ts"), px,
                      total, was_long=not m.get("is_short"), reason=reason,
                      shadow=shadow_tag)
        meta.pop(coin, None)

    while True:
        now = datetime.now(timezone.utc)
        t0 = time.time()
        store.heartbeat(bot_id)
        # [2026-07-30] Levers EVERY loop, not only at boot. `apply_tuning()`
        # was called once before this loop, so the board could author
        # `fundspread.k` and this container would never see it until a
        # redeploy — a lever that is registered, authored, graded and inert at
        # the consumer. K is read at each REBALANCE below, so refreshing here
        # is what makes the authored value reach a trade. (UNIVERSE_N stays a
        # boot-time decision: widening the universe mid-run would rank coins
        # whose funding history was never backfilled.)
        _lv = apply_tuning(live=_is_live)
        if _lv:
            log.info("levers applied %s (K=%d)", _lv, K)
        # [2026-08-05 (jr) S1] the allocation organ's capital scale, SHADOW
        # arm only and NEW entries only (rebalance legs open at the scaled
        # clip; held legs keep their entry size). The live arm's clip stays
        # PINNED at GOLIVE_ORDER_USD per (ia) — capital levers do not reach
        # real money, and the allocation organ doubly so. Dark bus -> 1.0.
        if not _is_live and fleet_bus is not None:
            _alloc = fleet_bus.allocation_scale(bot_id) or 1.0
            _target = ctx.order_usd(ORDER_USD, own=True) * _alloc
            if abs(_target - order_usd) > 1e-9:
                log.info("allocation scale %.2fx: clip %.2f -> %.2f",
                         _alloc, order_usd, _target)
                order_usd = _target
        if now.date() != cur_day:
            cur_day, halted_today = now.date(), False
            day_start_equity = account_value()

        equity = account_value()
        if (not halted_today and day_start_equity
                and equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)):
            _confirmed, equity = ctx.rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT, account_value)
            if _confirmed:
                log.warning("DAILY LOSS LIMIT HIT (%.2f <= %.2f). Flatten + halt.",
                            equity, day_start_equity)
                halted_today = True
                store.save_daily_halt(bot_id, cur_day.isoformat(), day_start_equity)
                for c in list(meta):
                    close_position(c, "rail_flatten")

        if halted_today:
            log.info("halted for today; sleeping.")
            try:
                store.publish(bot_id, status="halted", equity=account_value(),
                              pnl_abs=account_value() - START_EQUITY,
                              closed_trades=n_closed, wins=n_wins,
                              losses=n_closed - n_wins,
                              extra={"mode": ctx.mode, "venue": ctx.mode,
                       # [2026-07-30] effective cap — see funding_carry_bot
                       "caps": {"k": K, "legs": 2 * K,
                                "universe_n": UNIVERSE_N,
                                "universe": len(COINS)},
                                     "style": "xsect-funding-spread"})
            except Exception:  # noqa: BLE001
                pass
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        try:
            fund = ctx.venue.funding_map()
        except Exception as e:  # noqa: BLE001
            log.warning("funding fetch failed (%s); retry next loop.", e)
            if args.once:
                break
            time.sleep(LOOP_SECONDS)
            continue

        # ---- ~hourly funding sample into the rolling window ----------------
        if t0 - last_sample >= SAMPLE_SECONDS:
            last_sample = t0
            for coin in COINS:
                r = (fund.get(coin) or {}).get("rate")
                if r is not None:
                    hist = fund_hist.setdefault(coin, [])
                    hist.append([int(t0), float(r)])
                    cut = t0 - (LOOKBACK_H + 24) * 3600
                    fund_hist[coin] = [x for x in hist if x[0] >= cut]

        # ---- accrue funding + mark open positions --------------------------
        dt_h = (t0 - last_ts) / 3600.0
        last_ts = t0
        for coin, m in list(meta.items()):
            px = fresh_mid(ctx, coin)
            if px is None:
                log.warning("%s: no live book — mark/accrual skipped this loop", coin)
                continue
            broker.mark(coin, px)
            rate = (fund.get(coin) or {}).get("rate")
            if rate is not None:
                notional = abs(broker.szi().get(coin, 0.0)) * px
                # [2026-07-17 BASIS FIX ii] `rate` is per 8h — modelling it as
                # HOURLY over-accrued 8x. This book RECEIVES on both legs, so
                # the artifact FLATTERED the one number it exists to earn:
                # published +$0.86 was really -$0.04. Commit 31ec660 fixed the
                # four siblings and missed this site (it changed only `H`).
                m["accrued"] = m.get("accrued", 0.0) + \
                    (1.0 if m.get("is_short") else -1.0) \
                    * funding_basis.to_hourly(rate, "lighter") * notional * dt_h

        # ---- rebalance on schedule -----------------------------------------
        if next_reb is None:
            next_reb = t0            # first loop rebalances immediately
        if t0 >= next_reb:
            while next_reb <= t0:
                next_reb += REBALANCE_H * 3600
            floor = t0 - LOOKBACK_H * 3600
            scores = {}
            for coin in COINS:
                if not ctx.supports(coin):
                    continue
                rs = [r for t, r in fund_hist.get(coin, []) if t >= floor]
                if len(rs) >= MIN_COVERAGE:
                    scores[coin] = sum(rs) / len(rs)
            if len(scores) < 2 * K:
                log.warning("rebalance skipped: only %d/%d coins rankable",
                            len(scores), 2 * K)
            else:
                ranked = sorted(scores, key=scores.get)      # most negative first
                want = {c: False for c in ranked[:K]}        # LONG  (receive <0)
                want.update({c: True for c in ranked[-K:]})  # SHORT (receive >0)
                for c in list(meta):
                    if want.get(c) != meta[c].get("is_short"):
                        close_position(c, "rebalance")
                for c, is_short in want.items():
                    if c in meta:
                        continue
                    px = fresh_mid(ctx, c)
                    if px is None:
                        log.warning("%s: no live book — entry skipped", c)
                        continue
                    size = order_usd / px
                    broker.open(c, not is_short, size, px)
                    ent = broker.pos.get(c)
                    meta[c] = {"is_short": is_short,
                               "entry": (ent[1] if ent else px),
                               "opened_ts": t0, "accrued": 0.0}
                    log.info("OPEN %s %s $%.0f @ %.6g (%dh mean %+.1f%% apr)",
                             c, "SHORT" if is_short else "LONG", order_usd,
                             meta[c]["entry"], LOOKBACK_H, scores[c] * H * 100)
                lo = {c: f"{scores[c]*H*100:+.0f}%" for c in ranked[:K]}
                hi = {c: f"{scores[c]*H*100:+.0f}%" for c in ranked[-K:]}
                log.info("REBALANCE done | LONG %s | SHORT %s | next %s",
                         lo, hi, datetime.fromtimestamp(
                             next_reb, tz=timezone.utc).isoformat())

        # ---- census: overlap vs the live Funding Farmer's candidate rule ---
        # (|apr| >= 40% receiving side == what the Farmer would consider). This
        # quantifies how different this book REALLY is — cited at go-live.
        ff_overlap = 0
        for coin, m in meta.items():
            rate = (fund.get(coin) or {}).get("rate")
            if rate is not None and abs(rate) * H >= 0.40 and \
                    (rate > 0) == bool(m.get("is_short")):
                ff_overlap += 1

        # ---- publish + persist ----------------------------------------------
        open_accr = sum((meta.get(c) or {}).get("accrued", 0.0) for c in meta)
        try:
            store.publish(
                bot_id, status="online",
                equity=account_value(),
                pnl_abs=account_value() - START_EQUITY,
                open_trades=broker.open_count(),
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": ctx.mode, "venue": ctx.mode,
                       "style": "xsect-funding-spread",
                       # [2026-07-30 (gs)] `caps` on the ONLINE path. (gd) added
                       # it to this bot's `status="halted"` publish only — the
                       # SafetyRails branch — so the effective cap appeared
                       # exactly when the book had STOPPED trading and never
                       # while it ran. Measured: the row showed caps=None at
                       # 23:50 with the book online and full at 10/10. The
                       # evidence board prefers a published cap over the
                       # registry precisely to tell "at its cap" from "at the
                       # cap it set itself", so for this book it has been
                       # falling back to the registry since (gd) — the same
                       # blindness (go) fixed for three other books, in a
                       # fourth I had already counted as done.
                       "caps": {"k": K, "legs": 2 * K,
                                "universe_n": UNIVERSE_N,
                                "universe": len(COINS)},
                       "held": {c: ("S" if m.get("is_short") else "L")
                                for c, m in meta.items()},
                       "fund_realized": round(fund_realized, 4),
                       "fund_open": round(open_accr, 4),
                       "ff_overlap": f"{ff_overlap}/{len(meta)}" if meta else "0/0",
                       "next_reb": datetime.fromtimestamp(
                           next_reb, tz=timezone.utc).isoformat() if next_reb else None})
            # [2026-07-31 (hq)] MTM EQUITY SERIES — and this book is where the
            # realised-only drawdown bar is most blind, measured rather than
            # asserted. Its ledger is +$7.29 realised over 48 closes while the
            # published row reads -$27.47: a -$34.76 OPEN loss carried across
            # 24 legs. `golive_readiness` scores it mean +1.080%/trade, win
            # 67.9%, maxDD 0.2% — the drawdown bar is measuring almost nothing,
            # because this book HOLDS and rarely closes. (hl) proved the two
            # definitions can disagree about the VERDICT; here the gap is
            # already ~3.5% of the book against a 15% bar. Publish-only: the
            # grader is unchanged until there is history to read.
            store.snapshot_equity(bot_id, account_value(), broker.open_count())
        except Exception:  # noqa: BLE001
            pass
        try:
            store.save_state(bot_id, {"broker": broker.to_state(), "meta": meta,
                                      "fund_hist": fund_hist,
                                      "fund_realized": fund_realized,
                                      "next_reb": next_reb,
                                      "last_ts": last_ts})
        except Exception:  # noqa: BLE001
            pass

        log.info("loop ok | book %d/%d (%s) | eq $%.2f (funding %+.2f real "
                 "%+.2f open) | next reb %s",
                 broker.open_count(), 2 * K,
                 ", ".join(f"{c}:{'S' if m.get('is_short') else 'L'}"
                           for c, m in sorted(meta.items())) or "empty",
                 account_value(), fund_realized, open_accr,
                 datetime.fromtimestamp(next_reb, tz=timezone.utc).strftime("%d %H:%MZ")
                 if next_reb else "-")
        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _selftest():
    """Offline checks of the mid read + the ledger row shape. No network, no
    DB, no venue — the bot ran with ZERO tests until 2026-07-29 (coverage
    Finding 7); this is the fleet's minimum selftest parity."""
    class _Ctx:
        class venue:
            @staticmethod
            def orderbook(coin):
                # UNSORTED on purpose: fresh_mid must take max(bid)/min(ask),
                # never trust [0] as top-of-book
                return {"bids": [(99.0, 1.0), (101.0, 2.0), (0.0, 5.0)],
                        "asks": [(104.0, 1.0), (102.0, 3.0), (103.0, 0.0)]}
    assert fresh_mid(_Ctx(), "BTC") == (101.0 + 102.0) / 2.0

    class _Empty:
        class venue:
            @staticmethod
            def orderbook(coin):
                return {"bids": [], "asks": [(102.0, 1.0)]}
    assert fresh_mid(_Empty(), "BTC") is None    # one-sided book = unreadable

    class _Down:
        class venue:
            @staticmethod
            def orderbook(coin):
                raise RuntimeError("venue down")
    assert fresh_mid(_Down(), "BTC") is None     # never mark on a stale print

    # ledger row: the SHORT leg's pct must profit DOWN, and both legs carry
    # their side in the reason tag (the brain grades per side_lens)
    cap = {}
    _orig = store.publish_paper_trade
    store.publish_paper_trade = lambda bot, **kw: cap.update(bot=bot, **kw)
    try:
        _record_close("perps-funding-spread-lshadow", "ETH", 100.0,
                      1_700_000_000, 90.0, total_pnl=2.0, was_long=False,
                      reason="flip", shadow=True)
        assert cap["reason"] == "short_flip"
        assert abs(cap["pnl_pct"] - 0.10) < 1e-12     # short: (ent-exit)/ent
        assert cap["pnl_abs"] == 2.0                  # funding-inclusive total
        _record_close("b", "ETH", 100.0, 1, 110.0, 1.0, True, "tp", True)
        assert cap["reason"] == "long_tp"
        assert abs(cap["pnl_pct"] - 0.10) < 1e-12     # long: (exit-ent)/ent
        _record_close("b", "ETH", 0.0, 1, 110.0, 1.0, True, "tp", True)
        assert cap["pnl_pct"] is None                 # no entry px -> honest None

        def _boom(bot, **kw):
            raise RuntimeError("db down")
        store.publish_paper_trade = _boom
        _record_close("b", "ETH", 100.0, 1, 90.0, 1.0, False, "tp", True)
    finally:
        store.publish_paper_trade = _orig
    # [2026-07-30 FULL UNIVERSE] resolve_universe — the widening must ADD to
    # the validated core, never replace or reorder it, and must degrade to
    # the configured list on every failure of the scout.
    _cfg = ["BTC", "ETH"]
    _saved_bus = globals().get("fleet_bus")
    try:
        class _FakeBus:
            syms = ["SOL", "BTC", "DOGE"]      # BTC already configured -> dedup

            @staticmethod
            def scout_universe(min_vol_m=0.0, current_time=None):
                return _FakeBus.syms

        globals()["fleet_bus"] = _FakeBus
        assert resolve_universe(_cfg, 4, 1.0) == ["BTC", "ETH", "SOL", "DOGE"], \
            "configured names FIRST and in order; scout adds; duplicates dropped"
        assert resolve_universe(_cfg, 3, 1.0) == ["BTC", "ETH", "SOL"], \
            "width truncates the ADDED names"
        assert resolve_universe(_cfg, 2, 1.0) == ["BTC", "ETH"], \
            "a width at/below the core adds nothing and DROPS nothing"
        assert resolve_universe(_cfg, 0, 1.0) == ["BTC", "ETH"], \
            "width 0 = the revert switch, hand-list exactly"
        _FakeBus.syms = []
        assert resolve_universe(_cfg, 9, 1.0) == ["BTC", "ETH"], \
            "DARK/STALE scout -> configured list unchanged (never shrink)"

        class _RaisingBus:
            @staticmethod
            def scout_universe(min_vol_m=0.0, current_time=None):
                raise RuntimeError("bus down")

        globals()["fleet_bus"] = _RaisingBus
        assert resolve_universe(_cfg, 9, 1.0) == ["BTC", "ETH"], \
            "a RAISING bus is caught — the book keeps trading its core"
        globals()["fleet_bus"] = None
        assert resolve_universe(_cfg, 9, 1.0) == ["BTC", "ETH"], \
            "born-dark import -> configured list, no AttributeError"
    finally:
        globals()["fleet_bus"] = _saved_bus
    # ---- [2026-07-31 (ia)] THE GO-LIVE GATE ------------------------------
    # This is the only thing standing between a shadow book and real money, so
    # every refusal path is pinned. FAIL-CLOSED means: the ONLY input that
    # returns None is opt-in + fresh + ready.
    _saved_env = os.environ.get("FUNDSPREAD_GOLIVE")
    _now = 1_800_000_000.0
    _fresh = datetime.fromtimestamp(_now - 60, timezone.utc).isoformat()
    _stale = datetime.fromtimestamp(_now - 200_000, timezone.utc).isoformat()

    def _payload(ready, updated=None, bars=None):
        return {"updated": updated or _fresh,
                "books": {BOT: {"ready": ready, "bars_passed": 6 if ready else 3,
                                "bars": bars or {b: ready for b in
                                                 ("window", "closes", "mean",
                                                  "t", "halves", "maxdd")}}}}
    try:
        # 1. NO OPT-IN -> refuse, even with a perfect gate. The env var is a
        #    deliberate act and nothing else may substitute for it.
        os.environ.pop("FUNDSPREAD_GOLIVE", None)
        assert golive_blocker(BOT, _payload(True), _now), "no opt-in must refuse"
        for _v in ("", "0", "true", "yes", "on", "TRUE"):
            os.environ["FUNDSPREAD_GOLIVE"] = _v
            assert golive_blocker(BOT, _payload(True), _now), \
                f"FUNDSPREAD_GOLIVE={_v!r} must not arm the live path"
        # ...but WHITESPACE IS TOLERATED, and that is a decision, not an
        # accident: a Railway env var picking up a stray space would otherwise
        # refuse to arm with no visible reason, which is a footgun pointing the
        # other way. The value must still be "1" — no truthy synonyms above.
        os.environ["FUNDSPREAD_GOLIVE"] = " 1 "
        assert golive_blocker(BOT, _payload(True), _now) is None, \
            "a stray space must not silently block a deliberate go-live"
        os.environ["FUNDSPREAD_GOLIVE"] = "1"

        # 2. WITH opt-in, the GATE decides — and every uncertainty refuses.
        assert golive_blocker(BOT, _payload(True), _now) is None, \
            "opt-in + fresh + READY is the one path that arms"
        _not_ready = golive_blocker(BOT, _payload(False), _now)
        assert _not_ready and "NOT ready" in _not_ready, _not_ready
        # the refusal must NAME the failing bars — a detector that says "no"
        # without saying why sends the operator hunting ((ht)'s lesson)
        _bars = {"window": False, "closes": True, "mean": True, "t": False,
                 "halves": True, "maxdd": True}
        _msg = golive_blocker(BOT, _payload(False, bars=_bars), _now)
        assert "window" in _msg and "t" in _msg, _msg

        # FAIL-CLOSED on every flavour of missing evidence
        assert golive_blocker(BOT, {}, _now), "dark gate must refuse"
        assert golive_blocker(BOT, None, _now), "None gate must refuse"
        assert golive_blocker(BOT, {"books": {}}, _now), "no stamp must refuse"
        assert golive_blocker(BOT, _payload(True, updated="not-a-date"), _now), \
            "unparseable stamp must refuse, not pass"
        _st = golive_blocker(BOT, _payload(True, updated=_stale), _now)
        assert _st and "STALE" in _st, _st
        # a payload for a DIFFERENT book must never arm this one
        assert golive_blocker(BOT, {"updated": _fresh,
                                    "books": {"some-other-bot": {"ready": True}}},
                              _now), "another book's verdict is not ours"
        # 'ready' must be exactly True — a truthy string must not arm real money
        for _bad in ("yes", 1, "READY"):
            assert golive_blocker(BOT, {"updated": _fresh,
                                        "books": {BOT: {"ready": _bad}}}, _now), \
                f"ready={_bad!r} is not True and must refuse"
    finally:
        if _saved_env is None:
            os.environ.pop("FUNDSPREAD_GOLIVE", None)
        else:
            os.environ["FUNDSPREAD_GOLIVE"] = _saved_env

    # THE LIVE ARM TAKES NO CAPACITY LEVER, and both terms of the exposure are
    # pinned. (hs) measured the rail ratcheting `fundspread.k` 5 -> 8 -> 12 on
    # a book at -$27.75; that lane must not reach real money.
    assert GOLIVE_K == 5 and GOLIVE_ORDER_USD == 20.0, \
        "the live config must be the BACKTESTED plateau centre"
    import inspect as _ins
    _src = _ins.getsource(apply_tuning)
    assert 'if live and attr == "K"' in _src and "K = GOLIVE_K" in _src, \
        "apply_tuning must pin K live, not merely default it"
    _saved_k = K
    try:
        globals()["K"] = 99
        apply_tuning(live=True)
        assert K == GOLIVE_K, "live must PIN K back to the validated value"
    finally:
        globals()["K"] = _saved_k

    print("[counterweight] selftest OK (fresh-mid/one-sided/venue-down/"
          "ledger-row/universe-widening; go-live gate: opt-in, ready, "
          "freshness, fail-closed, live config pinned)")


def _supervised():
    """Unhandled exception -> log, mark row ERROR, restart in 60s (state
    re-hydrates). SystemExit/Ctrl-C pass through. (GO-GREEN furniture.)"""
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
    if "--selftest" in sys.argv:
        _selftest()
        raise SystemExit(0)
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
