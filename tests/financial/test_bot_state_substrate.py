"""Tier 2 — bot_pnl_store's SUBSTRATE: the bot_state bus + the trades ledger.

Finding 8 (TEST_COVERAGE_ANALYSIS_2026-07-29.md): every cross-bot contract
rides save_state/load_state (the bot_state table IS the bus every organ
publishes on), every learning loop reads the trades ledger, and none of it
had a direct test. The contracts pinned here:

  * NEVER-RAISE. These functions are called from inside live trading loops;
    a DB outage must return False/None/[]/0 and RESET the cached connection —
    never raise into the loop.
  * load_state_checked's three-state read: (True, dict) / (True, None) /
    (False, None). Its docstring records the incident: a caller that SEEDS
    durable state on an empty read must be able to tell "definitely nothing
    stored" from "I could not find out" (the perp-sniper false-seed class).
  * fetch_trades carries the (ea)/(ee) union doctrine in its SQL:
    `is_open IS NOT TRUE`, never `= FALSE` — NULL is_open rows are CLOSED
    rows and dropping them silently starved the analyzer.
  * publish_trades: rows without an open timestamp are skipped, epoch-ms
    timestamps convert to aware UTC datetimes, and freqtrade's own
    trade_duration wins over the computed fallback.

All via a fake connection at the _get_conn seam — no Postgres anywhere.
"""
import datetime as dt

import pytest

import bot_pnl_store as store

pytestmark = pytest.mark.financial


class _Cursor:
    def __init__(self, rows=None, description=None, fail=False):
        self.rows = rows if rows is not None else []
        self.description = description
        self.fail = fail
        self.executed = []          # (sql, params)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if self.fail:
            raise RuntimeError("db down")
        self.executed.append((sql, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def _wire(monkeypatch, cursor):
    conn = _Conn(cursor)
    monkeypatch.setattr(store, "_get_conn", lambda: conn)
    monkeypatch.setattr(store, "_ensure_state_table", lambda c: None)
    monkeypatch.setattr(store, "_ensure_trades_table", lambda c: None)
    return conn


# ── save_state: the bus write ────────────────────────────────────────────────
def test_save_state_upserts_json(monkeypatch):
    cur = _Cursor()
    _wire(monkeypatch, cur)
    assert store.save_state("fleet-risk", {"light": "green", "n": 3}) is True
    sql, params = cur.executed[-1]
    assert "INSERT INTO bot_state" in sql and "ON CONFLICT (bot)" in sql
    assert params[0] == "fleet-risk"
    assert '"light": "green"' in params[1]          # json.dumps'd payload


def test_save_state_never_raises_and_resets_the_cached_conn(monkeypatch):
    conn = _wire(monkeypatch, _Cursor(fail=True))
    monkeypatch.setattr(store, "_conn", object())   # a stale cached conn
    assert store.save_state("k", {"a": 1}) is False  # no exception escapes
    assert conn.closed is True                       # broken conn closed…
    assert store._conn is None                       # …and the cache reset


def test_no_database_is_a_false_not_a_crash(monkeypatch):
    monkeypatch.setattr(store, "_get_conn", lambda: None)
    assert store.save_state("k", {}) is False
    assert store.load_state("k") is None
    assert store.load_state_checked("k") == (False, None)
    assert store.fetch_states(["a", "b"]) == {}
    assert store.publish_trades("b", [{"open_date": "2026-01-01"}]) == 0
    assert store.fetch_trades(["b"]) == []
    assert store.heartbeat("b") is False


# ── load_state_checked: the three-state read ─────────────────────────────────
def test_load_state_checked_row_exists(monkeypatch):
    _wire(monkeypatch, _Cursor(rows=[('{"x": 1}',)]))
    assert store.load_state_checked("k") == (True, {"x": 1})
    # jsonb may come back as a dict already — both shapes are the contract
    _wire(monkeypatch, _Cursor(rows=[({"y": 2},)]))
    assert store.load_state_checked("k") == (True, {"y": 2})


def test_load_state_checked_distinguishes_empty_from_failed(monkeypatch):
    # ok=True, state=None: read SUCCEEDED, genuinely nothing stored — a seeder
    # may baseline. ok=False: the read FAILED — a seeder must NOT infer
    # emptiness (the perp-sniper false-seed incident).
    _wire(monkeypatch, _Cursor(rows=[]))
    assert store.load_state_checked("k") == (True, None)
    _wire(monkeypatch, _Cursor(fail=True))
    assert store.load_state_checked("k") == (False, None)


def test_load_state_collapses_to_the_value(monkeypatch):
    _wire(monkeypatch, _Cursor(rows=[('{"x": 1}',)]))
    assert store.load_state("k") == {"x": 1}


def test_fetch_states_batch_skips_null_and_short_circuits_empty(monkeypatch):
    cur = _Cursor(rows=[("a", '{"x": 1}'), ("b", None), ("c", {"y": 2})])
    _wire(monkeypatch, cur)
    out = store.fetch_states(["a", "b", "c"])
    assert out == {"a": {"x": 1}, "c": {"y": 2}}    # NULL state absent, not None
    cur.executed.clear()
    assert store.fetch_states([]) == {}
    assert store.fetch_states(None) == {}
    assert cur.executed == []                        # no query for no keys


# ── publish_trades: the ledger write ─────────────────────────────────────────
def test_publish_trades_skips_rows_without_an_open_timestamp(monkeypatch):
    cur = _Cursor()
    _wire(monkeypatch, cur)
    n = store.publish_trades("freqtrade-mum", [
        {"pair": "BTC/USDT", "profit_abs": 1.0},                 # no open ts
        {"open_timestamp": 1_700_000_000_000, "pair": "ETH/USDT",
         "is_open": False, "profit_abs": 2.5, "trade_duration": 90},
    ])
    assert n == 1 and len(cur.executed) == 1
    _, params = cur.executed[0]
    assert params[0] == "freqtrade-mum" and params[2] == "ETH/USDT"
    assert params[3] is False and params[5] == 2.5
    assert params[11] == 90                          # freqtrade's own duration wins


def test_publish_trades_converts_epoch_ms_to_aware_utc(monkeypatch):
    cur = _Cursor()
    _wire(monkeypatch, cur)
    store.publish_trades("b", [{"open_timestamp": 1_700_000_000_000,
                                "close_timestamp": 1_700_003_600_000,
                                "pair": "BTC/USDT"}])
    _, params = cur.executed[0]
    open_ts, close_ts = params[1], params[6]
    assert open_ts.tzinfo == dt.timezone.utc
    assert (close_ts - open_ts).total_seconds() == 3600
    assert params[11] == 60.0                        # _dur_min fallback, minutes


def test_publish_trades_never_raises(monkeypatch):
    _wire(monkeypatch, _Cursor(fail=True))
    assert store.publish_trades("b", [{"open_date": "2026-01-01"}]) == 0


# ── fetch_trades: the (ea)/(ee) union doctrine ───────────────────────────────
def test_fetch_trades_sql_treats_null_is_open_as_closed(monkeypatch):
    cur = _Cursor(rows=[], description=[("bot",), ("pair",)])
    _wire(monkeypatch, cur)
    store.fetch_trades(["freqtrade-mum"])
    sql = cur.executed[-1][0]
    assert "is_open IS NOT TRUE" in sql, "the union doctrine: NULL == closed"
    assert "is_open = FALSE" not in sql, "= FALSE silently drops NULL rows"


def test_fetch_trades_zips_rows_into_dicts(monkeypatch):
    cur = _Cursor(rows=[("freqtrade-mum", "BTC/USDT")],
                  description=[("bot",), ("pair",)])
    _wire(monkeypatch, cur)
    assert store.fetch_trades(["freqtrade-mum"]) == [
        {"bot": "freqtrade-mum", "pair": "BTC/USDT"}]


# ── heartbeat: liveness without clobbering the snapshot ──────────────────────
def test_heartbeat_touches_only_updated_at(monkeypatch):
    cur = _Cursor()
    _wire(monkeypatch, cur)
    assert store.heartbeat("freqtrade-mum") is True
    sql, params = cur.executed[-1]
    # the SET clause carries updated_at and NOTHING else — a heartbeat must
    # never clobber the last good money snapshot
    assert "SET updated_at = now() WHERE" in sql
    assert "equity" not in sql and "pnl_abs" not in sql
    assert params == ("freqtrade-mum",)
