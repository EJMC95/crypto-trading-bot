# CLAUDE.md — working agreement for this repo

Multiple Claude sessions develop this crypto-bot fleet **in parallel**. Read this
before making changes so sessions don't clobber or duplicate each other's work.

> **START HERE.** This repo is the durable anchor for the crypto-bot workspace.
> On any new session, read in this order: **`SESSION_LOG.md`** (narrative state +
> what to watch for) → **`CHANGELOG.md`** (line-by-line recent changes) → this
> file. The live dashboard + Railway services are the running truth; the chat
> session is ephemeral, but the workspace state lives here in git and in the
> always-on cloud. Append to `SESSION_LOG.md` at the end of each major session.

## The #1 rule: log every bot-affecting change
If your diff touches a running bot (`*.py`, `*.sh`, a strategy in
`user_data/strategies/`, a `user_data/config_*.json`, or a workflow), add a dated
one-line entry to `CHANGELOG.md` **in the same commit**. A CI check
(`.github/workflows/changelog-check.yml`) fails the build if you don't. This is
the single source of truth for "what did the other session just change" — it is
why we stopped tuning code another session had already replaced.

## Ground truth
- `main` is the only source of truth. All sessions push here (directly or via a
  quick fast-forward from a feature branch). There is no long-lived divergence.
- Before editing a strategy/bot, `git log --oneline -20 <file>` and skim the file
  header — this repo documents prior failed tweaks inline (e.g. "relaxing RSI 6×'d
  trades and made losses WORSE"). Don't re-try a documented failure.

## Deploy model (Railway)
- `freqtrade-bots` service: 5 freqtrade dry-run bots via `run_all.sh`. Auto-deploys
  on push to `main` when `user_data/**`, `Dockerfile.freqtrade`, `run_all.sh`, or
  the shared pollers change. Paper DBs persist on the `/freqtrade/persist` volume —
  **redeploys are safe** (no reset).
- `perps-*`, `pnl-dashboard`, scanners, sniper: separate Railway services, native
  auto-deploy on push to `main`. Perps/sniper persist state to Postgres.
- Nothing here is real money — all bots are dry-run/paper. Keep it that way unless
  the human explicitly flips a bot to live.

## Suggested ownership split (avoid collisions)
To reduce two sessions editing the same file, prefer these lanes; if you must
cross a lane, say so in the CHANGELOG entry.
- **Strategy/trading logic** — `user_data/strategies/*`, `hyperliquid_*_bot.py`,
  `funding_carry_bot.py`, `listing_sniper.py`, configs.
- **Dashboard & visualisation** — `pnl_dashboard.py`, `dashboard_*.py`.
- **Learning/analytics** — `bot_learn.py`, `trade_analyzer.py`, `market_pulse.py`,
  `listing_intel.py`, `freqtrade_retrain.py`.
- **Ops/infra** — `.github/workflows/*`, `run_all.sh`, `Dockerfile*`,
  `bot_pnl_store.py` (shared — coordinate; changing its schema affects everyone).

## Live dashboard
`https://pnl-dashboard-production-858c.up.railway.app` — `/pnl.json` (fleet
snapshot, no auth), `/trades.json?bot=&limit=` (per-trade, no auth). Use these to
verify behaviour instead of guessing.
