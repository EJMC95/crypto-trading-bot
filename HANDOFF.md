# HANDOFF — start here

_Generated 2026-09-02 15:01 Sydney (05:01Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

## Carried — pick these up FIRST (I11)

### `funding-studies-inherit-the-rank-universe`  ·  owner: **session**
(su) found `backtest_funding_lighter` selects its universe by RANK while the live bot filters on an absolute $10M/day floor only 11 of 212 markets clear — so its verdicts were measured on books the book refuses, and the gate table it produced INVERTS between universe 25 and 50. The loader now carries volume and `study_farmer_gate_minvol_2026-08-22` replays the honest population. **Four other scripts reuse that loader and have not been re-derived**: study_farmer_take_profit, backtest_farmer_breadth_lighter, backtest_funding_persistence and backtest_xsect_funding_lighter.

_Still open because:_ the VERDICTS are now re-derived and recorded in each header; what is still open is the WIRING — these scripts keep selecting by rank, so the next person to run one gets the rank-selected answer unless they pass the floor by hand. Closes when study_farmer_take_profit uses `minvol_entry_ok` itself.

### `allocation-clamp-is-a-per-position-bound-doing-per-book-duty`  ·  owner: **OPERATOR**
💰 fleet_allocation's [0.25, 4.0] clamp is a per-POSITION slippage bound being asked to do a per-BOOK job. **[(vj)] THE 4.0 ALARM THIS ROW USED TO CARRY IS WITHDRAWN — it was measured stale.** It read '💰 sits AT its 4.0 ceiling on 🌾 carry right now, delta_usd +13,500, $14,400 of gross on a $1,000 book'. Measured on the live payload 27-Aug: the MAXIMUM scale anywhere in the fleet is **1.594** (🙏 avo shadow) and carry sits at **1.272** ($1,271.75 target on a $1,000 book). (tz) replaced the winner-take-all split with a tilted flat prior, which made 4.0 structurally unreachable — so the row described the organ as it behaved BEFORE the fix that had already shipped. What survives is LATENT, not live: the ceiling still PERMITS a scale that breaches the 15% go-live drawdown bar, because maxDD is the one bar that is NOT clip-invariant ((hl) measured per-trade % invariance for the other five) — ⚖️ Counterweight breaches at 3.06x, inside the 4.0 ceiling.

_Still open because:_ the clamp is a capital-allocation policy and moving it moves money between books — an operator call (I16), not a session one. It is NOT urgent: nothing is near the ceiling today. What a session CAN do first is derive the per-book bound the drawdown bar implies (the `GROSS_X_MAX = 0.15/|stop|` shape (sr) used on avo) and publish it beside the claim, so the ceiling stops being a single number shared by books with different stops.

### `brain-mult-transition-oscillation`  ·  owner: **session**
The brain's `t` is computed on DOLLARS (`brain_stats.weighted_bucket` reads `profit_abs`), so a bucket MID-TRANSITION is a mixture of two clip scales: sd inflates against mean and `t` falls on a book whose edge has not moved. Predicted shape: a bucket that clears a rung steps back down a rung within ~10 closes, then climbs again. A uniform scale is invariant, so there is no runaway — this is a transient limit cycle, damped by the 14d decay and the 3-run streak gate.

_Still open because:_ the fix is hysteresis in the PUBLISHER (`qualify_v3` is stateless; the held rung lives in bot_learn's `mult_streaks`), and rewriting the brain's ladder on the same day 13 consumers were wired to it is the untested-rewrite-of-an-authority the doctrine forbids. It is now MEASURABLE for the first time — every close carries its `brain_mult` — so the next pass tests the prediction against real closes instead of a model.

### `brain-mults-are-two-opinions-wide`  ·  owner: **session**
(so) wired every living book to the brain's stake multiplier, including both real-money rows — and on the day it shipped the brain had exactly TWO published opinions across twenty books (taker short-divergence 0.75, Counterweight long 0.75). The plumbing is done; the ORGAN is nearly silent, because a mult needs >=30 era closes AND >=3 consecutive runs and most books never reach the first. The open question is whether those floors are right now that the range is 6.7x either way: a floor calibrated for a 1.5x ceiling is not obviously the floor for a 6.7x one.

_Still open because:_ moving a brain floor changes what sizes EVERY book, real money included — it needs its own measurement (how many buckets would qualify at each floor, and what their realised expectancy was), not a judgement call.

### `taker-replay-blind-to-breakoutup`  ·  owner: **session**
lighter_ticket_replay refuses every breakout entry (`_up = False if lens == "breakout"`), so the scout tuner's gate cannot see the taker's ONLY living lens. (sk) pinned the cages shut against the resulting one-way ratchet; the DURABLE fix is to give the replay the taker's own breakoutup relabel via up_read(), after which the cage pins are a decision to re-make on evidence.

_Still open because:_ changes what the tuner's leaderboard measures — needs its own before/after on the recorded tape, not a refactor.

### `breakout-arm-inherits-reversion-clock`  ·  owner: **session**
bull_exit() hands the breakout TREND exit the reversion arm's MAX_HOLD_H. A rule built to let a winner run (no TP cap, wide stop, trailing give-back) is timed by a mean-reversion book's clock; 23-32 of 37 replayed exits are that clock, not the trail.

_Still open because:_ splitting it decouples the arm from a lever the rail actively moves, and the only evidence for 48h->96h died to leave-one-symbol-out (+0.78pp -> +0.07pp ex-HYPE).

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

### `taker-divergence-stop-unpriced`  ·  owner: **session**
🎫 the taker's short-divergence stop (SHADOW arm) reads +28pp reclaim excess and +2.10% held at 24h over n=22 — a measured SIGNAL with no priced VALUE. lighter_ticket_replay is the calibrated instrument; a candle walk is not (it has no short branch).

_Still open because:_ shadow book, so a session may measure AND act ((kd)); the reason it is open is that nobody has priced it — the replay is the instrument and it has not been run.

### `georgia-t-bar`  ·  owner: **session**
🔮 georgia is 5 of 6 go-live bars, failing only t. [MEASURED 26-Aug (tm) pass]: the weak t is ONE real 3-leg flash-crash batch (22-Aug 05:11Z: XRP -16.4/NEAR -19.5/TRX -3.0) = 73.5% of cluster variance — drop those 3 rows and t_cluster reads +2.51. Tail CONTROL cannot clear the bar honestly (at the live arm's own measured -7.17% crash fill for a -5% stop, t_cluster caps at ~1.40), and the stress-metric entry pause is REFUTED on the fleet's own instrument (scout stress read 8.6bps at the 05:00:33 entry vs the taker's 15bps bar; the 11.8 peak came 13 MINUTES after the dump started). Exits are a dead dial (see ceiling-slots-georgia). What remains is ENTRY QUALITY: the crash entry rode a +7.5%-in-50-min parabolic spike, and rank1 entries earn +0.023% vs rank2's +0.656%.

_Still open because:_ [26-Aug (tp)]: the parabolic-extension veto was RUN and REFUTED-AS-OVERFIT, adversarially confirmed — the best cell's whole effect is the three crash rows; ex-crash it forgoes $+10.17 of winners and refuses 73% of trend_breakout's supply (I7); random-veto null P~0.10, forced-kept P=0.0002 / conditional P=0.37. BOTH her dials are now measured dead (exits at (tm), the entry filter at (tp)). What remains: (1) the rank1-vs-rank2 gap (+0.55pp, NOT explained by extension — corr −0.050) gets its own pre-registered study on fresh closes once rank-3 stamps accrue; (2) her live arm accrues under the (tm)-fixed policy — time, not tuning.

### `carry-garrett-ranking-collision`  ·  owner: **OPERATOR**
🌾 carry's measured-depth gate now reaches the whole of 🛢️ Garrett's [0.1M, 2M) band, and Garrett's own (pl) measurement found 6 of 6 of its top-ranked candidates are >=20% APR — so carry is a rival for exactly the supply Garrett ranks first. A RANKING collision; audit_book_overlap's axes (apr x vol x class) cannot express it.

_Still open because:_ declared in KNOWN_CELL_COLLISIONS; the call is the same ~12-Sep decision point as the rest of that component.

## Shipped today (40 commit(s), entries (tg), (wb), (wc), (wd), (we), (wg), (wh), (wi), (wj), (wp))

- `7227ca0` Renumber (wo) -> (wp): main took (wo) for the edge audit while this PR waited on CI; citations moved with it (wp)
- `dec9ad4` (wo) the support-system deep dive: cohort long budget, held-basket margin, shadow scan-order parity, a living shortfall pair, Counterweight's date
- `09e5fc4` (wn) the CI-liveness pager cried wolf 1-in-10: heartbeat rides push CI, LATE warns at 4h, DARK pages at the measured 12h
- `4e65d49` Merge PR #261: CodeQL hygiene on the #257 suites, with its dated (wg) note
- `65d67c5` the changelog gate counts tests/ as bot-affecting — the CodeQL hygiene pass gets its dated note in (wg)
- `9f091f0` (wm) — mum pre-registered on the winners' docket (I21); the snapshot pin re-aimed per I26
- `c90e359` CodeQL hygiene on the #257 suites: an unused os import and an unclosed file handle
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

