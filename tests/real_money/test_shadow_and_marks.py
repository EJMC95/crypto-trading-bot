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
