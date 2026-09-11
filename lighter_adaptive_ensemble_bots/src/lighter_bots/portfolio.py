"""Open-book accounting: exposure, correlation groups and effective bets.

`n_eff` IS THE POINT. A book holding nine crypto longs does not hold nine
bets; on a venue whose majors run pairwise correlation ~0.5 it holds closer to
one and a half. Reporting a SYMBOL COUNT as diversification is the specific
error this module refuses to make: `effective_bets` is computed from the
correlation matrix of realised returns, and when correlations cannot be
measured it degrades to 1.0 -- ONE BET -- which is the conservative direction.
Degrading to the symbol count would claim diversification nobody measured.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from .models import Position, Trade
from .risk import ExposureState

#: Coarse groups for the correlation multiplier when a measured matrix is not
#: available. Crude on purpose and used only to SIZE DOWN.
DEFAULT_GROUPS = {"BTC": "majors", "ETH": "majors", "SOL": "majors",
                  "BNB": "majors", "XRP": "majors", "DOGE": "alt",
                  "SPY": "equity", "QQQ": "equity", "IWM": "equity",
                  "NVDA": "equity", "WTI": "commodity", "XAU": "commodity",
                  "XAG": "commodity", "XCU": "commodity"}


def group_of(symbol: str) -> str:
    return DEFAULT_GROUPS.get(symbol, "crypto")


def returns(closes: Sequence[float]) -> list[float]:
    out = []
    for i in range(1, len(closes)):
        p0 = closes[i - 1]
        if p0 > 0:
            out.append(closes[i] / p0 - 1.0)
    return out


def correlation(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 20:
        return None
    a, b = list(a[-n:]), list(b[-n:])
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def effective_bets(symbols: Sequence[str],
                   closes_by_symbol: dict[str, Sequence[float]]) -> float:
    """N / (1 + (N-1) * mean pairwise rho), floored at 1.0.

    An unmeasurable pair contributes rho = 1.0 (perfectly correlated), so a
    dark price feed can only ever REDUCE the claimed diversification."""
    syms = [s for s in dict.fromkeys(symbols)]
    n = len(syms)
    if n <= 1:
        return float(n)
    rets = {s: returns(closes_by_symbol.get(s) or []) for s in syms}
    rhos: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            r = correlation(rets.get(syms[i]) or [], rets.get(syms[j]) or [])
            rhos.append(1.0 if r is None else max(-0.99, min(1.0, r)))
    mean_rho = sum(rhos) / len(rhos)
    denom = 1.0 + (n - 1) * mean_rho
    if denom <= 0:
        return float(n)
    return max(1.0, n / denom)


@dataclass
class Book:
    """Live positions plus the day/week P&L the loss lockouts read."""
    positions: dict[str, Position] = field(default_factory=dict)
    closed: list[Trade] = field(default_factory=list)
    day_pnl: float = 0.0
    week_pnl: float = 0.0
    realized: float = 0.0

    def open_risk(self) -> float:
        total = 0.0
        for p in self.positions.values():
            total += abs(p.entry_price - p.stop_price) * p.quantity
        return total

    def exposure(self, marks: dict[str, float] | None = None) -> ExposureState:
        marks = marks or {}
        gross = long_n = short_n = 0.0
        per_market: dict[str, float] = {}
        groups: dict[str, int] = {}
        for sym, p in self.positions.items():
            px = marks.get(sym, p.entry_price)
            notional = abs(p.quantity) * px
            gross += notional
            per_market[sym] = per_market.get(sym, 0.0) + notional
            if p.side == "long":
                long_n += notional
            else:
                short_n += notional
            g = group_of(sym)
            groups[g] = groups.get(g, 0) + 1
        return ExposureState(
            open_positions=len(self.positions), open_risk=self.open_risk(),
            gross_notional=gross, net_long_notional=long_n,
            net_short_notional=short_n, per_market_notional=per_market,
            day_pnl=self.day_pnl, week_pnl=self.week_pnl,
            correlation_group_count=groups)

    def unrealized(self, marks: dict[str, float]) -> float:
        return sum(p.unrealized(marks.get(s, p.entry_price))
                   for s, p in self.positions.items())

    def summary(self, marks: dict[str, float] | None = None) -> dict[str, Any]:
        marks = marks or {}
        exp = self.exposure(marks)
        return {"open": len(self.positions), "closed": len(self.closed),
                "realized": round(self.realized, 4),
                "unrealized": round(self.unrealized(marks), 4),
                "gross_notional": round(exp.gross_notional, 2),
                "net_long": round(exp.net_long_notional, 2),
                "net_short": round(exp.net_short_notional, 2),
                "open_risk": round(exp.open_risk, 4),
                "day_pnl": round(self.day_pnl, 4),
                "week_pnl": round(self.week_pnl, 4),
                "held": {s: ("S" if p.side == "short" else "L")
                         for s, p in self.positions.items()}}
