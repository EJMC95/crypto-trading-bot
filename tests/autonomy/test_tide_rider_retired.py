"""🌊 Tide Rider's retirement, pinned in all THREE places it has to hold.

DECISION (2026-08-01, (ie), operator: *"full permission to go ahead with your
advisements"*). Measured over the book's whole 22-day life:

    venue_orders   9 buys, ZERO sells        paper_trades   0 closes
    holding 6 of 6 (AT CAP)                  33% of the fleet-wide long budget
    fleet-allocation claim: none             only price exit: a 35% stop

`(hk)`'s universe widening is the argument FOR retiring, not against: it worked
on the ENTRY side only — 5 of those 9 lifetime buys landed in the two days
after it shipped — so the book now fills ~12x faster and still cannot exit. A
one-way ratchet reaches its cap sooner and parks there. And its 35% stop is
2.3x the 15% go-live drawdown bar ((gv)), so it can never clear the gate that
governs real money however long it runs.

WHY THREE PLACES, AND WHY ORDER MATTERS. `RETIRED_ROWS` hides the card;
`LEGACY_BOTS` prunes the frozen row; the bot's own guard stops it publishing.
Doing fewer than all three is the documented failure — the repo's own prior
notes on this exact book said the -lshadow twin could NOT be listed *because*
its service was still running and "the row simply returns". Pruning is also
what actually returns the 6 long slots: `fleet_risk` counts open longs from the
bot_pnl row, so a hidden-but-present row keeps consuming the budget invisibly
(the 14-Jul phantom-holdings incident that pinned the light RED for hours).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BOT = ROOT / "lighter_trend_bot.py"
DASH = ROOT / "pnl_dashboard.py"
CLEANUP = ROOT / "cleanup_legacy_bots.py"

ROW = "crypto-trend-daily-lshadow"
OVERRIDE = "TIDE_RIDER_RETIRED_OVERRIDE"


def _string_set(src, name):
    """The names inside a module-level `NAME = {...}` / `NAME = [...]` literal.

    Parsed with `ast`, not by scanning to the closing bracket: these blocks are
    heavily commented and the comments contain dated tags like
    `# [2026-07-14 GHOST-EXPOSURE CLEANUP]`, so a text scan stops at the `]`
    inside a COMMENT and silently returns a truncated set. That is the
    "page-wide substring scan is not a structural claim" trap, and it produced
    a false FAILURE here on the first run of this file.
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
    """Hiding is not retiring. The prune is what frees the long budget."""
    assert ROW in _string_set(CLEANUP.read_text(), "LEGACY_BOTS"), (
        f"{ROW} is not in LEGACY_BOTS — the frozen row survives, and "
        "fleet_risk keeps counting its 6 longs against the fleet budget")


def test_the_bot_idles_and_never_exits():
    """`restartPolicy=always` turns a `sys.exit` into a permanent crash-loop —
    the Trail Blazer pattern, and (ib) re-learned it on 28-Jul when a NameError
    crash-looped both carry containers for 25.6h. The guard must SLEEP."""
    src = BOT.read_text()
    i = src.index(OVERRIDE)
    block = src[i:i + 1400]
    assert "while True:" in block and "time.sleep" in block, (
        "the retirement guard must IDLE, not exit — an exit crash-loops")
    assert "sys.exit" not in block and "SystemExit" not in block, (
        "the retirement guard must never raise SystemExit")


def test_the_guard_runs_before_any_venue_work():
    """A guard placed after the broker is built has already made venue calls.
    It must precede `venue_context`, the first thing that reaches the venue."""
    src = BOT.read_text()
    assert src.index(OVERRIDE) < src.index("venue_context("), (
        "the retirement guard must sit BEFORE venue_context — otherwise it "
        "idles a bot that has already connected and published")


def _printed_strings(src):
    """Every string literal that is actually an argument to `print(...)`.

    AST, not a file-wide substring scan. A mutation that stripped the override
    out of the LOG LINE survived a text search, because the same token also
    appears in the comment right above it — the exact trap this repo has now
    hit four times ("a page-wide substring scan is not a structural claim").
    What the operator reads is the print, so the print is what must be tested.
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
    LIGHTER-ONLY idiom (GAPSCOUT_RETIRED_OVERRIDE and friends), and the way
    back must be in the message the operator actually sees (I8: a detector
    must name the object the operator can act on)."""
    src = BOT.read_text()
    assert re.search(rf'{OVERRIDE}[^\n]*\)\s*\.strip\(\)\.lower\(\)', src), (
        "the override must be read as a normalised env string")
    printed = " ".join(_printed_strings(src))
    assert f"{OVERRIDE}=run" in printed, (
        "the LOG LINE must name the exact variable that resurrects the bot; "
        "naming it only in a comment leaves the operator reading a stop with "
        "no stated way back")


def test_the_live_row_stays_retired_too():
    """The 17-Jul retirement of the LIVE row must not be undone by this edit;
    both rows are retired for different reasons and both must hold."""
    for store, name in ((DASH.read_text(), "RETIRED_ROWS"),
                        (CLEANUP.read_text(), "LEGACY_BOTS")):
        assert "crypto-trend-daily-lighter" in _string_set(store, name), name
