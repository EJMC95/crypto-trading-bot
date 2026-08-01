#!/usr/bin/env python3
"""Fail the build on a name that is READ in shipped code and BOUND NOWHERE.

WHY THIS EXISTS (1-Aug (ib)). `(hp)` shipped the sole-writer guard as

    _ok_writer, _other = store.claim_writer(BOT_ROW)

into `funding_carry_bot.py`. `BOT_ROW` is bound nowhere in that file — the
module has `BOT` (the bare base) and `bot_id` (the suffixed row). Python binds
globals at runtime, so the file imports, compiles and passes `--selftest`
cleanly; the name is only resolved when the line executes. That line is at the
TOP OF THE TRADING LOOP, so every boot died on `NameError` and Railway's
`restartPolicy=always` restarted it — the guard written to PREVENT the Trail
Blazer crash-loop became one. Both carry containers crash-looped and
`perps-funding-carry-lshadow` had no writer for 25.6h while its row still read
`status: "online"`.

Nothing could have caught it. The suite tests `bot_pnl_store.claim_writer`
directly with literal strings (`test_payload_contracts.py`), never the bot's
own call site; `_selftest_basis()` exercises the funding arithmetic and never
enters `main()`; `audit_image_imports` walks IMPORTS, and this is not an
import. A `NameError` inside a long-running loop is invisible to every static
check this repo had.

THE RULE IT ENFORCES: a name read in shipped code must be bound somewhere in
its own module, or be a builtin.

DELIBERATELY CONSERVATIVE — it does not model scopes. A name is reported only
if it is bound in NO scope of the module at all. That misses shadowing
subtleties (a local read before assignment in one branch) and catches the class
that actually ships: a renamed, typo'd or never-created identifier. The trade
is on purpose — a detector that flags everything trains the operator to ignore
it, so this one is built to have no false positives rather than full coverage.

A module doing `from x import *` is SKIPPED and reported, because its global
namespace is not knowable from the AST. Silence is not an option — the skip is
printed.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Shipped surface: the bots and organs that run in a container. Tests and
# research scripts are excluded — a NameError there fails a run a human is
# watching, not a trading loop nobody is.
SCAN_DIRS = ("", "venues", "parliament", "user_data/strategies")
SKIP_DIRS = {".venv", "venv", ".git", "__pycache__", "tests", "node_modules"}

# Names Python injects into a module namespace that are not in `builtins`.
# `match` landed in 3.10 and this repo's interpreter is 3.9 — resolve the node
# classes dynamically so the guard runs on both. A tuple of whatever exists is
# safe to hand to isinstance().
_MATCH_AS = tuple(
    c for c in (getattr(ast, n, None) for n in ("MatchAs", "MatchStar")) if c
)
_MATCH_MAPPING = tuple(
    c for c in (getattr(ast, "MatchMapping", None),) if c
)

MODULE_DUNDERS = {
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__", "__path__", "__all__", "__debug__",
    "__class__",  # implicit in methods using zero-arg super()
}


def _bound_names(tree: ast.AST) -> set[str]:
    """Every name bound ANYWHERE in the module, in any scope."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(node.name)
            a = node.args
            for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs):
                bound.add(arg.arg)
            if a.vararg:
                bound.add(a.vararg.arg)
            if a.kwarg:
                bound.add(a.kwarg.arg)
        elif isinstance(node, ast.Lambda):
            a = node.args
            for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs):
                bound.add(arg.arg)
            if a.vararg:
                bound.add(a.vararg.arg)
            if a.kwarg:
                bound.add(a.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or alias.name
                bound.add(name.split(".")[0])
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.Name) and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            bound.add(node.id)
        elif _MATCH_AS and isinstance(node, _MATCH_AS) and node.name:
            bound.add(node.name)
        elif _MATCH_MAPPING and isinstance(node, _MATCH_MAPPING) and node.rest:
            bound.add(node.rest)
    return bound


def _loaded_names(tree: ast.AST) -> list[ast.Name]:
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    ]


def _module_level_bound(tree: ast.Module) -> set[str]:
    """Names bound in the MODULE namespace — imports, assignments, defs, at
    module level or inside module-level if/try/for/while/with blocks.

    Deliberately NOT descending into function or class bodies: a name imported
    inside `def f()` is bound in f's LOCAL scope and is not visible to
    module-level code. That distinction is the whole point of this arm.
    """
    out: set[str] = set()

    def add_target(node):
        for s in ast.walk(node):
            if isinstance(s, ast.Name):
                out.add(s.id)

    def visit(body):
        for n in body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    out.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name)          # the NAME is bound; the body is not visited
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    add_target(t)
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
                add_target(n.target)
            elif isinstance(n, (ast.If, ast.While)):
                visit(n.body); visit(n.orelse)
            elif isinstance(n, ast.For):
                add_target(n.target); visit(n.body); visit(n.orelse)
            elif isinstance(n, ast.With):
                for item in n.items:
                    if item.optional_vars is not None:
                        add_target(item.optional_vars)
                visit(n.body)
            elif isinstance(n, ast.Try):
                visit(n.body); visit(n.orelse); visit(n.finalbody)
                for h in n.handlers:
                    if h.name:
                        out.add(h.name)
                    visit(h.body)
    visit(tree.body)
    return out


#: Nodes that introduce their OWN scope. Descending into them would attribute
#: their locals to the module namespace. Comprehensions matter as much as
#: functions here: `[s.strip() for s in XS]` binds `s` inside the comprehension,
#: and a first cut of this arm reported 53 findings — every one of them a
#: comprehension variable, and not one a real defect. A detector that flags
#: everything trains the operator to ignore it ((ib)'s own stated principle),
#: so the arm is worth nothing until this is exact.
_OWN_SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
              ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _module_level_loads(tree: ast.Module) -> list[ast.Name]:
    """`Load` Names evaluated in the MODULE namespace.

    A hand-written recursive descent rather than `ast.walk`, because `walk` is
    a flat traversal of ALL descendants — a `continue` on a nested function
    node does not stop it from yielding that function's body, so the obvious
    implementation silently reports every local variable in the file.

    `if __name__ == "__main__":` blocks ARE module level, which is exactly
    where the 01-Aug incident lived.
    """
    out: list[ast.Name] = []

    def expr(node):
        if node is None or isinstance(node, _OWN_SCOPE):
            return
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                out.append(node)
            return
        for child in ast.iter_child_nodes(node):
            expr(child)

    def visit(body):
        for n in body:
            if isinstance(n, _OWN_SCOPE):
                # The DECORATORS and DEFAULTS of a def are evaluated in the
                # enclosing (module) scope even though the body is not.
                for d in getattr(n, "decorator_list", []) or []:
                    expr(d)
                continue
            if isinstance(n, (ast.If, ast.While)):
                expr(n.test); visit(n.body); visit(n.orelse)
            elif isinstance(n, ast.For):
                expr(n.iter); visit(n.body); visit(n.orelse)
            elif isinstance(n, ast.With):
                for item in n.items:
                    expr(item.context_expr)
                visit(n.body)
            elif isinstance(n, ast.Try):
                visit(n.body); visit(n.orelse); visit(n.finalbody)
                for h in n.handlers:
                    expr(h.type); visit(h.body)
            else:
                for child in ast.iter_child_nodes(n):
                    expr(child)
    visit(tree.body)
    return out


def check_source(src: str, path: str) -> tuple[list[str], bool]:
    """Return (findings, skipped). `skipped` marks an unknowable namespace."""
    tree = ast.parse(src, filename=path)
    star = any(
        isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)
        for n in ast.walk(tree)
    )
    if star:
        return [], True

    builtin_names = set(dir(builtins)) | MODULE_DUNDERS
    known = _bound_names(tree) | builtin_names
    findings = []
    seen: set[tuple[str, int]] = set()
    for node in _loaded_names(tree):
        if node.id in known:
            continue
        key = (node.id, node.lineno)
        if key in seen:
            continue
        seen.add(key)
        findings.append(f"{path}:{node.lineno}: reads {node.id!r}, bound nowhere")

    # [2026-08-01 (ig)] THE SCOPE ARM — the hole this guard shipped WITH.
    #
    # `(ib)` built this file the day before and declared it "deliberately
    # conservative: it does not model scopes, so it reports a name only if NO
    # scope of the module binds it". That conservatism has one guaranteed
    # false negative, and it was already live in production when the guard
    # went green over 99 modules: a name bound ONLY inside a function is not
    # visible to module-level code, so using it at module level is a certain
    # NameError — no scope modelling required to know that.
    #
    # MEASURED: `bot_learn.py:2340` and `event_sentinel.py:808` both ran
    # `store.organ_main(...)` in their `if __name__` block while binding
    # `import bot_pnl_store as store` only inside functions (3 and 4 sites).
    # Both crashed on EVERY run from ~16:00Z 31-Jul — the brain and the event
    # sentinel, dead for 14h, behind `run_all.sh`'s `|| true`. A container
    # restart could not help: they crash instantly, every cycle. The irony is
    # the point — `(hw)`'s wrapper, added so that no organ could die silently,
    # was itself what killed them, silently.
    #
    # This arm needs no scope model: module-level LOADS versus module-level
    # BINDINGS, both computed without descending into function bodies.
    mod_bound = _module_level_bound(tree) | builtin_names
    for node in _module_level_loads(tree):
        if node.id in mod_bound:
            continue
        key = (node.id, node.lineno)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            f"{path}:{node.lineno}: reads {node.id!r} at MODULE level, but it is "
            "bound only inside a function — import it at the call site")
    return findings, False


def iter_files() -> list[str]:
    out = []
    for d in SCAN_DIRS:
        root = os.path.join(REPO, d) if d else REPO
        if not os.path.isdir(root):
            continue
        if d:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
                for fn in filenames:
                    if fn.endswith(".py"):
                        out.append(os.path.join(dirpath, fn))
        else:
            for fn in sorted(os.listdir(root)):
                if fn.endswith(".py"):
                    out.append(os.path.join(root, fn))
    return sorted(set(out))


def audit(verbose: bool = False) -> int:
    findings, skipped, unparsed = [], [], []
    files = iter_files()
    for path in files:
        rel = os.path.relpath(path, REPO)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
        except OSError as exc:
            unparsed.append(f"{rel}: unreadable ({exc})")
            continue
        try:
            found, was_skipped = check_source(src, rel)
        except SyntaxError as exc:
            unparsed.append(f"{rel}: SyntaxError {exc}")
            continue
        if was_skipped:
            skipped.append(rel)
        findings.extend(found)

    print(f"audit_undefined_names: scanned {len(files)} shipped module(s)")
    for s in skipped:
        print(f"  SKIPPED (star-import, namespace unknowable): {s}")
    for u in unparsed:
        print(f"  ::error::{u}")
    if verbose and not findings:
        print("  no undefined names")
    for f in findings:
        print(f"  ::error::{f}")

    if findings or unparsed:
        print(
            f"\nFAIL: {len(findings)} undefined name(s), "
            f"{len(unparsed)} unparsed file(s).\n"
            "A name read in a trading loop that is bound nowhere is a boot "
            "crash-loop, not a lint nit — see (ib)."
        )
        return 1
    print("OK")
    return 0


def _selftest() -> None:
    """Pin BOTH directions: it must fire on the real defect and stay quiet on
    a clean module. A detector that flags everything is worth nothing."""
    # 1. The (ib) defect itself, reduced.
    bad = (
        "import store\n"
        "BOT = 'perps-funding-carry'\n"
        "def main():\n"
        "    bot_id = 'perps-funding-carry-lshadow'\n"
        "    while True:\n"
        "        ok, other = store.claim_writer(BOT_ROW)\n"
    )
    found, skipped = check_source(bad, "t.py")
    assert not skipped
    assert len(found) == 1 and "BOT_ROW" in found[0], found
    assert ":6:" in found[0], f"wrong line reported: {found}"

    # 2. The FIXED form must be silent — otherwise the guard blocks its own fix.
    good = bad.replace("BOT_ROW", "bot_id")
    found, _ = check_source(good, "t.py")
    assert found == [], found

    # 3. No false positive on the idioms this repo actually uses: builtins,
    #    comprehensions, walrus, except-as, decorators, globals, class attrs,
    #    lambdas, nested defs, star-args, module dunders.
    clean = (
        "import os, json\n"
        "from typing import Optional as Opt\n"
        "CONST = 1\n"
        "_cache = {}\n"
        "def outer(a, *args, b=2, **kw):\n"
        "    global CONST\n"
        "    total = sum(x * a for x in range(10) if x)\n"
        "    if (n := len(args)) > 0:\n"
        "        total += n\n"
        "    try:\n"
        "        json.loads('{}')\n"
        "    except ValueError as exc:\n"
        "        print(exc, os.sep, __file__)\n"
        "    f = lambda z: z + total\n"
        "    def inner():\n"
        "        return f(CONST) + len(_cache)\n"
        "    with open('/dev/null') as fh:\n"
        "        fh.read()\n"
        "    for i, (p, q) in enumerate([]):\n"
        "        del p\n"
        "        print(i, q)\n"
        "    return inner, Opt\n"
        "class K:\n"
        "    attr = CONST\n"
        "    def m(self):\n"
        "        return self.attr\n"
    )
    found, _ = check_source(clean, "clean.py")
    assert found == [], f"false positive on clean idioms: {found}"

    # 4. A star-import module is SKIPPED, not silently passed.
    found, skipped = check_source("from os.path import *\nprint(join('a','b'))\n", "s.py")
    assert skipped and found == [], (found, skipped)

    # ------------------------------------------------------------------
    # 5. THE SCOPE ARM — the (ig) incident, 01-Aug.
    #
    # bot_learn.py:2340 and event_sentinel.py:808 ran `store.organ_main(...)`
    # in their `if __name__` block while binding `import bot_pnl_store as
    # store` only INSIDE functions. Both crashed on every run for 14h — the
    # brain and the event sentinel — behind run_all.sh's `|| true`. This guard
    # was GREEN over 99 modules throughout, because (ib) declared it "does not
    # model scopes: report a name only if NO scope binds it".
    # ------------------------------------------------------------------
    incident = (
        "import sys\n"
        "def main():\n"
        "    import bot_pnl_store as store\n"
        "    return store.ping()\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(store.organ_main('k', main))\n"
    )
    found, _ = check_source(incident, "organ.py")
    assert any("MODULE level" in f and "'store'" in f for f in found), found

    # the fix: import at the call site
    fixed = incident.replace(
        "    sys.exit(store.organ_main('k', main))",
        "    import bot_pnl_store as store\n    sys.exit(store.organ_main('k', main))")
    assert check_source(fixed, "organ.py")[0] == [], check_source(fixed, "organ.py")

    # a module-level import also fixes it
    assert check_source("import bot_pnl_store as store\n" + incident,
                        "organ.py")[0] == []

    # ------------------------------------------------------------------
    # 6. NO FALSE POSITIVES on scoped constructs the fleet actually uses.
    #    The first cut of arm 5 reported 53 findings and every single one was
    #    a COMPREHENSION variable — `ast.walk` is flat, so `continue` on a
    #    nested scope does not stop it yielding that scope's body.
    # ------------------------------------------------------------------
    for ok in (
        "XS = ['a']\nWATCH = [s.strip().upper() for s in XS]\n",   # listcomp
        "XS = ['a']\nD = {k: 1 for k in XS}\n",                    # dictcomp
        "XS = ['a']\nG = (y for y in XS)\n",                       # genexp
        "XS = [1]\nS = {z for z in XS}\n",                         # setcomp
        "F = lambda q: q + 1\n",                                   # lambda arg
        "XS = [1]\nT = [b for a in XS for b in range(a)]\n",       # chained
        "def f():\n    tmp = 1\n    return tmp\n",                # function local
        "class C:\n    attr = 1\n    def m(self):\n        return self.attr\n",
        "import os\nfor fn in os.listdir('.'):\n    print(fn)\n",  # for target
        "try:\n    import json\nexcept ImportError:\n    json = None\nprint(json)\n",
        "with open('f') as fh:\n    print(fh)\n",                  # with target
    ):
        assert check_source(ok, "ok.py")[0] == [], (ok, check_source(ok, "ok.py"))

    print("audit_undefined_names --selftest OK (fires on (ib) and on (ig)'s "
          "scope defect, silent on both fixes, no false positive on 21 real "
          "idioms incl. every comprehension form, star-import declared)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        sys.exit(0)
    sys.exit(audit(verbose=args.verbose))
