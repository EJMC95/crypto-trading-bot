"""[19-Aug (qk)] 🌾 CARRY'S PERP FEE IS VENUE-SCOPED — AND THE FIX IS SMALLER
THAN IT LOOKS, WHICH IS THE POINT.

`PERP_FEE = 0.00045` is a HYPERLIQUID taker fee. The HL arm was retired 17-Jul
(LIGHTER-ONLY); the only arm that runs is `lighter_shadow`, where the venue's
fee is measured ZERO. Same stale-foreign-venue shape as the brain's Kraken-SPOT
`FEE_RT` in (gg).

WHAT THIS TEST EXISTS TO STOP, in priority order:

  1. **The overstated version of this fix.** A session nearly shipped "the 29bps
     round trip is phantom, cut it and carry turns positive". Measured on the
     era sample from its OWN recorded fees/notional: the real charge is a
     **median 22.2bps**, because on `lighter_shadow` the perp leg is ALREADY
     measured per fill by an order-book walk — PERP_FEE is only the FALLBACK.
     So this constant is not what the book charges, and correcting it does not
     move the ledger. Carry stays a loser (-0.155%/trade, t=-4.48).
  2. **HEDGE_COST must not drift with it.** Kiyosaki's header says that leg "is
     modelled, it does not exist", and these books omit any PRICE term for the
     same reason — the hypothetical hedge is what cancels price. Charging its
     cost and omitting price risk are two halves of ONE simulation; deleting
     the cost alone models a FREE hedge, better than reality in both
     directions. That is how a losing book gets laundered into a winner.
  3. The HL arm keeps its own correct fee — a global overwrite would invert the
     bug onto the honest arm (the `_basis` lesson in this same file).
"""
import pytest

import funding_carry_bot as carry

pytestmark = pytest.mark.autonomy


def test_each_arm_gets_its_own_venues_fee():
    assert carry.perp_fee("hl_paper") == carry.PERP_FEE == 0.00045, \
        "the Hyperliquid arm must keep the Hyperliquid taker fee"
    assert carry.perp_fee("lighter_shadow") == carry.PERP_FEE_LIGHTER, \
        "the Lighter arm must not be charged a Hyperliquid fee"
    assert carry.perp_fee("lighter_shadow") < carry.perp_fee("hl_paper"), \
        "Lighter's fee is measured ZERO; only slippage remains"


def test_the_lighter_arms_modelled_round_trip_matches_what_it_actually_charged():
    """The measured era median is 22.2bps (n=10, its own fees/notional). The
    modelled RT must land in that neighbourhood — not at the 29bps the old
    constants implied, and not near zero either."""
    rt_bps = 2 * carry.open_cost("lighter_shadow") * 1e4
    assert 18.0 <= rt_bps <= 26.0, (
        f"modelled RT {rt_bps:.1f}bps is outside the measured band "
        "[20.7, 49.7] median 22.2 — re-measure before moving this")
    assert 2 * carry.open_cost("hl_paper") * 1e4 == pytest.approx(29.0, abs=0.1)


def test_hedge_cost_is_untouched_and_dominates():
    """The fix corrects the perp leg ONLY. HEDGE_COST is a declared modelling
    assumption whose removal would be incoherent with the missing price term —
    a change to it is a POLICY decision, never a fee correction."""
    assert carry.HEDGE_COST == 0.0010, \
        "HEDGE_COST moved — that is not a fee fix, it is a re-spec of the book"
    # the hedge is the great majority of the Lighter arm's modelled friction
    assert carry.HEDGE_COST / carry.open_cost("lighter_shadow") > 0.9


def test_the_price_term_stays_absent_so_the_simulation_stays_coherent():
    """Carry realises P&L as EXACTLY `accrued - fees`, with no mark — BECAUSE
    the hypothetical hedge cancels price. (Unlike hull/kiyosaki this file has
    no `position_pnl` helper; the expression is inline, so pin the
    expression.) If a price term is ever added, HEDGE_COST must be revisited
    in the SAME change — the two are one assumption, and a book that both
    charges for a hedge and eats price movement is charged twice."""
    import ast
    import pathlib as _p
    tree = ast.parse(_p.Path(carry.__file__).read_text(encoding="utf-8"))
    realisations = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp)
                and isinstance(node.value.op, ast.Sub)):
            continue
        src = ast.unparse(node.value)
        if "accrued" in src:
            realisations.append((node.lineno, src))
    assert realisations, "no `accrued - ...` realisation found — scan is broken"
    for lineno, src in realisations:
        assert "mark" not in src and "price" not in src and "rate" not in src, (
            f"line {lineno}: carry's P&L gained a price term ({src!r}). The "
            "hedge assumption (HEDGE_COST + no price risk) must be re-derived "
            "in the same change.")
