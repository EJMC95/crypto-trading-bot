"""[2026-08-04 (iz)] The go-live grader's MTM reader must actually read.

The incident: `golive_readiness.equity_series` shipped calling
`store.load_history` — a method that has NEVER existed on `bot_pnl_store`
(the read side is `fetch_state_history`) — inside a blanket except that
returned []. Result: every one of 18 graded books published
`mtm_why: "no usable equity series"` while the series accrued healthily
underneath, and the MTM drawdown bar (ia) folded into the gate that governs
real money was structurally inert. The bug was invisible because the failure
artifact ("no usable series") was byte-identical to the legitimate thin-series
state the floors produce — a programming error wearing a declaration.

Class rule these tests close: a consumer's reference into another module's
API is verified against THAT MODULE, not against a fixture's idea of it
((hj): a consumer is tested against a payload its publisher built).
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bot_pnl_store  # noqa: E402
import golive_readiness as gr  # noqa: E402


def _store_attrs_used_by(func_name):
    """Every `store.<attr>` / `bot_pnl_store.<attr>` reference inside the named
    golive_readiness function, found by AST — so a rename on EITHER side of the
    seam reddens this test instead of silently returning []."""
    tree = ast.parse((ROOT / "scripts" / "golive_readiness.py").read_text())
    attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Name)
                        and sub.value.id in ("store", "bot_pnl_store")):
                    attrs.add(sub.attr)
    return attrs


def test_every_store_reference_in_equity_series_exists():
    attrs = _store_attrs_used_by("equity_series")
    assert attrs, "equity_series no longer references the store — rewrite this test with it"
    missing = [a for a in attrs if not hasattr(bot_pnl_store, a)]
    assert not missing, (
        f"golive_readiness.equity_series references store.{missing} which "
        f"bot_pnl_store does not provide — this is the exact (iz) bug: the "
        f"blanket except will turn it into 'no usable equity series' on every "
        f"book while the series accrues underneath")


def test_equity_series_reads_the_publishers_shape_newest_first():
    # The REAL publisher (`fetch_state_history`) returns NEWEST FIRST
    # ("ORDER BY ts DESC", bot_pnl_store.py) as [{"ts": iso, "payload": dict}].
    # Feed the consumer that exact shape/order and require a correct,
    # time-ascending-equivalent drawdown: mtm_drawdown sorts internally, and
    # this pins that the pair survives the descending order the store emits.
    class _Store:
        @staticmethod
        def fetch_state_history(key, limit=800):
            assert key.endswith(":equity")
            return [  # newest first, exactly as the SQL orders it
                {"ts": "2026-08-03T00:00:00+00:00", "payload": {"equity": 990.0}},
                {"ts": "2026-08-02T00:00:00+00:00", "payload": {"equity": 940.0}},
                {"ts": "2026-08-01T00:00:00+00:00", "payload": {"equity": 1000.0}},
            ]

    pts = gr.equity_series("some-book", store=_Store)
    assert len(pts) == 3
    dd = gr.mtm_drawdown(pts, book_usd=1000.0)
    # peak 1000 (1-Aug) -> trough 940 (2-Aug): 6% drawdown, 2.0 days span.
    assert dd is not None
    assert abs(dd["max_dd_usd"] - (-60.0)) < 1e-9
    assert abs(dd["max_dd_frac"] - 0.06) < 1e-9
    assert abs(dd["days"] - 2.0) < 1e-9


def test_dark_db_still_fails_safe():
    # The fail-safe the bug hid behind must SURVIVE the fix: a store whose
    # read RAISES (dark DB) yields [], grading falls back to realised.
    class _Dark:
        @staticmethod
        def fetch_state_history(key, limit=800):
            raise RuntimeError("db unreachable")

    assert gr.equity_series("some-book", store=_Dark) == []
