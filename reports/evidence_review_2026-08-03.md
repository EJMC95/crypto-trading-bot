# Evidence Review — 2026-08-03

_Reviewed 2026-08-03T04:24:51+00:00._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live 5e27c751f5b2 vs shadow b8629828e530 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds
- 🧬 REAL MONEY perps-funding-lighter-lighter is BEHIND THE REPO: container 16c4b139231d vs repo 7b28de41783f (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 perps-funding-lighter-lshadow is BEHIND THE REPO: container 16c4b139231d vs repo 7b28de41783f (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 REAL MONEY lighter-ticket-taker-lighter is BEHIND THE REPO: container 5e27c751f5b2 vs repo b8629828e530 (both n=15, so this is code, not file set) — the running container does not carry what has been merged

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | census now 9998 events across 35 books (threshold 50) |
| disloc:0G | active | census 467 ev / 277bps (alert 466), last event 0.1h ago, 42 entries |
| disloc:APEX | active | census 4040 ev / 313bps (alert 4040), last event 21.6h ago, 458 entries |
| disloc:BIO | active | census 100 ev / 272bps (alert 98), last event 0.6h ago, 9 entries |
| disloc:CHIP | active | census 208 ev / 160bps (alert 207), last event 0.6h ago, 15 entries |
| disloc:EIGEN | active | census 197 ev / 161bps (alert 197), last event 10.4h ago, 9 entries |
| disloc:GMX | active | census 172 ev / 151bps (alert 172), last event 16.7h ago, 19 entries |
| disloc:KAITO | active | census 1358 ev / 350bps (alert 1348), last event 0.3h ago, 264 entries |
| disloc:MU | active | census 183 ev / 158bps (alert 183), last event 52.2h ago, 87 entries |
| disloc:NEAR | active | census 22 ev / 150bps (alert 22), last event 60.7h ago, 0 entries |
| disloc:RESOLV | active | census 472 ev / 188bps (alert 470), last event 0.6h ago, 11 entries |
| disloc:SKHYNIXUSD | active | census 910 ev / 414bps (alert 902), last event 0.1h ago, 725 entries |
| disloc:SKY | active | census 98 ev / 315bps (alert 98), last event 6.8h ago, 4 entries |
| disloc:SNDK | active | census 329 ev / 252bps (alert 329), last event 25.9h ago, 194 entries |
| disloc:STABLE | active | census 343 ev / 396bps (alert 342), last event 0.9h ago, 22 entries |
| disloc:STBL | active | census 246 ev / 245bps (alert 244), last event 1.0h ago, 40 entries |
| disloc:WTI | active | census 73 ev / 230bps (alert 73), last event 6.4h ago, 57 entries |
| disloc:ZORA | active | census 242 ev / 202bps (alert 242), last event 6.0h ago, 14 entries |
| factor-sample:11 | resolved | joined decision+context dataset at 373 closes (50% win), bucket 12 |
| factor-sample:12 | active | joined decision+context dataset at 373 closes (50% win), bucket 12 |
| veto:SOXL | resolved | SOXL no longer vetoed |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=91 (≥10): net $+12.87, WR 35%, t=1.09 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-breakoutup' at n=15 (≥10): net $+1.89, WR 47%, t=0.23 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=76, net $+8.47 — by lens [('short', 72, 7.96), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=36, net $-0.08 — by lens [('short-divergence', 24, 1.82), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🚦 fleet-risk light green — longs 11/20, shorts 2/12 (gross 13); 7d DD -0.06%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap -0.022pp (live +0.386% n=48, shadow +0.408% n=53) — no divergence
- 🧬 Farmer arms AGREE: live 16c4b139231d vs shadow 16c4b139231d (n=15)
- 🧬 Taker arms DRIFT: live 5e27c751f5b2 vs shadow b8629828e530 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds
- 🧬 REAL MONEY perps-funding-lighter-lighter is BEHIND THE REPO: container 16c4b139231d vs repo 7b28de41783f (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 perps-funding-lighter-lshadow is BEHIND THE REPO: container 16c4b139231d vs repo 7b28de41783f (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 REAL MONEY lighter-ticket-taker-lighter is BEHIND THE REPO: container 5e27c751f5b2 vs repo b8629828e530 (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 lighter-ticket-taker-lshadow matches the repo tree: b8629828e530 (n=15)

## Summary

21 alert keys reviewed: 19 active, 2 resolved, 0 stale. No divergence and no drawdown-governor trigger. 16 new-evidence items scanned.

---

# HUMAN LAYER — added after the script run (2026-08-03, 14:5x Sydney/AEST)

## 0. The four 🧬 ACTION items above are FALSE ALARMS — resolved by measurement

The script's build-drift arm fired on four rows. **All four are expected and
declared.** I replayed `build_compute` across the last 14 commits in a clean
worktree rather than trusting either the changelog or the alert:

| Row | Container | = commit | Repo HEAD | Verdict |
|---|---|---|---|---|
| `perps-funding-lighter-lighter` (REAL $) | `16c4b139231d` | **(iq)** `53b24da` | `7b28de41783f` = (ir) | **Expected** — (ir) deliberately carries NO live marker |
| `perps-funding-lighter-lshadow` | `16c4b139231d` | **(iq)** | same | **Expected** — same delta; arms AGREE |
| `lighter-ticket-taker-lighter` (REAL $) | `5e27c751f5b2` | **(ij)/(ik)** | `b8629828e530` | Behind by (il)(im)(in) — but `lighter_ticket_taker.py` **did not change**; the hash moved only because `bot_pnl_store.py` (a `_BUILD_SHARED` file) changed at (il) |
| Taker arms "DRIFT" | live (ij) vs shadow (il) | — | — | Delta is **ledger/publish code only, not trading logic** — the control arm is still sound for decisions |

**(in)'s central claim is CONFIRMED:** the live taker runs `5e27c751f5b2`,
which is exactly (ij)/(ik) — so **(ij)'s lens veto IS live on real money.**

> **Script improvement earned here (for tomorrow):** the drift arm cannot
> distinguish "the container is stale" from "the merged commit was
> deliberately not deployed". Every no-marker commit will re-raise these as
> ⚠️ ACTION. Worth teaching it to read the live-deploy marker from the commit
> subject range between container-commit and HEAD. I did **not** implement it
> this run — see §5 for why the tree was not safe to edit.

## 1. Today's Funding Farmer work — GRADED SOLID, and verified against live data

Operator flagged today's Farmer changes as solid. I checked all four against
the running payload rather than the changelog, and they hold up:

- **(io)** — card units. The live row now publishes `clip_usd=37.5`,
  `cap_usd=150.0`, `max_open=5`, `enter_apr=0.05`. ✅ **Verified live.** The
  prose card that had been 8× wrong on APR since the 17-Jul basis fix is gone.
- **(io)** — deposit accounting. Equity $198.91, `pnl_abs` +$7.39 — the
  deposit booked as capital, not P&L, exactly as the entry claims. ✅
- **(ip)** — the gate0 rollback path. The live Farmer runs a **main-derived**
  build (`16c4b139231d` = (iq)), not a gate0 build. The ungated second deploy
  path is closed. ✅ **This is the fix for the drift/setback the operator
  named, and it is confirmed working.**
- **(iq)** — `hot_since` durability. ✅ **Verified live, and it cleared during
  this review:** at 04:33Z the live book held **0** positions (still inside the
  declared post-restart blackout); by 04:40Z it held **1**, and the shadow held
  **3**. The blackout ended at 04:36Z precisely as (iq)/(ir) predicted.
- **(ir)** — `hot_h` telemetry + persistence-suppression logging. On main,
  **deliberately undeployed** (no marker, to avoid costing the book another 4h).
  Consistent; this is the source of the §0 "behind the repo" alarms.

**Farmer arms AGREE** (`16c4b139231d` both sides) — the judge's control pair is
clean. Live-vs-shadow per-trade gap **−0.022pp** (live +0.386% n=48, shadow
+0.408% n=53): no divergence.

## 2. ⚠️ THE REAL FINDING: 🌾 carry is structurally stalled and its go-live clock cannot start

This is the item that matters and it is **not** in the script's output.

- **`perps-funding-carry-lshadow` has not OPENED a position in 98.9 hours**
  (last open 30-Jul 01:40Z). Last close was 39.5h ago.
- Its era moved to **2026-07-31** at (ii) — correctly, for the two-writer
  invalidation. The grader therefore reads **`0 of 86 closes count` →
  UNGRADEABLE**. Earliest gradeable date ~30-Aug **assuming it trades**, and it
  is not trading.
- It holds **6 of 12** slots, so **capacity is not the constraint.**

**The binding constraint, measured against the scout's live `vols` (203 books,
age 0.06h):**

| Floor | Books clearing it |
|---|---|
| $0.25M | 53 |
| $0.5M | 35 |
| $1.0M | 26 |
| **$2.0M ← carry's floor** | **14** |
| $5.0M | 9 |

Median book volume is **$0.043M**. The book's own published hot list:
`CXMT −692.9%` at **$0.155M**, `H100 +209.4%` at **$0.128M** — 13–16× below the
floor. `KAITO` sits at **$1.998M, missing the $2M bar by $2,000.** The one hot
AND liquid coin (`SKHYNIXUSD`, $10.4M, +121.8%) it **already holds**.

So the intersection of *hot* ∩ *liquid* is nearly empty, and what is in it, it
already owns. **This is a market condition correctly handled — not a defect** —
but the consequence is that the fleet's former go-live frontrunner will
accumulate zero evidence indefinitely.

**`MIN_DAY_VOLUME = 2e6` is a BARE LITERAL** (`funding_carry_bot.py:87`) — not
`os.environ.get`-backed, not in `_ENV_DEFAULTS`, not a registered lever. Only
`carry.enter_apr` and `carry.max_positions` are registered. **The growth rail
cannot move the one constraint that binds.** `PERSIST_H = 6.0` (line 118) is
the same shape. This is precisely the carried-priority-1 pattern
(`LONG_BUDGET`/`SHORT_BUDGET`), on a different book.

## 3. Carried priorities — status

1. **L2 long-budget levers** — **STILL OPEN**, but **de-escalated**. Measured
   today: `long_positions=11 / budget 20`, light green, `clip_scale 1.0`. The
   veto is nowhere near binding, so this is no longer a live ceiling on reach —
   it is a latent one. Step 1 (env-default + register, inert) still correct.
2. **🌾 carry's duplicate writer** — ✅ **CLOSE THIS ITEM as an operator
   action.** `audit_ledger_integrity` reports the most recent overlap began
   **116.8h ago**: *"HISTORICAL, no overlap inside 6h. Nothing to stop."* The
   row publishes a single consistent `svc=funding-carry`. `claim_writer` is
   doing its job. **What remains is permanent and needs no action:** the 7
   historical overlaps stay in the ledger forever, which is exactly why (ii)
   moved the era — that is the handled consequence, not an open task.
3. **MTM drawdown re-grade of carry** — not yet; window closes ~10–11 Aug.
   Note it will land on a book with **zero in-era closes**, so plan for it to
   be uninformative unless §2 is unblocked.
4. **Three fleet position counters** — **STILL OPEN and still disagreeing**:
   `long_positions=11` vs `exposure.long_n=15` vs `long_effective_n=11.8`. The
   veto reads the first.

## 4. Fleet state — clean

- **All 11 organs fresh**, every one inside its TTL (brain, radar, judge,
  tuner, immune, proprioception, sentinel, go-live, allocation, proposals).
  This is a real improvement on 1-Aug, when two organs had been dead 12.5h.
- **Go-live: READY: none.** No book newly qualifies. Nearest is the live
  Farmer at t=1.27 (window fails until ~16-Aug).
- **Fleet 7d drawdown −0.06%**, governor untriggered, light green.
- **44 ledger rows quarantined** — the declared (hm) BOT/USDC + CXMT/USDC
  basis-defect episode. Expected, not new.
- `errors: []` — no section failed soft. Nothing to repair in the script's
  own plumbing this run.
- ⚠️ **`long-dip` shadow lens is significantly negative**: n=13, −$9.15, WR 15%,
  **t=−2.74**. Shadow-only — `LIVE_SIDES` restricts real money to
  divergence-short — so no real money is exposed. Flagging for the brain's
  veto path, not for action.

## 5. Why I changed no code this run

`funding_carry_bot.py` carries **another live session's uncommitted work** — a
~98-line `scan_census()` that diagnoses this exact stall (its docstring
independently reaches my §2 conclusion: the volume floor, `FOLKS/S/ARC` 1–3
orders of magnitude below it, `KAITO` 0.74h short). Editing that file to
register the lever would tangle two sessions' work in one file, which is the
(hp) incident. **Backed up to scratchpad, left untouched.** Their census is the
right first half of the fix — it makes the constraint self-reporting.

---

# OPTIONS TO OPTIMISE — ranked

### 1. Register 🌾 carry's `MIN_DAY_VOLUME` as a bounded lever (UNBLOCKING) — highest value
- **Now:** bare literal `2e6` at `funding_carry_bot.py:87`. Unreachable by the growth rail.
- **Change:** `os.environ.get("CARRY_MIN_VOL", "2e6")` + `_ENV_DEFAULTS` +
  registry entry `carry.min_vol` with `env_default=2e6`, consumed in
  `apply_tuning()`. **Inert on ship — zero behaviour change**, exactly the
  carried-priority-1 Step 1 pattern.
- **Cage, derived from measurement (not guessed):** `lo=1.0e6` (26 books —
  doubles the eligible set), `hi=2.0e6` (today's value; the rail may only
  loosen toward the tape, never tighten past today — the `disloc.exit_bps`
  precedent).
- **Evidence:** 189 of 203 books excluded; both hot coins 13–16× below; KAITO
  misses by $2k; 6 of 12 slots idle for 99h; era gives 0 gradeable closes.
- **Expectancy cost: NOT ZERO, and it must be replay-gated.** Thinner books
  mean unmeasured per-book slippage ([[lighter-slippage-is-per-book-not-per-venue]]),
  and carry's $300 clip on a $0.155M book is 0.19% of daily volume. **Do not
  hand-set it** — register it, then let the scout tuner's replay gate walk it,
  brain veto senior. Registration itself costs nothing.
- **Blocked this run** by the file collision in §5. **This is the one change I
  recommend for the next session that owns that file.**

### 2. Teach the review's drift arm about deliberate no-marker commits (TOOLING)
- **Now:** four ⚠️ ACTION false alarms today; will recur on every undeployed commit.
- **Change:** when container-commit ≠ HEAD, scan commit **subjects** in that
  range for `[deploy-live-*]`; absent ⇒ report as *expected*, not ACTION.
- **Cost:** none. Pure reporting fidelity. Blocked only by review-script
  ownership being cleaner tomorrow; no data dependency.

### 3. Reconcile the three position counters (CORRECTNESS, carried #4)
- `long_positions=11` vs `exposure.long_n=15` vs `long_effective_n=11.8` in one
  payload. The veto acts on the smallest. Until they agree, any admission-by-edge
  work (carried #1 Step 2/3) is built on a number nobody has reconciled.
- **Cost:** none — measurement only.

### 4. REFUSED today, with evidence — capacity widening
- ⚖️ **Counterweight is the only book at its structural cap** (open=16 = k=8 × 2
  legs). Under (hs)/**I7** a capacity widening must read mark-to-market P&L and
  **fail closed** — the book grades **mean −0.236%, t=−0.26**. **Correctly
  refused.** No other book is capacity-bound: carry 6/12, Index Rider 4/9,
  Snap Back 0 open, Perp Sniper 0 open.
- **REACH is not binding either:** longs 11/20, shorts 2/12. Nothing to widen.
- This is the honest "nothing on offer" for the two categories that usually pay.

### Which book moved today (doctrine rule 4)
**💸 the Funding Farmer.** It went from *structurally unable to open* to
*trading again* — (iq) landed on real money and the 4h blackout cleared during
this review (0 → 1 open live, 3 shadow). It is 4/6 bars from the gate
(t=1.27, window until ~16-Aug). **🌾 carry moved backwards** and needs §2 or it
moves no further.

---

# ADDENDUM — implemented + a self-refutation (operator: *"fix the things holding it back from wins"*)

## What I shipped into the tree (green, mutation-verified, UNCOMMITTED)

**`carry.min_vol` is now a registered, bounded lever.** The liquidity floor was
a bare literal, so the growth rail could move carry's two *non-binding* gates
and not the one that actually gated it.

- `funding_carry_bot.py` — `MIN_DAY_VOLUME` is now
  `float(os.environ.get("CARRY_MIN_VOL", "2e6"))`, added to `_ENV_DEFAULTS` and
  to the `apply_tuning()` loop (so it reaches the gate through the same single
  path, not a call-site read — the registered-but-inert failure).
- `fleet_tuning.py` — `carry.min_vol`, lane `lighter-books`, cage
  **[1e6, 2e6]**, `env_default` 2e6, `step` −250k.
- `scripts/audit_lever_bounds.py` — added to `CONSUMERS` so the drift arm
  watches it.

**Verified:** ships **INERT** (`MIN_DAY_VOLUME` still exactly 2e6); clamp can
only loosen ($2.5M→$2.0M capped, $0.5M→$1.0M floored); the step ladder
terminates ($2.00→1.75→1.50→1.25→1.00M). Full suite **828 passed, 0 failed**;
all six guards pass. **Three mutations verified red:** unwiring it from
`apply_tuning`, drifting the registry default (the audit named the exact
defect), and dropping it from the test list.

### It also closed a class, and the class-closer caught a real gap on its first run

`tests/autonomy/test_book_levers.py` drove its coverage from a **hand-written
list**, so when I registered `carry.min_vol` all 104 tests passed *around* it —
green, covering nothing. Added `test_every_lighter_books_lever_is_listed_here`,
which asserts the registry's `lighter-books` membership is a subset of the
tested list. **On its first run it failed on `disloc.exit_bps`** — the fleet's
first exit lever, shipped (gu) on 30-Jul, registered on that lane and never
listed here, so it had no cage, consumer or auto-revert assertion for four
days. Verified correctly wired (it is), added to both consumption
parametrizes. Coverage hole, not a live defect — which is exactly the shape
that stays invisible until the lever misbehaves.

## ⚠️ AND THEN THE MEASUREMENT REFUTED THE POINT OF IT — stated plainly

I then measured what each rung of that new cage would actually unlock. **It
unlocks nothing.**

```
  floor    liquid books   hot & liquid   NEW vs $2M
  $2.00M        15              1            —      (SKHYNIXUSD +137%, ALREADY HELD)
  $1.75M        16              1           +0
  $1.50M        18              1           +0
  $1.25M        20              1           +0
  $1.00M        26              1           +0
```

Walking the floor all the way to the cage bottom adds **11 liquid books and
ZERO hot ones.** The hot coins (CXMT $0.155M, H100 $0.128M) are 6–13× below
even the $1M bound — they were never one notch away.

**The real constraint is that the venue's funding distribution has collapsed.**
Every liquid book, ranked:

```
  SKHYNIXUSD  +136.7%  $10.4M   HELD
  ---- nothing between 13% and 137% ----
  SOXL         +13.1%   $2.3M
  LIT/SOL/ZEC/HYPE/KAITO  ~±10.5%
  BTC           +6.1%  $404.8M
  MU/SPY/WTI/XAU/SNDK/BRENT +3.5%
```

Exactly **one** liquid book clears the 20% TRUE bar and **carry already holds
it.** This is a market condition, correctly handled — not a defect, and not a
knob. **My own §2/Option-1 framing this morning was wrong about the payoff and
I am withdrawing it:** the floor was genuinely unreachable by the rail and
fixing that is correct structural work, but it buys no trades today.

## The only gate with real headroom — and I am NOT touching it

`carry.enter_apr` (registered, cage [0.80, 3.20] = 10–40% TRUE, shipped 1.60 =
20%). Measured at the $2M floor:

| TRUE bar | lever | unheld candidates |
|---|---|---|
| 20% *(shipped)* | 1.60 | **0** |
| 15% | 1.20 | 0 |
| 12% | 0.96 | 1 — SOXL |
| 10% | 0.80 | **6** — SOXL, LIT, SOL, ZEC, HYPE, KAITO (all $2.3M–$26.8M, no liquidity concern) |

**Why I did not move it.** The 21-Jul gate sweep on Lighter's own 150d tape
measured this exact direction as loss-making: 0.40 (5% TRUE) was structural
bleed, −$93.31/150d at a 20% win rate, and the sweep was monotone with only
1.60 beating shipped on the full window **and** both halves. I reproduced its
mechanism independently from the bot's own constants:

```
round trip 29.0 bps, MAX_HOLD 336h — hours of accrual to merely repay friction
    5% -> 508h  CANNOT PAY within MAX_HOLD   <- reproduces the 21-Jul finding
   10% -> 254h  pays, margin  82h            <- the cage floor: thin
   15% -> 169h  pays, margin 167h
   20% -> 127h  pays, margin 209h            <- shipped
```

10% is not *structurally* impossible the way 5% was, but it needs the rate to
hold for 254 of 336 hours just to break even — on rates that mean-revert in
hours, which is the whole reason `PERSIST_H` exists. **This is precisely a
"more trades bought with expectancy" candidate, and the standing rule is not
to bank it.** It is also not mine to hand-set: it belongs in
`fleet_proposals.py` → the scout tuner's replay gate, brain veto senior.

## Bottom line for the operator

- 🌾 **carry is not broken and nothing is misconfigured.** It is holding 6 of
  12 slots against a venue where one liquid book is hot and it already owns it.
- **No lever available today buys it a win without paying expectancy.** That is
  a refusal with evidence, not a shrug.
- Its era restart (31-Jul) plus this drought means its 30-day clock is very
  unlikely to start before the funding distribution widens again. **If carry
  stays flat into late August, the honest question is keep-or-retire on the
  go-live pipeline — an operator call, not a code change.**
- **The Funding Farmer, not carry, is the book that moved today** (§1) and it
  is 4/6 bars from the gate.

## Not committed — and why

`funding_carry_bot.py` now holds **two sessions' work**: my lever change and
another session's `scan_census()` (still uncommitted). I did not commit,
because committing would sweep up their unfinished work under my message —
the (hp) incident verbatim. Their census and my lever are complementary (the
census reads `MIN_DAY_VOLUME`, so it will report the *tuned* floor, not the
literal). **Whoever commits must review both hunks.** Backup of their WIP:
`scratchpad/backup/funding_carry_bot.wip.diff`.

---

# ADDENDUM 2 — "how are we months behind?" (operator question, 3-Aug)

**Measured answer: nothing in the live fleet is months behind.** Checked at
2026-08-03 05:00Z:

- **23 of 23 `bot_pnl` rows are fresher than 24h.** Every live and shadow book
  is publishing now. Zero exceptions.
- **64 of 80 `bot_state` keys are fresher than 24h.**
- The `evidence-review` row carries `reviewed_at = 2026-08-03T04:24:51+00:00` —
  today, written by this run.

**The 16 old keys are all retired-bot tombstones, and they are kept ON
PURPOSE.** Cross-checked every one against `cleanup_legacy_bots.LEGACY_BOTS` —
11 of 11 matched `True`:

| Key | Age | Why it is old |
|---|---|---|
| `perps-donchian-breakout*`, `perps-rsi-meanrev*` | 18–23d | retired 12/13-Jul |
| `event-listing-sniper`, `scanner-cross-exchange-arb`, `listing-intel`, `gapscout-census`, `perps-funding-carry` (HL arm) | 16d | the 17-Jul LIGHTER-ONLY cut |
| `crypto-trend-daily-lighter:live` / `:eqguard`, `equities-momentum-lshadow` | 16–17d | retired 17-Jul |
| `crypto-trend-daily-lshadow` | 1d | 🌊 Tide Rider, retired 2-Aug (`c2fd25a`) |
| `learn:pair_blacklist`, `dashboard-hidden-bots` | 21–28d | config keys — they only change when edited |

`cleanup_legacy_bots.py` deletes **the `bot_pnl` snapshot row only**; its own
header states *"trade ledgers … and bot_state history are kept"*. That is the
documented retirement contract (`RETIRED_ROWS` hides the card, `LEGACY_BOTS`
prunes the row, the ledger survives as history). `gapscout-census` is even
declared STALE FOREVER in CLAUDE.md. **So these are gravestones, not lag.**

## The reports have not been inconsistent either — since 28-Jul

| Date | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 1 | 2 | 3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| report | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**Seven consecutive days, 28-Jul → 3-Aug, no gaps.** The 25–27 Jul hole is the
documented failure this script was built to fix (the `closed_at`-is-TEXT and
`max_drawdown`-not-a-column schema traps killed the run partway while cron's
`lastRunAt` advanced daily). It has not recurred in seven runs.

## The one real observation

A permanent graveyard of 16 never-expiring keys makes any age scan look
alarming, and that is the `(hh)` hazard pointed at a human instead of a
detector: **a list that always contains stale entries trains you to ignore
staleness**, and a genuinely dead organ would sit in that list unnoticed. Not
a defect and not worth a prune (the ledgers are deliberately durable) — but
worth knowing that "old key" ≠ "lagging fleet" here. This review reads
liveness per **I1** (`age_sec` first) against the *living* cohort, which is why
it did not flag them.

---

# ADDENDUM 3 — committed, and one more defect found on the way out

Four commits landed. Suite **833 passed, 0 failed**; six guards green.

| Commit | What |
|---|---|
| `6955f67` **(is)** | the other session's `scan_census` — judged useful, kept, and **hardened** (its call site was unguarded and it raises on a malformed funding entry) |
| `13a9018` **(it)** | `carry.min_vol` registered as a bounded lever — **and the same entry records that it unlocks zero books today** |
| `84bd802` | the operator's standing rule engraved in CLAUDE.md |
| `8eef434` **(iu)** | 🌾 carry was **resurrecting hot streaks that never persisted** |

## (iu) is the one that actually protects win rate

Found while checking whether carry shared the Farmer's `(iq)` blackout bug. **It
did not — it had the mirror of it, which is worse.** Carry already persisted
`hot_since`, so it never went inert; but it restored **unconditionally** — any
dict, any age, no `saved_ts`, no gap bound, no skew or future-stamp check.

- `(iq)`'s bug = a **lost** clock ⇒ the book goes **INERT** ⇒ shows up as
  silence (which is why it took two operator asks to find).
- carry's bug = a **wrongly-restored** clock ⇒ the book goes **PERMISSIVE** ⇒ a
  coin skips `PERSIST_H` on hotness that lapsed while the container was down.
  **That shows up as a bad trade.**

It costs the book its own thesis: `PERSIST_H` exists because *"persistent
funding pays carries, spikes pay fees"*, and a resurrected streak admits exactly
the spike entry the gate was built to refuse. The 21-Jul Lighter sweep measured
what such entries do — **−$93.31/150d at a 20% win rate**.

Fixed with **one owner** in `funding_basis.py` (already in `_BUILD_SHARED` and
COPY'd into both images), fail-closed in every direction, floor = today's
behaviour. **The live Farmer's copy was deliberately not touched** — real money,
shipped hours ago — so a parity test pins the two to identical output across 9
blobs instead. Two mutations verified red.

**Cost: one 6h wait, once** — and now is the cheapest moment to pay it, since
carry has opened nothing in 98.9h and the only liquid book clearing its bar is
one it already holds.

## ⚠️ NOT PUSHED — and pushing is a deploy

All four commits are local. **`funding_carry_bot.py` and `funding_basis.py` are
both on the auto-deploy `paths:` list**, so a push redeploys the `funding-carry`
service. That is fine and intended, but it is an operator act, not a reviewer's:

```bash
git push origin main
```

- **No live marker is present in any of the four subjects**, so the live Farmer
  and live Taker will **not** deploy — deliberate.
- `funding_basis.py` is in `_BUILD_SHARED`, so every image's `extra.build` stamp
  shifts on its next deploy. The change is purely additive (one new function,
  one import) and cannot alter existing behaviour.
- Verify the carry deploy landed by the `extra.build` + `extra.build_n` stamp,
  never by the green run.
