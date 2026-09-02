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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
