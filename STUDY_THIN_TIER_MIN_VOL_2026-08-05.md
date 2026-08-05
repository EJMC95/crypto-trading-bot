# The thin-tier min_vol floor — "if it produces better numbers then proceed" (2026-08-05, (ka))

**The ask (operator, verbatim):** *"what is the most optimal min vol cage
floor"* → recommendation delivered → *"if it produces better numbers then
proceed!"* — a conditional signature. This study IS the condition's test,
run before anything shipped, with the decision rule pre-registered in the
driver's header before results existed
(`scratchpad/thin_tier_study.py`, preserved below).

## Method — the calibrated instrument, each tier at its own measured friction

`scripts/backtest_funding_lighter.py::run()` — the persistence-parity-fixed
replay of the Farmer's real rule (PERSIST_H 4, exit ratio 0.375, ladder
stop>tp>flip>cold>max_hold, 6 slots, 72h cap, $25 clips) — driven over
universes defined by the venue's OWN `daily_quote_token_volume` on 5-Aug,
30 days of Lighter's own funding + candles (93 books fetched, 0 skipped),
window ending 2026-08-05 05:00Z. Friction per tier from the (js) tx-hash
fill study (n=158): ≥$10M 0.27/0.97 bps per fill (median/p90); $1–10M 1.93;
<$1M 5.12/14.77.

**Pre-registered rule:** ship the floor down IFF the [0.1M,2M) added band
ALONE is positive at its tier-median friction at an EXPRESSIBLE gate (0.05
shipped / 0.12 cage-hi), both halves not-both-negative, AND the combined
wide universe charged fail-closed (every book at thin-tier slip) is not
materially worse than the incumbent at its own slip.

## Results (net $ on 6×$25 slots, 30d)

| cell | net$ | n | win% | maxDD | med hold | halves |
|---|---|---|---|---|---|---|
| INC ≥$10M @0.27bps g.05 | **+4.01** | 152 | 52.6 | −7.22 | 7.0h | +4.80/+1.02 |
| INC @0.97 (p90) | +3.48 | 152 | 52.6 | −7.26 | 7.0h | — |
| U2 ≥$2M @1.93 g.05 | **−11.61** | 211 | 53.6 | −19.63 | 9.0h | −9.00/+4.40 |
| U01 ≥$0.1M @5.12 g.05 (fail-closed) | +0.20 | 172 | 56.4 | −16.96 | 12.0h | −8.69/+19.19 |
| U01 @1.93 (sens) | +2.94 | 172 | 57.0 | −16.48 | 12.0h | — |
| BAND2 [2,10)M alone @1.93 g.05 | +1.76 | 116 | 61.2 | −12.56 | 11.0h | +0.80/+7.32 |
| **BAND01 [0.1,2)M alone @5.12 g.05** | **+14.83** | 158 | **65.8** | **−7.97** | 13.0h | **+7.68/+10.29** |
| BAND01 alone @5.12 g.12 | +8.31 | 315 | 49.5 | −9.28 | 5.0h | +6.30/+1.97 |
| BAND01 alone @14.77 g.05 (p90) | **+7.20** | 158 | 61.4 | −8.96 | 13.0h | — |
| BAND01 alone @14.77 g.12 (p90) | −6.89 | 315 | 45.7 | −15.77 | 5.0h | — |

**Rule A PASSES**: the thin band alone, at its own tier-median friction, at
the SHIPPED gate, nearly 4× the incumbent's net on the same window, both
halves positive, comparable drawdown — and still +$7.20 at the tier's p90.
The fail-closed combined cell (+0.20 vs +4.01) is flat, not materially
worse, with the stated caveat that the harness fills slots in volume order
while the real bot RANKS by |apr| — the truth sits between the combined and
band-alone cells.

## Secondary findings, recorded so nobody re-derives them

1. **Gate 0.12 is the WORSE in-tier gate** (churn doubles to n=315, p90
   flips to −$6.89) — the snapshot breakeven arithmetic that favoured a
   higher gate is overturned by the replay's tp/flip dynamics: the shipped
   0.05 admission with the tp/stop ladder harvests the tier better than a
   tighter admission. The higher expressible gate is deliberately NOT filed.
2. **The $2–10M band is the WEAK half of the widening on this window**
   (BAND2 alone +1.76 stop-heavy; U2 combined −11.61 with a −$54.90 stop
   bucket — slot interference makes the union worse than both parts). The
   filed `min-vol-2e6` candidate's ~11-Sep verdict is therefore genuinely
   informative — a subset question that de-risks reading `min-vol-1e5`.
3. **In-tier flips are POSITIVE** (+$5.49 over 60 flips in BAND01 at g.05)
   — unlike everywhere else in the fleet where the flip family loses.
4. **APR transience measured directly** (live snapshot, 6 days): of the
   five books that motivated the lever, H100 and XPD decayed 41–99% → 3.5%,
   TRUMP → the 10.5% resting default; XLM held −42%; SKR sits at −1611%
   (four-digit outlier, treat as suspect). The tier's harvestable object is
   a decaying rate — the replay prices this via its own tape; the snapshot
   alone would have misled in either direction.

## Honesty gates

30 days, one regime, one window; $25 clips (larger-clip scaling in thin
books UNMEASURED — the (js) gate rides along); iteration-order slot model
(no |apr| ranking); slip charged flat per trade (tail events beyond p90 not
modelled); SKR/CXMT four-digit APRs are inside the BAND01 numbers and CXMT
is the fleet's one quarantined-manipulation symbol — the arm's own
SCAN_MAX_SLIP_BPS / MAX_SPREAD_BPS vetoes stay senior per-book at runtime,
which the harness does not model. This study ranks TIERS and prices a cage;
it promotes nothing — the paired live-vs-shadow bar remains the only
promotion evidence ((gt): a harness may rank what it replays; the judge's
bar rules real money).

## What shipped on this signature ((ka))

- `fleet_tuning.py`: `xp.funding.min_vol` lo 2e6 → **1e5** AND
  `live.funding.min_vol` lo 2e6 → **1e5**, signature recorded in both
  notes. The live half is REQUIRED for the evidence to flow at all: the
  judge's both-cage clamp invariant (statics must clamp clean in BOTH
  cages, (ju)-pinned) makes an xp-only floor structurally unexercisable —
  mutation-verified: reverting only the live lo reddens the candidate cage
  loop. The real-money gate was never this cage; it is the paired bar
  (judge sole `live.funding.*` writer) + fade-watch, unchanged.
- `experiment_judge.py`: `min-vol-1e5` filed FOURTH (above the
  negative-prior `enter-gate-0.105`, below the filed `min-vol-2e6` whose
  subset verdict lands first) — order pinned `names[:5]`,
  mutation-verified.
- OPERATOR_QUEUE item 2 recorded DECIDED; schedule: min-vol-2e6 ~4-Sep →
  min-vol-1e5 ~mid-Sep → enter-gate-0.105 slides right, all conditional on
  no predecessor promoting.
