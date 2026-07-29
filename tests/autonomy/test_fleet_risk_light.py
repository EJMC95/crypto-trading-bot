"""Tier 3 — fleet_risk's enforcement outputs: the light itself + the clip release.

Finding 5 (TEST_COVERAGE_ANALYSIS_2026-07-29.md): `light_for` — the function
that computes the fleet's GREEN/YELLOW/RED — had never executed under any
test, and `governed_clip_scale`'s own docstring says "extracted from main()
so the contract is unit-tested (it drove real money before it had a test)"
— yet no unit test existed in tests/. These are the two enforcement outputs
every consumer reads; both are pure.
"""
import pytest

import fleet_risk

pytestmark = pytest.mark.autonomy


# ── light_for: the traffic light ─────────────────────────────────────────────
def test_light_thresholds_at_the_documented_budget():
    b = fleet_risk.LONG_BUDGET          # 20 at the time of writing
    frac = fleet_risk.YELLOW_FRAC       # 0.7
    assert fleet_risk.light_for(0, b) == "green"
    assert fleet_risk.light_for(int(frac * b) - 1, b) == "green"
    assert fleet_risk.light_for(int(frac * b), b) == "yellow"   # exactly at 70%
    assert fleet_risk.light_for(b - 1, b) == "yellow"
    assert fleet_risk.light_for(b, b) == "red"                  # AT budget = red
    assert fleet_risk.light_for(b + 5, b) == "red"


def test_light_red_is_the_veto_boundary():
    # The L2 long-budget veto blocks NEW longs at budget; the light must agree
    # with the veto's boundary so the dashboard never shows green while the
    # strategies are being refused.
    assert fleet_risk.light_for(19, 20) == "yellow"
    assert fleet_risk.light_for(20, 20) == "red"


# ── governed_clip_scale: advisory releases the clip actuator ─────────────────
def test_enforce_passes_the_governor_value_through():
    pub, raw = fleet_risk.governed_clip_scale(0.5, "enforce")
    assert pub == 0.5 and raw == 0.5


def test_advisory_releases_the_clip_but_keeps_raw_for_forensics():
    # [IMB-16] FLEET_RISK_MODE=advisory is SENIOR: the published clip goes to
    # 1.0 (consumers size at full clip) while raw keeps the governor's value.
    # This is the documented deliberate scope expansion of 17-Jul — the kill
    # switch releases BOTH actuators, not just the long-budget veto.
    pub, raw = fleet_risk.governed_clip_scale(0.25, "advisory")
    assert pub == 1.0 and raw == 0.25


def test_any_non_enforce_mode_fails_open_to_full_clip():
    # A typo'd or unset mode must never leave the governor biting through a
    # thrown kill switch — the exact 15-Jul false-down-scale class.
    for mode in ("off", "", None, "ADVISORY-ish"):
        pub, raw = fleet_risk.governed_clip_scale(0.5, mode)
        assert pub == 1.0 and raw == 0.5, mode
