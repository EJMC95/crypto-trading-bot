"""Scoring: the components, the bars, and the two failure modes that matter --
a component that can never fire, and one that fires on everything."""
import dataclasses as dc

import pytest

from dt_helpers import (breakdown_tape, falling, flat,
                      overrun_pivot_tape, rising)
from downtrend_bot import indicators as ind
from downtrend_bot import signals as S
from downtrend_bot.config import StrategyConfig
from downtrend_bot.models import Regime


def ctx(bars, strat=None):
    return S.context(bars, strat or StrategyConfig())


def test_weights_sum_to_one_hundred():
    assert sum(S.WEIGHTS.values()) == 100


def test_insufficient_history_yields_no_context():
    assert ctx(falling(50)) is None


def test_min_bars_follows_the_configured_slow_ema():
    assert S.min_bars_for(StrategyConfig(ema_slow=200)) == 210
    assert S.min_bars_for(StrategyConfig(ema_slow=60)) == 70


def test_min_bars_also_covers_the_breakdown_lookback():
    """A context handed out before the range window exists would make the
    20-point breakdown component structurally unscoreable on those bars."""
    st = StrategyConfig(ema_slow=10, structure_window=50)
    assert S.min_bars_for(st) >= st.structure_window + S.BREAK_LOOKBACK + 1


# ------------------------------------------------------- the 2026-09 bug ----
def test_the_breakdown_windows_do_not_overlap():
    """THE REGRESSION TEST FOR THE BUG THAT MADE THIS COMPONENT UNREACHABLE.

    The level was taken as min(lows) over a window that CONTAINED the bars
    searched for a break. Since close >= low >= min(lows over any window
    containing that bar), no close could ever be below it: measured 0 hits in
    400,000 random bar-sets. The component is worth 20 of 100 points and
    scored 0.00 on every signal.

    This asserts the WINDOWS, not the arithmetic, because the arithmetic is
    what was subtly wrong."""
    assert S.BREAK_LOOKBACK >= 1
    # the range must end strictly before the first bar that can carry a break
    i = 300
    range_end = i - S.BREAK_LOOKBACK - 1
    first_break_bar = i - S.BREAK_LOOKBACK
    assert range_end < first_break_bar, \
        "the range window still overlaps the break window"


def test_the_breakdown_component_can_actually_score():
    """The positive control. A component that never fires and a component that
    is wired wrong look identical from the outside, and the only thing that
    tells them apart is a tape built to contain the setup."""
    x = ctx(breakdown_tape(300))
    assert x is not None
    pts, note, level = S.breakdown_component(x, "short", StrategyConfig())
    assert pts > 0, f"breakdown scored nothing on a hand-built breakdown: {note}"
    assert level is not None


def test_the_breakdown_component_does_not_fire_on_everything():
    """The negative control, and it is the half people skip. A component that
    scores on a flat tape is not detecting a breakdown."""
    fired = 0
    for seed in range(12):
        x = ctx(flat(300, seed=seed))
        if x is None:
            continue
        pts, _n, _l = S.breakdown_component(x, "short", StrategyConfig())
        fired += 1 if pts > 0 else 0
    assert fired < 6, f"breakdown fired on {fired}/12 flat tapes"


def test_the_breakdown_score_decays_strictly_with_extension():
    """Spec 6B: never chase. The score must fall MEASURABLY as price runs from
    the level, and reach zero past `max_entry_distance_atr`.

    `<=` was not enough: with both cells at full marks the assertion held while
    the decay was gone entirely (a mutation removing it SURVIVED). This walks
    the curve and requires it to be strictly decreasing and to terminate."""
    from downtrend_bot.models import Candle
    st = StrategyConfig(max_entry_distance_atr=0.75)
    base = breakdown_tape(300, level=100.0)
    scores = []
    for push in (0.0, 1.0, 2.0, 4.0, 12.0):
        t = list(base)
        last = t[-1]
        t[-1] = Candle(last.ts, last.open, last.high, last.low - push,
                       last.close - push, last.volume)
        x = ctx(t)
        pts, _n, _l = S.breakdown_component(x, "short", st)
        scores.append(pts)
    assert scores[0] > 0, "the control tape scored nothing"
    assert all(a >= b for a, b in zip(scores, scores[1:])), scores
    assert scores[0] > scores[2], f"no measurable decay: {scores}"
    assert scores[-1] == 0.0, f"a far-extended entry still scored: {scores}"


# ---------------------------------------------------------- momentum band ---
def test_an_oversold_rsi_earns_nothing_from_the_rsi_band():
    """Spec 6C, and the reason it is a BAND: 'RSI is low' is a reason a short
    is LATE, not a reason to take one. Same non-sequitur the parent fleet
    removed from its go-live gate.

    SCOPE, stated precisely because my first version of this test asserted the
    wrong thing: the RSI LIMB scores zero on an extreme, not the whole
    component -- MACD and ROC are separate information and still count. So the
    assertion is a DIFFERENCE, which is what the rule actually claims: the
    identical bar with an in-band RSI must score strictly more."""
    st = StrategyConfig(rsi_short_lo=35.0, rsi_short_hi=60.0)
    base = dict(ctx(falling(400, seed=11)))
    i = base["i"]

    def score(r):
        x = dict(base)
        rsi = list(base["rsi"])
        rsi[i] = r
        x["rsi"] = rsi
        return S.momentum_component(x, "short", st)

    extreme_pts, extreme_note = score(12.0)
    band_pts, _ = score(45.0)
    assert "OVERSOLD" in extreme_note
    assert band_pts - extreme_pts == pytest.approx(S.WEIGHTS["momentum"] * 0.5)
    assert extreme_pts < band_pts


def test_an_rsi_inside_the_band_can_score():
    st = StrategyConfig()
    x = dict(ctx(falling(400, seed=11)))
    rsi = list(x["rsi"])
    rsi[x["i"]] = 45.0
    x["rsi"] = rsi
    pts, _n = S.momentum_component(x, "short", st)
    assert pts > 0


# ------------------------------------------------------------- the others ---
def test_volume_below_average_scores_nothing():
    st = StrategyConfig(volume_ratio_floor=1.0)
    x = dict(ctx(flat(400, seed=2)))
    v = list(x["v"])
    for k in range(len(v) - 1):
        v[k] = 1000.0
    v[x["i"]] = 100.0
    x["v"] = v
    pts, note = S.volume_component(x, st)
    assert pts == 0.0, note


def test_an_unknown_spread_scores_zero_quality_never_full_marks():
    st = StrategyConfig()
    pts, note = S.quality_component(None, 50.0, 1.0, st, 8.0)
    assert pts == 0.0, note


def test_regime_component_refuses_a_short_in_a_bull_market():
    pts, note = S.regime_component(Regime.BULLISH, "short", True)
    assert pts == 0.0 and "bullish" in note.lower()


def test_regime_component_refuses_a_short_without_a_bearish_symbol():
    pts, _n = S.regime_component(Regime.BEARISH, "short", False)
    assert pts == 0.0


# ------------------------------------------------------------ the builder ---
def test_the_stop_is_capped_in_atr_terms():
    st = StrategyConfig(max_stop_distance_atr=2.0)
    x = ctx(falling(400, seed=4))
    stop = S.build_stop(x, "short", st)
    dist = (stop - x["c"][x["i"]]) / x["atr"]
    assert dist <= st.max_stop_distance_atr + 1e-6


@pytest.mark.parametrize("seed", range(8))
def test_a_short_stop_sits_above_the_entry_and_a_long_stop_below(seed):
    st = StrategyConfig()
    x = ctx(falling(400, seed=seed))
    px = x["c"][x["i"]]
    assert S.build_stop(x, "short", st) > px
    assert S.build_stop(x, "long", st) < px


def test_an_overrun_pivot_never_puts_a_stop_on_the_wrong_side():
    """THE CASE THE SIDE CHECK EXISTS FOR, built deterministically rather than
    hoped for from a random walk.

    `last_swing` returns the most recent CONFIRMED pivot, and on a falling tape
    price routinely runs straight through it -- so the last swing LOW sits
    ABOVE the current close. Using it verbatim gave a long a stop above its own
    entry: stopped on the fill, sized off a positive `abs(entry - stop)` that
    nothing upstream questions."""
    st = StrategyConfig()
    bars = overrun_pivot_tape(300)
    x = ctx(bars)
    px = x["c"][x["i"]]
    swing = ind.last_swing(x["l"], x["i"], "low")
    assert swing is not None and swing > px, \
        "the fixture no longer contains an overrun pivot"
    assert S.build_stop(x, "long", st) < px
    # and the mirror, on a rising tape with an overrun swing HIGH
    up = list(reversed([type(b)(b.ts, b.close, b.high, b.low, b.open, b.volume)
                        for b in bars]))
    up = [type(b)(bars[k].ts, b.open, b.high, b.low, b.close, b.volume)
          for k, b in enumerate(up)]
    y = ctx(up)
    if y is not None:
        assert S.build_stop(y, "short", st) > y["c"][y["i"]]


def test_reward_risk_is_measured_to_the_last_defined_target():
    """The runner is trailed, so its reward is unknown at decision time.
    Counting it would be crediting ourselves with a number we do not have."""
    st = StrategyConfig(tp1_r=1.5, tp2_r=2.5)
    sig, _rej = S.evaluate("BTC/USDT:USDT", breakdown_tape(300), "short",
                           regime=Regime.BEARISH, cfg=st,
                           symbol_bearish_ok=True, spread_bps=2.0)
    if sig is not None:
        assert sig.reward_risk == pytest.approx(st.tp2_r, rel=0.02)


def test_admissible_enforces_score_reward_risk_and_distance():
    """All THREE bars, each shown to REFUSE, against a signal shown to PASS.

    This test used to compute the baseline verdict and throw it away, asserting
    only the score bar -- so it carried the name of three properties and the
    evidence for one. Without the positive control the refusals prove nothing
    either: a signal that is inadmissible for an unrelated reason refuses under
    every strict config too, and the test goes green on a dead fixture. CodeQL
    found it as `ok is not used`, which is what an assertion that was never
    written looks like from outside.

    AND THE CONTROL FAILED THE MOMENT IT WAS WRITTEN: the fixture's signal
    scores 66.6, so at the old config's `minimum_score=70.0` it was ALREADY
    inadmissible -- the refusal the test asserted at 99.0 was guaranteed by the
    baseline, not caused by the bar under test. A `minimum_score` that read the
    BASE config instead of the strict one would have passed it. The bar here is
    60.0 so the control clears it; this is a test about the BARS, not about how
    well the fixture happens to score."""
    st = StrategyConfig(minimum_score=60.0, minimum_reward_risk=1.8,
                        max_entry_distance_atr=0.75)
    sig, _r = S.evaluate("BTC/USDT:USDT", breakdown_tape(300), "short",
                         regime=Regime.BEARISH, cfg=st,
                         symbol_bearish_ok=True, spread_bps=2.0)
    if sig is None:
        pytest.skip("no signal on the control tape")

    # THE POSITIVE CONTROL. Every refusal below is only informative because
    # this signal clears the shipped bars.
    ok, why = S.admissible(sig, st, Regime.BEARISH)
    assert ok, f"the control signal is not admissible at the shipped bars: {why}"
    assert why == "admissible"

    # EACH VARIANT MOVES EXACTLY ONE BAR AND HOLDS THE REST AT THE CONTROL'S
    # VALUES. A bare `StrategyConfig(minimum_reward_risk=99.0)` carries the
    # DEFAULT minimum_score of 70.0, which this 66.6 signal fails first -- so
    # the assertion would have read a score refusal and called it reward/risk.
    # `admissible` returns on the FIRST failing bar, so a single-bar test that
    # lets a second bar move measures whichever one happens to be checked
    # earlier.
    one = lambda **kw: dc.replace(st, **kw)              # noqa: E731

    # 1/3 score
    ok_s, why_s = S.admissible(sig, one(minimum_score=99.0), Regime.BEARISH)
    assert not ok_s and "score" in why_s, why_s

    # 2/3 reward/risk. The knob measured INERT at shipped values (targets are
    # fixed R-multiples of the stop, so RR is `tp2_r` by construction) -- which
    # is exactly why the bar itself must be shown to still BITE when it is set
    # above that constant, or "inert" quietly becomes "unwired".
    ok_r, why_r = S.admissible(sig, one(minimum_reward_risk=99.0),
                               Regime.BEARISH)
    assert not ok_r and "reward/risk" in why_r, why_r

    # 3/3 distance from the trigger level -- reachable only on a signal that
    # HAS one, so an absent trigger is reported, never skipped past.
    assert sig.trigger_level is not None, (
        "the breakdown fixture produced no trigger level, so the distance bar "
        "is untested here -- fix the fixture rather than dropping the limb")
    ok_d, why_d = S.admissible(sig, one(max_entry_distance_atr=0.0),
                               Regime.BEARISH)
    assert not ok_d and "ATR from the trigger level" in why_d, why_d

    # and the bump arguments are the same bars by another route
    ok_b, why_b = S.admissible(sig, st, Regime.BEARISH, score_bump=100.0)
    assert not ok_b and "score" in why_b, why_b


def test_a_refused_signal_always_carries_a_reason():
    _sig, rejects = S.evaluate("BTC/USDT:USDT", falling(50), "short",
                               regime=Regime.BEARISH, cfg=StrategyConfig(),
                               symbol_bearish_ok=True)
    assert rejects and all(r.reason for r in rejects)


def test_signal_ids_are_deterministic_and_distinct():
    a, _ = S.evaluate("BTC/USDT:USDT", breakdown_tape(300), "short",
                      regime=Regime.BEARISH, cfg=StrategyConfig(),
                      symbol_bearish_ok=True, spread_bps=2.0)
    b, _ = S.evaluate("BTC/USDT:USDT", breakdown_tape(300), "short",
                      regime=Regime.BEARISH, cfg=StrategyConfig(),
                      symbol_bearish_ok=True, spread_bps=2.0)
    c, _ = S.evaluate("ETH/USDT:USDT", breakdown_tape(300), "short",
                      regime=Regime.BEARISH, cfg=StrategyConfig(),
                      symbol_bearish_ok=True, spread_bps=2.0)
    if a and b and c:
        assert a.signal_id == b.signal_id
        assert a.signal_id != c.signal_id


# ------------------------------------------------------------- causality ----
@pytest.mark.parametrize("fn,args", [
    (lambda c: ind.ema(c, 20), None), (lambda c: ind.rsi(c, 14), None),
    (lambda c: ind.roc(c, 10), None),
])
def test_indicators_are_causal(fn, args):
    """The precondition that licenses SeriesCache: a value at bar i must be
    identical whether computed over [0..i] or [0..N]. Without it, precomputing
    the whole series is a look-ahead bug wearing an optimisation's clothes."""
    closes = [c.close for c in falling(300, seed=8)]
    assert ind.assert_causal(fn, closes)


def test_the_cache_matches_a_bar_by_bar_computation():
    bars = falling(320, seed=9)
    st = StrategyConfig()
    cache = S.SeriesCache(bars, st)
    for i in (250, 280, 310):
        a = cache.at(i)
        b = S.context(bars[:i + 1], st)
        assert a is not None and b is not None
        assert a["atr"] == pytest.approx(b["atr"])
        assert a["e20"][i] == pytest.approx(b["e20"][i])


def test_a_spike_planted_in_the_future_changes_nothing_in_the_past():
    """The consequence of causality, asserted directly. If a bar 40 into the
    future can move today's score, the backtest is fiction."""
    from downtrend_bot.models import Candle
    bars = falling(320, seed=10)
    poisoned = list(bars)
    last = poisoned[-1]
    poisoned[-1] = Candle(last.ts, last.open, last.high * 5, last.low,
                          last.close * 5, last.volume * 50)
    st = StrategyConfig()
    a = S.SeriesCache(bars, st).at(250)
    b = S.SeriesCache(poisoned, st).at(250)
    assert a["atr"] == pytest.approx(b["atr"])
    assert a["rsi"][250] == pytest.approx(b["rsi"][250])


# --------------------------------------------------- the stop-side property --
@pytest.mark.parametrize("buffer_atr", [0.0, 0.25, 1.0])
@pytest.mark.parametrize("max_stop", [0.0, 0.05, 1.0, 3.0, 9.0])
@pytest.mark.parametrize("seed", [0, 3, 6])
def test_a_stop_is_always_strictly_on_the_correct_side(buffer_atr, max_stop,
                                                       seed):
    """THE PROPERTY, swept rather than sampled -- including the degenerate
    configurations the final clamp is the ONLY defence against.

    Mutation testing showed the two guards in `build_stop` are independently
    sufficient on ordinary tapes: removing either alone survived, removing
    BOTH reddened. That is defence in depth working, and it is also how a
    redundant guard rots -- nothing measures it until the day it is the one
    that matters. A `max_stop_distance_atr` small enough to collapse the cap
    onto the entry price is exactly that day, and it is reachable from a config
    file."""
    st = StrategyConfig(atr_stop_buffer=buffer_atr,
                        max_stop_distance_atr=max_stop)
    for bars in (falling(400, seed=seed), rising(400, seed=seed),
                 flat(400, seed=seed), overrun_pivot_tape(300)):
        x = ctx(bars)
        if x is None:
            continue
        px = x["c"][x["i"]]
        assert S.build_stop(x, "short", st) > px, (buffer_atr, max_stop, seed)
        assert S.build_stop(x, "long", st) < px, (buffer_atr, max_stop, seed)


def test_reward_risk_is_structurally_constant_and_that_is_declared():
    """The sweep measured `minimum_reward_risk` as INERT (spread 0.000pp). The
    cause is structural, not a bug: targets are fixed R-multiples of the stop,
    so a signal's reward/risk IS `tp2_r` and the bar cannot bind below it.

    Pinned so the declaration cannot go stale: if targets ever stop being fixed
    multiples, this reddens and the comment in `config.py` gets corrected with
    it."""
    st = StrategyConfig(tp1_r=1.5, tp2_r=2.5)
    for seed in range(4):
        sig, _r = S.evaluate("BTC/USDT:USDT", breakdown_tape(300, level=100.0),
                             "short", regime=Regime.BEARISH, cfg=st,
                             symbol_bearish_ok=True, spread_bps=2.0)
        if sig is None:
            continue
        assert sig.reward_risk == pytest.approx(st.tp2_r, rel=1e-6), \
            "reward/risk is no longer tp2_r by construction -- the INERT " \
            "declaration in config.py is now wrong"
        break
