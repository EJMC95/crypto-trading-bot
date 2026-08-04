"""🧲 Snap Back's retirement, pinned in all THREE places it has to hold.

DECISION (2026-08-04, operator: *"full permission to go ahead with all
advancements"* — OPERATOR_QUEUE.md item 2, option A). Measured in the
golive-readiness payload the day of the decision:

    t = -2.97   n = 175   mean -0.281%/trade   BOTH halves negative
    (-$2.48 / -$2.56)     ~ -$1/day            100% `converged` exits
                                               since the widening

This was the strongest retire case in the fleet: not an undecidable book (the
Tide Rider shape, (if)) but a DECIDED one — decided against. The widened
adaptive gate enters at a percentile floored by `EXIT_BPS * ENTER_FLOOR_MULT`
and every close since exits `converged`, so the book books round trips whose
capture is structurally smaller than the noise producing them. And the growth
rail cannot restrict it: the binding entry floor `ENTER_FLOOR_MULT` is an
unregistered bare literal (the I18 class), while every lever the registry CAN
express — `disloc.enter_pct` down, `disloc.exit_bps` down,
`disloc.universe_n` up — LOOSENS a measured loser.

WHY THREE PLACES, AND WHY ORDER MATTERS — the (if) Tide Rider pattern exactly.
`RETIRED_ROWS` hides the card; `LEGACY_BOTS` prunes the frozen row;
the bot's own guard stops it publishing. Doing fewer than all three is the
documented failure ("hiding a row is not retiring it"), and the guard must
come FIRST or the row simply returns on the service's next publish. The prune
is what actually frees the book's held slots: readers of bot_pnl keep counting
a hidden-but-present row's positions invisibly (the 14-Jul phantom-holdings
incident). The Railway service stop is the operator's separate act — the
deploy workflow resurrects stopped services, so the CODE guard is the durable
half.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BOT = ROOT / "lighter_dislocation_bot.py"
DASH = ROOT / "pnl_dashboard.py"
CLEANUP = ROOT / "cleanup_legacy_bots.py"

ROW = "lighter-dislocation-lshadow"
OVERRIDE = "SNAPBACK_RETIRED_OVERRIDE"


def _string_set(src, name):
    """The names inside a module-level `NAME = {...}` / `NAME = [...]` literal.

    Parsed with `ast`, not by scanning to the closing bracket: these blocks are
    heavily commented and the comments contain dated tags like
    `# [2026-07-14 GHOST-EXPOSURE CLEANUP]`, so a text scan stops at the `]`
    inside a COMMENT and silently returns a truncated set — the trap the (if)
    test hit on its own first run.
    """
    import ast

    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        if not isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
            continue
        return {e.value for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    raise AssertionError(f"{name} is not a module-level string collection")


def test_the_row_is_hidden():
    assert ROW in _string_set(DASH.read_text(), "RETIRED_ROWS"), (
        f"{ROW} is not in RETIRED_ROWS — the dashboard card would still render")


def test_the_row_is_pruned():
    """Hiding is not retiring. The prune is what frees the book's slots."""
    assert ROW in _string_set(CLEANUP.read_text(), "LEGACY_BOTS"), (
        f"{ROW} is not in LEGACY_BOTS — the frozen row survives, and every "
        "reader of bot_pnl keeps counting its held positions")


def test_the_bot_idles_and_never_exits():
    """`restartPolicy=always` turns a `sys.exit` into a permanent crash-loop —
    the Trail Blazer pattern, re-learned by (ib) when a NameError crash-looped
    both carry containers for 25.6h. The guard must SLEEP."""
    src = BOT.read_text()
    i = src.index(OVERRIDE)
    block = src[i:i + 1000]
    assert "while True:" in block and "time.sleep" in block, (
        "the retirement guard must IDLE, not exit — an exit crash-loops")
    assert "sys.exit" not in block and "SystemExit" not in block, (
        "the retirement guard must never raise SystemExit")


def test_the_guard_runs_before_any_venue_work():
    """A guard placed after the broker is built has already made venue calls.
    It must precede `venue_context`, the first thing that reaches the venue —
    and in this bot it must also precede `load_state_required`, which blocks
    on Postgres at boot ((jd) seed guard): a retired book must not sit in a
    DB retry loop before discovering it is retired."""
    src = BOT.read_text()
    assert src.index(OVERRIDE) < src.index("venue_context("), (
        "the retirement guard must sit BEFORE venue_context — otherwise it "
        "idles a bot that has already connected and published")
    assert src.index(OVERRIDE) < src.index("load_state_required("), (
        "the retirement guard must sit BEFORE the boot-time state read")


def _printed_strings(src):
    """Every string literal that is actually an argument to `print(...)`.

    AST, not a file-wide substring scan: a mutation stripping the override out
    of the LOG LINE survives a text search because the same token appears in
    the comment right above it — the trap this repo has hit four times. What
    the operator reads is the print, so the print is what must be tested.
    """
    import ast

    out = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "print"):
            for a in ast.walk(node):
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append(a.value)
    return out


def test_the_retirement_is_reversible_and_says_so():
    """A stop with no documented way back is a deletion. The override is the
    LIGHTER-ONLY idiom (GAPSCOUT_RETIRED_OVERRIDE, TIDE_RIDER_RETIRED_OVERRIDE
    and friends), and the way back must be in the message the operator
    actually sees (I8: a detector must name the object the operator can act
    on)."""
    src = BOT.read_text()
    assert re.search(rf'{OVERRIDE}[^\n]*\)\s*\.strip\(\)\.lower\(\)', src), (
        "the override must be read as a normalised env string")
    printed = " ".join(_printed_strings(src))
    assert f"{OVERRIDE}=run" in printed, (
        "the LOG LINE must name the exact variable that resurrects the bot; "
        "naming it only in a comment leaves the operator reading a stop with "
        "no stated way back")


def test_the_disloc_levers_stay_registered():
    """The (if) precedent: a retired book's levers stay in the registry (and
    its BOOK_AUTHOR entry stays, inert) so a deliberate resurrection restores
    the growth rail's reach in one act instead of coming back unreachable —
    the (hk) defect. Deleting them would also orphan `fleet-tuning` payload
    history that names them."""
    import sys

    sys.path.insert(0, str(ROOT))
    import fleet_tuning

    for lever in ("disloc.enter_pct", "disloc.universe_n", "disloc.exit_bps"):
        assert lever in fleet_tuning.LEVERS, (
            f"{lever} was deleted from the registry — a resurrected book "
            "would come back with the growth rail unable to reach it")


def test_the_tide_rider_retirement_still_holds():
    """Two retirements now share this pattern; adding the second must not have
    disturbed the first (both lists are edited by hand, near each other)."""
    for store, name in ((DASH.read_text(), "RETIRED_ROWS"),
                        (CLEANUP.read_text(), "LEGACY_BOTS")):
        assert "crypto-trend-daily-lshadow" in _string_set(store, name), name
