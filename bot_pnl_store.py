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
        # [2026-07-08] bot-supplied daily P&L. The dashboard prefers this over
        # its server-side equity-curve delta when present — lets bots with an
        # authoritative broker daily figure (Alpaca equity vs last_equity)
        # override the glitch-prone cross-snapshot estimate.
        cur.execute(
            "ALTER TABLE bot_pnl ADD COLUMN IF NOT EXISTS pnl_daily DOUBLE PRECISION"
        )
    _table_ready = True


def publish(bot, status="online", equity=None, pnl_abs=None, pnl_pct=None,
            open_trades=None, closed_trades=None, wins=None, losses=None,
            extra=None, pnl_daily=None):
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
                    pnl_pct, open_trades, closed_trades, wins, losses, extra,
                    pnl_daily)
                VALUES (%s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    extra         = EXCLUDED.extra,
                    pnl_daily     = EXCLUDED.pnl_daily
                """,
                (bot, status, equity, pnl_abs, pnl_pct, open_trades,
                 closed_trades, wins, losses,
                 json.dumps(extra) if extra is not None else None,
                 pnl_daily),
            )
        return True
    except Exception as e:
        # [2026-07-12 GO-GREEN] one immediate reconnect+retry so a transient
        # Postgres blip doesn't cost a whole publish cycle. Second failure
        # falls through to the original guarded behaviour.
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        try:
            conn2 = _get_conn()
            if conn2 is not None:
                with conn2.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO bot_pnl (bot, updated_at, status, equity, pnl_abs,
                            pnl_pct, open_trades, closed_trades, wins, losses, extra,
                            pnl_daily)
                        VALUES (%s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                            extra         = EXCLUDED.extra,
                            pnl_daily     = EXCLUDED.pnl_daily
                        """,
                        (bot, status, equity, pnl_abs, pnl_pct, open_trades,
                         closed_trades, wins, losses,
                         json.dumps(extra) if extra is not None else None,
                         pnl_daily),
                    )
                return True
        except Exception as e2:
            _warn_once(f"write failed twice ({e}; retry: {e2})")
            try:
                _conn.close()  # type: ignore[union-attr]
            except Exception:
                pass
            _conn = None
            return False
        _warn_once(f"write failed ({e})")
        return False


# ---------------------------------------------------------------------------
# Durable bot state (one JSON blob per bot). Lets the dry-run bots restore
# their paper account (equity, open positions, risk state) after a redeploy or
# restart, so equity curves GROW across deploys instead of resetting to $1000.

_state_table_ready = False


def _ensure_state_table(conn):
    global _state_table_ready
    if _state_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_state (
                bot        TEXT PRIMARY KEY,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                state      JSONB
            )
            """
        )
    _state_table_ready = True


def save_state(bot, state):
    """Upsert this bot's durable state blob. Safe to call every loop. Never raises."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_state (bot, updated_at, state)
                VALUES (%s, now(), %s)
                ON CONFLICT (bot) DO UPDATE SET
                    updated_at = now(),
                    state      = EXCLUDED.state
                """,
                (bot, json.dumps(state)),
            )
        return True
    except Exception as e:
        _warn_once(f"state write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def heartbeat(bot):
    """[2026-07-12 GO-GREEN] Touch ONLY updated_at on the bot's existing row —
    a liveness proof that never clobbers the last good snapshot. Cheap enough
    to call at the TOP of every loop, so slow scans, venue outages and
    skip-paths that never reach the full publish can't read as a dead bot."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE bot_pnl SET updated_at = now() WHERE bot = %s", (bot,))
        return True
    except Exception as e:
        _warn_once(f"heartbeat failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def set_status(bot, status):
    """[2026-07-12 GO-GREEN] Update ONLY status+updated_at (keeps the last
    equity/P&L intact). Used by boot-refusal paths so an ARMED/misconfigured
    bot shows as ERROR on the dashboard instead of silently going stale."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bot_pnl (bot, updated_at, status)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (bot) DO UPDATE SET
                       updated_at = now(), status = EXCLUDED.status""",
                (bot, status))
        return True
    except Exception as e:
        _warn_once(f"set_status failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def save_daily_halt(bot, day_iso, day_start_equity=None):
    """Persist a tripped daily-loss halt under <bot>:halt. Never raises.

    [2026-07-11 DURABLE HALT] halted_today was memory-only in every perps bot,
    so a restart/redeploy on the same UTC day silently resumed trading after
    the loss rail fired. Bots call load_daily_halt at boot to stay halted.
    """
    return save_state(bot + ":halt", {"halted_date": day_iso,
                                      "day_start_equity": day_start_equity})


def load_daily_halt(bot, day_iso):
    """Return the halt state saved for day_iso (UTC 'YYYY-MM-DD'), else None."""
    st = load_state(bot + ":halt") or {}
    return st if st.get("halted_date") == day_iso else None


def load_state(bot):
    """Return the bot's saved state dict (from save_state), or None. Never raises."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT state FROM bot_state WHERE bot = %s", (bot,))
            row = cur.fetchone()
        if row and row[0] is not None:
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return None
    except Exception as e:
        _warn_once(f"state read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return None


def fetch_states(keys):
    """[2026-07-15 BLOODSTREAM] Batch read: {key: state_dict} for many keys in
    ONE query instead of N round-trips. Organs that read a fistful of bus keys
    per cycle (immune, respiration, regen, evidence board) get their whole
    working set in a single beat. Missing keys are simply absent from the
    result. Returns {} on any failure — callers fall back to load_state /
    defaults, so this is a pure optimization with the same fail-safe contract."""
    keys = [k for k in (keys or []) if k]
    if not keys:
        return {}
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT bot, state FROM bot_state WHERE bot = ANY(%s)",
                        (list(keys),))
            out = {}
            for k, v in cur.fetchall():
                if v is None:
                    continue
                out[k] = v if isinstance(v, dict) else json.loads(v)
        return out
    except Exception as e:
        _warn_once(f"batch state read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return {}


_trades_table_ready = False


def _ensure_trades_table(conn):
    """Per-trade history table. Keyed by (bot, open_ts, pair) — stable across
    redeploys. Pair is included so two bots entering the same coin at the same
    candle time never collide on the PK."""
    global _trades_table_ready
    if _trades_table_ready:
        return
    with conn.cursor() as cur:
        # [2026-07-06] Migrate old (bot, open_ts) PK -> (bot, open_ts, pair).
        # Recreate the table if the old constraint exists to fix cross-bot collisions.
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_name = 'bot_trades'
                    AND constraint_type = 'PRIMARY KEY'
                ) THEN
                    -- Check if pair is NOT already in the PK
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.key_column_usage
                        WHERE table_name = 'bot_trades'
                        AND constraint_name = (
                            SELECT constraint_name FROM information_schema.table_constraints
                            WHERE table_name = 'bot_trades' AND constraint_type = 'PRIMARY KEY'
                        )
                        AND column_name = 'pair'
                    ) THEN
                        DROP TABLE bot_trades;
                    END IF;
                END IF;
            END
            $$;
        """)
        conn.commit()
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
                PRIMARY KEY (bot, open_ts, pair)
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
                    ON CONFLICT (bot, open_ts, pair) DO UPDATE SET
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


# --------------------------------------------------------------------------- #
# Durable paper-trade ledger (2026-06-25)
#
# Bots that compute their cumulative P&L by re-reading a LOCAL csv each loop
# (e.g. listing_sniper.py reading sniper_trades.csv) silently reset to $0 / 0
# closed whenever that ephemeral file is wiped on a Railway redeploy — which is
# exactly what happened on 2026-06-24/25 (listing-sniper: -$300/6 closed -> 0/0).
# This table persists each closed paper trade in Postgres, keyed by a caller-
# supplied stable id, so the cumulative aggregate survives restarts. Idempotent.
# --------------------------------------------------------------------------- #
_paper_trades_table_ready = False


def _ensure_paper_trades_table(conn):
    global _paper_trades_table_ready
    if _paper_trades_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
                bot        TEXT NOT NULL,
                trade_id   TEXT NOT NULL,
                pair       TEXT,
                pnl_abs    DOUBLE PRECISION,
                pnl_pct    DOUBLE PRECISION,
                opened_at  TEXT,
                closed_at  TEXT,
                reason     TEXT,
                seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (bot, trade_id)
            )
            """
        )
        # [2026-07-09 LIGHTER GATE-0] venue provenance so shadow/testnet/live
        # rows are queryable apart from the HL paper era (venue NULL = hl paper).
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS venue TEXT")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS shadow BOOLEAN")
        # [2026-07-15 EVIDENCE] learning-layer widening (revives the 7-Jul
        # b82c5aa design that never reached the deployed line): WHERE the trade
        # happened (prices/size/side), the publisher's own tag, and a JSONB
        # extra for entry-time context (e.g. the sniper's book microstructure).
        # side='skip' is reserved for gate-rejection log rows — every trade
        # reader must exclude it (fetch_paper_trades does; per-bot aggregates
        # are safe because skips publish under a separate '<bot>-skips' name).
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS side TEXT")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS tag TEXT")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS entry_price DOUBLE PRECISION")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS exit_price DOUBLE PRECISION")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS size DOUBLE PRECISION")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS extra JSONB")
    _paper_trades_table_ready = True


def publish_paper_trade(bot, trade_id, pnl_abs, pnl_pct=None, pair=None,
                        opened_at=None, closed_at=None, reason=None,
                        venue=None, shadow=None, side=None, tag=None,
                        entry_price=None, exit_price=None, size=None,
                        extra=None):
    """Idempotently record one closed paper trade so cumulative P&L survives a
    redeploy. `trade_id` must be stable+unique for the trade. Never raises.
    [2026-07-15 EVIDENCE] optional learning fields: side ('long'/'short', or
    'skip' for gate-rejection logs), publisher tag, entry/exit price, size, and
    a JSON-able `extra` dict for entry-time context."""
    conn = _get_conn()
    if conn is None or trade_id is None:
        return False
    try:
        _ensure_paper_trades_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_trades (bot, trade_id, pair, pnl_abs, pnl_pct,
                    opened_at, closed_at, reason, venue, shadow, side, tag,
                    entry_price, exit_price, size, extra, seen_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, now())
                ON CONFLICT (bot, trade_id) DO UPDATE SET
                    pnl_abs=EXCLUDED.pnl_abs, pnl_pct=EXCLUDED.pnl_pct,
                    closed_at=EXCLUDED.closed_at, reason=EXCLUDED.reason,
                    venue=EXCLUDED.venue, shadow=EXCLUDED.shadow,
                    side=EXCLUDED.side, tag=EXCLUDED.tag,
                    entry_price=EXCLUDED.entry_price,
                    exit_price=EXCLUDED.exit_price, size=EXCLUDED.size,
                    extra=EXCLUDED.extra, seen_at=now()
                """,
                (bot, str(trade_id), pair, pnl_abs, pnl_pct,
                 opened_at, closed_at, reason, venue, shadow, side, tag,
                 entry_price, exit_price, size,
                 json.dumps(extra) if extra is not None else None),
            )
        return True
    except Exception as e:  # noqa: BLE001
        _warn_once(f"paper-trade write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def fetch_paper_aggregate(bot):
    """Return {'realized','closed','wins','losses'} from the durable ledger, or
    None if the DB is unavailable. Lets a bot recover its cumulative totals after
    a local-file wipe."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        _ensure_paper_trades_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(pnl_abs), 0.0),
                       COUNT(*),
                       COUNT(*) FILTER (WHERE pnl_abs > 0)
                FROM paper_trades WHERE bot = %s
                """,
                (bot,),
            )
            realized, closed, wins = cur.fetchone()
        closed = int(closed or 0)
        wins = int(wins or 0)
        return {"realized": float(realized or 0.0), "closed": closed,
                "wins": wins, "losses": closed - wins}
    except Exception as e:  # noqa: BLE001
        _warn_once(f"paper-trade read failed ({e})")
        return None


def split_reason(reason):
    """(enter_tag | None, exit_reason) from a paper-ledger close `reason`.

    [2026-07-14 TAG-SEMANTICS FIX] Only a real direction prefix
    (long_/short_) carries entry info. Splitting EVERY reason made exit
    reasons masquerade as entry modes — funding-carry's 'flip' and the
    sniper's 'delisted' became enter_tags, and the brain spent 92 runs
    proposing to "tighten the 'flip' entry gates" (an exit path, not an
    entry). No direction prefix -> untagged entry + the FULL reason kept as
    exit_reason (also fixes 'decay_paid' being mangled into 'decay'/'paid').
    [2026-07-15 AUDIT FIX] also accept the Ticket Taker's hyphenated
    side-lens tags ('long-breakout_tp' -> enter 'long-breakout', exit 'tp')
    — the underscore-only gate silently untagged every taker close.
    [2026-07-15 LEARNING-LOOP WIRING] the split is at the FIRST underscore,
    so composers must keep the tag part underscore-free — the family bot
    hyphenates its strategy tags ('long-bounce-pullback_<exit>', see
    lighter_family_bot.ledger_reason). This helper is the ONE parser those
    composers round-trip against."""
    reason = reason or ""
    if reason.startswith(("long_", "short_", "long-", "short-")):
        direction, _sep, exit_reason = reason.partition("_")
        return (direction or None), (exit_reason or "trade")
    return None, (reason or "trade")


def fetch_paper_trades(limit=2000):
    """Per-trade rows from the durable paper_trades ledger (perps + sniper),
    normalized to the SAME shape bot_learn expects from the freqtrade /trades.json
    feed — so the learning brain can analyse the whole fleet, not just the
    freqtrade bots. The stored `reason` is '<direction>_<exit>' (e.g.
    'long_range_high', 'short_stop'); we split it so the brain gets enter_tag
    (long/short) AND exit_reason. Returns [] if the DB is unavailable."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        _ensure_paper_trades_table(conn)
        with conn.cursor() as cur:
            # [2026-07-15 EVIDENCE] side='skip' rows are gate-rejection logs
            # (sniper), not trades — they must never reach the brain/analyzer.
            cur.execute(
                "SELECT bot, pair, pnl_abs, pnl_pct, opened_at, closed_at, reason "
                "FROM paper_trades WHERE side IS DISTINCT FROM 'skip' "
                "ORDER BY closed_at DESC NULLS LAST LIMIT %s",
                (int(limit),),
            )
            rows = cur.fetchall()
        from datetime import datetime
        out = []
        for bot, pair, pnl_abs, pnl_pct, opened_at, closed_at, reason in rows:
            direction, exit_reason = split_reason(reason)
            # [2026-07-15 AUDIT FIX] tolerant timestamp parse — the listing
            # sniper writes '2026-07-13 15:05:04 UTC', which fromisoformat
            # rejects, so its 337 rows carried duration_min=None forever.
            def _pts(s):
                s = str(s).strip().replace("Z", "+00:00")
                if s.endswith(" UTC"):
                    s = s[:-4] + "+00:00"
                return datetime.fromisoformat(s)
            dur = None
            try:
                if opened_at and closed_at:
                    dur = max(0.0, (_pts(closed_at) - _pts(opened_at))
                              .total_seconds() / 60.0)
            except Exception:
                dur = None
            out.append({
                "bot": bot, "pair": pair,
                "profit_abs": float(pnl_abs) if pnl_abs is not None else 0.0,
                "profit_ratio": pnl_pct,
                "enter_tag": direction or None,   # None -> brain's "(untagged)"
                "exit_reason": exit_reason or "trade",
                "duration_min": dur,
                "open_ts": opened_at, "close_ts": closed_at,
                "is_open": False,
            })
        return out
    except Exception as e:  # noqa: BLE001
        _warn_once(f"paper-trade fetch failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return []


if __name__ == "__main__":
    # quick self-test: writes a dummy row if DATABASE_URL is set, else no-ops.
    ok = publish("selftest", status="online", pnl_abs=1.23, pnl_pct=0.0123,
                 extra={"note": "self-test"})
    print("publish ->", ok, "(DATABASE_URL set)" if _DATABASE_URL else "(no DATABASE_URL; no-op)")
    time.sleep(0.1)


# ---------------------------------------------------------------------------
# [2026-07-07 CROSS-BOT] Fleet-level reader + append-only history for the
# shared layers (regime oracle, fleet risk, signal bus). Same guarded,
# never-raise pattern as everything above.


def fetch_bot_pnl():
    """Return every bot's latest bot_pnl row as a list of dicts, or None if
    the DB is unavailable. Read-only; used by fleet_risk.py."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bot, updated_at, status, equity, pnl_abs, open_trades, "
                "closed_trades, wins, losses, extra FROM bot_pnl")
            cols = [d[0] for d in cur.description]
            out = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if isinstance(d.get("extra"), str):
                    try:
                        d["extra"] = json.loads(d["extra"])
                    except Exception:
                        d["extra"] = {}
                if d.get("updated_at") is not None:
                    d["updated_at"] = d["updated_at"].isoformat()
                out.append(d)
        return out
    except Exception as e:
        _warn_once(f"bot_pnl read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return None


_history_table_ready = False


def _ensure_history_table(conn):
    global _history_table_ready
    if _history_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_state_history (
                key     TEXT NOT NULL,
                ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
                payload JSONB
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS bot_state_history_key_ts "
            "ON bot_state_history (key, ts)")
    _history_table_ready = True


def save_history(key, payload):
    """Append one snapshot to bot_state_history (oracle calls, risk lights) so
    the shared layers become backtestable. Safe every loop. Never raises."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_history_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bot_state_history (key, ts, payload) "
                "VALUES (%s, now(), %s)",
                (key, json.dumps(payload)))
        return True
    except Exception as e:
        _warn_once(f"history write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def fetch_state_history(key, limit=800):
    """[2026-07-14] Read side of save_history: recent bot_state_history
    snapshots for one shared-layer key, NEWEST FIRST -> [{"ts": iso, "payload":
    dict}]. Built for the brain's diagnosis layer (joining trades to the
    regime-oracle reading at their open time). Returns [] when unavailable."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        _ensure_history_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ts, payload FROM bot_state_history "
                "WHERE key = %s ORDER BY ts DESC LIMIT %s",
                (key, int(limit)))
            rows = cur.fetchall()
        out = []
        for ts, payload in rows:
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    continue
            out.append({"ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "payload": payload or {}})
        return out
    except Exception as e:  # noqa: BLE001
        _warn_once(f"state-history read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return []


# --------------------------------------------------------------------------
# venue order log [2026-07-09 LIGHTER GATE-0]
# Order-level provenance for the Lighter migration: every shadow-modelled fill
# AND (later) every live order lands here with the raw exchange response, so
# Gate-3 can price realizable spread/slippage per market from real evidence.
_venue_orders_table_ready = False


def _ensure_venue_orders_table(conn):
    global _venue_orders_table_ready
    if _venue_orders_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS venue_orders (
                id            BIGSERIAL PRIMARY KEY,
                at            TIMESTAMPTZ NOT NULL DEFAULT now(),
                bot           TEXT NOT NULL,
                venue         TEXT NOT NULL,
                shadow        BOOLEAN NOT NULL DEFAULT TRUE,
                coin          TEXT,
                side          TEXT,
                size          DOUBLE PRECISION,
                px_decision   DOUBLE PRECISION,
                px_fill       DOUBLE PRECISION,
                spread_bps    DOUBLE PRECISION,
                slippage_bps  DOUBLE PRECISION,
                raw           JSONB
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS venue_orders_bot_at "
            "ON venue_orders (bot, at)")
    _venue_orders_table_ready = True


def publish_venue_order(bot, venue, shadow, coin, side, size,
                        px_decision=None, px_fill=None, spread_bps=None,
                        slippage_bps=None, raw=None):
    """Append one venue order (shadow or live) to the durable order log.
    Guarded like every publisher here: never raises into a trading loop."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_venue_orders_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO venue_orders (bot, venue, shadow, coin, side, size,
                    px_decision, px_fill, spread_bps, slippage_bps, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (bot, venue, bool(shadow), coin, side, size, px_decision,
                 px_fill, spread_bps, slippage_bps,
                 json.dumps(raw) if raw is not None else None),
            )
        return True
    except Exception as e:  # noqa: BLE001
        _warn_once(f"venue-order write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False
