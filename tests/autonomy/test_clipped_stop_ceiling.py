"""The ceiling the mmf clip ACTUALLY enforces, and the pager that reads it.

INCIDENT (2026-09-11 (aau)). Eamon raised 👩 mum's gross 5.0x -> 9.5x. The
immune organ paged `protective stop is DEAD at gross 9.5 (ceiling 4.17) —
liquidation fires before the stop`, and it fired on ~14.5 of ~99 cycles that
day. The number is real and the verdict is wrong: **4.17 is the CLIP-OFF
bound**, `1/(|stop| + worst_mmf)`, and `mmf_clip_factor` has scaled the
high-margin coins since (vy) precisely so that stop stays alive. Her clip-ON
ceiling is **10.0x**, so the page was true at any gross above 4.17 — a
condition met by CONFIGURATION, which is I7's "a trigger a book satisfies
structurally is not a measurement". The number that actually bound her, the
headroom at her own measured slippage (**+0.0066x** at 9.5 against a 9.5066x
ceiling), was published NOWHERE — it took a 45-agent workflow to compute what
the row should have carried every loop (I23: the decider must see what it
steers).

THE CLOSED FORM, and it is the shipped clip's own arithmetic rather than a
second copy. `mmf_clip_factor` scales a coin by `(sl+REF)/(sl+mmf)` exactly
when the stop would otherwise die, which EQUALISES maintenance-per-deployed-
dollar at `MMF_CLIP_REF` for every tier at or above it, so the whole family
collapses to one number:

    G_dead = 1 / (|stop| + min(mmf, MMF_CLIP_REF))

`test_the_closed_form_is_the_shipped_clips_own_arithmetic` brute-forces the
SHIPPED `mmf_clip_factor` over uniform and mixed 12-leg baskets and pins the
agreement, so the form cannot drift from the function it summarises.

WHAT WAS REFUSED, recorded so it is not re-proposed: adding `stop_dead` to
`fleet_immune.HEADROOM_OK` to quiet the page. It silences the structural false
positive AND the true positive underneath it — the condition the limb exists
for — and an exemption granted to quiet a pre-existing alarm is how a guard
stops guarding.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_immune                                   # noqa: E402
import lighter_avo_live_bot as host                   # noqa: E402

#: 👩 mum's stop, passed EXPLICITLY to every call rather than read from
#: `host.S.stoploss`. Two reasons, both load-bearing: the host resolves its
#: book from `FAMILY_LIVE_BOOK` AT IMPORT, so reading `S` would make these
#: assertions depend on which test module imported it first (avo's -10% and
#: mum's -4% give different ceilings); and setting that env at module level is
#: what `test_no_test_module_mutates_process_env_at_import` forbids — a
#: ratchet this file tripped on its first run, correctly.
STOP = 0.04


def _margin_map(basket):
    """The venue's OWN shape — `{sym: {"mmf_bps": ...}}`. Built from the real
    key so the fixture cannot encode the assumption under test: the first cut
    of this helper passed `{"mmf": m}`, `coin_mmf` returned None, and every
    leg silently degraded to MMF_CLIP_UNKNOWN."""
    return {f"C{i}": {"mmf_bps": m * 1e4} for i, m in enumerate(basket)}


def _basket_liq_move(gross, basket):
    """Adverse move that reaches maintenance, using the SHIPPED clip."""
    rows = _margin_map(basket)
    fs = [host.mmf_clip_factor(f"C{i}", rows, gross=gross, stop=STOP)[0]
          for i in range(len(basket))]
    sf = sum(fs)
    sfm = sum(f * m for f, m in zip(fs, basket))
    return len(basket) / (gross * sf) - sfm / sf


def _brute_ceiling(basket, stop):
    lo, hi = 1.0, 60.0
    for _ in range(90):
        mid = (lo + hi) / 2.0
        if _basket_liq_move(mid, basket) > stop:
            lo = mid
        else:
            hi = mid
    return lo


@pytest.mark.parametrize("mmf", [0.012, 0.03, 0.06, 0.075, 0.12, 0.20, 0.30])
def test_the_closed_form_is_the_shipped_clips_own_arithmetic(mmf):
    """The published ceiling must equal what the SHIPPED clip actually does.

    A retyped formula is a formula that drifts; this brute-forces
    `mmf_clip_factor` itself over a uniform 12-leg basket and pins agreement.
    """
    stop = STOP
    assert host.clipped_stop_ceiling(mmf, stop) == pytest.approx(
        _brute_ceiling([mmf] * 12, stop), rel=1e-3)


def test_a_mixed_basket_is_bound_by_the_reference_tier_not_the_worst_coin():
    """The counter-intuitive half, brute-forced: 8x0.20 + 4x0.12 does NOT
    liquidate earlier than a pure 600bps basket, because the clip has already
    shrunk both high tiers to the same maintenance-per-dollar."""
    stop = STOP
    mixed = _brute_ceiling([0.20] * 8 + [0.12] * 4, stop)
    assert mixed == pytest.approx(host.clipped_stop_ceiling(0.20, stop),
                                  rel=1e-3)


def test_every_tier_at_or_above_the_clip_reference_collapses_to_one_ceiling():
    """The clip equalises them — so the binding basket is the REF tier, not
    the highest-margin one, which is the counter-intuitive half of (aau)."""
    stop = STOP
    ref = host.clipped_stop_ceiling(host.MMF_CLIP_REF, stop)
    for m in (0.075, 0.12, 0.20, 0.30, 0.50):
        assert host.clipped_stop_ceiling(m, stop) == ref
    # ...and it is STRICTLY above the clip-OFF bound the row used to publish.
    assert ref > host.stop_reachable(0.20)[1]


def test_a_dark_margin_read_publishes_no_ceiling_at_all():
    """I1/I8: the closed form needs no margin map, so computing it anyway
    would turn a DARK read into an affirmative green on a levered row."""
    assert host.clipped_stop_ceiling(None, STOP) is None


def test_a_thin_overshoot_sample_may_not_call_itself_measured():
    """Below OVERSHOOT_MIN_N only the nominal basis exists — the same floor
    and the same reason as `_honest_stop_cost`."""
    thin = host.stop_bases({"n": 3, "vals": [10.0, 20.0, 30.0]}, stop=STOP)
    assert set(thin) == {"nominal"}
    n = host.OVERSHOOT_MIN_N
    fat = host.stop_bases({"n": n, "vals": [10.0] * n}, stop=STOP)
    assert {"nominal", "measured_p90", "measured_worst"} <= set(fat)
    # a fill BETTER than the level does not earn leverage
    better = host.stop_bases({"n": n, "vals": [-50.0] * n}, stop=STOP)
    assert better["measured_p90"] == pytest.approx(better["nominal"])


def _row(bot="freqtrade-mum-lighter", **lev):
    base = {"set": 9.5, "mmf": 0.20, "stop_reachable": False,
            "stop_dead_above": 4.17, "stop_reachable_held": None,
            "headroom": {"ok": True, "reason": "flat"}}
    base.update(lev)
    return {"bot": bot, "updated": "2026-09-11T01:00:00+00:00",
            "ttl_sec": 3600, "open_trades": 1,
            "extra": {"leverage": base}}


def _details(rows, ok=None):
    return " | ".join(f["detail"] for f
                      in fleet_immune.headroom_sickness(rows, ok=ok or {}))


def test_the_pager_reads_the_clip_on_verdict_not_the_clip_off_bound():
    """The whole point: a book INSIDE its clip-ON ceiling must not page, even
    though the clip-OFF `stop_reachable` is False by configuration."""
    alive = _row(stop_reachable_eff=True, gross_x_max_alive=10.0,
                 stop_ceiling_basis="measured_p90", gross_x_headroom=0.0066,
                 headroom={"ok": True, "reason": "measured"})
    assert fleet_immune.headroom_sickness([alive], ok={}) == []


def test_a_genuinely_dead_stop_still_pages_and_names_the_real_ceiling():
    dead = _row(set=9.6, stop_reachable_eff=False, gross_x_max_alive=9.5066,
                stop_ceiling_basis="measured_p90", gross_x_headroom=-0.0934,
                headroom={"ok": True, "reason": "measured"})
    d = _details([dead])
    assert "DEAD" in d and "9.5066" in d and "mmf clip" in d


def test_a_row_with_the_clip_on_verdict_never_reports_the_clip_off_ceiling():
    """The branch ORDER is the property: once a row publishes the clip-ON
    verdict, the 4.17x clip-OFF bound must never reach the operator — not as
    a second finding and not as a fallback. Pins what the removed redundant
    `and _eff is None` clause was trying to say, in a form a mutation kills."""
    dead = _row(set=9.6, stop_reachable_eff=False, gross_x_max_alive=9.5066,
                stop_ceiling_basis="measured_p90", gross_x_headroom=-0.0934,
                headroom={"ok": True, "reason": "measured"})
    found = fleet_immune.headroom_sickness([dead], ok={})
    assert len(found) == 1
    assert "4.17" not in found[0]["detail"]


def test_a_row_without_the_new_field_keeps_the_old_reading():
    """Nothing goes quiet in the deploy window — the (wp) rule."""
    legacy = _row(headroom={"ok": True, "reason": "measured"})
    assert "ceiling 4.17" in _details([legacy])


def test_a_dark_margin_read_is_not_silent_on_a_levered_book():
    """I1/I4: every other limb fires only on `is False`, so a dark bus — which
    ALSO turns the clip off — used to page nothing at all."""
    dark = _row(mmf=None, stop_reachable=None, stop_reachable_eff=None,
                stop_dead_above=None,
                headroom={"ok": True, "reason": "measured"})
    assert "DARK" in _details([dark])


def test_an_unlevered_book_does_not_page_on_an_organ_outage():
    """A 1x book does not need the answer, and an outage must not page it."""
    dark1x = _row(set=1.0, mmf=None, stop_reachable=None,
                  stop_reachable_eff=None, stop_dead_above=None,
                  headroom={"ok": True, "reason": "measured"})
    assert fleet_immune.headroom_sickness([dark1x], ok={}) == []
