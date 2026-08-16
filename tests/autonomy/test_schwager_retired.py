"""(oh) 🧙 book-schwager is RETIRED — the UNDECIDABLE-BY-TAIL call.

THE DECISION (2026-08-16, operator: "retire schwager"). The I17
keep-or-retire call, made on the (nu)/(oe) re-measurement rather than on a
hunch. Its founding evidence — n=277, +$457.21, t=1.88, both halves positive,
beats random P=0.015 — does not reproduce:

  * a 90-cell window sweep puts +$457.21 OUTSIDE the entire measurable
    distribution (total -$93.52..+$404.55, t -0.68..+1.774), with t>=2.0 in
    0 of 90 cells and the full go-live gate passing in 0 of 90;
  * the top 3 of 298 trades are 112% of the total — drop them and the book
    reads -$17.97, t=-0.13;
  * the random-entry null, re-run under current code, reads P=0.183;
  * at the measured mean/sd it needs ~719 closes (~40 MONTHS at 17.9
    closes/30d) to reach t=2.0.

WHY THAT IS A RETIREMENT AND NOT A TUNING PASS: the sample cannot resolve the
rule, and no amount of waiting fixes a t that is a statistic about the tail.
Fat tails are Schwager's own doctrine (276 of 298 exits are the trail), so the
strategy is not being called bad — it is being called UNGRADEABLE by this
fleet's bar, which is a different verdict and the honest one.

WHAT THESE TESTS GUARD. This book OWNS its module and its service, so unlike
`(mr)`'s shared-module case the whole process idles — the 🌊/📊 shape. The
failure modes that matter here are therefore:
  1. the guard is dropped or made unreachable (the book quietly resumes);
  2. the guard EXITS instead of idling — `restartPolicy=always` turns an exit
     into a permanent crash-loop (the Trail Blazer lesson);
  3. only ONE half of the retirement ships — hiding the card without pruning
     the row, or the reverse, which is how a retirement hides its own omission;
  4. the reversal switch is renamed or dropped, making the call irreversible.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ROW = "book-schwager-lshadow"
OVERRIDE = "SCHWAGER_RETIRED_OVERRIDE"
SRC = ROOT / "lighter_book_schwager_bot.py"


def _main_fn():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("lighter_book_schwager_bot.main() not found")


def _guard_if():
    """The `if <override not set>:` node in main(). AST, not a substring —
    a page-wide grep for the env name passes on a comment that merely
    mentions it, which is the (gn)-class mistake this repo has already paid
    for."""
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
    got_env = any(isinstance(c.func, ast.Attribute) and c.func.attr == "get"
                  for c in calls)
    assert got_env, "the guard must READ the override env, not hardcode a bool"


def test_the_guard_idles_and_never_exits():
    """A retirement that EXITS is a crash-loop under restartPolicy=always."""
    guard = _guard_if()
    body = list(ast.walk(ast.Module(body=guard.body, type_ignores=[])))

    sleeps = [n for n in body if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "sleep"]
    assert sleeps, "the guard must idle (time.sleep in a loop), not fall through"

    loops = [n for n in body if isinstance(n, ast.While)]
    assert loops, "the sleep must be inside a while loop — one sleep then exit "\
                  "is still an exit"
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
    """Idling must happen BEFORE venue_context — a retired book that still
    opens a client is still talking to the venue."""
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
    """RETIRED_ROWS hides the card; LEGACY_BOTS prunes the frozen row.
    Doing one hides your own omission — the 16-Jul lesson."""
    import cleanup_legacy_bots as cl
    assert ROW in cl.LEGACY_BOTS, f"{ROW} missing from LEGACY_BOTS (not pruned)"

    dash = (ROOT / "pnl_dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(dash)
    rows = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "RETIRED_ROWS"
                for t in node.targets):
            rows = {n.value for n in ast.walk(node.value)
                    if isinstance(n, ast.Constant)
                    and isinstance(n.value, str)}
    assert rows is not None, "RETIRED_ROWS assignment not found"
    assert ROW in rows, f"{ROW} missing from RETIRED_ROWS (card not hidden)"


def test_the_call_is_reversible():
    """A retirement with no way back is a deletion. The override token set
    must match the fleet convention so the documented value actually works."""
    src = SRC.read_text(encoding="utf-8")
    assert OVERRIDE in src
    guard = _guard_if()
    toks = {n.value for n in ast.walk(guard.test)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "run" in toks, ("the documented resurrect value "
                           f"{OVERRIDE}=run must be accepted")


def test_the_ledger_is_kept_not_deleted():
    """Retirement stops NEW trades; it never deletes history. Nothing in the
    guard may touch the ledger."""
    body = ast.Module(body=_guard_if().body, type_ignores=[])
    for n in ast.walk(body):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            assert n.func.attr not in ("delete", "drop", "truncate",
                                       "delete_bot", "purge"), \
                f"guard calls {n.func.attr} — a retirement keeps the ledger"
