"""[2026-09-02 (wy)] THE REPRODUCTION ORGAN BREEDS FOR THE LANE THE JUDGE RUNS.

Measured 2-Sep 09:06Z on the live bus: `xp-judge.lanes.serial_lane: "mum"`
(moved at (ww)); `strategy-incubator.proposal_capacity: {exhausted: true,
generatable: 4}` with eight Farmer offspring in lifetime memory — a lane whose
shadow arm (wt) retired the same day; `xp-queue.candidates: []`. The judge's
`candidate_pool` admits a queue proposal ONLY under its own lane's prefix, so
every offspring this organ could mint was structurally refused: the fleet's
only path from an experiment to real money was fed nothing.

Pins, each with the mutation that turns it red:
  * the lane is read off the judge's payload (hard-code "farmer" -> red);
  * a mum-lane proposal carries ONLY `xp.mum.*` levers inside their cages and
    never her registry default (widen the grid past the cage -> red);
  * THE CONSUMER ADMITS IT: `experiment_judge.candidate_pool` on its offline
    lane (mum, deterministic since (wv)) admits at least one incubator mum
    offspring that no static already tests, and refuses a Farmer offspring on
    that lane (a lane-unaware generator -> zero admitted -> red);
  * an unknown lane proposes nothing (a guess about which book the judge runs
    would spend a 7-day serial slot).
"""
import os
import sys
from datetime import datetime, timezone

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fleet_tuning as tuning              # noqa: E402
import strategy_incubator as inc          # noqa: E402
import experiment_judge as ej             # noqa: E402

pytestmark = pytest.mark.autonomy

MUM = {"lanes": {"serial_lane": "mum", "live": ["farmer", "mum"]}}


def test_the_lane_is_the_judges_own():
    assert inc.serial_lane_of(MUM) == "mum"
    assert inc.serial_lane_of({}) == "farmer"
    assert inc.serial_lane_of({"lanes": {"serial_lane": ""}}) == "farmer"
    assert set(inc.LANE_GENES) >= {"farmer", "mum"}


def test_mum_offspring_live_inside_her_cages_and_off_her_default():
    props = inc.funding_proposals(MUM, {})
    assert props, "the mum lane must mint something on a fresh ledger"
    assert len(props) <= 6
    for p in props:
        assert p["lane"] == "mum" and p["name"].startswith("xp-mum-"), p
        (lever, val), = p["levers"].items()
        assert lever.startswith("xp.mum."), lever
        spec = tuning.LEVERS[lever]
        assert spec["lo"] <= val <= spec["hi"], (lever, val)
        assert tuning.clamp(lever, val) == val
        assert val != spec["env_default"], "her shipped default is not an experiment"
    # the full grid: every mum allele is registry-legal in both directions
    for gene, (lever, grid) in inc.MUM_GENES.items():
        for allele in grid:
            assert tuning.clamp(lever, allele) == allele, (gene, allele)
    # both her knobs are represented — a single-gene lane is a single hypothesis
    assert {list(p["levers"])[0] for p in props} == set(l for l, _ in inc.MUM_GENES.values())


def test_the_judge_admits_mum_offspring_and_refuses_farmer_offspring_on_her_lane():
    assert ej.lane_prefix() == "xp.mum.", \
        "the judge's offline lane is mum since (wv); this pin assumes it"
    now = datetime.now(timezone.utc)
    mum_props = inc.funding_proposals(MUM, {})
    farmer_props = inc.funding_proposals({"lanes": {"serial_lane": "farmer"}}, {})
    queue = {"updated": now.isoformat(), "ttl_sec": 10800,
             "candidates": [{"name": p["name"], "levers": p["levers"]}
                            for p in mum_props + farmer_props]}
    pool = ej.candidate_pool(queue, now=now.timestamp())
    statics = {c["name"] for c in ej.CANDIDATES}
    admitted = [c for c in pool if c["name"] not in statics]
    assert admitted, "not one incubator offspring reached the judge's pool"
    assert all(list(c["levers"])[0].startswith("xp.mum.") for c in admitted), admitted
    assert not any(c["name"].startswith("xp-enter_apr") or c["name"].startswith("xp-take_profit")
                   for c in pool), "a Farmer offspring burned a slot on mum's lane"
    # the NOVEL alleles are the ones the statics do not test (signature dedup
    # drops the copies of rsi-32 / hold-720 / hold-2880 — that is the point).
    #
    # [(xl)] ASSERTED AS THE PROPERTY, NOT A NAME LIST. This pinned four exact
    # names, which encoded the emitter's ORDERING as well as its content — so
    # adding a gene to her pool failed it even though the behaviour improved.
    # Worse, a name list cannot express the thing that actually matters and
    # that (xl) had to fix: the emitter enumerated gene-by-gene under a cap,
    # so genes declared later were minted ZERO times ((lv) inside the
    # incubator). What must hold is that EVERY gene reaches the judge and no
    # admitted offspring duplicates a static.
    names = {c["name"] for c in admitted}
    levers_seen = {list(c["levers"])[0] for c in admitted}
    assert levers_seen == {l for l, _ in inc.MUM_GENES.values()}, (
        "a declared gene never reached the judge's pool — position in "
        f"MUM_GENES is deciding reachability again: {sorted(levers_seen)}")
    static_sigs = {tuple(sorted(c["levers"].items())) for c in ej.CANDIDATES}
    for c in admitted:
        assert tuple(sorted(c["levers"].items())) not in static_sigs, (
            f"{c['name']} duplicates a hand-declared static — the dedup that "
            "keeps an offspring from burning a slot on a known cell is gone")
    assert not any(n in names for n in ("xp-mum-rsi_max-32", "xp-mum-max_hold_min-720",
                                        "xp-mum-max_hold_min-2880")), names


def test_an_unknown_lane_proposes_nothing_and_is_not_sterile():
    js = {"lanes": {"serial_lane": "georgia"}}
    assert inc.funding_proposals(js, {}) == []
    cap = inc.proposal_capacity(js, {})
    assert cap["lane"] == "georgia" and cap["generatable"] == 0 and cap["exhausted"] is False


def test_lifetime_memory_and_verdicts_dedup_on_the_mum_lane():
    first = inc.funding_proposals(MUM, {})
    tried = {"proposed": [{"name": first[0]["name"]}]}
    again = inc.funding_proposals(MUM, tried)
    assert first[0]["name"] not in {p["name"] for p in again}
    verd = dict(MUM, verdicts=[{"name": first[1]["name"]}])
    assert first[1]["name"] not in {p["name"] for p in inc.funding_proposals(verd, {})}
    cap = inc.proposal_capacity(MUM, {"proposed": [{"name": p["name"]} for p in
                                       inc._funding_candidates(MUM, {}, lane="mum")[1]]})
    assert cap["exhausted"] is True and cap["untried"] == 0
