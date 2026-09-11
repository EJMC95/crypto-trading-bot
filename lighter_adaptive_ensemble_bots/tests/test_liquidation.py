"""Liquidation maths and the stop-before-liquidation refusal."""
import pytest

from lighter_bots import liquidation as L


def test_isolated_long_matches_the_closed_form():
    # P_liq = E * (1 - 1/L) / (1 - mmf)
    e, lev, mmf = 100.0, 10.0, 0.012
    want = e * (1 - 1 / lev) / (1 - mmf)
    got = L.isolated_liquidation(e, lev, mmf, "long", fee_buffer_frac=0.0)
    assert got == pytest.approx(want)


def test_isolated_short_matches_the_closed_form():
    e, lev, mmf = 100.0, 10.0, 0.012
    want = e * (1 + 1 / lev) / (1 + mmf)
    got = L.isolated_liquidation(e, lev, mmf, "short", fee_buffer_frac=0.0)
    assert got == pytest.approx(want)


def test_liquidation_is_further_away_at_lower_leverage():
    a = L.isolated_liquidation(100, 10, 0.012, "long", 0.0)
    b = L.isolated_liquidation(100, 2, 0.012, "long", 0.0)
    assert b < a, "2x must survive a deeper drawdown than 10x"


def test_fee_buffer_moves_liquidation_toward_entry():
    bare = L.isolated_liquidation(100, 10, 0.012, "long", 0.0)
    buffered = L.isolated_liquidation(100, 10, 0.012, "long", 0.005)
    assert buffered > bare, "fees eat margin: liquidation gets CLOSER"


def test_cross_margin_without_account_context_refuses():
    est = L.estimate(entry=100, side="long", leverage=10,
                     maintenance_margin_frac=0.012, margin_mode="cross",
                     quantity=1.0)
    assert est.price is None and not est.reliable
    assert "ACCOUNT property" in est.reason


def test_cross_margin_with_account_context_is_computable():
    est = L.estimate(entry=100, side="long", leverage=10,
                     maintenance_margin_frac=0.012, margin_mode="cross",
                     quantity=1.0, account_equity=50.0,
                     account_maintenance=10.0)
    assert est.reliable and est.price == pytest.approx(100 * (1 - 40 / 100))


def test_unknown_maintenance_margin_refuses():
    est = L.estimate(entry=100, side="long", leverage=10,
                     maintenance_margin_frac=None, margin_mode="isolated",
                     quantity=1.0)
    assert not est.reliable and est.price is None


def test_stop_beyond_liquidation_is_refused():
    est = L.estimate(entry=100, side="long", leverage=10,
                     maintenance_margin_frac=0.012, margin_mode="isolated",
                     quantity=1.0)
    ok, why, _gap = L.stop_is_safe(entry=100, stop=est.price - 1.0,
                                   side="long", atr=1.0, liq=est,
                                   min_atr_buffer=2.0)
    assert not ok and "BEYOND liquidation" in why


def test_stop_too_close_to_liquidation_is_refused():
    est = L.estimate(entry=100, side="long", leverage=10,
                     maintenance_margin_frac=0.012, margin_mode="isolated",
                     quantity=1.0)
    ok, why, gap = L.stop_is_safe(entry=100, stop=est.price + 0.5, side="long",
                                  atr=1.0, liq=est, min_atr_buffer=2.0)
    assert not ok and gap == pytest.approx(0.5) and "ATR minimum" in why


def test_an_unreliable_estimate_never_passes():
    bad = L.LiquidationEstimate(None, "unknown", "cross", reliable=False)
    ok, why, _ = L.stop_is_safe(entry=100, stop=90, side="long", atr=1.0,
                                liq=bad, min_atr_buffer=2.0)
    assert not ok and "not reliably computable" in why


def test_max_safe_leverage_walks_down_for_a_wide_stop():
    tight = L.max_safe_leverage(entry=100, stop=99, side="long", atr=1.0,
                                mmf=0.012, min_atr_buffer=2.0, cap=10.0)
    wide = L.max_safe_leverage(entry=100, stop=91, side="long", atr=1.0,
                               mmf=0.012, min_atr_buffer=2.0, cap=10.0)
    assert tight == 10.0
    assert 0.0 < wide < tight, "a wider stop must force leverage DOWN"


def test_max_safe_leverage_returns_zero_when_nothing_works():
    """A refusal, never a silent 1x fallback.

    The condition has to be unachievable at EVERY leverage, and a wide stop
    alone is not: at 1.75x on a $100 entry liquidation sits near $43, so a
    $50 stop clears it comfortably. What cannot be satisfied is a buffer
    expressed in an ATR larger than the whole distance to zero -- here ATR 50
    demands 100 points of clearance and even 1x liquidation (0.0) leaves 99."""
    got = L.max_safe_leverage(entry=100, stop=99, side="long", atr=50.0,
                              mmf=0.012, min_atr_buffer=2.0, cap=10.0)
    assert got == 0.0

    # ...and the control: the same call with a workable ATR does NOT refuse,
    # so the test above is failing for the right reason.
    assert L.max_safe_leverage(entry=100, stop=99, side="long", atr=1.0,
                               mmf=0.012, min_atr_buffer=2.0, cap=10.0) > 0


def test_short_side_is_not_a_sign_flipped_long():
    est_l = L.estimate(entry=100, side="long", leverage=10,
                       maintenance_margin_frac=0.012,
                       margin_mode="isolated", quantity=1.0)
    est_s = L.estimate(entry=100, side="short", leverage=10,
                       maintenance_margin_frac=0.012,
                       margin_mode="isolated", quantity=1.0)
    assert est_l.price < 100 < est_s.price
    # The distances are NOT equal: (1-1/L)/(1-m) vs (1+1/L)/(1+m).
    assert est_l.distance_frac != pytest.approx(est_s.distance_frac, abs=1e-6)
