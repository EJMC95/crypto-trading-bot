"""Position sizing and the budget ladder.

THE RULE THIS MODULE EXISTS TO ENFORCE: **leverage is not a reason to take
more risk.** Size comes from the STOP DISTANCE and equity:

    risk_amount = equity * risk_per_trade * regime_mult * health_mult
    quantity    = risk_amount / |entry - stop|

Leverage only decides whether that quantity FITS in the margin available, and
it is capped at `min(config, account, market)`. Raising leverage never raises
`risk_amount`; it can only make an already-sized position financeable -- and
if the resulting leverage would put liquidation inside the stop, the trade is
refused or the leverage is walked down (`liquidation.max_safe_leverage`).

Every refusal carries a reason. `RiskDecision(ok=False)` with an empty reason
is a bug, and `test_risk` pins that.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import liquidation as liq
from .config import RiskConfig, ExecutionConfig
from .logging_setup import get
from .market_metadata import MarketRegistry
from .models import RiskDecision, Signal

log = get("risk")


@dataclass
class AccountState:
    equity: float
    available_collateral: float
    margin_used: float = 0.0
    account_max_leverage: float = 20.0
    margin_mode: str = "isolated"
    total_maintenance: float = 0.0

    @property
    def margin_utilisation(self) -> float:
        return 0.0 if self.equity <= 0 else self.margin_used / self.equity


@dataclass
class ExposureState:
    """What the book already carries. Passed in rather than discovered so the
    sizer stays pure and the caller owns reconciliation."""
    open_positions: int = 0
    open_risk: float = 0.0              # sum of risk-at-stop, currency
    gross_notional: float = 0.0
    net_long_notional: float = 0.0
    net_short_notional: float = 0.0
    per_market_notional: dict[str, float] = field(default_factory=dict)
    day_pnl: float = 0.0
    week_pnl: float = 0.0
    correlation_group_count: dict[str, int] = field(default_factory=dict)


def _pct(x: float, equity: float) -> float:
    return 0.0 if equity <= 0 else 100.0 * x / equity


def size_position(*, signal: Signal, account: AccountState,
                  exposure: ExposureState, registry: MarketRegistry,
                  risk_cfg: RiskConfig, exec_cfg: ExecutionConfig,
                  regime_multiplier: float, health_multiplier: float = 1.0,
                  requested_leverage: float | None = None,
                  correlation_multiplier: float = 1.0,
                  liquidity_multiplier: float = 1.0,
                  volatility_multiplier: float = 1.0,
                  est_funding: float = 0.0) -> RiskDecision:
    eq = account.equity
    sym = signal.symbol
    meta = registry.get(sym)
    if meta is None or not meta.complete:
        missing = "unknown market" if meta is None else ", ".join(meta.missing())
        return RiskDecision(False, f"{sym}: metadata incomplete ({missing})")
    if eq <= 0:
        return RiskDecision(False, "equity is not positive")
    if regime_multiplier <= 0:
        return RiskDecision(False, "regime forbids new entries")

    # ---- loss lockouts, checked BEFORE any sizing arithmetic -------------
    if exposure.day_pnl <= -abs(risk_cfg.max_daily_loss) * eq:
        return RiskDecision(False, f"daily loss lockout: {exposure.day_pnl:.2f} "
                            f"<= -{risk_cfg.max_daily_loss:.3%} of equity")
    if exposure.week_pnl <= -abs(risk_cfg.max_weekly_loss) * eq:
        return RiskDecision(False, f"weekly loss lockout: {exposure.week_pnl:.2f}")
    if exposure.open_positions >= risk_cfg.max_concurrent_positions:
        return RiskDecision(False, f"at max_concurrent_positions "
                            f"({risk_cfg.max_concurrent_positions})")
    if account.margin_utilisation >= risk_cfg.max_margin_utilisation:
        return RiskDecision(False, f"margin utilisation "
                            f"{account.margin_utilisation:.1%} >= "
                            f"{risk_cfg.max_margin_utilisation:.1%}")

    # ---- risk budget -----------------------------------------------------
    mult = (regime_multiplier * health_multiplier * correlation_multiplier
            * liquidity_multiplier * volatility_multiplier)
    risk_amount = eq * risk_cfg.risk_per_trade * mult
    budget_left = eq * risk_cfg.max_portfolio_risk - exposure.open_risk
    if budget_left <= 0:
        return RiskDecision(False, f"portfolio risk budget exhausted "
                            f"(open {exposure.open_risk:.2f} of "
                            f"{eq * risk_cfg.max_portfolio_risk:.2f})")
    if risk_amount > budget_left:
        risk_amount = budget_left

    entry, stop = signal.entry, signal.stop
    dist = abs(entry - stop)
    if dist <= 0:
        return RiskDecision(False, "stop distance is zero")

    # ---- leverage: capped, then walked down if the stop needs it ---------
    want = requested_leverage if requested_leverage is not None \
        else risk_cfg.max_leverage
    cap = registry.effective_leverage(sym, min(want, risk_cfg.max_leverage),
                                      account.account_max_leverage)
    if cap <= 0:
        return RiskDecision(False, f"{sym}: no admissible leverage")
    safe_lev = liq.max_safe_leverage(
        entry=entry, stop=stop, side=signal.side, atr=signal.atr,
        mmf=meta.maintenance_margin_frac or 0.0,
        min_atr_buffer=risk_cfg.min_stop_to_liquidation_atr, cap=cap)
    if safe_lev <= 0:
        return RiskDecision(
            False,
            f"{sym}: no leverage up to {cap:.2f}x keeps the stop "
            f"{risk_cfg.min_stop_to_liquidation_atr:.1f} ATR clear of "
            "liquidation -- the stop is too close to the liquidation price")
    leverage = safe_lev

    # ---- quantity from the STOP, then every cap ---------------------------
    qty = risk_amount / dist
    caps: list[tuple[str, float]] = []

    max_mkt_notional = eq * risk_cfg.max_notional_per_market_percent / 100.0
    held = exposure.per_market_notional.get(sym, 0.0)
    room = max(0.0, max_mkt_notional - held)
    caps.append(("per_market_notional", room / entry if entry > 0 else 0.0))

    gross_room = max(0.0, eq * risk_cfg.max_gross_notional_percent / 100.0
                     - exposure.gross_notional)
    caps.append(("gross_notional", gross_room / entry if entry > 0 else 0.0))

    if signal.side == "long":
        side_room = max(0.0, eq * risk_cfg.max_net_long_notional_percent / 100.0
                        - exposure.net_long_notional)
        caps.append(("net_long_notional", side_room / entry))
    else:
        side_room = max(0.0, eq * risk_cfg.max_net_short_notional_percent / 100.0
                        - exposure.net_short_notional)
        caps.append(("net_short_notional", side_room / entry))

    margin_room = max(0.0, eq * risk_cfg.max_margin_utilisation
                      - account.margin_used)
    margin_room = min(margin_room, max(0.0, account.available_collateral))
    caps.append(("margin", margin_room * leverage / entry if entry > 0 else 0.0))

    binding = "risk_at_stop"
    for name, cap_qty in caps:
        if cap_qty < qty:
            qty, binding = cap_qty, name
    if qty <= 0:
        return RiskDecision(False, f"{binding} leaves no room for a position")

    qty = registry.round_qty(sym, qty)
    ok, why = registry.order_ok(sym, qty, entry)
    if not ok:
        return RiskDecision(False, why, detail={"binding_cap": binding})

    notional = qty * entry
    actual_risk = qty * dist
    if actual_risk > budget_left * 1.0001:
        return RiskDecision(False, f"rounded size risks {actual_risk:.4f} "
                            f"above the remaining budget {budget_left:.4f}")

    est = liq.estimate(entry=entry, side=signal.side, leverage=leverage,
                       maintenance_margin_frac=meta.maintenance_margin_frac,
                       margin_mode=account.margin_mode, quantity=qty,
                       account_equity=eq,
                       account_maintenance=account.total_maintenance)
    safe, reason, gap_atr = liq.stop_is_safe(
        entry=entry, stop=stop, side=signal.side, atr=signal.atr, liq=est,
        min_atr_buffer=risk_cfg.min_stop_to_liquidation_atr)
    if not safe:
        return RiskDecision(False, f"{sym}: {reason}")

    fee_rate = exec_cfg.taker_fee if exec_cfg.taker_fee else 0.0
    est_fees = 2.0 * notional * fee_rate
    # Worst case is a GAP THROUGH the stop, not a fill at it. 1 ATR beyond is
    # the modelled gap; it is a floor on the pain, never a promise.
    gap_px = (stop - signal.atr) if signal.side == "long" else (stop + signal.atr)
    worst = qty * abs(entry - gap_px) + est_fees

    return RiskDecision(
        ok=True, reason=f"sized off the stop; binding cap: {binding}",
        quantity=qty, notional=notional, risk_amount=actual_risk,
        risk_pct_equity=_pct(actual_risk, eq), leverage=leverage,
        initial_margin=notional / leverage,
        maintenance_margin=notional * (meta.maintenance_margin_frac or 0.0),
        liquidation_price=est.price, stop_to_liq_atr=gap_atr,
        est_fees=est_fees, est_funding=est_funding, worst_case_gap_loss=worst,
        rounded=True,
        detail={"binding_cap": binding, "risk_multiplier": mult,
                "regime_multiplier": regime_multiplier,
                "health_multiplier": health_multiplier,
                "leverage_cap": cap, "leverage_used": leverage,
                "stop_distance": dist, "stop_atr": dist / max(signal.atr, 1e-12),
                "budget_left_before": budget_left,
                "gross_after_pct": _pct(exposure.gross_notional + notional, eq),
                "liquidation_reason": est.reason})


def volatility_multiplier(atr_pct_of_price: float,
                          reference: float = 0.02) -> float:
    """Halve size as volatility doubles past the reference, floored at 0.35.
    Bounded on BOTH ends: an unbounded vol scaler becomes a leverage knob in
    quiet markets."""
    if atr_pct_of_price <= 0:
        return 1.0
    return max(0.35, min(1.25, reference / atr_pct_of_price))


def liquidity_multiplier(spread_bps: float | None, max_spread_bps: float
                         ) -> float:
    """Unknown liquidity sizes DOWN, never up."""
    if spread_bps is None:
        return 0.5
    if spread_bps >= max_spread_bps:
        return 0.0
    return max(0.35, 1.0 - 0.65 * (spread_bps / max(max_spread_bps, 1e-9)))


def correlation_multiplier(group_count: int) -> float:
    """N positions in one correlated group are closer to ONE bet than to N.
    Sizing the (N+1)th at full risk is how a book discovers it held one trade
    in five names. 1/sqrt(1+N) is the crude, conservative form."""
    return 1.0 / ((1.0 + max(0, group_count)) ** 0.5)
