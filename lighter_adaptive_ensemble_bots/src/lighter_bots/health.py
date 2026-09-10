"""System health: is the machine fit to trade RIGHT NOW?

Distinct from `strategy_health`, which asks whether a STRATEGY still works.
This module asks whether the plumbing is trustworthy, and it fails CLOSED:
anything it cannot verify counts as a problem, because on this path the cost
of a wrong "healthy" is an order sent on stale data.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from .data import is_fresh, staleness_s
from .models import Candle, Regime


@dataclass
class HealthCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SystemHealth:
    checks: list[HealthCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def failures(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if not c.ok]

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(HealthCheck(name, bool(ok), detail))

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok,
                "checks": {c.name: {"ok": c.ok, "detail": c.detail}
                           for c in self.checks},
                "failures": self.failures()}

    def render(self) -> str:
        w = max((len(c.name) for c in self.checks), default=10)
        lines = [f"  [{'ok ' if c.ok else 'FAIL'}] {c.name:<{w}}  {c.detail}"
                 for c in self.checks]
        return "\n".join(["SYSTEM HEALTH: "
                          + ("OK" if self.ok else "NOT HEALTHY")] + lines)


def kill_switch_path(runtime_dir: str) -> str:
    return os.path.join(runtime_dir, "KILL_SWITCH")


def kill_switch_active(runtime_dir: str) -> bool:
    return os.path.exists(kill_switch_path(runtime_dir))


def check(*, runtime_dir: str, metadata_version: str | None,
          metadata_age_s: float | None, candles: dict[str, list[Candle]],
          timeframe: str, ws_health: dict[str, Any] | None,
          nonce_ok: tuple[bool, str] | None,
          account_reconciled: bool, regime: Regime | None,
          max_metadata_age_s: float = 24 * 3600.0) -> SystemHealth:
    h = SystemHealth()
    h.add("kill_switch_absent", not kill_switch_active(runtime_dir),
          "KILL_SWITCH present -- entries halted"
          if kill_switch_active(runtime_dir) else "no kill switch")
    h.add("market_metadata", bool(metadata_version),
          f"version {metadata_version}" if metadata_version
          else "no metadata snapshot: REFUSE to trade")
    if metadata_age_s is not None:
        h.add("metadata_fresh", metadata_age_s <= max_metadata_age_s,
              f"{metadata_age_s / 3600.0:.1f}h old")
    stale = {s: round(staleness_s(cs, timeframe), 1)
             for s, cs in candles.items()
             if not is_fresh(cs, timeframe, tolerance_bars=2.0)}
    h.add("candles_fresh", not stale,
          "all series current" if not stale else f"stale: {stale}")
    h.add("candles_present", bool(candles),
          f"{len(candles)} series" if candles else "no candle series at all")
    if ws_health is not None:
        h.add("websocket", bool(ws_health.get("connected")),
              f"stale {ws_health.get('stale_s')}s, "
              f"reconnects {ws_health.get('reconnects')}")
    if nonce_ok is not None:
        h.add("nonce_manager", nonce_ok[0], nonce_ok[1])
    h.add("account_reconciled", bool(account_reconciled),
          "reconciled with the venue" if account_reconciled
          else "NOT reconciled: refuse new entries")
    if regime is not None:
        h.add("regime_tradable",
              regime not in (Regime.PANIC, Regime.DATA_UNRELIABLE),
              regime.value)
    return h
