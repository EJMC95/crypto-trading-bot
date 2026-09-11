"""Walk-forward validation and the sensitivity sweep (spec 12).

TWO INSTRUMENTS, AND THEY ANSWER DIFFERENT QUESTIONS.

`walk_forward` asks: *does this configuration survive being carried forward
into data it was not chosen on?* It slices the tape into rolling
train/validate/test folds, and -- this is the part that is easy to get wrong --
it does NOT fit anything on the training window. There is no optimiser here.
The train slice exists so the indicator warm-up and the health/budget state a
fold starts from are the ones a live run would have had; the reported numbers
are the TEST slices only. A walk-forward whose folds are graded on the window
that chose them is a backtest wearing a longer name.

`sensitivity` asks the harsher question: *is the result a plateau or a spike?*
It sweeps one parameter at a time around the shipped value and reports the
whole curve. A configuration whose profit collapses when a threshold moves by
one step is fitted, whatever its headline says, and the sweep is the only thing
that can tell you which of the two you have.

THE SPAN TRAP, learned the expensive way in the sibling package: a fold's span
must be measured on the EXECUTION timeframe, not across all timeframes. Take
the union and a fold can land where the 15m tape does not exist yet while the
4h tape does -- the fold then runs, takes no trades, and reports "0 trades",
which reads exactly like a strategy declining to trade. Thin folds are SKIPPED
and REPORTED, never silently averaged in.
"""
from __future__ import annotations

import copy
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from .backtester import Backtester, Frictions, Result, robustness
from .config import AppConfig
from .logging_setup import get
from .models import Candle, Market

log = get("walk_forward")

DAY = 86400.0


# --------------------------------------------------------------- slicing ---
def _slice(tape: dict[str, list[Candle]], lo: float, hi: float
           ) -> dict[str, list[Candle]]:
    return {tf: [c for c in bars if lo <= c.ts < hi]
            for tf, bars in tape.items()}


def _span(tapes: dict[str, dict[str, list[Candle]]], tf: str
          ) -> tuple[float, float]:
    """First and last timestamp on ONE timeframe. See the span trap above."""
    lo, hi = None, None
    for tape in tapes.values():
        bars = tape.get(tf) or []
        if not bars:
            continue
        lo = bars[0].ts if lo is None else min(lo, bars[0].ts)
        hi = bars[-1].ts if hi is None else max(hi, bars[-1].ts)
    return (lo or 0.0), (hi or 0.0)


@dataclass
class Fold:
    index: int
    train: tuple[float, float]
    test: tuple[float, float]
    result: Result | None = None
    skipped: str | None = None

    def summary(self) -> dict[str, Any]:
        d = {"fold": self.index,
             "test_from": self.test[0], "test_to": self.test[1],
             "test_days": round((self.test[1] - self.test[0]) / DAY, 1)}
        if self.skipped:
            d["skipped"] = self.skipped
            return d
        m = self.result.metrics()
        for k in ("trades", "total_return_pct", "max_drawdown_pct",
                  "win_rate_pct", "profit_factor", "expectancy", "avg_r",
                  "sharpe"):
            if k in m:
                d[k] = m[k]
        return d


@dataclass
class WalkForwardReport:
    folds: list[Fold] = field(default_factory=list)
    train_days: int = 180
    validate_days: int = 60
    test_days: int = 60
    step_days: int = 60

    @property
    def graded(self) -> list[Fold]:
        return [f for f in self.folds if f.result is not None]

    def aggregate(self) -> dict[str, Any]:
        g = self.graded
        if not g:
            return {"folds": len(self.folds), "graded": 0,
                    "note": "no fold produced a gradeable test window",
                    "skips": [f.summary() for f in self.folds if f.skipped]}
        # A fold that took NO TRADES is not a losing window -- it is the
        # strategy declining to trade, and folding it in as a 0.0% return
        # makes "declined" and "broke even" the same number. Both readings are
        # published: `consistency` is over folds that actually traded, and the
        # count that did not is stated beside it so nothing is hidden by the
        # choice of denominator.
        traded = [f for f in g if f.result.metrics().get("trades", 0) > 0]
        quiet = len(g) - len(traded)
        rets = [f.result.metrics().get("total_return_pct") or 0.0
                for f in traded]
        dds = [f.result.metrics().get("max_drawdown_pct") or 0.0
               for f in traded]
        trades = [f.result.metrics().get("trades", 0) for f in g]
        positive = sum(1 for r in rets if r > 0)
        if not traded:
            return {"folds": len(self.folds), "graded": len(g),
                    "folds_that_traded": 0, "folds_with_no_trades": quiet,
                    "note": "every graded fold declined to trade; read the "
                            "rejection census, not the return"}
        # Every graded fold's trades pooled, so the aggregate is measured on
        # trades rather than on an average of per-fold percentages (which
        # weights a 2-trade fold like a 40-trade one).
        pooled = [t for f in traded for t in f.result.trades]
        pnl = sum(t.pnl for t in pooled)
        wins = [t.pnl for t in pooled if t.pnl > 0]
        return {
            "folds": len(self.folds),
            "graded": len(g),
            "skipped": len(self.folds) - len(g),
            "folds_that_traded": len(traded),
            "folds_with_no_trades": quiet,
            "test_windows_positive": positive,
            "consistency": round(positive / len(traded), 3),
            "pooled_trades": len(pooled),
            "pooled_pnl": round(pnl, 2),
            "pooled_win_rate": (round(len(wins) / len(pooled), 4)
                                if pooled else None),
            "pooled_average_r": (round(statistics.fmean(
                [t.r_multiple for t in pooled]), 4) if pooled else None),
            "return_pct_per_fold": [round(r, 3) for r in rets],
            "return_pct_median": round(statistics.median(rets), 3),
            "return_pct_worst": round(min(rets), 3),
            "max_drawdown_pct_worst": round(max(dds), 3) if dds else None,
            "trades_per_fold": trades,
            "power": (None if len(traded) >= 4 else
                      f"only {len(traded)} fold(s) traded: `consistency` over "
                      f"{len(traded)} window(s) is not a measurement, and "
                      f"1.000 here means 'the one window that traded was "
                      f"positive' -- nothing more"),
            "note": ("consistency is the share of TEST windows THAT TRADED "
                     "and were positive; folds that took no trades are "
                     "counted separately, never as a 0% return. A strategy "
                     "that only works in one window is a window, not a "
                     "strategy"),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"config": {"train_days": self.train_days,
                           "validate_days": self.validate_days,
                           "test_days": self.test_days,
                           "step_days": self.step_days},
                "folds": [f.summary() for f in self.folds],
                "aggregate": self.aggregate()}


def walk_forward(cfg: AppConfig, markets: dict[str, Market],
                 tapes: dict[str, dict[str, list[Candle]]], *,
                 train_days: int = 180, validate_days: int = 60,
                 test_days: int = 60, step_days: int | None = None,
                 frictions: Frictions | None = None,
                 min_test_bars: int = 200,
                 progress: Callable[[str], None] | None = None
                 ) -> WalkForwardReport:
    """Rolling 180/60/60 by default, stepping by the test length.

    The TRAIN+VALIDATE slice is carried into the fold as history (warm-up),
    and the fold is GRADED on the TEST slice alone."""
    step = step_days or test_days
    tf_x = cfg.timeframes.execution
    lo, hi = _span(tapes, tf_x)
    rep = WalkForwardReport(train_days=train_days, validate_days=validate_days,
                            test_days=test_days, step_days=step)
    if hi <= lo:
        log.warning("walk_forward: no %s tape at all", tf_x)
        return rep

    warm = (train_days + validate_days) * DAY
    total_days = (hi - lo) / DAY
    need = train_days + validate_days + test_days
    if total_days < need:
        log.warning("walk_forward: %.0f days of %s tape, need %d for one fold",
                    total_days, tf_x, need)
        rep.folds.append(Fold(0, (lo, lo), (lo, hi),
                              skipped=f"tape is {total_days:.0f} days; one "
                                      f"fold needs {need}"))
        return rep

    idx, start = 0, lo
    while start + warm + test_days * DAY <= hi + 1:
        t0 = start + warm
        t1 = min(hi + 1, t0 + test_days * DAY)
        fold = Fold(idx, (start, t0), (t0, t1))
        sliced = {s: _slice(t, start, t1) for s, t in tapes.items()}
        bars = sum(1 for s in sliced
                   for c in (sliced[s].get(tf_x) or []) if c.ts >= t0)
        if bars < min_test_bars:
            fold.skipped = (f"only {bars} {tf_x} bars inside the test window "
                            f"(need {min_test_bars}) -- REPORTED, not averaged "
                            "in: a thin fold reads like a quiet strategy")
            log.warning("fold %d skipped: %s", idx, fold.skipped)
        else:
            bt = Backtester(cfg, markets, frictions=frictions,
                            start_equity=cfg.backtest.start_equity)
            # `grade_from` makes the fold report the TEST slice only while the
            # engine still walks the warm-up bars.
            fold.result = bt.run(sliced, on_bar=None)
            fold.result = _restrict(fold.result, t0)
        rep.folds.append(fold)
        if progress:
            progress(f"fold {idx}: {fold.summary()}")
        idx += 1
        start += step * DAY
    return rep


def _restrict(res: Result, t0: float) -> Result:
    """Keep only what happened at or after t0 -- the warm-up window funded the
    indicators, it does not get to fund the score."""
    out = Result(start_equity=res.start_equity, end_equity=res.end_equity,
                 bars=res.bars, liquidations=res.liquidations,
                 rejections=dict(res.rejections), health=res.health)
    out.trades = [t for t in res.trades if t.opened_ts >= t0]
    out.equity_curve = [(ts, e) for ts, e in res.equity_curve if ts >= t0]
    out.regime_transitions = [r for r in res.regime_transitions
                              if float(r.get("ts", 0)) >= t0]
    out.changepoints = [c for c in res.changepoints
                        if float(c.get("ts", 0)) >= t0]
    if out.equity_curve:
        out.start_equity = out.equity_curve[0][1]
        out.end_equity = out.equity_curve[-1][1]
    return out


# ----------------------------------------------------------- sensitivity ---
#: (dotted config path, [values]) -- the spec-12 dimensions. Each is swept
#: ALONE, around the shipped default, so a collapse is attributable.
def default_grid(cfg: AppConfig) -> dict[str, list[Any]]:
    s = cfg.strategy
    return {
        "strategy.ema_fast": [10, 15, 20, 30],
        "strategy.ema_mid": [30, 40, 50, 70],
        "strategy.ema_slow": [100, 150, 200],
        "strategy.adx_threshold": [15.0, 20.0, 25.0, 30.0],
        "strategy.atr_stop_buffer": [0.0, 0.25, 0.5, 1.0],
        "strategy.minimum_score": [60.0, 65.0, 70.0, 75.0, 80.0],
        "strategy.max_stop_distance_atr": [2.0, 3.0, 4.0],
        "strategy.tp1_r": [1.0, 1.5, 2.0],
        "strategy.tp2_r": [2.0, 2.5, 3.5],
        "strategy.max_holding_days": [2.0, 5.0, 10.0],
        "strategy.minimum_reward_risk": [1.4, 1.8, 2.2],
        "_shipped": [
            (s.ema_fast, s.ema_mid, s.ema_slow, s.adx_threshold,
             s.atr_stop_buffer, s.minimum_score, s.max_stop_distance_atr,
             s.tp1_r, s.tp2_r, s.max_holding_days, s.minimum_reward_risk)],
    }


def _set(cfg: AppConfig, path: str, value: Any) -> AppConfig:
    out = copy.deepcopy(cfg)
    obj = out
    parts = path.split(".")
    for p in parts[:-1]:
        obj = getattr(obj, p)
    if not hasattr(obj, parts[-1]):
        raise AttributeError(f"{path} is not a config field")
    setattr(obj, parts[-1], value)
    return out


@dataclass
class Cell:
    path: str
    value: Any
    metrics: dict[str, Any]
    robust: bool
    robust_fails: list[str]
    error: str | None = None


def sensitivity(cfg: AppConfig, markets: dict[str, Market],
                tapes: dict[str, dict[str, list[Candle]]], *,
                grid: dict[str, list[Any]] | None = None,
                frictions: Frictions | None = None,
                progress: Callable[[str], None] | None = None
                ) -> dict[str, Any]:
    """One parameter at a time. Reports the CURVE, never a winner.

    Deliberately NOT an optimiser. Picking the best cell of a sweep is the
    selection premium in its purest form -- the sibling package measured a
    ~1.85 t-unit inflation from exactly this move -- so this function has no
    'best' key and nothing downstream reads one. What it is for is shape: a
    plateau across neighbouring values is evidence, a spike is a warning."""
    g = dict(grid or default_grid(cfg))
    g.pop("_shipped", None)
    cells: list[Cell] = []
    base = None
    for path, values in g.items():
        for v in values:
            try:
                trial = _set(cfg, path, v)
            except AttributeError as exc:
                cells.append(Cell(path, v, {}, False, [], error=str(exc)))
                continue
            bt = Backtester(trial, markets, frictions=frictions,
                            start_equity=trial.backtest.start_equity)
            try:
                res = bt.run(tapes)
            except Exception as exc:                       # noqa: BLE001
                cells.append(Cell(path, v, {}, False, [], error=repr(exc)))
                continue
            ok, fails = robustness(res)
            m = res.metrics()
            cells.append(Cell(path, v, m, ok, fails))
            if progress:
                progress(f"{path}={v}: trades={m.get('trades')} "
                         f"ret={m.get('total_return_pct')}")
    # The shipped configuration, run once, as the reference line.
    bt = Backtester(cfg, markets, frictions=frictions,
                    start_equity=cfg.backtest.start_equity)
    res = bt.run(tapes)
    ok, fails = robustness(res)
    base = Cell("_shipped", "-", res.metrics(), ok, fails)

    by_path: dict[str, list[dict[str, Any]]] = {}
    for c in cells:
        by_path.setdefault(c.path, []).append(
            {"value": c.value, "trades": c.metrics.get("trades"),
             "return_pct": c.metrics.get("total_return_pct"),
             "max_drawdown_pct": c.metrics.get("max_drawdown_pct"),
             "average_r": c.metrics.get("avg_r"),
             "robust": c.robust, "error": c.error})

    verdicts = {p: _shape(rows) for p, rows in by_path.items()}
    inert = sorted(p for p, v in verdicts.items() if v["verdict"] == "INERT")
    return {
        "shipped": {"trades": base.metrics.get("trades"),
                    "return_pct": base.metrics.get("total_return_pct"),
                    "max_drawdown_pct": base.metrics.get("max_drawdown_pct"),
                    "robust": base.robust, "robust_fails": base.robust_fails},
        "by_parameter": by_path,
        "verdicts": verdicts,
        "inert_parameters": inert,
        "note": ("no 'best' cell is reported, on purpose: selecting the best "
                 "of N cells inflates its statistic by roughly the spread of "
                 "the unselected ones. Read the SHAPE. An INERT parameter is "
                 "a knob that reached no decision on this tape -- declare it, "
                 "do not tune it."),
    }


def _shape(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    vals = [r["return_pct"] for r in rows if r["return_pct"] is not None]
    if len(vals) < 2:
        return {"verdict": "UNGRADED", "why": "fewer than 2 gradeable cells"}
    lo, hi = min(vals), max(vals)
    spread = hi - lo
    trades = [r["trades"] for r in rows if r["trades"] is not None]
    if spread < 1e-9 and len(set(trades)) <= 1:
        return {"verdict": "INERT", "spread_pct": 0.0,
                "why": "every value produced an identical result -- this knob "
                       "does not reach a decision on this tape"}
    positive = sum(1 for v in vals if v > 0)
    if positive == 0:
        return {"verdict": "NEGATIVE-THROUGHOUT", "spread_pct": round(spread, 3),
                "why": "no value of this parameter was profitable; the "
                       "parameter is not the problem"}
    if positive == len(vals):
        return {"verdict": "PLATEAU", "spread_pct": round(spread, 3),
                "why": "profitable at every swept value -- the result does not "
                       "depend on this knob's exact setting"}
    return {"verdict": "SENSITIVE", "spread_pct": round(spread, 3),
            "positive_cells": f"{positive}/{len(vals)}",
            "why": "the sign flips inside the swept range; a value chosen "
                   "here is a fitted value until it is validated forward"}
