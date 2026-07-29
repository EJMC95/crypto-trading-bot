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
    # [2026-07-28] breakout-quality study: --selftest is offline-green &
    # stdlib-only (verified `python -m scripts.analyze_breakout_quality
    # --selftest` on a bare interpreter); registering it here fixes the
    # test_no_unregistered_selftest red on main since 24-Jul.
    "scripts.analyze_breakout_quality",
    # [2026-07-28 (dx)] judge operator-release tool: --selftest is offline/pure
    # (transition-mirror + refusal guards, no DB). Registered the same day it
    # shipped — (dw) landed during the Actions billing lockout, so the very
    # guard that enforces this registration never ran on that push; the first
    # local CI-stand-in run caught it.
    "scripts.xp_judge_release",
    # [2026-07-28 (dy)] daily evidence review as code (fail-soft sections; sole
    # write bot_state['evidence-review']): authored by the Daily-evidence-review
    # scheduled session, found stranded UNTRACKED in the shared tree (tripping
    # this very guard locally, 1/200 red). Landed + registered here on the
    # review session's own flag — --selftest is offline-green, no DB.
    "scripts.evidence_review",
    # [2026-07-29 (ev)] the Farmer TAKE_PROFIT study — --selftest is offline
    # (universe-slice + grid/slip invariants + harness identity; no network,
    # no cache read). It pins the constants the recorded tp-0.06 verdict is
    # quoted against, so a silent grid edit cannot orphan the header.
    "scripts.study_farmer_take_profit",
    # [2026-07-29 (ex)] prospect-admission test — --selftest is offline (veto
    # reduction, signature dedupe, ordering, empty-state); the full run needs
    # the tape + register from the DB.
    "scripts.study_prospect_admission",
    # [2026-07-29 (fv)] alpha-vs-regime — the instrument item 18 has needed
    # since 21-Jul. --selftest is fully offline (synthetic markets) and must
    # discriminate BOTH directions: a drift strategy with a huge raw t and
    # ~zero excess, genuine skill, NEGATIVE alpha, and the thin-cross-section
    # refusal. A detector that can only ever say "no alpha" is not a detector,
    # so the drift/skill pair is the load-bearing assertion. The full run needs
    # a pickled scout tape (--tape) plus the dashboard ledger.
    "scripts.study_alpha_vs_regime",
    # [2026-07-29 (fk)] go-live readiness grader — --selftest is offline
    # (synthetic books: a clean pass, the low-win-rate/positive-expectancy
    # "carry shape", the high-win-rate money-loser, window/DD bars). It pins
    # that win rate is NOT a bar and that expectancy IS one.
    "scripts.golive_readiness",
    # [2026-07-30 (gq)] exit attribution — the first instrument in this repo
    # that reads the exit REASON off the ledger and asks which one makes the
    # money. --selftest is fully offline (synthetic ledgers) and pins the
    # things a refactor would quietly break: the carry shape and its hold
    # ratio, BOTH exit-reason dialects (`reason` and the tag suffix, with
    # `reason` winning), single-exit detection, that an UNTAGGED close survives
    # as "?" instead of vanishing, that unparseable or negative holds give None
    # rather than a zero (a zero reads as "fires instantly", the exact
    # conclusion the hold column exists to test), and that labelling a book
    # RETIRED changes no number.
    "scripts.study_exit_attribution",
    "bot_learn",
    "bot_pnl_store",
    "brain_replay",
    "brain_stats",
    "cross_exchange_arb",
    "event_sentinel",
    "evidence_board",
    "experiment_judge",
    "fleet_agronomy",
    "fleet_radar",
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
    # [2026-07-29 (el)] Finding 7: the two RUNNING shadow bots that had zero
    # tests and no selftest at all (Index Rider, Counterweight) get the
    # fleet's minimum selftest parity, registered the day they shipped.
    "lighter_funding_spread_bot",
    "lighter_index_bot",
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
# asserted here too.
# [2026-07-18] venue-purity's shipped-code scan was made green (compile_market_data
# declared as a dashboard display panel; the 2 retired bots declared) and wired
# into CI, so it moves up to ENFORCED. Its BACKTEST section stays advisory.
# [2026-07-23] deploy-coverage moves to ENFORCED. The old comment here — "it's
# informational, a census not a pass/fail" — was FACTUALLY WRONG: audit_deploy_
# coverage.main() returns 1 on an orphan and 0 otherwise (it IS pass/fail), and
# that mis-classification is exactly why the fleet_radar orphan (cl/cm/cn) shipped
# unblocked — the guard existed but ran nowhere. It is now green on main (radar
# added to the deploy paths) and CI-gating (changelog-check.yml), so its full
# scan is asserted here too. The live bots are declared in DEPLOY_COVERAGE_OK.
ENFORCED_AUDITS = [
    "scripts/audit_image_imports.py",     # born-dark guard (CI-gating)
    "scripts/audit_sdk_pin.py",           # real-money wheel pin (CI-gating)
    "scripts/audit_venue_purity.py",      # LIGHTER-first, shipped-code scan (CI-gating)
    "scripts/audit_deploy_coverage.py",   # every shipped file has a deploy path (CI-gating)
    "scripts/audit_changelog_letters.py",  # sync-channel citations resolve (CI-gating)
    # [2026-07-30] the cage must fit the value: every lever carries a
    # machine-readable default, that default is INSIDE its own bounds, and it
    # MATCHES the `os.environ.get` default its consumer actually runs. The
    # drift arm is the point — `scout.ticket_top_n` was moved 6 -> 12 in code
    # on 2026-07-30 and its registry note still said 6 the same afternoon, so
    # every organ reasoning about that lever's headroom read the wrong number.
    "scripts/audit_lever_bounds.py",
]
GUARD_ONLY_AUDITS = [
    # [2026-07-22] lever-authority census: asks whether a lever's [lo, hi] can
    # change BEHAVIOUR, not merely whether a value is inside it. Its bare run
    # exits 1 on 5 open findings (live.funding.enter_apr's hi sits below the
    # venue's modal funding; FUNDING_HARD_STOP / FUNDING_EXIT_APR carry the
    # live book's loss with no lever at all), so it is INFORMATIONAL until
    # those are triaged — same footing as the deploy census. Only its
    # `--selftest` negative fixture runs here.
    "scripts/audit_lever_authority.py",
    # [2026-07-29 (em)] coverage-floor ratchet: its FULL run needs the
    # coverage.json the tests.yml `coverage-floors` job produces (the suite
    # under subprocess-aware coverage), so only the detector's negative
    # fixture runs in the lean suite; the full check gates in its own job.
    "scripts/audit_coverage_floors.py",
]

# Files that carry a `--selftest` marker but are deliberately NOT in the CI
# runner, with the reason. The rot guard consults this so an intentional
# omission is DECLARED (the BORN_DARK_OK pattern), never silent.
SELFTEST_EXCLUDE = {
    # [2026-07-29 (fd)] secret-leak guard: BOTH its scan and its negative
    # fixture shell out to the `gitleaks` binary and FAIL CLOSED when it is
    # absent ("a missing scanner is not a pass" — correct). NOTE it was briefly
    # registered in SELFTEST_MODULES instead (the (fb) session's own fix for
    # the same rot-guard red) — that MAKES THE SUITE FAIL anywhere gitleaks is
    # absent, and `tests.yml` never installs it, so the pytest job would have
    # gone red on the next push. Measured, then moved here. The lean pytest
    # environment has no gitleaks; its own changelog-check job installs a
    # pinned, checksum-verified copy first and runs both modes there, so the
    # guard IS enforced — just not from here. Registered because it shipped
    # unregistered in f6d7a2a and turned this rot-guard red on main; declaring
    # it is the pattern (a silent omission is what the guard exists to catch).
    "scripts/audit_secret_leak.py",
    # Research backtest: needs historical market data / network, not a unit test.
    "scripts/backtest_georgia_short_sleeve.py",
    # [2026-07-21] TSL reclaim study: --selftest IS offline-green, but the
    # module's import pulls the family bot's full strategy surface and its
    # full run needs the venue API — a research script, not an organ. Its
    # verdict (NO CHANGE at any stop width; bleed is entry-side) lives in
    # its header; re-run with --refresh, never re-argue from prose.
    "scripts/study_intraday_tsl_reclaim_lighter.py",
    # [2026-07-21] carry flip-grace study: --selftest is offline-green (run it
    # directly); the full run needs the venue API + dashboard ledger. Verdict
    # in its header: NO exit change (magnitude bar is a no-op on the real
    # episodes, 8h grace is deferral), the queued follow-up is the ENTRY gate.
    "scripts/study_carry_flip_grace_lighter.py",
    # [2026-07-21] carry entry-gate sweep (the flip study's queued follow-up):
    # --selftest offline-green; full run pages the venue's funding API.
    # Verdict in its header: shipped 5%-TRUE gate = -$93/150d structural
    # bleed; 0.20 TRUE passes both halves — ENACTED as CARRY_ENTER_APR
    # default 1.60. Re-run with --refresh, never re-argue from prose.
    "scripts/backtest_carry_gate_lighter.py",
    # [2026-07-21] regime-gate counterfactual on the same harness (imports
    # the study above — same exclusion reasons). Verdict in header: both
    # gate variants cut the bleed on both halves but neither flips the book
    # positive; the wired brain regime_gate is the mechanism and its
    # measured benefit is an UPPER bound (the actuator also needs a
    # standing ACTIONABLE finding).
    "scripts/study_intraday_regime_gate.py",
    # [2026-07-21] DIV_GAP tighten study: offline --selftest green but the
    # module imports the taker+replay surface and its full run wants the
    # bus tape — research script. Header verdict: NO SUPPORTED CHANGE at
    # 75/87.5 (replay fails H2; ledger method inert at n=3); the entry
    # filter is EXHAUSTED as a diagnosis for divergence's bleed — the big
    # losers were the highest-conviction tickets (all |gap| >= 101).
    "scripts/study_div_gap_tighten.py",
    # [2026-07-22] breakout LEVEL-vs-EVENT entry study: --selftest offline-green
    # (fixtures only); full run pages the venue's 4h candles for 25 coins.
    # Header verdict: DO NOT ENACT — crossing entry fails both halves in both
    # books, the 14-Jul "boot burst" re-attributes to a market-wide fresh
    # breakout candle, and the stale entries a crossing rule removes are
    # net-POSITIVE. Re-run with --refresh, never re-argue from prose.
    "scripts/study_breakout_boot_entry.py",
    # [2026-07-22] taker realized-SL study: --selftest offline-green; full run
    # reads the bus tape + paper ledger. Header verdict: NO CHANGE — the
    # replay already prices SL at the breaching mark; the filed −3.55% mixed
    # bars-in-force (−4% lever windows). The real follow-up is LEVER FLAP
    # (expiry snapping a tighter bar onto in-flight positions), filed for the
    # tuner/TTL semantics review.
    "scripts/study_taker_sl_realized.py",
    # [2026-07-22] MomoBreakout BTC-tide parity study: --selftest offline-green;
    # full run pages the venue's 4h candles. Header verdict: ENACT (operator-
    # approved) — the port was missing MomoBreakoutV1's 14-Jul BTC-tide gate;
    # restoring it cuts the falling-half bleed ~46-71% in both books. Strict
    # both-halves not met (H1 gives back ~14-17%, stays positive); shipped on
    # the directional-restrict reading with operator sign-off + kill switch.
    "scripts/study_breakout_tide_gate.py",
    # [2026-07-22] entry-side budget allocation study: --selftest offline-green;
    # full run reuses the family caches. Header verdict: EVIDENCE ONLY for the
    # review (budget is 2.4x over-subscribed; the three parkers hold 14/20
    # slots for 0 realized wins). No cut is not-worse-both-halves except
    # breakout 6->5; re-sizing the budget is the operator's review call.
    "scripts/study_budget_allocation.py",
    # [2026-07-22] family time-stop study: --selftest offline-green; full run
    # pages the venue's 4h+1d candles. Header verdict: DO NOT ENACT — max
    # slot-day relief anywhere on the grid is -6.1% (bar >=20%) because
    # level-condition entries refill a freed slot within ~2 bars; 97-100% of
    # time-stopped positions exit via the shipped rules anyway. The real
    # budget lever is entry-side (max_open / allocation) — review item.
    "scripts/study_family_time_stop.py",
    # [2026-07-22] swing-daily dormancy study: --selftest offline-green; full
    # run pages the venue's 1d candles. Header verdict: GENUINE DORMANCY, not
    # a data-depth bug — the 240-bar fetch reproduces the full-depth signal
    # stream 25/25; the would-be entries lost money, the gate's silence
    # protected the book.
    "scripts/study_swing_daily_dormancy.py",
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
        rel = py.as_posix()
        if "/tests/" in rel or py.name == "conftest.py":
            continue
        # [2026-07-21] .claude/worktrees/* are per-session git worktrees —
        # full repo COPIES whose files are duplicates by construction; a
        # stale one made this test fail on every file it already registers.
        if "/.claude/" in rel:
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
