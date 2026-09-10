"""Liquidation estimation and the stop-before-liquidation rule.

THE POINT OF THIS MODULE, in one sentence: at 10x a 10% adverse move is the
whole position, so a stop that sits BEYOND liquidation is not a stop -- the
exchange closes the trade first and the risk number the sizing was built on
was never real.

ISOLATED margin has a closed form and it is derived here rather than quoted:

    long:   margin + (P - E)q = mmf * P * q ,  margin = E*q/L
            =>  P_liq = E * (1 - 1/L) / (1 - mmf)
    short:  margin + (E - P)q = mmf * P * q
            =>  P_liq = E * (1 + 1/L) / (1 + mmf)

CROSS margin has NO per-position answer -- liquidation there is a property of
the whole account, so `estimate` REFUSES (returns None with a reason) unless
the caller supplies account equity and total maintenance requirement. Refusing
is the safe output; a plausible-looking cross-margin number computed from
position fields alone would be confidently wrong.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LiquidationEstimate:
    price: float | None
    reason: str
    margin_mode: str
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    distance_frac: float | None = None      # |liq - entry| / entry
    reliable: bool = False
    detail: dict[str, Any] = None            # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.detail is None:
            self.detail = {}


def isolated_liquidation(entry: float, leverage: float, mmf: float,
                         side: str, fee_buffer_frac: float = 0.0
                         ) -> float | None:
    """Closed form above. `fee_buffer_frac` moves liquidation CLOSER to entry
    to account for fees and accrued funding eating the margin -- always in the
    conservative direction."""
    if entry <= 0 or leverage <= 0 or mmf is None or mmf < 0:
        return None
    eff_mmf = mmf + max(0.0, fee_buffer_frac)
    if side == "long":
        if eff_mmf >= 1.0:
            return None
        return entry * (1.0 - 1.0 / leverage) / (1.0 - eff_mmf)
    return entry * (1.0 + 1.0 / leverage) / (1.0 + eff_mmf)


def estimate(*, entry: float, side: str, leverage: float,
             maintenance_margin_frac: float | None, margin_mode: str,
             quantity: float = 0.0, account_equity: float | None = None,
             account_maintenance: float | None = None,
             fee_buffer_frac: float = 0.0005) -> LiquidationEstimate:
    if maintenance_margin_frac is None:
        return LiquidationEstimate(
            None, "maintenance margin fraction unknown for this market",
            margin_mode, reliable=False)
    if entry <= 0 or leverage <= 0:
        return LiquidationEstimate(None, "entry or leverage not positive",
                                   margin_mode, reliable=False)
    notional = abs(quantity) * entry
    im = notional / leverage if notional else 0.0
    mm = notional * maintenance_margin_frac

    if margin_mode == "isolated":
        px = isolated_liquidation(entry, leverage, maintenance_margin_frac,
                                  side, fee_buffer_frac)
        if px is None or px <= 0:
            return LiquidationEstimate(None, "isolated formula degenerate",
                                       margin_mode, im, mm, reliable=False)
        return LiquidationEstimate(
            px, "isolated closed form", margin_mode, im, mm,
            abs(px - entry) / entry, True,
            {"mmf": maintenance_margin_frac, "fee_buffer": fee_buffer_frac})

    if account_equity is None or account_maintenance is None:
        return LiquidationEstimate(
            None,
            "cross margin: liquidation is an ACCOUNT property and account "
            "equity / total maintenance were not supplied. Refusing to "
            "estimate rather than guess.",
            margin_mode, im, mm, reliable=False)
    if not notional:
        return LiquidationEstimate(None, "cross margin: zero notional",
                                   margin_mode, im, mm, reliable=False)
    # Account-level: the adverse move that eats free equity down to the total
    # maintenance requirement, attributed to THIS position's notional.
    free = account_equity - account_maintenance
    if free <= 0:
        return LiquidationEstimate(entry, "cross margin: already at or below "
                                   "maintenance", margin_mode, im, mm, 0.0,
                                   True, {"free_equity": free})
    move = free / notional
    px = entry * (1.0 - move) if side == "long" else entry * (1.0 + move)
    return LiquidationEstimate(
        px, "cross margin: account free-equity attribution", margin_mode,
        im, mm, abs(px - entry) / entry, True,
        {"free_equity": free, "account_equity": account_equity,
         "account_maintenance": account_maintenance})


def stop_is_safe(*, entry: float, stop: float, side: str, atr: float,
                 liq: LiquidationEstimate, min_atr_buffer: float
                 ) -> tuple[bool, str, float | None]:
    """The stop must sit at least `min_atr_buffer` ATR on the SAFE side of
    liquidation. An unreliable estimate is a REFUSAL, never a pass."""
    if not liq.reliable or liq.price is None:
        return False, f"liquidation not reliably computable: {liq.reason}", None
    if atr <= 0:
        return False, "ATR not positive; cannot express the buffer", None
    gap = (stop - liq.price) if side == "long" else (liq.price - stop)
    gap_atr = gap / atr
    if gap <= 0:
        return False, (f"stop {stop:.8g} is at or BEYOND liquidation "
                       f"{liq.price:.8g} -- the exchange would close first"), gap_atr
    if gap_atr < min_atr_buffer:
        return False, (f"stop-to-liquidation {gap_atr:.2f} ATR < the "
                       f"{min_atr_buffer:.2f} ATR minimum"), gap_atr
    return True, f"stop is {gap_atr:.2f} ATR clear of liquidation", gap_atr


def max_safe_leverage(*, entry: float, stop: float, side: str, atr: float,
                      mmf: float, min_atr_buffer: float,
                      cap: float, fee_buffer_frac: float = 0.0005,
                      step: float = 0.25) -> float:
    """The largest leverage (<= cap) at which the stop still clears
    liquidation by the buffer. Walks DOWN from the cap and returns 0.0 when no
    admissible leverage exists -- which is a refusal, not a 1x fallback."""
    lev = cap
    while lev >= 1.0:
        est = estimate(entry=entry, side=side, leverage=lev,
                       maintenance_margin_frac=mmf, margin_mode="isolated",
                       quantity=1.0, fee_buffer_frac=fee_buffer_frac)
        ok, _reason, _gap = stop_is_safe(entry=entry, stop=stop, side=side,
                                         atr=atr, liq=est,
                                         min_atr_buffer=min_atr_buffer)
        if ok:
            return round(lev, 4)
        lev -= step
    return 0.0
