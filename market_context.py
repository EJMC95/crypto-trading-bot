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
  * Lighter /api/v1/orderBookDetails — mark / index / OI for every book, 1 call.
  * Lighter /api/v1/funding-rates — the venue's own funding, 1 call.
  * Binance futures !forceOrder@arr websocket — liquidation tape (guarded: if
    the stream is unreachable from this host, liq fields are simply absent).
    NOT a Lighter substitute and NOT a purity violation: Lighter publishes no
    liquidation tape, and these feed a SEPARATE field family (liq_5m/liq_1h)
    that no Lighter field could supply. Untouched by the 17-Jul swap below.

[2026-07-17 VENUE SWAP — Hyperliquid -> Lighter]  audit_venue_purity flagged
`host:api.hyperliquid.xyz:44`: this collector fed the LIGHTER-FIRST fleet its
market context off a venue the fleet does not trade. The four quantities are
now sourced from Lighter NATIVELY. Same key names, same units, same consumers.

  VERDICT — the swap is BEHAVIOUR-NEUTRAL BY CONSTRUCTION, not by luck. The
  mctx snapshot is written into the ledger AFTER the order executes
  (lighter_funding_bot.py:1137, `raw={... "mctx": _mctx_slice(...)}`); no
  branch anywhere reads it. It is a DATASET, and the swap re-denominates that
  dataset. Nothing here gates a trade, so nothing here changes one.

  MEASURED HL-vs-Lighter divergence (2026-07-17, 96 overlapping coins) — read
  LIMITATIONS below before joining pre- and post-swap ledger rows:
    mark         median -6.9 bps, max |26 bps|      — same asset, same price.
    funding_apr  median diff -0.0044; |apr| medians 0.1095 (HL) vs 0.1051 (LT)
                 — those ARE the two venues' resting defaults. Conversion goes
                 through funding_basis (8h basis), never 24*365.
    premium_bps  |prem| median 2.4 bps (HL) vs 6.4 bps (LT) — ~2.7x. NOT a
                 bug: a different QUANTITY. See premium_bps in book_ctxs().
    oi_ntl       Lighter/HL notional ratio median 0.052 (p10 0.022, p90 0.117)
                 — Lighter is a ~20x smaller venue. A LEVEL break, not an
                 error; oi_chg_1h/24h are RATIOS and stay comparable.

LIMITATIONS (read before trusting this row)
  * EPOCH BREAK. `heat_mean_apr` (mean |apr| over the venue's own universe)
    measures HL 0.1278 vs Lighter 0.2210 — 1.73x, on DIFFERENT universes
    (Lighter lists 105 books HL does not, incl. equity/commodity perps that
    rest at a lower 0.03504). `heat`, `premium_bps` and `oi_ntl` are NOT
    comparable across 17-Jul. evaluate_evidence()'s joined decision+context
    dataset spans the boundary: any factor study on those three fields must
    split at the swap or it will fit the venue change, not the market.
    oi_chg_1h/24h and btc_vol_1h are ratios and cross the boundary cleanly.
  * COVERAGE MOVED (deliberately, and toward the consumers). HL 232 books vs
    Lighter 201 active; only 96 overlap. 136 HL-only coins are gone — but the
    fleet does not trade them. The two consumers are Lighter bots, so this
    swap ADDS context for 105 Lighter books that previously resolved to an
    empty slice. Coverage is explicit, never silent: a book with no Lighter
    funding row gets funding_apr=None (not 0.0), and a book with no index
    gets premium_bps=None — a missing input reads as "no evidence".
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
import funding_basis
from venues.symbol_map import from_lighter

BOT = "market-context"
# [2026-07-17] The VENUE this organ's raw levels come from. Stamped into the
# persisted snapshot so a future venue swap cannot silently divide one venue's
# open interest by another's — see the VENUE-EPOCH guard in main(). Bump this
# string whenever the price/OI source changes; that is the whole mechanism.
SOURCE = "lighter"
LIGHTER_API = os.environ.get("LIGHTER_API_BASE",
                             "https://mainnet.zklighter.elliot.ai")
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


# ---------------------------------------------------------------------------
# PURE COMPUTE (unit-tested offline via --selftest — no network, no DB)
# ---------------------------------------------------------------------------

def funding_aprs(rows):
    """/funding-rates rows -> {fleet_coin: apr_fraction}, Lighter's OWN rows only.

    The endpoint also republishes binance/bybit/hyperliquid benchmark rows
    (that is how the fleet reads a cross-venue rate without leaving Lighter);
    they are NOT this venue's funding and are skipped here.

    EVERY row on that endpoint — Lighter's included — is quoted on an 8-HOUR
    basis, so the conversion goes through funding_basis. Do NOT write 24*365
    here: that is the 8x bug the fleet fixed on 17-Jul. It was CORRECT in this
    file's old Hyperliquid call (HL quotes hourly) and is wrong for Lighter —
    which is exactly how a venue swap smuggles the bug back in.
    """
    out = {}
    for row in rows or []:
        if row.get("exchange") != "lighter":
            continue
        rate = row.get("rate")
        if rate is None:
            continue          # absent, never 0.0 — a missing rate is not "flat"
        try:
            fleet, _ = from_lighter(row.get("symbol") or "")
            out[fleet] = funding_basis.to_apr(float(rate), "lighter")
        except (TypeError, ValueError):
            continue
    return out


def book_ctxs(books, aprs):
    """orderBookDetails rows + {coin: apr} -> {coin: {oi_ntl, funding_apr,
    premium_bps, mark}} for every ACTIVE book. Key names and units are the
    Hyperliquid call's, unchanged — pnl_dashboard's alert/veto rows and both
    bot consumers read this shape.

    oi_ntl — `open_interest` is in BASE units, so notional = oi * mark. VERIFIED
      against live rows rather than assumed: the Lighter/HL notional ratio holds
      at ~0.03-0.12 across coins whose marks span 63354 (BTC) to 0.072 (DOGE).
      Were the field quote-denominated, that ratio would scale with mark and the
      two ends would differ by ~10^6. They do not. (BTC: 1745 * $63.4k = $110M
      OI — plausible for the venue; $1,745 of total BTC OI would be absurd.)

    premium_bps — Lighter publishes NO premium field. It publishes the two
      ingredients (`mark_price`, `index_price`), and mark-vs-index IS the
      fleet's established Lighter premium (lighter_market_scout.book_stats
      `prem_bps`, same formula) — so this is the venue's own convention, not a
      proxy invented here.
      BUT IT IS NOT HL's `premium`, AND THE OPERATOR MUST KNOW THAT: HL's field
      matches NO instantaneous formula (measured 17-Jul — mark/mid/impact-vs-
      oracle each reproduce it on only 36-44 of 177 coins), because HL publishes
      a SMOOTHED, funding-relevant premium. Ours is instantaneous mark-vs-index.
      Both are "premium"; they are different quantities, and the magnitude gap
      is real (|prem| median 6.4 bps here vs 2.4 bps on HL, ~2.7x).
      No index -> None. A premium is not fabricated from a fallback.
    """
    out = {}
    for b in books or []:
        try:
            if b.get("status") != "active":
                continue
            sym = b.get("symbol")
            mark = float(b.get("mark_price") or 0.0)
            oi = float(b.get("open_interest") or 0.0)
            if not sym or mark <= 0.0:
                continue
            idx = float(b.get("index_price") or 0.0)
            fleet, _ = from_lighter(sym)
            out[fleet] = {
                "oi_ntl": oi * mark,
                # None (not 0.0) when the venue published no rate for this book:
                # heat skips it and the ledger records "unknown" honestly.
                "funding_apr": (aprs or {}).get(fleet),
                "premium_bps": ((mark / idx - 1.0) * 1e4) if idx > 0.0 else None,
                "mark": mark,
            }
        except (TypeError, ValueError, KeyError):
            continue
    return out


# ---------------------------------------------------------------------------
# NETWORK
# ---------------------------------------------------------------------------

def _get(path):
    req = urllib.request.Request(LIGHTER_API + path,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def lighter_ctxs():
    """{coin: {oi_ntl, funding_apr, premium_bps, mark}} for every ACTIVE Lighter
    book. Two calls; raises to the caller's guard (which goes NEUTRAL)."""
    books = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    rows = _get("/api/v1/funding-rates").get("funding_rates") or []
    return book_ctxs(books, funding_aprs(rows))


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


# [2026-07-17 BUS CONTRACT] fleet-alerts was the ONE bot_state key published
# without `updated`/`ttl_sec`. CLAUDE.md's bus contract is unambiguous — "every
# payload carries updated+ttl_sec; consumers go NEUTRAL on stale data" — and
# every other feed the evidence board reads is _fresh()-gated. fleet-alerts
# could not be: with no `updated` to read, `_fresh()` returns False on the
# except branch, so gating it as-written would have blinded the board entirely
# rather than protecting it. The fix belongs at the WRITER: give the payload
# the stamp the contract requires, and the existing gate starts working.
#
# TTL sizing is the load-bearing decision. evaluate_evidence only runs on the
# coin-quality tick (QUALITY_EVERY_H, default 6h), so this payload is EXPECTED
# to be up to ~6h old in normal health — a 6h TTL would flap between "fresh"
# and "stale" on nothing but cadence. Two cadences share one key, so the TTL
# must cover the SLOWER writer plus slack: check_live_freshness re-stamps every
# loop, but only when it fires. 8h = the 6h evidence cadence + 2h slack.
# WHAT THIS IS NOT: the per-alert `ts`/`last_seen` remain the authority on
# whether any INDIVIDUAL alert is current (the board's 6h LIVE_GAP_FRESH_H
# still rules the real-money down-scale). This TTL answers only "is the alerts
# FEED itself still being written?" — a different question, and the one that
# went unasked when the feed's own age was invisible to every reader.
ALERTS_TTL_SEC = int(os.environ.get("MCTX_ALERTS_TTL_SEC", str(8 * 3600)))


def save_alerts(alerts):
    """The single writer for fleet-alerts. Every save carries the bus stamp —
    there is no path that writes this key without one."""
    store.save_state("fleet-alerts", {
        "alerts": alerts,
        "updated": datetime.now(timezone.utc).isoformat(),
        "ttl_sec": ALERTS_TTL_SEC,
    })


def _alert(alerts, key, severity, msg, dedup_h=24):
    """Append an alert unless the same key fired within dedup_h. Returns True
    if it fired. Alerts are the SIGNAL layer only — the only automated ACTION
    anywhere in the fleet is the veto list (restrict-only, below).
    [2026-07-16 AUDIT FIX] a dedup-hit now REFRESHES last_seen (+msg) on the
    existing entry: the board trusts a divergence alert for only 6h, but the
    24h dedup meant a PERSISTING divergence carried a fresh ts once per day —
    the live down-scale reflex was blind ~18h of every 24. last_seen keeps a
    still-confirmed condition visibly current without re-firing notify."""
    now = time.time()
    for a in alerts:
        if a["key"] == key and now - a["ts"] < dedup_h * 3600:
            a["last_seen"] = now
            a["msg"] = msg
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
    # [2026-07-17 IMB-03] the fleet freshness contract (updated+ttl_sec) on
    # the ONE consumed payload of the live-money entry path that lacked it —
    # a dead publisher must read as "no evidence", not as a standing veto
    # set (or a standing all-clear) forever. TTL = 12 missed 5-min cycles.
    store.save_state("coin-vetoes",
                     {"ts": datetime.now(timezone.utc).isoformat(),
                      "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "ttl_sec": 3600, "coins": vetoes})

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

    save_alerts(alerts)
    if fired:
        log.warning("evidence evaluation: %d new alert(s).", fired)
    return fired


# [2026-07-12 GO-GREEN] cross-region live-bot watchdog: this collector runs in
# sfo while the LIVE bots run in Southeast Asia — independent failure domains,
# so a region outage that silences the bots can't silence THIS alert. Limits
# sized ~4 missed publishes (the dashboard's stale windows are ~2).
#
# [2026-07-17 ROSTER] The roster is DERIVED from bot_pnl, not declared here.
# WHY: the declared version was the LAST live-cohort constant in the fleet left
# unswept by the 17-Jul retirement, and it had rotted BOTH ways at once —
#   * it still named `crypto-trend-daily-lighter`, retired that day. A pruned
#     row returns no age, and the old loop's `if age is not None` skipped it in
#     silence: a dead name is indistinguishable from a healthy bot.
#   * it never gained `lighter-ticket-taker-lighter`, the LIVE real-money book
#     that TOOK that slot the same day — so the one watchdog deliberately built
#     to survive a region outage did not know the Ticket Taker existed.
# fleet_respiration.py:57 is the receipt: that sweep EXAMINED this dict, wrote
# down that its semantics differ ("treats it as no-evidence"), and moved on.
# Unrefuted is not checked. A roster that must be remembered is the control
# that already failed — so this one cannot be forgotten, because nobody
# maintains it: `venue_mode == lighter_live` IS the roster, exactly as
# fleet_watchdog_svc.py:137 derives it (the only live-cohort reader that
# survived the swap untouched, because it never hardcoded one).
#
# FAIL-SAFE DIRECTION. Discovery reads the LAST PUBLISHED row, which survives
# the bot's death — a live book whose service dies keeps its row, keeps
# venue=lighter_live, and its `updated_at` simply stops moving. So the case
# this organ exists for (a live bot going dark) is exactly the case discovery
# still catches. The residue is a book that has NEVER published, or one whose
# last publish carried no venue: both are louder, different failures, and
# neither is quieter than the old dict's silent skip.
LIVE_CADENCE_SEC = {
    "perps-funding-lighter-lighter": 1200,    # 💸 Funding Farmer — 300s loop
    "lighter-ticket-taker-lighter":  1200,    # 🎫 Ticket Taker — 300s loop, LIVE 17-Jul
}
# Any live row NOT named above is still watched, at a deliberately slack bar —
# an unknown cadence earns a late page, never no page.
DEFAULT_LIVE_LIMIT = int(os.environ.get("MCTX_DEFAULT_LIVE_LIMIT", "3600"))


def live_freshness_alerts(rows, alerts, now_iso=None):
    """Pure core: [(bot, age_s, equity)] -> alerts fired. Split out so the
    detector is testable without a DB — the `if dry_run`-branch lesson: a
    detective control whose only path needs live Postgres is a control nobody
    has ever seen fire."""
    fired = 0
    for bot, age, equity in rows:
        if age is None:
            continue
        limit = LIVE_CADENCE_SEC.get(bot, DEFAULT_LIVE_LIMIT)
        if age > limit:
            eq = f" (${equity:,.2f} real)" if equity is not None else ""
            fired += _alert(alerts, f"stale-live:{bot}", "warn",
                            f"⚠️ LIVE bot {bot}{eq} last published "
                            f"{age / 60:.0f} min ago (limit {limit / 60:.0f}) "
                            f"— check the Railway service",
                            dedup_h=6)
    return fired


def check_live_freshness():
    conn = store._get_conn()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            # The roster IS the query. No name to forget, no name to rot.
            cur.execute("SELECT bot, extract(epoch from now()-updated_at), equity "
                        "FROM bot_pnl WHERE extra->>'venue' = %s", ("lighter_live",))
            rows = list(cur.fetchall())
    except Exception as e:  # noqa: BLE001
        log.warning("live-freshness check failed: %s", e)
        return
    if not rows:
        # Zero live rows is not "all healthy" — it is the sensor reading blank.
        # Cheap to say, and it is the reading a total prune/outage produces.
        log.warning("live-freshness: NO rows with venue=lighter_live — "
                    "either no live book is publishing, or the venue stamp moved")
        return
    alerts = (store.load_state("fleet-alerts") or {}).get("alerts") or []
    fired = live_freshness_alerts(rows, alerts)
    log.info("live-freshness: %d live row(s) watched (%s), %d alert(s)",
             len(rows), ", ".join(sorted(r[0] for r in rows)), fired)
    if fired:
        save_alerts(alerts)


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
                SELECT split_part(pair, '/', 1), count(*),
                       sum(case when pnl_abs > 0 then 1 else 0 end),
                       sum(case when reason like '%%stop%%' then 1 else 0 end)
                FROM paper_trades WHERE closed_at > (now() - interval '30 days')::text
                GROUP BY 1""")
            # [2026-07-15 AUDIT FIX] keys normalized to base coin so they merge
            # with venue_orders' coin namespace ('NEAR', not 'NEAR/USDC')
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
    # [2026-07-17 VENUE-EPOCH GUARD] oi_hist and btc_marks are RAW LEVELS, and
    # oi_chg_1h/24h divide today's level by a persisted one. The persisted rows
    # were written from HYPERLIQUID; this loop now reads LIGHTER. The two venues
    # hold genuinely different open interest — MEASURED: Lighter/HL oi_ntl ratio
    # has a MEDIAN of 0.052 across the 96 overlapping coins. So a restored HL
    # row would make the FIRST post-swap loop compute Lighter_OI / HL_OI - 1 and
    # publish a ~-94% OI COLLAPSE, fleet-wide, on every coin at once — a change
    # that never happened, on the exact key ("OI is dumping") a human or organ
    # would read as a crisis. Reviewers measured 35/35 boundary-crossing top-60
    # coins reading >50% collapse, 25/35 >90%.
    # A history whose SOURCE has changed is not history, it is a different
    # series wearing the same key. Discard it and re-accumulate: 24h of a
    # missing oi_chg is honest; a fabricated -94% is not. regime_oracle stamps
    # its tape the same way, "because it must not lie about the tape".
    _prev_src = _saved.get("source")
    if _prev_src != SOURCE:
        if _saved.get("oi_hist") or _saved.get("btc_marks"):
            log.warning("VENUE EPOCH: saved state is from source=%r, now %r — "
                        "dropping oi_hist/btc_marks (raw levels are NOT "
                        "comparable across venues; oi_chg re-accumulates over "
                        "~24h rather than publishing a phantom move)",
                        _prev_src, SOURCE)
    else:
        oi_hist = {int(k): v for k, v in (_saved.get("oi_hist") or {}).items()}
        btc_marks.extend((int(t), m) for t, m in (_saved.get("btc_marks") or []))
    last_quality = 0.0

    log.info("market-context collector | loop=%ds | top %d coins by OI | "
             "quality table every %.0fh | INSTRUMENT-ONLY (no bot acts on this "
             "until it validates)", LOOP_SECONDS, TOP_N, QUALITY_EVERY_H)

    while True:
        t0 = time.time()
        try:
            ctxs = lighter_ctxs()
        except Exception as e:  # noqa: BLE001
            log.warning("Lighter market ctxs unavailable: %s", e)
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
            # funding_apr is None for a book the venue published no rate for
            # (see book_ctxs) — heat SKIPS it rather than averaging in a 0.0
            # that would silently drag the fleet's heat gauge toward zero.
            aprs = [abs(v["funding_apr"]) for v in ctxs.values()
                    if v["funding_apr"] is not None]
            rets = [(b / a - 1) for (_, a), (_, b) in
                    zip(list(btc_marks)[:-1], list(btc_marks)[1:]) if a]
            btc_vol = (sum(r * r for r in rets) / len(rets)) ** 0.5 if len(rets) > 3 else None

            top = sorted(ctxs.items(), key=lambda kv: -kv[1]["oi_ntl"])[:TOP_N]
            h1 = oi_hist.get(hour - 3600, {})
            h24 = oi_hist.get(hour - 24 * 3600, {})
            coins = {}
            for c, v in top:
                # funding_apr / premium_bps are None-able since the 17-Jul swap
                # (missing venue rate / missing index) — round() would raise on
                # None and take the whole snapshot down with it.
                _apr, _prem = v["funding_apr"], v["premium_bps"]
                coins[c] = {
                    "oi_ntl": round(v["oi_ntl"]),
                    "oi_chg_1h": (round(v["oi_ntl"] / h1[c] - 1, 4)
                                  if h1.get(c) else None),
                    "oi_chg_24h": (round(v["oi_ntl"] / h24[c] - 1, 4)
                                   if h24.get(c) else None),
                    "funding_apr": round(_apr, 4) if _apr is not None else None,
                    "premium_bps": round(_prem, 2) if _prem is not None else None,
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
            # `source` STAMPS the venue these raw levels came from, so the next
            # boot can tell whether they are comparable (see the VENUE-EPOCH
            # guard in main()). Without it, a venue swap silently divides one
            # venue's OI by another's.
            store.save_state(BOT, {"oi_hist": {str(k): v for k, v in oi_hist.items()},
                                   "btc_marks": list(btc_marks),
                                   "source": SOURCE})
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

        # [2026-07-17 verify fix] coin-vetoes LIVENESS re-stamp every loop:
        # the veto CONTENT changes only per QUALITY_EVERY_H evaluation, but
        # `updated` attests the publisher is ALIVE — without this, the 1h
        # ttl went stale for ~5 of every 6 hours on a healthy service and
        # the live consumer discarded the set (adversarial-verify caught
        # the cadence mismatch before it shipped). Now ttl 3600 really does
        # mean "12 missed 5-min loops = dead publisher".
        try:
            _cv = store.load_state("coin-vetoes") or {}
            if _cv.get("coins") is not None:
                _cv["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                _cv["ttl_sec"] = 3600
                store.save_state("coin-vetoes", _cv)
        except Exception:  # noqa: BLE001
            pass

        if once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _selftest():
    """Offline. Guards the CONTRACT (key names/units the consumers read) and
    the two ways this swap could go wrong silently: the 8x funding bug and a
    fabricated premium."""
    # --- funding_aprs: basis + row selection -------------------------------
    rows = [
        {"exchange": "lighter", "symbol": "ETH", "rate": 9.6e-05},
        {"exchange": "hyperliquid", "symbol": "ETH", "rate": 9.6e-05},  # bench
        {"exchange": "binance", "symbol": "ETH", "rate": 5.0e-04},      # bench
        {"exchange": "lighter", "symbol": "1000BONK", "rate": 1.0e-04},
        {"exchange": "lighter", "symbol": "NORATE", "rate": None},
        {"exchange": "lighter", "symbol": "JUNK", "rate": "abc"},
    ]
    a = funding_aprs(rows)
    # the verified Lighter anchor: 9.6e-05 per 8h -> 10.512% TRUE apr
    assert abs(a["ETH"] - 0.10512) < 1e-6, a["ETH"]
    # NEGATIVE FIXTURE — the 8x bug this swap could smuggle back in. If someone
    # "simplifies" funding_basis away to `rate * 24 * 365`, ETH reads 0.84096
    # and every number stays self-consistent and merely wrong by 8x. Fail LOUD.
    assert abs(a["ETH"] - 9.6e-05 * 24 * 365) > 0.7, "8x funding bug reintroduced"
    assert a["ETH"] == funding_basis.to_apr(9.6e-05, "lighter")
    # bench rows are other venues' funding, not ours — they must not leak in
    # (both bench rows here are ETH; a leak would overwrite the real rate)
    assert abs(a["ETH"] - 0.10512) < 1e-6, "cross-venue bench row leaked"
    assert from_lighter("1000BONK")[0] == "kBONK"
    assert "kBONK" in a and "1000BONK" not in a, "fleet symbol namespace broken"
    assert "NORATE" not in a and "JUNK" not in a, "missing/junk rate must be absent"

    # --- book_ctxs: units, contract, coverage ------------------------------
    books = [
        {"symbol": "BTC", "status": "active", "mark_price": "63354.1",
         "index_price": "63381.5", "open_interest": 1744.18314},
        {"symbol": "ETH", "status": "active", "mark_price": 1845.0,
         "index_price": 1845.0, "open_interest": 100.0},
        {"symbol": "1000BONK", "status": "active", "mark_price": 2.0,
         "index_price": 2.0, "open_interest": 10.0},
        {"symbol": "NOIDX", "status": "active", "mark_price": 10.0,
         "index_price": 0, "open_interest": 5.0},          # no index
        {"symbol": "HALT", "status": "inactive", "mark_price": 5.0,
         "index_price": 5.0, "open_interest": 1.0},        # not tradeable
        {"symbol": "BROKEN", "status": "active", "mark_price": None,
         "index_price": 1.0, "open_interest": 1.0},
    ]
    c = book_ctxs(books, a)
    # the OUTPUT CONTRACT: exact key names + units pnl_dashboard's consumers and
    # both bots read. A rename here is a silent None at the far end.
    assert set(c["BTC"]) == {"oi_ntl", "funding_apr", "premium_bps", "mark"}, set(c["BTC"])
    assert c["BTC"]["mark"] == 63354.1                       # strings coerced
    # oi_ntl: BASE units * mark == notional (VERIFIED against live rows)
    assert abs(c["BTC"]["oi_ntl"] - 1744.18314 * 63354.1) < 1e-6
    assert abs(c["ETH"]["oi_ntl"] - 184500.0) < 1e-9
    # premium_bps: mark-vs-index, in BPS, signed (mark < index -> negative)
    assert abs(c["BTC"]["premium_bps"] - (63354.1 / 63381.5 - 1) * 1e4) < 1e-9
    assert c["BTC"]["premium_bps"] < 0 and abs(c["BTC"]["premium_bps"]) < 10
    assert c["ETH"]["premium_bps"] == 0.0                    # mark == index
    # FAIL-SAFE, both directions: a missing input is None, never a fabricated
    # number and never a 0.0 that reads as "flat".
    assert c["NOIDX"]["premium_bps"] is None, "premium fabricated without an index"
    assert c["ETH"]["funding_apr"] == 0.10512
    # BTC is ACTIVE and priced but the venue published no funding row for it,
    # so its apr is unknown. The COVERAGE TRAP in miniature: the book must still
    # appear (its OI/mark/premium are real) with funding_apr None — dropping the
    # coin, or calling it 0.0, are both lies. (This assertion is here because the
    # first draft of this test asserted heat saw 3 rates and it saw 2 — the code
    # was right and the test was wrong. Kept as the fixture that proves it.)
    assert "BTC" in c and c["BTC"]["funding_apr"] is None, \
        "a priced book with no venue rate must survive with funding_apr None"
    assert c["BTC"]["oi_ntl"] > 0 and c["BTC"]["premium_bps"] is not None
    assert "NOIDX" in c and c["NOIDX"]["funding_apr"] is None, \
        "a book with no venue rate must read None, not 0.0"
    assert "HALT" not in c, "inactive book must be skipped"
    assert "BROKEN" not in c, "junk row must be skipped"
    assert "kBONK" in c and c["kBONK"]["funding_apr"] == funding_basis.to_apr(1.0e-04, "lighter")

    # heat: the main loop's aggregation must SKIP None, not crash or count 0.0.
    # Exactly the 2 books with a venue rate (ETH, kBONK) — NOT 4, and not a
    # 0.0 from BTC/NOIDX dragging the fleet's heat gauge toward zero.
    aprs = [abs(v["funding_apr"]) for v in c.values() if v["funding_apr"] is not None]
    assert len(aprs) == 2 and all(x > 0 for x in aprs), aprs
    assert abs(sum(aprs) / len(aprs) - 0.10731) < 1e-5, sum(aprs) / len(aprs)

    # the snapshot's round() guards must survive a None-able field: this is the
    # exact expression main() builds, run over a ctx that CONTAINS Nones.
    for _c, v in c.items():
        _apr, _prem = v["funding_apr"], v["premium_bps"]
        row = {"oi_ntl": round(v["oi_ntl"]),
               "funding_apr": round(_apr, 4) if _apr is not None else None,
               "premium_bps": round(_prem, 2) if _prem is not None else None}
        assert isinstance(row["oi_ntl"], int)
    assert json.dumps({"coins": c})   # the row is published as JSON — None is fine, NaN is not

    # --- the cross-region live-bot watchdog (17-Jul) -----------------------
    # NEGATIVE FIXTURE FIRST: the detector must FIRE. This control had never
    # been seen firing — its only path needed live Postgres, so `pure core +
    # thin query` is what makes it testable at all. Synthetic rows throughout:
    # it asserts the DETECTOR, not today's fleet, so it cannot start failing on
    # good news (a healthy fleet) or pass on bad news (an empty roster).
    a = []
    assert live_freshness_alerts([("perps-funding-lighter-lighter", 60.0, 66.26)], a) == 0
    assert a == [], "a FRESH live bot must not alert"
    a = []
    assert live_freshness_alerts([("perps-funding-lighter-lighter", 5000.0, 66.26)], a) == 1
    assert "perps-funding-lighter-lighter" in a[0]["msg"] and a[0]["severity"] == "warn"
    assert "$66.26 real" in a[0]["msg"], a[0]["msg"]   # name the money at stake

    # THE ACTUAL 17-Jul BUG: a live row absent from LIVE_CADENCE_SEC must still
    # be watched, at DEFAULT_LIVE_LIMIT. The Ticket Taker went live into a slot
    # whose previous occupant was retired; the old dict-driven loop iterated its
    # own keys, so an unlisted live book was not late — it was invisible.
    a = []
    assert live_freshness_alerts([("some-future-live-bot", DEFAULT_LIVE_LIMIT + 1, 12.0)], a) == 1
    assert "some-future-live-bot" in a[0]["msg"], "an UNLISTED live row must still be watched"
    a = []
    assert live_freshness_alerts([("some-future-live-bot", DEFAULT_LIVE_LIMIT - 1, 12.0)], a) == 0

    # a None age (row present, age unreadable) makes NO claim rather than a
    # false page — but note this is the ONLY silent path, and it is now
    # unreachable from the query, which cannot return a NULL age for a live row.
    a = []
    assert live_freshness_alerts([("perps-funding-lighter-lighter", None, 1.0)], a) == 0

    # ROT GUARD: the cadence map is a display/tuning aid now, not the roster —
    # but a retired name in it is still a lie about what we watch, and the
    # retirement list is the only authority on that. Same guard evidence_board
    # and fleet_proprioception carry; this module is where it was missing.
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as _retired
        _rot = set(LIVE_CADENCE_SEC) & set(_retired)
        assert not _rot, (
            f"LIVE_CADENCE_SEC names RETIRED row(s) {sorted(_rot)}. The roster "
            f"itself is derived (venue=lighter_live), so this no longer blinds "
            f"the watchdog — but a retired name here still advertises a cadence "
            f"for a book that cannot publish. Remove them.")
    except ImportError:      # not in this image — the guard is best-effort
        pass

    print("market_context self-tests passed (LIGHTER-native: 8h funding basis "
          "via funding_basis, mark-vs-index premium, BASE-unit OI, fleet "
          "symbols, coverage explicit, output contract held; live-freshness "
          "detector fires + unlisted live rows watched + no retired cadence).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped by user.")
