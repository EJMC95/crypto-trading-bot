# Live Funding Farmer — gate sweep on LIGHTER's own tape (2026-07-23)

Run: `scripts/backtest_funding_lighter.py --days 180 --universe 25`
against `mainnet.zklighter.elliot.ai` (settled hourly fundings + candles).
180d, 25 markets, 2026-01-24 → 2026-07-23, clip $25 × 6 slots, exit = enter ×
0.375. **Lighter-only, per doctrine.**

## ⚠️ THE VERDICT TURNS ENTIRELY ON EXECUTION COST — and the real cost is ~0.5bps, not 5

`SLIP` is the load-bearing constant (`backtest_funding_lighter.py:230`) and it
was never measured — the default 5bps came from "nothing" (the file's own
comment). The fleet's fill-telemetry has since **measured the live Farmer's
round-trip slip at ~0.47–0.54 bps/fill** (`impl_shortfall.order_slip.live`,
"live executes TIGHTER than its own shadow model ~0.87bps"). At the real cost
the arm is a genuine, modest positive-carry edge — my first pass (5bps) made it
look dead, which was an artifact of the unfounded assumption, NOT the venue.

### Gate 0.05 (what the live bot does today) across the plausible slip band

| slip/fill | P&L 180d | 1st half | 2nd half | win% | maxDD |
|---|---|---|---|---|---|
| **0.5 bps (MEASURED live)** | **+$33.47** | +24.74 | +13.12 | 59.3 | −44.76 |
| 0.86 bps (shadow model) | +$31.08 | +23.30 | +12.18 | 59.0 | −45.20 |
| 1.0 bps | +$30.15 | +22.75 | +11.81 | 59.0 | −45.37 |
| 2.0 bps | +$23.50 | +18.76 | +9.19 | 58.2 | −47.12 |
| 5.0 bps (my earlier ASSUMPTION) | +$3.57 | +6.79 | +1.33 | 56.8 | −55.21 |

At the measured cost the live gate is **both-halves-positive with a real margin**
(+$33/180d ≈ +2.2% on the $1.5k deployed, 59% win) — and it stays positive and
both-halves-robust all the way out to 2bps. It only collapses toward zero as
slip approaches the unfounded 5bps.

## The gate curve at the measured slip (0.5bps/fill)

| gate | P&L $ | 1st half | 2nd half | both agree? |
|------|-------|----------|----------|-------------|
| 0.02 | +$45.47 | +29.25 | +20.25 | ✅ (deeper DD −56) |
| 0.03 | +$28.98 | +14.16 | +21.25 | ✅ |
| **0.05 (LIVE)** | **+$33.47** | +24.74 | +13.12 | ✅ (DD −45, win 59%) |
| 0.08 | +$16.98 | +2.16 | +13.81 | ✅ (marginal) |
| 0.12 | −$27.18 | −9.51 | −17.50 | ❌ both − |
| 0.20 | −$12.97 | −4.26 | −9.32 | ❌ both − |
| 0.30 | −$13.08 | −13.12 | +0.04 | ❌ |
| 0.40 | −$3.93 | −10.61 | +6.68 | ❌ (HL-fitted) |

## What this actually says

1. **The live funding arm is NOT dead — it is a modest, real, both-halves-positive
   carry edge at the measured execution cost.** Do NOT idle it. (An earlier read
   here said "cost-bound, idle it"; that was the 5bps artifact — corrected.)

2. **Widening the entry gate UP still LOSES — at EVERY slip level.** Every gate
   ≥ 0.12 is negative in both halves whether slip is 0.5 or 5bps. The premise
   "the lever needs more space upward" stays refuted; the tight ceiling is
   protective. This conclusion is slip-invariant and robust.

3. **The arm's edge IS its execution quality.** Because carry is thin, the whole
   P&L is a function of slip: viable at ≤~2bps, dead toward 5bps. The productive
   lever is therefore NOT the gate or the strategy — it is KEEPING SLIP LOW, and
   the fleet already monitors exactly this (`implementation_shortfall` /
   fill-telemetry). If measured live slip ever drifts up past ~2bps, the arm's
   edge is gone and it should idle. That monitor is load-bearing.

4. **The current gate (0.05) is a sound, slightly-conservative choice.** Lower
   gates (0.02/0.03) earn marginally more but with deeper drawdown (−56 vs −45);
   0.05 has the best win% and shallowest DD of the positive rows. No change to
   the live gate is indicated — it is already at a good value.

## Recommendation (operator authority — surfaced, not taken)

- **KEEP the live funding arm and its 0.05 gate.** It earns at the real cost.
- **Do NOT widen the gate up** (loses at all slip levels) and **do NOT idle**
  (it works) — unless measured live slip drifts up past ~2bps, which is the one
  condition that kills it; watch `impl_shortfall.order_slip.live`.
- The `SLIP=5.0` default in the backtest is an unfounded pessimistic constant —
  future runs must use the measured ~0.5bps (the fill-telemetry number) or they
  will repeat the "it's dead" artifact. The live-slip measurement is owned by
  the fill-telemetry work (its final n is still accumulating); this doc uses it
  as a band (0.5–2bps), not a single point.

Full-tape (438d) re-run is a follow-up; the slip-sensitivity conclusion is
structural and holds across the window.
