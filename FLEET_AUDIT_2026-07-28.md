# FULL-FLEET AUDIT — 2026-07-28 (evening pass, post-review)

*Operator ask: "Audit the complete fleet set up; all integrations and bug
fixes. Optimise each bot… arm them with all the latest advancements… Make
sure all organs are running, teaching, learning and implementing… fixes to
all bugs found… stronger focus on the positives." Conducted the same evening
as FLEET_REVIEW_2026-07-28.md, as its complement: the review judged the
evidence; this audit swept the machinery. Method: 8 parallel read-only
audit agents (live-money surface, organs/bus, promotion pipeline, brain,
deploy/CI, dashboard/store, Parliament, live runtime state), consequential
findings adversarially verified by independent agents before fixes. All
times UTC.*

## What shipped (PR #100, branch `claude/fleet-audit-optimize-d86ysl`)

Four CHANGELOG letters — **(dy)** growth/promotion pipeline armed (growth
promoter wired + guarded, D7 slope lever end-to-end, xp-queue heartbeat,
explore slice gradeable), **(dz)** live-money hardening (deposit
double-count → phantom halt; unchecked `:live` restore → durable wipe;
same-loop conviction cap under-count; W/L truth), **(ea)** learning loops
closed + CI un-broken (brain speaks Lighter, venue A/B resurrected,
Parliament consumes the brain's regime gate, ci-notify/weekly-assessment/
marker-grep fixes, ledger build-stamp made re-publish-proof), **(eb)** the
Parliament unstarved (candles follow holdings, honest tuner denominators,
Howard's fleet ingest closes its loop), **(ec)** every organ readable off-
Railway + release-tool state pass-through. Details live in CHANGELOG.md and
the PR body; every fix selftested, guards green, full suite green.

## Runtime verification (from the live endpoints, 14:25–14:31Z)

- Watchdog 0 problems / 0 warnings, 23/23 rows fresh; all organ keys
  fresh within their own TTLs; proprioception 18 graded / 3 helping /
  0 hurting; impl-shortfall verdict `live-ahead`, live slip 0.38bps.
- **§3e residual PASSES**: the first post-(ds) live Farmer close stamps
  the growth receipts AND `extra.build` matching the arm's bot_pnl build —
  the review's ledger-stamp + receipt pipeline is live end-to-end.
- Scout-tuner sweep enacted AND consumed (shadow taker at tp 0.06 /
  sl −0.04 / hold 72h vs live env defaults — correct lane separation).

## OPERATOR DECISION MENU (real-money / authority items — routed, not taken)

- **O1 — Live Ticket Taker runs a 4-day-old build** (905813c, 24-Jul;
  build-hash verified). Both Farmer arms were re-dispatched today; the
  taker was skipped by both live dispatches. After PR #100 merges:
  `gh workflow run 305025607 -f services="trail-blazer-live,tide-rider-lighter-live"`
  then marker-grep BOTH containers. This also delivers the taker's (dz)
  halted-day sl_block fix and the Farmer's (dz) capital/restore guards to
  real money.
- **O2 — the judge idles on the D3a release cooldown until 30-Jul
  09:20Z.** Deploying this PR's freqtrade-bots (auto on merge) before then
  puts the growth promoter in the container in time to measure the
  explore/conviction pair during the window. Note honestly: when `tp-0.06`
  auto-starts after the cooldown, the shadow twin still runs the operator's
  growth envs — the same joint-config read D3 flagged for 0.075. The
  entry-time receipts now make the mix auditable; whether to read it
  eyes-open or strip the envs for the candidate's window is the operator's
  call.
- **O3 — the units-bug lever bounds** (`live/xp.funding.enter_apr`
  INERT-PINNED, decisive modal value outside the bound) and the
  EXIT_APR / HARD_STOP unlevered-knob findings remain exactly as the
  23-Jul triage routed them: re-bounding a live entry gate is
  operator-only. Nothing new this pass; restated so the backlog stays lit.
- **O4 — venue-purity backtest backlog** (22 undeclared, 5 cited by a live
  bot): unchanged — re-run on Lighter's tape or declare in
  `BACKTEST_VENUE_OK`; operator's call per CLAUDE.md.
- **O5 — fleet_agronomy stays benched** (its own docstring: wiring is a
  review decision). Its inert-lever detector would have caught the
  `taker.sl_cooldown_h` dark lever this audit fixed by hand — an argument
  for wiring it at the next review.
- **O6 — growth faster-bar floors vs measured cadence**: GROWTH_MIN_CLOSES
  15 per 2.5d vs the shadow arm's measured ~9 — the ~2–3d bar may sit at
  "floors" until explore lifts cadence. The floors ARE the promotion bar on
  a real-money path, so re-deriving them is not Claude's to do; watch
  whether explore's first opens change the arithmetic.

## Known-open, watched (no action needed yet)

- **Explore still 0 opens ~5h after the f7cad49 fix deployed** (fix
  confirmed running by build hash). Re-check at ~24h; if still zero the
  §3d design question (explore samples only below the deep-scan cut)
  becomes primary.
- **Parliament asyncio loop runs Postgres/ntfy synchronously** — one DB
  hang freezes all six books + Howard at once. Tolerable at today's
  latencies; an async-refactor (`run_in_executor`, the pattern data.py
  already uses) for a calmer session.
- **fleet_risk enforced pileup cohort** includes books documented as
  advisory-only (Parliament ×6, dislocation, equities-regime) — shadow-lane
  restrict gate, no live money; either re-scope the enforced cohort to the
  budget cohort or ratify the wider one at a review. Left for the review
  because narrowing an ENFORCED gate is expand-direction.
- **Dashboard header cohorts** ("Crypto (paper)" / "Scanner" / "Stocks"
  spans) sum cohorts that emptied when the fleet went fully venue-suffixed
  — permanent zeros. Display-only; needs a visual pass, deferred.
- **Brain dip-tighten proposal clamps to a no-op** (registry lo == env
  default) — the tighten notch doesn't exist in-registry; widening the
  bound or excluding dip from TAKER_TIGHTEN is a small review call.

*Next weekly review (2026-08-04) additions to the standing list: O1–O6
above; explore's first opens; the first shadow-Farmer close's receipt keys;
gillard's tuner once candle coverage accrues (replay_coverage is now a
published number on `parliament-tuning`).*
