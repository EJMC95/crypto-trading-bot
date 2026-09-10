"""Regime classification, hysteresis, and the permission table."""
import pytest

from lighter_bots.config import RegimeConfig
from lighter_bots.models import Regime
from lighter_bots.regime import (MarketRegimeEngine, RegimeInputs, breadth,
                                 atr_percentile_now, risk_multiplier)
from conftest import ramp


def _bull(n=260):
    return ramp(n, drift=0.004)


def _bear(n=260):
    return ramp(n, drift=-0.004)


def test_bullish_needs_trend_and_breadth():
    e = MarketRegimeEngine(RegimeConfig(minimum_confirmation_candles=1))
    cand, _r = e.classify(RegimeInputs(btc_4h=_bull(), btc_1h=_bull(),
                                       breadth_up_frac=0.8))
    assert cand is Regime.BULLISH


def test_bearish_needs_lower_highs_and_lower_lows_too():
    e = MarketRegimeEngine(RegimeConfig(minimum_confirmation_candles=1))
    cand, _r = e.classify(RegimeInputs(btc_4h=_bear(), btc_1h=_bear(),
                                       breadth_up_frac=0.2))
    assert cand is Regime.BEARISH


def test_no_btc_history_is_DATA_UNRELIABLE_not_neutral():
    e = MarketRegimeEngine(RegimeConfig())
    cand, reasons = e.classify(RegimeInputs(btc_4h=[], btc_1h=[]))
    assert cand is Regime.DATA_UNRELIABLE and reasons


def test_data_marked_unreliable_short_circuits_everything():
    e = MarketRegimeEngine(RegimeConfig())
    cand, _r = e.classify(RegimeInputs(btc_4h=_bull(), btc_1h=_bull(),
                                       data_ok=False,
                                       data_problems=["stale candles"]))
    assert cand is Regime.DATA_UNRELIABLE


def test_panic_on_a_liquidation_burst():
    e = MarketRegimeEngine(RegimeConfig())
    cand, _r = e.classify(RegimeInputs(btc_4h=_bull(), btc_1h=_bull(),
                                       breadth_up_frac=0.6,
                                       liquidation_burst=True))
    assert cand is Regime.PANIC


def test_panic_on_a_severe_spread():
    e = MarketRegimeEngine(RegimeConfig())
    cand, _r = e.classify(RegimeInputs(btc_4h=_bull(), btc_1h=_bull(),
                                       breadth_up_frac=0.6, spread_bps=120.0))
    assert cand is Regime.PANIC


def test_high_volatility_on_an_extreme_atr_percentile():
    e = MarketRegimeEngine(RegimeConfig(high_volatility_atr_percentile=90))
    cand, _r = e.classify(RegimeInputs(btc_4h=_bull(), btc_1h=_bull(),
                                       breadth_up_frac=0.6,
                                       atr_percentile=95.0))
    assert cand is Regime.HIGH_VOLATILITY


def test_hysteresis_delays_a_RELAXING_transition():
    e = MarketRegimeEngine(RegimeConfig(minimum_confirmation_candles=3))
    inp = RegimeInputs(btc_4h=_bull(), btc_1h=_bull(), breadth_up_frac=0.8)
    assert e.update(inp).regime is Regime.NEUTRAL, "1 of 3 confirmations"
    assert e.update(inp).regime is Regime.NEUTRAL, "2 of 3"
    assert e.update(inp).regime is Regime.BULLISH, "3 of 3"


def test_restrictive_states_arm_IMMEDIATELY():
    e = MarketRegimeEngine(RegimeConfig(minimum_confirmation_candles=5))
    bull = RegimeInputs(btc_4h=_bull(), btc_1h=_bull(), breadth_up_frac=0.8)
    for _ in range(5):
        e.update(bull)
    assert e.state is Regime.BULLISH
    panic = RegimeInputs(btc_4h=_bull(), btc_1h=_bull(), breadth_up_frac=0.8,
                         liquidation_burst=True)
    assert e.update(panic).regime is Regime.PANIC, "no delay on the way IN"


def test_leaving_a_restrictive_state_still_needs_confirmations():
    e = MarketRegimeEngine(RegimeConfig(minimum_confirmation_candles=3))
    panic = RegimeInputs(btc_4h=_bull(), btc_1h=_bull(), breadth_up_frac=0.8,
                         liquidation_burst=True)
    e.update(panic)
    assert e.state is Regime.PANIC
    calm = RegimeInputs(btc_4h=_bull(), btc_1h=_bull(), breadth_up_frac=0.8)
    assert e.update(calm).regime is Regime.PANIC
    assert e.update(calm).regime is Regime.PANIC
    assert e.update(calm).regime is Regime.BULLISH


def test_transitions_are_recorded():
    e = MarketRegimeEngine(RegimeConfig(minimum_confirmation_candles=1))
    e.update(RegimeInputs(btc_4h=_bull(), btc_1h=_bull(),
                          breadth_up_frac=0.8), ts=1.0)
    assert e.history and e.history[-1][2] is Regime.BULLISH


@pytest.mark.parametrize("regime,side,want", [
    (Regime.PANIC, "long", 0.0), (Regime.PANIC, "short", 0.0),
    (Regime.DATA_UNRELIABLE, "short", 0.0),
    (Regime.BULLISH, "long", 1.0), (Regime.BULLISH, "short", 0.25),
    (Regime.BEARISH, "short", 1.0), (Regime.BEARISH, "long", 0.25),
    (Regime.NEUTRAL, "long", 0.75), (Regime.HIGH_VOLATILITY, "short", 0.50),
])
def test_permission_table(regime, side, want):
    assert risk_multiplier(RegimeConfig(), regime, side) == pytest.approx(want)


def test_panic_multiplier_is_exactly_zero_for_both_sides():
    for side in ("long", "short"):
        assert risk_multiplier(RegimeConfig(), Regime.PANIC, side) == 0.0


def test_breadth_is_none_when_too_few_markets_can_be_graded():
    assert breadth({"A": [1.0] * 10}) is None, \
        "an unmeasurable breadth must not read as 0.0, which looks like a crash"


def test_breadth_counts_markets_above_their_own_ema():
    up = [100.0 * (1.01 ** i) for i in range(80)]
    down = list(reversed(up))
    got = breadth({f"U{i}": up for i in range(6)}
                  | {f"D{i}": down for i in range(2)}, n=50)
    assert got == pytest.approx(6 / 8)


def test_atr_percentile_is_none_on_a_short_series():
    assert atr_percentile_now(ramp(20)) is None
