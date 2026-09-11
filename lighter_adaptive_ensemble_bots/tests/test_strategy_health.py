"""Health state machine and the overtrading budget."""
import pytest

from lighter_bots.config import HealthConfig, OvertradingConfig
from lighter_bots.models import HealthState, Trade
from lighter_bots.strategy_health import (HealthRegistry, TradeBudget,
                                          strategy_key)

KEY = strategy_key("ensemble.trend", "BTC", "long", "BULLISH")


def _trade(pnl, r=None, ts=0.0):
    return Trade(symbol="BTC", side="long", strategy="ensemble.trend",
                 regime="BULLISH", opened_ts=ts, closed_ts=ts + 3600,
                 entry=100.0, exit=100.0 + pnl, quantity=1.0, pnl=pnl,
                 fees=0.0, funding=0.0,
                 r_multiple=(pnl if r is None else r), reason="test")


def _reg(tmp_path, **kw):
    return HealthRegistry(HealthConfig(**kw), str(tmp_path))


def test_an_unknown_strategy_starts_active(tmp_path):
    assert _reg(tmp_path).get(KEY).state is HealthState.ACTIVE


def test_three_consecutive_losses_throttle(tmp_path):
    reg = _reg(tmp_path)
    for _ in range(3):
        reg.record(KEY, _trade(-1.0))
    assert reg.get(KEY).state is HealthState.THROTTLED


def test_five_consecutive_losses_pause(tmp_path):
    reg = _reg(tmp_path, max_consecutive_losses=4)
    for _ in range(5):
        reg.record(KEY, _trade(-1.0))
    assert reg.get(KEY).state is HealthState.PAUSED


def test_a_paused_strategy_may_not_enter(tmp_path):
    reg = _reg(tmp_path, max_consecutive_losses=4)
    for _ in range(5):
        reg.record(KEY, _trade(-1.0))
    h = reg.get(KEY)
    assert not h.may_enter and h.risk_multiplier(reg.cfg) == 0.0


def test_throttled_cuts_risk_and_raises_the_bars(tmp_path):
    reg = _reg(tmp_path)
    for _ in range(3):
        reg.record(KEY, _trade(-1.0))
    h = reg.get(KEY)
    assert h.risk_multiplier(reg.cfg) == pytest.approx(0.50)
    assert h.score_bump(reg.cfg) == pytest.approx(5.0)
    assert h.rr_bump(reg.cfg) == pytest.approx(0.2)
    assert h.may_enter, "throttled still trades, at half size"


def test_negative_expectancy_over_the_warning_count_throttles(tmp_path):
    reg = _reg(tmp_path, warning_trade_count=20)
    for i in range(20):
        reg.record(KEY, _trade(1.0 if i % 2 else -1.2))
    assert reg.get(KEY).state in (HealthState.THROTTLED, HealthState.PAUSED)


def test_profit_factor_is_none_not_infinity_without_a_loss(tmp_path):
    reg = _reg(tmp_path)
    for _ in range(5):
        reg.record(KEY, _trade(1.0))
    assert reg.get(KEY).stats.profit_factor is None, \
        "an infinite PF from a tiny sample is not a measurement"


def test_paused_never_returns_straight_to_active(tmp_path):
    reg = _reg(tmp_path, max_consecutive_losses=4)
    for _ in range(5):
        reg.record(KEY, _trade(-1.0))
    for _ in range(10):
        reg.record(KEY, _trade(+5.0))
    assert reg.get(KEY).state is HealthState.PAUSED, \
        "winning again is not validation; RECOVERY is the only way back"


def test_recovery_requires_an_explicit_validated_promotion(tmp_path):
    reg = _reg(tmp_path, max_consecutive_losses=4)
    for _ in range(5):
        reg.record(KEY, _trade(-1.0))
    h = reg.promote_to_recovery(KEY, "walk-forward rerun 2026-09-10")
    assert h.state is HealthState.RECOVERY
    assert h.risk_multiplier(reg.cfg) == pytest.approx(0.25)
    assert "walk-forward" in h.reason


def test_recovery_completes_only_after_enough_positive_trades(tmp_path):
    reg = _reg(tmp_path, max_consecutive_losses=4)
    for _ in range(5):
        reg.record(KEY, _trade(-1.0))
    reg.promote_to_recovery(KEY, "validated")
    for _ in range(9):
        reg.record(KEY, _trade(+3.0))
    assert reg.get(KEY).state is HealthState.RECOVERY
    reg.record(KEY, _trade(+3.0))
    assert reg.get(KEY).state is HealthState.ACTIVE


def test_recovery_failure_returns_to_paused(tmp_path):
    reg = _reg(tmp_path, max_consecutive_losses=4)
    for _ in range(5):
        reg.record(KEY, _trade(-1.0))
    reg.promote_to_recovery(KEY, "validated")
    for _ in range(3):
        reg.record(KEY, _trade(-1.0))
    assert reg.get(KEY).state is HealthState.PAUSED


def test_state_survives_a_restart(tmp_path):
    reg = _reg(tmp_path)
    for _ in range(3):
        reg.record(KEY, _trade(-1.0))
    assert HealthRegistry(HealthConfig(), str(tmp_path)).get(KEY).state \
        is HealthState.THROTTLED


def test_keys_separate_by_symbol_side_and_regime(tmp_path):
    reg = _reg(tmp_path)
    for _ in range(3):
        reg.record(KEY, _trade(-1.0))
    other = strategy_key("ensemble.trend", "ETH", "long", "BULLISH")
    assert reg.get(other).state is HealthState.ACTIVE
    short = strategy_key("ensemble.trend", "BTC", "short", "BULLISH")
    assert reg.get(short).state is HealthState.ACTIVE


def test_transitions_are_recorded_with_reasons(tmp_path):
    reg = _reg(tmp_path)
    for _ in range(3):
        reg.record(KEY, _trade(-1.0))
    tr = reg.get(KEY).transitions
    assert tr and tr[-1]["to"] == "THROTTLED" and tr[-1]["reason"]


# ------------------------------------------------------------- budgets -----
def _budget(tmp_path, **kw):
    return TradeBudget(OvertradingConfig(**kw), str(tmp_path))


def test_a_duplicate_signal_id_is_refused(tmp_path):
    b = _budget(tmp_path)
    b.record_entry(symbol="BTC", strategy="s", signal_id="sig-1", now=0.0)
    ok, why = b.may_enter(symbol="BTC", strategy="s", signal_id="sig-1",
                          now=10.0)
    assert not ok and "duplicate" in why


def test_per_market_daily_budget(tmp_path):
    b = _budget(tmp_path, max_entries_per_market_per_day=3,
                cooldown_after_loss_hours=0, cooldown_after_profit_hours=0)
    for i in range(3):
        b.record_entry(symbol="BTC", strategy=f"s{i}", signal_id=f"x{i}",
                       now=float(i))
    ok, why = b.may_enter(symbol="BTC", strategy="s9", signal_id="x9", now=4.0)
    assert not ok and "entries today" in why
    ok, _ = b.may_enter(symbol="ETH", strategy="s9", signal_id="y9", now=4.0)
    assert ok, "another market is unaffected"


def test_portfolio_hourly_budget(tmp_path):
    b = _budget(tmp_path, max_portfolio_entries_per_hour=5,
                max_entries_per_market_per_day=99,
                max_entries_per_strategy_per_day=99)
    for i in range(5):
        b.record_entry(symbol=f"S{i}", strategy="s", signal_id=f"x{i}",
                       now=float(i))
    ok, why = b.may_enter(symbol="ZZ", strategy="s", signal_id="x9", now=10.0)
    assert not ok and "this hour" in why


def test_cooldown_is_keyed_on_the_symbol_not_the_strategy(tmp_path):
    b = _budget(tmp_path, cooldown_after_loss_hours=6)
    b.record_entry(symbol="BTC", strategy="a", signal_id="s1", now=0.0)
    b.record_exit(symbol="BTC", signal_id="s1", pnl=-10.0, now=0.0)
    ok, why = b.may_enter(symbol="BTC", strategy="b", signal_id="s2", now=60.0)
    assert not ok and "cooldown" in why, \
        "a second strategy must not re-enter a market that just proved hostile"


def test_a_loss_cools_down_longer_than_a_win(tmp_path):
    b = _budget(tmp_path, cooldown_after_loss_hours=6,
                cooldown_after_profit_hours=2)
    b.record_exit(symbol="BTC", signal_id="a", pnl=-1.0, now=0.0)
    loss_until = b.cooldown_until["BTC"]
    b.record_exit(symbol="ETH", signal_id="b", pnl=+1.0, now=0.0)
    assert loss_until > b.cooldown_until["ETH"]


def test_breakeven_gets_its_own_cooldown(tmp_path):
    b = _budget(tmp_path, cooldown_after_breakeven_hours=3)
    b.record_exit(symbol="BTC", signal_id="a", pnl=0.0, now=0.0)
    assert b.cooldown_until["BTC"] == pytest.approx(3 * 3600.0)


def test_four_losses_in_a_day_arm_a_global_lockout(tmp_path):
    b = _budget(tmp_path)
    for i in range(4):
        b.record_entry(symbol=f"S{i}", strategy="s", signal_id=f"x{i}",
                       now=float(i))
        b.record_exit(symbol=f"S{i}", signal_id=f"x{i}", pnl=-5.0, now=float(i))
    assert b.global_lockout_until > 0
    ok, why = b.may_enter(symbol="ZZ", strategy="s", signal_id="new", now=100.0)
    assert not ok and "global loss lockout" in why


def test_two_consecutive_losses_cut_risk_a_quarter(tmp_path):
    b = _budget(tmp_path)
    assert b.consecutive_loss_multiplier(now=100.0) == 1.0
    for i in range(2):
        b.record_entry(symbol=f"S{i}", strategy="s", signal_id=f"x{i}",
                       now=float(i))
        b.record_exit(symbol=f"S{i}", signal_id=f"x{i}", pnl=-1.0, now=float(i))
    cut = b.consecutive_loss_multiplier(now=100.0)
    assert cut == pytest.approx(0.75)
    # THE STREAK IS AN ORDER PROPERTY, NOT A TIME WINDOW. The same entries
    # give the same multiplier at any clock -- including one BEFORE they were
    # recorded, and none at all. `consecutive_loss_multiplier` takes `now` for
    # symmetry with the other budget methods and deliberately ignores it (the
    # 24h LOCKOUT is the one that reads the clock). Pinned here so the
    # timestamps above cannot be mistaken for the cause of the change, and so
    # a future session cannot quietly make this time-dependent.
    assert b.consecutive_loss_multiplier(now=0.0) == cut
    assert b.consecutive_loss_multiplier(now=10.0 ** 12) == cut
    assert b.consecutive_loss_multiplier() == cut


def test_budget_survives_a_restart(tmp_path):
    b = _budget(tmp_path)
    b.record_entry(symbol="BTC", strategy="s", signal_id="sig-1", now=0.0)
    b2 = TradeBudget(OvertradingConfig(), str(tmp_path))
    ok, _ = b2.may_enter(symbol="BTC", strategy="s", signal_id="sig-1", now=1.0)
    assert not ok, "a restart must not forget a signal it already traded"


# --- the drawdown bar must still FIRE when a reference IS supplied ----------
def test_drawdown_bar_is_skipped_only_when_the_reference_is_unknown(tmp_path):
    """The fix for the 'one loss pauses everything' bug must not have turned
    the drawdown condition off. With a reference equity it fires; without one
    it is skipped, and both halves are pinned here."""
    reg = _reg(tmp_path, warning_drawdown=0.05, hard_drawdown=0.08,
               max_consecutive_losses=99)
    # no reference -> the condition cannot be evaluated
    for _ in range(2):
        reg.record(KEY, _trade(-100.0))
    assert reg._drawdown_frac(reg.get(KEY).stats) is None
    assert reg.get(KEY).state is HealthState.ACTIVE

    # with a reference -> a 10% drawdown of a $1,000 account PAUSES
    other = strategy_key("ensemble.trend", "ETH", "long", "BULLISH")
    for _ in range(2):
        reg.record(other, _trade(-50.0), reference_equity=1_000.0)
    assert reg._drawdown_frac(reg.get(other).stats) == pytest.approx(0.10)
    assert reg.get(other).state is HealthState.PAUSED


def test_the_reference_equity_is_captured_once_and_does_not_drift(tmp_path):
    """A growing account must not quietly loosen the drawdown bar."""
    reg = _reg(tmp_path)
    reg.record(KEY, _trade(-1.0), reference_equity=1_000.0)
    reg.record(KEY, _trade(-1.0), reference_equity=1_000_000.0)
    assert reg.get(KEY).stats.reference_equity == pytest.approx(1_000.0)


def test_budgets_bind_on_historical_timestamps(tmp_path):
    """The backtest case the wall-clock prune silently disabled."""
    b = _budget(tmp_path, max_entries_per_market_per_day=2,
                cooldown_after_profit_hours=0, cooldown_after_loss_hours=0)
    t0 = 1_600_000_000.0                     # years before the wall clock
    for i in range(2):
        b.record_entry(symbol="BTC", strategy="s", signal_id=f"h{i}",
                       now=t0 + i)
    assert len(b.entries) == 2, "historical entries must survive the prune"
    ok, why = b.may_enter(symbol="BTC", strategy="s", signal_id="h9",
                          now=t0 + 5)
    assert not ok and "entries today" in why
