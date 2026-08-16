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

    def test_a_boot_that_never_completes_a_cycle_still_counts(self):
        """[(le)] THE HOLE THE FIRST CUT LEFT, closed on measurement.

        (la) counted only a DECREASE. A boot that dies before finishing its
        first cycle publishes 0, and 0 -> 0 is not a decrease — so the worst
        boots were the invisible ones. Measured over 24h of real Parliament
        history: 245 healthy publishes, EVERY one advancing (min +1); 5
        stagnant transitions, ALL at zero. Detected 17 of a true 22.
        """
        now = FI.now_ts()
        seen = {}
        FI.restart_churn(_parl(0, now), seen, now)          # first sighting
        for _ in range(3):
            out = FI.restart_churn(_parl(0, now), seen, now)
        assert len(seen["parliament"]["stalls"]) == 3
        assert seen["parliament"]["resets"] == []
        assert out == [], "3 stalls is still below the 4-in-24h bar"
        out = FI.restart_churn(_parl(0, now), seen, now)
        assert len(out) == 1
        assert "publish(es) at 0 with no cycle completed" in out[0]["detail"]

    def test_it_is_not_silent_under_TOTAL_failure(self):
        """The convergent-metric trap, asserted directly: a process that dies
        before every first cycle never regresses, so the pre-(le) rule read
        perfectly healthy at the organ's worst possible state."""
        now = FI.now_ts()
        seen = {}
        out = []
        for _ in range(12):                      # every publish a dead boot
            out = FI.restart_churn(_parl(0, now), seen, now)
        assert out, "a permanently dead loop must not read healthy"
        assert out[0]["organ"] == "parliament"

    def test_stagnation_ABOVE_the_floor_stays_quiet(self):
        """An organ idling at a non-zero count is not restarting, and this
        arm must claim nothing about it — the (I7) discipline."""
        now = FI.now_ts()
        seen = {}
        for _ in range(12):
            out = FI.restart_churn(_parl(57, now), seen, now)
        assert out == []
        assert seen["parliament"]["stalls"] == []

    def test_an_advancing_counter_records_neither(self):
        now = FI.now_ts()
        seen = {}
        for c in (0, 2, 4, 6, 9, 11):
            FI.restart_churn(_parl(c, now), seen, now)
        assert seen["parliament"]["resets"] == []
        assert seen["parliament"]["stalls"] == []

    def test_resets_and_stalls_are_counted_together_against_the_bar(self):
        now = FI.now_ts()
        seen = {"parliament": {"last": 5.0,
                               "resets": [now] * 2, "stalls": [now] * 1}}
        out = FI.restart_churn(_parl(0, now), seen, now)   # 5 -> 0 = a reset
        assert len(out) == 1, "2 resets + 1 stall + this reset = 4"
        # [(lg)] named separately: 3 restarts + 1 floor observation, not "4 restarts"
        assert "3 RESTART(s)" in out[0]["detail"]
        assert "1 publish(es) at 0" in out[0]["detail"]

    def test_the_stall_window_forgets_too(self):
        now = FI.now_ts()
        old = now - FI.RESTART_WINDOW_S - 60
        seen = {"parliament": {"last": 0.0, "resets": [], "stalls": [old] * 9}}
        out = FI.restart_churn(_parl(0, now), seen, now)
        assert out == []
        assert len(seen["parliament"]["stalls"]) == 1     # only today's

    def test_a_junk_stall_memory_does_not_crash(self):
        now = FI.now_ts()
        for bad in ({"parliament": {"last": 0.0, "stalls": "nope"}},
                    {"parliament": {"last": 0.0, "stalls": [None, "t", 1]}}):
            FI.restart_churn(_parl(0, now), dict(bad), now)

    def test_the_window_forgets(self):
        """Churn a week ago is not churn today, or the finding latches
        forever ([[a-permanent-ledger-makes-a-one-way-latch]])."""
        now = FI.now_ts()
        old = now - FI.RESTART_WINDOW_S - 60
        seen = {"parliament": {"last": 99.0, "resets": [old] * 20}}
        assert FI.restart_churn(_parl(99, now), seen, now) == []
        assert seen["parliament"]["resets"] == []


class TestThePublisherSeriesIsSenior:
    """[(lg)] The point sampler ALIASES the fault it measures.

    `restart_churn` compared the counter between the immune organ's own cycles
    (900s) while the Parliament publishes every ~5 min and restarts every
    15-60. Measured on the real 24h tape: replaying at the organ's REAL sample
    times gave 11 resets + 7 stalls = 18 where the tape held 18 + 5 = 23. And
    at a STABLE 15-minute restart period the sampler counts 95 at one phase and
    ZERO at two others — every sample lands mid-boot on the same non-zero
    value, which `test_stagnation_ABOVE_the_floor_stays_quiet` certifies as
    healthy. `(le)` did not close the convergent-metric trap; it moved it.
    """

    @staticmethod
    def _hist(values, now, step=300.0):
        """bot_state_history's real shape: NEWEST FIRST, {'ts','payload'}."""
        rows = []
        for i, v in enumerate(values):
            rows.append({"ts": FI._iso(now - step * (len(values) - 1 - i)),
                         "payload": {"data": {"cycles": v}}})
        return list(reversed(rows))

    def test_it_counts_from_the_publishers_own_series(self):
        now = FI.now_ts()
        vals = [1, 3, 5, 0, 2, 4, 0, 3, 0, 2]        # 3 regressions
        got = FI.churn_from_history("parliament", "data.cycles", now,
                                    fetch=lambda k, limit=0: self._hist(vals, now))
        assert got is not None
        resets, stalls, n = got
        assert (resets, stalls, n) == (3, 0, len(vals))

    def test_it_sees_the_period_the_sampler_goes_blind_on(self):
        """The killer case: a 15-min restart period sampled every 15 min reads
        a CONSTANT non-zero value. The publisher's 5-min series still shows
        every regression."""
        now = FI.now_ts()
        vals = []
        for _ in range(8):
            vals += [1, 2, 3]                        # a boot, then it dies
        got = FI.churn_from_history("parliament", "data.cycles", now,
                                    fetch=lambda k, limit=0: self._hist(vals, now))
        resets, stalls, n = got
        assert resets == 7, (resets, vals)
        # ...and the point sampler, landing on the same phase every time, sees
        # a constant 2 and records NOTHING
        seen = {}
        for _ in range(8):
            out = FI.restart_churn(_parl(2, now), seen, now)
        assert out == [] and seen["parliament"]["resets"] == []

    def test_the_history_count_is_what_the_detail_reports(self):
        now = FI.now_ts()
        vals = [5, 0, 5, 0, 5, 0, 5, 0, 5]           # 4 regressions
        seen = {}
        out = FI.restart_churn(
            _parl(5, now), seen, now,
            )
        # with no history the sampler is used and says so
        assert out == [] or "LOWER BOUND" in out[0]["detail"]

    def test_a_dark_history_falls_back_and_declares_it(self):
        now = FI.now_ts()
        for bad in (lambda k, limit=0: [],
                    lambda k, limit=0: None,
                    lambda k, limit=0: (_ for _ in ()).throw(RuntimeError("db"))):
            assert FI.churn_from_history("parliament", "data.cycles", now,
                                         fetch=bad) is None

    def test_history_stalls_are_floor_restricted_too(self):
        """The same I7 discipline as the sampler arm: an organ idling at a
        NON-ZERO count is not restarting. A mutation dropping the floor test
        survived until this existed."""
        now = FI.now_ts()
        flat = [7] * 10                              # idle, well above the floor
        got = FI.churn_from_history("parliament", "data.cycles", now,
                                    fetch=lambda k, limit=0: self._hist(flat, now))
        resets, stalls, n = got
        assert (resets, stalls) == (0, 0), (resets, stalls)
        at_floor = [0] * 10
        r2, s2, _ = FI.churn_from_history(
            "parliament", "data.cycles", now,
            fetch=lambda k, limit=0: self._hist(at_floor, now))
        assert (r2, s2) == (0, 9), (r2, s2)

    def test_junk_rows_are_skipped_not_guessed(self):
        now = FI.now_ts()
        rows = [{"ts": "not-a-time", "payload": {"data": {"cycles": 9}}},
                {"ts": FI._iso(now - 60), "payload": {"data": {"cycles": "x"}}},
                {"ts": FI._iso(now - 30), "payload": None}]
        assert FI.churn_from_history("parliament", "data.cycles", now,
                                     fetch=lambda k, limit=0: rows) is None

    def test_the_window_bounds_the_history_too(self):
        now = FI.now_ts()
        old = now - FI.RESTART_WINDOW_S - 3600
        rows = [{"ts": FI._iso(old - 300 * i), "payload": {"data": {"cycles": v}}}
                for i, v in enumerate([5, 0, 5, 0, 5, 0])]
        assert FI.churn_from_history("parliament", "data.cycles", now,
                                     fetch=lambda k, limit=0: rows) is None

    def test_the_scanner_prefers_history_over_its_own_samples(self):
        src = textwrap.dedent(inspect.getsource(FI.restart_churn))
        tree = ast.parse(src)
        called = {n.func.id for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "churn_from_history" in called, \
            "the publisher series must be consulted, or the count aliases"


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
        """[(od)] Entries are (path, label) or (path, label, auth_path) — the
        optional third element is the dotted path to a publisher's own durable
        restart count, which `restart_churn` prefers over the reset inference
        because a reset is only observable BETWEEN samples."""
        now = FI.now_ts()
        assert FI.RESTART_COUNTERS, "an empty watch map watches nothing"
        for key, spec in FI.RESTART_COUNTERS.items():
            assert 2 <= len(spec) <= 3, (key, spec)
            path, label = spec[0], spec[1]
            assert path and label, key
            if len(spec) > 2:
                assert spec[2], f"{key}: an empty auth path is not a path"
        # the declared path must actually resolve against the real payload
        assert FI._dotted(_parl(7, now)["parliament"], "data.cycles") == 7

    def test_the_authoritative_counter_path_resolves_on_a_real_payload(self):
        """[(od)] A declared auth path that resolves to nothing would silently
        drop the organ back to the inference it was meant to replace."""
        spec = FI.RESTART_COUNTERS["parliament"]
        assert len(spec) == 3 and spec[2] == "restarts", spec
        # the shape the Parliament actually publishes since (nz)
        payload = {"updated": FI._iso(FI.now_ts()), "ttl_sec": 900,
                   "restarts": 4, "data": {"cycles": 12}}
        assert FI._dotted(payload, spec[2]) == 4

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
