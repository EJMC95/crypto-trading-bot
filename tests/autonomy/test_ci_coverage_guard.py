#!/usr/bin/env python3
"""
[2026-08-16 (pc)] WAS THE DEPLOYED CODE EVER GRADED?

The two workflows disagree about a burst of pushes, silently:

    Tests            cancel-in-progress: TRUE   -> the verdict is dropped
    Railway Redeploy cancel-in-progress: FALSE  -> the deploy still runs

Measured 16-Aug over four hours: **27 of 60 Tests runs cancelled (45%)** against
**41 successful deploys and zero failures**. Code reached containers from
commits CI never graded, and that is what turned a standing red into a manual
bisect.

This pins the guard's CALIBRATION as much as its logic, because the calibration
is the part that decides whether anyone keeps reading it:

  * a cancelled or failed run is NOT a verdict;
  * an in-flight run is not yet owed one;
  * an unreadable history is UNKNOWN and exits 2 — never a vacuous green
    ((mq): "the currency guard had no answer for 7 of 27 rows, and said OK");
  * **ungraded but nothing shipped is OK**, because the container is still
    running the last green commit. Reddening on a doc-only push is the `(gl)`
    cry-wolf shape, and this repo has paid for it.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_ci_coverage as g            # noqa: E402

GREEN = ("c0", "success", "completed")


def test_a_green_tip_is_covered():
    assert g.assess([("tip", "success", "completed")], "tip",
                    [("tip", ["fleet_bus.py"])])["verdict"] == "OK"


def test_an_in_flight_tip_is_not_yet_owed_a_verdict():
    """MUTATION: treat queued/in_progress as settled -> RED."""
    for st in ("in_progress", "queued"):
        assert g.assess([("tip", "", st)], "tip",
                        [("tip", ["fleet_bus.py"])])["verdict"] == "OK", st


def test_a_cancelled_run_is_not_a_verdict():
    """The premise of the whole guard. MUTATION: count cancelled as green."""
    r = g.assess([GREEN, ("tip", "cancelled", "completed")], "tip",
                 [("tip", ["fleet_bus.py"]), GREEN[:1] + (["x.py"],)][:2])
    assert r["verdict"] == "UNGRADED", r


def test_a_failed_run_is_not_a_verdict_either():
    r = g.assess([("tip", "failure", "completed")], "tip",
                 [("tip", ["fleet_bus.py"])])
    assert r["verdict"] == "UNGRADED", r


def test_an_unreadable_history_is_UNKNOWN_never_OK():
    """MUTATION: return [] instead of None on a dark API -> RED.

    `None` and `[]` must not collapse: "could not ask" and "no runs" are
    different states, and only one of them is safe to pass ((kw))."""
    assert g.assess(None, "tip", [])["verdict"] == "UNKNOWN"


def test_fetch_runs_returns_None_on_a_dark_api_never_an_empty_list():
    """The gap a mutation found: every other test drove `assess` directly, so
    `fetch_runs` itself was unpinned and could return `[]` on failure — which
    `assess` reads as "no green runs anywhere", i.e. a confident verdict built
    on no data. `None` and `[]` must not collapse ((kw)).

    MUTATION: return [] instead of None on a non-zero exit -> RED.
    """
    import subprocess as sp

    class Boom:
        returncode = 1
        stdout = ""

    orig = sp.run
    try:
        sp.run = lambda *a, **k: Boom()
        assert g.fetch_runs() is None, "a failed `gh` call must be UNKNOWN"
        sp.run = lambda *a, **k: type("R", (), {"returncode": 0,
                                                "stdout": "not json"})()
        assert g.fetch_runs() is None, "unparseable output must be UNKNOWN"
        sp.run = lambda *a, **k: type("R", (), {"returncode": 0,
                                                "stdout": '{"a": 1}'})()
        assert g.fetch_runs() is None, "a non-list payload must be UNKNOWN"
    finally:
        sp.run = orig
    # ...and the whole path end-to-end: dark fetch -> UNKNOWN verdict
    assert g.assess(g.fetch_runs.__wrapped__() if hasattr(
        g.fetch_runs, "__wrapped__") else None, "tip", [])["verdict"] == "UNKNOWN"


def test_ungraded_but_nothing_shipped_passes_and_is_still_reported():
    """THE CALIBRATION. Docs/tests/changelog reach no container, so the last
    green commit is what runs — pass, but keep the count visible.

    MUTATION: fail whenever anything is ungraded -> RED (cry-wolf).
    """
    r = g.assess([GREEN, ("c2", "cancelled", "completed")], "c2",
                 [("c2", ["CHANGELOG.md"]), ("c1", ["tests/t.py"]),
                  ("c0", ["x.py"])])
    assert r["verdict"] == "OK", r
    assert r["shipped"] == [], r
    assert r["ungraded"] == ["c2", "c1"], "the context must stay visible"


def test_ungraded_AND_shipped_is_the_failing_state():
    r = g.assess([GREEN, ("c2", "cancelled", "completed")], "c2",
                 [("c2", ["venues/marks.py"]), ("c1", ["CHANGELOG.md"]),
                  ("c0", ["x.py"])])
    assert r["verdict"] == "UNGRADED", r
    assert r["shipped"] == ["c2"], r
    assert r["last_green"] == "c0", r


# ------------------------------------------------------------------ ships()
def test_ships_classifies_container_reaching_files():
    assert g.ships(["venues/marks.py"])
    assert g.ships(["fleet_bus.py"])
    assert g.ships(["run_all.sh"])
    assert g.ships(["Dockerfile.funding"])
    assert g.ships(["parliament/brain.py"])


def test_ships_excludes_what_reaches_no_container():
    for p in ("CHANGELOG.md", "CLAUDE.md", "README.md",
              "tests/autonomy/test_x.py", "reports/daily.md"):
        assert not g.ships([p]), p
    assert not g.ships([]) and not g.ships(None), "no files -> no claim"


def test_a_mixed_commit_ships():
    """A commit that touches docs AND code still reached a container —
    the exclusion is per-FILE, never per-commit."""
    assert g.ships(["CHANGELOG.md", "venues/marks.py"])


# --------------------------------------------------------------- it is WIRED
def test_the_guard_is_wired_into_a_workflow():
    """`(gk)`: a rule that runs only when a human remembers it is half a fix.
    MUTATION: remove the step from the workflow -> RED.
    """
    wf = (ROOT / ".github/workflows/fleet-weekly-assessment.yml").read_text()
    assert "scripts/audit_ci_coverage.py" in wf, (
        "the guard has no consumer — it runs only when a human types it")
    assert "GH_TOKEN" in wf, (
        "the step needs GH_TOKEN for `gh run list`; without it the guard "
        "reads UNKNOWN on every run and exits 2 forever")
    # fetch-depth 0 is load-bearing: a shallow checkout finds no green commit
    assert "fetch-depth: 0" in wf


def test_the_selftest_is_registered():
    """Every `--selftest` in this repo must be registered, or it is a guard
    nobody runs (`audit_organ_silence`'s rule, applied to itself)."""
    reg = (ROOT / "tests/test_selftests.py").read_text()
    assert "scripts.audit_ci_coverage" in reg, (
        "scripts/audit_ci_coverage.py defines --selftest but is not "
        "registered in SELFTEST_MODULES")
    # PLACEMENT, per that file's own rule: this audit's verdict reads GitHub
    # run history, which changes with no code change, so its SCAN must not
    # gate local pytest. In ENFORCED_AUDITS it would turn every developer's
    # `pytest` red whenever CI happened to be mid-flight.
    assert "scripts/audit_ci_coverage.py" not in reg, (
        "audit_ci_coverage is in ENFORCED_AUDITS; its verdict depends on CI "
        "run state, so its scan belongs in the weekly job, not in pytest")


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("test_ci_coverage_guard: all passed")
