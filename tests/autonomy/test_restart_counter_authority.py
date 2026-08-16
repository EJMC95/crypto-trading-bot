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


# ---------------------------------------------------------------------------
# [(ok)] THE RESIDUAL A PEER SESSION FOUND BY REPLAYING THE DISCRIMINATOR:
# freqtrade-bots also redeploys on `run_all.sh` and `user_data/**`, neither of
# which is in `build_compute`'s set — so a commit touching only those would
# restart the container with an IDENTICAL stamp and read as a CRASH. The
# question the stamp must answer is "did the CONTAINER change?", which is
# strictly wider than "did my module set change?".
# ---------------------------------------------------------------------------
def _mk_image(root):
    (root / "parliament").mkdir(parents=True)
    (root / "parliament").joinpath("brain.py").write_text("B = 1\n")
    (root / "parliament_main.py").write_text("M = 1\n")
    (root / "run_all.sh").write_text("echo one\n")
    (root / "fleet_immune.py").write_text("I = 1\n")
    (root / "user_data").mkdir()
    (root / "user_data" / "s.py").write_text("S = 1\n")
    (root / "persist").mkdir()
    (root / "persist" / "db.json").write_text('{"n": 1}\n')


def _stamp(root, monkeypatch):
    import parliament.brain as brain
    from parliament.ecosystem_db import EcosystemDB
    monkeypatch.setattr(brain, "__file__", str(root / "parliament" / "brain.py"))
    h = brain.Howard(db=EcosystemDB(path=":memory:"))
    h._build = None
    return h.build_stamp()


def test_any_shipped_file_moves_the_stamp(tmp_path, monkeypatch):
    """[(ok)] The container redeploys on ~30 organ modules, run_all.sh and
    user_data/** — a deploy touching ANY of them must move the stamp, or the
    restart it causes reads as a CRASH. MEASURED: the 04:08Z same-build
    restart followed a deploy whose commit touched fleet_immune.py, which is
    in the container's trigger set and in no bot's _BUILD_SHARED."""
    root = tmp_path / "img"
    _mk_image(root)
    base = _stamp(root, monkeypatch)
    assert base

    for path, new in ((root / "fleet_immune.py", "I = 2\n"),
                      (root / "run_all.sh", "echo two\n"),
                      (root / "user_data" / "s.py", "S = 2\n"),
                      (root / "parliament_main.py", "M = 2\n")):
        before = _stamp(root, monkeypatch)
        path.write_text(new)
        assert _stamp(root, monkeypatch) != before, f"{path.name} did not move it"


def test_the_persist_VOLUME_does_not_move_the_stamp(tmp_path, monkeypatch):
    """The volume changes constantly (a live SQLite file). If it were hashed,
    every publish would look like a deploy and every real crash would be
    absorbed — the failure mode that matters most here."""
    root = tmp_path / "img"
    _mk_image(root)
    before = _stamp(root, monkeypatch)
    (root / "persist" / "db.json").write_text('{"n": 99999}\n')
    assert _stamp(root, monkeypatch) == before, (
        "the persist volume is inside the stamp — every publish would read "
        "as a deploy and no crash could ever be reported")


def test_an_unreadable_image_publishes_UNKNOWN_not_a_constant(tmp_path,
                                                              monkeypatch):
    root = tmp_path / "empty"
    (root / "parliament").mkdir(parents=True)
    assert _stamp(root, monkeypatch) is None
