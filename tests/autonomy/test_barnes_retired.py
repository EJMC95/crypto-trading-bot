"""(pm) 🎸 band-barnes is RETIRED — the ZERO-INDEPENDENT-EVIDENCE call.

THE DECISION (2026-08-17, operator). The I17 keep-or-retire call on the carry
cell, made on a measurement of the book's OWN ledger rather than on a hunch:

  * **0 of 9.** Every episode its living carry sleeve ever opened was a coin
    🌾 carry was holding AT THAT MOMENT — 3 distinct coins (SKHYNIXUSD, SPCX,
    WTI), every one also traded by carry. In its whole life it produced no
    independent observation.
  * It was minted as a THREE-sleeve "funding super-book", and two sleeves are
    already retired — `extreme` (ly), `xsect` (nf). The founding thesis was the
    COMBINATION; what survives is one sleeve.
  * That survivor is 🌾 carry's own gate (20% TRUE / $2M / 6h / crypto) at a
    smaller cap, 4 vs 12 — I20's "one bet held twice at a new row id".
  * All 9 closes are the non-crypto class removed 13-Aug (lk)/(lv); it has
    opened nothing since. `fleet_allocation` claim: 0.0.

WHY THIS IS A RETIREMENT AND NOT A TUNING PASS: it is birth-FROZEN until
4-Sep, so it cannot be tuned; and the thing to tune would be a gate whose
every setting is already covered by a book with three times the capacity.
Retiring it costs ZERO coverage — that is what makes this cheap.

WHY IT AND NOT ONE OF THE OTHER TWO ON THE CELL, stated so the reasoning is
falsifiable: 🌾 carry is the book the other two COPIED, has the largest cap and
the only real history. 🏦 Rich Dad is 4 days old with a genuinely different rule
set (payback-velocity bar ~21.9% effective, `liability_flip`, `decay_paid`) and
its own ~12-Sep gradeable date — retiring it now would be judging a book before
its record starts, the trap (nu) names on 🧙 Schwager.

WHAT THESE TESTS GUARD. This book OWNS its module and its service, so the whole
process idles — the 🌊/📊/🧙 shape, not (mr)'s shared-module case:
  1. the guard is dropped or made unreachable (the book quietly resumes);
  2. the guard EXITS instead of idling — `restartPolicy=always` turns an exit
     into a permanent crash-loop (the Trail Blazer lesson);
  3. only ONE half ships — hiding the card without pruning the row, or the
     reverse, which is how a retirement hides its own omission;
  4. the reversal switch is renamed or dropped, making the call irreversible;
  5. the cell declaration still claims three books after one left.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ROW = "band-barnes-lshadow"
OVERRIDE = "BARNES_RETIRED_OVERRIDE"
SRC = ROOT / "lighter_band_barnes_bot.py"


def _main_fn():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("lighter_band_barnes_bot.main() not found")


def _guard_if():
    """The `if <override not set>:` node in main(). AST, not a substring — a
    page-wide grep for the env name passes on a comment that merely mentions
    it, the (gn)-class mistake this repo has already paid for."""
    for node in ast.walk(_main_fn()):
        if not isinstance(node, ast.If):
            continue
        names = {n.value for n in ast.walk(node.test)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if OVERRIDE in names:
            return node
    raise AssertionError(f"no guard in main() testing {OVERRIDE}")


def test_the_guard_exists_and_reads_the_override():
    guard = _guard_if()
    calls = [n for n in ast.walk(guard.test) if isinstance(n, ast.Call)]
    assert any(isinstance(c.func, ast.Attribute) and c.func.attr == "get"
               for c in calls), \
        "the guard must READ the override env, not hardcode a bool"


def test_the_guard_idles_and_never_exits():
    """A retirement that EXITS is a crash-loop under restartPolicy=always."""
    guard = _guard_if()
    body = list(ast.walk(ast.Module(body=guard.body, type_ignores=[])))

    sleeps = [n for n in body if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "sleep"]
    assert sleeps, "the guard must idle (time.sleep in a loop), not fall through"

    loops = [n for n in body if isinstance(n, ast.While)]
    assert loops, ("the sleep must be inside a while loop — one sleep then "
                   "exit is still an exit")
    assert any(isinstance(w.test, ast.Constant) and w.test.value is True
               for w in loops), "the idle loop must be `while True`"

    for n in body:
        if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) \
                and isinstance(n.exc.func, ast.Name) \
                and n.exc.func.id == "SystemExit":
            raise AssertionError("guard raises SystemExit — crash-loop")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("exit", "_exit"):
            raise AssertionError("guard calls sys.exit — crash-loop")


def test_the_guard_runs_before_any_venue_work():
    """A retired book that still opens a venue client is still talking to the
    venue. The guard must precede `venue_context` — and this book's VENUE
    allowlist check sits between them, so the ordering is easy to get wrong."""
    main = _main_fn()
    guard_line = _guard_if().lineno
    venue_lines = [n.lineno for n in ast.walk(main)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == "venue_context"]
    assert venue_lines, "venue_context call not found in main()"
    assert guard_line < min(venue_lines), (
        f"guard at line {guard_line} runs AFTER venue_context at "
        f"{min(venue_lines)} — the retired book would still call the venue")


def test_both_halves_of_the_retirement_shipped():
    """RETIRED_ROWS hides the card; LEGACY_BOTS prunes the frozen row. Doing
    one hides your own omission — the 16-Jul lesson."""
    import cleanup_legacy_bots as cl
    assert ROW in cl.LEGACY_BOTS, f"{ROW} missing from LEGACY_BOTS (not pruned)"

    tree = ast.parse((ROOT / "pnl_dashboard.py").read_text(encoding="utf-8"))
    rows = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "RETIRED_ROWS"
                for t in node.targets):
            rows = {n.value for n in ast.walk(node.value)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert rows is not None, "RETIRED_ROWS assignment not found"
    assert ROW in rows, f"{ROW} missing from RETIRED_ROWS (card not hidden)"


def test_the_call_is_reversible():
    """A retirement with no way back is a deletion."""
    assert OVERRIDE in SRC.read_text(encoding="utf-8")
    toks = {n.value for n in ast.walk(_guard_if().test)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "run" in toks, ("the documented resurrect value "
                           f"{OVERRIDE}=run must be accepted")


def test_the_ledger_is_kept_not_deleted():
    """Retirement stops NEW trades; it never deletes history. This book HAS a
    realised record (9 closes) — unlike 🧙 Schwager, which had none — so the
    keep-the-ledger rule has something to protect here."""
    body = ast.Module(body=_guard_if().body, type_ignores=[])
    for n in ast.walk(body):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            assert n.func.attr not in ("delete", "drop", "truncate",
                                       "delete_bot", "purge"), \
                f"guard calls {n.func.attr} — a retirement keeps the ledger"


def test_the_cell_declaration_followed_the_retirement():
    """[(pl)] The collision declaration named THREE books on the carry cell.
    A retirement that leaves it saying three is a doctrine line describing a
    fleet that no longer exists — I12's defect, and here it would also mean
    the guard stops matching the live group and silently reports UNDECLARED."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "abo", ROOT / "scripts" / "audit_book_overlap.py")
    abo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(abo)

    keys = list(abo.KNOWN_CELL_COLLISIONS)
    assert not any(ROW in k for k in keys), \
        f"{ROW} is retired but still named in a KNOWN_CELL_COLLISIONS group"
    cell = frozenset({"perps-funding-carry-lshadow", "book-kiyosaki-lshadow"})
    why = abo.KNOWN_CELL_COLLISIONS.get(cell)
    assert why, "the carry cell is still shared by TWO books and must stay declared"
    assert "OWNER" in why, "a declaration is a decision: it needs an owner"


def test_the_retired_book_is_not_still_listed_as_a_living_funding_book():
    """`FUNDING_BOOKS` drives the whole overlap audit. Leaving a retired row in
    it keeps the book in every rivalry count it should have left."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "abo", ROOT / "scripts" / "audit_book_overlap.py")
    abo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(abo)
    assert ROW not in abo.FUNDING_BOOKS, (
        f"{ROW} is retired but still in FUNDING_BOOKS — it will keep being "
        "counted as a rival for supply it can no longer take")
