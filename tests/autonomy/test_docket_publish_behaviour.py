"""[(lj)] BEHAVIOURAL tests for the decision docket's publish path.

WHY THIS FILE EXISTS, and it is the whole point of it: `(ld)` pinned the
docket's wiring with SUBSTRING COUNTS and two mutations walked straight
through. `(lf)` replaced them with AST claims and called them structural. Both
detect DELETION and not DISABLEMENT — an AST assertion that a NAME appears
somewhere is still a presence check, and `UnaryOp(Not, Name('_seen_ok'))`
contains every string a guard over `_seen_ok` looks for. So `if _seen_ok:` can
be flipped to `if not _seen_ok:`, restoring the exact bug the test was written
for, and the suite stays green.

THE ANSWER IS TO STOP ASSERTING ABOUT SOURCE. These tests drive the REAL
`main(--publish)` against a fake `bot_pnl_store` and read WHAT IT ACTUALLY
WROTE. Every mutation that changes the writes is caught, whatever it does to
the source text.

`(lh)` diagnosed all of the above correctly and shipped NONE of it — the entry
described this file, `docket_valid`, the I4 clock-read, the key migration and
the `ledger_missing` split as done, and the tree contained no line of it (the
entry was written into CHANGELOG.md by the `(li)` commit, which touched only
the brain). This file is that deliverable, actually committed.

The mutations these tests are built to redden, each restoring a real prior bug:
  M1  `if _seen_ok:` -> `if not _seen_ok:`  (writes the empty map on failure)
  M2  the roster docket write -> `if False:` (the (ld) hole: equities-regime
      invisible to the docket that exists for it)
  M3  the checked-read guard -> `and False`  (the (jz) seed class)
  M4  `DOCKET_SEEN_KEY = KEY`               (blanks the ENTIRE grade payload)
  M5  the clock write's result discarded    (I4: clocks advertised, never stored)
"""
import importlib
import sys
import types

import pytest

pytestmark = pytest.mark.autonomy

GR = importlib.import_module("scripts.golive_readiness") \
    if "scripts.golive_readiness" in sys.modules else None
if GR is None:                                   # normal path
    import scripts.golive_readiness as GR        # noqa: E402


class FakeStore:
    """A stand-in for bot_pnl_store that RECORDS every write.

    Deliberately not a Mock: the assertions below are about the payloads that
    reach `save_state`, so the writes must be inspectable as plain data.
    """

    def __init__(self, rows=None, pnl_rows=None, state=None,
                 read_ok=True, save_ok=True, fail_keys=()):
        self.rows = rows or []
        self.pnl_rows = pnl_rows or []
        self.state = dict(state or {})
        self.read_ok = read_ok
        self.save_ok = save_ok
        self.fail_keys = set(fail_keys)
        self.writes = []            # [(key, payload)] in call order
        self.history = []

    # --- reads -----------------------------------------------------------
    def fetch_paper_trades(self, limit=None):
        return list(self.rows)

    def fetch_bot_pnl(self):
        return list(self.pnl_rows)

    def load_state(self, key):
        return self.state.get(key)

    def load_state_checked(self, key):
        if not self.read_ok:
            return False, None
        return True, self.state.get(key)

    def fetch_state_history(self, key, limit=None):
        return []

    # --- writes ----------------------------------------------------------
    def save_state(self, key, payload):
        self.writes.append((key, payload))
        if key in self.fail_keys or not self.save_ok:
            return False
        self.state[key] = payload
        return True

    def save_history(self, key, payload):
        self.history.append((key, payload))
        return True

    # --- helpers for the assertions --------------------------------------
    def written(self, key):
        """The LAST payload written to `key`, or None if never written."""
        for k, p in reversed(self.writes):
            if k == key:
                return p
        return None

    def write_keys(self):
        return [k for k, _ in self.writes]


def run_publish(store, argv=("--publish", "--min-closes", "1")):
    """Drive the REAL main() with `store` injected, and return it."""
    real_mod = sys.modules.get("bot_pnl_store")
    real_argv = sys.argv
    shim = types.ModuleType("bot_pnl_store")
    for name in ("fetch_paper_trades", "fetch_bot_pnl", "load_state",
                 "load_state_checked", "fetch_state_history", "save_state",
                 "save_history"):
        setattr(shim, name, getattr(store, name))
    sys.modules["bot_pnl_store"] = shim
    sys.argv = ["golive_readiness.py", *argv]
    try:
        GR.main()
    finally:
        sys.argv = real_argv
        if real_mod is None:
            sys.modules.pop("bot_pnl_store", None)
        else:
            sys.modules["bot_pnl_store"] = real_mod
    return store


def _pnl_row(bot, closed=0, updated=None):
    from datetime import datetime, timezone
    return {"bot": bot, "closed_trades": closed,
            "updated_at": updated or datetime.now(timezone.utc)}


def _ledger(bot="graded-lshadow", n=12, days=40):
    """A minimal but REAL-SHAPED paper_trades ledger for one graded book.

    The (kd) degraded-read guard refuses to publish over ZERO ledger rows —
    correctly, since an empty fetch is an auth/connection failure and not a
    legitimate fleet state. So every case here supplies a real ledger and puts
    the book under test in `pnl_rows` (the roster sweep) alongside it.
    """
    from datetime import datetime, timedelta, timezone
    t0 = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for i in range(n):
        close = t0 + timedelta(days=i * (days - 1) / max(n - 1, 1))
        out.append({"bot": bot, "pair": "BTC/USDC",
                    "profit_abs": 1.0, "profit_ratio": 0.01,
                    "enter_tag": "long", "exit_reason": "tp",
                    "duration_min": 60.0,
                    "open_ts": close - timedelta(hours=1), "close_ts": close,
                    "is_open": False, "venue": "lighter",
                    "open_rate": 100.0, "close_rate": 101.0, "extra": {}})
    return out


# ---------------------------------------------------------------------------
# M4 — the two keys must differ, and the grade payload must survive a publish
# ---------------------------------------------------------------------------

def test_the_grade_payload_is_not_replaced_by_the_clock_payload():
    """M4: `DOCKET_SEEN_KEY = KEY` blanks the grade on every publish.

    save_state replaces a payload WHOLESALE, so sharing the key means the
    clock write ({updated, ttl_sec, seen}) lands on top of the grade — no
    `books`, no `ready`. The 🚦 card renders empty and fleet_immune's
    two-writer pager (which reads books.<bot>.integrity) goes blind, all on a
    green build. Asserted on the WRITTEN payload, not on the source.
    """
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("a-lshadow")]))
    grade = s.written(GR.KEY)
    assert grade is not None, "the grade was never published"
    assert "books" in grade and "ready" in grade and "bar_names" in grade, (
        "the grade payload was overwritten by the clock payload: " +
        repr(sorted(grade)))


def test_the_clock_key_and_the_grade_key_are_distinct_keys():
    assert GR.DOCKET_SEEN_KEY != GR.KEY


# ---------------------------------------------------------------------------
# M1/M3 — a FAILED read must not rewrite the clocks
# ---------------------------------------------------------------------------

def test_a_failed_clock_read_never_writes_the_clock_key():
    """M1 + M3. On a read failure the clocks must be left ALONE.

    The bug this catches: writing the empty `_seen` map over a real one. One
    Postgres blip in any of the ~112 publishes a book needs to reach
    DOCKET_DAYS would reset every clock to zero, leaving an organ whose entire
    job is to say a decision is overdue structurally unable to ever say it.
    """
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("a-lshadow")], read_ok=False))
    assert GR.DOCKET_SEEN_KEY not in s.write_keys(), (
        "the clocks were rewritten after a FAILED read: " + repr(s.write_keys()))
    assert s.written(GR.KEY) is not None, "the grade must publish anyway"


def test_a_failed_clock_read_is_reported_as_invalid_not_as_empty():
    """An empty docket is a CLAIM. `docket_valid` must say it is not one."""
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("a-lshadow")], read_ok=False))
    grade = s.written(GR.KEY)
    assert grade["docket_valid"] is False
    assert grade["decision_docket"] == []
    assert grade.get("docket_why"), "a failed read must explain itself"


def test_a_successful_read_does_write_the_clocks_and_is_valid():
    """The positive control. Without it, a guard that never writes passes
    every test above — the assertion that holds on an empty result."""
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("a-lshadow")]))
    assert GR.DOCKET_SEEN_KEY in s.write_keys()
    assert s.written(GR.KEY)["docket_valid"] is True


# ---------------------------------------------------------------------------
# M5 — I4: the clock write's result must be READ
# ---------------------------------------------------------------------------

def test_a_failed_clock_write_is_not_reported_as_a_valid_docket():
    """M5. The write result was DISCARDED, so the payload advertised clocks
    that were never stored.

    The damage is specific: a book already in the map keeps its older `since`
    and reads fine, but a NEWLY stuck book never gets its clock started, so it
    can never accrue DOCKET_DAYS and the docket cannot ever name it.
    """
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("a-lshadow")],
                              fail_keys={GR.DOCKET_SEEN_KEY}))
    grade = s.written(GR.KEY)
    assert grade["docket_valid"] is False, (
        "a clock write that FAILED was reported as a valid docket")
    assert "clock write FAILED" in (grade.get("docket_why") or "")


def test_the_grade_still_publishes_when_the_clock_write_fails():
    """Fail-safe direction: the clocks are not allowed to cost the grade."""
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("a-lshadow")],
                              fail_keys={GR.DOCKET_SEEN_KEY}))
    assert s.written(GR.KEY) is not None
    assert "books" in s.written(GR.KEY)


# ---------------------------------------------------------------------------
# M2 — the roster sweep must feed the docket
# ---------------------------------------------------------------------------

def test_a_zero_ledger_roster_book_reaches_the_docket_clock():
    """M2, and it is the docket's own motivating case.

    📊 equities-regime has zero closes ever and enters the payload ONLY via
    the (kv) roster sweep. (ld) claimed below-floor books were in the docket;
    they were not, because that loop did not write `_docket_now`. A zero-ledger
    book also has NO era, so the `no_rate` arm could never fire for it either.
    """
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("equities-regime-lshadow")]))
    seen = s.written(GR.DOCKET_SEEN_KEY)["seen"]
    assert "equities-regime-lshadow" in seen, (
        "the roster sweep did not feed the docket: " + repr(seen))
    assert seen["equities-regime-lshadow"]["reason"] == "zero_ledger"


def test_a_roster_book_is_also_in_the_published_below_floor_map():
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("equities-regime-lshadow")]))
    assert "equities-regime-lshadow" in s.written(GR.KEY)["below_floor"]


# ---------------------------------------------------------------------------
# I8 — `ledger_missing` is a READ failure, not a retirement case
# ---------------------------------------------------------------------------

def test_a_book_whose_ledger_cannot_be_read_is_not_docketed_for_retirement():
    """A book with a non-zero bot_pnl close count and no ledger rows is a
    grader READ problem. Telling the operator to retire it names the wrong
    object (I8) and would destroy a working book on a fetch failure."""
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("busy-lshadow", closed=250)]))
    seen = s.written(GR.DOCKET_SEEN_KEY)["seen"]
    assert seen["busy-lshadow"]["reason"] == "ledger_missing"
    asks = GR.DOCKET_ASKS["ledger_missing"]
    assert "NOT a retirement case" in asks
    assert asks != GR.DOCKET_ASKS["_default"]


def test_a_genuinely_empty_book_keeps_the_i17_retirement_ask():
    """The control group for the test above: the split must not have turned
    every roster book into a read problem."""
    s = run_publish(FakeStore(rows=_ledger(), pnl_rows=[_pnl_row("silent-lshadow", closed=0)]))
    seen = s.written(GR.DOCKET_SEEN_KEY)["seen"]
    assert seen["silent-lshadow"]["reason"] == "zero_ledger"
    assert "keep-or-retire" in GR.DOCKET_ASKS["_default"]


# ---------------------------------------------------------------------------
# The migration — clocks must not silently restart on the (lf) key move
# ---------------------------------------------------------------------------

def test_clocks_are_carried_over_from_the_pre_split_location_once():
    """`load_state_checked` returns (True, None) for a MISSING row, so the
    first run after the (lf) key move read an EMPTY prior as a SUCCESSFUL one:
    every `since` restamped to now. 14 clocks all stamped at deploy time read
    exactly like "the fleet became stuck today" — an unknown wearing the
    costume of a verdict."""
    old_since = "2026-07-01T00:00:00+00:00"
    s = FakeStore(
        rows=_ledger(),
        pnl_rows=[_pnl_row("equities-regime-lshadow")],
        state={GR.KEY: {"docket_seen": {
            "equities-regime-lshadow": {"reason": "zero_ledger",
                                        "since": old_since}}}})
    run_publish(s)
    grade = s.written(GR.KEY)
    assert grade["docket_seen"]["equities-regime-lshadow"]["since"] == old_since, (
        "the migration did not carry the clock: it restarted at now")
    assert "migrated" in (grade.get("docket_why") or ""), (
        "a migrated run must SAY it migrated, or a reader cannot tell it "
        "from a genuinely fresh one")
    # and having been carried, the book is old enough to actually docket
    assert [d["book"] for d in grade["decision_docket"]] == \
        ["equities-regime-lshadow"]


def test_the_migration_does_not_fire_when_the_new_key_already_has_clocks():
    """It is a ONE-TIME fallback. If it re-read the old location every run it
    would resurrect clocks the new key had deliberately reset."""
    s = FakeStore(
        rows=_ledger(),
        pnl_rows=[_pnl_row("equities-regime-lshadow")],
        state={GR.KEY: {"docket_seen": {
                   "equities-regime-lshadow": {"reason": "zero_ledger",
                                               "since": "2026-07-01T00:00:00+00:00"}}},
               GR.DOCKET_SEEN_KEY: {"seen": {
                   "equities-regime-lshadow": {"reason": "zero_ledger",
                                               "since": "2026-08-05T00:00:00+00:00"}}}})
    run_publish(s)
    grade = s.written(GR.KEY)
    assert grade["docket_seen"]["equities-regime-lshadow"]["since"] == \
        "2026-08-05T00:00:00+00:00"
    assert "migrated" not in (grade.get("docket_why") or "")
