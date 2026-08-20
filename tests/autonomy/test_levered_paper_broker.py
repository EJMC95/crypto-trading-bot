"""[2026-08-20] A LEVERED BOOK ON THE 1x BROKER DOES NOT MIS-REPORT — IT BOOKS A
PROFIT THE VENUE WOULD NEVER HAVE LET IT COLLECT.

`PaperBroker` is "cash-settled perps, LEVERAGE 1": no margin requirement, no
maintenance level, no liquidation. Run a 3x book on it and a drawdown that would
have closed a real account out instead rides the position down, marks it back up,
and books the recovery. That is not imprecision — it makes ruin INVISIBLE, in the
one direction that matters, and it is why I22 admits leverage only as the output
of a vol target on a book whose ruin distance is modelled.

The margin surface these tests use is the venue's own, published since (se):
measured 20-Aug across 212 active books the maintenance tiers are
1.20% x7 · 2.40% x9 · 3.00% x25 · 6.00% x89 · 12% x40 · 20% x35 — so a single
assumed maintenance rate is wrong by up to 16x, which is exactly how a ruin table
concludes "the stop fires first" for a portfolio holding a market where it does
not.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from paper_broker import (  # noqa: E402
    UNKNOWN_MARGIN, LeveredPaperBroker, LiquidatedError, MarginSpec, PaperBroker,
)


def _b(**kw):
    """A 3x-capable account on BTC-like margin (5% initial / 3% maintenance)."""
    return LeveredPaperBroker(start_equity=1000.0, fee_bps=0.0,
                              margins={"BTC": MarginSpec(0.05, 0.03),
                                       "KAITO": MarginSpec(0.20, 0.12)}, **kw)


# --- 1 · the thing the base class gets WRONG, not merely imprecise ---------
def test_the_1x_broker_books_a_recovery_a_real_account_could_not_have_had():
    """The whole reason this class exists, stated as a comparison. Same trades,
    same prices; one account survives because it cannot be liquidated."""
    naive = PaperBroker(start_equity=1000.0, fee_bps=0.0)
    real = _b()
    # 3x long: $3,000 notional on $1,000 equity.
    for b in (naive, real):
        b.open("BTC", True, 30.0, 100.0)
    # −33% adverse move. Equity would be 1000 - 990 = $10 against a $30
    # maintenance requirement on the remaining $2,010 notional -> CLOSED OUT.
    for b in (naive, real):
        b.mark("BTC", 67.0)
    real.check()
    assert real.liquidated is True, "a real 3x account is gone here"
    # ...then the price recovers all the way.
    for b in (naive, real):
        b.mark("BTC", 100.0)
    naive_eq, real_eq = naive.equity(), real.equity()
    assert naive_eq == pytest.approx(1000.0), (
        "the 1x broker rides it down and marks it back to flat")
    assert real_eq < 100.0, (
        f"the levered account was closed out and cannot recover: {real_eq}")
    assert naive_eq - real_eq > 900.0, (
        "this gap IS the fiction a levered book on the 1x broker would publish")


# --- 2 · the maintenance requirement is PER MARKET -------------------------
def test_maintenance_is_summed_per_market_not_at_one_assumed_rate():
    """mmf ranges 1.2%-20% on this venue. A portfolio's requirement is the sum
    of each leg's own, and using one rate is wrong by up to 16x."""
    b = _b()
    b.open("BTC", True, 10.0, 100.0)      # $1,000 notional @ 3% -> $30
    b.open("KAITO", True, 100.0, 5.0)     # $500 notional  @ 12% -> $60
    assert b.gross_notional() == pytest.approx(1500.0)
    assert b.maintenance_requirement() == pytest.approx(90.0)
    # a single assumed 3% would have said 45 — half the truth
    assert b.maintenance_requirement() != pytest.approx(1500.0 * 0.03)


def test_distance_to_liquidation_is_not_one_over_L():
    """The correction this whole thread turned on. At 3x gross the naive answer
    is 33.3%; the truth subtracts the maintenance margin."""
    b = _b()
    b.open("BTC", True, 30.0, 100.0)      # $3,000 on $1,000 -> 3x
    assert b.cross_leverage() == pytest.approx(3.0, rel=1e-3)
    naive = 1.0 / 3.0
    true = b.distance_to_liquidation()
    assert true == pytest.approx((1000.0 - 90.0) / 3000.0, rel=1e-3)
    assert true < naive, "ignoring mmf OVERSTATES the safety margin"
    assert naive - true == pytest.approx(0.03, abs=1e-3), "the gap IS mmf"


def test_a_high_mmf_market_liquidates_where_a_low_one_survives():
    """KAITO (12%) vs BTC (3%) at the SAME leverage — the case that broke the
    'stop fires first at every level' claim.

    The thresholds are DERIVED, not guessed. With equity E0, gross G0 and an
    adverse fraction x: liquidation when `E0 - x*G0 <= G0*(1-x)*mmf`, i.e.
    `x >= (E0 - G0*mmf) / (G0*(1-mmf))`. At 3x that is **31.27% for BTC** and
    **24.24% for KAITO** — a 7pp spread from the margin tier alone. The first
    draft of this test asserted a split at -24% and failed, because -24%
    liquidates NEITHER; the arithmetic, not the guess, sets the fixture."""
    for coin, x_liq in (("BTC", 0.3127), ("KAITO", 0.2424)):
        just_inside = _b()
        just_inside.open(coin, True, 30.0, 100.0)          # 3x
        just_inside.mark(coin, 100.0 * (1 - (x_liq - 0.01)))
        assert just_inside.check() is False, (
            f"{coin} must SURVIVE 1pp inside its {x_liq:.2%} threshold")
        just_past = _b()
        just_past.open(coin, True, 30.0, 100.0)
        just_past.mark(coin, 100.0 * (1 - (x_liq + 0.01)))
        assert just_past.check() is True, (
            f"{coin} must LIQUIDATE 1pp past its {x_liq:.2%} threshold")
    # ...and the separation is the point: one move kills KAITO and not BTC.
    sep = 0.27
    btc, kaito = _b(), _b()
    btc.open("BTC", True, 30.0, 100.0); btc.mark("BTC", 100.0 * (1 - sep))
    kaito.open("KAITO", True, 30.0, 100.0); kaito.mark("KAITO", 100.0 * (1 - sep))
    assert btc.check() is False and kaito.check() is True, (
        "a -27% move is survivable at 3% maintenance and fatal at 12%")


# --- 3 · fail-closed on an unknown market ---------------------------------
def test_an_unknown_market_gets_the_HARSHEST_spec_not_a_generous_one():
    """(se)'s contract, carried into the broker: unknown margin must never be
    modelled as no margin. UNKNOWN_MARGIN is the venue's worst tier."""
    b = _b()
    assert b.spec("NEVER_HEARD_OF_IT") is UNKNOWN_MARGIN
    assert UNKNOWN_MARGIN.mmf == 0.12, "must be the harshest tier, not a mid one"
    b.open("NEVER_HEARD_OF_IT", True, 10.0, 100.0)
    assert b.maintenance_requirement() == pytest.approx(120.0), (
        "an unknown market must cost the HARSH requirement")


def test_set_margins_skips_junk_rather_than_half_reading_it():
    b = LeveredPaperBroker(start_equity=1000.0, fee_bps=0.0)
    b.set_margins({"BTC": {"imf_bps": 500, "mmf_bps": 300},
                   "BAD": {"imf_bps": None, "mmf_bps": 300},
                   "ZERO": {"imf_bps": 0, "mmf_bps": 0}})
    assert b.spec("BTC").mmf == pytest.approx(0.03)
    assert b.spec("BAD") is UNKNOWN_MARGIN, "a half-read row keeps the harsh default"
    assert b.spec("ZERO") is UNKNOWN_MARGIN, "imf=0 is junk, not infinite leverage"


def test_it_consumes_the_shape_fleet_bus_actually_publishes():
    """(hj): driven with the real accessor's output shape, not a hand fixture."""
    published = {"BTC": {"max_lev": 20.0, "imf_bps": 500.0, "mmf_bps": 300.0}}
    b = LeveredPaperBroker(start_equity=1000.0, fee_bps=0.0)
    b.set_margins(published)
    assert b.spec("BTC").imf == pytest.approx(0.05)
    assert b.spec("BTC").mmf == pytest.approx(0.03)


# --- 4 · liquidation is total, and it sticks ------------------------------
def test_liquidation_closes_EVERY_position_not_just_the_loser():
    b = _b()
    b.open("BTC", True, 30.0, 100.0)
    b.open("KAITO", True, 20.0, 5.0)
    b.mark("BTC", 65.0)
    assert b.check() is True
    assert b.open_count() == 0, "a venue closes the ACCOUNT, not one leg"
    assert b.liquidation_events and b.liquidation_events[0]["n"] == 2


def test_a_liquidated_account_cannot_trade_again_or_forget_across_a_restart():
    """A memory-only halt is one this fleet has already paid for."""
    b = _b()
    b.open("BTC", True, 30.0, 100.0)
    b.mark("BTC", 65.0)
    b.check()
    assert b.can_open("BTC", 1.0, 100.0) is False
    st = b.to_state()
    fresh = _b()
    assert fresh.restore_state(st) is True
    assert fresh.liquidated is True, "liquidation must survive a redeploy"
    assert fresh.can_open("BTC", 1.0, 100.0) is False


def test_check_is_quiet_when_flat_or_healthy_and_can_raise_when_asked():
    b = _b()
    assert b.check() is False, "a flat account is not liquidated"
    b.open("BTC", True, 5.0, 100.0)        # 0.5x — very healthy
    assert b.check() is False
    assert b.margin_ratio() > 10
    # A 0.5x long can NEVER be liquidated by a price fall: the position is
    # smaller than the equity backing it, so equity cannot reach the
    # requirement. Verified rather than assumed — the first draft asserted a
    # raise here and correctly did not get one.
    b.mark("BTC", 1.0)
    assert b.check() is False, "sub-1x cannot liquidate on a fall"
    # To exercise the raise, LEVER it.
    lev = _b()
    lev.open("BTC", True, 30.0, 100.0)     # 3x
    lev.mark("BTC", 60.0)                  # -40%, past the 31.27% threshold
    with pytest.raises(LiquidatedError):
        lev.check(raise_on_liquidation=True)


def test_can_open_respects_the_INITIAL_margin_of_the_whole_book():
    b = _b()
    assert b.can_open("BTC", 100.0, 100.0) is True     # $10k @5% = $500 <= 1000
    b.open("BTC", True, 100.0, 100.0)
    assert b.can_open("KAITO", 1000.0, 5.0) is False, (
        "$5k @20% = $1,000 more initial margin on top of $500 already used")


def test_risk_extra_publishes_the_numbers_a_reader_would_otherwise_re_derive():
    b = _b()
    b.open("BTC", True, 30.0, 100.0)
    x = b.risk_extra()
    assert x["gross_x"] == pytest.approx(3.0, rel=1e-3)
    assert x["dist_to_liq_frac"] == pytest.approx(0.3033, abs=1e-3)
    assert x["liquidated"] is False
    flat = _b().risk_extra()
    assert flat["dist_to_liq_frac"] is None, "flat is None, never a fake 0 or 1"
