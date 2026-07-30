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


def cross_branch(mine, theirs):
    """-> {letter: (my_title, their_title)} for letters BOTH sides used with
    DIFFERENT titles. Pure, so the selftest can drive it.

    WHY (2026-07-30 (hj)). The in-file check above cannot see the collision
    that actually keeps happening: two sessions on two BRANCHES each pick "the
    next free letter" from their own snapshot, and each file is internally
    unique right up until the merge. That is the documented failure mode —
    CLAUDE.md's rule 2 says pick the letter at PUSH time — and on 2026-07-30 it
    bit again: main's entry and a branch's entry both landed as (fz), and the
    loser had already been renumbered once before ((fx) -> (fz) -> (gi)).

    SAME letter + SAME title is a merge/rebase of the same entry, not a
    collision — comparing titles rather than letters alone is what keeps this
    quiet on every ordinary branch.
    """
    theirs_by_letter = {l: t for _d, l, t in theirs}
    out = {}
    for _d, letter, title in mine:
        other = theirs_by_letter.get(letter)
        if other is not None and other != title:
            out[letter] = (title, other)
    return out


def _baseline_changelog():
    """origin/main's CHANGELOG, or None when it is unavailable/irrelevant.

    Fail-SAFE OPEN and deliberately so: no git, a shallow clone with no
    origin/main, or running ON main itself all return None and the guard keeps
    its pre-existing in-file behaviour. This arm can only ADD a finding.
    """
    import subprocess
    def _git(*a):
        try:
            r = subprocess.run(("git",) + a, cwd=ROOT, capture_output=True,
                               text=True, timeout=20)
        except Exception:                      # noqa: BLE001 — no git, no arm
            return None
        return r.stdout if r.returncode == 0 else None

    base = (_git("rev-parse", "origin/main") or "").strip()
    mine = (_git("rev-parse", "HEAD") or "").strip()
    if not base or base == mine:
        return None                            # nothing to compare against
    # NOTE: deliberately NOT skipped when the local branch is called "main".
    # My first cut excluded it, and that disabled this arm in the exact
    # workflow this repo actually uses — sessions commit straight to local
    # `main` and push. It was disabled on the very run that would have caught
    # (gm) being taken by a concurrent session. What matters is whether HEAD
    # has diverged from origin/main, not what the local ref is called.
    return _git("show", "origin/main:CHANGELOG.md")


def main():
    if not os.path.isfile(CHANGELOG):
        print("audit_changelog_letters: CHANGELOG.md not found", file=sys.stderr)
        return 1
    entries, dups = scan(open(CHANGELOG, encoding="utf-8").read())
    base_text = _baseline_changelog()
    if base_text:
        clashes = cross_branch(entries, scan(base_text)[0])
        if clashes:
            print("\nCROSS-BRANCH CHANGELOG LETTER COLLISION — this branch and "
                  "origin/main both used\nthese letters for DIFFERENT entries. "
                  "Every citation to them is ambiguous after the merge:\n")
            for letter, (mine_t, theirs_t) in sorted(clashes.items()):
                print(f"  ({letter})")
                print(f"      this branch : {mine_t[:84]}")
                print(f"      origin/main : {theirs_t[:84]}")
            print("\nFIX: the entry that is CITED FROM TRACKED CODE keeps the "
                  "letter; the other moves\nto the next free one and records "
                  "the move inline. Decide by grepping the tree:\n"
                  "  grep -rn '(<letter>)' --include='*.md' --include='*.py' "
                  "--include='*.yml' .\n")
            return 1
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

    # ---- CROSS-BRANCH arm (hj): the collision the in-file check CANNOT see --
    # Reproduces 2026-07-30 exactly: both sides internally unique, both used
    # (fz) for a different entry.
    _mine = scan("## 2026-07-30 (fz) — THE OFFENSE PASS\n\nb\n")[0]
    _main = scan("## 2026-07-30 (fz) — a THIRD era-pooling error\n\nb\n")[0]
    assert set(cross_branch(_mine, _main)) == {"fz"}, cross_branch(_mine, _main)
    assert cross_branch(_mine, _main)["fz"] == (
        "— THE OFFENSE PASS", "— a THIRD era-pooling error")
    # SAME letter + SAME title is a rebase/merge of the same entry, NOT a
    # collision. Without this the guard would fire on every ordinary branch
    # that merged main in — i.e. it would be turned off within a day.
    assert cross_branch(_mine, _mine) == {}
    # a letter only one side has is not a collision either
    _other = scan("## 2026-07-30 (hj) — something else\n\nb\n")[0]
    assert cross_branch(_mine, _other) == {}
    assert cross_branch([], _main) == {} and cross_branch(_mine, []) == {}
    # the pre-era scope applies here too — 17-Jul's restart must not clash
    _pre = scan("## 2026-07-17 (a) — restart head\n\nb\n")[0]
    assert cross_branch(_pre, scan("## 2026-07-17 (a) — tail\n\nb\n")[0]) == {}
    # fail-SAFE: the baseline arm must never raise, whatever git says here
    _b = _baseline_changelog()
    assert _b is None or isinstance(_b, str), type(_b)

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
