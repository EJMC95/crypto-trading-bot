"""The maxDD bar's numerator and denominator must be the same object.

INCIDENT (2026-09-11 (aau)). `mtm_drawdown` finds the max dollar hole against
a RUNNING peak and then divides it by the GLOBAL peak. On a series that later
exceeds the peak the hole opened at — every book that took a DEPOSIT — that
understates, and `apply_mtm` makes the field THE BAR while `fleet_bus.dd_scale`
reads it to size live clips. Measured across all 35 live equity series the day
this shipped, the two readings differ on FIVE books and materially on exactly
the two real-money arms, which are the only two that ever took a deposit:

    freqtrade-avo-maria-lighter   12.32%  ->  24.09%
    freqtrade-mum-lighter          9.90%  ->  13.05%
    lighter-ticket-taker-lshadow   4.77%  ->   4.88%   (max-% vs max-$ episode)
    perps-funding-carry-lshadow    1.75%  ->   1.81%
    equities-regime-lshadow        0.36%  ->   0.36%

THE FLEET ALREADY HAD THE RIGHT IMPLEMENTATION AND IT WAS NOT THE ONE HOLDING
THE GUN: `pnl_dashboard._max_drawdown_pct` walks `min(dd, v/peak - 1.0)` — a
running peak on both sides — and has since the 15-Jul salvage. This is the
"a second copy of a rule is a second rule" failure with the wrong copy
governing real money.

REPORTED, NEVER A BAR — this commit deliberately moves no verdict and no
dollar. Switching onto it fails BOTH live books at the 15% bar and cuts their
clip through `dd_scale`, and avo's reading is additionally confounded by
$66.40 of attested operator manual trades sitting in her equity series. That
is an operator decision taken on a published readback, not a side effect of a
correctness fix, so `test_the_bar_is_byte_unchanged` pins that here.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import golive_readiness as g                          # noqa: E402


def _sample():
    """A REAL sample, built by the publisher (`stats`) rather than hand-rolled.

    The first cut of this file hand-wrote the dict and chased KeyErrors one
    field at a time — `days`, then `win_rate` — which is exactly the
    fixture-that-encodes-the-assumption trap. `stats` owns this shape; ask it.
    """
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    rows = [((0.6 if i % 3 else -0.4), (3.0 if i % 3 else -2.0),
             t0 + timedelta(hours=12 * i))
            for i in range(40)]
    return g.stats(rows, book_usd=1000.0)


def _series(vals, start=None):
    t0 = start or datetime(2026, 9, 1, tzinfo=timezone.utc)
    return [(t0 + timedelta(minutes=5 * i), float(v))
            for i, v in enumerate(vals)]


def test_a_deposit_after_the_trough_understates_the_shipped_reading():
    """avo's shape, minimised: fall 100 -> 75, then a deposit lifts the series
    above its old peak. The hole is 25% of the peak it opened at and 12.5% of
    the peak the deposit created."""
    m = g.mtm_drawdown(_series([100, 90, 75, 200, 200]))
    assert m["max_dd_frac_runpeak"] == pytest.approx(0.25)
    assert m["max_dd_frac_peak"] == pytest.approx(0.125)
    assert m["runpeak_denom_usd"] == pytest.approx(100.0)


# A MUTATION THAT SURVIVES BY PROOF, RECORDED SO IT IS NOT CHASED. Replacing
# the stored `_r` with `abs(dd) / peak` inside the update is a NO-OP, not a
# test gap: `peak` is monotone non-decreasing, so if an earlier hole were
# larger in DOLLARS its RATIO would be larger too (same or smaller peak) and
# the update would not be firing here. Verified over 200,000 random series —
# zero counterexamples. The distinction the test below pins is the real one:
# the max-of-ratio vs the SHIPPED `max_dd_frac_peak`, which divides by the
# GLOBAL peak and is a genuinely different number.
def test_it_is_the_max_of_the_RATIO_not_the_ratio_of_the_max_dollar_hole():
    """The two pick DIFFERENT EPISODES, and the fleet has a live instance —
    🎫 the taker's shadow reads 4.879% (max-%) vs 4.769% (max-$), in the
    WORSE direction, on its first-ever READY book. A small early hole on a
    small peak can beat a larger later hole on a larger peak.
    """
    # 100 -> 50 is 50% on a peak of 100; 1000 -> 600 is a BIGGER dollar hole
    # (400 vs 50) but only 40%.
    m = g.mtm_drawdown(_series([100, 50, 1000, 600]))
    assert m["max_dd_usd"] == pytest.approx(-400.0)     # the max-$ episode
    assert m["max_dd_frac_runpeak"] == pytest.approx(0.50)   # the max-% one
    assert m["runpeak_denom_usd"] == pytest.approx(100.0)


def test_a_monotone_series_agrees_with_the_shipped_reading():
    """No capital move and no new high after the hole => the two conventions
    are the same number. This is why 30 of 35 books do not move."""
    m = g.mtm_drawdown(_series([100, 120, 90, 100, 110]))
    assert m["max_dd_frac_runpeak"] == pytest.approx(m["max_dd_frac_peak"])


def test_no_positive_peak_degrades_to_None_never_to_zero():
    """I8 — unknown degrades to unknown. A fabricated 0.0 drawdown on a
    levered row is the flattering direction."""
    m = g.mtm_drawdown(_series([-5.0, -6.0]))
    assert m["max_dd_frac_runpeak"] is None
    assert m["runpeak_at"] is None


def test_the_bar_is_byte_unchanged_by_this_commit():
    """`apply_mtm` must still decide on `max_dd_frac_peak`. If a future pass
    switches the bar it does so deliberately, not by editing `mtm_drawdown`."""
    m = g.mtm_drawdown(_series([100, 90, 75, 200, 200]))
    out = g.apply_mtm(_sample(), m, min_samples=1, min_days=0)
    assert out["maxdd_denom"] == "peak_equity"
    assert out["max_dd_frac"] == pytest.approx(m["max_dd_frac_peak"])
    assert out["max_dd_frac"] != pytest.approx(m["max_dd_frac_runpeak"])


def test_the_field_actually_reaches_a_reader():
    """`book_payload` rebuilds a hand-picked whitelist rather than serialising
    `mtm`, so a field added to `mtm_drawdown` alone is BORN DARK in the
    payload — the defect this test exists to keep closed."""
    m = g.mtm_drawdown(_series([100, 90, 75, 200, 200]))
    s = g.apply_mtm(_sample(), m, min_samples=1, min_days=0)
    pay = g.book_payload(s)
    assert pay["mtm"]["max_dd_pct_runpeak"] == pytest.approx(25.0)
    assert pay["mtm"]["runpeak_denom_usd"] == pytest.approx(100.0)
