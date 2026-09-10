"""Our vocabulary -> Lighter's. One conversion, and the SDK constants exist."""
import pytest

from lighter_bots import execution as ex
from lighter_bots.config import ExecutionConfig
from lighter_bots.models import (OrderIntent, RiskDecision, ScoreBreakdown,
                                 Signal)
from lighter_bots.lighter_adapter import build_capability_report


def _sig(side="long", entry=100.0, stop=98.0):
    return Signal(symbol="BTC", side=side, strategy="ensemble.trend",
                  timeframe="1h", candle_ts=1_700_000_000, setup="trend",
                  score=ScoreBreakdown(regime=25, trend=20, structure=20,
                                       momentum=10, volume=5),
                  entry=entry, stop=stop,
                  targets=[entry + 2.4, entry + 4.0] if side == "long"
                  else [entry - 2.4, entry - 4.0],
                  atr=1.0, reward_risk=2.0)


def _dec(qty=0.01):
    return RiskDecision(ok=True, quantity=qty, notional=qty * 100,
                        leverage=5.0, liquidation_price=80.0,
                        stop_to_liq_atr=18.0, rounded=True)


def test_side_conversion_happens_in_exactly_one_place():
    assert ex.side_to_is_ask("long") is False
    assert ex.side_to_is_ask("short") is True
    with pytest.raises(ValueError):
        ex.side_to_is_ask("buy")


def test_exit_side_is_the_opposite():
    assert ex.exit_side("long") == "short"
    assert ex.exit_side("short") == "long"


def test_sdk_exposes_every_constant_we_map_to():
    """Mapped BY NAME, so an SDK renumber surfaces here rather than as a
    wrong order at runtime."""
    import lighter
    signer = lighter.SignerClient
    for name in ex.ORDER_TYPE.values():
        assert hasattr(signer, name), f"SDK lost {name}"
    for name in ex.TIME_IN_FORCE.values():
        assert hasattr(signer, name), f"SDK lost {name}"


def test_capability_report_finds_the_protective_primitives():
    r = build_capability_report("https://example.invalid", 304)
    for cap in ("order_create", "order_cancel", "stop_loss_orders",
                "take_profit_orders", "reduce_only_exits", "post_only",
                "ioc", "good_til_time"):
        assert r.supports(cap), f"{cap} reported unsupported"
    assert not r.problems


def test_every_exit_leg_is_reduce_only(registry):
    plan = ex.build_plan(signal=_sig(), decision=_dec(), registry=registry,
                         cfg=ExecutionConfig(), spread=3.0)
    assert plan.entry.reduce_only is False
    assert plan.stop.reduce_only is True
    assert all(t.reduce_only for t in plan.targets)


def test_exit_legs_face_the_opposite_way_to_the_entry(registry):
    for side in ("long", "short"):
        plan = ex.build_plan(signal=_sig(side), decision=_dec(),
                             registry=registry, cfg=ExecutionConfig(),
                             spread=3.0)
        assert plan.entry.side == side
        assert plan.stop.side == ex.exit_side(side)
        assert all(t.side == ex.exit_side(side) for t in plan.targets)


def test_stop_rounds_away_from_the_position_never_into_it(registry):
    # BTC tick is 0.1. A long's stop must not round UP (tighter).
    s = _sig("long", entry=77000.0, stop=76999.97)
    plan = ex.build_plan(signal=s, decision=_dec(), registry=registry,
                         cfg=ExecutionConfig(), spread=3.0)
    assert plan.stop.trigger_price <= s.stop


def test_prices_and_quantities_are_rounded_to_venue_precision(registry):
    plan = ex.build_plan(signal=_sig("long", 77000.123456, 76000.987654),
                         decision=_dec(0.0123456789), registry=registry,
                         cfg=ExecutionConfig(), spread=3.0)
    assert abs(plan.entry.price * 10 - round(plan.entry.price * 10)) < 1e-9
    assert plan.entry.quantity == 0.01234


def test_a_refused_trade_cannot_produce_a_plan(registry):
    with pytest.raises(ValueError):
        ex.build_plan(signal=_sig(), decision=RiskDecision(False, "no"),
                      registry=registry, cfg=ExecutionConfig(), spread=3.0)


def test_unknown_spread_never_yields_a_market_order():
    cfg = ExecutionConfig()
    ot, tif, notes = ex.choose_entry_order(cfg, spread=None, urgent=True)
    assert (ot, tif) == ("limit", "post_only")
    assert any("never market" in n for n in notes)


def test_a_wide_spread_refuses_urgency():
    cfg = ExecutionConfig(max_spread_bps=10.0)
    ot, tif, _n = ex.choose_entry_order(cfg, spread=40.0, urgent=True)
    assert (ot, tif) == ("limit", "post_only")


def test_urgency_inside_the_spread_limit_uses_ioc():
    cfg = ExecutionConfig(max_spread_bps=10.0, use_ioc_when_necessary=True)
    assert ex.choose_entry_order(cfg, 3.0, urgent=True)[1] == "ioc"


def test_slippage_is_positive_when_worse_for_both_sides():
    assert ex.slippage_bps(100.0, 100.1, "long") > 0
    assert ex.slippage_bps(100.0, 99.9, "short") > 0
    assert ex.slippage_bps(100.0, 99.9, "long") < 0


def test_client_order_indices_are_unique():
    seen = {ex.next_client_order_index() for _ in range(500)}
    assert len(seen) == 500


def test_grouping_is_recorded_in_the_plan(registry):
    a = ex.build_plan(signal=_sig(), decision=_dec(), registry=registry,
                      cfg=ExecutionConfig(), spread=3.0,
                      supports_grouping=True)
    b = ex.build_plan(signal=_sig(), decision=_dec(), registry=registry,
                      cfg=ExecutionConfig(), spread=3.0,
                      supports_grouping=False)
    assert a.grouped and not b.grouped
    assert any("grouped" in n for n in a.notes)
    assert any("immediately after fill" in n for n in b.notes)
