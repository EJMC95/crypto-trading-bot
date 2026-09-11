"""The exchange boundary: an abstract interface, a deterministic mock, and a
REAL adapter that is scaffolded and DISABLED.

DESIGN RULE: **never silently emulate.** If an exchange cannot place a
reduce-only order or a native stop, the adapter reports that capability as
unsupported and the caller refuses live trading for that market. An emulated
stop -- a client-side price watch pretending to be an exchange order -- dies
with the process, and the operator believes they are protected.

The real adapter is `CcxtAdapter`. It is:
  * NOT imported at module load (ccxt is an optional extra);
  * constructed with `allow_submit=False` by default, so it builds and
    validates every order and REFUSES to send one;
  * marked with TODO at each place a specific exchange's quirks must be
    verified before that changes.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Sequence

from .logging_setup import get
from .models import Candle, Market, OrderRequest, OrderResult, Position

log = get("exchange")


class ExchangeError(RuntimeError):
    pass


class NotSupported(ExchangeError):
    """Raised instead of substituting a weaker order."""


@dataclass
class Balance:
    equity: float
    free: float
    used: float = 0.0
    currency: str = "USDT"


@dataclass
class Ticker:
    symbol: str
    last: float
    bid: float | None = None
    ask: float | None = None
    mark: float | None = None
    index: float | None = None
    quote_volume_24h: float = 0.0
    ts: float = 0.0

    @property
    def spread_bps(self) -> float | None:
        if not self.bid or not self.ask or self.bid <= 0 or self.ask <= 0:
            return None
        mid = 0.5 * (self.bid + self.ask)
        return None if mid <= 0 else 10_000.0 * (self.ask - self.bid) / mid


#: THE CAPABILITY VOCABULARY, in one place. A capability name is a string, and
#: a misspelled string returns False from a naive `.get()` -- so a caller that
#: asks for `place_reduce_only_stop` against an adapter that publishes
#: `native_stop` gets a silent, permanent "not supported".
#:
#: MEASURED, not hypothetical: that exact mismatch made `build_plan` stamp
#: "WARNING: the adapter reports NO native stop" on EVERY plan, including from
#: the mock adapter that fully supports one, and closed the live gate's
#: `protective_exit_capability` lock against an adapter that would have passed
#: it. A warning that fires on everything is a warning the operator learns to
#: ignore -- which is how the real one gets missed.
#:
#: `capability()` now REFUSES an unknown name rather than answering False.
CAPABILITIES = ("reduce_only", "native_stop", "native_take_profit",
                "post_only", "set_leverage", "funding_rate", "open_interest",
                "cancel_all")


class ExchangeAdapter:
    """The interface. Every method returns validated data or RAISES."""

    name = "abstract"
    #: Capabilities a caller may not assume. A False here must reach the live
    #: gate, not be worked around.
    supports: dict[str, bool] = {}

    def fetch_markets(self) -> list[Market]: raise NotImplementedError
    def fetch_ohlcv(self, symbol: str, timeframe: str,
                    limit: int = 500) -> list[Candle]: raise NotImplementedError
    def fetch_ticker(self, symbol: str) -> Ticker: raise NotImplementedError
    def fetch_order_book(self, symbol: str,
                         depth: int = 20) -> dict[str, Any]: raise NotImplementedError
    def fetch_funding_rate(self, symbol: str) -> float | None:
        raise NotImplementedError
    def fetch_open_interest(self, symbol: str) -> float | None:
        raise NotImplementedError
    def fetch_balance(self) -> Balance: raise NotImplementedError
    def fetch_positions(self) -> list[Position]: raise NotImplementedError
    def create_order(self, req: OrderRequest) -> OrderResult:
        raise NotImplementedError
    def cancel_order(self, symbol: str, order_id: str) -> OrderResult:
        raise NotImplementedError
    def cancel_all_orders(self, symbol: str | None = None) -> list[OrderResult]:
        raise NotImplementedError
    def set_leverage(self, symbol: str, leverage: float) -> OrderResult:
        raise NotImplementedError
    def place_reduce_only_stop(self, symbol: str, side: str, qty: float,
                               trigger: float) -> OrderResult:
        raise NotImplementedError
    def place_reduce_only_take_profit(self, symbol: str, side: str, qty: float,
                                      trigger: float) -> OrderResult:
        raise NotImplementedError

    # ------------------------------------------------------------- helpers --
    def capability(self, name: str) -> bool:
        if name not in CAPABILITIES:
            raise KeyError(
                f"{name!r} is not a capability. Known: {', '.join(CAPABILITIES)}"
                ". A misspelled capability answers False forever, which reads "
                "exactly like an unsupported venue.")
        return bool(self.supports.get(name, False))

    def require(self, *names: str) -> None:
        missing = [n for n in names if not self.capability(n)]
        if missing:
            raise NotSupported(
                f"{self.name}: {', '.join(missing)} unsupported. Refusing to "
                "emulate; live trading for this market must be refused.")


# ------------------------------------------------------------------- mock ---
class MockExchange(ExchangeAdapter):
    """Deterministic adapter for tests and backtests. Submits nothing, ever.

    `fail_next` / `stale_after` / `partial_fill` let a test drive the failure
    paths that matter: a rejected order, a stale feed, a partial fill."""

    name = "mock"
    supports = {"reduce_only": True, "native_stop": True,
                "native_take_profit": True, "post_only": True,
                "set_leverage": True, "funding_rate": True,
                "open_interest": True, "cancel_all": True}

    def __init__(self, markets: Sequence[Market] = (),
                 candles: dict[tuple[str, str], list[Candle]] | None = None,
                 equity: float = 10_000.0, seed: int = 7):
        self._markets = {m.symbol: m for m in markets}
        self._candles = dict(candles or {})
        self._equity = equity
        self._positions: dict[str, Position] = {}
        self.submitted: list[OrderRequest] = []
        self.cancelled: list[tuple[str, str]] = []
        self.leverage_calls: list[tuple[str, float]] = []
        self.marks: dict[str, float] = {}
        self.funding: dict[str, float] = {}
        self.open_interest: dict[str, float] = {}
        self.spread_bps: float = 2.0
        self.fail_next: str | None = None
        self.stale_after: float | None = None
        self.partial_fill: float | None = None
        self.rng = random.Random(seed)

    # -- reads -------------------------------------------------------------
    def fetch_markets(self) -> list[Market]:
        return list(self._markets.values())

    def fetch_ohlcv(self, symbol: str, timeframe: str,
                    limit: int = 500) -> list[Candle]:
        return list(self._candles.get((symbol, timeframe), []))[-limit:]

    def _price(self, symbol: str) -> float:
        if symbol in self.marks:
            return self.marks[symbol]
        for (s, _tf), cs in self._candles.items():
            if s == symbol and cs:
                return cs[-1].close
        raise ExchangeError(f"{symbol}: no price")

    def fetch_ticker(self, symbol: str) -> Ticker:
        px = self._price(symbol)
        half = px * (self.spread_bps / 2.0) / 10_000.0
        ts = self.stale_after if self.stale_after is not None else time.time()
        m = self._markets.get(symbol)
        return Ticker(symbol=symbol, last=px, bid=px - half, ask=px + half,
                      mark=px, index=px,
                      quote_volume_24h=(m.quote_volume_24h if m else 0.0),
                      ts=ts)

    def fetch_order_book(self, symbol: str, depth: int = 20) -> dict[str, Any]:
        px = self._price(symbol)
        half = px * (self.spread_bps / 2.0) / 10_000.0
        return {"bids": [[px - half, 50.0] for _ in range(depth)],
                "asks": [[px + half, 50.0] for _ in range(depth)]}

    def fetch_funding_rate(self, symbol: str) -> float | None:
        return self.funding.get(symbol, 0.0001)

    def fetch_open_interest(self, symbol: str) -> float | None:
        return self.open_interest.get(symbol, 1_000_000.0)

    def fetch_balance(self) -> Balance:
        return Balance(equity=self._equity, free=self._equity)

    def fetch_positions(self) -> list[Position]:
        return list(self._positions.values())

    # -- writes ------------------------------------------------------------
    def create_order(self, req: OrderRequest) -> OrderResult:
        if self.fail_next:
            err, self.fail_next = self.fail_next, None
            return OrderResult(False, error=err, submitted=False)
        if req.reduce_only:
            self.require("reduce_only")
        self.submitted.append(req)
        filled = req.quantity
        partial = False
        if self.partial_fill is not None:
            filled = req.quantity * self.partial_fill
            partial = filled < req.quantity
        return OrderResult(True, order_id=f"mock-{len(self.submitted)}",
                           status="closed" if not partial else "open",
                           filled=filled, avg_price=req.price or self._price(
                               req.symbol), submitted=True,
                           raw={"partial": partial})

    def cancel_order(self, symbol: str, order_id: str) -> OrderResult:
        self.cancelled.append((symbol, order_id))
        return OrderResult(True, order_id=order_id, status="canceled",
                           submitted=True)

    def cancel_all_orders(self, symbol: str | None = None) -> list[OrderResult]:
        self.require("cancel_all")
        self.cancelled.append((symbol or "*", "all"))
        return [OrderResult(True, status="canceled", submitted=True)]

    def set_leverage(self, symbol: str, leverage: float) -> OrderResult:
        self.require("set_leverage")
        self.leverage_calls.append((symbol, leverage))
        return OrderResult(True, submitted=True)

    def place_reduce_only_stop(self, symbol: str, side: str, qty: float,
                               trigger: float) -> OrderResult:
        self.require("native_stop", "reduce_only")
        return OrderResult(True, order_id=f"stop-{symbol}", submitted=True)

    def place_reduce_only_take_profit(self, symbol: str, side: str, qty: float,
                                      trigger: float) -> OrderResult:
        self.require("native_take_profit", "reduce_only")
        return OrderResult(True, order_id=f"tp-{symbol}", submitted=True)


# ------------------------------------------------------------------- real ---
class CcxtAdapter(ExchangeAdapter):
    """Scaffold for a real exchange. SUBMITS NOTHING by default.

    `allow_submit=False` is the shipped state: every write path builds and
    validates the request, logs the INTENT, and returns a refusal. Flipping it
    is a deliberate code change, which is the last safeguard after the live
    gate's own conditions are satisfied.

    TODO(exchange): before `allow_submit=True` on any venue, VERIFY on that
    venue's testnet, and record the result in the README:
      * that reduce-only is honoured on the exit path (not silently dropped);
      * that a native stop survives a disconnect and is not client-side;
      * the exact symbol format and contract sizing (linear vs inverse);
      * whether `set_leverage` is per-symbol, per-account or unsupported;
      * the real tick/step/min-notional, and that rounding matches;
      * rate limits, and which endpoints share a bucket;
      * whether a retried create_order can DUPLICATE (idempotency keys).
    """

    name = "ccxt"
    supports = {"reduce_only": False, "native_stop": False,
                "native_take_profit": False, "post_only": False,
                "set_leverage": False, "funding_rate": False,
                "open_interest": False, "cancel_all": False}

    def __init__(self, exchange_id: str, *, allow_submit: bool = False,
                 credentials: dict[str, str] | None = None,
                 sandbox: bool = True):
        self.exchange_id = exchange_id
        self.allow_submit = bool(allow_submit)
        self.sandbox = bool(sandbox)
        self._client: Any | None = None
        self._creds = dict(credentials or {})
        self.name = f"ccxt:{exchange_id}"

    def connect(self) -> None:
        try:
            import ccxt                                   # noqa: PLC0415
        except ImportError as exc:                        # pragma: no cover
            raise ExchangeError(
                "ccxt is not installed. It is an OPTIONAL extra: "
                "pip install 'downtrend-ensemble-bot[exchange]'. The system "
                "backtests and paper trades without it.") from exc
        klass = getattr(ccxt, self.exchange_id, None)
        if klass is None:
            raise ExchangeError(f"ccxt has no exchange {self.exchange_id!r}")
        self._client = klass({
            "apiKey": self._creds.get("apiKey"),
            "secret": self._creds.get("secret"),
            "password": self._creds.get("password"),
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
        if self.sandbox and hasattr(self._client, "set_sandbox_mode"):
            self._client.set_sandbox_mode(True)
        # Capabilities are READ from the venue, never assumed.
        has = getattr(self._client, "has", {}) or {}
        self.supports = {
            "reduce_only": bool(has.get("createReduceOnlyOrder", False)
                                or has.get("createOrder", False)),
            "native_stop": bool(has.get("createStopOrder", False)
                                or has.get("createStopLossOrder", False)),
            "native_take_profit": bool(has.get("createTakeProfitOrder", False)),
            "post_only": bool(has.get("createPostOnlyOrder", False)),
            "set_leverage": bool(has.get("setLeverage", False)),
            "funding_rate": bool(has.get("fetchFundingRate", False)),
            "open_interest": bool(has.get("fetchOpenInterest", False)),
            "cancel_all": bool(has.get("cancelAllOrders", False)),
        }

    def _refuse(self, what: str) -> OrderResult:
        log.warning("REFUSING to %s: adapter constructed with "
                    "allow_submit=False", what)
        return OrderResult(False, submitted=False,
                           error=f"submission disabled: refusing to {what}")

    def create_order(self, req: OrderRequest) -> OrderResult:
        if req.reduce_only:
            self.require("reduce_only")
        if not self.allow_submit or self._client is None:
            return self._refuse(f"submit {req.intent.value} for {req.symbol}")
        raise NotSupported(                                # pragma: no cover
            "TODO(exchange): implement and TESTNET-VERIFY order submission "
            "for this venue before enabling it.")

    def cancel_order(self, symbol: str, order_id: str) -> OrderResult:
        if not self.allow_submit or self._client is None:
            return self._refuse(f"cancel {order_id} on {symbol}")
        raise NotSupported("TODO(exchange): implement cancel for this venue.")

    def set_leverage(self, symbol: str, leverage: float) -> OrderResult:
        self.require("set_leverage")
        if not self.allow_submit or self._client is None:
            return self._refuse(f"set {symbol} leverage to {leverage}x")
        raise NotSupported("TODO(exchange): implement set_leverage.")
