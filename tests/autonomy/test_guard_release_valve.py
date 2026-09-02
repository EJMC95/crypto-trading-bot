"""[2026-09-02 (wj)] The operator release valve for a latched protections lock.

The (vn) latch is durable by design; the day the (wf) denominator fix deployed
it kept honouring a maxdd lock STAMPED by the defective rail (avo, expiry
04:02:46Z, $12.56 bar on a $305 book). `release_latched_guard` clears exactly
the latch whose stored expiry matches `{PFX}_RELEASE_GUARD_AT` within ±2s and
touches nothing else. These drive the pure function directly — the caller owns
persistence, the same split entries_lock itself uses.

Mutation notes (verified red while writing):
- tolerance 2.0 -> 8*3600: `test_five_seconds_off_is_kept` reddens.
- drop the abs(): the kept case stores the expiry BELOW the target, so the
  signed diff (-5.0) would pass a bare `<= 2.0` and the same test reddens.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

os.environ.setdefault("AVO_VENUE", "lighter_live")

from lighter_avo_live_bot import release_latched_guard  # noqa: E402

# The real incident's stamp; the epoch is DERIVED by the same parse the valve
# runs, because the stored latch is a float the row's iso() renders as this
# string — the round-trip identity is exactly what the valve relies on.
RGA = "2026-09-02T04:02:46+00:00"
TS = datetime.fromisoformat(RGA).timestamp()


def test_exact_match_releases():
    out = release_latched_guard([TS, "maxdd"], RGA)
    assert out == [0.0, None], out


def test_sub_second_fraction_still_releases():
    # entries_lock stores t_now + stop*tf as a float; iso() output truncates.
    out = release_latched_guard([TS + 0.7, "maxdd"], RGA)
    assert out == [0.0, None], out


def test_five_seconds_off_is_kept():
    # Stored BELOW the target on purpose: kills both the widened-tolerance
    # mutation and the dropped-abs mutation (signed diff -5.0 <= 2.0).
    latch = [TS - 5.0, "maxdd"]
    assert release_latched_guard(latch, RGA) is latch


def test_unset_env_releases_nothing():
    latch = [TS, "maxdd"]
    assert release_latched_guard(latch, "") is latch
    assert release_latched_guard(latch, None) is latch


def test_garbage_env_releases_nothing():
    latch = [TS, "slguard"]
    assert release_latched_guard(latch, "tomorrowish") is latch
    assert release_latched_guard(latch, "2026-13-45T99:99:99Z") is latch


def test_zulu_suffix_parses():
    out = release_latched_guard([TS, "maxdd"], "2026-09-02T04:02:46Z")
    assert out == [0.0, None], out


def test_unlatched_book_is_untouched():
    latch = [0.0, None]
    assert release_latched_guard(latch, RGA) is latch


def test_degenerate_latch_shapes_never_raise():
    for bad in ([None, None], ["junk", "maxdd"], [], None):
        assert release_latched_guard(bad, RGA) is bad
