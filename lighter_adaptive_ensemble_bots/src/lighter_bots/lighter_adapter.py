"""Native Lighter adapter + capability report + a mock for tests.

DESIGN RULE: **never silently emulate.** If the installed SDK cannot place a
reduce-only order, a native stop, or set leverage, the adapter reports that
capability as UNSUPPORTED and the caller refuses live trading for that market.
An emulated stop -- a client-side price watch pretending to be an exchange
order -- dies with the process, and the operator believes they are protected.

Lighter is NOT CCXT-compatible and nothing here pretends otherwise: methods
and constants are resolved from the installed `lighter` package BY NAME, and a
missing name becomes a capability gap rather than an AttributeError at 3am.

SIGNING: `NativeLighterAdapter` takes `allow_signing=False` by default. In
that state it will build and validate every transaction and REFUSE to send
one. `live_trader` is the only caller that passes True, and only after
`config.LiveGate` has allowed it.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any

from .logging_setup import get
from .models import (Candle, Fill, MarketMeta, OrderIntent, OrderRequest,
                     OrderResult, Position)

log = get("adapter")


# --------------------------------------------------------- capabilities -----
CAPABILITIES = (
    "public_market_metadata", "market_id_symbol_mapping", "tick_size",
    "quantity_step", "minimum_order_size", "mark_price", "index_price",
    "order_book", "recent_trades", "ohlcv", "funding_rate", "open_interest",
    "account_equity", "available_collateral", "open_positions",
    "active_orders", "inactive_orders", "fills", "order_create",
    "order_modify", "order_cancel", "batch_transactions", "reduce_only_exits",
    "stop_loss_orders", "take_profit_orders", "post_only", "ioc",
    "good_til_time", "twap", "leverage_config", "margin_mode_config",
    "grouped_orders_oto_oco", "websocket",
)


@dataclass
class Capability:
    name: str
    supported: bool
    via: str = ""
    detail: str = ""


@dataclass
class CapabilityReport:
    sdk_version: str
    base_url: str
    chain_id: int
    capabilities: list[Capability] = field(default_factory=list)
    order_types: dict[str, int] = field(default_factory=dict)
    time_in_force: dict[str, int] = field(default_factory=dict)
    grouping_types: dict[str, int] = field(default_factory=dict)
    margin_modes: dict[str, int] = field(default_factory=dict)
    api_classes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def unsupported(self) -> list[str]:
        return [c.name for c in self.capabilities if not c.supported]

    def supports(self, name: str) -> bool:
        return any(c.name == name and c.supported for c in self.capabilities)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["unsupported"] = self.unsupported()
        return d

    def render(self) -> str:
        w = max(len(c.name) for c in self.capabilities) if self.capabilities else 20
        lines = ["Lighter capability report",
                 f"  lighter-sdk : {self.sdk_version}",
                 f"  base_url    : {self.base_url}",
                 f"  chain_id    : {self.chain_id}",
                 f"  API classes : {len(self.api_classes)}", ""]
        for c in self.capabilities:
            mark = "yes" if c.supported else "NO "
            lines.append(f"  [{mark}] {c.name:<{w}}  {c.via}"
                         + (f"   -- {c.detail}" if c.detail else ""))
        if self.order_types:
            lines += ["", "  order types      : "
                      + ", ".join(f"{k}={v}" for k, v in
                                  sorted(self.order_types.items()))]
        if self.time_in_force:
            lines += ["  time in force    : "
                      + ", ".join(f"{k}={v}" for k, v in
                                  sorted(self.time_in_force.items()))]
        if self.grouping_types:
            lines += ["  grouping types   : "
                      + ", ".join(f"{k}={v}" for k, v in
                                  sorted(self.grouping_types.items()))]
        if self.problems:
            lines += ["", "  PROBLEMS:"] + [f"    - {p}" for p in self.problems]
        return "\n".join(lines)


def _sdk():
    try:
        import lighter  # noqa: PLC0415
        return lighter
    except Exception:                                   # noqa: BLE001
        return None


def _sdk_version(lighter_mod) -> str:
    """The DISTRIBUTION version is authoritative; the module attribute is
    reported beside it when they disagree.

    They do disagree in practice -- lighter-sdk 1.1.2 ships a package whose
    `lighter.__version__` still reads "1.0.0". Reporting only the module
    attribute would understate the installed SDK, and reporting only the
    distribution would hide that the package's own metadata is stale, so the
    report carries both."""
    dist = None
    try:
        from importlib.metadata import version          # noqa: PLC0415
        dist = version("lighter-sdk")
    except Exception:                                   # noqa: BLE001
        dist = None
    attr = None
    for name in ("__version__", "VERSION"):
        v = getattr(lighter_mod, name, None)
        if v:
            attr = str(v)
            break
    if dist and attr and dist != attr:
        return f"{dist} (dist) / {attr} (lighter.__version__)"
    return dist or attr or "unknown"


def build_capability_report(base_url: str, chain_id: int) -> CapabilityReport:
    """Inspect the INSTALLED SDK. Everything is resolved by name so an SDK
    upgrade that renames a method degrades to a reported gap."""
    mod = _sdk()
    if mod is None:
        return CapabilityReport("not installed", base_url, chain_id,
                                [Capability(n, False, "", "lighter-sdk missing")
                                 for n in CAPABILITIES],
                                problems=["lighter-sdk is not importable"])
    ver = _sdk_version(mod)
    signer = getattr(mod, "SignerClient", None)
    apis = [n for n in dir(mod) if n.endswith("Api")]

    def const(name: str):
        return getattr(signer, name, None) if signer is not None else None

    def has(name: str) -> bool:
        return signer is not None and callable(getattr(signer, name, None))

    order_types = {k: const(v) for k, v in (
        ("limit", "ORDER_TYPE_LIMIT"), ("market", "ORDER_TYPE_MARKET"),
        ("stop_loss", "ORDER_TYPE_STOP_LOSS"),
        ("stop_loss_limit", "ORDER_TYPE_STOP_LOSS_LIMIT"),
        ("take_profit", "ORDER_TYPE_TAKE_PROFIT"),
        ("take_profit_limit", "ORDER_TYPE_TAKE_PROFIT_LIMIT"),
        ("twap", "ORDER_TYPE_TWAP")) if const(v) is not None}
    tifs = {k: const(v) for k, v in (
        ("ioc", "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL"),
        ("gtt", "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME"),
        ("post_only", "ORDER_TIME_IN_FORCE_POST_ONLY")) if const(v) is not None}
    groups = {k: const(v) for k, v in (
        ("oto", "GROUPING_TYPE_ONE_TRIGGERS_THE_OTHER"),
        ("oco", "GROUPING_TYPE_ONE_CANCELS_THE_OTHER"),
        ("otoco", "GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER"))
        if const(v) is not None}
    margins = {k: const(v) for k, v in (
        ("cross", "CROSS_MARGIN_MODE"), ("isolated", "ISOLATED_MARGIN_MODE"))
        if const(v) is not None}

    reduce_only = False
    if has("create_order"):
        try:
            import inspect                              # noqa: PLC0415
            reduce_only = "reduce_only" in inspect.signature(
                signer.create_order).parameters
        except Exception:                               # noqa: BLE001
            reduce_only = False

    caps = [
        Capability("public_market_metadata", True, "REST /api/v1/orderBookDetails"),
        Capability("market_id_symbol_mapping", True, "orderBookDetails.symbol/market_id"),
        Capability("tick_size", True, "derived from price_decimals"),
        Capability("quantity_step", True, "derived from size_decimals"),
        Capability("minimum_order_size", True, "min_base_amount / min_quote_amount"),
        Capability("mark_price", True, "orderBookDetails.mark_price"),
        Capability("index_price", True, "orderBookDetails.index_price"),
        Capability("order_book", "OrderApi" in apis, "OrderApi"),
        Capability("recent_trades", "OrderApi" in apis, "OrderApi.trades"),
        Capability("ohlcv", "CandlestickApi" in apis,
                   "CandlestickApi / REST /api/v1/candles"),
        Capability("funding_rate", "FundingApi" in apis,
                   "FundingApi / REST /api/v1/fundings",
                   "settled series is quoted in PERCENT PER HOUR"),
        Capability("open_interest", True, "orderBookDetails.open_interest"),
        Capability("account_equity", "AccountApi" in apis, "AccountApi"),
        Capability("available_collateral", "AccountApi" in apis, "AccountApi"),
        Capability("open_positions", "AccountApi" in apis, "AccountApi.account"),
        Capability("active_orders", "OrderApi" in apis, "OrderApi.account_active_orders"),
        Capability("inactive_orders", "OrderApi" in apis, "OrderApi.account_inactive_orders"),
        Capability("fills", "OrderApi" in apis, "OrderApi.trades"),
        Capability("order_create", has("create_order"), "SignerClient.create_order"),
        Capability("order_modify", has("modify_order"), "SignerClient.modify_order"),
        Capability("order_cancel", has("cancel_order"), "SignerClient.cancel_order"),
        Capability("batch_transactions", has("send_tx_batch"), "SignerClient.send_tx_batch"),
        Capability("reduce_only_exits", reduce_only, "create_order(reduce_only=)"),
        Capability("stop_loss_orders", has("create_sl_order"),
                   "SignerClient.create_sl_order / create_sl_limit_order"),
        Capability("take_profit_orders", has("create_tp_order"),
                   "SignerClient.create_tp_order / create_tp_limit_order"),
        Capability("post_only", "post_only" in tifs, "ORDER_TIME_IN_FORCE_POST_ONLY"),
        Capability("ioc", "ioc" in tifs, "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL"),
        Capability("good_til_time", "gtt" in tifs, "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME"),
        Capability("twap", "twap" in order_types, "ORDER_TYPE_TWAP",
                   "constant exposed; not used by this system"),
        Capability("leverage_config", has("update_leverage"), "SignerClient.update_leverage"),
        Capability("margin_mode_config", bool(margins),
                   "CROSS_MARGIN_MODE / ISOLATED_MARGIN_MODE"),
        Capability("grouped_orders_oto_oco", has("create_grouped_orders") and "otoco" in groups,
                   "SignerClient.create_grouped_orders",
                   "entry + stop + target as ONE transaction"),
        Capability("websocket", getattr(mod, "WsClient", None) is not None, "lighter.WsClient"),
    ]
    problems = []
    for critical in ("order_create", "order_cancel", "stop_loss_orders",
                     "reduce_only_exits"):
        if not any(c.name == critical and c.supported for c in caps):
            problems.append(f"{critical} is UNSUPPORTED: live trading must be "
                            "refused until this resolves")
    return CapabilityReport(ver, base_url, chain_id, caps, order_types, tifs,
                            groups, margins, apis, problems)


# ------------------------------------------------------------- base class ---
@dataclass
class AccountSnapshot:
    equity: float
    available_collateral: float
    margin_used: float
    total_maintenance: float
    positions: list[Position] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    fetched_at: float = 0.0


class AdapterError(RuntimeError):
    pass


class BaseAdapter:
    """The interface. Every method either returns validated data or RAISES."""

    def markets(self) -> list[MarketMeta]: raise NotImplementedError
    def mark_price(self, symbol: str) -> float: raise NotImplementedError
    def order_book(self, symbol: str) -> dict[str, Any]: raise NotImplementedError
    def candles(self, symbol: str, tf: str, pages: int = 4) -> list[Candle]:
        raise NotImplementedError
    def funding_rate(self, symbol: str) -> float | None: raise NotImplementedError
    def account(self) -> AccountSnapshot: raise NotImplementedError
    def active_orders(self) -> list[dict[str, Any]]: raise NotImplementedError
    def fills(self, since: float = 0.0) -> list[Fill]: raise NotImplementedError
    def submit(self, req: OrderRequest) -> OrderResult: raise NotImplementedError
    def submit_grouped(self, reqs: list[OrderRequest]) -> OrderResult:
        raise NotImplementedError
    def cancel(self, symbol: str, order_id: str) -> OrderResult:
        raise NotImplementedError
    def set_leverage(self, symbol: str, leverage: float,
                     margin_mode: str) -> OrderResult:
        raise NotImplementedError


# -------------------------------------------------------------- read-only ---
def _http_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "lighter-bots/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class TokenBucket:
    """Endpoint-agnostic limiter. Lighter publishes per-endpoint limits; this
    keeps us well under them and, critically, is NEVER applied to a signed
    order retry -- a retried signed order can execute twice."""

    def __init__(self, rate_per_s: float = 5.0, burst: int = 10):
        self.rate, self.capacity = rate_per_s, float(burst)
        self.tokens, self.updated = float(burst), time.monotonic()

    def take(self, n: float = 1.0) -> None:
        while True:
            now = time.monotonic()
            self.tokens = min(self.capacity,
                              self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens >= n:
                self.tokens -= n
                return
            time.sleep(max(0.01, (n - self.tokens) / max(self.rate, 1e-9)))


class NativeLighterAdapter(BaseAdapter):
    """REST reads + SDK writes. `allow_signing=False` builds and refuses."""

    def __init__(self, base_url: str, chain_id: int = 304, *,
                 account_index: int | None = None,
                 api_key_index: int | None = None,
                 signer: Any | None = None, allow_signing: bool = False,
                 nonce_manager: Any | None = None,
                 rate: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.chain_id = int(chain_id)
        self.account_index = account_index
        self.api_key_index = api_key_index
        self.signer = signer
        self.allow_signing = bool(allow_signing)
        self.nonces = nonce_manager
        self.bucket = TokenBucket(rate)
        self.report = build_capability_report(self.base_url, self.chain_id)
        self._markets: dict[str, MarketMeta] = {}

    # -- reads ------------------------------------------------------------
    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        self.bucket.take()
        q = ("?" + urllib.parse.urlencode(params)) if params else ""
        return _http_json(f"{self.base_url}{path}{q}")

    def markets(self) -> list[MarketMeta]:
        from .market_metadata import parse_market      # noqa: PLC0415
        doc = self._get("/api/v1/orderBookDetails")
        rows = doc.get("order_book_details") or []
        if not rows:
            raise AdapterError("no market metadata returned")
        out = [parse_market(r) for r in rows
               if str(r.get("market_type", "perp")) == "perp"]
        self._markets = {m.symbol: m for m in out}
        return out

    def _detail(self, symbol: str) -> dict[str, Any]:
        doc = self._get("/api/v1/orderBookDetails")
        for r in doc.get("order_book_details") or []:
            if r.get("symbol") == symbol:
                return r
        raise AdapterError(f"{symbol}: not listed")

    def mark_price(self, symbol: str) -> float:
        px = float(self._detail(symbol).get("mark_price") or 0.0)
        if px <= 0:
            raise AdapterError(f"{symbol}: mark price unusable ({px})")
        return px

    def index_price(self, symbol: str) -> float:
        return float(self._detail(symbol).get("index_price") or 0.0)

    def open_interest(self, symbol: str) -> float | None:
        v = self._detail(symbol).get("open_interest")
        return None if v is None else float(v)

    def order_book(self, symbol: str) -> dict[str, Any]:
        mid = self._markets.get(symbol)
        if mid is None:
            self.markets()
            mid = self._markets.get(symbol)
        if mid is None:
            raise AdapterError(f"{symbol}: unknown market")
        return self._get("/api/v1/orderBookOrders", market_id=mid.market_id,
                         limit=25)

    def best_bid_ask(self, symbol: str) -> tuple[float | None, float | None]:
        try:
            ob = self.order_book(symbol)
        except Exception as exc:                        # noqa: BLE001
            log.warning("order book unavailable for %s: %s", symbol, exc)
            return None, None
        bids = ob.get("bids") or []
        asks = ob.get("asks") or []
        bid = float(bids[0]["price"]) if bids else None
        ask = float(asks[0]["price"]) if asks else None
        return bid, ask

    def candles(self, symbol: str, tf: str, pages: int = 4) -> list[Candle]:
        from .data import CandleSource                  # noqa: PLC0415
        m = self._markets.get(symbol)
        if m is None:
            self.markets()
            m = self._markets.get(symbol)
        if m is None:
            raise AdapterError(f"{symbol}: unknown market")
        src = CandleSource(self.base_url, os.environ.get(
            "LIGHTER_BOTS_DATA_DIR", "data"))
        # `get`, not `fetch`: the cache is skipped only when the stored series
        # is more than one bar stale. A live loop polling every 60s must not
        # re-pull the same closed 1h candles every cycle -- that is how a
        # client earns the venue's rate limiter (which answers with a 405
        # that looks like a permanent method error).
        return src.get(m.symbol, m.market_id, tf, pages=pages)

    def funding_rate(self, symbol: str) -> float | None:
        m = self._markets.get(symbol) or (self.markets() and
                                          self._markets.get(symbol))
        if m is None:
            return None
        try:
            doc = self._get("/api/v1/fundings", market_id=m.market_id,
                            resolution="1h", start_timestamp=0,
                            end_timestamp=int(time.time()), count_back=1)
        except Exception:                               # noqa: BLE001
            return None
        rows = doc.get("fundings") or []
        if not rows:
            return None
        # THE UNIT TRAP: the settled series is PERCENT PER HOUR.
        return float(rows[-1].get("rate") or 0.0) / 100.0

    def account(self) -> AccountSnapshot:
        if self.account_index is None:
            raise AdapterError("LIGHTER_ACCOUNT_INDEX is not configured; "
                               "cannot read account state")
        doc = self._get("/api/v1/account", by="index",
                        value=str(self.account_index))
        accounts = doc.get("accounts") or []
        if not accounts:
            raise AdapterError("account query returned no rows")
        a = accounts[0]
        positions = []
        for p in a.get("positions") or []:
            size = float(p.get("position") or 0.0)
            if size == 0:
                continue
            sym = p.get("symbol") or ""
            positions.append(Position(
                symbol=sym, side="long" if size > 0 else "short",
                quantity=abs(size),
                entry_price=float(p.get("avg_entry_price") or 0.0),
                opened_ts=0.0, stop_price=0.0, meta={"venue": p}))
        return AccountSnapshot(
            equity=float(a.get("total_asset_value") or 0.0),
            available_collateral=float(a.get("available_balance")
                                       or a.get("collateral") or 0.0),
            margin_used=float(a.get("total_position_margin") or 0.0),
            total_maintenance=float(a.get("total_maintenance_margin") or 0.0),
            positions=positions, raw=a, fetched_at=time.time())

    def active_orders(self) -> list[dict[str, Any]]:
        if self.account_index is None:
            raise AdapterError("account index not configured")
        doc = self._get("/api/v1/accountActiveOrders",
                        account_index=self.account_index)
        return list(doc.get("orders") or [])

    def fills(self, since: float = 0.0) -> list[Fill]:
        if self.account_index is None:
            raise AdapterError("account index not configured")
        doc = self._get("/api/v1/trades", account_index=self.account_index,
                        limit=100)
        out = []
        for t in doc.get("trades") or []:
            ts = float(t.get("timestamp") or 0.0) / 1000.0
            if ts < since:
                continue
            out.append(Fill(symbol=str(t.get("symbol") or ""),
                            side="short" if t.get("is_ask") else "long",
                            quantity=float(t.get("size") or 0.0),
                            price=float(t.get("price") or 0.0), ts=ts,
                            order_id=str(t.get("order_index") or "")))
        return out

    # -- writes -----------------------------------------------------------
    def _refuse(self, what: str) -> OrderResult:
        return OrderResult(accepted=False, submitted=False,
                           error=f"signing disabled: refusing to {what}. "
                                 "This adapter was constructed with "
                                 "allow_signing=False.")

    def _map(self, req: OrderRequest) -> dict[str, Any]:
        """OrderRequest -> SDK kwargs. Raises when a needed capability is
        missing rather than substituting a weaker order."""
        from .execution import ORDER_TYPE, TIME_IN_FORCE, side_to_is_ask
        r = self.report
        if req.reduce_only and not r.supports("reduce_only_exits"):
            raise AdapterError("reduce-only is unsupported by this SDK; "
                               "refusing to send a non-reduce-only exit")
        if req.intent is OrderIntent.STOP and not r.supports("stop_loss_orders"):
            raise AdapterError("native stop-loss orders unsupported; refusing "
                               "to emulate a stop client-side")
        ot_name = ORDER_TYPE.get(req.order_type)
        tif_name = TIME_IN_FORCE.get(req.time_in_force)
        if ot_name is None or tif_name is None:
            raise AdapterError(f"unmapped order type/tif "
                               f"{req.order_type}/{req.time_in_force}")
        signer_cls = getattr(_sdk(), "SignerClient", None)
        ot = getattr(signer_cls, ot_name, None)
        tif = getattr(signer_cls, tif_name, None)
        if ot is None or tif is None:
            raise AdapterError(f"SDK does not expose {ot_name}/{tif_name}")
        m = self._markets.get(req.symbol) or (self.markets()
                                              and self._markets[req.symbol])
        base = int(round(req.quantity / m.qty_step)) if m.qty_step else 0
        price = int(round((req.price or 0.0) / m.tick_size)) if m.tick_size else 0
        trig = int(round((req.trigger_price or 0.0) / m.tick_size)) \
            if m.tick_size else 0
        return {"market_index": req.market_id,
                "client_order_index": req.client_order_index,
                "base_amount": base, "price": price, "is_ask":
                side_to_is_ask(req.side), "order_type": ot,
                "time_in_force": tif, "reduce_only": req.reduce_only,
                "trigger_price": trig,
                "order_expiry": int(req.expiry_ms or -1)}

    def submit(self, req: OrderRequest) -> OrderResult:
        kwargs = self._map(req)              # validates capabilities first
        if not self.allow_signing or self.signer is None:
            return self._refuse(f"submit {req.intent.value} for {req.symbol}")
        if self.nonces is None:
            return OrderResult(False, error="no nonce manager: refusing to sign")
        with self.nonces.reserve(self.account_index, self.api_key_index) as n:
            kwargs["nonce"] = n
            tx, tx_hash, err = self.signer.create_order(**kwargs)
            if err:
                raise AdapterError(f"order rejected: {err}")
            return OrderResult(True, order_id=str(
                getattr(tx, "order_index", req.client_order_index)),
                tx_hash=str(tx_hash), submitted=True, raw={"tx": str(tx)})

    def submit_grouped(self, reqs: list[OrderRequest]) -> OrderResult:
        if not self.report.supports("grouped_orders_oto_oco"):
            return OrderResult(False, error="grouped orders unsupported")
        for r in reqs:
            self._map(r)
        if not self.allow_signing or self.signer is None:
            return self._refuse(f"submit a grouped transaction of {len(reqs)} "
                                "orders")
        return OrderResult(False, error="grouped submission requires a "
                                        "configured signer")

    def cancel(self, symbol: str, order_id: str) -> OrderResult:
        if not self.allow_signing or self.signer is None:
            return self._refuse(f"cancel {order_id} on {symbol}")
        m = self._markets.get(symbol)
        if m is None:
            return OrderResult(False, error=f"{symbol}: unknown market")
        with self.nonces.reserve(self.account_index, self.api_key_index) as n:
            _tx, tx_hash, err = self.signer.cancel_order(
                market_index=m.market_id, order_index=int(order_id), nonce=n)
            if err:
                return OrderResult(False, error=str(err))
            return OrderResult(True, tx_hash=str(tx_hash), submitted=True)

    def set_leverage(self, symbol: str, leverage: float,
                     margin_mode: str = "isolated") -> OrderResult:
        if not self.report.supports("leverage_config"):
            return OrderResult(False, error="leverage config unsupported by SDK")
        if not self.allow_signing or self.signer is None:
            return self._refuse(f"set {symbol} leverage to {leverage}x")
        m = self._markets.get(symbol)
        signer_cls = getattr(_sdk(), "SignerClient", None)
        mode = getattr(signer_cls, "ISOLATED_MARGIN_MODE" if margin_mode ==
                       "isolated" else "CROSS_MARGIN_MODE")
        with self.nonces.reserve(self.account_index, self.api_key_index) as n:
            _tx, tx_hash, err = self.signer.update_leverage(
                market_index=m.market_id, margin_mode=mode,
                leverage=int(leverage), nonce=n)
            if err:
                return OrderResult(False, error=str(err))
            return OrderResult(True, tx_hash=str(tx_hash), submitted=True)


# ------------------------------------------------------------------- mock ---
class MockLighterAdapter(BaseAdapter):
    """Deterministic adapter for tests and backtests. Signs nothing, ever."""

    def __init__(self, markets: list[MarketMeta] | None = None,
                 candles: dict[tuple[str, str], list[Candle]] | None = None,
                 equity: float = 10_000.0):
        self._markets = {m.symbol: m for m in (markets or [])}
        self._candles = candles or {}
        self._equity = equity
        self.submitted: list[OrderRequest] = []
        self.cancelled: list[tuple[str, str]] = []
        self.leverage_calls: list[tuple[str, float, str]] = []
        self.marks: dict[str, float] = {}
        self.fail_next: str | None = None
        self.report = CapabilityReport(
            "mock", "mock://lighter", 304,
            [Capability(n, True, "mock") for n in CAPABILITIES])

    def markets(self) -> list[MarketMeta]:
        return list(self._markets.values())

    def mark_price(self, symbol: str) -> float:
        if symbol in self.marks:
            return self.marks[symbol]
        for (s, _tf), cs in self._candles.items():
            if s == symbol and cs:
                return cs[-1].close
        raise AdapterError(f"{symbol}: no mark")

    def order_book(self, symbol: str) -> dict[str, Any]:
        px = self.mark_price(symbol)
        return {"bids": [{"price": px * 0.9999, "size": 100}],
                "asks": [{"price": px * 1.0001, "size": 100}]}

    def best_bid_ask(self, symbol: str) -> tuple[float | None, float | None]:
        ob = self.order_book(symbol)
        return ob["bids"][0]["price"], ob["asks"][0]["price"]

    def candles(self, symbol: str, tf: str, pages: int = 4) -> list[Candle]:
        return list(self._candles.get((symbol, tf), []))

    def funding_rate(self, symbol: str) -> float | None:
        return 0.0

    def open_interest(self, symbol: str) -> float | None:
        return 1_000_000.0

    def account(self) -> AccountSnapshot:
        return AccountSnapshot(self._equity, self._equity, 0.0, 0.0,
                               fetched_at=time.time())

    def active_orders(self) -> list[dict[str, Any]]:
        return []

    def fills(self, since: float = 0.0) -> list[Fill]:
        return []

    def submit(self, req: OrderRequest) -> OrderResult:
        if self.fail_next:
            err, self.fail_next = self.fail_next, None
            return OrderResult(False, error=err)
        self.submitted.append(req)
        return OrderResult(True, order_id=f"mock-{len(self.submitted)}",
                           submitted=True)

    def submit_grouped(self, reqs: list[OrderRequest]) -> OrderResult:
        for r in reqs:
            self.submitted.append(r)
        return OrderResult(True, order_id=f"mock-group-{len(self.submitted)}",
                           submitted=True)

    def cancel(self, symbol: str, order_id: str) -> OrderResult:
        self.cancelled.append((symbol, order_id))
        return OrderResult(True, submitted=True)

    def set_leverage(self, symbol: str, leverage: float,
                     margin_mode: str = "isolated") -> OrderResult:
        self.leverage_calls.append((symbol, leverage, margin_mode))
        return OrderResult(True, submitted=True)
