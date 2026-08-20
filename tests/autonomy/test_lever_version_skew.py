"""[2026-08-06 (kp)] A READ-TIME CLAMP IS A VERSION SKEW, NOT AN ADJUSTMENT.

`write_levers` clamps every value against the AUTHOR's registry before it
reaches the bus. So a value that still needs clamping when a CONSUMER reads it
can only mean one of two things, and neither is benign:

  * the author's registry and this container's disagree — a cage moved and this
    image has not been redeployed; or
  * the payload is corrupt / hand-written.

The old behaviour was `min(hi, max(lo, value))` at the consumer: it silently
applied a DIFFERENT number than the author wrote and told nobody. That is the
[[enacted-is-not-applied]] shape — a lever that reads as enacted on the bus
while the book runs something else.

THE LIVE INSTANCE THIS WAS WRITTEN FOR, measured:

    `(ka)` moved {xp,live}.funding.min_vol cage lo from 2e6 -> 1e5 and filed
    `min-vol-1e5` in the judge's queue. BOTH 💸 Farmer arms are marker-gated
    and 17 commits behind, still carrying lo=2e6. When the judge reaches that
    candidate it writes 1e5, the container clamps to 2e6, and the judge grades
    a thin-tier experiment the book never ran — against a value identical to
    the `min-vol-2e6` candidate queued beside it. An A/B measuring the wrong
    arm, silently, on the pipeline that promotes to real money.

Refusing to the OPERATOR DEFAULT is the same fail-safe direction `get_lever`
already takes for a quarantined lever, a measured-bad live lever and a stale
payload: when in doubt, the operator's value.

SHIPPED INERT, verified before writing a line: no lever open on the live bus
(taker.momo_chg, taker.brk_range, evsent.*, scout.dip_range_max,
xp.funding.slope_gate) skews under HEAD's registry OR under either deferred
container's registry. This guard changes nothing today.
"""
import pathlib
import sys
import time
from datetime import datetime, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import fleet_tuning as ft  # noqa: E402


@pytest.fixture
def bus():
    """A fresh in-cage payload writer, plus registry/state restoration."""
    saved = {n: dict(s) for n, s in ft.LEVERS.items()}
    ft._SKEW.clear()
    now = time.time()

    def publish(name, value):
        iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat(
            timespec="seconds")
        ft._cache.update(ts=now, payload={"updated": iso, "ttl_sec": 10800,
                                          "levers": {name: {"value": value}}})
        return now

    yield publish, now
    for n, s in saved.items():
        ft.LEVERS[n] = s
    ft._SKEW.clear()
    ft._cache.clear()


class TestTheKaSkew:
    """The exact live case, replayed through the real accessor."""

    NAME = "xp.funding.min_vol"

    def test_an_old_container_refuses_the_judges_value(self, bus):
        publish, now = bus
        publish(self.NAME, 1e5)
        ft.LEVERS[self.NAME]["lo"] = 2e6              # the deferred container
        got = ft.get_lever(self.NAME, 10e6, now_ts=now)
        assert got == 10e6, (
            "the container applied a value the judge never wrote — the judge "
            "would then grade a thin-tier experiment the book never ran")

    def test_it_says_which_lever_and_what_the_gap_is(self, bus):
        publish, now = bus
        publish(self.NAME, 1e5)
        ft.LEVERS[self.NAME]["lo"] = 2e6
        ft.get_lever(self.NAME, 10e6, now_ts=now)
        skew = ft.skewed_levers()[self.NAME]
        assert skew["written"] == 1e5 and skew["clamped"] == 2e6, skew

    def test_a_redeployed_container_takes_the_value(self, bus):
        publish, now = bus
        publish(self.NAME, 1e5)
        ft.LEVERS[self.NAME]["lo"] = 1e5              # after the marker deploy
        assert ft.get_lever(self.NAME, 10e6, now_ts=now) == 1e5
        assert not ft.skewed_levers()


class TestItIsStateNotAOneShotWarning:
    """I4: never report a persistent condition with a one-shot warning. A skew
    persists until the image is redeployed, so it stays readable that long."""

    def test_the_condition_survives_repeated_reads(self, bus):
        publish, now = bus
        publish("xp.funding.min_vol", 1e5)
        ft.LEVERS["xp.funding.min_vol"]["lo"] = 2e6
        for _ in range(5):
            ft.get_lever("xp.funding.min_vol", 10e6, now_ts=now)
        assert ft.skewed_levers()["xp.funding.min_vol"]["n"] == 5

    def test_it_clears_itself_once_the_value_fits(self, bus):
        publish, now = bus
        publish("xp.funding.min_vol", 1e5)
        ft.LEVERS["xp.funding.min_vol"]["lo"] = 2e6
        ft.get_lever("xp.funding.min_vol", 10e6, now_ts=now)
        assert ft.skewed_levers()
        ft.LEVERS["xp.funding.min_vol"]["lo"] = 1e5
        ft.get_lever("xp.funding.min_vol", 10e6, now_ts=now)
        assert not ft.skewed_levers(), "a healed skew must not linger"


class TestItDoesNotBreakTheNormalPath:
    def test_an_in_cage_value_is_applied_untouched(self, bus):
        publish, now = bus
        publish("xp.funding.min_vol", 5e6)
        assert ft.get_lever("xp.funding.min_vol", 10e6, now_ts=now) == 5e6
        assert not ft.skewed_levers()

    def test_a_csv_lever_still_filters_rather_than_refusing(self, bus):
        """csv levers legitimately drop non-whitelisted members — that is the
        lever's semantics, not a skew, and it must keep working."""
        publish, now = bus
        publish("gapscout.extra_exchanges", "kucoin")
        assert ft.get_lever("gapscout.extra_exchanges", "", now_ts=now) == "kucoin"

    def test_an_unknown_lever_still_returns_the_default(self, bus):
        publish, now = bus
        publish("no.such.lever", 1)
        assert ft.get_lever("no.such.lever", 7, now_ts=now) == 7


class TestItShipsInert:
    """Verified against the live bus before this shipped: nothing currently
    open skews under HEAD's registry. A guard that changes behaviour on day
    one is a change, not a guard — and this one must not move a real-money
    book by surprise."""

    OPEN_ON_THE_BUS = {
        "taker.momo_chg": 6.0,
        "evsent.min_sources": 3, "evsent.severity_bar": 0.55,
        "scout.dip_range_max": 0.2, "xp.funding.slope_gate": 0,
    }

    #: [2026-08-20 (sf)] DELIBERATELY CLAMPED — a live lever this registry now
    #: refuses ON PURPOSE, with the value it snaps back to. Split out rather
    #: than deleted, because "this cage moved a live lever" is a decision that
    #: must stay visible and stay asserted: silently dropping the row would
    #: make the next accidental clamp indistinguishable from this intended one.
    #:
    #: `taker.brk_range` sat at 0.97 — the TIGHTEST end of its old cage, above
    #: the 0.95 module default — put there by the scout-tuner from an
    #: event-sentinel proposal, on 🎫 the Ticket Taker's ONLY living lens. The
    #: tuner's replay cannot fill that lens (`lighter_ticket_replay.py:206`
    #: refuses every breakout entry), so restrict enacted for free and expand
    #: was arithmetically impossible: a one-way ratchet. The cage's restrictive
    #: end is now pinned AT the default, which reverses the lever at the
    #: consumer with no lever write.
    DELIBERATELY_CLAMPED = {"taker.brk_range": (0.97, 0.95)}

    @pytest.mark.parametrize("name,value", sorted(OPEN_ON_THE_BUS.items()))
    def test_no_open_lever_skews_under_head(self, name, value):
        c = ft.clamp(name, value)
        assert c is not None and abs(float(c) - float(value)) < 1e-9, (
            f"{name} would start refusing — this guard is meant to be inert "
            f"on the currently-open set")

    @pytest.mark.parametrize("name,pair", sorted(DELIBERATELY_CLAMPED.items()))
    def test_a_deliberate_clamp_still_clamps_to_the_declared_value(self, name,
                                                                   pair):
        """The other direction, and it is the one that matters: if a later
        cage edit quietly restored the old bound, the ratchet would be back
        and nothing else in the suite would notice."""
        was, becomes = pair
        c = ft.clamp(name, was)
        assert c is not None and abs(float(c) - becomes) < 1e-9, (
            f"{name} no longer clamps {was} -> {becomes}: the (sf) cage pin "
            "has been undone and the one-way ratchet is open again")

    def test_neither_declaration_can_be_emptied_into_silence(self):
        """Caught by a SURVIVING mutation on the day this shipped: emptying
        `DELIBERATELY_CLAMPED` leaves the parametrized test above with zero
        cases, and a parametrize over nothing PASSES. That is the
        check-that-inspects-nothing failure — the guard would go green while
        asserting nothing at all, and the (sf) cage pin could then be undone
        with the suite still clean."""
        assert self.DELIBERATELY_CLAMPED, (
            "the deliberate-clamp declaration is empty — the clamp assertions "
            "above are now vacuous")
        assert self.OPEN_ON_THE_BUS, (
            "the inert-set declaration is empty — same vacuity, other half")

    def test_the_two_sets_are_disjoint(self):
        """A lever cannot be both inert and deliberately clamped — the
        contradiction would make one of the two assertions vacuous."""
        assert not (set(self.OPEN_ON_THE_BUS)
                    & set(self.DELIBERATELY_CLAMPED))
