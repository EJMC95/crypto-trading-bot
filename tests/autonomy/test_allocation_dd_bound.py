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


# ------------------------------------------- phantom closes out of the claim
def test_the_allocation_organ_excludes_phantom_closes():
    """[28-Aug (vd)] THE THIRD GRADER FINALLY AGREES WITH THE OTHER TWO.

    A $0.00 close with no entry price is a halt/flatten EVENT, not a trade.
    `golive_readiness` has excluded them since (th) and the winners' docket
    since 26-Aug; THIS organ — the one that ranks CAPITAL — did not.

    Measured on the live ledger the day this shipped: 13 phantom rows on
    exactly the two real-money books (🙏 avo 9, 🔮 georgia 4). Avo's published
    claim was **+0.194%/trade on n=15**; her true traded n is **6**, below this
    organ's own MIN_N floor, so the honest claim is NONE. Phantoms lift a
    losing book's mean toward zero AND raise n (shrinking SE), so they inflate
    the lower bound from both directions — on the books most likely to have
    them, since only real money halts.
    """
    src = (ROOT / "fleet_allocation.py").read_text()
    assert "from golive_readiness import is_phantom_close" in src, (
        "the organ must use the GATE'S signature, not its own copy")
    tree = __import__("ast").parse(src)
    called = any(
        isinstance(n, __import__("ast").Call)
        and getattr(n.func, "id", None) == "is_phantom_close"
        for n in __import__("ast").walk(tree))
    assert called, "is_phantom_close imported but never applied"


def test_the_phantom_signature_has_one_owner():
    """Identity, not a lookalike — two copies would let the graders drift
    apart on exactly the rows that matter ((hj))."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_gl2", ROOT / "scripts" / "golive_readiness.py")
    gl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gl)
    assert gl.is_phantom_close({"profit_abs": 0.0, "open_rate": None}) is True
    assert gl.is_phantom_close({"profit_abs": -3.87, "open_rate": 0.31}) is False


def test_build_populates_the_bound_on_every_record():
    """DRIVE `build()`, not just `dd_bound()`. The first cut read `rec["bot"]`
    while the records are KEYED by bot, so the payload published `dd_bound:
    null` on every book while the unit test stayed green — a defect only the
    real publisher could show ([[test-consumers-against-publisher-built-payloads]])."""
    # The REAL input shape: {bot: [per-trade pct, ...]}. My first fixture
    # passed record dicts and blew up inside `sample_stats` — the
    # stub-encodes-the-assumption trap, caught by running it.
    pcts = [0.004, -0.002, 0.006, 0.001, -0.003,
            0.002, 0.005, -0.001, 0.003, 0.002, 0.004, -0.002]
    alloc = {"freqtrade-mum-lighter": list(pcts), "NEVER_SEEN": list(pcts)}
    out = fa.build(alloc)
    assert out is not None
    books = out["books"]
    assert "dd_bound" in books["freqtrade-mum-lighter"], "field never written"
    assert books["freqtrade-mum-lighter"]["dd_bound"]["max_scale"] == pytest.approx(3.75)
    assert books["NEVER_SEEN"]["dd_bound"] is None


# ------------------------------------------- the import must RESOLVE, not exist
def _clean_run(body):
    """Run `body` in a CLEAN interpreter from the repo root.

    THE WHOLE POINT: pytest puts `scripts/` on sys.path, so every in-process
    assertion about `from golive_readiness import ...` is answered by the test
    harness rather than by the code. The container has no such help.
    """
    import subprocess
    return subprocess.run([sys.executable, "-c", body], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=180)


def test_the_phantom_import_resolves_in_a_clean_interpreter():
    """[2026-08-28 (vd)] THE REGRESSION ARM FOR A DEFECT THAT SHIPPED LIVE.

    `run_once` imported `is_phantom_close` with a BARE
    `from golive_readiness import ...`. That module lives under `scripts/`,
    which is not on the path in the freqtrade image, so the import raised
    ModuleNotFoundError, hit the fail-open `except`, and the filter was inert
    in production — 🙏 avo kept publishing `n=15, claim +0.194%/trade` off a
    true traded sample of SIX.

    It passed locally for two compounding reasons, and neither is a property of
    the code: pytest adds `scripts/` to the path, and this file's two OTHER
    `golive_readiness` importers DO insert the path, so any run that graded an
    era first left `sys.path` already mutated. The bug was ORDER DEPENDENT.

    The test that shipped beside the defect asserted the import string was
    present and called — which a permanently-broken import satisfies perfectly.
    This one EXECUTES it ([[a-substring-test-is-not-a-wiring-test]]).

    AND IT DRIVES THE REAL `run_once`, not a re-enactment of its import: a test
    that performs the path insert ITSELF proves only that the module is
    importable somehow, which was never in doubt. This hands the function a
    ledger containing three phantom rows and asserts they do not reach the
    claim — the production path, end to end.
    """
    # [2026-09-02 (wl)] vehicle swapped 🔮 georgia-live -> 👩 mum-live: georgia's
    # live arm joined LEGACY_BOTS at her (wg) retirement, so `_living` now
    # correctly drops her rows BEFORE the phantom screen — this test is about
    # the phantom mechanism, which needs a LIVING carrier (the (wg) rule:
    # mechanics tests name why their vehicle changed).
    r = _clean_run(
        "import fleet_allocation as fa\n"
        "REAL = {'bot': 'freqtrade-mum-lighter', 'profit_ratio': -0.004,\n"
        "        'profit_abs': -1.2, 'open_rate': 0.31, 'close_rate': 0.30,\n"
        "        'closed_at': '2026-08-27T10:00:00Z',\n"
        "        'opened_at': '2026-08-27T09:00:00Z'}\n"
        "PH = {'bot': 'freqtrade-mum-lighter', 'profit_ratio': 0.0,\n"
        "      'profit_abs': 0.0, 'open_rate': None, 'close_rate': None,\n"
        "      'closed_at': '2026-08-27T11:00:00Z',\n"
        "      'opened_at': '2026-08-27T11:00:00Z'}\n"
        "class S:\n"
        "    def fetch_paper_trades(self, limit=None):\n"
        "        return [dict(REAL) for _ in range(12)] + [dict(PH) for _ in range(3)]\n"
        "    def fetch_bot_pnl(self, *a, **k): return []\n"
        "fa.store = S()\n"
        "p = fa.run_once(publish=False)\n"
        "rec = (p.get('books') or {}).get('freqtrade-mum-lighter') or {}\n"
        "print('RESULT', p.get('n_phantom'), rec.get('n'))\n")
    assert "RESULT 3 12" in r.stdout, (
        "run_once did not exclude the 3 phantom rows from a clean "
        f"interpreter — this is the production path:\n{r.stdout}\n{r.stderr}")


def test_a_bare_golive_import_cannot_reach_run_once_again():
    """The CLASS, not the instance. Every `from golive_readiness import ...`
    inside this module must be preceded, in its own `try` block, by the
    `sys.path` insert that makes it resolvable. A fourth site written without
    it fails here instead of failing silently in production.

    `dd_bound`'s importer is exempt BY CONSTRUCTION: it resolves the module by
    explicit file path (`spec_from_file_location`), which needs no path insert
    — the born-dark correction above is why it is written that way.
    """
    import ast
    src = (ROOT / "fleet_allocation.py").read_text()
    tree = ast.parse(src)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        block = node.body
        inserts = [n for n in ast.walk(ast.Module(body=block, type_ignores=[]))
                   if isinstance(n, ast.Attribute) and n.attr == "insert"]
        for n in ast.walk(ast.Module(body=block, type_ignores=[])):
            if isinstance(n, ast.ImportFrom) and n.module == "golive_readiness":
                if not inserts:
                    bad.append((n.lineno, [a.name for a in n.names]))
    assert not bad, (
        "a `from golive_readiness import` with no sys.path insert in the same "
        f"try block — it will ModuleNotFoundError in the image: {bad}")


def test_the_organ_publishes_whether_the_filter_ran():
    """0 (ran, found none) and None (could not run) must not be the same
    byte-string. The defect above was invisible precisely because `n_phantom`
    was computed and dropped, so the payload could not distinguish them
    ([[guards-blind-to-their-own-refusals]])."""
    import ast
    src = (ROOT / "fleet_allocation.py").read_text()
    assert 'payload["n_phantom"] = n_phantom' in src, (
        "run_once computes n_phantom but never publishes it")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "run_once")
    # The fail-open branch must assign None, never 0 — a 0 there would claim
    # the filter ran clean when it never ran at all.
    handlers = [h for n in ast.walk(fn) if isinstance(n, ast.Try)
                for h in n.handlers]
    assigns_none = any(
        isinstance(s, ast.Assign) and getattr(s.targets[0], "id", "") == "n_phantom"
        and isinstance(s.value, ast.Constant) and s.value.value is None
        for h in handlers for s in ast.walk(h))
    assert assigns_none, "the fail-open path must set n_phantom=None, not 0"
