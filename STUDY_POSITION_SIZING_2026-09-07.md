# STUDY — position sizing: five rules on one ladder of risk

**Date:** 2026-09-07 · **Instrument:** `scripts/study_position_sizing_2026-09-07.py`
· **Status: REPORTED. Nothing moved — no lever written, no clip changed, no
capital allocated.** The instrument asserts that about itself in its own
selftest (a source scan for `write_levers` / `market_open` / `publish` /
`set_status` / `get_lever`), and 11 of 11 mutations reddened its guards.

---

## 0. The verdict, before the tables

> **THE RULE BARELY MATTERS. THE RUNG IS EVERYTHING.** Held at one common risk
> level across all 14 calibrated books, the five sizing rules land within
> **1–7%** of each other on return and **±22%** on drawdown. Move the rung one
> notch instead — 0.25% → 1% of equity risked per position — and the median
> book's p95 drawdown goes from inside the go-live bar to **over half the
> account**. Sizing policy is a choice of NUMBER, not a choice of FORMULA, and
> the fleet has spent its attention on the formula.
>
> **THE ONE RULE THAT PAYS FOR ITSELF is quarter-Kelly on the LOWER BOUND** of
> the mean, not the mean: same return as mean-based Kelly (+6.7% vs the fixed
> dollar baseline), **21.7% less drawdown** and 6% less volatility. Every other
> difference between the five is noise at a conservative rung.
>
> **FIXED DOLLAR IS THE ONLY ONE OF THE FIVE THAT CAN ZERO AN ACCOUNT.** It
> never de-risks after a loss, so on a losing book its bootstrap reaches −100%
> (max P(ruin) **0.166** across books at the 0.5% rung). Every compounding rule
> has P(ruin) = 0.00 at every rung, because a fraction of a shrinking equity
> cannot reach zero. Strict ruin is therefore the wrong question for this
> fleet; **P(drawdown > 50%) is the right one**, and it goes 0.00 → 0.82 → 1.00
> across 0.25% → 0.5% → 1%.
>
> **THE PROPOSAL IS CAPPED HARD AND REFUSES MOST BOOKS.** 11 of 14 books get NO
> proposed size, each with a stated reason. The three that do are the three
> with a measured positive edge bound. **The one real-money finding: 👩 mum's
> live arm runs at 1.67% risk per position against a proposed 0.25% — 6.7×.**
> That reading rests on 10 trading days and is the thinnest in the table, so it
> is a flag rather than a mandate; but it is corroborated from a completely
> independent direction by her own published row (below).

---

## 1. What the fleet does today — the review of the existing logic

There are **four different sizing bases** running simultaneously, and **five
multiplicative modifiers** layered on top of them:

| where | rule | shape |
|---|---|---|
| 👩 mum live, 🙏 avo live (`lighter_avo_live_bot.clip_usd`) | `equity × GROSS_X / max_open` | **fixed fraction**, compounding |
| 🎫 the taker (`lighter_ticket_taker.vol_clip`) | `RISK_USD / (day_range/2)`, bounded `[20, 70]` | **risk-per-trade**, volatility-scaled |
| the family shadows (`lighter_family_bot.STAKE_USD`) | `$50` flat | **fixed dollar** |
| the funding books | fixed notional ($80–$300) | **fixed dollar** |

Modifiers, all multiplicative: the brain's conviction `[1/6.7, 6.7]`; the
allocation organ's evidence scale `[0.25, 4.0]`; the 7-day fleet drawdown
governor `{1.0, 0.5, 0.25}`; the `(wu)` drawdown rail (1.0 to the 15% bar, then
down to 0.25 at twice it); and `SafetyRails`' operator notional cap, which is a
hard boolean rather than a scale.

**THE GAP THIS STUDY FILLS.** Every one of those is expressed in DOLLARS or in
a multiplier on dollars. **Not one place in the fleet computes the quantity
that actually governs survival — risk at the stop, per position, as a fraction
of equity.** So a $50 flat stake behind a 1.5% stop and a $240 clip behind a 4%
stop cannot be compared, and were not. On the common axis `rho = f × s`:

| book | per-position notional | stop | **rho** |
|---|---|---|---|
| 🙏 avo live | 33.3% of equity (2× / 6 slots) | 10% | **3.33%** |
| 👩 mum live | 41.7% of equity (5× / 12 slots) | 4% | **1.67%** |
| 🎫 the taker | `RISK_USD` $3 on $1,000, by construction | — | **0.30%** |
| 🏛️ turnbull | ~$25 clip | 1.5% | **0.04%** |

That is an **83× spread in risk per position across one fleet**, and no organ
had ever printed it. The taker is the only book already sizing by risk, and it
is the one sitting closest to what this study concludes is right.

---

## 2. The instrument, and what its calibration certifies

`rho = f × s` puts every rule on one axis. The unit of risk is the **UTC trading
day**: `R_day = Σ rᵢ` over that day's closes on a unit clip. Positions sized on
the same equity and lost together are one observation, not several — `(xy)`
already ruled that 👩 mum's 8-leg halt is ONE draw.

**THE FIRST CUT OF THIS GOT THE UNIT WRONG, and its own output caught it.**
Version one chained trades by overlap (a trade joins the batch if it opens
before the batch's latest close). That is single-linkage clustering: on a book
continuously in the market it collapses the whole history into one cluster —
measured on 🎫 the taker, **183 closes became 5 "batches", one of them 108
legs**. A calendar day cannot do that.

Two fail-closed gates, both of which REFUSE rather than warn:

1. the sample must reproduce the LIVE `golive-readiness` grade exactly
   (`edge_audit.calibrate`, imported — the one owner of the era / quarantine /
   phantom / adopted pipeline);
2. this module's own path arithmetic must reproduce each graded book's
   published realised drawdown from `pnl_abs` in close order, to 0.05pp.

**Scope, stated rather than assumed:** only the **14 books the live grade
covers** are studied. A retired book's history is not certified by gate 1 and is
skipped by name. Horizons are capped at **10× each book's own span** (the edge
audit's quotability rule) — the first run projected mum's live book 19.2×.

---

## 3. The five rules at one common rung — the comparison asked for

At **0.5% risk per position**, across all 14 books, median ratio to fixed
dollar. Holding the rung fixed is what isolates the RULE from the book.

| rule | ret p50 | ret p05 | maxDD p95 | vol/day | P(dd>50%) | max P(ruin) | peak gross |
|---|---|---|---|---|---|---|---|
| fixed_dollar | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | **0.166** | 1.000 |
| fixed_fraction | 1.010 | 1.012 | 1.004 | 1.043 | 0.000 | 0.000 | 1.000 |
| vol_adjusted | 1.024 | 1.015 | **1.105** | **1.152** | 0.000 | 0.000 | **1.469** |
| risk_per_trade | 1.010 | 1.012 | 1.004 | 1.046 | 0.000 | 0.000 | 1.000 |
| kelly_half | 1.069 | 1.080 | 0.964 | 1.043 | 0.000 | 0.000 | 1.000 |
| kelly_quarter | 1.067 | 1.080 | 0.968 | 1.043 | 0.000 | 0.000 | 1.000 |
| **kelly_quarter_lb** | **1.067** | 1.076 | **0.783** | **0.940** | 0.000 | 0.000 | 1.000 |

**Readings, in order of how much they should change behaviour:**

* **The spread is tiny.** Six of seven rules sit inside ±7% on return. At a
  conservative rung the formula is close to irrelevant — which is the strongest
  argument in the table for spending the effort on the rung instead.
* **Quarter-Kelly on the lower bound is the only free lunch**: the same return
  as mean-Kelly with **21.7% less drawdown** and 6% less volatility. It is more
  conservative precisely where the estimate is least trustworthy, which is why
  it wins on a fleet whose samples are short.
* **The volatility target is the worst of the compounding rules here.** It buys
  +2.4% return for +10.5% drawdown, +15% volatility and **+47% peak gross** —
  it leans in when trailing volatility is low, and that is exactly when gross
  exposure climbs. On this fleet it is a bad trade.
* **fixed_fraction and risk_per_trade are numerically identical** on most books,
  because a book whose per-trade stops do not vary makes them the same rule.
  They separate only where stops genuinely differ per trade.
* **Fixed dollar is the only one that can wipe an account out.** Its P(ruin) of
  0.166 is not a rounding artifact: a non-compounding rule does not shrink after
  losses, so a bad enough run reaches zero. This was discovered by the report
  section crashing on a division by `1 + (−1.000)`.

---

## 4. The ladder — what each extra notch actually costs

Across books, on fixed fraction, forward:

| rung | max P(equity→0) | max P(dd>50%) | books with P(dd>50%) > 0 |
|---|---|---|---|
| 0.25% | 0.00 | **0.00** | 0 of 14 |
| 0.50% | 0.00 | 0.82 | 2 |
| 1.00% | 0.00 | **1.00** | 6 |
| 2.00% | 0.00 | 1.00 | 8 |
| 3.00% | 0.00 | 1.00 | 10 |
| 5.00% | 0.00 | 1.00 | 10 |

**The practical-ruin cliff sits between 0.25% and 1%.** Below it no book in the
fleet has any path to a halving; above it six do. That is the single most
decision-relevant number in this study, and it is why the hard cap is 2% and the
proposals cluster at 0.25%.

---

## 5. Risk of ruin — the honest answer is two numbers

**Strict ruin (equity reaches zero) is 0.00 for every compounding rule at every
rung, for every book.** That is arithmetic, not a finding about the fleet: a
rule that risks a fraction of current equity cannot reach zero in finite steps.
Reporting it alone would be a check that cannot fail — the shape this repo's own
doctrine calls "a check that inspects nothing reports clean".

**So the binding measure is P(max drawdown > 50%)** — a hole no $1,000 book
recovers from in any relevant horizon. It is 0.00 for every book at 0.25% and
reaches 1.00 for six books at 1%. Both are published per book and per rung.

---

## 6. The proposals — and the eleven refusals

`rho* = min(2%, ½ × the largest rung with P(ruin)=0, p95 DD ≤ 15%, peak gross ≤
2×)`. The rule reads **ruin, drawdown and gross only — never a return column**,
and its selftest permutes every return field to prove they cannot move it.

**Edge enters exactly once, as a precondition, and this study's own first output
is why.** 🎯 the perp sniper has a NEGATIVE measured mean (t = −0.78) and still
earned a 0.25% proposal, purely because at that size it loses slowly enough to
keep its drawdown inside the bar. A rule that reads no returns cannot tell *safe
because it wins* from *safe because it loses slowly*. So a book is sized at all
only while its I16 lower bound is positive — this fleet's own **I24**, *scale a
coin flip and you scale a coin flip*.

| book | running | admissible | **rho\*** | edge LB | verdict |
|---|---|---|---|---|---|
| 👩 mum live | **1.67%** | 0.5% | **0.25%** | +0.157% | **CUT 6.7×** |
| 👩 mum shadow | 0.21% | 0.5% | 0.25% | +0.279% | at |
| 🙏 avo shadow | 0.44% | 2% | 1% | +0.821% | headroom |
| 🙏 avo live | 3.33% | — | — | +0.436% | refused: 7 trading days |
| 🎫 the taker | 0.25% | 0.25% | — | +0.609% | refused: half the floor is off the ladder |
| 🌾 carry | 0.72% | 0.25% | — | +0.121% | refused: same, and gross |
| 🔮 georgia, 🔮 v3, 🪁 kelly, 🎯 sniper, ⚖️ counterweight, 🏛️ albanese, 🏛️ turnbull, 📕 bezos | — | — | — | **negative or thin** | refused on I24 or on days |

**Eleven of fourteen books get no proposed size at all.** That is the instrument
working as specified: a book without a measured edge does not get a sizing
recommendation, it gets the allocation organ's probe floor.

---

## 7. The real-money finding, and its corroboration

👩 **mum's live arm runs at 1.67% risk per position; the study proposes 0.25%.**
Her geometry: clip $240 on $576 equity = **41.7% of the account in one position**,
behind a 4% stop, 12 slots, 5× gross.

**This does not rest on the study alone. Her own published row says the same
thing from three independent directions:**

| her own published field | value | against |
|---|---|---|
| `leverage.all_slots_stop_pct` | **0.20** | the go-live bar of 0.15 |
| `leverage.vol_target_at_neff1` | 3.75× | she runs **5.0×** |
| `leverage.stop_reachable` | **false** (`stop_dead_above` 4.17×) | she runs 5.0× |

The third is the sharpest: **on the worst-margin book in her universe the venue
liquidates before her −4% stop fires**, so the stop is dead code there. On what
she actually holds today it is not (`stop_reachable_held: true`, mmf 0.068).

**The one number that argues the other way, stated fairly:** her measured basket
independence is `n_eff` 1.824, and at that credit her own `vol_target_here` is
**5.06×** — she is sized exactly at her measured volatility target. The fleet's
own I22 requires N_eff to be measured, and it is. So this is not a rule
violation; it is a book sized to the aggressive end of its own framework, by a
credit computed on three concurrent positions.

**The limitation, said plainly:** 10 trading days, at the 10× extrapolation cap.
It is the thinnest reading in the table. Treat it as a flag to re-read when her
sample doubles, not as a mandate to cut today.

---

## 8. What fractional Kelly actually wants — and why it is capped

Uncapped to the top of the ladder, on the books with an edge:

| book | half-Kelly | quarter | quarter on the LOWER BOUND | p95 DD at half-Kelly |
|---|---|---|---|---|
| 👩 mum live | 5.00% (at the cap 62% of steps) | 2.92% | **1.45%** | **76.7%** |
| 👩 mum shadow | 5.00% (100%) | 5.00% | 5.00% | 28.5% |
| 🎫 the taker | 2.66% | 1.33% | **0.85%** | **71.1%** |
| 🙏 avo shadow | 5.00% (100%) | 5.00% | 5.00% | 4.0% |

**Every one of these breaks the fleet's own 15% drawdown bar** — half-Kelly on
mum's live book wants a 76.7% p95 drawdown. Fractional Kelly estimated on a
short, hot sample is not a conservative rule; it is a leverage rule wearing a
conservative name. The lower-bound variant roughly halves what it asks for and
is the only one that behaves, which is the same result as the cross-rule table
reached independently.

This is what the **2% hard cap** exists for: the bootstrap is conditional on a
one-regime tape (item 18), and no amount of in-sample optimality earns the right
to a rung the sample cannot support.

---

## 8a. Sensitivity — the proposal does not move with the projection window

Re-run at 3, 6 and 12 months (300 draws each), every proposal is **identical**:

| book | h=3m | h=6m | h=12m |
|---|---|---|---|
| 🙏 avo shadow | 1.00% | 1.00% | 1.00% |
| 👩 mum live | 0.25% | 0.25% | 0.25% |
| 👩 mum shadow | 0.25% | 0.25% | 0.25% |

`rho_adm` does drift down at longer horizons on some REFUSED books (⚖️
Counterweight 0.5% → 0.25% → none; 🏛️ albanese the same), which is the right
direction — a longer path gives more chances to draw down. But no book that
gets a proposal changes it, so the recommendation is a property of the ledger
rather than of the window chosen to project it.

---

## 9. What this does NOT establish

* **Every forward number is conditional on the sample repeating in
  distribution.** The returns compound a measured daily mean; on a short hot
  window they are arithmetically correct and absurd as forecasts. Nothing in the
  proposal reads them, and they should be read ACROSS rules at one rung, never
  as a level.
* **It does not model the venue's liquidation.** That is
  `scripts/lighter_margin_model.py` and the live rows' own `leverage` block. This
  study reports peak GROSS instead, from the ledger's own peak concurrency.
* **The funding books are mapped onto this ladder imperfectly.** 🌾 carry has no
  price stop; its 2% `BLEED_STOP_FRAC` is a P&L threshold standing in for one, and
  ⚖️ Counterweight, being genuinely stopless, gets a proxy stop from the p95 of
  its own losing trades (28.7%). Both are declared on their rows. A delta-neutral
  book's risk unit is basis, not a stop, and this ladder does not measure basis.
* **It changes nothing.** Every number here is reported.

---

## 10. Adversarial review

Five independent lenses were run over the instrument — path arithmetic and
look-ahead, the unit of risk and the resampling, the stop mapping, the proposal
rule, and what the calibration actually certifies — with every finding
adversarially verified by a second agent whose default was REFUTED. Results are
recorded in the CHANGELOG entry for `(yk)`.

Mutation record: **11 of 11 killed** across two rounds — the I24 edge
precondition, the gross ceiling, the ½ haircut, the look-ahead index, the Kelly
`MIN_N` floor, the daily-unit key, the risk-per-trade branch, the drawdown pin's
scale, the fixed-dollar non-compounding path, the volatility ratio's direction,
and the lower-bound sign.
