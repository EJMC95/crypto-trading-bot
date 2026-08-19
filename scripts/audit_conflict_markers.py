#!/usr/bin/env python3
"""[2026-08-19] NO CONFLICT MARKER REACHES A COMMIT — including a MID-LINE one.

WHY THIS EXISTS, and why the existing check was not enough. `CHANGELOG.md`
line 13890 already records this class once: *"THE SYNC CHANNEL WAS CORRUPT AND
EVERY CI RUN SAID GREEN"* — three committed stash-conflict markers surviving
seven commits with every run reporting success. The fix that incident produced
was the `changelog-check.yml` step

    git grep -nE '^(<<<<<<<|>>>>>>>|=======$)' -- .

and it is **caret-anchored**. On 2026-08-19 the same class landed again in a
new costume and walked straight past it:

    CHANGELOG.md:955
    gradeable ~mid-Sep on its OWN ledger (I14).>>>>>>> 3ce869e (The operator-
    queue sweep: carry PERSIST 6h->12h ships at the clean boundary; ...)

A rebase-form end marker appended to the END of a prose line with no newline
in front of it. Because it is not at column 0, `^` never matched, the guard
reported clean, and the marker was committed and pushed. It was found by an
adversarial body-level byte-compare against the other merge parent — which had
a clean copy of the very same entry — not by any guard.

THE RULE THIS ENFORCES, and the reason it is shaped the way it is:

  * `<<<<<<<` and `>>>>>>>` are flagged ANYWHERE on a line, not just at
    column 0. Seven-run angle brackets do not otherwise occur in this tree.
  * `=======` is flagged ONLY at column 0 and only as a whole line. It cannot
    be flagged mid-line: this repo is full of banner comments
    (`# ==============`), and a rule that fires on those would be turned off
    within a day. That asymmetry is DECLARED rather than silently chosen — the
    middle marker is the one form this guard genuinely cannot see mid-line.
  * A marker enclosed in a backtick or a quote is PROSE and is skipped. Both
    real exemptions in this tree are of that shape: the CHANGELOG entry that
    documents the first incident, and the fixtures in `audit_venue_purity.py`
    and `changelog-check.yml` that construct markers deliberately.
  * This file builds its own marker tokens with `"<" * 7` rather than writing
    them out, so the guard cannot flag its own source. That is not cleverness
    for its own sake: the anchored check it replaces could only avoid
    self-matching BY being anchored, which is precisely the property that let
    the defect through.

Exit 0 clean, 1 on a finding, 2 on a usage error. `--selftest` runs positive
controls: a guard that has never been seen to fire on a case it should catch
is not evidence of anything (CLAUDE.md, "A CHECK THAT INSPECTS NOTHING REPORTS
CLEAN, AND CLEAN READS AS EVIDENCE").
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

OPEN = "<" * 7
CLOSE = ">" * 7
MIDDLE = "=" * 7

#: Characters that mark a marker-shaped token as PROSE rather than a real
#: marker. A real conflict marker is never quoted — git writes it bare.
QUOTES = ("`", "'", '"')

#: Paths whose CONTENT is allowed to construct markers, because constructing
#: one is their job. Declared rather than pattern-matched, the `BORN_DARK_OK`
#: idiom: an exemption must name itself and say why.
FIXTURE_OK = {
    "scripts/audit_conflict_markers.py": "this guard's own selftest fixtures",
    "scripts/audit_venue_purity.py": "its selftest writes a marker fixture",
    ".github/workflows/changelog-check.yml": "carries the legacy anchored check + its fixture",
}

_TEXT_SKIP = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2",
              ".zip", ".gz", ".sqlite", ".whl", ".parquet")


def _quoted(line: str, col: int, token: str) -> bool:
    """True when the token at `col` sits INSIDE a quoted/backticked span.

    SPAN, not adjacency. My first cut tested only the characters immediately
    either side of the marker, and it was wrong within the hour: the very
    comment registering this guard reads

        # ... an anchored `git grep -nE '^(<<<<<<<|>>>>>>>|=======$)'` since ...

    where the marker is genuinely prose but the character before it is `(`, not
    a backtick. An adjacency test flags that and a span test does not. Real
    markers are written BARE by git, so being inside any balanced quote pair on
    the line is sound evidence of prose.

    Each quote character is paired independently and only BALANCED pairs count,
    so an unmatched apostrophe in prose ("the pair's clock") cannot open a span
    that swallows a real marker to its right.

    DELIBERATELY PER-LINE. A backtick span that OPENS on one line and closes on
    another does not excuse a marker between them — if it did, a real marker
    sitting on its own line anywhere inside a long quoted block would be
    invisible, and CHANGELOG.md is full of long quoted blocks. The cost is that
    prose quoting a marker must keep the marker and its quotes on ONE line;
    that cost is the feature, because it is what keeps every exclusion in this
    tree readable at a glance."""
    for q in QUOTES:
        idx = [i for i, ch in enumerate(line) if ch == q]
        # Consume in pairs; a trailing unmatched quote opens no span.
        for a, b in zip(idx[0::2], idx[1::2]):
            if a < col and col + len(token) <= b:
                return True
    return False


def findings_in(path: str, text: str) -> list[tuple[int, str]]:
    """[(lineno, line)] for every real marker in `text`."""
    out: list[tuple[int, str]] = []
    exempt = path.replace(os.sep, "/") in FIXTURE_OK
    for n, line in enumerate(text.split("\n"), 1):
        for token in (OPEN, CLOSE):
            col = line.find(token)
            if col < 0:
                continue
            if exempt:
                continue
            if _quoted(line, col, token):
                continue
            out.append((n, line))
            break
        else:
            stripped = line.rstrip()
            if stripped == MIDDLE and not exempt:
                out.append((n, line))
    return out


def tracked_files(root: str = ".") -> list[str]:
    r = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.split("\0")
            if p and not p.lower().endswith(_TEXT_SKIP)]


def audit(root: str = ".") -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for rel in tracked_files(root):
        full = os.path.join(root, rel)
        try:
            with open(full, encoding="utf-8", errors="strict") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue          # binary or unreadable — not our class
        for n, line in findings_in(rel, text):
            hits.append((rel, n, line))
    return hits


def _selftest() -> int:
    """POSITIVE CONTROLS FIRST. Each case states what it proves."""
    cases = [
        # (name, path, text, must_be_caught)
        ("line-start open", "a.md", f"{OPEN} HEAD\nx\n", True),
        ("line-start close", "a.md", f"{CLOSE} origin/main\n", True),
        ("whole-line middle", "a.md", f"a\n{MIDDLE}\nb\n", True),
        # THE INCIDENT THIS GUARD WAS BUILT FOR — the anchored check misses it.
        ("MID-LINE close (the 19-Aug defect)", "a.md",
         f"gradeable ~mid-Sep on its OWN ledger (I14).{CLOSE} 3ce869e (subj)\n",
         True),
        ("mid-line open", "a.py", f"x = 1  {OPEN} HEAD\n", True),
        # NEGATIVE CONTROLS — a guard that flags everything trains the operator
        # to ignore it (the (hh) rule).
        ("backticked prose", "a.md",
         f"carried markers (`:1` `{OPEN} Updated upstream`, `:72` `{CLOSE} Stashed changes`)\n",
         False),
        # The case that reddened this guard within an hour of writing it: the
        # marker is inside a LONGER backticked span, so nothing adjacent to it
        # is a quote. Adjacency-only prose detection flags this; span detection
        # does not. Kept as a permanent control against that regression.
        ("marker inside a longer backticked span", "a.py",
         f"# an anchored `git grep -nE '^({OPEN}|{CLOSE}|{MIDDLE}$)'` since the\n",
         False),
        # ...but an UNMATCHED apostrophe must NOT open a span that hides a real
        # marker to its right. This is the direction a span test can get wrong.
        ("unmatched apostrophe does not excuse a real marker", "a.md",
         f"the pair's clock\n{CLOSE} origin/main\n", True),
        ("banner comment", "a.py", "# " + "=" * 60 + "\n", False),
        ("shell banner", "a.sh", 'echo "' + "=" * 40 + '"\n', False),
        ("middle mid-line is NOT flagged (declared)", "a.py",
         f"# ==== SECTION {MIDDLE} ====\n", False),
        ("declared fixture file", "scripts/audit_venue_purity.py",
         f'open(p, "w").write("{OPEN} Updated upstream")\n', False),
    ]
    bad = 0
    for name, path, text, want in cases:
        got = bool(findings_in(path, text))
        if got != want:
            print(f"  SELFTEST FAIL [{name}] on {path}: caught={got} want={want}")
            bad += 1
    # The anchored check MUST miss the mid-line case — this is the whole point,
    # and pinning it means a future "simplification" back to `^` reddens here.
    import re
    anchored = re.compile(rf"^({OPEN}|{CLOSE}|{MIDDLE}$)", re.M)
    midline = f"gradeable ...(I14).{CLOSE} 3ce869e (subj)"
    if anchored.search(midline):
        print("  SELFTEST FAIL: the anchored pattern was expected to MISS the "
              "mid-line marker; if it now matches, this guard's premise moved")
        bad += 1
    # And it must still catch the line-start case, or the fixture is wrong.
    if not anchored.search(f"{CLOSE} origin/main"):
        print("  SELFTEST FAIL: anchored control did not match a line-start marker")
        bad += 1
    if bad:
        print(f"audit_conflict_markers --selftest: {bad} FAILURE(S)")
        return 1
    # COUNTED, never asserted. The hand-written "(5 positive, 5 negative)" here
    # was stale the moment two cases were added — a summary line that restates
    # the data instead of reading it is the same doc-truth rot this repo keeps
    # correcting in place, and it is worse in a guard, whose whole output IS a
    # claim about what it checked.
    pos = sum(1 for c in cases if c[3])
    print(f"audit_conflict_markers --selftest: OK — {len(cases)} cases "
          f"({pos} positive, {len(cases) - pos} negative) + 2 anchored-pattern "
          "controls")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return _selftest()
    if len(argv) > 1:
        print(__doc__)
        return 2
    hits = audit(".")
    if hits:
        print(f"audit_conflict_markers: {len(hits)} CONFLICT MARKER(S) IN "
              "TRACKED CONTENT\n")
        for rel, n, line in hits:
            print(f"  {rel}:{n}\n      {line.strip()[:160]}")
        print("\n  A marker committed here is not cosmetic: it corrupts the "
              "file for every later reader and, on CHANGELOG.md, it corrupts "
              "the entry a future session will cite.\n"
              "  If the text is deliberate PROSE about markers, wrap it in "
              "backticks; if the file's job is to construct one, declare it in "
              "FIXTURE_OK with a reason.")
        return 1
    n = len(tracked_files("."))
    print(f"audit_conflict_markers: OK — {n} tracked files, no conflict marker "
          "at line start OR mid-line")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
