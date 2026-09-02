"""The organ board grades OUTPUT, and its four failure shapes stay red.

`scripts/organ_board.py` replaces the 2-Sep (wp) by-hand organ review with a
weekly diff off the public feeds. These tests pin what makes it a guard rather
than a decoration — each has a specific silent-degrade mode:

  * an organ aged past its ttl reads DARK, and its CONTENT is never graded (I1:
    a frozen payload is byte-identical to a healthy one; only the stamp differs);
  * `fleet_immune.sick` non-empty reads WATCH and names the organ (I8);
  * a MISSING field reads `watch: field absent` — a check that inspects nothing
    must not report clean (house rule), and it must not crash either;
  * an EMPTY bus is a dark FEED and exits 2 — twenty `dark` rows rendered as a
    result would be the vacuous green the `--pnl-json` contract exists to stop.

Plus the baseline pin: the fixture IS the 2-Sep feed, so `REVIEW_2SEP` must
equal what `grade` reads off it — otherwise `fixed?` is measured against a
number nobody derived.
"""
import copy
import importlib.util
import json
import os
import sys

import pytest

pytestmark = pytest.mark.autonomy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_spec = importlib.util.spec_from_file_location(
    "organ_board", os.path.join(ROOT, "scripts", "organ_board.py"))
OB = importlib.util.module_from_spec(_spec)
sys.modules["organ_board"] = OB
_spec.loader.exec_module(OB)


def _rows(bus, pnl=None, now=None):
    return {r["organ"]: r for r in OB.grade(
        bus, OB.FIXTURE_PNL if pnl is None else pnl, now or OB.FIXTURE_NOW)}


def test_fixture_grades_to_the_pinned_baseline_and_every_organ_is_covered():
    rows = OB.grade(OB.FIXTURE_BUS, OB.FIXTURE_PNL, OB.FIXTURE_NOW)
    assert [r["organ"] for r in rows] == [o for o, _ in OB.CHECKS]
    assert {r["organ"]: r["state"] for r in rows} == OB.REVIEW_2SEP
    assert all(r["state"] in OB.STATES and r["why"] for r in rows)
    for organ in ("fleet_risk", "brain_stake_mults", "strategy_incubator", "xp_judge",
                  "xp_queue", "scout_tuner", "proprioception", "evidence_board",
                  "fleet_immune", "impl_shortfall", "event_sentinel", "parliament",
                  "fleet_respiration", "golive_readiness", "fleet_allocation",
                  "lighter_market"):
        assert organ in OB.REVIEW_2SEP, organ


def test_mutation_a_aged_past_ttl_reads_dark_and_content_is_not_consulted():
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["lighter_market"]["updated"] = "2026-09-01T00:00:00+00:00"
    m["lighter_market"]["n_books"] = "this would crash a content check"
    r = _rows(m)["lighter_market"]
    assert r["state"] == "dark" and "ttl" in r["why"], r
    # absent key and unreadable stamp are dark too — liveness unknowable is not ok
    m = copy.deepcopy(OB.FIXTURE_BUS)
    del m["fleet_risk"]
    m["parliament"]["updated"] = "yesterday-ish"
    rows = _rows(m)
    assert rows["fleet_risk"]["state"] == "dark"
    assert rows["parliament"]["state"] == "dark" and "unparseable" in rows["parliament"]["why"]


def test_mutation_b_immune_sick_reads_watch_and_names_the_organ():
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["fleet_immune"]["sick"] = [{"organ": "some-live-book", "detail": "stop is dead"}]
    r = _rows(m)["fleet_immune"]
    assert r["state"] == "watch" and "some-live-book" in r["why"], r
    m["fleet_immune"]["sick"] = []
    # baseline read watch; clean now is a CLAIM for a human, never a silent ok
    assert _rows(m)["fleet_immune"]["state"] == "fixed?"


def test_mutation_c_a_missing_field_degrades_to_watch_absent_never_crash_never_ok():
    m = copy.deepcopy(OB.FIXTURE_BUS)
    del m["fleet_respiration"]["spo2"]
    del m["golive_readiness"]["decision_docket"]
    rows = _rows(m)
    for organ in ("fleet_respiration", "golive_readiness"):
        assert rows[organ]["state"] == "watch" and "absent" in rows[organ]["why"], rows[organ]
    # every organ stripped to its liveness stamps: none may read ok, none may raise
    bare = {o: {"updated": OB.FIXTURE_NOW.isoformat(), "ttl_sec": 60} for o, _ in OB.CHECKS}
    for organ, r in _rows(bare).items():
        assert r["state"] == "watch" and "absent" in r["why"], (organ, r)
    # a wrong TYPE is a check error, still watch, still no crash
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["proprioception"]["counts"]["hurting"] = "many"
    assert _rows(m)["proprioception"]["state"] == "watch"


def test_mutation_d_an_empty_bus_is_a_dark_feed_and_exits_2(tmp_path):
    assert OB.feed_dark({}, OB.FIXTURE_PNL)
    assert OB.feed_dark({"history_hours": 24.0}, OB.FIXTURE_PNL)
    assert OB.feed_dark(OB.FIXTURE_BUS, {"bots": []})
    assert OB.feed_dark(OB.FIXTURE_BUS, OB.FIXTURE_PNL) is None
    bus, pnl = tmp_path / "bus.json", tmp_path / "pnl.json"
    pnl.write_text(json.dumps(OB.FIXTURE_PNL))
    bus.write_text("{}")
    assert OB.main(["--bus-json", str(bus), "--pnl-json", str(pnl)]) == 2
    bus.write_text("<html>502</html>")
    assert OB.main(["--bus-json", str(bus), "--pnl-json", str(pnl)]) == 2
    assert OB.main(["--bus-json", str(bus), "--pnl-json", str(tmp_path / "missing.json")]) == 2


def test_a_healthy_feed_exits_0_and_writes_the_step_summary(tmp_path, monkeypatch, capsys):
    bus, pnl = tmp_path / "bus.json", tmp_path / "pnl.json"
    bus.write_text(json.dumps(OB.FIXTURE_BUS))
    pnl.write_text(json.dumps(OB.FIXTURE_PNL))
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(OB, "datetime", _FrozenDatetime)
    assert OB.main(["--bus-json", str(bus), "--pnl-json", str(pnl)]) == 0
    out = capsys.readouterr().out
    assert "| Organ | State | What the payload says |" in out
    assert summary.read_text().strip() == out.strip()
    assert "| `fleet_immune` | 🟡 watch |" in out


class _FrozenDatetime(OB.datetime):
    @classmethod
    def now(cls, tz=None):
        return OB.FIXTURE_NOW


def test_the_semantic_arms_each_move_on_their_own_field():
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["xp_judge"]["lanes"]["live"] = ["mum"]          # a live lane with an empty queue is starved
    assert _rows(m)["xp_queue"]["state"] == "watch"
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["brain_stake_mults"]["mults"].popitem()          # 2 opinions < 3
    assert _rows(m)["brain_stake_mults"]["state"] == "watch"
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["fleet_risk"]["long_positions"] = 3
    m["fleet_risk"]["cohorts"] = {"live": {"long_positions": 1, "long_budget": 6},
                                  "shadow": {"long_positions": 2, "long_budget": 20}}
    r = _rows(m)["fleet_risk"]
    assert r["state"] == "fixed?" and "live 1/6" in r["why"] and "shadow 2/20" in r["why"]
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["event_sentinel"]["sources_ok"]["gdelt"] = True
    for g in m["event_sentinel"]["playbook_grades"].values():
        g["hit_rate"] = 0.3                            # gdelt back, every playbook below a coin flip
    assert _rows(m)["event_sentinel"]["state"] == "watch"
    m = copy.deepcopy(OB.FIXTURE_BUS)
    m["golive_readiness"]["decision_docket"] = []
    assert _rows(m)["golive_readiness"]["state"] == "fixed?"


def test_selftest_is_green():
    assert OB.selftest() == 0
