# Crypto Bots — Weekly P&L Digest

**Week:** Mon 2026-06-22 → Sun 2026-06-28 (most recent completed week)
**Generated:** 2026-06-29 (Mon) · Dry-run / paper · simulated fills on live market data
**Source:** pnl-dashboard-production-858c.up.railway.app

---

## Realized P&L by trading bot

| Bot | Strategy | Realized P&L | Trades | W | L | Win % |
|---|---|---:|---:|---:|---:|---:|
| intraday-daytrader-5m | V5 5m daytrader | **−$14.03** | 86 | 9 | 77 | 10% |
| momo-breakout-alt | v8 breakout (alts) | **−$11.33** | 2 | 0 | 2 | 0% |
| momo-breakout-4h | V7 breakout | **−$0.70** | 1 | 0 | 1 | 0% |
| swing-dip-buyer | V6 swing | $0.00 | 0 | — | — | — |
| trend-golden-cross | V4 daily trend | $0.00 | 0 | — | — | — |
| **TOTAL (trading)** | | **−$26.07** | **89** | **9** | **80** | **10%** |

*Arb scanners (triangular-arb, cross-exchange-arb) excluded — optimistic paper, not real fills.*

## Prior-week comparison

No comparison available — trade history begins **2026-06-22**, so this is the **first full week** of recorded paper trading. Monthly June total is −$26.28 across 91 trades, i.e. essentially all activity occurred in this one week.

## Best / worst

- **Worst (by $):** intraday-daytrader-5m at −$14.03 — the volume engine (86 trades, 90% losers). Most losses are tiny trailing-stop exits, but they bleed steadily.
- **Worst (by severity):** momo-breakout-alt (v8) at −$11.33 on just **2 trades** (−5.7% of equity). Two large losers — concerning sizing/quality on the alt breakout sleeve.
- **Best:** momo-breakout-4h (V7), basically flat at −$0.70 on 1 trade — too little to read into.

## Is each strategy's validated edge showing yet?

**Too early — and the two bots that should prove the edge haven't fired.** The re-validation (REVALIDATION_2026-06-22.md) judged **V6 swing best risk-adjusted, V7 good in trends, V4 good on majors, and V5 a confirmed loser kept only as a paper control.** This week the live paper tape is consistent with that prior but provides almost no positive confirmation: V5 (daytrader) did exactly what its validation predicted — churned 86 trades into a −$14 loss with a 10% win rate, reaffirming it's a loser. Meanwhile **V6 (swing) and V4 (golden cross) placed zero closed trades all week** (V4 currently holds 1 open position; V6 has none), so their validated edges simply have not had a chance to show up — the strategies are selective and the market may not have offered setups. V7 and v8 each took 1–2 trades, which is far too small a sample to judge. Net: the only edge "showing up" so far is V5's known negative edge; the strategies expected to carry the book are still on the sidelines. Need several more weeks of V6/V4/V7 actually trading before any live read is meaningful.

## Health

| Bot | Status | Note |
|---|---|---|
| intraday-daytrader-5m | 🟢 online, fresh | trading normally |
| swing-dip-buyer (V6) | 🟢 online, fresh | **0 trades all-time** — no setups fired; watch it isn't mis-gated |
| trend-golden-cross (V4) | 🟢 online, fresh | 0 closed, 1 open position |
| momo-breakout-4h (V7) | 🟢 online, fresh | 1 closed trade |
| momo-breakout-alt (v8) | 🟢 online, fresh | 2 open trades, 2 closed |

No mapped trading bot was offline, stale, or halted during the week. (Outside the crypto map, the stock/IBKR/Alpaca feeds and listing-sniper showed as stale on the snapshot, but they're not part of this digest.)

---

*Dry-run paper trading on live market data — simulated fills. Not financial advice. Figures from the public dashboard at generation time.*
