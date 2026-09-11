"""Sizing, caps, lockouts, and the arithmetic that must never round the wrong way."""
import pytest

from dt_helpers import SYMS
from downtrend_bot.config import ExecutionConfig, RiskConfig, StrategyConfig
from downtrend_bot.models import Regime, ScoreCard, Signal
from downtrend_bot.risk import (Account, Exposure, correlation_multiplier,
                                liquidity_multiplier, round_step, round_tick,
                                size_position, volatility_multiplier)
from downtrend_bot.synthetic import make_market


def sig(symbol=SYMS[0], side="short", entry=100.0, stop=103.0, atr=2.0):
    return Signal(symbol=symbol, side=side, strategy="downtrend.ensemble",
                  setup="breakdown_retest", timeframe="1h", candle_ts=1,
                  score=ScoreCard(regime=25, trend=20, breakdown=20,
                                  momentum=10, volume=5, derivatives=3,
                                  quality=3),
                  entry=entry, stop=stop,
                  targets=[entry - 1.5 * abs(entry - stop),
                           entry - 2.5 * abs(entry - stop)],
                  atr=atr, reward_risk=2.5, regime=Regime.BEARISH)


def size(**kw):
    base = dict(signal=sig(), market=make_market(SYMS[0]),
                account=Account(equity=10_000.0, free_collateral=10_000.0,
                                margin_used=0.0, max_leverage=1.5),
                exposure=Exposure(), risk_cfg=RiskConfig(),
                exec_cfg=ExecutionConfig(), regime_multiplier=1.0,
                spread_bps=2.0)
    base.update(kw)
    return size_position(**base)


# ------------------------------------------------------------- rounding ----
def test_quantity_always_rounds_down():
    """Rounding a size UP can breach a notional cap that was just checked."""
    assert round_step(0.123456789, 0.001) == pytest.approx(0.123)
    assert round_step(9.9999, 1.0) == pytest.approx(9.0)


def test_a_protective_price_rounds_away_from_the_position():
    """A stop rounded INTO the position is a tighter stop than the one the
    risk calculation used -- the position is then larger than intended."""
    # a short's stop is ABOVE: round UP
    assert round_tick(103.004, 0.01, side="short", protective=True) >= 103.004
    # a long's stop is BELOW: round DOWN
    assert round_tick(97.006, 0.01, side="long", protective=True) <= 97.006


def test_a_non_protective_price_rounds_conservatively_too():
    got = round_tick(100.006, 0.01, side="short", protective=False)
    assert abs(got - 100.006) <= 0.01


# -------------------------------------------------------------- refusals ---
def test_every_refusal_carries_a_reason():
    for kw in ({"regime_multiplier": 0.0},
               {"account": Account(equity=0.0, free_collateral=0.0)},
               {"exposure": Exposure(open_positions=99)},
               {"spread_bps": 10_000.0}):
        d = size(**kw)
        assert not d.ok and d.reason, kw


def test_lockouts_are_checked_before_any_arithmetic():
    """A daily-loss lockout must refuse regardless of how good the signal is.
    Checking it after sizing means a bug in sizing can bypass a risk limit."""
    d = size(exposure=Exposure(day_pnl=-200.0), risk_cfg=RiskConfig(
        max_daily_loss=0.015))
    assert not d.ok and "daily loss" in d.reason


def test_weekly_lockout_refuses():
    d = size(exposure=Exposure(week_pnl=-500.0))
    assert not d.ok and "weekly" in d.reason


def test_consecutive_losses_lock_out():
    d = size(exposure=Exposure(consecutive_losses=4),
             risk_cfg=RiskConfig(max_consecutive_losses=4))
    assert not d.ok and "consecutive" in d.reason


def test_position_count_cap_refuses():
    d = size(exposure=Exposure(open_positions=3),
             risk_cfg=RiskConfig(max_concurrent_positions=3))
    assert not d.ok


def test_correlated_position_cap_refuses():
    d = size(correlated_group_count=2,
             risk_cfg=RiskConfig(max_correlated_positions=2))
    assert not d.ok and "correlated" in d.reason


def test_margin_utilisation_cap_refuses():
    d = size(account=Account(equity=10_000.0, free_collateral=1_000.0,
                             margin_used=9_000.0, max_leverage=1.5))
    assert not d.ok and "margin" in d.reason


def test_an_untradable_market_is_refused_not_defaulted():
    import dataclasses
    m = dataclasses.replace(make_market(SYMS[0]), tick_size=0.0)
    assert not m.tradable and "tick_size" in m.missing()
    d = size(market=m)
    assert not d.ok and "not tradable" in d.reason


# ---------------------------------------------------------------- limits ---
def test_risk_per_trade_is_respected():
    d = size()
    assert d.ok, d.reason
    risk_dollars = d.quantity * abs(100.0 - 103.0)
    assert risk_dollars <= 10_000.0 * RiskConfig().risk_per_trade * 1.001


def test_leverage_never_exceeds_the_configured_cap():
    d = size(risk_cfg=RiskConfig(max_leverage=1.5, risk_per_trade=0.005,
                                 max_portfolio_risk=0.02))
    if d.ok:
        assert d.leverage <= 1.5 + 1e-9


def test_the_portfolio_risk_budget_binds():
    """Two trades at full size must not both fit inside a budget of one."""
    cfg = RiskConfig(risk_per_trade=0.0025, max_portfolio_risk=0.0025)
    first = size(risk_cfg=cfg)
    assert first.ok
    used = Exposure(open_risk=first.quantity * 3.0, open_positions=1)
    second = size(risk_cfg=cfg, exposure=used)
    assert not second.ok or second.quantity < first.quantity


def test_per_symbol_notional_cap_binds():
    cfg = RiskConfig(max_notional_per_symbol_pct=0.001)
    d = size(risk_cfg=cfg)
    assert (not d.ok) or d.notional <= 10_000.0 * 0.001 * 1.001


def test_aggregate_short_notional_cap_binds():
    cfg = RiskConfig(max_aggregate_short_notional_pct=0.01)
    d = size(risk_cfg=cfg, exposure=Exposure(short_notional=99.0))
    assert (not d.ok) or (d.notional + 99.0) <= 10_000.0 * 0.01 * 1.001


# ----------------------------------------------------------- multipliers ---
def test_higher_volatility_sizes_smaller():
    a = volatility_multiplier(0.01)
    b = volatility_multiplier(0.08)
    assert b < a


def test_an_unknown_spread_halves_size_rather_than_assuming_the_best():
    assert liquidity_multiplier(None, 8.0) == pytest.approx(0.5)


def test_a_spread_over_the_limit_refuses_outright():
    assert liquidity_multiplier(20.0, 8.0) == 0.0


def test_each_correlated_position_reduces_the_next():
    a = correlation_multiplier(0, 0.5)
    b = correlation_multiplier(1, 0.5)
    assert b < a


def test_a_regime_multiplier_of_zero_refuses_rather_than_sizing_zero():
    d = size(regime_multiplier=0.0)
    assert not d.ok, "a zero-size 'success' is a refusal wearing a fill"


def test_health_and_regime_multipliers_compound():
    full = size(regime_multiplier=1.0, health_multiplier=1.0)
    half = size(regime_multiplier=0.5, health_multiplier=0.5)
    assert full.ok and half.ok
    assert half.quantity < full.quantity


def test_a_degenerate_stop_never_produces_an_infinite_size():
    d = size(signal=sig(entry=100.0, stop=100.0))
    assert not d.ok
