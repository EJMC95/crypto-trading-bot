#!/usr/bin/env python3
"""audit_task_prompts.py — the scheduled routines' prompts, under the same guard as the code.

    python3 scripts/audit_task_prompts.py            # all arms
    python3 scripts/audit_task_prompts.py --selftest

THE CLASS THIS CLOSES (2026-09-11). Five scheduled tasks review this fleet
every day, and their instructions lived in `~/.claude/scheduled-tasks/*/SKILL.md`
— **outside the repo**. Nothing could diff them, test them, grep them, or
notice when one rotted, and the fleet's own doctrine is emphatic about what
happens next: a scope rule keyed to a LIST goes stale on every slot swap, and
CLAUDE.md records that happening FOUR times to one rule. It happened here too —
`crypto-daily-pnl` named 💸 the Funding Farmer's live arm as current
real-money surface for **20 days** after its 22-Aug retirement, and
`audit_live_roster`'s prose arm could not see it because that guard scans
`CLAUDE.md` and nothing else.

So the prompts are now TRACKED (`scheduled_tasks/<task>/SKILL.md`) and this
audit holds them to three rules:

  A. **Every repo path a prompt names must exist.** A prompt that sends its run
     at a deleted script is the (gk) "rule nobody runs" shape with the blame
     landing on the routine.
  B. **No prompt may name a retired live row.** A task prompt is an INSTRUCTION,
     not a history — unlike `CLAUDE.md`, it has no legitimate reason to carry a
     dead row id, so the check needs no anchor window and cannot be evaded by
     moving a sentence. The roster itself is imported from `fleet_books`, so
     this guard cannot disagree with the fleet about who holds real money.
  C. **The tracked copy and the installed copy must match.** Local-only: a CI
     runner has no `~/.claude`, and that is reported as SKIPPED rather than
     passing — swept-dark and swept-clean must never be byte-identical ((kw)).

WHAT IT DELIBERATELY DOES NOT DO: judge the prose. Tone, ordering and length
are not checkable by a static guard, and a guard that tried would be the
mistake CLAUDE.md's own tone rule names. This checks facts that have a single
owner elsewhere in the repo.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleet_books import ROW_ENTRY                                  # noqa: E402
from audit_live_roster import FORMERLY_LIVE                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Where the tracked copies live, and where the scheduler reads from.
TRACKED = os.path.join(ROOT, "scheduled_tasks")
INSTALLED = os.path.expanduser("~/.claude/scheduled-tasks")

#: Paths a prompt may name that are not repo files — an endpoint, a home dir.
#: Anything else must resolve, either as written or under `scripts/`.
_PATH = re.compile(
    r"(?:scripts/|tests/|\.github/workflows/)[A-Za-z0-9_./-]+\.(?:py|sh|yml)"
    r"|(?<![/\w])[a-z][a-z0-9_]+\.(?:py|sh)")

#: A task is IN SCOPE iff its own prompt tells the run to work in this repo.
#: DERIVED, not listed — the alternative is a roster of task ids, which is the
#: exact shape this audit exists to stop rotting. Eamon's personal jobs
#: (`daily-email-autofile`, `spark-email-*`) never name the repo and are
#: correctly invisible here.
SCOPE_MARK = "Claude/Projects/Crypto Trading Bot"

#: Fleet tasks that are installed, in scope, and deliberately NOT tracked.
#: A RATCHET, per (mz): a guard that reddens the build on a pre-existing
#: backlog is exempted within a day and then guards nothing, so the backlog may
#: only shrink and a NEW untracked fleet routine fails immediately.
UNTRACKED_OK = {
    "counterweight-keep-or-retire": "SPENT one-shot, disabled 28-Aug after its "
                                    "own run; kept as a record, deleting it is "
                                    "P5 housekeeping and Eamon's call",
    "snap-back-census-check": "RESOLVED + disabled 4-Aug when 🧲 Snap Back was "
                              "retired (jh); kept as a record",
}

#: Named in prose as examples of a FILENAME PATTERN rather than a file.
PATH_EXEMPT = {
    # the report artifacts themselves — written by the routines, gitignored
    "expansion_research_log.md",
}


def tracked_prompts(root=TRACKED):
    """-> {task_id: text} for every tracked prompt. Missing dir -> {}."""
    out = {}
    if not os.path.isdir(root):
        return out
    for task in sorted(os.listdir(root)):
        p = os.path.join(root, task, "SKILL.md")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                out[task] = fh.read()
    return out


def unresolved_paths(text, root=ROOT):
    """-> sorted [path] the prompt names that do not exist in the repo.

    A bare `foo.py` is accepted if `scripts/foo.py` exists: the prompts
    legitimately refer to a script by name in running prose after naming it in
    full once.
    """
    bad = set()
    for m in _PATH.findall(text):
        if m in PATH_EXEMPT:
            continue
        if os.path.exists(os.path.join(root, m)):
            continue
        if "/" not in m and os.path.exists(os.path.join(root, "scripts", m)):
            continue
        bad.add(m)
    return sorted(bad)


def retired_rows_named(text, formerly=None):
    """-> sorted [row] retired-live ids the prompt names. Instructions only."""
    formerly = FORMERLY_LIVE if formerly is None else formerly
    return sorted(r for r in formerly if r in text)


def divergences(tracked=None, installed=INSTALLED, untracked_ok=None):
    """-> (findings, checked) comparing tracked vs installed prompts.

    `checked` is False when there is no installed tree (CI) — the caller must
    report SKIPPED rather than clean.
    """
    tracked = tracked_prompts() if tracked is None else tracked
    untracked_ok = UNTRACKED_OK if untracked_ok is None else untracked_ok
    if not os.path.isdir(installed):
        return [], False
    out = []
    for task, text in sorted(tracked.items()):
        p = os.path.join(installed, task, "SKILL.md")
        if not os.path.exists(p):
            out.append((task, "tracked but NOT INSTALLED — the scheduler is "
                              "running something else, or nothing"))
            continue
        with open(p, encoding="utf-8") as fh:
            live = fh.read()
        if live != text:
            out.append((task, f"tracked copy DIVERGES from {p} — the repo's "
                              f"copy is not what runs"))
    for task in sorted(os.listdir(installed)):
        p = os.path.join(installed, task, "SKILL.md")
        if not os.path.exists(p) or task in tracked or task in untracked_ok:
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                body = fh.read()
        except OSError:
            continue
        if SCOPE_MARK not in body:
            continue                 # not a fleet routine — not this guard's
        out.append((task, "installed as a FLEET routine but NOT TRACKED — no "
                          "guard, no history, no diff. Copy it to "
                          "scheduled_tasks/ or declare it in UNTRACKED_OK."))
    return out, True


def check(tracked=None, root=ROOT, formerly=None):
    """-> [(task, arm, detail)] findings from the arms that need no home dir."""
    tracked = tracked_prompts() if tracked is None else tracked
    fails = []
    for task, text in sorted(tracked.items()):
        for p in unresolved_paths(text, root):
            fails.append((task, "PATH", f"names `{p}`, which does not exist"))
        for row in retired_rows_named(text, formerly):
            why = (FORMERLY_LIVE if formerly is None else formerly)[row]
            fails.append((task, "RETIRED-ROW",
                          f"names `{row}` — {why}. A prompt is an instruction, "
                          f"not a history: derive the roster from the feed."))
    return fails


def _selftest():
    import tempfile

    # -- arm A: paths ------------------------------------------------------
    assert unresolved_paths("run `scripts/golive_readiness.py` now") == []
    assert unresolved_paths("read ceiling.py") == [], \
        "a bare name resolving under scripts/ is fine"
    assert unresolved_paths("run scripts/not_a_real_script.py") == \
        ["scripts/not_a_real_script.py"]
    assert unresolved_paths("see .github/workflows/nope.yml") == \
        [".github/workflows/nope.yml"]
    # a URL must not be mined for paths
    assert unresolved_paths("https://example.com/pnl.json") == []

    # -- arm B: retired rows, with an INJECTED roster so the test does not
    #    drift when the real one changes -----------------------------------
    fake = {"dead-row-lighter": "retired 1-Jan"}
    assert retired_rows_named("the live pair is dead-row-lighter", fake) == \
        ["dead-row-lighter"]
    assert retired_rows_named("no rows here", fake) == []
    fails = check({"t": "we watch dead-row-lighter daily"}, formerly=fake)
    assert [f[1] for f in fails] == ["RETIRED-ROW"], fails
    assert "instruction" in fails[0][2], "say WHY a prompt may not carry one"

    # -- the real prompts, if they are tracked yet -------------------------
    # Not an assertion that they exist: this audit ships in the same commit
    # that first tracks them, and a bootstrap that fails on its own arrival
    # would be exempted within a day ((mz)).
    for task, text in tracked_prompts().items():
        assert isinstance(text, str) and text, task

    # -- arm C: divergence, and SKIPPED is not CLEAN -----------------------
    with tempfile.TemporaryDirectory() as td:
        out, checked = divergences({"a": "x"}, installed=os.path.join(td, "nope"))
        assert checked is False and out == [], "absent home tree -> SKIPPED"
        inst = os.path.join(td, "home")
        os.makedirs(os.path.join(inst, "a"))
        with open(os.path.join(inst, "a", "SKILL.md"), "w") as fh:
            fh.write("x")
        out, checked = divergences({"a": "x"}, installed=inst)
        assert checked is True and out == [], out
        out, _ = divergences({"a": "DIFFERENT"}, installed=inst)
        assert out and "DIVERGES" in out[0][1], out
        out, _ = divergences({"a": "x", "b": "y"}, installed=inst)
        assert any("NOT INSTALLED" in d for _, d in out), out
        # OUT OF SCOPE unless the prompt names the repo — Eamon's personal
        # jobs live in the same directory and are not this guard's business.
        out, _ = divergences({}, installed=inst)
        assert out == [], f"a prompt with no repo marker is out of scope: {out}"
        with open(os.path.join(inst, "a", "SKILL.md"), "w") as fh:
            fh.write("work in " + SCOPE_MARK)
        out, _ = divergences({}, installed=inst)
        assert any("NOT TRACKED" in d for _, d in out), out
        # and the declared backlog is exempt (the ratchet)
        out, _ = divergences({}, installed=inst,
                             untracked_ok={"a": "declared"})
        assert out == [], f"a declared exemption must not fire: {out}"

    print("audit_task_prompts selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()

    tracked = tracked_prompts()
    if not tracked:
        print(f"no tracked prompts under {TRACKED} — nothing to check")
        return 0
    fails = check(tracked)
    div, checked = divergences(tracked)

    print(f"prompts checked : {', '.join(sorted(tracked))}")
    print(f"roster owner    : fleet_books ({len(ROW_ENTRY)} rows mapped, "
          f"{len(FORMERLY_LIVE)} formerly live)")
    if checked:
        print(f"installed copies: compared against {INSTALLED}")
    else:
        print(f"installed copies: SKIPPED — no {INSTALLED} here (not clean, "
              f"unchecked)")

    for task, detail in div:
        fails.append((task, "DIVERGED", detail))
    if fails:
        print("\nFINDINGS:")
        for task, arm, detail in fails:
            print(f"  [{arm}] {task}: {detail}")
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
