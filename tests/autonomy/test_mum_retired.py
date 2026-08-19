"""[2026-08-19] 👩 mum is RETIRED — the I17 no_rate call, row-scoped.

mum shares `lighter_family_bot` with 🙏 avo maria and 🔮 georgia, so the guard
must be ROW-scoped ((mo)): idling the process would silence two living books,
one of which is the fleet's nearest gate candidate. This pins that, and pins
that the retirement carries BOTH the dashboard and prune halves — doing one
hides your own omission.

The evidence it rests on: 3 closes lifetime, ALL opened 2026-07-12 so ZERO are
in-era against a 17-Jul era; ~2.4 closes/30d => ~12 months to the 30-close bar;
funding drag -$2.15 exceeds +$0.68 realised. It CORRECTS (nf)'s "green, slow"
hold, whose green was open MARKS not evidence (the (lo) precedent).
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_family_bot as fam  # noqa: E402


def test_mum_is_declared_retired_with_a_reversal_env():
    assert fam.RETIRED_BOOKS.get("freqtrade-mum") == "MUM_RETIRED_OVERRIDE"


def test_mum_is_not_in_the_live_roster():
    assert "freqtrade-mum" not in {s.bot for s in fam.live_strategies()}


def test_the_guard_is_ROW_scoped_and_the_living_books_survive():
    """The (mo) rule: mum shares a module with avo (the nearest gate
    candidate) and georgia. Retiring the ROW must not idle the process."""
    live = {s.bot for s in fam.live_strategies()}
    assert "freqtrade-avo-maria" in live, "avo must keep trading"
    assert "freqtrade-georgia" in live, "georgia must keep trading"
    assert live, "the process must still run books"


def test_the_override_brings_it_back_with_no_redeploy(monkeypatch):
    """Fail-OPEN on a set override — the standard reversal contract."""
    monkeypatch.setenv("MUM_RETIRED_OVERRIDE", "run")
    assert "freqtrade-mum" in {s.bot for s in fam.live_strategies()}


def test_both_halves_shipped():
    """A retirement needs the dashboard hide AND the prune. Doing one hides
    your own omission — CLAUDE.md says so in those words."""
    row = "freqtrade-mum-lshadow"
    assert row in (ROOT / "pnl_dashboard.py").read_text(), "RETIRED_ROWS half missing"
    assert row in (ROOT / "cleanup_legacy_bots.py").read_text(), "LEGACY_BOTS half missing"


def test_the_retirement_states_its_measured_reason():
    """A retirement with no number is the thing this fleet has paid for."""
    src = (ROOT / "lighter_family_bot.py").read_text()
    i = src.index('"freqtrade-mum":')
    window = src[max(0, i - 1400):i]
    assert "in-era" in window, "must say the closes are not in-era"
    assert "2.4 closes/30d" in window or "2.4 closes" in window
    assert "MUM_RETIRED_OVERRIDE" in src
