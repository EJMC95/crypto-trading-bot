"""The dashboard row: optional, honest, and driven against the REAL publisher.

A row for a bot that publishes nothing is a permanent "no data yet" ghost card
-- the dashboard's own source records that defect. So the row is earned by a
working publisher, and this file is what says it works."""
import os
import sys
import types

import pytest

from lighter_bots import fleet_publish as FP


@pytest.fixture(autouse=True)
def _reset():
    FP._WARNED[0] = False
    yield
    FP._WARNED[0] = False


def test_it_is_off_by_default_and_never_raises(monkeypatch):
    """A standalone checkout has no fleet and no database. Publishing must be
    a silent no-op there, not an import error in a trading loop."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert FP.enabled() is False
    assert FP.publish(row=FP.ROW_IDS["adaptive-ensemble"], mode="paper",
                      equity=1000.0, start_equity=1000.0, open_trades=0,
                      closed_trades=0, wins=0, losses=0) is False


def test_an_importable_store_with_no_database_is_still_off(monkeypatch):
    """The two halves are separate: an importable module with no DATABASE_URL
    returns False from every publish forever, and looks exactly like a
    publisher that is working. `enabled()` must require BOTH."""
    monkeypatch.setitem(sys.modules, "bot_pnl_store",
                        types.SimpleNamespace(publish=lambda **kw: True))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert FP.enabled() is False


def test_an_undeclared_row_id_is_refused(monkeypatch):
    """A row id is a SHARED key. A typo creates a SECOND row rather than
    updating the first, and two writers of one key is a fleet invariant this
    repo has already paid for."""
    monkeypatch.setitem(sys.modules, "bot_pnl_store",
                        types.SimpleNamespace(publish=lambda **kw: True))
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    assert FP.publish(row="adaptive-typo-lshadow", mode="paper", equity=1.0,
                      start_equity=1.0, open_trades=0, closed_trades=0,
                      wins=0, losses=0) is False


def test_a_paper_row_never_claims_to_be_online(monkeypatch):
    """`online` on a paper book is a claim it is not entitled to make, and the
    watchdog's own vocabulary has a word for this: `paper`."""
    seen = {}
    monkeypatch.setitem(sys.modules, "bot_pnl_store",
                        types.SimpleNamespace(
                            publish=lambda **kw: seen.update(kw) or True))
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    assert FP.publish(row=FP.ROW_IDS["adaptive-ensemble"], mode="paper",
                      equity=1050.0, start_equity=1000.0, open_trades=2,
                      closed_trades=7, wins=4, losses=3, day_pnl=12.5)
    assert seen["status"] == "paper"
    assert seen["extra"]["real_money"] is False
    assert seen["extra"]["mode"] == "paper"
    assert seen["extra"]["engine"] == "lighter_adaptive_ensemble_bots"
    assert seen["pnl_abs"] == pytest.approx(50.0)
    assert seen["pnl_pct"] == pytest.approx(0.05)
    assert seen["wins"] == 4 and seen["losses"] == 3


def test_a_failing_publish_never_breaks_the_trading_loop(monkeypatch):
    def boom(**kw):
        raise RuntimeError("database is on fire")
    monkeypatch.setitem(sys.modules, "bot_pnl_store",
                        types.SimpleNamespace(publish=boom))
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    assert FP.publish(row=FP.ROW_IDS["adaptive-ensemble"], mode="paper",
                      equity=1.0, start_equity=1.0, open_trades=0,
                      closed_trades=0, wins=0, losses=0) is False


def test_a_false_return_is_kept_not_discarded(monkeypatch):
    """The fleet has already paid for a persistence call whose False was
    thrown away for three days while the organ looked healthy off frozen
    state. The soak report carries the answer."""
    monkeypatch.setitem(sys.modules, "bot_pnl_store",
                        types.SimpleNamespace(publish=lambda **kw: False))
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    assert FP.publish(row=FP.ROW_IDS["adaptive-ensemble"], mode="paper",
                      equity=1.0, start_equity=1.0, open_trades=0,
                      closed_trades=0, wins=0, losses=0) is False


def test_the_runner_publishes_every_cycle_and_records_the_answer(monkeypatch):
    """END TO END through the REAL Runner, against the real publisher's
    signature -- not a hand-written fixture. A consumer tested against a
    payload it wrote itself is how four defects shipped green in this repo."""
    calls = []
    monkeypatch.setitem(sys.modules, "bot_pnl_store",
                        types.SimpleNamespace(
                            publish=lambda **kw: calls.append(kw) or True))
    monkeypatch.setenv("DATABASE_URL", "postgres://x")

    from conftest import make_runner
    runner = make_runner()
    runner.cycle(["BTC", "ETH"], now=1_700_000_000.0)
    assert calls, "the cycle did not publish"
    assert runner.published is True
    row = calls[-1]
    assert row["bot"] == FP.ROW_IDS["adaptive-ensemble"]
    assert row["status"] == "paper"
    assert row["extra"]["real_money"] is False
    for key in ("mode", "engine", "regime", "soak_days", "symbols"):
        assert key in row["extra"], key


def test_a_cycle_outside_the_fleet_still_completes(monkeypatch):
    """The no-op path, driven rather than assumed: with no fleet and no
    database the cycle must run to completion and simply report published
    False."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from conftest import make_runner
    runner = make_runner()
    out = runner.cycle(["BTC", "ETH"], now=1_700_000_000.0)
    assert out["published"] is False and runner.published is False
    assert "regime" in out and "equity" in out


def test_the_real_store_accepts_the_arguments_we_send(monkeypatch):
    """SIGNATURE PARITY against the fleet's ACTUAL `bot_pnl_store.publish`,
    bound with `inspect.signature`. The repo's own doc block once listed five
    parameters `publish()` does not take, and a bot that followed it raised
    TypeError at the call site inside its trading loop."""
    import inspect
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    store_path = os.path.join(root, "bot_pnl_store.py")
    if not os.path.exists(store_path):
        pytest.skip("standalone checkout: no fleet publisher to check against")
    import ast
    tree = ast.parse(open(store_path).read())
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "publish"), None)
    assert fn is not None, "bot_pnl_store.publish has moved or been renamed"
    accepted = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
    sent = {"bot", "status", "equity", "pnl_abs", "pnl_pct", "open_trades",
            "closed_trades", "wins", "losses", "pnl_daily", "extra"}
    assert sent <= accepted, f"we send arguments publish() rejects: {sent - accepted}"
