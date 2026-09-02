"""Tier 1 — SafetyRails: the kill switch, the daily-loss rails, and the boot gate.

These are the rails that decide whether a LIVE bot may start, whether it must
flatten mid-run, and whether a single dislocated equity print gets to force a
sell into the dislocation. venues/safety.py's own `_selftest` covers only
`open_notional` + `notional_ok` (the sizing math); everything that actually
STOPS real money — `confirm_daily_loss`'s fail-safe branches, `kill_check`,
`assert_can_start`, `daily_loss_hit`, env parsing — was untested. This file
covers it.
"""
import pytest

from venues import safety
from venues.safety import SafetyRails, kill_switch_armed


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Start every test from a known env so a stray CI var can't arm/disarm us.
    for k in ("REAL_MONEY_KILL", "LIGHTER_MAX_DAILY_LOSS",
              "TRAIL_BLAZER_MAX_NOTIONAL", "PERPS_DONCHIAN_BREAKOUT_MAX_NOTIONAL",
              "MY_BOT_MAX_NOTIONAL"):
        monkeypatch.delenv(k, raising=False)
    # _publish_refusal touches the DB-backed store; neutralize it so boot-gate
    # tests never depend on Postgres.
    monkeypatch.setattr(safety.SafetyRails, "_publish_refusal", lambda self, why: None)


# ── kill switch ──────────────────────────────────────────────────────────────
def test_kill_armed_by_default(monkeypatch):
    monkeypatch.delenv("REAL_MONEY_KILL", raising=False)
    assert kill_switch_armed() is True


def test_kill_armed_for_any_non_disarm_value(monkeypatch):
    for v in ("ARMED", "", "disarmed_i_understand", "DISARMED", "yes"):
        monkeypatch.setenv("REAL_MONEY_KILL", v)
        assert kill_switch_armed() is True, f"{v!r} must NOT disarm"


def test_kill_disarms_only_on_exact_token(monkeypatch):
    monkeypatch.setenv("REAL_MONEY_KILL", "DISARMED_I_UNDERSTAND")
    assert kill_switch_armed() is False
    # surrounding whitespace is stripped (operator convenience), value is exact
    monkeypatch.setenv("REAL_MONEY_KILL", "  DISARMED_I_UNDERSTAND\n")
    assert kill_switch_armed() is False


def test_kill_check_only_fires_when_live_and_armed(monkeypatch):
    monkeypatch.setenv("REAL_MONEY_KILL", "DISARMED_I_UNDERSTAND")
    live = SafetyRails("mybot", "lighter_live")
    assert live.kill_check() is False           # disarmed
    monkeypatch.setenv("REAL_MONEY_KILL", "ARMED")
    assert live.kill_check() is True            # armed -> flatten now
    shadow = SafetyRails("mybot", "lighter_shadow")
    assert shadow.kill_check() is False         # shadow never trades real money


# ── __init__ env parsing ─────────────────────────────────────────────────────
def test_notional_cap_from_generic_prefix(monkeypatch):
    monkeypatch.setenv("MY_BOT_MAX_NOTIONAL", "250")
    r = SafetyRails("my-bot", "lighter_live")
    assert r.max_notional == 250.0


def test_notional_cap_from_pilot_alias(monkeypatch):
    # perps-donchian-breakout accepts its fleet name TRAIL_BLAZER_MAX_NOTIONAL
    monkeypatch.setenv("TRAIL_BLAZER_MAX_NOTIONAL", "200")
    r = SafetyRails("perps-donchian-breakout", "lighter_live")
    assert r.max_notional == 200.0


def test_daily_loss_default_and_override(monkeypatch):
    assert SafetyRails("b", "lighter_live").max_daily_loss == 30.0
    monkeypatch.setenv("LIGHTER_MAX_DAILY_LOSS", "45")
    assert SafetyRails("b", "lighter_live").max_daily_loss == 45.0


# ── assert_can_start (boot gate) ─────────────────────────────────────────────
def test_boot_refuses_when_kill_armed(monkeypatch):
    monkeypatch.setenv("REAL_MONEY_KILL", "ARMED")
    monkeypatch.setenv("MY_BOT_MAX_NOTIONAL", "250")
    with pytest.raises(SystemExit):
        SafetyRails("my-bot", "lighter_live").assert_can_start()


def test_boot_refuses_when_no_notional_cap(monkeypatch):
    monkeypatch.setenv("REAL_MONEY_KILL", "DISARMED_I_UNDERSTAND")  # disarmed…
    # …but no *_MAX_NOTIONAL set -> must still refuse (no code-default cap)
    with pytest.raises(SystemExit):
        SafetyRails("my-bot", "lighter_live").assert_can_start()


def test_boot_ok_when_disarmed_and_capped(monkeypatch):
    monkeypatch.setenv("REAL_MONEY_KILL", "DISARMED_I_UNDERSTAND")
    monkeypatch.setenv("MY_BOT_MAX_NOTIONAL", "250")
    SafetyRails("my-bot", "lighter_live").assert_can_start()  # no raise


def test_boot_gate_is_noop_for_non_live(monkeypatch):
    # A shadow bot must boot even fully armed with no cap — rails are live-only.
    monkeypatch.setenv("REAL_MONEY_KILL", "ARMED")
    SafetyRails("my-bot", "lighter_shadow").assert_can_start()  # no raise


# ── daily_loss_hit (absolute-$ rail) ─────────────────────────────────────────
def test_daily_loss_hit_boundary(monkeypatch):
    monkeypatch.setenv("LIGHTER_MAX_DAILY_LOSS", "30")
    r = SafetyRails("b", "lighter_live")
    assert r.daily_loss_hit(1000.0, 970.0) is True    # exactly -$30
    assert r.daily_loss_hit(1000.0, 970.01) is False  # -$29.99, under the rail
    assert r.daily_loss_hit(1000.0, 950.0) is True    # well past


def test_daily_loss_hit_guards(monkeypatch):
    r_live = SafetyRails("b", "lighter_live")
    assert r_live.daily_loss_hit(0, 500.0) is False       # no day-start baseline
    assert r_live.daily_loss_hit(1000.0, None) is False    # unreadable equity
    r_shadow = SafetyRails("b", "lighter_shadow")
    assert r_shadow.daily_loss_hit(1000.0, 0.0) is False   # not live


# ── confirm_daily_loss (the one-print glitch guard) ──────────────────────────
# delay_s=0 so the 60s confirm sleep doesn't run in tests.
def _rails(monkeypatch, daily_loss="30"):
    monkeypatch.setenv("LIGHTER_MAX_DAILY_LOSS", daily_loss)
    return SafetyRails("b", "lighter_live")


def test_confirm_failsafe_on_read_exception(monkeypatch):
    r = _rails(monkeypatch)

    def boom():
        raise RuntimeError("venue API down")

    confirmed, eq = r.confirm_daily_loss(1000.0, 940.0, 0.05, boom, delay_s=0)
    # A crashing confirm read is EXACTLY when the venue is degraded — the breach
    # must count as CONFIRMED, and equity falls back to the first read.
    assert confirmed is True
    assert eq == 940.0


def test_confirm_failsafe_on_none_read(monkeypatch):
    r = _rails(monkeypatch)
    confirmed, eq = r.confirm_daily_loss(1000.0, 940.0, 0.05, lambda: None, delay_s=0)
    assert confirmed is True
    assert eq == 940.0


def test_confirm_true_when_second_read_still_breaching_pct(monkeypatch):
    r = _rails(monkeypatch, daily_loss="9999")  # take absolute rail out of play
    # pct_limit 5%: second read 940 <= 1000*0.95 -> still breaching
    confirmed, eq = r.confirm_daily_loss(1000.0, 930.0, 0.05, lambda: 940.0, delay_s=0)
    assert confirmed is True
    assert eq == 940.0  # caller adopts the fresher read


def test_confirm_true_via_absolute_rail_even_if_pct_ok(monkeypatch):
    # pct rail would NOT trip (990 > 950) but the absolute -$30 rail does.
    r = _rails(monkeypatch, daily_loss="30")
    confirmed, eq = r.confirm_daily_loss(1000.0, 930.0, 0.05, lambda: 969.0, delay_s=0)
    assert confirmed is True
    assert eq == 969.0


def test_confirm_false_when_transient(monkeypatch):
    # First print was a dislocation; second read recovered above both rails.
    r = _rails(monkeypatch, daily_loss="30")
    confirmed, eq = r.confirm_daily_loss(1000.0, 750.0, 0.05, lambda: 998.0, delay_s=0)
    assert confirmed is False
    # The docstring's contract: callers adopt the fresher credible read on BOTH
    # paths, so a dislocated first print never leaks into published equity.
    assert eq == 998.0
