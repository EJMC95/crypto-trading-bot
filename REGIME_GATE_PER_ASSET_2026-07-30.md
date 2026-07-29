# Per-asset vs BTC regime gating — the item-18/D5 evidence, at tape depth (2026-07-30)

Run: `scripts/study_per_asset_gate.py`. Feeds the **4-Aug review**; changes
nothing and consumes nothing at runtime. The 28-Jul review held step-2
wiring ("DO NOT wire the gate yet — the accrual is working, the n is not
there"; bar: oracle self-grades n≥20/sym d1, ~mid-Aug). This study is the
**deep-history complement** that review asked the tape for: the oracle's OWN
method (`regime_oracle.classify` — EMA50/200 + ADX hysteresis, 203-bar
floor, prefix-exact because every component is causal) replayed over each
non-crypto book's whole Lighter 1d tape, against the family gate's actual
BTC counterfactual (`btc_regime_up`, 4h EMA50>EMA200, causal series).

## What was measured

For every graded bar of every non-crypto book, two long-permission reads —
`own` (the asset's oracle verdict == LONG-window; what step 2 would consume)
and `btc` (what D5 forbids for non-crypto) — then the ASSET's forward return
at +1/+3 closed bars, split by the 2×2 (btc, own) cells. The two decision
cells: **(1,0)** = BTC's gate admits, the asset's own gate refuses (the D5
damage cell); **(0,1)** = BTC's gate blocks, the asset's own gate would take.

## Results (30-Jul tape; graded windows are YOUNG — n stated everywhere)

| book | graded n | disagree% | (1,0) damage cell d1/d3 | (0,1) blocked cell d1/d3 |
|---|---|---|---|---|
| TSLA | 40 (39d) | 20% | **−2.60pp / −7.87pp (n=7)** | −0.46 / −2.82 (n=1) |
| NVDA | 40 (39d) | 28% | +1.30 / +2.17 (n=3) | −0.48 / −1.23 (n=8) |
| XAG | 77 (76d) | 19% | +0.62 / +0.98 (n=13) | −2.05 / −2.49 (n=2) |
| XAU | 77 (76d) | 22% | +0.10 / +0.08 (n=17) | — (n=0) |
| pooled equity-single | 80 | — | **−1.43 / −4.86 (n=10)** | −0.48 / −1.41 (n=9) |
| pooled commodity | 154 | — | +0.33 / +0.47 (n=30) | −2.05 / −2.49 (n=2) |

NOT graded (named): SPY(188<206), QQQ(188<206), MSTR(203<206), XCU(170),
WTI(161), IWM(148) — short-history; SPY/QQQ cross the floor ~mid-Aug,
exactly the 28-Jul review's timeline.

## Honest read — this is an evidence-backed HOLD, not a go

1. **The gates genuinely differ**: 19–28% of bars disagree per book. A BTC
   gate over these books makes a different call roughly one bar in four —
   the incoherence D5 named is real and persistent at depth.
2. **Where they disagree, the outcome is ASSET-SPECIFIC and n is thin.**
   On TSLA the per-asset gate is decisively protective (the damage cell is
   −2.60pp/−7.87pp — BTC's gate would have admitted longs into the worst
   forward moves on the table). On the metals it is mildly the OTHER way
   (+0.33/+0.47 pooled: the own-gate refusals cost a little). NVDA is
   noise-level (n=3/8). Pooling classes would launder TSLA's win and the
   metals' cost into one number — the per-asset point itself.
3. **Every long-permission cell is negative on the equity books this
   window** ((1,1) −0.26/−2.74 pooled) — consistent with the 28-Jul
   self-grades (metals negative both horizons): the oracle's long calls on
   these young books have not yet been money-shaped anywhere. A gate is
   only as good as the verdicts it consumes.
4. **The books that MOTIVATED D5 (SPY's bull run through btc-risk-off)
   still cannot be graded** — they are exactly the short-history set. The
   deep-history complement cannot yet rule on the case that matters most.

**Recommendation for 4-Aug**: HOLD the step-2 wiring (unchanged from
28-Jul), with the decision now carrying tape evidence instead of only thin
self-grades. Re-run this study when SPY/QQQ cross the 203-bar floor
(~mid-Aug — the same beat the self-grade bar matures); the wiring case goes
to the review that sees BOTH the index books graded AND self-grade
n≥20/sym. If TSLA-class protection generalizes to the index books, wire it;
if the metals' pattern generalizes, the right consumer may be
class-scoped rather than universal — the study prints per-book cells so
that option stays open. "Never BTC's EMA for SPY" stands regardless: the
fallback for an ungraded non-crypto book is NO ENTRY (fail-closed), never
BTC's gate.

*Limits: gate alignment only (no entries/exits/slip/sizing — the same
object the oracle's self-grades measure, at depth); one venue tape (the
only admissible one); BTC-up base rate is only 18–26% over these windows
(the known one-regime tape), so the damage cell's n is structurally small
yet; young books dominate. Venue-pure: Lighter candles only, the oracle's
own fetch path.*
