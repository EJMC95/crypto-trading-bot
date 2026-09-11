"""Typed domain objects. Dataclasses rather than Pydantic so the package has
no hard runtime dependency beyond the SDK, pandas and numpy.

Two conventions the rest of the package relies on:
  * `side` is the string "long" or "short" everywhere in OUR code. The
    exchange's `is_ask` boolean is produced at exactly ONE place
    (`execution.side_to_is_ask`) so a sign error cannot be spread by copying.
  * every price and quantity that reaches an adapter has ALREADY been rounded
    to the market's tick/step. `RiskDecision.rounded` records that it happened.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Mode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


class Regime(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    PANIC = "PANIC"
    DATA_UNRELIABLE = "DATA_UNRELIABLE"


class HealthState(str, Enum):
    ACTIVE = "ACTIVE"
    THROTTLED = "THROTTLED"
    PAUSED = "PAUSED"
    RECOVERY = "RECOVERY"
    DISABLED = "DISABLED"


class OrderIntent(str, Enum):
    ENTRY = "entry"
    STOP = "stop"
    TAKE_PROFIT = "take_profit"
    FLATTEN = "flatten"


@dataclass(frozen=True)
class MarketMeta:
    """One Lighter perpetual market, as the venue currently describes it.

    `complete` is the gate: a market missing tick size, quantity step, minimum
    size or a max-leverage figure is REFUSED rather than defaulted, because
    every default here is a silent risk decision."""
    symbol: str
    market_id: int
    tick_size: float
    qty_step: float
    min_base_amount: float
    min_quote_amount: float
    max_leverage: float | None
    maintenance_margin_frac: float | None
    initial_margin_frac: float | None
    taker_fee: float | None
    maker_fee: float | None
    daily_quote_volume: float = 0.0
    status: str = "unknown"
    price_decimals: int | None = None
    size_decimals: int | None = None

    @property
    def complete(self) -> bool:
        return all(x is not None and x > 0 for x in
                   (self.tick_size, self.qty_step, self.min_base_amount)) \
            and self.max_leverage is not None \
            and self.maintenance_margin_frac is not None \
            and str(self.status).lower() == "active"

    def missing(self) -> list[str]:
        out = []
        for name in ("tick_size", "qty_step", "min_base_amount"):
            v = getattr(self, name)
            if v is None or v <= 0:
                out.append(name)
        if self.max_leverage is None:
            out.append("max_leverage")
        if self.maintenance_margin_frac is None:
            out.append("maintenance_margin_frac")
        if str(self.status).lower() != "active":
            out.append(f"status={self.status}")
        return out


@dataclass
class Candle:
    ts: int          # UNIX seconds, bar OPEN
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True


@dataclass
class ScoreBreakdown:
    """Every component that produced a score, kept so a rejected signal can
    say WHY. A score with no breakdown is unexplainable and therefore
    untunable."""
    regime: float = 0.0
    trend: float = 0.0
    structure: float = 0.0
    momentum: float = 0.0
    volume: float = 0.0
    derivatives: float = 0.0
    liquidity: float = 0.0

    @property
    def total(self) -> float:
        return round(self.regime + self.trend + self.structure + self.momentum
                     + self.volume + self.derivatives + self.liquidity, 4)

    def as_dict(self) -> dict[str, float]:
        d = asdict(self)
        d["total"] = self.total
        return d


@dataclass
class Signal:
    symbol: str
    side: str                       # "long" | "short"
    strategy: str
    timeframe: str
    candle_ts: int
    setup: str
    score: ScoreBreakdown
    entry: float
    stop: float
    targets: list[float] = field(default_factory=list)
    atr: float = 0.0
    reward_risk: float = 0.0
    regime: Regime = Regime.NEUTRAL
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def signal_id(self) -> str:
        """Deterministic: the same setup on the same closed candle is the same
        signal, so a restart cannot double-enter."""
        return (f"{self.strategy}:{self.symbol}:{self.timeframe}"
                f":{self.candle_ts}:{self.setup}:{self.side}")


@dataclass
class RiskDecision:
    """The answer to 'may we take this, and how big?'. `ok=False` always
    carries a reason; a refusal with no reason is a bug."""
    ok: bool
    reason: str = ""
    quantity: float = 0.0
    notional: float = 0.0
    risk_amount: float = 0.0
    risk_pct_equity: float = 0.0
    leverage: float = 0.0
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    liquidation_price: float | None = None
    stop_to_liq_atr: float | None = None
    est_fees: float = 0.0
    est_funding: float = 0.0
    worst_case_gap_loss: float = 0.0
    rounded: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderRequest:
    """What we INTEND to send. SHADOW mode emits exactly this and stops."""
    symbol: str
    market_id: int
    side: str
    intent: OrderIntent
    order_type: str              # "limit" | "market" | "stop_loss" | ...
    time_in_force: str           # "post_only" | "gtt" | "ioc"
    price: float | None
    trigger_price: float | None
    quantity: float
    reduce_only: bool
    client_order_index: int
    expiry_ms: int | None = None
    signal_id: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["intent"] = self.intent.value
        return d


@dataclass
class OrderResult:
    accepted: bool
    order_id: str | None = None
    tx_hash: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    submitted: bool = False       # False in shadow/dry-run: never sent


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
    realized: float = 0.0
    scaled_out: float = 0.0       # fraction already closed
    stop_order_id: str | None = None
    protective_ok: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def unrealized(self, mark: float) -> float:
        sgn = 1.0 if self.side == "long" else -1.0
        return sgn * (mark - self.entry_price) * self.quantity


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

    @property
    def held_h(self) -> float:
        return max(0.0, (self.closed_ts - self.opened_ts) / 3600.0)


def now() -> float:
    return time.time()


# --------------------------------------------------- filesystem boundary ---
#: Characters a path component may contain. Anything else is replaced, so a
#: separator, a traversal or a NUL can never survive into a filename.
_SAFE_CHARS = set("abcdefghijklmnopqrstuvwxyz"
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def safe_filename(name: str, *, fallback: str = "unnamed",
                  max_len: int = 96) -> str:
    """Reduce an untrusted string to a single, safe path COMPONENT.

    WHY THIS EXISTS, and it is not hypothetical: market symbols are read from
    the venue's own `orderBookDetails` response and were being interpolated
    straight into cache filenames (`f"{symbol}_{tf}.json"`). A venue --
    compromised, buggy, or simply listing a market with an unusual name --
    could therefore choose a path outside the data directory. The tape cache
    is written on every data command, so this is reachable in BACKTEST mode
    with no credentials configured at all.

    The rule is allowlist, not denylist: anything outside `_SAFE_CHARS`
    becomes `_`. A denylist here (strip "..", strip "/") is the version that
    keeps being bypassed, because the interesting inputs are the ones nobody
    listed. Leading dots are stripped so a component can never be `.`, `..`
    or a hidden file, and an empty result becomes `fallback` rather than the
    empty string -- `os.path.join(d, "")` silently yields the DIRECTORY."""
    cleaned = "".join(c if c in _SAFE_CHARS else "_" for c in str(name))
    cleaned = cleaned.lstrip(".")[:max_len]
    return cleaned or fallback


def contained_path(directory: str, *parts: str) -> str:
    """Join `parts` under `directory` and REFUSE to escape it.

    Belt and braces: every part is passed through `safe_filename`, and the
    resolved result is then required to sit inside the resolved directory.
    The second check is what catches a symlink or an unforeseen encoding --
    sanitising and then verifying is cheap, and only one of the two has to
    hold for the write to be safe."""
    import os as _os
    root = _os.path.realpath(directory)
    joined = _os.path.join(root, *[safe_filename(p) for p in parts])
    resolved = _os.path.realpath(joined)
    if resolved != root and not resolved.startswith(root + _os.sep):
        raise ValueError(
            f"refusing to write outside {directory!r}: {joined!r} resolves to "
            f"{resolved!r}")
    return joined
