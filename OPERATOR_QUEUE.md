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
- **S2 — The literal consolidated funding super-book.** One new row (next
  cohort naming: Australian musicians) running three sleeves — carry-decay
  harvest, funding-extreme entries, cross-sectional L/S — each closing with
  its own tag so the brain grades sleeves independently. This is
  FORWARD_STEPS item 4 ("more funding surface") in consolidated form, and its
  own condition applies: **build it after the promotion pipeline proves itself
  on an existing book** — i.e. decide at ~16-Aug when the Farmer's window
  fills. Cost: a fresh 30-day clock (gradeable ~mid-Sep at the earliest); a
  merged book is a NEW policy, so none of the three books' existing evidence
  carries over ((hm)). *Option: pre-build in shadow now and let the clock run
  — the cost is only a row and attention.*
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
- **📊 Index Rider** — nothing to decide until the ~28-Aug zero-closes read;
  its MTM series now actually grades (post-(iz)/(ja)) from ~6-Aug.

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
  3. `tide-rider-lighter-shadow` — retired (if). **Repo half DONE 5-Aug**:
     paths/grep/AUTO_IMAGES entries removed (image declared in
     MANUAL_IMAGES_OK; `test_retired_services_have_no_deploy_rule` pins the
     rule's absence). Safe to delete the service whenever you like.
  4. `snap-back-shadow` — retired 4-Aug (jh). **Repo half DONE 5-Aug**, same
     treatment as tide-rider above. Safe to delete the service whenever you
     like. (Until then it idles harmlessly behind the code guard — the
     container prints the retirement line and sleeps.)
  5. Offline corpses: `freqtrade-{mum,dad,georgia,avo-maria}`.
  6. `nrl-feed` → move to its own Railway project (cost attribution + its
     failing workflow leaves this repo's CI).
  Do NOT touch: the failover pair (`funding-carry` + `yield-harvester-shadow`
  — now deliberate), both live services, the remaining live shadow services,
  `pnl-dashboard`, `market-context`, `Postgres`, `freqtrade-bots`.
  Saving: ~6 containers ≈ $10–30/mo + the resurrect hazard gone.
- **Five git-connected shadow services** (snap-back, counterweight,
  equities-regime, perp-sniper, family — Railway auto-deploys them from main
  beside the workflow's own `railway up`). Options: **A ★ disconnect** (one
  `railway service source disconnect --service <name>` each — same command
  (ip) used on the live Farmer; consistency, one deploy path), **B** keep +
  declare in CLAUDE.md with a guard asserting the branch is main (they are
  harmless-to-helpful while pointed at main). Either is defensible; A is
  cleaner doctrine. **[5-Aug: DONE — option A executed on the operator's
  explicit direction ("attend to railway item"), all five disconnected and
  VERIFIED: `railway status --json` reads `source: null` on EVERY service in
  the project, so the workflow's `railway up` is now the ONLY deploy path
  anywhere — the (io) class closed project-wide. The earlier blocked attempt
  note is superseded; `perps-bot` turned out to be ALREADY DELETED (the
  operator had done the deletion sitting — 16 services remain of the
  review's 26; the crash-loop is over).]**
- **Zombie publishers (external projects).** `equities-momentum-alpaca` still
  writes daily (~22:01 UTC ≈ 08:00 Sydney; $86k paper equity) — publisher is
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

- **Postgres password rotation** — still open, now less theoretical (copies
  existed in the dropped stash and in session scratchpads). Rotate in
  Railway → update `DATABASE_URL` references → the gitleaks hook already
  guards new commits.
- **LuLu** — flip `allowInstalled=false` (the 29-Jul posture sweep's one gap).
- *Done this session: scheduler purged (5 spent one-shots deleted; the four
  "Kraken-era P&L tasks" turned out to be unregistered leftover files — they
  never ran); all three git stashes verified superseded and dropped, with the
  4 stash-only analysis scripts recovered into `analysis_2026-07-01/` first.*

## 5 · Standing (calendar, no action)

First MTM-graded book ~6-Aug → Counterweight ~7-Aug · Farmer window ~16-Aug
(t≥2 is the whole question) · item-18 oracle grades + SPY/QQQ graduation
~mid-Aug · Farnham-Six verdicts ~28-29-Aug · carry gradeable ~30-Aug · Taker
policy-clock ruling (chip queued will surface the evidence).
