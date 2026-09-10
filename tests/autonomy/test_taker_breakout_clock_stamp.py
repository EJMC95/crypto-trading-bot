"""[2026-09-09 (zv)] THE (wr) CLOCK SPLIT MUST HOLD IN THE BOOK, NOT ONLY IN
THE REPLAY.

(wr) gave the breakout trend exit its own hold, `BRK_MAX_HOLD_H`, inside
`bull_exit`, so that `taker.max_hold_h` steers ONLY the divergence bracket.
The replay honours it: it calls `tt.bull_exit(lens)` and hands those bars to
`exit_reason` unmodified. The RUNNING manager does not: per the (dg) flap-fix
it grafts the ENTRY-STAMPED hold over bull_exit's tuple, and the stamp
(`entry_bars`) wrote `MAX_HOLD_H` — the divergence lever — on every lens.

Measured read-only on origin/main 2faa3a1 with MAX_HOLD_H=24 and
BRK_MAX_HOLD_H=48: a 30h-old flat breakoutup position returns None (hold on)
through the replay path and "hold" (exit) through the manager's graft. Both
existing pins were green — `test_breakout_cage_redecision` checks bull_exit
alone, and the taker selftest pins that a breakout honours its ENTRY stamp —
because the defect sits between them: the stamp itself. Behaviour-neutral
today (both constants read 48, no lever in force, and `apply_ready_freeze`
drops `taker.max_hold_h` while the book reads READY), and the (sk)-measured
+0.22..0.57pp harm on the fleet's only READY book the moment the sweep's grid
[24, 48, 72] or a sentinel restrict enacts 24.

The fix stamps the hold the LENS is priced under. (dg)'s invariant survives
untouched: the stamp still governs, so a mid-position lever move still cannot
re-time an open breakout.
"""
import ast
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import lighter_ticket_taker as tt   # noqa: E402

pytestmark = pytest.mark.autonomy


@pytest.fixture
def split_clocks(monkeypatch):
    """The exact configuration the sweep can produce: the divergence lever at
    its cage floor (24h) while the breakout keeps its own 48h clock."""
    monkeypatch.setattr(tt, "BULL_MODE", True)
    monkeypatch.setattr(tt, "MAX_HOLD_H", 24.0)
    monkeypatch.setattr(tt, "BRK_MAX_HOLD_H", 48.0)
    yield


def _manager_reason(meta, entry, mark, opened, now, peak_ret=0.0):
    """The manager's exit decision, reproduced from main() (the graft at the
    `bull_exit` site): bull_exit's bars with the ENTRY-STAMPED hold grafted
    on, exactly as the running loop does it."""
    ebars, etrail = tt.bull_exit(meta.get("lens"))
    if ebars is not None:
        ebars = (ebars[0], ebars[1], tt.pos_bars(meta)[2])
    trail = etrail if etrail is not None else 0.0
    return tt.exit_reason(entry, mark, opened, now, True,
                          bars=(ebars or tt.pos_bars(meta)),
                          peak_ret=peak_ret, trail=trail)


def _replay_reason(meta, entry, mark, opened, now, peak_ret=0.0):
    """The replay's exit decision (lighter_ticket_replay: bull_exit's bars,
    unmodified)."""
    ebars, etrail = tt.bull_exit(meta["lens"])
    return tt.exit_reason(entry, mark, opened, now, True, bars=ebars,
                          peak_ret=peak_ret, trail=etrail)


def test_the_stamp_carries_the_clock_the_lens_is_priced_under(split_clocks):
    assert tt.entry_bars("breakoutup")["max_hold_h"] == 48.0
    assert tt.entry_bars("breakout")["max_hold_h"] == 48.0
    assert tt.entry_bars("divergence")["max_hold_h"] == 24.0
    assert tt.entry_bars()["max_hold_h"] == 24.0, "no lens = the lever, as before"


def test_with_bull_off_every_lens_stamps_the_lever(split_clocks, monkeypatch):
    """bull_exit returns (None, None) with bull off, so the manager runs the
    stamp alone and the replay runs the module default: both must be the
    lever, or the two disagree the other way."""
    monkeypatch.setattr(tt, "BULL_MODE", False)
    assert tt.entry_bars("breakoutup")["max_hold_h"] == 24.0


def test_manager_and_replay_agree_on_a_30h_old_breakout(split_clocks):
    """THE DEFECT: on origin/main the manager says 'hold' (exit at the
    divergence lever's 24h) and the replay says None (run to 48h). The two
    instruments that decide the lever must agree about the trade it clocks."""
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    opened = now - timedelta(hours=30)        # exit_reason takes datetimes
    meta = {"lens": "breakoutup", "bars": tt.entry_bars("breakoutup")}
    assert _replay_reason(meta, 100.0, 100.4, opened, now) is None
    assert _manager_reason(meta, 100.0, 100.4, opened, now) is None
    # ...and at 49h both time out — the split is a different clock, not no clock
    opened49 = now - timedelta(hours=49)
    assert _replay_reason(meta, 100.0, 100.4, opened49, now) == "hold"
    assert _manager_reason(meta, 100.0, 100.4, opened49, now) == "hold"


def test_a_divergence_position_is_still_clocked_by_the_lever(split_clocks):
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    meta = {"lens": "divergence", "bars": tt.entry_bars("divergence")}
    assert _manager_reason(meta, 100.0, 100.2, now - timedelta(hours=30), now) == "hold"
    assert _manager_reason(meta, 100.0, 100.2, now - timedelta(hours=20), now) is None


def test_dg_survives_a_mid_position_lever_move_cannot_retime_a_breakout(split_clocks, monkeypatch):
    """The (dg) flap-fix: the STAMP governs. A breakout stamped at 48h keeps
    48h even if the module constant later moves to 12h."""
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    meta = {"lens": "breakoutup", "bars": tt.entry_bars("breakoutup")}
    monkeypatch.setattr(tt, "BRK_MAX_HOLD_H", 12.0)
    assert _manager_reason(meta, 100.0, 100.4, now - timedelta(hours=30), now) is None


def test_the_call_site_hands_the_lens_to_the_stamp():
    """AST, not substring: the position-open site must build `bars` from
    `entry_bars(lens)`. A bare `entry_bars()` there is the defect restored."""
    tree = ast.parse(open(os.path.join(ROOT, "lighter_ticket_taker.py")).read())
    stamped = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if (isinstance(k, ast.Constant) and k.value == "bars"
                    and isinstance(v, ast.Call)
                    and isinstance(v.func, ast.Name) and v.func.id == "entry_bars"):
                stamped.append([a.id for a in v.args if isinstance(a, ast.Name)])
    assert stamped, "no position-open site stamps bars from entry_bars()"
    assert all(args == ["lens"] for args in stamped), \
        f"entry_bars must receive the lens at every stamp site, got {stamped}"
