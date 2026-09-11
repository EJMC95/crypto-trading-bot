"""Dashboard safety (spec 17): append-only, verified, and fail-closed."""
import json

import pytest

from lighter_bots import dashboard_patch as D


def _feed(tmp_path, rows, name="pnl.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"bots": rows}))
    return str(p)


ROWS = [
    {"bot": "freqtrade-mum-lighter", "status": "online", "equity": 531.5,
     "pnl_abs": 11.08, "pnl_pct": 0.02, "closed_trades": 30, "open_trades": 4,
     "wins": 18, "losses": 12},
    {"bot": "perps-funding-carry-lshadow", "status": "online", "equity": 1066.0,
     "pnl_abs": 66.0, "pnl_pct": 0.066, "closed_trades": 120, "open_trades": 6,
     "wins": 47, "losses": 73},
]


def test_an_unreadable_feed_is_a_FAILURE_not_a_clean_baseline(tmp_path):
    with pytest.raises(D.DashboardVerificationError):
        D.snapshot(str(tmp_path / "does-not-exist.json"))


def test_an_empty_feed_is_refused(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"bots": []}))
    with pytest.raises(D.DashboardVerificationError):
        D.snapshot(str(p))


def test_a_snapshot_captures_every_bot(tmp_path):
    snap = D.snapshot(_feed(tmp_path, ROWS))
    assert snap.bots == {"freqtrade-mum-lighter",
                         "perps-funding-carry-lshadow"}


def test_identical_feeds_verify_unchanged(tmp_path):
    a = D.snapshot(_feed(tmp_path, ROWS, "a.json"))
    b = D.snapshot(_feed(tmp_path, ROWS, "b.json"))
    ok, problems = D.verify_unchanged(a, b)
    assert ok and not problems


def test_a_moving_pnl_is_the_fleet_trading_not_a_defect(tmp_path):
    a = D.snapshot(_feed(tmp_path, ROWS, "a.json"))
    moved = [dict(r) for r in ROWS]
    moved[0]["pnl_abs"] = 99.0
    moved[0]["equity"] = 620.0
    b = D.snapshot(_feed(tmp_path, moved, "b.json"))
    ok, _p = D.verify_unchanged(a, b)
    assert ok, "live numbers move between reads; that is not a patch defect"


def test_a_DISAPPEARED_row_fails_verification(tmp_path):
    a = D.snapshot(_feed(tmp_path, ROWS, "a.json"))
    b = D.snapshot(_feed(tmp_path, ROWS[:1], "b.json"))
    ok, problems = D.verify_unchanged(a, b)
    assert not ok and any("DISAPPEARED" in p for p in problems)


def test_a_changed_status_fails_verification(tmp_path):
    a = D.snapshot(_feed(tmp_path, ROWS, "a.json"))
    changed = [dict(r) for r in ROWS]
    changed[0]["status"] = "halted"
    b = D.snapshot(_feed(tmp_path, changed, "b.json"))
    ok, problems = D.verify_unchanged(a, b)
    assert not ok and any("status" in p for p in problems)


def test_a_field_that_vanishes_fails_verification(tmp_path):
    a = D.snapshot(_feed(tmp_path, ROWS, "a.json"))
    stripped = [dict(r) for r in ROWS]
    stripped[0].pop("wins")
    b = D.snapshot(_feed(tmp_path, stripped, "b.json"))
    ok, problems = D.verify_unchanged(a, b)
    assert not ok and any("presence changed" in p for p in problems)


def test_a_retyped_field_fails_verification(tmp_path):
    a = D.snapshot(_feed(tmp_path, ROWS, "a.json"))
    retyped = [dict(r) for r in ROWS]
    retyped[0]["closed_trades"] = "30"
    b = D.snapshot(_feed(tmp_path, retyped, "b.json"))
    ok, problems = D.verify_unchanged(a, b)
    assert not ok and any("type changed" in p for p in problems)


def test_a_NEW_row_is_permitted_by_default(tmp_path):
    a = D.snapshot(_feed(tmp_path, ROWS, "a.json"))
    extra = ROWS + [dict(ROWS[0], bot="lus-new-lshadow")]
    b = D.snapshot(_feed(tmp_path, extra, "b.json"))
    assert D.verify_unchanged(a, b)[0]
    assert not D.verify_unchanged(a, b, allow_new=False)[0]


def test_append_only_refuses_to_overwrite_an_existing_key():
    with pytest.raises(D.DashboardVerificationError):
        D.append_only({"a": 1}, {"a": 2})
    assert D.append_only({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


@pytest.mark.parametrize("name", D.PROTECTED_NAMES)
def test_touching_a_protected_name_is_refused(name):
    plan = D.PatchPlan(additions={"x": 1}, touched_names=[name])
    ok, problems = plan.safe()
    assert not ok and problems


def test_a_pure_append_to_source_is_allowed():
    before = "CURRENT_BOTS = [\n    'a',\n    'b',\n]\n"
    after = before + "\nNEW_LIGHTER_BOTS = ['c']\n"
    assert D.forbidden_edits(before, after) == []


def test_editing_a_protected_block_is_refused():
    before = "STALE_SECONDS = 300\n"
    after = "STALE_SECONDS = 900\n"
    problems = D.forbidden_edits(before, after)
    assert problems


def test_deleting_an_existing_line_is_refused():
    before = "CURRENT_BOTS = ['a']\nEXPECTED = 3\nLABELS = {}\n"
    after = "CURRENT_BOTS = ['a']\nLABELS = {}\n"
    problems = D.forbidden_edits(before, after)
    assert any("removed or reordered" in p or "EXPECTED" in p
               for p in problems)


def test_reordering_existing_lines_is_refused():
    before = "A = 1\nB = 2\nC = 3\n"
    after = "C = 3\nA = 1\nB = 2\n"
    assert D.forbidden_edits(before, after)


# ------------------------------------------------- the two-verifier finding --
_SET_BEFORE = '''SLOW_LOOP = {"a"}
STALE_SECONDS = 180
VARIANT_ONLY = {"alpha",
                "beta",
                "nav-cook"}
EXPECTED = ["x"]
'''
_SET_APPENDED = '''SLOW_LOOP = {"a"}
STALE_SECONDS = 180
VARIANT_ONLY = {"alpha",
                "beta",
                "nav-cook",
                "downtrend-ensemble"}
EXPECTED = ["x"]
'''
_SET_REMOVED = '''SLOW_LOOP = {"a"}
STALE_SECONDS = 180
VARIANT_ONLY = {"alpha",
                "downtrend-ensemble"}
EXPECTED = ["x"]
'''


def test_appending_past_a_shared_closing_brace_is_not_a_removal():
    """THE FALSE POSITIVE, found by running one real patch through BOTH of
    this repo's dashboard verifiers and getting two different answers.

    A set written `{..., "nav-cook"}` necessarily rewrites its LAST line when
    it grows: `"nav-cook"}` becomes `"nav-cook",`. Nothing was removed. The
    line-subsequence check called it a removal -- which is the one operation
    this verifier exists to permit, and a check that fires on the legitimate
    case is a check that gets waived."""
    assert D.forbidden_edits(_SET_BEFORE, _SET_APPENDED) == []


def test_actually_removing_an_entry_is_still_refused():
    """The other half, and the reason the exemption is written narrowly: only
    a dropped closer plus an added comma is forgiven. Change the entry TEXT
    and it still fails."""
    problems = D.forbidden_edits(_SET_BEFORE, _SET_REMOVED)
    assert problems and any("removed or reordered" in p for p in problems)


def test_renaming_an_entry_is_still_refused():
    renamed = _SET_BEFORE.replace('"beta",', '"beta-v2",')
    assert D.forbidden_edits(_SET_BEFORE, renamed)


def test_a_protected_constant_change_is_still_refused():
    assert D.forbidden_edits(_SET_BEFORE,
                           _SET_BEFORE.replace("STALE_SECONDS = 180",
                                               "STALE_SECONDS = 5"))
