"""An organ whose loop DIES must be able to reach the operator.

INCIDENT (2026-08-01, found by the daily review). Two `( while true; ... ) &`
subshells in `run_all.sh` had stopped ~12.5h earlier — `bot_learn` and
`event_sentinel` — inside a container whose other ~20 organs were publishing
seconds fresh. Measured ages: `brain-vitals` 12.87h (TTL 7.2h),
`event-sentinel` / `event-sentinel-state` / `tuning-proposals` 12.52h
(TTL 0.67h, i.e. 18.8x). Consequences were already live and measurable —
`scout-tuner` logged *"brain dark (lens-forward stale/absent) — lens-keyed bar
walks suppressed"*, so the growth rail's most active author was running at
reduced authority, and the sentinel's proposal channel had no proposer.

**Nothing paged for 12.5 hours.** `fleet_watchdog_svc` pages only on organs
flagged `critical` in `ORGAN_SPECS` (`fleet_watchdog_svc.py:271`), and
`event-sentinel` was that organ's ONLY key and was non-critical — so the organ
was structurally unpageable, not merely quiet.

WHY (hw)'s WRAPPER CANNOT COVER THIS. `bot_pnl_store.organ_main` records a
crash on the organ's own key. A subshell that has DIED runs no handler, records
nothing, and leaves every key it ever wrote looking exactly as it did at the
last successful publish. Death-of-the-loop is only ever visible from OUTSIDE,
by age — which is what `ORGAN_SPECS` + the watchdog are for. So the wrapper and
this list are complements, and the list was the half with the hole.

These tests do not try to flip all 19 non-critical TTL'd keys. The file's own
comment sets the policy — *"the rest bed in as non-critical to avoid a pager
storm, promote per-organ once proven"* — and a pager nobody trusts is the
documented failure mode. What they pin is that the unpageable surface is
DECLARED and cannot grow silently.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
DASH = ROOT / "pnl_dashboard.py"
WATCHDOG = ROOT / "fleet_watchdog_svc.py"

#: Keys that carry a TTL (so staleness is meaningful) yet cannot page. Each is
#: a deliberate bedding-in choice per the ORGAN_SPECS comment. Adding a key
#: here is a decision to accept silent death for that organ; REMOVING one by
#: promoting it to critical is always allowed and never fails this test.
UNPAGEABLE_OK = {
    "brain-stake-mults", "brain-lens-forward", "brain-diagnosis",
    "signal-bus", "regime-oracle", "scout-tuner", "fleet-proprioception",
    "strategy-incubator", "fleet-radar", "golive-readiness", "xp-queue",
    "xp-judge", "fleet-regen", "fleet-clock", "impl-shortfall",
    "parliament", "parliament-tuning",
}


def specs():
    """-> [(key, critical: bool, ttl_s: int|None)] parsed from ORGAN_SPECS.

    Read from source rather than imported: importing `pnl_dashboard` starts a
    server. The list is a literal, so this is a faithful read of the shipped
    value, not a re-derivation of it.
    """
    src = DASH.read_text()
    blk = src[src.index("ORGAN_SPECS = ["):]
    blk = blk[:blk.index("\n]") + 2]
    out = []
    for key, crit, ttl in re.findall(
            r'\(\s*"([^"]+)",\s*"[^"]*",\s*(True|False),\s*(None|\d+)\)', blk):
        out.append((key, crit == "True", None if ttl == "None" else int(ttl)))
    assert len(out) >= 25, f"ORGAN_SPECS parse looks wrong: got {len(out)} rows"
    return out


def test_the_watchdog_still_pages_only_on_critical():
    """The premise of every assertion below. If the watchdog ever pages on all
    organs, `critical` stops being load-bearing and these tests are theatre —
    they should be re-read, not silently kept passing."""
    assert re.search(r'o\.get\("critical"\)\s+and\s+o\.get\("status"\)',
                     WATCHDOG.read_text()), (
        "fleet_watchdog_svc no longer gates paging on `critical` — the "
        "pageability model changed; re-read this whole file")


def test_event_sentinel_is_pageable():
    """THE INCIDENT. Dark 12.5h at 18.8x its own TTL, sole key of its organ,
    non-critical, zero pages. It is also the sole publisher of
    `tuning-proposals`, so its death removes a growth-rail proposer."""
    by_key = {k: (c, t) for k, c, t in specs()}
    assert "event-sentinel" in by_key, "event-sentinel left ORGAN_SPECS"
    crit, ttl = by_key["event-sentinel"]
    assert crit, ("event-sentinel must be watchdog-critical — it went DARK for "
                  "12.5h on 01-Aug and nothing paged")
    assert ttl and ttl <= 3600, (
        f"event-sentinel TTL {ttl}s is too loose for a 600s loop — DARK is 3x "
        "TTL, so a slack TTL re-opens the same silent window")


def test_no_organ_becomes_unpageable_without_being_declared():
    """THE RATCHET, and the part that closes the class.

    A key with a TTL but no `critical` flag is one whose loop can die in
    silence. That set is allowed to exist — the bedding-in doctrine is
    deliberate — but it must be WRITTEN DOWN, so a new organ cannot join it by
    default and a promotion cannot be quietly reverted. Failing in the
    ADD direction only: shrinking the set always passes.
    """
    unpageable = {k for k, crit, ttl in specs() if not crit and ttl is not None}
    undeclared = unpageable - UNPAGEABLE_OK
    assert not undeclared, (
        f"these organs carry a TTL but cannot page, and are not declared: "
        f"{sorted(undeclared)} — either mark them critical in ORGAN_SPECS or "
        "add them to UNPAGEABLE_OK, accepting that their loop can die silently")


def test_declared_unpageable_keys_still_exist():
    """A stale declaration hides a real gap: if a key is renamed, its entry
    here keeps excusing a key that no longer exists while the new one goes
    undeclared. Same arm `audit_doctrine_enforcement` (hy) puts on ENFORCED BY."""
    keys = {k for k, _, _ in specs()}
    gone = UNPAGEABLE_OK - keys
    assert not gone, f"UNPAGEABLE_OK names keys not in ORGAN_SPECS: {sorted(gone)}"


@pytest.mark.parametrize("key", ["fleet-risk", "lighter-market", "fleet-immune",
                                 "fleet-respiration", "learning-brain",
                                 "coin-vetoes"])
def test_the_established_critical_organs_stay_critical(key):
    """Demotion is the quiet way to un-arm a pager. `coin-vetoes` gates the
    LIVE Funding Farmer and FAILS OPEN when stale; `learning-brain` is the
    brain's only pageable key."""
    by_key = {k: c for k, c, _ in specs()}
    assert by_key.get(key) is True, f"{key} was demoted out of paging"


#: The brain publishes a MEMORY key and a HEARTBEAT key, and they fail
#: independently. Both must be able to page, or one fault masks the other.
BRAIN_MEMORY, BRAIN_HEARTBEAT = "learning-brain", "brain-vitals"


def test_the_brain_has_a_liveness_alarm_distinct_from_its_memory_alarm():
    """INCIDENT (01-Aug). `learning-brain` was the brain's ONLY critical key.
    It is written by `_save_state`, and (hw)/(hx) showed it goes dark for a
    cause that is NOT process death — the run crashed after publishing, so
    memory froze while vitals stayed fresh. It had therefore been DARK and
    paging continuously since 28-Jul. When `bot_learn` actually STOPPED at
    16:02Z on 31-Jul, there was no new signal to give: 13.8h later nothing had
    paged, while `scout-tuner` logged "brain dark ... lens-keyed bar walks
    suppressed" — the growth rail degraded, silently.

    `brain-vitals` is the per-run heartbeat, published every run BEFORE
    `_save_state`, so it separates "not running" from "cannot remember".
    """
    by_key = {k: (c, t) for k, c, t in specs()}
    for key in (BRAIN_MEMORY, BRAIN_HEARTBEAT):
        assert key in by_key, f"{key} left ORGAN_SPECS"
        assert by_key[key][0], (
            f"{key} must be watchdog-critical — the brain needs BOTH a memory "
            "alarm and a liveness alarm; one masks the other")


def test_the_brain_heartbeat_goes_dark_within_a_working_day():
    """A TTL loose enough to hide a stopped loop for a day is the defect, not
    the flag. DARK is 3x TTL (`organ_status`) and the loop is 7200s, so the
    old 26000s put DARK at 21.7h — nine missed cycles."""
    ttl = {k: t for k, _, t in specs()}[BRAIN_HEARTBEAT]
    assert ttl is not None, "the brain heartbeat must be TTL'd, not EVENT-typed"
    dark_h = 3 * ttl / 3600.0
    assert dark_h <= 9.0, (
        f"brain-vitals goes DARK only after {dark_h:.1f}h — a stopped 2h loop "
        "must surface inside a working day")
    assert ttl >= 7200, (
        f"TTL {ttl}s is below the 7200s loop period — one ordinary cycle would "
        "read LATE on every single run, which is how an alarm becomes noise")
