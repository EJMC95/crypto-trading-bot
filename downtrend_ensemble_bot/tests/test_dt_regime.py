"""Regime detection, hysteresis, and what a regime change may and may not do."""
import pytest

from dt_helpers import falling, flat, rising
from downtrend_bot import regime as R
from downtrend_bot.config import RegimeConfig, StrategyConfig
from downtrend_bot.models import Regime


def inputs(bars, **kw):
    return R.RegimeInputs(btc_4h=bars, **kw)


def test_a_falling_tape_is_classified_bearish():
    eng = R.MarketRegimeEngine(RegimeConfig())
    v = eng.update(inputs(falling(400), breadth_20=0.2))
    for _ in range(4):
        v = eng.update(inputs(falling(400), breadth_20=0.2))
    assert v.regime is Regime.BEARISH, v.reasons


def test_a_rising_tape_is_not_bearish():
    eng = R.MarketRegimeEngine(RegimeConfig())
    for _ in range(5):
        v = eng.update(inputs(rising(400), breadth_20=0.9))
    assert v.regime is not Regime.BEARISH


def test_short_history_is_data_unreliable_not_neutral():
    """The distinction that matters: 'I do not know' must never render as
    'nothing is happening'. NEUTRAL still permits half-size entries."""
    eng = R.MarketRegimeEngine(RegimeConfig())
    v = eng.update(inputs(falling(50)))
    assert v.regime is Regime.DATA_UNRELIABLE
    assert not v.tradable


def test_data_ok_false_short_circuits_everything():
    eng = R.MarketRegimeEngine(RegimeConfig())
    v = eng.update(R.RegimeInputs(btc_4h=falling(400), data_ok=False,
                                  data_problems=["feed down"]))
    assert v.regime is Regime.DATA_UNRELIABLE and "feed down" in v.reasons


def test_restrictive_states_arm_immediately_and_clear_slowly():
    """The asymmetry IS the hysteresis. Danger is believed on the first bar;
    safety has to be confirmed. A symmetric filter would delay every crouch by
    exactly as long as it delays every recovery, and only one of those is
    expensive."""
    cfg = RegimeConfig(minimum_regime_confirmation_candles=3)
    eng = R.MarketRegimeEngine(cfg)
    for _ in range(4):
        eng.update(inputs(falling(400), breadth_20=0.3))
    assert eng.state is Regime.BEARISH
    # one panic bar is enough to arm
    v = eng.update(inputs(falling(400), breadth_20=0.0))
    assert v.regime is Regime.PANIC
    # ...and one calm bar is NOT enough to clear
    v = eng.update(inputs(falling(400), breadth_20=0.3))
    assert v.regime is Regime.PANIC, "PANIC cleared on a single bar"
    v = eng.update(inputs(falling(400), breadth_20=0.3))
    assert v.regime is Regime.PANIC
    v = eng.update(inputs(falling(400), breadth_20=0.3))
    assert v.regime is Regime.BEARISH


def test_bearish_disables_new_longs_and_permits_shorts():
    cfg = RegimeConfig()
    assert R.risk_multiplier(cfg, Regime.BEARISH, "long") == 0.0
    assert R.risk_multiplier(cfg, Regime.BEARISH, "short") > 0.0


def test_bullish_disables_new_shorts():
    cfg = RegimeConfig()
    assert R.risk_multiplier(cfg, Regime.BULLISH, "short") == 0.0
    assert R.risk_multiplier(cfg, Regime.BULLISH, "long") > 0.0


def test_panic_and_data_unreliable_forbid_both_sides():
    cfg = RegimeConfig()
    for reg in (Regime.PANIC, Regime.DATA_UNRELIABLE):
        for side in ("long", "short"):
            assert R.risk_multiplier(cfg, reg, side) == 0.0, (reg, side)


def test_high_volatility_reduces_risk_without_forbidding_it():
    cfg = RegimeConfig()
    m = R.risk_multiplier(cfg, Regime.HIGH_VOLATILITY, "short")
    assert 0.0 < m < R.risk_multiplier(cfg, Regime.BEARISH, "short")


def test_neutral_is_reduced_risk_not_zero():
    assert 0.0 < R.risk_multiplier(RegimeConfig(), Regime.NEUTRAL,
                                   "short") < 1.0


def test_a_transition_records_what_it_affected():
    eng = R.MarketRegimeEngine(RegimeConfig(minimum_regime_confirmation_candles=1))
    eng.update(inputs(falling(400), breadth_20=0.3), 100.0,
               symbols=["BTC/USDT:USDT"], open_positions=["ETH/USDT:USDT"])
    eng.update(inputs(rising(400), breadth_20=0.9), 200.0,
               symbols=["BTC/USDT:USDT"], open_positions=["ETH/USDT:USDT"])
    assert eng.transitions, "no transition was recorded at all"
    t = eng.transitions[-1].as_dict()
    for key in ("previous", "new", "reasons", "ts", "open_positions",
                "entries_disabled", "risk_reduced"):
        assert key in t


def test_btc_short_needs_extra_confirmation():
    """The benchmark IS the regime signal, so shorting it on the same bar that
    declares the regime is circular. It needs its own extra candles."""
    cfg = RegimeConfig(minimum_regime_confirmation_candles=1,
                       btc_extra_confirmation_candles=3)
    eng = R.MarketRegimeEngine(cfg)
    eng.update(inputs(falling(400), breadth_20=0.2))
    assert eng.state is Regime.BEARISH
    assert not eng.btc_short_confirmed()
    for _ in range(3):
        eng.update(inputs(falling(400), breadth_20=0.2))
    assert eng.btc_short_confirmed()


def test_breadth_is_none_when_unmeasurable_never_zero():
    """0.0 breadth means EVERY asset is below its EMA -- a crash. It must
    never be what 'we could not compute it' renders as."""
    assert R.breadth({}) is None
    assert R.breadth({"a": [1.0] * 3}) is None          # too few gradeable
    got = R.breadth({"a": [1.0] * 60, "b": [1.0] * 60})
    assert got is not None


def test_symbol_bearish_requires_every_condition():
    st = StrategyConfig()
    ok, fails = R.symbol_bearish(rising(400, tf="4h"), 20.0, 20, st)
    assert not ok and fails
    ok, fails = R.symbol_bearish(falling(400, tf="4h"), 20.0, 20, st)
    assert ok or fails, "must always explain itself"


def test_symbol_bearish_reaches_the_configured_ema_lengths():
    """Spec 12 sweeps EMA lengths. If the lengths did not reach this function
    the sweep would be measuring nothing -- so a shorter slow EMA must be able
    to change the verdict's REASON, not merely its speed."""
    st_long = StrategyConfig(ema_mid=50, ema_slow=200)
    st_short = StrategyConfig(ema_mid=5, ema_slow=10)
    bars = flat(400, tf="4h")
    _ok, f_long = R.symbol_bearish(bars, 20.0, 20, st_long)
    _ok, f_short = R.symbol_bearish(bars, 20.0, 20, st_short)
    assert any("EMA50" in x or "EMA200" in x for x in f_long) or not f_long
    assert not any("EMA50" in x for x in f_short), \
        "the 50/200 lengths are still hard-coded somewhere"


def test_incomplete_history_is_refused_at_the_configured_length():
    st = StrategyConfig(ema_slow=200)
    ok, fails = R.symbol_bearish(falling(100, tf="4h"), 20.0, 20, st)
    assert not ok and "need 210" in fails[0]
