#!/usr/bin/env python3
"""
parliament/ecosystem_db.py — the central SQLite ecosystem database.

The Parliament's SHARED MEMORY: every scanner signal, every trade, every
tuner lever episode, every ML training sample and heartbeat lands here. It
is the substrate the system evolves on — the ML engine trains from `trades`
+ `features`, the tuners replay `trades` against `candles`, Howard grades
lever episodes from `tuning`, and ANY other bot that writes rows into this
file joins the learning loop (Howard also INGESTS the fleet's Postgres
paper_trades ledger into `trades` with source='fleet', so the wider fleet
is in the training set from day one).

Storage: stdlib sqlite3, WAL mode, one file. Default path prefers the
Railway persist volume (/freqtrade/persist) so memory survives redeploys;
falls back to CWD; PARLIAMENT_DB overrides. All calls are synchronous and
fast (indexed, small rows) — callers on the event loop use them directly;
nothing here blocks on network.

Fail-safe: a broken/unwritable DB degrades to an in-memory database and the
system keeps trading (it just forgets on restart) — a storage fault must
never stop a shadow book.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time

log = logging.getLogger("parliament.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    ts REAL NOT NULL, scanner TEXT NOT NULL, sym TEXT NOT NULL,
    direction INTEGER NOT NULL, strength REAL NOT NULL, payload TEXT);
CREATE INDEX IF NOT EXISTS ix_signals_ts ON signals (ts);
CREATE INDEX IF NOT EXISTS ix_signals_scanner ON signals (scanner, ts);

CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY, bot TEXT NOT NULL, source TEXT NOT NULL,
    sym TEXT, side TEXT, tag TEXT, opened_ts REAL, closed_ts REAL,
    entry_px REAL, exit_px REAL, size REAL, pnl_abs REAL, reason TEXT,
    features TEXT);
CREATE INDEX IF NOT EXISTS ix_trades_bot ON trades (bot, closed_ts);

CREATE TABLE IF NOT EXISTS candles (
    sym TEXT NOT NULL, resolution TEXT NOT NULL, ts INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY (sym, resolution, ts));

CREATE TABLE IF NOT EXISTS tuning (
    id INTEGER PRIMARY KEY AUTOINCREMENT, bot TEXT NOT NULL,
    param TEXT NOT NULL, value REAL NOT NULL, baseline REAL NOT NULL,
    applied_ts REAL NOT NULL, expires_ts REAL NOT NULL,
    released_ts REAL, verdict TEXT, note TEXT);
CREATE INDEX IF NOT EXISTS ix_tuning_bot ON tuning (bot, expires_ts);

CREATE TABLE IF NOT EXISTS heartbeats (
    organ TEXT PRIMARY KEY, ts REAL NOT NULL, note TEXT);

CREATE TABLE IF NOT EXISTS memory (
    key TEXT PRIMARY KEY, ts REAL NOT NULL, payload TEXT NOT NULL);
"""


def _default_path() -> str:
    override = os.environ.get("PARLIAMENT_DB", "").strip()
    if override:
        return override
    persist = "/freqtrade/persist"
    if os.path.isdir(persist) and os.access(persist, os.W_OK):
        return os.path.join(persist, "parliament.db")
    return os.path.join(os.getcwd(), "parliament.db")


class EcosystemDB:
    def __init__(self, path: str | None = None):
        self.path = path or _default_path()
        self._lock = threading.Lock()
        try:
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        except Exception as e:  # noqa: BLE001 — storage fault -> memory-only
            log.warning("ecosystem DB unusable at %s (%s) — running in-memory "
                        "(state will not survive restart)", self.path, e)
            self.path = ":memory:"
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    # -- generic helpers ------------------------------------------------------
    def _exec(self, sql: str, args: tuple = ()) -> None:
        try:
            with self._lock, self._conn:
                self._conn.execute(sql, args)
        except Exception as e:  # noqa: BLE001
            log.warning("db write failed (%s): %s", e, sql.split("(")[0].strip())

    def _query(self, sql: str, args: tuple = ()) -> list[tuple]:
        try:
            with self._lock:
                return self._conn.execute(sql, args).fetchall()
        except Exception as e:  # noqa: BLE001
            log.warning("db read failed (%s)", e)
            return []

    # -- signals --------------------------------------------------------------
    def add_signal(self, scanner: str, sym: str, direction: int,
                   strength: float, payload: dict | None = None,
                   ts: float | None = None) -> None:
        self._exec(
            "INSERT INTO signals (ts, scanner, sym, direction, strength, payload)"
            " VALUES (?,?,?,?,?,?)",
            (ts if ts is not None else time.time(), scanner, sym,
             int(direction), float(strength),
             json.dumps(payload) if payload else None))

    def recent_signals(self, hours: float = 4.0,
                       scanner: str | None = None) -> list[dict]:
        cutoff = time.time() - hours * 3600
        if scanner:
            rows = self._query(
                "SELECT ts, scanner, sym, direction, strength, payload FROM signals"
                " WHERE ts >= ? AND scanner = ? ORDER BY ts", (cutoff, scanner))
        else:
            rows = self._query(
                "SELECT ts, scanner, sym, direction, strength, payload FROM signals"
                " WHERE ts >= ? ORDER BY ts", (cutoff,))
        return [{"ts": r[0], "scanner": r[1], "sym": r[2], "direction": r[3],
                 "strength": r[4],
                 "payload": json.loads(r[5]) if r[5] else {}} for r in rows]

    # -- trades ---------------------------------------------------------------
    def record_trade(self, trade_id: str, bot: str, source: str, sym: str,
                     side: str, tag: str, opened_ts: float,
                     closed_ts: float | None, entry_px: float,
                     exit_px: float | None, size: float,
                     pnl_abs: float | None, reason: str | None,
                     features: dict | None = None) -> None:
        self._exec(
            "INSERT INTO trades (trade_id, bot, source, sym, side, tag,"
            " opened_ts, closed_ts, entry_px, exit_px, size, pnl_abs, reason,"
            " features) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(trade_id) DO UPDATE SET closed_ts=excluded.closed_ts,"
            " exit_px=excluded.exit_px, pnl_abs=excluded.pnl_abs,"
            " reason=excluded.reason",
            (trade_id, bot, source, sym, side, tag, opened_ts, closed_ts,
             entry_px, exit_px, size, pnl_abs, reason,
             json.dumps(features) if features else None))

    def closed_trades(self, bot: str | None = None, days: float = 14.0,
                      limit: int = 2000) -> list[dict]:
        cutoff = time.time() - days * 86400
        if bot:
            rows = self._query(
                "SELECT trade_id, bot, source, sym, side, tag, opened_ts,"
                " closed_ts, entry_px, exit_px, size, pnl_abs, reason, features"
                " FROM trades WHERE closed_ts IS NOT NULL AND closed_ts >= ?"
                " AND bot = ? ORDER BY closed_ts DESC LIMIT ?",
                (cutoff, bot, limit))
        else:
            rows = self._query(
                "SELECT trade_id, bot, source, sym, side, tag, opened_ts,"
                " closed_ts, entry_px, exit_px, size, pnl_abs, reason, features"
                " FROM trades WHERE closed_ts IS NOT NULL AND closed_ts >= ?"
                " ORDER BY closed_ts DESC LIMIT ?", (cutoff, limit))
        cols = ("trade_id", "bot", "source", "sym", "side", "tag", "opened_ts",
                "closed_ts", "entry_px", "exit_px", "size", "pnl_abs", "reason",
                "features")
        out = []
        for r in rows:
            d = dict(zip(cols, r))
            d["features"] = json.loads(d["features"]) if d["features"] else None
            out.append(d)
        return out

    # -- candles --------------------------------------------------------------
    def store_candles(self, sym: str, resolution: str, candles: list[dict]) -> None:
        try:
            with self._lock, self._conn:
                self._conn.executemany(
                    "INSERT OR REPLACE INTO candles (sym, resolution, ts,"
                    " o, h, l, c, v) VALUES (?,?,?,?,?,?,?,?)",
                    [(sym, resolution, int(c["t"]), c.get("o"), c.get("h"),
                      c.get("l"), c.get("c"), c.get("v")) for c in candles])
        except Exception as e:  # noqa: BLE001
            log.warning("candle store failed (%s)", e)

    def get_candles(self, sym: str, resolution: str,
                    since_ts: int = 0, limit: int = 500) -> list[dict]:
        rows = self._query(
            "SELECT ts, o, h, l, c, v FROM candles WHERE sym=? AND resolution=?"
            " AND ts >= ? ORDER BY ts DESC LIMIT ?",
            (sym, resolution, since_ts, limit))
        return [{"t": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4],
                 "v": r[5]} for r in reversed(rows)]

    # -- tuner lever episodes -------------------------------------------------
    def open_lever(self, bot: str, param: str, value: float, baseline: float,
                   ttl_sec: float, note: str = "") -> int:
        now = time.time()
        try:
            with self._lock, self._conn:
                cur = self._conn.execute(
                    "INSERT INTO tuning (bot, param, value, baseline,"
                    " applied_ts, expires_ts, note) VALUES (?,?,?,?,?,?,?)",
                    (bot, param, float(value), float(baseline), now,
                     now + ttl_sec, note))
                return int(cur.lastrowid)
        except Exception as e:  # noqa: BLE001
            log.warning("lever open failed (%s)", e)
            return -1

    def active_levers(self, bot: str | None = None) -> list[dict]:
        now = time.time()
        if bot:
            rows = self._query(
                "SELECT id, bot, param, value, baseline, applied_ts, expires_ts"
                " FROM tuning WHERE released_ts IS NULL AND expires_ts > ?"
                " AND bot = ?", (now, bot))
        else:
            rows = self._query(
                "SELECT id, bot, param, value, baseline, applied_ts, expires_ts"
                " FROM tuning WHERE released_ts IS NULL AND expires_ts > ?",
                (now,))
        cols = ("id", "bot", "param", "value", "baseline", "applied_ts",
                "expires_ts")
        return [dict(zip(cols, r)) for r in rows]

    def release_lever(self, lever_id: int, verdict: str = "released") -> None:
        self._exec("UPDATE tuning SET released_ts=?, verdict=? WHERE id=?",
                   (time.time(), verdict, lever_id))

    def grade_lever(self, lever_id: int, verdict: str) -> None:
        self._exec("UPDATE tuning SET verdict=? WHERE id=?", (verdict, lever_id))

    def lever_history(self, bot: str, param: str, limit: int = 10) -> list[dict]:
        rows = self._query(
            "SELECT id, value, baseline, applied_ts, expires_ts, released_ts,"
            " verdict FROM tuning WHERE bot=? AND param=?"
            " ORDER BY applied_ts DESC LIMIT ?", (bot, param, limit))
        cols = ("id", "value", "baseline", "applied_ts", "expires_ts",
                "released_ts", "verdict")
        return [dict(zip(cols, r)) for r in rows]

    # -- heartbeats + memory --------------------------------------------------
    def beat(self, organ: str, note: str = "") -> None:
        self._exec("INSERT INTO heartbeats (organ, ts, note) VALUES (?,?,?)"
                   " ON CONFLICT(organ) DO UPDATE SET ts=excluded.ts,"
                   " note=excluded.note", (organ, time.time(), note))

    def beats(self) -> dict[str, float]:
        return {r[0]: r[1] for r in self._query(
            "SELECT organ, ts FROM heartbeats")}

    def remember(self, key: str, payload: dict) -> None:
        self._exec("INSERT INTO memory (key, ts, payload) VALUES (?,?,?)"
                   " ON CONFLICT(key) DO UPDATE SET ts=excluded.ts,"
                   " payload=excluded.payload",
                   (key, time.time(), json.dumps(payload, default=str)))

    def recall(self, key: str) -> dict | None:
        rows = self._query("SELECT payload FROM memory WHERE key=?", (key,))
        if not rows:
            return None
        try:
            return json.loads(rows[0][0])
        except Exception:  # noqa: BLE001
            return None

    def prune(self, keep_days: float = 30.0) -> None:
        cutoff = time.time() - keep_days * 86400
        self._exec("DELETE FROM signals WHERE ts < ?", (cutoff,))
        self._exec("DELETE FROM trades WHERE closed_ts IS NOT NULL"
                   " AND closed_ts < ?", (cutoff,))
        self._exec("DELETE FROM candles WHERE ts < ?", (int(cutoff),))


def selfcheck() -> None:
    """Offline invariants on an in-memory DB (parliament_main --selftest)."""
    db = EcosystemDB(path=":memory:")
    now = time.time()
    db.add_signal("breakout", "BTC", 1, 0.8, {"z": 2.1})
    assert db.recent_signals(scanner="breakout")[0]["sym"] == "BTC"
    db.record_trade("t1", "pm-abbott", "parliament", "BTC", "long",
                    "long-burst", now - 200.0, now - 100.0, 50000.0, 50500.0,
                    0.001, 0.5, "tp", {"rsi": 70})
    ct = db.closed_trades(bot="pm-abbott")
    assert len(ct) == 1 and ct[0]["pnl_abs"] == 0.5 and ct[0]["features"]["rsi"] == 70
    # upsert: closing the same trade id again updates, never duplicates
    db.record_trade("t1", "pm-abbott", "parliament", "BTC", "long",
                    "long-burst", now - 200.0, now - 90.0, 50000.0, 50400.0,
                    0.001, 0.4, "sl", None)
    ct = db.closed_trades(bot="pm-abbott")
    assert len(ct) == 1 and ct[0]["pnl_abs"] == 0.4
    db.store_candles("BTC", "15m", [{"t": 1, "o": 1, "h": 2, "l": 0.5,
                                     "c": 1.5, "v": 10}])
    assert db.get_candles("BTC", "15m")[0]["c"] == 1.5
    lid = db.open_lever("pm-abbott", "tp_pct", 0.03, 0.02, ttl_sec=3600)
    assert any(l["id"] == lid for l in db.active_levers("pm-abbott"))
    db.release_lever(lid, "expired")
    assert not db.active_levers("pm-abbott")
    db.beat("scanner.breakout")
    assert "scanner.breakout" in db.beats()
    db.remember("regime", {"vol": "high"})
    assert db.recall("regime") == {"vol": "high"}
    print("parliament.ecosystem_db selfcheck OK")
