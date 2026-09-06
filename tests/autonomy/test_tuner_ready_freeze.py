"""[2026-09-06 (yd)] A READY BOOK KEEPS THE BRACKET IT PASSED ON.

(hm) wrote "if a book needs grading, FREEZE ITS BARS FIRST" after 137 shadow
closes produced zero gradeable ones because the scout tuner moved the taker's
bracket ~20 times in a fortnight. (jf) then made the era MECHANICAL and — on
purpose — excluded bracket levers from the signature (venue/bull/lenses/sides
only), because resetting the clock on every tuner step would make the 30-day
bar unreachable. Both were right, and together they left a hole: nothing
stopped the tuner from moving a READY book's bracket, so on 6-Sep the fleet's
first-ever READY verdict (🎫 the taker, 6 of 6) was computed over a sample
spanning `taker.tp` 0.03/0.04 and `taker.max_hold_h` 24/48.

The freeze is FORWARD-ONLY and lives at the tuner's write site: while the
tuned book reads `ready: true` on a FRESH `golive-readiness` payload, every
lever in FROZEN_WHEN_READY is dropped from the enactment and published under
`ready_freeze.dropped`. Entry/supply levers keep moving ((hc) ordinary
tuning). Fail-OPEN on a dark/stale/unreadable/non-READY gate — the shadow-lane
contract: a dark organ restricts nothing.

MUTATIONS THAT MUST TURN THIS RED (verified in the changelog entry):
  * deleting the `apply_ready_freeze` call before `write_levers`;
  * dropping `taker.tp` (or any sweep-owned bracket lever) from the set;
  * freezing on a STALE gate (fail-closed inversion);
  * freezing when `ready` is False/absent.
"""
import ast
import datetime as dt
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import lighter_scout_tuner as tuner  # noqa: E402

pytestmark = pytest.mark.autonomy

BOOK = tuner.TUNED_BOOK
NOW = dt.datetime(2026, 9, 6, 11, 0, tzinfo=dt.timezone.utc)


def _gate(ready, age_s=60, ttl=43200, book=BOOK):
    upd = (NOW - dt.timedelta(seconds=age_s)).isoformat()
    return {"updated": upd, "ttl_sec": ttl,
            "books": {book: {"ready": ready, "bars": {}}}}


def _levers():
    return {
        "taker.tp": {"value": 0.03, "reason": "sweep"},
        "taker.max_hold_h": {"value": 24.0, "reason": "sweep"},
        "taker.dip_range": {"value": 0.08, "reason": "widen"},
        "scout.momo_chg_min": {"value": 2.0, "reason": "diet"},
    }


def test_a_ready_book_keeps_its_bracket_and_entry_levers_still_move():
    kept, log, rec = tuner.apply_ready_freeze(_levers(), _gate(True),
                                              now_ts=NOW.timestamp())
    assert set(kept) == {"taker.dip_range", "scout.momo_chg_min"}, kept
    assert sorted(rec["dropped"]) == ["taker.max_hold_h", "taker.tp"]
    assert rec["ready"] is True and rec["fresh"] is True and rec["book"] == BOOK
    assert len(log) == 2 and all("NOT enacted" in l for l in log)


def test_a_book_that_is_not_ready_is_untouched():
    for gate in (_gate(False), _gate(None)):
        kept, log, rec = tuner.apply_ready_freeze(_levers(), gate,
                                                  now_ts=NOW.timestamp())
        assert kept == _levers() and log == [] and rec["dropped"] == []
        assert rec["ready"] is False


def test_dark_stale_or_junk_gate_fails_open():
    """The freeze protects EVIDENCE, not money: darkness must not restrict."""
    stale = _gate(True, age_s=43200 + 1)
    for gate in ({}, None, "junk", {"updated": "nonsense"}, stale,
                 _gate(True, book="some-other-book")):
        kept, log, rec = tuner.apply_ready_freeze(_levers(), gate,
                                                  now_ts=NOW.timestamp())
        assert kept == _levers(), f"restricted on {gate!r}"
        assert log == [] and rec["dropped"] == []
    _, _, rec = tuner.apply_ready_freeze(_levers(), stale, now_ts=NOW.timestamp())
    assert rec["fresh"] is False, "a stale gate must be REPORTED stale (I1)"


def test_every_sweep_owned_bracket_lever_is_in_the_frozen_set():
    """The sweep can write tp / sl / max_hold_h; every one must be frozen, or
    a READY sample can still be re-specified by the instrument that grades
    against it."""
    assert {"taker.tp", "taker.sl", "taker.max_hold_h"} <= set(
        tuner.FROZEN_WHEN_READY)
    # and the freeze never touches an ENTRY lever (those are (hc) tuning)
    entry = {lever for _a, (_attr, lever, _lad) in tuner.TAKER_LADDERS.items()}
    assert not (entry & set(tuner.FROZEN_WHEN_READY)), (
        "an entry/supply lever is in the frozen set — that would starve a "
        "READY book of tickets, which is the opposite of the intent")


def test_the_freeze_runs_at_the_write_site_after_every_other_filter():
    """AST, not substring: inside the tuner's cycle the call to
    `apply_ready_freeze` must precede `tuning.write_levers`, and its result
    must be what `write_levers` receives."""
    src = (ROOT / "lighter_scout_tuner.py").read_text()
    mod = ast.parse(src)
    freeze_line = write_line = None
    for n in ast.walk(mod):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == "apply_ready_freeze":
                freeze_line = n.lineno
            if (isinstance(f, ast.Attribute) and f.attr == "write_levers"
                    and isinstance(f.value, ast.Name) and f.value.id == "tuning"):
                write_line = n.lineno
    assert freeze_line and write_line, "call sites not found — guard is vacuous"
    assert freeze_line < write_line, \
        "apply_ready_freeze must run BEFORE write_levers"
    assert '"ready_freeze": ready_freeze' in src, \
        "the freeze's receipt must be PUBLISHED on the tuner payload (I18)"


def test_the_tuned_book_is_the_takers_shadow_row():
    assert BOOK.endswith("-lshadow") and BOOK.startswith("lighter-ticket-taker")
