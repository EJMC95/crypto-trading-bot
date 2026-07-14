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


def _alert(alerts, key, severity, msg, dedup_h=24):
    """Append an alert unless the same key fired within dedup_h. Returns True
    if it fired. Alerts are the SIGNAL layer only — the only automated ACTION
    anywhere in the fleet is the veto list (restrict-only, below)."""
    now = time.time()
    for a in alerts:
        if a["key"] == key and now - a["ts"] < dedup_h * 3600:
            return False
    alerts.append({"ts": now, "iso": datetime.now(timezone.utc).isoformat(),
                   "key": key, "severity": severity, "msg": msg})
    log.warning("ALERT [%s] %s", severity, msg)
    del alerts[:-50]
    return True


def evaluate_evidence(quality):
    """[2026-07-11 SELF-CORRECT, VETO-ONLY] Turn accumulated evidence into
    (a) alerts and (b) the coin-veto list. HARD PRINCIPLE: automated evidence
    may only RESTRICT the bots (skip a coin, flag a problem) — never widen a
    gate, raise size, or add leverage. Expansion stays human + backtest gated.

    Checks:
      * dislocation census (Snap Back state): any tradeable event (>=150bps)
        -> alert; census milestones -> alert.
      * factor milestones: joined entries(context) -> outcomes sample sizes;
        building-vs-rolling win split with a crude two-proportion z at n>=30.
      * coin quality vetoes: measured slip > 15bps (n>=5) or stop-rate >= 50%
        (n>=5 closes) -> veto entry on that coin; alert on any list CHANGE.
      * live vs shadow divergence (Funding Farmer): PAIRED per-coin per-trade
        pnl_pct comparison on overlapping coins (>=3 coins, gap >1.5pp/trade)
        -> alert. [2026-07-14] Replaced the whole-book equity-ratio check,
        which divided a ~$64 live book against the $1k shadow book — every
        live dollar moved the "gap" ~16x more, and the capital-constrained
        live book holds only the top slots, so the old alert measured base
        size + slot selection, not execution.
    """
    alerts = (store.load_state("fleet-alerts") or {}).get("alerts") or []
    fired = 0

    # --- Snap Back census ---
    sb = store.load_state("lighter-dislocation-lshadow") or {}
    census = sb.get("census") or {}
    total = sum(c.get("count", 0) for c in census.values())
    big = {c: v for c, v in census.items() if v.get("max_bps", 0) >= 150}
    for c, v in big.items():
        fired += _alert(alerts, f"disloc:{c}", "info",
                        f"🧲 tradeable dislocation on {c}: {v['max_bps']:.0f}bps "
                        f"(census {v['count']} events) — Snap Back thesis evidence")
    if total >= 50:
        fired += _alert(alerts, "census:50", "info",
                        f"🧲 dislocation census reached {total} events — worth a review",
                        dedup_h=24 * 7)

    # --- factor sample milestones + significance (joined dataset) ---
    conn = store._get_conn()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT v.raw->'slope'->>'apr_prev' IS NOT NULL AS has_slope,
                           p.pnl_abs > 0 AS win
                    FROM venue_orders v
                    JOIN paper_trades p
                      ON p.bot = v.bot AND p.pair = v.coin
                     AND abs(extract(epoch from p.opened_at::timestamptz
                                     - v.at)) < 900
                    WHERE v.raw->>'leg' = 'open' AND v.raw ? 'mctx'
                      AND p.pnl_abs IS NOT NULL""")
                rows = cur.fetchall()
            n = len(rows)
            if n and n >= 30:
                fired += _alert(alerts, f"factor-sample:{n // 30}", "info",
                                f"🛰️ joined decision+context dataset at {n} closed "
                                f"trades — factor validation is becoming possible",
                                dedup_h=24 * 7)
        except Exception as e:  # noqa: BLE001
            log.warning("factor-evidence query failed: %s", e)

    # --- coin-quality vetoes (the ONLY automated action, restrict-only) ---
    vetoes = {}
    for coin, q in (quality or {}).items():
        if (q.get("orders_14d") or 0) >= 5 and (q.get("slip_bps") or 0) > 15:
            vetoes[coin] = f"measured slip {q['slip_bps']}bps > 15 (n={q['orders_14d']})"
        closes = q.get("closes_30d") or 0
        stops = q.get("stops_30d") or 0
        if closes >= 5 and stops / closes >= 0.5:
            vetoes[coin] = f"stop rate {stops}/{closes} >= 50% (30d)"
    prev = (store.load_state("coin-vetoes") or {}).get("coins") or {}
    if set(vetoes) != set(prev):
        added = sorted(set(vetoes) - set(prev))
        removed = sorted(set(prev) - set(vetoes))
        fired += _alert(alerts, f"veto:{','.join(added + removed)}", "action",
                        "🚫 coin veto list changed — "
                        + (f"added {added} " if added else "")
                        + (f"removed {removed}" if removed else "")
                        + f" | now vetoed: {sorted(vetoes) or 'none'}")
    store.save_state("coin-vetoes",
                     {"ts": datetime.now(timezone.utc).isoformat(), "coins": vetoes})

    # --- live vs shadow divergence (execution health, PAIRED per-coin) ---
    # [2026-07-14] Same coin, same signal family, per-trade returns — only
    # execution differs. Trade-count-weighted mean of (live avg pnl_pct −
    # shadow avg pnl_pct) across coins BOTH books closed in the last 7d.
    # Needs >=3 overlapping coins; below that it stays quiet rather than
    # alerting on noise (the 13-Jul +5.4% firing was the old ratio artifact:
    # live 9W/0L on its 3 slots vs shadow 15W/5L on 8, same-coin closes
    # near-identical — SOL +$0.19 live vs +$0.27 shadow).
    try:
        conn2 = store._get_conn()
        if conn2 is None:
            raise LookupError("no DB connection")
        LIVE, SHAD = "perps-funding-lighter-lighter", "perps-funding-lighter-lshadow"
        with conn2.cursor() as cur:
            # closed_at is TEXT (iso); seen_at is a real TIMESTAMPTZ stamped at
            # insert (== close publication time) — filter on that.
            cur.execute("""SELECT bot, pair, AVG(pnl_pct), COUNT(*) FROM paper_trades
                           WHERE bot IN (%s, %s)
                             AND pnl_pct IS NOT NULL
                             AND seen_at >= now() - interval '7 days'
                           GROUP BY bot, pair""", (LIVE, SHAD))
            per = {}
            for b, pair, avg_pct, n in cur.fetchall():
                per.setdefault(pair, {})[b] = (float(avg_pct), int(n))
        diffs = [(sides[LIVE][0] - sides[SHAD][0],
                  min(sides[LIVE][1], sides[SHAD][1]))
                 for sides in per.values() if LIVE in sides and SHAD in sides]
        n_overlap = len(diffs)
        tot_w = sum(w for _, w in diffs)
        if n_overlap >= 3 and tot_w > 0:
            gap = sum(d * w for d, w in diffs) / tot_w
            if abs(gap) > 0.015:
                fired += _alert(alerts, "live-shadow-gap", "warn",
                                f"⚠️ Funding Farmer live vs shadow PER-TRADE gap "
                                f"{gap:+.2%} across {n_overlap} overlapping coins "
                                f"({tot_w} paired closes) — execution divergence "
                                f"worth investigating")
    except Exception as e:  # noqa: BLE001
        log.warning("divergence check failed: %s", e)

    store.save_state("fleet-alerts", {"alerts": alerts})
    if fired:
        log.warning("evidence evaluation: %d new alert(s).", fired)
    return fired


# [2026-07-12 GO-GREEN] cross-region live-bot watchdog: this collector runs in
# sfo while the LIVE bots run in Southeast Asia — independent failure domains,
# so a region outage that silences the bots can't silence THIS alert. Limits
# sized ~4 missed publishes (the dashboard's stale windows are ~2).
LIVE_FRESHNESS_LIMITS = {
    "perps-funding-lighter-lighter": 1200,    # 300s loop
    "crypto-trend-daily-lighter":    9000,    # hourly loop
}


def check_live_freshness():
    conn = store._get_conn()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT bot, extract(epoch from now()-updated_at) "
                        "FROM bot_pnl WHERE bot = ANY(%s)",
                        (list(LIVE_FRESHNESS_LIMITS),))
            ages = dict(cur.fetchall())
    except Exception as e:  # noqa: BLE001
        log.warning("live-freshness check failed: %s", e)
        return
    alerts = (store.load_state("fleet-alerts") or {}).get("alerts") or []
    fired = 0
    for b, limit in LIVE_FRESHNESS_LIMITS.items():
        age = ages.get(b)
        if age is not None and age > limit:
            fired += _alert(alerts, f"stale-live:{b}", "warn",
                            f"⚠️ LIVE bot {b} last published {age / 60:.0f} min ago "
                            f"(limit {limit / 60:.0f}) — check the Railway service",
                            dedup_h=6)
    if fired:
        store.save_state("fleet-alerts", {"alerts": alerts})


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

        try:
            check_live_freshness()
        except Exception as e:  # noqa: BLE001
            log.warning("live-freshness wrapper failed: %s", e)

        if time.time() - last_quality >= QUALITY_EVERY_H * 3600:
            q = coin_quality()
            if q:
                store.save_state("coin-quality",
                                 {"ts": datetime.now(timezone.utc).isoformat(),
                                  "coins": q})
                log.info("coin-quality table refreshed: %d coins", len(q))
            try:
                evaluate_evidence(q)
            except Exception as e:  # noqa: BLE001
                log.warning("evidence evaluation failed: %s", e)
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
