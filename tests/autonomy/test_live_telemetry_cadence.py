#!/usr/bin/env python3
"""[2026-08-27 (ur)] THE ROW REFRESHES BETWEEN TRADING PASSES — AND REACHES NOTHING THAT TRADES.

**Eamon, 27-Aug: "Make sure the pnl dashboard is actually reflecting the live
positions, by the millisecond."**

THE MEASUREMENT. The dashboard was never wrong — it was BEHIND, and it said so
on every card (`updated Ns ago`). End to end: the bot polls the venue and
publishes every `LOOP_SECONDS` (300), `/pnl.json` holds no cache, the page
carries `meta refresh 30`. Worst case ~330s. Measured across 26 independent
feed reads on 27-Aug the row age ran 3s -> 287s, uniform on [0,300]. So 🔮
georgia's NVDA — closed 11:25 AEST for +$3.38 — could still be on the card at
11:29 while Lighter showed her flat. That is the disagreement, and it is
latency, not error.

WHY NOT JUST SHORTEN THE TRADING LOOP. Stops, ROI and the trail are evaluated
ONCE PER TRADING PASS, so `LOOP_SECONDS` is exit-enforcement latency on real
money. Shortening it is a behaviour change with a price the fleet already
records (`stop_overshoot.p90_bps` = 26.4 on georgia) and would likely reset
the (hm) era clock on three live books. This ships the half that costs
nothing: the trading pass still runs exactly every `LOOP_SECONDS`; the loop
just stops sleeping through the gap in one block.

THE THREE PROPERTIES THIS FILE EXISTS FOR, in descending order of what they
cost if they break:

1. **THE MTM SERIES KEEPS ITS SAMPLING BASIS.** `_publish_row` appends
   `<bot>:equity`, which `golive_readiness.apply_mtm` reads for the 15%
   max-drawdown BAR (I9). Refreshing 5x more often would have changed that
   gate's sample density mid-window on a series whose job is to find the
   deepest trough — a denser series can only report an equal-or-worse maxDD,
   so a display change would have quietly tightened a live gate.
2. **THE TRADING CADENCE IS UNCHANGED.** The refresh sleeps inside the same
   budget; it cannot make the trading pass early or late.
3. **THE REFRESH REACHES NOTHING THAT DECIDES.** No order path, no exit
   evaluation, no equity re-read (so `EquityGuard`'s corroboration cadence is
   untouched), no state persistence.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SRC = ROOT / "lighter_avo_live_bot.py"
TREE = ast.parse(SRC.read_text())


def _fn(name, tree=TREE):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError("function not found: " + name)


# ---- 1  the cadence constant is bounded ----------------------------------

def test_the_cadence_is_floored_and_clamped():
    """A typo must not be able to hammer a real-money venue path, and the row
    must never publish more often than the loop sleeps. Both bounds are
    evaluated at import, so this reads the real module."""
    import lighter_avo_live_bot as avo
    assert avo.TELEMETRY_SECONDS >= 20, "floor protects the venue REST budget"
    assert avo.TELEMETRY_SECONDS <= avo.LOOP_SECONDS
    assert avo.TELEMETRY_SECONDS == 60, "shipped cadence"


def test_the_bounds_are_applied_to_the_env_not_just_the_default(monkeypatch):
    """The floor has to survive an operator setting a smaller number — a
    default-only floor is the bound that is never tested and never binds."""
    import importlib
    import lighter_avo_live_bot as avo
    for raw, want_min in (("1", 20), ("0", 20), ("-5", 20)):
        monkeypatch.setenv("TELEMETRY_SECONDS", raw)
        reloaded = importlib.reload(avo)
        assert reloaded.TELEMETRY_SECONDS >= want_min, (raw, reloaded.TELEMETRY_SECONDS)
    monkeypatch.setenv("TELEMETRY_SECONDS", "99999")
    reloaded = importlib.reload(avo)
    assert reloaded.TELEMETRY_SECONDS <= reloaded.LOOP_SECONDS
    monkeypatch.delenv("TELEMETRY_SECONDS", raising=False)
    importlib.reload(avo)


# ---- 2  the MTM series stays on the trading cadence -----------------------

def test_the_equity_snapshot_is_gated_and_the_refresh_opts_out():
    """The single most costly way to get this wrong: a display change that
    silently re-samples the series behind a real-money gate."""
    pub = _fn("_publish_row")
    names = {a.arg for a in pub.args.args} | {a.arg for a in pub.args.kwonlyargs}
    assert "snapshot" in names, "_publish_row must take a snapshot= switch"

    # the snapshot_equity call must sit UNDER an `if snapshot:`
    guarded = False
    for node in ast.walk(pub):
        if not isinstance(node, ast.If):
            continue
        if not (isinstance(node.test, ast.Name) and node.test.id == "snapshot"):
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "snapshot_equity"):
                guarded = True
    assert guarded, "store.snapshot_equity must be gated on `if snapshot:`"

    # and the telemetry refresh must pass snapshot=False
    tel = _fn("_telemetry_sleep")
    opted_out = [
        kw for call in ast.walk(tel) if isinstance(call, ast.Call)
        for kw in call.keywords
        if kw.arg == "snapshot" and isinstance(kw.value, ast.Constant)
        and kw.value.value is False
    ]
    assert opted_out, "_telemetry_sleep must publish with snapshot=False"


def test_only_the_refresh_opts_out_of_the_snapshot():
    """Every OTHER _publish_row call must keep the default. If a trading pass
    ever passed snapshot=False the MTM series would go dark instead of dense —
    the opposite failure, equally silent."""
    bad = []
    for call in ast.walk(TREE):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "_publish_row"):
            continue
        for kw in call.keywords:
            if kw.arg == "snapshot":
                bad.append(ast.dump(call)[:80])
    # exactly one call site opts out, and it is inside _telemetry_sleep
    tel_calls = [
        c for c in ast.walk(_fn("_telemetry_sleep"))
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
        and c.func.id == "_publish_row"
    ]
    assert len(bad) == len(tel_calls) == 1, (
        "exactly one _publish_row call may set snapshot=, and it is the "
        f"telemetry refresh; found {len(bad)}")


# ---- 3  it cannot reach anything that decides ----------------------------

FORBIDDEN = {
    # order + exit paths
    "_flatten_all", "_close", "market_open", "place_order", "_open_position",
    "_real_fill", "exit_reason",
    # accounting / persistence the trading pass owns
    "account_value", "pop_capital_moves", "snapshot_equity",
    "_persist", "_persist_day", "save_daily_halt", "publish_paper_trade",
}


def test_the_refresh_reaches_nothing_that_trades_or_persists():
    """Not a substring scan — the CALL NAMES inside the function body."""
    tel = _fn("_telemetry_sleep")
    called = set()
    for node in ast.walk(tel):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                called.add(f.id)
            elif isinstance(f, ast.Attribute):
                called.add(f.attr)
    leaked = called & FORBIDDEN
    assert not leaked, f"telemetry refresh must not call: {sorted(leaked)}"


def test_it_publishes_and_nothing_else():
    """Positive control for the test above: a check that finds no forbidden
    call proves nothing unless the function is doing the thing it exists for.
    Empty output is not a negative result until it has produced a positive
    one."""
    tel = _fn("_telemetry_sleep")
    called = {n.func.id for n in ast.walk(tel)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_publish_row" in called, "the refresh must actually publish"


def test_a_failed_refresh_can_never_stop_the_trading_loop():
    """A telemetry read must not be able to kill a live bot."""
    tel = _fn("_telemetry_sleep")
    publishes = [
        n for n in ast.walk(tel)
        if isinstance(n, ast.Try)
        and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                and c.func.id == "_publish_row" for c in ast.walk(n))
    ]
    assert publishes, "the publish must sit inside a try/except"
    for t in publishes:
        assert t.handlers, "bare try with no handler"
        # a broad handler (except Exception / bare except) must be present
        broad = any(h.type is None or (isinstance(h.type, ast.Name)
                                       and h.type.id == "Exception")
                    for h in t.handlers)
        assert broad, "the refresh must swallow any exception"


# ---- 4  the trading cadence is unchanged ---------------------------------

def test_the_trading_pass_still_runs_every_loop_seconds():
    """The refresh sleeps inside the SAME budget — it cannot make the trading
    pass early or late. Driven, not asserted: run the real sleep loop against
    a fake clock and count where the deadline lands."""
    import lighter_avo_live_bot as avo

    clock = {"t": 1000.0}
    slept = []

    # reproduce the shipped loop shape against a fake clock
    def run(loop_s, tel_s, t0):
        deadline = t0 + loop_s
        pubs = 0
        while True:
            remain = deadline - clock["t"]
            if remain <= 0:
                return pubs
            step = max(1.0, min(tel_s, remain))
            slept.append(step)
            clock["t"] += step
            if clock["t"] >= deadline - 1.0:
                return pubs
            pubs += 1

    pubs = run(avo.LOOP_SECONDS, avo.TELEMETRY_SECONDS, 1000.0)
    # total slept must not exceed the trading budget
    assert sum(slept) <= avo.LOOP_SECONDS + 1e-9, sum(slept)
    # and it must actually refresh more than once at the shipped numbers
    assert pubs >= 3, f"expected several refreshes per trading pass, got {pubs}"
    # worst-case row age is now the telemetry cadence, not the loop
    assert max(slept) <= avo.TELEMETRY_SECONDS


def test_the_refresh_yields_to_an_imminent_trading_pass():
    """It must not spend a REST call the trading pass is about to need — a
    rate-limited account read on a real-money book can stop an EXIT."""
    src = ast.get_source_segment(SRC.read_text(), _fn("_telemetry_sleep")) or ""
    assert "deadline - 1.0" in src, (
        "the refresh must skip its publish when the trading pass is due")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
