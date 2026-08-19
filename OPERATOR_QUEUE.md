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

## ⚡ ~~WAITING ON YOU~~ · 🪁 band-kelly — **EXECUTED 18-Aug ~22:16Z under your "Continue maverick" grant: PR #180/#181 merged, service provisioned by the one-shot dispatch (workflow deleted at activation per the (lr) rule), row verified by stamp readback (`5eea92e33277`/n=14 byte-equal to prediction). The readback surfaced and closed a second (ml) stale-reader instance (run 537). Activation + the pre-first-close fidelity pass land with the (qh) PR. Item closes at the next daily review.**

**Born 18-Aug on your ask** (*"does the exact opposite of all of the major
losing sequences"*): `lighter_band_kelly_bot.py`, the measured mirror of
retired 🧲 Snap Back (founding claim crypto n=65, +0.605%/trade, t=+5.71 —
`STUDY_BAND_KELLY_2026-08-18.md`; brkfade and dipfade measured and REFUSED,
on the record). Everything is wired pre-provision (row map, dashboard,
tests, image); the deploy rule ships COMMENTED because since (hj) an
unresolvable service name is a hard error. Two steps:

**A ★ — provision (you, or any session with Railway access, ~2 min):**

```bash
railway add --service band-kelly-shadow
railway variables --service band-kelly-shadow \
  --set "RAILWAY_DOCKERFILE_PATH=Dockerfile.bandkelly" \
  --set "VENUE=lighter_shadow" \
  --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}'   # REFERENCE form, never a literal ((kb))
railway up --service band-kelly-shadow --detach
```

**B — activation commit (any session, after the row publishes):** verify
`band-kelly-lshadow` on /pnl.json carries an `extra.build` stamp matching
the local prediction (`build_compute` against the image's own COPY set —
compare `build_n` too, (fd)), then uncomment the three-line decide rule in
`railway-redeploy.yml` (search "band-kelly") and move `Dockerfile.bandkelly`
from `MANUAL_IMAGES_OK` to `AUTO_IMAGES` in `audit_deploy_coverage.py` —
the exact kiyosaki/(mk) path. Then this item leaves the queue.

---

## ⚡ NEW 19-Aug · THE UNDECIDABILITY SLATE — five I17 calls + one restrict-only cap, all from the fleet-wide audit `(qk)`

**Full evidence: `FLEET_AUDIT_2026-08-19.md`.** The audit's headline is that
the fleet has **no open wound** — four of five loss centres are populations
already gated off between 13 and 18-Aug. What is left is not tuning; it is
these decisions. Nothing below is executed by an agent.

**Read this first, because it reframes every row:** the venue is in a measured
liquidity drought ((qa): alt volume halving every 9.4 weeks, 44 weeks running).
Several books below are **starved, not edgeless**. That is an argument for
deciding them deliberately — not for retiring them as failures, and not for
widening a gate to manufacture entries (I19).

### A ★ — ⚖️ Counterweight: the ~28-Aug pre-registration stands, and today's read is RETIRE
Not a bleed call — an **undecidability** call. The book is clean: −$0.48 open
marks, screen holding, 30 closes in 14 days on the admissible basket. But the
(jg) KEEP consolation has decayed monotonically **+0.461% → +0.307% → +0.163%**
(t=+0.25, cluster-t +0.22), and t≥2 needs **~4,300 closes ≈ 5.1 years**. Even
**20 consecutive +1% closes** before 28-Aug move admissible t only to **+0.70**
— *no achievable data can flip this to KEEP*. **Do not pre-empt the date**
(nothing decisive is met in the losing direction and the residual is ~cents/day
at $5 legs); decide it on 28-Aug with this number in hand.

### B ★ — 💸 the LIVE Farmer: an I17 call on the only live funding book
era n=85, mean **+0.039%/trade**, t=0.29, **+$0.22 over 25.5 days**; trailing
14d −$1.99/45 closes; shadow twin −$9.52. Horizon: **undecidable, ~4,337
closes ≈ 1,332 days**. The 15-Aug study already refuted every exit-tuning
escape on this cell (48 cells, zero winners) — *"the stall is edge."* Real
capital ($197.31) sits on it. **This is explicitly NOT a tuning pass**; if you
KEEP, the rationale should be recorded against the P=0.06/P=0.155 controls.

### C ✅ — 👩 mum: **EXECUTED 19-Aug `(rd)`** — retired, ROW-scoped, reversible via `MUM_RETIRED_OVERRIDE=run`. Confirmed on its own ledger before acting: 3 closes lifetime, **all three opened 12-Jul so ZERO in-era**, ~2.4 closes/30d ⇒ ~12 months to the bar, funding drag −$2.15 > +$0.68 realised. Overturns the `(nf)` "green, slow" hold because that green is +$2.23 of OPEN MARKS (the `(lo)` precedent). 4 open paper positions freeze. Both halves + guard shipped, 5/5 mutations red. Exposed and fixed five tests that encoded "mum is alive"; `test_breakout4h_retired`'s survivor set is now DERIVED. Item closes at the next daily review.
3 closes in 5.3 weeks, **0 in-era**, all four slots frozen in month-long trend
holds; funding drag **−$2.15** exceeds **+$0.69** realised. `crypto-swing-daily`
was retired at (nf) on n=3 in six weeks. mum was HELD as "green" — that green
is **open marks, not evidence** (the (lo) precedent).

### D — 💼 turnbull and 📐 Grimes: starved by their own gates
turnbull: **zero entries for 16.4 days**; every observed skip is
`ml-gate(0.19–0.43)` against a 0.45 bar, and the ML ensemble is near chance
(oos_acc 0.51–0.57). `ml_gate` is registered but **declared authorless** — the
I18 shape. Grimes: gate flipped back to **all-three-CLOSED** since (om)
(keltner t=−0.20), 0 closes ever; its own study predicted this (0/31 retests
open). Both were HELD at (nf) on numbers since measured. **Neither is a
bar-lowering session** — the birth declarations say so themselves.

### E ★ — 🙏 Avo LIVE notional cap: restrict-only, zero expectancy price — **OPERATOR-ONLY BY DOCTRINE, not by capability.** CLAUDE.md's own routing table ends *"go-live/keys/SafetyRails caps stay operator-only forever"*, and this is a SafetyRails cap. (There is also no `railway` CLI in the session container, but that is incidental — the rule decides it.) Re-verified live 19-Aug 05:41Z: `cap_usd` **200.0** against equity **62.64**. Stated here so no future session re-attempts it as though it were merely blocked on tooling.
Published `cap_usd` is **$200.00** against **$62.53 equity** (3.2×) and $38.61
gross (5.2×) — so SafetyRails currently provides **no defence-in-depth** at the
book's real scale. The effective constraint is structural (clip = equity/4), so
**no trade the sizing can express reaches $200** and tightening changes nothing
admissible. The specific value is your risk choice; ≈ current equity is the
natural restore:

```bash
railway variables --service tide-rider-lighter-live --set "FREQTRADE_AVO_MARIA_MAX_NOTIONAL=65"
```

### F — the capital decision, restated because it dwarfs the rest
Real money is **$259.84 at ≈$0/day**. The nearest genuine event is 🙏 avo's
gate run (n=30 lands early-Sep; **t=+2.31 already passes**), worth ~$0.10–0.13/day
at today's clip — and ~10× that only via a deposit. **No lever in the codebase
is worth two orders of magnitude.**

---

## ✅ ~~19-Aug · GITHUB ACTIONS IS DARK~~ — **RESOLVED 19-Aug ~04:37Z (operator raised the spending limit). CI green, deploys running, PR #184 merged. The COST MEASUREMENT below is kept because it explains the recurrence and sizes it; the operator's decision on it is recorded and the item closes at the next daily review.**

*Independently corroborated from the one signal that runs on `main` with no PR
code in it: the `fleet-watchdog` hourly heartbeat went green again at run
`32216819346` (**19-Aug 04:43:59Z**), ending the failure streak `32205969563`
(01:43Z) · `32210855045` (03:04Z) · `32213741453` (03:53Z) whose last green
predecessor was `32197328429` (18-Aug 23:28:37Z). That lands ~7 min after the
limit was raised, so the two accounts of the recovery agree to the minute.*

**THE DECISION (operator, 19-Aug): leave CI structure alone and raise the
spending limit.** Recorded rather than re-litigated — the consolidation option
below is measured, refused by decision, and must not be re-proposed as if it
were an open question.

**THE MEASUREMENT, because it explains why this recurs and why the 28-Jul fix
only bought three weeks.** Actions bills PER JOB, rounded UP to a full minute:

| workflow | structure | measured burn |
|---|---|---|
| `changelog-check` | **12 jobs × ~6–17s**, billed as 12 min | ~15–20 runs/day ⇒ **~5,400–7,200 min/mo** |
| `fleet-watchdog` | 1 job, hourly | **~720 min/mo** |
| `tests` + `ci-notify` | 2 jobs/run | ~1,400–2,900 min/mo |

**Total ≈ 7,500–11,000 min/month against a 2,000 (Free) / 3,000 (Pro)
allowance** on a PRIVATE repo (public repos are unmetered — this cost exists
only because the repo is private). So the dominant cost is NOT the scheduled
watchdog at ~10%; it is 12 parallel guard jobs each billing a full minute for
ten seconds of work. **The 28-Jul cadence cut (30-min → hourly) targeted the
10%**, which is why it bought three weeks rather than fixing it.

**Consequence to expect, stated plainly:** at this burn the limit will be
reached again. The measured options if that becomes annoying are (a) consolidate
`changelog-check`'s 12 jobs into 1 job with 12 named steps (~5,000–6,600 min/mo,
costs the at-a-glance red/green matrix on the PR page), or (b) make the repo
public (unmetered, but needs a secrets-in-history audit first — credentials were
rotated in early Aug and that history has NOT been audited). Neither is being
done; both are priced here so the next session does not re-derive them.

---

## ~~19-Aug · original report~~ — CI **and every auto-deploy** were down

**The fleet's own watchdog diagnosed this before I did, and names the remedy:**
`/watchdog.json` → *"GITHUB ACTIONS DARK: hourly heartbeat 4.5h old (last
run_id 32197328429) — a billing lockout kills CI AND deploys silently (28-Jul
scar); check the repo's Actions runs + Settings/Billing"*.

Independently corroborated by bisecting scheduled runs on `main` (no PR code
involved): `fleet-watchdog` succeeded hourly through **18-Aug 23:28:37Z** (13s)
and has failed in **~3 seconds with no downloadable logs** ever since —
19-Aug 01:43Z, 03:04Z. Every PR check on every branch, from two different
sessions, fails identically. **The watchdog's `last run_id` is byte-equal to
the last green run I isolated**, so two instruments agree on the boundary.

**Why it matters beyond red checks:** the same lockout kills
`railway-redeploy.yml`, which is the ONLY automated deploy path. **No shadow
book can receive code until this clears** — including the `(qk)` correctness
fixes, which are merged-pending and will sit in main doing nothing.

**THE "JUST WAIT" OPTION IS RULED OUT, MEASURED.** The watchdog's *"billing
lockout"* line is an INFERENCE from heartbeat age — it never reads billing — so
it was worth testing against the one alternative that would mean do-nothing:
a GitHub platform incident. `githubstatus.com/api/v2/summary.json`, 19-Aug
04:2xZ: **"All Systems Operational", Actions `operational`, 0 active
incidents.** GitHub is fine; the lockout is account-side. Also ruled out: a
broken workflow file — **zero commits landed on `main` between the last green
run (23:28Z) and the first red (01:43Z)**, so no change of ours caused it.

**A — check Settings → Billing on the repo's account ★** (the 28-Jul scar is
the precedent; a spend cap or exhausted minutes produces exactly this
signature: instant failure, no logs, scheduled runs on `main` affected). With
the platform ruled out and a code cause ruled out, this is the remaining
explanation.

**B — if billing is fine**, the fallback is a manual `railway up` per service
for anything urgent, and CI stays advisory until Actions returns.

No code change can fix this and none was attempted. PR #184 is unaffected by
anything in its own diff.

---

*Closed at the 18-Aug queue sweep, per this file's own maintenance rule and
each item's "closes at the next daily review" clause — this sweep is that
review, and each closure was RE-VERIFIED against the live payload today, not
carried on the old claim: the BOOKS wave-2 birth (all four rows publishing
fresh on /pnl.json, ages < 4 min), the Avo Maria live slot swap
(`freqtrade-avo-maria-lighter` publishing at $62.46 via `tide-rider-lighter-live`;
the Taker LIVE row absent — no double-count), §0 PENDING DEPLOYS (closed
13-Aug), §6 the judge-unblock dispatch (both 💸 Farmer arms read equal build
`ab7b8b378665` on today's payload — note §6's "window re-accrues from
15-Aug" was itself superseded by the 18-Aug (pt) arm split + re-pair: the
judge's clean window accrues from the 18-Aug alignment), and §7 the red-stop slate (17 rows on
/pnl.json, none of the seven retired rows present, 🎸 Barnes gone too per
(pm)). Decisions live in the changelog; history in git.*

---

## 1 · The "super bot" question — combining utilities

Four routes, ranked by evidence. ~~The fleet's measured reality (1-Aug,
allocation organ): ALL measured claims live in the FUNDING class (3 books,
+$72.89, n=297); DIRECTIONAL has zero claims in 867 closes.~~ **[18-Aug
sweep, corrected in place per I12 — that 1-Aug frame is stale in both
directions: (nc) found ≈$13 of carry's pooled accrual is phantom (every
pooled all-time quote overstates, and its clean era reads −$15.45/n=10), and
the fleet's only above-bar book today is a DIRECTIONAL one — 🙏 avo shadow
(t=+2.31, on_track, the winners'-docket candidate, (qb)/(qd)). Read the
allocation organ's live claims table, not this paragraph.]**

- **S1 — DECIDED-SHIPPED 5-Aug (jr)** (operator: *"Proceed with all of the
  above"* / *"Full permission"*). `fleet_bus.allocation_scale` consumes the
  organ's `target_usd`, clamped [0.25, 4.0], NEW entries only, wired into
  🌾 carry + ⚖️ Counterweight (live via the auto-deploy path) and 💸 the
  Farmer's SHADOW arm ~~(deferred behind the next marked Farmer deploy)~~
  **[18-Aug sweep, corrected in place per I12: that deferral is SPENT several
  times over — (lx) 13-Aug measured the consumer already RUNNING on the
  shadow arm, and marked Farmer deploys have since landed 15-Aug (§6 dispatch),
  18-Aug ((pt) re-pair) and 18-Aug ((pz)); both arms read equal build
  `ab7b8b378665` today. S1 is LIVE end-to-end, snapshot_equity bundle
  included.]** Real money never reads it
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
  AUTO_IMAGES + ROW_ENTRY + dashboard row. **[18-Aug sweep: the S2
  experiment ENDED — 🎸 retired 17-Aug (pm), the I17 call, zero independent
  evidence on the carry cell; two of its three sleeves had already retired
  ((ly), (nf)). The super-bot answer stands where S1 left it: capital
  routing by measured claim, not a merged book.]**
- **S3 — Directional consolidation: REFUSED, with evidence.** Merging the
  directional tail (Snap Back / gillard / abbott / intraday...) into one bot
  combines zero measured claims into one ungraded book with a fresh clock —
  a merged loser is still a loser, minus its history. The 🏛️ Parliament
  already IS the multi-strategy self-evolving experiment; the honest version
  of this wish is promoting its best book through the standard gate.
- **S4 — Consensus-ensemble book** (scout tickets × oracle regime × sentinel
  events × brain mults gating one book's entries). ~~Cheap first step
  instead: measure retrospectively before minting anything~~ **[18-Aug
  sweep, corrected in place per I12: that first step was RUN — TWICE — and
  the thesis is REFUTED. `STUDY_CONSENSUS_GATE_2026-08-04.md` graded 84
  cells and ruled REFUSAL WITH EVIDENCE (the fleet's gating signals are
  CONSTANTS on this tape — stress never fired in 6,090 samples, sentinel
  risk-off 91.3%, oracle never LONG — so a consensus has no variance to
  gate on); the 13-Aug (lp) re-measurement agreed (retrospective gates on
  the taker's 42 era closes: survivors −$8.02 vs unfiltered −$4.40 — no
  gate stack turns a negative signal supply positive). S4 is
  CLOSED-REFUSED; the study's own §8 names what would reopen it (a second
  regime, i.e. BTC dir=+1 ever observed). This bullet was stale since
  4-Aug — the exact I12 decay class.]**

## 2 · Book decisions

- **🧲 Snap Back — DECIDED-RETIRED 4-Aug (option A, operator: "full
  permission to go ahead with all advancements").** Shipped same day,
  changelog (jh): code guard idles the bot (`SNAPBACK_RETIRED_OVERRIDE=run`
  to resurrect), row hidden + pruned, evidence engraved. ~~The one act left is
  YOURS and moved to item 3's Railway list: stop/delete the
  `snap-back-shadow` service~~ **[18-Aug sweep, corrected in place per I12:
  that act was DONE 5-Aug — item 3.4 records `snap-back-shadow` DELETED,
  deploy-rule entries removed first. Nothing is left on this book; its
  measured mirror lives on as 🪁 band-kelly's founding claim (qf).]**
- **🌾 Carry — DECIDED-WAIT 5-Aug (option A, operator: "Proceed with all of
  the above").** Ride to ~30-Aug; both widening levers stay refused on
  measurement ((it)). Revisit lands on the calendar with the era window; the
  S1 scale (jr) now sizes its NEW entries by claim in the meantime.
  **[13-Aug (mf) evidence block — SUPERSEDED 18-Aug, corrected in place per
  I12: the grace extension SHIPPED in `(px)` (FLIP_GRACE_H 1.0 → 6.0,
  env-tunable `CARRY_FLIP_GRACE_H`), together with `CARRY_MIN_VOL` $2M → $1M
  (2.3× cell occupancy over 34.9d: 5.73% → 13.42%, coins
  KAITO/XMR/PAXG/ROBO/XRP/ENA). The "deliberately NOT applied now" rationale
  died with the sample it protected — the class screen froze it 12-Aug and
  the book held ZERO positions at ship, so every future close opens under
  the new rule at a clean boundary. The (mf) numbers stand as the evidence:
  grace 1h +$27.25/t=1.95 h2-NEGATIVE with 192/231 exits churning the RT;
  6h +$41.17/t=2.96 both halves; 24h +$50.12/t=3.52 monotone.]**
  **[18-Aug — WHAT REMAINS PARKED FOR THE ~30-Aug DAY: ONE half, not two.**
  `STUDY_FUNDING_LIFECYCLE_2026-08-15.md` §4's **PERSIST 6h→12h**
  (+0.161%/episode, t=1.80, both halves positive, peaks at P=12; referee
  ruled NOT denominator shrinkage; consistent with 🧮 Hull's independent 24h
  persistence) stays parked behind this docket call — deliberately NOT
  ridden along with `(px)`, which chose the exit-and-floor pair and stopped
  there. ★If the ~30-Aug call is ride-on, PERSIST 12h ships then, through
  the replay gate; if retire, it dies at zero cost. Supply tripwire for the
  decision day: carry's census `eligible` going positive under the NEW $1M
  floor (the ≥20%/$2M count had been 0.00 for 3+ days pre-`(px)`; the $1M
  cell historically reads occupied 13.42% of snapshots).]**
  **[(qx) TRIPWIRE RE-BASING — read this before reading `eligible` on the
  decision day: the 13.42% base rate was measured at the 6h persistence
  gate, and (qx) moved the live gate to 12h, which admits strictly fewer
  windows (91% of qualifying windows die under 6h — most of what 13.42%
  counted never survives to 12h). A low `eligible` under the 12h gate is
  therefore NOT comparable to 13.42% and must not be read as "venue stall
  persists". Recompute the base rate at the shipped gate first:
  `python3 scripts/audit_book_overlap.py --gate 0.20 --floor 1e6
  --persist-h 12` — and judge supply against THAT number.]**
  **[18-Aug later (qx) — PERSIST 12h SHIPPED, under your queue directive
  ("implement all operator queue items that make the fleet improve/make more
  profit and win rate"), at the same clean boundary (px) used: the book held
  ZERO positions and the census read `eligible 0 / waiting 2` under the $1M
  floor at ship (the tripwire had NOT fired — recorded so the ~30-Aug day
  reads the supply story straight). Env-tunable `CARRY_PERSIST_H`; ordinary
  entry tuning per (hc), era unchanged; hypothesis-grade t=1.80 stated in
  the code comment; pinned by tests/autonomy/test_carry_persistence_gate.py
  (4 mutations red). WHAT REMAINS FOR ~30-Aug IS NOW ONLY THE DECISION
  ITSELF: the keep-or-retire docket call — no tuning half rides on it any
  more; if the call is retire, (qx) dies with the book at zero cost, exactly
  as this item priced it.]**
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
  **[18-Aug (qb) — the docket numbers refreshed again on today's class map:
  crypto +$5.94/n=94 vs non-crypto −$36.48/n=21 (t=−2.86, the class drag is
  119% of the era loss); trades under the CURRENT admission rule now read
  n=23, +$0.95, 56.5% win — thin, mildly positive. Still weakly
  KEEP-pointing; the ~28-Aug date stands untouched.]**
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
- **🎸 Barnesy — ~~harvest sleeves lack the (lk) class screen; frozen, so it
  is YOUR call~~ MOOT, corrected in place per I12 at the 18-Aug sweep: the
  BOOK WAS RETIRED 17-Aug (pm)** — the I17 call on the carry cell, your
  decision, zero independent evidence (0 of 9 episodes were a coin 🌾 carry
  was not already holding). Both 4-Sep unfreeze items below died with it:
  the (lk) class-screen extension and the (mf) FLIP_GRACE_H 6h extension
  have no consumer any more (`BARNES_RETIRED_OVERRIDE=run` resurrects the
  book, and only then would either fix matter — apply both in that same
  commit if it ever runs). The (mf) grace measurement itself was not lost:
  🌾 carry ships it since (px) and 🏦 Rich Dad since (mf). Historical
  options kept in git; this bullet leaves the queue with the sweep.
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
  ~~**`min-vol-1e5` filed FOURTH** (above the negative-prior enter-gate,
  below the filed `min-vol-2e6`, whose ~11-Sep subset verdict de-risks the
  wider read — measured here the $2–10M band is the WEAK half).~~ **[18-Aug
  sweep, corrected in place per I12: the queue order was REVERSED 13-Aug
  ((ln): min-vol-1e5 runs AHEAD of min-vol-2e6 — strongest direct prior
  first), and the ~11-Sep slot date is void twice over — the judge's window
  was voided 14→15-Aug ((mu)/the §6 dispatch) and again 18-Aug ((pt) arm
  split; re-paired same day, (pz) then moved both arms to HEAD), so the
  clean window accrues from the 18-Aug alignment and every downstream slot
  slid. The +$14.83-vs-+$4.01 prior quoted above is also no longer the
  current reading: (pw) measures the band's edge decayed on the trailing
  window and (qa)'s (kc) refresh reads every Farmer gate row negative
  full-window.]** Real money
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
  8. **[18-Aug sweep]** `band-barnes-shadow` — 🎸 retired 17-Aug (pm); the
     code guard idles it durably, so stop/delete is the same 3.7-shaped
     optional tidiness.
  9. **[18-Aug sweep]** `book-schwager-shadow` — 🧙 retired (po), service
     already STOPPED 16-Aug; its auto-deploy rule is still ACTIVE in
     `railway-redeploy.yml` (incl. `$_shared`), so any shared-module push
     resurrects the stopped container — the code guard then idles it, cost
     is one container ([[railway-autodeploy-resurrects-stopped-services]]).
     If you want it GONE: say so and a session does the repo half first
     (rule + grep + AUTO_IMAGES→MANUAL_IMAGES_OK, the 3.3 tide-rider
     sequence), then you delete the service.
  **[18-Aug sweep: the counts above are the 5-Aug census and stale — seven
  services were born since ((jw) barnes, (lr) garrett, (ls) kiyosaki, (mk)
  the wave-2 four), band-kelly is pending, and "every one load-bearing" no
  longer holds (3.8/3.9 idle retired). No fresh `railway status` census is
  recorded; the next operator sitting should recount. Note 2b and 5 list
  the same four freqtrade corpse services twice.]**
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
not this paragraph. ~~First live read: Farmer-live on_track ~23-Aug (t bar
binding)~~ **[15-Aug audit, corrected in place per I12 — that first read is
SUPERSEDED by the grader's own later publishes: Farmer-live now reads
`undecidable` (era t=0.48, needs n≈1,333 at trajectory vs n=76; both halves
negative), and every snapshot of the 14-Aug 24h history agrees. Its era edge
is statistically zero while execution measures clean — the stall is EDGE,
which no date can fix. It matures onto the decision docket at the 15-Aug
publishes alongside carry and Barnesy — and (qa) 18-Aug adds: its t collapsed
1.73→0.24 and it holds NOTHING today (eligible 0 / off_band 109); the (kc)
refresh withdrew gate support in both directions, so its idleness is
CORRECT.]** · carry window-floor 30-Aug (in-era n=10/−$15.45/t=−4.48 per
(nc)/(qb); the venue stall (I18) is the real blocker — **and (nc) 15-Aug: when
its keep-or-retire matures, read the pooled +$66 all-time as inflated ≈$13 by
the stale-container phantom-accrual window (17–28-Jul rows, 2.5–6.7× over);
the era sample is clean and reads −$15.45/n=10. The book's true story is
weaker than its row suggests**). Human-decision dates stay
hand-carried, correctly — a trajectory cannot derive a review date: item-18
oracle grades + ~~SPY/QQQ graduation ~mid-Aug~~ **[(qa) 18-Aug: graduation
re-run FIRED — graduated in bar count, NOT in graded sample (n=3 each vs the
n≥20 bar); milestone moves to ~mid-Sep]** · Farnham-Six keep-or-retire
verdicts ~28-29-Aug (⚖️ Counterweight's pre-registered criterion recomputed
15-Aug: crypto-only in-era +$5.90/+0.307%/trade t=0.49 — still weakly
KEEP-pointing; trades under the CURRENT admission rule n=15 read flat) ·
~~Barnesy gradeable ~mid-Sep~~ **[retired 17-Aug (pm) — off the calendar]**
· 🛢️ Garrett + 🏦 Rich Dad gradeable ~12-Sep (with the declared carry-cell
collision decision, `audit_book_overlap.KNOWN_CELL_COLLISIONS`, same day) ·
Taker policy-clock ruling (chip queued will surface the evidence).
