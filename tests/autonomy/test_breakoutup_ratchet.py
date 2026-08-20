"""[(sf)] The growth rail could only ever SHRINK the taker's one living lens.

MEASURED ON THE LIVE BUS, 2026-08-20. 🎫 the Ticket Taker's shadow book trades
exactly one lens — `long-breakoutup` holds every open slot, `dip` and
`divergence` are both vetoed by the book's own realised record. Both registered
levers that reach that lens sat at the TIGHTEST end of their cage:

    taker.brk_range   0.97   cage [0.90, 0.97]  hi = tightest   default 0.95
    taker.max_hold_h  24.0   cage [24.0, 72.0]  lo = tightest   default 48.0

Both `set_by: scout-tuner`, both from `organ-proposal:event-sentinel`. And
`lighter_ticket_replay.py:206` reads `_up = False if lens == "breakout" else
None`, so `bull_entry_ok` refuses EVERY breakout entry and the replay that
gates those enactments contains ZERO breakoutup trades — the tuner's own
published baseline says so: `breakout taken=0 closed=0`.

THE CONSEQUENCE IS ARITHMETIC. On a lens the gate cannot fill, a candidate's
replay delta is exactly $0.00:

    RESTRICT  fails only if `var < base - tol`  ->  0.00 passes, ENACTED FREE
    EXPAND    needs `+MARGIN_HALF` on both halves -> 0.00 can never clear it
    STARVING  needs `taken > 0` -> logs "0 replay fills — no evidence"

**The cage could only get smaller, forever.** Not a tuning accident — a
structural property of pointing a blind gate at a live lens.

THE FIX HERE is the cheap half: pin each cage's restrictive end AT the module
default. `clamp()` is `min(hi, max(lo, v))` and runs at READ, so both live
levers snap back on the next `get_lever` — no lever write, no deploy race, and
reach in the growth direction untouched.

IT IS NOT SOLD AS ALPHA. Restoring 24h -> 48h measures +0.22pp to +0.57pp/trade
on the book's own closes and LOSES to a same-coin random-start placebo
(P=0.45..0.88) — most of it is exposure, not edge. The claim is that an
UNEVIDENCED RESTRICTION IS REVERSED, and the burden for undoing a restriction a
blind gate imposed is not the burden for widening past a validated one.
"""
import pytest

pytestmark = pytest.mark.autonomy

import fleet_tuning as FT              # noqa: E402
import lighter_ticket_taker as TT      # noqa: E402


#: (lever, module attr, which cage end is the RESTRICTIVE one)
BREAKOUTUP_LEVERS = [
    ("taker.brk_range", "BRK_RANGE", "hi"),    # higher = must be nearer the high
    ("taker.max_hold_h", "MAX_HOLD_H", "lo"),  # lower  = cut sooner
    ("taker.brk_trail", "BRK_TRAIL", "lo"),    # lower  = bank sooner
    ("taker.brk_sl", "BRK_SL", "hi"),          # higher (less negative) = tighter
]


@pytest.mark.parametrize("lever,attr,tight_end", BREAKOUTUP_LEVERS)
def test_no_breakoutup_cage_is_tighter_than_the_operators_default(lever, attr,
                                                                  tight_end):
    """THE RULE, and it is the whole entry: while the actuator that moves these
    is blind to the lens they govern, its restrict path is free and its expand
    path is arithmetically impossible. A cage whose restrictive end sits BEYOND
    the default therefore hands a blind gate a one-way ratchet — it can walk
    the book tighter than the operator ever configured and can never walk it
    back."""
    lev = FT.LEVERS[lever]
    assert lev[tight_end] == lev["env_default"] == getattr(TT, attr), (
        f"{lever}'s restrictive end ({tight_end}={lev[tight_end]}) is not "
        f"pinned at the default ({lev['env_default']}) — a blind gate can "
        "ratchet this lens tighter than the operator configured")


@pytest.mark.parametrize("lever,attr,tight_end", BREAKOUTUP_LEVERS)
def test_and_the_growth_direction_still_has_room(lever, attr, tight_end):
    """The other half. Pinning the restrictive end must not close the cage —
    that would swap a one-way ratchet for a welded bolt, which is worse."""
    lev = FT.LEVERS[lever]
    loose = "lo" if tight_end == "hi" else "hi"
    assert lev[loose] != lev["env_default"], (
        f"{lever} has no room in the growth direction: {lev}")


def test_the_live_levers_snap_back_at_the_consumer():
    """`clamp` runs at READ as well as write, so the cage change reverses the
    two live levers with no lever write and no deploy race. This is the
    mechanism the fix depends on — if `clamp` ever stopped clamping at read,
    the cages would be documentation."""
    assert FT.clamp("taker.max_hold_h", 24.0) == 48.0
    assert FT.clamp("taker.brk_range", 0.97) == 0.95
    # …while a legitimate value inside the cage passes through untouched
    assert FT.clamp("taker.max_hold_h", 60.0) == 60.0
    assert FT.clamp("taker.brk_range", 0.92) == 0.92


def test_the_replay_still_cannot_see_the_lens_so_the_upstream_fix_is_open():
    """The DURABLE fix is upstream and is deliberately NOT in this change.
    This test exists to fail loudly the day someone teaches the replay the
    breakoutup relabel — at which point the cage pins may be revisited on
    evidence, and this docstring is where they should look."""
    import inspect
    import lighter_ticket_replay as R
    src = inspect.getsource(R)
    assert '_up = False if lens == "breakout" else None' in src, (
        "the replay's breakout blindness has changed — re-read (sf): the "
        "cage pins above were justified BY that blindness, and if the gate "
        "can now see the lens they are a decision to re-make on evidence, "
        "not a rule to keep by inertia")


def test_the_blind_lens_is_not_handed_to_the_tuners_proposal_surface():
    """Registering the trend-exit knobs for CONSUMPTION is reach; wiring them
    into the tuner's ladders would recreate the ratchet on two more knobs
    while the gate is still blind."""
    import lighter_scout_tuner as ST
    src = "".join(
        str(getattr(ST, n, "")) for n in dir(ST)
        if n.isupper() and isinstance(getattr(ST, n, None), (list, tuple, dict, set))
    )
    for lever in ("taker.brk_trail", "taker.brk_sl"):
        assert lever not in src, (
            f"{lever} reached a scout-tuner ladder/proposal surface while the "
            "replay still cannot fill breakoutup — restrict would enact free "
            "and expand could never pass")


def test_divergence_is_deliberately_left_alone():
    """Fixing the ratchet means fixing it where the gate is BLIND, not
    everywhere a lever moved. `taker.div_gap_pp` governs divergence, which the
    replay CAN see (42 taken), so the tuner had real evidence — and a 12-rung
    ladder through that replay reads negative at every rung and monotonically
    LESS negative as the bar tightens. Its cage must keep the room to stay
    tightened."""
    lev = FT.LEVERS["taker.div_gap_pp"]
    assert lev["hi"] > lev["env_default"], (
        "div_gap_pp lost the room to tighten — that room is EARNED here, on a "
        "lens the tuner's replay can actually fill")
