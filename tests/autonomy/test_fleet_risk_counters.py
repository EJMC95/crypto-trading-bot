"""[2026-08-03 (iv)] THE THREE FLEET POSITION COUNTERS MUST BE RECONCILABLE.

THE INCIDENT, carried as an open review item for four days. One `fleet-risk`
payload published `long_positions=11`, `exposure.long_n=15` and `gross=13`,
with `exposure.sym_uncovered=0` asserting the symbol view saw everything the
budget counted. Three numbers describing "how many longs does the fleet hold",
disagreeing, and the ENFORCED long-budget veto acts on the first of them
(`fleet_bus` reads `long_positions`).

TWO DEFECTS, and neither was the arithmetic:

  1. **`per_bot` was computed on every cycle and thrown away at the publish
     boundary.** The breakdown that says WHICH bot contributes what — the only
     thing that turns a discrepancy into a diagnosis — never left the process.
     That is why the item survived four reviews: each one could see the gap and
     none could attribute it. I8, pointed at the organ's own output.

  2. **`sym_uncovered` could only report HALF its own failure mode.** It was
     `max(0, longs + shorts - covered)`, so when the symbol harvest saw MORE
     positions than the budget cohort counted, the excess was clamped to zero
     and the metric read "fully covered". The honesty metric was structurally
     incapable of reporting the direction that was actually happening.

Also pinned here: the fleet budgets are env-backed, which is Step 1 of the
growth restructure — they were the only bounds in `fleet_risk.py` that were
not, so the growth rail could widen every book's universe and cap but not the
fleet-wide budget those books compete for.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_risk as fr  # noqa: E402
import fleet_tuning as tuning  # noqa: E402

pytestmark = pytest.mark.autonomy


def test_over_coverage_is_reported_not_clamped_away():
    """The direction the old metric could not see.

    Mutation that turns this red: drop `over` and go back to reporting only
    `sym_uncovered`.
    """
    e = fr.exposure_concentration(
        [("bot", "BTC", "long"), ("bot", "ETH", "long")], uncovered=0, over=4)
    assert e["sym_over"] == 4, e
    assert e["sym_uncovered"] == 0, e
    # and the two are independent, not the same number under two names
    e2 = fr.exposure_concentration([("b", "BTC", "long")], uncovered=3, over=0)
    assert (e2["sym_uncovered"], e2["sym_over"]) == (3, 0), e2


def test_a_fully_reconciled_view_reports_zero_in_both_directions():
    """The clean case must be clean — otherwise the metric cries wolf and the
    (hh) rule bites: a detector that flags everything trains you to ignore it."""
    e = fr.exposure_concentration(
        [("b", "BTC", "long"), ("b", "ETH", "short")], uncovered=0, over=0)
    assert e["sym_uncovered"] == 0 and e["sym_over"] == 0, e
    assert e["long_n"] == 1 and e["short_n"] == 1, e


def test_the_budgets_are_env_backed_so_the_ceiling_is_reachable():
    """STEP 1: inert on ship, but no longer a bare literal.

    Mutation that turns this red: revert either to a literal.
    """
    import ast
    import pathlib
    tree = ast.parse(pathlib.Path(fr.__file__).read_text(encoding="utf-8"))
    env_backed = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if name not in ("LONG_BUDGET", "SHORT_BUDGET"):
            continue
        for sub in ast.walk(node.value):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "get"
                    and isinstance(sub.func.value, ast.Attribute)
                    and sub.func.value.attr == "environ"):
                env_backed.add(name)
    assert env_backed == {"LONG_BUDGET", "SHORT_BUDGET"}, (
        f"still a bare literal: {{'LONG_BUDGET','SHORT_BUDGET'}} - {env_backed} "
        "— the growth rail cannot reach a literal")


def test_the_budget_levers_are_registered_but_NOT_auto_enactable():
    """BOTH halves are deliberate and both are load-bearing.

    Registered: machine-readable, drift-checked against the code, settable by
    the operator without a deploy.

    NOT enactable: this veto reaches the strategies, the family books AND the
    Ticket Taker. A lane that lets an automated author widen the fleet's whole
    risk budget is a categorically larger object than one that widens a single
    shadow book's universe, and turning it on must be an explicit operator act.

    Mutation that turns this red: move either lever onto an enacted lane.
    """
    for name, dflt in (("risk.long_budget", 20), ("risk.short_budget", 12)):
        spec = tuning.LEVERS.get(name)
        assert spec, f"{name} unregistered"
        assert spec["env_default"] == dflt, spec
        assert spec["lo"] <= spec["env_default"] <= spec["hi"], spec
        # one-sided UP: the rail may only ever widen the fleet's budget
        assert spec["lo"] == spec["env_default"], (
            f"{name} must not be tightenable below the operator's value")
        assert spec["lane"] not in tuning.ENACT_LANES, (
            f"{name} is on an ENACTED lane — an automated author must not be "
            "able to move the fleet-wide risk budget")


def test_registering_the_budgets_changed_nothing():
    """INERT ON SHIP. The whole justification for doing Step 1 separately is
    that it cannot move behaviour; if these ever differ, it did."""
    assert fr.LONG_BUDGET == 20 and fr.SHORT_BUDGET == 12


def test_per_bot_reaches_the_payload():
    """THE FIX THAT CLOSES THE CLASS.

    `per_bot` was populated on every cycle by both counting loops and never
    published, so `long_positions` vs `exposure.long_n` vs `gross` could be
    seen to disagree and never attributed. Publishing it converts a mystery
    into a measurement.

    AST over the publish dict, not a substring scan — this file's own prose
    says "per_bot" many times over (the (hm) lesson).

    Mutation that turns this red: drop the key from the published dict.
    """
    import ast
    import pathlib
    tree = ast.parse(pathlib.Path(fr.__file__).read_text(encoding="utf-8"))

    # the payload dict is the one carrying the counters we are reconciling
    published = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if {"long_positions", "gross", "exposure"} <= keys:
            assert "per_bot" in keys, (
                "the payload carrying long_positions/gross/exposure does not "
                "publish per_bot — the breakdown that attributes the gap")
            published = True
    assert published, "could not find the fleet-risk payload dict"


def test_the_counters_are_documented_as_distinct_populations():
    """`long_positions` counts the BUDGET cohort; `exposure.long_n` counts
    SYMBOL-HARVESTED positions. They are allowed to differ — what is not
    allowed is differing silently, which is what `sym_over` now prevents.

    This asserts the payload can express the disagreement at all: a reader
    holding only these fields must be able to tell a reconciled view from an
    unreconciled one.
    """
    e = fr.exposure_concentration([("b", "BTC", "long")], uncovered=0, over=4)
    assert {"long_n", "sym_uncovered", "sym_over"} <= set(e), e
    assert e["sym_over"] > 0, "the payload must be able to SAY they disagree"
