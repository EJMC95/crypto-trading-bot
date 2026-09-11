"""Kill switch, system health, and the live gate's fail-closed behaviour."""
import os

import pytest

from lighter_bots import health as H
from lighter_bots.config import AppConfig, LiveGate, flatten_confirmed
from lighter_bots.models import Regime
from lb_helpers import ramp

ENV_OK = {
    "ENABLE_LIVE_TRADING": "true",
    "LIVE_CONFIRMATION": "I_UNDERSTAND_THE_RISK",
    "LIGHTER_ACCOUNT_INDEX": "42",
    "LIGHTER_API_KEY_INDEX": "3",
    "LIGHTER_API_PRIVATE_KEY": "0xdeadbeef",
}
ALL_OK = dict(soak_days=45.0, soak_signals=250, metadata_valid=True,
              account_reconciled=True, protective_capability=True,
              nonce_ok=True, interactive_confirmed=True)


def _cfg(tmp_path):
    c = AppConfig()
    c.runtime_dir = str(tmp_path / "runtime")
    c.state_dir = str(tmp_path / "state")
    os.makedirs(c.runtime_dir, exist_ok=True)
    os.makedirs(c.state_dir, exist_ok=True)
    return c


def test_kill_switch_is_detected_by_presence(tmp_path):
    c = _cfg(tmp_path)
    assert not H.kill_switch_active(c.runtime_dir)
    open(H.kill_switch_path(c.runtime_dir), "w").write("halt")
    assert H.kill_switch_active(c.runtime_dir)


def test_the_example_file_does_not_arm_the_switch(tmp_path):
    c = _cfg(tmp_path)
    open(os.path.join(c.runtime_dir, "KILL_SWITCH.example"), "w").write("x")
    assert not H.kill_switch_active(c.runtime_dir), \
        "the shipped .example must never halt a system by existing"


def test_the_gate_opens_only_when_everything_agrees(tmp_path):
    c = _cfg(tmp_path)
    g = LiveGate(c, env=dict(ENV_OK)).evaluate(**ALL_OK)
    assert g.allowed and not g.blockers


@pytest.mark.parametrize("drop", sorted(ENV_OK))
def test_each_missing_env_var_closes_the_gate(tmp_path, drop):
    env = {k: v for k, v in ENV_OK.items() if k != drop}
    g = LiveGate(_cfg(tmp_path), env=env).evaluate(**ALL_OK)
    assert not g.allowed and g.blockers


def test_the_wrong_confirmation_phrase_closes_the_gate(tmp_path):
    env = dict(ENV_OK, LIVE_CONFIRMATION="i understand the risk")
    g = LiveGate(_cfg(tmp_path), env=env).evaluate(**ALL_OK)
    assert not g.allowed and "live_confirmation" in g.blockers


@pytest.mark.parametrize("flag", ["metadata_valid", "account_reconciled",
                                  "protective_capability", "nonce_ok",
                                  "interactive_confirmed"])
def test_each_preflight_condition_closes_the_gate(tmp_path, flag):
    kw = dict(ALL_OK)
    kw[flag] = False
    g = LiveGate(_cfg(tmp_path), env=dict(ENV_OK)).evaluate(**kw)
    assert not g.allowed


def test_the_kill_switch_closes_the_gate(tmp_path):
    c = _cfg(tmp_path)
    open(H.kill_switch_path(c.runtime_dir), "w").write("halt")
    g = LiveGate(c, env=dict(ENV_OK)).evaluate(**ALL_OK)
    assert not g.allowed and "no_kill_switch" in g.blockers


def test_an_incomplete_soak_closes_the_gate(tmp_path):
    kw = dict(ALL_OK, soak_days=10.0, soak_signals=20)
    g = LiveGate(_cfg(tmp_path), env=dict(ENV_OK)).evaluate(**kw)
    assert not g.allowed and "soak_complete" in g.blockers


def test_the_soak_override_is_explicit_and_recorded(tmp_path):
    env = dict(ENV_OK, LIVE_SOAK_OVERRIDE="true")
    kw = dict(ALL_OK, soak_days=0.0, soak_signals=0)
    g = LiveGate(_cfg(tmp_path), env=env).evaluate(**kw)
    assert g.allowed
    assert g.checks.get("soak_overridden_documented") is True


def test_risk_above_a_hard_ceiling_closes_the_gate(tmp_path):
    c = _cfg(tmp_path)
    c.risk.risk_per_trade = 0.5          # 50% per trade
    g = LiveGate(c, env=dict(ENV_OK)).evaluate(**ALL_OK)
    assert not g.allowed and "risk_within_ceilings" in g.blockers


def test_flatten_needs_its_own_phrase():
    assert not flatten_confirmed(env={})
    assert not flatten_confirmed(env={"FLATTEN_CONFIRMATION": "yes"})
    assert flatten_confirmed(env={"FLATTEN_CONFIRMATION": "CLOSE_ALL_POSITIONS"})


def test_system_health_fails_on_stale_candles(tmp_path):
    c = _cfg(tmp_path)
    old = ramp(60, tf_sec=3600, t0=1_600_000_000)
    hc = H.check(runtime_dir=c.runtime_dir, metadata_version="v1",
                 metadata_age_s=10.0, candles={"BTC": old}, timeframe="1h",
                 ws_health=None, nonce_ok=(True, "ok"),
                 account_reconciled=True, regime=Regime.BULLISH)
    assert not hc.ok and any("candles_fresh" in f for f in hc.failures())


def test_system_health_fails_without_metadata(tmp_path):
    c = _cfg(tmp_path)
    hc = H.check(runtime_dir=c.runtime_dir, metadata_version=None,
                 metadata_age_s=None, candles={}, timeframe="1h",
                 ws_health=None, nonce_ok=None, account_reconciled=True,
                 regime=None)
    assert not hc.ok
    assert any("market_metadata" in f for f in hc.failures())


def test_system_health_fails_in_panic(tmp_path):
    import time
    c = _cfg(tmp_path)
    fresh = ramp(60, tf_sec=3600, t0=int(time.time()) - 60 * 3600)
    hc = H.check(runtime_dir=c.runtime_dir, metadata_version="v1",
                 metadata_age_s=10.0, candles={"BTC": fresh}, timeframe="1h",
                 ws_health=None, nonce_ok=(True, "ok"),
                 account_reconciled=True, regime=Regime.PANIC)
    assert not hc.ok and any("regime_tradable" in f for f in hc.failures())


def test_health_render_names_every_failure(tmp_path):
    c = _cfg(tmp_path)
    hc = H.check(runtime_dir=c.runtime_dir, metadata_version=None,
                 metadata_age_s=None, candles={}, timeframe="1h",
                 ws_health={"connected": False, "stale_s": 99,
                            "reconnects": 4},
                 nonce_ok=(False, "2 UNKNOWN"), account_reconciled=False,
                 regime=Regime.DATA_UNRELIABLE)
    text = hc.render()
    assert "NOT HEALTHY" in text
    for name in ("market_metadata", "websocket", "nonce_manager",
                 "account_reconciled", "regime_tradable"):
        assert name in text


def test_the_live_gate_never_copies_the_whole_environment(tmp_path):
    """Least privilege on secret material.

    An earlier version did `dict(os.environ)`, which copied every secret in
    the process onto a long-lived object that is passed around and partially
    rendered by `preflight`. The gate needs six names; it keeps six names."""
    from lighter_bots.config import _GATE_ENV_KEYS
    env = dict(ENV_OK)
    env["UNRELATED_API_SECRET"] = "sk-should-never-be-copied"
    env["AWS_SECRET_ACCESS_KEY"] = "also-not-ours"
    gate = LiveGate(_cfg(tmp_path), env=env)
    assert set(gate.env) == set(_GATE_ENV_KEYS)
    blob = repr(gate.env)
    assert "sk-should-never-be-copied" not in blob
    assert "also-not-ours" not in blob


def test_the_gate_still_reads_the_variables_it_does_keep(tmp_path):
    """The narrowing must not have broken the gate: with everything present
    it opens, and dropping one of the kept names closes it."""
    gate = LiveGate(_cfg(tmp_path), env=dict(ENV_OK))
    assert gate.evaluate(**ALL_OK).allowed
    missing = {k: v for k, v in ENV_OK.items()
               if k != "LIGHTER_API_PRIVATE_KEY"}
    closed = LiveGate(_cfg(tmp_path), env=missing).evaluate(**ALL_OK)
    assert not closed.allowed and "api_private_key" in closed.blockers
