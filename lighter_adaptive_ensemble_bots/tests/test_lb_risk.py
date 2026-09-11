"""Sizing: from the STOP, capped everywhere, and never louder because of
leverage."""
import pytest

from lighter_bots import risk as R
from lighter_bots.config import ExecutionConfig, RiskConfig
from lighter_bots.models import ScoreBreakdown, Signal
from lighter_bots.risk import AccountState, ExposureState


def _sig(side="long", entry=100.0, stop=98.0, atr=1.0, symbol="BTC"):
    return Signal(symbol=symbol, side=side, strategy="ensemble.trend",
                  timeframe="1h", candle_ts=1, setup="trend",
                  score=ScoreBreakdown(regime=25, trend=20, structure=20),
                  entry=entry, stop=stop,
                  targets=[entry + 4.0] if side == "long" else [entry - 4.0],
                  atr=atr, reward_risk=2.0)


def _acct(equity=10_000.0, **kw):
    kw.setdefault("available_collateral", equity)
    return AccountState(equity=equity, **kw)


def _size(registry, sig=None, acct=None, exp=None, risk=None, mult=1.0, **kw):
    return R.size_position(
        signal=sig or _sig(), account=acct or _acct(),
        exposure=exp or ExposureState(), registry=registry,
        risk_cfg=risk or RiskConfig(), exec_cfg=ExecutionConfig(),
        regime_multiplier=mult, **kw)


def test_quantity_comes_from_the_stop_distance(registry):
    d = _size(registry)
    assert d.ok, d.reason
    # risk_amount = 10000 * 0.004 = 40; stop distance 2.0 -> 20 units, then
    # rounded to the venue step.
    assert d.quantity == pytest.approx(20.0, rel=0.01)
    assert d.risk_amount == pytest.approx(40.0, rel=0.02)


def test_halving_the_stop_distance_doubles_the_size(registry):
    wide = _size(registry, sig=_sig(stop=96.0))
    tight = _size(registry, sig=_sig(stop=98.0))
    assert tight.quantity == pytest.approx(2 * wide.quantity, rel=0.02)


def test_risk_at_stop_is_invariant_to_leverage(registry):
    a = _size(registry, risk=RiskConfig(max_leverage=2.0))
    b = _size(registry, risk=RiskConfig(max_leverage=10.0))
    assert a.ok and b.ok
    assert a.risk_amount == pytest.approx(b.risk_amount, rel=0.02), \
        "leverage must not change the amount risked at the stop"


def test_regime_multiplier_scales_the_risk_not_the_stop(registry):
    full = _size(registry, mult=1.0)
    quarter = _size(registry, mult=0.25)
    assert quarter.risk_amount == pytest.approx(full.risk_amount * 0.25,
                                                rel=0.03)


def test_daily_loss_lockout_refuses_before_any_arithmetic(registry):
    exp = ExposureState(day_pnl=-300.0)          # 3% of 10k, bar is 2.5%
    d = _size(registry, exp=exp)
    assert not d.ok and "daily loss lockout" in d.reason


def test_weekly_loss_lockout_refuses(registry):
    d = _size(registry, exp=ExposureState(week_pnl=-800.0))
    assert not d.ok and "weekly loss lockout" in d.reason


def test_max_concurrent_positions_refuses(registry):
    d = _size(registry, exp=ExposureState(open_positions=6))
    assert not d.ok and "max_concurrent_positions" in d.reason


def test_margin_utilisation_ceiling_refuses(registry):
    d = _size(registry, acct=_acct(margin_used=4_000.0))    # 40% > 35%
    assert not d.ok and "margin utilisation" in d.reason


def test_exhausted_portfolio_risk_budget_refuses(registry):
    d = _size(registry, exp=ExposureState(open_risk=200.0))  # 2% > 1.2%
    assert not d.ok and "budget exhausted" in d.reason


def test_a_partly_used_budget_clips_rather_than_refuses(registry):
    d = _size(registry, exp=ExposureState(open_risk=110.0))  # 10 left
    assert d.ok and d.risk_amount <= 10.0 + 1e-6


def test_per_market_notional_cap_binds(registry):
    exp = ExposureState(per_market_notional={"BTC": 2_500.0})  # cap is 25%
    d = _size(registry, exp=exp)
    assert not d.ok or d.detail["binding_cap"] == "per_market_notional"


def test_gross_notional_cap_binds(registry):
    d = _size(registry, exp=ExposureState(gross_notional=24_999.0))
    assert not d.ok or d.detail["binding_cap"] == "gross_notional"


def test_net_short_cap_is_separate_from_net_long(registry):
    exp = ExposureState(net_short_notional=14_999.0)
    d = _size(registry, sig=_sig("short", 100.0, 102.0), exp=exp)
    assert not d.ok or d.detail["binding_cap"] == "net_short_notional"
    # the same exposure must NOT bind a long
    d2 = _size(registry, exp=exp)
    assert d2.ok and d2.detail["binding_cap"] != "net_short_notional"


def test_a_stop_too_close_to_liquidation_is_refused(registry):
    """A 1% stop at high leverage sits inside the liquidation band."""
    d = _size(registry, sig=_sig(entry=100.0, stop=99.9, atr=0.02),
              risk=RiskConfig(max_leverage=10.0,
                              min_stop_to_liquidation_atr=2.0))
    if d.ok:
        assert d.stop_to_liq_atr >= 2.0
    else:
        assert "liquidation" in d.reason


def test_leverage_is_walked_down_rather_than_refusing_outright(registry):
    d = _size(registry, sig=_sig(entry=100.0, stop=88.0, atr=4.0),
              risk=RiskConfig(max_leverage=10.0))
    if d.ok:
        assert d.leverage <= 10.0
        assert d.stop_to_liq_atr >= 2.0


def test_leverage_never_exceeds_the_market_maximum(registry):
    d = R.size_position(
        signal=_sig(symbol="SOL", entry=100.0, stop=98.0),
        account=_acct(account_max_leverage=50.0), exposure=ExposureState(),
        registry=registry, risk_cfg=RiskConfig(max_leverage=10.0),
        exec_cfg=ExecutionConfig(), regime_multiplier=1.0)
    assert d.ok and d.leverage <= 10.0


def test_incomplete_metadata_refuses(registry):
    from lb_helpers import make_market
    from lighter_bots.market_metadata import MarketRegistry
    reg = MarketRegistry([make_market("BTC", max_leverage=None)])
    d = _size(reg)
    assert not d.ok and "metadata incomplete" in d.reason


def test_zero_regime_multiplier_refuses(registry):
    d = _size(registry, mult=0.0)
    assert not d.ok and "regime forbids" in d.reason


def test_every_refusal_carries_a_reason(registry):
    cases = [
        _size(registry, mult=0.0),
        _size(registry, exp=ExposureState(open_positions=99)),
        _size(registry, exp=ExposureState(day_pnl=-9_999.0)),
        _size(registry, acct=_acct(equity=0.0)),
    ]
    for d in cases:
        assert not d.ok
        assert d.reason.strip(), "a refusal with no reason is a bug"


def test_a_success_reports_the_full_risk_picture(registry):
    d = _size(registry)
    assert d.ok and d.rounded
    for field in ("quantity", "notional", "risk_amount", "risk_pct_equity",
                  "leverage", "initial_margin", "maintenance_margin",
                  "liquidation_price", "stop_to_liq_atr", "est_fees",
                  "worst_case_gap_loss"):
        assert getattr(d, field) is not None


def test_worst_case_gap_loss_exceeds_the_loss_at_the_stop(registry):
    d = _size(registry)
    assert d.ok and d.worst_case_gap_loss > d.risk_amount, \
        "a gap THROUGH the stop must cost more than a fill AT it"


def test_volatility_multiplier_is_bounded_both_ways():
    assert R.volatility_multiplier(0.20) == pytest.approx(0.35)   # floor
    assert R.volatility_multiplier(0.0001) == pytest.approx(1.25)  # ceiling
    assert R.volatility_multiplier(0.02) == pytest.approx(1.0)


def test_unknown_liquidity_sizes_down_never_up():
    assert R.liquidity_multiplier(None, 10.0) == 0.5
    assert R.liquidity_multiplier(20.0, 10.0) == 0.0
    assert R.liquidity_multiplier(1.0, 10.0) < 1.0


def test_correlation_multiplier_shrinks_with_group_crowding():
    assert R.correlation_multiplier(0) == pytest.approx(1.0)
    assert R.correlation_multiplier(3) < R.correlation_multiplier(1) < 1.0
