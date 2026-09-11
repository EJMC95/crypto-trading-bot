"""A book's drawdown must be the BOOK'S, not the sub-account's.

INCIDENT (2026-09-11 (abe)). Eamon: *"cant you find that out?"* — about the
$66.40 of his own manual fills sitting inside 🙏 avo's equity series, which
`(aaw)` could date only as "somewhere before 25-Aug". They were dated, and the
answer moved a real-money verdict.

HOW THEY WERE DATED, three independent lines agreeing to 33 cents:
  1. the SHADOW TWIN (same strategy, no manual interference) moved
     -0.00% / +0.05% / -0.07% on 22/23/24-Aug while the live arm lost
     -1.92% / -9.12% / -10.88% of book — excess -$66.73 vs an attested -$66.40;
  2. `venue_orders`, which records every order the BOT places, holds ZERO bot
     orders in either loss window while $62 left the account;
  3. the operator's own attestation total.

WHAT IT CHANGED. avo's drawdown is not 12.32% (the published figure, which is
close to right BY COINCIDENCE — a global-peak denominator understating while
the manual trades overstate) and not 24.09% (the (aaw) running-peak reading,
which is real money he never traded). It is 14.64%-20.44% depending on an
intraday shape nobody measured, and **the 15% bar is inside that band**. 👩 mum,
whose flows are all instants and carry no shape uncertainty, reads 17.64% —
OVER the bar the gate currently shows her passing at 9.90%.

SO THE BAND IS THE PRODUCT, NOT THE POINT ESTIMATE. Publishing 14.64% alone
would hand a reader a settled-looking number whose verdict flips on an
assumption; `test_a_straddling_band_is_not_a_pass` pins that.

REPORTED, NEVER A BAR. `grade`/`bar_map`/`apply_mtm` are byte-unchanged.
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

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _s(vals, step_min=5):
    return [(T0 + timedelta(minutes=step_min * i), float(v))
            for i, v in enumerate(vals)]


def test_a_deposit_no_longer_erases_the_drawdown_it_lands_in():
    """The whole point. 100 -> 75 is a 25% hole; a deposit that doubles the
    book immediately after must not make it look like a 12.5% one."""
    pts = _s([100, 90, 75, 175, 175])
    dep = [(pts[3][0], pts[3][0], 100.0)]
    assert g._bot_only_dd(pts, dep) == pytest.approx(0.25, abs=1e-6)
    # ...and without the flow declared, the raw series hides it:
    m = g.mtm_drawdown(pts)
    assert m["max_dd_frac_peak"] == pytest.approx(0.25 * 100 / 175, abs=1e-6)


def test_a_return_index_not_a_capital_subtraction():
    """Subtracting contributed capital from equity drives the denominator to
    zero on a deposit-funded book — avo read 121% under that naive fix. A TWR
    index keeps a denominator of 1.0 by construction."""
    pts = _s([10, 10, 1010, 1005])          # $1000 deposit onto a $10 book
    dep = [(pts[2][0], pts[2][0], 1000.0)]
    dd = g._bot_only_dd(pts, dep)
    assert dd < 0.01, dd                     # ~0.5% of the funded book, not 50%


def test_a_misdated_flow_fails_closed_rather_than_lying():
    """A declared instant that lands on the WRONG step leaves the raw jump in
    one step and subtracts it from another. On avo that produced +266% then
    -73% and a fabricated 75.92% drawdown. Unknown must beat wrong (I8)."""
    pts = _s([62.9, 62.9, 230.7, 230.7, 230.7])
    late = [(pts[3][0], pts[3][0], 167.8)]   # one step after the real jump
    assert g._bot_only_dd(pts, late) is None
    ontime = [(pts[2][0], pts[2][0], 167.8)]
    assert g._bot_only_dd(pts, ontime) is not None


def test_the_intraday_shape_changes_the_answer_which_is_why_it_is_banded():
    """On a FALLING series the timing of the removal moves the drawdown
    materially — 8.26% spread evenly vs 12.50% if it all landed at the open.
    (A flat fixture hides this: the first cut of this test used one and both
    shapes returned 0.0, which is the fixture encoding the assumption under
    test rather than exercising it.)"""
    pts = _s([100, 96, 92, 88, 84, 86, 88, 90])
    a, b = pts[1][0], pts[4][0]
    fl = [(a, b, -8.0)]
    assert g._bot_only_dd(pts, fl) == pytest.approx(0.0826, abs=1e-3)
    assert g._bot_only_dd(pts, fl, mode="start") == pytest.approx(0.125, abs=1e-3)
    assert g._bot_only_dd(pts, fl, mode="end") == pytest.approx(0.120, abs=1e-3)


def test_a_flow_dated_before_the_series_is_dropped_not_applied_to_step_one():
    """The difference between "the step CONTAINING the instant" and "the first
    step at or after it". They agree everywhere INSIDE the series; they
    disagree on a flow dated BEFORE it starts, where the naive form subtracts
    a deposit the series never saw — here a -60% first step, which then trips
    the misalignment guard and returns None. The correct behaviour is to DROP
    it, leaving the series' own drawdown untouched.

    (The first cut of this test asserted `is None or ...`, which accepts both
    branches and could not kill the mutation. An assertion with an `or` in it
    is usually a test that has not decided what it believes.)
    """
    pts = _s([100, 90, 80, 85])            # raw running-peak drawdown = 20%
    before = pts[0][0] - timedelta(days=1)
    assert g._bot_only_dd(pts, [(before, before, 50.0)]) == \
        pytest.approx(0.20, abs=1e-6)


def test_the_band_reports_the_WORST_shape_not_the_friendliest():
    """`_hi` must be the max across shapes. Taking the min would publish a
    band that always passes — the failure that makes a band decorative.

    ASSERTED THROUGH `mtm_drawdown`, not against `_botonly_band` directly: the
    first cut called the helper, so it exercised the function and never the
    CALL SITE, and a mutation that swapped `max` for `min` in the payload
    survived it untouched.
    """
    pts = _s([100, 96, 92, 88, 84, 86, 88, 90])
    a, b = pts[1][0], pts[4][0]
    fl = [(a, b, -8.0)]
    shapes = [g._bot_only_dd(pts, fl, mode=m)
              for m in ("spread", "start", "end")]
    assert max(shapes) - min(shapes) > 0.03      # the fixture has teeth
    m = g.mtm_drawdown(pts, flows=fl)
    assert m["max_dd_frac_botonly_hi"] == pytest.approx(max(shapes), abs=1e-9)
    assert m["max_dd_frac_botonly_lo"] == pytest.approx(min(shapes), abs=1e-9)
    assert m["max_dd_frac_botonly_hi"] > m["max_dd_frac_botonly_lo"]


def test_a_straddling_band_is_not_a_pass():
    """The property the incident turns on: when the band crosses the bar the
    honest reading is UNDECIDED, so `_hi` must be published and must be the
    worst shape — not quietly dropped in favour of the friendly point."""
    pts = _s([100, 96, 92, 88, 84, 86, 88, 90])
    a, b = pts[1][0], pts[4][0]
    flows = [(a, b, -8.0)]
    lo = g._botonly_band(pts, flows, min)
    hi = g._botonly_band(pts, flows, max)
    point = g._bot_only_dd(pts, flows)
    assert lo is not None and hi is not None
    assert lo <= point <= hi
    assert hi >= lo


def test_a_book_with_no_declared_flow_publishes_nothing():
    """Not a duplicate of `max_dd_frac_runpeak` under a name promising more —
    33 of 35 live books have no flow and must read None."""
    m = g.mtm_drawdown(_s([100, 90, 75, 80]))
    assert m["max_dd_frac_botonly"] is None
    assert m["max_dd_frac_botonly_lo"] is None
    assert m["botonly_flows_usd"] is None


def test_junk_in_the_declaration_is_dropped_never_guessed():
    bad = {"x": [{"from": "nonsense", "to": "nonsense", "usd": 1.0, "why": ""},
                 {"from": "2026-09-01T00:00:00+00:00", "usd": 1.0},
                 {"from": "2026-09-02T00:00:00+00:00",
                  "to": "2026-09-01T00:00:00+00:00", "usd": 1.0, "why": ""},
                 {"from": "2026-09-01T00:00:00+00:00",
                  "to": "2026-09-01T00:00:00+00:00", "usd": float("nan"),
                  "why": ""}]}
    real = g.NON_BOT_FLOWS
    try:
        g.NON_BOT_FLOWS = bad
        assert g._flows_for("x") == []
    finally:
        g.NON_BOT_FLOWS = real


def test_the_declared_flows_reconcile_to_what_the_books_publish():
    """The table is an attestation; it must agree with the rows' own
    `capital_adjust` / `manual_pnl_usd`, or it is a third number nobody can
    reconcile. avo: 167.77 + 150.00 deposits = 317.77 (row 317.76) and
    -66.73 of manual (attested -66.40). mum: 220.42 + 265.44 = 485.86 exactly,
    and no manual at all."""
    avo = g._flows_for("freqtrade-avo-maria-lighter")
    dep = sum(u for _, _, u in avo if u > 0)
    man = sum(u for _, _, u in avo if u < 0)
    assert dep == pytest.approx(317.77, abs=0.02)
    assert man == pytest.approx(-66.40, abs=0.40)
    mum = g._flows_for("freqtrade-mum-lighter")
    assert sum(u for _, _, u in mum) == pytest.approx(485.86, abs=0.01)
    assert all(u > 0 for _, _, u in mum)     # no manual trading on her account
