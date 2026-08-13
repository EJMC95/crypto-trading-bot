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

## ⚡ WAITING ON YOU · The BOOKS wave-2 birth (PR #169) — merge, then one dispatch

**(mb)–(me), 13-Aug:** 🧘 book-douglas, 📐 book-grimes, 🧙 book-schwager,
🧮 book-hull — four measured shadow books, full green bar, birth state (no
deploy rule is armed, so the merge cannot red any push). Two acts, in order:

1. **Merge PR #169** (draft — mark ready + merge).
2. **Dispatch the one-shot provisioner** (creates the four services + first
   deploys; the workflow only registers once it is on main):

```bash
gh workflow run books-provision.yml
```

Then say "done" in any session — it verifies all four rows on /pnl.json by
build stamp ((iw): a green dispatch is not a running book) and lands the
ACTIVATION commit (decide rules + paths:, MANUAL→AUTO, provision workflow
deleted per its DELETE-after-use header). Reading docs: the four
`BOOK_*_2026-08-13.md`; evidence: `scripts/study_books_cohort_2026-08-13.py`.

---

## ⚡ ~~WAITING ON YOU~~ · Avo Maria live slot swap — **EXECUTED 13-Aug ~19:13 AEST, verified by stamp readback (`e49ba8fa7ed2`); retirement + live-roster sweep shipped the same evening ((ma) addendum). Item closes at the next daily review.**

**Your decision, built end-to-end and inert on main.** 🙏 Avo Maria
(SwingDip, imported from the family registry so the arms cannot drift) takes
`tide-rider-lighter-live` — same service/keys/sub-account (~$62.80), clip =
equity/4, rails sized to the balance. The self-halted live Taker keeps
standing by until you run these. Full runbook + verification + rollback:
`CUTOVER_AVO_LIVE_2026-08-13.md`. Evidence basis stated there honestly:
shadow n≈10, +1.378%/trade, t=+1.68 — does NOT pass the gate; the go-live is
your explicit act.

```bash
railway variables --service tide-rider-lighter-live --set "AVO_VENUE=lighter_live" --set "FREQTRADE_AVO_MARIA_MAX_NOTIONAL=63" --set "LIGHTER_MAX_DAILY_LOSS=6"
```

```bash
gh workflow run 305025607 -f services="tide-rider-lighter-live"
```

Then say "done" in any session — it verifies by stamp readback and applies
`CUTOVER_AVO_LIVE_2026-08-13.patch` (retires the Taker LIVE row so the fleet
total does not double-count the sub-account; shadow arm untouched).

---

## 0 · PENDING DEPLOYS — **NONE. Section closed 13-Aug by the daily review.**

*Closed per this file's own maintenance rule ("an item leaves the day it is
decided") and per 0c's own instruction ("the section can drop at the next daily
review"). Verified 13-Aug 16:05 AEST by the rule this file sets for itself —
stamp readback, not a green run: `audit_code_currency --depth 45` reads every
stamped container **CURRENT at HEAD `5a4c9b8`**, except both 💸 Farmer arms,
which are **DEFERRED** (8 commits, none marked for their marker-gated service —
working as designed, not a finding). 0a/0b (6-Aug) and 0c (the (lj) live-Taker
veto + (lk) class screens, 13-Aug) are all landed and stamp-verified; carry's
`extra.scan.noncrypto` census bucket is publishing, so the (lk) screen is live
in the payload. Nothing is waiting on anyone.*

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
  **[13-Aug (mf) — NEW EVIDENCE FOR THE ~30-Aug DECISION DAY, deliberately
  NOT applied now (changing the exit mid-window corrupts the very sample the
  decision reads):** the carry-cell grace study — this book's own gate +
  exits replayed over 250d of the cell's coin population — measured the 1h
  flip grace churning half the cell's profit away: grace 1h +$27.25/t=1.95
  with h2 NEGATIVE and 192/231 exits paying the RT on sign wobbles; 6h
  +$41.17/t=2.96; 24h +$50.12/t=3.52, monotone, robust ex-AVNT. Its own
  ledger agrees in shape ((gq): sided `*_flip`s −$17.32 vs `decay_paid`
  +$71.42). ★If the book RIDES ON at ~30-Aug, extend `funding_carry_bot.py`'s
  `FLIP_GRACE_H` (a literal, 1.0) in the same act — 🏦 Rich Dad already took the 6h form at (mf), zero clock
  cost, hours after its birth. `scripts/study_books_cohort_2026-08-13.py`
  reproduces.]**
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
- **🛢️ Garrett — DONE 13-Aug (lr): ALIVE AND PUBLISHING.** Provisioned by
  the dispatched workflow on your grant (repo's own RAILWAY_TOKEN), verified
  by the row itself: `band-garrett-lshadow` online, $1,000, svc
  `band-garrett-shadow`, build stamped — the 22nd row on your board.
  Auto-deploy rule ACTIVE (placed after `farmer_files` is assigned — an
  empty shell var greps everything, learned on placement); the provision
  workflow is DELETED per its own delete-after-use note. One recorded
  wrinkle: runtime clip reads $30 (venue minimum) vs the study's modeled
  $25 — per-trade % is clip-invariant and clip-scaling was declared
  unmeasured in the study's own honesty gates. 30-day clock started at
  first publish (~13-Aug): gradeable ~12-Sep. Nothing left for you here.
  Original checklist kept for the record: The thin-tier funding book (the fleet's strongest
  measured unbuilt claim: the [0.1M,2M) band, +$14.83 both halves vs the
  incumbent's +$4.01) ships as a VARIANT of the Farmer's proven file — code,
  tests, dashboard row and docs are all on main. To bring it to life:
  1. Railway dashboard → this project → **New Service** → name it exactly
     `band-garrett-shadow` (empty service, no source — the workflow deploys
     it, same as every other service).
  2. Set its variables:
     `FUNDING_VARIANT=band-garrett` · `VENUE=lighter_shadow` ·
     `FUNDING_MIN_VOL=1e5` · `FUNDING_MAX_VOL=2e6` ·
     `DATABASE_URL=${{Postgres.DATABASE_URL}}` (the REFERENCE form, (kb))
     — gate 0.05 TRUE and $25 clips are the file's defaults; set nothing
     else.
  3. First deploy: `gh workflow run 305025607 -f services="band-garrett-shadow"`
     (or tell the session "garrett service is up" and it will dispatch +
     activate the auto-deploy rule so every future push tracks main). The
     rule to add in `railway-redeploy.yml`'s decide step, right under the
     Garrett prose note (three lines, verbatim):

     ```
     if echo "$changed" | grep -qE "$farmer_files"; then
       svcs="${svcs:+$svcs,}band-garrett-shadow"
     fi
     ```
  The row appears on the dashboard at first publish; 30-day clock starts
  then — gradeable ~mid-Sep.
- **🏦 Rich Dad (`book-kiyosaki-shadow`) — DONE 13-Aug (ls): ALIVE AND
  PUBLISHING, VERIFIED BY THE ROW** (`book-kiyosaki-lshadow` online,
  $1,000, build `96aac5eae665`/n=14 — equal to the locally predicted id,
  so the container runs the merged code; the 23rd row on your board).
  Nothing left for you here; the birth uncovered and closed a real
  infrastructure class along the way (the 21,000-char run-scalar cap that
  killed main's deploy workflow for ~30 min — changelog (ls)). Original
  bullet kept below for the record. Your ask ("read rich dad poor dad and create a
  bot from it") shipped as the cash-flow doctrine book: only
  funding-RECEIVING positions (assets), delta-neutral modelled so P&L is
  pure cash flow, liability sales after a 1h grace, decay-closes only
  after payback (pay yourself first), and the payback-velocity entry gate
  (a deal must repay its round trip inside 120h — effective bar ~21.9%
  TRUE, a tightening of the validated 20%). Full reading + evidence table:
  `BOOK_KIYOSAKI_RICH_DAD_2026-08-13.md`. Timeline, executed under your
  ask + the (lr) precedent: birth PR #164 merged on green CI; **Provision
  Rich Dad dispatch #1 GREEN in 96s** (service created, env set, first
  `railway up` accepted); the birth merge then hit the (ls)
  scalar-length incident (see the changelog entry — main's deploy workflow
  was dead until the repair), so the DASHBOARD had not yet learned the new
  base and the row could not appear on /pnl.json. PR #165 carries the
  repair + the activated deploy rule + the AUTO_IMAGES move + the
  provision tool's deletion. **After #165 merges, the only check left is
  yours to enjoy, not to perform: `book-kiyosaki-lshadow` on the dashboard
  with `extra.build` stamped.** 30-day clock starts at first publish —
  gradeable ~12-Sep by the standard gate. Env-only config (no tuning
  lane), so nothing here can drift while it accrues.
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
  **[13-Aug (mf) — a SECOND item for the same 4-Sep unfreeze rev, so one
  policy change carries both:** the carry-cell grace study measured the 1h
  flip grace on the ≥20% cell churning half the profit away (1h +$27.25/
  t=1.95 h2 negative → 6h +$41.17/t=2.96 → 24h +$50.12/t=3.52, monotone,
  robust ex-AVNT). Its carry sleeve's own 8 closes are ALL `flip` exits at
  0% win ((lv)). ★Extend `lighter_band_barnes_bot.py`'s `FLIP_GRACE_H` (a literal,
  1.0) to 6h in the same unfreeze commit as the class screen — two measured fixes, one clock reset,
  already spent.]**
- **📊 Index Rider — DECIDED-RETIRED 13-Aug (lo)** (operator: *"get rid of
  what's not working"* — the I17 call, made early on conclusive evidence:
  ZERO closes in 44 days and a measured rule rate of ~17.2 closes/yr against
  a 30-close bar — no waiting period changes structural undecidability).
  Shipped same day: code guard idles the bot
  (`INDEX_RIDER_RETIRED_OVERRIDE=run` resurrects), row hidden + pruned.
  The one act left is YOURS: stop/delete the `equities-regime-shadow`
  Railway service whenever — the code guard is the durable half either way
  (added to item 3's list).
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
  7. **[13-Aug (lo)]** `equities-regime-shadow` — 📊 Index Rider retired;
     the code guard idles it durably, so stopping/deleting the service is
     optional tidiness (~$2-5/mo).
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
