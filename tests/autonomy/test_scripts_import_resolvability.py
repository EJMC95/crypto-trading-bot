"""A fail-open `except` around an import is a silent kill switch for the
feature inside it.

[2026-08-28 (vd)] THE CLASS BEHIND A DEFECT THAT SHIPPED TO PRODUCTION.

`fleet_allocation.run_once` imported the phantom-close signature with a bare
`from golive_readiness import is_phantom_close`. That module lives under
`scripts/`, which is NOT on `sys.path` in the freqtrade image, so the import
raised ModuleNotFoundError, hit the fail-open `except`, and the filter was
INERT — 🙏 avo kept publishing `n=15, claim +0.194%/trade` off a true traded
sample of SIX, on the organ that decides where the next dollar goes.

WHY IT SURVIVED EVERY LOCAL CHECK, none of which is a property of the code:
  * pytest puts `scripts/` on `sys.path`, so the harness answered the question
    the code was supposed to answer;
  * the same file's OTHER two `golive_readiness` importers DO insert the path,
    and `sys.path` is process-global — so any run that graded an era first left
    the path already mutated. **The bug was ORDER DEPENDENT**, which is exactly
    the kind that passes every time a human checks it by hand;
  * `--selftest` exited 0, because fail-open is silent by design.

FAIL-OPEN IS THE RIGHT CHOICE HERE — an allocation organ that silently sees
NOTHING is worse than one that sees a few phantom rows. That is precisely why
the import must be made to resolve rather than left to chance: the handler will
never tell anyone it fired.

THE RULE THIS PINS: a module OUTSIDE `scripts/` that imports a `scripts/`
module inside a swallowing `try` must make it resolvable, by either
  (a) inserting the `scripts/` directory on `sys.path` in the same `try`, or
  (b) falling back to the `scripts.<mod>` namespace-package form in a handler.
Both work. `fleet_allocation` uses (a) to match its neighbours;
`evidence_board` uses (b), which is arguably cleaner since it mutates nothing
global — that one is NOT a defect and this test must keep passing it.

MEASURED WHEN WRITTEN: exactly ONE violation existed (the one above, now
fixed), so this guard reddens on a NEW instance rather than carrying a backlog
— the (mz) lesson that a guard which fails the build on pre-existing debt gets
exempted within a day and then guards nothing.

DELIBERATELY NOT FLAGGED, with reasons:
  * modules INSIDE `scripts/` importing siblings — Python puts the script's own
    directory on `sys.path[0]`, so those resolve by construction;
  * imports with NO `try` at all — those crash loudly, which is a fine outcome
    and the opposite of this failure mode.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

#: [2026-08-28 (vd)] THESE ARE MATCHED ON THE PATH *RELATIVE TO ROOT*, and the
#: absolute form was a live defect in this very file: the skip list carried
#: ".claude/worktrees" while the repo itself lives at
#: `…/.claude/worktrees/hatchlings`, so EVERY file matched the skip and the
#: sweep inspected ZERO of them. It reported clean, and both mutations of the
#: real code stayed green — a guard indistinguishable from `assert True`,
#: shipped inside the file whose own docstring quotes "a check that inspects
#: nothing reports clean". Caught only by the mutation round (I3).
#:
#: The sibling worktrees a run must still not walk are OUTSIDE this ROOT, so
#: `rglob` never reaches them and no skip entry is needed for them at all
#: ([[a-guard-that-walks-sibling-worktrees]]).
SKIP_PARTS = (".venv", "__pycache__", "build", ".git", "node_modules")


def _script_modules():
    d = ROOT / "scripts"
    return {p.stem for p in d.glob("*.py")} if d.is_dir() else set()


def _handler_has_scripts_fallback(handlers, mod):
    """Form (b): `from scripts.<mod> import ...` anywhere in a handler."""
    for h in handlers:
        for n in ast.walk(h):
            if isinstance(n, ast.ImportFrom) and n.module in (
                    f"scripts.{mod}", "scripts"):
                return True
    return False


def _violations():
    mods = _script_modules()
    assert mods, "no modules found under scripts/ — the sweep would be vacuous"
    out = []
    visited = []
    for f in sorted(ROOT.rglob("*.py")):
        rel = f.relative_to(ROOT)
        if any(p in SKIP_PARTS for p in rel.parts):
            continue
        # A module inside scripts/ gets its own dir on sys.path[0].
        if f.parent == ROOT / "scripts":
            continue
        try:
            tree = ast.parse(f.read_text())
        except Exception:                                # noqa: BLE001
            continue
        visited.append(str(rel))
        for t in ast.walk(tree):
            if not isinstance(t, ast.Try):
                continue
            body = ast.Module(body=t.body, type_ignores=[])
            has_insert = any(
                isinstance(n, ast.Attribute) and n.attr == "insert"
                for n in ast.walk(body))
            swallows = any(
                not any(isinstance(s, ast.Raise) for s in ast.walk(h))
                for h in t.handlers)
            if not swallows:
                continue
            for n in ast.walk(body):
                if not isinstance(n, ast.ImportFrom) or n.module not in mods:
                    continue
                if has_insert or _handler_has_scripts_fallback(t.handlers,
                                                               n.module):
                    continue
                out.append(f"{rel}:{n.lineno} "
                           f"from {n.module} import "
                           f"{','.join(a.name for a in n.names)}")
    return out, visited


def test_no_silent_kill_switch_import_of_a_scripts_module():
    bad, _ = _violations()
    assert not bad, (
        "a swallowing `try` imports a scripts/ module with neither a sys.path "
        "insert nor a `scripts.<mod>` fallback. It will ModuleNotFoundError in "
        "the image and the feature inside will be silently dead:\n  "
        + "\n  ".join(bad))


def test_the_sweep_actually_walks_the_tree():
    """THE ARM THAT WOULD HAVE CAUGHT THIS GUARD BEING VACUOUS, and did not
    exist until a mutation round proved it was needed.

    The skip list originally matched ".claude/worktrees" against the ABSOLUTE
    path. This repo lives at `…/.claude/worktrees/hatchlings`, so every file
    matched and the sweep visited ZERO. `test_..._can_actually_find_one` still
    passed, because it exercises the PREDICATE on a synthetic string — it never
    touches the file walk. Predicate coverage and sweep coverage are different
    properties and each needs its own assertion.

    So: assert the walk reaches a real, known population, and name the specific
    files this guard exists to police.
    """
    _, visited = _violations()
    assert len(visited) > 50, (
        f"the sweep visited only {len(visited)} files — it is not walking the "
        f"tree, so it would report CLEAN on any defect: {visited[:10]}")
    for must in ("fleet_allocation.py", "evidence_board.py"):
        assert must in visited, (
            f"{must} is a module this guard exists to police and the sweep "
            f"never opened it")


def test_the_sweep_can_actually_find_one():
    """A CHECK THAT INSPECTS NOTHING REPORTS CLEAN, AND CLEAN READS AS
    EVIDENCE. The test above passes on an empty tree, on a broken parser, and
    on a `_script_modules()` that returns nothing — so prove the detector
    fires by handing it the exact shape of the shipped defect.

    Without this arm the guard above is indistinguishable from `assert True`.
    """
    import tempfile
    import textwrap
    mods = _script_modules()
    assert "golive_readiness" in mods

    src = textwrap.dedent("""
        def f(trades):
            try:
                from golive_readiness import is_phantom_close
                return [t for t in trades if not is_phantom_close(t)]
            except Exception:
                return trades
    """)
    tree = ast.parse(src)
    found = []
    for t in ast.walk(tree):
        if not isinstance(t, ast.Try):
            continue
        body = ast.Module(body=t.body, type_ignores=[])
        has_insert = any(isinstance(n, ast.Attribute) and n.attr == "insert"
                         for n in ast.walk(body))
        swallows = any(not any(isinstance(s, ast.Raise) for s in ast.walk(h))
                       for h in t.handlers)
        for n in ast.walk(body):
            if (isinstance(n, ast.ImportFrom) and n.module in mods
                    and swallows and not has_insert
                    and not _handler_has_scripts_fallback(t.handlers, n.module)):
                found.append(n.module)
    assert found == ["golive_readiness"], (
        "the detector did not fire on a verbatim copy of the shipped defect — "
        "it would report CLEAN on a real one")
    del tempfile


def test_the_two_accepted_forms_are_both_accepted():
    """Neither remediation may be quietly outlawed by a future tightening.
    `fleet_allocation` uses the sys.path insert; `evidence_board` uses the
    namespace-package fallback and is NOT a defect."""
    mods = _script_modules()

    def clean(src):
        tree = ast.parse(src)
        for t in ast.walk(tree):
            if not isinstance(t, ast.Try):
                continue
            body = ast.Module(body=t.body, type_ignores=[])
            has_insert = any(isinstance(n, ast.Attribute) and n.attr == "insert"
                             for n in ast.walk(body))
            for n in ast.walk(body):
                if isinstance(n, ast.ImportFrom) and n.module in mods:
                    if not (has_insert or _handler_has_scripts_fallback(
                            t.handlers, n.module)):
                        return False
        return True

    form_a = ("try:\n"
              "    sys.path.insert(0, 'scripts')\n"
              "    from golive_readiness import grade\n"
              "except Exception:\n"
              "    grade = None\n")
    form_b = ("try:\n"
              "    from golive_readiness import GOLIVE_MAX_DD\n"
              "except Exception:\n"
              "    try:\n"
              "        from scripts.golive_readiness import GOLIVE_MAX_DD\n"
              "    except Exception:\n"
              "        GOLIVE_MAX_DD = None\n")
    assert clean(form_a), "the sys.path-insert form must stay acceptable"
    assert clean(form_b), (
        "the scripts.<mod> namespace fallback must stay acceptable — "
        "evidence_board uses it and is not a defect")
