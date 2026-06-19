# Live P&L Dashboard — deploy guide

A new unified dashboard that shows **all bots on one live page**, backed by the
Postgres service already in your Railway project.

## How it works

1. Each bot calls `bot_pnl_store.publish(...)` once per loop and upserts its
   snapshot (equity / P&L / trade counts) into a shared `bot_pnl` table.
2. A new **dashboard service** (`pnl_dashboard.py`) reads that table and serves a
   live, auto-refreshing page on `$PORT`.

Everything is guarded: if `DATABASE_URL` is missing or Postgres is down, the bots
keep trading (publish just no-ops) and the dashboard shows a clear banner instead
of crashing.

## What changed in the repo

- `bot_pnl_store.py` — new shared publisher (Postgres, safe no-op without a DB).
- `pnl_dashboard.py` — new dashboard service.
- `triangular_arb.py`, `hyperliquid_perps_bot.py`, `hyperliquid_momo_bot.py`,
  `listing_sniper.py` — each now publishes a snapshot per loop.
- `requirements.txt` — added `psycopg2-binary`.

## Deploy steps (Railway)

1. **Push the code** (Railway auto-redeploys the existing bot services):
   ```bash
   cd "~/Claude/Projects/Crypto Trading Bot"
   git add -A && git commit -m "Add shared Postgres P&L store + live dashboard service"
   git push origin main
   ```

2. **Give every bot service access to Postgres.** For each of `perps-bot`,
   `momo-bot`, `triangular-arb`, `listing-sniper` (and the freqtrade service if/when
   deployed): Variables → New Variable → **Add Reference** → pick the Postgres
   service's `DATABASE_URL`. (This is why nothing published before — the bots had no
   `DATABASE_URL`.)

3. **Create the dashboard service:**
   - New → Deploy from the same repo.
   - **Start Command:** `python pnl_dashboard.py`
   - **Variables:** add a reference to Postgres `DATABASE_URL`; optionally set
     `DASH_USER` / `DASH_PASS` (defaults: `eamon` / `freqbot2026`).
   - **Networking:** Generate Domain so you can open it in a browser. It serves on
     `$PORT` automatically.

4. Open the generated URL, log in, and you should see every bot tile populate
   within one loop interval (arb ~8s, perps ~60s, momo ~5m, sniper ~30s). Tiles
   older than 180s are flagged **STALE** so a dead bot is obvious.

## Notes

- The dashboard lists expected bots even before they publish, so an empty tile =
  that bot hasn't checked in yet (usually missing `DATABASE_URL`).
- The freqtrade bots (v4–v8) don't publish yet — they aren't deployed as a Railway
  service right now. When they are, the cleanest path is a small poller that reads
  their REST API and calls `store.publish(...)`; the dashboard already reserves
  tiles for them.
- Verified locally end-to-end against an in-memory Postgres stand-in (publish,
  upsert, and render all pass); the no-DB no-op path is also tested.
