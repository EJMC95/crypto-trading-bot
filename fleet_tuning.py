#!/usr/bin/env python3
"""fleet_tuning.py — the fleet's bounded GROWTH RAIL (shipped 2026-07-15).

WHY THIS EXISTS (user instruction, 15-Jul): "if the scanner just restricts
then we eventually will only stay still … the scanner needs to be able to
implement opening or altering a strategy or widening something too so growth
can happen fleet wide as I am not going to be able to make fixes and
implement suggestions every occasion in time."

Until now every autonomous actuator in the fleet was RESTRICT-only (vetoes,
clip scales, stake mults ≤ 1.0). Safe — but a fleet that can only say "no"
converges to standing still unless the operator hand-ships every widening.
This module is the sanctioned middle path: a WHITELISTED, HARD-BOUNDED,
TTL'd lever registry through which an authoring organ (the evidence board)
can WIDEN parameters autonomously — but only levers registered here, only
inside their bounds, only on lanes explicitly marked enactable (paper/
scanner lanes today), and only while the author keeps re-asserting the
evidence every cycle: levers EXPIRE back to defaults on their own, so
auto-revert is the resting state, not a feature to remember.

WHAT IT CAN NEVER DO
  - touch a lever that is not in the registry (unknown names are dropped);
  - exceed a lever's hard bounds (values are clamped, never trusted);
  - let the WRONG author touch real money: the `lighter-live` lane (added
    15-Jul by user mandate — live.clip_scale for the board, live.funding.*
    for the experiment judge's promotions, and nothing else) is bound per
    author in AUTHOR_LANES; write_levers() drops any lever outside the
    author's own lanes, anything whose lane isn't in ENACT_LANES, and any
    live.* lever from an unbound author. Go-live and the operator's hard
    caps (SafetyRails) stay operator-only.
  - outlive its TTL: if the author dies or stops re-asserting, every
    consumer is back on its own defaults within TTL_SEC.

CONTRACT (same fail-safe shape as fleet_bus):
  writer:  write_levers({name: {"value", "reason", "evidence"}})
           -> bot_state['fleet-tuning'] with updated+ttl_sec (+ history).
  reader:  get_lever(name, default) -> clamped fresh value, else default.
           No DB / stale / unknown / unparseable -> default. Backtests are
           inert (no DATABASE_URL -> load_state returns None -> defaults).

Adding a lever = one registry line here + one get_lever() call in the
consumer. Trading-book lanes (e.g. Ticket Taker bars) may be REGISTERED
later but stay proposal-only until a review adds their lane to
FLEET_TUNING_ENACT_LANES — the earn-your-wiring path the L2 light walked.
"""
import os
import time
from datetime import datetime, timezone

try:
    import bot_pnl_store as store
except Exception:                                    # pragma: no cover
    store = None

KEY = "fleet-tuning"
TTL_SEC = int(os.environ.get("FLEET_TUNING_TTL_SEC", "7200"))   # 2h re-assert
CACHE_SEC = 60.0

# Lanes the rail may ENACT autonomously. Everything else is proposal-only.
#   paper-scanner — detection/census organs (no trading surface at all)
#   lighter-scout — the scout's ADVISORY ticket emission (widens what gets
#                   GRADED by the brain; the taker's bars still gate fills)
#   lighter-taker — the $1k SHADOW book's bars; enactments on this lane are
#                   REPLAY-GATED by lighter_scout_tuner (both-halves on the
#                   recorded tape) before they are ever written here
#   lighter-live  — (15-Jul user mandate: "i want evidence and scanning for
#                   live bot changes also and for it to implement also")
#                   REAL-MONEY lane, deliberately one lever: a bounded
#                   multiplier on the operator's env clip size. It cannot
#                   raise total live exposure — SafetyRails' notional cap is
#                   operator-only, checked at order time, and divides the
#                   open-position budget by the scaled clip. Evidence bar in
#                   evidence_board.synthesize_live(); every change pushes
#                   URGENT to the phone. Remove the lane from this env to
#                   kill it. Go-live itself (keys, dry_run, caps) remains
#                   operator-only forever.
#   lighter-xp    — the Funding Farmer SHADOW twin's experiment arm (the
#                   judge's candidate parameters; zero real money)
#   event-sentinel — [2026-07-21 operator mandate: organs must be able to
#                   implement changes] the sentinel's OWN detection bars
#                   (evsent.min_sources / evsent.severity_bar): sensitivity
#                   of an ADVISORY news organ, zero trading surface — the
#                   same class as paper-scanner. Until today this lane was
#                   registered but unreachable: not enactable AND no author
#                   bound, so the levers could never move at all.
ENACT_LANES = {s.strip() for s in os.environ.get(
    "FLEET_TUNING_ENACT_LANES",
    "paper-scanner,lighter-scout,lighter-taker,lighter-live,lighter-xp,"
    "event-sentinel,lighter-books"
    ).split(",") if s.strip()}

# [2026-07-16 AUDIT FIX] author -> lanes each author may WRITE. "The judge is
# the ONLY writer of live.funding.*" was pure convention — any author could
# technically have written any enact-lane lever, so one bug in the board's or
# tuner's lever dict could move a real-money bar. Now enforced here, plus a
# name-prefix rule inside the live lane (the board owns live.clip_scale, the
# judge owns live.funding.*). An author absent from this map keeps the old
# behavior for NON-live lanes but can never write live.*.
AUTHOR_LANES = {
    # [2026-07-30] the board gains `lighter-books` — the six shadow books
    # that had no lever surface at all. It is the fleet's general-purpose
    # growth-rail author (bounded, TTL'd, auto-reverting) and these are
    # $1k shadow books, so the blast radius is bounded twice over. The
    # board still cannot write `live.funding.*` (that is the judge's, by
    # name-prefix below) and gains no new reach into real money.
    "evidence-board":   {"paper-scanner", "lighter-scout", "lighter-taker",
                         "lighter-live", "lighter-books"},
    "scout-tuner":      {"lighter-scout", "lighter-taker"},
    "experiment-judge": {"lighter-xp", "lighter-live"},
    # [2026-07-21] the sentinel tunes ONLY its own detection lane
    "event-sentinel":   {"event-sentinel"},
}
_LIVE_PREFIX_OWNERS = {"live.clip_scale": "evidence-board",
                       # [2026-08-16 (nj)] every per-book clip arm is the
                       # board's, same as the shared one it replaced. The
                       # judge's sole-writer claim on live.funding.* is
                       # untouched — a new live prefix that matched NOTHING
                       # here would be unwritable by anyone (the `return
                       # False` below), so this entry is what makes Avo's
                       # arm real rather than silently inert.
                       "live.avo.": "evidence-board",
                       # [2026-08-22 (tb)] 🔮 georgia's arm, for the same
                       # reason and found the same way: (sx) registered
                       # `live.georgia.clip_scale` in LEVERS and stopped there,
                       # so it was unwritable by ANY author until this line.
                       "live.georgia.": "evidence-board",
                       # [2026-08-25] 👩 mum's arm, registered WITH its lever
                       # in one commit — the (tb) lesson applied forward
                       # instead of re-learned.
                       "live.mum.": "evidence-board",
                       "live.funding.": "experiment-judge"}


def _author_may_write(name, lane, set_by):
    """Lane + live-prefix authorization for one lever write."""
    allowed = AUTHOR_LANES.get(set_by)
    if allowed is not None and lane not in allowed:
        return False
    if lane == "lighter-live":
        for prefix, owner in _LIVE_PREFIX_OWNERS.items():
            if name == prefix or name.startswith(prefix):
                return set_by == owner
        return False          # unknown live lever name: nobody writes it
    if allowed is None and name.startswith("live."):
        return False          # unbound authors never touch real money
    return True

# ---------------------------------------------------------------------------
# THE REGISTRY — every autonomously-tunable lever in the fleet, with hard
# bounds. A lever absent from this dict cannot be moved by any organ.
# ---------------------------------------------------------------------------
LEVERS = {
    # Event Sentinel 🗞️⚡ (event_sentinel.py): ADVISORY news-event organ —
    # nothing trades on it yet, so these levers tune detection sensitivity
    # only (how much corroboration activates an event / freezes a
    # prediction). Bounds keep it between "wire-service confirmation" and
    # "front-page only".
    "evsent.min_sources": {
        "kind": "int", "lo": 2, "hi": 5, "lane": "event-sentinel",
        "note": "distinct headlines to activate an event; default 2", "env_default": 2},
    "evsent.severity_bar": {
        "kind": "float", "lo": 0.30, "hi": 0.80, "lane": "event-sentinel",
        "note": "min severity to freeze a sector anticipation; default 0.45", "env_default": 0.45},
    # Gap Scout (scanner-cross-exchange-arb): paper-only census organ.
    "gapscout.prefilter_gap": {
        "kind": "float", "lo": 0.0010, "hi": 0.0030, "lane": "paper-scanner",
        "note": "stage-1 raw-gap bar for book-checking; default 0.0020", "env_default": 0.002},
    "gapscout.max_book_fetches": {
        "kind": "int", "lo": 10, "hi": 60, "lane": "paper-scanner",
        "note": "order books pulled per scan (2/pair); default 30", "env_default": 30},
    "gapscout.extra_exchanges": {
        "kind": "csv", "allowed": {"kucoin", "gateio", "mexc", "bitget", "htx"},
        "lane": "paper-scanner",
        "note": "second-tier venues hot-added to the census net"},
    # Lighter Scout 🛰️ — learning-throughput levers: they widen which
    # ADVISORY tickets get emitted (and therefore counterfactually graded by
    # the brain), not what trades. Widening = faster lens learning.
    "scout.ticket_top_n": {
        "kind": "int", "lo": 6, "hi": 15, "lane": "lighter-scout",
        "note": "tickets emitted per lens per scan; default 12 (was 6 until "
                "2026-07-30 — it was the supply cap on the fleet's only "
                "measured alpha)", "env_default": 12},
    "scout.brk_range_min": {
        "kind": "float", "lo": 0.80, "hi": 0.90, "lane": "lighter-scout",
        "note": "breakout lens: min range_pos to emit; default 0.90", "env_default": 0.9},
    "scout.dip_range_max": {
        "kind": "float", "lo": 0.10, "hi": 0.25, "lane": "lighter-scout",
        "note": "dip lens: max range_pos to emit; default 0.10", "env_default": 0.1},
    # [2026-07-21 IMB-20, review-sanctioned] divergence-ticket emission gap
    # (TRUE pp since the basis fix). The winner lens (only one positive at
    # every horizon, ehit4h Wilson lo 0.509) had no diet lever — the one
    # registry expand-asymmetry the audit flagged. Lower = more advisory
    # tickets; fills stay gated by the taker's bars.
    "scout.div_gap_pp": {
        "kind": "float", "lo": 20.0, "hi": 75.0, "lane": "lighter-scout",
        "note": "divergence-ticket emission gap (TRUE pp); env default 37.5", "env_default": 37.5},
    "scout.momo_chg_min": {
        "kind": "float", "lo": 2.0, "hi": 3.0, "lane": "lighter-scout",
        "note": "momentum lens: min day change %% to emit; default 3.0", "env_default": 3.0},
    # Ticket Taker 🎫 (SHADOW $1k book) — conviction bars + exit ladder.
    # Bounds = the 21-Jul agenda's own sweep grids. The tuner only writes
    # these after the change beats/matches baseline on BOTH halves of the
    # recorded tape (lighter_ticket_replay through the taker's real code).
    "taker.dip_range": {
        "kind": "float", "lo": 0.05, "hi": 0.15, "lane": "lighter-taker",
        "note": "dip conviction bar (range_pos <=); default 0.05", "env_default": 0.05},
    "taker.brk_range": {
        "kind": "float", "lo": 0.90, "hi": 0.95, "lane": "lighter-taker",
        "note": "breakout conviction bar (range_pos >=); default 0.95", "env_default": 0.95},
    "taker.momo_chg": {
        "kind": "float", "lo": 3.0, "hi": 6.0, "lane": "lighter-taker",
        "note": "momentum conviction bar (day %% >=); default 5.0", "env_default": 5.0},
    "taker.div_gap_pp": {
        # [2026-07-17] bounds /8 with the fleet-wide funding BASIS FIX: the
        # apr these pp are measured against was 8x TRUE. Same bar, true units.
        "kind": "float", "lo": 37.5, "hi": 87.5, "lane": "lighter-taker",
        "note": "divergence conviction bar (|gap| pp >=); default 62.5", "env_default": 62.5},
    "taker.tp": {
        "kind": "float", "lo": 0.03, "hi": 0.06, "lane": "lighter-taker",
        "note": "take-profit fraction; default 0.04", "env_default": 0.04},
    "taker.sl": {
        "kind": "float", "lo": -0.04, "hi": -0.02, "lane": "lighter-taker",
        "note": "stop-loss fraction; default -0.03", "env_default": -0.03},
    "taker.max_hold_h": {
        "kind": "float", "lo": 48.0, "hi": 72.0, "lane": "lighter-taker",
        "note": "max hold hours; default 48", "env_default": 48.0},
    # [2026-08-20 (sk)] THE RESTRICTIVE END OF EVERY BREAKOUTUP CAGE IS NOW
    # PINNED AT THE MODULE DEFAULT, because the actuator that moves these is
    # STRUCTURALLY BLIND to the lens they govern.
    #
    # MEASURED, on the live bus: `taker.brk_range` sat at **0.97** (cage hi =
    # tightest; default 0.95) and `taker.max_hold_h` at **24.0** (cage lo =
    # tightest; default 48) — BOTH `set_by: scout-tuner`, both from
    # `organ-proposal:event-sentinel`. And `lighter_ticket_replay.py:206` reads
    # `_up = False if lens == "breakout" else None`, so `bull_entry_ok` refuses
    # EVERY breakout entry and the tuner's replay contains ZERO breakoutup
    # trades. Its own published baseline agrees: breakout taken=0 closed=0.
    #
    # THE CONSEQUENCE IS ARITHMETIC, NOT STATISTICS. On a lens the gate cannot
    # fill, a candidate's replay delta is exactly $0.00 — so RESTRICT passes
    # `not_worse` for free (it fails only if `var < base - tol`), while EXPAND
    # needs `+MARGIN_HALF` on BOTH halves and can never clear $0.00, and the
    # starving-widen path needs `taken > 0` and logs "0 replay fills — no
    # evidence". **The cage on this book's only living lens could only ever get
    # smaller.** That is the one-way ratchet, in the actuator.
    #
    # WHAT THIS FIX CLAIMS, AND WHAT IT DOES NOT. `clamp()` is
    # `min(hi, max(lo, v))` and runs at READ as well as write, so pinning the
    # restrictive end at the default snaps both live levers back on the next
    # `get_lever` — no lever write, no deploy race. It is NOT a widening: the
    # values return to what the operator configured, and reach in the growth
    # direction is untouched (max_hold may still go to 72, brk_range down to
    # 0.90). It is also NOT sold as alpha — the 24h->48h restoration measures
    # +0.22pp to +0.57pp/trade on the book's own closes but LOSES to a
    # same-coin random-start placebo (P=0.45..0.88), i.e. most of it is
    # exposure rather than edge. **The claim is that an unevidenced
    # restriction is reversed**, and the burden for undoing a restriction a
    # blind gate imposed is not the burden for widening past a validated one.
    #
    # `taker.div_gap_pp` is DELIBERATELY LEFT at its levered 75.0 (default
    # 62.5). Its lens is divergence, which the replay CAN see (42 taken), so
    # the tuner had real evidence — and a 12-rung ladder through that replay
    # reads negative at every rung and monotonically LESS negative as the bar
    # tightens. Fixing the ratchet means fixing it where the gate is blind,
    # not everywhere a lever moved.
    #
    # THE DURABLE FIX IS UPSTREAM and is NOT in this change: teach
    # `lighter_ticket_replay` the taker's own breakoutup relabel so the gate
    # can SEE the lens before it is allowed to steer it. Until then, do NOT
    # add any breakoutup constant to `lighter_scout_tuner`'s PROPOSAL_TAKER /
    # TAKER_LADDERS / SWEEP_* — that hands more of this book to a blind
    # actuator. The two levers below are registered for CONSUMPTION only, and
    # their cages are one-sided at the default for exactly this reason.
    #
    # [2026-08-20 (sk)] THE BREAKOUT ARM'S TREND EXIT JOINS THE RAIL. Under
    # BULL_MODE `bull_exit()` routes breakout/breakoutup to a DIFFERENT exit
    # from every other lens — no TP cap, a wide hard stop, and a trailing
    # give-back off the peak — and both of its numbers were bare env literals
    # with no registry entry. So the growth rail could move the fixed
    # reversion bracket (`taker.tp`/`taker.sl`) that divergence uses and could
    # not touch the exit that actually binds the taker's best long lens:
    # `long-breakoutup_hold` n=27 +$23.77 (+1.412%/trade) against
    # `long-breakoutup_trail` n=18 -$9.59 (-1.722%). That is I18 — the binding
    # constraint must be a reachable lever — and until now it was not one.
    #
    # REGISTERING MOVES NOTHING (the `disloc.exit_bps` idiom): both defaults
    # are today's values and this ships INERT. It is reach, not a set value,
    # and the distinction matters here because the widening these knobs invite
    # was MEASURED AND WITHHELD the same day: on the trail, the harness's own
    # calibration drift (+0.508pp) exceeds the whole 6%->OFF effect (~0.10pp);
    # on the clock, leave-one-symbol-out takes the 48h->96h gain from +0.78pp
    # to +0.07pp without HYPE. What the rail gets is the ABILITY to walk them
    # through `lighter_scout_tuner`'s replay gate hourly, on evidence, instead
    # of a session hand-setting a number two measurements refused.
    #
    # SHADOW ONLY, structurally: `lighter_ticket_taker.apply_tuning` returns
    # an empty dict when TT_VENUE == lighter_live, and the live arm is
    # divergence-SHORT only (`LIVE_SIDES`), so the breakout branch of
    # `bull_exit` is unreachable on real money twice over.
    "taker.brk_trail": {
        # Cage `hi` stops at 0.15 because the sweep measured the rule
        # SATURATING there — 15%, 20% and trail-OFF are the same book, so a
        # cage past 0.15 is reach into a region where the lever does nothing.
        # `lo` 0.04 keeps a tightening notch available if the trend arm ever
        # measures better banking earlier.
        "kind": "float", "lo": 0.06, "hi": 0.15, "lane": "lighter-taker",
        "note": ("breakout TREND exit: give-back off the peak before banking; "
                 "env default 0.06 (TT_BRK_TRAIL)"),
        "env_default": 0.06, "step": 0.01},
    "taker.brk_sl": {
        # Signed like `taker.sl`, so `lo` is the WIDER stop. -0.12 is the
        # widest the arm's own rationale supports ("entries draw -3.4% before
        # running"); -0.05 is a notch tighter than shipped and still wider
        # than the reversion bracket's -0.03, which the breakout pop churns.
        "kind": "float", "lo": -0.12, "hi": -0.07, "lane": "lighter-taker",
        "note": ("breakout TREND exit: wide hard stop; env default -0.07 "
                 "(TT_BRK_SL)"),
        "env_default": -0.07, "step": -0.01},
    # [2026-07-21] post-stop re-entry cooldown (TT_SL_COOLDOWN_H, default
    # 2.0h — the same-day churn fix: NBIS -$5.37/8, BOT -$4.60/3, every
    # same-minute re-entry a loser). Registered so the proposal channel and
    # the tuner can move it within bounds. Replay ladders are window-
    # sensitive: the 16→21-Jul tape scored 2-8h clearly positive (full
    # -0.47 -> +5.97) while the next morning's 120h window scored 2-4h
    # marked-NEUTRAL (the churn episodes aged out) — a widening proposal
    # must clear the improve bar on the tape of ITS day. 0 = off.
    "taker.sl_cooldown_h": {
        "kind": "float", "lo": 0.0, "hi": 24.0, "lane": "lighter-taker",
        "note": "hours a symbol stays entry-blocked after its own sl close; "
                "default 2.0, 0 = off", "env_default": 2.0},
    # LIVE lane 💰 — a multiplier on the env clip, ONE ARM PER REAL-MONEY BOOK.
    # SafetyRails' notional cap stays senior at order time: these reshape
    # clips, they can never raise total live exposure.
    # [2026-08-16 (nj)] `live.clip_scale` was a SINGLE dial across every live
    # book, which stopped being right the day 🙏 Avo took the live slot
    # (13-Aug (ma)): one number sized a directional funding book and a
    # swing-dip long book at once, so a Farmer drawdown shrank Avo's clips
    # and an Avo drawdown moved nothing. Each row now carries its own arm
    # (evidence_board.LIVE_CLIP_LEVERS). `live.clip_scale` KEEPS ITS NAME and
    # its meaning — the 💸 Farmer's clip — because renaming a lever its
    # real-money consumer is reading today opens a protection gap for one
    # deploy, and that gap is the whole risk of this change.
    "live.clip_scale": {
        "kind": "float", "lo": 0.5, "hi": 1.5, "lane": "lighter-live",
        "note": "💸 Farmer live clip multiplier; 1.0 = the operator's env sizing",
        "env_default": 1.0},
    # 🙏 Avo Maria's own arm. Cage `hi` is 1.0, not 1.5, because its consumer
    # is RESTRICT-ONLY by construction — lighter_avo_live_bot.py clamps the
    # lever to min(1.0, ...) so its gross can never exceed equity (clip =
    # equity/max_open x this x stake_mult, all three reduce-only). A cage
    # above 1.0 would register authority the consumer silently discards,
    # which is the registered-but-inert failure this registry exists to stop.
    "live.avo.clip_scale": {
        "kind": "float", "lo": 0.5, "hi": 1.0, "lane": "lighter-live",
        "note": "🙏 Avo live clip multiplier, restrict-only; 1.0 = equity/slots",
        "env_default": 1.0},
    # [2026-08-22 (sx)] 🔮 georgia's own arm, registered AHEAD of her live row.
    # Same shape and same cage as Avo's for the same reason: the consumer is
    # the SAME code (`lighter_avo_live_bot._clip_scale_now`, now a variant
    # host) and clamps to min(1.0, ...), so a cage above 1.0 would register
    # authority the consumer silently discards.
    #
    # Registered before she is funded ON PURPOSE: `fleet_tuning.get_lever`
    # returns the env default for an UNREGISTERED name, so a live book whose
    # arm does not exist has a dial nothing can turn — the reverse of the
    # registered-but-inert failure and just as silent. This costs nothing
    # while she is unfunded (nothing writes it) and means the protection is
    # already there on the first real order.
    "live.georgia.clip_scale": {
        "kind": "float", "lo": 0.5, "hi": 1.0, "lane": "lighter-live",
        "note": "🔮 georgia live clip multiplier, restrict-only; 1.0 = equity/slots",
        "env_default": 1.0},
    # [2026-08-25] 👩 mum's own arm, registered AHEAD of her live row — the
    # same pre-registration georgia's got at (sx), for the same reason: an
    # unregistered name silently returns the env default, so a live book
    # whose arm does not exist has a dial nothing can turn. Same cage as her
    # siblings' because the consumer is the SAME restrict-only code
    # (`lighter_avo_live_bot._clip_scale_now`, min(1.0, ...)). Its prefix is
    # in `_LIVE_PREFIX_OWNERS` in the SAME commit — (tb) measured that
    # registering the lever and stopping there leaves it unwritable by any
    # author, the registered-but-inert failure with extra steps.
    "live.mum.clip_scale": {
        "kind": "float", "lo": 0.5, "hi": 1.0, "lane": "lighter-live",
        "note": "👩 mum live clip multiplier, restrict-only; 1.0 = equity/slots",
        "env_default": 1.0},
    # Funding Farmer EXPERIMENT arm 🧪 (the -lshadow twin ONLY — zero real
    # money). The experiment judge runs ONE candidate at a time here; while
    # a candidate runs, the twin is an experiment arm, not a control arm.
    "xp.funding.enter_apr": {
        # [2026-07-17] bounds /8 with the BASIS FIX — TRUE apr now.
        # [2026-07-30 A1 — operator sign-off "widen"] hi 0.075 -> 0.12: the
        # venue's modal funding (10.5% TRUE, 42.6% of observations) sat
        # OUTSIDE the old ceiling, so an "enter only above modal" candidate
        # was structurally unaskable. The widening moves no money by itself
        # — any value inside still needs the judge's full paired bar, and
        # THIS twin is where the experiment runs first.
        "kind": "float", "lo": 0.03125, "hi": 0.12, "lane": "lighter-xp",
        "note": "shadow twin's funding entry gate (TRUE apr); env default 0.05", "env_default": 0.05},
    "xp.funding.take_profit": {
        "kind": "float", "lo": 0.03, "hi": 0.08, "lane": "lighter-xp",
        "note": "shadow twin's TP; env default 0.04", "env_default": 0.04},
    "xp.funding.max_hold_h": {
        "kind": "float", "lo": 24.0, "hi": 96.0, "lane": "lighter-xp",
        "note": "shadow twin's max hold; env default 72", "env_default": 72.0},
    # …and their PROMOTED-to-live counterparts. Written by exactly ONE
    # author — the experiment judge — and only after the paired promotion
    # bar (>=7d, >=30 shadow closes, beats live per-trade on the window AND
    # both halves by the margin). TTL'd: promotion fades back to env
    # defaults when the judge stops re-asserting it.
    "live.funding.enter_apr": {
        # [2026-07-17] bounds /8 with the BASIS FIX — TRUE apr now. 💰
        # [2026-07-30 A1 — operator sign-off "widen"] hi 0.075 -> 0.12,
        # identical to the xp twin above (the twin runs the experiment; the
        # judge remains the ONLY writer here, and its paired promotion bar
        # is unchanged — the cage widened, the gatekeeper did not).
        "kind": "float", "lo": 0.03125, "hi": 0.12, "lane": "lighter-live",
        "note": "PROMOTED funding entry gate (TRUE apr); env default 0.05", "env_default": 0.05},
    "live.funding.take_profit": {
        "kind": "float", "lo": 0.03, "hi": 0.08, "lane": "lighter-live",
        "note": "PROMOTED TP; env default 0.04", "env_default": 0.04},
    "live.funding.max_hold_h": {
        "kind": "float", "lo": 24.0, "hi": 96.0, "lane": "lighter-live",
        "note": "PROMOTED max hold; env default 72", "env_default": 72.0},
    # [2026-07-24/25] Farmer GROWTH levers (Lever 1 explore, Lever 2 conviction),
    # promotable to real money by the experiment judge on the operator-chosen
    # FASTER bar (~2-3d, net-positive + beats-live, tight fade-revert). explore_k
    # reserves scan slots for coverage-sampled coins; conviction_hi is the numeric
    # up-size cap (>1.0 => scaled sizing, floor 1.0) — ALWAYS bounded by the
    # SafetyRails notional cap at order time, so it reshapes clips, never raises
    # the ceiling. Same single-author rule: the judge alone writes live.funding.*.
    "xp.funding.explore_k": {
        "kind": "int", "lo": 0, "hi": 3, "lane": "lighter-xp",
        "note": "shadow twin's explore slots; env default 0", "env_default": 0},
    "xp.funding.conviction_hi": {
        "kind": "float", "lo": 1.0, "hi": 2.2, "lane": "lighter-xp",
        "note": "shadow twin's conviction up-cap; 1.0 = off", "env_default": 2.2},
    "live.funding.explore_k": {
        "kind": "int", "lo": 0, "hi": 3, "lane": "lighter-live",
        "note": "PROMOTED explore slots; env default 0", "env_default": 0},
    "live.funding.conviction_hi": {
        "kind": "float", "lo": 1.0, "hi": 2.2, "lane": "lighter-live",
        "note": "PROMOTED conviction up-cap; 1.0 = off, env default off", "env_default": 2.2},
    # [2026-07-28 D7] Farmer slope gate as a JUDGE-reachable lever (0 = off,
    # 1 = on; env default FUNDING_SLOPE_GATE=on). The (dp) Lighter backtest
    # refuted the gate on this venue (live gate 0.05: durable-history -$14.90
    # vs gate-off +$34.07 @5bps — the gate is HL-validated, Lighter-negative),
    # so gate-OFF is the natural next shadow candidate after tp-0.06. Doctrine
    # path, not an env flip: the judge runs it on the paired bar and alone
    # writes the live twin.
    "xp.funding.slope_gate": {
        "kind": "int", "lo": 0, "hi": 1, "lane": "lighter-xp",
        "note": "shadow twin's funding slope gate; 0 = off, env default on", "env_default": 1},
    "live.funding.slope_gate": {
        "kind": "int", "lo": 0, "hi": 1, "lane": "lighter-live",
        "note": "PROMOTED slope gate; 0 = off, env default on", "env_default": 1},
    # [2026-07-30 LIQUIDITY FLOOR as a lever] The Farmer's $10M floor
    # EXCLUDES 5 of the venue's 8 most extreme funding books, including the
    # two most extreme (measured: H100 -99.0% APR at $0.14M, XLM -89.4% at
    # $0.26M, SKR -78.8% at $0.25M, XPD +47.3% at $0.11M, TRUMP -41.2% at
    # $0.22M). Its own sibling, the carry book, runs a $2M floor and is the
    # fleet's biggest earner. The floor is a CRUDE PROXY for the thing the
    # scan already measures directly (SCAN_MAX_SLIP_BPS on the real clip),
    # so lowering it is not "less risk control", it is deferring to the
    # better instrument. Doctrine path: the shadow twin explores, the judge
    # alone promotes. Env defaults untouched by this registration.
    "xp.funding.min_vol": {
        "kind": "float", "lo": 1e5, "hi": 20e6, "lane": "lighter-xp",
        "note": "shadow twin's 24h $ turnover floor; env default 10e6. "
                "[5-Aug (ka)] lo 2e6->1e5 OPERATOR-SIGNED ('if it produces "
                "better numbers then proceed') on the thin-tier replay: the "
                "[0.1M,2M) band ALONE, at its tier-median 5.12bps/fill, "
                "shipped gate 0.05, reads +$14.83/30d, both halves positive, "
                "+$7.20 at p90 14.77 (STUDY_THIN_TIER_MIN_VOL_2026-08-05)",
        "env_default": 10000000.0},
    # [2026-08-15 (na)] THE FARMER'S EXIT KNOBS BECOME LEVERS. The 15-Aug
    # audit measured (adversarially verified from the live ledger) that
    # EXIT_APR and HARD_STOP decide ~100% of the LIVE row's gross loss
    # (48.9% / 51.1% of $7.83) while being the only bars outside the growth
    # rail — I18's unreachable-binding-constraint, on real money. Registered
    # as the min_vol-precedent PAIR: the judge explores on the shadow twin
    # (xp), promotes through the paired bar (live; judge sole writer,
    # fade-watch unchanged). Cages bracket the E2 study's pre-registered
    # grid (exit_apr 0.5x-2x default; hard_stop 5%-15%); consumers price
    # them at ENTRY (pos_exit_bars), so mid-hold flap is structurally closed.
    "xp.funding.exit_apr": {
        "kind": "float", "lo": 0.009375, "hi": 0.0375, "lane": "lighter-xp",
        "note": "shadow twin's decay-exit TRUE-apr floor; env default "
                "0.01875 — a rate cooling below this books 'decay'",
        "env_default": 0.01875},
    "live.funding.exit_apr": {
        "kind": "float", "lo": 0.009375, "hi": 0.0375, "lane": "lighter-live",
        "note": "PROMOTED decay-exit floor; env default 0.01875; judge sole "
                "writer via the paired bar",
        "env_default": 0.01875},
    "xp.funding.hard_stop": {
        "kind": "float", "lo": 0.05, "hi": 0.15, "lane": "lighter-xp",
        "note": "shadow twin's adverse-move hard stop; env default 0.10 "
                "(HL-fitted 17-Jul; never measured on this book's own cell "
                "— the E2 study's whole point)",
        "env_default": 0.10},
    "live.funding.hard_stop": {
        "kind": "float", "lo": 0.05, "hi": 0.15, "lane": "lighter-live",
        "note": "PROMOTED hard stop; env default 0.10; judge sole writer "
                "via the paired bar",
        "env_default": 0.10},
    "live.funding.min_vol": {
        "kind": "float", "lo": 1e5, "hi": 20e6, "lane": "lighter-live",
        "note": "PROMOTED turnover floor; env default 10e6. [5-Aug (ka)] lo "
                "2e6->1e5 with the xp twin, same signature — the judge's "
                "both-cage clamp invariant makes an xp-only floor "
                "unexercisable (a static must clamp clean in BOTH cages), "
                "and the real-money gate was never this cage: it is the "
                "paired bar (judge sole writer) + fade-watch, unchanged",
        "env_default": 10000000.0},
    # ---------------------------------------------------------------------
    # [2026-07-30 THE SHADOW BOOKS GET LEVERS — operator: "every bot needs
    # every tool at its disposal and every bot needs the ability to grow"]
    #
    # Until now SIX books had ZERO registered levers: the Yield Harvester,
    # Counterweight, Snap Back, Index Rider, Tide Rider and the Perp Sniper.
    # The growth rail could not move a single knob on any of them — including
    # `carry.enter_apr`, which is the best-performing gate in the fleet
    # (+$56.20 on n=80, t=2.42, both halves positive). "The ability to grow"
    # is not a metaphor here; it is registry membership, and they had none.
    #
    # All six are $1,000 SHADOW books — zero real money — so this lane is
    # bounded by construction as well as by these `lo`/`hi` pairs. Kill
    # switch: drop `lighter-books` from FLEET_TUNING_ENACT_LANES and every
    # consumer below reverts to its operator env default on the next read.
    "carry.enter_apr": {
        # env default 1.60 = 20% TRUE apr = the top ~14% of the venue's
        # funding distribution (measured over all 202 books).
        # [2026-08-15 (mv)] `lo` 0.80 -> 1.60 — the cage may no longer WIDEN
        # this gate, only tighten it, for two measured reasons the 30-Jul
        # "test BOTH directions" rationale predates:
        #   I19: 3-Aug measured 20%->10% TRUE as loss-making (a 29bps RT needs
        #   the rate to hold 254 of a 336h max hold to break even at 10%) and
        #   REFUSED it — yet the board's STARVED ladder walked this lever to
        #   0.80 = exactly that refused value, and the book consumed it
        #   (caps.enter_apr=0.1 on the live row, 15-Aug audit, adversarially
        #   verified). A cage that admits a measured-refused value makes the
        #   refusal decorative.
        #   I20: below 1.60 this gate invades 🧮 Hull's PUBLISHED zero-rival
        #   band [7.82%, 20%) x [$2M,$10M) — the tiling declared at Hull's
        #   birth. A widening here is a silent second entrant, not growth.
        # The read-side clamp retires the open 0.80 lever without a bus write.
        # A future widening BELOW 20% is a replay-gated measurement first
        # (I19), then a deliberate two-sided cage change citing it.
        "kind": "float", "lo": 1.60, "hi": 3.20, "lane": "lighter-books",
        "note": "Yield Harvester funding entry gate; env default 1.60 (=20% TRUE); tighten-only since (mv)", "env_default": 1.6, "step": -0.2},
    "carry.max_positions": {
        # measured AT 7 open of 8 — the fleet's biggest earner is one slot
        # from full and cannot take the eighth-best carry it has graded.
        "kind": "int", "lo": 6, "hi": 20, "lane": "lighter-books",
        "note": "Yield Harvester concurrent carries; env default 12", "env_default": 12, "step": 2},
    # [2026-08-03 (iv)] THE FLEET-WIDE BUDGETS — the ceiling every book competes
    # for, and the last bounds in fleet_risk.py that were not env-backed. The
    # rail could widen a book's universe, its cap and its gates but not the
    # budget those books share, so growth anywhere pushed harder against a
    # ceiling no author could move.
    #
    # ONE-SIDED BY CONSTRUCTION: `lo` == the operator's current value, so the
    # rail may only WIDEN and can never tighten the fleet's risk budget below
    # what a human set. That asymmetry is deliberate — a growth rail that can
    # restrict the whole fleet's admission is a different and much more
    # dangerous object than one that can only loosen it.
    #
    # INERT ON SHIP (defaults == today's 20/12). This is Step 1 only: it makes
    # the ceiling reachable. Step 2 is admission by EDGE with a displacement
    # policy — on 30-Jul ⚖️ Counterweight (t=0.65) held budget that 🌾 carry
    # (t=2.60) competed for, because `fleet_bus` refuses the NEXT long rather
    # than the WORST one — and that needs replay evidence before it governs
    # anything, because it changes which trades six books take.
    # LANE `fleet-risk` IS DELIBERATELY *NOT* IN `ENACT_LANES`. Registering
    # these makes them machine-readable, drift-checked and settable by the
    # OPERATOR without a deploy — which is the whole of Step 1. It does NOT
    # hand an automated author the fleet-wide risk budget, and that restraint
    # is the point: this veto reaches the strategies, the family books AND the
    # Ticket Taker, so a lane that could widen it is a different and much
    # larger object than one that widens a single shadow book's universe.
    # Turning it on is one entry in `FLEET_TUNING_ENACT_LANES` plus an
    # `AUTHOR_LANES` binding — an explicit operator act, exactly like go-live.
    "risk.long_budget": {
        "kind": "int", "lo": 20, "hi": 40, "lane": "fleet-risk",
        "note": "fleet-wide concurrent LONG budget; env default 20",
        "env_default": 20, "step": 2},
    "risk.short_budget": {
        "kind": "int", "lo": 12, "hi": 24, "lane": "fleet-risk",
        "note": "fleet-wide concurrent SHORT budget; env default 12",
        "env_default": 12, "step": 2},
    "carry.min_vol": {
        # [2026-08-03] THE GATE THAT WAS ACTUALLY BINDING. `enter_apr` and
        # `max_positions` were both registered and both had room — the book
        # sat at 6 of 12 slots and went 98.9h without an OPEN, because only
        # **14 of 203** books clear its $2M turnover floor (median book:
        # $0.043M). Its own hot list read CXMT -692.9% at $0.155M and H100
        # +209.4% at $0.128M, 13-16x below the floor, while KAITO missed by
        # $2,000. Registering the two knobs with slack and leaving the binding
        # one a bare literal is how a book looks tunable and cannot move.
        #
        # `hi` is today's value so the rail can only LOOSEN toward the tape,
        # never tighten past the operator's setting (the `disloc.exit_bps`
        # idiom). `lo` = $1M doubles the eligible set (14 -> 26) and holds the
        # $300 clip at <=0.03% of daily turnover; it stops there because
        # per-book slippage here is unmeasured and the real-money funding
        # floors bottom at $2M. Step walks DOWN a notch at a time
        # (2.0 -> 1.75 -> 1.5 -> 1.25 -> 1.0), each one replay-gated.
        # [2026-08-18 (pr)] env default 2e6 -> 1e6 (the cage's own designed
        # `lo`): measured over 9,996 snapshots / 34.9d, the cell's occupancy
        # at $2M is 5.73%/3 coins vs 13.42%/6 coins at $1M — the 3-Aug "zero
        # unlock" census above was point-in-time and is corrected in place in
        # the bot. The default now sits AT `lo`, so the cage is one-sided the
        # OTHER way: the rail can only TIGHTEN back toward the operator's old
        # floor. Loosening below $1M stays blocked on the unmeasured-slippage
        # reason above.
        "kind": "float", "lo": 1e6, "hi": 2e6, "lane": "lighter-books",
        "note": "Yield Harvester 24h $ turnover floor; env default 1e6 since (pr)",
        "env_default": 1000000.0, "step": -250000.0},
    "carry.payback_max_h": {
        # [2026-08-20 (sk)] THE OTHER HALF OF THE LIQUIDITY GATE, and the only
        # one that can OPEN this book. `carry.min_vol`'s cage is one-sided in
        # the TIGHTEN direction (default sits at `lo`), so after (pr) the rail
        # had no lever anywhere that could widen 🌾 carry's intake — the fleet's
        # best-evidenced book, sitting at 0 of 12 slots with `eligible: 0` of
        # 228 scanned. That is I18 in its purest form: every reachable motion
        # restricted a book whose problem was that it could not find a trade.
        #
        # WHAT IT GATES. A coin below the turnover floor is admitted only if
        # the LIVE book can fill this book's clip and the funding repays the
        # MEASURED round trip within this many hours (`depth_admits`). It is a
        # bound on a payback horizon, not on volume, so it is denominated in
        # the same units as the decision — unlike turnover, which measured
        # 2026-08-20 as close to orthogonal to fill cost at an $80 clip.
        #
        # CAGE. `lo` 6h is roughly the fastest payback the venue has ever
        # offered (UNITREE at 1162% APR repays 34.8bps in 2.6h, so even `lo`
        # admits the extremes); `hi` 168h is a QUARTER of the 336h max hold —
        # deliberately far short of it, because a carry that needs most of its
        # maximum life just to break even has no margin for the rate decaying,
        # which is the thing carries actually do. Step walks UP a notch at a
        # time, each one replay-gated like every other lever on this lane.
        "kind": "float", "lo": 6.0, "hi": 168.0, "lane": "lighter-books",
        "note": ("Yield Harvester max payback horizon (h) for a sub-floor "
                 "coin admitted on MEASURED book depth; env default 48"),
        "env_default": 48.0, "step": 12.0},
    "fundspread.k": {
        # measured AT its cap: 10 open = exactly K=5 x 2 legs.
        # [2026-08-04] default 8 -> 5: the (fz) widening reverted per its own
        # pre-registered criterion (t=-0.44 and falling; see the bot's K note).
        # K=5 is the validated plateau centre; the cage is unchanged so the
        # board can still WIDEN a book that is measured in profit MTM ((hs)).
        "kind": "int", "lo": 3, "hi": 12, "lane": "lighter-books",
        "note": "Counterweight legs per side; env default 5", "env_default": 5, "step": 1},
    # -----------------------------------------------------------------------
    # [2026-08-05] 🎸 Barnesy (band-barnes-lshadow) — the funding super-book.
    # Registered AT BIRTH so the growth surface exists (I18: the binding
    # constraint must be a reachable lever), and BIRTH-FROZEN at the consumer:
    # `lighter_band_barnes_bot.apply_tuning` refuses the rail outright until
    # BARNES_FREEZE_UNTIL (default 2026-09-04, 30 days from first publish),
    # because a book whose bars move accrues zero gradeable closes ((hm)).
    # Reach without rule-drift: on day 31 the rail needs no deploy.
    #
    # CAGES ARE ONE-SIDED ON PURPOSE, each default pinned at `lo`:
    #   * enter_apr may only walk UP (more selective, the tail-seeking
    #     direction) — walking DOWN toward 10% TRUE is the direction (it)
    #     measured loss-making on the parent (29bps round trip needs 254h of
    #     a 336h max hold to break even at 10%) and must not be reachable.
    #   * max_positions / k may only WIDEN, and only after the board's
    #     (hs)-fixed capacity author sees MTM profit — K=5 is the validated
    #     Counterweight plateau centre, so 5 is the floor, not the middle.
    "barnes.enter_apr": {
        "kind": "float", "lo": 0.20, "hi": 0.40, "lane": "lighter-books",
        "note": ("Barnesy harvest entry bar, TRUE apr fraction (both harvest "
                 "sleeves); env default 0.20 = the 21-Jul gate-sweep winner. "
                 "One-sided: may only tighten upward — 10-20% TRUE is "
                 "measured loss-making ((it))"),
        "env_default": 0.20, "step": 0.04},
    "barnes.max_positions": {
        "kind": "int", "lo": 4, "hi": 8, "lane": "lighter-books",
        "note": ("Barnesy per-harvest-sleeve concurrent positions (carry AND "
                 "extreme each); env default 4. One-sided: capacity widens "
                 "only on MTM evidence ((hs))"),
        "env_default": 4, "step": 1},
    "barnes.k": {
        "kind": "int", "lo": 5, "hi": 8, "lane": "lighter-books",
        "note": ("Barnesy xsect legs per side; env default 5 = Counterweight's "
                 "VALIDATED plateau centre (the un-backtested K=8 is the "
                 "cautionary tale, not the target)"),
        "env_default": 5, "step": 1},
    # [2026-08-06 (kl)] I18 — THE GATES THAT ACTUALLY BIND THIS BOOK. Barnesy
    # had three registered levers and every one of them is tighten-only or
    # inert on a starved sleeve, while the four gates its OWN census names as
    # binding were bare literals: no lever, no cage, no reader, invisible to
    # the rail. That is the `carry.MIN_DAY_VOLUME` shape I18 was written for —
    # "a book whose only tunable knobs are the ones with room LOOKS tunable
    # and cannot move". Measured the day these were registered: 218 scanned,
    # cold 201, thin 15, waiting 2, ELIGIBLE 0, and the carry sleeve's nearest
    # candidate ETA moved AWAY over an hour (3.42h -> 4.45h) as thin books
    # dipped below the apr gate and had their persistence clocks deleted.
    # REACH, NOT PAYOFF, and said plainly: every default is UNCHANGED, so
    # registering these moves nothing today — exactly as (it) recorded when
    # walking `carry.min_vol` to its floor unlocked zero books.
    "barnes.persist_h": {
        "kind": "float", "lo": 3.0, "hi": 12.0, "lane": "lighter-books",
        "note": ("Barnesy hours a book must hold |TRUE apr| >= enter_apr "
                 "before entry; env default 6.0 = both parents' bar. The "
                 "MEASURED binding gate: thin books dip and the clock is "
                 "deleted, so candidates never mature. Two-sided, but "
                 "loosening is an I19 widening and owes expectancy first"),
        "env_default": 6.0, "step": -0.5},
    "barnes.carry_min_vol": {
        "kind": "float", "lo": 1e6, "hi": 4e6, "lane": "lighter-books",
        "note": ("Barnesy carry sleeve 24h $ turnover floor; env default 2e6 "
                 "= 🌾 the parent's. Cage lo is 1e6 NOT lower on purpose: at "
                 "the >=20%% apr gate the venue's crypto candidates run "
                 "$600-$23k/day against an $80 clip, so a deeper cut buys "
                 "unfillable names, not trades"),
        "env_default": 2e6, "step": -250000.0},
    "barnes.extreme_min_vol": {
        "kind": "float", "lo": 5e6, "hi": 20e6, "lane": "lighter-books",
        "note": ("Barnesy extreme sleeve 24h $ turnover floor; env default "
                 "10e6 = 💸 the Farmer's liquidity floor. Directional and "
                 "unhedged, so its floor stays above the carry sleeve's"),
        "env_default": 10e6, "step": -1e6},
    "barnes.xsect_universe_n": {
        "kind": "int", "lo": 30, "hi": 60, "lane": "lighter-books",
        "note": ("Barnesy xsect cross-section width; env default 30 == the "
                 "validated 30-name core, so no scout book is added. Cage lo "
                 "is 30: the rail may never rank FEWER names than the "
                 "validated list, and widening past it re-runs the experiment "
                 "(jg) reverted on the parent"),
        "env_default": 30, "step": 5},
    "fundspread.universe_n": {
        # [2026-08-04] default 60 -> 30 with fundspread.k: width 30 == the
        # 30-name hand list both validations ranked, so no scout book is added.
        "kind": "int", "lo": 20, "hi": 90, "lane": "lighter-books",
        "note": "Counterweight scout-universe width; env default 30", "env_default": 30, "step": 10},
    "disloc.enter_pct": {
        # Snap Back's gate was a FIXED 150bps against a measured median
        # residual of 3.8bps — ~40x the middle of its own signal, which is
        # why it has 10 closes. Now a PERCENTILE of the live residual
        # distribution, so it tracks the venue instead of a constant
        # inherited from the Hyperliquid-referenced era.
        "kind": "float", "lo": 0.90, "hi": 0.999, "lane": "lighter-books",
        "note": "Snap Back entry percentile of the live residual; default 0.98", "env_default": 0.98, "step": -0.01},
    "disloc.universe_n": {
        "kind": "int", "lo": 10, "hi": 60, "lane": "lighter-books",
        "note": "Snap Back scout-universe width; env default 40", "env_default": 40, "step": 10},
    # [2026-07-30 (gu)] THE FLEET'S FIRST EXIT LEVER. Until now all 9 levers on
    # this lane were ENTRY or CAPACITY — the growth rail could move what every
    # book OPENS and nothing about what it CLOSES, on a fleet whose exits (gq)
    # showed decide the result.
    #
    # WHY THIS ONE FIRST, and why it is not an arbitrary pick: Snap Back's exit
    # target throttles its own ENTRY. (fz) replaced its fixed 150bps entry gate
    # with a percentile of the live residual distribution — then floored that
    # adaptive gate at `EXIT_BPS * ENTER_FLOOR_MULT` = 40 * 1.5 = **60bps**.
    # Measured live this hour across 90 liquid books: median **7.9bps**, p90
    # **21.8bps**, max **50.1bps**. So the floor sits ABOVE the 90th percentile
    # of the very distribution the gate adapts to — the adaptation can only
    # descend to a bound set by a stale exit constant, which is the same class
    # of defect the adaptive gate was introduced to remove. (gq) corroborates
    # from the other side: this book's dominant exit is `long_max_hold`, i.e.
    # positions TIME OUT instead of converging, because 40bps convergence is
    # outside what the tape delivers.
    #
    # CAGE DERIVED FROM THE MEASUREMENT, not chosen: lo 8 ≈ the live median
    # (a target the tape reaches most days), hi 40 = the operator's current
    # default (so this lever can only ever LOOSEN the exit toward the observed
    # distribution, never tighten it beyond today's setting). Default UNCHANGED
    # at 40 — registering a lever moves nothing; it makes the constant
    # REACHABLE by the organ that measures, instead of by me picking a number.
    # `step` is negative for the same reason the entry percentile's is.
    "disloc.exit_bps": {
        "kind": "float", "lo": 8.0, "hi": 40.0, "lane": "lighter-books",
        "note": ("Snap Back convergence target in bps; env default 40. Also "
                 "sets the ADAPTIVE ENTRY FLOOR via ENTER_FLOOR_MULT, so this "
                 "one constant governs both sides — the only lever on this "
                 "lane that does"),
        "env_default": 40.0, "step": -4.0},
    "index.max_open": {
        "kind": "int", "lo": 3, "hi": 12, "lane": "lighter-books",
        "note": "Index Rider concurrent sleeves; env default 9 (a LITERAL since (hl) — it tracked len(SYMBOLS) and drifted)",
        "env_default": 9, "step": 2},
    "trend.rank_by_funding": {
        # [2026-07-30 (hk)] HONEST NOTE: this lever cannot change what this book
        # trades. It only reorders ADMISSION, and it is inert whenever
        # candidates <= slots — measured, the maximum number of simultaneously
        # golden coins over 192 aligned days was ONE, against six slots. It is
        # kept (it costs nothing and binds once the universe is wide enough to
        # oversubscribe the slots) but `trend.universe_n` below is the lever
        # that actually moves the trade rate. `step: 0` is deliberate and is
        # why audit_lever_bounds exempts binary levers from the step rule.
        "kind": "int", "lo": 0, "hi": 1, "lane": "lighter-books",
        "note": "Tide Rider ranks candidates by funding; env default 1 (on)", "env_default": 1, "step": 0},
    # [2026-07-30 (hk)] THE TWO LEVERS THAT CAN ACTUALLY MOVE TIDE RIDER'S RATE.
    # Until now this book had exactly ONE registered lever and it was inert by
    # construction (above) — i.e. it was in the registry without being able to
    # grow, the failure this tier exists to prevent, one level subtler than the
    # six books that had no levers at all.
    "trend.universe_n": {
        # The scan ceiling: configured core first, then the scout's most-liquid
        # books. `golden()` needs 202 CLOSED daily bars so young books are
        # skipped for free; the real cost of a wider N is one candle fetch per
        # coin per loop, which is why hi is 60 and not 220.
        "kind": "int", "lo": 6, "hi": 60, "lane": "lighter-books",
        "note": "Tide Rider scan universe (configured core + scout's most liquid); env default 24",
        "env_default": 24, "step": 4},
    "trend.max_open": {
        # The capacity lever, registered so the SATURATED branch of the board's
        # book author has something to step once a 24-wide universe can actually
        # oversubscribe six slots. Inert until then, by construction — with a
        # 6-coin universe the book never held more than one position.
        # [2026-07-30 (hl)] hi 12 -> 9, and this is a SAFETY bound, not a
        # throughput one. Measured: the maximum number of simultaneously-golden
        # books over 500 days at the live universe is SIX, and 7 at the cage
        # extreme — so the lever has never bound and cannot. What >=10 DOES do
        # is make the -10% daily-loss halt reachable BEFORE the -35%
        # catastrophic stop, and in shadow that halt `continue`s past the whole
        # scan: no death cross, no seatbelt, no marks for the rest of the UTC
        # day. Capping at 9 makes that branch unreachable by construction
        # rather than leaving it armed for an author to walk into.
        "kind": "int", "lo": 2, "hi": 9, "lane": "lighter-books",
        "note": "Tide Rider concurrent long slots; env default 6 (hi capped at 9 — see the halt note)",
        "env_default": 6, "step": 1},
    "trend.min_vol_m": {
        # Liquidity floor on the SCOUT-added books only — the configured majors
        # are never filtered out by it. Restrict direction is UP (a higher floor
        # admits fewer books), so the growth step is negative.
        "kind": "float", "lo": 1.0, "hi": 50.0, "lane": "lighter-books",
        # [2026-07-30 (hl)] 5.0 -> 3.0. Measured: 3.0 admits ZEC ($3.38M) and
        # PAXG, which carry 91% of the whole measured delta; going further to
        # 2.0 buys 6 more trades and LOWERS the mean (+8.52% -> +7.93%) by
        # admitting books held for weeks at $0.58-1.29M/day. 3.0 is the point
        # where the candidates stop paying for themselves.
        "note": "Tide Rider scout-universe 24h $M liquidity floor; env default 3.0",
        "env_default": 3.0, "step": -0.5},
    "sniper.surge_mult": {
        # the sniper's event (a brand-new listing) is too rare to grade —
        # n=1 in weeks, and `new_listings` is empty on the bus right now.
        # This widens the TRIGGER to the adjacent population (young book +
        # volume surge) rather than widening any risk bound.
        "kind": "float", "lo": 2.0, "hi": 8.0, "lane": "lighter-books",
        "note": "Perp Sniper volume-surge trigger multiple; env default 3.0", "env_default": 3.0, "step": -0.5},
}


#: [2026-08-06 (kp)] Levers this container could not express as written —
#: {name: {"written", "clamped", "n", "since"}}. Kept as STATE, not announced
#: once and forgotten: I4 — "never report a persistent condition with a
#: one-shot warning". A skew persists until the image is redeployed, so it has
#: to stay readable for as long as it is true. `skewed_levers()` is the
#: supported read.
_SKEW = {}


def skewed_levers():
    """{name: {written, clamped, n, since}} for levers this container's
    registry cannot express — i.e. it is running an older cage than the lever's
    author. Empty in a consistently-deployed fleet."""
    return {k: dict(v) for k, v in _SKEW.items()}


def _skewed(name, written, clamped, now_ts=None):
    """True when `written` and `clamped` differ — recorded, then refused."""
    try:
        same = abs(float(written) - float(clamped)) < 1e-9
    except (TypeError, ValueError):
        same = written == clamped
    if same:
        _SKEW.pop(name, None)
        return False
    prev = _SKEW.get(name)
    if not prev or prev["written"] != written or prev["clamped"] != clamped:
        # Print on first sighting and on any CHANGE, not once ever.
        print(f"[fleet_tuning] LEVER SKEW {name}: author wrote {written!r}, "
              f"this container's cage clamps to {clamped!r} — refusing to the "
              f"operator default. This image is running an older registry "
              f"than the lever's author; redeploy it.", flush=True)
        _SKEW[name] = {"written": written, "clamped": clamped, "n": 1,
                       "since": now_ts if now_ts is not None else time.time()}
    else:
        prev["n"] += 1
    return True


def clamp(name, value):
    """Registry-checked, bounds-clamped value; None if unusable/unknown."""
    spec = LEVERS.get(name)
    if not spec:
        return None
    kind = spec["kind"]
    try:
        if kind == "float":
            return min(spec["hi"], max(spec["lo"], float(value)))
        if kind == "int":
            return int(min(spec["hi"], max(spec["lo"], int(value))))
        if kind == "csv":
            items = value if isinstance(value, (list, tuple)) else str(value).split(",")
            kept = [s.strip() for s in items if s.strip() in spec["allowed"]]
            return ",".join(dict.fromkeys(kept))     # dedup, order-stable
    except (TypeError, ValueError):
        return None
    return None


def _is_fresh(payload, now_ts):
    try:
        u = datetime.fromisoformat(str(payload["updated"]).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        age = now_ts - u.timestamp()
        return 0 <= age <= float(payload.get("ttl_sec") or 0)
    except Exception:
        return False


_cache = {"ts": 0.0, "payload": None}
_immune_cache = {"ts": 0.0, "q": frozenset()}
_prop_cache = {"ts": 0.0, "h": frozenset()}


def _load(now_ts):
    if now_ts - _cache["ts"] < CACHE_SEC:
        return _cache["payload"]
    payload = None
    try:
        if store is not None:
            payload = store.load_state(KEY) or None
    except Exception:
        payload = None
    _cache.update(ts=now_ts, payload=payload)
    return payload


def _quarantined(now_ts):
    """Levers the immune organ ('fleet-immune') has quarantined — get_lever
    returns the caller's default for these, so a sick lever reverts to the
    operator's own value. Fail-safe OPEN: a stale/absent immune payload
    quarantines nothing (a dead immune organ must not paralyze tuning; the
    levers stay bounded + TTL'd regardless)."""
    if now_ts - _immune_cache["ts"] < CACHE_SEC:
        return _immune_cache["q"]
    q = frozenset()
    try:
        if store is not None:
            p = store.load_state("fleet-immune") or {}
            if _is_fresh(p, now_ts):
                q = frozenset((p.get("quarantined_levers") or {}).keys())
    except Exception:
        q = frozenset()
    _immune_cache.update(ts=now_ts, q=q)
    return q


def _live_hurting(now_ts):
    """[2026-07-16 late, operator: 'and with the new rule, real money bots
    too'] LIVE-lane levers whose fleet_proprioception verdict is HURTING —
    get_lever returns the caller's env default for these, so a measured-bad
    lever stops steering REAL MONEY at the consumer, every loop, without
    waiting out the board's 10-min cycle, the judge's hourly cycle, or the
    lever's TTL. Same one-hook-protects-every-consumer pattern as the
    immune quarantine above: the funding bot's apply_levers and both live
    bots' clip read (venues VenueContext.order_usd) all pass through here.
    LIVE LANE ONLY: shadow lanes keep TTL semantics — their authors already
    stop re-asserting on hurting, and an instant consumer-side revert there
    would distort the learning dynamics the 21-Jul review grades. Fail-safe
    OPEN: a dark/stale organ reverts nothing (a dead sense must not steer;
    levers stay bounded + TTL'd regardless). Restrict-only by construction:
    the hook can only ever hand back the operator's own default."""
    if now_ts - _prop_cache["ts"] < CACHE_SEC:
        return _prop_cache["h"]
    h = frozenset()
    try:
        if store is not None:
            p = store.load_state("fleet-proprioception") or {}
            if _is_fresh(p, now_ts):
                h = frozenset(
                    k for k, v in (p.get("verdicts") or {}).items()
                    if isinstance(v, dict) and v.get("verdict") == "hurting")
    except Exception:
        h = frozenset()
    _prop_cache.update(ts=now_ts, h=h)
    return h


def _lever_alive(entry, now_ts):
    """A lever entry is alive until its own `expires` stamp (falling back to
    never-expired for entries that predate per-lever expiry)."""
    try:
        exp = entry.get("expires")
        if not exp:
            return True
        e = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        if e.tzinfo is None:
            e = e.replace(tzinfo=timezone.utc)
        return e.timestamp() > now_ts
    except Exception:
        return False


def get_lever(name, default, now_ts=None):
    """Fresh, unexpired, un-quarantined, not-hurting-on-live, registered,
    clamped lever value — or the caller's default."""
    now_ts = now_ts if now_ts is not None else time.time()
    try:
        spec = LEVERS.get(name)
        # [2026-07-17 AUDIT] THE LANE GATE, at the CONSUMER. FLEET_TUNING_ENACT_LANES
        # is documented as the per-lane kill switch — "Remove the lane from this
        # env to kill it" (:74) — but the check lived ONLY in write_levers
        # (:385). get_lever tested quarantine, live-hurting, freshness, expiry
        # and clamp, and never the lane. Measured with the live lane removed:
        #   get_lever('live.clip_scale', 1.0)         -> 1.5     (should be 1.0)
        #   get_lever('live.funding.enter_apr', 0.05) -> 0.075   (should be 0.05)
        # i.e. throwing the documented switch changed nothing a bot reads; an
        # already-written lever kept steering REAL MONEY until its TTL lapsed —
        # and only if the AUTHOR's service also got the env and was redeployed.
        # This is the exact shape of the 17-Jul FLEET_RISK_MODE finding (a kill
        # switch only some consumers honoured), which is now a CLAUDE.md rule:
        # a switch that does not reach the consumer is not a switch. Checked
        # FIRST, so a killed lane short-circuits every other read. `not spec`
        # keeps the old behaviour for unregistered names (they fell through to
        # clamp() -> None -> default anyway). Inert by default: the shipped
        # ENACT_LANES contains all six lanes (paper-scanner, lighter-scout,
        # lighter-taker, lighter-live, lighter-xp, event-sentinel — the last
        # added 21-Jul; this comment said "five" until the 23-Jul audit).
        if not spec or spec.get("lane") not in ENACT_LANES:
            return default                   # lane switched off -> operator default
        if name in _quarantined(now_ts):
            return default                   # immune-quarantined -> operator default
        if (spec.get("lane") == "lighter-live"
                and name in _live_hurting(now_ts)):
            return default                   # measured-bad LIVE lever -> operator default
        p = _load(now_ts)
        if not p or not _is_fresh(p, now_ts):
            return default
        entry = (p.get("levers") or {}).get(name)
        if not isinstance(entry, dict) or not _lever_alive(entry, now_ts):
            return default
        written = entry.get("value")
        v = clamp(name, written)
        if v is None:
            return default
        # [2026-08-06 (kp)] A READ-TIME CLAMP IS A VERSION SKEW, NEVER A
        # LEGITIMATE ADJUSTMENT — so it REFUSES rather than silently
        # substituting a different number.
        #
        # `write_levers` already clamps every value against the AUTHOR's
        # registry before it reaches the bus. So a value that needs clamping
        # HERE can only mean the author's registry and this container's
        # disagree: a cage moved and this image has not been redeployed. The
        # old behaviour was `min(hi, max(lo, v))`, which quietly applied a
        # DIFFERENT value than the author wrote and told nobody.
        #
        # THE LIVE INSTANCE this was written for: `(ka)` moved
        # `{xp,live}.funding.min_vol` cage lo from 2e6 to 1e5 and filed
        # `min-vol-1e5` in the judge's queue. Both 💸 Farmer arms are
        # marker-gated and 17 commits behind, still carrying lo=2e6 — so when
        # the judge reaches that candidate it would write 1e5, the container
        # would clamp it to 2e6, and the judge would grade a thin-tier
        # experiment the book never ran, against a value identical to the
        # `min-vol-2e6` candidate queued beside it. An A/B measuring the wrong
        # arm, silently, on the pipeline that feeds real money.
        #
        # Refusing to the OPERATOR DEFAULT is the same fail-safe direction
        # this function already takes for a quarantined lever, a measured-bad
        # live lever and a stale payload: when in doubt, the operator's value.
        if _skewed(name, written, v, now_ts):
            return default
        return v
    except Exception:
        return default


def active_levers(now_ts=None):
    """{name: entry} of currently-live levers (for display/telemetry).

    [2026-07-17 AUDIT] Honours ENACT_LANES too, so this cannot report a lever
    as ACTIVE that get_lever now ignores — the dashboard's 🎚️ count and the
    Autonomy card read this, and a switched-off lane still listed here would
    tell the operator the switch had not worked. Display must agree with the
    consumer; a telemetry view that disagrees with the actuator is how you get
    talked out of a correct kill."""
    now_ts = now_ts if now_ts is not None else time.time()
    p = _load(now_ts)
    if not p or not _is_fresh(p, now_ts):
        return {}
    return {k: v for k, v in (p.get("levers") or {}).items()
            if k in LEVERS and isinstance(v, dict) and _lever_alive(v, now_ts)
            and LEVERS[k].get("lane") in ENACT_LANES}


def write_levers(levers, set_by="evidence-board", now_ts=None, ttl_sec=None):
    """Author lever entries, MERGED with other authors' live levers (the
    board and the scout tuner share this key — a write must never clobber
    the other author's lane). Drops unknown/out-of-lane levers, clamps every
    value, stamps per-lever `expires` (auto-revert) + payload updated/ttl.
    Returns the payload written, or None when nothing valid survived (or no
    DB). Never raises."""
    now_ts = now_ts if now_ts is not None else time.time()
    ttl = float(ttl_sec or TTL_SEC)

    def _iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")

    out = {}
    for name, entry in (levers or {}).items():
        spec = LEVERS.get(name)
        if not spec or spec["lane"] not in ENACT_LANES:
            continue
        if not _author_may_write(name, spec["lane"], set_by):
            continue
        v = clamp(name, (entry or {}).get("value"))
        if v is None:
            continue
        # [2026-07-16] optional per-entry ttl_sec — may only SHORTEN the
        # call-level TTL (floor 60s), never extend it: faster auto-revert is
        # always allowed, a longer-lived lever never is. The board uses this
        # to give its real-money live.clip_scale a 30-min leash while the
        # scanner levers keep the 2h default.
        ettl = ttl
        try:
            e_req = float((entry or {}).get("ttl_sec") or 0)
            if e_req > 0:
                ettl = max(60.0, min(ttl, e_req))
        except (TypeError, ValueError):
            pass
        out[name] = {"value": v, "lane": spec["lane"], "set_by": set_by,
                     "expires": _iso(now_ts + ettl),
                     "reason": str((entry or {}).get("reason") or "")[:200],
                     "evidence": str((entry or {}).get("evidence") or "")[:300]}
    if not out:
        return None

    def _merge_payload(prev):
        """Merge MY levers over the other authors' still-alive levers. Pure —
        runs under the store's advisory lock when available."""
        merged = {k: v for k, v in ((prev or {}).get("levers") or {}).items()
                  if k in LEVERS and isinstance(v, dict) and k not in out
                  and v.get("set_by") != set_by and _lever_alive(v, now_ts)}
        merged.update(out)
        # payload ttl covers the longest-lived lever so readers stay fresh
        horizon = now_ts
        for v in merged.values():
            try:
                e = datetime.fromisoformat(str(v.get("expires")).replace("Z", "+00:00"))
                horizon = max(horizon, e.timestamp())
            except Exception:
                horizon = max(horizon, now_ts + ttl)
        return {"updated": _iso(now_ts),
                "ttl_sec": int(max(ttl, horizon - now_ts)),
                "levers": merged}

    try:
        if store is None:
            return None
        # [2026-07-16 MERGE-RACE FIX] three authors write this key on
        # independent timers; a merge off a stale read silently dropped the
        # other author's just-written levers. The advisory-locked update
        # serializes read->merge->write; the unlocked path stays as the
        # fallback so a lock failure degrades to exactly today's behavior.
        payload = None
        if hasattr(store, "locked_state_update"):
            payload = store.locked_state_update(KEY, _merge_payload)
        if payload is None:
            prev = {}
            try:
                prev = store.load_state(KEY) or {}
            except Exception:
                prev = {}
            payload = _merge_payload(prev)
            # [2026-07-16 F3 REPAIR — adversarial-verify finding] save_state
            # returns False on a failed write and NEVER raises; ignoring it
            # returned a truthy payload that never persisted (reads-OK/
            # writes-failing DB — e.g. Postgres flipped read-only), which
            # false-positived every "landed" check downstream, including the
            # board's live_write_ok guard on the real-money push. None on a
            # failed durable write is the documented contract — honor it.
            if not store.save_state(KEY, payload):
                return None
        if hasattr(store, "save_history"):
            store.save_history(KEY, {"updated": payload["updated"],
                                     "levers": {k: v["value"] for k, v in out.items()},
                                     "set_by": set_by})
        _cache.update(ts=now_ts, payload=payload)   # readers in-process see it
        return payload
    except Exception:
        return None


def _released_payload(prev, names, set_by, now_ts):
    """Pure: `prev` minus MY named levers — other authors' levers and my
    unnamed levers survive, dead entries are pruned, updated/ttl recomputed.
    Selftested offline; runs under the store's advisory lock when available."""
    def _iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
    levers = {k: v for k, v in ((prev or {}).get("levers") or {}).items()
              if k in LEVERS and isinstance(v, dict) and _lever_alive(v, now_ts)
              and not (k in names and v.get("set_by") == set_by)}
    horizon = now_ts
    for v in levers.values():
        try:
            e = datetime.fromisoformat(str(v.get("expires")).replace("Z", "+00:00"))
            horizon = max(horizon, e.timestamp())
        except Exception:
            horizon = max(horizon, now_ts + TTL_SEC)
    return {"updated": _iso(now_ts),
            "ttl_sec": int(max(60, horizon - now_ts)),
            "levers": levers}


def release_levers(names, set_by, now_ts=None):
    """[2026-07-16] Withdraw MY OWN named levers NOW — auto-revert without
    the TTL wait. The honest twin of write_levers for the moment an author's
    evidence LAPSES: the lever disappears from the rail (consumers fall back
    to operator defaults immediately) instead of lingering to expiry or
    being overwritten with a no-op value that downstream graders would
    treat as a real stance. An author can never release another author's
    lever. Returns the payload written; None only when no lever names were
    given or the DB path is unavailable (callers retry). Never raises."""
    now_ts = now_ts if now_ts is not None else time.time()
    names = {str(n) for n in (names or ())}
    if not names:
        return None
    try:
        if store is None:
            return None
        payload = None
        if hasattr(store, "locked_state_update"):
            payload = store.locked_state_update(
                KEY, lambda prev: _released_payload(prev, names, set_by, now_ts))
        if payload is None:
            prev = {}
            try:
                prev = store.load_state(KEY) or {}
            except Exception:
                prev = {}
            payload = _released_payload(prev, names, set_by, now_ts)
            # [2026-07-16 F3 REPAIR] same landed-signal contract as
            # write_levers: a failed durable write must return None.
            if not store.save_state(KEY, payload):
                return None
        if hasattr(store, "save_history"):
            store.save_history(KEY, {"updated": payload["updated"],
                                     "released": sorted(names),
                                     "set_by": set_by})
        _cache.update(ts=now_ts, payload=payload)
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------

def _selftest():
    now = time.time()
    # clamping: bounds enforced, unknown dropped, junk rejected
    assert clamp("gapscout.prefilter_gap", 0.0001) == 0.0010     # floor
    assert clamp("gapscout.prefilter_gap", 0.5) == 0.0030        # ceiling
    assert clamp("gapscout.prefilter_gap", 0.0015) == 0.0015
    assert clamp("gapscout.max_book_fetches", 999) == 60
    assert clamp("gapscout.max_book_fetches", "45") == 45
    assert clamp("nonexistent.lever", 1) is None
    assert clamp("gapscout.prefilter_gap", "junk") is None
    # csv: only whitelisted venues survive, deduped
    assert clamp("gapscout.extra_exchanges", "kucoin, binance, gateio,kucoin") == "kucoin,gateio"
    assert clamp("gapscout.extra_exchanges", ["mexc", "evil"]) == "mexc"
    assert clamp("gapscout.extra_exchanges", "binance") == ""
    # reader: stale payload -> default; fresh -> clamped value
    _cache.update(ts=now, payload={"updated": "2020-01-01T00:00:00+00:00",
                                   "ttl_sec": 7200,
                                   "levers": {"gapscout.prefilter_gap": {"value": 0.0015}}})
    assert get_lever("gapscout.prefilter_gap", 0.002, now_ts=now) == 0.002
    fresh_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="seconds")
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {"gapscout.prefilter_gap": {"value": 0.9},
                                              "gapscout.extra_exchanges": {"value": "kucoin"}}})
    # [2026-08-06 (kp)] WAS: `== 0.0030  # clamped`. A read-time clamp now
    # REFUSES to the operator default instead of silently applying a value the
    # author never wrote. This payload (0.9 against a 0.0030 cage) is written
    # straight into the cache by hand — `write_levers` clamps against the
    # AUTHOR's registry, so a value needing a clamp HERE can only be a version
    # skew or a corrupted payload, and in both cases the operator's default
    # beats a number nobody chose. Deliberate behaviour change, stated rather
    # than absorbed.
    assert get_lever("gapscout.prefilter_gap", 0.002, now_ts=now) == 0.002
    assert "gapscout.prefilter_gap" in skewed_levers()
    _SKEW.clear()
    assert get_lever("gapscout.extra_exchanges", "", now_ts=now) == "kucoin"
    assert get_lever("unknown.lever", 7, now_ts=now) == 7
    # immune QUARANTINE: a quarantined lever returns the caller's default
    # even with a fresh, in-bounds value present
    _immune_cache.update(ts=now, q=frozenset({"gapscout.prefilter_gap"}))
    assert get_lever("gapscout.prefilter_gap", 0.002, now_ts=now) == 0.002
    assert get_lever("gapscout.extra_exchanges", "", now_ts=now) == "kucoin"  # others fine
    _immune_cache.update(ts=now, q=frozenset())    # clear for later asserts
    # 🦾 LIVE hurting-revert (the real-money consumer hook): a fresh HURTING
    # verdict on a lighter-live lever returns the caller's env default at
    # the consumer; SHADOW lanes keep their TTL semantics (lane-scoped)
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {"live.clip_scale": {"value": 1.25},
                                              "live.funding.enter_apr": {"value": 0.0375},
                                              "taker.tp": {"value": 0.05}}})
    _prop_cache.update(ts=now, h=frozenset({"live.clip_scale",
                                            "live.funding.enter_apr",
                                            "taker.tp"}))
    assert get_lever("live.clip_scale", 1.0, now_ts=now) == 1.0, \
        "hurting LIVE lever -> operator default"
    assert get_lever("live.funding.enter_apr", 0.05, now_ts=now) == 0.05
    assert get_lever("taker.tp", 0.04, now_ts=now) == 0.05, \
        "shadow lane keeps TTL semantics (author-side skip owns it)"
    _prop_cache.update(ts=now, h=frozenset())
    assert get_lever("live.clip_scale", 1.0, now_ts=now) == 1.25, \
        "verdict cleared -> the asserted lever applies again"
    assert get_lever("live.funding.enter_apr", 0.05, now_ts=now) == 0.0375
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {"gapscout.prefilter_gap": {"value": 0.9},
                                              "gapscout.extra_exchanges": {"value": "kucoin"}}})
    assert set(active_levers(now_ts=now)) == {"gapscout.prefilter_gap",
                                              "gapscout.extra_exchanges"}
    # per-lever expiry: a dead lever yields the default even in a fresh payload
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {
                                       "taker.tp": {"value": 0.05,
                                                    "expires": "2020-01-01T00:00:00+00:00"},
                                       "taker.sl": {"value": -0.02}}})   # no expires = alive
    assert get_lever("taker.tp", 0.04, now_ts=now) == 0.04, "expired lever -> default"
    assert get_lever("taker.sl", -0.03, now_ts=now) == -0.02
    assert set(active_levers(now_ts=now)) == {"taker.sl"}
    # writer: unknown/out-of-lane dropped, values clamped, expires stamped,
    # merge keeps OTHER authors' live levers. Writer tests run against a
    # stubbed ALWAYS-SUCCEEDS store (no local DB) so the merge/clamp logic
    # executes; the failed-write landed-signal contract is pinned right
    # after with the opposite stub.
    _real_save = getattr(store, "save_state", None) if store else None
    _real_locked = getattr(store, "locked_state_update", None) if store else None
    if store is not None:
        store.save_state = lambda k, s: True
        store.locked_state_update = lambda k, fn: None    # force the fallback
    p = write_levers({"gapscout.prefilter_gap": {"value": 0.00001, "reason": "r"},
                      "taker.dip_range": {"value": 0.99},
                      "not.a.lever": {"value": 1}}, set_by="t", now_ts=now)
    if p is not None:                       # store module importable
        assert set(p["levers"]) >= {"gapscout.prefilter_gap", "taker.dip_range"}
        assert p["levers"]["gapscout.prefilter_gap"]["value"] == 0.0010
        assert p["levers"]["taker.dip_range"]["value"] == 0.15       # clamped
        assert p["levers"]["taker.dip_range"]["expires"] > fresh_iso[:10]
    # [2026-07-16 AUDIT] author -> lane binding: only the board may write
    # live.clip_scale, only the judge live.funding.*; nobody else touches
    # the live lane (this was convention only — now enforced)
    assert _author_may_write("live.clip_scale", "lighter-live", "evidence-board")
    assert not _author_may_write("live.clip_scale", "lighter-live", "scout-tuner")
    assert not _author_may_write("live.clip_scale", "lighter-live", "experiment-judge")
    assert _author_may_write("live.funding.enter_apr", "lighter-live", "experiment-judge")
    assert not _author_may_write("live.funding.enter_apr", "lighter-live", "evidence-board")
    assert not _author_may_write("live.clip_scale", "lighter-live", "t")  # unbound
    assert _author_may_write("gapscout.prefilter_gap", "paper-scanner", "t")
    assert not _author_may_write("taker.tp", "lighter-taker", "experiment-judge")
    p_bad = write_levers({"live.clip_scale": {"value": 1.5}}, set_by="scout-tuner",
                         now_ts=now)
    assert p_bad is None or "live.clip_scale" not in p_bad["levers"], \
        "tuner must never write the live lane"
    p_j = write_levers({"xp.funding.enter_apr": {"value": 0.30},
                        "live.funding.enter_apr": {"value": 0.0375},
                        "live.clip_scale": {"value": 1.5}},
                       set_by="experiment-judge", now_ts=now)
    if p_j is not None:
        assert "xp.funding.enter_apr" in p_j["levers"]
        assert "live.funding.enter_apr" in p_j["levers"]
        assert p_j["levers"].get("live.clip_scale", {}).get("set_by") != \
            "experiment-judge", "judge must never write the board's clip lever"
    # per-entry ttl_sec: shortens the leash, can never extend it
    p_ttl = write_levers({"live.clip_scale": {"value": 1.25, "ttl_sec": 1800},
                          "gapscout.prefilter_gap": {"value": 0.0015},
                          "gapscout.max_book_fetches": {"value": 45,
                                                        "ttl_sec": 999999}},
                         set_by="evidence-board", now_ts=now)
    if p_ttl is not None:
        from datetime import timedelta
        _short = datetime.fromtimestamp(now + 1800, tz=timezone.utc).isoformat(timespec="seconds")
        _full = datetime.fromtimestamp(now + TTL_SEC, tz=timezone.utc).isoformat(timespec="seconds")
        assert p_ttl["levers"]["live.clip_scale"]["expires"] == _short, \
            "per-entry ttl must shorten expiry"
        assert p_ttl["levers"]["gapscout.prefilter_gap"]["expires"] == _full
        assert p_ttl["levers"]["gapscout.max_book_fetches"]["expires"] == _full, \
            "per-entry ttl must never EXTEND the call-level TTL"
    # release: an author withdraws its OWN lever instantly; other authors'
    # levers and its own unnamed levers survive; dead entries are pruned
    _far = datetime.fromtimestamp(now + 3600, tz=timezone.utc).isoformat(timespec="seconds")
    _prev = {"levers": {
        "live.clip_scale": {"value": 1.25, "set_by": "evidence-board",
                            "expires": _far},
        "gapscout.prefilter_gap": {"value": 0.0015, "set_by": "evidence-board",
                                   "expires": _far},
        "live.funding.enter_apr": {"value": 0.0375, "set_by": "experiment-judge",
                                   "expires": _far},
        "taker.tp": {"value": 0.05, "set_by": "scout-tuner",
                     "expires": "2020-01-01T00:00:00+00:00"}}}
    rp = _released_payload(_prev, {"live.clip_scale", "live.funding.enter_apr"},
                           "evidence-board", now)
    assert "live.clip_scale" not in rp["levers"], "own named lever released"
    assert "live.funding.enter_apr" in rp["levers"], \
        "another author's lever must survive my release"
    assert "gapscout.prefilter_gap" in rp["levers"], "my unnamed lever survives"
    assert "taker.tp" not in rp["levers"], "dead entries pruned in passing"
    assert rp["ttl_sec"] >= 60
    assert release_levers([], "evidence-board", now_ts=now) is None
    # [F3 REPAIR] the landed-signal contract: a reads-OK/writes-FAILING
    # store (save_state -> False, locked path unavailable) must yield None
    # from BOTH authors — a payload that never persisted must never read
    # as a landed real-money write (the board's live_write_ok depends on it)
    if store is not None:
        store.save_state = lambda k, s: False
        assert write_levers({"live.clip_scale": {"value": 0.75}},
                            set_by="evidence-board", now_ts=now) is None, \
            "failed durable write must not report as landed"
        assert release_levers(["live.clip_scale"], "evidence-board",
                              now_ts=now) is None, \
            "failed durable release must not report as landed"
        if _real_save is not None:
            store.save_state = _real_save
        if _real_locked is not None:
            store.locked_state_update = _real_locked
    # every registered lever must clamp its own documented default
    for name, spec in LEVERS.items():
        if spec["kind"] in ("float", "int"):
            assert clamp(name, spec["lo"]) == spec["lo"]
            assert clamp(name, spec["hi"]) == spec["hi"]

    # [2026-07-17 AUDIT] THE LANE KILL SWITCH, ASSERTED AT THE CONSUMER.
    # ENACT_LANES only ever gated write_levers, so a lever ALREADY WRITTEN kept
    # steering real money through a thrown switch. The old suite tested the
    # write side and called it covered — but the operator throws this switch to
    # stop a lever that is already in force, which is precisely the case nothing
    # tested. Drive get_lever/active_levers directly with the live lane removed.
    _saved_lanes = ENACT_LANES
    _saved_load, _saved_q, _saved_h = _load, _quarantined, _live_hurting
    try:
        _t = 1_800_000_000.0

        def _ts(ts):
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        _p = {"updated": _ts(_t), "ttl_sec": 3600, "levers": {
            "live.clip_scale": {"value": 1.5, "expires": _ts(_t + 3600),
                                "set_by": "evidence-board"},
            "taker.dip_range": {"value": 0.11, "expires": _ts(_t + 3600),
                                "set_by": "scout-tuner"}}}
        globals()["_load"] = lambda now_ts=None: _p
        globals()["_quarantined"] = lambda now_ts=None: set()
        globals()["_live_hurting"] = lambda now_ts=None: set()

        globals()["ENACT_LANES"] = {"paper-scanner", "lighter-scout",
                                    "lighter-taker", "lighter-live", "lighter-xp"}
        assert get_lever("live.clip_scale", 1.0, _t) == 1.5, "shipped lanes: enacted"
        assert get_lever("taker.dip_range", 0.08, _t) == 0.11
        assert set(active_levers(_t)) == {"live.clip_scale", "taker.dip_range"}

        # the operator kills ONLY the live lane
        globals()["ENACT_LANES"] = {"paper-scanner", "lighter-scout",
                                    "lighter-taker", "lighter-xp"}
        assert get_lever("live.clip_scale", 1.0, _t) == 1.0, \
            "REGRESSION: a killed lane still steers REAL MONEY at the consumer"
        assert get_lever("taker.dip_range", 0.08, _t) == 0.11, \
            "killing one lane must not disturb another"
        assert set(active_levers(_t)) == {"taker.dip_range"}, \
            "display must not report a killed lane as active"

        # kill everything -> every consumer reads the operator's env default
        globals()["ENACT_LANES"] = set()
        assert get_lever("live.clip_scale", 1.0, _t) == 1.0
        assert get_lever("taker.dip_range", 0.08, _t) == 0.08
        assert active_levers(_t) == {}
        # an UNREGISTERED name keeps its old behaviour (default), not a crash
        assert get_lever("nope.not.a.lever", 7.0, _t) == 7.0
    finally:
        globals()["ENACT_LANES"] = _saved_lanes
        globals()["_load"] = _saved_load
        globals()["_quarantined"] = _saved_q
        globals()["_live_hurting"] = _saved_h

    print("fleet_tuning selftest OK (incl. author-lane binding + per-entry ttl "
          "+ the ENACT_LANES kill switch at the CONSUMER)")


if __name__ == "__main__":
    _selftest()
