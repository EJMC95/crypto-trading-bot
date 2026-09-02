"""[2026-09-02 (wv)] THE INCUBATOR'S CHAMPION IS INSIDE THE CAGE NOW — and the
breakout clock takes no lever.

(wr) split the breakout trend exit's clock off `taker.max_hold_h` and REFUSED
a lever on the new constant (the only 48->96 widening died to
leave-one-symbol-out). (wq) re-opened `taker.max_hold_h` to lo 24 on the
sighted gate. This pass moved the two remaining bounds the incubator's only
champion-grade genotype (sl -0.02 / gap 25 / hold 24 / tp 0.02, n=189,
lcb +$3.21, halves +$10.27/+$10.79) was out of cage on, put the alleles back
in TAKER_GENES and the tuner's SWEEP_HOLD, and pre-registered the revert.

Mutations that turn these red: any of the three `lo` bounds creeping back;
an allele dropped from a grid; SWEEP_HOLD losing 24; a `taker.brk_max_hold_h`
lever appearing (reach toward a measured artifact); the champion going out
of cage again.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_tuning as ft            # noqa: E402
import lighter_scout_tuner as st     # noqa: E402
import lighter_ticket_taker as tt    # noqa: E402
import strategy_incubator as inc     # noqa: E402

pytestmark = pytest.mark.autonomy

CHAMPION = {"taker.sl": -0.02, "taker.div_gap_pp": 25.0,
            "taker.max_hold_h": 24.0, "taker.tp": 0.02}
PRE_REGISTERED_REVERT = {"taker.max_hold_h": 48.0, "taker.div_gap_pp": 37.5,
                         "taker.tp": 0.03}


def test_the_three_lo_bounds_are_re_decided():
    assert ft.LEVERS["taker.max_hold_h"]["lo"] == 24.0
    assert ft.LEVERS["taker.div_gap_pp"]["lo"] == 25.0
    assert ft.LEVERS["taker.tp"]["lo"] == 0.02
    # and the revert targets are the bounds that stood before — recorded so
    # the revert is a one-line edit with the number already in the tree
    for k, v in PRE_REGISTERED_REVERT.items():
        assert ft.LEVERS[k]["lo"] < v


def test_the_champion_genotype_is_inside_every_cage():
    for k, v in CHAMPION.items():
        assert ft.clamp(k, v) == v, (k, v, ft.LEVERS[k]["lo"], ft.LEVERS[k]["hi"])


def test_no_default_moved_with_the_cage():
    """Expectancy-neutral by construction: only reach changed."""
    assert ft.LEVERS["taker.max_hold_h"]["env_default"] == 48.0
    assert ft.LEVERS["taker.div_gap_pp"]["env_default"] == 62.5
    assert ft.LEVERS["taker.tp"]["env_default"] == 0.04


def test_the_alleles_are_back_in_the_incubators_grids():
    genes = {lever: alleles for lever, alleles in inc.TAKER_GENES.values()}
    assert 25.0 in genes["taker.div_gap_pp"]
    assert 0.02 in genes["taker.tp"]
    assert 24.0 in genes["taker.max_hold_h"]
    # every allele the incubator can breed is a value the cage admits
    for k, vals in genes.items():
        for v in vals:
            assert ft.clamp(k, v) == v, (k, v)


def test_the_tuner_sweep_reaches_the_24h_rung():
    assert 24.0 in st.SWEEP_HOLD
    assert st.SWEEP_HOLD == sorted(st.SWEEP_HOLD)


def test_the_breakout_clock_takes_no_lever():
    """(wr)'s refusal, pinned: no registered lever reaches BRK_MAX_HOLD_H.
    The 48->96 widening died to leave-one-symbol-out, so a cage that reaches
    it is reach toward a measured artifact."""
    assert "taker.brk_max_hold_h" not in ft.LEVERS
    assert not any(attr == "BRK_MAX_HOLD_H" for _lever, attr in tt.TUNABLE)
    assert tt.BRK_MAX_HOLD_H == 48.0


def test_max_hold_h_steers_only_the_divergence_bracket():
    """The split itself is (wr)'s and lives in the taker's selftest; this is
    the consumer-side restatement — the lever and the trend exit are
    different constants."""
    assert ("taker.max_hold_h", "MAX_HOLD_H") in tt.TUNABLE
    old = tt.BULL_MODE
    try:
        tt.BULL_MODE = True
        assert tt.bull_exit("breakoutup")[0][2] == tt.BRK_MAX_HOLD_H
    finally:
        tt.BULL_MODE = old
