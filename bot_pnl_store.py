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
import sys
import json
import math
import time
import hashlib

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


# ---------------------------------------------------------------------------
# BUILD ID — what code is this process actually running?
# ---------------------------------------------------------------------------
# WHY IT LIVES HERE and not in its own module. It was `build_id.py` for about
# ten minutes, until the born-dark guard reported it MISSING FROM 19 OF 20
# IMAGES — because this file is universal and nothing COPYs that one. The fix
# is not 20 `COPY build_id.py` lines: that is a ROSTER, and a roster nobody
# maintains is the control that already failed (17-Jul: LIVE_FRESHNESS_LIMITS
# rotted, the deploy path list rotted, and this very guard exists because
# `brain_stats` shipped to an image that lacked it). A new image tomorrow
# forgets the COPY, that bot silently never stamps, and the drift detector goes
# quiet for exactly the bot that changed. Here, "can publish" == "can stamp",
# by construction — the property no list can give you.
#
# WHY BYTES, NOT A LABEL. Every self-describing label in this fleet has lied:
# `RAILWAY_GIT_*` reads 0 on EVERY service, connected or not (it produced a
# false fleet-wide "nothing is git-connected" verdict on 17-Jul);
# `railway status` meta.branch is blank for every `railway up`, so CI and a
# desk upload are indistinguishable; `lighter.__version__` reports "1.0.0", a
# release PyPI does not have, while the wheel signing real orders was 1.1.2.
# A hash of the source bytes cannot lie about being those bytes.
#
# WHAT IT CATCHES — ARM DRIFT. Every live bot has a `-lshadow` CONTROL arm in a
# DIFFERENT Railway service (Farmer: trail-blazer-live vs funding-farmer-shadow;
# Taker: tide-rider-lighter-live vs the organ container) — separate deploy
# clocks. `experiment_judge` promotes to `live.funding.*` on "shadow beats live
# per-trade", and `implementation_shortfall` reads that same gap as execution
# quality. Drifted arms put a strategy delta into both numbers, and neither
# organ can see it: they compare OUTCOMES, the drift is in the INPUTS.
_BUILD_ROOT = os.path.dirname(os.path.abspath(__file__))
# A FIXED, DECLARED set — the entry module + the real-money surface both arms
# share. NOT "every repo-local module in sys.modules": a lazy or conditional
# import (`if VENUE.startswith('lighter')`, a try/except organ guard) changes
# the module set without changing the code, so identical arms would report
# different ids and the detector would cry drift forever. The set must not
# depend on the execution path — the same reason `if dry_run` branches cannot
# be compared across arms.
_BUILD_SHARED = ("venues", "funding_basis.py", "bot_pnl_store.py")
_BUILD_CACHE = None


def _build_rel(path):
    """The name a file has INSIDE its image — the only path two arms share.

    LOAD-BEARING: the same module sits at DIFFERENT absolute paths in different
    images (`/app/...` on the live Farmer, `/freqtrade/...` in the organ
    container). Keying on the absolute path would report permanent drift
    between identical code. Falls back to the basename for anything outside the
    root (test tmpdirs only) rather than raising.

    NOTE the explicit prefix test rather than a bare `os.path.relpath`: relpath
    does NOT fail for a path outside the root, it happily returns
    `../../tmp/xyz/arm.py` — so two identical files in different temp dirs got
    different keys and the path-independence fixture caught it. A fallback that
    triggers on an exception is worthless when the function never raises."""
    p = os.path.abspath(path)
    root = _BUILD_ROOT.rstrip(os.sep) + os.sep
    if p.startswith(root):
        return p[len(root):]
    return os.path.basename(p)


def _build_files(entry=None):
    out = []
    if entry and os.path.isfile(entry):
        out.append(os.path.abspath(entry))
    for name in _BUILD_SHARED:
        p = os.path.join(_BUILD_ROOT, name)
        if os.path.isdir(p):
            for d, _sub, fs in os.walk(p):
                out.extend(os.path.join(d, f) for f in fs if f.endswith(".py"))
        elif os.path.isfile(p):
            out.append(p)
    return sorted(set(out), key=_build_rel)


def build_compute(entry=None):
    """(id12, n_files) — sha256 over name+bytes of a fixed file set.
    None on any read failure: a sensor that cannot see must not vote, and a
    fabricated id would read as agreement between two drifted arms."""
    try:
        if entry is None:
            m = sys.modules.get("__main__")
            entry = getattr(m, "__file__", None)
            entry = os.path.abspath(entry) if entry else None
        files = _build_files(entry)
        if not files:
            return None, 0
        h = hashlib.sha256()
        for p in files:
            h.update(_build_rel(p).encode())
            h.update(b"\0")
            with open(p, "rb") as fh:
                h.update(fh.read())
            h.update(b"\0")
        return h.hexdigest()[:12], len(files)
    except Exception:      # noqa: BLE001 — never break a publish
        return None, 0


def build_code_id():
    """Cached per process — the bytes cannot change under a running process."""
    global _BUILD_CACHE
    if _BUILD_CACHE is None:
        _BUILD_CACHE = build_compute()
    return _BUILD_CACHE[0]


def _stamp_build(extra):
    """Stamp `extra.build` on every publish. Never raises, never overwrites a
    caller's key: telemetry must not break a publish that reports real money."""
    try:
        cid = build_code_id()
        if not cid:
            return extra
        out = dict(extra or {})
        out.setdefault("build", cid)
        return out
    except Exception:      # noqa: BLE001
        return extra


def _finite_or_none(x):
    """Coerce a money field to a FINITE float, else None.

    [2026-07-18] The shared bot_pnl schema is nullable and every consumer treats
    None as 'no value'. A NaN/inf/garbage value does NOT fail the write —
    Postgres float8 accepts 'NaN'/'Infinity' — it silently poisons every
    aggregate that reads the column: SUM(pnl_abs) over the fleet becomes NaN, so
    ONE mis-publishing bot corrupts the whole fleet total (and the dashboard's
    `money()` would render it '+nan'). Nulling the bad value contains the blast
    radius to the one row. Never raises; identity on a valid finite number.
    """
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def publish(bot, status="online", equity=None, pnl_abs=None, pnl_pct=None,
            open_trades=None, closed_trades=None, wins=None, losses=None,
            extra=None, pnl_daily=None):
    """Upsert this bot's current snapshot. Returns True on success, else False.

    Safe to call every loop. Never raises.
    """
    conn = _get_conn()
    if conn is None:
        return False
    extra = _stamp_build(extra)
    # Sanitize the money fields BEFORE they reach the shared table — a single
    # NaN/inf poisons the fleet-wide SUM() aggregates (see _finite_or_none).
    equity = _finite_or_none(equity)
    pnl_abs = _finite_or_none(pnl_abs)
    pnl_pct = _finite_or_none(pnl_pct)
    pnl_daily = _finite_or_none(pnl_daily)
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


def locked_state_update(key, fn):
    """[2026-07-16 MERGE-RACE FIX] Serialize a read-modify-write on ONE
    bot_state key across processes: read under a Postgres session advisory
    lock, apply fn(old_dict_or_None) -> new_dict, upsert, release. The
    fleet-tuning key has three authors on independent timers — an unlocked
    merge off a stale read silently dropped the other author's just-written
    levers. Returns the written dict, or None when the DB/lock path is
    unavailable (callers keep their unlocked fallback). fn must be pure and
    fast — the lock is held while it runs. Never raises."""
    conn = _get_conn()
    if conn is None:
        return None
    lock_id = None
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT hashtext(%s)", (key,))
            lock_id = cur.fetchone()[0]
            cur.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
            cur.execute("SELECT state FROM bot_state WHERE bot = %s", (key,))
            row = cur.fetchone()
            old = row[0] if row else None
            if isinstance(old, str):
                try:
                    old = json.loads(old)
                except Exception:
                    old = None
            new = fn(old if isinstance(old, dict) else None)
            if not isinstance(new, dict):
                return None
            cur.execute(
                """
                INSERT INTO bot_state (bot, updated_at, state)
                VALUES (%s, now(), %s)
                ON CONFLICT (bot) DO UPDATE SET
                    updated_at = now(),
                    state      = EXCLUDED.state
                """,
                (key, json.dumps(new)))
            return new
    except Exception as e:  # noqa: BLE001
        _warn_once(f"locked state update failed ({e})")
        return None
    finally:
        if lock_id is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
            except Exception:  # noqa: BLE001
                pass


def load_state_checked(bot):
    """(ok, state) — `ok` is False only if the READ ITSELF failed.

    [2026-07-17] load_state() collapses "no row" and "read failed" into the same
    None. That is fine for a bot that just wants its last state, but it is a trap
    for any caller that SEEDS durable state on an empty read: a Postgres blip
    then looks identical to a first run. The perp sniper seeds its listing
    baseline that way, and a false seed there silently absorbs every live market
    (see the 17-Jul RETRY FIX in lighter_perp_sniper.py). Such callers must be
    able to tell "definitely nothing stored" from "I could not find out".

    ok=True,  state=dict -> the row exists
    ok=True,  state=None -> read succeeded, genuinely no row
    ok=False, state=None -> read FAILED; the caller must NOT infer emptiness
    """
    conn = _get_conn()
    if conn is None:
        return False, None
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT state FROM bot_state WHERE bot = %s", (bot,))
            row = cur.fetchone()
        if row and row[0] is not None:
            return True, (row[0] if isinstance(row[0], dict) else json.loads(row[0]))
        return True, None
    except Exception as e:
        _warn_once(f"state read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False, None


def load_state(bot):
    """Return the bot's saved state dict (from save_state), or None. Never raises.

    NOTE: None means "no state OR the read failed" — see load_state_checked().
    """
    return load_state_checked(bot)[1]


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
            # [2026-07-16] `extra` carries the arm's PROOF-OF-APPLICATION
            # receipt (extra.bars, stamped only inside the bot's apply_levers).
            # It was written since 15-Jul and never selected, so the experiment
            # judge — whose docstring already relies on it ("Every close row
            # carries extra.bars") — could not see which params produced a
            # close, and scored an arm that ignores its levers. Additive: every
            # other consumer ignores unknown keys.
            # [2026-07-17 DRIFT PLUMBING] venue/entry_price/exit_price were in
            # the table since day one and NEVER selected, so every paper row
            # reached the brain with open_rate/close_rate = None. bot_learn's
            # _post_exit_drift needs both rates and returned None at its guard
            # for ALL 409 recent losers on the living fleet — drift evidence was
            # 0 of 409, silently, because the fetch dropped the columns rather
            # than because the data was missing. `venue` comes along so a
            # consumer can grade a trade on the venue it actually happened on
            # (the brain now refuses to price a Lighter close off any other
            # book). Additive, like the 16-Jul `extra` fix above: every other
            # consumer ignores unknown keys.
            cur.execute(
                "SELECT bot, pair, pnl_abs, pnl_pct, opened_at, closed_at, "
                "reason, extra, venue, entry_price, exit_price "
                "FROM paper_trades WHERE side IS DISTINCT FROM 'skip' "
                "ORDER BY closed_at DESC NULLS LAST LIMIT %s",
                (int(limit),),
            )
            rows = cur.fetchall()
        from datetime import datetime
        out = []
        for (bot, pair, pnl_abs, pnl_pct, opened_at, closed_at, reason,
             extra, venue, entry_price, exit_price) in rows:
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
            def _rate(x):
                # None stays None: a missing fill price must read as ABSENT
                # evidence, never as 0.0 (which would look like a real price).
                try:
                    return float(x) if x is not None else None
                except (TypeError, ValueError):
                    return None
            out.append({
                "bot": bot, "pair": pair,
                "profit_abs": float(pnl_abs) if pnl_abs is not None else 0.0,
                "profit_ratio": pnl_pct,
                "enter_tag": direction or None,   # None -> brain's "(untagged)"
                "exit_reason": exit_reason or "trade",
                "duration_min": dur,
                "open_ts": opened_at, "close_ts": closed_at,
                "is_open": False,
                # [2026-07-17] the venue this trade actually executed on
                # ('lighter' | None for the CEX sniper / HL-data carry book).
                "venue": venue,
                # freqtrade's names, so a paper row and a bot_trades row carry
                # rates under the SAME keys (bot_learn reads open_rate /
                # close_rate for both).
                "open_rate": _rate(entry_price),
                "close_rate": _rate(exit_price),
                # dict or {} — never None, so consumers can .get() safely
                "extra": extra if isinstance(extra, dict) else {},
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


def _selftest_build():
    """The build-id contract. It had its own module and its own suite for ten
    minutes; the born-dark guard sent it in here, so the suite comes too — a
    guard that moves house without its tests is how `brain_stats` shipped."""
    import tempfile
    a, n = build_compute(__file__)
    assert a and n >= 2, (a, n)
    assert build_compute(__file__)[0] == a, "must be deterministic across calls"

    # THE CONTRACT: different bytes -> different id. Without this the detector
    # reports agreement between two drifted arms — a green light on the judge's
    # invalid promotion bar, which is worse than having no detector.
    with tempfile.TemporaryDirectory() as d:
        m = os.path.join(d, "m.py")
        open(m, "w").write("x = 1\n")
        b1, _ = build_compute(m)
        open(m, "w").write("x = 2\n")
        b2, _ = build_compute(m)
        assert b1 and b2, f"a readable entry must yield an id: {b1!r}/{b2!r}"
        assert b1 != b2, "a byte change MUST change the id"

    # SAME bytes, DIFFERENT path -> SAME id. This is production: the live arm
    # runs /app/<mod>.py, the shadow arm /freqtrade/<mod>.py. Keying on the
    # absolute path would flag permanent drift between identical code.
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        for d in (d1, d2):
            open(os.path.join(d, "arm.py"), "w").write("SAME = 'bytes'\n")
        i1, _ = build_compute(os.path.join(d1, "arm.py"))
        i2, _ = build_compute(os.path.join(d2, "arm.py"))
        assert i1 and i1 == i2, f"same bytes must agree across paths: {i1} vs {i2}"

    # The ENTRY MODULE COUNTS — two bots sharing venues/ are NOT one build.
    # Asserted with a file that is NOT already in _BUILD_SHARED: this module is
    # both the entry and a shared file, so compute(__file__) == the shared-only
    # id and the naive form of this check passes vacuously. A fixture that can
    # only pass is not a fixture (`tests-must-not-fail-on-good-news`, inverted).
    _probe = os.path.join(_BUILD_ROOT, "implementation_shortfall.py")
    if os.path.isfile(_probe):
        _with = build_compute(_probe)[0]
        _without = build_compute(os.path.join(_BUILD_ROOT, "nope.py"))[0]
        assert _with and _without and _with != _without, \
            f"the entry file must change the id: {_with} vs {_without}"

    # the stamp: adds `build`, preserves caller keys, never overwrites one
    e = _stamp_build({"venue": "lighter_live"})
    assert e["build"] == build_code_id() and e["venue"] == "lighter_live", e
    assert _stamp_build(None)["build"] == build_code_id()
    assert _stamp_build({"build": "caller"})["build"] == "caller"
    print(f"bot_pnl_store selftest OK (build id: deterministic, byte-sensitive, "
          f"path-independent, entry counts; stamp preserves caller keys) "
          f"build={a} over {n} files")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest_build())
    # quick self-test: writes a dummy row if DATABASE_URL is set, else no-ops.
    ok = publish("selftest", status="online", pnl_abs=1.23, pnl_pct=0.0123,
                 extra={"note": "self-test"})
    print("publish ->", ok, "(DATABASE_URL set)" if _DATABASE_URL else "(no DATABASE_URL; no-op)")
    time.sleep(0.1)


# ---------------------------------------------------------------------------
# [2026-07-07 CROSS-BOT] Fleet-level reader + append-only history for the
# shared layers (regime oracle, fleet risk, signal bus). Same guarded,
# never-raise pattern as everything above.


def fetch_realized_window(bots, days=7):
    """[2026-07-16 LIVE-LANE BALANCE] Per-bot realized P&L over the trailing
    window, straight from the paper_trades ledger: {bot: {"pnl", "closes"}}.
    Bots with no closes in the window get {"pnl": 0.0, "closes": 0} — present,
    not missing, so callers can tell "quiet book" from "DB dark". Returns None
    if the DB is unavailable (callers must fail toward their conservative
    side). Read-only; used by evidence_board's live clip lane, which needed a
    time-local view: lifetime pnl_abs anchors never heal (a healed book stayed
    'hurt' forever) and never forgive (one good month masked a bad week)."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        _ensure_paper_trades_table(conn)
        from datetime import datetime, timedelta, timezone
        cut = (datetime.now(timezone.utc) - timedelta(days=float(days))).isoformat()
        out = {str(b): {"pnl": 0.0, "closes": 0} for b in bots}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bot, COUNT(*), COALESCE(SUM(pnl_abs), 0) FROM paper_trades "
                "WHERE bot = ANY(%s) AND side IS DISTINCT FROM 'skip' "
                "AND closed_at >= %s GROUP BY bot",
                (list(out), cut))
            for b, n, s in cur.fetchall():
                out[str(b)] = {"pnl": float(s or 0.0), "closes": int(n or 0)}
        return out
    except Exception as e:  # noqa: BLE001
        _warn_once(f"realized-window read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return None


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
                # [2026-07-15 AUDIT FIX] include pnl_pct — the immune organ's
                # NaN/absurd-pnl_pct sickness check reads it; it was omitted, so
                # that check silently never fired on real rows.
                "SELECT bot, updated_at, status, equity, pnl_abs, pnl_pct, "
                "open_trades, closed_trades, wins, losses, extra FROM bot_pnl")
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


_HISTORY_KEEP_DAYS = float(os.environ.get("BOT_STATE_HISTORY_KEEP_DAYS", "60"))
_hist_writes = 0


def prune_history(conn=None, keep_days=None):
    """[2026-07-16 AUDIT FIX] bot_state_history had NO retention anywhere in
    the repo (~400+ rows/day from the 15-Jul organs alone — the shared
    Railway Postgres bloated indefinitely). Deletes rows older than
    keep_days (default 60 — every consumer reads days, not months: brain
    lens grading, replay tape, regen last-good 24h, /bus.json?hours<=200).
    Returns rows deleted, or None on DB trouble. Never raises."""
    conn = conn or _get_conn()
    if conn is None:
        return None
    try:
        _ensure_history_table(conn)
        days = float(keep_days if keep_days is not None else _HISTORY_KEEP_DAYS)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM bot_state_history WHERE ts < now() - "
                "make_interval(days => %s)", (days,))
            return cur.rowcount
    except Exception as e:  # noqa: BLE001
        _warn_once(f"history prune failed ({e})")
        return None


def save_history(key, payload):
    """Append one snapshot to bot_state_history (oracle calls, risk lights) so
    the shared layers become backtestable. Safe every loop. Never raises.
    Every ~200th write also age-prunes the table (see prune_history)."""
    global _hist_writes
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
        _hist_writes += 1
        if _hist_writes % 200 == 0:
            n = prune_history(conn)
            if n:
                print(f"[bot_pnl_store] history prune: {n} rows older than "
                      f"{_HISTORY_KEEP_DAYS:g}d removed", flush=True)
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
