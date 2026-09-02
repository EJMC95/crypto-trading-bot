"""[2026-09-02 (wt)] THE ORGAN-REVIEW DOCKET CALLS, MADE IN ONE ACT.

Eamon, 2-Sep: *"Proceed with everything in the organ review."* The review laid
out seven keep-or-retire calls with a recommendation each; four were RETIRE and
each carried the I17-as-amended bar — a MEASURED exclusion (upper bound of the
mean at or below zero) or a zero rate — never a thin sample:

  🛢️ band-garrett     unreachable  n=85   -1.090%/t  t=-2.22  ub -0.455%
  🧘 book-douglas     unreachable  n=81   -0.725%/t  t=-2.54  ub -0.357%
  📐 book-grimes      zero_ledger  0 closes in 19d; every gate closed
  🔮 georgia-lshadow  undecidable  n=232  +0.043%/t  t=+0.29  ~4,224 days

Two mechanisms, deliberately: douglas and grimes OWN their module and service,
so the whole process idles (the 🌊/📊/🧙/🎸 shape). garrett is a VARIANT of the
Farmer's module and georgia's shadow shares the family host with mum and avo,
so both are ROW-scoped — the (mr)/(ta) rule: retiring one row must not silence
the others in the same process.

Mutations that turn these red: drop a guard; make a guard exit instead of
idle; put the Garrett guard on VARIANT == "" (the Farmer twin); ship one half
of a retirement; leave garrett in the overlap audit's living funding books;
keep a carried row for a book that no longer trades.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.autonomy

OWN_MODULE = [
    ("book-douglas-lshadow", "DOUGLAS_RETIRED_OVERRIDE", "lighter_book_douglas_bot.py"),
    ("book-grimes-lshadow", "GRIMES_RETIRED_OVERRIDE", "lighter_book_grimes_bot.py"),
    ("band-garrett-lshadow", "GARRETT_RETIRED_OVERRIDE", "lighter_funding_bot.py"),
    # the Farmer's SHADOW twin, retired the day the judge's lane moved to mum
    ("perps-funding-lighter-lshadow", "FARMER_SHADOW_RETIRED_OVERRIDE",
     "lighter_funding_bot.py"),
]
ROWS = ["band-garrett-lshadow", "book-douglas-lshadow", "book-grimes-lshadow",
        "freqtrade-georgia-lshadow", "perps-funding-lighter-lshadow"]


def _main_fn(src):
    tree = ast.parse((ROOT / src).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError(f"{src}: main() not found")


def _guard_if(src, override):
    for node in ast.walk(_main_fn(src)):
        if not isinstance(node, ast.If):
            continue
        names = {n.value for n in ast.walk(node.test)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if override in names:
            return node
    raise AssertionError(f"{src}: no guard in main() testing {override}")


@pytest.mark.parametrize("row,override,src", OWN_MODULE)
def test_the_guard_reads_the_override_and_idles_never_exits(row, override, src):
    guard = _guard_if(src, override)
    calls = [n for n in ast.walk(guard.test) if isinstance(n, ast.Call)]
    assert any(isinstance(c.func, ast.Attribute) and c.func.attr == "get"
               for c in calls), "the guard must READ the env"
    body = list(ast.walk(ast.Module(body=guard.body, type_ignores=[])))
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "sleep" for n in body), "must idle"
    assert any(isinstance(w, ast.While) and isinstance(w.test, ast.Constant)
               and w.test.value is True for w in body), "must be `while True`"
    for n in body:
        assert not (isinstance(n, ast.Raise)), "guard raises — crash-loop"
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            assert n.func.attr not in ("exit", "_exit", "delete", "drop",
                                       "truncate", "purge"), n.func.attr


@pytest.mark.parametrize("row,override,src", OWN_MODULE)
def test_the_guard_runs_before_any_venue_work(row, override, src):
    main = _main_fn(src)
    g = _guard_if(src, override).lineno
    venue = [n.lineno for n in ast.walk(main) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "venue_context"]
    assert venue and g < min(venue), (src, g, venue)


@pytest.mark.parametrize("row,override,src", OWN_MODULE)
def test_the_call_is_reversible(row, override, src):
    toks = {n.value for n in ast.walk(_guard_if(src, override).test)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "run" in toks, f"{override}=run must resurrect"


def test_the_garrett_guard_is_scoped_to_the_variant_not_the_farmer_twin():
    """The Farmer's shadow twin (VARIANT == '') runs in the SAME module on a
    different service; Garrett's call must not idle it (row-scope, (ta))."""
    guard = _guard_if("lighter_funding_bot.py", "GARRETT_RETIRED_OVERRIDE")
    consts = {n.value for n in ast.walk(guard.test)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "band-garrett" in consts, "the guard must test VARIANT == 'band-garrett'"
    names = {n.id for n in ast.walk(guard.test) if isinstance(n, ast.Name)}
    assert "VARIANT" in names


def test_georgias_shadow_is_row_scoped_and_the_shared_process_keeps_trading(monkeypatch):
    import lighter_family_bot as fam
    assert fam.RETIRED_BOOKS.get("freqtrade-georgia") == "GEORGIA_SHADOW_RETIRED_OVERRIDE"
    monkeypatch.delenv("GEORGIA_SHADOW_RETIRED_OVERRIDE", raising=False)
    live = {s.bot for s in fam.live_strategies()}
    assert "freqtrade-georgia" not in live
    for keep in ("freqtrade-mum", "freqtrade-avo-maria", "freqtrade-georgia-v3"):
        assert keep in live, f"{keep} must keep trading — row scope"
    monkeypatch.setenv("GEORGIA_SHADOW_RETIRED_OVERRIDE", "run")
    assert "freqtrade-georgia" in {s.bot for s in fam.live_strategies()}


def test_both_halves_shipped_for_all_four_rows():
    import cleanup_legacy_bots as cl
    tree = ast.parse((ROOT / "pnl_dashboard.py").read_text(encoding="utf-8"))
    hidden = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "RETIRED_ROWS" for t in node.targets):
            hidden = {n.value for n in ast.walk(node.value)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert hidden is not None
    for row in ROWS:
        assert row in hidden, f"{row} not hidden"
        assert row in cl.LEGACY_BOTS, f"{row} not pruned"


def test_garrett_left_the_living_funding_books_and_the_collision_map():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "abo", ROOT / "scripts" / "audit_book_overlap.py")
    abo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(abo)
    assert "band-garrett-lshadow" not in abo.FUNDING_BOOKS
    assert "perps-funding-lighter-lshadow" not in abo.FUNDING_BOOKS
    assert "perps-funding-lighter-lighter" not in abo.FUNDING_BOOKS
    assert not any("band-garrett-lshadow" in k for k in abo.KNOWN_CELL_COLLISIONS)
    cell = frozenset({"perps-funding-carry-lshadow", "book-kiyosaki-lshadow"})
    assert abo.KNOWN_CELL_COLLISIONS.get(cell), "the carry/Rich Dad pair stays declared"


def test_no_carried_row_survives_for_a_retired_book():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ss", ROOT / "scripts" / "session_state.py")
    ss = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ss)
    ids = {r["id"] for r in ss.CARRIED}
    for gone in ("carry-garrett-ranking-collision", "georgia-t-bar",
                 "ceiling-slots-georgia"):
        assert gone not in ids, f"{gone} outlived the book it was about ((vj))"
