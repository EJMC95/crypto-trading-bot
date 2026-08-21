# HANDOFF — start here

_Generated 2026-08-21 15:52 Sydney (05:52Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

## Carried — pick these up FIRST (I11)

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
🔮 georgia is 310 closes from t=2.0 — 83.5 DAYS at today's 0.5 of 5 slots, 7.6 days at full occupancy. An 11x speed-up to decidability on the fleet's closest book to real money, costing zero expectancy. `scripts/ceiling.py` names it; what it does NOT say is whether her SIGNAL can fill those slots.

_Still open because:_ the ceiling is REACHABLE, not promised — the next step is her own census: what refuses the other 4.5 slots, the regime gate, the universe, or no signal at all.

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

## Shipped today (53 commit(s), entries (rt), (sb), (sc), (sd), (se), (sf), (sg), (sh), (si), (sp), (sq), (sr))

- `fb724f5` [deploy-live-taker] Avo 4 -> 5 slots: the ask was 6, the ledger refused it (sr)
- `79c80e9` Doctrine + handoff: Avo funded 3.7x, levered 1.4x on a derived drawdown budget (sr)
- `fc9ada7` Credit (sq)'s quote to Eamon, not the role — the ratchet was red on main
- `0365707` [deploy-live-taker] Avo: cap census + leverage on a derived drawdown budget (sr)
- `f5b89dc` Close the (sr) mutation survivor: nothing tested that leverage reaches the clip
- `bf45934` Avo: the cap census the deposit needed, and leverage on a derived drawdown budget (sr)
- `91f52fc` Fix the stale bots: neither was broken, and nothing they published could say so (sq)
- `c7003d4` Merge PR #213: the gross bound failed a second way — the call pattern, not the call (sp)
- `15b5809` The gross bound failed a SECOND way: the call pattern, not the call (sp)
- `30c5cae` [deploy-live] Merge PR #210: the brain reaches every book, and the rails now trim instead of refusing (sk–sp)
- `f9d6387` Correct the live numbers against the live rows, and name the sharper finding (sp)
- `7f34d28` Close the class the rail guard could not see: worst-case gross per book (sp)
- `78ffde3` The rails now actually dispose: trim, not refuse — and the brain's lookup is atomic (sp)
- `4119336` Merge remote-tracking branch 'origin/main' into claude/fleet-wide-bugs-improvements-64qta3
- `314f5a3` WIP: brain sizing reaches every book (letter pending)
- `f835deb` The brain's range reaches 6.7x, either way (si)
- `98f787a` Regenerate the handoff after the (sh) work (sh)
- `966abc4` Nineteen designs, one way of judging them — the manifest (sh)
- `e31648f` The ceiling becomes a measurement, and the brain's training wheel comes off (sh)
- `f0fba40` The never-recorded class, closed fleet-wide; and I11 finally has teeth (sg)
- `7217633` Merge PR #174: unchoke the fleet book by book — six improvements shipped, four refuted with numbers (ru–sj)
- `3730955` Renumber (sf) -> (sj): main took (sf) for the I22 entry while this waited on CI
- `16766ee` Garrett: three refutations and no knob turned — the stop is right, thinness is wrong, and the real problem is already on the docket (si)
- `89e1514` Ship two parked improvements: Georgia's stop on the tag left behind, and the Sniper's missing census (sh)
- `a28fc98` Un-blind the replay that gates every growth-rail actuator: 39% of the taker was structurally unreachable (sg)
- `e2ab51b` Renumber (sd) -> (sf): main claimed (sd)/(se) concurrently
- `f62ef32` Four books unchoked individually, each on its own number — and the fifth fix withdrawn (sd)
- `d071dec` Changelog: four entries at (ru),(rv),(rw),(rx) — fourth renumber after main ran to (rt)
- `c7f22ab` The class split becomes a published number, the docket deferral that expires, and the evidence saved as a calibration-gated study (ru, rv, rw, rx)
- `2758677` Merge PR #211: I22 — a book must spend the ecosystem, and two of this session's walls were imaginary (sf)
- `e34b6a2` The only path to more real money was rigged against ever promoting (sf)
- `50a051e` (sf) entry; and correct (sc) in place — 1.11x not 3.6x on the full ledger
- `ef3a682` I22 guard + doctrine: a book must spend the ecosystem (sf)
- `a173a93` The growth rail could only ever SHRINK the taker's one living lens (sf)
- `308f6e7` The trend exit joins the rail, and starts recording what its knobs cut (sf)
- `06d5e6c` The depth gate, driven against the live venue — and a cage I almost added (sf)
- `b643738` Widening carry's gate broke the guard that watches for shared supply (sf)
- `4bed760` Carry was idle at 0 of 12 behind a gate measuring the wrong thing (sf)
- `95650c5` Three instruments for asking a book where it can win, not where it can break (sf)
- `931fe7c` Merge PR #209: the fleet could not SEE leverage — publish the venue's margin surface, fail-closed to unlevered (se)
- `842622f` renumber (sd) -> (se) and record the ruin-table finding the margin surface caught (se)
- `7a05635` record the mutation survivor the margin test earned (sd)
- `36a4820` the margin test was grading its own arithmetic, not the publisher's — drive build_snapshot (sd)
- `a579b5d` the fleet could not see leverage: publish the venue's margin surface, fail-closed to unlevered (sd)
- `3551501` Ignore scripts/.*.pkl tape caches — the existing wildcard is .json only, so a 58MB pickle slipped into git add (sc)
- `96cdaa1` Leverage measured and shipped on nav-cook (clip $80->$240, below half-Kelly); two unmined signal families swept and refuted; the void mutation round corrected and mutate.py hardened (sc)
- `5d859b9` Close the surviving mutation: the measured-drawdown constant is pinned against itself (pre-mutation)
- `a1f18d4` nav-cook clip $80 -> $240: leverage measured on the book's own 226-trade series, sized below half-Kelly, pinned against the 15% drawdown bar (pre-mutation)
- `9a07d02` Merge PR #208: ⚖️ Counterweight was graded on its price return alone — 3.6× worse than it performs (sc)
- `a0b2c03` Merge remote-tracking branch 'origin/main' into claude/todays-work-review-6y8tua
- `85fb26b` nav-cook's founding claim reproduces (n=226, +0.373%, t=+2.61), the conflicting replay is explained as a confirm-convention difference, and the harness is finally committed (sb)
- `44c7703` a funding book was graded on its price return alone: Counterweight reads 3.6x worse than it performs (sb)
- `1bd0644` Daily review (ro): nav-cook shipped a gate 3.3x looser than the one it was graded on

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

