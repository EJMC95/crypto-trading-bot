"""Backtester: NO LOOK-AHEAD, gap modelling, and the frictions that matter."""
import pytest

from lighter_bots import signals as S
from lighter_bots.backtester import Backtester, Frictions
from lighter_bots.config import AppConfig
from lighter_bots.models import Candle
from conftest import ramp


def _cfg(tmp_path):
    c = AppConfig()
    c.state_dir = str(tmp_path / "state")
    c.timeframes.execution = "1h"
    c.timeframes.signal = "1h"
    c.timeframes.regime = "4h"
    import os
    os.makedirs(c.state_dir, exist_ok=True)
    return c


def _tape(n=500, drift=0.003, wiggle=0.004):
    h1 = ramp(n, drift=drift, wiggle=wiggle, tf_sec=3600)
    h4 = ramp(n // 4 + 260, drift=drift * 4, wiggle=wiggle, tf_sec=14400)
    return {"1h": h1, "4h": h4}


def _tapes(n=500, **kw):
    return {s: _tape(n, **kw) for s in ("BTC", "ETH")}


def test_precomputed_series_match_the_incremental_ones():
    """The equivalence that licenses SeriesCache. If an indicator peeked,
    these two would differ and every backtest number would be fiction."""
    bars = ramp(400, drift=0.002, wiggle=0.005)
    cache = S.SeriesCache(bars)
    for i in (250, 300, 350, 399):
        incremental = S.SeriesCache(bars[:i + 1])
        for name in ("e20", "e50", "e200", "atr", "rsi", "macd_hist", "roc",
                     "adx", "bb_lo", "bb_hi"):
            a = getattr(cache, name)[i]
            b = getattr(incremental, name)[i]
            if a is None or b is None:
                assert a is b, f"{name}@{i}: warm-up disagrees"
            else:
                assert a == pytest.approx(b, rel=1e-9), f"{name}@{i}"


def test_a_spike_planted_in_the_FUTURE_changes_nothing(tmp_path):
    """The structural no-look-ahead test: alter bars the decision cannot have
    seen and require an identical result."""
    cfg = _cfg(tmp_path)
    base = _tapes(420)
    bt = Backtester(cfg, _reg(), Frictions(post_only_miss_rate=0.0),
                    10_000.0, cfg.state_dir)
    clean = bt.run(base, "BTC")

    spiked = {s: {tf: [Candle(c.ts, c.open, c.high, c.low, c.close, c.volume)
                       for c in bars] for tf, bars in by.items()}
              for s, by in base.items()}
    for s in spiked:
        for tf in spiked[s]:
            for c in spiked[s][tf][-40:]:                # the FUTURE tail
                c.high *= 5.0
                c.close *= 5.0
    bt2 = Backtester(cfg, _reg(), Frictions(post_only_miss_rate=0.0),
                     10_000.0, cfg.state_dir)
    after = bt2.run(spiked, "BTC")

    early_clean = [t for t in clean.trades
                   if t.closed_ts < base["BTC"]["1h"][-45].ts]
    early_after = [t for t in after.trades
                   if t.closed_ts < base["BTC"]["1h"][-45].ts]
    assert len(early_clean) == len(early_after)
    for a, b in zip(early_clean, early_after):
        assert a.entry == pytest.approx(b.entry)
        assert a.pnl == pytest.approx(b.pnl)


def _reg():
    from conftest import make_market
    from lighter_bots.market_metadata import MarketRegistry
    return MarketRegistry([
        make_market("BTC", 1, tick_size=0.001, qty_step=0.0001,
                    min_base_amount=0.0001, min_quote_amount=1.0),
        make_market("ETH", 0, tick_size=0.001, qty_step=0.0001,
                    min_base_amount=0.0001, min_quote_amount=1.0)], "t")


def test_a_stop_that_GAPPED_fills_at_the_open_not_the_stop(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(slippage_bps=0.0), 10_000.0,
                    cfg.state_dir)
    bar = Candle(0, 90.0, 91.0, 89.0, 90.5, 1.0)     # opened BELOW the stop
    got = bt._exit_price(bar, level=95.0, side="long", kind="stop")
    assert got == pytest.approx(90.0), "a gap must not be flattered to the stop"
    bar2 = Candle(0, 96.0, 97.0, 94.0, 95.5, 1.0)    # traded through it
    assert bt._exit_price(bar2, 95.0, "long", "stop") == pytest.approx(95.0)


def test_a_short_stop_gap_is_modelled_the_same_way(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(slippage_bps=0.0), 10_000.0,
                    cfg.state_dir)
    bar = Candle(0, 110.0, 111.0, 109.0, 110.5, 1.0)  # opened ABOVE the stop
    assert bt._exit_price(bar, 105.0, "short", "stop") == pytest.approx(110.0)


def test_slippage_makes_a_stop_worse_on_both_sides(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(slippage_bps=10.0), 10_000.0,
                    cfg.state_dir)
    bar = Candle(0, 96.0, 97.0, 94.0, 95.5, 1.0)
    assert bt._exit_price(bar, 95.0, "long", "stop") < 95.0
    bar2 = Candle(0, 104.0, 106.0, 103.0, 104.5, 1.0)
    assert bt._exit_price(bar2, 105.0, "short", "stop") > 105.0


def test_funding_costs_longs_and_pays_shorts(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(funding_per_hour=0.0001),
                    10_000.0, cfg.state_dir)
    assert bt._funding("long", 1000.0, 10.0) < 0
    assert bt._funding("short", 1000.0, 10.0) > 0
    assert bt._funding("long", 1000.0, 10.0) == \
        pytest.approx(-bt._funding("short", 1000.0, 10.0))


def test_post_only_only_fills_when_the_price_is_touched(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(), 10_000.0, cfg.state_dir)
    miss = Candle(0, 101.0, 102.0, 100.5, 101.5, 1.0)
    px, _bps, _p = bt._entry_fill(miss, want=100.0, side="long",
                                  order_type="post_only")
    assert px is None, "an untouched limit does not fill"
    hit = Candle(0, 101.0, 102.0, 99.0, 101.5, 1.0)
    px, bps, _p = bt._entry_fill(hit, 100.0, "long", "post_only")
    assert px == pytest.approx(100.0) and bps == 0.0


def test_a_taker_entry_pays_spread_and_slippage(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(spread_bps=10.0, slippage_bps=10.0),
                    10_000.0, cfg.state_dir)
    bar = Candle(0, 100.0, 101.0, 99.0, 100.0, 1.0)
    long_px, long_bps, _ = bt._entry_fill(bar, 100.0, "long", "gtt")
    short_px, short_bps, _ = bt._entry_fill(bar, 100.0, "short", "gtt")
    assert long_px > 100.0 > short_px, "cost is adverse on BOTH sides"
    assert long_bps > 0 and short_bps > 0


def test_closed_bar_pointer_never_returns_an_unclosed_bar(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(), 10_000.0, cfg.state_dir)
    bars = ramp(10, tf_sec=3600)
    # the bar opening at bars[3].ts closes one hour later
    i = bt._closed_upto(bars, "1h", bars[3].ts + 3600)
    assert i == 3
    j = bt._closed_upto(bars, "1h", bars[3].ts + 3599)
    assert j == 2, "a bar one second from closing is NOT closed"


def test_a_run_produces_metrics_or_says_it_took_no_trades(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(post_only_miss_rate=0.0),
                    10_000.0, cfg.state_dir)
    res = bt.run(_tapes(420), "BTC")
    m = res.metrics()
    assert res.bars > 0
    if m.get("trades"):
        for k in ("total_return_pct", "sharpe", "max_drawdown_pct",
                  "profit_factor", "expectancy", "by_side", "by_regime"):
            assert k in m
    else:
        assert "note" in m and res.rejections


def test_rejections_are_counted_so_a_quiet_book_is_explainable(tmp_path):
    cfg = _cfg(tmp_path)
    bt = Backtester(cfg, _reg(), Frictions(), 10_000.0, cfg.state_dir)
    res = bt.run(_tapes(420), "BTC")
    assert res.rejections, "'no trades' must never be an unexplained result"


def test_robustness_refuses_a_one_symbol_result(tmp_path):
    from lighter_bots.walk_forward import robust
    from lighter_bots.backtester import BacktestResult
    from lighter_bots.models import Trade
    res = BacktestResult(start_equity=1000.0)
    res.equity_curve = [(0.0, 1000.0), (86400.0, 1100.0)]
    for i in range(40):
        pnl = 100.0 if i == 0 else 0.1
        res.trades.append(Trade("BTC" if i == 0 else "ETH", "long", "s", "N",
                                float(i), float(i) + 1, 100.0, 101.0, 1.0,
                                pnl, 0.0, 0.0, 1.0, "tp"))
    ok, fails = robust(res)
    assert not ok
    assert any("carries" in f for f in fails)


def test_walk_forward_reports_the_gap_rather_than_shrinking_the_split(tmp_path):
    from lighter_bots.walk_forward import run as wf_run
    cfg = _cfg(tmp_path)
    rep = wf_run(cfg, _reg(), _tapes(420), train_days=180, validate_days=60,
                 test_days=60)
    assert rep.problems and "needs" in rep.problems[0]
    assert not rep.folds, "no folds is the honest answer on a short tape"


def test_walk_forward_measures_the_span_of_the_EXECUTION_tape(tmp_path):
    """A fold placed where the execution timeframe has no bars must be named,
    never reported as a strategy that declined to trade.

    The bug this pins: measuring the span across ALL timeframes put a fold in
    a 333-day 4h window while the 15m clock only reached back 31 days. The
    fold produced 0 trades and read as a result."""
    from lighter_bots.walk_forward import run as wf_run
    cfg = _cfg(tmp_path)
    cfg.timeframes.execution = "15m"
    tapes = {}
    for s in ("BTC", "ETH"):
        deep_4h = ramp(2000, drift=0.001, wiggle=0.004, tf_sec=14400)
        # 15m tape covering only the LAST slice of that 4h history
        shallow = ramp(3000, drift=0.001, wiggle=0.004, tf_sec=900,
                       t0=deep_4h[-1].ts - 3000 * 900)
        tapes[s] = {"15m": shallow, "1h": ramp(2000, tf_sec=3600),
                    "4h": deep_4h}
    rep = wf_run(cfg, _reg(), tapes, train_days=180, validate_days=60,
                 test_days=60)
    assert rep.problems, "a fold with no execution tape must be reported"
    assert all("15m" in p or "needs" in p for p in rep.problems)
    for f in rep.folds:
        assert f.test.get("trades", 0) >= 0


def test_a_backtest_never_mutates_operational_state(tmp_path):
    """A backtest is a simulation. If it wrote to `state/`, a replayed losing
    streak would arrive as a PAUSED live strategy and a spent trade budget --
    silently, and in the dangerous direction."""
    import json
    import os
    cfg = _cfg(tmp_path)
    health_path = os.path.join(cfg.state_dir, "strategy_health.json")
    budget_path = os.path.join(cfg.state_dir, "trade_budget.json")
    sentinel = {"live-book|BTC|long|BULLISH|v1": {"state": "ACTIVE", "n": 7}}
    with open(health_path, "w") as fh:
        json.dump(sentinel, fh)
    with open(budget_path, "w") as fh:
        json.dump({"entries": [], "seen_signal_ids": ["keep-me"],
                   "cooldown_until": {}, "global_lockout_until": 0.0}, fh)

    bt = Backtester(cfg, _reg(), Frictions(post_only_miss_rate=0.0),
                    10_000.0, cfg.state_dir)
    res = bt.run(_tapes(420), "BTC")
    assert res.bars > 0

    assert json.load(open(health_path)) == sentinel, \
        "the backtest overwrote live strategy health"
    assert "keep-me" in json.load(open(budget_path))["seen_signal_ids"], \
        "the backtest overwrote the live trade budget"
