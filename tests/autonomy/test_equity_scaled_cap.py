#!/usr/bin/env python3
"""[2026-08-26 (to)] THE FIXED-DOLLAR-CAP CLASS CLOSES: EQUITY_SCALED_CAP.

Third measured instance in three weeks of a fixed-dollar rail on an
equity-derived book — (sr) the deposit that stranded a slot at cap $200, the
farmer-cap HANDOFF row, and 26-Aug avo at cap_slots 3 of 5. The (tn)
one-shot fixed the VALUES; this closes the CLASS: with the switch on,
`SafetyRails.equity_scale` re-derives the cap every loop as
max(env floor, equity x gross x 1.05).

What is pinned here, in fail-safe order:
  * OFF is byte-identical to the pre-(to) rails — the default must change
    NOTHING on any service that has not opted in;
  * the operator's env value is a FLOOR the scaled cap can never undercut;
  * a dark/junk equity read moves NOTHING (I4 — a real-money rail must not
    be steered by an unreadable number);
  * a rail with NO env cap never GAINS one from scaling;
  * the live host actually calls it each loop and publishes cap_src.

The switch is read at import, so these tests reload venues.safety under a
controlled env and restore the original module afterwards — a leaked reload
would poison identity checks in the rest of the suite.
"""
import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import venues.safety as safety_mod  # noqa: E402

BOT = "unit-cap-bot"
CAP_ENV = "UNIT_CAP_BOT_MAX_NOTIONAL"


@pytest.fixture
def scaled_safety(monkeypatch):
    """venues.safety reloaded with the switch ON and a $1700 floor; restored
    to the ORIGINAL import (switch off) afterwards, whatever happens."""
    monkeypatch.setenv("EQUITY_SCALED_CAP", "1")
    monkeypatch.setenv(CAP_ENV, "1700")
    mod = importlib.reload(safety_mod)
    yield mod
    monkeypatch.delenv("EQUITY_SCALED_CAP", raising=False)
    importlib.reload(safety_mod)


def _rails(mod, cap="1700"):
    os.environ[CAP_ENV] = cap
    return mod.SafetyRails(BOT, "lighter_live")


# ------------------------------------------------------------- OFF = inert
def test_switch_off_is_byte_identical(monkeypatch):
    monkeypatch.delenv("EQUITY_SCALED_CAP", raising=False)
    monkeypatch.setenv(CAP_ENV, "1700")
    mod = importlib.reload(safety_mod)
    try:
        r = _rails(mod)
        assert mod.EQUITY_SCALED_CAP is False
        assert r.equity_scale(10_000.0, 5.0) == 1700.0
        assert r.max_notional == 1700.0 and r.cap_src == "env", (
            "the default must change nothing on a service that has not "
            "opted in")
    finally:
        importlib.reload(safety_mod)


# ------------------------------------------------------- ON = floor + scale
def test_floor_binds_below_crossover_and_scaling_above(scaled_safety):
    r = _rails(scaled_safety)
    # avo's 26-Aug numbers: 319.6 x 5 x 1.05 = 1677.9 < 1700 -> floor binds
    assert r.equity_scale(319.6, 5.0) == 1700.0
    assert r.cap_src == "env"
    # equity outgrows the floor -> scaling takes over smoothly
    assert r.equity_scale(340.0, 5.0) == pytest.approx(340.0 * 5.0 * 1.05)
    assert r.cap_src == "scaled"
    assert r.notional_ok(0.0, 1780.0) and not r.notional_ok(0.0, 1790.0), (
        "notional_ok must consume the scaled value")


def test_the_cap_never_undercuts_the_operator_floor(scaled_safety):
    r = _rails(scaled_safety)
    r.equity_scale(400.0, 5.0)                       # scaled to 2100
    assert r.equity_scale(100.0, 5.0) == 1700.0, (
        "an equity collapse tightens back to the FLOOR, never below it")
    assert r.cap_src == "env"


def test_junk_equity_moves_nothing(scaled_safety):
    r = _rails(scaled_safety)
    r.equity_scale(400.0, 5.0)
    before = r.max_notional
    for eq, g in ((None, 5.0), (float("nan"), 5.0), (float("inf"), 5.0),
                  (0.0, 5.0), (-5.0, 5.0), (400.0, 0.0), (400.0, None),
                  ("junk", 5.0)):
        assert r.equity_scale(eq, g) == before
        assert r.max_notional == before, (eq, g)


def test_a_capless_rail_never_gains_a_cap(scaled_safety, monkeypatch):
    monkeypatch.delenv(CAP_ENV, raising=False)
    r = scaled_safety.SafetyRails(BOT, "lighter_shadow")
    assert r.max_notional is None
    assert r.equity_scale(400.0, 5.0) is None
    assert r.max_notional is None, (
        "scaling must never invent a cap the operator did not set")


# ----------------------------------------------------------- host wiring
def test_the_live_host_scales_each_loop_and_publishes_the_source():
    src = open(os.path.join(ROOT, "lighter_avo_live_bot.py")).read()
    assert "rails.equity_scale(equity, gross_x())" in src, (
        "the host no longer re-derives the cap from its fresh equity read — "
        "the (to) switch would be registered-but-inert (I18)")
    assert '"cap_src": getattr(rails, "cap_src", "env")' in src, (
        "cap_src is no longer published beside cap_usd")
