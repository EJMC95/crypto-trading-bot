"""The allocation clamp is ONE number doing a per-BOOK job — publish the bound.

[2026-08-28 (vd)] Carried item `allocation-clamp-is-a-per-position-bound-doing-
per-book-duty`. Its own note names the session half: *"derive the per-book bound
the drawdown bar implies (the `GROSS_X_MAX = 0.15/|stop|` shape (sr) used on
avo) and publish it beside the claim, so the ceiling stops being a single number
shared by books with different stops."* This is that.

WHY IT MATTERS AT ALL: **maxDD is the only go-live bar that is NOT
clip-invariant.** (hl) measured per-trade % invariance for the other five, so
scaling a book moves its drawdown against a fixed 15% bar while leaving `mean`,
`t` and the halves untouched. One shared ceiling therefore means different real
risk on every book.

REPORTED, NEVER A BAR (I15): moving the clamp moves money between books and is
an operator call (I16). Publishing the number makes that call arithmetic
instead of a shared constant.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fleet_allocation as fa                              # noqa: E402


def test_the_bar_is_imported_from_the_grader_not_retyped():
    """A retyped bar drifts. Five constants drifted in this repo in one day."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_gl", ROOT / "scripts" / "golive_readiness.py")
    gl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gl)
    assert fa._golive_max_dd() == pytest.approx(float(gl.GOLIVE_MAX_DD))


@pytest.mark.parametrize("bot,stop,scale", [
    # These three reproduce (sr)'s own published numbers from the STOPS, which
    # is the point: derived, not copied. test_variant_host pins the same values
    # independently, so the two must agree or one of them is wrong.
    ("freqtrade-mum-lighter", 0.04, 3.75),
    ("freqtrade-avo-maria-lighter", 0.10, 1.50),
    ("freqtrade-georgia-lighter", 0.05, 3.00),
])
def test_the_bound_is_the_gate_bar_over_the_books_own_stop(bot, stop, scale):
    d = fa.dd_bound(bot)
    assert d is not None, f"{bot} has a known stop and must get a bound"
    assert d["stop"] == pytest.approx(stop)
    assert d["max_scale"] == pytest.approx(scale, rel=1e-3)
    assert d["max_scale"] == pytest.approx(d["bar"] / d["stop"], rel=1e-3)


def test_an_unknown_book_gets_no_bound_never_a_permissive_default():
    """THE FAIL-SAFE DIRECTION. A missing bound that reads as 'no limit' is the
    same defect this whole item is about, pointed the other way."""
    for bot in ("NEVER_SEEN", "", "freqtrade-nobody-lighter"):
        assert fa.dd_bound(bot) is None


def test_no_stop_by_design_is_distinguishable_from_unknown():
    """⚖️ Counterweight carries no per-leg stop by design (replay fidelity with
    its validated parent), so its bar-breach point comes from REALISED
    drawdown. Both cases refuse a bound; only the declaration says which is
    which, and a reader who cannot tell them apart will treat a gap as a
    design choice."""
    d = fa.dd_bound("perps-funding-spread-lshadow")
    assert d is not None and d["max_scale"] is None
    assert "by design" in d["why"]
    assert fa.dd_bound("NEVER_SEEN") is None


def test_the_shared_ceiling_exceeds_the_tightest_book():
    """The item's whole claim, as a number: one clamp, many stops."""
    bounds = [fa.dd_bound(b) for b in
              ("freqtrade-mum-lighter", "freqtrade-avo-maria-lighter",
               "freqtrade-georgia-lighter")]
    scales = [d["max_scale"] for d in bounds if d and d["max_scale"]]
    assert len(scales) == 3
    assert min(scales) < max(scales), (
        "if every book had the same bound the item would be moot")
    ceil = getattr(fa, "SCALE_CEIL", 4.0)
    assert ceil > min(scales), (
        f"the shared ceiling {ceil} must exceed the tightest book's "
        f"{min(scales)} — that gap IS the finding")


# ------------------------------------------------- the born-dark correction
def test_the_bound_reads_no_bot_module(monkeypatch):
    """[28-Aug] THE REGRESSION ARM FOR A GUARD-CAUGHT DEFECT.

    The first cut imported each book's module to read its stop constant — no
    drift, but `fleet_allocation` runs in the freqtrade image, which does NOT
    COPY `lighter_family_bot`. In production every family lookup would have
    failed inside its own try/except and every family book would silently have
    got no bound: the born-dark class (17-Jul brain_stats postmortem).

    Worse, `audit_image_imports` could only see the STATIC import. The dynamic
    `importlib.import_module` calls for the other books were invisible to it,
    so that half would have shipped born-dark with NOTHING reporting it.

    A retyped constant a guard CAN check beats an import it cannot.
    """
    src = (ROOT / "fleet_allocation.py").read_text()
    for mod in ("lighter_family_bot", "lighter_funding_bot",
                "lighter_band_kelly_bot", "lighter_nav_cook_bot"):
        assert f"import {mod}" not in src, (
            f"fleet_allocation imports {mod} — born-dark in the freqtrade image")


def test_the_books_own_publication_beats_the_bridge():
    """`fleet_manifest.design_for`'s pattern: a book that declares itself is
    authoritative, and its bridge entry goes quiet on its own."""
    live = fa.dd_bound("freqtrade-mum-lighter")
    assert live["stop"] == pytest.approx(0.04)          # from the bridge
    own = fa.dd_bound("freqtrade-mum-lighter", {"policy": {"stoploss": -0.02}})
    assert own["stop"] == pytest.approx(0.02)           # her own word wins
    assert own["max_scale"] == pytest.approx(7.5)


@pytest.mark.parametrize("payload", [
    {"policy": {"stoploss": "junk"}}, {"policy": {"stoploss": None}},
    {"policy": {"stoploss": 0}}, {"policy": "not-a-dict"}, {}, None,
])
def test_a_junk_payload_falls_back_rather_than_inventing(payload):
    d = fa.dd_bound("freqtrade-mum-lighter", payload)
    assert d is not None and d["stop"] == pytest.approx(0.04)
