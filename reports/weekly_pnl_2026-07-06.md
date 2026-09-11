# Crypto Bots — Weekly P&L Digest

**Report date:** 2026-07-06 (Mon) · **Completed week covered:** Mon 2026-06-29 → Sun 2026-07-05
*Dry-run (paper) bots trading live market data with simulated fills. Not financial advice.*

## Reporting week — realized P&L (Jun 29 – Jul 5)

Only the V5 daytrader closed trades this week; V4/V6/V7/v8 realized nothing (idle or holding open positions).

| Bot | Strategy | Realized P&L | Trades | W / L | Win % |
|-----|----------|-------------:|-------:|:-----:|:-----:|
| crypto-intraday-15m (V5) | 5m daytrader | **−$8.92** | 79 | 17 / 62 | 21.5% |
| crypto-trend-daily (V4) | daily trend, majors | — | 0 | 0 / 0 | — |
| crypto-swing-daily (V6) | swing dip-buyer | — | 0 | 0 / 0 | — |
| crypto-breakout-4h (V7) | 4h breakout | — | 0 | 0 / 0 | — |
| crypto-trendmomo-4h (v8) | SMA momentum | — | 0 | 0 / 0 | — |
| **TOTAL (trading bots)** | | **−$8.92** | **79** | **17 / 62** | **21.5%** |

*Arb scanners (triangular-arb, cross-exchange-arb) excluded — optimistic paper.*

## Week-over-week

| Metric | Prior wk (Jun 22–28) | This wk (Jun 29–Jul 5) | Δ |
|--------|-------------------:|---------------------:|:--:|
| Total realized | −$26.07 | −$8.92 | **+$17.15 (loss cut ~66%)** |
| Trades | 89 | 79 | −10 |
| Bots that traded | 3 (V5, V7, v8) | 1 (V5) | −2 |

- **Best:** n/a — no bot was green. Least-bad and only mover: **V5 −$8.92** (also improved from −$14.03 the prior week).
- **Worst:** **V5** by default (sole trader). The prior week's big loser, v8/crypto-trendmomo-4h (−$11.33), did not close any trades this week.

## Is the validated edge showing up yet?

Too early / too few trades for most of the fleet. Per the 22-Jun re-validation (V6 best risk-adjusted, V7 good in trends, V4 good on majors, V5 a confirmed loser): the **only** strategy to actually trade this week was **V5**, and it lost again (−$8.92, 21.5% win rate) — fully consistent with its "confirmed loser, kept on paper" verdict. The three strategies with a real validated edge (V4, V6, V7) plus v8 closed **zero** trades in the completed week, so their edge has had no chance to express itself in live paper — they're either between setups or holding open positions (at the Jul-7 snapshot V7 was carrying 6–8 mostly-red breakout longs and v8 was holding a green ETH position). Verdict: fleet-wide edge is **unproven in live paper so far**; the only signal is negative (V5) and it's the one we already expect to lose. Need V4/V6/V7 to actually cycle trades before drawing conclusions.

## Health

- No crypto trading bot was offline, stale, or halted at the snapshot (feed_stale: false, n_stale: 0). All of V4–v8 reported `status: online`, `stale: false`.
- Idle ≠ halted: V4/V6/V7/v8 had no closed trades this week but were live and holding/scanning normally.
- Nothing to flag on the crypto fleet this week.

---
*Source: pnl-dashboard periods.json / pnl.json / trades.json, fetched 2026-07-08. Paper trading only.*
