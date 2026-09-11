"""Position sizing and the budget ladder.

THE RULE THIS MODULE ENFORCES: **size comes from the STOP DISTANCE, never
from a fixed coin quantity and never from leverage.**

    risk_amount = equity * risk_per_trade * regime_mult * health_mult
    quantity    = risk_amount / |entry - stop|

Leverage (capped at 1.5x by default) only decides whether the already-sized
position FITS. Raising it never raises `risk_amount`. Every refusal carries a
reason -- `Sizing(ok=False)` with an empty reason is a bug, and `test_risk`
pins that.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import ExecutionConfig, RiskConfig
from .logging_setup import get
from .models import Market, Signal, Sizing

log = get("risk")


@dataclass
class Account:
    equity: float
    free_collateral: float
    margin_used: float = 0.0
    max_leverage: float = 1.5


@dataclass
class Exposure:
    """What the book already carries. Passed in rather than discovered, so the
    sizer stays pure and the caller owns reconciliation."""
    open_positions: int = 0
    open_risk: float = 0.0
    gross_notional: float = 0.0
    short_notional: float = 0.0
    long_notional: float = 0.0
    per_symbol_notional: dict[str, float] = field(default_factory=dict)
    correlated_counts: dict[str, int] = field(default_factory=dict)
    day_pnl: float = 0.0
    week_pnl: float = 0.0
    consecutive_losses: int = 0


def round_step(value: float, step: float) -> float:
    """Always DOWN: rounding a size UP can breach a notional cap."""
    if step <= 0:
        return value
    return math.floor(value / step) * step


def round_tick(price: float, tick: float, *, side: str,
               protective: bool) -> float:
    """A PROTECTIVE level rounds AWAY from the position, so a rounding error
    can never tighten a stop into something the risk maths did not price."""
    if tick <= 0:
        return price
    n = price / tick
    if not protective:
        return round(n) * tick
    # short stop is ABOVE entry -> round up; long stop is BELOW -> round down
    return (math.ceil(n) if side == "short" else math.floor(n)) * tick


def volatility_multiplier(atr_frac: float, reference: float = 0.02) -> float:
    """Halve size as volatility doubles past the reference. Bounded at BOTH
    ends -- an unbounded vol scaler becomes a leverage knob in a quiet tape."""
    if atr_frac <= 0:
        return 1.0
    return max(0.35, min(1.20, reference / atr_frac))


def liquidity_multiplier(spread_bps: float | None, max_spread_bps: float
                         ) -> float:
    """Unknown liquidity sizes DOWN, never up."""
    if spread_bps is None:
        return 0.5
    if spread_bps >= max_spread_bps:
        return 0.0
    return max(0.35, 1.0 - 0.65 * (spread_bps / max(max_spread_bps, 1e-9)))


def correlation_multiplier(existing_in_group: int, penalty: float) -> float:
    """Spec 9: if BTC and ETH are both open, the SECOND position is penalised.
    N positions in one correlated group are closer to ONE bet than to N, and
    sizing the (N+1)th at full risk is how a book finds out it held one trade
    in three names."""
    if existing_in_group <= 0:
        return 1.0
    return max(0.0, penalty ** existing_in_group)


def size_position(*, signal: Signal, market: Market, account: Account,
                  exposure: Exposure, risk_cfg: RiskConfig,
                  exec_cfg: ExecutionConfig, regime_multiplier: float,
                  health_multiplier: float = 1.0,
                  spread_bps: float | None = None,
                  correlated_group_count: int = 0,
                  est_funding: float = 0.0) -> Sizing:
    eq = account.equity
    sym = signal.symbol

    if not market.tradable:
        return Sizing(False, f"{sym}: market not tradable "
                             f"({', '.join(market.missing())})")
    if eq <= 0:
        return Sizing(False, "equity is not positive")
    if regime_multiplier <= 0:
        return Sizing(False, "regime forbids new entries in this direction")

    # ---- lockouts, checked BEFORE any sizing arithmetic ------------------
    if exposure.day_pnl <= -abs(risk_cfg.max_daily_loss) * eq:
        return Sizing(False, f"daily loss lockout: {exposure.day_pnl:.2f} <= "
                             f"-{risk_cfg.max_daily_loss:.2%} of equity")
    if exposure.week_pnl <= -abs(risk_cfg.max_weekly_loss) * eq:
        return Sizing(False, f"weekly loss lockout: {exposure.week_pnl:.2f}")
    if exposure.consecutive_losses >= risk_cfg.max_consecutive_losses:
        return Sizing(False, f"{exposure.consecutive_losses} consecutive "
                             f"losses >= {risk_cfg.max_consecutive_losses}")
    if exposure.open_positions >= risk_cfg.max_concurrent_positions:
        return Sizing(False, f"at max_concurrent_positions "
                             f"({risk_cfg.max_concurrent_positions})")
    if correlated_group_count >= risk_cfg.max_correlated_positions:
        return Sizing(False, f"{correlated_group_count} correlated positions "
                             f">= {risk_cfg.max_correlated_positions}")
    util = 0.0 if eq <= 0 else account.margin_used / eq
    if util >= risk_cfg.max_margin_utilisation:
        return Sizing(False, f"margin utilisation {util:.1%} >= "
                             f"{risk_cfg.max_margin_utilisation:.1%}")

    # ---- risk budget -----------------------------------------------------
    vol_mult = volatility_multiplier(signal.atr / max(signal.entry, 1e-9))
    liq_mult = liquidity_multiplier(spread_bps, exec_cfg.max_spread_bps)
    corr_mult = correlation_multiplier(correlated_group_count,
                                       risk_cfg.correlation_penalty)
    if liq_mult <= 0:
        return Sizing(False, f"{sym}: spread {spread_bps} exceeds the "
                             f"{exec_cfg.max_spread_bps}bps limit")
    mult = (regime_multiplier * health_multiplier * vol_mult * liq_mult
            * corr_mult)
    risk_amount = eq * risk_cfg.risk_per_trade * mult

    budget_left = eq * risk_cfg.max_portfolio_risk - exposure.open_risk
    if budget_left <= 0:
        return Sizing(False, f"portfolio risk budget exhausted (open "
                             f"{exposure.open_risk:.2f} of "
                             f"{eq * risk_cfg.max_portfolio_risk:.2f})")
    risk_amount = min(risk_amount, budget_left)

    entry, stop = signal.entry, signal.stop
    dist = abs(entry - stop)
    if dist <= 0:
        return Sizing(False, "stop distance is zero")

    qty = risk_amount / dist
    binding = "risk_at_stop"
    caps: list[tuple[str, float]] = []

    per_sym = eq * risk_cfg.max_notional_per_symbol_pct
    room = max(0.0, per_sym - exposure.per_symbol_notional.get(sym, 0.0))
    caps.append(("per_symbol_notional", room / entry))

    lev_room = max(0.0, eq * min(risk_cfg.max_leverage, account.max_leverage,
                                 market.max_leverage or 1e9)
                   - exposure.gross_notional)
    caps.append(("leverage", lev_room / entry))

    if signal.side == "short":
        agg = eq * risk_cfg.max_aggregate_short_notional_pct
        caps.append(("aggregate_short_notional",
                     max(0.0, agg - exposure.short_notional) / entry))

    margin_room = max(0.0, eq * risk_cfg.max_margin_utilisation
                      - account.margin_used)
    margin_room = min(margin_room, max(0.0, account.free_collateral))
    caps.append(("margin", margin_room * risk_cfg.max_leverage / entry))

    for name, cap_qty in caps:
        if cap_qty < qty:
            qty, binding = cap_qty, name
    if qty <= 0:
        return Sizing(False, f"{binding} leaves no room for a position")

    qty = round_step(qty, market.qty_step)
    if qty < market.min_qty:
        return Sizing(False, f"{sym}: qty {qty} below the exchange minimum "
                             f"{market.min_qty}",
                      detail={"binding_cap": binding})
    notional = qty * entry
    if notional < market.min_notional:
        return Sizing(False, f"{sym}: notional {notional:.4f} below the "
                             f"exchange minimum {market.min_notional}")

    actual_risk = qty * dist
    if actual_risk > budget_left * 1.0001:
        return Sizing(False, f"rounded size risks {actual_risk:.4f}, above the "
                             f"remaining budget {budget_left:.4f}")

    leverage = notional / eq if eq > 0 else 0.0
    if leverage > risk_cfg.max_leverage * 1.0001:
        return Sizing(False, f"{sym}: implied leverage {leverage:.2f}x exceeds "
                             f"{risk_cfg.max_leverage}x")

    est_fees = 2.0 * notional * exec_cfg.taker_fee
    # Worst case is a GAP THROUGH the stop, not a fill at it. One ATR beyond
    # is the modelled gap -- a floor on the pain, never a promise.
    gap_px = (stop + signal.atr) if signal.side == "short" \
        else (stop - signal.atr)
    worst = qty * abs(entry - gap_px) + est_fees

    return Sizing(
        ok=True, reason=f"sized off the stop; binding cap: {binding}",
        quantity=qty, notional=notional, risk_amount=actual_risk,
        risk_pct_equity=100.0 * actual_risk / eq, leverage=leverage,
        est_fees=est_fees, est_funding=est_funding,
        worst_case_gap_loss=worst, rounded=True,
        detail={"binding_cap": binding, "risk_multiplier": mult,
                "regime_multiplier": regime_multiplier,
                "health_multiplier": health_multiplier,
                "volatility_multiplier": vol_mult,
                "liquidity_multiplier": liq_mult,
                "correlation_multiplier": corr_mult,
                "stop_distance": dist,
                "stop_atr": dist / max(signal.atr, 1e-12),
                "budget_left_before": budget_left,
                "margin_utilisation": util})
