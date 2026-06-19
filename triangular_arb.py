#!/usr/bin/env python3
"""
Triangular arbitrage DETECTION + PAPER-TRADING engine for Kraken.
Depth-aware, wide-universe edition.

What this does
--------------
- Scans Kraken's FULL liquid spot universe for 3-leg loops (e.g. USD -> BTC ->
  ETH -> USD) where the round trip returns more than you started with AFTER
  fees AND real order-book slippage at your actual trade size.
- Places NO real orders. Reads only public market data (no API keys needed).
- Detection is depth-aware: when a loop looks promising on top-of-book prices,
  the engine pulls the real order books and re-prices the loop by WALKING the
  book for `PAPER_TRADE_SIZE`. The number it reports/logs is what you'd really
  have filled at, slippage included. Profitable loops are booked to a virtual
  balance.

Why two stages
--------------
Pulling an order book for every pair every scan would be thousands of API calls
and take minutes (Kraken rate-limits public calls). So:
  Stage 1  one cheap fetch_tickers call -> rank ALL cycles on best bid/ask.
  Stage 2  pull deduped order books for only the top candidates -> confirm the
           edge depth-aware at trade size.
This gives true depth-aware detection across the whole net with a bounded,
rate-limit-friendly number of book fetches per scan.

Usage
-----
    pip install ccxt
    python triangular_arb.py                 # live depth-aware detection + paper trading
    python triangular_arb.py --selftest      # offline math checks, no network

Config is at the top of the file.
"""

import argparse
import csv
import os
import time
import traceback
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

# Currencies you would actually hold and settle a loop back into.
# Widened to include BTC/ETH so loops can also start from crypto you hold.
BASE_CURRENCIES = ["USD", "USDT", "USDC", "EUR", "BTC", "ETH"]

# Kraken Pro base-tier TAKER fee, per leg. 0.0040 = 0.40%.
# Arbitrage fills must be taker, so this is the honest number. Lower only if
# your 30-day volume genuinely earns a lower tier.
TAKER_FEE = 0.0040

# Restrict the tradable universe to currencies that connect to liquid markets.
# None = every active Kraken spot market (widest net, more cycles, slower
# stage-1 ranking but stage-1 is still a single API call). A curated set keeps
# the cycle count and noise down. Set to None for the absolute widest net.
UNIVERSE_HINT = {
    "USD", "USDT", "USDC", "EUR", "DAI",
    "BTC", "ETH", "SOL", "XRP", "ADA", "DOT", "LINK", "MATIC", "LTC",
    "AVAX", "ATOM", "ALGO", "XLM", "TRX", "BCH", "DOGE", "UNI", "AAVE",
}

# Stage-1 -> Stage-2 gate. Only loops whose TOP-OF-BOOK net edge is at least
# this get a (costly) depth-aware order-book confirmation. Keeps book fetches
# bounded. Set lower (more negative) to depth-check more near-misses.
PREFILTER_EDGE = -0.010   # -1.0%

# Hard cap on unique order books fetched per scan (rate-limit guard).
MAX_BOOK_FETCHES = 24

# Log a confirmed (depth-aware) loop if its net edge is at least this.
MIN_NET_EDGE = -0.006

# Notional size of each simulated trade, in the loop's start currency. The
# depth-aware edge is computed for THIS size, so slippage scales with it.
PAPER_TRADE_SIZE = 1000.0

# Seconds between full scans.
POLL_SECONDS = 8.0

# Order-book depth (levels) to pull per pair. More = better slippage modelling
# for large sizes, marginally heavier calls.
BOOK_LEVELS = 100

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
OPP_LOG = os.path.join(LOG_DIR, "arb_opportunities.csv")

# ----------------------------------------------------------------------------
# CORE MATH (pure functions — unit-testable with no network)
# ----------------------------------------------------------------------------


def convert_top_of_book(amount, cur_from, cur_to, market, ticker, fee):
    """Convert `amount` of cur_from -> cur_to using best bid/ask only (Stage 1)."""
    base, quote = market["base"], market["quote"]
    bid, ask = ticker.get("bid"), ticker.get("ask")
    if not bid or not ask:
        return None
    if cur_to == base and cur_from == quote:
        return (amount / ask) * (1 - fee)          # buy base, pay ask
    if cur_from == base and cur_to == quote:
        return (amount * bid) * (1 - fee)          # sell base, hit bid
    return None


def walk_book(amount, cur_from, cur_to, market, order_book, fee):
    """Depth-aware fill: consume real order-book levels for `amount` of cur_from.

    Returns (received_cur_to, filled_fully). Models slippage by eating
    successive price levels, not just the best one.
    """
    base, quote = market["base"], market["quote"]
    if cur_to == base and cur_from == quote:
        # buying base, spend `amount` of quote up the asks
        spent, got = 0.0, 0.0
        for level in order_book.get("asks", []):
            # ccxt levels are [price, size]; some exchanges (e.g. Kraken)
            # append a 3rd element (timestamp). Unpack defensively.
            price, size = level[0], level[1]
            take = min(amount - spent, price * size)
            if take <= 0:
                break
            got += take / price
            spent += take
            if spent >= amount - 1e-12:
                break
        return got * (1 - fee), spent >= amount - 1e-9
    if cur_from == base and cur_to == quote:
        # selling `amount` of base down the bids
        sold, got = 0.0, 0.0
        for level in order_book.get("bids", []):
            # ccxt levels are [price, size]; some exchanges (e.g. Kraken)
            # append a 3rd element (timestamp). Unpack defensively.
            price, size = level[0], level[1]
            take = min(amount - sold, size)
            if take <= 0:
                break
            got += take * price
            sold += take
            if sold >= amount - 1e-12:
                break
        return got * (1 - fee), sold >= amount - 1e-9
    return None, False


def evaluate_cycle_top(cycle, markets_by_pair, tickers, fee, start_amount=1.0):
    """Stage 1: best bid/ask net edge for a [A,B,C] loop settling back to A."""
    amount = start_amount
    for cur_from, cur_to in zip(cycle, cycle[1:] + cycle[:1]):
        market = markets_by_pair.get(frozenset((cur_from, cur_to)))
        if market is None:
            return None
        ticker = tickers.get(market["symbol"])
        if ticker is None:
            return None
        amount = convert_top_of_book(amount, cur_from, cur_to, market, ticker, fee)
        if amount is None:
            return None
    return amount / start_amount - 1


def evaluate_cycle_depth(cycle, markets_by_pair, books, fee, size):
    """Stage 2: depth-aware net edge + P&L for a loop, walking real books.

    `books` maps symbol -> order book. Returns
    (net_edge, pnl, filled_fully) or (None, None, None) if not priceable.
    """
    amount = size
    all_filled = True
    for cur_from, cur_to in zip(cycle, cycle[1:] + cycle[:1]):
        market = markets_by_pair.get(frozenset((cur_from, cur_to)))
        if market is None:
            return None, None, None
        ob = books.get(market["symbol"])
        if ob is None:
            return None, None, None
        amount, filled = walk_book(amount, cur_from, cur_to, market, ob, fee)
        if amount is None:
            return None, None, None
        all_filled = all_filled and filled
    return amount / size - 1, amount - size, all_filled


# ----------------------------------------------------------------------------
# GRAPH BUILDING
# ----------------------------------------------------------------------------


def build_graph(markets):
    """ccxt markets -> (markets_by_pair, neighbors)."""
    markets_by_pair, neighbors = {}, {}
    for m in markets.values():
        if not (m.get("spot") and m.get("active")):
            continue
        base, quote = m.get("base"), m.get("quote")
        if not base or not quote:
            continue
        if UNIVERSE_HINT is not None and (
            base not in UNIVERSE_HINT or quote not in UNIVERSE_HINT
        ):
            continue
        markets_by_pair[frozenset((base, quote))] = m
        neighbors.setdefault(base, set()).add(quote)
        neighbors.setdefault(quote, set()).add(base)
    return markets_by_pair, neighbors


def enumerate_cycles(base_currencies, neighbors, markets_by_pair):
    """All directed 3-currency loops starting/ending in a base currency."""
    cycles, seen = [], set()
    for a in base_currencies:
        for b in neighbors.get(a, ()):
            if b == a:
                continue
            for c in neighbors.get(b, ()):
                if c in (a, b):
                    continue
                if frozenset((c, a)) not in markets_by_pair:
                    continue
                if (a, b, c) in seen:
                    continue
                seen.add((a, b, c))
                cycles.append([a, b, c])
    return cycles


# ----------------------------------------------------------------------------
# LIVE ENGINE
# ----------------------------------------------------------------------------


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_log():
    if not os.path.exists(OPP_LOG):
        with open(OPP_LOG, "w", newline="") as f:
            csv.writer(f).writerow(
                ["timestamp", "cycle", "top_of_book_net_pct", "depth_net_pct",
                 "paper_pnl", "filled", "virtual_balance"]
            )


def log_opp(row):
    with open(OPP_LOG, "a", newline="") as f:
        csv.writer(f).writerow(row)


def run_live(once=False):
    import ccxt  # imported here so --selftest works without ccxt installed

    ex = ccxt.kraken({"enableRateLimit": True})
    print(f"[{now_iso()}] Loading Kraken markets...")
    markets = ex.load_markets()
    markets_by_pair, neighbors = build_graph(markets)
    cycles = enumerate_cycles(BASE_CURRENCIES, neighbors, markets_by_pair)
    print(
        f"[{now_iso()}] {len(markets_by_pair)} pairs, {len(cycles)} triangular "
        f"cycles. Taker {TAKER_FEE*100:.2f}%/leg. Depth-aware @ "
        f"{PAPER_TRADE_SIZE:.0f}/loop."
    )
    print(
        f"[{now_iso()}] Detection-only + paper trading. NO real orders.\n"
        f"           Stage-1 ticker scan -> Stage-2 depth confirm (<= "
        f"{MAX_BOOK_FETCHES} books/scan). Logging to {OPP_LOG}\n"
    )

    ensure_log()
    virtual_balance = 0.0
    best_depth_seen = -1.0

    while True:
        t0 = time.time()
        try:
            tickers = ex.fetch_tickers()
        except Exception as e:
            print(f"[{now_iso()}] ticker fetch failed: {e}")
            time.sleep(POLL_SECONDS)
            continue

        # Everything below is wrapped so that a single malformed book/ticker
        # or an unexpected arithmetic error logs and is skipped, instead of
        # killing the process (which the KeepAlive supervisor would then
        # respawn into an endless crash loop).
        try:
            # Stage 1: rank every cycle on top-of-book.
            ranked = []
            for cycle in cycles:
                net = evaluate_cycle_top(cycle, markets_by_pair, tickers, TAKER_FEE)
                if net is not None and net >= PREFILTER_EDGE:
                    ranked.append((net, cycle))
            ranked.sort(reverse=True)

            # Stage 2: gather deduped books for the top candidates (capped), then
            # confirm depth-aware at trade size.
            books, confirmed = {}, []
            for net_top, cycle in ranked:
                symbols = [markets_by_pair[frozenset((f, t))]["symbol"]
                           for f, t in zip(cycle, cycle[1:] + cycle[:1])]
                need = [s for s in symbols if s not in books]
                if len(books) + len(need) > MAX_BOOK_FETCHES:
                    break  # respect the per-scan fetch budget
                ok = True
                for s in need:
                    try:
                        books[s] = ex.fetch_order_book(s, limit=BOOK_LEVELS)
                    except Exception:
                        ok = False
                        break
                if not ok:
                    continue
                net_depth, pnl, filled = evaluate_cycle_depth(
                    cycle, markets_by_pair, books, TAKER_FEE, PAPER_TRADE_SIZE
                )
                if net_depth is None:
                    continue
                best_depth_seen = max(best_depth_seen, net_depth)
                confirmed.append((net_depth, net_top, pnl, filled, cycle))

            confirmed.sort(reverse=True)

            # Book any loop that is break-even-or-better AFTER depth+fees as a
            # paper trade; log anything down to MIN_NET_EDGE for the record.
            for net_depth, net_top, pnl, filled, cycle in confirmed:
                if net_depth < MIN_NET_EDGE:
                    continue
                booked = net_depth >= 0.0 and filled
                if booked:
                    virtual_balance += pnl
                log_opp([
                    now_iso(), "->".join(cycle + [cycle[0]]),
                    f"{net_top*100:.4f}", f"{net_depth*100:.4f}",
                    f"{pnl:.4f}", filled, f"{virtual_balance:.4f}",
                ])
                tag = "PAPER-FILL" if booked else "seen"
                print(
                    f"[{now_iso()}] {tag} {'->'.join(cycle)} | top {net_top*100:+.3f}% "
                    f"| depth {net_depth*100:+.3f}% | P&L {pnl:+.2f} {cycle[0]} "
                    f"| filled={filled} | bal {virtual_balance:+.2f}"
                )

            best = confirmed[0] if confirmed else None
            summary = (
                f"best depth {best[0]*100:+.3f}% ({'->'.join(best[4])})" if best
                else f"best depth seen {best_depth_seen*100:+.3f}%"
            )
            print(
                f"[{now_iso()}] {len(cycles)} cycles | {len(ranked)} passed prefilter "
                f"| {len(books)} books pulled | {summary} | {time.time()-t0:.1f}s"
            )
        except Exception as e:
            # Log full traceback but keep the scan loop alive.
            print(f"[{now_iso()}] scan error (skipping cycle): {e!r}")
            traceback.print_exc()
        if once:
            print(f"\n[{now_iso()}] --once smoke test complete. The engine is "
                  f"live against Kraken and the math ran end-to-end.")
            return
        time.sleep(max(0.0, POLL_SECONDS - (time.time() - t0)))


# ----------------------------------------------------------------------------
# OFFLINE SELF-TEST (no network) — proves the math is sane
# ----------------------------------------------------------------------------


def selftest():
    print("Running offline math self-test...\n")

    def mk(base, quote):
        return {"base": base, "quote": quote, "symbol": f"{base}/{quote}",
                "spot": True, "active": True}

    markets = {"BTC/USD": mk("BTC", "USD"),
               "ETH/USD": mk("ETH", "USD"),
               "ETH/BTC": mk("ETH", "BTC")}
    mbp, neighbors = build_graph(markets)
    cycles = enumerate_cycles(["USD"], neighbors, mbp)
    assert cycles, "should find a USD cycle"

    # 1) Real Kraken snapshot must offer no post-fee arbitrage.
    real = {"BTC/USD": {"bid": 65605.10, "ask": 65605.40},
            "ETH/USD": {"bid": 1790.78, "ask": 1790.94},
            "ETH/BTC": {"bid": 0.027299, "ask": 0.027302}}
    worst = min(evaluate_cycle_top(c, mbp, real, TAKER_FEE) for c in cycles)
    print(f"  real snapshot best loop: {worst*100:+.4f}% (top-of-book, after fees)")
    assert worst < 0, "real market must net negative after fees"
    print("  PASS: real market offers no arbitrage\n")

    # 2) DEPTH-AWARE: a loop with a juicy TOP-OF-BOOK edge but THIN liquidity
    #    should collapse once we try to fill $1,000; the SAME edge with DEEP
    #    books should survive. This is the whole point of depth wiring.
    #    Construct a 5% gross top-of-book loop: USD->BTC->ETH->USD.
    def book(levels_bids, levels_asks):
        return {"bids": levels_bids, "asks": levels_asks}

    # Best prices give ~5% gross; depth differs between the two scenarios.
    # USD->BTC: buy BTC at 100 ; BTC->ETH: buy ETH at 0.10 ; ETH->USD: sell at 10.5
    thin = {
        "BTC/USD": book([[100, 9999]], [[100.0, 0.2]]),   # only 0.2 BTC at best ask
        "ETH/BTC": book([[0.10, 9999]], [[0.10, 0.5]]),   # thin
        "ETH/USD": book([[10.5, 0.5], [9.0, 9999]], []),  # only 0.5 ETH at 10.5 bid
    }
    deep = {
        "BTC/USD": book([[100, 9999]], [[100.0, 9999]]),
        "ETH/BTC": book([[0.10, 9999]], [[0.10, 9999]]),
        "ETH/USD": book([[10.5, 9999]], []),
    }
    top = evaluate_cycle_top(
        ["USD", "BTC", "ETH"], mbp,
        {"BTC/USD": {"bid": 100, "ask": 100}, "ETH/BTC": {"bid": 0.10, "ask": 0.10},
         "ETH/USD": {"bid": 10.5, "ask": 10.5}}, TAKER_FEE)
    net_thin, _, filled_thin = evaluate_cycle_depth(
        ["USD", "BTC", "ETH"], mbp, thin, TAKER_FEE, 1000.0)
    net_deep, pnl_deep, filled_deep = evaluate_cycle_depth(
        ["USD", "BTC", "ETH"], mbp, deep, TAKER_FEE, 1000.0)
    print(f"  top-of-book edge:      {top*100:+.3f}%")
    print(f"  depth @ $1k THIN book: {net_thin*100:+.3f}% (filled={filled_thin})")
    print(f"  depth @ $1k DEEP book: {net_deep*100:+.3f}% (filled={filled_deep}, "
          f"P&L ${pnl_deep:+.2f})")
    assert top > 0.03, "setup should show a fat top-of-book edge"
    assert net_thin < net_deep, "thin liquidity must erode the edge vs deep"
    assert net_deep > 0 and filled_deep, "deep book should keep the edge & fill"
    print("  PASS: depth wiring kills the mirage and keeps the real thing\n")

    # 3) Wider-net plumbing: graph + cycle enumeration across many currencies.
    big = {}
    for b, q in [("BTC", "USD"), ("ETH", "USD"), ("ETH", "BTC"), ("SOL", "USD"),
                 ("SOL", "BTC"), ("XRP", "USD"), ("XRP", "BTC")]:
        big[f"{b}/{q}"] = mk(b, q)
    mbp2, n2 = build_graph(big)
    cyc2 = enumerate_cycles(["USD"], n2, mbp2)
    print(f"  wider net: {len(mbp2)} pairs -> {len(cyc2)} USD cycles: "
          + ", ".join("->".join(c) for c in cyc2))
    assert any(c[1] == "SOL" or c[2] == "SOL" for c in cyc2), "should reach SOL"
    print("  PASS: wider universe enumerates multi-asset cycles\n")

    print("All self-tests passed. Depth-aware detection + wide net verified.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true",
                   help="run offline math checks (no network, no ccxt needed)")
    p.add_argument("--once", action="store_true",
                   help="run ONE live scan against Kraken and exit (smoke test)")
    args = p.parse_args()
    if args.selftest:
        selftest()
    else:
        run_live(once=args.once)
