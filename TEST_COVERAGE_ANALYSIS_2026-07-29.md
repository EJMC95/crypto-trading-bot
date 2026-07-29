# Test Coverage Analysis — 2026-07-29

**Method.** The full suite (`python -m pytest`, exactly as `tests.yml` runs it)
executed under subprocess-aware coverage (`COVERAGE_PROCESS_START` + a
`sitecustomize` hook), so the 43 registered `--selftest` subprocesses and the
four enforced audit-guard full scans are all measured, not just the pytest
tiers. 54 coverage data files combined. Result: **200 passed, 1 skipped** (the
skip is `lighter_ticket_taker --selftest-live` — see Finding 1), and:

> **27,708 statements measured, 48% line coverage** (14,329 lines never
> executed by any test). ~2,200 lines of pytest across 10 test files + 43
> in-module selftests, all dating from 2026-07-18 or later.

Two honesty caveats on that 48%:

* Selftest line-% **overstates** assertion depth: importing a module marks all
  its module-level code covered. The taker's 38% includes ~1,000 lines of
  constants/plumbing its selftest never asserts on.
* It also **understates** one thing: `--selftest-live` needs the lighter SDK
  and skipped here (as in CI), so `venues/lighter_client.py`'s true coverage in
  the full image is somewhat higher than the 37% measured.

Per the standing operator rule (16-Jul), the live real-money surface was
checked explicitly in this pass: Funding Farmer (`lighter_funding_bot.py`),
Ticket Taker (`lighter_ticket_taker.py`), and `venues/`.

---

## What is already good (don't spend effort here)

The 18-Jul test build was aimed at incidents, and it shows. These are in good
shape and only need maintenance:

| Surface | Coverage | What pins it |
|---|---|---|
| `venues/safety.py` (kill switch, rails) | 94% | `test_safety_rails.py` — every stop-real-money branch incl. confirm fail-safes |
| `venues/equity_guard.py` (dislocation guard) | 95% | `test_equity_guard.py` — 714 lines, every verdict path of the 11-Jul incident class |
| `funding_basis.py` (the 8x fix) | 95% | own selftest + `test_funding_gate.py` locking H=1095 at the Farmer's call site |
| `brain_stats.py` (v3 statistics engine) | 98% | own selftest + `brain_replay` validation |
| `fleet_bus.py` (consumer clamps, L2 veto) | 90% | `test_fleet_bus.py` — [0.5, 1.5] clamp, stale→fail-open/closed contracts |
| `fleet_tuning.py` (lever registry/clamps) | 85% | own selftest |
| newer organs (proprioception 83%, radar 83%, scout 82%, incubator 88%, sniper 85%, judge 77%, immune 76%, tuner 75%, board 71%, agronomy 71%) | 71–88% | substantial selftests, several mutation-verified |
| retirement de-dup invariants | n/a | `test_retirement_consistency.py` — the $34.67 double-count class, as set algebra |

The house test style — every test names the incident it prevents — is worth
keeping as a hard convention for everything proposed below.

---

## Ranked gaps and proposals

Ranked by (real money at risk) × (size of gap) × (incident history).

### 1. The live-order harness (`--selftest-live`) runs NOWHERE automatically — top priority

**[2026-07-29 SHIPPED, same day (ej):** `tests.yml` now carries a
`selftest-live` job on every push/PR — it installs the wheel version straight
out of `requirements.txt` (the pin `audit_sdk_pin.py` enforces; never
hardcoded in the workflow), proves `import lighter` in its own loud step (so
the job can never quietly regress to skipping — the exact rot this finding is
about), then runs the harness via the `LIVE_SELFTESTS` registry so any future
live harness is picked up automatically. Verified end-to-end on a bare Linux
box before shipping: `lighter-sdk==1.1.2` installs clean and all 13 scenario
groups pass. The paragraphs below are kept as the record of WHY.]**

The Ticket Taker's offline selftest says it plainly at
`lighter_ticket_taker.py:2449`: the funding-accrual block "PINS THE ARITHMETIC,
it does NOT detect the bug… the only real detector is `--selftest-live` (tests
6 and 9), which drives that loop and caught the mutation immediately." That
harness:

* **skips in CI** (`tests.yml` installs no lighter-sdk; the suite records it as
  the 1 skip),
* appears in **no Dockerfile, no `*_loop.sh`, no workflow** (grepped), and
* is therefore run only when someone remembers to run it by hand in a
  container.

So the single strongest regression net over the live order/accrual loop — the
one that catches the 8x-class call-site bug the offline tests provably cannot —
has the same status the 38 selftests had before 18-Jul: it exists and nothing
runs it.

**Proposal:** add a `selftest-live` job to `tests.yml` that installs the
**pinned** signer wheel (the pin `audit_sdk_pin.py` already enforces on every
push) and runs `python -m lighter_ticket_taker --selftest-live`. The harness is
already offline-by-design (it needs the SDK's types, not the venue). If the
wheel can't install on the runner, the fallback is a `RUN` step in
`Dockerfile.tickettaker` / `Dockerfile.fundinglighter` so a live image that
fails its harness never builds — that also closes the "code was right and never
running" class at the deploy boundary. Either way, the skip should become a
loud, declared exception rather than the permanent quiet state.

### 2. `pnl_dashboard.py` — 9% on the fleet's money scoreboard (biggest file: 4,945 lines, 2,169 stmts, 1,971 missed)

**[2026-07-29 FIRST SLICE SHIPPED (ek):** `tests/financial/test_dashboard_money.py`
— 16 tests, handler driven without a socket, fetchers without a DB (a fake
psycopg2 for `fetch_rows`). Pins: the read-time retirement filter at its choke
point (the retired Tide-Rider live row is dropped while the Ticket Taker row
passes — the $34.67 class; plus the ex-Kraken double-life, a bare base RETIRED
while its `-lshadow` variant passes), the `/pnl.json` live-fleet subtotal
(shadow twins never counted; None-money rows contribute zero instead of
corrupting the sum), per-bot stale flags + the all-must-be-stale `feed_stale`
contract, the 500-on-DB-error path, `/trades.json` clamping/routing, the
fail-closed auth gate (no secret ⇒ no access, the committed-default incident),
and formatter None-safety. Measured 9% → 15% — a modest % on a 2,169-stmt file
by design: the slice targets the money choke points, not line count. The
aggregation inside `render()` (stage subtotals, health checks) remains
untested — the seam-extraction recipe applies when it is next touched.]**

This is the file Eamon reads money from, and the file with the double-count
incident history. What's tested today: the retirement constant sets and
`parliament_card`. What isn't: everything that computes a number.

**Proposal — in order of money-impact:**

* **Fleet-total aggregation**: retired-row exclusion at read time, live-row
  handling, and NULL-money summing. `_finite_or_none` (tested) now publishes
  `None` for NaN money — nothing tests that the dashboard's SUMs and win-rate
  math survive `None` rows without turning a card or the fleet total into
  garbage. This is the direct successor to the $34.67 test.
* **Read-only endpoint contracts**: `/pnl.json`, `/trades.json`
  (`?source=paper`), `/bus.json` — these are consumed by organs
  (`implementation_shortfall` reads trades; `fleet-watchdog.yml` probes
  pnl.json; `/bus.json` is the documented off-Railway accessor). A shape change
  is a cross-service break nothing would catch today. Pin each payload's schema
  with a fake-DB fixture.
* **Auth gate** (DASH_USER/DASH_PASS): one test that unauthenticated requests
  to protected routes are refused while the read-only endpoints stay open.
* The `test_parliament.py::test_dashboard_parliament_card_renders` pattern
  (monkeypatch `fetch_states`, assert on rendered card) already shows the
  house recipe — extend it to the money cards.

Some of this needs small extract-a-pure-function refactors. That's justified
here and only here: the dashboard is the one big file whose failures are
*silent wrong numbers* rather than crashes.

### 3. `venues/lighter_client.py` — 37% on the code that signs real orders

**[2026-07-29 SHIPPED (ek):** `tests/real_money/test_lighter_client_parsing.py`
— 20 tests on a bare client, venue-shaped fixtures, no SDK/network. Pins:
`_positions_from` (sign→signed size, flat rows dropped, `1000BONK`→`kBONK` —
the kNOT round-trip class, junk-upnl tolerance), `_equity_fields`
(total→collateral fallback; unreadable equity raises `VenueError`, never a
silent 0.0 into the loss rail), `funding_map` (lighter rate vs `_bench` rows,
None-rate coercion, mark/vol enrichment), `_rest_book` (the UNSORTED-snapshot
fix: best bid highest/best ask lowest; TTL cache + `force=`), `_our_fills`
(ownership is checked on EVERY tier — "the id narrows, it never authorises" —
tx-hash VWAP over partials, client-id blend exclusion, ms→s window fallback),
`_resolve`/`supports` (inactive ≠ tradable), candles non-200, interval math.
The sort and ownership guards are mutation-verified. Measured 37% → 65% on
the full suite as CI now runs it (the (ej) live-harness job contributes; the
pytest tiers alone stand at 44%). Still open on this file: `_run`/governor
error paths, ws `_BookCache`, `last_fill_detail`'s two-tape reason
strings.]**

`test_lighter_client_orders.py` covers the order path well (sizing, ±2% guard,
side pick, reduce-only flatten). The missing 315 statements are the **response
parsing and error paths**: `positions()`, account/equity reads, `orderbook()`,
funding reads, fill detail, retry/backoff, and the `_run_signer` error
branches. Mis-parsed venue responses are exactly the input class that fed the
11-Jul dislocation flatten — the equity guard defends against a *wrong number*,
but nothing tests that the client produces *right numbers* from real venue
payloads.

**Proposal:** recorded-fixture tests — capture real Lighter REST/ws payloads
(one healthy, one degraded/partial each) as JSON fixtures and assert the parsed
contract (`positions` dict shape, equity float, orderbook levels, funding
sign/period). Add `VenueError`-path tests for truncated/empty payloads. No SDK
needed — this is pure parsing, same `__new__`-bypass pattern the order tests
already use.

### 4. The two live bots' main-loop orchestration (Farmer 47%, Taker 38%)

The Farmer's `_selftest_*` battery (9 blocks — notional, fill-read, flap,
quarantine, vol-filter, conviction, explore, heal, lever-consume) and the
gate/lever pytest tier are genuinely good. What neither covers is **`main()`'s
glue**: scan → gate → open → fill-verify → publish; the exit ladder
(flip/TP/max-hold) as executed; the daily-loss flatten end-to-end
(`daily_loss_hit` → `confirm_daily_loss` → equity-guard interplay → flatten);
boot rehydration. The (ef) `_heal_merge` extraction — pull the inline logic
into a pure function, then fixture-test the three semantics that were wrong —
is the proven recipe, and it exists because the 29-Jul audit found three real
defects *in a path with no test seam*.

**Proposal:** continue the extraction pattern one seam per week rather than a
big-bang harness: (a) Farmer — one offline "single tick" driver with a stub
venue: a coin passes the gate → order placed → fill read → meta stamped →
publish payload correct; (b) Farmer — the flatten path: breach → confirm →
close all → halt record written; (c) Taker — an SDK-free offline tick (the
`--selftest-live` fixtures minus the signer) so at least the decision layer of
the loop runs in lean CI even after Finding 1 is fixed. Target: every line
that can place or close a real order is reachable from some test.
**[2026-07-29 FIRST SEAM SHIPPED (en):** the Farmer's EXIT LADDER —
`exit_decision()` extracted pure from the inline block at main():1773-1796
(every real-money close ran through it with no test seam), (ef) recipe.
`_selftest_exit_decision` (battery block #10) pins: the sign convention
(+adverse = against us, short hurt by UP / long by DOWN), the precedence
stop > tp > flip > decay > max_hold (a flipped-and-decayed rate books FLIP —
the flip is the information), apr=None disabling flip AND decay (price/time
exits only on an unreadable funding read), at-the-bar triggers vs decay's
strict <, zero-entry no-fabrication, and the default wiring to the env-only
HARD_STOP/EXIT_APR. Precedence and sign mutations each turn exactly their
named assertion red. Behavior identical; reaches the live container on the
next deliberate `[deploy-live-farmer]` dispatch. Remaining Finding-4 seams:
the Farmer's entry tick + flatten path, the Taker's SDK-free tick.]**

### 5. `fleet_risk.py` — 37%; the enforcement authority's core function is untested

**[2026-07-29 FIRST SLICE SHIPPED (el):** `tests/autonomy/test_fleet_risk_light.py`
— `light_for` pinned at the documented thresholds (yellow exactly at 70% of
budget, red AT budget = the veto boundary, so the light can never show green
while strategies are being refused), and `governed_clip_scale`'s
advisory-releases-the-clip contract (published 1.0 / raw kept; ANY non-enforce
mode fails open to full clip — the 15-Jul false-down-scale class). Both
mutation-verified. `main()`'s 400-statement assembly remains — the seam
recipe applies when next touched.]**

`light_for()` — the function that actually computes GREEN/AMBER/RED — is in
the missed lines (300–304), and `main()` (321–721) is a 400-statement monolith
covering budget counting, exposure assembly, premium mirroring, and publishing.
The documented contract "**advisory mode releases BOTH actuators** (publishes
`clip_scale=1.0`, raw kept as `clip_scale_raw`)" — a deliberate 17-Jul scope
expansion recorded in CLAUDE.md — has no test at the publish side. The
freshness tier (`state_fresh`/`row_fresh`/`authoritative_row`) is solid;
`dd_governor`+exposure have selftest cover.

**Proposal:** extract light/budget computation out of `main()` (same seam
recipe as Finding 4), then: light precedence fixtures (mixed live/lshadow/paper
rows, fresh vs stale), long-budget counting at the veto boundary (19/20/21
longs), and the advisory-release contract asserted on the *published payload*.
This is the layer whose false RED pinned the fleet for hours (ghost-exposure
incident) — cheap tests, real authority.

### 6. Venue plumbing: factory 24%, governor 28%, shadow 22%, marks 15%, fills 64%

Small files, outsized blast radius, and two of them have shipped incidents:

* `venues/__init__.py` (24%): mode selection + bot-id suffixing + `order_usd`.
  Incident history on BOTH: the `hl_paper` default that "silently pointed the
  SHARED entry point, real-money services included, at Hyperliquid", and the
  global clip override that ran Snap Back at 3x its documented size (16-Jul
  audit fix, `own=True`). **Proposal:** a mode matrix test — for each `VENUE`
  value: resulting mode, suffix, `dry_run`, broker type, and that unset/junk
  falls back to `lighter_shadow` and *never* to a live client; plus
  `order_usd` own-clip vs global-env precedence.
  **[2026-07-29 SHIPPED, same day (ej):**
  `tests/real_money/test_venue_factory.py` — 17 tests, all constructors
  stubbed (no network/signer/DB): the full mode matrix incl. the never-live
  fail-safe default and the typo'd-VENUE refusal, suffixing, the signer/
  equity-guard wiring on live, the loud error-row on failed live auth,
  own-clip vs anchor precedence, the live clip lever (and shadow's
  non-consumption of it), and the 16-Jul slot-minting regression (a x0.5
  lever must not double `max_open`). The default-flip and slot-anchor guards
  are mutation-verified — each reverted fix turns exactly its test red.
  Factory coverage measured 24% → 88% (the residue: the hl_paper
  `live_flag` exchange arm and log-once plumbing).]**
* `venues/governor.py` (28%): `TxBudgetGovernor` paces live order
  transactions. Pure arithmetic, no tests. Cheap to pin (budget consumption,
  refill, refusal at zero).
* `venues/shadow.py` (22%): ShadowBroker fills are the P&L for every `-lshadow`
  book — i.e. the *evidence the promotion pipeline judges live money by*. A
  fill-model bug here corrupts the judge's paired bar silently. **Proposal:**
  open/mark/close round-trip vs `paper_broker` (96%) semantics, fee and
  funding-sign parity.
* `venues/fills.py` (64%): the untested branches are the degraded reads
  (missing detail, tx-hash fallback) — the measured-fills telemetry the 17-Jul
  "58 orders, 0 measured fills" incident was about.

### 7. Running shadow bots with zero (or near-zero) tests

Coverage found three **currently-trading** services whose modules have no
selftest at all or a token one:

| Module | Row | Coverage |
|---|---|---|
| `lighter_index_bot.py` | 📊 Index Rider (`equities-regime-lshadow`) | **0%** — no selftest exists |
| `lighter_funding_spread_bot.py` | ⚖️ Counterweight (`perps-funding-spread-lshadow`) | **0%** — no selftest exists |
| `lighter_trend_bot.py` | 🌊 Tide Rider shadow (`crypto-trend-daily-lshadow`) | 12% |

(`lighter_momentum_bot.py` at 0% is 🏆 Stock Leaders — retired 17-Jul, fine to
leave; same for `listing_sniper.py`, `hyperliquid_*`, and the legacy
`dashboard*.py` files.)

These books are $1k paper, so this ranks below the live surface — but their
curves feed the brain, the risk light, and ultimately go-live decisions.
**Proposal:** bring both zero-test bots to the fleet's minimum selftest parity
(accounting round-trip incl. funding sign, exit ladder incl. short side,
publish-schema fields, and the `lighter_live`-refusal guard the momentum bot
already models), and register them in `SELFTEST_MODULES`. The rot guard will
then hold the line.
**[2026-07-29 SHIPPED (el):** both bots now carry offline `--selftest` blocks,
registered in `SELFTEST_MODULES` the day they shipped. Index Rider: sma
warmup, regime flip, the band-HYSTERESIS hold (asserted to differ from plain
regime on the same bar — the whipsaw filter as one assertion), sleeve
dispatch, and the ledger-row shape (`long_<reason>` tag, price+funding sum,
zero-notional → None pct, publish guard never raises). Counterweight:
`fresh_mid` on an unsorted book (max-bid/min-ask, never [0]), one-sided book
and venue-down → None, and the ledger row's SHORT-side pct profiting down
(`short_<reason>` tag). CI runs them from the repo on every push; the bots'
own services pick the blocks up on their next deploy — inert until then, and
the selftest changes nothing at runtime either way.]**

### 8. `bot_pnl_store.py` — 28%: the substrate every contract rides on

`publish()` money sanitization and `split_reason` are pinned. Structurally
unexercised anywhere (no `DATABASE_URL` in any test): `set_bot_state` /
`get_bot_state` (the entire cross-bot bus), `save_state` / `load_state` (bot
crash rehydration), `publish_trades` / `fetch_trades` (the ledger the brain
and judge learn from — `fetch_trades` just had the (ee) `is_open` union fix,
which shipped with no test), and the build stamp beyond its selftest.

**Proposal:** extend the existing `_FakeConn` pattern to the state and trades
functions: round-trip a payload through `set_bot_state`→`get_bot_state`
asserting `updated`/`ttl_sec` stamping; pin the **never-raise** guarantee (a
raising conn must return False/None — an exception here lands inside a live
trading loop); assert `fetch_trades`' open/closed filtering including
NULL `is_open` rows (locking the (ee) fix).
**[2026-07-29 SHIPPED (el):** `tests/financial/test_bot_state_substrate.py`
— 13 tests at the `_get_conn` seam. (Naming correction: the bus functions are
`save_state`/`load_state`/`fetch_states` on the bot_state table — this
finding's `set/get_bot_state` names came from the conftest docstring and
don't exist.) Pinned: the never-raise + cached-conn-reset contract on a DB
failure, dead-DB returns (False/None/{}/0/[]) across all seven substrate
functions, `load_state_checked`'s three-state read (the perp-sniper
false-seed incident), `fetch_states` NULL-skip + empty-short-circuit,
`publish_trades` open-ts skip / epoch-ms→aware-UTC / trade_duration
precedence, the `fetch_trades` `is_open IS NOT TRUE` union doctrine
(mutation-verified against the `= FALSE` revert), and heartbeat's
SET-only-updated_at (never clobbers the money snapshot).]**

### 9. CI measures nothing about coverage — add the ratchet

**[2026-07-29 SHIPPED (em):** three pieces. (1) `tests.yml` gains a
`coverage-floors` job — the full suite under subprocess-aware coverage
(selftest subprocesses measured), SDK installed so the live harness
contributes, then `scripts/audit_coverage_floors.py` holds **17 floors** on
the real-money surface at measured-minus-~2pp (taker 90, farmer 45, safety
92, equity-guard 93, client 63, factory 86, …). Floors only ratchet UP;
lowering one is an operator decision with a CHANGELOG entry; a floored file
going MISSING from the measurement is itself a breach. Detector
selftest-verified (breach + hold + missing all seen) and registered in
`GUARD_ONLY_AUDITS`. (2) `tests/test_coverage_policy.py` — the born-dark
pattern applied to tests: every module calling `publish`/`publish_paper_trade`
must be in `SELFTEST_MODULES`, imported by `tests/`, or DECLARED in
`PUBLISH_TEST_OK` with a reason; only RETIRED bots may be declared, stale
declarations fail, and the roster is scanned, never hand-maintained — the
Finding-7 class is now structurally unreintroducible. (3) Measured at ship
time with the SDK present: the live harness alone carries the **Ticket Taker
to 92%** and the tx governor to 79% — numbers the pre-(ej) suite could never
see. Fleet total at ship: 54%.]**

`requirements-test.txt` installs `pytest-cov` and `coverage`; `tests.yml` never
invokes them. Nobody can see drift.

**Proposal:**

* Run the suite in CI the way this analysis did (the `COVERAGE_PROCESS_START`
  hook is ~6 lines) and upload the report as an artifact.
* Add **floors only on the real-money surface**, at today's values so they
  ratchet up, never block unrelated work: `venues/` aggregate, the two live
  bots, `bot_pnl_store`, `fleet_risk`. A global-% gate on a repo with this many
  retired modules would just be noise.
* Extend the born-dark pattern to tests: a policy test asserting every
  *non-retired* module that publishes to `bot_pnl` is either in
  `SELFTEST_MODULES` or covered by a `tests/` file, with a declared-exception
  set. Finding 7's two bots would fail it today — which is the point.

### 10. Lower priority, for completeness

* `bot_learn.py` 39% (958 stmts missed *of the pipeline*, while `brain_stats`
  is 98%): the ledger→bucket→floors/streaks/fast-path plumbing is validated
  mainly by `brain_replay` (69%) rather than unit tests. Consumers are
  shadow-only; medium priority. Synthetic-ledger fixtures for the EMER
  fast-path gate and the two-way expand bars would be the first picks.
* `parliament/data.py` 25%: ws/REST network code; fixture-test its parsers
  when convenient. The rest of the Parliament is well covered (74–86%).
* Display/report layer at 0%: `report_emailer.py` and `compile_market_data.py`
  ship in the dashboard image; one import-and-render smoke test each.
* `user_data/` freqtrade strategies: 0%, dormant post-Kraken (the family bot
  re-expresses them). Declare them as the exception in the Finding-9 policy
  test rather than testing them.
* `market_pulse.py` 47% / `event_sentinel.py` 48% / `fleet_respiration.py` 52%
  / `fleet_regen.py` 56% / `fleet_watchdog_svc.py` 51% / `market_context.py`
  42%: real gaps but advisory/monitoring surfaces; grow them opportunistically
  when touched (the watchdog just gained `evaluate()` fixtures in (eg) — that's
  the pattern).

---

## Suggested sequencing

1. **This week:** Finding 1 (wire `--selftest-live` into CI or the image
   build — hours, closes the biggest incident-class hole) + Finding 6's
   factory mode-matrix test (an afternoon). **[Both SHIPPED 2026-07-29 (ej)
   — see the stamps above.]**
2. **Next:** Finding 2 endpoint/aggregation tests and Finding 3 parsing
   fixtures — the two places silent wrong numbers reach money decisions.
   **[First slices SHIPPED 2026-07-29 (ek) — see the stamps above; render()'s
   internal aggregation and the client's fill-read reason strings remain.]**
3. **Then:** Findings 4–5 seam extractions (one per week, (ef)-style),
   Finding 7 selftest parity, Finding 8 substrate tests.
   **[Finding 5's pure-function slice, Finding 7, and Finding 8 SHIPPED
   2026-07-29 (el) — see the stamps above. Still open here: Finding 4's
   live-bot `main()` seams and `fleet_risk.main()`'s assembly.]**
4. **Standing:** Finding 9's CI ratchet, so none of the above regresses.
   **[SHIPPED 2026-07-29 (em) — the ratchet holds 17 floors on every push.
   Of the original nine findings, the only work left open is Finding 4's
   live-bot `main()` seam extractions (deliberately one per week) and the
   opportunistic Finding-10 items.]**

*Measured on branch `claude/test-coverage-analysis-yn0mfs` at e8076a5; suite
green (200 passed, 1 skipped) before and throughout.*
