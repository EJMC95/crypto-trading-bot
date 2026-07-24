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
import math
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis
from venues import marks, venue_context
from venues.fills import measured_from_reason, read_fill, slip_bps_of
from venues.safety import capital_adjusted_day_start, open_notional

BOT = "perps-funding-lighter"
# [2026-07-17 BASIS FIX — behaviour-NEUTRAL, see funding_basis.py]
# Was `H = 24 * 365`, which annualised Lighter's 8-HOUR funding fraction as if
# hourly: every apr this LIVE book computed was 8x TRUE. H is now 3*365=1095,
# and EVERY apr-denominated threshold below is divided by the same 8 in this
# SAME commit — so entry/exit decisions are bit-identical (asserted in the
# selftest). This commit re-denominates ONLY; it does not re-tune. Re-tuning
# the gate is a separate, operator-gated, backtest-first change — mixing the
# two is how a reporting fix becomes an 8x live entry change.
H = funding_basis.periods_per_year("lighter")

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
# [2026-07-21 D1] CAPITAL IS NOT P&L. The EquityGuard records the deposits/
# withdrawals it accepts (pop_capital_moves) and they accumulate in the
# persisted ":live" state; this env knob backfills moves that predate the
# mechanism. Default = this book's 18-Jul deposit as measured in the
# fleet-equity series (+$32.55 @ 02:33Z — review 2026-07-21 N1; printed as
# profit until this fix). Override with the exact figure if known; set to 0
# if initial_equity is ever re-baselined by hand (the backfill assumes the
# baseline predates the 18-Jul deposit).
CAPITAL_ADJUST_USD = float(os.environ.get("CAPITAL_ADJUST_USD", "32.55"))
ORDER_USD = float(os.environ.get("FUNDING_ORDER_USD", "25"))   # small: directional
MAX_OPEN_POSITIONS = int(os.environ.get("FUNDING_MAX_OPEN", "6"))
MAX_NEW_PER_LOOP = int(os.environ.get("FUNDING_MAX_NEW_PER_LOOP", "2"))

# [2026-07-24 CONVICTION SIZING — Lever 2 | operator: "reach higher highs"]
# Size each entry by a bounded multiple of the flat clip, driven by funding
# CONVICTION (|apr| vs a reference): the crowded/extreme funders — the ones the
# gate sweep and the live book both say pay best — get a bigger clip; marginal
# ones stay at (or below) base. Default OFF (multiplier ≡ 1.0) so it ships DARK
# on the live arm and every existing decision stays byte-identical; enabled
# per-arm by env (shadow twin first). VALIDATED on Lighter's own 150d tape
# (scripts/backtest_farmer_breadth_lighter.py, measured 0.5bps): the allocation-
# SKILL term (net − mean_mult×flat) is +$19.64 in 'scaled' bounds — bigger size
# lands on the winners, separately from leverage, corroborated by the independent
# gate sweep (hotter funding = better net). maxDD grows with size, so the
# multiplier is BOUNDED here AND the venues/safety notional cap still enforces
# the real-money ceiling — the entry cap check below sees the CONVICTION clip,
# not the flat one. [[notional-cap-vs-variable-clip]]
_CONV_RAW = os.environ.get("FUNDING_CONVICTION", "off").strip().lower()
CONVICTION_MODE = _CONV_RAW if _CONV_RAW in ("scaled", "realloc") else (
    "scaled" if _CONV_RAW in ("on", "1", "true", "yes") else "off")
_CDLO, _CDHI = (0.6, 1.6) if CONVICTION_MODE == "realloc" else (1.0, 2.2)
CONVICTION_LO = float(os.environ.get("FUNDING_CONVICTION_LO", str(_CDLO)))
CONVICTION_HI = float(os.environ.get("FUNDING_CONVICTION_HI", str(_CDHI)))
# reference |apr| where the multiplier ~ 1.0 — ~ the venue resting-funding
# default (0.105 TRUE) / the live book's median entry |apr|. Above it -> size up.
CONVICTION_REF = float(os.environ.get("FUNDING_CONVICTION_REF", "0.105"))


def conviction_mult(apr):
    """Bounded conviction multiplier on the base clip, from funding |apr|.
    Returns 1.0 (a no-op) when disabled or misconfigured — the dark-default
    contract, so an unset env leaves every clip exactly order_usd. Never
    unbounded: clamped to [CONVICTION_LO, CONVICTION_HI] so a single position can
    never eat the notional cap on its own (the cap is the outer guard)."""
    if CONVICTION_MODE == "off" or CONVICTION_REF <= 0:
        return 1.0
    try:
        m = abs(float(apr)) / CONVICTION_REF
    except (TypeError, ValueError):
        return 1.0
    return max(CONVICTION_LO, min(CONVICTION_HI, m))

# [2026-07-17 RE-DENOMINATED /8 with H above — the DECISION is unchanged.]
# These were 0.40 / 0.15 against an 8x-inflated apr, i.e. they really admitted
# at 5% / 1.875% TRUE. They now read 0.05 / 0.01875 against a TRUE apr: the
# same trades, honestly labelled. 0.40 was NOT fitted in these units — it was
# born in funding_carry_bot.py against HYPERLIQUID (hourly, so 24*365 is right
# there and 0.40 meant a true 40%) and ported here as a bare constant. The PORT
# is the bug. So the live gate has never been supported by any backtest.
#
# [2026-07-17 CORRECTION — the sentence that stood here was FALSE, and under
# this repo's "don't re-test what a script header rejects" doctrine it BLOCKED
# the next reader from the right answer.] It read: "ZERO backtests have ever
# run on Lighter funding data — that artifact (scripts/backtest_lighter_funding
# .py) is what re-tuning must wait for." Both halves are wrong. The filename is
# TRANSPOSED — the artifact is scripts/backtest_FUNDING_LIGHTER.py — and it
# EXISTS, is Lighter-native, and has already run. Its verdict on 150d of
# Lighter's own settled tape, gate in TRUE apr:
#
#     gate      @0.86bps (shadow MODEL)   @5bps (ASSUMED)   both halves
#     0.05 LIVE      -15.85                  -41.95            no / no
#     0.12           +11.91                  -10.26            no (h1 -4.23)
#     0.20           +22.51                   +5.01            no (h1 -2.31)
#     0.40 (HL)       -0.82                  -10.66            no / no
#
# So the live gate is not merely unsupported — it is the WORST value tested, at
# BOTH frictions, on the venue it trades. NO gate passes both halves at either
# friction; that row is friction-INDEPENDENT and stands.
#
# WHY IT IS STILL 0.05, deliberately: the ranking above is denominated in a
# friction NOBODY HAS MEASURED. 5bps was assumed; 0.86bps is the ShadowBroker's
# MODEL, not a fill the venue gave anyone. They merely disagree. The only two
# REAL fills ever observed (venues/lighter_client.py:664-667: STRC 13.78bps,
# 1000BONK 0.00bps — n=2, the taker's illiquid books) lean toward the "dead"
# end. Moving the gate now swaps one unmeasured constant for another. The live
# fill telemetry is running as of 17-Jul 11:20Z; re-derive the gate when paired
# decision/fill prices exist on THIS book. See [[funding-farmer-stop-is-the-bug]].
#
# STRUCTURAL, and it does not need the friction number: Lighter publishes only
# 39 distinct funding values across 201 books — 96 books (47.8%) sit at exactly
# 9.6e-05/8h = 10.51% TRUE, and 59 (29.4%) at 3.50%. 77% of the venue rests on
# two constants. A 5% bar is BELOW the 10.51% resting default, so it admits the
# resting population wholesale: 132 of 201 books (65.7%) clear it, and 21 of the
# live book's first 27 opens fired at exactly that resting value. Measured
# 17-Jul off /api/v1/funding-rates. See [[venue-resting-defaults-trap]].
ENTER_APR = float(os.environ.get("FUNDING_ENTER_APR", "0.05"))  # TRUE apr >= 5%
EXIT_APR = float(os.environ.get("FUNDING_EXIT_APR", "0.01875"))  # TRUE apr cools
PERSIST_H = float(os.environ.get("FUNDING_PERSIST_H", "4"))     # hot this long first
MAX_HOLD_H = float(os.environ.get("FUNDING_MAX_HOLD_H", "72"))  # recycle after 3d
MIN_VOL = float(os.environ.get("FUNDING_MIN_VOL", "10e6"))      # 24h turnover floor
MAX_SPREAD_BPS = float(os.environ.get("FUNDING_MAX_SPREAD_BPS", "20"))  # book-spread gate

# Directional risk controls, TUNED on scripts/backtest_directional_funding.py
# (real HYPERLIQUID funding+price, 150d, 30 coins). Key finding: funding capture
# is real (+) but directional price risk eats it (-), so the strategy is only
# ~break-even. Its config claim — "a WIDE stop + TIGHT take-profit is least-bad;
# a tight stop whipsaws out before funding + mean-reversion pay, LOSING more" —
# is HYPERLIQUID'S. It is the ONLY justification this live stop has ever had.
#
# [2026-07-17, ⛔ WITHDRAWN 2026-07-22] This block used to say "LIGHTER'S OWN
# TAPE INVERTS IT" and print a sweep in which STOP 0.03 returned **+$21.32,
# both halves positive, n=1911** at 0.86bps. **That number was a HARNESS
# ARTIFACT and the claim is withdrawn.**
#
# THE BUG: scripts/backtest_funding_lighter.py never cleared its `hot` dict on a
# close, while THIS bot pops `hot_since` on EVERY close (see :940 and :1226 —
# "force a fresh persistence wait — no instant re-entry"). So PERSIST_H bit once
# per hot run in the backtest and every time in production; 22.0% of the trades
# behind that +$21.32 (420/1911) were instant re-entries this bot refuses.
#
#     STOP 0.03 @0.86bps:   recorded +$21.32 (h1/h2 +12.05/+9.31)
#                          CORRECTED  −$11.57, BOTH HALVES NEGATIVE
#
# So Lighter's tape does NOT invert the Hyperliquid claim above — the inversion
# was the artifact. Both of that harness's headline verdicts were artifacts:
# first "the strategy is dead" (an unmeasured 5bps), then "the stop is the bug"
# (this). Nothing currently supports tightening this stop.
#
# HARD_STOP stays 0.10 — unchanged since 17-Jul, but now for a better reason:
# the evidence that argued for tightening it no longer exists. The friction
# caveat also still stands on its own — Lighter's real per-book slippage has
# never been measured (0 measured fills to date), and every stop verdict here
# turns on it.
#
# ✅ RESOLVED 2026-07-22 (operator: "unset to 0.10 — clean the A/B"). The
# EXPERIMENT JUDGE'S CONTROL ARM (funding-farmer-shadow) had carried
# FUNDING_HARD_STOP=0.03 since 17-Jul, set on the strength of the number
# withdrawn above — so the paired promotion bar, the fleet's only path to
# live.funding.*, was comparing arms that differed by the xp candidate AND by
# the stop. The env var was found already REMOVED from the service; the shadow
# was restarted 22:06 Sydney and now boots at the 0.10 default (verified in its
# banner). Both arms are now at 0.10, so the A/B varies only the intended
# xp.funding.enter_apr candidate. The prior "accumulated evidence" was itself
# confounded, so nothing valid was lost. (Operational rule retained: loosening
# a stop is safe with positions open; NEVER TIGHTEN a live stop with positions
# open — it is evaluated against them on the next loop and liquidates anything
# already >3% adverse.)
# See [[funding-farmer-stop-is-the-bug]], [[harness-must-mirror-productions-close-path]].
HARD_STOP = float(os.environ.get("FUNDING_HARD_STOP", "0.10"))     # 10% — HL-fitted; the Lighter counter-evidence was WITHDRAWN 22-Jul (above)
TAKE_PROFIT = float(os.environ.get("FUNDING_TAKE_PROFIT", "0.04"))  # 4% — lock the reversion pop
DAILY_LOSS_LIMIT = float(os.environ.get("FUNDING_DAILY_LOSS", "0.05"))
STOP_COOLDOWN_H = float(os.environ.get("FUNDING_STOP_COOLDOWN_H", "12"))  # quarantine after a stop
# [2026-07-21] repeat-stop escalation (the LIT lesson: 5 of 7 fleet stops
# were the same coin, re-selected by the entry gate after every 12h
# quarantine because its funding stays extreme). 0 disables.
REPEAT_STOP_COOLDOWN_H = float(os.environ.get("FUNDING_REPEAT_STOP_COOLDOWN_H", "72"))
REPEAT_STOP_WINDOW_D = float(os.environ.get("FUNDING_REPEAT_STOP_WINDOW_D", "7"))
BLIND_STOP_MISSES = int(os.environ.get("FUNDING_BLIND_STOP_MISSES", "3"))  # live fail-safe

# ---- position SCANNER (2026-07-11) — choose the best RISK-ADJUSTED positions, not
# just the hottest funder. Backtested (scripts/backtest_scanner.py, real HL funding+
# price, 150d, 6-slot portfolio): a realized-vol VETO + fresh-adverse-trend VETO + a
# widened entry gate lift net +155% and ret/DD 2.0->7.4, robust across both halves +
# OOS. HONEST CAVEAT: much of that gain is directional MEAN-REVERSION (regime-
# dependent), not extra funding — the vol veto (skip coins whose price is convulsing
# too hard to hold past the stop) is the DURABLE piece. All existing SAFETY gates stay
# as a floor; the scanner only refines WHICH survivors get the scarce slots. The
# cross-venue (_bench) + book-VWAP-slippage layer can't be backtested from HL history
# -> shipped as LIVE-ONLY, logged to venue_orders for the shadow ledger to validate.
# Toggle SCAN=off restores the exact legacy raw-|APR| selection (old-vs-new + rollback).
SCAN_ENABLED = os.environ.get("SCAN", "on").strip().lower() not in ("off", "0", "false", "no")
SCAN_VETO_VOL = float(os.environ.get("SCAN_VETO_VOL", "0.015"))  # skip 1h realized vol > 1.5%/hr
SCAN_VETO_ADVERSE = float(os.environ.get("SCAN_VETO_ADVERSE", "0.05"))  # skip fresh >5% adverse move
SCAN_MAX_SLIP_BPS = float(os.environ.get("SCAN_MAX_SLIP_BPS", "25"))    # clip VWAP-slip gate (deeper than 20 TOB)
# CANDLE-scan only the top-N by |apr|*bench. This is a deliberate governor bound: on a
# cold cache (restart) the deep-scan bursts up to SCAN_DEEP_MAX candle fetches against the
# ~21 weight/min bucket, so 15 leaves headroom for order/close txs. TRADE-OFF (reviewed,
# low-sev): in a large live pool (~215 markets) this prefilter can miss a lower-|apr| but
# higher-quality (low-vol) coin the score would have preferred — validate on the expanded-
# universe backtest + shadow ledger before raising it. The 30-coin backtest rarely has >15
# eligible, so shipped ~= backtested there.
SCAN_DEEP_MAX = int(os.environ.get("SCAN_DEEP_MAX", "15"))
SCAN_BOOK_PROBE = int(os.environ.get("SCAN_BOOK_PROBE", "5"))   # BOOK-fetch only the top-N finalists (governor)
SCAN_VOL_LOOKBACK_H = int(os.environ.get("SCAN_VOL_LOOKBACK_H", "24"))
SCAN_MOM_LOOKBACK_H = int(os.environ.get("SCAN_MOM_LOOKBACK_H", "6"))
# (candle features are cached per CLOSED hourly bar — see _candle_features — so they
# refresh the moment a new bar closes and are reused free within the hour; no TTL knob.)

# [2026-07-24 EXPLORE BUCKET — Lever 1 | operator: "not restricted to what it
# knows to win on" / "cut windows on the box so it's not starved"] The scanner
# above is a pure EXPLOIT ranker — it deep-scans only the top SCAN_DEEP_MAX by
# |apr|, so the book re-selects the same hottest funders (measured: ~2 coins) and
# never evaluates a mid-funding, high-QUALITY coin. This reserves SCAN_EXPLORE_K
# of the MAX_OPEN slots for COVERAGE-sampled coins ranked BELOW the exploit set —
# least-recently-tried first, so exploration sweeps the eligible universe over
# time. They pass the SAME Stage-B/C quality vetoes (vol / adverse / spread /
# slip); breadth never means trading convulsing junk, and the funding FLOOR is
# unchanged (no adverse-selection widening — that was measured to cost). Every
# explore entry is stamped src=explore so the brain / radar / experiment-judge
# grade the bucket's own P&L. Default 0 = OFF: ships DARK on the live arm and the
# scanner's returned list stays byte-identical to today; enabled per-arm by env
# (shadow twin first). Adds up to K candle+book fetches to the ~21/min governor
# budget — keep K small. HONEST PRIOR: on 150d Lighter tape the explore slice
# backtested NEGATIVE within the top-25 liquid set (a funding-harvest edge is
# monotonic in funding extremity), so this is a SHADOW probe of whether a wider
# universe hides breadth, not a proven earner.
SCAN_EXPLORE_K = int(os.environ.get("SCAN_EXPLORE_K", "0"))

# Entry gate. The DEFAULT KEEPS THE TUNED 0.40 SAFETY GATE — the scanner's mandate is to
# pick better AMONG the survivors (veto stop-out traps + risk-adjusted rank), NOT to
# loosen the floor. Widening to ~0.25 lifts the in-cache net far more (+155% vs +53%) but
# partly as a flat-slippage backtest artifact, ~doubles churn, and changes a SAFETY gate —
# so it is OPT-IN (set SCAN_ENTER=0.25) and should be shadow-validated first. Defaults to
# ENTER_APR = no widening. (Backtest: scripts/backtest_scanner.py.)
SCAN_ENTER = float(os.environ.get("SCAN_ENTER", str(ENTER_APR)))
ENTER_GATE = SCAN_ENTER if SCAN_ENABLED else ENTER_APR

# ---- Growth rail: EXPERIMENT arm + PROMOTED bars (2026-07-15) ---------------
# The -lshadow twin is the fleet's experiment arm: the experiment judge can
# move its bars via bounded xp.* levers (zero real money). The LIVE bot only
# ever consumes live.funding.* — written by the judge ALONE, after a
# candidate beats the live arm on the paired promotion bar. Env defaults
# always rule when no lever is live (TTL auto-revert = the resting state).
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None

_ENV_BARS = {"enter_apr": ENTER_APR, "scan_enter": SCAN_ENTER,
             "take_profit": TAKE_PROFIT, "max_hold_h": MAX_HOLD_H,
             # Lever 1/2 growth knobs — env defaults so a lever's expiry reverts
             # cleanly. explore_k numeric; conviction as (mode, lo, hi).
             "explore_k": SCAN_EXPLORE_K,
             "conviction": (CONVICTION_MODE, CONVICTION_LO, CONVICTION_HI)}
_ACTIVE_BARS = {}    # what this arm is running NOW — stamped on every close


def apply_levers(mode):
    """Overlay this arm's levers onto the module bars, from env defaults
    (never from mutated state — expiry reverts cleanly). Returns the moved
    levers for the log; refreshes _ACTIVE_BARS either way."""
    global ENTER_APR, SCAN_ENTER, ENTER_GATE, TAKE_PROFIT, MAX_HOLD_H
    global SCAN_EXPLORE_K, CONVICTION_MODE, CONVICTION_LO, CONVICTION_HI
    prefix = {"lighter_shadow": "xp.funding.", "lighter_live": "live.funding."}.get(mode)
    moved = {}
    ENTER_APR, SCAN_ENTER = _ENV_BARS["enter_apr"], _ENV_BARS["scan_enter"]
    TAKE_PROFIT, MAX_HOLD_H = _ENV_BARS["take_profit"], _ENV_BARS["max_hold_h"]
    # growth knobs revert to env each call; a live/xp lever overrides below
    SCAN_EXPLORE_K = _ENV_BARS["explore_k"]
    CONVICTION_MODE, CONVICTION_LO, CONVICTION_HI = _ENV_BARS["conviction"]
    if tuning is not None and prefix:
        ea = tuning.get_lever(prefix + "enter_apr", ENTER_APR)
        if ea != ENTER_APR:
            ENTER_APR = SCAN_ENTER = ea         # one coherent gate
            moved[prefix + "enter_apr"] = ea
        tp = tuning.get_lever(prefix + "take_profit", TAKE_PROFIT)
        if tp != TAKE_PROFIT:
            TAKE_PROFIT = tp
            moved[prefix + "take_profit"] = tp
        mh = tuning.get_lever(prefix + "max_hold_h", MAX_HOLD_H)
        if mh != MAX_HOLD_H:
            MAX_HOLD_H = mh
            moved[prefix + "max_hold_h"] = mh
        # Lever 1 — explore slots (registry-clamped int; entry loop caps at max_open-1)
        ek = tuning.get_lever(prefix + "explore_k", None)
        if ek is not None and int(ek) != SCAN_EXPLORE_K:
            SCAN_EXPLORE_K = int(ek)
            moved[prefix + "explore_k"] = SCAN_EXPLORE_K
        # Lever 2 — conviction as a numeric up-cap: >1.0 => scaled(floor 1.0, cap hi).
        # Only ever sizes UP on the live arm; the notional cap still bounds it.
        ch = tuning.get_lever(prefix + "conviction_hi", None)
        if ch is not None and float(ch) > 1.0:
            CONVICTION_MODE, CONVICTION_LO, CONVICTION_HI = "scaled", 1.0, float(ch)
            moved[prefix + "conviction_hi"] = float(ch)
    ENTER_GATE = SCAN_ENTER if SCAN_ENABLED else ENTER_APR
    _ACTIVE_BARS.clear()
    _ACTIVE_BARS.update({"enter_apr": ENTER_APR, "take_profit": TAKE_PROFIT,
                         "max_hold_h": MAX_HOLD_H, "explore_k": SCAN_EXPLORE_K,
                         "conviction": CONVICTION_MODE,
                         "arm": mode or "paper", "tuned": sorted(moved)})
    return moved


# [2026-07-22 LEVER FLAP FIX — operator: "implement the flap to all those who
# need it"] The (bw) taker study measured the class on the sibling book: a
# WIDER lever expiring mid-position snaps the tighter default onto an
# in-flight trade and books the whole gap instantly. This bot's lever-driven
# exit bars are take_profit and max_hold_h, on BOTH arms (xp.* on the shadow
# twin, live.funding.* on real money): a judge promotion starting/fading
# mid-hold is exactly such a snap. The rule now: THE BARS PRICED AT ENTRY
# GOVERN THE TRADE — entries stamp them into meta, exits read the stamp.
# enter_apr stays live-read (it gates NEW entries only); HARD_STOP / EXIT_APR
# / flip are env-only, never levers, unchanged. This also makes the judge's
# ran_candidate receipt strictly truthful: a row stamped with candidate bars
# now provably RAN them to its exit. Unstamped/legacy positions keep the old
# close-time behavior; LEVER_GRANDFATHER=off reverts it everywhere.
LEVER_GRANDFATHER = os.environ.get("LEVER_GRANDFATHER", "on").strip().lower() \
    not in ("off", "0", "no", "false", "disabled")


def pos_bars(m):
    """(take_profit, max_hold_h) GOVERNING an open position: its entry stamp
    when grandfathering is on and sane, else the module's current bars
    (fail-safe: legacy/junk behaves exactly as before)."""
    try:
        if LEVER_GRANDFATHER:
            b = (m or {}).get("bars") or {}
            tp = float(b["take_profit"])
            mh = float(b["max_hold_h"])
            if tp > 0.0 and mh > 0.0:
                return tp, mh
    except (KeyError, TypeError, ValueError):
        pass
    return TAKE_PROFIT, MAX_HOLD_H

# ---- funding-SLOPE entry gate (2026-07-11) — only enter while the rate is
# still BUILDING (|apr| >= |apr LOOKBACK_H ago|). Backtested on the 150d
# portfolio sim (scripts/backtest_funding_leverage.py): at the live 2x config
# baseline +1.3% -> +8.4% with LOWER maxDD (16.5% -> 12.5%), positive in BOTH
# halves; the mirror rule (enter only on rollover) is symmetrically negative
# (-13.3%) — the effect is causal, not noise. 1h lookback chosen for
# ROBUSTNESS: 3h scores higher in-cache (+24.6%) but sits next to a sign FLIP
# at 4h — a sweet-spot overfit trap. FAIL-OPEN when history is missing
# (restart gap ~1h) — matches the backtest's handling exactly.
SLOPE_GATE = os.environ.get("FUNDING_SLOPE_GATE", "on").strip().lower() \
    not in ("off", "0", "false", "no")
SLOPE_LOOKBACK_H = float(os.environ.get("FUNDING_SLOPE_LOOKBACK_H", "1"))

# ---- coin-quality VETO (2026-07-11 SELF-CORRECT, RESTRICT-ONLY) — skip entry
# on coins the fleet's OWN measured evidence flags as toxic (slip > 15bps or
# stop-rate >= 50%, computed by market_context.py from venue_orders /
# paper_trades). HARD PRINCIPLE: automated evidence only ever REMOVES
# candidates — it can never widen a gate, raise size, or add leverage. Fails
# open (no veto state -> no vetoes). Toggle: FUNDING_QUALITY_VETO=off.
QUALITY_VETO = os.environ.get("FUNDING_QUALITY_VETO", "on").strip().lower() \
    not in ("off", "0", "false", "no")

LOOP_SECONDS = int(os.environ.get("FUNDING_LOOP_SECONDS", "300"))

# [2026-07-17 IMB-03] one-shot log flag for a stale coin-vetoes payload
# (warn on the fresh->stale transition, not every 5-min loop).
_veto_stale = {"warned": False}

LOG_FILE = os.environ.get("FUNDING_LOG_FILE", "funding_lighter_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _slope_ref(hist, now_ts, lookback_s):
    """Newest funding-apr sample at least lookback_s old (staleness-bounded to
    3x lookback). None = not enough history -> the gate FAILS OPEN."""
    if not hist:
        return None
    ref = None
    for ts, apr in hist:                      # oldest -> newest
        age = now_ts - ts
        if lookback_s <= age <= 3 * lookback_s:
            ref = apr                          # keep the newest qualifying
        elif age < lookback_s:
            break
    return ref


def _mctx_slice(mctx, coin):
    """[2026-07-11 INSTRUMENT-FIRST] Compact market-context snapshot attached to
    every ledgered ENTRY (see market_context.py). Validation dataset only —
    nothing here gates a trade until a factor passes the both-halves bar."""
    c = (mctx.get("coins") or {}).get(coin) or {}
    return {"heat": mctx.get("heat_mean_apr"), "btc_vol": mctx.get("btc_vol_1h"),
            "oi_chg_1h": c.get("oi_chg_1h"), "oi_chg_24h": c.get("oi_chg_24h"),
            "premium_bps": c.get("premium_bps"), "liq_1h": c.get("liq_1h")}


def fresh_mid(ctx, coin):
    """Current mid from the LIVE book, or None if unavailable. NEVER falls back to
    the funding-map mark — that is a last-trade price frozen at client construction
    and using it on the stop path would silently freeze the stop while the real
    price runs away. Callers MUST treat None as 'cannot evaluate risk here'.
    Shared impl: venues/marks.py (also sorts the unsorted REST-snapshot
    fallback, which this local copy did not)."""
    return marks.fresh_mid(ctx.venue, coin)


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


# ============================ POSITION SCANNER ==============================
# Chooses the best RISK-ADJUSTED candidates for the scarce slots (see the SCAN_*
# config block for the thesis + backtest). Cheap funding-only prefilter runs in the
# main loop; these helpers do the deep-scan (candles + one book fetch) on the top-N.
_feat_cache = {}   # coin -> (ts, {vol, ret_mom}); candle features are slow-moving


def _candle_features(ctx, coin):
    """Realized vol + short-horizon momentum from ~1d of CLOSED 1h candles. Returns
    {'vol','ret_mom'} or None if unavailable — None means 'cannot assess price risk',
    and the caller MUST skip the candidate (never enter blind on the vol veto).
    Definitions match scripts/backtest_scanner.py EXACTLY: vol = sample stdev of the
    last SCAN_VOL_LOOKBACK_H hourly returns; ret_mom = the SCAN_MOM_LOOKBACK_H-hour
    close-to-close return.

    [review 2026-07-11] Two fixes so live == backtested + no look-ahead:
      * DROP the forming (current-hour) bar — candles() returns it as the last row;
        including it would compute vol/momentum off a partial bar (the backtest uses
        closed bars only) and read the current price into the entry feature.
      * Cache is keyed on the most-recent CLOSED hour, not a wall-clock TTL, so it
        refreshes the instant a new bar closes (a fresh vol spike is picked up next
        loop, not up to ~50min later) and is otherwise reused free within the hour.
    Rows are sorted chronologically (don't trust API order) before differencing."""
    now = time.time()
    last_closed = int(now // 3600) * 3600 - 3600     # open-ts of the newest CLOSED hour (sec)
    hit = _feat_cache.get(coin)
    if hit and hit[0] == last_closed:
        return hit[1]
    need_h = max(SCAN_VOL_LOOKBACK_H, SCAN_MOM_LOOKBACK_H) + 4
    try:
        end_ms = int(now * 1000)
        rows = ctx.venue.candles(coin, "1h", end_ms - need_h * 3600 * 1000, end_ms)
    except Exception:
        return None
    bars = []
    for c in rows or []:
        try:
            t_s = int(c["t"]) // 1000
            cl = float(c["c"])
        except (KeyError, TypeError, ValueError):
            continue
        if t_s > last_closed:            # drop the forming (current-hour) bar
            continue
        bars.append((t_s, cl))
    bars.sort()                          # chronological; API order not trusted
    closes = [cl for _, cl in bars]
    if len(closes) < SCAN_VOL_LOOKBACK_H + 1:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0
            for i in range(1, len(closes)) if closes[i - 1]]
    w = rets[-SCAN_VOL_LOOKBACK_H:]
    mean = sum(w) / len(w)
    vol = math.sqrt(sum((r - mean) ** 2 for r in w) / (len(w) - 1)) if len(w) > 1 else 0.0
    ret_mom = (closes[-1] / closes[-1 - SCAN_MOM_LOOKBACK_H] - 1.0) \
        if len(closes) > SCAN_MOM_LOOKBACK_H and closes[-1 - SCAN_MOM_LOOKBACK_H] else 0.0
    feats = {"vol": vol, "ret_mom": ret_mom}
    _feat_cache[coin] = (last_closed, feats)
    return feats


def book_metrics(ctx, coin, order_usd):
    """ONE orderbook fetch -> {mid, spread_bps, buy_slip, sell_slip}. buy/sell_slip is
    the VWAP slippage (bps, >=0) to fill an `order_usd` clip walking the asks/bids;
    None for a side without enough depth for the clip. Replaces the old
    book_spread_bps + fresh_mid DOUBLE fetch on the entry path (governor efficiency)."""
    try:
        book = ctx.venue.orderbook(coin)
    except Exception:
        return None
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if not bids or not asks:
        return None
    # sort defensively best-first — the ws cache is pre-sorted but the REST-snapshot
    # fallback (the Railway norm, ws is CDN-blocked) is NOT, and the VWAP walk below
    # would be wrong on an unordered book. [review 2026-07-11]
    bids = sorted(bids, key=lambda x: -x[0])     # highest bid first
    asks = sorted(asks, key=lambda x: x[0])      # lowest ask first
    if not bids[0][0] or not asks[0][0]:
        return None
    bid, ask = bids[0][0], asks[0][0]
    mid = (bid + ask) / 2.0

    def vwap_slip(levels, adverse_up):
        need, cost, base = order_usd, 0.0, 0.0
        for px, sz in levels:
            if px <= 0 or sz <= 0:
                continue
            take = min(need, px * sz)
            cost += take
            base += take / px
            need -= take
            if need <= 1e-9:
                break
        if need > 1e-9 or base <= 0:
            return None                      # book too thin for the clip
        vwap = cost / base
        return (vwap - mid) / mid * 1e4 if adverse_up else (mid - vwap) / mid * 1e4

    # near-touch notional depth within +/-0.5% of mid (for the imbalance tiebreak)
    band = mid * 0.005
    bid_depth = sum(px * sz for px, sz in bids if px >= mid - band)
    ask_depth = sum(px * sz for px, sz in asks if px <= mid + band)
    return {"mid": mid, "spread_bps": (ask - bid) / mid * 1e4,
            "buy_slip": vwap_slip(asks, True), "sell_slip": vwap_slip(bids, False),
            "bid_depth": bid_depth, "ask_depth": ask_depth}


def cross_venue_mult(f):
    """Bounded [0.5, 1.2] score multiplier from cross-venue funding agreement
    (f['_bench']: binance/bybit/hyperliquid). Benches confirming Lighter's sign =
    structural crowding (reward); a Lighter-only extreme = local dislocation (demote).
    LIVE-ONLY (no _bench history to backtest); never a hard gate, never re-admits a
    vetoed coin — it only re-orders survivors. Returns 1.0 when there is no bench data
    (e.g. hl_paper)."""
    rate = f.get("rate") or 0.0
    bench = f.get("_bench") or {}
    if not rate or not bench:
        return 1.0
    total = sum(1 for v in bench.values() if v)
    if not total:
        return 1.0
    agree = sum(1 for v in bench.values() if v and (v > 0) == (rate > 0))
    return 0.5 + 0.7 * (agree / total)       # 0 agree -> 0.5, all agree -> 1.2


def scan_candidates(ctx, prelim, order_usd, log, last_tried=None):
    """Three governor-aware stages; returns finalists ranked best-first as
    (coin, f, apr, is_short, book_metrics, evidence). Fetch-cost is bounded so the
    scan can't drain the ~21 weight/min Lighter budget shared with order txs + sibling
    bots (on Railway the ws is CDN-blocked, so EVERY orderbook() costs 1 token):

      A. FREE prefilter — rank the whole eligible pool by |apr| x cross-venue mult
         (both already in the funding_map row; 0 extra tokens). Steer the scarce
         candle/book budget toward structurally-crowded names.
      B. CANDLE deep-scan the top SCAN_DEEP_MAX (cached ~50min): VETO stop-out traps
         (vol / adverse-trend) and score survivors by |APR| x bounded risk discounts
         x cross-venue. This is the BACKTESTED core (scripts/backtest_scanner.py).
      C. BOOK-probe only the top SCAN_BOOK_PROBE survivors (ONE fetch each): spread +
         clip-slippage gate + a small book-imbalance tiebreak. Live-only overlay.

    EXPLORE (Lever 1, SCAN_EXPLORE_K>0): additionally coverage-samples K coins from
    BELOW the exploit cut (least-recently-tried first, via `last_tried`) and runs
    them through the SAME B/C vetoes, tagged src=explore and returned AHEAD of the
    exploit finalists so the entry loop's reservation holds under slot scarcity.
    K=0 (default) returns exactly the exploit list — byte-identical to pre-Lever-1."""
    # STAGE A — free cross-venue-weighted prefilter over the whole eligible pool
    ranked_pre = sorted(prelim, key=lambda cfa: -abs(cfa[2]) * cross_venue_mult(cfa[1]))

    def _evaluate(cands, src):
        """STAGE B (candle veto + core score) then STAGE C (book probe) over
        `cands`; finalists best-first, ev tagged `src`. The vetoes do NOT bend for
        breadth — exploit and explore clear the identical quality bar."""
        survivors = []
        for coin, f, apr in cands:
            feats = _candle_features(ctx, coin)
            if feats is None:
                log.info("%s SCAN_SKIP no-candles (risk unverifiable)", coin)
                continue
            is_short = apr > 0                       # funding>0 -> longs pay -> we SHORT
            adverse = feats["ret_mom"] if is_short else -feats["ret_mom"]
            if feats["vol"] > SCAN_VETO_VOL:
                log.info("%s VETO vol %.2f%%/h > %.2f%%", coin, feats["vol"] * 100,
                         SCAN_VETO_VOL * 100)
                continue
            if adverse > SCAN_VETO_ADVERSE:
                log.info("%s VETO adverse-trend %+.1f%% (fresh move into our stop)",
                         coin, adverse * 100)
                continue
            vol_disc = 1.0 / (1.0 + (feats["vol"] / SCAN_VETO_VOL) ** 2)  # (0,1], .5 at veto
            adv_disc = math.exp(-6.0 * max(0.0, adverse))                 # (0,1]
            xv = cross_venue_mult(f)                                      # [0.5,1.2]
            core = abs(apr) * vol_disc * adv_disc * xv
            survivors.append((core, coin, f, apr, is_short, feats, xv, adverse))
        survivors.sort(key=lambda x: -x[0])

        finalists = []
        for core, coin, f, apr, is_short, feats, xv, adverse in survivors[:SCAN_BOOK_PROBE]:
            bm = book_metrics(ctx, coin, order_usd)
            if bm is None or bm["spread_bps"] > MAX_SPREAD_BPS:
                log.info("%s SPREAD/BOOK_SKIP (%s)", coin,
                         f"{bm['spread_bps']:.0f}bps" if bm else "no book")
                continue
            slip = bm["sell_slip"] if is_short else bm["buy_slip"]
            if slip is None or slip > SCAN_MAX_SLIP_BPS:
                log.info("%s VETO clip-slip %s bps > %.0f", coin,
                         f"{slip:.0f}" if slip is not None else "thin", SCAN_MAX_SLIP_BPS)
                continue
            # adverse near-touch imbalance: book leaning INTO our stop (short hurt by bids,
            # long by asks). Small tiebreak only — noisy/spoofable, never a gate.
            tot = bm["bid_depth"] + bm["ask_depth"]
            imb = (((bm["bid_depth"] - bm["ask_depth"]) if is_short
                    else (bm["ask_depth"] - bm["bid_depth"])) / tot) if tot > 0 else 0.0
            final = core * (1.0 - 0.30 * max(0.0, imb))
            ev = {"score": round(final, 4), "vol": round(feats["vol"], 5),
                  "adverse": round(adverse, 4), "slip_bps": round(slip, 1),
                  "xv": round(xv, 2), "imb": round(imb, 2), "src": src}
            finalists.append((final, coin, f, apr, is_short, bm, ev))
        finalists.sort(key=lambda x: -x[0])
        return [(c, f, apr, is_short, bm, ev)
                for _, c, f, apr, is_short, bm, ev in finalists]

    exploit = _evaluate(ranked_pre[:SCAN_DEEP_MAX], "exploit")
    if SCAN_EXPLORE_K <= 0:
        return exploit                       # DARK default — pre-Lever-1 behaviour
    # STAGE A' — EXPLORE: coverage-sample K from BELOW the exploit cut, least-
    # recently-tried first (never-tried == 0.0 sorts first), |apr| as tiebreak.
    lt = last_tried or {}
    tail = ranked_pre[SCAN_DEEP_MAX:]
    tail.sort(key=lambda cfa: (lt.get(cfa[0], 0.0), -abs(cfa[2])))
    explore = _evaluate(tail[:SCAN_EXPLORE_K], "explore")
    # explore FIRST so the reservation survives slot scarcity; the entry loop caps
    # explore opens at SCAN_EXPLORE_K and lets exploit overflow any unused window.
    return explore + exploit


# [2026-07-17] The cap rule now lives on the RAIL that enforces it
# (venues.safety.open_notional) — this bot and lighter_trend_bot each carried
# their own code-identical copy, and the Ticket Taker's live path would have
# been the third. Re-exported under the original private name so every call
# site and _selftest_notional() below are unchanged: the selftests are the
# proof this move is behaviour-neutral, not a claim that it is.
_open_notional = open_notional


# [2026-07-17 FILL READ] The three fill helpers moved to venues/fills.py, where
# the Ticket Taker's LIVE path imports the same code instead of copying it. The
# copy is exactly what let them drift: the taker's `_real_fill` stamped
# measured=True on any price that came back (reason string ignored), and its
# `_slip_bps_of` returned None for an unmeasured leg where this one returned a
# number computed off a blended read. Same move, same reason, and the same proof
# as _open_notional above: re-exported under the original private names so every
# call site and _selftest_fill_read() below are UNCHANGED — the selftests are
# what demonstrate the move is behaviour-neutral, not a claim that it is.
#
# ONE RULE DID CHANGE, deliberately. slip_bps_of now returns None for ANY
# unmeasured leg, not only when d == f. It was unreachable before: an unmeasured
# read had no price, so d == f always held and both rules agreed. read_fill's
# id-miss fallback is the first thing in the fleet's history to produce a REAL
# price with measured=False, and implementation_shortfall._fetch_order_slip
# AVGs slippage_bps without reading `measured` — so the old rule would have
# averaged a 180s VWAP blend into the live-vs-shadow execution verdict. Pinned
# by case (9) in _selftest_fill_read.
_measured_from_reason = measured_from_reason
_read_fill = read_fill
_slip_bps_of = slip_bps_of


def _record_close(bot, coin, ent_px, ent_ts, exit_px, price_pnl, fund_pnl, was_long,
                  reason, order_usd=ORDER_USD, venue=None, shadow=None,
                  bars=None):
    """Mirror a realized directional funding trade to the paper_trades ledger.
    pnl_abs = price P&L + funding accrued; pnl_pct is on the deployed clip
    (the ENTRY clip — callers pass meta['clip'], not the current loop's clip,
    so a mid-hold growth-rail clip change can't distort the per-trade return
    the promotion judge reads)."""
    pnl = float(price_pnl) + float(fund_pnl)
    pnl_pct = (pnl / (order_usd or 1.0)) if ent_px else None
    oa = datetime.fromtimestamp(ent_ts, tz=timezone.utc).isoformat() if ent_ts else None
    try:
        store.publish_paper_trade(
            bot, trade_id=f"{coin}:{ent_ts}", pnl_abs=pnl, pnl_pct=pnl_pct,
            pair=coin, opened_at=oa, closed_at=datetime.now(timezone.utc).isoformat(),
            reason=("long_" if was_long else "short_") + reason,
            venue=venue, shadow=shadow,
            # [2026-07-21 BRAIN JURISDICTION] entry-side tag: every close row
            # carried tag=null, so the brain's per-(bot, enter_tag) buckets
            # had nothing to key on — it structurally COULD NOT form a
            # reduce-only opinion on the fleet's largest real-money book even
            # if it turned bad. `<side>-funding` matches the taker's
            # `<side>-<lens>` convention the brain already parses. Reporting
            # field only: no entry/exit decision reads it.
            tag=("long-funding" if was_long else "short-funding"),
            # [2026-07-15] record fill prices + side so the implementation-
            # shortfall tracker can attribute the live-vs-shadow gap to the
            # ENTRY vs EXIT side (live = real fills, shadow = mark fills).
            side=("long" if was_long else "short"),
            entry_price=ent_px, exit_price=exit_px,
            # [2026-07-15 XP; 2026-07-22 FLAP FIX] stamp the bars this trade
            # RAN — since the flap fix that is the position's ENTRY stamp
            # (`bars` from meta), overlaid on the arm context; a trade that
            # opened before the stamp existed falls back to close-time
            # _ACTIVE_BARS, labelled via bars_basis. The judge's
            # ran_candidate receipt reads these values.
            extra=_close_bars_extra(bars))
    except Exception:
        pass


def _close_bars_extra(bars):
    """extra payload for a close row: arm context from _ACTIVE_BARS with the
    position's entry-stamped bar VALUES overlaid when present."""
    out = dict(_ACTIVE_BARS) if _ACTIVE_BARS else {}
    basis = "close-legacy"
    if isinstance(bars, dict) and bars:
        out.update({k: v for k, v in bars.items()})
        basis = "entry"
    return {"bars": out, "bars_basis": basis} if out else None


def parse_quarantine(st):
    """state dict -> (cooldown, stop_hist), tolerant of junk/absent fields."""
    st = st or {}
    _cd = st.get("cooldown") or {}
    _sh = st.get("stop_hist") or {}
    cd = ({str(k): float(v) for k, v in _cd.items()
           if isinstance(v, (int, float)) and not isinstance(v, bool)}
          if isinstance(_cd, dict) else {})
    sh = ({str(k): [float(t) for t in v
                    if isinstance(t, (int, float)) and not isinstance(t, bool)]
           for k, v in _sh.items() if isinstance(v, list)}
          if isinstance(_sh, dict) else {})
    return cd, sh


def read_quarantine(load_checked, key, tries=3, backoff=2.0, sleep=None):
    """(ok, cooldown, stop_hist) — ok=False ONLY when the READ ITSELF failed.

    [2026-07-22] (cb) made the post-stop quarantine durable but restored it with
    the UNCHECKED load_state(), which collapses "no row" and "read failed" into
    the same None ([[load-state-seeds-durable-state-on-a-failed-read]]). A
    Postgres blip at boot then looked exactly like a first run and silently
    re-armed every stopped coin — the precise failure (cb) exists to prevent,
    reintroduced one layer down. Bounded retry absorbs a transient blip;
    ok=False is a REAL failure and the caller must fail CLOSED (block new
    entries), never treat it as "nothing quarantined".
    """
    _sleep = sleep or time.sleep
    for attempt in range(max(1, tries)):
        ok, st = load_checked(key)
        if ok:
            cd, sh = parse_quarantine(st)
            return True, cd, sh
        if attempt < tries - 1:
            _sleep(backoff * (attempt + 1))
    return False, {}, {}


def main():
    p = argparse.ArgumentParser(description="Yield Harvester — Lighter directional funding")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    global _SUPERVISOR_BOT_ID
    # [2026-07-17 VENUE MUST BE EXPLICIT — real money] This bot's identity, and
    # whether it trades REAL MONEY, come from $VENUE. It has no default it can
    # safely inherit, and until now it had NO guard at all — the only
    # venue_context caller with neither a setdefault nor a mode refusal, while
    # every shadow-only bot had one.
    #   The shared default moved hl_paper -> lighter_shadow (correct on the
    #   operator's "the real money fallback has to be lighter" rule), and that
    #   silently flipped this bot's lost-var failure mode from LOUD to SILENT:
    #     before: lost VENUE -> hl_paper -> bot_id "perps-funding-lighter",
    #             which publishes nothing -> the row goes STALE -> the watchdog
    #             phones the operator.
    #     after : lost VENUE -> lighter_shadow -> "perps-funding-lighter-lshadow"
    #             == experiment_judge.SHADOW_BOT (online, $1012.78, 38 closed).
    #             The LIVE service would SIMULATE fills while its REAL positions
    #             sat unmanaged on the venue, double-write the judge's promotion
    #             arm (the only writer of live.funding.*), and NEVER page.
    # A lost Railway VENUE var is not hypothetical — it happened on 16-Jul and
    # is why the sniper/spread/family bots carry setdefaults. Both services
    # (trail-blazer-live=lighter_live, funding-farmer-shadow=lighter_shadow) set
    # it explicitly, so this is INERT for them: it only turns the lost-var case
    # back into a loud one. --once (offline smoke) is exempt.
    if not os.environ.get("VENUE", "").strip() and not args.once:
        raise SystemExit(
            "VENUE is unset. This bot's identity — and whether it trades REAL "
            "MONEY — comes from it, and its lighter_shadow id collides with the "
            "experiment judge's shadow arm. An inherited default must never "
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
    log.info("BOOT lighter_funding_bot build=%s bot=%s VENUE=%s clip=$%.2f max_open=%d "
             "| explore_k=%d conviction=%s", store.build_code_id(), bot_id, ctx.mode,
             order_usd, max_open, SCAN_EXPLORE_K, CONVICTION_MODE)

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
    rate_hist = {}     # coin -> deque[(ts, apr)] — slope-gate memory (in-process)
    hot_since = {}     # coin -> ts |apr| first >= ENTER_APR
    cooldown = {}      # coin -> ts until which re-entry is blocked (post-stop)
    stop_hist = {}     # coin -> [stop ts] inside the repeat window (21-Jul)
    explore_seen = {}  # coin -> ts last opened as an EXPLORE pick (Lever 1 coverage cursor)
    miss = {}          # coin -> consecutive fresh-price misses (live fail-safe)
    fund_realized = 0.0  # dry_run only: cumulative realized funding (price P&L is in broker)

    # [2026-07-22] QUARANTINE READ MUST DISTINGUISH "empty" FROM "unreadable".
    # (cb) made cooldown/stop_hist durable, but the restore used the UNCHECKED
    # load_state(), which collapses "no row" and "read failed" into the same
    # None ([[load-state-seeds-durable-state-on-a-failed-read]] — the same trap
    # that wiped a 7d live promotion). A Postgres blip at boot therefore looked
    # exactly like a first run and silently re-armed every stopped coin — the
    # very failure (cb) was written to close. Bounded retry converts a transient
    # blip into a good read; a genuinely failed read sets quarantine_blind, and
    # the entry gate then refuses NEW entries (restrict-only: exits and position
    # management are untouched) until a later cycle reads it successfully.
    quarantine_blind = False

    def _read_quarantine(key, tries=3, backoff=2.0):
        ok, cd, sh = read_quarantine(store.load_state_checked, key,
                                     tries=tries, backoff=backoff)
        if not ok:
            log.error("QUARANTINE READ FAILED for %s after %d attempt(s) — cannot "
                      "tell 'nothing quarantined' from 'could not read it'. "
                      "Blocking NEW entries until a clean read; exits unaffected.",
                      key, tries)
        return ok, cd, sh

    if dry_run:
        _saved = store.load_state(bot_id)
        if _saved and broker is not None and broker.restore_state(_saved.get("broker") or {}):
            meta = {str(k): v for k, v in (_saved.get("meta") or {}).items()}
            fund_realized = float(_saved.get("fund_realized") or 0.0)
            explore_seen = {str(k): float(v) for k, v in
                            (_saved.get("explore_seen") or {}).items()}
            _qok, _qcd, _qsh = _read_quarantine(bot_id)
            cooldown, stop_hist = _qcd, _qsh
            if not _qok:
                quarantine_blind = True
            log.info("restored paper state: equity $%.2f, %d open", broker.equity(),
                     broker.open_count())
    else:
        # Live: restore open-position meta so opened_ts (max-hold clock) survives
        # a redeploy instead of resetting to now.
        _live = store.load_state(bot_id + ":live") or {}
        meta = {str(k): v for k, v in (_live.get("meta") or {}).items()}
        explore_seen = {str(k): float(v) for k, v in
                        (_live.get("explore_seen") or {}).items()}
        # [2026-07-22 COOLDOWN DURABILITY — a MEASURED real-money guard failure]
        # `cooldown` and `stop_hist` were memory-only, so EVERY restart silently
        # cleared the post-stop quarantine. Measured on the live book: LIT was
        # stopped 21-Jul 11:23:12Z and RE-OPENED 16:03:29Z — 4h40m against a
        # 12h COOLDOWN, and it should have been the 72h repeat escalation
        # (LIT's 2nd stop inside REPEAT_STOP_WINDOW_D). The shadow twin, same
        # code, honoured 12.00h exactly on both of its stops — the difference is
        # that the LIVE service restarts constantly (11 deploys on 22-Jul alone).
        # LIT is 55.4% of the live book's gross loss and its funding is still
        # the venue's top extreme, so the gate re-selects it every cycle.
        # Same class as the flatten/halt redeploy incident: a memory-only guard
        # on a bot whose container is not.
        _qok, _qcd, _qsh = _read_quarantine(bot_id + ":live")
        cooldown, stop_hist = _qcd, _qsh
        if not _qok:
            quarantine_blind = True
        if cooldown or stop_hist:
            _still = sum(1 for t in cooldown.values() if t > time.time())
            log.info("restored post-stop quarantine: %d cooldown(s) (%d still "
                     "active), %d coin(s) with stop history — a restart no "
                     "longer re-arms a stopped coin", len(cooldown), _still,
                     len(stop_hist))
    live_baseline = (store.load_state(bot_id + ":live") or {}).get("initial_equity") \
        if not dry_run else None
    # [2026-07-21 D1] persisted capital ledger: guard-detected deposits/
    # withdrawals fold in here (loop below); pnl subtracts it + the env backfill.
    capital_adjust = ((store.load_state(bot_id + ":live") or {}).get("capital_adjust")
                      if not dry_run else None) or {"total": 0.0, "events": []}

    log.info("=" * 64)
    log.info("Yield Harvester (Lighter DIRECTIONAL funding) | venue=%s (%s)",
             ctx.mode, "modelled fills" if dry_run else "SENDS ORDERS")
    log.info("enter |apr|>=%.0f%% persist %.0fh, exit<%.0f%% | HARD STOP %.0f%% / TP %.0f%% "
             "| $%.0f x max %d | vol>=$%.0fM spread<=%.0fbps | loop=%ds", ENTER_GATE * 100,
             PERSIST_H, EXIT_APR * 100, HARD_STOP * 100, TAKE_PROFIT * 100, order_usd,
             max_open, MIN_VOL / 1e6, MAX_SPREAD_BPS, LOOP_SECONDS)
    if SCAN_ENABLED:
        log.info("SCANNER on: candle-scan top %d, book-probe top %d | VETO vol>%.1f%%/h | "
                 "adverse>%.0f%% | clip-slip>%.0fbps; rank |apr| x risk-discounts x "
                 "cross-venue. gate=%.0f%%%s", SCAN_DEEP_MAX, SCAN_BOOK_PROBE,
                 SCAN_VETO_VOL * 100, SCAN_VETO_ADVERSE * 100, SCAN_MAX_SLIP_BPS,
                 ENTER_GATE * 100,
                 " (WIDENED — opt-in; shadow-validate)" if SCAN_ENTER < ENTER_APR else "")
        log.info("Scanner edge is largely directional MEAN-REVERSION (regime-dependent); "
                 "the vol veto is the durable piece. Backtest: scripts/backtest_scanner.py.")
    else:
        log.info("SCANNER off (SCAN=off): legacy raw-|apr| selection.")
    log.info("DIRECTIONAL — not delta-neutral; price risk bounded by the hard stop.")
    log.info("SLOPE GATE %s: enter only while |apr| still >= its level %gh ago "
             "(building, not rolling over) — validated both-halves on the 150d "
             "portfolio sim; fails open for ~1h after restart.",
             "on" if SLOPE_GATE else "OFF", SLOPE_LOOKBACK_H)
    log.info("=" * 64)

    def account_value():
        return broker.equity() if dry_run else ctx.venue.account_value()

    def _live_pnl(eq):
        """[2026-07-21 D1] Live P&L = equity − baseline − CAPITAL. Deposits and
        withdrawals are the operator's money moving, not trading results —
        subtract the persisted guard-recorded ledger plus the env backfill
        (CAPITAL_ADJUST_USD). Reporting-only: no trading decision reads this."""
        if eq is None or live_baseline is None:
            return None
        return eq - live_baseline - capital_adjust["total"] - CAPITAL_ADJUST_USD

    def _fold_capital_moves():
        """[2026-07-21 D1] Fold guard-detected cash moves into the persisted
        capital ledger the moment they are accepted (fail-safe: no guard or no
        moves -> no-op). Events keep the last 20 for audit.

        [2026-07-23] Returns the NET $ folded this call (0.0 if none). The caller
        shifts the daily-loss rail's day_start by the same amount so a capital
        move lands in BOTH the equity read and the rail baseline. Otherwise a
        deposit MASKS a real drawdown and a withdrawal FABRICATES a halt (the
        rail compares raw equity to a day_start that never moved). The leash is
        NET of deposits/withdrawals (operator, 2026-07-23); this ledger stays
        DISPLAY-only (`_live_pnl`) — the caller reads the return value."""
        if dry_run:
            return 0.0
        _net = 0.0
        for _mv in getattr(ctx.venue, "pop_capital_moves", lambda: [])():
            capital_adjust["total"] = round(capital_adjust["total"] + _mv["delta"], 2)
            capital_adjust["events"] = (capital_adjust.get("events") or [])[-19:] + [_mv]
            _net += _mv["delta"]
            log.warning("capital ledger: $%+.2f (%s) -> lifetime $%+.2f "
                        "(+$%.2f env backfill) — P&L baseline absorbed it.",
                        _mv["delta"], _mv["how"], capital_adjust["total"],
                        CAPITAL_ADJUST_USD)
        return round(_net, 2)

    def positions():
        if dry_run:
            return {c: {"size": sz, "entry": en} for c, (sz, en) in broker.pos.items()}
        return ctx.venue.positions()

    def _real_exit(coin, is_short, fallback, client_id=None, tx_hash=None,
                   settle_ms=None):
        """[2026-07-17 FILL READ] (px, measured, reason) — REAL exit fill (venue
        trades read; closing a long SELLS -> is_ask=True) or the decision price.

        `client_id` is the order's own name, threaded from the market_close that
        produced this exit. Without it the read blends every same-side fill in a
        180s window; with it, the fill is exact.

        Still returns `fallback` for the price when there is no read — the exit
        price is LOAD-BEARING (it feeds price_pnl and the ledger row), so it
        cannot be None. But it now says whether that price was measured, so the
        caller records slippage NULL instead of a fabricated zero. This is why
        the two legs differ: the entry leg's fill is telemetry and can be NULL;
        this one has to be a number either way."""
        if dry_run:
            return fallback, False, "dry_run"
        px, measured, reason = _read_fill(
            getattr(ctx.venue, "last_fill_detail", None), coin,
            is_ask=not is_short, since_ts=time.time() - 180, client_id=client_id,
            tx_hash=tx_hash, settle_ms=settle_ms)
        if px is not None:
            log.info("%s exit fill (venue): %.6g (decision %.6g) [%s%s]", coin,
                     px, fallback or 0.0, reason,
                     "" if measured else " — NOT measured")
        else:
            log.info("%s exit fill: no read [%s] — slippage NULL", coin, reason)
        return (px if px is not None else fallback), measured, reason

    def _real_entry(coin, is_short, fallback, client_id=None, tx_hash=None,
                   settle_ms=None):
        """[2026-07-17 FILL READ] (px_or_None, measured, reason) — REAL entry
        fill (OPENING a short SELLS -> is_ask=True).

        MIRROR of _real_exit, and it exists because A ROUND TRIP NEEDS BOTH
        LEGS. 445e189 gave the two CLOSE legs a real fill read and left the
        entry leg publishing `px_decision=px, px_fill=px` — the decision mid
        echoed into the fill field.

        Returns None (not the fallback) when there is no read, so the caller
        records px_fill=NULL rather than an echo: an echoed decision price is
        what let me compute a confident "0.000bps slippage" off this table an
        hour ago. TELEMETRY ONLY — nothing downstream consumes this price."""
        if dry_run:
            return None, False, "dry_run"
        px, measured, reason = _read_fill(
            getattr(ctx.venue, "last_fill_detail", None), coin,
            # opening a SHORT sells -> is_ask=True (the exact inverse of the
            # close leg's `is_ask=not is_short`).
            is_ask=is_short, since_ts=time.time() - 180, client_id=client_id,
            tx_hash=tx_hash, settle_ms=settle_ms)
        if px is not None:
            log.info("%s entry fill (venue): %.6g (decision %.6g) [%s%s]", coin,
                     px, fallback or 0.0, reason,
                     "" if measured else " — NOT measured")
        else:
            log.info("%s entry fill: no read [%s] — px_fill NULL", coin, reason)
        return px, measured, reason

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
                _res = ctx.venue.market_close(c)
            except Exception as e:
                log.error("flatten %s: %s", c, e)
                continue
            if _res is None:
                # [2026-07-23 AUDIT] no position under this key — already flat
                # (the flatten's own goal). Don't book a phantom close on the
                # stale size; the manage loop reconciles meta next cycle.
                log.warning("flatten %s: no position to close (already flat) — "
                            "not booking a phantom close", c)
                continue
            _decision_px = px                      # mid at the close decision
            # -> REAL venue fill if readable, named by the order's own client id
            px, _meas, _src = _real_exit(
                c, is_short, px, client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
            price_pnl = abs(held) * ((px - entry) if not is_short else (entry - px))
            n_closed += 1
            n_wins += 1 if price_pnl > 0 else 0
            _record_close(bot_id, c, entry, opened_ts, px, price_pnl, m.get("accrued", 0.0),
                          was_long=not is_short, reason=reason,
                          order_usd=float((m or {}).get("clip") or order_usd),
                          venue=venue_tag, shadow=shadow_tag,
                          bars=(m or {}).get("bars"))
            try:
                # [2026-07-17 FILL TELEMETRY] px_fill was px_decision — the
                # decision price echoed back, so slippage_bps was NULL on every
                # live order and the fleet could not measure its own execution.
                # `px` here is ALREADY the real venue fill when _real_exit got
                # one (it falls back to the decision mid), so pass the decision
                # mid separately and let the two differ.
                store.publish_venue_order(
                    bot_id, venue=("lighter" if venue_tag else "hl"), shadow=shadow_tag,
                    coin=c, side=("buy" if is_short else "sell"), size=abs(held),
                    px_decision=_decision_px, px_fill=px,
                    slippage_bps=_slip_bps_of(_decision_px, px, is_buy=is_short,
                                              measured=_meas),
                    raw={"reason": reason, "leg": "close",
                         "measured": _meas, "fill_src": _src})
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
    # [2026-07-11 DURABLE HALT] a tripped daily-loss halt survives restarts —
    # the memory-only flag meant a same-day redeploy silently resumed trading.
    _halt = store.load_daily_halt(bot_id, cur_day.isoformat())
    if _halt:
        halted_today = True
        day_start_equity = _halt.get("day_start_equity") or day_start_equity
        log.warning("daily-loss halt restored from state — halted for the rest of today.")
    elif not dry_run:
        # [2026-07-21 D3 — review item 15 residual] same-UTC-day persisted
        # baseline (the Ticket Taker's proven pattern): a PRE-halt restart
        # part-way down a losing day used to re-base the 10% daily-loss rail to
        # the already-depressed boot equity, so the rail could no longer fire on
        # that day's real drawdown. The halt record above stays SENIOR; a
        # persisted day_start for TODAY beats the boot re-read.
        _ds = (store.load_state(bot_id + ":live") or {}).get("day_start") or {}
        if _ds.get("day") == cur_day.isoformat() and _ds.get("equity"):
            day_start_equity = float(_ds["equity"])
            log.info("day-start equity restored from state: $%.2f (%s)",
                     day_start_equity, cur_day)
    last_ts = time.time()
    _last_moved = None      # growth-rail bars log dedup

    while True:
        t0 = time.time()
        # [2026-07-12 GO-GREEN] loop-top liveness touch: slow scans, venue
        # outages and skip-paths below can't read as a dead bot any more.
        store.heartbeat(bot_id)
        # [2026-07-15 GROWTH RAIL] live clip re-read each loop: the evidence
        # board's bounded live.clip_scale lever applies to NEW entries only
        # (open positions untouched); reverts with the lever's own expiry.
        _clip = ctx.order_usd(ORDER_USD)
        if _clip != order_usd:
            log.info("growth rail: clip %s -> %s (max_open recomputed)",
                     order_usd, _clip)
            order_usd = _clip
            max_open = ctx.max_open_positions(MAX_OPEN_POSITIONS)
        # [2026-07-15 XP] arm-aware bars: shadow twin runs the experiment
        # candidate (xp.*), live runs promoted values only (live.funding.*).
        _moved = apply_levers(ctx.mode)
        if sorted(_moved) != _last_moved:
            log.info("growth rail bars (%s): %s", ctx.mode,
                     _moved or "env defaults")
            _last_moved = sorted(_moved)
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            # [2026-07-21 AUDIT FIX] roll the day ONLY on a successful
            # baseline read. The old order stamped cur_day first, so a failed
            # account_value() left YESTERDAY's day_start_equity filed under
            # today — and the D3 restart-durable restore then trusted that
            # stale baseline across restarts (pre-D3 a restart re-read fresh
            # boot equity; D3 made the corruption durable). Failing the read
            # keeps yesterday's stamp so the roll retries next loop;
            # halted_today stays conservative until the roll lands.
            try:
                day_start_equity = account_value()
                cur_day, halted_today = now.date(), False
            except Exception:
                log.warning("day-roll equity read failed — keeping the %s "
                            "baseline; retrying next loop", cur_day)

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
        # [2026-07-21 D1] a deposit/withdrawal the guard accepted on that read
        # is capital — absorb it into the ledger before any P&L is computed.
        _cap_delta = _fold_capital_moves()
        # [2026-07-11 LATE BASELINE] if the boot/day-roll capture failed (venue
        # down, or the equity guard vetoed a dislocated print) the rail used to
        # stay OFF all day. Adopt the first credible read instead. This read is
        # already capital-inclusive, so it is NOT also shifted below.
        if day_start_equity is None and equity is not None:
            day_start_equity = equity
            log.warning("day-start equity adopted late: %.2f", equity)
        else:
            # [2026-07-23] keep day_start on the SAME raw footing as `equity` so a
            # capital move folded mid-day cancels in the rail's (day_start - equity)
            # — the leash measures TRADING P&L only (net of deposits/withdrawals).
            # capital_adjusted_day_start is the shared rule (venues/safety.py); it
            # shifts only when a baseline exists AND a move folded. The in-memory
            # value carries across the `while True` loop and is persisted for
            # restart-durability.
            day_start_equity, _shifted = capital_adjusted_day_start(
                day_start_equity, _cap_delta)
            if _shifted:
                log.warning("day-start equity shifted $%+.2f for a capital move -> "
                            "%.2f (daily-loss rail stays net of deposits/withdrawals)",
                            _cap_delta, day_start_equity)

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
            # single failed close (rate-limit storm, venue blip) left that
            # position with NO stop until the day rolled. Idempotent once the
            # book is flat; the kill-switch path already retries per loop, so
            # skip when the kill switch just flattened this same loop.
            if not dry_run and not ctx.rails.kill_check():
                _flatten_all("daily_loss")
            # [2026-07-11 HALT HEARTBEAT] keep the dashboard row fresh while
            # halted — the early `continue` skipped the publish below, so a
            # halted bot looked DEAD (stale row) instead of HALTED.
            try:
                if dry_run:
                    _open_fund = sum((meta.get(c) or {}).get("accrued", 0.0)
                                     for c in meta)
                    _hb_eq = broker.equity() + fund_realized + _open_fund
                    _hb_pnl = _hb_eq - START_EQUITY
                else:
                    _hb_eq = equity
                    _hb_pnl = _live_pnl(equity)   # capital-adjusted (D1)
                store.publish(
                    bot_id, status="paper" if ctx.mode == "hl_paper" and dry_run
                    else "halted",
                    equity=_hb_eq, pnl_abs=_hb_pnl,
                    closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                    extra={"mode": ctx.mode, "venue": ctx.mode,
                           "style": "directional-funding",
                           "held": {c: ("S" if (meta.get(c) or {}).get("is_short") else "L")
                                    for c in meta}})
            except Exception:
                pass
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

        # [2026-07-11 INSTRUMENT-FIRST] one cheap state read per loop; the
        # snapshot rides along on every entry's ledger row via _mctx_slice.
        try:
            _mctx = store.load_state("market-context") or {}
        except Exception:  # noqa: BLE001
            _mctx = {}
        try:
            _vp = (store.load_state("coin-vetoes") or {}) if QUALITY_VETO else {}
            _vetoes = _vp.get("coins") or {}
            # [2026-07-17 IMB-03] freshness gate on the LIVE entry path — the
            # one consumed payload that had none. A fossil set is not
            # evidence: a dead market-context either vetoed forever or (died
            # empty) silently disabled the veto forever. Stale -> NO vetoes,
            # the veto's documented fail-OPEN direction. Accepts the legacy
            # 'ts' stamp and an env TTL fallback so a publisher one deploy
            # behind still ages honestly.
            _vts = _vp.get("updated") or _vp.get("ts")
            _vttl = float(_vp.get("ttl_sec")
                          or os.environ.get("FUNDING_VETO_TTL_S", "3600"))
            _vage = ((now - datetime.fromisoformat(
                str(_vts).replace("Z", "+00:00"))).total_seconds()
                if _vts else None)
            if _vage is not None and 0 <= _vage <= _vttl:
                # ANY fresh payload (an empty set included) re-arms the
                # one-shot warning — a later, independent staleness episode
                # must not be silent (verify amendment).
                _veto_stale["warned"] = False
            elif _vetoes:
                if not _veto_stale["warned"]:
                    log.warning("coin-vetoes STALE (age %s > ttl %.0fs) — "
                                "discarding %d veto(s); quality veto fails "
                                "OPEN until the publisher is back",
                                f"{_vage:.0f}s" if _vage is not None
                                else "unstamped", _vttl, len(_vetoes))
                    _veto_stale["warned"] = True
                _vetoes = {}
        except Exception:  # noqa: BLE001
            _vetoes = {}

        # [2026-07-17 IMB-17] L2 long-budget veto: this book's directional
        # longs were counted INTO the fleet's long budget but the bot never
        # read the light — count and enforcement now match. Same contract as
        # the trend bot / family bot / taker: fresh payload + mode=enforce +
        # budget full -> skip NEW LONGS this loop (shorts, exits and stops
        # untouched; the short budget is deliberately unenforced — see the
        # 16-Jul balance audit, IMB-05 refuted). Missing/stale fails OPEN;
        # kill switch stays central: FLEET_RISK_MODE=advisory.
        fleet_long_veto = False
        try:
            _fr = store.load_state("fleet-risk") or {}
            _fage = (now - datetime.fromisoformat(
                str(_fr.get("updated")).replace("Z", "+00:00"))).total_seconds()
            _lb = _fr.get("long_budget")
            _lb = 10**9 if _lb is None else int(_lb)   # 0 is a REAL budget
            if (_fage <= float(_fr.get("ttl_sec") or 900)
                    and _fr.get("mode") == "enforce"
                    and (_fr.get("long_positions") or 0) >= _lb):
                fleet_long_veto = True
                log.info("FLEET LONG-BUDGET VETO — %s/%s directional longs; "
                         "no new LONG entries this cycle (shorts/exits "
                         "unaffected)", _fr.get("long_positions"),
                         _fr.get("long_budget"))
        except Exception:  # noqa: BLE001 — fail-safe open
            fleet_long_veto = False

        # [2026-07-11 SLOPE GATE] rolling in-process funding history (apr units)
        # feeding the building-vs-rolling-over entry gate. Restart loses ~1h of
        # history -> gate fails open, exactly as backtested.
        for _c, _f in fund.items():
            _r = _f.get("rate")
            if _r is not None:
                rate_hist.setdefault(_c, deque(maxlen=64)).append((t0, _r * H))

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
                        _res = ctx.venue.market_close(coin)
                        if _res is None:
                            # [2026-07-23 AUDIT] already flat — don't fabricate a
                            # blind-stop close on the stale held size (corrupts
                            # n_closed/n_wins); meta reconciles next loop.
                            log.warning("%s: fail-safe flatten found no position "
                                        "(already flat) — not booking a phantom "
                                        "close", coin)
                        else:
                            _bpx, _, _ = _real_exit(
                                coin, is_short, entry,
                                client_id=(_res or {}).get("client_order_index"),
                    tx_hash=(_res or {}).get("tx_hash"),
                    settle_ms=(_res or {}).get("settle_ms"))
                            _bpnl = abs(held) * ((_bpx - entry) if not is_short
                                                 else (entry - _bpx))
                            _record_close(bot_id, coin, entry, opened_ts, _bpx, _bpnl,
                                          m.get("accrued", 0.0), was_long=not is_short,
                                          reason="stop_blind",
                                          order_usd=float((m or {}).get("clip") or order_usd),
                                          venue=venue_tag, shadow=shadow_tag,
                                          bars=(m or {}).get("bars"))
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
                # [2026-07-17 BASIS FIX] Lighter quotes an 8h rate; this line
                # accrued it PER HOUR = 8x. Live equity is honest (the venue
                # charges the real thing) but this figure reaches the
                # per-trade ledger AND the win/loss call — an inflated carry
                # credit inflates the win rate of a book that COLLECTS carry.
                accr = ((1.0 if is_short else -1.0)
                        * funding_basis.to_hourly(rate, 'lighter') * notional * dt_h)
                m["accrued"] = m.get("accrued", 0.0) + accr
            meta[coin] = {**m, "is_short": is_short, "entry": entry, "opened_ts": opened_ts}

            held_h = (t0 - opened_ts) / 3600.0
            raw = (px - entry) / entry if entry else 0.0        # +ve = price rose
            # A SHORT loses when price rises (+raw is against us); a LONG loses
            # when price falls (so its adverse is -raw). +ve adverse == against us.
            adverse = raw if is_short else -raw
            favour = -adverse
            flipped = (apr is not None) and ((is_short and apr < 0) or (not is_short and apr > 0))

            # [2026-07-22 FLAP FIX] tp/hold from the position's OWN entry
            # stamp (pos_bars); stop/flip/decay bars are env-only, unchanged.
            _tp, _mh = pos_bars(m)
            decision = None
            if adverse >= HARD_STOP:
                decision = "stop"
            elif favour >= _tp:
                decision = "take_profit"
            elif flipped:
                decision = "flip"
            elif apr is not None and abs(apr) < EXIT_APR:
                decision = "decay"
            elif held_h >= _mh:
                decision = "max_hold"
            if decision is None:
                continue

            fund_pnl = m.get("accrued", 0.0)
            # [2026-07-17] BIND BEFORE THE BRANCH. 445e189 bound _decision_px
            # only in the `else`, but the publish below reads it unconditionally
            # -> every dry_run close raised NameError into the bare `except:
            # pass` beneath it, so the SHADOW arm silently stopped writing close
            # rows to venue_orders the moment that image deployed. The shadow
            # arm is the control this bot is judged against; losing its rows is
            # not cosmetic. Nothing in the ledger shows the break because the
            # deployed image still predates 445e189 — the bug is armed, not yet
            # fired. In dry_run the fill IS the decision mid (ShadowBroker
            # publishes its own modelled-fill row separately), so measured=False
            # is the honest label, not a degradation.
            _decision_px = px                      # mid at the close decision
            _meas, _src = False, "dry_run"
            if dry_run:
                price_pnl = broker.close(coin, px)   # realizes price P&L in broker
                fund_realized += fund_pnl
            else:
                try:
                    _res = ctx.venue.market_close(coin)
                except Exception as e:
                    log.error("close %s failed: %s — leaving position, retry next loop", coin, e)
                    continue
                if _res is None:
                    # [2026-07-23 AUDIT] None = the venue holds NO position under
                    # this key (already flat / externally closed / liquidated
                    # between the positions() read and here). Booking a close now
                    # fabricates price_pnl on the STALE held size and corrupts
                    # n_closed/n_wins — the exact data the promotion judge and the
                    # brain rest on. The Ticket Taker already treats None as a
                    # FAILED close; mirror it. Don't pop meta — the top-of-loop
                    # reconciliation (held==0 -> meta.pop) or a retry handles it.
                    log.warning("%s: close returned no position — NOT booking a "
                                "phantom close; reconciles next loop", coin)
                    continue
                # -> REAL venue fill if readable, named by the order's client id
                px, _meas, _src = _real_exit(
                    coin, is_short, px,
                    client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
                price_pnl = (abs(held) * (px - entry)) if not is_short \
                    else (abs(held) * (entry - px))
            realized += (price_pnl + fund_pnl) if dry_run else 0.0
            n_closed += 1
            n_wins += 1 if (price_pnl + fund_pnl) > 0 else 0
            log.info("CLOSE %s %s after %.1fh | price %+.2f funding %+.2f [%s]",
                     coin, "short" if is_short else "long", held_h, price_pnl,
                     fund_pnl, decision)
            _record_close(bot_id, coin, entry, opened_ts, px, price_pnl, fund_pnl,
                          was_long=not is_short, reason=decision,
                          order_usd=float((m or {}).get("clip") or order_usd),
                          venue=venue_tag, shadow=shadow_tag,
                          bars=(m or {}).get("bars"))
            try:
                # [2026-07-17 FILL TELEMETRY] px_fill was the decision price
                # echoed back -> slippage_bps NULL on every live order.
                store.publish_venue_order(
                    bot_id, venue=("lighter" if venue_tag else "hl"),
                    shadow=shadow_tag, coin=coin,
                    side=("buy" if is_short else "sell"), size=abs(held),
                    px_decision=_decision_px, px_fill=px,
                    slippage_bps=_slip_bps_of(_decision_px, px, is_buy=is_short,
                                              measured=_meas),
                    raw={"reason": decision, "leg": "close",
                         "measured": _meas, "fill_src": _src})
            except Exception:
                pass
            meta.pop(coin, None)
            hot_since.pop(coin, None)      # force a fresh persistence wait — no instant re-entry
            if decision == "stop":
                # [2026-07-21 AUDIT FIX] ESCALATING quarantine on repeat
                # stops. Measured across both arms: 5 of the Farmer's 7
                # stops are LIT shorts (-$9.17 of -$11.19 total stop
                # damage) — the coin is the venue's standing funding
                # extreme, so after every 12h quarantine the entry gate
                # re-selects the same squeeze. A SECOND stop inside
                # REPEAT_STOP_WINDOW_D escalates the quarantine to
                # REPEAT_STOP_COOLDOWN_H (72h default). Restrict-only
                # seatbelt: it can only ever skip re-entering a coin that
                # just stopped twice.
                stop_hist[coin] = [ts for ts in stop_hist.get(coin, [])
                                   if t0 - ts <= REPEAT_STOP_WINDOW_D * 86400]
                stop_hist[coin].append(t0)
                _cd_h = (REPEAT_STOP_COOLDOWN_H
                         if len(stop_hist[coin]) >= 2 else STOP_COOLDOWN_H)
                cooldown[coin] = t0 + _cd_h * 3600.0
                if _cd_h != STOP_COOLDOWN_H:
                    log.warning("%s: %d stops inside %gd — quarantine "
                                "ESCALATED to %gh", coin,
                                len(stop_hist[coin]),
                                REPEAT_STOP_WINDOW_D, _cd_h)

        # ---- persistence clock over the whole funding map (uses the SAME gate the
        # scanner enters on, else persistence would never arm at the wider gate) ----
        for c, f in fund.items():
            r = f.get("rate")
            if r is not None and abs(r * H) >= ENTER_GATE:
                hot_since.setdefault(c, t0)
            else:
                hot_since.pop(c, None)

        # ---- scan for new entries — cheap funding prefilter, then deep-scan ----
        open_now = sum(1 for v in pos.values() if (v.get("size") if isinstance(v, dict) else v))
        # [2026-07-22] If the post-stop quarantine could not be READ at boot, we
        # do not know which coins are quarantined — so we must not open anything.
        # Re-attempt every cycle; a transient Postgres blip self-heals here and
        # trading resumes. Restrict-only by construction: exits, stops, funding
        # accrual and position management below are untouched.
        if quarantine_blind:
            _qok, _qcd, _qsh = _read_quarantine(
                bot_id if dry_run else bot_id + ":live", tries=1)
            if _qok:
                quarantine_blind = False
                for _c, _t in _qcd.items():
                    cooldown.setdefault(_c, _t)
                for _c, _ts in _qsh.items():
                    stop_hist.setdefault(_c, _ts)
                log.warning("quarantine re-read OK — %d cooldown(s) recovered; "
                            "entries re-enabled", len(_qcd))
            else:
                log.warning("QUARANTINE BLIND — skipping all NEW entries this "
                            "cycle (exits unaffected)")

        if open_now < max_open and not quarantine_blind:
            # cheap prefilter: hard SAFETY gates on the funding map only (no network)
            prelim = []
            for c, f in fund.items():
                if c in meta or c in pos:
                    continue
                if c in cooldown and t0 < cooldown[c]:
                    continue
                r = f.get("rate")
                if r is None:
                    continue
                apr = r * H
                if abs(apr) < ENTER_GATE or (f.get("vol") or 0.0) < MIN_VOL:
                    continue
                if (t0 - hot_since.get(c, t0)) / 3600.0 < PERSIST_H:
                    continue
                if not ctx.supports(c):
                    continue
                prelim.append((c, f, apr))
            prelim.sort(key=lambda x: -abs(x[2]))

            if SCAN_ENABLED:
                # deep-scan the hottest SCAN_DEEP_MAX: veto traps + rank risk-adjusted.
                # Each tuple carries its already-fetched book_metrics + scan evidence.
                # Wrapped: a scanner bug must NEVER crash the loop that manages stops —
                # degrade to no new entries this loop. [review 2026-07-11]
                try:
                    ranked = scan_candidates(ctx, prelim, order_usd, log, explore_seen)
                except Exception as e:  # noqa: BLE001
                    log.error("scanner error (%s) — no new entries this loop", e)
                    ranked = []
            else:
                # legacy: raw |apr|, book fetched per-candidate below (bm/ev = None)
                ranked = [(c, f, apr, apr > 0, None, None) for c, f, apr in prelim]

            # [2026-07-24 EXPLORE RESERVATION — Lever 1] cap TOTAL explore
            # positions at SCAN_EXPLORE_K. Explore candidates arrive FIRST in
            # `ranked`, so they claim their reserved windows and exploit overflows
            # whatever explore doesn't use. K=0 -> no explore tags -> unchanged.
            n_explore = sum(1 for mm in meta.values()
                            if isinstance(mm, dict) and mm.get("src") == "explore")
            # clamp so EXPLOIT always keeps >=1 slot even if K is misconfigured high
            _expl_k = max(0, min(SCAN_EXPLORE_K, max_open - 1))
            for coin, f, apr, is_short, bm, ev in ranked:
                if open_now >= max_open or opened_this_loop >= MAX_NEW_PER_LOOP:
                    break
                src = (ev or {}).get("src", "exploit")
                if src == "explore" and n_explore >= _expl_k:
                    continue      # explore reservation full — leave the slot to exploit
                # [2026-07-11 QUALITY VETO] fleet-measured toxicity, restrict-only
                if coin in _vetoes:
                    log.info("%s VETO_SKIP (%s)", coin, _vetoes[coin])
                    continue
                # [2026-07-17 IMB-17] fleet long budget (computed above) —
                # NEW directional longs only; the funding mandate's shorts
                # and every exit path are untouched
                if not is_short and fleet_long_veto:
                    log.info("%s FLEET_LONG_VETO_SKIP", coin)
                    continue
                # [2026-07-11 SLOPE GATE] only enter while crowding still builds
                # (validated: see config block). Fails open with no history.
                _slope_prev = (_slope_ref(rate_hist.get(coin), t0,
                                          SLOPE_LOOKBACK_H * 3600)
                               if SLOPE_GATE else None)
                if _slope_prev is not None and abs(apr) < abs(_slope_prev):
                    log.info("%s SLOPE_SKIP (apr %+.1f%% < %+.1f%% %gh ago — rolling over)",
                             coin, apr * 100, _slope_prev * 100, SLOPE_LOOKBACK_H)
                    continue
                if bm is None:
                    # legacy / scanner-off: spread gate + fresh mid (own book fetch)
                    sp = book_spread_bps(ctx, coin)
                    if sp is None or sp > MAX_SPREAD_BPS:
                        log.info("%s SPREAD_SKIP (%.0fbps)", coin, sp if sp is not None else -1)
                        continue
                    px, spread_bps = fresh_mid(ctx, coin), sp
                else:
                    px, spread_bps = bm["mid"], bm["spread_bps"]   # from the deep-scan fetch
                if px is None:
                    continue
                clip = order_usd * conviction_mult(apr)   # Lever 2: dark default -> order_usd
                size = round(clip / px, 6)
                if not dry_run:
                    # [2026-07-15 AUDIT FIX v2] real deployed notional (held at
                    # their own clips + this loop's opens) — NOT open_now*clip,
                    # which breaches the cap when the growth rail moved the clip.
                    open_ntl = _open_notional(pos, meta, open_now, order_usd)
                    # cap check sees the CONVICTION clip, not the flat one — a
                    # bigger clip must be admitted against the cap it will fill.
                    if not ctx.rails.notional_ok(open_ntl, clip):
                        log.info("%s NOTIONAL_CAP_SKIP", coin)
                        continue
                _res = None
                try:
                    if dry_run:
                        broker.open(coin, not is_short, size, px)
                    else:
                        # KEEP the return: it carries this order's
                        # client_order_index, which is what turns the fill read
                        # below from a 180s same-side blend into a measurement.
                        _res = ctx.venue.market_open(coin, not is_short, size)
                except Exception as e:
                    log.error("open %s failed: %s", coin, e)
                    continue
                meta[coin] = {"is_short": is_short, "entry": px, "opened_ts": t0,
                              "accrued": 0.0, "clip": clip,   # deployed clip (conviction-scaled)
                              "src": src,                     # Lever 1: explore|exploit (grading)
                              # [2026-07-22 FLAP FIX] the bars priced at
                              # entry govern this trade (enter_apr is the
                              # admission gate, attribution only).
                              "bars": {"enter_apr": ENTER_APR,
                                       "take_profit": TAKE_PROFIT,
                                       "max_hold_h": MAX_HOLD_H}}
                open_now += 1
                opened_this_loop += 1
                if src == "explore":
                    n_explore += 1
                    explore_seen[coin] = t0   # coverage cursor -> rotate this coin to the back
                log.info("OPEN %s %s $%.2f | funding %+.1f%% APR | px %.6g | spread %.0fbps%s",
                         coin, "short" if is_short else "long", clip, apr, px, spread_bps,
                         (" | " + " ".join(f"{k}={v}" for k, v in ev.items())) if ev else "")
                try:
                    raw = {"apr": round(apr, 3), "spread_bps": round(spread_bps, 1),
                           "leg": "open", "mctx": _mctx_slice(_mctx, coin),
                           "conv_mult": round(clip / order_usd, 3) if order_usd else 1.0,
                           "slope": {"apr_prev": (round(_slope_prev, 4)
                                                  if _slope_prev is not None else None),
                                     "lookback_h": SLOPE_LOOKBACK_H,
                                     "gate": SLOPE_GATE}}
                    if ev:
                        raw["scan"] = ev      # vol/adverse/slip/xv/score -> shadow ledger
                    # [2026-07-17 FILL TELEMETRY — entry leg] was
                    # `px_decision=px, px_fill=px`: the decision mid echoed into
                    # the fill column, so ENTRY slippage was unmeasurable and
                    # anyone computing it off this table got a fabricated 0.000.
                    # A round trip needs BOTH legs; 445e189 fixed only the
                    # closes. px_fill is NULL when the venue gives no read —
                    # never an echo. TELEMETRY ONLY: meta[coin]["entry"] above
                    # is untouched (it feeds the stop/TP and the manage pass
                    # already reconciles it from avg_entry_price), so this
                    # changes what we RECORD, never what the bot DOES.
                    _fill_px, _meas, _src = _real_entry(
                        coin, is_short, px,
                        client_id=(_res or {}).get("client_order_index"),
                tx_hash=(_res or {}).get("tx_hash"),
                settle_ms=(_res or {}).get("settle_ms"))
                    raw["measured"] = _meas
                    raw["fill_src"] = _src
                    store.publish_venue_order(
                        bot_id, venue=("lighter" if venue_tag else "hl"),
                        shadow=shadow_tag, coin=coin,
                        side=("sell" if is_short else "buy"), size=size,
                        px_decision=px, px_fill=_fill_px,
                        slippage_bps=_slip_bps_of(px, _fill_px,
                                                  is_buy=not is_short,
                                                  measured=_meas),
                        raw=raw)
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
            pub_pnl = _live_pnl(equity)   # capital-adjusted (D1)
        top = sorted(((c, f.get("rate") or 0.0) for c, f in fund.items()),
                     key=lambda cr: -abs(cr[1]))[:3]
        try:
            store.publish(
                bot_id, status="paper" if ctx.mode == "hl_paper" and dry_run
                else ("halted" if halted_today else "online"),
                equity=pub_equity, pnl_abs=pub_pnl, open_trades=pub_open,
                closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                extra={"mode": ctx.mode, "venue": ctx.mode, "style": "directional-funding",
                       # lever state PUBLISHED (bot_pnl_store already stamps
                       # extra.build) so a deploy is confirmable from Postgres.
                       "levers": {"explore_k": SCAN_EXPLORE_K, "conviction": CONVICTION_MODE},
                       "held": {c: ("S" if (meta.get(c) or {}).get("is_short") else "L")
                                for c in meta},
                       "hottest_apr": {c: f"{r*H:+.0%}" for c, r in top},
                       # D1: total capital excluded from pnl_abs — self-describing
                       **({} if dry_run else {"capital_adjust": round(
                           capital_adjust["total"] + CAPITAL_ADJUST_USD, 2)})})
        except Exception:
            pass
        # persist state (dry_run: full paper account; live: baseline + open meta)
        try:
            if dry_run:
                store.save_state(bot_id, {
                    "broker": broker.to_state(), "meta": meta,
                    "fund_realized": fund_realized,
                    # [2026-07-22 ARM PARITY] the same quarantine the LIVE
                    # branch persists. Shipping it on one arm only is what the
                    # agronomy scan caught: this twin is the JUDGE'S CONTROL
                    # ARM, so a cooldown that survives a restart on live and
                    # not here makes the paired promotion bar compare two
                    # different rules (measured: 3 cooldown + 5 stop_hist leaks
                    # over 6 stop events on this arm while live leaked 1 of 2).
                    "cooldown": {c: t for c, t in cooldown.items()
                                 if t > time.time()},
                    "stop_hist": {c: ts for c, ts in (
                        (c, [t for t in v
                             if time.time() - t <= REPEAT_STOP_WINDOW_D * 86400])
                        for c, v in stop_hist.items()) if ts},
                    # [2026-07-24] explore coverage cursor (Lever 1). Pruned to a
                    # 14d window: a coin not explored that long resets to never-
                    # tried and regains priority — bounded + self-cleaning.
                    "explore_seen": {c: t for c, t in explore_seen.items()
                                     if time.time() - t <= 14 * 86400}})
            elif live_baseline is not None:
                store.save_state(bot_id + ":live", {
                    "initial_equity": live_baseline, "meta": meta,
                    # D1: guard-recorded deposits/withdrawals (capital, not P&L)
                    "capital_adjust": capital_adjust,
                    # D3: same-UTC-day rail baseline survives a pre-halt restart
                    "day_start": {"day": cur_day.isoformat(),
                                  "equity": day_start_equity},
                    # [2026-07-22] the post-stop quarantine, so a redeploy cannot
                    # re-arm a coin the bot just stopped out of. Pruned on write:
                    # expired cooldowns and stops outside REPEAT_STOP_WINDOW_D
                    # are dropped, so this cannot grow without bound.
                    "cooldown": {c: t for c, t in cooldown.items()
                                 if t > time.time()},
                    "stop_hist": {c: ts for c, ts in (
                        (c, [t for t in v
                             if time.time() - t <= REPEAT_STOP_WINDOW_D * 86400])
                        for c, v in stop_hist.items()) if ts},
                    # [2026-07-24] explore cursor (Lever 1) — dark on live (K=0 ->
                    # empty), persisted for arm parity with the shadow twin.
                    "explore_seen": {c: t for c, t in explore_seen.items()
                                     if time.time() - t <= 14 * 86400}})
        except Exception:
            pass

        held = ", ".join(f"{c}({'S' if (meta.get(c) or {}).get('is_short') else 'L'})"
                         for c in meta) or "none"
        log.info("scan ok | %d perps | held: %s | realized $%+.2f", len(fund), held, realized)

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
    """The exact 16-Jul breach scenario: cap $150, five $30 positions held at
    clip 30, growth-rail down-scale to clip 22.50 → the old open_now*order_usd
    estimate said $112.50 (a 6th entry passed); real deployment is $150 (at
    cap — the 6th must block)."""
    pos = {c: {"size": 1.0, "entry": 30.0} for c in "ABCDE"}
    meta = {c: {"clip": 30.0, "entry": 30.0} for c in "ABCDE"}
    assert _open_notional(pos, meta, 5, 22.50) == 150.0
    # meta lost entirely → venue entry notional (not the down-scaled clip)
    assert _open_notional(pos, {}, 5, 22.50) == 150.0
    # venue entry also missing → last-resort current clip (conservative floor)
    assert _open_notional({c: {"size": 1.0} for c in "ABCDE"}, {}, 5, 22.50) == 112.5
    # opens-this-loop not yet visible in pos count at the current clip
    assert _open_notional(pos, meta, 7, 22.50) == 195.0
    # short at its own entry (size*entry, sign-independent)
    assert _open_notional({"Z": {"size": -2.0, "entry": 20.0}}, {}, 1, 30.0) == 40.0
    print("lighter_funding_bot _selftest_notional OK")


def _selftest_fill_read():
    """[2026-07-17] Drives the fill read directly — the point of lifting it out
    of main(). Every case below is a MUTATION test: each one FAILS against the
    behaviour that shipped before this commit, so a revert cannot pass silently.

    The fixtures encode the venue layer's real contract (px, reason) with its
    real reason strings, not a paraphrase — a stub that mirrors names but not
    semantics is how a green test comes to mean nothing."""
    calls = []

    def fake(px_by_call, reasons):
        def _f(coin, is_ask, since_ts, client_id=None):
            calls.append(client_id)
            i = len(calls) - 1
            return px_by_call[i], reasons[i]
        return _f

    # 1) id MATCHES -> exact, and it is a MEASUREMENT.
    calls.clear()
    px, meas, src = _read_fill(fake([100.5], ["trades"]), "SOL", True, 0, 12345)
    assert (px, meas) == (100.5, True), (px, meas)
    assert calls == [12345], "the id must reach the venue — the whole point"

    # 2) NO id -> the venue blends; a price, but NOT a measurement.
    #    Pre-commit this bot ALWAYS took this path (it passed no id at all).
    calls.clear()
    px, meas, src = _read_fill(fake([100.5], ["trades(approx)"]), "SOL", True, 0, None)
    assert (px, meas) == (100.5, False), (px, meas)
    assert "approx" in src

    # 3) id MISSES on a readable tape -> fall back to the heuristic, say so.
    #    The taker's hard filter used to lose this case entirely (-> None); it
    #    now shares read_fill, and check 12(c) there pins the same behaviour
    #    end-to-end through main().
    calls.clear()
    px, meas, src = _read_fill(
        fake([None, 99.0], ["no-match:trades", "trades(approx)"]),
        "SOL", True, 0, 777)
    assert (px, meas) == (99.0, False), (px, meas)
    assert calls == [777, None], "must retry WITHOUT the id, exactly once"
    assert "id-miss" in src, src

    # 4) budget skip / auth failure -> NO retry. A second call would spend the
    #    governor's telemetry reserve to fail identically, and lighter_client is
    #    explicit that telemetry must never make the next order queue behind it.
    for bad in ("skipped:budget(2.0 tok, reserve 4)", "auth-failed:expired",
                "api-error:trades:TimeoutError:x", "empty:trades"):
        calls.clear()
        px, meas, _ = _read_fill(fake([None, 1.0], [bad, "trades(approx)"]),
                                 "SOL", True, 0, 777)
        assert (px, meas) == (None, False), (bad, px, meas)
        assert calls == [777], f"{bad!r} must NOT retry (spends budget to re-fail)"

    # 5) a raising venue never reaches the caller — telemetry cannot break money.
    def boom(coin, is_ask, since_ts, client_id=None):
        raise RuntimeError("venue on fire")
    px, meas, src = _read_fill(boom, "SOL", True, 0, 1)
    assert (px, meas) == (None, False) and "read-raised" in src, src
    assert _read_fill(None, "SOL", True, 0, 1) == (None, False, "no-detail-fn")

    # 6) measured d == f is a TRUE zero; unmeasured d == f stays NULL.
    #    The old rule returned None for both and silently dropped every genuinely
    #    perfect fill (1000BONK filled exactly at mark on the taker's first live
    #    order — real data the fleet threw away).
    assert _slip_bps_of(100.0, 100.0, is_buy=True, measured=True) == 0.0
    assert _slip_bps_of(100.0, 100.0, is_buy=True, measured=False) is None
    assert _slip_bps_of(100.0, 100.0, is_buy=True) is None, "default must be safe"

    # 7) sign: POSITIVE = worse than the decision price, both directions.
    assert round(_slip_bps_of(100.0, 100.1, is_buy=True, measured=True), 4) == 10.0
    assert round(_slip_bps_of(100.0, 99.9, is_buy=False, measured=True), 4) == 10.0
    assert round(_slip_bps_of(100.0, 99.9, is_buy=True, measured=True), 4) == -10.0
    assert _slip_bps_of(0.0, 1.0, is_buy=True, measured=True) is None
    assert _slip_bps_of(None, 1.0, is_buy=True, measured=True) is None

    # 8) `measured` is derived from the venue's OWN label, never re-decided here.
    assert _measured_from_reason(1.0, "trades") is True
    assert _measured_from_reason(1.0, "recentTrades(after empty:trades)") is True
    assert _measured_from_reason(1.0, "trades(approx)") is False
    assert _measured_from_reason(1.0, "recentTrades-approx(after x)") is False
    assert _measured_from_reason(None, "trades") is False, "no price is no measurement"

    # 9) UNMEASURED IS NULL EVEN WHEN d != f. The rule the two copies disagreed
    #    on, and the one read_fill's fallback makes REACHABLE: an approx read is
    #    the first thing in the fleet's history to carry a real price AND
    #    measured=False. This bot's old rule returned the bps for it (only the
    #    d == f branch consulted `measured`); the taker's returned None. That
    #    number would land in venue_orders.slippage_bps, which
    #    implementation_shortfall._fetch_order_slip AVGs with no `measured`
    #    filter at all — one blended row is indistinguishable from a clean one in
    #    the live-vs-shadow execution verdict. Record the blend as px_fill (it IS
    #    a real price); record NO slippage from it.
    assert _slip_bps_of(100.0, 100.5, is_buy=True, measured=False) is None, \
        ("an unmeasured leg must record NULL slippage even with a real blended "
         "price — implementation_shortfall AVGs this column unfiltered")
    assert _slip_bps_of(100.0, 100.5, is_buy=True, measured=True) is not None, \
        "and the strict rule must not swallow a genuine measurement"

    print("lighter_funding_bot _selftest_fill_read OK")


def _selftest_flap():
    """[2026-07-22] The bars priced at entry govern the trade (lever-flap
    fix). A judge fade releasing live.funding.take_profit mid-position must
    not snap the tighter default onto an in-flight trade."""
    global LEVER_GRANDFATHER
    # position stamped under a PROMOTED (wider-hold, tighter-tp) candidate
    m = {"bars": {"enter_apr": 0.60, "take_profit": 0.06, "max_hold_h": 96}}
    assert pos_bars(m) == (0.06, 96.0), pos_bars(m)
    # unstamped/legacy/junk -> the module's current bars, exactly as before
    assert pos_bars({}) == (TAKE_PROFIT, MAX_HOLD_H)
    assert pos_bars(None) == (TAKE_PROFIT, MAX_HOLD_H)
    assert pos_bars({"bars": {"take_profit": "x"}}) == (TAKE_PROFIT, MAX_HOLD_H)
    assert pos_bars({"bars": {"take_profit": -0.04, "max_hold_h": 96}}) == \
        (TAKE_PROFIT, MAX_HOLD_H), "nonsense sign -> current bars"
    # kill switch reverts behavior (stamps stay written regardless)
    _lg = LEVER_GRANDFATHER
    LEVER_GRANDFATHER = False
    assert pos_bars(m) == (TAKE_PROFIT, MAX_HOLD_H)
    LEVER_GRANDFATHER = _lg
    # close-row attribution: entry stamp overlays the arm context and is
    # labelled; a legacy close keeps close-time values, labelled so.
    _ACTIVE_BARS.clear()
    _ACTIVE_BARS.update({"enter_apr": 1.60, "take_profit": 0.04,
                         "max_hold_h": 72, "arm": "lighter_live",
                         "tuned": []})
    e = _close_bars_extra(m["bars"])
    assert e["bars_basis"] == "entry" and e["bars"]["take_profit"] == 0.06 \
        and e["bars"]["max_hold_h"] == 96 and e["bars"]["arm"] == "lighter_live", e
    e2 = _close_bars_extra(None)
    assert e2["bars_basis"] == "close-legacy" \
        and e2["bars"]["take_profit"] == 0.04, e2
    _ACTIVE_BARS.clear()
    assert _close_bars_extra(None) is None, "no context, no stamp -> None"
    print("lighter_funding_bot _selftest_flap OK")


def _selftest_quarantine():
    """[2026-07-22] The post-stop quarantine must distinguish "genuinely no
    quarantine" from "could not read it". (cb) made it durable; it was still
    restored through the UNCHECKED load_state, so a Postgres blip at boot
    re-armed every stopped coin — exactly the failure (cb) closed."""
    # (1) a good read round-trips, and junk is dropped without killing the read
    st = {"cooldown": {"LIT": 1000.0, "BAD": "x", "T": True},
          "stop_hist": {"LIT": [1.0, 2.0, "x"], "NOPE": "notalist"}}
    ok, cd, sh = read_quarantine(lambda k: (True, st), "b")
    assert ok and cd == {"LIT": 1000.0} and sh == {"LIT": [1.0, 2.0]}, (ok, cd, sh)

    # (2) READ SUCCEEDED, genuinely empty -> ok=True, empty. Trading continues.
    ok, cd, sh = read_quarantine(lambda k: (True, None), "b")
    assert ok and cd == {} and sh == {}, (ok, cd, sh)

    # (3) THE REGRESSION: read FAILED -> ok=False. Must NOT look like (2).
    calls = []
    def _fail(k):
        calls.append(k)
        return False, None
    ok, cd, sh = read_quarantine(_fail, "b", tries=3, backoff=0, sleep=lambda s: None)
    assert ok is False and cd == {} and sh == {}, (ok, cd, sh)
    assert len(calls) == 3, f"must retry a transient blip, got {len(calls)}"

    # (4) a blip that clears on retry recovers WITHOUT going blind
    seq = [(False, None), (False, None), (True, {"cooldown": {"LIT": 5.0}})]
    ok, cd, sh = read_quarantine(lambda k: seq.pop(0), "b", tries=3, backoff=0,
                                 sleep=lambda s: None)
    assert ok and cd == {"LIT": 5.0}, (ok, cd, sh)

    # (5) the two states are DISTINGUISHABLE — the whole point. A caller that
    #     cannot tell them apart re-arms a stopped coin on a DB blip.
    empty_ok, _, _ = read_quarantine(lambda k: (True, None), "b")
    failed_ok, _, _ = read_quarantine(lambda k: (False, None), "b", tries=1)
    assert empty_ok != failed_ok, "empty and unreadable must not be the same"
    print("lighter_funding_bot _selftest_quarantine OK")


def _selftest_conviction():
    """[2026-07-24 Lever 2] conviction_mult is DARK by default and BOUNDED. Each
    assertion fails against a naive implementation (unbounded, sizes-down in
    scaled, or not off-by-default) — a revert cannot pass silently."""
    M = sys.modules[__name__]      # the globals conviction_mult actually reads
    save = (M.CONVICTION_MODE, M.CONVICTION_LO, M.CONVICTION_HI, M.CONVICTION_REF)
    try:
        M.CONVICTION_MODE = "off"                       # DARK: every clip == order_usd
        assert M.conviction_mult(0.30) == 1.0 and M.conviction_mult(0.01) == 1.0
        assert M.conviction_mult(None) == 1.0, "bad input is a no-op, never a crash"
        M.CONVICTION_MODE, M.CONVICTION_LO, M.CONVICTION_HI, M.CONVICTION_REF = \
            "scaled", 1.0, 2.2, 0.105
        assert M.conviction_mult(0.02) == 1.0, "scaled FLOORS at 1.0 — never sizes down"
        assert abs(M.conviction_mult(0.21) - 2.0) < 1e-9, "2x ref -> 2.0x"
        assert M.conviction_mult(9.99) == 2.2, "far above ref -> CAPPED, never unbounded"
        assert M.conviction_mult(-0.30) == M.conviction_mult(0.30), "keys on |apr| (sign-free)"
        M.CONVICTION_MODE, M.CONVICTION_LO, M.CONVICTION_HI = "realloc", 0.6, 1.6
        assert M.conviction_mult(0.02) == 0.6, "realloc may size DOWN to LO"
        assert M.conviction_mult(9.99) == 1.6, "realloc still capped at HI"
        M.CONVICTION_REF = 0.0
        assert M.conviction_mult(0.30) == 1.0, "REF<=0 guard -> no-op (no div-by-zero)"
    finally:
        (M.CONVICTION_MODE, M.CONVICTION_LO, M.CONVICTION_HI, M.CONVICTION_REF) = save
    print("lighter_funding_bot _selftest_conviction OK")


def _selftest_explore():
    """[2026-07-24 Lever 1] the explore bucket: coverage-samples K coins from
    BELOW the exploit cut, tags src, and returns them FIRST; K=0 is byte-identical
    to the pre-Lever exploit-only list. Stubs only the fetch layer (the vetoes are
    pinned by the scanner's own history) to isolate the SELECTION under test."""
    M = sys.modules[__name__]
    save_fns = (M._candle_features, M.book_metrics, M.cross_venue_mult)
    save_cfg = (M.SCAN_EXPLORE_K, M.SCAN_DEEP_MAX, M.SCAN_BOOK_PROBE)
    try:
        M._candle_features = lambda ctx, coin: {"ret_mom": 0.0, "vol": 0.001}
        M.book_metrics = lambda ctx, coin, ou: {
            "spread_bps": 5.0, "sell_slip": 2.0, "buy_slip": 2.0,
            "bid_depth": 1000.0, "ask_depth": 1000.0, "mid": 100.0}
        M.cross_venue_mult = lambda f: 1.0
        M.SCAN_DEEP_MAX, M.SCAN_BOOK_PROBE = 15, 8
        # 20 coins, |apr| strictly descending: C00 hottest ... C19 coolest.
        prelim = [(f"C{i:02d}", {"rate": 0.0}, 0.30 - i * 0.01) for i in range(20)]
        lg = logging.getLogger("selftest-explore")
        tail = {f"C{i:02d}" for i in range(15, 20)}     # the below-cut names

        M.SCAN_EXPLORE_K = 0                             # DARK -> exploit-only
        r0 = scan_candidates(None, list(prelim), 25.0, lg, {})
        assert r0 and all(ev["src"] == "exploit" for *_, ev in r0), "K=0 must be all-exploit"
        assert all(c not in tail for c, *_ in r0), "K=0 must never surface a below-cut coin"

        M.SCAN_EXPLORE_K = 2                             # ACTIVE, all never-tried
        r = scan_candidates(None, list(prelim), 25.0, lg, {})
        exp = [c for c, f, a, s, bm, ev in r if ev["src"] == "explore"]
        assert exp == ["C15", "C16"], f"2 explore from the tail, hottest first; got {exp}"
        assert r[0][5]["src"] == "explore" and r[1][5]["src"] == "explore", "explore FIRST"
        assert any(ev["src"] == "exploit" for *_, ev in r), "exploit must still follow"

        # COVERAGE: recently-tried C15/C16 -> skipped for never-tried C17/C18
        r2 = scan_candidates(None, list(prelim), 25.0, lg, {"C15": 1e9, "C16": 1e9})
        exp2 = sorted(c for c, f, a, s, bm, ev in r2 if ev["src"] == "explore")
        assert exp2 == ["C17", "C18"], f"coverage must avoid recently-tried; got {exp2}"
    finally:
        (M._candle_features, M.book_metrics, M.cross_venue_mult) = save_fns
        (M.SCAN_EXPLORE_K, M.SCAN_DEEP_MAX, M.SCAN_BOOK_PROBE) = save_cfg
    print("lighter_funding_bot _selftest_explore OK")


def _selftest_lever_consume():
    """[2026-07-25] apply_levers consumes the PROMOTED explore_k + conviction_hi
    on the live arm (dark when no lever); conviction_hi>1 => scaled capped at hi;
    a live lever never leaks onto the no-prefix (paper) arm. Mutation-tested: each
    assertion fails if the consumption is absent, unbounded, or leaks."""
    M = sys.modules[__name__]
    real_tuning = M.tuning

    class _FakeT:
        def __init__(self, d):
            self.d = d
        def get_lever(self, name, default):
            return self.d.get(name, default)

    save = (dict(M._ENV_BARS), M.SCAN_EXPLORE_K, M.CONVICTION_MODE,
            M.CONVICTION_LO, M.CONVICTION_HI)
    try:
        M._ENV_BARS["explore_k"] = 0                      # live env defaults: dark
        M._ENV_BARS["conviction"] = ("off", 1.0, 2.2)
        M.tuning = _FakeT({})                             # 1) no lever -> DARK
        M.apply_levers("lighter_live")
        assert M.SCAN_EXPLORE_K == 0 and M.CONVICTION_MODE == "off", "no lever must be dark"
        M.tuning = _FakeT({"live.funding.explore_k": 2,   # 2) judge promotes both
                           "live.funding.conviction_hi": 2.2})
        moved = M.apply_levers("lighter_live")
        assert M.SCAN_EXPLORE_K == 2, M.SCAN_EXPLORE_K
        assert (M.CONVICTION_MODE, M.CONVICTION_LO, M.CONVICTION_HI) == ("scaled", 1.0, 2.2)
        assert {"live.funding.explore_k", "live.funding.conviction_hi"} <= set(moved)
        M.tuning = _FakeT({"live.funding.conviction_hi": 1.0})   # 3) hi<=1 -> stays OFF
        M.apply_levers("lighter_live")
        assert M.CONVICTION_MODE == "off", "conviction_hi<=1.0 must not enable sizing"
        M.tuning = _FakeT({"live.funding.explore_k": 2})  # 4) no leak onto paper arm
        M.apply_levers("hl_paper")
        assert M.SCAN_EXPLORE_K == 0, "no-prefix arm must ignore live levers"
    finally:
        M.tuning = real_tuning
        env, M.SCAN_EXPLORE_K, M.CONVICTION_MODE, M.CONVICTION_LO, M.CONVICTION_HI = save
        M._ENV_BARS.clear(); M._ENV_BARS.update(env)
    print("lighter_funding_bot _selftest_lever_consume OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest_notional()
        _selftest_fill_read()
        _selftest_flap()
        _selftest_quarantine()
        _selftest_conviction()
        _selftest_explore()
        _selftest_lever_consume()
        sys.exit(0)
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
