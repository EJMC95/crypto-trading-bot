"""The short ensemble (and its long mirror): independent setups, scored 0-100.

WHY AN ENSEMBLE. No single indicator gets to open a trade. Seven components
vote, they are weighted by how much each one has to say about whether a
downtrend CONTINUES, and the total must clear 70 of 100.

    regime 25 | trend 20 | breakdown/retest 20 | momentum 15
    volume 10 | derivatives 5 | quality 5                      = 100

THREE RULES THAT ARE ENCODED, NOT COMMENTED:

1. **An RSI extreme is not an entry.** A continuation short wants RSI in
   [35, 60]; at 15 it scores ZERO. Shorting something already deeply oversold
   is selling the bottom, and momentum is capped at 15 of 100 precisely so it
   can never carry a trade on its own.
2. **Derivatives are a SECONDARY filter and are capped at 5.** Funding that is
   already extremely negative means the short is crowded and the easy money is
   gone -- it SUBTRACTS unless trend and breakdown are both near-perfect.
   Falling open interest with falling price is liquidation exhaustion, not
   continuation, and it reduces confidence.
3. **Unknown never scores well.** A missing spread scores zero on quality; a
   missing funding print scores the neutral half of derivatives, never full
   marks. Absence of evidence is not confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from . import indicators as ind
from .config import StrategyConfig
from .logging_setup import get
from .models import Candle, Regime, ScoreCard, Signal

log = get("signals")

WEIGHTS = {"regime": 25.0, "trend": 20.0, "breakdown": 20.0, "momentum": 15.0,
           "volume": 10.0, "derivatives": 5.0, "quality": 5.0}
assert abs(sum(WEIGHTS.values()) - 100.0) < 1e-9

#: Warm-up floor for the DEFAULT ema_slow=200. `min_bars_for` derives the real
#: floor from whatever length the config carries, so a sweep that shortens the
#: slow EMA also shortens the history it demands -- otherwise every short-EMA
#: cell would be graded on a tape it was never allowed to trade.
MIN_BARS = 210


def min_bars_for(strat: StrategyConfig | None) -> int:
    st = strat or StrategyConfig()
    # The slow EMA dominates, but the breakdown range needs
    # structure_window + BREAK_LOOKBACK bars behind the current one too, and a
    # floor that ignored it would let `at()` hand out a context on which the
    # 20-point component can never score.
    return max(int(st.ema_slow) + 10,
               int(st.structure_window) + BREAK_LOOKBACK + 2)


@dataclass
class Rejection:
    symbol: str
    side: str
    setup: str
    reason: str
    score: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class SeriesCache:
    """Indicator series computed ONCE over a tape, then indexed by bar.

    Safe only because causality is PROVEN: every indicator passes
    `assert_causal`, so the value at bar i is identical whether computed over
    [0..i] or [0..N]. That property is what separates an optimisation from a
    look-ahead bug, and `test_backtester` pins both the equivalence and the
    consequence (a spike planted in the future changes nothing)."""

    __slots__ = ("c", "h", "l", "v", "e20", "e50", "e200", "atr", "rsi",
                 "macd_hist", "roc", "adx", "n", "min_bars", "strat")

    def __init__(self, candles: Sequence[Candle],
                 strat: StrategyConfig | None = None):
        st = strat or StrategyConfig()
        self.strat = st
        self.min_bars = min_bars_for(st)
        self.c = [x.close for x in candles]
        self.h = [x.high for x in candles]
        self.l = [x.low for x in candles]
        self.v = [x.volume for x in candles]
        self.n = len(self.c)
        # The names are the ROLES (fast/mid/slow), not the lengths -- a sweep
        # moves the lengths and every consumer keeps reading the same role.
        self.e20 = ind.ema(self.c, st.ema_fast)
        self.e50 = ind.ema(self.c, st.ema_mid)
        self.e200 = ind.ema(self.c, st.ema_slow)
        self.atr = ind.atr(self.h, self.l, self.c, st.atr_period)
        self.rsi = ind.rsi(self.c, st.rsi_period)
        self.macd_hist = ind.macd(self.c)[2]
        self.roc = ind.roc(self.c, 10)
        self.adx = ind.adx(self.h, self.l, self.c, st.adx_period)

    def at(self, i: int) -> dict[str, Any] | None:
        if i < self.min_bars - 1 or i >= self.n or i < 0:
            return None
        if None in (self.e20[i], self.e50[i], self.e200[i], self.atr[i]) \
                or not self.atr[i]:
            return None
        return {"i": i, "c": self.c, "h": self.h, "l": self.l, "v": self.v,
                "e20": self.e20, "e50": self.e50, "e200": self.e200,
                "atr": self.atr[i], "rsi": self.rsi,
                "macd_hist": self.macd_hist, "roc": self.roc, "adx": self.adx}


def context(candles: Sequence[Candle],
            strat: StrategyConfig | None = None) -> dict[str, Any] | None:
    if len(candles) < min_bars_for(strat):
        return None
    return SeriesCache(candles, strat).at(len(candles) - 1)


# ------------------------------------------------------------- components ---
def regime_component(regime: Regime, side: str,
                     symbol_bearish_ok: bool) -> tuple[float, str]:
    """25 points. The single largest weight, because direction against the
    market is the most expensive mistake this system can make."""
    w = WEIGHTS["regime"]
    if regime in (Regime.PANIC, Regime.DATA_UNRELIABLE):
        return 0.0, f"{regime.value}: no entries"
    if side == "short":
        if regime is Regime.BULLISH:
            return 0.0, "bullish market: no new shorts"
        if not symbol_bearish_ok:
            return 0.0, "symbol 4h regime is not bearish"
        if regime is Regime.BEARISH:
            return w, "bearish market + bearish symbol"
        if regime is Regime.HIGH_VOLATILITY:
            return w * 0.55, "high volatility"
        return w * 0.70, "neutral market, bearish symbol"
    # longs
    if regime is Regime.BEARISH:
        return 0.0, "bearish market: new trend-following longs disabled"
    if regime is Regime.BULLISH:
        return w, "bullish market"
    if regime is Regime.HIGH_VOLATILITY:
        return w * 0.55, "high volatility"
    return w * 0.70, "neutral market"


def trend_component(x: dict[str, Any], side: str, adx_threshold: float
                    ) -> tuple[float, str]:
    """20 points: alignment (12) + measured ADX strength (8). Spec 6A."""
    i, c, w = x["i"], x["c"], WEIGHTS["trend"]
    e20, e50 = x["e20"], x["e50"]
    s = ind.slope(e20, i)
    down = side == "short"
    align = 0.0
    for cond in ((e20[i] < e50[i]) if down else (e20[i] > e50[i]),
                 (c[i] < e20[i]) if down else (c[i] > e20[i]),
                 (s is not None and (s < 0 if down else s > 0))):
        align += 1.0 if cond else 0.0
    a = x["adx"][i]
    strength = 0.0 if a is None else max(0.0, min(1.0,
                                                  (a - adx_threshold) / 20.0))
    pts = w * 0.60 * (align / 3.0) + w * 0.40 * strength
    return pts, (f"align {align:.0f}/3, ADX "
                 f"{'n/a' if a is None else f'{a:.1f}'}, "
                 f"EMA20 slope {'n/a' if s is None else f'{s:+.4f}'}")


#: How far back a closed break may have happened and still count. The range
#: that defines the level is formed on the bars BEFORE this window -- see the
#: derivation in `breakdown_component`.
BREAK_LOOKBACK = 8


def breakdown_component(x: dict[str, Any], side: str, cfg: StrategyConfig
                        ) -> tuple[float, str, float | None]:
    """20 points, and it returns the TRIGGER LEVEL the entry is measured
    against (spec 7.9). Spec 6B: a closed break of support, then a RETEST that
    REJECTS -- never chasing an already-extended candle.

    THE WINDOWS MUST NOT OVERLAP, AND THE FIRST VERSION OF THIS FUNCTION HAD
    THEM OVERLAPPING, WHICH MADE THE WHOLE COMPONENT UNREACHABLE. It took the
    support level as `rolling_min(lows, 20, end=i-1)` and then asked whether
    any close in `[i-8, i)` was BELOW it -- but those eight bars are inside the
    twenty the minimum was taken over, and `close[j] >= low[j] >= min(lows)`
    for any window containing j. So the test could never pass: not rarely,
    NEVER. Measured on 400,000 random bar-sets obeying only `close >= low`:
    **0 hits**. The component is worth 20 of 100 points, the second-largest
    weight, and on a first synthetic run it scored 0.00 on every one of 332
    signals while the score bar was never reached.

    The fix is to form the range on the bars BEFORE the break window
    (`end = i - BREAK_LOOKBACK - 1`), so a close inside the window can sit
    below a level established earlier. Same bars, corrected windowing: 7.4%.

    THE GENERAL SHAPE, worth more than the instance: a scoring component that
    returns 0.0 is byte-identical between "the market did not do this" and
    "this can never fire". The census that separates them is the only reason
    this was found, and `test_signals` now pins the base rate rather than the
    code."""
    i, c, h, l, w = x["i"], x["c"], x["h"], x["l"], WEIGHTS["breakdown"]
    n = cfg.structure_window
    end = i - BREAK_LOOKBACK - 1
    lo = ind.rolling_min(l, n, end)
    hi = ind.rolling_max(h, n, end)
    if lo is None or hi is None:
        return 0.0, "range not computable", None
    level = lo if side == "short" else hi
    broke_at = None
    for j in range(max(0, i - BREAK_LOOKBACK), i):
        if side == "short" and c[j] < lo:
            broke_at = j
        if side == "long" and c[j] > hi:
            broke_at = j
    if broke_at is None:
        return 0.0, (f"no closed break of {level:.6g} in the last "
                     f"{BREAK_LOOKBACK} bars"), level

    if side == "short":
        retested = h[i] >= level - 0.25 * x["atr"]
        rejected = c[i] < level and c[i] < (l[i] + 0.5 * (h[i] - l[i]))
        extension = (level - c[i]) / max(x["atr"], 1e-9)
    else:
        retested = l[i] <= level + 0.25 * x["atr"]
        rejected = c[i] > level and c[i] > (l[i] + 0.5 * (h[i] - l[i]))
        extension = (c[i] - level) / max(x["atr"], 1e-9)

    if not retested:
        return 0.0, f"break at bar -{i - broke_at} but no retest yet", level
    if not rejected:
        return 0.0, "retest has not rejected", level
    # Do not chase: score decays with how far price already ran from the level.
    closeness = max(0.0, 1.0 - extension / max(cfg.max_entry_distance_atr, 1e-9))
    return (w * closeness,
            f"break at bar -{i - broke_at}, retest rejected, "
            f"{extension:.2f} ATR from the level", level)


def momentum_component(x: dict[str, Any], side: str, cfg: StrategyConfig
                       ) -> tuple[float, str]:
    """15 points, CAPPED there on purpose (spec 6C).

    RSI enters as a BAND, never as an extreme. A short wants [35, 60]; an RSI
    of 15 is a market that has already fallen hard and scores ZERO here. That
    is the 'do not enter merely because RSI is oversold' rule, encoded rather
    than written in a comment."""
    i, w = x["i"], WEIGHTS["momentum"]
    r, mh, ro = x["rsi"][i], x["macd_hist"][i], x["roc"][i]
    if r is None:
        return 0.0, "RSI not computable"
    lo, hi = ((cfg.rsi_short_lo, cfg.rsi_short_hi) if side == "short"
              else (cfg.rsi_long_lo, cfg.rsi_long_hi))
    in_band = lo <= r <= hi
    band_pts = w * 0.50 if in_band else 0.0
    macd_ok = (mh is not None) and ((mh < 0) if side == "short" else (mh > 0))
    roc_ok = (ro is not None) and ((ro < 0) if side == "short" else (ro > 0))
    pts = band_pts + (w * 0.30 if macd_ok else 0.0) \
        + (w * 0.20 if roc_ok else 0.0)
    tag = "in" if in_band else ("OVERSOLD" if r < lo else "OVERBOUGHT")
    return pts, (f"RSI {r:.1f} {tag} [{lo:.0f},{hi:.0f}], "
                 f"MACD {'ok' if macd_ok else 'no'}, "
                 f"ROC {'ok' if roc_ok else 'no'}")


def volume_component(x: dict[str, Any], cfg: StrategyConfig
                     ) -> tuple[float, str]:
    """10 points. Spec 6D: breakdown volume above its rolling average, and a
    signal on materially BELOW-average volume is rejected outright (zero)."""
    i, v, w = x["i"], x["v"], WEIGHTS["volume"]
    if i < 21:
        return 0.0, "insufficient volume history"
    mean = sum(v[i - 20:i]) / 20.0
    if mean <= 0:
        return 0.0, "no measurable volume"
    ratio = v[i] / mean
    if ratio < cfg.volume_ratio_floor * 0.6:
        return 0.0, f"volume {ratio:.2f}x is materially below average"
    return (w * max(0.0, min(1.0, (ratio - 0.7) / 1.3)),
            f"volume {ratio:.2f}x its 20-bar average")


def derivatives_component(funding: float | None, oi_change: float | None,
                          side: str, price_falling: bool,
                          trend_pts: float, breakdown_pts: float
                          ) -> tuple[float, str]:
    """5 points, SECONDARY by weight and by construction (spec 6E).

    Three encoded judgements:
      * funding already extremely negative means a crowded short -- it scores
        NOTHING unless trend and breakdown are both near-maximal, which is the
        'exceptionally strong trend signal' escape the spec allows;
      * rising OI with falling price is fresh positioning -> continuation;
      * FALLING OI with falling price is liquidation exhaustion -> confidence
        is REDUCED, not raised.
    """
    w = WEIGHTS["derivatives"]
    if funding is None and oi_change is None:
        return w * 0.5, "derivatives unavailable (neutral credit, not full)"
    notes, pts = [], 0.0
    exceptional = (trend_pts >= WEIGHTS["trend"] * 0.9
                   and breakdown_pts >= WEIGHTS["breakdown"] * 0.9)

    if funding is None:
        pts += w * 0.3
        notes.append("funding unknown")
    else:
        crowded = (funding < -0.0005) if side == "short" else (funding > 0.0005)
        if crowded and not exceptional:
            notes.append(f"funding {funding:+.5f} already extreme: crowded "
                         "side, no credit")
        elif crowded and exceptional:
            pts += w * 0.3
            notes.append(f"funding {funding:+.5f} extreme but trend/breakdown "
                         "are near-maximal")
        else:
            pays_us = (funding > 0) if side == "short" else (funding < 0)
            pts += w * 0.6 if pays_us else w * 0.2
            notes.append(f"funding {funding:+.5f} "
                         f"{'pays us' if pays_us else 'costs us'}")

    if oi_change is None:
        pts += w * 0.2
        notes.append("OI unknown")
    elif side == "short" and price_falling:
        if oi_change > 0:
            pts += w * 0.4
            notes.append(f"OI {oi_change:+.3f} rising with falling price: "
                         "continuation")
        else:
            notes.append(f"OI {oi_change:+.3f} FALLING with falling price: "
                         "liquidation exhaustion, confidence reduced")
    else:
        pts += w * 0.2
        notes.append(f"OI {oi_change:+.3f}")
    return min(pts, w), "; ".join(notes)


def quality_component(spread_bps: float | None, atr_pct: float | None,
                      stop_atr: float | None, cfg: StrategyConfig,
                      max_spread_bps: float) -> tuple[float, str]:
    """5 points for a market we can actually get in and out of (spec 6F).
    An unknown spread scores ZERO -- this is the one component where missing
    data is a genuine reason to refuse."""
    w = WEIGHTS["quality"]
    if spread_bps is None:
        return 0.0, "spread unknown"
    if spread_bps > max_spread_bps:
        return 0.0, (f"spread {spread_bps:.1f}bps over the "
                     f"{max_spread_bps:.0f}bps limit")
    tight = 1.0 - spread_bps / max(max_spread_bps, 1e-9)
    vol_pen = 0.0 if atr_pct is None else max(0.0, (atr_pct - 85.0) / 15.0)
    wide_pen = 0.0
    if stop_atr is not None and cfg.max_stop_distance_atr > 0:
        wide_pen = max(0.0, (stop_atr / cfg.max_stop_distance_atr) - 0.6)
    return (w * max(0.0, min(1.0, tight - vol_pen - wide_pen)),
            f"spread {spread_bps:.1f}bps, ATR pct "
            f"{'n/a' if atr_pct is None else f'{atr_pct:.0f}'}, "
            f"stop {'n/a' if stop_atr is None else f'{stop_atr:.2f}'} ATR")


# ---------------------------------------------------------------- builder ---
def build_stop(x: dict[str, Any], side: str, cfg: StrategyConfig) -> float:
    """Beyond the invalidation swing, plus an ATR buffer, capped in ATR terms.

    The cap matters: an invalidation 9 ATR away is a real level and a useless
    stop, and sizing off it spends the whole risk budget on one idea.

    AND THE SWING MUST BE ON THE RIGHT SIDE OF PRICE. `last_swing` returns the
    most recent CONFIRMED pivot, which price may already have run through -- on
    a falling tape the last confirmed swing LOW routinely sits ABOVE the
    current close. Taking it verbatim put a long's stop above its own entry: a
    trade that is stopped the instant it fills, sized off a positive `risk`
    that made the arithmetic look fine. Caught by `test_signals`, which asserts
    the side rather than the distance. An overrun pivot is not an invalidation
    level any more, so it degrades to the ATR stop."""
    i, c, a = x["i"], x["c"], x["atr"]
    px = c[i]
    if side == "short":
        swing = ind.last_swing(x["h"], i, "high")
        inval = swing if (swing is not None and swing > px) else px + 1.5 * a
        stop = inval + cfg.atr_stop_buffer * a
        stop = min(stop, px + cfg.max_stop_distance_atr * a)
        # Belt: even the CAP must not land at or below the entry.
        return max(stop, px + max(cfg.atr_stop_buffer, 0.1) * a)
    swing = ind.last_swing(x["l"], i, "low")
    inval = swing if (swing is not None and swing < px) else px - 1.5 * a
    stop = inval - cfg.atr_stop_buffer * a
    stop = max(stop, px - cfg.max_stop_distance_atr * a)
    return min(stop, px - max(cfg.atr_stop_buffer, 0.1) * a)


def evaluate(symbol: str, candles: Sequence[Candle], side: str, *,
             regime: Regime, cfg: StrategyConfig, symbol_bearish_ok: bool,
             cache: SeriesCache | None = None, bar: int | None = None,
             timeframe: str = "1h", funding: float | None = None,
             oi_change: float | None = None, spread_bps: float | None = None,
             atr_percentile: float | None = None,
             max_spread_bps: float = 8.0, strategy: str = "downtrend.ensemble",
             ) -> tuple[Signal | None, list[Rejection]]:
    """Score one (symbol, side). Returns the signal and every rejection
    reason, so a quiet book is always explainable."""
    rejects: list[Rejection] = []
    if cache is not None:
        x = cache.at((cache.n - 1) if bar is None else bar)
    else:
        x = context(candles, cfg)
    if x is None:
        return None, [Rejection(symbol, side, "-",
                                f"insufficient history (need "
                                f"{min_bars_for(cfg)} closed bars)")]
    i = x["i"]

    reg_pts, reg_note = regime_component(regime, side, symbol_bearish_ok)
    if reg_pts <= 0.0:
        return None, [Rejection(symbol, side, "-", f"regime blocks: {reg_note}")]

    tr_pts, tr_note = trend_component(x, side, cfg.adx_threshold)
    bd_pts, bd_note, level = breakdown_component(x, side, cfg)
    mo_pts, mo_note = momentum_component(x, side, cfg)
    vo_pts, vo_note = volume_component(x, cfg)
    falling = x["c"][i] < x["c"][i - 1] if i >= 1 else False
    de_pts, de_note = derivatives_component(funding, oi_change, side, falling,
                                            tr_pts, bd_pts)

    entry = x["c"][i]
    stop = build_stop(x, side, cfg)
    risk = abs(entry - stop)
    if risk <= 0:
        return None, [Rejection(symbol, side, "-", "degenerate stop distance")]
    stop_atr = risk / x["atr"]
    if stop_atr > cfg.max_stop_distance_atr * 1.0001:
        return None, [Rejection(symbol, side, "-",
                                f"stop {stop_atr:.2f} ATR exceeds the "
                                f"{cfg.max_stop_distance_atr} cap")]

    ql_pts, ql_note = quality_component(spread_bps, atr_percentile, stop_atr,
                                        cfg, max_spread_bps)

    card = ScoreCard(
        regime=round(reg_pts, 3), trend=round(tr_pts, 3),
        breakdown=round(bd_pts, 3), momentum=round(mo_pts, 3),
        volume=round(vo_pts, 3), derivatives=round(de_pts, 3),
        quality=round(ql_pts, 3),
        notes={"regime": reg_note, "trend": tr_note, "breakdown": bd_note,
               "momentum": mo_note, "volume": vo_note, "derivatives": de_note,
               "quality": ql_note})

    sgn = -1.0 if side == "short" else 1.0
    targets = [entry + sgn * cfg.tp1_r * risk, entry + sgn * cfg.tp2_r * risk]
    # Reward/risk is measured to TP2, the last DEFINED target. The runner is
    # trailed, so its reward is unknown at decision time and counting it would
    # be crediting ourselves with a number we do not have.
    rr = abs(targets[-1] - entry) / risk

    setup = "breakdown_retest" if bd_pts > 0 else "trend_continuation"
    sig = Signal(symbol=symbol, side=side, strategy=strategy, setup=setup,
                 timeframe=timeframe, candle_ts=candles[i].ts if i < len(candles)
                 else int(x["c"][i]), score=card, entry=entry, stop=stop,
                 targets=targets, atr=x["atr"], reward_risk=rr, regime=regime,
                 trigger_level=level,
                 meta={"stop_atr": stop_atr, "falling": falling})
    return sig, rejects


def admissible(sig: Signal, cfg: StrategyConfig, regime: Regime, *,
               score_bump: float = 0.0, rr_bump: float = 0.0
               ) -> tuple[bool, str]:
    """The final bars: score, reward/risk, and distance from the trigger."""
    need_score = cfg.minimum_score + score_bump
    need_rr = cfg.minimum_reward_risk + rr_bump
    if sig.score.total < need_score:
        return False, (f"score {sig.score.total:.1f} < {need_score:.1f} "
                       f"({regime.value}/{sig.side})")
    if sig.reward_risk < need_rr:
        return False, f"reward/risk {sig.reward_risk:.2f} < {need_rr:.2f}"
    if sig.trigger_level is not None and sig.atr > 0:
        dist = abs(sig.entry - sig.trigger_level) / sig.atr
        if dist > cfg.max_entry_distance_atr:
            return False, (f"entry {dist:.2f} ATR from the trigger level "
                           f"exceeds {cfg.max_entry_distance_atr}")
    return True, "admissible"
