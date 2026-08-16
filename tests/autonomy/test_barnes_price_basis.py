#!/usr/bin/env python3
"""
[2026-08-16 (nw)] 🎸 BARNES PRICED ITS ONLY OPEN BOOK OFF A BOOT-FROZEN MARK.

The `(nm)` sweep fixed the three PRICE books and deliberately left Barnes: its
one LIVE sleeve (carry) is delta-neutral modelled, so `position_pnl` has no
price term for it and the frozen mark could not reach P&L. That reasoning was
right about the sleeve and wrong about the BOOK — measured 16-Aug, Barnes still
held **10 open `xsect` legs, its entire open book at −$10.22**, in the sleeve
`(nf)` retired and is winding to flat. `position_pnl` DOES add a price term for
non-carry sleeves, and Barnes had zero `fresh_mid` uses, so those ten legs were
being marked — and would have CLOSED — on `markets[sym]["last"]`, captured at
client construction and never refreshed.

The lesson worth keeping: **a retired sleeve is not an absent sleeve.** Reading
the code alone said "carry only, no price term, unaffected"; reading the live
payload said ten priced legs. `(nm)`'s scope was decided from the former.

TWO THINGS THIS FILE PINS THAT THE (nm) TESTS DO NOT:

  1. **Barnes's `if fund:` gate is CORRECT and must stay.** The price books had
     their exits moved OUT of it because a funding outage must not suspend a
     price stop. Barnes is the opposite case: the funding RATE drives accrual
     and the carry/extreme exits and refreshes every call, so with no `fund`
     there is genuinely nothing to compute. Copying the (nm) shape here would
     be cargo-culting a fix into a book that does not have the defect.

  2. **The price basis is stamped on every priced close.** The xsect legs close
     ACROSS this fix, so the sleeve's realised record spans two bases. Absent
     the stamp that is one indistinguishable mixture and `(nf)`'s −$9.56
     attribution cannot be split. ABSENT means pre-(nw)/frozen — never
     back-stamped onto old rows, which would be inventing evidence.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BARNES = ROOT / "lighter_band_barnes_bot.py"


def _tree():
    return ast.parse(BARNES.read_text())


def _main_fn(tree):
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_no_funding_map_mark_on_any_price_path():
    """MUTATION: restore any `.get("mark")` read -> RED."""
    for n in ast.walk(_tree()):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get" and n.args
                and isinstance(n.args[0], ast.Constant)
                and n.args[0].value == "mark"):
            raise AssertionError(
                'lighter_band_barnes_bot.py reads .get("mark") — the funding '
                "map's boot-frozen last-trade price, banned on a price path "
                "by venues/marks.py")


def test_live_book_is_the_price_source():
    """MUTATION: drop the venues.marks import or either call -> RED."""
    tree = _tree()
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "venues.marks":
            imported |= {a.name for a in n.names}
    assert {"fresh_mid", "stop_marks"} <= imported, (
        f"must import fresh_mid + stop_marks (got {sorted(imported)})")
    called = {n.func.id for n in ast.walk(_main_fn(tree))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "stop_marks" in called, "main() never calls stop_marks()"
    assert "fresh_mid" in called, (
        "main() never calls fresh_mid() — priced ENTRIES would still be "
        "booked at the frozen mark")


def test_the_funding_gate_stays_because_this_book_needs_it():
    """The (nm) shape must NOT be copied here.

    Barnes's accrual and its carry/extreme exits key on the funding RATE, so
    `if fund:` is a real dependency, not the defect it was in the price books.
    MUTATION: delete the `if fund:` gate -> RED.
    """
    gates = [n for n in ast.walk(_main_fn(_tree()))
             if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
             and n.test.id == "fund"]
    assert gates, (
        "the `if fund:` gate is gone — Barnes's accrual and carry/extreme "
        "exits read the funding rate; without it they compute on nothing")


def test_carry_is_still_delta_neutral_and_asks_for_no_price():
    """The price term must remain non-carry only. If carry ever grows one,
    every claim in this file's header stops being true.
    MUTATION: drop the sleeve check in position_pnl -> RED.
    """
    import lighter_band_barnes_bot as bb
    base = {"notional": 100.0, "accrued": 1.0, "fees": 0.25,
            "side": "long", "entry_mark": 10.0, "last_mark": 10.0}
    carry = dict(base, sleeve="carry")
    # a 50% price move must not move a carry leg's P&L by one cent
    assert bb.position_pnl(carry, 15.0) == bb.position_pnl(carry, 5.0)
    assert abs(bb.position_pnl(carry, 15.0) - (1.0 - 0.25)) < 1e-12
    # ...and MUST move a mark sleeve's
    xs = dict(base, sleeve="xsect")
    assert bb.position_pnl(xs, 15.0) > bb.position_pnl(xs, 5.0)


def test_priced_closes_stamp_the_basis_and_carry_does_not():
    """The stamp is what keeps (nf)'s attribution splittable across the fix.

    MUTATION: drop `price_basis`, or stamp it unconditionally (so carry rows
    claim a basis they have no price term for) -> RED.
    """
    src = BARNES.read_text()
    tree = _tree()
    close = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_close")
    keys = [k.value for n in ast.walk(close)
            if isinstance(n, ast.Dict)
            for k in n.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    assert "price_basis" in keys, '_close() never stamps "price_basis"'
    # it must be CONDITIONAL on the sleeve, not a bare constant
    for n in ast.walk(close):
        if (isinstance(n, ast.Dict)
                and any(isinstance(k, ast.Constant) and k.value == "price_basis"
                        for k in n.keys)):
            val = n.values[[k.value for k in n.keys].index("price_basis")]
            assert isinstance(val, ast.IfExp), (
                "price_basis must be conditional on the sleeve — a carry row "
                "has no price term and must not claim a basis")
    assert "back-stamped" in src, (
        "the never-back-stamp rule must stay written where the stamp is: an "
        "absent basis means pre-(nw)/frozen, and filling it in retroactively "
        "would be inventing evidence")


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("test_barnes_price_basis: all passed")
