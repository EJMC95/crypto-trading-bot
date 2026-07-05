# Changelog

Shared log of every change that affects a running bot, the dashboard, or deploy
behaviour. **Multiple Claude sessions work this repo in parallel** — this file is
how they stay in sync. If your diff touches bot code (`*.py`, `*.sh`, a strategy,
a config) you MUST add a dated entry here in the same commit (a CI check enforces
it). Newest first. Keep entries one line; link the commit if useful.

## 2026-07-05
- day trader (`DayTraderV5Gated`): loosen risk-off band gate 2.2% → 2.0% (more relief-rally pairs, still above fee floor).
- day trader: add third entry mode `bounce_pullback` — trades the relief rally in a risk-off regime when the pair's own 1h EMA50 is above price AND rising; half stake, fast exits. Fixes the "idle in a bounce" gap.
- perps `rsi-meanrev`: global position cap (`MAX_OPEN_POSITIONS=6`, `MAX_NEW_PER_LOOP=2`) gated on a live open count — was holding 14 longs (70% of book) in one correlated dip with no cap.
- ops: schedule the learning brain (`bot_learn.py`) every 2h in the freqtrade supervisor (`run_all.sh`) — it was never scheduled, so it never accumulated the 3 runs needed to promote a lesson to actionable.
- ops: add `CHANGELOG.md` + CI enforcement + `CLAUDE.md` session-coordination rules (this change).

## 2026-07-04
- Dashboard v2: health checks, per-mode (enter_tag) W/L/P&L rows, brain card, BTC regime chip, sparklines, pulse strip.
- sniper: throttle — stake 100→50, max-open 25→10, SL 50%→35%, max-hold 48h→24h, spread gate 500→250bps, depth 3×→5×, vol floor 25k, anti-chase 150%→100%.
- sniper intel (`listing_intel.py`): exchange announcement feeds + CoinGecko footprint, half-stake on junk listings.
- pulse: extend panic sizing to V6/V7 bounces; pulse history records funding APRs.
- brain v1.1: era awareness — hypotheses only from current-strategy-era trades.

## 2026-07-03
- Adaptive dual-mode strategies (V5/V6/V7/V8): BTC-4h 50/200 regime switch (risk-on pullbacks / risk-off sweep-reclaim bounces).
- Durable equity across redeploys: `/freqtrade/persist` volume + Postgres state for perps/sniper; freqtrade auto-deploy unfrozen (persistence makes redeploys safe).
- `perps-funding-carry` bot added (dry-run Hyperliquid funding-rate harvester).
- `market_pulse.py` news/social/funding feed → Postgres; `bot_learn.py` brain added.
- `perps-regime-switch` moved to Donchian-style entries; auto-deploys on its own file changes.

## Before 2026-07-03
See git history. Key milestones: fee-bleed + close fixes for perps (07-01), the
persistent-volume saga (07-01), day-trader fee-gate/trend-gate (07-01/02),
unified pnl-dashboard + Postgres publishing (06-19), multi-bot freqtrade
supervisor (06-18).
