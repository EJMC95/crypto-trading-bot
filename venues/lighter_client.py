#!/usr/bin/env python3
"""
venues/lighter_client.py — Lighter.xyz venue client (zk perps, zero fees).

Built on lighter-sdk (verified 1.1.1: signer binaries load on BOTH our deploy
target linux/amd64 python:3.11-slim AND the dev Mac arm64 — docs/lighter.md).
The SDK is asyncio; the bots are synchronous, so this client runs one event
loop in a daemon thread and bridges calls with run_coroutine_threadsafe.

Design constraints it encodes (all empirically verified 2026-07-09):
  * Standard tier = 60 WEIGHTED req/min per L1 address shared REST+tx (order
    tx weight 6) -> ALL REST goes through venues.governor.TxBudgetGovernor;
    market data is websocket-first (free: 200 conns/IP, 500 subs/conn).
  * Fleet symbols are HL-style; venues/symbol_map.py translates (kBONK ↔
    1000BONK 1:1, PEPE ↔ 1000PEPE ×0.001). INJ/ATOM/ORDI/TON are unlisted —
    supports() lets bots skip them.
  * Auth model: L1 key NEVER touches this code. Trading uses an API key
    (index 4-254; 0-3 reserved for Lighter's own UI) created from Eamon's
    Ledger on the Mac; env only:
        LIGHTER_API_PRIVATE_KEY   (api key private key, env/Railway secret)
        LIGHTER_ACCOUNT_INDEX     (from accounts_by_l1_address)
        LIGHTER_API_KEY_INDEX     (default 4)
  * Candle dicts come back as {t,o,h,l,c,v} (t in ms) — same keys the HL
    path yields, so strategy code is venue-blind.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time

from .base import VenueClient, VenueError
from .equity_guard import EquityGuard, EquityRejected, vet_account_read
from .governor import TxBudgetGovernor, WEIGHT_INFO, WEIGHT_ORDER_TX
from .symbol_map import to_lighter

log = logging.getLogger("venues.lighter")

MAINNET_URL = "https://mainnet.zklighter.elliot.ai"
TESTNET_URL = "https://testnet.zklighter.elliot.ai"   # verified live 2026-07-09
BOOK_STALE_SEC = 30.0    # ws book older than this -> REST fallback
# REST book snapshots are cached this long. The ws path already serves books up
# to BOOK_STALE_SEC old, so a <=20s snapshot is no staler than the accepted
# norm — and it stops the equity guard and the strategy's fresh_mid calls from
# double-paying the governor for the same book within one loop.
REST_BOOK_TTL = float(os.environ.get("LIGHTER_REST_BOOK_TTL", "20"))


class _BookCache(threading.Thread):
    """One ws connection streaming order_book/{id} for every subscribed market,
    with automatic reconnect + resubscribe. Book state mirrors the SDK's merge
    semantics (price-keyed upsert, size-0 removal)."""

    def __init__(self, host: str):
        super().__init__(daemon=True, name="lighter-book-ws")
        self.url = "wss://" + host.replace("https://", "") + "/stream"
        self.market_ids: set[int] = set()
        self.books: dict[int, dict] = {}
        self.updated: dict[int, float] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self.started_ok = threading.Event()

    def subscribe(self, market_id: int):
        with self._lock:
            if market_id in self.market_ids:
                return
            self.market_ids.add(market_id)
        self._wake.set()  # force a reconnect that picks up the new subscription

    def get(self, market_id: int):
        with self._lock:
            book = self.books.get(market_id)
            ts = self.updated.get(market_id, 0.0)
        if book is None or (time.time() - ts) > BOOK_STALE_SEC:
            return None
        bids = sorted(((float(o["price"]), float(o["size"])) for o in book["bids"]),
                      key=lambda x: -x[0])
        asks = sorted(((float(o["price"]), float(o["size"])) for o in book["asks"]),
                      key=lambda x: x[0])
        return {"bids": bids, "asks": asks}

    def _merge(self, side_new, side_state):
        for new in side_new:
            for old in side_state[:]:
                if new["price"] == old["price"]:
                    old["size"] = new["size"]
                    break
            else:
                side_state.append(new)
        side_state[:] = [o for o in side_state if float(o["size"]) > 0]

    # Browser-like handshake — Lighter's CDN 400s a bare ws upgrade from cloud
    # (datacenter) IPs even though its REST works from the same host, so present
    # as a browser. Best-effort: if the CDN blocks by IP anyway, the client falls
    # back to REST orderbook snapshots (which work) — see the graceful backoff.
    _WS_ORIGIN = "https://app.lighter.xyz"
    _WS_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

    def run(self):
        from websockets.sync.client import connect
        backoff = 1.0
        fails = 0
        degraded_logged = False
        while True:
            try:
                with self._lock:
                    wanted = set(self.market_ids)
                if not wanted:
                    time.sleep(1.0)
                    continue
                self._wake.clear()
                with connect(self.url, open_timeout=15,
                             origin=self._WS_ORIGIN,
                             user_agent_header=self._WS_UA,
                             additional_headers={"Origin": self._WS_ORIGIN}) as ws:
                    for mid in wanted:
                        ws.send(json.dumps({"type": "subscribe",
                                            "channel": f"order_book/{mid}"}))
                    self.started_ok.set()
                    if fails:
                        log.info("book ws reconnected after %d failure(s)", fails)
                    fails, backoff, degraded_logged = 0, 1.0, False
                    while not self._wake.is_set():
                        msg = json.loads(ws.recv(timeout=30))
                        mt = msg.get("type")
                        if mt == "ping":
                            ws.send(json.dumps({"type": "pong"}))
                        elif mt in ("subscribed/order_book", "update/order_book"):
                            mid = int(msg["channel"].split(":")[1].split("/")[-1])
                            with self._lock:
                                if mt == "subscribed/order_book":
                                    self.books[mid] = msg["order_book"]
                                elif mid in self.books:
                                    self._merge(msg["order_book"]["asks"],
                                                self.books[mid]["asks"])
                                    self._merge(msg["order_book"]["bids"],
                                                self.books[mid]["bids"])
                                self.updated[mid] = time.time()
            except Exception as e:  # noqa: BLE001 — reconnect forever
                fails += 1
                # A few quick retries; then assume the venue ws is blocked from
                # this host (cloud-IP CDN 400) and go QUIET — orderbook() falls
                # back to governed REST snapshots, which work. Retry every 10 min
                # in case the block lifts, without spamming the log every cycle.
                if fails <= 3:
                    log.warning("book ws dropped (%s); retry in %.0fs", e, backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                else:
                    if not degraded_logged:
                        log.warning("book ws unavailable after %d tries (%s) — using "
                                    "REST orderbook snapshots; retrying every 10 min", fails, e)
                        degraded_logged = True
                    time.sleep(600.0)


class LighterClient(VenueClient):
    name = "lighter"

    def __init__(self, net: str = "mainnet", with_signer: bool = False,
                 governor: TxBudgetGovernor | None = None,
                 guard_state_key: str | None = None):
        try:
            import lighter  # lazy: only lighter modes need the SDK installed
        except ImportError as e:
            raise VenueError(f"lighter-sdk missing (pip install lighter-sdk): {e}")
        self._lighter = lighter
        self.net = net
        self.host = MAINNET_URL if net == "mainnet" else TESTNET_URL
        self.gov = governor or TxBudgetGovernor()

        # one asyncio loop thread for the whole client. aiohttp requires its
        # session objects to be created INSIDE a running loop, so the ApiClient
        # is built by a coroutine on that loop, not here.
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True,
                         name="lighter-async").start()

        async def _build():
            cfg = lighter.Configuration(host=self.host)
            api = lighter.ApiClient(configuration=cfg)
            return (api, lighter.OrderApi(api), lighter.CandlestickApi(api),
                    lighter.FundingApi(api), lighter.AccountApi(api),
                    lighter.AnnouncementApi(api))

        (self._api, self._order_api, self._candle_api, self._funding_api,
         self._account_api, self._announcement_api) = asyncio.run_coroutine_threadsafe(
            _build(), self._loop).result(timeout=30)

        # market metadata (symbol -> id, decimals, mins) — one governed call
        self.markets = self._load_markets()
        self._books = _BookCache(self.host)
        self._books.start()
        self._rest_books: dict[int, tuple[float, dict]] = {}   # market_id -> (ts, book)

        self.signer = None
        self.account_index = None
        self._guard = None
        if with_signer:
            self._init_signer()
            self.sends_orders = True
            self._guard = self._make_guard(guard_state_key)

        # tidy shutdown for short-lived uses (scripts) — the long-running bots
        # never exit, so this just silences aiohttp "Unclosed session" on exit.
        import atexit
        atexit.register(self.close)

    def close(self):
        try:
            asyncio.run_coroutine_threadsafe(self._api.close(), self._loop).result(timeout=5)
        except Exception:  # noqa: BLE001
            pass

    # ---- plumbing -----------------------------------------------------------
    def _run(self, coro, timeout=30.0, weight=WEIGHT_INFO):
        if not self.gov.acquire(weight=weight):
            raise VenueError("lighter tx budget exhausted; skipping")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            out = fut.result(timeout=timeout)
            self.gov.reward()
            return out
        except Exception as e:
            msg = repr(e)
            if "429" in msg or "405" in msg:
                self.gov.punish()
                log.warning("lighter rate-limited (%s); backing off", msg[:120])
            raise

    def _load_markets(self):
        r = self._run(self._order_api.order_book_details())
        out = {}
        for d in r.order_book_details:
            dd = d.to_dict()
            out[dd["symbol"]] = {
                "id": int(dd["market_id"]),
                "status": dd.get("status"),
                "price_decimals": int(dd.get("supported_price_decimals",
                                             dd.get("price_decimals", 2))),
                "size_decimals": int(dd.get("supported_size_decimals",
                                            dd.get("size_decimals", 4))),
                "min_base": float(dd.get("min_base_amount") or 0.0),
                "min_quote": float(dd.get("min_quote_amount") or 0.0),
                "last": float(dd.get("last_trade_price") or 0.0),
                "day_vol": float(dd.get("daily_quote_token_volume") or 0.0),
            }
        log.info("lighter %s: %d markets loaded", self.net, len(out))
        return out

    def refresh_markets(self):
        """Re-fetch the market list (governed) and update self.markets. Returns
        the current {symbol: meta} dict — the new-perp sniper diffs this to spot
        freshly-listed markets."""
        self.markets = self._load_markets()
        return self.markets

    def announcements(self):
        """Recent Lighter announcements (list of {title, content, created_at,...}).
        Freeform text — used only as CONTEXT for a new listing, never as the
        detection source of truth. Returns [] on any error."""
        try:
            r = self._run(self._announcement_api.announcement())
            return r.to_dict().get("announcements") or []
        except Exception:  # noqa: BLE001
            return []

    def _resolve(self, coin: str):
        sym, mult = to_lighter(coin)
        m = self.markets.get(sym)
        if m is None or m.get("status") != "active":
            raise VenueError(f"{coin} ({sym}) not listed/active on lighter {self.net}")
        return sym, mult, m

    def supports(self, coin: str) -> bool:
        try:
            self._resolve(coin)
            return True
        except VenueError:
            return False

    # ---- market data ---------------------------------------------------------
    def candles(self, coin, interval, start_ms, end_ms):
        _, _, m = self._resolve(coin)
        n = max(2, min(1500, int((end_ms - start_ms) / self._interval_ms(interval)) + 2))
        r = self._run(self._candle_api.candles(
            market_id=m["id"], resolution=interval,
            start_timestamp=int(start_ms / 1000), end_timestamp=int(end_ms / 1000),
            count_back=n))
        d = r.to_dict()
        if d.get("code") != 200:
            raise VenueError(f"candles {coin} code={d.get('code')}")
        return d.get("c") or []

    @staticmethod
    def _interval_ms(interval):
        unit = interval[-1]
        n = int(interval[:-1])
        return n * {"m": 60, "h": 3600, "d": 86400}[unit] * 1000

    def funding_map(self):
        """Lighter's own funding per market, in fleet symbols. The same endpoint
        also carries binance/bybit/hyperliquid benchmark rows — surfaced under
        '_bench' so the carry bot can do cross-venue math without extra calls."""
        from .symbol_map import from_lighter
        r = self._run(self._funding_api.funding_rates())
        rows = r.to_dict().get("funding_rates") or []
        out = {}
        for row in rows:
            sym = row.get("symbol")
            fleet, _ = from_lighter(sym)
            rec = out.setdefault(fleet, {"rate": 0.0, "mark": 0.0, "vol": 0.0,
                                         "_bench": {}})
            if row.get("exchange") == "lighter":
                rec["rate"] = float(row.get("rate") or 0.0)
            else:
                rec["_bench"][row.get("exchange")] = float(row.get("rate") or 0.0)
        for fleet, rec in out.items():
            sym, _ = to_lighter(fleet)
            m = self.markets.get(sym)
            if m:
                rec["mark"] = m["last"]
                rec["vol"] = m["day_vol"]
        return out

    def orderbook(self, coin):
        _, _, m = self._resolve(coin)
        self._books.subscribe(m["id"])
        book = self._books.get(m["id"])
        if book is not None:
            return book
        # ws not warm (the Railway norm — CDN blocks cloud-IP ws) -> governed
        # REST snapshot, TTL-cached so guard + strategy don't double-pay
        return self._rest_book(m["id"])

    def _rest_book(self, market_id, force=False):
        now = time.time()
        if not force:
            hit = self._rest_books.get(market_id)
            if hit and (now - hit[0]) <= REST_BOOK_TTL:
                return hit[1]
        r = self._run(self._order_api.order_book_orders(market_id=market_id, limit=25))
        d = r.to_dict()
        # REST snapshots come back UNSORTED (the ws cache sorts in _BookCache
        # .get) and every consumer takes [0] as top-of-book — sort here once.
        bids = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                       for o in (d.get("bids") or [])), key=lambda x: -x[0])
        asks = sorted(((float(o["price"]), float(o["remaining_base_amount"]))
                       for o in (d.get("asks") or [])), key=lambda x: x[0])
        book = {"bids": bids, "asks": asks}
        self._rest_books[market_id] = (now, book)
        return book

    # ---- account / orders (testnet + live only) ------------------------------
    def _init_signer(self):
        key = os.environ.get("LIGHTER_API_PRIVATE_KEY", "").strip()
        acct = os.environ.get("LIGHTER_ACCOUNT_INDEX", "").strip()
        if not key or not acct:
            raise VenueError("LIGHTER_API_PRIVATE_KEY / LIGHTER_ACCOUNT_INDEX not set "
                             "(env only — never in the repo)")
        self.account_index = int(acct)
        # Indices 0-3 are reserved for Lighter's own desktop/mobile UI; bots use
        # 4-254 (docs.lighter.xyz). Default 4 so a bot key never collides with UI.
        self.api_key_index = int(os.environ.get("LIGHTER_API_KEY_INDEX", "4"))
        # SignerClient.__init__ builds an aiohttp ApiClient internally, which calls
        # asyncio.get_running_loop() — so it MUST be constructed ON the loop thread
        # (like ApiClient in _build), not in this synchronous __init__ context, or
        # it raises RuntimeError('no running event loop'). [live-path fix 2026-07-10]
        async def _mk_signer():
            return self._lighter.SignerClient(
                url=self.host, account_index=self.account_index,
                api_private_keys={self.api_key_index: key})
        self.signer = asyncio.run_coroutine_threadsafe(
            _mk_signer(), self._loop).result(timeout=30)
        err = self.signer.check_client()   # local Go-binary validation (no loop)
        if err:
            raise VenueError(f"lighter signer check failed: {err}")
        log.info("lighter signer ready (account %d, key index %d)",
                 self.account_index, self.api_key_index)

    def _run_signer(self, coro, timeout=30.0):
        return self._run(coro, timeout=timeout, weight=WEIGHT_ORDER_TX)

    def _make_guard(self, state_key):
        """EquityGuard wiring: cached mids ride the ws/TTL-REST book path (what
        the bots already pay for); fresh mids force new REST snapshots and are
        only fetched on a SUSPECTED dislocation. The last accepted read is
        persisted (bot_pnl_store bot_state, like the durable daily-loss halt)
        so a redeploy can't re-anchor the guard on a dislocated print."""
        from .marks import mid_map
        load = save = None
        if state_key:
            try:
                import bot_pnl_store as _store
                load = lambda: _store.load_state(state_key)          # noqa: E731
                save = lambda st: _store.save_state(state_key, st)   # noqa: E731
            except Exception as e:  # noqa: BLE001 — guard works memory-only too
                log.warning("equity guard: no state persistence (%s)", e)
        return EquityGuard(
            mids_cached=lambda coins: mid_map(self, coins),
            mids_fresh=lambda coins: {c: m for c in coins
                                      if (m := self._mid_fresh(c))},
            load_state=load, save_state=save)

    def _mid_fresh(self, coin):
        """Force-fresh REST book mid (bypasses ws + TTL caches) — dislocation
        re-check evidence only. Governed weight-1 per coin."""
        try:
            _, _, m = self._resolve(coin)
            book = self._rest_book(m["id"], force=True)
        except Exception:  # noqa: BLE001
            return None
        bids = [px for px, _ in book["bids"] if px > 0]
        asks = [px for px, _ in book["asks"] if px > 0]
        if bids and asks:
            return (max(bids) + min(asks)) / 2.0
        return None

    def _account_payload(self):
        r = self._run(self._account_api.account(by="index",
                                                value=str(self.account_index)))
        d = r.to_dict()
        accts = d.get("accounts") or []
        if not accts:
            raise VenueError("account not found")
        return accts[0]

    @staticmethod
    def _positions_from(acct):
        from .symbol_map import from_lighter
        out = {}
        for p in (acct.get("positions") or []):
            sym = p.get("symbol") or ""
            fleet, _ = from_lighter(sym)
            sign = -1.0 if int(p.get("sign", 1)) < 0 else 1.0
            size = float(p.get("position") or 0.0) * sign
            if size:
                rec = {"size": size,
                       "entry": float(p.get("avg_entry_price") or 0.0)}
                # venue's own mark-to-market — the equity guard cross-checks it
                # against live book mids (extra key is harmless to strategy code)
                try:
                    if p.get("unrealized_pnl") is not None:
                        rec["upnl"] = float(p["unrealized_pnl"])
                except (TypeError, ValueError):
                    pass
                out[fleet] = rec
        return out

    def _equity_fields(self, acct):
        total = None
        for k in ("total_asset_value", "collateral"):
            if acct.get(k) is not None:
                total = float(acct[k])
                break
        if total is None:
            raise VenueError("no account value field in response")
        coll = float(acct["collateral"]) if acct.get("collateral") is not None else None
        return total, coll, self._positions_from(acct)

    def account_value(self):
        """Venue equity, vetted by the EquityGuard: the print is cross-checked
        against live book mids and the previous ACCEPTED read, and rejected
        (VenueError) on positive evidence of dislocation. [2026-07-11: one
        dislocated total_asset_value print tripped the daily-loss rail and the
        flatten sold into it — see venues/equity_guard.py.] Callers already
        treat a raise as 'equity unreadable this loop'; the day-start baseline
        is captured through this same path, so a dislocated-HIGH baseline is
        vetoed too (cold boots take two agreeing reads)."""
        try:
            return vet_account_read(
                self._guard, lambda: self._equity_fields(self._account_payload()))
        except EquityRejected as e:
            raise VenueError(str(e))

    def positions(self):
        return self._positions_from(self._account_payload())

    def _scaled(self, m, size, price):
        base = int(round(size * (10 ** m["size_decimals"])))
        px = int(round(price * (10 ** m["price_decimals"])))
        return base, px

    def market_open(self, coin, is_long, size):
        sym, mult, m = self._resolve(coin)
        book = self.orderbook(coin)
        side = book["asks"] if is_long else book["bids"]
        if not side:
            raise VenueError(f"{coin}: empty book")
        # worst acceptable = top of book +/- 2% (market-with-slippage-guard)
        worst = side[0][0] * (1.02 if is_long else 0.98)
        base, px = self._scaled(m, size * mult, worst)
        if base <= 0:
            raise VenueError(f"{coin}: size {size} scales to 0")
        tx, resp, err = self._run_signer(self.signer.create_market_order(
            market_index=m["id"],
            client_order_index=int(time.time() * 1000) % (2 ** 48),
            base_amount=base, avg_execution_price=px, is_ask=not is_long,
            api_key_index=self.api_key_index))
        if err:
            raise VenueError(f"order failed {coin}: {err}")
        return {"tx": getattr(tx, "to_dict", lambda: str(tx))(),
                "resp": getattr(resp, "to_dict", lambda: str(resp))()}

    def last_fill(self, coin, is_ask, since_ts, lookback=10):
        """[2026-07-16 FILL RECON] Best-effort REAL average fill price for
        THIS account's most recent fills on `coin` since `since_ts` (epoch
        seconds), on the given side (is_ask=True when we sold). Size-weighted
        across the partial fills a single market order crossed. Read-only —
        an auth-token GET on the venue's trades endpoint (verified against
        lighter-sdk OrderApi.trades: price/size/ask_account_id/bid_account_id/
        timestamp fields). Returns None on ANY failure; callers fall back to
        the decision price, so a broken read can never block a close."""
        try:
            if self.signer is None or self.account_index is None:
                return None
            _sym, _mult, m = self._resolve(coin)
            auth = self.signer.create_auth_token_with_expiry(
                api_key_index=self.api_key_index)
            if isinstance(auth, tuple):          # sdk returns (token, err)
                auth, _err = auth
                if _err or not auth:
                    return None
            r = self._run(self._order_api.trades(
                sort_by="timestamp", sort_dir="desc", limit=int(lookback),
                authorization=auth, market_id=m["id"],
                account_index=self.account_index))
            fills = []
            for t in (getattr(r, "trades", None) or []):
                ts = float(getattr(t, "timestamp", 0) or 0)
                if ts > 1e12:                    # ms -> s
                    ts /= 1000.0
                if ts < float(since_ts) - 5:
                    continue
                ours_ask = getattr(t, "ask_account_id", None) == self.account_index
                ours_bid = getattr(t, "bid_account_id", None) == self.account_index
                if is_ask and not ours_ask:
                    continue
                if not is_ask and not ours_bid:
                    continue
                px = float(getattr(t, "price", 0) or 0)
                sz = abs(float(getattr(t, "size", 0) or 0))
                if px > 0 and sz > 0:
                    fills.append((px, sz))
            if not fills:
                return None
            tot = sum(sz for _, sz in fills)
            return sum(px * sz for px, sz in fills) / tot
        except Exception:  # noqa: BLE001 — measurement-only: never raise
            return None

    def market_close(self, coin):
        pos = self.positions().get(coin)
        if not pos or not pos["size"]:
            return None
        sym, mult, m = self._resolve(coin)
        is_long = pos["size"] > 0
        book = self.orderbook(coin)
        side = book["bids"] if is_long else book["asks"]
        if not side:
            raise VenueError(f"{coin}: empty book")
        worst = side[0][0] * (0.98 if is_long else 1.02)
        base, px = self._scaled(m, abs(pos["size"]) * mult, worst)
        tx, resp, err = self._run_signer(self.signer.create_market_order(
            market_index=m["id"],
            client_order_index=int(time.time() * 1000) % (2 ** 48),
            base_amount=base, avg_execution_price=px, is_ask=is_long,
            reduce_only=True, api_key_index=self.api_key_index))
        if err:
            raise VenueError(f"close failed {coin}: {err}")
        return {"tx": getattr(tx, "to_dict", lambda: str(tx))(),
                "resp": getattr(resp, "to_dict", lambda: str(resp))()}
