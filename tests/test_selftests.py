"""Tier 0 — run every in-module `--selftest` block, and fail the build if one breaks.

WHY THIS FILE EXISTS
~38 fleet modules carry a hand-rolled `--selftest` (or bare-`__main__`) block —
the de-facto unit tests for this repo. Before 2026-07-18 NOTHING ran them: not
CI, not a pre-commit hook, nothing. So a regression inside a *covered* function
(e.g. experiment_judge's promotion math, fleet_tuning's clamps) still shipped
green, because the assertion that would have caught it was never executed.

This test turns those dormant assertions into a live regression net: each module
is invoked as `python -m <module> --selftest` in a subprocess and must exit 0.
Running as a module (not a path) makes venues/ package-relative imports resolve
and hands the gated blocks their flag; bare-`__main__` selftests ignore the
extra flag harmlessly.

ROT GUARD (`test_no_unregistered_selftest`): if someone adds a new `--selftest`
block and forgets to register it here, this suite fails and names the file — the
same "a rule nobody runs is not a control" logic the born-dark guard enforces
for imports.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 120

# ── Registry ────────────────────────────────────────────────────────────────
# Every module whose `--selftest` block is a de-facto unit test. Invoked as
# `python -m <dotted> --selftest`. Keep this list in sync with the codebase —
# the rot guard below fails the build if a new selftest module is missing.
SELFTEST_MODULES = [
    "bot_learn",
    "bot_pnl_store",
    "brain_stats",
    "cross_exchange_arb",
    "event_sentinel",
    "evidence_board",
    "experiment_judge",
    "fleet_bus",
    "fleet_clock",
    "fleet_immune",
    "fleet_proposals",
    "fleet_proprioception",
    "fleet_regen",
    "fleet_respiration",
    "fleet_risk",
    "fleet_tuning",
    "fleet_watchdog_svc",
    "funding_basis",
    "funding_carry_bot",
    "implementation_shortfall",
    "lighter_dislocation_bot",
    "lighter_family_bot",
    "lighter_funding_bot",
    "lighter_market_scout",
    "lighter_perp_sniper",
    "lighter_scout_tuner",
    "lighter_ticket_replay",
    "lighter_ticket_taker",
    "lighter_trend_bot",
    "market_context",
    "market_pulse",
    "paper_broker",
    "parliament_main",
    "regime_oracle",
    "strategy_incubator",
    "triangular_arb",
    "venues.safety",
    "venues.lighter_client",
]

# Heavier live-fixture harnesses that need the real signer SDK. Skipped when the
# import prereq is absent (lean CI job / local dev), run when it is present
# (full image). (module, flag, required_import).
LIVE_SELFTESTS = [
    ("lighter_ticket_taker", "--selftest-live", "lighter"),
]

# Structural guards. The CI-gating ones are green on main — their FULL scan is
# asserted here too. deploy-coverage is informational (its full scan reports a
# census, not a pass/fail), so it runs only its negative `--selftest` fixture.
# [2026-07-18] venue-purity's shipped-code scan was made green (compile_market_data
# declared as a dashboard display panel; the 2 retired bots declared) and wired
# into CI, so it moves up to ENFORCED. Its BACKTEST section stays advisory.
ENFORCED_AUDITS = [
    "scripts/audit_image_imports.py",   # born-dark guard (CI-gating)
    "scripts/audit_sdk_pin.py",         # real-money wheel pin (CI-gating)
    "scripts/audit_venue_purity.py",    # LIGHTER-first, shipped-code scan (CI-gating)
]
GUARD_ONLY_AUDITS = [
    "scripts/audit_deploy_coverage.py", # deploy-route census (informational)
]

# Files that carry a `--selftest` marker but are deliberately NOT in the CI
# runner, with the reason. The rot guard consults this so an intentional
# omission is DECLARED (the BORN_DARK_OK pattern), never silent.
SELFTEST_EXCLUDE = {
    # Research backtest: needs historical market data / network, not a unit test.
    "scripts/backtest_georgia_short_sleeve.py",
    # [2026-07-21] TSL reclaim study: --selftest IS offline-green, but the
    # module's import pulls the family bot's full strategy surface and its
    # full run needs the venue API — a research script, not an organ. Its
    # verdict (NO CHANGE at any stop width; bleed is entry-side) lives in
    # its header; re-run with --refresh, never re-argue from prose.
    "scripts/study_intraday_tsl_reclaim_lighter.py",
    # Their selfcheck() blocks run INSIDE `parliament_main --selftest` (which
    # IS registered above) — the marker hit here is the docstring saying so.
    "parliament/bus.py",
    "parliament/ecosystem_db.py",
}


def _run(args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
    )


def _tail(r, n=2500):
    return (r.stdout[-n:] + "\n" + r.stderr[-n:]).strip()


@pytest.mark.selftest
@pytest.mark.parametrize("mod", SELFTEST_MODULES)
def test_module_selftest(mod):
    r = _run(["-m", mod, "--selftest"])
    assert r.returncode == 0, f"`python -m {mod} --selftest` exited {r.returncode}:\n{_tail(r)}"


@pytest.mark.selftest
@pytest.mark.parametrize("mod,flag,needs", LIVE_SELFTESTS)
def test_module_selftest_live(mod, flag, needs):
    if importlib.util.find_spec(needs) is None:
        pytest.skip(f"{needs!r} not installed — live harness needs the real signer SDK")
    r = _run(["-m", mod, flag])
    assert r.returncode == 0, f"`python -m {mod} {flag}` exited {r.returncode}:\n{_tail(r)}"


@pytest.mark.selftest
@pytest.mark.parametrize("script", ENFORCED_AUDITS)
def test_enforced_audit_guard(script):
    ok = _run([script])
    assert ok.returncode == 0, f"{script} full scan failed:\n{_tail(ok)}"
    neg = _run([script, "--selftest"])
    assert neg.returncode == 0, f"{script} --selftest (negative fixture) failed:\n{_tail(neg)}"


@pytest.mark.selftest
@pytest.mark.parametrize("script", GUARD_ONLY_AUDITS)
def test_guard_negative_fixture(script):
    # Only the guard's own self-check — proves the detector still works. The full
    # scan is a repo-content policy check tracked outside this suite.
    neg = _run([script, "--selftest"])
    assert neg.returncode == 0, f"{script} --selftest (negative fixture) failed:\n{_tail(neg)}"


def _registered_paths():
    paths = set(SELFTEST_EXCLUDE) | set(ENFORCED_AUDITS) | set(GUARD_ONLY_AUDITS)
    for mod in SELFTEST_MODULES:
        paths.add(mod.replace(".", "/") + ".py")
    return paths


def test_no_unregistered_selftest():
    """Every file with a `--selftest`/`def _selftest` marker must be registered.

    Catches the failure mode where a new selftest is added but never wired into
    CI — it would pass locally when run by hand and silently never run again.
    """
    markers = ("--selftest", "def _selftest", "def selftest")
    found = set()
    for py in ROOT.rglob("*.py"):
        if "/tests/" in py.as_posix() or py.name == "conftest.py":
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(m in text for m in markers):
            found.add(py.relative_to(ROOT).as_posix())

    registered = _registered_paths()
    unregistered = sorted(found - registered)
    assert not unregistered, (
        "These files define a --selftest but are not registered in "
        "tests/test_selftests.py (add to SELFTEST_MODULES, or to "
        f"SELFTEST_EXCLUDE with a reason):\n  " + "\n  ".join(unregistered)
    )
