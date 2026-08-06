"""[2026-08-06 (ku)] THE INSTRUMENT CLASS RIDES ON THE TICKET, so closing the
next leak costs a scout cycle instead of a real-money deploy.

`(kt)` closed a LIVE exposure: 🎫 the Ticket Taker screens non-crypto on its
real-money path (`bull_entry_ok` -> `_is_crypto`) from a HAND LIST that had
fallen 41 names behind. Measured on the bus that morning, `DRAM`, `CXMT` and
`CAP` were live tickets it would have admitted — `CAP` on the `divergence`
lens, which is the only lens the live arm trades.

Closing it cost a code change to a real-money module and a marked deploy, and
the same defect recurs every time the venue lists another tokenised equity —
which it does weekly.

THE STRUCTURAL FIX: the scout stamps `noncrypto` on every ticket from the
VENUE's own `strategy_index`. The taker cannot read `lighter-market.classes`
at all (`Dockerfile.tickettaker` deliberately omits `fleet_bus` to keep the
lean live image free of its dependency chain — the born-dark trap its own
comment names), but it already reads TICKETS. So the fact travels on the
object the consumer is guaranteed to have.

TWO CONTRACTS, both load-bearing:
  * ABSENT means NO OPINION, never "crypto". The key is omitted when the venue
    publishes no class, so a consumer falls back to its own rule instead of
    reading a fabricated answer.
  * RESTRICT-ONLY at the consumer: either screen may reject, neither may
    admit. The local list stays as the fallback for an unstamped ticket.
"""
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import fleet_bus  # noqa: E402
import lighter_market_scout as scout  # noqa: E402
import lighter_ticket_taker as tt  # noqa: E402


def _book(sym, idx, qvol=5e6):
    """One `orderBookDetails` row in the venue's real shape."""
    return {"symbol": sym, "status": "active", "strategy_index": idx,
            "mark_price": "100", "index_price": "100",
            "daily_quote_token_volume": str(qvol), "open_interest": "10",
            "last_trade_price": "110", "daily_price_high": "110",
            "daily_price_low": "100", "daily_price_change": "5.0",
            "created_at": "1737098461107",
            "taker_fee": "0", "maker_fee": "0"}


#: The three symbols `(kt)` measured on the live bus, plus a control and a
#: book the venue does not classify.
_VENUE = [_book("BTC", 2), _book("CAP", 7), _book("CXMT", 7),
          _book("DRAM", 5), _book("NOCLASS", None)]


@pytest.fixture
def tickets():
    """Built by the PUBLISHER, never hand-written — the (hj) rule."""
    stats = scout.book_stats(_VENUE, min_qvol=0.0)
    aprs = {b["symbol"]: 10.0 for b in _VENUE}
    out = {}
    for rows in scout.strategy_tickets(stats, aprs).values():
        for r in rows:
            out.setdefault(r["sym"], r)
    return out


class TestThePublisherStampsIt:
    @pytest.mark.parametrize("sym", ["CAP", "CXMT", "DRAM"])
    def test_the_three_symbols_the_incident_named(self, tickets, sym):
        assert tickets[sym]["noncrypto"] is True

    def test_crypto_is_stamped_false_not_omitted(self, tickets):
        """False and absent mean different things; a crypto book says so."""
        assert tickets["BTC"]["noncrypto"] is False

    def test_an_unclassified_book_has_NO_KEY(self, tickets):
        """ABSENT = no opinion. Emitting `False` here would be a fabricated
        answer, and the consumer would trust it over its own list."""
        assert "noncrypto" not in tickets["NOCLASS"]

    def test_every_lens_is_stamped_not_just_one(self):
        """Stamped in ONE place for all four lenses, so a lens cannot silently
        miss it — the idiom the regime stamp already uses."""
        stats = scout.book_stats(_VENUE, min_qvol=0.0)
        aprs = {b["symbol"]: 10.0 for b in _VENUE}
        div = [{"sym": "CAP", "gap_pct": -400.0,
                "lighter_apr": -1500.0, "xvenue_apr": -1100.0}]
        out = scout.strategy_tickets(stats, aprs, divergence=div)
        assert out["divergence"], "fixture produced no divergence ticket"
        for lens, rows in out.items():
            for r in rows:
                if r["sym"] != "NOCLASS":
                    assert "noncrypto" in r, f"{lens}/{r['sym']} unstamped"


class TestTheConsumerHonoursIt:
    """`bull_entry_ok` gates the live real-money path: the live arm is
    divergence-SHORT only and runs bull mode."""

    def test_a_stamped_noncrypto_ticket_is_refused(self):
        assert not tt.bull_entry_ok(
            "divergence", "short", {"sym": "CAP", "noncrypto": True}, up=False)

    def test_an_unstamped_ticket_falls_back_to_the_local_list(self):
        """An older scout, or a book the venue does not classify. The hand
        list is the fallback, not dead weight."""
        assert not tt.bull_entry_ok(
            "divergence", "short", {"sym": "CAP"}, up=False)

    def test_an_unknown_symbol_is_still_admitted_fail_open(self):
        """The venue lists new CRYPTO books constantly; a closed default would
        starve the book every time one appeared."""
        assert tt.bull_entry_ok(
            "divergence", "short", {"sym": "NEWCOIN"}, up=False)

    def test_crypto_is_admitted(self):
        assert tt.bull_entry_ok(
            "divergence", "short", {"sym": "BTC", "noncrypto": False}, up=False)

    def test_the_stamp_can_only_reject_never_admit(self):
        """Restrict-only: a ticket claiming `noncrypto: False` on a symbol the
        local list screens must STILL be refused. Otherwise a stale or hostile
        payload could widen what the real-money book trades."""
        assert not tt.bull_entry_ok(
            "divergence", "short", {"sym": "AAPL", "noncrypto": False},
            up=False)


class TestTheDuplicatedConstantCannotDrift:
    def test_publisher_and_consumer_agree_on_the_crypto_class(self):
        """The scout must not import a consumer-side library to describe its
        own data, so the constant is duplicated — and pinned."""
        assert scout.CRYPTO_STRATEGY_INDEX == fleet_bus.CRYPTO_STRATEGY_INDEX
