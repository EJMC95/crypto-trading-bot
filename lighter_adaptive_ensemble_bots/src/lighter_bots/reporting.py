"""Reports and the local terminal dashboard. No external notifications.

Every number here carries its basis. A report that prints "Sharpe 1.8" without
the trade count, the window and what fees were assumed is how a backtest gets
quoted as a fact six weeks later.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from .models import Regime


def _f(v: Any, nd: int = 2, dash: str = "n/a") -> str:
    if v is None:
        return dash
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def write_json(reports_dir: str, name: str, payload: dict[str, Any]) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, name)
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1, default=str, sort_keys=True)
    return path


def backtest_report(metrics: dict[str, Any], *, config_note: str = "",
                    frictions: dict[str, Any] | None = None) -> str:
    if not metrics.get("trades"):
        return ("BACKTEST: no trades were taken.\n"
                "  That is a RESULT, not a failure -- read the rejection\n"
                "  table below before changing a threshold.\n"
                + json.dumps(metrics.get("rejections", {}), indent=2))
    L = ["=" * 74, "BACKTEST RESULT", "=" * 74]
    if config_note:
        L.append(f"  config: {config_note}")
    if frictions:
        L.append("  frictions: " + ", ".join(f"{k}={v}" for k, v in
                                             sorted(frictions.items())))
    L += [f"  window: {_f(metrics.get('span_days'), 1)} days"
          f"   trades: {metrics['trades']}"
          f"   ({_f(metrics.get('trades_per_30d'), 1)}/30d)", ""]
    rows = [("total return %", _f(metrics.get("total_return_pct"), 3)),
            ("CAGR %", _f(metrics.get("cagr_pct"), 3)),
            ("Sharpe", _f(metrics.get("sharpe"), 3)),
            ("Sortino", _f(metrics.get("sortino"), 3)),
            ("Calmar", _f(metrics.get("calmar"), 3)),
            ("max drawdown %", _f(metrics.get("max_drawdown_pct"), 3)),
            ("win rate %", _f(metrics.get("win_rate_pct"), 2)),
            ("profit factor", _f(metrics.get("profit_factor"), 3)),
            ("expectancy", _f(metrics.get("expectancy"), 5)),
            ("average R", _f(metrics.get("avg_r"), 3)),
            ("longest losing streak", metrics.get("longest_losing_streak")),
            ("fees", _f(metrics.get("fees"), 3)),
            ("funding", _f(metrics.get("funding"), 3)),
            ("avg slippage bps", _f(metrics.get("avg_slippage_bps"), 2)),
            ("liquidation violations", metrics.get("liquidation_violations"))]
    for k, v in rows:
        L.append(f"  {k:<24} {v}")
    for title, key in (("BY STRATEGY", "by_strategy"), ("BY SIDE", "by_side"),
                       ("BY REGIME", "by_regime"), ("BY SYMBOL", "by_symbol")):
        d = metrics.get(key) or {}
        if not d:
            continue
        L += ["", f"  {title}"]
        for k, v in sorted(d.items(), key=lambda kv: -kv[1]["pnl"])[:12]:
            L.append(f"    {k:<34} n={v['n']:<5} pnl={_f(v['pnl'], 2):>12}"
                     f"  avgR={_f(v['avg_r'], 3)}")
    rej = metrics.get("rejections") or {}
    if rej:
        L += ["", "  TOP REJECTION REASONS (why trades did NOT happen)"]
        for k, v in list(rej.items())[:10]:
            L.append(f"    {v:>7}  {k}")
    L.append("=" * 74)
    L.append("NOT A CLAIM OF PROFITABILITY. Past tape, modelled fills.")
    return "\n".join(L)


def walk_forward_report(summary: dict[str, Any],
                        folds: list[dict[str, Any]] | None = None,
                        problems: list[str] | None = None) -> str:
    L = ["=" * 74, "WALK-FORWARD", "=" * 74]
    for p in (problems or []):
        L.append(f"  PROBLEM: {p}")
    for k, v in summary.items():
        L.append(f"  {k:<26} {v}")
    for i, f in enumerate(folds or []):
        t = f.get("test") or {}
        L.append(f"    fold {i:>2}: test trades={t.get('trades', 0):<5} "
                 f"return%={_f(t.get('total_return_pct'), 3):>9} "
                 f"maxDD%={_f(t.get('max_drawdown_pct'), 2):>7}")
    L.append("=" * 74)
    return "\n".join(L)


def dashboard(*, mode: str, regime: Regime | str, equity: float,
              book: dict[str, Any], health: dict[str, Any],
              ws: dict[str, Any] | None = None,
              nonces: dict[str, Any] | None = None,
              kill_switch: bool = False, budgets: dict[str, Any] | None = None,
              data_age_s: float | None = None,
              margin_utilisation: float | None = None,
              liq_distances: dict[str, float] | None = None) -> str:
    r = regime.value if isinstance(regime, Regime) else str(regime)
    L = ["+" + "-" * 72 + "+",
         f"| lighter_adaptive_ensemble_bots   mode={mode:<9} "
         f"regime={r:<17}|",
         "+" + "-" * 72 + "+"]
    if kill_switch:
        L.append("|  ** KILL SWITCH PRESENT -- no new entries **"
                 + " " * 28 + "|")
    L.append(f"|  equity {_f(equity, 2):>14}   open {book.get('open', 0):<3} "
             f"closed {book.get('closed', 0):<5} "
             f"realized {_f(book.get('realized'), 2):>10}      |")
    L.append(f"|  gross {_f(book.get('gross_notional'), 0):>10}  "
             f"long {_f(book.get('net_long'), 0):>9}  "
             f"short {_f(book.get('net_short'), 0):>9}  "
             f"risk {_f(book.get('open_risk'), 2):>7} |")
    if margin_utilisation is not None:
        L.append(f"|  margin utilisation {margin_utilisation:>6.1%}"
                 + " " * 46 + "|")
    if data_age_s is not None:
        L.append(f"|  data age {data_age_s:>8.0f}s" + " " * 51 + "|")
    held = book.get("held") or {}
    if held:
        L.append("|  held: " + ", ".join(f"{k}{v}" for k, v in
                                         sorted(held.items()))[:63].ljust(64)
                 + "|")
    if liq_distances:
        L.append("|  liq distance: " + ", ".join(
            f"{k} {v:.1%}" for k, v in sorted(liq_distances.items())
        )[:55].ljust(56) + "|")
    if ws:
        L.append(f"|  ws connected={str(ws.get('connected')):<5} "
                 f"stale={_f(ws.get('stale_s'), 0):>6}s "
                 f"reconnects={ws.get('reconnects', 0):<4} "
                 f"dupes={ws.get('dropped_duplicates', 0):<5}     |")
    if nonces:
        for k, v in sorted(nonces.items()):
            L.append(f"|  nonce {k:<10} next={v.get('next_nonce'):<10} "
                     f"unknown={v.get('unknown', 0):<3}"
                     + " " * 24 + "|")
    if budgets:
        L.append(f"|  entries 1h={budgets.get('hour', 0)} "
                 f"24h={budgets.get('day', 0)}  "
                 f"cooldowns={budgets.get('cooldowns', 0)}  "
                 f"lockout={str(budgets.get('lockout', False)):<5}"
                 + " " * 16 + "|")
    if health:
        L.append("+" + "-" * 72 + "+")
        for k, v in list(sorted(health.items()))[:10]:
            state = v.get("state", "?")
            L.append(f"|  {k[:44]:<44} {state:<10} n={v.get('n', 0):<5}"
                     + " " * 4 + "|")
    L.append("+" + "-" * 72 + "+")
    return "\n".join(L)


def daily_report(mode: str, metrics: dict[str, Any], health: dict[str, Any],
                 reports_dir: str, day: str | None = None) -> str:
    day = day or time.strftime("%Y-%m-%d", time.gmtime())
    payload = {"day": day, "mode": mode, "generated": time.time(),
               "metrics": metrics, "strategy_health": health,
               "disclaimer": "Modelled results. No claim of profitability."}
    return write_json(reports_dir, f"{mode}_{day}.json", payload)
