"""A red `main` must reach a human — the notifier that was the exact complement of a hole.

INCIDENT (2026-09-07 (yx), measured). `ci-notify.yml` reports every CI
transition ON THE PULL REQUEST and skips main by design, with the reason in its
own comment: *"main-branch runs are post-merge CI - no PR to notify"*. That is
correct for work arriving through PRs and it is not the workflow this repo runs
— CLAUDE.md's worktree rule publishes with `git rebase origin/main && git push
origin HEAD:main`, so the pushes that actually govern the fleet have no PR, and
therefore had no notification of any kind.

What that cost, on the day it was found: `(yl)` landed
`scripts/study_taker_ready_2026-09-06.py` with a `--selftest` and no
registration at 03:16Z. `test_no_unregistered_selftest` — a guard that works,
and had ALREADY caught this exact class once before ((wr)/(wu), recorded in
`tests/test_selftests.py`'s own comments) — reddened `Tests` at run #1031
(03:29Z). Main was still red at run #1035 on HEAD ~10 hours later, with eight
further pushes landing on top of it. Nobody was told, by anything, at any
point.

That is the `(gl)` shape one level up. `(gl)` says a guard whose only output is
a warning on a passing run is not a guard. This is a guard whose output is a
RED RUN THAT NOBODY IS SHOWN — and the failure mode is worse, because a red
build is exactly the state in which every subsequent push is unverified.

These tests pin the properties that make `main-red.yml` a notifier rather than
a decoration. Each maps to a specific way it could go silently useless:

  * it is the EXACT COMPLEMENT of ci-notify — if a later edit lets ci-notify
    handle main, both fire and the operator is spammed; if main-red stops
    requiring main, the hole reopens exactly as it was. The complement is the
    class-closing property and it is asserted from BOTH files;
  * it never fires on `cancelled` — 6 of the 10 most recent main runs were
    cancelled by the push after them, which is NORMAL here. A notifier that
    cries wolf is one the operator learns to ignore ((gl) again);
  * the issue is scoped PER WORKFLOW — two workflows report here, and without
    the marker a green "Changelog check" closes the issue a red "Tests" just
    opened, on the same commit: the notifier silently cancelling its own alarm;
  * concurrency is keyed on the workflow, not the sha — both workflows finish
    on the SAME head_sha, so ci-notify's sha-keyed `cancel-in-progress: true`
    group would have one event cancel the other's alert;
  * untrusted commit text never reaches the shell through `${{ }}` — a commit
    subject is attacker-shaped, and interpolating it into a `run:` block is
    script injection into a job holding `issues: write`;
  * it is granted the scopes it uses — `permissions:` zeroes every scope it
    does not list, which is precisely how `audit_ci_coverage` shipped unable
    to answer its own question ((pn), one workflow over).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_RED = ROOT / ".github" / "workflows" / "main-red.yml"
CI_NOTIFY = ROOT / ".github" / "workflows" / "ci-notify.yml"


def _text(p):
    assert p.exists(), f"{p.name} is missing — see this file's docstring"
    return p.read_text()


def _job_guard(text, job):
    """The `if:` expression of one job, joined to a single line.

    Deliberately not a YAML parse: requirements-test.txt carries no yaml lib
    (the `test_code_currency_wired` convention), and a guard is line-shaped.
    """
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if re.fullmatch(rf"  {re.escape(job)}:\s*", ln))
    body = []
    for ln in lines[start + 1:]:
        if re.match(r"  \S", ln):
            break
        body.append(ln)
    body = "\n".join(body)
    m = re.search(r"^\s*if:\s*(.*?)^\s{4}\w+:", body + "\n    end:",
                  re.S | re.M)
    assert m, f"job `{job}` has no `if:` guard"
    return " ".join(m.group(1).split())


def test_main_red_and_ci_notify_are_exact_complements():
    """THE CLASS-CLOSING PIN — asserted from both files, in both directions.

    A completed workflow run must be handled by exactly one of these two jobs.
    ci-notify must EXCLUDE main (or main gets two alerts); main-red must
    REQUIRE main (or the 10-hour hole reopens byte-for-byte).
    """
    notify = _job_guard(_text(CI_NOTIFY), "notify")
    assert "head_branch != 'main'" in notify, (
        "ci-notify no longer excludes main. Either it now double-reports "
        "alongside main-red, or its guard was rewritten — reconcile the two "
        "files: between them, a completed main run is handled exactly once")

    report = _job_guard(_text(MAIN_RED), "report")
    assert "head_branch == 'main'" in report, (
        "main-red no longer requires head_branch == 'main' — this is the hole "
        "it was built to close, reopened: ci-notify skips main, so nothing "
        "would report a red main at all")


def test_main_red_never_fires_on_a_cancelled_run():
    """`cancelled` is the NORMAL state here — each push supersedes the run
    before it. Alerting on it makes the notifier noise within a day."""
    guard = _job_guard(_text(MAIN_RED), "report")
    assert "conclusion == 'failure'" in guard, (
        "main-red does not act on `failure` — it cannot report a red main")
    assert "conclusion == 'success'" in guard, (
        "main-red does not act on `success` — it can open an issue and never "
        "close it, which is an alert that stays lit after recovery")
    for noise in ("cancelled", "skipped", "neutral", "timed_out"):
        assert noise not in guard, (
            f"main-red's guard admits `{noise}` runs. 6 of the 10 most recent "
            f"main runs were cancelled by the push after them; alerting on "
            f"that trains the operator to ignore the label ((gl))")


def test_the_issue_is_scoped_per_workflow():
    """Two workflows report here. Without a per-workflow marker, a green
    "Changelog check" closes the issue a red "Tests" opened on the same sha."""
    text = _text(MAIN_RED)
    assert re.search(r'MARK="<!-- main-red:\$\{?WF\}? -->"', text), (
        "the issue marker is not keyed on the workflow name — one workflow's "
        "recovery will close the other's open alert on the same commit")
    assert "contains(env.MARK)" in text, (
        "the issue lookup does not filter on the per-workflow marker, so it "
        "picks up whichever main-red issue happens to be first")


def test_both_reporting_workflows_are_watched():
    text = _text(MAIN_RED)
    m = re.search(r"workflows:\s*\[(.*?)\]", text)
    assert m, "main-red declares no `workflows:` filter"
    watched = m.group(1)
    for wf in ("Tests", "Changelog check"):
        assert f'"{wf}"' in watched, (
            f"main-red does not watch `{wf}` on main — a red {wf} would be "
            f"as invisible as the incident this file records")


def test_untrusted_commit_text_is_not_interpolated_into_the_script():
    """A commit subject is attacker-shaped text and this job holds
    `issues: write`. It must be FETCHED into a variable, never interpolated."""
    text = _text(MAIN_RED)
    # STRUCTURAL, not a page-wide substring scan ((po)): this file's own
    # comments name `head_commit` to explain why it is banned, and the first
    # cut of this test failed on its own prose. What is banned is the
    # INTERPOLATION, so match the `${{ ... }}` expressions and nothing else.
    exprs = re.findall(r"\$\{\{(.*?)\}\}", text, re.S)
    tainted = [e.strip() for e in exprs
               if "head_commit" in e or "display_title" in e]
    assert not tainted, (
        "main-red interpolates attacker-shaped commit text through `${{ }}`: "
        f"{tainted}. That is script injection into a job holding "
        "issues: write — fetch the subject with `gh api` into a shell "
        "variable instead")
    assert re.search(r"SUBJ=\$\(gh api [\"']?repos/\$REPO/commits/\$SHA",
                     text), (
        "the commit subject is no longer fetched through the API — check it "
        "did not move back to a `${{ }}` interpolation")


def test_concurrency_does_not_let_one_workflows_event_cancel_anothers():
    """Both watched workflows complete on the SAME head_sha, so ci-notify's
    sha-keyed cancel-in-progress group would drop one of the two alerts."""
    text = _text(MAIN_RED)
    m = re.search(r"^concurrency:\n(?:[ \t]+\S.*\n)+", text, re.M)
    assert m, "main-red declares no concurrency group"
    block = m.group(0)
    assert "workflow_run.name" in block, (
        "main-red's concurrency group is not keyed on the workflow name — "
        "Tests and Changelog check finish on the same sha, so a sha-keyed "
        "group makes them cancel each other")
    assert re.search(r"cancel-in-progress:\s*false", block), (
        "main-red cancels in-progress runs in its own group: a second event "
        "for the same workflow would kill the alert the first is writing")


def test_the_notifier_is_granted_the_scopes_it_uses():
    """`permissions:` zeroes every scope it does not list — the (pn) class."""
    text = _text(MAIN_RED)
    m = re.search(r"^permissions:\n((?:\s+\S+:\s*\S+\n)+)", text, re.M)
    assert m, "main-red declares no `permissions:` block"
    perms = m.group(1)
    assert re.search(r"issues:\s*write", perms), (
        "main-red cannot open or close an issue — it has no `issues: write`, "
        "and a permissions block zeroes every scope it omits")
    assert re.search(r"actions:\s*read", perms), (
        "main-red reads the run's failing job names via the Actions API; "
        "without `actions: read` that call 403s and every alert reads "
        "'(job names unavailable)' — the (pn) missing-scope class")
