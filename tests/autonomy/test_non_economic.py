"""EVENTS ARE NOT TRADES — the (tw) owner and the aggregate that consumes it.

🙏 avo published 3W/**10L** over 13 "closes" on a book that had taken 4 real
trades (3W/1L); 🔮 georgia 24W/28L against a real 24W/24L. Nine and four of
those rows were daily-loss FLATTEN EVENTS: no entry basis, no P&L, counted as
closes and — via `losses = closed - wins` — as losses.

The distinction is NOT the reason string. `daily_loss` appears on both: her
25-Aug rail closed five REAL positions at real prices for -$30.96, and those
are losses the book genuinely took.
"""
import bot_pnl_store as store
from bot_pnl_store import is_non_economic


# ------------------------------------------------- the event signature
def test_a_flatten_event_with_no_basis_is_not_a_trade():
    assert is_non_economic(0.0, None, {}) is True


def test_the_th_marker_alone_is_enough():
    """The forward CONTRACT: a marked row needs no signature match."""
    assert is_non_economic(0.0, None, {"non_economic": True}) is True


# ------------------------------- what must NEVER be classified as an event
def test_georgias_real_forced_flatten_losses_stay_in_the_sample():
    """Her 25-Aug rail closed five REAL positions. Reason strings collide
    (`daily_loss` on both); the BASIS is what separates them."""
    for pnl, entry in ((-3.04, 2500.05), (-8.42, 1.518757), (-6.64, 11.78749),
                       (-3.20, 7.6169), (-9.66, 1.97479), (-3.87, 0.3509)):
        assert is_non_economic(pnl, entry, {}) is False, \
            f"real forced-flatten loss {pnl} misread as an event"


def test_the_lit_trade_that_the_none_collision_nearly_destroyed():
    """-$0.84, entry 3.6604, unknown open — a real trade, not an event."""
    assert is_non_economic(-0.84, 3.6604, {}) is False


def test_a_funding_row_books_accrual_not_a_price():
    """Funding books legitimately record NO price. They are the population a
    naive signature would have eaten — measured: carry 0 of 105 zero-P&L
    rows, farmer-shadow 0 of 215, garrett 0 of 56, so the conjunction cannot
    fire on them today. `_FUNDING_FORM` makes that structural, not lucky."""
    for key in ("entry_apr", "exit_apr", "accrued", "held_h", "fees"):
        assert is_non_economic(0.0, None, {key: 0.3}) is False, \
            f"a funding row carrying {key} is a TRADE"


def test_a_zero_pnl_trade_with_a_price_is_still_a_trade():
    assert is_non_economic(0.0, 100.0, {}) is False


# ------------------------------------------------------------ fail-OPEN
def test_an_UNKNOWN_pnl_is_not_a_zero_pnl():
    """The mutation round caught this: the first draft wrote
    `float(pnl_abs or 0.0)`, which coerces a MISSING P&L to zero and so
    reads an unknown-P&L row as an event — the exact "fabricate what you do
    not know" class this owner exists to close, reproduced inside it.

    The extra here is a VALID empty dict on purpose: the earlier test reached
    `False` through the unreadable-extra path instead, so it looked like
    cover and was not (M1 survived)."""
    assert is_non_economic(None, None, {}) is False


def test_unparseable_rows_are_ADMITTED_never_swallowed():
    """`is_quarantined`'s contract verbatim: a filter that swallows what it
    cannot read silently shrinks every sample it touches."""
    assert is_non_economic("junk", None, None) is False
    assert is_non_economic(None, None, "not-a-dict") is False
    assert is_non_economic(0.0, None, ["list"]) is False


# ------------------------------------------- the aggregate actually uses it
def test_the_aggregate_subtracts_events_from_closed_but_not_from_realized():
    """An event's P&L is 0.00, so equity cannot move — only the COUNTS.
    Driven against the real function with a stubbed cursor rather than a
    hand-written fixture ((hj): test the consumer against a real shape)."""
    calls = []

    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def execute(self, sql, args=None):
            calls.append(sql)
            self._sql = sql

        def fetchone(self):
            # (realized, closed, wins, candidates) — the REAL query shape:
            # 15 rows, 6 real, 9 candidates. The 4th column gates the second
            # round trip so a clean book pays only one.
            return (5.24, 15, 3, 9)

        def fetchall(self):
            if "non_economic" in self._sql:
                # 9 candidate rows, all events
                return [(0.0, None, {}) for _ in range(9)]
            return []

    class _Conn:
        def cursor(self): return _Cur()

    real_get = store._get_conn
    real_ensure = store._ensure_paper_trades_table
    try:
        store._get_conn = lambda: _Conn()
        store._ensure_paper_trades_table = lambda c: None
        agg = store.fetch_paper_aggregate("freqtrade-avo-maria-lighter")
    finally:
        store._get_conn = real_get
        store._ensure_paper_trades_table = real_ensure

    assert agg["closed"] == 6, f"9 events must leave 6 closes, got {agg}"
    assert agg["wins"] == 3
    assert agg["losses"] == 3, "3W of 6 leaves 3L, not 10L"
    assert abs(agg["realized"] - 5.24) < 1e-9, \
        "realized must NOT move — an event's P&L is 0.00"


def test_the_aggregate_never_returns_negative_counters():
    """max(0, ...) survives: a pathological filter must not invent -1 closes."""
    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, args=None): self._sql = sql
        def fetchone(self): return (0.0, 2, 0, 5)
        def fetchall(self):
            if "non_economic" in self._sql:
                return [(0.0, None, {}) for _ in range(5)]   # more than exist
            return []

    class _Conn:
        def cursor(self): return _Cur()

    real_get, real_ensure = store._get_conn, store._ensure_paper_trades_table
    try:
        store._get_conn = lambda: _Conn()
        store._ensure_paper_trades_table = lambda c: None
        agg = store.fetch_paper_aggregate("x")
    finally:
        store._get_conn, store._ensure_paper_trades_table = real_get, real_ensure
    assert agg["closed"] >= 0 and agg["losses"] >= 0, agg
