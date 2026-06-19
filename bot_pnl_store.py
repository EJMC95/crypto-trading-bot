#!/usr/bin/env python3
"""
bot_pnl_store.py — tiny shared P&L publisher backed by Railway Postgres.

Every bot calls publish(...) once per loop with whatever it knows about its own
state (equity, paper P&L, trade counts). The row is upserted into a single
`bot_pnl` table keyed by bot name. The live dashboard (pnl_dashboard.py) reads
that table and renders all bots on one page.

DESIGN GOALS
  * Zero impact on the trading loop. If DATABASE_URL is unset, psycopg2 is
    missing, or Postgres is unreachable, publish() quietly no-ops and returns
    False. It NEVER raises into the caller.
  * One dependency (psycopg2-binary). Connection is cached and lazily
    re-established if it drops.

USAGE
    import bot_pnl_store as store
    store.publish("triangular-arb", status="online",
                  pnl_abs=virtual_balance, extra={"cycles": n})

Set DATABASE_URL on each Railway service to a reference to the Postgres
service's connection string (Railway: Variables -> add reference -> Postgres
DATABASE_URL). Locally, leave it unset and this module is a no-op.
"""
import os
import json
import time

_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_conn = None
_warned = False
_table_ready = False


def _warn_once(msg):
    global _warned
    if not _warned:
        print(f"[bot_pnl_store] disabled: {msg}", flush=True)
        _warned = True


def _get_conn():
    """Return a live connection, or None if unavailable (no raise)."""
    global _conn
    if not _DATABASE_URL:
        _warn_once("DATABASE_URL not set")
        return None
    try:
        import psycopg2  # noqa: imported lazily so missing dep is a no-op
    except Exception as e:
        _warn_once(f"psycopg2 not importable ({e})")
        return None
    if _conn is not None:
        try:
            # cheap liveness check
            with _conn.cursor() as cur:
                cur.execute("SELECT 1")
            return _conn
        except Exception:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
    try:
        _conn = psycopg2.connect(_DATABASE_URL, connect_timeout=5)
        _conn.autocommit = True
        return _conn
    except Exception as e:
        _warn_once(f"connect failed ({e})")
        return None


def _ensure_table(conn):
    global _table_ready
    if _table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_pnl (
                bot            TEXT PRIMARY KEY,
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                status         TEXT,
                equity         DOUBLE PRECISION,
                pnl_abs        DOUBLE PRECISION,
                pnl_pct        DOUBLE PRECISION,
                open_trades    INTEGER,
                closed_trades  INTEGER,
                wins           INTEGER,
                losses         INTEGER,
                extra          JSONB
            )
            """
        )
    _table_ready = True


def publish(bot, status="online", equity=None, pnl_abs=None, pnl_pct=None,
            open_trades=None, closed_trades=None, wins=None, losses=None,
            extra=None):
    """Upsert this bot's current snapshot. Returns True on success, else False.

    Safe to call every loop. Never raises.
    """
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_pnl (bot, updated_at, status, equity, pnl_abs,
                    pnl_pct, open_trades, closed_trades, wins, losses, extra)
                VALUES (%s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bot) DO UPDATE SET
                    updated_at    = now(),
                    status        = EXCLUDED.status,
                    equity        = EXCLUDED.equity,
                    pnl_abs       = EXCLUDED.pnl_abs,
                    pnl_pct       = EXCLUDED.pnl_pct,
                    open_trades   = EXCLUDED.open_trades,
                    closed_trades = EXCLUDED.closed_trades,
                    wins          = EXCLUDED.wins,
                    losses        = EXCLUDED.losses,
                    extra         = EXCLUDED.extra
                """,
                (bot, status, equity, pnl_abs, pnl_pct, open_trades,
                 closed_trades, wins, losses,
                 json.dumps(extra) if extra is not None else None),
            )
        return True
    except Exception as e:
        _warn_once(f"write failed ({e})")
        # drop the connection so the next call reconnects
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


if __name__ == "__main__":
    # quick self-test: writes a dummy row if DATABASE_URL is set, else no-ops.
    ok = publish("selftest", status="online", pnl_abs=1.23, pnl_pct=0.0123,
                 extra={"note": "self-test"})
    print("publish ->", ok, "(DATABASE_URL set)" if _DATABASE_URL else "(no DATABASE_URL; no-op)")
    time.sleep(0.1)
