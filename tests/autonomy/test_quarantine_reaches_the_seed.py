"""[2026-08-19 fleet audit] The quarantine must reach the SEED path, and a
book whose state could not be read must not publish a fabricated one.

Two findings from the 19-Aug fleet-wide audit, both the same shape: an
instrument that answers a question CORRECTLY on one path and wrongly on
another, where nothing made the two agree.

1. `bot_pnl_store.fetch_paper_aggregate` — the totals a book re-reads at boot
   to recover from a local-file wipe — was raw SQL with no LEDGER_QUARANTINE
   filter, while `fetch_paper_trades` (every grading consumer) withholds those
   rows. 🧘 douglas therefore re-seeded the two (nm)/(pv) void rows on every
   reboot and published pnl_abs -$24.68 / 8 closes against a graded record of
   +$1.81 / 6 closes.

2. `parliament.strategies.Book.publish` published the FRESH-BOOK constructor
   state (equity $1000.00, closed 0) whenever `restore()` had failed, while
   `save()` has refused in exactly that case since the 21-Jul audit fix — and
   `snapshot_equity` wrote the fabricated number into the MTM series the (ia)
   worse-of-both drawdown bar reads. Measured: pm-albanese's 0.18% published
   MTM drawdown is (1001.84-1000.00)/1001.84 = 0.1838%, the flicker exactly.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# 1. the seed path honours the quarantine — behaviourally, against fakes
# --------------------------------------------------------------------------
class _Cur:
    def __init__(self, outer):
        self.outer = outer

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.outer.sql.append((" ".join(str(sql).split()), params))

    def fetchone(self):
        return self.outer.agg

    def fetchall(self):
        return self.outer.rows


class _Conn:
    def __init__(self, agg, rows):
        self.agg, self.rows, self.sql = agg, rows, []

    def cursor(self):
        return _Cur(self)


@pytest.fixture()
def store(monkeypatch):
    import bot_pnl_store as s
    monkeypatch.setattr(s, "_ensure_paper_trades_table", lambda conn: None)
    return s


def _run(store, monkeypatch, bot, agg, rows):
    conn = _Conn(agg, rows)
    monkeypatch.setattr(store, "_get_conn", lambda: conn)
    return store.fetch_paper_aggregate(bot), conn


def test_the_seed_withholds_exactly_the_quarantined_rows(store, monkeypatch):
    """douglas's real numbers: 8 closes / -$24.68 raw, 6 / +$1.81 admissible.

    The two void rows are ROBO and LINK on 2026-08-15, both losers, so the
    win count must NOT move — only closed, losses and realized.
    """
    agg = (-24.68, 8, 4)
    rows = [("ROBO", "2026-08-15 13:35:41+00:00", -23.16),
            ("LINK", "2026-08-15 13:35:41+00:00", -3.31)]
    out, _ = _run(store, monkeypatch, "book-douglas-lshadow", agg, rows)
    assert out["closed"] == 6, out
    assert out["wins"] == 4 and out["losses"] == 2, out
    assert round(out["realized"], 2) == 1.79, out["realized"]


def test_a_row_outside_the_declared_window_is_still_counted(store, monkeypatch):
    """The quarantine is a bounded window, not a pair-wide ban — a later
    ROBO trade on the FIXED build is the book's record and must survive."""
    agg = (-24.68, 8, 4)
    rows = [("ROBO", "2026-08-15 13:35:41+00:00", -23.16),
            ("ROBO", "2026-08-17 09:00:00+00:00", -1.50)]
    out, _ = _run(store, monkeypatch, "book-douglas-lshadow", agg, rows)
    assert out["closed"] == 7, "only the in-window row is withheld"
    assert round(out["realized"], 2) == -1.52, out["realized"]


def test_a_clean_book_is_untouched_and_asks_no_second_query(store, monkeypatch):
    """A detector that fires on everything trains the operator to ignore it —
    and a book with no quarantine entry must not pay for a second round trip."""
    out, conn = _run(store, monkeypatch, "perps-funding-carry-lshadow",
                     (66.21, 101, 43), [])
    assert out == {"realized": 66.21, "closed": 101, "wins": 43, "losses": 58}
    assert len(conn.sql) == 1, [s for s, _ in conn.sql]


def test_the_filter_never_breaks_the_recovery_it_refines(store, monkeypatch):
    """Fail-OPEN: the seed's job is surviving a local-file wipe, so a broken
    withholding pass returns the unfiltered total rather than None."""
    class _Boom(_Conn):
        def cursor(self):
            if self.sql:
                raise RuntimeError("second query exploded")
            return _Cur(self)

    conn = _Boom((-24.68, 8, 4), [])
    monkeypatch.setattr(store, "_get_conn", lambda: conn)
    out = store.fetch_paper_aggregate("book-douglas-lshadow")
    assert out is not None and out["closed"] == 8, out


def test_is_quarantined_stays_the_one_owner(store):
    """(hj): a second copy of a rule is a second rule. The seed path may
    pre-filter on `pair` for cost, but the VERDICT must come from the shared
    predicate — so the function must call it by name."""
    src = (ROOT / "bot_pnl_store.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_paper_aggregate")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "is_quarantined" in calls, sorted(calls)


# --------------------------------------------------------------------------
# 2. parliament: no publish from a book whose state could not be read
# --------------------------------------------------------------------------
def _publish_fn():
    src = (ROOT / "parliament" / "strategies.py").read_text()
    for cls in ast.walk(ast.parse(src)):
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name == "publish":
                return fn
    raise AssertionError("no publish method found")


def test_publish_refuses_before_restore_completes():
    """The guard must sit AHEAD of every write in publish() — the equity
    snapshot is the one that poisons the (ia) drawdown bar, so a guard placed
    after the store.publish call would still leave the artifact behind."""
    fn = _publish_fn()
    guard_line = None
    for node in fn.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp)
                and isinstance(node.test.op, ast.Not)
                and isinstance(node.test.operand, ast.Attribute)
                and node.test.operand.attr == "_restored"
                and any(isinstance(b, ast.Return) for b in node.body)):
            guard_line = node.lineno
            break
    assert guard_line is not None, "publish() must return early when not _restored"

    writes = [c.lineno for c in ast.walk(fn)
              if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
              and c.func.attr in ("publish", "snapshot_equity")]
    assert writes, "expected publish()/snapshot_equity call sites"
    assert min(writes) > guard_line, (
        f"guard at {guard_line} must precede every write {sorted(writes)}")


def test_save_and_publish_agree_about_unread_state():
    """The defect was an ASYMMETRY: save() refused and publish() did not.
    Pin both, so restoring one without the other cannot pass."""
    src = (ROOT / "parliament" / "strategies.py").read_text()
    tree = ast.parse(src)
    found = {}
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name in ("save", "publish"):
                found[fn.name] = any(
                    isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp)
                    and isinstance(n.test.operand, ast.Attribute)
                    and n.test.operand.attr == "_restored"
                    for n in ast.walk(fn))
    assert found.get("save") and found.get("publish"), found
