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

# Tokens the public-tape FILL FALLBACK will not dip below, so a measurement can
# never eat the budget a pending market order (WEIGHT_ORDER_TX=6, capacity ~21)
# still needs. Paired with a NON-BLOCKING acquire, which is the real protection:
# telemetry never QUEUES behind money, it takes a free token or skips and says
# so. Measured on the taker's real 2-open cycle: 17 of 21 tokens spent, so one
# order's reserve leaves the measurement reachable — a reserve of 2 orders
# suppressed the very fill this fix exists to record.
_TELEMETRY_RESERVE = float(os.environ.get("LIGHTER_TELEMETRY_RESERVE",
                                          WEIGHT_ORDER_TX))
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


# [2026-07-17 WITHDRAWN — min_size_error]
# I shipped a guard here that refused an order whose size was below its book's
# `min_base_amount` or whose notional was below `min_quote_amount`, and told the
# operator "$10 is a HARD FLOOR on every Lighter book; there is no $5 clip".
#
# BOTH HALVES ARE REFUTED BY THE FLEET'S OWN ORDER LEDGER, which had the
# evidence sitting in it the whole time:
#   * min_base_amount is NOT enforced for market orders. 16 of 56 real orders
#     were BELOW their book's min_base and the venue ACCEPTED every one —
#     including the LIVE Funding Farmer's ZEC (0.037358 vs a min_base of 0.1,
#     sent 17-Jul 10:36) and HYPE (0.33 vs 0.5), and Tide Rider's TRX (38.8 vs
#     40). The guard would have BLOCKED LIVE REAL-MONEY ENTRIES.
#   * min_quote_amount is NOT a $10 floor. The smallest real order ever sent is
#     $5.00 — four of them (perps-donchian-breakout-lighter, HYPE + kBONK,
#     10/11-Jul) — and they FILLED (67.0896, 66.3824, 0.003998, 0.004142).
#
# WHAT THESE FIELDS ACTUALLY GATE IS UNKNOWN (limit orders? resting orders? UI
# display?). Unknown is the honest answer; the venue is the authority and it
# already rejects what it dislikes, with an error the caller surfaces.
#
# THE LESSON, and it is the same one this whole day was about: I found a field
# named `min_base_amount`, ASSUMED it was enforced, derived a "floor" from it,
# and gave the operator a confident number that the outcome ledger refuted in
# one query. An unmeasured constant makes a false verdict — see
# [[unmeasured-assumptions-make-false-verdicts]]. Ask what MEASURED the number.
# Do not rebuild this without a fixture proving the venue actually rejects a
# sub-minimum MARKET order.


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
                 guard_state_key: str | None = None,
                 guard_persist_reject_streak: bool = False):
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
        # RUN-ONCE bots (Ticket Taker) set this so the guard persists its reject
        # streak across relaunches; long-lived bots (Funding Farmer) leave it
        # False so their memory-only streak resets on every redeploy. See
        # EquityGuard(persist_reject_streak=...).
        self._guard_persist_reject_streak = bool(guard_persist_reject_streak)
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
    def _run(self, coro, timeout=30.0, weight=WEIGHT_INFO, gov_timeout=None):
        # gov_timeout=0 -> NON-BLOCKING acquire: take a free token or give up
        # instantly. Telemetry passes 0 so a measurement can never queue ahead
        # of (and delay) a real order. Default None keeps acquire's own 120s.
        _kw = {} if gov_timeout is None else {"timeout": gov_timeout}
        if not self.gov.acquire(weight=weight, **_kw):
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
        # [2026-07-17] STATE THE WHEEL THAT SIGNS REAL ORDERS. requirements.txt
        # pins `lighter-sdk>=1.1.1` — UNPINNED — and 1.1.2 shipped 10-Jul, so
        # every image built since resolves to whatever PyPI's latest is on build
        # day. That wheel IS the signer (SignerClient, create_market_order, the
        # Go binary, the nonce manager): a `pip install` at build time can
        # silently swap the code that moves real money, and the born-dark guard
        # models repo-local imports and CANNOT see a pip dep (its own docstring
        # says so).
        #
        # It is NOT pinned here on purpose: either pin moves the signer under a
        # bot holding real positions, and NOBODY HAS MEASURED which version is
        # actually deployed — the build logs are cached, and `lighter.__version__`
        # is stale upstream ("1.0.0", a release PyPI does not even have; use
        # importlib.metadata). Choosing a pin from an INFERENCE is exactly the
        # mistake this file's own min_size_error withdrawal records.
        #
        # So: measure first. Every boot now names its own signer version, which
        # turns "which SDK signs our orders?" from an argument into a grep.
        try:
            import importlib.metadata as _md
            _sdk = _md.version("lighter-sdk")
        except Exception:  # noqa: BLE001 — never let telemetry block a signer
            _sdk = "unknown"
        # State the FACT (the version), not a claim about the repo. The first
        # cut appended "requirements pins >=1.1.1 — UNPINNED", which was true
        # when written and became a LIE the moment the pin landed hours later —
        # a log line asserting something it cannot know. Same class as the
        # comment-honesty fixes: say what you measured, nothing else.
        log.info("lighter signer ready (account %d, key index %d) | "
                 "lighter-sdk %s (this wheel signs real orders)",
                 self.account_index, self.api_key_index, _sdk)

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
            load_state=load, save_state=save,
            persist_reject_streak=self._guard_persist_reject_streak)

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

        # [2026-07-17] KEEP the client id — it is the fill's exact name. It was
        # computed and thrown away, so the fill read had to guess with
        # (side, since_ts) and VWAP everything that matched. Returned ADDITIVELY:
        # every caller in the fleet discards this dict (the taker only tests it
        # for None), so nothing downstream moves.
        _cid = int(time.time() * 1000) % (2 ** 48)
        tx, resp, err = self._run_signer(self.signer.create_market_order(
            market_index=m["id"],
            client_order_index=_cid,
            base_amount=base, avg_execution_price=px, is_ask=not is_long,
            api_key_index=self.api_key_index))
        if err:
            raise VenueError(f"order failed {coin}: {err}")
        return {"tx": getattr(tx, "to_dict", lambda: str(tx))(),
                "resp": getattr(resp, "to_dict", lambda: str(resp))(),
                "client_order_index": _cid}

    def _our_fills(self, trades, is_ask, since_ts, client_id=None):
        """Size-weighted VWAP of OUR fills in a trade list, or None. Shared by
        both read paths so the authoritative and fallback tapes can never
        disagree about what counts as ours.

        [2026-07-17] `client_id` NAMES THE ORDER, and it is what makes this a
        measurement rather than an estimate. VWAP across the partial fills of
        ONE market order is exactly right — that IS the fill price. VWAP across
        DIFFERENT orders is a fabrication: two same-side sells inside the
        `since_ts` window (an open on one lens plus a stop on another) blended
        into a single fake "fill". The old (is_ask, since_ts) match could not
        tell them apart, and the public tape widens the blend from 10 rows of
        OUR trades to 100 rows of the WHOLE market. With the id, neither window
        nor tape choice can corrupt the read.

        Without an id it still falls back to the heuristic, so callers that
        cannot supply one (an exit whose order id was not threaded) are no worse
        off than before — but they get `approx` in the reason so a blended read
        is never mistaken for an exact one.

        OWNERSHIP IS CHECKED ON BOTH PATHS, never replaced by the id. The client
        id is `int(time.time()*1000) % 2**48` — TIMESTAMP-derived and only unique
        PER ACCOUNT, so two accounts ordering in the same millisecond collide.
        My first cut matched on the id ALONE and would have read a stranger's
        fill as ours; the selftest caught it."""
        fills = []
        for t in (trades or []):
            # OURS, always — the id narrows, it never authorises.
            ours_ask = getattr(t, "ask_account_id", None) == self.account_index
            ours_bid = getattr(t, "bid_account_id", None) == self.account_index
            if is_ask and not ours_ask:
                continue
            if not is_ask and not ours_bid:
                continue
            if client_id is not None:
                # our side's client id must match EXACTLY — no window, no blend
                cid = (getattr(t, "ask_client_id", None) if is_ask
                       else getattr(t, "bid_client_id", None))
                if cid is None or int(cid) != int(client_id):
                    continue
            else:
                ts = float(getattr(t, "timestamp", 0) or 0)
                if ts > 1e12:                # ms -> s (venue stamps ms)
                    ts /= 1000.0
                if ts < float(since_ts) - 5:
                    continue
            px = float(getattr(t, "price", 0) or 0)
            sz = abs(float(getattr(t, "size", 0) or 0))
            if px > 0 and sz > 0:
                fills.append((px, sz))
        if not fills:
            return None
        tot = sum(sz for _, sz in fills)
        return sum(px * sz for px, sz in fills) / tot

    def last_fill_detail(self, coin, is_ask, since_ts, lookback=10,
                         client_id=None):
        """[2026-07-17 OBSERVABLE] REAL average fill price for THIS account,
        as (price_or_None, reason). `reason` names WHY a read produced no price
        — the whole point of this method.

        WHY IT EXISTS. `last_fill` returned None for every distinct failure
        through one bare `except`, so a broken read and a genuinely empty tape
        were indistinguishable. MEASURED 17-Jul: the taker's first two REAL
        orders (STRC, 1000BONK) both fell back to the decision price with no
        log line, and the fleet had NO way to tell why — 0 of 57 real-money
        orders in its history carry a measured fill. That is the same defect
        the 17-Jul (g) fix named one level up: "measured 0" and "never
        recorded" must never be conflated. Here: "no fill found" and "the read
        exploded" must never be conflated either.

        TWO TAPES, deliberately. The account-filtered `trades` endpoint is
        AUTHORITATIVE but needs an auth token; the public `recentTrades` needs
        none and carries the same ask_account_id/bid_account_id fields.
        VERIFIED 17-Jul against the venue: our account_index appears in the
        public tape and reproduces both live fills exactly, size to the unit
        (STRC 0.175 @ 85.511 vs a decision 85.629 = 13.78bps; 1000BONK 4580 @
        0.003275 = at mark). So the fallback is a MEASUREMENT, not a guess.
        It is second, not first, because it is a market-wide window: a busy
        book can push our fill out of its 100-row cap, which the
        account-filtered tape cannot do.

        Measurement-only: EVERY path is caught and reported; a broken read can
        never block or unwind an order."""
        if self.signer is None or self.account_index is None:
            return None, "no-signer"
        try:
            _sym, _mult, m = self._resolve(coin)
        except Exception as e:  # noqa: BLE001
            return None, f"resolve-failed:{type(e).__name__}"

        # --- 1) authoritative: account-filtered, auth'd -----------------------
        reason = None
        try:
            auth = self.signer.create_auth_token_with_expiry(
                api_key_index=self.api_key_index)
            if isinstance(auth, tuple):          # sdk returns (token, err)
                auth, _err = auth
                if _err or not auth:
                    reason = f"auth-failed:{str(_err)[:60] or 'empty-token'}"
                    auth = None
            if auth:
                r = self._run(self._order_api.trades(
                    sort_by="timestamp", sort_dir="desc",
                    limit=max(1, min(int(lookback), 100)),
                    authorization=auth, market_id=m["id"],
                    account_index=self.account_index))
                trades = getattr(r, "trades", None) or []
                px = self._our_fills(trades, is_ask, since_ts, client_id)
                if px:
                    return px, ("trades" if client_id is not None
                                else "trades(approx)")
                reason = "no-match:trades" if trades else "empty:trades"
        except Exception as e:  # noqa: BLE001 — never raise from telemetry
            reason = f"api-error:trades:{type(e).__name__}:{str(e)[:60]}"

        # --- 2) fallback: PUBLIC market tape, no auth ------------------------
        # TELEMETRY MUST NEVER STARVE AN ORDER. `_run` blocks up to 120s to
        # acquire, and WEIGHT_ORDER_TX is 6 against a capacity of ~21 — so a
        # measurement burst here could make the NEXT market_open wait, or trip
        # the 429 ladder. Take this tape only from genuinely spare budget:
        # skip (naming the skip) rather than queue behind money.
        with self.gov._lock:                       # noqa: SLF001 — read-only peek
            self.gov._refill()                     # noqa: SLF001
            spare = self.gov.tokens - _TELEMETRY_RESERVE
        if spare < WEIGHT_INFO:
            return None, (f"skipped:budget({self.gov.tokens:.1f} tok, reserve "
                          f"{_TELEMETRY_RESERVE}) after {reason or 'trades-empty'}")
        try:
            r = self._run(self._order_api.recent_trades(
                market_id=m["id"], limit=100), gov_timeout=0)
            trades = getattr(r, "trades", None) or []
            px = self._our_fills(trades, is_ask, since_ts, client_id)
            if px:
                _exact = "" if client_id is not None else "-approx"
                return px, f"recentTrades{_exact}(after {reason or 'trades-empty'})"
            return None, (f"no-match:both({reason or 'trades-empty'})"
                          if trades else f"empty:both({reason or 'trades-empty'})")
        except Exception as e:  # noqa: BLE001
            return None, (f"api-error:recentTrades:{type(e).__name__}"
                          f":{str(e)[:50]} (after {reason or 'trades-empty'})")

    def last_fill(self, coin, is_ask, since_ts, lookback=10, client_id=None):
        """[2026-07-16 FILL RECON] REAL average fill price, or None. Thin
        back-compat wrapper over `last_fill_detail` — same contract, reason
        dropped. Prefer `last_fill_detail`: a caller that cannot say WHY it
        got no price is how the fleet went 57 real orders without one."""
        return self.last_fill_detail(coin, is_ask, since_ts, lookback,
                                    client_id)[0]

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
        _cid = int(time.time() * 1000) % (2 ** 48)   # see market_open: the fill's name
        tx, resp, err = self._run_signer(self.signer.create_market_order(
            market_index=m["id"],
            client_order_index=_cid,
            base_amount=base, avg_execution_price=px, is_ask=is_long,
            reduce_only=True, api_key_index=self.api_key_index))
        if err:
            raise VenueError(f"close failed {coin}: {err}")
        return {"tx": getattr(tx, "to_dict", lambda: str(tx))(),
                "resp": getattr(resp, "to_dict", lambda: str(resp))(),
                "client_order_index": _cid}


def _selftest():
    """[2026-07-17] The first selftest this file has ever had.

    It began life proving a guard (`min_size_error`) that turned out to be
    WRONG — see the withdrawal note at the top of this file. What survives is
    the part that was real: the REGRESSION FIXTURES built from actual orders
    the venue actually accepted. They now pin the REFUTATION, so nobody
    rebuilds the floor I invented.

    Scope is honest: pure surfaces only (`_our_fills`' matching rules and the
    order-minimum facts). The loop/signer need a venue and are not covered.
    """
    class _Trade:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _Fake:
        account_index = 7
        _our_fills = LighterClient._our_fills

    f = _Fake()          # bound method: f._our_fills(trades, ...) passes self

    # --- THE REFUTATION, pinned as executable fact -------------------------
    # These are REAL orders the venue ACCEPTED. Any future "minimum order"
    # guard must let every one of them through, or it is wrong the same way.
    ACCEPTED_REAL_ORDERS = [
        # (coin,   size,        px,        book min_base, note)
        ("ZEC",    0.037358,    535.4,     0.1,   "LIVE Funding Farmer, 17-Jul 10:36"),
        ("HYPE",   0.33,        59.06,     0.5,   "LIVE Funding Farmer, 17-Jul 05:29"),
        ("TRX",    38.8102,     0.32208,   40.0,  "Tide Rider, 17-Jul 07:42"),
        ("HYPE",   0.0745,      67.0896,   0.5,   "$5.00 order — and it FILLED"),
        ("kBONK",  1250.6,      0.003998,  500.0, "$5.00 order — and it FILLED"),
    ]
    for coin, size, px, min_base, note in ACCEPTED_REAL_ORDERS:
        ntl = size * px
        assert size < min_base or ntl < 10.0, (
            f"{coin}: fixture must actually violate a claimed minimum, else it "
            f"proves nothing")
    # the two facts those orders establish:
    assert any(s < mb for _, s, _, mb, _ in ACCEPTED_REAL_ORDERS), \
        "min_base_amount is NOT enforced — 16 of 56 real orders were under it"
    assert any(s * p < 10.0 for _, s, p, _, _ in ACCEPTED_REAL_ORDERS), \
        "min_quote_amount is NOT a $10 floor — $5 orders filled"

    # --- _our_fills: the client-id match is EXACT, no blending -------------
    t_ours_a = _Trade(timestamp=1_700_000_000_000, price=100.0, size=1.0,
                      ask_account_id=7, bid_account_id=9, ask_client_id=111)
    t_ours_b = _Trade(timestamp=1_700_000_000_000, price=200.0, size=1.0,
                      ask_account_id=7, bid_account_id=9, ask_client_id=222)
    t_theirs = _Trade(timestamp=1_700_000_000_000, price=999.0, size=5.0,
                      ask_account_id=8, bid_account_id=9, ask_client_id=333)
    since = 1_699_999_999_000 / 1000.0
    trades = [t_ours_a, t_ours_b, t_theirs]

    # with an id: EXACTLY that order, never blended with our other same-side fill
    assert f._our_fills(trades, True, since, client_id=111) == 100.0
    assert f._our_fills(trades, True, since, client_id=222) == 200.0
    # without an id: the OLD heuristic blends our two orders into a fiction —
    # this is the defect the client id removes, pinned so it cannot come back
    # unnoticed. 150.0 is the average of two DIFFERENT orders: not a fill price.
    assert f._our_fills(trades, True, since) == 150.0, \
        "id-less path blends — that is why callers must pass client_id"
    # NEVER counts someone else's trade — even when the client id MATCHES.
    # The id is time.time()*1000 % 2**48: unique per ACCOUNT, not globally, so
    # two accounts ordering in the same millisecond collide. My first cut
    # matched on the id alone and this fixture caught it.
    t_collide = _Trade(timestamp=1_700_000_000_000, price=999.0, size=5.0,
                       ask_account_id=8, bid_account_id=9, ask_client_id=111)
    assert f._our_fills([t_collide], True, since, client_id=111) is None, \
        "a client-id COLLISION with another account must never read as our fill"
    assert f._our_fills(trades, True, since, client_id=333) is None
    # partial fills of ONE order DO vwap — that is correct, it IS the fill
    p1 = _Trade(timestamp=1_700_000_000_000, price=100.0, size=1.0,
                ask_account_id=7, bid_account_id=9, ask_client_id=111)
    p2 = _Trade(timestamp=1_700_000_000_000, price=102.0, size=3.0,
                ask_account_id=7, bid_account_id=9, ask_client_id=111)
    assert f._our_fills([p1, p2], True, since, client_id=111) == 101.5

    print("venues.lighter_client _selftest OK (min-order floor REFUTED and "
          "pinned; client-id match exact, id-less path blends)")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    print("venues/lighter_client.py — library; run: python3 -m venues.lighter_client --selftest")
