"""A deploy that moves ONE arm of a matched pair must be visible.

[2026-08-18 (pt)] The two Funding Farmer arms are a MATCHED PAIR: the
experiment judge refuses to grade a window in which they ran different code
("this window measures a code delta, not edge"), and that judge is the ONLY
writer of `live.funding.*` — the sole designed path from shadow evidence to
real money.

MEASURED, and self-inflicted: a `workflow_dispatch` naming only
`trail-blazer-live` deployed the live arm alone, leaving
live=35562ac7b4de vs shadow=e981e11820fc. The judge held `slope-gate-off` at
n_shadow 10/30 with `ARMS ON DIFFERENT CODE` — and **`audit_code_currency`
printed OK**, calling the lagging arm "DEFERRED ... working as designed".

It was right about the ROW and wrong about the PAIR. `DEFERRED` means
"deliberately held behind a marker gate", which is only true when BOTH arms
are held; one arm current and the other not is drift, never design. Two guards
were green over a real break, which is why this is pinned in both places:

  * `audit_deploy_coverage.arm_pairing_orphans` — the two names must be
    appended by ONE condition in the workflow's decide step (it was, in the
    PUSH branch; the dispatch branch took the operator's list verbatim);
  * `audit_code_currency.arm_drift` — the runtime half, here.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import audit_code_currency as acc            # noqa: E402
import audit_deploy_coverage as adc          # noqa: E402

LIVE, CTRL = "trail-blazer-live", "funding-farmer-shadow"


def _row(svc, verdict):
    return {"row": svc, "svc": svc, "verdict": verdict}


def test_the_pair_is_declared_once_and_imported_not_copied():
    """MUTATION: re-declare PAIRED_ARMS inside audit_code_currency -> RED.

    A second copy of a rule is a second rule ((hj)); the pair must have ONE
    owner. Pinned by identity of the mapping, not by a name check.
    """
    assert adc.PAIRED_ARMS.get(LIVE) == CTRL
    src = open(os.path.join(ROOT, "scripts", "audit_code_currency.py")).read()
    assert "from audit_deploy_coverage import PAIRED_ARMS" in src, (
        "audit_code_currency must IMPORT PAIRED_ARMS from its owner; a local "
        "copy drifts silently the day a pair is added")
    assert "PAIRED_ARMS = {" not in src, (
        "audit_code_currency re-declares PAIRED_ARMS — a second copy of a rule")


def test_one_arm_ahead_is_a_finding():
    """MUTATION: never fire, or invert the compare -> RED. This is the exact
    state the fleet was in on 18-Aug while both guards printed OK."""
    drift = acc.arm_drift([_row(LIVE, "CURRENT"), _row(CTRL, "DEFERRED")])
    assert drift, (
        "one arm CURRENT while its pair is DEFERRED must be reported: the "
        "judge cannot grade that window, so no promotion to live.funding.* "
        "can rest on it")
    assert LIVE in drift[0][2] and CTRL in drift[0][2], (
        "the finding must NAME both services — a detector's output has to "
        "identify the thing the operator acts on (I8)")


@pytest.mark.parametrize("verdict", ["CURRENT", "DEFERRED", "BEHIND-SHARED"])
def test_matched_arms_are_silent(verdict):
    """Both arms on the same verdict is the healthy state, INCLUDING both
    DEFERRED — that one is genuine design, and firing on it would be the
    cry-wolf shape ((gl)) that trains the reader to skip the guard."""
    assert not acc.arm_drift([_row(LIVE, verdict), _row(CTRL, verdict)])


def test_an_arm_missing_from_the_feed_makes_no_claim():
    """Fail-QUIET on absence, never a fabricated finding: an arm that is not
    publishing says nothing about pairing, and an absence is only evidence
    against a control group (I6)."""
    assert not acc.arm_drift([_row(LIVE, "CURRENT")])
    assert not acc.arm_drift([_row(CTRL, "CURRENT")])
    assert not acc.arm_drift([])


def test_the_dispatch_branch_expands_the_pair():
    """The workflow half. MUTATION: drop the `case` expansion -> RED.

    `arm_pairing_orphans` already required both names under ONE condition, and
    was GREEN throughout the incident: it inspects `svcs=` lines, and the
    dispatch branch assigns the operator's raw input. So the runtime guard
    above is necessary but not sufficient — the dispatch path itself must
    append the control arm.
    """
    wf = open(os.path.join(ROOT, ".github", "workflows",
                           "railway-redeploy.yml")).read()
    dispatch = wf.split('if [ "${{ github.event_name }}" = "workflow_dispatch" ]', 1)
    assert len(dispatch) == 2, "workflow has no workflow_dispatch branch"
    branch = dispatch[1].split("else", 1)[0]
    assert CTRL in branch, (
        f"the workflow_dispatch branch never appends {CTRL}: a dispatch "
        f"naming {LIVE} alone ships one arm and freezes the judge — the "
        f"18-Aug incident, reproduced")
    assert not adc.arm_pairing_orphans(), \
        "audit_deploy_coverage reports an unpaired arm route"
