"""[2026-09-02 (wo)] THE SHADOW TWIN IS A CONTROL ARM AGAIN.

The judge read every family pair `unjudgeable:policy_mismatch` on
`scan_order` — live=diversified, shadow=list — so the ONLY path from a
shadow candidate to real money had no pair it could open. Measured on 👩 mum
since 25-Aug: 36 of 53 live entries matched a shadow entry (same coin, ±2h),
7 coins live-only, 4 shadow-only. Material, so the fix is the port, not a
waiver. One owner now: fleet_bus.diversified_order; the live host aliases it.

Mutations that turn these red: put `for coin in b.coins` back; stamp "list"
while scanning diversified (or vice versa); let the env kill switch stamp
"diversified"; make the live host carry its own copy of the rule.
"""
import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_bus as fb                 # noqa: E402
import lighter_avo_live_bot as A       # noqa: E402
import lighter_family_bot as F         # noqa: E402

pytestmark = pytest.mark.autonomy


def _rets(n=60, seed=1.0):
    return {i: ((-1) ** i) * 0.01 * seed for i in range(n)}


def test_one_owner_the_live_host_aliases_fleet_bus():
    assert A.diversified_order is fb.diversified_order


def test_the_shadow_host_offers_the_least_correlated_candidate_first(monkeypatch):
    monkeypatch.setattr(F, "SHADOW_SCAN_ORDER", "diversified")
    held = {"BTC": _rets()}
    twin = {"ETH": _rets()}                          # rho +1 with BTC
    anti = {"XAU": {k: -v for k, v in _rets().items()}}  # rho -1
    rets = {**held, **twin, **anti}
    assert F.shadow_scan_order(["ETH", "XAU"], ["BTC"], rets) == ["XAU", "ETH"]
    assert F.shadow_scan_order_stamp() == "diversified"


def test_the_kill_switch_restores_list_order_and_stamps_it(monkeypatch):
    monkeypatch.setattr(F, "SHADOW_SCAN_ORDER", "list")
    rets = {"BTC": _rets(), "ETH": _rets(),
            "XAU": {k: -v for k, v in _rets().items()}}
    assert F.shadow_scan_order(["ETH", "XAU"], ["BTC"], rets) == ["ETH", "XAU"]
    assert F.shadow_scan_order_stamp() == "list"


def test_a_dark_read_returns_the_list_unchanged(monkeypatch):
    monkeypatch.setattr(F, "SHADOW_SCAN_ORDER", "diversified")
    assert F.shadow_scan_order(["A", "B"], [], {}) == ["A", "B"]
    assert F.shadow_scan_order(["A", "B"], ["Z"], None) == ["A", "B"]


def test_the_scan_loop_iterates_the_ordered_offer_not_b_coins():
    src = open(F.__file__).read()
    assert "for coin in shadow_scan_order(b.coins" in src
    assert "            for coin in b.coins:\n                bars = cache.get(coin" not in src


def test_the_stamp_and_the_loop_read_one_constant():
    """AST: both helpers reference SHADOW_SCAN_ORDER and nothing else decides."""
    tree = ast.parse(open(F.__file__).read())
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
           and n.name in ("shadow_scan_order", "shadow_scan_order_stamp")}
    assert set(fns) == {"shadow_scan_order", "shadow_scan_order_stamp"}
    for fn in fns.values():
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        assert "SHADOW_SCAN_ORDER" in names, fn.name


def test_the_policy_stamp_site_uses_the_stamp_helper():
    src = open(F.__file__).read()
    assert 'policy_stamp(self.s, "lighter_shadow",\n' \
           '                                                  shadow_scan_order_stamp(),' in src
    assert '"lighter_shadow",\n                                                  "list",' not in src
