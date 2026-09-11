"""Terminal rendering and JSON artefacts (spec 16).

NO EXTERNAL NOTIFICATIONS. Not Telegram, not email, not a webhook. The spec
says so and it is also the right call: a notifier is a network dependency
inside the loop that manages money, and the first thing it does when it fails
is make the loop slower and noisier at exactly the moment something is wrong.

TWO REPORTING RULES THIS FILE ENFORCES:

1. A ZERO IS NEVER RENDERED THE SAME AS AN UNKNOWN. `-` means unmeasurable.
   0.0 means measured, and it was zero. This has cost the sibling fleet real
   days: a breadth that could not be computed rendered as 0.0 and read exactly
   like a market-wide crash.

2. NO PROFITABILITY CLAIM. The renderer states measurements and never grades
   them as good. `robustness()` is allowed to say a configuration is REFUSED;
   nothing here is allowed to say a strategy works.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Mapping, Sequence

from .models import contained_path, safe_filename

BAR = "-" * 78


def fmt(v: Any, spec: str = ".2f", dash: str = "-") -> str:
    """The unknown/zero distinction, in one place so it cannot drift."""
    if v is None:
        return dash
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        try:
            return format(float(v), spec)
        except (ValueError, TypeError):
            return str(v)
    return str(v)


def pct(v: Any, nd: int = 2) -> str:
    return "-" if v is None else f"{float(v):.{nd}f}%"


def ts(t: Any) -> str:
    if not t:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(float(t))) + "Z"


def table(rows: Sequence[Mapping[str, Any]], cols: Sequence[str],
          widths: Sequence[int] | None = None) -> str:
    if not rows:
        return "  (none)"
    w = list(widths or [max(len(c), *(len(str(r.get(c, ""))) for r in rows))
                        for c in cols])
    head = "  " + "  ".join(c.ljust(w[i])[:w[i]] for i, c in enumerate(cols))
    line = "  " + "  ".join("-" * w[i] for i in range(len(cols)))
    body = [
        "  " + "  ".join(str(r.get(c, "")).ljust(w[i])[:w[i]]
                         for i, c in enumerate(cols))
        for r in rows]
    return "\n".join([head, line, *body])


# ------------------------------------------------------------- artefacts ---
def write_json(reports_dir: str, name: str, payload: Any) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    path = contained_path(reports_dir, safe_filename(name, fallback="report"))
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2, default=str, sort_keys=False)
    return path


def write_text(reports_dir: str, name: str, text: str) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    path = contained_path(reports_dir, safe_filename(name, fallback="report"))
    with open(path, "w") as fh:
        fh.write(text)
    return path


# --------------------------------------------------------------- renders ---
def render_backtest(metrics: Mapping[str, Any], *,
                    monte_carlo: Mapping[str, Any] | None = None,
                    robust: tuple[bool, Sequence[str]] | None = None,
                    title: str = "BACKTEST") -> str:
    out = [BAR, title, BAR]
    if not metrics.get("trades"):
        out.append("  NO TRADES were taken.")
        out.append("  " + str(metrics.get("note", "")))
        rej = metrics.get("rejections") or {}
        if rej:
            out.append("")
            out.append("  Why the book stayed empty (top rejection reasons):")
            for k, v in list(rej.items())[:12]:
                out.append(f"    {v:>6}  {k}")
        out.append(BAR)
        return "\n".join(out)

    left = [
        ("trades", fmt(metrics.get("trades"), ".0f")),
        ("win rate", pct(metrics.get("win_rate_pct"))),
        ("profit factor", fmt(metrics.get("profit_factor"), ".3f")),
        ("expectancy $", fmt(metrics.get("expectancy"), ".2f")),
        ("average R", fmt(metrics.get("avg_r"), ".3f")),
        ("longest loss streak", fmt(metrics.get("longest_losing_streak"), ".0f")),
    ]
    right = [
        ("total return", pct(metrics.get("total_return_pct"))),
        ("CAGR", pct(metrics.get("cagr_pct"))),
        ("max drawdown", pct(metrics.get("max_drawdown_pct"))),
        ("Sharpe", fmt(metrics.get("sharpe"), ".2f")),
        ("Sortino", fmt(metrics.get("sortino"), ".2f")),
        ("Calmar", fmt(metrics.get("calmar"), ".2f")),
    ]
    for (a, av), (b, bv) in zip(left, right):
        out.append(f"  {a:<22}{av:>12}     {b:<20}{bv:>12}")
    out.append("")
    out.append(f"  span {fmt(metrics.get('span_days'), '.1f')} days   "
               f"equity {fmt(metrics.get('start_equity'))} -> "
               f"{fmt(metrics.get('end_equity'))}   "
               f"fees {fmt(metrics.get('fees'))}   "
               f"funding {fmt(metrics.get('funding'))}   "
               f"liquidations {fmt(metrics.get('liquidations'), '.0f')}")
    conc = metrics.get("top3_share_of_profit")
    out.append(f"  top-3 trades are {pct(None if conc is None else conc * 100)}"
               f" of profit   avg exposure "
               f"{pct(metrics.get('avg_exposure_pct'))}"
               f"   peak {pct(metrics.get('max_exposure_pct'))}"
               f"   {fmt(metrics.get('trades_per_30d'), '.1f')} trades/30d")

    for key, label in (("by_side", "BY SIDE"), ("by_setup", "BY SETUP"),
                       ("by_regime", "BY REGIME"), ("by_symbol", "BY SYMBOL")):
        d = metrics.get(key) or {}
        if not d:
            continue
        out.append("")
        out.append(f"  {label}")
        rows = [{"key": k, "n": v.get("n"), "pnl": round(v.get("pnl", 0), 2),
                 "avg_r": round(v.get("avg_r", 0), 3)}
                for k, v in sorted(d.items(),
                                   key=lambda kv: -abs(kv[1].get("pnl", 0)))]
        out.append(table(rows[:12], ["key", "n", "pnl", "avg_r"]))

    if monte_carlo and monte_carlo.get("runs"):
        out.append("")
        out.append("  MONTE CARLO (trade order reshuffled; trades held fixed)")
        out.append(f"    max drawdown  p50 {pct(monte_carlo['max_drawdown_pct_p50'])}"
                   f"   p90 {pct(monte_carlo['max_drawdown_pct_p90'])}"
                   f"   p99 {pct(monte_carlo['max_drawdown_pct_p99'])}"
                   f"   worst {pct(monte_carlo['max_drawdown_pct_worst'])}")
        out.append(f"    final return  p05 {pct(monte_carlo['final_return_pct_p05'])}"
                   f"   p50 {pct(monte_carlo['final_return_pct_p50'])}")
        out.append(f"    {monte_carlo.get('note', '')}")

    if robust is not None:
        ok, fails = robust
        out.append("")
        out.append(f"  ROBUSTNESS GATE: {'PASS' if ok else 'REFUSED'}")
        for f in fails:
            out.append(f"    - {f}")
        if ok:
            out.append("    the gate found no disqualifying pattern. That is "
                       "NOT a claim that the strategy is profitable.")

    rej = metrics.get("rejections") or {}
    if rej:
        out.append("")
        out.append("  TOP REJECTION REASONS")
        for k, v in list(rej.items())[:10]:
            out.append(f"    {v:>6}  {k}")
    out.append(BAR)
    return "\n".join(out)


def render_walk_forward(report: Mapping[str, Any]) -> str:
    out = [BAR, "WALK-FORWARD VALIDATION", BAR]
    c = report.get("config", {})
    out.append(f"  train {c.get('train_days')}d / validate "
               f"{c.get('validate_days')}d / test {c.get('test_days')}d, "
               f"step {c.get('step_days')}d")
    out.append("")
    rows = []
    for f in report.get("folds", []):
        rows.append({
            "fold": f.get("fold"),
            "test_from": ts(f.get("test_from")),
            "days": f.get("test_days"),
            "trades": f.get("trades", "-") if not f.get("skipped") else "-",
            "return%": (fmt(f.get("total_return_pct"), ".2f")
                        if not f.get("skipped") else "SKIPPED"),
            "maxDD%": (fmt(f.get("max_drawdown_pct"), ".2f")
                       if not f.get("skipped") else "-"),
            "avgR": (fmt(f.get("avg_r"), ".3f")
                     if not f.get("skipped") else "-"),
        })
    out.append(table(rows, ["fold", "test_from", "days", "trades", "return%",
                            "maxDD%", "avgR"]))
    for f in report.get("folds", []):
        if f.get("skipped"):
            out.append(f"    fold {f.get('fold')} skipped: {f['skipped']}")
    agg = report.get("aggregate", {})
    out.append("")
    out.append("  AGGREGATE (test windows only)")
    for k in ("folds", "graded", "skipped", "folds_that_traded",
              "folds_with_no_trades", "test_windows_positive", "consistency",
              "pooled_trades", "pooled_pnl", "pooled_win_rate",
              "pooled_average_r", "return_pct_median", "return_pct_worst",
              "max_drawdown_pct_worst"):
        if k in agg:
            out.append(f"    {k:<26}{fmt(agg[k], '.4f')}")
    if agg.get("power"):
        out.append("")
        out.append(f"    ! {agg['power']}")
    if agg.get("note"):
        out.append(f"    {agg['note']}")
    out.append(BAR)
    return "\n".join(out)


def render_sensitivity(report: Mapping[str, Any]) -> str:
    out = [BAR, "SENSITIVITY SWEEP (one parameter at a time)", BAR]
    sh = report.get("shipped", {})
    out.append(f"  shipped config: trades {fmt(sh.get('trades'), '.0f')}   "
               f"return {pct(sh.get('return_pct'))}   "
               f"maxDD {pct(sh.get('max_drawdown_pct'))}   "
               f"robustness {'PASS' if sh.get('robust') else 'REFUSED'}")
    for f in sh.get("robust_fails", []) or []:
        out.append(f"    - {f}")
    for path, rows in (report.get("by_parameter") or {}).items():
        v = (report.get("verdicts") or {}).get(path, {})
        out.append("")
        out.append(f"  {path}   [{v.get('verdict', '?')}]  "
                   f"spread {fmt(v.get('spread_pct'), '.3f')}pp")
        out.append(f"    {v.get('why', '')}")
        pretty = [{"value": r["value"], "trades": fmt(r["trades"], ".0f"),
                   "return%": fmt(r["return_pct"], ".2f"),
                   "maxDD%": fmt(r["max_drawdown_pct"], ".2f"),
                   "avgR": fmt(r["average_r"], ".3f"),
                   "robust": "PASS" if r["robust"] else "REFUSED",
                   "error": r.get("error") or ""}
                  for r in rows]
        out.append(table(pretty, ["value", "trades", "return%", "maxDD%",
                                  "avgR", "robust", "error"]))
    if report.get("inert_parameters"):
        out.append("")
        out.append("  INERT PARAMETERS (declared, not tuned):")
        for p in report["inert_parameters"]:
            out.append(f"    - {p}")
    out.append("")
    out.append(f"  {report.get('note', '')}")
    out.append(BAR)
    return "\n".join(out)


def render_status(state: Mapping[str, Any]) -> str:
    """The live/paper terminal dashboard (spec 16)."""
    out = [BAR,
           f"DOWNTREND ENSEMBLE  |  mode {state.get('mode', '?').upper()}"
           f"  |  {ts(state.get('ts'))}",
           BAR]
    out.append(f"  regime {str(state.get('regime', '-')):<18}"
               f"risk multiplier {fmt(state.get('risk_multiplier'), '.2f'):>6}"
               f"     entries {'DISABLED' if state.get('entries_disabled') else 'enabled'}")
    out.append(f"  equity {fmt(state.get('equity')):>12}"
               f"   day P&L {fmt(state.get('day_pnl')):>10}"
               f"   week P&L {fmt(state.get('week_pnl')):>10}")
    out.append(f"  exposure {pct(state.get('exposure_pct')):>10}"
               f"   effective bets {fmt(state.get('effective_bets'), '.2f'):>6}"
               f"   margin used {pct(state.get('margin_pct')):>8}")
    if state.get("halts"):
        out.append("")
        out.append("  HALTS IN FORCE")
        for h in state["halts"]:
            out.append(f"    ! {h}")

    out.append("")
    out.append("  OPEN POSITIONS")
    rows = []
    for p in state.get("positions", []) or []:
        rows.append({"symbol": p.get("symbol"), "side": p.get("side"),
                     "qty": fmt(p.get("quantity"), ".6f"),
                     "entry": fmt(p.get("entry_price"), ".6g"),
                     "stop": fmt(p.get("stop_price"), ".6g"),
                     "R": fmt(p.get("r_multiple"), ".2f"),
                     "uPnL": fmt(p.get("unrealized"), ".2f"),
                     "held_h": fmt(p.get("held_h"), ".1f"),
                     "protected": "yes" if p.get("protective_ok") else "NO"})
    out.append(table(rows, ["symbol", "side", "qty", "entry", "stop", "R",
                            "uPnL", "held_h", "protected"]))

    hs = state.get("strategy_health") or {}
    if hs:
        out.append("")
        out.append("  STRATEGY HEALTH")
        rows = [{"strategy": k,
                 "state": v.get("state"),
                 "n": v.get("trades"),
                 "PF": fmt(v.get("profit_factor"), ".2f"),
                 "expectancy": fmt(v.get("expectancy"), ".3f"),
                 "streak": v.get("consecutive_losses"),
                 "dd": pct(None if v.get("drawdown_frac") is None
                           else v["drawdown_frac"] * 100)}
                for k, v in sorted(hs.items())]
        out.append(table(rows, ["strategy", "state", "n", "PF", "expectancy",
                                "streak", "dd"]))

    cps = state.get("changepoints") or []
    if cps:
        out.append("")
        out.append("  CHANGE POINTS")
        for c in cps[:6]:
            out.append(f"    {c.get('metric')}: {c.get('severity')} "
                       f"(z {fmt(c.get('z'), '.2f')})  {c.get('note', '')}")

    rec = state.get("recent_decisions") or []
    if rec:
        out.append("")
        out.append("  RECENT DECISIONS")
        for d in rec[:10]:
            out.append(f"    {ts(d.get('ts'))}  {str(d.get('action')):<7}"
                       f"{str(d.get('symbol')):<14}{d.get('reason', '')[:60]}")
    out.append(BAR)
    return "\n".join(out)
