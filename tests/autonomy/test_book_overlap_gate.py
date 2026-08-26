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


class TestCellCollisions:
    """[(pl)] I20's check, run off the books' own published gates instead of a
    cell a human had to type. It was a manual command nobody ran — which is how
    THREE books ended up on a cell that holds at most two coins at once."""

    CARRY = {"enter_apr": 0.20, "min_vol": 2e6, "max_vol": None,
             "crypto_only": True, "vol_known": True}
    FARMER = {"enter_apr": 0.05, "min_vol": 10e6, "max_vol": None,
              "crypto_only": False, "vol_known": True}
    GARRETT = {"enter_apr": 0.05, "min_vol": 1e5, "max_vol": 2e6,
               "crypto_only": False, "vol_known": True}
    HULL = {"enter_apr": 0.0782, "apr_hi": 0.20, "min_vol": 2e6,
            "max_vol": 10e6, "crypto_only": True, "vol_known": True}

    def test_identical_gates_collide(self):
        assert mod.cells_collide(self.CARRY, dict(self.CARRY))

    def test_a_volume_TIER_separates_two_books(self):
        """🛢️ Garrett [0.1M,2M) vs 🧮 Hull [2M,10M) — the tiling that is
        supposed to keep them apart."""
        assert not mod.cells_collide(self.GARRETT, self.HULL)

    def test_an_apr_BAND_separates_two_books(self):
        """🧮 Hull's ceiling is half-open at 20%, which is exactly where the
        carry cohort starts."""
        assert not mod.cells_collide(self.HULL, self.CARRY)

    def test_three_books_on_one_cell_are_ONE_finding(self):
        gates = {"a": self.CARRY, "b": dict(self.CARRY), "c": dict(self.CARRY)}
        found = mod.collisions(gates)
        assert found == [frozenset({"a", "b", "c"})], found

    def test_an_EMPTY_intersection_is_not_a_collision(self):
        """THE DEFECT THE FIRST RUN EXPOSED. Carry (`apr>=20%, vol>=$2M`) and
        💸 the Farmer (`apr>=5%, vol>=$10M`) DO intersect on paper — at
        `apr>=20%, vol>=$10M` — so the transitive closure fused two genuinely
        different tiers into one blob. That region has **zero** supply and
        always has: `(ly)` measured *"no crypto book has ever cleared the $10M
        floor at the 20% bar — observed max $5.53M, KAITO"*, and this run
        reproduced it at 0 snapshots / 0 coins over 9,693.
        """
        gates = {"carry": self.CARRY, "farmer": self.FARMER}
        assert mod.collisions(gates) == [frozenset({"carry", "farmer"})], \
            "set-theoretically they DO overlap — that is the trap"
        empty = lambda _region: False          # noqa: E731 — the measured answer
        assert mod.collisions(gates, has_supply=empty) == []

    def test_a_populated_intersection_still_collides(self):
        """The mirror: materiality must not become a blanket excuse that
        silences every finding."""
        gates = {"a": self.CARRY, "b": dict(self.CARRY)}
        full = lambda _region: True            # noqa: E731
        assert mod.collisions(gates, has_supply=full) == [frozenset({"a", "b"})]

    def test_the_intersection_takes_the_STRICTER_class_screen(self):
        r = mod.intersect(self.CARRY, self.FARMER)
        assert r[0] == 0.20 and r[2] == 10e6, r
        assert r[4] is True, "a crypto-only book cannot contend for non-crypto"

    def test_the_live_carry_cell_is_DECLARED_with_a_reason_and_an_owner(self):
        """TWO books since `(pm)` retired 🎸 band-barnes — it was three when
        this guard shipped. The group is the dict KEY, so a retirement that
        forgets to update it leaves the live pair matching nothing and the
        run reporting UNDECLARED: the declaration has to track the fleet."""
        key = frozenset({"perps-funding-carry-lshadow", "book-kiyosaki-lshadow"})
        why = mod.KNOWN_CELL_COLLISIONS.get(key)
        assert why, "the live carry cell must be declared, not silent"
        assert "OWNER" in why and "%" in why, \
            "a declaration is a decision: it needs an owner and the measurement"

    def test_no_declaration_names_a_book_that_left_the_roster(self):
        """A group naming a retired book can never match the live gates again,
        so it guards nothing while looking like it does."""
        for grp in mod.KNOWN_CELL_COLLISIONS:
            stale = grp - set(mod.FUNDING_BOOKS)
            assert not stale, f"declaration names non-living book(s): {stale}"

    def test_every_declaration_names_real_books(self):
        """A stale entry naming a retired book silently stops guarding."""
        for grp in mod.KNOWN_CELL_COLLISIONS:
            for b in grp:
                assert b in mod.FUNDING_BOOKS, f"{b} is not a living funding book"


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


class TestAConditionalFloorIsNotTheFloorItPublishes:
    """[(sk)] 🌾 carry's turnover floor became a FAST PATH rather than a
    verdict: below it, a coin is admitted on MEASURED book depth and payback.
    So `caps.min_vol` keeps reading $1M while the book's real reach extends
    underneath it — and this guard, whose whole job is "who else can take this
    supply?", would UNDERSTATE the one book whose reach just grew.

    That is the `(gl)` phantom-rival class inverted, and the inverted direction
    is the worse one: a phantom rival is noise the operator learns to ignore,
    but a rival that is REAL and INVISIBLE is a sibling silently starved, with
    an UNDECLARED collision never failing the run that should have caught it.
    """

    def _gate(self, caps):
        cur = _Cur([("perps-funding-carry-lshadow",
                     {"caps": dict({"enter_apr": 0.2, "min_vol": 1e6}, **caps)})])
        return mod.living_gates(cur)["perps-funding-carry-lshadow"]

    def test_a_depth_admitting_book_reaches_below_its_published_floor(self):
        g = self._gate({"depth_admit": True})
        assert g["min_vol"] == 0.0, (
            "the published floor is still being read as the real one — a "
            "sub-floor rival would be invisible to the collision check")
        assert g["min_vol_published"] == 1e6, (
            "the published floor must be KEPT, not overwritten: it is what "
            "the operator reads to understand where the escape starts")

    def test_a_book_without_the_escape_keeps_its_floor(self):
        """The control group. If this arm fired on every book it would make
        every funding book a rival for every other, which is a detector that
        flags everything."""
        assert self._gate({})["min_vol"] == 1e6
        assert self._gate({"depth_admit": False})["min_vol"] == 1e6

    @pytest.mark.parametrize("bad", ["true", "yes", 1, 0, "", None, [], {}])
    def test_only_a_REAL_bool_widens_the_reach(self, bad):
        """Same three-valued discipline as `crypto_only`: this arm WIDENS a
        book's claimed reach, so a malformed value must not trigger it — an
        unpublished escape may not manufacture a collision."""
        g = self._gate({"depth_admit": bad})
        assert g["depth_admit"] is None, f"{bad!r} must not be believed"
        assert g["min_vol"] == 1e6, f"{bad!r} widened the reach"

    def test_the_widened_floor_is_still_marked_as_a_volume_bound(self):
        """`vol_known` gates the (gl) unpublished-ceiling rule. A book whose
        floor became conditional still PUBLISHES a volume bound, so it must
        not fall back into the UNKNOWN branch and stop being compared."""
        assert self._gate({"depth_admit": True})["vol_known"] is True

    def test_the_printed_line_says_depth_not_a_bare_zero(self):
        """I8. Printed bare, a 0.00M floor reads as 'this book has no floor',
        which is a different and much less useful fact than 'this book's floor
        is conditional'."""
        import inspect
        src = inspect.getsource(mod)
        assert 'else f"{(mn or 0) / 1e6:.2f}M"' in src and '"depth"' in src, (
            "the per-book line does not distinguish a depth escape from an "
            "absent floor")
