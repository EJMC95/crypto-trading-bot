"""[2026-08-19 (rn)] The reader-currency check's file list may not drift.

THE INCIDENT THIS GUARDS THE GUARD OF: the (rl) freeze ate the (rj)
pnl-dashboard deploy, so the SERVING reader predated main's nav-cook
registration and the born row was silently filtered from /pnl.json for ~2h.
fleet-watchdog.yml now checks, hourly and from outside, that the reader's
boot time is not older than the newest main commit touching the dashboard
image's own files.

That check necessarily carries a SECOND COPY of the routing rule — the same
file set railway-redeploy.yml's decide step uses to deploy pnl-dashboard —
and a second copy of a rule is a second rule ((hj)): the day someone adds a
file to the dashboard image and its decide grep, a watchdog list that missed
it would go quietly blind to exactly the deploys of that file. So the two
sets are pinned EQUAL here, extracted from the real workflow texts, with
positive controls so an extractor that matches nothing fails rather than
passing vacuously ((po)).
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
REDEPLOY = ROOT / ".github" / "workflows" / "railway-redeploy.yml"
WATCHDOG = ROOT / ".github" / "workflows" / "fleet-watchdog.yml"


def _redeploy_dash_set():
    """The pnl-dashboard decide grep's file set, from the real workflow text.

    The grep is the line whose FOLLOWING assignment adds pnl-dashboard —
    matched as a pair so a reordering of the decide rules cannot silently
    aim this test at another service's set.
    """
    text = REDEPLOY.read_text()
    m = re.search(
        r"grep -qE '\^\(([^']+)\)'; then\s*\n\s*svcs=\"\$\{svcs:\+\$svcs,\}pnl-dashboard\"",
        text)
    assert m, "could not locate the pnl-dashboard decide grep in railway-redeploy.yml"
    alts = m.group(1).split("|")
    files = {a.replace("\\.", ".").rstrip("$") for a in alts}
    assert files, "extractor matched an empty alternation — not a clean pass"
    return files


def _watchdog_dash_set():
    text = WATCHDOG.read_text()
    m = re.search(r'DASH_FILES="([^"]+)"', text)
    assert m, "could not locate DASH_FILES in fleet-watchdog.yml"
    files = set(m.group(1).split())
    assert files, "DASH_FILES is empty — not a clean pass"
    return files


def test_watchdog_list_equals_the_decide_greps_dashboard_set():
    assert _watchdog_dash_set() == _redeploy_dash_set()


def test_positive_control_the_extractors_see_the_known_members():
    """(po): prove the extractors read something real before trusting the
    equality — both sets must contain the two members the incident was about
    (the dashboard server and the file the watchdog itself serves from)."""
    for s in (_watchdog_dash_set(), _redeploy_dash_set()):
        assert "pnl_dashboard.py" in s
        assert "fleet_watchdog_svc.py" in s


def test_the_check_runs_between_probe_and_alerting():
    """The step appends to problems.txt, so it must sit AFTER the probe that
    writes the file and BEFORE the alerting step that reads it — a correct
    check in the wrong slot pages nothing."""
    text = WATCHDOG.read_text()
    probe = text.index("name: Probe fleet feed")
    reader = text.index("name: Reader currency")
    alert = text.index("name: Transition-aware alerting")
    assert probe < reader < alert


def test_a_skip_is_visible_never_silent():
    """A run that verified nothing must not read like a run that found
    nothing ((po)) — both skip paths print a SKIP line into the step summary."""
    text = WATCHDOG.read_text()
    step = text[text.index("name: Reader currency"):
                text.index("name: Transition-aware alerting")]
    assert step.count("reader-currency: SKIP") == 2
    assert "GITHUB_STEP_SUMMARY" in step
