# Idle-Bot Deep Dive — 7 July 2026

**Method:** instead of guessing why bots hold fire, I pulled live market data (Hyperliquid daily candles for the regime universe, Kraken 4h for the spot universe) and computed *exactly what each bot's gates see right now*. Idleness splits into three very different categories, and the right response differs for each.

---

## 1. perps-regime-switch (⚖️ Two-Way Tide) — ARMED, not broken

The daily regime gate — the thing two blind gate-lowerings tried to fix — is **wide open**:

| Coin | ADX(14) | Direction | Verdict |
|---|---|---|---|
| BTC | 29.5 | down | **SHORT-window** |
| ETH | 26.0 | down | **SHORT-window** |
| XRP | 21.5 | down | **SHORT-window** |
| BNB | 20.6 | down | **SHORT-window** |
| DOGE | 36.5 | down | **SHORT-window** |
| AVAX | 34.6 | down | **SHORT-window** |
| LTC | 29.7 | down | **SHORT-window** |
| LINK | 20.1 | down | **SHORT-window** |
| SOL | 23.2 | flat (EMA50 slope +) | dir-flat |
| ADA | 37.8 | flat (slope ≈ 0) | dir-flat |

Eight of ten pairs are in a legitimate short regime with ADX far above the 17 gate. **The binding constraint is the entry trigger, not the regime**: it shorts only a fresh 4h close *below the prior 15-bar low*, and the market has spent the last two days bouncing (the same bounce breakout-4h bought into). A Donchian short engine correctly refuses to short a rally — the trades it's waiting for arrive on the next leg down.

The diagnostics shipped today (`[regime-diag]` per pair per 4h candle) will confirm this from `railway logs` — you'll see `SHORT-window` verdicts with price sitting above `dcL`.

**Options, in order of my recommendation:**
1. **Wait (recommended).** The design is correct: short fresh weakness, never bounces. With 8/10 pairs armed, the next 4h breakdown fires real entries. Zero risk of design damage.
2. **Add a second, tagged entry mode — `short_retest_fail` (half stake).** In a SHORT-window, enter when a bounce *rejects* the 4h EMA50 from below (rally exhausts at resistance) instead of waiting for new lows. This is the classic pullback-entry variant of trend-following: better entry price, earlier participation, but more whipsaw risk — which is why it gets half stake, its own tag (so the brain measures it separately), and the same structure exits. This is the one accelerator that adds information rather than loosening discipline.
3. **Shrink `entry_lookback` in short windows only.** Not recommended — asymmetric knobs tuned to the current tape are exactly how curve-fitting starts.

## 2. Disciplined idlers — the gates are doing their job

**crypto-swing-daily (SwingDipV1):** current 4h RSI across its majors is 50–56 against a buy gate of 42. In the last week the deepest reading was 43.2 (ADA) — it *grazes* the gate on flush days and fires only when a real flush coincides with its other conditions. In a bear market that grinds sideways-up between dumps, weeks of silence are the correct output. Options: leave it (recommended — it has 1 open position doing fine); or pilot `buy_rsi 42→45` at half stake under a new tag so the brain can grade the looser gate honestly. Don't raise stake and threshold together — you'd never know which change did what.

**crypto-trend-daily (golden-cross):** 2 of 15 pairs in a golden cross. A daily 50/200 trend bot in this tape *should* hold cash — its one +$6.44 ROI winner already paid for all 12 of its probe losses. The idle capital question belongs to the cross-bot design (see the companion doc): idle regime-gated capital is exactly what a fleet-level allocator could lend to the short engines during down-regimes.

**crypto-breakout-4h:** not idle this week — probing the bounce with correlated longs, which is why it now has the max_open 6 cap it was missing.

## 3. Mislabeled or structural cases

**crypto-trendmomo-4h: not actually idle — it's full.** `max_open_trades = 2`, and it holds 2 (ETH +$3.53, SOL). The bot looks quiet because its book is tiny. Option: raise to 3–4 — defensible since it's equity-positive with the symmetry fix in, and 4h cadence keeps fees viable; keep stakes unchanged so risk grows linearly and visibly. Or leave until it banks more closed evidence (only 2 lifetime closes, both pre-fix).

**scanner-triangular-arb: a correct null result, permanently.** 848 cycles, best loop −1.04% *after fees* — single-venue triangular arb on Kraken cannot clear the fee floor, and that finding is stable. Three honest options: (a) **retire the service** — banks the lesson, saves the resources; (b) **repoint it as a market-structure sensor** — its spread/depth telemetry is a decent chop/liquidity signal the pulse could ingest (zero new infra, it already publishes `best_depth_pct`); (c) leave it running as a monitor. I'd do (b) — it costs nothing and feeds the cross-bot layer.

**Family bots (mum/dad/avo-maria/georgia):** era-zero as of today's isolation cutover — each now runs once, in its own service, on its own volume. Mum took its first clean trade minutes after boot. Two clean weeks before judging them; their pre-cutover data is quarantined.

**perps-funding-carry:** rebuilt today (flip-grace / fee-payback / bleed-stop exits + 6h persistence entry filter). Expect *far fewer* closes — that's the fix working, not idleness. The first `decay_paid` exit in the ledger is the signal that a carry survived to fee payback. If every close is still `flip`, the universe is too spiky → next lever is majors-only.

---

## The one-line summary

Idleness here is mostly **discipline visible in real time**: the regime engine is armed and waiting for legal prey, the dip buyers are waiting for a flush, the trend bot is waiting for a regime. The two genuine actions available without damaging any design: ship the `short_retest_fail` half-stake mode on regime-switch, and raise trendmomo's cap to 3 — both tagged, both measurable, both reversible.
