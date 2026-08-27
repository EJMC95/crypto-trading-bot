#!/usr/bin/env python3
"""A CROSS-READ PAYLOAD WITHOUT `updated`+`ttl_sec` IS UNCONSUMABLE BY DESIGN.

[2026-08-27 (ut)] WHY THIS GUARD EXISTS. `market_context` published
`coin-quality` — the fleet's OWN measured per-coin execution cost, folded from
3,230 `venue_orders` book-walk rows going back to 9-Jul — as
`{"ts": ..., "coins": {...}}`. No `updated`. No `ttl_sec`.

`fleet_bus.is_fresh` reads exactly those two keys and returns False on any
exception, so **every consumer obeying the bus contract would have judged that
payload stale forever.** Which is why, for seven weeks, none was ever written:
the books that needed the number gated on a 24h-turnover PROXY instead, and a
study reconstructed the same quantity with Roll's estimator and overstated the
liquid names 5-12x, producing a refusal on the wrong binding constraint.

**A recording nothing can consume is not a slow recording, it is an absent one
— and it is worse than absent, because it looks like diligence.** Nothing in
the fleet could ask the question, so nothing did.

WHAT IT CHECKS. A key is a BUS payload when one module `save_state`s it and a
DIFFERENT module `load_state`s it — cross-module reach is the whole definition,
and it is derived by AST from the tree rather than from a hand-list that would
go stale the day a consumer is added. For every such key whose save-site
payload is a dict LITERAL, both contract fields must be present.

    python3 scripts/audit_bus_contract.py
    python3 scripts/audit_bus_contract.py --selftest

TWO REGIMES, and the second is why this reads SOURCE and never the database:
CI has no `DATABASE_URL`, so a guard that inspected live rows would silently
pass on an empty result — the vacuous-green failure this repo has already paid
for. Everything here is static.

**IT IS A RATCHET, NOT A BAR.** `RATCHET` records the backlog measured the day
this shipped. A guard that reddens the build on a pre-existing backlog gets
exempted within a day and then guards nothing ((mz)'s lesson), so the backlog
may only SHRINK and a NEW instance fails immediately. Four of the five known
instances are retired books' own durable state or payloads no consumer
freshness-checks; `coin-quality` was the one that mattered and it is fixed.

DECLARED LIMIT, stated rather than hidden: a save site whose payload is built
in a variable cannot be judged from the call site, and those are REPORTED as
unverifiable rather than counted either way. Turning an unverifiable into a
pass would make this guard exactly the kind of check that inspects nothing.
"""
import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

#: The measured backlog, 2026-08-27. MAY ONLY SHRINK.
#: Each entry is a bus key whose save-site literal lacks a contract field, with
#: the reason it is tolerated. A new key not on this list FAILS the build.
RATCHET = {
    "market-context":
        "the collector's own per-coin OI/funding snapshot. Consumed only as a "
        "ledger ATTACHMENT (lighter_funding_bot._mctx_slice) — a validation "
        "dataset written into `raw` AFTER the order executes, never a gate. "
        "No branch reads it, so freshness cannot change a trade. If anything "
        "ever GATES on it, this entry must go and the fields must be added.",
}

#: Keys that are private durable state BY CONSTRUCTION — a bot's own position
#: map, a writer claim — and must never be required to carry a TTL. These are
#: not exemptions from the contract; they are outside it.
PRIVATE_PREFIXES = ("writer:",)
PRIVATE_SUFFIXES = (":standby", ":live", ":eqguard")

_SAVE = "save_state"
#: Both read paths. `fleet_bus` wraps every consumer read in its own `_load`,
#: so a guard that watched only `load_state` saw 4 cross-read keys where the
#: live bus carries ~18 — it would have been blind to exactly the accessors
#: this contract exists to protect.
_LOADS = ("load_state", "_load")


def _pyfiles():
    out = []
    for d in (ROOT, os.path.join(ROOT, "venues"), os.path.join(ROOT, "parliament")):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".py"):
                out.append(os.path.join(d, f))
    return out


def _key_of(call):
    """First positional arg, when it is a plain string literal."""
    if not call.args:
        return None
    a = call.args[0]
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        return a.value
    return None


def _dict_fields(node):
    """String keys of a dict-shaped expression, or None if not dict-shaped.

    Handles the two forms the tree actually uses: a `{...}` literal (including
    `{**base, "updated": x}`, where the starred part contributes nothing
    knowable and the explicit keys still count) and `dict(a=1, b=2)`.
    """
    if isinstance(node, ast.Dict):
        return {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "dict"):
        return {kw.arg for kw in node.keywords if kw.arg}
    return None


def _local_dicts(tree):
    """{name: set(fields)} for `name = {...}` / `name["k"] = v` in the module.

    WITHOUT THIS THE GUARD INSPECTS ALMOST NOTHING. Measured 27-Aug: judging
    only call-site literals left 3 of 4 cross-read keys 'unverifiable' and the
    guard verified exactly ONE — decoration, and precisely the check-that-
    inspects-nothing failure this repo names. Real publishers build a payload
    in a variable and then save it.

    Deliberately FLAT (module-wide, not scope-aware) and UNION-ing every
    assignment to a name. That is the conservative direction for a guard whose
    failure mode should be a missed violation, never a false alarm: a name
    assigned two different payloads reports the union of their fields, so this
    can only ever be too lenient. Stated rather than hidden — a guard that
    over-reports gets ignored, and then guards nothing.
    """
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            f = _dict_fields(node.value)
            if f is None:
                continue
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, set()).update(f)
        # `payload["ttl_sec"] = ...` — a field added after construction.
        elif isinstance(node, ast.Assign) is False and isinstance(node, ast.Subscript):
            continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                    and isinstance(t.slice, ast.Constant)
                    and isinstance(t.slice.value, str)):
                out.setdefault(t.value.id, set()).add(t.slice.value)
    return out


def scan(files=None):
    """-> (saves, loads, fields, nonliteral) across the tree.

    saves/loads: {key: {module, ...}}
    fields: {(module, key): set(field names)} where the payload is dict-shaped
    """
    saves, loads, fields, nonliteral = {}, {}, {}, set()
    for path in (files or _pyfiles()):
        mod = os.path.basename(path)
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (SyntaxError, OSError):
            continue
        locals_ = _local_dicts(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else (fn.id if isinstance(fn, ast.Name) else None))
            if name != _SAVE and name not in _LOADS:
                continue
            key = _key_of(node)
            if key is None:
                continue
            if name in _LOADS:
                loads.setdefault(key, set()).add(mod)
                continue
            saves.setdefault(key, set()).add(mod)
            payload = node.args[1] if len(node.args) > 1 else None
            got = _dict_fields(payload) if payload is not None else None
            if got is None and isinstance(payload, ast.Name):
                got = locals_.get(payload.id)
            if got is None:
                nonliteral.add((mod, key))
            else:
                fields.setdefault((mod, key), set()).update(got)
    return saves, loads, fields, nonliteral


def _private(key):
    return (key.startswith(PRIVATE_PREFIXES)
            or key.endswith(PRIVATE_SUFFIXES))


def audit(files=None):
    saves, loads, fields, nonliteral = scan(files)
    bus, offenders, unverifiable = [], [], []
    for key, writers in sorted(saves.items()):
        if _private(key):
            continue
        readers = loads.get(key, set()) - writers
        if not readers:
            continue                      # nobody else reads it: not a bus key
        bus.append(key)
        seen = set()
        any_literal = False
        for mod in writers:
            f = fields.get((mod, key))
            if f is None:
                continue
            any_literal = True
            seen |= f
        if not any_literal:
            unverifiable.append((key, sorted(writers), sorted(readers)))
            continue
        missing = {"updated", "ttl_sec"} - seen
        if missing:
            offenders.append((key, sorted(missing), sorted(writers),
                              sorted(readers)))
    return bus, offenders, unverifiable


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    bus, offenders, unverifiable = audit()
    print(f"audit_bus_contract: {len(bus)} cross-read bus keys; "
          f"{len(offenders)} missing a contract field, "
          f"{len(unverifiable)} unverifiable (payload not a dict literal)")
    print("  COVERAGE, stated because a guard that hides how little it sees is "
          "the very\n  failure it checks for: this resolves a key only when "
          "BOTH the save and the\n  read name it as a string LITERAL. The live "
          "bus carried ~18 cross-read keys\n  on 27-Aug; many are saved under a "
          "variable (`save_state(bot_id, ...)`) and are\n  invisible here. This "
          "is a RATCHET on what is statically decidable, not a\n  census of the "
          "bus.")

    if unverifiable:
        print("\n  UNVERIFIABLE — payload built in a variable, not judged either way:")
        for key, w, r in unverifiable:
            print(f"    {key:<28} written by {','.join(w)}")

    new = [o for o in offenders if o[0] not in RATCHET]
    known = [o for o in offenders if o[0] in RATCHET]

    if known:
        print("\n  KNOWN BACKLOG (ratcheted — may only shrink):")
        for key, missing, w, r in known:
            print(f"    {key:<28} missing {'+'.join(missing)}")
            print(f"      {RATCHET[key]}")

    fixed = sorted(set(RATCHET) - {o[0] for o in offenders})
    if fixed:
        print(f"\n  RATCHET TIGHTENS — these are compliant now and must be "
              f"removed from RATCHET:")
        for k in fixed:
            print(f"    {k}")
        print("  (the backlog may only shrink; a stale entry hides the next "
              "regression)")
        return 1

    if new:
        print("\n!! NEW CONTRACT VIOLATION — a payload other modules read, that "
              "`fleet_bus.is_fresh`\n   will judge STALE FOREVER. This is the "
              "`coin-quality` defect: seven weeks of\n   a correct recording "
              "no consumer could ever read.\n")
        for key, missing, w, r in new:
            print(f"    {key}")
            print(f"      missing : {'+'.join(missing)}")
            print(f"      written : {', '.join(w)}")
            print(f"      read by : {', '.join(r)}")
        print("\n   FIX: add `updated` (ISO-8601) and `ttl_sec` to the payload at "
              "the save site.\n   If the key is genuinely private durable state, "
              "it should not be read by\n   another module at all — and if it is "
              "deliberate, add it to RATCHET with a\n   reason a reader can check.")
        return 1

    print("\naudit_bus_contract: OK — every cross-read payload carries the "
          "contract, or is\n  declared in RATCHET with a reason.")
    return 0


def selftest():
    import tempfile
    import textwrap
    ok = True

    def _case(name, src, expect_offender):
        nonlocal ok
        with tempfile.TemporaryDirectory() as d:
            w = os.path.join(d, "writer_mod.py")
            r = os.path.join(d, "reader_mod.py")
            open(w, "w").write(textwrap.dedent(src))
            open(r, "w").write("import store\nstore.load_state('k')\n")
            _, offenders, unver = audit([w, r])
            got = bool(offenders)
            if got != expect_offender:
                print(f"  FAIL {name}: offenders={offenders} unver={unver}")
                ok = False
            else:
                print(f"  ok   {name}")

    _case("missing both fields is caught",
          "import store\nstore.save_state('k', {'ts': 1, 'coins': {}})\n", True)
    _case("missing ttl_sec alone is caught",
          "import store\nstore.save_state('k', {'updated': 1})\n", True)
    _case("compliant payload passes",
          "import store\nstore.save_state('k', {'updated': 1, 'ttl_sec': 2})\n",
          False)

    # A key nobody else reads is NOT a bus key.
    with tempfile.TemporaryDirectory() as d:
        w = os.path.join(d, "solo.py")
        open(w, "w").write("import store\nstore.save_state('k', {'ts': 1})\n"
                           "store.load_state('k')\n")
        bus, offenders, _ = audit([w])
        if bus or offenders:
            print(f"  FAIL self-read key treated as bus: {bus}")
            ok = False
        else:
            print("  ok   a self-read key is not a bus key")

    # A non-literal payload is UNVERIFIABLE, never a silent pass or fail.
    with tempfile.TemporaryDirectory() as d:
        w = os.path.join(d, "varw.py")
        r = os.path.join(d, "varr.py")
        open(w, "w").write("import store\np = build()\nstore.save_state('k', p)\n")
        open(r, "w").write("import store\nstore.load_state('k')\n")
        _, offenders, unver = audit([w, r])
        if offenders or not unver:
            print(f"  FAIL non-literal: offenders={offenders} unver={unver}")
            ok = False
        else:
            print("  ok   a non-literal payload is reported unverifiable")

    # Private state is outside the contract entirely.
    for key in ("writer:some-book", "some-book:standby"):
        with tempfile.TemporaryDirectory() as d:
            w = os.path.join(d, "pw.py")
            r = os.path.join(d, "pr.py")
            open(w, "w").write(f"import store\nstore.save_state({key!r}, {{'a': 1}})\n")
            open(r, "w").write(f"import store\nstore.load_state({key!r})\n")
            bus, offenders, _ = audit([w, r])
            if bus or offenders:
                print(f"  FAIL private key {key} treated as bus")
                ok = False
            else:
                print(f"  ok   {key} is outside the contract")

    print("audit_bus_contract selftest:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
