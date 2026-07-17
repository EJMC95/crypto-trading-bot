#!/usr/bin/env python3
"""
funding_basis.py — the fleet's single authority on funding-rate BASIS per venue.

WHY THIS EXISTS (2026-07-17)
  A venue's quoted funding `rate` is a fraction per FUNDING PERIOD — and the
  period length differs by venue. Annualising with the wrong period is a silent
  multiplicative error that no test catches, because every number stays
  self-consistent and merely wrong by a constant.

  It happened. Lighter's /funding-rates `rate` is a fraction per **8 HOURS**,
  and every Lighter consumer annualised it as HOURLY (`rate * 24 * 365`) —
  8x TRUE, fleet-wide, for as long as the Lighter fleet has existed. VERIFIED
  17-Jul against the SETTLED series /api/v1/fundings (whose `rate` is %/hr):
    ETH  predicted 9.6e-05 -> published 84.1% apr, settled 10.51%, ratio 8.00
    DOGE, SPY likewise exactly 8.00 (SPY floor: published 28.0%, settled 3.50%)
    and the arithmetic closes: 9.6e-05 * 3 * 365 * 100 = 10.512.
  (Lighter SETTLES hourly, at rate/8 per hour — the quote is the 8h convention.
  Both facts hold; `rate * 3 * 365` is correct either way.)

  The cost was NOT cosmetic. `FUNDING_ENTER_APR = 0.40` was born in
  funding_carry_bot.py against HYPERLIQUID data — where funding IS hourly, so
  24*365 is CORRECT and 0.40 meant a true 40% APR. It was then ported to
  lighter_funding_bot.py as a bare constant. **The port is the bug**: the LIVE
  book has been admitting at ~5% TRUE apr ever since, on a bar no backtest ever
  supported.

DO NOT "FIX" THIS WITH A GLOBAL REPLACE OF `24 * 365`.
  The fleet knows both conventions and gets them RIGHT everywhere except
  Lighter — the one venue holding real money. These sites are CORRECT and must
  not be touched: funding_carry_bot.py + market_context.py (Hyperliquid,
  hourly), market_pulse.py (Binance, already rate_8h * 3 * 365), and every
  scripts/backtest_*.py (Hyperliquid). A blanket replace breaks four working
  things to fix one broken one.

THE CONTRACT
  A quoted `rate` is a fraction per period. APR = rate * periods_per_year(venue).
  Ask this module; never hardcode 24*365 against a venue again.
"""

# periods per DAY of the venue's QUOTED funding rate.
#   lighter     : /funding-rates `rate` is per 8h  -> 3/day   (VERIFIED 17-Jul)
#   hyperliquid : `funding` is per 1h              -> 24/day
#   binance     : `lastFundingRate` is per 8h      -> 3/day
#   bybit       : per 8h                           -> 3/day
_PERIODS_PER_DAY = {
    "lighter": 3.0,
    "hyperliquid": 24.0,
    "binance": 3.0,
    "bybit": 3.0,
}

# The factor a Lighter APR computed the OLD way (rate*24*365) is too high by.
# Kept as a named constant so the one-time re-denomination of every
# Lighter-apr-denominated threshold reads as arithmetic instead of magic:
#   24/3 == 8. A threshold in old units / LIGHTER_LEGACY_APR_FACTOR == same
#   decision under the corrected conversion. See the 17-Jul (f) CHANGELOG entry.
LIGHTER_LEGACY_APR_FACTOR = 8.0

DEFAULT_VENUE = "lighter"


def periods_per_day(venue: str = DEFAULT_VENUE) -> float:
    """Funding periods per day for `venue`. Raises on an unknown venue — a
    typo must never silently fall back to a convention that is wrong by 8x."""
    v = (venue or "").strip().lower()
    # tolerate the fleet's venue-mode spellings (lighter_live / lighter_shadow)
    if v.startswith("lighter"):
        v = "lighter"
    if v not in _PERIODS_PER_DAY:
        raise KeyError(
            f"funding_basis: unknown venue {venue!r} — add its funding period "
            f"to _PERIODS_PER_DAY rather than guessing. Known: "
            f"{sorted(_PERIODS_PER_DAY)}")
    return _PERIODS_PER_DAY[v]


def periods_per_year(venue: str = DEFAULT_VENUE) -> float:
    """The `H` every bot wants: rate * periods_per_year(venue) == APR (fraction).
    Lighter = 1095.0 (3*365). Hyperliquid = 8760.0 (24*365)."""
    return periods_per_day(venue) * 365.0


def to_apr(rate, venue: str = DEFAULT_VENUE):
    """Quoted rate -> APR as a FRACTION (0.10 == 10%/yr). None-safe."""
    if rate is None:
        return None
    return float(rate) * periods_per_year(venue)


def to_apr_pct(rate, venue: str = DEFAULT_VENUE):
    """Quoted rate -> APR in PERCENT (10.5 == 10.5%/yr). None-safe."""
    apr = to_apr(rate, venue)
    return None if apr is None else apr * 100.0


def to_hourly(rate, venue: str = DEFAULT_VENUE):
    """Quoted rate -> the fraction accrued per HOUR. None-safe.

    This is the other half of the same bug, and the easier one to miss. Every
    bot that models its own carry does:
        accrued -= rate * notional * dt_h
    which is only right when the quote IS hourly. On Lighter the quote is per
    8h, so that over-accrues by 8x. Lighter SETTLES hourly at rate/8 per hour —
    which is exactly what this returns (3/24 == 1/8).

    Live books are charged by the VENUE, so their equity is honest either way;
    but a modelled accrual still reaches the per-trade LEDGER and the win/loss
    classification, so an 8x-inflated funding credit inflates the win rate of
    any book that collects carry. Shadow books have it in their equity too.
    """
    if rate is None:
        return None
    # [2026-07-17] The divide is HOISTED deliberately: `rate * p / 24.0` parses
    # as `(rate*p)/24.0` — two roundings, which differ from the one-rounding
    # form on ~17% of inputs by up to 1 ulp. Hoisted, the factor is an EXACT
    # binary value (1.0 for hyperliquid, 0.125 for lighter), so `rate*factor`
    # is exact identity / an exact /8. ~1e-16 is far below any threshold this
    # feeds, so this is a PROOF-STANDARD fix, not a money fix: it is what lets
    # a per-venue basis change be proven BIT-IDENTICAL on the untouched arm,
    # which is the 31ec660 bar.
    return float(rate) * (periods_per_day(venue) / 24.0)


def _selftest():
    # the verified Lighter anchor: ETH 9.6e-05 per 8h -> 10.51% true APR
    assert abs(to_apr_pct(9.6e-05, "lighter") - 10.512) < 0.01, to_apr_pct(9.6e-05, "lighter")
    # SPY's floor band: published 28.0% the old way -> 3.50% true
    spy_rate = 28.0 / (24 * 365 * 100)
    assert abs(to_apr_pct(spy_rate, "lighter") - 3.50) < 0.01, to_apr_pct(spy_rate, "lighter")
    # the legacy factor IS the ratio of the two conventions
    assert abs(24.0 / periods_per_day("lighter") - LIGHTER_LEGACY_APR_FACTOR) < 1e-9
    # HL is hourly and must be LEFT ALONE at 24*365
    assert periods_per_year("hyperliquid") == 24 * 365
    assert periods_per_year("binance") == 3 * 365
    # venue-mode spellings resolve
    assert periods_per_year("lighter_live") == periods_per_year("lighter_shadow") == 3 * 365
    # an unknown venue must RAISE, never default (a silent default is the bug)
    try:
        periods_per_day("kraken")
        raise AssertionError("unknown venue must raise, not default")
    except KeyError:
        pass
    # None-safe
    assert to_apr(None) is None and to_apr_pct(None) is None
    print("funding_basis self-tests passed "
          "(lighter=3/day VERIFIED vs settled, hyperliquid=24/day untouched).")


if __name__ == "__main__":
    _selftest()
