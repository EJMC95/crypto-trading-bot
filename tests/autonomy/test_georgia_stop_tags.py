"""🔮 Georgia's ATR stop is TAG-SPECIFIC, and the split is measured.

[2026-08-20] `trend_breakout` moved 2.5x -> 3.5x on a calibrated paired
counterfactual over her own 68 priced entries (+0.103%/trade, both
chronological halves positive), joining the two counter-trend tags that made
the same move on 2026-07-13.

`range_on` was swept identically and moves the OTHER way — 3.5x reads
-0.280%/trade, t=-2.25, BOTH halves negative — so it stays at 2.5x.

That asymmetry is the whole point of these tests: the easy wrong change here is
a BLANKET widening, and nothing in the code itself says one tag was measured up
while another was measured down.
"""
import lighter_family_bot as fam


def _georgia():
    """The LIVE roster's Georgia — resolved through `live_strategies()` so a
    retirement makes this test disappear with the book rather than pin a
    constant on a corpse."""
    # [2026-09-02 (ws)] her shadow is RETIRED (row-scoped, RETIRED_BOOKS), so
    # the declaration is read rather than the living roster: the stop-tag
    # multipliers are a property of the strategy class, which the override
    # can resurrect at any time, and this test keeps guarding it.
    for b in fam.STRATEGIES:
        if str(getattr(b, "bot", "")).endswith("georgia"):
            return b
    raise AssertionError("could not locate Georgia in STRATEGIES")


def _dist(strategy, tag, atr, px):
    """Read the stop distance for `tag` by driving the real method with a
    stubbed signal — the multiplier is `dist * px / atr` when the carrier cap
    is not binding."""
    orig = strategy.signals
    try:
        strategy.signals = lambda bars, extra: {"atr": atr}
        return strategy.atr_stop_dist(tag, bars=[1], px=px)
    finally:
        strategy.signals = orig


def test_trend_breakout_now_uses_the_wide_counter_trend_multiplier():
    s = _georgia()
    px, atr = 1000.0, 1.0          # tiny ATR so the -stoploss cap cannot bind
    d = _dist(s, "trend_breakout", atr, px)
    assert abs(d * px / atr - 3.5) < 1e-6, (
        "trend_breakout must use the 3.5x multiplier measured on 2026-08-20 "
        "(+0.103%%/trade paired, both halves positive); got %.4fx" % (d * px / atr))


def test_range_on_stays_narrow_because_widening_it_was_measured_worse():
    s = _georgia()
    px, atr = 1000.0, 1.0
    d = _dist(s, "range_on", atr, px)
    assert abs(d * px / atr - 2.5) < 1e-6, (
        "range_on measured -0.280%%/trade at 3.5x with BOTH halves negative "
        "(t=-2.25) — it must NOT inherit trend_breakout's widening; got %.4fx"
        % (d * px / atr))


def test_the_counter_trend_tags_are_unchanged():
    s = _georgia()
    px, atr = 1000.0, 1.0
    for tag in ("bounce_pullback", "range_meanrev"):
        d = _dist(s, tag, atr, px)
        assert abs(d * px / atr - 3.5) < 1e-6, \
            "%s kept its 2026-07-13 value of 3.5x" % tag


def test_the_carrier_stoploss_still_caps_a_wide_atr():
    """The widening must not be able to push the stop past the config bound —
    that cap is what keeps the change a stop-DISTANCE change and not a risk
    change."""
    s = _georgia()
    px = 100.0
    d = _dist(s, "trend_breakout", atr=50.0, px=px)   # 3.5x50/100 = 175%
    assert abs(d - (-s.stoploss)) < 1e-9, (
        "an enormous ATR must clamp to the carrier stoploss (%r), got %r"
        % (-s.stoploss, d))
