#!/usr/bin/env python3
"""CHANGELOG entry-letter UNIQUENESS — the sync channel's own integrity guard.

WHY THIS EXISTS (2026-07-29 (fd)). CHANGELOG.md is how parallel Claude sessions
stay in sync, and entries cross-reference each other BY LETTER ("the (co) paths
fix", "see (az)"). A duplicated letter silently makes every such reference
ambiguous — including from TRACKED CODE (`.github/workflows/railway-redeploy.yml`
cites "(ff)"; `tests/test_selftests.py` cites "(ex)").

It has happened at least SEVEN times: 21-Jul (av)->(aw)->(ax), (bn) twice,
21-Jul (br) twice, 22-Jul (ca)/(cb), the 23-Jul (co)-(cr) QUADRUPLE — whose own
merge note promised a de-duplication follow-up that then sat unrepaired for six
days — and on 2026-07-29 alone, twice in one afternoon: one session's (ev)
collided, moved to (ex), collided AGAIN, and finally landed on (fi) only after
the other session had taken (fb) AND (fc) mid-edit — NINE recorded collisions.

Every one of those was found by a human reading the file. The rule itself was
written NOWHERE a session reads before writing — so the control that kept
failing was "remember to check", the same shape the born-dark guard exists to
replace. This is the detector; CLAUDE.md carries the rule.

THE ERA BOUNDARY IS MEASURED, NOT ASSUMED. The letter sequence is CONTINUOUS
(not per-day) and it RESTARTED at (a) on 2026-07-17: that day legitimately
carries both the tail of the old run (aa..au) and the head of the new one, so
17-Jul contains real, deliberate duplicates. From 2026-07-18 forward the only
duplicates were ever the (co)-(cr) block. Scoping to >= 2026-07-18 therefore
fails ONLY on genuine collisions and never on history. Headers with no letter
at all (all 2026-07-15 and older, pre-convention) are ignored everywhere.

    python3 scripts/audit_changelog_letters.py            # scan (CI-gating)
    python3 scripts/audit_changelog_letters.py --selftest # negative fixture
"""
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

# Measured 2026-07-29: >=07-18 isolates the current sequence from the 17-Jul
# restart day. Moving this EARLIER will fail the build on deliberate history.
ERA_START = "2026-07-18"

HEADER = re.compile(r"^## (\d{4}-\d{2}-\d{2}) \(([a-z]+)\)(.*)$", re.M)

# Deliberate, DECLARED duplicates. A letter belongs here only with a reason that
# says why it must stay ambiguous — which is almost never the right answer,
# because the whole point of a letter is to be citable. Prefer renumbering.
LETTERS_OK = {}


def scan(text):
    """-> (entries, duplicates). Pure, so the selftest can drive it."""
    entries = [(d, l, t.strip()) for d, l, t in HEADER.findall(text)
               if d >= ERA_START]
    by_letter = collections.defaultdict(list)
    for d, l, t in entries:
        by_letter[l].append((d, t))
    dups = {l: v for l, v in by_letter.items()
            if len(v) > 1 and l not in LETTERS_OK}
    return entries, dups


def main():
    if not os.path.isfile(CHANGELOG):
        print("audit_changelog_letters: CHANGELOG.md not found", file=sys.stderr)
        return 1
    entries, dups = scan(open(CHANGELOG, encoding="utf-8").read())
    if dups:
        print(f"\nDUPLICATE CHANGELOG LETTERS (era >= {ERA_START}) — every "
              f"cross-reference to these is ambiguous:\n")
        for letter, uses in sorted(dups.items()):
            print(f"  ({letter}) used {len(uses)}x:")
            for d, t in uses:
                print(f"      {d}  {t[:88]}")
        print("\nFIX: the entry that is CITED keeps the letter; the other moves "
              "to the next free one\nand records the move inline (see the "
              "convention in CLAUDE.md). Check citations with:\n"
              "  grep -rn '(<letter>)' --include='*.md' --include='*.py' "
              "--include='*.yml' .\n")
        return 1
    print(f"audit_changelog_letters: OK — {len(entries)} lettered entries since "
          f"{ERA_START}, every letter unique"
          + (f" ({len(LETTERS_OK)} declared)" if LETTERS_OK else ""))
    return 0


def _selftest():
    """The detector must FIRE on a duplicate, not merely stay quiet on a clean
    file — a guard that can only pass is not a guard."""
    clean = ("## 2026-07-29 (fa) — one\n\nbody\n\n"
             "## 2026-07-29 (fb) — two\n\nbody\n")
    _e, d = scan(clean)
    assert not d, d
    assert len(_e) == 2, _e

    dirty = clean + "\n## 2026-07-29 (fa) — a colliding third\n\nbody\n"
    _e2, d2 = scan(dirty)
    assert set(d2) == {"fa"}, d2
    assert len(d2["fa"]) == 2, d2
    assert any("colliding third" in t for _dt, t in d2["fa"]), d2

    # PRE-ERA duplicates must be tolerated: 17-Jul is the restart day and
    # legitimately carries two sequences.
    old = ("## 2026-07-17 (a) — restart head\n\nb\n\n"
           "## 2026-07-17 (a) — old-sequence tail\n\nb\n")
    _e3, d3 = scan(old)
    assert not d3 and not _e3, "pre-era headers must be ignored entirely"

    # letterless headers (pre-convention) must never crash or count
    assert scan("## 2026-07-14\n\nbody\n") == ([], {})

    # and the REAL file must parse to something (a regex that matches nothing
    # would make this guard vacuously green forever)
    real, _rd = scan(open(CHANGELOG, encoding="utf-8").read())
    assert len(real) > 50, f"parsed only {len(real)} headers — regex rot?"

    print(f"audit_changelog_letters selftest OK (fires on a duplicate; ignores "
          f"the pre-{ERA_START} restart era and letterless headers; sees "
          f"{len(real)} real entries)")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
