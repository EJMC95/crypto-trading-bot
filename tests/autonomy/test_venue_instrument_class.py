"""[2026-08-06] THE VENUE CLASSIFIES ITS OWN INSTRUMENTS AND THE FLEET GUESSED.

`(ki)` shipped `fleet_bus.is_crypto()` on 5-Aug as the ONE owner of "is this
crypto", seeded from the widest hand list the fleet had (58 names). It declared
its own residual risk in the docstring — fail-OPEN, so "a genuinely new
non-crypto listing slips through until declared".

Measured the next morning against the venue's own `strategy_index`, on the same
`/api/v1/orderBookDetails` response the scout already fetches every cycle, that
list was wrong on **41 of 204 active books**:

    strategy_index=2 crypto (111) · 3 commodities (11) · 4 FX (9)
                   · 5 US equities (52) · 6 Asian equities (12) · 7 pre-IPO (9)

    missed: 5 FX crosses · 2 commodities · 16 US equities
          · 10 Asian equities · 8 pre-IPO names (incl. ANTHROPIC, OPENAI)

Six of the missed US tickers are BB, BE, WEN, BOT, CAP and QNT — which read as
crypto slang. **No human sweep catches those**, which is the whole argument for
reading the field instead of maintaining a list. Same shape as `(ki)`'s own
`created_at` finding and the `(gg)` fee basis: the venue knew all along.

WHAT THIS DOES NOT COVER, stated so nobody reads it as closed: the LIVE Ticket
Taker keeps a private `_is_crypto` over `TRADFI_BASES` gating real-money ticket
admission. It has the same leak. Changing what a real-money book trades is an
operator act, so it is reported, not shipped here.
"""
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import fleet_bus  # noqa: E402
import lighter_market_scout as scout  # noqa: E402


def _obd_row(sym, strategy_index, status="active"):
    """One `orderBookDetails` row in the venue's real shape."""
    return {"symbol": sym, "status": status, "strategy_index": strategy_index,
            "mark_price": "100.0", "index_price": "100.0",
            "daily_quote_token_volume": "5000000", "open_interest": "10",
            "last_trade_price": "100.0", "daily_price_high": "101.0",
            "daily_price_low": "99.0", "daily_price_change": "0.0",
            "created_at": "1737098461107",
            "taker_fee": "0.0000", "maker_fee": "0.0000"}


#: One book per class the venue actually uses, named from the live payload.
_VENUE = [_obd_row("BTC", 2), _obd_row("SOL", 2), _obd_row("PAXG", 2),
          _obd_row("XAU", 3), _obd_row("URA", 3),
          _obd_row("USDKRW", 4),
          _obd_row("SPY", 5), _obd_row("WEN", 5), _obd_row("BB", 5),
          _obd_row("TENCENT", 6), _obd_row("SKHYNIXUSD", 6),
          _obd_row("OPENAI", 7)]


@pytest.fixture
def published(monkeypatch):
    """The classifier read against a payload THE PUBLISHER BUILT.

    Doctrine, learned four times in one session: never hand-write a fixture
    that "looks like" the payload — that is how a consumer ends up reading a
    key its publisher does not emit, with a green test."""
    stats = scout.book_stats(_VENUE, min_qvol=0.0)
    snap = scout.build_snapshot(stats, {}, {}, {})
    now = datetime.now(timezone.utc)
    fleet_bus._cache["lighter-market"] = {
        "ts": now,
        "payload": dict(snap, updated=now.isoformat(timespec="seconds"),
                        ttl_sec=2700)}
    yield snap
    fleet_bus._cache.pop("lighter-market", None)


class TestThePublisherEmitsTheClass:
    def test_book_stats_carries_strategy_index(self):
        stats = scout.book_stats(_VENUE, min_qvol=0.0)
        assert stats["BTC"]["strategy_index"] == 2
        assert stats["TENCENT"]["strategy_index"] == 6

    def test_the_snapshot_publishes_classes(self, published):
        assert published["classes"]["BTC"] == 2
        assert published["classes"]["OPENAI"] == 7
        assert len(published["classes"]) == len(_VENUE)

    def test_index_zero_is_a_value_not_a_missing_field(self):
        """`or None` here would discard class 0. The venue uses it, and a
        symbol silently losing its class falls back to the hand list — the
        exact failure this replaces."""
        stats = scout.book_stats([_obd_row("WEIRD", 0)], min_qvol=0.0)
        assert stats["WEIRD"]["strategy_index"] == 0
        snap = scout.build_snapshot(stats, {}, {}, {})
        assert snap["classes"]["WEIRD"] == 0

    def test_a_missing_or_junk_index_is_absent_never_guessed(self):
        rows = [_obd_row("A", None), _obd_row("B", "nonsense"),
                _obd_row("C", True)]
        snap = scout.build_snapshot(scout.book_stats(rows, min_qvol=0.0),
                                    {}, {}, {})
        assert snap["classes"] == {}, "unknown class must be ABSENT, not 2"


class TestTheVenueOutranksTheHandList:
    @pytest.mark.parametrize("sym", ["WEN", "BB", "TENCENT", "SKHYNIXUSD",
                                     "OPENAI", "USDKRW", "URA"])
    def test_the_41_are_not_crypto(self, published, sym):
        assert not fleet_bus.is_crypto(sym)

    @pytest.mark.parametrize("sym", ["BTC", "SOL"])
    def test_real_crypto_still_reads_crypto(self, published, sym):
        assert fleet_bus.is_crypto(sym)

    def test_paxg_override_beats_the_venues_own_class(self, published):
        """The venue files PAXG under crypto (strategy_index=2) because it is
        a token. The fleet trades it as a metal price, and that judgement is
        DECLARED — it must survive the venue disagreeing with it, which is the
        one case a naive 'just read the field' rewrite gets wrong."""
        assert published["classes"]["PAXG"] == 2
        assert not fleet_bus.is_crypto("PAXG")


class TestTheFallbackIsNotStale:
    """An organ outage must not silently re-admit 41 equities to a
    funding-rank book, so the hand list is kept in sync rather than retired."""

    @pytest.mark.parametrize("sym", ["WEN", "BB", "CAP", "QNT", "BOT",
                                     "ANTHROPIC", "SAMSUNGUSD", "NZDUSD"])
    def test_dark_scout_still_screens_them(self, sym):
        fleet_bus._cache.pop("lighter-market", None)
        assert not fleet_bus.is_crypto(sym), (
            f"{sym} re-admitted when the scout is dark — the fallback list "
            "has drifted from the venue field again")

    def test_a_stale_payload_falls_back_rather_than_trusting_itself(self):
        """I1: liveness before semantics. A frozen `classes` map and a live one
        are byte-identical."""
        old = datetime.now(timezone.utc) - timedelta(days=3)
        fleet_bus._cache["lighter-market"] = {
            "ts": datetime.now(timezone.utc),
            "payload": {"classes": {"BTC": 5},           # frozen nonsense
                        "updated": old.isoformat(timespec="seconds"),
                        "ttl_sec": 2700}}
        try:
            assert fleet_bus.is_crypto("BTC"), "stale class must not be trusted"
        finally:
            fleet_bus._cache.pop("lighter-market", None)


class TestTheFailOpenContractSurvives:
    def test_an_unlisted_symbol_is_still_crypto(self, published):
        """The venue lists new crypto books constantly; a closed default would
        starve a book every time one appeared."""
        assert fleet_bus.is_crypto("SOMENEWCOIN")

    def test_it_never_raises(self, published):
        for junk in (None, "", 1, 2.5, object()):
            assert isinstance(fleet_bus.is_crypto(junk), bool)
        for junk in (None, [], [None], ["BTC", None], "BTC"):
            out = fleet_bus.crypto_only(junk)
            assert out is not None and isinstance(out, list)

    def test_crypto_only_uses_the_venue_class(self, published):
        held = ["BTC", "WEN", "SOL", "TENCENT", "PAXG"]
        assert fleet_bus.crypto_only(held) == ["BTC", "SOL"]


class TestTheLiveTakerLeakIsDeclaredNotForgotten:
    """The remaining copy, pinned so it cannot be quietly assumed fixed. When
    the operator decides the live arm should screen too, this test is what
    tells the next reader the decision was made deliberately."""

    def test_the_takers_private_list_is_still_the_narrower_one(self):
        from lighter_ticket_taker import TRADFI_BASES
        leak = fleet_bus.NONCRYPTO_BASES - TRADFI_BASES
        assert leak, (
            "the taker's list now covers the canonical set — if that was "
            "deliberate, retire this test and say so in the CHANGELOG")
