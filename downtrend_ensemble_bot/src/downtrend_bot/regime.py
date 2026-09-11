"""MarketRegimeEngine — six states, closed candles only, with hysteresis.

WHY HYSTERESIS IS NOT OPTIONAL. A regime that flips on a single closed bar
turns every threshold into a coin flip near the boundary, and the permissions
hanging off it (no new longs in BEARISH, no entries in PANIC) then oscillate.
`minimum_regime_confirmation_candles` requires the SAME candidate on N
consecutive closed bars before the engine moves.

ONE ASYMMETRY, and it is the design: the three "something is wrong" states --
PANIC, HIGH_VOLATILITY, DATA_UNRELIABLE -- arm IMMEDIATELY and still need
confirmations to clear. Fast to protect, slow to relax.

DATA_UNRELIABLE is a first-class state rather than an exception. A stale feed,
a missing funding print or a failed reconciliation must produce a REGIME the
rest of the system already knows how to refuse to trade in -- not a traceback
inside a loop that then carries on.

BTC IS TREATED DIFFERENTLY ON PURPOSE (spec 5): it drives the whole market, so
shorting it requires MORE confirmation than shorting an alt, and
`btc_short_confirmed` is the extra gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Sequence

from . import indicators as ind
from .config import RegimeConfig
from .logging_setup import get
from .models import Candle, Regime

if TYPE_CHECKING:                       # import cycle: config imports models,
    from .config import StrategyConfig  # regime imports config only for a type

log = get("regime")

#: States that arm immediately and clear slowly.
RESTRICTIVE = (Regime.PANIC, Regime.DATA_UNRELIABLE, Regime.HIGH_VOLATILITY)


@dataclass
class RegimeInputs:
    """Everything the engine reads. Assembled by the caller so the engine
    stays pure and exhaustively testable."""
    btc_4h: Sequence[Candle] = field(default_factory=list)
    btc_1h: Sequence[Candle] = field(default_factory=list)
    breadth_20: float | None = None       # share of tracked assets above EMA20
    breadth_50: float | None = None
    atr_percentile: float | None = None
    realized_vol: float | None = None
    realized_vol_median: float | None = None
    total_volume_ratio: float | None = None
    funding_rate: float | None = None
    open_interest_change: float | None = None
    risk_proxy: float | None = None       # e.g. stablecoin dominance change
    spread_bps: float | None = None
    depth_usd: float | None = None
    liquidation_intensity: float | None = None
    data_ok: bool = True
    data_problems: list[str] = field(default_factory=list)


@dataclass
class RegimeVerdict:
    regime: Regime
    candidate: Regime
    confirmations: int
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)
    transitioned: bool = False

    @property
    def tradable(self) -> bool:
        return self.regime not in (Regime.PANIC, Regime.DATA_UNRELIABLE)


@dataclass
class Transition:
    ts: float
    previous: Regime
    new: Regime
    reasons: list[str]
    affected_symbols: list[str] = field(default_factory=list)
    open_positions: list[str] = field(default_factory=list)
    entries_disabled: bool = False
    risk_reduced: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "previous": self.previous.value,
                "new": self.new.value, "reasons": self.reasons,
                "affected_symbols": self.affected_symbols,
                "open_positions": self.open_positions,
                "entries_disabled": self.entries_disabled,
                "risk_reduced": self.risk_reduced}


def _trend(candles: Sequence[Candle], window: int = 20) -> dict[str, Any]:
    c = [x.close for x in candles]
    h = [x.high for x in candles]
    l = [x.low for x in candles]
    if len(c) < 210:
        return {"ok": False, "why": f"only {len(c)} closed bars, need 210"}
    e50, e200 = ind.ema(c, 50), ind.ema(c, 200)
    i = len(c) - 1
    if e50[i] is None or e200[i] is None:
        return {"ok": False, "why": "EMA warm-up incomplete"}
    return {"ok": True,
            "e50_above": e50[i] > e200[i],
            "px_above_e50": c[i] > e50[i],
            "higher_high": ind.made_higher_high(h, i, window),
            "lower_low": ind.made_lower_low(l, i, window),
            "e50": e50[i], "e200": e200[i], "close": c[i]}


class MarketRegimeEngine:
    def __init__(self, cfg: RegimeConfig):
        self.cfg = cfg
        self.state = Regime.NEUTRAL
        self._candidate = Regime.NEUTRAL
        self._streak = 0
        self._bearish_streak = 0
        self.transitions: list[Transition] = []

    # ------------------------------------------------------------ classify --
    def classify(self, inp: RegimeInputs) -> tuple[Regime, list[str]]:
        """The candidate for THIS closed bar, before hysteresis."""
        if not inp.data_ok:
            return Regime.DATA_UNRELIABLE, (inp.data_problems
                                            or ["data marked unreliable"])
        t4 = _trend(inp.btc_4h, self.cfg.__dict__.get("structure_window", 20))
        if not t4.get("ok"):
            return Regime.DATA_UNRELIABLE, [f"BTC 4h: {t4.get('why')}"]

        reasons: list[str] = []
        # ---- PANIC: market-wide stress, however it shows up ---------------
        panic = []
        if inp.liquidation_intensity is not None and inp.liquidation_intensity > 3.0:
            panic.append(f"liquidation intensity {inp.liquidation_intensity:.1f}x")
        if inp.spread_bps is not None and inp.spread_bps > 50.0:
            panic.append(f"spread {inp.spread_bps:.1f}bps severe")
        if (inp.breadth_20 is not None and inp.breadth_20 < 0.10
                and not t4["px_above_e50"]):
            panic.append(f"breadth {inp.breadth_20:.2f} with BTC below its "
                         "4h EMA50")
        if panic:
            return Regime.PANIC, panic

        # ---- HIGH_VOLATILITY ---------------------------------------------
        hv = []
        if inp.atr_percentile is not None \
                and inp.atr_percentile >= self.cfg.high_volatility_atr_percentile:
            hv.append(f"ATR percentile {inp.atr_percentile:.0f} >= "
                      f"{self.cfg.high_volatility_atr_percentile:.0f}")
        if (inp.realized_vol is not None and inp.realized_vol_median
                and inp.realized_vol > 2.0 * inp.realized_vol_median):
            hv.append(f"realised vol {inp.realized_vol:.4f} > 2x its median")
        if inp.spread_bps is not None and inp.spread_bps > 3.0 * self.cfg.__dict__.get(
                "_normal_spread_bps", 8.0):
            hv.append(f"spread {inp.spread_bps:.1f}bps abnormal")
        if hv:
            return Regime.HIGH_VOLATILITY, hv

        # ---- directional --------------------------------------------------
        breadth = inp.breadth_20
        thr = self.cfg.market_breadth_threshold
        bull = (t4["e50_above"] and t4["px_above_e50"]
                and (breadth is None or breadth >= thr))
        bear = ((not t4["e50_above"]) and (not t4["px_above_e50"])
                and (breadth is None or breadth <= (1.0 - thr))
                and (t4["lower_low"] or not t4["higher_high"]))
        if bull:
            reasons.append(
                "BTC 4h EMA50>EMA200 and price above EMA50"
                + (f", breadth {breadth:.2f} >= {thr:.2f}" if breadth is not None
                   else ""))
            return Regime.BULLISH, reasons
        if bear:
            reasons.append(
                "BTC 4h EMA50<EMA200, price below EMA50, "
                + ("lower low present" if t4["lower_low"]
                   else "no higher high in structure")
                + (f", breadth {breadth:.2f}" if breadth is not None else ""))
            return Regime.BEARISH, reasons
        reasons.append("no confirmed directional structure")
        return Regime.NEUTRAL, reasons

    # ---------------------------------------------------------- hysteresis --
    def update(self, inp: RegimeInputs, ts: float = 0.0, *,
               symbols: Sequence[str] = (), open_positions: Sequence[str] = ()
               ) -> RegimeVerdict:
        cand, reasons = self.classify(inp)
        need = max(1, int(self.cfg.minimum_regime_confirmation_candles))

        if cand == self._candidate:
            self._streak += 1
        else:
            self._candidate, self._streak = cand, 1
        self._bearish_streak = (self._bearish_streak + 1
                                if cand is Regime.BEARISH else 0)

        prev = self.state
        if cand == self.state:
            pass
        elif cand in RESTRICTIVE:
            self.state = cand                     # arm immediately
        elif self._streak >= need:
            self.state = cand                     # relax only on confirmation

        transitioned = self.state is not prev
        if transitioned:
            entries_off = self.state in (Regime.PANIC, Regime.DATA_UNRELIABLE,
                                         Regime.BEARISH)
            tr = Transition(ts=ts, previous=prev, new=self.state,
                            reasons=list(reasons),
                            affected_symbols=list(symbols),
                            open_positions=list(open_positions),
                            entries_disabled=entries_off,
                            risk_reduced=self.state is not Regime.BULLISH)
            self.transitions.append(tr)
            log.info("regime %s -> %s (%s)", prev.value, self.state.value,
                     "; ".join(reasons) or "n/a")

        return RegimeVerdict(
            regime=self.state, candidate=cand, confirmations=self._streak,
            reasons=reasons, transitioned=transitioned,
            detail={"breadth_20": inp.breadth_20, "breadth_50": inp.breadth_50,
                    "atr_pct": inp.atr_percentile, "spread_bps": inp.spread_bps,
                    "funding": inp.funding_rate,
                    "bearish_streak": self._bearish_streak,
                    "needed_confirmations": need})

    # -------------------------------------------------------------- gates ---
    def btc_short_confirmed(self) -> bool:
        """BTC drives the market, so shorting IT needs more than the regime.

        The extra requirement is simply MORE consecutive bearish bars than an
        alt needs -- a cheap, explainable bar rather than a new indicator."""
        return self._bearish_streak >= (
            self.cfg.minimum_regime_confirmation_candles
            + self.cfg.btc_extra_confirmation_candles)


def symbol_bearish(candles: Sequence[Candle], adx_threshold: float,
                   structure_window: int = 20,
                   strat: "StrategyConfig | None" = None
                   ) -> tuple[bool, list[str]]:
    """The per-symbol 4h bearish regime (spec 5). ALL of:
    EMA(mid)<EMA(slow), close<EMA(mid), ADX>threshold, and no higher high.

    The lengths come from the strategy config so the spec-12 sweep reaches
    them. The MARKET regime (`_trend`, computed on the benchmark) deliberately
    does NOT sweep: it is the control the other dimensions are measured
    against, and moving the definition of "bearish" underneath a sweep would
    make every cell's result a comparison to a different baseline."""
    from .config import StrategyConfig
    st = strat or StrategyConfig()
    c = [x.close for x in candles]
    h = [x.high for x in candles]
    l = [x.low for x in candles]
    need = int(st.ema_slow) + 10
    if len(c) < need:
        return False, [f"only {len(c)} closed 4h bars, need {need}"]
    i = len(c) - 1
    e50, e200 = ind.ema(c, st.ema_mid), ind.ema(c, st.ema_slow)
    a = ind.adx(h, l, c, st.adx_period)
    if None in (e50[i], e200[i], a[i]):
        return False, ["indicator warm-up incomplete"]
    fails = []
    if not e50[i] < e200[i]:
        fails.append(f"4h EMA{st.ema_mid} is not below EMA{st.ema_slow}")
    if not c[i] < e50[i]:
        fails.append(f"4h close is not below EMA{st.ema_mid}")
    if not a[i] > adx_threshold:
        fails.append(f"4h ADX {a[i]:.1f} <= {adx_threshold:.1f}")
    if ind.made_higher_high(h, i, structure_window):
        fails.append("structure made a higher high in the window")
    return (not fails), fails


def breadth(closes_by_symbol: dict[str, Sequence[float]], n: int = 20
            ) -> float | None:
    """Share of tracked assets above their own EMA(n). None when too few can
    be graded -- an unmeasurable breadth must NOT read as 0.0, which looks
    exactly like a crash."""
    up = total = 0
    for _sym, c in closes_by_symbol.items():
        if len(c) < n + 5:
            continue
        e = ind.ema(list(c), n)
        if e[-1] is None:
            continue
        total += 1
        up += 1 if c[-1] > e[-1] else 0
    if total < 2:
        return None
    return up / total


def atr_percentile_now(candles: Sequence[Candle], n: int = 14,
                       window: int = 240) -> float | None:
    if len(candles) < n + 30:
        return None
    h = [c.high for c in candles]
    l = [c.low for c in candles]
    c_ = [c.close for c in candles]
    series = ind.atr(h, l, c_, n)[-window:]
    return ind.percentile_rank(series, series[-1] if series else None)


def risk_multiplier(cfg: RegimeConfig, regime: Regime, side: str) -> float:
    """The permission table as one function. 0.0 means NO NEW ENTRY.

    Shorts are the system's primary direction, so a BEARISH regime is their
    FULL-risk state while it is a zero for trend-following longs. The mirror
    holds: a BULLISH regime zeroes new shorts."""
    if regime in (Regime.PANIC, Regime.DATA_UNRELIABLE):
        return 0.0
    if regime is Regime.HIGH_VOLATILITY:
        return cfg.high_volatility_risk_multiplier
    if side == "short":
        if regime is Regime.BEARISH:
            return cfg.bullish_risk_multiplier      # full risk, our direction
        if regime is Regime.BULLISH:
            return 0.0                              # never short a bull tape
        return cfg.neutral_risk_multiplier
    # longs
    if regime is Regime.BULLISH:
        return cfg.bullish_risk_multiplier
    if regime is Regime.BEARISH:
        return cfg.bearish_risk_multiplier          # 0.0 by config validation
    return cfg.neutral_risk_multiplier
