"""The locks. Every test here is a way the system must REFUSE."""
import os

import pytest

from downtrend_bot import config as C
from downtrend_bot.config import (LIVE_CONFIRMATION_PHRASE, AppConfig, LiveGate,
                                  Mode, _GATE_ENV_KEYS, flatten_confirmed,
                                  validate)
from downtrend_bot.health import kill_switch_active, kill_switch_path

ENV_OK = {"ENABLE_LIVE_TRADING": "true",
          "LIVE_CONFIRMATION": LIVE_CONFIRMATION_PHRASE}
ALL_OK = dict(paper_days=45.0, paper_trades=40, paper_report_exists=True,
              paper_checks_passed=True, account_reconciled=True,
              protective_capability=True, data_healthy=True,
              interactive_confirmed=True)


def gate(cfg, **env):
    e = dict(ENV_OK)
    e.update(env)
    return LiveGate(cfg, env=e)


# --------------------------------------------------------------- defaults --
def test_the_default_mode_is_backtest():
    assert AppConfig().mode is Mode.BACKTEST


def test_a_default_config_is_valid():
    assert validate(AppConfig()) == []


def test_the_default_leverage_ceiling_is_one_point_five():
    """Spec 1, verbatim: 'Start with leverage limited to 1.5x.'"""
    assert AppConfig().risk.max_leverage == 1.5


def test_hard_ceilings_reject_rather_than_clamp(tmp_path):
    """Clamping is the dangerous choice: the operator asked for 10x, got 3x,
    and was told nothing. A config that asks for something forbidden must
    FAIL, so the mismatch is impossible to miss."""
    cfg = AppConfig()
    cfg.risk.max_leverage = 25.0
    problems = validate(cfg)
    assert problems and "hard ceiling" in problems[0]
    assert cfg.risk.max_leverage == 25.0, "validate() must not silently clamp"


def test_risk_per_trade_above_the_portfolio_budget_is_refused():
    cfg = AppConfig()
    cfg.risk.risk_per_trade = 0.05
    cfg.risk.max_portfolio_risk = 0.01
    assert any("max_portfolio_risk" in p for p in validate(cfg))


def test_bearish_must_disable_new_longs():
    cfg = AppConfig()
    cfg.regime.bearish_risk_multiplier = 0.9
    assert any("bearish_risk_multiplier" in p for p in validate(cfg))


def test_panic_must_forbid_entries():
    cfg = AppConfig()
    cfg.regime.panic_risk_multiplier = 0.5
    assert any("panic_risk_multiplier" in p for p in validate(cfg))


def test_live_mode_requires_reduce_only_exits():
    cfg = AppConfig()
    cfg.mode = Mode.LIVE
    cfg.execution.use_reduce_only_exits = False
    assert any("reduce_only" in p for p in validate(cfg))


def test_an_unknown_config_key_is_refused_not_ignored(tmp_path):
    """A silently ignored key is a setting the operator believes is applied."""
    p = tmp_path / "c.yaml"
    p.write_text("risk:\n  risk_per_trade: 0.001\n  totally_made_up: 5\n")
    with pytest.raises(ValueError, match="unknown key"):
        C.load(str(p))


# ------------------------------------------------------------- live gate ---
def test_the_gate_is_closed_with_no_environment_at_all(cfg):
    g = LiveGate(cfg, env={})
    assert not g.evaluate(**ALL_OK).allowed


def test_the_gate_opens_only_when_every_lock_is_open(cfg):
    assert gate(cfg).evaluate(**ALL_OK).allowed


@pytest.mark.parametrize("drop", sorted(ALL_OK))
def test_removing_any_single_precondition_closes_the_gate(cfg, drop):
    """Each lock alone must be sufficient to refuse. This is the test that
    catches a lock that was written and never wired to the `all()`."""
    kw = dict(ALL_OK)
    kw[drop] = 0.0 if isinstance(kw[drop], float) else (
        0 if isinstance(kw[drop], int) and not isinstance(kw[drop], bool)
        else False)
    assert not gate(cfg).evaluate(**kw).allowed, f"{drop} did not gate"


def test_the_wrong_confirmation_phrase_closes_the_gate(cfg):
    g = gate(cfg, LIVE_CONFIRMATION="i understand the risk")
    assert not g.evaluate(**ALL_OK).allowed


def test_enable_live_trading_must_be_exactly_true(cfg):
    for v in ("1", "yes", "TRUE ", "", "false"):
        g = gate(cfg, ENABLE_LIVE_TRADING=v)
        got = g.evaluate(**ALL_OK)
        if v.strip().lower() == "true":
            assert got.allowed
        else:
            assert not got.allowed, v


def test_a_kill_switch_file_closes_the_gate(cfg):
    open(kill_switch_path(cfg.runtime_dir), "w").close()
    assert not gate(cfg).evaluate(**ALL_OK).allowed
    assert kill_switch_active(cfg.runtime_dir)


def test_the_gate_never_copies_the_whole_environment(cfg):
    """Least privilege on secret material: the gate needs two names, so it
    keeps two names -- it does not take a snapshot of every secret in the
    process and carry it on a long-lived object."""
    env = dict(ENV_OK)
    env["EXCHANGE_API_SECRET"] = "sk-must-never-be-copied"
    g = LiveGate(cfg, env=env)
    assert set(g.env) == set(_GATE_ENV_KEYS)
    assert "sk-must-never-be-copied" not in repr(g.env)


def test_the_soak_override_is_recorded_and_cannot_be_silent(cfg):
    """It exists, it works, and it leaves a fingerprint in the check map --
    so a bypassed soak can never look like a passed one."""
    g = gate(cfg, PAPER_SOAK_OVERRIDE="true")
    got = g.evaluate(**{**ALL_OK, "paper_days": 0.0, "paper_trades": 0})
    assert got.checks["paper_soak_complete"]
    assert got.checks.get("paper_soak_overridden_documented") is True


def test_the_soak_override_does_not_unlock_anything_else(cfg):
    g = gate(cfg, PAPER_SOAK_OVERRIDE="true", ENABLE_LIVE_TRADING="")
    assert not g.evaluate(**ALL_OK).allowed


def test_flatten_needs_its_own_phrase():
    assert not flatten_confirmed({})
    assert not flatten_confirmed({"FLATTEN_CONFIRMATION": "yes"})
    assert flatten_confirmed({"FLATTEN_CONFIRMATION": "CLOSE_ALL_POSITIONS"})


def test_no_credential_is_ever_written_into_a_config_file():
    """A grep, deliberately whole-file rather than scoped: scoping is where
    the silence hides."""
    import glob
    import re
    secretish = re.compile(r"(?i)(private_key|api_secret|secret_key)\s*[:=]\s*"
                           r"['\"]?[A-Za-z0-9_\-/+]{12,}")
    for path in glob.glob(os.path.join(os.path.dirname(__file__), "..",
                                       "config", "*.yaml")):
        body = open(path).read()
        assert not secretish.search(body), f"{path} looks like it holds a key"


def test_secrets_never_reach_the_logs():
    """Driven through the real FORMATTER, not through `scrub` alone.

    A unit test of the scrubber proves the scrubber works; it does not prove
    the handler calls it, and the handler is the thing between a careless log
    line and a leaked key. This asserts on the JSON a handler would actually
    emit."""
    import json
    import logging

    from downtrend_bot.logging_setup import JsonFormatter, scrub

    key = "0x" + "a" * 64
    rec = logging.LogRecord("downtrend_bot.t", logging.INFO, __file__, 1,
                            "submitting with key %s", (key,), None)
    rec.extra_fields = {"LIGHTER_API_PRIVATE_KEY": key,
                        "api_secret": "s3cr3tvaluegoeshere0123456789abcdef",
                        "authorization": "Bearer " + "z" * 40,
                        "symbol": "BTC/USDT:USDT", "quantity": 1.5}
    out = JsonFormatter().format(rec)
    parsed = json.loads(out)

    assert parsed["symbol"] == "BTC/USDT:USDT" and parsed["quantity"] == 1.5
    for secret in ("a" * 64, "s3cr3tvaluegoeshere0123456789abcdef", "z" * 40):
        assert secret not in out, f"a secret survived the formatter: {secret[:12]}"
    assert "<redacted>" in out


def test_redaction_survives_a_secret_that_arrives_inside_a_message():
    """The costly case: nobody puts a key in `extra`. They interpolate it into
    a message string by accident. The long-token filter is what catches that,
    and it must run on the MESSAGE, not only on structured fields."""
    import logging

    from downtrend_bot.logging_setup import JsonFormatter

    key = "A" * 48
    rec = logging.LogRecord("downtrend_bot.t", logging.ERROR, __file__, 1,
                            "order rejected, payload signed with " + key,
                            None, None)
    out = JsonFormatter().format(rec)
    assert key not in out and "<redacted>" in out


def test_redaction_is_recursive_and_total():
    from downtrend_bot.logging_setup import scrub
    nested = {"outer": {"inner": [{"api_key": "abc123"},
                                  {"ok": "BTC/USDT:USDT"}]}}
    got = scrub(nested)
    assert got["outer"]["inner"][0]["api_key"] == "<redacted>"
    assert got["outer"]["inner"][1]["ok"] == "BTC/USDT:USDT"


def test_the_declared_dependencies_are_the_ones_actually_imported():
    """An unused dependency is an attack surface, a wheel to build and a
    version to pin, bought for nothing -- and a MISSING one is an ImportError
    on someone else's machine. Both directions, checked against the source."""
    import ast
    import glob
    import os
    import re

    root = os.path.join(os.path.dirname(__file__), "..")
    declared = set()
    body = open(os.path.join(root, "pyproject.toml")).read()
    m = re.search(r"^dependencies = \[(.*?)\]", body, re.S | re.M)
    assert m, "no dependencies list in pyproject.toml"
    for tok in re.findall(r'"([A-Za-z0-9_.\-]+)', m.group(1)):
        declared.add(tok.lower().replace("-", "_"))

    third_party = set()
    stdlib = set(getattr(__import__("sys"), "stdlib_module_names", ()))
    local = {"downtrend_bot", "conftest"}
    for path in glob.glob(os.path.join(root, "src", "downtrend_bot", "*.py")):
        tree = ast.parse(open(path).read())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                mods = [(node.module or "").split(".")[0]]
            for mod in mods:
                if mod and mod not in stdlib and mod not in local:
                    third_party.add(mod.lower())

    # ccxt is a DECLARED optional extra, imported lazily inside a guard.
    third_party.discard("ccxt")

    # A DISTRIBUTION name is not an IMPORT name -- `PyYAML` imports as `yaml`,
    # and a test that assumed they matched would fail on the one dependency
    # this package actually has. `packages_distributions()` inverts the real
    # install metadata rather than guessing.
    from importlib.metadata import packages_distributions
    dist_of = {mod: {d.lower().replace("-", "_") for d in dists}
               for mod, dists in packages_distributions().items()}

    def satisfied(mod: str) -> bool:
        return bool(dist_of.get(mod, {mod}) & declared) or mod in declared

    undeclared = {m for m in third_party if not satisfied(m)}
    assert not undeclared, f"imported and never declared: {undeclared}"

    imported_dists = set()
    for mod in third_party:
        imported_dists |= dist_of.get(mod, {mod})
    unused = declared - imported_dists
    assert not unused, f"declared and never imported: {unused}"
