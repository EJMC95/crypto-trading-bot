#!/usr/bin/env python3
"""[2026-09-02 (wg)] 🔮 GEORGIA'S LIVE ARM IS RETIRED — Eamon's "retire +
reallocate to mum" call, on the fleet's OWN grader.

Her clean in-era sample (post the 26-Aug exit-parity fix) reads n=30, mean
-0.354%/trade, t=-1.70, maxDD 37.6% MTM — horizon `unreachable` (the in-era
upper bound -0.081% has already excluded a positive mean), burning ~-$6.4/day.
The standing v3 replacement grades negative too (shadow n=41, t=-1.58,
unreachable), so this is I17 keep-or-decide, not a tuning pass. Her ~$220
sub-account frees for 👩 mum — the fleet's only live book with a positive edge
lower bound (+0.366%/trade).

She shares the variant host with 👩 mum and 🙏 avo, so the retirement must be
BOOK-SCOPED. This file pins the three properties that cost real money if they
break:

1. SCOPED BY THE REGISTRY, NOT A HOST BRANCH. `live_arm_retired(BOT_ROW)` is
   True only for a row in `fleet_bus.RETIRED_LIVE_ARMS`; mum and avo are not in
   it, so they read False and trade untouched. A typo fails toward KEEP-TRADING.
2. ENTRIES ONLY, GRACEFUL. The host gates ENTRIES on `not _retired` and keeps
   the exit/flatten paths running (a book must always be able to CLOSE), and it
   never sys.exit (restartPolicy=always would crash-loop).
3. ONE OWNER OF THE FACT. The declaration lives in `fleet_bus` and the bot, the
   judge and impl-shortfall all read it — including the override, parsed one
   way, so the arm resurrects on BOTH services or neither.
"""
import ast
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fleet_bus as fb  # noqa: E402

LIVE = "freqtrade-georgia-lighter"
SHADOW = "freqtrade-georgia-lshadow"
HOST = ROOT / "lighter_avo_live_bot.py"


# ---- the fact, single-owned in fleet_bus ----------------------------------

def test_georgia_live_is_declared_retired_with_its_reason():
    spec = fb.RETIRED_LIVE_ARMS[LIVE]
    assert spec["override"] == "GEORGIA_LIVE_RETIRED_OVERRIDE"
    assert spec["successor"] == "freqtrade-mum-lighter"
    assert "unreachable" in spec["why"]
    assert fb.live_arm_retired(LIVE) is True


def test_the_shadow_twin_keeps_trading():
    """Retiring the LIVE arm; the shadow stays as the control (the (ta) rule)."""
    assert SHADOW not in fb.RETIRED_LIVE_ARMS
    assert fb.live_arm_retired(SHADOW) is False


def test_mum_and_avo_are_not_retired_by_georgia():
    """Book-scoping by construction: the two live winners on the same host must
    read live == not retired, or one bug halts real money on a winner."""
    for row in ("freqtrade-mum-lighter", "freqtrade-avo-maria-lighter"):
        assert row not in fb.RETIRED_LIVE_ARMS, row
        assert fb.live_arm_retired(row) is False, row


@pytest.mark.parametrize("val,retired", [
    ("run", False), ("1", False), ("true", False), ("RUN", False),
    ("", True), ("no", True), ("stop", True),
])
def test_the_override_resurrects_and_is_parsed_one_way(monkeypatch, val, retired):
    monkeypatch.setenv("GEORGIA_LIVE_RETIRED_OVERRIDE", val)
    assert fb.live_arm_retired(LIVE) is retired


# ---- the wiring in the host, AST-pinned -----------------------------------

def _host_tree():
    return ast.parse(HOST.read_text())


def test_the_host_computes_retired_from_live_arm_retired_of_BOT_ROW():
    """`_retired = _bus.live_arm_retired(BOT_ROW)` must exist — the registry is
    the source, never a hand-typed row name here."""
    src = HOST.read_text()
    calls = [n for n in ast.walk(_host_tree())
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "live_arm_retired"]
    assert calls, "host never calls live_arm_retired"
    assert any(any(isinstance(a, ast.Name) and a.id == "BOT_ROW" for a in c.args)
               for c in calls), "live_arm_retired must be called on BOT_ROW"
    assert "_retired = bool(_bus.live_arm_retired(BOT_ROW))" in src


def test_entries_are_gated_on_not_retired():
    """The master entry gate must include `not _retired`, so a retired book
    opens NOTHING — and `entries_shut` names it, so the row says why."""
    src = HOST.read_text()
    # the entries_ok assignment carries the retirement term
    gate = next((n for n in ast.walk(_host_tree())
                 if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "entries_ok"
                         for t in n.targets)), None)
    assert gate is not None, "entries_ok gate not found"
    assert "not _retired" in ast.unparse(gate.value), \
        "entries_ok must AND in `not _retired`"
    assert '"live_retired"' in src or "'live_retired'" in src


def test_the_host_never_sys_exits_on_retirement():
    """A retirement must stand DOWN, never exit — restartPolicy=always turns an
    exit into a crash-loop. The retirement path adds no SystemExit."""
    src = HOST.read_text()
    # the retirement is expressed as an entries gate + census reason, never a
    # raise near the _retired computation.
    assert "_retired" in src
    i = src.index("_retired = bool(")
    window = src[i:i + 1200]
    assert "SystemExit" not in window and "sys.exit" not in window, \
        "the retirement path must not exit the process"


# ---- the (wl) receipt: a bus-retired arm stamps extra.retired --------------
# The (ta) Farmer published `extra.retired.{since,why,open,override}` beside
# status=halted because `halted` is byte-identical between "lost 5% today" and
# "retired" (I1/I18); the (wg) registry mechanism skipped that stamp and the
# watchdog warned "halted (daily-loss rule)" at a retirement the next day.
# AST-pinned (a substring test is not a wiring test).

def _receipt_assign(tree):
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Subscript)
                and isinstance(node.targets[0].value, ast.Name)
                and node.targets[0].value.id == "payload"
                and isinstance(node.targets[0].slice, ast.Constant)
                and node.targets[0].slice.value == "retired"):
            return node
    return None


def test_a_bus_retired_arm_stamps_the_farmer_receipt_shape():
    node = _receipt_assign(_host_tree())
    assert node is not None, \
        "the host must stamp payload['retired'] for a bus-retired row"
    assert isinstance(node.value, ast.Dict), "the receipt is a dict literal"
    keys = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    assert {"since", "why", "open", "override"} <= keys, \
        f"the (ta) receipt shape is since/why/open/override — got {sorted(keys)}"


def test_the_receipt_is_gated_on_the_one_registry_and_forces_halted():
    tree = _host_tree()
    receipt = _receipt_assign(tree)
    gate = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.If)
                 and receipt in list(ast.walk(n))), None)
    assert gate is not None, "the receipt must sit inside an if, never stamp unconditionally"
    assert any(isinstance(n, ast.Name) and n.id == "_rspec"
               for n in ast.walk(gate.test)), \
        "the if must test _rspec itself — an always-true gate stamps every row"
    # inside the same branch, status is forced to the Farmer's published value
    assert any(isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "status"
                       for t in n.targets)
               and isinstance(n.value, ast.Constant)
               and n.value.value == "halted"
               for n in ast.walk(gate)), \
        "a retired arm must publish status='halted' beside the receipt"
    # and the condition rides _rspec, which is derived from the ONE
    # declaration: RETIRED_LIVE_ARMS.get(BOT_ROW) gated on live_arm_retired
    src = HOST.read_text()
    i = src.index("_rspec = ")
    window = src[i:i + 400]
    assert "RETIRED_LIVE_ARMS.get(BOT_ROW)" in window, \
        "the receipt spec must come from fleet_bus.RETIRED_LIVE_ARMS (one declaration)"
    assert "live_arm_retired(BOT_ROW)" in window, \
        "the receipt must be gated on the same accessor as the entry gate"


def test_the_receipt_fails_toward_not_stamping():
    """A bus error must not mislabel a LIVE row as retired — the handler
    degrades _rspec to None, mirroring the entry gate's keep-trading default."""
    tree = _host_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            assigns = [n for n in ast.walk(node)
                       if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "_rspec"
                               for t in n.targets)]
            if not assigns:
                continue
            handler_assigns = [n for h in node.handlers
                               for n in ast.walk(h)
                               if isinstance(n, ast.Assign)
                               and any(isinstance(t, ast.Name)
                                       and t.id == "_rspec"
                                       for t in n.targets)]
            if handler_assigns:
                assert all(isinstance(n.value, ast.Constant)
                           and n.value.value is None
                           for n in handler_assigns), \
                    "the except path must set _rspec = None, never a guess"
                return
    raise AssertionError("no try/except computing _rspec found in the host")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
