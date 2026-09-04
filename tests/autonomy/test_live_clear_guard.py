"""[2026-09-02] FAMILY_CLEAR_GUARD reaches the LIVE arm — once per process.

THE GAP. (vg) built `FAMILY_CLEAR_GUARD` for the shadow `Book` and its own
correction (vh) recorded, correctly at the time, that it "does not unlock the
live arm" — the live arm then had nothing durable to clear. (vn) later gave the
live arm a durable latch (`state.guard_until`, restored at boot, survives
redeploys BY DESIGN) and did not port the release. Measured cost: 🙏 avo's
latch, armed by the (wf) denominator defect at a reading of 35.23% that the
corrected rail scores at 7.25%, had no designed release and served its full
20-hour clock on an already-fixed bug, on real money.

THE HAZARD THESE TESTS EXIST FOR. The family's clear runs inside `restore()` —
genuinely once per boot. The live arm's latch restore runs INSIDE THE MAIN
LOOP, every iteration. A straight port therefore re-clears every loop while the
env var is set: not an unlock but the slguard/maxdd rails switched off. That
version was written in this session and caught before commit; the
`_GUARD_CLEAR_DONE` sentinel is what stands between "auditable operator unlock"
and "protection quietly disabled". These tests drive the sentinel and both
identity forms, and pin the (vh) rule that the two arms share one env var.
"""
import ast
import os
import pathlib as _p
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
LIVE = os.path.join(ROOT, "lighter_avo_live_bot.py")
FAMILY = os.path.join(ROOT, "lighter_family_bot.py")


def _clear_block(src):
    """The clear site: the `if` whose test names _GUARD_CLEAR_DONE."""
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.If) and "_GUARD_CLEAR_DONE" in ast.unparse(n.test):
            return n
    return None


def test_the_live_arm_reads_the_same_env_var_as_the_family():
    """(vh): one tool, one name. A second env var for the same concept is a
    second rule, free to drift."""
    # [(ya)] read via pathlib — a bare `open().read()` leaks the handle and
    # the repo's own ratchet counts it (test_no_leaked_file_handles).
    live = _p.Path(LIVE).read_text()
    assert 'os.environ.get("FAMILY_CLEAR_GUARD"' in live
    assert 'FAMILY_CLEAR_GUARD' in _p.Path(FAMILY).read_text()


def test_the_clear_is_guarded_by_a_once_per_process_sentinel():
    """The load-bearing line. Without `not _GUARD_CLEAR_DONE` in the SAME test
    as the env check, a set env var re-clears every loop and the rails are off.
    Asserted on the AST so a refactor cannot satisfy it with a comment."""
    node = _clear_block(_p.Path(LIVE).read_text())
    assert node is not None, "the clear site is gone from the live arm"
    cond = ast.unparse(node.test)
    assert "_GUARD_CLEAR_DONE" in cond and "not " in cond, cond
    assert "guard_latch[0]" in cond, (
        "the clear must require a LIVE latch — clearing nothing must not "
        "consume the once-per-process shot")
    body = "\n".join(ast.unparse(s) for s in node.body)
    assert "_GUARD_CLEAR_DONE.append" in body, (
        "the sentinel is never marked — the clear would repeat every loop")
    assert "guard_latch = [0.0, None]" in body


def test_the_module_sentinel_starts_empty_and_is_module_level():
    import lighter_avo_live_bot as A
    assert isinstance(A._GUARD_CLEAR_DONE, list)
    # a fresh import = a fresh process = one shot available
    assert list(A._GUARD_CLEAR_DONE) == []


def test_both_identity_forms_are_accepted_and_the_match_is_exact():
    """The operator may type the bare id (family convention) or the row id.
    Substring matches would let `freqtrade-avo` clear `freqtrade-avo-maria`."""
    src = open(LIVE).read()
    node = _clear_block(src)
    cond = ast.unparse(node.test)
    assert "{BOT, BOT_ROW}" in cond and "& _clear" in cond, cond


def test_the_clear_logs_what_it_cleared():
    """(vg): an unlock nobody can see is how a protection goes missing
    quietly. The log must carry the cause and the deadline it dropped."""
    node = _clear_block(_p.Path(LIVE).read_text())
    body = "\n".join(ast.unparse(s) for s in node.body)
    assert "FAMILY_CLEAR_GUARD" in body
    assert "guard_latch[1]" in body and "guard_latch[0]" in body


def test_the_env_default_is_off():
    """Unset env ⇒ empty set ⇒ no bot matches ⇒ the latch stands. The tool is
    opt-in per (vg); a default that cleared anything would be a standing
    bypass of a live protection."""
    node = _clear_block(_p.Path(LIVE).read_text())
    # find the _clear assignment just above: it must default to ""
    src = open(LIVE).read()
    assert 'os.environ.get("FAMILY_CLEAR_GUARD", "")' in src
    cond = ast.unparse(node.test)
    assert "_clear" in cond
