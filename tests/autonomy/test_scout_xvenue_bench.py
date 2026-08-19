"""[19-Aug (qh)] THE CROSS-VENUE BENCH MUST BE THE FULL CROSS-SECTION.

`funding_divergence` is published truncated to the top 5, and that truncation
is why the 19-Aug divergence study could recover a per-coin gap AT OPEN for
only 15 of 270 era funding-book closes — it had to reconstruct the bench
externally to reach a verdict at all. `xvenue_funding` exists to fix exactly
that, so the property under test is that it does NOT inherit the truncation.

The module's own selftest cannot test this: its fixture has 2 divergent coins,
so `divergence[:5]` and `divergence` are the same list and the assertion is
vacuous — measured, by a mutation that survived it. This file supplies the
>5-coin cross-section that makes the difference observable.
"""
import pytest

import lighter_market_scout as scout

pytestmark = pytest.mark.autonomy


def _stats(syms):
    return {s: {"prem_bps": 1.0, "qvol": 5e6, "oi": 1.0, "liquid": True,
                "last": 100.0, "high": 101.0, "low": 99.0, "chg": 0.5}
            for s in syms}


def _wide():
    """8 liquid coins with a cross-venue quote — comfortably past the top-5
    cut — plus one with NO external quote."""
    syms = [f"C{i}" for i in range(8)]
    stats = _stats(syms + ["NOBENCH"])
    # descending |gap| so the truncation, if present, keeps C0..C4
    lighter_apr = {s: 50.0 - 5.0 * i for i, s in enumerate(syms)}
    lighter_apr["NOBENCH"] = 12.0
    other_aprs = {s: [1.0, 1.5] for s in syms}      # NOBENCH deliberately absent
    return stats, lighter_apr, other_aprs, syms


def test_bench_is_not_truncated_to_the_published_top_five():
    stats, lighter_apr, other_aprs, syms = _wide()
    snap = scout.build_snapshot(stats, lighter_apr, other_aprs, {})
    bench = snap["xvenue_funding"]
    assert len(snap["funding_divergence"]) == 5, \
        "precondition: the published list IS truncated to 5"
    assert len(bench) == len(syms) == 8, (
        f"bench must carry every benched coin, not the top 5 — got "
        f"{sorted(bench)}")
    for s in syms:
        assert s in bench, f"{s} missing from the bench"


def test_a_coin_with_no_external_quote_is_absent_never_zero():
    """I6/I8: 'no bench' and 'a bench of zero' are different facts, and the
    tokenised non-crypto symbols genuinely have no external bench."""
    stats, lighter_apr, other_aprs, _ = _wide()
    snap = scout.build_snapshot(stats, lighter_apr, other_aprs, {})
    assert "NOBENCH" not in snap["xvenue_funding"], \
        "an unbenched coin must be ABSENT, never 0.0"


def test_bench_survives_into_history():
    """It exists only to be joined to a decision after the fact — a key
    dropped by historized() is the difference between evidence and nothing."""
    stats, lighter_apr, other_aprs, syms = _wide()
    snap = scout.build_snapshot(stats, lighter_apr, other_aprs, {})
    h = scout.historized(snap)
    assert "xvenue_funding" in h
    assert h["xvenue_funding"] == snap["xvenue_funding"]
    assert len(h["xvenue_funding"]) == 8


def test_bench_values_are_the_cross_venue_median_not_lighters_own():
    stats, lighter_apr, other_aprs, syms = _wide()
    snap = scout.build_snapshot(stats, lighter_apr, other_aprs, {})
    for s in syms:
        # derive the expectation from the OWNER of the rule, never a second
        # hardcoded copy ((hj)) — this module's _median takes the upper
        # element on an even-length list, which a hand-written 1.25 got wrong.
        want = round(scout._median(other_aprs[s]), 1)
        assert snap["xvenue_funding"][s] == want, \
            "bench must be the OTHER venues' median, not Lighter's own apr"
        assert snap["xvenue_funding"][s] != lighter_apr[s], \
            "a bench equal to Lighter's own rate would make every gap zero"
