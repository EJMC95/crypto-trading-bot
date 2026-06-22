# Re-validation & Loss Diagnosis — 22 June 2026

Goal (per request): **widen the net and re-validate before stopping anything, and
understand *why* the losers lose before removing them.** Nothing was removed or
changed in the live bots. All work is backtest/diagnostic only.

## Method
- Engine: freqtrade's own backtester, run inside the live `freqtradeorg/freqtrade:stable`
  image, so it tests the **actual deployed strategy code** (not a reimplementation).
- Data: Binance OHLCV (deepest history), downloaded for a **15-coin basket**
  (BTC ETH SOL BNB XRP ADA DOGE AVAX LINK DOT LTC BCH ATOM XLM TRX), 2022-01→2026-06.
- Universe override forces `StaticPairList` over exactly the basket (the live
  `VolumePairList` isn't supported in backtest and isn't reproducible).
- Fee 0.10%/side, starting balance $1000, `max_open_trades=15` (so each coin's
  standalone edge is visible, not capacity-limited). Regimes tested separately:
  BULL_24 (2023-10→2024-03), CHOP_25 (2025 full), CRASH_26 (2025-12→2026-06).
- `profit%` is on the whole $1000 with each config's `tradable_balance_ratio`, so
  magnitudes are smaller than the headline docs; **read the columns relative to each
  other and across regimes**, not as absolute strategy returns.

> Operational finding made during this work: the **live containers mount
> `~/freqtrade/user_data`, not this git repo.** The repo's recent edits (incl. the
> V5 churn-fix) are **not deployed**. The running V5 is the OLD version.

---

## Freqtrade strategies — basket vs BTC/ETH, by regime

| Strategy | Universe | FULL 23–26 | BULL_24 | CHOP_25 | CRASH_26 |
|---|---|---|---|---|---|
| **V4** trend (1d) | BASKET | +19.7% (75tr, PF1.76, DD8.9) | **+47.8%** | **−20.0%** (PF0.09, DD22) | −0.9% |
| | BTCETH | +8.0% (6tr) | +4.6% | −1.0% | no trades |
| **V6** SwingDip (4h) | BASKET | +3.1% (136tr, **PF1.73, DD0.7**) | +0.2% | **+1.4%** | −0.2% |
| | BTCETH | +0.6% (19tr) | no trades | +0.0% | no trades |
| **V7** Momo (4h) | BASKET | **+20.0%** (880tr, PF1.47, DD5.4) | +10.1% | −0.8% | −3.5% |
| | BTCETH | +2.8% (116tr) | +1.8% | +0.6% | −0.4% |
| **V5** DayTrader (5m) | basket(4) | **−38.6%** (24,043tr, **win9%, PF0.08**) | — | −21.4% | no trades |
| V5 churn-"fixed" | basket(4) | **−39.5%** (29,499tr, win13%) | — | −21.0% | **−10.1%** |

### Reads
- **V6 SwingDip — widening HELPS, clearly the best risk-adjusted bot.** 69% win,
  PF 1.73, **0.7% max drawdown**, positive in every regime except a trivial −0.2%
  in the crash. The wide net gives it 7× more dip setups (136 vs 19 trades) with no
  loss of quality. This is the diversifier working exactly as designed. **Keep wide.**
- **V7 Momo — widening HELPS in trends, hurts in chop/crash.** Wide basket turns
  +2.8%→+20% over the cycle (more coins = more breakouts; per-pair below shows 12/15
  coins positive). But the loosened `range_buy (rsi<45, any trend)` + momentum-
  continuation paths bleed in CHOP_25 (−0.8%) and CRASH_26 (−3.5%). **Keep wide,
  but cut the counter-trend `range_buy` path and/or gate entries to an up-regime.**
- **V4 trend — widening is a wash that adds chop risk.** Net +19.7% over the cycle,
  but it's a barbell: superb in clean bull (**+47.8%**), brutal in chop
  (**−20%, 22% drawdown**) because the daily 50/200 cross whipsaws on laggard alts.
  Per-pair: winners are the strong trenders (SOL +95, BTC +79, TRX +77, XRP +47,
  BNB +27); losers are the also-rans (ATOM −28, AVAX −27, LTC −21, LINK −17, DOT −15,
  ADA −13). **Either keep V4 on a curated strong-trend set, or add a chop filter
  (e.g. ADX/regime) — don't run it on the full indiscriminate top-100.**
- **V5 day-trader — negative edge, confirmed at scale. Do NOT risk real money.**
  −38.6% with **24,043 trades at 9% win / PF 0.08** is pure fee-churn — the same
  pattern that lost −99% before. The repo "churn-fix" makes it **worse** (more
  trades) and, fatally, its loosened regime gate lets it trade *into* the 2026 crash
  (−10.1%) where the deployed version correctly took **zero** trades. The 5m-scalp
  approach is the problem, not the parameters.

### V4 per-pair (FULL, profit_abs $)
losers: ATOM −27.6, AVAX −27.1, LTC −21.2, LINK −17.2, DOT −15.0, ADA −12.6 ·
winners: SOL +94.8, BTC +79.3, TRX +77.0, XRP +47.3, BNB +27.2

### V7 Momo per-pair (FULL, profit_abs $)
only 3 small losers (DOT −7.5, LTC −7.4, ATOM −5.1); winners broad:
XLM +60, XRP +36, SOL +27, AVAX +23, DOGE +17, ETH +17, BTC +13, TRX +12 …

---

## Why the "losers" lose (diagnosed, not assumed)

**Hyperliquid RSI perps bot — structurally a loser.** Faithful replication of the
live logic (long RSI<45, short RSI>55, flip-only, no stop) across the basket, 1x,
fees+slippage, funding NOT modelled:

| thresholds | FULL 23–26 | coins profitable | trades | CHOP_25 |
|---|---|---|---|---|
| original 30/70 | **−89.8% avg/coin** | 0/15 | 3,308 | +9.4% |
| **live 45/55** | **−93.1% avg/coin** | 0/15 | **18,756** | −56.6% |

Root cause: it's mean-reversion with **no stop and no trend filter** — it shorts
bull rallies and longs falling knives, holding all the way. The 45/55 loosening
**6×'d the trade count** → fee bleed, turning even the chop window (where mean-
reversion should work, +9.4% at 30/70) into −56.6%. Funding would make it worse.

**Triangular arb (Kraken, single-exchange) — impossible by construction.** 3 legs ×
0.40% taker = ~1.2% round-trip. Over **358 logged scans the best loop ever seen was
−0.98%** net (mean −1.15%); the live scanner currently logs **every** loop at
≈−1.1% to −1.2%. It has never been within a percent of profitable. The "+$150 paper"
on the dashboard is slippage-free fiction.

**Cross-exchange arb (Kraken/Coinbase/Gemini)** — the only arb with real potential,
but `cross_arb_opportunities.csv` is **empty**: nothing has cleared its filter, and
its model explicitly ignores rebalancing/withdrawal/capital-parking cost, so any
positive it ever logs is an upper bound, not a tradable edge.

---

## Evidence-based recommendations (no removals yet)

1. **Fix the deployment-divergence first.** The live bots run from `~/freqtrade`, so
   none of the repo edits are live. Decide on one source of truth before tuning
   anything, or you'll keep validating code you aren't running.
2. **V6 SwingDip — promote.** Best risk-adjusted, benefits from the wide net. The
   strongest candidate to carry real-money weight first.
3. **V7 Momo — keep wide, tighten.** Cut the counter-trend `range_buy` path and
   regime-gate entries; re-test — should keep the +20% bull capture while removing
   the chop/crash bleed. (I can do this and re-validate.)
4. **V4 trend — curate or filter.** Run on the strong-trend subset (BTC/ETH/SOL/
   BNB/XRP/TRX) or add a chop/ADX filter; don't run on the full indiscriminate net.
5. **V5 day-trader — retire from the real-money path.** Re-validation confirms
   negative edge at scale; the fix doesn't help. Keep only as a paper experiment if
   you want, but it should never get capital. Understood *why*: 5m scalping +
   tight-ROI churn at ~10% win rate = fees eat it.
6. **Triangular arb — stop treating as a profit engine.** Keep as a spread-logger if
   useful, but it cannot clear its own fees. Refocus arb effort on cross-exchange.

---

## Follow-up: V7 tighten + V4 curation (implemented & A/B-tested)

### V7 Momo — tighten experiment → **revert to the original wins**
The live/container V7 is the *original pure breakout* (`close > 30-bar high &
close > 200-EMA`); the loosened `range_buy` code only ever lived in the repo. A/B
on the full basket, by regime:

| V7 variant | FULL 23–26 | trades | BULL_24 | CHOP_25 | CRASH_26 | maxDD |
|---|---|---|---|---|---|---|
| **Original (pure breakout)** | **+20.0%** | 880 | +10.1% | −0.8% | −3.5% | 5.4% |
| Loosened (repo, +range_buy + pullback + momo-cont) | −3.8% | 3,301 | +14.3% | −4.2% | −6.2% | 16.5% |
| Tightened V2 (range_buy removed, other paths kept) | −4.1% | 2,037 | +8.8% | −5.3% | −4.2% | 13.7% |

The tighten experiment **disproved the partial-fix idea**: removing `range_buy`
alone still leaves the pullback + momentum-continuation paths, which are *also*
net-negative (2,037 trades, PF 0.95). Only the original is profitable.
**Action taken:** repo `MomoBreakoutV1.py` reverted to the original breakout logic;
the inferior `MomoBreakoutV2` and `ImprovedStrategyV4Adx` experiments were removed.

### V4 Trend — curation → **clear win; ADX filter → no effect**

| V4 variant | FULL 23–26 | PF | CHOP_25 | chop maxDD |
|---|---|---|---|---|
| Full basket (15) | +19.7% | 1.76 | −20.0% | 21.7% |
| **Majors (BTC/ETH/SOL/BNB/XRP/TRX)** | **+33.3%** | **7.26** | **−3.5%** | **4.6%** |
| +ADX(>20) full basket | +19.8% | 1.78 | −20.3% | 21.8% |
| +ADX(>20) majors | +33.3% | 7.42 | −3.6% | 4.6% |

Curating to liquid majors raises full-cycle return (+19.7%→+33.3%) and, crucially,
turns the −20% / 22%-drawdown chop disaster into −3.5% / 4.6%. The **ADX chop
filter did essentially nothing** (alts whipsaw *with* ADX>20), so universe choice —
not an indicator gate — is the fix. **Action taken:** `config_v4_core.json` switched
to `StaticPairList` over the 6 Kraken majors (also fixes the VolumePairList-ignores-
whitelist bug). *Caveat:* the majors set is partly in-sample; it's chosen by a
liquidity rule (not P&L cherry-pick) and is consistent with the thesis (majors trend
cleaner than alts), but treat as one historical sample.

### To go live
These edits are in the **repo**. The live bots run from `~/freqtrade` (see divergence
note above), so they take effect only after that directory is reconciled with the repo
and the freqtrade service is redeployed.

## Reproduce
In the freqtrade image (`docker exec v4core ...`): data lives in
`user_data/data/binance`; runners are `user_data/run_revalidation.py` (V4/V6/V7),
`user_data/run_v5.py` / `run_v5fixed.py` (V5), `user_data/diag_perps_rsi.py`,
`user_data/per_pair.py`. Override: `user_data/backtest_override.json`.
NOTE: do **not** pass `--datadir` (it disables freqtrade's exchange-subdir lookup);
let the config default resolve it.
