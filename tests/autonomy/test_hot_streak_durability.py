"""A TIMER ON A CONTAINER THAT RESTARTS MUST SURVIVE THE RESTART (2026-08-03).

MEASURED on the live Funding Farmer: it booted 00:05Z after a deploy and could
not open a position until **04:05Z**, because the entry gate needs a coin hot
for `PERSIST_H` (4h) and `hot_since` was memory-only — every boot reset every
coin's streak to zero. The loop meanwhile printed

    scan ok | 217 perps | held: none

which is byte-identical to "nothing was hot enough". A blocked book and an
idle book looked the same from outside, on real money, for four hours after
every deploy — and there were several deploys that day.

**This is the same defect the 22-Jul COOLDOWN DURABILITY fix closed on this very
bot** ("a memory-only guard on a bot whose container is not"), and `hot_since`
is the timer it missed. Only the direction differs: a lost cooldown made the
bot too PERMISSIVE (re-armed a coin it had just stopped out of), a lost
hot-streak makes it entirely INERT. Same class, opposite sign — which is
presumably why one got noticed and the other did not.

The validated gate is UNCHANGED: `PERSIST_H` is still 4h and a coin must still
be continuously hot for it. Restoring the clock only readmits entries an
UNINTERRUPTED process would have taken.

`test_both_arms_persist_the_clock` is the load-bearing one. The shadow twin is
the experiment judge's CONTROL ARM, and the bot's own 22-Jul note records what
happens when a durability fix ships on one arm only: "makes the paired
promotion bar compare two different rules". So parity is asserted structurally,
by AST, over the publisher's own save blobs.
"""
import ast
import os
import pathlib
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import lighter_funding_bot as M  # noqa: E402

NOW = 1_000_000.0


def _blob(hot, saved):
    return {"hot_since": hot, "saved_ts": saved}


def test_clock_survives_a_deploy_sized_gap():
    """The whole point: a redeploy must not cost the book its streak."""
    hot, why = M.restore_hot_since(_blob({"BTC": NOW - 5 * 3600}, NOW - 60), NOW)
    assert hot == {"BTC": NOW - 5 * 3600}, why
    # ...and the restored clock actually CLEARS the gate it exists to satisfy
    age_h = (NOW - hot["BTC"]) / 3600.0
    assert age_h >= M.PERSIST_H, f"{age_h}h should clear PERSIST_H={M.PERSIST_H}"


def test_a_pre_fix_blob_restores_nothing():
    """No `saved_ts` = a blob written before this shipped. Fail-closed to the
    OLD behaviour, never to a guess about when the coin went hot."""
    hot, why = M.restore_hot_since({"hot_since": {"BTC": NOW - 9e9}}, NOW)
    assert hot == {} and "no saved_ts" in why


def test_a_long_gap_is_refused():
    """Hot before, hot now, COLD IN BETWEEN is indistinguishable from
    continuously hot once the observer was away — so an outage-sized gap must
    not resurrect a streak. This is the one case that could wrongly let a coin
    skip the gate on a real-money book."""
    hot, why = M.restore_hot_since(
        _blob({"BTC": NOW - 5 * 3600}, NOW - 6 * 3600), NOW)
    assert hot == {} and "not restored" in why


def test_clock_skew_is_refused():
    hot, why = M.restore_hot_since(_blob({"BTC": NOW - 5 * 3600}, NOW + 500), NOW)
    assert hot == {} and "negative gap" in why


@pytest.mark.parametrize("bad", [NOW + 3600, "soon", None, float("nan")])
def test_untrustworthy_stamps_are_dropped_per_coin(bad):
    """A future or unparseable stamp drops THAT coin, without taking the
    healthy ones with it. NaN compares False against every bound, so it is
    excluded by the same `t <= now` test rather than by a special case."""
    hot, _ = M.restore_hot_since(
        _blob({"BTC": NOW - 5 * 3600, "JUNK": bad}, NOW - 60), NOW)
    assert hot == {"BTC": NOW - 5 * 3600}


def test_bound_is_configurable_and_defaults_sanely():
    assert 0 < M.HOT_RESTORE_MAX_GAP_S <= 3600, (
        "the bound must cover a deploy, not an outage — a large value "
        "reintroduces the stale-streak hazard this fails closed on")


def _save_blob_keys(module_filename):
    """Key sets of every `store.save_state(bot, {...})` dict literal. AST, not
    a substring scan — `"hot_since"` appears in this file's own docstring and
    in the bot's comments, either of which would satisfy a grep."""
    src = open(os.path.join(_ROOT, module_filename), encoding="utf-8").read()
    out = []
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "save_state"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Dict):
                out.append({k.value for k in arg.keys
                            if isinstance(k, ast.Constant)
                            and isinstance(k.value, str)})
    return out


def test_both_arms_persist_the_clock():
    """ARM PARITY. Every state blob that persists `explore_seen` is an arm's
    own blob (live and shadow both do); each must also carry the hot clock and
    its stamp. Ship it on one arm and the judge's paired bar silently compares
    two different rules — the bot's 22-Jul note says exactly that."""
    blobs = [k for k in _save_blob_keys("lighter_funding_bot.py")
             if "explore_seen" in k]
    assert len(blobs) >= 2, f"expected both arm blobs, found {len(blobs)}"
    for keys in blobs:
        assert "hot_since" in keys, f"arm blob missing hot_since: {sorted(keys)}"
        assert "saved_ts" in keys, (
            f"arm blob has hot_since but no saved_ts — the clock would be "
            f"restored with no gap bound: {sorted(keys)}")


def test_the_validated_gate_was_not_weakened():
    """The fix restores a clock; it must not loosen the rule. If someone
    'fixes' the blackout by shrinking PERSIST_H instead, that is a different
    change and this says so."""
    assert M.PERSIST_H >= 4.0, (
        "PERSIST_H is the validated persistence gate; the restart blackout is "
        "a bookkeeping bug and must not be worked around by weakening it")


def test_entry_stamp_records_the_streak_age():
    """[(ir)] The ledger recorded the persistence BAR but never the
    OBSERVATION, so "should PERSIST_H be shorter?" could not be answered from
    the book's own record — the unfalsifiable-constant class (gr) closed for
    exit prices."""
    m = M.entry_stamp(True, 100.0, 1_700_000_000.0, 25.0, "exploit", hot_h=7.25)
    assert m["hot_h"] == 7.25
    assert M.entry_stamp(True, 100.0, 1.0, 25.0, "exploit")["hot_h"] is None


def test_zero_hours_is_recorded_not_swallowed():
    """0.0 is a REAL and alarming reading — it would mean the gate admitted a
    coin with no streak at all. A falsy test would hide exactly the bug most
    worth seeing, so this pins truthiness is not used."""
    assert M._close_hot_extra({}, 0.0) == {"hot_h": 0.0}


@pytest.mark.parametrize("bad", [None, "later", float("nan")])
def test_unusable_streak_ages_never_reach_storage(bad):
    """NaN is the I5 case: json.dumps emits bare NaN and Postgres jsonb rejects
    the whole row, so one bad field would cost the entire close record."""
    assert M._close_hot_extra({"bars": {"x": 1}}, bad) == {"bars": {"x": 1}}


def test_hot_extra_is_additive_only():
    assert M._close_hot_extra(None, None) is None
    assert M._close_hot_extra(None, 3.0) == {"hot_h": 3.0}
    assert M._close_hot_extra({"hot_h": "keep"}, 9.0)["hot_h"] == "keep"


def test_every_close_path_carries_the_streak_age():
    """Class-closer. Three call sites record a close; a fourth added later
    without `hot_h` would silently drop the telemetry for that exit reason
    only — and a partial ledger is worse than none, because the gap would look
    like a finding. Any `_record_close` call passing `src` must pass `hot_h`."""
    src = open(os.path.join(_ROOT, "lighter_funding_bot.py"), encoding="utf-8").read()
    n = 0
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_record_close"):
            continue
        kw = {k.arg for k in node.keywords}
        if "src" not in kw:
            continue
        n += 1
        assert "hot_h" in kw, "a close path records src but drops hot_h"
    assert n >= 3, f"expected >=3 close paths, found {n}"


# ---------------------------------------------------------------------------
# [2026-08-03 (iu)] THE CARRY BOOK HAD THE MIRROR OF THIS BUG.
#
# `(iq)` fixed a LOST clock on the Farmer -> the book went INERT for 4h. The
# carry book restored its clock UNCONDITIONALLY — any dict, any age, no
# `saved_ts` and no gap bound — which is the same defect pointing the other
# way: a WRONGLY-restored streak lets a coin skip PERSIST_H on hotness that
# did not persist. An inert book shows up as nothing; a permissive one shows
# up as a bad trade, and "spikes pay fees" is this book's whole thesis.
#
# The rule now has ONE OWNER in `funding_basis` (already in _BUILD_SHARED and
# COPY'd into both images), so the two funding books cannot drift — the `(hj)`
# rule that a second copy of a rule is a second rule.
# ---------------------------------------------------------------------------

import funding_basis  # noqa: E402
import funding_carry_bot as CARRY  # noqa: E402

_NOW = 1_000_000.0
_CASES = [
    None,
    {},
    {"hot_since": {"A": 1.0}},                                # pre-durability blob
    {"saved_ts": _NOW - 60, "hot_since": {"A": 5.0}},          # good
    {"saved_ts": _NOW - 899, "hot_since": {"A": 1.0, "B": 2.0}},
    {"saved_ts": _NOW - 99999, "hot_since": {"A": 5.0}},       # outage gap
    {"saved_ts": _NOW + 60, "hot_since": {"A": 5.0}},          # clock skew
    {"saved_ts": _NOW - 60, "hot_since": {"A": _NOW + 900}},   # future stamp
    {"saved_ts": _NOW - 60, "hot_since": {"A": "junk"}},       # unparseable
]


@pytest.mark.parametrize("blob", _CASES)
def test_both_funding_books_restore_the_clock_identically(blob):
    """One rule, one owner. If these ever disagree, one book is admitting
    entries the other refuses — silently, and only after an outage."""
    assert (funding_basis.restore_hot_since(blob, _NOW)[0]
            == M.restore_hot_since(blob, _NOW)[0])


def test_the_shared_restore_fails_closed_in_every_doubtful_direction():
    """The floor of every failure mode must be the pre-durability behaviour
    (a fresh wait), never a resurrected streak.

    Mutations that turn this red: drop the gap bound, trust a future stamp,
    default a missing `saved_ts` to now.
    """
    r = funding_basis.restore_hot_since
    assert r({"hot_since": {"A": 1.0}}, _NOW)[0] == {}, "no saved_ts must not restore"
    assert r({"saved_ts": _NOW - 99999, "hot_since": {"A": 5.0}}, _NOW)[0] == {}, \
        "an outage-sized gap must not resurrect a streak"
    assert r({"saved_ts": _NOW + 60, "hot_since": {"A": 5.0}}, _NOW)[0] == {}, \
        "clock skew must not restore"
    assert r({"saved_ts": _NOW - 60, "hot_since": {"A": _NOW + 900}}, _NOW)[0] == {}, \
        "a future per-coin stamp must be dropped"
    # and the good case still restores, so the above are not vacuously empty
    assert r({"saved_ts": _NOW - 60, "hot_since": {"A": 5.0}}, _NOW)[0] == {"A": 5.0}


def test_carry_restores_through_the_shared_owner_and_persists_saved_ts():
    """Two halves, both load-bearing: the carry bot must CALL the shared
    restore (not re-implement or inline a bare dict copy), and it must WRITE
    `saved_ts` — without the write, the read fails closed forever and the book
    silently reduces to a fresh PERSIST_H wait on every boot.

    AST, not a substring scan: this file's own prose says every one of these
    words (the (hm) lesson).
    """
    tree = ast.parse(pathlib.Path(CARRY.__file__).read_text(encoding="utf-8"))

    calls_shared = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "restore_hot_since"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "funding_basis"
        for n in ast.walk(tree))
    assert calls_shared, "carry must restore through funding_basis, not its own copy"

    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "restore_hot_since"
        for n in ast.walk(tree)), "carry must not define a SECOND copy of the rule"

    saves_ts = False
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "save_state"):
            for a in n.args:
                if isinstance(a, ast.Dict) and any(
                        isinstance(k, ast.Constant) and k.value == "saved_ts"
                        for k in a.keys):
                    saves_ts = True
    assert saves_ts, (
        "carry never writes `saved_ts` — the restore would fail closed forever "
        "and every boot would start a fresh PERSIST_H wait")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
