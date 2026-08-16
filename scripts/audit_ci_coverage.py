#!/usr/bin/env python3
"""audit_ci_coverage.py — is the code that REACHED CONTAINERS covered by a
green test verdict?

WHY THIS EXISTS (2026-08-16 (pc)). The two workflows disagree about what a
burst of pushes means, and the disagreement is silent:

    Tests            concurrency: cancel-in-progress: TRUE   -> verdict dropped
    Railway Redeploy concurrency: cancel-in-progress: FALSE  -> deploy still runs

So on a busy day the deploy always happens and the verdict often does not.
MEASURED 16-Aug across a 4-hour window: **27 of 60 Tests runs cancelled (45%)**
against **41 successful deploy runs and zero failures** — code reached
containers from commits CI never graded.

`cancel-in-progress` is CORRECT and this guard does not argue with it: an
ungraded commit that sits INSIDE a green descendant is covered transitively,
which is how most of them resolve, and re-running the suite on every superseded
push is the quota burn the flag was added to stop ((the 28-Jul note in
tests.yml)). The failure this catches is narrower and real: **the tip settles
with no green verdict, while commits that touched deploy paths have already
shipped.** That is what turned a standing red into a manual bisect on 16-Aug.

WHAT IT REPORTS
  * `last_green`   — most recent commit with a successful Tests run
  * `ungraded`     — commits after it, up to the tip
  * `shipped`      — of those, the ones that touched a deploy path, i.e. the
                     ones that actually reached a container

VERDICTS
  OK        the deployed code is covered — the tip is green, its run is still
            in flight, or the ungraded commits SHIPPED NOTHING (docs, tests
            and changelog entries reach no container, so the last green
            commit is still what is running)
  UNGRADED  ungraded commits reached a container. The only failing state, and
            deliberately so: firing on a doc-only push would train the reader
            to ignore it, which is the `(gl)` cry-wolf shape this repo has
            paid for. The count of SHIPPED commits is the signal; the count
            of ungraded ones is context.
  UNKNOWN   the run history could not be read

FAIL-CLOSED, and the reason is written on the repo's own scar tissue: `(mq)`
("the currency guard had no answer for 7 of 27 rows, and said OK") and `(kw)`
(a sweep that is DARK must never be byte-identical to a sweep that is CLEAN).
An unreadable history exits 2. It does not pass.

    python3 scripts/audit_ci_coverage.py             # scan
    python3 scripts/audit_ci_coverage.py --gha       # + step-summary table
    python3 scripts/audit_ci_coverage.py --selftest  # negative fixtures
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The workflow whose verdict counts as "graded".
WORKFLOW = os.environ.get("CI_COVERAGE_WORKFLOW", "Tests")

#: A commit "ships" when it touches something a deploy rule watches. An
#: ALLOW-LIST, deliberately: the first draft also carried a deny-list
#: (`tests/`, `docs/`, `CHANGELOG.md`...) and a mutation proved every entry of
#: it INERT — `tests/foo.py` is already excluded because it has a slash and
#: sits under no shipping prefix. A dead guard clause that reads like a live
#: one is worse than none, so it is gone and the positive rules stand alone.
#: Kept BROAD rather than copying the workflow's exact greps: a narrower copy
#: would be a second copy of the deploy rule ((hj)) and would UNDERCOUNT what
#: shipped, the wrong direction for a guard whose job is refusing to overstate
#: safety.
SHIP_PREFIXES = (
    "venues/", "user_data/", "parliament/", "scripts/golive_readiness.py",
)
#: Top-level `*.py` only. A nested one (`tests/`, most of `scripts/`) is not in
#: any image, which is why the slash test carries the whole exclusion.
SHIP_SUFFIX = ".py"
SHIP_EXACT = ("run_all.sh", "requirements.txt")


def _git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True).stdout.strip()


def ships(paths):
    """True when a commit's file list would reach a container.

    Absent/empty -> False: a commit we cannot read the files of makes no
    claim here (the count it feeds is a floor, and `runs` reading dark is the
    thing that exits 2, not this).
    """
    for p in paths or ():
        if p.startswith(SHIP_PREFIXES):
            return True
        if p.endswith(SHIP_SUFFIX) and "/" not in p:
            return True
        if p in SHIP_EXACT or p.startswith("Dockerfile"):
            return True
    return False


def fetch_runs(limit=60):
    """[(sha, conclusion, status)] newest first for WORKFLOW, or None if the
    history cannot be read. None is the UNKNOWN verdict — never an empty list,
    because "no runs" and "could not ask" must not collapse ((kw))."""
    try:
        out = subprocess.run(
            ["gh", "run", "list", "--workflow", WORKFLOW, "--limit", str(limit),
             "--json", "headSha,conclusion,status"],
            cwd=ROOT, capture_output=True, text=True, timeout=90)
        if out.returncode != 0:
            return None
        rows = json.loads(out.stdout or "[]")
    except Exception:                      # noqa: BLE001 — dark is an answer
        return None
    if not isinstance(rows, list):
        return None
    return [(r.get("headSha") or "", r.get("conclusion") or "",
             r.get("status") or "") for r in rows]


def assess(runs, tip, commits):
    """-> dict. `commits` is [(sha, [paths])] newest-first from tip backwards.

    Pure, so the selftest drives it with fixtures instead of the network.
    """
    if runs is None:
        return {"verdict": "UNKNOWN", "reason": "run history unreadable"}

    green = {sha for sha, concl, _ in runs if concl == "success"}
    live = {sha for sha, concl, st in runs
            if st in ("in_progress", "queued") and not concl}

    if tip in green:
        return {"verdict": "OK", "reason": "tip has a green run",
                "last_green": tip, "ungraded": [], "shipped": []}
    if tip in live:
        return {"verdict": "OK", "reason": "tip's run is still in flight",
                "last_green": None, "ungraded": [], "shipped": []}

    ungraded, last_green = [], None
    for sha, paths in commits:
        if sha in green:
            last_green = sha
            break
        ungraded.append((sha, paths))
    shipped = [s for s, p in ungraded if ships(p)]
    return {
        # Nothing shipped => the container is still running the last green
        # commit, so the deployed code IS covered. Reported, not failed.
        "verdict": "UNGRADED" if shipped else "OK",
        "reason": ("ungraded commits reached a container"
                   if shipped else
                   "tip is ungraded but nothing shipped — the last green "
                   "commit is still what runs"),
        "last_green": last_green,
        "ungraded": [s for s, _ in ungraded],
        "shipped": shipped,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--depth", type=int, default=40,
                    help="commits to walk back from the tip")
    ap.add_argument("--gha", action="store_true", help="write a step summary")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()

    tip = _git("rev-parse", "HEAD")
    shas = _git("log", f"-{a.depth}", "--format=%H").split()
    commits = [(s, _git("show", "--name-only", "--format=", s).split())
               for s in shas]
    res = assess(fetch_runs(), tip, commits)

    v = res["verdict"]
    print(f"audit_ci_coverage: {v} — {res['reason']}")
    if res.get("ungraded") and v == "OK":
        print(f"  ungraded   : {len(res['ungraded'])} commit(s) since "
              f"{(res['last_green'] or 'none in window')[:12]}, none shipped")
    if v == "UNGRADED":
        print(f"  last green : {(res['last_green'] or 'none in window')[:12]}")
        print(f"  ungraded   : {len(res['ungraded'])} commit(s) since")
        print(f"  SHIPPED    : {len(res['shipped'])} of them touched a deploy "
              f"path and reached a container")
        for s in res["shipped"][:10]:
            print(f"     {s[:12]}  {_git('log','-1','--format=%s',s)[:60]}")
    if a.gha and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(f"### CI coverage — {v}\n\n{res['reason']}\n\n")
            if v == "UNGRADED":
                fh.write(f"- ungraded commits: {len(res['ungraded'])}\n"
                         f"- **shipped ungraded: {len(res['shipped'])}**\n")
    # UNKNOWN exits 2 — a guard with no answer must not print OK ((mq)).
    return 0 if v == "OK" else (2 if v == "UNKNOWN" else 1)


def _selftest():
    R = [("tip", "success", "completed")]
    assert assess(R, "tip", [("tip", [])])["verdict"] == "OK"

    # in flight -> not yet owed a settled answer
    assert assess([("tip", "", "in_progress")], "tip",
                  [("tip", [])])["verdict"] == "OK"

    # dark history -> UNKNOWN, never OK
    assert assess(None, "tip", [])["verdict"] == "UNKNOWN"

    # tip settled ungraded, one shipping commit behind it
    runs = [("c0", "success", "completed"), ("c2", "cancelled", "completed")]
    commits = [("c2", ["fleet_bus.py"]), ("c1", ["CHANGELOG.md"]),
               ("c0", ["x.py"])]
    r = assess(runs, "c2", commits)
    assert r["verdict"] == "UNGRADED", r
    assert r["last_green"] == "c0", r
    assert r["ungraded"] == ["c2", "c1"], r
    assert r["shipped"] == ["c2"], f"CHANGELOG-only must not count: {r}"

    # THE CALIBRATION: ungraded but nothing shipped is NOT a failure — the
    # container still runs the last green commit. A guard that reddens on a
    # doc-only push is one the reader learns to ignore ((gl)).
    docs = assess([("c0", "success", "completed"),
                   ("c2", "cancelled", "completed")], "c2",
                  [("c2", ["CHANGELOG.md"]), ("c1", ["tests/t.py"]),
                   ("c0", ["x.py"])])
    assert docs["verdict"] == "OK", docs
    assert docs["ungraded"] == ["c2", "c1"], "the context is still reported"
    assert docs["shipped"] == [], docs

    # a cancelled run is NOT a verdict — the whole premise
    assert assess([("tip", "cancelled", "completed")], "tip",
                  [("tip", ["fleet_bus.py"])])["verdict"] == "UNGRADED"
    # ...and neither is a failure
    assert assess([("tip", "failure", "completed")], "tip",
                  [("tip", ["fleet_bus.py"])])["verdict"] == "UNGRADED"

    # ships(): the classification itself
    assert ships(["venues/marks.py"]) and ships(["fleet_bus.py"])
    assert ships(["run_all.sh"]) and ships(["Dockerfile.funding"])
    assert not ships(["CHANGELOG.md"]), "a top-level .md is not .py"
    assert not ships(["tests/autonomy/test_x.py"]), "nested .py is in no image"
    assert not ships(["scripts/study_x.py"]), "scripts/ is not shipped"
    assert ships(["scripts/golive_readiness.py"]), "...except the one that is"
    assert not ships([]) and not ships(None), "no files -> no claim"
    assert ships(["CHANGELOG.md", "venues/marks.py"]), "mixed commit ships"

    print("audit_ci_coverage selftest OK "
          "(green/in-flight/dark/ungraded, cancelled-is-not-a-verdict, ships)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
