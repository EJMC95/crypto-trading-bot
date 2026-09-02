"""[2026-09-02 (xa)] THE PER-CARRIER NON-CRYPTO EXCLUSION — the mirror of the
(vd) extension, and it must fail in the same directions.

WHY IT EXISTS. Eamon, 2-Sep: *"How do we fix mum"* / *"if it makes any bot make
more money then implement."* 👩 mum's one measured weak spot on the day he asked
is her graded NON-CRYPTO sleeve: live arm 7 closes at −0.383%/trade (t −1.67,
upper bound −0.052%), shadow twin 7 at −0.540% (t −2.38), five of seven
`max_hold` losers on BOTH arms — against a crypto sleeve of +0.600% / +0.614%
on the same two arms. Seven is below `fleet_allocation.MIN_N`, so the CUT is
pre-registered (`scripts/study_mum_noncrypto_sleeve_2026-09-02.py`), not
applied — and this mechanism is what makes acting on that read ONE ENV rather
than a build, the day it passes.

THE THREE THINGS THIS FILE EXISTS TO STOP, each a defect the sibling
`noncrypto_extra` already paid for once:

  1. A CUT THAT RE-AIMS ANOTHER BOOK. (vd) widened the SHARED
     `NONCRYPTO_UNIVERSE` and silently took 🙏 avo — a LIVE real-money arm —
     from 25 names to 45. The exclusion is per-carrier for exactly that reason,
     and an unnamed carrier must be untouched.
  2. A CUT THAT REACHES THE CRYPTO HALF. mum's crypto sleeve is the book
     (+0.600%/trade, t=2.18). The subtraction applies to the non-crypto half
     ONLY; if a symbol somehow appeared in both, the crypto entry survives.
  3. A CUT THAT SPLITS THE ARM FROM ITS CONTROL. `carrier_universe` is ONE
     OWNER, BOTH HOSTS — the live variant host imports it. A universe rule that
     moved the live arm and not its shadow twin would break the very control
     the judge's paired bar depends on.

Plus the inertness pin: shipped default is `""`, so this changes NOTHING until
it is deliberately set. Mutations that turn these red: make the exclusion apply
to `crypto`; drop the per-carrier scoping; have the live host build its own
universe inline; make the default non-empty.
"""
import ast
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import lighter_family_bot as fam    # noqa: E402

pytestmark = pytest.mark.autonomy

MUM = "freqtrade-mum"
AVO = "freqtrade-avo-maria"


def _s(bot):
    for s in fam.STRATEGIES:
        if s.bot == bot:
            return s
    raise AssertionError(f"{bot} not in STRATEGIES")


# ------------------------------------------------------------------ inertness
def test_the_shipped_default_is_empty_so_nothing_moves_until_it_is_set():
    """A mechanism that ships already-cutting is a cut nobody approved."""
    assert fam.FAMILY_NONCRYPTO_EXCLUDE == "", fam.FAMILY_NONCRYPTO_EXCLUDE
    for bot in (MUM, AVO):
        assert fam.noncrypto_exclude(bot) == []


def test_the_universe_is_byte_identical_under_the_default(monkeypatch):
    before = {s.bot: list(fam.carrier_universe(s)) for s in fam.STRATEGIES}
    monkeypatch.setattr(fam, "FAMILY_NONCRYPTO_EXCLUDE", "")
    after = {s.bot: list(fam.carrier_universe(s)) for s in fam.STRATEGIES}
    assert before == after


# -------------------------------------------------------------- it does cut
def test_a_named_carrier_loses_exactly_the_named_noncrypto_symbols(monkeypatch):
    mum = _s(MUM)
    base = fam.carrier_universe(mum)
    cut = [c for c in ("XAU", "QQQ", "SPY", "XCU") if c in base]
    assert len(cut) == 4, f"the sleeve under test is not in her universe: {cut}"
    monkeypatch.setattr(fam, "FAMILY_NONCRYPTO_EXCLUDE", f"{MUM}:{','.join(cut)}")
    after = fam.carrier_universe(mum)
    assert set(cut).isdisjoint(after), [c for c in cut if c in after]
    assert set(after) == set(base) - set(cut), "the cut removed something it did not name"


# ------------------------------------------------------- it cannot reach crypto
def test_the_exclusion_can_never_drop_a_crypto_name(monkeypatch):
    """The crypto half is the book. Naming a crypto symbol must be a no-op —
    driven on a symbol that IS in her crypto list, not asserted from the source."""
    mum = _s(MUM)
    base = fam.carrier_universe(mum)
    crypto_names = [c for c in fam.COINS if c in base]
    assert crypto_names, "no crypto names in her universe — fixture is wrong"
    monkeypatch.setattr(fam, "FAMILY_NONCRYPTO_EXCLUDE",
                        f"{MUM}:{','.join(crypto_names)}")
    after = fam.carrier_universe(mum)
    for c in crypto_names:
        assert c in after, f"the exclusion reached the crypto half and dropped {c}"
    assert list(after) == list(base), "a crypto-only exclusion must be a no-op"


def test_a_symbol_in_both_halves_keeps_its_crypto_entry(monkeypatch):
    """Belt and braces: if the venue ever filed a name into both lists, the
    subtraction is scoped to the non-crypto half and the crypto entry lives."""
    mum = _s(MUM)
    monkeypatch.setattr(fam, "NONCRYPTO_UNIVERSE", ["BTC", "SPY"])
    monkeypatch.setattr(fam, "FAMILY_NONCRYPTO_EXCLUDE", f"{MUM}:BTC,SPY")
    after = fam.carrier_universe(mum)
    assert "BTC" in after, "BTC is in COINS — the crypto half must survive"
    assert "SPY" not in after


# ------------------------------------------------------------ per-carrier scope
def test_an_unnamed_carrier_is_untouched(monkeypatch):
    """(vd)'s lesson, in the other direction: a cut for one book must not
    re-aim another — 🙏 avo is LIVE REAL MONEY."""
    avo, mum = _s(AVO), _s(MUM)
    avo_before = list(fam.carrier_universe(avo))
    monkeypatch.setattr(fam, "FAMILY_NONCRYPTO_EXCLUDE", f"{MUM}:XAU,QQQ,SPY,XCU")
    assert list(fam.carrier_universe(avo)) == avo_before
    assert "XAU" not in fam.carrier_universe(mum)


@pytest.mark.parametrize("raw,bot,want", [
    ("", MUM, []),
    (f"{MUM}:XAU", MUM, ["XAU"]),
    (f"{MUM}:XAU", AVO, []),
    (f"{MUM}: xau , qqq ", MUM, ["XAU", "QQQ"]),          # whitespace + case
    (f"{AVO}:SPY;{MUM}:XAU", MUM, ["XAU"]),                # multi-group
    (f"{MUM}:", MUM, []),                                  # empty group
    ("garbage", MUM, []),
    (f"{MUM}-lshadow:XAU", MUM, []),                       # a PREFIX is not a match
    (None, MUM, []),
])
def test_the_parser_never_guesses(raw, bot, want):
    assert fam.noncrypto_exclude(bot, raw) == want


def test_the_parser_matches_its_sibling_on_scoping(monkeypatch):
    """`noncrypto_extra` and `noncrypto_exclude` split the same `bot:a,b;bot:c`
    grammar. They may differ in CASE handling (exclude normalises so a lowercase
    env still bites; extra feeds symbols straight to the venue), but they must
    never disagree about WHICH CARRIER a group belongs to — that is the
    property (vd) bought with a live book."""
    raw = f"{AVO}:SPY;{MUM}:XAU"
    assert fam.noncrypto_extra(MUM, raw) == ["XAU"]
    assert fam.noncrypto_exclude(MUM, raw) == ["XAU"]
    assert fam.noncrypto_extra(AVO, raw) == ["SPY"]
    assert fam.noncrypto_exclude(AVO, raw) == ["SPY"]
    assert fam.noncrypto_extra("nobody", raw) == []
    assert fam.noncrypto_exclude("nobody", raw) == []


def test_the_exclusion_is_case_insensitive_where_the_universe_is_not(monkeypatch):
    """A lowercase env must still cut — the symbols in the universe are upper."""
    mum = _s(MUM)
    monkeypatch.setattr(fam, "FAMILY_NONCRYPTO_EXCLUDE", f"{MUM}:xau")
    assert "XAU" not in fam.carrier_universe(mum)


# --------------------------------------------------------------- both hosts
def test_the_live_host_reads_the_same_universe_owner():
    """👩 mum's LIVE arm and her SHADOW twin must see one universe rule. The
    live variant host must IMPORT carrier_universe, never rebuild it inline —
    a divergence here silently breaks the judge's control arm."""
    src = open(os.path.join(ROOT, "lighter_avo_live_bot.py")).read()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("lighter_family_bot"):
            imported |= {a.name for a in node.names}
    assert "carrier_universe" in imported, \
        "the live host must import the ONE universe owner"
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "carrier_universe"]
    assert calls, "the live host imports carrier_universe but never calls it"
    # and it must not REBUILD the universe from the raw lists beside it.
    # AST, not a substring scan: that exact phrase appears in a COMMENT in this
    # file (the (sr) scan-order note), and a page-wide grep would fail on the
    # sentence describing the defect rather than on the defect — the repo's own
    # "a page-wide substring scan is not a structural claim" rule.
    def _names(node):
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            nm = _names(node)
            assert not ({"COINS", "NONCRYPTO_UNIVERSE"} <= nm), (
                "the live host composes its own universe again — a second copy "
                f"of the rule at line {getattr(node, 'lineno', '?')}")


def test_the_subtraction_lives_in_the_one_owner():
    """The cut must be inside `carrier_universe`, so every host inherits it."""
    src = open(os.path.join(ROOT, "lighter_family_bot.py")).read()
    body = src.split("def carrier_universe(", 1)[1].split("\ndef ", 1)[0]
    assert "noncrypto_exclude(" in body, \
        "the exclusion is not applied in carrier_universe — a host could miss it"
    crypto_line = [ln for ln in body.splitlines() if "return crypto" in ln]
    assert crypto_line and "drop" not in crypto_line[0], \
        "the return must hand back the crypto half unfiltered"
