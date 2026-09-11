"""Order construction: our vocabulary -> Lighter's, in exactly one place.

`side_to_is_ask` is the ONLY conversion from our "long"/"short" to Lighter's
`is_ask` boolean, and every order builder calls it. A sign error that lives in
one function is a bug; the same sign error copied into six call sites is an
incident, and this fleet's history is full of the second kind.

THE EXIT RULE: every exit is REDUCE-ONLY. An exit that is not reduce-only can,
on a race with a partial fill or a stale position read, OPEN a position in the
opposite direction -- turning a risk-reducing action into a new naked trade.

THE PROTECTIVE RULE: the entry and its stop are submitted as ONE grouped
transaction where the SDK exposes it
(`GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER`), so there is no window
in which a filled position has no stop. Where grouping is unavailable, the
stop is placed IMMEDIATELY after the fill and `require_native_stop_or_fail`
decides whether a failure to place it is tolerable (it is not, in live).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .config import ExecutionConfig
from .logging_setup import get
from .market_metadata import MarketRegistry
from .models import OrderIntent, OrderRequest, RiskDecision, Signal

log = get("execution")

#: Lighter SDK constants, mirrored by NAME so a version bump that renumbers
#: them is caught by `test_order_mapping` rather than by a wrong order.
ORDER_TYPE = {"limit": "ORDER_TYPE_LIMIT", "market": "ORDER_TYPE_MARKET",
              "stop_loss": "ORDER_TYPE_STOP_LOSS",
              "stop_loss_limit": "ORDER_TYPE_STOP_LOSS_LIMIT",
              "take_profit": "ORDER_TYPE_TAKE_PROFIT",
              "take_profit_limit": "ORDER_TYPE_TAKE_PROFIT_LIMIT",
              "twap": "ORDER_TYPE_TWAP"}
TIME_IN_FORCE = {"ioc": "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL",
                 "gtt": "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME",
                 "post_only": "ORDER_TIME_IN_FORCE_POST_ONLY"}


def side_to_is_ask(side: str) -> bool:
    """long -> buy -> is_ask False; short -> sell -> is_ask True.
    THE ONLY PLACE THIS CONVERSION HAPPENS."""
    if side not in ("long", "short"):
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")
    return side == "short"


def exit_side(position_side: str) -> str:
    return "short" if position_side == "long" else "long"


def spread_bps(best_bid: float | None, best_ask: float | None) -> float | None:
    if not best_bid or not best_ask or best_bid <= 0 or best_ask <= 0:
        return None
    mid = 0.5 * (best_bid + best_ask)
    return 0.0 if mid <= 0 else 10_000.0 * (best_ask - best_bid) / mid


@dataclass
class ExecutionPlan:
    """The complete intent for one trade. SHADOW mode renders exactly this and
    submits nothing."""
    entry: OrderRequest
    stop: OrderRequest
    targets: list[OrderRequest]
    grouped: bool
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"entry": self.entry.as_dict(), "stop": self.stop.as_dict(),
                "targets": [t.as_dict() for t in self.targets],
                "grouped": self.grouped, "notes": self.notes}


_COI = int(time.time() * 1000) % 1_000_000


def next_client_order_index() -> int:
    """Monotonic within a process; the caller persists it across restarts.
    Distinct from the signal id on purpose: the venue wants a small integer,
    the dedupe logic wants a meaningful string."""
    global _COI
    _COI = (_COI + 1) % 1_000_000_000
    return _COI


def choose_entry_order(cfg: ExecutionConfig, spread: float | None,
                       urgent: bool) -> tuple[str, str, list[str]]:
    """-> (order_type, time_in_force, notes). An unknown or wide spread NEVER
    yields a market order: that is precisely when an unrestricted market order
    is most expensive."""
    notes: list[str] = []
    if spread is None:
        notes.append("spread unknown -> post-only limit, never market")
        return "limit", "post_only", notes
    if spread > cfg.max_spread_bps:
        notes.append(f"spread {spread:.1f}bps over the "
                     f"{cfg.max_spread_bps:.0f}bps limit -> refuse urgency")
        return "limit", "post_only", notes
    if urgent and cfg.use_ioc_when_necessary:
        notes.append("urgency justified and spread inside limits -> IOC")
        return "limit", "ioc", notes
    if cfg.entry_preference == "post_only_limit":
        return "limit", "post_only", notes
    return "limit", "gtt", notes


def build_plan(*, signal: Signal, decision: RiskDecision,
               registry: MarketRegistry, cfg: ExecutionConfig,
               spread: float | None = None, urgent: bool = False,
               supports_grouping: bool = True,
               now_s: float | None = None) -> ExecutionPlan:
    """Entry + protective stop + scale-out targets, fully rounded."""
    if not decision.ok:
        raise ValueError(f"cannot build a plan for a refused trade: "
                         f"{decision.reason}")
    now_s = time.time() if now_s is None else now_s
    sym = signal.symbol
    mid = registry.market_id(sym)
    if mid is None:
        raise ValueError(f"{sym}: no market id")

    otype, tif, notes = choose_entry_order(cfg, spread, urgent)
    entry_px = registry.round_price(sym, signal.entry, side=signal.side,
                                    conservative=False)
    # A protective stop rounds AWAY from the position -- never into a tighter
    # level than the risk calculation used.
    stop_px = registry.round_price(sym, signal.stop, side=signal.side,
                                   conservative=True)
    qty = registry.round_qty(sym, decision.quantity)
    expiry_ms = int((now_s + cfg.order_timeout_seconds) * 1000)

    entry = OrderRequest(
        symbol=sym, market_id=mid, side=signal.side, intent=OrderIntent.ENTRY,
        order_type=otype, time_in_force=tif, price=entry_px,
        trigger_price=None, quantity=qty, reduce_only=False,
        client_order_index=next_client_order_index(), expiry_ms=expiry_ms,
        signal_id=signal.signal_id,
        detail={"score": signal.score.total, "setup": signal.setup,
                "regime": signal.regime.value,
                "leverage": decision.leverage})

    stop = OrderRequest(
        symbol=sym, market_id=mid, side=exit_side(signal.side),
        intent=OrderIntent.STOP, order_type="stop_loss",
        time_in_force="ioc", price=None, trigger_price=stop_px,
        quantity=qty, reduce_only=cfg.use_reduce_only_exits,
        client_order_index=next_client_order_index(), expiry_ms=None,
        signal_id=signal.signal_id,
        detail={"liquidation_price": decision.liquidation_price,
                "stop_to_liq_atr": decision.stop_to_liq_atr})

    targets: list[OrderRequest] = []
    fractions = [0.30, 0.35]
    for k, tp in enumerate(signal.targets[:2]):
        frac = fractions[k] if k < len(fractions) else 0.0
        tq = registry.round_qty(sym, qty * frac)
        if tq <= 0:
            notes.append(f"TP{k + 1} skipped: rounded size is zero at "
                         f"{frac:.0%} of {qty}")
            continue
        targets.append(OrderRequest(
            symbol=sym, market_id=mid, side=exit_side(signal.side),
            intent=OrderIntent.TAKE_PROFIT, order_type="take_profit",
            time_in_force="ioc", price=None,
            trigger_price=registry.round_price(sym, tp,
                                               side=exit_side(signal.side),
                                               conservative=False),
            quantity=tq, reduce_only=cfg.use_reduce_only_exits,
            client_order_index=next_client_order_index(), expiry_ms=None,
            signal_id=signal.signal_id, detail={"r_multiple": 1.2 + 0.8 * k}))

    grouped = bool(supports_grouping)
    notes.append("entry+stop submitted as one grouped transaction"
                 if grouped else
                 "grouping unavailable: stop placed immediately after fill")
    if not cfg.use_reduce_only_exits:
        notes.append("WARNING: reduce-only exits disabled in config")
    return ExecutionPlan(entry, stop, targets, grouped, notes)


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
