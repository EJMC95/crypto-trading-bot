#!/usr/bin/env python3
"""audit_doctrine_enforcement.py — every INVARIANT names what enforces it.

WHY (2026-07-31 (hy), operator: "all of the breakthroughs and milestones we
reach must be doctrines that serve as building blocks so we stop this
perpetual cycle of going back to the same square one routine").

THE MEASUREMENT THAT MOTIVATED IT, taken the same day: CLAUDE.md carried **31
rule-shaped doctrines across 1,405 lines** against **7 executable guards** in
CI. So most doctrine in this repo is prose, and prose is remembered or it is
not.

THE SESSION ITSELF IS THE CONTROLLED EXPERIMENT, and it is not flattering:

  RULES READ AND VIOLATED ANYWAY (all already written in CLAUDE.md):
    * "pick a test that could detect the damage" — violated TWICE on one row.
      A monitor compared a bot_pnl payload's CONTENT 20 times and never read
      `age_sec`, so a book that had been DEAD for 13 hours read as a stable
      live writer. I quoted this rule while breaking it.
    * "unknown degrades to the OLD id, never to a guess" — written in (ht),
      and one entry later I guessed which Railway service owned a row from an
      absence with no control group.

  THINGS THAT ACTUALLY CAUGHT ERRORS, same session:
    * audit_deploy_coverage      -> a comma-joined `svcs=` value that would
                                    have orphaned 7 files
    * audit_changelog_letters    -> two separate letter collisions, pre-push
    * a selftest                 -> a wrong assumption about `"1 "` stripping
    * mutation testing           -> defects inside guards I had just written
    * the live payload           -> a detector that fired NOTHING on the
                                    condition it was built for

THE RULE THIS FILE ENFORCES: a doctrine listed under THE INVARIANTS must
declare either the executable artifact that enforces it, or an explicit
UNENFORCED reason. A doctrine with neither is the failure mode above — it will
be re-learned, and the re-learning is the "square one routine".

WHAT THIS CANNOT DO, stated so nobody reads more into a green run: it verifies
that a declared enforcement EXISTS, not that it is CORRECT. A test named in an
ENFORCED BY line could be vacuous. This closes the "doctrine with no teeth"
class; it does not grade the teeth. Mutation testing is what grades the teeth,
and that stays a human discipline.

Usage:
  python3 scripts/audit_doctrine_enforcement.py
  python3 scripts/audit_doctrine_enforcement.py --selftest
"""
import argparse
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
DOC = os.path.join(ROOT, "CLAUDE.md")

BEGIN = "<!-- INVARIANTS:BEGIN -->"
END = "<!-- INVARIANTS:END -->"

#: An invariant heading: `### I3 · SOME TITLE`
RE_HEAD = re.compile(r"^###\s+(I\d+)\s+·\s+(.+?)\s*$", re.M)
#: `ENFORCED BY: \`path::symbol\`, \`path\`` — one or more backticked refs
RE_ENFORCED = re.compile(r"^\s*ENFORCED BY:\s*(.+?)\s*$", re.M)
RE_UNENFORCED = re.compile(r"^\s*UNENFORCED:\s*(.+?)\s*$", re.M)
RE_REF = re.compile(r"`([^`]+)`")

MIN_REASON = 25


def block(text):
    """The INVARIANTS region of the doc, or '' when the markers are absent."""
    i, j = text.find(BEGIN), text.find(END)
    if i < 0 or j < 0 or j < i:
        return ""
    return text[i + len(BEGIN):j]


def parse(text):
    """-> [{id, title, body, enforced:[refs], unenforced:str|None}] in order."""
    blk = block(text)
    heads = list(RE_HEAD.finditer(blk))
    out = []
    for n, m in enumerate(heads):
        body = blk[m.end():(heads[n + 1].start() if n + 1 < len(heads) else len(blk))]
        enf = RE_ENFORCED.search(body)
        unenf = RE_UNENFORCED.search(body)
        out.append({
            "id": m.group(1), "title": m.group(2), "body": body,
            "enforced": RE_REF.findall(enf.group(1)) if enf else [],
            "enforced_raw": enf.group(1) if enf else None,
            "unenforced": unenf.group(1) if unenf else None,
        })
    return out


def check_ref(ref, root=None):
    """-> None if the reference resolves, else why it does not.

    `path::symbol` requires the symbol to appear in the file; a bare `path`
    only requires the file. Symbols are matched as plain substrings on
    purpose: this asks "does the named thing still exist", not "is it called
    correctly" — the latter is the enforcement's own job, and an over-clever
    matcher here would fail on every legitimate rename of a call site.
    """
    root = ROOT if root is None else root
    path, _, sym = ref.partition("::")
    path = path.strip()
    full = os.path.join(root, path)
    if not os.path.exists(full):
        return f"no such file: {path}"
    if not sym:
        return None
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError as e:
        return f"unreadable ({e})"
    return None if sym.strip() in src else f"{path} no longer contains {sym.strip()!r}"


def audit(text, root=None):
    """-> (findings, invariants). A finding is a string naming what is wrong."""
    inv = parse(text)
    bad = []
    if not block(text).strip():
        return ["CLAUDE.md has no INVARIANTS block (markers missing or empty)"], inv
    if not inv:
        return ["the INVARIANTS block declares no invariants"], inv
    # [2026-08-28 (vd)] AN INVARIANT WRITTEN OUTSIDE THE MARKERS WAS SILENTLY
    # IGNORED — the exact hole this guard exists to close, in the guard itself.
    #
    # I26 was appended immediately BEFORE the "Acknowledged recurrence" heading
    # and landed 27 characters AFTER `<!-- INVARIANTS:END -->`. `parse()` reads
    # only the bounded block, so the new doctrine had NO enforcement checking
    # at all — and this audit reported a clean 25 while the file held 26. A
    # doctrine the guard cannot see is doctrine with no teeth, which is the
    # sentence at the top of CLAUDE.md.
    #
    # Cheap to detect and impossible to argue with: count the headings in the
    # WHOLE document and compare. Naming the stray ids matters more than the
    # count — "26 in the file, 25 audited" sends the reader hunting (I8).
    strays = [m.group(1) for m in RE_HEAD.finditer(text)
              if m.group(1) not in {e["id"] for e in inv}]
    if strays:
        bad.append(
            f"invariant(s) {sorted(set(strays))} sit OUTSIDE the "
            f"{BEGIN}/{END} markers and are NOT audited — move them inside, "
            f"or they are doctrine with no enforcement checking")
    seen = {}
    for e in inv:
        tag = f"{e['id']} ({e['title'][:44]})"
        if e["id"] in seen:
            bad.append(f"{tag}: duplicate id, already used by {seen[e['id']][:44]!r}")
        seen[e["id"]] = e["title"]
        if e["enforced"] and e["unenforced"]:
            bad.append(f"{tag}: declares BOTH enforced and unenforced")
            continue
        # ORDER MATTERS: a bare `ENFORCED BY: some test somewhere` is a CLAIM
        # WITH NO REFERENT, which is a different (and more misleading) defect
        # than declaring nothing at all — it reads as enforced to a human
        # skimming the section. Diagnose it as itself. Caught by this file's
        # own selftest, which is the point of writing one.
        if e["enforced_raw"] is not None and not e["enforced"]:
            bad.append(f"{tag}: ENFORCED BY has no `backticked` reference — a "
                       f"claim with no referent reads as enforced and is not")
            continue
        if not e["enforced"] and e["unenforced"] is None:
            bad.append(f"{tag}: no ENFORCED BY and no UNENFORCED — a doctrine "
                       f"with neither is prose, and prose is what gets "
                       f"re-learned")
            continue
        if e["unenforced"] is not None:
            if len(e["unenforced"].strip()) < MIN_REASON:
                bad.append(f"{tag}: UNENFORCED needs a real reason "
                           f"(>={MIN_REASON} chars), got {e['unenforced']!r}")
            continue
        for ref in e["enforced"]:
            why = check_ref(ref, root)
            if why:
                bad.append(f"{tag}: enforcement `{ref}` is broken — {why}")
    return bad, inv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    try:
        with open(DOC, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"audit_doctrine_enforcement: cannot read CLAUDE.md ({e})")
        return 1
    bad, inv = audit(text)
    enforced = sum(1 for e in inv if e["enforced"])
    if bad:
        print("DOCTRINE WITHOUT TEETH — each of these will be re-learned:\n")
        for b in bad:
            print(f"  {b}")
        print("\n  Fix: give the invariant an `ENFORCED BY: `path::symbol``, or")
        print("  DECLARE `UNENFORCED: <why that is currently acceptable>`.")
        print(f"\naudit_doctrine_enforcement: {len(bad)} problem(s) "
              f"over {len(inv)} invariant(s)")
        return 1
    print(f"audit_doctrine_enforcement: {len(inv)} invariant(s), "
          f"{enforced} with executable enforcement, "
          f"{len(inv) - enforced} declared unenforced.")
    return 0


def _selftest():
    good = f"""
prose before
{BEGIN}
### I1 · A THING
Some text.
  ENFORCED BY: `CLAUDE.md`
### I2 · ANOTHER THING
  UNENFORCED: no cheap executable check exists for this one yet, and saying so
{END}
prose after
"""
    bad, inv = audit(good)
    assert not bad, bad
    assert [e["id"] for e in inv] == ["I1", "I2"], inv

    # NO MARKERS -> the block is missing, which is itself the finding. Without
    # this the guard would pass vacuously on a doc that lost its section.
    assert audit("nothing here")[0], "a missing block must FAIL, not pass"
    assert audit(f"{BEGIN}\n{END}")[0], "an empty block must fail"

    # THE CORE RULE: a doctrine with neither declaration fails.
    neither = f"{BEGIN}\n### I1 · A RULE\njust prose\n{END}"
    b, _ = audit(neither)
    assert b and "no ENFORCED BY" in b[0], b

    # [(vd)] AN INVARIANT OUTSIDE THE MARKERS FAILS. Without this arm the guard
    # passes on a doc whose newest doctrine it cannot see — which is exactly
    # what happened to I26 on the day this was added.
    stray = (f"{BEGIN}\n### I1 · IN\n  ENFORCED BY: `scripts/"
             f"audit_doctrine_enforcement.py`\n{END}\n"
             f"### I2 · OUTSIDE\n  ENFORCED BY: `scripts/"
             f"audit_doctrine_enforcement.py`\n")
    b, _ = audit(stray)
    assert b and "OUTSIDE" in b[0] and "I2" in b[0], b
    # and a doc with everything inside must stay clean, or the arm is a blocker
    ok_all = (f"{BEGIN}\n### I1 · IN\n  ENFORCED BY: `scripts/"
              f"audit_doctrine_enforcement.py`\n{END}\n")
    b, _ = audit(ok_all)
    assert not b, b

    # a BROKEN enforcement reference fails — this is the arm that catches a
    # guard being deleted or renamed out from under its doctrine
    gone = f"{BEGIN}\n### I1 · X\n  ENFORCED BY: `scripts/does_not_exist.py`\n{END}"
    b, _ = audit(gone)
    assert b and "no such file" in b[0], b
    missing_sym = (f"{BEGIN}\n### I1 · X\n  ENFORCED BY: "
                   f"`CLAUDE.md::zzz_not_in_this_file_zzz`\n{END}")
    b, _ = audit(missing_sym)
    assert b and "no longer contains" in b[0], b

    # a lazy UNENFORCED reason fails — "TODO" must not buy an exemption
    lazy = f"{BEGIN}\n### I1 · X\n  UNENFORCED: TODO\n{END}"
    b, _ = audit(lazy)
    assert b and "real reason" in b[0], b

    # both declarations at once is ambiguous, and ambiguity resolves to FAIL
    both = (f"{BEGIN}\n### I1 · X\n  ENFORCED BY: `CLAUDE.md`\n"
            f"  UNENFORCED: because reasons that are long enough to pass\n{END}")
    b, _ = audit(both)
    assert b and "BOTH" in b[0], b

    # duplicate ids make every cross-reference ambiguous — the same failure
    # the changelog-letter guard exists for
    dup = (f"{BEGIN}\n### I1 · FIRST\n  ENFORCED BY: `CLAUDE.md`\n"
           f"### I1 · SECOND\n  ENFORCED BY: `CLAUDE.md`\n{END}")
    b, _ = audit(dup)
    assert b and "duplicate id" in b[0], b

    # ENFORCED BY with no backticks is a claim with no referent
    nobt = f"{BEGIN}\n### I1 · X\n  ENFORCED BY: some test somewhere\n{END}"
    b, _ = audit(nobt)
    assert b and "no `backticked` reference" in b[0], b

    # ...and the REAL doc must pass, or this guard is decorative
    with open(DOC, encoding="utf-8") as f:
        real = f.read()
    rbad, rinv = audit(real)
    assert not rbad, f"CLAUDE.md's own invariants do not pass:\n" + "\n".join(rbad)
    assert len(rinv) >= 3, f"expected a seeded invariant list, got {len(rinv)}"

    print(f"audit_doctrine_enforcement selftest OK (missing block, no "
          f"declaration, broken ref, missing symbol, lazy reason, both, "
          f"duplicate id, bare claim; real doc has {len(rinv)} invariants)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
