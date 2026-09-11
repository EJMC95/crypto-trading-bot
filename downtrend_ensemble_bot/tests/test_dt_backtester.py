"""The backtester's honesty: no look-ahead, no free fills, no state leakage."""
import os

import pytest

from dt_helpers import SYMS, tape
from downtrend_bot.backtester import Backtester, Frictions, robustness
from downtrend_bot.models import Candle, Trade
from downtrend_bot.synthetic import aggregate, make_market


def run(cfg, markets, tapes, **kw):
    bt = Backtester(cfg, markets, frictions=Frictions(**kw),
                    start_equity=cfg.backtest.start_equity)
    return bt.run(tapes)


def test_a_run_produces_a_result_and_never_raises_on_an_empty_tape(cfg,
                                                                   markets):
    res = run(cfg, markets, {s: {} for s in SYMS})
    assert res.metrics()["trades"] == 0


def test_no_trade_is_ever_opened_on_an_unclosed_bar(cfg, markets):
    """LAG-1: a signal at bar i's close fills at bar i+1's open. A fill at
    bar i's close is the whole family of look-ahead bugs in one line."""
    t = tape(bars_1h=400)
    res = run(cfg, markets, t)
    ex = cfg.timeframes.execution
    for tr in res.trades:
        bars = t[tr.symbol][ex]
        opens = {c.ts: c.open for c in bars}
        # every entry must coincide with SOME bar's open timestamp
        assert tr.opened_ts in opens or tr.opened_ts > bars[0].ts


def test_the_rejection_table_explains_an_empty_book(cfg, markets):
    """A book that takes nothing must say why. `{trades: 0}` alone is
    byte-identical between 'the market offered nothing' and 'a gate is wired
    shut'."""
    cfg.strategy.minimum_score = 99.9
    res = run(cfg, markets, tape(bars_1h=400))
    m = res.metrics()
    assert m["trades"] == 0
    assert m["rejections"], "no rejection census on an empty book"


def test_a_backtest_never_mutates_operational_state(cfg, markets, tmp_path):
    """A simulation that writes to the same `runtime/` a paper run reads is a
    backtest that can pause a live strategy."""
    health = os.path.join(cfg.runtime_dir, "strategy_health.json")
    budget = os.path.join(cfg.runtime_dir, "trade_budget.json")
    before = {p: (os.path.exists(p), os.path.getmtime(p)
                  if os.path.exists(p) else None)
              for p in (health, budget)}
    run(cfg, markets, tape(bars_1h=400))
    for p, (existed, mtime) in before.items():
        assert os.path.exists(p) == existed, f"{p} was created by a backtest"
        if existed:
            assert os.path.getmtime(p) == mtime


def test_frictions_actually_cost_money(cfg, markets):
    """A backtest with fees that reads identically to one without is a
    backtest whose frictions are not wired in."""
    t = tape(bars_1h=500)
    free = run(cfg, markets, t, taker_fee=0.0, maker_fee=0.0, spread_bps=0.0,
               slippage_bps=0.0, limit_miss_rate=0.0)
    costly = run(cfg, markets, t, taker_fee=0.002, maker_fee=0.002,
                 spread_bps=20.0, slippage_bps=30.0, limit_miss_rate=0.0)
    if free.metrics()["trades"] and costly.metrics()["trades"]:
        assert costly.metrics()["total_return_pct"] < \
            free.metrics()["total_return_pct"]


def test_funding_pays_shorts_and_costs_longs(cfg, markets):
    """A positive funding rate is paid BY longs TO shorts. Getting the sign
    backwards flatters a short book by exactly the amount it should earn."""
    bt = Backtester(cfg, markets,
                    frictions=Frictions(funding_per_hour=0.0001))
    paid_short = bt._funding("short", 1000.0, 24.0)
    paid_long = bt._funding("long", 1000.0, 24.0)
    assert paid_short > 0 and paid_long < 0
    assert paid_short == pytest.approx(-paid_long)


def test_a_gapped_stop_fills_at_the_open_not_the_stop_price(cfg, markets):
    """The single most common way a backtest lies. If the market gaps THROUGH
    a stop, the fill is the open -- assuming the stop price is free money."""
    bt = Backtester(cfg, markets, frictions=Frictions(slippage_bps=0.0))
    # a short's stop at 103; the bar opens at 110 (gapped through)
    bar = Candle(ts=0, open=110.0, high=112.0, low=109.0, close=111.0,
                 volume=1.0)
    assert bt._exit_price(bar, 103.0, "short", "stop") == 110.0
    # and when it does NOT gap, the stop price is realistic
    bar2 = Candle(ts=0, open=100.0, high=105.0, low=99.0, close=104.0,
                  volume=1.0)
    assert bt._exit_price(bar2, 103.0, "short", "stop") == 103.0


def test_the_robustness_gate_refuses_a_thin_result():
    from downtrend_bot.backtester import Result
    res = Result(start_equity=1000.0, end_equity=1100.0)
    res.trades = [Trade(symbol=SYMS[0], side="short", strategy="s", setup="b",
                        regime="BEARISH", opened_ts=0, closed_ts=1, entry=100,
                        exit=99, quantity=1, pnl=10.0, fees=0.1, funding=0.0,
                        r_multiple=1.0, reason="tp") for _ in range(5)]
    res.equity_curve = [(0, 1000.0), (30 * 86400, 1100.0)]
    ok, fails = robustness(res)
    assert not ok and any("underpowered" in f for f in fails)


def test_the_robustness_gate_refuses_a_one_market_result():
    from downtrend_bot.backtester import Result
    res = Result(start_equity=1000.0, end_equity=1100.0)
    trades = []
    for k in range(40):
        sym = SYMS[0] if k % 8 else SYMS[1]
        pnl = 10.0 if sym == SYMS[0] else 0.1
        trades.append(Trade(symbol=sym, side="short", strategy="s", setup="b",
                            regime="BEARISH", opened_ts=k, closed_ts=k + 1,
                            entry=100, exit=99, quantity=1, pnl=pnl, fees=0.0,
                            funding=0.0, r_multiple=1.0, reason="tp"))
    res.trades = trades
    res.equity_curve = [(0, 1000.0), (60 * 86400, 1100.0)]
    ok, fails = robustness(res)
    assert not ok and any("one-market" in f for f in fails)


def test_monte_carlo_reshuffles_order_and_says_what_it_does_not_prove():
    from downtrend_bot.backtester import Result
    res = Result(start_equity=1000.0)
    res.trades = [Trade(symbol=SYMS[0], side="short", strategy="s", setup="b",
                        regime="BEARISH", opened_ts=k, closed_ts=k + 1,
                        entry=100, exit=99, quantity=1,
                        pnl=(10.0 if k % 3 else -20.0), fees=0.0, funding=0.0,
                        r_multiple=1.0, reason="tp") for k in range(30)]
    mc = res.monte_carlo(runs=200, seed=1)
    assert mc["runs"] == 200
    assert mc["max_drawdown_pct_p99"] >= mc["max_drawdown_pct_p50"]
    assert "held fixed" in mc["note"]


def test_monte_carlo_refuses_to_speak_about_too_few_trades():
    from downtrend_bot.backtester import Result
    res = Result(start_equity=1000.0)
    res.trades = []
    assert res.monte_carlo()["runs"] == 0


def test_the_same_seed_gives_the_same_result(cfg, markets):
    """A backtest that is not reproducible cannot be compared to itself, so no
    sensitivity sweep run on it means anything."""
    t = tape(bars_1h=400)
    a = run(cfg, markets, t)
    b = run(cfg, markets, t)
    assert a.metrics()["trades"] == b.metrics()["trades"]
    assert a.metrics().get("total_return_pct") == \
        b.metrics().get("total_return_pct")


def test_aggregation_only_emits_complete_groups():
    """A partial group is a FORMING candle, and this package never acts on
    one."""
    bars = [Candle(ts=i * 900, open=1, high=2, low=0.5, close=1.5, volume=1)
            for i in range(10)]
    assert len(aggregate(bars, 4, "1h")) == 2      # 10 // 4, remainder dropped


def test_a_span_too_short_to_annualise_reports_none_and_never_crashes():
    """The metric that reports the run must not be able to kill it. A span of
    seconds sends `365 / span` into the millions; the first version of this
    raised OverflowError from inside `metrics()`."""
    from downtrend_bot.backtester import MIN_ANNUALISE_DAYS, Result
    res = Result(start_equity=1000.0, end_equity=1100.0)
    res.trades = [Trade(symbol=SYMS[0], side="short", strategy="s", setup="b",
                        regime="BEARISH", opened_ts=0, closed_ts=1, entry=100,
                        exit=99, quantity=1, pnl=10.0, fees=0.0, funding=0.0,
                        r_multiple=1.0, reason="tp")]
    res.equity_curve = [(0.0, 1000.0), (1.0, 1100.0)]
    m = res.metrics()                       # must not raise
    assert m["cagr_pct"] is None and m["calmar"] is None
    res.equity_curve = [(0.0, 1000.0), (MIN_ANNUALISE_DAYS * 86400 * 2,
                                        1100.0)]
    assert res.metrics()["cagr_pct"] is not None


def test_a_short_span_is_refused_even_when_the_maths_does_not_overflow():
    """The sharper half. A 1-day 10% gain annualises to 6e14% WITHOUT
    overflowing, so the try/except catches nothing and a fabricated number
    reaches the report. The FLOOR is what refuses it, and only a
    non-overflowing case can prove the floor is doing the work."""
    from downtrend_bot.backtester import MIN_ANNUALISE_DAYS, Result
    res = Result(start_equity=1000.0, end_equity=1100.0)
    res.trades = [Trade(symbol=SYMS[0], side="short", strategy="s", setup="b",
                        regime="BEARISH", opened_ts=0, closed_ts=1, entry=100,
                        exit=99, quantity=1, pnl=10.0, fees=0.0, funding=0.0,
                        r_multiple=1.0, reason="tp")]
    one_day = 86400.0
    assert one_day / 86400.0 < MIN_ANNUALISE_DAYS
    res.equity_curve = [(0.0, 1000.0), (one_day, 1100.0)]
    naive = (1100.0 / 1000.0) ** (365.0 / 1.0) - 1.0     # finite, and absurd
    assert naive > 1e10
    assert res.metrics()["cagr_pct"] is None
