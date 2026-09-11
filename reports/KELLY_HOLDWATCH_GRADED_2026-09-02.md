# 🪁 band-kelly's hold-watch, graded — the (ub) win-more finding is REFUTED out-of-sample, and it INVERTED

**2026-09-02 (Wed, Sydney) · expansion research · read-only, nothing shipped**

Instruments: `scripts/study_kelly_holdwatch_2026-09-02.py` ·
`scripts/study_kelly_side_2026-09-02.py`

---

## THE HYPOTHESIS, AND WHY IT WAS PICKED

`(ub)` (26-Aug, expansion log) closed with a pre-registered next thread:

> once `holdwatch` carries a week of `t`, the exit re-spec is a query, not a
> guess

It also recorded a **win-more finding** on n=218 aggregate samples with **no
dispersion**, so no `t`:

| horizon | +15m | +30m | +60m | +120m |
|---|---:|---:|---:|---:|
| extra %/trade | −0.332 | +0.044 | **+0.291** | **+0.324** |

against a `conv` exit realising −0.186%/trade. The reading was "holding past
the book's own exit earns; throughput is not the obstacle (occupancy 3% of 4
slots), so a 12.8× longer hold costs no entries." That is a **bounded,
reversible widening on a live book that cannot currently be graded** — I26's
ship-by-default shape — and it was gated only on the missing `t`.

A week has passed. 🪁 band-kelly now reads **−$128.48 on 380 closes**, is the
fleet's largest bleeder, had its clip cut $250 → $80 on 1-Sep `(vy)`, and has
a ~18-Sep grade. The question is decision-blocking and the instrument built
for it is live.

## THE METHOD, AND THE ACCIDENT THAT MADE IT AN OUT-OF-SAMPLE TEST

`holdwatch_block` counts dispersion on its **own** counter (`n2`/`sum2`/
`sumsq`), separate from `n`/`sum`. That was shipped for a different reason —
a durable bucket restored from before the field existed carries `n` without
`sumsq`, and dividing the new `sumsq` by the old `n` would understate sd on
exactly the longest-running horizons.

The side effect is that **`n` pools the whole history while `n2` counts only
the samples taken since 26-Aug**. So the published cell decomposes:

```
mean2   = t · sd / √n2                    (invert the published t)
old_n   = n − n2
old_mean = (mean·n − mean2·n2) / old_n
```

`old_*` must reproduce the `(ub)` registration; `mean2` is the fresh sample
the registration is graded on — never the pooled window that generated it
(I21's follow-through rule, I25's baseline rule).

**THE CALIBRATION GATE.** The decomposition may only be read if it reproduces
the window it claims to have removed. Tolerance 0.005pp, fail-closed.

## NUMBERS

### 1 · The gate passes on all four horizons

| horizon | n | n2 | pooled | old (n−n2) | (ub) registered | recon |
|---|---:|---:|---:|---:|---:|:--|
| +15m | 368 | 149 | −0.3487 | **−0.3317** | −0.332 | ✅ |
| +30m | 367 | 149 | −0.1357 | **+0.0438** | +0.044 | ✅ |
| +60m | 365 | 147 | −0.3203 | **+0.2912** | +0.291 | ✅ |
| +120m | 363 | 145 | −0.6366 | **+0.3251** | +0.324 | ✅ |

Four independent reconstructions of a four-number registration, to three
decimals, from a counter nobody split for this purpose. The removed window
**is** `(ub)`'s.

### 2 · The verdict on the fresh sample alone

| horizon | registered | **FRESH** | n2 | t | |
|---|---:|---:|---:|---:|:--|
| +15m | −0.332 | **−0.374** | 149 | −1.32 | inverts, ns |
| +30m | +0.044 | **−0.398** | 149 | −1.11 | inverts, ns |
| +60m | **+0.291** | **−1.227** | 147 | **−2.06** | **inverts, significant** |
| +120m | **+0.324** | **−2.083** | 145 | **−2.66** | **inverts, significant** |

**Every horizon inverts, and the two that motivated the widening are
significantly negative.** The gap at +120m is **2.41 pp/trade** against the
registration.

Three things make this stronger than the bare t:

* **It is on the optimistic basis.** The extra is priced at a **MID** while
  the exit it is measured against was a **VWAP** — favourable by ~half a
  spread. The true figure is worse.
* **It is monotone in the direction of harm** (−0.37 → −0.40 → −1.23 →
  −2.08). A noise cell does not order itself.
* **Clustering helps this `t`, it does not make it.** `(ub)` measured
  variance inflation **0.37×** with **n_eff 589 > n 216** on this book —
  clusters self-hedge — so the cluster-robust figure is *more* negative.
* **It is stable across a live refresh.** The payload advanced mid-session
  (+60m n 365→366) and t moved −2.06 → −2.08.

**DECLARED LIMIT, not waved away:** `holdwatch` publishes aggregates only, so
a **drop-worst test is structurally impossible** here. One −50% sample would
move the fresh mean by 0.34pp — which does not reach +60m's 1.52pp reversal
or +120m's 2.41pp, but *is* the whole of the +15m/+30m cells. Read the two
significant horizons; the two thin ones are directionally consistent and
nothing more.

### 3 · The record agrees (I14)

| | n | mean %/trade | t | win |
|---|---:|---:|---:|---:|
| pre 26-Aug | 229 | −0.13 | −0.79 | 37.1% |
| post 26-Aug | 151 | −0.27 | −0.81 | 47.7% |

The pre-window reproduces `(ub)`'s own split exactly (216 snapfade at
−0.025% + 13 dipfade at −1.852% ⇒ −0.129%). The book got *worse* over the
window in which holding longer would have had to be earning.

## THE SECOND FINDING — A SIDE CUT LOOKS SHIPPABLE AND IS NOT

The exit census raised an obvious follow-on. Splitting the honest cell
(`snapfade` `conv`, no outcome-conditioned families):

| | n | mean | t | h1 | h2 |
|---|---:|---:|---:|---:|---:|
| long-snap_conv | 185 | −0.097% | −1.42 | −0.192 (t −2.86) | +0.283 (t +1.41) |
| **short-snap_conv** | **99** | **−0.731%** | **−4.32** | −0.172 | −1.350 |

t=−4.32, both halves negative, survives drop-3-worst at −0.540%. Dollars
agree: short −$153.96 vs long +$24.69 of a −$129.26 book. It reads like a
shippable, bounded, restrict-direction cut.

**IT IS REFUSED, and the number that refuses it is the one the verdict rule
excludes.** A verdict must drop outcome-conditioned exit families (I21) —
`*_stop` loses and `*_ghoststop` wins *by construction*. But **a side cut
removes the side's whole ledger, tails included**, and the two sides do not
take those families in remotely equal proportion:

| | n | mean | Σ pct-points |
|---|---:|---:|---:|
| short `conv` | 99 | −0.731% | **−72.4** |
| short `ghoststop` | 36 | +5.90% | **+212.4** |
| short `stop` | 30 | −6.79% | **−203.7** |

The two tail buckets nearly cancel (**net +8.7**) and each is ~8× the
centre. Put them back and the short side reads:

**n=190, mean −0.4229%/trade, t=−1.35 — not significant.** Drop-worst
finishes it: ex-3-worst **t=−0.84**, ex-5-worst **t=−0.52**.

So `t=−4.32` → `t=−1.35` → `t=−0.52`. The short side is **undecidable by
tail** ((po)'s class, at the *side* level) — not a measured loser. The long
side is undecided too and **sign-unstable across the boundary** (h1 −0.002
→ h2 +0.283), which is I25's own signature and must not be read as a
winner.

**The transferable trap: the cell that must be excluded to reach a VERDICT is
the cell that must be included to price a DECISION.** Both readings are
correct in their own place and they disagree by 3.8 t-units. A future session
reading `short-snap_conv t=−4.32` off an exit census and cutting the side
would be acting on an artifact of its own exclusion rule.

## VERIFICATION

Calibration gate mutation-tested, **3/3 behaved correctly**:

1. registration constant +0.291 → +0.591 ⇒ **MISMATCH, refuses to grade**;
2. `√n2` → `n2` in the t inversion ⇒ **MISMATCH, refuses** — and note this
   mutation produces a *plausible* fresh mean of −0.173%, a far milder
   finding that would have been believed without the gate;
3. unpriceable cells (`t` missing / sd 0 / n2<2) return **None, never 0**
   (I6).

## VERDICT

**REFUTED.** The `(ub)` hold-longer widening is dead: graded on its own
pre-registered instrument, on the fresh sample alone, it inverts on every
horizon and is significantly negative at both horizons that motivated it
(+60m −1.227%/trade t=−2.06; +120m −2.083%/trade t=−2.66). **Do not re-run
it without new evidence.** The measured harm required to refuse a bounded
widening (I26) is on the record.

**The exit re-spec that `(ub)` gated on this instrument is therefore not a
"loosen `conv`" change.** The `holdwatch` question is closed in the losing
direction; nothing here says the *opposite* (a tighter exit) works, and that
is a separate measurement nobody has run.

**No side cut.** Refused with numbers above.

**NOTHING SHIPPED.** No lever written, no proposal routed, no position
differs. Two read-only scripts added. `(ub)`'s recorded win-more finding is
now false-as-written and is corrected in place in the expansion log per I12.

## WHAT THIS DOES TO THE ~18-SEP GRADE

Unchanged in mechanics, clarified in expectation. `(ub)` left the book
"UNDECIDED, not proven bad" with a live win-more lever outstanding. **That
lever is gone.** The book is undecided *and* has no measured improvement
available to it — which makes 18-Sep a genuine I17 keep-or-decide call
rather than a checkpoint on a pending fix. The clip cut to $80 `(vy)` was
the right call and costs the grade nothing (%-invariant, `(hl)`).

## NEXT THREAD

1. **The stop asymmetry, unmeasured and the largest number in the book.**
   Both stops are set at 5% by construction (the mirror's `MY_HARD_STOP` and
   the ghost's, mirrored as profit cover), yet realise **−6.79%** and
   **+5.90%** — the loss side overshoots its bar by 1.79pp while the win side
   falls 0.90pp short of it, a **−0.89pp gap per stop-pair event across 66
   events**. If that is execution (gap-through on the adverse side), it is a
   cost finding on the fleet's own fills, not a strategy finding. Needs the
   fill data, not the ledger.
2. **🧭 nav-cook cannot be asked the same question — it has no `holdwatch`**
   (verified: 0 references in `lighter_nav_cook_bot.py`, absent from its live
   `extra`). `(ub)` named it as the sibling to check. **The prior has moved
   against porting the instrument**: the one book that measured the
   hold-longer thesis refuted it, so a port is a measurement, never a step
   toward a widening.
3. The four `funding-studies-inherit-the-rank-universe` re-derivations remain
   carried and untouched (HANDOFF, owner: session).
