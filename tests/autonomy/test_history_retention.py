"""[2026-08-02] THE RETENTION PRUNE THAT HAD NEVER ONCE RUN.

`bot_state_history` is the fleet's durable time series — the MTM equity samples
`(hl)` started collecting for the drawdown re-grade live there, along with the
replay tape and the regen organ's last-good snapshots. `prune_history` is its
only retention, added 16-Jul because the table "bloated indefinitely".

It raised on EVERY call for seventeen days:

    function make_interval(days => numeric) does not exist

`make_interval(days => %s)` takes an **integer**; `days` is built with
`float(...)`, so psycopg2 bound a `numeric` and Postgres found no matching
function. The exception was swallowed by a bare `except`, reported by
`_warn_once` — a single line per process — and the caller discards the `None`
return. That is `(I4)` exactly: a persistent condition announced by a one-shot
warning, behind a return value nobody reads.

HOW IT WAS FOUND: reading a container's logs during the daily review, not by a
test. No test ever ran this function against a real Postgres, and no test could
have — which is why the arms below pin the STATEMENT and the BIND instead,
because those are the two things that were wrong.

VERIFIED against the live Postgres the day it was fixed, both directions:
`select now() - make_interval(days => 60.0)` fails with exactly the logged
message, `select now() - (60.0 * interval '1 day')` resolves, and the
multiplication idiom additionally supports FRACTIONAL retention, which
`make_interval` could never express.

IMPACT, stated honestly: zero rows to date. The table spanned 26 days against
a 60-day policy when this was fixed, so the prune had nothing to delete yet and
would first have mattered around 5-Sep. A bug fixed before it could cost
anything is still a bug that ran broken for seventeen days announcing itself.
"""
import ast
import inspect
import textwrap

import bot_pnl_store as store


def test_prune_sql_cannot_use_the_integer_only_idiom():
    """make_interval(days=>) demands an INTEGER and this function sends a float."""
    assert "make_interval" not in store.HISTORY_PRUNE_SQL
    assert "interval '1 day'" in store.HISTORY_PRUNE_SQL


def test_the_broken_idiom_cannot_return_via_an_inline_query():
    """A named constant is only a guard if the function actually runs it.

    SCAN THE CODE, NOT THE PROSE. The first cut of this asserted `"make_interval"
    not in inspect.getsource(...)` and failed on the docstring that EXPLAINS the
    fix — the exact trap CLAUDE.md records ("a page-wide substring scan is not a
    structural claim"; three tests in one session failed on the very sentence
    promising the property they checked). The docstring must be free to name the
    defect; only the executable body may not contain it.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(store.prune_history)))
    fn = tree.body[0]
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    code = "\n".join(ast.dump(n) for n in body)
    assert "make_interval" not in code, "the broken idiom is back in the body"
    assert "HISTORY_PRUNE_SQL" in code, "the function must run the constant"


class _FakeCur:
    def __init__(self):
        self.sql = self.args = None
        self.rowcount = 7

    def execute(self, sql, args=None):
        self.sql, self.args = sql, args

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCur()

    def cursor(self):
        return self.cur


def _run(monkeypatch, keep_days):
    monkeypatch.setattr(store, "_ensure_history_table", lambda _c: None)
    conn = _FakeConn()
    rows = store.prune_history(conn, keep_days=keep_days)
    return rows, conn.cur


def test_prune_runs_the_reviewed_statement_not_a_private_copy(monkeypatch):
    rows, cur = _run(monkeypatch, 30.0)
    assert rows == 7
    assert cur.sql is store.HISTORY_PRUNE_SQL


def test_the_bind_stays_a_float(monkeypatch):
    """The half of the bug a SQL-string check cannot see.

    An INTEGER bind would have worked under the old idiom too, so a test that
    only inspected the statement could pass while the real defect — a numeric
    parameter meeting an integer-only function — walked straight back in.
    """
    _rows, cur = _run(monkeypatch, 0.5)
    assert isinstance(cur.args[0], float)
    assert cur.args[0] == 0.5, "fractional retention must survive the fix"


def test_prune_never_raises_and_reports_failure_as_none(monkeypatch):
    """Retention is maintenance: it must never take a trading loop down.

    This is also why the original defect was invisible for so long, so the
    behaviour is pinned deliberately rather than tightened.
    """
    class _Boom:
        def cursor(self):
            raise RuntimeError("no db")

    monkeypatch.setattr(store, "_ensure_history_table", lambda _c: None)
    assert store.prune_history(_Boom(), keep_days=1.0) is None


def test_a_missing_connection_is_not_an_error(monkeypatch):
    monkeypatch.setattr(store, "_get_conn", lambda: None)
    assert store.prune_history(None) is None
