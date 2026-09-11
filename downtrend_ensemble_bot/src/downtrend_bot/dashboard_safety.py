"""Spec 28: how this package may touch an EXISTING dashboard. Mostly: it may not.

THE SPEC IS A LIST OF NEVERS, and they are all the same never wearing different
clothes: **an existing dashboard is a running production system whose other
bots this package knows nothing about.** So this module is written as a
VERIFIER, not an editor. It reads a proposed patch and either certifies it as
append-only or refuses it. It does not write to the dashboard, and there is no
function here that can.

WHAT IT REFUSES, each mapped to the spec's own words:
  * "NEVER modify SLOW_LOOP / STALE_SECONDS"       -> `PROTECTED_CONSTANTS`
  * "NEVER modify filters that affect existing bots" -> `PROTECTED_CALLABLES`
  * "NEVER delete, rename or restructure existing bot entries"
  * "Only APPEND to EXPECTED, LABELS, CURRENT_BOTS"  -> `check_append_only`
  * "If /pnl.json cannot be verified, do not modify the dashboard"
                                                    -> `verify_feed`

THE FEED CHECK IS FAIL-CLOSED AND IT IS THE FIRST GATE. An unreachable feed,
an HTML error page, a JSON body with no rows -- every one of those returns
`verified=False`, and `certify` then refuses regardless of how clean the patch
looks. That ordering is the whole point: you cannot show a change is
append-only against a list of existing bots you were unable to read.
"""
from __future__ import annotations

import ast
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .logging_setup import get

log = get("dashboard")

#: Names the spec forbids touching, whatever the reason.
PROTECTED_CONSTANTS = ("SLOW_LOOP", "STALE_SECONDS", "FAST_LOOP",
                       "RETIRED_ROWS", "LEGACY_BOTS")
PROTECTED_CALLABLES = ("row_fresh", "is_fresh", "filter_rows",
                       "authoritative_row", "visible_bots")
#: Registries this package may add a row to, and may do nothing else to.
APPEND_ONLY = ("EXPECTED", "LABELS", "CURRENT_BOTS")


@dataclass
class FeedCheck:
    verified: bool
    url: str = ""
    rows: int = 0
    bots: list[str] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def verify_feed(url: str, *, timeout: float = 10.0,
                opener=urllib.request.urlopen) -> FeedCheck:
    """Read /pnl.json and prove it is the real feed.

    "Verified" means: it answered, it parsed as JSON, and it contains at least
    one row carrying a bot identifier. Anything short of that -- a timeout, a
    401, an HTML login page, an empty list -- is NOT verified, because each of
    those is indistinguishable from 'the dashboard has no bots', which is
    exactly the state under which an append would look safe and be wrong."""
    try:
        with opener(url, timeout=timeout) as fh:
            raw = fh.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return FeedCheck(False, url, error=f"unreachable: {exc!r}")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        return FeedCheck(False, url, error=f"not JSON: {exc!r}")
    rows: Sequence[Mapping[str, Any]]
    if isinstance(data, dict):
        for key in ("bots", "rows", "data"):
            if isinstance(data.get(key), list):
                rows = data[key]
                break
        else:
            rows = [v for v in data.values() if isinstance(v, dict)]
    elif isinstance(data, list):
        rows = data
    else:
        return FeedCheck(False, url, error=f"unexpected top level "
                                          f"{type(data).__name__}")
    bots = [str(r.get("bot")) for r in rows
            if isinstance(r, Mapping) and r.get("bot")]
    if not bots:
        return FeedCheck(False, url, rows=len(rows),
                         error="parsed, but no row carries a bot id -- this "
                               "is not verification, it is an empty answer")
    return FeedCheck(True, url, rows=len(rows), bots=sorted(set(bots)))


# ------------------------------------------------------------- AST checks --
def _collection_names(tree: ast.AST, name: str) -> list[str] | None:
    """The literal string members of a module-level list/tuple/dict/set."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == name:
                v = node.value
                if isinstance(v, (ast.List, ast.Tuple, ast.Set)):
                    return [e.value for e in v.elts
                            if isinstance(e, ast.Constant)
                            and isinstance(e.value, str)]
                if isinstance(v, ast.Dict):
                    return [k.value for k in v.keys
                            if isinstance(k, ast.Constant)
                            and isinstance(k.value, str)]
    return None


def _module_names(tree: ast.Module) -> set[str]:
    """Every name the MODULE defines: assignments, functions and classes.

    Two things this gets right that the first version did not. It walks
    `tree.body` rather than `ast.walk`, so a renamed LOCAL variable inside an
    unrelated function is not reported as a module-level deletion -- a guard
    that cries wolf is a guard that gets waived. And it counts FUNCTION and
    CLASS definitions, which the first version missed entirely: deleting a
    helper the dashboard's own rendering depends on passed clean, because
    only `PROTECTED_CALLABLES` and bare assignments were being compared."""
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                            ast.Name):
            out.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                out.add(a.asname or a.name.split(".")[0])
    return out


def _function_source(tree: ast.AST, src: str, name: str) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return ast.get_source_segment(src, node)
    return None


@dataclass
class PatchVerdict:
    append_only: bool
    added: dict[str, list[str]] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"append_only": self.append_only, "added": self.added,
                "violations": self.violations}


def check_append_only(before_src: str, after_src: str) -> PatchVerdict:
    """Compare two versions of a dashboard module. ADDITIONS ONLY.

    Structural, not textual: it parses both and compares the MEMBERS of the
    protected registries and the SOURCE of the protected callables. A
    reformatting of an untouched function is not a violation; a one-character
    change to `STALE_SECONDS` is."""
    v = PatchVerdict(True)
    try:
        a = ast.parse(before_src)
        b = ast.parse(after_src)
    except SyntaxError as exc:
        return PatchVerdict(False, violations=[f"unparseable: {exc}"])

    for name in APPEND_ONLY:
        old = _collection_names(a, name)
        new = _collection_names(b, name)
        if old is None and new is None:
            continue
        if old is None:
            v.violations.append(f"{name} did not exist before; this package "
                                "may only APPEND to an existing registry")
            continue
        if new is None:
            v.violations.append(f"{name} was REMOVED")
            continue
        removed = [x for x in old if x not in new]
        if removed:
            v.violations.append(f"{name}: entries removed or renamed "
                                f"{removed}")
        if new[:len(old)] != old:
            v.violations.append(f"{name}: existing entries were reordered or "
                                "rewritten; appending means adding at the end "
                                "and touching nothing before it")
        v.added[name] = [x for x in new if x not in old]

    for const in PROTECTED_CONSTANTS:
        oldv = _constant_of(a, const)
        newv = _constant_of(b, const)
        if oldv is not None and newv is not None and oldv != newv:
            v.violations.append(f"{const} changed {oldv!r} -> {newv!r}: this "
                                "is a protected dashboard constant")
        if oldv is not None and newv is None:
            v.violations.append(f"{const} was removed")

    for fn in PROTECTED_CALLABLES:
        olds = _function_source(a, before_src, fn)
        news = _function_source(b, after_src, fn)
        if olds is not None and news is None:
            v.violations.append(f"{fn}() was removed: it filters rows for "
                                "bots this package knows nothing about")
        elif olds is not None and news is not None and olds != news:
            v.violations.append(f"{fn}() was modified: a filter change "
                                "affects EVERY existing bot, not only ours")

    gone = _module_names(a) - _module_names(b)
    if gone:
        v.violations.append(f"module-level names disappeared: {sorted(gone)} "
                            "-- this package may only ADD")

    v.append_only = not v.violations
    return v


def _constant_of(tree: ast.AST, name: str) -> Any:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        return "<non-literal>"
    return None


def certify(*, feed_url: str, before_src: str, after_src: str,
            new_bot_ids: Iterable[str] = (),
            opener=urllib.request.urlopen) -> dict[str, Any]:
    """The whole spec-28 decision, in one call. Refuses by default.

    Order matters and is the point: the FEED is verified first. A patch cannot
    be certified append-only against a bot list that could not be read."""
    feed = verify_feed(feed_url, opener=opener)
    out: dict[str, Any] = {"feed": feed.as_dict(), "allowed": False}
    if not feed.verified:
        out["reason"] = ("/pnl.json could not be verified, so the dashboard "
                         "must not be modified (spec 28). "
                         f"{feed.error}")
        return out
    verdict = check_append_only(before_src, after_src)
    out["patch"] = verdict.as_dict()
    clash = [b for b in new_bot_ids if b in feed.bots]
    if clash:
        out["reason"] = (f"bot id(s) {clash} already publish to this "
                         "dashboard: adding a row under an existing id makes "
                         "two writers of one key")
        return out
    if not verdict.append_only:
        out["reason"] = "the patch is not append-only: " + "; ".join(
            verdict.violations)
        return out
    out["allowed"] = True
    out["reason"] = (f"append-only against a verified feed of {feed.rows} "
                     f"rows; adds {sum(len(x) for x in verdict.added.values())}"
                     " registry entrie(s)")
    out["note"] = ("certification is not application: this module never "
                   "writes to the dashboard. A human applies the patch.")
    return out
