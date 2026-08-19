"""[2026-08-18 (qo)] 🌾 CARRY'S PERSISTENCE GATE MOVED ON A MEASUREMENT —
PIN THE VALUE, THE ESCAPE HATCH, THE DECLARATION, AND THE BITE.

STUDY_FUNDING_LIFECYCLE_2026-08-15.md §4 (E4) measured per-episode net
MONOTONE INCREASING in entry persistence on this cell's own 205d tape:
P=1 −0.064% (enter-immediately −21.8%, t=−5.9) → P=6 +0.016% → P=12 +0.161%
(t=1.80, both halves positive) → P=24 +0.269% (n=8 only). The referee
reproduced it exactly, LAG-1 clean, and ruled it NOT denominator shrinkage
(TOTAL net also peaks at P=12). Hypothesis-grade (n=26, t < 2.0), stated —
which is exactly why the value must be pinned: a number this soft invites a
quiet "tidy-up" revert that would erase a measured +0.145%/episode delta
without anyone re-running the study.

The queue parked the move for the ~30-Aug docket day; the operator's 18-Aug
directive ("implement all operator queue items that make the fleet
improve/make more profit and win rate") pulled it forward at the cleanest
boundary the book offers — ZERO open positions, census `eligible 0` under the
new $1M floor. Era unchanged (ordinary entry tuning per (hc)).

Four pins, each mutation-verified:
  1. The default IS 12.0 — a silent revert to 6.0, or a constant rewrite
     that drops the env read, reddens.
  2. `CARRY_PERSIST_H` reverses it without a deploy — the escape-hatch
     contract every carry gate move ships with ((px) min_vol / flip grace).
  3. The ONLINE caps payload DECLARES `persist_h` — an unpublished gate is
     how the (lz)/(pf) class went undetected, and this gate now DIFFERS
     from 🏦 Rich Dad's 6h on the shared carry cell, so the declaration is
     what keeps the cell reads honest.
  4. The gate actually BITES at the new value: 9 hot hours (which cleared
     the old 6h gate) now lands in `waiting`; 13 clears. Tested through
     `scan_census`, whose `eligible` is already pinned byte-equal to the
     entry loop's real predicate by test_carry_scan_census.py.
"""
import ast
import importlib
import pathlib

import pytest

import funding_carry_bot as carry

pytestmark = pytest.mark.autonomy

_SRC = pathlib.Path(carry.__file__)

# The census fixtures' convention (test_carry_scan_census.py): explicit basis
# so nothing depends silently on which arm is configured.
H = 1095.0
BAR = 0.20
HOT = 0.0004
T0 = 1_785_600_000.0


def _reload_with(monkeypatch, value):
    """Reload the module under a controlled env, restoring it afterwards via
    the caller's second _reload_with(None) — reload mutates the module object
    in place, so every other test module's `carry` reference stays valid."""
    if value is None:
        monkeypatch.delenv("CARRY_PERSIST_H", raising=False)
    else:
        monkeypatch.setenv("CARRY_PERSIST_H", value)
    importlib.reload(carry)


def test_default_is_the_measured_twelve_hours(monkeypatch):
    _reload_with(monkeypatch, None)
    assert carry.PERSIST_H == 12.0, (
        "PERSIST_H default moved off the §4-measured P=12 — if this is "
        "deliberate, it needs its own measurement and changelog entry, "
        "not a revert")


def test_env_override_reverses_it_without_a_deploy(monkeypatch):
    try:
        _reload_with(monkeypatch, "6.0")
        assert carry.PERSIST_H == 6.0, (
            "CARRY_PERSIST_H no longer reaches the gate — the no-deploy "
            "escape hatch is the condition the ship rode on")
    finally:
        _reload_with(monkeypatch, None)
    assert carry.PERSIST_H == 12.0


def test_online_caps_declare_the_persistence_gate():
    """AST, not a substring scan (the (hm) lesson): the ONLINE publish's
    `caps` dict must map "persist_h" to the module constant itself, so the
    published value cannot drift from the one the gate runs."""
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    declared = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys
                if isinstance(k, ast.Constant)}
        # the online caps dict, identified by its own established fields —
        # the minimal standby caps ({max_positions, enter_apr}) is exempt
        # by the same deliberate-minimalism that exempts min_vol there
        if "flip_grace_h" not in keys:
            continue
        assert "persist_h" in keys, (
            "the online caps dict dropped persist_h — the entry gate must "
            "publish like the exit gate ((lz)/(pf)/(px) doctrine), and this "
            "gate differs from Rich Dad's on the shared cell")
        idx = next(i for i, k in enumerate(node.keys)
                   if isinstance(k, ast.Constant) and k.value == "persist_h")
        v = node.values[idx]
        assert isinstance(v, ast.Name) and v.id == "PERSIST_H", (
            "caps.persist_h must BE the module constant, never a retyped "
            "copy — a retyped constant is a constant that drifts ((gx))")
        declared.append(node)
    assert declared, "no online caps dict found (flip_grace_h key missing?)"


def test_nine_hot_hours_no_longer_clears_the_gate(monkeypatch):
    """The bite, at module default: what the old gate admitted now waits."""
    _reload_with(monkeypatch, None)
    fund = {"KAITO": {"rate": HOT, "vol": 3_011_700, "mark": 100.0}}
    c9 = carry.scan_census(fund, {}, {"KAITO": T0 - 9 * 3600}, T0, H, BAR)
    assert c9["waiting"] == 1 and c9["eligible"] == 0, c9
    assert c9["next"] == "KAITO", c9
    assert c9["next_eta_h"] == pytest.approx(3.0, abs=0.01), c9
    c13 = carry.scan_census(fund, {}, {"KAITO": T0 - 13 * 3600}, T0, H, BAR)
    assert c13["eligible"] == 1 and c13["waiting"] == 0, c13
