"""Causal indicators. Every function reads bars [0..i] and NEVER i+1.

`assert_causal` is the executable form of that claim: it recomputes a series on
a tape truncated by `cut` bars and requires every overlapping value to be
identical. An indicator that peeks CHANGES when you hide the future, so this is
a real test rather than a restatement of intent -- and it is what licenses the
backtester to precompute a whole series once and index it.

`None` padding in the warm-up means NOT YET COMPUTABLE and must never be
coerced to 0.0. A zeroed warm-up reads as a genuine value and silently changes
every gate downstream.
"""
from __future__ import annotations

import math
from typing import Sequence


def sma(values: Sequence[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if n <= 0:
        return out
    run = 0.0
    for i, v in enumerate(values):
        run += v
        if i >= n:
            run -= values[i - n]
        if i >= n - 1:
            out[i] = run / n
    return out


def ema(values: Sequence[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if n <= 0 or len(values) < n:
        return out
    k = 2.0 / (n + 1.0)
    seed = sum(values[:n]) / n
    out[n - 1] = seed
    prev = seed
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1.0 - k)
        out[i] = prev
    return out


def rsi(values: Sequence[float], n: int = 14) -> list[float | None]:
    """Wilder RSI."""
    out: list[float | None] = [None] * len(values)
    if len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / n, losses / n
    out[n] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(n + 1, len(values)):
        d = values[i] - values[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def true_range(high: Sequence[float], low: Sequence[float],
               close: Sequence[float]) -> list[float]:
    out: list[float] = [0.0] * len(close)
    for i in range(len(close)):
        out[i] = (high[i] - low[i]) if i == 0 else max(
            high[i] - low[i], abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]))
    return out


def atr(high: Sequence[float], low: Sequence[float], close: Sequence[float],
        n: int = 14) -> list[float | None]:
    """Wilder ATR in PRICE units."""
    tr = true_range(high, low, close)
    out: list[float | None] = [None] * len(close)
    if len(close) < n + 1:
        return out
    a = sum(tr[1:n + 1]) / n
    out[n] = a
    for i in range(n + 1, len(close)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def macd(values: Sequence[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[list[float | None], list[float | None],
                                   list[float | None]]:
    ef, es = ema(values, fast), ema(values, slow)
    line = [None if (ef[i] is None or es[i] is None) else ef[i] - es[i]
            for i in range(len(values))]
    dense = [v for v in line if v is not None]
    sig_dense = ema(dense, signal)
    sig: list[float | None] = [None] * len(values)
    k = 0
    for i, v in enumerate(line):
        if v is not None:
            sig[i] = sig_dense[k]
            k += 1
    hist = [None if (line[i] is None or sig[i] is None) else line[i] - sig[i]
            for i in range(len(values))]
    return line, sig, hist


def roc(values: Sequence[float], n: int = 10) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(n, len(values)):
        prev = values[i - n]
        out[i] = None if prev == 0 else (values[i] / prev - 1.0) * 100.0
    return out


def adx(high: Sequence[float], low: Sequence[float], close: Sequence[float],
        n: int = 14) -> list[float | None]:
    """Wilder ADX -- trend STRENGTH, direction-free. Used as a filter, never
    as a direction."""
    size = len(close)
    out: list[float | None] = [None] * size
    if size < 2 * n + 1:
        return out
    tr = true_range(high, low, close)
    pdm, ndm = [0.0] * size, [0.0] * size
    for i in range(1, size):
        up, dn = high[i] - high[i - 1], low[i - 1] - low[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        ndm[i] = dn if (dn > up and dn > 0) else 0.0
    atr_s = sum(tr[1:n + 1])
    p_s, n_s = sum(pdm[1:n + 1]), sum(ndm[1:n + 1])
    dxs: list[float] = []
    for i in range(n + 1, size):
        atr_s = atr_s - atr_s / n + tr[i]
        p_s = p_s - p_s / n + pdm[i]
        n_s = n_s - n_s / n + ndm[i]
        if atr_s <= 0:
            continue
        pdi, ndi = 100.0 * p_s / atr_s, 100.0 * n_s / atr_s
        denom = pdi + ndi
        dxs.append(0.0 if denom == 0 else 100.0 * abs(pdi - ndi) / denom)
        if len(dxs) == n:
            out[i] = sum(dxs) / n
        elif len(dxs) > n:
            out[i] = (out[i - 1] * (n - 1) + dxs[-1]) / n
    return out


def rolling_max(values: Sequence[float], n: int, end: int) -> float | None:
    """max over the n bars ENDING at `end` inclusive. `end` is caller-shifted
    when a look-back must exclude the current bar."""
    if end < n - 1 or end >= len(values) or end < 0:
        return None
    return max(values[end - n + 1:end + 1])


def rolling_min(values: Sequence[float], n: int, end: int) -> float | None:
    if end < n - 1 or end >= len(values) or end < 0:
        return None
    return min(values[end - n + 1:end + 1])


def percentile(values: Sequence[float], q: float) -> float | None:
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * max(0.0, min(1.0, q / 100.0))
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def percentile_rank(series: Sequence[float | None], value: float | None
                    ) -> float | None:
    """Where `value` sits in `series`, 0-100. None when unmeasurable -- an
    unknown percentile must not read as 0 (calm) or 100 (danger)."""
    xs = [v for v in series if v is not None]
    if value is None or len(xs) < 10:
        return None
    return 100.0 * sum(1 for x in xs if x <= value) / len(xs)


def realized_vol(values: Sequence[float], n: int = 24) -> float | None:
    """sd of log returns over the last n bars, unannualised."""
    if len(values) < n + 1:
        return None
    rs = []
    for i in range(len(values) - n, len(values)):
        p0, p1 = values[i - 1], values[i]
        if p0 > 0 and p1 > 0:
            rs.append(math.log(p1 / p0))
    if len(rs) < 2:
        return None
    m = sum(rs) / len(rs)
    return math.sqrt(sum((r - m) ** 2 for r in rs) / (len(rs) - 1))


def swing_high(high: Sequence[float], i: int, left: int = 2, right: int = 2
               ) -> bool:
    """A pivot CONFIRMED only once `right` bars have closed after it. A caller
    asking about bar i must therefore already be at i+right -- this never asks
    the future for permission."""
    if i - left < 0 or i + right >= len(high):
        return False
    return all(high[i] > high[j] for j in range(i - left, i)) and \
        all(high[i] > high[j] for j in range(i + 1, i + right + 1))


def swing_low(low: Sequence[float], i: int, left: int = 2, right: int = 2
              ) -> bool:
    if i - left < 0 or i + right >= len(low):
        return False
    return all(low[i] < low[j] for j in range(i - left, i)) and \
        all(low[i] < low[j] for j in range(i + 1, i + right + 1))


def last_swing(values: Sequence[float], i: int, kind: str, left: int = 2,
               right: int = 2, lookback: int = 60) -> float | None:
    """The most recent CONFIRMED pivot at or before bar i."""
    test = swing_high if kind == "high" else swing_low
    for j in range(i - right, max(-1, i - lookback), -1):
        if j - left < 0:
            break
        if test(values, j, left, right):
            return values[j]
    return None


def made_higher_high(high: Sequence[float], i: int, window: int = 20,
                     left: int = 2, right: int = 2) -> bool:
    """Market structure: is the most recent CONFIRMED swing high above the one
    before it? A bearish regime requires this to be FALSE (spec 5)."""
    pivots: list[float] = []
    for j in range(i - right, max(-1, i - window * 3), -1):
        if j - left < 0:
            break
        if swing_high(high, j, left, right):
            pivots.append(high[j])
        if len(pivots) >= 2:
            break
    if len(pivots) < 2:
        return False          # not enough structure to claim a higher high
    return pivots[0] > pivots[1]


def made_lower_low(low: Sequence[float], i: int, window: int = 20,
                   left: int = 2, right: int = 2) -> bool:
    pivots: list[float] = []
    for j in range(i - right, max(-1, i - window * 3), -1):
        if j - left < 0:
            break
        if swing_low(low, j, left, right):
            pivots.append(low[j])
        if len(pivots) >= 2:
            break
    if len(pivots) < 2:
        return False
    return pivots[0] < pivots[1]


def slope(series: Sequence[float | None], i: int, n: int = 5) -> float | None:
    """Normalised change over n bars. None when either endpoint is unknown."""
    if i - n < 0 or i >= len(series) or series[i] is None \
            or series[i - n] is None:
        return None
    base = abs(series[i - n]) or 1e-9
    return (series[i] - series[i - n]) / base


def zscore(values: Sequence[float], value: float | None = None
           ) -> float | None:
    xs = [v for v in values if v is not None]
    if len(xs) < 5:
        return None
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    if sd <= 0:
        return None
    v = xs[-1] if value is None else value
    return (v - m) / sd


def cusum(values: Sequence[float], target: float | None = None,
          drift: float = 0.5) -> tuple[list[float], list[float]]:
    """One-sided CUSUM pair (positive, negative) in units of sd.

    A documented, boring change-point method chosen over anything fancier on
    purpose: it has two parameters, both interpretable, and a simple baseline
    is what the spec asks to beat before reaching for a model."""
    xs = [v for v in values if v is not None]
    if len(xs) < 5:
        return [], []
    m = target if target is not None else sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) or 1e-9
    pos, neg = [], []
    sp = sn = 0.0
    for x in xs:
        z = (x - m) / sd
        sp = max(0.0, sp + z - drift)
        sn = min(0.0, sn + z + drift)
        pos.append(sp)
        neg.append(sn)
    return pos, neg


def assert_causal(fn, series, *args, cut: int = 5, **kw) -> bool:
    """Recompute on a truncated tape; require overlapping values identical."""
    full = fn(series, *args, **kw)
    part = fn(series[:len(series) - cut], *args, **kw)
    if isinstance(full, tuple):
        full, part = full[0], part[0]
    for i in range(len(part)):
        a, b = full[i], part[i]
        if a is None and b is None:
            continue
        if a is None or b is None or abs(a - b) > 1e-9:
            return False
    return True
