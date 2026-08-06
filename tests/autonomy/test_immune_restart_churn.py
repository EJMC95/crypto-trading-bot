"""[2026-08-06] The restart-churn detector: a publisher that keeps RESTARTING
looks perfectly healthy to every age check the fleet owns.

THE INCIDENT. 🏛️ the Parliament's supervisor crash-looped **15 times in 24h**
(measured off `/bus.json?hours=24`: `data.cycles` 110->0, 250->0, 128->0, ...),
wiping the six PM books' equity/closed telemetry to 1000.0/0 on every boot —
and its key never once read stale, because each new boot republishes within
seconds. `fleet_immune` had invariants for fresh-but-wrong CONTENT and the
watchdog pages on staleness; neither can see an organ that is永 alive and
永 starting over. This is I13's twin: I13 covers a loop that STOPS (age
grows), this covers a loop that RESTARTS (age is held fixed by the fault).

These tests pin the sensor AND its wiring, because the failure mode this file
exists to prevent is the (hh) one — a scanner whose key is not fetched is dead
code that passes every test written about the scanner alone.
"""
import ast
import inspect
import pathlib
import textwrap

import pytest

import fleet_immune as FI


def _parl(cycles, now, age_s=0, ttl=900):
    """The parliament payload's REAL nesting (data.cycles), not a flat fixture."""
    return {"parliament": {"updated": FI._iso(now - age_s), "ttl_sec": ttl,
                           "data": {"cycles": cycles, "books": 204},
                           "health": {"stalled": []}}}


class TestTheSensor:
    def test_a_first_sighting_claims_nothing(self):
        now = FI.now_ts()
        seen = {}
        assert FI.restart_churn(_parl(110, now), seen, now) == []
        assert seen["parliament"]["last"] == 110.0

    def test_an_advancing_counter_is_healthy(self):
        now = FI.now_ts()
        seen = {}
        for c in range(1, 40):
            assert FI.restart_churn(_parl(c, now), seen, now) == []
        assert seen["parliament"]["resets"] == []

    def test_one_reset_is_a_deploy_and_stays_quiet(self):
        """A deploy restarts the container; paging on it trains the operator
        to ignore the pager (the (gl) warn-on-green lesson)."""
        now = FI.now_ts()
        seen = {}
        FI.restart_churn(_parl(110, now), seen, now)
        assert FI.restart_churn(_parl(0, now), seen, now) == []
        assert len(seen["parliament"]["resets"]) == 1

    def test_the_measured_incident_fires(self):
        """The 6-Aug sequence, replayed: 15 resets must be sickness."""
        now = FI.now_ts()
        seen = {}
        # the 15 peaks read off /bus.json?hours=24 on 6-Aug, each followed by
        # the 0 its restart published (110->0, 13->0, ... 8->0 at 08:33Z)
        peaks = [110, 13, 23, 3, 43, 20, 250, 5, 10, 128, 35, 4, 28, 10, 8]
        observed = [v for peak in peaks for v in (peak, 0)]
        out = []
        for c in observed:
            out = FI.restart_churn(_parl(c, now), seen, now)
        assert len(out) == 1
        assert out[0]["organ"] == "parliament"
        assert len(seen["parliament"]["resets"]) == 15
        # I8: the finding must name the thing the operator can go and look at
        assert "Parliament" in out[0]["detail"]
        assert "data.cycles" in out[0]["detail"]

    def test_it_fires_at_the_threshold_and_not_below(self):
        now = FI.now_ts()
        for n_resets, expect in ((FI.RESTART_CHURN_N - 1, 0),
                                 (FI.RESTART_CHURN_N, 1)):
            seen = {"parliament": {"last": 50.0, "resets": [now] * n_resets}}
            # a counter that HOLDS adds no reset — isolates the threshold
            out = FI.restart_churn(_parl(50, now), seen, now)
            assert len(out) == expect, (n_resets, out)

    def test_the_window_forgets(self):
        """Churn a week ago is not churn today, or the finding latches
        forever ([[a-permanent-ledger-makes-a-one-way-latch]])."""
        now = FI.now_ts()
        old = now - FI.RESTART_WINDOW_S - 60
        seen = {"parliament": {"last": 99.0, "resets": [old] * 20}}
        assert FI.restart_churn(_parl(99, now), seen, now) == []
        assert seen["parliament"]["resets"] == []


class TestFailSafeTowardSilence:
    @pytest.mark.parametrize("states", [
        {},
        {"parliament": {}},
        {"parliament": {"updated": None, "data": {"cycles": 0}}},
    ])
    def test_absent_or_unreadable_claims_nothing(self, states):
        now = FI.now_ts()
        loaded = {"parliament": {"last": 500.0, "resets": [now] * 20}}
        assert FI.restart_churn(states, loaded, now) == []

    def test_a_stale_organ_is_the_watchdogs_jurisdiction(self):
        now = FI.now_ts()
        seen = {"parliament": {"last": 500.0, "resets": [now] * 20}}
        assert FI.restart_churn(_parl(0, now, age_s=99999), seen, now) == []

    @pytest.mark.parametrize("junk", ["many", None, True, {"n": 1}, []])
    def test_a_non_numeric_counter_claims_nothing(self, junk):
        now = FI.now_ts()
        states = {"parliament": {"updated": FI._iso(now), "ttl_sec": 900,
                                 "data": {"cycles": junk}}}
        seen = {"parliament": {"last": 9.0, "resets": [now] * 20}}
        assert FI.restart_churn(states, seen, now) == []

    def test_a_junk_memory_does_not_crash_the_organ(self):
        now = FI.now_ts()
        for bad in ({"parliament": {"last": "x", "resets": "nope"}},
                    {"parliament": None},
                    {"parliament": {"resets": [None, "t", 1]}}):
            FI.restart_churn(_parl(5, now), dict(bad), now)


class TestItIsActuallyWired:
    """The (hh) lesson, a third time: a scanner whose key is never fetched is
    dead code. Checked by AST/source against run_once, not by a page-wide
    substring scan (the (gn) rule)."""

    def test_the_scanner_is_called_in_run_once(self):
        src = textwrap.dedent(inspect.getsource(FI.run_once))
        tree = ast.parse(src)
        called = {n.func.id for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "restart_churn" in called

    def test_every_watched_key_reaches_the_fetch_list(self):
        """STRUCTURAL, not a substring scan.

        The first cut of this test asserted `"RESTART_COUNTERS" in src` and a
        mutation that deleted `+ tuple(RESTART_COUNTERS)` from the `_keys`
        assignment stayed GREEN — the explanatory COMMENT above the line
        still carried the word. That is the (gn) rule biting the test written
        to enforce it, so the claim is now made about the assignment node
        itself: whatever builds `_keys` must actually read RESTART_COUNTERS.
        """
        src = textwrap.dedent(inspect.getsource(FI.run_once))
        keys_assigns = [n for n in ast.walk(ast.parse(src))
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "_keys"
                                for t in n.targets)]
        assert keys_assigns, "run_once no longer builds a _keys fetch list"
        reads = {d.id for a in keys_assigns for d in ast.walk(a.value)
                 if isinstance(d, ast.Name)}
        assert "RESTART_COUNTERS" in reads, (
            "the _keys fetch must be BUILT from RESTART_COUNTERS — a watched "
            "key that is never fetched makes restart_churn dead code (hh)")

    def test_the_watch_map_is_usable(self):
        now = FI.now_ts()
        assert FI.RESTART_COUNTERS, "an empty watch map watches nothing"
        for key, (path, label) in FI.RESTART_COUNTERS.items():
            assert path and label, key
        # the declared path must actually resolve against the real payload
        assert FI._dotted(_parl(7, now)["parliament"], "data.cycles") == 7

    def test_the_memory_is_persisted(self):
        """Without persistence every cycle is a first sighting and the sensor
        can never fire — the defect would be invisible to every test above."""
        src = inspect.getsource(FI.run_once)
        assert 'prior.get("churn_seen")' in src
        assert '"churn_seen": churn_seen' in src

    def test_the_watch_list_is_published(self):
        src = inspect.getsource(FI.run_once)
        assert '"churn_watched"' in src, \
            "an organ that is NOT watched must be visible, not silently omitted"


def test_the_module_ships_in_the_image_that_runs_it():
    """restart_churn lives in fleet_immune, which run_all.sh already loops —
    no new COPY, so no born-dark risk. Guard the assumption anyway."""
    root = pathlib.Path(__file__).resolve().parents[2]
    assert (root / "fleet_immune.py").exists()
    assert "fleet_immune" in (root / "run_all.sh").read_text()
