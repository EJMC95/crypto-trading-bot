# Evidence & Bot-Learning Assessment — 2026-07-15

Snapshot taken ~04:50 UTC from the live dashboard feeds (`/bus.json`,
`/pnl.json`, `/trades.json`, `/trades.json?source=paper`) plus the code at
main `8c449cb` (== gate0 for every file checked: `lighter_family_bot.py`,
`lighter_ticket_taker.py`, `bot_learn.py`, `bot_pnl_store.py`).

## Verdict

The learning machinery itself is honest and well-guarded: 120 brain runs and
it has **never published a premature stake throttle** (all 15 of the last 24h
`brain-stake-mults` snapshots carry `mults: {}`, `mult_streaks` is empty —
the n≥15/30 floors and 3-run streak gate are doing exactly what the design
doc promised). The fail-safe contract (`updated`+`ttl_sec`, neutral on
stale) is respected by every consumer checked.

But the 14-Jul Lighter pivot broke the brain's flagship loop — the L4 stake
multipliers — **on both ends at once**, and most of what it currently labels
ACTIONABLE is about bots the fleet already retired:

1. **No live consumer**: the only code that applies `brain-stake-mults`
   (`custom_stake_amount` in the four Kraken freqtrade strategies) belongs
   to processes the operator stopped 14–15 Jul. The running re-expression
   (`lighter_family_bot.py`, gate0) sizes with its own vol-based
   `stake_mult()` and never calls `fleet_bus.stake_multiplier()`.
2. **No tag evidence coming in**: the family bot records closes as
   `reason="long_"+reason` — the strategy enter-tag sits in `meta["tag"]`
   at entry (lighter_family_bot.py:880) and is dropped at close
   (lighter_family_bot.py:653). Every family/spot shadow book therefore
   buckets as enter-tag `long` in the ledger, so per-(bot, tag) learning —
   the key the whole L4 layer is built on — is structurally impossible for
   the 7 books that ARE the current fleet. (The Ticket Taker got exactly
   this fix on 15-Jul: `<side>-<lens>_<exit>`; the family bot didn't.)
3. **10 of 16 ACTIONABLE hypotheses target retired bots** (8 × Trail
   Blazer/Bounce Catcher, 2 × crypto-trend-daily). None target the running
   Lighter fleet — partly young books, partly the tag blindness above.

Meanwhile the two learning loops that *are* wired end-to-end into the
running fleet are healthy: the fleet-risk layer (long-budget veto is
literally active at this snapshot: 23 longs ≥ budget 20, mode=enforce, and
both the taker and family bot honor it) and the new lens-forward loop
(brain grades scout tickets counterfactually → taker restrict-only veto),
which is empty only because scout `marks` began publishing at 04:27 today —
first grades expected within 1–2 brain runs.

## 1. What the brain is (as built, v2 + 14/15-Jul layers)

| Layer | Output key | Gate before anything is claimed | Consumer |
|---|---|---|---|
| Hypotheses (pair/session/stop/mood) | `learning-brain` state, lessons_latest.md | n≥8 pair / n≥20 session, must persist 3 consecutive runs to be ACTIONABLE | humans only |
| L4 stake multipliers | `brain-stake-mults` | tag negative at n≥30 (0.5×) / n≥15 (soft 0.75×), 3-run streak, reduce-only, era-filtered, untagged excluded | `fleet_bus.stake_multiplier()` — **only the stopped Kraken strategies** |
| Diagnosis (which lever loses) | `brain-diagnosis` | n≥10 negative bucket; ordered rules: exit_too_tight → venue_execution → fee_bleed → regime_timing → entry_quality | humans + dashboard (advisory by design) |
| Venue A/B | state `venue_ab` | paper row vs `-lshadow`/`-lighter` twin from bot_pnl | diagnosis rule 2 (twin_n≥5 guard) + lessons |
| Lens-forward (15-Jul) | `brain-lens-forward` | forward returns of EVERY scout ticket at 1h/4h/24h from scout `marks`; ≥3 mark snapshots needed | Ticket Taker veto (n4h≥75, avg<0, hit<0.5 — restrict-only, fail-open) |

Evidence inputs: bot_trades (125 closed) + paper_trades (701 closed) ledgers,
Kraken public 1h candles (post-exit drift, budgeted 120 fetches/run),
regime-oracle history, market-pulse history, bot_pnl rows (venue A/B),
lighter-market history with marks (lens-forward).

Guardrails verified in code AND in live state: era awareness (ERA_START),
`(untagged)` never gets a multiplier, `fleet_bus` double-clamps to
[0.5, 1.0], every consumer goes neutral on stale/missing payloads,
backtests inert without DATABASE_URL.

## 2. State of the evidence (live snapshot)

- Brain run count **120** (2-hourly since ~5-Jul), last run 04:29 UTC;
  `brain-stake-mults` + `brain-diagnosis` fresh (age ~21 min, TTL 26000s).
- Era filters have (correctly) zeroed most Kraken-era data: era_n=0 for
  crypto-intraday-15m, crypto-breakout-4h, freqtrade-mum, freqtrade-dad —
  those engines are stopped, their fixes never got to prove themselves.
- The running fleet's books are 1–2 days old. Largest current-era
  (bot, tag) buckets: `perps-funding-lighter-lshadow|short` n=25 (+$4.51),
  `freqtrade-georgia-lshadow|long` n=11 (+$0.71),
  `lighter-ticket-taker-lshadow|long-breakout` n=2 (+$4.15, both TP wins).
- **No (bot, tag) bucket anywhere qualifies for a multiplier** (nothing
  negative at n≥15 with wr<25%). Closest: `crypto-trend-daily|
  sma_fast_above_slow` n=12, wr 0%, −$3.88 — below the floor, and its bot
  is retired anyway. Zero multipliers published is the CORRECT output.
- Lens evidence: scout tickets flowing (this snapshot: 6 breakout / 6
  momentum / 6 divergence / 0 dip); taker has only 2 lens-tagged closes —
  which is exactly why the counterfactual lens-forward layer exists
  (~5,000 tickets/day vs ~6 fills). `marks` (99 books) first appeared in
  `lighter-market` history at **04:27 today**; the 04:29 brain run saw <3
  mark snapshots → `lens_forward={}` is freshness, not a bug. Expect the
  first 1h/4h grades from the ~06:30 run, 24h grades tomorrow.

## 3. What it has actually learned — quality review of the 16 ACTIONABLE

- **8 × retired perps bots** (perps-donchian-breakout = Trail Blazer,
  perps-rsi-meanrev = Bounce Catcher): HYPE 39-trade 92%-win earner, NEAR
  100%-win earner, UTC12-14 hot zone, etc. True patterns, dead addressees.
  Worse: **Trail Blazer's paper engine is still trading** — 16 paper_trades
  closes since 14-Jul, latest 00:59 today — despite the 11/12-Jul
  retirement (dashboard hides the row, fleet_risk excludes it, but the momo
  Railway service noted in pnl_dashboard.py:141 is still running and keeps
  feeding the brain).
- **6 × event-listing-sniper** (live, legacy): UTC00-02 dead zone (61
  trades, 0% win vs 10% overall), UTC03-05 hot (37 @ 19%), pair bleeders
  AMAT/BMNR/EWY/LITE (8–9 trades each, ≤11% win). Real and current — but
  purely advisory (the sniper reads none of it), and with a 9.8%-WR/+$192
  lottery-ticket book, session/pair blocks risk cutting the tail winners
  that pay for everything. Handle as human judgement, n is small per pair.
- **2 × crypto-trend-daily** (Kraken paper, stopped): the fee_bleed
  diagnosis is the brain's best work to date — n=12, 0% win, −$3.88,
  median loser 0.54% vs ~0.52% round-trip fees, reclaim=1.0 (every losing
  exit reclaimed entry within 24h). Translation: the signal was fine, Kraken
  spot fees ate it. The fleet's actual response — Tide Rider live on
  Lighter at ~bps-scale fees — is precisely the named lever. Post-hoc
  validation of the Lighter pivot, from the machine.
- The 92-run "tighten the 'flip' entry gates" artifact is confirmed dead
  (tag-semantics fix + diagnosis layer); funding-carry now shows untagged
  n=36, +$5.64 and generates no bogus entry-gate prose.
- **Venue A/B** (5 twins): directionally pro-Lighter everywhere — family
  shadows beat their frozen Kraken papers by +$5.5…+$9.3; funding-carry
  shadow +$13.36 (8W/5L) vs paper +$5.64. It answered its one question
  ("does the signal survive the venue?" — so far, yes) but the comparison
  now decays: the paper arms are frozen 13/14-Jul, gaps mix unrealized P&L
  and different inceptions (mum shadow: 0 closed trades, gap +$9.25). The
  twin_n≥5 guard keeps it out of diagnoses; treat the report section as
  historical from here.

## 4. Structural gaps (ranked)

1. **L4 loop has no live consumer.** Restore it where the fleet actually
   trades: `lighter_family_bot.py` entry sizing
   (`stake = STAKE_USD * b.s.stake_mult(tag, bars)`, line 871) should also
   multiply by `fleet_bus.stake_multiplier(b.bot_id, tag)` — guarded,
   reduce-only, fail-neutral, no entry/exit logic touched.
2. **Family closes drop the enter-tag**, so the brain can't build the
   per-tag buckets the multipliers key on. One-line fix mirroring the
   taker's 15-Jul pattern: `reason=f"long-{m.get('tag') or '?'}_{reason}"`
   in `record_close` (bot_pnl_store.py already parses `long-*_*`). Until
   this ships, every family-book mult/diagnosis is stuck at tag=`long`.
   Note the identity shift too: ledger rows are `-lshadow` names, so
   ERA_START/mult keys built for Kraken-era names never collide — but any
   future logic change to the family books needs `-lshadow` ERA_START
   entries, and the mult lookup key must be `b.bot_id` (the row name), per
   the CLAUDE.md rule that bot identity = dashboard ID.
3. **The brain studies the dead.** No liveness filter: retired bots'
   trades sit in the fetch windows (125≪2000, 701≪5000) so their
   hypotheses re-fire every run and will stay "ACTIONABLE" for months —
   today that's 10 of 16, and the streak-retire path
   (`run_no - last_run ≥ 3`) can never trigger while the rows remain in
   window. Cheapest fix: only generate hypotheses for bots with a close in
   the last N days (7?) or not in a shared RETIRED set (reuse
   pnl_dashboard.RETIRED_ROWS); keep scorecards for the rest.
4. **Trail Blazer's engine is still running** — operator action: stop the
   momo Railway service (the 12-Jul note in pnl_dashboard.py:141 is still
   true). Until then it burns API/compute and pollutes learning output.
5. Minor observability: `/bus.json` exposes `brain-stake-mults` /
   `brain-diagnosis` but not `brain-lens-forward` (pnl_dashboard.py:2762
   and :2776 SELECT lists) — the learning tab shows it, the taker reads the
   DB directly, but external tooling can't see the newest brain layer.
6. Cosmetic: run_all.sh:148 says the taker tags `long_<lens>_<exit>`; the
   code writes `<side>-<lens>_<exit>` (that hyphen is what makes the brain
   parse it). Comment drift only.

## 5. What deserves credit

- Floor discipline: 120 runs, zero premature throttles, zero overfit
  promotions — "0 multipliers published — correct" (FLEET_REVIEW 14-Jul)
  still holds at run 120 under real data.
- Diagnosis layer genuinely discriminates levers now (fee_bleed with
  drift/fee/regime evidence attached), replacing the old blanket
  "tighten the entry gates" reflex.
- Lens-forward closes the taker's sample-size problem the right way
  (grade all ~5k daily tickets counterfactually, veto restrict-only at
  n≥75) and it's already wired consumer-side, waiting only on marks depth.
- The risk loop is alive and biting: light red, 23/20 longs, enforce mode —
  and post-15-Jul-audit both running entry engines (family bot, taker)
  honor the veto with fail-open semantics. That's the first fully-closed
  perceive→decide→act loop in the fleet.
- Provenance hygiene (venue/shadow columns, era filters, untagged
  exclusion, TTL contracts) is consistently applied — rare in a system
  this young.

## Bottom line

Evidence quality: good and improving; volumes on the new fleet are simply
young (1–2 days). Learning quality: methodologically sound, currently
aimed at the wrong targets. The two wiring fixes (family tag-preserving
closes + a family-bot multiplier hook) plus a liveness filter would point
the whole apparatus at the fleet that actually trades — in time for the
new era's sample sizes to reach the floors it's been patiently enforcing.

## Addendum — shipped 15-Jul (same PR as this doc)

Gaps 1, 2, 3, 5 and the run_all.sh comment drift are FIXED in this PR:

- `lighter_family_bot.py` now composes closes as `long-<tag hyphenated>_
  <exit>` (`ledger_reason`, hyphens because `bot_pnl_store.split_reason`
  splits at the first underscore) and applies
  `fleet_bus.stake_multiplier(b.bot_id, ledger_tag(tag))` at entry —
  same function derives the ledger tag and the lookup key, so buckets and
  lookups cannot drift. `fleet_bus.py` added to Dockerfile.familyshadow.
  No-op at deploy (published table is empty); reduce-only + fail-neutral
  by contract. **Needs the main→gate0 cross-merge to reach the running
  family-lighter-shadow service.**
- `bot_learn.py` generates hypotheses/diagnoses/multipliers for LIVING
  bots only (not in `cleanup_legacy_bots.LEGACY_BOTS`, ≥1 ledger close in
  7 days); scorecards still print for everyone, flagged
  `[inactive/retired]`. Existing dead-bot ACTIONABLE entries decay to
  retired via the normal 3-run path. `_epoch` now parses the sniper's
  `'... UTC'` timestamps (liveness + drift joins).
- `bot_pnl_store.fetch_paper_trades`'s reason-parse extracted to the pure
  `split_reason()` — the one parser the taker's and family bot's composers
  round-trip against (unit-tested: 36 tag/exit combos + legacy edges).
- `/bus.json` now exposes `brain-lens-forward` (live + history), same as
  the other brain keys.

Verified: py_compile on all touched files; compose→parse round-trip;
multiplier fail-safe/clamp cases (no-DB, stale, floor 0.5, ceil 1.0,
wrong bot/tag → neutral); `compute_stake_mults` streak semantics (publish
at run 3, drop on recovery, streak reset); and a 3-run `bot_learn` smoke
against a fixture ledger — identical losing evidence in a live, a stale,
and a retired bot produced hypotheses ONLY for the live one.

Still open: #4 (operator stops Trail Blazer's momo Railway service) and
the venue-A/B re-base (paper arms frozen — future change, low urgency).
