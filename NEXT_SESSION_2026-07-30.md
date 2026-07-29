# Next Session — prepared 2026-07-29 evening (AEST)

> **[2026-07-30 session — outcome stamps]** §1 research tail: ALL THREE
> done same-day — explore options 2/3 measured (option 2 rejected by
> occupancy; §30-Jul of the diagnosis doc), the 455d vol run CLOSED (KEEP
> stands; bar ungradeable at depth, decomposed in the filter doc), the
> per-asset gate study shipped as an evidence-backed HOLD
> (`REGIME_GATE_PER_ASSET_2026-07-30.md` — wiring stays review-gated per
> 28-Jul; SPY/QQQ graduate ~mid-Aug). §2 seam 3 DONE: `entry_admission()` +
> `entry_stamp()` extracted pure, battery block #12, 4 mutations killed;
> the full stub-venue tick driver remains the calmer-week cut. §3 review
> prep: three read-and-decide items appended to the triage doc's agenda
> (items 4–6). §5 health: clean at session start (watchdog zero problems,
> both Farmer arms online on `89c2c56b2da5`).

Handoff from the 29-Jul campaign (PRs #105–#113, all merged). State at
sign-off: suite **299 passed / 0 skipped**, 19 ratchet floors armed, both
Farmer arms **hash-verified converged on `89c2c56b2da5`** (live money runs
the (ef)/(en) hardening). Nothing is broken, nothing is waiting on a human
overnight.

## Priority list

### 1. The research tail (the session's main effort — needs full fuel)
- **Explore A/B design decision, backtest-first.** Explore has structurally
  never fired (the tail is empty at any floor); three routed options in
  `EXPLORE_ZERO_DIAGNOSIS_2026-07-29.md` §3d — the lean one is an
  explore-specific prefilter through the SAME Stage-B/C vetoes. Build the
  numbers for all three so the decision lands with evidence, not prose.
- **The 438d vol-filter run** (`study_funding_vol_filter.py`, full depth).
  Filter is KEEP but magnitude "not canon" until this runs
  (`FUNDING_VOL_FILTER_2026-07-24.md` + its correction block).
- **Per-asset regime gate** — the 21-Jul D5 prerequisite for any non-crypto
  widening. Build order is DECLARED: regime_oracle per-asset coverage → the
  family gate consumes it → only then the universe (SPY/QQQ/WTI books).
  Never BTC's EMA for SPY again.

### 2. Finding 4, seam 3 (weekly cadence — one only)
Next up per `TEST_COVERAGE_ANALYSIS_2026-07-29.md`: the **Farmer's entry
tick** (scan → gate → open, offline with a stub venue), then the Taker's
SDK-free tick, then the flatten orchestration loop (six captured deps —
wants a calm day). The (eq) flatten decision-layer seam rides the next
farmer dispatch; no urgency, behavior-identical.

### 3. 04-Aug review prep (5 days out)
Agenda additions are written in `LEVER_AUTHORITY_TRIAGE_2026-07-29.md`:
- **A1**: widen `live.funding.enter_apr` hi 0.075 → 0.12 (+xp twin) — the
  venue's modal funding (10.5%) sits OUTSIDE the current bound. Operator
  yes/no; moves no money by itself.
- **A2**: declare `EXIT_APR`/`HARD_STOP` in `LEVER_AUTHORITY_OK` (the
  flap-fix "env-only by design" reasoning) + queue the decay-exit backtest
  (decay = 67% of Farmer closes, 36% of gross loss).
- **Ratify** the 29-Jul testing doctrine: floors only ratchet up (lowering =
  operator + CHANGELOG), the weekly seam cadence, and assertion-depth over
  line-% (the bot_learn blind-selftest lesson).

### 4. Engineering queue (safe, no review needed)
- Decision-time quantity receipts for the UNMEASURED levers
  (`conviction_hi`, `explore_k`, `slope_gate`, live + xp) so the authority
  census can measure instead of shrugging (triage doc §B).
- Opportunistic "touch it, test it": monitoring organs (~50%), `render()`
  internals, deeper bot_learn slices. No dedicated pushes — the ratchet
  holds the ground.

### 5. Quick health glance (minutes, not a task)
Both Farmer rows on `89c2c56b2da5` and online at sign-off. Normal morning
review covers it; only dig if the watchdog or the rows say otherwise.

## Where the detail lives
`TEST_COVERAGE_ANALYSIS_2026-07-29.md` (stamps = exact frontier) ·
`LEVER_AUTHORITY_TRIAGE_2026-07-29.md` (decisions + agenda) ·
`EXPLORE_ZERO_DIAGNOSIS_2026-07-29.md` (the three options) ·
CHANGELOG `(ei)`–`(eq)` (the day, entry by entry).
