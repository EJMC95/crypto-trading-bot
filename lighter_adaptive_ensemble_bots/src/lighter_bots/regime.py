"""MarketRegimeEngine — six states, with hysteresis.

WHY HYSTERESIS IS NOT OPTIONAL. A regime that flips on a single closed bar
turns every threshold into a coin flip near the boundary, and the strategy
permissions hanging off it (no longs in BEARISH, no entries in PANIC) then
oscillate. `minimum_confirmation_candles` requires the SAME candidate state on
N consecutive closed bars before the engine moves. The three states that mean
'something is wrong' -- PANIC, HIGH_VOLATILITY, DATA_UNRELIABLE -- bypass the
delay in the RESTRICTIVE direction only: they arm immediately and still need
confirmations to clear. Fast to protect, slow to relax.

DATA_UNRELIABLE is a first-class state rather than an exception. A stale feed,
a missing price or a failed reconciliation must produce a REGIME the rest of
the system already knows how to refuse to trade in -- not a traceback in a
loop that then continues.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from . import indicators as ind
from .config import RegimeConfig
from .logging_setup import get
from .models import Candle, Regime

log = get("regime")

RESTRICTIVE = (Regime.PANIC, Regime.DATA_UNRELIABLE, Regime.HIGH_VOLATILITY)


@dataclass
class RegimeInputs:
    """Everything the engine reads. Assembled by the caller so the engine
    stays pure and exhaustively testable."""
    btc_4h: Sequence[Candle] = field(default_factory=list)
    btc_1h: Sequence[Candle] = field(default_factory=list)
    breadth_up_frac: float | None = None      # share of liquid markets above EMA50
    atr_percentile: float | None = None
    realized_vol: float | None = None
    volume_ratio: float | None = None         # last bar vs 20-bar mean
    funding_rate: float | None = None
    open_interest_change: float | None = None
    liquidation_burst: bool = False
    spread_bps: float | None = None
    depth_usd: float | None = None
    data_ok: bool = True
    data_problems: list[str] = field(default_factory=list)


@dataclass
class RegimeVerdict:
    regime: Regime
    candidate: Regime
    confirmations: int
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def tradable(self) -> bool:
        return self.regime not in (Regime.PANIC, Regime.DATA_UNRELIABLE)


class MarketRegimeEngine:
    def __init__(self, cfg: RegimeConfig):
        self.cfg = cfg
        self.state = Regime.NEUTRAL
        self._candidate = Regime.NEUTRAL
        self._streak = 0
        self.history: list[tuple[float, Regime, Regime]] = []

    # ------------------------------------------------------------ scoring --
    @staticmethod
    def _trend(candles: Sequence[Candle]) -> dict[str, Any]:
        c = [x.close for x in candles]
        if len(c) < 210:
            return {"ok": False}
        e50, e200 = ind.ema(c, 50), ind.ema(c, 200)
        i = len(c) - 1
        if e50[i] is None or e200[i] is None:
            return {"ok": False}
        return {"ok": True, "e50_above": e50[i] > e200[i],
                "px_above_e50": c[i] > e50[i],
                "e50": e50[i], "e200": e200[i], "close": c[i]}

    @staticmethod
    def _lower_structure(candles: Sequence[Candle], look: int = 40) -> bool:
        """Lower highs AND lower lows over the recent window -- the structural
        half of BEARISH, so the state is not purely a moving-average artifact."""
        if len(candles) < look + 2:
            return False
        h = [x.high for x in candles][-look:]
        l = [x.low for x in candles][-look:]
        half = look // 2
        return (max(h[half:]) < max(h[:half])) and (min(l[half:]) < min(l[:half]))

    def classify(self, inp: RegimeInputs) -> tuple[Regime, list[str]]:
        """The candidate state for THIS closed bar, before hysteresis."""
        reasons: list[str] = []
        if not inp.data_ok:
            return Regime.DATA_UNRELIABLE, (inp.data_problems
                                            or ["data marked unreliable"])
        t4 = self._trend(inp.btc_4h)
        t1 = self._trend(inp.btc_1h)
        if not t4.get("ok"):
            return Regime.DATA_UNRELIABLE, ["BTC 4h series too short to grade"]

        if inp.liquidation_burst:
            reasons.append("liquidation burst")
        panic_spread = (inp.spread_bps is not None and inp.spread_bps > 50.0)
        if panic_spread:
            reasons.append(f"spread {inp.spread_bps:.1f}bps severe")
        crash = (inp.breadth_up_frac is not None and inp.breadth_up_frac < 0.10
                 and t4["close"] < t4["e50"])
        if crash:
            reasons.append(f"breadth {inp.breadth_up_frac:.2f} with BTC below "
                           "its 4h EMA50")
        if inp.liquidation_burst or panic_spread or crash:
            return Regime.PANIC, reasons

        if inp.atr_percentile is not None \
                and inp.atr_percentile >= self.cfg.high_volatility_atr_percentile:
            return Regime.HIGH_VOLATILITY, [
                f"ATR percentile {inp.atr_percentile:.0f} >= "
                f"{self.cfg.high_volatility_atr_percentile:.0f}"]

        breadth = inp.breadth_up_frac
        bull = (t4["e50_above"] and t4["px_above_e50"]
                and (breadth is None or breadth >= 0.45))
        bear = ((not t4["e50_above"]) and (not t4["px_above_e50"])
                and (breadth is None or breadth <= 0.55)
                and self._lower_structure(inp.btc_4h))
        if bull:
            reasons.append("BTC 4h EMA50>EMA200, price above EMA50"
                           + (f", breadth {breadth:.2f}" if breadth else ""))
            if t1.get("ok") and not t1["e50_above"]:
                reasons.append("1h trend disagrees (confirmation only)")
            return Regime.BULLISH, reasons
        if bear:
            reasons.append("BTC 4h EMA50<EMA200, price below EMA50, lower "
                           "highs and lower lows"
                           + (f", breadth {breadth:.2f}" if breadth else ""))
            return Regime.BEARISH, reasons
        reasons.append("no confirmed directional structure")
        return Regime.NEUTRAL, reasons

    # ---------------------------------------------------------- hysteresis --
    def update(self, inp: RegimeInputs, ts: float | None = None) -> RegimeVerdict:
        cand, reasons = self.classify(inp)
        need = max(1, int(self.cfg.minimum_confirmation_candles))

        if cand == self._candidate:
            self._streak += 1
        else:
            self._candidate, self._streak = cand, 1

        prev = self.state
        if cand == self.state:
            pass                                    # already there
        elif cand in RESTRICTIVE:
            self.state = cand                       # arm immediately
        elif self._streak >= need:
            self.state = cand                       # relax only on confirmation

        if self.state is not prev:
            log.info("regime %s -> %s (%s)", prev.value, self.state.value,
                     "; ".join(reasons) or "n/a")
            self.history.append((ts or 0.0, prev, self.state))

        return RegimeVerdict(
            regime=self.state, candidate=cand, confirmations=self._streak,
            reasons=reasons,
            detail={"breadth": inp.breadth_up_frac,
                    "atr_pct": inp.atr_percentile,
                    "spread_bps": inp.spread_bps,
                    "funding": inp.funding_rate,
                    "needed_confirmations": need})


def risk_multiplier(cfg: RegimeConfig, regime: Regime, side: str) -> float:
    """The permission table, as one function. `0.0` means NO ENTRY."""
    if regime is Regime.PANIC or regime is Regime.DATA_UNRELIABLE:
        return 0.0
    if regime is Regime.HIGH_VOLATILITY:
        return cfg.high_volatility_risk_multiplier
    if regime is Regime.BULLISH:
        return (cfg.bullish_long_risk_multiplier if side == "long"
                else cfg.bullish_short_risk_multiplier)
    if regime is Regime.BEARISH:
        return (cfg.bearish_long_risk_multiplier if side == "long"
                else cfg.bearish_short_risk_multiplier)
    return cfg.neutral_risk_multiplier


def breadth(closes_by_symbol: dict[str, Sequence[float]], n: int = 50
            ) -> float | None:
    """Share of markets trading above their own EMA(n). None when too few
    markets can be graded -- an unmeasurable breadth must not read as 0.0,
    which would look like a crash."""
    up = total = 0
    for _sym, c in closes_by_symbol.items():
        if len(c) < n + 5:
            continue
        e = ind.ema(list(c), n)
        if e[-1] is None:
            continue
        total += 1
        up += 1 if c[-1] > e[-1] else 0
    if total < 5:
        return None
    return up / total


def atr_percentile_now(candles: Sequence[Candle], n: int = 14,
                       window: int = 240) -> float | None:
    """Where the CURRENT ATR sits in its own recent distribution, as a
    percentile 0-100."""
    if len(candles) < n + 30:
        return None
    h = [c.high for c in candles]
    l = [c.low for c in candles]
    c_ = [c.close for c in candles]
    series = [x for x in ind.atr(h, l, c_, n)[-window:] if x is not None]
    if len(series) < 30:
        return None
    cur = series[-1]
    below = sum(1 for x in series if x <= cur)
    return 100.0 * below / len(series)
