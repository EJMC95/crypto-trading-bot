"""Tier 3 — fleet_bus: the consumer-side clamps + the L2 veto + advisory release.

fleet_bus is the ONE file strategies import to read the shared bus, so the
fail-safe contract lives here — and it was the shallowest-tested file on the
autonomy surface (its selftest covers only lever_outcome). The untested pieces
are the ones that actually bound real trading:

  * stake_multiplier's TWO-WAY [0.5, 1.5] clamp (reduce-only [0.5, 1.0]
    until 21-Jul) — the last guarantee the brain sizes inside the documented
    band. compute_stake_mults adds no clamp of its own, so this line is the
    backstop.
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


def test_stake_multiplier_clamps_below_the_floor():
    """[(sn)] the floor is 1/6.7, not 0.5 — 6.7x either way. A cut BELOW the
    floor still clamps, and a cut inside the new range now passes where it
    used to be flattened to 0.5, which is the whole point of the deeper rungs:
    the brain could always SEE the difference between a bad tag and a
    catastrophic one and had no way to say it."""
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": 0.001}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == fleet_bus.MULT_FLOOR
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": 0.25}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == 0.25, (
        "a cut inside the new range was flattened — the floor is clamping "
        "work the brain is now allowed to do")


def test_stake_multiplier_clamps_above_one_to_ceiling():
    # [2026-07-21 TWO-WAY, operator: "brain needs to be able to widen too"]
    # This test used to pin reduce-only (ceiling 1.0). The contract changed
    # deliberately: expand mults pass, and the clamp bounds the top.
    # [2026-08-20 (sm)] AND THE CEILING MOVED AGAIN, 1.5 -> 2.0, on the same
    # kind of deliberate contract change (operator: "training wheels need to
    # go off ... the brain that has every loss we've had or win"). The value
    # is asserted through `fleet_bus.MULT_CEIL` rather than retyped, so the
    # next move needs one edit and not two — but the BEHAVIOUR either side of
    # it is pinned literally, because that is what a clamp is for.
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": fleet_bus.MULT_CEIL}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == fleet_bus.MULT_CEIL
    assert fleet_bus.MULT_CEIL == 6.7, (
        "the ceiling moved without this contract being re-read — (sn) set it "
        "to 6.7 at Eamon's explicit ask; a change here must say why")
    assert abs(fleet_bus.MULT_FLOOR * fleet_bus.MULT_CEIL - 1.0) < 1e-12, (
        "6.7x EITHER WAY: the floor must stay the ceiling's reciprocal")
    _prime("brain-stake-mults", _fresh(
        mults={"b": {"t": {"mult": 9.0}}}))
    assert fleet_bus.stake_multiplier("b", "t", NOW) == 6.7, "over-ceiling clamps"
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


# ── entry_regime_gated (BRAIN ACTS, 21-Jul) ─────────────────────────────────
def _diag(mode="enforce", actions=None):
    return {"updated": _iso(NOW), "ttl_sec": 26000, "actions_mode": mode,
            "actions": actions if actions is not None else {
                "freqtrade-georgia-lshadow": {
                    "long-trend-breakout": {"action": "regime_gate"}}}}


def _oracle(read="risk-off"):
    return {"updated": _iso(NOW), "ttl_sec": 3600, "fleet": {"read": read}}


def test_regime_gate_bites_on_actionable_plus_riskoff():
    _prime("brain-diagnosis", _diag())
    _prime("regime-oracle", _oracle("risk-off"))
    assert fleet_bus.entry_regime_gated(
        "freqtrade-georgia-lshadow", "long-trend-breakout", NOW) is True


def test_regime_gate_lifts_when_regime_turns():
    _prime("brain-diagnosis", _diag())
    _prime("regime-oracle", _oracle("risk-on"))
    assert fleet_bus.entry_regime_gated(
        "freqtrade-georgia-lshadow", "long-trend-breakout", NOW) is False


def test_regime_gate_advisory_mode_is_the_kill_switch():
    _prime("brain-diagnosis", _diag(mode="advisory"))
    _prime("regime-oracle", _oracle("risk-off"))
    assert fleet_bus.entry_regime_gated(
        "freqtrade-georgia-lshadow", "long-trend-breakout", NOW) is False


def test_regime_gate_fails_open_on_stale_brain():
    d = _diag()
    d["updated"] = _iso(NOW - timedelta(hours=10))
    _prime("brain-diagnosis", d)
    _prime("regime-oracle", _oracle("risk-off"))
    assert fleet_bus.entry_regime_gated(
        "freqtrade-georgia-lshadow", "long-trend-breakout", NOW) is False


def test_regime_gate_fails_open_on_stale_oracle():
    _prime("brain-diagnosis", _diag())
    o = _oracle("risk-off")
    o["updated"] = _iso(NOW - timedelta(hours=10))
    _prime("regime-oracle", o)
    assert fleet_bus.entry_regime_gated(
        "freqtrade-georgia-lshadow", "long-trend-breakout", NOW) is False


def test_regime_gate_other_tags_untouched():
    _prime("brain-diagnosis", _diag())
    _prime("regime-oracle", _oracle("risk-off"))
    assert fleet_bus.entry_regime_gated(
        "freqtrade-georgia-lshadow", "long-range-on", NOW) is False
    assert fleet_bus.entry_regime_gated(
        "freqtrade-mum-lshadow", "long-trend-breakout", NOW) is False


# ── long_symbol_blocked (pileup cap, 21-Jul) ────────────────────────────────
def _risk_symcap(mode="enforce", cap=3, by_symbol=None):
    return {"updated": _iso(NOW), "ttl_sec": 900,
            "symbol_cap": {"mode": mode, "cap": cap,
                           "long_by_symbol": by_symbol or {}}}


def test_symbol_cap_blocks_at_cap():
    _prime("fleet-risk", _risk_symcap(by_symbol={"ETH": 3}))
    assert fleet_bus.long_symbol_blocked("ETH", NOW) is True
    assert fleet_bus.long_symbol_blocked("ETH/USDC", NOW) is True   # base split


def test_symbol_cap_open_below_cap_and_for_unlisted():
    _prime("fleet-risk", _risk_symcap(by_symbol={"ETH": 2}))
    assert fleet_bus.long_symbol_blocked("ETH", NOW) is False
    assert fleet_bus.long_symbol_blocked("BTC", NOW) is False


def test_symbol_cap_advisory_mode_inert():
    _prime("fleet-risk", _risk_symcap(mode="advisory", by_symbol={"ETH": 9}))
    assert fleet_bus.long_symbol_blocked("ETH", NOW) is False


def test_symbol_cap_fails_open_stale_or_capzero():
    stale = _risk_symcap(by_symbol={"ETH": 9})
    stale["updated"] = _iso(NOW - timedelta(hours=10))
    _prime("fleet-risk", stale)
    assert fleet_bus.long_symbol_blocked("ETH", NOW) is False
    _prime("fleet-risk", _risk_symcap(cap=0, by_symbol={"ETH": 9}))
    assert fleet_bus.long_symbol_blocked("ETH", NOW) is False


def test_symbol_cap_cap1_enforces_on_single_long():
    # [2026-07-21] the cap=1 case that under-enforced before fleet_risk
    # published counts >= min(2, cap): a single held long must block the 2nd
    _prime("fleet-risk", _risk_symcap(cap=1, by_symbol={"ETH": 1}))
    assert fleet_bus.long_symbol_blocked("ETH", NOW) is True
