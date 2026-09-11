"""Section 30, end to end: the behaviours only the whole loop can demonstrate."""
import json
import os
import time

import pytest

from conftest import SYMS, tape
from downtrend_bot.config import Mode
from downtrend_bot.exchange_adapter import MockExchange, NotSupported
from downtrend_bot.health import (StrategyHealthMonitor, kill_switch_path)
from downtrend_bot.models import Candle, Position, Regime, Trade
from downtrend_bot.portfolio import Book, TradeBudget, effective_bets
from downtrend_bot.store import Store, reconcile
from downtrend_bot.synthetic import make_market
from downtrend_bot.trader import Trader


def mock(cfg, **kw):
    t = tape(bars_1h=400)
    return MockExchange(markets=[make_market(s) for s in cfg.symbols],
                        candles={(s, tf): bars for s, tape_ in t.items()
                                 for tf, bars in tape_.items()},
                        equity=cfg.backtest.start_equity, **kw)


def trader(cfg, **kw):
    t = Trader(cfg, mock(cfg), submit=False, clock=lambda: 2_000_000_000.0,
               **kw)
    t.load_markets()
    return t


def trade(symbol=SYMS[0], pnl=-10.0, ts=0.0):
    return Trade(symbol=symbol, side="short", strategy="downtrend.ensemble",
                 setup="breakdown_retest", regime="BEARISH", opened_ts=ts,
                 closed_ts=ts + 3600, entry=100.0, exit=101.0, quantity=1.0,
                 pnl=pnl, fees=0.1, funding=0.0,
                 r_multiple=(1.0 if pnl > 0 else -1.0), reason="stop")


# ------------------------------------------------------------ the loop -----
def test_a_full_loop_runs_and_reports(cfg):
    t = trader(cfg)
    st = t.step()
    assert st.ts and st.mode == "paper"
    assert st.regime
    from downtrend_bot.reporting import render_status
    assert "DOWNTREND ENSEMBLE" in render_status(st.as_dict())


def test_paper_mode_never_submits_an_order(cfg):
    """The one behavioural difference between paper and live, asserted on the
    ADAPTER rather than on a flag."""
    ex = mock(cfg)
    t = Trader(cfg, ex, submit=False, clock=lambda: 2_000_000_000.0)
    t.load_markets()
    for _ in range(3):
        t.step()
    assert ex.submitted == [], "paper mode reached the exchange"


def test_submit_true_is_impossible_outside_live_mode(cfg):
    """Order submission is gated on the MODE, so a paper run cannot be turned
    into a live one by a constructor keyword."""
    with pytest.raises(ValueError, match="LIVE"):
        Trader(cfg, mock(cfg), submit=True)


def test_an_incomplete_candle_is_never_used(cfg):
    """Spec 2. A bar is closed only once `ts + timeframe` is in the past."""
    t = trader(cfg)
    now = 1_000_000.0
    t.clock = lambda: now
    bars = [Candle(ts=now - 7200, open=1, high=2, low=0.5, close=1.5, volume=1),
            Candle(ts=now - 3600, open=1, high=2, low=0.5, close=1.5, volume=1),
            Candle(ts=now, open=1, high=2, low=0.5, close=1.5, volume=1)]
    closed = t._closed_only(bars, "1h")
    assert len(closed) == 2 and closed[-1].ts == now - 3600


def test_entries_halt_when_the_kill_switch_appears(cfg):
    t = trader(cfg)
    open(kill_switch_path(cfg.runtime_dir), "w").close()
    st = t.step()
    assert st.entries_disabled
    assert any("KILL_SWITCH" in h for h in st.halts)


def test_entries_halt_at_the_daily_loss_limit(cfg):
    t = trader(cfg)
    t.step()                      # roll the period keys first
    t.day_pnl = -abs(cfg.risk.max_daily_loss) * t.equity - 1.0
    st = t.step()
    assert st.entries_disabled
    assert any("daily loss" in h for h in st.halts)


def test_entries_halt_at_the_weekly_loss_limit(cfg):
    t = trader(cfg)
    t.step()
    t.week_pnl = -abs(cfg.risk.max_weekly_loss) * t.equity - 1.0
    st = t.step()
    assert any("weekly loss" in h for h in st.halts)


def test_a_halted_loop_records_why(cfg):
    """A quiet book must be explainable from the store alone, after the fact."""
    t = trader(cfg)
    open(kill_switch_path(cfg.runtime_dir), "w").close()
    t.step()
    halts = [d for d in t.store.decisions(limit=50) if d["action"] == "halt"]
    assert halts and halts[0]["reason"]


# ----------------------------------------------------- protective stops ----
def test_a_position_that_cannot_be_protected_is_closed_not_carried(cfg):
    """The invariant that justifies the whole ordering in `_place`: a fill
    without a stop is an unhedged naked position."""
    t = trader(cfg)
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=103.0,
                   r_unit=3.0, protective_ok=False)
    t.book.positions[pos.symbol] = pos
    t._send_protective = lambda req: None          # the venue refuses the stop
    t._manage({SYMS[0]: 100.0})
    assert SYMS[0] not in t.book.positions, "an unprotected position survived"
    reasons = [d["reason"] for d in t.store.decisions(limit=20)]
    assert any("unprotected" in r for r in reasons)


def test_a_regime_change_never_widens_an_open_stop(cfg):
    """Spec 5/21: a regime change may TIGHTEN a stop or CLOSE a position. It
    may never make an open trade riskier than it was when it was sized."""
    t = trader(cfg)
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=t.clock() - 60,
                   stop_price=101.0, r_unit=3.0, protective_ok=True)
    t.book.positions[pos.symbol] = pos
    before = pos.stop_price
    for _ in range(3):
        t._manage({SYMS[0]: 95.0})
        if pos.symbol not in t.book.positions:
            break
        assert pos.stop_price <= before + 1e-12, "the stop was widened"
        before = pos.stop_price


def test_a_short_stop_only_ever_moves_down(cfg):
    t = trader(cfg)
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=103.0,
                   r_unit=3.0, protective_ok=True)
    assert t._toward(pos, 99.0) == 99.0            # tighter: accepted
    assert t._toward(pos, 110.0) == 103.0          # looser: refused


def test_a_long_stop_only_ever_moves_up(cfg):
    t = trader(cfg)
    pos = Position(symbol=SYMS[0], side="long", quantity=1.0,
                   entry_price=100.0, opened_ts=0.0, stop_price=97.0,
                   r_unit=3.0, protective_ok=True)
    assert t._toward(pos, 99.0) == 99.0
    assert t._toward(pos, 90.0) == 97.0


def test_the_time_stop_closes_a_stale_position(cfg):
    cfg.strategy.max_holding_days = 1.0
    t = trader(cfg)
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=t.clock() - 2 * 86400,
                   stop_price=103.0, r_unit=3.0, protective_ok=True)
    t.book.positions[pos.symbol] = pos
    t._manage({SYMS[0]: 100.0})
    assert SYMS[0] not in t.book.positions
    assert t.book.closed[-1].reason == "time_stop"


# -------------------------------------------------------- overtrading ------
def test_a_duplicate_signal_id_is_refused(cfg):
    b = TradeBudget(cfg.overtrading, cfg.runtime_dir, persist=False)
    ok, _w = b.may_enter(symbol=SYMS[0], strategy="s", signal_id="sig-1",
                         score=80.0, price=100.0, atr=2.0, now=1000.0)
    assert ok
    b.record_entry(symbol=SYMS[0], strategy="s", signal_id="sig-1",
                   score=80.0, price=100.0, now=1000.0)
    ok, why = b.may_enter(symbol=SYMS[0], strategy="s", signal_id="sig-1",
                          score=80.0, price=100.0, atr=2.0, now=1001.0)
    assert not ok and "duplicate" in why


def test_a_cooldown_after_a_loss_blocks_re_entry(cfg):
    cfg.overtrading.cooldown_after_loss_hours = 6.0
    b = TradeBudget(cfg.overtrading, cfg.runtime_dir, persist=False)
    b.record_entry(symbol=SYMS[0], strategy="s", signal_id="a", score=80.0,
                   price=100.0, now=0.0)
    b.record_exit(symbol=SYMS[0], signal_id="a", pnl=-10.0, now=0.0)
    ok, why = b.may_enter(symbol=SYMS[0], strategy="s", signal_id="b",
                          score=80.0, price=100.0, atr=2.0, now=3600.0)
    assert not ok and "cooldown" in why
    ok, _w = b.may_enter(symbol=SYMS[0], strategy="s", signal_id="c",
                         score=80.0, price=100.0, atr=2.0, now=7 * 3600.0)
    assert ok


def test_the_per_symbol_daily_budget_binds(cfg):
    cfg.overtrading.max_entries_per_symbol_per_day = 2
    cfg.overtrading.cooldown_after_profit_hours = 0.0
    b = TradeBudget(cfg.overtrading, cfg.runtime_dir, persist=False)
    for k in range(2):
        b.record_entry(symbol=SYMS[0], strategy="s", signal_id=f"s{k}",
                       score=80.0, price=100.0 + 10 * k,
                       now=k * 3600.0)
    ok, why = b.may_enter(symbol=SYMS[0], strategy="s", signal_id="s9",
                          score=80.0, price=200.0, atr=2.0, now=3 * 3600.0)
    assert not ok, why


def test_four_losses_in_a_day_lock_the_whole_book(cfg):
    """Four losses in a day is the PORTFOLIO talking, not one symbol -- so a
    SYMBOL with no cooldown of its own must still be refused."""
    b = TradeBudget(cfg.overtrading, cfg.runtime_dir, persist=False)
    for k in range(4):
        sym = SYMS[k % len(SYMS)]
        b.record_entry(symbol=sym, strategy="s", signal_id=f"x{k}",
                       score=80.0, price=100.0, now=k * 600.0)
        b.record_exit(symbol=sym, signal_id=f"x{k}", pnl=-5.0, now=k * 600.0)
    ok, why = b.may_enter(symbol="FRESH/USDT:USDT", strategy="s",
                          signal_id="z", score=90.0, price=100.0, atr=2.0,
                          now=5000.0)
    assert not ok and "lockout" in why


def test_a_loss_with_no_recorded_entry_still_counts_toward_the_lockout():
    """The restart case: the process came back after the position opened, so
    the entry list starts empty. A loss the budget cannot SEE is a loss the
    portfolio lockout cannot COUNT -- and the trades most likely to be going
    wrong are exactly the ones that span a restart."""
    from downtrend_bot.config import OvertradingConfig
    b = TradeBudget(OvertradingConfig(), "runtime", persist=False)
    for k in range(4):
        b.record_exit(symbol=SYMS[k % len(SYMS)], signal_id=f"orphan{k}",
                      pnl=-5.0, now=k * 600.0)
    ok, why = b.may_enter(symbol="FRESH/USDT:USDT", strategy="s",
                          signal_id="z", score=90.0, price=100.0, atr=2.0,
                          now=5000.0)
    assert not ok and "lockout" in why


def test_consecutive_losses_shrink_the_next_size(cfg):
    b = TradeBudget(cfg.overtrading, cfg.runtime_dir, persist=False)
    full = b.consecutive_loss_multiplier(1000.0)
    assert full == 1.0
    for k in range(3):
        b.record_entry(symbol=SYMS[0], strategy="s", signal_id=f"y{k}",
                       score=80.0, price=100.0, now=k * 600.0)
        b.record_exit(symbol=SYMS[0], signal_id=f"y{k}", pnl=-5.0,
                      now=k * 600.0)
    assert b.consecutive_loss_multiplier(2000.0) < full


def test_the_budget_prunes_against_the_data_not_the_wall_clock(cfg, tmp_path):
    """A budget that prunes against `time.time()` deletes every historical
    entry as it is written, so in a backtest every limit silently does
    nothing."""
    b = TradeBudget(cfg.overtrading, str(tmp_path), persist=True)
    old = 1_600_000_000.0
    b.record_entry(symbol=SYMS[0], strategy="s", signal_id="hist",
                   score=80.0, price=100.0, now=old)
    b.save()
    b2 = TradeBudget(cfg.overtrading, str(tmp_path), persist=True)
    ok, why = b2.may_enter(symbol=SYMS[0], strategy="s", signal_id="hist",
                           score=80.0, price=100.0, atr=2.0, now=old + 60)
    assert not ok and "duplicate" in why, "the historical entry was pruned away"


# ------------------------------------------------------ strategy health ----
def test_one_losing_trade_does_not_pause_a_strategy(cfg):
    """A strategy's equity starts at zero, so a naive drawdown denominator
    reads the first losing trade as a 100% drawdown and pauses everything."""
    mon = StrategyHealthMonitor(cfg.strategy_health, cfg.runtime_dir,
                               persist=False)
    h = mon.record("k", trade(pnl=-10.0), reference_equity=10_000.0)
    assert h.may_enter, f"one loss paused the strategy ({h.state})"


def test_a_sustained_losing_run_pauses_a_strategy(cfg):
    cfg.strategy_health.hard_pause_trade_count = 10
    cfg.strategy_health.pause_profit_factor = 0.65
    mon = StrategyHealthMonitor(cfg.strategy_health, cfg.runtime_dir,
                               persist=False)
    for k in range(30):
        mon.record("k", trade(pnl=-10.0, ts=k * 3600), reference_equity=10_000.0)
    assert not mon.get("k").may_enter


def test_recovery_is_impossible_without_paper_validation(cfg):
    """Spec 10: a paused strategy may not resume on its own. Auto-recovery is
    how a broken strategy quietly comes back."""
    mon = StrategyHealthMonitor(cfg.strategy_health, cfg.runtime_dir,
                               persist=False)
    for k in range(30):
        mon.record("k", trade(pnl=-10.0, ts=k * 3600), reference_equity=10_000.0)
    ok, why = mon.promote_to_recovery("k")
    assert not ok and why


def test_recovery_is_possible_after_paper_validation(cfg):
    mon = StrategyHealthMonitor(cfg.strategy_health, cfg.runtime_dir,
                               persist=False)
    for k in range(30):
        mon.record("k", trade(pnl=-10.0, ts=k * 3600), reference_equity=10_000.0)
    ok, why = mon.record_paper_validation(
        "k", signals=50, expectancy=0.2, max_drawdown=0.01,
        note="30-day shadow run, 20 trades")
    assert ok, why
    ok, why = mon.promote_to_recovery("k")
    assert ok, why


def test_a_drawdown_that_cannot_be_measured_returns_none(cfg):
    """None means 'condition skipped', a declared weakening. 0.0 would mean
    'measured, and it is zero' -- which would silently pass the check."""
    mon = StrategyHealthMonitor(cfg.strategy_health, cfg.runtime_dir,
                               persist=False)
    from downtrend_bot.health import Stats
    assert mon.drawdown_frac(Stats()) is None


# ------------------------------------------------------- change points -----
def test_the_detector_needs_sustained_evidence_not_one_spike(cfg):
    from downtrend_bot.changepoint import ChangePointDetector
    cfg.changepoint.min_duration_bars = 3
    d = ChangePointDetector(cfg.changepoint)
    for _ in range(80):
        d.observe("volatility", 1.0)
    d.observe("volatility", 40.0)
    assert d.evaluate(1.0).severity == "none", "one spike flipped the state"
    for _ in range(5):
        d.observe("volatility", 40.0)
        v = d.evaluate(2.0)
    assert v.severity != "none"


def test_the_detector_clears_slowly(cfg):
    from downtrend_bot.changepoint import ChangePointDetector
    cfg.changepoint.min_duration_bars = 2
    cfg.changepoint.clear_duration_bars = 5
    d = ChangePointDetector(cfg.changepoint)
    for _ in range(80):
        d.observe("volatility", 1.0)
    for _ in range(6):
        d.observe("volatility", 40.0)
        v = d.evaluate(1.0)
    assert v.severity != "none"
    d.observe("volatility", 1.0)
    assert d.evaluate(2.0).severity != "none", "cleared on a single calm bar"


def test_a_critical_change_point_forbids_entries(cfg):
    from downtrend_bot.changepoint import Verdict
    assert Verdict(changed=True, severity="critical").risk_multiplier == 0.0


# --------------------------------------------------------- correlation -----
def test_correlated_names_count_as_fewer_bets():
    """`effective_bets` over three names that move together must be well
    below 3 -- otherwise the position cap counts one bet as three."""
    import math
    n = 200
    base = [math.sin(i / 7.0) for i in range(n)]
    closes = {"A/USDT:USDT": [100 + b for b in base],
              "B/USDT:USDT": [100 + b * 1.01 for b in base],
              "C/USDT:USDT": [100 + b * 0.99 for b in base]}
    got = effective_bets(list(closes), closes)
    assert got is not None and got < 1.6, got


def test_an_unmeasurable_correlation_is_treated_as_perfectly_correlated():
    """The fail-safe direction. Reading an unknown correlation as ZERO buys
    diversification the book does not have."""
    got = effective_bets(["A/USDT:USDT", "B/USDT:USDT"],
                         {"A/USDT:USDT": [1.0], "B/USDT:USDT": [1.0]})
    assert got is None or got <= 1.01


# ------------------------------------------------- store + reconciliation --
def test_the_store_round_trips_a_position_and_a_trade(cfg):
    with Store(cfg.state_db) as s:
        pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                       entry_price=100.0, opened_ts=1.0, stop_price=103.0,
                       protective_ok=True)
        s.upsert_position(pos)
        assert len(s.open_positions()) == 1
        s.record_trade(trade())
        assert len(s.trades()) == 1
        s.drop_position(SYMS[0])
        assert s.open_positions() == []


def test_reconciliation_reports_an_orphan_and_never_repairs_it(cfg):
    """A position at the venue we have no record of has no stop attached in
    our book. It must be surfaced, and it must NOT be silently adopted --
    a wrong guess writes a real order."""
    with Store(cfg.state_db) as s:
        venue = [Position(symbol=SYMS[1], side="short", quantity=2.0,
                          entry_price=50.0, opened_ts=1.0, stop_price=0.0)]
        rep = reconcile(s, venue)
        assert not rep["clean"] and rep["orphans"]
        assert "never repairs" in rep["action"]
        assert s.open_positions() == [], "reconcile MUTATED the book"


def test_reconciliation_reports_a_ghost(cfg):
    with Store(cfg.state_db) as s:
        s.upsert_position(Position(symbol=SYMS[0], side="short", quantity=1.0,
                                   entry_price=100.0, opened_ts=1.0,
                                   stop_price=103.0, protective_ok=True))
        rep = reconcile(s, [])
        assert not rep["clean"] and rep["ghosts"]


def test_reconciliation_flags_a_venue_position_with_no_stop(cfg):
    with Store(cfg.state_db) as s:
        s.upsert_position(Position(symbol=SYMS[0], side="short", quantity=1.0,
                                   entry_price=100.0, opened_ts=1.0,
                                   stop_price=103.0, protective_ok=False))
        venue = [Position(symbol=SYMS[0], side="short", quantity=1.0,
                          entry_price=100.0, opened_ts=1.0, stop_price=103.0)]
        rep = reconcile(s, venue)
        assert rep["unprotected"] and not rep["clean"]


def test_a_clean_book_reconciles_clean(cfg):
    with Store(cfg.state_db) as s:
        pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                       entry_price=100.0, opened_ts=1.0, stop_price=103.0,
                       protective_ok=True)
        s.upsert_position(pos)
        assert reconcile(s, [pos])["clean"]


def test_trading_stays_halted_until_reconciliation_is_clean(cfg):
    t = trader(cfg)
    t._reconciled = False
    st = t.step()
    assert st.entries_disabled


# ------------------------------------------------------------- adapter -----
def test_an_unsupported_capability_raises_rather_than_emulating(cfg):
    """Spec 1: never silently emulate a stop, a reduce-only order or a
    leverage setting with an unsafe order."""
    ex = MockExchange(markets=[make_market(SYMS[0])])
    ex.supports = {}
    assert not ex.capability("native_stop")
    with pytest.raises(NotSupported):
        ex.require("native_stop", "reduce_only")


def test_the_real_exchange_adapter_refuses_to_submit_by_default():
    from downtrend_bot.exchange_adapter import CcxtAdapter
    a = CcxtAdapter("binanceusdm")
    assert a.allow_submit is False
    res = a.create_order.__doc__ or ""
    from downtrend_bot.models import OrderIntent, OrderRequest
    req = OrderRequest(symbol=SYMS[0], side="short", action="sell",
                       intent=OrderIntent.ENTRY, order_type="limit",
                       quantity=1.0, price=100.0)
    out = a.create_order(req)
    assert not out.accepted and not out.submitted


def test_every_store_write_path_actually_writes(cfg):
    """A positional INSERT breaks silently the moment its table gains a
    column, and nothing above it notices until an order is being placed. This
    drives EVERY writer once -- it is the test that caught an `orders` INSERT
    one placeholder short of its own schema, which would have raised on the
    first order in paper mode."""
    from downtrend_bot.models import (Fill, OrderIntent, OrderRequest,
                                      OrderResult, ScoreCard, Signal)
    with Store(cfg.state_db) as s:
        req = OrderRequest(symbol=SYMS[0], side="short", action="sell",
                           intent=OrderIntent.ENTRY, order_type="limit",
                           quantity=1.0, price=100.0, client_order_id="c1",
                           signal_id="s1")
        s.record_order(req, None)
        s.record_order(req, OrderResult(accepted=True, order_id="x",
                                        status="filled", filled=1.0,
                                        avg_price=100.0))
        s.record_fill(Fill(symbol=SYMS[0], side="short", quantity=1.0,
                           price=100.0, ts=1.0, fee=0.05, order_id="c1"))
        s.upsert_position(Position(symbol=SYMS[0], side="short", quantity=1.0,
                                   entry_price=100.0, opened_ts=1.0,
                                   stop_price=103.0))
        s.record_signal(Signal(symbol=SYMS[0], side="short", strategy="s",
                               setup="b", timeframe="1h", candle_ts=1,
                               score=ScoreCard(regime=25.0), entry=100.0,
                               stop=103.0, targets=[97.0], atr=2.0,
                               reward_risk=2.0, regime=Regime.BEARISH))
        s.record_trade(trade())
        s.record_equity(1000.0, 0.1, 1, "BEARISH")
        s.record_event("kind", {"a": 1})
        s.record_decision(symbol=SYMS[0], side="short", action="enter",
                          reason="ok")
        counts = s.counts()
    for table, n in counts.items():
        assert n >= 1, f"{table} recorded nothing"
    with Store(cfg.state_db) as s:
        assert s.order("c1")["status"] == "filled"


def test_reconciliation_reports_a_quantity_mismatch(cfg):
    """Same symbol, same side, DIFFERENT size. Neither an orphan nor a ghost,
    and the most dangerous of the three: every downstream stop, target and
    risk number is computed against a quantity the venue does not hold."""
    with Store(cfg.state_db) as s:
        s.upsert_position(Position(symbol=SYMS[0], side="short", quantity=1.0,
                                   entry_price=100.0, opened_ts=1.0,
                                   stop_price=103.0, protective_ok=True))
        venue = [Position(symbol=SYMS[0], side="short", quantity=2.5,
                          entry_price=100.0, opened_ts=1.0, stop_price=103.0)]
        rep = reconcile(s, venue)
        assert not rep["clean"] and rep["mismatched"]
        assert rep["mismatched"][0]["venue"]["quantity"] == 2.5


def test_reconciliation_reports_a_side_mismatch(cfg):
    with Store(cfg.state_db) as s:
        s.upsert_position(Position(symbol=SYMS[0], side="short", quantity=1.0,
                                   entry_price=100.0, opened_ts=1.0,
                                   stop_price=103.0, protective_ok=True))
        venue = [Position(symbol=SYMS[0], side="long", quantity=1.0,
                          entry_price=100.0, opened_ts=1.0, stop_price=97.0)]
        assert reconcile(s, venue)["mismatched"]


def test_a_rounding_size_difference_is_not_a_mismatch(cfg):
    """The other half: a guard that fires on venue dust is a guard that gets
    waived, and then the real mismatch is ignored too."""
    with Store(cfg.state_db) as s:
        s.upsert_position(Position(symbol=SYMS[0], side="short",
                                   quantity=1.0000001, entry_price=100.0,
                                   opened_ts=1.0, stop_price=103.0,
                                   protective_ok=True))
        venue = [Position(symbol=SYMS[0], side="short", quantity=1.0,
                          entry_price=100.0, opened_ts=1.0, stop_price=103.0)]
        assert not reconcile(s, venue)["mismatched"]


def test_a_misspelled_capability_raises_rather_than_answering_false(cfg):
    """A capability name is a string, and a naive `.get()` answers False for a
    typo -- indistinguishable from a venue that genuinely cannot do it.

    MEASURED: `place_reduce_only_stop` (a method name) was being asked of
    adapters that publish `native_stop` (a capability name). Every plan got
    'WARNING: the adapter reports NO native stop', including from the mock that
    fully supports one, and the live gate's protective-exit lock was closed
    against an adapter that would have passed it."""
    ex = MockExchange(markets=[make_market(SYMS[0])])
    assert ex.capability("native_stop") is True
    with pytest.raises(KeyError, match="not a capability"):
        ex.capability("place_reduce_only_stop")


def test_a_capable_adapter_does_not_get_the_missing_stop_warning(cfg):
    """The other half. A warning that fires on everything is a warning the
    operator learns to ignore, and then the real one is missed too."""
    from downtrend_bot.execution import build_plan
    from downtrend_bot.models import Regime, ScoreCard, Signal, Sizing
    sig = Signal(symbol=SYMS[0], side="short", strategy="s", setup="b",
                 timeframe="1h", candle_ts=1, score=ScoreCard(regime=25.0),
                 entry=100.0, stop=103.0, targets=[95.5, 92.5], atr=2.0,
                 reward_risk=2.5, regime=Regime.BEARISH)
    ex = MockExchange(markets=[make_market(SYMS[0])])
    plan = build_plan(signal=sig, sizing=Sizing(True, quantity=1.0),
                      market=make_market(SYMS[0]), cfg=cfg.execution,
                      strat=cfg.strategy,
                      adapter_supports_stop=(ex.capability("native_stop")
                                             and ex.capability("reduce_only")),
                      adapter_supports_tp=True)
    assert not any("NO native stop" in n for n in plan.notes), plan.notes


def test_the_live_gate_sees_a_capable_adapter_as_capable(cfg):
    """The lock must be closed by a venue that cannot protect a position, and
    OPEN for one that can -- a lock that is always closed protects nothing
    because it will be the first thing someone overrides."""
    from downtrend_bot.config import Mode
    from downtrend_bot.live_trader import preflight
    cfg.mode = Mode.LIVE
    res, detail = preflight(cfg, mock(cfg), interactive_confirmed=True,
                            env={"ENABLE_LIVE_TRADING": "true",
                                 "LIVE_CONFIRMATION": "I_UNDERSTAND_THE_RISK"})
    assert detail["protective_capability"] is True
    assert res.checks["protective_exit_capability"] is True


def test_paper_fills_are_never_kinder_than_the_backtest(cfg):
    """The soak GATES live trading, so it must not be a softer test than the
    backtest it validates.

    The first version filled at the exact limit price and charged no entry
    fee, while the backtester charged spread, slippage and both fees -- so a
    book could look gradeable on paper and not be. This asserts the direction
    on both sides rather than the exact number: a long pays MORE than the
    quoted price, a short receives LESS."""
    t = trader(cfg)
    long_fill = t._adverse(100.0, "long", closing=False)
    short_fill = t._adverse(100.0, "short", closing=False)
    assert long_fill > 100.0, "a paper long filled at or better than the quote"
    assert short_fill < 100.0, "a paper short filled at or better than the quote"
    # closing reverses which direction hurts
    assert t._adverse(100.0, "long", closing=True) < 100.0
    assert t._adverse(100.0, "short", closing=True) > 100.0


def test_a_paper_round_trip_charges_both_legs(cfg):
    """Charging only the exit understates the round trip by half, and a paper
    book is graded on round trips."""
    t = trader(cfg)
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=t.clock() - 60,
                   stop_price=103.0, r_unit=3.0, protective_ok=True)
    t.book.positions[pos.symbol] = pos
    t._close(pos, 100.0, "manual")
    tr = t.book.closed[-1]
    one_leg = 100.0 * cfg.execution.taker_fee
    assert tr.fees > one_leg * 1.9, f"only one leg was charged: {tr.fees}"


def test_a_flat_paper_round_trip_loses_money(cfg):
    """The sanity check the frictions exist for: open and close at the same
    mark and the book must be DOWN. A paper book that breaks even on a flat
    round trip is a book whose costs are not wired in."""
    t = trader(cfg)
    before = t.equity
    pos = Position(symbol=SYMS[0], side="short", quantity=1.0,
                   entry_price=100.0, opened_ts=t.clock() - 60,
                   stop_price=103.0, r_unit=3.0, protective_ok=True)
    t.book.positions[pos.symbol] = pos
    t._close(pos, 100.0, "manual")
    assert t.equity < before, "a flat round trip cost nothing"
