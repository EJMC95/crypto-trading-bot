# HANDOFF — start here

_Generated 2026-09-02 15:45 Sydney (05:45Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

## Carried — pick these up FIRST (I11)

### `counterweight-preregistered-fresh-read`  ·  owner: **session**
⚖️ Counterweight was KEPT 1-Sep under I17-as-amended with a PRE-REGISTERED read (I21, recorded in CLAUDE.md's acknowledged-recurrence line for perps-funding-spread): grade the FRESH on-class closes (class_split, closes AFTER 1-Sep only — never the window that motivated the keep) at n>=60 or on 1-Oct, whichever first. RETIRE without further debate if the fresh on-class upper bound (m+1.28*SE) <= 0; keep grading if the fresh mean > 0; anything else returns to Eamon with both numbers.

_Still open because:_ the read date has not arrived. This row is the tripwire the registration lacked: its predicate fires on 1-Oct, so CI reds until a session actually PERFORMS the read and closes this row with the verdict in the CHANGELOG. If fresh on-class n reaches 60 EARLIER, do the read then — the date is the backstop, not the trigger.

### `allocation-clamp-is-a-per-position-bound-doing-per-book-duty`  ·  owner: **OPERATOR**
💰 fleet_allocation's [0.25, 4.0] clamp is a per-POSITION slippage bound being asked to do a per-BOOK job. **[(vj)] THE 4.0 ALARM THIS ROW USED TO CARRY IS WITHDRAWN — it was measured stale.** It read '💰 sits AT its 4.0 ceiling on 🌾 carry right now, delta_usd +13,500, $14,400 of gross on a $1,000 book'. Measured on the live payload 27-Aug: the MAXIMUM scale anywhere in the fleet is **1.594** (🙏 avo shadow) and carry sits at **1.272** ($1,271.75 target on a $1,000 book). (tz) replaced the winner-take-all split with a tilted flat prior, which made 4.0 structurally unreachable — so the row described the organ as it behaved BEFORE the fix that had already shipped. What survives is LATENT, not live: the ceiling still PERMITS a scale that breaches the 15% go-live drawdown bar, because maxDD is the one bar that is NOT clip-invariant ((hl) measured per-trade % invariance for the other five) — ⚖️ Counterweight breaches at 3.06x, inside the 4.0 ceiling.

_Still open because:_ the clamp is a capital-allocation policy and moving it moves money between books — an operator call (I16), not a session one. It is NOT urgent: nothing is near the ceiling today. What a session CAN do first is derive the per-book bound the drawdown bar implies (the `GROSS_X_MAX = 0.15/|stop|` shape (sr) used on avo) and publish it beside the claim, so the ceiling stops being a single number shared by books with different stops.

### `brain-mult-transition-oscillation`  ·  owner: **session**
The brain's `t` is computed on DOLLARS (`brain_stats.weighted_bucket` reads `profit_abs`), so a bucket MID-TRANSITION is a mixture of two clip scales: sd inflates against mean and `t` falls on a book whose edge has not moved. Predicted shape: a bucket that clears a rung steps back down a rung within ~10 closes, then climbs again. A uniform scale is invariant, so there is no runaway — this is a transient limit cycle, damped by the 14d decay and the 3-run streak gate.

_Still open because:_ the fix is hysteresis in the PUBLISHER (`qualify_v3` is stateless; the held rung lives in bot_learn's `mult_streaks`), and rewriting the brain's ladder on the same day 13 consumers were wired to it is the untested-rewrite-of-an-authority the doctrine forbids. It is now MEASURABLE for the first time — every close carries its `brain_mult` — so the next pass tests the prediction against real closes instead of a model.

### `brain-mults-are-two-opinions-wide`  ·  owner: **session**
(so) wired every living book to the brain's stake multiplier, including both real-money rows — and on the day it shipped the brain had exactly TWO published opinions across twenty books (taker short-divergence 0.75, Counterweight long 0.75). The plumbing is done; the ORGAN is nearly silent, because a mult needs >=30 era closes AND >=3 consecutive runs and most books never reach the first. The open question is whether those floors are right now that the range is 6.7x either way: a floor calibrated for a 1.5x ceiling is not obviously the floor for a 6.7x one.

_Still open because:_ moving a brain floor changes what sizes EVERY book, real money included — it needs its own measurement (how many buckets would qualify at each floor, and what their realised expectancy was), not a judgement call.

### `family-shadow-stale-writer`  ·  owner: **OPERATOR**
🩺 family-lighter-shadow's rows (👩 mum-lshadow, 🙏 avo-lshadow — the live pair's CONTROL ARMS) publish build edc3032d1c46/15, which the repo's own audit_code_currency resolves to commit d2c0cb9 (28-Aug, 84 commits behind, 5 touching lighter_family_bot.py). Measured 2-Sep: THREE OK-reported deploys (05:12 run 660, 05:21 run 661, 05:33 dispatch 664 from clean main) each booted a container that runs its loop, and the (vy) restart lever (run 665) ran too — the rows kept the old stamp through all four. A pre-28-Aug container is still the writer: the (ml)/(vy) stuck-serving class on this service for the SECOND time (646/647/648 before), and the family bot has no claim_writer, so the two writers are unguarded ((hp) class). Consequence: the (wp) scan-order parity port, mum v2's post-28-Aug fixes and the (wt) lever surface have NOT reached the shadow twins; the judge's pair cannot open until they do.

_Still open because:_ no lever in this repo swaps the serving container when Railway's activation wedges: `up` builds and the swap does not happen, `redeploy` re-runs the CURRENT deployment ((vz)). The act is Eamon's, in the Railway UI: find and remove the extra running instance of family-lighter-shadow (or `railway down` the service, then `railway up` from clean main), then read back extra.build on freqtrade-mum-lshadow — expected 9c90be27d763/15 at 6639f1e, or the (wt) image's own id once merged (16 files: fleet_tuning.py joins the COPY set).

### `ceiling-capital-inversion`  ·  owner: **OPERATOR**
Capital sits in INVERSE proportion to measured edge: the two worst books run at 88-102% of capacity (⚖️ Counterweight -1.433%, 🛢️ Garrett -1.460%) while 👩 mum at +4.658%/trade is capped at FOUR slots and 🙏 avo at +1.085% uses 40% of six. `fleet_allocation` computes the right answer and is ADVISORY with consumers on three funding books only.

_Still open because:_ moving capital between books is an operator call, not a session one — the organ already ranks it honestly (I16).

### `books-should-declare-themselves`  ·  owner: **session**
18 of 19 living books do not publish `extra.thesis` — their design lives in `fleet_manifest`'s bridge table instead of on the row. `design_for` already prefers a book's own publication, so each migration is one publish-site edit and the manifest entry goes quiet on its own.

_Still open because:_ 18 bot edits and 18 deploys; do it a book at a time on the next deploy each one earns for another reason.

### `unmeasurable-lever-backlog`  ·  owner: **session**
30 registered levers still have no QUANTITIES spec — no recorded quantity to profile them against. The ratchet in audit_lever_measurability stops the pile GROWING; draining it is per-lever work: record what the knob cuts, then spec it.

_Still open because:_ each one needs the bot to stamp its own governing quantity first (the (sk) give_back/mae_ret pattern).

## Shipped today (62 commit(s), entries (tg), (wb), (wc), (wd), (we), (wg), (wh), (wi), (wj), (wl), (wm), (wn), (wo), (wp))

- `bd1ad2a` Merge remote-tracking branch 'origin/main' into claude/bot-system-health-check-q0hko4
- `b7599d4` Renumber (ws) -> (wt): main took (ws) for the sentinel's graded bar while this pass was open
- `21283ad` (ws) Proceed with everything in the organ review: five docket retirements, the incubator cage re-decided beside (wr)'s clock split, the judge's lane moved to mum, and a weekly organ board
- `6639f1e` The sentinel earns its fear (ws): one graded bar (n>=10, hit>=0.55) for BOTH proposal directions — a below-coin-flip playbook can no longer propose the crouch
- `7ab31ed` The clock split (wr): the breakout trend exit gets its own BRK_MAX_HOLD_H — taker.max_hold_h steers only the divergence bracket, AST-pinned, behaviour-neutral at ship
- `7cb0c7d` The backlog drained (wq): both live books claim-justified (ratchet 2->0), Counterweight fresh-read tripwire, minvol wired into the tp study, the (sk) breakoutup pins re-decided on a sighted gate, divergence stop priced (a refusal)
- `faf9bc8` [deploy-live] Merge PR #262: (wp) support-system deep dive — cohort long budget, held-basket margin, shadow scan-order parity, living shortfall pair
- `f58ba46` Merge remote-tracking branch 'origin/main' into claude/bot-system-health-check-q0hko4
- `7227ca0` Renumber (wo) -> (wp): main took (wo) for the edge audit while this PR waited on CI; citations moved with it (wp)
- `cf11c48` Merge PR #260: the edge audit — 18 living books, zero survive multiplicity, four of four founding claims rejected on their own ledgers (wo)
- `dec9ad4` (wo) the support-system deep dive: cohort long budget, held-basket margin, shadow scan-order parity, a living shortfall pair, Counterweight's date
- `713c0c0` Kelly's clip was already cut to $80 on 1-Sep (vy): the audit's 'nothing reduces her clip' corrected in place, and her Monte Carlo re-run at the live clip (wo)
- `aa93e7d` Regenerate HANDOFF after the third main merge (wo)
- `a46640b` Merge origin/main: (wn) the CI-liveness pager landed first; the edge audit keeps (wo) above it
- `bdf6689` Renumber (wn) -> (wo): main took (wn) for the CI-liveness pager; citations moved with it (wo)
- `09e5fc4` (wn) the CI-liveness pager cried wolf 1-in-10: heartbeat rides push CI, LATE warns at 4h, DARK pages at the measured 12h
- `bd9b07a` CodeQL hygiene on the edge audit: nine findings — eight bare open() calls now use context managers, one unused local removed (wn)
- `4e65d49` Merge PR #261: CodeQL hygiene on the #257 suites, with its dated (wg) note
- `8516ff6` Regenerate HANDOFF after the second main merge — I11's regenerate-last half (wn)
- `b874c82` Merge origin/main: mum's (wm) pre-registration landed first; the edge audit keeps (wn) above it
- `07b609e` Renumber (wm) -> (wn): main took (wm) for mum's I21 pre-registration first; citations moved with it (wn)
- `6dfbc16` Regenerate HANDOFF after the main merge — I11's regenerate-last half (wm)
- `af7700b` Merge origin/main: main's (wl) dashboard fix landed first; the edge audit keeps (wm) above it
- `65d67c5` the changelog gate counts tests/ as bot-affecting — the CodeQL hygiene pass gets its dated note in (wg)
- `712c3df` Renumber (wl) -> (wm): main took (wl) for the dashboard fix first; citations moved with it (wm)
- `9f091f0` (wm) — mum pre-registered on the winners' docket (I21); the snapshot pin re-aimed per I26
- `c90e359` CodeQL hygiene on the #257 suites: an unused os import and an unclosed file handle
- `c974f7d` Regenerate HANDOFF — I11's regenerate-last half (wl)
- `acc656a` The edge audit: 18 living books, zero survive multiplicity, four of four founding claims rejected on their own ledgers (wl)
- `05985d6` [deploy-live-georgia] (wl) pnl dashboard fix: capital-move-immune daily P&L + georgia's drained live row hidden with the (ta) receipt
- `3e15884` Merge PR #258: the (wk) record — the night's cross-session convergences, receipts and withdrawals
- `0030ce1` Merge remote-tracking branch 'origin/main' into claude/fleet-audit-review-wjz9zy
- `6887a8e` [deploy-live-mum] Merge PR #259: the (wh) daily-loss floor reverted — the pinned rail restored, mum's staged $57 cap activates (wj)
- `0173257` Merge remote-tracking branch 'origin/main' into claude/fleet-audit-review-wjz9zy
- `fa87526` (we) corrected in place: the guard learns direction after crying wolf on a deploy wave
- `7d6fdef` wiring test rejects a constant: kwarg-present/value-None survived the round
- `48642fe` SPLIT-BRAIN guard: direction is load-bearing — the second live run cried wolf on a deploy wave
- `0cb659e` Merge origin/main: the peer's (wi) latch-release landed first — the runbook entry renumbers to (wj); the avo host now carries both the clear-guard and the restored daily-loss rail
- `9515786` The latched-lock release valve: a lock stamped by a defective rail no longer outlives its own fix — avo's 04:02:46Z phantom is its first release (wj)
- `85c9f8e` [deploy-live-taker] avo: FAMILY_CLEAR_GUARD release lever for the (vn) latch — armed-by-fixed-defect lock gets a designed exit
- `6626f39` (wi) — the latch outlived its bug: the (vg) unlock ported to the live arm
- `1e01a45` FAMILY_CLEAR_GUARD reaches the live arm — once per process, and the sentinel is the point
- `e733653` Eamon takes the lever: LIGHTER_MAX_DAILY_LOSS=57 set on mum-live (skipDeploys, rides the marker deploy) — derivation published per (tg)
- `d5741ec` the (wh) title keeps its main stem + CORRECTED IN PLACE declared — the cross-branch letter arm now reads it as the same entry corrected (retitle, not a deletion; session_commit's deletion guard cannot tell those apart, its own message routes retitles here)
- `1d959e9` the (wh) entry records the shipped window: the refuted floor rode Eamon's merge to all three live services for ~2h, telemetry disagreeing with the actuator
- `dd5bb32` Drive #258 to green: the (wh) daily-loss floor left one real-money test pinning the superseded pilot-cap contract — main red on its own direct push
- `9e22cbd` Revert the (wh) daily-loss floor — a pinned safety test showed the abs cap is a deliberate tighter fleet rail
- `0b97876` the taker is georgia's successor — staged go-live runbook + carry named the regime hedge (wi)
- `2b6e101` The (wi) record: #257 taken over and deployed to all three live services in one act; avo's unlock stamped 04:02:46Z; binding-label nit recorded (wi)
- `9b41ab5` [deploy-live] Merge PR #257: avo's maxdd rail reads the funded book + georgia's live arm retired, reallocated to mum (wf)(wg)
- `ea2d96f` mum's daily-loss pilot cap floors under the pct leash — funded to $570 she halted at 5.26% not 10% (wh)
- `bdfc309` Drive #257 to green: the judge's own selftest didn't know georgia stands down, and main's (we) detector selftest was never registered
- `6ea2664` Merge origin/main; renumber my letters (wd->wf avo, we->wg georgia) around the concurrent (wd)/(we) on main
- `a5b928a` retire georgia's live arm (row-scoped) — Eamon's 'retire + reallocate to mum' call (we)
- `0b36f02` (we) — the orphan had no detector: the split brain re-derived from the DB alone, and the class gets its guard
- `681377b` tomllib shim: the local autonomy suite was dying at COLLECTION, so it ran zero tests
- `2fe4b5f` SPLIT-BRAIN detector: extract classify_orphan so the georgia-v3 half is mutation-testable
- `5a43ba0` SPLIT-BRAIN detector: a book's summary row must carry the same build stamp as its own newest close
- `40a311f` avo's maxdd rail was measuring 4% of her book and calling it 20% — funded-equity denominator (wd)
- `03ed81c` Merge PR #256: repo public - sweeps clean, CodeQL path reopens, branch protection now more urgent (wd)
- `d69ed1a` Merge PR #255: the orphan survives a region migration; CodeQL enable withdrawn - code scanning is plan-blocked on a private personal repo (wc)
- `879ba9b` Merge PR #253: GROSS_X live on all three books via the Railway connector; the family wedge is an orphaned container and (id)'s assumption is measured false (wb)

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

