# HANDOFF — start here

_Generated 2026-09-03 01:20 Sydney (15:20Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

## Carried — pick these up FIRST (I11)

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

_Still open because:_ the clamp is a capital-allocation policy and moving it moves money between books — an operator call (I16), not a session one. It is NOT urgent: nothing is near the ceiling today. What a session CAN do first is derive the per-book bound the drawdown bar implies (the `GROSS_X_MAX = 0.15/|stop|` shape (sr) used on avo) and publish it beside the claim, so the ceiling stops being a single number shared by books with different stops.

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

## Shipped today (8 commit(s))

- `d81f540` Merge remote-tracking branch 'origin/main' into claude/edge-radar-incubator-review-wjioye
- `96cd8a6` the halves default, the dropped cache line, and the crypto CONTROL sweep
- `66b37a7` C4's own metric was the artifact it existed to prevent — corrected to the aggregate
- `fd071e4` PRE-REGISTRATION: mum's class-aware ladder study, committed BEFORE the run
- `98f0a3d` [deploy-live-mum] (xf)(xg) mum's gross 3.75x and her halt-aware entry gate (#271)
- `f0f998e` CodeQL: drop the now-unused math import from the mum sleeve study
- `4f7189d` (xg) the grader published a false I17 exclusion; (xf) the mum sleeve mechanism is refuted and its cut rule rewritten
- `5497e71` Merge remote-tracking branch 'origin/main' into claude/edge-radar-incubator-review-wjioye

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

