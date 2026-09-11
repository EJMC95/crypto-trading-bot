"""Order construction and the exit ladder.

`side_to_action` is the ONLY conversion from our "long"/"short" to the
exchange's "buy"/"sell", and every builder calls it. A sign error that lives
in one function is a bug; the same error copied into six call sites is an
incident.

THE EXIT RULE: every exit is REDUCE-ONLY. An exit that is not reduce-only can,
on a race with a partial fill or a stale position read, OPEN a position in the
opposite direction -- turning a risk-reducing action into a new naked trade.

THE UNRESTRICTED-MARKET-ORDER RULE: this package never emits one. The most
aggressive thing it will build is a MARKETABLE LIMIT with an explicit
slippage cap, and only when spread and liquidity are inside their limits.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .config import ExecutionConfig, StrategyConfig
from .logging_setup import get
from .models import (Market, OrderIntent, OrderRequest, Position, Signal,
                     Sizing)
from .risk import round_step, round_tick

log = get("execution")


def side_to_action(side: str, *, closing: bool = False) -> str:
    """long->buy, short->sell (and the reverse when closing).
    THE ONLY PLACE THIS CONVERSION HAPPENS."""
    if side not in ("long", "short"):
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")
    opening = {"long": "buy", "short": "sell"}[side]
    if not closing:
        return opening
    return "sell" if opening == "buy" else "buy"


def spread_bps(bid: float | None, ask: float | None) -> float | None:
    if not bid or not ask or bid <= 0 or ask <= 0:
        return None
    mid = 0.5 * (bid + ask)
    return None if mid <= 0 else 10_000.0 * (ask - bid) / mid


def slippage_bps(expected: float, filled: float, side: str) -> float:
    """Positive = worse than expected, for BOTH sides."""
    if expected <= 0:
        return 0.0
    raw = (filled - expected) / expected
    return 10_000.0 * (raw if side == "long" else -raw)


def acceptable_fill(expected: float, filled: float, side: str,
                    cfg: ExecutionConfig) -> tuple[bool, float]:
    s = slippage_bps(expected, filled, side)
    return s <= cfg.max_slippage_bps, s


_COID = int(time.time() * 1000) % 1_000_000


def next_client_order_id(prefix: str = "dtb") -> str:
    """Distinct from the signal id on purpose: the exchange wants a short
    unique token, the dedup logic wants a meaningful string."""
    global _COID
    _COID = (_COID + 1) % 1_000_000_000
    return f"{prefix}-{_COID}"


@dataclass
class Plan:
    """The complete intent for one trade. Dry-run renders exactly this."""
    entry: OrderRequest
    stop: OrderRequest
    targets: list[OrderRequest]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"entry": self.entry.as_dict(), "stop": self.stop.as_dict(),
                "targets": [t.as_dict() for t in self.targets],
                "notes": self.notes}


def choose_entry_order(cfg: ExecutionConfig, spread: float | None,
                       urgent: bool) -> tuple[str, bool, float | None, list[str]]:
    """-> (order_type, post_only, slippage_cap_bps, notes).

    An unknown or wide spread NEVER yields anything marketable: that is
    precisely when crossing is most expensive."""
    notes: list[str] = []
    if spread is None:
        notes.append("spread unknown -> passive limit, never marketable")
        return "limit", True, None, notes
    if spread > cfg.max_spread_bps:
        notes.append(f"spread {spread:.1f}bps over the "
                     f"{cfg.max_spread_bps:.0f}bps limit -> passive only")
        return "limit", True, None, notes
    if urgent and cfg.allow_marketable_limit:
        notes.append(f"marketable limit with a {cfg.max_slippage_bps:.0f}bps "
                     "slippage cap (never an unrestricted market order)")
        return "limit", False, cfg.max_slippage_bps, notes
    if cfg.prefer_limit_orders:
        return "limit", True, None, notes
    return "limit", False, cfg.max_slippage_bps, notes


def build_plan(*, signal: Signal, sizing: Sizing, market: Market,
               cfg: ExecutionConfig, strat: StrategyConfig,
               spread: float | None = None, urgent: bool = False,
               adapter_supports_stop: bool = True,
               adapter_supports_tp: bool = True) -> Plan:
    """Entry + protective stop + scale-out targets, fully rounded."""
    if not sizing.ok:
        raise ValueError(f"cannot build a plan for a refused trade: "
                         f"{sizing.reason}")
    # A stop on the WRONG SIDE of the entry is a trade that is stopped the
    # instant it fills, and `risk = abs(entry - stop)` is happily positive for
    # it -- so the arithmetic upstream looks fine and the money is gone.
    # `build_stop` cannot produce one any more; this refuses one that arrives
    # from anywhere else, because this is where a number becomes an ORDER.
    if signal.side == "short" and signal.stop <= signal.entry:
        raise ValueError(f"short stop {signal.stop} is not above the entry "
                         f"{signal.entry}")
    if signal.side == "long" and signal.stop >= signal.entry:
        raise ValueError(f"long stop {signal.stop} is not below the entry "
                         f"{signal.entry}")
    otype, post_only, slip_cap, notes = choose_entry_order(cfg, spread, urgent)
    sym = signal.symbol
    entry_px = round_tick(signal.entry, market.tick_size, side=signal.side,
                          protective=False)
    # A protective level rounds AWAY from the position -- never into a tighter
    # level than the risk calculation used.
    stop_px = round_tick(signal.stop, market.tick_size, side=signal.side,
                         protective=True)
    qty = round_step(sizing.quantity, market.qty_step)

    entry = OrderRequest(
        symbol=sym, side=signal.side, action=side_to_action(signal.side),
        intent=OrderIntent.ENTRY, order_type=otype, quantity=qty,
        price=entry_px, reduce_only=False, post_only=post_only,
        time_in_force="GTC", client_order_id=next_client_order_id(),
        signal_id=signal.signal_id, max_slippage_bps=slip_cap,
        detail={"score": signal.score.total, "setup": signal.setup,
                "regime": signal.regime.value, "leverage": sizing.leverage,
                "timeout_s": cfg.order_timeout_seconds})

    if not adapter_supports_stop:
        notes.append("WARNING: the adapter reports NO native stop. A "
                     "client-side stop dies with the process; live trading "
                     "must be refused for this market.")
    stop = OrderRequest(
        symbol=sym, side=signal.side,
        action=side_to_action(signal.side, closing=True),
        intent=OrderIntent.STOP, order_type="stop", quantity=qty,
        price=None, trigger_price=stop_px,
        reduce_only=cfg.use_reduce_only_exits, post_only=False,
        time_in_force="GTC", client_order_id=next_client_order_id(),
        signal_id=signal.signal_id,
        detail={"r_unit": abs(signal.entry - signal.stop)})

    targets: list[OrderRequest] = []
    fractions = [strat.tp1_fraction, strat.tp2_fraction]
    for k, tp in enumerate(signal.targets[:2]):
        tq = round_step(qty * fractions[k], market.qty_step)
        if tq <= 0:
            notes.append(f"TP{k + 1} skipped: {fractions[k]:.0%} of {qty} "
                         "rounds to zero at this step size")
            continue
        if not adapter_supports_tp:
            notes.append("adapter reports no native take-profit; TPs will be "
                         "managed locally and are NOT exchange-resident")
        targets.append(OrderRequest(
            symbol=sym, side=signal.side,
            action=side_to_action(signal.side, closing=True),
            intent=OrderIntent.TAKE_PROFIT, order_type="take_profit",
            quantity=tq, price=None,
            trigger_price=round_tick(tp, market.tick_size, side=signal.side,
                                     protective=False),
            reduce_only=cfg.use_reduce_only_exits,
            client_order_id=next_client_order_id(),
            signal_id=signal.signal_id,
            detail={"r_multiple": strat.tp1_r if k == 0 else strat.tp2_r,
                    "fraction": fractions[k]}))

    if not cfg.use_reduce_only_exits:
        notes.append("WARNING: reduce-only exits are DISABLED in config")
    return Plan(entry, stop, targets, notes)


# ------------------------------------------------------------ trailing ------
def breakeven_stop(position: Position, cfg: ExecutionConfig) -> float:
    """After TP1: breakeven PLUS estimated round-trip fees, so a stopped
    runner is not a loss manufactured by our own costs."""
    fee_px = position.entry_price * (2.0 * cfg.taker_fee)
    return (position.entry_price - fee_px if position.side == "short"
            else position.entry_price + fee_px)


def trail_stop(position: Position, ema20: float | None, atr: float,
               buffer_atr: float = 0.25) -> float:
    """Ratchet the stop toward the position, never away from it.

    A DELIBERATE DEPARTURE FROM THE WRITTEN SPEC, flagged rather than silently
    implemented. The spec gives the short trail as:

        max(previous_stop, 1H EMA 20 + ATR buffer)

    and `max` is the LONG form. A short's stop sits ABOVE its entry, so a
    HIGHER stop is a LOOSER one. Worked through: short at 100 with the stop at
    105, price falls to 90, EMA20 93 and ATR 2 gives a candidate of 93.5.
    `max(105, 93.5)` = 105 -- the stop never moves, the trail does nothing,
    and the runner gives back the entire move. Worse, on a rally the same
    formula would RAISE the stop, which is widening a stop to avoid a loss --
    the one thing the safety requirements forbid outright.

    So the short form is `min`, the long form is `max`, and the invariant both
    express is the real rule: **the stop is monotone toward the position.**
    `test_execution` pins that a trail can never loosen on either side."""
    if ema20 is None or atr <= 0:
        return position.stop_price
    if position.side == "short":
        candidate = ema20 + buffer_atr * atr
        return min(position.stop_price, candidate)   # lower = tighter for short
    candidate = ema20 - buffer_atr * atr
    return max(position.stop_price, candidate)       # higher = tighter for long


def should_time_stop(position: Position, now: float,
                     max_holding_days: float) -> bool:
    return (now - position.opened_ts) >= max_holding_days * 86400.0
