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

## [2026-07-30 CONSUMER WIRED — operator call, same day]

The operator overrode the hold on the WIRING half ("per asset have
consumer"): **step 2 of the build order is now BUILT**, shipped inert.

- `fleet_bus.oracle_asset_regimes()` — the supported accessor ({sym:
  verdict}, standard fail-safe: dark/stale/absent → {}).
- `lighter_family_bot.regime_inputs_for(coin, btc_regime, btc_tide,
  verdicts)` — crypto pairs: byte-identical passthrough of the validated
  BTC 4h gates (selftest-pinned). Non-crypto pairs: the asset's OWN
  verdict, LONG-window ⇒ both gates up, anything else / ungraded / dark ⇒
  fail-CLOSED. Classification is STATIC (`NONCRYPTO_SYMS`, drift-guarded
  against `regime_oracle.NONCRYPTO`) so a dark oracle can never re-route
  SPY to BTC's gate. Kill switch `FAMILY_PER_ASSET_REGIME=off` closes
  non-crypto entirely — there is deliberately no value that yields BTC.
- **Inert today, asserted**: the selftest checks the configured family
  universe contains no NONCRYPTO_SYMS member — the oracle fetch runs zero
  times until step 3. Four mutations (classification inversion, fail-open
  revert, kill-switch-to-BTC, stale-trusting accessor) each turn their
  named assertion red.

**What this changes about the recommendation above:** nothing about the
evidence. The HOLD verdict applied to the wiring decision — the operator
made that call. The study's per-book cells now inform **step 3 (the
universe)**, which remains review-gated: TSLA-class books look protected,
metals argue for a class-scoped or verdict-quality-gated widening, and the
index books still need their ~mid-Aug graduation re-run before they can be
candidates at all.

## [2026-07-30 STEP 3 RUN — operator call, same day: "run step 3 too"]

The universe half also shipped on the operator's word, and the gate's
fail-closed construction is what makes that safe with the index books
still ungraded:

- The four FAMILY books list the oracle's 10 non-crypto symbols
  (`FAMILY_NONCRYPTO_COINS`; empty string reverts to crypto-only). Spot
  ports keep their pinned crypto lists — selftest-asserted.
- **The gate binds at the entry site** (`noncrypto_entry_blocked`): a
  non-crypto long needs the asset's OWN LONG-window regardless of which
  strategy is asking — TrendMomo and SwingDip never read the regime
  extras, and without this rule they would have bought SPY dips bare of
  any gate (the Georgia diagnosis is the measured cost of that shape).
  Mutation-verified both ways (inverted rule; crypto-blind rule).
- What actually trades at ship: nothing new immediately. The six
  short-history books sit listed-and-idle until the oracle grades them;
  the four graded books admit only inside their own LONG-windows (NVDA
  30% of bars, TSLA 2%, XAU 4%, XAG 12% at the 28-Jul read). The
  widening's first real effect is that graduation (~mid-Aug) flows
  straight into live shadow evidence instead of a hypothetical.
- The ~mid-Aug re-run of this study now doubles as the first
  LISTED-universe read: per-book cells against books that are actually
  tradable, per-tag brain grades accruing from the family ledger.

---

## THE ~mid-Aug GRADUATION RE-RUN — EXECUTED 18-Aug (the clause above is discharged)

`scripts/study_per_asset_gate.py` re-run 18-Aug with SPY/QQQ now ABOVE the
203-bar floor and both publishing `LONG-window, dir=1` on the live oracle
(fresh payload, n_published 7 of 10; IWM/WTI/XCU still short-history, named).

**The honest verdict: graduated in BAR COUNT, not yet in GRADED SAMPLE.**
SPY and QQQ carry n=3 graded verdict-days each (2 days above the floor) —
far under the 28-Jul review's n≥20/sym self-grade bar, so no wiring decision
changes today. What the deep-history cells DO say, pooled where thin:
- equity-single (n=138 graded days): the D5 damage cell (btc=1, own=0) reads
  **−0.52pp d1 / −1.70pp d3** — BTC's gate admitting what the asset's own
  gate refuses is measurably poor, which SUPPORTS the per-asset wiring
  already shipped (steps 2+3, 30-Jul).
- commodity (n=194): same direction on the (1,1) cell (−0.64/−3.25pp);
  the (0,1) cell is n=2 — noise, not evidence.
- equity-index: n=6 total. Nothing decidable.

**Standing state**: the wiring is LIVE (`noncrypto_entry_blocked` at the
entry site; SPY/QQQ in LONG-window means family books can now take the
fleet's first second-regime longs on their own signals — 🙏 avo shadow
already holds SPY). **The next milestone is the oracle's self-grade n≥20 on
SPY/QQQ (~mid-Sep at 1 verdict-day/day)** — that, not bar count, is when the
28-Jul review's decision bar is actually met. Nothing to re-run before then.
