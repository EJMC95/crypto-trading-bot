"""[2026-08-17 (ph)] THE CLASS SCREEN IS PART OF THE GATE — and this file is
the first test `audit_book_overlap.py` has ever had.

CLAUDE.md names it as I20's enforcement (`report_supply`, `admits`), and
`audit_doctrine_enforcement` only checks that the reference RESOLVES — which is
exactly the caveat at the top of that file: *"a green run verifies that a
declared enforcement EXISTS, not that it is CORRECT."* It existed and was
untested.

THE DEFECT, measured on the live tape before fixing, at
`--gate 0.20 --allow-noncrypto`:

    supply: 14 coins deep — MU, SAMSUNGUSD, SKHY, QQQ … mostly NON-crypto
    "LIVING BOOKS WHOSE GATE ALREADY ADMITS THIS SUPPLY:"
        band-barnes-lshadow · book-kiyosaki-lshadow · perps-funding-carry-lshadow

All three screen crypto-only `(lk)`/`(lv)` and can reach **3** of those 14. The
verdict quoted 14. That is the phantom-rival class the apr ceiling `(mh)` and
the volume ceiling `(gl)` were both added to prevent, arriving on the third
axis — and I20's own corollary is that a detector which overstates is one the
operator learns to ignore.

`(pf)` supplied the missing input (🌾 carry and 🎸 Barnes now publish
`caps.crypto_only`); this is the consumer half.
"""
import importlib.util
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "audit_book_overlap.py"
spec = importlib.util.spec_from_file_location("audit_book_overlap", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


#: The live supply the defect was found on: 3 crypto + 11 non-crypto.
MIXED = ["KAITO", "XMR", "PAXG", "MU", "SAMSUNGUSD", "SKHY", "QQQ",
         "SPCX", "WTI", "XAU", "US500", "US100", "AAPL", "AMD"]
CRYPTO = {"KAITO", "XMR", "PAXG"}


def _is_crypto(c):
    return c in CRYPTO


class TestClassReach:
    def test_a_crypto_only_book_reaches_only_the_crypto_part(self):
        n, note = mod.class_reach({"crypto_only": True}, MIXED, _is_crypto)
        assert n == 3, "the three books reach 3 of 14, not 14"
        assert "reaches 3 of 14" in note

    def test_an_unscreened_book_reaches_all_of_it(self):
        n, note = mod.class_reach({"crypto_only": False}, MIXED, _is_crypto)
        assert n == len(MIXED) and note == ""

    def test_an_unpublished_screen_is_UNKNOWN_and_says_so(self):
        """Three-valued, like every other bound in this file. An unpublished
        screen may neither manufacture a finding (by shrinking reach) nor erase
        one (by silently claiming full reach with no label)."""
        n, note = mod.class_reach({}, MIXED, _is_crypto)
        assert n == len(MIXED), "unknown must not shrink the reach"
        assert "UNPUBLISHED" in note, "…but it must be visible that it is unknown"
        assert mod.class_reach({"crypto_only": None}, MIXED, _is_crypto) == (n, note)

    def test_a_pure_crypto_supply_produces_NO_annotation(self):
        """At a crypto-only gate every coin is crypto, so a crypto-only book
        reaches all of it. Annotating there would be noise on every line — the
        cry-wolf direction this fix exists to reduce."""
        pure = ["KAITO", "XMR", "PAXG"]
        for g in ({"crypto_only": True}, {"crypto_only": False}, {}):
            n, note = mod.class_reach(g, pure, _is_crypto)
            assert (n, note) == (3, ""), g

    def test_an_all_noncrypto_supply_leaves_a_screened_book_at_zero(self):
        n, note = mod.class_reach({"crypto_only": True}, ["MU", "QQQ"], _is_crypto)
        assert n == 0 and "reaches 0 of 2" in note


class _Cur:
    """Minimal stand-in for the psycopg2 cursor `living_gates` uses. It reads
    exactly one query shape — `(bot, extra)` rows — so the stub encodes the
    ROW SHAPE and nothing about the semantics under test."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_a, **_k):
        return None

    def fetchall(self):
        return self._rows


class TestTheDeclarationIsNormalised:
    """A book publishes `crypto_only` as JSON, so it can arrive as anything.
    Only a real bool may be believed — anything else is UNKNOWN, never a
    silent "not screened". Caught by a surviving mutation: dropping the
    `isinstance` check let a malformed value fall through `class_reach`'s
    `is True` test into the unscreened branch WITHOUT the UNPUBLISHED label,
    which is the one outcome that is wrong in both directions."""

    def _gate(self, caps):
        cur = _Cur([("perps-funding-carry-lshadow",
                     {"caps": dict({"enter_apr": 0.2, "min_vol": 2e6}, **caps)})])
        return mod.living_gates(cur)["perps-funding-carry-lshadow"]

    def test_a_real_bool_is_believed(self):
        assert self._gate({"crypto_only": True})["crypto_only"] is True
        assert self._gate({"crypto_only": False})["crypto_only"] is False

    @pytest.mark.parametrize("bad", ["true", "yes", 1, 0, "", None, [], {}])
    def test_anything_else_is_UNKNOWN(self, bad):
        g = self._gate({"crypto_only": bad})
        assert g["crypto_only"] is None, f"{bad!r} must not be believed"
        # …and it must then be LABELLED, not silently treated as unscreened
        assert "UNPUBLISHED" in mod.class_reach(g, MIXED, _is_crypto)[1]

    def test_an_absent_key_is_UNKNOWN(self):
        assert self._gate({})["crypto_only"] is None


class TestTheGateItself:
    """`admits` had no test either. These pin the bounds the phantom-rival
    findings were built on, so the class cannot regress on the other axes."""

    BASE = {"enter_apr": 0.05, "min_vol": 2e6, "max_vol": 10e6,
            "vol_known": True}

    def test_a_stricter_apr_bar_is_not_a_rival(self):
        g = dict(self.BASE, enter_apr=0.20)
        assert mod.admits(g, 0.05, 2e6) == "no"

    def test_supply_above_an_apr_CEILING_is_not_a_rival(self):
        """[(mh)] 🧮 Hull's band is half-open at 20%."""
        g = dict(self.BASE, apr_hi=0.20)
        assert mod.admits(g, 0.20, 2e6) == "no"
        assert mod.admits(g, 0.10, 2e6) == "yes"

    def test_supply_above_a_volume_CEILING_is_not_a_rival(self):
        """[(gl)] the unpublished-ceiling incident: 🛢️ Garrett read as a rival
        for supply its own band excludes."""
        assert mod.admits(self.BASE, 0.05, 20e6) == "no"

    def test_an_unpublished_volume_bound_is_unknown_not_yes(self):
        g = {"enter_apr": 0.05, "vol_known": False}
        assert mod.admits(g, 0.05, 2e6) == "unknown"


class TestArmPairsAreNotTwoBooks:
    """The XAU ×2 'REAL MONEY IN THE STACK' false positive: 💸 the Farmer's
    live row and its own control twin are SUPPOSED to hold the same coin."""

    def test_the_farmers_two_arms_are_one_book(self):
        assert mod.same_book(["perps-funding-lighter-lighter",
                              "perps-funding-lighter-lshadow"])

    def test_two_genuinely_different_books_are_not(self):
        assert not mod.same_book(["perps-funding-lighter-lshadow",
                                  "perps-funding-spread-lshadow"])

    def test_one_holder_is_not_an_overlap_at_all(self):
        assert not mod.same_book(["perps-funding-lighter-lighter"])

    def test_a_third_book_joining_an_arm_pair_is_still_a_finding(self):
        """The exclusion must be a SUBSET test, not "any arm present" — LINK is
        live today across the Farmer shadow, ⚖️ Counterweight and 🛢️ Garrett,
        and that is real concentration."""
        assert not mod.same_book(["perps-funding-lighter-lighter",
                                  "perps-funding-lighter-lshadow",
                                  "band-garrett-lshadow"])
