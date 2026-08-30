#!/usr/bin/env python3
"""
lighter_ticket_taker.py — 🎫 Ticket Taker: the scanner's designated trader (SHADOW).

WHAT / WHY (2026-07-14, user ask: "when a scanner finds something incredible,
the bot designated to that particular find absorbs the scanner's findings and
makes a trade")
  Lighter Scout publishes per-strategy TICKETS (breakout / dip / momentum
  lenses over every liquid Lighter book). Until now nothing traded them —
  publish-first doctrine. This bot is the designated consumer: a $1,000
  SHADOW book that takes only the HIGH-CONVICTION subset of each lens (the
  "incredible" bars below), models fills at Lighter's own mark price via
  PaperBroker (fees included), accrues hourly funding drag from the venue's
  funding feed, and exits on TP / SL / max-hold.

  Every close is tagged long_<lens>_<exit> in the durable paper_trades
  ledger, so the LEARNING BRAIN grades each lens on real forward returns
  (bot_learn already ingests that ledger). That closes the loop the user
  asked for: scanner finds -> designated bot trades -> brain learns which
  lens actually has an edge -> only graded lenses ever graduate.

  UNVALIDATED BY DESIGN (like every new shadow book: Perp Sniper, Snap Back):
  the lens rules cannot be backtested — they need forward data, which is
  exactly what this book collects. Run-once process; run_all.sh loops it every
  5 min. Broker state + entry metadata persist in bot_state so redeploys
  continue the same equity curve.

  THE LIVE PATH EXISTS AND IS REFUSED (see main()). It is built so the switch
  is one env var WHEN the evidence lands — not a claim that it has.

Usage:
    python3 lighter_ticket_taker.py             # one management cycle
    python3 lighter_ticket_taker.py --selftest  # offline accounting checks
    python3 lighter_ticket_taker.py --selftest-live
                                     # drive the LIVE order path end-to-end
                                     # against a stub venue (no network, no
                                     # signer, no money) — see _selftest_live()
"""
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import bot_pnl_store as store
# [2026-08-20 (so)] the brain's sizing accessor. UNGUARDED, deliberately, and
# the Dockerfile gains the COPY in the same commit: every import in this file
# is unguarded on purpose (a missing module is a boot crash-loop, not a silent
# degrade), and `audit_image_imports.py` is what verifies the claim. Both
# images that carry this file — Dockerfile.tickettaker and Dockerfile.freqtrade
# — now COPY fleet_bus.py.
import fleet_bus
import funding_basis
from paper_broker import PaperBroker
# [2026-07-17] The fill read is SHARED with the live Funding Farmer now
# (venues/fills.py), not copied. The copy is what let the two drift: this bot
# stamped measured=True on any price the venue returned and had no fallback when
# the client id missed, where the Farmer derived measured from the venue's own
# label and fell back once. Two live bots disagreeing about what "measured"
# means is not a style problem — implementation_shortfall compares their rows.
from venues.fills import measured_from_reason, read_fill, slip_bps_of
# Module scope, same reason as venues.safety below: this bot keys everything by
# the venue-native symbol while LighterClient.positions() speaks FLEET symbols,
# and the conversion between them is a real-money rule (see _positions()). A
# lazy import inside the live branch is one the born-dark audit cannot see.
from venues.symbol_map import from_lighter, to_lighter


def _fleet(sym):
    """venue-native symbol -> FLEET symbol: the space LighterClient's API speaks.

    [2026-07-17] The client is fleet-symbol'd END TO END — positions() runs every
    symbol through from_lighter(), and market_close() looks the coin up IN THAT
    DICT (venues/lighter_client.py:558). Its _resolve() happens to tolerate a
    native symbol (to_lighter is identity for "1000BONK"), which is exactly what
    makes this dangerous: market_OPEN accepts native and works, while
    market_CLOSE accepts native, misses the lookup, and returns None WITHOUT
    RAISING. Open succeeds, close silently no-ops, and the position is stranded.
    So: convert at EVERY venue call, not just the ones that fail loudly.
    """
    return from_lighter(sym)[0]
# The notional-cap rule lives on the rail that enforces it. Imported at module
# scope on purpose (not lazily inside the live branch): the born-dark guard
# reads static imports, and a money rule that only materialises on the live
# path is a money rule the image audit cannot see. venues/safety.py is
# dependency-free — no SDK, no network — so this costs the shadow arm nothing.
from venues.safety import capital_adjusted_day_start, open_notional

# [2026-07-17 LIVE PATH] The taker was PAPER-ONLY BY CONSTRUCTION: PaperBroker
# modelling its own fills at a flat 4bps, a hardcoded -lshadow row, and no
# venue client, signer, order path or SafetyRails anywhere. Setting
# VENUE=lighter_live on the service would NOT have placed one order — it would
# have published paper P&L into a real-money row, which looks like it works.
# That is the failure this wiring removes.
#
# Modes (TT_VENUE, default lighter_shadow — the fleet's fail-safe default):
#   lighter_paper  the legacy book: PaperBroker, modelled fills, flat fee.
#                  KEPT so the existing -lshadow equity curve stays continuous
#                  and comparable; it is a MODEL, not execution.
#   lighter_shadow ShadowBroker: fills WALK THE REAL LIGHTER BOOK (crossing the
#                  spread at our clip) and every order lands in venue_orders
#                  with decision-vs-fill slippage. This is the arm that earns a
#                  go-live, because it is the only one measuring real execution.
#   lighter_live   REFUSED — see the guard in main(). Divergence is the only
#                  lens with forward evidence and it has n=7 (~2 fills of
#                  swing) against a 30-day gate. The path exists so the switch
#                  is one env var WHEN the evidence lands; it is not a promise
#                  that it has.
#
# [2026-07-17] TT_VENUE KEEPS its default, deliberately — unlike $VENUE on the
# two real-money bots, which f44e3eb just made MANDATORY ("a default is fine
# for a preference, never for an IDENTITY that decides whether real money
# moves"). The rule is the same; the exposure is not. This bot has no service
# of its own: run_all.sh loops it inside the shared freqtrade-bots container
# with no env, so a mandatory var would simply kill the shadow arm that is
# collecting the only evidence a go-live could rest on. And an unset var CANNOT
# produce a live taker — live requires the literal string "lighter_live", which
# is explicit by construction, so the lost-var case fails SAFE here rather than
# silently-live.
# GO-LIVE PRECONDITION (write it down now, while it is cheap): the live arm
# must be its OWN Railway service with TT_VENUE set explicitly.
# [2026-07-17 DONE — that service exists: Dockerfile.tickettaker +
# railway.tickettaker.toml, and the mandatory guard is now in main(). The module
# default below is what run_all.sh's shadow arm no longer relies on: it DECLARES
# TT_VENUE=lighter_shadow on the command line, because with the guard in place
# an unset var is a refusal, not a fallback. Keep the default only so the four
# modules that import this file (replay/tuner/incubator/proprioception) can read
# the bars without an env.]
TT_VENUE = os.environ.get("TT_VENUE", "lighter_shadow").strip() or "lighter_shadow"
TT_MODES = ("lighter_paper", "lighter_shadow", "lighter_live")

try:
    import fleet_tuning as tuning     # growth rail (optional import)
except Exception:  # noqa: BLE001
    tuning = None

# [2026-07-17] the row follows the MODE — a live arm must never publish into
# the shadow arm's curve (and vice versa). paper/shadow share -lshadow on
# purpose: same book, better fill model, one continuous curve.
BOT = "lighter-ticket-taker"
_ROW_SUFFIX = {"lighter_paper": "-lshadow", "lighter_shadow": "-lshadow",
               "lighter_live": "-lighter"}
BOT_ROW = BOT + _ROW_SUFFIX.get(TT_VENUE, "-lshadow")


def _standby_key(bot_row):
    """[2026-08-04] The bot_state key a STOOD-DOWN process reports on —
    funding_carry_bot's (ic) pattern, applied to the real-money pair.

    Deliberately NOT the book's `bot_pnl` row and NOT a `bot_pnl` row at all:
    the loser of the writer claim must not touch the row it does not own.
    (ib)/(ic) measured the naive version inverted — the standby loop WON the
    row 10 of 12 samples, and a loser's `heartbeat` keeps a DEAD incumbent's
    row reading fresh over a frozen snapshot (I1). Suffix, never a rewrite:
    derivable from the row it shadows, so a reader holding the book id can
    always find its standby record.
    """
    return f"{bot_row}:standby"


STATE_KEY = "lighter-ticket-taker"
# [2026-07-17 LIVE PATH] The live arm keeps its OWN state key. STATE_KEY holds
# a PaperBroker/ShadowBroker snapshot (a local account); a live arm restoring
# that would inherit the shadow book's equity curve and open positions as if
# they were its own. Live persists only what a live arm can legitimately
# remember: the P&L baseline and per-position meta (the max-hold clock, entry
# clip and lens) — the ACCOUNT itself lives on the venue. Mirrors
# lighter_funding_bot's `bot_id + ":live"`.
LIVE_STATE_KEY = STATE_KEY + ":live"
SCOUT_KEY = "lighter-market"
API_BASE = os.environ.get("LIGHTER_API_BASE", "https://mainnet.zklighter.elliot.ai")

START_EQUITY = 1000.0
# [2026-07-21 D1] CAPITAL IS NOT P&L. The EquityGuard records the deposits/
# withdrawals it accepts (pop_capital_moves); they accumulate in the persisted
# LIVE_STATE_KEY blob, and this env knob backfills moves that predate the
# mechanism. Default = this book's 18-Jul deposit as measured in the
# fleet-equity series (+$32.22 @ 07:37Z — review 2026-07-21 N1; printed as
# profit until this fix). Override with the exact figure if known; set to 0
# if initial_equity is ever re-baselined by hand.
CAPITAL_ADJUST_USD = float(os.environ.get("CAPITAL_ADJUST_USD", "32.22"))
CLIP_USD = float(os.environ.get("TT_CLIP_USD", "50"))   # fallback when no vol data
# [2026-08-27 (vn)] 6 -> 8, Eamon: *"take it to 8"*, and it CLEARED THE REPLAY
# rather than bypassing it. `slot_census` (uo) had shown `{offered: 4,
# slots_full: 4, lens_once: 0}` — four tickets a loop refused purely on the
# position cap, with the per-lens throttle NOT binding — but that was n=1 cycle.
# Driven through `lighter_ticket_replay` over the same 2,388-snapshot bus tape
# (19-27 Aug), the taker's REAL code, both arms identical but for this number:
#     6 slots -> 75 closes, net +$1.85, $0.025/trade
#     8 slots -> 99 closes, net +$6.76, $0.068/trade
# +32% throughput AND a better mean, so this is not denominator shrinkage
# ((hl)'s 25-of-30 failure mode) — it is the slot cap having been the binding
# constraint, as the census said. DECLARED LIMIT: the replay cannot resolve the
# up-regime without a candle fetch, so `breakoutup` (39% of the live book's
# closes) is absent from BOTH arms — the comparison is apples-to-apples, the
# LEVEL is not the book's. Capacity, so the era clock does not reset ((hc)).
MAX_OPEN = int(os.environ.get("TT_MAX_OPEN", "8"))
# [2026-07-14c CONSTANT-RISK SIZING] Fixed $ clips carry wildly different risk
# across books (a $50 clip in a 10%-range alt is ~5x the risk of $50 in BTC).
# Size so every position risks ~the same dollars: expected adverse move ~ half
# the daily range, clip = RISK_USD / adverse, bounded. The brain still grades
# per-lens on pnl_pct (per-clip), so sizing doesn't distort lens grading.
# [2026-08-25 (td)] RISK_USD 1.5 -> 3.0 and CLIP_MAX 80 -> 95 — the weekly
# review's #1 win-more item, executed under Eamon's "bigger bets" directive.
# The evidence (I19), all on this book's OWN ledger: era long-breakoutup
# +1.99%/trade t=2.52 (the brain's ONLY expand, 1.25x); the (qd)
# pre-registered exit:hold follow-through CONFIRMING at n=10 +5.86%/t t=3.38;
# the allocation organ's era claim licenses 4.0x (target $6,208 vs $1,000)
# with NO consumer — while the book deployed a median $21 clip, ~16% of its
# own equity, at 6/6 slots. The step is 2x on the risk budget, not the 4x
# the claim licenses, per (sv): one notch generates the sample that grades
# the next. Expectancy price: ZERO — sizing is %-invariant, entries
# unchanged, capacity per (hc) so the era clock does not reset. Drawdown
# arithmetic at the new caps: all-slots-stop 6 x $95 x 3% = $17.10 = 1.6%
# of the book (15% bar); worst-case gross 6 x $95 = $570 = 0.54x equity —
# unlevered, and see CLIP_MAX below for why 95 and not more.
RISK_USD = float(os.environ.get("TT_RISK_USD", "3.0"))
CLIP_MIN = float(os.environ.get("TT_CLIP_MIN", "20"))
# CLIP_MAX is DERIVED from the fleet's own funding bar, not picked: the
# sizing-safety guard (test_brain_live_sizing_safety) requires worst-case
# gross — CLIP_MAX x BRAIN_GROSS_X (2.0) x MAX_OPEN — to stay inside
# 1.2x the book's $1,000 capital, because fill/slippage terms calibrated at
# the designed clip become fiction above what the book could fund. A first
# draft shipped 160 and the guard correctly refused it.
# [2026-08-27 (vn)] 95 -> 70, and THE PAIRING IS MANDATORY, not a second
# opinion: at MAX_OPEN 8 the old ceiling gives 95 x 2 x 8 = $1,520 and the
# guard reddens. 70 x 2 x 8 = $1,120, strictly inside $1,200 — the same
# "strictly inside" the 95 was chosen for at 6 slots (75 would sit exactly ON
# the bar). It reads as undoing (td)'s 80 -> 95 and mostly is not: the book's
# MEDIAN DEPLOYED CLIP is ~$21, so a $70 ceiling binds on almost nothing,
# while the extra two slots are worth +32% of closes on the replay. Trading
# the tail of one trade's size for a third more trades is the right side of
# that swap on a book whose binding go-live bar is `t`, which grows with
# sqrt(n) at fixed edge.
CLIP_MAX = float(os.environ.get("TT_CLIP_MAX", "70"))
TAKE_PROFIT = float(os.environ.get("TT_TP", "0.04"))       # +4%
STOP_LOSS = float(os.environ.get("TT_SL", "-0.03"))        # -3%
MAX_HOLD_H = float(os.environ.get("TT_MAX_HOLD_H", "48"))
# [2026-07-24 TREND EXIT — the breakout arm's missing exit, SHIPPED DISABLED]
# The bull-engine research landed here: long-breakout in a per-asset up-regime is
# a REAL crypto-native continuation edge (beats a LOSING up-regime baseline by
# +0.75-1.5%/trade, both-halves-positive, 54 effective bets, ex-memecoin robust)
# — but the fixed TP+4%/SL-3% ladder CHURNS it to zero: the median breakout trade
# exits at the -3% stop itself, because the entries routinely draw -3.4% before
# they run. A TREND entry needs a TREND exit, not a reversion bracket (the
# infinity-grid insight, now measured): let it run, trail off the peak, bank
# before the ~1-week reversion. `TT_TRAIL_PCT`>0 enables a trailing-from-peak
# exit (the caller supplies peak_ret); with it OFF (default 0) exit_reason is
# byte-for-byte the old fixed bracket for every existing caller.
# CAPTURABILITY IS UNPROVEN, BY CONSTRUCTION: the daily-tape edge is delay-0 ONLY
# (a one-bar entry delay flips it negative) and this taker fills INTRADAY, inside
# that danger zone — so whether THIS async taker can actually capture the pop is
# unknown, and ONLY a SHADOW run with the taker's real fill timing can settle it.
# This is a SHADOW-only capturability TEST. It never touches real money.
TRAIL_PCT = float(os.environ.get("TT_TRAIL_PCT", "0"))
# [2026-07-16 ZOMBIE GUARD] a delisted/vanished book used to mean "hold
# forever" (exit_reason needs a mark, so even max-hold was unreachable) —
# the position froze at its last mark and ate a MAX_OPEN slot for good.
# After this many hours continuously unpriceable, close at the last known
# mark (entry if none was ever seen) — the sniper's 2-Jul give-up, ported.
DELIST_GIVEUP_H = float(os.environ.get("TT_DELIST_GIVEUP_H", "6"))

# "Incredible" — the conviction bars. A ticket must clear its lens's bar to
# be taken; ordinary tickets stay advisory for the weekly lens grading.
BRK_RANGE = float(os.environ.get("TT_BRK_RANGE", "0.95"))  # at the daily high
BRK_VOL_M = float(os.environ.get("TT_BRK_VOL_M", "1.0"))   # >= $1M/day
DIP_RANGE = float(os.environ.get("TT_DIP_RANGE", "0.05"))  # pinned to the low
MOMO_CHG = float(os.environ.get("TT_MOMO_CHG", "5.0"))     # >= +5% day
# [2026-07-21] hours a symbol stays entry-blocked after ITS OWN stop-loss
# close (0 disables). Measured basis: same-minute SL->re-enter churn, every
# instance a loser (NBIS -$5.37/8, BOT -$4.60/3 on the 17-20 Jul tape).
SL_COOLDOWN_H = float(os.environ.get("TT_SL_COOLDOWN_H", "2.0"))


def _sl_active(until_iso, t_now):
    """True while a post-stop cooldown stamp is still in the future. Junk
    stamps read as inactive (fail-open — a corrupt stamp must not embargo a
    symbol forever). Pure; selftested."""
    try:
        return parse_ts(until_iso) > t_now
    except (ValueError, TypeError):
        return False
MOMO_VOL_M = float(os.environ.get("TT_MOMO_VOL_M", "2.0")) # >= $2M/day
# [2026-07-14b] Divergence lens: receive Lighter's funding when it diverges
# this hard (percentage points of APR) from the cross-venue median.
# [2026-07-17] /8 with the fleet basis fix — same decision, true units.
DIV_GAP_PP = float(os.environ.get("TT_DIV_GAP", "62.5"))
# [2026-07-22 COIN-QUALITY VETO — the third "kill switch that never reached the
# consumer"] market_context publishes bot_state 'coin-vetoes'. TWO bars, not one
# (market_context.py:396-399): measured |slip| > 15bps over >=5 orders in 14d,
# **OR** stop-rate >= 50% over >=5 closes in 30d — pooled FLEET-WIDE across every
# bot, so a coin can arrive here on another book's stop-outs with clean slippage
# of its own (ADA today: stop-rate veto, 3.65bps slip). Do not describe this set
# as "slippage" anywhere the operator reads it. It was the fleet's
# one automated restrict-only actuator, and until now its ONLY consumer was
# lighter_funding_bot.py:1033 — the taker never read it.
# WHAT THAT COST, measured 22-Jul: BOT/USDC carries **747.6 bps** mean absolute
# slippage over 93 taker orders (81.9bps spread); the next-worst book it trades
# is SOXL at 20.9. On 22-Jul the taker put 44 of its 52 closes through BOT, and
# the short-divergence lens' realised mean went to -0.695%/trade — while the
# BRAIN still grades the divergence SIGNAL positive (ehit4h 0.536 [0.516,0.557],
# n=10522) because it grades tickets counterfactually, not slipped fills.
# The lens never decayed. One un-vetoed book was eating it.
# Contract mirrors the Farmer's verbatim: RESTRICT-ONLY, fail-OPEN on a missing
# or STALE payload (a fossil veto set is not evidence), kill switch below.
QUALITY_VETO = os.environ.get("TT_QUALITY_VETO", "on").strip().lower() \
    not in ("0", "off", "false", "no")
QUALITY_VETO_TTL_S = float(os.environ.get("TT_VETO_TTL_S", "3600"))
# [2026-07-21 DIAGNOSIS; corrected same day] divergence has no liquidity
# check (breakout >= $1M, momentum >= $2M; dip has none either — the
# original "ONLY bar without one" claim was wrong) while being the only
# lens LIVE money fills — 79% of bar-clearing divergence tickets sat on
# books under $1M/day. SHIPPED DISABLED (0 = off), and the
# fill-ledger counterfactual (scripts/study_div_vol_floor.py, 37 shadow +
# 5 live closes, volumes matched at open time 42/42) REJECTS every tested
# floor {0.25, 0.5, 1.0, 2.0}: none improves both halves — the seductive
# full-window winner (1.0: +$10.32 vs +$2.21) is a pure second-half effect,
# and thin-print P&L flips sign between halves, so volume is not a stable
# loss predictor on this tape. The knob exists for the day the evidence
# supports it (re-test at ~n>=60 per the script header); until then 0.
DIV_VOL_M = float(os.environ.get("TT_DIV_VOL_M", "0"))
# [2026-07-23 SPREAD GATE — the proactive execution-cost guard, SHIPPED DISABLED]
# The 23-Jul taker root-cause landed here: the divergence SIGNAL is intact (the
# brain grades it forward-positive at n>11k) but realised P&L is eaten by
# EXECUTION on wide-QUOTE books. Measured (n=99 divergence closes + 179 taker
# fills carrying a recorded spread_bps): the quoted spread AT DECISION predicts
# realised slippage (pearson r=+0.44, and it HOLDS ex-BOT at r=+0.42: BOT quote
# 74bps -> 747 slip, STRC 98 -> 46, SOXL 24 -> 78), and a per-entry gate at
# spread <= ~20bps is the ONLY gate (spread OR volume) that improves BOTH halves
# ex-BOT while excluding ONLY losers (ex-BOT +$14.15 vs +$8.96 baseline, t=+1.30).
# It catches a wide-quote FRESH listing on its FIRST fill — the exact class the
# reactive coin-quality veto (needs >=5 orders/14d) is structurally blind to.
# The VOLUME floor (DIV_VOL_M) was RE-REJECTED at this n: its apparent win was a
# BOT mark-pathology artifact and it fails both-halves ex-BOT. Evidence table:
# scripts/study_taker_spread_gate.py.
#
# SHIPPED DISABLED (0 = off). Three reasons it is dormant, not on: the edge it
# protects is not yet significant (t=1.30 < 2), enabling changes REAL-MONEY
# entries (operator-only), and the LIVE arm records no spread yet. Staged
# rollout on ONE knob: 0 = fully dormant (no book fetch); a HIGH value (e.g.
# 9999) = RECORD-ONLY (fetch + log the spread on live fills to validate the gate
# on the live arm's own tape, blocking nothing); a moderate value (e.g. 20) =
# ACTIVE gate. Fail-OPEN — a missing/empty book NEVER blocks (same contract as
# the coin-quality veto; the delisted-book case is owned by other guards).
# RESTRICT-ONLY: an over-wide spread can only SKIP an entry, never force one.
# [2026-07-31 (hr)] DEFAULT 0 -> 20. The LIVE service sets this explicitly; the
# SHADOW service carries only TT_BULL_MODE, so the gate defaulted OFF on the arm
# whose entire job is to GRADE this book. The two arms were therefore trading
# different populations, and the shadow arm was admitting books the money arm
# would never touch — which is not a conservative difference, it is a grading
# error in the permissive direction.
# MEASURED (hm): at 20bps this would have refused 43 of 46 BOT/USDC entries
# (93%) — the churn chain that poisoned 45 of 98 short-divergence rows and
# produced the "39 take-profits that booked a loss" defect. A 747bps gap
# between the mark and the book top is not a tradable spread on any arm.
# Setting the DEFAULT (rather than the live env) changes nothing on real money:
# an explicit env var always wins, and the live arm has one.
SPREAD_GATE_BPS = float(os.environ.get("TT_SPREAD_GATE_BPS", "20"))
# [2026-07-14b] Stress veto: when the venue-wide |premium| median is at or
# above this (bps), the whole venue is dislocated — take NO new entries this
# cycle (exits keep running). Normal tape prints ~6bps median.
STRESS_VETO_BPS = float(os.environ.get("TT_STRESS_VETO_BPS", "15"))
# [2026-07-17 LIVE PATH] Per-bot daily-loss rail, as a FRACTION of the day's
# starting equity — the strategy-side rail every funded bot carries on top of
# SafetyRails' absolute fleet rail (LIGHTER_MAX_DAILY_LOSS). Either one firing
# flattens the book and halts for the rest of the UTC day. Live-only.
DAILY_LOSS_LIMIT = float(os.environ.get("TT_DAILY_LOSS_LIMIT", "0.05"))


# [2026-07-15 GROWTH RAIL] The tuner (lighter_scout_tuner.py) may move the
# conviction bars / exit ladder within fleet_tuning's hard bounds — but ONLY
# after the change beat/matched baseline on BOTH halves of the recorded tape
# through this module's own decision code. Levers expire on their own; the
# env defaults above stay authoritative whenever no live lever exists.
TUNABLE = (("taker.dip_range", "DIP_RANGE"),
           ("taker.brk_range", "BRK_RANGE"),
           ("taker.momo_chg", "MOMO_CHG"),
           ("taker.div_gap_pp", "DIV_GAP_PP"),
           ("taker.tp", "TAKE_PROFIT"),
           ("taker.sl", "STOP_LOSS"),
           ("taker.max_hold_h", "MAX_HOLD_H"),
           # [2026-07-21] the post-stop cooldown joins the growth rail: the
           # stamp at close reads the module attr, so a lever overlay moves
           # future stamps (never an already-written sl_block entry).
           ("taker.sl_cooldown_h", "SL_COOLDOWN_H"),
           # [2026-08-20 (sk)] the breakout arm's TREND exit — see the registry
           # note. `bull_exit()` reads these as module globals, so the overlay
           # reaches the routing through the same single owner main() uses,
           # exactly as the reversion bracket above does. Defined further down
           # the file than TUNABLE; harmless, because apply_tuning resolves
           # through globals() at CALL time, and the selftest pins that.
           ("taker.brk_trail", "BRK_TRAIL"),
           ("taker.brk_sl", "BRK_SL"))


def apply_tuning():
    """Overlay live growth-rail levers onto the module bars. Returns what
    moved (for the log). Defaults untouched when no lever is live.

    [2026-07-17 NOT ON REAL MONEY] The `taker.*` levers live in the
    `lighter-taker` lane — fleet_tuning.py documents it as "the $1k SHADOW
    book's bars", its author is `scout-tuner` (which has NO live authority and
    is gated by a replay over SHADOW tape), and it sits in ENACT_LANES by
    default. Taking this bot live would silently promote a shadow lane into a
    real-money lane: a shadow-replay-gated author would be steering real clips,
    which is exactly what `_LIVE_PREFIX_OWNERS` exists to prevent. Fleet
    doctrine is that ONLY `live.*` levers may steer real money, and only their
    bound author may write them. So live runs the OPERATOR's env bars, full
    stop. If the live clip should ever be tunable it goes through the existing
    board-owned `live.clip_scale` (bounded, TTL'd, and already reverted at the
    consumer when proprioception grades it hurting) — not through this door.
    """
    if TT_VENUE == "lighter_live":
        return {}
    if tuning is None:
        return {}
    moved = {}
    for lever, attr in TUNABLE:
        cur = globals()[attr]
        val = tuning.get_lever(lever, cur)
        if val != cur:
            globals()[attr] = val
            moved[lever] = val
    return moved


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _get(path):
    req = urllib.request.Request(API_BASE + path,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_marks_and_funding():
    """{sym: mark}, {sym: hourly_rate}, {sym: day_range_pct} — keyless API."""
    obd = _get("/api/v1/orderBookDetails")
    marks, ranges = {}, {}
    for b in obd.get("order_book_details") or []:
        try:
            if b.get("status") == "active" and float(b.get("mark_price") or 0) > 0:
                sym = b["symbol"]
                marks[sym] = float(b["mark_price"])
                hi = float(b.get("daily_price_high") or 0.0)
                lo = float(b.get("daily_price_low") or 0.0)
                if hi > lo > 0:
                    ranges[sym] = 100.0 * (hi - lo) / marks[sym]
        except (TypeError, ValueError):
            continue
    fr = _get("/api/v1/funding-rates")
    funding = {}
    for r in fr.get("funding_rates") or []:
        try:
            if r.get("exchange") == "lighter" and r.get("rate") is not None:
                funding[r["symbol"]] = float(r["rate"])
        except (TypeError, ValueError):
            continue
    return marks, funding, ranges


# ---------------------------------------------------------------------------
# PURE DECISION LOGIC (unit-tested offline)
# ---------------------------------------------------------------------------

def vol_clip(day_range_pct, risk_usd=None, clip_max=None):
    """Constant-risk clip: RISK_USD / expected adverse move (~half the daily
    range, floored at 0.5%), bounded [CLIP_MIN, CLIP_MAX]. Falls back to
    CLIP_USD when the book has no range data.

    [2026-08-20 (sp)] `risk_usd`/`clip_max` exist so the brain's conviction
    enters this book AS RISK, not as a clip multiplier applied after the fact.
    (so) multiplied the RESULT, which broke the one property this function
    exists for: every trade risks the same $1.50, and `CLIP_MAX` is the ceiling
    that keeps a calm book from taking an oversized position. A post-hoc x6.7
    bypassed both — worse, because the mult is per-(side, lens) and the clip is
    per-COIN, the two normalisations FOUGHT: a favoured lens on a wide-range
    alt got the largest vol_clip AND the largest boost, so the risk-equalising
    this function does was inverted exactly where it mattered most.
    Scaling the RISK BUDGET instead is what conviction actually means — risk
    more on the bucket that has earned it — and the [CLIP_MIN, clip_max] bound
    still applies afterwards, so the ceiling holds. Defaults keep every other
    caller (and the replay) byte-identical."""
    _risk = RISK_USD if risk_usd is None else float(risk_usd)
    _cmax = CLIP_MAX if clip_max is None else float(clip_max)
    if not day_range_pct or day_range_pct <= 0:
        return CLIP_USD
    adverse = max(day_range_pct / 2.0, 0.5) / 100.0
    return round(min(_cmax, max(CLIP_MIN, _risk / adverse)), 2)


def book_spread_bps(book):
    """Top-of-book bid/ask spread in bps, or None if the book is missing/empty.
    Mirrors the ShadowBroker's fill-time computation (venues/shadow.py) EXACTLY,
    so the gate reads the same number the ledger records. None is the fail-open
    signal — the caller must treat 'unknown spread' as 'do not block'."""
    try:
        bids, asks = book.get("bids"), book.get("asks")
        if not bids or not asks:
            return None
        bid, ask = bids[0][0], asks[0][0]
        mid = (bid + ask) / 2.0
        return (ask - bid) / mid * 1e4 if mid else None
    except (AttributeError, TypeError, IndexError, ZeroDivisionError):
        return None


def spread_gate_blocks(spread_bps, threshold_bps):
    """True iff the gate is ENABLED (threshold > 0), the spread is KNOWN, AND it
    exceeds the threshold. Fail-open on BOTH a disabled gate (threshold <= 0 —
    the shipped default) and an unknown spread (None). Restrict-only: this can
    only ever cause a SKIP, never force an entry."""
    if threshold_bps <= 0 or spread_bps is None:
        return False
    return spread_bps > threshold_bps


# [2026-07-24 (dk)] 'breakoutup' is the taker-internal lens for an UP-REGIME
# crypto breakout (the entry loop relabels a candle-up breakout to it BEFORE the
# brain veto, so the broad 4h 'breakout' veto — right for un-gated breakouts —
# does not kill the up-regime subset). It is NOT scout-emitted; it exists so the
# up-regime population is graded + vetoed on its OWN closes (tag 'long-breakoutup')
# instead of the broad breakout grade. Shadow-only: NOT in LIVE_LENSES.
ALL_LENSES = frozenset({"breakout", "breakoutup", "dip", "momentum", "divergence"})
# [2026-07-17 LIVE = DIVERGENCE ONLY — operator decision] The live arm may fill
# ONE lens. The brain grades the other three NEGATIVE at n=1279-2620 with
# hit-rate 95% CIs entirely below 50% (dip -0.471%/.392, breakout -0.210%/.399,
# momentum -0.365%/.394) — three independent dip-buyer rejections across the
# fleet's history. Real money does not get to re-litigate that.
LIVE_LENSES = frozenset({"divergence"})


def allowed_lenses(mode):
    """Hard per-MODE lens allow-list. Fail-CLOSED, and deliberately NOT the
    brain's veto.

    Why this exists ALONGSIDE vetoed_lenses(): that one is RESTRICT-ONLY and
    fail-safe OPEN by design — a dark brain, a stale payload, a DB read blip or
    a lens dropped from the grade set all collapse to "veto nothing". That is
    correct for a shadow book whose JOB is grading every lens. It is
    catastrophic as the ONLY thing standing between real money and a lens the
    fleet has already rejected three times. Four independent paths re-enable
    dip/breakout/momentum with no error; none of them can reach this function,
    because it reads no bus payload at all.

    `mode` is taken EXPLICITLY rather than read off module-level TT_VENUE: four
    modules import this one (lighter_ticket_replay, lighter_scout_tuner,
    strategy_incubator, fleet_proprioception) and every one must keep grading
    ALL FOUR lenses on the shadow tape. A module-level read would make their
    behaviour depend on the importing process's environment — the exact
    "env silently decides real-money semantics" trap the 17-Jul VENUE fix
    closed. The brain's veto stays SENIOR on top of this (restrict-only).
    """
    return LIVE_LENSES if mode == "lighter_live" else ALL_LENSES


# [2026-07-30 (hj)] LIVE = DIVERGENCE **SHORT** ONLY. allowed_lenses() above was
# only HALF the real-money rule, and the missing half was load-bearing.
#
# MEASURED, from this bot's own live ledger: the live arm has 25 closes and
# **12 of them are `long-divergence`** (last 2026-07-24T13:53Z). The 17-Jul
# go-live note in main() states the risk in as many words — "long-divergence has
# ZERO realized fills and the live arm can take it" — and then it took twelve.
#
# What stopped it was NOT a gate. It was `TT_BULL_MODE` flipping on 24-Jul:
# BULL_LENS_SIDES omits ("divergence","long"), but that set is only ever
# consulted inside `if BULL_MODE:` at the entry loop. So the ONLY thing standing
# between real money and the measured-losing side of this lens was an ENV VAR
# that defaults to "off". Unset it, typo it, or deploy an image whose service
# never had it, and the live arm silently re-opens long divergence — the side
# the brain grades 0.470 ehit4h / -0.199%/4h, i.e. the half of the pool that
# LOSES (the short side is what carries it: 0.517 / +0.289%).
#
# This is the identical shape allowed_lenses' own docstring was written about,
# one level down: a restrict-only, fail-safe-OPEN path (BULL_MODE) used as the
# sole guard on real money. The fix is the same fix — a hard, per-MODE,
# fail-CLOSED allow-list that reads no env var and no bus payload.
ALL_SIDES = frozenset({"long", "short"})
LIVE_SIDES = {"divergence": frozenset({"short"})}


def allowed_sides(mode, lens):
    """Hard per-(MODE, LENS) side allow-list — the SIDE twin of allowed_lenses().

    Returns the set of sides `lens` may be filled on in `mode`. Non-live modes
    get BOTH sides: the shadow arm's job is to grade every (lens, side) pair,
    and narrowing it would blind the very grade that justifies the live rule.

    FAIL-CLOSED in the direction that matters: a lens with no LIVE_SIDES entry
    returns the EMPTY set on the live arm, so a lens added to LIVE_LENSES
    without a deliberate side decision fills NOTHING rather than both sides.
    Adding real money to a new lens must be two explicit edits, not one.

    `mode` is taken EXPLICITLY for the same reason allowed_lenses() takes it —
    four modules import this one and must keep grading both sides on the shadow
    tape regardless of the importing process's environment.

    Deliberately independent of BULL_MODE and of bull_entry_ok(): that gate is
    RESTRICT-ONLY and evaluated only when an env var is on, which is exactly why
    it cannot be the thing protecting real money. The bull gate stays, and stays
    senior on the shadow arm; this one cannot be turned off at all.
    """
    if mode != "lighter_live":
        return ALL_SIDES
    return LIVE_SIDES.get(lens, frozenset())


def side_of(ticket):
    """The ONE reading of a ticket's side, so belt and braces cannot disagree.

    Mirrors the entry loop's `is_long` (`side != "short"` ⇒ long), which is what
    actually drives `market_open`. A separate re-derivation here is how a gate
    ends up guarding a value the order path never uses.
    """
    return "short" if str((ticket or {}).get("side", "long")) == "short" \
        else "long"


# [2026-07-24 BULL DUAL-MODE — long-breakout(up-regime) + short-divergence,
# crypto-only, SHADOW-only. The bull-engine research settled the shape:
# divergence's only real side is SHORT and its only clean universe is CRYPTO
# (tradfi contaminates the read); the sole hint of a long edge is BREAKOUT, and
# it pays only in a per-asset UP regime with a TREND exit (TT_TRAIL_PCT). This
# mode fuses those into ONE entry policy. DEFAULT OFF: the gate only runs when
# TT_BULL_MODE is on, so it is a pure no-op otherwise. RESTRICT-ONLY (it can only
# SKIP an entry the base filters already admitted). Going live is operator-only
# AND gated on a SHADOW capturability proof first — the breakout edge is
# delay-0-only and may not survive the async taker's intraday fills.]
BULL_MODE = os.environ.get("TT_BULL_MODE", "off").strip().lower() \
    in ("on", "1", "true", "yes")
# the ONLY (lens, side) pairs the bull arm fills. 'breakoutup' (dk) is the
# relabelled up-regime breakout — long only, like 'breakout'.
BULL_LENS_SIDES = frozenset({("breakout", "long"), ("breakoutup", "long"),
                             ("divergence", "short")})


# Tradfi (tokenized equity / commodity / FX) bases. Kept LOCAL + env-driven —
# mirrors fleet_risk.EQUITY_BASES's own pattern — deliberately NOT imported from
# fleet_risk/regime_oracle, to keep the lean live-taker image (Dockerfile.
# tickettaker) free of their pandas dependency chain (a cross-import there would
# fail and silently under-restrict, the exact born-dark trap). Default = the
# fleet's equity set + the oracle's commodities + FX + the pre-IPO tokenised
# equities that bled the live book; override via TT_TRADFI_BASES.
TRADFI_BASES = {s.strip().upper() for s in os.environ.get(
    "TT_TRADFI_BASES",
    "SPY,QQQ,IWM,US100,US500,SOXL,AMD,MU,HOOD,RKLB,TSLA,NVDA,AAPL,MSFT,META,"
    "GOOGL,GOOG,AMZN,COIN,MSTR,PLTR,TSM,INTC,SKHYNIX,AMAT,EWY,LITE,CRCL,BMNR,"
    "SNDK,NBIS,MRVL,ASML,BABA,DELL,ORCL,QCOM,AVGO,ARM,SMCI,SPCX,ZHIPU,CBRS,"
    # [2026-08-06 (kt)] THE 41 THIS LIST WAS MISSING, from the venue's own
    # `strategy_index` (see `(kj)`). NOT a regression guard — LIVE EXPOSURE,
    # measured on the bus the day it shipped: 3 of 16 scout tickets were
    # non-crypto instruments this list did not catch (DRAM, CXMT, CAP), and
    # **CAP was on the `divergence` lens**. The live arm is divergence-SHORT
    # only, runs `bull: True`, and `("divergence","short")` is in
    # BULL_LENS_SIDES — so every live real-money entry passes through
    # `bull_entry_ok` -> `_is_crypto`, and this screen is the ONLY thing
    # standing between the real-money book and a short on a tokenised equity.
    # Its own docstring is the rationale: "the divergence short edge and the
    # breakout edge both live in CRYPTO; tradfi contaminates the read".
    # Synced by HAND on purpose: this list stays LOCAL (see above — importing
    # fleet_bus would drag a dependency into the lean live image, the
    # born-dark trap), and `test_taker_tradfi_parity` pins it EQUAL to
    # `fleet_bus.NONCRYPTO_BASES` so it cannot drift again.
    "NZDUSD,USDCAD,USDCHF,USDHKD,USDKRW,"
    "H100,URA,"
    "AAOI,BB,BE,BOT,BOTZ,CRWV,DRAM,GEV,GME,IBM,NOK,NOW,QNT,STRC,TTWO,WEN,"
    "BYD,HYUNDAIUSD,MINIMAX,POPMART,SAMSUNGUSD,SKHY,SKHYNIXUSD,SMIC,TENCENT,"
    "XIAOMI,"
    "ADI,ANSEM,ANTHROPIC,CAP,CXMT,FOLKS,OPENAI,UNITREE,"
    "WTI,BRENTOIL,NATGAS,USOIL,XAU,XAG,XCU,XPD,XPT,PAXG,WHEAT,CORN,"
    "USDJPY,AUDUSD,EURUSD,GBPUSD,USDCNH,"
    # [2026-08-20 (ty)] THE EIGHT THIS LIST HAD DRIFTED BY — the (kt) shape
    # again, two weeks later, and found the same way: measured against the
    # venue's own `strategy_index`, 8 of 101 active non-crypto books were
    # absent from BOTH this list and `fleet_bus.NONCRYPTO_BASES`. All eight
    # are recent listings, which is the mechanism — the venue lists weekly and
    # both lists are reconciled by hand. `test_taker_tradfi_parity` pins the
    # two EQUAL, so this edit and the fleet_bus one are a single change; and
    # `scripts/audit_noncrypto_fallback.py` now measures the drift against the
    # venue directly, so the NEXT recurrence is found by a guard rather than
    # by a test noticing after the fact.
    "AXTI,SOXS,WDC,KIOXIA,KORU,CASHCAT,MRNA,US10Y").split(",") if s.strip()}


def _is_crypto(sym):
    """True unless `sym` is a Lighter tokenized-equity/commodity/FX book
    (TRADFI_BASES). The divergence short edge and the breakout edge both live in
    CRYPTO; tradfi contaminates the read — so the bull arm is crypto-only."""
    return str(sym or "").split("/")[0].upper() not in TRADFI_BASES


EMA_N = int(os.environ.get("TT_REGIME_EMA_N", "20"))


def up_regime(closes, n=None):
    """Per-asset UP regime from DAILY closes (oldest->newest): the last close is
    above its own EMA(n) AND the EMA is rising. Tri-state — True / False /
    None(too few bars). This is the broad-coverage read the oracle's ~8% grading
    lacks: it works for ANY book with a candle history. Matches the bull-engine
    research's own 'close>EMA20 & rising' up-regime definition."""
    n = EMA_N if n is None else n
    if not closes or len(closes) < n + 2:
        return None
    k = 2.0 / (n + 1)
    ema = closes[0]
    prev = ema
    for c in closes[1:]:
        prev = ema
        ema = c * k + ema * (1.0 - k)
    return closes[-1] > ema and ema > prev


def up_strength(closes, n=None):
    """A bounded UP-regime STRENGTH in [0,1] from DAILY closes (oldest->newest):
    the bull-engine research's #1 winning-breakout feature, quantified for RANKING
    (up_regime stays the boolean gate). 0.0 when not in a confirmed up-regime (or
    too few bars), rising toward 1 as the last close sits further above a steeper-
    rising EMA(n). Blends the close-vs-EMA margin (10%+ = full) and the EMA slope
    (2%/day = full). Strength>0 <=> up_regime()==True by construction (same two
    inequalities), so it never disagrees with the gate."""
    n = EMA_N if n is None else n
    if not closes or len(closes) < n + 2:
        return None
    k = 2.0 / (n + 1)
    ema = closes[0]
    prev = ema
    for c in closes[1:]:
        prev = ema
        ema = c * k + ema * (1.0 - k)
    if ema <= 0 or prev <= 0:
        return 0.0
    margin = closes[-1] / ema - 1.0        # last close above its EMA
    slope = ema / prev - 1.0               # EMA rising?
    if margin <= 0 or slope <= 0:
        return 0.0                          # not a confirmed up -> zero strength
    m = min(margin / 0.10, 1.0)            # 10%+ above EMA = full marks
    s = min(slope / 0.02, 1.0)             # 2%/day EMA slope = full marks
    return round(0.6 * m + 0.4 * s, 4)


def breakout_quality(up_str, range_pos, vol_m):
    """A bounded [0,1] QUALITY score for a breakout candidate — the scanner
    'sidekick': it ranks admitted breakouts (so a scarce slot can go to the
    highest-conviction one) and feeds the default-off TT_BRK_QUALITY_MIN gate.
    Blends the research's winning features: up-regime STRENGTH (0.5, the #1
    signal), nearness to the daily high (0.3), liquidity (0.2). ADVISORY — it
    NEVER admits anything up_regime/bull_entry_ok refused; it only ranks/filters
    within the admitted set. up_str None -> treated as 0 (unknown = worst). The
    WEIGHTS are a research-seeded starting point; the entry-feature capture lets
    the winning threshold be DERIVED from shadow outcomes rather than guessed."""
    u = 0.0 if up_str is None else max(0.0, min(float(up_str), 1.0))
    r = (max(0.0, min((float(range_pos) - 0.90) / 0.10, 1.0))
         if range_pos is not None else 0.0)          # 0.90->0, 1.00->1
    v = max(0.0, min(float(vol_m) / 5.0, 1.0)) if vol_m else 0.0   # $5M+ = full
    return round(0.5 * u + 0.3 * r + 0.2 * v, 4)


def _up_from_ticket(ticket):
    """Tri-state up-regime from the oracle's per-asset stamp on a ticket:
    dir==+1 -> True, dir==-1 -> False, absent -> None (ungraded)."""
    d = (ticket.get("regime") or {}).get("dir")
    return True if d == 1 else (False if d == -1 else None)


def bull_entry_ok(lens, side, ticket, up=None):
    """The bull dual-mode entry gate (RESTRICT-ONLY; only applied when
    BULL_MODE). Admits ONLY long-breakout + short-divergence, crypto-only, with a
    per-asset regime gate. `up` is a tri-state up-regime read the caller supplies
    (True/False/None) — the CANDLE-derived up_regime() for broad coverage; when
    None it falls back to the oracle's sparse per-asset stamp. A LONG needs a
    CONFIRMED up (fail-CLOSED: buying up-regime alone LOSES, the signal needs the
    confirmation); a SHORT is refused only INTO a confirmed up — else the funding
    screen carries it."""
    if (lens, side) not in BULL_LENS_SIDES:
        return False
    # [2026-08-06 (ku)] BOTH screens, and the order is deliberate. The scout
    # now stamps `noncrypto` on every ticket from the VENUE's own class, so a
    # newly listed tokenised equity is screened the moment the scout sees it —
    # no code change here, no marked real-money deploy. The local hand list
    # stays as the fallback for a ticket with no stamp (an older scout, or a
    # book the venue does not classify): ABSENT means no opinion, never
    # "crypto". Restrict-only — either screen may reject, neither may admit.
    if ticket.get("noncrypto") is True:
        return False
    if not _is_crypto(ticket.get("sym")):
        return False
    if up is None:
        up = _up_from_ticket(ticket)
    if side == "long":
        return up is True          # confirmed up required
    return up is not True          # short: allowed unless a confirmed up


# The breakout arm's TREND exit params (only used under BULL_MODE): a WIDE hard
# stop (the -3% bracket churns the pop; entries draw -3.4% before running) + a
# trailing give-back off the peak, and NO fixed TP cap.
BRK_TRAIL = float(os.environ.get("TT_BRK_TRAIL", "0.06"))   # trail 6% off peak
BRK_SL = float(os.environ.get("TT_BRK_SL", "-0.07"))        # wide hard stop
# The scanner sidekick's ADVISORY quality gate: skip a breakout whose
# breakout_quality() < this. DEFAULT 0.0 = inert (blocks nothing) — the score is
# CAPTURED on every breakout entry regardless, so the winning threshold can be
# derived from shadow outcomes before it is ever raised. Restrict-only.
BRK_QUALITY_MIN = float(os.environ.get("TT_BRK_QUALITY_MIN", "0"))


def bull_exit(lens):
    """Per-lens exit routing under BULL_MODE, returned as (bars_or_None, trail)
    for exit_reason: BREAKOUT runs the TREND exit (no TP cap, wide SL, trail);
    every other lens (i.e. divergence) keeps its fixed reversion bracket. When
    BULL_MODE is off returns (None, None) = the module default, unchanged."""
    if not BULL_MODE:
        return None, None
    if lens in ("breakout", "breakoutup"):      # (dk) up-regime breakout too
        return (999.0, BRK_SL, MAX_HOLD_H), BRK_TRAIL
    return None, 0.0        # divergence: fixed bracket, no trail


_UP_CACHE = {}             # sym -> (up_tristate, strength, expiry_epoch) — read TTL


def up_read(venue, sym, now_ts, ttl_s=3600.0):
    """Cached candle-derived up-regime for `sym`: fetch ~EMA_N+6 DAILY closes off
    the venue and run up_regime(). This is the COVERAGE FIX — it works for ANY
    book, not the oracle's ~8% graded set. Tri-state (True/False/None); any fetch
    failure -> None -> the long is fail-CLOSED. Cached with a TTL, but the bot is
    RUN-ONCE (a fresh process each cycle) so the cache is effectively intra-cycle;
    a recurring candidate re-fetches next boot. Only breakout candidates trigger
    it (the caller gates on lens)."""
    hit = _UP_CACHE.get(sym)
    if hit and hit[2] > now_ts:
        return hit[0]
    up = None
    strength = None
    try:
        end_ms = int(now_ts * 1000)
        start_ms = end_ms - int((EMA_N + 6) * 86400 * 1000)
        # venue.candles returns Lighter's candle DICTS ({t,o,h,l,c,v,...}); the
        # close is c["c"]. Handle a bare-float shape too (defensive).
        raw = venue.candles(sym, "1d", start_ms, end_ms) or []
        # DROP the still-forming daily bar (end_ms=now): the sibling daily-regime
        # reads do the same (lighter_trend_bot `candles[:-1]`, family parse_candles).
        # A partial bar makes closes[-1] the LIVE price, which collapses up_regime's
        # "close>EMA AND EMA rising" into the single test "price>yesterday's EMA" —
        # the "rising" half is algebraically lost. Completed bars only, matching
        # the bull-engine research's own completed-bar EMA20 up-regime definition.
        raw = raw[:-1] if raw else raw
        closes = [float(c["c"]) if isinstance(c, dict) else float(c) for c in raw]
        up = up_regime(closes)
        strength = up_strength(closes)     # cached alongside — one fetch, no extra
    except Exception:  # noqa: BLE001 — a candle blip fails CLOSED, never a crash
        up = None
        strength = None
    _UP_CACHE[sym] = (up, strength, now_ts + ttl_s)
    return up


def up_read_strength(sym):
    """The up-regime STRENGTH cached by the last up_read(sym) this cycle (None if
    unread or the fetch failed). Companion accessor — NO extra fetch; the caller
    that already ran up_read(sym) for the gate reads the strength for free."""
    hit = _UP_CACHE.get(sym)
    return hit[1] if hit else None


# [2026-07-28 (dv) CROSS-CYCLE up-regime CACHE] The bot is RUN-ONCE (a fresh
# process every ~5 min), so `_UP_CACHE`'s TTL died at boot and up_read re-fetched
# each book's DAILY candles every cycle — ~12x/hour for a signal that only moves
# once a day. Worse since (dk): up_read now runs for EVERY breakout ticket
# pre-veto. Persisting the cache across boots collapses that to ~1 fetch/book/TTL,
# cutting REST-throttle pressure. Shadow-only in effect (up_read never runs on the
# live arm — breakout is filtered by allowed_lenses). Cache-only + fail-safe: a
# dark read seeds nothing (up_read fetches fresh), a dark write drops nothing.
def upregime_cache_key(bot_row):
    return f"{bot_row}-upregime"


def load_upregime_cache(store, bot_row, now_ts):
    """Seed _UP_CACHE from the persisted cross-cycle cache — only UNEXPIRED
    entries (each is [up, strength, expiry_epoch]). Fail-safe: any read problem
    seeds nothing, so up_read simply fetches fresh (no regression, no stale gate)."""
    try:
        raw = store.load_state(upregime_cache_key(bot_row)) or {}
        for sym, v in (raw.get("syms") or {}).items():
            if (isinstance(v, (list, tuple)) and len(v) == 3
                    and isinstance(v[2], (int, float)) and float(v[2]) > now_ts):
                _UP_CACHE[sym] = (v[0], v[1], float(v[2]))
    except Exception:  # noqa: BLE001 — a dark cache read is never a stop
        pass


def save_upregime_cache(store, bot_row, now_ts):
    """Persist the UNEXPIRED up-regime cache for the next run-once boot. Skips a
    write when there is nothing live to save (e.g. the live arm, which never
    populates the cache). Fail-safe: a write problem drops the cache, not the run."""
    try:
        syms = {s: [v[0], v[1], v[2]] for s, v in _UP_CACHE.items()
                if isinstance(v, tuple) and len(v) == 3 and float(v[2]) > now_ts}
        if syms:
            store.save_state(upregime_cache_key(bot_row),
                             {"syms": syms, "updated": iso(now())})
    except Exception:  # noqa: BLE001
        pass


def lens_evidence(o, min_n=None):
    """(n, floor_met, avg_pct, hit) for one lens grade — EPISODE basis when
    the brain's v3 fields are present, RAW fallback otherwise.

    [2026-07-21 IMB-24, review-sanctioned migration] Raw `n4h` counts
    serially-correlated emissions: MEASURED 8-11x per genuinely independent
    episode (31x for momentum), so a raw floor of 75 can be met by ~2-8
    independent opinions. When the v3 engine publishes episode fields
    (eps4h/n_syms/eavg4h_pct/ehit4h — validated at this review: eps4h
    117-850 across the four lenses), the floor is eps4h >= TT_LENS_VETO_MIN_EPS
    AND n_syms >= TT_LENS_VETO_MIN_SYMS, and the GRADE is the episode-deduped
    mean/hit. Fallback to the raw rule when episode fields are absent keeps
    the restrict capability under a v2 brain relapse (which the immune organ
    pages on independently)."""
    o = o or {}
    if o.get("eps4h") is not None:
        eps_min = int(os.environ.get("TT_LENS_VETO_MIN_EPS", "25"))
        syms_min = int(os.environ.get("TT_LENS_VETO_MIN_SYMS", "10"))
        floor = ((o.get("eps4h") or 0) >= eps_min
                 and (o.get("n_syms") or 0) >= syms_min)
        return ((o.get("eps4h") or 0), floor,
                (o.get("eavg4h_pct") or 0), (o.get("ehit4h") or 0))
    if min_n is None:
        min_n = int(os.environ.get("TT_LENS_VETO_MIN_N", "75"))
    n = o.get("n4h") or 0
    return n, n >= min_n, (o.get("avg4h_pct") or 0), (o.get("hit4h") or 0)


# [2026-07-29 (fn)] Which SINGLE side of each lens is this arm allowed to take?
# Under TT_BULL_MODE the entry gate admits only (breakout,long)/(breakoutup,long)
# /(divergence,short), so `divergence` is a SHORT-ONLY lens here — and grading it
# on a population that is 69% long is grading a book this arm does not trade.
# Returns {} when bull mode is off (both sides reachable => pooled is correct).
def restricted_sides():
    if not BULL_MODE:
        return {}
    by_lens = {}
    for lens, side in BULL_LENS_SIDES:
        by_lens.setdefault(lens, set()).add(side)
    return {lens: next(iter(s)) for lens, s in by_lens.items() if len(s) == 1}


SIDE_AWARE_VETO = os.environ.get(
    "TT_LENS_VETO_SIDE_AWARE", "on").strip().lower() not in ("off", "0", "false", "no")


def vetoed_lenses(lens_fwd, min_n=None, sides=None, realised=None):
    """THE lens veto rule, and the single authority for it (2026-07-17): a
    lens the brain grades negative at sample size stops getting fills.

    Extracted from this module's own loop so the rule has ONE definition. It
    had two — the loop below and lighter_scout_tuner.vetoed_lenses — and a
    third was about to appear in strategy_incubator, which breeds the very
    bars this veto decides are worthless. Consumers must not drift on the
    question "is this lens allowed to trade?".

    [2026-07-21 IMB-24] Evidence basis migrated to EPISODES via
    lens_evidence() — measured consequence on the 21-Jul payload, recorded
    honestly: dip flips allowed->vetoed (raw hit4h 0.505 vs episode ehit4h
    0.495 — the dedup'd number sits on the other side of coin-flip).
    Restrict-only, shadow-book consequence only (the LIVE taker's
    allowed_lenses is divergence-only regardless).

    RESTRICT-ONLY and fail-safe open: an empty/missing grade set vetoes
    nothing (freshness is the CALLER's job — see the loop and the tuner).

    [2026-07-29 (fn) SIDE-AWARE] `sides` maps lens -> the ONE side this arm may
    trade (restricted_sides()). When the brain publishes a `by_side` grade for
    that side AND it meets the same floor, the verdict is taken from THAT
    sub-population instead of the pooled one — because the pooled grade answers
    a question about trades this arm cannot make. Measured on the 200h tape:
    pooled divergence ehit4h 0.483 / eavg -0.093% (VETO) while the short side
    the live arm actually trades is 0.513 / +0.139% and short+crypto is 0.525 /
    +0.289%; the long side (69% of episodes) is what fails, at 0.470 / -0.199%.
    [2026-08-01 (ij) — THAT MEASUREMENT HAS SINCE MOVED, recorded rather than
    left to be re-derived (I12). The short side now grades 0.502 / **-0.155%**
    over 305 episodes: it has gone NEGATIVE on the forward basis and escaped
    the old veto by 0.002 of hit rate. It is not vetoed today, and the reason
    is no longer the sign of this number — it is that the lens's OWN 16 live
    closes read +0.558%, and realised closes are senior to a 4h proxy for a
    book that holds a bracket. See `realised_lens_evidence`.]
    This is NOT a loosening — it cuts BOTH ways: an arm restricted to a side
    that grades badly inside a healthy pool now gets vetoed where it did not.
    Fail-safe to the pre-(fn) rule in every degraded case: no `sides`, no
    `by_side` block, an unmet sub-floor, or TT_LENS_VETO_SIDE_AWARE=off all
    fall back to the pooled grade byte-for-byte."""
    out = set()
    for lens, o in (lens_fwd or {}).items():
        graded = o
        if SIDE_AWARE_VETO and sides and lens in (sides or {}):
            sub = ((o or {}).get("by_side") or {}).get(sides[lens])
            if isinstance(sub, dict) and lens_evidence(sub, min_n=min_n)[1]:
                graded = sub
        # [2026-08-01 (ij)] THE LENS'S OWN REALISED CLOSES ARE SENIOR.
        # `brain-lens-forward` grades the SCOUT's tickets on 4h/24h FORWARD
        # MARKS. The taker does not hold 4h — it holds a bracket (tp/sl/
        # max_hold). `(dm)` already established the consequence and built a
        # bespoke escape hatch for one lens: "'breakoutup' earns its OWN veto —
        # from its own realized closes, NOT the 4h forward grade (dk) proved
        # misjudges it ... graded at the right horizon BY CONSTRUCTION".
        # This generalises that instead of adding a third bespoke path.
        rl = (realised or {}).get(lens)
        if rl is not None:
            r_n, r_mean, r_t = rl
            if r_n >= REALISED_MIN_N:
                if realised_loses(r_mean, r_t):
                    out.add(lens)
                continue          # realised decides, in BOTH directions
        _n, floor_met, avg, hit = lens_evidence(graded, min_n=min_n)
        if floor_met and lens_loses(avg, hit):
            out.add(lens)
    return out


#: Floors for the REALISED-closes verdict. A lens decides its own fate only
#: once it has enough of its own trades: below this the 4h forward proxy is
#: still the only evidence there is.
REALISED_MIN_N = int(os.environ.get("TT_LENS_REALISED_MIN_N", "10"))
#: How much evidence a realised LOSS needs before it vetoes. Deliberately a
#: t-stat and not just `mean < 0`: at n=10 a mean is noise, and a veto that
#: fires on noise starves a lens that never had a chance. -1.0 is one-sided
#: and lenient; the one lens it currently catches (`long-dip`) reads -2.66.
REALISED_VETO_T = float(os.environ.get("TT_LENS_REALISED_VETO_T", "-1.0"))


def realised_loses(mean_pct, t):
    """Does this lens's OWN trading record say it loses money?

    Restrict-only and evidence-gated: BOTH a negative mean and a t at or below
    `REALISED_VETO_T`. A lens that is merely noisy-negative keeps trading and
    keeps collecting — the shadow arm exists to grade, and a veto on n=10 of
    noise would end the grade before it started.
    """
    return mean_pct < 0 and t <= REALISED_VETO_T


def current_policy():
    """The policy-signature half of the `extra.policy` stamp — the fields THIS
    process is running RIGHT NOW, in exactly the shape `_close_extra` writes
    them. ONE builder for both the stamp and the veto's era filter, so the two
    cannot drift: a close is stamped with `current_policy()` and a row is
    admitted to the realised grade iff its stamp matches `current_policy()`.

    [(hj)] `sides` is stamped per lens because the side rule changed on 30-Jul
    and a grader pooling across it would mix long+short divergence eras exactly
    as the retracted alpha claim did. Capacity levers (`max_open`,
    `ticket_top_n`) are stamped BESIDE these in `_close_extra` but are NOT
    signature fields — (hc): ordinary tuning must not reset an era."""
    return {"bull": BULL_MODE,
            "lenses": sorted(allowed_lenses(TT_VENUE)),
            "sides": {l: sorted(allowed_sides(TT_VENUE, l))
                      for l in sorted(allowed_lenses(TT_VENUE))},
            "venue": TT_VENUE}


#: [2026-08-13] Mirrors `scripts/golive_readiness.POLICY_SIG_FIELDS` — pinned
#: equal by `tests/autonomy/test_realised_veto_era.py`, which also pins the
#: two signature functions byte-equal on shared fixtures. A direct import is
#: blocked in the OTHER direction than usual: this file ships in the LIVE
#: taker image, and dragging the grader into a real-money image is the
#: born-dark class. The test is the drift arm that makes two copies unable to
#: disagree silently (the `audit_lever_bounds` pattern).
_POLICY_SIG_FIELDS = ("venue", "bull", "lenses", "sides")

#: A row that carries NO `policy` stamp at all — written before this book
#: adopted the stamp. Distinct from a stamp that is present and malformed,
#: which stays fail-closed (excluded). (kk): an absence is not a change.
_STAMP_ABSENT = "\x00absent"


def _policy_stamp_state(extra):
    """`_STAMP_ABSENT` | None (unreadable) | canonical signature string.

    The policy branch of `scripts/golive_readiness.stamp_state`, scoped to
    this book's own rows (every post-adoption taker close carries `policy`,
    so the grader's bracket branch never applies here). A stamp without a
    non-empty `lenses` is unreadable: a policy naming no admissible signal
    describes nothing."""
    if not isinstance(extra, dict) or "policy" not in extra:
        return _STAMP_ABSENT
    pol = extra.get("policy")
    if not isinstance(pol, dict):
        return None
    sig = {k: pol[k] for k in _POLICY_SIG_FIELDS if k in pol}
    if not sig.get("lenses"):
        return None
    try:
        return json.dumps(sig, sort_keys=True)
    except (TypeError, ValueError):
        return None


def realised_lens_evidence(rows, bot_row, sides=None, policy=None, min_n=None):
    """{scout-lens: (n, mean_pct, t)} from THIS ARM's own closed trades.

    Keyed to the SCOUT lens name so it can be compared against the forward
    grade: ledger `reason` is `<side>-<lens>_<exit>` ('short-divergence_tp'),
    so the lens is the part after the side.

    SIDE-AWARE for the same reason `vetoed_lenses` is: when this arm may only
    fill one side of a lens, the other side's closes answer a question about
    trades it cannot make. The live arm trades `divergence` SHORT only, and its
    long-divergence closes — which predate the (hj) hard gate — read -1.581%
    against short's +0.576%. Pooling them would veto the live book on trades it
    is already forbidden to take.

    Pure; the caller supplies rows and owns freshness.

    [2026-08-13 (lj)] ERA-AWARE when `policy` is supplied: only rows whose
    `extra.policy` stamp matches the CURRENT policy signature are graded.

    THE INCIDENT this closes: the live arm's short-divergence read n=44,
    mean −0.468%, t=−0.83 POOLED — veto silent — while the rows taken under
    the policy it actually runs read n=31, mean −1.128%, t=−1.75 (and the
    trailing 8 days −2.456%, t=−3.68, nine of ten closes `_sl`). The 13
    diluting rows predate the 30-Jul policy boundary THE GRADER ALREADY
    REFUSES TO POOL ACROSS — era discipline existed in `golive_readiness`
    and never reached this actuator, the exact I15 shape ("when a bad idea
    is removed from a report, grep for it in the things that ACT").

    Era membership is the (jf)/(kk) stamp rule, membership-by-signature:
      * stamp matches `policy`   -> in the era sample;
      * stamp differs            -> out (another era's trade);
      * stamp unreadable         -> out (fail-closed — a trade whose policy
        cannot be confirmed cannot confirm the current one);
      * stamp ABSENT             -> out ONLY when at least one of this arm's
        rows carries a readable stamp (I6: an absence is evidence only
        against a control group). An arm with NO stamps anywhere keeps the
        pooled behaviour — "the stamp mechanism is not deployed" must not
        read as "every trade is another era's".
    A lens whose ERA sample is below `min_n` (default REALISED_MIN_N) is
    graded on the arm's FULL record instead — scoped-preferred,
    pooled-fallback; see the merge comment below for why the proxy must NOT
    take over there.
    Deliberately signature-MATCH, not the gate's same-signature SUFFIX: an
    A→B→A ledger pools both A runs here, because the question is "does the
    policy the arm runs lose money?", and a policy's own earlier record is
    admissible for that. Degrades: `policy=None` (legacy callers) or an
    unreadable current signature -> pooled, byte-for-byte pre-(lj).
    """
    import math

    try:
        cur_sig = (_policy_stamp_state({"policy": dict(policy)})
                   if policy else None)
    except (TypeError, ValueError):
        cur_sig = None          # malformed current policy -> pooled, never raise
    any_stamped = False
    if cur_sig:
        for r in (rows or []):
            if (r or {}).get("bot") != bot_row:
                continue
            if _policy_stamp_state(r.get("extra")) is not _STAMP_ABSENT:
                any_stamped = True
                break

    buckets = {}        # rows stamped with the CURRENT policy (the era sample)
    pooled = {}         # every row, the pre-(lj) sample — the thin-era fallback
    for r in (rows or []):
        if (r or {}).get("bot") != bot_row:
            continue
        in_era = True
        if cur_sig and any_stamped:
            st = _policy_stamp_state(r.get("extra"))
            in_era = st is not _STAMP_ABSENT and st == cur_sig
        # OPEN positions carry an UNREALISED mark and must not be graded.
        #
        # [2026-08-06 (kq)] THE `exit_reason == "hold"` CLAUSE IS GONE — it was
        # discarding 22% of this book's REALISED record, by exit path.
        #
        # The claim it rested on ("`fetch_paper_trades` returns open positions
        # with exit_reason='hold'") is FALSE of this ledger, measured three
        # ways: that helper reads only `paper_trades` (the CLOSED table), it
        # hardcodes `is_open: False` on every row it builds, and the shadow
        # arm's 165 rows carry **165 distinct trade_ids with ZERO duplicate
        # (pair, opened_at) groups** — so a `_hold` row is never a snapshot
        # that later re-closes as `_tp`. `hold` is what `exit_reason()` returns
        # when NO bracket condition fired, so a close written with it is a
        # position closed by some other path — a real trade with realised P&L.
        #
        # WHAT IT COST, measured on the live ledger the day this shipped:
        #   * `breakoutup` — n=13 −1.856%/t=−1.18 (VETOED, `realised_loses`)
        #     vs n=22 −0.242%/t=−0.22 on its full record: NOT a loser. **The
        #     verdict flipped**, so a lens was being denied fills on a sample
        #     truncated by exit path.
        #   * `momentum` — absent ENTIRELY (every close exits `hold`), so a
        #     whole lens was invisible to the realised veto.
        #   * `divergence`, the LIVE arm's only lens — n=61 -> 74 shadow,
        #     37 -> 41 live. Verdict unchanged, but this is the evidence that
        #     overrides the forward proxy for a real-money book (I14), and it
        #     was 18% short.
        #
        # THE CORROBORATION that settles it: I14 in CLAUDE.md cites `dip` at
        # **−1.162%/trade, t=−2.66**. That is the hold-INCLUSIVE number (n=13);
        # the shipped filter computes −2.485%/t=−2.97 on n=4. The doctrine was
        # written from the full record and the code drifted from it.
        #
        # THE DISCRIMINATOR IS `is_open`, AND AN ABSENT KEY DEFAULTS TO OPEN.
        # That default is what the old 'hold' clause was really reaching for,
        # and `test_open_positions_never_reach_the_realised_grade` is right to
        # demand it: a caller who hands over a row with no `is_open` at all has
        # told us nothing, and grading an unknown row is the very guess this
        # excludes. It costs nothing in production — `fetch_paper_trades` sets
        # the key on every row it builds — while keeping the fail-safe for any
        # future caller. What it does NOT do is infer "open" from an exit
        # LABEL, which is how 22% of a realised ledger went missing.
        if r.get("is_open", True):
            continue
        # SHAPE, verified against `bot_pnl_store.fetch_paper_trades` itself:
        # it SPLITS the stored `reason` into `enter_tag` ('short-divergence')
        # + `exit_reason`, and names the return `profit_ratio`. My first cut
        # read `reason`/`pnl_pct` — the raw COLUMN names — and silently graded
        # nothing, which on the live payload would have let the forward proxy
        # halt the live arm. `reason`/`pnl_pct` stay as fallbacks so a caller
        # reading the ledger table directly still works.
        pct = r.get("profit_ratio")
        if pct is None:
            pct = r.get("pnl_pct")
        if pct is None:
            continue
        head = str(r.get("enter_tag") or r.get("reason") or "").split("_", 1)[0]
        if "-" not in head:
            continue
        side, _, lens = head.partition("-")
        if not lens:
            continue
        if sides and lens in sides and side != sides[lens]:
            continue
        try:
            v = float(pct)
        except (TypeError, ValueError):
            continue
        pooled.setdefault(lens, []).append(v)
        if in_era:
            buckets.setdefault(lens, []).append(v)

    def _stats(v):
        n = len(v)
        mean = sum(v) / n
        if n > 1:
            sd = math.sqrt(sum((x - mean) ** 2 for x in v) / (n - 1))
            t = (mean / (sd / math.sqrt(n))) if sd else 0.0
        else:
            t = 0.0
        return n, mean * 100.0, t

    # [(lj)] SCOPED-PREFERRED, POOLED-FALLBACK. The current policy's own
    # record decides once it clears `min_n`; below that the arm's FULL record
    # stays senior to the 4h proxy — I14's horizon argument (a bracket-holding
    # book is misjudged by 4h marks) is not era-conditional, and the flagship
    # case is `dip`: n=13/t=−2.66 across eras, ~0 closes under the current
    # policy because the veto itself blocks them. Falling to the PROXY there
    # would have RELEASED the fleet's only significant realised loser on the
    # day this shipped. Restrict-direction conservative by construction: a
    # standing veto holds until current-policy evidence clears the floor.
    min_n = REALISED_MIN_N if min_n is None else int(min_n)
    out = {}
    for lens, v in pooled.items():
        era_v = buckets.get(lens) or []
        out[lens] = _stats(era_v if len(era_v) >= min_n else v)
    return out


#: Restores the pre-(ij) conjunction (`avg < 0 AND hit < 0.5`). Kept because
#: this rule gates a REAL-MONEY book and a change to it must be revertible
#: without a deploy — the FLEET_RISK_MODE / BRAIN_MULT_ENGINE pattern.
LEGACY_HIT_GATE = os.environ.get(
    "TT_LENS_VETO_LEGACY_HIT_GATE", "").strip().lower() in ("1", "on", "true")


def lens_loses(avg, hit):
    """Does this grade say the lens LOSES MONEY? Expectancy only.

    [2026-08-01 (ij)] THE `hit < 0.5` CONJUNCT IS GONE, and it was the same
    non-sequitur this fleet has already ruled on once. `(fk)` removed win rate
    from the GO-LIVE GATE on 29-Jul because **win rate is orthogonal to
    expectancy** — 🌾 carry wins 38.8% of its trades and is the best-evidenced
    book in the fleet. The lens veto kept win rate as a NECESSARY condition, so
    a lens that loses money while winning slightly more than half its bets was
    structurally unvetoable. Same wrong idea, in an actuator instead of a
    report.

    MEASURED on the live `brain-lens-forward` payload the day this shipped:

        lens                 eavg4h_pct   ehit4h    old rule   new rule
        dip                     -0.027     0.526    allowed    VETO
        divergence / SHORT      -0.155     0.502    allowed    VETO
        divergence (pooled)     -0.098     0.490    VETO       VETO
        momentum                -0.044     0.435    VETO       VETO
        breakout                +0.026     0.480    allowed    allowed

    Two of those matter. `dip` is the fleet's only STATISTICALLY SIGNIFICANT
    taker result — its own realised closes read n=13, **-1.162%/trade,
    t=-2.66, -$9.15** — and it escaped the veto on a 52.6% hit rate.
    `divergence/short` is the LIVE book's only lens; it escaped by **0.002**.
    When `(fn)` justified the live short-only rule it measured that side at
    `0.513 / +0.139%`; it has since degraded to `0.502 / -0.155%` over 305
    episodes, and nothing could say so.

    NOTE THE ASYMMETRY, because it is the whole point: this does NOT veto a
    lens with POSITIVE expectancy and a low hit rate. That is the carry shape —
    lose often, win big — and vetoing it would be the mirror image of the
    defect being fixed. `breakout` (+0.026 at hit 0.480) stays allowed, and
    would have been wrongly killed by a naive `avg < 0 or hit < 0.5`.

    Win rate is still REPORTED by `lens_evidence` and still consumed by the
    tuner — demoted from a bar, exactly as `(fk)` demoted it, not deleted.

    RESTRICT-ONLY and fail-safe open are preserved: the CALLER owns freshness,
    and a missing/thin grade vetoes nothing.
    """
    if LEGACY_HIT_GATE:
        return avg < 0 and hit < 0.5
    return avg < 0


# [2026-07-24 (dm) INCREMENT B] 'breakoutup' earns its OWN veto — from its own
# realized closes, NOT the 4h forward grade (dk) proved misjudges it.
#
# WHY a SEPARATE path from vetoed_lenses() above (which is otherwise THE single
# veto authority): that one reads 'brain-lens-forward', which grades the SCOUT's
# tickets on FORWARD marks and is keyed by SCOUT lens name. 'breakoutup' is a
# taker-internal relabel — it is NOT a scout lens and can NEVER appear there
# (verified: the scout hardcodes {breakout,dip,momentum,divergence}). The only
# brain payload keyed by CLOSE-TAG is 'brain-stake-mults': mults[bot]['long-
# breakoutup'] is published ONLY once the brain has graded that tag's own closes
# a loser at its floor and REDUCED it (bot_learn.py:1058 `if mult is None:
# continue`; MULT_MIN_N=30 for a 0.5x). So a reduce to the FLOOR (mult<=0.5 =
# wr<0.25, pnl<0 at n>=30) is the brain's DECISIVE "this lens loses" verdict ->
# veto. A MILD reduce (0.75) or an expand (winner) does NOT veto, so those keep
# collecting for the (dj) quality refinement — the veto harmonises with the
# quality pipeline instead of starving it. Realized closes reflect the TREND-exit
# hold, so this is graded at the right horizon BY CONSTRUCTION (no 4h/24h trap).
#
# RESTRICT-ONLY + fail-OPEN: an absent / thin / mild / positive grade vetoes
# nothing. SHADOW-ONLY by construction: breakoutup never exists on the live arm
# (LIVE_LENSES={divergence} filters breakout before the relabel), and BOT_ROW
# there is '<bot>-lighter', whose 'long-breakoutup' bucket is always empty.
BRKUP_VETO_MULT = float(os.environ.get("TT_BRKUP_VETO_MULT", "0.5"))  # <=0 disables
BRKUP_VETO_MIN_N = int(os.environ.get("TT_BRKUP_VETO_MIN_N", "30"))   # = MULT_MIN_N


def breakoutup_self_vetoed(mults_payload, bot_row):
    """True iff the brain has DECISIVELY graded this bot's OWN 'long-breakoutup'
    closes a loser: a floor-met (n>=BRKUP_VETO_MIN_N) reduce to <=BRKUP_VETO_MULT.
    Pure; fail-OPEN on any missing/thin field. Disabled when BRKUP_VETO_MULT<=0.
    The CALLER owns freshness (mirrors the lens-forward veto loop)."""
    if BRKUP_VETO_MULT <= 0:
        return False
    entry = ((mults_payload or {}).get("mults") or {}).get(bot_row) or {}
    if not isinstance(entry, dict):
        return False
    tag = entry.get("long-breakoutup")
    if not isinstance(tag, dict):
        return False
    if (tag.get("n") or 0) < BRKUP_VETO_MIN_N:
        return False               # below the brain's floor — keep collecting
    return (tag.get("mult") or 1.0) <= BRKUP_VETO_MULT


def incredible(tickets):
    """The high-conviction subset of the scout's tickets, per lens."""
    out = []
    for t in (tickets.get("breakout") or []):
        if t.get("range_pos", 0) >= BRK_RANGE and t.get("vol_m", 0) >= BRK_VOL_M:
            out.append(("breakout", t))
    for t in (tickets.get("dip") or []):
        if t.get("range_pos", 1) <= DIP_RANGE:
            out.append(("dip", t))
    for t in (tickets.get("momentum") or []):
        if t.get("chg_pct", 0) >= MOMO_CHG and t.get("vol_m", 0) >= MOMO_VOL_M:
            out.append(("momentum", t))
    for t in (tickets.get("divergence") or []):
        if (abs(t.get("gap_pct") or 0) >= DIV_GAP_PP
                and (DIV_VOL_M <= 0 or t.get("vol_m", 0) >= DIV_VOL_M)):
            out.append(("divergence", t))
    return out


def live_boot_gate(rails, live):
    """The BOOT half of the rails for a RUN-ONCE live arm. Returns a refusal
    string, or None to proceed. Pure — unit-tested in selftest().

    THE RULE, and why it differs from every daemon in this fleet: the cap is a
    hard boot gate; the KILL SWITCH IS NOT — it must be allowed to reach
    _flatten_all() + halt in main().

    venues/safety.py promises both halves ("refuses to start — and
    flattens+halts mid-run"), and for a daemon both hold: the funding bot is
    already looping when the switch is armed, so kill_check() fires and closes
    the book. This bot is run-once — EVERY CYCLE IS A BOOT — so
    assert_can_start() would raise before kill_check() is ever reached, and the
    flatten would be unreachable dead code. Arming REAL_MONEY_KILL would stop
    the position manager and STRAND the book: no stop, no max-hold, nothing
    watching it. The switch meant to protect the money would be what abandons
    it. That is not hypothetical — it is the shape of Tide Rider's live row
    right now (kill armed, boot refused, a position left for the operator to
    close by hand).

    So the kill switch still stops ALL trading on the first cycle (main() halts
    and takes no entries) — it now closes the book on the way out.
    """
    if live and rails.max_notional is None:
        return ("lighter_live requires an explicit per-bot notional cap "
                "(LIGHTER_TICKET_TAKER_MAX_NOTIONAL) — refusing to start.")
    return None


def delist_due(no_mark_since_iso, t_now, giveup_h=None):
    """True when a mark has been continuously missing since the given stamp
    for >= giveup_h. Unparseable stamp -> False (the caller re-stamps)."""
    try:
        gone_h = (t_now - parse_ts(no_mark_since_iso)).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return False
    return gone_h >= (DELIST_GIVEUP_H if giveup_h is None else giveup_h)


def exit_reason(entry, mark, opened, t_now, is_long=True, bars=None,
                peak_ret=None, trail=None):
    """tp / sl / hold / trail / None for a position held from `opened`.

    `bars` is an optional (tp, sl, max_hold_h) tuple — the position's OWN
    governing bars (see pos_bars). None = the module's current bars, the
    pre-(by) behavior every existing caller keeps.

    [2026-07-24] `peak_ret` = the best FAVOURABLE return reached since entry
    (the caller tracks it across cycles). When TRAIL_PCT>0 AND peak_ret is
    supplied, the position runs a TREND exit — trail TRAIL_PCT off the peak once
    it is in profit, plus the (deliberately WIDE for a trend book) hard `sl` and
    max-hold, and NO fixed TP so the trend can run. Default (TRAIL_PCT=0 or
    peak_ret=None) = the fixed bracket, byte-for-byte unchanged for every caller
    that does not opt in. Restrict-safe: an unknown peak never trails."""
    if not entry or entry <= 0 or not mark or mark <= 0:
        return None
    tp, sl, hold_h = bars if bars else (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H)
    ret = (mark / entry - 1.0) * (1.0 if is_long else -1.0)
    _trail = TRAIL_PCT if trail is None else trail   # per-lens/per-call override
    if _trail > 0 and peak_ret is not None:
        # TREND mode: give back _trail from a peak that is in profit -> bank the
        # trend; else the wide hard stop; else max-hold. No TP cap.
        if peak_ret > 0 and ret <= peak_ret - _trail:
            return "trail"
        if ret <= sl:
            return "sl"
        if (t_now - opened).total_seconds() >= hold_h * 3600:
            return "hold"
        return None
    if ret >= tp:
        return "tp"
    if ret <= sl:
        return "sl"
    if (t_now - opened).total_seconds() >= hold_h * 3600:
        return "hold"
    return None


# [2026-07-22 LEVER FLAP FIX — operator: "implement the flap to all those who
# need it"] The (bw) taker-SL study measured the defect this closes: 9/22 SL
# closes were "already past the close-time bar" because a WIDER lever (sl
# -0.04) EXPIRED mid-position and the snapped-back default (-0.03) booked the
# whole gap instantly (delays up to 58m). The rule now: THE BARS PRICED AT
# ENTRY GOVERN THE TRADE. Entries stamp the bars in force into position meta;
# exits check the stamp, so a lever expiry can only change the bars of NEW
# positions. This also makes the runtime match every instrument that already
# assumes per-trade constant bars (replay sweep, judge receipts,
# proprioception counterfactuals). Entry GATES (dip/brk/momo/div) still read
# live levers — a crouch still bites new entries immediately; and the
# post-close SL_COOLDOWN_H deliberately stays close-time (it is close-side
# policy, not a bar the position was priced at). Stamps are written even with
# the switch off (attribution is free); LEVER_GRANDFATHER=off reverts the
# BEHAVIOR to close-time bars.
LEVER_GRANDFATHER = os.environ.get("LEVER_GRANDFATHER", "on").strip().lower() \
    not in ("off", "0", "no", "false", "disabled")


def entry_bars():
    """The bars in force RIGHT NOW, stamped into a new position's meta —
    exit bars (governing) plus the entry filters that admitted it
    (attribution; the filters never re-apply mid-position)."""
    return {"tp": TAKE_PROFIT, "sl": STOP_LOSS, "max_hold_h": MAX_HOLD_H,
            "div_gap_pp": DIV_GAP_PP, "div_vol_m": DIV_VOL_M,
            "dip_range": DIP_RANGE, "brk_range": BRK_RANGE,
            "momo_chg": MOMO_CHG}


def pos_bars(m):
    """(tp, sl, max_hold_h) GOVERNING an open position: its entry stamp when
    grandfathering is on and the stamp is sane, else the module's current
    bars. Fail-safe: an unstamped/legacy/junk position behaves exactly as
    before this fix."""
    try:
        if LEVER_GRANDFATHER:
            b = (m or {}).get("bars") or {}
            tp = float(b["tp"])
            sl = float(b["sl"])
            hold_h = float(b["max_hold_h"])
            if sl < 0.0 < tp and hold_h > 0.0:
                return tp, sl, hold_h
    except (KeyError, TypeError, ValueError):
        pass
    return TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H


def _close_fill_extra(out, measured, fill_reason):
    """[2026-07-30 (hb)] Stamp whether the exit price was a MEASURED fill or the
    decision mark, on the LEDGER row.

    `_book_close` already receives `measured`/`fill_reason` and already routes
    them to the venue-order row — but the CLOSE row got only `_close_extra(m)`,
    and `golive_readiness`, the brain and the judge all read
    `fetch_paper_trades`. `raw.measured` lives on `venue_orders` and no grading
    consumer joins that table, so every grading layer has been unable to tell a
    measured round trip from an assumed one.

    That is sharper here than on the Farmer: this book sets `fee_rate = 0.0` for
    the live arm on the stated premise that "its spread is inside the real fill"
    — the exact premise `venues/fills.py` measured false ("0 of 81 live orders
    ever produced a measured fill"). So a live row can carry zero fee AND zero
    spread. This change does NOT touch `fee_rate`: it makes the premise
    CHECKABLE first, because deciding what the fee should be needs to start from
    how many closes were actually measured. TELEMETRY ONLY.

    setdefault-shaped so it can never clobber a bars/evidence key, and ABSENT
    when unknown rather than defaulted to False — the shadow arm has no venue
    fill and must not be recorded as an unmeasured live one.
    """
    if not isinstance(out, dict):
        out = {}
    if measured is not None:
        out.setdefault("exit_measured", bool(measured))
    if fill_reason:
        out.setdefault("exit_fill_src", str(fill_reason))
    return out


def _close_extra(m):
    """The close row's extra: the governing bars stamp PLUS the entry-time
    evidence. Pure — selftested.

    [2026-07-28 REVIEW] (di) captures brk_quality/up_strength into
    meta["evidence"] precisely so winning-breakout criteria can be DERIVED
    from realized closes — but the capture stopped at meta, so
    analyze_breakout_quality.py's `extra ? 'brk_quality'` matched ZERO rows
    on any build and the first 6 breakoutup closes shipped without their
    features (unrecoverable from the ledger). Evidence keys merge with
    setdefault so bars/bars_basis can never be clobbered; non-dict/absent
    evidence degrades to exactly the old payload. Observable-only."""
    m = m or {}
    stamped = isinstance(m.get("bars"), dict) and m.get("bars")
    out = {"bars": (m.get("bars") if stamped else entry_bars()),
           "bars_basis": ("entry" if stamped else "close-legacy")}
    # [2026-08-20 (sk)] the trend exit's own receipts ride the close row. See
    # the tracking site in main() for why MAXIMUM rather than final. Absent on
    # a position that never saw a mark (a legacy row, or one closed on its
    # first cycle), and absent is UNKNOWN — a grader must not read a missing
    # give_back as zero, which is why these are omitted rather than defaulted.
    for _k in ("peak_ret", "give_back", "mae_ret", "brain_mult"):
        _v = m.get(_k)
        if isinstance(_v, (int, float)) and not isinstance(_v, bool):
            out[_k] = round(float(_v), 6)
    # [2026-07-29 (fx) POLICY STAMP] The bars stamp records the EXIT bracket.
    # It says nothing about which SIGNALS the bot was allowed to take — and
    # that is the field whose absence caused three separate mis-gradings in one
    # day. TT_BULL_MODE flipping on 24-Jul changed the lens set, the side and
    # the crypto-only rule while leaving the bracket byte-identical, so the
    # ledger's ONLY trace of a policy change was the `reason` tag flipping from
    # long-divergence_* to short-divergence_* — a downstream symptom a grader
    # has to already know to look for. Pooling across it produced BOTH
    # "n=25, t=-0.26, no edge" (fs) and the over-corrected "pooled t=+2.86,
    # the edge is real" (fv). Two opposite errors, one missing field.
    # With this, any grader — golive_readiness, bot_learn, the experiment
    # judge, fleet_proprioception or a human — can split eras MECHANICALLY.
    # Observable-only: it changes no decision, and setdefault means it can
    # never clobber bars/bars_basis or an evidence key.
    # [2026-07-30] TICKET SUPPLY joins the stamp, and it belongs here for the
    # same reason everything else does. (fx)/(gi) fixed era-pooling by
    # recording the policy the taker ran — but the taker's CANDIDATE SET is set
    # one level further up, by the scout's `TICKET_TOP_N`, and that moved 6 -> 12
    # on 2026-07-30. A grader splitting eras "MECHANICALLY" would have pooled
    # across a 2x change in the supply the arm chose from, with nothing in the
    # ledger to see it by — the identical defect, one level upstream. Read from
    # the lever registry so the stamp follows the real value rather than a
    # second copy of it (the `env_default` field (gd) added is what makes that
    # possible). Observable-only; setdefault still protects every other key.
    _supply = None
    try:
        if tuning is not None:
            _spec = (tuning.LEVERS.get("scout.ticket_top_n") or {})
            _supply = tuning.get_lever("scout.ticket_top_n",
                                       _spec.get("env_default"))
    except Exception:  # noqa: BLE001
        _supply = None
    # [(lj)] the signature half comes from `current_policy()` — the SAME
    # builder the realised veto's era filter compares against, so the stamp
    # and the filter cannot drift. Capacity levers ride beside it, outside
    # the signature ((hc): ordinary tuning must not reset an era).
    out.setdefault("policy", dict(current_policy(),
                                  max_open=MAX_OPEN,
                                  ticket_top_n=_supply))
    ev = m.get("evidence")
    if isinstance(ev, dict):
        for k, v in ev.items():
            out.setdefault(k, v)
    return out


# ---------------------------------------------------------------------------


def _setup_logging(_ctx=None):
    """[2026-07-17] Make the venue layer AUDIBLE. This bot configured NO logging,
    and Python drops `log.info` when the root logger has no handler — so the LIVE
    taker has been running BLIND to `venues/`: no signer banner (and therefore no
    lighter-sdk version), no EQUITY GUARD REJECTs, no governor 429/punish, no
    ws-degraded. Only WARNING+ ever surfaced, via the handler of last resort,
    which is exactly why `Unclosed client session` was visible and nothing else
    was. The funding bot configures logging and printed its signer's wheel on the
    first boot after the banner shipped; this bot could not, and that asymmetry
    is what exposed the hole.

    INSIDE main(), never at import. FOUR modules import this file
    (lighter_ticket_replay, lighter_scout_tuner, strategy_incubator,
    fleet_proprioception) and NONE configure logging — an import-time
    basicConfig would silently hijack the root logger for all of them inside the
    shared freqtrade-bots container. Same reason the TT_VENUE gate lives here.

    Idempotent by construction: basicConfig is a no-op when the root already has
    handlers, so a caller that configured its own logging keeps it. `_ctx` is the
    offline test path — left alone so the selftests' captured stdout stays clean.
    """
    if _ctx is not None:
        return
    logging.basicConfig(
        level=os.environ.get("TT_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout)


def main(_ctx=None):
    """One management cycle.

    `_ctx` is a TEST-ONLY injection point ({venue, rails, broker}); production
    calls main() with no args. It bypasses the EVIDENCE refusal below so the
    live order path can be driven end-to-end offline (--selftest-live). It does
    NOT bypass SafetyRails: the kill switch and the notional cap stay senior on
    every path, so an injected REAL client still cannot send an order without a
    deliberate REAL_MONEY_KILL=DISARMED_I_UNDERSTAND and an explicit cap. The
    evidence gate and the money gate are different gates — this opens neither
    for production, and only the first for a test.
    """
    # [2026-07-17 TT_VENUE MUST BE EXPLICIT — real money] This bot's identity,
    # its dashboard row, and whether it trades REAL MONEY all come from
    # $TT_VENUE, and it has no default it can safely inherit: the shadow id is
    # the row the freqtrade-bots container already publishes, so a lost var on
    # the live service would make TWO writers of one row while the live book's
    # positions went unmanaged — no page, because the row looks healthy. Same
    # class as the 17-Jul VENUE fix on the other two live bots; both services
    # set it explicitly, so this is inert for them and only makes a lost var
    # LOUD. Gated INSIDE main() on purpose: four modules import this one
    # (lighter_ticket_replay, lighter_scout_tuner, strategy_incubator,
    # fleet_proprioception) and an import-time guard would break every one.
    # _ctx is the offline test path and never trades.
    if _ctx is None and not os.environ.get("TT_VENUE", "").strip():
        raise SystemExit(
            "TT_VENUE is unset. This bot's identity — and whether it trades "
            "REAL MONEY — comes from it, and its lighter_shadow id is a row "
            "another service already publishes. An inherited default must never "
            "decide that. Set TT_VENUE=lighter_live or TT_VENUE=lighter_shadow "
            "explicitly.")
    _setup_logging(_ctx)
    # [2026-08-04] ONE BOOK, ONE WRITER — claimed at the TOP of the cycle,
    # before any read, lever or trading act. The TT_VENUE guard directly above
    # names the exact two-writer scenario this closes: "a lost var on the live
    # service would make TWO writers of one row while the live book's
    # positions went unmanaged — no page, because the row looks healthy."
    # That guard catches the UNSET var; this claim catches every other route
    # to two processes on one row (a mis-set var, a duplicate service, an
    # operator `railway up` racing the workflow — the carry book lost 25.6h
    # and its ledger's integrity to exactly this class, (hf)/(hp)).
    # funding_carry_bot's hardened (hp)/(ib)/(ic)/(id) pattern, adapted to a
    # RUN-ONCE process: `return` skips the cycle (the ~300s shell loop is the
    # wait — no sleep, and never sys.exit/SystemExit: a raise here would read
    # as a crash and mark the row error over a book another process owns).
    # claim_writer is FAIL-OPEN (a dark DB never idles the book) and a
    # redeploy is NOT a duplicate (`_claim_is_my_own_dead_replica` — same svc,
    # new replica id — or every deploy would idle the book for the full
    # 30-min TTL, the (id) stall).
    _ok_writer, _other_writer = store.claim_writer(BOT_ROW)
    if not _ok_writer:
        print(f"[ticket-taker] {iso(now())} STANDING DOWN — {BOT_ROW} is "
              f"already claimed by another container ({_other_writer}). Two "
              f"writers make `n` a mixture of two books and, on the live arm, "
              f"two managers of one real account. Skipping this cycle; the "
              f"claim expires in <= {store.WRITER_CLAIM_TTL}s if the "
              f"incumbent stops.", flush=True)
        try:
            # The loser reports on its OWN key ((ic)): no publish, no
            # heartbeat, no bot_pnl row. `caps` identifies WHICH build is
            # standing down — a standby record without it is
            # indistinguishable from a stale one.
            store.save_state(_standby_key(BOT_ROW), {
                "standing_down": True,
                "book": BOT_ROW,
                "duplicate_writer": _other_writer,
                "svc": store.service_name() or None,
                "venue": TT_VENUE,
                "caps": {"max_open": MAX_OPEN, "clip_usd": CLIP_USD},
                "updated": iso(now()),
                "ttl_sec": store.WRITER_CLAIM_TTL,
            })
        except Exception:  # noqa: BLE001
            pass
        return
    moved = apply_tuning()
    if moved:
        print(f"[ticket-taker] {iso(now())} growth-rail levers active: {moved}")
    try:
        marks, funding, ranges = fetch_marks_and_funding()
    except Exception as e:  # noqa: BLE001 — keyless API down: skip this cycle
        # [2026-07-17] liveness touch on the skip path (the funding bot's
        # 12-Jul GO-GREEN rule, ported): this `return` published NOTHING, so a
        # keyless-API blip made the row go STALE — indistinguishable from a
        # dead bot. A skip is not a death; say so.
        print(f"[ticket-taker] {iso(now())} fetch failed (skipping): {e!r}")
        try:
            store.heartbeat(BOT_ROW)
        except Exception:  # noqa: BLE001
            pass
        return

    if TT_VENUE not in TT_MODES:
        raise SystemExit(f"TT_VENUE={TT_VENUE!r} unknown (expected {TT_MODES})")
    # [2026-07-17 LIVE REFUSAL LIFTED — operator decision, on the record.]
    # The refusal that stood here said: "divergence is the only fillable lens
    # and it has n=7 closes; the fleet's gate is a 30-day record. Lift it when
    # divergence has the closes — NOT to fill a vacancy." The operator was shown
    # that reasoning with the numbers and lifted it deliberately, to take Tide
    # Rider's vacated live slot. Recording what was traded away, because nobody
    # should have to re-derive it later:
    #   * THE EVIDENCE IS THIN AND KNOWN THIN. divergence's episode-deduped
    #     forward grade is +0.004%/4h (≈zero) with an ehit4h CI of 0.494-0.572
    #     STRADDLING a coin flip, while this bot's median divergence hold is
    #     6.68h. Its realized +4.23%/trade is 5-1000x the brain's forward grade
    #     of the SAME signal at n=2934 — that gap is the luck. $10.72 over 7
    #     fills is ~3 fills of swing, at 100% WR: a streak, not a record.
    #   * The fleet gate (30d WR>55% AND maxDD<15%) is NOT met. This is a
    #     deliberate exception to it, not a pass.
    #   * long-divergence has ZERO realized fills and the live arm can take it.
    # What replaced the refusal is not permission — it is guards, all landed and
    # negative-fixture tested: a fail-CLOSED live lens allow-list that does not
    # read the brain (allowed_lenses), a hard assert at the order, the symbol
    # round-trip fix, None-is-a-failed-close, TT_VENUE mandatory, apply_tuning
    # disabled live, plus the pre-existing kill switch / notional cap / equity
    # guard / daily-loss rail. REAL_MONEY_KILL is still the last gate and it is
    # the OPERATOR's to disarm.
    live = (TT_VENUE == "lighter_live")
    dry_run = not live

    t_now = now()
    venue = rails = broker = None
    if _ctx is not None:
        venue, rails, broker = _ctx["venue"], _ctx["rails"], _ctx["broker"]
    elif TT_VENUE == "lighter_paper":
        # legacy: models its own fills at a flat fee. Kept for curve continuity.
        broker = PaperBroker(start_equity=START_EQUITY, fee_bps=4.0)
    else:
        # REAL fills: ShadowBroker walks the live Lighter book at our clip and
        # writes every order to venue_orders (decision px vs modelled fill px,
        # spread + slippage). Lighter's perp fee is ZERO — the crossed spread
        # IS the cost, and it lands in the fill price rather than a flat 4bps
        # guess. This is the arm whose record can support a go-live.
        from venues.lighter_client import LighterClient
        from venues.shadow import ShadowBroker
        from venues.safety import SafetyRails
        # [2026-07-17 LIVE PATH] the signer is what separates a modelled fill
        # from a real one. shadow -> no signer, ShadowBroker walks the book;
        # live -> signer + market_open/market_close against the venue, and
        # SafetyRails demands an explicit notional cap or refuses to start.
        #
        # guard_state_key is LIVE-ONLY and load-bearing: LighterClient only
        # builds an EquityGuard when it has a signer, and vet_account_read()
        # returns the raw print unvetted when the guard is None. Omitting it
        # would have run the live arm's daily-loss rail on UNVETTED equity —
        # the exact 11-Jul failure where one dislocated print tripped the rail
        # and the flatten sold into the dislocation for a real -5.9%. The
        # funding bot gets this via venue_context(); this bot builds its client
        # directly, so it must pass it explicitly.
        venue = LighterClient(
            net="mainnet", with_signer=live,
            guard_state_key=(BOT_ROW + ":eqguard") if live else None,
            # RUN-ONCE (this file re-invokes main() every ~300s via
            # tickettaker_loop.sh / run_all.sh), so the EquityGuard must PERSIST
            # its reject streak across relaunches or the deposit-heal rebase can
            # never reach its consecutive-reject count. The long-lived Funding
            # Farmer leaves this False (keeps its redeploy streak-reset).
            guard_persist_reject_streak=live)
        rails = SafetyRails(BOT, TT_VENUE)
        # [2026-07-17 RUN-ONCE KILL SEMANTICS — deliberately NOT
        # assert_can_start() on the live arm.]
        # safety.py promises BOTH halves: lighter_live "refuses to start — and
        # flattens+halts mid-run". For a DAEMON both work: the funding bot is
        # already looping, so kill_check() fires and _flatten_all() closes the
        # book. This bot is RUN-ONCE (run_all.sh / the live loop re-invokes it
        # every 5 min), so EVERY CYCLE IS A BOOT — assert_can_start() would
        # raise SystemExit before kill_check() is ever reached, making the
        # flatten below unreachable dead code. Arming REAL_MONEY_KILL would
        # then STOP the position manager and STRAND whatever it holds, with no
        # stop and no max-hold: the switch meant to protect the money would be
        # the thing that abandons it. (That is not theoretical — it is exactly
        # the shape of Tide Rider's live row today: kill armed, boot refused,
        # a position left behind for the operator to close by hand.)
        # So: keep the CAP half as a hard boot gate, and let the kill switch
        # reach _flatten_all() + halt below. The kill switch still stops all
        # trading on the very first cycle; it now closes the book on the way.
        _refusal = live_boot_gate(rails, live)
        if _refusal:
            store.set_status(BOT_ROW, "error")
            raise SystemExit(_refusal)
        if not live:
            rails.assert_can_start()
        broker = None if live else ShadowBroker(BOT_ROW, venue, START_EQUITY)

    # State: the paper/shadow arms own a local ACCOUNT (broker snapshot); the
    # live arm's account lives on the venue and it persists only what it may
    # legitimately remember — the P&L baseline, the day-start equity and
    # per-position meta (max-hold clock, entry clip, lens).
    if dry_run:
        # [2026-08-05 SEED GUARD] the SHADOW arm gets the live arm's
        # 17-Jul treatment (below) — it had the unchecked read the whole
        # time: a run-once bot re-boots every ~300s cycle, so one Postgres
        # blip seeded a fresh $1000 book over the graded shadow record and
        # the save at cycle end made it durable. Refuse the cycle; the loop
        # retries in ~300s.
        _ok_sh, saved = store.load_state_checked(STATE_KEY)
        if not _ok_sh:
            print(f"[ticket-taker] {iso(now())} shadow state read FAILED — "
                  f"skipping this cycle rather than seed a fresh book over "
                  f"the graded record", flush=True)
            return
        saved = saved or {}
        broker.restore_state(saved.get("broker") or {})
        live_baseline = None
    else:
        # [2026-07-17 AUDIT] load_state_CHECKED on the live arm. `load_state`
        # collapses "no row" and "READ FAILED" into None (bot_pnl_store.py:409
        # — its sibling's docstring calls this "a trap for any caller that
        # SEEDS durable state on an empty read"), and `or {}` then made meta={}
        # -> EVERY live position unattributable -> the dirty-account guard
        # below fired on a bot whose account was perfectly clean. One Postgres
        # blip therefore stopped the exit ladder on REAL positions while
        # telling the operator to go hunt a foreign position that never
        # existed. A read we could not perform is NOT evidence of an empty
        # account; refuse the cycle and let the 300s loop retry, rather than
        # act on a fact we do not have.
        _ok, _saved = store.load_state_checked(LIVE_STATE_KEY)
        if not _ok:
            store.set_status(BOT_ROW, "error")
            raise SystemExit(
                "lighter-ticket-taker: live state READ FAILED — cannot tell "
                "an empty account from an unreadable one, so this cycle does "
                "nothing rather than guess. Positions (if any) keep their "
                "venue-side state; the next cycle retries in ~300s. This is a "
                "TRANSIENT database condition, NOT a dirty account — do not "
                "reconcile meta on the strength of this message. If it "
                "persists, the DB is down: REAL_MONEY_KILL=DISARMED_I_UNDERSTAND "
                "still flattens (the kill switch runs above this).")
        saved = _saved or {}
        live_baseline = saved.get("initial_equity")
    # [2026-07-21 D1] persisted capital ledger — deposits the guard accepted;
    # pnl_abs subtracts it (+ the CAPITAL_ADJUST_USD backfill) so the
    # operator's own money never prints as trading profit. {} for dry_run.
    capital_adjust = (saved.get("capital_adjust") if live else None) \
        or {"total": 0.0, "events": []}
    meta = saved.get("meta") or {}          # sym -> {lens, opened, accrued_to}
    stats = saved.get("stats") or {"closed": 0, "wins": 0, "losses": 0}
    # [2026-07-21 AUDIT FIX] post-STOP re-entry cooldown: closes run before
    # entries each cycle and the only re-entry guard was 'sym in pos', so a
    # symbol whose stop-loss just fired was IMMEDIATELY eligible while the
    # scout's ticket still stood — measured churn on the shadow tape: NBIS
    # SL'd and re-opened in the SAME minute, 8 closes -$5.37; BOT 3 closes
    # -$4.60; every same-cycle re-entry lost. A stopped symbol now waits
    # TT_SL_COOLDOWN_H (persisted, both arms; tp/hold closes unaffected —
    # winners may re-enter freely).
    sl_block = {s: t for s, t in (saved.get("sl_block") or {}).items()
                if _sl_active(t, t_now)}
    # ShadowBroker's cost is the CROSSED SPREAD, already inside the fill price
    # (fee_bps=0 — Lighter charges no perp fee). Charging a flat fee on top
    # would double-count it; the legacy paper arm still models one. LIVE pays
    # the venue's real fee (zero) and its spread is inside the real fill, so
    # its modelled fee is zero for the same reason the shadow arm's is.
    fee_rate = broker.fee if dry_run else 0.0

    def _fold_capital_moves():
        """[2026-07-21 D1] Fold guard-detected deposits/withdrawals into the
        persisted capital ledger (fail-safe: no guard / no moves -> no-op).
        Run-once process: the same run that heals a deposit folds it, and the
        loop-bottom save_state persists it.

        [2026-07-23] Returns the NET $ folded this call (0.0 if none). The caller
        shifts the daily-loss rail's day_start by the same amount so a capital
        move lands in BOTH the equity read and the rail baseline. Otherwise a
        deposit MASKS a real drawdown (raw equity rises, day_start doesn't -> the
        rail can't fire) and a withdrawal FABRICATES a halt (raw equity falls,
        day_start doesn't -> the rail flattens on the operator's own cash-out).
        The leash is NET of deposits/withdrawals (operator, 2026-07-23). This
        ledger stays DISPLAY-only — no rail reads it; the caller reads the
        return value."""
        if not live:
            return 0.0
        _net = 0.0
        for _mv in getattr(venue, "pop_capital_moves", lambda: [])():
            capital_adjust["total"] = round(capital_adjust["total"] + _mv["delta"], 2)
            capital_adjust["events"] = (capital_adjust.get("events") or [])[-19:] + [_mv]
            _net += _mv["delta"]
            print(f"[ticket-taker] capital ledger: ${_mv['delta']:+.2f} "
                  f"({_mv['how']}) -> lifetime ${capital_adjust['total']:+.2f} "
                  f"(+${CAPITAL_ADJUST_USD:.2f} env backfill) — P&L baseline "
                  f"absorbed it.", flush=True)
        return round(_net, 2)

    def account_value():
        """Equity. dry_run: the local broker. live: the VENUE, vetted by the
        EquityGuard (raises VenueError on a dislocated print)."""
        return broker.equity() if dry_run else venue.account_value()

    def positions():
        """{sym: {size, entry}} — the funding bot's shape. In LIVE the account
        is the source of truth, never our memory (the 11-Jul ghost-position
        lesson: a redeploy wiped an in-memory halt and the bot re-bought 37s
        after boot)."""
        if dry_run:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        # [2026-07-17 SYMBOL SPACE — live-only, and it fires on the FIRST ticket]
        # This bot keys marks/funding/ranges/meta by the VENUE-NATIVE symbol from
        # its own orderBookDetails fetch ("1000BONK"). LighterClient.positions()
        # runs every symbol through from_lighter() and returns FLEET symbols
        # ("kBONK"). Unremapped, the live arm looks up "1000BONK" in a dict keyed
        # "kBONK", sees itself FLAT, and RE-OPENS the same position every cycle;
        # meanwhile the exit pass never examines the real one, so it runs with no
        # stop and no max-hold. MEASURED: 1000BONK is a divergence ticket right
        # now (short, gap 87.5pp) — the first thing a divergence-only arm touches.
        # Remap at THIS boundary rather than normalising the bot into fleet space:
        # meta and the broker snapshot are PERSISTED in the venue-native keys, so
        # changing the bot's key space would strand every open position on the
        # shadow arm. One space, converted where the two meet.
        # (to_lighter() mirrors from_lighter() as of today, so the trip closes for
        # all six 1000-markets — verified against all 218 live markets.)
        return {to_lighter(c)[0]: v for c, v in (venue.positions() or {}).items()}

    def _real_fill(sym, is_ask, fallback, leg, client_id=None,
                   tx_hash=None, settle_ms=None):
        """REAL fill price from the venue's own trade tape as (price, measured,
        reason). is_ask=True when WE sold (opening a SHORT / closing a LONG).
        `price` is the decision price when `measured` is False, so every caller
        can keep using it as a price — but only `measured` may be read as
        evidence.

        Extends lighter_funding_bot._real_exit to the OPEN leg too: that bot
        echoes the decision price on opens, which is the same unmeasurable-fill
        shape its own 17-Jul telemetry fix called out on closes. Entries here
        are rare (<=4/cycle), so the extra governed read is cheap and it makes
        this arm's execution measurable on BOTH legs — which is the entire
        reason a live arm exists before a go-live.

        [2026-07-17] RETURNS `measured` INSTEAD OF LETTING THE CALLER INFER IT.
        The old contract said "price == decision means we got no read". MEASURED
        false the same night: 1000BONK's REAL fill was 0.003275 and the decision
        price was 0.003275 — a genuinely perfect fill, identical to the mark,
        which the inference threw away as "unmeasured". Only THIS function knows
        whether the tape answered; inferring it from the number is a guess.

        [2026-07-17b] TWO DEFECTS FIXED, both by delegating to venues.fills:

        (1) THE ID FILTER WAS A CLIFF. `_our_fills` HARD-filters on the client id
            (lighter_client.py:624-629 `continue`s on a mismatch, no fallback),
            so the moment Lighter stopped echoing `client_order_index` — or any
            call site handed us a dict without the key — this read went from
            approximate to NOTHING (`no-match:both`), silently. Threading the id
            made the read exact on the happy path and strictly WORSE than the old
            heuristic on the unhappy one. `read_fill` retries once without the id
            on a no-match, so a venue that stops echoing costs precision, never
            the measurement. The round trip is still UNPROVEN in production: the
            only two live orders (STRC + 1000BONK, 17-Jul 09:08/09:13Z) predate
            the fill-read code by an hour, so no venue_orders row has ever
            carried `measured` at all. The fallback is what makes that
            uncertainty cost precision instead of the whole reading.

        (2) `measured` WAS HARD-CODED TRUE. This function returned
            `real, True, reason` for any price that came back, ignoring the very
            reason string that says whether the venue NAMED the fill or guessed
            it. An id-less read is labelled `trades(approx)` and is a 180s
            same-side VWAP blend — it would have been recorded as an exact
            measurement. `measured_from_reason` derives the verdict from the
            venue layer's own label, so the two cannot drift.

        Measurement-only: ANY failure falls back to the decision price, so a
        broken read can never block or unwind an order."""
        if dry_run:
            return fallback, False, "dry-run"
        detail = getattr(venue, "last_fill_detail", None)
        if detail is not None:
            px, measured, reason = read_fill(
                detail, sym, is_ask=is_ask, since_ts=time.time() - 180,
                client_id=client_id, tx_hash=tx_hash, settle_ms=settle_ms)
        else:
            # LEGACY venue: no reason channel and no id round trip, so this read
            # can only ever be a (side, since_ts) blend. It is labelled `approx`
            # for that reason — the old code called it `ok` and returned
            # measured=True, claiming an exactness the accessor cannot deliver.
            # Unreachable in production (LighterClient has both methods and the
            # shadow arm returns above), kept so a venue without the detail API
            # degrades to the heuristic rather than to nothing — the same cliff
            # as (1), one layer up.
            try:
                _lf = getattr(venue, "last_fill", None)
                px = (_lf(sym, is_ask=is_ask, since_ts=time.time() - 180)
                      if _lf else None)
                reason = ("last_fill(approx:no-detail-api)" if px
                          else "no-venue-method")
            except Exception as e:  # noqa: BLE001 — telemetry never breaks money
                px, reason = None, f"caller-error:{type(e).__name__}"
            measured = measured_from_reason(px, reason)
        if px is not None:
            print(f"[ticket-taker] {sym} {leg} fill (venue): {px:.6g} "
                  f"(decision {fallback:.6g}) via {reason}"
                  f"{'' if measured else ' — NOT measured, slippage NULL'}")
            return px, measured, reason
        # NOT a crash and NOT zero slippage — an UNMEASURED leg. Say so, loudly
        # enough that 57 orders can never again go by without anyone noticing.
        print(f"[ticket-taker] {sym} {leg} fill UNMEASURED — {reason} "
              f"(recording decision {fallback:.6g}, slippage NULL)")
        return fallback, False, reason

    # [2026-07-17] SHARED with the live Funding Farmer (venues/fills.py). The
    # local copy's `measured=None -> infer d == f` back-compat is gone: both
    # call sites below pass `measured` explicitly (they get it from _real_fill,
    # which is the only thing that knows), so the inference was dead code that
    # existed only to be gotten wrong later. The shared rule is the STRICTER of
    # the two copies — an unmeasured leg is NULL even when d != f, which is this
    # bot's rule winning over the Farmer's. See venues/fills.py for why that
    # direction: the id-miss fallback is the first read that can hand us a real
    # price we did NOT measure, and implementation_shortfall AVGs this column
    # without ever reading `measured`.
    _slip_bps_of = slip_bps_of

    def _book_close(sym, m, size, entry, exit_px, pnl, reason, decision_px=None,
                    measured=None, fill_reason=None):
        """Ledger + counters + meta pop for ONE close. Shared by the exit pass
        and _flatten_all so an emergency flatten reconstructs identically to a
        normal close (the funding bot's rule: forensics must stay consistent
        with account equity).

        `measured`/`fill_reason` carry _real_fill's verdict so the order row can
        record a MEASURED zero as zero, and name the cause when it measured
        nothing. Default None = "caller doesn't know" = the old inference."""
        is_long = size > 0
        drag = float(m.get("funding_paid") or 0.0)   # signed: shorts credit
        clip_used = float(m.get("clip") or CLIP_USD)
        fees = 2 * clip_used * fee_rate
        net = pnl - drag - fees
        stats["closed"] += 1
        stats["wins" if net > 0 else "losses"] += 1
        # [2026-07-30 (hm)] THE BASIS INVARIANT. A `_tp` cannot book a LOSS,
        # and an `_sl` cannot book a PROFIT, beyond funding and fees. Both
        # would be contradictions — and 39 of this book's 70 short-divergence
        # `_tp` rows were exactly that, undetected for nine days.
        #
        # THE MECHANISM, measured: `exit_reason(entry, mark)` is handed
        # `entry` = the ShadowBroker's book-WALKED fill while `mark` = the
        # venue's `mark_price`, and the P&L is then booked by re-walking the
        # real book. On BOT/USDC the mark sat ~7.4% BELOW its own book top
        # (mean |px_fill/px_decision - 1| = 747.6 bps over 93 orders, against
        # a ~9 bps ledger median), so a short opened at the book fill was born
        # ~+7.5% in profit ON THE MARK BASIS, tripped tp on the very next
        # 5-minute cycle, and closed by crossing an 81.9 bps spread for ~-0.7%.
        # `pos.pop()` then freed the slot and `SL_COOLDOWN_H` only gates
        # re-entry after an `sl`, so it re-entered every loop: 43 closes in
        # 4.5 hours, 42 of 43 with close[i] == open[i+1] TO THE SECOND. One
        # episode, not 43 trades, and -$6.16.
        #
        # This is a DETECTOR, not a gate: it never blocks a close (the trade
        # already happened and the ledger row must be written) — it stamps the
        # row and shouts, so the next occurrence is visible on the day it
        # happens rather than nine days later in an audit. The proactive half
        # is the basis check at the ORDER site below.
        _contradiction = None
        if reason == "tp" and net < -abs(drag) - fees - 1e-9:
            _contradiction = "tp_booked_a_loss"
        elif reason == "sl" and net > abs(drag) + fees + 1e-9:
            _contradiction = "sl_booked_a_profit"
        if _contradiction:
            print(f"[ticket-taker] {iso(t_now)} LEDGER CONTRADICTION on {sym}: "
                  f"{_contradiction} — reason={reason!r} net={net:+.4f} "
                  f"pnl={pnl:+.4f} drag={drag:+.4f} fees={fees:.4f} "
                  f"entry={entry} exit={exit_px}. The exit rule and the P&L are "
                  f"reading DIFFERENT PRICE BASES; this row is not gradeable.",
                  flush=True)
        lens = m.get("lens") or "ticket"
        side = "long" if is_long else "short"
        # tag format <side>-<lens>_<exit>: the ledger's reason parser splits
        # on the FIRST underscore, so the brain's enter_tag becomes
        # "long-breakout"/"short-divergence" — per-lens grading, not one
        # blended "long" bucket.
        store.publish_paper_trade(
            BOT_ROW, trade_id=f"{sym}-{m.get('opened')}",
            pnl_abs=round(net, 4),
            pnl_pct=round(net / clip_used, 6),
            pair=f"{sym}/USDC",
            opened_at=m.get("opened"), closed_at=iso(t_now),
            # [2026-08-05 (kf)] `side` is stamped. It was COMPUTED four lines
            # above and dropped — the exact (gr) shape, where 8 of 9 bots held
            # the value in scope and never passed it. `publish_paper_trade` has
            # accepted side= since 17-Jul and 💸 the Farmer stamps it on 71 of
            # 71 priced closes, which is the control group that makes this
            # absence a finding (I6) rather than a venue quirk.
            #
            # THE COST while it was missing: `study_exit_sweep.load_trades`
            # read a missing side as a LONG, so all 15 of the LIVE Taker's
            # priced closes — every one a SHORT — replayed backwards, and a
            # candidate bracket inverted from +0.397% to -0.397%/trade. The
            # harness now SKIPS side-less rows instead of guessing, so without
            # this stamp the book is simply unsweepable; with it, its exits
            # become analysable for the first time.
            side=side,
            reason=f"{side}-{lens}_{reason}",
            # [2026-07-15 AUDIT FIX] provenance: venue + arm on every row —
            # venue NULL claimed the pre-Gate-0 HL-paper era.
            venue="lighter", shadow=dry_run,
            # [2026-07-30 (gr)] EXIT TELEMETRY on the REAL-MONEY taker too. The
            # slippage decomposition already rides `extra` (px_decision/px_fill),
            # but the trade's own entry/exit prices were never columns on the
            # row — so a counterfactual exit sweep could not join a price path
            # to the trade. `entry` and `exit_px` are both parameters of this
            # function; they were simply not passed. Telemetry only.
            entry_price=entry, exit_price=exit_px, size=size,
            # [2026-07-21 ATTRIBUTION; 2026-07-22 FLAP FIX] bars on every
            # close row. Since the flap fix these are the ENTRY-time stamp —
            # the bars that actually GOVERNED the trade (the 21-Jul
            # close-time caveat "a mid-hold lever change stamps the exit's
            # bars" is exactly the contamination the (bw) study had to
            # reconstruct around: 11/22 SL closes ran under a different bar
            # than the one stamped/assumed). Legacy positions opened before
            # the stamp existed fall back to close-time values, labelled so.
            # [2026-07-28 REVIEW] ...and the ENTRY EVIDENCE rides the close
            # row. (di) captured brk_quality/up_strength into meta["evidence"]
            # so the winning-breakout criteria could be DERIVED from closes —
            # but the capture stopped at meta: analyze_breakout_quality.py
            # filters `extra ? 'brk_quality'` and matched ZERO rows forever
            # (the first 6 breakoutup closes' features are unrecoverable).
            # Merge is setdefault-shaped: bars/bars_basis can never be
            # clobbered by an evidence key. Observable-only, both arms.
            extra={**_close_fill_extra(_close_extra(m), measured, fill_reason),
                   # [(hm)] stamped so the corruption is QUERYABLE. Nine days
                   # of BOT/USDC churn were only found by a human eyeballing
                   # exit reasons against P&L signs; a column makes it a WHERE
                   # clause. Absent on a healthy row, so it costs nothing.
                   **({"basis_contradiction": _contradiction}
                      if _contradiction else {})})
        if not dry_run:
            try:
                store.publish_venue_order(
                    BOT_ROW, venue="lighter", shadow=False, coin=sym,
                    side=("sell" if is_long else "buy"), size=abs(size),
                    px_decision=decision_px, px_fill=exit_px,
                    slippage_bps=_slip_bps_of(decision_px, exit_px,
                                              is_buy=not is_long,
                                              measured=measured),
                    # `measured` + `fill_src` make the blind spot QUERYABLE off
                    # the ledger instead of grep-able off a container log that
                    # ages out. 0 of 57 real orders carried a fill; nobody could
                    # ask the database why.
                    raw={"reason": reason, "lens": lens, "leg": "close",
                         "measured": measured, "fill_src": fill_reason})
            except Exception:  # noqa: BLE001
                pass
        print(f"[ticket-taker] {iso(t_now)} CLOSE {side} {sym} ({lens}) {reason} "
              f"pnl {pnl:+.2f} funding {-drag:+.3f} net {net:+.2f}")
        meta.pop(sym, None)

    def _flatten_all(reason):
        """LIVE emergency flatten (kill switch / daily loss). Reads the VENUE,
        not meta — an untracked position still holds real risk and must still
        be closed. Mirrors normal-close bookkeeping via _book_close."""
        try:
            # fleet -> venue-native, same boundary rule as _positions()
            live_pos = {to_lighter(c)[0]: v
                        for c, v in (venue.positions() or {}).items()}
        except Exception as e:  # noqa: BLE001
            print(f"[ticket-taker] {iso(t_now)} flatten scan failed: {e!r}")
            return
        for sym in list(live_pos):
            size = (live_pos.get(sym) or {}).get("size") or 0.0
            if not size:
                continue
            m = meta.get(sym) or {}
            is_long = size > 0
            entry = float((live_pos.get(sym) or {}).get("entry")
                          or m.get("entry") or 0.0)
            px = marks.get(sym) or float(m.get("last_mark") or entry)
            try:
                # [2026-07-17] None == the venue did NOT close it (no position
                # under that key). Treating it as success books a phantom close
                # and pops meta, stranding a REAL position with no exit rule.
                _res = venue.market_close(_fleet(sym))
                if _res is None:
                    print(f"[ticket-taker] {iso(t_now)} flatten {sym}: venue "
                          f"reported NO position to close — leaving meta intact "
                          f"and retrying next cycle (NOT booking a close)")
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"[ticket-taker] {iso(t_now)} flatten {sym}: {e!r}")
                continue
            _dpx = px
            px, _meas, _why = _real_fill(
                sym, is_ask=is_long, fallback=px, leg="exit",
                client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
            pnl = abs(size) * ((px - entry) if is_long else (entry - px))
            _book_close(sym, m, size, entry, px, pnl, reason, decision_px=_dpx,
                        measured=_meas, fill_reason=_why)

    # ---- LIVE RAILS (loop-top order mirrors lighter_funding_bot) -----------
    # This bot is a RUN-ONCE process (run_all.sh loops it every 5 min), so
    # everything the funding bot keeps in memory across its `while True` must
    # be DURABLE here or it resets every cycle: the day-start equity baseline
    # and the halt. A memory-only halt is exactly the 11-Jul incident — the
    # redeploy wiped it and the bot re-bought 37 seconds after boot.
    cur_day = t_now.date().isoformat()
    halted_today = False
    day_start_equity = None
    if live:
        _halt = store.load_daily_halt(BOT_ROW, cur_day)
        if _halt:
            halted_today = True
            day_start_equity = _halt.get("day_start_equity")
            print(f"[ticket-taker] {iso(t_now)} daily-loss halt restored from "
                  f"state — halted for the rest of {cur_day}")
        else:
            _ds = saved.get("day_start") or {}
            if _ds.get("day") == cur_day:
                day_start_equity = _ds.get("equity")

        # kill switch FIRST — checked every cycle, not once at boot.
        if rails.kill_check():
            print(f"[ticket-taker] {iso(t_now)} REAL_MONEY_KILL armed — "
                  f"flatten + halt.")
            halted_today = True
            _flatten_all("kill_switch")

    try:
        equity = account_value()
    except Exception as e:  # noqa: BLE001 — guard rejected, or venue down
        print(f"[ticket-taker] {iso(t_now)} account value unavailable: {e!r}")
        equity = None
    _cap_delta = _fold_capital_moves()   # D1: a deposit accepted on that read is capital

    if live:
        if day_start_equity is None and equity is not None:
            # [2026-07-11 LATE BASELINE] if the boot/day-roll capture failed
            # (venue down, or the guard vetoed a dislocated print) the rail
            # used to stay OFF all day. Adopt the first credible read instead.
            # This read is already capital-inclusive (the just-folded move is
            # inside `equity`), so it is NOT also shifted below.
            day_start_equity = equity
            print(f"[ticket-taker] {iso(t_now)} day-start equity for {cur_day}: "
                  f"{equity:.2f}")
        else:
            # [2026-07-23] keep day_start on the SAME raw footing as `equity` so a
            # capital move folded mid-day cancels in the rail's (day_start - equity)
            # — the leash measures TRADING P&L only (net of deposits/withdrawals).
            # capital_adjusted_day_start is the shared rule (venues/safety.py); it
            # shifts only when a baseline exists AND a move folded. Persisted with
            # day_start below, so the next run-once cycle restores the shifted one.
            day_start_equity, _shifted = capital_adjusted_day_start(
                day_start_equity, _cap_delta)
            if _shifted:
                print(f"[ticket-taker] {iso(t_now)} day-start equity shifted "
                      f"${_cap_delta:+.2f} for a capital move -> {day_start_equity:.2f} "
                      f"(daily-loss rail stays net of deposits/withdrawals)")
        _fleet_loss = rails.daily_loss_hit(day_start_equity, equity)
        if (not halted_today and equity is not None and day_start_equity
                and (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)
                     or _fleet_loss)):
            # [2026-07-11 RAIL DEBOUNCE] one dislocated equity print sold the
            # book into the dislocation (-5.9% real). Confirm on a second read
            # (shared SafetyRails.confirm_daily_loss — FAIL-SAFE: an unreadable
            # confirm counts as CONFIRMED). Adopt the fresher read either way
            # so a phantom print can't leak into published equity or the
            # persisted baseline.
            _confirmed, equity = rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT, account_value)
            if _confirmed:
                print(f"[ticket-taker] {iso(t_now)} DAILY LOSS LIMIT HIT "
                      f"({equity:.2f} vs day start {day_start_equity:.2f}) — "
                      f"flatten + halt.")
                halted_today = True
                store.save_daily_halt(BOT_ROW, cur_day, day_start_equity)
                _flatten_all("daily_loss")

        if halted_today:
            # [2026-07-16 AUDIT FIX] retry the flatten every halted cycle — it
            # used to run once at the halt transition, so a single failed close
            # (rate-limit storm, venue blip) left that position with NO stop
            # until the day rolled. Idempotent once flat; skip when the kill
            # switch already flattened this same cycle.
            if not rails.kill_check():
                _flatten_all("daily_loss")
            # [2026-07-28 AUDIT FIX] this save was missing sl_block, so every
            # halted cycle overwrote LIVE_STATE_KEY without the post-stop
            # cooldown map — a symbol that SL'd just before the halt was
            # instantly re-eligible at the day roll. Same payload as the
            # normal section-4 save; its False return is paged there, so
            # page here too rather than failing silent.
            _hsave_ok = store.save_state(LIVE_STATE_KEY, {
                "initial_equity": live_baseline, "meta": meta, "stats": stats,
                "capital_adjust": capital_adjust, "sl_block": sl_block,
                "day_start": {"day": cur_day, "equity": day_start_equity}})
            if _hsave_ok is False:
                print("[taker] WARN: halted-day state save FAILED — sl_block/"
                      "day_start may be stale on restart", flush=True)
            # Report what the VENUE actually holds, not 0. A flatten can fail
            # (rate-limit storm, venue blip) and publishing open_trades=0 while
            # real positions are still open would make the retry-every-cycle
            # rail above invisible — a green row over an unstopped book is the
            # convergent-metric trap the perp sniper already walked into.
            try:
                _still = len(venue.positions())
            except Exception:  # noqa: BLE001
                _still = None
            store.publish(
                BOT_ROW, status="halted", equity=equity,
                pnl_abs=((equity - live_baseline - capital_adjust["total"]
                          - CAPITAL_ADJUST_USD)   # D1: capital-adjusted
                         if (equity is not None and live_baseline is not None)
                         else None),
                open_trades=_still, closed_trades=stats["closed"],
                wins=stats["wins"], losses=stats["losses"],
                extra={"venue": TT_VENUE, "strategy": "scout tickets (live)",
                       "halted": True, "day": cur_day,
                       "flatten_incomplete": bool(_still)})
            # [2026-08-04] the MTM series must not skip halted days — a
            # daily-loss halt IS the drawdown the series exists to see.
            try:
                store.snapshot_equity(BOT_ROW, equity, _still)
            except Exception:  # noqa: BLE001
                pass
            print(f"[ticket-taker] {iso(t_now)} halted for {cur_day}; no entries"
                  f"{f'; {_still} STILL OPEN — flatten incomplete' if _still else ''}.")
            return

    try:
        pos = positions()
    except Exception as e:  # noqa: BLE001
        # [2026-07-17] LIVE: never act on a phantom-empty position set. An
        # unreadable venue would zero BOTH the MAX_OPEN slot count and the
        # notional cap's input (open_notional sums what's in `pos`), so the
        # entry pass below would happily open a full book ON TOP of positions
        # that already exist — the cap breach the rail exists to prevent,
        # reached by believing our own blindness. The funding bot skips its
        # loop for exactly this reason; this is a run-once process, so
        # skipping the cycle IS the loop-skip.
        print(f"[ticket-taker] {iso(t_now)} positions unreadable ({e!r}) — "
              f"skipping cycle (no entries, no exits)")
        store.heartbeat(BOT_ROW)
        return

    # [2026-07-17 ADOPTION GUARD — the Tide Rider handover] A live arm inherits
    # a real Lighter SUB-ACCOUNT, and the plan is to hand it the one Tide Rider
    # is vacating. If ANY position on it has no meta of ours, this bot did not
    # open it and MUST NOT manage it: it has no entry clip, no lens and no
    # opened-time, so every rule below would be applied to someone else's
    # position on the wrong strategy's bars — the exit ladder would TP/SL a
    # trend position at the taker's ±4%, the ledger would book it under a
    # "ticket" lens the brain then grades, and the divergence-only mandate
    # would be silently violated by a coin no scout ever ticketed.
    #
    # WHY THIS IS NOT PARANOIA: crypto-trend-daily-lighter's row still reads
    # held:['TRX'] at equity $34.67 — but its status is `error`, and
    # SafetyRails._publish_refusal is a STATUS-ONLY write, so those values are
    # the LAST GOOD PUBLISH, frozen. The dashboard cannot tell you whether that
    # account is flat; only a keyed read can. So the bot checks at the venue,
    # every cycle, and refuses rather than guesses.
    #
    # Fail-CLOSED on real money: a lost meta (a failed state write) also lands
    # here, and halting is still right — a position we cannot attribute is one
    # we cannot manage. The kill switch runs ABOVE this and still flattens,
    # so REAL_MONEY_KILL remains the escape hatch for a dirty account.
    # [2026-07-17 AUDIT] SCOPED to the foreign symbols, not the whole account.
    # This guard was `raise SystemExit` on ANY unattributable position — which
    # ran BEFORE sections 1-4, so it did not merely decline to adopt the
    # stranger: it abandoned OUR OWN meta'd positions in the same breath. No
    # mark, no stop-loss, no max-hold, no delist give-up, for as long as the
    # stranger sat there. On a $15 clip at the $30 cap that is real money left
    # unstopped, and a lost meta WRITE (save_state returns False silently)
    # makes it PERMANENT — operator-only to clear.
    #
    # The original reasoning is still honoured, and is the reason this is a
    # FILTER rather than a deletion: we must not run the taker's exit ladder on
    # another strategy's position (no entry clip, lens or opened-time), and we
    # must not trade while the account is dirty. So: drop the foreign symbols
    # from the working set (sections 1-2 can never touch them), refuse NEW
    # entries, and page — while our own positions keep every exit they had.
    # The file's own live_boot_gate docstring names this exact hazard: "the
    # switch meant to protect the money would be what abandons it."
    dirty_syms = []
    if live:
        dirty_syms = sorted(s for s in pos if s not in meta)
        if dirty_syms:
            store.set_status(BOT_ROW, "error")
            print(f"[ticket-taker] {iso(t_now)} DIRTY ACCOUNT: venue reports "
                  f"{dirty_syms} with no meta of ours — NOT adopting "
                  f"{'them' if len(dirty_syms) > 1 else 'it'} (no entry clip, "
                  f"lens or opened-time, so the exit ladder would manage "
                  f"another strategy's position on the taker's bars) and NO "
                  f"NEW ENTRIES this cycle. Our own {len(pos) - len(dirty_syms)} "
                  f"position(s) keep their stop/max-hold. If this is Tide "
                  f"Rider's leftover on the handed-over sub-account, flatten it "
                  f"(by hand, or REAL_MONEY_KILL=DISARMED_I_UNDERSTAND). If it "
                  f"is OURS with a lost meta write, reconcile "
                  f"bot_state['{LIVE_STATE_KEY}'].meta — those symbols have NO "
                  f"stop until you do.", flush=True)
            # (the `error` row status above IS the operator signal — this file
            # has no push helper, and inventing one here would be a second
            # untested path on a live bot.)
            # sections 1-2 iterate `pos`; the stranger must not be in it
            pos = {s: v for s, v in pos.items() if s not in set(dirty_syms)}

    # 1) mark + hourly funding drag on held positions (longs pay positive rate)
    for sym in list(pos):
        mark = marks.get(sym)
        if mark and dry_run:
            broker.mark(sym, mark)
        m = meta.get(sym) or {}
        try:
            last = parse_ts(m.get("accrued_to") or m.get("opened"))
            hours = max(0.0, (t_now - last).total_seconds() / 3600.0)
        except (ValueError, TypeError):
            hours = 0.0
        rate = funding.get(sym)
        if hours > 0 and rate and mark:
            size = pos[sym]["size"]
            # SIGNED accrual: a long pays a positive rate (drag > 0), a short
            # RECEIVES it (drag < 0 = credit) — the divergence lens's whole
            # thesis is collecting that credit.
            #
            # [2026-07-17 BASIS FIX] This read Lighter's quote as HOURLY and
            # accrued `rate * hours` = 8x TRUE (Lighter quotes per 8h). The
            # THIRD accruing book to carry this bug — 93be95e fixed
            # Counterweight and the family bot and called the set complete;
            # this one models its carry inline rather than via funding_basis,
            # so a grep for the fixed call site could not see it.
            # It lands exactly where it hurts most: DIVERGENCE is the only
            # lens with a positive forward grade and the only one that
            # COLLECTS carry, so the inflated credit flattered the one number
            # that could earn this bot a go-live. Same shape as Counterweight,
            # whose entire reported profit was this artifact.
            # LIVE note: a live arm's real funding is charged by the VENUE and
            # is already inside account_value(), so it must NOT also hit a
            # modelled equity — but the accrual still reaches the per-trade
            # ledger and the win/loss call, which is why it is computed on
            # both arms and applied to equity on only one.
            drag = size * mark * funding_basis.to_hourly(rate, "lighter") * hours
            if dry_run:
                broker.fees += drag
            m["funding_paid"] = round(float(m.get("funding_paid") or 0.0) + drag, 6)
            m["accrued_to"] = iso(t_now)
            meta[sym] = m

    # 2) exits
    for sym in list(pos):
        mark = marks.get(sym)
        m = meta.get(sym) or {}
        try:
            opened = parse_ts(m.get("opened"))
        except (ValueError, TypeError):
            opened = t_now
        size = pos[sym]["size"]
        # The VENUE's avg_entry_price is the REAL fill and outranks our
        # decision price; meta is the fallback for a position the venue
        # reports without one. In dry_run pos[] IS the broker, so this is the
        # broker's own entry — one expression, right on both arms.
        entry = float(pos[sym].get("entry") or m.get("entry") or 0.0)
        is_long = size > 0
        if mark:
            m.pop("no_mark_since", None)     # priceable again — reset the clock
            m["last_mark"] = mark
            # [2026-07-24 (de) TREND EXIT in the LIVE/shadow manager] track the
            # peak favourable return so a breakout can trail from its high, and
            # route the exit per lens. MIRRORS the replay's peak-track
            # (lighter_ticket_replay.py) so the capturability read and the live
            # manager exit identically.
            _sgn = 1.0 if is_long else -1.0
            _ret = (mark / entry - 1.0) * _sgn if entry else 0.0
            if _ret > m.get("peak_ret", 0.0):
                m["peak_ret"] = _ret
            # [2026-08-20 (sk)] RECEIPTS FOR THE TREND EXIT'S OWN TWO KNOBS.
            # `taker.brk_trail` and `taker.brk_sl` became registered levers
            # today, and neither could ever be PROFILED, because the quantity
            # each one cuts was tracked in memory and thrown away at close:
            # the trail fires on GIVE-BACK from the peak, the stop on ADVERSE
            # EXCURSION, and the ledger recorded neither. A cage nobody can
            # measure is `audit_lever_authority`'s named failure — and it is
            # the reason both widenings had to be WITHHELD today rather than
            # decided: the harness had to reconstruct from hourly candles what
            # the bot already knew to the loop.
            #
            # MAXIMUM, not final, on both: the bar cuts the worst point the
            # position ever reached, so a distribution of final values would
            # be the wrong one (and, for the trail, truncated at the bar by
            # construction — the emission-truncation trap). Observable-only;
            # `exit_reason` reads neither.
            m["give_back"] = max(m.get("give_back", 0.0),
                                 m.get("peak_ret", 0.0) - _ret)
            m["mae_ret"] = min(m.get("mae_ret", 0.0), _ret)
            meta[sym] = m
            _ebars, _etrail = bull_exit(m.get("lens"))
            if _ebars is not None:
                # [(dg) FLAP-FIX for breakout] the breakout runs the TREND policy
                # (no-TP cap 999, wide BRK_SL) BUT its max-hold must stay the
                # ENTRY-STAMPED bar — MAX_HOLD_H is a growth-rail lever, and the
                # (bw) invariant is "bars priced at entry govern the trade". Graft
                # the stamped hold onto the trend tp/sl so a mid-position lever
                # move cannot re-time an open breakout.
                _ebars = (_ebars[0], _ebars[1], pos_bars(m)[2])
            # [(dg) INERTNESS GUARD] when bull is off bull_exit -> (None, None);
            # pass trail=0.0 (NOT None) so exit_reason cannot fall back to the
            # global TT_TRAIL_PCT and silently trend-exit a REAL-MONEY position.
            # The real guard is BULL_MODE — this makes the code match that claim
            # (pre-(de) main() never passed peak_ret, so TT_TRAIL_PCT was dormant
            # here; (de) began passing it, which this restores to inert).
            _trail = _etrail if _etrail is not None else 0.0
            reason = exit_reason(entry, mark, opened, t_now, is_long,
                                 bars=(_ebars or pos_bars(m)),
                                 peak_ret=m.get("peak_ret"), trail=_trail)
        else:
            # [2026-07-16 ZOMBIE GUARD] book missing from the active universe
            first = m.get("no_mark_since")
            try:
                parse_ts(first)
            except (ValueError, TypeError):
                first = None
            if not first:
                m["no_mark_since"] = iso(t_now)   # start (or restart) the clock
                meta[sym] = m
                continue
            if not delist_due(first, t_now):
                continue
            mark = float(m.get("last_mark") or entry)
            reason = "delisted"
        if not reason:
            continue
        if dry_run:
            pnl = broker.close(sym, mark)
            _dpx = None
            _meas, _why = None, None
        else:
            try:
                # [2026-07-17] This block's own comment already said "never book
                # a close that did not happen" — but it only caught EXCEPTIONS,
                # and the stranding case does NOT raise: market_close() returns
                # None when it finds no position under that key
                # (venues/lighter_client.py:558-560). That is precisely the
                # symbol-space failure, so the guard missed the case it was
                # written for. None is a FAILED close.
                _res = venue.market_close(_fleet(sym))
                if _res is None:
                    print(f"[ticket-taker] {iso(t_now)} close {sym}: venue "
                          f"reported NO position under {_fleet(sym)!r} — NOT "
                          f"booking a close; leaving position, retry next cycle")
                    continue
            except Exception as e:  # noqa: BLE001
                # Leave the position and retry next cycle. Never book a close
                # that did not happen — a phantom close drops the position from
                # meta while the venue still holds the risk.
                print(f"[ticket-taker] {iso(t_now)} close {sym} failed: {e!r} — "
                      f"leaving position, retry next cycle")
                continue
            _dpx = mark                                  # mid at the decision
            mark, _meas, _why = _real_fill(
                sym, is_ask=is_long, fallback=mark, leg="exit",
                client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
            pnl = abs(size) * ((mark - entry) if is_long else (entry - mark))
        _book_close(sym, m, size, entry, mark, pnl, reason, decision_px=_dpx,
                    measured=_meas, fill_reason=_why)
        pos.pop(sym, None)
        if reason == "sl" and SL_COOLDOWN_H > 0:
            sl_block[sym] = iso(t_now + timedelta(hours=SL_COOLDOWN_H))
            print(f"[ticket-taker] {iso(t_now)} {sym} entry-blocked "
                  f"{SL_COOLDOWN_H:g}h post-stop (same-cycle re-entry churn "
                  f"guard)")

    # 3) entries — only from a FRESH scout snapshot, only the incredible subset
    # [2026-07-17 AUDIT] ...and never onto a DIRTY account. The old guard's
    # SystemExit blocked entries as a side effect of abandoning everything;
    # scoping it to the foreign symbols means the no-new-entries half must now
    # be stated EXPLICITLY, or relaxing the strand would have quietly relaxed
    # the trading refusal too. Refusing to ADD exposure while the account holds
    # something we cannot attribute is the half of the original rule that was
    # always right — it is the abandonment half that was the bug.
    scout = {} if dirty_syms else (store.load_state(SCOUT_KEY) or {})
    fresh = False
    try:
        age = (t_now - parse_ts(scout.get("updated"))).total_seconds()
        # [2026-07-23 AUDIT] bound BELOW too: a future-dated payload (clock skew
        # / bad publisher) must read STALE, not fresh — matching fleet_bus.is_fresh
        # and this bot's own coin-veto read (0 <= age <= ttl). Without the lower
        # bound a future stamp passed as fresh and its stress value was used.
        fresh = 0 <= age <= float(scout.get("ttl_sec") or 900)
    except (ValueError, TypeError):
        fresh = False
    # [2026-07-14b] Stress veto: a venue-wide |premium| blowout means marks
    # are unreliable and every book is dislocating together — no new bets.
    stress_med = ((scout.get("stress") or {}).get("med")
                  if fresh else None)
    stressed = stress_med is not None and stress_med >= STRESS_VETO_BPS
    if stressed:
        print(f"[ticket-taker] {iso(t_now)} STRESS VETO — venue |premium| "
              f"median {stress_med}bps >= {STRESS_VETO_BPS}bps; no new entries")
    # [2026-07-14c] Fleet drawdown governor: fleet_risk publishes clip_scale
    # (1.0 / 0.5 past -5% 7d dd / 0.25 past -10%). Fail-safe neutral on
    # missing/stale state — same contract as every bus consumer.
    gov = 1.0
    long_budget_full = False
    try:
        fr = store.load_state("fleet-risk") or {}
        fr_age = (t_now - parse_ts(fr.get("updated"))).total_seconds()
        if 0 <= fr_age <= float(fr.get("ttl_sec") or 900):  # [2026-07-23] future-stamp-safe
            gov = max(0.25, min(1.0, float(fr.get("clip_scale") or 1.0)))
            # [2026-07-15 AUDIT FIX] L2 long-budget veto now has a consumer in
            # the RUNNING fleet (it was wired only into the retired Kraken
            # strategies). Fail-safe OPEN: stale/missing state never blocks.
            _lb = fr.get("long_budget")
            _lb = 10**9 if _lb is None else int(_lb)   # 0 is a REAL budget
            if (fr.get("mode") == "enforce"
                    and (fr.get("long_positions") or 0) >= _lb):
                long_budget_full = True
    except (ValueError, TypeError):
        gov = 1.0
    # [2026-07-21 AUDIT FIX] the LIVE arm now honors live.clip_scale — the
    # board's ONLY live restrict lever. CLAUDE.md's live-lane contract
    # ("covers ... both live bots' clip") was half-true: the Funding Farmer
    # reads it via VenueContext.order_usd, but this bot builds LighterClient
    # directly and sized off TT_CLIP_* alone, so the board's real-money
    # down-scale (and the proprioception hurting-revert riding get_lever's
    # central hook) never reached the live Ticket Taker. get_lever carries
    # the whole fail-safe stack: registry clamp [0.5,1.5], TTL expiry,
    # immune quarantine, hurting-revert, ENACT_LANES kill.
    # [2026-07-21b, same-day verify catch] the lever REPLACES the fleet-risk
    # drawdown governor on the live arm rather than compounding with it:
    # CLAUDE.md's contract is explicit — the fleet clip_scale "reaches only
    # shadow consumers (family/taker); the live bots size off the separate
    # live.clip_scale lever" — and this arm consuming BOTH would double-
    # restrict through two organs' opinions of the same drawdown. Shadow
    # arm keeps the fleet governor unchanged (its book is the lens-grading
    # instrument).
    if not dry_run:
        live_scale = 1.0
        if tuning is not None:
            try:
                live_scale = float(tuning.get_lever("live.clip_scale", 1.0))
            except Exception:  # noqa: BLE001
                live_scale = 1.0
        gov = live_scale
        if live_scale != 1.0:
            print(f"[ticket-taker] {iso(t_now)} LIVE CLIP SCALE — "
                  f"x{live_scale} (live.clip_scale; fleet governor is "
                  f"shadow-lane per contract)")
    elif gov < 1.0:
        print(f"[ticket-taker] {iso(t_now)} DRAWDOWN GOVERNOR — clips x{gov}")
    if long_budget_full:
        print(f"[ticket-taker] {iso(t_now)} FLEET LONG-BUDGET VETO — "
              f"{fr.get('long_positions')}/{fr.get('long_budget')} directional "
              f"longs; no new LONG entries this cycle (shorts unaffected)")
    # [2026-07-15 LENS-FORWARD VETO] The brain grades every scout ticket
    # counterfactually (bot_state 'brain-lens-forward'). RESTRICT-ONLY, per
    # doctrine: a lens graded negative at sample size stops getting fills;
    # missing/stale grades never block anything (fail-safe open).
    lens_vetoed = set()
    # [2026-08-01 (ij)] THIS ARM'S OWN CLOSES, which are SENIOR to the forward
    # proxy for any lens that has enough of them. Read here rather than inside
    # `vetoed_lenses` so the rule stays pure and testable, and so a ledger
    # outage degrades to the pre-(ij) behaviour (forward grade only) instead of
    # to "veto nothing" or a crash. Fail-safe open, like every read in this
    # block: no rows -> `realised={}` -> the forward grade decides, unchanged.
    realised = {}
    try:
        # [(lj)] policy= scopes the grade to trades taken under the policy
        # this arm runs NOW — the same boundary the go-live grader draws.
        realised = realised_lens_evidence(
            store.fetch_paper_trades(limit=4000), BOT_ROW,
            sides=restricted_sides(), policy=current_policy())
    except Exception:                       # noqa: BLE001
        realised = {}
    try:
        lf = store.load_state("brain-lens-forward") or {}
        lf_age = (t_now - parse_ts(lf.get("updated"))).total_seconds()
        if 0 <= lf_age <= float(lf.get("ttl_sec") or 26000):  # [2026-07-23] future-stamp-safe
            lens_vetoed = vetoed_lenses(lf.get("lenses"),
                                        sides=restricted_sides(),
                                        realised=realised)
        elif realised:
            # The brain is DARK but this arm's own record is not. A lens its
            # own trades have disproven must still stop — the forward grade
            # being stale is no reason to keep paying for a measured loser.
            lens_vetoed = vetoed_lenses({k: {} for k in realised},
                                        sides=restricted_sides(),
                                        realised=realised)
    except (ValueError, TypeError):
        lens_vetoed = set()
    if lens_vetoed:
        print(f"[ticket-taker] {iso(t_now)} LENS VETO — brain grades "
              f"{sorted(lens_vetoed)} negative at sample size; skipping their "
              f"tickets (restrict-only; recovers when the grade does)")
    # [2026-07-24 (dm) INCREMENT B] breakoutup earns its OWN veto from its own
    # 'long-breakoutup' closes. brain-lens-forward can never carry breakoutup
    # (it grades SCOUT lenses' forward marks) — the per-close-tag grade lives in
    # brain-stake-mults, read here (freshness-checked like the lens-forward read
    # above; fail-OPEN on missing/stale). breakoutup_self_vetoed() bites only on
    # the brain's DECISIVE floor-reduce; it folds into the SAME lens_vetoed set
    # the entry loop checks AFTER the relabel (:~1871), so no entry-loop change.
    # Inert on the live arm: breakoutup never fills there, so its bucket is empty.
    try:
        sm = store.load_state("brain-stake-mults") or {}
        sm_age = (t_now - parse_ts(sm.get("updated"))).total_seconds()
        if 0 <= sm_age <= float(sm.get("ttl_sec") or 26000):  # future-stamp-safe
            if breakoutup_self_vetoed(sm, BOT_ROW):
                lens_vetoed.add("breakoutup")
                print(f"[ticket-taker] {iso(t_now)} BREAKOUTUP SELF-VETO — brain "
                      f"reduced long-breakoutup to its floor on its own closes; "
                      f"pausing the lens (restrict-only; recovers when it does)")
    except (ValueError, TypeError):
        pass
    # [2026-07-22 COIN-QUALITY VETO] Same contract as the Farmer's
    # (lighter_funding_bot.py:1033), transcribed so the two cannot drift:
    # RESTRICT-ONLY, and a missing OR STALE payload yields NO vetoes (fail
    # OPEN). Staleness matters in both directions — a dead market-context
    # either vetoes forever or, if it died empty, silently disables the veto
    # forever; only an age check distinguishes them.
    coin_vetoed = {}
    if QUALITY_VETO:
        try:
            _vp = store.load_state("coin-vetoes") or {}
            _cv = _vp.get("coins") or {}
            # a veto set is a coin->reason MAP; anything else is not evidence
            if not isinstance(_cv, dict):
                _cv = {}
            _vts = _vp.get("updated") or _vp.get("ts")
            _vttl = float(_vp.get("ttl_sec") or QUALITY_VETO_TTL_S)
            _vage = ((t_now - parse_ts(_vts)).total_seconds() if _vts else None)
            if _vage is not None and 0 <= _vage <= _vttl:
                coin_vetoed = _cv
                if coin_vetoed:
                    # Print each coin's OWN reason. The set is NOT slippage-only
                    # — market_context.py:396-399 has two branches (slip > 15bps
                    # over >=5 orders/14d, OR stop-rate >=50% over >=5 closes/
                    # 30d, pooled fleet-wide) — and today's live set proves it:
                    # ADA is a STOP-RATE veto whose own slip is 3.65bps. A log
                    # line saying "measured slippage [ADA, BOT, SOXL]" is this
                    # repo's own self-describing-label failure, in the actuator's
                    # own receipt. Say what each one actually is.
                    print(f"[ticket-taker] {iso(t_now)} COIN VETO — "
                          + "; ".join(f"{c}: {coin_vetoed[c]}"
                                      for c in sorted(coin_vetoed))
                          + "  (restrict-only for NEW entries; exits, stops and "
                            "held positions untouched)")
            elif _cv:
                print(f"[ticket-taker] {iso(t_now)} coin-vetoes STALE "
                      f"(age {_vage if _vage is None else round(_vage)}s > "
                      f"ttl {_vttl:.0f}s) — discarding {len(_cv)} veto(s); "
                      f"quality veto fails OPEN until the publisher returns")
        except Exception:  # noqa: BLE001 — the Farmer's ACTUAL contract
            # Widened from (ValueError, TypeError, AttributeError): the Farmer
            # catches bare Exception, and a narrower tuple here is exactly the
            # silent drift this change exists to prevent. On the LIVE run-once
            # arm an escape here would abort the cycle before the durable write,
            # losing day_start and re-baselining the daily-loss rail.
            coin_vetoed = {}
    opened_syms, opened_lenses = set(), set()
    # [2026-08-27 (uo)] THE SLOT CENSUS — which constraint actually binds.
    # `open 6/6` is BYTE-IDENTICAL between "six tickets existed" and "twenty
    # existed and fourteen were refused for want of a slot" (I18/(lv), in the
    # mirror direction: not an arm that opens NOTHING, an arm that is always
    # FULL). Three throttles can bind here and none was counted:
    #   slots_full  -- `len(pos) >= MAX_OPEN`, which `break`s silently
    #   lens_once   -- one NEW position per lens per cycle
    #   held_sym    -- never add to a symbol already held
    # So nobody tuning TT_MAX_OPEN could see the thing they were tuning (I23).
    # This is the measurement that has to exist BEFORE a slot change can be
    # justified, and it is REPORTED, never a gate — it changes no entry.
    slot_census = {"offered": 0, "slots_full": 0, "lens_once": 0,
                   "held_sym": 0, "opened": 0}
    # [2026-07-17] Hard mode allow-list, evaluated ONCE and independently of any
    # bus payload. Live = divergence only; shadow keeps filling all four so the
    # control arm still grades them. See allowed_lenses().
    _allowed = allowed_lenses(TT_VENUE)
    # [(dv)] seed the up-regime cache from the last boot BEFORE the entry loop's
    # up_read calls — turns ~12 daily-candle fetches/book/hour into ~1. Gated to
    # the arm that can actually fill breakout (live filters it at the allow-list,
    # so this is a pure no-op there — not even the state read). Fail-safe.
    if BULL_MODE and "breakout" in _allowed:
        load_upregime_cache(store, BOT_ROW, t_now.timestamp())
    if fresh and not stressed:
        for lens, t in incredible(scout.get("tickets") or {}):
            sym = t.get("sym")
            if lens not in _allowed:
                continue          # mode allow-list — FAIL-CLOSED, reads no bus
            # [(hj)] SIDE allow-list, the twin of the line above and evaluated
            # in the same place for the same reason: independent of BULL_MODE,
            # of the brain, and of every bus payload. On the live arm this is
            # what keeps `long-divergence` — 12 of the live book's 25 closes,
            # and the measured-losing side of the lens — off real money when
            # TT_BULL_MODE is not set. No-op on shadow (both sides allowed).
            if side_of(t) not in allowed_sides(TT_VENUE, lens):
                continue
            # [2026-07-24 (dk) breakout_up RELABEL — BEFORE the veto] An UP-REGIME
            # crypto breakout becomes its own lens 'breakoutup' HERE, ahead of the
            # brain veto: the broad 4h 'breakout' veto is correct for un-gated
            # breakouts (eavg4h -0.042) but would otherwise skip the up-regime
            # subset before up_read ever runs — and that subset is positive at the
            # bull horizon (eavg24h +0.314). 'breakoutup' is not scout-graded, so
            # it starts OUT of lens_vetoed => fires + collects data (the unblock);
            # it earns its OWN veto from its 'long-breakoutup' closes — WIRED in
            # (dm) above (breakoutup_self_vetoed reads brain-stake-mults and adds
            # 'breakoutup' to lens_vetoed on the brain's decisive floor-reduce).
            # A NON-up breakout stays 'breakout' and correctly hits the veto below.
            # Bull + breakout only; the LIVE arm never reaches here (allowed_lenses
            # filtered breakout above), so real money is untouched. up_read is done
            # here (pre-veto) and REUSED in the bull block — no double fetch.
            _bull_up = None
            if BULL_MODE and lens == "breakout" \
                    and str(t.get("side", "long")) != "short":
                _bull_up = up_read(venue, sym, t_now.timestamp())
                if _bull_up is True and _is_crypto(sym):
                    lens = "breakoutup"
            if lens in lens_vetoed:
                continue          # brain veto stays SENIOR (restrict-only)
            # [2026-07-24] BULL DUAL-MODE gate — no-op unless TT_BULL_MODE.
            # Restrict-only: admits ONLY long-breakout(up-regime) + short-
            # divergence, crypto-only. SHADOW-only until it proves capturable.
            if BULL_MODE:
                _bside = "short" if str(t.get("side", "long")) == "short" \
                    else "long"
                # 'breakoutup' is up-confirmed by construction (relabelled above);
                # a plain 'breakout' reuses the pre-veto read (None for a non-
                # breakout lens -> divergence's funding-screen fallback).
                _up = True if lens == "breakoutup" else _bull_up
                if not bull_entry_ok(lens, _bside, t, up=_up):
                    continue
                # [2026-07-24 (di) SCANNER SIDEKICK] breakout QUALITY score — for
                # a plain 'breakout' AND the relabelled 'breakoutup'. Reuses
                # up_read's cached strength (NO extra fetch); applies the ADVISORY,
                # default-off TT_BRK_QUALITY_MIN gate (restrict-only, inert at 0.0).
                # Stashes the score + up-strength on the ticket so they are CAPTURED
                # on the entry (evidence, below) -> the close row -> the winning
                # criteria can be DERIVED from outcomes. Divergence is untouched.
                if lens in ("breakout", "breakoutup"):
                    _ustr = up_read_strength(sym)
                    _q = breakout_quality(_ustr, t.get("range_pos"),
                                          t.get("vol_m"))
                    if _q < BRK_QUALITY_MIN:
                        continue          # default 0.0 -> never blocks
                    t = {**t, "_brk_quality": _q, "_up_strength": _ustr}
            # [2026-07-22] coin-quality veto. Symbol form is normalised because
            # the scout emits a bare base ("BOT") while the ledger records a
            # pair ("BOT/USDC"); matching only one form would make this veto
            # silently inert — the exact failure mode it exists to fix.
            # ALSO fold the venue's 1000X spelling into the fleet-canonical kX
            # via _fleet(): coin_quality now publishes the veto set keyed by the
            # fleet form (from_lighter), and this arm writes '1000BONK', so an
            # un-normalised lookup here would miss its own coin's veto for all
            # six 1000-markets. _fleet() is identity for a coin with no 1000
            # prefix, so ordinary coins are unaffected. Check BOTH the canonical
            # AND the raw base so this is robust to deploy ORDER: market_context
            # auto-deploys (new canonical payload) while this LIVE arm needs a
            # manual dispatch, so for a window the payload is canonical and the
            # code old, or vice-versa — matching either form vetoes correctly
            # throughout the transition. Restrict-only, so an extra match only
            # ever SKIPS an entry, never forces one.
            _vbase = str(sym or "").split("/")[0]
            if coin_vetoed and (_fleet(_vbase) in coin_vetoed
                                or _vbase in coin_vetoed):
                continue          # measured slippage over the bar (fail-open)
            # one NEW position per lens per cycle; never add to a held symbol
            # [(uo)] counted BEFORE the `continue`/`break` so the census sees
            # exactly what each throttle refused. `slots_full` is counted for
            # EVERY remaining ticket rather than once, because the question it
            # answers is "how much supply did the cap turn away this cycle?"
            slot_census["offered"] += 1
            if len(pos) >= MAX_OPEN:
                slot_census["slots_full"] += 1
                continue
            if (not sym or sym in pos or sym in opened_syms
                    or lens in opened_lenses
                    or _sl_active(sl_block.get(sym), t_now)):
                if sym and (sym in pos or sym in opened_syms):
                    slot_census["held_sym"] += 1
                elif lens in opened_lenses:
                    slot_census["lens_once"] += 1
                continue
            mark = marks.get(sym)
            if not mark:
                continue
            # [2026-07-23] SPREAD GATE — proactive execution-cost veto, default
            # OFF. The book is fetched ONLY when the gate is enabled and ONLY for
            # a candidate that has already cleared every cheap filter above, so
            # the shipped default (0) adds ZERO network calls and an enabled gate
            # fetches at most ~MAX_OPEN books per cycle. spread_bps stays defined
            # (None) for the publish below whether or not the gate ran. Fail-OPEN:
            # a book fetch blip must never halt entries. See SPREAD_GATE_BPS.
            spread_bps = None
            if SPREAD_GATE_BPS > 0:
                try:
                    spread_bps = book_spread_bps(venue.orderbook(sym))
                except Exception:  # noqa: BLE001 — read blip is not a stop
                    spread_bps = None
                if spread_gate_blocks(spread_bps, SPREAD_GATE_BPS):
                    print(f"[ticket-taker] {iso(t_now)} {sym} SPREAD_GATE_SKIP "
                          f"(quoted {spread_bps:.1f}bps > {SPREAD_GATE_BPS:.0f})")
                    continue
            is_long = t.get("side", "long") != "short"
            if is_long and long_budget_full:
                continue          # L2 veto: fleet long budget is full
            # [2026-08-20 (so)] THE BRAIN SIZES THIS ENTRY, per (side, lens).
            # This book is the reason the wiring exists: on the morning it
            # shipped the brain's entire published opinion across the fleet was
            # two mults, and one of them was THIS row's `short-divergence` at
            # 0.75 (n=78, t=-1.43), held for 11 consecutive runs into a
            # consumer that did not exist. The lens is the natural bucket —
            # the taker already grades, vetoes and tunes per lens, and sizing
            # was the one lens-shaped decision still taken flat.
            # ORDER MATTERS: the governor (`gov`) is the FLEET's drawdown
            # brake and the brain's mult is this BOOK's evidence; both are
            # multiplicative and both apply, and the notional cap below still
            # sees the final number.
            # [(sp)] the brain scales the RISK BUDGET and vol_clip converts
            # risk -> clip exactly as it always has, so constant-risk sizing
            # survives and CLIP_MAX still binds — see vol_clip's own note.
            # The ceiling is lifted by BRAIN_GROSS_X (not by the full 6.7x):
            # this book's cap is 6 slots, so an unlifted ceiling would make the
            # brain inert on a calm book while a fully-lifted one would put
            # $3,216 of gross on a $1,000 shadow row.
            _bm = fleet_bus.brain_mult_multi(
                [(BOT_ROW, f"{'long' if is_long else 'short'}-{lens}")])
            clip = round(vol_clip(
                ranges.get(sym), risk_usd=RISK_USD * _bm,
                clip_max=CLIP_MAX * getattr(fleet_bus, "BRAIN_GROSS_X", 1.0)
            ) * gov, 2)
            bmult = _bm
            size = clip / mark
            ev = {k: t.get(k) for k in ("range_pos", "chg_pct", "vol_m",
                                        "prem_bps", "apr_pct", "gap_pct")}
            # [2026-07-24 (di)] capture the scanner-sidekick features for a
            # breakout entry (stashed by the bull gate above) so the close row
            # carries them — the raw material for DERIVING the winning criteria.
            if t.get("_brk_quality") is not None:
                ev["brk_quality"] = t.get("_brk_quality")
                ev["up_strength"] = t.get("_up_strength")
            entry_px = mark
            # [2026-07-17] BRACES to the allow-list's belt. The filter above is
            # the belt; this is the last statement before real money moves, so
            # a future second entry path cannot bypass it by construction.
            # SystemExit propagates through _supervised() untouched — a breach
            # HALTS rather than restarting into the same bug.
            if not dry_run and lens not in LIVE_LENSES:
                raise SystemExit(
                    f"live lens allow-list BREACHED: {lens!r} reached the order "
                    f"path on real money (allowed: {sorted(LIVE_LENSES)}). "
                    f"Halting rather than filling.")
            # [(hj)] The SIDE braces. Checked against `is_long` — the variable
            # that is actually handed to market_open — NOT against the ticket
            # field the belt read, so a divergence between the two is caught
            # here rather than filled. Same halt-don't-restart semantics.
            if not dry_run:
                _oside = "long" if is_long else "short"
                _ok_sides = allowed_sides(TT_VENUE, lens)
                if _oside not in _ok_sides:
                    raise SystemExit(
                        f"live SIDE allow-list BREACHED: {_oside} {lens!r} "
                        f"reached the order path on real money (allowed: "
                        f"{sorted(_ok_sides) or 'NOTHING'}). "
                        f"Halting rather than filling.")
            if dry_run:
                broker.open(sym, is_long, size, mark)
                # ShadowBroker fills by WALKING the book, so the decision price
                # is NOT the fill — read the entry back instead of assuming it.
                # PaperBroker.open() also silently no-ops on a bad size/price;
                # a missing key here means no position was actually taken, and
                # claiming one in `pos` would strand a phantom in the cap
                # count and the slot budget.
                if sym not in broker.pos:
                    print(f"[ticket-taker] {iso(t_now)} open {sym} rejected by "
                          f"broker (size {size} @ {mark})")
                    continue
                _sz, entry_px = broker.pos[sym]
                size = abs(_sz)
            else:
                # The operator's hard notional cap is SENIOR to every other
                # sizing input (governor, vol_clip, growth rail) and is checked
                # against REAL deployed notional at order time — never
                # count*clip, which breached the cap on 15-Jul once the growth
                # rail made the clip variable. venues.safety owns this rule.
                open_ntl = open_notional(pos, meta, len(pos), clip)
                if not rails.notional_ok(open_ntl, clip):
                    print(f"[ticket-taker] {iso(t_now)} {sym} NOTIONAL_CAP_SKIP "
                          f"(deployed ${open_ntl:.2f} + ${clip:.2f} > cap "
                          f"${rails.max_notional})")
                    continue
                size = round(size, 6)
                try:
                    # fleet symbol — the space the client's API speaks. This one
                    # would have "worked" with a native symbol (_resolve tolerates
                    # it), which is exactly how open/close drifted apart.
                    _res = venue.market_open(_fleet(sym), is_long, size)
                except Exception as e:  # noqa: BLE001
                    print(f"[ticket-taker] {iso(t_now)} open {sym} failed: {e!r}")
                    continue
                _fill_px, _meas, _why = _real_fill(
                    sym, is_ask=not is_long, fallback=mark, leg="entry",
                    client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
                try:
                    store.publish_venue_order(
                        BOT_ROW, venue="lighter", shadow=False, coin=sym,
                        side=("buy" if is_long else "sell"), size=size,
                        px_decision=mark, px_fill=_fill_px,
                        slippage_bps=_slip_bps_of(mark, _fill_px,
                                                  is_buy=is_long,
                                                  measured=_meas),
                        # [2026-07-23] the LIVE arm records no spread today (the
                        # order goes via market_open, not a book walk). When the
                        # spread gate is enabled (incl. record-only mode) it has
                        # already fetched the decision-time book, so log it here
                        # too — closing the live-spread telemetry gap the gate
                        # needs to be validated on the live arm's own tape. None
                        # (gate off) is identical to prior behaviour.
                        spread_bps=spread_bps,
                        raw={"lens": lens, "leg": "open", "clip": clip,
                             "evidence": ev,
                             "measured": _meas, "fill_src": _why})
                except Exception:  # noqa: BLE001
                    pass
                # ---- ORDER BEHAVIOUR STOPS HERE ---------------------------
                # Everything above is telemetry. `entry_px` is NOT: it becomes
                # meta[sym]["entry"], which the stop and TP hang off, so it
                # decides when REAL money closes. This is the one place the
                # taker differs from the Farmer, whose exit read is pure
                # forensics (the position is already flat when it runs) — here
                # the read steers the next decision.
                #
                # So an UNMEASURED price never reaches it. read_fill's id-miss
                # fallback is a 180s same-side VWAP and has NEVER run in
                # production (the id round trip is unproven — the only two live
                # orders predate the fill-read code), and a fallback's first
                # ever execution must not be the thing that moves a live stop.
                # It is probably a better entry estimate than the decision mark.
                # "Probably" is not a bar this bot clears with real money on the
                # book: the ledger records the blend and names it, the operator
                # reads it there, and a later change can promote it on evidence.
                #
                # BEHAVIOUR-IDENTICAL on every path production can reach today:
                # an exact id match (_meas=True) keeps feeding meta the real
                # fill exactly as it does now, and no-read keeps feeding it the
                # mark. Only the id-miss path — today a `no-match:both` that
                # yields the mark anyway — is touched, and it yields the mark.
                entry_px = _fill_px if _meas else mark
            # visible to the rest of THIS cycle: the cap check above and the
            # MAX_OPEN slot count must both see what we just opened.
            pos[sym] = {"size": size if is_long else -size, "entry": entry_px}
            meta[sym] = {"lens": lens, "opened": iso(t_now), "clip": clip,
                         "entry": entry_px,
                         # [(so)] I22 receipt — the brain scale in force when
                         # this clip was set. `clip` alone cannot say whether a
                         # small position was a calm book (vol_clip), a fleet
                         # drawdown (gov) or the brain, and those are three
                         # different findings.
                         "brain_mult": bmult,
                         "accrued_to": iso(t_now), "funding_paid": 0.0,
                         "evidence": ev,
                         # [2026-07-22 FLAP FIX] the bars priced at entry
                         # govern this trade — see pos_bars/entry_bars.
                         "bars": entry_bars()}
            opened_syms.add(sym)
            opened_lenses.add(lens)
            slot_census["opened"] += 1
            print(f"[ticket-taker] {iso(t_now)} OPEN "
                  f"{'long' if is_long else 'SHORT'} {sym} ({lens}) "
                  f"${clip}{'' if bmult == 1.0 else f' (brain {bmult:.2f}x)'}"
                  f" @ {entry_px} (range {round(ranges.get(sym) or 0, 1)}%) "
                  f"evidence={ev}")

    # [(dv)] persist the up-regime cache for the next run-once boot — same gate
    # as the load; the helper itself skips an empty cache, so this never writes
    # a row on an arm that took no candle reads.
    if BULL_MODE and "breakout" in _allowed:
        save_upregime_cache(store, BOT_ROW, t_now.timestamp())

    # 4) persist + publish
    if dry_run:
        equity = broker.equity()
        pnl_abs = equity - START_EQUITY
        pnl_pct = equity / START_EQUITY - 1.0
        store.save_state(STATE_KEY, {"broker": broker.to_state(), "meta": meta,
                                     "stats": stats, "sl_block": sl_block})
    else:
        # re-read AFTER trading: the loop-top print fed the rails, this one is
        # what the row reports. A failed re-read keeps the loop-top value
        # rather than publishing a hole.
        try:
            equity = account_value()
        except Exception:  # noqa: BLE001
            pass
        # [2026-07-21 AUDIT FIX] fold AGAIN before persisting: the guard can
        # record a capital move on the two LATER same-cycle reads (the rails'
        # confirm_daily_loss re-read and the line above) — a run-once process
        # that only folded at loop-top exited with those moves un-persisted,
        # so the next run's fresh guard had lost them and the P&L baseline
        # silently absorbed the operator's deposit as "trading profit".
        _cap_delta2 = _fold_capital_moves()
        # [2026-07-23] a move detected on those LATER reads lands after the rail
        # already ran this cycle — shift day_start now and persist it (below) so
        # the next cycle restores a baseline still on raw footing with equity.
        # Without this the move reaches the DISPLAY ledger but never the rail
        # baseline, permanently skewing the leash by that one move.
        day_start_equity, _shifted2 = capital_adjusted_day_start(
            day_start_equity, _cap_delta2)
        if _shifted2:
            print(f"[ticket-taker] {iso(t_now)} day-start equity shifted "
                  f"${_cap_delta2:+.2f} (late capital move) -> {day_start_equity:.2f}")
        if live_baseline is None and equity is not None:
            live_baseline = equity
        # [2026-07-21 D1] capital-adjusted: deposits are the operator's money
        # moving, not trading results. Reporting-only — no rail reads pnl_abs.
        pnl_abs = ((equity - live_baseline - capital_adjust["total"]
                    - CAPITAL_ADJUST_USD)
                   if (equity is not None and live_baseline is not None) else None)
        # [(vv)] denominator is CONTRIBUTED capital (baseline + deposits),
        # matching the pattern in lighter_avo_live_bot.py:1486.
        _contrib = (live_baseline + capital_adjust["total"]
                    + CAPITAL_ADJUST_USD) if live_baseline is not None else None
        pnl_pct = ((pnl_abs / _contrib)
                   if (pnl_abs is not None and _contrib and _contrib > 0)
                   else None)
        # [2026-07-17 AUDIT] The meta WRITE's return was discarded. save_state
        # "Never raises" — it returns False (bot_pnl_store.py:222). So a write
        # that failed after a successful market_open lost that position's meta
        # SILENTLY AND FOREVER: next cycle the venue reports a position we have
        # no record of, and it is indistinguishable from a stranger. Before the
        # guard above was scoped that meant a PERMANENT strand; it is still the
        # one path that manufactures an unstoppable position out of nothing but
        # a DB blip. We cannot retroactively remember what we failed to write —
        # but we can refuse to let it pass unnoticed, so the operator finds it
        # by page rather than by reading the P&L.
        if not store.save_state(LIVE_STATE_KEY, {
                "initial_equity": live_baseline, "meta": meta, "stats": stats,
                "capital_adjust": capital_adjust, "sl_block": sl_block,
                "day_start": {"day": cur_day, "equity": day_start_equity}}):
            store.set_status(BOT_ROW, "error")
            print(f"[ticket-taker] {iso(t_now)} CRITICAL: live state WRITE "
                  f"FAILED — {len(meta)} position(s) worth of meta (entry clip, "
                  f"lens, max-hold clock) did NOT persist. If the process dies "
                  f"before the next successful write, those positions become "
                  f"unattributable and lose their stop/max-hold until you "
                  f"reconcile bot_state['{LIVE_STATE_KEY}'].meta by hand. "
                  f"Held: {sorted(meta)}", flush=True)
    store.publish(
        BOT_ROW, status="online",
        equity=(round(equity, 2) if equity is not None else None),
        pnl_abs=(round(pnl_abs, 2) if pnl_abs is not None else None),
        pnl_pct=(round(pnl_pct, 6) if pnl_pct is not None else None),
        open_trades=len(pos),
        closed_trades=stats["closed"], wins=stats["wins"], losses=stats["losses"],
        extra={"venue": TT_VENUE,
               "strategy": f"scout tickets ({'live' if live else 'shadow'})",
               # [2026-07-24 (df)] the RUNNING process's OWN bull-mode read —
               # emit it so enablement is verifiable by published output, not by
               # "the env var is set on the service" (self-describing-labels-lie:
               # a var on the service does not prove the process read it as on).
               "bull": BULL_MODE,
               # [2026-07-24 (dh)] the RUNNING process's OWN effective RISK CONFIG
               # — the slot count and the SafetyRails notional cap it is actually
               # using. Published so an operator env change (TT_MAX_OPEN,
               # LIGHTER_TICKET_TAKER_MAX_NOTIONAL) is verifiable by output, and
               # so a config-as-code override that silently beats the env var is
               # caught (railway-config-as-code-overrides-env).
               "max_open": MAX_OPEN,
               # [(uo)] WHICH CONSTRAINT BINDS. `slots_full > 0` is the only
               # evidence that raising MAX_OPEN would buy trades this book has
               # already earned; `lens_once > 0` says the per-lens-per-cycle
               # throttle is the binder instead and slots would change nothing.
               # Reported, never a gate. A cycle that never reached the entry
               # loop (stale scout / stress veto) publishes the zeroed census
               # rather than the previous cycle's, so quiet is never mistaken
               # for full.
               "slot_census": slot_census,
               "cap_usd": (rails.max_notional if rails is not None else None),
               # D1: total capital excluded from pnl_abs — self-describing
               **({"capital_adjust": round(capital_adjust["total"]
                                           + CAPITAL_ADJUST_USD, 2)}
                  if live else {}),
               "open_pos": [{"pair": f"{s}/USDC",
                             "tag": (("long-" if pos[s]["size"] > 0 else "short-")
                                     + (meta.get(s) or {}).get("lens", "ticket"))}
                            for s in pos],
               "scout_fresh": fresh, "stress_veto": stressed,
               # [2026-08-13 (lw)] THE ENTRY VETOES, PUBLISHED — the actuator
               # standing between this book and a measured-losing lens was
               # visible ONLY in container logs. Measured the day this shipped:
               # the LIVE arm's sole lens (`divergence`) crossed its own
               # realised bar at 11-Aug 14:18Z and answering "is the real-money
               # book halted?" required `railway logs`, because /pnl.json
               # carried `stress_veto`, `bars` and `tuned` but nothing about
               # the veto that actually STOPS entries.
               #
               # This is I13's shape pointed at an ACTUATOR rather than an
               # organ: self-reporting covers what the loop DOES, and a gate
               # that silently stops gating is byte-identical from outside to
               # one that is correctly quiet. `lens_veto: []` now means
               # "evaluated, nothing vetoed"; the key's ABSENCE means a
               # container too old to publish it. Those two readings were the
               # same reading before this line existed.
               #
               # `lens_evidence` ships the numbers the verdict was computed
               # from, so a reader can tell a veto from a near-miss without
               # re-deriving anything (the (li) `base_regime` lesson: a bare
               # verdict cannot be distinguished from a vacuous one) — and
               # `coin_veto` carries each coin's OWN reason, not a bare list,
               # per the same I8 rule its log line already follows.
               #
               # PUBLISH-ONLY: every value here was already computed and used
               # by the entry loop above. No decision changes.
               "lens_veto": sorted(lens_vetoed),
               "lens_evidence": {k: {"n": n,
                                     "mean_pct": round(m, 3),
                                     "t": round(t, 2)}
                                 for k, (n, m, t) in sorted(realised.items())},
               "coin_veto": {c: coin_vetoed[c] for c in sorted(coin_vetoed)},
               # the bars actually in force this cycle (growth-rail visible)
               "bars": {lever: globals()[attr] for lever, attr in TUNABLE},
               "tuned": sorted(moved)})
    # [2026-08-05] MTM EQUITY SERIES — ranked-plan item ② (4-Aug review): the
    # (ia)/(iz) drawdown bar reads bot_state_history['<bot>:equity'] and BOTH
    # taker arms were dark on it. `equity` is this arm's own MTM number
    # (shadow: broker.equity(); live: the venue's account value — a failed
    # live read leaves it None and snapshot_equity no-ops rather than write a
    # hole). NOTE the LIVE container only picks this up at the next
    # [deploy-live-taker] marker push — code-in-main is not code-in-container;
    # the shadow arm auto-deploys with freqtrade-bots.
    store.snapshot_equity(BOT_ROW, equity, len(pos), pnl_abs)
    print(f"[ticket-taker] {iso(t_now)} equity "
          f"{equity if equity is None else round(equity, 2)} "
          f"open {len(pos)}/{MAX_OPEN} closed {stats['closed']} "
          f"({stats['wins']}W/{stats['losses']}L) scout_fresh={fresh}")


# ---------------------------------------------------------------------------


def selftest():
    print("Running Ticket Taker offline self-test...\n")
    # conviction bars (incl. the divergence lens)
    tk = {"breakout": [{"sym": "A", "range_pos": 0.96, "vol_m": 2.0},
                       {"sym": "B", "range_pos": 0.91, "vol_m": 2.0}],   # below bar
          "dip": [{"sym": "C", "range_pos": 0.04},
                  {"sym": "D", "range_pos": 0.08}],                      # below bar
          "momentum": [{"sym": "E", "chg_pct": 6.0, "vol_m": 3.0},
                       {"sym": "F", "chg_pct": 6.0, "vol_m": 1.0}],      # thin
          # [2026-07-17 BASIS FIX] fixture /8 with DIV_GAP_PP (500 -> 62.5):
          # G clears the bar, H sits below it. Intent pinned, not digits.
          "divergence": [{"sym": "G", "side": "short", "gap_pct": 87.5},
                         {"sym": "H", "side": "long", "gap_pct": -43.75}]}  # below bar
    picks = incredible(tk)
    assert [(l, t["sym"]) for l, t in picks] == \
        [("breakout", "A"), ("dip", "C"), ("momentum", "E"),
         ("divergence", "G")], picks

    # exit ladder — long and short
    t0 = now()
    from datetime import timedelta
    assert exit_reason(100.0, 104.1, t0, t0) == "tp"
    assert exit_reason(100.0, 96.9, t0, t0) == "sl"
    assert exit_reason(100.0, 101.0, t0 - timedelta(hours=49), t0) == "hold"
    assert exit_reason(100.0, 101.0, t0, t0) is None
    assert exit_reason(100.0, 95.9, t0, t0, is_long=False) == "tp"   # short profits down
    assert exit_reason(100.0, 103.1, t0, t0, is_long=False) == "sl"

    # [2026-07-22 FLAP FIX] the bars priced at entry govern the trade.
    # A position stamped under a WIDER sl (-0.04) does NOT book "sl" when the
    # module bar has snapped back to -0.03 — the measured 9/22 flap class.
    _wide = {"bars": {"tp": 0.06, "sl": -0.04, "max_hold_h": 72}}
    assert pos_bars(_wide) == (0.06, -0.04, 72.0)
    assert exit_reason(100.0, 96.5, t0, t0, bars=pos_bars(_wide)) is None, \
        "-3.5% under a grandfathered -4% bar -> still holding, no gap booked"
    assert exit_reason(100.0, 95.9, t0, t0, bars=pos_bars(_wide)) == "sl", \
        "the grandfathered bar itself still fires"
    assert exit_reason(100.0, 101.0, t0 - timedelta(hours=50), t0,
                       bars=pos_bars(_wide)) is None, \
        "grandfathered 72h hold outlives the module's 48h"
    # fail-safe: unstamped/legacy/junk positions behave exactly as before
    assert pos_bars({}) == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H)
    assert pos_bars(None) == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H)
    assert pos_bars({"bars": {"tp": "x"}}) == \
        (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H), "junk stamp -> current bars"
    assert pos_bars({"bars": {"tp": -0.06, "sl": 0.04, "max_hold_h": 72}}) \
        == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H), "nonsense signs -> current"
    # kill switch: LEVER_GRANDFATHER=off reverts behavior to close-time bars
    global LEVER_GRANDFATHER
    _lg = LEVER_GRANDFATHER
    LEVER_GRANDFATHER = False
    assert pos_bars(_wide) == (TAKE_PROFIT, STOP_LOSS, MAX_HOLD_H), \
        "switch off -> stamps ignored, pre-fix behavior"
    LEVER_GRANDFATHER = _lg
    # entry_bars stamps every TUNABLE the trade was admitted/priced under
    assert set(entry_bars()) == {"tp", "sl", "max_hold_h", "div_gap_pp",
                                 "div_vol_m", "dip_range", "brk_range",
                                 "momo_chg"}

    # accounting round-trip incl. funding drag (long pays, short receives)
    b = PaperBroker(start_equity=1000.0, fee_bps=4.0)
    b.open("A", True, 0.5, 100.0)           # $50 clip
    b.mark("A", 105.0)
    drag = 0.5 * 105.0 * 0.0001 * 10        # signed: long, +1bp/h, 10h -> pays
    b.fees += drag
    pnl = b.close("A", 105.0)
    assert abs(pnl - 2.5) < 1e-9
    exp = 1000.0 + 2.5 - (0.5*100*0.0004) - (0.5*105*0.0004) - drag
    assert abs(b.equity() - exp) < 1e-9, (b.equity(), exp)
    b2 = PaperBroker(start_equity=1000.0, fee_bps=4.0)
    b2.open("S", False, 0.5, 100.0)
    credit = (-0.5) * 100.0 * 0.0001 * 10   # signed: SHORT under +rate -> credit
    b2.fees += credit
    assert credit < 0 and b2.fees < 0.5*100*0.0004, "short must be credited"

    # constant-risk sizing: calm books size up, wild books size down, bounded
    assert vol_clip(None) == CLIP_USD, "no range data -> fallback clip"
    assert vol_clip(2.0) == CLIP_MAX, "calm 2%-range book hits the cap"
    # [(td)] pins updated with RISK_USD 1.5 -> 3.0: the formula is unchanged
    # (risk / half-range), only the budget doubled.
    assert abs(vol_clip(10.0) - 60.0) < 1e-9, "10% range -> $60 (3.0/5%)"
    assert abs(vol_clip(20.0) - 30.0) < 1e-9, "20% range -> $30"
    assert vol_clip(60.0) == CLIP_MIN, "wild book floors at CLIP_MIN"

    # [2026-07-17 RUN-ONCE KILL SEMANTICS] the boot gate: the cap refuses, the
    # kill switch must NOT (it has to reach the flatten). The negative fixture
    # is the one that matters — if this ever starts refusing on an armed kill
    # switch, a live taker abandons its book instead of closing it.
    class _R:
        def __init__(self, cap): self.max_notional = cap
    assert live_boot_gate(_R(None), live=True), "live with NO cap must refuse"
    assert live_boot_gate(_R(150.0), live=True) is None, "live with a cap proceeds"
    # the kill switch is NOT a boot gate here — armed or not, the gate is the
    # cap alone, so main() reaches kill_check() -> _flatten_all() -> halt.
    _prev = os.environ.get("REAL_MONEY_KILL")
    os.environ["REAL_MONEY_KILL"] = "ARMED"
    try:
        from venues.safety import kill_switch_armed
        assert kill_switch_armed() is True, "fixture must actually arm the switch"
        assert live_boot_gate(_R(150.0), live=True) is None, \
            ("an ARMED kill switch must NOT refuse the boot of a run-once bot — "
             "it must reach _flatten_all() and CLOSE the book, not strand it")
    finally:
        if _prev is None:
            os.environ.pop("REAL_MONEY_KILL", None)
        else:
            os.environ["REAL_MONEY_KILL"] = _prev
    # shadow never needs a cap
    assert live_boot_gate(_R(None), live=False) is None

    # [2026-07-16 ZOMBIE GUARD] delist give-up clock
    _t = now()
    assert delist_due(iso(_t - timedelta(hours=DELIST_GIVEUP_H + 1)), _t) is True
    assert delist_due(iso(_t - timedelta(hours=1)), _t) is False
    assert delist_due("garbage", _t) is False and delist_due(None, _t) is False

    # [2026-07-17 BASIS FIX] Lighter quotes funding per 8h; the old code
    # accrued `rate * hours` = 8x.
    #
    # HONEST SCOPE — this block PINS THE ARITHMETIC, it does NOT detect the
    # bug. Verified by mutation: re-introduce `rate * hours` in main() and
    # these assertions still pass, because they exercise funding_basis (which
    # has its own selftest) rather than the CALL SITE. The accrual is inline
    # in main()'s loop, so the only real detector is --selftest-live (tests 6
    # and 9), which drives that loop and caught the mutation immediately.
    # Left here as the worked example of the true numbers; do not mistake it
    # for the guard.
    _true = 1.0 * 100.0 * funding_basis.to_hourly(8e-4, "lighter") * 8.0
    assert abs(_true - 0.08) < 1e-12, _true
    assert abs(1.0 * 100.0 * 8e-4 * 8.0 - 0.64) < 1e-12    # what the bug paid
    assert abs(_true * funding_basis.LIGHTER_LEGACY_APR_FACTOR - 0.64) < 1e-12
    # a SHORT still gets the credit, and it is the true-sized one
    _short = -1.0 * 100.0 * funding_basis.to_hourly(8e-4, "lighter") * 8.0
    assert _short < 0 and abs(_short + 0.08) < 1e-12, _short

    # ---- LIVE LENS ALLOW-LIST — fail-CLOSED, and the negative fixture ------
    # A guard that never fires is not a guard (adversarial-verify-3-lens).
    assert allowed_lenses("lighter_live") == {"divergence"}, allowed_lenses("lighter_live")
    assert allowed_lenses("lighter_shadow") == ALL_LENSES   # control arm grades all 4
    assert allowed_lenses("lighter_paper") == ALL_LENSES
    # an UNKNOWN mode must not silently widen live (it is not "lighter_live",
    # so it gets the shadow set — and TT_VENUE is validated against TT_MODES
    # before this is ever reached)
    assert allowed_lenses("") == ALL_LENSES

    # ---- (hr) THE SPREAD GATE IS ON BY DEFAULT --------------------------
    # The live service sets this env explicitly; the SHADOW service does not,
    # so the arm that GRADES this book had the gate OFF and was admitting
    # books the money arm would never touch. Measured: at 20bps it refuses 43
    # of 46 BOT/USDC entries — the churn that poisoned 45 of 98
    # short-divergence rows. A default of 0 here is a grading error, not a
    # neutral choice.
    assert SPREAD_GATE_BPS == 20.0, SPREAD_GATE_BPS
    # ...and it must still be RESTRICT-ONLY and FAIL-OPEN: an unreadable book
    # blocks nothing (the delisted case is owned by other guards).
    assert spread_gate_blocks(45.0, 20.0) is True
    assert spread_gate_blocks(12.0, 20.0) is False
    assert spread_gate_blocks(None, 20.0) is False, "unknown spread must not block"
    assert spread_gate_blocks(999.0, 0.0) is False, "gate off = never blocks"

    # ---- (hm) THE BASIS INVARIANT: a _tp cannot book a loss --------------
    # Reproduces the BOT/USDC shape exactly: the exit rule fired on a mark
    # 7.4% away from the book the P&L was booked against, so the reason is
    # honest and the row is still a contradiction.
    def _contra(reason, net, drag, fees):
        if reason == "tp" and net < -abs(drag) - fees - 1e-9:
            return "tp_booked_a_loss"
        if reason == "sl" and net > abs(drag) + fees + 1e-9:
            return "sl_booked_a_profit"
        return None
    assert _contra("tp", -0.60, 0.0, 0.0) == "tp_booked_a_loss"   # the BOT shape
    assert _contra("sl", +0.42, 0.0008, 0.0) == "sl_booked_a_profit"  # CXMT
    # a HEALTHY row must stay silent, or the detector is noise
    assert _contra("tp", +2.17, 0.0, 0.01) is None
    assert _contra("sl", -1.17, 0.0, 0.01) is None
    assert _contra("hold", -0.60, 0.0, 0.0) is None   # only tp/sl are claims
    assert _contra("trail", +0.60, 0.0, 0.0) is None
    # funding and fees are EXCUSED, not evidence: a short CREDITS funding, so a
    # tp that lands slightly negative purely from drag+fees is not a basis bug
    assert _contra("tp", -0.05, 0.04, 0.02) is None
    assert _contra("tp", -0.30, 0.04, 0.02) == "tp_booked_a_loss"
    # exactly at the boundary is not a contradiction (float-safe)
    assert _contra("tp", -0.06, 0.04, 0.02) is None

    # ---- LIVE SIDE ALLOW-LIST (hj) — the twin, same fail-closed contract ----
    # THE INCIDENT THIS PINS: the live arm filled 12 `long-divergence` closes
    # (of 25 total) up to 2026-07-24, and the only thing that stopped it was
    # TT_BULL_MODE flipping on — an env var defaulting to "off".
    assert allowed_sides("lighter_live", "divergence") == {"short"}
    # the shadow arm MUST keep both sides — it is what grades the live rule
    assert allowed_sides("lighter_shadow", "divergence") == ALL_SIDES
    assert allowed_sides("lighter_paper", "breakout") == ALL_SIDES
    assert allowed_sides("", "divergence") == ALL_SIDES      # unknown != live
    # FAIL-CLOSED: a lens with no deliberate side decision fills NOTHING live.
    # Adding a lens to LIVE_LENSES must be two explicit edits, not one.
    assert allowed_sides("lighter_live", "breakout") == frozenset()
    assert allowed_sides("lighter_live", "dip") == frozenset()
    assert allowed_sides("lighter_live", "nonesuch") == frozenset()
    # every lens real money may fill MUST carry a side decision — this is the
    # assertion that turns red if LIVE_LENSES grows and LIVE_SIDES does not
    assert all(allowed_sides("lighter_live", l) for l in LIVE_LENSES), LIVE_LENSES
    # ...and no side decision may name a side that is not a real side
    assert all(s <= ALL_SIDES for s in LIVE_SIDES.values()), LIVE_SIDES
    # THE INDEPENDENCE CLAIM, asserted rather than described: the gate must not
    # move when BULL_MODE does. A fixture that only ran at the current value
    # would prove nothing about the config that caused the incident.
    _wb = globals()["BULL_MODE"]
    try:
        for _bm in (True, False):
            globals()["BULL_MODE"] = _bm
            assert allowed_sides("lighter_live", "divergence") == {"short"}, _bm
            assert allowed_sides("lighter_shadow", "divergence") == ALL_SIDES, _bm
    finally:
        globals()["BULL_MODE"] = _wb
    # side_of() must agree with the entry loop's own is_long derivation, or
    # belt and braces guard different values
    assert side_of({"side": "short"}) == "short"
    assert side_of({"side": "long"}) == "long"
    assert side_of({}) == "long" and side_of(None) == "long"   # default long
    assert side_of({"side": "SHORT"}) == "long"   # exact match, as is_long does
    for _t_ in ({"side": "short"}, {"side": "long"}, {}, {"side": None}):
        assert (side_of(_t_) == "long") is (_t_.get("side", "long") != "short")

    # THE POINT: a DARK brain vetoes NOTHING (fail-open by design), and the
    # allow-list must hold anyway. This is the fixture that proves live cannot
    # re-acquire a rejected lens when the brain goes down.
    # [2026-07-21 IMB-24] the veto's evidence basis is EPISODES when v3
    # fields are present, raw fallback otherwise:
    # raw-only payload (v2 relapse) — old rule verbatim
    assert vetoed_lenses({"m": {"n4h": 80, "avg4h_pct": -1.0, "hit4h": 0.3}}) == {"m"}
    assert vetoed_lenses({"m": {"n4h": 50, "avg4h_pct": -1.0, "hit4h": 0.3}}) == set()
    # episode payload — the serial-correlation case IMB-24 exists for: a lens
    # clearing the raw floor 16x over on too few independent episodes/symbols
    # no longer clears the floor…
    assert vetoed_lenses({"m": {"n4h": 1202, "eps4h": 20, "n_syms": 15,
                                "eavg4h_pct": -0.95, "ehit4h": 0.29}}) == set()
    assert vetoed_lenses({"m": {"n4h": 1202, "eps4h": 34, "n_syms": 8,
                                "eavg4h_pct": -0.95, "ehit4h": 0.29}}) == set()
    # …while real episode evidence vetoes on the DEDUP'D grade
    assert vetoed_lenses({"m": {"n4h": 1202, "eps4h": 117, "n_syms": 29,
                                "eavg4h_pct": -0.30, "ehit4h": 0.427}}) == {"m"}
    # the measured 21-Jul dip flip: the EPISODE number wins when present.
    # [2026-08-01 (ij)] REBUILT. The original contrast was raw hit4h 0.505
    # (allowed) vs episode ehit4h 0.495 (vetoed) — a contrast that existed ONLY
    # because the old rule required `hit < 0.5`. Expectancy-only makes both
    # bases agree here (both avg are negative), so that fixture no longer
    # discriminates between them and would pass vacuously. The property under
    # test is unchanged, so the fixture now disagrees on EXPECTANCY: raw says
    # the lens makes money, episodes say it loses.
    _dip = {"n4h": 6072, "avg4h_pct": +0.061, "hit4h": 0.505,
            "eps4h": 760, "n_syms": 110, "eavg4h_pct": -0.053, "ehit4h": 0.495}
    assert vetoed_lenses({"dip": _dip}) == {"dip"}, "the episode grade must win"
    assert vetoed_lenses({"dip": {k: v for k, v in _dip.items()
                                  if not k.startswith(("e", "n_s"))}}) == set(), \
        "with no episode fields the RAW grade decides, and it is positive"

    # ---- (ij) EXPECTANCY ONLY — win rate is not a bar --------------------
    # THE DEFECT: `avg < 0 AND hit < 0.5` made a money-LOSING lens unvetoable
    # whenever it won slightly more than half its bets. Measured on the live
    # payload: `dip` at eavg -0.027 / ehit 0.526 and `divergence/short` — the
    # LIVE book's only lens — at -0.155 / 0.502, escaping by 0.002. Same
    # non-sequitur `(fk)` removed from the GO-LIVE GATE on 29-Jul: win rate is
    # orthogonal to expectancy, and carry wins 38.8% while being the best book
    # in the fleet.
    _loser_hi_hit = {"eps4h": 900, "n_syms": 100, "eavg4h_pct": -0.027,
                     "ehit4h": 0.526}
    assert vetoed_lenses({"dip": _loser_hi_hit}) == {"dip"}, \
        "a lens that LOSES MONEY must be vetoed however often it wins"
    # …and the mirror image must NOT happen: positive expectancy at a LOW hit
    # rate is the carry shape (lose often, win big) and must keep trading.
    _winner_lo_hit = {"eps4h": 900, "n_syms": 100, "eavg4h_pct": +0.026,
                      "ehit4h": 0.480}
    assert vetoed_lenses({"breakout": _winner_lo_hit}) == set(), \
        "positive expectancy at a low hit rate is the carry shape, not a loser"
    # the kill switch restores the pre-(ij) conjunction exactly
    globals()["LEGACY_HIT_GATE"] = True
    try:
        assert vetoed_lenses({"dip": _loser_hi_hit}) == set()
        assert vetoed_lenses({"m": {"eps4h": 900, "n_syms": 100,
                                    "eavg4h_pct": -0.5, "ehit4h": 0.4}}) == {"m"}
    finally:
        globals()["LEGACY_HIT_GATE"] = False

    # ---- (ij) REALISED CLOSES ARE SENIOR to the 4h forward proxy ---------
    # The taker holds a BRACKET, not 4h. (dm) already found the forward grade
    # "misjudges" a lens and built a bespoke realised-closes veto for
    # 'breakoutup'; this generalises it. MEASURED the day it shipped: the
    # forward grade called divergence/short -0.155% while that lens's own 16
    # live closes read +0.558% — the proxy was about to halt the live book.
    _fwd_bad = {"divergence": {"eps4h": 900, "n_syms": 90,
                               "eavg4h_pct": -0.155, "ehit4h": 0.502}}
    assert vetoed_lenses(_fwd_bad) == {"divergence"}, "forward-only: vetoed"
    assert vetoed_lenses(_fwd_bad, realised={"divergence": (16, +0.558, +0.57)}) \
        == set(), "its OWN closes are positive — the proxy must not halt it"
    # senior in BOTH directions: a realised loser is vetoed even when the
    # forward proxy likes it.
    _fwd_ok = {"dip": {"eps4h": 900, "n_syms": 90,
                       "eavg4h_pct": +0.10, "ehit4h": 0.60}}
    assert vetoed_lenses(_fwd_ok) == set()
    assert vetoed_lenses(_fwd_ok, realised={"dip": (13, -1.162, -2.66)}) == {"dip"}
    # below the sample floor the realised verdict does NOT decide — too thin
    assert vetoed_lenses(_fwd_ok, realised={"dip": (4, -2.485, -2.97)}) == set()

    # ---- (kq) A `hold` EXIT IS A REALISED CLOSE, NOT AN OPEN POSITION ------
    # THE INCIDENT: `realised_lens_evidence` skipped `exit_reason == "hold"`,
    # believing those rows were open positions carrying an unrealised mark.
    # They are not: `fetch_paper_trades` reads only the CLOSED ledger and
    # hardcodes `is_open: False`, and the shadow arm's 165 rows carry 165
    # DISTINCT trade_ids with zero duplicate (pair, opened_at) groups. `hold`
    # is simply what `exit_reason()` returns when no bracket condition fired.
    # It discarded 22% of the book's realised record, BY EXIT PATH, and the
    # two tuples immediately above are the same lens: (13, -1.162, -2.66) is
    # `dip`'s full record — the number I14 itself quotes — while the filter
    # produced (4, -2.485, -2.97), which this file asserts does NOT veto. So
    # the fleet's only statistically significant taker loser was escaping its
    # own veto by being truncated below the sample floor.
    _hold_rows = [
        {"bot": "b", "enter_tag": "long-dip", "exit_reason": "hold",
         "profit_ratio": -0.02, "is_open": False},
        {"bot": "b", "enter_tag": "long-dip", "exit_reason": "sl",
         "profit_ratio": -0.03, "is_open": False},
        # a genuinely OPEN row must STILL be excluded — that half is unchanged
        {"bot": "b", "enter_tag": "long-dip", "exit_reason": "hold",
         "profit_ratio": +9.99, "is_open": True},
    ]
    _ev = realised_lens_evidence(_hold_rows, "b")
    assert _ev["dip"][0] == 2, \
        f"a `hold` close is realised evidence and must count: {_ev}"
    assert _ev["dip"][1] < 0, "the open row's +9.99 must not leak in: %s" % (_ev,)
    # and the exclusion that IS correct still holds on its own
    assert realised_lens_evidence(
        [{"bot": "b", "enter_tag": "long-dip", "exit_reason": "tp",
          "profit_ratio": 0.01, "is_open": True}], "b") == {}, \
        "an OPEN position carries an unrealised mark and may never be graded"
    # a realised loss that is merely NOISY does not veto: the shadow arm is a
    # grading instrument and a veto on noise ends the grade before it starts
    assert vetoed_lenses(_fwd_ok, realised={"dip": (30, -0.4, -0.5)}) == set()

    # ---- (fn) SIDE-AWARE VETO — the pooled grade is not this arm's grade ----
    # Fixture built from the MEASURED 200h tape: pooled divergence fails the bar
    # (ehit 0.483 / eavg -0.093) while the SHORT side the bull-mode arm actually
    # trades passes (0.513 / +0.139) and the LONG side is what drags it under
    # (0.470 / -0.199).
    _div = {"eps4h": 1006, "n_syms": 90, "eavg4h_pct": -0.093, "ehit4h": 0.483,
            "by_side": {
                "long": {"eps4h": 692, "n_syms": 74,
                         "eavg4h_pct": -0.199, "ehit4h": 0.470},
                "short": {"eps4h": 314, "n_syms": 45,
                          "eavg4h_pct": 0.139, "ehit4h": 0.513}}}
    # pooled verdict, i.e. every consumer that does NOT pass `sides`: unchanged
    assert vetoed_lenses({"divergence": _div}) == {"divergence"}
    # the bull-mode arm trades short-divergence only -> graded on the short side
    assert vetoed_lenses({"divergence": _div},
                         sides={"divergence": "short"}) == set()
    # ...and it CUTS BOTH WAYS: an arm restricted to the LONG side is vetoed on
    # the long grade even though a healthier pool might have carried it. This is
    # the assertion that stops (fn) from being a one-directional loosening.
    _healthy = dict(_div, eavg4h_pct=0.120, ehit4h=0.540)
    assert vetoed_lenses({"divergence": _healthy}) == set()
    assert vetoed_lenses({"divergence": _healthy},
                         sides={"divergence": "long"}) == {"divergence"}
    # FAIL-SAFE to the pooled rule in every degraded case
    _nosub = {k: v for k, v in _div.items() if k != "by_side"}
    assert vetoed_lenses({"divergence": _nosub},
                         sides={"divergence": "short"}) == {"divergence"}
    _thin = dict(_div, by_side={"short": dict(_div["by_side"]["short"],
                                              eps4h=3, n_syms=1)})
    assert vetoed_lenses({"divergence": _thin},          # sub-floor unmet
                         sides={"divergence": "short"}) == {"divergence"}
    assert vetoed_lenses({"divergence": _div},           # side absent from block
                         sides={"divergence": "sideways"}) == {"divergence"}
    # restricted_sides() derives the map from BULL_LENS_SIDES, and is EMPTY
    # (=> pooled everywhere) whenever bull mode is off
    _was = globals()["BULL_MODE"]
    try:
        globals()["BULL_MODE"] = False
        assert restricted_sides() == {}, restricted_sides()
        globals()["BULL_MODE"] = True
        _rs = restricted_sides()
        assert _rs["divergence"] == "short", _rs
        assert _rs["breakout"] == "long" and _rs["breakoutup"] == "long", _rs
    finally:
        globals()["BULL_MODE"] = _was

    _dark = vetoed_lenses({})
    assert _dark == set(), _dark                    # confirms the fail-open premise
    _live_fills = {l for l, _ in incredible(tk)
                   if l in allowed_lenses("lighter_live") and l not in _dark}
    assert _live_fills == {"divergence"}, _live_fills
    # ...while the shadow arm still fills every lens the fixture qualifies
    _shadow_fills = {l for l, _ in incredible(tk)
                     if l in allowed_lenses("lighter_shadow") and l not in _dark}
    assert _shadow_fills == {"breakout", "dip", "momentum", "divergence"}, _shadow_fills
    # and the brain stays SENIOR on top: it can still restrict divergence away
    _senior = {l for l, _ in incredible(tk)
               if l in allowed_lenses("lighter_live")
               and l not in {"divergence"}}
    assert _senior == set(), _senior

    # ---- (dm) breakoutup SELF-VETO: the brain's per-close-tag grade ----------
    # Bites ONLY on a floor-met DECISIVE reduce (mult<=0.5 at n>=floor) of the
    # bot's OWN long-breakoutup closes; mild / positive / thin / absent => open.
    _bot = "b-lshadow"

    def _sm(tag):
        return {"mults": {_bot: {"long-breakoutup": tag}}}
    assert breakoutup_self_vetoed(_sm({"mult": 0.5, "n": 30}), _bot)   # decisive
    assert breakoutup_self_vetoed(_sm({"mult": 0.5, "n": 99}), _bot)
    assert not breakoutup_self_vetoed(_sm({"mult": 0.75, "n": 99}), _bot)  # mild -> collect
    assert not breakoutup_self_vetoed(_sm({"mult": 1.5, "n": 99}), _bot)   # expand (winner)
    assert not breakoutup_self_vetoed(_sm({"mult": 0.5, "n": 29}), _bot)   # below floor
    assert not breakoutup_self_vetoed(_sm({"mult": 0.5}), _bot)            # no n field
    assert not breakoutup_self_vetoed({"mults": {_bot: {}}}, _bot)         # tag absent
    assert not breakoutup_self_vetoed({"mults": {}}, _bot)                 # bot absent
    assert not breakoutup_self_vetoed({}, _bot)                           # empty payload
    assert not breakoutup_self_vetoed(None, _bot)                         # dark brain
    # a DIFFERENT bot's bad grade never vetoes THIS bot (the live arm's empty
    # bucket can't be poisoned by the shadow twin's losses)
    assert not breakoutup_self_vetoed(_sm({"mult": 0.5, "n": 99}), "other-lighter")
    # kill switch: TT_BRKUP_VETO_MULT<=0 disables entirely
    _saved_bvm = globals()["BRKUP_VETO_MULT"]
    try:
        globals()["BRKUP_VETO_MULT"] = 0.0
        assert not breakoutup_self_vetoed(_sm({"mult": 0.5, "n": 99}), _bot)
    finally:
        globals()["BRKUP_VETO_MULT"] = _saved_bvm

    # ---- SYMBOL SPACE — the live-only stranding bug, pinned -----------------
    # This bot keys everything venue-native ("1000BONK"); LighterClient speaks
    # FLEET ("kBONK") in positions() AND in market_close()'s own lookup. The
    # round trip must close for every 1000-market or a real position is stranded
    # with no exit rule. 1000BONK was a live divergence ticket when this landed.
    for _native in ("1000BONK", "1000PEPE", "1000SHIB", "1000FLOKI",
                    "1000NOT", "1000TOSHI"):
        _f = _fleet(_native)                       # what the venue calls it
        assert _f.startswith("k"), (_native, _f)
        assert to_lighter(_f)[0] == _native, (_native, _f, to_lighter(_f)[0])
    # 1000NOT/1000TOSHI are the regression: they were absent from _EXPLICIT, so
    # to_lighter("kNOT") used to return "kNOT" — a symbol the venue does not have.
    assert to_lighter("kNOT")[0] == "1000NOT"
    assert to_lighter("kTOSHI")[0] == "1000TOSHI"
    # plain symbols must be untouched in both directions
    for _plain in ("BTC", "ETH", "SOL", "XPD", "DRAM"):
        assert _fleet(_plain) == _plain and to_lighter(_plain)[0] == _plain, _plain
    # raw-unit markets keep their size multiplier (PEPE != kPEPE)
    assert to_lighter("PEPE") == ("1000PEPE", 0.001)
    assert to_lighter("kPEPE") == ("1000PEPE", 1.0)

    # [2026-07-21] post-stop cooldown stamps: active in the future, inactive
    # in the past, fail-OPEN on junk/absent (a corrupt stamp must never
    # embargo a symbol forever)
    _ct = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    assert _sl_active(iso(_ct + timedelta(hours=1)), _ct)
    assert not _sl_active(iso(_ct - timedelta(hours=1)), _ct)
    assert not _sl_active(None, _ct) and not _sl_active("junk", _ct)

    # ---- SPREAD GATE — proactive execution-cost veto, default OFF -----------
    # A guard that never fires is not a guard; a DORMANT guard that fires by
    # default is worse. Both directions pinned + mutation-noted.
    _tight = {"bids": [(100.0, 5)], "asks": [(100.2, 5)]}   # ~20 bps
    _wide = {"bids": [(100.0, 5)], "asks": [(101.0, 5)]}    # ~99.5 bps
    assert abs(book_spread_bps(_tight) - 19.98) < 0.1, book_spread_bps(_tight)
    assert abs(book_spread_bps(_wide) - 99.50) < 0.5, book_spread_bps(_wide)
    # missing / empty / junk book -> None (the fail-open signal, never a 0 spread
    # that would read as "tight" and wave a dark book through)
    assert book_spread_bps({"bids": [], "asks": []}) is None
    assert book_spread_bps({}) is None and book_spread_bps(None) is None
    # the SHIPPED DEFAULT (threshold 0 = disabled) blocks NOTHING, even a
    # pathological quote — deleting the `threshold <= 0` short-circuit trips this.
    assert not spread_gate_blocks(9999.0, 0.0)
    assert not spread_gate_blocks(book_spread_bps(_wide), 0.0)
    # an ENABLED gate: unknown spread fails OPEN, a within-bar quote passes, an
    # over-bar quote BLOCKS — deleting the `is None` short-circuit trips the
    # fail-open assert.
    assert not spread_gate_blocks(None, 20.0)
    assert not spread_gate_blocks(19.98, 20.0)
    assert spread_gate_blocks(99.5, 20.0)
    assert spread_gate_blocks(book_spread_bps(_wide), 20.0)

    # ---- TREND EXIT — trailing-from-peak, default OFF (shadow capturability) --
    # Must be the fixed bracket byte-for-byte at TRAIL_PCT=0, and let a winner
    # RUN past the +4% cap once enabled — the whole reason it exists.
    _te, _to = 100.0, datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    _ten = _to + timedelta(hours=1)
    assert TRAIL_PCT == 0.0, TRAIL_PCT
    # DEFAULT (off): fixed bracket even when a peak is supplied
    assert exit_reason(_te, 105.0, _to, _ten, True, peak_ret=0.10) == "tp"
    assert exit_reason(_te, 96.0, _to, _ten, True, peak_ret=0.10) == "sl"
    assert exit_reason(_te, 101.0, _to, _ten, True, peak_ret=0.10) is None
    globals()["TRAIL_PCT"] = 0.06
    try:
        # peaked +10%, back to +3% -> gave back 7%>6% -> trail
        assert exit_reason(_te, 103.0, _to, _ten, True, peak_ret=0.10) == "trail"
        # peaked +10%, at +5% -> gave back 5%<6% -> RUNS (a fixed +4% TP would
        # have wrongly banked here; deleting the TP-skip regresses this)
        assert exit_reason(_te, 105.0, _to, _ten, True, peak_ret=0.10) is None
        # wide hard stop still bites; never-in-profit never trails
        assert exit_reason(_te, 92.0, _to, _ten, True, bars=(0.04, -0.07, 48), peak_ret=0.0) == "sl"
        assert exit_reason(_te, 101.0, _to, _ten, True, bars=(0.04, -0.07, 48), peak_ret=0.0) is None
        # unknown peak fails SAFE to the fixed bracket even when enabled
        assert exit_reason(_te, 105.0, _to, _ten, True, peak_ret=None) == "tp"
    finally:
        globals()["TRAIL_PCT"] = 0.0

    # ---- close-row extra: bars stamp + entry evidence ride together --------
    # [2026-07-28 REVIEW] the (di) capture must SURVIVE to the ledger row the
    # analyzer reads (`extra ? 'brk_quality'`). Mutation check: dropping the
    # evidence merge in _close_extra (or reverting _book_close to the bare
    # bars dict) turns these red.
    _cm = {"bars": {"tp": 0.04, "sl": -0.07, "max_hold_h": 24},
           "evidence": {"brk_quality": 0.42, "up_strength": 0.13}}
    _cx = _close_extra(_cm)
    assert _cx["bars"] == _cm["bars"] and _cx["bars_basis"] == "entry", _cx
    assert _cx["brk_quality"] == 0.42 and _cx["up_strength"] == 0.13, _cx
    # legacy/absent evidence degrades to exactly the old payload
    _cl = _close_extra({})
    assert set(_cl) == {"bars", "bars_basis", "policy"} and \
        _cl["bars_basis"] == "close-legacy"
    assert set(_close_extra({"bars": _cm["bars"], "evidence": "junk"})) == \
        {"bars", "bars_basis", "policy"}, "non-dict evidence must add nothing"

    # [2026-07-29 (fx)] THE POLICY STAMP. The bars stamp is byte-identical
    # across the 24-Jul bull flip, so without this a grader cannot see that the
    # bot changed WHICH SIGNALS it takes — the blind spot behind both the
    # "no edge" and the "edge is real" mis-gradings. Mutation-checked: dropping
    # the setdefault, or dropping any of the four keys, turns these red.
    _pol = _cx["policy"]
    # [2026-07-30] `ticket_top_n` joined the stamp. The four original keys
    # record the policy the TAKER ran; the candidate SET it chose from is set
    # one level up by the scout, and that supply moved 6 -> 12 on 2026-07-30.
    # Without it in the stamp a grader splitting eras "mechanically" would pool
    # across a 2x change in the arm's opportunity set with nothing in the
    # ledger to see it by — the identical defect (fx)/(gi) fixed, one level
    # upstream. Mutation-checked: dropping any key turns these red.
    # [(hj)] `sides` joined it for the same reason: the SIDE rule changed on
    # 2026-07-30 (live went divergence-SHORT-only by hard gate rather than by
    # TT_BULL_MODE), so a grader pooling across that boundary would mix the
    # long and short divergence eras — precisely the pooling error that
    # retracted the alpha claim.
    assert set(_pol) == {"bull", "lenses", "sides", "venue", "max_open",
                         "ticket_top_n"}, _pol
    assert _pol["sides"] == {l: sorted(allowed_sides(TT_VENUE, l))
                             for l in sorted(allowed_lenses(TT_VENUE))}, _pol
    # every stamped lens carries a stamped side list — a lens whose sides are
    # missing or empty in the stamp is a lens no grader can era-split
    assert set(_pol["sides"]) == set(_pol["lenses"]), _pol
    assert all(_pol["sides"].values()), _pol
    # the supply must be the REGISTRY's value, never a second hardcoded copy —
    # audit_lever_bounds keeps the registry equal to the scout's real default,
    # so this is the one number that cannot drift from what the scout emits
    import fleet_tuning as _ft
    assert _pol["ticket_top_n"] == (
        _ft.LEVERS["scout.ticket_top_n"]["env_default"]), _pol
    assert _pol["bull"] is BULL_MODE and _pol["venue"] == TT_VENUE, _pol
    assert _pol["lenses"] == sorted(allowed_lenses(TT_VENUE)), _pol
    # it must record the LENS SET, which is what the flip actually changed —
    # and on the live venue that set is the allow-list, not everything
    assert sorted(allowed_lenses("lighter_live")) == ["divergence"]
    assert len(sorted(allowed_lenses("lighter_shadow"))) > 1
    # and evidence must never be able to forge it
    _cf = _close_extra({"bars": _cm["bars"], "evidence": {"policy": "EVIL"}})
    assert _cf["policy"] != "EVIL", "evidence must not clobber the policy stamp"
    # an evidence key can never clobber the bars stamp
    _cc = _close_extra({"bars": _cm["bars"],
                        "evidence": {"bars": "EVIL", "gap_pp": 9.0}})
    assert _cc["bars"] == _cm["bars"] and _cc["gap_pp"] == 9.0, _cc

    # ---- BULL DUAL-MODE gate — long-breakout(up) + short-divergence, crypto ---
    _up = {"regime": {"dir": 1}}
    _dn = {"regime": {"dir": -1}}
    _bt = lambda ls, sd, ex: bull_entry_ok(ls, sd, {**ex, "sym": "SOL"})
    # the ONLY two admitted pairs
    assert _bt("breakout", "long", _up)            # long-breakout in up-regime
    assert _bt("divergence", "short", _dn)         # short-divergence in down
    assert not _bt("divergence", "long", _up)      # long-divergence NEVER
    assert not _bt("breakout", "short", _dn)       # short-breakout NEVER
    assert not _bt("dip", "long", _up) and not _bt("momentum", "long", _up)
    # regime gate: LONG needs a CONFIRMED up; SHORT refused only INTO a confirmed up
    assert not _bt("breakout", "long", _dn)        # long in down -> skip
    assert not _bt("breakout", "long", {})         # long unstamped -> skip (fail-CLOSED)
    assert _bt("divergence", "short", {})          # short unstamped -> kept (funding screen)
    assert not _bt("divergence", "short", _up)     # short INTO confirmed up -> skip
    # crypto-only: a tokenized equity (TRADFI_BASES) is refused
    assert not bull_entry_ok("breakout", "long", {"sym": "AMD", "regime": {"dir": 1}})
    assert bull_entry_ok("divergence", "short", {"sym": "SOL", "regime": {"dir": -1}})
    # up_regime (candle-derived broad coverage): above a RISING ema -> True
    assert up_regime([float(i) for i in range(1, 40)]) is True         # monotone up
    assert up_regime([float(40 - i) for i in range(1, 40)]) is False   # monotone down
    assert up_regime([1.0, 2.0, 3.0]) is None                          # too few bars
    # the `up` override drives the gate REGARDLESS of the (absent) oracle stamp —
    # the fix that lets long-breakout fire on the ~92% of ungraded symbols
    assert bull_entry_ok("breakout", "long", {"sym": "SOL"}, up=True)
    assert not bull_entry_ok("breakout", "long", {"sym": "SOL"}, up=False)
    assert not bull_entry_ok("breakout", "long", {"sym": "SOL"}, up=None)   # unknown -> skip
    assert not bull_entry_ok("divergence", "short", {"sym": "SOL"}, up=True)  # short refused into up
    assert bull_entry_ok("divergence", "short", {"sym": "SOL"}, up=False)
    # [(dk)] 'breakoutup' is the relabelled up-regime crypto breakout: long-only,
    # crypto-only, up-confirmed (the entry loop passes up=True by construction).
    assert bull_entry_ok("breakoutup", "long", {"sym": "SOL"}, up=True)
    assert not bull_entry_ok("breakoutup", "long", {"sym": "AMD"}, up=True)   # tradfi refused
    assert not bull_entry_ok("breakoutup", "short", {"sym": "SOL"}, up=True)  # long-only
    assert "breakoutup" in ALL_LENSES and "breakoutup" not in LIVE_LENSES     # shadow-only
    # bull_exit routes 'breakoutup' to the TREND exit exactly like 'breakout'
    globals()["BULL_MODE"] = True
    try:
        assert bull_exit("breakoutup")[1] == BRK_TRAIL          # trail, not fixed
        assert bull_exit("breakoutup")[0][1] == BRK_SL          # wide stop
        assert bull_exit("divergence") == (None, 0.0)           # unchanged
    finally:
        globals()["BULL_MODE"] = False
    assert bull_exit("breakoutup") == (None, None)             # off -> module default
    # up_read: candle fetch -> up_regime, cached. The stub returns Lighter's REAL
    # candle DICT shape ({t,o,h,l,c,v}), NOT bare floats — so this exercises the
    # c["c"] extraction (a float-only stub passed green while the live dict shape
    # crashed: a stub must encode SEMANTICS, not just the method name).
    class _StubV:
        def __init__(self, cs):
            self._cs = [{"t": 0, "o": c, "h": c, "l": c, "c": c, "v": 1.0}
                        for c in cs]
        def candles(self, coin, interval, s, e): return self._cs

    class _BadV:
        def candles(self, *a):
            raise RuntimeError("candle blip")
    globals()["_UP_CACHE"] = {}
    assert up_read(_StubV([float(i) for i in range(1, 40)]), "SOL", 1.7e9) is True
    globals()["_UP_CACHE"] = {}
    assert up_read(_StubV([float(40 - i) for i in range(1, 40)]), "X", 1.7e9) is False
    globals()["_UP_CACHE"] = {}
    assert up_read(_BadV(), "SOL", 1.7e9) is None          # fetch error -> fail-CLOSED
    globals()["_UP_CACHE"] = {}
    # [(dg) FORMING-BAR DROP] up_read must ignore the still-forming daily bar. A
    # FALLING history with a spiking partial bar reads DOWN (the spike is dropped);
    # WITHOUT the drop the leaked partial bar flips it UP — so this pins the fix.
    assert up_read(_StubV([float(40 - i) for i in range(0, 38)] + [100.0]),
                   "SPIKE", 1.7e9) is False
    globals()["_UP_CACHE"] = {}
    # [(di) SCANNER SIDEKICK] up_strength: bounded [0,1], 0 when not up, >0 EXACTLY
    # when up_regime is True (same two inequalities); differentiates gentle vs steep.
    assert up_strength([1.0, 2.0, 3.0]) is None                        # too few bars
    _su = up_strength([float(i) for i in range(1, 40)])
    assert _su is not None and 0.0 < _su <= 1.0
    assert up_regime([float(i) for i in range(1, 40)]) is True          # consistent
    assert up_strength([float(40 - i) for i in range(1, 40)]) == 0.0    # down -> 0
    assert up_strength([100.0] * 40) == 0.0                            # flat -> 0
    assert (up_strength([100.0 + 0.1 * i for i in range(40)])          # gentle up ...
            < up_strength([float(i * i) for i in range(1, 41)]))       # ... < steep up
    # breakout_quality: bounded [0,1], monotone in each feature, None up-str -> 0
    assert breakout_quality(1.0, 1.0, 10.0) == 1.0                     # max
    assert breakout_quality(0.0, 0.90, 0.0) == 0.0                     # min
    assert breakout_quality(None, 0.95, 1.0) == breakout_quality(0.0, 0.95, 1.0)
    assert breakout_quality(0.9, 0.95, 1.0) > breakout_quality(0.5, 0.95, 1.0)  # up_str
    assert breakout_quality(0.5, 1.00, 1.0) > breakout_quality(0.5, 0.95, 1.0)  # range_pos
    assert breakout_quality(0.5, 0.95, 5.0) > breakout_quality(0.5, 0.95, 1.0)  # volume
    # up_read now caches the strength; up_read_strength() reads it with NO refetch,
    # and the cache-hit path still returns the tri-state after the tuple reshape.
    assert up_read_strength("NEVER") is None                          # unread -> None
    globals()["_UP_CACHE"] = {}
    assert up_read(_StubV([float(i) for i in range(1, 40)]), "UPS", 1.7e9) is True
    assert (up_read_strength("UPS") or 0.0) > 0.0                      # cached strength
    globals()["_UP_CACHE"] = {}
    assert up_read(_StubV([float(40 - i) for i in range(1, 40)]), "DNS", 1.7e9) is False
    assert up_read_strength("DNS") == 0.0
    globals()["_UP_CACHE"] = {}
    assert up_read(_BadV(), "ERRS", 1.7e9) is None
    assert up_read_strength("ERRS") is None                           # fetch failed -> None
    globals()["_UP_CACHE"] = {"HITSYM": (True, 0.5, 9.9e18)}          # pre-seeded cache
    assert up_read(None, "HITSYM", 1.7e9) is True                     # served from cache, no venue
    globals()["_UP_CACHE"] = {}
    # [(dv) CROSS-CYCLE CACHE] save -> load round-trip through a stub store: the
    # next run-once boot must be served from the persisted cache (up_read with NO
    # venue), expired entries must be dropped at BOTH ends, and a dark store must
    # seed nothing / drop nothing — never a crash.
    class _MemStore:
        def __init__(self): self.d = {}
        def save_state(self, k, v): self.d[k] = v
        def load_state(self, k): return self.d.get(k)

    class _DarkStore:
        def save_state(self, k, v): raise RuntimeError("db down")
        def load_state(self, k): raise RuntimeError("db down")
    _ms = _MemStore()
    globals()["_UP_CACHE"] = {"SOL": (True, 0.7, 2.0e9),       # live entry
                              "OLD": (False, 0.0, 1.0e9)}      # expired at save
    save_upregime_cache(_ms, "row-x", 1.7e9)
    assert "SOL" in _ms.d["row-x-upregime"]["syms"]
    assert "OLD" not in _ms.d["row-x-upregime"]["syms"], "expired must not persist"
    globals()["_UP_CACHE"] = {}                                # fresh boot
    load_upregime_cache(_ms, "row-x", 1.7e9)
    assert up_read(None, "SOL", 1.7e9) is True                 # served, no venue call
    assert up_read_strength("SOL") == 0.7                      # strength round-trips
    # an entry that EXPIRED between boots is dropped at load
    _ms.d["row-x-upregime"]["syms"]["SOL"][2] = 1.6e9
    globals()["_UP_CACHE"] = {}
    load_upregime_cache(_ms, "row-x", 1.7e9)
    assert "SOL" not in _UP_CACHE, "expired must not seed"
    # dark store: load seeds nothing, save drops silently — no crash either way
    globals()["_UP_CACHE"] = {}
    load_upregime_cache(_DarkStore(), "row-x", 1.7e9)
    assert _UP_CACHE == {}
    globals()["_UP_CACHE"] = {"SOL": (True, 0.7, 2.0e9)}
    save_upregime_cache(_DarkStore(), "row-x", 1.7e9)          # must not raise
    # junk payload shapes seed nothing (fail-safe on a corrupt row)
    _ms.d["row-x-upregime"] = {"syms": {"BAD": "junk", "ALSO": [1], "N": [True, 0.5, "x"]}}
    globals()["_UP_CACHE"] = {}
    load_upregime_cache(_ms, "row-x", 1.7e9)
    assert _UP_CACHE == {}, "junk shapes must not seed"
    globals()["_UP_CACHE"] = {}
    # exit_reason trail OVERRIDE (per-lens): divergence keeps its +4% TP cap while
    # the trend exit is on globally; breakout runs past it
    globals()["TRAIL_PCT"] = 0.06
    try:
        assert exit_reason(100.0, 105.0, _to, _ten, True, peak_ret=0.10, trail=0.0) == "tp"
        assert exit_reason(100.0, 105.0, _to, _ten, True, peak_ret=0.10, trail=0.06) is None
    finally:
        globals()["TRAIL_PCT"] = 0.0

    # [2026-07-24 (de)] The LIVE/shadow position-manager COMPOSITION: the exit
    # loop now calls bull_exit(lens) and threads (bars, peak_ret, trail) into
    # exit_reason exactly as reproduced here. Guard the composition, not just the
    # parts — this is a real-money surface (live-bots-always-in-audit-scope). A
    # breakout must run PAST the +4% cap, TRAIL off its peak, and stop at the
    # WIDE -7% breakout SL; divergence keeps its fixed reversion bracket.
    def _mgr_exit(lens, entry, mark, is_long, peak_ret, pbars):
        # mirrors main()'s exit loop EXACTLY: graft the entry-stamped max-hold
        # onto the breakout trend bars, and pass trail=0.0 (never None) when bull
        # is off so the fixed bracket holds regardless of the global TT_TRAIL_PCT.
        _eb, _et = bull_exit(lens)
        if _eb is not None:
            _eb = (_eb[0], _eb[1], pbars[2])
        _tr = _et if _et is not None else 0.0
        return exit_reason(entry, mark, _to, _ten, is_long,
                           bars=(_eb or pbars), peak_ret=peak_ret, trail=_tr)
    _pb = (0.04, -0.03, 48)                        # a normal divergence stamp
    globals()["BULL_MODE"] = True
    try:
        assert _mgr_exit("breakout", 100.0, 108.0, True, 0.10, _pb) is None   # runs past +4%
        assert _mgr_exit("breakout", 100.0, 103.5, True, 0.10, _pb) == "trail"  # give back 6%
        assert _mgr_exit("breakout", 100.0, 96.5, True, 0.0, _pb) is None     # -3.5% > wide SL
        assert _mgr_exit("breakout", 100.0, 92.9, True, 0.0, _pb) == "sl"     # -7.1% <= -7%
        assert _mgr_exit("divergence", 100.0, 104.1, True, 0.0, _pb) == "tp"  # fixed bracket
        # [(dg) FLAP-FIX] a breakout honours its ENTRY-STAMPED max-hold, not the
        # live 48h default: a 1h-old flat breakout stamped hold=1h must "hold"
        # (without the graft it reads the 48h default and does NOT exit).
        assert _mgr_exit("breakout", 100.0, 100.5, True, 0.0, (0.04, -0.03, 1)) == "hold"
    finally:
        globals()["BULL_MODE"] = False
    # MUTATION: bull OFF, the SAME breakout path hits the fixed +4% TP — proving
    # the routing (not the price path) is what let the winner run above.
    assert _mgr_exit("breakout", 100.0, 108.0, True, 0.10, _pb) == "tp"
    # [(dg) INERTNESS GUARD] with bull OFF the manager exit stays the FIXED bracket
    # even when the global TT_TRAIL_PCT>0 — the real-money exit's guard is
    # BULL_MODE, not TRAIL_PCT (else a live redeploy + a stray TT_TRAIL_PCT would
    # silently trend-exit real positions). Without the trail=0.0-when-off fix the
    # first assert 'trail's instead of None.
    globals()["TRAIL_PCT"] = 0.06
    try:
        assert _mgr_exit("divergence", 100.0, 103.5, True, 0.10, _pb) is None   # would 'trail' if leaked
        assert _mgr_exit("divergence", 100.0, 104.1, True, 0.10, _pb) == "tp"    # fixed +4% still fires
    finally:
        globals()["TRAIL_PCT"] = 0.0

    print("All Ticket Taker self-tests passed (bars incl. divergence, "
          "long/short exits, signed funding on the TRUE 8h basis, "
          "constant-risk sizing, delist give-up, LIVE lens allow-list "
          "fail-CLOSED vs a dark brain, symbol round-trip for all six "
          "1000-markets, spread gate ON by default (20bps) + fail-open, trend exit "
          "default-OFF + let-winner-run).")


# ---------------------------------------------------------------------------
# LIVE ORDER PATH — driven end-to-end against a stub venue.
#
# The live branch is REFUSED in production (evidence, not safety), so without
# this it would be code no one has ever executed — which is how the fleet got
# a "live-ready" bot that would not have placed a single order (c5924e4). The
# stub speaks LighterClient's interface and records what it was asked to do;
# no network, no signer, no money.
# ---------------------------------------------------------------------------


class _StubVenue:
    """Records orders instead of sending them. Mirrors the LighterClient
    surface the live path touches: positions / account_value / market_open /
    market_close / last_fill_detail / last_fill.

    [2026-07-17] IT MUST MIRROR `last_fill_detail`, NOT JUST `last_fill`.
    Production's LighterClient has both, and `_real_fill` prefers the detail
    API — so a stub carrying only `last_fill` sends every test down the
    LEGACY fallback branch and leaves the real production path untested. That
    is exactly how `_StubRails`, lacking `assert_can_start`, let tests 3/4 pass
    against a path production could not reach (17-Jul entry (p)). A stub that
    is missing a method does not fail — it silently tests something else."""

    def __init__(self, equity=1000.0, pos=None, fills=None, fill_reason=None,
                 echo_ids=True, cap_moves=None):
        self._equity = equity
        # [2026-07-23] guard-recorded capital moves this venue will report ONCE
        # via pop_capital_moves (the EquityGuard's real contract), so the
        # daily-loss rail's net-of-capital shift is exercised end-to-end.
        self._cap_moves = list(cap_moves or [])
        self._pos = dict(pos or {})
        self._fills = dict(fills or {})     # sym -> REAL fill px the tape returns
        self._fill_reason = fill_reason     # reason reported when there is no fill
        # echo_ids=False models THE failure this stub exists for: Lighter stops
        # echoing client_order_index back as ask_client_id/bid_client_id, so an
        # id-filtered read matches nothing while the tape itself is perfectly
        # readable. That round trip is UNPROVEN in production — the taker's only
        # two live orders predate the fill-read code — so the id working is an
        # assumption, and this is the fixture that stops it being a silent one.
        self._echo_ids = echo_ids
        self.opens, self.closes, self.value_reads = [], [], 0
        self.fail_close = set()
        self._cid = 0
        self.last_cid = None
        self.seen_client_ids = []      # what the fill read was ACTUALLY given

    def account_value(self):
        self.value_reads += 1
        return self._equity

    def candles(self, coin, interval, s, e):
        # [(dk)] the bull path calls this for a breakout up-regime read; a stub
        # missing it would fail up_read CLOSED and silently skip the relabel. Real
        # Lighter candle DICT shape. Default = monotone-UP daily closes (so a bull
        # breakout RELABELS to breakoutup); set `_candles` for a down-regime case.
        cs = getattr(self, "_candles", None)
        if cs is None:
            cs = [float(i) for i in range(1, 40)]
        return [{"t": 0, "o": c, "h": c, "l": c, "c": c, "v": 1.0} for c in cs]

    def pop_capital_moves(self):
        """Mirror EquityGuard.pop_capital_moves: return queued moves once, then
        empty. Item shape is the guard's {ts, delta, how}."""
        out, self._cap_moves = self._cap_moves, []
        return out

    def positions(self):
        return {s: dict(v) for s, v in self._pos.items() if v.get("size")}

    def market_open(self, coin, is_long, size):
        self.opens.append((coin, is_long, size))
        self._pos[coin] = {"size": size if is_long else -size,
                           "entry": self._fills.get(coin, 100.0)}
        # mirrors the real client: the order's client id comes back so the fill
        # read can name it. A stub that omits it sends the caller down the
        # id-less heuristic and leaves the exact-match path untested.
        self._cid += 1
        self.last_cid = self._cid
        return {"tx": "stub", "client_order_index": self._cid}

    def market_close(self, coin):
        if coin in self.fail_close:
            raise RuntimeError(f"stub: close {coin} refused")
        self.closes.append(coin)
        self._pos.pop(coin, None)
        self._cid += 1
        self.last_cid = self._cid
        return {"tx": "stub", "client_order_index": self._cid}

    def last_fill_detail(self, coin, is_ask, since_ts, lookback=10,
                         client_id=None):
        self.seen_client_ids.append(client_id)
        px = self._fills.get(coin)
        if px:
            if client_id is not None and not self._echo_ids:
                # The tape IS readable — our id simply is not on it. This is the
                # venue layer's real string for that (lighter_client.py:726) and
                # the reason strings are the contract `read_fill` keys its retry
                # on, so a paraphrase here would test nothing.
                return None, "no-match:both(no-match:trades)"
            return px, ("trades" if client_id is not None else "trades(approx)")
        return None, (self._fill_reason or "empty:both(stub)")

    def last_fill(self, coin, is_ask, since_ts, lookback=10, client_id=None):
        # delegates exactly as the real client does
        return self.last_fill_detail(coin, is_ask, since_ts, lookback,
                                     client_id)[0]


class _StubRails:
    """SafetyRails' surface, with the real notional_ok/daily_loss_hit rules."""

    def __init__(self, max_notional=None, killed=False, max_daily_loss=30.0):
        from venues.safety import SafetyRails
        self.max_notional = max_notional
        self.max_daily_loss = max_daily_loss
        self.killed = killed
        self.live = True
        self._real = SafetyRails.__new__(SafetyRails)
        self._real.max_notional = max_notional
        self._real.max_daily_loss = max_daily_loss
        self._real.live = True
        self.confirmed = []

    def kill_check(self):
        return self.killed

    def notional_ok(self, open_ntl, add_usd):
        return self._real.notional_ok(open_ntl, add_usd)

    def daily_loss_hit(self, day_start_equity, equity):
        return self._real.daily_loss_hit(day_start_equity, equity)

    def confirm_daily_loss(self, day_start, first_eq, pct_limit, read_equity):
        # the REAL one sleeps 60s to debounce; the rule under test here is
        # "what does the taker do once it IS confirmed", so confirm instantly.
        self.confirmed.append((day_start, first_eq))
        return True, first_eq


def _selftest_live():
    """Drive main()'s LIVE branch against the stub. Asserts the properties the
    order path exists to guarantee — every one of them a rail that has already
    cost real money somewhere in this fleet."""
    import types
    global TT_VENUE, BOT_ROW
    print("Running Ticket Taker LIVE order-path self-test (stub venue)...\n")

    _saved_env = (TT_VENUE, BOT_ROW)
    TT_VENUE, BOT_ROW = "lighter_live", BOT + "-lighter"
    # [2026-07-17] This harness rebinds the MODULE GLOBAL; the identity guard in
    # main() reads os.environ (it must — the global carries a default and so
    # cannot tell "unset" from "set to shadow"). One fixture below drives
    # _supervised() -> bare main(), which trips that guard before the crash it
    # is actually testing. Production always sets the var, so give the harness
    # one too; the guard has its own dedicated fixture in selftest().
    _saved_ttv = os.environ.get("TT_VENUE")
    os.environ["TT_VENUE"] = "lighter_live"

    # --- capture every side effect instead of hitting Postgres -------------
    captured = {"paper": [], "orders": [], "state": {}, "halts": [],
                "published": []}
    _real = {k: getattr(store, k) for k in
             ("publish_paper_trade", "publish_venue_order", "save_state",
              "load_state", "load_state_checked", "publish", "save_daily_halt",
              "load_daily_halt", "heartbeat", "claim_writer",
              "snapshot_equity")}
    store.heartbeat = lambda bot: None
    # [2026-08-04] main() now claims the writer lock and appends an MTM equity
    # sample each cycle. Stub BOTH: this harness rebinds BOT_ROW to the LIVE
    # row id, so unstubbed on an operator machine with DATABASE_URL set, the
    # fixtures below would append FICTIONAL equity samples to the live book's
    # '<bot>:equity' series — the exact series the go-live drawdown bar reads.
    # A test that can poison the gate's evidence is worse than no test.
    store.claim_writer = lambda bot, now=None: (True, None)
    store.snapshot_equity = (
        lambda bot, equity, open_trades=None, realized=None: True)
    store.publish_paper_trade = lambda bot, **kw: captured["paper"].append((bot, kw))
    store.publish_venue_order = lambda bot, **kw: captured["orders"].append((bot, kw))

    # [2026-07-17 AUDIT] These two stubs must mirror the REAL functions'
    # RETURN CONTRACTS, not just their names — a stub that gets the shape right
    # and the semantics wrong makes every green assertion below meaningless.
    #   save_state: really returns True/False and NEVER raises
    #     (bot_pnl_store.py:222-250). The old stub returned None (dict
    #     __setitem__), i.e. FALSY — so the moment main() started checking that
    #     return, every fixture would have reported a failed write. The stub was
    #     silently teaching the bot that all writes fail.
    #   load_state_checked: (ok, state) — ok=False means "I could not find out",
    #     which is NOT "no row". Unstubbed, it would have reached real Postgres
    #     from inside the selftest and returned (False, None), tripping main()'s
    #     new READ-FAILED refusal in every live fixture.
    # `captured["fail_writes"]` / `["fail_reads"]` let a fixture drive the
    # failure halves deliberately — see fixtures 11a-11c.
    captured["fail_writes"] = False
    captured["fail_reads"] = False

    def _stub_save(k, v):
        if captured["fail_writes"]:
            return False
        captured["state"][k] = v
        return True

    def _stub_load_checked(k):
        if captured["fail_reads"]:
            return (False, None)          # read FAILED — not "no row"
        return (True, captured["state"].get(k))

    store.save_state = _stub_save
    store.load_state_checked = _stub_load_checked
    store.load_state = lambda k: captured["state"].get(k)
    store.publish = lambda bot, **kw: captured["published"].append((bot, kw))
    store.save_daily_halt = lambda bot, day, eq=None: captured["halts"].append((bot, day, eq))
    store.load_daily_halt = lambda bot, day: None

    _real_fetch = globals()["fetch_marks_and_funding"]

    def _stub_market(marks=None, funding=None, ranges=None):
        globals()["fetch_marks_and_funding"] = lambda: (
            dict(marks or {}), dict(funding or {}), dict(ranges or {}))

    def _scout(tickets):
        captured["state"][SCOUT_KEY] = {
            "updated": iso(now()), "ttl_sec": 900, "tickets": tickets,
            "stress": {"med": 1.0}}

    def _boom(*_a, **_kw):
        # the REAL 17-Jul crash: LighterClient -> `import lighter` -> missing
        # wheel -> VenueError, every cycle, behind an "online" row.
        raise RuntimeError("lighter-sdk missing (pip install lighter-sdk): "
                           "No module named 'lighter'")

    try:
        # ================================================================
        # 1) ENTRY sends a REAL order — not a modelled fill
        # ================================================================
        captured["state"].clear()
        _stub_market(marks={"AAA": 100.0}, funding={}, ranges={"AAA": 6.0})
        _scout({"divergence": [{"sym": "AAA", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"AAA": 100.5})
        r = _StubRails(max_notional=150.0)
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.opens == [("AAA", False, 1.0)], v.opens  # $100 clip @ 100 ((td) 3.0/3%)
        assert len(captured["orders"]) == 1, captured["orders"]
        _o = captured["orders"][0][1]
        assert _o["shadow"] is False and _o["side"] == "sell"
        # the REAL fill (100.5) is recorded, and selling above the decision
        # price is NEGATIVE slippage = better than decided
        assert _o["px_fill"] == 100.5 and _o["px_decision"] == 100.0
        assert _o["slippage_bps"] < 0, _o["slippage_bps"]
        # live state is its OWN key, and it never writes a broker snapshot
        assert LIVE_STATE_KEY in captured["state"]
        assert STATE_KEY not in captured["state"]
        assert "broker" not in captured["state"][LIVE_STATE_KEY]
        # entry recorded at the REAL fill, not the decision price
        assert captured["state"][LIVE_STATE_KEY]["meta"]["AAA"]["entry"] == 100.5

        # ================================================================
        # 1b) [(hj)] LIVE SIDE ALLOW-LIST, end-to-end and BULL_MODE-BLIND.
        #     THE INCIDENT: 12 of this book's 25 live closes are
        #     `long-divergence`, and the only thing that stopped them was
        #     TT_BULL_MODE flipping on 24-Jul — an env var that defaults OFF.
        #     So the fixture that matters is the one that runs with BULL_MODE
        #     *off*: the exact config under which real money took the losing
        #     side. Driven through main() against the stub venue, because a
        #     unit assertion on allowed_sides() would not have caught the
        #     BULL_MODE-only wiring that caused this in the first place.
        # ================================================================
        _bm_was = globals()["BULL_MODE"]
        try:
            for _bm in (False, True):
                globals()["BULL_MODE"] = _bm
                captured["state"].clear()
                captured["orders"].clear()
                _stub_market(marks={"AAA": 100.0}, funding={},
                             ranges={"AAA": 6.0})
                # a LONG divergence ticket, otherwise identical to case 1 —
                # same symbol, same conviction, same everything but the side
                _scout({"divergence": [{"sym": "AAA", "side": "long",
                                        "gap_pct": -99.0}]})
                v = _StubVenue(equity=1000.0, fills={"AAA": 100.5})
                r = _StubRails(max_notional=150.0)
                main(_ctx={"venue": v, "rails": r, "broker": None})
                assert v.opens == [], (
                    f"long-divergence reached real money with BULL_MODE={_bm}: "
                    f"{v.opens}")
                assert captured["orders"] == [], captured["orders"]
            # ...and the SHORT still fills with BULL_MODE off, or the gate has
            # simply switched the book off rather than restricted its side.
            # A guard that blocks everything is indistinguishable from a
            # broken bot, so this half is not optional.
            globals()["BULL_MODE"] = False
            captured["state"].clear()
            captured["orders"].clear()
            _stub_market(marks={"AAA": 100.0}, funding={}, ranges={"AAA": 6.0})
            _scout({"divergence": [{"sym": "AAA", "side": "short",
                                    "gap_pct": 99.0}]})
            v = _StubVenue(equity=1000.0, fills={"AAA": 100.5})
            main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                       "broker": None})
            assert v.opens == [("AAA", False, 1.0)], v.opens   # (td) $100 clip
        finally:
            globals()["BULL_MODE"] = _bm_was

        # ================================================================
        # 2) NOTIONAL CAP is senior — the cap-breaching entry never sends
        # ================================================================
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"BBB": 100.0}, funding={}, ranges={"BBB": 6.0})
        _scout({"divergence": [{"sym": "BBB", "side": "short", "gap_pct": 99.0}]})
        # $120 already deployed at its own clip, cap $150, this clip is $50
        v = _StubVenue(equity=1000.0, pos={"HELD": {"size": 1.0, "entry": 120.0}})
        r = _StubRails(max_notional=150.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0, "meta": {"HELD": {"clip": 120.0,
                                                        "lens": "divergence"}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.opens == [], f"cap breach: {v.opens}"
        assert captured["orders"] == []

        # ================================================================
        # 3) KILL SWITCH flattens the venue's book and halts — no entries
        # ================================================================
        captured["state"].clear()
        captured["paper"].clear()
        _stub_market(marks={"CCC": 100.0}, funding={}, ranges={"CCC": 6.0})
        _scout({"divergence": [{"sym": "CCC", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, pos={"ZZZ": {"size": 1.0, "entry": 90.0}},
                       fills={"ZZZ": 95.0})
        r = _StubRails(max_notional=150.0, killed=True)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"ZZZ": {"clip": 90.0, "lens": "divergence",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.closes == ["ZZZ"], v.closes
        assert v.opens == [], "halted bot must not enter"
        assert len(captured["paper"]) == 1, captured["paper"]
        # the flatten books the ledger row like a normal close: a long closed
        # at 95 from entry 90 = +5
        _p = captured["paper"][0][1]
        assert _p["reason"] == "long-divergence_kill_switch", _p["reason"]
        assert abs(_p["pnl_abs"] - 5.0) < 1e-9, _p["pnl_abs"]
        assert _p["shadow"] is False
        assert captured["published"][-1][1]["status"] == "halted"

        # ================================================================
        # 4) DAILY LOSS flattens + halts DURABLY (survives the next cycle)
        # ================================================================
        captured["state"].clear()
        captured["halts"].clear()
        _stub_market(marks={"DDD": 100.0}, funding={}, ranges={"DDD": 6.0})
        _scout({"divergence": [{"sym": "DDD", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=940.0, pos={"YYY": {"size": 1.0, "entry": 90.0}},
                       fills={"YYY": 90.0})
        r = _StubRails(max_notional=150.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"YYY": {"clip": 90.0, "lens": "divergence",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0},
            "day_start": {"day": now().date().isoformat(), "equity": 1000.0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert r.confirmed, "a loss breach must be CONFIRMED before flattening"
        assert v.closes == ["YYY"], v.closes
        assert v.opens == []
        assert captured["halts"] and captured["halts"][0][0] == BOT_ROW
        # ... and the halt is durable: replay with load_daily_halt returning it
        store.load_daily_halt = lambda bot, day: {"halted_date": day,
                                                  "day_start_equity": 1000.0}
        v2 = _StubVenue(equity=940.0)
        r2 = _StubRails(max_notional=150.0)
        main(_ctx={"venue": v2, "rails": r2, "broker": None})
        assert v2.opens == [], "a restored halt must still block entries"
        store.load_daily_halt = lambda bot, day: None

        # ================================================================
        # 4b) DEPOSIT must NOT MASK a real drawdown. The daily-loss rail is
        #     NET of capital (operator 2026-07-23): a +$100 deposit that lands
        #     the SAME day exactly offsets a -$100 (-10%) trading loss, so RAW
        #     equity is flat at 1000 vs a day_start of 1000. Pre-fix the rail
        #     saw 1000 vs 1000 and never fired — the operator's own money hid a
        #     10% loss. The fix shifts day_start +100 -> 1100, so 1000 <= 1045
        #     trips and the book is flattened.
        # ================================================================
        captured["state"].clear()
        captured["halts"].clear()
        _stub_market(marks={"DEP": 100.0}, funding={}, ranges={"DEP": 6.0})
        _scout({})
        v = _StubVenue(equity=1000.0, pos={"YYY": {"size": 1.0, "entry": 90.0}},
                       fills={"YYY": 90.0},
                       cap_moves=[{"ts": 0.0, "delta": 100.0, "how": "cash-escape"}])
        r = _StubRails(max_notional=150.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 900.0, "capital_adjust": {"total": 0.0, "events": []},
            "meta": {"YYY": {"clip": 90.0, "lens": "divergence",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0},
            "day_start": {"day": now().date().isoformat(), "equity": 1000.0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.closes == ["YYY"], \
            f"a deposit masked a real drawdown — rail failed to flatten: {v.closes}"
        assert captured["halts"] and captured["halts"][0][0] == BOT_ROW, \
            "a masked drawdown must still halt for the day"
        # day_start was shifted onto raw footing and persisted for the next cycle
        assert captured["state"][LIVE_STATE_KEY]["day_start"]["equity"] == 1100.0, \
            captured["state"][LIVE_STATE_KEY]["day_start"]

        # ================================================================
        # 4c) WITHDRAWAL must NOT FABRICATE a halt. A -$30 withdrawal drops RAW
        #     equity 1000 -> 970 with zero trading loss; the absolute fleet rail
        #     ($30) saw 1000-970 >= 30 and flattened the book pre-fix. The fix
        #     shifts day_start -30 -> 970, so 970-970 = 0 and nothing fires.
        # ================================================================
        captured["state"].clear()
        captured["halts"].clear()
        _stub_market(marks={"WWW": 100.0}, funding={}, ranges={"WWW": 6.0})
        _scout({})
        v = _StubVenue(equity=970.0, pos={"WWW": {"size": 1.0, "entry": 100.0}},
                       fills={"WWW": 100.0},
                       cap_moves=[{"ts": 0.0, "delta": -30.0, "how": "cash-escape"}])
        r = _StubRails(max_notional=150.0, max_daily_loss=30.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0, "capital_adjust": {"total": 0.0, "events": []},
            "meta": {"WWW": {"clip": 100.0, "lens": "divergence",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0},
            "day_start": {"day": now().date().isoformat(), "equity": 1000.0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.closes == [], \
            f"a withdrawal fabricated a phantom flatten: {v.closes}"
        assert not captured["halts"], \
            "a withdrawal is the operator's cash-out, not a trading loss — no halt"
        assert not r.confirmed, "no breach should even be read on a withdrawal"
        assert captured["state"][LIVE_STATE_KEY]["day_start"]["equity"] == 970.0, \
            captured["state"][LIVE_STATE_KEY]["day_start"]

        # ================================================================
        # 5) A FAILED CLOSE never books a phantom exit
        # ================================================================
        captured["state"].clear()
        captured["paper"].clear()
        _stub_market(marks={"EEE": 200.0}, funding={}, ranges={})
        _scout({})
        v = _StubVenue(equity=1000.0, pos={"EEE": {"size": 1.0, "entry": 100.0}})
        v.fail_close.add("EEE")                     # +100% -> TP, but close fails
        r = _StubRails(max_notional=150.0)
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"EEE": {"clip": 100.0, "lens": "breakout",
                             "opened": iso(now()), "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert captured["paper"] == [], "a failed close must not book a row"
        assert "EEE" in captured["state"][LIVE_STATE_KEY]["meta"], \
            "a failed close must KEEP the position — the venue still holds it"

        # ================================================================
        # 6) LIVE funding is the VENUE's — it must not hit modelled equity,
        #    but it must still reach the ledger and the win/loss call
        # ================================================================
        captured["state"].clear()
        captured["paper"].clear()
        _stub_market(marks={"FFF": 104.0}, funding={"FFF": 8e-4}, ranges={})
        _scout({})
        v = _StubVenue(equity=1234.56, pos={"FFF": {"size": 1.0, "entry": 100.0}},
                       fills={"FFF": 104.0})
        r = _StubRails(max_notional=150.0)
        _opened = iso(now() - timedelta(hours=8))
        captured["state"][LIVE_STATE_KEY] = {
            "initial_equity": 1000.0,
            "meta": {"FFF": {"clip": 100.0, "lens": "breakout",
                             "opened": _opened, "accrued_to": _opened,
                             "funding_paid": 0.0,
                             # [2026-07-28] entry evidence must ride the row
                             "evidence": {"brk_quality": 0.42,
                                          "up_strength": 0.13}}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert len(captured["paper"]) == 1, captured["paper"]
        _p = captured["paper"][0][1]
        # [2026-07-28 REVIEW] the close ROW carries the (di) capture — the
        # analyzer's filter is `extra ? 'brk_quality'` and it matched zero
        # rows for the first 6 breakoutup closes. Mutation check: reverting
        # _book_close's extra to the bare bars dict turns this red.
        assert _p["extra"]["brk_quality"] == 0.42, _p["extra"]
        assert "bars" in _p["extra"], _p["extra"]
        # price +4 on a long; funding on the TRUE 8h basis = 1*104*1e-4*8 = 0.0832
        # (the 8x bug would have charged 0.6656). net = 4 - 0.0832 - 0 (no fee).
        assert abs(_p["pnl_abs"] - (4.0 - 0.0832)) < 1e-4, _p["pnl_abs"]
        # published equity is the VENUE's, never a modelled one
        _pub = captured["published"][-1][1]
        assert _pub["equity"] == 1234.56, _pub["equity"]
        # [2026-07-21 D1] published live P&L is CAPITAL-ADJUSTED: equity −
        # baseline − guard-recorded capital (0 here) − the env backfill.
        # Computed from the module constant so the fixture tracks the
        # contract, not a frozen number (this assert still read the pre-D1
        # 234.56 after D1 shipped — it only ever runs on signer-wheel
        # machines, where it failed on GOOD news).
        assert abs(_pub["pnl_abs"] - (234.56 - CAPITAL_ADJUST_USD)) < 1e-9, \
            _pub["pnl_abs"]

        # ================================================================
        # 7) UNREADABLE positions must SKIP the cycle — never trade blind.
        #    The negative fixture that matters: a phantom-empty set zeroes
        #    both the slot count and the cap's input, so "no positions" would
        #    read as "full book available" on top of real open risk.
        # ================================================================
        captured["state"].clear()
        _stub_market(marks={"GGG": 100.0}, funding={}, ranges={"GGG": 6.0})
        _scout({"divergence": [{"sym": "GGG", "side": "short", "gap_pct": 99.0}]})

        class _BlindVenue(_StubVenue):
            def positions(self):
                raise RuntimeError("stub: venue unreadable")

        v = _BlindVenue(equity=1000.0)
        r = _StubRails(max_notional=150.0)
        main(_ctx={"venue": v, "rails": r, "broker": None})
        assert v.opens == [], f"traded blind: {v.opens}"

        # ================================================================
        # 8) A FAILED FLATTEN must not publish open_trades=0. The halted row
        #    has to show the book it could not close, or the retry rail above
        #    is invisible behind a green-looking row.
        # ================================================================
        captured["state"].clear()
        captured["published"].clear()
        _stub_market(marks={"HHH": 100.0}, funding={}, ranges={})
        _scout({})
        v = _StubVenue(equity=1000.0, pos={"HHH": {"size": 1.0, "entry": 100.0}})
        v.fail_close.add("HHH")
        r = _StubRails(max_notional=150.0, killed=True)   # kill -> flatten fails
        main(_ctx={"venue": v, "rails": r, "broker": None})
        _pub = captured["published"][-1][1]
        assert _pub["status"] == "halted"
        assert _pub["open_trades"] == 1, \
            f"a failed flatten must report the open book, got {_pub['open_trades']}"
        assert _pub["extra"]["flatten_incomplete"] is True

        # ================================================================
        # 9) THE SHADOW ARM MUST NOT REGRESS. It is DEPLOYED and it is
        #    collecting the only evidence a go-live could ever rest on;
        #    breaking it mid-flight costs exactly what we are waiting for.
        #    The live refactor moved every call site in this loop off
        #    broker.pos, so drive the dry_run path end-to-end too.
        # ================================================================
        TT_VENUE, BOT_ROW = "lighter_shadow", BOT + "-lshadow"
        captured["state"].clear()
        captured["paper"].clear()
        captured["published"].clear()
        _stub_market(marks={"III": 104.0}, funding={"III": 8e-4},
                     ranges={"III": 6.0})
        _scout({"divergence": [{"sym": "III", "side": "short", "gap_pct": 99.0}]})
        b = PaperBroker(start_equity=1000.0, fee_bps=4.0)
        _opened = iso(now() - timedelta(hours=8))
        b.open("III", True, 1.0, 100.0)          # held long, +4% -> TP
        captured["state"][STATE_KEY] = {
            "broker": b.to_state(),
            "meta": {"III": {"clip": 100.0, "lens": "breakout",
                             "opened": _opened, "accrued_to": _opened,
                             "funding_paid": 0.0}},
            "stats": {"closed": 0, "wins": 0, "losses": 0}}
        b2 = PaperBroker(start_equity=1000.0, fee_bps=4.0)
        main(_ctx={"venue": None, "rails": None, "broker": b2})
        # closed through the BROKER, and the shadow arm writes the shadow row
        assert len(captured["paper"]) == 1, captured["paper"]
        _p = captured["paper"][0][1]
        assert _p["shadow"] is True and _p["reason"] == "long-breakout_tp"
        # funding on the TRUE 8h basis reaches the ledger AND the equity here
        # (a shadow book has no venue charging it): 1*104*1e-4*8 = 0.0832
        # price +4, fees 2*100*0.0004 = 0.08  ->  net = 4 - 0.0832 - 0.08
        assert abs(_p["pnl_abs"] - (4.0 - 0.0832 - 0.08)) < 1e-4, _p["pnl_abs"]
        # shadow persists a BROKER snapshot under its own key, never the live one
        assert STATE_KEY in captured["state"] and LIVE_STATE_KEY not in captured["state"]
        assert "broker" in captured["state"][STATE_KEY]
        # equity is the broker's, and the drag landed in it. Leg by leg, the
        # broker charges on ACTUAL notional at each leg (not the ledger's
        # modelled 2*clip*fee above — a pre-existing, deliberate difference):
        #   0.0400  restored entry fee on the held long (1 @ 100)
        # + 0.0832  funding, TRUE 8h basis (1 * 104 * 1e-4 * 8)
        # + 0.0416  close fee at the EXIT price 104, not the entry
        # + 0.0400  entry fee on the new divergence short (100/104 @ 104 —
        #           (td) doubled the risk budget, so the clip is $100 now)
        _pub = captured["published"][-1][1]
        assert _pub["extra"]["venue"] == "lighter_shadow"
        # [2026-07-24 (df)] the heartbeat emits the process's OWN bull-mode read
        # (KeyError if the marker is dropped; mismatch if it is hardcoded).
        assert _pub["extra"]["bull"] == BULL_MODE
        # [2026-07-24 (dh)] the heartbeat emits the process's OWN effective risk
        # config: the slot count is the module global; cap is None here (rails is
        # None in this shadow-path test) but the KEY must always be present.
        assert _pub["extra"]["max_open"] == MAX_OPEN
        assert "cap_usd" in _pub["extra"] and _pub["extra"]["cap_usd"] is None
        assert abs(b2.fees - 0.2048) < 1e-4, b2.fees
        # THE basis detector: with the 8x bug the funding leg alone was 0.6656
        # and this total would be 0.7872. This assertion is what fails if
        # anyone ever routes this accrual around funding_basis again.
        assert abs(b2.fees - 0.7672) > 1e-2, "8x funding over-accrual is BACK"
        # and it still takes new tickets (the entry pass survived the refactor)
        assert _pub["open_trades"] == 1, _pub["open_trades"]

        # ================================================================
        # 9b) breakout_up RELABEL end-to-end (dk): a CRYPTO breakout ticket, in a
        #     candle up-regime, under bull, opens as lens 'breakoutup' (relabelled
        #     BEFORE the veto) — proving it fires (not scout-graded => not vetoed)
        #     and is tagged distinctly so the brain grades it on its OWN closes.
        #     up_read needs a venue for candles even on the shadow arm, so drive
        #     with the candle-stub venue + the broker.
        # ================================================================
        globals()["BULL_MODE"] = True
        try:
            captured["state"].clear()
            captured["paper"].clear()
            _stub_market(marks={"SOL": 100.0}, funding={}, ranges={"SOL": 6.0})
            _scout({"breakout": [{"sym": "SOL", "range_pos": 0.98,
                                  "chg_pct": 2.0, "vol_m": 5.0}]})
            _bv = _StubVenue(equity=1000.0)      # default candles() = up-regime
            _b3 = PaperBroker(start_equity=1000.0, fee_bps=4.0)
            main(_ctx={"venue": _bv, "rails": None, "broker": _b3})
            _meta = (captured["state"].get(STATE_KEY) or {}).get("meta") or {}
            _lens = (_meta.get("SOL") or {}).get("lens")
            assert _lens == "breakoutup", f"expected relabel to breakoutup, got {_lens!r}"
            # and it carries the captured quality (di) for later criteria derivation
            assert (_meta.get("SOL") or {}).get("evidence", {}).get("brk_quality") is not None
        finally:
            globals()["BULL_MODE"] = False

        # ================================================================
        # 9c) breakoutup SELF-VETO end-to-end (dm, Increment B): the SAME
        #     up-regime breakout that opened in 9b is SKIPPED once the brain has
        #     decisively reduced long-breakoutup on its own closes (mult<=0.5 at
        #     n>=floor) via brain-stake-mults. Mutation-verifies the wiring: with
        #     the veto disarmed, SOL opens (9b); with the grade present, it must
        #     not. Restrict-only, shadow-only.
        # ================================================================
        globals()["BULL_MODE"] = True
        try:
            captured["state"].clear()
            captured["paper"].clear()
            _stub_market(marks={"SOL": 100.0}, funding={}, ranges={"SOL": 6.0})
            _scout({"breakout": [{"sym": "SOL", "range_pos": 0.98,
                                  "chg_pct": 2.0, "vol_m": 5.0}]})
            captured["state"]["brain-stake-mults"] = {
                "updated": iso(now()), "ttl_sec": 26000,
                "mults": {BOT_ROW: {"long-breakoutup": {"mult": 0.5, "n": 30}}}}
            _bv = _StubVenue(equity=1000.0)
            _b4 = PaperBroker(start_equity=1000.0, fee_bps=4.0)
            main(_ctx={"venue": _bv, "rails": None, "broker": _b4})
            _meta = (captured["state"].get(STATE_KEY) or {}).get("meta") or {}
            assert "SOL" not in _meta, \
                f"breakoutup must be self-vetoed, but opened {_meta.get('SOL')!r}"
        finally:
            globals()["BULL_MODE"] = False

        # ================================================================
        # 10) A CRASH MUST MARK THE ROW. The negative fixture is the REAL
        #     incident: the exact VenueError the missing lighter-sdk wheel
        #     raised, crash-looping behind a row that still read "online".
        # ================================================================
        _status = []
        _real_set = store.set_status
        _real_load = store.load_state
        store.set_status = lambda bot, st: _status.append((bot, st))
        try:
            # The incident crashed at LighterClient construction — line 335 of
            # main(), propagating straight out to <module> UNCAUGHT. Reproduce
            # the shape (an uncaught raise from main's body) rather than the
            # exact call: the fetch path is CAUGHT and returns, so raising
            # there would prove nothing about this control. Verified the hard
            # way — the first draft of this fixture did exactly that and passed
            # against a supervisor that had never run.
            globals()["fetch_marks_and_funding"] = lambda: ({}, {}, {})
            store.load_state = _boom
            try:
                _supervised()
                raise AssertionError("the crash must propagate")
            except RuntimeError:
                pass               # re-raised by design
            store.load_state = _real_load
            assert _status == [(BOT_ROW, "error")], \
                f"a crash must mark the row, got {_status}"
            # ... and a boot REFUSAL is not a crash: it must pass through
            # untouched (SafetyRails._publish_refusal already owns that row).
            # [2026-07-17] This used to assert on the EVIDENCE refusal
            # (lighter_live raises SystemExit). The operator lifted that gate,
            # so the fixture had to be re-pointed at a refusal that still
            # exists — otherwise it would assert that a removed gate is present
            # and demand the code stay as it was. The IDENTITY refusal (TT_VENUE
            # unset) is the right subject: it is a boot refusal on the same path,
            # and unlike the old one it cannot be lifted by a decision.
            _status.clear()
            globals()["fetch_marks_and_funding"] = lambda: ({}, {}, {})
            _ttv_save = os.environ.get("TT_VENUE")
            try:
                os.environ.pop("TT_VENUE", None)
                try:
                    _supervised()          # no _ctx, no TT_VENUE -> identity refusal
                    raise AssertionError("an unset TT_VENUE must refuse")
                except SystemExit:
                    pass
                assert _status == [], f"a refusal is not a crash, got {_status}"
            finally:
                if _ttv_save is None:
                    os.environ.pop("TT_VENUE", None)
                else:
                    os.environ["TT_VENUE"] = _ttv_save
        finally:
            store.set_status = _real_set
            store.load_state = _real_load

        # ================================================================
        # 11) THE TIDE RIDER HANDOVER. The live arm inherits the sub-account
        #     Tide Rider is vacating. A leftover position there must HALT the
        #     bot, not be silently adopted onto the taker's exit ladder.
        # ================================================================
        TT_VENUE, BOT_ROW = "lighter_live", BOT + "-lighter"
        captured["state"].clear()
        captured["paper"].clear()
        _status = []
        _real_set = store.set_status
        store.set_status = lambda bot, st: _status.append((bot, st))
        try:
            # TRX at Tide Rider's entry, 5% against — inside the taker's ±4% TP
            # bar, so an ADOPTING bot would close a trend position on the
            # taker's rule. It must refuse instead.
            _stub_market(marks={"TRX": 0.2625}, funding={}, ranges={})
            _scout({"divergence": [{"sym": "AAA", "side": "short", "gap_pct": 99.0}]})
            v = _StubVenue(equity=34.67, pos={"TRX": {"size": 100.0, "entry": 0.25}})
            r = _StubRails(max_notional=150.0)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67, "meta": {},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            # [2026-07-17 AUDIT] No longer a SystemExit: the guard is SCOPED to
            # the foreign symbols. Everything this fixture ever asserted still
            # holds — the stranger is not managed, nothing is traded, the row is
            # marked — but the bot now completes its cycle instead of dying,
            # which is what lets 11a (below) keep its own stops.
            main(_ctx={"venue": v, "rails": r, "broker": None})
            assert v.closes == [], f"must not manage a foreign position: {v.closes}"
            assert v.opens == [], f"must not trade on a dirty account: {v.opens}"
            assert captured["paper"] == [], "must not book a foreign close"
            assert _status[0] == (BOT_ROW, "error"), \
                f"a dirty account must mark the row: {_status}"

            # ================================================================
            # 11a) THE BUG THIS FIXTURE NEVER CAUGHT: our OWN position, held
            #      ALONGSIDE the stranger, must keep its stop-loss. The case
            #      above is all-foreign (meta={}) — the one shape where
            #      "abandon everything" and "abandon only the stranger" are
            #      INDISTINGUISHABLE. So `assert v.closes == []` passed for the
            #      whole life of the defect while encoding it as the contract.
            #      Mixed is the shape that tells them apart, and it is the shape
            #      production actually has: a lost meta write (or one Postgres
            #      blip) puts a stranger next to real, stopped positions.
            # ================================================================
            _status.clear()
            captured["paper"].clear()
            # OURS: a divergence SHORT 10% against us — far through the -3% stop.
            # THEIRS: Tide Rider's TRX, untouched.
            _stub_market(marks={"OWN": 110.0, "TRX": 0.2625}, funding={}, ranges={})
            v3 = _StubVenue(equity=34.67,
                            pos={"OWN": {"size": -0.15, "entry": 100.0},
                                 "TRX": {"size": 100.0, "entry": 0.25}},
                            fills={"OWN": 110.0, "TRX": 0.2625})
            r3 = _StubRails(max_notional=150.0)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67,
                "meta": {"OWN": {"lens": "divergence", "opened": iso(now()),
                                 "entry": 100.0, "clip": 15.0, "is_long": False}},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v3, "rails": r3, "broker": None})
            assert "OWN" in v3.closes, (
                "REGRESSION: our own position was abandoned because a stranger "
                f"shared the account — this is the whole bug: {v3.closes}")
            assert "TRX" not in v3.closes, \
                f"the stranger must still not be managed: {v3.closes}"
            assert v3.opens == [], f"still no new entries while dirty: {v3.opens}"
            assert _status[0] == (BOT_ROW, "error"), "still marks the row"

            # ================================================================
            # 11b) A FAILED READ IS NOT A DIRTY ACCOUNT. One Postgres blip used
            #      to yield meta={} -> every position "foreign" -> the guard
            #      fired on a CLEAN account, stopping the exit ladder on real
            #      money and sending the operator hunting a phantom stranger.
            # ================================================================
            _status.clear()
            captured["fail_reads"] = True
            v4 = _StubVenue(equity=34.67, pos={"OWN": {"size": -0.15, "entry": 100.0}},
                            fills={"OWN": 110.0})
            try:
                main(_ctx={"venue": v4, "rails": _StubRails(max_notional=150.0),
                           "broker": None})
                raise AssertionError("an unreadable state must not be guessed at")
            except SystemExit as e:
                assert "READ FAILED" in str(e), str(e)
                assert "DIRTY ACCOUNT" not in str(e), \
                    f"must NOT blame a dirty account for a DB fault: {e}"
            assert v4.closes == [] and v4.opens == [], \
                "a blind cycle must not trade on either side"
            captured["fail_reads"] = False

            # ================================================================
            # 11c) A FAILED WRITE MUST PAGE. save_state returns False and never
            #      raises, so a lost meta write is how a position becomes
            #      unattributable — and therefore unstoppable — out of nothing
            #      but a DB blip. It cannot be undone; it must not be silent.
            # ================================================================
            _status.clear()
            captured["fail_writes"] = True
            v5 = _StubVenue(equity=34.67, pos={"OWN": {"size": -0.15, "entry": 100.0}},
                            fills={"OWN": 100.5})
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67,
                "meta": {"OWN": {"lens": "divergence", "opened": iso(now()),
                                 "entry": 100.0, "clip": 15.0, "is_long": False}},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v5, "rails": _StubRails(max_notional=150.0),
                       "broker": None})
            assert (BOT_ROW, "error") in _status, \
                f"a failed meta write must mark the row: {_status}"
            captured["fail_writes"] = False
            _status.clear()

            # ... and the kill switch stays the escape hatch: it runs ABOVE the
            # guard, so REAL_MONEY_KILL can still flatten a dirty account.
            _status.clear()
            v2 = _StubVenue(equity=34.67, pos={"TRX": {"size": 100.0, "entry": 0.25}},
                            fills={"TRX": 0.2625})
            r2 = _StubRails(max_notional=150.0, killed=True)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 34.67, "meta": {},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v2, "rails": r2, "broker": None})
            assert v2.closes == ["TRX"], \
                f"the kill switch must still flatten a dirty account: {v2.closes}"

            # ... and a CLEAN account (every position has meta) proceeds.
            _stub_market(marks={"KNOWN": 100.0}, funding={}, ranges={})
            _scout({})
            v3 = _StubVenue(equity=1000.0, pos={"KNOWN": {"size": 1.0, "entry": 100.0}})
            r3 = _StubRails(max_notional=150.0)
            captured["state"][LIVE_STATE_KEY] = {
                "initial_equity": 1000.0,
                "meta": {"KNOWN": {"clip": 100.0, "lens": "divergence",
                                   "opened": iso(now()), "funding_paid": 0.0}},
                "stats": {"closed": 0, "wins": 0, "losses": 0}}
            main(_ctx={"venue": v3, "rails": r3, "broker": None})   # must not raise
        finally:
            store.set_status = _real_set

        # ================================================================
        # 12) FILL TELEMETRY is a DETECTOR — a measured 0 is a 0, and an
        #     unmeasured leg is NULL *and names why*.
        #
        #     Both halves are regression fixtures for real 17-Jul defects:
        #     (a) the taker's first two REAL orders recorded px_fill ==
        #         px_decision with slippage NULL and NO reason anywhere — 0 of
        #         57 real-money orders fleet-wide had ever carried a measured
        #         fill, and nobody could ask the ledger why.
        #     (b) 1000BONK's REAL fill was 0.003275 against a decision price of
        #         0.003275 — a genuinely perfect fill. The old `d == f` rule
        #         inferred "no read" and THREW THE MEASUREMENT AWAY.
        #     Mutation-checked: reverting _slip_bps_of to the `d == f`
        #     inference must fail (a) or (b).
        # ================================================================
        captured["state"].clear()
        captured["orders"].clear()
        # (b) a REAL fill exactly ON the mark -> slippage 0.0, measured True
        _stub_market(marks={"MRK": 100.0}, funding={}, ranges={"MRK": 6.0})
        _scout({"divergence": [{"sym": "MRK", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"MRK": 100.0})   # fill == decision
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _o = captured["orders"][0][1]
        assert _o["px_fill"] == 100.0 and _o["px_decision"] == 100.0
        assert _o["slippage_bps"] == 0.0, \
            ("a MEASURED at-mark fill must record 0.0, not None — an at-mark "
             f"fill is a measurement, not a failure: {_o['slippage_bps']!r}")
        assert _o["raw"]["measured"] is True, _o["raw"]
        # EXACT match, not the (side, since_ts) heuristic: the order's own
        # client id must reach the read, or the fill is a VWAP of whatever else
        # we happened to trade on that side inside the window.
        assert _o["raw"]["fill_src"] == "trades", \
            (f"fill_src {_o['raw']['fill_src']!r} — '(approx)' means the client "
             f"id did NOT reach last_fill_detail, so the read is a blend")
        assert v.seen_client_ids == [v.last_cid], \
            (f"the fill read must be given the order's client id: "
             f"got {v.seen_client_ids!r}, order was {v.last_cid!r}")

        # (a) NO read -> decision price recorded, slippage NULL, reason NAMED
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"UNM": 100.0}, funding={}, ranges={"UNM": 6.0})
        _scout({"divergence": [{"sym": "UNM", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={},
                       fill_reason="api-error:trades:VenueError:boom")
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _o = captured["orders"][0][1]
        assert v.opens, "the order must still SEND — telemetry never blocks it"
        assert _o["px_fill"] == 100.0, _o          # falls back to the decision
        assert _o["slippage_bps"] is None, \
            f"an UNMEASURED leg must be NULL, never 0.0: {_o['slippage_bps']!r}"
        assert _o["raw"]["measured"] is False, _o["raw"]
        assert "api-error" in (_o["raw"]["fill_src"] or ""), \
            f"the ledger must NAME why it could not measure: {_o['raw']!r}"

        # (c) THE ID FILTER IS NOT A CLIFF. Lighter stops echoing client ids —
        #     the tape is readable, our id is just not on it. The venue layer's
        #     id match is HARD (lighter_client.py:624-629 `continue`s, no
        #     fallback), so before this fix the read went from approximate to
        #     NOTHING: threading the id made the happy path exact and the
        #     unhappy path strictly WORSE than the heuristic it replaced, in
        #     silence. That round trip has never been proven in production — the
        #     taker's only two live orders (STRC/1000BONK, 09:08 + 09:13Z 17-Jul)
        #     predate the fill-read code by an hour, so NO venue_orders row has
        #     ever carried `measured`. This fixture is the whole reason the
        #     assumption is survivable.
        #
        #     MUTATION: drop read_fill's retry (revert to the hard filter) and
        #     px_fill collapses to the decision price -> RED.
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"NOID": 100.0}, funding={}, ranges={"NOID": 6.0})
        _scout({"divergence": [{"sym": "NOID", "side": "short", "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"NOID": 100.5}, echo_ids=False)
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _o = captured["orders"][0][1]
        assert _o["px_fill"] == 100.5, \
            (f"an id-miss must FALL BACK to the (side, since_ts) read, not "
             f"collapse to the decision price: px_fill={_o['px_fill']!r}")
        assert v.seen_client_ids == [v.last_cid, None], \
            (f"the id must be tried FIRST and dropped exactly once: "
             f"{v.seen_client_ids!r}")
        # ...and the fallback is an ESTIMATE. A blended read recorded as a
        # measurement is worse than no read at all: it is a fabrication wearing
        # a `measured: true` stamp.
        #     MUTATION: restore `return real, True, reason` in _real_fill -> RED.
        assert _o["raw"]["measured"] is False, \
            f"a fallback read is a BLEND, never a measurement: {_o['raw']!r}"
        assert "id-miss" in (_o["raw"]["fill_src"] or ""), \
            f"the ledger must NAME the degraded read: {_o['raw']!r}"
        #     MUTATION: let slip_bps_of return the bps for an unmeasured leg
        #     (the Farmer's old rule) -> RED. implementation_shortfall AVGs this
        #     column with no `measured` filter, so a blend would contaminate the
        #     live-vs-shadow execution verdict rather than just sit there.
        assert _o["slippage_bps"] is None, \
            (f"an unmeasured leg must record NULL slippage even though the "
             f"blended price differs from the decision: {_o['slippage_bps']!r}")
        # ...and the blend goes NO FURTHER THAN THE LEDGER. meta[sym]["entry"]
        # is where telemetry would become ORDER BEHAVIOUR: the stop and TP hang
        # off it, so a fallback that has never run in production would be
        # deciding when real money closes on its first ever execution. The
        # ledger row above carries the blend (px_fill=100.5, named + measured
        # False); the bot still runs its stop off the decision mark, exactly as
        # it does today when the id misses.
        #     MUTATION: `entry_px = _fill_px` (drop the `if _meas else mark`)
        #     and this is RED — that one line is the whole telemetry/behaviour
        #     boundary, and nothing else in the suite constrains it.
        _live = captured["state"][LIVE_STATE_KEY]
        assert _live["meta"]["NOID"]["entry"] == 100.0, \
            (f"an UNMEASURED fill must never reach meta['entry'] — the stop "
             f"and TP hang off it: {_live['meta']['NOID']['entry']!r} "
             f"(decision mark was 100.0, the blended read was 100.5)")
        # The measured path is the control: when the venue NAMES the fill, meta
        # takes it — that is today's behaviour and this fix must not touch it.
        captured["state"].clear()
        captured["orders"].clear()
        _stub_market(marks={"YESID": 100.0}, funding={}, ranges={"YESID": 6.0})
        _scout({"divergence": [{"sym": "YESID", "side": "short",
                                "gap_pct": 99.0}]})
        v = _StubVenue(equity=1000.0, fills={"YESID": 100.5})   # ids echo
        main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                   "broker": None})
        _live = captured["state"][LIVE_STATE_KEY]
        assert _live["meta"]["YESID"]["entry"] == 100.5, \
            (f"a MEASURED fill must still reach meta['entry'] — guarding the "
             f"fallback must not cost us the real fill we did measure: "
             f"{_live['meta']['YESID']['entry']!r}")

        # (d) A FAILED READ MUST NOT RETRY. `skipped:budget` / `auth-failed` /
        #     `api-error` mean the tape was never read — a second call spends the
        #     governor's telemetry reserve to fail identically, against
        #     lighter_client's explicit rule that telemetry must never make the
        #     NEXT market_open queue behind it. Only `no-match` (a readable tape
        #     our id was absent from) earns the retry.
        #
        #     MUTATION: retry on any falsy read instead of `no-match` only -> RED.
        for _bad in ("skipped:budget(2.0 tok, reserve 4)", "auth-failed:expired",
                     "api-error:trades:TimeoutError:x", "empty:both(stub)"):
            captured["state"].clear()
            captured["orders"].clear()
            _stub_market(marks={"BUD": 100.0}, funding={}, ranges={"BUD": 6.0})
            _scout({"divergence": [{"sym": "BUD", "side": "short",
                                    "gap_pct": 99.0}]})
            v = _StubVenue(equity=1000.0, fills={}, fill_reason=_bad)
            main(_ctx={"venue": v, "rails": _StubRails(max_notional=150.0),
                       "broker": None})
            assert v.seen_client_ids == [v.last_cid], \
                (f"{_bad!r} must NOT retry — the tape was never read, so a "
                 f"second call burns budget to re-fail: {v.seen_client_ids!r}")

        # ================================================================
        # 13) THE VENUE LAYER IS AUDIBLE — and importing this file must NOT
        #     hijack anyone else's logging.
        #
        #     The live taker configured no logging, so Python dropped every
        #     `log.info` from venues/: no signer banner (hence no lighter-sdk
        #     version), no EQUITY GUARD REJECTs, no governor 429s. The funding
        #     bot could report its wheel and this bot could not — that asymmetry
        #     IS the bug. Both halves are pinned because the fix has two ways to
        #     be wrong: silent (no handler) or invasive (hijacking 4 importers).
        # ================================================================
        import logging as _lg
        import inspect as _insp

        # (0) THE CALL SITE. Testing _setup_logging() directly proves the
        #     FUNCTION works and says NOTHING about main() calling it — and a
        #     helper nobody calls is precisely the original bug. This is the
        #     THIRD time tonight that a fixture exercised a helper and missed
        #     its wiring (see _bars in funding_carry_bot, and _slip_bps_of's
        #     `measured`); mutation-proven, M14 sailed through without it.
        _main_src = "\n".join(ln.split("#", 1)[0]
                              for ln in _insp.getsource(main).splitlines())
        assert "_setup_logging(_ctx)" in _main_src, (
            "main() must CALL _setup_logging(_ctx) — without it venues' "
            "log.info is dropped and the live bot runs blind to its own "
            "signer, equity guard and governor")

        # (a) IMPORT-TIME PURITY. Four modules import this file and NONE of them
        #     configure logging; a module-level basicConfig would silently take
        #     over the root logger for all four inside the shared container.
        #     Merely importing us must therefore add no handler.
        _root = _lg.getLogger()
        _saved_handlers, _saved_level = list(_root.handlers), _root.level
        try:
            for _h in list(_root.handlers):
                _root.removeHandler(_h)
            assert not _lg.getLogger().handlers, (
                "importing lighter_ticket_taker must NOT configure the root "
                "logger — four modules import it and none configure logging")
            # _ctx (the offline path) must also leave logging alone, so these
            # very selftests never inherit a handler they did not ask for.
            _setup_logging(_ctx={"stub": True})
            assert not _lg.getLogger().handlers, \
                "_setup_logging(_ctx=...) is the TEST path — it must not configure"

            # (b) THE FIX ITSELF: the real path makes venues' log.info audible.
            _setup_logging(None)
            assert _lg.getLogger().handlers, \
                "_setup_logging() must give the root a handler, or venues' " \
                "log.info is dropped and the live bot runs blind"
            assert _lg.getLogger("venues.lighter").isEnabledFor(_lg.INFO), \
                "venues log.info must be ENABLED — that is the signer banner, " \
                "the equity-guard REJECTs and the governor 429s"
            # idempotent: a caller that already configured keeps its own setup
            _n = len(_lg.getLogger().handlers)
            _setup_logging(None)
            assert len(_lg.getLogger().handlers) == _n, \
                "basicConfig must be a no-op when the root already has handlers"
        finally:
            for _h in list(_root.handlers):
                _root.removeHandler(_h)
            for _h in _saved_handlers:
                _root.addHandler(_h)
            _root.setLevel(_saved_level)

        # ================================================================
        # 14) [(lw)] THE ENTRY VETOES REACH THE ROW. On 13-Aug the LIVE
        #     arm's only lens crossed its own realised bar at 11-Aug
        #     14:18Z and the book correctly stopped entering — but the
        #     ONLY way to establish that was `railway logs`. /pnl.json
        #     carried `stress_veto`, `bars` and `tuned` and nothing about
        #     the veto that actually halts the book.
        #
        #     Behavioural by construction, per (lh): this drives the real
        #     main() and reads what it PUBLISHED. An AST/substring test
        #     here would pass against a payload that carries the key with
        #     a permanently empty value — which is exactly the failure
        #     being guarded (a gate that stops gating looks quiet).
        # ================================================================
        TT_VENUE, BOT_ROW = "lighter_shadow", BOT + "-lshadow"
        captured["state"].clear()
        captured["paper"].clear()
        captured["published"].clear()
        _stub_market(marks={"JJJ": 100.0}, funding={}, ranges={"JJJ": 6.0})
        _scout({"divergence": [{"sym": "JJJ", "side": "short",
                                "gap_pct": 99.0}]})
        # A losing realised record for `divergence`: mean < 0 and t <= -1.0
        # over >= REALISED_MIN_N closes is exactly `realised_loses`.
        # The returns must VARY: `_stats` yields t=0.0 at zero variance, so a
        # column of identical losses is not a losing record by this rule — it
        # is an undefined one. (Caught by this fixture on its first run.)
        _losers = [{"bot": BOT_ROW, "pair": "ZZZ/USDC", "is_open": False,
                    "reason": "short-divergence_sl",
                    "profit_ratio": -0.012 + 0.002 * ((i % 3) - 1),
                    "close_ts": iso(now() - timedelta(hours=6 + i)),
                    "extra": {}}
                   for i in range(REALISED_MIN_N + 4)]
        _saved_fetch = store.fetch_paper_trades
        store.fetch_paper_trades = lambda **kw: list(_losers)
        # a FRESH forward grade carrying the lens — the path production runs
        captured["state"]["brain-lens-forward"] = {
            "updated": iso(now()), "ttl_sec": 26000,
            "lenses": {"divergence": {}}}
        try:
            main(_ctx={"venue": None, "rails": None,
                       "broker": PaperBroker(start_equity=1000.0,
                                             fee_bps=4.0)})
        finally:
            store.fetch_paper_trades = _saved_fetch
        _pub = captured["published"][-1][1]["extra"]
        # (a) the verdict rides the row
        assert "lens_veto" in _pub, \
            "the row must carry the veto state — its absence is what made " \
            "'is the book halted?' a shell-access question"
        assert "divergence" in _pub["lens_veto"], \
            f"a lens its own closes disprove must be PUBLISHED as vetoed, " \
            f"got {_pub['lens_veto']}"
        # (b) and the evidence it was computed from, so a reader can tell a
        #     veto from a near-miss without re-deriving it (the (li) lesson:
        #     a bare verdict cannot be distinguished from a vacuous one).
        _ev = _pub["lens_evidence"]["divergence"]
        assert _ev["n"] == len(_losers) and _ev["mean_pct"] < 0 \
            and _ev["t"] <= REALISED_VETO_T, _ev
        # (c) the book actually acted on it — a published verdict that did
        #     not gate is a label, not an actuator.
        assert not captured["paper"], \
            f"a vetoed lens must not open: {captured['paper']}"
        # (d) NEGATIVE ARM — the empty list must be reachable, or `lens_veto`
        #     is a constant and (a) passes on a payload that never varies.
        captured["state"].clear()
        captured["published"].clear()
        captured["state"]["brain-lens-forward"] = {
            "updated": iso(now()), "ttl_sec": 26000, "lenses": {}}
        _stub_market(marks={"JJJ": 100.0}, funding={}, ranges={"JJJ": 6.0})
        _scout({})
        main(_ctx={"venue": None, "rails": None,
                   "broker": PaperBroker(start_equity=1000.0, fee_bps=4.0)})
        assert captured["published"][-1][1]["extra"]["lens_veto"] == [], \
            "with nothing vetoed the row must say so EXPLICITLY — [] and a " \
            "missing key are different facts about the container"

        print("\nAll LIVE order-path self-tests passed:")
        print("  1 entry SENDS a real order + records the REAL fill")
        print("  2 notional cap is senior — cap-breaching entry never sends")
        print("  3 kill switch flattens the VENUE's book + halts")
        print("  4 daily loss confirms, flattens, halts DURABLY")
        print("  5 a failed close books no phantom row and keeps the position")
        print("  6 live funding hits the ledger, not equity; equity is the venue's")
        print("  7 unreadable positions SKIP the cycle — never trade blind")
        print("  8 a failed flatten reports the open book, not a green zero")
        print("  9 the DEPLOYED shadow arm still trades, on the TRUE 8h basis")
        print(" 10 a crash marks the row ERROR instead of going quietly stale")
        print(" 11 a DIRTY account is QUARANTINED, not adopted: the stranger is\n"
              "    never managed and nothing new is opened — but our OWN positions\n"
              "    keep their stop (11a), a failed READ is not called a dirty\n"
              "    account (11b), a failed meta WRITE pages (11c), and the kill\n"
              "    switch still flattens")
        print(" 12 fill telemetry DETECTS: a measured at-mark fill records 0.0,")
        print("    an unmeasured leg records NULL and names the reason, an")
        print("    id-miss FALLS BACK (labelled, never stamped measured), and")
        print("    a read that never happened does not retry into the reserve")
        print(" 13 the venue layer is AUDIBLE (signer/equity-guard/governor),")
        print("    and importing this file hijacks nobody's logging")
        print(" 14 the ENTRY VETOES reach the row: a lens its own closes")
        print("    disprove is published as vetoed WITH its evidence, does")
        print("    not open, and an empty veto set is published explicitly")
    finally:
        for k, fn in _real.items():
            setattr(store, k, fn)
        globals()["fetch_marks_and_funding"] = _real_fetch
        TT_VENUE, BOT_ROW = _saved_env
        if _saved_ttv is None:
            os.environ.pop("TT_VENUE", None)
        else:
            os.environ["TT_VENUE"] = _saved_ttv


def _supervised():
    """[2026-07-17 INCIDENT] A crash used to publish NOTHING — the row simply
    went stale, which reads as a DEAD bot rather than a broken one, and the two
    look identical on the dashboard until someone greps the container.

    That is not hypothetical: the shadow arm shipped at 05:35 UTC missing its
    lighter-sdk wheel and crash-looped every 5 minutes for an hour behind a row
    still showing the OLD image's last-good `online, 1013.99, 18 closes`. Two
    commits then cited that fossil as evidence the arm was healthy.

    A run-once process has no supervisor loop to mark the row, so do it here:
    mark ERROR and re-raise. run_all.sh's `|| true` swallows the exit code, but
    the ROW now says why — the same reason SafetyRails._publish_refusal exists
    (a refused boot must not look like a dead one). Status-only: the last good
    equity/P&L stays intact.
    """
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise                      # boot refusals (incl. lighter_live) pass through
    except Exception:              # noqa: BLE001
        try:
            store.set_status(BOT_ROW, "error")
        except Exception:          # noqa: BLE001 — never mask the real failure
            pass
        raise


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--selftest-live" in sys.argv:
        _selftest_live()
    else:
        _supervised()
