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

try:
    import fleet_proposals as fprop      # organ proposal channel (optional)
except Exception:  # noqa: BLE001
    fprop = None

KEY = "xp-judge"
TTL_SEC = int(os.environ.get("XPJ_TTL_SEC", "10800"))
LEVER_TTL = int(os.environ.get("XPJ_LEVER_TTL", "7800"))      # ~2h re-assert
SHADOW_BOT = os.environ.get("XPJ_SHADOW_BOT", "perps-funding-lighter-lshadow")
LIVE_BOT = os.environ.get("XPJ_LIVE_BOT", "perps-funding-lighter-lighter")
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

# One candidate at a time, in order.
CANDIDATES = [
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
              "xp.funding.min_vol": "live.funding.min_vol"}


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


def arm_trades(rows, bot, start_ts, end_ts=None, levers=None):
    """[(close_ts, pnl_pct)] for one arm inside the window, oldest first.

    levers=None keeps the historical behaviour (time-window attribution only) —
    correct for the LIVE control arm, which runs env defaults and whose rows
    predate the receipt. Pass levers to count ONLY closes the arm PROVED it ran
    them on (see ran_candidate).
    """
    out = []
    for r in rows or []:
        if str(r.get("bot")) != bot or r.get("profit_ratio") is None:
            continue
        if levers is not None and not ran_candidate(r, levers):
            continue
        try:
            ts = parse_ts(r.get("close_ts"))
        except Exception:
            continue
        if ts >= start_ts and (end_ts is None or ts < end_ts):
            out.append((ts, float(r["profit_ratio"])))
    out.sort()
    return out


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
    sh = arm_trades(rows, shadow_bot, start_ts, end_ts, levers=cand_levers)
    lv = arm_trades(rows, live_bot, start_ts, end_ts)
    v = {"promote": False, "n_shadow": len(sh), "n_live": len(lv),
         "shadow_mean_pct": _mean_pct(sh), "live_mean_pct": _mean_pct(lv)}
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
    half_sh_min = max(2, min_closes // 2)
    half_lv_min = max(3, live_min // 2)
    for a, b, label in (((start_ts, mid, "h1"), (mid, end_ts, "h2")) if both_halves else ()):
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
                     "live.funding.min_vol": (10000000.0, "up")}


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
        if lv and all(k in XP_TO_LIVE for k in lv):
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
    for _xk in XP_TO_LIVE:
        _bar = _xk.split(".")[-1]
        assert f'"{_bar}":' in _stamp_src, (
            f"apply_levers stamps no bars.{_bar} receipt — a {_bar} judge "
            f"candidate would accrue ZERO closes (ran_candidate fails closed)")
        assert f'"{_bar}":' in _es_bars_src, (
            f"entry_stamp carries no {_bar} — a mid-hold lever expiry would "
            f"rewrite the admission-time receipt (the (ed) rule)")

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
    assert names[:5] == ["slope-gate-off", "min-vol-1e5", "min-vol-2e6",
                         "tp-0.06", "enter-gate-0.105"], names
    # the rule itself, asserted independently of the literal above: every
    # static is ranked by the strength of its recorded prior, strongest first.
    _PRIOR_RANK = {"slope-gate-off": 0,    # venue-supported ((dp))
                   "min-vol-1e5": 1,       # calibrated own-tape replay, both
                                           # halves +ve — strongest DIRECT prior
                   "min-vol-2e6": 2,       # unrefuted friction-tier prior —
                                           # indirect ((ln) swap)
                   "tp-0.06": 3,           # MUTE — no both-halves-positive tp
                   "enter-gate-0.105": 4}  # tape prior AGAINST it
    _ranks = [_PRIOR_RANK[n] for n in names[:5]]
    assert _ranks == sorted(_ranks), \
        f"statics must run strongest-prior-first ((ju)'s rule): {names[:5]}"
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
    assert n2 == ["slope-gate-off", "min-vol-1e5", "min-vol-2e6", "tp-0.06",
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
    assert next_candidate(pool, [], None)["name"] == "slope-gate-off"
    assert next_candidate(pool, ["slope-gate-off"],
                          None)["name"] == "min-vol-1e5"
    assert next_candidate(pool, ["slope-gate-off", "min-vol-1e5"],
                          None)["name"] == "min-vol-2e6"
    assert next_candidate(pool, ["slope-gate-off", "min-vol-1e5",
                                 "min-vol-2e6"],
                          None)["name"] == "tp-0.06"
    assert next_candidate(pool, ["slope-gate-off", "min-vol-1e5",
                                 "min-vol-2e6", "tp-0.06"],
                          None)["name"] == "enter-gate-0.105"
    # the statics precede queue proposals by pool construction (statics first)
    assert next_candidate(pool, ["slope-gate-off", "min-vol-2e6",
                                 "min-vol-1e5", "tp-0.06",
                                 "enter-gate-0.105"],
                          None)["name"] == "xp-tp-0.05"
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

    print("experiment_judge selftest OK (promote, lucky-half reject, margin, "
          "floors, own-right, fade, proprioception early-fade, registry mapping, "
          "arm-skew receipt gate, per-half floors, relative+rolling fade, "
          "asserted-write guard)")


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
