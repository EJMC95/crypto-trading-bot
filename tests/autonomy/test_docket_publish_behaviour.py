"""[2026-08-06 (lh)] The docket's PUBLISH PATH, driven end to end.

WHY THIS FILE EXISTS, and it is the most useful thing in today's whole sequence.
`(ld)` pinned its wiring with substring counts; two mutations walked through.
`(lf)` replaced them with AST claims and reported them structural. An adversarial
pass then showed **the AST claims survive the mutations that restore the exact
bugs they were written for**:

  * inverting the write guard to `if not _seen_ok:` — 47/47 GREEN
    (the assertion looked for the NAME `_seen_ok` in the test's dump, and
    `UnaryOp(Not, Name('_seen_ok'))` contains it);
  * making the roster docket write unreachable with `if False:` — GREEN
    (the marquee "a fourth path cannot arrive quietly" test);
  * neutering the checked-read guard with `and False` — GREEN;
  * `DOCKET_SEEN_KEY = KEY`, which blanks the entire grade payload — GREEN.

Deleting those lines IS red. So the suite detected DELETION and not
DISABLEMENT — the same `(hh)` dead-code class, one abstraction level up from
the substring form it replaced. An AST assertion that a NAME appears somewhere
is still a presence check.

The answer is to stop asserting about the source and drive the real `main()`
publish block against a fake store, then read what it actually wrote. Every
mutation above changes the WRITES, so every one of them reddens here.
"""
import datetime as _dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import golive_readiness as g  # noqa: E402
import bot_pnl_store as store  # noqa: E402


BOOK = "lighter-perp-sniper-lshadow"  # a real unreachable book
# [(nf) 15-Aug] WAS pm-gillard-lshadow — retired in the red-stop slate,
# so the roster stops admitting it: the exact green-alone/red-together
# signature this file already documents from (lu). Swapped to the one
# unreachable book the slate deliberately KEPT (screens landed).
# [(lu)] WAS `equities-regime-lshadow`, and (lo) RETIRED that book on 13-Aug —
# into RETIRED_ROWS and LEGACY_BOTS — so the roster sweep correctly stops
# admitting it and this fixture could never pass again. The signature was the
# one CLAUDE.md names: green on HEAD, green with these changes alone, red in
# combination. Replaced with a LIVING zero-ledger book (born 13-Aug (ls), n=0,
# publishing) so the case under test still exists in the fleet.
ZERO = "book-kiyosaki-lshadow"       # the zero-ledger I17 case


class FakeStore:
    """Records every write; serves whatever prior state the test seeds."""

    def __init__(self, state=None, read_ok=True, write_ok=True):
        self.state = dict(state or {})
        self.read_ok = read_ok
        self.write_ok = write_ok
        self.writes = []

    def load_state_checked(self, key):
        if not self.read_ok:
            return False, None
        return True, self.state.get(key)

    def load_state(self, key):
        return self.state.get(key) if self.read_ok else None

    def save_state(self, key, payload):
        self.writes.append((key, payload))
        self.state[key] = payload
        return self.write_ok

    def save_history(self, key, payload):
        return True

    def fetch_bot_pnl(self):
        # one living zero-ledger publisher, so the roster sweep has work
        now = _dt.datetime.now(_dt.timezone.utc)
        return [{"bot": ZERO, "closed_trades": 0, "updated_at": now.isoformat()}]

    def fetch_paper_trades(self, limit=2000):
        return _losing_ledger()

    def fetch_state_history(self, key, limit=800):
        return []


def _losing_ledger(n=40):
    """A book with a clearly negative mean -> horizon `unreachable`."""
    base = _dt.datetime(2026, 6, 1, tzinfo=_dt.timezone.utc)
    rows = []
    for i in range(n):
        t0 = base + _dt.timedelta(days=i)
        rows.append({"bot": BOOK, "pair": f"C{i}", "profit_abs": -1.0,
                     "profit_ratio": -0.01,
                     "open_ts": t0.isoformat(),
                     "close_ts": (t0 + _dt.timedelta(hours=2)).isoformat()})
    return rows


def _run(monkeypatch, fake, argv=("--min-closes", "5", "--publish")):
    for name in ("load_state_checked", "load_state", "save_state",
                 "save_history", "fetch_bot_pnl", "fetch_paper_trades",
                 "fetch_state_history"):
        monkeypatch.setattr(store, name, getattr(fake, name), raising=False)
    monkeypatch.setattr(sys, "argv", ["golive_readiness.py", *argv])
    g.main()
    return fake


def _written(fake, key):
    for k, payload in reversed(fake.writes):
        if k == key:
            return payload
    return None


class TestTheClocksAreWrittenToTheirOwnKey:
    def test_a_clean_cycle_writes_the_clocks_separately_from_the_grade(
            self, monkeypatch, capsys):
        fake = _run(monkeypatch, FakeStore())
        capsys.readouterr()
        keys = [k for k, _ in fake.writes]
        assert g.KEY in keys, "the grade must publish"
        assert g.DOCKET_SEEN_KEY in keys, "the clocks must publish"
        assert g.DOCKET_SEEN_KEY != g.KEY
        grade = _written(fake, g.KEY)
        assert grade.get("books"), "collapsing the keys blanks the grade payload"
        assert "ready" in grade and "below_floor" in grade
        clocks = _written(fake, g.DOCKET_SEEN_KEY)
        assert isinstance(clocks.get("seen"), dict) and clocks["seen"]

    def test_a_failed_read_writes_the_grade_and_NOT_the_clocks(
            self, monkeypatch, capsys):
        """The whole point of the (lf) split, asserted on the WRITES."""
        fake = _run(monkeypatch, FakeStore(read_ok=False))
        capsys.readouterr()
        keys = [k for k, _ in fake.writes]
        assert g.KEY in keys, "a clocks problem must never cost the grade"
        assert g.DOCKET_SEEN_KEY not in keys, (
            "the clocks were rewritten after an unreadable prior — this is the "
            "defect that zeroes every book's clock on one Postgres blip")

    def test_a_failed_read_marks_the_docket_INVALID(self, monkeypatch, capsys):
        fake = _run(monkeypatch, FakeStore(read_ok=False))
        capsys.readouterr()
        grade = _written(fake, g.KEY)
        assert grade.get("docket_valid") is False, (
            "an empty docket is a CLAIM; consumers need a positive validity "
            "flag to tell it from 'unknown'")
        assert grade.get("docket_why")


class TestTheMigration:
    def test_clocks_seeded_only_in_the_OLD_location_are_carried_over(
            self, monkeypatch, capsys):
        """(lf) read only the new key, and `load_state_checked` returns
        (True, None) for a MISSING row — so the first publish would have
        restamped every `since` to now AND overwritten the old mirror in the
        same wholesale write. A silent restart of all 14 live clocks."""
        old_since = "2026-08-01T00:00:00+00:00"
        fake = FakeStore(state={g.KEY: {"docket_seen": {
            BOOK: {"reason": "unreachable", "since": old_since}}}})
        _run(monkeypatch, fake)
        capsys.readouterr()
        clocks = _written(fake, g.DOCKET_SEEN_KEY)
        assert clocks["seen"][BOOK]["since"] == old_since, (
            "the migration lost the clock — every book restarts at 7 days")
        grade = _written(fake, g.KEY)
        assert "migrated" in (grade.get("docket_why") or ""), (
            "a one-time hand-off must be STATED, not silent — 14 clocks all "
            "stamped at deploy time read as 'the fleet became stuck today'")

    def test_a_genuinely_first_run_starts_clocks_without_claiming_migration(
            self, monkeypatch, capsys):
        fake = _run(monkeypatch, FakeStore())
        capsys.readouterr()
        grade = _written(fake, g.KEY)
        assert "migrated" not in (grade.get("docket_why") or "")


class TestTheRosterPathReachesTheDocket:
    def test_a_zero_ledger_book_gets_a_clock(self, monkeypatch, capsys):
        """The (ld) hole, asserted on the OUTPUT rather than on the source:
        an `if False:` around the roster write reddens this."""
        fake = _run(monkeypatch, FakeStore())
        capsys.readouterr()
        clocks = _written(fake, g.DOCKET_SEEN_KEY)["seen"]
        grade = _written(fake, g.KEY)
        assert ZERO in grade.get("below_floor", {}), "roster sweep did not run"
        assert ZERO in clocks, (
            "a book that reaches the payload but not the docket is invisible "
            "to I17 forever — this is the case the docket was built for")
        assert clocks[ZERO]["reason"] == "zero_ledger"

    def test_every_stuck_below_floor_book_has_a_clock(self, monkeypatch, capsys):
        fake = _run(monkeypatch, FakeStore())
        capsys.readouterr()
        grade = _written(fake, g.KEY)
        clocks = _written(fake, g.DOCKET_SEEN_KEY)["seen"]
        for b, v in (grade.get("below_floor") or {}).items():
            if (v.get("horizon") or {}).get("verdict") == "no_rate" \
                    and v.get("n_alltime") == 0:
                assert b in clocks, b


class TestTheTwoZeroLedgerDiagnosesAreDistinct:
    def test_a_read_problem_does_not_ask_for_a_retirement(self):
        """(lf) gave both the same reason and the same `asks`. Telling the
        operator to retire a book because the GRADER cannot see its trades is
        the wrong instruction (I8)."""
        stuck, reason = g._docket_stuck({"verdict": "no_rate"},
                                        roster_zero_ledger=True,
                                        roster_n_alltime=500)
        assert stuck and reason == "ledger_missing"
        now = _dt.datetime(2026, 8, 6, tzinfo=_dt.timezone.utc).isoformat()
        later = (_dt.datetime(2026, 8, 6, tzinfo=_dt.timezone.utc)
                 + _dt.timedelta(days=g.DOCKET_DAYS + 1)).isoformat()
        cur = {"x": {"hz": {"verdict": "no_rate"}, "roster_zero_ledger": True,
                     "n": 500, "era_days": None, "mean_pct": None, "t": None}}
        _, seen = g.decision_docket(cur, {}, now)
        d, _ = g.decision_docket(cur, seen, later)
        assert d and "NOT an I17 decision" in d[0]["asks"], d

    def test_a_genuinely_empty_book_still_asks_for_the_I17_call(self):
        stuck, reason = g._docket_stuck({"verdict": "no_rate"},
                                        roster_zero_ledger=True,
                                        roster_n_alltime=0)
        assert stuck and reason == "zero_ledger"


class TestTheClockWriteResultIsNotDiscarded:
    def test_a_failed_clock_write_is_reported(self, monkeypatch, capsys):
        """I4: never discard a persistence result. (lf) dropped this return,
        so the payload advertised clocks that were never stored."""
        fake = _run(monkeypatch, FakeStore(write_ok=False))
        out = capsys.readouterr().out
        assert "CLOCK WRITE FAILED" in out
