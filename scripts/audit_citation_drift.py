#!/usr/bin/env python3
"""[2026-08-19 (rz)] A CITATION THAT RESOLVES IS NOT A CITATION THAT IS RIGHT.

WHY THIS EXISTS. `audit_changelog_letters.dangling_code_citations` asks one
question — *does this letter resolve to a header?* — and appends a finding only
`if letter not in known`. So a citation that resolves to the WRONG entry is
green by construction. That is its declared blind spot, and on 2026-08-19 it
cost real-money surface:

  Renumbering an entry `(ql) -> (qq)`, a `grep ... | head -40` over 48 matching
  lines silently dropped the last eight. All eight were in
  `lighter_funding_bot.py` and `venues/safety.py` — the LIVE Funding Farmer and
  SafetyRails. Seven citations of the ruin-gate entry stayed on `(ql)`, which
  by then meant a concurrent session's unrelated "CARRIED ITEMS, DISCHARGED".
  The implementation and its own test cited DIFFERENT ENTRIES, through a
  commit, a push, and a fully green CI run.

THE SIGNAL, and why it is evidence rather than a heuristic. A citation is
written against whatever the letter meant AT THAT MOMENT. So `git blame` the
citation line, read that letter's TITLE in the CHANGELOG as of the introducing
commit, and compare it to the title it carries now. If they are not the same
entry, the letter was reused underneath a citation that never moved with it.
Nothing about topic, keywords or intent is guessed.

MEASURED BEFORE IT WAS BUILT, both directions:
  * On the real incident (commit 41a9167) it flags 5 of the 7 stale sites and
    both affected FILES — enough to redden the build, which is the job.
  * On the current tree it flags 0 of 994 real citations. Zero false positives
    is what makes a guard survive contact with a busy repo; the fleet's own
    rule is that a detector which flags everything trains the operator to
    ignore it.

WHAT IT DELIBERATELY DOES NOT DO — the 44-case skip, declared rather than
defaulted into. When a letter does not exist yet at the blame commit (the code
landed before its changelog entry), this guard SKIPS it and says so in its
summary. The obvious repair — walk forward to the first commit where the letter
appears — was BUILT AND REJECTED ON MEASUREMENT: it lands on whatever the letter
transiently meant in between, and it produced a false positive immediately, on
`tests/autonomy/test_payload_contracts.py:922`, where the citation of `(kq)` is
correct today and merely passed through a window in which `(kq)` briefly meant
`🔭 GATE HORIZON` before that entry became `(ks)`. A forward walk is a guess
about intent; the blame-commit read is evidence. Skipping is the honest answer,
and the count is published so the skip is never invisible.

Also skipped, correctly rather than as a limitation: an UNCOMMITTED citation
line. Drift is a letter changing meaning AFTER a citation was written, so a
line being written right now cannot have drifted.

Fails OPEN with the arm disabled when git cannot answer (no repo, shallow
clone, missing history) — a guard that cannot read history must not invent a
verdict, and CI checks out full history for exactly this reason.

Exit 0 clean, 1 on a finding, 2 on a usage error.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ONE owner for each borrowed rule. `code_citations` is the tokenizer,
# `HEADER` the entry grammar, `same_entry` the calibrated title-similarity
# test (difflib >= 0.6: a real in-place correction measured 0.978, a genuine
# letter race 0.26). Re-implementing any of the three here would make this a
# second rule that drifts from the first.
from audit_changelog_letters import (          # noqa: E402
    HEADER, code_citations, same_entry,
)

#: Citations that are known-stale and deliberately left alone, with a reason.
#: Empty, and it should stay that way — repointing a citation is a one-token
#: edit, so an exemption here is almost always the wrong answer.
DRIFT_OK: dict[tuple[str, int], str] = {}


def _git(*args):
    try:
        r = subprocess.run(("git",) + args, capture_output=True, text=True,
                           timeout=120)
    except Exception:                       # noqa: BLE001 — no git, no arm
        return None
    return r.stdout if r.returncode == 0 else None


class Titles:
    """`letter -> title` at a revision, cached. One `git show` per revision."""

    def __init__(self):
        self._c: dict[str, dict] = {}

    def working_tree(self):
        """`letter -> title` from CHANGELOG.md on disk, or {} if unreadable."""
        try:
            txt = open("CHANGELOG.md", encoding="utf-8").read()
        except OSError:
            return {}
        d = {}
        for m in HEADER.finditer(txt):
            d.setdefault(m.group(2), m.group(3).strip())
        return d

    def at(self, rev):
        if rev not in self._c:
            txt = _git("show", f"{rev}:CHANGELOG.md")
            d = {}
            if txt:
                for m in HEADER.finditer(txt):
                    d.setdefault(m.group(2), m.group(3).strip())
            self._c[rev] = d
        return self._c[rev]


def blame_map(path):
    """`lineno -> (sha, truncated)`, or {} when git cannot answer.

    `truncated` is git's OWN boundary marker: a leading `^` means the line is
    older than the deepest commit this clone has, so its real origin is
    unknown. Stripping that caret — which is the obvious thing to do, and what
    the first cut of this guard did — silently converts "I cannot see where
    this came from" into "it came from the graft commit", and then reads a
    CHANGELOG title there as if it were evidence. In this working clone that is
    215 of 374 lines in `venues/safety.py` alone. CI checks the suite job out
    at `fetch-depth: 0`, so nothing is truncated where this guard is enforced;
    locally it degrades to skipping, and the count is published."""
    out = _git("blame", "-l", "--", path)
    if out is None:
        return {}
    m = {}
    for i, line in enumerate(out.split("\n"), 1):
        if line:
            tok = line.split(" ", 1)[0]
            m[i] = (tok.lstrip("^"), tok.startswith("^"))
    return m


def uncommitted(sha):
    """git blames a working-tree line to an all-zero sha."""
    return not sha or set(sha) <= {"0"}


def audit(paths=None):
    """-> (findings, stats). Findings are (path, line, letter, then, now, suggestion)."""
    if _git("rev-parse", "--git-dir") is None:
        return [], {"armed": False, "why": "no git repository"}
    if paths is None:
        listed = _git("ls-files", "*.py")
        if listed is None:
            return [], {"armed": False, "why": "git ls-files failed"}
        paths = listed.split()

    cites = code_citations(paths)
    titles = Titles()
    # [(rz)] `now` is the WORKING TREE, not HEAD — found by this guard's first
    # real firing, which was a FALSE POSITIVE. Mid-merge it read
    # `git show HEAD:CHANGELOG.md`, i.e. the file BEFORE the conflict was
    # resolved, and reported a citation as drifted against a letter the
    # resolution had already moved. The question this guard asks is "does this
    # citation still mean what it meant, AS THE FILE STANDS NOW" — and the file
    # that matters is the one about to be committed, which is exactly the state
    # a pre-push guard exists to judge. Falls back to HEAD when the working
    # copy is unreadable, so the arm degrades rather than disappears.
    now = titles.working_tree() or titles.at("HEAD")
    if not now:
        return [], {"armed": False, "why": "CHANGELOG.md unreadable at HEAD"}

    blames = {p: blame_map(p) for p in sorted({p for p, _, _ in cites})}
    findings = []
    stats = {"armed": True, "citations": len(cites), "checked": 0,
             "skipped_uncommitted": 0, "skipped_letter_absent": 0,
             "skipped_unresolved": 0, "skipped_truncated": 0, "exempt": 0}

    for path, line, letter in cites:
        entry = blames.get(path, {}).get(line)
        sha, truncated = entry if entry else (None, False)
        if truncated:
            stats["skipped_truncated"] += 1
            continue
        if uncommitted(sha):
            stats["skipped_uncommitted"] += 1
            continue
        then = titles.at(sha).get(letter)
        if then is None:
            # The letter did not exist yet at the introducing commit. See the
            # module docstring: the forward walk was built, measured, and
            # rejected for landing on transient meanings.
            stats["skipped_letter_absent"] += 1
            continue
        cur = now.get(letter)
        if cur is None:
            # Resolves to nothing — that is the OTHER guard's finding, not a
            # drift. Reported in the stats so it is never silently absorbed.
            stats["skipped_unresolved"] += 1
            continue
        stats["checked"] += 1
        if same_entry(then, cur):
            continue
        if (path, line) in DRIFT_OK:
            stats["exempt"] += 1
            continue
        suggest = next((l for l, t in now.items() if same_entry(then, t)), None)
        findings.append((path, line, letter, then, cur, suggest))
    return findings, stats


def _selftest():
    """Positive controls FIRST, and one of them is the REAL incident.

    A synthetic fixture proves the comparison works; replaying the actual
    commit proves the guard would have caught the thing it was built for. The
    second is the one that matters, and it is skipped rather than faked when
    the history is not present."""
    bad = 0

    # 1. the comparison itself, on titles alone
    same = ("THE FLEET COULD WATCH ITSELF APPROACH LIQUIDATION",
            "THE FLEET COULD WATCH ITSELF APPROACH LIQUIDATION AND HAD NOTHING")
    diff = ("THE FLEET COULD WATCH ITSELF APPROACH LIQUIDATION",
            "THE CARRIED ITEMS, DISCHARGED: the organ sweep is clean")
    if not same_entry(*same):
        print("  SELFTEST FAIL: an edited title must read as the SAME entry")
        bad += 1
    if same_entry(*diff):
        print("  SELFTEST FAIL: two unrelated titles must read as DIFFERENT")
        bad += 1

    # 2. THE REAL INCIDENT. At 41a9167, seven citations of (ql) pointed at the
    #    ruin-gate entry while (ql) had come to mean CARRIED ITEMS.
    incident = "41a916744fcc65a1fa6a34c85b710df5ad125154"
    if _git("cat-file", "-e", f"{incident}^{{commit}}") is None:
        print("  SELFTEST SKIP: incident commit not in this checkout "
              "(shallow clone) — the synthetic arm still ran")
    else:
        titles = Titles()
        then_t = titles.at("84e5dfde9").get("ql") if _git(
            "cat-file", "-e", "84e5dfde9^{commit}") is not None else None
        now_t = titles.at(incident).get("ql")
        if then_t is None or now_t is None:
            print("  SELFTEST SKIP: incident history present but titles "
                  "unreadable")
        elif same_entry(then_t, now_t):
            print("  SELFTEST FAIL: the real incident's two meanings of (ql) "
                  "must NOT compare as the same entry -- this guard's whole "
                  f"premise. then={then_t[:40]!r} now={now_t[:40]!r}")
            bad += 1

    # 3. END-TO-END POSITIVE CONTROL in a throwaway repo. Arms 1 and 2 pin the
    #    COMPARISON; without this one nothing pins the blame/skip plumbing that
    #    feeds it, so a mutation that made `audit()` stop detecting would redden
    #    nothing — the current tree is clean, and a guard whose detection path
    #    no test exercises is exactly the vacuous-guard shape this repo keeps
    #    paying for. Builds a real renumber: a citation is committed while a
    #    letter means one thing, then the letter is reused for another entry.
    import tempfile
    cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            def g(*a):
                subprocess.run(("git",) + a, capture_output=True, text=True)
            g("init", "-q")
            g("config", "user.email", "t@t"); g("config", "user.name", "t")
            g("config", "commit.gpgsign", "false")
            _A, _B = "z" + "z", "z" + "y"       # see the note below
            # THE ROOT COMMIT IS ALSO A BOUNDARY. git marks it with the same
            # `^` as a shallow graft, so a citation committed there would be
            # skipped as "beyond this clone's history" and the positive control
            # could never fire. Found by this arm failing on its first run —
            # which is the arm doing its job before it had ever guarded
            # anything. It is now used TWICE: as the filler that lets the
            # positive control work, and as its own NEGATIVE control below.
            open("README", "w").write("root\n")
            open("CHANGELOG.md", "w").write(
                f"## 2026-08-19 ({_A}) — THE ORIGINAL SUBJECT, liquidation\n")
            # A citation born IN the root commit, i.e. at the boundary.
            open("rootmod.py", "w").write(
                f"# [2026-08-19 ({_A})] cited from beyond the horizon\n")
            g("add", "-A"); g("commit", "-qm", "root")
            # COMPOSED, never written literally. `audit_changelog_letters`
            # tokenizes STRING literals too, so a fixture spelled out in
            # citation form here would be read as a real citation of a letter
            # that resolves to nothing — the self-reference trap that guard's
            # own docstring warns about, walked into by the guard built to
            # sit beside it. Caught by that guard, one push too late.
            _cite = f"# [2026-08-19 ({_A})] cites the original\n"
            open("mod.py", "w").write(_cite)
            g("add", "-A"); g("commit", "-qm", "one")
            # the letter is now reused for a completely different entry
            open("CHANGELOG.md", "w").write(
                f"## 2026-08-19 ({_A}) — AN ENTIRELY DIFFERENT SUBJECT, about "
                "changelog housekeeping\n")
            g("add", "-A"); g("commit", "-qm", "two")
            found, st = audit(["mod.py"])
            if not st.get("armed"):
                print(f"  SELFTEST FAIL: arm disabled in the control repo "
                      f"({st.get('why')})")
                bad += 1
            elif len(found) != 1:
                print(f"  SELFTEST FAIL: end-to-end control expected exactly 1 "
                      f"drift finding, got {len(found)} (stats={st})")
                bad += 1
            elif found[0][2] != _A:
                print(f"  SELFTEST FAIL: wrong letter reported: {found[0][2]!r}")
                bad += 1
            # NEGATIVE half: an untouched letter must NOT be flagged.
            open("CHANGELOG.md", "a").write(
                f"\n## 2026-08-19 ({_B}) — A STABLE ENTRY\n")
            open("mod2.py", "w").write(
                f"# [2026-08-19 ({_B})] cites a stable one\n")
            g("add", "-A"); g("commit", "-qm", "three")
            found2, _ = audit(["mod2.py"])
            if found2:
                print(f"  SELFTEST FAIL: a stable citation was flagged: {found2}")
                bad += 1

            # BOUNDARY NEGATIVE CONTROL — the arm two mutations survived
            # without. `rootmod.py`'s citation sits in the root commit, which
            # git marks `^`, so its true origin is unknowable in the general
            # case (a shallow graft looks identical). Its letter HAS since
            # changed meaning, so the only thing stopping a finding here is the
            # truncation skip itself. Disable that skip — or make the `^`
            # detection always return False — and this control starts flagging
            # a line whose provenance the guard cannot actually see, which is
            # precisely the unsound path the forward walk was rejected for.
            # UNCOMMITTED CONTROL. This one pins the CENSUS, not a verdict:
            # with the uncommitted branch disabled, `git show` on an all-zero
            # sha fails, the title reads None, and the line is skipped anyway —
            # so no verdict changes and only the BUCKET is wrong, reporting
            # work-in-progress as "letter not yet written". That is still a
            # false statement in a published census (I18), and the whole claim
            # of this guard's summary line is that its skips are honest.
            open("mod2.py", "a").write(
                f"# [2026-08-19 ({_A})] written but not yet committed\n")
            _f4, st4 = audit(["mod2.py"])
            if _f4:
                print(f"  SELFTEST FAIL: an UNCOMMITTED citation was judged: "
                      f"{_f4}. A line being written now cannot have drifted.")
                bad += 1
            elif st4.get("skipped_uncommitted") != 1:
                print("  SELFTEST FAIL: the uncommitted citation was not "
                      f"counted as such (stats={st4}) — a skip filed under the "
                      "wrong reason is a census that lies.")
                bad += 1
            subprocess.run(("git", "checkout", "--", "mod2.py"),
                           capture_output=True, text=True)

            found3, st3 = audit(["rootmod.py"])
            if found3:
                print("  SELFTEST FAIL: a citation at the history boundary was "
                      f"JUDGED rather than skipped: {found3}. Its origin is "
                      "unknowable — reading a title at the graft commit is a "
                      "guess wearing evidence's clothes.")
                bad += 1
            elif not st3.get("skipped_truncated"):
                print("  SELFTEST FAIL: the boundary citation was neither "
                      f"flagged nor counted as truncated (stats={st3}) — the "
                      "skip must be VISIBLE, not silent.")
                bad += 1
    except Exception as e:                      # noqa: BLE001
        print(f"  SELFTEST SKIP: end-to-end control could not run ({e})")
    finally:
        os.chdir(cwd)

    if bad:
        print(f"audit_citation_drift --selftest: {bad} FAILURE(S)")
        return 1
    print("audit_citation_drift --selftest: OK — title comparison both ways, "
          "the 19-Aug incident replayed from real history, and an end-to-end "
          "renumber control (1 drift found, 1 stable citation ignored, 1 "
          "boundary citation skipped and counted, 1 uncommitted citation "
          "counted under its own reason)")
    return 0


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) > 1:
        print(__doc__)
        return 2
    findings, stats = audit()
    if not stats.get("armed"):
        print(f"audit_citation_drift: arm DISABLED ({stats.get('why')}) — "
              "no verdict claimed")
        return 0
    if findings:
        print(f"audit_citation_drift: {len(findings)} CITATION(S) POINT AT A "
              "DIFFERENT ENTRY THAN THE ONE THEY WERE WRITTEN AGAINST\n")
        for path, line, letter, then, cur, suggest in findings:
            print(f"  {path}:{line}  cites ({letter})")
            print(f"      written against : {then[:88]}")
            print(f"      ({letter}) now means   : {cur[:88]}")
            print(f"      -> repoint to ({suggest})" if suggest else
                  "      -> the original entry no longer exists under any letter")
        print("\n  A letter was reused underneath these citations and they did "
              "not move with it.\n  The other guard cannot see this: it checks "
              "that a letter RESOLVES, not that it\n  resolves to the right "
              "entry.")
        return 1
    print("audit_citation_drift: OK — {checked} of {citations} citations "
          "verified against the entry they were written against "
          "(skipped: {skipped_letter_absent} letter-not-yet-written, "
          "{skipped_truncated} beyond this clone's history, "
          "{skipped_uncommitted} uncommitted, {skipped_unresolved} "
          "unresolved)".format(**stats))
    if stats["checked"] == 0 and stats["citations"]:
        # A run that verified NOTHING must not read as a run that found
        # nothing — the difference this repo pays for over and over.
        print("  NOTE: zero citations were actually checked. In a shallow "
              "clone that is expected; in CI (fetch-depth 0) it means the "
              "guard is inert and should be investigated.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
