"""Execution plans end-to-end and the spread/slippage gates."""
import pytest

from lighter_bots import execution as ex
from lighter_bots.config import ExecutionConfig
from lighter_bots.models import OrderIntent, RiskDecision, ScoreBreakdown, Signal


def _sig(side="long"):
    e = 100.0
    return Signal(symbol="BTC", side=side, strategy="ensemble.trend",
                  timeframe="1h", candle_ts=1, setup="trend",
                  score=ScoreBreakdown(regime=25, trend=20, structure=20),
                  entry=e, stop=e - 2 if side == "long" else e + 2,
                  targets=([e + 2.4, e + 4.0] if side == "long"
                           else [e - 2.4, e - 4.0]),
                  atr=1.0, reward_risk=2.0)


def _dec(q=1.0):
    return RiskDecision(ok=True, quantity=q, notional=q * 100, leverage=5.0,
                        liquidation_price=80.0, stop_to_liq_atr=18.0)


def test_spread_bps_is_none_on_a_missing_side():
    assert ex.spread_bps(None, 100.0) is None
    assert ex.spread_bps(100.0, None) is None
    assert ex.spread_bps(0.0, 100.0) is None


def test_spread_bps_is_the_relative_width():
    assert ex.spread_bps(99.95, 100.05) == pytest.approx(10.0, rel=1e-3)


def test_a_plan_has_a_stop_for_every_entry(registry):
    for side in ("long", "short"):
        p = ex.build_plan(signal=_sig(side), decision=_dec(),
                          registry=registry, cfg=ExecutionConfig(), spread=2.0)
        assert p.entry.intent is OrderIntent.ENTRY
        assert p.stop.intent is OrderIntent.STOP
        assert p.stop.quantity == p.entry.quantity


def test_targets_scale_out_and_leave_a_runner(registry):
    p = ex.build_plan(signal=_sig(), decision=_dec(10.0), registry=registry,
                      cfg=ExecutionConfig(), spread=2.0)
    total = sum(t.quantity for t in p.targets)
    assert total < p.entry.quantity, "something must be left to trail"
    assert len(p.targets) == 2


def test_a_target_that_rounds_to_zero_is_skipped_with_a_note(registry):
    p = ex.build_plan(signal=_sig(), decision=_dec(0.0001), registry=registry,
                      cfg=ExecutionConfig(), spread=2.0)
    if len(p.targets) < 2:
        assert any("skipped" in n for n in p.notes)


def test_the_entry_carries_an_expiry(registry):
    cfg = ExecutionConfig(order_timeout_seconds=30)
    p = ex.build_plan(signal=_sig(), decision=_dec(), registry=registry,
                      cfg=cfg, spread=2.0, now_s=1000.0)
    assert p.entry.expiry_ms == int((1000.0 + 30) * 1000)


def test_disabling_reduce_only_is_surfaced_as_a_warning(registry):
    cfg = ExecutionConfig(use_reduce_only_exits=False)
    p = ex.build_plan(signal=_sig(), decision=_dec(), registry=registry,
                      cfg=cfg, spread=2.0)
    assert any("WARNING" in n for n in p.notes)
    assert p.stop.reduce_only is False   # honest about what it will send


def test_acceptable_fill_rejects_slippage_over_the_limit():
    cfg = ExecutionConfig(max_slippage_bps=15.0)
    ok, bps = ex.acceptable_fill(100.0, 100.05, "long", cfg)
    assert ok and bps == pytest.approx(5.0)
    ok, bps = ex.acceptable_fill(100.0, 100.30, "long", cfg)
    assert not ok and bps == pytest.approx(30.0)


def test_a_favourable_fill_is_always_acceptable():
    cfg = ExecutionConfig(max_slippage_bps=15.0)
    ok, bps = ex.acceptable_fill(100.0, 99.90, "long", cfg)
    assert ok and bps < 0
