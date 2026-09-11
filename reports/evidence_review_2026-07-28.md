# Evidence Review — 2026-07-28

_Machine pass 2026-07-28T08:58Z (18:58 AEST) via `scripts/evidence_review.py`;
human layer added after. **No ⚠️ ACTION required.**_

All **15** distinct alert keys in the 7-day `fleet-alerts` window verify
**ACTIVE**. Nothing resolved, nothing stale. Zero sections failed.

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | census now **6994** events across 30 books (threshold 50) |
| factor-sample:4 | active | joined decision+context dataset at **144** closes (57% win), bucket 4 |
| disloc:KAITO | active | 791 ev / 350bps (alert 771), last event 0.0h ago, 16 entries |
| disloc:STBL | active | 169 ev / 245bps (alert 168), 0.6h ago, 3 entries |
| disloc:ZORA | active | 211 ev / 202bps (alert 210), 0.6h ago, 3 entries |
| disloc:CHIP | active | 128 ev / 160bps (alert 126), 1.8h ago |
| disloc:0G | active | 315 ev / 277bps (alert 305), 2.5h ago, 4 entries |
| disloc:BIO | active | 74 ev / 272bps (alert 73), 2.6h ago |
| disloc:RESOLV | active | 417 ev / 188bps (alert 416), 2.9h ago |
| disloc:GMX | active | 126 ev / 151bps (alert 123), 3.1h ago |
| disloc:EIGEN | active | 162 ev / 161bps (alert 161), 3.2h ago |
| disloc:SKY | active | 83 ev / 315bps (alert 82), 4.3h ago, 2 entries |
| disloc:APEX | active | 3820 ev / 313bps (alert 3820), 7.2h ago, 382 entries |
| disloc:STABLE | active | 295 ev / 396bps (alert 295), 7.3h ago, 4 entries |
| disloc:NEAR | active | 18 ev / 150bps (alert 18), 7.9h ago — thin but current |

## New evidence

- **🎫 `long-dip` is significantly NEGATIVE** — n=13, net **−$9.15**, WR 15%,
  **t=−2.74**. This is the only taker lens with a significant result in either
  direction, and it is a losing one. Restrict-safe and worth acting on.
- 🎫 short-divergence (the live lens) n=81, net **+$7.79**, t=0.72 — flipped
  positive since 23-Jul (was −$4.50) but **still noise**.
- 🎫 long-divergence n=20, +$2.44, t=0.31 — noise. long-breakout n=10, +$7.72,
  t=1.73 — noise.
- 💰 **LIVE Farmer**: n=60, net **+$8.07** — short 57 (+$7.48), long 3 (+$0.59).
- 💰 **LIVE Taker**: n=24, net −$0.77 — long-divergence 12 (−$1.90),
  short-divergence 12 (+$1.13).
- 🚦 **Go-live gates** (retired, already-live and live-twin rows excluded;
  drawdown derived from the LEDGER): only `perps-funding-spread-lshadow`
  (n=38, WR 55.3%, dd −0.2%). It clears the mechanical gates but radar grades it
  class **"noise"** with t=0.64 — **not** a promotion case.
- 🚦 fleet-risk **yellow** — 15 gross vs long budget 20; 7d DD −0.21%,
  clip_scale 1.0. Governor untriggered.
- 📏 Farmer live-vs-shadow per-trade gap **−0.038pp** (live +0.313% n=49 vs
  shadow +0.352% n=61) — no divergence.
- 🧬 **Farmer arms now AGREE** (both `f7044072157f`). 🧬 **Taker arms DRIFT**
  (live `134c1822a3ff` vs shadow `ca1f3d6a326e`).

## Corrections to yesterday's read

Two items flagged this morning turned out to be **already remediated** — both
were true historically and neither needs operator action:

1. **The live taker's long-side leak is closed.** Split at 24-Jul 14:00 UTC
   (proper `::timestamptz` cast): **12** long-divergence closes (−$1.90) before,
   **zero** after; all 10 closes since are short-divergence (+$0.43). The
   24-Jul BULL DUAL-MODE commit (`lighter_ticket_taker.py:465-501` — "divergence's
   only real side is SHORT and its only clean universe is CRYPTO") is in force on
   the live container. The −$1.90 is a closed chapter, not an open wound.
2. **The Farmer's `arm-drift` resolved during this review.** At 08:20Z the arms
   read `a5336fda3e84` (live) vs `9e4982f47f62` (shadow); by 08:40Z both read
   `f7044072157f`, stable across 10 samples over 3 minutes. `impl-shortfall`'s
   "arm-drift" verdict was computed pre-convergence and should clear on its next
   cycle, restoring the execution read.

## What was fixed today

- **The four missed runs are explained and fixed.** The cron never missed a
  firing (`lastRunAt` advanced daily); the runs were **dying partway**, after
  computing verdicts but before the UPSERT, on two schema traps that kill the
  natural query on first contact:
  - `paper_trades.closed_at`/`opened_at` are **TEXT in four formats** (measured:
    2267 rows at lengths 32/23/25/20, mixing `2026-07-16 05:04:54 UTC` with
    ISO-8601). `WHERE closed_at > now() - interval` **raises**, and lexicographic
    comparison is unsound across those formats — `' '` sorts before `'T'`.
  - `bot_pnl` has **no `max_drawdown` column** (it lives in `extra` jsonb,
    unpopulated fleet-wide). `SELECT max_drawdown` **raises**. This is the same
    caveat the 24-Jul report logged and left open.
- **`scripts/evidence_review.py`** now does the mechanical review
  deterministically, with every section **fail-soft** (a throwing section records
  its error and the review still publishes), a `--selftest` that survives four
  mutations, and a single gated write to `bot_state['evidence-review']`.
- **The go-live drawdown gate is verifiable again** — derived from the durable
  ledger equity curve instead of the unpopulated `bot_pnl` field.
- **The scheduled task now runs the script** and spends its judgement on the
  parts a script cannot do.

## Recommended human action

None urgent. One decision worth taking:

- **`long-dip` is the fleet's one significant lens result and it is negative**
  (t=−2.74, −$9.15 over 13 closes). It is shadow-only, so nothing is bleeding
  real money — but it is a restrict-only, reversible kill with actual evidence
  behind it, which is rarer here than it sounds.

One thing to watch, not act on: the **taker's arms are on different builds**, so
its shadow arm is not a clean control right now. The Farmer's just converged; the
taker's has not.

## Update — 19:10 AEST (09:10Z)

Re-ran the review: **every number identical** to the 08:57Z publish, so the
`evidence-review` row stands as published (15 active, 0 errors). The tree,
however, moved — three commits landed from the concurrent review session
(`9476811`, `f4f55cc`, `52d2ca3`, plus `f7cad49`), including the
**28-Jul fleet review** itself.

**One finding changes shape.** Both of today's taker commits touch
`lighter_ticket_taker.py` (+166 lines) and both ride the **freqtrade-bots auto
path only** — the CHANGELOG states it outright: *"no live-money service is
deployed by this commit"* and *"no live dispatch (live path untouched by
construction)"*. So the 🧬 taker arm drift I flagged is about to **widen**, and
it is now **deliberate**: the shadow taker picks up both commits, the live taker
stays on `134c1822a3ff`. That is a design choice, not a defect — but the
consequence stands unchanged: while it holds, the shadow taker is not a
byte-identical control, so any live-vs-shadow taker comparison mixes a code
delta into an execution number.

Worth noting as a follow-up, not acted on: because the live taker is on no auto
path, this drift item will now fire **every day indefinitely**, which is exactly
how a signal turns into wallpaper (`convergent-metric-is-not-a-health-check`
cuts both ways). It needs either an expected-drift baseline or a live dispatch.

**Independent corroboration.** The review session reached two of the same
conclusions from its own data: the carry book's net is an **artifact**
(it measured +$58.62 vs my +$55.22, same verdict), and the live taker is
**~flat since the bull-mode flip at n=10** — which is the same event my
before/after split found at 24-Jul 14:00Z. Two paths, one answer.

Also confirmed by that commit: the Farmer's build convergence I measured at
08:40Z was the `(ds)` deploy landing, and the judge's own arm-drift gate had
been **dark from birth** (`publish_paper_trade` never stamped `extra.build` —
0 of 143 Farmer ledger rows). My drift read came off `bot_pnl`, which *is*
stamped, so it was reading the one source that worked.

---
_The verdict table and new-evidence list are regenerated by
`scripts/evidence_review.py` on every run — edit this file after the run, not
before._
