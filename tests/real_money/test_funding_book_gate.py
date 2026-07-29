"""Tier 1 — the LIVE Funding Farmer's orderbook gate: `book_metrics` + `vwap_slip`.

MEASURED COVERAGE, 2026-07-29: across the ENTIRE suite,
`lighter_funding_bot.book_metrics` executed **only its `def` line**, and the
inner `vwap_slip` executed **not at all**. The bot's own `--selftest`
monkeypatches `book_metrics` with a canned dict (`lighter_funding_bot.py:3114`)
— sensible for testing the scan's ranking, but it means the real function has
never run under any test. This is stage C of `scan_candidates`, the last gate
before a REAL-MONEY order, and it is the only place in the entry path that
reads the book.

WHY THAT IS THE WORST PLACE FOR A COVERAGE HOLE. Every failure here is silent
and expensive:

  * **The defensive sort is load-bearing.** Its own comment says the ws cache
    is pre-sorted but the REST-snapshot fallback is NOT — and that fallback is
    "the Railway norm, ws is CDN-blocked". So the live bot's normal path is the
    unsorted one. Drop the sort and the VWAP walk consumes levels in arbitrary
    order: slippage reads far too low, the 25bps gate waves the clip through,
    and the fill happens at a price nobody gated on.
  * **`None` must mean "too thin", never "free".** `vwap_slip` returns None
    when the book cannot fill the clip. The caller vetoes on
    `slip is None or slip > SCAN_MAX_SLIP_BPS` — correct, and fail-closed. A
    refactor that returned 0.0 instead of None would invert that into
    "bottomless book, zero cost".
  * **The side mapping decides which half of the book is checked.** A SHORT
    sells to enter (`sell_slip`, walks bids); a LONG buys (`buy_slip`, walks
    asks). Swap them and the bot gates on the liquidity it is not going to use.
  * **Both slips must be >= 0.** They are adverse costs. A sign flip on either
    side turns an expensive book into an apparently profitable one.

These tests drive the REAL function with hand-built books, so the arithmetic is
checkable by hand rather than asserted against itself. `ctx` is a stub with just
the one attribute the function touches (`ctx.venue.orderbook`) — no venue, no
keys, no network.
"""
import pathlib

import pytest

import lighter_funding_bot as lfb

_ROOT = pathlib.Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.real_money


class _Venue:
    def __init__(self, book):
        self._book = book
        self.calls = 0

    def orderbook(self, coin):
        self.calls += 1
        if isinstance(self._book, Exception):
            raise self._book
        return self._book


class _Ctx:
    def __init__(self, book):
        self.venue = _Venue(book)


def _bm(book, order_usd=1000.0, coin="BTC"):
    return lfb.book_metrics(_Ctx(book), coin, order_usd)


# --------------------------------------------------------------------------
# 1. ONE fetch. The whole reason this function exists.
# --------------------------------------------------------------------------

def test_it_costs_exactly_one_orderbook_fetch():
    """Its docstring: "Replaces the old book_spread_bps + fresh_mid DOUBLE
    fetch on the entry path (governor efficiency)". On Railway the ws is
    CDN-blocked, so every orderbook() costs 1 token of a ~21/min budget shared
    with order txs and sibling bots. A silent second fetch halves the scan's
    reach."""
    ctx = _Ctx({"bids": [[100.0, 100.0]], "asks": [[101.0, 100.0]]})
    lfb.book_metrics(ctx, "BTC", 1000.0)
    assert ctx.venue.calls == 1


# --------------------------------------------------------------------------
# 2. THE DEFENSIVE SORT — the live bot's NORMAL path is the unsorted one.
# --------------------------------------------------------------------------

#: Bids best(highest)-first, asks best(lowest)-first — what the ws cache gives.
_SORTED = {
    "bids": [[99.0, 20.0], [98.0, 20.0], [97.0, 20.0], [90.0, 100.0]],
    "asks": [[101.0, 20.0], [102.0, 20.0], [103.0, 20.0], [110.0, 100.0]],
}
#: The SAME book, order scrambled — what a REST snapshot can hand back.
_SCRAMBLED = {
    "bids": [[90.0, 100.0], [97.0, 20.0], [99.0, 20.0], [98.0, 20.0]],
    "asks": [[110.0, 100.0], [102.0, 20.0], [103.0, 20.0], [101.0, 20.0]],
}


def test_an_unsorted_book_gives_the_IDENTICAL_answer():
    """The single most important assertion in this file. If the sort is ever
    removed as "defensive cruft", these two diverge — and the live bot runs the
    scrambled path, so its slippage estimate would be the wrong one."""
    a, b = _bm(_SORTED, 2000.0), _bm(_SCRAMBLED, 2000.0)
    assert a is not None and b is not None
    assert a == b, (a, b)


def test_the_scrambled_book_does_not_look_cheaper_than_it_is():
    """Directional statement of the same defect: without the sort, the walk
    would start at the 90/110 far levels and report a huge slip, or (depending
    on the scramble) skip them and report a tiny one. Either way it is not the
    real cost of the clip. Pinned against the hand-computed truth below."""
    got = _bm(_SCRAMBLED, 2000.0)
    truth = _bm(_SORTED, 2000.0)
    assert got["buy_slip"] == pytest.approx(truth["buy_slip"])
    assert got["sell_slip"] == pytest.approx(truth["sell_slip"])


def test_top_of_book_comes_from_the_BEST_prices_not_the_first_rows():
    """mid and spread must be computed from best bid/ask. On the scrambled book
    the first rows are 90 and 110 — a 2000bps spread that would trip
    MAX_SPREAD_BPS and veto a perfectly tradeable coin (a false NEGATIVE, the
    cheap direction, but it silently starves the book)."""
    m = _bm(_SCRAMBLED)
    assert m["mid"] == pytest.approx(100.0)
    assert m["spread_bps"] == pytest.approx(200.0)   # (101-99)/100 * 1e4


# --------------------------------------------------------------------------
# 3. THE VWAP ARITHMETIC — hand-computed, not asserted against itself.
# --------------------------------------------------------------------------

def test_a_clip_that_fits_the_touch_slips_by_the_half_spread():
    """$1,000 into a single 101 ask level holding $2,020: VWAP = 101 exactly,
    so slip = (101 - 100)/100 * 1e4 = 100bps. Same on the bid side by
    symmetry."""
    book = {"bids": [[99.0, 100.0]], "asks": [[101.0, 20.0]]}
    m = _bm(book, 1000.0)
    assert m["buy_slip"] == pytest.approx(100.0)
    assert m["sell_slip"] == pytest.approx(100.0)


def test_a_clip_that_walks_two_levels_pays_the_notional_weighted_average():
    """$3,000 of asks: $2,020 at 101, then $980 of the 102 level.
      base = 2020/101 + 980/102 = 20 + 9.60784… = 29.60784…
      vwap = 3000 / 29.60784… = 101.3266…  -> 132.66 bps
    Computed here the same way a human would check it, from the level sizes."""
    book = {"bids": [[99.0, 1000.0]], "asks": [[101.0, 20.0], [102.0, 50.0]]}
    m = _bm(book, 3000.0)
    base = 2020.0 / 101.0 + 980.0 / 102.0
    expect = (3000.0 / base - 100.0) / 100.0 * 1e4
    assert m["buy_slip"] == pytest.approx(expect)
    assert m["buy_slip"] > 100.0, "walking deeper must cost MORE than the touch"


def test_both_sides_are_reported_as_POSITIVE_adverse_cost():
    """They are costs, not signed price deltas. A sign flip on either side
    turns an expensive book into a free one and the 25bps gate stops gating."""
    m = _bm(_SORTED, 2000.0)
    assert m["buy_slip"] > 0 and m["sell_slip"] > 0, m


def test_a_notionally_symmetric_book_costs_the_same_either_way():
    """The clean statement of "both sides use the same arithmetic".

    NOTE the fixture: `_SORTED` is PRICE-symmetric (99/101 about a mid of 100)
    but NOT notionally symmetric — its touch levels hold $1,980 of bids against
    $2,020 of asks, so a $2,000 clip walks two bid levels and one ask level and
    the two slips legitimately differ (100.0 vs 101.01 bps). Asserting equality
    there would have been asserting a fixture accident, so the sides are matched
    in NOTIONAL here instead."""
    book = {"bids": [[99.0, 2000.0 / 99.0]], "asks": [[101.0, 2000.0 / 101.0]]}
    m = _bm(book, 2000.0)
    assert m["buy_slip"] == pytest.approx(m["sell_slip"])
    assert m["buy_slip"] == pytest.approx(100.0)


def test_a_bigger_clip_never_slips_LESS():
    """Monotonicity. The property that would break first under an off-by-one in
    the level walk, and it holds for any real book."""
    prev = -1.0
    for usd in (500.0, 1000.0, 2000.0, 3000.0):
        m = _bm(_SORTED, usd)
        assert m is not None, usd
        assert m["buy_slip"] >= prev - 1e-9, (usd, m["buy_slip"], prev)
        prev = m["buy_slip"]


# --------------------------------------------------------------------------
# 4. None means TOO THIN — the fail-closed contract with the caller.
# --------------------------------------------------------------------------

def test_a_book_too_thin_for_the_clip_returns_None_not_zero():
    """`scan_candidates` vetoes on `slip is None or slip > SCAN_MAX_SLIP_BPS`.
    A refactor returning 0.0 for "ran out of levels" would read as a bottomless
    book at zero cost — the worst possible default on a real-money gate."""
    book = {"bids": [[99.0, 1.0]], "asks": [[101.0, 1.0]]}   # ~$100 a side
    m = _bm(book, 10_000.0)
    assert m is not None, "the METRICS still exist; only the slips are unknown"
    assert m["buy_slip"] is None and m["sell_slip"] is None
    assert m["mid"] == pytest.approx(100.0)      # still usable for logging


def test_one_thin_side_does_not_hide_behind_the_other():
    """Asks deep, bids shallow: a LONG is fine, a SHORT must be vetoed. If the
    two sides shared a computation, the deep side would mask the thin one."""
    book = {"bids": [[99.0, 1.0]], "asks": [[101.0, 1000.0]]}
    m = _bm(book, 5000.0)
    assert m["buy_slip"] is not None, "the deep ask side should fill"
    assert m["sell_slip"] is None, "the shallow bid side must report thin"


def test_the_caller_vetoes_on_None_rather_than_treating_it_as_cheap():
    """The contract, exercised as the caller writes it (lighter_funding_bot.py
    :1029). Pinned here because the fail-closed direction is the whole value of
    returning None."""
    m = _bm({"bids": [[99.0, 1.0]], "asks": [[101.0, 1.0]]}, 10_000.0)
    for is_short in (True, False):
        slip = m["sell_slip"] if is_short else m["buy_slip"]
        vetoed = slip is None or slip > lfb.SCAN_MAX_SLIP_BPS
        assert vetoed, (is_short, slip)


def test_the_side_mapping_matches_the_direction_of_the_trade():
    """A SHORT SELLS to enter, so it walks the BIDS (`sell_slip`); a LONG BUYS,
    so it walks the ASKS (`buy_slip`). Swapping them gates on liquidity the
    order will never touch. Proven with an ASYMMETRIC book, where the two
    answers actually differ.

    The book is TIGHT (99.99/100.01, a 2bps spread) on purpose. An earlier
    version of this test used 99/101 — a 200bps spread — and its "cheap" side
    still cost 100bps against a 25bps gate, so the gate-consequence assertion
    below could not hold for either direction. A fixture has to be a book the
    shipped gate would actually admit, or it tests nothing about the gate."""
    book = {"bids": [[99.99, 1000.0]],                     # deep, cheap to sell
            "asks": [[100.01, 0.01], [140.0, 1000.0]]}     # a dust touch, then awful
    m = _bm(book, 5000.0)
    short_slip = m["sell_slip"]
    long_slip = m["buy_slip"]
    assert short_slip == pytest.approx(1.0), short_slip     # (100 - 99.99)/100 bps
    assert long_slip > 1000.0, long_slip
    # and therefore, at the shipped gate, the short trades and the long does not
    assert short_slip <= lfb.SCAN_MAX_SLIP_BPS
    assert long_slip > lfb.SCAN_MAX_SLIP_BPS


# --------------------------------------------------------------------------
# 5. Junk books must return None, never raise — this runs inside the loop.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("book", [
    {},
    {"bids": [], "asks": []},
    {"bids": [[100.0, 1.0]], "asks": []},
    {"bids": [], "asks": [[101.0, 1.0]]},
    {"bids": None, "asks": None},
    {"bids": [[0.0, 5.0]], "asks": [[101.0, 5.0]]},     # zero-priced top bid
    {"bids": [[99.0, 5.0]], "asks": [[0.0, 5.0]]},      # zero-priced top ask
])
def test_a_degenerate_book_returns_None(book):
    assert _bm(book) is None


def test_a_venue_error_returns_None_rather_than_killing_the_scan():
    assert lfb.book_metrics(_Ctx(RuntimeError("429 rate limited")),
                            "BTC", 1000.0) is None


def test_junk_levels_on_the_BID_side_are_skipped_not_counted():
    """Zero/negative prices and zero sizes appear in real snapshots. On the bid
    side they are harmless: bids sort HIGHEST-first, so garbage sinks to the
    bottom and the VWAP walk's `if px <= 0 or sz <= 0: continue` skips it."""
    clean = {"bids": [[99.0, 100.0]], "asks": [[101.0, 100.0]]}
    dirty = {"bids": [[99.0, 100.0], [0.0, 50.0], [98.0, 0.0], [-1.0, 5.0]],
             "asks": [[101.0, 100.0]]}
    assert _bm(dirty, 1000.0)["sell_slip"] == \
        pytest.approx(_bm(clean, 1000.0)["sell_slip"])
    assert _bm(dirty, 1000.0)["mid"] == pytest.approx(100.0)


def test_FINDING_one_junk_ASK_level_discards_the_whole_book():
    """[2026-07-30 FINDING — behaviour PINNED, deliberately NOT changed here.]

    The two sides are NOT symmetric under junk, and the sort is why. Asks sort
    LOWEST-first, so a single `[0.0, size]` level lands at `asks[0]`, the
    `if not bids[0][0] or not asks[0][0]` top-of-book check sees a falsy price,
    and the ENTIRE book is discarded — including the six perfectly good levels
    behind it. The same garbage on the bid side sorts last and is ignored (the
    test above). `vwap_slip` skips non-positive levels correctly; the sort and
    the top-of-book check, which run BEFORE it, do not.

    DIRECTION IS SAFE: it returns None, the caller vetoes, no bad order is
    placed. So this is not a money-loss defect — it is a **silent starvation**
    path on the LIVE Farmer's entry gate, and this repo has an expensive history
    with exactly that shape (🎯 Perp Sniper sat at n=1 for weeks on an
    unobservable trigger). One malformed level in a REST snapshot — and the REST
    snapshot is the Railway norm, since the ws is CDN-blocked — makes a coin
    permanently untradeable for that loop with no log line saying why.

    WHY NOT FIXED IN THIS COMMIT: filtering non-positive levels before the sort
    would change WHICH COINS the live real-money bot considers. "Never modify
    bot logic without backtesting first" (CLAUDE.md) covers that, and a
    test-coverage pass is the wrong place to widen a live entry gate. The fix is
    a two-line pre-filter, it is fail-safe in the admitting direction only for
    books that were already good, and it needs its own change with the operator
    aware. Pinned here so the fix is a deliberate act with a test that flips,
    rather than something a future refactor does by accident."""
    good_asks = [[101.0, 100.0]]
    m_ok = _bm({"bids": [[99.0, 100.0]], "asks": good_asks}, 1000.0)
    assert m_ok is not None and m_ok["buy_slip"] is not None

    # exactly one garbage level prepended, nothing else changed
    m_junk = _bm({"bids": [[99.0, 100.0]],
                  "asks": [[0.0, 50.0]] + good_asks}, 1000.0)
    assert m_junk is None, (
        "if this now returns a dict, the pre-filter fix has landed — update "
        "this test and the FINDING note above, and make sure the change was "
        "deliberate rather than a side effect")


def test_a_NEGATIVE_priced_ask_is_rejected_and_no_longer_passes_both_gates():
    """[2026-07-30 — this one WAS a fail-open defect, and IS fixed here.]

    The zero case above is safe (it rejects). The negative case was not. The
    top-of-book check was `if not bids[0][0] or not asks[0][0]` — falsy for
    exactly ONE bad value, zero, and TRUE for every negative one — while
    `vwap_slip`, twenty lines below, validates with `if px <= 0`. Two notions of
    "valid price" in one function.

    MEASURED consequence on the LIVE entry path, before the fix. An ask level of
    `[-1.0, 50]` sorts FIRST (asks sort ascending), passed the check, and gave:

        mid 49.0 · spread_bps -20408 · sell_slip -10204 · ask_depth -50

    The caller's gates are `spread_bps > MAX_SPREAD_BPS` (20) and
    `slip > SCAN_MAX_SLIP_BPS` (25). A NEGATIVE number passes both. So a SHORT
    on that book cleared every gate in stage C on a garbage mid — fail-OPEN, on
    real money.

    The fix is `<= 0`: strictly restricting, able only to reject books it used
    to accept, and only ones whose best price is not a positive number. It moves
    no strategy parameter, which is why it does not implicate the
    backtest-first rule the way the zero-ask widening above would."""
    good_asks = [[101.0, 100.0]]
    assert _bm({"bids": [[99.0, 100.0]],
                "asks": [[-1.0, 50.0]] + good_asks}, 1000.0) is None
    # and the bid side too, for the case where every bid is negative
    assert _bm({"bids": [[-99.0, 100.0]], "asks": good_asks}, 1000.0) is None


def test_no_metric_is_ever_negative_or_nonsensical_on_any_junk_book():
    """The generalisation, which is what stops the next variant of this bug. If
    a dict comes back at all, mid must be positive, the spread non-negative, and
    both depths non-negative — because every one of those was negative on the
    book above, and the caller's gates are all `>` comparisons that a negative
    number sails through."""
    junk = [
        {"bids": [[99.0, 100.0]], "asks": [[-1.0, 50.0], [101.0, 100.0]]},
        {"bids": [[-99.0, 100.0]], "asks": [[101.0, 100.0]]},
        {"bids": [[99.0, -100.0]], "asks": [[101.0, 100.0]]},
        {"bids": [[99.0, 100.0]], "asks": [[101.0, -100.0]]},
        {"bids": [[0.0, 100.0]], "asks": [[101.0, 100.0]]},
        {"bids": [[99.0, 100.0], [-5.0, 1.0]], "asks": [[101.0, 100.0]]},
    ]
    for book in junk:
        m = _bm(book, 1000.0)
        if m is None:
            continue                      # rejected outright — the safe answer
        assert m["mid"] > 0, (book, m)
        assert m["spread_bps"] >= 0, (book, m)
        assert m["bid_depth"] >= 0 and m["ask_depth"] >= 0, (book, m)
        for k in ("buy_slip", "sell_slip"):
            assert m[k] is None or m[k] >= 0, (book, k, m)


# --------------------------------------------------------------------------
# 6. The near-touch depth band — input to the imbalance tiebreak.
# --------------------------------------------------------------------------

def test_depth_counts_only_the_half_percent_band_around_mid():
    """band = mid * 0.005, so at mid 100 the window is [99.5, 100.5]. Levels
    outside it are NOT near-touch depth. Getting this wrong feeds the imbalance
    tiebreak a number dominated by far-away resting size — spoofable, and the
    reason the tiebreak is capped at a 30% score haircut rather than a gate."""
    book = {"bids": [[99.9, 10.0], [99.0, 1000.0]],      # 99.0 is OUTSIDE
            "asks": [[100.1, 10.0], [101.0, 1000.0]]}    # 101.0 is OUTSIDE
    m = _bm(book, 500.0)
    assert m["bid_depth"] == pytest.approx(99.9 * 10.0)
    assert m["ask_depth"] == pytest.approx(100.1 * 10.0)


def test_the_imbalance_tiebreak_can_only_ever_REDUCE_a_score():
    """Its own comment: "Small tiebreak only — noisy/spoofable, never a gate."
    The shipped expression is `core * (1 - 0.30 * max(0, imb))`, so a favourable
    book must not be able to PROMOTE a coin past a better-scoring one. Pinned
    because a dropped `max(0, ...)` would silently make it two-way."""
    for imb in (-1.0, -0.5, 0.0, 0.5, 1.0):
        mult = 1.0 - 0.30 * max(0.0, imb)
        assert 0.70 - 1e-9 <= mult <= 1.0, (imb, mult)


def test_zero_total_depth_does_not_divide_by_zero():
    """Both sides can fall entirely outside the band on a wide book. The
    shipped guard is `if tot > 0 else 0.0`; this pins that the inputs which
    trigger it are reachable, so the guard is not dead code."""
    book = {"bids": [[95.0, 10.0]], "asks": [[105.0, 10.0]]}
    m = _bm(book, 100.0)
    assert m["bid_depth"] == 0.0 and m["ask_depth"] == 0.0
    tot = m["bid_depth"] + m["ask_depth"]
    imb = 0.0 if tot <= 0 else 1.0
    assert imb == 0.0


# --------------------------------------------------------------------------
# 7. The gate constant itself — real money sizes off it.
# --------------------------------------------------------------------------

def test_the_slip_gate_is_a_sane_positive_bound():
    """A zero or negative SCAN_MAX_SLIP_BPS would veto everything (silent
    starvation, the failure mode 🎯 Perp Sniper spent weeks in); an enormous one
    would gate nothing at all."""
    assert 1.0 <= lfb.SCAN_MAX_SLIP_BPS <= 200.0, lfb.SCAN_MAX_SLIP_BPS


def test_the_selftest_stub_still_matches_the_real_return_shape():
    """`lighter_funding_bot.py:3114` monkeypatches `book_metrics` with a canned
    dict for its own --selftest. That stub is WHY this function had no coverage,
    and if the real return shape gains a key the stub does not have, the
    selftest passes while the live path KeyErrors. Bind them.

    The stub lives in `_selftest_explore`, not in `main` — an earlier version of
    this test read `main`'s source, found none of the keys, and "failed" on a
    claim about the wrong function. Read the whole module."""
    src = (_ROOT / "lighter_funding_bot.py").read_text()
    stub = src[src.index("M.book_metrics = lambda"):]
    stub = stub[:stub.index("}") + 1]
    real = set(_bm(_SORTED, 1000.0))
    stub_keys = {k for k in real if f'"{k}"' in stub}
    assert real <= stub_keys, (
        f"the --selftest stub is missing {sorted(real - stub_keys)} — the real "
        "book_metrics returns keys the stub does not, so the selftest exercises "
        "a shape the live bot never sees")
