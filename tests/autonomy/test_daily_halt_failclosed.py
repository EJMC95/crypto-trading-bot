"""The daily-loss halt must fail CLOSED on both real-money books.

[2026-08-18 (pq)/(pr)] `bot_pnl_store.load_daily_halt` returns None for BOTH
"not halted today" and "the READ failed" — `load_state` collapses them, as its
own docstring warns. Its consumers are daily-loss rails on REAL MONEY, so on a
failed read the book resumed entering positions on a day it had already halted.
Measured on 🙏 Avo LIVE:

    read OK + halt stored -> {'halted_date': ...}   halted=True
    read FAILS            -> None                   halted=False   <-- re-admits
    read OK + no halt     -> None                   halted=False

The last two are byte-identical to every caller. 💸 the Farmer had the same
class one shelf up and worse: its read is at BOOT ONLY, so a blip there lost
the halt for the whole UTC day with no per-cycle re-read.

Both now use `load_daily_halt_checked` and carry a `halt_blind` flag into their
entry gate — block NEW entries while blind, never block exits.

WHY AST AND NOT A GREP: this file's own docstring contains every string a
substring scan would look for, and this repo has already shipped three
mutations that survived a page-wide `in` check ((hm), and the memory note
"a substring test is NOT a wiring test"). Every assertion below resolves a real
call node or a real `if` test.

SCOPED TO THE LIVE BOOKS on purpose. `lighter_ticket_taker.py` (shadow) still
uses the unchecked read; that is a known, declared gap, not something this test
should redden — real money first, and a guard that fails on a book nobody
decided about is one the reader learns to ignore ((gl)).
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

#: (module, name of the flag its entry gate must consult)
LIVE_BOOKS = [
    ("lighter_avo_live_bot.py", "halt_blind"),
    ("lighter_funding_bot.py", "halt_blind"),
]


def _tree(fname):
    return ast.parse((ROOT / fname).read_text())


def _attr_calls(tree, attr):
    """Every Call node of the form `<anything>.<attr>(...)`."""
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == attr]


@pytest.mark.parametrize("fname,flag", LIVE_BOOKS)
def test_live_book_reads_the_halt_through_the_checked_form(fname, flag):
    """MUTATION: swap the call back to `store.load_daily_halt(...)` -> RED."""
    tree = _tree(fname)
    checked = _attr_calls(tree, "load_daily_halt_checked")
    bare = _attr_calls(tree, "load_daily_halt")

    assert checked, (
        f"{fname} never calls store.load_daily_halt_checked — a real-money "
        f"daily-loss rail is reading the halt through the form that cannot "
        f"tell a Postgres blip from a clean day ((pq))")
    assert not bare, (
        f"{fname} still calls store.load_daily_halt (the unchecked form) at "
        f"{[n.lineno for n in bare]}. It returns None for BOTH 'not halted' "
        f"and 'the read failed', so a blip re-admits entries on a halted day")


@pytest.mark.parametrize("fname,flag", LIVE_BOOKS)
def test_the_entry_gate_consults_the_blind_flag(fname, flag):
    """The flag must GATE something — a variable nobody reads is decoration.

    MUTATION: drop `and not halt_blind` from the entry condition -> RED.
    """
    # The two books express the same gate differently and BOTH are legitimate:
    # the Farmer guards an `if ... and not halt_blind:` directly, Avo folds the
    # term into an `entries_ok = (... and not halt_blind ...)` assignment that
    # then guards the loop. Match the `not <flag>` operand wherever it occurs
    # inside a boolean expression — checking only `ast.If` tests missed Avo's
    # shape entirely and reddened a correct book.
    tree = _tree(fname)
    gates = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)
             and isinstance(n.operand, ast.Name) and n.operand.id == flag]
    assert gates, (
        f"{fname} never evaluates `not {flag}`: the blind flag is set but "
        f"nothing consults it, so an unreadable halt still opens positions — "
        f"the defect, with a variable added")


@pytest.mark.parametrize("fname,flag", LIVE_BOOKS)
def test_blindness_never_gates_an_exit(fname, flag):
    """Fail-closed on ENTRIES only. A book must always be able to CLOSE.

    Pinned by name: no call whose function mentions flatten/close/exit may sit
    inside a branch guarded by `not <flag>`.
    """
    tree = _tree(fname)
    # `ast.IfExp` as well as `ast.If`: a first version walked only statements
    # and a ternary `_flatten_all(...) if not halt_blind else None` SURVIVED
    # the mutation round. A guard that cannot kill proves nothing.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.IfExp)):
            continue
        guarded = any(
            isinstance(sub, ast.UnaryOp) and isinstance(sub.op, ast.Not)
            and isinstance(sub.operand, ast.Name) and sub.operand.id == flag
            for sub in ast.walk(node.test))
        if not guarded:
            continue
        # ONLY the branch taken when NOT blind. An exit sitting in the `else`
        # of `if not halt_blind:` runs precisely WHEN blind, which is correct
        # and must not be flagged — walking the whole node would fail a book
        # for doing the right thing.
        body = node.body if isinstance(node.body, list) else [node.body]
        for call in [c for stmt in body for c in ast.walk(stmt)]:
            if not isinstance(call, ast.Call):
                continue
            name = (call.func.attr if isinstance(call.func, ast.Attribute)
                    else getattr(call.func, "id", "") or "")
            assert not any(k in name.lower()
                           for k in ("flatten", "close_", "_close", "exit_")), (
                f"{fname}:{call.lineno} calls {name}() inside a branch gated "
                f"on `not {flag}` — halt-blindness must never block an EXIT, "
                f"or the fix traps real money in an open position")


def test_the_owner_distinguishes_a_failed_read():
    """`load_daily_halt_checked` must report ok=False on a failed read.

    Driven against the REAL function with the REAL failure return of
    `load_state_checked` — not a hand fixture ((hj): test consumers against
    publisher-built payloads).
    """
    import bot_pnl_store as store

    day, halt = "2026-08-18", {"halted_date": "2026-08-18"}
    real = store.load_state_checked
    try:
        store.load_state_checked = lambda k: (True, dict(halt))
        assert store.load_daily_halt_checked("b", day) == (True, halt)

        store.load_state_checked = lambda k: (True, None)
        assert store.load_daily_halt_checked("b", day) == (True, None)

        store.load_state_checked = lambda k: (False, None)   # the blip
        ok, rec = store.load_daily_halt_checked("b", day)
        assert ok is False and rec is None, (
            "a failed read must report ok=False; returning True here is the "
            "whole (pq) defect, moved one function down")
    finally:
        store.load_state_checked = real
