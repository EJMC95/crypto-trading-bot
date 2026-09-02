"""[(sk)] The growth rail could only ever SHRINK the taker's one living lens.

MEASURED ON THE LIVE BUS, 2026-08-20. 🎫 the Ticket Taker's shadow book trades
exactly one lens — `long-breakoutup` holds every open slot, `dip` and
`divergence` are both vetoed by the book's own realised record. Both registered
levers that reach that lens sat at the TIGHTEST end of their cage:

    taker.brk_range   0.97   cage [0.90, 0.97]  hi = tightest   default 0.95
    taker.max_hold_h  24.0   cage [24.0, 72.0]  lo = tightest   default 48.0

Both `set_by: scout-tuner`, both from `organ-proposal:event-sentinel`. And the
replay that gates those enactments contained ZERO breakoutup trades, so on a
lens the gate cannot fill a candidate's replay delta is exactly $0.00:

    RESTRICT  fails only if `var < base - tol`  ->  0.00 passes, ENACTED FREE
    EXPAND    needs `+MARGIN_HALF` on both halves -> 0.00 can never clear it

**The cage could only get smaller, forever** — a structural property of
pointing a blind gate at a live lens. (sk)'s fix pinned every breakoutup
cage's restrictive end at the module default, explicitly as a decision to
re-make the day the gate could see.

[2026-09-02 — THE GATE CAN SEE, AND THE DECISION WAS RE-MADE.] The replay
gained `daily_up_resolver` + the taker's own breakoutup relabel, the tuner
builds and forwards it every cycle (its own selftests pin the forwarding),
and the LIVE tuner baseline read `breakoutup taken=26 closed=23` the day this
was re-decided. So:

  * `taker.brk_range` / `taker.max_hold_h` — the two levers the tuner's
    ladders actually walk — are TWO-WAY again. A restrict walk now pays a
    real replay delta; expand can genuinely clear its margin. The un-pin is
    COUPLED TO SIGHT below: re-blind the replay or stop forwarding the
    resolver and these tests demand the pins back. [Same day, later:
    `max_hold_h` was then DECOUPLED from the breakout arm entirely — the
    trend exit runs its own `BRK_MAX_HOLD_H` clock (AST-pinned in the
    taker's selftest), so the lever steers only the divergence bracket,
    a lens the replay could always fill (42 taken).]
  * `taker.brk_trail` / `taker.brk_sl` STAY pinned — not blindness any more:
    nothing walks them (registered for consumption only, off every ladder),
    and both widenings were measured and WITHHELD on their own numbers
    (trail effect below the harness's +0.508pp calibration drift; the
    48h->96h clock gain falls +0.78pp -> +0.07pp to leave-one-symbol-out).
"""
import inspect

import pytest

pytestmark = pytest.mark.autonomy

import fleet_tuning as FT              # noqa: E402
import lighter_ticket_taker as TT      # noqa: E402


#: The levers whose restrictive end STAYS pinned at the operator default:
#: (lever, module attr, which cage end is the RESTRICTIVE one). Nothing walks
#: these, and their widenings were measured-and-withheld — see the module doc.
BREAKOUTUP_LEVERS = [
    ("taker.brk_trail", "BRK_TRAIL", "lo"),    # lower  = bank sooner
    ("taker.brk_sl", "BRK_SL", "hi"),          # higher (less negative) = tighter
]

#: The levers un-pinned 2-Sep on the sighted-gate evidence:
#: (lever, restrictive end, restored bound).
UNPINNED = [
    ("taker.brk_range", "hi", 0.97),
    ("taker.max_hold_h", "lo", 24.0),
]


@pytest.mark.parametrize("lever,attr,tight_end", BREAKOUTUP_LEVERS)
def test_the_unwalked_trend_exit_cages_stay_pinned_at_the_default(lever, attr,
                                                                  tight_end):
    """These two reach no actuator (no ladder walks them), so an open
    restrictive end is reach handed to nothing — and both widenings were
    measured and withheld. Unpinning them is a separate, measured decision."""
    lev = FT.LEVERS[lever]
    assert lev[tight_end] == lev["env_default"] == getattr(TT, attr), (
        f"{lever}'s restrictive end ({tight_end}={lev[tight_end]}) is not "
        f"pinned at the default ({lev['env_default']}) — see the module doc: "
        "unpinning this one needs a ladder design and a measurement, not a "
        "cage edit")


@pytest.mark.parametrize("lever,attr,tight_end", BREAKOUTUP_LEVERS)
def test_and_the_growth_direction_still_has_room(lever, attr, tight_end):
    """Pinning the restrictive end must not close the cage — that would swap
    a one-way ratchet for a welded bolt, which is worse."""
    lev = FT.LEVERS[lever]
    loose = "lo" if tight_end == "hi" else "hi"
    assert lev[loose] != lev["env_default"], (
        f"{lever} has no room in the growth direction: {lev}")


@pytest.mark.parametrize("lever,tight_end,restored", UNPINNED)
def test_the_walked_levers_are_two_way_again(lever, tight_end, restored):
    """The 2-Sep un-pin: the tuner's gate can fill the lens, so its restrict
    path pays a real replay delta and the two-way cage is honest."""
    lev = FT.LEVERS[lever]
    assert lev[tight_end] == restored, (
        f"{lever}'s restrictive end moved from the restored {restored} — if "
        "this was re-pinned, the sight test below should say why; if it was "
        "widened further, that needs its own measurement")
    assert lev[tight_end] != lev["env_default"], (
        f"{lever} reads pinned-at-default again — if the gate went blind, "
        "fine, but then the sight test below must be failing too")


def test_the_unpin_is_coupled_to_the_gates_sight():
    """THE CONDITION, executable. The two-way cages above are legitimate ONLY
    while the tuner's replay can see breakoutup: the replay must own the
    resolver + relabel, and the tuner must build and forward it. Re-blind
    either half and this fails, demanding the (sk) pins back."""
    import lighter_ticket_replay as R
    import lighter_scout_tuner as ST
    assert callable(getattr(R, "daily_up_resolver", None)), (
        "the replay lost daily_up_resolver — the tuner's gate is blind to "
        "breakoutup again: re-pin taker.brk_range hi=0.95 and "
        "taker.max_hold_h lo=48.0 (the (sk) rule)")
    assert 'lens = "breakoutup"' in inspect.getsource(R), (
        "the replay lost the breakoutup relabel — same consequence as above")
    assert callable(getattr(ST, "build_up_resolver", None)), (
        "the tuner lost build_up_resolver — its replay runs blind: re-pin")
    assert "up_resolver=_UP_RESOLVER" in inspect.getsource(ST), (
        "the tuner no longer forwards the cycle's resolver into replay() — "
        "its gate is blind in practice whatever the replay supports: re-pin")


def test_the_restored_reach_passes_the_clamp():
    """`clamp` runs at READ as well as write. The restored bounds must pass
    through, and beyond-cage values must still clamp — reach, not anarchy."""
    assert FT.clamp("taker.max_hold_h", 24.0) == 24.0
    assert FT.clamp("taker.brk_range", 0.97) == 0.97
    assert FT.clamp("taker.max_hold_h", 12.0) == 24.0
    assert FT.clamp("taker.brk_range", 0.99) == 0.97
    # …and legitimate interior values are untouched
    assert FT.clamp("taker.max_hold_h", 60.0) == 60.0
    assert FT.clamp("taker.brk_range", 0.92) == 0.92


def test_the_trend_exit_knobs_are_still_not_on_the_tuners_ladders():
    """brk_trail/brk_sl stay off every tuner ladder/proposal surface — no
    longer because the gate is blind (it is not), but because wiring them in
    is a WIDENING whose two candidate moves were measured and withheld
    ((sk): trail below calibration drift; clock gain dies ex-HYPE). A ladder
    for them needs its own design + evidence, recorded when it ships."""
    import lighter_scout_tuner as ST
    src = "".join(
        str(getattr(ST, n, "")) for n in dir(ST)
        if n.isupper() and isinstance(getattr(ST, n, None), (list, tuple, dict, set))
    )
    for lever in ("taker.brk_trail", "taker.brk_sl"):
        assert lever not in src, (
            f"{lever} reached a scout-tuner ladder/proposal surface — that "
            "widening was measured and withheld; shipping it needs the new "
            "measurement recorded, not just this test edited")


def test_divergence_is_deliberately_left_alone():
    """Fixing the ratchet means fixing it where the gate was BLIND, not
    everywhere a lever moved. `taker.div_gap_pp` governs divergence, which the
    replay could always see (42 taken), so the tuner had real evidence — and a
    12-rung ladder through that replay reads negative at every rung and
    monotonically LESS negative as the bar tightens. Its cage must keep the
    room to stay tightened."""
    lev = FT.LEVERS["taker.div_gap_pp"]
    assert lev["hi"] > lev["env_default"], (
        "div_gap_pp lost the room to tighten — that room is EARNED here, on a "
        "lens the tuner's replay can actually fill")
