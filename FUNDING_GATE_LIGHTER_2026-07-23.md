# Live Funding Farmer — gate sweep on LIGHTER's own tape (2026-07-23)

Run: `scripts/backtest_funding_lighter.py --days 180 --universe 25 --refresh`
against `mainnet.zklighter.elliot.ai` (settled hourly fundings + candles).
180d, 25 markets, 2026-01-24 → 2026-07-23, clip $25 × 6 slots, 5bps/fill slip,
exit = enter × 0.375. **Lighter-only, per doctrine.** This is the evidence the
"fix the brakes, then widen" plan gated the real-money widening on.

## The gate curve (TRUE apr = annualised funding at entry)

| gate | P&L $ | fund $ | price $ | n | win% | maxDD $ | 1st half | 2nd half | both agree? |
|------|-------|--------|---------|---|------|---------|----------|----------|-------------|
| 0.02 | **+19.82** | 14.74 | 5.11 | 1140 | 56.1 | −61.23 | +14.74 | +8.71 | ✅ both + |
| 0.03 | +3.18 | 15.26 | −12.03 | 1147 | 53.8 | −61.40 | −0.26 | +9.95 | ❌ h1 − |
| **0.05 (LIVE)** | **+3.57** | 16.54 | −12.93 | 1329 | 56.8 | −55.21 | +6.79 | +1.33 | ✅ both + |
| 0.08 | −10.54 | 17.09 | −27.57 | 1223 | 56.0 | −65.12 | −13.64 | +2.38 | ❌ |
| 0.12 | −47.14 | 20.61 | −67.74 | 887 | 47.5 | −50.13 | −18.33 | −28.60 | ❌ both − |
| 0.20 | −28.38 | 19.49 | −47.86 | 685 | 49.9 | −30.95 | −10.90 | −18.05 | ❌ both − |
| 0.30 | −24.78 | 17.08 | −41.86 | 520 | 47.9 | −28.15 | −17.75 | −7.02 | ❌ both − |
| 0.40 | −12.79 | 15.76 | −28.55 | 394 | 49.5 | −21.24 | −13.94 | +1.15 | ❌ (HL-fitted) |

## What this actually says

1. **Widening the entry gate UP loses money — decisively.** Every gate ≥ 0.08 is
   negative, most in BOTH halves. The premise "the lever needs more space to
   operate" is, for this lever, backwards: more space upward = more loss. The
   lever-authority audit's "the decisive value ~10.5% sits above the 0.075
   ceiling" is real, but reaching it is a LOSS — the tight ceiling is
   PROTECTIVE, not a defect.

2. **The current live gate (0.05) is marginally POSITIVE in simulation — not the
   "negative both halves" an earlier read of the live LEDGER suggested.** +3.57
   over 180d, both halves + (+6.79 / +1.33). The live realised book is negative
   (radar `cn`: ZEC+HYPE concentration, t 1.10→−0.32) because of execution +
   coin concentration + the specific window — but the GATE itself is not
   inherently a both-halves loser in simulation. Both are true; they measure
   different things.

3. **THE STRUCTURAL FINDING (matters more than the sweep): the strategy is
   COST-BOUND, not gate-bound.** At gate 0.05: median hold 9h, carry earned over
   that hold = **0.5 bps vs a 10 bps round-trip slip**. **Operative breakeven =
   0.97 TRUE apr (97% APR)** — the venue floor is 3.5%, ETH ~8%. Funding almost
   never reaches the level this needs to clear its own transaction cost. 56% of
   trades exit because the funding signal EVAPORATED (flip+cold) before enough
   carry accrued. The tiny positive rows (0.02, 0.05) are a handful of tp
   winners barely out-running slippage — noise around zero, not a durable edge.

## The real-money recommendation (operator authority)

- **Do NOT widen `live.funding.enter_apr` upward.** Measured: it loses. The
  bound's tight ceiling is correct and should stay.
- **The live arm is scratching around breakeven at best, negative in live
  realisation.** The productive lever is NOT the gate — it is COST: longer holds
  on genuinely high-funding coins only (fewer flips), or tighter execution. Absent
  that, idling the live funding arm loses nothing real.
- **Where autonomy CAN still earn:** the shadow books and execution-cost work —
  not gate-widening on a cost-bound live book. The brakes (cq–ct) make that
  autonomy trustworthy; this evidence says where it should and should NOT reach.

Full-tape (438d) re-run is a follow-up, but the conclusion is STRUCTURAL
(0.5bps carry vs 10bps slip → 97% breakeven) and does not turn on window length.
