#!/usr/bin/env python3
"""Fail the build when executable code hardcodes a date the ERA TABLES own.

THE OPERATOR'S COMPLAINT (1-Aug): *"This constant issue of things maintaining
old dates and times needs to be fixed so everything is constant. This is a
trivial issue that causes such a set back."*

He is describing a real and repeating cost. `(ii)` moved 🌾 carry's declared
policy era 17-Jul -> 31-Jul for a measured reason — a 12-day two-writer window
— and that ONE legitimate change broke **five** assertions that had nothing to
do with what they were testing:

    tests/autonomy/test_golive_era.py   assert iso == "2026-07-17"
                                        in_era("2026-07-16T12:00", ...)
                                        "era 2026-07-17" in out
                                        fixture rows dated 2026-07-1x / 2x
    scripts/golive_readiness.py         assert iso == "2026-07-17"  (selftest)
                                        in_era("2026-07-20T00:00", ...)

None of those tests is ABOUT the date. They test the suffix strip, the
open-stamp boundary rule, and the min-closes filter. They pinned the date
incidentally, so a correct change to the table read as five failures and cost
a debugging pass — the "trivial issue that causes such a set back".

THE RULE: **exactly one place may state an era date — the table that owns it.**
`scripts/golive_readiness.POLICY_ERA` and `bot_learn.ERA_START` are the owners.
Everything else derives:

    era_iso = g.POLICY_ERA[g.era_base(BOT)][0]
    era_d   = datetime.fromisoformat(era_iso).replace(tzinfo=timezone.utc)
    before  = (era_d - timedelta(hours=12)).isoformat()

so a table move propagates instead of breaking. This is the same principle the
review already applies to the go-live BARS ("never restate a standard, import
it") and to `BAR_NAMES` — applied to the other half of the gate, its SAMPLE.

SCOPE, deliberately narrow so the guard has no false positives:
  * only EXECUTABLE string constants — docstrings and bare string expressions
    are excluded, and comments never parse into the AST at all. A historical
    marker like `# [2026-07-17 BASIS FIX]` is documentation of something that
    genuinely happened on that date and must NOT move.
  * only inside `tests/**` and `--selftest` functions, which is where a frozen
    date turns a correct change into a red build.
  * only dates that EQUAL a value the tables currently hold. A date the tables
    do not know is just data.
  * the tables' own module is exempt for the declaration itself — the reason
    strings are prose ABOUT history and are supposed to name dates.

A genuine coincidence is DECLARED in `COINCIDENTAL` with its reason, the
`BORN_DARK_OK` idiom this repo uses everywhere. Silence is not an option.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

#: This guard's own path — see `iter_targets` for why it must exempt itself.
SELF_REL = "scripts/audit_era_date_literals.py"

#: (file, line-content-substring) -> why this literal is NOT a duplicated era
#: date. Keyed on content rather than line number so an unrelated edit above it
#: does not silently move the exemption onto a different literal.
COINCIDENTAL = {
    ("fleet_immune.py", "2026-07-31T14:12:06+00:00"):
        "brain-amnesia fixture: the vitals/memory timestamp skew. It shares a "
        "DATE with carry's era by accident and has no relationship to it — "
        "moving the era must not move this fixture.",
    ("fleet_immune.py", "2026-07-31T13:00:00+00:00"):
        "the paired stale-memory stamp for the same amnesia fixture; see above.",
    ("scripts/study_exit_attribution.py", "2026-07-03T18:00:00+00:00"):
        "a synthetic close time in the exit-attribution selftest. Coincides "
        "with ERA_START['crypto-trendmomo-4h'], a RETIRED strategy this study "
        "never reads.",
    ("lighter_market_scout.py", "2026-07-17"):
        "the venue basis-fix date asserted as a literal in the scout's own "
        "unit-conversion selftest — it is a statement about the VENUE's "
        "settlement schedule, not about any book's policy era.",
}


def canonical_dates():
    """The set of YYYY-MM-DD strings the era tables currently own."""
    import bot_learn
    import golive_readiness as g
    out = {iso[:10] for iso, _why in g.POLICY_ERA.values()}
    out |= {str(v)[:10] for v in bot_learn.ERA_START.values()}
    return out


def _doc_nodes(tree):
    """ids of string Constants that are docstrings or bare string statements."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) \
                and isinstance(n.value.value, str):
            out.add(id(n.value))
    return out


def scan_source(src, path, canon, selftest_only):
    """-> [(lineno, literal)] executable date literals duplicating an era date."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    docs = _doc_nodes(tree)
    roots = [tree]
    if selftest_only:
        roots = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and "selftest" in n.name]
        if not roots:
            return []
    hits = []
    for root in roots:
        for n in ast.walk(root):
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
                continue
            if id(n) in docs:
                continue
            m = _DATE.match(n.value)
            if not m or m.group(1) not in canon:
                continue
            if (path, n.value) in COINCIDENTAL:
                continue
            hits.append((n.lineno, n.value))
    return sorted(set(hits))


def iter_targets():
    """[(relpath, selftest_only)] — tests wholesale, shipped code by selftest."""
    out = []
    for d in ("tests", "tests/autonomy", "tests/real_money", "tests/financial"):
        full = os.path.join(REPO, d)
        if not os.path.isdir(full):
            continue
        for fn in sorted(os.listdir(full)):
            if fn.endswith(".py"):
                out.append((f"{d}/{fn}", False))
    for d in ("", "scripts"):
        full = os.path.join(REPO, d) if d else REPO
        for fn in sorted(os.listdir(full)):
            if not fn.endswith(".py"):
                continue
            rel = f"{d}/{fn}" if d else fn
            # THIS FILE is exempt, and the exemption is narrow and necessary
            # rather than convenient: its own selftest must build synthetic
            # sources CONTAINING canonical dates in order to prove the matcher
            # fires on them. Scanning itself would make the guard permanently
            # red on its own test fixtures. Printed by `audit`, never silent.
            if rel == SELF_REL:
                continue
            # the tables' own module states its dates in the declaration
            out.append((rel, True))
    return out


def audit(verbose=False):
    canon = canonical_dates()
    findings = []
    for rel, selftest_only in iter_targets():
        path = os.path.join(REPO, rel)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                src = f.read()
        except OSError:
            continue
        for ln, lit in scan_source(src, rel, canon, selftest_only):
            findings.append(f"{rel}:{ln}: hardcodes {lit!r}, a date the era "
                            "tables own — derive it from POLICY_ERA/ERA_START")
    print(f"audit_era_date_literals: {len(canon)} canonical era date(s): "
          f"{', '.join(sorted(canon))}")
    if verbose and not findings:
        print("  no hardcoded era dates in executable test/selftest code")
    for f in findings:
        print(f"  ::error::{f}")
    if COINCIDENTAL:
        print(f"  {len(COINCIDENTAL)} declared coincidence(s) (not duplicates)")
    print(f"  SKIPPED (its selftest must contain canonical dates): {SELF_REL}")
    if findings:
        print(f"\nFAIL: {len(findings)} hardcoded era date(s).\n"
              "One legitimate table move must not redden a test that is not "
              "about the date. Derive it:\n"
              "    era_iso = g.POLICY_ERA[g.era_base(BOT)][0]\n"
              "    era_d = datetime.fromisoformat(era_iso).replace(tzinfo=utc)\n"
              "…or declare a genuine coincidence in COINCIDENTAL with a reason.")
        return 1
    print("OK")
    return 0


def _selftest():
    canon = {"2026-07-31", "2026-07-17"}

    # 1. FIRES on an executable literal in a test.
    src = 'def test_x():\n    assert iso == "2026-07-31"\n'
    assert scan_source(src, "tests/t.py", canon, False), "missed a duplicate"

    # 2. SILENT on the derived form — the whole point.
    ok = ('def test_x():\n'
          '    era_iso = g.POLICY_ERA[b][0]\n'
          '    assert iso == era_iso\n')
    assert scan_source(ok, "tests/t.py", canon, False) == [], "false positive"

    # 3. SILENT on documentation. A historical marker records something that
    #    really happened on that date and must never move with the table.
    for doc in ('x = 1  # [2026-07-17 BASIS FIX] the venue changed\n',
                '"""Fixed on 2026-07-17, see the note."""\nx = 1\n',
                'def f():\n    """Since 2026-07-31 this is guarded."""\n    return 1\n'):
        assert scan_source(doc, "tests/t.py", canon, False) == [], doc

    # 4. A date the tables do NOT own is just data.
    assert scan_source('def test_x():\n    d = "2026-01-01"\n',
                       "tests/t.py", canon, False) == []

    # 5. Shipped code is scanned only inside selftests — a fixture in a normal
    #    function is data, and flagging it would train everyone to ignore this.
    ship = ('def main():\n    d = "2026-07-17"\n'
            'def _selftest():\n    assert x == "2026-07-31"\n')
    hits = scan_source(ship, "mod.py", canon, True)
    assert len(hits) == 1 and hits[0][1] == "2026-07-31", hits

    # 6. A DECLARED coincidence is exempt, and only for its own file+literal.
    COINCIDENTAL[("tests/probe.py", "2026-07-17")] = "x" * 40
    try:
        assert scan_source('def test_x():\n    d = "2026-07-17"\n',
                           "tests/probe.py", canon, False) == []
        assert scan_source('def test_x():\n    d = "2026-07-17"\n',
                           "tests/other.py", canon, False), (
            "an exemption leaked to another file")
    finally:
        COINCIDENTAL.pop(("tests/probe.py", "2026-07-17"))

    # 7. Every declared coincidence carries a real reason.
    for key, why in COINCIDENTAL.items():
        assert isinstance(why, str) and len(why) >= 40, key

    # 8. The canonical set is non-empty — a guard over zero dates is vacuous.
    assert canonical_dates(), "no canonical era dates found; guard is vacuous"

    print("audit_era_date_literals --selftest OK (fires on a duplicate, silent "
          "on the derived form and on documentation, selftest-scoped in shipped "
          "code, exemptions file-local and reasoned)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
        raise SystemExit(0)
    raise SystemExit(audit(a.verbose))
