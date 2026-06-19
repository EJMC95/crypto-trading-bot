# Bot P&L Review & Post-Mortem — 19 June 2026

## Headline

**No real money was lost.** Every bot is in `dry_run` / paper mode. The "red" you're
seeing is from **backtests and paper runs**, not your wallet. The real problem is the
opposite of reckless trading: **almost none of the bots traded at all**, and the one
that *did* (in backtest) was a strategy that loses catastrophically in a downtrend.

---

## Current P&L by bot

| Bot (db) | Strategy | Closed trades | Realized P&L | Status |
|----------|----------|--------------:|-------------:|--------|
| v4_core | ImprovedStrategyV4 | 0 | $0.00 | Running, never fired a signal |
| v5_kraken | DayTraderV5Gated | 0 | $0.00 | Running, never fired a signal |
| v6_swing | SwingDipV1 | 0 | $0.00 | Running, never fired a signal |
| v7_momo | MomoBreakoutV1 | 0 | $0.00 | Running, never fired a signal |
| momo (Hyperliquid) | Donchian/EMA | 0 | $0.00 | Pure `HOLD`, intermittent data errors |
| triangular arb | — | 0 | $0.00 | **Crash-looping** (fixed below) |

All four freqtrade SQLite databases are empty (0 rows in `trades` and `wallet_history`) —
only heartbeat keys in `KeyValueStore`. So the on-paper P&L is flat $0, and the real cost
is **opportunity cost plus the near-miss disaster the backtests exposed.**

### The actual "red" — where it shows up

The loss numbers in your own notes come from backtesting the **live 5-minute scalper
(`DayTraderV1Aggro`)** over the Dec 2025 → Jun 2026 crash window:

| Asset | Strategy | Return | Trades | Win % |
|------|----------|-------:|------:|------:|
| BTC | DayTraderV1Aggro (the bot you were running) | **−99.1%** | 976 | 16% |
| ETH | DayTraderV1Aggro | **−99.4%** | 1,044 | 18% |
| BTC | DayTraderV5Gated (regime-gated replacement) | 0.0% | 0 | — |

That is the mistake that nearly cost real money: an ungated scalper taking ~1,000 small
longs into a falling market and bleeding to near-zero on **fees + losing trades**.

---

## The mistakes, and what to learn from each

**1. Over-strict entry logic → zero trades.** Every freqtrade bot required a rare
"perfect storm" of 3–5 simultaneous conditions, so none ever entered. *Lesson: before
deploying, backtest and confirm the strategy actually fires at a sane frequency. A bot
that never trades isn't safe — it's just untested.*

**2. Trading a thin/wrong market.** Bots were set to `BTC/USDT` on Kraken (a shallow
secondary book), producing endless `Could not fetch OHLCV … Giving up`. *Lesson: trade
the deep book (`BTC/USD`, `ETH/USD` on Kraken) and treat repeated data-fetch failures as
a config bug, not noise.*

**3. Config didn't match intent.** `config_daytrader_binance.json` actually had
`"exchange": "kraken"`, so the "Binance" and "Kraken" bots ran the *same pair on the same
exchange* — zero diversification, doubled BTC exposure. *Lesson: assert that each config's
exchange/pair matches its name and purpose; a quick sanity check would have caught this.*

**4. Running the weakest idea, benching the strongest.** The proven V4 daily trend filter
(+209% vs +120% buy-and-hold in backtest, half the drawdown) was *not* deployed, while two
5-minute scalpers — the exact "churn + fees" pattern V4's own notes warn against — were
live. *Lesson: deploy the strategy with a validated edge; keep experiments on paper until
they earn promotion.*

**5. No macro-regime gate.** The scalper had nothing stopping it from buying into a
six-month downtrend. The one-line fix (`DayTraderV5Gated`: only go long when daily
50-EMA > 200-EMA) turns −99% into 0% by simply sitting out the bear. *Lesson: a cheap
regime filter is the highest-leverage risk control you have.*

**6. Arbitrage threshold below cost.** The arb bot needed 0.50% edge but Kraken fees are
~0.40%/leg × 3 legs ≈ 1.2%+, so no loop was ever profitable (848 cycles, 0 passed,
"best depth −100%"). *Lesson: model round-trip fees first; if the threshold is below total
cost, the strategy can't win by construction.*

**7. Crashes masked as "it keeps restarting."** See below — a parsing bug killed the arb
process, and `KeepAlive` respawned it every 30s, hiding a hard bug as a flaky service.
*Lesson: catch and log exceptions per cycle so one bad tick doesn't take down the process;
don't let a supervisor paper over real crashes.*

---

## Why the triangular arb bot keeps crashing — root cause & fix

**Root cause (confirmed and reproduced):** in `triangular_arb.py`, `walk_book()` unpacked
order-book levels with `for price, size in order_book.get("asks", [])`. ccxt returns Kraken
L2 levels as **three** elements `[price, size, timestamp]`, not two, so every time a loop
passed the prefilter and pulled a real book, it threw:

```
ValueError: too many values to unpack (expected 2)   (triangular_arb.py line 119)
```

The process then exited, and the `com.eamon.tri-arb` LaunchAgent (`KeepAlive=true`,
30s throttle) restarted it — producing the endless restart loop you saw.

**Fix applied** (both the asks and bids loops now unpack defensively):

```python
for level in order_book.get("asks", []):
    price, size = level[0], level[1]   # ignore Kraken's 3rd timestamp element
```

Verified: the file parses, the old code reproduces the exact crash, and the new code parses
3-element levels cleanly.

**Two follow-ups worth doing** (not yet applied — your call):
- Wrap the per-cycle body in `try/except` + log-and-continue, so any future bad book can't
  kill the process again.
- Investigate the "0 books pulled / best depth −100%" — the prefilter is rejecting
  everything, so the bot would find no opportunities even without the crash. Likely the
  same fee-vs-threshold issue as mistake #6.

---

## Recommended next steps

1. Deploy V4 (proven core) + V5Gated (safe experiment) as the two live paper bots; retire
   the ungated 5m scalper configs.
2. Restart the arb bot with the fix; watch `arb_run.log` — the `ValueError` traceback
   should be gone.
3. Let everything run on paper for a week and re-pull these P&L numbers before risking any
   real capital.
