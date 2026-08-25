# HANDOFF — start here

_Generated 2026-08-25 23:46 Sydney (13:46Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

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

_Still open because:_ the step is DELIBERATELY one notch: rank 3 has n=1 in her whole life because the cap was 2, so everything above it is extrapolation. `entry_rank` now rides every close, so the next step is graded from a query — re-run `scripts/study_georgia_entry_rank_2026-08-22.py` once rank-3 rows exist and take 3 -> 4 only if it holds. The OTHER half is untouched: her median hold is 1.9h against a 1440m cap, and nobody has asked whether letting winners run raises her mean instead of her count.

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
🔮 georgia is 5 of 6 go-live bars, failing only t (1.11 < 2.0) — the fleet's closest book to the gate. Its trailing stop is NOT the leak (reclaim 74% vs placebo 75%). Where its t comes from is the open question: raise the mean, cut the variance, or raise n.

_Still open because:_ unmeasured; the per-book audit was still running.

### `carry-garrett-ranking-collision`  ·  owner: **OPERATOR**
🌾 carry's measured-depth gate now reaches the whole of 🛢️ Garrett's [0.1M, 2M) band, and Garrett's own (pl) measurement found 6 of 6 of its top-ranked candidates are >=20% APR — so carry is a rival for exactly the supply Garrett ranks first. A RANKING collision; audit_book_overlap's axes (apr x vol x class) cannot express it.

_Still open because:_ declared in KNOWN_CELL_COLLISIONS; the call is the same ~12-Sep decision point as the rest of that component.

## Shipped today (20 commit(s), entries (tc), (td), (te), (tf), (tg), (th))

- `de35657` Merge PR #219: the second-in-command grant, and the improvement round's instruments on all three live books (tg)(th) [deploy-live]
- `c90675b` [deploy-live] The improvement round ships as instruments: halt geometry, the ruin gate's eyes, mum's real control arm, rank at the open, phantom hygiene, stop overshoot (th)
- `0cc99d5` Second in command: the judge and the rails join the delegated surface (tg)
- `378764a` Merge PR #218: mum's launch receipts, the stamp readback banked, and one Lucy on every surface (te)(tf)
- `b9bf742` One Lucy on every surface — the naming extends across Code, Cowork and the app (tf)
- `7828b11` The stamp readback banks mum's launch: bridges out, census live on all three real-money rows (te)
- `edf0837` Her name is Lucy (tf)
- `7975665` Launch receipts and the (lr) deletions: both one-shots go the way of every provisioner (te)
- `143bf45` Merge PR #217: weekly review, mum v2 LIVE on her own sub-account, the missing custom_exit, the swap's red-main discharge (tc)(td)(te) [deploy-live]
- `c10fc6b` The I22 census reaches the live host — the guard's first real catch was its own two variants (te)
- `460e6b9` The signer refutes the hyphen call; Eamon's launch config ships; the disarm is his button (te)
- `646d567` One-shot variables-only config for mum-live (deleted at activation)
- `7ec551a` The feed-followers, staged on the branch: mum declared in every live registry (te)
- `2b95ea9` One-shot provisioner for mum-live (registered from main so dispatch resolves; deleted at activation)
- `c31f98c` Mum goes live: the deploy rule activates with the service, keys never touch the repo (te)
- `2d48f0d` Regenerate the handoff after (td)
- `567c18e` Manual trades attested out of the bots' P&L; the taker's budget doubles under a guard-derived ceiling (td) [deploy-live]
- `4627aa8` The weekly review: what the week banked, where the money is, what broke (tc)
- `f27d4de` Mum v2 goes live-capable; the live host finally calls custom_exit (tc) [deploy-live-georgia]
- `9a5bd65` The swap's aftermath: six red tests, two blind organs, one erased census (tc)

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

