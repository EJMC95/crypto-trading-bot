"""Tier 1 — the ShadowBroker fill model + the shared mid helpers.

Finding 6's last open item (TEST_COVERAGE_ANALYSIS_2026-07-29.md): every
`-lshadow` book's P&L — the EVIDENCE the promotion judge's paired bar and the
brain's grades rest on — is produced by venues/shadow.py's fill model, at 28%
coverage with no tests. A silent bug here corrupts go-live decisions
fleet-wide while every individual bot looks healthy. venues/marks.py (15%)
is the shared live-book mid the equity guard and bots price risk from.

The contracts pinned:
  * fills CROSS THE SPREAD in the real book — buys walk UP the asks, sells
    DOWN the bids, VWAP'd over the levels actually consumed (the honest,
    slightly pessimistic model the module docstring promises);
  * slippage_bps is ADVERSE-POSITIVE on both sides (a buy filled above
    decision and a sell filled below both read positive);
  * a dead venue or thin book falls back to the DECISION price and never
    raises into the trading loop; the ledger row still publishes;
  * accounting uses the FILL price, zero fees (slippage IS the cost model);
  * fresh_mid reduces with max(bid)/min(ask) — the venue's REST snapshots
    come back UNSORTED and [0]-indexing an unsorted book is just some price.
"""
from types import SimpleNamespace as NS

import pytest

import bot_pnl_store
from venues import marks
from venues.shadow import ShadowBroker, fill_from_book

pytestmark = pytest.mark.real_money


# ── fill_from_book: the spread-crossing walk ─────────────────────────────────
def test_buy_walks_up_the_asks_and_vwaps():
    book = {"asks": [(100.0, 1.0), (101.0, 2.0), (102.0, 5.0)],
            "bids": [(99.0, 9.0)]}
    px, levels, top = fill_from_book(book, is_buy=True, size=2.0)
    assert px == pytest.approx((100.0 * 1 + 101.0 * 1) / 2)   # 100.5 — worse than top
    assert levels == 2 and top == 100.0


def test_sell_walks_down_the_bids():
    book = {"bids": [(100.0, 1.0), (99.0, 2.0)], "asks": [(101.0, 9.0)]}
    px, levels, top = fill_from_book(book, is_buy=False, size=2.0)
    assert px == pytest.approx(99.5) and levels == 2 and top == 100.0


def test_single_level_fill_is_exact():
    book = {"asks": [(100.0, 5.0)], "bids": []}
    assert fill_from_book(book, True, 1.0) == (100.0, 1, 100.0)


def test_insufficient_depth_and_empty_side_are_none():
    assert fill_from_book({"asks": [(100.0, 1.0)], "bids": []}, True, 5.0) is None
    assert fill_from_book({"asks": [], "bids": [(99.0, 1.0)]}, True, 1.0) is None


# ── ShadowBroker: the evidence engine ────────────────────────────────────────
class _Venue:
    def __init__(self, book=None, boom=False):
        self.book, self.boom = book, boom

    def orderbook(self, coin):
        if self.boom:
            raise RuntimeError("venue down")
        return self.book


@pytest.fixture
def orders(monkeypatch):
    rows = []
    monkeypatch.setattr(bot_pnl_store, "publish_venue_order",
                        lambda bot, **kw: rows.append({"bot": bot, **kw}))
    return rows


def test_open_accounts_at_the_fill_price_not_the_decision(orders):
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.5, 10.0)],
                                          "bids": [(99.5, 10.0)]}))
    b.open("BTC", is_long=True, size=1.0, price=100.0)
    size, entry = b.pos["BTC"]
    assert size == 1.0 and entry == 100.5      # the crossed spread is the cost
    row = orders[-1]
    assert row["side"] == "buy" and row["px_decision"] == 100.0
    assert row["px_fill"] == 100.5
    assert row["slippage_bps"] == pytest.approx(50.0)      # buy above decision
    assert row["spread_bps"] == pytest.approx((100.5 - 99.5) / 100.0 * 1e4)
    assert row["shadow"] is True and row["venue"] == "lighter"


def test_slippage_is_adverse_positive_on_both_sides(orders):
    # closing a LONG sells into the bids: filled BELOW decision must read
    # POSITIVE too (symmetric pessimism), or slip stats would net to zero.
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.5, 10.0)],
                                          "bids": [(99.5, 10.0)]}))
    b.open("BTC", True, 1.0, 100.0)
    b.close("BTC", 100.0)
    row = orders[-1]
    assert row["side"] == "sell" and row["px_fill"] == 99.5
    assert row["slippage_bps"] == pytest.approx(50.0)


def test_dead_venue_falls_back_to_decision_and_never_raises(orders):
    b = ShadowBroker("t-lshadow", _Venue(boom=True))
    b.open("BTC", True, 1.0, 100.0)            # no exception into the loop
    assert b.pos["BTC"] == (1.0, 100.0)        # decision px used
    row = orders[-1]
    assert row["px_fill"] == 100.0
    assert row["raw"]["levels_used"] == 0      # honest: nothing was walked
    assert row["spread_bps"] is None


def test_thin_book_falls_back_to_decision(orders):
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.5, 0.1)],
                                          "bids": [(99.5, 0.1)]}))
    b.open("BTC", True, 5.0, 100.0)            # book can't fill 5 units
    assert b.pos["BTC"] == (5.0, 100.0)
    assert orders[-1]["raw"]["levels_used"] == 0


def test_close_unknown_coin_is_zero_and_publishes_nothing(orders):
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(1, 1)], "bids": [(1, 1)]}))
    assert b.close("NEVERHELD", 100.0) == 0.0
    assert orders == []


def test_closing_a_short_buys_back_up_the_asks(orders):
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.5, 10.0)],
                                          "bids": [(99.5, 10.0)]}))
    b.open("ETH", is_long=False, size=2.0, price=100.0)     # short fills at bid
    assert b.pos["ETH"][1] == 99.5
    b.close("ETH", 100.0)                                    # cover crosses the ask
    assert orders[-1]["side"] == "buy" and orders[-1]["px_fill"] == 100.5


def test_zero_fee_model_round_trip_costs_only_the_spread(orders):
    # fee_bps forced to 0 (Lighter standard tier): a full round trip on a
    # 1-wide book must cost exactly the crossed spread, nothing else.
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.5, 10.0)],
                                          "bids": [(99.5, 10.0)]}),
                     start_equity=1000.0)
    b.open("BTC", True, 1.0, 100.0)            # buy at 100.5
    b.close("BTC", 100.0)                      # sell at 99.5
    assert b.equity() == pytest.approx(1000.0 - 1.0)   # the spread, only


# ── venues/marks: the shared live-book mid ───────────────────────────────────
def test_fresh_mid_reduces_unsorted_books_with_max_min():
    v = _Venue({"bids": [(99.0, 1.0), (101.0, 2.0)],
                "asks": [(104.0, 1.0), (102.0, 3.0)]})
    assert marks.fresh_mid(v, "BTC") == pytest.approx((101.0 + 102.0) / 2)


def test_fresh_mid_filters_junk_and_fails_to_none():
    assert marks.fresh_mid(_Venue(boom=True), "BTC") is None
    assert marks.fresh_mid(_Venue(None), "BTC") is None
    assert marks.fresh_mid(_Venue({"bids": [], "asks": [(1.0, 1)]}), "BTC") is None
    # non-positive levels are not prices
    v = _Venue({"bids": [(0.0, 5.0), (-1.0, 2.0)], "asks": [(1.0, 1.0)]})
    assert marks.fresh_mid(v, "BTC") is None


def test_mid_map_skips_unreadable_coins():
    class _V:
        def orderbook(self, coin):
            if coin == "DEAD":
                raise RuntimeError("no book")
            return {"bids": [(99.0, 1.0)], "asks": [(101.0, 1.0)]}

    out = marks.mid_map(_V(), ["BTC", "DEAD", "ETH"])
    assert out == {"BTC": 100.0, "ETH": 100.0}     # DEAD absent, not None


# ── the unmeasured fill: NULL, never a fabricated zero ───────────────────────
# [2026-09-07] An order the book could not fill was published with
# `slippage_bps = 0.0`, i.e. as a MEASURED zero-cost execution.
# `market_context._fold_coin_quality` counts non-null slippage as
# `measured_14d` — the n-floor of the coin-quality veto all three live books
# consume at their entry site — and averages the same column. So the orders
# that could NOT be filled satisfied the floor and pulled the average toward
# zero, in the one mechanism whose job is to veto coins that are expensive to
# trade. The rule pinned below is the fleet's own, already enforced for live
# fills in venues/fills.slip_bps_of and in the Ticket Taker's selftest.

def _walked_book():
    return {"asks": [(100.5, 10.0)], "bids": [(99.5, 10.0)]}


def test_a_walked_fill_is_measured_and_names_its_source(orders):
    b = ShadowBroker("t-lshadow", _Venue(_walked_book()))
    b.open("BTC", True, 1.0, 100.0)
    row = orders[-1]
    assert row["raw"]["measured"] is True
    assert row["raw"]["fill_src"] == "walked"
    assert row["raw"]["levels_used"] == 1
    assert row["raw"]["book_top"] == 100.5
    assert row["slippage_bps"] == pytest.approx(50.0)


def test_a_thin_book_records_NULL_slippage_not_zero(orders):
    # the book quotes both sides but cannot cover the clip
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.5, 0.1)],
                                          "bids": [(99.5, 0.1)]}))
    b.open("BTC", True, 5.0, 100.0)
    row = orders[-1]
    assert row["slippage_bps"] is None, \
        f"an unfillable order must be NULL, never 0.0: {row['slippage_bps']!r}"
    assert row["raw"]["measured"] is False
    assert row["raw"]["fill_src"] == "thin-book"
    assert row["raw"]["book_top"] is None, \
        "no level was read, so there is no book top to report"
    assert row["px_fill"] == 100.0        # accounting still uses the decision


def test_an_empty_side_is_named_apart_from_a_thin_book(orders):
    # the thinnest market of all: nothing quoted on the side we must cross
    b = ShadowBroker("t-lshadow", _Venue({"asks": [], "bids": [(99.5, 10.0)]}))
    b.open("BTC", True, 1.0, 100.0)
    row = orders[-1]
    assert row["slippage_bps"] is None
    assert row["raw"]["fill_src"] == "empty-side"


def test_a_dead_venue_is_named_apart_from_a_thin_book(orders):
    # {levels_used: 0} is byte-identical between "market too thin" and "the
    # venue is down" — and the second fires fleet-wide at once.
    b = ShadowBroker("t-lshadow", _Venue(boom=True))
    b.open("BTC", True, 1.0, 100.0)
    row = orders[-1]
    assert row["slippage_bps"] is None
    assert row["raw"]["measured"] is False
    assert row["raw"]["fill_src"].startswith("venue-dark:"), row["raw"]


def test_an_empty_book_answer_is_named_apart_from_a_raise(orders):
    b = ShadowBroker("t-lshadow", _Venue(None))
    b.open("BTC", True, 1.0, 100.0)
    assert orders[-1]["raw"]["fill_src"] == "no-book"
    assert orders[-1]["slippage_bps"] is None


def test_a_MEASURED_at_mark_fill_still_records_a_real_zero(orders):
    # the over-correction this guards against: a genuine fill that lands
    # exactly on the decision price is a measurement of zero slippage, and
    # must NOT be swept into the NULL bucket with the unfillable orders.
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.0, 10.0)],
                                          "bids": [(100.0, 10.0)]}))
    b.open("BTC", True, 1.0, 100.0)
    row = orders[-1]
    assert row["px_fill"] == 100.0 and row["px_decision"] == 100.0
    assert row["slippage_bps"] == 0.0, \
        ("a walked fill at the decision price is a MEASURED zero, not an "
         f"absence: {row['slippage_bps']!r}")
    assert row["raw"]["measured"] is True


def test_the_fallback_leaves_pnl_byte_identical(orders):
    # the fix is telemetry-only: an unfillable open/close must book exactly
    # what it booked before, or every shadow equity curve moves under it.
    b = ShadowBroker("t-lshadow", _Venue({"asks": [(100.5, 0.1)],
                                          "bids": [(99.5, 0.1)]}))
    b.open("BTC", True, 5.0, 100.0)
    assert b.pos["BTC"] == (5.0, 100.0)
    pnl = b.close("BTC", 110.0)
    assert pnl == pytest.approx(50.0)          # 5 units x $10, fees are zero
    assert b.equity() == pytest.approx(1050.0)


def test_the_close_leg_is_held_to_the_same_rule(orders):
    # the entry-side spread gate some books carry does not sit on the close,
    # so the exit is where an unmeasured fill is most likely to slip through.
    b = ShadowBroker("t-lshadow", _Venue(_walked_book()))
    b.open("BTC", True, 1.0, 100.0)
    b.venue.book = {"asks": [(100.5, 0.01)], "bids": [(99.5, 0.01)]}
    b.close("BTC", 100.0)
    row = orders[-1]
    assert row["side"] == "sell"
    assert row["slippage_bps"] is None and row["raw"]["measured"] is False
