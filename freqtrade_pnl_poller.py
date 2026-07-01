#!/usr/bin/env python3
"""
freqtrade_pnl_poller.py — bridge the 5 freqtrade bots into the shared Postgres
P&L table so they appear on the unified pnl_dashboard alongside the custom bots.

Runs INSIDE the freqtrade container (started by run_all.sh). Every loop it polls
each bot's local REST API (127.0.0.1:<port>) for profit + open trades and calls
bot_pnl_store.publish(...). Fully guarded: if a bot is down or Postgres is
unreachable it logs and keeps going — never crashes the container.

Needs DATABASE_URL set on the freqtrade-bots Railway service (reference the
Postgres service). Without it, bot_pnl_store just no-ops.
"""
import base64
import json
import os
import time
import urllib.request

import bot_pnl_store as store

# Must match the api_server creds in every config_*.json
BOT_USER = "freqtrader"
BOT_PASS = "freqbot2026"

# (publish-name, REST port) — names match pnl_dashboard's EXPECTED list.
# Default = the 5 spot bots in the freqtrade-bots container. A dedicated
# single-bot container (e.g. perps-regime-switch) overrides this via the
# FT_POLLER_BOTS env var — a JSON list of [name, port] pairs — so the same
# poller code drives any freqtrade service without editing this list.
_DEFAULT_BOTS = [
    ("crypto-trend-daily", 8085),
    ("crypto-intraday-15m", 8084),
    ("crypto-swing-daily", 8086),
    ("crypto-breakout-4h", 8087),
    ("crypto-trendmomo-4h", 8088),
]
_env_bots = os.environ.get("FT_POLLER_BOTS", "").strip()
if _env_bots:
    BOTS = [(str(n), int(p)) for n, p in json.loads(_env_bots)]
else:
    BOTS = _DEFAULT_BOTS

POLL_SECONDS = 30


def _req(url, headers=None, method="GET", timeout=6):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _token(port):
    auth = base64.b64encode(f"{BOT_USER}:{BOT_PASS}".encode()).decode()
    return _req(f"http://127.0.0.1:{port}/api/v1/token/login",
                headers={"Authorization": f"Basic {auth}"}, method="POST")["access_token"]


def poll_one(name, port):
    try:
        h = {"Authorization": f"Bearer {_token(port)}"}
        profit = _req(f"http://127.0.0.1:{port}/api/v1/profit", headers=h)
        try:
            status = _req(f"http://127.0.0.1:{port}/api/v1/status", headers=h) or []
            open_n = len(status) if isinstance(status, list) else 0
        except Exception:
            open_n = profit.get("open_trade_count")
        pct = profit.get("profit_closed_percent")
        # Read current wallet value so the dashboard shows real (paper) equity.
        # Freqtrade's /balance returns "total" in the stake currency; guard it
        # so a missing/!=200 endpoint never breaks the publish.
        try:
            bal = _req(f"http://127.0.0.1:{port}/api/v1/balance", headers=h)
            equity = bal.get("total")
        except Exception:
            equity = None
        store.publish(
            name,
            status="online",
            equity=equity,
            pnl_abs=profit.get("profit_closed_coin"),
            pnl_pct=(pct / 100.0) if isinstance(pct, (int, float)) else None,
            open_trades=open_n,
            closed_trades=profit.get("closed_trade_count"),
            wins=profit.get("winning_trades"),
            losses=profit.get("losing_trades"),
            extra={"src": "freqtrade", "port": port},
        )
        # Persist per-trade history (durable in Postgres so it survives redeploys;
        # the trainer's analyzer reads this for the win/loss deep dive).
        try:
            tr = _req(f"http://127.0.0.1:{port}/api/v1/trades?limit=500", headers=h)
            trades = tr.get("trades", tr) if isinstance(tr, dict) else tr
            if isinstance(trades, list):
                store.publish_trades(name, trades)
        except Exception:
            pass
        return True
    except Exception as e:
        # Bot not up yet / API not ready — record as starting, keep going.
        store.publish(name, status="starting", extra={"err": type(e).__name__})
        return False


def main():
    print(f"[freqtrade-poller] polling {len(BOTS)} bots every {POLL_SECONDS}s "
          f"-> Postgres", flush=True)
    while True:
        ok = 0
        for name, port in BOTS:
            if poll_one(name, port):
                ok += 1
        print(f"[freqtrade-poller] published {ok}/{len(BOTS)} bots", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
