"""[(zp)] BOOT-TIME DDL ON A HOT TABLE IS A LOCK CONVOY — AND THE FLEET RAN
NINE OF THEM PER PROCESS, ON ITS HOTTEST TABLE, EVERY TIME IT REDEPLOYED.

Measured 9-Sep on the live dashboard, twice, each within minutes of a fleet
redeploy (05:55Z and 12:47Z): /trades.json requests of 90-250 s, /pnl.json 499
at 45 s, /watchdog.json (no DB) 3 ms, then everything draining in one burst —
with CPU idle on the dashboard AND on Postgres, whose log showed ~15 backends
dropping "with an open transaction" in the same second. Idle CPU with
minute-long waits is lock queueing, not work.

THE LOCK. Every `_ensure_*` here ran `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
at a process's first DB touch. Postgres takes ACCESS EXCLUSIVE for that
statement BEFORE finding the column exists; one such ALTER queued behind a
long SELECT makes every later SELECT on the table queue behind the ALTER. A
redeploy boots ~20 processes inside two minutes, each firing eight of them at
`paper_trades` and one at `bot_pnl`.

THE FIX, two halves, both pinned here:
  * SKIP: `_existing_columns` reads information_schema (ACCESS SHARE, conflicts
    with nothing) and the ALTER runs ONLY for a column that is genuinely
    missing. In production every column exists -> boot takes ZERO exclusive
    locks. The class-closer test asserts exactly that: a complete schema
    executes no ALTER at all.
  * BOUND: an ALTER that must run (a real migration) holds `lock_timeout`
    (DDL_LOCK_TIMEOUT_S, default 3 s) and gives up rather than holding the
    queue; the caller leaves its `_ready` flag unset so the next call retries.
FAIL-SAFE toward today's behaviour: an unreadable catalogue treats every
column as missing and runs the ALTER path exactly as before — never worse.
Identifiers go through psycopg2.sql, never f-strings.
"""
import os
import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.autonomy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import bot_pnl_store as S              # noqa: E402


def _render(q):
    """psycopg2.sql.Composed -> plain text without a live connection."""
    from psycopg2 import sql
    if isinstance(q, str):
        return q
    if isinstance(q, sql.Composed):
        return "".join(_render(x) for x in q.seq)
    if isinstance(q, sql.SQL):
        return q.string
    if isinstance(q, sql.Identifier):
        return ".".join(f'"{x}"' for x in q.strings)
    if isinstance(q, sql.Literal):
        v = q.wrapped
        return f"'{v}'" if isinstance(v, str) else str(v)
    return str(q)


class _Cur:
    def __init__(self, conn):
        self.c = conn
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, q, params=None):
        text = _render(q)
        self.c.executed.append(text)
        if "information_schema.columns" in text:
            if self.c.catalogue is None:
                raise RuntimeError("catalogue unreadable")
            self._rows = [(c,) for c in self.c.catalogue]
            return
        if text.startswith("ALTER TABLE") and self.c.fail_alter:
            raise RuntimeError("canceling statement due to lock timeout")
        self._rows = []
    def fetchall(self):
        return list(self._rows)


class _Conn:
    def __init__(self, catalogue, fail_alter=False):
        self.catalogue, self.fail_alter, self.executed = catalogue, fail_alter, []
    def cursor(self):
        return _Cur(self)


def _alters(conn):
    return [q for q in conn.executed if q.startswith("ALTER TABLE")]


@pytest.fixture(autouse=True)
def _fresh_flags(monkeypatch):
    monkeypatch.setattr(S, "_table_ready", False)
    monkeypatch.setattr(S, "_paper_trades_table_ready", False)


# --------------------------------------------------------- THE CLASS-CLOSER

def test_a_complete_schema_takes_zero_exclusive_locks_at_boot():
    """Production: every column exists. The whole point — no ALTER runs."""
    have = {"bot", "trade_id"} | {n for n, _t in S.PAPER_TRADES_COLUMNS}
    c = _Conn(catalogue=have)
    S._ensure_paper_trades_table(c)
    assert _alters(c) == [], _alters(c)
    assert not any("lock_timeout" in q for q in c.executed)
    assert S._paper_trades_table_ready is True
    # and the read that decided it was a catalogue read, not a lock
    assert any("information_schema.columns" in q for q in c.executed)


def test_bot_pnl_is_covered_too():
    c = _Conn(catalogue={"bot", "pnl_daily"})
    S._ensure_table(c)
    assert _alters(c) == []
    assert S._table_ready is True


# ------------------------------------------------------ ONLY WHAT IS MISSING

def test_only_the_missing_column_is_added_and_under_a_bounded_lock():
    have = {n for n, _t in S.PAPER_TRADES_COLUMNS} - {"extra"}
    c = _Conn(catalogue=have)
    S._ensure_paper_trades_table(c)
    a = _alters(c)
    assert len(a) == 1 and '"paper_trades"' in a[0] and '"extra"' in a[0] and "JSONB" in a[0], a
    i_set = next(i for i, q in enumerate(c.executed) if q.startswith("SET lock_timeout = '"))
    i_alt = next(i for i, q in enumerate(c.executed) if q.startswith("ALTER TABLE"))
    i_rst = next(i for i, q in enumerate(c.executed) if q == "SET lock_timeout = 0")
    assert i_set < i_alt < i_rst, c.executed
    assert S._paper_trades_table_ready is True


def test_the_bound_is_the_declared_constant_in_milliseconds():
    c = _Conn(catalogue=set())
    S._add_columns_if_missing(c, "bot_pnl", S.BOT_PNL_COLUMNS, lock_timeout_s=2.5)
    assert any(q == "SET lock_timeout = '2500ms'" for q in c.executed), c.executed
    assert S.DDL_LOCK_TIMEOUT_S == 3.0


# ------------------------------------------------------------ THE TIMEOUT

def test_a_lock_timeout_gives_up_resets_and_leaves_ready_unset_so_it_retries():
    c = _Conn(catalogue=set(), fail_alter=True)
    S._ensure_paper_trades_table(c)
    assert S._paper_trades_table_ready is False, "a deferred DDL must not read as done"
    assert c.executed[-1] == "SET lock_timeout = 0", "the reset must run even on failure"
    assert len(_alters(c)) == 1, "stops at the first failure — no pile-up of queued DDL"
    # next call retries (the flag stayed False), and succeeds once the lock clears
    c2 = _Conn(catalogue=set())
    S._ensure_paper_trades_table(c2)
    assert S._paper_trades_table_ready is True
    assert len(_alters(c2)) == len(S.PAPER_TRADES_COLUMNS)


# ------------------------------------------------------------- FAIL-SAFE

def test_an_unreadable_catalogue_falls_back_to_todays_alter_path():
    """Never worse than before: no catalogue -> every column treated missing."""
    c = _Conn(catalogue=None)
    ok = S._add_columns_if_missing(c, "paper_trades", S.PAPER_TRADES_COLUMNS)
    assert ok is True
    assert len(_alters(c)) == len(S.PAPER_TRADES_COLUMNS)


def test_the_column_lists_match_what_the_functions_used_to_alter():
    """The lists are the ONE owner now; pin their membership so a column can
    neither be silently dropped from the migration nor typed twice."""
    assert [n for n, _t in S.PAPER_TRADES_COLUMNS] == [
        "venue", "shadow", "side", "tag", "entry_price", "exit_price", "size", "extra"]
    assert S.BOT_PNL_COLUMNS == (("pnl_daily", "DOUBLE PRECISION"),)
    assert len({n for n, _ in S.PAPER_TRADES_COLUMNS}) == len(S.PAPER_TRADES_COLUMNS)


# ------------------------------------------------------------ THE WIRING

def test_no_raw_alter_add_column_survives_in_the_store():
    """Every ADD COLUMN goes through the helper; a raw one reintroduces the lock."""
    src = pathlib.Path(S.__file__).read_text()
    raw = [m.group(0) for m in re.finditer(r'cur\.execute\(\s*"ALTER TABLE[^"]*ADD COLUMN', src)]
    assert raw == [], raw


def test_identifiers_never_go_through_an_fstring():
    src = pathlib.Path(S.__file__).read_text()
    body = src.split("def _add_columns_if_missing", 1)[1].split("\ndef ", 1)[0]
    assert 'f"ALTER' not in body and "f'ALTER" not in body
    assert "_sql.Identifier(table)" in body and "_sql.Identifier(name)" in body
