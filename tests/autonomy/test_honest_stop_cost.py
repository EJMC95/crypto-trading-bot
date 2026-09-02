"""[(xp)] The all-slots-stop cost, measured rather than assumed.

`leverage.all_slots_stop_pct` prices an all-slots stop at `gross_x * |stoploss|`
— which assumes every stop fires AT its level. 👩 mum's own live fills say it
does not: n=6 measured 12.2 / 12.2 / 12.6 / 40.8 / 51.7 / 62.4 bps PAST the
level, so her 4.0% stop has actually cost 4.01%..4.62%.

The (th) comment specified this ceiling and never built it ("the honest ceiling
divides by (|stop|+overshoot+mmf)") — a defense living only in prose is a
defense that has not been written (I21/(tt)).

It is REPORTED, never a clamp: `GROSS_X_MAX` is an operator env by (sr)'s
explicit rule. What these tests pin is that the number is honest in the one
direction that matters — it may never read LOWER than the assumption it
corrects, and it may never silently BE that assumption.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("FAMILY_LIVE_BOOK", "freqtrade-avo-maria")

import lighter_avo_live_bot as L  # noqa: E402


def _ov(vals, n=None):
    return {"n": len(vals) if n is None else n, "unmeasured_n": 0,
            "vals": list(vals)}


FLOOR = L.OVERSHOOT_MIN_N


def test_the_n_floor_is_the_fleets_own_constant_not_a_second_copy():
    """(hj): pin re-use by IDENTITY. A retyped constant is one that drifts.

    Reached via `fleet_bus`, which this image CARRIES — importing
    `fleet_allocation` here would take a fallback silently in production while
    this very test passed in the repo (the 17-Jul brain_stats class). The
    fleet_bus -> fleet_allocation half of the chain is pinned by
    `test_brain_sizing_rails`; this pins our half of it.
    """
    import fleet_bus
    from fleet_allocation import MIN_N
    assert L.OVERSHOOT_MIN_N == fleet_bus.LB_CAP_MIN_N
    assert fleet_bus.LB_CAP_MIN_N == MIN_N  # the chain, end to end


def test_the_floor_is_not_reached_through_a_module_this_image_lacks():
    """`audit_image_imports` caught the first version of this. Keep it caught:
    the real-money image COPYs fleet_bus and not fleet_allocation."""
    import ast
    src = open(L.__file__).read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module == "fleet_allocation":
            raise AssertionError(
                "lighter_avo_live_bot imports fleet_allocation, which "
                "Dockerfile.avolive does not COPY — a guarded import makes "
                "that SILENT in production")
        if isinstance(node, ast.Import):
            assert not any(a.name == "fleet_allocation" for a in node.names)


def test_below_the_floor_it_is_none_never_the_flattering_assumption():
    thin = _ov([50.0] * (FLOOR - 1))
    assert L._honest_stop_cost(thin, gx=2.0, stop=-0.04) is None


def test_at_the_floor_it_speaks():
    ok = _ov([50.0] * FLOOR)
    assert L._honest_stop_cost(ok, gx=2.0, stop=-0.04) is not None


def test_it_adds_the_overshoot_to_the_stop():
    # p90 of a constant list is that constant: 50bps = 0.005
    got = L._honest_stop_cost(_ov([50.0] * FLOOR), gx=2.0, stop=-0.04)
    assert got == round(2.0 * (0.04 + 0.005), 4)
    # and it is strictly WORSE than the assumption it corrects
    assert got > 2.0 * 0.04


def test_it_never_reads_lower_than_the_fire_at_level_number():
    """A fill BETTER than the level does not earn leverage."""
    good = _ov([-90.0] * FLOOR)
    got = L._honest_stop_cost(good, gx=3.0, stop=-0.04)
    assert got == round(3.0 * 0.04, 4)


def test_mums_own_six_fills_land_where_the_ledger_says():
    """The measured record, run through the shipped function."""
    mum = [12.2, 12.6, 13.0, 40.8, 51.7, 62.4]
    # her real n is 6 — below the floor, so the honest answer today is None
    assert L._honest_stop_cost(_ov(mum), gx=1.0, stop=-0.04) is None
    # padded to the floor with her own worst, the cost is her stop + p90
    padded = mum + [62.4] * (FLOOR - len(mum))
    got = L._honest_stop_cost(_ov(padded), gx=1.0, stop=-0.04)
    assert got is not None and got > 0.04
    # the field is published rounded to 4dp
    assert got == round(0.04 + 0.00624, 4)


@pytest.mark.parametrize("bad", [None, {}, {"n": 99, "vals": None},
                                 {"n": 99, "vals": ["x"] * 40},
                                 {"n": "many", "vals": [1.0] * 40}])
def test_junk_and_dark_degrade_to_none_and_never_raise(bad):
    assert L._honest_stop_cost(bad, gx=2.0, stop=-0.04) is None


def test_a_nonfinite_gross_or_stop_is_none_not_an_exception():
    assert L._honest_stop_cost(_ov([10.0] * FLOOR), gx=float("inf"),
                               stop=-0.04) is None
    assert L._honest_stop_cost(_ov([10.0] * FLOOR), gx=2.0,
                               stop=float("nan")) is None


def test_the_row_publishes_both_numbers_under_distinguishable_names():
    """Quiet and dark must not be the same byte-string (I1/I18): a reader has
    to be able to tell 'not measured' from 'measured and equal'."""
    src = open(L.__file__).read()
    assert '"all_slots_stop_pct"' in src
    assert '"all_slots_stop_pct_measured": _honest_stop_cost(ov)' in src
    assert '"overshoot_n"' in src
