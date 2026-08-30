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
    # [2026-08-16 (pc)] the CI-coverage guard: was the code that reached a
    # container ever graded? SELFTEST_MODULES and deliberately NOT
    # ENFORCED_AUDITS, per this file's own rule directly below — its verdict
    # reads GitHub run history, which changes with no code change at all, so
    # a scan here would turn local `pytest` red whenever CI happened to be
    # mid-flight. The negative fixtures are offline and pure (`assess` takes
    # run rows and commit paths as arguments); the SCAN runs in
    # fleet-weekly-assessment.yml beside audit_code_currency, which is where
    # "which commit is running, and was it graded" is the actual subject.
    "scripts.audit_ci_coverage", "scripts.edge_aware_safety",
    # [2026-08-17 (pp)] the weekly scoreboard's exposure flag. SELFTEST_MODULES
    # for the same reason as audit_ci_coverage above: its verdict reads the LIVE
    # bus (`fleet_risk.long_positions`), which moves with every fill and no code
    # change, so a scan here would redden local `pytest` on the fleet's trading
    # activity. `exposure_flag()` itself is pure — it takes the parsed payload
    # and a clock — so the 20-case negative fixture is offline and deterministic,
    # and it covers the branch that matters most: a STALE payload is UNKNOWN even
    # when its numbers read clean, and even when they read over budget (I1).
    "scripts.weekly_exposure_flag",
    # [2026-08-16 (nx)] the shared-worktree commit wrapper: --selftest is
    # offline and pure (classify + snapshot round-trip, no git, no DB).
    # Registered in the same commit that adds the tool, per this guard's own
    # rule — a --selftest nobody runs is the shape it exists to prevent.
    # [2026-08-27 (ut)] the shared TAPE CACHE. SELFTEST_MODULES and not
    # ENFORCED_AUDITS: its --selftest is offline and pure (an injected fetcher,
    # a temp dir, a frozen clock), while a scan would hit the venue. Registered
    # in the same commit that adds the tool, per this guard's own rule.
    "scripts.tape_cache",
    "scripts.session_commit",
    # [2026-08-19 (qg)] the MUTATION HARNESS. Same shape as session_commit
    # above — a hand-rolled step that every session re-implements and
    # re-breaks, made safe once. Registered in the commit that adds it.
    # --selftest is offline and pure: no git, no pytest, no DB (it exercises
    # apply/compile/no-op/absent-target on a tempfile). The three bugs it
    # closes are all MEASURED, five times across sessions: out-of-tree
    # bytecode (`sys.pycache_prefix` is outside the repo, so a same-SIZE
    # mutation survives `git checkout` and a restored file keeps running the
    # mutant), scoring on text instead of the exit code, and a mutation that
    # silently never applied — the last two both misreported a whole round on
    # 18-Aug, and the first one voided a round on 19-Aug in the session that
    # wrote this.
    "scripts.mutate",
    # [2026-08-25 (tk)] the LIVE P&L + SYNC AUDIT. --selftest is offline and
    # pure (a fixture payload in the dashboard's own shape; no network, no
    # git, no DB — the network path is main()'s, not selftest()'s), so it
    # belongs here and not in SELFTEST_EXCLUDE. Registered in the round that
    # added the tool, caught by this very guard on the PR's first CI run —
    # the "selftest nobody runs" shape, prevented by its own detector.
    "scripts.live_pnl_audit",
    # [2026-08-18 (qd)/I21] the WINNERS' DOCKET. SELFTEST_MODULES and
    # deliberately NOT ENFORCED_AUDITS, per this file's own rule: its verdict
    # reads the live ledger, which moves with every close and no code change.
    # The --selftest is offline and pure (exact t-tail vs known values, BH on
    # a fixture, the MIN_N luck floor, outcome-exit exclusion) — and
    # tests/autonomy/test_winners_docket.py carries the mutation-verified
    # structural pins (5 of 5 red).
    "scripts.winners_docket",
    # [2026-08-27 (vm)] THE LEDGER OF CLAIMS and its freshness audit. BOTH in
    # SELFTEST_MODULES and deliberately NOT ENFORCED_AUDITS, by the rule stated
    # at the head of ENFORCED_AUDITS: the freshness verdict reads the number an
    # ORGAN publishes, which moves with every close and no code change, so a
    # scan here would redden local `pytest` on the fleet's trading activity —
    # and its live arm exits 2 with no DATABASE_URL, which is a deliberate
    # INCONCLUSIVE, not a pass. Both `--selftest` blocks are offline and pure
    # (fixture payloads, an injected clock, a `file://` URL that cannot
    # resolve; no network, no DB, no git), and the structural pins live in
    # tests/autonomy/test_claims_ledger.py — including the one a fixture cannot
    # reach: every claim's dotted owner path resolved against a payload built
    # by `golive_readiness`'s OWN publisher functions.
    "scripts.claims_ledger",
    "scripts.audit_claim_freshness",
    # [2026-08-20 I22] the BOOK SPEND census. SELFTEST_MODULES and deliberately
    # NOT ENFORCED_AUDITS, the same reason as winners_docket directly above: its
    # live arm reads the public /pnl.json, which moves with every publish and no
    # code change, and a network wobble must never be able to read as a pass.
    # The --selftest is offline and pure. The live scan runs in CI, in
    # changelog-check.yml's `book-spend` job, with the selftest ahead of it.
    "scripts.audit_book_spend",
    # [2026-08-20 (ru)] the docket class-split evidence. --selftest is offline
    # and pure (the split, the sleeve-tag round-trip, and the calibration gate's
    # fail-closed arms); the SCAN needs the public feeds, so only the fixture
    # runs here. Registered in the same commit that adds the script, per this
    # guard's own rule — a --selftest nobody runs is the shape it prevents.
    "scripts.study_docket_class_split_2026-08-17",
    # [2026-08-26] the stuck-vs-slow discriminator. INHERITED from main — the
    # script shipped in 27529e2 without a registry entry, so this guard was RED
    # on main itself and on every branch that rebased onto it. Registered here
    # rather than left for its author because a guard that cannot stay green is
    # one the next session learns to route around ((gl)), and the fix is one
    # line. SELFTEST_MODULES and deliberately not ENFORCED_AUDITS, for this
    # file's standing reason: the --selftest is offline and pure (verdicts over
    # real publisher rows, plus the stale/halted/fail-closed arms) while the
    # SCAN reads the live feed, which moves with every publish and no code
    # change.
    "scripts.audit_stuck_vs_slow",
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
    # [2026-07-30 (gt)] the exit SWEEP — the counterfactual half. --selftest is
    # fully offline (hand-built candle paths) and pins the properties that make
    # it trustworthy rather than merely runnable: the adverse-first intra-bar
    # rule, mirrored shorts, the position CAP actually skipping entries (both
    # directions), max-drawdown and peak-concurrency floors that REFUSE the
    # "delete the stop" artifact its own first real run produced, grid-edge
    # detection, and the CALIBRATION gate — no reproduction of the observed
    # result, no recommendation, fail-closed when no baseline is supplied.
    "scripts.audit_lever_measurability",
    # [2026-08-20 (sp)] SELFTEST_MODULES only, and the rule at the head of
    # ENFORCED_AUDITS is why: this guard's verdict depends on CHANGELOG.md,
    # which any concurrent session can change without touching code — the
    # `audit_recurrence` shape exactly. Its negative fixtures run here (five
    # attribution forms must FIRE, nine role references must stay quiet); the
    # scan runs in changelog-check.yml, where "is my entry right" is the
    # actual subject.
    "scripts.audit_operator_name",
    "scripts.ceiling",
    "fleet_manifest",
    "scripts.session_state",
    "scripts.study_exit_sweep",
    "scripts.study_stop_reclaim",
    "scripts.study_entry_exit_stoploss_fleet",
    "scripts.study_trail_sweep",
    "scripts.study_depth_vs_volume",
    # [2026-07-30 (hf)] LEDGER INTEGRITY — is a book's ledger ONE book's record?
    # --selftest is fully offline and pins the discrimination that makes the
    # detector usable rather than alarming: sequential holds on one symbol are
    # clean, a close-and-reopen inside a single loop (sub-60s, identical stamps)
    # must NOT fire, a hold that opens HOURS inside another on the same symbol
    # must, a DECLARED book reports the same overlaps without the accusation,
    # rows missing a stamp are skipped rather than guessed, and the sniper's
    # '... UTC' dialect still parses.
    "scripts.audit_ledger_integrity",
    # [2026-08-14 (mo)] THE ROW REGISTRY. Its --selftest pins the registry's
    # own invariants (every declared-live row maps to an entry file; no row is
    # both mapped and declared a non-bot) and — the load-bearing half — that
    # `live_rows_from_feed` is FAIL-CLOSED: a dark, empty or venue-less feed
    # returns None ("cannot say"), never [] ("nothing is live"), because []
    # would let the roster guard pass vacuously on every network blip.
    "scripts.fleet_books",
    # [2026-07-31 (hy)] THE DOCTRINE GUARD. Its --selftest carries the negative
    # fixtures (missing block, undeclared invariant, broken enforcement ref,
    # renamed symbol, lazy UNENFORCED reason, duplicate id, backtick-less
    # claim) AND asserts CLAUDE.md's own invariants pass — so a doctrine whose
    # enforcement was deleted reddens here as well as in CI.
    "scripts.audit_doctrine_enforcement",
    # [2026-07-31 (hz)] THE SQUARE-ONE DETECTOR. Its --selftest pins the
    # threshold and window against being tuned into silence, the
    # longest-match extractor against substring double-counting, and that
    # the LIVE changelog is clean -- so an unclosed recurring subject
    # reddens here as well as in CI.
    "scripts.audit_recurrence",
    # [2026-08-01 (ib)] THE UNDEFINED-NAME GUARD. (hp) shipped
    # `store.claim_writer(BOT_ROW)` into funding_carry_bot.py with `BOT_ROW`
    # bound nowhere; Python resolves globals at runtime, so it imported,
    # compiled and passed --selftest, then died on NameError at the top of the
    # trading loop on every boot — a 25.6h crash-loop on both carry containers
    # while the row still read "online". Its --selftest pins BOTH directions
    # (fires on the real defect, silent on the fix) plus ten real idioms that
    # must not false-positive, because a detector that flags everything trains
    # the operator to ignore it.
    "scripts.audit_undefined_names",
    # [2026-08-01 (ii)] one owner for an era date. A legitimate table move
    # must not redden tests that are not about the date; its --selftest pins
    # that it fires on a duplicate, stays silent on the derived form AND on
    # documentation (a `# [2026-07-17 BASIS FIX]` marker records history and
    # must never move), and that exemptions are file-local and reasoned.
    "scripts.audit_era_date_literals",
    # [2026-08-05] deploy_live_verify — the live deploy as ONE VERIFIED ACT
    # (print the operator command / watch the gh run / verify by stamp
    # readback), replacing the measured 8-dispatches-5-cancelled-in-4-minutes
    # dance of 3-Aug. --selftest is fully offline (injected fetch/sleep, feed-
    # shaped fixtures) and pins the properties that make the tool safe rather
    # than merely runnable: it structurally CANNOT dispatch (`gh workflow ...`
    # is AST-banned — live dispatch is operator-only), it re-implements none
    # of the stamp rule (second-copy AST pin; audit_code_currency is the
    # owner), a stale row never confirms (I1), a build_n mismatch reports the
    # (fd) FILE-SET reading, and every poll is bounded (P1–P3). Six mutation
    # classes verified red the day it shipped.
    "scripts.deploy_live_verify",
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
    "fleet_allocation",
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
    # [2026-08-13 (ma)] 🙏 Avo Maria LIVE — registered the day it was born
    # (the live Taker slot swap). Offline stub-venue harness: identity guard,
    # balance-derived sizing, cap seniority, stop/ROI parity with the family
    # instance, kill-switch flatten, seed guard, standby, published vetoes.
    "lighter_avo_live_bot",
    # [2026-08-05] 🎸 Barnesy — registered the day it was born; its selftest
    # is offline (gates, exits, tags, freeze, publisher-built payload).
    "lighter_band_barnes_bot",
    # [2026-08-13 (ls)] 🏦 Rich Dad — registered the day it was born; offline
    # (payback gate, entry gates, census, exits, income statement, payload).
    "lighter_book_kiyosaki_bot",
    # [2026-08-13 (mb)-(me)] the BOOKS cohort's second wave — each registered
    # the day it was born; all offline (gates, exits, tags, census, payload,
    # plus each book's signature pin: Douglas's consistency signature,
    # Grimes's I20 roster exclusion + replay gate, Schwager's no-pyramid +
    # monotone trail, Hull's band tiling + measured grace).
    "lighter_book_douglas_bot",
    "lighter_book_grimes_bot",
    "lighter_book_hull_bot",
    "lighter_book_schwager_bot",
    # [2026-08-29] 🏭 book-bezos — thin wrapper over lighter_book_douglas_bot;
    # its selftest delegates to core._selftest() so it is tested via douglas.
    "lighter_book_bezos_bot",
    # [2026-08-18] 🪁 band-kelly — registered the day it was born; offline
    # (mirror inversion pinned as a property, ghost import identity, both
    # exit ladders, empty-screen universe contract, publish/state builders).
    "lighter_band_kelly_bot",
    # [2026-08-19 (re)/(ri)] 🧭 nav-cook — the [45,60)bps dislocation band that
    # tiles BELOW band-kelly's floor. Its selftest pins the half-open ceiling
    # (the I20 disjointness), the stop-before-data exit order, the fail-OPEN
    # class screen, and that the shipped horizon is one the study measured.
    "lighter_nav_cook_bot",
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
    # [2026-08-16] the isolated-margin liquidation MODEL (the paper-arm
    # counterpart to (no)'s live-account margin_state). Registered here rather
    # than excluded because its selftest is pure and offline — it parses a
    # literal orderBookDetails fixture — and because a liquidation engine that
    # silently stops firing is the exact vacuous-guard shape I3 warns about.
    # It lives under scripts/ ON PURPOSE: venues/ is inside
    # bot_pnl_store._BUILD_SHARED, and putting it there re-stamped 22 images
    # (build_n 17 -> 18) for a module none of them import — the (fd) trap.
    "scripts.lighter_margin_model",
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
# WHICH LIST DOES A NEW AUDIT GO IN? [2026-08-16 (pb)] The question that keeps
# being answered by feel, so it is written here once:
#
#   Does the audit's verdict depend on state that changes WITHOUT a code change?
#
#   NO  -> ENFORCED_AUDITS. Its scan runs here, so `pytest` catches the defect
#          before a push instead of after one.
#   YES -> SELFTEST_MODULES only (the negative fixture), and let the SCAN run in
#          changelog-check.yml, where "is my entry right" is the actual subject.
#
# The measured example of YES is `audit_recurrence`: it fails when one subject
# collects more than MAX_ENTRIES=5 changelog entries in 7 days, and on the day
# this rule was written `tide-rider-lighter` sat at exactly 5 — one entry from
# ANY concurrent session would have turned every local `pytest` red for a
# developer who had touched nothing related. That is not a guard doing its job
# in the wrong place; it is a guard whose subject is the shared file itself.
# `audit_changelog_letters` is the deliberate exception, and it earns it: at
# push time your own letter IS part of the change under test.
ENFORCED_AUDITS = [
    # [2026-08-16] boot-stagger reachability. A push is a deploy and a deploy
    # restarts every organ's boot timer, so an organ whose time-to-first-run
    # exceeds the deploy cadence never starts — and NOTHING else reports that,
    # because an organ that never ran is not sick: no exception, no stale-key
    # alarm from the organ itself, every liveness contract green. Registered
    # here rather than left to pytest alone for the (ox) reason one group
    # below: the SCAN and the negative fixture answer different questions, and
    # a guard whose scan runs nowhere is the (gk) shape. Both exit 0 today; the
    # scan asserts nothing when no deploy cadence is reachable, so it is safe
    # offline and in CI.
    "scripts/audit_boot_stagger.py",      # organs can reach their first run
    # [2026-08-27 (ut)] THE BUS CONTRACT. `coin-quality` published the fleet's
    # own measured execution cost for seven weeks as `{ts, coins}` — no
    # `updated`, no `ttl_sec` — so `fleet_bus.is_fresh` judged it stale FOREVER
    # and no consumer could ever be written. Registered in the same commit that
    # adds the guard, per this file's own rule: static, offline, no DB (CI has
    # no DATABASE_URL, and a guard that read live rows would pass vacuously on
    # an empty result). Exits 0 today against a one-entry RATCHET.
    "scripts/audit_bus_contract.py",      # cross-read payloads carry updated+ttl_sec
    "scripts/audit_image_imports.py",     # born-dark guard (CI-gating)
    "scripts/audit_sdk_pin.py",           # real-money wheel pin (CI-gating)
    "scripts/audit_venue_purity.py",      # LIGHTER-first, shipped-code scan (CI-gating)
    "scripts/audit_deploy_coverage.py",   # every shipped file has a deploy path (CI-gating)
    "scripts/audit_changelog_letters.py",  # sync-channel citations resolve (CI-gating)
    # [2026-08-16 (ox)] THE SCAN, not just the --selftest. This guard was in
    # SELFTEST_MODULES only, so `pytest` ran its negative fixture and never
    # pointed it at the repo: the scan lived solely in changelog-check.yml, and
    # a NameError introduced locally was invisible until after a push. Nine of
    # the thirteen audits in that workflow are ALSO here for exactly this
    # reason; of the four that were not, three are changelog/doctrine scans
    # that belong there — this one is a CODE guard and was in the wrong group.
    # ~1.6s over 195 modules. (ow) reverted this line once, on the wrong
    # reading that it duplicated an existing registration; it does not.
    "scripts/audit_undefined_names.py",
    # [2026-08-16 (pb)] Same finding as the line above, two more instances,
    # placed by the rule stated at the head of this list rather than by feel.
    # `audit_era_date_literals` is pure AST over python (1.1s) — a hardcoded
    # era date is a CODE defect and was catchable only after a push.
    # `audit_doctrine_enforcement` (0.03s) reads CLAUDE.md but fails on a CODE
    # change: an invariant whose named guard no longer resolves, i.e. a guard
    # deleted out from under its doctrine.
    "scripts/audit_era_date_literals.py",
    "scripts/audit_doctrine_enforcement.py",
    # [2026-07-30] the cage must fit the value: every lever carries a
    # machine-readable default, that default is INSIDE its own bounds, and it
    # MATCHES the `os.environ.get` default its consumer actually runs. The
    # drift arm is the point — `scout.ticket_top_n` was moved 6 -> 12 in code
    # on 2026-07-30 and its registry note still said 6 the same afternoon, so
    # every organ reasoning about that lever's headroom read the wrong number.
    "scripts/audit_lever_bounds.py",
    "scripts/audit_organ_silence.py",
    # [2026-08-03 (iw)] CODE CURRENCY — resolves each container's `extra.build`
    # to an actual COMMIT and classifies the gap. Its selftest is the whole
    # value: the classifier must keep telling BEHIND-OWN (missing merged
    # behaviour) apart from DEFERRED (marker-gated, working as designed) and
    # FILE-SET (a different `build_n`, i.e. a different COPY set, not stale
    # code). Its own first three runs got each of those wrong in turn, so the
    # negative fixtures are not ceremony.
    "scripts/audit_code_currency.py",
    # [2026-08-14 (mo)] LIVE ROSTER — is the DECLARED live pair still the pair
    # that holds real money? The roster rotted twice on one line (17-Jul and
    # 13-Aug slot swaps) and the second time CLAUDE.md's own audit-scope rule
    # named a retired row for 22 days, sending every audit past the book that
    # actually holds the money. Its selftest carries the discrimination that
    # makes it usable rather than alarming: both directions of disagreement are
    # named, an UNREADABLE feed makes NO claim (fail-closed — a network blip is
    # not a clean roster), a retired row inside the live-scope rule fires while
    # the SAME row as distant history does not, and a removed anchor is
    # reported rather than silently skipping the check.
    "scripts/audit_live_roster.py",
    # [2026-08-27 (tw)] A RECORD MUST NOT FABRICATE WHAT IT DOES NOT KNOW.
    # Its --selftest pins the `is_non_economic` contract this audit imports
    # rather than re-expresses — that georgia's real -$0.84 LIT loss and her
    # five REAL forced-flatten closes are never classified as events, that a
    # funding row booking accrual is a TRADE, and that anything unparseable
    # fails OPEN — plus that the RATCHET keys are the four it reports on.
    # Registered because the guard caught its own omission on first CI: the
    # file was UNTRACKED during the local run, so the enumerator could not
    # see it (the (th) `live_pnl_audit` shape, exactly).
    "scripts/audit_ledger_records.py",
    # [2026-08-19 (qz)] MID-LINE conflict markers. changelog-check.yml has
    # carried an anchored `git grep -nE '^(<<<<<<<|>>>>>>>|=======$)'` since the
    # committed-stash-marker incident, and on 19-Aug the SAME class landed again
    # past it: a rebase end-marker appended to the END of a CHANGELOG prose line
    # with no newline in front, so `^` never matched and the guard reported
    # clean through a commit AND a push. Found by an adversarial byte-compare
    # against the other merge parent, not by any check. This scan is the
    # un-anchored twin; it is registered HERE rather than only in the workflow
    # by the rule at the head of this list — the corruption it catches is
    # content, and a content defect must be catchable before a push.
    "scripts/audit_conflict_markers.py",
    # [2026-08-19 (rz)] Citation DRIFT — the blind spot `audit_changelog_letters`
    # declares in its own docstring: it checks that a letter RESOLVES, never
    # that it resolves to the entry the citation was written against. On 19-Aug
    # a renumber left seven citations of the ruin-gate entry pointing at another
    # session's unrelated one, across `lighter_funding_bot.py` and
    # `venues/safety.py` — the live Farmer and SafetyRails — through a commit, a
    # push and a green CI run. Registered here, not only in the workflow,
    # because it needs the suite job's `fetch-depth: 0`: it reads history via
    # git blame, and at depth 1 it would verify nothing while reporting clean.
    "scripts/audit_citation_drift.py",
]
GUARD_ONLY_AUDITS = [
    # [2026-08-20] 🎯 the SNIPER EXIT-SHAPE counterfactual. Registered HERE and
    # not in SELFTEST_EXCLUDE, deliberately, and the reason is a naming
    # accident worth stating because it applies to every dated study: a
    # `study_*_2026-08-20.py` filename contains HYPHENS, so it is not a legal
    # python module name and `python -m` — the only route SELFTEST_MODULES has
    # — cannot reach it. The three dated studies already in SELFTEST_EXCLUDE
    # were excluded for a DIFFERENT reason (their selftests need cached tape).
    # This one's `--selftest` is offline and pure — no network, no DB, no
    # cache: 15 groups of synthetic bars with known answers, including the two
    # that decide whether the instrument may speak at all (LAG-1 entry-bar
    # exclusion, and the calibration gate REFUSING). It is path-invoked here so
    # it actually runs, because a selftest nobody runs is the exact shape this
    # file exists to prevent. Only `--selftest` runs: the full study needs the
    # venue's 1m tape and the dashboard ledger, and its verdict (the harness
    # CANNOT calibrate against this book at 1m — see its header) is a finding
    # to re-run, never to re-argue from prose.
    "scripts/study_sniper_exit_shape_2026-08-20.py",
    # [2026-08-20 (ty)] The DEBUT-DIRECTION study behind the young-source
    # supply fix. Path-invoked for the same hyphenated-filename reason as the
    # study above; its `--selftest` is offline and pure (synthetic bars with
    # known answers), and it pins the two things that decide whether the study
    # may speak: that `venue_priced` is a CLASSIFICATION and not `class == 2`,
    # and that entries are LAG-1 at a bar open rather than clamped.
    "scripts/study_sniper_debut_direction_2026-08-20.py",
    # [2026-08-20 (ty)] The dark-scout fallback drift guard. Its LIVE run needs
    # the venue, so CI runs only `--selftest` — which pins the comparison logic
    # itself (drift in both directions, the override excluded from both,
    # inactive books ignored). The live check is a one-command operator action;
    # it FAILS rather than passing when it cannot reach the venue, so a
    # network-less run can never be quoted as "clean".
    "scripts/audit_noncrypto_fallback.py",
    # [2026-07-22] lever-authority census: asks whether a lever's [lo, hi] can
    # change BEHAVIOUR, not merely whether a value is inside it. Its bare run
    # exits 1 on 5 open findings (live.funding.enter_apr's hi sits below the
    # venue's modal funding; FUNDING_HARD_STOP / FUNDING_EXIT_APR carry the
    # live book's loss with no lever at all), so it is INFORMATIONAL until
    # those are triaged — same footing as the deploy census. Only its
    # `--selftest` negative fixture runs here.
    "scripts/audit_lever_authority.py",
    # [2026-07-29 (em)] coverage-floor ratchet: its FULL run needs the
    # coverage.json the tests.yml `suite` job produces (the suite under
    # subprocess-aware coverage; job renamed from `coverage-floors` in the
    # 5-Aug one-runner merge), so only the detector's negative fixture runs
    # in the lean suite; the full check gates in that job's last step.
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
    # [2026-08-22 (sw)] THE TWO 22-Aug STUDIES, excluded for the same
    # MECHANICAL reason as the (sb) entry directly below and enforced the same
    # way — their filenames carry a hyphenated date, so a
    # `"scripts.study_georgia_entry_rank_2026-08-22"` entry in SELFTEST_MODULES
    # is not an importable module name, collects ZERO tests and reports green.
    #
    # Both `--selftest`s are offline and pure (no network, no cached tape, no
    # DB), so neither is exempt from RUNNING — only from being imported by
    # dotted name. `tests/autonomy/test_2026_08_22_studies.py` loads both by
    # PATH, runs each `_selftest`, and adds the two structural checks that
    # matter: the Farmer study must keep REFUSING an unknown volume (a data gap
    # becoming a free pass is what would drift it back to the rank-universe it
    # exists to correct), and the georgia study must keep preferring a stamped
    # `entry_rank` over its own reconstruction (or the I23 fix it motivated is
    # inert). If that file is deleted, nothing covers either study and these
    # two lines are a lie.
    #
    # Each carries a decision that was ACTED ON: the first is why 💸 the
    # Farmer's gate was NOT moved (on the honest population the shipped 0.05 is
    # the best of seven; on the rank universe 0.40 looks like +$14.95), and the
    # second is why 🔮 georgia's throttle went 2 -> 3.
    "scripts/study_farmer_gate_minvol_2026-08-22.py",
    "scripts/study_georgia_entry_rank_2026-08-22.py",
    # [2026-08-20 (sb)] 🧭 nav-cook's FOUNDING harness. Excluded from
    # SELFTEST_MODULES for a MECHANICAL reason, not a discretionary one: the
    # filename carries a hyphenated date, so `"scripts.study_dislocation_band_
    # 2026-08-19"` is not an importable module name — an entry there collects
    # ZERO tests and reports green, which is precisely what it did on the first
    # attempt ((po): a check that inspects nothing reports clean). It IS
    # enforced, by path, in tests/autonomy/test_dislocation_band_study.py —
    # which runs the same `_selftest` plus four structural tests. This
    # exemption is narrowed to the ONE rule it must dodge; if that file is
    # deleted, nothing covers the harness and this line is a lie.
    "scripts/study_dislocation_band_2026-08-19.py",
    # Research backtest: needs historical market data / network, not a unit test.
    "scripts/backtest_georgia_short_sleeve.py",
    # [2026-08-16 (om)] 📐 Grimes's GATE-FIX study. `--selftest` is
    # offline-green but needs the cached 4h/1d tape, so it is excluded like
    # every other research script here. VERDICT IN ITS HEADER: grading a
    # FIXED coin set is the only candidate that reaches 100% verdict
    # stability while keeping the shipped gate's detection sensitivity;
    # sub-sampling, a 240d window and a t>=1.0 bar each need 2x the edge to
    # fire. Re-run it, do not re-argue it from prose.
    "scripts/study_grimes_gate_2026-08-16.py",
    # [2026-08-16] ⚡ High Voltage's decision-point study. `--selftest` IS
    # offline-green (run it directly); the full run needs the venue's live
    # margin tiers AND the cached 208d tape. VERDICT IN ITS HEADER: the
    # risk-normalised sizing design is REFUTED — t 0.50 -> -0.82 on identical
    # entries, because equal-risk weighting upweights the tight-stop trades
    # where this edge loses. Re-run it, do not re-argue it from prose.
    "scripts/study_leverage_sizing_2026-08-16.py",
    # [2026-07-21] TSL reclaim study: --selftest IS offline-green, but the
    # module's import pulls the family bot's full strategy surface and its
    # full run needs the venue API — a research script, not an organ. Its
    # verdict (NO CHANGE at any stop width; bleed is entry-side) lives in
    # its header; re-run with --refresh, never re-argue from prose.
    "scripts/study_intraday_tsl_reclaim_lighter.py",
    # [2026-07-21] carry flip-grace study: --selftest is offline-green (run it
    # directly); the full run needs the venue API + dashboard ledger.
    # [2026-07-30 (he)] Verdict UPDATED and the 21-Jul SAMPLE retracted: the
    # selector pooled the retired Hyperliquid arm (15 flips), the ledger fetch
    # was truncated to the endpoint's 500-row default, and 11 episodes predate
    # the (hc) accrual era. Era-clean it is 44 episodes, and on those the 8h
    # grace PASSES the both-halves bar it was rejected on — but the run is
    # UNCALIBRATED (V0-sim -$35.22 vs a -$15.13 ledger) so every recommendation
    # is withheld. THIS FILE's replay still may not recommend.
    # [2026-08-18 (pr), corrected in place per I12: FLIP_GRACE_H HAS since
    # moved, 1h -> 6h — not "from prose" but on the (mf) books-cohort
    # measurement (the cell's own gate/coins, 250d), the same harness Rich
    # Dad consumed at (mf). The study's own selftest now pins the 6.0 value.]
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
