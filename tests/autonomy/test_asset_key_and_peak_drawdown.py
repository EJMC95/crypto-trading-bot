"""[2026-09-07] Two measured defects, both of which err in the REASSURING
direction, and the guards that keep them closed.

1. `edge_audit` keyed every asset on the raw `pair` string. This venue spells
   one market three ways (`ADA`, `ADA/USD`, `ADA/USDC`), so `coholding()` —
   which INTERSECTS those strings across books — reported a perfect 0.000 for
   any pair of books that spelled a shared coin differently. Measured on the
   live ledger: 194 raw keys for 131 real assets, 24 of 88 book pairs reading
   a false zero, and same-coin book-pair hours understated by 34.7%. The
   instrument built to detect "one bet held three times" could not see it.

2. `golive_readiness.mtm_drawdown` divides every book's drawdown by
   `BOOK_USD` ($1,000). That is right for a $1,000 paper book and wrong for a
   LIVE book holding real money below it — 🙏 avo read 5.57% against a true
   13.36% peak-relative, 👩 mum 6.43% against 11.05%, both against a 15% bar.

Both fixes are REPORTING fixes: `grade()` is byte-unchanged and no actuator
reads either number. `fleet_risk`, the live organ, already normalised symbols
at every harvest site, so no veto ever acted on the understated co-holding.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (ROOT, os.path.join(ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import edge_audit as ea            # noqa: E402
import golive_readiness as gr      # noqa: E402


# ------------------------------------------------------------------ 1. keys
@pytest.mark.parametrize("raw,want", [
    ("ADA", "ADA"),
    ("ADA/USD", "ADA"),
    ("ADA/USDC", "ADA"),
    ("ADA/USDC:USDC", "ADA"),
    ("SKHYNIXUSD/USD", "SKHYNIXUSD"),
    ("1000PEPE/USDC", "1000PEPE"),
    # A settlement suffix with NO quote leg. Not a shape this venue emits
    # today, which is exactly why it is pinned: the `:` split is otherwise an
    # untested branch, and a mutation round proved the rest of the suite
    # cannot tell whether it is there.
    ("ADA:USDC", "ADA"),
])
def test_the_venues_three_spellings_of_one_market_collapse_to_one_asset(raw, want):
    assert ea.base_symbol(raw) == want


@pytest.mark.parametrize("raw", ["", None, "/", "/USDC"])
def test_an_unreadable_pair_degrades_to_itself_never_to_another_asset(raw):
    """I8: unknown degrades to the honest identifier, never to a guess. What
    it must NOT do is return a shared value like '' for several different
    unreadable keys AND then merge them with a real asset."""
    got = ea.base_symbol(raw)
    assert got == str(raw or "").split(":")[0].split("/")[0] or got == str(raw or "")
    assert got != "ADA"


def _row(pct, abs_usd, closed, opened, pair, reason="long_tp"):
    return (pct, abs_usd, closed, opened.isoformat(), {}, reason, pair,
            {"reason": reason, "pair": pair})


T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _book(pair, hours=6):
    """One book holding `pair` for `hours` from T0."""
    return {"rows": [_row(0.01, 1.0, T0 + timedelta(hours=hours),
                          T0, pair)]}


def test_two_books_holding_one_coin_under_different_spellings_are_seen_as_co_holding():
    """THE INCIDENT, reduced. Before the fix this pair reported 0.000."""
    shaped = {"a": _book("ADA"), "b": _book("ADA/USDC")}
    out = ea.coholding(shaped, ["a", "b"], step_s=600)
    assert out["max_stack"]["books"] == 2, out["max_stack"]
    assert out["max_stack"]["coin_side"].startswith("ADA/"), out["max_stack"]


def test_two_books_holding_genuinely_different_coins_still_do_not_co_hold():
    """The counterfactual that stops the fix from flagging everything — a
    normaliser that collapsed too far would make every pair look concentrated,
    which is the same defect mirrored."""
    shaped = {"a": _book("ADA"), "b": _book("SOL/USDC")}
    out = ea.coholding(shaped, ["a", "b"], step_s=600)
    assert out["max_stack"]["books"] == 1, out["max_stack"]


def test_co_holding_requires_the_same_SIDE_not_merely_the_same_coin():
    """One book long ADA and another short ADA is a hedge, not a doubled bet."""
    long_b = {"rows": [_row(0.01, 1.0, T0 + timedelta(hours=6), T0, "ADA",
                            "long_tp")]}
    short_b = {"rows": [_row(0.01, 1.0, T0 + timedelta(hours=6), T0,
                             "ADA/USDC", "short_tp")]}
    out = ea.coholding({"a": long_b, "b": short_b}, ["a", "b"], step_s=600)
    assert out["max_stack"]["books"] == 1, out["max_stack"]


def test_concentration_counts_one_asset_once_across_its_spellings():
    rows = [_row(0.01, 10.0, T0 + timedelta(hours=1), T0, "UNI"),
            _row(0.01, 20.0, T0 + timedelta(hours=2), T0, "UNI/USDC"),
            _row(0.01, 1.0, T0 + timedelta(hours=3), T0, "SOL")]
    c = ea.concentration(rows)
    assert c["n_coins"] == 2, c["n_coins"]
    assert c["top_coin"] == "UNI"
    assert c["top_coin_n"] == 2
    assert c["top_coin_share_of_net"] == pytest.approx(30.0 / 31.0)


def test_the_breakdown_coin_slice_uses_the_same_owner():
    rows = [_row(0.01, 10.0, T0 + timedelta(hours=1), T0, "UNI"),
            _row(0.02, 20.0, T0 + timedelta(hours=2), T0, "UNI/USDC")]
    b = ea.breakdowns(rows)
    assert set(b["coin"]) == {"UNI"}, b["coin"]
    assert b["coin"]["UNI"]["n"] == 2


def test_coholding_and_concentration_share_one_owner_no_second_copy():
    """(hj): a second copy of a rule is a second rule. Both call sites must
    route through `base_symbol` — a hand-rolled `.split('/')` in either would
    drift the day the venue adds a fourth spelling."""
    import inspect
    for fn in (ea.coholding, ea.concentration, ea.breakdowns):
        src = inspect.getsource(fn)
        assert "base_symbol(" in src, f"{fn.__name__} does not use the owner"
        assert 'str(q[6])' not in src, f"{fn.__name__} still keys on the raw pair"


# -------------------------------------------------- 2. peak-relative drawdown
def _series(equities, start=T0):
    return [(start + timedelta(hours=i), e) for i, e in enumerate(equities)]


def test_peak_relative_drawdown_is_published_beside_the_book_usd_one():
    """A live book that peaks at $500 and troughs at $400 has lost 20% of its
    own money, and 10% of a $1,000 book it never had."""
    md = gr.mtm_drawdown(_series([450.0, 500.0, 400.0, 420.0]))
    assert md["peak_equity"] == 500.0
    assert md["max_dd_usd"] == pytest.approx(-100.0)
    assert md["max_dd_frac"] == pytest.approx(0.10)        # the $1,000 basis
    assert md["max_dd_frac_peak"] == pytest.approx(0.20)   # the honest one


def test_a_thousand_dollar_paper_book_reads_essentially_the_same_either_way():
    """The 12 shadow books must not move — if they did, this would be a
    re-spec of every existing verdict rather than a correction for live rows."""
    md = gr.mtm_drawdown(_series([1000.0, 1010.0, 960.0]))
    assert md["max_dd_frac"] == pytest.approx(0.05)
    assert md["max_dd_frac_peak"] == pytest.approx(50.0 / 1010.0, rel=1e-9)
    assert abs(md["max_dd_frac_peak"] - md["max_dd_frac"]) < 0.005


def test_it_is_not_uniformly_stricter_a_book_that_grew_reads_lower():
    """🪁 kelly's real case: equity peaked above $1,000, so the peak-relative
    number is SMALLER. Stated so nobody sells this as a tightening."""
    md = gr.mtm_drawdown(_series([1000.0, 1200.0, 900.0]))
    assert md["max_dd_frac"] == pytest.approx(0.30)
    assert md["max_dd_frac_peak"] == pytest.approx(0.25)
    assert md["max_dd_frac_peak"] < md["max_dd_frac"]


def test_a_non_positive_peak_is_None_never_zero():
    """I8 again: 0.0 reads as 'no drawdown', which is the one answer a broken
    series must never give on a safety number."""
    md = gr.mtm_drawdown([(T0, 0.0), (T0 + timedelta(hours=1), 0.0)])
    assert md is not None
    assert md["max_dd_frac_peak"] is None


def test_the_grade_is_byte_unchanged_by_the_new_field():
    """The whole safety of this change: `grade()` must not read it. If a future
    edit makes the peak fraction blocking, this reddens — and making it
    blocking is a gate re-spec, i.e. an operator act."""
    import inspect
    src = inspect.getsource(gr.grade)
    assert "max_dd_frac_peak" not in src
    assert "GOLIVE_MAX_DD" in src or "max_dd_frac" in src


def test_apply_mtm_decides_on_the_peak_relative_fraction():
    """RE-AIMED at (yz), not deleted — and the reason is recorded here.

    This was `test_apply_mtm_still_decides_on_the_book_usd_fraction`, and it
    was CORRECT when (yr) wrote it: the peak fraction shipped as REPORTED, the
    re-spec was Eamon's to make, and this pin is what stopped a later session
    quietly making it blocking. He made it on 7-Sep — *"Fix the drawdown
    denominator"* — so the pin now guards the opposite direction.

    Its stated worry was that swapping the fraction "would silently re-verdict
    every live book". That was the right question and it is ANSWERED WITH A
    MEASUREMENT rather than waived: on the live payload, all 14 graded books,
    the change produced **zero verdict flips**, and `fleet_bus.dd_scale` — the
    real-money sizing rail reading this number — moved on no live book. I26:
    a pin is a snapshot, not a property; when it blocks a change the question
    is whether the change is right, never whether the pin exists.

    Driven through the function rather than grepped out of its source: the old
    form asserted a SUBSTRING was absent, which is (po)'s "a page-wide
    substring scan is not a structural claim" — it would have passed against a
    correct implementation that spelled the field differently, and failed
    against a comment that merely mentioned it.
    """
    stats_like = {"n": 40, "days": 40.0, "mean_pct": 0.5, "t": 3.0,
                  "h1": 1.0, "h2": 1.0,
                  "max_dd_frac": 0.0708, "max_dd_usd": -70.80}
    mtm = {"n": 3761, "days": 13.0, "max_dd_frac": 0.0643,
           "max_dd_frac_peak": 0.1104, "peak_equity": 581.96}

    got = gr.apply_mtm(stats_like, mtm)

    # 👩 mum's real shape: $70.80 of hole on a book that peaked at $581.96.
    assert got["maxdd_denom"] == "peak_equity"
    assert got["max_dd_frac"] == pytest.approx(70.80 / 581.96, rel=1e-4), (
        "the graded fraction is not the book's own peak-relative drawdown")
    assert got["max_dd_frac"] > mtm["max_dd_frac_peak"], (
        "the REALISED half must be able to decide too — rebasing only the MTM "
        "half leaves a $1,000-denominated number able to win the max()")

    # The superseded reading is kept, not hidden (I12).
    assert got["max_dd_frac_book"] == pytest.approx(0.0708)

    # ONE denominator, never a mix: without the dollar figure NEITHER half
    # moves, and the realised hole must still be able to fail the bar.
    no_dollars = {k: v for k, v in stats_like.items() if k != "max_dd_usd"}
    no_dollars["max_dd_frac"] = 0.40
    kept = gr.apply_mtm(no_dollars, mtm)
    assert kept["maxdd_denom"] == "book_usd"
    assert kept["max_dd_frac"] == pytest.approx(0.40), (
        "the realised half was dropped when it could not be rebased — a "
        "silent loosening of the bar that governs real money")


def test_the_peak_denominator_is_not_uniformly_stricter():
    """🎫 the taker's shape, and the fleet's first-ever READY: a book whose
    equity peaked ABOVE $1,000 reads LOWER, because the denominator grew.
    Pinned so nobody re-sells this change as a one-way tightening."""
    got = gr.apply_mtm(
        {"n": 187, "days": 37.8, "mean_pct": 1.17, "t": 2.6, "h1": 1.0,
         "h2": 1.0, "max_dd_frac": 0.0231, "max_dd_usd": -23.10},
        {"n": 3000, "days": 30.0, "max_dd_frac": 0.0542,
         "max_dd_frac_peak": 0.0458, "peak_equity": 1185.20})
    assert got["max_dd_frac"] == pytest.approx(0.0458)
    assert got["max_dd_frac"] < got["max_dd_frac_book"]
    assert gr.bar_map(got)["maxdd"] is True
