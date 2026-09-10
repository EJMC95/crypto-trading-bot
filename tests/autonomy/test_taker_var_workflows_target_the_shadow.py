"""[2026-09-10 (zv)] A WORKFLOW MUST NOT RESTART A REAL-MONEY BOOK TO SET A
VARIABLE THAT BOOK CANNOT READ.

Eamon, 10-Sep: *"dont restart things untill bots have cleared their current
orders or you just lose more money"*.

THE DEFECT THIS PINS. `taker-live-bars.yml` and `taker-bull-mode.yml` set the
Ticket Taker's `TT_*` env vars and then run `railway redeploy --yes` on the
chosen arm. Both DEFAULTED to `tide-rider-lighter-live` — correct when written,
because that service ran the LIVE Ticket Taker. `(ma)` swapped the slot on
13-Aug: it now runs 🙏 Avo Maria (`lighter_avo_live_bot.py`) and the taker's
live arm is retired.

MEASURED 10-Sep — the arithmetic that makes it a pure cost:
    grep -c 'TT_TP|TT_SL|TT_MAX_HOLD_H|TT_BULL_MODE'
      lighter_avo_live_bot.py   0
      lighter_family_bot.py     0
      lighter_ticket_taker.py  25
So at its own default each workflow set variables nothing in the target
container reads, then bounced a REAL-MONEY container — benefit zero by
construction, cost one unmanaged window on a book that was holding positions
(9 open across the two live books when this was written; exits run in-process
and Lighter holds no resting stop).

It had already happened once and been recorded rather than closed — the
sibling's own header calls its first dispatch *"a NO-OP that bounced a
real-money container"*. The slot swap turned that one-off belief into a
STRUCTURAL certainty on every dispatch, which is why it is closed here.

Mutations that turn these red: a live service name returning to either
`options:` list or either `case` guard; the default drifting back; the refusal
branch being dropped; a NEW TT_* reader appearing in a live-host file.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.autonomy

WORKFLOWS = ("taker-live-bars.yml", "taker-bull-mode.yml")

#: Services that run REAL MONEY today. Derived, not typed: `fleet_books` is the
#: one declaration and `audit_live_roster` reconciles it against the feed.
LIVE_SERVICES = ("tide-rider-lighter-live", "mum-live", "trail-blazer-live")

#: The variables these two workflows exist to set.
TT_VARS = ("TT_TP", "TT_SL", "TT_MAX_HOLD_H", "TT_BULL_MODE")


def _wf(name):
    return (ROOT / ".github" / "workflows" / name).read_text()


@pytest.mark.parametrize("name", WORKFLOWS)
def test_no_real_money_service_is_dispatchable(name):
    """The `options:` list is what a human sees in the dropdown. A real-money
    service must not be one click away from a redeploy here."""
    src = _wf(name)
    opts = re.findall(r'^\s*-\s*"([a-z0-9-]+)"', src, re.M)
    assert opts, "no dispatch options parsed — rewrite this test"
    for svc in LIVE_SERVICES:
        assert svc not in opts, (
            f"{name} offers {svc} in its dropdown; selecting it would redeploy "
            "a real-money container to set a variable it does not read")
    assert "lighter-ticket-taker" in opts, \
        f"{name} must still be able to steer the shadow twin"


@pytest.mark.parametrize("name", WORKFLOWS)
def test_the_default_is_the_shadow_twin(name):
    src = _wf(name)
    m = re.search(r'arm:.*?default:\s*"([a-z0-9-]+)"', src, re.S)
    assert m, "no arm default found — rewrite this test"
    assert m.group(1) == "lighter-ticket-taker", \
        f"{name} defaults to {m.group(1)!r}; the default must be the paper arm"


@pytest.mark.parametrize("name", WORKFLOWS)
def test_the_shell_guard_refuses_the_retired_target_by_name(name):
    """Belt and braces: the dropdown is the UI, the `case` is the gate. A
    dispatch built by API or by an old bookmark must still be refused, and the
    refusal must SAY WHY (I8) rather than printing a bare 'invalid'."""
    src = _wf(name)
    assert "tide-rider-lighter-live)" in src, \
        "the retired target has no explicit refusal branch — an API dispatch " \
        "would fall through to the generic error and teach nothing"
    branch = src.split("tide-rider-lighter-live)", 1)[1][:600]
    assert "::error::" in branch and "exit 1" in branch, \
        "the retired target must refuse, not warn"
    assert "Avo" in branch or "avo" in branch, \
        "the refusal must name what actually runs there now"


@pytest.mark.parametrize("name", WORKFLOWS)
def test_the_case_guard_admits_only_the_shadow_twin(name):
    src = _wf(name)
    m = re.search(r'case "\$\{ARM_IN\}" in\n(.*?)\n\s*esac', src, re.S)
    assert m, "no ARM_IN case block found — rewrite this test"
    block = m.group(1)
    accepted = re.findall(r'^\s{12}([a-z0-9-]+)\)\s*;;\s*$', block, re.M)
    assert accepted == ["lighter-ticket-taker"], \
        f"{name} accepts {accepted}; only the shadow twin may pass"


def test_the_premise_holds_no_live_host_file_reads_a_TT_VAR():
    """The measurement the whole change rests on. If a live host ever DOES
    start reading TT_*, this test fails and the workflows must be re-decided
    rather than left pointing at the paper arm by habit."""
    pat = "|".join(TT_VARS)
    for f in ("lighter_avo_live_bot.py", "lighter_family_bot.py"):
        hits = len(re.findall(pat, (ROOT / f).read_text()))
        assert hits == 0, (
            f"{f} now reads a TT_* variable ({hits} hits) — the premise that "
            "these workflows cannot affect a live book no longer holds")
    taker = len(re.findall(pat, (ROOT / "lighter_ticket_taker.py").read_text()))
    assert taker > 0, \
        "the taker no longer reads TT_* — these workflows steer nothing"


def test_the_workflows_still_parse():
    yaml = pytest.importorskip("yaml")
    for name in WORKFLOWS:
        d = yaml.safe_load(_wf(name))
        assert d, name
        # `on:` parses as the boolean True in YAML 1.1
        inputs = d[True]["workflow_dispatch"]["inputs"]
        assert "arm" in inputs, name
