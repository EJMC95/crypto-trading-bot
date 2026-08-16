#!/usr/bin/env python3
"""
[2026-08-16 (os)] 🛡️ THE IMMUNE ORGAN NEVER RAN, AND ITS OWN FRESHNESS
CONTRACT SAID IT WAS FINE.

`run_all.sh` started it as `( sleep 540; while true; do run; sleep 900; done )`.
The 540s fuse is a thundering-herd stagger — one of nineteen, 60s..900s — and
it is reset by every container restart. MEASURED 16-Aug: freqtrade-bots
redeployed 10x between 03:40Z and 04:09Z with gaps of 0:36..7:31, every one
shorter than the fuse, and the organ went from 03:38:49Z to 41+ minutes with
**zero executions**. Not slow, not crashed: never started.

TWO REASONS NOTHING NOTICED, both worth keeping:

  * ITS TTL IS SLACKER THAN ITS LOOP. `ttl_sec` 2400 against a 900s interval,
    so a 40-minute silence is still INSIDE the freshness contract and the
    watchdog reads a healthy key. That is the (mw) shape — a TTL absorbing a
    missed cadence — on the organ whose whole job is spotting organs that are
    fresh and wrong.
  * `audit_organ_silence` ((hw)) CANNOT COVER THIS BY CONSTRUCTION. It routes
    organs through `organ_main` so a CRASH lands on the organ's own key. A
    process killed during `sleep` never reaches main(), so there is nothing to
    record and no one to record it. Crash-reporting and never-starting are
    different failures, and only the first was guarded.

The fix is one guaranteed execution per boot BEFORE the stagger. Steady-state
cadence is unchanged; a restart now costs one duplicated run instead of the
whole organ.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUN_ALL = ROOT / "run_all.sh"

# [(ou)] The whole starved cohort, not just 🛡️. Every organ whose boot stagger
# exceeded the gap between container restarts executed ZERO times across the
# 03:40-04:09Z deploy storm. `fleet_radar.py`'s block also runs
# `fleet_allocation.py`, so fixing that one covers two organs.
STARVED = [
    "fleet_immune.py",              # (os) — the pageable safety organ, first
    "lighter_scout_tuner.py",
    "fleet_proprioception.py",
    "experiment_judge.py",
    "fleet_regen.py",
    "strategy_incubator.py",
    "implementation_shortfall.py",
    "fleet_radar.py",               # block also runs fleet_allocation.py
]


# `sleep 540` and `sleep "${IMMUNE_BOOT_STAGGER_SEC:-540}"` are both sleeps;
# only matching the bare form would silently skip the organ whose stagger is
# env-overridable — i.e. exactly the one this file was written for.
_SLEEP = re.compile(r"""\bsleep\s+(?:"?\$\{[A-Z_]+:-(\d+)\}"?|(\d+))""")


def _sleeps(body: str):
    """[(position, seconds)] for every sleep in a block, either spelling."""
    return [(m.start(), int(m.group(1) or m.group(2)))
            for m in _SLEEP.finditer(body)]


def _block_for(entry: str) -> str:
    """The `( ... ) &` subshell that launches `entry`."""
    src = RUN_ALL.read_text()
    i = src.index(f"python3 /freqtrade/{entry}")
    start = src.rindex("\n( ", 0, i) + 1
    end = src.index(") &", i) + 3
    return src[start:end]


def _immune_block() -> str:
    """The `( ... ) &` subshell that launches fleet_immune.py."""
    src = RUN_ALL.read_text()
    i = src.index("python3 /freqtrade/fleet_immune.py")
    start = src.rindex("\n( ", 0, i) + 1
    end = src.index(") &", i) + 3
    return src[start:end]


def test_every_starved_organ_runs_once_before_its_long_stagger():
    """THE PROPERTY, for the whole cohort. A restart must always yield one
    execution per organ, whatever the deploy cadence.

    The boot offset that remains in front of the first run must be SHORT — a
    long one here would rebuild the exact bug. 60s is the bar: every observed
    gap in the storm that mattered was longer than that.

    MUTATION: move any organ's run back below its long stagger, or inflate an
    offset past 60s -> RED.
    """
    for entry in STARVED:
        block = _block_for(entry)
        body = block[block.index("(") + 1:]
        run_at = body.index(f"python3 /freqtrade/{entry}")
        sleeps = _sleeps(body)
        assert sleeps, f"{entry}: no sleep found at all — parser or block broke"
        before = [n for pos, n in sleeps if pos < run_at]
        assert len(before) <= 1, (
            f"{entry}: more than one sleep precedes the first run")
        if before:
            assert before[0] <= 60, (
                f"{entry}: boot offset {before[0]}s sits in front of the first "
                f"run. That is the (os)/(ou) bug — an offset longer than the "
                f"gap between container restarts means the organ never runs")
        # The long stagger must sit BETWEEN the boot run and the loop — the
        # loop's own interval is not it, and checking "some sleep follows the
        # run" would be satisfied by the interval alone (a mutant that deleted
        # the stagger survived exactly that weaker assertion).
        while_at = body.index("while true")
        assert run_at < while_at, f"{entry}: boot run is inside the loop"
        between = [n for pos, n in sleeps if run_at < pos < while_at]
        assert between, (
            f"{entry}: the original long stagger is gone. It must survive "
            f"BETWEEN the boot run and the loop, or every organ's steady-state "
            f"phase collapses onto the same few seconds")


def test_the_boot_offsets_are_distinct_so_the_burst_stays_spread():
    """The offsets are a LADDER, not all-zero: the staggers exist to spread
    ~20 organs at boot and collapsing them to one instant trades one bug for
    another. MUTATION: give two organs the same offset -> RED.
    """
    offs = {}
    for entry in STARVED:
        block = _block_for(entry)
        body = block[block.index("(") + 1:]
        run_at = body.index(f"python3 /freqtrade/{entry}")
        before = [n for pos, n in _sleeps(body) if pos < run_at]
        offs[entry] = before[0] if before else 0
    vals = list(offs.values())
    dupes = sorted({o for o in vals if vals.count(o) > 1})
    assert not dupes, (
        f"boot offsets collide (a burst, not a ladder): {offs}")
    assert max(vals) <= 60, f"a boot offset exceeds the 60s bar: {offs}"


def test_the_stagger_survives_for_the_steady_state_loop():
    """The fix must not delete the thundering-herd stagger — it exists to
    spread ~20 organs at boot, and removing it trades one bug for another.
    MUTATION: drop the stagger entirely -> RED.
    """
    block = _immune_block()
    assert "IMMUNE_BOOT_STAGGER_SEC" in block, (
        "the boot stagger is gone; it should be preserved (and overridable), "
        "just no longer able to starve the organ")
    assert "IMMUNE_INTERVAL_SEC" in block, "the steady-state interval is gone"


def test_the_loop_still_cannot_take_the_supervisor_down():
    """`|| true` on every invocation — one sick organ must never kill
    run_all.sh. MUTATION: drop `|| true` -> RED."""
    for entry in STARVED:
        blk = _block_for(entry)
        runs = re.findall(rf"python3 /freqtrade/{re.escape(entry)}[^\n]*", blk)
        assert len(runs) >= 2, f"{entry}: expected boot + loop run, got {runs}"
        for r in runs:
            assert "|| true" in r, f"{entry}: invocation without `|| true`: {r!r}"


def test_run_all_is_still_valid_shell():
    """A syntax error here silences the WHOLE container, not one organ."""
    p = subprocess.run(["bash", "-n", str(RUN_ALL)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


def test_fleet_allocation_rides_the_radar_block():
    """`fleet_allocation.py` has no loop of its own — it runs inside the radar
    block, so it is fixed by that block and would be silently re-starved if it
    were ever split out with a long stagger of its own."""
    blk = _block_for("fleet_radar.py")
    # Twice: once in the boot run, once in the loop. Counting >=1 would pass
    # with it removed from the LOOP, which is the starvation, not the fix.
    n = blk.count("python3 /freqtrade/fleet_allocation.py")
    assert n >= 2, (
        f"fleet_allocation.py appears {n}x in the radar block; it needs BOTH "
        f"the boot run and the loop run, or it publishes once per deploy and "
        f"then never again. If it has grown its own loop, give it a STARVED "
        f"entry and its own boot ladder offset")


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("test_immune_boot_execution: all passed")
