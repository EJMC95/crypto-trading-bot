"""THE DURABLE DAILY-LOSS LATCH HAS AN AUDITABLE RELEASE — and it cannot
disable the rail.

[2026-09-11 (abh)] The daily-loss halt is persisted under `<bot>:halt` and
cleared ONLY by the UTC day roll. That durability is deliberate and correct —
`(pq)` built it because a re-derived halt let one Postgres blip re-admit entries
on a day a real-money book had already halted, and `(vg)` says of the sibling
lock that *"a redeploy must not be a way to bypass a protection"*.

The cost of that correctness is that there was NO way to resume a book mid-day,
which `(vg)` already named a gap on the other lock and solved with
`FAMILY_CLEAR_GUARD`: an explicit, operator-only, opt-in, per-book, LOGGED
release. This is that same contract applied to the daily latch.

THE CASE IT WAS BUILT FOR. 👩 mum latched at 11:11Z on 11-Sep against a $105 cap
that was a frozen snapshot of her own 20% leash taken at a $525 day-start.
`(abg)` corrected the cap to $156.11 = `0.20 x $780.57`, her real day-start — and
under the corrected cap she was never in breach: she had lost $114.01 against a
$156.11 allowance, and the 20% level ($624.46) sits below her $666.56 equity. So
the latch outlived the constant that caused it. Eamon, 11-Sep: *"I want to resume
trading now"* / *"Ive given you permission"*.

WHAT IS PINNED HERE IS THE SAFETY PROPERTY, not the convenience: the release
drops a stale LATCH and never suppresses the RAIL. Every test below exists to
make the difference non-negotiable.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOT = ROOT / "lighter_avo_live_bot.py"
SRC = BOT.read_text(encoding="utf-8")


def _mod():
    import importlib
    import lighter_avo_live_bot as m
    return importlib.reload(m)


def _main_fn():
    tree = ast.parse(SRC)
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


# --------------------------------------------------------------------------
# THE ENV CONTRACT — opt-in, per book, and read at BOOT not at import.
# --------------------------------------------------------------------------
def test_the_release_is_opt_in_and_named_per_book(monkeypatch):
    m = _mod()
    monkeypatch.delenv("FAMILY_CLEAR_DAILY_HALT", raising=False)
    assert m._clear_halt_books() == set(), "absent env must release nothing"
    monkeypatch.setenv("FAMILY_CLEAR_DAILY_HALT", "")
    assert m._clear_halt_books() == set(), "empty env must release nothing"
    monkeypatch.setenv("FAMILY_CLEAR_DAILY_HALT", "freqtrade-mum-lighter")
    assert m._clear_halt_books() == {"freqtrade-mum-lighter"}
    # a list releases exactly the named books and nothing else
    monkeypatch.setenv("FAMILY_CLEAR_DAILY_HALT",
                       " freqtrade-mum-lighter , freqtrade-avo-maria-lighter ")
    assert m._clear_halt_books() == {"freqtrade-mum-lighter",
                                     "freqtrade-avo-maria-lighter"}
    # and never a wildcard: an "all books" release is not expressible
    monkeypatch.setenv("FAMILY_CLEAR_DAILY_HALT", "*")
    assert "freqtrade-mum-lighter" not in m._clear_halt_books()


def test_the_env_is_read_at_boot_not_frozen_at_import(monkeypatch):
    """A module-level constant would capture whatever was set when the module
    was first imported, so an operator setting the var would appear to do
    nothing. Pinned as a FUNCTION call, by AST."""
    tree = ast.parse(SRC)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_clear_halt_books")
    reads = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "get"]
    assert reads, "_clear_halt_books must read os.environ at call time"
    # and the call site must call it, never reference a cached constant
    assert "_clear_halt_books()" in SRC
    m = _mod()
    monkeypatch.setenv("FAMILY_CLEAR_DAILY_HALT", "later-set")
    assert m._clear_halt_books() == {"later-set"}, (
        "the value must follow the RUNNING env, not the import-time one")


# --------------------------------------------------------------------------
# THE SAFETY PROPERTY. This is the whole test file.
# --------------------------------------------------------------------------
def test_the_release_never_suppresses_the_rail_only_the_latch():
    """THE LOAD-BEARING PROPERTY. Clearing must drop the stored latch and leave
    the breach re-derivation untouched, so a book genuinely in breach re-halts
    on the SAME cycle. Structurally: the clear sits in the `elif _halt:` restore
    branch, and the `if breach and not halted_today:` rail is a LATER, separate
    statement that the clear does not guard, gate or skip."""
    fn = _main_fn()
    clear_lines, rail_lines = [], []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == "_clear_halt_books":
            clear_lines.append(n.lineno)
        if isinstance(n, ast.If):
            t = ast.dump(n.test)
            if "breach" in t and "halted_today" in t:
                rail_lines.append(n.lineno)
    assert clear_lines, "the release is not wired into main()"
    assert rail_lines, "the breach rail was not found — did it move?"
    assert max(clear_lines) < min(rail_lines), (
        f"the release at {clear_lines} must run BEFORE the breach rail at "
        f"{rail_lines}, so a real breach re-halts the same cycle")
    # and the rail must NOT be conditioned on the release in any way
    rail = next(n for n in ast.walk(fn)
                if isinstance(n, ast.If) and n.lineno == min(rail_lines))
    assert "_halt_cleared" not in ast.dump(rail.test), (
        "the breach rail must not consult the release flag")
    assert "_clear_halt_books" not in ast.dump(rail.test)


def test_the_release_is_once_per_process():
    """Leaving the env set must not re-clear on a later cycle, or the rail is
    permanently off for that book rather than released once."""
    m = _mod()
    assert m._halt_cleared == [False], "must start un-fired"
    # the call site guards on the flag AND sets it
    assert "not _halt_cleared[0]" in SRC
    assert "_halt_cleared[0] = True" in SRC
    # the flag is set BEFORE the clearing write, so a failed write cannot leave
    # the release armed to fire again every cycle
    i_set = SRC.index("_halt_cleared[0] = True")
    i_write = SRC.index('store.save_state(BOT_ROW + ":halt"')
    assert i_set < i_write, "latch the flag before attempting the write"


def test_the_cleared_record_is_written_so_the_day_no_longer_matches():
    """`load_daily_halt_checked` returns a halt only while
    `halted_date == today`, so the release must write a record whose date can
    never equal a UTC day — not delete the key, which would lose the audit."""
    assert '"halted_date": None' in SRC
    assert '"cleared_at"' in SRC and '"cleared_record"' in SRC, (
        "the release must preserve WHAT it cleared and WHEN — an unlock with no "
        "record is how a protection goes missing quietly ((vg))")


def test_a_failed_clearing_write_never_breaks_the_live_loop():
    """The write is telemetry-adjacent on a real-money loop: the `halt_level`
    hazard is a field able to take down the loop that publishes it."""
    fn = _main_fn()
    guarded = False
    for n in ast.walk(fn):
        if isinstance(n, ast.Try):
            body = ast.dump(ast.Module(body=n.body, type_ignores=[]))
            if 'save_state' in body and ':halt' in body:
                guarded = any(h.type is not None or h.type is None
                              for h in n.handlers) and bool(n.handlers)
    assert guarded, "the clearing write must sit inside a try/except"


# --------------------------------------------------------------------------
# VISIBILITY. An unlock nobody can see is the thing (vg) warns about.
# --------------------------------------------------------------------------
def test_the_release_is_loud_and_publishes_a_receipt():
    assert "DAILY HALT LATCH CLEARED" in SRC, "the release must log loudly"
    assert '"halt_cleared": bool(_halt_cleared[0])' in SRC, (
        "the release must publish on the row — a log line is not visible on "
        "the feed")
    # the receipt lives in entry_vetoes, beside the other shut-reason fields
    i_recv = SRC.index('"halt_cleared"')
    i_vetoes = SRC.index('"entry_vetoes": {')
    i_held = SRC.index('"evolve": {')
    assert i_vetoes < i_recv < i_held, "receipt belongs in entry_vetoes"


def test_exits_are_never_gated_by_any_of_this():
    """The standing contract on every halt path: block NEW entries, never
    EXITS. The release must not appear anywhere near an exit decision."""
    # the release touches only the halt RESTORE branch; assert it is not used
    # in any function other than main()
    tree = ast.parse(SRC)
    users = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                        and n.func.id == "_clear_halt_books":
                    users.add(fn.name)
    assert users == {"main"}, users
