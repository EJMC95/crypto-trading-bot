#!/usr/bin/env python3
"""Offline Lighter safety-vs-edge sizing analysis.

This tool is deliberately not imported by a live bot and never places orders.
It compares gross-sizing candidates against the same measured trade tape so a
safety change cannot be promoted merely because it lowers drawdown.

Input JSON::

    {
      "baseline_gross": 10.0,
      "stop_frac": 0.10,
      "mmf": 0.06,
      "overshoot_bps": 0.0,
      "trades": [{"pnl_usd": 1.20}, {"pnl_usd": -0.80}]
    }

``pnl_usd`` must be the realised net P&L at the baseline gross, after fees
and slippage. Scaling is a sizing sensitivity, not a claim that fills or
throughput are unchanged; the report labels it accordingly.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _positive(name: str, value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def stop_alive_ceiling(stop_frac: float, mmf: float, overshoot_frac: float = 0.0) -> float:
    """Strict upper bound where the protective stop still beats liquidation."""
    stop = _positive("stop_frac", stop_frac)
    maintenance = _positive("mmf", mmf)
    overshoot = float(overshoot_frac)
    if not math.isfinite(overshoot) or overshoot < 0:
        raise ValueError("overshoot_frac must be finite and non-negative")
    return 1.0 / (stop + maintenance + overshoot)


def reserve_ceiling(
    stop_frac: float,
    mmf: float,
    headroom_k: float = 1.0,
    overshoot_frac: float = 0.0,
) -> float:
    """Upper bound for a requested liquidation-distance reserve in stop widths."""
    stop = _positive("stop_frac", stop_frac)
    k = _positive("headroom_k", headroom_k)
    maintenance = _positive("mmf", mmf)
    overshoot = float(overshoot_frac)
    if not math.isfinite(overshoot) or overshoot < 0:
        raise ValueError("overshoot_frac must be finite and non-negative")
    return 1.0 / (maintenance + overshoot + k * stop)


@dataclass(frozen=True)
class Metrics:
    gross: float
    safe_stop: bool
    total_pnl_usd: float
    expectancy_usd: float
    max_drawdown_usd: float
    win_rate: float
    n: int


def metrics_at_gross(
    trades: list[dict[str, Any]], baseline_gross: float, gross: float, ceiling: float
) -> Metrics:
    base = _positive("baseline_gross", baseline_gross)
    candidate = _positive("gross", gross)
    scaled: list[float] = []
    for index, trade in enumerate(trades):
        if not isinstance(trade, dict):
            raise ValueError(f"trade {index} must be an object")
        try:
            pnl = float(trade["pnl_usd"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"trade {index} needs numeric pnl_usd") from exc
        if not math.isfinite(pnl):
            raise ValueError(f"trade {index} pnl_usd must be finite")
        scaled.append(pnl * candidate / base)
    running = peak = drawdown = 0.0
    for pnl in scaled:
        running += pnl
        peak = max(peak, running)
        drawdown = max(drawdown, peak - running)
    total = sum(scaled)
    return Metrics(
        gross=candidate,
        safe_stop=candidate < ceiling - 1e-9,
        total_pnl_usd=total,
        expectancy_usd=total / len(scaled) if scaled else 0.0,
        max_drawdown_usd=drawdown,
        win_rate=sum(pnl > 0 for pnl in scaled) / len(scaled) if scaled else 0.0,
        n=len(scaled),
    )


def report(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    baseline = _positive("baseline_gross", payload.get("baseline_gross"))
    stop = _positive("stop_frac", payload.get("stop_frac"))
    mmf = _positive("mmf", payload.get("mmf"))
    overshoot = float(payload.get("overshoot_bps", 0.0)) / 10000.0
    ceiling = stop_alive_ceiling(stop, mmf, overshoot)
    reserve = reserve_ceiling(stop, mmf, 4.0, overshoot)
    trades = payload.get("trades") or []
    if not isinstance(trades, list):
        raise ValueError("trades must be a list")
    requested = payload.get("candidate_gross")
    candidates = requested if isinstance(requested, list) else [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, ceiling]
    rows = [metrics_at_gross(trades, baseline, value, ceiling).__dict__ for value in candidates]
    return {
        "baseline_gross": baseline,
        "stop_frac": stop,
        "mmf": mmf,
        "overshoot_bps": overshoot * 10000.0,
        "stop_alive_ceiling": ceiling,
        "reserve_4_stop_width_ceiling": reserve,
        "caveat": "sizing sensitivity only; re-test fills, throughput, fees and slippage before promotion",
        "candidates": rows,
    }


def _selftest() -> None:
    assert round(stop_alive_ceiling(0.10, 0.06), 6) == round(6.25, 6)
    assert round(reserve_ceiling(0.10, 0.06, 4), 6) == round(2.1739130435, 6)
    sample = {"baseline_gross": 10, "stop_frac": 0.10, "mmf": 0.06, "trades": [{"pnl_usd": 10}, {"pnl_usd": -4}]}
    result = report(sample)
    assert result["candidates"][0]["total_pnl_usd"] == 0.6
    assert result["candidates"][-1]["safe_stop"] is False
    try:
        stop_alive_ceiling(0, 0.06)
    except ValueError:
        pass
    else:
        raise AssertionError("zero stop must refuse")
    print("edge_aware_safety self-tests passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JSON input file")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return
    if not args.input:
        parser.error("--input is required unless --selftest is used")
    print(json.dumps(report(json.loads(args.input.read_text())), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
