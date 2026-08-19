"""[2026-08-19] Rule 4's rolling sample must honour the ledger quarantine.

MEASURED LIVE, and it is why this exists: after the seed-path fix landed,
🧘 douglas published `closed 7 / realized -0.12` beside
`sample20 {n: 9, sum_usd: -26.60}` — the dashboard card and the book's OWN
discipline instrument disagreeing by exactly the two (nm)/(pv) void rows, in
the SAME payload. The card was fixed; the sample was still counting rows the
fleet had ruled inadmissible, because `recent` carried only {pnl, r} and
`is_quarantined` keys on (bot, pair, closed_at) — it literally could not be
asked.

The fix stamps the identifying fields so the ONE owner can answer, and filters
at load. It does NOT add a second copy of the rule.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_book_douglas_bot as dg  # noqa: E402


def _pos(sl=0.01, notional=100.0):
    return {"notional": notional, "sl_frac": sl, "opened_ts": 0.0}


def test_a_recent_entry_is_stamped_so_the_quarantine_can_reach_it():
    e = dg.recent_entry("ROBO", _pos(), -1.0)
    assert e["pair"] == "ROBO"
    assert e["closed_at"], "an unstamped row is unfalsifiable"
    # and the numbers it always carried are unchanged
    assert e["pnl"] == -1.0 and e["r"] == -1.0


def test_the_two_void_rows_are_withheld_from_the_sample():
    """ROBO and LINK on 2026-08-15 are the (nm)/(pv) quarantined pair."""
    recent = [
        dg.recent_entry("ROBO", _pos(), -23.16, "2026-08-15T13:35:41+00:00"),
        dg.recent_entry("LINK", _pos(), -3.31, "2026-08-15T13:35:41+00:00"),
        dg.recent_entry("BTC", _pos(), +1.50, "2026-08-17T09:00:00+00:00"),
    ]
    out = dg.admissible_recent("book-douglas-lshadow", recent)
    assert [e["pair"] for e in out] == ["BTC"], out
    assert dg.sample20(out)["n"] == 1


def test_a_row_outside_the_declared_window_survives():
    """The quarantine is a bounded window, not a pair-wide ban — a later ROBO
    trade on the FIXED build is the book's record."""
    recent = [dg.recent_entry("ROBO", _pos(), -1.0, "2026-08-17T09:00:00+00:00")]
    assert len(dg.admissible_recent("book-douglas-lshadow", recent)) == 1


def test_unstamped_legacy_rows_are_KEPT_not_guessed_at():
    """Fail-OPEN, the same contract is_quarantined uses. A quarantine that
    swallows rows it cannot classify silently shrinks every sample it touches —
    the disease, not the cure. They age out of the 20-row window instead."""
    legacy = [{"pnl": -23.16, "r": -3.29}, {"pnl": -3.31, "r": -3.73}]
    assert len(dg.admissible_recent("book-douglas-lshadow", legacy)) == 2


def test_is_quarantined_stays_the_one_owner():
    """(hj): a second copy of a rule is a second rule."""
    import ast
    src = (ROOT / "lighter_book_douglas_bot.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "admissible_recent")
    names = {a.attr for a in ast.walk(fn) if isinstance(a, ast.Attribute)}
    assert "is_quarantined" in names, sorted(names)


def test_a_broken_quarantine_lookup_admits_rather_than_drops(monkeypatch):
    """Never let the withholding pass break the sample it refines."""
    monkeypatch.setattr(dg.store, "is_quarantined",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    recent = [dg.recent_entry("ROBO", _pos(), -1.0, "2026-08-15T13:35:41+00:00")]
    assert len(dg.admissible_recent("book-douglas-lshadow", recent)) == 1


def test_the_sample_is_still_reporting_only():
    """The entry path must not read the sample — the book's structural
    consistency pin. Stamping fields must not have changed that."""
    import inspect
    sig = inspect.signature(dg._open_position)
    assert "recent" not in sig.parameters and "sample" not in sig.parameters


def test_sample20_names_how_many_rows_it_could_not_classify():
    """[2026-08-19 follow-through on (rk)] The fail-OPEN choice leaves a ~4-day
    window in which sample20 visibly disagrees with the card (n=9/−$26.60
    beside closed 7/−$0.12, live). The disagreement must carry its own
    explanation: `unstamped` counts the rows the quarantine cannot be asked
    about, and it is ALWAYS present — an omitted key is byte-identical between
    "all stamped" and "not computed" ((lv))."""
    legacy = [{"pnl": -23.16, "r": -3.29}, {"pnl": -3.31, "r": -3.73}]
    stamped = [dg.recent_entry("ROBO", _pos(), 1.0, "2026-08-17T09:00:00+00:00")]
    assert dg.sample20(legacy + stamped)["unstamped"] == 2
    assert dg.sample20(stamped)["unstamped"] == 0
    assert dg.sample20([])["unstamped"] == 0
