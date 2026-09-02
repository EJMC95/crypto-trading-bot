#!/usr/bin/env python3
"""
experiment_judge.py — 🧪⚖️ the shadow→live PROMOTION JUDGE.

WHY (2026-07-15, user): "positive changes made to shadow bots and new
implementations get carried across to the real money bots … so that they
also carry the edge to a win" — with the bar that separates EDGE from LUCK
(the Trail Blazer lesson: a +$197 paper month evaporated under scrutiny).
Nothing reaches real money on a hot streak; it reaches real money by
beating the live arm, per trade, over a real window, on both halves.

THE ARMS (Funding Farmer — the only live bot that trades often enough to
judge; Tide Rider trades ~weekly and stays backtest-validated):
  live arm    perps-funding-lighter-lighter  — env-default bars (until a
              promotion is in force via live.funding.* levers)
  shadow arm  perps-funding-lighter-lshadow  — the EXPERIMENT arm: runs the
              current candidate's bars via xp.* levers (zero real money)

LIFECYCLE (bot_state 'xp-judge'; hourly; one candidate at a time so
attribution is never confounded):
  IDLE      start the next CANDIDATE: assert its xp.* levers on the shadow
            arm, stamp started_ts. (Every close row carries extra.bars, so
            the ledger records which params produced what.)
  RUNNING   re-assert the xp levers each cycle. Once MIN_DAYS have passed
            and the floors are met (shadow >= MIN_CLOSES closes in-window,
            live >= LIVE_MIN_CLOSES for a fair pair), run the PAIRED
            evaluation: promote only if the shadow arm's mean per-trade
            pnl_pct is positive AND beats the live arm's by MARGIN_PP on
            the full window AND on both halves. Abandon at MAX_DAYS
            without clearing (verdict logged, cooldown, next candidate).
  PROMOTED  assert the live.funding.* counterpart(s) — this judge is the
            ONLY writer of that prefix — and keep the xp levers, so both
            arms run the same bars again (the control arm is restored).
            FADE WATCH: if the live arm's mean pnl_pct since promotion
            goes negative at n >= FADE_N, stop asserting; every lever
            expires back to env defaults on its own. Cooldown, then the
            queue continues. [16-Jul evening] prop_fade is the EARLIER
            signal: fleet_proprioception grades the promotion's episodes
            per-trade vs the live arm's own pre-window AND the shadow
            twin — a fresh HURTING verdict releases before the absolute
            fade bar is reached. The judge stays the only writer;
            proprioception is evidence in, never a hand on the lever.

Every transition pushes to the phone (urgent for PROMOTE and FADE — real
money changed). Fail-safe: no DB / short ledger -> nothing is asserted and
whatever was live expires back to env defaults within the lever TTL.

Run-once process; run_all.sh loops it hourly. --selftest is offline.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import fleet_tuning as tuning

# [(ta)] the fleet's declaration of which LIVE ARMS are retired. Soft import
# for the same reason every other organ's is: a judge that cannot import the
# bus must keep judging, not crash. Dark bus ⇒ no stand-down ⇒ the paired bar's
# own `live >= 10` floor still blocks every promotion onto a flat arm, so the
# fail-open direction here costs visibility, never safety.
try:
    import fleet_bus as _bus
except Exception:  # noqa: BLE001
    _bus = None

try:
    import fleet_proposals as fprop      # organ proposal channel (optional)
except Exception:  # noqa: BLE001
    fprop = None

KEY = "xp-judge"
TTL_SEC = int(os.environ.get("XPJ_TTL_SEC", "10800"))
LEVER_TTL = int(os.environ.get("XPJ_LEVER_TTL", "7800"))      # ~2h re-assert
# [2026-09-02 (wv)] THE SERIAL LANE FOLLOWS THE LIVING PAIR. These were
# literals naming 💸 the Farmer's arms, retired 22-Aug — so the fleet's only
# path from a shadow candidate to real money stood down for 11 days while
# 👩 mum traded real money with no judge. fleet_bus.living_pair_default is the
# ONE owner (the shortfall organ reads the same one), env still wins.
def _default_pair():
    try:
        return _bus.living_pair_default()
    except Exception:  # noqa: BLE001
        return ("perps-funding-lighter-lighter", "perps-funding-lighter-lshadow")


_DEF_LIVE, _DEF_SHADOW = _default_pair()
SHADOW_BOT = os.environ.get("XPJ_SHADOW_BOT") or _DEF_SHADOW
LIVE_BOT = os.environ.get("XPJ_LIVE_BOT") or _DEF_LIVE
MIN_DAYS = float(os.environ.get("XPJ_MIN_DAYS", "7"))
MAX_DAYS = float(os.environ.get("XPJ_MAX_DAYS", "14"))
# [2026-07-17 IMB-07] the done-list AGES: a finite candidate universe (3
# statics + <=6 incubator lever-sets) with a lifetime done-list permanently
# self-exhausted the pipeline — an ABANDONED/FADED candidate becomes
# retry-eligible after this many days. Retry is FALLBACK-only (see
# pick_candidate): untried candidates always come first.
DONE_RETRY_D = float(os.environ.get("XPJ_DONE_RETRY_D", "28"))
MIN_CLOSES = int(os.environ.get("XPJ_MIN_CLOSES", "30"))      # shadow arm
LIVE_MIN_CLOSES = int(os.environ.get("XPJ_LIVE_MIN_CLOSES", "10"))
MARGIN_PP = float(os.environ.get("XPJ_MARGIN_PP", "0.5"))     # per-trade pp
FADE_N = int(os.environ.get("XPJ_FADE_N", "15"))
COOLDOWN_H = float(os.environ.get("XPJ_COOLDOWN_H", "48"))
# [2026-07-16 AUDIT] promoted-phase ledger blackout tolerance: keep re-asserting
# live levers through a SHORT ledger outage (a DB blip shouldn't release a
# 7d-earned promotion), but past this many consecutive blind cycles stop
# asserting — fade-watch is blind, so the fail-safe direction (levers expire
# back to env defaults) must win over an indefinitely-blind promotion.
BLIND_MAX = int(os.environ.get("XPJ_BLIND_MAX_CYCLES", "24"))

#: The one-sided 90% normal quantile, the MDE multiplier for `_pair_power`.
#: DELIBERATELY NOT imported from `fleet_allocation.Z_LOWER`, which is the same
#: 1.28 for the same reason: that one is a LIVE ENV LEVER on the allocation
#: lane (`ALLOC_Z_LOWER`), so importing it would let a session tightening
#: capital allocation silently move the judge's published power report. Same
#: number, different owner — named here so the coincidence is on the record
#: rather than looking like a missed de-duplication.
MDE_Z = 1.28


def half_floors(min_closes=None, live_min=None):
    """THE PER-HALF SAMPLE FLOORS — one owner, so the bar and the power report
    can never disagree about what the binding rung is.

    [(vm)] `paired_eval` computed these inline and `_pair_power` retyped the
    FULL-WINDOW floors instead, which is how the published MDE came to describe
    a rung that is not the binding one. Returns (shadow_half, live_half)."""
    mc = MIN_CLOSES if min_closes is None else min_closes
    lm = LIVE_MIN_CLOSES if live_min is None else live_min
    return max(2, mc // 2), max(3, lm // 2)


# One candidate at a time, in order.
FARMER_CANDIDATES = [
    # [2026-07-21 REVIEW D2] the gate WIDENING (11-Jul "opt-in, shadow-validate",
    # re-denominated 17-Jul to enter-gate-0.0375) is DROPPED from the queue:
    # scripts/backtest_funding_lighter.py measured the 0.03-0.08 TRUE region as
    # the WORST on the gate curve (0.03 loses -$76 / 0.05 -$42 on 150d, both
    # halves) — spending a 7-day judge slot re-testing a widening the venue's
    # own tape refutes contradicts the evidence. The gate direction the tape
    # DOES support (tightening toward the 0.122 friction breakeven) is already
    # running as the re-spec'd 0.075 candidate (see _respec_clamped).
    #
    # [2026-07-29 (ev) ORDER REVERSED — slope-gate-off now runs FIRST.] The
    # 28-Jul review (D7) queued slope-gate-off as "the natural next judge
    # candidate AFTER tp-0.06", and that ordering was correct ON ITS PREMISE:
    # tp-0.06 was believed evidence-backed because "take_profit IS the
    # Farmer's measured-positive exit family". scripts/study_farmer_take_profit
    # measured that premise on Lighter's own tape and it does NOT survive:
    #   * the exit-family claim is TRUE but does not imply raising the bar —
    #     TP exits are the only positive family ($1.010/trade at 0.04) and
    #     raising 0.04 -> 0.06 cuts them 224 -> 117, pushing those trades into
    #     flip/cold/max_hold. Two different populations; a non-sequitur.
    #   * NO take_profit value is both-halves positive, at either universe or
    #     either slip (h1 is negative in every row).
    #   * tp-0.06 vs the live 0.04 is +$13.89 on the canonical top-25 and
    #     -$50.43 on all-79 — the UNIVERSE flips the sign. Unresolvable here.
    # tp-0.06 is therefore UNSUPPORTED, not refuted, and it is NOT deleted:
    # the judge's paired live-vs-shadow bar is independent forward evidence,
    # and a mute backtest is not a negative one. But the SERIAL queue is the
    # fleet's only path to live.funding.* at >=7d per slot, so the slot goes
    # to the candidate the venue's own tape actually supports. Reordering is
    # restrict-safe: no bar moves, no lever changes, the paired bar still
    # gates every promotion.
    # [2026-08-20 (sk)] max-hold-24 JUMPS THE QUEUE, and it is the
    # best-evidenced candidate this queue has ever carried.
    #
    # THE MEASUREMENT, on 328 ledger closes (279 priced, 14-Jul->19-Aug)
    # replayed against Lighter's own 15m candles. CALIBRATION GATE PASSED:
    # the harness reproduces 27/27 take-profit closes and 238/243 (97.9%) of
    # the non-barrier ones. Return by realised hold, pooled:
    #     0-3h   +0.285%  (n=85, t=+2.30)      24-48h  -1.797%  (n=20, t=-1.89)
    #     3-6h   +0.481%  (n=37, t=+2.59)      48-73h  -1.797%  (n=22, t=-3.07)
    #     6-12h  +0.413%  (n=67, t=+1.97)
    #     12-24h +0.569%  (n=48, t=+1.24)
    # **The book's returns invert at 24h.** The cap sweep, computed SEPARATELY
    # per arm and peaking at 24h on BOTH — a single interior peak bracketed by
    # worse cells on both sides, not a grid edge:
    #     LIVE   (n=91)  72h +0.113 (t=+0.81, halves +15.0/-4.7)
    #                 -> 24h +0.217 (t=+1.76, halves +15.8/+4.0)
    #     SHADOW (n=159) 72h -0.054 (t=-0.28, halves +18.3/-26.9)
    #                 -> 24h +0.270 (t=+1.59, halves +36.4/+6.5)
    # Pooled delta +0.1924pp; trade bootstrap 95% CI [+0.064, +0.325],
    # P(delta<=0)=0.0017; symbol-cluster bootstrap CI [+0.049, +0.468].
    # Realised-path maxDD **41.99pp -> 14.52pp**. The gain is spread across
    # every exit family, not one.
    #
    # AND IT IS NOT THE TAPE. Two same-coin/same-side placebos: an
    # unconditioned random-start truncation gains +0.230pp where this book's
    # own gains +1.278pp; the rigorous one — synthetic positions CONDITIONED
    # IDENTICALLY (same barriers, required to survive 24h untouched, so the
    # survivorship selection is matched) — returns -0.299% on the forward leg
    # against this book's -1.278%. Excess -0.979pp, t=-2.44, P(excess>=0)=0.011.
    # That kills the martingale/conditioning explanation. A random short on
    # these coins earns -0.07%/24h, so this is not the (hm) free-short bonus
    # either. Jackknife by coin: no coin carries it (t=+2.33..+3.73 across all
    # eight drops).
    #
    # THE PRICE, DECLARED. `BRACKET_SIG_FIELDS` includes `max_hold_h`, so a
    # promotion RESETS the 30-day era on both arms and costs the live row 26.6
    # of the 30 days it has banked. Cheap here, and checked: the live row's own
    # horizon organ says its t bar needs ~1208d at the current trajectory, so
    # the window bar was never binding — and the cap is precisely what changes
    # the trajectory (t +0.82 -> +1.76 live, -0.25 -> +1.59 shadow, and the
    # halves bar flips FAIL->PASS on both arms). Forfeited tail accrual is
    # netted pro-rata into every number above (mean +0.097pp/affected trade).
    # Roughly one extra round trip per truncated position, ~0.012pp against a
    # +0.19pp gain. Turnover is NOT the win: the book runs 4/6 and 3/5 slots
    # against `eligible: 2`, so a shorter hold buys no extra entries today.
    #
    # WHY IT GOES FIRST. `slope-gate-off` has been `phase: running` with
    # `promoted_ts: null` for five weeks behind a paired bar that was
    # structurally biased against it (see `match_policy` — the shadow arm's
    # explore bucket was a 0.161pp handicap against a 0.50pp margin, now
    # fixed). This candidate is the only one in the queue whose evidence
    # includes a conditioned placebo, a calibration gate and two bootstraps,
    # and it is the only one that moves the DRAWDOWN bar. 24.0 is the cage
    # floor of `xp.funding.max_hold_h` ([24.0, 96.0]), so no cage change is
    # needed. No flap risk: `pos_bars()` prices max_hold at ENTRY, so it
    # reaches only new positions. The judge remains the sole writer of
    # `live.funding.*` — nothing here touches the live arm.
    {"name": "max-hold-24",     "levers": {"xp.funding.max_hold_h": 24.0}},
    {"name": "slope-gate-off",  "levers": {"xp.funding.slope_gate": 0}},
    # [2026-08-13 (ln) ORDER SWAPPED — min-vol-1e5 now runs BEFORE
    # min-vol-2e6, by operator directive ("fix all of the above and ...
    # what we know does work"), executed under the 13-Aug real-money grant.
    # WHY: the Farmer-live horizon now reads its t bar UNREACHABLE at the
    # current mean (+0.079%/trade needs ~1,152 closes ≈ 311d at 3.48/d) —
    # the blocker is the MEAN, and this queue is the only path that can
    # raise it. min-vol-1e5 holds the strongest measured mean-raiser in the
    # queue (the [0.1M,2M) band alone: +$14.83, BOTH halves, robust at p90,
    # vs the incumbent's +$4.01 — STUDY_THIN_TIER_MIN_VOL_2026-08-05),
    # while min-vol-2e6's role was to DE-RISK that read (~11-Sep subset
    # verdict) at the cost of a 7-day slot. The operator's directive buys
    # the speed. Restrict-safe per the (ev) precedent: no bar moves, no
    # lever changes, the paired live-vs-shadow bar still gates every
    # promotion, fade-watch unchanged.
    # [2026-08-05 (ka)] min-vol-1e5 — the thin-tier follow-through, filed
    # the day the operator signed both cage floors down ('if it produces
    # better numbers then proceed'). THE NUMBERS, from the calibrated
    # backtest_funding_lighter.run() over 30d of the venue's own tape, each
    # tier priced at ITS OWN measured friction ((js) fill study;
    # STUDY_THIN_TIER_MIN_VOL_2026-08-05):
    #   * the [0.1M,2M) band ALONE (74 books) at tier-median 5.12bps/fill,
    #     shipped gate 0.05: +$14.83, n=158, win 65.8%, BOTH halves
    #     positive (+7.68/+10.29), maxDD -7.97 — vs the incumbent >=10M
    #     universe's +$4.01 on the same window at ITS 0.27bps median.
    #   * robust at the tier's p90 (14.77bps): +$7.20. At gate 0.12 the
    #     churn doubles and p90 flips negative (-$6.89) — 0.05 is the
    #     better in-tier gate; the higher expressible gate is NOT filed.
    #   * fail-closed combined read (every book charged 5.12): +$0.20 vs
    #     incumbent +$4.01 — flat, not materially worse; the harness fills
    #     slots in volume order while the real bot RANKS by |apr|, so the
    #     truth sits between the combined and band-alone cells.
    # ~~WHY FOURTH~~ [13-Aug (ln): SUPERSEDED — swapped ahead of
    # min-vol-2e6 by the reorder note above; the original ordering logic
    # is kept below for the record.] (prior ordering per (ju)): its prior
    # is an own-tape
    # replay with both halves positive — stronger than enter-gate-0.105's
    # negative tape prior below, weaker than nothing above it; min-vol-2e6
    # keeps its filed slot (its subset verdict ~11-Sep de-risks this one's
    # read). Honesty gates ride along: 30d, one regime, $25 clips
    # (larger-clip scaling in thin books UNMEASURED), iteration-order slot
    # model, and the band's two four-digit-APR outliers (SKR/CXMT — CXMT
    # is the quarantined-manipulation symbol) are inside these numbers;
    # the arm's own SCAN_MAX_SLIP_BPS/MAX_SPREAD_BPS vetoes stay senior
    # per-book at runtime, which the harness does not model.
    {"name": "min-vol-1e5",     "levers": {"xp.funding.min_vol": 1e5}},
    # [2026-08-05 (jy)] min-vol-2e6 — the (ju) reserved slot, FILED. The
    # (ju) QUEUE NOTE's three gaps are closed the same day: XP_TO_LIVE
    # mapping (below), the arm's bars.min_vol receipt (apply_levers +
    # entry_stamp, shipped to both arms via the (jy) marked Farmer
    # deploy), and LIVE_ENV_DEFAULTS/impl-shortfall release paths.
    # DERIVATION of the VALUE — the cage floor, 2e6, for three measured
    # reasons (STUDY_MEASURED_FRICTION_2026-08-05 §1):
    #   * $2M is the carry sibling's own floor — the fleet's biggest
    #     earner trades this tier, and its shadow arm models 1.01bps/fill
    #     median (n=218), consistent with the tier's MEASURED 1.93bps
    #     median — so the shadow ledger the paired bar will grade prices
    #     the new books' friction honestly (ShadowBroker validated ±60%).
    #   * Measured 05-Aug at 2e6: +3 books join (LIT 31.5% APR — pays the
    #     tier's ~3.9bps rt in ~11h vs the 72h max hold and 5.9h live
    #     median hold; ZEC/PUMP sit AT the venue's 10.5% resting default,
    #     needing ~32h — inside max hold, marginal). Any HIGHER value
    #     admits a subset of the same 3: the floor is a crude proxy for
    #     what the scan measures directly (SCAN_MAX_SLIP_BPS on the real
    #     clip, MAX_SPREAD_BPS), and those stay senior per-book — so ask
    #     the widest expressible question and let the paired bar judge.
    #   * WHY ABOVE enter-gate-0.105 and not higher: its prior (the
    #     study's per-tier friction table — the first measured friction
    #     prior) is unrefuted, so it outranks the negative-tape-prior row
    #     below; slope-gate-off is venue-supported ((dp)) and tp-0.06's
    #     second place is (ju)-pinned — this row takes the RESERVED slot,
    #     it does not re-litigate the order above it.
    # CAGE LIMIT, recorded so the verdict is read honestly: ALL five
    # extreme books that MOTIVATED the lever ((fz): H100/XLM/SKR/XPD/
    # TRUMP) measured $0.11-0.35M on 05-Aug — BELOW the 2e6 cage floor,
    # in the <$1M tier (5.12bps/fill median, p90 14.77). NO candidate
    # value can reach them; widening the cage is an operator-signed act
    # (precedent: the 30-Jul A1 widening) — queued, OPERATOR_QUEUE.md
    # item 2. A verdict on this candidate is a verdict on the $1-10M
    # tier only, not on the extreme-book thesis.
    {"name": "min-vol-2e6",     "levers": {"xp.funding.min_vol": 2e6}},
    # [2026-07-21, corrected same day] BOTH hold-cap candidates (hold-48,
    # and the hold-96 that briefly replaced it) are WITHDRAWN — refuted by
    # adversarial verify against the fleet's own recorded evidence:
    #   (1) scripts/backtest_funding_lighter.py §3b: "'hold longer' REFUTED,
    #       recorded so nobody re-runs it" (72->720h moves funding earned by
    #       $0.20 and makes P&L WORSE; the cap never binds — max_hold is
    #       ~5% of exits, median hold 8h). hold-96 re-ran a recorded-refuted
    #       hypothesis; hold-48 tests the same inert knob the other way.
    #   (2) The lever is inert where it acts: on the Farmer twin only 2/59
    #       closes hit max_hold — no cap value can move the paired mean by
    #       the judge's +0.5pp bar on >=30 closes. A 7-day slot is wasted by
    #       construction at ANY hold number.
    #   (3) The +$46.21 decay_paid family that motivated hold-96 belongs to
    #       the HEDGED carry bot, where the fee-payback EXIT (shipped 07-07,
    #       FEE_PAYBACK_MARGIN) is the mechanism — an exit-architecture
    #       question for a future candidate, not a cap number; and on a
    #       hedged book "close only when paid" records wins by construction.
    # [2026-07-28 D7] slope-gate-off's own evidence, and why it took the slot:
    # the (dp) Lighter backtest refuted the slope gate ON THIS VENUE (live gate
    # 0.05: durable-history -$14.90 vs gate-off +$34.07 @5bps; the gate is
    # HL-validated, Lighter-NEGATIVE). That is a real prior in the supported
    # direction, on the tape that holds the money — the thing tp-0.06 lacks.
    # The Farmer consumes xp.funding.slope_gate in apply_levers and stamps the
    # receipt (`bars.slope_gate`), so the skew gate can accrue.
    #
    # tp-0.06 keeps its slot HERE (second), on the reasoning recorded above.
    # Its original rationale line — "take_profit IS the Farmer's
    # measured-positive exit family (shadow 11-0 +$14.96, live 9-0 +$8.11)" —
    # is kept verbatim on purpose: the numbers are real, the INFERENCE from
    # them to "raise the bar" is what the 29-Jul study falsified.
    #
    # [2026-08-06 (ld)] MOVED FROM SECOND TO FOURTH — both min_vol rows now
    # outrank it, and this applies the queue's OWN rule rather than a new one.
    # (ju) fixed the principle — rank by PRIOR STRENGTH — when it wrote that "a
    # negative-prior candidate must never outrank the supported
    # (slope-gate-off) or merely-mute (tp-0.06) ones". Read forward, the same
    # rule says a candidate with a POSITIVE measured prior must not sit BELOW a
    # merely-mute one. (ka) all but wrote the correction itself: it placed
    # min-vol-1e5 fourth on the grounds that its prior was "weaker than nothing
    # above it" — while tp-0.06 sat above it. Nothing above it was stronger;
    # the row simply took the next free slot. (jy) likewise declined to
    # re-litigate, taking "the RESERVED slot" — a scope choice, not an argument
    # that tp-0.06 earns second place.
    # THE PRIORS, which is the whole argument:
    #   * tp-0.06 — MUTE. NO take_profit value is both-halves positive at
    #     either universe or either slip, and the universe FLIPS THE SIGN
    #     (+$13.89 top-25 vs -$50.43 all-79): "unresolvable here".
    #   * min-vol-2e6 — unrefuted per-tier friction prior, +3 books.
    #   * min-vol-1e5 — own-tape replay: +$14.83, n=158, win 65.8%, BOTH
    #     halves positive (+7.68/+10.29), robust at the tier p90 (+$7.20).
    #     The strongest prior in this queue.
    # WHY THE MOVE IS WORTH MAKING — a schedule fact, not a taste. The queue is
    # SERIAL at 7-14d + 48h cooldown, so a position IS weeks. On (ju)'s own
    # arithmetic min-vol-1e5 started ~20-Sep and resolved ~4-Oct; ahead of
    # tp-0.06 it starts ~4-Sep. It is also the only queued candidate aimed at
    # the binding constraint of the fleet's ONLY on-track book: 💸 the Farmer
    # needs ~102 in-era closes for t>=2.0 against 44 today, and THROUGHPUT AT
    # CONSTANT MEAN is the sole honest route ((kp)). The shipped 10e6 floor
    # admits ~11 books and passes ~3; 1e5 admits 74 more.
    # tp-0.06 IS NOT DELETED and its position is not a verdict: a mute backtest
    # is not a negative one, and the paired live-vs-shadow bar remains
    # independent forward evidence. Restrict-safe exactly as (ev)'s reorder
    # was — no bar moves, no lever changes, no promotion becomes easier; only
    # the ORDER in which questions are asked.
    # 2e6-BEFORE-1e5 IS PRESERVED DELIBERATELY: (ka) gives a real dependency
    # for it ("its subset verdict de-risks this one's read"), untouched here.
    {"name": "tp-0.06",         "levers": {"xp.funding.take_profit": 0.06}},
    # [2026-08-05 (ju)] enter-gate-0.105 — the measured-friction study
    # (STUDY_MEASURED_FRICTION_2026-08-05 §3b, entry (js)) filed through
    # THIS channel.
    # DERIVATION, from measured fills not assumption: Farmer round trip =
    # 0.22 + 0.36 = 0.58bps median (n=91 tx-hash fills) at the live book's
    # own 5.9h median hold -> breakeven 0.58e-4 * 8760 / 5.9 = 8.6% TRUE apr;
    # the bar is the venue's RESTING DEFAULT 0.105 = breakeven + 22% margin
    # (an entry at 10.5% pays its round trip in ~4.8h vs the 5.9h the market
    # grants). 0.105 is the exact "enter only above modal" candidate the
    # 30-Jul A1 cage widening (hi -> 0.12, operator-signed) existed to make
    # askable. Registration only: nothing moves until this candidate's slot
    # arrives, and then only on the shadow twin; live.funding.* still changes
    # ONLY via this judge's paired bar.
    # WHY IT SITS LAST — the tape prior is AGAINST it, recorded here so the
    # eventual verdict is era-honest: on the cached 180d/25-book tape at
    # HEAD, varying ONLY (gate, slip), gate 0.05 nets +$15.60/+$10.65 at
    # measured slip 0.27/0.97bps while 0.105 nets +$5.58/+$0.42 — shipped
    # beats this candidate full-window at BOTH measured frictions, and h1 is
    # negative for every gate at every slip (the study's regime caveat). It
    # is still worth a LAST-position slot because that same cache has a
    # documented reproduction problem (§3b: the 23-Jul both-halves read does
    # not reproduce; universe drift flips signs —
    # [[backtest-cache-serves-the-wrong-universe]]), so the paired
    # live-vs-shadow bar is the only instrument that can settle it — and the
    # bar fails closed: no promotion unless the twin beats live by >=0.5pp
    # on the window AND both halves.
    # TRIPWIRE DEPENDENCY: the premise is the measured 0.58bps rt, guarded
    # by the published impl-shortfall.order_slip.live ~2bps tripwire (worst
    # single measured fill in 13d: 2.06bps). At ~2bps rt the breakeven is
    # 29.7% TRUE — OUTSIDE the cage — so a tripped guard kills this
    # candidate's rationale; read any verdict against it.
    # [2026-08-05 (jy)] the reserved min_vol candidate is FILED ABOVE this
    # row (its block precedes the (ju) one), so this row starts one slot
    # later than the (ju) dates.
    {"name": "enter-gate-0.105", "levers": {"xp.funding.enter_apr": 0.105}},
]
XP_TO_LIVE = {"xp.funding.enter_apr": "live.funding.enter_apr",
              "xp.funding.take_profit": "live.funding.take_profit",
              "xp.funding.max_hold_h": "live.funding.max_hold_h",
              "xp.funding.slope_gate": "live.funding.slope_gate",
              # [2026-08-05 (jy)] gap 1 of the (ju) QUEUE NOTE: without
              # this mapping a running min_vol spec would _needs_reset as
              # invalid state and promotion could not name its live twin
              "xp.funding.min_vol": "live.funding.min_vol",
              # [(wv)] 👩 mum's lane — the live twins are judge-owned by
              # fleet_tuning's prefix map; the board keeps her clip scale.
              "xp.mum.rsi_max": "live.mum.rsi_max",
              "xp.mum.max_hold_min": "live.mum.max_hold_min"}

# [2026-09-02 (wv)] 👩 MUM'S CANDIDATES — hand-declared and MEASURED, in
# order. The incubator's funding genes are the Farmer's and cannot breed
# these (its offspring are refused by lane prefix in candidate_pool), so this
# list is the whole queue until a family-gene incubator exists.
#   rsi-32     — (tr): 32 is the measured peak by two independent studies
#                (STUDY_MUM_SUPPLY: bracket +0.104%/t, t=2.38, both halves),
#                36 shipped as "she doesn't miss anything too good".
#   hold-720   — the plateau's tighter edge (12h): the (ro) carry-tax
#                argument taken one step further.
#   hold-2880  — the wider edge (48h): more of the roi ladder's tail.
MUM_CANDIDATES = [
    {"name": "mum-rsi-32", "levers": {"xp.mum.rsi_max": 32.0}},
    {"name": "mum-hold-720", "levers": {"xp.mum.max_hold_min": 720.0}},
    {"name": "mum-hold-2880", "levers": {"xp.mum.max_hold_min": 2880.0}},
]
LANE_CANDIDATES = {"farmer": FARMER_CANDIDATES, "mum": MUM_CANDIDATES}


def _lane_of(live_bot):
    """The declared pair whose live arm is `live_bot` (inline; serial_lane_id
    below is the same lookup and is used everywhere after import)."""
    for pid, ps in (getattr(_bus, "JUDGED_PAIRS", {}) or {}).items():
        if isinstance(ps, dict) and ps.get("live_bot") == live_bot:
            return pid
    return None


def lane_prefix(live_bot=None):
    """The xp.* prefix of the machine's lane — candidate_pool admits queue
    proposals ONLY under it, so a Farmer offspring cannot land on mum."""
    ps = (getattr(_bus, "JUDGED_PAIRS", {}) or {}).get(_lane_of(live_bot or LIVE_BOT)) or {}
    return str(ps.get("xp_prefix") or "xp.funding.")


#: the CURRENT lane's queue (the name every existing consumer reads)
CANDIDATES = list(LANE_CANDIDATES.get(_lane_of(LIVE_BOT), []))


def now_ts():
    return datetime.now(timezone.utc).timestamp()


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def parse_ts(s):
    s = str(s).strip().replace("Z", "+00:00")
    if s.endswith(" UTC"):
        s = s[:-4] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


# ---------------------------------------------------------------------------
# pure evaluation (selftested offline)
# ---------------------------------------------------------------------------

def ran_candidate(row, levers):
    """PROOF the arm actually APPLIED these levers on this close.

    [2026-07-16 SKEW GATE] `extra.bars` is stamped by the ARM, and only from
    inside its apply_levers() — an image with no lever-reading code
    structurally CANNOT emit it. That makes a missing receipt DISPROOF, not
    silence, which is the whole point: this gate must fail CLOSED.

    Why it exists: the judge asserted xp.funding.enter_apr=0.30 for hours at a
    frozen shadow arm carrying zero lever code (30 closes, 0 receipts). It runs
    the env default 0.40 — the SAME gate live runs — so the paired bar was
    scoring 07-11-code vs 07-16-code and calling the difference the candidate's
    edge, on a path that promotes to live.funding.* (REAL MONEY).
    """
    bars = (row.get("extra") or {}).get("bars")
    if not isinstance(bars, dict):
        return False
    for name, want in (levers or {}).items():
        # xp.funding.enter_apr -> enter_apr (the arm stamps the bare bar name)
        got = bars.get(str(name).split(".")[-1])
        try:
            if got is None or abs(float(got) - float(want)) > 1e-9:
                return False
        except (TypeError, ValueError):
            return False
    return True


def arm_trades(rows, bot, start_ts, end_ts=None, levers=None,
               keep_srcs=None):
    """[(close_ts, pnl_pct)] for one arm inside the window, oldest first.

    levers=None keeps the historical behaviour (time-window attribution only) —
    correct for the LIVE control arm, which runs env defaults and whose rows
    predate the receipt. Pass levers to count ONLY closes the arm PROVED it ran
    them on (see ran_candidate).

    [2026-08-28 (vd)] HALT EVENTS ARE NOT TRADES, AND THIS IS THE SAMPLE THE
    PROMOTION DECISION IS MADE ON.

    The only filter here was `profit_ratio is None`, and a phantom close — a
    halt/flatten EVENT with $0.00 P&L and no entry price — carries
    `profit_ratio = 0.0`, so every one of them passed straight into `sh_h`/
    `lv_h`, the per-half paired bar that IS the promotion, and into fade-watch.

    The judge's own PUBLISHED power block already excludes them (avo live reads
    `n=6`, georgia `n=51`), because `_pair_power` applies the pair's
    `strip_exits`. But `_pair_power`'s docstring says it is *"REPORT ONLY ...
    nothing gates on it"* — so the number the operator READS was clean while the
    number that DECIDES was not. That is the (gk)/(iz) shape: a defense that
    exists in the report and not in the actuator.

    DIRECTION, which is why it is worth touching a promotion gate at all: a
    0.0% row pulls a losing arm's mean toward zero and raises `n`, shrinking
    SE — so phantoms flatter whichever arm holds them, in the PROMOTIONAL
    direction. Priced on avo's pair: the shipped shadow-vs-live gap reads
    -0.4566pp over 14d against a phantom-filtered -1.4825pp (delta 1.03pp), and
    -0.3485 vs -3.2004 over 7d (delta 2.85pp) — against a `MARGIN_PP` of 0.5,
    i.e. 2.1x and 5.7x the bar.

    EXPECTANCY TODAY: ZERO, verified rather than assumed. Every pair is
    `unjudgeable` or `stood_down` (avo live n=6, mum n=0, georgia blocked on
    `policy_stamp_required`, farmer retired), so no promotion is reachable. The
    exposure is the next winning live arm that halts.

    WHAT IS DELIBERATELY **NOT** DONE HERE, with the number that refuses it:
    the pair specs also declare `strip_exits = ("daily_loss", "kill_switch",
    "v1_legacy")`, and a sweep recommended applying those here too. **Refused.**
    `strip_exits` removes REAL forced-flatten LOSSES, not just events —
    measured on georgia's live arm, phantom-filtering alone gives
    **n=57, -0.1768%/trade**, and adding `strip_exits` gives
    **n=51, +0.0535%/trade**. It FLIPS A LOSING REAL-MONEY ARM POSITIVE by
    discarding six trades that cost real dollars. Whether a forced flatten
    belongs in a promotion sample is a genuine policy question with a measured
    sign change attached; it is not a correctness fix and must not ride in on
    one.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "scripts"))
        from golive_readiness import is_phantom_close as _phantom
    except Exception:                                        # noqa: BLE001
        _phantom = None
    out = []
    for r in rows or []:
        if str(r.get("bot")) != bot or r.get("profit_ratio") is None:
            continue
        if _phantom is not None and _phantom(r):
            continue
        if levers is not None and not ran_candidate(r, levers):
            continue
        # [(sk)] entry-policy match — see `match_policy`. Applied here so the
        # decision is made while the ROW is in hand; a caller filtering the
        # returned (ts, pct) pairs cannot, because close_ts is not unique.
        if keep_srcs is not None and _src_of(r) not in keep_srcs:
            continue
        try:
            ts = parse_ts(r.get("close_ts"))
        except Exception:
            continue
        if ts >= start_ts and (end_ts is None or ts < end_ts):
            out.append((ts, float(r["profit_ratio"])))
    out.sort()
    return out


def _src_of(row):
    """The ENTRY POLICY that produced a close, or None when unstamped."""
    x = row.get("extra") if isinstance(row, dict) else None
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except Exception:                                        # noqa: BLE001
            x = None
    v = (x or {}).get("src") if isinstance(x, dict) else None
    return str(v) if isinstance(v, str) and v else None


def policy_srcs(rows, bot, start_ts, end_ts=None):
    """The set of entry policies one arm actually ran in the window.

    None (not an empty set) when the arm stamps nothing — "I cannot tell" and
    "the arm ran no policies" are different states, and only the first must
    disable the match.
    """
    seen, any_row = set(), False
    for r in rows or []:
        if str(r.get("bot")) != bot or r.get("profit_ratio") is None:
            continue
        try:
            ts = parse_ts(r.get("close_ts"))
        except Exception:                                        # noqa: BLE001
            continue
        if not (ts >= start_ts and (end_ts is None or ts < end_ts)):
            continue
        any_row = True
        sv = _src_of(r)
        if sv:
            seen.add(sv)
    return seen if (seen or not any_row) else None


def match_policy(rows, bot, start_ts, end_ts, keep, levers=None):
    """Restrict one arm to closes whose entry policy the CONTROL also ran.
    Returns (trades, dropped).

    FILTERS AT THE ROW, deliberately. The first draft joined `arm_trades`'
    `[(ts, pct)]` back onto the rows by TIMESTAMP, and a fixture caught it
    within the hour: two closes can share a close_ts — ⚖️ Counterweight closes
    ten legs in one instant, and even here 3 of 40 on-policy closes were
    silently dropped because an off-policy row overwrote their key. A join on a
    non-unique key is not a filter.

    [2026-08-20 (sk)] WHY THE PAIRED BAR NEEDED THIS. The judge's whole job is
    "did the experiment arm beat the control by MARGIN_PP?", and `arm_trades`
    gated the experiment arm on the lever RECEIPT alone — proof it ran the
    candidate's BARS — while saying nothing about which ENTRY POLICY produced
    the close. The two arms do not run the same one: the shadow twin runs
    `explore_k=2` (+ scaled conviction) and the live control runs
    `explore_k=0`, so a third of the experiment arm's closes are a policy the
    control never runs.

    MEASURED post-28-Jul, the src-stamped era, both arms on one build so no
    `arm_drift` fires: shadow ALL n=113 mean -0.1711%/trade, of which
    src=exploit n=74 mean -0.0104% and src=explore n=38 mean **-0.4961%**;
    live n=73 mean -0.0368% and 72 of its 73 stamped `exploit`. The paired gap
    the judge computed was **-0.1343pp**; on src-matched subsets it is
    **+0.0264pp**. The explore bucket was a **0.161pp handicap against a
    +0.50pp margin** — 32% of the bar, charged to the experiment before it
    started.

    THIS IS NOT HYPOTHETICAL AND IT IS NOT CHEAP. The judge's ONE completed
    verdict in five weeks reads `RELEASED-OPERATOR ... 3-variable A/B (shadow
    ran explore+conviction mid-window)` — the asymmetry already destroyed a
    candidate — and the growth promoter has been parked on "shadow arm not
    positive in its own right", which is circular, because explore is what
    makes it not positive. Zero promotions to real money in five weeks, on the
    fleet's ONLY designed path to more of it.

    SYMMETRIC, so no guess is made. Both arms are restricted to the SAME src
    set, which also drops unstamped rows from both rather than assuming an
    unstamped close was exploit. FAIL-SAFE toward today's behaviour: `keep` of
    None (the control stamps nothing) filters nothing, and an empty result
    filters nothing — a bias fix that can silence the judge entirely would be
    a worse defect than the bias.
    """
    everything = arm_trades(rows, bot, start_ts, end_ts, levers=levers)
    if keep is None:
        return everything, 0
    kept = arm_trades(rows, bot, start_ts, end_ts, levers=levers,
                      keep_srcs=keep)
    if not kept:
        return everything, 0
    return kept, len(everything) - len(kept)


def _mean_pct(trades):
    return 100.0 * sum(p for _, p in trades) / len(trades) if trades else None


def paired_eval(rows, start_ts, end_ts, shadow_bot=None, live_bot=None,
                min_closes=None, live_min=None, margin_pp=None,
                cand_levers=None, drift=None, both_halves=True):
    """The promotion bar. Returns a verdict dict; verdict['promote'] is True
    only when the shadow arm is positive AND beats the live arm per-trade by
    margin_pp on the FULL window AND on BOTH halves (the doctrine's
    both-halves rule — a candidate that won one lucky week doesn't clear).

    both_halves=False drops ONLY the per-half gate (the FASTER bar the operator
    chose 25-Jul for the growth-lever pair: ~2-3d, positive + beats-live, no
    both-halves). Every other guard — arm-drift, arm-skew, the full-window
    floors, shadow-positive, and the full-window margin — is UNCHANGED, and the
    tight fade-revert is what backstops the weaker gate.

    [2026-07-16] cand_levers gates the SHADOW arm on proof-of-application: a
    close counts only if its receipt shows the arm ran the candidate's bars.
    The LIVE arm is deliberately NOT gated — it is the control running env
    defaults, and its rows predate the receipt (1 of 14 stamped), so gating it
    would starve the baseline and freeze the pipeline for good.
    """
    shadow_bot = shadow_bot or SHADOW_BOT
    live_bot = live_bot or LIVE_BOT
    min_closes = min_closes or MIN_CLOSES
    live_min = live_min or LIVE_MIN_CLOSES
    margin_pp = MARGIN_PP if margin_pp is None else margin_pp
    _keep0 = policy_srcs(rows, live_bot, start_ts, end_ts)
    sh, _sh_drop = match_policy(rows, shadow_bot, start_ts, end_ts, _keep0,
                                levers=cand_levers)
    lv, _lv_drop = match_policy(rows, live_bot, start_ts, end_ts, _keep0)
    # [2026-08-20 (sk)] COMPARE LIKE WITH LIKE — see `match_policy`. The
    # control defines the policy set; the experiment arm is restricted to it,
    # and so is the control, so the restriction is symmetric and no unstamped
    # row is guessed at. Published (`policy_match`) rather than silent: a
    # sample that shrank by a third without saying so is the same class of
    # defect this fixes.
    _keep = _keep0
    v = {"promote": False, "n_shadow": len(sh), "n_live": len(lv),
         "shadow_mean_pct": _mean_pct(sh), "live_mean_pct": _mean_pct(lv),
         "policy_match": {"keep": sorted(_keep) if _keep else None,
                          "dropped_shadow": _sh_drop, "dropped_live": _lv_drop}}
    # [2026-07-17 ARM DRIFT] The arms are running DIFFERENT CODE, so this
    # comparison contains a code delta and cannot be read as edge. Same class as
    # ARM SKEW below, and checked FIRST: skew asks "is the arm running the
    # candidate?", drift asks the prior question "are these two arms the same
    # experiment at all?". Neither is a data-volume problem — no window makes a
    # drifted comparison valid, so waiting cannot fix it.
    # WHY THIS GATE EXISTS AT ALL: the arms live in different Railway services
    # (trail-blazer-live vs funding-farmer-shadow) on separate deploy clocks —
    # and that split is DELIBERATE and must stay: the control arm's container
    # holds ZERO keys and no REAL_MONEY_KILL, so it is PHYSICALLY incapable of
    # trading real money. Merging the arms into one service to stop the drift
    # would trade that hard boundary for a soft one (a TT_VENUE string). So the
    # drift stays possible BY DESIGN — and this gate is what makes it harmless:
    # the judge refuses to spend real money on a comparison it cannot trust.
    # Build ids come from bot_pnl_store's central stamp (bytes, not a label —
    # every self-describing label in this fleet has lied).
    # Fail-safe toward SILENCE, matching the sensor: `drift` is only ever set on
    # positive evidence (two stamps, both present, both different). Unknown is
    # not drift, or this gate would freeze the queue through every rollout.
    if drift:
        v["arm_drift"] = drift
        v["why"] = (f"ARMS ON DIFFERENT CODE: live={drift.get('live')} "
                    f"shadow={drift.get('shadow')} — this window measures a "
                    f"code delta, not edge; no promotion can rest on it")
        return v
    if cand_levers:
        # ARM SKEW: the arm closed trades in-window but proved NONE of them ran
        # the candidate. Distinct from "not enough data yet" — the experiment
        # is not running at all, so no window will ever make it valid. Caller
        # must NOT age this toward ABANDONED (that would retire a possibly-good
        # candidate on a verdict about an experiment that never happened).
        n_all = len(arm_trades(rows, shadow_bot, start_ts, end_ts))
        v["n_shadow_closes"] = n_all
        if n_all and not sh:
            v["arm_skew"] = True
            v["why"] = (f"ARM NOT APPLYING: 0/{n_all} shadow closes carry a "
                        f"receipt for {json.dumps(cand_levers)} — the arm is "
                        f"not running this experiment")
            return v
    if len(sh) < min_closes or len(lv) < live_min:
        v["why"] = f"floors: shadow {len(sh)}/{min_closes}, live {len(lv)}/{live_min}"
        return v
    mid = start_ts + (end_ts - start_ts) / 2.0
    # [2026-07-16] per-half sample floors. The full-window floors said nothing
    # about the halves, so ONE live trade in a half set that half's entire
    # baseline and the both-halves rule — the doctrine's central noise filter —
    # degenerated into a noise amplifier on the exact comparison that moves
    # real money. Floors derive from the effective window floors (env-tunable
    # via the same XPJ_* knobs), so an even split of exactly-at-floor data
    # still clears; a lopsided one holds until the thin half fills in.
    # [(vm)] ONE owner for these two numbers — `half_floors`. They were typed
    # here and the power report retyped the FULL-WINDOW pair instead, so the
    # published MDE described a rung the bar does not use.
    half_sh_min, half_lv_min = half_floors(min_closes, live_min)
    for a, b, label in (((start_ts, mid, "h1"), (mid, end_ts, "h2")) if both_halves else ()):
        # [(sk)] the halves take the SAME policy match as the full window.
        # Caught by the fix's own fixture: matching only the full window left
        # the both-halves gate — the doctrine's central noise filter — reading
        # the biased sample, so a candidate could clear the window bar and be
        # failed by a half that still counted the control's off-policy closes.
        # A half-applied bias fix is worse than none: it looks corrected.
        sh_h = arm_trades(rows, shadow_bot, a, b, levers=cand_levers,
                          keep_srcs=_keep)
        lv_h = arm_trades(rows, live_bot, a, b, keep_srcs=_keep)
        if _keep is not None and not sh_h:
            # same fail-safe as the full window: never let the match starve a
            # half into a verdict about missing data
            sh_h = arm_trades(rows, shadow_bot, a, b, levers=cand_levers)
            lv_h = arm_trades(rows, live_bot, a, b)
        if len(sh_h) < half_sh_min or len(lv_h) < half_lv_min:
            v[label] = {"shadow_n": len(sh_h), "live_n": len(lv_h)}
            v["why"] = (f"{label} under-powered: shadow {len(sh_h)}/"
                        f"{half_sh_min}, live {len(lv_h)}/{half_lv_min}")
            return v
        shm = _mean_pct(sh_h)
        lvm = _mean_pct(lv_h)
        v[label] = {"shadow": shm, "live": lvm}
        # [2026-07-16 AUDIT FIX] each half must clear the SAME margin as the
        # full window — `shm > lvm` by any amount let one half's edge be pure
        # noise (+0.01pp), which is the lucky-half pattern this bar exists to
        # reject before real money moves.
        if shm is None or lvm is None or (shm - lvm) < margin_pp:
            v["why"] = (f"{label}: shadow {shm} vs live {lvm} — edge < margin "
                        f"{margin_pp}pp on this half")
            return v
    full_gap = v["shadow_mean_pct"] - v["live_mean_pct"]
    v["gap_pp"] = round(full_gap, 3)
    if v["shadow_mean_pct"] <= 0:
        v["why"] = "shadow arm not positive in its own right"
        return v
    if full_gap < margin_pp:
        v["why"] = f"gap {full_gap:.2f}pp < margin {margin_pp}pp"
        return v
    v["promote"] = True
    v["why"] = (f"shadow beats live by {full_gap:.2f}pp/trade over the window "
                f"AND both halves (n={len(sh)} vs {len(lv)})")
    return v


def fade_check(rows, promoted_ts, now, live_bot=None, fade_n=None,
               baseline_pct=None, margin_pp=None):
    """True when the promoted lever is measured HURTING the live arm.

    [2026-07-16] Two release bars; either trips (restrict-only — an extra
    release path can only ever pull a lever OFF real money, never keep one on):

      ABSOLUTE — recent live mean < 0 (the original bar).
      RELATIVE — recent live mean has fallen >= margin_pp below the arm's own
        PRE-promotion baseline (the paired window's live mean, stamped into
        state at PROMOTE). The old bar was absolute-only: a lever that cut
        live from +0.80%%/trade to +0.10%% destroyed the promoted edge without
        inverting the sign and could stay in force forever. The promotion bar
        is relative (+margin vs live); the release bar must be too.

    Both bars run on the ROLLING last fade_n closes, not the cumulative mean
    since promotion — the cumulative mean converges toward its early value as
    n grows, so a LATE fade became mathematically unreachable.

    Fail-safe: fewer than fade_n closes -> no release signal here (the lever
    TTL + the blind-cycle guard remain the backstop); missing/invalid baseline
    -> absolute bar only, exactly the historical behaviour.
    """
    lv = arm_trades(rows, live_bot or LIVE_BOT, promoted_ts, now)
    k = int(fade_n or FADE_N)
    if len(lv) < k:
        return False, len(lv), _mean_pct(lv)
    m = _mean_pct(lv[-k:])
    if m is None:
        return False, len(lv), m
    if m < 0:
        return True, len(lv), m
    mp = MARGIN_PP if margin_pp is None else float(margin_pp)
    try:
        if baseline_pct is not None and m < float(baseline_pct) - mp:
            return True, len(lv), m
    except (TypeError, ValueError):
        pass
    return False, len(lv), m


def prop_fade(prop_state, live_levers, now):
    """[2026-07-16 evening, operator: 'the live lane needs to learn'] The
    EARLIER fade signal: fleet_proprioception grades every live.funding.*
    episode per-trade against the live arm's own pre-window AND the shadow
    twin; a fresh HURTING verdict on a promoted lever means the promotion
    is measurably underperforming BOTH baselines — release it before the
    absolute fade bar (live mean < 0 at n>=FADE_N) is even reached. The
    judge stays the ONLY writer of live.funding.*; proprioception is
    evidence in, never a hand on the lever. Fail-safe False on a dark/
    stale/absent organ. Returns (fading, why). Pure — selftested."""
    try:
        upd = parse_ts((prop_state or {}).get("updated"))
        if now - upd > float(prop_state.get("ttl_sec") or 0):
            return False, None
        for k in sorted(live_levers or ()):
            v = (prop_state.get("verdicts") or {}).get(k)
            if isinstance(v, dict) and v.get("verdict") == "hurting":
                return True, (f"proprioception: {k} graded HURTING "
                              f"(bad {v.get('bad')}/{v.get('n')} episodes vs "
                              f"pre-window + shadow twin)")
    except Exception:
        return False, None
    return False, None


# [2026-07-21b] proposal_fade's release-direction safety: releasing a
# promotion reverts the lever to the OPERATOR'S ENV DEFAULT, so a release is
# only a RESTRICT outcome when that default is tighter-or-equal than the
# promoted value. Orientation: 'up' = higher is tighter (an entry bar),
# 'down' = lower is tighter (an exposure/hold cap). Values are the fleet's
# documented live defaults (FUNDING_ENTER_APR 0.05 TRUE / TP 0.04 / 72h) —
# the registry notes carry the same numbers.
# [2026-07-23 AUDIT] This is a HARDCODED COPY of the live funding bot's env
# defaults (the judge runs in a different process and can't read that service's
# env at runtime). A selftest drift guard pins these to the funding bot's SOURCE
# defaults so they can't diverge in CODE. But a per-service ENV OVERRIDE (e.g.
# the operator setting FUNDING_MAX_HOLD_H=96 on the live service) is INVISIBLE
# here — if you set one, update this dict too, or proposal_fade's restrict-only
# guarantee (release only when reverting TIGHTENS) can be defeated on that lever.
LIVE_ENV_DEFAULTS = {"live.funding.enter_apr": (0.05, "up"),
                     "live.funding.take_profit": (0.04, "down"),
                     "live.funding.max_hold_h": (72.0, "down"),
                     # [2026-07-28] the growth pair + slope gate join the map
                     # so the organ release paths (prop_fade/proposal_fade)
                     # can reach every promotable live.funding.* lever —
                     # before this, a promoted growth pair had NO organ
                     # early-release (unmapped lever: "never release on a
                     # guess"). Releasing tightens by construction: env
                     # defaults are 0 explore slots (SCAN_EXPLORE_K "0"),
                     # conviction OFF (FUNDING_CONVICTION "off" -> hi 1.0),
                     # slope gate ON (FUNDING_SLOPE_GATE "on" -> 1).
                     "live.funding.explore_k": (0.0, "down"),
                     "live.funding.conviction_hi": (1.0, "down"),
                     "live.funding.slope_gate": (1.0, "up"),
                     # [2026-08-05 (jy)] min_vol joins with promotability:
                     # env default $10M, HIGHER floor = tighter, so a
                     # release of a promoted (lowered) floor tightens by
                     # construction. Selftest pins XP_TO_LIVE's live twins
                     # to THIS map — a promotable lever with no organ
                     # release path can no longer arrive silently.
                     "live.funding.min_vol": (10000000.0, "up"),
                     # [(wv)] 👩 mum's twins: a LOWER rsi bar admits fewer
                     # entries (tighter = down); a SHORTER hold is tighter
                     # (down). Env defaults from lighter_family_bot's class.
                     "live.mum.rsi_max": (36.0, "down"),
                     "live.mum.max_hold_min": (1440.0, "down")}


def proposal_fade(proposals, live_levers, now):
    """[2026-07-21 ORGAN PROPOSALS, operator: organs must "implement changes
    to forward onto the tuners to act on"] The organs' release path: a fresh
    RESTRICT-direction proposal (fleet_proposals) on a promoted live lever —
    e.g. implementation-shortfall measuring sustained live slip — is an
    organ's measured case against the promotion, so release it early rather
    than ride the lever to the absolute fade bar.

    [2026-07-21b AUDIT FIX, caught same-day] restrict-only now holds in
    OUTCOME, not just intent: releasing a promoted TIGHTENING (e.g. the
    re-spec'd enter-gate 0.075 vs the 0.05 env default) would WIDEN the
    live gate on 'restrict' evidence — exactly backwards. `live_levers` is
    now the {name: promoted_value} dict and a proposal releases only when
    reverting to the env default moves the lever in the tighter direction
    (LIVE_ENV_DEFAULTS). The judge stays the ONLY writer of live.funding.*;
    a proposal is evidence in, never a hand on the lever. Fail-safe False
    on an empty/dark channel or an unmapped lever. Pure — selftested."""
    try:
        for p in proposals or []:
            name = p.get("lever")
            if name not in (live_levers or {}) or p.get("direction") != "restrict":
                continue
            ref = LIVE_ENV_DEFAULTS.get(name)
            if ref is None:
                continue        # unmapped lever: never release on a guess
            default, tighter = ref
            promoted_v = float(live_levers[name])
            release_tightens = (default >= promoted_v if tighter == "up"
                                else default <= promoted_v)
            if not release_tightens:
                continue        # releasing would WIDEN — refuse
            return True, (f"organ proposal: {p.get('set_by')} proposes "
                          f"restrict {name} "
                          f"({str(p.get('reason') or '')[:120]})")
    except Exception:
        return False, None
    return False, None


# ---------------------------------------------------------------------------

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send_push(title, body, priority="default"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", "test_tube")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[xp-judge] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def _assert_levers(levers, reason, evidence):
    return tuning.write_levers(
        {k: {"value": v, "reason": reason[:180], "evidence": evidence[:280]}
         for k, v in levers.items()},
        set_by="experiment-judge", ttl_sec=LEVER_TTL)


def _asserted(rc, levers):
    """[2026-07-16] Did the rail write actually LAND? write_levers returns the
    payload written, or None when nothing valid survived (unknown lever,
    out-of-lane, clamp reject, no DB) — documented as never raising. Every
    call site used to discard that return, so a silently-dropped write left
    the judge counting days toward promotion on an experiment it never
    asserted, and could stamp phase=promoted while no live lever was in
    force. Pure — selftested."""
    got = (rc or {}).get("levers") or {}
    return bool(levers) and all(k in got for k in levers)


def _lever_sig(levers):
    """A candidate's IDENTITY: the experiment it actually runs, not its name.
    Values are floated so 48 and 48.0 are one experiment. Never raises — a
    non-numeric value keeps its raw form rather than sinking the whole pool."""
    out = []
    for k in sorted(levers or {}):
        v = levers[k]
        try:
            v = float(v)
        except (TypeError, ValueError):
            pass
        out.append((k, v))
    return tuple(out)


def candidate_pool(queue, now=None):
    """The static CANDIDATES followed by fresh incubator proposals from
    'xp-queue', deduped by name AND by LEVER SIGNATURE (static wins). Only
    proposals whose levers are all registered xp.funding.* are admitted — an
    offspring can't smuggle an unknown lever past the judge. Pure — selftested.

    [2026-07-28 REVIEW] The queue is consumed ONLY while fresh by its own
    `updated`+`ttl_sec` — the same payload-self-TTL check prop_fade already
    does, fail-CLOSED on a missing/unparseable stamp (the fleet bus contract:
    consumers go neutral on stale). Found live: the judge was consuming an
    11-day-stale queue (updated 17-Jul, ttl 3h) whose enter_apr-0.3/-0.5
    entries the 23-Jul Lighter tape sweep had since refuted — each would have
    clamped to 0.075 and burned a >=7d serial slot re-running the identical
    experiment, plus the withdrawn hold-48/-96 pair: ~4 wasted slots (~a
    month) on the fleet's only path to live.funding.*. Restrict-only: a stale
    queue contributes zero candidates; the statics are untouched. Publisher
    side (incubator republish-while-endorsed) is flagged in
    FLEET_REVIEW_2026-07-28.md — this is the consumer's half of the contract.

    [2026-07-17 AUDIT] Signature dedup added. Name dedup ALONE was vacuous
    here: the incubator mints its own namespace (`xp-<gene>-<allele>`,
    strategy_incubator.py:517) which can never collide with a static name, so
    three of its six cycle-1 proposals were byte-identical experiments to the
    three statics wearing different names — and `done`/`next_candidate` are
    name-based, so each one bought a SECOND >=7d slot on a SERIAL pipeline
    that is the fleet's only path to live.funding.*. Measured: pool of 9 =
    6 distinct experiments + 3 duplicates = >=21 wasted judge-days.
    The old selftest missed it because its dup fixture re-used a static NAME
    — the one shape the incubator never emits (see the negative fixture in
    _selftest). Dedup on identity, not on label. Restrict-only: this can only
    REMOVE a candidate that some earlier pool entry already tests."""
    pool, seen, sigs = [], set(), set()
    for c in CANDIDATES:
        pool.append(c)
        seen.add(c["name"])
        sigs.add(_lever_sig(c["levers"]))
    q = queue or {}
    try:
        _now = (datetime.now(timezone.utc).timestamp()
                if now is None else float(now))
        if _now - parse_ts(q.get("updated")) > float(q.get("ttl_sec") or 0):
            return pool                     # stale queue: statics only
    except Exception:                       # noqa: BLE001
        return pool                         # unstampable queue: fail closed
    for c in q.get("candidates", []):
        nm, lv = c.get("name"), c.get("levers") or {}
        if not nm or nm in seen:
            continue
        # [(wv)] and ONLY this lane's prefix — a funding offspring in the
        # queue must not burn a serial slot on 👩 mum's lane.
        _pfx = lane_prefix()
        if lv and all(k in XP_TO_LIVE and str(k).startswith(_pfx) for k in lv):
            sig = _lever_sig(lv)
            if sig in sigs:
                continue          # same experiment, different label
            pool.append({"name": nm, "levers": lv})
            seen.add(nm)
            sigs.add(sig)
    return pool


def next_candidate(pool, done, current):
    """First pool candidate not already completed and not the current one.
    Name-based so the pool may GROW (incubator appends) without reindexing.
    Pure — selftested."""
    done = set(done or [])
    for c in pool:
        if c["name"] not in done and c["name"] != current:
            return c
    return None


def pick_candidate(pool, done, done_at, current, now, retry_sec):
    """[2026-07-17 IMB-07] (candidate, retried) — untried candidates FIRST,
    always; a done entry aged past retry_sec is retry-eligible ONLY when
    nothing untried remains. Plain aging was verify-refuted: the statics
    sit ahead of offspring in pool order and rotate (~16d per failed slot)
    slower than the retry window, so an aged static would be re-selected
    ahead of every NEVER-tried offspring, forever — the fallback shape
    starves nothing. Pure — selftested."""
    cand = next_candidate(pool, done, current)
    if cand is not None:
        return cand, False
    aged = {n for n in (done or [])
            if now - (done_at or {}).get(n, now) >= retry_sec}
    if not aged:
        return None, False
    cand = next_candidate(pool, [n for n in done if n not in aged], current)
    return cand, cand is not None


def _num(x, d=0.0):
    """Corrupt/legacy state fields must reset the judge, never crash-loop it."""
    try:
        return float(x)
    except Exception:
        return d


def _needs_reset(phase, current, spec):
    """True when the judge is mid-experiment (running/promoted) but the stored
    spec is missing or mismatched — e.g. state written by the old index-based
    code before the 16-Jul name-based refactor. `levers` must be a non-empty
    dict ({"levers": None} passed the old `in` check and crashed downstream).
    Pure — selftested."""
    if phase not in ("running", "promoted"):
        return False
    if not (current and isinstance(spec, dict) and spec.get("name") == current
            and isinstance(spec.get("levers"), dict) and spec.get("levers")):
        return True
    # a persisted spec whose lever was dropped from XP_TO_LIVE would KeyError
    # at promotion time — treat it as invalid state, not a crash-loop
    return any(k not in XP_TO_LIVE for k in spec["levers"])


def _respec_clamped(cand, clamp=None):
    """[2026-07-21 REVIEW D2/N2] A RUNNING candidate whose stored lever values
    differ from their registry clamp is running a DIFFERENT experiment than its
    spec claims. MEASURED live: `enter-gate-0.30` (a gate WIDENING, 0.30
    pre-basis-fix units) kept asserting 0.30 into the re-denominated registry
    (hi=0.075), the write clamped to 0.075 TRUE — a gate TIGHTENING — and the
    arm's receipts stamped 0.075 while ran_candidate demanded 0.30, so the
    skew gate excluded EVERY close since 17-Jul: 20 valid-receipt closes,
    zero accrued, an experiment that could never finish under a name that
    lied about its direction.

    Returns (cand', changed) where changed maps lever -> (stored, clamped);
    {} means no re-spec needed. The caller restarts the window (started_ts) —
    pre-clamp closes must not mix into the paired bar — and the new name
    carries the truth. An unclampable lever returns unchanged: _needs_reset /
    the INVALID path own that failure, not this migration. Pure — selftested."""
    clamp = clamp or tuning.clamp
    levers = cand.get("levers") or {}
    clamped, changed = {}, {}
    for k, v in levers.items():
        cv = clamp(k, v)
        if cv is None:
            return cand, {}
        clamped[k] = cv
        try:
            if abs(float(cv) - float(v)) > 1e-9:
                changed[k] = (v, cv)
        except (TypeError, ValueError):
            return cand, {}
    if not changed:
        return cand, {}
    new_name = (str(cand.get("name")) + "@"
                + ",".join(f"{k.split('.')[-1]}={clamped[k]:g}"
                           for k in sorted(changed)))
    return {**cand, "name": new_name, "levers": clamped}, changed


# --- Growth-lever promoter (Farmer explore + conviction) — the FASTER path ----
# [2026-07-25] The operator's 2-3d auto-promotion for the two growth levers,
# promoted as a PAIR and released together. Self-contained (NOT the one-at-a-time
# xp queue): the shadow runs both levers via its OWN env, always on, so this
# compares the shadow arm (levers on) vs the live arm (env-default off) on the
# FASTER bar (both_halves=False). Still receipt-gated on the shadow (fail-CLOSED:
# no promotion until the shadow's closes PROVE they ran the levers via extra.bars),
# arm-drift-gated (same as every promotion), and TTL-asserted so a fade OR a dark
# ledger reverts to env within LEVER_TTL. The tight fade-revert backstops the
# weaker bar. The judge stays the SOLE writer of live.funding.*.
GROWTH_CAND = {"xp.funding.explore_k": 2, "xp.funding.conviction_hi": 2.2}
GROWTH_LIVE = {"live.funding.explore_k": 2, "live.funding.conviction_hi": 2.2}
GROWTH_WINDOW_D = float(os.environ.get("XPJ_GROWTH_DAYS", "2.5"))
GROWTH_MIN_CLOSES = int(os.environ.get("XPJ_GROWTH_MIN_CLOSES", "15"))
GROWTH_LIVE_MIN = int(os.environ.get("XPJ_GROWTH_LIVE_MIN", "10"))
# [2026-07-28 AUDIT FIX] post-release cooldown — the main pipeline stamps
# COOLDOWN_H after every FADED/ABANDONED for exactly this reason: without
# it, a fade release (rolling live mean < 0) followed by a trailing-window
# bar that still clears is an hourly promote/release oscillation, each
# promote re-steering real money. Same default as the main path.
GROWTH_COOLDOWN_H = float(os.environ.get("XPJ_GROWTH_COOLDOWN_H", "48"))


GROWTH_REACH_LOOKBACK_D = float(os.environ.get("XPJ_GROWTH_REACH_LOOKBACK_D", "14"))


def growth_reachable(rows, now, window_d=None, min_closes=None,
                     lookback_d=None, shadow_bot=None):
    """(reachable, detail) — can the shadow arm even PRODUCE `min_closes`
    inside a `window_d` trailing window, at its OWN recent close rate?

    [2026-07-29] WHY THIS EXISTS. The growth pair's faster bar is 15 shadow
    closes in a 2.5d trailing window — a spec that silently encodes an assumed
    ~6 closes/day. Measured on 29-Jul the Farmer's shadow arm was closing
    ~1.6/day (4 in 2.5d, 19 in 7d, 58 in 14d), so the floor could not be met
    and `last_growth` had been printing "floors: shadow N/15" indefinitely with
    nothing distinguishing "not yet" from "not ever". That is the failure shape
    this fleet keeps paying for: a gate whose bar sits on an unmeasured
    assumption ([[unmeasured-assumptions-make-false-verdicts]]).

    This REPORTS; it does not gate. Deliberately so — the 2.5d window is a
    recorded operator preference ("the operator's 2-3d auto-promotion"), and
    an organ must not quietly widen a real-money promotion window to make its
    own bar easier. Surfacing the arithmetic is what lets the operator decide
    whether to widen the window, accept the stall, or feed the arm.

    Fail-safe: returns (None, ...) — UNKNOWN, never a stall claim — on a
    missing/short ledger, so a dark feed can never manufacture an alarm
    ([[a-dead-sensor-must-not-score-a-hit]]). The projection is deliberately
    OPTIMISTIC (ungated by the candidate receipt the real floor also demands),
    so `reachable is False` means *definitely* not, never merely 'probably'.
    Pure — selftested."""
    window_d = GROWTH_WINDOW_D if window_d is None else window_d
    min_closes = GROWTH_MIN_CLOSES if min_closes is None else min_closes
    lookback_d = GROWTH_REACH_LOOKBACK_D if lookback_d is None else lookback_d
    shadow_bot = shadow_bot or SHADOW_BOT
    seen = arm_trades(rows, shadow_bot, now - lookback_d * 86400, now)
    n = len(seen)
    detail = {"n_lookback": n, "lookback_d": lookback_d,
              "window_d": window_d, "min_closes": min_closes}
    if n < 2:
        detail["why"] = "no usable close-rate sample — claiming nothing"
        return None, detail
    rate = n / float(lookback_d)
    projected = rate * window_d
    detail.update(rate_per_day=round(rate, 3), projected=round(projected, 2))
    detail["why"] = (f"{shadow_bot} closes ~{rate:.2f}/day over the last "
                     f"{lookback_d:g}d -> ~{projected:.1f} in a {window_d:g}d "
                     f"window vs a {min_closes}-close floor")
    return projected >= min_closes, detail


def growth_promoter(rows, gstate, now, drift=None):
    """Promote/keep/release the growth-lever PAIR on the faster bar. PURE: returns
    (new_gstate, (kind, payload)); the caller does the _assert_levers / push / log
    and persists gstate. kind in {'promote','reassert','release','eval'}."""
    gstate = dict(gstate or {})
    if gstate.get("promoted"):
        pts = float(gstate.get("promoted_ts") or now)
        fading, n, m = fade_check(rows, pts, now, live_bot=LIVE_BOT,
                                  baseline_pct=gstate.get("baseline_pct"))
        if fading:
            return ({"promoted": False, "released_ts": now, "release_mean": m,
                     "cooldown_until": now + GROWTH_COOLDOWN_H * 3600},
                    ("release", {"why": f"fade: live rolling mean {m}%/trade (n={n})",
                                 "levers": list(GROWTH_LIVE)}))
        return (gstate, ("reassert", {"levers": GROWTH_LIVE, "n": n, "mean": m}))
    # [2026-07-28] post-release cooldown: a freshly-released pair must not
    # re-clear on the same trailing window that just faded — the main
    # pipeline's COOLDOWN_H rule, mirrored.
    if _num(gstate.get("cooldown_until")) > now:
        return (gstate, ("eval", {"promote": False,
                                  "why": f"release cooldown until "
                                         f"{iso(_num(gstate['cooldown_until']))}"}))
    start = growth_window_start(now)
    v = paired_eval(rows, start, now, shadow_bot=SHADOW_BOT, live_bot=LIVE_BOT,
                    min_closes=GROWTH_MIN_CLOSES, live_min=GROWTH_LIVE_MIN,
                    cand_levers=GROWTH_CAND, drift=drift, both_halves=False)
    v["candidate"] = "growth-levers"
    if v.get("promote"):
        return ({"promoted": True, "promoted_ts": now,
                 "baseline_pct": v.get("live_mean_pct"), "gap_pp": v.get("gap_pp")},
                ("promote", {"levers": GROWTH_LIVE, "why": v["why"], "ev": v}))
    return (gstate, ("eval", v))


_UNSET = object()


def growth_window_start(now):
    """The growth pair's trailing window start — ONE definition.

    Read by growth_promoter (the bar) and by the drift scoping at the call
    site, so the two can never disagree about which closes are in-window.
    A second copy of this expression would be a second rule (the (hj) class).
    """
    return now - GROWTH_WINDOW_D * 86400


def _rows_since(rows, since_ts):
    """`rows` restricted to closes at-or-after `since_ts` — the SAME filter
    arm_trades applies to build the bar.

    An unparseable stamp is EXCLUDED, matching arm_trades' own `continue`:
    a row the bar cannot place in time is a row the drift check must not
    place either, and the sensor's declared direction is silence.
    """
    if since_ts is None:
        return rows
    out = []
    for r in rows or []:
        try:
            if parse_ts(r.get("close_ts")) >= since_ts:
                out.append(r)
        except Exception:      # noqa: BLE001
            continue
    return out


def _row_build_sets(rows, live=None, shadow=None):
    """{bot: set(build ids)} over the rows given, ignoring unstamped rows."""
    live, shadow = live or LIVE_BOT, shadow or SHADOW_BOT
    out = {live: set(), shadow: set()}
    for r in rows or []:
        b = str(r.get("bot"))
        if b in out:
            bid = ((r.get("extra") or {}) or {}).get("build")
            if bid:
                out[b].add(str(bid))
    return out


def _row_drift(rows, live=None, shadow=None):
    """The ROW half: did this window's two samples come from DISJOINT code?

    [2026-08-06 (lf)] THIS REPLACES A NEWEST-vs-NEWEST COMPARISON THAT WAS
    UNSOUND AT ANY WINDOW WIDTH. `implementation_shortfall.arm_drift` keeps one
    row per bot — for `bot_pnl` that is right (one row per bot, describing NOW),
    but for a LEDGER it compares each arm's newest close, and two "newest"
    closes are two DIFFERENT MOMENTS. Across a rolling deploy the faster-closing
    arm publishes a post-deploy close while the slower one's newest is still
    pre-deploy, and the sensor calls that "ARMS ON DIFFERENT CODE".

    MEASURED 6-Aug, and this is why `(la)`'s window scoping was only half a fix:
    on the SERIAL window (opened 06:29Z, after the 06:06/06:22Z deploys) the
    stale live close fell outside and the hold cleared — but the GROWTH window
    is 2.5 DAYS, wide enough to straddle any deploy, so the scoped verdict was
    byte-identical to the unscoped one. Production carried
    "ARMS ON DIFFERENT CODE" on five consecutive samples AFTER the fix landed,
    holding a growth bar whose floors were BOTH met (shadow 15/15, live 11/10),
    while `bot_pnl` had both containers on the same build.

    THE SOUND QUESTION IS ABOUT SETS, NOT ENDPOINTS. If the arms' in-window
    build sets INTERSECT they tracked the same deploy sequence and the
    difference is TIMING; only DISJOINT sets mean the two samples were really
    produced by different code with no overlap. Measured on that same tape:
    live {f27e50d805af, 6ff86f4d6b09} vs shadow {f27e50d805af, 6ff86f4d6b09,
    4f998e4eec4d} — a two-build intersection, i.e. not drift.

    RESTRICT-ONLY and fail-safe toward SILENCE, unchanged: a claim needs BOTH
    arms to have stamped rows in the window (an empty set on either side is
    "unknown", never drift), so a rollout cannot make this fire.
    """
    sets = _row_build_sets(rows, live, shadow)
    a, b = sets[live or LIVE_BOT], sets[shadow or SHADOW_BOT]
    if not a or not b:
        return None                      # unknown is not drift
    if a & b:
        return None                      # shared build => same deploy line
    return {"live": sorted(a)[-1], "shadow": sorted(b)[-1],
            "source": "rows-disjoint"}


def _current_drift(fetch=None):
    """The CONTAINER half: are the arms running different code right NOW?

    One reading per cycle by construction — it describes a single moment and
    both consumers ask it the same question. Split out of
    _arm_drift_snapshot so the row half can be scoped per-window without
    re-fetching bot_pnl per consumer."""
    try:
        import implementation_shortfall as _isf
    except Exception:      # noqa: BLE001
        return None
    try:
        pnl_rows = (fetch or store.fetch_bot_pnl)() or []
        cur = _isf.arm_drift(pnl_rows, live=LIVE_BOT, shadow=SHADOW_BOT)
        return dict(cur, source="bot_pnl-current") if cur is not None else None
    except Exception:      # noqa: BLE001
        return None


def _arm_drift_snapshot(rows, fetch=None, since_ts=None, current=_UNSET):
    """Arm-drift for paired_eval: EITHER source may raise a hold, neither clears.

    [2026-07-28 REVIEW] The row-based check was structurally DARK from birth:
    0 of 143 all-time Farmer paper_trades rows carried extra.build, because
    publish_paper_trade never stamped it (fixed today in bot_pnl_store,
    forward-only) — so arm_drift returned None on every eval while
    impl-shortfall's bot_pnl read simultaneously reported the two arms on
    different builds. A drift gate that cannot fire is a dead sensor
    ([[a-dead-sensor-must-not-score-a-hit]]): the 2026-07-17 "one snapshot"
    design was right, its feed was empty.

    Semantics (2026-07-29 — the seniority rule that used to sit here is GONE):
    - The row-based check runs first and a POSITIVE row verdict is returned
      as-is: those rows really were produced by two different builds.
    - A row verdict of None no longer ends it. The arms' CURRENT bot_pnl
      builds are always consulted, and a positive verdict there raises the
      hold too (stamped `source: bot_pnl-current`). WHY the reversal: the old
      "both arms stamped => row verdict final" rule certified the Farmer pair
      CONVERGED on ddd019900bf0 on 29-Jul while the containers were actually
      running c2d0ccc64d7d and 89c2c56b2da5. The rows described the past
      honestly; the promotion they gated spends money through the code running
      NOW ([[self-describing-labels-lie]] — except build ids are bytes, so the
      stamps were true and only the RULE reading them was wrong).
    - Both sources claim drift only on POSITIVE evidence (two stamps present
      and different), so this is RESTRICT-ONLY: it can add a hold, never clear
      one, and "unknown" stays quiet (it must — treating unknown as drift
      would fire on every rollout and train the operator to ignore it).
      Fail-safe None on any import/DB failure (a dark sensor claims nothing).

    [2026-08-06 THE ROW HALF IS WINDOW-SCOPED — `since_ts`.] The 17-Jul
    "same snapshot" note above claimed the drift check and the bar it gates
    "can never describe different moments" because both read the same `rows`.
    Same OBJECT, different SAMPLE: the bar filters to [start, now] via
    arm_trades and the row check read the whole ledger, so it compared each
    arm's NEWEST close whenever that was — routinely outside the window.
    MEASURED 6-Aug: both Farmer deploys landed 06:06/06:22Z and the candidate
    window opened 06:29Z with n_live=0, yet the row check compared the live
    arm's 02:06Z close (build 6ff86f4d6b09, pre-deploy) against the shadow's
    07:01Z close (4f998e4eec4d) and raised a HOLD — while bot_pnl had BOTH
    containers on 4f998e4eec4d. Every row that could enter that bar was
    post-deploy and converged. The cost was not cosmetic: it held the
    real-money promotion pipeline and fired an urgent push telling the
    operator to "deploy both arms to the same build" when they already
    matched (the (ht)/I8 class — a detector naming an act already taken),
    and the recovery branch then RESTARTS the experiment clock, so any
    deploy cost the window its accrued days even when the window was clean.
    Scoping the row half loses nothing: if the CONTAINERS disagree the
    current half still holds, and pre-window rows can never reach the bar.
    `since_ts=None` keeps the whole-ledger behaviour for callers with no
    window (the selftest).

    `fetch` is injectable for the selftest; defaults to store.fetch_bot_pnl.
    `current` is the pre-computed container half (_current_drift), hoisted so
    one cycle takes one bot_pnl reading however many windows it scopes."""
    try:
        import implementation_shortfall as _isf
    except Exception:      # noqa: BLE001
        return None
    try:
        # [(lf)] SET-DISJOINTNESS, not newest-vs-newest — see _row_drift. The
        # window scoping stays (the bar's sample is what a row claim is about),
        # but it is no longer load-bearing on its own: a 2.5-day window
        # straddles any deploy, and that is exactly where (la) was inert.
        d = _row_drift(_rows_since(rows, since_ts))
        if d is not None:
            return d
        if current is not _UNSET:
            return current

        # [2026-07-29] The row verdict is no longer FINAL-on-converged, and the
        # reason is a measured live state, not a theory. The old rule said: if
        # both arms have build-stamped rows, a None from them means converged —
        # skip the bot_pnl fallback (the "same-snapshot doctrine"). Measured
        # today: both arms' NEWEST stamped rows carried ddd019900bf0 (28-Jul
        # 20:00/20:02) while bot_pnl showed the arms live on c2d0ccc64d7d and
        # 89c2c56b2da5 — TWO DIFFERENT builds, NEITHER of them the one the gate
        # was certifying as converged. The seniority rule is right about the
        # PAST (those rows really were produced by one build) and wrong about
        # the DECISION: a promotion steers FUTURE real money through the code
        # the containers are running NOW. So the current-build check is always
        # consulted, and either source may raise a hold.
        # RESTRICT-ONLY by construction: arm_drift claims only on POSITIVE
        # evidence (two stamps present, two stamps different), so this can add
        # a hold and never clear one, and "unknown" stays quiet exactly as
        # before (it must — see the docstring on why unknown != drift).
        return _current_drift(fetch)
    except Exception:      # noqa: BLE001
        return None


def growth_step(gstate, rows, have_ledger, now, drift=None,
                assert_fn=None, asserted_fn=None, push=None,
                prop_state=None, proposals=None, serial_phase=None):
    """[2026-07-28 §3c] The growth-lever pair's cycle glue — the run_once
    wiring growth_promoter was committed without (53c7e8c shipped the promoter
    with its only callers in its own selftest; the 28-Jul review §3c mapped
    this exact arming chain). PURE apart from the injected effects
    (assert_fn/push default to the real rail + phone): returns
    (new_gstate, last_growth); the caller persists new_gstate under
    st['growth'].

    Discipline mirrors the main pipeline branch-for-branch:
    - the promotion IS the write — a promote whose live-lever write does not
      land keeps the OLD (unpromoted) gstate so the bar re-evaluates next
      cycle, pushes once per episode, and stamps nothing;
    - reassert failure is fail-safe (the lever TTL-expires back to env
      defaults) but never SILENT — one urgent push per episode;
    - release pushes once (growth_promoter emits it only on the transition);
    - a DARK LEDGER asserts nothing: the standing promotion stops
      re-asserting immediately and the live lever expires within LEVER_TTL —
      exactly the "a fade OR a dark ledger reverts to env within LEVER_TTL"
      contract in the promoter's design block (deliberately TIGHTER than the
      main path's BLIND_MAX: the faster bar earns less trust).
    All promotion gates (receipts fail-closed, arm-drift, floors) live in
    growth_promoter/paired_eval and are unchanged — this function only
    carries verdicts to the rail. The judge stays the sole writer of
    live.funding.*."""
    assert_fn = assert_fn or _assert_levers
    asserted_fn = asserted_fn or _asserted
    push = push or send_push
    gstate = dict(gstate or {})
    if not have_ledger:
        return gstate, {"kind": "dark",
                        "why": "no ledger — asserting nothing (fail-safe)"}
    g2, (kind, pay) = growth_promoter(rows, gstate, now, drift=drift)
    if kind in ("promote", "reassert") and prop_state is None:
        # resolve the organ evidence once: the promote path consults it
        # BEFORE steering real money, the reassert path for early release
        try:
            prop_state = store.load_state("fleet-proprioception") or {}
        except Exception:      # noqa: BLE001
            prop_state = {}
    if kind == "promote":
        # [2026-07-29 AUDIT F1] promote HELD while the SERIAL pipeline is
        # mid-candidate. The growth window compares shadow-vs-live on a
        # rolling 2.5d read, and a running serial candidate changes the
        # shadow arm's config INSIDE that window — the same multi-variable
        # confound the operator released the 0.075 candidate over (D3):
        # `ran_candidate` subset-matches the growth levers and cannot see
        # the extra lever. Evaluation continues every cycle (last_growth
        # stays honest) and reassert/fade/organ-release above/below are
        # untouched — only the WRITE that steers real money waits for a
        # clean window. Fail-safe: unknown/absent phase promotes normally.
        if serial_phase == "running":
            return gstate, {"kind": "eval",
                            "why": "promote HELD: serial candidate running — "
                                   "the shadow window is a multi-variable "
                                   "confound (D3 class); re-evaluating each "
                                   "cycle until the slot clears"}
        # [2026-07-28] never promote INTO a standing organ objection: a fresh
        # proprioception HURTING on a growth lever is the live lane's own
        # measurement that this knob is bad — the same evidence that would
        # release the promotion one cycle later must block it one cycle
        # earlier. Fail-safe False on a dark organ (promotes normally).
        _pf, _pwhy = prop_fade(prop_state, set(GROWTH_LIVE), now)
        if _pf:
            return gstate, {"kind": "eval",
                            "why": f"promote BLOCKED by organ verdict: {_pwhy}"}
        # [2026-07-29 AUDIT F4] ...and never INTO a standing organ PROPOSAL:
        # the reassert path already honors a fresh restrict proposal on the
        # pair (early release); promote-time must consult the same channel or
        # a promotion steers real money for one cycle before the very organ
        # evidence that releases it. Fail-safe on a dark channel.
        _props = proposals
        if _props is None and fprop is not None:
            try:
                _props = fprop.fresh_proposals()
            except Exception:      # noqa: BLE001
                _props = None
        if _props:
            _of, _owhy = proposal_fade(_props, dict(GROWTH_LIVE), now)
            if _of:
                return gstate, {"kind": "eval",
                                "why": f"promote BLOCKED by organ proposal: "
                                       f"{_owhy}"}
        rc = assert_fn(dict(GROWTH_LIVE),
                       "growth-levers PROMOTED (faster bar)",
                       str(pay.get("why") or "")[:280])
        if not asserted_fn(rc, GROWTH_LIVE):
            if not gstate.get("assert_fail_notified"):
                push("growth PROMOTION WRITE FAILED",
                     "the faster bar cleared but the live lever write did "
                     "not land — nothing reached real money; retrying next "
                     "cycle", priority="urgent")
            gstate["assert_fail_notified"] = True
            return gstate, {"kind": "promote-failed", "why": pay.get("why")}
        g2 = dict(g2)
        g2["assert_fail_notified"] = False
        push("PROMOTED to LIVE: Farmer growth levers",
             f"{pay.get('why')}\nlive levers: {json.dumps(GROWTH_LIVE)} "
             f"(TTL'd; the tight fade-revert backstops the faster bar)",
             priority="urgent")
        return g2, {"kind": kind, "why": pay.get("why")}
    if kind == "reassert":
        # [2026-07-28] the organ release paths reach this promotion exactly
        # as they reach the main pipeline's promoted phase: proprioception's
        # HURTING verdict (the live lane's own paired grades) and a fresh
        # organ restrict proposal each release EARLY, before the absolute
        # fade bar. Restrict-only in outcome via LIVE_ENV_DEFAULTS
        # orientation (releasing reverts to 0 explore slots / conviction
        # off — tighter by construction); fail-safe False on a dark organ
        # or channel. prop_state/proposals are injectable for the selftest;
        # prop_state was resolved above (shared with the promote gate).
        pfading, pwhy = prop_fade(prop_state, set(GROWTH_LIVE), now)
        ofading, owhy = (False, None)
        _props = proposals
        if _props is None and fprop is not None:
            try:
                _props = fprop.fresh_proposals()
            except Exception:      # noqa: BLE001
                _props = None
        if _props:
            ofading, owhy = proposal_fade(_props, dict(GROWTH_LIVE), now)
        if pfading or ofading:
            why = pwhy if pfading else owhy
            push("growth promotion RELEASED (organ signal)",
                 f"{why} — levers released, env defaults return within "
                 f"the TTL", priority="urgent")
            return ({"promoted": False, "released_ts": now,
                     "release_why": why,
                     "cooldown_until": now + GROWTH_COOLDOWN_H * 3600},
                    {"kind": "release", "why": why})
        rc = assert_fn(dict(GROWTH_LIVE), "growth-levers promotion in force",
                       f"live n={pay.get('n')} mean={pay.get('mean')}")
        g2 = dict(g2)
        if not asserted_fn(rc, GROWTH_LIVE):
            if not g2.get("assert_fail_notified"):
                push("growth re-assert FAILING",
                     "the live growth-lever write is not landing — it will "
                     "TTL-expire back to env defaults (fail-safe); "
                     "fade-watch continues on live data", priority="urgent")
            g2["assert_fail_notified"] = True
        else:
            g2["assert_fail_notified"] = False
        return g2, {"kind": kind, "n": pay.get("n"), "mean": pay.get("mean")}
    if kind == "release":
        push("growth promotion RELEASED",
             f"{pay.get('why')} — levers released, env defaults return "
             f"within the TTL", priority="urgent")
        return g2, {"kind": kind, "why": pay.get("why")}
    ev = pay if isinstance(pay, dict) else {}
    return g2, {"kind": kind, "why": ev.get("why")}


# [2026-07-29 audit R1] the OPERATOR RELEASE-REQUEST channel. The (dw) tool
# wrote the judge's state DIRECTLY under a row lock — but the judge's own
# hourly read→compute→save holds no lock, so a release committed mid-cycle
# could be overwritten by the judge's stale save seconds later: the release,
# its verdict and the 48h cooldown vanish AFTER the tool printed RELEASED
# (a tool-side compare-and-swap cannot fix this — the losing write is the
# judge's). The race-free shape is single-writer: the tool queues a REQUEST
# row; the judge — the only writer of its own state — consumes it at cycle
# start through its own save path. The request honors the standing bus
# contract (its own updated+ttl_sec, fail-closed): a request older than its
# TTL must NOT fire — the world it described has moved.
RELEASE_REQ_KEY = "xp-judge-release-request"
RELEASE_REQ_TTL = int(os.environ.get("XPJ_RELEASE_REQ_TTL", "7200"))


def release_transition(st, name, why, now):
    """The judge's ABANDON transition with verdict RELEASED-OPERATOR, as a
    pure function of current state — the SINGLE SOURCE for both the judge's
    request-consume path and scripts/xp_judge_release (which imports this;
    two copies of a state transition is how mirrors drift). Mirrors run_once's
    abandon save() field-for-field: phase idle, done+name, done_at stamp,
    COOLDOWN_H cooldown, started_ts cleared, verdicts appended + capped [-10:],
    last_eval preserved, growth/drift/skew/promote_baseline passed through.
    Raises ValueError on refusal (not-running / name mismatch) — callers
    translate: the tool to SystemExit, the judge to a recorded outcome."""
    if st.get("phase") != "running":
        raise ValueError(f"judge phase is {st.get('phase')!r}, not 'running'")
    if st.get("current") != name:
        raise ValueError(f"running candidate is {st.get('current')!r}, "
                         f"not {name!r}")
    done = list(st.get("done") or []) + [name]
    done_at = dict(st.get("done_at") or {})
    done_at[name] = now
    verdicts = list(st.get("verdicts") or []) + [{
        "name": name, "verdict": "RELEASED-OPERATOR", "ts": iso(now),
        "eval": st.get("last_eval"), "why": why}]
    return {"updated": iso(now), "ttl_sec": TTL_SEC,
            "phase": "idle", "current": None, "spec": {}, "candidate": None,
            "done": done, "done_at": done_at,
            "started_ts": None, "promoted_ts": st.get("promoted_ts"),
            "cooldown_until": now + COOLDOWN_H * 3600,
            "blind_cycles": st.get("blind_cycles") or 0,
            "skew_notified": bool(st.get("skew_notified")),
            "assert_fail_notified": bool(st.get("assert_fail_notified")),
            "drift_notified": bool(st.get("drift_notified")),
            "growth": st.get("growth"),
            "last_growth": st.get("last_growth"),
            "promote_baseline": st.get("promote_baseline"),
            "verdicts": verdicts[-10:], "last_eval": st.get("last_eval")}


def consume_release_request(req, phase, current, now):
    """(verdict, detail) for a queued operator release-request. PURE.
    verdict: 'none'        — no actionable request (absent / already consumed
                             / no name): do nothing, write nothing;
             'stale'       — request exists but is past its own updated+
                             ttl_sec (or unstamped — fail-closed): tombstone
                             it, do NOT release;
             'not-running' — judge is not mid-candidate: tombstone;
             'mismatch'    — running candidate differs from the request's:
                             tombstone (the judge moved; operator re-checks);
             'release'     — fresh + phase running + name match: caller
                             performs release_transition through its own save."""
    if not isinstance(req, dict) or req.get("consumed") or not req.get("name"):
        return "none", None
    try:
        u = datetime.fromisoformat(str(req.get("updated")).replace("Z", "+00:00"))
        age = now - u.timestamp()
        ttl = float(req.get("ttl_sec") or 0)
    except Exception:
        return "stale", "unparseable updated stamp (fail-closed)"
    if ttl <= 0 or age > ttl:
        return "stale", f"request age {age:.0f}s > ttl {ttl:.0f}s"
    if phase != "running":
        return "not-running", f"judge phase is {phase!r}"
    if current != req["name"]:
        return "mismatch", f"running {current!r}, requested {req['name']!r}"
    return "release", None


# ---------------------------------------------------------------------------
# [2026-08-25 (ti)] JUDGE V2.0 — THE MULTI-PAIR CENSUS.
#
# Eamon: *"The judge has malfunctioned several times for this sole reason,
# and it's well overdue for v2."* The sole reason, measured across four
# recorded failures (the I23 0.161pp handicap · the (pt) frozen window · the
# (ta) silent stand-down · the (tb) census erasure) and confirmed live on the
# bus: a SINGLE-pair machine hardwired to the Farmer's lanes, stood down
# since (ta) naming a successor it structurally could not judge.
#
# v2.0 ships the ENGINE'S EYES: every live/shadow twin in
# fleet_bus.JUDGED_PAIRS gets a per-pair published state with FAIRNESS
# PRECHECKS that emit `unjudgeable:<reason>` (naming the object, I8) instead
# of ever computing a biased bar — the F1 closure made structural. The
# farmer lane's serial candidate machine below is UNCHANGED and mirrors into
# pairs["farmer"]; family pairs run no candidates yet (their xp.<book>.*
# lever wave is v2.1, one registry entry away, and arrives as its own
# measured act) — so v2.0's blast radius on trading is ZERO while every
# pair's judgeability becomes a readable, wake-conditioned fact.
# Top-level phase/current stay the farmer lane's for consumer compatibility
# (impl_shortfall, the dashboard card); the rollup flip is v2.1's, taken
# WITH its consumers.

#: How stale a `bot_pnl` row may be before `_pair_precheck` calls the arm dark.
#: 3x the fleet's conventional 900s publish TTL, which is the value this bar has
#: always ACTUALLY had — it was written as `3 * (row.ttl_sec or 900)` and
#: `fetch_bot_pnl` emits no `ttl_sec`, so the per-row term never once applied.
#: Named here so it is greppable, mutatable and true. Live hosts publish every
#: 300s (`lighter_avo_live_bot.LOOP_SECONDS`), so this is ~9x headroom.
PAIR_ROW_STALE_S = 3 * 900


def _close_rank(r):
    """Sort key mirroring the publisher's own `ORDER BY closed_at DESC NULLS
    LAST` — non-null closes rank above unorderable ones, newest first under
    `reverse=True`. `parse_ts` RAISES on junk, so an unreadable stamp degrades
    to the NULLS-LAST bucket rather than taking the reader down.

    [(uy)] IT READS THE PUBLISHER'S KEY, NOT THE SQL'S. This read `closed_at`
    — the DB COLUMN name, lifted off the `ORDER BY` clause it was written to
    mirror — while `store.fetch_paper_trades`, the judge's ONLY ledger source
    (the fetch site below), normalises that column to `close_ts` and emits no
    `closed_at` at all. So on real data every row ranked `(False, 0.0)` and
    the sort was a stable NO-OP: the window was still the newest `look` only
    because the SQL happens to deliver them that way — precisely the
    caller-dependence (ts) was written to remove, reintroduced inside the fix
    for it. Every other ledger consumer in this file already reads `close_ts`.

    ONE KEY, NO FALLBACK, DELIBERATELY. A `closed_at` fallback was written and
    removed: the census has exactly one production caller (the fetch below)
    and it is publisher-shaped, so the tolerance served no caller — it only
    kept a future wrong-shaped one silently working, which is the mechanism
    that hid this for a day. `.get` on a missing key degrades to the NULLS-LAST
    bucket with no raise and no log, so tolerance here is indistinguishable
    from correctness. The drift it was meant to catch is caught instead by
    `tests/autonomy/test_judge_policy_waiver.py`, which reads this key off the
    AST and checks it against the key `fetch_paper_trades` really emits — a
    rename on EITHER side reddens, which the fallback could never have done."""
    try:
        ts = parse_ts(r.get("close_ts"))
    except (TypeError, ValueError, AttributeError):
        ts = None
    return (ts is not None, ts or 0.0)


def _latest_policy_stamp(rows, bot, look=30):
    """(stamp_dict|None, stamped_n, total_n) over the bot's newest `look`
    ledger closes. None = the arm does not stamp yet — an ABSENCE, reported
    as `policy_unstamped`, never guessed at ((kk): an absence is not a
    change; I6: it is only evidence once the other arm shows the mechanism
    works).

    [(ts)] THE WINDOW IS ORDERED HERE, NOT INHERITED FROM THE CALLER. This
    read `mine[-look:]` and `stamped[-1]`, which is the newest `look` only
    when rows arrive OLDEST-first — and the real publisher
    (`store.fetch_paper_trades`) is `ORDER BY closed_at DESC NULLS LAST`, so
    the census was scoring each arm's OLDEST 30 closes and calling the
    OLDEST stamp "latest". MEASURED 26-Aug: georgia's shadow arm published
    its first stamped close 09:22:44Z and the 09:43:39Z census still read
    `shadow 0/30`, byte-identical to an arm that stamps nothing, while the
    live arm read 30/30 because EVERY one of its rows is stamped and the
    window could not tell. The (tj) class in the ordering dimension: the
    fixture built ONE row per bot, where a slice direction is unobservable.
    Sorting here makes the answer independent of how the caller fetched."""
    mine = [r for r in rows or [] if str(r.get("bot")) == bot]
    mine.sort(key=_close_rank, reverse=True)
    mine = mine[:look]
    stamped = [r for r in mine
               if isinstance((r.get("extra") or {}).get("policy"), dict)]
    latest = (stamped[0]["extra"]["policy"] if stamped else None)
    return latest, len(stamped), len(mine)


def _stamp_readable(stamp, field):
    """Did the arm actually SAY something about `field`?

    A waiver may only cover a divergence both arms can be READ on. `dict.get`
    returns None for both "the arm stamps null here" and "the arm has never
    heard of this field", and neither is a measured value — so both are
    UNREADABLE and fail closed at the rung above. Deliberately not a
    truthiness test: `0`, `False` and `[]` are values an arm can legitimately
    stamp, and treating them as absent would fail a pair closed on a real
    reading (which is safe, but wrong, and trains the operator to ignore the
    state)."""
    if not isinstance(stamp, dict):
        return False
    return field in stamp and stamp.get(field) is not None


def _pair_precheck(pair_id, pspec, rows, bot_rows, now):
    """Stage-0 fairness for ONE pair -> a publishable pair state dict.

    Ordered by ACTIONABILITY (the (gl)/I8 rule — the reason the operator
    sees decides what they do next): retirement > dark live row > pnl_form >
    policy stamps > policy parity > capacity parity > idle. Every
    unjudgeable state names its object and carries `wake_when`; UNREADABLE
    parity inputs are `parity_unreadable`, never assumed-equal — darkness
    must not re-open the F1 handicap through the stage built to close it.

    The policy-parity rung honours this pair's DECLARED `policy_waived`
    fields (fleet_bus): a waived divergence does not block, is republished on
    the entry as `policy_waived`, and is refused outright where either arm's
    value is unreadable. A pair with no waiver behaves exactly as before."""
    # [(va)] normalised at the point of USE, not at `pair_census`, so BOTH
    # entry points are total — the judge's own selftest and the pair tests call
    # this function directly, and a normalisation one level up would leave the
    # direct callers on the raw shape (which is how the two `now` types coexisted
    # unnoticed in the first place).
    now = _epoch(now)
    live_bot, shadow_bot = pspec["live_bot"], pspec["shadow_bot"]
    st = {"live_bot": live_bot, "shadow_bot": shadow_bot,
          "pnl_form": pspec["pnl_form"], "candidate": None, "hold": None}
    # [2026-08-27 (vm)] THE POWER REPORT IS PUBLISHED ON EVERY STATE, NOT ONLY
    # ON `idle`. It was computed inside the `idle` rung's `st.update(...)`, and
    # every `_un(...)` and the `stood_down` branch return BEFORE that line — so
    # three of four live pairs published no power at all, and the one number
    # that says HOW LONG a blocked pair still has to run was visible only on
    # the pairs that were not blocked. Exactly backwards: a pair reading
    # `policy_unstamped` for a fortnight is the one whose closes/day and
    # `eta_judgeable` decide whether closing the wire is worth the week.
    # Computed ONCE here so no rung can forget it and no two rungs can disagree
    # (`_pair_power` never raises and returns None where the sample cannot
    # say — a blocked pair's report is honest, not absent).
    st["power"] = _pair_power(rows, live_bot, shadow_bot, pspec, now)
    st["eta_judgeable"] = _eta_judgeable(st["power"], now)

    def _un(reason, detail, wake):
        st.update(phase="unjudgeable",
                  unjudgeable={"reason": reason, "detail": detail,
                               "wake_when": wake})
        return st

    if _bus is not None and _bus.live_arm_retired(live_bot):
        spec = (getattr(_bus, "RETIRED_LIVE_ARMS", {}) or {}).get(live_bot, {})
        st.update(phase="stood_down",
                  stood_down={
                      "why": f"live arm retired {spec.get('since', '?')} "
                             f"{spec.get('entry', '')}",
                      "wake_when": f"{spec.get('override', '?')}=run on both "
                                   f"services (and the parked candidate "
                                   f"queue resumes at its head)",
                      "successor": spec.get("successor")})
        return st
    live_row = next((r for r in bot_rows or []
                     if str(r.get("bot")) == live_bot), None)
    shadow_row = next((r for r in bot_rows or []
                       if str(r.get("bot")) == shadow_bot), None)

    def _fresh(row):
        # [(tj)] the REAL publisher (`fetch_bot_pnl`) carries `updated_at`
        # (ISO), never a precomputed `age_sec` — the first live census read
        # every row dark because this required the dashboard feed's derived
        # field. The (hj) class, caught by the census's own first run within
        # the hour: a consumer is tested against the payload its publisher
        # builds, and the selftest now drives the `updated_at`-only shape
        # FIRST. Unknown age stays dark (fail-closed — this gate ADMITS a
        # pair toward a real-money comparison).
        # [(uy)] ...AND `ttl_sec` WAS THE SAME MISS, TWO LINES BELOW THAT
        # COMMENT. The bar read `3 * float(row.get("ttl_sec") or 900)` as
        # though the horizon were per-book, but `bot_pnl` HAS NO SUCH COLUMN
        # and `ttl_sec` does not occur once in bot_pnl_store.py — so the read
        # was None on every real row and the bar was always the fallback. Dead
        # rather than wrong, but it made the LIVE number untestable: both
        # fixtures supplied the phantom key, so the suite took a branch
        # production never takes and `900 -> 1` survived the whole suite. The
        # horizon is a CONSTANT because bot_pnl cannot carry a TTL; a per-book
        # bar has to come from somewhere that exists (pnl_dashboard's
        # `stale_secs_for` is the worked example), not from an absent key.
        if not isinstance(row, dict):
            return False
        try:
            age = row.get("age_sec")
            if age is None:
                ts = parse_ts(row.get("updated_at") or row.get("updated"))
                if ts is None:
                    return False
                # [(va)] the clock it was HANDED, not the wall clock. In
                # production these are the same object (`run_once` passes
                # `now = now_ts()`), so this changes no verdict — but it makes
                # the gate DETERMINISTIC, and it had to: the in-module
                # selftest drives t0 = 1_800_000_000.0, ~12.2M seconds in the
                # FUTURE of wall clock, so every age came out NEGATIVE and the
                # bar passed for any horizon. That selftest could not exercise
                # this gate in either direction — and it would have silently
                # flipped on 2027-01-15, when t0 becomes the past.
                age = now - ts
            return float(age) <= PAIR_ROW_STALE_S
        except (TypeError, ValueError):
            return False

    if not _fresh(live_row):
        return _un("live_row_dark",
                   f"{live_bot} absent or stale in bot_pnl — a registry "
                   f"entry must never outlive its row (the audit-scope "
                   f"lesson: a rule keyed to a list goes stale on every "
                   f"slot swap)",
                   "the live row publishes fresh again")
    # [(va)] I1 AT THE CONTROL ARM. `live_row_dark` was the ONLY liveness
    # check in the whole precheck, so every rung below read the SHADOW row's
    # last known values with no evidence anything still writes them — and
    # `fetch_bot_pnl` upserts on a bot primary key, so a dead publisher's final
    # row persists forever rather than ageing out. MEASURED by driving this
    # function: a shadow row TEN DAYS stale returns verdicts BYTE-IDENTICAL to
    # a fresh one — caps 5v6 publishes `capacity_mismatch` (which the
    # dashboard files under PIPE_WIRE, "a session can clear this week", so it
    # sends someone to align caps against a corpse), and caps 5v5 publishes
    # `idle`, i.e. JUDGEABLE. The second is the dangerous one: `idle` is the
    # state a real comparison starts from. Nor do the rungs in front of
    # capacity help — `_latest_policy_stamp` has no recency window at all, so a
    # dead arm still yields a policy stamp and parity passes on it.
    # A false certification, not merely a wrong bar, which is why it is
    # fail-CLOSED here rather than reported downstream (I1: establish that
    # something still WRITES the payload before interpreting what it says).
    if not _fresh(shadow_row):
        return _un("shadow_row_dark",
                   f"{shadow_bot} absent or stale in bot_pnl — the CONTROL "
                   f"arm's publisher is not writing, and every rung below "
                   f"this one would read its last known values as current "
                   f"(the paired bar is only as live as its control)",
                   "the shadow row publishes fresh again — if it does not, "
                   "the shadow service is stopped or crash-looping and that "
                   "is the thing to fix, not the pair's caps")
    # P1 — policy parity, from the arms' OWN close stamps (the shared
    # policy_stamp builder is the one source; a spec-side field list would
    # miss exactly the live-only divergences F1 is made of).
    lp, ln, lt = _latest_policy_stamp(rows, live_bot)
    sp, sn, stn = _latest_policy_stamp(rows, shadow_bot)
    st["stamps"] = {"live": f"{ln}/{lt}", "shadow": f"{sn}/{stn}"}
    # [2026-08-27 (vm)] AN EMPTY LEDGER IS NOT AN UNSTAMPED ONE — `no_closes`.
    #
    # 👩 mum published `policy_unstamped` naming `lighter_avo_live_bot.py` as
    # the file to go fix, on stamps `{live: "0/0", shadow: "0/8"}`. That host
    # HAS no stamping bug — 🔮 georgia reads `30/30` off the same code — so the
    # reason sent the next reader hunting a defect in a file that does not have
    # one (I8: the reason the operator sees decides what they do next, and a
    # wrong object is worse than an opaque one). Her actual condition is that
    # her LIVE arm has never closed a trade: `0/0` is zero closes, while
    # `0/8` is eight closes and none stamped, and the old rung read them as the
    # same fact because it only ever looked at `latest is None`.
    #
    # The split is on the DENOMINATOR, which is the only thing that
    # distinguishes them, and it runs FIRST because no stamping work can fix an
    # empty ledger. Its wake condition is a trade, not a deploy.
    _empty = [f"{b} ({t} closes)" for b, t in ((live_bot, lt), (shadow_bot, stn))
              if t == 0]
    if _empty:
        return _un("no_closes",
                   f"no closes at all on: {', '.join(_empty)} — the arm has "
                   f"never traded, so there is nothing to stamp and nothing "
                   f"to pair (stamps {st['stamps']}); this is NOT a stamping "
                   f"defect in {pspec['host_file']} / lighter_family_bot.py",
                   "the arm closes its first trade — a paired bar needs "
                   f"{MIN_CLOSES} shadow and {LIVE_MIN_CLOSES} live closes, "
                   "so the first one is the floor, not the bar")
    if lp is None or sp is None:
        which = []
        if lp is None:
            which.append(f"{live_bot} ({pspec['host_file']})")
        if sp is None:
            which.append(f"{shadow_bot} (lighter_family_bot.py)")
        return _un("policy_unstamped",
                   f"no policy stamp on the newest closes of: "
                   f"{', '.join(which)}",
                   "both arms' closes carry the shared policy_stamp "
                   "(ships with this build; wakes on the first stamped "
                   "close each side)")
    # [2026-08-26] THE DECLARED WAIVER, honoured HERE and nowhere else.
    # `pspec["policy_waived"]` (fleet_bus, per pair) maps a FIELD to the
    # measurement that makes it inert on THAT pair. Three properties, each
    # driven by tests/autonomy/test_judge_policy_waiver.py:
    #   * a waived field does not BLOCK, but the divergence is still
    #     REPORTED on the published entry (`st["policy_waived"]`, both arms'
    #     values + the reason). A waiver that hides the difference is how
    #     this class comes back;
    #   * it covers a field the arms READ DIFFERENTLY — never one either arm
    #     cannot read. A missing/None value on either side is DARKNESS and
    #     falls through to `parity_unreadable` below, because assumed-equal
    #     is precisely the F1 handicap this stage was built to close;
    #   * a pair with no `policy_waived` key takes the identical path it did
    #     before: `waived` and `dark` stay empty, `diffs` is built in
    #     policy_fields order exactly as the old comprehension built it.
    waivers = pspec.get("policy_waived") or {}
    diffs, waived, dark = [], {}, []
    for f in pspec["policy_fields"]:
        if f == "venue" or lp.get(f) == sp.get(f):
            continue
        if f in waivers:
            if _stamp_readable(lp, f) and _stamp_readable(sp, f):
                waived[f] = {"live": lp.get(f), "shadow": sp.get(f),
                             "why": str(waivers[f])}
            else:
                dark.append(f)
            continue
        diffs.append(f)
    if waived:
        # published BEFORE any later rung can return, so a pair that stops at
        # capacity parity still carries its waiver on the payload.
        st["policy_waived"] = waived
    if dark:
        return _un("parity_unreadable",
                   f"waived field(s) {dark} unreadable on an arm (live="
                   f"{ {f: lp.get(f) for f in dark} } shadow="
                   f"{ {f: sp.get(f) for f in dark} }) — a waiver covers a "
                   f"MEASURED divergence, never an absent value; "
                   f"assumed-equal would re-open the F1 handicap through "
                   f"the stage built to close it",
                   "both arms stamp the waived field with a readable value")
    if diffs:
        return _un("policy_mismatch",
                   f"arms diverge on {diffs}: live="
                   f"{ {f: lp.get(f) for f in diffs} } shadow="
                   f"{ {f: sp.get(f) for f in diffs} }",
                   "the divergence is ported across or declared out of "
                   "this pair's policy_fields — a measured act, never a "
                   "silent default")
    # [2026-08-26] P2b — THE REQUIRED-STAMP RUNG, the waiver's mirror.
    #
    # A `policy_fields` entry NEITHER host stamps compares None to None, reads
    # EQUAL, and sails through the rung above in silence — so the registry
    # would claim to police a divergence it structurally cannot see. That is
    # how 🔮 georgia's SECOND entry-policy divergence stayed invisible while
    # the first one blocked her: the shadow throttles entries per clock hour
    # and the live host does not, and no stamp carries it.
    # `pspec["policy_stamp_required"]` (fleet_bus, per pair, field -> reason
    # with the measurement and the exact stamp work) turns that absence into a
    # BLOCK that self-closes the moment both publishers stamp the key.
    #
    # PRESENCE, never truthiness: `None` is the honest stamp for "this host
    # has no such rule", and a host that says so has answered — the divergence
    # then blocks at the PARITY rung above, on its value, which is where it
    # belongs.
    #
    # RUNG ORDER, deliberate: this sits AFTER parity, so a pair that already
    # has a VISIBLE divergence keeps reporting that one (the more actionable
    # of two wire-class blocks, and the precedence every existing consumer was
    # written against). Either way the pair cannot reach `idle` while a
    # required field is unstamped, which is the property that matters.
    # It reuses `policy_unstamped` rather than minting a reason: the fact IS
    # that the stamp is missing a field, and a new string would fall through
    # every consumer's reason map to "unknown".
    missing = [f for f, _why in sorted((pspec.get("policy_stamp_required")
                                        or {}).items())
               if f not in lp or f not in sp]
    if missing:
        return _un("policy_unstamped",
                   f"required policy field(s) {missing} are stamped by "
                   f"NEITHER arm's closes (live {live_bot} / "
                   f"{pspec['host_file']}, shadow {shadow_bot} / "
                   f"lighter_family_bot.py) — the arms are known to differ "
                   f"here and an unstamped field compares equal, so the "
                   f"parity rung above cannot see it: "
                   + " | ".join(str((pspec.get("policy_stamp_required")
                                     or {}).get(f, "")) for f in missing),
                   "lighter_family_bot.policy_stamp() — the ONE builder both "
                   "hosts call — carries the field, each host answering for "
                   "itself (None is a valid answer meaning 'no such rule "
                   "here'); the divergence then blocks on its VALUE at the "
                   "parity rung until the arms are aligned or it is waived "
                   "on its own evidence")
    # P3 — capacity parity off the rows' own published caps (I1-fresh).
    lmo = (live_row.get("extra") or {}).get("max_open")
    smo = ((shadow_row or {}).get("extra") or {}).get("max_open")
    if lmo is None or smo is None:
        return _un("parity_unreadable",
                   f"max_open unreadable (live={lmo} shadow={smo}) — "
                   f"assumed-equal would re-open the F1 handicap through "
                   f"the stage built to close it",
                   "both rows publish extra.max_open fresh")
    if lmo != smo:
        return _un("capacity_mismatch",
                   f"live max_open {lmo} vs shadow {smo} — a capacity "
                   f"delta biases the paired bar unless it IS the "
                   f"receipted candidate",
                   "the caps match, or the delta becomes this pair's "
                   "first receipted candidate")
    # [2026-08-26] A WAIVED PAIR SAYS SO WHERE THE OPERATOR READS IT. The
    # structured `policy_waived` above is the machine-readable record; the
    # 🏭 pipeline card renders `note` for an idle pair, so a pair that is
    # judgeable ONLY because of a declared waiver must not read identically
    # to one whose arms genuinely match (I1's shape at the report layer).
    # Empty waiver -> the byte-identical pre-waiver note.
    _note = ("judgeable; no candidate in this pair's queue "
             f"({pspec['xp_prefix']}*) — the lever wave is v2.1")
    if waived:
        _note += (f" · judgeable WITH a declared parity waiver on "
                  f"{sorted(waived)} (measured inert on this pair; the "
                  f"divergence is published, not hidden)")
    # [(ti)/(vm)] the POWER REPORT rides `st` from the top of this function —
    # every state carries it, `idle` included. It stays REPORT ONLY (I16's own
    # advisory scoping); nothing gates on it.
    st.update(phase="idle", note=_note)
    return st


def _pair_power(rows, live_bot, shadow_bot, pspec, now, window_d=14.0):
    """{sd_pct, closes_per_day, n} per arm + the MDE at the floors, over
    the trailing window's ECONOMIC closes (strip_exits removed — the same
    strip the bar itself will take). None fields where the sample cannot
    say; never raises."""
    try:
        import math
        cutoff = now - window_d * 86400.0
        out = {}
        strips = tuple(pspec.get("strip_exits") or ())
        sds = []
        for label, bot in (("live", live_bot), ("shadow", shadow_bot)):
            pts = []
            for r in rows or []:
                if str(r.get("bot")) != bot:
                    continue
                if any(s in str(r.get("exit_reason") or "") for s in strips):
                    continue
                try:
                    ts = parse_ts(r.get("close_ts"))
                    if ts is None or ts < cutoff:
                        continue
                    p = r.get("profit_ratio")
                    if p is None:
                        continue
                    pts.append(float(p) * 100.0)
                except Exception:  # noqa: BLE001
                    continue
            n = len(pts)
            sd = None
            if n >= 5:
                m = sum(pts) / n
                sd = math.sqrt(sum((x - m) ** 2 for x in pts) / (n - 1))
                sds.append(sd)
            out[label] = {"n": n, "sd_pct": (round(sd, 3) if sd else None),
                          "closes_per_day": round(n / window_d, 2)}
        if sds:
            pooled = max(sds)
            # [2026-08-27 (vm)] THE PUBLISHED MDE DESCRIBED THE WRONG RUNG.
            # It read `sqrt(1/30 + 1/10)` — the FULL-WINDOW floors — while the
            # bar that actually binds is the PER-HALF one: `paired_eval` splits
            # the window and requires the margin on h1 AND h2 at
            # `half_floors()` = (15, 5). That interval is
            # sqrt(1/15+1/5)/sqrt(1/30+1/10) = **1.414x wider**, and it must be
            # cleared TWICE — so the number the operator was reading
            # under-stated the real detection threshold by 41% on the rung that
            # rejects candidates first. Both are published now: `mde_pp_half`
            # is THE bar (kept as the headline `mde_pp_at_floors` so no
            # consumer silently keeps reading the looser one under the old key
            # — the key's MEANING is corrected, not its name), and
            # `mde_pp_full_window` stays beside it so the 1.414x is visible
            # rather than asserted. Still REPORT ONLY: `paired_eval` is
            # untouched and no verdict moves.
            _hs, _hl = half_floors()
            out["mde_pp_half"] = round(
                MDE_Z * pooled * math.sqrt(1 / _hs + 1 / _hl), 3)
            out["mde_pp_full_window"] = round(
                MDE_Z * pooled * math.sqrt(1 / MIN_CLOSES + 1 / LIVE_MIN_CLOSES), 3)
            out["mde_pp_at_floors"] = out["mde_pp_half"]
            out["mde_basis"] = (f"per-half floors {_hs}/{_hl}, cleared twice "
                                f"(h1 AND h2) — the binding rung; full-window "
                                f"{MIN_CLOSES}/{LIVE_MIN_CLOSES} is looser")
            out["margin_pp"] = MARGIN_PP
        return out
    except Exception:  # noqa: BLE001
        return None


def _eta_judgeable(power, now, min_days=None, min_closes=None, live_min=None):
    """WHEN could this pair be judged at all, at its arms' MEASURED close
    rates — a FLOOR, with the BINDING term named.

    Same shape and same discipline as `scripts/golive_readiness.gate_horizon`:
    one `days` per term, the binding one is the MAX, and the answer is
    explicitly a floor (the earliest the paired bar can OPEN, never a claim
    that it will pass). Three terms, each one of the judge's own gates:

        window         MIN_DAYS — the calendar the candidate must run
        shadow_closes  MIN_CLOSES / shadow closes-per-day
        live_closes    LIVE_MIN_CLOSES / live closes-per-day

    From a STANDING START, deliberately: a candidate window begins when the
    judge asserts its levers, so the closes it needs are the ones that accrue
    AFTER that moment — the trailing sample sizes the rate, never the numerator.

    FAIL-SAFE: an arm with no measurable rate makes its own term
    UNPROJECTABLE, and the whole answer is then `days: None` with that arm
    NAMED — never a number computed off the arms that do move, which would read
    as a real ETA for a pair that has one dead arm (I1: the smaller arm is the
    one that decides). Never raises; `None` power in, `None` out.

    `now` is the clock this cycle was HANDED (epoch seconds or a datetime, via
    `_epoch`), never the wall clock — the (va) lesson: a date computed off
    `now_ts()` inside a function given a `now` is undriveable by a test and
    silently disagrees with every other field on the same payload."""
    md = MIN_DAYS if min_days is None else float(min_days)
    mc = MIN_CLOSES if min_closes is None else int(min_closes)
    lm = LIVE_MIN_CLOSES if live_min is None else int(live_min)
    if not isinstance(power, dict):
        return None
    try:
        terms, dead = {"window": round(md, 1)}, []
        for label, need in (("shadow", mc), ("live", lm)):
            rate = (power.get(label) or {}).get("closes_per_day")
            key = f"{label}_closes"
            if not isinstance(rate, (int, float)) or rate <= 0:
                terms[key], dead = None, dead + [label]
                continue
            terms[key] = round(need / float(rate), 1)
        if dead:
            return {"days": None, "eta": None, "kind": "floor",
                    "binding": f"{dead[0]}_closes", "terms": terms,
                    "why": (f"no measurable close rate on the {'/'.join(dead)} "
                            f"arm over the power window — the pair cannot be "
                            f"judged at any date, and a number from the other "
                            f"arm alone would read as one")}
        binding = max(terms, key=lambda k: terms[k])
        days = terms[binding]
        return {"days": days,
                "eta": iso(_epoch(now) + days * 86400.0)[:10],
                "kind": "floor", "binding": binding, "terms": terms,
                "why": (f"floor {days:.1f}d, bound by {binding} "
                        f"({', '.join(f'{k} {v}d' for k, v in sorted(terms.items()))}) "
                        f"— the earliest the paired bar can OPEN, not pass")}
    except Exception:  # noqa: BLE001
        return None


def _epoch(now):
    """`now` as EPOCH SECONDS, whichever way a caller expresses it.

    [(va)] ONE boundary, one meaning. This parameter had TWO live shapes and
    nothing noticed, because until this commit `_fresh` ignored it and read the
    wall clock: `run_once` passes `now_ts()` (a float) and the pipeline-card
    fixture passes a `datetime`. The moment the freshness gate actually READ
    the argument, the datetime path raised inside `_fresh`'s `except
    (TypeError, ValueError)` and every pair in that fixture went `live_row_dark`
    — a type ambiguity failing CLOSED, which is the safe direction and still a
    defect. Normalised here rather than in `_fresh` so every rung below shares
    one meaning; anything that is neither raises, rather than degrading."""
    return now.timestamp() if hasattr(now, "timestamp") else float(now)


def pair_census(rows, bot_rows, now):
    """Every JUDGED_PAIRS entry -> its published state. The farmer entry is
    OVERWRITTEN by the serial machine's own state in save() — the machine
    is senior for the lane it actually runs.

    `now` is epoch seconds or a datetime; see `_epoch`."""
    out = {}
    for pid, pspec in (getattr(_bus, "JUDGED_PAIRS", {}) or {}).items():
        try:
            out[pid] = _pair_precheck(pid, pspec, rows, bot_rows, now)
        except Exception as e:  # noqa: BLE001
            out[pid] = {"phase": "unjudgeable",
                        "unjudgeable": {"reason": "parity_unreadable",
                                        "detail": f"census error: {e!r}",
                                        "wake_when": "the census computes"}}
    return out


# [2026-08-27 (vm)] THE STAND-DOWN IS PER-PAIR, NOT PER-PROCESS.
#
# MEASURED before this change: `run_once` hit `if _bus.live_arm_retired(
# LIVE_BOT): return save(stood_down)` at module scope, and BOTH production
# `paired_eval` call sites sit below it — so the sole producer of
# `promote: True` ran ZERO TIMES PER CYCLE, for every pair, because ONE pair's
# live arm is retired. The four `pairs` entries computed above it are a
# read-only precheck; the judge published a census of four and judged none.
#
# The retirement itself is CORRECT and stays: 💸 the Farmer's live arm was
# retired 22-Aug (ta) and must never be promoted onto. What was wrong is its
# SCOPE — a process-wide return keyed on a module global, standing down three
# living pairs on a fourth's retirement.
#
# So the question the machine asks is now "is MY OWN lane parked?", answered
# off the census's own per-pair verdict. Today the answer is still yes (the
# serial machine's lane IS the farmer's — `LIVE_BOT` is its live arm), so no
# trade and no promotion moves; what changes is that georgia's, mum's and
# avo's lanes are no longer stood down BY the farmer, and the moment their
# `xp.<book>.*` candidate wave lands (v2.1) they are admitted per-pair instead
# of needing this gate rewritten under them.
def serial_lane_id(live_bot=None, pairs=None):
    """Which declared pair IS this module's serial candidate machine's lane?

    DERIVED, never declared a second time: the machine trades `LIVE_BOT` vs
    `SHADOW_BOT`, so the pair naming `LIVE_BOT` as its live arm is its lane. A
    second hardcoded `"farmer"` here would be a second copy of the rule, and it
    would go stale on exactly the slot swap that produced this defect.
    None when no declared pair claims the row (an unpaired machine)."""
    lb = live_bot or LIVE_BOT
    src = pairs if pairs is not None else (getattr(_bus, "JUDGED_PAIRS", {}) or {})
    for pid, ps in src.items():
        if isinstance(ps, dict) and ps.get("live_bot") == lb:
            return pid
    return None


def lane_stood_down(pairs, live_bot=None, bus=None):
    """-> (parked: bool, lane_id, stood_down_block) for the SERIAL machine's
    OWN lane.

    Two independent arms, and that is deliberate rather than belt-and-braces
    tidiness:
      * the CENSUS arm is the per-pair one — this lane is parked because the
        precheck parked THIS pair, not because some other pair is retired;
      * the BUS arm is the fail-CLOSED backstop. `pair_census` degrades to `{}`
        on a dark `bot_pnl` fetch or any census error, and an empty census must
        never read as "nobody is retired" and hand a RETIRED REAL-MONEY ARM
        back to the candidate machine. Darkness stands down.
    Neither arm can be removed without opening one of those two holes."""
    lane = serial_lane_id(live_bot, pairs=None)
    entry = (pairs or {}).get(lane) if lane else None
    if isinstance(entry, dict) and entry.get("phase") == "stood_down":
        return True, lane, dict(entry.get("stood_down") or {})
    lb = live_bot or LIVE_BOT
    if bus is not None and bus.live_arm_retired(lb):
        spec = (getattr(bus, "RETIRED_LIVE_ARMS", {}) or {}).get(lb, {})
        return True, lane, {"why": f"live arm retired {spec.get('since', '?')} "
                                   f"{spec.get('entry', '')}",
                            "successor": spec.get("successor"),
                            "src": "bus (census dark — fail-closed)"}
    return False, lane, None


def lane_census(pairs, live_bot=None):
    """The one-line answer to 'how many of its pairs is the judge judging?' —
    published beside the pairs map so `0 of 4` stops being something a reader
    has to derive by hand from four nested phases.

    `live` = a pair the machine could run today (idle/running/promoted).
    Every declared pair lands in exactly one bucket; an unrecognised phase
    lands in `unknown` rather than being absorbed into a known one (the
    pipeline card's own rule, and for the same reason)."""
    out = {"serial_lane": serial_lane_id(live_bot, pairs=None),
           "live": [], "stood_down": [], "unjudgeable": [], "unknown": []}
    for pid, ent in sorted((pairs or {}).items()):
        ph = (ent or {}).get("phase") if isinstance(ent, dict) else None
        if ph in ("idle", "running", "promoted"):
            out["live"].append(pid)
        elif ph == "stood_down":
            out["stood_down"].append(pid)
        elif ph == "unjudgeable":
            out["unjudgeable"].append(pid)
        else:
            out["unknown"].append(pid)
    out["judging"] = f"{len(out['live'])} of {len(pairs or {})}"
    return out


def _farmer_pair_entry(payload):
    """Mirror the serial machine's top-level state into pairs['farmer'] —
    one machine, two views, no second copy of the rule: everything here is
    DERIVED from the payload the machine just built."""
    hold = None
    if payload.get("phase") == "running":
        le = payload.get("last_eval") or {}
        if le.get("arm_drift"):
            hold = "arm_drift"
        elif le.get("arm_skew"):
            hold = "arm_skew"
        elif payload.get("assert_fail_notified"):
            hold = "assert_fail"
        elif str(le.get("why") or "").startswith(("floors", "h1", "h2")):
            hold = "floors"
    entry = {"phase": payload.get("phase"),
             "candidate": payload.get("candidate"), "hold": hold,
             "live_bot": LIVE_BOT, "shadow_bot": SHADOW_BOT,
             "pnl_form": "funding",
             # provenance: THIS entry is the serial machine's own state, not
             # the census's precheck view — the machine is senior for the
             # lane it runs, and a reader (or a test) can tell which view
             # it is holding.
             "src": "machine"}
    if payload.get("phase") == "stood_down":
        le = payload.get("last_eval") or {}
        spec = (le.get("retired") or {})
        entry["stood_down"] = {
            "why": le.get("why"),
            "wake_when": f"{spec.get('override', '?')}=run on both services",
            "successor": spec.get("successor")}
    return entry


def run_once():
    now = now_ts()
    # [2026-07-17 AUDIT] A FAILED READ IS NOT AN EMPTY JUDGE. `load_state`
    # returns None for BOTH "no row" and "read failed" — and
    # load_state_checked's docstring names this exact caller shape: "a trap for
    # any caller that SEEDS durable state on an empty read". This function is
    # that caller: it read `or {}`, defaulted phase to "idle", and then wrote
    # the whole state back UNCONDITIONALLY at the end. Reads and writes fail
    # independently (the read path drops the connection; the write path
    # reconnects), so read-fails/write-OK is the ordinary shape of a Postgres
    # blip — not an exotic one.
    #
    # Measured: with one failed read, a stored `phase=promoted` (7 days earned,
    # steering REAL live.funding.* bars), its done-list and every verdict were
    # overwritten with an idle first-run state. The promotion record dies
    # silently — the phone said PROMOTED and no FADED verdict is ever logged —
    # and the wiped done-list makes a candidate previously FADED (i.e. MEASURED
    # to be hurting the live arm) immediately retry-eligible, bypassing both
    # COOLDOWN_H and DONE_RETRY_D.
    #
    # It also silently disarmed BLIND_MAX, whose own comment says "a DB blip
    # shouldn't release a 7d-earned promotion": a DB outage fails load_state
    # too, so `phase` read "idle" and the promoted branch it guards was never
    # reached. The guard could not fire in the scenario it was written for.
    #
    # Skipping a cycle costs one hour on an hourly organ. Seeding costs a
    # 7-day experiment and can re-run a knob the live lane already measured bad.
    _ok, _st = store.load_state_checked(KEY)
    if not _ok:
        print("[xp-judge] state READ FAILED — skipping this cycle rather than "
              "seeding an empty judge over a live promotion (a blip must not "
              "release a 7d-earned experiment). Retries next hour.", flush=True)
        return
    st = _st or {}
    phase = st.get("phase") or "idle"
    done = list(st.get("done") or [])
    # [2026-07-17 IMB-07] done_at stamps make the done-list AGEABLE. Legacy
    # names with no stamp (pre-aging state) are stamped NOW — a fresh retry
    # clock, never an instant flood-back.
    done_at = {k: _num(v, now) for k, v in (st.get("done_at") or {}).items()}
    for _n in done:
        done_at.setdefault(_n, now)
    done_at = {k: v for k, v in done_at.items() if k in done}
    current = st.get("current")
    spec = st.get("spec") or {}                 # full {name, levers} of current
    verdicts = st.get("verdicts") or []
    # [2026-07-29 audit R1] consume a queued operator release-request FIRST —
    # single-writer discipline: the tool queues, the judge acts through its
    # own save. Ordering is the idempotency: judge state is written BEFORE
    # the request tombstone, so a failed state write leaves the request
    # unconsumed (retried next cycle, TTL permitting) and a failed tombstone
    # write is self-healing (next cycle reads phase=idle → 'not-running' →
    # tombstones then). A dark request channel consumes nothing.
    try:
        _req = store.load_state(RELEASE_REQ_KEY)
    except Exception:      # noqa: BLE001
        _req = None
    _rq, _rq_why = consume_release_request(_req, phase, current, now)
    if _rq != "none":
        if _rq == "release":
            payload = release_transition(st, _req["name"],
                                         str(_req.get("why") or
                                             "operator release"), now)
            if not store.save_state(KEY, payload):
                print("[xp-judge] release-request: state write FAILED — "
                      "request left queued for next cycle", flush=True)
                return
            send_push("candidate RELEASED (operator request)",
                      f"{_req['name']} released via the request channel: "
                      f"{_req.get('why')}\ncooldown "
                      f"{COOLDOWN_H:.0f}h; xp levers lapse on TTL",
                      priority="urgent")
            _rq_why = "released"
        store.save_state(RELEASE_REQ_KEY,
                         {"updated": iso(now), "ttl_sec": 7 * 86400,
                          "consumed": True, "outcome": _rq,
                          "detail": _rq_why,
                          "request": {k: _req.get(k)
                                      for k in ("name", "why", "requested")}})
        print(f"[xp-judge] release-request: {_rq} ({_rq_why})", flush=True)
        if _rq == "release":
            return          # state just changed wholesale; resume next cycle
    rows = store.fetch_paper_trades(limit=4000)
    have_ledger = bool(rows)
    # [(ti)] v2.0: the multi-pair census — every registered twin's
    # judgeability, precheck-verdicted and wake-conditioned, computed once
    # per cycle and attached to every save() below. Guarded like every
    # optional read: a dark fetch censuses nothing (the farmer mirror still
    # publishes from the machine's own state).
    try:
        _census = pair_census(rows, store.fetch_bot_pnl() or [], now)
    except Exception:  # noqa: BLE001
        _census = {}
    # [2026-07-28] ONE drift snapshot per cycle, shared by the growth step and
    # the running phase — the drift check and the numbers it gates must never
    # describe different moments (the 17-Jul same-snapshot doctrine).
    # [2026-08-06] ...and "the same moment" now means the same SAMPLE too: the
    # CONTAINER half is one reading per cycle (it describes NOW, and both
    # consumers ask it the same question), while the ROW half is scoped to
    # each consumer's own window — growth's trailing 2.5d below, the
    # candidate's `started` in the running phase. Unscoped, the row half
    # compared closes the bar excludes and held the pipeline on a converged
    # pair; see _arm_drift_snapshot.
    _cur_drift = _current_drift() if have_ledger else None
    _drift_snap = (_arm_drift_snapshot(rows, since_ts=growth_window_start(now),
                                       current=_cur_drift)
                   if have_ledger else None)

    def save(**kw):
        payload = {"updated": iso(now), "ttl_sec": TTL_SEC,
                   "phase": kw.get("phase", phase),
                   "current": kw.get("current", current),
                   "spec": kw.get("spec", spec),
                   "candidate": (kw.get("current", current)
                                 if kw.get("phase", phase) in ("running", "promoted")
                                 else None),
                   "done": kw.get("done", done),
                   "done_at": kw.get("done_at", done_at),
                   "started_ts": kw.get("started_ts", st.get("started_ts")),
                   "promoted_ts": kw.get("promoted_ts", st.get("promoted_ts")),
                   "cooldown_until": kw.get("cooldown_until", st.get("cooldown_until")),
                   "blind_cycles": kw.get("blind_cycles", st.get("blind_cycles") or 0),
                   # [2026-07-16] sticky across cycles so the urgent ARM-SKEW
                   # push fires once per episode, not every 30 min forever.
                   "skew_notified": bool(kw.get("skew_notified",
                                                st.get("skew_notified"))),
                   # [2026-07-28 AUDIT FIX] the ARM-DRIFT hold's sticky flag
                   # was passed as a save() kwarg but NEVER persisted (no key
                   # here), so every drift-hold cycle re-read None: the
                   # urgent push re-fired hourly AND the arms-re-matched
                   # clock restart (`if st.get("drift_notified")`) could
                   # never fire — the one recovery of the three that was
                   # structurally dead. Mirrors skew_notified exactly.
                   "drift_notified": bool(kw.get("drift_notified",
                                                 st.get("drift_notified"))),
                   # [2026-07-16] same once-per-episode contract for failed
                   # rail writes (idle-start / re-assert / promote).
                   "assert_fail_notified": bool(kw.get("assert_fail_notified",
                                                       st.get("assert_fail_notified"))),
                   # [2026-07-16] the live arm's pre-promotion mean, stamped at
                   # PROMOTE — the relative fade bar's anchor. None for
                   # promotions predating the stamp (absolute bar only).
                   "promote_baseline": kw.get("promote_baseline",
                                              st.get("promote_baseline")),
                   # [2026-07-28 §3c] the growth-lever pair's own state +
                   # last verdict — set on st by the growth step below
                   # before any branch saves, so every exit persists it.
                   "growth": kw.get("growth", st.get("growth")),
                   "last_growth": kw.get("last_growth", st.get("last_growth")),
                   # [2026-07-29] close-rate reachability of the growth floor
                   # — report-only, so a multi-week "floors: N/15" can be told
                   # apart from a bar that cannot be met. See growth_reachable.
                   "growth_reach": kw.get("growth_reach",
                                          st.get("growth_reach")),
                   "verdicts": verdicts[-10:], "last_eval": kw.get("last_eval")}
        # [(ti)] v2.0 pairs map: the census, with the farmer entry
        # OVERWRITTEN by this machine's own just-built state (the machine is
        # senior for the lane it runs). Top-level phase/current stay the
        # farmer lane's for consumer compat; the pairs map is the truth a
        # v2.1 rollup flip will promote, WITH its consumers.
        try:
            _pairs = dict(_census)
            _pairs["farmer"] = _farmer_pair_entry(payload)
            payload["pairs"] = _pairs
            # [(vm)] the roll-up of that map: which lanes are live, which are
            # parked, and which one the serial machine below actually runs.
            # Published, not derived by every reader — see `lane_census`.
            payload["lanes"] = lane_census(_pairs)
        except Exception:  # noqa: BLE001
            payload["pairs"] = {}
            payload["lanes"] = {}
        store.save_state(KEY, payload)
        if hasattr(store, "save_history"):
            try:
                # [2026-07-16 AUDIT FIX] snapshot the FULL state, not a
                # {phase, candidate} summary — fleet_regen restores the judge
                # from these rows, and a summary "repair" wiped done/verdicts/
                # spec (total memory loss, promotion dropped).
                store.save_history(KEY, payload)
            except Exception:
                pass
        print(f"[xp-judge] {iso(now)} phase={payload['phase']} "
              f"candidate={payload['candidate']} "
              f"{kw.get('note') or ''}", flush=True)
        return payload

    # [2026-08-22 (ta)] THE LIVE ARM IS RETIRED — STAND DOWN, OUT LOUD.
    #
    # This judge exists to promote `live.funding.*` bars onto ONE row, and 💸
    # the Farmer's live arm was retired 22-Aug so 🔮 georgia could take the
    # sub-account. Its paired bar needs `live >= 10` closes in the window, so a
    # flat arm silences the pipeline CORRECTLY and INVISIBLY — `promote: false`
    # would read identically for "no candidate cleared the bar" and "there is
    # no live arm left to promote onto". That is the (I18) ambiguity a
    # component owes its own census for.
    #
    # RETURNING IS THE RELEASE. Promoted levers are TTL'd and are kept alive by
    # this cycle re-asserting them; not asserting is how the rail was designed
    # to revert ("expiry = env defaults"), so a stand-down cleans up after
    # itself with no second code path to get wrong. Measured at the
    # retirement: ZERO `live.*` levers open, so nothing had to.
    #
    # Placed AFTER the state read and the release-request consumption (both
    # safe, and the latter only ever RELEASES) and BEFORE any evaluation, so
    # the judge writes a phase and touches nothing else.
    #
    # [2026-08-27 (vm)] SCOPED TO THIS LANE'S OWN PAIR — see `lane_stood_down`.
    # The condition was `_bus.live_arm_retired(LIVE_BOT)` read as a fact about
    # the PROCESS; it is now a fact about the pair this machine runs, taken off
    # the census's own per-pair verdict with the bus as the fail-closed
    # backstop. Same answer today (the farmer's lane IS this machine's, and it
    # stays parked), and no longer the reason three living pairs are skipped.
    _parked, _lane, _why = lane_stood_down(_census, bus=_bus)
    if _parked:
        _spec = (getattr(_bus, "RETIRED_LIVE_ARMS", {}) or {}).get(LIVE_BOT, {}) \
            if _bus is not None else {}
        _others = [p for p in sorted(_census) if p != _lane]
        return save(phase="stood_down",
                    note=(f"lane {_lane}: live arm {LIVE_BOT} retired "
                          f"{_spec.get('since', '?')} {_spec.get('entry', '')}"
                          f" -> {_spec.get('successor', '?')}; not promoting, "
                          f"and not re-asserting (TTL reverts any open lever). "
                          f"Resurrect with "
                          f"{_spec.get('override', '?')}=run on BOTH this "
                          f"service and the live one. "
                          f"THIS PARKS ONE LANE, NOT THE JUDGE: {_others} keep "
                          f"their prechecks and wake conditions, and admit "
                          f"candidates as soon as their queues exist."),
                    last_eval={"promote": False, "why": "live arm retired",
                               "lane": _lane, "lane_why": _why,
                               # `note` is PRINTED, never persisted (see
                               # save()), so the fact that this parks one lane
                               # and not the judge has to live on the payload
                               # or it lives in a log nobody greps.
                               "lanes_not_parked": _others,
                               "retired": dict(_spec, row=LIVE_BOT)})

    # [2026-07-28 §3c] the growth-lever pair runs its own self-contained
    # promoter EVERY cycle, whatever the serial queue is doing (it is
    # deliberately NOT one-at-a-time — the shadow runs both levers via its
    # own env, always on). All effects go through the same rail + phone as
    # the main path; state rides st['growth'] into every save() above.
    # Fail-closed at every gate (receipts, drift, floors, write-lands) —
    # see growth_step/growth_promoter. [2026-07-29 AUDIT F1] serial_phase
    # passes the queue's state so the promote WRITE holds while a serial
    # candidate contaminates the shadow window; evaluation never stops.
    _g2, _glast = growth_step(st.get("growth"), rows, have_ledger, now,
                              drift=_drift_snap, serial_phase=phase)
    st["growth"], st["last_growth"] = _g2, _glast
    if _glast.get("kind") not in (None, "eval"):
        print(f"[xp-judge] growth-levers: {_glast}", flush=True)
    # [2026-07-29] Is the growth floor even REACHABLE at the arm's own close
    # rate? Report-only (see growth_reachable) — "floors: shadow N/15" for
    # weeks must be distinguishable from a bar that cannot be met.
    _reach, _reach_d = growth_reachable(rows, now)
    st["growth_reach"] = dict(_reach_d, reachable=_reach)
    if _reach is False and not _g2.get("promoted"):
        print(f"[xp-judge] ⚠️  growth floor UNREACHABLE at the current rate: "
              f"{_reach_d['why']} — the pair cannot promote until the arm "
              f"closes faster or the operator re-specs the window "
              f"(XPJ_GROWTH_DAYS); not auto-widened by design", flush=True)

    if phase == "idle":
        if _num(st.get("cooldown_until")) > now:
            return save(note=f"cooldown until {iso(_num(st['cooldown_until']))}")
        if not have_ledger:
            return save(note="no ledger visible — asserting nothing (fail-safe)")
        pool = candidate_pool(store.load_state("xp-queue") or {}, now=now)
        cand, _retried = pick_candidate(pool, done, done_at, current, now,
                                        DONE_RETRY_D * 86400)
        if cand is None:
            return save(note="queue exhausted — awaiting new incubator "
                             "proposals (or a done entry aging past "
                             f"{DONE_RETRY_D:g}d)")
        if _retried:
            done = [n for n in done if n != cand["name"]]
            done_at.pop(cand["name"], None)
            print(f"[xp-judge] RETRYING aged-out candidate {cand['name']} "
                  f"(done {DONE_RETRY_D:g}d+ ago; no untried candidates "
                  f"remain)", flush=True)
        # [2026-07-16] a candidate the registry can NEVER accept (unknown
        # lever / unclampable value) must not retry forever — mark INVALID and
        # move on, spending no judge slot. Distinct from a transient write
        # failure below, which retries.
        bad = [k for k, v in cand["levers"].items()
               if k not in tuning.LEVERS or tuning.clamp(k, v) is None]
        if bad:
            verdicts.append({"name": cand["name"], "verdict": "INVALID",
                             "ts": iso(now),
                             "why": f"registry rejected levers: {bad}"})
            send_push(f"experiment INVALID: {cand['name']}",
                      f"registry rejected {bad} — skipped, no judge slot spent")
            return save(done=done + [cand["name"]],
                        done_at={**done_at, cand["name"]: now},
                        note=f"INVALID {cand['name']}: registry rejected {bad}")
        rc = _assert_levers(cand["levers"], f"experiment {cand['name']} started",
                            f"shadow arm {SHADOW_BOT}; judge bar: {MIN_DAYS}d/"
                            f"{MIN_CLOSES} closes/+{MARGIN_PP}pp both-halves")
        if not _asserted(rc, cand["levers"]):
            # [2026-07-16] the write did not land (no DB / lock lost) — the
            # experiment did NOT start. Without this the judge stamped
            # started_ts and counted days on an arm running env defaults.
            return save(note=f"lever write did not land for {cand['name']} — "
                             f"experiment NOT started, retrying next cycle")
        send_push(f"experiment started: {cand['name']}",
                  f"shadow arm now runs {json.dumps(cand['levers'])}; "
                  f"promotion bar {MIN_DAYS:g}d / {MIN_CLOSES} closes / "
                  f"+{MARGIN_PP}pp vs live on both halves")
        return save(phase="running", current=cand["name"], spec=cand,
                    started_ts=now, note=f"STARTED {cand['name']}")

    # running / promoted use the stored spec. [2026-07-16 FIX] Guard the
    # migration from the OLD index-based state (cand_idx, no 'current'/'spec'):
    # a running/promoted phase with no valid spec used to KeyError on
    # cand['levers'] every cycle (the judge was dead ~9h). Reset to idle and
    # re-select from the pool cleanly instead.
    if _needs_reset(phase, current, spec):
        return save(phase="idle", current=None, spec={},
                    note="legacy/partial judge state (no valid spec) — reset to idle")
    cand = spec

    if phase == "running":
        # [2026-07-21 D2] a candidate the registry clamp has rewritten under us
        # is a different experiment wearing the old spec — re-spec to the
        # clamped truth with a FRESH window (pre-clamp closes must not mix into
        # the paired bar; the arm's receipts already stamp the clamped values,
        # so accrual starts immediately). Idempotent: post-re-spec the stored
        # values equal their clamp and this never fires again.
        _cand2, _changed = _respec_clamped(cand)
        if _changed:
            send_push(f"experiment RE-SPEC'd: {cand['name']} -> {_cand2['name']}",
                      f"registry clamp changed the running values {_changed}; "
                      f"window restarted so the skew gate can accrue receipts")
            return save(phase="running", current=_cand2["name"], spec=_cand2,
                        started_ts=now,
                        note=f"RE-SPEC {cand['name']} -> {_cand2['name']} "
                             f"(registry clamp {_changed}); window restarted")
        started = _num(st.get("started_ts"), now)
        rc = _assert_levers(cand["levers"], f"experiment {cand['name']} running",
                            f"started {iso(started)}")
        assert_ok = _asserted(rc, cand["levers"])
        days = (now - started) / 86400.0
        # [2026-07-17] Read the arms' build stamps off the SAME `rows` the bar
        # is computed from — one snapshot, so the drift check and the numbers it
        # gates can never describe different moments. Imported lazily and
        # guarded: implementation_shortfall is not in every image, and a dark
        # sensor must cost this organ nothing (it simply cannot claim drift).
        # [2026-07-29] ...and the arms' CURRENT bot_pnl builds are consulted
        # too, always — not only when the rows are unstamped. One snapshot is
        # still right for the NUMBERS; it was wrong for the DECISION, which
        # spends future money through today's containers. See the docstring.
        # [2026-07-28 §3c] hoisted to _drift_snap (one snapshot per cycle,
        # shared with the growth step above).
        # [2026-08-06] The CONTAINER half is still that one shared reading;
        # the ROW half is re-scoped to THIS candidate's window, because the
        # growth pair's trailing 2.5d and a candidate's `started` are
        # different samples and a hold must be about the rows this bar uses.
        _drift = _arm_drift_snapshot(rows, since_ts=started,
                                     current=_cur_drift)
        ev = (paired_eval(rows, started, now, cand_levers=cand.get("levers"),
                          drift=_drift)
              if have_ledger else {"promote": False, "why": "no ledger"})
        # ARM DRIFT -> HOLD, exactly as ARM SKEW below and for the same reason:
        # the comparison is structurally invalid, so no window fixes it and the
        # candidate is not at fault. Do not promote, do not age toward ABANDONED.
        if ev.get("arm_drift"):
            if not st.get("drift_notified"):
                send_push(f"experiment ARMS ON DIFFERENT CODE: {cand['name']}",
                          f"{ev['why']}\nthe judge is holding — deploy both arms "
                          f"to the same build; no promotion can clear until they "
                          f"match", priority="urgent")
            return save(last_eval=ev, drift_notified=True,
                        note=f"ARM DRIFT {cand['name']}: {ev['why']}")
        if st.get("drift_notified"):
            # [2026-07-21 AUDIT FIX] arms re-matched — RESTART THE CLOCK,
            # exactly as the skew and assert-fail recoveries below already
            # do and for the same reason: the days (and closes) that accrued
            # while the arms ran DIFFERENT BUILDS belong to a comparison the
            # drift hold itself ruled structurally invalid. Without this,
            # the moment the stale twin was redeployed the window could
            # already exceed MIN_DAYS and the paired bar would score a
            # mixed-build shadow tape against live — the exact mixing (bb)
            # flagged ("consider restarting the judge window at the new
            # build"). This was the one recovery of the three that kept the
            # old clock.
            return save(last_eval=ev, drift_notified=False, started_ts=now,
                        note=f"arms re-matched: {cand['name']} — experiment "
                             f"clock restarted at the common build")
        # [2026-07-16] ARM SKEW -> HOLD. The arm is closing trades but proving
        # none of them ran the candidate, so every number here is about a
        # different experiment. Do not promote (real money) and do not age
        # toward ABANDONED (a false negative retires the candidate for good).
        # Stay running and stay LOUD until the arm is fixed — fail-closed:
        # a stuck, noisy queue beats a phantom promotion.
        if ev.get("arm_skew"):
            if not st.get("skew_notified"):
                send_push(f"experiment ARM NOT APPLYING: {cand['name']}",
                          f"{ev['why']}\nthe judge is holding — no promotion "
                          f"can clear until the arm runs the candidate's bars",
                          priority="urgent")
            return save(last_eval=ev, skew_notified=True,
                        note=f"ARM SKEW {cand['name']}: {ev['why']}")
        if st.get("skew_notified"):
            # Arm recovered. Restart the clock: `days` accrued while the arm
            # was NOT applying, so without this the first good cycle could land
            # past MAX_DAYS and instantly ABANDON an experiment that had never
            # actually run. The window must cover only the applied period.
            return save(last_eval=ev, skew_notified=False, started_ts=now,
                        note=f"arm applying again: {cand['name']} — "
                             f"experiment clock restarted")
        # [2026-07-16] the re-assert did not land: the lever will TTL-expire
        # and the arm reverts to env defaults — data from here on measures the
        # wrong experiment. Same HOLD semantics as ARM SKEW (which the receipt
        # gate would eventually raise anyway once unstamped closes arrive —
        # this just refuses to promote/abandon in the gap before that).
        if not assert_ok:
            if not st.get("assert_fail_notified"):
                send_push(f"experiment lever write FAILING: {cand['name']}",
                          "the judge could not re-assert the xp levers — "
                          "holding (not promoting, not aging); the arm reverts "
                          "to env defaults when the TTL lapses",
                          priority="urgent")
            return save(assert_fail_notified=True, last_eval=ev,
                        note=f"lever re-assert did not land — holding "
                             f"{cand['name']}")
        if st.get("assert_fail_notified"):
            # writes recovered — restart the clock for the same reason as the
            # skew recovery above: days accrued while the arm ran defaults.
            return save(assert_fail_notified=False, started_ts=now,
                        last_eval=ev,
                        note=f"lever writes recovered: {cand['name']} — "
                             f"experiment clock restarted")
        if days >= MIN_DAYS and ev["promote"]:
            live_levers = {XP_TO_LIVE[k]: v for k, v in cand["levers"].items()}
            rc = _assert_levers({**cand["levers"], **live_levers},
                                f"PROMOTED {cand['name']}", ev["why"])
            # [2026-07-16] the promotion IS the write. If it did not land,
            # nothing reached real money — do not stamp phase=promoted (the
            # fade-watch would grade a lever that is not in force) and do not
            # push PROMOTED. Stay running; the bar stays cleared, retry next
            # cycle. ABANDON at MAX_DAYS cannot fire meanwhile because that
            # branch is unreachable while ev['promote'] holds (this return).
            if not _asserted(rc, {**cand["levers"], **live_levers}):
                if not st.get("assert_fail_notified"):
                    send_push(f"PROMOTION WRITE FAILED: {cand['name']}",
                              "the paired bar cleared but the live lever write "
                              "did not land — staying RUNNING and retrying; "
                              "nothing reached real money",
                              priority="urgent")
                return save(assert_fail_notified=True, last_eval=ev,
                            note=f"promotion write did not land for "
                                 f"{cand['name']} — staying running")
            verdicts.append({"name": cand["name"], "verdict": "PROMOTED",
                             "ts": iso(now), "eval": ev})
            send_push(f"PROMOTED to LIVE: {cand['name']}",
                      f"{ev['why']}\nlive levers: {json.dumps(live_levers)} "
                      f"(TTL'd; fades back to env if the live arm turns)",
                      priority="urgent")
            # [2026-07-16] stamp the live arm's PRE-promotion baseline (the
            # paired window's live mean) — the relative fade bar releases the
            # lever when the post-promotion live mean falls margin_pp below
            # this. Absent/None -> fade_check falls back to the absolute bar.
            return save(phase="promoted", promoted_ts=now, last_eval=ev,
                        assert_fail_notified=False,
                        promote_baseline={"live_mean_pct": ev.get("live_mean_pct"),
                                          "n_live": ev.get("n_live")},
                        note=f"PROMOTED {cand['name']}")
        if days >= MAX_DAYS:
            verdicts.append({"name": cand["name"], "verdict": "ABANDONED",
                             "ts": iso(now), "eval": ev})
            send_push(f"experiment abandoned: {cand['name']}",
                      f"{MAX_DAYS:g}d without clearing the bar — {ev.get('why')}")
            return save(phase="idle", done=done + [cand["name"]],
                        done_at={**done_at, cand["name"]: now}, current=None,
                        spec={}, started_ts=None,
                        cooldown_until=now + COOLDOWN_H * 3600, last_eval=ev,
                        note=f"ABANDONED {cand['name']}")
        return save(last_eval=ev, note=f"day {days:.1f}/{MIN_DAYS:g}: {ev.get('why')}")

    if phase == "promoted":
        promoted = _num(st.get("promoted_ts"), now)
        # [2026-07-16 AUDIT FIX] ledger blackout used to be fail-OPEN here:
        # fade_check was skipped but the live levers kept re-asserting every
        # cycle, so a fading promotion could never release while the judge was
        # blind. Tolerate a short outage, then stop asserting (levers expire
        # to env defaults — the safe direction). Ledger back = counter resets.
        blind = int(_num(st.get("blind_cycles")))
        if not have_ledger:
            blind += 1
            if blind > BLIND_MAX:
                return save(blind_cycles=blind,
                            note=f"ledger dark {blind} cycles (> {BLIND_MAX}) — "
                                 f"NOT re-asserting live levers; env defaults "
                                 f"return within the TTL")
        else:
            blind = 0
        # [2026-07-16] the relative fade bar measures against the live arm's
        # own pre-promotion baseline, stamped at PROMOTE. Old promotions (or a
        # regen restore predating the stamp) have none -> absolute bar only.
        baseline = (st.get("promote_baseline") or {}).get("live_mean_pct")
        fading, n, m = (fade_check(rows, promoted, now, baseline_pct=baseline)
                        if have_ledger else (False, 0, None))
        live_levers = {XP_TO_LIVE[k]: v for k, v in cand["levers"].items()}
        # 🦾 the earlier fade signal: the live lane's own paired grades
        pfading, pwhy = prop_fade(store.load_state("fleet-proprioception") or {},
                                  set(live_levers), now)
        # 🗞️ the organs' release path (21-Jul): a fresh restrict proposal on
        # a promoted lever (e.g. impl-shortfall's sustained-slip case)
        ofading, owhy = (False, None)
        if fprop is not None:
            try:
                ofading, owhy = proposal_fade(fprop.fresh_proposals(),
                                              live_levers, now)
            except Exception:
                ofading, owhy = (False, None)
        if fading or pfading or ofading:
            why = (f"live arm {m:+.2f}%/trade on the recent window (n={n} "
                   f"since promotion"
                   + (f"; pre-promotion baseline {baseline:+.2f}%"
                      if isinstance(baseline, (int, float)) else "") + ")"
                   if fading else (pwhy if pfading else owhy))
            verdicts.append({"name": cand["name"], "verdict": "FADED",
                             "ts": iso(now), "live_n": n, "live_mean_pct": m,
                             "why": why})
            send_push(f"promotion FADED: {cand['name']}",
                      f"{why} — levers released, env defaults return within "
                      f"the TTL",
                      priority="urgent")
            return save(phase="idle", done=done + [cand["name"]],
                        done_at={**done_at, cand["name"]: now}, current=None,
                        spec={}, started_ts=None, promoted_ts=None,
                        promote_baseline=None,
                        cooldown_until=now + COOLDOWN_H * 3600,
                        note=f"FADED {cand['name']} ({why})")
        rc = _assert_levers({**cand["levers"], **live_levers},
                            f"promotion {cand['name']} in force",
                            f"promoted {iso(promoted)}; live n={n} mean "
                            f"{m if m is None else round(m, 3)}%/trade")
        # [2026-07-16] re-assert failure here is inherently fail-safe (the
        # lever TTL-expires and real money reverts to env defaults) but must
        # not be SILENT: the judge would keep reporting "promotion in force"
        # while nothing was. One warn per episode; fade-watch keeps running on
        # live data either way.
        if not _asserted(rc, live_levers):
            if not st.get("assert_fail_notified"):
                send_push(f"promotion re-assert FAILING: {cand['name']}",
                          "the live lever write is not landing — it will "
                          "TTL-expire back to env defaults (fail-safe); "
                          "fade-watch continues on live data",
                          priority="urgent")
            return save(blind_cycles=blind, assert_fail_notified=True,
                        note=f"promotion re-assert did not land — lever "
                             f"expires to env defaults within the TTL")
        return save(blind_cycles=blind, assert_fail_notified=False,
                    note=f"promotion in force (live n={n}, mean "
                         f"{m if m is None else round(m, 2)}%"
                         f"{', ledger dark ' + str(blind) + ' cycles' if blind else ''})")

    return save(phase="idle", current=None, spec={},
                note=f"unknown phase {phase!r} reset")


# ---------------------------------------------------------------------------

def _selftest():
    """[(wv)] The body below was written when 💸 the Farmer's pair WAS the
    machine's default lane; the default is DERIVED now (mum today). Aim the
    machine at the Farmer for the duration so every existing assertion keeps
    testing the property it was written for, then assert the derived lane's
    own properties once the globals are restored."""
    global LIVE_BOT, SHADOW_BOT, CANDIDATES
    _save = (LIVE_BOT, SHADOW_BOT, CANDIDATES)
    LIVE_BOT, SHADOW_BOT = "perps-funding-lighter-lighter", "perps-funding-lighter-lshadow"
    CANDIDATES = list(FARMER_CANDIDATES)
    try:
        _selftest_body()
    finally:
        LIVE_BOT, SHADOW_BOT, CANDIDATES = _save
    # the derived lane: the living pair, its own candidates, its own prefix
    _lane = serial_lane_id()
    assert _lane == _lane_of(LIVE_BOT) and _lane in LANE_CANDIDATES, _lane
    assert CANDIDATES == list(LANE_CANDIDATES[_lane]), _lane
    for _c in CANDIDATES:
        assert all(str(_k).startswith(lane_prefix()) for _k in _c["levers"]), _c
    print(f"  derived lane {_lane}: {len(CANDIDATES)} candidates under {lane_prefix()}")


def _selftest_body():
    def row(bot, ts, pct):
        return {"bot": bot, "profit_ratio": pct, "close_ts": iso(ts)}

    t0 = 1_800_000_000.0
    day = 86400.0
    end = t0 + 8 * day
    # shadow beats live steadily on both halves: 32 shadow closes @ +1%,
    # 12 live closes @ +0.2%
    rows = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01) for i in range(32)]
            + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev = paired_eval(rows, t0, end)
    assert ev["promote"], ev
    assert abs(ev["gap_pp"] - 0.8) < 0.01, ev

    # one lucky half must NOT clear: shadow's edge only in h1
    rows2 = ([row(SHADOW_BOT, t0 + i * (4 * day / 16), 0.02) for i in range(16)]
             + [row(SHADOW_BOT, t0 + 4 * day + i * (4 * day / 16), -0.001)
                for i in range(16)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev2 = paired_eval(rows2, t0, end)
    assert not ev2["promote"] and "h2" in ev2["why"], ev2

    # margin gate: a 0.1pp edge is noise, not promotion
    rows3 = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), 0.003) for i in range(32)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev3 = paired_eval(rows3, t0, end)
    assert not ev3["promote"] and "margin" in ev3["why"], ev3

    # [2026-07-16 AUDIT] the margin must hold on EACH half: h1 +1.8pp but h2
    # only +0.01pp (full-window gap comfortably > 0.5pp) must NOT promote —
    # the old `shm > lvm` any-amount check let this lucky-half case through
    rows3b = ([row(SHADOW_BOT, t0 + i * (4 * day / 16), 0.02) for i in range(16)]
              + [row(SHADOW_BOT, t0 + 4 * day + i * (4 * day / 16), 0.0021)
                 for i in range(16)]
              + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev3b = paired_eval(rows3b, t0, end)
    assert not ev3b["promote"] and "h2" in ev3b["why"], ev3b

    # floors: not enough closes -> not ready
    ev4 = paired_eval(rows[:10], t0, end)
    assert not ev4["promote"] and "floors" in ev4["why"], ev4

    # shadow must be positive in its own right (beating a very negative live
    # arm with a less-negative one is damage control, not edge)
    rows5 = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), -0.001) for i in range(32)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), -0.02) for i in range(12)])
    ev5 = paired_eval(rows5, t0, end)
    assert not ev5["promote"] and "own right" in ev5["why"], ev5

    # fade: live negative at n>=FADE_N since promotion -> release
    rows6 = [row(LIVE_BOT, t0 + i * 3600, -0.005) for i in range(20)]
    fading, n, m = fade_check(rows6, t0, t0 + 2 * day)
    assert fading and n == 20 and m < 0
    fading2, n2, _ = fade_check(rows6[:5], t0, t0 + 2 * day)
    assert not fading2 and n2 == 5, "below FADE_N: keep the promotion"

    # 🦾 prop_fade: the earlier fade signal — a fresh HURTING verdict on a
    # promoted lever releases; helping/unrelated/stale/absent do nothing
    fresh_p = {"updated": iso(t0), "ttl_sec": 2700, "verdicts": {
        "live.funding.enter_apr": {"verdict": "hurting", "n": 3, "bad": 2}}}
    okp, whyp = prop_fade(fresh_p, {"live.funding.enter_apr"}, t0 + 60)
    assert okp and "HURTING" in whyp, (okp, whyp)
    assert not prop_fade(fresh_p, {"live.funding.take_profit"}, t0 + 60)[0], \
        "unrelated lever must not fade"
    assert not prop_fade({"updated": iso(t0), "ttl_sec": 2700, "verdicts": {
        "live.funding.enter_apr": {"verdict": "helping"}}},
        {"live.funding.enter_apr"}, t0 + 60)[0]
    assert not prop_fade(fresh_p, {"live.funding.enter_apr"}, t0 + 99999)[0], \
        "stale organ must not fade"
    assert prop_fade({}, {"live.funding.enter_apr"}, t0) == (False, None)
    assert prop_fade(None, {"live.funding.enter_apr"}, t0) == (False, None)

    # 🗞️ proposal_fade (21-Jul organ proposals): a fresh RESTRICT proposal on
    # a promoted lever releases — but ONLY when the release itself tightens
    # (21-Jul-b: releasing a promoted TIGHTENING would widen on 'restrict'
    # evidence). expand/unrelated/unmapped/empty do nothing.
    props = [{"lever": "live.funding.enter_apr", "value": 0.0625,
              "direction": "restrict", "set_by": "impl-shortfall",
              "reason": "sustained live slip"}]
    # promotion WIDENED the gate (0.0375 < env 0.05): release tightens -> fade
    oko, whyo = proposal_fade(props, {"live.funding.enter_apr": 0.0375}, t0)
    assert oko and "impl-shortfall" in whyo, (oko, whyo)
    # promotion TIGHTENED the gate (0.075 > env 0.05): release would WIDEN ->
    # the restrict proposal must NOT release it
    assert not proposal_fade(props, {"live.funding.enter_apr": 0.075}, t0)[0], \
        "releasing a promoted tightening is a WIDENING — refuse"
    # tp promotion (0.06 > env 0.04, 'down' = lower tighter): release tightens
    assert proposal_fade(
        [dict(props[0], lever="live.funding.take_profit")],
        {"live.funding.take_profit": 0.06}, t0)[0]
    assert not proposal_fade(props, {"live.funding.take_profit": 0.06}, t0)[0], \
        "unrelated lever must not fade"
    assert not proposal_fade(
        [dict(props[0], direction="expand")],
        {"live.funding.enter_apr": 0.0375}, t0)[0], \
        "expand proposal must NEVER release"
    assert proposal_fade([], {"live.funding.enter_apr": 0.0375}, t0) == (False, None)
    assert proposal_fade(None, {"live.funding.enter_apr": 0.0375}, t0) == (False, None)

    # [2026-07-23 AUDIT — LIVE_ENV_DEFAULTS drift guard] proposal_fade rules a
    # release "restrict-only" by reverting to the funding bot's env DEFAULT,
    # which it keeps as a HARDCODED COPY (LIVE_ENV_DEFAULTS). If that copy drifts
    # from the live bot's actual default, a 'restrict' proposal could WIDEN a
    # real-money lever (operator raises FUNDING_MAX_HOLD_H -> judge still thinks
    # 72 -> releases -> live reverts WIDER on 'restrict' evidence). The judge
    # runs in a different process from the live Farmer so it cannot read that
    # env at runtime, but it CAN pin its copy to the funding bot's SOURCE
    # defaults so the two literals never silently drift in code. (A per-service
    # env OVERRIDE stays the operator's job to mirror — see LIVE_ENV_DEFAULTS.)
    import re as _re
    import pathlib as _pl
    _fb_src = _pl.Path(__file__).with_name("lighter_funding_bot.py").read_text()
    _src_def = {}
    for _var, _key in (("FUNDING_ENTER_APR", "live.funding.enter_apr"),
                       ("FUNDING_TAKE_PROFIT", "live.funding.take_profit"),
                       ("FUNDING_MAX_HOLD_H", "live.funding.max_hold_h"),
                       ("SCAN_EXPLORE_K", "live.funding.explore_k"),
                       # [2026-08-05 (jy)] min_vol is promotable now; its
                       # source default is the literal "10e6", hence the
                       # scientific-notation e in the regex class
                       ("FUNDING_MIN_VOL", "live.funding.min_vol")):
        _mm = _re.search(_var + r'"\s*,\s*"([0-9.e]+)"', _fb_src)
        assert _mm, f"could not read {_var} default from lighter_funding_bot.py"
        _src_def[_key] = float(_mm.group(1))
    # [2026-07-28] the two non-numeric env defaults pin the same way, via
    # their documented mapping: FUNDING_CONVICTION default "off" is
    # conviction_hi 1.0 (the numeric receipt apply_levers stamps for off);
    # FUNDING_SLOPE_GATE default "on" is slope_gate 1.
    _mm = _re.search(r'FUNDING_CONVICTION"\s*,\s*"(\w+)"', _fb_src)
    assert _mm and _mm.group(1) == "off", \
        "FUNDING_CONVICTION source default changed — re-derive conviction_hi"
    _src_def["live.funding.conviction_hi"] = 1.0
    _mm = _re.search(r'FUNDING_SLOPE_GATE"\s*,\s*"(\w+)"', _fb_src)
    assert _mm and _mm.group(1) == "on", \
        "FUNDING_SLOPE_GATE source default changed — re-derive slope_gate"
    _src_def["live.funding.slope_gate"] = 1.0
    # [(wv)] 👩 mum's twins pin to lighter_family_bot's OWN class defaults
    _fam_src = _pl.Path(__file__).with_name("lighter_family_bot.py").read_text()
    _mm = _re.search(r'MUM_RSI_MAX"\s*,\s*"([0-9.]+)"', _fam_src)
    assert _mm, "could not read MUM_RSI_MAX default from lighter_family_bot.py"
    _src_def["live.mum.rsi_max"] = float(_mm.group(1))
    _mm = _re.search(r'MAX_HOLD_MIN = (\d+)\s+# 24h', _fam_src)
    assert _mm, "could not read OversoldRebound.MAX_HOLD_MIN from lighter_family_bot.py"
    _src_def["live.mum.max_hold_min"] = float(_mm.group(1))
    for _key, (_v, _dir) in LIVE_ENV_DEFAULTS.items():
        assert _src_def[_key] == _v, (
            f"LIVE_ENV_DEFAULTS[{_key}]={_v} has DRIFTED from the funding bot's "
            f"source default {_src_def[_key]}; a restrict proposal could widen a "
            f"real-money lever. Sync the two.")

    # [2026-08-05 (jy)] TWO CLASS-CLOSERS for the (ju) "unfilable candidate"
    # shape, so the NEXT promotable lever cannot arrive half-wired:
    # (1) every XP_TO_LIVE live twin has an organ release path — a promoted
    #     lever absent from LIVE_ENV_DEFAULTS is unreleasable on organ
    #     evidence ("unmapped lever: never release on a guess").
    for _lk in XP_TO_LIVE.values():
        assert _lk in LIVE_ENV_DEFAULTS, (
            f"{_lk} is promotable (XP_TO_LIVE) but has no LIVE_ENV_DEFAULTS "
            f"entry — proposal_fade could never release it")
    # (2) every XP_TO_LIVE bar is RECEIPTED by the arm, at BOTH stamp sites:
    #     close-time (_ACTIVE_BARS.update in apply_levers) and entry-time
    #     (entry_stamp's bars dict — the (ed) mid-hold rule). A consumed-but-
    #     unreceipted lever is the enter-gate-0.30@0.075 zero-accrual
    #     pathology: ran_candidate excludes every close, silently. Scoped to
    #     the two stamp sites, NOT a page-wide substring (the doctrine's
    #     structural-claim rule — "min_vol" also appears in _ENV_BARS and
    #     get_lever calls, where its presence proves nothing).
    _al_src = _fb_src.split("def apply_levers", 1)[1].split("\ndef ", 1)[0]
    _stamp_src = _al_src[_al_src.index("_ACTIVE_BARS.update"):]
    _es_src = _fb_src.split("def entry_stamp", 1)[1].split("\ndef ", 1)[0]
    _es_bars_src = _es_src[_es_src.index('"bars": {'):]
    # [(wv)] the receipt guard is PER LANE: funding keys against the Farmer
    # host's two stamp sites, mum keys against lighter_family_bot.mum_bars
    # (the ONE stamp both her hosts write) and apply_book_levers (the
    # consumer) — a consumed-but-unreceipted lever is the zero-accrual class.
    _mb_src = _fam_src.split("def mum_bars", 1)[1].split("\ndef ", 1)[0]
    # the consumer reads its bars through MUM_LEVER_ATTRS, declared just
    # above the function — the declaration + the body are the consumer
    _ab_src = _fam_src.split("MUM_LEVER_ATTRS = ", 1)[1].split("def mum_bars", 1)[0]
    for _xk in XP_TO_LIVE:
        _bar = _xk.split(".")[-1]
        if _xk.startswith("xp.mum."):
            assert f'"{_bar}":' in _mb_src, (
                f"lighter_family_bot.mum_bars stamps no {_bar} receipt — a "
                f"{_bar} judge candidate on mum would accrue ZERO closes")
            assert f'"{_bar}"' in _ab_src, (
                f"apply_book_levers does not read {_bar} — registered-but-inert")
            continue
        assert f'"{_bar}":' in _stamp_src, (
            f"apply_levers stamps no bars.{_bar} receipt — a {_bar} judge "
            f"candidate would accrue ZERO closes (ran_candidate fails closed)")
        assert f'"{_bar}":' in _es_bars_src, (
            f"entry_stamp carries no {_bar} — a mid-hold lever expiry would "
            f"rewrite the admission-time receipt (the (ed) rule)")
    # every lane's candidates are registered, in-bounds, and map to a live twin
    for _lane_cands in LANE_CANDIDATES.values():
        for c in _lane_cands:
            for k, v in c["levers"].items():
                assert tuning.clamp(k, v) == v, (k, v)
                assert tuning.clamp(XP_TO_LIVE[k], v) == v, (XP_TO_LIVE[k], v)
    assert lane_prefix("freqtrade-mum-lighter") == "xp.mum."
    assert lane_prefix("perps-funding-lighter-lighter") == "xp.funding."

    # every candidate's levers are registered, in-bounds, and map to a live twin
    for c in CANDIDATES:
        for k, v in c["levers"].items():
            assert tuning.clamp(k, v) == v, (k, v)
            lk = XP_TO_LIVE[k]
            assert tuning.clamp(lk, v) == v, (lk, v)

    # candidate_pool: static first, then admitted incubator proposals; an
    # offspring with an UNKNOWN lever is rejected (can't smuggle a lever past)
    _qnow = datetime.now(timezone.utc).timestamp()

    def _fresh(qq):
        # [2026-07-28] fixtures carry the stamps the REAL payload always has
        return dict(qq, updated=iso(_qnow), ttl_sec=10800)

    q = _fresh({"candidates": [
        {"name": "tp-0.06", "levers": {"xp.funding.take_profit": 0.06}},        # dup static
        {"name": "xp-tp-0.05", "levers": {"xp.funding.take_profit": 0.05}},     # ok
        {"name": "evil", "levers": {"xp.funding.enter_apr": 0.06, "bad.lever": 1}},  # reject
    ]})
    pool = candidate_pool(q, now=_qnow)
    names = [c["name"] for c in pool]
    # [2026-07-29 (ev)] statics lead, and slope-gate-off leads THEM: the
    # 28-Jul D7 order was reversed once the 29-Jul TP study falsified
    # tp-0.06's premise. Pinned so a silent re-shuffle of the fleet's only
    # path to live.funding.* cannot pass unnoticed.
    # [2026-08-05 (ju)] enter-gate-0.105 is pinned LAST of the statics: its
    # tape prior is negative vs shipped at measured friction (see the
    # CANDIDATES comment), so it must never outrank the supported
    # (slope-gate-off) or merely-mute (tp-0.06) candidates.
    # [2026-08-05 (jy)] min-vol-2e6 takes the (ju)-reserved slot between
    # them: unrefuted friction-tier prior outranks the negative tape prior,
    # and must never outrank the two rows (ju) pinned above it.
    # [2026-08-05 (ka)] min-vol-1e5 sits between min-vol-2e6 and the
    # negative-prior enter-gate row: its prior is an own-tape replay with
    # both halves positive (see its CANDIDATES block) — reordering any of
    # the five reddens here.
    # [2026-08-06 (ld)] tp-0.06 MOVED 2nd -> 4th, behind both min_vol rows.
    # The pin's PURPOSE is unchanged and this is not a loosening of it: the
    # queue is still strictly ordered by PRIOR STRENGTH, which is the rule
    # (ju) set. What changed is that the rule is now applied to tp-0.06 as
    # well — its prior is MUTE (no take_profit value both-halves positive;
    # the universe flips the sign) while both min_vol rows carry positive or
    # unrefuted priors, so it can no longer consume a ~2-week serial slot
    # ahead of them. Full argument in the CANDIDATES comment above tp-0.06.
    # The invariant this asserts is the ORDERING RULE, spelled out below so a
    # future re-shuffle has to argue with the rule rather than edit a literal.
    # [2026-08-13 (ln)] min-vol-1e5 and min-vol-2e6 SWAPPED, arguing with
    # the rule as this block demands: 1e5's prior is the queue's only
    # CALIBRATED OWN-TAPE replay with both halves positive (+$14.83 vs the
    # incumbent's +$4.01, robust at p90) — a DIRECT measurement — while
    # 2e6's prior is indirect (the carry sibling trades the tier + the
    # friction table). (ka) ranked 2e6 first as a de-risking SEQUENCE
    # preference dressed in the prior frame; with the Farmer-live t bar
    # now UNREACHABLE at its current mean (~1,152 closes needed), the
    # 7-day de-risking slot costs more than it insures. Operator-directed
    # 13-Aug, executed under the real-money grant; paired bar unchanged.
    # [2026-08-20 (sk)] max-hold-24 leads. Its prior is the strongest this
    # queue has carried: a CALIBRATED own-tape replay (27/27 tp, 97.9%
    # non-barrier reproduced), a single interior peak reproduced INDEPENDENTLY
    # on both arms, two bootstraps (trade P<=0 = 0.0017; symbol-cluster CI
    # [+0.049, +0.468]), a coin jackknife that no drop breaks, and — the part
    # nothing else in the queue has — an IDENTICALLY CONDITIONED placebo
    # (matched survivors, same barriers, same 24h survival requirement) that
    # rules out the martingale explanation at P=0.011. It is also the only
    # candidate that moves the DRAWDOWN bar (realised maxDD 41.99 -> 14.52pp).
    assert names[:6] == ["max-hold-24", "slope-gate-off", "min-vol-1e5",
                         "min-vol-2e6", "tp-0.06", "enter-gate-0.105"], names
    # the rule itself, asserted independently of the literal above: every
    # static is ranked by the strength of its recorded prior, strongest first.
    _PRIOR_RANK = {"max-hold-24": 0,       # calibrated own-tape replay +
                                           # CONDITIONED placebo + two
                                           # bootstraps + coin jackknife, and
                                           # both arms peak at the same cell
                                           # independently ((sk))
                   "slope-gate-off": 1,    # venue-supported ((dp))
                   "min-vol-1e5": 2,       # calibrated own-tape replay, both
                                           # halves +ve — strong DIRECT prior
                   "min-vol-2e6": 3,       # unrefuted friction-tier prior —
                                           # indirect ((ln) swap)
                   "tp-0.06": 4,           # MUTE — no both-halves-positive tp
                   "enter-gate-0.105": 5}  # tape prior AGAINST it
    _ranks = [_PRIOR_RANK[n] for n in names[:6]]
    assert _ranks == sorted(_ranks), \
        f"statics must run strongest-prior-first ((ju)'s rule): {names[:6]}"
    assert "xp-tp-0.05" in names and "evil" not in names, names
    assert names.count("tp-0.06") == 1, "dup name deduped"

    # [2026-07-17 AUDIT] NEGATIVE FIXTURE for the signature dedup — the shape
    # the incubator ACTUALLY emits: same experiment, name it can never share
    # with a static. The fixture above (dup NAME) passed throughout the bug's
    # life, so it proved nothing about the real failure. 48 vs 48.0 pins the
    # float normalisation; the last row proves a genuinely NEW experiment
    # still gets in (dedup must not become a wall).
    q2 = _fresh({"candidates": [
        {"name": "xp-take_profit-0.06", "levers": {"xp.funding.take_profit": 0.06}},
        {"name": "xp-enter_apr-0.0625", "levers": {"xp.funding.enter_apr": 0.0625}},
    ]})
    n2 = [c["name"] for c in candidate_pool(q2, now=_qnow)]
    assert n2 == ["max-hold-24", "slope-gate-off", "min-vol-1e5",
                  "min-vol-2e6", "tp-0.06",
                  "enter-gate-0.105", "xp-enter_apr-0.0625"], n2
    # the int-vs-float signature normalisation stays pinned by the direct
    # _lever_sig asserts below (the hold statics that used to pin it via a
    # 96-vs-96.0 dedup are withdrawn — see CANDIDATES)
    # two offspring proposing the SAME novel experiment: first wins, no dup slot
    q3 = _fresh({"candidates": [
        {"name": "child-a", "levers": {"xp.funding.enter_apr": 0.0625}},
        {"name": "child-b", "levers": {"xp.funding.enter_apr": 0.0625}},
    ]})
    assert [c["name"] for c in candidate_pool(q3, now=_qnow)][-1] == "child-a"
    assert len(candidate_pool(q3, now=_qnow)) == len(CANDIDATES) + 1

    # [2026-07-28 REVIEW] QUEUE FRESHNESS, fail-closed — the live defect shape:
    # an 11-day-stale queue (its own ttl_sec 3h) must contribute NOTHING, and
    # a payload with no freshness stamp at all must be treated the same way.
    # Mutation check: bypassing the staleness gate turns the first assert red
    # (the stale child would appear in the pool).
    q4 = dict(q3, updated=iso(_qnow - 11 * 86400))          # 11d old, ttl 3h
    assert [c["name"] for c in candidate_pool(q4, now=_qnow)] == \
        [c["name"] for c in CANDIDATES], "stale queue must yield statics only"
    q5 = {"candidates": q3["candidates"]}                    # no stamp at all
    assert [c["name"] for c in candidate_pool(q5, now=_qnow)] == \
        [c["name"] for c in CANDIDATES], "unstamped queue must fail closed"
    # boundary: just inside TTL is still fresh (10799 not 10800 — iso()
    # truncates to whole seconds, so the exact edge rounds stale)
    q6 = dict(q3, updated=iso(_qnow - 10799))
    assert "child-a" in [c["name"] for c in candidate_pool(q6, now=_qnow)]

    # [2026-07-28 REVIEW] _arm_drift_snapshot: the drift sensor must FIRE on
    # unstamped ledger rows when the arms' CURRENT builds differ (the defect:
    # 0/143 rows stamped -> row-based None forever -> the HOLD never fired on
    # a live build divergence impl-shortfall was reporting simultaneously).
    #
    # [2026-07-29 ROW SENIORITY WITHDRAWN — deliberate reversal of the assert
    # that used to live here.] That rule made a stamped-and-matching row pair a
    # FINAL all-clear that the current-build check could not override. Measured
    # live the same day: both Farmer arms' newest stamped rows read
    # ddd019900bf0 (28-Jul 20:00/20:02) while bot_pnl had them on
    # c2d0ccc64d7d / 89c2c56b2da5 — two different builds, neither the certified
    # one. The old assert was not testing a defect-free property; it was
    # pinning the blind spot. A promotion spends FUTURE money through the code
    # running NOW, so the current check always gets a vote. Restrict-only:
    # arm_drift claims only on positive evidence, so this adds holds and clears
    # none, and unknown stays quiet.
    # Mutation check: dropping the bot_pnl consult turns asserts 1 AND 3 red;
    # letting `unknown` count as drift turns assert 2 red.
    try:
        import implementation_shortfall as _isf_probe   # noqa: F401
        _isf_ok = True
    except Exception:      # noqa: BLE001
        _isf_ok = False
    _r_unstamped = [{"bot": LIVE_BOT, "extra": {"bars": {}}},
                    {"bot": SHADOW_BOT, "extra": {"bars": {}}}]
    _pnl_drift = [{"bot": LIVE_BOT, "extra": {"build": "aaa"}},
                  {"bot": SHADOW_BOT, "extra": {"build": "bbb"}}]
    _pnl_same = [{"bot": LIVE_BOT, "extra": {"build": "ccc"}},
                 {"bot": SHADOW_BOT, "extra": {"build": "ccc"}}]
    if _isf_ok:
        # fallback fires: unstamped rows + drifted current builds -> HOLD
        assert _arm_drift_snapshot(_r_unstamped, fetch=lambda: _pnl_drift) == \
            {"live": "aaa", "shadow": "bbb", "source": "bot_pnl-current"}
        # fallback stays quiet when current builds match (no false hold)
        assert _arm_drift_snapshot(_r_unstamped, fetch=lambda: _pnl_same) is None
        # THE 29-Jul REVERSAL, asserted: rows agree on a build, but the arms
        # are on two different builds NOW -> HOLD. This is the exact live
        # shape (rows ddd0199.., arms c2d0ccc.. vs 89c2c56..); the previous
        # contract returned None here and let the promotion proceed.
        _r_same = [{"bot": LIVE_BOT, "extra": {"build": "x"}},
                   {"bot": SHADOW_BOT, "extra": {"build": "x"}}]
        assert _arm_drift_snapshot(_r_same, fetch=lambda: _pnl_drift) == \
            {"live": "aaa", "shadow": "bbb", "source": "bot_pnl-current"}
        # ...and converged rows + converged current builds still clear
        assert _arm_drift_snapshot(_r_same, fetch=lambda: _pnl_same) is None
        # row-based POSITIVE drift: DISJOINT build sets, the only shape that
        # actually proves the two samples came from different code ((lf))
        _r_drift = [{"bot": LIVE_BOT, "extra": {"build": "p"}},
                    {"bot": SHADOW_BOT, "extra": {"build": "q"}}]
        assert _arm_drift_snapshot(_r_drift, fetch=lambda: _pnl_same) == \
            {"live": "p", "shadow": "q", "source": "rows-disjoint"}
        # a dead fetch costs nothing, claims nothing
        def _boom():
            raise RuntimeError("db down")
        assert _arm_drift_snapshot(_r_unstamped, fetch=_boom) is None

        # [2026-08-06] THE WINDOW SCOPING, asserted on the shape that was
        # measured live: the live arm's newest close predates the deploy and
        # the candidate window opened AFTER it, so the only rows that can
        # reach the bar are converged — no hold. Unscoped (since_ts=None)
        # the same rows raise one, which is exactly the defect.
        # Mutation check: dropping the _rows_since filter turns assert A red;
        # letting the scoping swallow the container half turns assert C red.
        # close_ts carries the ISO string the ledger actually stores (the (hj)
        # rule: the fixture is the publisher's shape, not a convenient one —
        # an epoch float here would make every row unparseable and every
        # assertion below pass vacuously).
        _w0 = 1_700_000_000.0                  # window opens here
        _r_prewindow = [
            {"bot": LIVE_BOT, "close_ts": iso(_w0 - 3600),
             "extra": {"build": "old"}},
            {"bot": SHADOW_BOT, "close_ts": iso(_w0 + 60),
             "extra": {"build": "new"}},
        ]
        # A — in-window rows are converged (the live row is out of scope): quiet
        assert _arm_drift_snapshot(_r_prewindow, since_ts=_w0,
                                   fetch=lambda: _pnl_same) is None
        # B — the same rows, unscoped: the build SETS are disjoint ({old} vs
        #     {new}), so a claim here is correct even without a window. This
        #     was the (la) shape; (lf) keeps it true for the right reason.
        assert _arm_drift_snapshot(_r_prewindow, fetch=lambda: _pnl_same) == \
            {"live": "old", "shadow": "new", "source": "rows-disjoint"}
        # C — scoping never blinds the CONTAINER half: rows clean in-window,
        #     containers on two builds -> hold. This is what makes dropping
        #     the pre-window rows safe.
        assert _arm_drift_snapshot(_r_prewindow, since_ts=_w0,
                                   fetch=lambda: _pnl_drift) == \
            {"live": "aaa", "shadow": "bbb", "source": "bot_pnl-current"}
        # D — real drift INSIDE the window is still caught
        _r_inwindow = [
            {"bot": LIVE_BOT, "close_ts": iso(_w0 + 30), "extra": {"build": "p"}},
            {"bot": SHADOW_BOT, "close_ts": iso(_w0 + 60), "extra": {"build": "q"}},
        ]
        assert _arm_drift_snapshot(_r_inwindow, since_ts=_w0,
                                   fetch=lambda: _pnl_same) == \
            {"live": "p", "shadow": "q", "source": "rows-disjoint"}
        # D2 [(lf)] — THE DEFECT (la) LEFT BEHIND, and the reason this rule
        #     changed. A ROLLING DEPLOY inside a wide window: both arms close
        #     under the old build AND the new one, but the slower arm's newest
        #     close is still the old build. Newest-vs-newest called that drift;
        #     the sets INTERSECT, so it is timing, not divergence. This is the
        #     exact live shape that held a growth bar with both floors met.
        _r_rolling = [
            {"bot": LIVE_BOT, "close_ts": iso(_w0 + 10), "extra": {"build": "A"}},
            {"bot": LIVE_BOT, "close_ts": iso(_w0 + 20), "extra": {"build": "B"}},
            {"bot": SHADOW_BOT, "close_ts": iso(_w0 + 15), "extra": {"build": "A"}},
            {"bot": SHADOW_BOT, "close_ts": iso(_w0 + 25), "extra": {"build": "B"}},
            {"bot": SHADOW_BOT, "close_ts": iso(_w0 + 40), "extra": {"build": "C"}},
        ]
        assert _arm_drift_snapshot(_r_rolling, since_ts=_w0,
                                   fetch=lambda: _pnl_same) is None, \
            "overlapping build sets are a shared deploy line, not drift"
        # ...and the container half is still free to hold on the same rows
        assert _arm_drift_snapshot(_r_rolling, since_ts=_w0,
                                   fetch=lambda: _pnl_drift) is not None
        # E — an unparseable stamp is excluded, matching arm_trades' own
        #     `continue`: the bar cannot place it, so neither may the sensor
        _r_junkts = [
            {"bot": LIVE_BOT, "close_ts": "not-a-time", "extra": {"build": "old"}},
            {"bot": SHADOW_BOT, "close_ts": iso(_w0 + 60),
             "extra": {"build": "new"}},
        ]
        assert _arm_drift_snapshot(_r_junkts, since_ts=_w0,
                                   fetch=lambda: _pnl_same) is None
        # F — the pre-computed container half is used verbatim when the rows
        #     are quiet (one bot_pnl reading per cycle, however many windows)
        assert _arm_drift_snapshot(_r_prewindow, since_ts=_w0,
                                   current=None, fetch=_boom) is None
        assert _arm_drift_snapshot(
            _r_prewindow, since_ts=_w0, fetch=_boom,
            current={"live": "a", "shadow": "b", "source": "bot_pnl-current"}
        ) == {"live": "a", "shadow": "b", "source": "bot_pnl-current"}
        # G — growth_window_start is the ONE definition of that window
        assert growth_window_start(_w0) == _w0 - GROWTH_WINDOW_D * 86400
    else:
        # image without the organ: the sensor is dark and must claim nothing
        assert _arm_drift_snapshot(_r_unstamped, fetch=lambda: _pnl_drift) is None
    assert _lever_sig({"a": 1}) == _lever_sig({"a": 1.0})
    assert _lever_sig({"a": "x"}) == (("a", "x"),)      # non-numeric survives
    # next_candidate: skips done + current, name-based (pool may grow)
    # [2026-07-29 (ev)] slope-gate-off is FIRST — it is the only static with a
    # Lighter-tape prior in the supported direction (gate-on -$14.90 vs
    # gate-off +$34.07).
    # [2026-08-06 (ld)] ...and the two min_vol rows follow it, ahead of the
    # merely-mute tp-0.06 — the serial slot goes to the stronger prior, which
    # is (ju)'s rule applied to tp-0.06 as well. Walked one slot at a time so
    # the DRAIN ORDER is pinned, not just the list: this is what actually
    # decides which question the fleet asks next.
    # [2026-08-20 (sk)] max-hold-24 drains FIRST — the queue's strongest prior
    # (see its CANDIDATES note) and the only candidate that moves the drawdown
    # bar. Walked one slot at a time so the DRAIN ORDER is pinned, not just the
    # list: this is what actually decides which question the fleet asks next.
    _drained = []
    for _expect in ("max-hold-24", "slope-gate-off", "min-vol-1e5",
                    "min-vol-2e6", "tp-0.06", "enter-gate-0.105"):
        assert next_candidate(pool, list(_drained), None)["name"] == _expect, \
            (_drained, _expect)
        _drained.append(_expect)
    # the statics precede queue proposals by pool construction (statics first)
    assert next_candidate(pool, _drained, None)["name"] == "xp-tp-0.05"
    assert next_candidate(pool, [c["name"] for c in pool], None) is None  # exhausted

    # ---- [2026-07-21 D2] re-spec migration: the clamp-inverted candidate ----
    # The live defect verbatim: enter-gate-0.30 stored 0.30, the registry
    # clamps to its hi -> re-spec renames honestly, rewrites levers, reports
    # the change. [2026-07-30 A1] the fixture reads the clamp ceiling FROM
    # the registry rather than pinning 0.075: the operator-signed widening
    # (hi -> 0.12) moved the cage, and this test pins the RE-SPEC MECHANISM,
    # not the cage's width — the registry's own selftest owns the bounds.
    import fleet_tuning as _ft
    _hi = _ft.LEVERS["xp.funding.enter_apr"]["hi"]
    _c, _ch = _respec_clamped({"name": "enter-gate-0.30",
                               "levers": {"xp.funding.enter_apr": 0.30}})
    assert _ch == {"xp.funding.enter_apr": (0.30, _hi)}, _ch
    assert _c["levers"] == {"xp.funding.enter_apr": _hi}, _c
    assert _c["name"] == f"enter-gate-0.30@enter_apr={_hi}", _c["name"]
    # idempotent: the re-spec'd candidate needs no further re-spec
    _c2, _ch2 = _respec_clamped(_c)
    assert _ch2 == {} and _c2 == _c, (_c2, _ch2)
    # in-bounds candidate untouched; unclampable lever left for INVALID path
    assert _respec_clamped({"name": "tp-0.06",
                            "levers": {"xp.funding.take_profit": 0.06}})[1] == {}
    assert _respec_clamped({"name": "bad",
                            "levers": {"no.such.lever": 1}})[1] == {}

    # migration guard: OLD index-based state (running phase, no current/spec)
    # must trigger a reset instead of KeyError on cand['levers']
    assert _needs_reset("running", None, {}) is True          # the 16-Jul crash
    assert _needs_reset("promoted", None, {}) is True
    assert _needs_reset("running", "x", {"name": "y", "levers": {}}) is True  # mismatch
    assert _needs_reset("running", "x", {"name": "x"}) is True  # spec lacks 'levers'
    _ok_lever = next(iter(XP_TO_LIVE))
    assert _needs_reset("running", "x", {"name": "x", "levers": {_ok_lever: 1}}) is False
    assert _needs_reset("idle", None, {}) is False             # idle never resets here
    # [2026-07-16 AUDIT] shapes that passed the old guard but crashed downstream
    assert _needs_reset("running", "x", {"name": "x", "levers": None}) is True
    assert _needs_reset("running", "x", {"name": "x", "levers": {}}) is True
    assert _needs_reset("promoted", "x", {"name": "x", "levers": {"gone.lever": 1}}) is True
    # corrupt numeric state fields must degrade, not crash-loop
    assert _num("not-a-ts") == 0.0 and _num(None, 5.0) == 5.0 and _num("7") == 7.0

    # ---- [2026-07-16] ARM-SKEW gate: enactment is not application ---------
    # Regression guard for the live defect: the judge asserted xp.* levers at a
    # frozen shadow arm with no lever code (30 closes, 0 receipts), so the bar
    # scored version skew and would have promoted an untested value to REAL
    # MONEY. A receipt is stamped only inside the arm's apply_levers(), so a
    # missing one is disproof. This gate must stay fail-CLOSED.
    def rowb(bot, ts, pct, bars=None):
        r = {"bot": bot, "profit_ratio": pct, "close_ts": iso(ts), "extra": {}}
        if bars is not None:
            r["extra"] = {"bars": bars}
        return r

    _cand = {"xp.funding.enter_apr": 0.3}
    _applied = {"arm": "lighter_shadow", "enter_apr": 0.3}
    _default = {"arm": "lighter_shadow", "enter_apr": 0.4}   # what a deaf arm runs

    assert ran_candidate(rowb(SHADOW_BOT, t0, 0.01, _applied), _cand) is True
    assert ran_candidate(rowb(SHADOW_BOT, t0, 0.01), _cand) is False      # no receipt
    assert ran_candidate(rowb(SHADOW_BOT, t0, 0.01, _default), _cand) is False
    assert ran_candidate({"bot": SHADOW_BOT}, _cand) is False             # no extra

    # shadow crushes live, but proves nothing: must NOT promote
    _sk = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.05) for i in range(32)]
           + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    assert paired_eval(_sk, t0, end)["promote"] is True          # old bar: promotes
    _skv = paired_eval(_sk, t0, end, cand_levers=_cand)          # gated: blocked
    assert _skv["promote"] is False and _skv["arm_skew"] is True, _skv
    assert _skv["n_shadow_closes"] == 32, _skv

    # ---- [2026-07-17] ARM-DRIFT gate: same arms, or no verdict -------------
    # The arms live in different Railway services on separate deploy clocks —
    # DELIBERATELY, because the control arm's container holds zero keys and so
    # cannot trade real money. Drift is therefore possible BY DESIGN, and this
    # gate is what keeps it harmless: a comparison across two builds measures a
    # code delta, not edge, and no window makes it valid. Synthetic throughout,
    # so it asserts the GATE, not tonight's (currently aligned) fleet.
    _win = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.05) for i in range(32)]
            + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    assert paired_eval(_win, t0, end)["promote"] is True, "baseline must promote"
    _dv = paired_eval(_win, t0, end, drift={"live": "aaa", "shadow": "bbb"})
    assert _dv["promote"] is False and _dv["arm_drift"] == {"live": "aaa", "shadow": "bbb"}, _dv
    assert "different code" in _dv["why"].lower(), _dv["why"]
    # unknown is NOT drift — the rollout state must not freeze the queue
    assert paired_eval(_win, t0, end, drift=None)["promote"] is True
    # drift is checked BEFORE skew: "are these the same experiment at all?" is
    # the prior question to "is the arm running the candidate?"
    _both = paired_eval(_win, t0, end, cand_levers=_cand,
                        drift={"live": "aaa", "shadow": "bbb"})
    assert _both.get("arm_drift") and not _both.get("arm_skew"), _both

    # the gate is not a brick wall — an APPLYING arm still clears
    _ap = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01, _applied) for i in range(32)]
           + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    _apv = paired_eval(_ap, t0, end, cand_levers=_cand)
    assert _apv["promote"] is True and not _apv.get("arm_skew"), _apv

    # rows carrying the WRONG bars are excluded from n and the mean
    _mx = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01, _applied) for i in range(32)]
           + [rowb(SHADOW_BOT, t0 + i * (8 * day / 8), -0.99, _default) for i in range(8)]
           + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    _mxv = paired_eval(_mx, t0, end, cand_levers=_cand)
    assert _mxv["n_shadow"] == 32 and _mxv["shadow_mean_pct"] > 0, _mxv

    # cand_levers=None must be byte-identical to the historical bar
    assert paired_eval(_sk, t0, end) == paired_eval(_sk, t0, end, cand_levers=None)

    # ---- [2026-07-16] per-half sample floors -------------------------------
    # Full-window floors said nothing about the halves: 25 shadow closes in h1
    # and 5 in h2 clears 30 overall, but h2's "both-halves" verdict rides on 5
    # trades. Must hold as under-powered, not promote.
    _lop = ([rowb(SHADOW_BOT, t0 + i * (4 * day / 25), 0.01, _applied) for i in range(25)]
            + [rowb(SHADOW_BOT, t0 + 4 * day + i * (4 * day / 5), 0.01, _applied)
               for i in range(5)]
            + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    _lv2 = paired_eval(_lop, t0, end, cand_levers=_cand)
    assert _lv2["promote"] is False and "under-powered" in _lv2["why"], _lv2
    # one live trade per half must never carry a promotion: 10 live closes all
    # in h1, h2 has 1 — the exact noise-amplifier shape
    _one = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01, _applied) for i in range(32)]
            + [rowb(LIVE_BOT, t0 + i * (4 * day / 10), 0.002) for i in range(10)]
            + [rowb(LIVE_BOT, t0 + 5 * day, 0.002)])
    _ov = paired_eval(_one, t0, end, cand_levers=_cand)
    assert _ov["promote"] is False and "under-powered" in _ov["why"], _ov
    # the original promote case still clears (16/16 + 6/6 split >= 15/5 floors)
    assert paired_eval(rows, t0, end)["promote"], "per-half floors broke the base case"

    # ---- [2026-07-16] relative + rolling fade bar --------------------------
    # edge destroyed but not inverted: baseline +0.8, post-promotion +0.1 —
    # the old absolute bar (m<0) never released this. n=20 @ FADE_N=15.
    _fade_rows = [rowb(LIVE_BOT, t0 + i * 3600, 0.001) for i in range(20)]
    f, n, m = fade_check(_fade_rows, t0 - 1, end, fade_n=15, baseline_pct=0.8,
                         margin_pp=0.5)
    assert f is True and n == 20, (f, n, m)
    # same data, no baseline (old promotion) -> absolute bar only -> no release
    f2, _, _ = fade_check(_fade_rows, t0 - 1, end, fade_n=15)
    assert f2 is False, "missing baseline must fall back to the absolute bar"
    # healthy: post-promotion holds near baseline -> no release
    _ok_rows = [rowb(LIVE_BOT, t0 + i * 3600, 0.007) for i in range(20)]
    f3, _, _ = fade_check(_ok_rows, t0 - 1, end, fade_n=15, baseline_pct=0.8,
                          margin_pp=0.5)
    assert f3 is False, "a healthy promotion must not release"
    # ROLLING beats cumulative: 30 early wins then 15 recent losses — the
    # cumulative mean stays positive (the old unreachable-release bug), the
    # rolling window sees the fade
    _late = ([rowb(LIVE_BOT, t0 + i * 3600, 0.02) for i in range(30)]
             + [rowb(LIVE_BOT, t0 + (40 + i) * 3600, -0.005) for i in range(15)])
    f4, _, m4 = fade_check(_late, t0 - 1, end, fade_n=15)
    assert f4 is True and m4 < 0, (f4, m4)
    assert 100.0 * (30 * 0.02 - 15 * 0.005) / 45 > 0  # cumulative would miss it
    # under FADE_N closes -> no signal (fail-safe unchanged)
    assert fade_check(_fade_rows[:5], t0 - 1, end, fade_n=15,
                      baseline_pct=9.9)[0] is False

    # ---- [2026-07-16] _asserted: a dropped rail write is not an assert -----
    assert _asserted({"levers": {"a": {}, "b": {}}}, {"a": 1, "b": 2}) is True
    assert _asserted(None, {"a": 1}) is False                # write_levers None
    assert _asserted({"levers": {"a": {}}}, {"a": 1, "b": 2}) is False  # partial
    assert _asserted({}, {"a": 1}) is False
    assert _asserted({"levers": {"a": {}}}, {}) is False     # nothing wanted

    # [2026-07-17 IMB-07] fallback-only retry: untried candidates ALWAYS
    # beat an aged-out done entry; a retry happens only when nothing
    # untried remains (plain aging was verify-refuted — pool-order statics
    # rotate slower than the retry window and would starve offspring)
    _pool = [{"name": "s1", "levers": {}}, {"name": "s2", "levers": {}},
             {"name": "off1", "levers": {}}]
    c, r = pick_candidate(_pool, ["s1"], {"s1": t0 - 40 * day}, None, t0,
                          28 * day)
    assert c["name"] == "s2" and not r, "untried static beats aged retry"
    c, r = pick_candidate(_pool, ["s1", "s2"], {"s1": t0 - 40 * day,
                                                "s2": t0 - day}, None, t0,
                          28 * day)
    assert c["name"] == "off1" and not r, \
        "NEVER-tried offspring beats an aged static (the starving case)"
    c, r = pick_candidate(_pool, ["s1", "s2", "off1"],
                          {"s1": t0 - 40 * day, "s2": t0 - day,
                           "off1": t0 - day}, None, t0, 28 * day)
    assert c["name"] == "s1" and r, "nothing untried -> retry the aged one"
    c, r = pick_candidate(_pool, ["s1", "s2", "off1"],
                          {k: t0 - day for k in ("s1", "s2", "off1")},
                          None, t0, 28 * day)
    assert c is None and not r, "nothing untried, nothing aged -> exhausted"

    # ---- [(ti)] v2.0: the multi-pair census + the imported vocabulary ------
    assert _bus is not None, "selftest requires fleet_bus (same image)"
    _VOC = _bus.XP_JUDGE_PHASES
    # every phase this module can emit is IN the imported vocabulary — the
    # (tb) inversion: a new phase that skips fleet_bus reddens THIS build,
    # instead of being erased by the validator downstream.
    for _p in ("idle", "running", "promoted", "stood_down", "unjudgeable"):
        assert _p in _VOC, _p
    assert set(_bus.XP_JUDGE_UNJUDGEABLE) >= {
        "policy_unstamped", "policy_mismatch", "capacity_mismatch",
        "parity_unreadable", "live_row_dark"}

    _psp = dict(_bus.JUDGED_PAIRS["georgia"])
    # [2026-08-26] the fixture stamps georgia's REQUIRED field aligned on both
    # arms, because it is a SEPARATE (unwaived) block with its own case below
    # — a fixture diverging on two fields at once cannot say which produced
    # the verdict.
    _stamp = {"strategy": "daytrader-15m", "venue": "lighter_live",
              "stoploss": -0.05, "roi": {"0": 0.02}, "sides": ["long"],
              "scan_order": "diversified", "max_entries_per_hour": 3}
    _sstamp = dict(_stamp, venue="lighter_shadow", scan_order="list")

    def _led(bot, pol, age=60):
        # [(ts)] the PUBLISHER'S ORDER, not just its fields: `fetch_paper_trades`
        # hands rows back `ORDER BY closed_at DESC NULLS LAST`. The pre-(ts)
        # fixture built one UNDATED row per bot, where a newest-vs-oldest slice
        # is unobservable by construction — which is how the census shipped
        # reading each arm's OLDEST 30 closes.
        # [(uy)] ...AND THE PUBLISHER'S KEY. This built `closed_at` — the DB
        # COLUMN — which `fetch_paper_trades` normalises to `close_ts` and never
        # emits. So every ordering assertion below was driving a shape the judge
        # is never handed, and `_close_rank` reading `closed_at` was invisible to
        # all of them while ranking every REAL row (False, 0.0). Driven as the
        # publisher builds it, so the sort has to do the work.
        return {"bot": bot, "close_ts": iso(t0 - age),
                "extra": ({"policy": pol} if pol else {})}

    def _row(bot, max_open=5, age=60):
        # [(tj)] the PUBLISHER'S shape: fetch_bot_pnl carries `updated_at`
        # (ISO), never a derived age_sec — the first live census read every
        # row dark because the fixture here was written in the dashboard
        # feed's shape instead ((hj)). Driven as the publisher builds it.
        # [(uy)] ...except for `ttl_sec: 900`, which it ALSO built and which
        # `fetch_bot_pnl` does not emit either — `ttl_sec` occurs zero times in
        # bot_pnl_store.py. That phantom fed `3 * (row.ttl_sec or 900)`, so the
        # fixture took the per-row branch while production took the fallback,
        # and the live number was unmutatable behind it. Gone; the bar is
        # `PAIR_ROW_STALE_S` and the fixture now drives the real one.
        return {"bot": bot, "updated_at": iso(t0 - age),
                "extra": {"max_open": max_open}}

    _lb, _sb = _psp["live_bot"], _psp["shadow_bot"]
    # 🔮 georgia joined RETIRED_LIVE_ARMS at (wg), which short-circuits every
    # precheck below to stood_down BEFORE the mechanics under test can run —
    # CI caught this selftest asserting unjudgeable against her registry state.
    # Force her live for the mechanics block via her own documented override
    # (the same pattern (wg) applied to the six pytest suites), restore after;
    # the stood_down branch is asserted on its own below, against BOTH retired
    # pairs, so the registry's word is still driven.
    _geo_ov = os.environ.get("GEORGIA_LIVE_RETIRED_OVERRIDE")
    os.environ["GEORGIA_LIVE_RETIRED_OVERRIDE"] = "run"
    # dark live row -> live_row_dark (a registry entry must not outlive its
    # row: the audit-scope stale-list class, made a named ageable state)
    _v = _pair_precheck("georgia", _psp, [], [], t0)
    assert _v["phase"] == "unjudgeable" and \
        _v["unjudgeable"]["reason"] == "live_row_dark", _v
    # unstamped arms -> policy_unstamped NAMING the stamper files
    _v = _pair_precheck("georgia", _psp, [_led(_lb, None), _led(_sb, None)],
                        [_row(_lb), _row(_sb)], t0)
    assert _v["unjudgeable"]["reason"] == "policy_unstamped", _v
    assert "lighter_family_bot.py" in _v["unjudgeable"]["detail"], _v
    # [(uy)] THE SORT KEY MUST FIRE ON THE PUBLISHER'S OWN KEY. `_close_rank`
    # read `closed_at` — the DB COLUMN, not the key `fetch_paper_trades`
    # emits — so it returned the NULLS-LAST bucket for every REAL row and the
    # sort below was a stable no-op. Asserted DIRECTLY on the rank, because
    # every ordering case that follows can be satisfied by delivery order
    # alone: they are what the sort is FOR, not proof that it ran.
    # (mutation: `close_ts` -> `closed_at` in _close_rank => this reddens)
    _ranked = _close_rank(_led(_sb, None, age=1))
    assert _ranked[0] is True and _ranked[1] > 0.0, \
        ("_close_rank is inert on a publisher-shaped row", _ranked)
    # ...and it is ORDERING, not merely non-degenerate: newer outranks older.
    assert _close_rank(_led(_sb, None, age=1)) > \
        _close_rank(_led(_sb, None, age=900))
    # [(ts)] THE INCIDENT: an arm that has JUST started stamping. 30 older
    # unstamped closes + 1 stamped newest, delivered NEWEST-FIRST exactly as
    # `fetch_paper_trades` returns them. The shipped `mine[-look:]` scored the
    # OLDEST 30 and read `0/30` — indistinguishable from an arm that stamps
    # nothing, which is what held georgia unjudgeable on 26-Aug while its
    # first stamped close sat in the ledger. (mutation: restore `[-look:]`, or
    # `stamped[-1]`, => this reddens)
    _fresh = [_led(_sb, _sstamp, age=1)] + \
             [_led(_sb, None, age=100 + i) for i in range(30)]
    _p, _n, _t = _latest_policy_stamp(_fresh, _sb)
    assert (_n, _t) == (1, 30), (_n, _t)
    assert _p == _sstamp, _p
    # ORDER-INDEPENDENT: the same rows any which way give the same answer, so
    # this cannot be "fixed" by flipping the slice to suit one caller.
    # [(uy)] THIS ONLY BECAME A TEST WHEN THE FIXTURE ABOVE STARTED BUILDING
    # THE PUBLISHER'S KEY. Written against `closed_at` rows it exercised a
    # shape the judge is never handed, and passed while the sort was inert on
    # every real one — a permutation is only a test of a SORT if the sort key
    # can read the rows. The middle permutation is deliberately neither the
    # publisher's order nor its reverse, so a fix that just flips the slice
    # cannot satisfy it either.
    for _perm in (list(reversed(_fresh)), _fresh[15:] + _fresh[:15]):
        assert _latest_policy_stamp(_perm, _sb) == (_p, _n, _t), _perm[:1]
    # "LATEST" MEANS LATEST: with two stamped closes the NEWEST stamp is the
    # one returned, because `_pair_precheck` compares THIS dict against the
    # live arm's — hand it the stale one and a policy the arm has already
    # moved off is what gets parity-checked, which is the F1 handicap the
    # census exists to close. (mutation: `stamped[-1]` => this reddens)
    _moved = [_led(_sb, _sstamp, age=1),
              _led(_sb, dict(_sstamp, scan_order="ancient"), age=900)]
    assert _latest_policy_stamp(_moved, _sb)[0]["scan_order"] == "list", \
        _latest_policy_stamp(_moved, _sb)[0]
    # ...and the window still ROLLS: a stamp older than the newest `look`
    # closes does NOT count (the negative control — a reader that always finds
    # the stamp is as useless as one that never does).
    _old = [_led(_sb, None, age=1 + i) for i in range(30)] + \
           [_led(_sb, _sstamp, age=500)]
    assert _latest_policy_stamp(_old, _sb) == (None, 0, 30), \
        _latest_policy_stamp(_old, _sb)
    # an unreadable `close_ts` degrades to the NULLS-LAST bucket, never a
    # raise (parse_ts throws on junk; the census must survive one bad row)
    _junk = [{"bot": _sb, "close_ts": "not-a-date", "extra": {}},
             _led(_sb, _sstamp, age=5)]
    assert _latest_policy_stamp(_junk, _sb)[0] == _sstamp
    # NULLS **LAST**, mirroring the publisher: undated rows are UNORDERABLE,
    # never "newest". Sorted the other way a bot with `look` junk rows would
    # fill the whole window and hide a real stamped close behind rows that
    # merely have no date. (mutation: `ts is None` in _close_rank => reddens)
    _dateless = [{"bot": _sb, "close_ts": None, "extra": {}}
                 for _ in range(30)] + [_led(_sb, _sstamp, age=5)]
    assert _latest_policy_stamp(_dateless, _sb)[:2] == (_sstamp, 1), \
        _latest_policy_stamp(_dateless, _sb)[:2]
    # stamped but diverging on a NON-WAIVED field -> policy_mismatch NAMING
    # the field. [2026-08-26] This used `scan_order`, which georgia now
    # DECLARES waived — so the case moved to `stoploss` rather than being
    # deleted: the rung must still block on an undeclared divergence, and a
    # test that quietly stopped asserting that would be the waiver hiding the
    # mechanism instead of one field. The waiver's own cases (and the
    # narrowness control on avo/mum, which carry no waiver and must still
    # read policy_mismatch on scan_order) live in
    # tests/autonomy/test_judge_policy_waiver.py.
    _v = _pair_precheck("georgia", _psp,
                        [_led(_lb, _stamp),
                         _led(_sb, dict(_sstamp, scan_order="diversified",
                                        stoploss=-0.09))],
                        [_row(_lb), _row(_sb)], t0)
    assert _v["unjudgeable"]["reason"] == "policy_mismatch", _v
    assert "stoploss" in _v["unjudgeable"]["detail"], _v
    # ...and the DECLARED waiver clears the same rung on scan_order alone,
    # republishing the divergence rather than swallowing it (mutation: drop
    # the `st["policy_waived"]` attach, or waive without publishing => red)
    _v = _pair_precheck("georgia", _psp,
                        [_led(_lb, _stamp), _led(_sb, _sstamp)],
                        [_row(_lb), _row(_sb)], t0)
    assert _v["phase"] == "idle", _v
    assert _v["policy_waived"]["scan_order"]["live"] == "diversified", _v
    assert _v["policy_waived"]["scan_order"]["shadow"] == "list", _v
    # ...and a waiver NEVER covers darkness: the same pair with the waived
    # field absent from an arm's stamp is parity_unreadable, not waived
    # (mutation: waive without the readability check => this reddens)
    _v = _pair_precheck("georgia", _psp,
                        [_led(_lb, {k: v for k, v in _stamp.items()
                                    if k != "scan_order"}),
                         _led(_sb, _sstamp)],
                        [_row(_lb), _row(_sb)], t0)
    assert _v["unjudgeable"]["reason"] == "parity_unreadable", _v
    assert "scan_order" in _v["unjudgeable"]["detail"], _v
    # [2026-08-26] THE WAIVER'S MIRROR: a policy field NEITHER arm stamps
    # compares None to None and reads EQUAL, so the parity rung above cannot
    # see it. georgia's hourly entry throttle is exactly that — the shadow
    # throttles, the live host declares it does not, and no stamp carries it —
    # so it is DECLARED required and blocks, naming the field and the stamp
    # work. (mutation: drop the `missing` rung => this reddens)
    _nothrottle = {k: v for k, v in _stamp.items()
                   if k != "max_entries_per_hour"}
    _v = _pair_precheck("georgia", _psp,
                        [_led(_lb, _nothrottle),
                         _led(_sb, dict(_nothrottle, venue="lighter_shadow",
                                        scan_order="list"))],
                        [_row(_lb), _row(_sb)], t0)
    assert _v["unjudgeable"]["reason"] == "policy_unstamped", _v
    assert "max_entries_per_hour" in _v["unjudgeable"]["detail"], _v
    assert "policy_stamp" in _v["unjudgeable"]["wake_when"], _v
    # matched policy, capacity 5 vs 6 -> capacity_mismatch (the (ne) delta)
    _match = dict(_sstamp, scan_order="diversified")
    _v = _pair_precheck("georgia", _psp,
                        [_led(_lb, _stamp), _led(_sb, _match)],
                        [_row(_lb, 5), _row(_sb, 6)], t0)
    assert _v["unjudgeable"]["reason"] == "capacity_mismatch", _v
    # UNREADABLE capacity is parity_unreadable, NEVER assumed-equal —
    # darkness must not re-open the F1 handicap through the stage built to
    # close it (mutation: default the None to "equal" => this reddens)
    _v = _pair_precheck("georgia", _psp,
                        [_led(_lb, _stamp), _led(_sb, _match)],
                        [_row(_lb, 5), _row(_sb, None)], t0)
    assert _v["unjudgeable"]["reason"] == "parity_unreadable", _v
    # the negative control: everything matched -> IDLE, judgeable, no
    # candidate (a census that flags everything trains ignoring it)
    _v = _pair_precheck("georgia", _psp,
                        [_led(_lb, _stamp), _led(_sb, _match)],
                        [_row(_lb, 5), _row(_sb, 5)], t0)
    assert _v["phase"] == "idle", _v
    # restore the registry's word: WITHOUT the override georgia's pair
    # STANDS DOWN — the exact branch CI caught this selftest not knowing.
    if _geo_ov is None:
        os.environ.pop("GEORGIA_LIVE_RETIRED_OVERRIDE", None)
    else:
        os.environ["GEORGIA_LIVE_RETIRED_OVERRIDE"] = _geo_ov
    _v = _pair_precheck("georgia", _psp, [], [], t0)
    assert _v["phase"] == "stood_down", _v
    assert _v["stood_down"]["successor"] == "freqtrade-mum-lighter", _v
    # retired live arm -> stood_down with wake_when + successor
    _fsp = dict(_bus.JUDGED_PAIRS["farmer"])
    _v = _pair_precheck("farmer", _fsp, [], [], t0)
    assert _v["phase"] == "stood_down", _v
    assert "run" in _v["stood_down"]["wake_when"], _v
    # the pairs map reaches the SAVED payload with the farmer mirrored —
    # driven through the REAL run_once against a stubbed store (mutations:
    # drop the payload attach, or the farmer overwrite => this reddens)
    _saved = {}
    _sv = {k: getattr(store, k, None) for k in (
        "load_state_checked", "load_state", "save_state",
        "fetch_paper_trades", "fetch_bot_pnl", "save_history")}
    store.load_state_checked = lambda k: (True, {})
    store.load_state = lambda k: None
    store.save_state = lambda k, v: _saved.__setitem__(k, v) or True
    store.fetch_paper_trades = lambda limit=4000: []
    store.fetch_bot_pnl = lambda: []
    store.save_history = lambda k, v: True
    try:
        run_once()
    finally:
        for _k, _fn in _sv.items():
            if _fn is not None:
                setattr(store, _k, _fn)
    _pl = _saved.get(KEY) or {}
    assert set(_pl.get("pairs") or {}) == set(_bus.JUDGED_PAIRS), \
        sorted(_pl.get("pairs") or {})
    assert _pl["pairs"]["farmer"]["phase"] == _pl["phase"], _pl["pairs"]
    # ...and the farmer entry is the MACHINE'S state, not the census's
    # precheck view — the two agree while stood_down, so provenance is what
    # makes the overwrite testable (mutation: drop the overwrite => red)
    assert _pl["pairs"]["farmer"].get("src") == "machine", _pl["pairs"]
    for _pid, _pe in _pl["pairs"].items():
        assert _pe.get("phase") in _VOC, (_pid, _pe)

    # the farmer mirror derives holds from the machine's own payload
    _fe = _farmer_pair_entry({"phase": "running", "candidate": "x",
                              "last_eval": {"arm_skew": True}})
    assert _fe["hold"] == "arm_skew", _fe
    _fe = _farmer_pair_entry({"phase": "running", "candidate": "x",
                              "last_eval": {"why": "floors: shadow 3/30"}})
    assert _fe["hold"] == "floors", _fe

    print("experiment_judge selftest OK (promote, lucky-half reject, margin, "
          "floors, own-right, fade, proprioception early-fade, registry mapping, "
          "arm-skew receipt gate, per-half floors, relative+rolling fade, "
          "asserted-write guard; v2.0 census: vocab imported, dark/unstamped/"
          "mismatch/capacity/unreadable/idle/stood_down + farmer mirror)")


def _selftest_growth():
    """[2026-07-25] the growth-lever FASTER-bar promoter: promotes on receipt-
    proven shadow beating live (no both-halves), reasserts while healthy, releases
    on fade, and fail-CLOSES on arm-drift + missing receipts. Each assertion fails
    against a naive promoter (no receipt gate, no drift gate, or no fade)."""
    now = 1_000_000.0
    span = GROWTH_WINDOW_D * 86400

    def mk(bot, pnl, ts, receipt=False):
        r = {"bot": bot, "profit_ratio": pnl, "close_ts": iso(ts)}
        if receipt:
            r["extra"] = {"bars": {"explore_k": 2, "conviction_hi": 2.2}}
        return r

    rows = []
    for i in range(20):
        t = now - span + (i + 1) * span / 21.0
        rows.append(mk(SHADOW_BOT, 0.012, t, receipt=True))    # shadow +1.2%/trade
        rows.append(mk(LIVE_BOT, 0.002, t))                    # live   +0.2%/trade
    g, (kind, pay) = growth_promoter(rows, {}, now)
    assert kind == "promote" and g["promoted"], (kind, g)
    assert set(pay["levers"]) == set(GROWTH_LIVE), pay

    _, (k2, _) = growth_promoter(rows, {}, now, drift={"live": "aa", "shadow": "bb"})
    assert k2 == "eval", "arm-drift must fail CLOSED"

    # [2026-07-29] growth_reachable — REPORTS whether the floor can be met at
    # the arm's own close rate. Each assertion fails against a detector that
    # guesses instead of measuring, or that alarms on a dark feed.
    #  (a) UNKNOWN on no sample: a dark ledger must claim nothing.
    assert growth_reachable([], now)[0] is None
    assert growth_reachable([mk(SHADOW_BOT, 0.01, now - 3600)], now)[0] is None, \
        "n<2 is not a rate"
    #  (b) the LIVE 29-Jul shape: ~1.6 closes/day cannot fill 15 in 2.5d.
    slow = [mk(SHADOW_BOT, 0.01, now - i * 86400 / 1.6) for i in range(1, 23)]
    ok, det = growth_reachable(slow, now, window_d=2.5, min_closes=15,
                               lookback_d=14.0)
    assert ok is False, det
    assert det["projected"] < 15 and det["n_lookback"] >= 2, det
    #  (c) a fast arm clears the same floor — the detector tracks the RATE,
    #      it is not a constant dressed up as a measurement.
    fast = [mk(SHADOW_BOT, 0.01, now - i * 3600.0) for i in range(1, 200)]
    assert growth_reachable(fast, now, window_d=2.5, min_closes=15,
                            lookback_d=14.0)[0] is True
    #  (d) OPTIMISTIC by construction: unreceipted closes still count toward
    #      the projection, so `False` means definitely-not, never merely-maybe
    #      (the real floor gates on receipts too, and is therefore stricter).
    bare = [mk(SHADOW_BOT, 0.01, now - i * 3600.0) for i in range(1, 200)]
    assert all("extra" not in r for r in bare)
    assert growth_reachable(bare, now, window_d=2.5, min_closes=15,
                            lookback_d=14.0)[0] is True
    #  (e) the LIVE arm's closes must not inflate the SHADOW arm's rate
    assert growth_reachable([mk(LIVE_BOT, 0.01, now - i * 3600.0)
                             for i in range(1, 200)], now)[0] is None

    norcpt = []
    for i in range(20):
        t = now - span + (i + 1) * span / 21.0
        norcpt.append(mk(SHADOW_BOT, 0.012, t, receipt=False))
        norcpt.append(mk(LIVE_BOT, 0.002, t))
    _, (k3, _) = growth_promoter(norcpt, {}, now)
    assert k3 == "eval", "missing shadow receipt must NOT promote"

    pstate = {"promoted": True, "promoted_ts": now - 86400, "baseline_pct": 0.2}
    fade = [mk(LIVE_BOT, -0.01, now - 86400 + (i + 1) * 3600) for i in range(FADE_N + 2)]
    g4, (k4, _) = growth_promoter(fade, pstate, now)
    assert k4 == "release" and not g4["promoted"], k4

    ok = [mk(LIVE_BOT, 0.005, now - 86400 + (i + 1) * 3600) for i in range(FADE_N + 2)]
    g5, (k5, _) = growth_promoter(ok, pstate, now)
    assert k5 == "reassert" and g5["promoted"], k5

    # ---- growth_step: the run_once glue (2026-07-28 §3c) --------------------
    # Each case fails against naive glue: one that stamps promoted on a failed
    # write, asserts through a dark ledger, spams the phone every cycle, or
    # drops the promoter's verdict on the floor.
    def _ok_assert(levers, reason, evidence):
        return {"levers": {k: {"value": v} for k, v in levers.items()}}

    def _no_assert(levers, reason, evidence):
        return None

    pushes = []

    def _push(title, body, priority="default"):
        pushes.append(title)
        return True

    # (1) clear bar + write LANDS -> promoted state persists, one push
    g, last = growth_step({}, rows, True, now, assert_fn=_ok_assert, push=_push)
    assert g.get("promoted") and last["kind"] == "promote", (g, last)
    assert any("PROMOTED" in t for t in pushes), pushes
    # (2) clear bar + write FAILS -> the promotion did NOT happen: old
    #     (unpromoted) state kept, one failure push, sticky flag set
    pushes.clear()
    g, last = growth_step({}, rows, True, now, assert_fn=_no_assert, push=_push)
    assert not g.get("promoted") and last["kind"] == "promote-failed", (g, last)
    assert g.get("assert_fail_notified") and len(pushes) == 1, (g, pushes)
    g, last = growth_step(g, rows, True, now, assert_fn=_no_assert, push=_push)
    assert len(pushes) == 1, "one failure push per EPISODE, not per cycle"
    # (3) DARK LEDGER: nothing evaluated, nothing asserted — the standing
    #     promotion's lever expires to env within LEVER_TTL (fail-safe)
    calls = []
    g, last = growth_step(dict(pstate), None, False, now,
                          assert_fn=lambda *a: calls.append(a), push=_push)
    assert last["kind"] == "dark" and not calls, (last, calls)
    assert g.get("promoted"), "a blip must not RELEASE the promotion state"
    # (4) healthy promotion -> reassert lands, sticky flag clears
    g, last = growth_step(dict(pstate, assert_fail_notified=True), ok, True,
                          now, assert_fn=_ok_assert, push=_push,
                          prop_state={}, proposals=[])
    assert last["kind"] == "reassert" and g["assert_fail_notified"] is False, (g, last)
    # (4b) ORGAN RELEASE — proprioception HURTING on a growth lever releases
    #      the promotion early (the main pipeline's prop_fade, same evidence)
    _hurt = {"updated": iso(now), "ttl_sec": 3600,
             "verdicts": {"live.funding.explore_k":
                          {"verdict": "hurting", "bad": 3, "n": 4}}}
    g, last = growth_step(dict(pstate), ok, True, now, assert_fn=_ok_assert,
                          push=_push, prop_state=_hurt, proposals=[])
    assert last["kind"] == "release" and not g.get("promoted"), (g, last)
    # (4c) ORGAN RELEASE — a fresh restrict proposal (e.g. impl-shortfall
    #      sustained slip) releases too; an expand proposal NEVER does
    _prop = [{"lever": "live.funding.conviction_hi", "direction": "restrict",
              "set_by": "impl-shortfall", "reason": "sustained slip"}]
    g, last = growth_step(dict(pstate), ok, True, now, assert_fn=_ok_assert,
                          push=_push, prop_state={}, proposals=_prop)
    assert last["kind"] == "release" and not g.get("promoted"), (g, last)
    g, last = growth_step(dict(pstate), ok, True, now, assert_fn=_ok_assert,
                          push=_push, prop_state={},
                          proposals=[dict(_prop[0], direction="expand")])
    assert last["kind"] == "reassert", "an expand proposal must NEVER release"
    # (5) fade -> release verdict carried through, state cleared, one push
    pushes.clear()
    g, last = growth_step(dict(pstate), fade, True, now,
                          assert_fn=_ok_assert, push=_push)
    assert last["kind"] == "release" and not g.get("promoted"), (g, last)
    assert any("RELEASED" in t for t in pushes), pushes
    # (6) drift -> the promoter's fail-closed eval passes straight through
    g, last = growth_step({}, rows, True, now, drift={"live": "a", "shadow": "b"},
                          assert_fn=_no_assert, push=_push)
    assert last["kind"] == "eval" and not g.get("promoted"), (g, last)
    # (7) POST-RELEASE COOLDOWN: a fade release stamps cooldown_until, and a
    #     bar that still clears on the trailing window must NOT re-promote
    #     inside it (the hourly promote/release oscillation this kills).
    g7, (k7, _) = growth_promoter(fade, dict(pstate), now)
    assert k7 == "release" and _num(g7.get("cooldown_until")) > now, g7
    g, (k7b, p7b) = growth_promoter(rows, g7, now + 3600)
    assert k7b == "eval" and "cooldown" in str(p7b.get("why")), (k7b, p7b)
    _t2 = now + GROWTH_COOLDOWN_H * 3600 + 3600
    rows2 = []
    for i in range(20):
        t = _t2 - span + (i + 1) * span / 21.0
        rows2.append(mk(SHADOW_BOT, 0.012, t, receipt=True))
        rows2.append(mk(LIVE_BOT, 0.002, t))
    g, (k7c, _) = growth_promoter(rows2, g7, _t2)
    assert k7c == "promote", "past the cooldown the bar clears again"
    # organ release stamps the same cooldown
    g7d, _l7d = growth_step(dict(pstate), ok, True, now, assert_fn=_ok_assert,
                            push=_push, prop_state=_hurt, proposals=[])
    assert _num(g7d.get("cooldown_until")) > now, g7d
    # (8) PROMOTE BLOCKED by a standing organ verdict: the same HURTING that
    #     would release one cycle later refuses the promotion one earlier
    g, last = growth_step({}, rows, True, now, assert_fn=_ok_assert,
                          push=_push, prop_state=_hurt, proposals=[])
    assert last["kind"] == "eval" and "BLOCKED" in str(last.get("why")), last
    assert not g.get("promoted"), g
    # (9) [2026-07-29 AUDIT F1] PROMOTE HELD while the serial pipeline runs:
    #     a mid-candidate shadow arm makes the growth window a multi-variable
    #     confound (the D3 class), so the WRITE waits — no assert, no push,
    #     state unpromoted, verdict says HELD. Idle/absent phase promotes
    #     (case 1); an EXISTING promotion still reasserts through it (the
    #     hold is promote-only — release paths must never wait).
    calls9 = []
    g, last = growth_step({}, rows, True, now,
                          assert_fn=lambda *a: calls9.append(a) or
                          _ok_assert(*a), push=_push,
                          prop_state={}, proposals=[],
                          serial_phase="running")
    assert last["kind"] == "eval" and "HELD" in str(last.get("why")), last
    assert not g.get("promoted") and not calls9, (g, calls9)
    g, last = growth_step(dict(pstate), ok, True, now, assert_fn=_ok_assert,
                          push=_push, prop_state={}, proposals=[],
                          serial_phase="running")
    assert last["kind"] == "reassert", \
        "an existing promotion must keep reasserting through a serial run"
    # (10) [2026-07-29 AUDIT F4] PROMOTE BLOCKED by a fresh restrict organ
    #      PROPOSAL — the reassert path honored the channel, promote-time
    #      did not: a promotion could steer real money for one cycle before
    #      the very proposal that releases it. An expand proposal never blocks.
    g, last = growth_step({}, rows, True, now, assert_fn=_ok_assert,
                          push=_push, prop_state={}, proposals=_prop)
    assert last["kind"] == "eval" and "organ proposal" in str(last.get("why")), last
    assert not g.get("promoted"), g
    g, last = growth_step({}, rows, True, now, assert_fn=_ok_assert,
                          push=_push, prop_state={},
                          proposals=[dict(_prop[0], direction="expand")])
    assert last["kind"] == "promote", \
        "an expand proposal must never block a promotion"
    # ---- release-request channel (2026-07-29 audit R1) ----------------------
    # The tool queues; the judge consumes; the transition is single-sourced.
    _rst = {"phase": "running", "current": "cand-x",
            "done": ["old"], "done_at": {"old": now - 9e5},
            "started_ts": now - 3 * 86400,
            "verdicts": [{"name": "old", "verdict": "ABANDONED"}],
            "last_eval": {"promote": False, "why": "floors"},
            "growth": {"promoted": True}, "drift_notified": True}
    _rp = release_transition(_rst, "cand-x", "op reason", now)
    assert _rp["phase"] == "idle" and _rp["current"] is None, _rp
    assert _rp["done"] == ["old", "cand-x"] and _rp["done_at"]["cand-x"] == now
    assert _rp["cooldown_until"] == now + COOLDOWN_H * 3600
    assert _rp["verdicts"][-1]["verdict"] == "RELEASED-OPERATOR"
    assert _rp["growth"] == {"promoted": True} and _rp["drift_notified"] is True, \
        "a main-candidate release must not touch the growth record"
    for bad_st, bad_nm in ((dict(_rst, phase="idle"), "cand-x"),
                           (dict(_rst, phase="promoted"), "cand-x"),
                           (_rst, "other")):
        try:
            release_transition(bad_st, bad_nm, "r", now)
            raise AssertionError("must refuse")
        except ValueError:
            pass
    _fresh_req = {"updated": iso(now - 60), "ttl_sec": 7200, "name": "cand-x",
                  "why": "confounded window"}
    assert consume_release_request(_fresh_req, "running", "cand-x", now) == \
        ("release", None)
    v, d = consume_release_request(dict(_fresh_req, updated=iso(now - 9000)),
                                   "running", "cand-x", now)
    assert v == "stale", (v, d)
    v, _ = consume_release_request(dict(_fresh_req, ttl_sec=None),
                                   "running", "cand-x", now)
    assert v == "stale", "missing ttl must fail CLOSED"
    v, _ = consume_release_request({"name": "x", "why": "y"},
                                   "running", "x", now)
    assert v == "stale", "missing updated stamp must fail CLOSED"
    v, _ = consume_release_request(_fresh_req, "idle", None, now)
    assert v == "not-running", v
    v, _ = consume_release_request(_fresh_req, "running", "other", now)
    assert v == "mismatch", v
    for noop in (None, {}, {"consumed": True, "name": "cand-x",
                            "updated": iso(now), "ttl_sec": 7200},
                 {"updated": iso(now), "ttl_sec": 7200}):
        assert consume_release_request(noop, "running", "cand-x", now)[0] \
            == "none", noop
    print("experiment_judge _selftest_growth OK (+ release-request channel)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        _selftest_growth()
    else:
        sys.exit(store.organ_main('xp-judge', run_once))
