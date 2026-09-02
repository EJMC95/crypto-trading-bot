# 👩 mum — is her ROI ladder mis-calibrated for the non-crypto half?

**Eamon, 2-Sep: "Start it."** — the build `(xk)` named and did not do.
Instrument: `scripts/study_mum_class_ladder_2026-09-02.py`, pre-registered and
committed **before** the run. Read-only; moves nothing.

## VERDICT: HYPOTHESIS, NOT SHIPPED — and the whole-book version is REFUTED

`k=0.5` (every rung halved) leads at **+0.0325%/bar-day** and +0.0440%/trade
over shipped, positive in both chronological halves, cluster-t +1.92, plateau
intact. It fails **C6**: shuffling the class labels and re-running the entire
best-of-N selection gives a **median advantage of +0.0363%** against the real
half's **+0.0304%**, i.e. **p = 0.5885**. A randomly-labelled half does
*better*. The advantage is the selection procedure, not the class.

**And the control closes the door on the larger version of the idea.** The same
cells on the CRYPTO half move the opposite way, monotonically in the dose:

| k | non-crypto Δ%/bar-day | crypto Δ%/bar-day | crypto Δ%/trade | crypto t_cl |
|---|---|---|---|---|
| 0.75 | +0.0199 | +0.0108 | −0.0026 | −0.20 |
| 0.50 | **+0.0325** | −0.0224 | −0.0208 | −1.06 |
| 0.35 | +0.0285 | −0.0799 | −0.0384 | −1.29 |
| 0.25 | −0.0567 | **−0.1763** | −0.0570 | −1.61 |

The crypto half is the profitable one (**+0.0953%/bar-day**, +0.0410%/trade,
n=12,397) and lowering the ladder degrades it by up to **−0.176%/bar-day** —
larger in magnitude than the non-crypto gain and monotone across four cells.
So: **a class-aware ladder is refused, and a whole-book lowering is refuted,
not merely untested.** No individual crypto cell reaches |t|≥2, so the evidence
there is a dose-response rather than a single significant cell; the direction
is unambiguous and it is the wrong one.

## The mechanism `(xk)` recorded is much weaker than its 7 closes implied

`(xk)` reported realised |return| of **0.623% vs 1.746% (2.80×)** and "5 of 7
run the 24h cap vs 4 of 52". Those come from **7 realised closes**. On the
tape — 10,020 non-crypto and 12,418 crypto episodes of her own mechanical
entry:

| | crypto | non-crypto |
|---|---|---|
| MFE median | 1.554% | 1.203% |
| MFE p90 | 2.744% | **2.903%** |
| reaches the first rung | 31.3% | 25.9% |
| reaches **any** rung | 74.5% | **66.0%** |

**1.29× on median favourable excursion, not 2.80× — and at the p90 the
non-crypto names move *more*.** Two-thirds still reach a rung. "The
crypto-fitted ladder is largely unreachable off-class" is not what the tape
says. Corrected in place in `lighter_family_bot.py` and in the sleeve study.

## The hold is not the lever either

Every shortening loses on per-bar-day (−0.042 at h=20 through −0.095 at h=12),
because it converts `roi` exits into `max_hold` exits (2,284 → 6,662 at h=8)
and `max_hold` is negative by construction (0 positive / 18 negative across
114 era closes). The "5 of 7 run the cap" observation points at the ladder,
never at the clock.

## C1 — calibration passed

Replaying her REAL era entries through the shipped ladder reproduces her actual
exit mix on 113 of 115 ledger rows: `roi` 69.9% vs 70.8%, `max_hold` 17.7% vs
16.8%, `stop` 12.4% vs 10.6% — worst family 1.8pp against a 20pp tolerance.

## THE DEFECT THIS STUDY SHIPPED AND CAUGHT — C4's metric was the artifact

The first run read **`per-bar-day +1.7173%` beside `%/trade −0.1333%` on the
same sleeve.** Impossible for any honest exposure metric, and that is what
exposed it: `mean` was the **mean of per-episode ratios** `ret/(held/24)`,
which gives a 1-bar winner 24× the weight of a 24-bar loser. Two trades of
+2%/1bar and −2%/24bars net to zero and score **+23%/day**. The guard against
denominator shrinkage *was* denominator shrinkage.

It is now the aggregate `total return / total bar-days` — the number `(hl)`
used. The old statistic is kept and reported as `mean_ratio` so the artifact
stays visible, and every cell prints its exposure ratio.

**This changed the headline by ~40×**: the first run's `k=0.35` read
**+1.2992%/bar-day at t=+9.58**, which reads as an overwhelming ship. Under
the honest metric the same cell is **+0.0285%**. Both runs refused on C6 — the
permutation held the line either way — but a reader seeing only the first
number would have shipped it.

## Declared limits

* **Slot contention is not simulated**, and that term **flatters the
  candidate** (a faster ladder frees a slot sooner). Named first because it is
  the one that runs into the candidate's favour.
* Entry is the OPEN of bar `e` and the walk tests that bar's own high/low —
  post-entry prices, so not the `(ne)` look-ahead. Declared for the record.
* Fill at the rung, never the bar high. Adverse leg first when both touch.
* Price return on both arms, so fees/funding cannot be mismodelled into the
  verdict.

## Reuse, verified rather than asserted

The generalised bracket walk is pinned **byte-identical** to
`study_mum_supply_2026-08-26.bracket_walk` on 300 episodes; the vectorised
entry predicate is **driven** against `OversoldRebound.signals` on 140
prefixes. The ladder, stop, hold and RSI bar are read from the live carrier —
load-bearing, since `RSI_MAX` has moved to **36.0** since those cells were
written. 7 of 7 mutations red.

## What remains open

Her non-crypto sleeve loses on the tape (**−0.2372%/bar-day**, −1331% total
over 5,612 bar-days) and no ladder in this grid makes it profitable — the best
cell reduces the loss by ~14%. That is a supply/entry question, not an exit
one, and it is **not** the `(xk)` cut either: that registration stands
unchanged, still inert, still requiring G≥10 entry days and a day-clustered
exclusion.
