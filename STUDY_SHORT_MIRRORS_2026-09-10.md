# Two short books like 👩 mum and 🙏 avo — measured, and both refused

**Eamon, 10-Sep-2026:** *"On days like today where the market is down, we need 2
bots that work like Avo and mum that short these sorts of occasions."*

**Verdict: the literal two-book mirror does not survive its own measurement, and
that refusal is what motivated `lighter_adaptive_ensemble_bots`.** This is a
first-class outcome, not an evasion — a refusal with evidence is the doctrine's
own standard, and here it saved two rows, two clocks and two capital slots.

Instrument: `scripts/study_short_mirrors_2026-09-10.py`
Raw output: `lighter_adaptive_ensemble_bots/docs/short_mirror_raw.txt`

---

## The two cells

The mirrors are exact, taken from the shipped carriers rather than invented:

| | 👩 mum — `OversoldRebound` (1h, LONG) | mirror **S1** (1h, SHORT) |
|---|---|---|
| entry | `rsi(14) < 38` **and NOT** `e50>e200` | `rsi(14) > 62` **and NOT** `e50<e200` |
| bracket | roi 2.0%→0 over 24h, stop −4%, max hold 24h | identical in magnitude |

| | 🙏 avo — `SwingDip` (4h, LONG) | mirror **S2** (4h, SHORT) |
|---|---|---|
| entry | `e50>e200` **and** `rsi<42` **and** `close < BB_lo` | `e50<e200` **and** `rsi>58` **and** `close > BB_hi` |
| exit | `rsi>65` or close ≥ sell-zone | `rsi<35` or close ≤ buy-zone |
| bracket | roi 20/12/6/0 over 14d, stop −10% | identical in magnitude |

Tape: Lighter's own candles, 24 crypto books ≥ $1M/24h by volume — **208 days at
1h, 500 days at 4h**. LAG-1 entry (signal at bar *i*'s close, fill at *i+1*'s
open), bracket walked forward from the entry bar including its own post-open
range, stop wins a same-bar tie, friction charged per side and reported at four
levels.

## The calibration gates, both passed before any verdict was read

**Positive control — 6 of 6 arms exact.** A planted drift must be recovered on
both sides through all three exit branches:

| arm | planted | recovered | branch |
|---|---|---|---|
| long / short · max_hold | ±2%/day, 24h hold | **+2.000%** | 100% `max_hold` |
| long / short · roi | ±40%/day | **+2.000%** (the ladder bar) | 100% `roi` |
| long / short · sl | ∓40%/day | **−4.000%** (the stop) | 100% `sl` |

A walker whose short side were sign-flipped would read every short cell
backwards; this is what rules that out.

**Long reproduction — reported, and it does NOT match the live books.** Run
through the same walker, mum's own cell reads −0.034%/trade (t=−0.64) and avo's
−0.660% (t=−0.98). So this harness grades a **cell over a volume-ranked
universe with modelled fills**, not either book. Stated plainly because it
bounds what the numbers below can claim. It does corroborate `(qu)`: avo's entry
had already been measured as carrying no exit-free edge, and it reads negative
here too.

---

## S1 — the mum mirror: REFUTED

| rsi bar | n | mean%/trade | t | h1 | h2 | closes/30d | med hold |
|---|---|---|---|---|---|---|---|
| 58 | 3495 | −0.108 | −2.51 | −0.103 | −0.113 | 534.7 | 3.0h |
| 60 | 3077 | −0.110 | −2.39 | −0.066 | −0.154 | 470.8 | 3.0h |
| **62** | **2744** | **−0.102** | **−2.08** | −0.056 | −0.148 | 419.8 | 3.0h |
| 64 | 2334 | −0.138 | −2.59 | −0.078 | −0.199 | 357.1 | 3.0h |
| 66 | 1995 | −0.153 | −2.64 | −0.026 | −0.279 | 305.2 | 3.0h |
| 70 | 1402 | −0.183 | −2.60 | −0.064 | −0.302 | 214.6 | 3.0h |

* **Negative at every bar**, both halves, t between −2.08 and −2.64.
* **Random-entry null (hm): excess +0.037%/trade, P(random ≥ signal) = 0.187.**
  The cell is indistinguishable from drawing an entry minute at random.
* **The loss is friction.** 0bps/side → −0.002%; 2bps → −0.042%; 5bps → −0.102%;
  10bps → −0.202%. At 420–535 closes/30d and a 3-hour median hold this is a
  turnover pump: it pays the spread ~450 times a month to harvest ~zero.
* Win rate **69%** — and it loses money. The clearest possible restatement of
  the fleet's own I15: *win rate is not expectancy.*

**Refused.** Not "unproven" — measured negative at every reachable setting, with
the mechanism identified.

## S2 — the avo mirror: NOT refuted, but NOT a book

| rsi bar | n | mean%/trade | t | h1 | h2 | closes/30d |
|---|---|---|---|---|---|---|
| 52 | 425 | +0.352 | +0.85 | +0.971 | −0.263 | 28.1 |
| 55 | 416 | +0.364 | +0.88 | +1.050 | −0.322 | 27.5 |
| **58** | **398** | **+0.389** | **+0.93** | **+1.144** | **−0.366** | 26.3 |
| 61 | 370 | +0.315 | +0.71 | +0.791 | −0.162 | 24.5 |
| 64 | 322 | +0.043 | +0.09 | +1.004 | −0.919 | 21.3 |
| 68 | 244 | −0.203 | −0.34 | +0.326 | −0.732 | 16.7 |

**What is genuinely good here:**
* **Excess over matched-random entries +0.319%/trade** (null +0.070%), the right
  direction and ~9× S1's.
* A **plateau**, not a lucky cell — +0.35/+0.36/+0.39/+0.32 across four adjacent
  bars, so the shipped value is not perched on a spike.
* **Selection premium only +0.15 t-units** (best +0.93 vs median +0.78 over six
  cells) — a small price for picking, unlike the ~1.85 t-units `(uz)` measured
  on mum's universe widening.
* **Friction-robust**: +0.489% at 0bps → +0.289% at 10bps.

**What refuses it as a BOOK:**
* **t = +0.93** and **P(random ≥ signal) = 0.137** — not significant.
* **h2 is NEGATIVE** (+1.144 / −0.366): it fails the go-live gate's both-halves
  bar outright.
* **days-to-gate 2,092** at 26.3 closes/30d. I22's bar is **60**. A design that
  cannot be decided inside 60 days is a STUDY, not a book — it does not get a
  row, a clock, capital or a budget slot.

**So: kept as a measured hypothesis, denied a row.**

---

## Why this produced an ensemble instead of two books

I22's arithmetic is the whole argument, and it is not rhetorical:

> With one decision per period `t = S_d·√T`, so **days-to-gate = (2/S_d)²**, and
> for independent sleeves **`S_d² = Σ S_i²`**. Decidability is ADDITIVE, so one
> construct is one term in that sum and a single-sleeve book earns a decision
> more slowly **by the square**.

S2 is one term. At `S_d` implying 2,092 days it is not a slow winner; it is a
sample nothing can grade. **Eamon said the same thing in his own words on
20-Aug:** *"everything you have put forward that is unreachable is because its
one construct, one set of tradeables, one set of entry and exits which havent
been explored properly."*

`lighter_adaptive_ensemble_bots` is that diagnosis taken seriously: several
independent setups, scored together, long **and** short, on a venue-wide
universe, with the decidability arithmetic in the reporting rather than
discovered a year later.

**And S1's refutation is written into the code, not just this file.**
`signals.momentum_component` caps RSI at 15 of 100 points and scores an RSI
extreme at ZERO for a short — the naive overbought fade cannot be an entry by
construction. `tests/test_signals.py::test_an_rsi_extreme_scores_ZERO_on_momentum_for_a_short`
pins it and cites these numbers.

## What was NOT done, and why

* **No row was minted.** I20 requires naming the supply and every living book
  whose gate already admits it; I22 requires publishing the spend with
  days-to-gate ≤ 60. S1 fails on edge, S2 on decidability. Neither clears the
  gate, so neither gets a name — the Portuguese-cohort naming rule is explicit
  that a good name is not a reason to mint a book.
* **No existing book was touched.** mum and avo are unchanged.
* **The instrument is kept** (`scripts/study_short_mirrors_2026-09-10.py`) so
  the S2 plateau can be re-read on fresh tape without re-deriving it.

## Honest limits of this study

1. The harness does not reproduce either live book's mean, so it speaks about
   **cells**, not about mum or avo.
2. The universe is **volume-ranked and therefore churns**; `(oe)` measured that
   universe choice alone can move `t` by 3.82 on a similar gate. The plateau
   across RSI bars is reassuring; a coin-resample was not run.
3. Funding is modelled at **zero for the short side**. A short RECEIVES the
   +0.0171%/day carry `(ro)` measured on majors, so S2's real economics are
   slightly better than shown — conservative, and stated.
4. The 4h tape is 500 days of one venue. Item 18's regime caveat applies in
   full: a directional short graded on a mostly-falling tape has been graded in
   that regime only.
