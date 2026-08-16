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


def _immune_block() -> str:
    """The `( ... ) &` subshell that launches fleet_immune.py."""
    src = RUN_ALL.read_text()
    i = src.index("python3 /freqtrade/fleet_immune.py")
    start = src.rindex("\n( ", 0, i) + 1
    end = src.index(") &", i) + 3
    return src[start:end]


def test_the_organ_runs_once_before_any_boot_stagger():
    """THE PROPERTY. A restart must always yield one execution.

    MUTATION: move the run back below the stagger -> RED.
    """
    block = _immune_block()
    body = block[block.index("(") + 1:]
    run_at = body.index("python3 /freqtrade/fleet_immune.py")
    sleeps = [m.start() for m in re.finditer(r"\bsleep\b", body)]
    assert sleeps, "expected the boot stagger to still exist"
    assert run_at < sleeps[0], (
        "fleet_immune.py is launched behind a sleep: a container restart "
        "before the fuse expires means the organ never runs at all, which is "
        "exactly the 41-minute silence this test names")


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
    block = _immune_block()
    runs = re.findall(r"python3 /freqtrade/fleet_immune\.py[^\n]*", block)
    assert len(runs) >= 2, f"expected a boot run and a loop run, got {runs}"
    for r in runs:
        assert "|| true" in r, f"invocation without `|| true`: {r!r}"


def test_run_all_is_still_valid_shell():
    """A syntax error here silences the WHOLE container, not one organ."""
    p = subprocess.run(["bash", "-n", str(RUN_ALL)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


def test_the_starved_siblings_are_declared_not_forgotten():
    """Seven organs share the shape and are deliberately NOT patched here.

    Declared in the comment so the next reader finds a decision rather than an
    oversight — the `BORN_DARK_OK` idiom. If someone fixes them, this
    assertion is what tells them to update the note.
    """
    src = RUN_ALL.read_text()
    i = src.index("python3 /freqtrade/fleet_immune.py")
    note = src[max(0, i - 3000):i]
    for organ in ("proprioception", "judge", "scout-tuner", "incubator",
                  "regen", "radar", "impl-shortfall"):
        assert organ in note, (
            f"the sibling organ {organ!r} is no longer named in the "
            f"declaration of what this fix deliberately leaves unpatched")


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("test_immune_boot_execution: all passed")
