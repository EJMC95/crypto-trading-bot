# CLAUDE.md — crypto-trading-bot Fleet

## What This Repo Is
Eamon's full crypto trading bot fleet. Multiple strategies running on paper (dry run) with $1,000 starting balance each, no top-ups. Dashboard lives at https://pnl-dashboard-production-858c.up.railway.app/

## Fleet Overview

### ⚡ 14-15 Jul 2026 — LIGHTER-FIRST PIVOT (user instruction: "retire the
### kraken bots, let's just focus on lighter")
The whole Kraken/laptop paper arm is RETIRED; the Lighter books are the
fleet. The pivot was first shipped 14 Jul only inside the freqtrade-bots
image (uncommitted); recovered via railway ssh and landed in git 15 Jul
(branch recovery/freqtrade-bots-image-20260715 = verbatim image snapshot).
Retired: the 4 Kraken spot originals, the 4 family Kraken carriers (Railway
services stopped 15 Jul), crypto-trendmomo-4h, perps-rsi-meanrev,
perps-donchian-breakout, perps-regime-switch, scanner-triangular-arb,
equities-momentum-alpaca (cron torn down 15 Jul) and equities-regime-ibkr
(publisher runs on an unidentified host — row dashboard-retired; stop it
when found). History stays in the ledgers; rows in dashboard RETIRED_ROWS.

### Active fleet (paper/shadow $1,000 books unless marked LIVE)
| Row | What it is | Where it runs |
|-----|------------|---------------|
| freqtrade-{mum,dad,avo-maria,georgia}-lshadow | Family four on Lighter candles (TrendMomo 1d / MomoBreakout 4h / SwingDip 4h / DayTraderV5Gated 15m) | family-lighter-shadow (gate0) |
| crypto-{intraday-15m,swing-daily,breakout-4h}-lshadow | Spot-original strategies on Lighter | family-lighter-shadow (gate0) |
| crypto-trend-daily-lshadow / **crypto-trend-daily-lighter (LIVE)** | Tide Rider 50/200 EMA trend, 1x long perp | tide-rider services (gate0) |
| **perps-funding-lighter-lighter (LIVE)** / -lshadow | Funding Farmer (funding-carry position scanner) | trail-blazer-live service + shadow |
| perps-funding-carry | HL paper funding carry (original) | funding-carry |
| perps-funding-spread-lshadow | Counterweight x-sect funding L/S | counterweight-shadow |
| lighter-dislocation-lshadow | Snap Back dislocation harvester (census-gated) | snap-back-shadow |
| lighter-perp-sniper-lshadow | Perp listing sniper | perp-sniper-shadow |
| lighter-ticket-taker-lshadow | 🎫 Ticket Taker — trades the Lighter Scout's tickets, tags closes per lens so the brain grades the scanner (UNVALIDATED by design) | freqtrade-bots |
| equities-momentum-lshadow | Stock Leaders — Alpaca momentum ported to Lighter STOCK PERPS + gold/silver/oil/BTC/ETH | momoshadow service |
| equities-regime-lshadow | Index Rider — SPY/QQQ SMA200 regime on Lighter stock perps | equities-regime-shadow |
| event-listing-sniper | New listing buyer | listing-sniper |
| scanner-cross-exchange-arb | Cross-exchange arb scanner (optimistic fills, separate subtotal) | cross-exchange-arb |

### Fleet organs (freqtrade-bots container, no bots of its own except 🎫)
run_all.sh runs: market_pulse (mood/F&G), bot_learn brain (L4 reduce-only
stake-mults + venue A/B + loss diagnosis), regime_oracle (L1), fleet_risk
(L2 traffic light, ENFORCE via fleet_bus long-budget veto), lighter_market_scout
(all-book venue map -> tickets), lighter_ticket_taker, dashboard copy, and a
boot-time cleanup_legacy_bots --apply that prunes retired rows (idempotent;
family rows stopped re-upserting once their services were stopped).
fleet_bus.py is the strategies' fail-safe-open read side (L2 veto + L4 mults).

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
