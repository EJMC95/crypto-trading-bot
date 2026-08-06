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
          _obd_row("OPENAI", 7),
          # A listing NO hand list has ever heard of. This one row is what
          # separates "reads the venue" from "reads a list that happens to
          # agree" — see TestTheVenueIsActuallyRead.
          _obd_row("NEWLISTINGCO", 5)]


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


class TestTheVenueIsActuallyRead:
    """MUTATION-DRIVEN. The first cut of this file passed with `is_crypto`
    ignoring the venue entirely — because all 41 missed names were synced into
    `NONCRYPTO_BASES`, so every symbol under test gave the SAME answer by
    either route. The list-only mutant survived, which means the venue-read
    path — the entire point of the change — was untested.

    The separating case is the one the change exists for: a listing the hand
    list has never heard of. List-only fails OPEN and ranks it as crypto; the
    venue says equity.
    """

    def test_a_brand_new_listing_screens_with_no_code_change(self, published):
        assert "NEWLISTINGCO" not in fleet_bus.NONCRYPTO_BASES, \
            "the separating case stops separating if it is added to the list"
        assert published["classes"]["NEWLISTINGCO"] == 5
        assert not fleet_bus.is_crypto("NEWLISTINGCO"), (
            "the venue's own class must outrank the hand list — otherwise "
            "this is still a hand list and rots at the same rate")

    def test_and_the_same_symbol_reads_crypto_when_the_scout_is_dark(self):
        """The other half of the same fact: the fallback genuinely IS a
        fallback, so this symbol's verdict depends on the venue read."""
        fleet_bus._cache.pop("lighter-market", None)
        assert fleet_bus.is_crypto("NEWLISTINGCO")


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


class TestTheTakersOwnListCannotDriftAgain:
    """[2026-08-06 (kq)] `(kj)` left this leak OPEN and declared it, because
    changing what a real-money book trades is an operator act. Then it was
    measured on the live bus and it was not theoretical:

        3 of 16 scout tickets were non-crypto instruments TRADFI_BASES did not
        catch — DRAM, CXMT and **CAP** — and CAP was on the `divergence` lens.

    The live arm is divergence-SHORT only, runs `bull: True`, and
    ("divergence","short") is in BULL_LENS_SIDES — so every live real-money
    entry passes `bull_entry_ok` -> `_is_crypto`, and that screen was the only
    thing between the real-money book and a short on a tokenised equity.

    The list stays LOCAL by design (importing fleet_bus would drag a
    dependency into the lean live image — the born-dark trap the taker's own
    comment names), so the two are pinned EQUAL here instead of shared. This
    replaces `(kj)`'s "the leak is declared, not forgotten" test, which existed
    to fail exactly when the leak was closed.
    """

    def test_the_taker_screens_everything_the_canonical_set_does(self):
        from lighter_ticket_taker import TRADFI_BASES
        missing = fleet_bus.NONCRYPTO_BASES - TRADFI_BASES
        assert not missing, (
            f"the LIVE taker would admit {sorted(missing)} — its crypto screen "
            f"is the only gate between the real-money book and a tokenised "
            f"equity short. Add them to TT_TRADFI_BASES' default.")

    def test_and_the_canonical_set_covers_the_takers(self):
        """Both directions: the two lists are EQUAL, so neither can drift."""
        from lighter_ticket_taker import TRADFI_BASES
        extra = TRADFI_BASES - fleet_bus.NONCRYPTO_BASES
        assert not extra, f"canonical set missing {sorted(extra)}"

    def test_the_three_symbols_the_incident_named(self):
        """Names the incident rather than a synthetic case."""
        from lighter_ticket_taker import _is_crypto
        for sym in ("CAP", "DRAM", "CXMT"):
            assert not _is_crypto(sym), sym
        for sym in ("BTC", "SOL", "ZRO"):
            assert _is_crypto(sym), sym


class TestPairShapedSymbolsAreScreened:
    """[2026-08-06 (kv)] MEASURED, not hypothetical. `is_crypto` compared the
    WHOLE string against the base set, so every ledger-shaped `BASE/QUOTE`
    pair fell through fail-open as "crypto".

    It was used to audit 🎫 the live Taker's ledger for non-crypto positions
    and returned ZERO. The real count is 19 all-time (−$1.97) and 5 in-era
    short-divergence — DRAM, MINIMAX, SKHY, last opened 4-Aug — which is over
    a THIRD of the in-era sample the go-live gate grades on the book nearest
    real money. `paper_trades.pair` is ALWAYS `BASE/QUOTE`, so the audit could
    never have detected the damage it was run to find.

    `lighter_ticket_taker._is_crypto` has split on "/" since it was written.
    The canonical owner did not, which is why the fleet's own screen and the
    fleet's own audit disagreed for a day.
    """

    @pytest.mark.parametrize("pair", [
        "SKHY/USDC", "DRAM/USDC", "MINIMAX/USDC", "AAPL/USDC",
        "TSLA/USDC", "SPCX/USDC", "USDKRW/USDC",
    ])
    def test_a_pair_shaped_noncrypto_symbol_is_screened(self, pair):
        assert not fleet_bus.is_crypto(pair), pair

    @pytest.mark.parametrize("pair", ["BTC/USDC", "SOL/USDC", "ZRO/USDC"])
    def test_a_pair_shaped_crypto_symbol_survives(self, pair):
        assert fleet_bus.is_crypto(pair), pair

    def test_crypto_only_filters_pairs_too(self):
        held = ["BTC/USDC", "SKHY/USDC", "SOL/USDC", "DRAM/USDC"]
        assert fleet_bus.crypto_only(held) == ["BTC/USDC", "SOL/USDC"]

    def test_it_agrees_with_the_takers_own_screen_on_pairs(self):
        """The two implementations must not disagree again — that disagreement
        is what let a day pass with a wrong audit."""
        from lighter_ticket_taker import _is_crypto
        for p in ("SKHY/USDC", "DRAM/USDC", "BTC/USDC", "SOL/USDC",
                  "AAPL/USDC", "ZRO/USDC", "NEWCOIN/USDC"):
            assert fleet_bus.is_crypto(p) == _is_crypto(p), p
