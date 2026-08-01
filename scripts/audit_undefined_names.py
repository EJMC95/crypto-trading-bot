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


def check_source(src: str, path: str) -> tuple[list[str], bool]:
    """Return (findings, skipped). `skipped` marks an unknowable namespace."""
    tree = ast.parse(src, filename=path)
    star = any(
        isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)
        for n in ast.walk(tree)
    )
    if star:
        return [], True

    known = _bound_names(tree) | set(dir(builtins)) | MODULE_DUNDERS
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

    print("audit_undefined_names --selftest OK (fires on (ib), silent on the "
          "fix, no false positive on 10 real idioms, star-import declared)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        sys.exit(0)
    sys.exit(audit(verbose=args.verbose))
