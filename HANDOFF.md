# HANDOFF — start here

_Generated 2026-08-27 18:42 Sydney (08:42Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

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

## Shipped today (102 commit(s), entries (tq), (tr), (ts), (tt), (tu), (tv), (tw), (ua), (ub), (uc), (ud), (uf), (ug), (ui), (uj), (uk), (ul), (um), (un), (uo), (uq), (ur), (us), (ut), (uu), (uv), (uw), (uy), (uz), (va), (vb), (vc), (vj))

- `58304e3` Pin each retirement registry term against a stub (vj)
- `05a8429` Kill the survivor: pin BOTH retirement registries separately (vj)
- `a7396b8` A carried row outlived the book it was about, behind a predicate that could never fire (vj)
- `581d8cf` The bot card read five bot_pnl columns that do not exist (vj)
- `eac49ae` Close my own guard's keyword blind spot; renumber (vb) -> (vj) (vj)
- `e1adb62` Renumber (uz) -> (vb): both uz and va were taken on main mid-write (vb)
- `9888ce7` The mirror book's quarantine filter was a permanent no-op: bot/pair swapped (uz)
- `d7efafe` Regenerate HANDOFF (vc)
- `4a1569c` We win, we change it, it starts losing — measured as regression to the mean: a hot window is followed by -1.674pp with or without a change (vc)
- `5837e0c` Merge remote-tracking branch 'origin/main'
- `8e9d4b0` Georgia's entry cap 3 -> 5, graded on the uncensored population: rank 3 is her best entry, days-to-gate 344 -> 187 (vb)
- `9c79fdf` The judge never checked whether the control arm was alive: a ten-day-dead shadow row certified a pair idle (va)
- `80917b4` Regenerate HANDOFF (uz)
- `62488dc` Mum is slow not stuck: her RSI bar is the measured peak, the universe widening is refuted by resampling, and the tape fetches once (uz)
- `6dc2563` Pre-registration snapshot: georgia's entry-rank cap verdict bars, committed before any result exists (uy)
- `656fd01` Mum is SLOW not stuck, and her shipped RSI bar is the measured peak — widening past 32 costs expectancy (ut)
- `67145a2` The venue tape, fetched once: a durable cache of CLOSED bars — 1804x on re-run, 0 requests (ut)
- `a8dc14c` Record the inert-sort fix + correct (ts)'s order-independence claim in place; renumbered (uw) -> (uy) on a cross-branch collision (uy)
- `e89aff0` Kill the second survivor: pin the extractor's row scoping (uw)
- `67208d2` Close the mutation survivor: the contract test's roster must not be emptiable (uw)
- `34846c4` The (ts) sort was inert: _close_rank read the DB column, not the key the publisher emits (uw)
- `c03a5c1` Register audit_ledger_records' selftest — its own guard caught the omission on first CI, because the file was untracked locally (tw)
- `2cab26d` Merge remote-tracking branch 'origin/main'
- `dbb3fba` Georgia's exit is not the lever: 48 configurations on her own 212 entries, zero with a positive mean (ux, uw)
- `4cab777` [deploy-live] Events are not trades: the real-money books published phantom losses, and the class behind six defects gets its guard (tw)
- `b088376` Pre-registration snapshot: georgia's replay-vs-record reconciliation bars, committed before any result exists (uw)
- `6f99b16` Fidelity: evaluate georgia's rule on the live CandleCache's own 300-bar span, not a growing full-history prefix (uv)
- `2268279` The arms ran different entry policies and neither stamped it: max_entries_per_hour joins the shared stamp (uv)
- `088e70c` Pre-registration snapshot: georgia's entry-first verdict bars, committed before any result exists (uv)
- `54fa128` [deploy-live] The ':None' collision: a real losing trade was one halt event from being silently zeroed (tv)
- `37d14a4` Merge remote-tracking branch 'origin/main'
- `e344e09` Four refusals with evidence: (tr)'s cell verdicts survive the corrected estimator, 32 is at the optimum, georgia cannot diversify, the arity guard is not worth shipping (uu)
- `70a5968` Regenerate HANDOFF — I11's regenerate-last half, skipped at this session's start and stale by ten entries (ut)
- `2fcb366` Register audit_bus_contract in ENFORCED_AUDITS — a guard whose scan runs nowhere is the (gk) shape (ut)
- `82935a9` A cross-read payload without updated+ttl_sec is unconsumable by design: ratchet the class coin-quality opened (ut)
- `b15d4b1` Record the recorded-cost unlock + correct (ur)'s cost number in place; renumbered (us) -> (ut) on a cross-branch collision (ut)
- `8ffc68f` One owner for the coin-quality TTL: the test was recomputing the publisher's arithmetic, so halving the real TTL left it green (us)
- `0bea667` Close the mutation survivor: map mode must drop junk entries (us)
- `76d1bef` The fleet has recorded its own execution cost since 9-Jul and nothing could ever read it: coin-quality shipped with no updated/ttl_sec, so is_fresh judged it stale forever (us)
- `b225109` The dashboard was never wrong, it was behind: the live row refreshes between trading passes (us)
- `34e5909` The floor test read a bare env the module never reads (ur)
- `a529903` The live row refreshes between trading passes: near-live positions with no trading change (ur)
- `fe2fb56` The LUS cohort is REFUSED: the study that would have minted it reported the opposite of what it computed — a double negation swapped both side labels under a "we ran both directions" defence (ur)
- `7d498cc` The live trio goes back to 10x: Eamon's own 22-Aug ceiling restored, arithmetic published, mum's cap un-stranded (uq)
- `596f7a9` Renumber (ul) -> (up): fifth concurrent letter collision on this entry today
- `e57a106` Merge remote-tracking branch 'origin/main'
- `0d7370b` The wire goes in — and the headline that motivated it is refuted by its own pre-registration (ul)
- `f655643` Merge remote-tracking branch 'origin/main'
- `98948af` Renumber (uk) -> (uo): concurrent session took the letter on main
- `7502025` Repoint the taker's slot-census citations after the fourth letter collision: (uk) -> (uo)
- `5a82e8a` Pin what the widening DOES, not just its ceiling: a mutation round showed a silent revert to 30 left the suite green (un)
- `35ed688` Mum's bar widens to the measured cell: RSI_MAX 30 -> 32, the isolated-sliver trap recorded (un)
- `27051f8` The born-dark guard was vacuous: a substring the comment also carried (uk)
- `73acead` Mum's bar at 32 is supported and my pre-registration tested the wrong object: widening a threshold merges episodes and moves the entry (un)
- `b0019d8` A retired arm has no execution to diverge from: the Farmer's own retirement flatten was cutting all three live books' clips 25% (uk)
- `d99966c` The guard's own test fixture made it flag itself: assemble the citation instead of writing it literally (um)
- `bda40e0` The letter guard was reading other sessions' private worktrees: a session could be turned red by work that was not its own (um)
- `dfe80c7` Changelog for (uk) the taker slot census; (uj) renumbered to (ul) after a concurrent session took the letter
- `6ecdb47` The taker's slot cap is the one legal go-live accelerator and nothing counted what it refused: extra.slot_census (uk)
- `6f04ca2` Pre-registration snapshot: mum's bar-at-32 and max-hold verdict bars, committed before any result exists (uj-followup)
- `2256b25` Regenerate the handoff after the tuning wave (uj)
- `4ab3f4a` The live-shadow alert could not be verified at all: the 26-Aug pass fixed the evidence section and the helper, and left the verifier on the old signature (uj)
- `5b21a24` Four books tuned on their own ledgers, no retirements — and the card I shipped green yesterday was a time bomb (uj)
- `a8c4929` Georgia publishes her census: one of four books whose row could not answer stuck-vs-slow (uc)
- `f786461` Kill the stride survivor: a slice of one cannot see a stride (uc)
- `5fceb7b` The joint sweep was dark for 4.5 days of every orbit: stride the walk, coprime so coverage is untouched (uc)
- `4b00a89` Merge PR #233: one owner for cluster-robust t (ug), the redistribution refused (uh), main un-redded (ui)
- `56d2029` Regenerate HANDOFF.md — I11's read-first/regenerate-last half
- `e62af15` Correct (ui)'s timestamps in place: two of them were inferred, not measured
- `fc343b8` The redistribution is refused with the number nobody had run; and main's red-by-the-clock fixture is fixed (uh)(ui)
- `749e689` The cluster-robust t had three implementations, and both copies reproduced the (kg) degeneracy the owner was fixed for (ug)
- `cced85d` Merge PR #232: sniper entombment (ue) + listing side unsupported (uf) + allocation gate leak (ud)
- `259f0c5` The listing source has no measured side on its own band — the short's evidence lives in young's (uf)
- `2c38512` Register scripts/audit_stuck_vs_slow's --selftest — inherited RED from main
- `36e95c7` Repoint a changelog citation the (uc) -> (ue) renumber left dangling
- `bc38b72` The allocation's two halves do not add up: $1,151.66 is withheld by the era gate and returned to nobody (ud)
- `86c88bd` A surge/young pending symbol that stops qualifying is never offered again, so its give-up can never fire (uc)
- `e8360e5` Close the declared gap: breakoutup's self-veto now reaches the incubator's fitness (uc)
- `623e6eb` The incubator mutation round: the survivors were test gaps, and the code was right in every one (uc)
- `814329d` Declare the board's golive freshness bound — the (ia) exception, one consumer along (uc)
- `98da5f7` The incubator's fitness was not the taker's book — and the mechanism I published for it was REFUTED before it shipped (uc)
- `27529e2` Stuck is not slow: the discriminator is OCCUPANCY, and the docket was reading two full books as empty ones (uc)
- `acef2aa` The board stops widening on a sample the gate refuses; the judge sees georgia's real divergence; the pipe becomes legible (uc)
- `15eafa9` Merge PR #231: the era headline counted a field that did not exist yet (ua)
- `73723c8` The daily review counted 13 halt EVENTS as real-money trades — and the filter that fixed it read a JSONB key nothing has ever written (tu)
- `f860e5c` The era headline counted a field that did not exist yet — it could only ever read zero (ua)
- `093a44e` The winners' docket crowned a PROVEN winner on the window that generated the hypothesis (tt)
- `63e497e` Merge PR #207: the sniper flies the other way — per-source side, and the fade that justified it corrected in place (tx)(ty)(tz)(ua)(ub)
- `04b3c94` The debut fade is 76-83% CALENDAR: the side flip stands, its justification is corrected in place, four code defects fixed (ub)
- `471323a` Merge origin/main — main's (ts) and this branch's (tx)-(ub), both kept whole
- `56b0061` Renumber (ts)-(tw) -> (tx)-(ub): the THIRD collision on this branch's letters
- `2ba1b9c` The pair census scored each arm's OLDEST 30 closes: georgia's shadow stamped at 09:22Z and still read 0/30 (ts)
- `ecf1d2f` Credit Eamon by name in this branch's entries (tw)
- `0cc6715` The sniper was on the wrong side of its own thesis: a perp lists AFTER the spot hype (tw)
- `7aa9962` Merge origin/main (116 commits) — and my four letters collide a SECOND time
- `6a1b01d` The sniper's side is per-source: listing and young go SHORT on a measured debut fade (letter pending)
- `091cc2f` Merge PR #229: mum's bar widens to the measured cell — RSI_MAX 25->30, referee-confirmed (tr)
- `bbf0bf0` The risk-up one-shot goes the way of every provisioner — receipts verified on both rows (tq)
- `e40ca82` [deploy-live-mum] Mum's bar widens to exactly what was measured: RSI_MAX 25->30, the rescue tiers refused with their numbers (tr)
- `c284590` Merge PR #228: the (tq) risk-up one-shot registered — derived gross ceilings, scaled cap, halt parity
- `4b08462` Pre-registration snapshot: mum supply study verdict bars, committed before any result exists (tq)
- `eed4576` Register the (tq) one-shot: derived gross ceilings for avo+georgia, scaled-cap activation, halt parity

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

