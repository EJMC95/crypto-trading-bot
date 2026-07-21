#!/usr/bin/env python3
"""
lighter_scout_tuner.py — 🧠🔧 the Lighter loop's SELF-TUNING organ.

WHY (2026-07-15, user mandate): "i want the scanning tool to be elite, make
the brain elite and scan the lighter universe for the best possible
opportunities and be able to adjust what it needs to … it needs the freedom,
with the brain's support to act on things, skyrocket the learning."

Until now the Lighter loop (scout 🛰️ → taker 🎫 → brain 🧠) could only
LEARN and RESTRICT: the brain grades every ticket counterfactually, the
taker vetoes lenses graded negative, and every widening needed the operator
to ship env changes. This organ closes the circuit — it is the loop's
EXPAND side, and every move it makes is evidence-gated by the fleet's own
doctrine (replay-first = backtest-first; both-halves; bounded levers):

  1. STARVATION → WIDEN (learning-first). A lens that produces no fills
     produces no grades, so it can never learn. Each cycle the tuner walks
     the lens's conviction-bar ladder from the env default, one notch at a
     time, accepting a notch only if the replayed tape (through the taker's
     OWN decision code — lighter_ticket_replay) is NOT WORSE on both halves.
     If the lens emits no tickets at all, the SCOUT's emission bar is the
     bottleneck instead — that widening is advisory-only (more tickets =
     more brain grading, zero trading surface) and reverts once the lens
     reaches the brain's ruling floor.
  2. EXIT-LADDER SWEEP (optimize). The 21-Jul agenda's TP/SL/max-hold grid,
     run automatically: a variant is enacted only when it beats the deployed
     defaults on BOTH halves of the tape AND by a real total margin AND with
     enough closed trades to mean anything (anti-overfit floors below).
  3. NEVER FIGHTS THE BRAIN. A lens the brain grades negative at its ruling
     floor (the taker's veto rule) is never widened — the restrict side owns
     it until the grade recovers.
  4. NEVER REPEATS A MOVEMENT THAT MEASURED BAD (16-Jul, proprioception).
     fleet_proprioception grades every closed lever episode on the tape
     recorded DURING it — out-of-sample relative to this tuner's in-sample
     replay gate. A lever with a fresh HURTING verdict is not re-asserted
     (apply_proprioception; restrict-only, fail-safe none on a dark organ).

STATELESS BY DESIGN: every cycle recomputes the desired bars from the env
DEFAULTS + today's tape, then re-asserts them via fleet_tuning (TTL'd
levers). If the evidence stops supporting a widening, the tuner stops
re-asserting and the lever expires back to default on its own — no ratchet,
no memory to corrupt, auto-revert as the resting state.

WHAT IT CAN NEVER DO: touch anything outside fleet_tuning's registry (hard
bounds, zero-real-money lanes only — the taker is a $1k SHADOW book), or
widen past the registry's ceilings. Live books have no levers to move.

Run-once process; run_all.sh loops it hourly. --selftest is offline.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import fleet_tuning as tuning
import lighter_ticket_taker as tt
import lighter_ticket_replay as rp

try:
    import fleet_proprioception as proprio   # outcome grades (optional import)
except Exception:  # noqa: BLE001
    proprio = None

try:
    import fleet_proposals as fprop          # organ proposal channel (optional)
except Exception:  # noqa: BLE001
    fprop = None

KEY = "scout-tuner"
TTL_SEC = int(os.environ.get("TUNER_TTL_SEC", "10800"))       # 3h payload ttl
LEVER_TTL = int(os.environ.get("TUNER_LEVER_TTL", "7800"))    # 2h10m per lever
MIN_SNAPS = int(os.environ.get("TUNER_MIN_SNAPS", "60"))      # ~5h of tape
MIN_TRADES_SWEEP = int(os.environ.get("TUNER_MIN_TRADES", "10"))
MARGIN_TOTAL = float(os.environ.get("TUNER_MARGIN_TOTAL", "2.0"))   # $ full tape
MARGIN_HALF = float(os.environ.get("TUNER_MARGIN_HALF", "0.5"))     # $ each half
TOL = float(os.environ.get("TUNER_TOL", "0.5"))               # $ not-worse slack
LENS_FLOOR = int(os.environ.get("TT_LENS_VETO_MIN_N", "75"))  # brain ruling floor

# Taker conviction-bar ladders: (tt attr, lever, ladder from default outward)
TAKER_LADDERS = {
    "dip":        ("DIP_RANGE",  "taker.dip_range",  [0.05, 0.08, 0.11, 0.15]),
    "breakout":   ("BRK_RANGE",  "taker.brk_range",  [0.95, 0.93, 0.91, 0.90]),
    "momentum":   ("MOMO_CHG",   "taker.momo_chg",   [5.0, 4.5, 4.0, 3.5, 3.0]),
    # [2026-07-17 BASIS FIX] ladder /8 with the fleet funding basis; every
    # rung must stay inside the (also /8) registry bounds 37.5-87.5.
    "divergence": ("DIV_GAP_PP", "taker.div_gap_pp",
                   [62.5, 56.25, 50.0, 43.75, 37.5]),
}
# Scout emission-bar ladders (advisory tickets — widen the brain's diet).
# [2026-07-16 AUDIT FIX] defaults come from the SCOUT'S OWN env (same names
# it reads — same container), not hardcoded notches: with an operator
# env-widened scout, the old absolute ladder[1] values would have TIGHTENED
# the very bars this organ exists to widen.
SCOUT_LADDERS = {
    "dip":      ("scout.dip_range_max",
                 float(os.environ.get("SCOUT_DIP_RANGE_MAX", "0.1")),
                 [0.10, 0.15, 0.20, 0.25]),
    "breakout": ("scout.brk_range_min",
                 float(os.environ.get("SCOUT_BRK_RANGE_MIN", "0.9")),
                 [0.90, 0.87, 0.84, 0.80]),
    "momentum": ("scout.momo_chg_min",
                 float(os.environ.get("SCOUT_MOMO_CHG_MIN", "3.0")),
                 [3.0, 2.5, 2.0]),
    # [2026-07-21 IMB-20, review-sanctioned] the WINNER lens finally gets a
    # diet lever: divergence is the only lens positive at every horizon
    # (ehit4h Wilson lo 0.509) and had NO emission knob — the one expand
    # asymmetry the audit flagged. Widening = LOWER gap = more advisory
    # tickets for the brain to grade; the taker's bars still gate fills.
    "divergence": ("scout.div_gap_pp",
                   float(os.environ.get("SCOUT_DIV_GAP", "37.5")),
                   [37.5, 30.0, 25.0, 20.0]),
}
TOP_N_LADDER = ("scout.ticket_top_n",
                int(os.environ.get("SCOUT_TICKET_TOP_N", "6")), [6, 9, 12, 15])
# Exit-ladder sweep grid = the 21-Jul agenda item-2 grid, verbatim
SWEEP_TP = [0.03, 0.04, 0.05, 0.06]
SWEEP_SL = [-0.02, -0.03, -0.04]
SWEEP_HOLD = [24.0, 48.0, 72.0]

# [2026-07-21 ORGAN PROPOSALS] levers this tuner will consider when another
# organ proposes them (fleet_proposals), with each attr's TIGHTER direction —
# the tuner re-derives the true direction itself; a declared intent that
# disagrees is disqualifying (an organ cannot smuggle a widening through a
# restrict-shaped gate). tp/sl stay sweep-owned: their direction semantics
# are not monotone, so proposals on them are ignored in v1.
PROPOSAL_TAKER = {
    "taker.dip_range":  ("DIP_RANGE",  "down"),   # lower  = tighter
    "taker.brk_range":  ("BRK_RANGE",  "up"),     # higher = tighter
    "taker.momo_chg":   ("MOMO_CHG",   "up"),
    "taker.div_gap_pp": ("DIV_GAP_PP", "up"),
    "taker.max_hold_h": ("MAX_HOLD_H", "down"),   # shorter = tighter
}
_ATTR_LENS = {attr: lens for lens, (attr, _lv, _lad) in TAKER_LADDERS.items()}
MAX_PROPOSALS_CYCLE = int(os.environ.get("TUNER_MAX_PROPOSALS", "3"))

# env defaults captured at import — the stateless walk always starts here
DEFAULTS = {attr: getattr(tt, attr)
            for attr, _lever, _lad in TAKER_LADDERS.values()}
DEFAULTS.update({"TAKE_PROFIT": tt.TAKE_PROFIT, "STOP_LOSS": tt.STOP_LOSS,
                 "MAX_HOLD_H": tt.MAX_HOLD_H})


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def replay_with(tape, bars):
    """Replay the tape with tt module bars temporarily patched. Pure w.r.t.
    module state: always restores, even on error."""
    saved = {k: getattr(tt, k) for k in bars}
    try:
        for k, v in bars.items():
            setattr(tt, k, v)
        return rp.replay(tape)
    finally:
        for k, v in saved.items():
            setattr(tt, k, v)


def halves(tape):
    mid = len(tape) // 2
    return tape[:mid], tape[mid:]


def _marked(rep):
    """closed_net + end-of-tape unrealized (survivors marked at the last
    snapshot's prices). [2026-07-17 IMB-10] Every tuner gate now scores THIS:
    closed_net alone was blind to deferral — a variant could 'win' a gate by
    pushing losses past the tape's end, because open positions were valued
    at entry and invisible to the very evidence bar the tuner accepts on."""
    return rep["closed_net"] + float(rep.get("unrealized") or 0.0)


def _tape_span_h(tape):
    """Tape span in hours; 0.0 when unparseable (callers then apply no
    span-based exclusion — the old behavior, never a degenerate sweep)."""
    try:
        t0 = datetime.fromisoformat(str(tape[0][0]).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(tape[-1][0]).replace("Z", "+00:00"))
        return max(0.0, (t1 - t0).total_seconds() / 3600.0)
    except Exception:  # noqa: BLE001
        return 0.0


def not_worse(tape_a, tape_b, bars_base, bars_var, tol=TOL):
    """Variant is acceptable if its MARKED net (closed + unrealized) is
    within tol of (or above) the base bars' on BOTH halves — the doctrine's
    both-halves rule, deferral-proof (see _marked)."""
    for half in (tape_a, tape_b):
        if not half:
            return False
        base = _marked(replay_with(half, bars_base))
        var = _marked(replay_with(half, bars_var))
        if var < base - tol:
            return False
    return True


def next_notches(ladder, current):
    """Ladder values strictly beyond `current`, in widening order. The
    ladder is written default-first, widening outward, so 'beyond' is just
    positional (works for both up-ladders and down-ladders)."""
    try:
        i = ladder.index(current)
        return ladder[i + 1:]
    except ValueError:
        # current between notches (operator env override): resume after the
        # nearest notch not wider than current
        out = []
        passed = False
        for v in ladder[1:]:
            if passed:
                out.append(v)
            elif (ladder[0] < ladder[-1] and v > current) or \
                 (ladder[0] > ladder[-1] and v < current):
                out.append(v)
                passed = True
        return out


def vetoed_lenses(lens_fwd):
    """The taker's own veto rule — the tuner never widens what the brain has
    ruled negative at the floor. [2026-07-17] Delegates to the taker, which
    now owns the single definition: this was a hand-copy of the taker's inline
    rule, and a third copy was about to land in the incubator. Same behaviour
    (LENS_FLOOR is the same TT_LENS_VETO_MIN_N env the taker reads)."""
    return tt.vetoed_lenses(lens_fwd, min_n=LENS_FLOOR)


def desired_taker_bars(tape, baseline, lens_fwd, helping=None, lens_fresh=True):
    """Walk each lens's conviction-bar ladder from the DEFAULT. Three rules:

    STARVING (seen tickets, zero fills, under the brain's ruling floor):
      widen one not-worse-on-both-halves notch at a time until the lens
      produces replay fills — samples are the goal, P&L must merely not
      degrade.
    WINNER (brain-graded POSITIVE at the ruling floor — the taker-veto rule
      inverted): expand the bar while each notch IMPROVES the replayed net
      on both halves by MARGIN_HALF — this is how the cream gets captured
      at size instead of waiting for an operator to notice.
    PROPRIO-HELPING (16-Jul, the expand side of proprioception): a lever
      whose graded real-world episodes measured net-POSITIVE (n>=2, >=+$3
      counterfactual — an evidence bar independent of the brain's) unlocks
      the same expansion walk BEFORE the lens reaches the brain's ruling
      floor. Every notch still needs the improve-both-halves margin, and
      the brain's veto stays senior — helping never overrides a veto.

    [2026-07-21 IMB-18 RESOLVED (was contested 2/3)] lens_fresh=False means
    the brain is DARK (stale/absent lens-forward), which is a DIFFERENT state
    from "fresh brain with no grades yet" (lens_fwd={}): dark makes the veto
    set UNKNOWABLE, so "the brain's veto stays senior / never widen a vetoed
    lens" cannot be honored — and before this fix the starving walk kept
    widening anyway (the veto simply failed open). A dark brain now earns
    nothing on the LENS-KEYED walks, the same contract proprioception already
    states; the lens-AGNOSTIC exit sweep is unaffected (it never consults the
    brain), and the scout-diet walk was already guarded at the call site.

    Returns ({tt attr: value} that differ from default, log list)."""
    if not lens_fresh:
        return {}, ["brain dark (lens-forward stale/absent) — lens-keyed bar "
                    "walks suppressed (IMB-18): the veto set is unknowable, so "
                    "a dark brain earns nothing; exit sweep unaffected"]
    h1, h2 = halves(tape)
    if not h1 or not h2:
        return {}, ["tape too short to halve — no taker-bar changes"]
    helping = set(helping or ())
    veto = vetoed_lenses(lens_fwd)
    bars = dict(DEFAULTS)
    log = []
    for lens, (attr, lever, ladder) in TAKER_LADDERS.items():
        if lens in veto:
            log.append(f"{lens}: brain-vetoed at floor — never widened")
            continue
        lens_rep = (baseline.get("lenses") or {}).get(lens) or {}
        g = (lens_fwd or {}).get(lens) or {}
        # [2026-07-21 IMB-24] episode basis when the brain publishes v3
        # fields, raw fallback otherwise — same authority as the veto.
        graded, floor_met, avg, hit = tt.lens_evidence(g, min_n=LENS_FLOOR)
        positive = floor_met and avg > 0 and hit >= 0.5
        earned = positive or lever in helping
        starving = (lens_rep.get("seen", 0) > 0
                    and lens_rep.get("taken", 0) == 0
                    and not floor_met)
        if not (starving or earned):
            continue
        mode = ("winner" if positive else
                "proprio-helping" if lever in helping else "starving")
        for notch in next_notches(ladder, DEFAULTS[attr]):
            cand = dict(bars, **{attr: notch})
            if earned:
                ok = all(_marked(replay_with(h, cand))
                         >= _marked(replay_with(h, bars)) + MARGIN_HALF
                         for h in (h1, h2))
                if not ok:
                    log.append(f"{lens}: notch {notch} REJECTED "
                               f"(no improvement on a half)")
                    break
                bars[attr] = notch
                taken = (replay_with(tape, cand).get("lenses") or {}) \
                    .get(lens, {}).get("taken", 0)
                log.append(f"{lens} ({mode}): widened {attr} -> {notch} "
                           f"(replay taken={taken}, improves both halves)")
                continue
            # [2026-07-16 AUDIT FIX] starving path: a notch that produces ZERO
            # replay fills used to pass not_worse trivially (0.0 vs 0.0) and
            # the walk enacted the ladder MAX on no evidence at all. A notch
            # is only enacted when the replay actually FILLS at it (evidence)
            # AND not-worse holds; unevidenced notches are probed but never
            # enacted, and an unreachable lens correctly gets NO widen. (The
            # earned walk above needs no gate — a zero-fill notch can never
            # clear its improve-by-margin bar.)
            taken = (replay_with(tape, cand).get("lenses") or {}) \
                .get(lens, {}).get("taken", 0)
            if taken == 0:
                log.append(f"{lens}: notch {notch} not enacted "
                           f"(0 replay fills — no evidence)")
                continue                 # probe wider; enact only on evidence
            if not not_worse(h1, h2, bars, cand):
                log.append(f"{lens}: notch {notch} REJECTED (worse on a half)")
                break
            bars[attr] = notch
            log.append(f"{lens} (starving): widened {attr} -> {notch} "
                       f"(replay taken={taken}, not-worse both halves)")
            break                        # first EVIDENCED notch that holds
    return {k: v for k, v in bars.items() if v != DEFAULTS[k]}, log


def sweep_exits(tape, baseline):
    """The agenda's TP/SL/hold grid. Returns ({attr: value}, log). Enacts
    only past anti-overfit floors: enough baseline trades, wins on BOTH
    halves, and a real total margin."""
    log = []
    closed = sum((s.get("closed") or 0) for s in (baseline.get("lenses") or {}).values())
    if closed < MIN_TRADES_SWEEP:
        log.append(f"sweep skipped: baseline closed {closed} < {MIN_TRADES_SWEEP}")
        return {}, log
    base_bars = {"TAKE_PROFIT": DEFAULTS["TAKE_PROFIT"],
                 "STOP_LOSS": DEFAULTS["STOP_LOSS"],
                 "MAX_HOLD_H": DEFAULTS["MAX_HOLD_H"]}
    base_net = _marked(baseline)
    best, best_net = None, base_net
    # [2026-07-17 IMB-10] a hold the tape can never reach is pure deferral —
    # nothing max-hold-exits inside the window, so its 'edge' is unpriced
    # open risk. Excluded from the grid (span 0 = unparseable -> no cap).
    span_h = _tape_span_h(tape)
    _skipped_holds = sorted(h for h in SWEEP_HOLD if span_h > 0 and h >= span_h)
    if _skipped_holds:
        log.append(f"sweep: holds {_skipped_holds} excluded "
                   f"(tape spans {span_h:.0f}h — unreachable = deferral)")
    for tp in SWEEP_TP:
        for sl in SWEEP_SL:
            for hold in SWEEP_HOLD:
                if hold in _skipped_holds:
                    continue
                cand = {"TAKE_PROFIT": tp, "STOP_LOSS": sl, "MAX_HOLD_H": hold}
                if cand == base_bars:
                    continue
                net = _marked(replay_with(tape, cand))
                if net > best_net:
                    best, best_net = cand, net
    if not best or best_net - base_net < MARGIN_TOTAL:
        log.append(f"sweep: no variant beats baseline by ${MARGIN_TOTAL:.2f} "
                   f"(best +${(best_net - base_net):.2f})")
        return {}, log
    h1, h2 = halves(tape)
    for half in (h1, h2):
        if not half:
            return {}, log + ["sweep: empty half — refused"]
        b = _marked(replay_with(half, base_bars))
        v = _marked(replay_with(half, best))
        if v < b + MARGIN_HALF:
            log.append(f"sweep: winner fails a half (+${v - b:.2f} < "
                       f"${MARGIN_HALF:.2f}) — refused (both-halves rule)")
            return {}, log
    log.append(f"sweep: {best} beats baseline +${best_net - base_net:.2f} "
               f"on the tape AND both halves — enacting")
    return {k: v for k, v in best.items() if v != DEFAULTS[k]}, log


def desired_scout_levers(lens_fwd, helping=None):
    """Scout emission widening: advisory tickets only — this widens the
    BRAIN'S GRADING DIET, never what trades (the taker's bars gate fills).
    A lens under the brain's ruling floor gets its emission bar held one
    notch beyond default until the floor is reached, then released (the
    lever expires back to default on its own). The live 15-Jul case this
    exists for: dip graded n4h=25 (hit 92%!) while every other lens sat at
    ~250 — the best lens was the one starving for grades.
    [16-Jul expand side] A diet lever proprioception graded HELPING (its
    past episodes measurably delivered grades) walks ONE NOTCH DEEPER while
    the lens stays under the floor — the diet that proved it feeds the
    brain gets a bigger portion; still advisory-only, still released at the
    floor. Returns ({lever: value}, log)."""
    out, log = {}, []
    helping = set(helping or ())
    veto = vetoed_lenses(lens_fwd)
    for lens, (lever, default, ladder) in SCOUT_LADDERS.items():
        if lens in veto:
            continue
        # [2026-07-21 IMB-24] episode-basis floor (raw fallback) — the diet
        # widens until the lens has enough INDEPENDENT episodes, not raw ticks
        graded, floor_met, _avg, _hit = tt.lens_evidence(
            (lens_fwd or {}).get(lens), min_n=LENS_FLOOR)
        if not floor_met:
            # only notches strictly WIDER than the (env) default — never
            # tighten a scout the operator already widened
            beyond = next_notches(ladder, default)
            if not beyond:
                continue          # env already at/past the ladder ceiling
            deeper = lever in helping and len(beyond) > 1
            val = beyond[1] if deeper else beyond[0]
            out[lever] = val
            log.append(f"{lens}: graded n={graded} under floor — scout "
                       f"emission {lever} -> {val} (grading diet, not trading"
                       + (", deeper: proprio-helping" if deeper else "") + ")")
        # else: floor reached — stop asserting, lever expires to default
    lever, default, ladder = TOP_N_LADDER
    hungry = any(not tt.lens_evidence((lens_fwd or {}).get(l),
                                      min_n=LENS_FLOOR)[1]
                 for l in SCOUT_LADDERS)
    if hungry and lens_fwd:
        beyond = next_notches(ladder, default)
        if beyond:
            deeper = lever in helping and len(beyond) > 1
            val = beyond[1] if deeper else beyond[0]
            out[lever] = val
            log.append(f"ticket_top_n -> {val} (a lens is below the ruling floor"
                       + (", deeper: proprio-helping" if deeper else "") + ")")
    return out, log


def consume_proposals(proposals, tape, bars, lens_fwd, lens_fresh):
    """[2026-07-21 operator mandate: "the organs need more ability to
    implement changes to forward onto the tuners to act on"] Gate ORGAN
    PROPOSALS (fleet_proposals) through this tuner's OWN evidence bars and
    merge the survivors into this cycle's taker bars. The organ supplies the
    trigger; the tape decides:

      RESTRICT (tighter than the cycle's current value): enacted iff the
        replay is NOT WORSE on both halves — a protective tightening that
        would have cost real P&L on the tape needs stronger evidence than a
        proposal carries. No brain needed (restricting is always allowed,
        dark brain included).
      EXPAND (wider): the full winner bar — fresh brain, lens not vetoed,
        and the notch must IMPROVE the replayed net on both halves by
        MARGIN_HALF. max_hold has no lens, so it accepts restrict only.

    A proposal whose DECLARED direction disagrees with the re-derived one is
    disqualified, not reinterpreted. At most MAX_PROPOSALS_CYCLE enactments
    per cycle; later proposals gate against the already-accepted set. Pure
    w.r.t. inputs (bars copied); selftested offline.
    Returns (bars, {attr: proposing organ}, log)."""
    log = []
    prov = {}
    if not proposals:
        return bars, prov, log
    h1, h2 = halves(tape)
    if not h1 or not h2:
        return bars, prov, ["proposals skipped: tape too short to halve"]
    bars = dict(bars)
    current = dict(DEFAULTS, **bars)
    enacted = 0
    flat = sorted((p for plist in proposals.values() for p in plist),
                  key=lambda p: (0 if p["direction"] == "restrict" else 1,
                                 p["set_by"], p["lever"]))
    for p in flat:
        if enacted >= MAX_PROPOSALS_CYCLE:
            log.append(f"proposal({p['set_by']}): {p['lever']} skipped — "
                       f"per-cycle cap {MAX_PROPOSALS_CYCLE} reached")
            continue
        attr, tighter = PROPOSAL_TAKER.get(p["lever"], (None, None))
        if attr is None:
            continue
        cur = current[attr]
        v = p["value"]
        if v == cur:
            continue
        true_dir = ("restrict"
                    if (tighter == "up" and v > cur) or
                       (tighter == "down" and v < cur)
                    else "expand")
        if true_dir != p["direction"]:
            log.append(f"proposal({p['set_by']}): {p['lever']}={v} DISQUALIFIED"
                       f" — declared {p['direction']}, derived {true_dir}")
            continue
        cand = dict(current, **{attr: v})
        if true_dir == "restrict":
            if not not_worse(h1, h2, current, cand):
                log.append(f"proposal({p['set_by']}): restrict {p['lever']}"
                           f"={v} REJECTED (worse on a half)")
                continue
        else:
            lens = _ATTR_LENS.get(attr)
            if lens is None:
                log.append(f"proposal({p['set_by']}): expand {p['lever']}"
                           f"={v} refused (no lens — restrict-only attr)")
                continue
            if not lens_fresh:
                log.append(f"proposal({p['set_by']}): expand {p['lever']}"
                           f"={v} refused (brain dark — earns nothing)")
                continue
            if lens in vetoed_lenses(lens_fwd):
                log.append(f"proposal({p['set_by']}): expand {p['lever']}"
                           f"={v} refused (lens brain-vetoed)")
                continue
            ok = all(_marked(replay_with(h, cand))
                     >= _marked(replay_with(h, current)) + MARGIN_HALF
                     for h in (h1, h2))
            if not ok:
                log.append(f"proposal({p['set_by']}): expand {p['lever']}"
                           f"={v} REJECTED (no improvement on a half)")
                continue
        current[attr] = v
        bars[attr] = v
        prov[attr] = p["set_by"]
        enacted += 1
        log.append(f"proposal({p['set_by']}): {true_dir} {p['lever']} -> {v} "
                   f"ENACTED ({p['reason'][:80] or 'no reason given'})")
    return ({k: v for k, v in bars.items() if v != DEFAULTS[k]}, prov, log)


def apply_proprioception(levers, prop_state, now_ts):
    """[2026-07-16 PROPRIOCEPTION] Drop any would-be enactment whose lever
    carries a fresh HURTING verdict from fleet_proprioception — the lever's
    graded real-world episodes measured net-negative, so the tuner stops
    repeating the movement even while in-sample replay still likes it.
    Restrict-only (only ever removes enactments) and fail-safe: a dark/
    stale/absent proprioception drops nothing. Pure — selftested."""
    if proprio is None or not levers:
        return levers, []
    hurt = proprio.hurting_levers(prop_state, now_ts)
    dropped = sorted(set(levers) & set(hurt))
    if not dropped:
        return levers, []
    log = [f"{k}: proprioception verdict HURTING "
           f"(Σ${(hurt[k].get('sum_delta_usd') or 0):+.2f} over "
           f"n={hurt[k].get('n')} graded episodes) — NOT re-asserted"
           for k in dropped]
    return {k: v for k, v in levers.items() if k not in hurt}, log


NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send_push(title, body):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", "default")
        req.add_header("Tags", "brain")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[scout-tuner] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def run_once():
    tape, used = rp.load_tape(source="auto")
    if len(tape) < MIN_SNAPS:
        print(f"[scout-tuner] {now_iso()} tape too short "
              f"({len(tape)}/{MIN_SNAPS} snapshots, {used}) — skipping")
        return None
    lf_state = store.load_state("brain-lens-forward") or {}
    lf_fresh = False
    try:
        u = datetime.fromisoformat(str(lf_state.get("updated")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        lf_fresh = ((datetime.now(timezone.utc) - u).total_seconds()
                    <= float(lf_state.get("ttl_sec") or 0))
    except Exception:
        lf_fresh = False
    # fail-safe NEUTRAL on a dark brain: taker-bar walks still run (the
    # replay is their evidence) but grading-floor logic contributes nothing.
    lens_fwd = (lf_state.get("lenses") or {}) if lf_fresh else {}

    # proprioception (16-Jul): HELPING levers earn the expansion walk /
    # deeper diet; HURTING levers are dropped before the write. Both sides
    # fail-safe — a dark organ earns nothing and restricts nothing.
    prop_state = (store.load_state(proprio.KEY) or {}) if proprio else {}
    prop_now = datetime.now(timezone.utc).timestamp()
    helping = set(proprio.helping_levers(prop_state, prop_now)) if proprio else set()

    baseline = replay_with(tape, DEFAULTS)
    bars, log1 = desired_taker_bars(tape, baseline, lens_fwd, helping=helping,
                                    lens_fresh=lf_fresh)
    exits, log2 = sweep_exits(tape, baseline)
    # [2026-07-16 AUDIT FIX] bars were validated against DEFAULT exits and
    # exits against DEFAULT bars — the deployed COMBINATION was never on the
    # tape. When both move in one cycle, the joint set must itself be
    # not-worse on both halves; if the interaction fails, the exits are
    # dropped this cycle (each side alone is a replay-tested combination —
    # the untested thing was only the pairing).
    if bars and exits:
        joint = dict(bars, **exits)
        h1j, h2j = halves(tape)
        if h1j and h2j and not_worse(h1j, h2j, DEFAULTS, dict(DEFAULTS, **joint)):
            bars = joint
            log2.append("joint bars+exits replay: not-worse both halves — "
                        "enacting together")
        else:
            log2.append("joint bars+exits replay FAILED a half — exits "
                        "dropped this cycle (interaction unproven)")
    else:
        bars.update(exits)
    if lf_fresh:
        scout_levers, log3 = desired_scout_levers(lens_fwd, helping=helping)
    else:
        scout_levers, log3 = {}, ["lens-forward missing/stale — no scout-diet "
                                  "changes (fail-safe neutral)"]

    # [2026-07-21 ORGAN PROPOSALS] other organs' proposed bar changes, gated
    # by THIS tuner's replay evidence (restrict: not-worse; expand: winner
    # bar). Fail-safe: dark channel proposes nothing.
    prov, log5 = {}, []
    if fprop is not None:
        props = fprop.proposals_for(set(PROPOSAL_TAKER))
        bars, prov, log5 = consume_proposals(props, tape, bars, lens_fwd,
                                             lens_fresh=lf_fresh)

    attr_to_lever = {attr: lever for _l, (attr, lever, _lad) in TAKER_LADDERS.items()}
    attr_to_lever.update({"TAKE_PROFIT": "taker.tp", "STOP_LOSS": "taker.sl",
                          "MAX_HOLD_H": "taker.max_hold_h"})
    levers = {attr_to_lever[a]: {
        "value": v,
        "reason": (f"organ-proposal:{prov[a]} (replay-gated at this tuner)"
                   if a in prov else
                   "replay-gated widen/optimize (both-halves on the tape)"),
        "evidence": f"tape {baseline['span']} ({baseline['snapshots']} snaps); "
                    f"baseline net ${baseline['closed_net']}"}
        for a, v in bars.items()}
    for lever, v in scout_levers.items():
        levers[lever] = {"value": v,
                         "reason": "lens starving — widen the brain's grading diet",
                         "evidence": f"lens-forward n4h below {LENS_FLOOR}"}

    # proprioception veto: a lever whose graded episodes measured HURTING in
    # reality is not re-asserted this cycle (restrict-only; fail-safe none)
    levers, log4 = apply_proprioception(levers, prop_state, prop_now)

    enacted = tuning.write_levers(levers, set_by="scout-tuner",
                                  ttl_sec=LEVER_TTL) if levers else None

    prev = store.load_state(KEY) or {}
    prev_set = prev.get("enacted") or {}
    now_set = {k: v["value"] for k, v in (enacted or {}).get("levers", {}).items()
               if v.get("set_by") == "scout-tuner"} if enacted else {}
    payload = {
        "updated": now_iso(), "ttl_sec": TTL_SEC,
        "tape": {"snapshots": baseline["snapshots"], "span": baseline["span"],
                 "source": used},
        "baseline_net": baseline["closed_net"],
        "baseline_lenses": {l: {k: s.get(k) for k in ("seen", "taken", "closed", "net")}
                            for l, s in (baseline.get("lenses") or {}).items()},
        "enacted": now_set, "log": (log4 + log5 + log1 + log2 + log3)[:20],
    }
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "enacted": now_set,
                                     "baseline_net": baseline["closed_net"]})
        except Exception:
            pass
    for line in payload["log"]:
        print(f"[scout-tuner] {line}")
    if now_set != prev_set:
        delta = {k: v for k, v in now_set.items() if prev_set.get(k) != v}
        released = sorted(set(prev_set) - set(now_set))
        body = (f"enacted: {json.dumps(delta)}" if delta else "") + \
               (f" released: {released}" if released else "")
        send_push("scout tuner: Lighter loop self-tuned", body or "levers refreshed")
        print(f"[scout-tuner] {now_iso()} CHANGE — {body}", flush=True)
    print(f"[scout-tuner] {now_iso()} tape={baseline['snapshots']} "
          f"baseline ${baseline['closed_net']:+.2f} levers={sorted(now_set) or '—'}",
          flush=True)
    return payload


# ---------------------------------------------------------------------------

def _selftest():
    from datetime import timedelta

    def dt(h, mi=0):
        return datetime(2026, 7, 14, h, mi, tzinfo=timezone.utc)

    def snap(h, marks, tickets=None, mi=0):
        return (dt(h, mi), {"marks": marks, "tickets": tickets or {}})

    # [2026-07-17 IMB-10] the deferral-proof score + span helpers (a
    # regression back to closed_net-only scoring must not pass silently)
    assert _marked({"closed_net": 5.0, "unrealized": -3.5}) == 1.5
    assert _marked({"closed_net": 5.0}) == 5.0            # missing -> 0
    assert _marked({"closed_net": -2.0, "unrealized": None}) == -2.0
    _sp = [(dt(0).isoformat(), {}), (dt(30 % 24).isoformat(), {})]
    assert _tape_span_h([(dt(0).isoformat(), {}),
                         ((dt(0) + timedelta(hours=30)).isoformat(), {})]) == 30.0
    assert _tape_span_h([]) == 0.0 and _tape_span_h([("junk", {})]) == 0.0
    # ...so a 72h hold is excluded on a 30h tape, 24h is not (sweep grid)
    assert [h for h in SWEEP_HOLD
            if 30.0 > 0 and h >= 30.0] == [48.0, 72.0]

    # ladders: next_notches walks outward from any starting point
    assert next_notches([0.05, 0.08, 0.11, 0.15], 0.05) == [0.08, 0.11, 0.15]
    assert next_notches([0.95, 0.93, 0.91, 0.90], 0.93) == [0.91, 0.90]
    assert next_notches([3.0, 2.5, 2.0], 2.0) == []
    assert next_notches([0.05, 0.08, 0.11, 0.15], 0.07) == [0.08, 0.11, 0.15]

    # veto rule mirrors the taker's
    lf = {"dip": {"n4h": 80, "avg4h_pct": -1.0, "hit4h": 0.3},
          "momentum": {"n4h": 80, "avg4h_pct": +1.0, "hit4h": 0.6},
          "breakout": {"n4h": 5}}
    assert vetoed_lenses(lf) == {"dip"}

    # A tape where dip tickets sit at range_pos 0.07: the default 0.05 bar
    # starves the lens; one notch (0.08) fills it. Make the dip trades WIN
    # (price rises to TP) so the widen is not-worse on both halves.
    dipt = {"sym": "DDD", "range_pos": 0.07}
    dipt2 = {"sym": "EEE", "range_pos": 0.07}
    win_tape = [
        snap(0, {"DDD": 100.0}, {"dip": [dipt]}),
        snap(1, {"DDD": 105.0}),                      # TP if held
        snap(2, {"EEE": 100.0}, {"dip": [dipt2]}),
        snap(3, {"EEE": 105.0}),
        snap(4, {}),
    ]
    base = replay_with(win_tape, DEFAULTS)
    assert base["lenses"]["dip"]["seen"] == 2 and base["lenses"]["dip"]["taken"] == 0
    bars, log = desired_taker_bars(win_tape, base, {})
    assert bars.get("DIP_RANGE") == 0.08, (bars, log)

    # [2026-07-16 AUDIT] tickets UNREACHABLE at every notch (range_pos 0.30
    # > ladder max 0.15): every notch fills nothing, not_worse passes 0-vs-0
    # trivially — the walk used to enact ladder MAX on zero evidence. Now an
    # unevidenced notch is never enacted: NO widen at all.
    fart = {"sym": "FFF", "range_pos": 0.30}
    far_tape = [
        snap(0, {"FFF": 100.0}, {"dip": [fart]}),
        snap(1, {"FFF": 105.0}),
        snap(4, {}),
    ]
    base_far = replay_with(far_tape, DEFAULTS)
    assert base_far["lenses"]["dip"]["seen"] == 1 and \
        base_far["lenses"]["dip"]["taken"] == 0
    bars_far, log_far = desired_taker_bars(far_tape, base_far, {})
    assert "DIP_RANGE" not in bars_far, (bars_far, log_far)
    assert any("no evidence" in l for l in log_far), log_far

    # Same setup but the dip trades LOSE hard (price dumps to SL) on both
    # halves: the widen must be REJECTED by the not-worse rule.
    lose_tape = [
        snap(0, {"DDD": 100.0}, {"dip": [dipt]}),
        snap(1, {"DDD": 90.0}),                       # SL
        snap(2, {"EEE": 100.0}, {"dip": [dipt2]}),
        snap(3, {"EEE": 90.0}),
        snap(4, {}),
    ]
    base_l = replay_with(lose_tape, DEFAULTS)
    bars_l, log_l = desired_taker_bars(lose_tape, base_l, {})
    assert "DIP_RANGE" not in bars_l, (bars_l, log_l)

    # brain veto blocks widening even when starving
    lf_veto = {"dip": {"n4h": 80, "avg4h_pct": -1.0, "hit4h": 0.3}}
    bars_v, _ = desired_taker_bars(win_tape, base, lf_veto)
    assert "DIP_RANGE" not in bars_v

    # WINNER expansion: a lens graded POSITIVE at the ruling floor gets its
    # bar widened while each notch IMPROVES the replayed net on both halves
    lf_winner = {"dip": {"n4h": 100, "avg4h_pct": +0.5, "hit4h": 0.6}}
    # [2026-07-21 IMB-18] a DARK brain suppresses every lens-keyed walk —
    # even on a tape where the starving walk would otherwise widen
    bars_dark, log_dark = desired_taker_bars(win_tape, base, {}, lens_fresh=False)
    assert bars_dark == {} and "brain dark" in log_dark[0], (bars_dark, log_dark)

    bars_w, log_w = desired_taker_bars(win_tape, base, lf_winner)
    assert bars_w.get("DIP_RANGE") == 0.08, (bars_w, log_w)
    # ...but a positive grade never expands into replay LOSSES
    bars_wl, _ = desired_taker_bars(lose_tape, base_l, lf_winner)
    assert "DIP_RANGE" not in bars_wl

    # PROPRIO-HELPING unlock (16-Jul expand side): dip FILLS at the default
    # bar (not starving) and the brain sits below its ruling floor (not a
    # winner) — only a HELPING verdict unlocks the expansion walk, and each
    # notch still needs the improve-both-halves margin. Tickets at 0.04 fill
    # at the default bar; tickets at 0.07 fill only at 0.08; every trade
    # WINS, so the wider bar improves both halves.
    in_a = {"sym": "AAA", "range_pos": 0.04}
    out_b = {"sym": "BBB", "range_pos": 0.07}
    in_c = {"sym": "CCC", "range_pos": 0.04}
    out_d = {"sym": "DDD", "range_pos": 0.07}
    help_tape = [
        snap(0, {"AAA": 100.0, "BBB": 100.0}, {"dip": [in_a, out_b]}),
        snap(1, {"AAA": 105.0, "BBB": 100.0}, {"dip": [out_b]}),
        snap(2, {"BBB": 105.0}),
        snap(3, {}),
        snap(4, {"CCC": 100.0, "DDD": 100.0}, {"dip": [in_c, out_d]}),
        snap(5, {"CCC": 105.0, "DDD": 100.0}, {"dip": [out_d]}),
        snap(6, {"DDD": 105.0}),
        snap(7, {}),
    ]
    base_h = replay_with(help_tape, DEFAULTS)
    assert base_h["lenses"]["dip"]["taken"] == 2, base_h["lenses"]["dip"]
    bars_h0, _ = desired_taker_bars(help_tape, base_h, {})
    assert "DIP_RANGE" not in bars_h0, bars_h0        # no evidence -> no walk
    bars_h1, log_h1 = desired_taker_bars(help_tape, base_h, {},
                                         helping={"taker.dip_range"})
    assert bars_h1.get("DIP_RANGE") == 0.08, (bars_h1, log_h1)
    assert any("proprio-helping" in l for l in log_h1), log_h1
    # ...but a losing tape refuses the helping walk (margin rule holds)...
    bars_h2, _ = desired_taker_bars(lose_tape, base_l, {},
                                    helping={"taker.dip_range"})
    assert "DIP_RANGE" not in bars_h2, bars_h2
    # ...and the brain's veto stays senior to a helping verdict
    bars_h3, _ = desired_taker_bars(help_tape, base_h, lf_veto,
                                    helping={"taker.dip_range"})
    assert "DIP_RANGE" not in bars_h3, bars_h3

    # sweep refuses tiny samples (anti-overfit floor)
    exits, slog = sweep_exits(win_tape, base)
    assert exits == {} and "skipped" in slog[0], slog

    # scout levers: a lens under the ruling floor gets its emission bar one
    # notch beyond default (grading diet); at the floor it is released.
    # [2026-07-21] divergence joined SCOUT_LADDERS (IMB-20), so every fixture
    # feeds it too — _fed keeps the pre-existing cases meaning what they meant.
    _fed = {"n4h": 252}
    sl, slog2 = desired_scout_levers({"dip": {"n4h": 25, "avg4h_pct": 1.1,
                                              "hit4h": 0.92},
                                      "breakout": {"n4h": 240},
                                      "momentum": {"n4h": 252},
                                      "divergence": dict(_fed)})
    assert sl.get("scout.dip_range_max") == 0.15, (sl, slog2)
    assert "scout.brk_range_min" not in sl, sl
    assert sl.get("scout.ticket_top_n") == 9, sl
    sl2, _ = desired_scout_levers({"dip": {"n4h": 100, "avg4h_pct": 1.0,
                                           "hit4h": 0.6},
                                   "breakout": {"n4h": 100},
                                   "momentum": {"n4h": 100},
                                   "divergence": dict(_fed)})
    assert sl2 == {}, sl2
    # a vetoed lens gets NO extra diet either
    sl3, _ = desired_scout_levers({"dip": {"n4h": 80, "avg4h_pct": -1.0,
                                           "hit4h": 0.3},
                                   "breakout": {"n4h": 100},
                                   "momentum": {"n4h": 100},
                                   "divergence": dict(_fed)})
    assert "scout.dip_range_max" not in sl3, sl3
    # HELPING diet levers walk one notch DEEPER while under the floor
    # (0.15 -> 0.20, top_n 9 -> 12); un-helped levers keep the first notch
    sl4, _ = desired_scout_levers({"dip": {"n4h": 25, "avg4h_pct": 1.1,
                                           "hit4h": 0.92},
                                   "breakout": {"n4h": 20},
                                   "momentum": {"n4h": 252},
                                   "divergence": dict(_fed)},
                                  helping={"scout.dip_range_max",
                                           "scout.ticket_top_n"})
    assert sl4.get("scout.dip_range_max") == 0.20, sl4
    assert sl4.get("scout.brk_range_min") == 0.87, sl4   # not helped: notch 1
    assert sl4.get("scout.ticket_top_n") == 12, sl4
    # [2026-07-21 IMB-20] a STARVING divergence lens finally has a diet lever
    # to widen (37.5 -> 30.0)…
    sl5, _ = desired_scout_levers({"dip": {"n4h": 100, "avg4h_pct": 1.0,
                                           "hit4h": 0.6},
                                   "breakout": {"n4h": 100},
                                   "momentum": {"n4h": 100},
                                   "divergence": {"n4h": 10}})
    assert sl5.get("scout.div_gap_pp") == 30.0, sl5
    # [2026-07-21 IMB-24] …and the floor is EPISODE-based when v3 fields are
    # present: raw n4h thousands with too few independent episodes still
    # counts as starving (the serial-correlation case, measured 8-31x)
    sl6, _ = desired_scout_levers({"dip": {"n4h": 100, "avg4h_pct": 1.0,
                                           "hit4h": 0.6},
                                   "breakout": {"n4h": 100},
                                   "momentum": {"n4h": 5000, "eps4h": 12,
                                                "n_syms": 4, "eavg4h_pct": 0.1,
                                                "ehit4h": 0.55},
                                   "divergence": dict(_fed)})
    assert sl6.get("scout.momo_chg_min") == 2.5, sl6

    # proprioception veto: a fresh HURTING verdict drops the enactment; a
    # stale/absent payload drops NOTHING (fail-safe); helping never drops
    if proprio is not None:
        nowts = datetime.now(timezone.utc).timestamp()
        want = {"taker.dip_range": {"value": 0.08, "reason": "r"},
                "scout.dip_range_max": {"value": 0.15, "reason": "r"}}
        fresh_prop = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "ttl_sec": 2700,
                      "verdicts": {"taker.dip_range": {"verdict": "hurting",
                                                       "n": 3, "sum_delta_usd": -5.1},
                                   "scout.dip_range_max": {"verdict": "helping"}}}
        kept, plog = apply_proprioception(dict(want), fresh_prop, nowts)
        assert set(kept) == {"scout.dip_range_max"} and len(plog) == 1, (kept, plog)
        stale_prop = dict(fresh_prop, updated="2020-01-01T00:00:00+00:00")
        assert apply_proprioception(dict(want), stale_prop, nowts) == (want, [])
        assert apply_proprioception(dict(want), {}, nowts) == (want, [])
        assert apply_proprioception({}, fresh_prop, nowts) == ({}, [])

    # [2026-07-21 ORGAN PROPOSALS] consume_proposals: the organ proposes,
    # THIS tuner's replay evidence decides.
    def prop(lever, value, direction, who="organ-x"):
        return {lever: [{"lever": lever, "value": value, "direction": direction,
                         "set_by": who, "reason": "test", "evidence": "t"}]}

    # restrict with no matching tickets on tape: replay unchanged -> not-worse
    # trivially -> ENACTED (a free protective tightening)
    b1, pv1, pl1 = consume_proposals(prop("taker.momo_chg", 6.0, "restrict"),
                                     win_tape, {}, {}, lens_fresh=True)
    assert b1.get("MOMO_CHG") == 6.0 and pv1 == {"MOMO_CHG": "organ-x"}, (b1, pl1)
    # ...and a dark brain does NOT block a restrict (restricting is always
    # allowed)
    b1d, _, _ = consume_proposals(prop("taker.momo_chg", 6.0, "restrict"),
                                  win_tape, {}, {}, lens_fresh=False)
    assert b1d.get("MOMO_CHG") == 6.0, b1d
    # restrict that would have EXCLUDED winning trades -> worse on a half ->
    # REJECTED (momo tickets at +5.5% win at the default 5.0 bar)
    m_in = {"sym": "MMM", "chg_pct": 5.5, "vol_m": 9.0}
    m_in2 = {"sym": "NNN", "chg_pct": 5.5, "vol_m": 9.0}
    momo_win = [
        snap(0, {"MMM": 100.0}, {"momentum": [m_in]}),
        snap(1, {"MMM": 105.0}),
        snap(2, {}),
        snap(3, {"NNN": 100.0}, {"momentum": [m_in2]}),
        snap(4, {"NNN": 105.0}),
        snap(5, {}),
    ]
    b2, pv2, pl2 = consume_proposals(prop("taker.momo_chg", 6.0, "restrict"),
                                     momo_win, {}, {}, lens_fresh=True)
    assert "MOMO_CHG" not in b2 and not pv2, (b2, pl2)
    assert any("REJECTED" in l for l in pl2), pl2
    # expand: winner bar — improves both halves (tickets at +4.6% win, only
    # reachable at the proposed 4.5 bar), brain fresh, lens not vetoed
    m_lo = {"sym": "MMM", "chg_pct": 4.6, "vol_m": 9.0}
    m_lo2 = {"sym": "NNN", "chg_pct": 4.6, "vol_m": 9.0}
    momo_exp = [
        snap(0, {"MMM": 100.0}, {"momentum": [m_lo]}),
        snap(1, {"MMM": 105.0}),
        snap(2, {}),
        snap(3, {"NNN": 100.0}, {"momentum": [m_lo2]}),
        snap(4, {"NNN": 105.0}),
        snap(5, {}),
    ]
    b3, pv3, pl3 = consume_proposals(prop("taker.momo_chg", 4.5, "expand"),
                                     momo_exp, {}, {}, lens_fresh=True)
    assert b3.get("MOMO_CHG") == 4.5, (b3, pl3)
    # ...refused on a dark brain (expand earns nothing dark)
    b3d, _, pl3d = consume_proposals(prop("taker.momo_chg", 4.5, "expand"),
                                     momo_exp, {}, {}, lens_fresh=False)
    assert "MOMO_CHG" not in b3d and any("brain dark" in l for l in pl3d), pl3d
    # ...refused when the lens is brain-vetoed (veto stays senior)
    lf_mveto = {"momentum": {"n4h": 80, "avg4h_pct": -1.0, "hit4h": 0.3}}
    b3v, _, pl3v = consume_proposals(prop("taker.momo_chg", 4.5, "expand"),
                                     momo_exp, {}, lf_mveto, lens_fresh=True)
    assert "MOMO_CHG" not in b3v and any("vetoed" in l for l in pl3v), pl3v
    # declared direction disagreeing with the derived one is DISQUALIFIED
    b4, _, pl4 = consume_proposals(prop("taker.momo_chg", 4.0, "restrict"),
                                   momo_exp, {}, {}, lens_fresh=True)
    assert "MOMO_CHG" not in b4 and any("DISQUALIFIED" in l for l in pl4), pl4
    # max_hold: restrict OK, expand refused (no lens to earn with)
    b5, _, _ = consume_proposals(prop("taker.max_hold_h", 24.0, "restrict"),
                                 win_tape, {}, {}, lens_fresh=True)
    assert b5.get("MAX_HOLD_H") == 24.0, b5
    b6, _, pl6 = consume_proposals(prop("taker.max_hold_h", 72.0, "expand"),
                                   win_tape, {}, {}, lens_fresh=True)
    assert "MAX_HOLD_H" not in b6 and any("restrict-only" in l for l in pl6), pl6
    # per-cycle cap: 4 free restricts, only MAX_PROPOSALS_CYCLE enacted
    many = {}
    for lv, val in (("taker.momo_chg", 6.0), ("taker.brk_range", 0.97),
                    ("taker.div_gap_pp", 87.5), ("taker.max_hold_h", 24.0)):
        many.update(prop(lv, val, "restrict"))
    b7, pv7, pl7 = consume_proposals(many, win_tape, {}, {}, lens_fresh=True)
    assert len(pv7) == MAX_PROPOSALS_CYCLE, (pv7, pl7)
    assert any("cap" in l for l in pl7), pl7
    # empty channel -> untouched passthrough
    assert consume_proposals({}, win_tape, {"MOMO_CHG": 4.5}, {}, True)[0] \
        == {"MOMO_CHG": 4.5}

    # every ladder/sweep value must be registered + in-bounds in fleet_tuning
    for lens, (attr, lever, ladder) in TAKER_LADDERS.items():
        for v in ladder:
            assert tuning.clamp(lever, v) == v, (lever, v)
    for lens, (lever, default, ladder) in SCOUT_LADDERS.items():
        for v in ladder:
            assert tuning.clamp(lever, v) == v, (lever, v)
    for v in SWEEP_TP:
        assert tuning.clamp("taker.tp", v) == v
    for v in SWEEP_SL:
        assert tuning.clamp("taker.sl", v) == v
    for v in SWEEP_HOLD:
        assert tuning.clamp("taker.max_hold_h", v) == v
    for v in TOP_N_LADDER[2]:
        assert tuning.clamp(TOP_N_LADDER[0], v) == v

    print("scout_tuner selftest OK (ladders, veto, win-widen, lose-reject, "
          "floor-release, anti-overfit sweep gate, proprioception "
          "hurting-skip + helping-unlock + deeper-diet, registry bounds)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
