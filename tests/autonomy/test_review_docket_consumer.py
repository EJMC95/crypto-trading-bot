"""[(lj)] The daily review must CONSUME the decision docket.

WHY. `(ld)` built the docket, `(lf)` fixed three defects in it, and `(lh)`
recorded — as still open — that *"the docket still has NO CONSUMER: nothing
renders it and the daily review does not read it"*, adding that by this repo's
own rule (*"a finding no gate consumes is a note"*) parts of that work improved
a signal reaching nobody. This file pins the consumer so it cannot quietly go
away again.

BEHAVIOURAL, not source-shaped. These drive the REAL `scan_new_evidence`
against a fake cursor and read the items it RETURNS. A source check would pass
against a section whose docket branch is unreachable — the exact class `(lh)`
diagnosed and `test_docket_publish_behaviour.py` exists to answer.

THE FOUR STATES ARE ALL DISTINCT, and that is the point of the tests rather
than an accident of coverage:
  * valid + entries   -> name the books and their `asks` (I8)
  * valid + empty     -> "clear", an affirmative negative
  * NOT valid         -> "could not tell", NEVER "nothing is overdue"
  * stale payload     -> UNKNOWN (I1: a frozen docket is byte-identical to a
                         live empty one, and only the age distinguishes them)
"""
import datetime as dt
import importlib
import json
import sys

import pytest

pytestmark = pytest.mark.autonomy

try:
    ER = importlib.import_module("scripts.evidence_review")
except Exception as _e:      # pragma: no cover - import must not be silent
    pytest.skip(f"evidence_review unimportable: {_e}", allow_module_level=True)


class FakeCur:
    """Answers only the queries this section needs; everything else is empty.

    The review wraps each section in `Section`, which suppresses exceptions, so
    a fake that raised would silently produce ZERO items and every assertion
    below would have to be "not in", which passes vacuously. Returning empties
    keeps the section running all the way to the docket block.
    """

    def __init__(self, state=None, updated_at=None):
        self.state = state
        self.updated_at = updated_at
        self._last = ""
        self._row = None

    def execute(self, sql, params=None):
        self._last = " ".join(str(sql).split())
        self._row = None
        if "FROM bot_state WHERE bot=" in self._last:
            key = (params or ("",))[0]
            if key == "golive-readiness" and self.state is not None:
                self._row = (json.dumps(self.state), self.updated_at)

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


def _run(state, age_h=1.0):
    updated = None
    if state is not None:
        updated = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=age_h)
    errors = []
    items = ER.scan_new_evidence(FakeCur(state, updated), errors)
    return [i for i in items if "decision docket" in i.lower()], errors


def _payload(docket, valid=True, why=None, days=7):
    p = {"decision_docket": docket, "docket_valid": valid, "docket_days": days,
         "books": {}, "ready": []}
    if why:
        p["docket_why"] = why
    return p


def _entry(book="equities-regime-lshadow", reason="zero_ledger", days=11.0,
           n=0, asks="keep-or-retire (I17) — an operator decision, not a "
                     "tuning pass"):
    return {"book": book, "reason": reason, "days_held": days, "n": n,
            "asks": asks, "mean_pct": None, "t": None}


# ---------------------------------------------------------------------------

def test_the_section_reaches_the_docket_block_at_all(caplog):
    """The empty-collection trap. If the fake broke the section, every
    assertion below would pass by producing nothing."""
    lines, errors = _run(_payload([]))
    assert lines, f"the docket block never ran; section errors: {errors}"


def test_an_overdue_book_is_named_with_its_ask(caplog):
    """I8 — a detector whose output is an instruction must name the object the
    operator can act on. A bare count is not actionable, and (la) had just
    fixed exactly that in the horizon tally beside this line."""
    lines, _ = _run(_payload([_entry()]))
    line = "\n".join(lines)
    assert "equities-regime-lshadow" in line
    assert "zero_ledger" in line
    assert "keep-or-retire" in line
    assert "11.0d" in line or "11.0" in line


def test_a_clear_docket_says_clear_rather_than_nothing(caplog):
    """An affirmative negative. Emitting nothing would be indistinguishable
    from the section having failed — the (kw) dark-reads-as-clean shape."""
    lines, _ = _run(_payload([]))
    assert any("clear" in l for l in lines), lines


def test_an_invalid_docket_is_never_reported_as_clear(caplog):
    """The whole reason `docket_valid` exists: `[]` is a CLAIM, and on a failed
    clock read it reads byte-identically to 'nothing is overdue'."""
    lines, _ = _run(_payload([], valid=False,
                             why="docket clocks unreadable — NOT recomputed"))
    line = "\n".join(lines)
    assert "NOT VALID" in line, line
    assert "clear" not in line, line
    assert "unreadable" in line, line


def test_a_stale_grader_payload_is_reported_as_unknown(caplog):
    """I1 — liveness before semantics. A docket frozen 40h ago and a live empty
    one are byte-identical in content; only the age tells them apart."""
    lines, _ = _run(_payload([_entry()]), age_h=40.0)
    line = "\n".join(lines)
    assert "stale" in line and "UNKNOWN" in line, line


def test_a_missing_grader_payload_is_reported_as_unknown(caplog):
    lines, _ = _run(None)
    line = "\n".join(lines)
    assert "unreadable" in line and "UNKNOWN" in line, line


def test_a_ledger_missing_book_is_not_presented_as_a_retirement_case(caplog):
    """I8 again, and the sharpest case: the grader cannot READ this book's
    trades. Telling the operator to retire it would destroy a working book on
    a fetch failure."""
    import scripts.golive_readiness as GR
    lines, _ = _run(_payload([_entry(book="busy-lshadow",
                                     reason="ledger_missing", n=250,
                                     asks=GR.DOCKET_ASKS["ledger_missing"])]))
    line = "\n".join(lines)
    assert "busy-lshadow" in line
    assert "NOT a retirement case" in line, line
