"""Policy — every module that PUBLISHES MONEY ROWS must have a test surface.

Finding 9 (TEST_COVERAGE_ANALYSIS_2026-07-29.md), the born-dark pattern
applied to tests: Finding 7 found two RUNNING books (Index Rider,
Counterweight) publishing dashboard money with zero tests and no selftest —
nothing structural prevented that, so it would happen again with the next
bot. This test makes the class impossible to reintroduce silently:

    any *.py that calls bot_pnl_store's publish()/publish_paper_trade()
    must be (a) registered in SELFTEST_MODULES, or (b) imported by a file
    under tests/, or (c) DECLARED below with a reason. Silence is not an
    option.

The roster is derived by scanning the tree, never hand-maintained — a new
publishing bot is caught the day it ships, named in the failure.
"""
import re
from pathlib import Path

from tests.test_selftests import SELFTEST_MODULES

ROOT = Path(__file__).resolve().parent.parent

# Publish call sites that make a module part of the money surface.
_PUBLISH_RE = re.compile(
    r"(?:\bstore\.publish(?:_paper_trade)?\s*\(|\bbot_pnl_store\.publish(?:_paper_trade)?\s*\()")

# (c) Declared exceptions — module -> reason. RETIRED bots only: their code
# is kept for the ledger/history and idles behind LIGHTER-ONLY guards; a
# retired bot needs no regression net because it must never trade again.
# Resurrecting one (the *_OVERRIDE=run switches) means REMOVING it here and
# giving it tests — deliberately, in the same commit.
PUBLISH_TEST_OK = {
    "hyperliquid_momo_bot": "Trail Blazer — RETIRED 15-Jul, idles at boot",
    "hyperliquid_perps_bot": "Bounce Catcher — RETIRED, idles behind guard",
    "lighter_momentum_bot": "Stock Leaders — RETIRED 17-Jul (maxDD vs gate)",
    "listing_sniper": "Launch Sniper — RETIRED 17-Jul, idles behind guard",
}


def _publishing_modules():
    out = set()
    for py in ROOT.glob("*.py"):          # bots live at the repo root
        if py.name == "conftest.py":
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _PUBLISH_RE.search(text):
            out.add(py.stem)
    return out


def _modules_imported_by_tests():
    imported = set()
    imp = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
    for py in (ROOT / "tests").rglob("*.py"):
        try:
            imported.update(imp.findall(py.read_text(encoding="utf-8",
                                                     errors="ignore")))
        except OSError:
            continue
    return imported


def test_every_money_publisher_has_a_test_surface():
    publishers = _publishing_modules()
    # sanity: the scan itself must keep seeing the known surface — if the
    # publish API is ever renamed, this test must fail loudly rather than
    # silently start matching nothing
    assert "lighter_funding_bot" in publishers, "roster scan went blind"
    assert "bot_pnl_store" in publishers

    registered = set(SELFTEST_MODULES)
    tested = _modules_imported_by_tests()
    naked = sorted(
        m for m in publishers
        if m not in registered and m not in tested and m not in PUBLISH_TEST_OK)
    assert not naked, (
        "These modules publish MONEY ROWS but have no test surface — no "
        "registered selftest, no tests/ import, no declared exception "
        "(add tests, or declare in PUBLISH_TEST_OK with a reason):\n  "
        + "\n  ".join(naked))


def test_declared_exceptions_are_all_retired_and_real():
    publishers = _publishing_modules()
    for mod, reason in PUBLISH_TEST_OK.items():
        assert mod in publishers, (
            f"PUBLISH_TEST_OK lists {mod!r} which no longer publishes — "
            "stale declarations hide real gaps; remove it")
        assert "RETIRED" in reason, (
            f"{mod!r}: only RETIRED bots may skip the test net — a running "
            "book needs tests, not an exception")


def test_exceptions_do_not_shadow_registered_modules():
    # A module both registered AND declared would mean the declaration is
    # dead weight that survives a future de-registration unnoticed.
    both = set(PUBLISH_TEST_OK) & set(SELFTEST_MODULES)
    assert not both, f"declared AND registered (drop the declaration): {sorted(both)}"
