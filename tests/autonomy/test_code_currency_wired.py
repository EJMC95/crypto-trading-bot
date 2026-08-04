"""The code-currency audit must KEEP a consumer — and a consumer that cannot fail.

INCIDENT CLASS (2026-08-04, fleet review §6 action ①). `(iw)` built
`scripts/audit_code_currency.py` — the command that answers "which commit is
this bot actually running?" — and it shipped with ZERO consumers: no workflow,
no scheduled task, no loop. Deploy-verification labor was ~29% of that week's
changelog entries while the tool that ends the class ran only when a human
remembered it. That is the exact "rule nobody runs" shape `(gk)` fixed for the
go-live grader, one tool later.

`(jc)` wired it into `.github/workflows/fleet-weekly-assessment.yml` as its
own job. These tests pin the properties that make that wiring a GUARD rather
than a decoration, each of which has a specific silent-degrade mode:

  * the job EXISTS and runs the script — deleting the step un-runs the rule
    with no red anywhere (the original gap, restored);
  * its checkout has `fetch-depth: 0` — the audit replays `build_compute`
    across history, and on a depth-1 checkout every container classifies
    UNRESOLVED, which does not fail: a vacuous green;
  * it passes `--pnl-json` — without it the script falls back to the DB,
    CI has no DATABASE_URL, `fetch_bot_pnl()` returns None, and the run
    prints "nothing to check" and passes forever: the same vacuous green
    (`--pnl-json` is the FAIL-CLOSED source precisely for this);
  * nothing masks the exit code — a `|| true` or `continue-on-error` turns
    BEHIND-OWN into a warning, and a guard whose only output is a warning on
    a passing run is not a guard (house rule, (gl)/(hj)).

Scoped to the job's own block, never page-wide substrings — `fetch-depth: 0`
elsewhere in the file must not satisfy the check ((hm): a page-wide scan is
not a structural claim).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WF = ROOT / ".github" / "workflows" / "fleet-weekly-assessment.yml"


def _job_block(name):
    """The literal YAML lines of one job under `jobs:`, by indentation.

    Jobs sit at 2-space indent; a job's body is everything more-indented
    beneath it up to the next 2-space key. Deliberately not a YAML parse:
    requirements-test.txt carries no yaml lib, and the properties pinned here
    are line-shaped.
    """
    text = WF.read_text()
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines)
                     if re.fullmatch(rf"  {re.escape(name)}:\s*", ln))
    except StopIteration:
        raise AssertionError(
            f"workflow has no `{name}` job — the code-currency audit has "
            f"lost its only consumer (the (jc) wiring; see this file's "
            f"docstring for why that is the original incident, restored)")
    body = []
    for ln in lines[start + 1:]:
        if re.match(r"  \S", ln):    # next 2-space key = next job
            break
        body.append(ln)
    return "\n".join(body)


def test_code_currency_job_runs_the_audit_from_the_public_feed():
    job = _job_block("code-currency")
    runs = [ln for ln in job.splitlines()
            if "scripts/audit_code_currency.py" in ln]
    assert runs, "code-currency job never invokes scripts/audit_code_currency.py"
    cmd = runs[0]
    assert "--pnl-json" in cmd, (
        "the audit runs without --pnl-json: CI has no DATABASE_URL, so the "
        "DB fallback returns no rows and the run passes VACUOUSLY forever — "
        "the feed source is the fail-closed one")
    assert "--gha" in cmd, (
        "without --gha the verdict table never reaches the run summary and "
        "BEHIND-OWN raises no annotation — the review reads the summary, "
        "not the log")


def test_code_currency_checkout_has_full_history():
    job = _job_block("code-currency")
    assert re.search(r"fetch-depth:\s*0", job), (
        "code-currency's checkout lacks fetch-depth: 0 — the audit replays "
        "build_compute across history, and on a depth-1 checkout every "
        "container reads UNRESOLVED, which does not fail: a vacuous green")


def test_code_currency_exit_code_is_not_masked():
    job = _job_block("code-currency")
    assert "continue-on-error" not in job, (
        "continue-on-error on the code-currency job turns BEHIND-OWN into a "
        "warning — and a guard whose only output is a warning on a passing "
        "run is not a guard ((gl)/(hj))")
    for ln in job.splitlines():
        if "audit_code_currency" in ln:
            assert "|| true" not in ln and not re.search(r"\|\|\s*echo", ln), (
                f"the audit's exit code is masked: {ln.strip()!r}")


def test_the_window_covers_a_week_of_commits():
    """Weekly cadence needs a deeper window than the script's ad-hoc default:
    measured 4-Aug, this repo lands ~120 commits in 7 days, and a deliberately
    DEFERRED live service more than --depth behind drifts into UNRESOLVED —
    losing exactly the verdict the weekly run exists to publish."""
    job = _job_block("code-currency")
    m = re.search(r"--depth\s+(\d+)", job)
    assert m, "the audit invocation pins no --depth; the default 40 is an " \
              "ad-hoc window, ~2 days of this repo's history"
    assert int(m.group(1)) >= 150, (
        f"--depth {m.group(1)} is under a week of history at the measured "
        f"commit rate (~120/7d); DEFERRED live services would read UNRESOLVED")
