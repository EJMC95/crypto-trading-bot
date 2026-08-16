"""💸 the LIVE Farmer's fleet long budget, in-cycle — the CALL SITES.

[2026-08-16 (oh)] `entry_admission` is pure and its own selftest pins the RULE
(headroom 1 admits the first long and refuses the second, shorts unaffected,
unknown headroom fails OPEN). What no test of a pure function can say is that
`main()` still HANDS it the two values — and that half is where this defect
lived in the first place.

THE DEFECT. `fleet_long_veto` is a BOOLEAN read once per loop, so it answers
"was the fleet at its long budget when this pass started?", not "is there still
room for the long I am about to open". At `long_positions == budget - 1` the
veto is False and one pass may open `MAX_NEW_PER_LOOP` longs, putting the fleet
over a budget this bot's own log calls ENFORCED; `fleet-risk` republishes on its
own cadence, so the overshoot stands until it does. The 21-Jul budget-headroom
fix bounded exactly this race and reached `lighter_family_bot` and
`lighter_avo_live_bot` — both count `cycle_admitted` against
`fleet_long_headroom` — and NOT this file, the live real-money book. Found by
the (oa) sweep for pre-loop snapshots.

WHY AST AND NOT A SUBSTRING. The repo has paid for the substring version twice
in three days: `(nv)` found "listing wins a tie" defended by
`'"listing"' in block and "setdefault" in block` over a 400-character window,
which stayed green while the priority inverted. A `"longs_admitted" in src`
check here would pass on a file that merely MENTIONS the name — including in
the comment explaining why it matters. So each assertion below names a syntax
node: the keyword actually present in the call's dict literal, and an
`AugAssign` guarded by `if not is_short`.

Mutation-verified, five red: drop the increment, move it out from under its
`not is_short` guard, drop either key from the call, or seed the headroom with
a literal 0. The last one SURVIVED the first draft of this file — the `except`
branch also assigns None, so "a None exists somewhere" was not the invariant.
The invariant is that every assignment is None or a computation.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

_SRC = (pathlib.Path(__file__).resolve().parents[2]
        / "lighter_funding_bot.py").read_text()
_TREE = ast.parse(_SRC)


def _admission_calls():
    """Every `entry_admission(...)` call node in the module."""
    return [n for n in ast.walk(_TREE)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "entry_admission"]


def _state_dicts():
    """The `st` dict literal each production call passes.

    The ladder is called as `entry_admission(coin, src, is_short, apr, {...})`,
    so the state is the 5th positional argument. The selftest builds its state
    through a helper (a Name, not a Dict) — skipped here on purpose: this file
    is about what MAIN() passes.
    """
    out = []
    for call in _admission_calls():
        if len(call.args) >= 5 and isinstance(call.args[4], ast.Dict):
            out.append(call.args[4])
    return out


def test_main_passes_both_halves_of_the_budget():
    """The boolean AND the headroom+counter reach the ladder.

    Passing only the boolean is the pre-(oh) file: the ladder then reads
    `fleet_long_headroom` as absent, its in-cycle arm is inert by its own
    fail-open contract, and the guard is silently a no-op — the shape this
    repo calls a registered-but-inert rule.
    """
    dicts = _state_dicts()
    assert dicts, "no entry_admission call passes a dict literal — did main() change?"
    for d in dicts:
        keys = {k.value for k in d.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        for needed in ("fleet_long_veto", "fleet_long_headroom", "longs_admitted"):
            assert needed in keys, (
                f"main() calls entry_admission without {needed!r} — the "
                f"in-cycle long budget is inert. Passed: {sorted(keys)}")


def test_a_long_open_consumes_headroom_in_the_same_cycle():
    """`longs_admitted += 1` exists, and only for a LONG.

    Without the increment the headroom never depletes and the ladder admits
    every long in the pass — the exact overshoot (oh) closes, with a guard in
    place that reads as if it were working.
    """
    augs = [n for n in ast.walk(_TREE)
            if isinstance(n, ast.AugAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "longs_admitted"
            and isinstance(n.op, ast.Add)]
    assert augs, "nothing increments longs_admitted — the headroom never depletes"

    # ...and it must sit under `if not is_short`, else a SHORT consumes the
    # LONG budget and the funding mandate's shorts start being rationed by a
    # rule that was never meant to touch them (IMB-17).
    guarded = False
    for node in ast.walk(_TREE):
        if not isinstance(node, ast.If):
            continue
        t = node.test
        if not (isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not)
                and isinstance(t.operand, ast.Name)
                and t.operand.id == "is_short"):
            continue
        if any(a in ast.walk(node) for a in augs):
            guarded = True
            break
    assert guarded, (
        "longs_admitted is incremented outside `if not is_short:` — a SHORT "
        "would consume the LONG budget")


def test_the_headroom_is_computed_fail_open():
    """`fleet_long_headroom` starts as None and is only set under `enforce`.

    None is the pre-(oh) behaviour by construction (the ladder's arm is
    `is not None`), so a dark, stale or advisory fleet-risk costs the book
    nothing. A default of 0 here would idle every long entry the moment the
    organ blinked — fail-closed on the growth side, which this fleet has been
    bitten by before.
    """
    assigns = [n for n in ast.walk(_TREE)
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "fleet_long_headroom"
                       for t in n.targets)]
    assert assigns, "fleet_long_headroom is never assigned"
    nones = [n for n in assigns
             if isinstance(n.value, ast.Constant) and n.value.value is None]
    assert nones, (
        "fleet_long_headroom is never initialised to None — unknown headroom "
        "must fail OPEN, and the ladder distinguishes exactly on `is not None`")

    # ...and EVERY assignment is either that None or a computed headroom.
    # Asserting only "a None exists somewhere" is not enough: the `except`
    # branch also assigns None, so seeding the initialiser with a literal 0
    # slips through — and 0 means a dark or advisory fleet-risk refuses every
    # long, which is fail-CLOSED on the growth side. (Caught by mutation: this
    # exact swap survived the first version of this test.)
    for n in assigns:
        if isinstance(n.value, ast.Constant):
            assert n.value.value is None, (
                f"fleet_long_headroom assigned the literal {n.value.value!r} at "
                f"line {n.lineno} — the only literal allowed is None (unknown "
                f"headroom fails OPEN); a number here rations longs on an "
                f"organ outage")
        else:
            assert isinstance(n.value, ast.Call), (
                f"fleet_long_headroom assigned a non-call expression at line "
                f"{n.lineno} — expected the max(0, budget - held) computation")
