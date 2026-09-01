#!/usr/bin/env python3
"""[2026-09-01 (vy)] THE MMF-AWARE CLIP — option D of the (vx) sizing card.

The (vx) measurement behind it: 👩 mum's stop-death ceiling collapsed to 4.17x
because her widened universe admits 20%-mmf coins at FULL clip — while 63% of
her P&L sits in ≤6%-mmf coins and the 12% tier is net negative. The factor
scales a coin's entry by (|stop|+REF)/(|stop|+mmf) exactly when the configured
gross exceeds that coin's own stop-alive ceiling, so the basket's ceiling pins
at the REF tier instead of the worst held coin's.

What these tests pin, each the target of a named mutation:
  * the scale NEVER exceeds 1.0 (drop the min -> a 1%-mmf coin would be sized
    2x — a restrict-only rule silently becoming leverage);
  * a coin at-or-under its own ceiling is UNTOUCHED, so a 1x book is
    byte-identical to the pre-(vy) sizing (the shadow-parity property);
  * the two absences stay DIFFERENT (bus contract vs (hs)/I6): a dark map is
    neutral, a coin missing from a populated map degrades to the worst tier;
  * the k-alias resolves (kBONK -> 1000BONK) — measured: both k-coins mum
    traded were invisible to every mmf lookup, worst_mmf included;
  * the kill switch restores the exact pre-(vy) behaviour;
  * BOTH stake sites carry the factor — the brain-expand refusal path
    recomputes stake from scratch and was the one path that would silently
    drop the protection.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
os.environ.setdefault("AVO_VENUE", "lighter_live")

import lighter_avo_live_bot as A  # noqa: E402

ROWS = {
    "MAJOR": {"mmf_bps": 600.0},     # the REF tier
    "MID":   {"mmf_bps": 1200.0},
    "MEME":  {"mmf_bps": 2000.0},
    "TIGHT": {"mmf_bps": 100.0},
    "1000BONK": {"mmf_bps": 2000.0},
}


def _factor(sym, rows=ROWS, gross=10.0, stop=0.04):
    f, _m = A.mmf_clip_factor(sym, rows, gross=gross, stop=stop)
    return f


def test_a_high_margin_coin_is_scaled_to_the_ref_budget():
    # mum's shape: stop 4%, gross 10, 20%-mmf coin -> (0.04+0.06)/(0.04+0.20)
    assert abs(_factor("MEME") - 0.10 / 0.24) < 1e-9
    # the 12% tier: (0.10)/(0.16)
    assert abs(_factor("MID") - 0.10 / 0.16) < 1e-9


def test_a_coin_whose_own_ceiling_clears_the_gross_is_untouched():
    # 3%..6% coins at gross 10 with a 4% stop: MAJOR's ceiling is exactly
    # 10.0 (engaged, factor 1.0 by the ratio); TIGHT's is 20 (exempt).
    assert _factor("MAJOR") == 1.0
    assert _factor("TIGHT") == 1.0
    # and at a LOWER gross even the meme tier is exempt — the shadow-parity
    # property: a 1x (or 4x) book is byte-identical to pre-(vy) sizing.
    assert _factor("MEME", gross=4.0) == 1.0
    assert _factor("MEME", gross=1.0) == 1.0


def test_the_tie_reads_engaged_like_stop_reachable_reads_dead():
    # at gross exactly == the coin's ceiling the stop and liquidation are the
    # same price; the protective reading is ENGAGED (mirror of the (sy) tie).
    g = 1.0 / (0.04 + 0.20)
    assert abs(_factor("MEME", gross=g) - 0.10 / 0.24) < 1e-9


def test_the_scale_never_exceeds_one():
    # a 1%-mmf coin's raw ratio is (0.10)/(0.05) = 2.0 — the cap must hold,
    # or a restrict-only rule silently becomes leverage.
    assert _factor("TIGHT", gross=25.0) == 1.0


def test_a_dark_map_is_neutral_and_a_missing_coin_is_conservative():
    # dark/empty map = organ outage -> NEUTRAL (no outage may resize a book)
    f, m = A.mmf_clip_factor("MEME", {}, gross=10.0, stop=0.04)
    assert f == 1.0 and m is None
    f, m = A.mmf_clip_factor("MEME", None, gross=10.0, stop=0.04)
    assert f == 1.0 and m is None
    # a coin MISSING from a POPULATED map = real absence -> worst tier
    f, m = A.mmf_clip_factor("GHOSTCOIN", ROWS, gross=10.0, stop=0.04)
    assert abs(f - 0.10 / (0.04 + A.MMF_CLIP_UNKNOWN)) < 1e-9
    assert m is None


def test_the_k_alias_resolves(monkeypatch):
    assert A.mmf_alias("kBONK") == "1000BONK"
    assert A.mmf_alias("kPEPE") == "1000PEPE"
    assert A.mmf_alias("KAITO") is None        # a real name starting with K
    assert A.mmf_alias("kiwi") is None         # lowercase after k = not the notation
    assert A.coin_mmf("kBONK", ROWS) == 0.20
    assert abs(_factor("kBONK") - 0.10 / 0.24) < 1e-9
    # and worst_mmf sees it too — the lookup that was silently blind
    import fleet_bus
    monkeypatch.setattr(fleet_bus, "market_margins", lambda *a, **k: ROWS)
    assert A.worst_mmf(["MAJOR", "kBONK"]) == 0.20
    assert A.worst_mmf(["MAJOR"]) == 0.06


def test_the_kill_switch_restores_pre_vy_sizing(monkeypatch):
    monkeypatch.setattr(A, "MMF_CLIP_SCALE", False)
    f, m = A.mmf_clip_factor("MEME", ROWS, gross=10.0, stop=0.04)
    assert f == 1.0
    assert m == 0.20, "the switch kills the SCALE, never the telemetry"


def test_both_stake_sites_carry_the_factor():
    """Source pin: the primary stake line AND the brain-expand refusal reset
    both multiply by the factor, and the open-site meta stamps it. The reset
    is the named hazard — it rebuilds stake from scratch."""
    src = open(os.path.join(os.path.dirname(A.__file__),
                            "lighter_avo_live_bot.py"), encoding="utf-8").read()
    assert len(re.findall(
        r"clip \* S\.stake_mult\(tag, bars\) \* _mf", src)) >= 2, (
        "both the entry stake and the expand-refusal reset must carry _mf")
    assert '"mmf_factor": round(_mf, 4)' in src, (
        "the open-site meta must stamp the factor so the close row can split "
        "the ledger by tier at day-30")
    assert '"mmf_factor": m.get("mmf_factor")' in src, (
        "the close row must copy the open-site stamp")
