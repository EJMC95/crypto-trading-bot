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
    "divergence": ("DIV_GAP_PP", "taker.div_gap_pp", [500.0, 450.0, 400.0, 350.0, 300.0]),
}
# Scout emission-bar ladders (advisory tickets — widen the brain's diet)
SCOUT_LADDERS = {
    "dip":      ("scout.dip_range_max", 0.10, [0.10, 0.15, 0.20, 0.25]),
    "breakout": ("scout.brk_range_min", 0.90, [0.90, 0.87, 0.84, 0.80]),
    "momentum": ("scout.momo_chg_min",  3.0,  [3.0, 2.5, 2.0]),
}
TOP_N_LADDER = ("scout.ticket_top_n", 6, [6, 9, 12, 15])
# Exit-ladder sweep grid = the 21-Jul agenda item-2 grid, verbatim
SWEEP_TP = [0.03, 0.04, 0.05, 0.06]
SWEEP_SL = [-0.02, -0.03, -0.04]
SWEEP_HOLD = [24.0, 48.0, 72.0]

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


def not_worse(tape_a, tape_b, bars_base, bars_var, tol=TOL):
    """Variant is acceptable if its closed net is within tol of (or above)
    the base bars' on BOTH halves — the doctrine's both-halves rule."""
    for half in (tape_a, tape_b):
        if not half:
            return False
        base = replay_with(half, bars_base)["closed_net"]
        var = replay_with(half, bars_var)["closed_net"]
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
    """The taker's own veto rule — the tuner never widens what the brain
    has ruled negative at the floor."""
    out = set()
    for lens, o in (lens_fwd or {}).items():
        if ((o.get("n4h") or 0) >= LENS_FLOOR
                and (o.get("avg4h_pct") or 0) < 0
                and (o.get("hit4h") or 0) < 0.5):
            out.add(lens)
    return out


def desired_taker_bars(tape, baseline, lens_fwd):
    """Walk each lens's conviction-bar ladder from the DEFAULT. Two rules:

    STARVING (seen tickets, zero fills, under the brain's ruling floor):
      widen one not-worse-on-both-halves notch at a time until the lens
      produces replay fills — samples are the goal, P&L must merely not
      degrade.
    WINNER (brain-graded POSITIVE at the ruling floor — the taker-veto rule
      inverted): expand the bar while each notch IMPROVES the replayed net
      on both halves by MARGIN_HALF — this is how the cream gets captured
      at size instead of waiting for an operator to notice.

    Returns ({tt attr: value} that differ from default, log list)."""
    h1, h2 = halves(tape)
    if not h1 or not h2:
        return {}, ["tape too short to halve — no taker-bar changes"]
    veto = vetoed_lenses(lens_fwd)
    bars = dict(DEFAULTS)
    log = []
    for lens, (attr, _lever, ladder) in TAKER_LADDERS.items():
        if lens in veto:
            log.append(f"{lens}: brain-vetoed at floor — never widened")
            continue
        lens_rep = (baseline.get("lenses") or {}).get(lens) or {}
        g = (lens_fwd or {}).get(lens) or {}
        graded = g.get("n4h") or 0
        positive = (graded >= LENS_FLOOR and (g.get("avg4h_pct") or 0) > 0
                    and (g.get("hit4h") or 0) >= 0.5)
        starving = (lens_rep.get("seen", 0) > 0
                    and lens_rep.get("taken", 0) == 0
                    and graded < LENS_FLOOR)
        if not (starving or positive):
            continue
        for notch in next_notches(ladder, DEFAULTS[attr]):
            cand = dict(bars, **{attr: notch})
            if positive:
                ok = all(replay_with(h, cand)["closed_net"]
                         >= replay_with(h, bars)["closed_net"] + MARGIN_HALF
                         for h in (h1, h2))
                if not ok:
                    log.append(f"{lens}: notch {notch} REJECTED "
                               f"(no improvement on a half)")
                    break
                bars[attr] = notch
                taken = (replay_with(tape, cand).get("lenses") or {}) \
                    .get(lens, {}).get("taken", 0)
                log.append(f"{lens} (winner): widened {attr} -> {notch} "
                           f"(replay taken={taken}, improves both halves)")
                continue
            # [2026-07-16 AUDIT FIX] starving path: a notch that produces ZERO
            # replay fills used to pass not_worse trivially (0.0 vs 0.0) and
            # the walk enacted the ladder MAX on no evidence at all. A notch
            # is only enacted when the replay actually FILLS at it (evidence)
            # AND not-worse holds; unevidenced notches are probed but never
            # enacted, and an unreachable lens correctly gets NO widen.
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
    base_net = baseline["closed_net"]
    best, best_net = None, base_net
    for tp in SWEEP_TP:
        for sl in SWEEP_SL:
            for hold in SWEEP_HOLD:
                cand = {"TAKE_PROFIT": tp, "STOP_LOSS": sl, "MAX_HOLD_H": hold}
                if cand == base_bars:
                    continue
                net = replay_with(tape, cand)["closed_net"]
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
        b = replay_with(half, base_bars)["closed_net"]
        v = replay_with(half, best)["closed_net"]
        if v < b + MARGIN_HALF:
            log.append(f"sweep: winner fails a half (+${v - b:.2f} < "
                       f"${MARGIN_HALF:.2f}) — refused (both-halves rule)")
            return {}, log
    log.append(f"sweep: {best} beats baseline +${best_net - base_net:.2f} "
               f"on the tape AND both halves — enacting")
    return {k: v for k, v in best.items() if v != DEFAULTS[k]}, log


def desired_scout_levers(lens_fwd):
    """Scout emission widening: advisory tickets only — this widens the
    BRAIN'S GRADING DIET, never what trades (the taker's bars gate fills).
    A lens under the brain's ruling floor gets its emission bar held one
    notch beyond default until the floor is reached, then released (the
    lever expires back to default on its own). The live 15-Jul case this
    exists for: dip graded n4h=25 (hit 92%!) while every other lens sat at
    ~250 — the best lens was the one starving for grades. Returns
    ({lever: value}, log)."""
    out, log = {}, []
    veto = vetoed_lenses(lens_fwd)
    for lens, (lever, default, ladder) in SCOUT_LADDERS.items():
        if lens in veto:
            continue
        graded = ((lens_fwd or {}).get(lens) or {}).get("n4h") or 0
        if graded < LENS_FLOOR:
            val = ladder[1] if len(ladder) > 1 else default
            out[lever] = val
            log.append(f"{lens}: graded n4h={graded} < {LENS_FLOOR} — scout "
                       f"emission {lever} -> {val} (grading diet, not trading)")
        # else: floor reached — stop asserting, lever expires to default
    lever, default, ladder = TOP_N_LADDER
    hungry = any(((lens_fwd or {}).get(l) or {}).get("n4h", 0) < LENS_FLOOR
                 for l in SCOUT_LADDERS)
    if hungry and lens_fwd:
        val = ladder[1]
        out[lever] = val
        log.append(f"ticket_top_n -> {val} (a lens is below the ruling floor)")
    return out, log


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

    baseline = replay_with(tape, DEFAULTS)
    bars, log1 = desired_taker_bars(tape, baseline, lens_fwd)
    exits, log2 = sweep_exits(tape, baseline)
    bars.update(exits)
    if lf_fresh:
        scout_levers, log3 = desired_scout_levers(lens_fwd)
    else:
        scout_levers, log3 = {}, ["lens-forward missing/stale — no scout-diet "
                                  "changes (fail-safe neutral)"]

    attr_to_lever = {attr: lever for _l, (attr, lever, _lad) in TAKER_LADDERS.items()}
    attr_to_lever.update({"TAKE_PROFIT": "taker.tp", "STOP_LOSS": "taker.sl",
                          "MAX_HOLD_H": "taker.max_hold_h"})
    levers = {attr_to_lever[a]: {
        "value": v,
        "reason": "replay-gated widen/optimize (both-halves on the tape)",
        "evidence": f"tape {baseline['span']} ({baseline['snapshots']} snaps); "
                    f"baseline net ${baseline['closed_net']}"}
        for a, v in bars.items()}
    for lever, v in scout_levers.items():
        levers[lever] = {"value": v,
                         "reason": "lens starving — widen the brain's grading diet",
                         "evidence": f"lens-forward n4h below {LENS_FLOOR}"}

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
        "enacted": now_set, "log": (log1 + log2 + log3)[:20],
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
    bars_w, log_w = desired_taker_bars(win_tape, base, lf_winner)
    assert bars_w.get("DIP_RANGE") == 0.08, (bars_w, log_w)
    # ...but a positive grade never expands into replay LOSSES
    bars_wl, _ = desired_taker_bars(lose_tape, base_l, lf_winner)
    assert "DIP_RANGE" not in bars_wl

    # sweep refuses tiny samples (anti-overfit floor)
    exits, slog = sweep_exits(win_tape, base)
    assert exits == {} and "skipped" in slog[0], slog

    # scout levers: a lens under the ruling floor gets its emission bar one
    # notch beyond default (grading diet); at the floor it is released
    sl, slog2 = desired_scout_levers({"dip": {"n4h": 25, "avg4h_pct": 1.1,
                                              "hit4h": 0.92},
                                      "breakout": {"n4h": 240},
                                      "momentum": {"n4h": 252}})
    assert sl.get("scout.dip_range_max") == 0.15, (sl, slog2)
    assert "scout.brk_range_min" not in sl, sl
    assert sl.get("scout.ticket_top_n") == 9, sl
    sl2, _ = desired_scout_levers({"dip": {"n4h": 100, "avg4h_pct": 1.0,
                                           "hit4h": 0.6},
                                   "breakout": {"n4h": 100},
                                   "momentum": {"n4h": 100}})
    assert sl2 == {}, sl2
    # a vetoed lens gets NO extra diet either
    sl3, _ = desired_scout_levers({"dip": {"n4h": 80, "avg4h_pct": -1.0,
                                           "hit4h": 0.3},
                                   "breakout": {"n4h": 100},
                                   "momentum": {"n4h": 100}})
    assert "scout.dip_range_max" not in sl3, sl3

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
          "floor-release, anti-overfit sweep gate, registry bounds)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
