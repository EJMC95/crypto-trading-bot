"""Tier 1 — LighterClient order path: sizing, slippage guard, and reduce-only.

This is the code that signs real orders. venues/lighter_client.py's own selftest
is explicit that "the loop/signer need a venue and are not covered" — so the
sizing (`_scaled`), the ±2% worst-price guard, the is_ask side pick, and the
`reduce_only=True` flag on the flatten path (the ONLY reduce_only in the
codebase, which every kill/daily-loss flatten depends on) were untested.

We never touch the real signer: a bare client is built with __new__ and the
signer's create_market_order is stubbed to CAPTURE the exact kwargs the venue
would receive, so we assert on what gets signed.
"""
import pytest

from venues.lighter_client import LighterClient, VenueError

MARKET = {"id": 7, "size_decimals": 3, "price_decimals": 2}


class _Signer:
    def __init__(self):
        self.kw = None

    def create_market_order(self, **kw):
        self.kw = kw
        return "ORDER_OBJECT"


def _client(book, positions=None):
    """A LighterClient with __init__ bypassed and only the order path wired."""
    c = LighterClient.__new__(LighterClient)
    c.api_key_index = 4
    c.signer = _Signer()
    c._resolve = lambda coin: (f"{coin}-USD", 1.0, MARKET)
    c.orderbook = lambda coin: book
    c.positions = lambda: (positions or {})
    c._run_signer = lambda order: (object(), object(), None)
    return c


# ── _scaled: integer scaling by the market's decimals ────────────────────────
def test_scaled_rounds_to_market_decimals():
    c = LighterClient.__new__(LighterClient)
    base, px = c._scaled(MARKET, 0.037358, 535.4)
    assert base == 37          # round(0.037358 * 1e3)
    assert px == 53540         # round(535.4 * 1e2)


def test_scaled_is_round_half_not_truncate():
    c = LighterClient.__new__(LighterClient)
    base, _ = c._scaled({"size_decimals": 0, "price_decimals": 0}, 2.5, 1.0)
    assert base == 2           # banker's rounding: round(2.5) == 2
    base, _ = c._scaled({"size_decimals": 0, "price_decimals": 0}, 3.5, 1.0)
    assert base == 4


# ── market_open: side, worst-price guard, no reduce_only ─────────────────────
def test_open_long_uses_ask_side_plus_2pct():
    c = _client({"asks": [[100.0, 9]], "bids": [[99.0, 9]]})
    out = c.market_open("BTC", is_long=True, size=0.05)
    kw = c.signer.kw
    assert kw["is_ask"] is False               # a long BUYS -> not an ask
    assert kw["avg_execution_price"] == 10200  # 100.0 * 1.02, scaled x100
    assert kw["base_amount"] == 50             # 0.05 * 1e3
    assert kw["market_index"] == 7 and kw["api_key_index"] == 4
    assert not kw.get("reduce_only")           # an OPEN must never be reduce-only
    assert out["client_order_index"] == kw["client_order_index"]


def test_open_short_uses_bid_side_minus_2pct():
    c = _client({"asks": [[100.0, 9]], "bids": [[99.0, 9]]})
    c.market_open("ETH", is_long=False, size=1.0)
    kw = c.signer.kw
    assert kw["is_ask"] is True                # a short SELLS -> an ask
    assert kw["avg_execution_price"] == 9702   # 99.0 * 0.98, scaled x100


def test_open_rejects_size_that_scales_to_zero():
    c = _client({"asks": [[100.0, 9]], "bids": [[99.0, 9]]})
    with pytest.raises(VenueError):
        c.market_open("BTC", is_long=True, size=0.0)
    assert c.signer.kw is None                 # nothing was signed


def test_open_rejects_empty_book():
    c = _client({"asks": [], "bids": [[99.0, 9]]})
    with pytest.raises(VenueError):
        c.market_open("BTC", is_long=True, size=0.05)


# ── market_close: the reduce-only flatten path ───────────────────────────────
def test_close_long_is_reduce_only_ask():
    c = _client({"asks": [[100.0, 9]], "bids": [[99.0, 9]]},
                positions={"BTC": {"size": 2.0, "entry": 100.0}})
    out = c.market_close("BTC")
    kw = c.signer.kw
    assert kw["reduce_only"] is True           # THE flatten guarantee
    assert kw["is_ask"] is True                # closing a long SELLS
    assert kw["avg_execution_price"] == 9702   # bid 99.0 * 0.98
    assert kw["base_amount"] == 2000           # 2.0 * 1e3
    assert out["client_order_index"] == kw["client_order_index"]


def test_close_short_is_reduce_only_bid():
    c = _client({"asks": [[100.0, 9]], "bids": [[99.0, 9]]},
                positions={"ETH": {"size": -3.0, "entry": 100.0}})
    c.market_close("ETH")
    kw = c.signer.kw
    assert kw["reduce_only"] is True
    assert kw["is_ask"] is False               # closing a short BUYS
    assert kw["avg_execution_price"] == 10200  # ask 100.0 * 1.02


def test_close_noop_when_flat():
    c = _client({"asks": [[100.0, 9]], "bids": [[99.0, 9]]}, positions={})
    assert c.market_close("BTC") is None
    assert c.signer.kw is None                 # no order signed for a flat book
