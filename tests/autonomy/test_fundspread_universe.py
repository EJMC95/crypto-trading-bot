"""⚖️ Counterweight's cross-section width — the 30 -> 40 widening (2026-08-27).

WHY THIS FILE EXISTS. `FUNDSPREAD_UNIVERSE_N` spent three weeks at a value that
did NOTHING. The book's configured core is 30 names and `resolve_universe` tops
up only while `len(out) < width`, so at width 30 the scout's contribution is
empty on the first pass — the live row published `universe_n: 30` beside
`universe: 25` for the whole period. A knob that cannot move is indistinguishable
from a knob set correctly, which is the (lv) `{open: 0}` ambiguity wearing a
lever's clothes.

So the NEGATIVE CONTROL is the point of this file, not a decoration:
`test_width_30_adds_nothing_and_width_40_adds_names` asserts BOTH ends. A test
that passes at width 30 AND width 40 proves nothing about this change — it would
have been just as green on the day the knob was inert.

The other three classes pinned here are the ones that make the widening free:

  * THE (ki) CRYPTO SCREEN ON THE TOP-UP. (jg) reverted the last widening
    (60 -> 30) because the wide set pulled in NON-CRYPTO books whose funding
    dispersion is ~9x crypto's — and its evidence window IS the non-crypto
    window. That confound is closed IN CODE, so the screen is now load-bearing
    in a way it was not while the widening was inert: it is the entire reason
    (jg)'s measurement does not apply to this one. Driven against the REAL
    `fleet_bus.crypto_only`, never a stub of it (a stub would encode the
    assumption under test).

  * THE CONFIGURED CORE IS NEVER DROPPED. Those 30 names are what both
    validations ranked; losing one silently changes what the book IS.

  * K AND GROSS ARE UNTOUCHED. Gross exposure is `2 * K * clip`, and the whole
    I19 claim for this widening is that it changes WHICH names fill the same ten
    slots and nothing else. If resolving a wider universe moved K or the clip,
    the widening would cost expectancy and the claim would be false.
"""
import ast
import pathlib

import pytest

import fleet_bus
import fleet_tuning
import lighter_funding_spread_bot as spread

pytestmark = pytest.mark.autonomy

_SRC = pathlib.Path(spread.__file__).read_text()
_TREE = ast.parse(_SRC)

#: The ten crypto names the scout top-up admits at width 40 (measured
#: 2026-08-27). Five of them — FARTCOIN, GRAM, UNI, ZEC, ZRO — were held SHORT
#: by 🌾 carry at the widening; that overlap is declared in
#: `audit_book_overlap.KNOWN_CELL_COLLISIONS` and pinned below.
ADDED = ["FARTCOIN", "GRAM", "HBAR", "LIT", "PUMP", "TAO", "TRUMP", "UNI",
         "ZEC", "ZRO"]


def _env_default(env_key):
    """The LITERAL default of `os.environ.get("<env_key>", <literal>)` in the
    bot's own source, found by AST.

    Read from the tree rather than from the imported global on purpose: an
    exported `FUNDSPREAD_UNIVERSE_N` in the test runner's environment would make
    a check on the global vacuous, and this is the value that ACTUALLY ships in
    the container. `audit_lever_bounds`'s drift arm reads the same literal.
    """
    for node in ast.walk(_TREE):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == "get"
                and isinstance(f.value, ast.Attribute) and f.value.attr == "environ"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        if node.args[0].value != env_key or len(node.args) < 2:
            continue
        return ast.literal_eval(node.args[1])
    raise AssertionError(f"no os.environ.get({env_key!r}, <literal>) in the bot")


class _Bus:
    """A stand-in for the SCOUT only. `crypto_only`/`is_crypto` are delegated to
    the REAL `fleet_bus`, because the class screen is the property under test and
    stubbing it would certify whatever the stub believes ((hj))."""

    def __init__(self, syms):
        self.syms = list(syms)
        self.seen_min_vol = None

    def scout_universe(self, min_vol_m=0.0, current_time=None):
        self.seen_min_vol = min_vol_m
        return list(self.syms)

    crypto_only = staticmethod(fleet_bus.crypto_only)
    is_crypto = staticmethod(fleet_bus.is_crypto)


@pytest.fixture
def bus(monkeypatch):
    def _make(syms):
        b = _Bus(syms)
        monkeypatch.setattr(spread, "fleet_bus", b)
        return b
    return _make


@pytest.fixture
def core():
    """The book's own configured core, read from the module (30 names)."""
    names = list(spread.COINS)
    assert len(names) == 30, (
        f"the core is {len(names)} names, not 30 — every width claim in this "
        "file is relative to that number, so re-derive them before editing it")
    return names


# ---------------------------------------------------------------------------
# 1. The shipped width.
# ---------------------------------------------------------------------------

def test_the_code_default_width_is_40():
    """30 was INERT: the core is 30 names, so the top-up added zero. 31 is the
    first width that does anything at all; 40 is the shipped one."""
    assert _env_default("FUNDSPREAD_UNIVERSE_N") == "40"


def test_the_autorevert_snapshot_carries_the_new_default():
    """`_ENV_DEFAULTS` is what `apply_tuning` hands `get_lever` as the fallback,
    so an expired/absent/quarantined lever reverts to THIS number. If it still
    said 30 the growth rail would silently un-ship the widening on the first
    lever expiry — the (fz) one-way-ratchet defect, mirrored."""
    assert spread._ENV_DEFAULTS["UNIVERSE_N"] == 40


def test_the_drift_arm_is_still_pointed_at_this_lever():
    """The registry-vs-code check is `audit_lever_bounds`'s job and is NOT
    re-implemented here — a second copy of a rule is a second rule ((hj)), and
    two guards printing different reds for one missing edit is how a real
    finding gets ignored.

    What this pins instead is that the drift arm can still SEE this lever: the
    routing names the bot and the env var, and the lever is not carved out into
    `DRIFT_OK`. An entry in that set is a HOLE in the guard ((hl), where the one
    exempted lever was the one that had actually drifted) — so a future session
    silencing the drift red by exemption rather than by syncing the number
    reddens here instead."""
    import sys
    sys.path.insert(0, str(pathlib.Path(spread.__file__).parent / "scripts"))
    import audit_lever_bounds as alb

    ent = alb.CONSUMERS.get("fundspread.universe_n")
    assert ent == ("lighter_funding_spread_bot.py", "FUNDSPREAD_UNIVERSE_N"), (
        f"the drift arm no longer routes this lever to this bot: {ent}")
    assert "fundspread.universe_n" not in alb.DRIFT_OK, (
        "fundspread.universe_n was exempted from the drift arm — an entry in "
        "DRIFT_OK is a hole in the guard, and the registry/code sync is the "
        "whole safety of a lever whose default just moved")
    # And the arm can actually READ this bot's literal — a renamed variable
    # would make it report "consumer default not found" rather than drift.
    assert alb._literal_env_default(*ent) == _env_default("FUNDSPREAD_UNIVERSE_N")


def test_the_shipped_width_is_inside_its_cage():
    spec = fleet_tuning.LEVERS["fundspread.universe_n"]
    code = int(_env_default("FUNDSPREAD_UNIVERSE_N"))
    assert spec["lo"] <= code <= spec["hi"]


# ---------------------------------------------------------------------------
# 2. THE NEGATIVE CONTROL — both ends, or the test proves nothing.
# ---------------------------------------------------------------------------

def test_width_30_adds_nothing_and_width_40_adds_names(bus, core):
    """THE control. At the OLD width the identical scout list contributes ZERO
    (that is what made the knob inert); at the NEW width it contributes. A test
    asserting only the second half would have been green on the inert config."""
    b = bus(ADDED)

    inert = spread.resolve_universe(core, 30, spread.UNIVERSE_MIN_VOL_M)
    assert inert == core, (
        "width 30 must add NOTHING — that is the inert config this widening "
        "replaces, and the whole reason a one-ended test proves nothing")

    wide = spread.resolve_universe(core, 40, spread.UNIVERSE_MIN_VOL_M)
    assert wide[:30] == core, "the core stays first and in order"
    assert wide[30:] == ADDED, f"expected the 10 measured names, got {wide[30:]}"
    assert len(wide) == 40


def test_31_is_the_first_width_that_admits_anything(bus, core):
    """The boundary, stated as a fact about the core's length rather than a
    magic number: below/at 30 nothing, at 31 exactly one."""
    b = bus(ADDED)
    assert spread.resolve_universe(core, 29, 1.0) == core
    assert spread.resolve_universe(core, 30, 1.0) == core
    assert spread.resolve_universe(core, 31, 1.0) == core + ADDED[:1]


def test_a_dark_scout_leaves_the_widened_book_at_its_core(bus, core):
    """The widening is an ENHANCEMENT, never a dependency — an organ outage may
    not shrink a book below its validated list."""
    bus([])
    assert spread.resolve_universe(core, 40, 1.0) == core


# ---------------------------------------------------------------------------
# 3. The (ki) crypto screen — load-bearing NOW that the top-up is reachable.
# ---------------------------------------------------------------------------

def test_the_top_up_refuses_non_crypto(bus, core):
    """(jg) reverted 60 -> 30 on a population measured at -9.209%/trade over a
    window that IS the non-crypto window. This screen is why that measurement
    does not transfer to the 30 -> 40 move: the population is unreachable.

    Driven through the REAL `fleet_bus.crypto_only`, so a change to the venue's
    own classification reaches this assertion with no edit here."""
    noncrypto = ["QQQ", "SPY", "WTI"]
    for s in noncrypto:                       # the premise, checked not assumed
        assert fleet_bus.is_crypto(s) is False, f"{s} is classed crypto"

    bus(noncrypto[:1] + ADDED[:2] + noncrypto[1:])
    out = spread.resolve_universe(core, 40, 1.0)
    added = out[30:]
    assert added == ADDED[:2], f"non-crypto reached the book: {added}"
    for s in noncrypto:
        assert s not in out


def test_a_screen_fault_fails_OPEN_and_never_shrinks_the_book(bus, core, monkeypatch):
    """Fail-open is deliberate and stated at the site itself (`# fail-open: a
    filter fault must not shrink the book`). It costs the SCREEN, not the core.

    [MUTATION ROUND, 2026-08-27] The first version of this test asserted only
    `out[:30] == core`, and the mutation that replaces the fail-open `pass`
    with `return out` — i.e. fail-CLOSED — **SURVIVED it**. The core is intact
    under both behaviours, so that assertion could not tell them apart, and
    the test's own name claimed a property it did not check. The stake is not
    cosmetic: fail-closed makes the entire 30 -> 40 widening evaporate on any
    classifier fault and puts this knob straight back into the
    structurally-inert state this change exists to end — silently, which is
    exactly how it went unnoticed for three weeks the first time.

    So the test now asserts what fail-OPEN actually MEANS: the top-up still
    happens, and the UNSCREENED list is what tops it up.
    """
    assert fleet_bus.is_crypto("QQQ") is False, "premise: QQQ is not crypto"
    mixed = [ADDED[0], "QQQ", ADDED[1]]

    # THE CONTROL, first: with the screen healthy the non-crypto name is
    # refused. Without it the fault-path assertion below would say nothing
    # about the screen — it would be true of a book that never screened at all.
    bus(mixed)
    healthy = spread.resolve_universe(core, 40, 1.0)
    assert healthy[30:] == ADDED[:2], healthy[30:]

    b = bus(mixed)

    def boom(_syms):
        raise RuntimeError("classifier down")
    monkeypatch.setattr(b, "crypto_only", boom, raising=False)

    out = spread.resolve_universe(core, 40, 1.0)
    assert out[:30] == core, "a screen fault must never drop the validated core"
    # AND the widening still RUNS. A fault that quietly returns the book to its
    # configured 30 is fail-CLOSED wearing fail-open's comment.
    assert out[30:], (
        "a screen fault took the book back to its core — that is fail-CLOSED, "
        "and it makes the whole widening inert on a classifier outage")
    # The declared PRICE of failing open, asserted rather than assumed: the
    # unscreened list is what tops up, so the name the healthy screen refused
    # does reach the book. Fail-open is not free, and this is the cost.
    assert out[30:] == mixed, out[30:]


def test_the_volume_floor_reaches_the_scout(bus, core):
    """`UNIVERSE_MIN_VOL_M` is the I18 gate BEHIND this one — a bare literal with
    no registry entry. Pin that it is at least still plumbed through, so a future
    session registering it has a live consumer to point at."""
    b = bus(ADDED)
    spread.resolve_universe(core, 40, spread.UNIVERSE_MIN_VOL_M)
    assert b.seen_min_vol == spread.UNIVERSE_MIN_VOL_M


# ---------------------------------------------------------------------------
# 4. The core survives, and the widening costs no exposure.
# ---------------------------------------------------------------------------

def test_the_core_is_never_dropped_even_when_the_scout_outranks_it(bus, core):
    """The contract the function states: configured names are the backtested
    list and are kept even when the scout ranks them below the cut. A width
    BELOW the core must not truncate it."""
    bus(ADDED)
    assert spread.resolve_universe(core, 5, 1.0) == core
    assert spread.resolve_universe(core, 0, 1.0) == core
    for width in (30, 31, 36, 40, 90):
        out = spread.resolve_universe(core, width, 1.0)
        assert out[:30] == core, f"core mangled at width {width}"


def test_the_widening_moves_no_exposure_term(bus, core):
    """Gross is `2 * K * clip`. The I19 claim is that this widening changes only
    WHICH names fill the same ten slots, so resolving a wider universe must move
    neither term — measured here by driving the real function and comparing the
    gross arithmetic across both widths."""
    bus(ADDED)
    k0, clip0 = spread.K, spread.ORDER_USD
    gross = lambda: 2 * spread.K * spread.ORDER_USD          # noqa: E731

    before = gross()
    spread.resolve_universe(core, 30, 1.0)
    assert gross() == before
    spread.resolve_universe(core, 40, 1.0)
    assert gross() == before, "the widening moved gross exposure"
    assert (spread.K, spread.ORDER_USD) == (k0, clip0)
    assert 2 * spread.K == 10, "K=5 per side => the same 10 legs at both widths"


def test_K_stays_at_the_validated_plateau_centre():
    """K=5 is what BOTH validations cleared and the measured optimum AT the
    widened universe (carry/noise: K=3 0.02463, K=5 0.02791, K=8 0.02680,
    K=12 0.02012). The un-backtested K=8 is the (jg) cautionary tale."""
    assert _env_default("FUNDSPREAD_K") == "5"
    assert fleet_tuning.LEVERS["fundspread.k"]["env_default"] == 5


# ---------------------------------------------------------------------------
# 5. I20 — the overlap the widening creates is DECLARED.
# ---------------------------------------------------------------------------

def _abo():
    import sys
    sys.path.insert(0, str(pathlib.Path(spread.__file__).parent / "scripts"))
    import audit_book_overlap as abo
    return abo


OVERLAP_KEY = frozenset({"perps-funding-carry-lshadow",
                         "perps-funding-spread-lshadow"})


def test_the_carry_overlap_is_declared_with_a_measurement_and_an_owner():
    """Five of the ten admitted names were held SHORT by 🌾 carry at the
    widening, on the same side. `audit_book_overlap` can never GROUP these two
    (⚖️ publishes no `enter_apr` — it ranks, it does not threshold), so the
    declaration is the only place the overlap is written down at all."""
    abo = _abo()
    why = abo.KNOWN_CELL_COLLISIONS.get(OVERLAP_KEY)
    assert why, "the rank/harvest overlap must be declared, not silent"
    assert "OWNER" in why, "a declaration is a decision: it needs an owner"
    assert "%" in why, "and the measurement that motivated it"
    for b in OVERLAP_KEY:
        assert b in abo.FUNDING_BOOKS, f"{b} left the roster; the key guards nothing"


def test_the_shared_set_is_DATA_and_matches_what_the_widening_admits():
    """A mutation round killed the first version of this test: dropping a coin
    from the SHARED clause left a `coin in why` check green, because the same
    ticker also appears in the ADMITTED clause two sentences earlier. A
    page-wide substring scan is not a structural claim — so the two sets are
    module constants now, the prose interpolates them, and this asserts the
    sets."""
    abo = _abo()
    assert tuple(abo.FUNDSPREAD_TOPUP_ADMITS) == tuple(ADDED), (
        "the declared top-up set drifted from the 10 names measured at the "
        f"widening: {abo.FUNDSPREAD_TOPUP_ADMITS}")
    shared = tuple(abo.FUNDSPREAD_CARRY_SHARED)
    assert shared == ("FARTCOIN", "GRAM", "UNI", "ZEC", "ZRO"), shared
    assert set(shared) < set(abo.FUNDSPREAD_TOPUP_ADMITS), (
        "every shared name must be one this widening actually admits — a "
        "shared coin outside the top-up is a different overlap, not this one")


def test_the_declaration_prose_cannot_drift_from_the_sets():
    """The sentence is built FROM the constants, so a set edited without the
    prose (or the reverse) is unrepresentable rather than merely unlikely."""
    abo = _abo()
    why = abo.KNOWN_CELL_COLLISIONS[OVERLAP_KEY]
    assert ", ".join(abo.FUNDSPREAD_TOPUP_ADMITS) in why
    assert ", ".join(abo.FUNDSPREAD_CARRY_SHARED) in why
    assert f"{len(abo.FUNDSPREAD_CARRY_SHARED)} were held SHORT" in why
