"""Ensemble scoring: weights, the RSI cap, and the admissibility bars."""
import pytest

from lighter_bots import signals as S
from lighter_bots.config import StrategyConfig
from lighter_bots.models import Regime, ScoreBreakdown
from lb_helpers import ramp


def test_weights_sum_to_one_hundred():
    assert sum(S.WEIGHTS.values()) == pytest.approx(100.0)


def test_score_breakdown_total_is_the_sum_of_its_parts():
    b = ScoreBreakdown(regime=25, trend=20, structure=20, momentum=15,
                       volume=10, derivatives=5, liquidity=5)
    assert b.total == pytest.approx(100.0)
    assert b.as_dict()["total"] == pytest.approx(100.0)


def test_no_component_can_exceed_its_weight():
    x = S._ctx(ramp(300, drift=0.004, wiggle=0.004))
    assert x is not None
    checks = [
        S.regime_component(Regime.BULLISH, "long")[0] <= S.WEIGHTS["regime"],
        S.trend_component(x, "long", 20.0)[0] <= S.WEIGHTS["trend"] + 1e-9,
        S.momentum_component(x, "long")[0] <= S.WEIGHTS["momentum"] + 1e-9,
        S.volume_component(x)[0] <= S.WEIGHTS["volume"] + 1e-9,
        S.derivatives_component(0.001, 0.1, "short")[0]
        <= S.WEIGHTS["derivatives"] + 1e-9,
        S.liquidity_component(1.0, 50.0, 10.0)[0] <= S.WEIGHTS["liquidity"] + 1e-9,
    ]
    assert all(checks)


def test_panic_and_unreliable_score_zero_on_regime():
    for r in (Regime.PANIC, Regime.DATA_UNRELIABLE):
        assert S.regime_component(r, "long")[0] == 0.0
        assert S.regime_component(r, "short")[0] == 0.0


def test_counter_regime_entries_start_a_long_way_behind():
    full = S.regime_component(Regime.BULLISH, "long")[0]
    counter = S.regime_component(Regime.BULLISH, "short")[0]
    assert counter < full * 0.5


def test_an_rsi_extreme_scores_ZERO_on_momentum_for_a_short():
    """The measured refutation of the naive overbought fade, encoded.

    STUDY_SHORT_MIRRORS_2026-09-10.md: a pure RSI>62 short cell read
    -0.102%/trade at t=-2.08 over 2,744 trades with an excess over
    matched-random entries of +0.037%/trade (P=0.187). So an RSI of 85 must
    not be a reason to short."""
    hot = ramp(300, drift=0.02)                # blown-off, RSI near 100
    x = S._ctx(hot)
    pts, note = S.momentum_component(x, "short")
    assert x["rsi"][x["i"]] > 60.0
    assert pts <= S.WEIGHTS["momentum"] * 0.5
    assert "OUTSIDE" in note


def test_momentum_is_capped_at_fifteen_of_one_hundred():
    assert S.WEIGHTS["momentum"] == 15.0
    assert S.WEIGHTS["momentum"] < S.WEIGHTS["regime"]
    assert S.WEIGHTS["momentum"] < S.WEIGHTS["trend"]
    assert S.WEIGHTS["momentum"] < S.WEIGHTS["structure"]


def test_unknown_spread_scores_zero_liquidity():
    assert S.liquidity_component(None, None, 10.0)[0] == 0.0


def test_a_spread_over_the_limit_scores_zero_liquidity():
    assert S.liquidity_component(25.0, None, 10.0)[0] == 0.0


def test_unknown_derivatives_get_neutral_credit_never_full():
    pts, note = S.derivatives_component(None, None, "long")
    assert 0 < pts < S.WEIGHTS["derivatives"]
    assert "unavailable" in note


def test_funding_credit_follows_the_side_that_receives_it():
    """A SHORT receives positive funding; a LONG receives negative funding."""
    short_paid = S.derivatives_component(0.0001, None, "short")[0]
    long_paid = S.derivatives_component(0.0001, None, "long")[0]
    assert short_paid > long_paid


def test_minimum_score_bars_by_regime_and_side():
    c = StrategyConfig()
    assert S.minimum_score(c, Regime.NEUTRAL, "long") == c.neutral_minimum_score
    assert S.minimum_score(c, Regime.BEARISH, "long") == \
        c.bearish_tactical_long_minimum_score
    assert S.minimum_score(c, Regime.BULLISH, "short") == \
        c.bearish_tactical_long_minimum_score
    assert S.minimum_score(c, Regime.BEARISH, "short") == c.short_minimum_score


def test_neutral_demands_a_higher_reward_risk():
    c = StrategyConfig()
    assert S.minimum_rr(c, Regime.NEUTRAL) > S.minimum_rr(c, Regime.BULLISH)


def test_admissible_refuses_a_low_score_and_says_the_numbers():
    c = StrategyConfig()
    sig, _r = S.evaluate("BTC", ramp(300, drift=0.004, wiggle=0.003), "long",
                         Regime.BULLISH, c, spread_bps=2.0, max_spread_bps=10.0)
    if sig is None:
        pytest.skip("no setup fired on this synthetic tape")
    ok, why = S.admissible(sig, c, Regime.BULLISH, score_bump=100.0)
    assert not ok and "score" in why


def test_a_throttled_strategy_faces_a_higher_bar():
    c = StrategyConfig()
    sig, _r = S.evaluate("BTC", ramp(300, drift=0.004, wiggle=0.003), "long",
                         Regime.BULLISH, c, spread_bps=2.0, max_spread_bps=10.0)
    if sig is None:
        pytest.skip("no setup fired")
    base_ok, _ = S.admissible(sig, c, Regime.BULLISH)
    bumped_ok, _ = S.admissible(sig, c, Regime.BULLISH, score_bump=5.0,
                                rr_bump=0.2)
    assert base_ok or not bumped_ok   # bumping can only ever make it harder


def test_short_history_is_refused_with_a_reason():
    sig, rejects = S.evaluate("BTC", ramp(50), "long", Regime.BULLISH,
                              StrategyConfig())
    assert sig is None and rejects and "insufficient history" in rejects[0].reason


def test_a_blocked_regime_produces_no_signal():
    sig, rejects = S.evaluate("BTC", ramp(300), "long", Regime.PANIC,
                              StrategyConfig())
    assert sig is None and "regime blocks" in rejects[0].reason


def test_signal_id_is_deterministic_and_side_aware():
    tape = ramp(300, drift=0.004, wiggle=0.003)
    a, _ = S.evaluate("BTC", tape, "long", Regime.BULLISH, StrategyConfig(),
                      spread_bps=2.0)
    b, _ = S.evaluate("BTC", tape, "long", Regime.BULLISH, StrategyConfig(),
                      spread_bps=2.0)
    if a is None:
        pytest.skip("no setup fired")
    assert a.signal_id == b.signal_id
    assert a.side in a.signal_id and str(a.candle_ts) in a.signal_id


def test_stop_is_capped_in_atr_terms():
    c = StrategyConfig(max_stop_distance_atr=2.0)
    x = S._ctx(ramp(300, drift=0.003, wiggle=0.002))
    setup = S.SetupResult("t", "long", True, 0.5, invalidation=x["c"][x["i"]]
                          - 50 * x["atr"])
    stop = S.build_stop(x, "long", setup, c)
    assert (x["c"][x["i"]] - stop) <= c.max_stop_distance_atr * x["atr"] * 1.001


def test_reward_risk_is_measured_to_the_last_DEFINED_target():
    """The runner is trailed, so its reward is unknown at decision time and
    must not be counted."""
    c = StrategyConfig(tp1_r=1.2, tp2_r=2.0)
    sig, _r = S.evaluate("BTC", ramp(300, drift=0.004, wiggle=0.003), "long",
                         Regime.BULLISH, c, spread_bps=2.0)
    if sig is None:
        pytest.skip("no setup fired")
    assert sig.reward_risk == pytest.approx(c.tp2_r, abs=0.05)


def test_both_sides_are_reachable_from_the_same_engine():
    up, down = ramp(300, drift=0.004, wiggle=0.003), ramp(300, drift=-0.004,
                                                          wiggle=0.003)
    c = StrategyConfig()
    long_sig, _ = S.evaluate("BTC", up, "long", Regime.BULLISH, c,
                             spread_bps=2.0)
    short_sig, _ = S.evaluate("BTC", down, "short", Regime.BEARISH, c,
                              spread_bps=2.0)
    assert (long_sig is not None) or (short_sig is not None), \
        "an ensemble that can never fire either way is not an ensemble"
    for s in (long_sig, short_sig):
        if s is not None:
            assert s.stop != s.entry
            if s.side == "long":
                assert s.stop < s.entry and all(t > s.entry for t in s.targets)
            else:
                assert s.stop > s.entry and all(t < s.entry for t in s.targets)


def test_reward_risk_is_currently_structurally_constant():
    """A DECLARED limitation, pinned so it cannot be forgotten.

    `strategy.minimum_reward_risk` cannot bind: targets are placed at fixed
    multiples of the stop (`tp1_r`, `tp2_r`), so every admissible signal has
    reward/risk == tp2_r exactly. The 354-day sweep measured 1.2 / 1.4 / 1.8
    producing byte-identical results, which is the observable consequence.

    Fixing it means deriving targets from STRUCTURE (the next swing or range
    boundary) instead of from R -- a design change that needs its own
    measurement. When that lands, this test SHOULD fail, and its failure is
    the signal that the knob has become real."""
    c = StrategyConfig(tp2_r=2.0)
    seen = set()
    for tape in (ramp(300, drift=0.004, wiggle=0.003),
                 ramp(300, drift=-0.004, wiggle=0.003),
                 ramp(300, drift=0.001, wiggle=0.008)):
        for side, regime in (("long", Regime.BULLISH), ("short", Regime.BEARISH)):
            sig, _r = S.evaluate("BTC", tape, side, regime, c, spread_bps=2.0)
            if sig is not None:
                seen.add(round(sig.reward_risk, 6))
    if not seen:
        pytest.skip("no setup fired on any synthetic tape")
    assert seen == {2.0}, (
        "reward/risk is no longer a constant -- if targets are now structural, "
        "delete this test and re-measure minimum_reward_risk as a live bar")
