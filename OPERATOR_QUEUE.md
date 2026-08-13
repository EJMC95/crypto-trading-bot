# OPERATOR QUEUE — every open decision, with options you can actually use

Created 4-Aug-2026 at the operator's ask (*"throw me some options I can
actually use — clean up the rest of the remaining items"*). ONE surface for
every act only the operator can take, each with lettered options, the
evidence, and the prepared command. **Maintenance rule: the daily review keeps
this current; an item leaves the day it is decided, with the decision recorded
in the changelog.** Nothing here is executed by an agent — that boundary is
the (hn) routing table and it does not move.

Recommended options are marked ★.

---

## 0 · PENDING DEPLOYS — ~~waiting on you~~ **BOTH EXECUTED AND VERIFIED**

*Verified 7-Aug 10:15 AEST by stamp readback, which is the rule this file
sets for itself — a green workflow run has never implied a container took it.
`audit_code_currency` reads **CURRENT, 0 behind** on all three previously
DEFERRED rows (`lighter-ticket-taker-lighter`, `perps-funding-lighter-lighter`,
`perps-funding-lighter-lshadow`), all matching HEAD `904e949bb`. The live
Taker now carries (kt)+(ku) — the venue-class screen — and (kq), the
realised-lens-veto rewrite that decides when it HALTS.*

*Added 6-Aug by one session; executed and stamp-verified the same day by a
parallel session running on the operator's "full permission to commit and
deploy all positive movements" — the two sessions crossed mid-flight, so this
section was born already-stale (corrected in place per I12). Evidence:
`audit_code_currency` reads **every stamped container CURRENT at main HEAD**;
0a landed via the 06:06Z + 06:22Z dispatches (live Taker carries (kt)+(ku),
stamp `d5d03751b3ef`→`3bacbbf6037d`), 0b via the 06:06Z + shadow-arm
dispatches (both Farmer arms on `4f998e4eec4d`, cage lo=1e5 live — the
judge's `min-vol-1e5` experiment is unblocked). Nothing here is waiting on
anyone; the section stays until the next daily review confirms and removes
it.*

### 0a ★ 🎫 Ticket Taker — ~~live arm is screening against a 41-name-stale list~~ DONE 6-Aug

**What it carries:** `(kt)` + `(ku)`.

**Why:** the live arm's only crypto screen (`bull_entry_ok` → `_is_crypto`) had
fallen 41 names behind the venue. Measured on the bus 6-Aug, **3 of the
scout's 16 tickets were non-crypto instruments it would have admitted** —
`DRAM`, `CXMT`, `CAP` — and **`CAP` was on the `divergence` lens**, the only
lens the live arm trades. The live arm is divergence-short only, runs
`bull: True`, and `("divergence","short")` is in `BULL_LENS_SIDES`, so every
live entry passes that screen. It is the only thing between the real-money
book and a short on a tokenised equity.

**Urgency — CORRECTED 6-Aug 18:40 AEST. The earlier text here said "not
currently armed". That was WRONG and the error was mine.** It was based on an
audit that used `fleet_bus.is_crypto` on the ledger's `pair` column — and that
function did not strip the `/USDC` quote, so it returned "crypto" for every
non-crypto row and the audit reported ZERO. Blind by construction; fixed in
`(lc)` (the fix cited `(kv)`, a letter the horizon work already held —
repointed and engraved there).

**Measured correctly, the live real-money book has already opened 19
non-crypto positions (−$1.97 all-time). Five are IN-ERA short-divergence —
DRAM, MINIMAX, SKHY — opened 1-Aug to 4-Aug.** In-era that population runs
**−0.263%/trade against +1.145% on the crypto trades the screen keeps**, and
it is **5 of 14 in-era trades: over a third of the sample the go-live gate is
grading** on the book nearest real money.

The dollar damage is two cents. The evidence damage is the reason to deploy:
the gate is grading a sample a third of which the book's own design excludes.

```bash
# ALREADY RUN 6-Aug 06:22Z — kept for the record, not as an instruction.
# Verified: the live Taker reads CURRENT at main HEAD (audit_code_currency).
# Re-running is harmless but redeploys identical code.
gh workflow run 305025607 -f services="tide-rider-lighter-live"
```

`(ku)` also means this is the LAST time this class needs a deploy: the scout
now stamps the venue's instrument class on every ticket, so a newly listed
equity is screened the moment the scout sees it.

### 0b · 💸 Funding Farmer — ~~lever cage is 17 commits stale~~ DONE 6-Aug

**What it carries:** `(ka)`'s `min_vol` cage widening, plus `(jx)`'s
`claim_writer` + MTM series on the real-money pair.

**Why:** `(ka)` moved `{xp,live}.funding.min_vol` cage `lo` 2e6 → 1e5 and filed
`min-vol-1e5` in the judge's queue. Both Farmer arms still carry `lo=2e6`, so
the judge would write 1e5, the container would clamp to 2e6, and it would
grade a thin-tier experiment **the book never ran** — against a value identical
to the `min-vol-2e6` candidate queued beside it.

**Urgency — low.** `(kp)` now makes that failure LOUD instead of silent (the
lever refuses to the operator default and `skewed_levers()` names it), and the
judge is on `slope-gate-off` at 16/30 shadow closes with `min-vol-2e6`
(unaffected) queued ahead. Realistically **2–4 weeks** out.

```bash
# ALREADY RUN 6-Aug (both arms) — kept for the record, not as an instruction.
# Verified: both Farmer arms CURRENT at main HEAD; cage lo=1e5 is live, so
# the judge's `min-vol-1e5` candidate will be graded on the value it writes.
gh workflow run 305025607 -f services="trail-blazer-live"
```

### 0c · 🎫 Ticket Taker — the (lj) realised-veto era fix ~~rides the audit PR~~ MERGED 13-Aug, verification pending

**What it carries:** `(lj)` — the realised lens veto scoped to the policy the
arm runs. On deploy the LIVE arm's veto FIRES on its own era record
(short-divergence n=31, mean −1.128%, t=−1.75; trailing 8d −2.456%, t=−3.68,
nine of ten closes `_sl`) and the book stops opening new entries until that
record clears — idle beats a measured −2.5%/trade.

**[13-Aug 12:35 AEST — EXECUTED under the operator's real-money grant
("full permission to commit push and adjust real money bots also"): PR #155
merged, squash `75ead10f`, `[deploy-live-taker]` in the title, Railway
Redeploy ran on the push.** Also ships (lk): carry + sniper class screens on
their shadow auto-deploy rules. **Verification OPEN until the stamps move**
— first readback ~6 min post-merge still showed old builds on all four rows;
re-check armed ~13:21 AEST. Expect: both Taker arms + carry + sniper rows at
new builds via `audit_code_currency`, carry's `extra.scan` carrying the new
`noncrypto` census bucket, and the live Taker opening nothing.]

### Verify either one landed — by stamp readback, never by the green run

```bash
.venv/bin/python3 scripts/audit_code_currency.py --pnl-json https://pnl-dashboard-production-858c.up.railway.app/pnl.json --depth 200
```

Expect the row to move from `DEFERRED` to `CURRENT`. A green workflow run has
never implied a container took it.

---

## 1 · The "super bot" question — combining utilities

Four routes, ranked by evidence. The fleet's measured reality (1-Aug,
allocation organ): ALL measured claims live in the FUNDING class (3 books,
+$72.89, n=297); DIRECTIONAL has zero claims in 867 closes.

- **S1 — DECIDED-SHIPPED 5-Aug (jr)** (operator: *"Proceed with all of the
  above"* / *"Full permission"*). `fleet_bus.allocation_scale` consumes the
  organ's `target_usd`, clamped [0.25, 4.0], NEW entries only, wired into
  🌾 carry + ⚖️ Counterweight (live via the auto-deploy path) and 💸 the
  Farmer's SHADOW arm (**deferred behind the next marked Farmer deploy** —
  bundle with the queued snapshot_equity push). Real money never reads it
  (AST-pinned); kill switch `FLEET_ALLOCATION_MODE=advisory` per service.
  The organ itself is unchanged, publish-only.
- **S2 — BUILDING 5-Aug (operator: "yes build the super bot" — the pre-build
  option taken).** 🎸 **Barnesy** (`band-barnes-lshadow`, service
  `band-barnes-shadow`, `lighter_band_barnes_bot.py`) — first of the
  Australian-musician cohort. Three sleeves, each a conservative
  re-expression of its parent's validated gates: carry harvest (≥20% TRUE,
  decay-paid discipline, $80×4), funding-extreme directional (top |APR|, 10%
  stop, $40×4), x-sect L/S at the VALIDATED K=5 ($33 legs, 24h rebalance).
  Closes tagged `<side>-<sleeve>_<exit>` so the brain grades sleeves
  independently. **Config birth-frozen 30 days (BARNES_FREEZE_UNTIL
  2026-09-04)** so the clock accrues a single-policy sample; the 30-day
  clock starts at FIRST PUBLISH — gradeable ~mid-Sep at the earliest, and
  none of the parents' evidence carries over ((hm)), stated in the bot's own
  header. Birth-complete parity shipped in one commit: claim_writer at loop
  top, funding-form exit telemetry, snapshot_equity from day one, barnes.*
  levers (registered + birth-frozen at the consumer), deploy route +
  AUTO_IMAGES + ROW_ENTRY + dashboard row.
- **S3 — Directional consolidation: REFUSED, with evidence.** Merging the
  directional tail (Snap Back / gillard / abbott / intraday...) into one bot
  combines zero measured claims into one ungraded book with a fresh clock —
  a merged loser is still a loser, minus its history. The 🏛️ Parliament
  already IS the multi-strategy self-evolving experiment; the honest version
  of this wish is promoting its best book through the standard gate.
- **S4 — Consensus-ensemble book** (scout tickets × oracle regime × sentinel
  events × brain mults gating one book's entries). Buildable, genuinely novel
  — but it is a NEW thesis with no evidence yet, so it enters as a standard
  shadow book behind S1/S2 in priority. Cheap first step instead: measure
  retrospectively (replay: would consensus-gating have improved any existing
  book's closes?) before minting anything.

## 2 · Book decisions

- **🧲 Snap Back — DECIDED-RETIRED 4-Aug (option A, operator: "full
  permission to go ahead with all advancements").** Shipped same day,
  changelog (jh): code guard idles the bot (`SNAPBACK_RETIRED_OVERRIDE=run`
  to resurrect), row hidden + pruned, evidence engraved. The one act left is
  YOURS and moved to item 3's Railway list: stop/delete the
  `snap-back-shadow` service (remove its deploy-rule entries first) — the
  code guard is the durable half either way.
- **🌾 Carry — DECIDED-WAIT 5-Aug (option A, operator: "Proceed with all of
  the above").** Ride to ~30-Aug; both widening levers stay refused on
  measurement ((it)). Revisit lands on the calendar with the era window; the
  S1 scale (jr) now sizes its NEW entries by claim in the meantime.
- **⚖️ Counterweight — early revert. DECIDED-REVERTED 4-Aug (option A,
  operator: "full permission to go ahead with all advancements").** Shipped
  as the CODE DEFAULT K 8→5 + universe 60→30 (`lighter_funding_spread_bot.py`
  \+ the registry `env_default`s) — the operator-default route, NOT a
  hand-set lever: no `fundspread.*` lever was open on the bus (the (hs)
  ratchet had lapsed), so the widening lived in the env default and only an
  operator decision could move it. One correction to this item's own text:
  option A said "through the board's `fundspread.k` lever", but the designed
  channel can only widen-or-lapse back to `env_default` — it cannot SET 5
  while the default IS 8; the default was the actuator. Criterion wording
  honoured wholesale (it blames "the wider cross-section", so the universe
  reverted with K). Era NOT reset — capacity change = ordinary tuning (hc).
  Verify: row caps read k=5, universe_n=30 after the push.
  **[13-Aug (ll) — THE DOCKET NUMBERS FOR YOUR ~28-Aug CALL, updated.]** The
  book's −$27.62 day (5-Aug 00:37Z) was the revert CRYSTALLIZING the old
  K=8/wide basket's MTM losses — all 12 closes in one rebalance instant, the
  losers the non-crypto legs (SOXL −47%, SNDK −41%, MU −21%, SAMSUNG,
  SKHYNIX, WTI, BRENTOIL). Post-revert on the crypto basket (6→13-Aug):
  −$0.54 realised over 10 rebalance closes, MTM flat. **Era split: crypto
  +$5.90 over 65 closes vs non-crypto −$36.48 over 21 — the whole era loss
  sits in the population (ki)/(jg) already made unenterable.** That updates
  (jg)'s "+$4.80 on the trades it can still take" to +$5.90/65 with the
  post-revert week added. Options unchanged; the date stands.
- **🎸 Barnesy — harvest sleeves lack the (lk) class screen; frozen, so it is
  YOUR call, not a code push.** `harvest_candidates` (carry + extreme
  sleeves) takes non-crypto harvests (−$1.58 over 8 closes since birth);
  only the xsect universe was screened at (ki). The (lk) fix is one line to
  extend — but the book is BIRTH-FROZEN to 2026-09-04 for its single-policy
  clock, and a universe change is a policy change in kind: shipping it now
  resets a young clock to zero ((hm)/(kk)). ★ **A — apply at unfreeze
  (4-Sep)**, the screen lands with the first post-freeze policy rev, clock
  intact. **B — apply now**, eating the clock reset, if the non-crypto
  harvest bleed grows enough to outweigh ~a week of accrued sample (it is
  ~$0.2/day today). Nothing needed from you before 4-Sep unless B.
- **📊 Index Rider** — nothing to decide until the ~28-Aug zero-closes read;
  its MTM series now actually grades (post-(iz)/(ja)) from ~6-Aug.
- **💸 Farmer `min_vol` cage floor — DECIDED-SIGNED-MEASURED 5-Aug (ka)
  (operator conditional: "if it produces better numbers then proceed!").**
  The condition was tested BEFORE shipping: the calibrated Farmer replay
  over 30d of the venue's own tape, each tier at its own (js) friction —
  the [0.1M,2M) band ALONE reads **+$14.83 (both halves positive, maxDD
  −7.97) vs the incumbent's +$4.01**, robust at the tier's p90 (+$7.20).
  Rule pre-registered, passed → shipped: **both cage los 2e6 → 1e5**
  (option B alone turned out structurally inert — the judge's both-cage
  clamp invariant means an xp-only floor can never be exercised;
  mutation-pinned now), signatures in both registry notes, and
  **`min-vol-1e5` filed FOURTH** (above the negative-prior enter-gate,
  below the filed `min-vol-2e6`, whose ~11-Sep subset verdict de-risks the
  wider read — measured here the $2–10M band is the WEAK half). Real money
  unchanged: the paired bar (judge sole writer) + fade-watch remain the
  only door. Full table: `STUDY_THIN_TIER_MIN_VOL_2026-08-05.md`.

## 3 · Infrastructure

- **Railway cleanup — MOSTLY DONE (measured 5-Aug: 16 services remain of the
  review's 26; `perps-bot`, the five retired idlers and the deletable
  corpses are gone — the operator did the sitting).** Remaining, all
  optional/low-urgency:
  1. ~~`perps-bot`~~ **DELETED** (crash-loop over).
  2. ~~cross-exchange-arb, listing-sniper, momo-bot, freqtrade-trainer,
     triangular-arb~~ **DELETED**.
  2b. `freqtrade-{mum,dad,avo-maria,georgia}` — still EXIST in the project
     (visible in `status --json`) but hold no running deployment; delete at
     the dashboard whenever.
  3. ~~`tide-rider-lighter-shadow`~~ **DELETED 5-Aug** (repo half landed
     first — paths/grep/AUTO_IMAGES removed, image in MANUAL_IMAGES_OK,
     rule-absence pinned by test — then the service).
  4. ~~`snap-back-shadow`~~ **DELETED 5-Aug**, same sequence. Project now at
     **15 services, every one load-bearing**.
  5. Offline corpses: `freqtrade-{mum,dad,georgia,avo-maria}`.
  6. `nrl-feed` → move to its own Railway project (cost attribution + its
     failing workflow leaves this repo's CI).
  Do NOT touch: the failover pair (`funding-carry` + `yield-harvester-shadow`
  — now deliberate), both live services, the remaining live shadow services,
  `pnl-dashboard`, `market-context`, `Postgres`, `freqtrade-bots`.
  Saving: ~6 containers ≈ $10–30/mo + the resurrect hazard gone.
- ~~Five git-connected shadow services~~ — **DONE 4-Aug (option A)**: all
  five disconnected (`railway service source disconnect`), verified
  `source={"image":null,"repo":null}` on each — the whole fleet now matches
  the live pair: `railway up` from the workflow is the ONLY deploy path
  anywhere. (Historical options kept for the record: **B** was keep +
  declare with a branch guard; A won on consistency — one deploy path,
  cleaner doctrine. **[5-Aug: DONE — option A executed on the operator's
  explicit direction ("attend to railway item"), all five disconnected and
  VERIFIED: `railway status --json` reads `source: null` on EVERY service in
  the project, so the workflow's `railway up` is now the ONLY deploy path
  anywhere — the (io) class closed project-wide. The earlier blocked attempt
  note is superseded; `perps-bot` turned out to be ALREADY DELETED (the
  operator had done the deletion sitting — 16 services remain of the
  review's 26; the crash-loop is over).]**
- **Zombie publishers — RESOLVED 7-Aug, and NOT the way this item or my first
  answer assumed. IT NEVER STOPPED.** Located: Railway project **`trading-bot`**,
  two services — **`market-scanner`** and **`trading-bot`** — both deploying from
  repo `EJMC95/equities-momentum-alpaca`. Both ran **6-Aug 22:00 and 22:03 UTC**
  and logged `=== Run complete (LIVE) ===` while placing orders (`order 7db96759
  accepted`, `STOP CRWD trailing 12% attached (qty 65)`).

  What stopped is its PUBLISHING, and the cause is ours: the 5-Aug rotation
  `(kb)`. `trading-bot` logs `[bot_pnl_store] disabled: connect failed …
  password authentication failed for user "postgres"` — **a 14th pasted DATABASE_URL
  literal, in a project the rotation never swept.** `market-scanner` logs
  `DATABASE_URL not set` and never published at all. So `bot_pnl` is empty of
  alpaca rows because the writer is locked out, not because it went away.

  **Two things for you, and both are yours because this is a separate system
  placing live orders:**
  1. **Decide whether it should be running.** It says LIVE. This item used to
     describe it as "$86k paper equity"; the logs do not confirm paper. Nothing
     in this repo can tell you which, and that is the question worth answering
     first.
  2. **If you want its row back**, set `DATABASE_URL` on both services to the
     rotated value from Keychain (`security find-generic-password -s
     fleet-pg-rotation -w`). The `${{Postgres.DATABASE_URL}}` reference form
     that `(kb)` mandates does NOT resolve across projects, so this one is
     necessarily a literal — the single declared exception to that rule, and it
     will break again on the next rotation unless it is on the sweep list.

  *Corrects my own 7-Aug entry, which read "MEASURED SILENT" on the strength of
  a `bot_pnl` sweep. The sweep was right that no row is being written and wrong
  about why; I said the two cases were indistinguishable from this side, and
  they were — from THIS side. Reading the other project's logs distinguished
  them in one command.*

- ~~**Zombie publishers — MEASURED SILENT 7-Aug (superseded above).**~~ A full sweep of `bot_pnl` reads **23 rows written
  in the last 24h and ZERO of them retired** — every writer is a live,
  load-bearing service, and no `equities-momentum%`/`%alpaca%` row exists in
  the table at all. So either the publisher stopped or its row was pruned
  after its last write; **the two are not distinguishable from this side**,
  and the difference only matters for the external project's own cost. The
  fleet-side concern is closed. Confirming the publisher itself is one
  command, below, and it is YOURS to run rather than mine — `railway link`
  rebinds this repo's Railway context and concurrent sessions deploy from
  here.

  ```bash
  # in a scratch dir, NOT this repo — link rebinds the project context
  cd /tmp && railway link   # pick: trading-bot   (then repeat for ikbr-stock-bot)
  railway service list && railway logs --service <whichever> | tail -40
  ```
  *(superseded text below kept for the record)*
- ~~`equities-momentum-alpaca` still writes daily (~22:01 UTC ≈ 08:00 Sydney; $86k paper equity) — publisher is
  almost certainly in your `trading-bot` or `ikbr-stock-bot` Railway
  projects, which are separate systems you may want. Inspect:
  `railway link` to the project, `railway service list`, `railway logs`.
  Decision: stop it, or declare it external-and-deliberate (the fleet
  dashboard already hides the row either way).
  *Done this session: the two LOCAL zombies are stopped — `com.eamon.tri-arb`
  (retired bot, KeepAlive launchd) and `com.eamon.freqtrade.datarefresh`
  (hourly Kraken data pulls for the dormant local freqtrade). Plists archived
  in `~/Library/LaunchAgents/disabled-2026-08-04/` — reversible.*
- **CI quota** — **DONE**: the off-Actions CI-liveness probe shipped 4-Aug
  (jl); the three test jobs merged into ONE runner 5-Aug (one checkout, one
  pip install, ONE full-suite run that is simultaneously the regression net,
  the live signer harness and the coverage-floor input — >50% of the
  workflow's billed minutes; the lean no-SDK pass is the declared loss,
  still exercised by every local run without the wheel).

## 4 · Security / hygiene

- ~~Postgres password rotation~~ — **DONE 5-Aug (kb), the hard way.** The
  leaked credential is DEAD (verified refused); the live value exists only in
  the DB and the operator's macOS Keychain (`security find-generic-password
  -s fleet-pg-rotation -w`). The incident en route produced the standing
  rule now in Railway Setup: **every consumer's `DATABASE_URL` is the
  `${{Postgres.DATABASE_URL}}` REFERENCE, never a literal** — 13 pasted
  literals were what took the fleet dark mid-rotation. Full runbook incl.
  the `railway ssh` stdin/quoting traps: memory `pg-rotation-runbook`.
- ~~LuLu~~ — **DONE 5-Aug**: `allowInstalled = false` verified in
  `/Library/Objective-See/LuLu/preferences.plist`.
- *Done this session: scheduler purged (5 spent one-shots deleted; the four
  "Kraken-era P&L tasks" turned out to be unregistered leftover files — they
  never ran); all three git stashes verified superseded and dropped, with the
  4 stash-only analysis scripts recovered into `analysis_2026-07-01/` first.*

## 5 · Standing (calendar, no action)

**COMPUTED NOW — 6-Aug (ks).** The go-live dates below are derived from the
ledger by the grader each publish (`golive-readiness` → per-book `horizon`,
rendered on the 🚦 dashboard card and the daily review's 🔭 line) — read those,
not this paragraph. First live read: **Farmer-live on_track ~23-Aug (t bar
binding — its stamped (jf) era is 23-Jul, so the "~16-Aug" this item used to
carry matched the superseded era; the rot is why the calendar is computed
now)** · carry window-floor 30-Aug (n=1 in-era; the venue stall (I18) is the
real blocker). Human-decision dates stay hand-carried, correctly — a
trajectory cannot derive a review date: item-18 oracle grades + SPY/QQQ
graduation ~mid-Aug · Farnham-Six keep-or-retire verdicts ~28-29-Aug ·
Barnesy gradeable ~mid-Sep · Taker policy-clock ruling (chip queued will
surface the evidence).
