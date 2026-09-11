# 💸 THE FUNDING FARMER IS A DIRECTIONAL BOOK, AND ITS DIRECTION HAS NEVER BEEN NULL-TESTED

**2026-08-19 (Wed, Sydney) · expansion-research slot · real-money finding ·
VERDICT: founding thesis NOT SUPPORTED (unproven, not disproven)**

## The claim under test

`lighter_funding_bot.py`'s own header states the thesis, and states that it is
the thing that could break:

> "it takes the funding-RECEIVING side of a hot perp ... That means it carries
> PRICE RISK the hedge would have removed. The thesis that makes it more than a
> coin-flip: extreme funding marks crowded positioning that tends to mean-revert,
> so the funding-receiving side is also the contrarian side."

That is a **directional** claim. The fleet has a standing doctrine for exactly
this — *"GRADE A DIRECTIONAL BOOK AGAINST A RANDOM-ENTRY BENCHMARK, NEVER
AGAINST ZERO"* (30-Jul `(hm)`) — and it has never been applied to this book or
its variants, because they are filed under "funding". This file applies it.

Books in scope: 💸 `perps-funding-lighter-lighter` (**REAL MONEY**), 💸
`perps-funding-lighter-lshadow` (the experiment judge's arm), 🛢️
`band-garrett-lshadow` (a variant instance of the same file, on a 30-day clock
to ~12-Sep).

---

## 1 · The P&L decomposition — the funding gate is not what moves this book

From the ledger, mirroring production's own formula
(`pnl_abs = price_pnl + fund_pnl`; `pnl_pct = pnl_abs / entry_clip`), so
`price_pct` is the signed price return **exactly** and `funding = total − price`.
Era-scoped to `POLICY_ERA["perps-funding-lighter"] = 2026-07-17`.

| book | n | shorts | med hold | TOTAL %/tr (t) | **price** %/tr (t) | funding %/tr (t) | price share |
|---|---:|---:|---:|---:|---:|---:|---:|
| 💸 Farmer LIVE | 104 | 95% | 6.17h | +0.1266 (0.73) | **+0.1095 (0.63)** | +0.0171 (7.14) | **86.5%** |
| 💸 Farmer shadow | 153 | 90% | 7.42h | +0.0145 (0.08) | +0.0079 (0.04) | +0.0066 (2.86) | 54.6% |
| 🛢️ Garrett (all-time) | 22 | 77% | 27.84h | −0.8288 (−1.06) | **−0.8360 (−1.05)** | +0.0072 (0.20) | **100.9%** |

**The price term is exact** (direct from recorded fills). **The funding term is a
residual and is only quotable on the LIVE arm**, where it carries the accrual
signature: 98/104 positive, median implied APR **10.25%** (coherent with a 5%
entry gate and a 1.875% exit), and a partial correlation with `|price|` of only
**+0.148** once hold is controlled, against **+0.470** for hold controlling for
`|price|`. On the shadow arms the residual is 52.6% positive with incoherent
implied APRs — contaminated, **not quoted**.

## 2 · Why this is structural, not a bad month

Funding is a **drift** (linear in hold); price is **noise** (∝ √hold). Measured
against each book's own gate (`enter_apr` 0.05) and its own realised holds:

| book | mean \|price\| | max funding at its own gate | ratio | at 20% APR | ratio |
|---|---:|---:|---:|---:|---:|
| 💸 Farmer LIVE | 1.0626% | 0.0066% | **162×** | 0.0263% | 40× |
| 💸 Farmer shadow | 1.4603% | 0.0082% | 178× | 0.0328% | 45× |
| 🛢️ Garrett | 2.3523% | 0.0176% | 133× | 0.0705% | 33× |

Fitting `|price| = k·√H` gives the hold at which funding would finally exceed
the price noise it is carried against:

| APR | crossover hold (Farmer LIVE) |
|---|---|
| 5% (the shipped gate) | **449,858 h ≈ 51 years** |
| 20% | 28,116 h ≈ 3.2 years |
| 100% | 1,125 h ≈ 47 days |

The book's `max_hold_h` is **72**. **At any reachable APR and any reachable hold,
this book's P&L is its price bet.** The carry is real and reliable; it is a
rounding error on the distribution the go-live gate actually grades.

## 3 · The random-entry null

**Construction:** same coin, same side, same hold duration, **random entry time**
drawn from the same window — holding regime, coin mix, side mix and horizon
constant and varying **only the timing**, which is exactly what the funding gate
claims to supply. 5m Lighter candles (8 + 19 coins, ~10,200 bars each),
4,000 book-replications, seed 20260819.

**Calibration gate first** (a harness that cannot reproduce what DID happen may
not say what WOULD have), paired per-episode:

| book | corr(ledger, 5m replay) | paired diff | t |
|---|---:|---:|---:|
| 💸 Farmer LIVE | **+0.9958** | −0.0479 pp | −2.87 |
| 💸 Farmer shadow | +0.9975 | −0.0177 pp | −1.31 |
| 🛢️ Garrett | +0.9982 | −0.0245 pp | −0.51 |

*Declared wedge:* the live arm's ledger reads ~4.8 bps/trade **better** than the
5m close basis — small, systematic, in the book's favour. The null is computed on
the **same** 5m basis as the actual, so the comparison never crosses bases (I14).

**Result:**

| book | n | actual (5m basis) | random-entry null | **P(random ≥ actual)** | verdict |
|---|---:|---:|---:|---:|---|
| 💸 **Farmer LIVE (REAL MONEY)** | 104 | +0.0701% | +0.0185% | **0.382** | **no edge demonstrated** |
| 💸 Farmer LIVE — shorts only | 99 | +0.0571% | +0.0242% | 0.426 | no edge demonstrated |
| 💸 Farmer shadow | 133 | −0.0377% | +0.0108% | 0.596 | **worse than random** |
| 💸 Farmer shadow — shorts only | 129 | −0.0378% | +0.0080% | 0.587 | worse than random |
| 🛢️ **Garrett** | 22 | −0.8604% | −0.1858% | **0.944** | **worse than random** |

**Not concentration.** Per-coin cumulative price return, Farmer LIVE in-era:
HYPE +7.185% (n=30) · SOL +2.881 (19) · ETH +2.833 (28) · SKHYNIXUSD +3.925 (5) ·
ZEC +5.495 (2) · LIT +2.106 (4) · BTC −3.613 (13) · XAU −9.424 (3). No single
coin carries or rescues the result.

## 4 · Decidability

The live arm's excess over random is **+0.0516%/trade** against a per-trade price
sd of **1.770%**. At t=2.0 that needs **4,709 closes ≈ 4.0 years** at its own
measured 3.25 closes/day.

The fleet's own horizon organ says the same thing from its own independent
sample (`golive-readiness`, live payload today):

- 💸 Farmer LIVE — `t=0.29`, *"needs ~1320d at the measured rate (3.22/d) —
  beyond the 90d horizon; I17"*
- 💸 Farmer shadow — `t=0.06`, *"needs ~36346d"* (≈100 years)
- 🛢️ Garrett — `t=−1.05`, *"mean −0.922% ≤ 0 — more of the same closes cannot
  flip mean/t/halves"*

This is a **fourth undecidability class**, beside I17's slow clock, `(oj)`/`(po)`'s
fat tail and `(pm)`'s redundancy: **undecidable by swamping** — the book produces
closes at a healthy rate, but the quantity it is built to harvest is two orders of
magnitude below the noise it is carried in.

## 5 · A methodological correction to `(hm)` itself

`(hm)` records *"a random short earns +0.2% to +1.1%/trade for free"* on this
tape, and that number gets quoted fleet-wide. **It was measured at the Ticket
Taker's horizon.** At the Farmer's horizon (6h median hold, majors) the measured
random-short premium is **+0.018% to +0.024%/trade** — an order of magnitude
smaller. **The free-short premium is horizon-dependent; measure it at the book's
own horizon, never quote it across books.** Same shape as I14, applied to the
null rather than to a grade.

## 6 · What this does and does not say

**Does not say:**
- ❌ Not that the Farmer loses money. Its live row is **+$5.74 realised on real
  money** and its in-era total is +0.1266%/trade.
- ❌ Not that funding is zero — on the live arm it is positive and remarkably
  consistent (t=7.14). It is *small*, not absent.
- ❌ **Not disproven — UNPROVEN.** P=0.382 means n=104 cannot distinguish this
  book from matched random timing. Garrett's P=0.944 is on n=22: suggestive,
  not decisive.

**Does say:**
- ✅ 86.5% of the live book's per-trade return is a **price** term, and that term
  does not beat a matched random-entry null.
- ✅ The founding thesis (extreme funding ⇒ crowded ⇒ mean-reverting) is **not
  supported on Lighter's own tape** at the samples available.
- ✅ The arithmetic in §2 means **no amount of gate tuning can change this**: at
  5% APR and a 72h cap the carry cannot reach the price noise.

## 7 · Consequences named (escalated — nothing applied)

1. **🛢️ Garrett's ~12-Sep keep-or-retire call.** The gate already reads
   `unreachable`; this supplies the *mechanism* — 100.9% of its loss is price,
   and its price term is beaten by random entries 94% of the time. **Operator
   decision; no action taken here.**
2. **💰 `fleet_allocation` points 85% of the capital pointer at the funding class**
   ($15,250 target vs $7,000 current) on **two** claims: 🌾 carry 0.1492% and
   💸 Farmer LIVE **0.0112%**. The Farmer's claim is ~86% a price term with no
   demonstrated edge. **Real money never reads the organ** (AST-pinned,
   `tests/autonomy/test_allocation_consumer.py`) — but three funding *shadow*
   books size new entries off it since `(jr)` S1.
3. **Standing practice gap:** the directional-funding family is filed as
   "funding" and so has never been put through `(hm)`'s null. 🌾 carry, 🏦 Rich
   Dad and 🧮 Hull are delta-neutral **modelled** (no price term by construction)
   and correctly exempt. 💸 ×2 and 🛢️ are not.
4. **No recommendation to retire the live Farmer.** It is real money, positive,
   and the honest reading is "unproven". That is an operator call.

## Reproduction

Scratchpad harnesses (read-only, seeded): `decomp.py` (ledger decomposition,
mirrors production's close path) · `diag.py` + partial-correlation check
(funding vs lot-rounding) · `snr.py` (signal-to-noise + crossover hold) ·
`fetch_tape.py` (5m Lighter candles, direct REST) · `null_v2.py` (paired
calibration + random-entry null). Lighter tape only, per the venue-purity rule.

---
---

# PART 2 — AND THE GATE DOES NOT SUPPLY SELECTION EITHER: FUNDING IS A FAIR PRICE FOR THE ADVERSE SELECTION IT SIGNALS

**Same day, second measurement.** Part 1 showed the gate supplies no *timing*.
This is the orthogonal question — does it supply *selection*? — and it is the
one that decides **re-express vs retire**.

## The pool the gate actually chooses from

Reconstructed from the scout's own `bot_state_history['lighter-market']`
snapshots — the venue read the bot itself gates on. **5,752 snapshots at 5-min
cadence, 29-Jul → 18-Aug** (retention limits history to 29-Jul; `funding` is
`apr_pct`, TRUE since 17-Jul, `true_apr_divisor: 1.0`).

At the Farmer's own `min_vol` of **$10M**, the eligible pool is:

| | |
|---|---|
| coins EVER eligible in 20 days | **13** (of 210 books) |
| pool size per snapshot | min 4 · median **7** · max 11 |
| always eligible | BTC, ETH, SOL (100%), HYPE (98.3%) |

**The gate has almost nothing to filter.** It picks 1 of ~7, and 4 of those 7
are always the same coins. Note also that the Farmer has **no class screen** —
deliberate, and re-affirmed 16-Aug — so XAU, WTI, SNDK, SKHYNIXUSD, SPCX, MU and
USDJPY are all in its pool.

## Design — paired, so market drift cancels exactly

At each period *t*: eligible = `vols ≥ $10M` with a funding reading; rank by
`|apr|` descending; side = short if `apr > 0` (the bot's own rule,
`lighter_funding_bot.py:2817,2842`). Then

    diff_t = return(rank-1) − mean(return over ALL eligible)

Under the null that funding rank carries no cross-sectional information,
E[diff] = 0 **regardless of what the tape did** — both sides of the pair are
receiving-side positions at the same instant, so the single falling-BTC regime
cannot manufacture a result here.

**Both halves are measured**: price return *and* the funding actually collected
(`|apr|·H/8760`), because the gate's fair defence is *"yes the price goes
against you — that is what you are being paid for."*

## Result — the two halves cancel

| H (non-overlapping) | n | price diff | funding edge | **TOTAL diff** | t |
|---|---:|---:|---:|---:|---:|
| **6h (primary — the book's own median hold)** | 80 | −0.0440% | +0.0444% | **+0.0003%** | **+0.00** |
| 24h | 20 | −0.0780% | +0.2140% | +0.1360% | +0.09 |
| 2h | 241 | +0.0094% | +0.0131% | +0.0225% | +0.30 |
| 6h, restricted to the bot's own 5% admission gate | 70 | −0.0506% | +0.0423% | −0.0083% | −0.04 |

**The funding almost exactly pays for the adverse price selection.** Total edge
at the book's own horizon and own gate: **+0.0003%/period, t=0.00**.

**Overlapping-window t-stats are inflated and are NOT quoted.** The 1h-sampled
series (477 periods, 5/6 overlap) gives naive `t=−1.61` on price and `t=−2.70`
on top-3 — both dissolve under a moving-block bootstrap (block = 1 day, 5,000
replications):

| | mean | naive t | **block-boot 95% CI** | P(mean ≥ 0) |
|---|---:|---:|---:|---:|
| price diff | −0.1459% | −1.61 | **[−0.548%, +0.180%]** | 0.228 |
| TOTAL diff | −0.1027% | −1.14 | **[−0.500%, +0.210%]** | 0.302 |

Quoting the naive `t=−2.70` would have been wrong; recorded so nobody does.

## This corroborates a refutation the fleet already made — and refines it

**22-Jul, 🏹 Tamerlane** (`backtest_funding_tail_raid_lighter.py`, 150d, 37
books): raiding the receiving side of extreme funding prints is dead in **25 of
25 cells**, because *"price adverse-selection scales with the extremity and eats
it."* That study rejected a **proposed** book. **It was never applied to the
live Farmer, which runs the same mechanism at a 5% gate** — and the same
mechanism was found a third time in `stock-leaders-funding-adverse-selection`.

The refinement this run adds, from the two studies read together:

| gate | adverse selection vs funding | edge |
|---|---|---|
| **extreme** (30–500%, Tamerlane) | adverse selection **>** funding | **negative** |
| **mild** (5–25%, the Farmer) | adverse selection **≈** funding | **zero** |

**Adverse selection scales with extremity, and so does the funding — they scale
together. There is no threshold at which this mechanism pays.** That is a
stronger and more general statement than either study alone, and it closes the
class rather than adding a 26th dead cell.

## Consolidated verdict across both parts

The funding gate supplies **neither timing** (Part 1: P(random ≥ actual) = 0.382
/ 0.596 / 0.944) **nor selection** (Part 2: total cross-sectional edge
+0.0003%/period, t=0.00). Its expected edge is **zero by construction**, because
funding is a fair price for the positioning risk it signals.

That explains Part 1 rather than merely agreeing with it: a book whose gate has
zero expected edge will show exactly what the Farmer shows — **realised P&L that
is price noise centred near zero** (live t=0.73, shadow t=0.08, Garrett t=−1.05).

**Re-expression on this venue has no headroom.** There is no gate setting that
fixes it: Part 1's arithmetic puts the funding/price crossover at ~51 years
against a 72h cap; Part 2 finds the edge is zero at the mild gate and negative at
the extreme one. **The remaining question is not "which parameters" but the I17
keep-or-retire question — and that is the operator's.**

**Still not a claim that the book loses.** The live row is **+$5.74 realised**;
a zero-edge book with a positive carry term and zero venue fees drifts sideways,
which is what 104 in-era closes at t=0.73 look like.

## Reproduction (added for Part 2)

`pull_snaps.py` (scout history → eligible pool) · `xsect.py` (rank test) ·
`xsect2.py` (funding-inclusive + moving-block bootstrap). Tape: 5m Lighter
candles for all 13 ever-eligible coins. Lighter only.
