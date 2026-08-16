#!/usr/bin/env python3
"""
[2026-08-16 (nm)] THE BOOKS COHORT'S STOP WAS NEITHER LIVE NOR RUNNING.

Two independent defects, both of which made a declared bracket not a bracket,
found on 🧘 book-douglas's first two closes (15-Aug) and shared verbatim by
the three PRICE books of the cohort (douglas / grimes / schwager):

  1. THE PRICE WAS FROZEN AT BOOT. The exit read
     `ctx.venue.funding_map()[coin]["mark"]`, which is
     `LighterClient.markets[sym]["last"]` — captured once by `_load_markets()`
     at CLIENT CONSTRUCTION and never refreshed (only `lighter_perp_sniper`
     calls `refresh_markets`; the books build their context once, outside the
     loop). So `bracket_exit` compared a boot-time price with itself.
     `venues/marks.py` has forbidden exactly this in its header since it was
     written: "NEVER a funding-map mark ... using it on a stop path would
     silently freeze the stop while the real price runs away."

  2. THE EXIT NEVER RAN WHEN THE FUNDING FETCH WAS DARK. The whole management
     block sat inside `if fund:`, so a failed/empty funding call suspended
     every stop while every position stayed open.

MEASURED (the incident these tests name): both Douglas closes recorded entry
prices OUTSIDE the venue's real hourly bar at the moment of entry —
ROBO 0.017707 against a 12:00 bar of [0.014507, 0.014938] (21% above the whole
hour's high; matches ~09:00), LINK 9.15316 against an 03:00 bar of
[9.53046, 9.74586] (matches ~01:00). Both realised ~3.5x their declared 1R
stop (`sample20.expectancy_r = -3.514`), and ROBO's REAL 12:04->13:35 move was
-6.7% — inside its own 7.03% stop — while the book booked -23.2%.

These are STRUCTURAL (AST) assertions, not substring scans: a page-wide
`in`-check passes against a hand-rolled copy and fails on a comment that
merely mentions the thing (the standing lesson from `(hj)`/memory
"a-substring-test-is-not-a-wiring-test").
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# The three PRICE books. hull/kiyosaki are deliberately ABSENT: they are
# delta-neutral MODELLED funding books whose `position_pnl` takes no mark at
# all (structural, pinned by their own selftests), so they carry no price stop
# for this defect to reach. Adding them here would assert a property they do
# not have — and `scripts/study_exit_sweep.py` classifies them the same way.
PRICE_BOOKS = [
    "lighter_book_douglas_bot.py",
    "lighter_book_grimes_bot.py",
    "lighter_book_schwager_bot.py",
]

# The bracket/stop evaluator each book calls inside its management loop.
EXIT_FN = {
    "lighter_book_douglas_bot.py": "bracket_exit",
    "lighter_book_grimes_bot.py": "bracket_exit",
    "lighter_book_schwager_bot.py": "trend_exit",
}


def _main_fn(path: pathlib.Path) -> ast.FunctionDef:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError(f"{path.name}: no main()")


def _calls(node: ast.AST) -> list[str]:
    """Every called simple name inside `node`."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.append(f.id)
            elif isinstance(f, ast.Attribute):
                out.append(f.attr)
    return out


def _funding_gates(fn: ast.FunctionDef) -> list[ast.If]:
    """Every `if fund:` block in main()."""
    return [n for n in ast.walk(fn)
            if isinstance(n, ast.If)
            and isinstance(n.test, ast.Name) and n.test.id == "fund"]


def test_exit_is_evaluated_outside_the_funding_gate():
    """A dark funding fetch must not suspend the stop.

    MUTATION: move the management block back inside `if fund:` -> RED.
    """
    for name in PRICE_BOOKS:
        fn = _main_fn(ROOT / name)
        gates = _funding_gates(fn)
        assert gates, f"{name}: expected an `if fund:` scan gate to still exist"
        for gate in gates:
            inside = _calls(gate)
            assert EXIT_FN[name] not in inside, (
                f"{name}: {EXIT_FN[name]}() is nested inside `if fund:` — a "
                f"dark funding fetch would suspend every stop")
            assert "stop_marks" not in inside, (
                f"{name}: stop_marks() is nested inside `if fund:` — the "
                f"stop price must not depend on the funding endpoint")
        # ...and it must actually be called somewhere in main().
        allc = _calls(fn)
        assert EXIT_FN[name] in allc, f"{name}: {EXIT_FN[name]}() never called"
        assert "stop_marks" in allc, f"{name}: stop_marks() never called"


def test_no_price_path_reads_the_funding_map_mark():
    """The frozen-at-boot mark must not come back on any price path.

    Catches the literal defect: `fund.get(coin)["mark"]` / `f["mark"]`.
    MUTATION: restore any `.get("mark")` read -> RED.
    """
    for name in PRICE_BOOKS:
        tree = ast.parse((ROOT / name).read_text())
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "get" and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == "mark"):
                raise AssertionError(
                    f'{name}: reads .get("mark") — that is the funding map\'s '
                    f'boot-frozen last-trade price, banned on a stop path by '
                    f'venues/marks.py')


def test_entry_and_exit_price_come_from_the_live_book():
    """Entry and exit must both price off the order book.

    The entry matters as much as the exit: ROBO was BOOKED at 0.017707 when
    the venue's whole 12:00 bar was [0.014507, 0.014938], so the -23.2% loss
    was mostly the staleness gap, not a move the book lived through.
    MUTATION: drop the fresh_mid import or the entry call -> RED.
    """
    for name in PRICE_BOOKS:
        src = (ROOT / name).read_text()
        tree = ast.parse(src)
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module == "venues.marks":
                imported |= {a.name for a in n.names}
        assert {"fresh_mid", "stop_marks"} <= imported, (
            f"{name}: must import fresh_mid + stop_marks from venues.marks "
            f"(got {sorted(imported)})")
        assert "fresh_mid" in _calls(_main_fn(ROOT / name)), (
            f"{name}: fresh_mid() is imported but never called in main() — "
            f"the entry would still be priced at the boot-frozen mark")


def test_blind_stop_is_published_never_silent():
    """A held coin with no live book has an UNEVALUATED stop, and the payload
    must say so — `open: N` is otherwise byte-identical between "stops live"
    and "stops blind" (I1/I18, the 🎸 extreme-sleeve lesson).

    MUTATION: drop the census["stops_blind"] assignment -> RED.
    """
    for name in PRICE_BOOKS:
        tree = ast.parse((ROOT / name).read_text())
        found = False
        for n in ast.walk(tree):
            if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                    and n.value.id == "census"
                    and isinstance(n.slice, ast.Constant)
                    and n.slice.value == "stops_blind"):
                found = True
        assert found, f'{name}: census["stops_blind"] is never set'


def test_stop_marks_returns_live_mids_and_names_the_blind():
    """Behavioural, against a fake venue — the map is the ONE price a bracket
    may read, and an unreadable book is reported, never silently dropped.
    """
    from venues.marks import stop_marks

    class FakeVenue:
        def orderbook(self, coin):
            if coin == "GOOD":
                # deliberately UNSORTED: the Lighter REST snapshot is, and
                # top-of-book-by-index on an unsorted book is just some price.
                return {"bids": [(9.0, 1), (10.0, 1)],
                        "asks": [(12.0, 1), (11.0, 1)]}
            if coin == "EMPTY":
                return {"bids": [], "asks": []}
            raise RuntimeError("no book")

    stops, blind = stop_marks(FakeVenue(), {"GOOD", "EMPTY", "RAISES"})
    assert stops == {"GOOD": 10.5}, stops       # (max bid + min ask) / 2
    assert blind == ["EMPTY", "RAISES"], blind
    # a coin that cannot be priced must NOT appear with a falsy price — that
    # would read as 0.0 and evaluate every bracket as a total loss.
    assert "EMPTY" not in stops and "RAISES" not in stops


def test_hull_and_kiyosaki_are_excluded_on_purpose():
    """The two delta-neutral books carry no price stop; this pins WHY they are
    out of PRICE_BOOKS so a later reader does not 'complete' the cohort and
    assert a property they do not have."""
    for name in ("lighter_book_hull_bot.py", "lighter_book_kiyosaki_bot.py"):
        src = (ROOT / name).read_text()
        tree = ast.parse(src)
        fns = {n.name for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)}
        assert "position_pnl" in fns, (
            f"{name}: expected the delta-neutral position_pnl; if this book "
            f"grew a price term it belongs in PRICE_BOOKS")
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == "position_pnl":
                args = [a.arg for a in n.args.args]
                assert not any(a in ("mark", "px", "price") for a in args), (
                    f"{name}: position_pnl now takes a price ({args}) — it is "
                    f"no longer delta-neutral-modelled and must be covered "
                    f"by the stop-price tests above")


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(f"  ok {_name}")
    print("test_cohort_stop_price: all passed")
