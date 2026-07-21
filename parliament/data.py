#!/usr/bin/env python3
"""
parliament/data.py — Layer 1: the Parliament's Lighter-native data layer.

LIGHTER-ONLY by construction: the ONLY host this module ever talks to is
mainnet.zklighter.elliot.ai (REST) / its /stream websocket. The venue we
trade is the venue we measure (operator rule, 17-Jul) — there is no foreign
reference price anywhere in the Parliament.

REST (keyless public endpoints, same ones lighter_market_scout uses):
  /api/v1/orderBookDetails  — every book: mark/index/last px, day OHLC, vols
  /api/v1/funding-rates     — venue funding (8h fraction; funding_basis is
                              the annualisation authority — never hand-roll)
  /api/v1/candles           — OHLCV, market_id + resolution + count_back
                              (500-bar page cap)

Budget: one orderBookDetails + one funding-rates per cycle (default 120s)
plus staggered candle refreshes for the small watchlist — a few requests a
minute, deliberately lighter than the scout's own cadence. The whole layer
is one shared client for ALL Parliament components; nobody else fetches.

WEBSOCKET (optional accelerator, never a dependency): subscribes
order_book/{market_id} for the top watchlist books, maintains depth
imbalance + spread for the imbalance scanner. Client pings every 90s (the
venue closes after ~2 min of silence) and answers server pings. Cloud IPs
are sometimes CDN-blocked from the ws (see venues/lighter_client.py) — on
repeated failure it goes quiet and the REST snapshot fields carry on.

Injectability: pass `fetch=` (a callable(path, **params) -> dict) to run the
whole Parliament against synthetic data — that is how the offline selftest
drives every layer with zero network.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.parse
import urllib.request

try:
    import funding_basis  # the fleet's annualisation authority (repo root)
except Exception:  # noqa: BLE001 — degraded: funding scanner goes quiet
    funding_basis = None

log = logging.getLogger("parliament.data")

API_BASE = os.environ.get("LIGHTER_API_BASE",
                          "https://mainnet.zklighter.elliot.ai")
WS_URL = API_BASE.replace("https://", "wss://") + "/stream"

RES_FAST = os.environ.get("PARL_RES_FAST", "15m")
RES_SLOW = os.environ.get("PARL_RES_SLOW", "1h")
_RES_SEC = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400,
            "1d": 86400}

SCAN_SEC = float(os.environ.get("PARL_SCAN_SEC", "120"))
CANDLE_FAST_SEC = float(os.environ.get("PARL_CANDLE_FAST_SEC", "300"))
CANDLE_SLOW_SEC = float(os.environ.get("PARL_CANDLE_SLOW_SEC", "900"))
WATCH_CORE = [s.strip().upper() for s in
              os.environ.get("PARL_WATCH", "BTC,ETH,SOL").split(",") if s.strip()]
WATCH_TOP_N = int(os.environ.get("PARL_WATCH_TOP_N", "9"))
MIN_QVOL = float(os.environ.get("PARL_MIN_QVOL", "1000000"))  # $1M/day
CANDLE_BARS = int(os.environ.get("PARL_CANDLE_BARS", "160"))


def http_fetch(path: str, **params) -> dict:
    """Blocking GET against the Lighter REST API. Raises on failure —
    callers run it in an executor and guard."""
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_books(raw: dict) -> dict[str, dict]:
    """orderBookDetails -> {sym: stats}. None-safe, junk rows skipped —
    the same defensive parse the scout uses."""
    out = {}
    for b in (raw or {}).get("order_book_details") or []:
        try:
            if b.get("status") != "active":
                continue
            sym = b.get("symbol")
            mark = float(b.get("mark_price") or 0.0)
            idx = float(b.get("index_price") or 0.0)
            last = float(b.get("last_trade_price") or 0.0)
            if not sym or mark <= 0.0:
                continue
            out[sym] = {
                "market_id": int(b.get("market_id") or -1),
                "mark": mark,
                "index": idx,
                "last": last if last > 0 else mark,
                "prem_bps": round((mark / idx - 1.0) * 1e4, 2) if idx > 0 else 0.0,
                "qvol": float(b.get("daily_quote_token_volume") or 0.0),
                "oi": float(b.get("open_interest") or 0.0),
                "high": float(b.get("daily_price_high") or 0.0),
                "low": float(b.get("daily_price_low") or 0.0),
                "chg": float(b.get("daily_price_change") or 0.0),
            }
        except (TypeError, ValueError):
            continue
    return out


def parse_funding(raw: dict) -> dict[str, float]:
    """funding-rates -> {sym: TRUE apr %} for Lighter's OWN rows only.
    Lighter quotes a fraction per 8h — funding_basis.to_apr_pct is the one
    correct annualisation (the 8x bug of 17-Jul lives in every hand-rolled
    version of this line)."""
    if funding_basis is None:
        return {}
    out = {}
    for r in (raw or {}).get("funding_rates") or []:
        try:
            if r.get("exchange") != "lighter":
                continue
            sym, rate = r.get("symbol"), r.get("rate")
            if not sym or rate is None:
                continue
            out[sym] = round(funding_basis.to_apr_pct(rate, "lighter"), 2)
        except (TypeError, ValueError):
            continue
    return out


def parse_candles(raw: dict) -> list[dict]:
    """/api/v1/candles -> [{t(sec, ascending), o,h,l,c,v}]."""
    out = []
    for c in (raw or {}).get("c") or []:
        try:
            out.append({"t": int(c["t"]) // 1000,
                        "o": float(c["o"]), "h": float(c["h"]),
                        "l": float(c["l"]), "c": float(c["c"]),
                        "v": float(c.get("v") or 0.0)})
        except (TypeError, ValueError, KeyError):
            continue
    out.sort(key=lambda x: x["t"])
    return out


class LighterData:
    """Shared market state for every Parliament layer. One writer (the poll
    tasks), many readers (scanners/bots read plain dicts — no awaits)."""

    def __init__(self, db=None, bus=None, fetch=None):
        self.db = db
        self.bus = bus
        self._fetch = fetch or http_fetch
        self.market: dict[str, dict] = {}       # sym -> parse_books stats
        self.funding: dict[str, float] = {}     # sym -> TRUE apr %
        self.candles: dict[tuple, list[dict]] = {}   # (sym, res) -> bars
        self.ws_books: dict[str, dict] = {}     # sym -> {ts, imb, spread_bps, mid}
        self.watchlist: list[str] = list(WATCH_CORE)
        self.market_ts = 0.0
        self.errors = 0
        self.cycles = 0

    # -- fetch plumbing -------------------------------------------------------
    async def _get(self, path: str, **params) -> dict | None:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None, lambda: self._fetch(path, **params))
        except Exception as e:  # noqa: BLE001
            self.errors += 1
            log.warning("GET %s failed (%s)", path, e)
            return None

    # -- market map -----------------------------------------------------------
    async def refresh_market(self) -> bool:
        books_raw = await self._get("/api/v1/orderBookDetails")
        fund_raw = await self._get("/api/v1/funding-rates")
        if books_raw is None:
            return False
        market = parse_books(books_raw)
        if not market:
            return False
        prev = self.market
        self.market = market
        if fund_raw is not None:
            self.funding = parse_funding(fund_raw)
        self.market_ts = time.time()
        self.cycles += 1
        self._rebuild_watchlist(prev)
        if self.bus is not None:
            self.bus.publish("market.snapshot", {
                "ts": self.market_ts, "n_books": len(market),
                "watchlist": list(self.watchlist)})
        return True

    def _rebuild_watchlist(self, prev: dict) -> None:
        """Core majors + the most liquid books by day quote volume. New
        entrants vs the previous snapshot are surfaced for the listing
        scanner via the market dict itself (`_new` flag)."""
        ranked = sorted(
            (s for s, st in self.market.items() if st["qvol"] >= MIN_QVOL),
            key=lambda s: -self.market[s]["qvol"])
        wl = [s for s in WATCH_CORE if s in self.market]
        for s in ranked:
            if len(wl) >= len(WATCH_CORE) + WATCH_TOP_N:
                break
            if s not in wl:
                wl.append(s)
        self.watchlist = wl
        if prev:
            for s, st in self.market.items():
                st["_new"] = s not in prev
        else:
            for st in self.market.values():
                st["_new"] = False

    # -- candles --------------------------------------------------------------
    async def refresh_candles(self, resolution: str) -> int:
        """One pass over the watchlist for `resolution`. Returns bars fetched."""
        res_sec = _RES_SEC.get(resolution, 3600)
        got = 0
        for sym in list(self.watchlist):
            st = self.market.get(sym)
            if not st or st.get("market_id", -1) < 0:
                continue
            end = int(time.time())
            raw = await self._get(
                "/api/v1/candles", market_id=st["market_id"],
                resolution=resolution,
                start_timestamp=end - CANDLE_BARS * res_sec,
                end_timestamp=end, count_back=CANDLE_BARS)
            bars = parse_candles(raw) if raw else []
            if bars:
                self.candles[(sym, resolution)] = bars[-CANDLE_BARS:]
                got += len(bars)
                if self.db is not None:
                    self.db.store_candles(sym, resolution, bars[-40:])
            await asyncio.sleep(0.25)   # stay polite: never burst the API
        return got

    def get_candles(self, sym: str, resolution: str) -> list[dict]:
        return self.candles.get((sym, resolution), [])

    def stats(self, sym: str) -> dict | None:
        return self.market.get(sym)

    def fresh(self, max_age_sec: float = 600.0) -> bool:
        return bool(self.market) and (time.time() - self.market_ts) <= max_age_sec

    # -- long-running tasks ---------------------------------------------------
    async def poll_market_forever(self, beat=None):
        while True:
            ok = await self.refresh_market()
            if beat:
                beat("data.market", "ok" if ok else "fetch-failed")
            await asyncio.sleep(SCAN_SEC)

    async def poll_candles_forever(self, resolution: str, interval: float,
                                   beat=None):
        while True:
            if self.market:
                n = await self.refresh_candles(resolution)
                if beat:
                    beat(f"data.candles.{resolution}", f"{n} bars")
            await asyncio.sleep(interval)

    # -- websocket accelerator ------------------------------------------------
    async def ws_forever(self, top_n: int = 6, beat=None):
        """Depth/imbalance stream for the top watchlist books. Optional: any
        failure degrades to REST-only quietly (the scanners fall back to the
        snapshot fields)."""
        try:
            import websockets
        except Exception:  # noqa: BLE001 — wheel absent: REST-only mode
            log.info("websockets wheel absent — ws accelerator off")
            return
        fails = 0
        while True:
            try:
                while not self.market:
                    await asyncio.sleep(5.0)
                wanted = {self.market[s]["market_id"]: s
                          for s in self.watchlist[:top_n]
                          if s in self.market and self.market[s]["market_id"] >= 0}
                async with websockets.connect(
                        WS_URL, open_timeout=15,
                        additional_headers={"Origin": "https://app.lighter.xyz"},
                ) as ws:
                    for mid in wanted:
                        await ws.send(json.dumps(
                            {"type": "subscribe",
                             "channel": f"order_book/{mid}"}))
                    fails = 0
                    books: dict[int, dict] = {}
                    last_ping = time.time()
                    while True:
                        # client keepalive every 90s — the venue closes the
                        # socket after ~2 min of silence.
                        timeout = max(5.0, 90.0 - (time.time() - last_ping))
                        try:
                            msg = json.loads(await asyncio.wait_for(
                                ws.recv(), timeout=timeout))
                        except asyncio.TimeoutError:
                            await ws.send(json.dumps({"type": "ping"}))
                            last_ping = time.time()
                            continue
                        mt = msg.get("type")
                        if mt == "ping":
                            await ws.send(json.dumps({"type": "pong"}))
                        elif mt in ("subscribed/order_book",
                                    "update/order_book"):
                            chan = str(msg.get("channel", ""))
                            mid_s = chan.split(":")[-1].split("/")[-1]
                            try:
                                mid = int(mid_s)
                            except ValueError:
                                continue
                            ob = msg.get("order_book") or {}
                            if mt == "subscribed/order_book":
                                books[mid] = {"bids": list(ob.get("bids") or []),
                                              "asks": list(ob.get("asks") or [])}
                            elif mid in books:
                                for side in ("bids", "asks"):
                                    self._merge(ob.get(side) or [],
                                                books[mid][side])
                            sym = wanted.get(mid)
                            if sym and mid in books:
                                snap = self._book_metrics(books[mid])
                                if snap:
                                    self.ws_books[sym] = snap
                        if beat:
                            beat("data.ws", f"{len(self.ws_books)} books")
            except Exception as e:  # noqa: BLE001 — reconnect with backoff
                fails += 1
                wait = min(600.0, 5.0 * (2 ** min(fails, 6)))
                if fails <= 3:
                    log.warning("ws dropped (%s); retry in %.0fs", e, wait)
                elif fails == 4:
                    log.warning("ws unavailable (cloud-IP CDN block is a known "
                                "state) — REST snapshots carry on; retrying "
                                "quietly")
                await asyncio.sleep(wait)

    @staticmethod
    def _merge(side_new: list, side_state: list) -> None:
        for new in side_new:
            for old in side_state[:]:
                if new.get("price") == old.get("price"):
                    old["size"] = new.get("size")
                    break
            else:
                side_state.append(dict(new))
        side_state[:] = [o for o in side_state
                         if float(o.get("size") or 0) > 0]

    @staticmethod
    def _book_metrics(book: dict, depth: int = 10) -> dict | None:
        try:
            bids = sorted(((float(o["price"]), float(o["size"]))
                           for o in book["bids"]), key=lambda x: -x[0])[:depth]
            asks = sorted(((float(o["price"]), float(o["size"]))
                           for o in book["asks"]), key=lambda x: x[0])[:depth]
            if not bids or not asks:
                return None
            bid_qty = sum(s * p for p, s in bids)
            ask_qty = sum(s * p for p, s in asks)
            tot = bid_qty + ask_qty
            mid = (bids[0][0] + asks[0][0]) / 2.0
            return {
                "ts": time.time(),
                "imb": (bid_qty - ask_qty) / tot if tot > 0 else 0.0,
                "spread_bps": (asks[0][0] - bids[0][0]) / mid * 1e4 if mid else 0.0,
                "mid": mid,
            }
        except Exception:  # noqa: BLE001
            return None
