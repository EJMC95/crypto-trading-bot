# HANDOFF — start here

_Generated 2026-09-03 18:01 Sydney (08:01Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

## Carried — pick these up FIRST (I11)

### `mum-halt-cost-preregistered-read`  ·  owner: **session**
(xv) pre-registered whether 👩 mum's daily-loss halt costs or saves her, paired same-coin against her never-halting shadow twin. At registration her ledger holds exactly ONE daily-loss halt (2-Sep 17:19:45Z, 8 legs, +1.76pp/leg cost against the twin) -- one flatten instant is ONE observation, not eight, so it decides nothing. READ at n>=5 halt EVENTS occurring AFTER 2026-09-03: LOOSEN only if mean paired cost > 1.0pp/leg AND the sign is consistent across events; otherwise KEEP. Instrument: scripts/study_mum_halt_cost_2026-09-03.py (its calibration gate REFUSES unless it reproduces both the registered event and the registered baseline).

_Still open because:_ the rail is HELD until the criterion is met -- a cost-only study of a daily-loss halt reads 'loosen' on every ordinary halt day right up until the day it saves the book, so the burden sits on loosening. Closes when the read is taken and recorded (the PRE_REGISTERED block removed from the study).

### `kelly-fresh-read-pre-registered`  ·  owner: **OPERATOR**
EDGE_AUDIT_2026-09-02.md section 6.1 pre-registered a keep-or-retire read on 🪁 kelly at the (vy) $80 clip: at n>=60 fresh closes since 1-Sep or on 1-Oct, whichever first -- RETIRE if the fresh upper bound (m+1.28*SE) <= 0, keep grading if the fresh mean > 0, anything else returns to Eamon. Her all-time upper bound (+0.03% on n=383) has not excluded a positive mean, so I17-as-amended forbids retiring on it today.

_Still open because:_ the read lived only in the report's prose (the I21 shape); it is now the `band-kelly` entry in golive_readiness.DECIDED_UNTIL, so the docket asks on the date. Closes when the decision is recorded and the entry removed.

### `georgia-v1-preregistered-read-10sep`  ·  owner: **session**
🔮 georgia v1 was on the (wt) September slate and DEFERRED on Eamon's confirmed date ('On 10 sep'): her cap-5 trajectory carries the pre-registered claim georgia-entry-cap-5-days-to-gate (grade_after 10-Sep, days-to-gate ~187 predicted at a higher mean). ON 10-SEP: grade the claim on her post-cap closes ONLY. Prediction fails -> retire via lighter_family_bot.RETIRED_BOOKS key 'freqtrade-georgia' (override GEORGIA_RETIRED_OVERRIDE) + both halves + slate-test update; holds -> record the keep with the fresh number. Either way, close this row with the verdict.

_Still open because:_ retiring her before the registration's own read voids it (I21/I25); the docket's ~4,233d pools ~200 pre-cap closes against ~25 post-cap ones.

### `counterweight-preregistered-fresh-read`  ·  owner: **session**
⚖️ Counterweight was KEPT 1-Sep under I17-as-amended with a PRE-REGISTERED read (I21, recorded in CLAUDE.md's acknowledged-recurrence line for perps-funding-spread): grade the FRESH on-class closes (class_split, closes AFTER 1-Sep only — never the window that motivated the keep) at n>=60 or on 1-Oct, whichever first. RETIRE without further debate if the fresh on-class upper bound (m+1.28*SE) <= 0; keep grading if the fresh mean > 0; anything else returns to Eamon with both numbers.

_Still open because:_ the read date has not arrived. This row is the tripwire the registration lacked: its predicate fires on 1-Oct, so CI reds until a session actually PERFORMS the read and closes this row with the verdict in the CHANGELOG. If fresh on-class n reaches 60 EARLIER, do the read then — the date is the backstop, not the trigger.

### `regime-short-veto-preregistered-read`  ·  owner: **session**
The edge audit's hypothesis #3 is a PRE-REGISTERED instrument now (I21): `scripts/study_regime_short_veto_2026-09-02.py` labels every close by the oracle's verdict for its coin at the OPEN and grades the vetoed set (short in LONG-window / long in SHORT-window) at t_crit(n). Registered 2-Sep 09:30Z. READ: run it with `--fresh` when the largest living vetoed set reaches n>=30 fresh closes (🪁 kelly's shorts run ~11/day; ⚖️ counterweight's ~1/day) or on 16-Sep, whichever first. CONFIRMED -> build the veto shadow-first on THAT book, graded against its un-gated twin, own entry; REFUTED -> record it beside the audit's hypothesis table; else record the numbers and re-arm one more read (P3: at most twice).

_Still open because:_ the fresh sample has not accrued. At registration the instrument read NOT DECIDABLE on every book: the oracle's reachable history is 200h, BTC read LONG-window in 418 of 418 snapshots, and the largest vetoed sets were 🪁 kelly n=122 (-0.273%/t, ub +0.25% — undecided), 💸 farmer-shadow n=26 (ub +0.009%, one close short — retired, frozen) and 🧘 douglas n=18 (ub +0.029% — retired, frozen). The date is the backstop, not the trigger.

### `taker-hold-floor-preregistered-read`  ·  owner: **session**
The edge audit's hypothesis #2 is a PRE-REGISTERED instrument now (I21): `scripts/study_taker_hold_floor_2026-09-02.py` walks 🎫 the taker's OWN entries through `exit_reason` with a hold floor (no tp/sl/trail before F h) against the shipped rule, paired, calibrated against the realised closes, on the scout tape. Registered 2-Sep 09:30Z. READ: run it with `--fresh` at n>=30 fresh walked closes (~4.7 closes/day -> ~10 days) or on 16-Sep, whichever first. CONFIRMED -> register `TT_MIN_HOLD_H` as a caged shadow-lane lever at the confirmed floor, its own entry, era untouched (an exit bar is not in the (jf) signature); REFUTED -> record it; else record and re-arm once.

_Still open because:_ the fresh sample has not accrued; the read at registration is in the (wy) changelog entry. Declared limit: the replay form of this test (a floor's effect on the ENTRIES it blocks by holding a slot) needs the up-resolver, which this environment's egress refuses — run that half in the container when the walk confirms.

### `mum-noncrypto-sleeve-preregistered-read`  ·  owner: **session**
👩 mum's NON-CRYPTO sleeve read 7 closes at −0.383%/trade live (−0.540% twin), 5 of 7 `max_hold` losers on both arms — and the SAME DAY an adversarial review REFUTED the mechanism that motivated it and the bar that would have acted on it. The closed-hours story is dead (0 of 10 max_hold losses expired before the underlying reopened; entry-while-OPEN is WORSE). The 7 closes are 4 ENTRY DAYS (3 share one `opened_at`), the upper bound is <=0 only on the iid read (+0.170% day-clustered), and the raw −0.98pp class gap FLIPS to +0.18pp under a close-day effect. PRE-REGISTERED (I21), corrected rule: run `scripts/study_mum_noncrypto_sleeve_2026-09-02.py` at G>=10 distinct ENTRY DAYS on the live arm or on 16-Sep, whichever first. CUT (set FAMILY_NONCRYPTO_EXCLUDE='freqtrade-mum:*' — the whole class, so the act matches the graded population — on mum-live AND family-lighter-shadow so the control twin moves with her) ONLY if the DAY-CLUSTERED upper bound <= 0 AND the sleeve is worse than CRYPTO on matched close-days. KEEP if the sleeve mean > 0. The twin is REPORTED, not a condition. Anything else re-arm once — and note the supported mechanism is a vol/bracket mismatch whose remedy is a class-aware ladder (I26 feed-it), measured on its own, NOT this cut.

_Still open because:_ G is 4; the floor is 10 entry days. The mechanism (`noncrypto_exclude`, per carrier, ENTRY-ONLY, inert at '') shipped with the registration so the cut is one env, not a build, if the corrected read ever passes.

### `allocation-clamp-is-a-per-position-bound-doing-per-book-duty`  ·  owner: **OPERATOR**
💰 fleet_allocation's [0.25, 4.0] clamp is a per-POSITION slippage bound being asked to do a per-BOOK job. **[(vj)] THE 4.0 ALARM THIS ROW USED TO CARRY IS WITHDRAWN — it was measured stale.** It read '💰 sits AT its 4.0 ceiling on 🌾 carry right now, delta_usd +13,500, $14,400 of gross on a $1,000 book'. Measured on the live payload 27-Aug: the MAXIMUM scale anywhere in the fleet is **1.594** (🙏 avo shadow) and carry sits at **1.272** ($1,271.75 target on a $1,000 book). (tz) replaced the winner-take-all split with a tilted flat prior, which made 4.0 structurally unreachable — so the row described the organ as it behaved BEFORE the fix that had already shipped. What survives is LATENT, not live: the ceiling still PERMITS a scale that breaches the 15% go-live drawdown bar, because maxDD is the one bar that is NOT clip-invariant ((hl) measured per-trade % invariance for the other five) — ⚖️ Counterweight breaches at 3.06x, inside the 4.0 ceiling.

_Still open because:_ the clamp is a capital-allocation policy and moving it moves money between books — an operator call (I16), not a session one. It is NOT urgent: nothing is near the ceiling today. **[(xj)] THE SESSION-DOABLE HALF THIS ROW NAMED IS DONE, AND THE ROW WAS FIVE DAYS STALE — it read 'what a session CAN do first is derive the per-book bound the drawdown bar implies and publish it beside the claim', which shipped at (vd) on 28-Aug as `fleet_allocation.dd_bound` and is LIVE on all 16 books. The stale row nearly caused it to be rebuilt.** What is actually left, measured on the live payload 2-Sep: 6 books bounded (incl. all three live arms — mum 3.75x, avo 1.5x), 1 declared NO_STOP_BY_DESIGN, and **9 living books with no bound at all**, so the shared ceiling governs them blind. (xj) built the drift guard `_STOP_BRIDGE` promised and never got (all 10 retyped stops verified correct, 6/6 mutations red both directions) and DECLARED the 9 as a shrink-only ratchet. Draining that backlog needs a per-book reading — a bleed stop is a genuine loss bound but whether it is the right input to 0.15/|stop| is a claim nobody has studied. The OPERATOR half is untouched: moving the clamp moves money between books (I16).

### `brain-mult-transition-oscillation`  ·  owner: **session**
The brain's `t` is computed on DOLLARS (`brain_stats.weighted_bucket` reads `profit_abs`), so a bucket MID-TRANSITION is a mixture of two clip scales: sd inflates against mean and `t` falls on a book whose edge has not moved. Predicted shape: a bucket that clears a rung steps back down a rung within ~10 closes, then climbs again. A uniform scale is invariant, so there is no runaway — this is a transient limit cycle, damped by the 14d decay and the 3-run streak gate.

_Still open because:_ the fix is hysteresis in the PUBLISHER (`qualify_v3` is stateless; the held rung lives in bot_learn's `mult_streaks`), and rewriting the brain's ladder on the same day 13 consumers were wired to it is the untested-rewrite-of-an-authority the doctrine forbids. It is now MEASURABLE for the first time — every close carries its `brain_mult` — so the next pass tests the prediction against real closes instead of a model.

### `ceiling-slots-georgia`  ·  owner: **session**
**(sv) ANSWERED THE CENSUS QUESTION AND THE ANSWER RETIRES THE HEADLINE.** This row read '83.5 DAYS at 0.5 of 5 slots, 7.6 days at full occupancy — an 11x speed-up'. Measured: her mean hold is **2.6h**, so occupancy = closes/day x 2.6/24 and FIVE slots need ~46 opens/day. Her signal supplies 40.9/day at best. **Full occupancy is unreachable by construction, and it was never the lever — CLOSES are.** She is flat 68.4% of the time not because something refuses her but because she exits in under 3 hours. (sv) took the one gate that cut closes for no quality reason (the 2/h throttle, +0.633pp in favour of the entry it refused, six splits) from 2 -> 3.

_Still open because:_ the step is DELIBERATELY one notch: rank 3 has n=1 in her whole life because the cap was 2, so everything above it is extrapolation. `entry_rank` now rides every close, so the next step is graded from a query — re-run `scripts/study_georgia_entry_rank_2026-08-22.py` once rank-3 rows exist and take 3 -> 4 only if it holds. [26-Aug (tm) pass]: rank-3 today reads n=3, 0% win, crash-dominated — decides NOTHING either way; 3 of the six (sv) controls have flipped negative, so the 3->4 step is REFUSED on current data and 3->2 reversion equally unsupported. The OTHER half is now MEASURED AND CLOSED: the calibrated LAG-1 hold/roi sweep (n=100 paired, both intrabar conventions) put every widening below the harness's own +0.246pp calibration error, roi-x2's gain is h2-NEGATIVE, trail-only sign-disagrees between conventions, and the 1440m max_hold fired 0 of 207 closes ever — exits are a dead dial on this book; the mean lever is ENTRY quality (rank1 +0.023% vs rank2 +0.656% on her own ledger).

### `ceiling-capital-inversion`  ·  owner: **OPERATOR**
Capital sits in INVERSE proportion to measured edge: the two worst books run at 88-102% of capacity (⚖️ Counterweight -1.433%, 🛢️ Garrett -1.460%) while 👩 mum at +4.658%/trade is capped at FOUR slots and 🙏 avo at +1.085% uses 40% of six. `fleet_allocation` computes the right answer and is ADVISORY with consumers on three funding books only.

_Still open because:_ moving capital between books is an operator call, not a session one — the organ already ranks it honestly (I16).

### `books-should-declare-themselves`  ·  owner: **session**
18 of 19 living books do not publish `extra.thesis` — their design lives in `fleet_manifest`'s bridge table instead of on the row. `design_for` already prefers a book's own publication, so each migration is one publish-site edit and the manifest entry goes quiet on its own.

_Still open because:_ 18 bot edits and 18 deploys; do it a book at a time on the next deploy each one earns for another reason.

### `unmeasurable-lever-backlog`  ·  owner: **session**
30 registered levers still have no QUANTITIES spec — no recorded quantity to profile them against. The ratchet in audit_lever_measurability stops the pile GROWING; draining it is per-lever work: record what the knob cuts, then spec it.

_Still open because:_ each one needs the bot to stamp its own governing quantity first (the (sk) give_back/mae_ret pattern).

### `georgia-t-bar`  ·  owner: **session**
🔮 georgia is 5 of 6 go-live bars, failing only t. [MEASURED 26-Aug (tm) pass]: the weak t is ONE real 3-leg flash-crash batch (22-Aug 05:11Z: XRP -16.4/NEAR -19.5/TRX -3.0) = 73.5% of cluster variance — drop those 3 rows and t_cluster reads +2.51. Tail CONTROL cannot clear the bar honestly (at the live arm's own measured -7.17% crash fill for a -5% stop, t_cluster caps at ~1.40), and the stress-metric entry pause is REFUTED on the fleet's own instrument (scout stress read 8.6bps at the 05:00:33 entry vs the taker's 15bps bar; the 11.8 peak came 13 MINUTES after the dump started). Exits are a dead dial (see ceiling-slots-georgia). What remains is ENTRY QUALITY: the crash entry rode a +7.5%-in-50-min parabolic spike, and rank1 entries earn +0.023% vs rank2's +0.656%.

_Still open because:_ [26-Aug (tp)]: the parabolic-extension veto was RUN and REFUTED-AS-OVERFIT, adversarially confirmed — the best cell's whole effect is the three crash rows; ex-crash it forgoes $+10.17 of winners and refuses 73% of trend_breakout's supply (I7); random-veto null P~0.10, forced-kept P=0.0002 / conditional P=0.37. BOTH her dials are now measured dead (exits at (tm), the entry filter at (tp)). What remains: (1) the rank1-vs-rank2 gap (+0.55pp, NOT explained by extension — corr −0.050) gets its own pre-registered study on fresh closes once rank-3 stamps accrue; (2) her live arm accrues under the (tm)-fixed policy — time, not tuning.

## Shipped today (105 commit(s), entries (wg), (wl), (wm), (wn), (wo), (wp), (wq), (wu), (wv), (wx), (wy), (xc), (xd))

- `b7ab9b9` (xu) pre-mutation
- `3a60488` [deploy-live] (xu) _run leaked every coroutine it refused — a prerequisite for main's own deferred-fill retry; plus (xx) the adopted purge, (xv)/(xw) two corrections in place (#281)
- `18ee037` (xt) resolve the fills the governor declined: live execution was measured on a non-random 42%
- `06d546d` (xs) the taker's gate census: 23 of 24 tickets died before (uo)'s counter
- `069d0eb` (xr) the declared-key check scans the whole loop — mutation round 2 found it blind to tickets_in
- `a741244` (xr) the taker's gate census: 23 of 24 tickets died before (uo)'s counter
- `0dc874b` (xr) the stuck-flatten page: a halted book that cannot close is loud in 30 min instead of never
- `dd57efb` [deploy-live] (xo) mum's halt could not flatten a 1000-market — 84% of a live book left unmanaged; plus (xp) the measured stop ceiling, (xq) adopted legs are not evidence, (xl) her dip-velocity band (#272)
- `decd8ee` Merge PR #280: (xj) the drift guard _STOP_BRIDGE promised in writing and never got — plus a carried row that was five days stale
- `9f0f186` Merge origin/main (xi) into the (xj) branch
- `cb4cc5d` (xj) the drift guard _STOP_BRIDGE promised in writing and never got — plus a carried row that was five days stale
- `988e40c` Merge PR #279: (xi) the check ran and came back positive — and my own predicate for it was wrong
- `578fa14` (xi) the check ran and came back positive — and my own predicate for it was wrong
- `d6626e9` Merge PR #278: (xi) the Railway delete is a platform limit, not a permission one — harm neutralised, reason measured
- `a0361e5` (xi) the Railway delete is a platform limit, not a permission one — harm neutralised, reason measured
- `26feade` Merge PR #276: (xh) the suite's 8-red floor was the container, and finding that surfaced a live-deploy marker lost to a squash merge on a real-money book
- `cbfcdb6` (xh) a live-deploy marker does not survive a squash merge — measured on a real-money book, closed executably
- `8b174ba` (xh) the local suite had a standing floor of 8 reds that were not the tree's — a SessionStart hook installs the repo's own declared deps
- `98f0a3d` [deploy-live-mum] (xf)(xg) mum's gross 3.75x and her halt-aware entry gate (#271)
- `9a667f7` (xe) One position, two spellings: a 1000-market's mark arrived venue-spelled and the margin block asked fleet-spelled (#275)
- `72cc51a` Merge PR #274: the judge's serial lane could not promote, by construction — a drift guard sound for one entry file in two services became a permanent block when the lane moved to two images (xd)
- `790ec1f` (xd) drop an unused import from the cross-image drift test
- `c8684ad` (xd) The judge's serial lane could not promote, by construction: a drift guard sound for one entry file in two services became a permanent block the day the lane moved to two images
- `f529d02` wip3
- `a992b9c` wip2
- `6b60e4d` wip: cross-image arm drift (pre-mutation)
- `4d1de6b` Merge PR #266: (xb)/(xc) the edge audit's last items, then both judgement numbers calibrated optimally
- `b2b7d8e` HANDOFF regenerated after merging main (xc)
- `cbf6f43` Merge origin/main into the calibration branch: #270's (wz) readback
- `93a77d1` HANDOFF regenerated after merging main (xc)
- `c1f3cc6` Merge origin/main into the calibration branch: (wz), (xa) and a second (wy) landed first; this branch's entries are (xb) and (xc)
- `1af3ebc` Merge PR #270: (wz) readback — shadow budget 26 published, the proposals heartbeat's first beat, six mum offspring queued
- `79d2f1d` Calibrate optimally with findings (xb): the live lane's margins are derived from each comparison's own noise at the fleet's critical value, the book baseline excludes the motivating window, the shape monitor pages at the exact minimum-total-error boundary
- `106259f` (wz) read back on the live bus: shadow budget 26 published, the proposals heartbeat's first beat, six mum offspring queued
- `80ef8b0` [deploy-live-mum] Merge PR #268: (xa) mum's 1000-market legs keep their bracket — positions read in one spelling, untracked legs adopted into stop/roi/max_hold
- `9115dac` Merge remote-tracking branch 'origin/main' into claude/real-money-performance-5irang
- `1c37d6c` Merge PR #269: (wz) the shadow long budget is the cohort's own cap sum (26) — the judge's control twins stop being vetoed on paper their live arms never see
- `476a4e9` Merge remote-tracking branch 'origin/main' into claude/real-money-performance-5irang
- `5175109` (wz) The shadow long budget is the cohort's own cap sum (26 = mum's twin 12 + avo's twin 6 + taker 8), pinned to the books' caps — the judge's control twins stop being vetoed on paper their live arms never see
- `b7cd24b` Mum's real-money 1000-market legs lose their bracket (wz): positions read in one spelling, untracked legs adopted into stop/roi/max_hold — driven tests, 3/3 mutations red
- `da15417` Merge PR #267: (wy) run 2 through 4 — two pre-registered studies, the incubator on the judge's lane, the organ board's two flags closed
- `34e33ad` CodeQL hygiene on (wy): four file reads through with-blocks, one constant comparison dropped from a test assertion
- `1b0a4e1` (wy) Run 2 through 4: two pre-registered studies from the edge audit (the taker's 4h hold floor already excluded on its own entries), the incubator breeds for the judge's lane, and the organ board's two flags close
- `5cc2a88` HANDOFF regenerated after merging main (wy)
- `31011bc` Merge origin/main into the calibration branch: main's (wx) landed first, this entry moves to (wy)
- `4a7e809` HANDOFF regenerated after the (wx) calibration
- `fb25313` Calibrate the two numbers (wx) left as judgements: the I25 margin is re-measured and stands, the shape monitor fires in sampling-noise units against the fleet's own claim bar
- `8f90426` HANDOFF regenerated at session end (save)
- `39311fc` The douglas guard spares his tenant (wx): scope by BOT — bezos is a variant of the retired engine and was idled ~3h; retirement scope is chosen by a module's importers
- `2860c20` Merge PR #265: (ww) readback — family-shadow-stale-writer closed on the feed
- `1e726a3` HANDOFF regenerated after merging main (wx)
- `42d438c` Merge origin/main: #264 (ww) landed under the follow-up branch; the entry keeps (wx)
- `fdb7182` The edge audit's last four items leave the prose: kelly's read is a docket deferral, mum's shape has a monitor, streaks are judged against chance, I25 reaches the live grader's margin (wx)
- `39a45ea` The closing note cites (ww), the entry it belongs to — no phantom letter
- `bf47978` Close family-shadow-stale-writer on the feed readback: family rows on 97dbe3986551/15, mum's 12-position book publishing, georgia-v3's first row
- `bd524a5` [deploy-live] Merge PR #264: (ww) proceed with everything in the organ review — docket calls reconciled with the (wt) slate, cage re-decided, mum judge lane, weekly organ board
- `6b24cc1` test_mum_census_both_terms follows the census series through (wv)'s one builder — red on main since the extraction, healed here
- `8bb645f` Merge origin/main: (wv) landed the family publish fix — my entry moves to (ww) and its stale-writer paragraph cites the root cause
- `3992544` The dashboard's georgia hole (wv): spend_extra's b.bot killed every family publish for five days behind a stale Railway writer — one builder, driven for every book, publish failures now log
- `085a748` Merge origin/main: reconcile with the (wt) September slate and the (wu) rails — georgia's shadow retirement withdrawn (deferred to her 10-Sep read), duplicate guards dropped for the slate's, roster re-aims reverted, letter (ws)->(wv)
- `9c3b2cb` Merge PR #263: the two sizing rails from the edge audit, reshaped to bite only on measured harm; the brain's expansion floors measured and kept (wu)
- `ab465ba` HANDOFF regenerated after the third re-merge (wu)
- `07adc37` Merge origin/main a third time: the (wt) September slate landed; the rails entry keeps (wu)
- `922016c` The September slate (wt): five I17 retirements on the grader's own verdicts (garrett, douglas, farmer-shadow, nav-cook, grimes), georgia v1 deferred to her pre-registered 10-Sep read, trail-blazer-live stopped — Eamon's delegated docket act
- `643bc6e` CodeQL hygiene on (wt) and the merged (wp): one import style for the family module, no dead binding, file reads through pathlib, explanatory comments in the two empty excepts, redundant inner imports dropped
- `83bcbfd` CodeQL hygiene on the floors study: the --out write goes through a with-block (wu)
- `cd8410c` Port the selftest registration for scripts/study_taker_divergence_stop_2026-09-02 (wu)
- `7544d84` (wt) the family shadow host is stuck on 28-Aug code: carried as an operator act with the stamp to read back
- `b0b2340` HANDOFF regenerated after the second re-merge (wu)
- `5724989` Merge origin/main again: main took (wq)-(ws) and holds (wt) in flight, so the rails entry moves to (wu); the carried list is main's minus the closed floors row
- `bd1ad2a` Merge remote-tracking branch 'origin/main' into claude/bot-system-health-check-q0hko4
- `b7599d4` Renumber (ws) -> (wt): main took (ws) for the sentinel's graded bar while this pass was open
- `1b12ace` HANDOFF regenerated after closing the floors row (wq)
- `7dd38b4` The brain's expansion floors, measured before the rails merge: floors KEPT with evidence, the entry's two false sentences corrected in place, the carried row closed (wq)
- `21283ad` (ws) Proceed with everything in the organ review: five docket retirements, the incubator cage re-decided beside (wr)'s clock split, the judge's lane moved to mum, and a weekly organ board
- `6639f1e` The sentinel earns its fear (ws): one graded bar (n>=10, hit>=0.55) for BOTH proposal directions — a below-coin-flip playbook can no longer propose the crouch
- `7ab31ed` The clock split (wr): the breakout trend exit gets its own BRK_MAX_HOLD_H — taker.max_hold_h steers only the divergence bracket, AST-pinned, behaviour-neutral at ship
- `694f7c6` HANDOFF regenerated after merging main into the rails branch (wq)
- `27a3d7b` Merge origin/main into the rails branch: #262 took (wp), so the rails entry moves to (wq) and every citation moves with it
- `7cb0c7d` The backlog drained (wq): both live books claim-justified (ratchet 2->0), Counterweight fresh-read tripwire, minvol wired into the tp study, the (sk) breakoutup pins re-decided on a sighted gate, divergence stop priced (a refusal)
- `faf9bc8` [deploy-live] Merge PR #262: (wp) support-system deep dive — cohort long budget, held-basket margin, shadow scan-order parity, living shortfall pair
- `2165a41` CodeQL hygiene on the rails: three NaN checks through math.isnan, a commented fallback except, an unused test import (wp)
- `f58ba46` Merge remote-tracking branch 'origin/main' into claude/bot-system-health-check-q0hko4
- `7227ca0` Renumber (wo) -> (wp): main took (wo) for the edge audit while this PR waited on CI; citations moved with it (wp)
- `a0f3426` Regenerate HANDOFF — I11's regenerate-last half (wp)
- `3aff7bc` The two sizing rails from the edge audit, reshaped to bite only on measured harm: a book past its drawdown bar is scaled, a book whose era bound is measured at zero is not levered (wp)
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

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

