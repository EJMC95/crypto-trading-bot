#!/usr/bin/env python3
"""audit_undefined_names.py — a name that is READ and never BOUND, anywhere.

[2026-08-16] WHY THIS EXISTS, and it is not "we should have a linter".

Changelog entries are tagged with a two-letter code and cited from tracked code, so
when a concurrent session takes your letter you re-letter your entry — and the
cheap way to do that is a blanket `(ok)` -> `(om)` over the file. **A citation
and a one-argument call are the same six characters.** Measured 16-Aug, three
sessions in one afternoon did a blanket replace and two of them hit code:

    assert ok.returncode == 0, f"... failed:\\n{_tail(om)}"     # was _tail(ok)

That line is inside an f-string that is only evaluated when an audit FAILS, so
it was invisible until the day an audit failed — and then it replaced the
audit's real message with `NameError: name 'om' is not defined`, hiding the
diagnosis at the exact moment it was needed. Main was red on it.

The class is wider than the letter convention: any mangled or misspelled name
that a test never executes. Python binds at RUNTIME, so nothing catches it
until that line runs, and the lines least likely to run are error paths — which
is where a wrong name costs the most.

WHAT IT CHECKS. For every tracked `*.py`: parse it, collect every name BOUND
anywhere in the module (assignment, for-target, with-as, def/class, every
argument form, import, except-as, global/nonlocal, walrus, comprehension), then
report every name LOADED that is in neither that set nor `builtins`.

WHY MODULE-WIDE AND NOT PER-SCOPE — this is the design choice that makes it
usable rather than noisy. A real scope analysis would flag "used before
assignment" and cross-scope reads, and drown a 300-file repo in findings that
are almost all fine. Pooling every binding in the module is deliberately
CONSERVATIVE: it only reports a name bound in NO scope at all, which cannot be
a false positive from scoping — it is a typo, a mangled token, or a genuinely
missing import. That is exactly the blanket-replace signature.

LIMITS, declared rather than discovered later:
  * a replace that swaps one BOUND name for another bound name is invisible
    here (`_tail(ok)` -> `_tail(neg)` would parse and run) — the test suite is
    the detector for that one;
  * `from x import *` would hide bindings, so a file using it is REFUSED
    loudly rather than skipped quietly (there are none today);
  * names injected at runtime (`globals()["x"] = ...`) and read as bare `x`
    are declared in `DYNAMIC_OK` with a reason.

Exit 0 = clean. Exit 1 = findings, each as file:line:name.
`--selftest` proves the detector still sees (a fixture carrying the real bug).
"""
import ast
import builtins
import pathlib
import subprocess
import sys

_BUILTINS = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__spec__", "__package__",
    "__loader__", "__builtins__", "__debug__",
}

# name -> why it is bound somewhere this AST cannot see. A DECLARATION, not a
# mute button: each entry names the mechanism.
DYNAMIC_OK = {}


# 3.10+ only; empty on 3.9, where match statements cannot be parsed anyway
_MATCH_BINDERS = tuple(
    c for c in (getattr(ast, nm, None)
                for nm in ("MatchAs", "MatchStar", "MatchMapping"))
    if c is not None)


def bound_names(tree):
    """Every name the module binds, in any scope, by any mechanism."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
            args = getattr(n, "args", None)
            if args is not None:
                out |= _arg_names(args)
        elif isinstance(n, ast.Lambda):
            out |= _arg_names(n.args)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for alias in n.names:
                out.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
        elif _MATCH_BINDERS and isinstance(n, _MATCH_BINDERS):
            # match/case capture names. Resolved through getattr because CI
            # runs 3.11 and this repo's venv is 3.9 — `ast.MatchAs` does not
            # exist before 3.10, and referencing it directly makes the audit
            # itself a NameError-shaped defect on the machine most likely to
            # run it first. (Walked into while writing this file.)
            for attr in ("name", "rest"):
                v = getattr(n, attr, None)
                if v:
                    out.add(v)
    return out



def _arg_names(args):
    out = set()
    for a in [*args.posonlyargs, *args.args, *args.kwonlyargs,
              args.vararg, args.kwarg]:
        if a is not None:
            out.add(a.arg)
    return out


def star_imports(tree):
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom)
            and any(a.name == "*" for a in n.names)]


def scan_source(src, path="<src>"):
    """-> ([(path, line, name)], [problem strings]). Pure: no filesystem."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [], [f"{path}:{e.lineno}: SYNTAX ERROR: {e.msg}"]
    stars = star_imports(tree)
    if stars:
        return [], [f"{path}:{stars[0]}: `import *` hides bindings from this "
                    f"audit — replace it with explicit names"]
    bound = bound_names(tree) | _BUILTINS | set(DYNAMIC_OK)
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) \
                and n.id not in bound:
            found.append((path, n.lineno, n.id))
    return found, []


def tracked_py():
    out = subprocess.run(["git", "ls-files", "*.py"],
                         capture_output=True, text=True)
    return [f for f in out.stdout.split() if f.endswith(".py")]


def check(paths=None):
    paths = tracked_py() if paths is None else paths
    findings, problems = [], []
    for f in paths:
        try:
            src = pathlib.Path(f).read_text()
        except OSError as e:
            problems.append(f"{f}: unreadable: {e}")
            continue
        hits, probs = scan_source(src, f)
        findings.extend(hits)
        problems.extend(probs)
    if not findings and not problems:
        print(f"audit_undefined_names: OK — {len(paths)} tracked python files, "
              f"every loaded name is bound somewhere")
        return 0
    if problems:
        print("AUDIT COULD NOT COMPLETE:")
        for p in problems:
            print(f"  {p}")
    if findings:
        print("\nNAMES THAT ARE READ AND NEVER BOUND — each is a NameError the "
              "moment that line runs, and the lines least likely to run are "
              "error paths:")
        for f, line, name in findings:
            print(f"  {f}:{line}: {name}")
        print("\nIf a name really is bound at runtime (globals() injection), "
              "declare it in DYNAMIC_OK with the mechanism. The common cause "
              "is a blanket changelog-letter replace hitting a call: "
              "`_tail(ok)` and a `(ok)` citation are the same six characters.")
    return 1


def _selftest():
    """The detector must see the REAL incident, and stay quiet on real code."""
    # 1) the exact 16-Aug damage: a citation-shaped replace inside an f-string
    #    that only evaluates on failure
    bug = (
        "def _tail(x):\n"
        "    return x\n"
        "def t(ok):\n"
        '    assert ok.returncode == 0, f"failed:\\n{_tail(om)}"\n'
    )
    hits, probs = scan_source(bug, "bug.py")
    assert not probs, probs
    assert [h[2] for h in hits] == ["om"], hits
    assert hits[0][1] == 4, f"must name the LINE: {hits}"

    # 2) the same file, undamaged, is silent — else the audit cries wolf
    ok_src = bug.replace("_tail(om)", "_tail(ok)")
    assert scan_source(ok_src, "ok.py") == ([], []), scan_source(ok_src, "ok.py")

    # 3) every binding form the fleet actually uses must count as BOUND, or
    #    this audit reds the build on healthy code (the failure mode that gets
    #    a guard deleted rather than fixed)
    forms = (
        "import os\n"
        "from json import dumps as d\n"
        "import numpy as np\n"
        "class K:\n"
        "    attr = 1\n"
        "def f(a, /, b, *args, c=1, **kw):\n"
        "    with open('x') as fh, open('y') as gh:\n"
        "        for i, j in enumerate([a, b, c, kw, args, fh, gh]):\n"
        "            [q for q in (i, j)]\n"
        "            {k: v for k, v in {}.items()}\n"
        "    try:\n"
        "        del K\n"
        "    except ValueError as e:\n"
        "        return e, os, d, np\n"
        "    if (w := 3):\n"
        "        return w\n"
        "    g = lambda z: z\n"
        "    return g, f, print, len\n"
        "def h():\n"
        "    global LATE\n"
        "    LATE = 1\n"
        "def i():\n"
        "    return LATE\n"
    )
    hits, probs = scan_source(forms, "forms.py")
    assert (hits, probs) == ([], []), f"false positive on a normal form: {hits} {probs}"

    # 4) a real syntax error is REPORTED, not swallowed into a green run
    hits, probs = scan_source("def (:\n", "broken.py")
    assert not hits and probs and "SYNTAX ERROR" in probs[0], (hits, probs)

    # 5) `import *` is REFUSED loudly — a quiet skip would let a whole file
    #    opt out of the audit by accident
    hits, probs = scan_source("from os import *\nprint(getcwd())\n", "star.py")
    assert not hits and probs and "import *" in probs[0], (hits, probs)

    print("audit_undefined_names --selftest OK (sees the real (oq) damage, "
          "silent on the fixed line, no false positive across every binding "
          "form, reports syntax errors and refuses import *)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    sys.exit(check(sys.argv[1:] or None))
