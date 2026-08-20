#!/usr/bin/env python3
"""
audit_lever_authority.py — CAN THIS LEVER CHANGE ANYTHING? (2026-07-22)

WHY THIS EXISTS
`fleet_tuning.clamp()` asks whether a value is INSIDE [lo, hi]. Nothing in the
fleet has ever asked whether [lo, hi] can change BEHAVIOUR. Those are different
questions and the gap between them is a whole failure class:

  * `live.funding.enter_apr` and `xp.funding.enter_apr` are bounded
    [0.03125, 0.075] (TRUE apr). Lighter's funding is PINNED: 42.6% of every
    book-observation on the recorded tape sits at exactly 10.512% apr (crypto
    resting) and 34.0% at 3.504% (equity resting). The gate is `abs(apr) >=
    ENTER_GATE` (lighter_funding_bot.py:1367). So across the ENTIRE registered
    range the admitted set moves 93.65% -> 57.26%, and 93% of that movement is
    ONE step at the equity pin. The value that actually separates the venue's
    modal population — 10.512 — is **1.40x above the lever's hi**. The judge
    can run its full 7-day paired promotion and promote a number that cannot
    reach the population it is supposed to select against.
  * The inverse is worse, because it is invisible: `FUNDING_HARD_STOP` and
    `FUNDING_EXIT_APR` have NO lever at all, and between them they carry
    100% of the LIVE book's gross loss (stop 51.1%, decay+flip 48.9%) and
    59.0% of its closes. The growth rail cannot reach either.

fleet_proprioception grades levers that MOVED. An inert lever produces zero
episodes, so it grades `insufficient` — which reads exactly like a healthy
fleet. That is the convergent-metric failure the sniper's `watching: 201`
taught us: a metric that reads healthy under total failure of its mechanism is
not a health check. Hence a guard, not another organ.

WHAT IT CHECKS
  A. AUTHORITY (per registered lever). Compare [lo, hi] against the MEASURED
     empirical distribution of the quantity the lever gates — Lighter's own
     recorded tape (`bot_state_history['lighter-market']`) and the fleet's own
     ledgers (`paper_trades`). Verdict ladder in `verdict()`.
  B. CONSUMER (per registered lever). A lever no shipped file reads is inert
     however good its bounds are.
  C. COVERAGE (per book module). Census every module-level env knob, subtract
     the ones an organ can actually move, and flag a knob that is DECISIVE —
     it names an exit reason in KNOB_ROLES — with no lever and no declaration.

DECLARING INTENT — the BORN_DARK_OK / VENUE_PURITY_OK pattern.
LEVER_AUTHORITY_OK is keyed `lever:<name>` and `knob:<file>:<NAME>`, and a
reason must say WHY the omission is correct, not restate it. Two forms of
"correct" appear here and they are not the same thing:
  * this lever's quantity CANNOT be measured (and why the obvious measurement
    would be circular) — e.g. take-profit bars, whose only recorded quantity
    is realised P&L, which is censored AT the bar;
  * this knob is DELIBERATELY operator-only — e.g. SafetyRails caps.

WHAT IT DELIBERATELY DOES NOT CHECK
  * Whether the lever's value is GOOD. That is fleet_proprioception's job
    (out-of-sample $ counterfactual) and this guard must not duplicate it.
    This one asks only whether the bound can express any change at all.
  * Whether the RUNNING container holds the env defaults this file reads out
    of source. It does not — see [[self-describing-labels-lie]]. Every knob
    value here is the CODE DEFAULT and is printed as such.
  * The live env. It never touches Railway, never writes, never trades.
  * PER-ARM reachability. Detector C is MODULE-level: a knob wired to
    `get_lever` reads as levered even on an arm that never calls it. The known
    instance is the Ticket Taker, whose `apply_tuning()` returns `{}` on
    `TT_VENUE == "lighter_live"` (lighter_ticket_taker.py:287) — so all eight
    `taker.*` bars are unreachable on the REAL-MONEY arm while this guard sees
    them as covered. That is a deliberate doctrine call by that bot (a
    shadow-replay-gated author must not write a live lane), not a defect this
    guard should re-litigate; it is named here so nobody reads a green line as
    "the live taker is tunable". Making it detectable needs venue-conditional
    analysis, which is a bigger and separate control.

MEASURED, NOT INFERRED — and the CI copy is offline.
The distributions in EVIDENCE were produced by `--measure`, which reads the
recorded Lighter tape and the ledgers read-only. `--measure` prints a
paste-ready EVIDENCE block and CHANGES NOTHING. The default run is pure
stdlib, offline, CI-safe like its siblings (audit_venue_purity /
audit_image_imports / audit_deploy_coverage / audit_sdk_pin). Evidence carries
its own `measured_utc`, `n` and `source`; evidence older than
EVIDENCE_MAX_AGE_D stops counting as evidence (a funding distribution from
three months ago is a hypothesis about today).

USAGE
    python3 scripts/audit_lever_authority.py             # audit; exit 1 on findings
    python3 scripts/audit_lever_authority.py --all       # show OK/declared too
    python3 scripts/audit_lever_authority.py --selftest
    python3 scripts/audit_lever_authority.py --measure --dsn <ro-url>

-----------------------------------------------------------------------------
REAL OUTPUT — `python3 scripts/audit_lever_authority.py`, measured 2026-07-22
20:27 Sydney (AEST +10) against 2362 recorded tape snapshots and the live
ledgers. This is the actual run, not a sample. exit 1.

  FINDINGS:
    live.funding.enter_apr    [0.03125, 0.075]   INERT-PINNED
        93% of the swing is ONE step, ending at 4.4, and the modal population
        (10.5, 42.6% of observations) lies OUTSIDE the bound — the decisive
        value is at 10.5, 1.4x the lever's hi
    xp.funding.enter_apr      [0.03125, 0.075]   INERT-PINNED   (same)
    taker.sl_cooldown_h       [0.0, 24.0]        DARK
        n=11 < 30: cannot tell a pin from noise
    lighter_funding_bot.py:EXIT_APR              UNLEVERED
        decides *_decay/*_flip — 36.2% of $20.34 gross loss, 67.3% of 104
        closes, n=70;  LIVE arm: 48.9% of $7.83, 66.7% of 39 closes, n=26
    lighter_funding_bot.py:HARD_STOP             UNLEVERED
        decides *_stop — 59.5% of $20.34 gross loss, 7.7% of 104 closes, n=8;
        LIVE arm: 51.1% of $7.83, 5.1% of 39 closes, n=2
  WARNINGS (COARSE — reported, not fatal): live.funding.max_hold_h,
    xp.funding.max_hold_h, taker.max_hold_h, taker.brk_range, taker.dip_range
  audit_lever_authority: 5 FINDING(s), 0 stale declaration(s), 5 warning(s);
  19 declared exception(s), 74 OK.

[2026-08-06 I12 — THE COUNT ABOVE IS 22-JUL HISTORY AND THE LIVE RUN NOW READS
27. Recorded here because the delta reads like a regression and is not.] The
registry grew ~32 -> 56 levers ((fz)'s lighter-books lane, (eu)'s receipt
levers, (it)'s carry.min_vol, (jw)'s seven barnes.*) while EVIDENCE still holds
only the 22-Jul --measure snapshot, and live/xp.funding.enter_apr's evidence was
deliberately DELETED at the A1 cage widening. So the growth is MEASUREMENT DEBT,
not guard rot: the mechanics are green (selftest passes, 0 stale declarations),
and 7 of the findings that were dangling-by-retirement (trend.*, disloc.*) are
declared as of today.

READ THIS BEFORE "FIXING" IT: --measure alone cannot clear most of what remains.
A lever reads UNMEASURED when its QUANTITIES spec OR its EVIDENCE is missing,
and the levers on the lighter-books lane have no QUANTITIES entry at all, so
--measure has nothing to profile for them. The upkeep is: write the specs, THEN
re-measure. The two founding findings (EXIT_APR, HARD_STOP — both on the LIVE
Farmer, both still unlevered) are the ones that were always real.

AND THE REASON THIS MATTERS RATHER THAN BEING TIDINESS: this guard is
CI-informational (tests/test_selftests.py runs only its --selftest), so a
saturated bare run is how a genuinely inert new cage arrives invisibly — the
convergent-metric failure this file's own header warns about, turned inward.

The funding pair's arithmetic in full, on the tape's own 1-decimal grid:
    A(>=3.125) = 93.65%   <- lever lo
    A(>=3.5)   = 93.65%   <- the equity pin 3.504 is STILL admitted here
    A(>=4.4)   = 59.66%   <- 34.0pp in ONE step: 93% of the entire swing
    A(>=7.5)   = 57.26%   <- lever hi: 2.4pp over the remaining 70% of width
    A(>=10.6)  = 12.84%   <- past the CRYPTO pin, 42.6% of the venue, at 1.4x hi

-----------------------------------------------------------------------------
HONEST CORRECTION TO THE BRIEF THIS WAS BUILT FROM. The brief said the funding
pair is INERT "vs a first selecting value of 0.1052". Measured, the bound is
not flat — it moves the admitted set 36.4pp. It is inert in the sense that
MATTERS (it cannot separate the venue's modal population, and the value that
can is outside it), and this guard says so with the number rather than
inheriting the word: verdict INERT-PINNED, `cliff_ratio 1.40`. Same class,
measured. See [[unmeasured-assumptions-make-false-verdicts]].

Read-only. Touches no bot, no DB (except read-only under --measure), no venue.
"""
from __future__ import annotations

import ast
import bisect
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# THRESHOLDS — every one of these is a MEASURED cut, and the measurement that
# fixes it is named. A threshold nobody can trace is a threshold nobody can
# defend.
# ---------------------------------------------------------------------------
# STEP_SHARE_BAR: on the 2360-snapshot tape the five levers with a measurable
# gated quantity score, in order: momo 0.01, div 0.01, brk 0.19, dip 0.26,
# funding 0.93. 0.50 sits inside the EMPTY measured gap between 0.26 and 0.93.
# It is honest today on five levers and eight days; re-derive it when the
# registry grows (see RISKS in the header of the report).
STEP_SHARE_BAR = 0.50
# FLAT_SWING_PP: below this the bound moves nothing worth naming. 5pp is one
# tenth of the swing the healthy levers show (38-41pp).
FLAT_SWING_PP = 5.0
# MODE_MASS_BAR: "the venue's modal population". Lighter's two resting pins
# hold 42.6% and 34.0%; the largest non-pin mode on any measured quantity is
# 31.2% (breakout range_pos == 1.0, a real cluster, not a pin).
MODE_MASS_BAR = 0.25
SATURATED_BAR = 0.90        # cannot restrict anywhere in bound
COARSE_R = 10               # distinct reachable admitted-sets across the bound
DEAD_ZONE_BAR = 0.50        # fraction of the bound's WIDTH with no observation
# n floors. TAPE quantities are population observations (hundreds of thousands
# available); LEDGER quantities are a census of a book's whole life and are
# small by construction. 200 is where a Wilson interval at p=0.25 has
# half-width < 0.075 — the smallest n that tells "pinned" (>=25% modal mass)
# from "not pinned" (<10%) at 95%.
MIN_N_TAPE = 200
MIN_N_LEDGER = 30
EVIDENCE_MAX_AGE_D = 90     # older than this is not evidence, it is a memory
# UNLEVERED tiers (measured on the live Farmer's own ledger: stop = 51.1% of
# gross loss on n=2; decay+flip = 48.9% on n=23 / 59.0% of closes). 0.25 is
# also structural: with four exit reasons, uniform share IS 0.25, so a knob at
# or above uniform is load-bearing by construction.
KNOB_SHARE_BAR = 0.25
KNOB_MIN_N = 5              # below this, report the ROLE, never the percentage


# ---------------------------------------------------------------------------
# QUANTITIES — what each lever actually gates, and where that quantity is
# RECORDED. `to_q` converts LEVER units into TAPE units; it is the seam the
# 8x funding-basis bug lived in and it is explicit on purpose
# ([[lighter-funding-apr-8x-overstated]]).
# ---------------------------------------------------------------------------
QUANTITIES = {
    "live.funding.enter_apr": {
        "source": "state:lighter-market", "extract": ("map", "funding"),
        "abs": True, "dir": "ge", "to_q": 100.0, "unit": "apr_pct",
        "min_n": MIN_N_TAPE, "precision": 0.1,
        "gate": "lighter_funding_bot.py:1367  abs(apr) >= ENTER_GATE",
        "note": "lever is a TRUE fraction; the tape's funding map is apr_pct"},
    "xp.funding.enter_apr": {
        "source": "state:lighter-market", "extract": ("map", "funding"),
        "abs": True, "dir": "ge", "to_q": 100.0, "unit": "apr_pct",
        "min_n": MIN_N_TAPE, "precision": 0.1,
        "gate": "lighter_funding_bot.py:1367 (shadow twin, same code)",
        "note": "same quantity, same pins — the experiment arm inherits it"},
    "taker.brk_range": {
        "source": "state:lighter-market", "extract": ("ticket", ("breakout", "range_pos")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "range_pos",
        "min_n": MIN_N_TAPE, "precision": 0.01,
        "gate": "lighter_ticket_taker.py:450  range_pos >= BRK_RANGE"},
    "taker.dip_range": {
        "source": "state:lighter-market", "extract": ("ticket", ("dip", "range_pos")),
        "abs": False, "dir": "le", "to_q": 1.0, "unit": "range_pos",
        "min_n": MIN_N_TAPE, "precision": 0.01,
        "gate": "lighter_ticket_taker.py:453  range_pos <= DIP_RANGE"},
    "taker.momo_chg": {
        "source": "state:lighter-market", "extract": ("ticket", ("momentum", "chg_pct")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "day_chg_pct",
        "min_n": MIN_N_TAPE, "precision": 0.01,
        "gate": "lighter_ticket_taker.py:456  chg_pct >= MOMO_CHG"},
    "taker.div_gap_pp": {
        "source": "state:lighter-market", "extract": ("ticket", ("divergence", "gap_pct")),
        "abs": True, "dir": "ge", "to_q": 1.0, "unit": "gap_pp",
        "min_n": MIN_N_TAPE, "precision": 0.1,
        "gate": "lighter_ticket_taker.py:459  abs(gap_pct) >= DIV_GAP_PP"},
    "taker.max_hold_h": {
        "source": "ledger:lighter-ticket-taker-lshadow", "extract": ("hold_h", None),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "hours",
        "min_n": MIN_N_LEDGER, "precision": 0.01, "censor_at": 48.0,
        "gate": "hold hours at close; a cap of x would have cut every hold >= x"},
    "taker.sl_cooldown_h": {
        "source": "ledger:lighter-ticket-taker-lshadow", "extract": ("gap_after", "_sl"),
        "abs": False, "dir": "le", "to_q": 1.0, "unit": "hours",
        "min_n": MIN_N_LEDGER, "precision": 0.01,
        "gate": "hours from an _sl close to the next entry on the same symbol"},
    "live.funding.max_hold_h": {
        "source": "ledger:perps-funding-lighter-lighter", "extract": ("hold_h", None),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "hours",
        "min_n": MIN_N_LEDGER, "precision": 0.01, "censor_at": 72.0,
        "gate": "hold hours at close (LIVE book)"},
    "xp.funding.max_hold_h": {
        "source": "ledger:perps-funding-lighter-lshadow", "extract": ("hold_h", None),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "hours",
        "min_n": MIN_N_LEDGER, "precision": 0.01, "censor_at": 72.0,
        "gate": "hold hours at close (shadow twin)"},
    # ------ [2026-07-30 (eu) §B RECEIPTS] the three formerly-UNMEASURED
    # growth levers, per arm, off the Farmer's new funding-scan-* payloads
    # (scan_receipts: slope ratios recorded for EVERY decision incl. skips,
    # UNCLAMPED conviction scores, per-cycle explore pool size). Entries
    # stay honestly UNMEASURED until the next --measure run accrues n. ----
    # [2026-08-20 (sf)] 🎫 THE BREAKOUT ARM'S TREND EXIT. Both knobs became
    # registered levers today and neither could be PROFILED, because the
    # quantity each cuts lived in memory and died at close. The bot now stamps
    # them (`give_back`, `mae_ret` on the close row) — so these read UNMEASURED
    # until closes accrue under the stamp, which is the honest state, and then
    # become the first thing this guard can say about the exit that binds the
    # taker's best long lens.
    #
    # SCOPED BY REASON SUFFIX, deliberately: the trail bar must be profiled
    # against the give-back distribution of the positions the TREND exit
    # governed, not against every close the book ever made. `_breakoutup` and
    # `_breakout` are the two lenses `bull_exit` routes there; the suffix
    # matches the exit tag, so both trail-closed and hold-closed breakouts
    # count — which is the untruncated distribution the bar cuts through.
    "taker.brk_trail": {
        "source": "ledger:lighter-ticket-taker-lshadow",
        "extract": ("xfield", ("give_back", None)),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "give_back_frac",
        "min_n": MIN_N_LEDGER, "precision": 0.0001,
        "gate": "lighter_ticket_taker.exit_reason — trail iff give-back from "
                "the peak >= this, on the lenses bull_exit routes to the "
                "trend exit",
        "note": "MAXIMUM give-back per position, stamped at close since (sf); "
                "recorded for EVERY trend-exit close, not only trailed ones, "
                "so the distribution is not truncated at the bar"},
    "taker.brk_sl": {
        "source": "ledger:lighter-ticket-taker-lshadow",
        "extract": ("xfield", ("mae_ret", None)),
        "abs": True, "dir": "ge", "to_q": 1.0, "unit": "adverse_frac",
        "min_n": MIN_N_LEDGER, "precision": 0.0001,
        "gate": "lighter_ticket_taker.exit_reason — hard stop iff adverse "
                "excursion reaches this magnitude",
        "note": "MAXIMUM adverse excursion per position, stamped at close "
                "since (sf); abs because the lever is signed and the "
                "excursion is negative"},
    # [2026-08-20 (sf)] 🌾 carry's measured-liquidity bound — the FIRST
    # QUANTITIES spec on the `lighter-books` lane, and it exists because the
    # lever shipped with its own receipts rather than after them. The header
    # above warns that "a saturated bare run is how a genuinely inert new cage
    # arrives invisibly"; a new cage that cannot be profiled would be exactly
    # that. `depth_scan.payback_h` records EVERY probe, admitted and refused,
    # so the distribution the bound cuts is observable rather than truncated
    # at the bound (the emission-truncation trap the Farmer's receipts note).
    "carry.payback_max_h": {
        "source": "state:perps-funding-carry-lshadow",
        "extract": ("list", ("depth_scan", "payback_h")),
        "abs": False, "dir": "le", "to_q": 1.0, "unit": "hours",
        "min_n": MIN_N_TAPE, "precision": 0.01,
        "gate": "funding_carry_bot.depth_admits — admit a sub-floor coin iff "
                "measured payback <= this many hours",
        "note": "recorded for admitted AND refused probes; UNMEASURED until "
                "a --measure run accrues n, which is the honest reading"},
    "live.funding.slope_gate": {
        "source": "state:funding-scan-live", "extract": ("list", ("slope", "ratios")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "slope_ratio",
        "min_n": MIN_N_TAPE, "precision": 0.01,
        "gate": "lighter_funding_bot.py entry_admission — skip iff ratio < 1 "
                "while the gate is 1",
        "note": "a 0/1 lever mapped onto the ratio distribution: threshold 0 "
                "= admit-all (gate off), threshold 1 = the real bar; recorded "
                "for admitted AND skipped candidates (no emission truncation)"},
    "xp.funding.slope_gate": {
        "source": "state:funding-scan-shadow", "extract": ("list", ("slope", "ratios")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "slope_ratio",
        "min_n": MIN_N_TAPE, "precision": 0.01,
        "gate": "shadow twin, same code",
        "note": "see live.funding.slope_gate"},
    "live.funding.conviction_hi": {
        "source": "state:funding-scan-live", "extract": ("list", ("conviction", "raws")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "conv_raw",
        "min_n": MIN_N_LEDGER, "precision": 0.01,
        "gate": "lighter_funding_bot.py conviction_mult — clip x min(hi, raw)",
        "note": "the UNCLAMPED score per admitted entry: admitted-share at hi "
                "= share of entries where the cap BINDS. The clamped mult is "
                "censored at the bar (the taker.tp class) and is deliberately "
                "not the recorded quantity. One value per entry, so n accrues "
                "at ledger pace — MIN_N_LEDGER"},
    "xp.funding.conviction_hi": {
        "source": "state:funding-scan-shadow", "extract": ("list", ("conviction", "raws")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "conv_raw",
        "min_n": MIN_N_LEDGER, "precision": 0.01,
        "gate": "shadow twin, same code",
        "note": "see live.funding.conviction_hi"},
    "live.funding.explore_k": {
        "source": "state:funding-scan-live", "extract": ("field", ("explore", "pool_n")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "pool_n",
        "min_n": MIN_N_TAPE, "precision": 1.0,
        "gate": "explore reservation fills from the pool — opens/cycle <= "
                "min(k, pool_n)",
        "note": "per-cycle explore-eligible candidate count: admitted-share "
                "at k = share of cycles where the FULL reservation is usable; "
                "a mode at 0 is the explore-zero diagnosis as a standing "
                "measurement. [2026-07-30 (fd)] The Farmer publishes pool_n "
                "ONLY while the pool is live (explore on AND a floor below "
                "MIN_VOL); with explore off it publishes explore.off instead, "
                "so this reads n=0 -> DARK rather than scoring the lever "
                "against a constant 0 — which the ladder would have seen as "
                "full swing, i.e. spurious authority on a switched-off lever"},
    "xp.funding.explore_k": {
        "source": "state:funding-scan-shadow", "extract": ("field", ("explore", "pool_n")),
        "abs": False, "dir": "ge", "to_q": 1.0, "unit": "pool_n",
        "min_n": MIN_N_TAPE, "precision": 1.0,
        "gate": "shadow twin, same code (the arm the growth A/B runs on)",
        "note": "see live.funding.explore_k"},
}


def _extract_state(payload, kind, arg):
    """Per-payload quantity extraction for `state:` sources, pure — split
    out of _measure so the extract kinds are selftestable offline.

    kinds: 'map'    -> payload[arg] is {sym: value}          (one per sym)
           'ticket' -> payload['tickets'][lens][field]       (one per ticket)
           'list'   -> payload[section][field] is [values]   ((eu) receipts)
           'field'  -> payload[section][field] is one value  ((eu) receipts)
    Junk values are skipped, never raised — a malformed payload thins the
    sample, it does not kill the census."""
    vals = []
    if kind == "map":
        for v in ((payload or {}).get(arg) or {}).values():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    elif kind == "ticket":
        lens, field = arg
        for t in ((payload or {}).get("tickets") or {}).get(lens) or []:
            v = t.get(field)
            if v is None:
                continue
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    elif kind == "list":
        sec, field = arg
        for v in (((payload or {}).get(sec) or {}).get(field) or []):
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    elif kind == "field":
        sec, field = arg
        v = ((payload or {}).get(sec) or {}).get(field)
        if v is not None:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    return vals


# ---------------------------------------------------------------------------
# EVIDENCE — produced by `--measure`. Each entry is the OUTPUT of profile()
# over the raw sample, plus its provenance. Regenerate with:
#   python3 scripts/audit_lever_authority.py --measure --dsn <read-only-url>
# ---------------------------------------------------------------------------
EVIDENCE = {
  # [2026-07-30 A1] live/xp.funding.enter_apr EVIDENCE DELETED, deliberately:
  # profile stats are computed AGAINST the registry bounds at measure time,
  # and the operator-signed widening (hi 0.075 -> 0.12) made the stored
  # entries bounds-stale — their INERT-PINNED verdict ("the modal population
  # lies OUTSIDE the bound") became false prose the moment the cage moved.
  # verdict() trusts stored stats and cannot know, so the honest state is
  # UNMEASURED ("no recorded quantity binding") until the next --measure
  # re-profiles the same lighter-market tape against the NEW bounds.
  "live.funding.max_hold_h": {"measured_utc": "2026-07-22T10:27:20Z", "n": 39, "n_groups": 1,
    "source": "ledger:perps-funding-lighter-lighter", "unit": "hours",
    "a_lo": 0.307692, "a_hi": 0.0, "swing_pp": 30.7692, "r": 13,
    "step_share": 0.0833, "step_at": 30.294143, "dead_zone": 0.9796,
    "mode": 2.67, "mode_mass": 0.051282, "sep": False, "cliff_x": 2.67,
    "cliff_drop": 0.051282, "cliff_ratio": 0.0278, "sup_min": 0.417738,
    "sup_max": 70.278195, "censored": False},
  "taker.brk_range": {"measured_utc": "2026-07-22T10:27:20Z", "n": 10764, "n_groups": 2362,
    "source": "state:lighter-market", "unit": "range_pos", "a_lo": 1.0,
    "a_hi": 0.586585, "swing_pp": 41.3415, "r": 8, "step_share": 0.191,
    "step_at": 0.97, "dead_zone": 1.0, "mode": 1.0, "mode_mass": 0.312337,
    "sep": False, "cliff_x": 1.0, "cliff_drop": 0.312337,
    "cliff_ratio": 1.0309, "sup_min": 0.9, "sup_max": 1.27, "censored": False},
  "taker.dip_range": {"measured_utc": "2026-07-22T10:27:20Z", "n": 7639, "n_groups": 2362,
    "source": "state:lighter-market", "unit": "range_pos", "a_lo": 0.739495,
    "a_hi": 1.0, "swing_pp": 26.0505, "r": 11, "step_share": 0.2633,
    "step_at": 0.06, "dead_zone": 1.0, "mode": 0.0, "mode_mass": 0.325043,
    "sep": False, "cliff_x": 0.0, "cliff_drop": 0.325043, "cliff_ratio": 0.0,
    "sup_min": -0.54, "sup_max": 0.15, "censored": False},
  "taker.div_gap_pp": {"measured_utc": "2026-07-22T10:27:20Z", "n": 12559, "n_groups": 2362,
    "source": "state:lighter-market", "unit": "gap_pp", "a_lo": 0.981448,
    "a_hi": 0.600764, "swing_pp": 38.0683, "r": 500, "step_share": 0.0086,
    "step_at": 49.6, "dead_zone": 0.0, "mode": 49.5, "mode_mass": 0.003265,
    "sep": True, "cliff_x": 49.5, "cliff_drop": 0.003265,
    "cliff_ratio": 0.5657, "sup_min": 30.0, "sup_max": 35040.0,
    "censored": False},
  "taker.max_hold_h": {"measured_utc": "2026-07-22T10:27:20Z", "n": 100, "n_groups": 1,
    "source": "ledger:lighter-ticket-taker-lshadow", "unit": "hours",
    "a_lo": 0.22, "a_hi": 0.0, "swing_pp": 22.0, "r": 22, "step_share": 0.0909,
    "step_at": 25.55, "dead_zone": 0.9847, "mode": 0.08, "mode_mass": 0.4,
    "sep": False, "cliff_x": 0.08, "cliff_drop": 0.4, "cliff_ratio": 0.0011,
    "sup_min": 0.083611, "sup_max": 48.090556, "censored": True},
  "taker.momo_chg": {"measured_utc": "2026-07-22T10:27:20Z", "n": 7413, "n_groups": 2362,
    "source": "state:lighter-market", "unit": "day_chg_pct", "a_lo": 1.0,
    "a_hi": 0.586267, "swing_pp": 41.3733, "r": 301, "step_share": 0.0095,
    "step_at": 3.09, "dead_zone": 0.0, "mode": 3.08, "mode_mass": 0.003912,
    "sep": True, "cliff_x": 3.08, "cliff_drop": 0.003912,
    "cliff_ratio": 0.5133, "sup_min": 3.0, "sup_max": 25.69, "censored": False},
  "taker.sl_cooldown_h": {"measured_utc": "2026-07-22T10:27:20Z", "n": 11, "n_groups": 1,
    "source": "ledger:lighter-ticket-taker-lshadow", "unit": "hours",
    "a_lo": 0.0, "a_hi": 0.818182, "swing_pp": 81.8182, "r": 10,
    "step_share": 0.1111, "step_at": 3.434722, "dead_zone": 0.993,
    "mode": 0.34, "mode_mass": 0.090909, "sep": True, "cliff_x": 0.34,
    "cliff_drop": 0.090909, "cliff_ratio": 0.0142, "sup_min": 0.335278,
    "sup_max": 63.3875, "censored": False},
  # (xp.funding.enter_apr deleted with its live twin — see the A1 note above)
  "xp.funding.max_hold_h": {"measured_utc": "2026-07-22T10:27:20Z", "n": 65, "n_groups": 1,
    "source": "ledger:perps-funding-lighter-lshadow", "unit": "hours",
    "a_lo": 0.230769, "a_hi": 0.0, "swing_pp": 23.0769, "r": 16,
    "step_share": 0.0667, "step_at": 35.34392, "dead_zone": 0.9687,
    "mode": 1.33, "mode_mass": 0.046154, "sep": False, "cliff_x": 1.33,
    "cliff_drop": 0.046154, "cliff_ratio": 0.0139, "sup_min": 0.25012,
    "sup_max": 72.052313, "censored": True},
}

# ---------------------------------------------------------------------------
# DECLARED EXCEPTIONS. Keys: `lever:<name>` / `knob:<file>:<NAME>`.
# A reason must say WHY the omission is correct, not restate it.
# ---------------------------------------------------------------------------
LEVER_AUTHORITY_OK = {
    # --- [2026-08-03 (iv)] the fleet budgets: the gated quantity has NEVER
    # BEEN OBSERVED, because the bound has never bound ------------------------
    "lever:risk.long_budget": (
        "UNMEASURABLE TODAY, and for a reason that is itself the measurement: "
        "the quantity this bound gates is 'the fleet-wide long count at which "
        "the veto starts refusing entries', and THE VETO HAS NEVER FIRED at "
        "20. Measured 3-Aug: longs 11/20, and the highest reading in the "
        "reviewed window is well inside it. There is no recorded episode of "
        "the budget binding, so there is no empirical distribution to "
        "calibrate [20, 40] against — and manufacturing one from the CURRENT "
        "long count would be circular, since that count is itself produced by "
        "books the veto never restrained. "
        "The cage is DERIVED rather than fitted: lo == the operator's value "
        "(the rail may only widen, never tighten the fleet's risk budget) and "
        "hi == 2x, which is the point at which `long_effective_n` (11.8 "
        "effective bets from 15 positions today) would need re-deriving "
        "anyway. This becomes measurable the first time the veto refuses a "
        "long — `fleet_bus.long_entries_blocked` is the event to record — and "
        "that is a real review item, not a reason to assert authority now."),
    "lever:risk.short_budget": (
        "UNMEASURABLE TODAY, same mechanism as `risk.long_budget` above and "
        "more so: shorts read 2/12 on 3-Aug, so the short budget is even "
        "further from binding than the long one. Declared separately rather "
        "than folded in, because the two cohorts are counted by different "
        "code paths and a single declaration would hide a divergence between "
        "them."),
    # --- levers whose gated quantity is NOT RECORDED, and the obvious
    # substitute would be CIRCULAR --------------------------------------------
    "lever:taker.tp": (
        "UNMEASURABLE, and the obvious measurement is circular. A take-profit "
        "bar gates the position's MAXIMUM FAVOURABLE EXCURSION, which this "
        "fleet does not record anywhere. The only recorded quantity is "
        "realised pnl_pct — which is CENSORED AT THE BAR (a trade closed by tp "
        "realises exactly +tp), so an empirical CDF of it says the bound has "
        "enormous authority no matter what the market did. That is a false "
        "PASS, the dangerous direction. Wiring excursion telemetry is a real "
        "review item; asserting authority off censored data is not."),
    "lever:taker.sl": (
        "Same censoring as taker.tp, mirrored: an sl close realises exactly "
        "-sl, so realised P&L cannot say whether a different bar would have "
        "bitten. Note the shape is NOT symmetric in consequence — a wrongly "
        "wide sl shows up as realised loss, so fleet_proprioception's $ "
        "counterfactual on the taker lane is the control that does cover it."),
    "lever:xp.funding.take_profit": (
        "Same censoring as taker.tp, on the funding experiment arm: the only "
        "recorded quantity is realised pnl_pct and a *_take_profit close "
        "realises exactly +tp, so the CDF is a picture of the bar, not of the "
        "market it is supposed to select against."),
    "lever:live.funding.take_profit": (
        "Same censoring as taker.tp, on the LIVE funding book — and note the "
        "measured shape corroborates the refusal: all 24 *_take_profit closes "
        "across both funding arms carry exactly $0.00 of gross loss, which is "
        "what censoring at the bar looks like, not evidence of a good bar."),
    # NOTE (2026-07-23, RESOLVED 2026-07-30): live/xp.funding.enter_apr's
    # INERT-PINNED finding was deliberately left open here and doubled as the
    # selftest's INERT/stale fixtures — until the operator signed the A1
    # widening (hi 0.075 -> 0.12, spanning the venue's modal 10.5). The
    # bounds-stale evidence is deleted (see the EVIDENCE note), the fixtures
    # re-anchored, and the pair reads UNMEASURED pending the next --measure.
    # The 23-Jul context stands as history: widening the ENV GATE up was
    # measured to lose (FUNDING_GATE_LIGHTER_2026-07-23.md) — but that
    # measured the naive gate, not the judge's paired-bar candidates, which
    # is exactly what the widened CAGE now lets the judge test (an
    # "enter only above modal" candidate was structurally unaskable before).
    "lever:scout.brk_range_min": (
        "EMISSION-TRUNCATED, so measuring it against the tape would be "
        "measuring this lever against its own current value. The scout only "
        "PUBLISHES tickets that already cleared its bar, so the recorded "
        "population is censored at the default (0.90) and every value in "
        "[0.80, 0.90] admits an identical 100%. That reads INERT and it is an "
        "artifact. The honest measurement needs the pre-emission candidate set, "
        "which is not published. Same for all four scout diet levers."),
    "lever:scout.dip_range_max": (
        "Emission-truncated — see scout.brk_range_min. Measured: every dip "
        "ticket on the recorded tape has range_pos <= 0.15 because the scout "
        "only publishes what already cleared its own bar."),
    "lever:scout.momo_chg_min": (
        "Emission-truncated — see scout.brk_range_min. Measured: the momentum "
        "tickets' chg_pct support starts at exactly 3.00, the current bar."),
    "lever:scout.div_gap_pp": (
        "Emission-truncated — see scout.brk_range_min. Its bound reaches down "
        "to 20.0 while the recorded support starts at 30.0, so the bottom "
        "third of the bound has never been observed at all."),
    "lever:scout.ticket_top_n": (
        "Emission-truncated in the same way and worse: the tape records the "
        "top-N list, never the length of the candidate list it was cut from, "
        "so the quantity this lever gates has literally never been observed."),
    "lever:live.clip_scale": (
        "NOT A THRESHOLD LEVER — it multiplies clip size, so there is no gated "
        "population and no admitted set to compare. Its authority is already "
        "measured, out-of-sample and in dollars, by fleet_proprioception's "
        "live-lane episodes; re-deriving it here would duplicate that organ "
        "and give the operator two numbers to reconcile."),
    "lever:live.avo.clip_scale": (
        "Same shape as live.clip_scale above and declared for the same reason: "
        "a multiplier, not a threshold, so it gates no population. [2026-08-16 "
        "(nj)] It exists because 🙏 Avo took the live slot on 13-Aug and was "
        "being sized by 💸 the Farmer's evidence through ONE shared dial; each "
        "live book now carries its own arm. Note this one is RESTRICT-ONLY at "
        "the consumer (clamped to <=1.0, cage hi 1.0 to match), so its whole "
        "reachable range shrinks the book — there is no expansion authority "
        "here for a measurement to vouch for."),
    # --- levers whose CONSUMER is retired -------------------------------------
    # [2026-08-06] 🌊 Tide Rider (retired 1-Aug (if): 9 buys / ZERO sells in 22
    # days) and 🧲 Snap Back (retired 4-Aug (jh): t=-2.97, n=175, the fleet's
    # only statistically significant loser) are the gapscout shape exactly —
    # both modules still ship and still contain their apply_tuning() calls,
    # they merely idle at boot behind TIDE_RIDER_RETIRED_OVERRIDE /
    # SNAPBACK_RETIRED_OVERRIDE, so the static consumer scan finds a consumer
    # that will never run. Their gated quantities stopped being produced at
    # retirement and cannot accrue again unless a book is resurrected.
    #
    # WHY DECLARED AND NOT DELETED, against the gapscout note's own advice:
    # both retirements are deliberately REVERSIBLE by env var, and deleting
    # the registry entries would mean a resurrected book comes back with NO
    # growth-rail reach at all — re-creating the I18 defect ("a book whose
    # only tunable knobs are the ones with room LOOKS tunable and cannot
    # move") as the price of tidying a report. The cost of keeping them is one
    # declared line each; the cost of deleting them is paid by whoever
    # resurrects the book and cannot work out why the rail ignores it.
    "lever:trend.universe_n": (
        "Dangling by retirement — 🌊 Tide Rider, retired 1-Aug (if). Reversible "
        "via TIDE_RIDER_RETIRED_OVERRIDE=run; see the block note above on why "
        "the entry is kept rather than deleted."),
    "lever:trend.max_open": (
        "Dangling by retirement — 🌊 Tide Rider (if). Note its cage hi was set "
        "to 9 as a SAFETY bound by (hl) (at >=10 the -10% daily-loss halt "
        "becomes reachable before the -35% stop), so this entry also records a "
        "safety finding that must survive any resurrection."),
    "lever:trend.min_vol_m": (
        "Dangling by retirement — 🌊 Tide Rider (if). Its 5.0 -> 3.0 move was "
        "measured (ZEC+PAXG carried 91% of the delta; 2.0 lowered the mean), so "
        "the bound is evidence-backed and worth preserving for a resurrection."),
    "lever:trend.rank_by_funding": (
        "Dangling by retirement — 🌊 Tide Rider (if), and INERT even before it: "
        "measured max simultaneously-golden coins = 1 against 6 slots, so the "
        "ranking never bound while the book ran."),
    "lever:disloc.enter_pct": (
        "Dangling by retirement — 🧲 Snap Back, retired 4-Aug (jh). Reversible "
        "via SNAPBACK_RETIRED_OVERRIDE=run. Its real binding gate was never "
        "this lever but the unregistered ENTER_FLOOR_MULT literal — the I18 "
        "finding that helped justify the retirement, recorded here so it is not "
        "re-learned."),
    "lever:disloc.universe_n": (
        "Dangling by retirement — 🧲 Snap Back, retired 4-Aug (jh). It widened "
        "the ranked universe 16 -> 40 off fleet_bus.scout_universe; that feed "
        "still publishes, but the book that consumed it idles at boot, so the "
        "admitted-set distribution this bound gates stopped being produced on "
        "the day of the retirement."),
    "lever:disloc.exit_bps": (
        "Dangling by retirement — 🧲 Snap Back (jh). This was the fleet's FIRST "
        "exit lever ((gu)) and its cage [8.0, 40.0] was derived from the live "
        "residual distribution (median 7.9bps, p90 21.8), so the entry carries a "
        "measurement that would have to be re-made from scratch."),
    "lever:gapscout.prefilter_gap": (
        "DANGLING BY RETIREMENT, declared because the automatic consumer scan "
        "CANNOT see it: Gap Scout was retired 17-Jul under LIGHTER-ONLY, but "
        "cross_exchange_arb.py is still shipped and still contains the "
        "get_lever call — it merely idles at boot behind the guard. So the "
        "static scan finds a consumer that will never run. The lane "
        "(paper-scanner) has no live consumer at all and `gapscout-census` is "
        "stale forever. The correct fix is DELETION from LEVERS, not a bounds "
        "change; it is declared here so the fact is recorded rather than "
        "silently passing. Same for the other two gapscout levers."),
    "lever:gapscout.max_book_fetches": (
        "Dangling by retirement — see gapscout.prefilter_gap. Its quantity "
        "(order books pulled per scan) stopped being produced on 17-Jul, so "
        "there is no distribution to compare a bound against and never will "
        "be again unless the bot is resurrected."),
    "lever:gapscout.extra_exchanges": (
        "Dangling by retirement (see gapscout.prefilter_gap) AND categorical: "
        "a csv lever has no ordered bound, so the threshold machinery in this "
        "guard does not apply to it even in principle."),
    # --- levers on an ADVISORY organ nothing trades on -------------------------
    "lever:evsent.min_sources": (
        "The Event Sentinel is ADVISORY with ZERO consumers by design — no "
        "book reads `event-sentinel`, so an inert bound here cannot cost or "
        "make a dollar. It tunes the organ's own detection sensitivity, whose "
        "gated quantity (distinct corroborating headlines per event) is "
        "recorded, but grading it before a consumer exists would rank a knob "
        "nothing consumes above knobs that steer real money."),
    "lever:evsent.severity_bar": (
        "Advisory organ with zero consumers — see evsent.min_sources. THE DAY "
        "A BOOK CONSUMES `event-sentinel`, both evsent declarations must be "
        "deleted and the levers measured: that is the moment a dead bound "
        "starts steering money, and this table is where the next reader will "
        "look for the reason it was ever allowed to sit unmeasured."),
    # NOTE — deliberately NOT declared here: taker.max_hold_h and the two
    # funding max_hold levers. Their hold-hour evidence is CENSORED at each
    # book's current cap, which the audit prints inline. Declaring them would
    # have been tidier and WRONG: a declaration suppresses every future fatal
    # verdict on that lever, so "I wanted to record a caveat" would have
    # bought permanent blindness to a real inertness later. Caveats belong in
    # the output; this table is only for omissions that are CORRECT.

    # --- KNOBS deliberately without a lever ------------------------------------
    "knob:lighter_funding_bot.py:DAILY_LOSS_LIMIT": (
        "OPERATOR-ONLY FOREVER. This is a SafetyRails-class circuit breaker on "
        "a real-money book. The growth rail's own charter puts go-live, keys "
        "and SafetyRails caps outside every autonomous author; a lever that "
        "can widen a daily-loss halt is a lever that can disable it."),
    "knob:lighter_ticket_taker.py:DAILY_LOSS_LIMIT": (
        "Operator-only forever — same SafetyRails-class reasoning, and this "
        "book has a LIVE arm."),
    # [caught by _stale_exceptions() on the first run — I wrote MAX_OPEN, the
    # Farmer's knob is MAX_OPEN_POSITIONS. A declaration naming a knob that
    # does not exist declares nothing and hides nothing; the check that a
    # table's keys are REAL is why it is in the selftest.]
    "knob:lighter_funding_bot.py:MAX_OPEN_POSITIONS": (
        "Operator-only: it is the position-count half of the live notional "
        "cap. venues/safety.py open_notional() is the other half, and the "
        "15-Jul cap breach happened precisely because a growth-rail lever "
        "moved clip size while a count-based estimate stayed still."),
    "knob:lighter_ticket_taker.py:MAX_OPEN": (
        "Operator-only — same position-count-half-of-the-cap reasoning as the "
        "Farmer's MAX_OPEN, and this book has a LIVE arm sharing the signer "
        "and the SafetyRails surface with it."),
}


# ---------------------------------------------------------------------------
# KNOB ROLES — which exit reasons a knob DECIDES. This is the one
# hand-maintained map in this guard and detector C's attribution rests on it,
# so it is kept honest two ways: a knob listed here is DECISIVE-BY-ROLE and
# must be levered or declared regardless of sample size, and every run prints
# the UNATTRIBUTED share of gross loss so a rotting map is visible rather than
# silent (a reason string nobody mapped lands nowhere and would otherwise just
# shrink everyone's percentage).
# ---------------------------------------------------------------------------
KNOB_ROLES = {
    "lighter_funding_bot.py": {
        "HARD_STOP":   ("*_stop",),
        "EXIT_APR":    ("*_decay", "*_flip"),
        "TAKE_PROFIT": ("*_take_profit",),
        "MAX_HOLD_H":  ("*_max_hold",),
    },
    "lighter_ticket_taker.py": {
        "STOP_LOSS":   ("*_sl",),
        "TAKE_PROFIT": ("*_tp",),
        "MAX_HOLD_H":  ("*_hold",),
    },
}

# module -> (bot rows whose ledger attributes to it, minimum knobs the parser
# MUST find). The knob floor is detector C's dark guard: if the module is
# renamed, restructured, or the regex/AST rots, the census finds zero knobs and
# the guard reports "0 unlevered" — a perfect score from a total parse failure.
BOOK_MODULES = {
    "lighter_funding_bot.py": (("perps-funding-lighter-lighter",
                                "perps-funding-lighter-lshadow"), 20),
    "lighter_ticket_taker.py": (("lighter-ticket-taker-lighter",
                                 "lighter-ticket-taker-lshadow"), 15),
    "lighter_dislocation_bot.py": ((), 8),
    "lighter_trend_bot.py": ((), 5),
    "lighter_index_bot.py": ((), 5),
    "lighter_perp_sniper.py": ((), 3),
    "lighter_funding_spread_bot.py": ((), 5),
    "funding_carry_bot.py": ((), 2),
    "lighter_family_bot.py": ((), 3),
}

# Attribution evidence for detector C — also produced by `--measure`.
KNOB_EVIDENCE = {
  "lighter_funding_bot.py": {
    "measured_utc": "2026-07-22T10:27:20Z", "n_closes": 104,
    "gross_loss": 20.3403,
    "reasons": {"long_decay": [2, 0.0261], "long_flip": [2, 0.0], "short_decay": [42, 3.1803], "short_flip": [24, 4.1567], "short_max_hold": [2, 0.8713], "short_stop": [8, 12.1059], "short_take_profit": [24, 0.0]},
    "per_bot": {
      "perps-funding-lighter-lighter": {"n_closes": 39, "gross_loss": 7.8261,
          "reasons": {"long_decay": [1, 0.0], "long_flip": [2, 0.0], "short_decay": [15, 0.4365], "short_flip": [8, 3.3876], "short_stop": [2, 4.002], "short_take_profit": [11, 0.0]}},
      "perps-funding-lighter-lshadow": {"n_closes": 65, "gross_loss": 12.5142,
          "reasons": {"long_decay": [1, 0.0261], "short_decay": [27, 2.7438], "short_flip": [16, 0.7691], "short_max_hold": [2, 0.8713], "short_stop": [6, 8.1039], "short_take_profit": [13, 0.0]}},
    }
  },
  "lighter_ticket_taker.py": {
    "measured_utc": "2026-07-22T10:27:20Z", "n_closes": 105,
    "gross_loss": 41.3311,
    "reasons": {"long-breakout_hold": [1, 0.0], "long-breakout_sl": [2, 2.6781], "long-breakout_tp": [3, 0.0], "long-dip_hold": [2, 1.2461], "long-dip_sl": [1, 1.9724], "long-dip_tp": [1, 0.0227], "long-divergence_hold": [6, 1.5951], "long-divergence_sl": [9, 9.8525], "long-divergence_tp": [6, 0.0], "long-momentum_hold": [2, 0.0219], "short-divergence_hold": [3, 0.0817], "short-divergence_sl": [12, 16.742], "short-divergence_tp": [57, 7.1186]},
    "per_bot": {
      "lighter-ticket-taker-lighter": {"n_closes": 5, "gross_loss": 0.6109,
          "reasons": {"long-divergence_sl": [2, 0.6109], "long-divergence_tp": [1, 0.0], "short-divergence_hold": [1, 0.0], "short-divergence_tp": [1, 0.0]}},
      "lighter-ticket-taker-lshadow": {"n_closes": 100, "gross_loss": 40.7202,
          "reasons": {"long-breakout_hold": [1, 0.0], "long-breakout_sl": [2, 2.6781], "long-breakout_tp": [3, 0.0], "long-dip_hold": [2, 1.2461], "long-dip_sl": [1, 1.9724], "long-dip_tp": [1, 0.0227], "long-divergence_hold": [6, 1.5951], "long-divergence_sl": [7, 9.2416], "long-divergence_tp": [5, 0.0], "long-momentum_hold": [2, 0.0219], "short-divergence_hold": [2, 0.0817], "short-divergence_sl": [12, 16.742], "short-divergence_tp": [56, 7.1186]}},
    }
  },
}

# ---------------------------------------------------------------------------
# A. AUTHORITY — the pure statistics, and the pure ladder.
# ---------------------------------------------------------------------------
def profile(values, lo, hi, direction="ge", precision=None, censor_at=None):
    """Empirical authority of the bound [lo, hi] over `values`, in the units of
    `values` (the caller applies to_q). Pure; no I/O.

    Returns None for an EMPTY sample — never a zeroed stats dict. That
    distinction is the whole point: `swing=0` on an empty sample renders
    identical to a genuinely flat lever, i.e. a DARK sensor scoring a verdict.
    """
    vals = sorted(float(v) for v in values)
    n = len(vals)
    if n == 0:
        return None                       # DARK, not "flat"
    lo, hi = (float(lo), float(hi)) if lo <= hi else (float(hi), float(lo))

    def A(x):
        # admitted fraction at bar x, on the SAMPLE's own grid
        if direction == "ge":
            return (n - bisect.bisect_left(vals, x)) / n
        return bisect.bisect_right(vals, x) / n

    inb = sorted({v for v in vals if lo <= v <= hi})
    grid = [lo] + inb + [hi]
    F = [A(x) for x in grid]
    swing = abs(F[0] - F[-1])
    steps = [abs(F[i + 1] - F[i]) for i in range(len(F) - 1)] or [0.0]
    top = max(steps)
    step_at = grid[steps.index(top) + 1] if len(grid) > 1 else lo
    width = hi - lo
    dead = 0.0
    if width > 0:
        prev = lo
        for v in inb + [hi]:
            g = v - prev
            if g > 0.01 * width:
                dead += g
            prev = v
        dead /= width
    q = precision or 1e-9
    cnt = Counter(round(v / q) * q for v in vals)
    mode, mm = cnt.most_common(1)[0]
    # THE CLIFF over the FULL support: the smallest x at which the admitted set
    # drops hardest. If it lies outside [lo, hi] the lever cannot reach the
    # decision the venue actually makes.
    cliff_x, cliff_drop = lo, 0.0
    for x, c in cnt.items():
        if c / n > cliff_drop:
            cliff_x, cliff_drop = x, c / n
    return {
        "n": n, "a_lo": F[0], "a_hi": F[-1], "swing_pp": round(swing * 100, 4),
        "r": len({round(f, 10) for f in F}),
        "step_share": round(top / swing, 4) if swing > 0 else 1.0,
        "step_at": round(step_at, 6), "dead_zone": round(dead, 4),
        "mode": round(mode, 6), "mode_mass": round(mm / n, 6),
        "sep": bool(lo <= mode <= hi),
        "cliff_x": round(cliff_x, 6), "cliff_drop": round(cliff_drop, 6),
        "cliff_ratio": round(cliff_x / hi, 4) if hi else 0.0,
        "sup_min": round(vals[0], 6), "sup_max": round(vals[-1], 6),
        "censored": bool(censor_at is not None and vals[-1] >= censor_at * 0.999),
    }


def verdict(ev, min_n=MIN_N_TAPE):
    """The ladder. Pure — takes a stats dict, returns (verdict, why).

    First match wins, and DARK is checked FIRST so a thin sample can never
    reach a verdict. [[a-convergent-metric-is-not-a-health-check]]
    """
    if not ev:
        return "DARK", "no observations of the gated quantity"
    n = ev.get("n") or 0
    if n < min_n:
        return "DARK", f"n={n} < {min_n}: cannot tell a pin from noise"
    swing = float(ev.get("swing_pp") or 0.0)
    if swing < FLAT_SWING_PP:
        return "INERT-FLAT", (f"the whole bound admits the same population "
                              f"(swing {swing:.2f}pp < {FLAT_SWING_PP}pp)")
    if float(ev.get("step_share") or 0) >= STEP_SHARE_BAR and not ev.get("sep"):
        return "INERT-PINNED", (
            f"{float(ev['step_share'])*100:.0f}% of the swing is ONE step, "
            f"ending at {ev.get('step_at')}, and the modal population "
            f"({ev.get('mode')}, "
            f"{float(ev.get('mode_mass') or 0)*100:.1f}% of observations) lies "
            f"OUTSIDE the bound — the decisive value is at {ev.get('cliff_x')}, "
            f"{ev.get('cliff_ratio')}x the lever's hi")
    if min(float(ev.get("a_lo") or 0), float(ev.get("a_hi") or 0)) >= SATURATED_BAR:
        return "SATURATED", ("admits >=90% of the population at BOTH ends — "
                             "the bound cannot restrict anywhere")
    if (ev.get("r") or 0) <= COARSE_R or float(ev.get("dead_zone") or 0) >= DEAD_ZONE_BAR:
        return "COARSE", (f"only {ev.get('r')} distinct admitted-sets are "
                          f"reachable across the bound; {float(ev.get('dead_zone') or 0)*100:.0f}% "
                          f"of its width has no observation")
    return "HEALTHY", (f"{ev.get('r')} reachable admitted-sets, swing "
                       f"{swing:.1f}pp, largest step {float(ev['step_share'])*100:.0f}%")


FATAL = {"INERT-FLAT", "INERT-PINNED", "SATURATED", "DARK", "UNMEASURED",
         "NO-CONSUMER"}


def evidence_age_days(ev, now=None):
    """Days since the evidence was measured; None if unstamped/unparseable."""
    import datetime as _dt
    try:
        s = str(ev["measured_utc"]).replace("Z", "+00:00")
        t = _dt.datetime.fromisoformat(s)
        if t.tzinfo is None:
            t = t.replace(tzinfo=_dt.timezone.utc)
        now = now or _dt.datetime.now(_dt.timezone.utc)
        return (now - t).total_seconds() / 86400.0
    except Exception:
        return None


# ---------------------------------------------------------------------------
# B. CONSUMER — does any shipped file read this lever name?
# ---------------------------------------------------------------------------
def _shipped_py():
    out = []
    for base, _dirs, files in os.walk(ROOT):
        rel = os.path.relpath(base, ROOT)
        if rel.split(os.sep)[0] in (".git", ".venv", "scripts", "tests",
                                    "logs", "reports", "node_modules"):
            continue
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(base, f))
    return out


# The file that DEFINES the levers is not a consumer of them. Without this
# exclusion every lever in the registry names itself and NO-CONSUMER could
# never fire — a detector that reads healthy under total failure of the thing
# it detects. (Found by printing the real consumer map: `fleet_tuning.py`
# appeared under all 25 levers.)
NOT_A_CONSUMER = {"fleet_tuning.py"}


def consumers(lever_names, files=None):
    """lever -> [repo-relative files that name it]. A literal-string scan on
    purpose: get_lever's name argument is sometimes assembled (`prefix +
    "enter_apr"`), so an AST call-graph would MISS the funding levers entirely.

    Presence is NECESSARY, NEVER SUFFICIENT, in two directions:
      * a RETIRED module still contains its call (gapscout.* — declared, not
        auto-detected);
      * a mention in a dashboard, an organ that merely REPORTS levers, or an
        audit tool is not consumption either. Only the registry itself is
        excluded mechanically; the rest is why this detector's verdict is
        NO-CONSUMER (a strong, rare claim) and not "consumed, therefore fine".
    """
    files = files if files is not None else _shipped_py()
    hits = {n: [] for n in lever_names}
    for p in files:
        # basename, not relpath: the exclusion must hold wherever the file
        # sits, including under a selftest tmpdir — an exclusion that only
        # works on the real tree cannot be tested on anything else.
        if os.path.basename(p) in NOT_A_CONSUMER:
            continue
        rel = os.path.relpath(p, ROOT)
        try:
            src = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for n in lever_names:
            if n in src:
                hits[n].append(rel)
            else:
                # `prefix + "enter_apr"` — accept the bare suffix ONLY when the
                # dotted prefix appears as its own STRING LITERAL in the same
                # file. Requiring merely "live." somewhere put listing_sniper.py
                # under live.funding.take_profit: a common word plus an
                # unrelated substring is not a call site.
                head, _, tail = n.rpartition(".")
                if tail and head and f'"{tail}"' in src and f'"{head}."' in src:
                    hits[n].append(rel)
    return hits


# ---------------------------------------------------------------------------
# C. COVERAGE — module-level env knobs, and which of them an organ can move.
# ---------------------------------------------------------------------------
def _is_env_call(node):
    """float(os.environ.get(...)) / int(os.getenv(...)) — returns the env name."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ("float", "int")):
        return None
    if not node.args:
        return None
    inner = node.args[0]
    if not isinstance(inner, ast.Call):
        return None
    f = inner.func
    name = None
    if isinstance(f, ast.Attribute) and f.attr in ("get", "getenv"):
        name = f.attr
    if name is None:
        return None
    if inner.args and isinstance(inner.args[0], ast.Constant) \
            and isinstance(inner.args[0].value, str):
        return inner.args[0].value
    return "<dynamic>"


def knob_census(src):
    """{ATTR: (env_var, default_literal)} for module-level numeric env knobs."""
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Name) or not tgt.id.isupper():
            continue
        env = _is_env_call(node.value)
        if env is None:
            continue
        dflt = ""
        try:
            inner = node.value.args[0]
            if len(inner.args) > 1 and isinstance(inner.args[1], ast.Constant):
                dflt = str(inner.args[1].value)
        except Exception:
            dflt = ""
        out[tgt.id] = (env, dflt)
    return out


def levered_attrs(src):
    """Attributes an organ can actually move: the DEFAULT argument of any
    get_lever call, any TUNABLE mapping, and anything transitively assigned
    from a get_lever result (apply_levers does `ea = get_lever(...)` then
    `ENTER_APR = SCAN_ENTER = ea` — a one-hop scan would miss both)."""
    tree = ast.parse(src)
    out, tainted = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "get_lever":
            if len(node.args) > 1 and isinstance(node.args[1], ast.Name):
                out.add(node.args[1].id)
        if isinstance(node, ast.Assign):
            if any(isinstance(c, ast.Call)
                   and getattr(c.func, "attr", None) == "get_lever"
                   for c in ast.walk(node.value)):
                for t in node.targets:
                    for nm in ast.walk(t):
                        if isinstance(nm, ast.Name):
                            tainted.add(nm.id)
        # TUNABLE = (("taker.dip_range", "DIP_RANGE"), ...)
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "TUNABLE" for t in node.targets):
            for c in ast.walk(node.value):
                if isinstance(c, ast.Constant) and isinstance(c.value, str) \
                        and c.value.isupper():
                    out.add(c.value)
    for _ in range(6):                    # fixpoint, bounded
        grew = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) \
                    and node.value.id in tainted:
                for t in node.targets:
                    for nm in ast.walk(t):
                        if isinstance(nm, ast.Name) and nm.id not in tainted:
                            tainted.add(nm.id)
                            grew = True
        if not grew:
            break
    return out | {t for t in tainted if t.isupper()}


def _reason_match(reason, globs):
    for g in globs:
        if re.fullmatch(g.replace("*", ".*"), reason or ""):
            return True
    return False


def attribute(roles, ev):
    """knob -> {n, close_share, loss_share} from a reason census, plus the
    UNATTRIBUTED share. Pure."""
    reasons = (ev or {}).get("reasons") or {}
    n_tot = sum(v[0] for v in reasons.values()) or 0
    gross = sum(v[1] for v in reasons.values()) or 0.0
    out, seen = {}, set()
    for knob, globs in (roles or {}).items():
        n = loss = 0.0
        for r, (cnt, ls) in reasons.items():
            if _reason_match(r, globs):
                n += cnt
                loss += ls
                seen.add(r)
        out[knob] = {"n": int(n),
                     "close_share": (n / n_tot) if n_tot else 0.0,
                     "loss_share": (loss / gross) if gross else 0.0,
                     "loss_usd": round(loss, 4)}
    unattr = sum(v[1] for r, v in reasons.items() if r not in seen)
    return out, ((unattr / gross) if gross else 0.0), gross, n_tot


# ---------------------------------------------------------------------------
# THE AUDIT
# ---------------------------------------------------------------------------
def audit(evidence=None, knob_evidence=None, files=None, now=None):
    """-> (findings, warnings, ok, declared). Pure w.r.t. injected evidence."""
    import fleet_tuning                                   # registry is the input
    evidence = EVIDENCE if evidence is None else evidence
    knob_evidence = KNOB_EVIDENCE if knob_evidence is None else knob_evidence
    findings, warnings, ok, declared = [], [], [], []

    cons = consumers(list(fleet_tuning.LEVERS), files=files)

    for name, spec in sorted(fleet_tuning.LEVERS.items()):
        why_ok = LEVER_AUTHORITY_OK.get("lever:" + name)
        bound = (spec.get("lo"), spec.get("hi"))
        if not cons.get(name):
            row = (name, bound, "NO-CONSUMER",
                   "no shipped file names this lever — nothing can read it")
            (declared if why_ok else findings).append(row + (why_ok,))
            continue
        q = QUANTITIES.get(name)
        ev = evidence.get(name)
        if q is None or ev is None:
            row = (name, bound, "UNMEASURED",
                   "no recorded quantity binding: this guard cannot vouch for it")
            (declared if why_ok else findings).append(row + (why_ok,))
            continue
        age = evidence_age_days(ev, now)
        if age is None or age > EVIDENCE_MAX_AGE_D:
            row = (name, bound, "UNMEASURED",
                   f"evidence is {'unstamped' if age is None else f'{age:.0f}d old'} "
                   f"(> {EVIDENCE_MAX_AGE_D}d) — re-run --measure")
            (declared if why_ok else findings).append(row + (why_ok,))
            continue
        v, why = verdict(ev, min_n=q.get("min_n", MIN_N_TAPE))
        if ev.get("censored"):
            why += (f"  [CENSORED at the book's current cap: values above it "
                    f"cannot be observed, so authority above the cap is a "
                    f"LOWER bound]")
        row = (name, bound, v, why)
        if v in FATAL:
            (declared if why_ok else findings).append(row + (why_ok,))
        elif v == "COARSE":
            warnings.append(row + (why_ok,))
        else:
            ok.append(row + (why_ok,))

    # ---- C. unlevered knobs --------------------------------------------------
    for mod, (bots, floor) in sorted(BOOK_MODULES.items()):
        p = os.path.join(ROOT, mod)
        if not os.path.exists(p):
            continue
        src = open(p, encoding="utf-8", errors="replace").read()
        f, w, o, d = coverage(mod, src, floor, KNOB_ROLES.get(mod) or {},
                              knob_evidence.get(mod), bots)
        findings += f
        warnings += w
        ok += o
        declared += d
    return findings, warnings, ok, declared


def coverage(mod, src, floor, roles, ev, bots=()):
    """Detector C for ONE module, taking its SOURCE TEXT — not a path — so the
    selftest can drive the dark guard and the attribution with fixtures.

    It lived inside audit()'s loop until a mutation run proved the point: with
    the `len(knobs) < floor` guard deleted the whole suite stayed green,
    because nothing could reach the branch without a real 26-knob file on disk.
    Testing AROUND a branch is not testing it — the same lesson
    audit_deploy_coverage.covered() paid for.
    """
    findings, warnings, ok, declared = [], [], [], []
    try:
        knobs = knob_census(src)
        lev = levered_attrs(src)
    except SyntaxError as e:
        return ([(mod, None, "UNMEASURED",
                  f"module will not parse ({e}) — the census cannot vouch for "
                  f"a file it cannot read", None)], [], [], [])
    if len(knobs) < floor:
        # DARK GUARD. Without it a renamed module, a restructured assignment or
        # a rotted parser censuses ZERO knobs and the guard reports "0
        # unlevered" — a perfect score earned by seeing nothing, which is the
        # convergent-metric failure this file exists to catch.
        return ([(mod, None, "DARK",
                  f"knob census found {len(knobs)} of an expected >= {floor} — "
                  f"the parser has rotted, not the code", None)], [], [], [])
    attr, unattr, gross, n_cl = attribute(roles, ev)
    for knob in sorted(knobs):
        if knob in lev:
            continue
        why_ok = LEVER_AUTHORITY_OK.get(f"knob:{mod}:{knob}")
        a = attr.get(knob)
        if a is not None:                           # DECISIVE BY ROLE
            # ALWAYS print the denominator next to the share. The brief this
            # guard was built from carried "73% of the live book's gross
            # loss"; that was $4.00/$5.51, and $5.51 is the book's NET
            # POSITIVE P&L, not its gross loss. Measured: 51.1%.
            sh = (f"{a['loss_share']*100:.1f}% of ${gross:.2f} gross loss, "
                  f"{a['close_share']*100:.1f}% of {n_cl} closes, n={a['n']}")
            if a["n"] < KNOB_MIN_N:
                sh += (f" — attribution INSUFFICIENT (n < {KNOB_MIN_N}); the "
                       f"ROLE is the finding, not the percentage")
            for b in bots:
                pb = ((ev or {}).get("per_bot") or {}).get(b)
                if not pb:
                    continue
                pa, _u, pg, pn = attribute({knob: roles[knob]}, pb)
                if pa[knob]["n"]:
                    sh += (f"\n        {b}: {pa[knob]['loss_share']*100:.1f}% of "
                           f"${pg:.2f} gross loss, "
                           f"{pa[knob]['close_share']*100:.1f}% of {pn} closes, "
                           f"n={pa[knob]['n']}")
            row = (f"{mod}:{knob}", None, "UNLEVERED",
                   f"decides {'/'.join(roles[knob])} — {sh}")
            (declared if why_ok else findings).append(row + (why_ok,))
        elif why_ok:
            declared.append((f"{mod}:{knob}", None, "UNLEVERED",
                             "no lever, declared", why_ok))
        else:
            ok.append((f"{mod}:{knob}", None, "unlevered-unmapped",
                       "no lever and no exit reason mapped to it "
                       "(context only — not a finding)", None))
    if unattr > 0.05:
        warnings.append((mod, None, "UNATTRIBUTED",
                         f"{unattr*100:.1f}% of gross loss falls on exit reasons "
                         f"no knob in KNOB_ROLES claims — the map is rotting",
                         None))
    return findings, warnings, ok, declared


def _stale_exceptions(table=None):
    """A declaration that no longer names anything real is rot. Same check
    audit_venue_purity makes on its own table.

    `table` is injectable so the selftest can prove the detector FIRES, not
    merely that today's tree is clean. A mutation run caught this: replacing
    the whole body with `return []` left the suite green, because the only
    assertion was `assert not _stale_exceptions()` — true either way. A
    negative-only test of a detector tests nothing about the detector."""
    import fleet_tuning
    table = LEVER_AUTHORITY_OK if table is None else table
    stale = []
    for k in table:
        kind, _, rest = k.partition(":")
        if kind == "lever":
            if rest not in fleet_tuning.LEVERS:
                stale.append(k)
        elif kind == "knob":
            mod, _, knob = rest.partition(":")
            p = os.path.join(ROOT, mod)
            if not os.path.exists(p):
                stale.append(k)
                continue
            try:
                if knob not in knob_census(open(p, encoding="utf-8").read()):
                    stale.append(k)
            except Exception:
                stale.append(k)
    return stale


def main(argv):
    show_all = "--all" in argv
    findings, warnings, ok, declared = audit()
    stale = _stale_exceptions()

    def show(rows, head):
        if not rows:
            return
        print(head)
        for name, bound, v, why, _d in rows:
            b = f"[{bound[0]}, {bound[1]}]" if bound and bound[0] is not None else ""
            print(f"  {name:<34} {b:<20} {v}")
            print(f"      {why}")
        print()

    if findings:
        print("LEVER AUTHORITY — a bound that cannot change behaviour is not a "
              "control,\nand a P&L-decisive knob with no lever is outside the "
              "growth rail entirely.\n")
        show(findings, "FINDINGS:")
    show(warnings, "WARNINGS (reported, not fatal):")
    if show_all:
        # The unmapped knobs are CONTEXT — 70-odd rows of "no lever, no exit
        # reason mapped". Printed one per line they bury the five findings, and
        # a report nobody reads to the end is the alarm-fatigue failure. Roll
        # them up per module; the count is the interesting number.
        unmapped = [r for r in ok if r[2] == "unlevered-unmapped"]
        show([r for r in ok if r[2] != "unlevered-unmapped"], "OK:")
        if unmapped:
            per = {}
            for name, *_ in unmapped:
                mod, _, knob = name.partition(":")
                per.setdefault(mod, []).append(knob)
            print("UNLEVERED BUT UNMAPPED (context — no lever AND no exit "
                  "reason in KNOB_ROLES,\nso this guard makes no claim about "
                  "what they cost):")
            for mod, ks in sorted(per.items()):
                print(f"  {mod}  ({len(ks)}): {', '.join(sorted(ks))}")
            print()
        show(declared, "DECLARED (LEVER_AUTHORITY_OK):")
        for name, _b, _v, _w, d in declared:
            print(f"  {name}\n      -> {d}\n")
    if stale:
        print("STALE DECLARATIONS — these name nothing that exists:")
        for k in stale:
            print(f"  {k}")
        print()

    n = len(findings) + len(stale)
    if n:
        print(f"  Fix: change the BOUND so it spans the value that actually "
              f"decides (measured\n  and printed above), REGISTER the knob in "
              f"fleet_tuning.LEVERS, or DECLARE it in\n  LEVER_AUTHORITY_OK "
              f"with a reason that says why the omission is CORRECT.\n"
              f"  Refresh the measurement with --measure (read-only) before "
              f"arguing with a number.\n")
        print(f"audit_lever_authority: {len(findings)} FINDING(s), "
              f"{len(stale)} stale declaration(s), {len(warnings)} warning(s); "
              f"{len(declared)} declared exception(s), {len(ok)} OK.")
        return 1
    print(f"audit_lever_authority: OK — every registered lever can change "
          f"behaviour within its bound, and every decisive knob is levered or "
          f"declared ({len(declared)} declared, {len(warnings)} warning(s)).")
    return 0


# ---------------------------------------------------------------------------
# --measure — READ-ONLY refresh of EVIDENCE. Prints a paste-ready block.
# ---------------------------------------------------------------------------
def _measure(dsn):                                        # pragma: no cover
    import json
    from datetime import datetime, timezone
    import psycopg2                                        # noqa: F401
    import fleet_tuning
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # [2026-07-30 (eu)] tapes are per state KEY now (funding-scan-live /
    # funding-scan-shadow joined lighter-market), fetched lazily once each
    _tapes = {}

    def tape_for(key):
        if key not in _tapes:
            cur.execute("SELECT payload FROM bot_state_history WHERE key=%s "
                        "ORDER BY ts", (key,))
            _tapes[key] = [r[0] for r in cur.fetchall()]
        return _tapes[key]

    def ledger(bot):
        cur.execute("SELECT pair, opened_at, closed_at, reason, pnl_abs FROM "
                    "paper_trades WHERE bot=%s AND closed_at IS NOT NULL", (bot,))
        return cur.fetchall()

    def ts(s):
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()

    out, stamp = {}, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, q in QUANTITIES.items():
        spec = fleet_tuning.LEVERS.get(name)
        if not spec:
            continue
        kind, arg = q["extract"]
        vals, groups = [], 0
        if q["source"].startswith("state:"):
            tape = tape_for(q["source"].split(":", 1)[1])
            groups = len(tape)
            for p in tape:
                vals.extend(_extract_state(p, kind, arg))
        else:
            groups = 1
            rows = [r for r in ledger(q["source"].split(":", 1)[1]) if r[1]]
            if kind == "hold_h":
                vals = [(ts(c) - ts(o)) / 3600.0 for _p, o, c, _r, _x in rows]
            elif kind == "xfield":
                # [2026-08-20 (sf)] A FIELD STAMPED ON THE CLOSE ROW'S `extra`.
                # The two ledger kinds above derive their quantity from the
                # row's TIMESTAMPS, which is all the ledger used to carry — so
                # any lever cutting something the bot knew and did not record
                # was unprofilable by construction, and stayed UNMEASURED
                # forever however many --measure runs ran. General on purpose:
                # every book that stamps a decision quantity at close becomes
                # profilable by adding a spec, with no further change here.
                # `arg` is (field, reason_suffix|None); the suffix scopes the
                # sample to one exit family, because a bar that governs the
                # trail must not be profiled against positions the stop closed.
                fld, suf = arg
                for _p, _o, _c, r, x in rows:
                    if suf and not str(r or "").endswith(suf):
                        continue
                    d = x if isinstance(x, dict) else {}
                    v = d.get(fld)
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        vals.append(float(v))
            elif kind == "gap_after":
                opens = sorted((p, ts(o)) for p, o, _c, _r, _x in rows)
                for p, _o, c, r, _x in rows:
                    if not (r or "").endswith(arg):
                        continue
                    nxt = [t for pp, t in opens if pp == p and t > ts(c)]
                    if nxt:
                        vals.append((min(nxt) - ts(c)) / 3600.0)
        if q.get("abs"):
            vals = [abs(v) for v in vals]
        scale = q["to_q"]
        st = profile(vals, spec["lo"] * scale, spec["hi"] * scale, q["dir"],
                     precision=q.get("precision"), censor_at=q.get("censor_at"))
        if st is None:
            st = {"n": 0}
        st.update({"measured_utc": stamp, "n_groups": groups,
                   "source": q["source"], "unit": q["unit"]})
        out[name] = st

    kn = {}
    for mod, (bots, _f) in BOOK_MODULES.items():
        if not bots:
            continue
        reasons, per_bot = {}, {}
        for b in bots:
            rr = {}
            for _p, _o, _c, r, pnl in ledger(b):
                cnt, ls = reasons.get(r, [0, 0.0])
                loss = -float(pnl) if (pnl or 0) < 0 else 0.0
                reasons[r] = [cnt + 1, round(ls + loss, 4)]
                c2, l2 = rr.get(r, [0, 0.0])
                rr[r] = [c2 + 1, round(l2 + loss, 4)]
            per_bot[b] = {"n_closes": sum(v[0] for v in rr.values()),
                          "gross_loss": round(sum(v[1] for v in rr.values()), 4),
                          "reasons": rr}
        kn[mod] = {"measured_utc": stamp,
                   "n_closes": sum(v[0] for v in reasons.values()),
                   "gross_loss": round(sum(v[1] for v in reasons.values()), 4),
                   "reasons": reasons, "per_bot": per_bot}
    conn.close()
    print("# ---- paste into EVIDENCE / KNOB_EVIDENCE (read-only measurement) ----")
    print("EVIDENCE = " + json.dumps(out, indent=2, sort_keys=True))
    print("KNOB_EVIDENCE = " + json.dumps(kn, indent=2, sort_keys=True))
    return 0


# ---------------------------------------------------------------------------
# SELFTEST — fixtures only. Never asserts that today's real violations still
# exist: a test that fails on GOOD NEWS demands the defect remain
# ([[tests-must-not-fail-on-good-news]]).
# ---------------------------------------------------------------------------
def _selftest():
    # --- 1. THE KNOWN CASE, rebuilt as a fixture. Two pins (crypto 10.512,
    # equity 3.504) plus a spread tail, against the registered bound.
    pinned = [10.512] * 426 + [3.504] * 340 + [0.0] * 46
    pinned += [3.5 + 0.9 * i for i in range(5)] * 20      # the in-bound values
    st = profile(pinned, 3.125, 7.5, "ge", precision=0.1)
    v, why = verdict(st, min_n=MIN_N_TAPE)
    assert v == "INERT-PINNED", (v, st)
    assert st["step_share"] >= 0.50, st["step_share"]
    assert st["sep"] is False, st
    assert st["cliff_ratio"] > 1.0, "the decisive value must read as OUTSIDE hi"
    # ...and the same sample with a bound that DOES reach the pin is not inert.
    st2 = profile(pinned, 3.125, 12.0, "ge", precision=0.1)
    assert verdict(st2, min_n=MIN_N_TAPE)[0] != "INERT-PINNED", st2
    # the detector must be able to say HEALTHY, or it is a rubber stamp
    import random
    random.seed(7)
    unif = [random.uniform(0, 100) for _ in range(4000)]
    assert verdict(profile(unif, 37.5, 87.5, "ge", precision=0.1),
                   min_n=MIN_N_TAPE)[0] == "HEALTHY"
    # a genuinely flat bound
    flat = [50.0] * 500 + [0.5] * 500
    assert verdict(profile(flat, 1.0, 10.0, "ge"), min_n=100)[0] == "INERT-FLAT"
    # saturated: >=90% admitted at BOTH ends, yet the bound is not flat. Note
    # the ladder ORDER matters — a constant sample is INERT-FLAT, not
    # SATURATED, and asserting the wrong one here would have let a flat lever
    # pass as merely "wide".
    sat = [1000.0] * 900 + [1.0 + 9.0 * i / 99 for i in range(100)]
    st_sat = profile(sat, 1.0, 10.0, "ge")
    assert st_sat["swing_pp"] >= FLAT_SWING_PP, st_sat
    assert verdict(st_sat, min_n=100)[0] == "SATURATED", (st_sat,
                                                          verdict(st_sat, 100))

    # --- 2. DARK must NOT read as a verdict. An empty sample is the total
    # failure of the sensor; it once would have rendered as swing=0 -> INERT.
    assert profile([], 1, 2, "ge") is None, "empty sample must not yield stats"
    assert verdict(None)[0] == "DARK"
    assert verdict({"n": 3, "swing_pp": 0.0}, min_n=30)[0] == "DARK", \
        "n below the floor must be DARK, never INERT/HEALTHY"
    assert "DARK" in FATAL and "UNMEASURED" in FATAL, \
        "an unmeasurable lever must not pass silently"

    # --- 3. DIRECTION. A `<=` lever inverts the admitted set; getting this
    # wrong makes every dip/cooldown verdict the mirror of the truth.
    asc = [float(i) for i in range(100)]
    assert profile(asc, 10, 20, "ge")["a_lo"] > profile(asc, 10, 20, "ge")["a_hi"]
    assert profile(asc, 10, 20, "le")["a_lo"] < profile(asc, 10, 20, "le")["a_hi"]

    # --- 4. UNITS. The lever is a FRACTION, the tape is PERCENT. Feeding the
    # raw fraction admits everything — the 8x-basis shape.
    apr_pct = [10.5] * 900 + [3.5] * 100
    raw = profile(apr_pct, 0.03125, 0.075, "ge", precision=0.1)     # NO to_q
    assert raw["a_lo"] == 1.0 and raw["a_hi"] == 1.0, raw
    assert verdict(raw, min_n=100)[0] == "INERT-FLAT", \
        "unadapted units must be LOUD, not quietly healthy"
    adapted = profile(apr_pct, 0.03125 * 100, 0.075 * 100, "ge", precision=0.1)
    assert adapted["a_hi"] < adapted["a_lo"], adapted
    assert verdict(adapted, min_n=100)[0] == "INERT-PINNED", adapted
    assert adapted != raw, "to_q must change the answer, or it is decoration"
    for n, q in QUANTITIES.items():
        assert "to_q" in q and "unit" in q and "dir" in q, n
        assert q["dir"] in ("ge", "le"), n

    # --- 4b. [2026-07-30 (eu)] state-extract kinds, incl. the receipt
    # shapes, on fixture payloads — junk thins the sample, never raises
    _fx = {"funding": {"A": "1.5", "B": None, "C": "junk"},
           "tickets": {"dip": [{"range_pos": 0.1}, {"range_pos": None}]},
           "slope": {"ratios": [1.25, "0.8", "x"], "no_ref": 4},
           "conviction": {"raws": [2.5]},
           "explore": {"pool_n": 7, "prelim_n": 11}}
    assert _extract_state(_fx, "map", "funding") == [1.5]
    assert _extract_state(_fx, "ticket", ("dip", "range_pos")) == [0.1]
    assert _extract_state(_fx, "list", ("slope", "ratios")) == [1.25, 0.8], \
        "receipt lists coerce floats and drop junk"
    assert _extract_state(_fx, "field", ("explore", "pool_n")) == [7.0], \
        "per-cycle scalars yield exactly one sample per payload"
    assert _extract_state(None, "list", ("slope", "ratios")) == []
    assert _extract_state({}, "field", ("explore", "pool_n")) == []
    assert _extract_state({"explore": {}}, "field", ("explore", "pool_n")) == []

    # --- 5. KNOB CENSUS + LEVERED detection, on a fixture that reproduces the
    # Farmer's two-hop shape (`ea = get_lever(...)` then `A = B = ea`).
    src = (
        "import os\n"
        "ENTER_APR = float(os.environ.get('F_ENTER', '0.05'))\n"
        "SCAN_ENTER = float(os.environ.get('F_SCAN', '0.05'))\n"
        "HARD_STOP = float(os.environ.get('F_STOP', '0.10'))\n"
        "MAX_OPEN = int(os.environ.get('F_MAXOPEN', '6'))\n"
        # NOT knobs: a derived constant and a plain literal. A census that
        # swept these in would flood every book with phantom "unlevered"
        # findings and bury the real ones. (Mutation M13 survived until this
        # pair was added — the fixture contained only env knobs, so relaxing
        # the env test changed nothing.)
        "H = 24 * 365\n"
        "LEVER_GRANDFATHER = ('take_profit',)\n"
        "def apply_levers():\n"
        "    global ENTER_APR, SCAN_ENTER\n"
        "    ea = tuning.get_lever('x.enter_apr', ENTER_APR)\n"
        "    if ea != ENTER_APR:\n"
        "        ENTER_APR = SCAN_ENTER = ea\n")
    ks = knob_census(src)
    assert set(ks) == {"ENTER_APR", "SCAN_ENTER", "HARD_STOP", "MAX_OPEN"}, ks
    assert ks["HARD_STOP"] == ("F_STOP", "0.10"), ks["HARD_STOP"]
    lv = levered_attrs(src)
    assert "ENTER_APR" in lv, "get_lever's DEFAULT arg is the knob"
    assert "SCAN_ENTER" in lv, "two-hop assignment must be followed"
    assert "HARD_STOP" not in lv and "MAX_OPEN" not in lv, lv
    # TUNABLE mapping
    src2 = ("import os\nA = float(os.environ.get('A','1'))\n"
            "B = float(os.environ.get('B','1'))\n"
            "TUNABLE = (('t.a','A'),)\n")
    assert "A" in levered_attrs(src2) and "B" not in levered_attrs(src2)
    # a module with nothing must not silently census clean
    assert knob_census("x = 1\n") == {}

    # --- 6. ATTRIBUTION. Shares must be denominated in GROSS LOSS, and the
    # denominator printed — the brief's 73% was $4.00/$5.51 where $5.51 is the
    # book's NET POSITIVE P&L, not its gross loss.
    ev = {"reasons": {"short_stop": [2, 4.0], "short_decay": [15, 0.44],
                      "short_flip": [8, 3.39], "short_take_profit": [11, 0.0]}}
    roles = {"HARD_STOP": ("*_stop",), "EXIT_APR": ("*_decay", "*_flip")}
    a, unattr, gross, n = attribute(roles, ev)
    assert abs(gross - 7.83) < 0.01, gross
    assert abs(a["HARD_STOP"]["loss_share"] - 0.511) < 0.01, a["HARD_STOP"]
    assert a["HARD_STOP"]["n"] == 2 and a["HARD_STOP"]["n"] < KNOB_MIN_N
    assert abs(a["EXIT_APR"]["loss_share"] - 0.489) < 0.01, a["EXIT_APR"]
    assert a["EXIT_APR"]["n"] == 23
    assert abs(unattr) < 1e-9, "everything is mapped here"
    a2, unattr2, _g, _n = attribute({"HARD_STOP": ("*_stop",)}, ev)
    assert unattr2 > 0.4, "an unmapped reason must show up as UNATTRIBUTED"
    assert _reason_match("short-divergence_sl", ("*_sl",))
    assert not _reason_match("short_slippage", ("*_sl",)), "globs are anchored"

    # --- 6b. THE DARK GUARD on the knob census. Found missing by a mutation
    # run: deleting `len(knobs) < floor` left the suite GREEN, because no test
    # could reach the branch. A guard whose removal changes nothing is not a
    # guard, and this is the shape that reports "0 unlevered knobs" from a
    # total parse failure.
    stub = ("import os\nA = float(os.environ.get('A','1'))\n"
            "B = float(os.environ.get('B','1'))\n")
    f_dark, _w, _o, _d = coverage("stub.py", stub, floor=20, roles={}, ev=None)
    assert [r[2] for r in f_dark] == ["DARK"], f_dark
    assert "2 of an expected >= 20" in f_dark[0][3], f_dark
    f_ok, _w, _o, _d = coverage("stub.py", stub, floor=2, roles={}, ev=None)
    assert not f_ok, "above the floor the census must proceed, not stay dark"
    # and a module that will not parse must be LOUD, never silently clean
    f_bad, _w, _o, _d = coverage("stub.py", "def (\n", floor=1, roles={}, ev=None)
    assert [r[2] for r in f_bad] == ["UNMEASURED"], f_bad
    # the decisive-by-role path, end to end on a fixture
    src3 = ("import os\nHARD_STOP = float(os.environ.get('S','0.1'))\n"
            "TAKE_PROFIT = float(os.environ.get('T','0.04'))\n"
            "TUNABLE = (('x.tp','TAKE_PROFIT'),)\n")
    f3, _w, _o, _d = coverage(
        "stub.py", src3, floor=2, roles={"HARD_STOP": ("*_stop",)},
        ev={"reasons": {"a_stop": [2, 4.0], "a_decay": [10, 4.0]}})
    assert [(r[0], r[2]) for r in f3] == [("stub.py:HARD_STOP", "UNLEVERED")], f3
    assert "INSUFFICIENT" in f3[0][3], "n=2 must not headline a percentage"

    # --- 7. CONSUMER scan.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p1 = os.path.join(d, "a.py")
        open(p1, "w").write('tuning.get_lever("taker.tp", TP)\n')
        p2 = os.path.join(d, "b.py")
        open(p2, "w").write('prefix = "live.funding."\n'
                            'tuning.get_lever(prefix + "enter_apr", X)\n')
        # The REAL over-match, reproduced: a file that mentions the lever
        # FAMILY in prose and happens to use the bare word "take_profit"
        # elsewhere. The first version of consumers() accepted `head + "."`
        # anywhere in the text (and even just `head.split(".")[0] + "."`,
        # i.e. the bare string "live."), which put listing_sniper.py under
        # live.funding.take_profit. Prose is not a call site.
        p3 = os.path.join(d, "c.py")
        open(p3, "w").write('# the judge promotes live.funding.* after the '
                            'paired bar; see live. lanes\n'
                            'x = {"take_profit": 1}\nurl = "live.example"\n')
        c = consumers(["taker.tp", "live.funding.enter_apr", "nobody.reads_me",
                       "live.funding.take_profit"], files=[p1, p2, p3])
        base = lambda v: [os.path.basename(x) for x in v]
        assert base(c["taker.tp"]) == ["a.py"], c["taker.tp"]
        assert base(c["live.funding.enter_apr"]) == ["b.py"], "assembled prefix+suffix"
        assert not c["nobody.reads_me"], "an unread lever must read as NO-CONSUMER"
        assert not c["live.funding.take_profit"], \
            ("a common word plus an unrelated 'live.' substring is not a call "
             "site — this exact over-match put listing_sniper.py under the "
             "LIVE funding TP lever")
        # THE REGISTRY IS NOT A CONSUMER. Without this exclusion every lever
        # names itself and NO-CONSUMER can never fire.
        reg = os.path.join(d, "fleet_tuning.py")
        open(reg, "w").write('LEVERS = {"orphan.lever": {}}\n')
        assert not consumers(["orphan.lever"], files=[reg])["orphan.lever"], \
            "a lever named ONLY in the registry must read as NO-CONSUMER"
        assert "fleet_tuning.py" in NOT_A_CONSUMER

    # --- 8. EVIDENCE AGE. Stale evidence is not evidence.
    import datetime as _dt
    now = _dt.datetime(2026, 7, 22, tzinfo=_dt.timezone.utc)
    assert evidence_age_days({"measured_utc": "2026-07-21T00:00:00Z"}, now) < 2
    assert evidence_age_days({"measured_utc": "2026-01-01T00:00:00Z"}, now) > 180
    assert evidence_age_days({}, now) is None
    assert evidence_age_days({"measured_utc": "not-a-date"}, now) is None

    # --- 9. INTEGRATION: drive audit() with INJECTED evidence, both ways, so
    # the wiring itself is covered. Testing around a function is not testing it
    # (the lesson audit_deploy_coverage.covered() paid for).
    fake_files = []
    f_bad, _w, _o, _d = audit(evidence={}, knob_evidence={}, files=fake_files)
    assert any(v == "NO-CONSUMER" for _n, _b, v, _y, _x in f_bad), \
        "no shipped files -> every lever must read NO-CONSUMER"
    # STALE evidence is not evidence. Same EVIDENCE, stamped in 2020: every
    # measured lever must fall back to UNMEASURED rather than keep quoting a
    # distribution from a market that no longer exists.
    # [2026-07-30 A1] fixtures re-anchored from the enter_apr pair to
    # taker.brk_range/momo_chg: the pair's EVIDENCE was deleted with the
    # operator-signed widening (bounds-stale — see the note in EVIDENCE)
    old_ev = {k: dict(v, measured_utc="2020-01-01T00:00:00Z")
              for k, v in EVIDENCE.items()}
    f_old, _w, _o, _d = audit(evidence=old_ev, knob_evidence={})
    stale_v = {n: v for n, _b, v, _y, _x in f_old
               if n in ("taker.brk_range", "taker.momo_chg")}
    assert "UNMEASURED" in set(stale_v.values()), stale_v
    # and unstamped evidence must fail the same way, not sail through
    no_stamp = {k: {kk: vv for kk, vv in v.items() if kk != "measured_utc"}
                for k, v in EVIDENCE.items()}
    f_ns, _w, _o, _d = audit(evidence=no_stamp, knob_evidence={})
    assert any(n == "taker.brk_range" and v == "UNMEASURED"
               for n, _b, v, _y, _x in f_ns), "unstamped evidence must be LOUD"

    f_now, _w2, _o2, _d2 = audit()
    # [2026-07-30 A1] the historical tripwire FIRED as designed: the 22-Jul
    # INERT-PINNED pair was the shipped-registry fixture here until the
    # operator signed the widening (hi 0.075 -> 0.12) — this commit deletes
    # the bounds-stale evidence, so the pair must now read UNMEASURED
    # ("cannot vouch") rather than assert a pin against a cage that moved.
    # The ladder's INERT-PINNED detection itself stays pinned by the
    # synthetic fixtures in section 4 above.
    unm = {n for n, _b, v, _y, _x in f_now if v == "UNMEASURED"}
    assert {"live.funding.enter_apr", "xp.funding.enter_apr"} <= unm, \
        f"the widened pair must read UNMEASURED pending re-measure: {unm}"
    # [(na) 15-Aug] FLIPPED: this pin used to assert HARD_STOP/EXIT_APR are
    # UNLEVERED — the very finding the 15-Aug audit acted on. They are
    # registered (xp/live.funding.{exit_apr,hard_stop}), consumed in
    # apply_levers and entry-priced via pos_exit_bars, so the honest pin is
    # now their ABSENCE from the unlevered set: a regression that severs the
    # consumer would resurface them here and redden this.
    knobs = {n for n, _b, v, _y, _x in f_now if v == "UNLEVERED"}
    assert "lighter_funding_bot.py:HARD_STOP" not in knobs, knobs
    assert "lighter_funding_bot.py:EXIT_APR" not in knobs, knobs

    # --- 10. Declarations must be reasons, and must name something real.
    for k, v in LEVER_AUTHORITY_OK.items():
        assert k.split(":")[0] in ("lever", "knob"), k
        assert len(v) > 60, f"{k}: a reason must be a reason, not a label"
    # the detector must FIRE on rot, not just stay quiet on a clean tree —
    # and it already earned its keep: it caught this file declaring
    # `lighter_funding_bot.py:MAX_OPEN`, a knob that does not exist (the real
    # name is MAX_OPEN_POSITIONS).
    bogus = {"lever:no.such.lever": "x" * 61,
             "knob:lighter_funding_bot.py:NO_SUCH_KNOB": "x" * 61,
             "knob:no_such_file.py:X": "x" * 61,
             "lever:taker.tp": "x" * 61}          # this one is REAL
    got = set(_stale_exceptions(bogus))
    assert got == {"lever:no.such.lever",
                   "knob:lighter_funding_bot.py:NO_SUCH_KNOB",
                   "knob:no_such_file.py:X"}, got
    assert not _stale_exceptions(), _stale_exceptions()
    print("audit_lever_authority selftest OK "
          "(widened enter_apr pair reads UNMEASURED pending re-measure; "
          "HARD_STOP/EXIT_APR reproduce; DARK != verdict; "
          "units, direction, two-hop lever detection, gross-loss denominator, "
          "consumer scan, evidence age, injected-evidence integration)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    if "--measure" in sys.argv:
        i = sys.argv.index("--dsn") if "--dsn" in sys.argv else -1
        dsn = sys.argv[i + 1] if i >= 0 else (os.environ.get("DATABASE_URL")
                                              or os.environ.get("DATABASE_PUBLIC_URL"))
        if not dsn:
            print("--measure needs --dsn <read-only-url> or DATABASE_URL")
            sys.exit(2)
        sys.exit(_measure(dsn))
    sys.exit(main(sys.argv))
