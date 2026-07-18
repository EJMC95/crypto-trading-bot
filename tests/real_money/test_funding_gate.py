"""Tier 1 — Funding Farmer entry gate: the 8x basis anchor + live-lever consumption.

Two real-money regressions live here:

1. THE 8x BUG. Lighter quotes funding per 8h; the live gate annualises via
   `H = funding_basis.periods_per_year("lighter")`. If H ever reverts to the
   hourly 24*365, the gate admits at 1/8 the intended APR — which is exactly how
   the live book ran at ~5% TRUE for as long as it existed. We lock H and the
   gate arithmetic so that regression cannot come back at THIS call site.

2. LIVE-LEVER CONSUMPTION. `apply_levers(mode)` overlays the growth-rail levers
   onto the live entry gate. A bad read here moves the bar that admits real
   orders. We assert author-lane isolation (live reads only live.funding.*,
   shadow only xp.funding.*), clean revert to env defaults, and fail-safe when
   the tuning organ is dark.
"""
import pytest

import funding_basis
import lighter_funding_bot as lfb


# ── the 8x basis anchor at the funding bot's own call site ───────────────────
def test_H_is_the_8h_lighter_convention():
    # 3 funding periods/day * 365 — NOT the hourly 24*365. This is the constant
    # whose corruption made the live book admit at 1/8 the intended APR.
    assert lfb.H == 1095.0
    assert lfb.H == funding_basis.periods_per_year("lighter")
    assert lfb.H != 24 * 365


def test_gate_compares_TRUE_apr():
    # The gate decision is `abs(rate * H) >= ENTER_GATE`. At the resting Lighter
    # default (9.6e-5 per 8h = 10.51% true) it must clear a 5% gate; a rate that
    # is only 5% true sits exactly on the boundary.
    resting = 9.6e-05
    assert abs(resting * lfb.H) >= 0.05           # 10.51% clears the 5% floor
    five_pct_true = 0.05 / lfb.H
    assert abs(five_pct_true * lfb.H) == pytest.approx(0.05)
    # If H were the buggy 24*365, that same 5%-true rate would read as 40% —
    # exactly 8x — so it (and almost everything) would clear the 5% gate. Lock
    # the 8x relationship so a revert to the hourly convention fails this test.
    buggy = abs(five_pct_true * (24 * 365))
    assert buggy == pytest.approx(0.05 * 8)     # 0.40 — 8x the true value
    assert buggy >= 0.05                        # would wrongly clear the gate


# ── apply_levers: live-lever consumption ─────────────────────────────────────
class _FakeTuning:
    def __init__(self, values):
        self.values = values     # {full_lever_key: value}
        self.asked = []

    def get_lever(self, key, default):
        self.asked.append(key)
        return self.values.get(key, default)


@pytest.fixture
def restore_bars():
    """Snapshot the module bars apply_levers mutates, and restore them after."""
    names = ("ENTER_APR", "SCAN_ENTER", "ENTER_GATE", "TAKE_PROFIT", "MAX_HOLD_H")
    saved = {n: getattr(lfb, n) for n in names}
    saved_tuning = lfb.tuning
    yield
    for n, v in saved.items():
        setattr(lfb, n, v)
    lfb.tuning = saved_tuning


def test_live_lever_moves_the_entry_gate(restore_bars, monkeypatch):
    monkeypatch.setattr(lfb, "tuning", _FakeTuning({"live.funding.enter_apr": 0.08}))
    moved = lfb.apply_levers("lighter_live")
    assert lfb.ENTER_APR == 0.08
    assert lfb.SCAN_ENTER == 0.08            # moved coherently — one gate
    assert lfb.ENTER_GATE == 0.08            # SCAN is on by default
    assert moved == {"live.funding.enter_apr": 0.08}


def test_live_arm_reads_only_live_prefix(restore_bars, monkeypatch):
    # A value on the SHADOW lane must NOT leak into the live gate (author-lane
    # isolation enforced at the consumer). Live keeps the env default.
    fake = _FakeTuning({"xp.funding.enter_apr": 0.30})
    monkeypatch.setattr(lfb, "tuning", fake)
    lfb.apply_levers("lighter_live")
    assert lfb.ENTER_APR == lfb._ENV_BARS["enter_apr"]     # untouched by xp.*
    assert all(k.startswith("live.funding.") for k in fake.asked)


def test_shadow_arm_reads_only_xp_prefix(restore_bars, monkeypatch):
    fake = _FakeTuning({"xp.funding.enter_apr": 0.30})
    monkeypatch.setattr(lfb, "tuning", fake)
    lfb.apply_levers("lighter_shadow")
    assert lfb.ENTER_APR == 0.30
    assert all(k.startswith("xp.funding.") for k in fake.asked)


def test_take_profit_and_max_hold_move_independently(restore_bars, monkeypatch):
    monkeypatch.setattr(lfb, "tuning", _FakeTuning({
        "live.funding.take_profit": 0.06,
        "live.funding.max_hold_h": 48,
    }))
    moved = lfb.apply_levers("lighter_live")
    assert lfb.TAKE_PROFIT == 0.06
    assert lfb.MAX_HOLD_H == 48
    assert lfb.ENTER_APR == lfb._ENV_BARS["enter_apr"]   # gate itself unmoved
    assert set(moved) == {"live.funding.take_profit", "live.funding.max_hold_h"}


def test_paper_mode_applies_no_levers(restore_bars, monkeypatch):
    # No prefix for paper/unknown mode -> env defaults, whatever levers exist.
    monkeypatch.setattr(lfb, "tuning", _FakeTuning({"live.funding.enter_apr": 0.08}))
    moved = lfb.apply_levers(None)
    assert moved == {}
    assert lfb.ENTER_APR == lfb._ENV_BARS["enter_apr"]


def test_dark_tuning_falls_back_to_env_defaults(restore_bars, monkeypatch):
    monkeypatch.setattr(lfb, "tuning", None)   # organ import failed
    moved = lfb.apply_levers("lighter_live")
    assert moved == {}
    assert lfb.ENTER_APR == lfb._ENV_BARS["enter_apr"]
    assert lfb.TAKE_PROFIT == lfb._ENV_BARS["take_profit"]


def test_lever_reverts_cleanly_when_it_expires(restore_bars, monkeypatch):
    # Apply a lever, then apply again with the lever gone (TTL expiry): the bar
    # must revert to the env default, not stick at the previous applied value.
    fake = _FakeTuning({"live.funding.enter_apr": 0.08})
    monkeypatch.setattr(lfb, "tuning", fake)
    lfb.apply_levers("lighter_live")
    assert lfb.ENTER_APR == 0.08
    fake.values.clear()                        # lever expired
    lfb.apply_levers("lighter_live")
    assert lfb.ENTER_APR == lfb._ENV_BARS["enter_apr"]
