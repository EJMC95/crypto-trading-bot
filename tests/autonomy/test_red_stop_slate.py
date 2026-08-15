"""[(nf), 15-Aug] THE RED-STOP SLATE — seven row retirements + one sleeve
wind-down, made in ONE operator act on the decision docket's own verdicts
(every retired book read horizon=unreachable or I17-undecidable; asks open
since 6-Aug). These tests pin each mechanism BEHAVIOURALLY and pin what must
NOT have been swept in: the green books stay alive, and both halves of every
row retirement shipped together.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_family_bot as fam                     # noqa: E402
from parliament import PM_BOTS, PM_RETIRED, live_pm_bots  # noqa: E402


FAMILY_RETIRED = {"crypto-intraday-15m", "crypto-swing-daily", "freqtrade-dad"}
PM_GONE = {"pm-gillard", "pm-abbott", "pm-rudd", "pm-morrison"}


def test_family_slate_books_are_out_and_greens_stay(monkeypatch):
    for env in fam.RETIRED_BOOKS.values():
        monkeypatch.delenv(env, raising=False)
    live = {s.bot for s in fam.live_strategies()}
    assert not (FAMILY_RETIRED & live), live
    # the too-broad mutation: retiring three books must not silence the rest
    for keep in ("freqtrade-mum", "freqtrade-avo-maria", "freqtrade-georgia"):
        assert keep in live, f"{keep} must stay alive — the (mr) row-scope rule"


def test_family_overrides_resurrect_each_book(monkeypatch):
    for book in FAMILY_RETIRED:
        monkeypatch.setenv(fam.RETIRED_BOOKS[book], "run")
    live = {s.bot for s in fam.live_strategies()}
    assert FAMILY_RETIRED <= live, (
        "an operator who says `run` gets the book back with no redeploy")


def test_pm_slate_books_are_out_and_greens_stay(monkeypatch):
    for env in PM_RETIRED.values():
        monkeypatch.delenv(env, raising=False)
    live = set(live_pm_bots())
    assert not (PM_GONE & live), live
    assert {"pm-albanese", "pm-turnbull"} <= live, (
        "the positive/undecidable books must stay accruing")


def test_pm_override_resurrects(monkeypatch):
    monkeypatch.setenv("PM_GILLARD_RETIRED_OVERRIDE", "run")
    assert "pm-gillard" in live_pm_bots()


def test_parliament_builder_goes_through_the_derivation():
    """A builder reading PM_BOTS raw would re-alive all four retired books —
    the retired-in-one-layer-alive-in-another failure (mo). AST on the real
    builder: build_bots must call live_pm_bots and must not iterate
    PM_BOTS.items()."""
    import ast
    src = (ROOT / "parliament" / "strategies.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "build_bots")
    dump = ast.dump(fn)
    assert "live_pm_bots" in dump
    assert "PM_BOTS" not in dump, "build_bots must not read PM_BOTS raw"


def test_xsect_retirement_rebalances_to_flat():
    """The wind-down mechanism, behaviourally: with the sleeve retired the
    target set is EMPTY, which is what makes the close-loop close every leg
    and the open-loop a no-op. Source-level pin on the gate expression plus
    the constant's default."""
    import lighter_band_barnes_bot as bb
    assert bb.XSECT_RETIRED is True, (
        "default is retired; BARNES_XSECT_RETIRED_OVERRIDE=run reverses")
    import ast
    src = (ROOT / "lighter_band_barnes_bot.py").read_text()
    # the gate must feed the SAME variables the want-dict is built from
    assert "(([], []) if XSECT_RETIRED" in src, (
        "the retired sleeve must rebalance to FLAT (empty targets), not "
        "freeze entries while stale legs bleed")


def test_xsect_retirement_is_published():
    src = (ROOT / "lighter_band_barnes_bot.py").read_text()
    assert 'sleeves[s]["retired"] = XSECT_RETIRED' in src, (
        "(ly): a retirement is PUBLISHED beside the sleeve's numbers, "
        "never inferred from open:0")


def test_both_halves_of_every_row_retirement_shipped():
    """The standing rule: RETIRED_ROWS hides, LEGACY_BOTS prunes — doing one
    hides your own omission."""
    import pnl_dashboard
    import cleanup_legacy_bots
    rows = {b + "-lshadow" for b in FAMILY_RETIRED | PM_GONE}
    missing_hide = rows - set(pnl_dashboard.RETIRED_ROWS)
    missing_prune = rows - set(cleanup_legacy_bots.LEGACY_BOTS)
    assert not missing_hide, f"not hidden: {missing_hide}"
    assert not missing_prune, f"not pruned: {missing_prune}"
