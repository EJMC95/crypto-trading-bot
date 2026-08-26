# HANDOFF — start here

_Generated 2026-08-26 13:20 Sydney (03:20Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

## Carried — pick these up FIRST (I11)

### `funding-studies-inherit-the-rank-universe`  ·  owner: **session**
(su) found `backtest_funding_lighter` selects its universe by RANK while the live bot filters on an absolute $10M/day floor only 11 of 212 markets clear — so its verdicts were measured on books the book refuses, and the gate table it produced INVERTS between universe 25 and 50. The loader now carries volume and `study_farmer_gate_minvol_2026-08-22` replays the honest population. **Four other scripts reuse that loader and have not been re-derived**: study_farmer_take_profit, backtest_farmer_breadth_lighter, backtest_funding_persistence and backtest_xsect_funding_lighter.

_Still open because:_ each cites its own verdict in a header that other work reads as settled ('do not re-test what a script header rejects'), so re-running them is not optional tidying — it is checking whether four standing refusals were measured on the wrong books. Cheap now that the tape carries volume; nobody has done it.

### `farmer-cap-collapses-slots-under-conviction`  ·  owner: **OPERATOR**
💸 the LIVE Farmer's notional cap turns a bigger clip into FEWER BETS. Live-verified: clip $30, cap $150, 5 slots, equity $194.28 — at brain 1.0x it holds 5 positions for $150 gross; at 2.0x it holds TWO ($120); at 3.0x it holds ONE ($90). Gross FALLS as conviction rises, on a funding book whose edge is breadth. (sp)'s trim fixes the outright halt at 6.7x; it cannot fix this, because a fixed cap and a bigger clip are arithmetically the same constraint.

_Still open because:_ the resolution is a cap that scales with equity rather than a fixed dollar env, or an explicit concentration policy — and SafetyRails caps are OPERATOR-ONLY by design, which is the one limit neither permission nor a doc edit moves. What a session can do is measure whether 5 small bets beat 1 large one on this book's own ledger; nobody has.

### `allocation-organ-4x-on-carry`  ·  owner: **OPERATOR**
💰 fleet_allocation sits AT its 4.0 ceiling on 🌾 carry right now (`delta_usd: +13,500` on a $1,000 book, the fleet's only measured claim), and carry runs 12 slots x $300. That is **$14,400 of gross on a $1,000 book** from the allocation organ alone, before the brain says anything — 14.4x equity on a book whose modelled `HEDGE_COST * notional` is calibrated at $300 a position. (sp)'s brain bound is derived from carry's CONSTANTS precisely so it does not double this; it also does not fix it.

_Still open because:_ the organ's 0.25-4.0 clamp is a capital-allocation policy and moving it moves money between books — an operator call (I16), not a session one. What a session CAN do first is measure whether 4.0 on a 12-slot book was ever intended, or whether the clamp was written for a 4-slot one.

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

### `live-taker-divergence-stop-unpriced`  ·  owner: **session**
The LIVE taker's short-divergence stop reads +28pp reclaim excess and +2.10% held at 24h over n=22 — a measured SIGNAL with no priced VALUE. lighter_ticket_replay is the calibrated instrument; a candle walk is not (it has no short branch).

_Still open because:_ real-money row: measure and hand over, never hand-set.

### `georgia-t-bar`  ·  owner: **session**
🔮 georgia is 5 of 6 go-live bars, failing only t. [MEASURED 26-Aug (tm) pass]: the weak t is ONE real 3-leg flash-crash batch (22-Aug 05:11Z: XRP -16.4/NEAR -19.5/TRX -3.0) = 73.5% of cluster variance — drop those 3 rows and t_cluster reads +2.51. Tail CONTROL cannot clear the bar honestly (at the live arm's own measured -7.17% crash fill for a -5% stop, t_cluster caps at ~1.40), and the stress-metric entry pause is REFUTED on the fleet's own instrument (scout stress read 8.6bps at the 05:00:33 entry vs the taker's 15bps bar; the 11.8 peak came 13 MINUTES after the dump started). Exits are a dead dial (see ceiling-slots-georgia). What remains is ENTRY QUALITY: the crash entry rode a +7.5%-in-50-min parabolic spike, and rank1 entries earn +0.023% vs rank2's +0.656%.

_Still open because:_ the one unbuilt candidate with evidence behind it is a parabolic-extension entry veto (price vs its own recent range at entry) — book logic, backtest-first on her own ledger + candles; nobody has run it. The (tm) parity fix means her live grade now accrues under her actual policy, so the live arm's fresh era is the other thing time has to deliver.

### `carry-garrett-ranking-collision`  ·  owner: **OPERATOR**
🌾 carry's measured-depth gate now reaches the whole of 🛢️ Garrett's [0.1M, 2M) band, and Garrett's own (pl) measurement found 6 of 6 of its top-ranked candidates are >=20% APR — so carry is a rival for exactly the supply Garrett ranks first. A RANKING collision; audit_book_overlap's axes (apr x vol x class) cannot express it.

_Still open because:_ declared in KNOWN_CELL_COLLISIONS; the call is the same ~12-Sep decision point as the rest of that component.

## Shipped today (25 commit(s), entries (tj), (tk), (tl), (tm), (tn), (to))

- `ff22aa2` The fixed-dollar-cap class closes: EQUITY_SCALED_CAP, opt-in, floor-preserving, fail-safe dark (to)
- `023bdf6` Merge PR #225: the avo cap+halt one-shot goes the way of every provisioner (tn)
- `c71c4b8` The avo cap+halt one-shot goes the way of every provisioner — receipts on the row (tn)
- `c188e13` Merge PR #224: georgia's live exit parity (veto + ratchet), mum's census split, avo cap+halt one-shot (tm, tn)
- `10d7a02` Merge remote-tracking branch 'origin/main' into claude/real-money-bot-optimisations-d42zko
- `f355361` The georgia carried rows record their 26-Aug measurements; the equity-scaling cap becomes a named build decision (tm)
- `14087d8` Regenerate the handoff after the 26-Aug expansion research
- `4effb9e` Extract holdwatch_accumulate: the mutation round proved the dispersion counter was unreachable from any test
- `5f7c2fe` 🪁 band-kelly's holdwatch publishes its dispersion — the field that says the exit is the leak could not say it was significant
- `8f2718d` Pin the WIRING, not just the helper: a mutation round showed the selftest missed the real defect
- `7937778` The divergence detector was subtracting two different books, and two live rows had no check at all (daily review 26-Aug)
- `f6d5b6b` The winners' referee was grading halt EVENTS as trades on both real-money books (daily review 26-Aug)
- `0c37554` One-shot cap+halt parity for avo's live service (registered from main; deleted after use) (tn)
- `2d4444c` [deploy-live-georgia] [deploy-live-mum] Georgia's live arm runs her own exit policy at last — breakout veto + trailing ratchet ported; mum's census names the uptrend block (tm)
- `77eeef4` The georgia attestation one-shot goes the way of every provisioner (tl)
- `b90deb5` Georgia's manual P&L attested (-26.4, read back on the row) — and the pair registry's service name corrected by the act of aiming at it (tl)
- `e5535a4` One-shot attestation for georgia's manual P&L (registered from main; deleted after use)
- `b9515b6` The duplicate attestation one-shot goes the way of every provisioner — the (tk) session already executed it
- `fc24edf` One-shot attestation workflow for avo's manual P&L (registered from main so dispatch resolves; deleted after use)
- `2db5b3a` The attestation one-shot goes the way of every provisioner; the (tk) record carries its receipts (tk)
- `1ebbb75` Merge PR #220: the standing live-bot audit, nav-cook un-muted, the attestation one-shot registered (tk)
- `30dba6a` One-shot attestation config + the (tk) execution record: Eamon's full-permission morning (tk)
- `b63035a` Merge origin/main: (ti)/(tj) in; the standing-audit entry renumbers (th)->(tk) on the merged entry's seniority
- `7e85c73` Merge PR #222: the census's freshness reads the publisher's shape (tj)
- `9d8876d` The census's first live run catches its own fixture bug — freshness now reads the publisher's shape (tj)

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

