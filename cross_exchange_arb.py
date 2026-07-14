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

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

# Exchanges to compare. ccxt ids. Public data only.
# NOTE: US-region-friendly set. Binance.com is NOT used because it returns
# HTTP 451 ("restricted location") from Railway's region. We use
# `coinbaseexchange` (Coinbase Exchange / ex-Pro) rather than `coinbase`
# (Advanced Trade) because the former exposes a working fetch_tickers.
EXCHANGES = ["kraken", "coinbaseexchange", "gemini"]

# Base-tier TAKER fee per exchange (fraction). Arb fills must be taker. These
# are conservative public defaults; the engine uses each market's own ccxt
# 'taker' fee when ccxt reports one, and falls back to these otherwise. Lower
# only if your real 30-day volume earns a better tier on that venue.
TAKER_FEE = {
    "kraken": 0.0026,           # Kraken Pro spot taker, base tier
    "coinbaseexchange": 0.0060, # Coinbase Exchange taker, base tier
    "gemini": 0.0040,           # Gemini ActiveTrader taker, base tier
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

# Hard cap on order books fetched per scan (2 per confirmed pair). Rate guard.
MAX_BOOK_FETCHES = 30

# Log a confirmed (depth-aware) opportunity if its net edge is at least this.
MIN_NET_EDGE = -0.005

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

    exchanges = {}
    for ex_id in EXCHANGES:
        try:
            exchanges[ex_id] = getattr(ccxt, ex_id)({"enableRateLimit": True})
        except Exception as e:
            print(f"[{now_iso()}] could not init {ex_id}: {e}")
    if len(exchanges) < 2:
        print(f"[{now_iso()}] need >=2 working exchanges, have {len(exchanges)}. Exiting.")
        return

    print(f"[{now_iso()}] Loading markets for {', '.join(exchanges)} ...")
    markets_by_ex = {}
    for ex_id, ex in exchanges.items():
        try:
            markets_by_ex[ex_id] = ex.load_markets()
        except Exception as e:
            print(f"[{now_iso()}] {ex_id} load_markets failed: {e}")
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
    virtual_balance = 0.0        # REAL basis: net of fees, slippage, haircuts
    gross_balance = 0.0          # legacy optimistic basis (no haircuts), for comparison
    last_heartbeat = 0.0

    while True:
        t0 = time.time()
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
            # Stage 1: rank every cross-venue pair on a reference price (mid
            # when bid/ask present, else last). The number here is the RAW
            # cross-venue price gap (no fees yet) — fees + real bid/ask +
            # slippage are applied in Stage 2 from order books.
            ranked = []
            best_top = None  # (gap, symbol, buy_ex, sell_ex)
            artifacts = 0    # implausible gaps skipped as data noise
            for symbol, exmarkets in sym_map.items():
                refs = ref_prices(symbol, exmarkets, tickers_by_ex)
                if len(refs) < 2:
                    continue
                buy_ex = min(refs, key=refs.get)    # cheapest reference price
                sell_ex = max(refs, key=refs.get)   # dearest reference price
                if buy_ex == sell_ex or refs[buy_ex] <= 0:
                    continue
                gap = refs[sell_ex] / refs[buy_ex] - 1.0
                if gap > MAX_PLAUSIBLE_GAP:
                    artifacts += 1   # symbol collision / stale price — ignore
                    continue
                if best_top is None or gap > best_top[0]:
                    best_top = (gap, symbol, buy_ex, sell_ex)
                if gap >= PREFILTER_GAP:
                    ranked.append((gap, symbol, buy_ex, sell_ex))
            ranked.sort(reverse=True)

            # Stage 2: confirm the top candidates depth-aware at trade size.
            books, confirmed, fetches = {}, [], 0
            for net_top, symbol, buy_ex, sell_ex in ranked:
                if fetches + 2 > MAX_BOOK_FETCHES:
                    break
                try:
                    ab = exchanges[buy_ex].fetch_order_book(symbol, limit=BOOK_LEVELS)
                    bb = exchanges[sell_ex].fetch_order_book(symbol, limit=BOOK_LEVELS)
                    fetches += 2
                except Exception:
                    continue
                fee_b = fee_for(buy_ex, sym_map[symbol].get(buy_ex))
                fee_s = fee_for(sell_ex, sym_map[symbol].get(sell_ex))
                net_d, pnl, filled = depth_edge(
                    PAPER_TRADE_SIZE, ab.get("asks", []), bb.get("bids", []),
                    fee_b, fee_s,
                )
                if net_d is None:
                    continue
                confirmed.append((net_d, net_top, pnl, filled, symbol, buy_ex, sell_ex))

            confirmed.sort(reverse=True)

            for net_d, net_top, pnl, filled, symbol, buy_ex, sell_ex in confirmed:
                if net_d < MIN_NET_EDGE:
                    continue
                # Effective edge after execution-reality haircuts. Book on the
                # REAL basis; keep the legacy optimistic booking in parallel so
                # the dashboard can show how much of the "edge" was fiction.
                net_eff = net_d - LATENCY_HAIRCUT - REBALANCE_HAIRCUT
                pnl_eff = pnl - PAPER_TRADE_SIZE * (LATENCY_HAIRCUT + REBALANCE_HAIRCUT)
                booked = net_eff >= 0.0 and filled
                if booked:
                    virtual_balance += pnl_eff
                if net_d >= 0.0 and filled:
                    gross_balance += pnl   # what the old rule would have booked
                # `filled` column = actual paper booking (profitable-after-depth
                # AND both legs fully fillable). A fillable-but-negative spread is
                # only "seen", never a fill, so write `booked` here. `had_depth`
                # keeps the liquidity diagnostic in the console log.
                had_depth = filled
                log_opp([
                    now_iso(), symbol, buy_ex, sell_ex,
                    f"{net_top*100:.4f}", f"{net_d*100:.4f}",
                    f"{pnl_eff:.4f}", booked, f"{virtual_balance:.4f}",
                ])
                tag = "PAPER-FILL" if booked else "seen"
                print(
                    f"[{now_iso()}] {tag} {symbol} buy {buy_ex}->sell {sell_ex} "
                    f"| top {net_top*100:+.3f}% | depth {net_d*100:+.3f}% "
                    f"| eff {net_eff*100:+.3f}% | P&L {pnl_eff:+.2f} | booked={booked} "
                    f"| had_depth={had_depth} | real {virtual_balance:+.2f} "
                    f"| gross {gross_balance:+.2f}"
                )

            best = confirmed[0] if confirmed else None
            if best:
                summary = (f"best depth {best[0]*100:+.3f}% "
                           f"({best[4]} {best[5]}->{best[6]})")
            elif best_top is not None:
                summary = (f"no depth confirm; best top {best_top[0]*100:+.3f}% "
                           f"({best_top[1]} {best_top[2]}->{best_top[3]})")
            else:
                summary = "no priceable pairs"
            print(
                f"[{now_iso()}] {len(sym_map)} pairs | {len(ranked)} passed prefilter "
                f"| {artifacts} artifacts skipped | {fetches} books pulled "
                f"| {summary} | {time.time()-t0:.1f}s"
            )

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
            extra={"kind": "scanner",
                   "basis": "real (fees+slippage+10bps latency+5bps rebalance)",
                   "gross_balance": round(gross_balance, 2),  # old optimistic rule
                   "pairs": len(sym_map),
                   "best_top_pct": round(best_top[0] * 100, 4) if best_top else None,
                   **lighter_extra()},
        )
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

    print("\nAll self-tests passed. Cross-exchange detection + depth math + "
          "Lighter premium verified.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="offline math checks")
    ap.add_argument("--once", action="store_true", help="single live scan then exit")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    else:
        run_live(once=args.once)


if __name__ == "__main__":
    main()
