"""[2026-08-05 (ki)] A FUNDING-RANK BOOK MUST NOT RANK TOKENISED EQUITIES.

Lighter lists ~27 non-crypto perps beside its crypto books. A book that ranks
the venue by |TRUE apr| and takes the extremes will take them, because the
extremes of a funding cross-section are exactly where the odd instruments sit.

THE MEASUREMENT, on ⚖️ Counterweight's own ledger:
    CRYPTO legs      n=69   +0.227%/trade
    NON-CRYPTO legs  n=19   -9.209%/trade, t=-2.80, both halves negative, -$34.52
and the split survives a BLOCK permutation over close-minute groups at P=0.002
(legs close in batches, so the effective n is ~23, not 88).

THE LIVE INSTANCE the day this shipped: 🎸 band-barnes held 5 of 10 legs in
that population — a long-AAPL / short-AMD single-stock semiconductor pair, plus
PAXG (gold), US500 and US100 — inside a book whose whole thesis is funding
carry. Its xsect sleeve called `scout_universe(min_vol_m=1.0, limit=60)` with
NO validated core, where its parent starts from a 30-name crypto hand list and
only tops up. `(jg)` had reverted exactly that universe half on the parent ONE
DAY EARLIER, on a criterion pre-registered 30-Jul.
"""
import ast
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import fleet_bus  # noqa: E402


#: The exact legs 🎸 Barnesy held when this was found, so the test names the
#: incident rather than a synthetic case.
_BARNES_HELD = ["AAPL", "AMD", "PAXG", "PUMP", "SOL",
                "UNI", "US100", "US500", "XRP", "ZEC"]


class TestTheClassifier:
    def test_it_removes_exactly_the_legs_the_incident_named(self):
        keep = fleet_bus.crypto_only(_BARNES_HELD)
        assert keep == ["PUMP", "SOL", "UNI", "XRP", "ZEC"], keep
        assert set(_BARNES_HELD) - set(keep) == {
            "AAPL", "AMD", "PAXG", "US100", "US500"}

    def test_paxg_is_not_crypto(self):
        """Gold-backed: a metal price, not a funding signal. It is the one
        entry a reader is most likely to 'correct' back out."""
        assert not fleet_bus.is_crypto("PAXG")

    def test_an_unknown_symbol_is_crypto_fail_open(self):
        """The venue lists new crypto books constantly. A closed default would
        silently starve a book every time one appeared — a far worse failure
        than a genuinely new non-crypto listing slipping through until it is
        declared."""
        assert fleet_bus.is_crypto("SOMENEWCOIN")
        assert fleet_bus.is_crypto("")

    def test_it_never_raises_and_never_returns_none(self):
        """It runs inside a trading loop; a fault here must not stop a book."""
        for junk in (None, [], [None], ["BTC", None], [1, 2.5], "BTC"):
            out = fleet_bus.crypto_only(junk)
            assert out is not None and isinstance(out, list)

    def test_order_is_preserved(self):
        assert fleet_bus.crypto_only(["ZEC", "BTC", "SOL"]) == ["ZEC", "BTC", "SOL"]


class TestItIsOneOwnerNotAFifthList:
    """The fleet already had FOUR non-crypto lists and they had drifted. Two of
    them are deliberately NARROWER — `regime_oracle.NONCRYPTO` is 'books we
    have a regime for' and `lighter_family_bot.NONCRYPTO_UNIVERSE` is 'books
    the family may trade', which are different questions from 'is this crypto'.
    So this pins the SUPERSET relationship rather than collapsing them.
    """

    def test_it_covers_the_takers_list(self):
        from lighter_ticket_taker import TRADFI_BASES
        missing = TRADFI_BASES - fleet_bus.NONCRYPTO_BASES
        assert not missing, (
            f"the canonical set must cover the taker's: missing {sorted(missing)}")

    def test_it_covers_fleet_risks_list(self):
        from fleet_risk import EQUITY_BASES
        missing = EQUITY_BASES - fleet_bus.NONCRYPTO_BASES
        assert not missing, f"missing {sorted(missing)}"

    def test_it_covers_the_narrower_purpose_built_lists(self):
        from regime_oracle import NONCRYPTO
        missing = set(NONCRYPTO) - fleet_bus.NONCRYPTO_BASES
        assert not missing, f"missing {sorted(missing)}"


class TestTheConsumersAreWired:
    def _calls_crypto_only(self, mod):
        tree = ast.parse((_ROOT / f"{mod}.py").read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "crypto_only"):
                return True
        return False

    @pytest.mark.parametrize("mod", ["lighter_band_barnes_bot",
                                     "lighter_funding_spread_bot"])
    def test_the_funding_rank_books_filter(self, mod):
        """AST, not a substring scan — a grep matches the COMMENT that
        describes the defect, which is how this class hides."""
        assert self._calls_crypto_only(mod), \
            f"{mod} ranks the venue by funding and does not screen non-crypto"

    def test_both_images_carry_fleet_bus(self):
        """A filter the container does not have is a filter that does not run.
        Born-dark is this repo's most repeated shipping defect."""
        for df in ("Dockerfile.bandbarnes", "Dockerfile.fundspread"):
            assert "fleet_bus.py" in (_ROOT / df).read_text(), df


class TestTheParentsValidatedCoreIsNeverFiltered:
    """`resolve_universe`'s own contract: the configured names are the
    backtested core and are NEVER dropped, even when the scout ranks them
    below the cut. Only the scout's TOP-UP is screened.
    """

    def test_the_configured_core_survives_intact(self):
        import lighter_funding_spread_bot as m
        core = ["BTC", "ETH", "SPY", "XAU"]          # core containing non-crypto
        out = m.resolve_universe(core, 4, 1.0)
        assert out == ["BTC", "ETH", "SPY", "XAU"], (
            "a configured name must never be filtered — dropping it would "
            "silently change what the book IS")

    def test_the_guard_is_inert_at_todays_width(self):
        """Shipped as a REGRESSION guard, not a live change: after (jg) the
        core is 30 names and width is 30, so nothing tops up. Verified on the
        live book, which holds zero legs and reads universe 25."""
        import lighter_funding_spread_bot as m
        out = m.resolve_universe(m.COINS, 30, 1.0)
        assert out == [c.strip().upper() for c in m.COINS]
