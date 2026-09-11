"""[(aap)] A TEST THAT SETS AN ENV VAR AT IMPORT REDDENS EVERY SUBPROCESS SELFTEST.

pytest imports every test module into ONE process before running anything, so
a module-level `os.environ[...] = ...` / `setdefault` leaks into the
environment that `tests/test_selftests.py`'s subprocess runs inherit. The
symptom is not an error in the offending file — it is three or four UNRELATED
suites going red with nonsense results, which is why it costs an hour every
time.

IT HAS NOW BITTEN TWICE, ON THE SAME VARIABLE:
* the 10-Sep random-null design — carried as blocker (1) of
  `taker-random-entry-null-blocked-on-ci`, and closed by construction in
  `(aaf)`: *"the prior design did os.environ.setdefault('TT_BULL_MODE','on')
  at import and raced the taker's import, reddening three unrelated
  selftests."*
* `(aap)`'s own test file, 11-Sep — written the same morning that entry was
  read. Measured: `lighter_scout_tuner`, `lighter_ticket_replay` and
  `lighter_ticket_taker --selftest-live` all went red reporting ZERO fills,
  and `fleet_proprioception` reported `too-few-trades`.

A lesson recorded in prose and violated the same day is the argument for a
guard rather than a note — the fleet's own "a fix closes a class or it is not
finished" rule.

WHAT IS ALLOWED: setting env INSIDE a test function or fixture (scoped, and
usually via monkeypatch), and `os.environ.get` anywhere. What is refused is a
mutation at MODULE level, where it runs at collection time for every test in
the session.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: THE RATCHET, measured 2026-09-11. Nine test modules already do this, all
#: with `setdefault` on a VENUE-selection variable their module-level import
#: genuinely needs. Reddening the build on a pre-existing backlog is how a
#: guard gets exempted within a day and then guards nothing ((mz), and I23
#: ships its own guards as ratchets for exactly this reason) — so the backlog
#: may only SHRINK and a NEW instance fails the push that adds it.
#:
#: To shrink it: move the set inside a fixture (monkeypatch.setenv) or into
#: the test body, then lower this number. Never raise it.
RATCHET = 9

#: Declared exemptions, each needing a reason. Empty by design — an entry here
#: is a permanent hole, where the ratchet is a shrinking one.
ALLOWED = {}

_MUTATORS = {"setdefault", "pop", "update", "clear", "setitem"}


def _module_level_env_mutations(tree):
    """Env mutations reachable at IMPORT time: module body, plus the bodies of
    module-level `if`/`try`/`with`/`for` blocks (all of which execute on
    import). Function and class bodies are deliberately NOT walked."""
    found = []

    def scan(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                continue
            for sub in ast.walk(node):
                # os.environ["X"] = ... / del os.environ["X"]
                if isinstance(sub, (ast.Assign, ast.AugAssign, ast.Delete)):
                    tgts = (sub.targets if isinstance(sub, (ast.Assign,
                                                            ast.Delete))
                            else [sub.target])
                    for t in tgts:
                        if isinstance(t, ast.Subscript) and \
                                "environ" in ast.unparse(t.value):
                            found.append(ast.unparse(sub))
                # os.environ.setdefault(...) / .update(...) / .pop(...)
                if isinstance(sub, ast.Call) and \
                        isinstance(sub.func, ast.Attribute) and \
                        sub.func.attr in _MUTATORS and \
                        "environ" in ast.unparse(sub.func.value):
                    found.append(ast.unparse(sub))
    scan(tree.body)
    return found


def _test_files():
    return sorted(p for p in (ROOT / "tests").rglob("test_*.py"))


def test_no_test_module_mutates_process_env_at_import():
    """Mutation: add `os.environ.setdefault("TT_BULL_MODE", "on")` at the top
    of any test module => this reddens."""
    offenders = {}
    for p in _test_files():
        rel = str(p.relative_to(ROOT))
        if rel in ALLOWED:
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:                       # not this guard's job
            continue
        hits = _module_level_env_mutations(tree)
        if hits:
            offenders[rel] = hits
    n = sum(len(v) for v in offenders.values())
    assert n <= RATCHET, (
        f"{n} test modules mutate process-global env at IMPORT time, above "
        f"the ratchet of {RATCHET}. pytest collects every module into ONE "
        f"process, so this leaks into every subprocess selftest and reddens "
        f"unrelated suites (measured: 3 red, all reporting zero fills).\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(offenders.items()))
        + "\nSet it inside the test or a fixture (monkeypatch), not at module "
          "level.")
    assert n == RATCHET or n < RATCHET, n
    if n < RATCHET:
        pytest.fail(
            f"GOOD NEWS, and the ratchet must follow it down: only {n} "
            f"module-level env mutations remain against a RATCHET of "
            f"{RATCHET}. Lower RATCHET to {n} in this file and say so in the "
            f"changelog — a ratchet that is not tightened when the backlog "
            f"shrinks stops being one.")


def test_the_guard_actually_detects_the_shape_it_is_named_for():
    """(po): empty output is not a negative result until the check has been
    seen to produce a POSITIVE one. This is that positive control."""
    bad = ast.parse('import os\nos.environ.setdefault("TT_BULL_MODE", "on")\n')
    assert _module_level_env_mutations(bad), "the guard cannot see setdefault"
    bad2 = ast.parse('import os\nos.environ["X"] = "1"\n')
    assert _module_level_env_mutations(bad2), "the guard cannot see assignment"
    bad3 = ast.parse('import os\nif True:\n    os.environ["X"] = "1"\n')
    assert _module_level_env_mutations(bad3), \
        "a module-level `if` body still runs at import"
    # and it must NOT fire on the legitimate forms
    ok = ast.parse('import os\ndef test_x(monkeypatch):\n'
                   '    monkeypatch.setenv("X", "1")\n'
                   '    os.environ["Y"] = "2"\n')
    assert not _module_level_env_mutations(ok), "a scoped set is allowed"
    ok2 = ast.parse('import os\nV = os.environ.get("X", "off")\n')
    assert not _module_level_env_mutations(ok2), "a READ is allowed"
