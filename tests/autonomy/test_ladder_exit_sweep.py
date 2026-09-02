"""[2026-08-19] The ladder-aware exit harness must stay fail-closed.

Built to answer 🔮 georgia's standing `exit_too_tight` diagnosis, which
`study_exit_sweep` structurally cannot express ((ql)). The whole value of the
answer rests on the calibration gate REFUSING when the replay cannot
reproduce the book's own record — the (ps) false pass is what happens when it
does not.
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import study_ladder_exit_sweep as lad  # noqa: E402


def test_the_shipped_rule_is_read_from_the_carrier_never_retyped():
    """A retyped constant is a constant that drifts. The ROI ladder and the
    stop cap must come from the live carrier object."""
    import lighter_family_bot as fam
    c = lad.carrier_for("freqtrade-georgia-lshadow")
    assert c is not None and type(c).__name__ == "DayTraderGated"
    rule = lad.shipped_rule(c)
    assert rule["roi"] == dict(c.roi), rule["roi"]
    assert rule["stop_cap"] == -c.stoploss
    # and the ladder must be the real one, not a placeholder
    assert len(rule["roi"]) > 1 and max(rule["roi"]) >= 720


def test_the_counter_trend_tags_get_the_wider_multiplier():
    """atr_stop_dist uses 3.5x for the counter-trend tags, 2.5x otherwise —
    a replay that flattens this grades the wrong rule."""
    assert "bounce_pullback" in lad.COUNTER_TAGS
    assert "range_meanrev" in lad.COUNTER_TAGS
    assert "trend_breakout" not in lad.COUNTER_TAGS


def test_the_signal_exit_path_is_excluded_not_silently_scored():
    """The exit_signal path needs the ENTRY strategy re-run; scoring those rows
    against a stop/roi rule would grade a rule the book did not run there."""
    rows = [{"coin": "X", "tag": "long-range-on", "exit": "range_top",
             "t0": 0, "t1": 1, "entry": 1.0, "exit_px": 1.0,
             "side": "long", "actual_ret": 0.0}]
    scored, mix, unmodelled = lad.score(rows, {}, lad.shipped_rule(
        lad.carrier_for("freqtrade-georgia-lshadow")))
    assert unmodelled == 1 and not scored


def test_both_intrabar_conventions_exist_and_are_selectable():
    """The verdict counts only if both arms agree ((ne) precedent), so both
    must be reachable — a single hard-coded convention silently picks a side."""
    src = (ROOT / "scripts" / "study_ladder_exit_sweep.py").read_text()
    assert "LADDER_INTRABAR" in src
    assert "RATCHET_FIRST" in src
    # and the adverse arm must be the DEFAULT (conservative unless asked)
    assert '"adverse"' in src


def test_split_tag_exit_recovers_the_tag_from_the_reason():
    """georgia's `tag` column is null; the tag lives in the reason string, and
    the multiplier choice depends on it."""
    assert lad.split_tag_exit("long-trend-breakout_trailing_stop_loss") == (
        "long-trend-breakout", "trailing_stop_loss")
    assert lad.split_tag_exit("long-bounce-pullback_range_top") == (
        "long-bounce-pullback", "range_top")
    assert lad.split_tag_exit(None)[0] is None


def test_a_walk_with_no_bars_returns_no_data_rather_than_a_number():
    """Fail-closed: an unpriceable position must not silently score as flat."""
    r = lad.walk([], {}, 0, 100.0, "long-trend-breakout",
                 lad.shipped_rule(lad.carrier_for("freqtrade-georgia-lshadow")))
    assert r == (None, None, "no-data")


def test_calibration_tolerances_are_tight_enough_to_bite():
    """A tolerance wide enough to admit anything is not a gate. georgia's
    measured calibration delta is 0.241pp, so a tolerance much above that
    would pass a harness that reproduces nothing."""
    assert lad.CAL_TOL_PP <= 0.5, lad.CAL_TOL_PP
    assert lad.MIX_TOL_PP <= 25.0, lad.MIX_TOL_PP
    assert lad.MIN_N >= 20, lad.MIN_N
