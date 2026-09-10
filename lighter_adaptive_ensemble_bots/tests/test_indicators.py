"""Indicators: correctness against hand-computable cases, and CAUSALITY."""
import math

import pytest

from lighter_bots import indicators as ind


def test_sma_and_ema_warmup_is_none_not_zero():
    v = [1.0] * 10
    s = ind.sma(v, 5)
    assert s[:4] == [None] * 4, "a zeroed warm-up reads as a real value"
    assert s[4] == pytest.approx(1.0)
    e = ind.ema(v, 5)
    assert e[3] is None and e[4] == pytest.approx(1.0)


def test_rsi_is_100_on_a_monotone_rise_and_0_on_a_fall():
    up = [float(i) for i in range(1, 40)]
    assert ind.rsi(up, 14)[-1] == pytest.approx(100.0)
    assert ind.rsi(list(reversed(up)), 14)[-1] == pytest.approx(0.0)


def test_rsi_midpoint_on_alternating_equal_moves():
    v, px = [100.0], 100.0
    for i in range(60):
        px = px + (1.0 if i % 2 == 0 else -1.0)
        v.append(px)
    assert 40.0 < ind.rsi(v, 14)[-1] < 60.0


def test_atr_of_a_constant_range_is_that_range():
    n = 40
    c = [100.0] * n
    h = [101.0] * n
    l = [99.0] * n
    assert ind.atr(h, l, c, 14)[-1] == pytest.approx(2.0, abs=1e-9)


def test_true_range_uses_the_previous_close():
    h, l, c = [10.0, 12.0], [9.0, 11.5], [9.5, 11.8]
    tr = ind.true_range(h, l, c)
    assert tr[1] == pytest.approx(max(12.0 - 11.5, abs(12.0 - 9.5),
                                      abs(11.5 - 9.5)))


def test_macd_line_follows_the_trend_and_the_histogram_does_not():
    """The LINE is direction; the HISTOGRAM is acceleration.

    An earlier version of this test asserted the histogram was negative on a
    falling series. It is not, and the reason matters for `signals.py`: a
    decaying exponential has ema12 BELOW ema26 (line negative, trend down)
    while the decay DECELERATES, so line > signal and the histogram is
    POSITIVE. Gating a short on `hist < 0` therefore rejects the cleanest
    part of a downtrend. `momentum_component` weights the histogram at 30% of
    15 points for exactly this reason -- it is confirmation, not direction."""
    up = [100.0 * (1.02 ** i) for i in range(120)]
    down = list(reversed(up))
    assert ind.macd(up)[0][-1] > 0, "line positive in an uptrend"
    assert ind.macd(down)[0][-1] < 0, "line negative in a downtrend"
    assert ind.macd(up)[2][-1] > 0
    assert ind.macd(down)[2][-1] > 0, "decelerating decay: histogram positive"


def test_adx_is_high_in_a_trend_and_low_in_chop():
    n = 200
    trend = [100.0 * (1.01 ** i) for i in range(n)]
    chop = [100.0 + (1.0 if i % 2 else -1.0) for i in range(n)]
    at = ind.adx([x * 1.005 for x in trend], [x * 0.995 for x in trend],
                 trend, 14)[-1]
    ac = ind.adx([x * 1.005 for x in chop], [x * 0.995 for x in chop],
                 chop, 14)[-1]
    assert at > ac


def test_bollinger_brackets_the_mean():
    v = [100.0 + math.sin(i / 3.0) for i in range(60)]
    lo, mid, hi = ind.bollinger(v, 20, 2.0)
    assert lo[-1] < mid[-1] < hi[-1]


def test_rolling_window_respects_the_end_index():
    v = [1.0, 5.0, 3.0, 9.0, 2.0]
    assert ind.rolling_max(v, 3, 3) == 9.0
    assert ind.rolling_max(v, 3, 2) == 5.0, "end=2 must not see index 3"
    assert ind.rolling_min(v, 3, 2) == 1.0
    assert ind.rolling_max(v, 3, 1) is None


def test_percentile_endpoints_and_interpolation():
    v = [1.0, 2.0, 3.0, 4.0]
    assert ind.percentile(v, 0) == 1.0
    assert ind.percentile(v, 100) == 4.0
    assert ind.percentile(v, 50) == pytest.approx(2.5)


@pytest.mark.parametrize("fn,args", [
    (ind.rsi, (14,)), (ind.ema, (20,)), (ind.sma, (20,)), (ind.roc, (10,)),
])
def test_every_series_indicator_is_causal(fn, args):
    """Recompute on a truncated tape; overlapping values must be identical.
    An indicator that peeks CHANGES when you hide the future."""
    import random
    random.seed(7)
    v = [100.0]
    for _ in range(300):
        v.append(v[-1] * (1 + random.gauss(0, 0.01)))
    assert ind.assert_causal(fn, v, *args, cut=10)


def test_atr_and_adx_are_causal():
    import random
    random.seed(11)
    c = [100.0]
    for _ in range(300):
        c.append(c[-1] * (1 + random.gauss(0, 0.01)))

    def _atr(s, n):
        return ind.atr([x * 1.004 for x in s], [x * 0.996 for x in s], s, n)

    def _adx(s, n):
        return ind.adx([x * 1.004 for x in s], [x * 0.996 for x in s], s, n)

    assert ind.assert_causal(_atr, c, 14, cut=10)
    assert ind.assert_causal(_adx, c, 14, cut=10)


def test_swing_pivot_needs_bars_on_both_sides():
    h = [1.0, 2.0, 5.0, 2.0, 1.0]
    assert ind.swing_high(h, 2, 2, 2) is True
    assert ind.swing_high(h, 4, 2, 2) is False, "no confirmation bars to the right"


def test_realized_vol_is_zero_on_a_flat_tape_and_positive_otherwise():
    assert ind.realized_vol([100.0] * 50, 24) == pytest.approx(0.0)
    import random
    random.seed(3)
    v = [100.0]
    for _ in range(60):
        v.append(v[-1] * (1 + random.gauss(0, 0.02)))
    assert ind.realized_vol(v, 24) > 0
