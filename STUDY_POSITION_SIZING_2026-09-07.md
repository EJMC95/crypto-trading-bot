# STUDY — position sizing: five rules on one ladder of risk

**Date:** 2026-09-07 · **Instrument:** `scripts/study_position_sizing_2026-09-07.py`
· **Status: REPORTED. Nothing moved** — no lever written, no clip changed, no
capital allocated. Asserted by an **AST walk of the module's own call sites**
(not a substring scan: `(po)`'s rule is that a page-wide substring scan is not a
structural claim), and **18 of 18 mutations reddened the guards**, including one
that inserts a `publish()` call into the file.

**Adversarially reviewed** by five independent lenses with every finding verified
by a second reviewer whose default was REFUTED: **10 findings, 9 survived, 2
changed real numbers and are fixed below.**

---

## 0. The verdict, before the tables

> **THE RULE BARELY MATTERS. THE RUNG IS EVERYTHING.** Held at one common risk
> level across all 14 calibrated books, the five rules land within **1–7%** of
> each other on return and **±22%** on drawdown. Move the *rung* one notch
> instead — 0.25% to 1% of equity risked per position — and the books with any
> path to losing half the account go from **0 of 14 to 5 of 14**. Sizing policy
> is a choice of NUMBER, not of FORMULA, and the fleet's attention has been on
> the formula.
>
> **QUARTER-KELLY ON THE LOWER BOUND is the one rule that pays for itself**:
> mean-Kelly's return with **21.7% less drawdown** and 6% less volatility. It is
> also the only rule of the five that **stands a losing book down without being
> told** — on 📕 bezos it sizes to nothing (−51.9% to −3.6%, drawdown 60.0% to
> 6.1%) because its lower bound is negative.
>
> **RISK-PER-TRADE SIZING IS WORSE HERE, on every book that can test it.** Eleven
> of fourteen books run exactly ONE stop, where it is *arithmetically identical*
> to fixed fraction — an identity, not a measured null. On the three books whose
> stops genuinely vary it raised drawdown every time: 🎫 the taker **8.9% to
> 18.2%**, 📕 bezos 60.0% to 66.0%, 🏛️ albanese 20.5% to 21.2%.
>
> **FIXED DOLLAR IS THE ONLY ONE OF THE FIVE THAT CAN ZERO AN ACCOUNT** (max
> P(ruin) **0.166**); it never de-risks. Every compounding rule has P(ruin) =
> 0.00 at every rung, so strict ruin is the wrong question for this fleet and
> **P(drawdown > 50%)** is the right one.
>
> **THE PROPOSAL REFUSES 10 OF 14 BOOKS.** Of the four it sizes, two are cuts:
> 👩 mum's **live** arm runs **6.7x** its proposal, and 🎫 the taker **2.3x**.
> Neither is executed — mum's rests on 10 trading days, so it is **pre-registered
> for a read on fresh days** instead.

---

## 1. What the fleet does today — the review of the existing logic

**Four different sizing bases run simultaneously**, under **five multiplicative
modifiers**:

| where | rule | shape |
|---|---|---|
| 👩 mum live, 🙏 avo live (`lighter_avo_live_bot.clip_usd`) | `equity x GROSS_X / max_open` | **fixed fraction**, compounding |
| 🎫 the taker (`lighter_ticket_taker.vol_clip`) | `RISK_USD / (day_range/2)`, bounded `[20, 70]` | **risk-per-trade**, volatility-scaled |
| the family shadows (`lighter_family_bot.STAKE_USD`) | `$50` flat | **fixed dollar** |
| the funding books | fixed notional ($80–$300) | **fixed dollar** |

Modifiers, all multiplicative: the brain's conviction `[1/6.7, 6.7]`; the
allocation organ's evidence scale `[0.25, 4.0]`; the 7-day governor
`{1.0, 0.5, 0.25}`; the `(wu)` drawdown rail; and `SafetyRails`' notional cap,
which is a hard boolean rather than a scale.

**THE GAP.** Every one of those is denominated in DOLLARS or in a multiplier on
dollars. **Nowhere does the fleet compute the quantity that governs survival —
risk at the stop, per position, as a fraction of equity.** So a $50 stake behind
a 1.5% stop and a $240 clip behind a 4% stop were never comparable. On the common
axis `rho = f x s`:

| book | per-position notional | stop | **rho** |
|---|---|---|---|
| 🙏 avo live | 33.3% of equity (2x / 6 slots) | 10% | **3.33%** |
| 👩 mum live | 41.7% of equity (5x / 12 slots) | 4% | **1.67%** |
| 🎫 the taker | ~8.3% of equity (mean recent clip $83) | 7% | **0.58%** |
| 🏛️ turnbull | ~$25 clip | 1.5% | **0.04%** |

**83x spread inside one fleet, and no organ had printed it.**

*The taker carries two readings and both are true.* Its own rule targets a
constant **$3 of risk = 0.30%** of a $1,000 book, but that is risk at the
*expected adverse move* (half the daily range), while `rho` here is risk at the
*bracket stop*. The two denominators differ, so 0.30% and 0.58% are not a
contradiction — they are one book measured against two different stops.

---

## 2. The instrument, and what its calibration actually certifies

`rho = f x s` puts every rule on one axis. The unit of risk is the **UTC trading
day** (`R_day = sum of r_i` on a unit clip): positions sized on the same equity
and lost together are one observation, which `(xy)` already ruled for 👩 mum's
8-leg halt.

**THE FIRST CUT GOT THE UNIT WRONG AND ITS OWN OUTPUT CAUGHT IT.** Version one
chained trades by *overlap*. That is single-linkage clustering: on a book
continuously in the market it collapses the entire history into one cluster —
measured on 🎫 the taker, **183 closes became 5 "batches", one of them 108 legs**.

Two fail-CLOSED gates, and the second is stated more narrowly than the first
draft claimed (an adversarial reviewer was right to press on it):

1. the sample must reproduce the LIVE `golive-readiness` grade exactly
   (`edge_audit.calibrate`, imported — the one owner of the era / quarantine /
   phantom / adopted pipeline);
2. this module's **trade set and drawdown convention** must reproduce each book's
   published realised drawdown to 0.05pp. **This does NOT pin the compounding
   path arithmetic** — `close_order_dd_pct` is a dollar-additive sum sharing no
   code with `run_paths`. The path arithmetic is pinned by the selftest and by
   mutation, which is where that burden belongs.

**Scope:** only the **14 books the live grade covers**. 27 other rows (retired
history) are skipped BY NAME. Horizons are capped at **10x each book's own span**
— the first run projected 👩 mum's live book 19.2x.

---

## 3. The five rules at one common rung — the comparison asked for

At **0.5% risk per position**, across all 14 books, median ratio to fixed dollar.
Holding the rung fixed isolates the RULE from the book.

| rule | ret p50 | ret p05 | maxDD p95 | vol/day | max P(ruin) | peak gross |
|---|---|---|---|---|---|---|
| fixed_dollar | 1.000 | 1.000 | 1.000 | 1.000 | **0.166** | 1.000 |
| fixed_fraction | 1.010 | 1.012 | 1.004 | 1.043 | 0.000 | 0.988 |
| vol_adjusted | 1.024 | 1.015 | **1.105** | **1.152** | 0.000 | **1.422** |
| risk_per_trade | 1.009 | 1.011 | 1.004 | 1.046 | 0.000 | 0.988 |
| kelly_half | 1.069 | 1.080 | 0.964 | 1.043 | 0.000 | 0.988 |
| kelly_quarter | 1.067 | 1.080 | 0.968 | 1.043 | 0.000 | 0.988 |
| **kelly_quarter_lb** | **1.067** | 1.055 | **0.783** | **0.940** | 0.000 | 0.988 |

* **The spread is tiny.** Six of seven sit inside ±7% on return.
* **Quarter-Kelly on the LOWER BOUND wins**, for a reason that generalises: it is
  most conservative exactly where the estimate is least trustworthy. It is also
  the only rule that **de-sizes a book with no edge automatically**.
* **The volatility target is the worst compounding rule here** — +2.4% return for
  +10.5% drawdown, +15% volatility and **+42% peak gross**. It leans in when
  trailing volatility is low, which is when gross climbs.
* **Fixed dollar is the only one that can wipe an account out**, and its gross
  *rises* as equity falls because its notional is a constant number of dollars.

### 3a. Risk-per-trade: 11 of 14 books cannot test it, and the 3 that can say no

`Q_day = sum of r_i/s_i`, so when a book runs **one stop**, `Q` is identically
`R/s` and risk_per_trade **is** fixed fraction — identical to 4.8e-14, at every
rung, on every metric. Eleven books are in that position, and they genuinely run
one stop; this is the ledger, not an artefact of the harness. **The near-tie in
the table above is therefore mostly an identity, not a measured null**, and the
instrument now publishes `n_distinct_stops` per book so no reader can mistake one
for the other.

On the three books whose stops actually vary, at the common rung:

| book | stops | rule | ret p50 | maxDD p95 | vol/day |
|---|---|---|---|---|---|
| 🎫 taker | 2 | fixed_fraction | +104.5% | **8.9%** | 1.28% |
| | | risk_per_trade | +72.4% | **18.2%** | 1.56% |
| 📕 bezos | 33 | fixed_fraction | −51.9% | 60.0% | 1.50% |
| | | risk_per_trade | −58.7% | 66.0% | 1.62% |
| 🏛️ albanese | 2 | fixed_fraction | −0.6% | 20.5% | 1.06% |
| | | risk_per_trade | +0.5% | 21.2% | 1.13% |

**Higher drawdown and higher volatility on all three.** This reproduces the
mechanism the fleet already measured in `(nt)`: equal-risk sizing charges every
tight-stop loss the full R, while a fixed clip charges it only `s x clip` — so it
concentrates cost exactly where stops are tightest.

---

## 4. The ladder — what each extra notch costs

| rung | max P(equity to 0) | max P(dd>50%) | books with P(dd>50%) > 0 |
|---|---|---|---|
| 0.25% | 0.00 | **0.00** | **0 of 14** |
| 0.50% | 0.00 | 0.82 | 2 |
| 1.00% | 0.00 | 1.00 | **5** |
| 2.00% | 0.00 | 1.00 | 7 |
| 3.00% | 0.00 | 1.00 | 10 |
| 5.00% | 0.00 | 1.00 | 10 |

**The practical-ruin cliff sits between 0.25% and 1%.** That is the single most
decision-relevant number here, and it is why the hard cap is 2% and the proposals
cluster at 0.25%.

---

## 5. Risk of ruin — the honest answer is two numbers

**P(equity to 0) is 0.00 for every compounding rule at every rung** — arithmetic,
not a finding: a rule risking a fraction of *current* equity cannot reach zero.
Reporting it alone would be `(po)`'s check that cannot fail, and the instrument
now says so at the clause itself rather than letting a reader take it for a
passed test.

**The binding measure is P(max drawdown > 50%)** — a hole no $1,000 book recovers
from. 0.00 at 0.25%; 1.00 for five books at 1%.

---

## 6. The proposals, and the ten refusals

`rho* = min(2%, half x largest rung with P(ruin)=0, p95 DD <= 15%, peak gross <=
2x)`. Of the bootstrap it reads **ruin, drawdown and gross only — never a
return**, and its selftest permutes every return field to prove they cannot move
it.

**Edge enters once, as a precondition, and the study's own first output is why.**
🎯 the sniper has a NEGATIVE mean (t = −0.78) and earned a 0.25% proposal purely
because at that size it loses slowly enough to stay inside the bar. A rule
reading no returns cannot tell *safe because it wins* from *safe because it loses
slowly*. So a book is sized only while its I16 lower bound is positive — this
fleet's own **I24**.

| book | running | admissible | **rho\*** | edge LB | verdict |
|---|---|---|---|---|---|
| 👩 mum live | **1.67%** | 0.5% | **0.25%** | +0.157% | **CUT 6.7x** |
| 🎫 the taker | **0.58%** | 0.5% | **0.25%** | +0.609% | **CUT 2.3x** |
| 👩 mum shadow | 0.21% | 0.5% | 0.25% | +0.279% | at |
| 🙏 avo shadow | 0.44% | 2% | 1% | +0.821% | unused headroom |
| 🙏 avo live | 3.33% | — | — | +0.436% | refused: 7 trading days |
| 🌾 carry | 0.72% | 0.25% | — | +0.121% | refused: half the floor is off the ladder |
| 🔮 georgia · 🔮 v3 · 🪁 kelly · 🎯 sniper · ⚖️ counterweight · 🏛️ albanese · 🏛️ turnbull · 📕 bezos | — | — | — | negative or thin | refused on I24 or on days |

**Ten of fourteen books get no proposed size at all** — the instrument working as
specified: a book without a measured edge gets the probe floor, not a number.

**Two of the four proposals RAISE rather than cut** (🙏 avo shadow 2.3x, 👩 mum
shadow 1.2x). Both are paper books running clips far below any sane rung, and
neither is a recommendation to act — they are *unused headroom*, reported.

---

## 7. The real-money reading, and why it is registered rather than executed

👩 **mum's live arm runs rho 1.67% against a proposed 0.25%.** Her geometry: clip
$240 on $576 equity = **41.7% of the account in one position**, behind a 4% stop,
12 slots, 5x gross.

**Her own published row says the same thing from three independent directions,
none of which had been read against the bar:**

| her own field | value | against |
|---|---|---|
| `leverage.all_slots_stop_pct` | **0.20** | the gate's 0.15 bar |
| `leverage.vol_target_at_neff1` | 3.75x | a configured **5.0x** |
| `leverage.stop_reachable` | **false** (`stop_dead_above` 4.17x) | 5.0x — the venue liquidates before her −4% stop fires, on the worst-margin book in her universe |

**The number that argues the other way, stated fairly:** her measured `n_eff` is
1.824, and at that credit her own `vol_target_here` is **5.06x** — she is sized
exactly at her framework's target, and I22 requires N_eff to be measured, which
it is. This is a book at the aggressive end of its own rules, not a violation.

**NOT ACTED ON.** The reading rests on **10 trading days** — the sample floor
exactly, so it dies if any single day is removed. Cutting a real-money clip 6.7x
on ten days of a hot sample is what **I25** forbids. It is **PRE-REGISTERED**
(I21): the at-registration numbers are declared as a commitment, the study prints
the fresh-day count and **DUE NOW** on every run, and the read is graded on days
after 2026-09-07 only, at `n_days >= 30` or 2026-10-07. Carried as
`mum-live-rho-read-preregistered`, whose predicate closes only when the verdict
is written down.

---

## 8. What fractional Kelly wants, and why it is capped

Uncapped to the top of the ladder:

| book | half-Kelly | quarter | quarter on the LOWER BOUND | p95 DD at half-Kelly |
|---|---|---|---|---|
| 👩 mum live | 5.00% | 2.92% | **1.45%** | **76.7%** |
| 🎫 the taker | 2.66% | 1.33% | **0.85%** | **71.1%** |
| 👩 mum shadow | 5.00% | 5.00% | 5.00% | 28.5% |
| 🙏 avo shadow | 5.00% | 5.00% | 5.00% | 4.0% |

**Every one breaks the fleet's 15% drawdown bar.** Fractional Kelly on a short,
hot sample is a leverage rule wearing a conservative name; the lower-bound
variant roughly halves what it asks for and is the only one that behaves. That is
what the **2% hard cap** exists for.

## 8a. Sensitivity — the proposal does not move with the projection window

Re-run at 3, 6 and 12 months, every proposal is **identical**. `rho_adm` does
drift down at longer horizons on 8 of 14 books, which is the right direction (a
longer path gives more chances to draw down) and is structural rather than
bootstrap noise — five RNG seeds move nothing. But no book that receives a
proposal changes it, so the recommendation is a property of the ledger rather
than of the window chosen to project it.

---

## 9. What this does NOT establish

* **Every forward number is conditional on the sample repeating in
  distribution**, on a tape that is one falling-BTC regime (item 18). The returns
  compound a measured daily mean; on a short hot window they are arithmetically
  correct and absurd as forecasts. Read them ACROSS rules at one rung, never as a
  level.
* **The edge precondition is a lower bound against ZERO, not against a
  random-entry null.** For a DIRECTIONAL book `(hm)` says the null is random
  entry, not zero — this instrument has no such benchmark, so its edge gate is
  weaker than the fleet's own standard and a book can pass it on drift alone.
* **The stop is the whole ladder, and two books are mapped onto it imperfectly.**
  🌾 carry's 2% `BLEED_STOP_FRAC` is a P&L threshold, not a price stop; ⚖️
  Counterweight is genuinely stopless and takes a p95-of-losses proxy (28.7%),
  which is an analyst choice and is declared as one. A delta-neutral book's risk
  unit is basis, and this ladder does not measure basis.
* **`MIN_N` is a floor on DAYS borrowed from a floor on TRADES.** They are not
  the same quantity, and mum's live book sits exactly on it.
* **It does not model liquidation** (that is `lighter_margin_model` and the live
  rows' `leverage` block); it reports peak GROSS instead.
* **It changes nothing.**

---

## 10. Adversarial review — 10 findings, 9 survived, 2 changed numbers

Five lenses, each finding verified by a second reviewer defaulting to REFUTED.

**FIXED — these changed the answer:**

1. **CONFIRMED, critical.** `stop_of` read a `bars.brk_sl` key that
   `lighter_ticket_taker.entry_bars()` **never emits** — 0 of 276 stamped rows
   carry it — so the dead branch priced **148 breakout rows at 3% instead of
   7%**, and the selftest *pinned the dead branch against a fixture this file
   wrote itself*: the exact "test the consumer against its publisher's payload"
   defect. Now the CONDITION is read from the ledger's own `policy.bull` stamp
   and the VALUE from the bot's `BRK_SL`, with the selftest asserting against
   `entry_bars()` directly. **The taker's stop went 3% to 7%, its rho 0.25% to
   0.58%, and it went from no proposal to a 2.3x cut.**
2. **CONFIRMED (partial), major.** Peak gross for `fixed_dollar` was computed at
   the constant fraction `f`, i.e. its value at t=0 — but that rule alone holds a
   constant *dollar* notional, so its gross *rises* as equity falls. It
   understated on exactly the losing paths a gross ceiling exists to catch.

**ACCEPTED AS CORRECTIONS TO THE CLAIMS, now stated in the report and the module:**

3. `risk_per_trade` is identical to `fixed_fraction` on 12 of 14 books. The
   reviewer **refuted my attribution** — I blamed the median stop-fill; the real
   cause is that those books genuinely run one stop — and the declaration was
   missing. Now published as `n_distinct_stops`, with its own section above.
4. Calibration gate 2 pins the trade set and the drawdown convention, **not** the
   path arithmetic the docstring claimed, and silently skips a book with no
   published field. Both corrected.
5. `p_ruin <= 0` cannot fail on a compounding rule — declared inert at the clause.
6. `rho_adm` is a monotone function of the `--horizon` knob on 8 of 14 books;
   `rho*` is invariant on every book that gets one. Reported in section 8a.
7. The edge precondition tests against zero rather than the `(hm)` random-entry
   null — a real weakness against the fleet's own standard, declared in section 9.
8. The p95-loss proxy stop is an undeclared free parameter; `MIN_N` is a trade
   floor used as a day floor. Both declared in section 9.
9. `GROSS_CAP_X` borrows `fleet_bus.BRAIN_GROSS_X` outside its owner's declared
   scope, and it — not drawdown — sets the answer on 4 of 14 books. Declared at
   the constant.

**REFUTED:** the claim that sizing every position at its close-day equity
understates drawdown up to 2.25x. The verifier decomposed it and found the effect
is a *sampling-grid* artefact, not a sizing-equity one; isolated, the median ratio
is 1.006, it goes *below* 1.0 on 6 of 14 books, and it moves **0 of 14**
admissible rungs on the criterion `propose()` actually reads.

**Mutation record: 18 of 18 killed** across four rounds — the I24 precondition,
the gross ceiling, the half haircut, the look-ahead index, Kelly's `MIN_N` floor
and lower-bound sign, the daily-unit key, the risk-per-trade branch, the drawdown
pin's scale, the fixed-dollar path and its gross base, the volatility ratio's
direction, the breakout-lens set, the stop read from the bot, the lens parser, an
inserted `publish()` call, and the AST scan's own vacuity.
