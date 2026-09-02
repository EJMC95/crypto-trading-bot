"""[2026-09-02 (wp)] THE STOP-DEAD PAGE WAS FIRING ON A BASKET NOBODY HELD.

MEASURED 2-Sep on both real-money rows: `worst_mmf(universe)` — the worst
maintenance margin across the ~93 books a row COULD hold — read 0.20 for 👩
mum, applied at her FULL-slot gross of 9.5x, so `stop_reachable` published
False and fleet_immune paged "protective stop is DEAD (ceiling 4.17)" every
loop. Her HELD basket, read off the venue's own margin block, was TAO 12%,
PENGU 7.5%, four majors at 6%, XCU/GRAM 3%, XAU 2.4%, QQQ 2%, SPY 1.2% —
notional-weighted ~5-6% — at the venue's own 5.6x, i.e. ~12% to liquidation
against a -4% stop. A trigger the book satisfies structurally is not a
measurement (I7); a detector that flags everything trains the operator to
ignore it ((gl)).

The bound stays published. `held_mmf` is the measurement beside it, and
fleet_immune pages on THAT when the row carries it.

Mutations that turn these red: weight equally when values are present; drop
the riskiest leg on an unreadable margin instead of returning None; treat a
missing `value` as 0 weight (which silently drops the leg).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import lighter_avo_live_bot as A  # noqa: E402

pytestmark = pytest.mark.autonomy

ROWS = {"TAO": {"mmf_bps": 1200}, "SPY": {"mmf_bps": 120},
        "DOGE": {"mmf_bps": 600}, "XCU": {"mmf_bps": 300}}


def test_the_held_basket_is_notional_weighted():
    pos = {"TAO": {"value": 100.0}, "SPY": {"value": 300.0}}
    m, w = A.held_mmf(pos, ROWS)
    assert w == "notional"
    assert abs(m - (0.12 * 100 + 0.012 * 300) / 400) < 1e-9
    # order of magnitude below the universe-worst bound the row also publishes
    assert m < 0.20


def test_an_unreadable_leg_makes_the_basket_unreadable_never_smaller():
    pos = {"TAO": {"value": 100.0}, "MYSTERY": {"value": 900.0}}
    assert A.held_mmf(pos, ROWS) == (None, None)
    assert A.held_mmf(pos, None) == (None, None)
    assert A.held_mmf({}, ROWS) == (None, None)
    assert A.held_mmf(None, ROWS) == (None, None)


def test_missing_notionals_fall_back_to_equal_weights_and_say_so():
    pos = {"TAO": {}, "SPY": {"value": None}}
    m, w = A.held_mmf(pos, ROWS)
    assert w == "equal" and abs(m - (0.12 + 0.012) / 2) < 1e-9


def test_the_stop_is_reachable_on_the_september_basket_and_dead_on_the_bound(monkeypatch):
    """The 2-Sep numbers: bound 0.20 @ 9.5x -> dead; held ~0.055 @ 5.6x ->
    reachable with ~12% to liquidation against the -4% stop."""
    monkeypatch.setattr(A.S, "stoploss", -0.04, raising=False)
    ok_bound, ceil_bound = A.stop_reachable(0.20, 9.5)
    assert ok_bound is False and abs(ceil_bound - 4.17) < 0.01
    ok_held, ceil_held = A.stop_reachable(0.055, 5.63)
    assert ok_held is True and ceil_held > 9.5
    gap = A.liq_gap_pct(0.055, 5.63)
    assert gap is not None and abs(gap) > 0.10


def test_the_row_publishes_the_held_measurement_beside_the_bound():
    src = open(A.__file__).read()
    for k in ("mmf_held", "liq_gap_held_pct", "stop_reachable_held",
              "stop_dead_above_held", "leverage_now"):
        assert f'"{k}"' in src, k
