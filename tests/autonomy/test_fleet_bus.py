"""Tier 3 — fleet_bus: the consumer-side clamps + the L2 veto + advisory release.

fleet_bus is the ONE file strategies import to read the shared bus, so the
fail-safe contract lives here — and it was the shallowest-tested file on the
autonomy surface (its selftest covers only lever_outcome). The untested pieces
are the ones that actually bound real trading:

  * stake_multiplier's reduce-only [0.5, 1.0] clamp — the last guarantee the
    brain can "never size above full stake / below half". compute_stake_mults
    adds no clamp of its own, so this line is the backstop.
  * long_entries_blocked — the L2 long-budget veto, including the enforce-mode
    gate (FLEET_RISK_MODE=advisory is the central kill switch) and the
    stale -> fail-OPEN behaviour (never dead-man-switch the fleet on an outage).

Every test primes the module cache directly (no DB), exactly as the selftest does.
"""
from datetime import datetime, timedelta, timezone

import pytest

import fleet_bus

NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _prime(key, payload):
    fleet_bus._cache[key] = {"ts": NOW, "payload": payload}


@pytest.fixture(autouse=True)
def _clear_cache():
    fleet_bus._cache.clear()
    yield
    fleet_bus._cache.clear()


def _fresh(**extra):
    return {"updated": _iso(NOW), "ttl_sec": 2700, **extra}


# ── stake_multiplier: the reduce-only clamp ──────────────────────────────────
def test_stake_multiplier_reads_the_published_value():
    _prime("brain-stake-mults", _fresh(
        mults={"freqtrade-mum": {"long-momo": {"mult": 0.7}}}))
    assert fleet_bus.stake_multiplier("freqtrade-mum", "long-momo", NOW) == 0.7


def test_stake_multiplier_clamps_below_half_to_floor():
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": 0.1}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == fleet_bus.MULT_FLOOR == 0.5


def test_stake_multiplier_clamps_above_one_to_ceiling():
    # [2026-07-21 TWO-WAY, operator: "brain needs to be able to widen too"]
    # This test used to pin reduce-only (ceiling 1.0). The contract changed
    # deliberately: expand mults (1.25/1.5) pass, and the clamp now bounds
    # at 1.5 — anything above still cannot boost past it.
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": 1.5}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == fleet_bus.MULT_CEIL == 1.5
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": 3.0}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == 1.5, "over-ceiling clamps"
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": 1.25}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == 1.25, "expand step passes"


def test_stake_multiplier_neutral_on_missing_tag():
    _prime("brain-stake-mults", _fresh(mults={"b": {"other": {"mult": 0.5}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == 1.0


def test_stake_multiplier_neutral_when_stale():
    stale = _fresh(mults={"b": {"t": {"mult": 0.5}}})
    stale["updated"] = _iso(NOW - timedelta(hours=10))   # older than ttl
    _prime("brain-stake-mults", stale)
    assert fleet_bus.stake_multiplier("b", "t", NOW) == 1.0


def test_stake_multiplier_neutral_when_absent():
    _prime("brain-stake-mults", None)
    assert fleet_bus.stake_multiplier("b", "t", NOW) == 1.0


# ── long_entries_blocked: the veto + advisory kill switch ────────────────────
def test_veto_blocks_at_or_over_budget():
    _prime("fleet-risk", _fresh(mode="enforce", long_positions=20, long_budget=20))
    assert fleet_bus.long_entries_blocked(NOW) is True


def test_veto_allows_under_budget():
    _prime("fleet-risk", _fresh(mode="enforce", long_positions=19, long_budget=20))
    assert fleet_bus.long_entries_blocked(NOW) is False


def test_advisory_mode_releases_the_veto():
    # THE central kill switch: mode!=enforce -> no veto even at budget.
    _prime("fleet-risk", _fresh(mode="advisory", long_positions=99, long_budget=20))
    assert fleet_bus.long_entries_blocked(NOW) is False


def test_veto_fails_open_when_stale():
    stale = _fresh(mode="enforce", long_positions=99, long_budget=20)
    stale["updated"] = _iso(NOW - timedelta(hours=10))
    _prime("fleet-risk", stale)
    # A publisher outage must NOT freeze the whole fleet's long entries.
    assert fleet_bus.long_entries_blocked(NOW) is False


def test_veto_fails_open_when_absent():
    _prime("fleet-risk", None)
    assert fleet_bus.long_entries_blocked(NOW) is False


# ── is_fresh edges ───────────────────────────────────────────────────────────
def test_is_fresh_true_within_ttl():
    assert fleet_bus.is_fresh(_fresh(), NOW) is True


def test_is_fresh_false_when_expired():
    p = _fresh()
    p["updated"] = _iso(NOW - timedelta(hours=10))
    assert fleet_bus.is_fresh(p, NOW) is False


def test_is_fresh_false_on_future_timestamp():
    # negative age (clock skew / bad publisher) must not read as fresh
    p = _fresh()
    p["updated"] = _iso(NOW + timedelta(minutes=5))
    assert fleet_bus.is_fresh(p, NOW) is False


def test_is_fresh_false_on_missing_fields():
    assert fleet_bus.is_fresh({}, NOW) is False                       # no updated
    # missing ttl_sec defaults to 0, so any elapsed time reads as stale
    assert fleet_bus.is_fresh({"updated": _iso(NOW - timedelta(seconds=1))}, NOW) is False
