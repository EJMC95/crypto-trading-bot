"""[2026-09-02 (wy)] THE LIGHT IS PER COHORT, AND REAL MONEY READS ITS OWN.

Measured on the live bus 2-Sep 09:06Z: pooled `long_positions` 21 against a
budget of 20 -> light RED in 76 of 288 five-minute samples (26% of the day).
The 21 were 👩 mum-live 12 + 🙏 avo-live 3 (real) + 🎫 the shadow taker 6
(paper); the LIVE cohort read 15/20 the whole time. Two consumers of that red:

  * `evidence_board.synthesize_live`'s UP ladder for `live.*.clip_scale`
    requires the light GREEN — a real-money up-scale gated on paper longs;
  * the shadow cohort's count (mum's twin 10 + avo's twin 5 + taker 6 = 21)
    against the pooled budget, so the two CONTROL twins vetoed each other on
    positions their live arms never see, with no budget of their own to move.

(wp) split the veto READS by cohort and left the LIGHT pooled. This pins the
other half: `cohorts.<c>.light` per cohort on its OWN budget (shadow's now
env-separable), the board's live ladder reading the live cohort, and the organ
board asking "at budget?" of each population rather than the mixture.

Mutations that turn these red: cohort_view scoring both cohorts on the pooled
budget; `_live_light` reading the pooled light when a live one is published;
c_fleet_risk grading the pooled count when cohorts are present.
"""
import copy
import importlib.util
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import evidence_board as eb   # noqa: E402
import fleet_risk as fr       # noqa: E402

pytestmark = pytest.mark.autonomy

_spec = importlib.util.spec_from_file_location(
    "organ_board", os.path.join(ROOT, "scripts", "organ_board.py"))
OB = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("organ_board", OB)
_spec.loader.exec_module(OB)


def test_each_cohort_is_lit_on_its_own_budget(monkeypatch):
    monkeypatch.setattr(fr, "LIVE_LONG_BUDGET", 20)
    monkeypatch.setattr(fr, "SHADOW_LONG_BUDGET", 20)
    v = fr.cohort_view({"live": 15, "shadow": 21})           # the 2-Sep reading
    assert v["live"] == {"long_positions": 15, "long_budget": 20, "light": "red" if 15 >= 20 else fr.light_for(15, 20)}
    assert v["live"]["light"] != "red" and v["shadow"]["light"] == "red"
    # the shadow budget is its OWN number: raising it moves only the shadow light
    monkeypatch.setattr(fr, "SHADOW_LONG_BUDGET", 24)
    v2 = fr.cohort_view({"live": 15, "shadow": 21})
    assert v2["shadow"]["long_budget"] == 24 and v2["shadow"]["light"] != "red"
    assert v2["live"] == v["live"]
    # the ladder is the SAME one the pooled light uses — one rule, two populations
    assert v2["shadow"]["light"] == fr.light_for(21, 24)
    # an absent cohort reads 0, never a crash and never the other cohort's count
    assert fr.cohort_view({})["live"]["long_positions"] == 0
    assert fr.cohort_view(None)["shadow"]["light"] == "green"


def test_the_board_default_shadow_budget_is_the_pooled_one():
    # behaviour-neutral at ship: nothing moves until the env is set on purpose
    assert fr.SHADOW_LONG_BUDGET == fr.LONG_BUDGET


def test_real_money_reads_the_live_cohorts_light():
    pooled_red = {"updated": "x", "ttl_sec": 900, "light": "red",
                  "long_positions": 21, "long_budget": 20,
                  "cohorts": {"live": {"long_positions": 15, "long_budget": 20, "light": "yellow"},
                              "shadow": {"long_positions": 21, "long_budget": 20, "light": "red"}}}
    assert eb._live_light(pooled_red) == "yellow"
    # pre-(wy) payload: no cohort light -> the pooled light, exactly as before
    old = {k: v for k, v in pooled_red.items() if k != "cohorts"}
    assert eb._live_light(old) == "red"
    junk = copy.deepcopy(pooled_red)
    junk["cohorts"]["live"]["light"] = "purple"
    assert eb._live_light(junk) == "red"          # junk never opens a gate
    assert eb._live_light(None) is None
    src = open(os.path.join(ROOT, "evidence_board.py")).read()
    ladder = src.split("def synthesize_live(", 1)[1].split("def synthesize_expand(", 1)[0]
    assert '_live_light(fleet_risk)) == "green"' in ladder
    assert 'fleet_risk.get("light")) == "green"' not in ladder, "the live ladder read the pooled light"


def _risk_row(payload):
    bus = copy.deepcopy(OB.FIXTURE_BUS)
    bus["fleet_risk"].update(payload)
    return {r["organ"]: r for r in OB.grade(bus, OB.FIXTURE_PNL, OB.FIXTURE_NOW)}["fleet_risk"]


def test_the_organ_board_asks_at_budget_of_each_cohort():
    both_under = _risk_row({"long_positions": 21, "long_budget": 20, "light": "red",
                            "cohorts": {"live": {"long_positions": 15, "long_budget": 20, "light": "yellow"},
                                        "shadow": {"long_positions": 6, "long_budget": 20, "light": "green"}}})
    # pooled 21/20 is a mixture, not a bind. (`fixed?` is the board's own
    # relabel of a clean row whose 2-Sep baseline read watch — not a state.)
    assert both_under["state"] in ("ok", "fixed?"), both_under
    shadow_at = _risk_row({"long_positions": 21, "long_budget": 20, "light": "red",
                           "cohorts": {"live": {"long_positions": 15, "long_budget": 20, "light": "yellow"},
                                       "shadow": {"long_positions": 21, "long_budget": 20, "light": "red"}}})
    assert shadow_at["state"] == "watch" and "AT BUDGET: shadow" in shadow_at["why"], shadow_at
    # pre-(wp) payload (the fixture itself): the pooled rule still grades it
    assert _risk_row({"long_positions": 20, "long_budget": 20})["state"] == "watch"
