"""[(od), 16-Aug] THE IMMUNE ORGAN PREFERS A COUNTER OVER AN INFERENCE.

`restart_churn` detects a restarting publisher by watching a monotone counter
RESET — and its own docstring is honest that a reset is only visible BETWEEN
samples, so "the counted number depends on when this organ happens to wake
up", reading ZERO at an unlucky phase while the organ restarts 96x/day. The
`churn_from_history` fallback reconstructs the publisher's series to reduce
that aliasing, but it depends on the history being readable.

`(nz)` gave 🏛️ the Parliament a restart counter that survives its own death
(persisted in the ecosystem DB on the Railway volume, monotone), after the
supervisor restarted 10x in 48h while its own payload reported `errors: 0`.
With an authoritative count the deaths can be READ instead of inferred: two
sightings N apart mean exactly N deaths, at any sampling phase.
"""
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import fleet_immune as fi  # noqa: E402

NOW = time.time()


def _state(cycles, restarts=None, age_s=0, build="img-A"):
    p = {"updated": dt.datetime.fromtimestamp(
             NOW - age_s, dt.timezone.utc).isoformat(),
         "ttl_sec": 900, "data": {"cycles": cycles}}
    if restarts is not None:
        p["restarts"] = restarts
    if build is not None:
        p["build"] = build
    return {"parliament": p}


def test_the_count_is_exact_at_a_phase_the_reset_heuristic_misses():
    """THE CASE THAT MOTIVATED IT: cycles never regresses between samples
    (each boot climbed past the last seen value before the next sweep), so
    the reset heuristic sees NOTHING while five restarts happened."""
    seen = {}
    assert fi.restart_churn(_state(100, 1), seen, NOW) == []   # first sighting
    out = fi.restart_churn(_state(140, 6), seen, NOW + 60)
    assert out, "five deaths went uncounted — the aliasing this closes"
    assert "5 RESTART(s)" in out[0]["detail"], out
    assert "durable counter" in out[0]["detail"], out


def test_a_first_sighting_claims_nothing():
    assert fi.restart_churn(_state(50, 99), {}, NOW) == []


def test_a_healthy_advance_stays_quiet():
    seen = {}
    fi.restart_churn(_state(10, 4), seen, NOW)
    assert fi.restart_churn(_state(300, 4), seen, NOW + 600) == []


def test_a_decrease_in_the_durable_counter_is_not_a_restart():
    """The store was reset or restored from a snapshot. That is not evidence
    of a death and must not be counted as one (fail-safe toward silence)."""
    seen = {}
    fi.restart_churn(_state(10, 40), seen, NOW)
    assert fi.restart_churn(_state(20, 2), seen, NOW + 60) == []


def test_an_organ_without_the_field_keeps_the_old_inference():
    """Backward compatibility: a 2-tuple declaration, or a publisher that has
    not deployed the counter yet, still gets the reset/stall heuristic."""
    seen = {}
    fi.restart_churn(_state(100), seen, NOW)
    fi.restart_churn(_state(0), seen, NOW + 60)
    assert seen["parliament"].get("basis"), seen
    assert "counter" not in (seen["parliament"]["basis"] or "")


def test_a_stale_payload_still_claims_nothing():
    """A stale organ is the watchdog's jurisdiction — unchanged by (od)."""
    seen = {}
    assert fi.restart_churn(_state(10, 1, age_s=99999), seen, NOW) == []


# ---------------------------------------------------------------------------
# [(oi)] A DEPLOY IS NOT A DEATH — the discriminator the detector's own
# comment said was missing. MEASURED: all 10 "restarts in 48h" that paged the
# operator correlated with a deploy run inside 15 minutes, ZERO unexplained.
# Two sessions pushing ~12 times in 40 minutes is deploy churn, not a
# crash-loop, and paging for it is the (gl) cry-wolf shape.
# ---------------------------------------------------------------------------
def test_increments_on_a_NEW_build_are_deploys_and_never_page():
    seen = {}
    fi.restart_churn(_state(100, 1, build="img-A"), seen, NOW)
    for i, n in enumerate((2, 3, 4, 5, 6), start=1):
        out = fi.restart_churn(
            _state(3, n, build=f"img-{n}"), seen, NOW + 60 * i)
        assert out == [], f"a deploy paged the operator at restart {n}: {out}"


def test_increments_on_the_SAME_build_are_real_deaths():
    seen = {}
    fi.restart_churn(_state(100, 1, build="img-A"), seen, NOW)
    out = fi.restart_churn(_state(3, 6, build="img-A"), seen, NOW + 60)
    assert out and "5 RESTART(s)" in out[0]["detail"], out


def test_a_publisher_with_no_build_stamp_keeps_counting_everything():
    """Fail-safe: an organ that cannot say which image it runs must not have
    its deaths silently absorbed — UNKNOWN is not 'it was a deploy'."""
    seen = {}
    fi.restart_churn(_state(100, 1, build=None), seen, NOW)
    out = fi.restart_churn(_state(3, 6, build=None), seen, NOW + 60)
    assert out and "5 RESTART(s)" in out[0]["detail"], out
