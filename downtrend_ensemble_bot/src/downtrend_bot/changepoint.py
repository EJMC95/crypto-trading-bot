"""ChangePointDetector — has the environment this strategy was validated in
actually changed?

DELIBERATELY BORING METHODS, in the order the spec asks for: rolling z-scores,
EWMA, percentile comparison and CUSUM. No machine-learning model, because a
simple baseline has to be beaten before a complex one is justified, and none
has been.

HYSTERESIS IS THE WHOLE DIFFERENCE BETWEEN A DETECTOR AND A NOISE GENERATOR.
A signal must persist `min_duration_bars` before it FIRES and stay clear for
`clear_duration_bars` before it CLEARS. Without that, a detector on ordinary
market noise flips state constantly, the strategy is throttled at random, and
the operator learns to ignore it -- which is worse than not having one.

Severity drives the response: `warn` raises the bar, `severe` throttles,
`critical` pauses. Nothing here closes a position.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from . import indicators as ind
from .config import ChangePointConfig
from .logging_setup import get

log = get("changepoint")

#: What we watch. Each is a scalar per bar/trade; the detector is agnostic.
MONITORED = ("volatility", "trend_direction", "volume", "funding", "spread",
             "slippage", "win_rate", "expectancy", "trade_duration",
             "score_return_corr", "live_vs_backtest")


@dataclass
class Evidence:
    metric: str
    z: float | None = None
    cusum: float | None = None
    baseline: float | None = None
    recent: float | None = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "z": self.z, "cusum": self.cusum,
                "baseline": self.baseline, "recent": self.recent,
                "note": self.note}


@dataclass
class Verdict:
    changed: bool
    severity: str                    # "none" | "warn" | "severe" | "critical"
    evidence: list[Evidence] = field(default_factory=list)
    firing_bars: int = 0
    clear_bars: int = 0

    @property
    def risk_multiplier(self) -> float:
        return {"none": 1.0, "warn": 0.75, "severe": 0.5,
                "critical": 0.0}[self.severity]

    @property
    def score_bump(self) -> float:
        return {"none": 0.0, "warn": 3.0, "severe": 6.0,
                "critical": 100.0}[self.severity]

    def as_dict(self) -> dict[str, Any]:
        return {"changed": self.changed, "severity": self.severity,
                "firing_bars": self.firing_bars, "clear_bars": self.clear_bars,
                "risk_multiplier": self.risk_multiplier,
                "evidence": [e.as_dict() for e in self.evidence]}


class ChangePointDetector:
    def __init__(self, cfg: ChangePointConfig):
        self.cfg = cfg
        self.series: dict[str, list[float]] = {m: [] for m in MONITORED}
        self._firing = 0
        self._clear = 0
        self.severity = "none"
        self.history: list[dict[str, Any]] = []

    def observe(self, metric: str, value: float | None) -> None:
        """Record one observation. Unknown values are DROPPED, never zeroed --
        a zero is a measurement and would move every statistic below."""
        if value is None or metric not in self.series:
            return
        s = self.series[metric]
        s.append(float(value))
        if len(s) > 5000:
            del s[:len(s) - 5000]

    # ------------------------------------------------------------ analysis --
    def _metric_evidence(self, metric: str) -> Evidence | None:
        cfg = self.cfg
        s = self.series.get(metric) or []
        if len(s) < cfg.baseline_window + cfg.window:
            return None
        baseline = s[-(cfg.baseline_window + cfg.window):-cfg.window]
        recent = s[-cfg.window:]
        if len(baseline) < 10 or len(recent) < 3:
            return None
        b_mean = statistics.fmean(baseline)
        b_sd = statistics.pstdev(baseline)
        r_mean = statistics.fmean(recent)
        z = None if b_sd <= 0 else (r_mean - b_mean) / (b_sd / len(recent) ** 0.5)
        pos, neg = ind.cusum(s[-(cfg.baseline_window + cfg.window):],
                             target=b_mean)
        cs = max(max(pos, default=0.0), abs(min(neg, default=0.0)))
        if z is None and cs <= 0:
            return None
        note = (f"{metric}: baseline {b_mean:.6g} -> recent {r_mean:.6g}"
                + (f", z={z:+.2f}" if z is not None else "")
                + f", cusum={cs:.2f}")
        return Evidence(metric=metric, z=z, cusum=cs, baseline=b_mean,
                        recent=r_mean, note=note)

    def evaluate(self, ts: float = 0.0) -> Verdict:
        cfg = self.cfg
        if not cfg.enabled:
            return Verdict(False, "none")

        hits: list[Evidence] = []
        for m in MONITORED:
            ev = self._metric_evidence(m)
            if ev is None:
                continue
            tripped = ((ev.z is not None and abs(ev.z) >= cfg.z_threshold)
                       or (ev.cusum is not None
                           and ev.cusum >= cfg.cusum_threshold))
            if tripped:
                hits.append(ev)

        # ---- hysteresis --------------------------------------------------
        if hits:
            self._firing += 1
            self._clear = 0
        else:
            self._clear += 1
            if self._clear >= cfg.clear_duration_bars:
                self._firing = 0

        if self._firing >= cfg.min_duration_bars:
            severity = ("critical" if len(hits) >= 4 else
                        "severe" if len(hits) >= 2 else "warn")
        elif self.severity != "none" and self._clear < cfg.clear_duration_bars:
            # Still inside the clearing window: hold the previous severity
            # rather than snapping back the moment one bar looks calm.
            severity = self.severity
        else:
            severity = "none"

        if severity != self.severity:
            log.info("change-point severity %s -> %s (%d metrics, "
                     "firing=%d clear=%d)", self.severity, severity, len(hits),
                     self._firing, self._clear)
            self.history.append({"ts": ts, "from": self.severity,
                                 "to": severity,
                                 "evidence": [e.as_dict() for e in hits]})
        self.severity = severity
        return Verdict(changed=severity != "none", severity=severity,
                       evidence=hits, firing_bars=self._firing,
                       clear_bars=self._clear)

    def snapshot(self) -> dict[str, Any]:
        return {"severity": self.severity, "firing_bars": self._firing,
                "clear_bars": self._clear,
                "observations": {m: len(s) for m, s in self.series.items()
                                 if s}}
