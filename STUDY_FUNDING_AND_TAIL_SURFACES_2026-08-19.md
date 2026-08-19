# Four surfaces, priced: the directional-funding family and the illiquid tail

**2026-08-19 · expansion-research slot · seven measurements, Lighter tape only ·
nothing applied**

Operator reframe mid-session: *"We are looking at this as a risk eliminating job
as opposed to a profit motivated job. Let's look at options, even though risk
will be higher."* Accepted, and the numbers agreed: **$259.75 of real money
against $16,026 of paper — 62:1.** What follows is the attempt to find a
surface worth scaling, and the four it closed instead.

Working notes with full method: `reports/expansion_research_log.md` (Parts 1–7)
and `reports/evidence_directional_funding_null_2026-08-19.md`.

---

## 1 · 💸 The Funding Farmer's gate supplies neither timing nor selection

`lighter_funding_bot.py`'s own header states the thesis and states that it is
what could break: *"extreme funding marks crowded positioning that tends to
mean-revert, so the funding-receiving side is also the contrarian side."* That
is a **directional** claim, and `(hm)` requires directional books to be graded
against a random-entry null. It had never been applied here because these books
are filed as "funding".

**P&L decomposition** (ledger, mirroring production's `pnl_abs = price_pnl +
fund_pnl`; era `2026-07-17`):

| book | n | TOTAL %/tr (t) | **price** %/tr (t) | price share |
|---|---:|---:|---:|---:|
| 💸 Farmer **LIVE (real money)** | 104 | +0.1266 (0.73) | **+0.1095 (0.63)** | **86.5%** |
| 💸 Farmer shadow | 153 | +0.0145 (0.08) | +0.0079 (0.04) | 54.6% |
| 🛢️ Garrett | 22 | −0.8288 (−1.06) | −0.8360 (−1.05) | **100.9%** |

**Random-entry null** (matched coin/side/duration, random entry time, 5m tape,
4,000 book-replications; paired calibration `corr(ledger, replay)` = **+0.996 to
+0.998**):

| book | actual | random | **P(random ≥ actual)** |
|---|---:|---:|---:|
| Farmer LIVE | +0.0701% | +0.0185% | **0.382** |
| Farmer shadow | −0.0377% | +0.0108% | 0.596 |
| Garrett | −0.8604% | −0.1858% | **0.944** |

**Structural, not a bad month.** Mean `|price|` is **162×** the maximum funding
the live book can accrue at its own 5% gate over its own holds (40× at 20% APR).
Funding is linear in hold, price noise ∝ √hold: the crossover is **~51 years
against a 72h max hold**.

**A fourth undecidability class — UNDECIDABLE BY SWAMPING.** Healthy close rate,
but the harvested quantity sits two orders of magnitude below the noise it rides
in. The gate's own horizon organ agrees independently: Farmer LIVE `t=0.29`
*"needs ~1320d"*, shadow `t=0.06` *"~36346d"*, Garrett `t=−1.05` *"unreachable"*.

**Selection tested separately.** At the $10M floor the eligible pool is **13
coins EVER / median 7** — the gate picks 1 of ~7. Rank-1 paired against the
equal-weight eligible basket at the same instant (so regime cancels), measuring
**both** price and funding collected:

| H | n | price | funding | **TOTAL** | t |
|---|---:|---:|---:|---:|---:|
| **6h (its own median hold)** | 80 | −0.0440% | +0.0444% | **+0.0003%** | **+0.00** |
| at its own 5% gate | 70 | −0.0506% | +0.0423% | −0.0083% | −0.04 |

**Funding is a fair price for the adverse selection it signals.**

## 2 · The same result at the opposite end of the range

The 22-Jul 🏹 Tamerlane study killed the RECEIVING side of extreme funding in
**25 of 25 cells** — but it rejected a *proposed* book. **The live Farmer runs
the identical mechanism at a 5% gate and was never re-examined against it.**

Running the **mirror** (pay the funding, take the crowded side) on the fleet's
own harness, 25 books × 180d, forced t+1 entry lag: **dead in 24 of 25 cells.**
The one marginal cell (th=1.00/8h, net +11.7bps, t@0.54bps=+2.0) dies on its own
event population — its events are SKHYNIXUSD 939, WTI 788, BRENTOIL 526, MU 214,
i.e. non-crypto and not liquid-tier; charged at the tier those books actually
fill in it reads **t=+1.4 / +0.3**.

**Funding and price cancel in EVERY cell, in BOTH directions**, to within
~10–20% (th=2.00/24h: −51.6 vs +66.8; th=5.00/24h: −80.6 vs +89.6).

| gate | adverse selection vs funding | edge |
|---|---|---|
| extreme (30–500%) | **>** funding | negative |
| mild (5–25%, the live Farmer) | **≈** funding | **zero** |

**They scale together — there is no threshold at which this mechanism pays.**

*Reproduction note: the control run reproduces 22-Jul in direction and mechanism
but not in cell values (different universe, 25 books/180d vs 37/150d). Quoted as
a re-measurement, never a reproduction.*

## 3 · `fleet_allocation`'s claim does not rank

Proposed replacing the go-live STEP function (6 bars incl. `t≥2.0`, which has
**never fired**) with a RAMP sized by I16's `max(0, mean − 1.28·SE)`. Built the
walk-forward simulation — retired books kept in-pool while alive, Kraken/HL-era
books excluded — then tested the foundation:

| | H=7d | H=14d |
|---|---:|---:|
| Pearson(claim, forward) | +0.096 | +0.105 |
| **Spearman(claim, forward)** | **−0.004** | **−0.069** |
| LOW / MID / HIGH tercile | −0.027 / **−0.216** / +0.028% | −0.099 / **−0.385** / −0.015% |
| top-claim minus same-day avg book | +0.052%, CI **[−0.648, +0.404]** | +0.064%, CI **[−0.826, +1.020]** |

**Non-monotone terciles — the middle bucket is worst — is the signature of
noise.** A tranche weighted by this claim would have deployed real capital on
noise, and in the one window available did worse than equal-weight (−1.89% vs
−0.28%). **Option refused; the refusal is the deliverable.**

Power limit stated: 24 days, 18 books, overlapping windows, block-bootstrapped.
*Not demonstrated with a point estimate of ~zero* — not *proven useless*.

## 4 · The illiquid tail: a real signal, exactly consumed by execution

The fleet trades **7 of 227** books. Tested the **137 active books at
$20k ≤ vol < $10M**, cross-sectional quintile long/short — **market-neutral by
construction**, which removes the single-falling-BTC-regime problem (item 18).
Execution lag enforced; staleness screen (illiquid books go flat then jump,
manufacturing fake reversal).

**Cost was re-derived from the fleet's own 3,015 `venue_orders`** rather than an
inherited constant (MEAN bps/fill — a continuous strategy pays the average):

| tier | orders | median | **mean** | p90 |
|---|---:|---:|---:|---:|
| ≥ $10M | 831 | 0.32 | **0.61** | 1.35 |
| $0.1–1M | 847 | 2.51 | **2.52** | 9.42 |
| **< $0.1M** | 446 | 3.91 | **17.49** | **398** |

**The dust tier is not a surface, it is a trap.**

| universe | books | gross | cost | **net** | t |
|---|---:|---:|---:|---:|---:|
| all tail (incl. dust) | 134 | +0.066% | 0.166% | −0.100% | −3.30 |
| **≥ $0.1M (tradeable)** | 85 | +0.054% | 0.054% | **+0.000%** | **+0.00** |

**The gross signal is REAL** — random-ranking null **P = 0.0100** — and is
**exactly** consumed by the cost of harvesting it.

## 5 · Passive execution is refuted, with a number

Lighter's maker fee is **0.0000**; the 5.12 bps is slippage from *crossing*.
Every bot in this fleet crosses (`venue_orders` has no `post_only`/`order_type`
column; 3,558 rows, all taker). Modelled resting at `close(t)`, filling during
bar *t+1* iff the market trades there:

| execution | fill L/S | gross | cost | **net** | t |
|---|---:|---:|---:|---:|---:|
| CROSS both sides | 100/100% | +0.054% | 0.054% | +0.000% | 0.00 |
| **PASSIVE (touch, δ=0)** | **100/100%** | +0.115% | 0.027% | +0.088% | 1.63 |
| PASSIVE (through 5 bps) | 89/88% | **−0.128%** | 0.027% | **−0.154%** | **−2.78** |
| PASSIVE (through 20 bps) | 80/80% | −0.304% | 0.027% | −0.330% | −5.57 |

**A 100% fill rate is not a fill model, it is an assumption** — `low(t+1) ≤
close(t)` holds on almost every bar, so δ=0 hands the strategy the better of two
prices with zero queue risk. **Price queue risk at all and the sign inverts.**
Fill rate stays at 89%, so trades are not missed — **the trades you get are
poisoned.** Consistent across halves (H1 −0.162% t=−1.92, H2 −0.151% t=−2.08),
block-bootstrap 95% CI **[−0.251%, −0.047%]**, P(net>0)=**0.002**.

Spread saving **+2.7 bps**; adverse selection **−18 bps**. The lever works and
is pointed at the wrong problem.

*Declared limits: 4h OHLC, no queue model, no historical bid/ask. The direction
is stable at every non-degenerate setting and across both halves; only the
zero-queue-risk assumption produces a positive.*

---

## What this changes

| surface | blocker | status |
|---|---|---|
| funding — timing | variance; edge zero by construction | **closed** |
| funding — selection | funding = fair price for adverse selection | **closed** |
| the I16 claim as a ranking signal | no predictive power (Spearman ≈ 0) | **closed** |
| funding tail, both directions | same pricing, opposite end of range | **closed** |
| tail cross-sectional reversal | gross real (P=0.01), consumed by execution | **closed** |

**The strategic reading.** The fleet's measured effects are two orders of
magnitude larger on **price dislocation** than on funding — 🧲 the retired
ghost's own realised **−0.281%/trade (t=−2.97)** is live-ledger evidence, and
its mirror 🪁 band-kelly's founding claim is **+0.605%/trade (t=+5.71)** — while
the funding surface prices to ~0.000% in every test above. **The fleet runs
three directional-funding books against one dislocation book born 18-Aug with
zero closes.** Attention and capital are allocated inversely to where the
measured signal is.

**Not claimed:** that any live book loses. 💸 the Farmer's live row is **+$5.74
realised**. The honest word throughout is *zero-edge* and *unproven*, never
*losing*.

**Still real and unexploited:** the tail's cross-sectional reversal ranking beats
a random ranking at **P=0.0100** — ~5.4 bps per 4h period. Every execution route
measured costs at least that much. A cheaper route would monetise it; the two
obvious ones are now both measured and both fail.

## Do not re-run

- Directional funding as a *signal*, either direction, any threshold 5–500%, any
  hold 1–24h. Priced, confirmed twice from opposite ends.
- A capital ramp weighted by the I16 claim, on current evidence.
- Passive entry on a ~4h horizon in the tail (−18 bps adverse selection).
- `(hm)`'s *"random short earns +0.2–1.1%/trade"* **must not be quoted across
  books** — that is the Ticket Taker's horizon. At the Farmer's (6h, majors) it
  is **+0.018–0.024%**. The free-short premium is horizon-dependent.
