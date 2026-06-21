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


_trades_table_ready = False


def _ensure_trades_table(conn):
    """Per-trade history table. Keyed by (bot, open_ts) so it SURVIVES container
    redeploys — freqtrade's integer trade_id resets to 1 each time the ephemeral
    sqlite is recreated, but each trade's open timestamp is stable and unique."""
    global _trades_table_ready
    if _trades_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_trades (
                bot           TEXT NOT NULL,
                open_ts       TIMESTAMPTZ NOT NULL,
                pair          TEXT,
                is_open       BOOLEAN,
                profit_ratio  DOUBLE PRECISION,
                profit_abs    DOUBLE PRECISION,
                close_ts      TIMESTAMPTZ,
                open_rate     DOUBLE PRECISION,
                close_rate    DOUBLE PRECISION,
                amount        DOUBLE PRECISION,
                stake_amount  DOUBLE PRECISION,
                duration_min  DOUBLE PRECISION,
                enter_tag     TEXT,
                exit_reason   TEXT,
                leverage      DOUBLE PRECISION,
                seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (bot, open_ts)
            )
            """
        )
    _trades_table_ready = True


def publish_trades(bot, trades):
    """Idempotently upsert a list of freqtrade trade dicts (from /api/v1/trades).
    Safe to call every loop; only changed/closed rows actually move. Never raises."""
    conn = _get_conn()
    if conn is None or not trades:
        return 0
    try:
        _ensure_trades_table(conn)
        n = 0
        with conn.cursor() as cur:
            for t in trades:
                open_ts = t.get("open_date") or t.get("open_timestamp")
                if open_ts is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO bot_trades (bot, open_ts, pair, is_open,
                        profit_ratio, profit_abs, close_ts, open_rate, close_rate,
                        amount, stake_amount, duration_min, enter_tag, exit_reason,
                        leverage, seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (bot, open_ts) DO UPDATE SET
                        is_open=EXCLUDED.is_open, profit_ratio=EXCLUDED.profit_ratio,
                        profit_abs=EXCLUDED.profit_abs, close_ts=EXCLUDED.close_ts,
                        close_rate=EXCLUDED.close_rate, duration_min=EXCLUDED.duration_min,
                        exit_reason=EXCLUDED.exit_reason, seen_at=now()
                    """,
                    (bot, _ts(open_ts), t.get("pair"), t.get("is_open"),
                     t.get("profit_ratio"), t.get("profit_abs"),
                     _ts(t.get("close_date") or t.get("close_timestamp")),
                     t.get("open_rate"), t.get("close_rate"), t.get("amount"),
                     t.get("stake_amount"),
                     (t.get("trade_duration") if t.get("trade_duration") is not None
                      else _dur_min(t)),
                     t.get("enter_tag"), t.get("exit_reason"), t.get("leverage")),
                )
                n += 1
        return n
    except Exception as e:  # noqa: BLE001
        _warn_once(f"trade write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return 0


def _ts(v):
    """Accept ISO string or epoch ms/s -> something psycopg2 stores as timestamptz."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # freqtrade timestamps are epoch milliseconds
        from datetime import datetime, timezone
        sec = v / 1000.0 if v > 1e12 else v
        return datetime.fromtimestamp(sec, tz=timezone.utc)
    return v  # ISO8601 string; Postgres parses it


def _dur_min(t):
    o = t.get("open_timestamp"); c = t.get("close_timestamp")
    if isinstance(o, (int, float)) and isinstance(c, (int, float)):
        return (c - o) / 60000.0
    return None


def fetch_trades(strategy_bot_names):
    """Return closed trades for the given bot names (list) as dicts, newest first.
    Used by the analyzer. Returns [] if DB unavailable."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        _ensure_trades_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bot, open_ts, pair, profit_ratio, profit_abs, close_ts,
                       duration_min, enter_tag, exit_reason
                FROM bot_trades
                WHERE bot = ANY(%s) AND is_open = FALSE
                ORDER BY close_ts DESC NULLS LAST
                """,
                (list(strategy_bot_names),),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:  # noqa: BLE001
        _warn_once(f"trade read failed ({e})")
        return []


def store_analysis(strategy, payload):
    """Persist the latest per-strategy analysis JSON for later viewing."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_trade_analysis (
                    strategy   TEXT PRIMARY KEY,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    analysis   JSONB
                )
                """
            )
            cur.execute(
                """
                INSERT INTO bot_trade_analysis (strategy, updated_at, analysis)
                VALUES (%s, now(), %s)
                ON CONFLICT (strategy) DO UPDATE SET
                    updated_at=now(), analysis=EXCLUDED.analysis
                """,
                (strategy, json.dumps(payload)),
            )
        return True
    except Exception as e:  # noqa: BLE001
        _warn_once(f"analysis write failed ({e})")
        return False


if __name__ == "__main__":
    # quick self-test: writes a dummy row if DATABASE_URL is set, else no-ops.
    ok = publish("selftest", status="online", pnl_abs=1.23, pnl_pct=0.0123,
                 extra={"note": "self-test"})
    print("publish ->", ok, "(DATABASE_URL set)" if _DATABASE_URL else "(no DATABASE_URL; no-op)")
    time.sleep(0.1)
