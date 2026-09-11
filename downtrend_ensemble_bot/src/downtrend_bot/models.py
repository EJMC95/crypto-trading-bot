"""Typed domain objects and the filesystem boundary.

Two conventions the package relies on:
  * `side` is "long" or "short" in OUR code. The exchange's own vocabulary
    ("buy"/"sell") is produced at exactly ONE place, `execution.side_to_action`,
    so a sign error cannot be spread by copying.
  * every price and quantity reaching an adapter has ALREADY been rounded to
    the market's tick/step. `Sizing.rounded` records that it happened.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Mode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class Regime(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    PANIC = "PANIC"
    DATA_UNRELIABLE = "DATA_UNRELIABLE"


class StrategyState(str, Enum):
    ACTIVE = "ACTIVE"
    THROTTLED = "THROTTLED"
    PAUSED = "PAUSED"
    RECOVERY = "RECOVERY"
    DISABLED = "DISABLED"


class OrderIntent(str, Enum):
    ENTRY = "entry"
    STOP = "stop"
    TAKE_PROFIT = "take_profit"
    TRAIL = "trail"
    FLATTEN = "flatten"


@dataclass(frozen=True)
class Market:
    """One perpetual market as the venue currently describes it.

    `tradable` is the gate: a market missing tick size, step, minimum size or
    contract status is REFUSED rather than defaulted, because every default
    here is a silent risk decision."""
    symbol: str
    base: str = ""
    quote: str = "USDT"
    tick_size: float = 0.0
    qty_step: float = 0.0
    min_qty: float = 0.0
    min_notional: float = 0.0
    max_leverage: float | None = None
    maker_fee: float | None = None
    taker_fee: float | None = None
    quote_volume_24h: float = 0.0
    status: str = "unknown"
    contract: bool = True

    def missing(self) -> list[str]:
        out = []
        for name in ("tick_size", "qty_step", "min_qty"):
            if getattr(self, name) <= 0:
                out.append(name)
        if self.taker_fee is None:
            out.append("taker_fee")
        if str(self.status).lower() not in ("active", "open", "trading"):
            out.append(f"status={self.status}")
        if not self.contract:
            out.append("not a perpetual contract")
        return out

    @property
    def tradable(self) -> bool:
        return not self.missing()


@dataclass
class Candle:
    ts: int          # UNIX seconds, bar OPEN
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Quality:
    """The liquidity/data screen a symbol must pass before it is considered."""
    symbol: str
    ok: bool
    reasons: list[str] = field(default_factory=list)
    quote_volume_24h: float = 0.0
    spread_bps: float | None = None
    depth_usd: float | None = None
    stale_s: float | None = None


@dataclass
class ScoreCard:
    """Every component that produced a score, kept so a REJECTED signal can
    say why. A score with no breakdown is unexplainable and untunable."""
    regime: float = 0.0
    trend: float = 0.0
    breakdown: float = 0.0
    momentum: float = 0.0
    volume: float = 0.0
    derivatives: float = 0.0
    quality: float = 0.0
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return round(self.regime + self.trend + self.breakdown + self.momentum
                     + self.volume + self.derivatives + self.quality, 4)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total"] = self.total
        return d


@dataclass
class Signal:
    symbol: str
    side: str                     # "short" | "long"
    strategy: str
    setup: str
    timeframe: str
    candle_ts: int
    score: ScoreCard
    entry: float
    stop: float
    targets: list[float] = field(default_factory=list)
    atr: float = 0.0
    reward_risk: float = 0.0
    regime: Regime = Regime.NEUTRAL
    trigger_level: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def signal_id(self) -> str:
        """Deterministic (spec 26A): strategy + symbol + timeframe + candle +
        setup. The same setup on the same closed candle is the SAME signal, so
        a restart cannot double-enter."""
        return (f"{self.strategy}:{self.symbol}:{self.timeframe}"
                f":{self.candle_ts}:{self.setup}:{self.side}")


@dataclass
class Sizing:
    """The answer to 'may we take this, and how big?'. `ok=False` always
    carries a reason; a refusal with no reason is a bug."""
    ok: bool
    reason: str = ""
    quantity: float = 0.0
    notional: float = 0.0
    risk_amount: float = 0.0
    risk_pct_equity: float = 0.0
    leverage: float = 0.0
    est_fees: float = 0.0
    est_funding: float = 0.0
    worst_case_gap_loss: float = 0.0
    rounded: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderRequest:
    """What we INTEND to send. Dry-run emits exactly this and stops."""
    symbol: str
    side: str                     # position side this order serves
    action: str                   # "buy" | "sell" -- the exchange's word
    intent: OrderIntent
    order_type: str               # "limit" | "market" | "stop" | "take_profit"
    quantity: float
    price: float | None = None
    trigger_price: float | None = None
    reduce_only: bool = False
    post_only: bool = False
    time_in_force: str = "GTC"
    client_order_id: str = ""
    signal_id: str = ""
    max_slippage_bps: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["intent"] = self.intent.value
        return d


@dataclass
class OrderResult:
    accepted: bool
    order_id: str | None = None
    status: str = ""
    filled: float = 0.0
    avg_price: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    submitted: bool = False       # False in dry-run: never sent


@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    opened_ts: float
    stop_price: float
    targets: list[float] = field(default_factory=list)
    strategy: str = ""
    signal_id: str = ""
    scaled_out: float = 0.0
    realized: float = 0.0
    stop_order_id: str | None = None
    protective_ok: bool = False
    r_unit: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def unrealized(self, mark: float) -> float:
        sgn = 1.0 if self.side == "long" else -1.0
        return sgn * (mark - self.entry_price) * self.quantity

    def r_multiple(self, price: float) -> float:
        if self.r_unit <= 0:
            return 0.0
        sgn = 1.0 if self.side == "long" else -1.0
        return sgn * (price - self.entry_price) / self.r_unit


@dataclass
class Fill:
    symbol: str
    side: str
    quantity: float
    price: float
    ts: float
    fee: float = 0.0
    order_id: str | None = None
    partial: bool = False


@dataclass
class Trade:
    """One closed round trip, in R and in currency."""
    symbol: str
    side: str
    strategy: str
    setup: str
    regime: str
    opened_ts: float
    closed_ts: float
    entry: float
    exit: float
    quantity: float
    pnl: float
    fees: float
    funding: float
    r_multiple: float
    reason: str
    signal_id: str = ""
    slippage_bps: float = 0.0
    score: float = 0.0

    @property
    def held_h(self) -> float:
        return max(0.0, (self.closed_ts - self.opened_ts) / 3600.0)


def now() -> float:
    return time.time()


# ------------------------------------------------------ filesystem boundary --
#: Allowlist for a path COMPONENT. Anything else is replaced.
_SAFE_CHARS = set("abcdefghijklmnopqrstuvwxyz"
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def safe_filename(name: str, *, fallback: str = "unnamed",
                  max_len: int = 96) -> str:
    """Reduce an untrusted string to ONE safe path component.

    Symbols here look like `BTC/USDT:USDT` -- they contain a separator and a
    colon by design, so they can NEVER be interpolated into a filename raw.
    This is an allowlist rather than a denylist because a denylist is the
    version that keeps getting bypassed: the interesting inputs are the ones
    nobody thought to list. Leading dots are stripped so a component can never
    be `.`, `..` or a hidden file, and an empty result becomes `fallback` --
    `os.path.join(d, "")` silently yields the DIRECTORY."""
    cleaned = "".join(c if c in _SAFE_CHARS else "_" for c in str(name))
    cleaned = cleaned.lstrip(".")[:max_len]
    return cleaned or fallback


def contained_path(directory: str, *parts: str) -> str:
    """Join under `directory` and REFUSE to escape it.

    Belt and braces: every part is sanitised, and the resolved result is then
    required to sit inside the resolved directory. The second check is what
    catches a symlink planted at the target name; only one of the two has to
    hold for the write to be safe."""
    root = os.path.realpath(directory)
    joined = os.path.join(root, *[safe_filename(p) for p in parts])
    resolved = os.path.realpath(joined)
    if resolved != root and not resolved.startswith(root + os.sep):
        raise ValueError(
            f"refusing to write outside {directory!r}: {joined!r} resolves to "
            f"{resolved!r}")
    return joined
