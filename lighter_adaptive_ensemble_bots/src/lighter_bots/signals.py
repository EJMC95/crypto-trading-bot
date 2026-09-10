"""The ensemble: independent setups, scored 0-100, long and short.

WHY AN ENSEMBLE RATHER THAN ONE CELL. With one decision per period,
`t = S_d * sqrt(T)`, so days-to-a-verdict is `(2/S_d)^2`; for independent
sleeves `S_d^2 = SUM S_i^2`. Decidability is ADDITIVE, so a single-construct
book earns a DECISION more slowly BY THE SQUARE. That is not theory here --
`STUDY_SHORT_MIRRORS_2026-09-10.md` measured two single-cell short
books on this venue's own tape and got days-to-gate of 2,092 on the better
one. The ensemble exists because the single cell was measured and refused.

WHAT THE SAME STUDY FORBIDS, and it is enforced in `momentum_component`:
**an RSI extreme is not an entry.** A pure overbought-fade cell (RSI>62,
outside a downtrend, 1h) measured -0.102%/trade at t=-2.08 across 2,744
trades, with an excess over matched-random entries of +0.037%/trade at
P=0.187 -- i.e. indistinguishable from a coin flip, and negative once the
venue's own friction is charged. So RSI here can only ever CONFIRM a setup
that already has trend and structure behind it, and it is capped at 15 of the
100 points. The spec's rule "do not enter because RSI is oversold or
overbought by itself" is therefore also this fleet's measured finding.

SCORE WEIGHTS (they sum to 100 by construction; `test_signals` pins it):
    regime 25 | trend 20 | structure 20 | momentum 15 | volume 10
    derivatives 5 | liquidity 5
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from . import indicators as ind
from .config import StrategyConfig
from .logging_setup import get
from .models import Candle, Regime, ScoreBreakdown, Signal

log = get("signals")

WEIGHTS = {"regime": 25.0, "trend": 20.0, "structure": 20.0, "momentum": 15.0,
           "volume": 10.0, "derivatives": 5.0, "liquidity": 5.0}
assert abs(sum(WEIGHTS.values()) - 100.0) < 1e-9


@dataclass
class SetupResult:
    name: str
    side: str
    valid: bool
    structure: float = 0.0            # 0..1, scaled by WEIGHTS["structure"]
    invalidation: float | None = None  # the price the idea is wrong at
    notes: list[str] = field(default_factory=list)


@dataclass
class Rejection:
    symbol: str
    side: str
    setup: str
    reason: str
    score: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ setups --
MIN_BARS = 210          # EMA200 needs >200 CLOSED bars before it means anything


class SeriesCache:
    """Indicator series computed ONCE over a tape, then indexed by bar.

    THIS IS ONLY SAFE BECAUSE CAUSALITY IS PROVEN, not assumed. Every
    indicator in `indicators.py` passes `assert_causal`: its value at index
    `i` is byte-identical whether it was computed over bars [0..i] or [0..N].
    That property is exactly what licenses precomputation, and it is the
    whole difference between an optimisation and a look-ahead bug.

    Without it the backtester is also unusable in practice -- recomputing six
    indicator families over a 3,000-bar tape for every symbol on every one of
    ~24,000 clock steps is hours of work to produce the same numbers.

    Pinned two ways in `test_backtester.py`: the precomputed series are
    compared value-by-value against incremental recomputation, and a spike
    planted in the FUTURE is required to leave the result unchanged."""

    __slots__ = ("c", "h", "l", "v", "e20", "e50", "e200", "atr", "rsi",
                 "macd_hist", "roc", "adx", "bb_lo", "bb_hi", "n")

    def __init__(self, candles: Sequence[Candle]):
        self.c = [x.close for x in candles]
        self.h = [x.high for x in candles]
        self.l = [x.low for x in candles]
        self.v = [x.volume for x in candles]
        self.n = len(self.c)
        self.e20 = ind.ema(self.c, 20)
        self.e50 = ind.ema(self.c, 50)
        self.e200 = ind.ema(self.c, 200)
        self.atr = ind.atr(self.h, self.l, self.c, 14)
        self.rsi = ind.rsi(self.c, 14)
        self.macd_hist = ind.macd(self.c)[2]
        self.roc = ind.roc(self.c, 10)
        self.adx = ind.adx(self.h, self.l, self.c, 14)
        self.bb_lo, _mid, self.bb_hi = ind.bollinger(self.c, 20, 2.0)

    def at(self, i: int) -> dict[str, Any] | None:
        """The context for bar `i`. None when the bar is inside the warm-up
        or beyond the tape -- never a zero-filled stand-in."""
        if i < MIN_BARS - 1 or i >= self.n or i < 0:
            return None
        if None in (self.e20[i], self.e50[i], self.e200[i], self.atr[i]) \
                or not self.atr[i]:
            return None
        return {"i": i, "c": self.c, "h": self.h, "l": self.l, "v": self.v,
                "e20": self.e20, "e50": self.e50, "e200": self.e200,
                "atr": self.atr[i], "rsi": self.rsi,
                "macd_hist": self.macd_hist, "roc": self.roc, "adx": self.adx,
                "bb_lo": self.bb_lo, "bb_hi": self.bb_hi}


def _ctx(candles: Sequence[Candle]) -> dict[str, Any] | None:
    """The simple path: build a cache and evaluate its LAST closed bar."""
    if len(candles) < MIN_BARS:
        return None
    return SeriesCache(candles).at(len(candles) - 1)


def _slope(series: Sequence[float | None], i: int, n: int = 5) -> float | None:
    if i - n < 0 or series[i] is None or series[i - n] is None:
        return None
    base = abs(series[i - n]) or 1e-9
    return (series[i] - series[i - n]) / base


def trend_continuation(x: dict[str, Any], side: str) -> SetupResult:
    """EMA20 vs EMA50, price on the right side of EMA20, slope agreeing."""
    i, c, e20, e50 = x["i"], x["c"], x["e20"], x["e50"]
    s = _slope(e20, i)
    if s is None:
        return SetupResult("trend_continuation", side, False,
                           notes=["EMA20 slope not computable"])
    if side == "long":
        ok = e20[i] > e50[i] and c[i] > e20[i] and s > 0
        inval = ind.last_swing(x["l"], i, "low") or (c[i] - 1.5 * x["atr"])
    else:
        ok = e20[i] < e50[i] and c[i] < e20[i] and s < 0
        inval = ind.last_swing(x["h"], i, "high") or (c[i] + 1.5 * x["atr"])
    sep = abs(e20[i] - e50[i]) / max(x["atr"], 1e-9)
    strength = max(0.0, min(1.0, sep / 1.5))
    return SetupResult("trend_continuation", side, ok, strength, inval,
                       [f"EMA20/50 separation {sep:.2f} ATR",
                        f"EMA20 slope {s:+.4f}"])


def pullback_continuation(x: dict[str, Any], side: str) -> SetupResult:
    """Higher-timeframe structure intact, price REJECTING a retest of EMA20/50
    -- the entry is the rejection bar, not the touch."""
    i, c, h, l = x["i"], x["c"], x["h"], x["l"]
    e20, e50, e200 = x["e20"], x["e50"], x["e200"]
    band_lo, band_hi = min(e20[i], e50[i]), max(e20[i], e50[i])
    tol = 0.35 * x["atr"]
    if side == "long":
        structure_ok = e50[i] > e200[i]
        touched = l[i] <= band_hi + tol
        rejected = c[i] > band_lo and c[i] > (l[i] + 0.5 * (h[i] - l[i]))
        inval = min(l[i], l[i - 1]) - 0.1 * x["atr"]
    else:
        structure_ok = e50[i] < e200[i]
        touched = h[i] >= band_lo - tol
        rejected = c[i] < band_hi and c[i] < (l[i] + 0.5 * (h[i] - l[i]))
        inval = max(h[i], h[i - 1]) + 0.1 * x["atr"]
    ok = bool(structure_ok and touched and rejected)
    rng = max(h[i] - l[i], 1e-9)
    wick = ((h[i] - c[i]) if side == "short" else (c[i] - l[i])) / rng
    return SetupResult("pullback_continuation", side, ok,
                       max(0.0, min(1.0, wick)), inval,
                       [f"HTF structure {'ok' if structure_ok else 'against'}",
                        f"rejection body {wick:.2f} of range"])


def breakout_retest(x: dict[str, Any], side: str) -> SetupResult:
    """A CLOSED break of the 20-bar range, then a retest that holds. The range
    is taken with `end=i-1` so the current bar never defines its own level."""
    i, c, h, l = x["i"], x["c"], x["h"], x["l"]
    hi = ind.rolling_max(h, 20, i - 1)
    lo = ind.rolling_min(l, 20, i - 1)
    if hi is None or lo is None:
        return SetupResult("breakout_retest", side, False,
                           notes=["range not computable"])
    band = max(hi - lo, 1e-9)
    broke_at = None
    for j in range(max(0, i - 8), i):
        if side == "long" and c[j] > hi:
            broke_at = j
        if side == "short" and c[j] < lo:
            broke_at = j
    if broke_at is None:
        return SetupResult("breakout_retest", side, False,
                           notes=["no closed break in the last 8 bars"])
    if side == "long":
        retested = l[i] <= hi + 0.25 * x["atr"]
        held = c[i] > hi
        inval = hi - 0.5 * x["atr"]
    else:
        retested = h[i] >= lo - 0.25 * x["atr"]
        held = c[i] < lo
        inval = lo + 0.5 * x["atr"]
    ok = bool(retested and held)
    depth = abs(c[i] - (hi if side == "long" else lo)) / max(x["atr"], 1e-9)
    return SetupResult("breakout_retest", side, ok,
                       max(0.0, min(1.0, 1.0 - depth / 2.0)), inval,
                       [f"break at bar -{i - broke_at}",
                        f"range {band:.6g}", f"retest depth {depth:.2f} ATR"])


LONG_SETUPS = (trend_continuation, pullback_continuation, breakout_retest)
SHORT_SETUPS = (trend_continuation, pullback_continuation, breakout_retest)


# -------------------------------------------------------------- components --
def regime_component(regime: Regime, side: str) -> tuple[float, str]:
    """25 points. Full marks only when the regime AGREES with the direction;
    a tactical counter-trend entry starts a long way behind and must make it
    up on structure, which is what the higher score bar for it enforces."""
    w = WEIGHTS["regime"]
    if regime is Regime.PANIC or regime is Regime.DATA_UNRELIABLE:
        return 0.0, f"{regime.value}: no entries"
    if regime is Regime.BULLISH:
        return (w, "bullish/long") if side == "long" else (w * 0.30, "bullish/short")
    if regime is Regime.BEARISH:
        return (w, "bearish/short") if side == "short" else (w * 0.25, "bearish/long tactical")
    if regime is Regime.HIGH_VOLATILITY:
        return w * 0.55, "high volatility"
    return w * 0.70, "neutral"


def trend_component(x: dict[str, Any], side: str, adx_threshold: float
                    ) -> tuple[float, str]:
    """20 points: alignment (12) + measured trend STRENGTH via ADX (8)."""
    i, c, w = x["i"], x["c"], WEIGHTS["trend"]
    e20, e50, e200 = x["e20"], x["e50"], x["e200"]
    up = side == "long"
    align = 0.0
    for cond in ((e20[i] > e50[i]) if up else (e20[i] < e50[i]),
                 (e50[i] > e200[i]) if up else (e50[i] < e200[i]),
                 (c[i] > e20[i]) if up else (c[i] < e20[i])):
        align += 1.0 if cond else 0.0
    a = x["adx"][i]
    strength = 0.0 if a is None else max(0.0, min(1.0, (a - adx_threshold) / 20.0))
    pts = w * 0.60 * (align / 3.0) + w * 0.40 * strength
    return pts, f"align {align:.0f}/3, ADX {('n/a' if a is None else f'{a:.1f}')}"


def momentum_component(x: dict[str, Any], side: str) -> tuple[float, str]:
    """15 points, and CAPPED there on purpose.

    RSI enters only as a REGIME-OF-MOMENTUM band, never as an extreme: a long
    wants 40-68 (healthy, not blown off) and a short wants 35-60. An RSI of 85
    scores ZERO on this component for a short -- the measured refutation of
    the naive overbought fade is encoded here rather than written in a
    comment somewhere."""
    i, w = x["i"], WEIGHTS["momentum"]
    r, mh, ro = x["rsi"][i], x["macd_hist"][i], x["roc"][i]
    if r is None:
        return 0.0, "RSI not computable"
    lo, hi = (40.0, 68.0) if side == "long" else (35.0, 60.0)
    in_band = lo <= r <= hi
    band_pts = w * 0.50 if in_band else 0.0
    macd_ok = (mh is not None) and ((mh > 0) if side == "long" else (mh < 0))
    roc_ok = (ro is not None) and ((ro > 0) if side == "long" else (ro < 0))
    pts = band_pts + (w * 0.30 if macd_ok else 0.0) + (w * 0.20 if roc_ok else 0.0)
    return pts, (f"RSI {r:.1f} {'in' if in_band else 'OUTSIDE'} [{lo:.0f},"
                 f"{hi:.0f}], MACD {'ok' if macd_ok else 'no'}, "
                 f"ROC {'ok' if roc_ok else 'no'}")


def volume_component(x: dict[str, Any]) -> tuple[float, str]:
    """10 points. Participation confirming the move, not volume for its own
    sake: the score saturates at 2x the 20-bar mean."""
    i, v, w = x["i"], x["v"], WEIGHTS["volume"]
    if i < 21:
        return 0.0, "insufficient volume history"
    mean = sum(v[i - 20:i]) / 20.0
    if mean <= 0:
        return 0.0, "no measurable volume"
    ratio = v[i] / mean
    return w * max(0.0, min(1.0, (ratio - 0.7) / 1.3)), f"volume {ratio:.2f}x 20-bar"


def derivatives_component(funding: float | None, oi_change: float | None,
                          side: str) -> tuple[float, str]:
    """5 points. Funding that PAYS our side and open interest confirming.
    Unknown scores the NEUTRAL half, never full marks -- absence of data is
    not confirmation."""
    w = WEIGHTS["derivatives"]
    if funding is None and oi_change is None:
        return w * 0.5, "derivatives unavailable (neutral credit)"
    pts = 0.0
    notes = []
    if funding is not None:
        # A short RECEIVES positive funding; a long receives negative funding.
        pays_us = (funding < 0) if side == "long" else (funding > 0)
        pts += w * 0.6 if pays_us else 0.0
        notes.append(f"funding {funding:+.6f} {'pays us' if pays_us else 'costs us'}")
    else:
        pts += w * 0.3
    if oi_change is not None:
        confirms = oi_change > 0
        pts += w * 0.4 if confirms else 0.0
        notes.append(f"OI {oi_change:+.3f}")
    else:
        pts += w * 0.2
    return min(pts, w), ", ".join(notes)


def liquidity_component(spread_bps: float | None, atr_pct: float | None,
                        max_spread_bps: float) -> tuple[float, str]:
    """5 points for a market we can actually get in and out of. An unknown
    spread scores ZERO: this is the one component where missing data is a
    genuine reason to size down."""
    w = WEIGHTS["liquidity"]
    if spread_bps is None:
        return 0.0, "spread unknown"
    if spread_bps > max_spread_bps:
        return 0.0, f"spread {spread_bps:.1f}bps over the {max_spread_bps:.0f} limit"
    tight = 1.0 - (spread_bps / max(max_spread_bps, 1e-9))
    vol_pen = 0.0 if atr_pct is None else max(0.0, (atr_pct - 90.0) / 10.0)
    return w * max(0.0, min(1.0, tight - vol_pen)), \
        f"spread {spread_bps:.1f}bps, ATR pct {('n/a' if atr_pct is None else f'{atr_pct:.0f}')}"


# ------------------------------------------------------------- the builder --
def build_stop(x: dict[str, Any], side: str, setup: SetupResult,
               cfg: StrategyConfig) -> float:
    """Beyond the invalidation, plus an ATR buffer, capped in ATR terms.
    The cap matters: an invalidation 9 ATR away is a real level and a useless
    stop, and sizing off it produces a position too small to matter or a
    risk budget spent on one idea."""
    i, c, atr_ = x["i"], x["c"], x["atr"]
    px = c[i]
    inval = setup.invalidation
    if inval is None:
        inval = px - 1.5 * atr_ if side == "long" else px + 1.5 * atr_
    buf = cfg.atr_stop_buffer * atr_
    stop = (inval - buf) if side == "long" else (inval + buf)
    max_dist = cfg.max_stop_distance_atr * atr_
    if side == "long":
        return max(stop, px - max_dist)
    return min(stop, px + max_dist)


def evaluate(symbol: str, candles: Sequence[Candle], side: str,
             regime: Regime, cfg: StrategyConfig, *,
             cache: "SeriesCache | None" = None, bar: int | None = None,
             timeframe: str = "1h", funding: float | None = None,
             oi_change: float | None = None, spread_bps: float | None = None,
             atr_percentile: float | None = None,
             max_spread_bps: float = 10.0,
             ) -> tuple[Signal | None, list[Rejection]]:
    """Score every setup for one (symbol, side). Returns the BEST admissible
    signal and the reasons the others were refused."""
    rejects: list[Rejection] = []
    if cache is not None:
        idx = (cache.n - 1) if bar is None else bar
        x = cache.at(idx)
    else:
        x = _ctx(candles)
    if x is None:
        return None, [Rejection(symbol, side, "-", "insufficient history "
                                f"(need {MIN_BARS} closed bars)")]
    i = x["i"]
    reg_pts, reg_note = regime_component(regime, side)
    if reg_pts <= 0.0:
        return None, [Rejection(symbol, side, "-", f"regime blocks: {reg_note}")]
    tr_pts, tr_note = trend_component(x, side, cfg.adx_threshold)
    mo_pts, mo_note = momentum_component(x, side)
    vo_pts, vo_note = volume_component(x)
    de_pts, de_note = derivatives_component(funding, oi_change, side)
    li_pts, li_note = liquidity_component(spread_bps, atr_percentile,
                                          max_spread_bps)

    best: Signal | None = None
    for fn in (LONG_SETUPS if side == "long" else SHORT_SETUPS):
        s = fn(x, side)
        if not s.valid:
            rejects.append(Rejection(symbol, side, s.name,
                                     "; ".join(s.notes) or "setup not present"))
            continue
        breakdown = ScoreBreakdown(
            regime=round(reg_pts, 3), trend=round(tr_pts, 3),
            structure=round(WEIGHTS["structure"] * s.structure, 3),
            momentum=round(mo_pts, 3), volume=round(vo_pts, 3),
            derivatives=round(de_pts, 3), liquidity=round(li_pts, 3))
        entry = x["c"][i]
        stop = build_stop(x, side, s, cfg)
        risk = abs(entry - stop)
        if risk <= 0:
            rejects.append(Rejection(symbol, side, s.name,
                                     "degenerate stop distance"))
            continue
        if risk > cfg.max_stop_distance_atr * x["atr"] * 1.0001:
            rejects.append(Rejection(symbol, side, s.name,
                                     f"stop {risk / x['atr']:.2f} ATR exceeds "
                                     f"the {cfg.max_stop_distance_atr} cap"))
            continue
        sgn = 1.0 if side == "long" else -1.0
        targets = [entry + sgn * cfg.tp1_r * risk, entry + sgn * cfg.tp2_r * risk]
        # Reward/risk is measured to TP2, the last DEFINED target; the runner
        # is trailed and its reward is unknown at decision time, so counting
        # it would be crediting ourselves with a number we do not have.
        rr = abs(targets[-1] - entry) / risk
        sig = Signal(symbol=symbol, side=side, strategy=f"ensemble.{s.name}",
                     timeframe=timeframe,
                     candle_ts=(candles[i].ts if i < len(candles)
                                else int(x["c"][i])),
                     setup=s.name, score=breakdown, entry=entry, stop=stop,
                     targets=targets, atr=x["atr"], reward_risk=rr,
                     regime=regime,
                     meta={"notes": {"regime": reg_note, "trend": tr_note,
                                     "momentum": mo_note, "volume": vo_note,
                                     "derivatives": de_note,
                                     "liquidity": li_note,
                                     "setup": "; ".join(s.notes)},
                           "stop_atr": risk / x["atr"]})
        if best is None or sig.score.total > best.score.total:
            best = sig
    return best, rejects


def minimum_score(cfg: StrategyConfig, regime: Regime, side: str) -> float:
    if regime is Regime.NEUTRAL:
        return cfg.neutral_minimum_score
    if regime is Regime.BEARISH and side == "long":
        return cfg.bearish_tactical_long_minimum_score
    if regime is Regime.BULLISH and side == "short":
        # A counter-regime short in a bull tape is the mirror of the tactical
        # long and is held to the same higher bar.
        return cfg.bearish_tactical_long_minimum_score
    return cfg.long_minimum_score if side == "long" else cfg.short_minimum_score


def minimum_rr(cfg: StrategyConfig, regime: Regime) -> float:
    return (cfg.neutral_minimum_reward_risk if regime is Regime.NEUTRAL
            else cfg.minimum_reward_risk)


def admissible(sig: Signal, cfg: StrategyConfig, regime: Regime,
               score_bump: float = 0.0, rr_bump: float = 0.0
               ) -> tuple[bool, str]:
    need_score = minimum_score(cfg, regime, sig.side) + score_bump
    need_rr = minimum_rr(cfg, regime) + rr_bump
    if sig.score.total < need_score:
        return False, (f"score {sig.score.total:.1f} < {need_score:.1f} "
                       f"({regime.value}/{sig.side})")
    if sig.reward_risk < need_rr:
        return False, f"reward/risk {sig.reward_risk:.2f} < {need_rr:.2f}"
    return True, "admissible"
