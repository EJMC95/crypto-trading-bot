#!/usr/bin/env python3
"""Does a change to this file actually DEPLOY? — the deploy-filter guard.

WHY THIS EXISTS (measured 2026-07-17). `.github/workflows/railway-redeploy.yml`
decides what ships by matching changed paths against a hand-written list. The
list was authored 2026-07-07 and names the organs that existed THEN. Measured
against `run_all.sh` on 17-Jul: **15 of the 19 organs the freqtrade-bots
container actually runs were absent from it** — bot_learn, evidence_board,
fleet_immune, fleet_proprioception, fleet_regen, fleet_respiration,
fleet_clock, experiment_judge, strategy_incubator, implementation_shortfall,
event_sentinel, lighter_market_scout, lighter_scout_tuner, lighter_ticket_taker,
cleanup_legacy_bots. The ENTIRE autonomy + evidence layer. A fix to any of them
merged to main, went green, and silently never reached the container.

The workflow's own header records the same bug happening once before — it was
added "after 9cedf08 (SUI + historize) silently didn't deploy". That fix
enumerated the three organs that existed and moved on. The instance got fixed;
the class did not. This guard is the class.

It is the same failure shape as market_context.LIVE_FRESHNESS_LIMITS (17-Jul):
a hand-maintained roster that nobody is reminded to sweep, whose failure mode is
SILENCE. Where a roster can be derived, derive it (fleet_watchdog_svc.py:137 is
the fleet's model). A GitHub `paths:` filter cannot be derived — it is static
YAML read by GitHub before any code runs — so the next best thing is a guard
that fails loudly the moment the static list drifts from reality.

CONTRACT: every module `run_all.sh` executes inside the freqtrade-bots image
must appear in the workflow's push-path filter AND in its freqtrade-bots
service matcher. Deliberate omissions are DECLARED in DEPLOY_FILTER_OK with a
reason — silence is not an option (the born-dark rule, same spirit).

NOTE ON SCOPE: this checks the modules run_all.sh RUNS. It does not chase their
imports — that is audit_image_imports.py's job (a module that is present but
never redeployed is this guard's problem; a module that is missing from the
image is that one's). Together they answer "is the code there?" and "does new
code get there?".

Usage:  python3 scripts/audit_deploy_filter.py        # exit 1 on drift
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/railway-redeploy.yml"
RUN_ALL = ROOT / "run_all.sh"

# Modules run_all.sh runs that deliberately do NOT gate a deploy. Each needs a
# reason. Empty by design: if you are adding to this, say why the container
# running stale code is acceptable.
DEPLOY_FILTER_OK = {
    # "example.py": "reason it must not trigger a freqtrade-bots redeploy",
}


def organs_run_by(run_all_text):
    """Modules the container actually executes, from run_all.sh itself."""
    return set(re.findall(r"python3?\s+/freqtrade/(\w+\.py)", run_all_text))


def filter_paths(wf_text):
    """Files named in the workflow's `on: push: paths:` block."""
    head = wf_text.split("workflow_dispatch:")[0]
    if "paths:" not in head:
        return set()
    return set(re.findall(r"-\s+'([^']+)'", head.split("paths:")[1]))


def freqtrade_matcher(wf_text):
    """Files named in the freqtrade-bots service grep in the decide step."""
    m = re.search(r"grep -qE '\^\(([^']+)\)'[^\n]*\n\s*svcs=\"freqtrade-bots\"",
                  wf_text)
    if not m:
        return None
    return set(x.replace("\\", "").rstrip("$")
               for x in m.group(1).split("|"))


def main():
    if not WORKFLOW.exists() or not RUN_ALL.exists():
        print("audit_deploy_filter: SKIP — workflow or run_all.sh not found")
        return 0

    wf = WORKFLOW.read_text()
    organs = organs_run_by(RUN_ALL.read_text())
    if not organs:
        print("audit_deploy_filter: SKIP — no organs parsed from run_all.sh")
        return 0

    paths = filter_paths(wf)
    matcher = freqtrade_matcher(wf)

    problems = []
    for o in sorted(organs):
        if o in DEPLOY_FILTER_OK:
            continue
        if o not in paths:
            problems.append((o, "absent from the push `paths:` filter — the "
                                "workflow will not even RUN when it changes"))
        elif matcher is not None and o not in matcher:
            problems.append((o, "in `paths:` but NOT in the freqtrade-bots "
                                "matcher — the workflow runs and deploys "
                                "nothing"))

    if problems:
        print(f"audit_deploy_filter: {len(problems)} organ(s) run by run_all.sh "
              f"whose changes DO NOT DEPLOY:\n")
        for o, why in problems:
            print(f"  {o}\n      {why}")
        print(f"\nFix: add them to BOTH lists in {WORKFLOW.relative_to(ROOT)}, "
              f"or declare them in DEPLOY_FILTER_OK with a reason.")
        print("A merged, green, selftested fix that never reaches the container "
              "is indistinguishable from no fix at all — and it looks like a "
              "success. That is how the autonomy layer went 10 days without a "
              "deploy path.")
        return 1

    dec = f", {len(DEPLOY_FILTER_OK)} declared" if DEPLOY_FILTER_OK else ""
    print(f"audit_deploy_filter: OK — all {len(organs)} organ(s) run by "
          f"run_all.sh gate a freqtrade-bots deploy{dec}.")
    return 0


def _selftest():
    """Assert the DETECTOR, not today's workflow — synthetic fixtures, so this
    keeps passing once the real filter is fixed and keeps failing if it rots."""
    ra = "python3 /freqtrade/alpha.py\npython3 /freqtrade/beta.py || true\n"
    assert organs_run_by(ra) == {"alpha.py", "beta.py"}, organs_run_by(ra)

    good = ("on:\n  push:\n    paths:\n      - 'alpha.py'\n      - 'beta.py'\n"
            "workflow_dispatch:\n")
    assert filter_paths(good) == {"alpha.py", "beta.py"}, filter_paths(good)
    # a filter that names only ONE of two organs is drift — the shipped state
    bad = "on:\n  push:\n    paths:\n      - 'alpha.py'\nworkflow_dispatch:\n"
    assert filter_paths(bad) == {"alpha.py"}
    assert "beta.py" not in filter_paths(bad)

    m = ("      if echo \"$changed\" | grep -qE "
         "'^(user_data/|alpha\\.py$|beta\\.py$)'; then\n"
         "        svcs=\"freqtrade-bots\"\n")
    got = freqtrade_matcher(m)
    assert got == {"user_data/", "alpha.py", "beta.py"}, got
    assert freqtrade_matcher("nothing here") is None
    print("audit_deploy_filter selftest OK (organ parse, paths parse, "
          "matcher parse, drift detected)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
