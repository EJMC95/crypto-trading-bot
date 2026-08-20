# HANDOFF — start here

_Generated 2026-08-20 19:41 Sydney (09:41Z) by `scripts/session_state.py`. Do not hand-edit: regenerate it._

## Carried — pick these up FIRST (I11)

### `taker-replay-blind-to-breakoutup`  ·  owner: **session**
lighter_ticket_replay refuses every breakout entry (`_up = False if lens == "breakout"`), so the scout tuner's gate cannot see the taker's ONLY living lens. (sf) pinned the cages shut against the resulting one-way ratchet; the DURABLE fix is to give the replay the taker's own breakoutup relabel via up_read(), after which the cage pins are a decision to re-make on evidence.

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

### `unmeasurable-lever-backlog`  ·  owner: **session**
30 registered levers still have no QUANTITIES spec — no recorded quantity to profile them against. The ratchet in audit_lever_measurability stops the pile GROWING; draining it is per-lever work: record what the knob cuts, then spec it.

_Still open because:_ each one needs the bot to stamp its own governing quantity first (the (sf) give_back/mae_ret pattern).

### `live-taker-divergence-stop-unpriced`  ·  owner: **session**
The LIVE taker's short-divergence stop reads +28pp reclaim excess and +2.10% held at 24h over n=22 — a measured SIGNAL with no priced VALUE. lighter_ticket_replay is the calibrated instrument; a candle walk is not (it has no short branch).

_Still open because:_ real-money row: measure and hand over, never hand-set.

### `georgia-t-bar`  ·  owner: **session**
🔮 georgia is 5 of 6 go-live bars, failing only t (1.11 < 2.0) — the fleet's closest book to the gate. Its trailing stop is NOT the leak (reclaim 74% vs placebo 75%). Where its t comes from is the open question: raise the mean, cut the variance, or raise n.

_Still open because:_ unmeasured; the per-book audit was still running.

### `carry-garrett-ranking-collision`  ·  owner: **OPERATOR**
🌾 carry's measured-depth gate now reaches the whole of 🛢️ Garrett's [0.1M, 2M) band, and Garrett's own (pl) measurement found 6 of 6 of its top-ranked candidates are >=20% APR — so carry is a rival for exactly the supply Garrett ranks first. A RANKING collision; audit_book_overlap's axes (apr x vol x class) cannot express it.

_Still open because:_ declared in KNOWN_CELL_COLLISIONS; the call is the same ~12-Sep decision point as the rest of that component.

## Shipped today (51 commit(s), entries (ro), (rp), (rq), (rr), (rs), (rt), (ry), (rz), (sb), (sc), (sd), (se), (sf), (sg))

- `f0fba40` The never-recorded class, closed fleet-wide; and I11 finally has teeth (sg)
- `e34b6a2` The only path to more real money was rigged against ever promoting (sf)
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
- `ace5112` Close the citation-drift blind spot, and refute the consumer bar my own note called right (rz)
- `547257e` merge origin/main: (rh)->(rz), and REFUTE the bar my own note called right
- `12d27ba` Merge PR #205: four declared enforcements were inert — the organ death recorder, I2's amnesia check, I10's gate key, and 39 dead assertions (ry)
- `4596e50` renumber the (rs) changelog entry to (ry) (letter taken on main mid-flight)
- `155f9c2` renumber (rs) -> (ry) in code citations: main took the letter for PR #204 mid-flight
- `341bdba` test fixture: compute timestamps rather than reuse a date the era tables own (rs)
- `053e8e5` pin the four inert enforcements with tests: 8 mutations, all red (rs)
- `64e1207` four declared enforcements were inert: the organ death recorder, I2's amnesia check, I10's real-money gate key, and 39 dead assertions (rs)
- `676a90a` Merge PR #206: the horizon measured forward — band-kelly's hold-watch, after two refusals with the mechanism (rt)
- `aa3b943` The horizon question cannot be answered backwards on this book (1.9-min median hold vs a 1-min candle), so band-kelly now measures it forward (rt)
- `84cc04e` Merge PR #204: fewer guards, more room — the ladder replaces my exemption, and agronomy sees every living book (rs)
- `321aec1` agronomy fidelity: band-kelly declares its two real guards, and (rs) states plainly that this organ does not run
- `55be410` merge origin/main: keep both changelog stacks — (rs) atop main's newest
- `f3c50f3` Fewer guards, more room: the taker gets the ladder instead of my exemption, the Navigator stops being flagged for trading, agronomy sees 8 books it never knew — one real money (rs)
- `3629035` Merge PR #203: mum v2's gate-reachability gauge — her card can now say how far the market is from her bar (rr)
- `a175da8` Merge remote-tracking branch 'origin/main' into claude/todays-work-review-6y8tua
- `74fbf2b` Merge PR #202: self-verification corrections — a guard exemption justified by a margin that does not exist (rq)
- `07fe4a9` mum v2's census could not say how far the market was from her bar — the reachability gauge (rq)
- `f7ffa27` merge origin/main: keep both changelog stacks — (rq) atop mum's un-retirement (ro)/(rp)
- `be95ebb` A verification sweep over my own claims found three false ones — the worst a guard exemption justified by a margin that does not exist (rq)
- `d6be57f` Merge PR #201: mum v2's control arm — atomic pairing kills the legacy contamination, and it now survives a redeploy (rp)
- `5f83a16` mum v2's first live payload indicted her own control arm: legacy contamination + no durability (rp)
- `18fb3eb` Merge PR #200: 👩 mum is ALIVE as v2 — the clock was the disease, and she now carries her own control arm (ro)
- `f5675e2` The I20 claim, stated at its real strength (ro)
- `98cdee5` The autopsy is re-runnable, and it corrects my own carry figure (ro)
- `9382f34` 👩 mum IS ALIVE as v2: the operator's reversal, and the autopsy says the disease was THE CLOCK (ro)
- `d6cc2c6` WIP mum v2 — pre-mutation checkpoint
- `05dc610` Merge PR #199: one-shot tape fetcher for the mum-v2 founding study (deleted at the v2 merge)
- `71d29a6` One-shot tape fetcher for the mum-v2 founding study (runs on this branch only; deleted before merge per the (lr) rule)

## How this file stays honest

Every carried row above carries a `closes_when` predicate that `--check` evaluates against the repo. A finished item cannot linger (it is reported CLOSE THIS and reddens CI) and an unfinished one cannot be dropped without deleting a row somebody has to justify. The shipped list is read from git, not typed.

