"""Order construction, the reduce-only rule, and the monotone-stop invariant."""
import pytest

from dt_helpers import SYMS
from downtrend_bot.config import ExecutionConfig, StrategyConfig
from downtrend_bot.execution import (Plan, acceptable_fill, breakeven_stop,
                                     build_plan, choose_entry_order,
                                     next_client_order_id, should_time_stop,
                                     side_to_action, slippage_bps, spread_bps,
                                     trail_stop)
from downtrend_bot.models import (OrderIntent, Position, Regime, ScoreCard,
                                  Signal, Sizing)
from downtrend_bot.synthetic import make_market


def sig(side="short", entry=100.0, stop=None):
    # The stop must sit on the correct side of the entry: ABOVE for a short,
    # BELOW for a long. Getting this wrong in a FIXTURE is how a wrong-sided
    # stop reaches production looking tested.
    if stop is None:
        stop = entry + 3.0 if side == "short" else entry - 3.0
    r = abs(entry - stop)
    sgn = -1.0 if side == "short" else 1.0
    return Signal(symbol=SYMS[0], side=side, strategy="s", setup="breakdown",
                  timeframe="1h", candle_ts=1,
                  score=ScoreCard(regime=25, trend=20, breakdown=20,
                                  momentum=10, volume=5),
                  entry=entry, stop=stop,
                  targets=[entry + sgn * 1.5 * r, entry + sgn * 2.5 * r],
                  atr=2.0, reward_risk=2.5, regime=Regime.BEARISH)


def plan(side="short", **kw):
    return build_plan(signal=sig(side), sizing=Sizing(True, quantity=1.0,
                                                      notional=100.0,
                                                      leverage=1.0),
                      market=make_market(SYMS[0]), cfg=ExecutionConfig(),
                      strat=StrategyConfig(), **kw)


# ------------------------------------------------------------ conversion ---
def test_side_conversion_is_correct_in_all_four_directions():
    assert side_to_action("short") == "sell"
    assert side_to_action("long") == "buy"
    assert side_to_action("short", closing=True) == "buy"
    assert side_to_action("long", closing=True) == "sell"


def test_an_unknown_side_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        side_to_action("flat")


def test_slippage_is_positive_when_worse_for_both_sides():
    assert slippage_bps(100.0, 99.0, "short") > 0     # sold lower = worse
    assert slippage_bps(100.0, 101.0, "long") > 0     # bought higher = worse
    assert slippage_bps(100.0, 101.0, "short") < 0
    assert slippage_bps(100.0, 99.0, "long") < 0


def test_a_fill_past_the_slippage_cap_is_unacceptable():
    cfg = ExecutionConfig(max_slippage_bps=10.0)
    ok, s = acceptable_fill(100.0, 99.0, "short", cfg)
    assert not ok and s == pytest.approx(100.0)


def test_client_order_ids_are_unique():
    ids = {next_client_order_id() for _ in range(200)}
    assert len(ids) == 200


# ------------------------------------------------------------ order type ---
def test_an_unknown_spread_never_yields_a_marketable_order():
    otype, post_only, cap, notes = choose_entry_order(ExecutionConfig(), None,
                                                      urgent=True)
    assert post_only and cap is None and "unknown" in notes[0]


def test_a_wide_spread_never_yields_a_marketable_order():
    otype, post_only, cap, _n = choose_entry_order(ExecutionConfig(
        max_spread_bps=8.0), 40.0, urgent=True)
    assert post_only and cap is None


def test_no_path_ever_produces_an_unrestricted_market_order():
    """Spec 1: never emit one. The most aggressive thing available is a
    marketable limit with an explicit slippage cap."""
    cfg = ExecutionConfig()
    for spread in (None, 0.5, 4.0, 7.9, 8.1, 100.0):
        for urgent in (True, False):
            otype, _po, cap, _n = choose_entry_order(cfg, spread, urgent)
            assert otype == "limit", (spread, urgent)
            if not _po:
                assert cap is not None, "a crossing order with no cap"


def test_spread_bps_is_none_when_unmeasurable():
    assert spread_bps(None, 100.0) is None
    assert spread_bps(0.0, 100.0) is None


# ------------------------------------------------------------------ plan ---
def test_every_exit_in_a_plan_is_reduce_only():
    p = plan()
    assert not p.entry.reduce_only
    assert p.stop.reduce_only
    assert all(t.reduce_only for t in p.targets)


def test_the_exit_actions_are_the_opposite_of_the_entry():
    p = plan("short")
    assert p.entry.action == "sell"
    assert p.stop.action == "buy"
    assert all(t.action == "buy" for t in p.targets)
    q = plan("long")
    assert q.entry.action == "buy" and q.stop.action == "sell"


def test_a_short_stop_is_above_the_entry_and_targets_below():
    p = plan("short")
    assert p.stop.trigger_price > p.entry.price
    assert all(t.trigger_price < p.entry.price for t in p.targets)


def test_a_long_stop_is_below_the_entry_and_targets_above():
    p = plan("long")
    assert p.stop.trigger_price < p.entry.price
    assert all(t.trigger_price > p.entry.price for t in p.targets)


def test_a_missing_native_stop_is_flagged_loudly():
    p = plan(adapter_supports_stop=False)
    assert any("NO native stop" in n for n in p.notes)


def test_a_refused_sizing_can_never_become_a_plan():
    with pytest.raises(ValueError):
        build_plan(signal=sig(), sizing=Sizing(False, reason="refused"),
                   market=make_market(SYMS[0]), cfg=ExecutionConfig(),
                   strat=StrategyConfig())


def test_the_stop_carries_its_r_unit_so_exits_can_be_graded():
    p = plan()
    assert p.stop.detail["r_unit"] == pytest.approx(3.0)


# ----------------------------------------------------------- the trail -----
def test_a_short_trail_can_only_tighten():
    """THE stop invariant. A short's stop is ABOVE it, so a HIGHER stop is a
    LOOSER one -- and widening a stop to avoid a loss is the single thing the
    safety requirements forbid outright."""
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=103.0)
    assert trail_stop(pos, 93.0, 2.0) < 103.0          # falls: tightens
    assert trail_stop(pos, 120.0, 2.0) == 103.0        # rallies: does NOT widen


def test_a_long_trail_can_only_tighten():
    pos = Position(symbol=SYMS[0], side="long", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=97.0)
    assert trail_stop(pos, 107.0, 2.0) > 97.0
    assert trail_stop(pos, 80.0, 2.0) == 97.0


def test_a_dark_ema_leaves_the_stop_exactly_where_it_was():
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=103.0)
    assert trail_stop(pos, None, 2.0) == 103.0
    assert trail_stop(pos, 93.0, 0.0) == 103.0


def test_breakeven_includes_round_trip_fees():
    """A runner stopped at exactly breakeven is a small LOSS after fees. The
    breakeven stop has to clear our own costs or it manufactures one."""
    cfg = ExecutionConfig(taker_fee=0.001)
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=103.0)
    be = breakeven_stop(pos, cfg)
    assert be < 100.0
    long_pos = Position(symbol=SYMS[0], side="long", quantity=1.0,
                        entry_price=100.0, opened_ts=0.0, stop_price=97.0)
    assert breakeven_stop(long_pos, cfg) > 100.0


def test_the_time_stop_fires_at_the_configured_horizon():
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=103.0)
    assert not should_time_stop(pos, 4.0 * 86400, 5.0)
    assert should_time_stop(pos, 5.0 * 86400, 5.0)


def test_a_wrong_sided_stop_is_refused_before_it_becomes_an_order():
    """The guard that this test file's own first fixture would have needed.
    A short whose stop sits BELOW its entry is stopped on the fill, and
    `risk = abs(entry - stop)` is positive for it, so nothing upstream
    complains."""
    bad_short = sig("short", entry=100.0, stop=97.0)
    with pytest.raises(ValueError, match="not above the entry"):
        build_plan(signal=bad_short, sizing=Sizing(True, quantity=1.0),
                   market=make_market(SYMS[0]), cfg=ExecutionConfig(),
                   strat=StrategyConfig())
    bad_long = sig("long", entry=100.0, stop=103.0)
    with pytest.raises(ValueError, match="not below the entry"):
        build_plan(signal=bad_long, sizing=Sizing(True, quantity=1.0),
                   market=make_market(SYMS[0]), cfg=ExecutionConfig(),
                   strat=StrategyConfig())
