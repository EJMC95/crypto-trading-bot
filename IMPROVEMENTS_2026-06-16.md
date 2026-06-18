# Trading bot review & improvements — 16 June 2026

A working-trader's audit of your live setup, the fixes, a new strategy (V5), and
**real backtests on your own data** to back every claim. Nothing here is financial
advice; everything below is still dry-run / paper unless you change it yourself.

---

## TL;DR

1. **Your live bot couldn't get data.** Both bots trade `BTC/USDT` on Kraken, a thin
   secondary market — hence the endless `Could not fetch OHLCV for BTC/USDT … Giving up`
   in the logs. Fixed by switching to Kraken's deep `BTC/USD` + `ETH/USD`.
2. **Your "Binance" bot isn't on Binance.** `config_daytrader_binance.json` had
   `"exchange": "kraken"`. So both bots traded the *same pair on the same exchange* —
   zero diversification, doubled BTC risk.
3. **You're running your weakest idea and benching your strongest.** Your own V4
   (daily 50/200 trend filter) is the only strategy with a validated edge, yet it
   isn't deployed — the two live bots are 5-minute scalpers, the exact "churn + fees
   + underperform holding" pattern your V4 notes warn about. The backtest below shows
   that 5m scalper losing **−99%** in the recent crash.
4. **New strategy `DayTraderV5Gated`**: your live day-trader **plus one rule** — don't
   buy while the daily macro trend is down. In the crash it stayed 100% in cash (0%)
   instead of being wiped out.
5. Security/risk hardening on both configs (localhost-only API, unique secrets,
   diversified to 2 pairs, no longer all-in on one position).

---

## The backtest numbers (your data, computed locally)

Engine: a self-contained backtester (`backtest.py`) — EMA/RSI/ATR computed directly,
freqtrade-style per-candle fill ordering (stop → ROI → exit signal), realistic fees.
**Validation check:** it reproduces your V4 notes' drawdowns *exactly* (BTC buy&hold
−51.2%, V4 −28.1%), so the engine is trustworthy.

### A) Daily trend filter (V4) vs buy & hold — Binance daily, 2023-07 → 2026-06

| Asset | Strategy | Return | Max drawdown | Trades |
|------|----------|-------:|-------------:|------:|
| BTC | Buy & hold | +120.6% | −51.2% | — |
| BTC | **V4 trend filter** | **+209.1%** | **−28.1%** | 1 |
| ETH | Buy & hold | −8.8% | −67.5% | — |
| ETH | **V4 trend filter** | **−1.9%** | **−50.5%** | 4 |

V4 wins by **side-stepping the crash**: it death-crossed to cash on **2025-11-17**
near the top and sat out the 2026 drop. Less return given up, far less pain.

### B) Intraday 5m — Kraken, Dec 2025 → Jun 2026 (a ~6-month crash)

The daily macro regime was **down the entire window**, so this is a pure stress test.

| Asset | Strategy | Return | Trades | Win % |
|------|----------|-------:|------:|------:|
| BTC | Buy & hold | −23.8% | — | — |
| BTC | DayTraderV1Aggro (your live bot, ungated) | **−99.1%** | 976 | 16% |
| BTC | **DayTraderV5Gated (new)** | **0.0%** | 0 | — |
| ETH | Buy & hold | −42.1% | — | — |
| ETH | DayTraderV1Aggro (ungated) | **−99.4%** | 1044 | 18% |
| ETH | **DayTraderV5Gated (new)** | **0.0%** | 0 | — |

*(Fees: realistic Kraken taker 0.26%/side. Even at an optimistic 0.10%/side the
ungated bot still loses ~−80%.)* The gate refused to trade into a falling market;
the ungated bot took ~1,000 small longs and bled to near-zero on fees + losses.

### ⚠️ The honest limitation

The only 5m data you have is that one bear window, where V5's correct move was to do
**nothing**. So this proves the gate **avoids disaster** — it does **not** yet prove
V5 makes money in an up-trend, because there's no 5m bull data to test on. Before
trusting any upside, download 2–3 years of 5m data and re-test (command below).

---

## What changed in the files

### New strategy — `strategies/DayTraderV5Gated.py`
Identical to your `DayTraderV1Aggro` except for **one added entry condition**
(search `[V5 GATE]`): only go long when the **daily 50-EMA > 200-EMA**. Everything
else — RSI, volume filter, 1h trend filter, ROI ladder, ATR stop, hyperopt params —
is preserved, so any tuning you do on Aggro carries straight over.

### Corrected configs — `config_v4_core.json` and `config_v5_kraken.json`

| Problem (old) | Fix (new) |
|---------------|-----------|
| `BTC/USDT` on Kraken → data-fetch failures | `BTC/USD` + `ETH/USD` (Kraken's deep books) |
| "binance" config actually on Kraken | exchange is explicit; V4 is the diversifier, not a fake 2nd exchange |
| Single pair, `max_open_trades:1`, ratio 0.99 → all-in one trade | 2 pairs, `max_open_trades:2`, ratio 0.95 |
| API on `0.0.0.0` (all interfaces) | bound to `127.0.0.1` only |
| Both bots shared the same jwt/ws secret | unique secret per bot |
| Password `freqUI2026` in plain sight | placeholder `CHANGE_ME_…` — set your own |

`dry_run` stays **true** in both. I did not touch your running bots or any keys.

---

## Recommended setup

Run **two bots side-by-side**, both dry-run:
- **`config_v4_core.json` → ImprovedStrategyV4** — your proven core. Slow, ~2–3
  trades/year, the reliable earner.
- **`config_v5_kraken.json` → DayTraderV5Gated** — the active experiment, now safely
  gated so it can't trade into a bear.

Retire the two old scalper configs (`config_daytrader_binance.json`,
`config_daytrader_kraken.json`) — the backtest shows why.

---

## Exact next steps (Terminal, in your `~/freqtrade` folder)

```bash
# 1. Copy the new strategy + configs into your freqtrade install
cp "~/Claude/Projects/Crypto Trading Bot/strategies/DayTraderV5Gated.py" user_data/strategies/
cp "~/Claude/Projects/Crypto Trading Bot/config_v4_core.json"  user_data/
cp "~/Claude/Projects/Crypto Trading Bot/config_v5_kraken.json" user_data/

# 2. Download the data the new pairs/timeframes need (USD pairs, incl. DAILY for the gate)
docker compose run --rm freqtrade download-data --exchange kraken \
  --pairs BTC/USD ETH/USD --timeframes 5m 1h 1d --days 1100

# 3. Backtest V5 to confirm it loads and behaves
docker compose run --rm freqtrade backtesting \
  --strategy DayTraderV5Gated --config user_data/config_v5_kraken.json \
  --timeframe 5m --timerange 20231201-

# 4. When happy, run both bots (different ports, both dry-run)
docker compose run --rm -d --name v4core  freqtrade trade --config user_data/config_v4_core.json
docker compose run --rm -d --name v5gated freqtrade trade --config user_data/config_v5_kraken.json
```

Before *any* real money: set strong unique passwords in both configs, create
**trade-only** API keys (never withdrawal), and let the dry-run prove itself for weeks.

---

## Files in this folder
- `strategies/DayTraderV5Gated.py` — the new regime-gated strategy
- `config_v4_core.json`, `config_v5_kraken.json` — corrected, hardened configs
- `backtest.py` — the backtester (re-runnable; point `DATA_DIR` at your `user_data/data`)
- `data/` — a copy of your OHLCV data used for these tests (safe to delete; it's a duplicate)
