#!/usr/bin/env python3
"""
freqtrade_pnl_poller.py — bridge the freqtrade bots into the shared Postgres
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
import datetime as dt
import urllib.request

import bot_pnl_store as store

# Must match the api_server creds in every config_*.json
BOT_USER = "freqtrader"
BOT_PASS = "freqbot2026"

# (publish-name, REST port) — names match pnl_dashboard's EXPECTED list.
# Default = original 5 spot bots + new July 2026 fleet.
# Override via FT_POLLER_BOTS env var — a JSON list of [name, port] pairs.
_DEFAULT_BOTS = [
    # Original fleet
    ("crypto-trend-daily",    8085),
    ("crypto-intraday-15m",   8084),
    ("crypto-swing-daily",    8086),
    ("crypto-breakout-4h",    8087),
    ("crypto-trendmomo-4h",   8088),
    # New fleet — July 2026 ($1000 paper, no top-ups)
    ("freqtrade-mum",         8089),
    ("freqtrade-dad",         8090),
    ("freqtrade-avo-maria",   8091),
    ("freqtrade-georgia",     8092),
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


def _compute_pnl_windows(trades):
    """
    From a list of closed trades, compute:
      - pnl_daily   : P&L on trades closed today (UTC)
      - pnl_weekly  : P&L on trades closed in last 7 days
      - pnl_monthly : P&L on trades closed in last 30 days
      - max_drawdown: max peak-to-trough drawdown on cumulative P&L curve
      - best_trade  : best single closed trade profit_abs
      - worst_trade : worst single closed trade profit_abs
    Returns a dict with those keys (None if not computable).
    """
    now = dt.datetime.utcnow()
    day_ago   = now - dt.timedelta(days=1)
    week_ago  = now - dt.timedelta(days=7)
    month_ago = now - dt.timedelta(days=30)

    pnl_daily = pnl_weekly = pnl_monthly = 0.0
    profits = []

    for t in trades:
        # Only closed trades have close_timestamp
        close_ts = t.get("close_timestamp")
        profit   = t.get("profit_abs") or t.get("close_profit_abs") or 0
        if close_ts is None:
            continue
        try:
            # close_timestamp is epoch ms in freqtrade
            close_dt = dt.datetime.utcfromtimestamp(close_ts / 1000)
        except Exception:
            continue
        profits.append((close_dt, float(profit)))
        if close_dt >= day_ago:
            pnl_daily   += float(profit)
        if close_dt >= week_ago:
            pnl_weekly  += float(profit)
        if close_dt >= month_ago:
            pnl_monthly += float(profit)

    if not profits:
        return {
            "pnl_daily": None, "pnl_weekly": None, "pnl_monthly": None,
            "max_drawdown": None, "best_trade": None, "worst_trade": None,
        }

    profit_vals = [p for _, p in sorted(profits)]
    best_trade  = max(profit_vals)
    worst_trade = min(profit_vals)

    # Max drawdown on cumulative equity curve
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in profit_vals:
        cum  += p
        if cum > peak:
            peak = cum
        if peak > 0:
            dd = (cum - peak) / peak
            if dd < max_dd:
                max_dd = dd

    return {
        "pnl_daily":    round(pnl_daily,   4),
        "pnl_weekly":   round(pnl_weekly,  4),
        "pnl_monthly":  round(pnl_monthly, 4),
        "max_drawdown": round(max_dd,      4),
        "best_trade":   round(best_trade,  4),
        "worst_trade":  round(worst_trade, 4),
    }


def poll_one(name, port):
    try:
        h = {"Authorization": f"Bearer {_token(port)}"}
        profit = _req(f"http://127.0.0.1:{port}/api/v1/profit", headers=h)
        try:
            status = _req(f"http://127.0.0.1:{port}/api/v1/status", headers=h) or []
            open_n = len(status) if isinstance(status, list) else 0
        except Exception:
            status, open_n = [], profit.get("open_trade_count")

        # Live open-position detail for dashboard card
        open_pos = []
        try:
            for t in (status if isinstance(status, list) else [])[:6]:
                pr  = t.get("profit_ratio")
                ots = t.get("open_timestamp")
                open_pos.append({
                    "pair": t.get("pair"),
                    "pnl":  round(pr * 100, 2) if isinstance(pr, (int, float)) else None,
                    "tag":  t.get("enter_tag"),
                    "h":    round((time.time() * 1000 - ots) / 3.6e6, 1) if ots else None,
                })
        except Exception:
            open_pos = []

        pct = profit.get("profit_closed_percent")

        # Current wallet equity
        try:
            bal    = _req(f"http://127.0.0.1:{port}/api/v1/balance", headers=h)
            equity = bal.get("total")
        except Exception:
            equity = None

        # Fetch closed trades for windowed P&L, drawdown, best/worst
        windows = {"pnl_daily": None, "pnl_weekly": None, "pnl_monthly": None,
                   "max_drawdown": None, "best_trade": None, "worst_trade": None}
        try:
            tr     = _req(f"http://127.0.0.1:{port}/api/v1/trades?limit=500", headers=h)
            trades = tr.get("trades", tr) if isinstance(tr, dict) else tr
            if isinstance(trades, list) and trades:
                windows = _compute_pnl_windows(trades)
                # Also persist trade history to Postgres
                store.publish_trades(name, trades)
        except Exception:
            pass

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
            # Windowed P&L + risk metrics (all bots, not just new ones)
            pnl_daily=windows["pnl_daily"],
            pnl_weekly=windows["pnl_weekly"],
            pnl_monthly=windows["pnl_monthly"],
            max_drawdown=windows["max_drawdown"],
            best_trade=windows["best_trade"],
            worst_trade=windows["worst_trade"],
            extra={"src": "freqtrade", "port": port,
                   **({"open_pos": open_pos} if open_pos else {})},
        )
        return True
    except Exception as e:
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
