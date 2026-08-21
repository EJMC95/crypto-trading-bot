#!/usr/bin/env python3
"""[2026-08-21 (sr)] 🙏 AVO SPREADS ITS BASKET — the scan order, and the N_eff it earns.

**Eamon: "diversify and addition is great" / "i want this bot to find a way so
leverage can be used".** With the book at 5x, the leverage is not the risk — the
BASKET it is applied to is. Measured on Lighter's own 200d daily tape, the book
held QQQ/SPY/NVDA: **N_eff 1.18, rho +0.775 — three names and ONE BET.**

WHY IT CONCENTRATED, structurally rather than by luck: the entry loop scanned
`list(COINS) + list(NONCRYPTO_UNIVERSE)` IN LIST ORDER and took the first
qualifying signal, so 29 crypto names got first refusal on every slot and the
diversifiers were last in line by construction. That is the (hl) finding on
📊 Index Rider — *"the entry loop iterates SYMBOLS in order with incumbents
holding slots, it would starve the LAST-listed diversifiers and RAISE
correlation"* — reaching a second book.

Re-ordering the scan puts **WTI ahead of BTC**, and that single position takes
the basket to **N_eff 2.87 (rho +0.132)** — 2.4x the effective diversification,
at ZERO expectancy cost, because it changes WHICH qualifying signal fills a slot
and never whether one is taken.

THE ENTRY PATH IS UNTOUCHED. Only the sequence changes, which is why these tests
pin both halves: the reorder happens, AND every gate still stands between a
candidate and a real order.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
os.environ.setdefault("AVO_VENUE", "lighter_live")

import lighter_avo_live_bot as A  # noqa: E402


def _synth(series):
    """{sym: {t: ret}} from {sym: [closes]}, on one shared timeline."""
    return {sym: A._bar_returns({"t": list(range(len(cs))), "c": cs})
            for sym, cs in series.items()}


def _walk(n, step, jitter=0.0, seed=1):
    """Deterministic price path. `step` is the shared factor; `jitter` adds an
    idiosyncratic component, so same-step/no-jitter names are ~perfectly
    correlated and reversed-step names offset."""
    px, out, s = 100.0, [100.0], seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        px *= (1.0 + step[i % len(step)] + ((s / 2147483648.0) - 0.5) * jitter)
        out.append(px)
    return out


UP = [0.01, -0.008, 0.012, -0.006, 0.009, -0.011]


# --------------------------------------------------------------- correlation
def test_a_short_overlap_reports_none_never_zero():
    """THE ONE ERROR THAT WOULD BUY LEVERAGE. An unmeasurable pair must be None.
    Returning 0.0 reads as 'perfectly diversifying' — it would both jump that
    name to the front of the queue AND inflate N_eff, crediting independence
    nobody measured. Unknown degrades to unknown (I8)."""
    short = {i: 0.01 for i in range(5)}
    assert A._pair_corr(short, dict(short)) is None


def test_a_flat_leg_reports_none_not_a_correlation():
    flat = {i: 0.0 for i in range(80)}
    moving = {i: (0.01 if i % 2 else -0.01) for i in range(80)}
    assert A._pair_corr(flat, moving) is None


def test_correlation_recovers_the_obvious_cases():
    r = _synth({"A": _walk(160, UP), "B": _walk(160, UP),
                "C": _walk(160, [-x for x in UP])})
    assert A._pair_corr(r["A"], r["B"]) > 0.95, "identical paths ~ +1"
    assert A._pair_corr(r["A"], r["C"]) < -0.5, "mirrored paths negative"


def test_bar_returns_refuses_a_series_too_short_to_measure():
    assert A._bar_returns({"t": [1, 2], "c": [10.0, 11.0]}) == {}
    assert A._bar_returns(None) == {}
    assert A._bar_returns({"t": [1, 2, 3], "c": [1.0, 2.0]}) == {}, \
        "mismatched lengths are unusable, not silently zipped"


# ------------------------------------------------------------------- n_eff
def test_n_eff_separates_one_bet_from_a_spread_basket():
    same = _synth({k: _walk(160, UP, 0.002, i)
                   for i, k in enumerate(("A", "B", "C"), 1)})
    ne_same, rho_same = A.basket_n_eff(same, ["A", "B", "C"])
    spread = _synth({"A": _walk(160, UP, 0.05, 7),
                     "B": _walk(160, UP[::-1], 0.05, 99),
                     "C": _walk(160, [-x for x in UP], 0.05, 4242)})
    ne_spread, rho_spread = A.basket_n_eff(spread, ["A", "B", "C"])
    assert ne_same < 1.5, f"identical paths must read ~one bet, got {ne_same}"
    assert rho_same > 0.9
    assert ne_spread > ne_same, "a spread basket must read MORE independent"
    assert rho_spread < rho_same


def test_n_eff_reports_none_when_nothing_is_measurable():
    """A dark read must never be credited as independence."""
    assert A.basket_n_eff({}, ["A", "B"]) == (None, None)
    assert A.basket_n_eff({"A": {}, "B": {}}, ["A", "B"]) == (None, None)


def test_the_vol_target_follows_the_measured_basket():
    """N_eff 1.18 (what it held) and 2.87 (after the diversifier) must map to
    materially different supported gross — that gap is the whole point."""
    assert A.vol_target_gross_x(1.18) < A.vol_target_gross_x(2.87)
    assert A.vol_target_gross_x(1.18) == pytest.approx(1.6289, abs=1e-3)
    assert A.vol_target_gross_x(2.87) == pytest.approx(2.5408, abs=1e-3)


# ------------------------------------------------------------- scan ordering
def test_the_most_diversifying_candidate_is_offered_first():
    """The behavioural claim: holding two correlated names, the offsetting
    candidate must be offered ahead of a third correlated one — even though
    list order puts the correlated one first."""
    r = _synth({"HELD1": _walk(160, UP, 0.002, 1),
                "HELD2": _walk(160, UP, 0.002, 2),
                "SAME": _walk(160, UP, 0.002, 3),
                "DIVERSE": _walk(160, [-x for x in UP], 0.002, 4)})
    order = A.diversified_order(["SAME", "DIVERSE"], ["HELD1", "HELD2"], r)
    assert order[0] == "DIVERSE", f"diversifier must lead, got {order}"


def test_unmeasurable_candidates_sort_after_measured_ones_in_original_order():
    r = _synth({"HELD": _walk(160, UP, 0.002, 1),
                "MEASURED": _walk(160, [-x for x in UP], 0.002, 2)})
    r["DARK_A"], r["DARK_B"] = {}, {}
    order = A.diversified_order(["DARK_A", "DARK_B", "MEASURED"], ["HELD"], r)
    assert order[0] == "MEASURED", "a name we cannot measure must not lead"
    assert order.index("DARK_A") < order.index("DARK_B"), \
        "unmeasured names keep their declared relative order"


def test_the_reorder_is_a_permutation_and_loses_nothing():
    """Diversification re-RANKS; it must never drop a candidate. Losing a name
    here would be an entry filter wearing an ordering costume."""
    r = _synth({"HELD": _walk(160, UP, 0.002, 1),
                "A": _walk(160, UP, 0.002, 2),
                "B": _walk(160, [-x for x in UP], 0.002, 3)})
    uni = ["A", "B", "DARK"]
    assert sorted(A.diversified_order(uni, ["HELD"], r)) == sorted(uni)


@pytest.mark.parametrize("held,rets", [
    (["QQQ"], {}),                 # dark returns
    ([], {"BTC": {1: 0.1}}),       # empty book, nothing to diversify against
    (None, None),                  # junk
    (["NOT_HELD_ANYWHERE"], {}),   # held name with no series
])
def test_ordering_falls_back_to_todays_behaviour_exactly(held, rets):
    """FAIL-SAFE IS THE CONTRACT: unmeasurable => the list UNCHANGED, i.e.
    byte-identical to the behaviour before this shipped. An enhancement is
    never a dependency, and no organ outage may re-rank a real-money book."""
    uni = ["BTC", "ETH", "SPY", "WTI"]
    assert A.diversified_order(uni, held, rets) == uni


# ------------------------------------------------------------------ wiring
def test_the_row_publishes_the_baskets_measured_independence():
    """n_eff on the row is what makes 'the slots are one bet' VISIBLE rather
    than inferable — five held names and one held bet look identical without
    it, which is how the book sat at N_eff 1.18 with nobody asking."""
    src = open(A.__file__).read()
    for f in ('"n_eff":', '"basket_rho":', '"vol_target_here":'):
        assert f in src, f"the leverage block must publish {f}"
    assert "held_n_eff = held_rho = None" in src, \
        "must default to None — 'not measured yet' is not 'one bet'"


def test_the_scan_is_reordered_and_every_entry_gate_survives():
    """The ONLY behavioural change is sequence. Pin that the loop iterates the
    reordered list, AND that every gate still stands between a candidate and a
    real order — an ordering change must not become an entry change."""
    src = open(A.__file__).read()
    assert "for sym in diversified_order(universe, list(pos), _rets):" in src, \
        "the entry scan must iterate the diversified order"
    for gate in ("noncrypto_entry_blocked(sym, r_up)", "if fleet_long_veto:",
                 "symcap_blocked(", "brain_entry_gated(", "rails.notional_ok(",
                 "if stake < MIN_CLIP_USD:", "coin_vetoed"):
        assert gate in src, f"entry gate went missing: {gate}"
