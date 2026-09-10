"""Lighter market discovery, parsing and versioned snapshots.

NOTHING here is hardcoded per symbol. Market IDs, tick size, quantity step,
minimum order size, max leverage and margin fractions are read from the venue
every startup and snapshotted with a content hash, so a change in Lighter's
own numbers is visible as a metadata VERSION change rather than as a silent
shift in what a 'valid' order is.

THE UNIT TRAP, recorded because it inverts a risk number by ~4x. Lighter
quotes the margin fractions in BASIS POINTS:

    maintenance_margin_fraction: 120      ->  1.20%
    min_initial_margin_fraction: 200      ->  2.00%  -> max leverage 50x
    default_initial_margin_fraction: 500  ->  5.00%  -> account default 20x

Maintenance margin is READ, never derived from the initial fraction. They are
different numbers with different jobs and the ratio between them is not fixed
across markets.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from dataclasses import asdict
from typing import Any, Iterable

from .logging_setup import get
from .models import MarketMeta, contained_path

log = get("market_metadata")

BPS = 10_000.0
_ENDPOINT = "/api/v1/orderBookDetails"


def _http_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "lighter-bots/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _f(row: dict[str, Any], key: str) -> float | None:
    v = row.get(key)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def parse_market(row: dict[str, Any]) -> MarketMeta:
    """One venue row -> MarketMeta. Anything unreadable stays None so
    `MarketMeta.complete` can refuse it; a default here would be a risk
    decision disguised as a parse."""
    pdec, sdec = row.get("price_decimals"), row.get("size_decimals")
    tick = 10.0 ** -int(pdec) if pdec is not None else None
    step = 10.0 ** -int(sdec) if sdec is not None else None

    mmf = _f(row, "maintenance_margin_fraction")
    imf = _f(row, "min_initial_margin_fraction")
    maint = (mmf / BPS) if mmf is not None else None
    init = (imf / BPS) if imf is not None else None
    # Max leverage is the RECIPROCAL of the minimum initial margin fraction.
    max_lev = (1.0 / init) if (init and init > 0) else None

    taker = _f(row, "taker_fee")
    maker = _f(row, "maker_fee")
    if not row.get("is_taker_fee_enabled", True):
        taker = 0.0
    if not row.get("is_maker_fee_enabled", True):
        maker = 0.0

    return MarketMeta(
        symbol=str(row.get("symbol") or ""),
        market_id=int(row.get("market_id", -1)),
        tick_size=tick if tick is not None else 0.0,
        qty_step=step if step is not None else 0.0,
        min_base_amount=_f(row, "min_base_amount") or 0.0,
        min_quote_amount=_f(row, "min_quote_amount") or 0.0,
        max_leverage=max_lev,
        maintenance_margin_frac=maint,
        initial_margin_frac=init,
        taker_fee=taker,
        maker_fee=maker,
        daily_quote_volume=_f(row, "daily_quote_token_volume") or 0.0,
        status=str(row.get("status") or "unknown"),
        price_decimals=int(pdec) if pdec is not None else None,
        size_decimals=int(sdec) if sdec is not None else None,
    )


def fetch(base_url: str, timeout: int = 30) -> list[MarketMeta]:
    doc = _http_json(base_url.rstrip("/") + _ENDPOINT, timeout=timeout)
    rows = doc.get("order_book_details") or []
    if not rows:
        raise RuntimeError("Lighter returned no market metadata; refusing to "
                           "continue on an empty universe")
    return [parse_market(r) for r in rows
            if str(r.get("market_type", "perp")) == "perp"]


class MetadataStore:
    """Versioned snapshots. The version IS a content hash of the risk-bearing
    fields, so two snapshots share a version only if every number an order or
    a liquidation estimate depends on is identical."""

    RISK_FIELDS = ("symbol", "market_id", "tick_size", "qty_step",
                   "min_base_amount", "min_quote_amount", "max_leverage",
                   "maintenance_margin_frac", "initial_margin_frac")

    def __init__(self, data_dir: str):
        self.dir = os.path.join(data_dir, "processed")
        os.makedirs(self.dir, exist_ok=True)

    @staticmethod
    def version(markets: Iterable[MarketMeta]) -> str:
        rows = sorted(
            ({k: getattr(m, k) for k in MetadataStore.RISK_FIELDS}
             for m in markets), key=lambda d: d["symbol"])
        blob = json.dumps(rows, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]

    def save(self, markets: list[MarketMeta]) -> tuple[str, str]:
        ver = self.version(markets)
        # `ver` is our own content hash and is already safe; routing it
        # through the same helper keeps ONE rule for every path this package
        # writes rather than a judgement call per site.
        path = contained_path(self.dir, f"markets_{ver}.json")
        payload = {"version": ver, "fetched_at": time.time(),
                   "markets": [asdict(m) for m in markets]}
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        with open(os.path.join(self.dir, "markets_latest.json"), "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        return ver, path

    def load_latest(self) -> tuple[str | None, list[MarketMeta], float]:
        path = os.path.join(self.dir, "markets_latest.json")
        if not os.path.exists(path):
            return None, [], 0.0
        with open(path) as fh:
            doc = json.load(fh)
        mk = []
        for row in doc.get("markets") or []:
            row = dict(row)
            row.pop("complete", None)
            mk.append(MarketMeta(**row))
        return doc.get("version"), mk, float(doc.get("fetched_at") or 0.0)


class MarketRegistry:
    """Symbol <-> market_id mapping plus the tradability decision."""

    def __init__(self, markets: list[MarketMeta], version: str = ""):
        self.version = version
        self.by_symbol = {m.symbol: m for m in markets}
        self.by_id = {m.market_id: m for m in markets}

    def __len__(self) -> int:
        return len(self.by_symbol)

    def get(self, symbol: str) -> MarketMeta | None:
        return self.by_symbol.get(symbol)

    def market_id(self, symbol: str) -> int | None:
        m = self.by_symbol.get(symbol)
        return None if m is None else m.market_id

    def symbol(self, market_id: int) -> str | None:
        m = self.by_id.get(market_id)
        return None if m is None else m.symbol

    def tradable(self, symbol: str, requested_leverage: float,
                 min_volume_usd: float = 0.0) -> tuple[bool, list[str]]:
        """-> (ok, reasons). REFUSES on incomplete metadata rather than
        filling a gap with a default."""
        m = self.by_symbol.get(symbol)
        if m is None:
            return False, [f"{symbol}: not listed on this venue"]
        problems = [f"{symbol}: incomplete metadata ({', '.join(m.missing())})"] \
            if not m.complete else []
        if m.max_leverage is not None and requested_leverage > m.max_leverage:
            problems.append(
                f"{symbol}: requested {requested_leverage}x exceeds the "
                f"market maximum {m.max_leverage:.1f}x")
        if min_volume_usd and m.daily_quote_volume < min_volume_usd:
            problems.append(
                f"{symbol}: 24h quote volume ${m.daily_quote_volume:,.0f} "
                f"below the ${min_volume_usd:,.0f} floor")
        return (not problems), problems

    def effective_leverage(self, symbol: str, requested: float,
                           account_cap: float) -> float:
        """min(requested, account cap, market cap) -- the LOWER supported
        value, never the one we asked for."""
        m = self.by_symbol.get(symbol)
        caps = [requested, account_cap]
        if m is not None and m.max_leverage is not None:
            caps.append(m.max_leverage)
        return max(0.0, min(caps))

    def round_price(self, symbol: str, price: float, *, side: str,
                    conservative: bool = True) -> float:
        """Round to tick. `conservative` rounds a LONG's stop DOWN and a
        SHORT's stop UP -- i.e. never tightens a protective level into a
        rounding error."""
        m = self.by_symbol.get(symbol)
        if m is None or m.tick_size <= 0:
            return price
        t = m.tick_size
        n = price / t
        if not conservative:
            r = round(n)
        else:
            r = (n // 1) if side == "long" else -((-n) // 1)
        return round(r * t, 12)

    def round_qty(self, symbol: str, qty: float) -> float:
        """Always DOWN: rounding a size up can breach a notional cap."""
        m = self.by_symbol.get(symbol)
        if m is None or m.qty_step <= 0:
            return qty
        return round((qty // m.qty_step) * m.qty_step, 12)

    def order_ok(self, symbol: str, qty: float, price: float
                 ) -> tuple[bool, str]:
        m = self.by_symbol.get(symbol)
        if m is None:
            return False, f"{symbol}: unknown market"
        if qty < m.min_base_amount:
            return False, (f"{symbol}: qty {qty} below min_base_amount "
                           f"{m.min_base_amount}")
        if qty * price < m.min_quote_amount:
            return False, (f"{symbol}: notional {qty * price:.4f} below "
                           f"min_quote_amount {m.min_quote_amount}")
        return True, ""


def discover(base_url: str, data_dir: str) -> tuple[MarketRegistry, str, str]:
    markets = fetch(base_url)
    store = MetadataStore(data_dir)
    ver, path = store.save(markets)
    log.info("discovered %d perp markets (metadata version %s)",
             len(markets), ver)
    return MarketRegistry(markets, ver), ver, path
