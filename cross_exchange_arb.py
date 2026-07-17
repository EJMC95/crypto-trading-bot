#!/usr/bin/env python3
"""
Cross-exchange arbitrage DETECTION + PAPER-TRADING engine.
Kraken / Binance / Coinbase, depth-aware, pre-funded model.

What this does
--------------
- For every trading pair that exists on TWO OR MORE of the configured
  exchanges, it compares prices and looks for a gap big enough to clear taker
  fees on BOTH legs: buy the asset where it is cheapest (lowest ask) and sell
  it where it is dearest (highest bid).
- PRE-FUNDED model: it assumes you already hold balances on every exchange, so
  a gap is captured INSTANTLY by buying on one venue and selling on the other
  from existing inventory (you rebalance later). No blockchain transfer, no
  withdrawal fee, no transfer latency is modelled here. That makes this the
  optimistic/upper-bound view of the edge — real life adds rebalancing cost.
- Places NO real orders. Reads only public market data (no API keys needed).
- Detection is depth-aware: a gap that looks good on best bid/ask is re-priced
  by WALKING both order books for `PAPER_TRADE_SIZE`, so the logged number is
  what you'd really fill at, slippage included.

IMPORTANT REALITY CHECK
-----------------------
A real cross-exchange edge has to beat: taker fee on the buy + taker fee on the
sell + the spread + slippage at size + the cost/dwell of keeping capital parked
on multiple venues + eventual rebalancing (withdrawal) fees. Persistent, large,
risk-free gaps between major USD/USDT pairs on Kraken/Binance/Coinbase are rare
and short-lived — market makers eat them in milliseconds. Treat a flat balance
as the honest, expected result, not a bug.

EPOCH 2 — HONEST COUNTER + WIDE NET (2026-07-15, agenda item 10)
----------------------------------------------------------------
The v1 counter was an odometer: bookings required modelled edge >= 0 (losses
impossible) and a PERSISTING gap was re-booked every ~19s scan (~190x/hour),
so a couple of stale-book/collision episodes printed +$5,225 in ~a day.
Epoch 2 changes the unit of account to the EPISODE:
  - one booking per (symbol, buy_venue, sell_venue) gap EPISODE; the episode
    re-arms only after the gap closes below REARM_EDGE (or falls silent);
  - bookable pairs need a 24h volume floor on BOTH venues (dead books can no
    longer print fills — or drive the liquid gauge);
  - the old odometer is parked in extra.legacy; balances restart at $0 with
    every new booked dollar carrying a paper_trades ledger row;
  - each booking records a CAPACITY CURVE (the same edge repriced at
    $250/$1k/$5k/$25k) — the number that would ever justify real execution;
  - a census (bot_state 'gapscout-census') records episodes, the >5% artifact
    band, and a cross-quote (USD vs USDT/USDC via live stablecoin rate)
    dislocation gauge for the majors.
Detection is meant to WIDEN over time (venues via ARB_EXCHANGES/tuning,
prefilter via tuning): the evidence board's growth rail (fleet_tuning.py)
may widen these bounded levers autonomously when the census runs quiet —
booking stays strict no matter how wide detection gets.

Usage
-----
    pip install ccxt
    python cross_exchange_arb.py                 # live depth-aware detection + paper trading
    python cross_exchange_arb.py --once          # single scan then exit (smoke test)
    python cross_exchange_arb.py --selftest      # offline math checks, no network

Config is at the top of the file.
"""

import argparse
import csv
import json
import os
import time
import traceback
from datetime import datetime, timezone

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)

# fleet_tuning: the evidence board's bounded growth rail. Optional import so
# the scanner runs unchanged if the module isn't shipped alongside it.
try:
    import fleet_tuning as tuning
except Exception:  # noqa: BLE001
    tuning = None

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

# Exchanges to compare. ccxt ids. Public data only. Env-overridable so the
# net can widen without a code change; the growth rail can hot-add from the
# whitelist in fleet_tuning (gapscout.extra_exchanges) at runtime.
# NOTE: US-region-friendly default set. Binance.com is NOT used because it
# returns HTTP 451 ("restricted location") from Railway's region. We use
# `coinbaseexchange` (Coinbase Exchange / ex-Pro) rather than `coinbase`
# (Advanced Trade) because the former exposes a working fetch_tickers.
EXCHANGES = [s.strip() for s in os.environ.get(
    "ARB_EXCHANGES", "kraken,coinbaseexchange,gemini").split(",") if s.strip()]
MAX_VENUES = int(os.environ.get("ARB_MAX_VENUES", "6"))   # scan-time bound

# Base-tier TAKER fee per exchange (fraction). Arb fills must be taker. These
# are conservative public defaults; the engine uses each market's own ccxt
# 'taker' fee when ccxt reports one, and falls back to these otherwise. Lower
# only if your real 30-day volume earns a better tier on that venue.
TAKER_FEE = {
    "kraken": 0.0026,           # Kraken Pro spot taker, base tier
    "coinbaseexchange": 0.0060, # Coinbase Exchange taker, base tier
    "gemini": 0.0040,           # Gemini ActiveTrader taker, base tier
    "kucoin": 0.0010,           # second-tier venues (growth-rail candidates)
    "gateio": 0.0020,
    "mexc": 0.0010,
    "bitget": 0.0010,
    "htx": 0.0020,
}
DEFAULT_TAKER = 0.0040   # used for any exchange not listed above

# Only consider pairs whose quote currency is one of these. Keeps the universe
# to liquid, settle-able pairs and avoids comparing exotic quote assets.
# NOTE: USD and USDT are treated as DIFFERENT quotes on purpose — they are not
# the same asset, and pretending so invents fake edges on a stablecoin wobble.
QUOTE_WHITELIST = {"USD", "USDT", "USDC", "EUR"}

# Stage-1 -> Stage-2 gate. Stage 1 ranks venues on a REFERENCE price (mid of
# bid/ask when a venue reports it, else last trade) because several exchanges
# (Coinbase Exchange, Gemini) do not return bid/ask in their bulk fetch_tickers
# — only `last`. A pair whose raw cross-venue reference gap is at least this
# gets a (costly) depth-aware order-book confirmation in Stage 2, where the real
# bid/ask + slippage are computed from order books. Keep it low enough to catch
# near-misses but high enough to bound book fetches.
PREFILTER_GAP = 0.0020   # 0.20% raw last/mid price gap between venues

# Cross-venue gaps larger than this are treated as DATA ARTIFACTS, not real
# arbitrage, and are skipped entirely (never book-checked, never booked). On a
# widest-net scan the big "edges" are almost always a ticker-symbol collision
# (the same string is a DIFFERENT asset on each venue, e.g. an obscure "VELO"
# or "SUP") or a stale/illiquid last price. Genuine cross-exchange edges on the
# same real asset are sub-1%; anything above this ceiling is noise.
MAX_PLAUSIBLE_GAP = 0.05   # 5%

# [2026-07-14 SIGNAL FIX — Jul-14 review verdict] The published best_top_pct
# was the max over ~340 pairs including illiquid/collision-prone books, so the
# signal bus's "dislocation" printed 4.6% junk and was ruled unusable as a
# stress gauge. The bus now gets liquid_top_pct: the same max restricted to
# real majors that exist unambiguously on these venues — when THESE books
# dislocate, that is genuine market stress. Raw best_top_pct is still
# published for the scanner's own diagnostics.
DISLOC_BASES = {s.strip() for s in os.environ.get(
    "DISLOC_BASES", "BTC,ETH,SOL,XRP,ADA,DOGE,LTC,LINK,DOT,AVAX").split(",") if s.strip()}

# Hard cap on order books fetched per scan (2 per confirmed pair). Rate guard.
MAX_BOOK_FETCHES = 30

# Log a confirmed (depth-aware) opportunity if its net edge is at least this.
MIN_NET_EDGE = -0.005

# ---- Epoch-2 honesty knobs (2026-07-15, agenda item 10) ---------------------
EPOCH = 2
# BOOKABLE floor: TOUCH DEPTH measured from the REAL order books Stage 2
# already fetches — a pair may only book when BOTH legs have at least this
# much quote value resting within TOUCH_DEPTH_PCT of that book's own mid.
# This kills dead/hollow books (the DOT/USDT-class artifact: a CBX book
# doing $2.8k/day was the 15-Jul "1% majors dislocation") using executable
# liquidity that is fresh by construction. NOTE: deliberately NOT a
# bulk-ticker volume/bid-ask bar — live probes showed CBX and Gemini
# structurally omit volume AND bid/ask from fetch_tickers (only `last`),
# so any bulk-ticker floor disqualifies 2 of 3 venues outright.
MIN_TOUCH_DEPTH = float(os.environ.get("ARB_MIN_TOUCH_DEPTH", "5000"))
TOUCH_DEPTH_PCT = 0.01
# An open episode re-arms (closes) when its depth edge net of haircuts falls
# below this; it also closes after EPISODE_STALE_S without being seen above
# the prefilter (gap gone or book died).
REARM_EDGE = -0.001
EPISODE_STALE_S = 900.0
# Capacity curve: each booked episode reprices its edge at these clip sizes.
CAPACITY_SIZES = [250.0, 1000.0, 5000.0, 25000.0]

# ---- Execution-reality haircuts (2026-07-03) --------------------------------
# Fees + book-walking slippage were always modelled, but fills were booked
# INSTANTLY at snapshot prices. That hides two real costs:
#   LATENCY: you cross the spread hundreds of ms after observing the gap,
#   racing market makers; cross-venue edges on majors decay within ~1s. Treat
#   as an adverse move between observation and fill.
#   REBALANCE: the pre-funded model accumulates inventory skew (base piles up
#   where you buy, quote where you sell); moving it back costs withdrawal fees
#   + spread, amortized here per fill.
# The REAL balance (published as pnl_abs) subtracts both; the old optimistic
# number is kept in parallel (extra.gross_balance) so the bases can be compared.
LATENCY_HAIRCUT = 0.0010    # 10 bps adverse move between snapshot and fill
REBALANCE_HAIRCUT = 0.0005  # 5 bps amortized inventory-rebalancing cost

# Notional size of each simulated trade, in the pair's quote currency. The
# depth-aware edge is computed for THIS size, so slippage scales with it.
PAPER_TRADE_SIZE = 1000.0

# Seconds between full scans.
POLL_SECONDS = 10.0

# Order-book depth (levels) to pull per side.
BOOK_LEVELS = 50

# Heartbeat: even when nothing clears the bar, write one row every this many
# seconds recording the best top-of-book cross edge, so the dashboard/digest
# always has trend data instead of an empty file. 0 disables.
HEARTBEAT_SECONDS = 900.0   # 15 min

# ---- Lighter venue premium (2026-07-14, advisory — see the Jul-14 review) ---
# The CEX legs above say nothing about Lighter, the venue the fleet actually
# trades. Lighter's public orderBookDetails returns mark_price AND index_price
# per book, so the venue premium (mark/index - 1) — how rich/cheap Lighter
# trades vs its own external-index oracle — comes from one keyless call.
# Published in extra.lighter_* each scan; fleet_risk mirrors it to the signal
# bus. PUBLISH-ONLY: no trader consumes it until a review earns the wiring.
# The fetch is guarded — Lighter's WAF has blocked other REST endpoints from
# Railway before; any failure simply omits the fields (consumers fail-safe on
# the bus TTL, same contract as everything else on it).
LIGHTER_API = os.environ.get(
    "LIGHTER_API",
    "https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails")
# Per-book premiums published for the family-relevant books only (bus stays
# small); the stress gauge below still spans every liquid book.
LIGHTER_WATCH = [s.strip() for s in os.environ.get(
    "LIGHTER_WATCH", "BTC,ETH,SOL,SPY,QQQ,XAU").split(",") if s.strip()]
# Books below this daily quote volume are excluded from the stress gauge —
# a stale mark on a dead book is not venue stress.
LIGHTER_MIN_QVOL = float(os.environ.get("LIGHTER_MIN_QVOL", "100000"))
# Lighter is polled at most this often regardless of scan cadence.
LIGHTER_POLL_SECONDS = float(os.environ.get("LIGHTER_POLL_SECONDS", "60"))

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
OPP_LOG = os.path.join(LOG_DIR, "cross_arb_opportunities.csv")

CSV_HEADER = [
    "timestamp", "symbol", "buy_ex", "sell_ex",
    "top_net_pct", "depth_net_pct", "paper_pnl", "filled", "virtual_balance",
]

# ----------------------------------------------------------------------------
# CORE MATH (pure functions — unit-testable with no network)
# ----------------------------------------------------------------------------


def top_of_book_edge(ask_buy, bid_sell, fee_buy, fee_sell):
    """Pre-funded cross edge on best prices only (Stage 1).

    Spend 1 unit of quote buying the base at `ask_buy` on the cheap venue
    (taker fee_buy), then sell that base at `bid_sell` on the dear venue
    (taker fee_sell). Returns net fraction (e.g. 0.002 = +0.20%), or None.
    """
    if not ask_buy or not bid_sell or ask_buy <= 0:
        return None
    base = (1.0 / ask_buy) * (1.0 - fee_buy)     # base bought per 1 quote
    quote_out = base * bid_sell * (1.0 - fee_sell)
    return quote_out - 1.0


def walk_buy(quote_amount, asks, fee):
    """Spend `quote_amount` up the asks. Returns (base_received, filled_fully).

    Models slippage by eating successive ask levels. ccxt levels are
    [price, size]; some venues append a 3rd element — unpack defensively.
    """
    spent, got = 0.0, 0.0
    for level in asks:
        price, size = level[0], level[1]
        if price <= 0 or size <= 0:
            continue
        take = min(quote_amount - spent, price * size)
        if take <= 0:
            break
        got += take / price
        spent += take
        if spent >= quote_amount - 1e-9:
            break
    return got * (1.0 - fee), spent >= quote_amount - 1e-6


def walk_sell(base_amount, bids, fee):
    """Sell `base_amount` down the bids. Returns (quote_received, filled_fully)."""
    sold, got = 0.0, 0.0
    for level in bids:
        price, size = level[0], level[1]
        if price <= 0 or size <= 0:
            continue
        take = min(base_amount - sold, size)
        if take <= 0:
            break
        got += take * price
        sold += take
        if sold >= base_amount - 1e-12:
            break
    return got * (1.0 - fee), sold >= base_amount - 1e-9


def depth_edge(quote_size, asks_buy, bids_sell, fee_buy, fee_sell):
    """Stage 2: depth-aware net edge + P&L for capturing the gap at size.

    Buy `quote_size` worth of base up the cheap venue's asks, then sell exactly
    that base down the dear venue's bids. Returns (net, pnl, filled) or
    (None, None, None) if not priceable.
    """
    if not asks_buy or not bids_sell:
        return None, None, None
    base, buy_filled = walk_buy(quote_size, asks_buy, fee_buy)
    if base <= 0:
        return None, None, None
    quote_out, sell_filled = walk_sell(base, bids_sell, fee_sell)
    net = quote_out / quote_size - 1.0
    return net, quote_out - quote_size, (buy_filled and sell_filled)


def lighter_premiums(books, watch, min_qvol):
    """Venue premiums from Lighter orderBookDetails rows (pure, unit-tested).

    Premium = (mark_price / index_price - 1) in bps: positive means Lighter
    trades RICH vs its external-index oracle (a taker long pays the premium;
    persistent premium is the leading indicator of positive funding).

    Returns (watch_prems, med_abs_bps, max_abs_bps, n) where watch_prems maps
    each watched symbol to its premium and med/max span every active book at
    or above the volume floor — the fleet-wide venue-stress gauge. Books
    missing a positive mark/index are skipped; (…, None, None, 0) if nothing
    qualifies.
    """
    prems, stress = {}, []
    for b in books:
        try:
            if b.get("status") != "active":
                continue
            mark = float(b.get("mark_price") or 0.0)
            idx = float(b.get("index_price") or 0.0)
            if mark <= 0.0 or idx <= 0.0:
                continue
            bps = (mark / idx - 1.0) * 10_000.0
            if float(b.get("daily_quote_token_volume") or 0.0) >= min_qvol:
                stress.append(abs(bps))
            if b.get("symbol") in watch:
                prems[b["symbol"]] = round(bps, 1)
        except (TypeError, ValueError):
            continue
    if not stress:
        return prems, None, None, 0
    stress.sort()
    return (prems, round(stress[len(stress) // 2], 1),
            round(stress[-1], 1), len(stress))


def book_mid(book):
    """Two-sided top-of-book mid from a fetched order book; None when either
    side is empty (a one-sided book is dead or halted — never bookable)."""
    try:
        bid = book["bids"][0][0]
        ask = book["asks"][0][0]
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
    except (KeyError, IndexError, TypeError):
        pass
    return None


def touch_depth(levels, mid, pct=TOUCH_DEPTH_PCT):
    """Quote value resting within pct of mid on ONE side of a real book —
    the bookable-liquidity floor. A hollow book (wide quotes, dust near
    touch) scores ~0 here no matter what its ticker claims."""
    if not mid or mid <= 0:
        return 0.0
    total = 0.0
    for level in levels or []:
        price, size = level[0], level[1]
        if price and size and price > 0 and size > 0 \
                and abs(price / mid - 1.0) <= pct:
            total += price * size
    return total


def fresh_mid(t):
    """Bid/ask mid ONLY when the venue reports both in the bulk tickers —
    the anti-stale bar for the gauge and for bookability. None otherwise
    (a `last`-only venue can still be book-CHECKED, just never booked)."""
    if not t:
        return None
    bid, ask = t.get("bid"), t.get("ask")
    if bid and ask and bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    return None


def update_episode(episodes, key, symbol, route, net_eff, filled, now_ts):
    """Episode state machine (pure; epoch-2 unit of account).

    Returns (should_book, closed_record). An ELIGIBLE signal (net_eff >= 0
    and both legs fillable) BOOKS only when no episode is open on this key;
    while the episode stays open the same gap is tracked, never re-booked.
    The episode closes (re-arms) when the pair is re-checked and its edge
    has fallen below REARM_EDGE."""
    eligible = net_eff is not None and net_eff >= 0.0 and filled
    ep = episodes.get(key)
    if eligible:
        if ep is None:
            episodes[key] = {"symbol": symbol, "route": route,
                             "opened": now_ts, "last_seen": now_ts,
                             "peak_eff": net_eff}
            return True, None
        ep["last_seen"] = now_ts
        ep["peak_eff"] = max(ep["peak_eff"], net_eff)
        return False, None
    if ep is not None and net_eff is not None and net_eff < REARM_EDGE:
        closed = dict(episodes.pop(key), closed=now_ts, close_reason="rearm")
        return False, closed
    if ep is not None:                       # hovering between bars: keep open
        ep["last_seen"] = now_ts
    return False, None


def sweep_stale_episodes(episodes, now_ts, stale_s=EPISODE_STALE_S):
    """Close episodes not seen above the prefilter for stale_s (gap vanished
    without a re-check, or the book died). Returns the closed records."""
    closed = []
    for key in [k for k, ep in episodes.items()
                if now_ts - ep["last_seen"] >= stale_s]:
        closed.append(dict(episodes.pop(key), closed=now_ts,
                           close_reason="stale"))
    return closed


def capacity_curve(asks_buy, bids_sell, fee_buy, fee_sell, haircut,
                   sizes=None):
    """The same books repriced at multiple clip sizes — the edge's CAPACITY.
    Answers the only question that could ever justify real execution: how
    much money the find absorbs before fees+depth (+haircuts) eat it."""
    out = []
    for size in (sizes or CAPACITY_SIZES):
        net, _pnl, filled = depth_edge(size, asks_buy, bids_sell,
                                       fee_buy, fee_sell)
        out.append({"size": size,
                    "net_eff_pct": round((net - haircut) * 100, 4)
                    if net is not None else None,
                    "filled": bool(filled)})
    return out


def cross_quote_gap(prices_by_quote, usd_rates):
    """Max USD-normalized gap between DIFFERENT-quote books of one base.

    prices_by_quote: {"USD": {ex: mid}, "USDT": {ex: mid}, ...} (fresh mids
    only). usd_rates: {quote: quote->USD rate} from LIVE stablecoin books —
    never an assumed 1:1 par. Quotes without a live rate are skipped.
    Returns (gap_frac, cheap_label, dear_label) or (None, None, None);
    labels are "venue:quote". Same-quote gaps are the main scan's business —
    this gauge only reports across quotes (the stablecoin-stress signal)."""
    entries = []
    for quote, per_ex in (prices_by_quote or {}).items():
        rate = (usd_rates or {}).get(quote)
        if not rate or rate <= 0:
            continue
        for ex, mid in (per_ex or {}).items():
            if mid and mid > 0:
                entries.append((mid * rate, f"{ex}:{quote}", quote))
    best = (None, None, None)
    for px_a, lab_a, q_a in entries:
        for px_b, lab_b, q_b in entries:
            if q_a == q_b or px_a <= 0:
                continue
            gap = px_b / px_a - 1.0
            if best[0] is None or gap > best[0]:
                best = (gap, lab_a, lab_b)
    return best


# ----------------------------------------------------------------------------
# GRAPH BUILDING
# ----------------------------------------------------------------------------


def fee_for(ex_id, market):
    """Per-market taker fee: use ccxt's reported taker if present, else default."""
    if market is not None:
        t = market.get("taker")
        if isinstance(t, (int, float)) and t > 0:
            return float(t)
    return TAKER_FEE.get(ex_id, DEFAULT_TAKER)


def build_symbol_map(markets_by_ex):
    """symbol -> {ex_id: market} for every spot/active pair on >=2 exchanges
    whose quote is in QUOTE_WHITELIST."""
    sym_to_ex = {}
    for ex_id, markets in markets_by_ex.items():
        for sym, m in markets.items():
            if not (m.get("spot") and m.get("active")):
                continue
            if m.get("quote") not in QUOTE_WHITELIST:
                continue
            sym_to_ex.setdefault(sym, {})[ex_id] = m
    # keep only symbols present on at least two venues
    return {s: exm for s, exm in sym_to_ex.items() if len(exm) >= 2}


# ----------------------------------------------------------------------------
# LIVE ENGINE
# ----------------------------------------------------------------------------


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_log():
    if not os.path.exists(OPP_LOG):
        with open(OPP_LOG, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADER)


def log_opp(row):
    with open(OPP_LOG, "a", newline="") as f:
        csv.writer(f).writerow(row)


_lighter_cache = {"t": 0.0, "extra": {}}


def lighter_extra():
    """Guarded Lighter premium fetch -> extra fields, {} on ANY failure.

    Cached LIGHTER_POLL_SECONDS so the scan cadence doesn't hammer the API.
    Never raises into the scan loop.
    """
    if time.time() - _lighter_cache["t"] < LIGHTER_POLL_SECONDS:
        return _lighter_cache["extra"]
    extra = {}
    try:
        import urllib.request
        req = urllib.request.Request(
            LIGHTER_API, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        books = payload.get("order_book_details") or []
        prems, med, mx, n = lighter_premiums(
            books, LIGHTER_WATCH, LIGHTER_MIN_QVOL)
        if n:
            extra = {"lighter_prem_bps": prems,
                     "lighter_prem_med_bps": med,
                     "lighter_prem_max_bps": mx,
                     "lighter_prem_n": n}
    except Exception as e:  # noqa: BLE001 — WAF/timeout/schema: skip quietly
        print(f"[{now_iso()}] lighter premium fetch failed (skipping): {e!r}")
    _lighter_cache.update(t=time.time(), extra=extra)
    return extra


def ref_prices(symbol, exmarkets, tickers_by_ex):
    """Per-exchange reference price for Stage-1 ranking.

    Uses the bid/ask mid when a venue reports both, else the last trade price.
    This is necessary because some venues (Coinbase Exchange, Gemini) return
    bid=ask=None in bulk fetch_tickers and only populate `last`. The real
    bid/ask + slippage are recovered from order books in Stage 2.
    """
    out = {}
    for ex_id in exmarkets:
        t = tickers_by_ex.get(ex_id, {}).get(symbol)
        if not t:
            continue
        bid, ask, last = t.get("bid"), t.get("ask"), t.get("last")
        if bid and ask:
            out[ex_id] = (bid + ask) / 2.0
        elif last:
            out[ex_id] = last
    return out


def run_live(once=False):
    import ccxt  # imported here so --selftest works without ccxt installed

    exchanges, markets_by_ex, failed_venues = {}, {}, set()

    def add_venue(ex_id):
        """Init + load markets for one venue. False (and process-lifetime
        blacklist) on any failure — a geo-blocked or broken venue never
        stalls the scan loop. Used at boot AND for growth-rail hot-adds."""
        if ex_id in exchanges or ex_id in failed_venues or len(exchanges) >= MAX_VENUES:
            return False
        try:
            ex = getattr(ccxt, ex_id)({"enableRateLimit": True})
            markets_by_ex[ex_id] = ex.load_markets()
            exchanges[ex_id] = ex
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[{now_iso()}] venue {ex_id} unavailable (blacklisted): {e}")
            failed_venues.add(ex_id)
            markets_by_ex.pop(ex_id, None)
            return False

    print(f"[{now_iso()}] Loading markets for {', '.join(EXCHANGES)} ...")
    for ex_id in EXCHANGES:
        add_venue(ex_id)
    if len(exchanges) < 2:
        print(f"[{now_iso()}] need >=2 working exchanges, have {len(exchanges)}. Exiting.")
        return

    sym_map = build_symbol_map(markets_by_ex)
    print(
        f"[{now_iso()}] {len(sym_map)} pairs listed on >=2 venues. "
        f"Pre-funded model, taker fees "
        + ", ".join(f"{k} {TAKER_FEE.get(k, DEFAULT_TAKER)*100:.2f}%" for k in exchanges)
        + f". Depth-aware @ {PAPER_TRADE_SIZE:.0f}/trade."
    )
    print(
        f"[{now_iso()}] Detection-only + paper trading. NO real orders.\n"
        f"           Stage-1 ticker scan -> Stage-2 depth confirm (<= "
        f"{MAX_BOOK_FETCHES} books/scan). Logging to {OPP_LOG}\n"
    )

    ensure_log()
    # [2026-07-14 PERSISTENCE FIX] The paper balances reset to $0 on every
    # redeploy (the same bug class fixed for the sniper on 25-Jun). Restore
    # from bot_state so the cumulative bases survive restarts; saved next to
    # every publish below. Guarded: no DB -> starts at 0 as before.
    _saved = store.load_state("scanner-cross-exchange-arb") or {}
    virtual_balance = float(_saved.get("virtual_balance") or 0.0)  # REAL basis
    gross_balance = float(_saved.get("gross_balance") or 0.0)      # optimistic
    # [2026-07-15 EVIDENCE] booked-fill record (W/L) — the dashboard showed
    # trades=0 forever because only the running balance was published, and the
    # 14-Jul review flagged the balance as unauditable (no per-fill rows).
    n_booked = int(_saved.get("booked") or 0)
    n_wins = int(_saved.get("wins") or 0)
    n_losses = int(_saved.get("losses") or 0)
    legacy = _saved.get("legacy")
    # [2026-07-15 EPOCH 2 — agenda item 10] the v1 counters were an odometer
    # (re-booked persisting gaps, no floors). Park them once and restart at
    # $0 so every printed dollar from here is episode-deduped, floored, and
    # ledger-backed. One-way migration; the old numbers stay visible in extra.
    if int(_saved.get("epoch") or 1) < EPOCH:
        legacy = {"real": round(virtual_balance, 2),
                  "gross": round(gross_balance, 2),
                  "booked": n_booked, "wins": n_wins, "losses": n_losses,
                  "retired": now_iso(),
                  "note": "v1 odometer: re-booked persisting gaps (agenda item 10)"}
        print(f"[{now_iso()}] EPOCH {EPOCH}: v1 odometer parked "
              f"(real {virtual_balance:+.2f} / gross {gross_balance:+.2f}) — "
              f"honest counter restarts at $0")
        virtual_balance = gross_balance = 0.0
        n_booked = n_wins = n_losses = 0
        epoch_started = time.time()
    else:
        epoch_started = float(_saved.get("epoch_started") or time.time())
        try:
            # ledger rows are written at booking time, the state blob at scan
            # end — if a state write failed the ledger carries the truth.
            # (Safe across the epoch reset: the ledger shipped 15-Jul with
            # zero pre-epoch rows, so every row IS an epoch-2 booking.)
            _agg = store.fetch_paper_aggregate("scanner-cross-exchange-arb")
            if _agg and _agg["closed"] > n_booked:
                n_booked, n_wins, n_losses = _agg["closed"], _agg["wins"], _agg["losses"]
        except Exception:
            pass
    episodes = _saved.get("episodes") or {}       # open gap episodes
    recent_eps = _saved.get("recent_episodes") or []
    last_close_ts = float(_saved.get("last_episode_close_ts") or 0.0)
    census_day = _saved.get("census_day") or {}
    if virtual_balance or gross_balance or episodes:
        print(f"[{now_iso()}] restored epoch-{EPOCH} state: "
              f"real {virtual_balance:+.2f} / gross {gross_balance:+.2f} / "
              f"{len(episodes)} open episodes")
    last_heartbeat = 0.0
    best_top = best_liquid = None   # safe defaults if the very first scan errors
    xq_best = (None, None, None, None)
    liquid_conf = None
    quiet_hours = 0.0
    eff_prefilter, eff_books = PREFILTER_GAP, MAX_BOOK_FETCHES

    while True:
        t0 = time.time()
        # Growth-rail levers: bounded in fleet_tuning's registry, authored by
        # the evidence board, expiring back to these defaults on their own.
        if tuning is not None:
            eff_prefilter = tuning.get_lever("gapscout.prefilter_gap", PREFILTER_GAP)
            eff_books = tuning.get_lever("gapscout.max_book_fetches", MAX_BOOK_FETCHES)
            # [2026-07-17 IMB-12] the venue set is DERIVED each scan from the
            # operator's base EXCHANGES + whatever the lever asserts NOW —
            # hot-added venues DROP the moment the lever expires or stops
            # naming them, so the rail's promised TTL auto-revert is real for
            # this lever too (it was one-way-until-redeploy: the only expand
            # lever in the fleet whose revert was unreachable). An open
            # census episode on a dropped venue closes via the census's own
            # staleness path — booking honesty is the scanner's, as ever.
            _extra = {e.strip() for e in
                      str(tuning.get_lever("gapscout.extra_exchanges", "")
                          ).split(",") if e.strip()}
            _vchanged = False
            for ex_id in sorted(_extra):
                if ex_id not in exchanges and add_venue(ex_id):
                    _vchanged = True
                    print(f"[{now_iso()}] growth rail: venue {ex_id} hot-added")
            for ex_id in [e for e in list(exchanges)
                          if e not in EXCHANGES and e not in _extra]:
                exchanges.pop(ex_id, None)
                markets_by_ex.pop(ex_id, None)
                _vchanged = True
                print(f"[{now_iso()}] growth rail: venue {ex_id} dropped "
                      f"(lever expired/unasserted — TTL revert)")
            if _vchanged:
                sym_map = build_symbol_map(markets_by_ex)
                print(f"[{now_iso()}] venue set {sorted(exchanges)} -> "
                      f"{len(sym_map)} pairs")

        # Stage 0: one fetch_tickers per exchange.
        tickers_by_ex = {}
        for ex_id, ex in exchanges.items():
            try:
                tickers_by_ex[ex_id] = ex.fetch_tickers()
            except Exception as e:
                print(f"[{now_iso()}] {ex_id} ticker fetch failed: {e}")
        if len(tickers_by_ex) < 2:
            time.sleep(POLL_SECONDS)
            continue

        try:
            today = now_iso()[:10]
            if census_day.get("day") != today:
                census_day = {"day": today, "opened": 0, "booked_pnl": 0.0}
            # Stage 1: rank every cross-venue pair on a reference price (mid
            # when bid/ask present, else last). The number here is the RAW
            # cross-venue price gap (no fees yet) — fees + real bid/ask +
            # slippage + the TOUCH-DEPTH bookability floor are all applied
            # in Stage 2 from real order books (bulk tickers on CBX/Gemini
            # carry only `last`, so stage 1 can rank but never book).
            ranked = []
            best_top = None     # (gap, symbol, buy_ex, sell_ex) — widest net
            best_liquid = None  # majors' widest REFERENCE gap (stage-2 confirms)
            artifacts = []      # > MAX_PLAUSIBLE_GAP — the census's >5% band
            xq_prices = {}      # majors' fresh mids by quote, for cross-quote
            for symbol, exmarkets in sym_map.items():
                refs = ref_prices(symbol, exmarkets, tickers_by_ex)
                if len(refs) < 2:
                    continue
                buy_ex = min(refs, key=refs.get)    # cheapest reference price
                sell_ex = max(refs, key=refs.get)   # dearest reference price
                if buy_ex == sell_ex or refs[buy_ex] <= 0:
                    continue
                gap = refs[sell_ex] / refs[buy_ex] - 1.0
                base = symbol.split("/")[0]
                if base in DISLOC_BASES:
                    quote = symbol.split("/")[-1]
                    for ex_id in exmarkets:
                        m = fresh_mid(tickers_by_ex.get(ex_id, {}).get(symbol))
                        if m:
                            xq_prices.setdefault(base, {}).setdefault(quote, {})[ex_id] = m
                if gap > MAX_PLAUSIBLE_GAP:
                    artifacts.append((gap, symbol, buy_ex, sell_ex))
                    continue
                if best_top is None or gap > best_top[0]:
                    best_top = (gap, symbol, buy_ex, sell_ex)
                if (base in DISLOC_BASES
                        and (best_liquid is None or gap > best_liquid[0])):
                    best_liquid = (gap, symbol, buy_ex, sell_ex)
                if gap >= eff_prefilter:
                    ranked.append((gap, symbol, buy_ex, sell_ex))
            ranked.sort(reverse=True)
            artifacts.sort(reverse=True)

            # [2026-07-16 AUDIT FIX] a persisting gap crowded OUT of the
            # stage-2 book budget (or freshly restored after a restart) used
            # to age past EPISODE_STALE_S and re-book as a NEW episode on its
            # next confirmation — double-counting census opened/n_booked (the
            # growth rail reads them). A stage-1 sighting above the prefilter
            # now keeps an ALREADY-OPEN episode alive; it cannot BOOK anything
            # (booking stays depth-confirmed in stage 2).
            for _g, _sym, _bex, _sex in ranked:
                _ep = episodes.get(f"{_sym}|{_bex}|{_sex}")
                if _ep is not None:
                    _ep["last_seen"] = t0

            # Cross-quote gauge: USD vs USDT/USDC books of the same major,
            # normalized through LIVE stablecoin rates (never assumed par).
            usd_rates = {"USD": 1.0}
            for q in ("USDT", "USDC"):
                for ex_id in exchanges:
                    m = fresh_mid(tickers_by_ex.get(ex_id, {}).get(f"{q}/USD"))
                    if m:
                        usd_rates[q] = m
                        break
            xq_best = (None, None, None, None)   # gap, base, cheap, dear
            for base, pq in xq_prices.items():
                g, cheap, dear = cross_quote_gap(pq, usd_rates)
                if g is not None and (xq_best[0] is None or g > xq_best[0]):
                    xq_best = (g, base, cheap, dear)

            # Stage 2: confirm the top candidates depth-aware at trade size,
            # and apply the TOUCH-DEPTH bookability floor from the real books.
            confirmed, fetches, depth_rejected = [], 0, 0
            liquid_books = None    # real books of the best MAJOR candidate
            for net_top, symbol, buy_ex, sell_ex in ranked:
                if fetches + 2 > eff_books:
                    break
                try:
                    ab = exchanges[buy_ex].fetch_order_book(symbol, limit=BOOK_LEVELS)
                    bb = exchanges[sell_ex].fetch_order_book(symbol, limit=BOOK_LEVELS)
                    fetches += 2
                except Exception:
                    continue
                if best_liquid and symbol == best_liquid[1] \
                        and (buy_ex, sell_ex) == (best_liquid[2], best_liquid[3]):
                    liquid_books = (ab, bb)
                fee_b = fee_for(buy_ex, sym_map[symbol].get(buy_ex))
                fee_s = fee_for(sell_ex, sym_map[symbol].get(sell_ex))
                net_d, pnl, filled = depth_edge(
                    PAPER_TRADE_SIZE, ab.get("asks", []), bb.get("bids", []),
                    fee_b, fee_s,
                )
                if net_d is None:
                    continue
                # bookability floor: enough REAL liquidity near both books'
                # own mids. A hollow/one-sided book can be logged, never booked.
                depth_ok = (
                    touch_depth(ab.get("asks"), book_mid(ab)) >= MIN_TOUCH_DEPTH
                    and touch_depth(bb.get("bids"), book_mid(bb)) >= MIN_TOUCH_DEPTH)
                if not depth_ok:
                    depth_rejected += 1
                # carry the books + fees forward: a booked episode records its
                # entry/exit tops AND a capacity curve from these same books.
                confirmed.append((net_d, net_top, pnl, filled, depth_ok, symbol,
                                  buy_ex, sell_ex,
                                  ab.get("asks") or [], bb.get("bids") or [],
                                  fee_b, fee_s))

            confirmed.sort(key=lambda c: c[0], reverse=True)

            closed_eps, booked_this_scan = [], False
            for (net_d, net_top, pnl, filled, depth_ok, symbol, buy_ex, sell_ex,
                 ab_asks, bb_bids, fee_b, fee_s) in confirmed:
                if net_d < MIN_NET_EDGE:
                    continue
                # Effective edge after execution-reality haircuts. EPOCH 2:
                # the EPISODE is the unit of account — one booking per gap
                # episode, tracked (never re-booked) while it persists.
                net_eff = net_d - LATENCY_HAIRCUT - REBALANCE_HAIRCUT
                pnl_eff = pnl - PAPER_TRADE_SIZE * (LATENCY_HAIRCUT + REBALANCE_HAIRCUT)
                key = f"{symbol}|{buy_ex}|{sell_ex}"
                booked, closed = update_episode(
                    episodes, key, symbol, f"{buy_ex}->{sell_ex}",
                    net_eff, filled and depth_ok, t0)
                if closed:
                    closed_eps.append(closed)
                if booked:
                    booked_this_scan = True
                    virtual_balance += pnl_eff
                    gross_balance += pnl   # same episode, no haircuts (basis A/B)
                    n_booked += 1
                    if pnl_eff > 0:
                        n_wins += 1
                    else:
                        n_losses += 1
                    census_day["opened"] = int(census_day.get("opened") or 0) + 1
                    census_day["booked_pnl"] = round(
                        float(census_day.get("booked_pnl") or 0.0) + pnl_eff, 4)
                    cap = capacity_curve(ab_asks, bb_bids, fee_b, fee_s,
                                         LATENCY_HAIRCUT + REBALANCE_HAIRCUT)
                    ask_top = ab_asks[0][0] if ab_asks else None
                    bid_top = bb_bids[0][0] if bb_bids else None
                    # one durable ledger row per EPISODE (REAL basis) — the
                    # balance stays auditable fill-by-fill.
                    try:
                        store.publish_paper_trade(
                            "scanner-cross-exchange-arb",
                            trade_id=f"e{EPOCH}:{symbol}:{buy_ex}>{sell_ex}:{t0:.3f}",
                            pnl_abs=pnl_eff, pnl_pct=net_eff, pair=symbol,
                            opened_at=now_iso(), closed_at=now_iso(),
                            reason="long-xarb_paper-fill",
                            entry_price=ask_top, exit_price=bid_top,
                            size=PAPER_TRADE_SIZE, side="long",
                            tag=f"{buy_ex}->{sell_ex}",
                            extra={"net_top_pct": round(net_top * 100, 4),
                                   "net_depth_pct": round(net_d * 100, 4),
                                   "gross_pnl": round(pnl, 4),
                                   "episode": True, "epoch": EPOCH,
                                   "capacity": cap},
                        )
                    except Exception:
                        pass
                # `filled` column = actual paper booking; an open episode's
                # repeat sightings and negative spreads are logged, not booked.
                log_opp([
                    now_iso(), symbol, buy_ex, sell_ex,
                    f"{net_top*100:.4f}", f"{net_d*100:.4f}",
                    f"{pnl_eff:.4f}", booked, f"{virtual_balance:.4f}",
                ])
                tag = ("PAPER-FILL" if booked
                       else "in-episode" if key in episodes else "seen")
                print(
                    f"[{now_iso()}] {tag} {symbol} buy {buy_ex}->sell {sell_ex} "
                    f"| top {net_top*100:+.3f}% | depth {net_d*100:+.3f}% "
                    f"| eff {net_eff*100:+.3f}% | P&L {pnl_eff:+.2f} | booked={booked} "
                    f"| had_depth={filled} | touch_ok={depth_ok} "
                    f"| real {virtual_balance:+.2f} | gross {gross_balance:+.2f}"
                )

            # Close episodes whose gap fell silent (no re-check above the
            # prefilter for EPISODE_STALE_S), then record every closure.
            closed_eps += sweep_stale_episodes(episodes, t0)
            for ce in closed_eps:
                last_close_ts = ce["closed"]
                summary = {"symbol": ce["symbol"], "route": ce["route"],
                           "opened": now_iso(), "dur_s": round(ce["closed"] - ce["opened"], 1),
                           "peak_eff_pct": round(ce["peak_eff"] * 100, 4),
                           "close_reason": ce["close_reason"]}
                summary["opened"] = datetime.fromtimestamp(
                    ce["opened"], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                recent_eps.append(summary)
                print(f"[{now_iso()}] EPISODE-CLOSE {ce['symbol']} {ce['route']} "
                      f"| peak eff {ce['peak_eff']*100:+.3f}% "
                      f"| {summary['dur_s']:.0f}s | {ce['close_reason']}")
            recent_eps = recent_eps[-15:]

            # The MAJORS gauge, depth-confirmed: the 15-Jul "1% dislocation"
            # was a stale `last` on a dead CBX book — so the bus-grade number
            # now comes from REAL top-of-book mids of the best major
            # candidate (2 extra fetches when the budget didn't cover it).
            # None = no major above the prefilter, itself an honest reading.
            liquid_conf = None
            if best_liquid is not None and best_liquid[0] >= eff_prefilter:
                _, lsym, lbuy, lsell = best_liquid
                if liquid_books is None:
                    try:
                        liquid_books = (
                            exchanges[lbuy].fetch_order_book(lsym, limit=BOOK_LEVELS),
                            exchanges[lsell].fetch_order_book(lsym, limit=BOOK_LEVELS))
                        fetches += 2
                    except Exception:
                        liquid_books = None
                if liquid_books:
                    mid_a, mid_b = book_mid(liquid_books[0]), book_mid(liquid_books[1])
                    da = touch_depth(liquid_books[0].get("asks"), mid_a)
                    db = touch_depth(liquid_books[1].get("bids"), mid_b)
                    if mid_a and mid_b and min(da, db) >= MIN_TOUCH_DEPTH:
                        liquid_conf = mid_b / mid_a - 1.0
            liquid_books = None

            best = confirmed[0] if confirmed else None
            if best:
                summary = (f"best depth {best[0]*100:+.3f}% "
                           f"({best[5]} {best[6]}->{best[7]})")
            elif best_top is not None:
                summary = (f"no depth confirm; best top {best_top[0]*100:+.3f}% "
                           f"({best_top[1]} {best_top[2]}->{best_top[3]})")
            else:
                summary = "no priceable pairs"
            print(
                f"[{now_iso()}] {len(sym_map)} pairs | {len(ranked)} past prefilter "
                f"| {depth_rejected} failed touch-depth | {len(artifacts)} artifacts "
                f"| {fetches} books | {len(episodes)} episodes open "
                f"| {summary} | {time.time()-t0:.1f}s"
            )

            # The census: what the net actually saw, for the board/review.
            quiet_since = max(epoch_started, last_close_ts)
            quiet_hours = 0.0 if episodes else round((t0 - quiet_since) / 3600.0, 2)
            census = {
                "updated": now_iso(), "ttl_sec": 3600, "epoch": EPOCH,
                "episodes_open": len(episodes),
                "open_keys": sorted(episodes)[:10],
                "day": census_day,
                "quiet_hours": quiet_hours,
                "recent_episodes": recent_eps[-10:],
                "implausible": {"count": len(artifacts),
                                "top": [{"symbol": s, "gap_pct": round(g * 100, 2),
                                         "route": f"{b}->{sl}"}
                                        for g, s, b, sl in artifacts[:3]]},
                "depth_rejected": depth_rejected,
                "xquote": ({"base": xq_best[1],
                            "gap_pct": round(xq_best[0] * 100, 4),
                            "cheap": xq_best[2], "dear": xq_best[3],
                            "rates": {k: round(v, 5) for k, v in usd_rates.items()}}
                           if xq_best[0] is not None else None),
                "venues": sorted(exchanges),
                "prefilter_pct": round(eff_prefilter * 100, 3),
                "book_budget": eff_books,
            }
            store.save_state("gapscout-census", census)
            if (booked_this_scan or closed_eps) and hasattr(store, "save_history"):
                try:
                    store.save_history("gapscout-census", {
                        "updated": census["updated"],
                        "episodes_open": len(episodes),
                        "day": census_day, "quiet_hours": quiet_hours})
                except Exception:
                    pass

            # Heartbeat row so the CSV/dashboard always has trend data.
            if (HEARTBEAT_SECONDS and best_top is not None
                    and time.time() - last_heartbeat >= HEARTBEAT_SECONDS):
                log_opp([
                    now_iso(), "HEARTBEAT", best_top[2], best_top[3],
                    f"{best_top[0]*100:.4f}", "", "0.0000", False,
                    f"{virtual_balance:.4f}",
                ])
                last_heartbeat = time.time()
        except Exception as e:
            print(f"[{now_iso()}] scan error (skipping): {e!r}")
            traceback.print_exc()

        store.publish(
            "scanner-cross-exchange-arb", status="online",
            pnl_abs=virtual_balance,   # REAL basis: fees+slippage+latency+rebalance
            closed_trades=n_booked, wins=n_wins, losses=n_losses,
            extra={"kind": "scanner",
                   "basis": f"epoch-{EPOCH} episodes "
                            "(deduped, floored, fees+slippage+15bps haircuts)",
                   "epoch": EPOCH,
                   "legacy": legacy,          # the parked v1 odometer
                   "gross_balance": round(gross_balance, 2),  # same eps, no haircuts
                   "episodes_open": len(episodes),
                   "quiet_hours": quiet_hours,
                   "venues": sorted(exchanges),
                   "prefilter_pct": round(eff_prefilter * 100, 3),
                   "pairs": len(sym_map),
                   "best_top_pct": round(best_top[0] * 100, 4) if best_top else None,
                   # bus-grade stress gauge: majors, DEPTH-CONFIRMED from the
                   # real books (None = no major above the prefilter). The
                   # raw stage-1 reference number stays as _ref diagnostics.
                   "liquid_top_pct": (round(liquid_conf * 100, 4)
                                      if liquid_conf is not None else None),
                   "liquid_basis": "book-mids",
                   "liquid_ref_pct": round(best_liquid[0] * 100, 4) if best_liquid else None,
                   "liquid_symbol": best_liquid[1] if best_liquid else None,
                   "xquote_top_pct": (round(xq_best[0] * 100, 4)
                                      if xq_best[0] is not None else None),
                   "xquote_base": xq_best[1],
                   **lighter_extra()},
        )
        store.save_state("scanner-cross-exchange-arb",
                         {"virtual_balance": round(virtual_balance, 4),
                          "gross_balance": round(gross_balance, 4),
                          "booked": n_booked, "wins": n_wins,
                          "losses": n_losses,
                          "epoch": EPOCH, "epoch_started": epoch_started,
                          "legacy": legacy,
                          "episodes": episodes,
                          "recent_episodes": recent_eps,
                          "last_episode_close_ts": last_close_ts,
                          "census_day": census_day})
        if once:
            print(f"\n[{now_iso()}] --once smoke test complete. Engine ran "
                  f"end-to-end against live public data.")
            return
        time.sleep(max(0.0, POLL_SECONDS - (time.time() - t0)))


# ----------------------------------------------------------------------------
# OFFLINE SELF-TEST (no network) — proves the math is sane
# ----------------------------------------------------------------------------


def selftest():
    print("Running offline cross-exchange math self-test...\n")

    # 1) Realistic near-equal prices across venues => no post-fee arb.
    #    BTC/USDT ~65,600 on both; tiny spread; fees alone sink it.
    net = top_of_book_edge(ask_buy=65601.0, bid_sell=65603.0,
                           fee_buy=0.0010, fee_sell=0.0026)
    print(f"  near-equal venues: {net*100:+.4f}%  (expect clearly negative)")
    assert net < 0, "fees must kill a 2-dollar gap on a 65k asset"

    # 2) A genuine fat gap (cheap venue 1.0% under dear venue) clears fees.
    net2 = top_of_book_edge(ask_buy=100.0, bid_sell=101.5,
                            fee_buy=0.0010, fee_sell=0.0026)
    print(f"  1.5% raw gap:      {net2*100:+.4f}%  (expect positive after ~0.36% fees)")
    assert net2 > 0, "a 1.5% gap should survive 0.36% combined fees"

    # 3) Depth walk: a thin dear-venue book shrinks the edge vs top-of-book.
    asks_cheap = [[100.0, 100.0]]                 # plenty to buy at 100
    bids_thin = [[101.5, 1.0], [100.2, 100.0]]    # only 1 unit at the good bid
    net_top = top_of_book_edge(100.0, 101.5, 0.0010, 0.0026)
    net_depth, pnl, filled = depth_edge(1000.0, asks_cheap, bids_thin,
                                        0.0010, 0.0026)
    print(f"  top {net_top*100:+.3f}% vs depth @ $1k {net_depth*100:+.3f}% "
          f"(filled={filled}, P&L {pnl:+.2f})")
    assert net_depth < net_top, "thin book must erode the top-of-book mirage"

    # 4) Symbol map keeps only pairs on >=2 venues with whitelisted quotes.
    def mk(base, quote):
        return {"base": base, "quote": quote, "symbol": f"{base}/{quote}",
                "spot": True, "active": True}
    markets_by_ex = {
        "kraken": {"BTC/USD": mk("BTC", "USD"), "ETH/USD": mk("ETH", "USD")},
        "binance": {"BTC/USD": mk("BTC", "USD"), "DOGE/TRY": mk("DOGE", "TRY")},
        "coinbase": {"BTC/USD": mk("BTC", "USD")},
    }
    sm = build_symbol_map(markets_by_ex)
    print(f"  symbol map: {sorted(sm)} (each with venues {[sorted(v) for v in sm.values()]})")
    assert set(sm) == {"BTC/USD"}, "only BTC/USD is on >=2 venues with a good quote"
    assert set(sm["BTC/USD"]) == {"kraken", "binance", "coinbase"}

    # 5) Lighter venue premium: watch filtering, volume floor, junk handling.
    def bk(sym, mark, idx, qvol, status="active"):
        return {"symbol": sym, "mark_price": mark, "index_price": idx,
                "daily_quote_token_volume": qvol, "status": status}
    books = [
        bk("BTC", 62430.0, 62461.3, 5e8),      # ~-5 bps, liquid, watched
        bk("SPY", 746.7, 746.6, 2e6),          # ~+1.3 bps, liquid, watched
        bk("RKLB", 100.26, 100.0, 3e5),        # +26 bps, liquid, NOT watched
        bk("DEADCOIN", 110.0, 100.0, 5e3),     # below floor: excluded from stress
        bk("HALTED", 90.0, 100.0, 9e9, status="inactive"),  # skipped
        bk("BROKEN", None, 100.0, 9e9),        # missing mark: skipped
    ]
    prems, med, mx, n = lighter_premiums(books, ["BTC", "SPY"], 1e5)
    print(f"  lighter premiums: {prems} | stress med {med} / max {mx} bps over {n} books")
    assert set(prems) == {"BTC", "SPY"}, "only watched symbols published per-book"
    assert prems["BTC"] < 0 < prems["SPY"]
    assert n == 3, "stress gauge spans liquid active books only (BTC, SPY, RKLB)"
    assert mx == 26.0, "RKLB's 26 bps is the max |premium|"
    assert med == 5.0, "median |premium| of [1.3, 5.0, 26.0] is 5.0"
    p2, m2, x2, n2 = lighter_premiums([], ["BTC"], 1e5)
    assert (p2, m2, x2, n2) == ({}, None, None, 0), "empty payload -> empty result"

    # 6) Epoch-2 episode machine: book ONCE, hold while persisting, re-arm.
    eps = {}
    b1, closed = update_episode(eps, "X/USD|a|b", "X/USD", "a->b", 0.004, True, 1000.0)
    assert b1 and closed is None and "X/USD|a|b" in eps
    b2, closed = update_episode(eps, "X/USD|a|b", "X/USD", "a->b", 0.009, True, 1010.0)
    assert not b2 and closed is None, "a persisting gap must NOT re-book"
    assert eps["X/USD|a|b"]["peak_eff"] == 0.009
    b3, closed = update_episode(eps, "X/USD|a|b", "X/USD", "a->b", -0.0005, True, 1020.0)
    assert not b3 and closed is None and "X/USD|a|b" in eps, "hover keeps it open"
    b4, closed = update_episode(eps, "X/USD|a|b", "X/USD", "a->b", -0.002, True, 1030.0)
    assert not b4 and closed["close_reason"] == "rearm" and not eps
    b5, _ = update_episode(eps, "X/USD|a|b", "X/USD", "a->b", 0.001, True, 1040.0)
    assert b5, "after re-arm the same route may open a NEW episode"
    stale = sweep_stale_episodes(eps, 1040.0 + EPISODE_STALE_S + 1)
    assert [s["close_reason"] for s in stale] == ["stale"] and not eps
    print("  episode machine: book-once / hold / re-arm / stale-sweep OK")

    # 7) Capacity curve: the edge decays (and fill fails) as the clip grows.
    asks = [[100.0, 20.0], [101.0, 20.0]]
    bids = [[102.0, 5.0], [99.0, 100.0]]
    cap = capacity_curve(asks, bids, 0.001, 0.001, 0.0015, sizes=[250.0, 5000.0])
    assert cap[0]["net_eff_pct"] > cap[1]["net_eff_pct"]
    assert cap[0]["filled"] and not cap[1]["filled"]
    print(f"  capacity curve: $250 {cap[0]['net_eff_pct']:+.2f}% vs "
          f"$5k {cap[1]['net_eff_pct']:+.2f}% (thins out as it should)")

    # 8) Cross-quote gauge: live rate normalization, cross-quote pairs only.
    g, cheap, dear = cross_quote_gap(
        {"USD": {"kraken": 100.0}, "USDT": {"mexc": 102.0}},
        {"USD": 1.0, "USDT": 1.0})
    assert abs(g - 0.02) < 1e-9 and cheap == "kraken:USD" and dear == "mexc:USDT"
    g2, _, _ = cross_quote_gap(
        {"USD": {"kraken": 100.0}, "USDT": {"mexc": 102.0}},
        {"USD": 1.0, "USDT": 0.999})
    assert g2 < g, "a real USDT/USD rate must shrink the naive-par gap"
    g3, _, _ = cross_quote_gap({"USD": {"k": 100.0}, "USDT": {"m": 200.0}},
                               {"USD": 1.0})
    assert g3 is None, "a quote without a LIVE rate contributes nothing"
    g4, _, _ = cross_quote_gap({"USD": {"k": 100.0, "c": 101.0}}, {"USD": 1.0})
    assert g4 is None, "same-quote gaps are the main scan's business"
    print(f"  cross-quote gauge: {g*100:+.2f}% naive-par vs {g2*100:+.2f}% live-rate")

    # 9) Bookable floor: touch depth from REAL books + the freshness bar.
    healthy = {"bids": [[99.5, 100.0]], "asks": [[100.5, 100.0], [150.0, 999.0]]}
    assert book_mid(healthy) == 100.0
    assert book_mid({"bids": [], "asks": [[100.0, 1.0]]}) is None, "one-sided = dead"
    d = touch_depth(healthy["asks"], book_mid(healthy))
    assert d == 100.5 * 100.0, "only levels within 1% of mid count"
    # the DOT/USDT-class hollow book: wide quotes, dust near touch
    hollow = {"bids": [[0.85, 30.0]], "asks": [[0.86, 30.0]]}
    assert touch_depth(hollow["asks"], book_mid(hollow)) < MIN_TOUCH_DEPTH
    assert touch_depth(healthy["asks"], None) == 0.0
    assert fresh_mid({"bid": 99.0, "ask": 101.0}) == 100.0
    assert fresh_mid({"last": 100.0}) is None, "last-only tickers are never fresh"
    print("  bookable floor: touch-depth + freshness bar OK")

    print("\nAll self-tests passed. Cross-exchange detection + depth math + "
          "Lighter premium + epoch-2 episode machinery verified.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="offline math checks")
    ap.add_argument("--once", action="store_true", help="single live scan then exit")
    args = ap.parse_args()
    if args.selftest:
        selftest()          # offline math — always allowed, no venue touched
    else:
        # [2026-07-17 LIGHTER-ONLY GUARD — operator: "i only want things running
        # on lighter"] 🔀 Gap Scout paper-trades arbitrage BETWEEN Kraken,
        # Binance and Coinbase. There is no Lighter leg in that trade and there
        # cannot be one — you cannot arb a single venue against itself — so
        # unlike Snap Back this bot could not be MOVED to Lighter, only stopped.
        # This file says so itself at line ~201: "The CEX legs above say nothing
        # about Lighter, the venue the fleet actually trades."
        #
        # Its one Lighter-facing job — publishing the venue premium — is now
        # done by lighter_market_scout.py, which reads the SAME mark/index off
        # the SAME endpoint for every liquid book instead of the 6 in
        # LIGHTER_WATCH. fleet_risk.py was rewired to that source in the same
        # commit, so the bus keys (and the dashboard card that formats them)
        # keep working, with better coverage. The Ticket Taker's stress veto
        # already read the scout, so nothing load-bearing moves.
        #
        # KNOCK-ON, stated so it isn't a surprise: `gapscout-census` stops
        # updating, so the evidence board's widen-ladder loop goes inert (it
        # fails safe on staleness). That loop widens the scanner to MORE CEXes
        # (kucoin/gateio/mexc) — under Lighter-only it should be inert.
        #
        # IDLE, never sys.exit: restartPolicy would crash-loop an exit (the
        # Trail Blazer reasoning, 15-Jul). Ledger + odometer history kept.
        # To resurrect deliberately: GAPSCOUT_RETIRED_OVERRIDE=run.
        if os.environ.get("GAPSCOUT_RETIRED_OVERRIDE", "").strip().lower() \
                not in ("run", "1", "true"):
            print("scanner-cross-exchange-arb is RETIRED: it paper-trades "
                  "Kraken/Binance/Coinbase against each other — no Lighter leg — "
                  "and the fleet is LIGHTER-ONLY (operator, 17-Jul). Its Lighter "
                  "premium is published by lighter_market_scout.py (every liquid "
                  "book, vs 6 here). Idling: no exchange calls, no publishes. "
                  "GAPSCOUT_RETIRED_OVERRIDE=run to resurrect.", flush=True)
            while True:
                time.sleep(3600)
        run_live(once=args.once)


if __name__ == "__main__":
    main()
