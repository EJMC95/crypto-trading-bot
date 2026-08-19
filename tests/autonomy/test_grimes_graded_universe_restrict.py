"""[19-Aug (qh)] 📐 GRIMES MAY NOT ENTER A COIN ITS OWN GATE NEVER GRADED.

`(om)` fixed the flapping gate by grading the founding study's fixed 18
(GATE_COINS) while trading kept following the live `resolve_universe()` — and
published the hazard that split created, in its own words: "`ungraded`
non-empty means the book can enter coins its own gate never tested — the one
direction that matters." Measured 19-Aug before this shipped: 100% of 24h bus
samples carried >=2 gate-ungraded coins in the traded universe (APEX in every
sample), live `gate_drift.ungraded = [APEX, VVV]`. The restrict's cost is
$0.00 in both halves — the book has zero trades ever — so this closes the
published hazard for free.

Pinned here, in priority order:
  1. the entry loop SKIPS a non-GATE_COINS coin, counts it in
     `ungraded_skip`, and does so BEFORE the candle fetch (a skipped coin
     must not cost a REST call);
  2. a HELD coin is never skipped (the held check runs first — exits and
     position management are untouched by the restrict);
  3. `GRIMES_TRADE_UNGRADED=1` reverts without a deploy;
  4. the census key exists from the literal, so `ungraded_skip: 0` and
     "restrict off" are never byte-identical (the (qg) lesson).
"""
import ast
import importlib
import os
import pathlib

import pytest

pytestmark = pytest.mark.autonomy


def _fresh(monkeypatch, **env):
    for k in ("GRIMES_TRADE_UNGRADED",):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import lighter_book_grimes_bot
    return importlib.reload(lighter_book_grimes_bot)


@pytest.fixture(autouse=True)
def _restore_module():
    yield
    os.environ.pop("GRIMES_TRADE_UNGRADED", None)
    import lighter_book_grimes_bot
    importlib.reload(lighter_book_grimes_bot)


def _entry_loop(tree):
    """The `for coin in universe:` node inside main's scan block."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.For) and isinstance(node.iter, ast.Name)
                and node.iter.id == "universe"
                and isinstance(node.target, ast.Name)
                and node.target.id == "coin"):
            return node
    raise AssertionError("entry loop not found — scan is broken, not clean")


def test_default_restricts_and_env_reverts(monkeypatch):
    g = _fresh(monkeypatch)
    assert g.TRADE_UNGRADED is False, "restrict must be the DEFAULT"
    assert g._GATE_SET == frozenset(g.GATE_COINS)
    g2 = _fresh(monkeypatch, GRIMES_TRADE_UNGRADED="1")
    assert g2.TRADE_UNGRADED is True, "the revert env must work without a deploy"


def test_skip_sits_between_held_check_and_candle_fetch():
    """Ordering is load-bearing twice: after `held` (a held coin is never
    skipped) and before the venue fetch (a skipped coin costs no REST call).
    AST, not substrings ((hm))."""
    import lighter_book_grimes_bot as g
    tree = ast.parse(pathlib.Path(g.__file__).read_text(encoding="utf-8"))
    loop = _entry_loop(tree)
    src_order = []
    for node in ast.walk(loop):
        if isinstance(node, ast.Subscript):  # census["..."] mentions
            try:
                key = node.slice.value if hasattr(node.slice, "value") else None
                if isinstance(key, str):
                    src_order.append((node.lineno, key))
            except Exception:  # noqa: BLE001
                pass
        if (isinstance(node, ast.Attribute) and node.attr == "candles"):
            src_order.append((node.lineno, "CANDLE_FETCH"))
    order = [k for _, k in sorted(src_order)]
    assert "ungraded_skip" in order, "the skip census bucket is not in the loop"
    assert order.index("held") < order.index("ungraded_skip"), \
        "held must be checked BEFORE the restrict — exits are untouched"
    assert order.index("ungraded_skip") < order.index("CANDLE_FETCH"), \
        "the restrict must run BEFORE the candle fetch"


def test_the_skip_is_gated_on_trade_ungraded_and_gate_set():
    """The skip's own condition must consult BOTH the revert env and
    membership — a skip keyed on only one of them either cannot be reverted
    or restricts nothing."""
    import lighter_book_grimes_bot as g
    tree = ast.parse(pathlib.Path(g.__file__).read_text(encoding="utf-8"))
    loop = _entry_loop(tree)
    for node in ast.walk(loop):
        if not isinstance(node, ast.If):
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if "TRADE_UNGRADED" in names:
            assert "_GATE_SET" in names, \
                "the skip must test membership of _GATE_SET"
            body_keys = {n.slice.value for n in ast.walk(node)
                         if isinstance(n, ast.Subscript)
                         and hasattr(n.slice, "value")
                         and isinstance(n.slice.value, str)}
            assert "ungraded_skip" in body_keys, \
                "the skip must COUNT what it refuses, never silently drop it"
            return
    raise AssertionError("no TRADE_UNGRADED-gated skip found in the entry loop")


def test_census_literal_carries_the_bucket():
    """`ungraded_skip: 0` must publish even when nothing was skipped — a
    bucket that appears only when it fires is byte-identical between
    'restrict off' and 'nothing to restrict' ((qg))."""
    import lighter_book_grimes_bot as g
    tree = ast.parse(pathlib.Path(g.__file__).read_text(encoding="utf-8"))
    found = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if "scanned" in keys and "held" in keys and "no_bars" in keys:
                found += 1
                assert "ungraded_skip" in keys, \
                    f"census-shaped dict at line {node.lineno} lacks " \
                    "ungraded_skip — the real literal and the selftest " \
                    "fixture must both carry it"
    assert found >= 2, f"expected the loop literal AND the selftest fixture, found {found}"
