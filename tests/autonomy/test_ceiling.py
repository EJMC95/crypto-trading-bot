"""[(sm)] The fleet measured six floors and no ceiling.

**Operator: "The discussion of the floor is too often had, where the
conversation of how high the ceiling goes is of little discussion... they know
the floor all too well."**

Every bar this fleet owns asks *don't be bad*. Measured 2026-08-20, slot
occupancy against each book's own cap beside its own mean per trade:

    👩 mum           +4.658%/trade   100% of a cap of FOUR
    🙏 avo           +1.085%          40%
    🌾 carry         +0.254%          49%
    🔮 georgia       +0.122%           9%   <- closest book to the gate
    ⚖️ counterweight -1.433%         102%   <- worst book, FULL
    🛢️ garrett       -1.460%          88%

Capital in inverse proportion to measured edge. The instrument that shows it
did not exist.

WHAT THESE TESTS PIN is not the arithmetic — it is the DISCIPLINE that keeps a
ceiling from becoming a licence: a losing book never gets one, the lower bound
and not the mean is what gets scaled, rate headroom never comes from holding
less, and the drawdown bar binds the clip.
"""
import pytest

pytestmark = pytest.mark.autonomy

import scripts.ceiling as C      # noqa: E402

#: A proven edge WITH REAL VARIANCE. The first version of this fixture was
#: `[0.02] * 40` — zero variance, so `se` is 0 and the lower bound EQUALS the
#: mean. A mutation swapping one for the other survived, because the fixture
#: could not tell them apart: the (po) inspects-nothing failure, in the test
#: written to pin I16's whole point.
GOOD = [0.04, 0.00] * 20        # mean 2.00%, lower bound 1.59% — distinct


def test_a_losing_book_is_never_given_a_ceiling():
    """THE load-bearing one. An instrument that answers "how high?" for a book
    that is going down would be the most dangerous thing in the tree."""
    r = C.book_ceiling(closes=[-0.01] * 40, span_days=40, concurrency=1.0,
                       cap=10, clip=80.0, equity=1000.0)
    assert r["verdict"] == "UNPROVEN"
    assert "ceiling_usd_per_day" not in r
    assert "keep-or-retire" in r["binding"]


def test_a_lucky_small_sample_is_not_a_ceiling_either():
    """I16: ranking on the MEAN rewards small samples that got lucky. The
    lower bound is what may be scaled, and here it is exactly zero."""
    lucky = [0.05, -0.04, 0.06, -0.03, 0.07, -0.05, 0.08, -0.06, 0.09]
    r = C.book_ceiling(closes=lucky, span_days=9, concurrency=1.0, cap=4,
                       clip=80.0, equity=1000.0)
    assert r["mean_pct"] > 0, r
    assert r["lower_bound_pct"] == 0.0 and r["verdict"] == "UNPROVEN", r
    assert "ceiling_usd_per_day" not in r


def test_the_ceiling_scales_the_LOWER_BOUND_not_the_mean():
    r = C.book_ceiling(closes=GOOD, span_days=40, concurrency=1.0, cap=4,
                       clip=80.0, equity=1000.0, maxdd=0.03)
    assert r["lower_bound_pct"] < r["mean_pct"], (
        "the fixture has no variance, so this test cannot tell the two apart")
    # computed from the UNROUNDED edge, not from the payload's own rounded
    # field — chaining two 4dp roundings and then demanding exactness is a
    # test about float formatting, not about which statistic is scaled
    _mean, _se, lb = C.edge(GOOD)
    rate = len(GOOD) / 40.0
    assert r["usd_per_day_lower_bound"] == pytest.approx(rate * 80.0 * lb,
                                                         abs=1e-4)
    # …and the distinction is MATERIAL, not a rounding artifact: scaling the
    # mean instead would overstate this book by a fifth
    assert rate * 80.0 * _mean > 1.2 * (rate * 80.0 * lb)


def test_rate_headroom_comes_from_SLOTS_never_from_holding_less():
    """(hl) measured that every 'more trades' candidate was denominator
    shrinkage. Two books with the same slots and wildly different holds must
    get the SAME rate headroom, or this instrument recommends churn."""
    slow = C.book_ceiling(closes=GOOD, span_days=40, concurrency=2.0, cap=4,
                          clip=80.0, equity=1000.0, maxdd=0.03)
    fast = C.book_ceiling(closes=[0.02] * 400, span_days=40, concurrency=2.0,
                          cap=4, clip=80.0, equity=1000.0, maxdd=0.03)
    assert slow["rate_headroom_x"] == fast["rate_headroom_x"] == 2.0
    assert fast["closes_per_day"] > 5 * slow["closes_per_day"]


def test_the_drawdown_bar_binds_the_clip():
    """%-drawdown scales with clip against a fixed book, so a book already at
    the 15% bar has NO size room however good its edge."""
    at_bar = C.book_ceiling(closes=GOOD, span_days=40, concurrency=4.0, cap=4,
                            clip=80.0, equity=1000.0, maxdd=C.MAXDD_BAR)
    assert at_bar["size_headroom_x"] == 1.0
    assert at_bar["headroom_x"] == 1.0
    assert "AT ITS CEILING" in at_bar["binding"]
    roomy = C.book_ceiling(closes=GOOD, span_days=40, concurrency=4.0, cap=4,
                           clip=80.0, equity=1000.0, maxdd=0.05)
    assert roomy["size_headroom_x"] == 3.0


def test_measured_depth_can_bind_before_the_drawdown_bar():
    r = C.book_ceiling(closes=GOOD, span_days=40, concurrency=4.0, cap=4,
                       clip=80.0, equity=1000.0, maxdd=0.03, depth_clip=120.0)
    assert r["size_headroom_x"] == 1.5 and r["size_bound_by"] == "measured depth"


def test_an_unproven_book_is_priced_in_DECIDABILITY_not_dollars():
    """Where I17 and the ceiling meet: the only ceiling an unproven book has is
    how fast it can learn what it is."""
    r = C.book_ceiling(closes=[0.01, -0.008] * 12, span_days=24,
                       concurrency=1.0, cap=5, clip=50.0, equity=1000.0)
    assert r["verdict"] == "UNPROVEN" and r["closes_to_t2"] > 0
    assert r["days_to_t2_at_full_slots"] < r["days_to_t2_now"]
    assert "DECIDABILITY" in r["binding"]


def test_the_reachability_caveat_is_stated_not_implied():
    """A ceiling says a book COULD run N times faster if its slots filled — not
    that the signal exists to fill them. Overstating that is the (gl) class,
    and the operator learns to ignore an instrument that does it."""
    r = C.book_ceiling(closes=[0.01, -0.008] * 12, span_days=24,
                       concurrency=1.0, cap=5, clip=50.0, equity=1000.0)
    assert "supply" in r["binding"] and "census" in r["binding"], r["binding"]
    p = C.book_ceiling(closes=GOOD, span_days=40, concurrency=0.5, cap=10,
                       clip=80.0, equity=1000.0, maxdd=0.10)
    assert "supply allows" in p["binding"], p["binding"]


def test_a_thin_book_gets_no_number_at_all():
    r = C.book_ceiling(closes=[0.01] * 4, span_days=4, concurrency=1.0, cap=4,
                       clip=80.0, equity=1000.0)
    assert r["verdict"] == "TOO-THIN" and "ceiling_usd_per_day" not in r
    assert C.MIN_N >= 8, "the thinness floor is what stops a 4-trade ceiling"


def test_the_binding_factor_is_the_LARGEST_headroom_and_the_rest_are_ranked():
    """The output has to be a plan, not a number: name the single change that
    buys most, then the runners-up."""
    r = C.book_ceiling(closes=GOOD, span_days=40, concurrency=1.0, cap=4,
                       clip=80.0, equity=1000.0, maxdd=0.03)
    assert "CLIP" in r["binding"] and any("SLOTS" in t for t in r["then"])


def test_the_ceiling_prices_the_graders_sample_not_the_raw_feed():
    """[2026-09-02] The public /trades.json feed carries rows the fleet's
    grader withholds — LEDGER_QUARANTINE rows and phantom halt events. A
    ceiling priced on them is a ceiling on trades the gate refuses. Pinned
    against the owners: a quarantined row and a phantom row are dropped, a
    real one kept. Mutation: remove either filter in `graded_sample` and the
    corresponding assertion reddens."""
    import bot_pnl_store as store
    q_pair, q_bot, lo, _hi, _why = store.LEDGER_QUARANTINE[0]
    bot = f"{q_bot}-ceiling-test"
    rows = [
        {"bot": bot, "pair": q_pair, "pnl_pct": 0.01, "pnl_abs": 1.0,
         "opened_at": f"{lo}T01:00:00+00:00", "closed_at": f"{lo}T02:00:00+00:00",
         "reason": "long_x", "entry_price": 1.0},                      # quarantined
        {"bot": bot, "pair": "ETH", "pnl_pct": 0.0, "pnl_abs": 0.0,
         "opened_at": "2026-08-21T01:00:00+00:00",
         "closed_at": "2026-08-21T02:00:00+00:00", "reason": "x"},    # phantom
        {"bot": bot, "pair": "ETH", "pnl_pct": 0.02, "pnl_abs": 2.0,
         "opened_at": "2026-08-22T01:00:00+00:00",
         "closed_at": "2026-08-22T02:00:00+00:00", "reason": "long_x",
         "entry_price": 1.0},                                          # real
    ]
    kept = C.graded_sample(rows, bot)
    assert len(kept) == 1 and kept[0]["pair"] == "ETH" and kept[0]["pnl_abs"] == 2.0
