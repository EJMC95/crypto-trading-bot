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

- **S1 ★ — Allocation-weighted funding trio (a super bot in effect, no new
  book).** Flip `fleet_allocation` from advisory to ACTING on the shadow
  notionals of 🌾 carry / 💸 Farmer-shadow / ⚖️ Counterweight (evidence-ranked
  split, 25% probe floor, conserved total). One capital brain over three
  specialised organs — the utilities combine at the CAPITAL layer, where the
  evidence is, without resetting a single 30-day clock. Touches zero real
  dollars (shadow notionals steer what the fleet LEARNS). Reversible by env.
  *Say "do S1" and a session wires the consumer + kill switch through the
  standard replay/registry pattern.*
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
- **🌾 Carry — keep or wait.** Fresh era (31-Jul) × venue stall (0 eligible;
  one liquid book clears the bar and carry holds it). Both widening levers
  already REFUSED on measurement ((it)) — they are not on this menu. Options:
  **A ★ wait to ~30-Aug** (costs nothing; 5 open carries +$10.33 riding),
  **B** retire (against: the fleet's best all-time record, 5/6 t=2.99).
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

- **Railway cleanup — one sitting, guard-first order.** Delete in this order
  (deploy rule out first where one exists, then the service):
  1. `perps-bot` — CRASH-LOOPING now, retired bot; delete first.
  2. `cross-exchange-arb`, `listing-sniper`, `momo-bot`, `freqtrade-trainer`,
     `triangular-arb` — retired, idling, no deploy rules to remove.
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
  cleaner doctrine.
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
