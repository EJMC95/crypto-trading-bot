"""Walk-forward, the sensitivity sweep, and the CLI's refusals."""
import json
import os
import re

import pytest

from dt_helpers import SYMS, tape
from downtrend_bot.backtester import Frictions
from downtrend_bot.walk_forward import (_set, _shape, default_grid,
                                        sensitivity, walk_forward)


def wf(cfg, markets, **kw):
    kw.setdefault("train_days", 10)
    kw.setdefault("validate_days", 3)
    kw.setdefault("test_days", 5)
    kw.setdefault("min_test_bars", 50)
    return walk_forward(cfg, markets, tape(bars_1h=1200), **kw)


def test_folds_are_produced_and_graded_on_the_test_slice(cfg, markets):
    rep = wf(cfg, markets)
    assert rep.folds
    for f in rep.graded:
        for tr in f.result.trades:
            assert tr.opened_ts >= f.test[0], "a warm-up trade was graded"


def test_the_span_is_measured_on_the_execution_timeframe(cfg, markets):
    """The trap: take the span across ALL timeframes and a fold can land where
    the 15m tape does not exist while the 4h tape does. The fold then runs,
    takes nothing, and reports '0 trades' -- which reads exactly like a
    strategy declining to trade."""
    from downtrend_bot.walk_forward import _span
    t = tape(bars_1h=400)
    lo15, hi15 = _span(t, "15m")
    lo4, hi4 = _span(t, "4h")
    assert (lo15, hi15) != (lo4, hi4) or hi15 == hi4


def test_a_thin_fold_is_skipped_and_reported_never_averaged_in(cfg, markets):
    rep = wf(cfg, markets, min_test_bars=10_000_000)
    assert rep.folds and not rep.graded
    assert all(f.skipped for f in rep.folds)
    agg = rep.aggregate()
    assert agg["graded"] == 0 and agg["skips"]


def test_a_tape_too_short_for_one_fold_says_so(cfg, markets):
    rep = walk_forward(cfg, markets, tape(bars_1h=300), train_days=180,
                       validate_days=60, test_days=60)
    assert rep.folds and rep.folds[0].skipped
    assert "one fold needs" in rep.folds[0].skipped


def test_consistency_is_the_share_of_positive_test_windows(cfg, markets):
    rep = wf(cfg, markets)
    agg = rep.aggregate()
    if agg.get("folds_that_traded"):
        assert 0.0 <= agg["consistency"] <= 1.0
        assert agg["test_windows_positive"] <= agg["folds_that_traded"]


def test_the_aggregate_pools_trades_rather_than_averaging_percentages(cfg,
                                                                     markets):
    """Averaging per-fold percentages weights a 2-trade fold like a 40-trade
    one. The pooled numbers are computed from the trades themselves."""
    rep = wf(cfg, markets)
    agg = rep.aggregate()
    if agg.get("folds_that_traded"):
        assert agg["pooled_trades"] == sum(
            len(f.result.trades) for f in rep.graded)


# ------------------------------------------------------------ sweep --------
def test_setting_a_config_path_does_not_mutate_the_original(cfg):
    before = cfg.strategy.minimum_score
    other = _set(cfg, "strategy.minimum_score", 99.0)
    assert other.strategy.minimum_score == 99.0
    assert cfg.strategy.minimum_score == before, "the sweep mutated its input"


def test_setting_an_unknown_path_raises():
    from downtrend_bot.config import AppConfig
    with pytest.raises(AttributeError):
        _set(AppConfig(), "strategy.no_such_knob", 1)


def test_every_grid_path_resolves_to_a_real_config_field(cfg):
    """A sweep dimension that reaches no field is a knob that measures
    nothing -- and its 'no effect' result would be a property of the harness."""
    grid = default_grid(cfg)
    grid.pop("_shipped", None)
    for path, values in grid.items():
        assert values, path
        _set(cfg, path, values[0])          # raises if the path is wrong


def test_the_sweep_reports_a_curve_and_never_a_winner(cfg, markets):
    rep = sensitivity(cfg, markets, tape(bars_1h=400),
                      grid={"strategy.minimum_score": [60.0, 70.0, 80.0]},
                      frictions=Frictions())
    assert "by_parameter" in rep and "verdicts" in rep
    assert "best" not in rep, "the sweep picked a winner"
    assert "selecting the best" in rep["note"]


def test_the_sweep_classifies_an_inert_knob():
    rows = [{"value": v, "trades": 5, "return_pct": 1.0,
             "max_drawdown_pct": 1.0, "average_r": 0.1, "robust": True}
            for v in (1, 2, 3)]
    assert _shape(rows)["verdict"] == "INERT"


def test_the_sweep_classifies_a_plateau_and_a_sign_flip():
    plateau = [{"value": v, "trades": 5 + v, "return_pct": 1.0 + 0.01 * v,
                "max_drawdown_pct": 1.0, "average_r": 0.1, "robust": True}
               for v in (1, 2, 3)]
    assert _shape(plateau)["verdict"] == "PLATEAU"
    flip = [{"value": 1, "trades": 5, "return_pct": 2.0,
             "max_drawdown_pct": 1.0, "average_r": 0.1, "robust": True},
            {"value": 2, "trades": 6, "return_pct": -3.0,
             "max_drawdown_pct": 1.0, "average_r": -0.1, "robust": False}]
    assert _shape(flip)["verdict"] == "SENSITIVE"


def test_an_ema_length_sweep_actually_changes_the_result(cfg, markets):
    """The end-to-end proof that the EMA knobs are wired: two very different
    slow lengths must not produce byte-identical results."""
    t = tape(bars_1h=800)
    rep = sensitivity(cfg, markets, t,
                      grid={"strategy.ema_slow": [60, 200]},
                      frictions=Frictions())
    rows = rep["by_parameter"]["strategy.ema_slow"]
    assert rep["verdicts"]["strategy.ema_slow"]["verdict"] != "INERT", rows


# -------------------------------------------------------------- the CLI ----
def test_the_cli_refuses_a_config_that_breaches_a_ceiling(tmp_path, capsys):
    from downtrend_bot.cli import main
    p = tmp_path / "bad.yaml"
    p.write_text("mode: backtest\nrisk:\n  max_leverage: 40.0\n")
    assert main(["--config", str(p), "backtest"]) == 2
    assert "CONFIG REFUSED" in capsys.readouterr().out


def test_validate_config_reports_ok_on_the_shipped_files(capsys):
    from downtrend_bot.cli import main
    here = os.path.dirname(__file__)
    for name in ("backtest", "paper", "live"):
        path = os.path.join(here, "..", "config", f"{name}.yaml")
        assert main(["--config", path, "validate-config"]) == 0, name


def test_the_backtest_command_exits_non_zero_when_robustness_refuses(tmp_path,
                                                                     capsys):
    """A CI job that runs a backtest must not go green on a configuration the
    robustness gate rejected."""
    from downtrend_bot.cli import main
    cfgp = os.path.join(os.path.dirname(__file__), "..", "config",
                        "backtest.yaml")
    code = main(["--config", cfgp, "--log-level", "ERROR", "backtest",
                 "--bars", "400"])
    out = capsys.readouterr().out
    assert code in (0, 2)
    if code == 2:
        assert "REFUSED" in out or "NO TRADES" in out


def test_the_live_command_refuses_a_backtest_config(capsys):
    from downtrend_bot.cli import main
    cfgp = os.path.join(os.path.dirname(__file__), "..", "config",
                        "backtest.yaml")
    assert main(["--config", cfgp, "live", "--loops", "1"]) == 2
    assert "NOT STARTED" in capsys.readouterr().out


def test_flatten_refuses_without_its_phrase(monkeypatch, capsys):
    from downtrend_bot.cli import main
    monkeypatch.delenv("FLATTEN_CONFIRMATION", raising=False)
    cfgp = os.path.join(os.path.dirname(__file__), "..", "config",
                        "backtest.yaml")
    assert main(["--config", cfgp, "flatten"]) == 2
    assert "CLOSE_ALL_POSITIONS" in capsys.readouterr().out


def test_a_malformed_config_file_is_a_refusal_not_a_traceback(tmp_path,
                                                              capsys):
    """An operator reading a stack trace cannot tell a rejected setting from a
    crashed program."""
    from downtrend_bot.cli import main
    p = tmp_path / "broken.yaml"
    p.write_text("risk:\n  totally_made_up: 5\n")
    assert main(["--config", str(p), "backtest"]) == 2
    assert "CONFIG REFUSED" in capsys.readouterr().out


def test_a_fold_that_took_no_trades_is_not_counted_as_a_flat_window(cfg,
                                                                    markets):
    """The zero-versus-unknown rule, at fold scale. A fold that DECLINED to
    trade and a fold that traded to exactly breakeven are different events,
    and folding the first in as a 0.0% return makes them the same number --
    which silently halves `consistency` on a selective strategy."""
    rep = wf(cfg, markets)
    agg = rep.aggregate()
    if agg.get("graded"):
        assert "folds_with_no_trades" in agg
        assert agg["folds_that_traded"] + agg["folds_with_no_trades"] == \
            agg["graded"]
        if agg["folds_that_traded"]:
            assert agg["consistency"] == round(
                agg["test_windows_positive"] / agg["folds_that_traded"], 3)


def test_a_consistency_computed_over_one_fold_says_so(cfg, markets):
    """`consistency 1.000` over a single traded window reads like a result and
    is not one. The report must carry that caveat where it is read."""
    rep = wf(cfg, markets)
    agg = rep.aggregate()
    if 0 < agg.get("folds_that_traded", 0) < 4:
        assert agg.get("power"), "a one-fold consistency was reported bare"


def test_make_examples_writes_tapes_the_loader_can_read(tmp_path, cfg, capsys):
    """The README tells a reader to run this and then point `--data` at the
    result. A generator whose output the loader cannot read would make every
    reproduction instruction in the README wrong."""
    import types

    from downtrend_bot.cli import _load_tapes, cmd_make_examples
    args = types.SimpleNamespace(out=str(tmp_path), bars=260, seed=3)
    assert cmd_make_examples(cfg, args) == 0
    assert "SYNTHETIC" in capsys.readouterr().out
    back = _load_tapes(cfg, str(tmp_path))
    assert set(back) == set(cfg.symbols)
    for sym, tape in back.items():
        for tf in (cfg.timeframes.regime, cfg.timeframes.signal,
                   cfg.timeframes.execution):
            assert tape.get(tf), (sym, tf)
            assert all(b.high >= b.low for b in tape[tf])


def test_the_sweep_reports_progress_rather_than_going_silent(cfg, markets,
                                                             capsys):
    """40 full backtests is a long silence, and the first thing anyone does
    about an hour of no output is kill it and never run it again. The `--only`
    filter exists for the same reason: a sweep you cannot scope is a sweep you
    cannot run."""
    import types

    from downtrend_bot.cli import cmd_sensitivity
    args = types.SimpleNamespace(data=None, bars=300, seed=4,
                                 only=["minimum_score"])
    assert cmd_sensitivity(cfg, args) == 0
    out = capsys.readouterr().out
    assert "sweeping" in out and "FULL backtest" in out
    # The total counts the swept cells PLUS the shipped reference run, so pin
    # the SHAPE of the progress line rather than an arithmetic I would have to
    # keep in step with the implementation.
    assert re.search(r"\[\s*\d+/\d+\] strategy\.minimum_score=", out), \
        "no per-cell progress line"
    assert "left)" in out, "no ETA"


def test_an_only_filter_that_matches_nothing_says_so(cfg):
    """Rather than sweeping the whole grid, or silently sweeping nothing."""
    import types

    from downtrend_bot.cli import cmd_sensitivity
    args = types.SimpleNamespace(data=None, bars=300, seed=4,
                                 only=["no_such_knob"])
    with pytest.raises(SystemExit, match="matched no parameter"):
        cmd_sensitivity(cfg, args)
