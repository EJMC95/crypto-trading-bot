"""[19-Aug (qh)] 🧮 HULL'S ADVERSE-BASIS VETO MUST BE FALSIFIABLE FROM ITS ROW.

The 10bps veto fired 0 times in its first 21d, and that zero was unreadable:
retained premium history keeps only the scout's top-8 outliers (cutoff median
17.9bps > the veto), so band-coin premiums were visible in 1 of 5,580
candidate coin-snapshots. "0 fires" was byte-identical between a slack bar
and blind history — the (ly) falsifiable-census principle applied to a gate.

Pinned:
  1. scan_census(prem_out=...) records the premium of every IN-BAND,
     class-admissible coin — and nothing else (out-of-band, non-crypto and
     held coins stay out);
  2. the census BUCKETS are untouched by the tap (exact dict + partition —
     the selftest's own pins, re-asserted here with prem_out active);
  3. build_extra publishes basis.{band_prems, coverage, veto_fires} with all
     three keys ALWAYS present ((qg): a key that appears only when it fires
     is the ambiguity this removes);
  4. build_state round-trips veto_fires so a restart cannot zero the record.
"""
import pytest

import lighter_book_hull_bot as hull

pytestmark = pytest.mark.autonomy

T0 = 1_785_600_000.0
H = hull.H


def _f(apr, vol):
    return {"rate": apr / H, "vol": vol}


def _fixture():
    """One coin per band outcome, premiums on all."""
    lo, hi = hull.APR_LO_EFF, hull.APR_HI
    mid = (lo + hi) / 2.0
    fund = {
        "INBAND":  _f(mid, 5_000_000),          # in band, liquid
        "INTHIN":  _f(mid, 100_000),            # in band, thin — still tapped
        "BELOW":   _f(lo * 0.5, 5_000_000),     # below band — NOT tapped
        "ABOVE":   _f(hi * 2.0, 5_000_000),     # above band — NOT tapped
        "NOCLASS": _f(mid, 5_000_000),          # in band, class-refused
        "HELDCOIN": _f(mid, 5_000_000),         # held — not scanned for entry
    }
    prem = {c: 3.0 for c in fund}
    # an AGED stability clock, or every in-band coin parks in `waiting`
    # before the class gate is ever reached (the gate ORDER working)
    aged = {c: T0 - (hull.STABLE_H + 1) * 3600 for c in fund}
    return fund, prem, aged


def test_prem_out_records_exactly_the_inband_admissible_coins():
    fund, prem, aged = _fixture()
    tap = {}
    cen = hull.scan_census(fund, {"HELDCOIN"}, aged, T0, prem_map=prem,
                           class_ok=lambda c: c != "NOCLASS", prem_out=tap)
    assert set(tap) == {"INBAND", "INTHIN"}, tap
    assert tap["INBAND"] == 3.0
    # the buckets are untouched by the tap
    assert sum(v for k, v in cen.items() if k != "scanned") == cen["scanned"]
    assert cen["held"] == 1 and cen["noncrypto"] == 1


def test_prem_out_none_and_missing_prems_are_safe():
    fund, _, aged = _fixture()
    cen = hull.scan_census(fund, set(), aged, T0, prem_map=None, prem_out=None)
    assert cen["scanned"] == len(fund)
    tap = {}
    hull.scan_census(fund, set(), aged, T0, prem_map={}, prem_out=tap)
    assert tap == {}, "no premiums fetched -> nothing recorded, no error"


def test_build_extra_basis_keys_always_present():
    ex = hull.build_extra({"scanned": 0}, {}, 0.0, 0.0)
    b = ex["basis"]
    assert b == {"band_prems": {}, "coverage": 0, "veto_fires": 0}, \
        "all three keys must exist even when everything is empty"
    ex2 = hull.build_extra({"scanned": 0}, {}, 0.0, 0.0,
                           band_prems={"A": -12.5}, veto_fires=7,
                           prem_coverage=225)
    assert ex2["basis"] == {"band_prems": {"A": -12.5}, "coverage": 225,
                            "veto_fires": 7}


def test_build_state_roundtrips_veto_fires():
    blob = hull.build_state({}, {}, {}, T0, now=T0, veto_fires=13)
    assert blob["veto_fires"] == 13
    assert hull.build_state({}, {}, {}, T0, now=T0)["veto_fires"] == 0, \
        "default stays 0 — absent is never a crash"
