# CLAUDE.md — crypto-trading-bot Fleet

## What This Repo Is
Eamon's full crypto trading bot fleet. Multiple strategies running on paper (dry run) with $1,000 starting balance each, no top-ups. Dashboard lives at https://pnl-dashboard-production-858c.up.railway.app/

## Fleet Overview

### Freqtrade Bots (new July 2026 — paper trading, $1,000 each)
The NFI/E0V1E/BinHCluc/FreqAI launch configs were replaced within days
(git: `config_*.json "-> proven strategy"`); what actually runs is the
in-house strategies on Kraken. Config `timeframe`/`stoploss` OVERRIDE the
strategy files — the table below is the config-resolved truth.
| Bot ID | Name | Strategy | Exchange | Timeframe | Stop |
|--------|------|----------|----------|-----------|------|
| freqtrade-mum | 👩 Mum | TrendMomoV1 | Kraken | 4h | -8% |
| freqtrade-dad | 👨 Dad | MomoBreakoutV1 | Kraken | 1h | -6% |
| freqtrade-avo-maria | 🙏 Avo Maria | SwingDipV1 | Kraken | 4h | -10% |
| freqtrade-georgia | 🔮 Georgia | DayTraderV5Gated | Kraken | 15m | ATR ≤5% |

Since 2026-07-13 the same four strategies ALSO run as **Lighter shadow
books** (`lighter_family_bot.py`, Railway service `family-lighter-shadow`,
deploys from `claude/lighter-gate0`): signals from Lighter's own candles,
ShadowBroker book-VWAP fills, funding drag modelled, rows
`freqtrade-*-lshadow`. The Kraken paper bots are the control arm; the port
refuses `lighter_live` in v1.

### Existing Bots (already running)
| Bot ID | Strategy | Type |
|--------|----------|------|
| crypto-trend-daily | 50/200 EMA trend | Crypto spot |
| crypto-intraday-15m | Adaptive range bounce | Crypto spot |
| crypto-swing-daily | BB/RSI dip buyer | Crypto spot |
| crypto-breakout-4h | Donchian breakout | Crypto spot |
| crypto-trendmomo-4h | SMA momentum | Crypto spot |
| perps-rsi-meanrev | RSI mean reversion | Perps |
| perps-donchian-breakout | 4h breakout | Perps |
| perps-regime-switch | Long/short trend | Perps |
| perps-funding-carry | Funding rate carry | Perps |
| scanner-triangular-arb | Triangular arb | Scanner |
| event-listing-sniper | New listing buyer | Scanner |
| equities-regime-ibkr | SPY/QQQ regime | Stocks (IBKR) |
| equities-momentum-alpaca | Momentum rank | Stocks (Alpaca) |

## Dashboard
- **File:** `pnl_dashboard.py` — Postgres-backed, auto-refreshes every 30s
- **DB:** Each bot publishes to `bot_pnl` table via `bot_pnl_store.py`
- **Auth:** DASH_USER / DASH_PASS env vars on Railway

## Key Files
- `pnl_dashboard.py` — main dashboard server
- `bot_pnl_store.py` — shared Postgres publisher (all bots import this)
- `hyperliquid_momo_bot.py` — Hyperliquid momentum bot
- `funding_carry_bot.py` — funding carry strategy
- `user_data/` — Freqtrade user data directory

## How Bots Publish to Dashboard
Each bot calls `bot_pnl_store.publish(...)` with:
```python
{
  "bot": "freqtrade-mum",          # bot ID — must match CURRENT_BOTS in dashboard
  "status": "running",
  "equity": 1023.50,
  "pnl_abs": 23.50,
  "pnl_pct": 0.0235,
  "closed_trades": 12,
  "open_trades": 2,
  "wins": 8,
  "losses": 4,
  "pnl_daily": 5.20,               # optional — today's P&L
  "pnl_weekly": 18.40,             # optional — 7d P&L
  "pnl_monthly": 23.50,            # optional — 30d P&L
  "max_drawdown": -0.045,          # optional — max drawdown %
  "best_trade": 12.30,             # optional — best single trade $
  "worst_trade": -8.10,            # optional — worst single trade $
}
```

## Freqtrade Bot Configs (new bots)
All new bots:
- `dry_run: true`
- `dry_run_wallet: 1000`
- API server enabled on ports 8080–8083
- Logs to `logs/freqtrade.log`
- SQLite DB at `logs/tradesv3.sqlite`

## Claude Code Instructions
- Ask Claude to backtest any bot: `freqtrade backtesting --config <bot>/config.json --strategy <Name>`
- Ask Claude to tune via Hyperopt: `freqtrade hyperopt --config <bot>/config.json --strategy <Name> --hyperopt-loss SharpeHyperOptLoss`
- Ask Claude to check logs: `tail -f <bot>/logs/freqtrade.log`
- Ask Claude to deploy: push to main branch → Railway auto-deploys

## Railway Setup
- Each bot is a separate Railway service
- All services share the same Postgres plugin via DATABASE_URL
- Deploy trigger: push to main branch
- Dashboard service: `pnl-dashboard`

## Rules
- $1,000 starting balance per bot, NO top-ups
- Paper trading only until 30-day win rate > 55% AND max drawdown < 15%
- Never modify bot logic without backtesting first
