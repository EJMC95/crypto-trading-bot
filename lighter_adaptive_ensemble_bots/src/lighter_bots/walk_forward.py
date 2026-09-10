"""Rolling walk-forward validation and parameter sensitivity.

WHY THIS AND NOT A SINGLE BACKTEST. One backtest over one window on one venue
is a hypothesis, not evidence -- and the failure it hides is specific: a
config chosen because it looked best on the window it was chosen on. The
rolling split (train 180d / validate 60d / test 60d) grades each config on
tape it was NOT selected on, and `robust()` refuses a result that leans on one
market, one period or a handful of exceptional trades.

THE SELECTION PREMIUM IS PRICED, NOT ASSUMED. Picking the best of N configs
inflates its statistic by roughly the spread of the unselected distribution.
`sensitivity()` reports the FULL grid and `selection_premium()` reports the
gap between the best cell and the median, so a headline number is always read
next to what picking it cost.
"""
from __future__ import annotations

import copy
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .backtester import Backtester, BacktestResult, Frictions
from .config import AppConfig
from .data import tf_seconds
from .logging_setup import get
from .market_metadata import MarketRegistry
from .models import Candle

log = get("walk_forward")


@dataclass
class Window:
    train_start: float
    train_end: float
    validate_end: float
    test_end: float

    def as_dict(self) -> dict[str, float]:
        return {"train_start": self.train_start, "train_end": self.train_end,
                "validate_end": self.validate_end, "test_end": self.test_end}


@dataclass
class FoldResult:
    window: Window
    validate: dict[str, Any]
    test: dict[str, Any]
    config_note: str = ""


@dataclass
class WalkForwardReport:
    folds: list[FoldResult] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        tests = [f.test for f in self.folds if f.test.get("trades")]
        if not tests:
            return {"folds": len(self.folds), "note": "no fold produced trades"}
        rets = [t["total_return_pct"] for t in tests]
        return {
            "folds": len(self.folds),
            "folds_with_trades": len(tests),
            "test_return_pct_mean": round(statistics.fmean(rets), 4),
            "test_return_pct_median": round(statistics.median(rets), 4),
            "test_folds_positive": sum(1 for r in rets if r > 0),
            "test_trades_total": sum(t["trades"] for t in tests),
            "worst_fold_pct": round(min(rets), 4),
            "best_fold_pct": round(max(rets), 4),
            "mean_max_drawdown_pct": round(statistics.fmean(
                t["max_drawdown_pct"] for t in tests), 4),
        }


def slice_tapes(tapes: dict[str, dict[str, list[Candle]]],
                start: float, end: float
                ) -> dict[str, dict[str, list[Candle]]]:
    out: dict[str, dict[str, list[Candle]]] = {}
    for sym, by_tf in tapes.items():
        out[sym] = {tf: [c for c in bars
                         if start <= c.ts and c.ts + tf_seconds(tf) <= end]
                    for tf, bars in by_tf.items()}
    return out


def windows(first_ts: float, last_ts: float, *, train_days: int = 180,
            validate_days: int = 60, test_days: int = 60,
            step_days: int | None = None) -> list[Window]:
    step = (step_days or test_days) * 86400.0
    tr, va, te = train_days * 86400.0, validate_days * 86400.0, test_days * 86400.0
    out: list[Window] = []
    start = first_ts
    while start + tr + va + te <= last_ts:
        out.append(Window(start, start + tr, start + tr + va,
                          start + tr + va + te))
        start += step
    return out


def run(cfg: AppConfig, registry: MarketRegistry,
        tapes: dict[str, dict[str, list[Candle]]], *,
        train_days: int = 180, validate_days: int = 60, test_days: int = 60,
        frictions: Frictions | None = None, start_equity: float = 10_000.0,
        btc_symbol: str = "BTC") -> WalkForwardReport:
    rep = WalkForwardReport()
    tf_exec = cfg.timeframes.execution
    # THE SPAN THAT MATTERS IS THE EXECUTION TAPE'S.
    #
    # An earlier version measured it across EVERY timeframe. On a venue where
    # 4h history reaches back 333 days while 15m reaches back 31, that placed
    # a fold in a window with no execution bars at all -- and the fold then
    # reported "0 trades", which reads as "the strategy declined to trade"
    # and is actually "there is no tape here". A silent nothing is the worst
    # possible output, so the span is taken from the clock's own timeframe and
    # thin folds are named.
    exec_ts = [c.ts for by_tf in tapes.values() for c in (by_tf.get(tf_exec) or [])]
    if not exec_ts:
        rep.problems.append(
            f"no {tf_exec} tape supplied -- the execution timeframe drives the "
            "clock, so there is nothing to walk")
        return rep
    first, last = min(exec_ts), max(exec_ts)
    wins = windows(first, last, train_days=train_days,
                   validate_days=validate_days, test_days=test_days)
    if not wins:
        span = (last - first) / 86400.0
        rep.problems.append(
            f"{tf_exec} tape spans {span:.0f}d; a {train_days}/"
            f"{validate_days}/{test_days} split needs "
            f"{train_days + validate_days + test_days}d. REPORTING THE GAP "
            "rather than shrinking the split to manufacture folds.")
        return rep
    for w in wins:
        va_tapes = slice_tapes(tapes, w.train_end, w.validate_end)
        te_tapes = slice_tapes(tapes, w.validate_end, w.test_end)
        thin = [name for name, t in (("validate", va_tapes), ("test", te_tapes))
                if sum(len(v.get(tf_exec) or []) for v in t.values()) == 0]
        if thin:
            rep.problems.append(
                f"fold starting {w.train_start:.0f}: no {tf_exec} bars in "
                f"{', '.join(thin)} -- SKIPPED rather than reported as zero "
                "trades")
            continue
        bt = Backtester(cfg, registry, frictions, start_equity)
        va = bt.run(va_tapes, btc_symbol)
        te = bt.run(te_tapes, btc_symbol)
        rep.folds.append(FoldResult(w, va.metrics(), te.metrics()))
    if not rep.folds and not rep.problems:
        rep.problems.append("no fold had usable execution tape")
    return rep


# --------------------------------------------------------- sensitivity -----
def sensitivity(cfg: AppConfig, registry: MarketRegistry,
                tapes: dict[str, dict[str, list[Candle]]],
                grid: dict[str, Sequence[Any]], *,
                apply: Callable[[AppConfig, str, Any], None] | None = None,
                frictions: Frictions | None = None,
                start_equity: float = 10_000.0,
                btc_symbol: str = "BTC") -> list[dict[str, Any]]:
    """One axis at a time, from the SAME baseline -- so each row is
    attributable to the parameter it names."""
    rows: list[dict[str, Any]] = []
    for param, values in grid.items():
        for v in values:
            c = copy.deepcopy(cfg)
            if apply is not None:
                apply(c, param, v)
            else:
                _set_path(c, param, v)
            bt = Backtester(c, registry, frictions, start_equity)
            m = bt.run(tapes, btc_symbol).metrics()
            rows.append({"param": param, "value": v,
                         "trades": m.get("trades", 0),
                         "return_pct": m.get("total_return_pct"),
                         "sharpe": m.get("sharpe"),
                         "max_dd_pct": m.get("max_drawdown_pct"),
                         "profit_factor": m.get("profit_factor")})
    return rows


def _set_path(cfg: AppConfig, dotted: str, value: Any) -> None:
    obj = cfg
    parts = dotted.split(".")
    for p in parts[:-1]:
        obj = getattr(obj, p)
    setattr(obj, parts[-1], value)


def selection_premium(rows: Iterable[dict[str, Any]], metric: str = "sharpe"
                      ) -> dict[str, Any] | None:
    vals = [r[metric] for r in rows if r.get(metric) is not None
            and r.get("trades", 0) >= 10]
    if len(vals) < 3:
        return None
    best, med = max(vals), statistics.median(vals)
    return {"metric": metric, "best": round(best, 4),
            "median": round(med, 4), "premium": round(best - med, 4),
            "cells": len(vals),
            "note": "the premium is what picking the best cell buys you "
                    "before any out-of-sample tape is seen"}


def robust(result: BacktestResult, *, max_symbol_share: float = 0.60,
           max_top3_share: float = 0.80, min_trades: int = 30
           ) -> tuple[bool, list[str]]:
    """Refuse a result that rests on one market, one stretch or three trades."""
    m = result.metrics()
    fails: list[str] = []
    n = m.get("trades", 0)
    if n < min_trades:
        fails.append(f"only {n} trades (< {min_trades}): underpowered")
    total = sum(t.pnl for t in result.trades)
    if total > 0:
        by_sym = m.get("by_symbol") or {}
        for sym, d in by_sym.items():
            share = d["pnl"] / total
            if share > max_symbol_share:
                fails.append(f"{sym} carries {share:.0%} of P&L "
                             f"(> {max_symbol_share:.0%})")
        top3 = sum(sorted((t.pnl for t in result.trades), reverse=True)[:3])
        if top3 / total > max_top3_share:
            fails.append(f"top 3 trades are {top3 / total:.0%} of P&L "
                         f"(> {max_top3_share:.0%}): tail-dependent")
    halves = len(result.trades) // 2
    if halves:
        h1 = sum(t.pnl for t in result.trades[:halves])
        h2 = sum(t.pnl for t in result.trades[halves:])
        if h1 <= 0 or h2 <= 0:
            fails.append(f"halves disagree (h1 {h1:+.2f} / h2 {h2:+.2f})")
    return (not fails), fails
