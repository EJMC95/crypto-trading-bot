"""Tier 1 — LighterClient venue-response PARSING: the numbers real money runs on.

test_lighter_client_orders.py covers the order path (sizing, worst-price,
reduce-only). This file covers the other half of Finding 3
(TEST_COVERAGE_ANALYSIS_2026-07-29.md): the parsing of what the VENUE sends
BACK — positions, equity fields, funding, order books, and fill matching.
A mis-parse here is the input class behind the 11-Jul dislocation flatten:
the equity guard defends against a wrong number, but nothing proved the
client produces right numbers from real venue payload shapes.

Everything runs on a bare client (__new__, no signer/network/SDK), with
fixtures shaped like the venue's real responses (dict payloads from
r.to_dict(), attr-style trade rows from the SDK models).
"""
from types import SimpleNamespace as NS

import pytest

from venues import lighter_client as lc
from venues.lighter_client import LighterClient, VenueError, _settle_ms_of, _tx_hash_of

pytestmark = pytest.mark.real_money

ACCOUNT = 733196          # the live account_index shape (docs/lighter.md banner)


def _client(**attrs):
    c = LighterClient.__new__(LighterClient)
    for k, v in attrs.items():
        setattr(c, k, v)
    return c


# ── _settle_ms_of / _tx_hash_of: the SDK-shape probes ────────────────────────
def test_settle_ms_probes_attr_dict_and_camelcase():
    assert _settle_ms_of(NS(predicted_execution_time_ms=350)) == 350.0
    assert _settle_ms_of({"predictedExecutionTimeMs": "250"}) == 250.0
    assert _settle_ms_of(NS(predicted_execution_time_ms=0)) is None   # not >0
    assert _settle_ms_of({"predicted_execution_time_ms": "junk"}) is None
    assert _settle_ms_of(NS()) is None and _settle_ms_of({}) is None


def test_tx_hash_probes_resp_first_then_tx_then_bare_hex():
    assert _tx_hash_of(None, NS(tx_hash="abc123")) == "abc123"
    assert _tx_hash_of(NS(hash="deadbeef"), None) == "deadbeef"
    assert _tx_hash_of(None, {"tx_hash": "ff00"}) == "ff00"
    # resp wins over tx when both carry a hash
    assert _tx_hash_of(NS(tx_hash="from_tx"), NS(tx_hash="from_resp")) == "from_resp"
    # a bare hex string of plausible length IS a hash…
    hex64 = "ab" * 32
    assert _tx_hash_of(None, hex64) == hex64
    # …but a repr-like string must never match a trade's hash by accident
    assert _tx_hash_of(None, f"<TxResp {hex64}>") is None
    assert _tx_hash_of(None, "abcdef") is None            # too short
    assert _tx_hash_of(None, None) is None


# ── _positions_from: the position parser feeding rails + equity guard ────────
def _acct(positions=None, **fields):
    return {"positions": positions or [], **fields}


def test_positions_sign_size_entry_and_upnl():
    acct = _acct([
        {"symbol": "BTC", "sign": 1, "position": "0.5",
         "avg_entry_price": "60000", "unrealized_pnl": "-12.5"},
        {"symbol": "ETH", "sign": -1, "position": "2",
         "avg_entry_price": "2500"},
    ])
    out = LighterClient._positions_from(acct)
    assert out["BTC"] == {"size": 0.5, "entry": 60000.0, "upnl": -12.5}
    assert out["ETH"]["size"] == -2.0          # sign -1 => a SHORT is negative
    assert out["ETH"]["entry"] == 2500.0
    assert "upnl" not in out["ETH"]            # absent stays absent


def test_positions_zero_size_rows_are_flat_not_positions():
    acct = _acct([{"symbol": "BTC", "sign": 1, "position": "0",
                   "avg_entry_price": "60000"}])
    assert LighterClient._positions_from(acct) == {}


def test_positions_translate_1000_markets_to_fleet_k_form():
    # The kNOT round-trip incident class: venue symbol 1000BONK must come back
    # as the fleet's kBONK, or market_close() on the held coin can no-op.
    acct = _acct([{"symbol": "1000BONK", "sign": 1, "position": "4580",
                   "avg_entry_price": "0.003275"}])
    out = LighterClient._positions_from(acct)
    assert list(out) == ["kBONK"]


def test_positions_junk_upnl_keeps_the_row_drops_the_field():
    acct = _acct([{"symbol": "BTC", "sign": 1, "position": "1",
                   "avg_entry_price": "100", "unrealized_pnl": "n/a"}])
    out = LighterClient._positions_from(acct)
    assert out["BTC"]["size"] == 1.0 and "upnl" not in out["BTC"]


# ── _equity_fields: the equity read the daily-loss rail runs on ──────────────
def test_equity_prefers_total_asset_value():
    c = _client()
    total, coll, pos = c._equity_fields(
        _acct(total_asset_value="1034.67", collateral="900.0"))
    assert total == 1034.67 and coll == 900.0 and pos == {}


def test_equity_falls_back_to_collateral():
    c = _client()
    total, coll, _ = c._equity_fields(_acct(collateral="880.5"))
    assert total == 880.5 and coll == 880.5


def test_equity_raises_when_no_value_field():
    # An unreadable equity must be a VenueError (callers treat it as
    # "unreadable this loop"), never a silent 0.0 that trips the loss rail.
    with pytest.raises(VenueError):
        _client()._equity_fields(_acct(irrelevant="1"))


# ── funding_map: lighter rate vs benchmark rows ──────────────────────────────
def test_funding_map_splits_lighter_rate_from_benchmarks():
    resp = NS(to_dict=lambda: {"funding_rates": [
        {"symbol": "BTC", "exchange": "lighter", "rate": "0.0001"},
        {"symbol": "BTC", "exchange": "binance", "rate": "0.0002"},
        {"symbol": "BTC", "exchange": "hyperliquid", "rate": None},
        {"symbol": "1000BONK", "exchange": "lighter", "rate": "-0.0003"},
    ]})
    c = _client(_funding_api=NS(funding_rates=lambda: "CORO"),
                _run=lambda coro: resp,
                markets={"BTC": {"last": 60000.0, "day_vol": 5e6},
                         "1000BONK": {"last": 0.0032, "day_vol": 1e5}})
    out = c.funding_map()
    assert out["BTC"]["rate"] == 0.0001            # lighter's own rate
    assert out["BTC"]["_bench"]["binance"] == 0.0002
    assert out["BTC"]["_bench"]["hyperliquid"] == 0.0   # None coerced, not crash
    assert out["BTC"]["mark"] == 60000.0 and out["BTC"]["vol"] == 5e6
    assert out["kBONK"]["rate"] == -0.0003         # fleet k-form key
    assert out["kBONK"]["mark"] == 0.0032          # enriched via to_lighter()


# ── _rest_book: the UNSORTED-snapshot fix + the TTL cache ────────────────────
def _book_resp(bids, asks):
    return NS(to_dict=lambda: {
        "bids": [{"price": str(p), "remaining_base_amount": str(s)}
                 for p, s in bids],
        "asks": [{"price": str(p), "remaining_base_amount": str(s)}
                 for p, s in asks]})


def test_rest_book_sorts_what_the_venue_returns_unsorted():
    # Every consumer takes [0] as top-of-book; the venue returns snapshots
    # UNSORTED. best bid must be the HIGHEST, best ask the LOWEST.
    calls = []

    def run(coro):
        calls.append(coro)
        return _book_resp(bids=[(99.0, 1), (101.0, 2), (100.0, 3)],
                          asks=[(103.0, 1), (102.0, 2), (104.0, 3)])

    c = _client(_order_api=NS(order_book_orders=lambda market_id, limit: "CORO"),
                _run=run, _rest_books={})
    book = c._rest_book(7)
    assert book["bids"][0] == (101.0, 2.0)     # highest bid on top
    assert book["asks"][0] == (102.0, 2.0)     # lowest ask on top
    assert [p for p, _ in book["bids"]] == [101.0, 100.0, 99.0]
    assert [p for p, _ in book["asks"]] == [102.0, 103.0, 104.0]


def test_rest_book_ttl_cache_and_force_refresh():
    calls = []

    def run(coro):
        calls.append(coro)
        return _book_resp(bids=[(100.0, 1)], asks=[(101.0, 1)])

    c = _client(_order_api=NS(order_book_orders=lambda market_id, limit: "CORO"),
                _run=run, _rest_books={})
    c._rest_book(7)
    c._rest_book(7)                    # within TTL -> cached, no second call
    assert len(calls) == 1             # guard + strategy don't double-pay
    c._rest_book(7, force=True)        # force bypasses the cache
    assert len(calls) == 2


# ── _our_fills: ownership, id tiers, and the VWAP ────────────────────────────
def _trade(ask_acct=None, bid_acct=None, price=100.0, size=1.0, ts=None,
           tx_hash=None, ask_cid=None, bid_cid=None):
    return NS(ask_account_id=ask_acct, bid_account_id=bid_acct,
              price=price, size=size, timestamp=ts, tx_hash=tx_hash,
              ask_client_id=ask_cid, bid_client_id=bid_cid)


def test_our_fills_id_narrows_but_never_authorises():
    # The incident the docstring records: a STRANGER's fill carrying our
    # client id (ids are per-account timestamps — collisions happen) must
    # never be read as ours. Ownership is checked on every path.
    c = _client(account_index=ACCOUNT)
    stranger = _trade(ask_acct=999999, price=50.0, size=1.0, ask_cid=42)
    assert c._our_fills([stranger], is_ask=True, since_ts=0, client_id=42) is None


def test_our_fills_vwaps_partials_of_one_order_by_tx_hash():
    c = _client(account_index=ACCOUNT)
    h = "aa" * 20
    trades = [
        _trade(ask_acct=ACCOUNT, price=100.0, size=1.0, tx_hash=h),
        _trade(ask_acct=ACCOUNT, price=102.0, size=3.0, tx_hash=h),
        _trade(ask_acct=ACCOUNT, price=999.0, size=5.0, tx_hash="bb" * 20),  # other order
    ]
    vwap = c._our_fills(trades, is_ask=True, since_ts=0, tx_hash=h)
    assert vwap == pytest.approx((100.0 * 1 + 102.0 * 3) / 4)


def test_our_fills_client_id_tier_excludes_other_orders_in_window():
    # The blend incident: an open on one lens + a stop on another, same side,
    # same window — the id match must keep them apart.
    c = _client(account_index=ACCOUNT)
    trades = [
        _trade(bid_acct=ACCOUNT, price=10.0, size=2.0, bid_cid=777),
        _trade(bid_acct=ACCOUNT, price=99.0, size=2.0, bid_cid=888),  # different order
    ]
    vwap = c._our_fills(trades, is_ask=False, since_ts=0, client_id=777)
    assert vwap == 10.0


def test_our_fills_timestamp_fallback_converts_ms_and_windows():
    c = _client(account_index=ACCOUNT)
    since = 1_700_000_000.0
    trades = [
        _trade(ask_acct=ACCOUNT, price=100.0, size=1.0,
               ts=(since + 10) * 1000),               # venue stamps ms
        _trade(ask_acct=ACCOUNT, price=50.0, size=1.0,
               ts=(since - 60) * 1000),               # before the window
    ]
    vwap = c._our_fills(trades, is_ask=True, since_ts=since)
    assert vwap == 100.0                              # the stale row excluded


def test_our_fills_empty_or_no_match_is_none():
    c = _client(account_index=ACCOUNT)
    assert c._our_fills([], is_ask=True, since_ts=0) is None
    assert c._our_fills(None, is_ask=True, since_ts=0) is None


# ── _resolve / supports / candles ────────────────────────────────────────────
def test_resolve_requires_listed_and_active():
    c = _client(net="mainnet",
                markets={"BTC": {"status": "active", "id": 1},
                         "OLD": {"status": "inactive", "id": 2}})
    assert c.supports("BTC") is True
    assert c.supports("OLD") is False       # listed but inactive
    assert c.supports("ATOM") is False      # not listed at all
    with pytest.raises(VenueError):
        c._resolve("ATOM")


def test_candles_raises_on_non_200_code():
    c = _client(net="mainnet",
                markets={"BTC": {"status": "active", "id": 1}},
                _candle_api=NS(candles=lambda **kw: "CORO"),
                _run=lambda coro: NS(to_dict=lambda: {"code": 429}))
    with pytest.raises(VenueError):
        c.candles("BTC", "4h", 0, 8 * 3600 * 1000)


def test_interval_ms_arithmetic():
    assert LighterClient._interval_ms("15m") == 15 * 60 * 1000
    assert LighterClient._interval_ms("4h") == 4 * 3600 * 1000
    assert LighterClient._interval_ms("1d") == 86400 * 1000
