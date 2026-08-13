"""[2026-08-13 (lt)] THE DOCKET'S PUBLISH PATH, ASSERTED ON WHAT IT *WROTE*.

WHY THIS FILE EXISTS — and it is a lesson about TESTS, not about the docket.

`(ld)` pinned the docket's wiring with substring counts. `(lf)` replaced those
with AST claims and called them structural. Neither detected DISABLEMENT.
Measured on this branch before a line was changed — four mutations, each
restoring the exact bug the tests were written for, run against the full
47-test `test_decision_docket.py`:

    | mutation                              | restores                          | (lf) suite |
    |---------------------------------------|-----------------------------------|-----------|
    | `if _seen_ok:` -> `if not _seen_ok:`  | writes the EMPTY map on failure   | **GREEN** |
    | roster docket write -> `if False:`    | the (ld) hole — 📊 invisible      | **GREEN** |
    | checked-read guard -> `and False`     | the (jz) seed class               | **GREEN** |
    | `DOCKET_SEEN_KEY = KEY`               | blanks the ENTIRE grade payload   | **GREEN** |

Deleting those lines IS red. So the suite detected DELETION and not
DISABLEMENT — the `(hh)` dead-code class one abstraction level up from the
substring form it replaced. **An AST assertion that a NAME appears somewhere is
still a presence check**: `UnaryOp(Not, Name('_seen_ok'))` still contains the
name the guard test looked for.

THE ANSWER IS TO STOP ASSERTING ABOUT SOURCE. These tests drive the REAL
`main()` with `--publish` against a fake `bot_pnl_store` and read what it
actually handed to `save_state`. Every one of the four mutations above changes
the writes, so every one is caught here.

The AST tests in `test_decision_docket.py` stay as a cheap second line. They
are no longer the claim.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import golive_readiness as G  # noqa: E402


NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def _closes(bot, n, days_span, mean_pct=0.5):
    """n closed trades for `bot` spread back over `days_span` days."""
    rows = []
    for i in range(n):
        ts = NOW - timedelta(days=days_span * (1 - i / max(n - 1, 1)))
        # Field names are the LEDGER's, not the dashboard's: the grader reads
        # `profit_ratio`/`profit_abs`. A fixture using the publish() names
        # produces a book with n=0 that silently falls below the floor — the
        # (hj) "a consumer tested against a hand-written payload" trap.
        rows.append({
            "bot": bot,
            "pair": "BTC/USDC",
            "profit_ratio": mean_pct / 100.0,
            "profit_abs": mean_pct,
            "open_ts": iso(ts - timedelta(hours=1)),
            "close_ts": iso(ts),
            "trade_id": f"{bot}:{i}",
            "exit_reason": "tp",
            "extra": {},
        })
    return rows


class FakeStore:
    """A `bot_pnl_store` that records every write instead of making it.

    Deliberately NOT a MagicMock: the point of this file is that the payload
    the grader hands to `save_state` is inspected for its real content, and a
    mock that accepts anything would reintroduce exactly the "green on a
    disabled path" property these tests exist to remove.
    """

    def __init__(self, trades=None, pnl_rows=None, prior_seen=None,
                 prior_seen_ok=True, save_ok=True, legacy_seen=None):
        self._trades = trades if trades is not None else []
        self._pnl = pnl_rows if pnl_rows is not None else []
        self._prior_seen = prior_seen
        self._prior_seen_ok = prior_seen_ok
        self._save_ok = save_ok
        self._legacy_seen = legacy_seen
        self.saved = {}          # key -> LAST payload written
        self.save_calls = []     # [(key, payload)] in order
        self.history = []
        self.loads = []

    # --- reads -------------------------------------------------------
    def fetch_paper_trades(self, limit=2000):
        return list(self._trades)

    def fetch_bot_pnl(self):
        return list(self._pnl)

    def fetch_state_history(self, key, limit=800):
        return []

    def load_state_checked(self, bot):
        self.loads.append(bot)
        if bot == G.DOCKET_SEEN_KEY:
            return (self._prior_seen_ok,
                    None if self._prior_seen is None
                    else {"seen": self._prior_seen})
        if bot == G.KEY:
            return (True, None if self._legacy_seen is None
                    else {"docket_seen": self._legacy_seen})
        return (True, None)

    def load_state(self, bot):
        return self.load_state_checked(bot)[1]

    # --- writes ------------------------------------------------------
    def save_state(self, bot, state):
        # round-trips through JSON exactly like the real publisher, so a
        # payload that could not actually be stored fails here too (I5).
        json.dumps(state, allow_nan=False)
        self.saved[bot] = state
        self.save_calls.append((bot, state))
        return self._save_ok

    def save_history(self, key, payload):
        self.history.append((key, payload))
        return True

    def claim_writer(self, bot):
        return (True, "test")


def run_publish(store, argv=("--publish", "--min-closes", "10")):
    """Drive the REAL main() and return the fake store it wrote through."""
    old_argv, old_mod = sys.argv, sys.modules.get("bot_pnl_store")
    sys.argv = ["golive_readiness.py", *argv]
    sys.modules["bot_pnl_store"] = store
    try:
        rc = main_rc = G.main()
        store.rc = main_rc
        return rc
    finally:
        sys.argv = old_argv
        if old_mod is None:
            sys.modules.pop("bot_pnl_store", None)
        else:
            sys.modules["bot_pnl_store"] = old_mod


# A book that is LIVING in bot_pnl and has ZERO ledger rows — the roster
# zero-ledger path, i.e. 📊 equities-regime, the docket's motivating case.
def _living_pnl_row(bot, closed=0):
    return {"bot": bot, "closed_trades": closed, "status": "running",
            "updated_at": NOW, "equity": 1000.0}


@pytest.fixture
def graded_and_zero_ledger():
    """One gradeable book + one living zero-ledger book."""
    trades = _closes("book-graded-lshadow", 40, 60.0, mean_pct=0.1)
    pnl = [_living_pnl_row("book-graded-lshadow", 40),
           _living_pnl_row("equities-regime-lshadow", 0)]
    return trades, pnl


class TestTheGradeAndTheClocksAreSeparateWrites:
    """M4: `DOCKET_SEEN_KEY = KEY` collapses them and blanks the grade."""

    def test_the_grade_payload_carries_books_and_ready(self,
                                                       graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s)
        grade = s.saved.get(G.KEY)
        assert grade is not None, "the grade was never published"
        # These three fields ARE the published contract. If the clocks were
        # written to the same key, the last write wins and all three vanish —
        # the 🚦 card renders empty and fleet_immune's two-writer pager
        # (which reads books.<bot>.integrity) goes blind, on a green build.
        assert "books" in grade, "grade payload lost `books`"
        assert "ready" in grade, "grade payload lost `ready`"
        assert "bar_names" in grade, "grade payload lost `bar_names`"
        assert grade["books"], "grade published an EMPTY books map"

    def test_the_clocks_land_on_their_own_key(self, graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s)
        assert G.DOCKET_SEEN_KEY != G.KEY, \
            "the clocks and the grade must not share a key"
        clocks = s.saved.get(G.DOCKET_SEEN_KEY)
        assert clocks is not None, "the clocks were never written"
        assert "seen" in clocks

    def test_the_grade_is_not_overwritten_by_a_later_write(
            self, graded_and_zero_ledger):
        """The ordering claim, checked on the CALL LOG rather than the map."""
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s)
        writes_to_grade_key = [p for k, p in s.save_calls if k == G.KEY]
        assert len(writes_to_grade_key) == 1, \
            f"the grade key was written {len(writes_to_grade_key)}x"
        assert "books" in writes_to_grade_key[-1]


class TestTheClocksAreWrittenOnlyOnASuccessfulRead:
    """M1: `if _seen_ok:` -> `if not _seen_ok:` writes the empty map."""

    def test_a_failed_prior_read_writes_no_clocks_at_all(
            self, graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl,
                      prior_seen=None, prior_seen_ok=False)
        run_publish(s)
        assert G.DOCKET_SEEN_KEY not in s.saved, (
            "a FAILED read must not rewrite the clocks — persisting the empty "
            "map zeroes every book's clock, the defect the key split exists "
            "to remove")

    def test_a_failed_prior_read_still_publishes_the_grade(
            self, graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl,
                      prior_seen=None, prior_seen_ok=False)
        run_publish(s)
        assert s.saved.get(G.KEY, {}).get("books"), \
            "a clock read failure must cost the CLOCKS, never the GRADE"

    def test_a_failed_read_says_so_and_declares_itself_invalid(
            self, graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl,
                      prior_seen=None, prior_seen_ok=False)
        run_publish(s)
        grade = s.saved[G.KEY]
        assert grade.get("docket_why"), "a degraded docket must say why"
        # An empty docket reads identically to "nothing is overdue". A present
        # POSITIVE field is what lets a consumer tell them apart.
        assert grade.get("docket_valid") is False, \
            "a docket that could not be computed must not claim validity"

    def test_a_successful_read_writes_the_clocks_and_claims_validity(
            self, graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s)
        assert G.DOCKET_SEEN_KEY in s.saved
        assert s.saved[G.KEY].get("docket_valid") is True


class TestTheCheckedReadIsHonoured:
    """M3: `if _ok_prior:` -> `and False` — the (jz) seed class."""

    def test_a_readable_prior_actually_reaches_the_docket(self):
        """A book stuck for longer than DOCKET_DAYS must APPEAR.

        This is the behavioural form of "the prior is actually passed": if
        the read result is ignored, every book looks first-seen today and the
        docket is empty — which is exactly what the disabled path produces.
        """
        trades = _closes("stuck-book-lshadow", 12, 90.0, mean_pct=-0.4)
        pnl = [_living_pnl_row("stuck-book-lshadow", 12)]
        long_ago = iso(NOW - timedelta(days=G.DOCKET_DAYS + 5))
        # Seed the clock for whatever reason the book actually gets, so the
        # test cannot pass merely because a reason string happened to match.
        s0 = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s0)
        seeded = {b: {"reason": v["reason"], "since": long_ago}
                  for b, v in s0.saved[G.DOCKET_SEEN_KEY]["seen"].items()}
        if not seeded:
            pytest.skip("fixture produced no stuck book to seed")
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen=seeded)
        run_publish(s)
        docket = s.saved[G.KEY]["decision_docket"]
        assert docket, ("a book stuck since %s did not reach the docket — the "
                        "prior clocks were not honoured" % long_ago)
        assert all(d["days_held"] >= G.DOCKET_DAYS for d in docket)


class TestTheRosterZeroLedgerBookReachesTheDocket:
    """M2: the roster docket write disabled — the (ld) hole, 📊 invisible."""

    def test_a_living_zero_ledger_book_gets_a_clock(self,
                                                    graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s)
        seen = s.saved[G.DOCKET_SEEN_KEY]["seen"]
        assert "equities-regime-lshadow" in seen, (
            "the zero-ledger roster book fed no clock — this is the (ld) hole "
            "(lf) claimed to close: the docket's own motivating case invisible "
            "to the docket")

    def test_it_dockets_once_the_clock_matures(self, graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s0 = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s0)
        seeded = {b: {"reason": v["reason"],
                      "since": iso(NOW - timedelta(days=G.DOCKET_DAYS + 2))}
                  for b, v in s0.saved[G.DOCKET_SEEN_KEY]["seen"].items()}
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen=seeded)
        run_publish(s)
        books = {d["book"] for d in s.saved[G.KEY]["decision_docket"]}
        assert "equities-regime-lshadow" in books


class TestTheZeroLedgerDiagnosesAreNotCollapsed:
    """(I8) A book the grader CANNOT READ is not a book to retire."""

    def test_no_closes_ever_asks_for_a_keep_or_retire_call(self):
        trades = _closes("book-graded-lshadow", 40, 60.0)
        pnl = [_living_pnl_row("book-graded-lshadow", 40),
               _living_pnl_row("silent-book-lshadow", 0)]
        s0 = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s0)
        seeded = {b: {"reason": v["reason"],
                      "since": iso(NOW - timedelta(days=G.DOCKET_DAYS + 2))}
                  for b, v in s0.saved[G.DOCKET_SEEN_KEY]["seen"].items()}
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen=seeded)
        run_publish(s)
        entry = next(d for d in s.saved[G.KEY]["decision_docket"]
                     if d["book"] == "silent-book-lshadow")
        assert entry["reason"] == "zero_ledger"
        assert "retire" in entry["asks"].lower()

    def test_a_ledger_we_cannot_read_asks_a_DIFFERENT_question(self):
        """`n_alltime > 0` with no ledger rows is a READ problem.

        Telling the operator to retire a book because the grader cannot see
        its trades is the wrong instruction (I8: a detector must name the
        thing the operator can act on).
        """
        trades = _closes("book-graded-lshadow", 40, 60.0)
        pnl = [_living_pnl_row("book-graded-lshadow", 40),
               _living_pnl_row("unreadable-book-lshadow", 137)]
        s0 = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s0)
        seeded = {b: {"reason": v["reason"],
                      "since": iso(NOW - timedelta(days=G.DOCKET_DAYS + 2))}
                  for b, v in s0.saved[G.DOCKET_SEEN_KEY]["seen"].items()}
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen=seeded)
        run_publish(s)
        entry = next(d for d in s.saved[G.KEY]["decision_docket"]
                     if d["book"] == "unreadable-book-lshadow")
        assert entry["reason"] == "ledger_missing", (
            "a book with closes the grader cannot READ was labelled the same "
            "as a book that has never traded")
        # Identity against the I17 default, not a substring hunt: the ask
        # legitimately contains the word "retire" while DENYING it.
        assert entry["asks"] != G.DOCKET_ASKS[None], \
            "the ask for an unreadable ledger must not be keep-or-retire"


class TestTheClockMigration:
    """(lf) moved the clocks and read only the new key — a silent restart."""

    def test_the_old_location_is_read_when_the_new_key_is_empty(self):
        trades = _closes("stuck-book-lshadow", 12, 90.0, mean_pct=-0.4)
        pnl = [_living_pnl_row("stuck-book-lshadow", 12)]
        s0 = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={})
        run_publish(s0)
        legacy = {b: {"reason": v["reason"],
                      "since": iso(NOW - timedelta(days=G.DOCKET_DAYS + 3))}
                  for b, v in s0.saved[G.DOCKET_SEEN_KEY]["seen"].items()}
        if not legacy:
            pytest.skip("fixture produced no stuck book to seed")
        # New key MISSING (not failed) + clocks still at the old location.
        s = FakeStore(trades=trades, pnl_rows=pnl,
                      prior_seen=None, prior_seen_ok=True, legacy_seen=legacy)
        run_publish(s)
        grade = s.saved[G.KEY]
        assert grade["decision_docket"], (
            "the pre-(lf) clocks were discarded — 14 clocks restamped at "
            "deploy time read exactly like 'the fleet became stuck today'")
        assert "migrat" in (grade.get("docket_why") or "").lower(), \
            "a migration must SAY it migrated"

    def test_a_genuinely_new_key_does_not_invent_a_migration(self):
        trades = _closes("stuck-book-lshadow", 12, 90.0, mean_pct=-0.4)
        pnl = [_living_pnl_row("stuck-book-lshadow", 12)]
        s = FakeStore(trades=trades, pnl_rows=pnl,
                      prior_seen=None, prior_seen_ok=True, legacy_seen=None)
        run_publish(s)
        grade = s.saved[G.KEY]
        assert grade.get("docket_valid") is True
        assert not grade["decision_docket"], \
            "with no prior clocks anywhere, nobody is overdue yet"


class TestTheClockWriteResultIsNotDiscarded:
    """(I4) A persistence call's return value is load-bearing."""

    def test_a_failed_clock_write_is_reported_not_swallowed(
            self, graded_and_zero_ledger):
        trades, pnl = graded_and_zero_ledger
        s = FakeStore(trades=trades, pnl_rows=pnl, prior_seen={},
                      save_ok=False)
        run_publish(s)
        grade = s.saved[G.KEY]
        # The payload advertised clocks that were never stored — the exact
        # shape (lf)'s own still-open list flagged, shipped one function away
        # from where it was written down.
        assert grade.get("docket_valid") is False, (
            "the clocks failed to persist and the payload still claimed a "
            "valid docket")
        assert "persist" in (grade.get("docket_why") or "").lower()
