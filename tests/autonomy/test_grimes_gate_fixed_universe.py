"""(om) 📐 Grimes's gate grades a FIXED set — trading still follows the live one.

THE DEFECT (oe). The gate is this book's entire thesis: a setup roster behind a
rolling replay gate. It replayed `resolve_universe()`, the set it would
actually trade — a top-18-BY-VOLUME ranking that CHURNS. Measured:

  * changing ONLY the coin set at a fixed as-of moved keltner's `t` across
    **3.82** (-2.55 .. +1.27) against a **0.5** bar, opening the gate in 4 of
    12 plausible draws;
  * on a FIXED set the bar was never crossed in 90 days (0 of 31 retests);
  * the live gate was nonetheless OPEN at t=+0.53.

So the gate could not distinguish "this setup's edge changed" from "the coin
list changed", and it was open on the second.

THE FIX, chosen by measurement (`scripts/study_grimes_gate_2026-08-16.py`):
grade `GATE_COINS`, the founding study's own fixed 18. Of four candidates it
was the only one that reached 100% verdict stability while KEEPING the shipped
gate's detection sensitivity — sub-sampling, a 240d window and a t>=1.0 bar all
needed twice the edge to fire, which is "raise the bar" in disguise and starves
the book toward an I17 retirement.

WHAT THESE TESTS GUARD — the four ways this fix could rot:
  1. the gate drifts back to grading the churning universe;
  2. `GATE_COINS` stops being fixed (someone points it at the scout);
  3. TRADING accidentally gets frozen to the graded set too — the fix is
     supposed to decouple the two, not collapse them;
  4. the graded-vs-traded gap stops being published, so a book entering coins
     its own gate never tested becomes invisible (I18).
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "lighter_book_grimes_bot.py"


def _mod():
    import lighter_book_grimes_bot as g
    return g


def _tree():
    return ast.parse(SRC.read_text(encoding="utf-8"))


def _retest_loop():
    """The `for coin in <X>:` that drives the retest replay — found by the
    bar-paging call inside it, not by position, so a refactor that moves the
    block does not silently pass."""
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.For):
            continue
        calls = {n.func.id for n in ast.walk(node)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        if "_paged_bars" in calls:
            return node
    raise AssertionError("retest bar-paging loop not found")


def test_the_gate_grades_the_fixed_set_not_the_traded_one():
    loop = _retest_loop()
    assert isinstance(loop.iter, ast.Name), \
        f"retest iterates {ast.dump(loop.iter)[:60]} — expected a plain name"
    assert loop.iter.id == "GATE_COINS", (
        f"the gate replays `{loop.iter.id}`; grading the churning traded "
        "universe is the (oe) defect")


def test_gate_coins_is_fixed_and_never_resolved_live():
    g = _mod()
    assert list(g.GATE_COINS) == list(g.DEFAULT_COINS)
    assert len(g.GATE_COINS) >= 10
    # it must be a module-level literal-derived constant, not a call into the
    # scout — a GATE_COINS that resolves live is the defect wearing a new name
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "GATE_COINS"
                for t in node.targets):
            calls = {n.func.id for n in ast.walk(node.value)
                     if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name)}
            assert "resolve_universe" not in calls, \
                "GATE_COINS must not call resolve_universe"
            return
    raise AssertionError("GATE_COINS assignment not found")


def test_trading_still_follows_the_live_universe():
    """The fix decouples grading from trading. Freezing BOTH would silently
    shrink the book to a stale list."""
    src = SRC.read_text(encoding="utf-8")
    assert "resolve_universe(" in src, "the live universe resolver is gone"
    g = _mod()
    # the resolver must still admit coins outside the graded set (held-coin
    # union is the (hk) rule), or trading has been frozen to GATE_COINS
    out = g.resolve_universe({"NOTACOIN"})
    assert "NOTACOIN" in out, \
        "resolve_universe no longer unions held coins — trading got frozen"


def test_the_graded_vs_traded_gap_is_published():
    g = _mod()
    d = g.gate_drift(["BTC", "WIF"])
    assert d["ungraded"] == ["WIF"], d
    assert d["overlap"] == 1 and d["graded"] == len(g.GATE_COINS)
    # ...and it reaches the payload, or nobody can see the drift
    ex = g.build_extra({"scanned": 1}, {}, {}, 0.0, 0.0,
                       drift=g.gate_drift(["BTC", "WIF"]))
    assert ex.get("gate_drift", {}).get("ungraded") == ["WIF"], \
        "gate_drift missing from the published extra (I18)"


def test_drift_is_empty_when_traded_equals_graded():
    g = _mod()
    d = g.gate_drift(g.GATE_COINS)
    assert d["ungraded"] == [] and d["untraded"] == []
    assert d["overlap"] == len(g.GATE_COINS)
