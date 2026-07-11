#!/usr/bin/env python3
"""
market_context.py — 🛰️ fleet market-context collector (INSTRUMENT-FIRST).

WHY (2026-07-11)
  Backtests killed every blunt regime gate (market-heat, BTC-vol: both fail the
  both-halves bar — see scripts/backtest_funding_leverage.py runs). The factors
  with real causal claims (open interest, liquidation cascades, cross-venue
  funding dispersion) have NO public history to backtest — so the fleet's
  doctrine applies: LOG FIRST, gate later. This daemon collects those factors
  and publishes them as durable state; the trading bots attach a snapshot to
  every entry they ledger. In a few weeks the joined dataset (decision +
  context -> outcome) validates or kills each factor with numbers.

  NOTHING here changes trading behaviour. No bot acts on this data until a
  factor passes the both-halves validation bar on the fleet's OWN evidence.

WHAT IT WRITES (bot_state rows)
  * "market-context" (every LOOP_SECONDS): per-coin OI notional + 1h/24h OI
    change, funding apr, premium bps, Binance forced-liquidation notional
    (5m/1h rolling), plus globals (mean|apr| heat, BTC 1h realized vol).
  * "coin-quality" (every QUALITY_EVERY_H): the fleet's own measured per-coin
    execution + outcome stats from venue_orders / paper_trades — the one input
    validated by construction.

SOURCES (all free, no keys)
  * Hyperliquid metaAndAssetCtxs — OI / funding / premium for every perp, 1 call.
  * Binance futures !forceOrder@arr websocket — liquidation tape (guarded: if
    the stream is unreachable from this host, liq fields are simply absent).
"""
import json
import logging
import os
import sys
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime, timezone

import bot_pnl_store as store

BOT = "market-context"
HL_INFO = "https://api.hyperliquid.xyz/info"
BINANCE_WS = "wss://fstream.binance.com/ws/!forceOrder@arr"

LOOP_SECONDS = int(os.environ.get("MCTX_LOOP_SECONDS", "300"))
QUALITY_EVERY_H = float(os.environ.get("MCTX_QUALITY_EVERY_H", "6"))
TOP_N = int(os.environ.get("MCTX_TOP_N", "60"))   # bound the state row size

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(BOT)

# Binance futures symbol -> fleet symbol (strip USDT; k-prefix the 1000x memes)
_BINANCE_MAP = {"1000BONK": "kBONK", "1000SHIB": "kSHIB", "1000PEPE": "kPEPE",
                "1000FLOKI": "kFLOKI", "1000RATS": "kRATS"}


def _fleet_sym(binance_sym):
    s = binance_sym.replace("USDT", "").replace("USDC", "")
    return _BINANCE_MAP.get(s, s)


def hl_asset_ctxs():
    """{coin: {oi_ntl, funding_apr, premium_bps, mark}} for every HL perp."""
    body = json.dumps({"type": "metaAndAssetCtxs"}).encode()
    req = urllib.request.Request(HL_INFO, data=body,
                                 headers={"Content-Type": "application/json"})
    meta, ctxs = json.loads(urllib.request.urlopen(req, timeout=20).read())
    out = {}
    for u, c in zip(meta.get("universe") or [], ctxs or []):
        try:
            mark = float(c.get("markPx") or 0)
            oi = float(c.get("openInterest") or 0)
            out[u["name"]] = {
                "oi_ntl": oi * mark,
                "funding_apr": float(c.get("funding") or 0) * 24 * 365,
                "premium_bps": float(c.get("premium") or 0) * 1e4,
                "mark": mark,
            }
        except (TypeError, ValueError, KeyError):
            continue
    return out


class LiqTape:
    """Rolling Binance forced-liquidation notional per fleet coin. Guarded:
    if the ws is unreachable (some cloud IPs), rolling sums just stay empty."""

    def __init__(self):
        self.events = deque()            # (ts, coin, usd)
        self.lock = threading.Lock()
        self.connected = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            import websockets.sync.client as wsc
        except Exception:  # noqa: BLE001
            log.warning("websockets lib unavailable — liquidation tape disabled.")
            return
        backoff = 1
        while True:
            try:
                with wsc.connect(BINANCE_WS, open_timeout=15) as ws:
                    self.connected = True
                    backoff = 1
                    log.info("liquidation tape connected (binance !forceOrder).")
                    while True:
                        o = json.loads(ws.recv(timeout=120)).get("o") or {}
                        try:
                            usd = float(o["ap"]) * float(o["q"])
                            coin = _fleet_sym(o["s"])
                        except (KeyError, TypeError, ValueError):
                            continue
                        with self.lock:
                            self.events.append((time.time(), coin, usd))
            except Exception as e:  # noqa: BLE001
                self.connected = False
                log.warning("liquidation ws dropped (%s); retry in %ds", e, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)

    def rolling(self):
        """{coin: {liq_5m, liq_1h}} + totals, trimming events older than 1h."""
        now = time.time()
        out = {}
        with self.lock:
            while self.events and now - self.events[0][0] > 3600:
                self.events.popleft()
            for ts, coin, usd in self.events:
                rec = out.setdefault(coin, {"liq_5m": 0.0, "liq_1h": 0.0})
                rec["liq_1h"] += usd
                if now - ts <= 300:
                    rec["liq_5m"] += usd
        return out


def coin_quality():
    """The fleet's own measured per-coin stats (validated by construction):
    execution costs from venue_orders (14d) + outcomes from paper_trades (30d)."""
    conn = store._get_conn()  # reuse the guarded shared connection
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT coin, count(*), avg(abs(slippage_bps)), avg(spread_bps)
                FROM venue_orders WHERE at > now() - interval '14 days'
                GROUP BY coin""")
            q = {r[0]: {"orders_14d": r[1],
                        "slip_bps": round(float(r[2]), 2) if r[2] is not None else None,
                        "spread_bps": round(float(r[3]), 2) if r[3] is not None else None}
                 for r in cur.fetchall()}
            cur.execute("""
                SELECT pair, count(*),
                       sum(case when pnl_abs > 0 then 1 else 0 end),
                       sum(case when reason like '%%stop%%' then 1 else 0 end)
                FROM paper_trades WHERE closed_at > (now() - interval '30 days')::text
                GROUP BY pair""")
            for pair, closes, wins, stops in cur.fetchall():
                rec = q.setdefault(pair, {})
                rec.update({"closes_30d": closes, "wins_30d": wins,
                            "stops_30d": stops})
        return q
    except Exception as e:  # noqa: BLE001
        log.warning("coin-quality query failed: %s", e)
        return None


def main():
    once = "--once" in sys.argv
    tape = LiqTape()
    oi_hist = {}      # hour_ts -> {coin: oi_ntl}; restart-safe via state
    btc_marks = deque(maxlen=25)   # (hour_ts, mark) for 24h realized vol
    _saved = store.load_state(BOT) or {}
    oi_hist = {int(k): v for k, v in (_saved.get("oi_hist") or {}).items()}
    btc_marks.extend((int(t), m) for t, m in (_saved.get("btc_marks") or []))
    last_quality = 0.0

    log.info("market-context collector | loop=%ds | top %d coins by OI | "
             "quality table every %.0fh | INSTRUMENT-ONLY (no bot acts on this "
             "until it validates)", LOOP_SECONDS, TOP_N, QUALITY_EVERY_H)

    while True:
        t0 = time.time()
        try:
            ctxs = hl_asset_ctxs()
        except Exception as e:  # noqa: BLE001
            log.warning("HL asset ctxs unavailable: %s", e)
            ctxs = {}

        if ctxs:
            hour = int(t0 // 3600) * 3600
            oi_hist[hour] = {c: v["oi_ntl"] for c, v in ctxs.items()}
            for h in [h for h in oi_hist if h < hour - 25 * 3600]:
                oi_hist.pop(h, None)
            if ctxs.get("BTC"):
                if not btc_marks or btc_marks[-1][0] != hour:
                    btc_marks.append((hour, ctxs["BTC"]["mark"]))

            liq = tape.rolling()
            aprs = [abs(v["funding_apr"]) for v in ctxs.values()]
            rets = [(b / a - 1) for (_, a), (_, b) in
                    zip(list(btc_marks)[:-1], list(btc_marks)[1:]) if a]
            btc_vol = (sum(r * r for r in rets) / len(rets)) ** 0.5 if len(rets) > 3 else None

            top = sorted(ctxs.items(), key=lambda kv: -kv[1]["oi_ntl"])[:TOP_N]
            h1 = oi_hist.get(hour - 3600, {})
            h24 = oi_hist.get(hour - 24 * 3600, {})
            coins = {}
            for c, v in top:
                coins[c] = {
                    "oi_ntl": round(v["oi_ntl"]),
                    "oi_chg_1h": (round(v["oi_ntl"] / h1[c] - 1, 4)
                                  if h1.get(c) else None),
                    "oi_chg_24h": (round(v["oi_ntl"] / h24[c] - 1, 4)
                                   if h24.get(c) else None),
                    "funding_apr": round(v["funding_apr"], 4),
                    "premium_bps": round(v["premium_bps"], 2),
                    **{k: round(x) for k, x in (liq.get(c) or {}).items()},
                }
            snapshot = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "heat_mean_apr": round(sum(aprs) / len(aprs), 4) if aprs else None,
                "btc_vol_1h": round(btc_vol, 6) if btc_vol is not None else None,
                "liq_tape": tape.connected,
                "coins": coins,
            }
            store.save_state("market-context", snapshot)
            store.save_state(BOT, {"oi_hist": {str(k): v for k, v in oi_hist.items()},
                                   "btc_marks": list(btc_marks)})
            tot_liq = sum((liq.get(c) or {}).get("liq_1h", 0) for c in liq)
            log.info("ctx ok | %d coins | heat %.1f%% | btc vol %s | liq(1h) $%.0fk%s",
                     len(coins), (snapshot["heat_mean_apr"] or 0) * 100,
                     f"{btc_vol:.3%}" if btc_vol is not None else "n/a",
                     tot_liq / 1e3, "" if tape.connected else " [tape down]")
            store.publish(BOT, status="online",
                          extra={"coins": len(coins), "liq_tape": tape.connected,
                                 "heat_mean_apr": snapshot["heat_mean_apr"]})

        if time.time() - last_quality >= QUALITY_EVERY_H * 3600:
            q = coin_quality()
            if q:
                store.save_state("coin-quality",
                                 {"ts": datetime.now(timezone.utc).isoformat(),
                                  "coins": q})
                log.info("coin-quality table refreshed: %d coins", len(q))
            last_quality = time.time()

        if once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")
