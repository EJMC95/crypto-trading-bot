"""🪁 band-kelly — the MIRROR book's structural pins (born 2026-08-18).

The bot's whole claim is "the ghost's own rules, sign-flipped" — so what a
future edit could silently break is exactly what gets pinned here:

  1. ONE OWNER: the gate math is imported from the retired ghost module
     (`lighter_dislocation_bot`), never re-implemented. A second copy of a
     rule is a second rule ((hj)); the negation claim dies the day the two
     drift.
  2. THE INVERSION ITSELF: mirror side is the ghost's opposite at every
     residual sign. This is the finding — a flipped comparison operator
     would quietly turn the mirror back into the loser it inverts.
  3. SOLE-WRITER AT THE TOP OF THE LOOP ((hp)/(ic)): claim before the first
     positions[] write; a losing claimant stands down on its own :standby
     key and never exits (restartPolicy=always turns an exit into a
     crash-loop).
  4. EXITS NEVER SIT BEHIND A DATA FETCH ((nm)): `mirror_exit` must not be
     nested under `if ref:` — a dark reference blinds the conv exit only,
     while the price stop and the clock keep running.
  5. ENV-ONLY: no tuning-lane read exists ((hm) single-policy clock — the
     Garrett choice). An import of fleet_tuning or a get_lever call is a
     policy change wearing a refactor.
  6. THE ROSTER RECORD: the refused/owned mirror families stay DECLARED in
     the published payload — deleting a refusal is how a refuted idea gets
     rebuilt in six weeks.

AST-bound, not substring scans (the standing (hj) lesson: a page-wide
`in`-check passes against a comment). Mutation-verified at birth: side
flip, claim moved below the open, standby branch exiting, mirror_exit
nested under `if ref:`, roster entry deleted — all red.
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

pytestmark = pytest.mark.autonomy

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_band_kelly_bot as kelly              # noqa: E402
import lighter_dislocation_bot as ghost_mod         # noqa: E402

SRC = (ROOT / "lighter_band_kelly_bot.py").read_text()
TREE = ast.parse(SRC)


def _main_fn():
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("no main()")


def _while_true(fn):
    for n in ast.walk(fn):
        if (isinstance(n, ast.While) and isinstance(n.test, ast.Constant)
                and n.test.value is True):
            return n
    raise AssertionError("no `while True` loop in main()")


# ---------------------------------------------------------------- 1. one owner
def test_the_ghost_math_is_imported_not_copied():
    """MUTATION: def a local adaptive_enter_bps in the bot -> RED."""
    assert kelly.ghost is ghost_mod, "the ghost alias must BE the module"
    local_defs = {n.name for n in ast.walk(TREE)
                  if isinstance(n, ast.FunctionDef)}
    for owned in ("adaptive_enter_bps", "book_view", "index_from_books",
                  "reference_prices"):
        assert owned not in local_defs, (
            f"{owned} is re-implemented locally — the negation claim requires "
            f"the ghost's own {owned}, imported (a second copy is a second "
            f"rule)")


def test_the_ghost_constants_are_the_retirement_config():
    """The founding claim negates a ledger earned at THESE constants; a
    drifted constant is a different ghost. (jh) retirement-day values."""
    assert ghost_mod.EXIT_BPS == 40.0
    assert ghost_mod.HARD_STOP == 0.05
    assert ghost_mod.MAX_HOLD_S == 7200.0
    assert ghost_mod.CONFIRM_LOOPS == 2
    assert ghost_mod.ENTER_PCT == 0.98
    assert ghost_mod.ENTER_FLOOR_MULT == 1.5


# ------------------------------------------------------------- 2. the inversion
def test_the_mirror_is_always_the_ghosts_opposite():
    """MUTATION: flip either comparison -> RED."""
    for dev in (-750.0, -60.01, -0.5, 0.5, 60.01, 750.0):
        assert kelly.mirror_side(dev) != kelly.ghost_side(dev), dev
    assert kelly.mirror_side(75.0) == "long"      # rich -> ride the premium
    assert kelly.mirror_side(-75.0) == "short"    # cheap -> ride the discount


def test_the_ghost_stop_is_the_mirrors_profit_side_cover():
    """The ghost's 5% death is the mirror's banked win — a sign error here
    would hold the mirror through exactly the move it should bank."""
    pos = {"coin": "X", "side": "long", "ghost_side": "short",
           "entry": 100.0, "ghost_entry": 100.0, "notional": 80.0,
           "opened_ts": 0.0, "last_px": 100.0}
    assert kelly.mirror_exit(pos, 80.0, 105.2, 105.2, 1.0) == "ghoststop"
    assert kelly._price_pnl(pos, 105.2) > 0, "ghoststop must bank a PROFIT"


# ---------------------------------------------------- 3. sole-writer contract
def test_claim_writer_precedes_the_first_position_write():
    loop = _while_true(_main_fn())
    claims = [n.lineno for n in ast.walk(loop)
              if isinstance(n, ast.Call)
              and getattr(n.func, "attr", None) == "claim_writer"]
    assert claims, "claim_writer is not called in the loop"
    opens = [n.lineno for n in ast.walk(loop)
             if isinstance(n, ast.Subscript)
             and getattr(n.value, "id", None) == "positions"]
    assert opens, "could not locate a positions[] site in the loop"
    assert min(claims) < min(opens), (
        "claim_writer must run before the first positions[] touch — after "
        "it, the duplicate has already traded ((ho))")


def test_a_losing_claimant_stands_down_and_never_exits():
    loop = _while_true(_main_fn())
    branch = None
    for n in ast.walk(loop):
        if isinstance(n, ast.If):
            t = n.test
            if (isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not)
                    and getattr(t.operand, "id", "") == "_ok_writer"):
                branch = n
                break
    assert branch is not None, "no `if not _ok_writer:` stand-down branch"
    body_dump = ast.dump(ast.Module(body=branch.body, type_ignores=[]))
    assert "SystemExit" not in body_dump and "sys_exit" not in body_dump, (
        "the stand-down branch must idle, never exit — restartPolicy=always "
        "turns an exit into a crash-loop")
    assert any(isinstance(x, ast.Continue) for b in branch.body
               for x in ast.walk(b)), "stand-down must `continue` the loop"
    calls = [getattr(c.func, "id", getattr(c.func, "attr", ""))
             for b in branch.body for c in ast.walk(b)
             if isinstance(c, ast.Call)]
    assert "_standby_key" in calls, (
        "the loser reports on its OWN :standby key ((ic)), never the row")
    banned = {"publish", "publish_paper_trade", "snapshot_equity"}
    assert not banned & set(calls), (
        f"a standing-down container must not publish: {banned & set(calls)}")


# ------------------------------------------------- 4. exits outside the fetch
def test_mirror_exit_is_not_gated_on_the_reference_fetch():
    """(nm): a dark index feed must not suspend the price stop. MUTATION:
    wrap the manage block in `if ref:` -> RED."""
    fn = _main_fn()
    called = False
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and getattr(n.test, "id", None) in (
                "ref", "fund"):
            inside = [getattr(c.func, "id", getattr(c.func, "attr", ""))
                      for c in ast.walk(n) if isinstance(c, ast.Call)]
            assert "mirror_exit" not in inside, (
                "mirror_exit is nested inside a data-fetch gate — a dark "
                "reference would suspend every stop")
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "mirror_exit":
            called = True
    assert called, "main() never evaluates mirror_exit"


def test_a_dark_reference_still_fires_the_price_stop():
    pos = {"coin": "X", "side": "long", "ghost_side": "short",
           "entry": 100.0, "ghost_entry": 100.0, "notional": 80.0,
           "opened_ts": 0.0, "last_px": 100.0}
    assert kelly.mirror_exit(pos, None, 94.9, 94.9, 1.0) == "stop"
    assert kelly.mirror_exit(pos, None, 100.0, 100.0, 7200.0) == "maxhold"


# --------------------------------------------------------------- 5. env-only
def test_no_tuning_lane_exists():
    """The (hm) single-policy clock is structural: no fleet_tuning import,
    no get_lever/write_levers call anywhere in the module."""
    for n in ast.walk(TREE):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in n.names]
            mod = getattr(n, "module", "") or ""
            assert "fleet_tuning" not in names and "fleet_tuning" not in mod, (
                "env-only book: fleet_tuning must not be imported")
        if isinstance(n, ast.Call):
            assert getattr(n.func, "attr", "") not in (
                "get_lever", "write_levers"), (
                "env-only book: no tuning-lane read/write may exist")


# ------------------------------------------------------------ 6. the roster
def test_the_refusals_stay_on_the_record():
    """A refuted mirror family stays DECLARED with its reason — deleting the
    refusal is how a refuted idea gets rebuilt. MUTATION: drop brkfade ->
    RED."""
    r = kelly.MIRROR_ROSTER
    assert r["snapfade"]["status"] == "live"
    assert r["brkfade"]["status"] == "refused" and "P=0.7" in r["brkfade"]["why"]
    assert r["dipfade"]["status"] == "waiting" and "I16" in r["dipfade"]["why"]
    assert r["impulse_cont"]["status"] == "owned" and "douglas" in (
        r["impulse_cont"]["why"])
    ex = kelly.build_extra({}, {}, [], 0.0, 0.0, 60.0)
    assert ex["roster"] is r, "the roster must publish every loop"


def test_the_mirrors_own_stop_is_inside_the_gate_bar():
    """(gv): the stop reconciles with the 15% go-live drawdown bar; also
    registered in test_stop_vs_gate.STOPS."""
    assert 0 < kelly.MY_HARD_STOP < 0.15


def test_venue_refusal_is_loud():
    """VENUE != lighter_shadow raises SystemExit in main() — the shadow book
    must never silently run against another venue."""
    fn = _main_fn()
    raises = [n for n in ast.walk(fn) if isinstance(n, ast.Raise)]
    assert any("SystemExit" in ast.dump(r) for r in raises), (
        "main() must refuse a foreign VENUE with a loud SystemExit")
