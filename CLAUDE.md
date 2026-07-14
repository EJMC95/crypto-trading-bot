# CLAUDE.md — crypto-trading-bot Fleet

## What This Repo Is
Eamon's crypto trading bot fleet — **LIGHTER-FIRST since 2026-07-14** (user
decision: "all services must run off lighter"). Books are $1,000 paper/shadow
each, no top-ups, except the real-money Lighter live rows. Dashboard:
https://pnl-dashboard-production-858c.up.railway.app/

## Fleet Overview (post 14-Jul Kraken retirement — ~21 live rows)

### The trading fleet (Lighter)
| Row | Name | What it is |
|-----|------|------------|
| freqtrade-{mum,dad,avo-maria,georgia}-lshadow | 👩👨🙏🔮 family | TrendMomo/MomoBreakout/SwingDip/DayTraderV5 on Lighter (gate0 `lighter_family_bot.py`, service `family-lighter-shadow`) |
| crypto-{intraday-15m,swing-daily,breakout-4h}-lshadow | spot ports | same service, 29-pair whitelist |
| crypto-trend-daily-lighter / -lshadow | 🌊 Tide Rider | **LIVE real money** + shadow (tide-rider service) |
| perps-funding-lighter-lighter / -lshadow | 💸 Funding Farmer | **LIVE** funding harvester + shadow |
| perps-funding-carry (+ -lshadow) | 🌾 Yield Harvester | HL-data paper origin + Lighter shadow |
| perps-funding-spread-lshadow | ⚖️ Counterweight | funding L/S book |
| lighter-perp-sniper-lshadow | 🎯 Perp Sniper | new-listing sniper |
| lighter-dislocation-lshadow | 🧲 Snap Back | dislocation fader |
| lighter-ticket-taker-lshadow | 🎫 Ticket Taker | **trades Lighter Scout's high-conviction tickets** (breakout/dip/momentum long + divergence long/short); stress veto pauses entries at venue |prem| med ≥15bps; closes tagged `<side>-<lens>_<exit>` so the brain grades each lens |
| equities-regime-lshadow / equities-momentum-lshadow | 📊 Index Rider / 🏆 Stock Leaders | stock-perp ports (IBKR/Alpaca originals RETIRED 14-Jul) |
| event-listing-sniper | 🎯 Launch Sniper | CEX spot listings (legacy, still running) |
| scanner-cross-exchange-arb | 🔀 Gap Scout | CEX dislocation scanner + Lighter premium publisher |

### Intelligence layer (main freqtrade-bots container, run_all.sh loops)
- `lighter_market_scout.py` 🛰️ — ALL ~215 Lighter books: premium stress,
  liquid funding extremes, cross-venue funding divergence, vol/OI moves,
  listings, **per-strategy tickets** → bot_state `lighter-market`
- `bot_learn.py` (brain) — L4 stake multipliers (strategies consume via
  `fleet_bus.py`), per-bucket DIAGNOSIS (exit/entry/fee/regime/venue),
  venue A/B; → `learning-brain`, `brain-stake-mults`, `brain-diagnosis`
- `fleet_risk.py` — traffic light (live > lshadow > paper via
  `authoritative_row`, 30-min staleness filter) + signal bus; long-budget
  veto ENFORCED in strategies (`FLEET_RISK_MODE=advisory` = kill switch)
- `regime_oracle.py`, `market_pulse.py` (history appends hourly),
  `cleanup_legacy_bots.py` (boot prune of retired rows)

### RETIRED (rows hidden + pruned; ledgers kept)
Kraken paper 8 (spot 4 + family 4, 14-Jul user cut — Kraken/laptop
processes are operator-stopped), equities-momentum-alpaca +
equities-regime-ibkr (14-Jul), Trail Blazer, Bounce Catcher, Two-Way Tide,
Loop Scout, trendmomo-4h (12/13-Jul). See RETIRED_ROWS in pnl_dashboard.py.

### Read-only endpoints (no auth)
`/pnl.json` `/trades.json` (`?source=paper` for the paper_trades ledger)
`/bus.json` (risk light + signal bus + brain keys + lighter-market,
`?hours=` history) `/pulse.json` `/disloc.json` `/watchdog.json`

## Dashboard
- **File:** `pnl_dashboard.py` — Postgres-backed, auto-refreshes every 30s
- **DB:** Each bot publishes to `bot_pnl` table via `bot_pnl_store.py`
- **Auth:** DASH_USER / DASH_PASS env vars on Railway

## Key Files
- `pnl_dashboard.py` — main dashboard server (+ fleet_watchdog_svc.py)
- `bot_pnl_store.py` — shared Postgres publisher (all bots import this)
- `lighter_market_scout.py` / `lighter_ticket_taker.py` — scout + its trader
- `bot_learn.py` + `fleet_bus.py` — brain and the strategies' read client
- `fleet_risk.py` / `regime_oracle.py` / `market_pulse.py` — shared organs
- `cross_exchange_arb.py` — Gap Scout (CEX dislocation + Lighter premium)
- `funding_carry_bot.py` — Yield Harvester (HL-data paper origin)
- `user_data/` — Freqtrade strategies/configs (dormant post-Kraken; the
  gate0 family bot re-expresses them on Lighter)
- gate0 branch (`claude/lighter-gate0`) — the Lighter runtime (venues/,
  ShadowBroker, lighter_family_bot.py); its services deploy from there

## Cross-Bot Intelligence (bot_state keys — since 2026-07-14 CONSUMED, not just published)
- `brain-stake-mults` — bot_learn's L4 reduce-only per-(bot, enter_tag) stake
  multipliers (floors: n≥30 era trades / 3 consecutive runs; never >1.0).
  Strategies apply them in `custom_stake_amount` via `fleet_bus.py`.
- `fleet-risk` — L2 traffic light, mode **enforce**: strategies veto NEW long
  entries at long-budget (20). Kill switch: `FLEET_RISK_MODE=advisory`.
- `signal-bus`, `regime-oracle`, `market-pulse`, `listing-intel` — published
  context (funding APRs, dislocation, per-major regime, news mood, sniper
  intel classes). Only market-pulse.panic + the two keys above are consumed.
- Every payload carries `updated`+`ttl_sec`; consumers go NEUTRAL on stale
  data (`fleet_bus.is_fresh`). Backtests are inert (no DATABASE_URL).
- Bot identity for multiplier lookup = `bot_name` in each freqtrade config
  (= dashboard bot ID — keep them matching).

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
