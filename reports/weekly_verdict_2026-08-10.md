# Fleet weekly verdict — week ending Sun 2026-08-09 (scoreboard), read Thu 2026-08-13 13:20 AEST

**Headline: no book moved toward the gate; the fleet's one big capital signal is
computed on a sample its own gate throws out.**

> ### ⚠️ CORRECTED 17:00 AEST — read this first
>
> The first version of this report was written against a `git fetch` taken at
> **12:19 AEST**, and a concurrent session pushed twelve commits between 12:34
> and 15:40. **Three statements below were wrong and are struck through in
> place** (I12 — a report that no longer describes the system is a defect):
>
> 1. **"No commits since 07-Aug (six days)" is FALSE.** Twelve commits landed
>    today, `(lj)`–`(ls)`, including **two new books born and verified alive**:
>    🛢️ `band-garrett-lshadow` (the thin-tier funding band, the fleet's strongest
>    measured unbuilt claim) and 🏦 `book-kiyosaki-lshadow` (Rich Dad as a rule
>    set). Both are on the feed at $0.00 / 0 closes. The fleet was not quiet;
>    it was the busiest day in a week.
> 2. **The 📊 `equities-regime-lshadow` "off-feed" finding is NOT a defect** —
>    it is `(lo)`, **today's deliberate I17 retirement** on the operator's "get
>    rid of what's not working", done properly in both halves (`RETIRED_ROWS`
>    *and* `LEGACY_BOTS`). My grep missed it because my checkout predated the
>    commit. **Do not go looking for a suppressed row.** The I17 call I asked
>    for had already been made.
> 3. **Recommendation 3 (rank allocation on `claim_era`) was already measured
>    and refused** by `(kc)`: era-scoping the *ranked* claim leaves zero
>    claimants on 15 of 15 days — it turns the organ off. I proposed it without
>    checking. The underlying defect is real, and the corrected fix is narrower;
>    **it is now shipped** — see the closing section.
>
> Also landed today and worth knowing while reading section (a): `(lj)`
> era-scoped the live Taker's realised lens veto and **deployed to real money**,
> and `(lk)` put crypto-only screens on 🌾 carry and 🎯 the sniper.

Sources: scoreboard issue #154 (`fleet-weekly-assessment.yml`, Mon 10-Aug 09:53 AEST,
run `31343011313` — **both jobs green, `code-currency` clean, no BEHIND-OWN**);
`/bus.json` `golive-readiness` (13-Aug 11:16 AEST), `fleet-allocation` (13-Aug 12:16 AEST),
`impl-shortfall` (13-Aug 12:15 AEST); `/pnl.json` (13-Aug 13:07 AEST).
Judged, not recomputed. Shadow books are $1,000 paper; not financial advice.
Every action below is an operator act — nothing here was executed.

---

## a. REAL MONEY

| Row | Mon 04-Aug | Mon 09-Aug | Thu 13-Aug 13:07 | Week (04→09) |
|---|---|---|---|---|
| 💸 `perps-funding-lighter-lighter` (Farmer) | +$8.48 | +$6.81 | **+$6.31** | −$1.67 |
| 🎫 `lighter-ticket-taker-lighter` (Taker) | +$0.65 | −$1.84 | **−$4.10** | −$2.49 |
| **Combined** | +$9.13 | +$4.97 | **+$2.21** | **−$4.16** |

Live equity **$260.60** across both arms. Both rows fresh (0.1h), both stamped
`build_n 15`, services `trail-blazer-live` / `tide-rider-lighter-live`.

**Per-trade, in-era — the gate's own sample, never equity:**

| | n | mean %/trade | t | halves | bars |
|---|---|---|---|---|---|
| Farmer **live** | 72 | **+0.079** | +0.50 | +2.62 / −1.71 | 3/6 |
| Farmer shadow | 131 | +0.029 | +0.14 | +7.75 / −14.02 | 3/6 |
| Taker **live** | 29 | **−1.122** | −1.67 | +1.05 / −4.15 | 1/6 |
| Taker shadow | 43 | −0.294 | −0.45 | +11.93 / −13.76 | 2/6 |

Live is **ahead of shadow by +0.05pp** on the Farmer and **behind by −0.83pp** on the
Taker — but **neither pair is a clean control**, and saying so is the point:
the Farmer's shadow twin is currently the judge's *experiment* arm (`slope-gate-off`
running since 06-Aug), and the live Taker is divergence-**short**-only by hard gate
while its shadow runs five lenses both sides.

**impl-shortfall** agrees and says so itself: verdict **`xp-contaminated`**,
gap −0.087pp over 27 paired closes / 6 coins, `slip_streak 0`. Execution is clean:
fills are 100 % real (`trades(tx)` on 56 Farmer + 30 Taker orders), Farmer live slips
**0.74 bps vs shadow 0.90** (live ahead), Taker live **5.14 bps vs shadow 3.19** on an
8.78 bps spread — ~1.9 bps behind, which is execution, not thesis.

**Nothing on the real-money rows needs an operator action this week.**

---

## b. WHICH BOOK MOVED TOWARD THE GATE (doctrine rule 4)

**`ready: []`. No book flipped a bar into passing. Two moved materially away.**

**The one genuine forward move — decidability, not profit.** `(li)` (07-Aug, deployed
and verified live today): three 🏛️ books — gillard, rudd, abbott, holding **484 of the
cohort's 552 closes** — were released from a `regime_timing` latch that fired on a rate
that was 1.0 by arithmetic and whose only exit was the book going silent long enough to
be declared dead. Confirmed in the live payload: all six PM books read `halted: false`
and every `last_skip` is now `ml-gate(...)`, not a regime gate; gillard has closed 22
`short-disloc` trades in the trailing 7d. That restores their ability to produce
evidence. It does not make them winners — the cohort reads **−$10.50** today.

**Moved away:**

- 🌾 **`perps-funding-carry-lshadow`** — the fleet's former flagship, five of six bars
  from the gate in late July, now **1 of 6**. In-era (since 31-Jul): n=10, mean
  **−0.155 %**, t=**−4.48**, halves −9.30/−6.15, horizon **unreachable**. −$6.15 realised
  since Monday. It holds nothing and cannot: **0 eligible of 219 books scanned**
  (196 below the APR gate, 22 below the liquidity floor, 1 waiting).
- ⚖️ **`perps-funding-spread-lshadow`** — **−$14.72 on the week** (−$15.79 → −$30.51),
  fleet-worst. In-era n=86, mean −1.908 %, t=−1.97, halves +3.77/**−34.36**, MTM DD 2.16 %.
- 💸 Farmer **shadow** −$13.61 (+18.52 → +4.91) — that is the *price of a running
  experiment*, not a book failing; the judge is holding `slope_gate=0` on that arm.

**Closest to the gate today:** `freqtrade-georgia-lshadow` at **4/6** (fails only
window 25.6 d < 30 and t=0.14 — verdict *undecidable*), and
`freqtrade-avo-maria-lshadow`, the **only book in the fleet with horizon `on_track`**
(ETA 2026-11-09, binding bar = **closes**, 0.26/day against a 30-close floor).

---

## c. CAPITAL vs CLAIMS (I16)

| class | books | closes | current | organ target | delta |
|---|---|---|---|---|---|
| funding | 5 | 536 | $5,000 | $17,750 | **+$12,750** |
| directional | 17 | 1,009 | $17,000 | $4,250 | **−$12,750** |

Only **2 of 22** books carry any claim: 🌾 carry **0.149 %/trade** (target $13,684,
**+$12,684**) and 💸 Farmer live 0.034 % (target $3,316, +$2,316). Twenty books hold
**$20,000 on a zero claim**.

**The disagreement that matters is not the $12,750 — it is that the organ and the gate
are reading different samples of the same book.** `fleet-allocation` publishes
`sample: "all-time-pooled"`. Carry's claim is computed on **n=101 all-time**, of which
**91 closes sit before its own declared era boundary** — the 17-Jul→29-Jul window in
which two containers wrote that ledger. The organ publishes the honest number right
beside it: **`claim_era: null`** (n_era=10, below its own n≥20 rule). In-era the same
book reads mean −0.155 %, t=−4.48.

So the fleet's single largest capital signal, **$12,684**, is computed on a sample the
go-live gate declares is two books' trades.

**This has consumers.** Since `(jr)`, `fleet_bus.allocation_scale` (clamped [0.25, 4.0])
sizes **new entries** on the three funding shadow books. Right now that means
🌾 carry at **×4.0**, ⚖️ Counterweight and the Farmer's shadow arm at **×0.25**.
Real money never reads it (AST-pinned in `test_allocation_consumer.py`).

Two things stop this being urgent, and one stops it being ignorable: the ×4 is
currently **inert** (carry holds nothing and has zero eligible candidates), and the
organ has Counterweight — the fleet's worst book — correctly at a quarter. But the
moment carry's venue gate admits again, it opens at 4× on a claim its own era rejects.

**~~Operator options~~ — SHIPPED, no operator action needed. See the closing section.**
~~or the code-side fix… rank on `claim_era` where it exists~~ — that specific fix was
already measured and refused by `(kc)` (era-scoping the *ranked* claim leaves zero
claimants on 15 of 15 days and turns the organ off). The corrected, narrower fix went
in as `(lv)` this afternoon. The kill switch below remains available and unchanged:

```bash
railway variables --service yield-harvester-shadow --set FLEET_ALLOCATION_MODE=advisory
```

---

## d. KEEP-OR-RETIRE PRESSURE (I17)

**Of 19 graded books: 0 ready, 13 `unreachable`, 5 `undecidable`, plus 1 zero-ledger book.**

**The decision docket fires tonight.** `decision_docket` is still empty, but
`docket_seen` holds all 19 books, **nine of them stamped `since 2026-08-06T12:28Z`**
against a `docket_days = 7.0` threshold — those nine publish at roughly
**22:28 AEST tonight**. Expect the 🚦 card to grow nine items; that is the organ working,
not a fault.

Named cases, with numbers:

1. **`crypto-breakout-4h-lshadow`** — the clearest retire case in the fleet.
   In-era n=15, mean **−1.745 %/trade**, **t=−3.50**, both halves negative (−2.56/−4.94);
   all-time n=21, t=−5.48, **−$10.13**. Frees $1,000 and 2 open longs against a long
   budget of 20 (21 long open now).
2. ~~**`equities-regime-lshadow`** — zero closed trades, ever… it has gone off the
   public feed… Operator check: the dashboard Manage panel.~~ **WITHDRAWN — this was
   my error, not a fault.** The row left `/pnl.json` because `(lo)` **retired it today**
   (operator: *"get rid of what's not working"*), on exactly the I17 grounds this
   section was about: 0 closes in 44 days, a measured ~17.2 closes/yr against a
   30-close bar, +$13.93 open MTM abandoned as marks-not-evidence. Both halves were
   done — `RETIRED_ROWS` **and** `LEGACY_BOTS` — and it is reversible via
   `INDEX_RIDER_RETIRED_OVERRIDE`. **No operator action.** The remaining act is the
   optional Railway service stop (`equities-regime-shadow`).
3. **`lighter-perp-sniper-lshadow`** — n=28, mean −0.709 %, t=−1.14 over 20.2 d at
   1.28 closes/day, `unreachable`. Undecidable *and* losing, and the evidence board has
   been holding `sniper.surge_mult=2.0` on a STARVED trigger to try to fix it.
4. ⚖️ **`perps-funding-spread-lshadow`** — worst P&L in the fleet (−$30.51) but
   **not a call to make today**: `(jg)`'s own revert criterion pre-registers this for the
   operator at **~28-Aug**, and `(ky)` measured its 86 closes as ~24 decisions. The
   allocation consumer already has it at ×0.25.
5. 🏛️ **`pm-abbott-lshadow`** (t=−2.06, n=82) — **do not retire on this.** Per `(li)`,
   abbott is the only individually significant PM loser and **no PM book survives
   Benjamini–Hochberg at FDR 0.05** over the six-book family.

**Recommended this week: one retirement (`crypto-breakout-4h-lshadow`) and one
liveness check (`equities-regime-lshadow`).** A retirement needs both halves —
`RETIRED_ROWS` in `pnl_dashboard.py` *and* `LEGACY_BOTS` in `cleanup_legacy_bots.py`.

---

## e. ONE EXPANSION CANDIDATE (I19) — **a refusal, with the numbers**

The binding constraint on the fleet's most-instrumented book is now measured exactly.
On the scout tuner's own 8-day tape (2,200 snapshots, 05-Aug → 13-Aug):

| lens | tickets seen | taken | closed | net |
|---|---|---|---|---|
| dip | 10,423 | **0** | 0 | $0 |
| breakout | 15,141 | **0** | 0 | $0 |
| momentum | 8,267 | **0** | 0 | $0 |
| divergence | 8,990 | 22 | 20 | **−$9.63** |

Three of four lenses convert **0 of 33,831 tickets**. The obvious widening is to loosen
those three — and **it is refused**. The tuner already tried and logged the refusal
itself: *"dip: brain-vetoed at floor — never widened"*, *"momentum: brain-vetoed at
floor — never widened"*. The brain's realised-record veto is senior by I14/I15, it is
holding at the floor, and the only lens that does fill loses **$9.63** on the same tape
while the live arm reads **−1.122 %/trade**. Widening there buys turnover with
expectancy — the exact thing the standing rule bans.

**What the week's evidence does support is already enacted, through the designed
channel:** the tuner's replay-gated sweep `taker.tp 0.06` / `taker.max_hold_h 24.0`,
*"beats baseline +$7.14 on the tape AND both halves"*. It sits on the `lighter-taker`
**shadow** lane with a TTL (expired ~14:23 AEST today; the tuner re-asserts hourly).
**It should not be propagated to real money this week** — only `live.*` levers steer the
live taker, only `experiment_judge` writes them, and the live arm's own record is n=29,
mean −1.122 %, t=−1.67, 1/6 bars. I14: the record beats the proxy, in both directions.

Two further refusals from the week, recorded rather than buried:

- **Judge `slope-gate-off`**: `promote: false` — *"shadow arm not positive in its own
  right"* (shadow −0.053 %/trade vs live −0.142 %; h1 edge below the 0.5pp margin).
- **Parliament `ml_gate 0.45`**: `(li)` refused to loosen it — the population it admits
  measures **−0.0168 %/trade**. It now binds all six PM books (every `last_skip` is
  `ml-gate`, p_win 0.23–0.43 against the 0.45 bar, zero open positions across the six).

---

## Housekeeping

- **Exposure.** Monday's scoreboard flagged *58 open vs budget 20*. Today `fleet-risk`
  reads gross 17, long 21 / short 2, **light YELLOW, mode `enforce`**, effective-bet
  count 11.3, max symbol share 14 % (NVDA), `sym_over: 0`. The two counts measure
  different things — the scoreboard counts every open leg on every row (⚖️'s 10 basket
  legs, 🎸 Barnes's 11), `fleet-risk` counts only its registered consumers. Not a breach
  of the budget the veto actually enforces.
- **🎸 `band-barnes-lshadow`** (new on feed, born 06-Aug): n=43, win **16.3 %**, mean
  −0.246 %/trade, −$4.34, MTM DD 0.5 %. Config **birth-frozen until 04-Sep** by design;
  gradeable ~mid-Sep. Too young to judge, correctly untouchable.
- ~~**The repo has had no commits since 07-Aug (six days).**~~ **WRONG — see the
  correction box.** Twelve commits landed on 13-Aug, `(lj)`–`(ls)`. The assessment
  *week* (04→09 Aug) was genuinely quiet — one commit, `(li)` on the 7th — but the
  fleet is not, and the "quietest finding" framing was an artifact of my stale
  checkout, not a measurement.
- **Two books were born today** and are on the feed publishing with build stamps:
  🛢️ `band-garrett-lshadow` and 🏦 `book-kiyosaki-lshadow`, both $0.00 / 0 closes,
  both env-only config with no tuning lane (single-policy clocks by construction).
  Fresh 30-day clocks; gradeable ~mid-September. Nothing to judge yet — noted so
  next week's scoreboard NEW flags are expected rather than investigated.

---

## IMPLEMENTED THIS AFTERNOON — `(lv)`, pushed to main

The section (c) defect is closed in code, and the fix is **narrower than what this
report first recommended**, because that recommendation had already been measured and
refused.

**What was wrong:** `fleet_bus.allocation_scale` was returning **4.0×** for 🌾 carry
off a claim computed on 91 closes from a declared two-writer window, with the organ's
own `claim_era: null` sitting unread in the same row.

**What shipped:** a book may be scaled **above** the flat allocation only while its
era-scoped claim is a positive number.

- **The ranking is untouched** — `(kc)`'s measurement that era-scoping the *ranked*
  claim empties the organ still governs. What it never weighed is the consumer,
  because on 05-Aug there wasn't one; `(jr)` added it four days later.
- **Expand-only.** The 25 % probe floor still comes from the all-time claim, so this
  can only make a book smaller than an *unearned expansion*, never smaller than the
  floor it needs to earn evidence at all (I17). It reverses itself with no
  intervention once the era sample reaches `MIN_N` with a positive bound.
- **Fail-closed on every unknown** — absent key, `None`, `NaN`, string, bool.
- **Measured effect: one book moves, 🌾 carry 4.0× → 1.0×.** ⚖️ Counterweight and the
  Farmer's shadow arm are at 0.25× and are untouched. **Real money reads none of this**
  — AST-pinned, unchanged. **Immediate realised cost: $0** — carry holds nothing and
  its census reads 0 eligible of 219 scanned, so the 4× was sizing nothing.
- **Mutation-verified ×5**, plus a sixth defect the tests caught on their first run:
  `float(ce)` coerces the string `"0.5"` and granted the full 4.0×.

It reaches the funding containers on this push (`fleet_bus.py` is on their deploy
paths); **verify by the `extra.build` + `extra.build_n` stamps**, never by the green
run.

### Carried into next pass (I11)

1. `crypto-breakout-4h-lshadow` retirement — operator decision, both halves.
   **This is now the only open item from section (d).**
2. ⚖️ Counterweight keep-or-retire — pre-registered for the operator ~28-Aug.
3. Watch 🌾 carry's `n_era` toward 20: that is what re-earns its expansion, and at
   0 eligible of 219 scanned the binding constraint is the venue, not capital (I18).
