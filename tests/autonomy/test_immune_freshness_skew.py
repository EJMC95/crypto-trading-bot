"""🛡️ `_fresh` must not call a payload FUTURE-DATED over float rounding.

[2026-08-16 (ol)] THE INCIDENT. `test_restart_counter_authority` — shipped the
same day by `(od)` — failed intermittently on main and in CI: ~30% of runs
measured locally, three of its tests red in run 31924… while the other 1,400
passed. It was not the Parliament logic. `_fresh` refused ANY negative age:

    return 0 <= age <= horizon

and the test stamps `updated` from its own clock:

    NOW = time.time()
    updated = datetime.fromtimestamp(NOW, utc).isoformat()
    ...
    restart_churn(state, seen, NOW)          # age should be exactly 0.0

`datetime.fromtimestamp` rounds to the nearest MICROSECOND, so the round trip
`float -> datetime -> isoformat -> float` lands a few hundred nanoseconds in the
FUTURE **38% of the time** (measured over 10,000 draws). Age is then ~-2e-7,
`0 <= age` is False, the payload reads as unusable, the first sighting is
skipped, `seen` stays empty — and the SECOND call becomes the first sighting and
reports nothing. The test asked for five deaths and got `[]`.

WHY THIS IS A PRODUCTION BUG AND NOT A TEST BUG. The same arithmetic runs
against real payloads, where publisher and reader are DIFFERENT CONTAINERS: any
NTP skew that leaves the publisher a few milliseconds ahead dates its payload in
the reader's future and this organ skips it. And the direction is the dangerous
one — every `_fresh` call site is `if _fresh(...)` guarding a CHECK, so refusing
does not make the immune organ careful, it makes it BLIND, which is the failure
class the whole file exists to catch (I1). A detector that switches itself off
on a nanosecond of rounding is exactly the "guard that cannot fire" shape.

The fix is a bounded tolerance (`FUTURE_SKEW_S`), not an unbounded one: a
payload dated minutes ahead is still refused, because THAT is a real fault.

DETERMINISTIC BY CONSTRUCTION. `_ROUNDS_UP` is a fixed epoch float found by
search whose round trip provably lands in the future; the first test asserts
that property still holds, so if CPython ever changes its rounding this file
says so instead of quietly passing. Nothing here samples the wall clock.
"""
import datetime as dt

import pytest

import fleet_immune as fi

pytestmark = pytest.mark.autonomy

# round-trips to +2.384e-07s (see the module docstring); 2025-08-15T23:20:00.000001Z
_ROUNDS_UP = 1755300000.0000007


def _stamp(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


def test_the_fixture_still_reproduces_the_rounding():
    """The premise of every assertion below — asserted, not assumed."""
    round_tripped = dt.datetime.fromisoformat(_stamp(_ROUNDS_UP)).timestamp()
    assert round_tripped > _ROUNDS_UP, (
        "the chosen timestamp no longer rounds UP — CPython's conversion "
        "changed, so this file is testing nothing; pick a new _ROUNDS_UP")
    assert round_tripped - _ROUNDS_UP < 1e-6, "rounding is sub-microsecond"


def test_a_payload_stamped_from_the_readers_own_clock_is_fresh():
    """THE REGRESSION. age is ~-2e-7 here; pre-(ol) this returned False."""
    st = {"updated": _stamp(_ROUNDS_UP), "ttl_sec": 900}
    assert fi._fresh(st, _ROUNDS_UP) is True, (
        "a payload stamped from this very clock reads as future-dated — the "
        "organ skips it and every check behind it goes silently blind")


def test_a_millisecond_of_container_clock_skew_is_tolerated():
    """The production shape: the publisher's clock runs slightly ahead."""
    for skew_ms in (1, 10, 250):
        st = {"updated": _stamp(_ROUNDS_UP + skew_ms / 1000.0), "ttl_sec": 900}
        assert fi._fresh(st, _ROUNDS_UP) is True, f"{skew_ms}ms of skew blinded it"


def test_the_future_guard_still_means_something():
    """Bounded, not removed — a payload dated well ahead is still refused.

    Without this the 'fix' is just deleting the guard, and a corrupt or wildly
    skewed write would be read as current.
    """
    st = {"updated": _stamp(_ROUNDS_UP + 600.0), "ttl_sec": 900}
    assert fi._fresh(st, _ROUNDS_UP) is False, \
        "ten minutes in the future must still be refused"
    edge = {"updated": _stamp(_ROUNDS_UP + fi.FUTURE_SKEW_S + 1.0), "ttl_sec": 900}
    assert fi._fresh(edge, _ROUNDS_UP) is False, \
        "beyond FUTURE_SKEW_S must be refused — the bound is the point"


def test_the_stale_side_is_untouched():
    """(ol) moved the lower bound only; ageing out is the guard's day job."""
    st = {"updated": _stamp(_ROUNDS_UP - 1000.0), "ttl_sec": 900}
    assert fi._fresh(st, _ROUNDS_UP) is False, "past its ttl must still be stale"
    ok = {"updated": _stamp(_ROUNDS_UP - 100.0), "ttl_sec": 900}
    assert fi._fresh(ok, _ROUNDS_UP) is True
    assert fi._fresh({"updated": "not-a-date", "ttl_sec": 900}, _ROUNDS_UP) is False


def test_the_consequence_the_incident_actually_showed():
    """End to end on the organ that broke: same-clock stamps, deaths counted.

    `_fresh` is a helper; what the incident showed is a DETECTOR reporting
    nothing. This drives `restart_churn` the way (od)'s test does — first
    sighting stamped from the same clock the call passes — and asserts the five
    restarts are reported. Pre-(ol) this returned [] about 38% of the time.
    """
    def state(cycles, restarts, at):
        return {"parliament": {"updated": _stamp(at), "ttl_sec": 900,
                               "data": {"cycles": cycles},
                               "restarts": restarts}}

    seen = {}
    assert fi.restart_churn(state(100, 1, _ROUNDS_UP), seen, _ROUNDS_UP) == []
    assert seen, (
        "the first sighting recorded NOTHING — the organ has no memory to "
        "compare against and the next sweep restarts from scratch, forever")
    out = fi.restart_churn(state(140, 6, _ROUNDS_UP), seen, _ROUNDS_UP + 60)
    assert out, "five deaths went uncounted"
    assert "5 RESTART(s)" in out[0]["detail"], out
