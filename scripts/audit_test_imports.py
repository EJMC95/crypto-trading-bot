#!/usr/bin/env python3
"""A test may not import what CI does not install — the vacuous-red twin of born-dark.

INCIDENT (2026-09-07, measured twice in one day). `tests/autonomy/
test_code_currency_wired.py` gained two tests that call `import yaml`.
**`requirements-test.txt` has no yaml**, deliberately — its own header says it
installs "the minimum needed to import the fleet modules and run their offline
`--selftest` blocks" — and the edited file's own docstring says so a second
time: *"requirements-test.txt carries no yaml lib, and the properties pinned
here are line-shaped."* The convention was written at the top of the file and
walked past. CI:

    FAILED test_code_currency_wired.py::test_code_currency_exit_code_is_not_masked
    FAILED test_code_currency_wired.py::test_a_red_guard_never_silences_the_guards_behind_it
        ModuleNotFoundError: No module named 'yaml'

**WHY IT PASSED LOCALLY AND FAILED IN CI, which is the whole class:** `yaml` IS
importable in the dev container (PyYAML 6.0.1, pulled in transitively) and is
NOT installed in CI. So the author ran the test, saw green, and pushed a red
build — the two-regimes shape this repo has already paid for at
`audit_ci_coverage` ((pn): a guard's fallbacks govern exactly where the build
is gated) and records as [[a-guard-has-two-regimes-ci-has-no-database]].

It is the exact mirror of `audit_image_imports` (the born-dark guard): that one
asks *"does this module import something its IMAGE does not ship?"*, and
nothing asked the same question of the TEST job. A red build is louder than a
born-dark organ, so this class is cheaper — but it is not free: it blocks
every other push until someone notices, and on 2026-09-07 a different instance
of "CI is red and nobody is shown" ran for ten hours ((yx)).

WHAT IT CHECKS. Every `import`/`from` in `tests/**` — **at any depth**, because
both failing imports were INSIDE a test function, where a module-level scan
sees nothing. A top-level module name must be one of:

  * the standard library (`sys.stdlib_module_names`);
  * a module this repo ships (a root `.py`, or a package directory here);
  * a distribution named in `requirements-test.txt` or `requirements.txt`,
    mapped through `_IMPORT_ALIASES` where the import name differs from the
    pip name (PyYAML -> yaml, psycopg2-binary -> psycopg2);
  * declared in `ALLOWED_UNDECLARED` with a reason.

Anything else fails the build BEFORE the push, in the regime that is cheap,
instead of after it in the regime that blocks everyone.

A GUARDED IMPORT IS FINE, AND THE FIRST CUT OF THIS GUARD GOT THAT WRONG. It
banned `try: import x / except ImportError:` outright, on the argument that a
silent skip is a vacuous green. Running it against the tree refuted that in one
pass: `test_workflow_shell_syntax` ALREADY imports yaml that way and
`test_margin_truth` imports `lighter` that way — and the second is the model of
doing it right, because it asserts the DEGRADED behaviour in the except branch
rather than skipping. Both are on main and both are green. So the defect is not
"imports something optional", it is **imports it with no fallback, so the test
cannot run at all where the module is absent** — which is exactly what
`import yaml` bare inside a test function did.

Accepted as guarded: an import inside a `try` whose handler catches
`ImportError`/`ModuleNotFoundError` (or is bare), and `pytest.importorskip`.

WHAT CI ACTUALLY HAS is read from the workflow, not retyped: `tests.yml`
installs `requirements-test.txt` and then greps a small alternation out of
`requirements.txt` (`lighter-sdk`, `websockets`). That pattern is parsed from
the workflow text so this guard cannot drift from the job it models; if the
file is unreadable it falls back to the declared tuple, which is the
conservative direction (fewer names available -> more findings, never fewer).

Usage:
  python3 scripts/audit_test_imports.py
  python3 scripts/audit_test_imports.py --selftest
"""
import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Directories scanned. `tests/` is where both incidents were and where the CI
#: job's import graph actually starts. Scripts are reached THROUGH tests (the
#: `SELFTEST_MODULES` registry imports them), so their imports are covered
#: transitively by the same run — a script importing an uninstalled module
#: reddens `test_selftests` identically.
SCAN_DIRS = ("tests",)

#: pip distribution name -> the name you actually `import`. Only the ones that
#: differ; everything else normalises by lowercasing and `-` -> `_`.
_IMPORT_ALIASES = {
    "pyyaml": "yaml",
    "psycopg2-binary": "psycopg2",
    "psycopg2_binary": "psycopg2",
    "pytest-cov": "pytest_cov",
    "python-dateutil": "dateutil",
    "beautifulsoup4": "bs4",
    "pillow": "PIL",
    "lighter-sdk": "lighter",
    "lighter_sdk": "lighter",
}

#: Third-party modules a test may import WITHOUT the requirements files naming
#: them. Each needs a reason — the `BORN_DARK_OK` idiom. Empty is the correct
#: resting state: an entry here is a dependency nobody has declared, which is
#: the thing this guard exists to surface.
ALLOWED_UNDECLARED = {
    # "some_module": "why it is safe that CI does not install it",
}


def _requirement_names(path):
    """Import names a requirements file makes available. Tolerant by design:
    an unparseable line is SKIPPED, never treated as declaring something."""
    out = set()
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return out
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # strip environment markers, extras and version specifiers
        line = line.split(";", 1)[0].strip()
        line = re.split(r"[\[<>=!~ ]", line, 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        out.add(_IMPORT_ALIASES.get(low, low.replace("-", "_")))
    return out


#: Directories the tests put on `sys.path` before importing. `scripts/` is the
#: big one — `golive_readiness`, `edge_audit` and every `audit_*` live there and
#: are imported by bare name after a `sys.path.insert`. Missing this reported
#: 70 repo-local modules as third-party on the first run; the guard was crying
#: wolf on its own codebase, which is how a guard gets exempted and then guards
#: nothing ((mz)).
PATH_INSERTED_DIRS = ("scripts", "tests", "tests/autonomy")

#: Distributions CI installs from `requirements.txt` on top of the test
#: requirements. FALLBACK ONLY — the live value is parsed from the workflow.
CI_EXTRA_FALLBACK = ("lighter-sdk", "websockets")


def _ci_extra_names(root):
    """Distribution names `tests.yml` installs from `requirements.txt`.

    Parsed from the workflow's own grep alternation rather than retyped, so
    the guard cannot drift from the job it models. Unreadable/unmatched falls
    back to the declared tuple — the CONSERVATIVE direction, since a smaller
    available set can only produce MORE findings, never fewer.
    """
    try:
        with open(os.path.join(root, ".github", "workflows", "tests.yml"),
                  encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return set(CI_EXTRA_FALLBACK)
    m = re.search(r"grep -E '\^\(([^)]*)\)'\s+requirements\.txt", text)
    if not m:
        return set(CI_EXTRA_FALLBACK)
    return {p.strip() for p in m.group(1).split("|") if p.strip()}


def _repo_modules(root=None):
    """Top-level names importable because this repo ships them — including the
    directories the tests insert on `sys.path`."""
    root = root or ROOT
    out = set()
    def _add(d):
        try:
            entries = os.listdir(d)
        except OSError:
            return
        for name in entries:
            if name.endswith(".py"):
                out.add(name[:-3])
            elif (os.path.isdir(os.path.join(d, name))
                  and not name.startswith(".")):
                out.add(name)
    _add(root)
    for rel in PATH_INSERTED_DIRS:
        _add(os.path.join(root, rel))
    return out


def _guarded(tree):
    """Module names imported under an ImportError fallback, or via
    `pytest.importorskip` — legitimate optional dependencies."""
    ok = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            catches = any(
                h.type is None
                or (isinstance(h.type, ast.Name)
                    and h.type.id in ("ImportError", "ModuleNotFoundError"))
                or (isinstance(h.type, ast.Tuple)
                    and any(isinstance(e, ast.Name)
                            and e.id in ("ImportError", "ModuleNotFoundError")
                            for e in h.type.elts))
                for h in node.handlers)
            if not catches:
                continue
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Import):
                        ok |= {a.name.split(".")[0] for a in sub.names}
                    elif isinstance(sub, ast.ImportFrom) and sub.module:
                        ok.add(sub.module.split(".")[0])
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == "importorskip"
              and node.args
              and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            ok.add(node.args[0].value.split(".")[0])
    return ok


def _imported_names(tree):
    """Every top-level module name imported anywhere in `tree`.

    AT ANY DEPTH: `ast.walk` rather than iterating `tree.body`, because both
    imports in the incident sat INSIDE a test function and a module-level scan
    reports a clean file. A relative `from . import x` has `level > 0` and is
    repo-local by construction, so it is skipped.
    """
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.setdefault(a.name.split(".")[0], node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                names.setdefault(node.module.split(".")[0], node.lineno)
    return names


def scan(root=None):
    """[(relpath, lineno, module)] for every undeclared third-party import."""
    root = root or ROOT
    stdlib = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
    declared = _requirement_names(os.path.join(root, "requirements-test.txt"))
    # ...plus only what CI additionally installs from requirements.txt. The
    # rest of that file is the IMAGE's dependency set and is NOT in the test
    # job, so treating it as available would hide exactly this class.
    extra = {_IMPORT_ALIASES.get(n.lower(), n.lower().replace("-", "_"))
             for n in _ci_extra_names(root)}
    declared |= extra
    local = _repo_modules(root)
    findings = []
    for scan_dir in SCAN_DIRS:
        base = os.path.join(root, scan_dir)
        for dirpath, _dirs, files in os.walk(base):
            for fn in sorted(files):
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), filename=path)
                except (OSError, SyntaxError):
                    continue        # a file that cannot parse is the suite's problem
                guarded = _guarded(tree)
                for mod, lineno in sorted(_imported_names(tree).items()):
                    if (mod in stdlib or mod in declared or mod in local
                            or mod in ALLOWED_UNDECLARED or mod in guarded):
                        continue
                    findings.append((os.path.relpath(path, root), lineno, mod))
    return sorted(findings)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        return _selftest()
    findings = scan()
    if not findings:
        print("audit_test_imports: OK — every test import is stdlib, "
              "repo-local, or named in a requirements file.")
        return 0
    print("A TEST IMPORTS WHAT CI DOES NOT INSTALL — this is a RED BUILD, "
          "and it will pass on your machine:\n")
    for rel, lineno, mod in findings:
        print(f"  {rel}:{lineno}  imports `{mod}`")
    print("\nFIX, in order of preference: use the stdlib (the workflow tests "
          "here parse YAML as TEXT for exactly this reason); or GUARD it — "
          "`try: import x / except ImportError:` with the except branch "
          "asserting the degraded behaviour, the `test_margin_truth` pattern; "
          "or add the distribution to requirements-test.txt; or declare it in "
          "ALLOWED_UNDECLARED with a reason. Measured (2026-09-07): a bare "
          "`import yaml` inside a test function reddened the Tests job while "
          "passing locally, because PyYAML is present in the dev container "
          "and absent in CI.")
    return 1


def _selftest():
    import tempfile
    import textwrap

    def _tree(src):
        return ast.parse(textwrap.dedent(src))

    # AT ANY DEPTH — the whole point. A module-level scan reports this clean.
    got = _imported_names(_tree("""
        import os
        def test_x():
            import yaml
            return yaml
        class T:
            def test_y(self):
                from openpyxl import Workbook
                return Workbook
    """))
    assert set(got) == {"os", "yaml", "openpyxl"}, got

    # a relative import is repo-local by construction and must not be reported.
    # `from .foo import bar` is the case that MATTERS: it has a module name, so
    # only the `level` check excludes it — `from . import x` has module=None and
    # is skipped by a second condition, which made an earlier mutation survive.
    assert "x" not in _imported_names(_tree("from . import x"))
    assert "foo" not in _imported_names(_tree("from .foo import bar")), \
        "a relative import must be excluded by its LEVEL, not by luck"
    assert "foo" in _imported_names(_tree("from foo import bar")), \
        "...and an absolute one with the same shape must still be seen"
    assert set(_imported_names(_tree("import a.b.c"))) == {"a"}, "dotted -> top"

    # requirements parsing: specifiers, markers, comments, aliases
    with tempfile.TemporaryDirectory() as td:
        req = os.path.join(td, "r.txt")
        with open(req, "w", encoding="utf-8") as fh:
            fh.write("# comment\npytest>=8.0\nPyYAML==6.0.1\n"
                     "psycopg2-binary>=2.9 # trailing\n"
                     'tomli>=2.0; python_version < "3.11"\n'
                     "-r other.txt\nnumpy\n\n")
        names = _requirement_names(req)
    assert "yaml" in names, "PyYAML must map to its IMPORT name, not its pip name"
    assert "psycopg2" in names and "pytest" in names and "tomli" in names, names
    assert "numpy" in names and "other.txt" not in names, names
    assert _requirement_names("/no/such/file") == set(), "missing file -> empty"

    # GUARDED imports are legitimate — the two patterns already on main.
    g = _guarded(_tree("""
        try:
            import yaml
        except ImportError:
            yaml = None
        try:
            from openpyxl import Workbook
        except (ValueError, ImportError):
            Workbook = None
        import pytest
        pytest.importorskip("scipy")
        try:
            import unguarded_by_the_wrong_handler
        except ValueError:
            pass
    """))
    assert {"yaml", "openpyxl", "scipy"} <= g, g
    assert "unguarded_by_the_wrong_handler" not in g, (
        "a try/except that does NOT catch ImportError is not a guard — the "
        "module is still missing at import time")

    # END TO END, both directions, against a synthetic tree.
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "tests", "autonomy"))
        os.makedirs(os.path.join(td, "scripts"))
        with open(os.path.join(td, "requirements-test.txt"), "w") as fh:
            fh.write("pytest>=8.0\n")
        with open(os.path.join(td, "fleet_bus.py"), "w") as fh:
            fh.write("")
        # scripts/ is sys.path-inserted by the real tests: a module there is
        # LOCAL, not third-party. Missing this reported 70 false positives.
        with open(os.path.join(td, "scripts", "golive_readiness.py"), "w") as fh:
            fh.write("")
        clean = os.path.join(td, "tests", "autonomy", "test_ok.py")
        with open(clean, "w") as fh:
            fh.write("import os, json, ast\nimport pytest\nimport fleet_bus\n"
                     "import golive_readiness\n"
                     "def test_a():\n    import re\n    return re\n"
                     "def test_b():\n"
                     "    try:\n        import yaml\n"
                     "    except ImportError:\n        yaml = None\n"
                     "    return yaml\n")
        assert scan(td) == [], scan(td)

        # THE POSITIVE CONTROL, and it is the real incident rather than a
        # sketch of it: an UNGUARDED import inside a test function. Verified
        # 2026-09-07 against the actual failing commit (de8918c on PR #293),
        # where this guard reports line 124 — the line CI reported.
        # An empty result is not a negative result until the check has been
        # seen to produce a positive one (house rule, (po)).
        dirty = os.path.join(td, "tests", "autonomy", "test_bad.py")
        with open(dirty, "w") as fh:
            fh.write("def test_b():\n    import yaml\n    return yaml\n")
        found = scan(td)
        assert [f[2] for f in found] == ["yaml"], found
        assert found[0][1] == 2, f"line number must point AT the import: {found}"

        # THE IMAGE'S DEPS ARE NOT THE TEST JOB'S. A module named only in
        # requirements.txt, and NOT in the workflow's extra-install grep, is
        # absent from CI and must still be a finding — treating that whole
        # file as available would hide the very class this guard exists for.
        with open(os.path.join(td, "requirements.txt"), "w") as fh:
            fh.write("lighter-sdk==1.1.2\nwebsockets>=12.0\nrequests>=2.0\n")
        os.makedirs(os.path.join(td, ".github", "workflows"))
        _wf = os.path.join(td, ".github", "workflows", "tests.yml")
        with open(_wf, "w") as fh:
            fh.write("          grep -E '^(lighter-sdk|websockets)' "
                     "requirements.txt | xargs pip install\n")
        img = os.path.join(td, "tests", "autonomy", "test_img.py")
        with open(img, "w") as fh:
            fh.write("import requests\nimport lighter\n")
        mods = [f[2] for f in scan(td)]
        assert "requests" in mods, (
            "a distribution in requirements.txt that CI does NOT install reads "
            "as available — the image's deps are not the test job's")
        assert "lighter" not in mods, (
            "lighter-sdk IS installed by the workflow's grep and must not be "
            "reported")
        os.remove(img)

        # CI's extra installs are read from the workflow, not retyped.
        wf = os.path.join(td, ".github", "workflows", "tests.yml")
        with open(wf, "w") as fh:
            fh.write("          grep -E '^(lighter-sdk|websockets)' "
                     "requirements.txt | xargs pip install\n")
        assert _ci_extra_names(td) == {"lighter-sdk", "websockets"}, \
            _ci_extra_names(td)
        with open(wf, "w") as fh:
            fh.write("nothing to match here\n")
        assert _ci_extra_names(td) == set(CI_EXTRA_FALLBACK), \
            "an unmatched workflow must fall back, never return empty"
        assert _ci_extra_names("/no/such/root") == set(CI_EXTRA_FALLBACK)

    print("audit_test_imports selftest OK (depth, relative/dotted imports, "
          "requirements parsing with aliases and markers, guarded-import "
          "acceptance, sys.path locals, the real unguarded-yaml control, and "
          "the workflow-parsed CI extras with their fallback)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
