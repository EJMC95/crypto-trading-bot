"""[2026-09-02 (wv)] THE JUDGE HAS A LIVING LANE AGAIN — 👩 mum's.

The (wp) review found the fleet's only path from a shadow candidate to real
money had no pair it could open: the Farmer lane retired 22-Aug, georgia
retired, mum and avo blocked on scan-order parity (ported at (wp)). And the
family shadow host had NO lever surface — no fleet_tuning, no `bars` receipt —
so even an open pair could never run a candidate. This is the build:

  * xp.mum.rsi_max / xp.mum.max_hold_min steer ONLY her shadow twin;
    live.mum.rsi_max / live.mum.max_hold_min are written ONLY by the judge
    after the paired bar (prefix owner), her clip scale stays the board's;
  * both hosts stamp `bars` at entry and copy it to the close row — the
    judge's fail-closed `ran_candidate` receipt — and record `rsi_entry`,
    the quantity rsi_max cuts (I23);
  * the serial lane DERIVES from fleet_bus.living_pair_default (no literal),
    candidates are per lane, and a queue proposal must carry the lane's
    prefix (a Farmer offspring cannot burn a mum slot);
  * an open position keeps the cap it was stamped with (the (bw) rule).

Mutations that turn these red: the board owning live.mum.rsi_max; a mum
lever off XP_TO_LIVE or LIVE_ENV_DEFAULTS; `mum_bars` dropping a key;
apply_book_levers mutating the CLASS; candidate_pool admitting xp.funding.*
on the mum lane; the live host stamping no `bars`.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import experiment_judge as ej      # noqa: E402
import fleet_bus as fb             # noqa: E402
import fleet_tuning as ft          # noqa: E402
import lighter_family_bot as fam   # noqa: E402

pytestmark = pytest.mark.autonomy

MUM = "freqtrade-mum-lighter"
FARMER = "perps-funding-lighter-lighter"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _mum():
    return next(s for s in fam.STRATEGIES if s.bot == "freqtrade-mum")


def test_the_serial_lane_is_the_living_pair_and_it_is_mum():
    assert not fb.live_arm_retired(ej.LIVE_BOT)
    assert ej.serial_lane_id() == "mum" and ej.LIVE_BOT == MUM
    assert ej.SHADOW_BOT == "freqtrade-mum-lshadow"
    assert [c["name"] for c in ej.CANDIDATES] == [c["name"] for c in ej.MUM_CANDIDATES]
    assert ej.lane_prefix() == "xp.mum." and ej.lane_prefix(FARMER) == "xp.funding."


def test_the_levers_are_registered_caged_mapped_and_judge_owned():
    for xk, lk in (("xp.mum.rsi_max", "live.mum.rsi_max"),
                   ("xp.mum.max_hold_min", "live.mum.max_hold_min")):
        assert ft.LEVERS[xk]["lane"] == "lighter-xp"
        assert ft.LEVERS[lk]["lane"] == "lighter-live"
        assert ej.XP_TO_LIVE[xk] == lk and lk in ej.LIVE_ENV_DEFAULTS
        assert ft.LEVERS[xk]["env_default"] == ft.LEVERS[lk]["env_default"] \
            == ej.LIVE_ENV_DEFAULTS[lk][0]
        # the judge, and only the judge, writes the live twin
        for author in ft.AUTHOR_LANES:
            assert ft._author_may_write(lk, "lighter-live", author) == \
                (author == "experiment-judge"), (lk, author)
    # ...while her clip scale stays the board's (exact key wins first)
    assert ft._author_may_write("live.mum.clip_scale", "lighter-live", "evidence-board")
    assert not ft._author_may_write("live.mum.clip_scale", "lighter-live", "experiment-judge")


def test_every_candidate_is_inside_both_cages():
    for c in ej.MUM_CANDIDATES:
        for k, v in c["levers"].items():
            assert ft.clamp(k, v) == v and ft.clamp(ej.XP_TO_LIVE[k], v) == v


def test_a_farmer_offspring_cannot_land_on_the_mum_lane():
    from datetime import datetime, timezone
    q = {"updated": datetime.now(timezone.utc).isoformat(), "ttl_sec": 10800,
         "candidates": [{"name": "xp-enter_apr-0.3",
                         "levers": {"xp.funding.enter_apr": 0.3}},
                        {"name": "mum-rsi-30", "levers": {"xp.mum.rsi_max": 30.0}}]}
    names = [c["name"] for c in ej.candidate_pool(q)]
    assert "xp-enter_apr-0.3" not in names
    assert "mum-rsi-30" in names


def test_the_overlay_moves_the_instance_never_the_class(monkeypatch):
    s = _mum()
    cls = type(s)
    base_rsi, base_hold = cls.RSI_MAX, cls.MAX_HOLD_MIN
    monkeypatch.setattr(ft, "get_lever",
                        lambda name, default, **kw: 32.0 if name.endswith("rsi_max")
                        else (720.0 if name.endswith("max_hold_min") else default))
    moved = fam.apply_book_levers(s, "xp.mum.")
    assert moved == {"xp.mum.rsi_max": 32.0, "xp.mum.max_hold_min": 720.0}
    assert s.RSI_MAX == 32.0 and s.MAX_HOLD_MIN == 720
    assert cls.RSI_MAX == base_rsi and cls.MAX_HOLD_MIN == base_hold
    assert fam.mum_bars(s) == {"rsi_max": 32.0, "max_hold_min": 720.0}
    # expiry reverts CLEANLY from the class defaults, never from mutated state
    monkeypatch.setattr(ft, "get_lever", lambda name, default, **kw: default)
    assert fam.apply_book_levers(s, "xp.mum.") == {}
    assert s.RSI_MAX == base_rsi and s.MAX_HOLD_MIN == base_hold


def test_a_carrier_without_the_knobs_is_a_no_op():
    avo = next(s for s in fam.STRATEGIES if s.bot == "freqtrade-avo-maria")
    assert fam.apply_book_levers(avo, "xp.avo.") == {}
    assert fam.mum_bars(avo) == {}


def test_an_open_position_keeps_the_cap_it_was_stamped_with():
    s = _mum()
    assert s.custom_exit("oversold-rebound", 800, 0.0, cap=720.0) == "max_hold"
    assert s.custom_exit("oversold-rebound", 800, 0.0, cap=1440.0) is None
    assert s.custom_exit("oversold-rebound", 1441, 0.0) == "max_hold"


def test_both_hosts_stamp_the_receipt_and_the_recorded_rsi():
    fam_src = Path(ROOT, "lighter_family_bot.py").read_text()
    live_src = Path(ROOT, "lighter_avo_live_bot.py").read_text()
    for src in (fam_src, live_src):
        assert '"bars": ' in src and '"rsi_entry"' in src
        assert 'cap=_cap' in src, "the exit must honour the entry-stamped cap"
    assert "_fam_mum_bars(S)" in live_src and "_fam_apply_book_levers(S" in live_src


def test_the_receipt_gate_accepts_the_stamp_the_hosts_write():
    row = {"extra": {"bars": {"rsi_max": 32.0, "max_hold_min": 1440.0}}}
    assert ej.ran_candidate(row, {"xp.mum.rsi_max": 32.0}) is True
    assert ej.ran_candidate(row, {"xp.mum.rsi_max": 30.0}) is False
    assert ej.ran_candidate({"extra": {}}, {"xp.mum.rsi_max": 32.0}) is False


def test_the_shortfall_organ_and_the_judge_name_the_same_twin():
    import implementation_shortfall as ish
    assert ish.XPJ_SHADOW_BOT == ish.SHADOW == ej.SHADOW_BOT


def test_the_family_image_ships_the_lever_surface():
    dockerfile = Path(ROOT, "Dockerfile.familyshadow").read_text()
    assert "fleet_tuning.py" in dockerfile
