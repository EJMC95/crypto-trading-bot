#!/usr/bin/env python3
"""
listing_sniper.py — DRY-RUN multi-exchange new-listing sniper / paper-trader.

What it does
------------
1. Snapshots every tradable SPOT pair on each selected exchange (via the unified
   CCXT public API — no keys, public endpoints only).
2. Polls on an interval and detects pairs that did NOT exist in the snapshot
   (i.e. brand-new listings) and are tradable ("active").
3. On detection it opens a *paper* position at the current ask price and then
   tracks the price, closing the paper trade on take-profit, stop-loss, or a
   max-hold timeout. Every simulated trade is logged to a CSV.

Exchanges are polled CONCURRENTLY and on a *best-effort* basis: any exchange
whose public API is unreachable, geo-blocked, rate-limited, or otherwise errors
is logged and skipped for that cycle — it never crashes the run. This is what
lets us widen the search to the top ~100 exchanges at once.

SAFETY
------
This script is 100% DRY-RUN. It only ever calls PUBLIC endpoints (markets /
tickers) through CCXT. It NEVER reads an API key, NEVER authenticates, and
NEVER places a real order. You cannot lose money running it. Its only purpose
is to find out whether a "buy the new listing" idea would have made or lost
money on *live* future listings — the only honest way to test this, because a
brand-new pair has no history to backtest against.

Usage
-----
First, seed a baseline of currently-listed pairs (do this once):
    python3 listing_sniper.py --seed

Then run the monitor (leave it running; new listings are rare):
    python3 listing_sniper.py

Useful flags:
    --exchanges top100   which exchanges to search. "topN" = the N highest-volume
                         exchanges CCXT supports (default top100), "all" = every
                         CCXT exchange, or a comma list of CCXT ids
                         (e.g. binance,coinbase,kraken).
    --workers 12         how many exchanges to poll in parallel (default 12).
    --interval 60        seconds between polls (default 60; be polite to the APIs)
    --quote USD,USDT,USDC,EUR
                         comma-separated quote currencies to snipe (default
                         USD,USDT,USDC,EUR — a wider net than USD-only)
    --tp-mult 5          take-profit as a MULTIPLE of entry; 5 = sell at 5x (default 5)
    --sl 0.50            stop-loss, -50% (default); set 0 to disable and ride to 5x or zero
    --max-hold 2880      max minutes to hold (default 48h; 0 = no limit)
    --max-open 25        max concurrent open positions (default 25; 0 = no cap)
    --no-price-give-up-min 60
                         close at last known price after this long unpriceable
    --stake 100          paper stake per trade in quote currency (default 100)
    --slippage-bps 30    simulated buy slippage in basis points (default 30)
    --any-status         open a paper trade as soon as the pair appears, even
                         before the exchange flips it to "active" (more
                         aggressive, less realistic).

PRE-TRADE RESEARCH GATE (2026-06-25)
------------------------------------
A brand-new pair has no history to backtest, so before committing paper capital
the sniper now inspects its LIVE microstructure on public endpoints (ticker +
order book) and only buys if it clears a quality gate:
    * OBSERVATION WINDOW — wait `--min-observe-sec` (120s) after first sight so we
      skip the opening-print spike instead of buying the top tick.
    * SPREAD — reject if bid/ask spread exceeds `--max-spread-bps` (500 = 5%).
    * EXIT LIQUIDITY — require resting bid-side depth within `--depth-band-pct`
      (5%) of touch to be >= `--min-depth-mult` x stake (3x), so the paper exit
      is realistic, not fiction.
    * ANTI-CHASE — skip if price already ran > `--max-launch-pump` (+150%) above
      where we first saw it (don't buy the blow-off top).
    * VOLUME FLOOR — optional `--min-quote-vol` (off by default; new pairs have
      little 24h history).
Candidates that fail are re-checked each cycle until they pass or age out after
`--max-pending-min` (30m). Rejections are logged to sniper_skips.csv so the gate
is auditable. Disable the whole gate with `--no-research` to restore the old
buy-the-first-print behaviour. This directly targets the 6-losses/6-trades run,
which came from buying illiquid, wide-spread, already-spiking first prints.

Files written (in ./sniper_data/):
    known_pairs.json     per-exchange baseline + every pair ever seen
    open_positions.json  currently-open paper trades (survives restarts)
    sniper_trades.csv     closed paper-trade log (your results)
    sniper_skips.csv      pairs the research gate rejected (+ why), for review
"""

import argparse
import csv
import gc
import os
import re
import json
import signal
import time
import math
from concurrent.futures import (
    ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError)
from datetime import datetime, timezone

import ccxt  # unified multi-exchange public API

import threading

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)

# [2026-07-04 INTEL] External listing intelligence (exchange announcement feeds
# + CoinGecko footprint). Stake modulation ONLY: junk tickets (no announcement,
# no CoinGecko page) get half stake; everything else full. Guarded import —
# missing module or dead APIs degrade to neutral.
try:
    import listing_intel as intel
except Exception:
    intel = None

# bot_pnl_store shares ONE module-global Postgres connection, so every store.*
# call in this process must hold this lock — the heartbeat thread below would
# otherwise race the main loop's publish/fetch calls on that connection.
_store_lock = threading.Lock()

# Last successful end-of-cycle publish: (kwargs, monotonic_ts). The heartbeat
# thread re-publishes this snapshot while a long cycle is still running.
_last_publish = {"kwargs": None, "ts": 0.0}

# Cycles are normally ~60s, but every `reload_every`th cycle rebuilds ~100
# exchanges' market lists and can run 8-9 minutes when slow exchanges hit their
# HTTP timeouts. Without a mid-cycle write the dashboard sees >180s of silence
# and flags a healthy sniper stale. The heartbeat re-upserts the last snapshot
# (same figures, fresh updated_at) every HEARTBEAT_SECONDS — but only while the
# main loop has published within HEARTBEAT_GIVE_UP_SECONDS, so a genuinely hung
# process still goes stale on the dashboard instead of being masked forever.
HEARTBEAT_SECONDS = 60
HEARTBEAT_GIVE_UP_SECONDS = 30 * 60
# [2026-07-16] The fleet's paper-book convention ($1,000 start, NO top-ups —
# CLAUDE.md Rules). This bot published pnl_abs but never `equity`, so
# bot_equity_history stored NULL for it and its dashboard GO-LIVE GATE read
# "dd —" / "age —" forever (the gate filters equity IS NOT NULL). Same basis
# the other paper books use (PaperBroker start_equity=1000).
START_EQUITY = 1000.0


def _heartbeat_loop():
    while True:
        time.sleep(HEARTBEAT_SECONDS)
        kwargs, ts = _last_publish["kwargs"], _last_publish["ts"]
        if kwargs is None:
            continue
        since = time.monotonic() - ts
        if HEARTBEAT_SECONDS < since < HEARTBEAT_GIVE_UP_SECONDS:
            with _store_lock:
                store.publish("event-listing-sniper", **kwargs)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sniper_data")
KNOWN_FILE = os.path.join(DATA_DIR, "known_pairs.json")
OPEN_FILE = os.path.join(DATA_DIR, "open_positions.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending.json")
TRADES_CSV = os.path.join(DATA_DIR, "sniper_trades.csv")
SKIPS_CSV = os.path.join(DATA_DIR, "sniper_skips.csv")

# Bases we never want to "snipe" (stablecoins / wrapped fiat — not real launches)
SKIP_BASES = {
    "USDT", "USDC", "DAI", "PYUSD", "USD", "EUR", "GBP", "AUD", "CAD", "CHF",
    "JPY", "ZUSD", "ZEUR", "ZGBP", "ZAUD", "ZCAD", "ZJPY", "USDG", "RLUSD",
    "TUSD", "FDUSD", "USDD", "USDP", "GUSD", "EURT", "EURS", "BUSD",
}

# [2026-07-03] Tokenized equities / ETFs / commodities are NOT crypto listings.
# WhiteBIT rolled out a tokenized-stocks section on 2026-07-02 and the sniper
# bought 46 of them in two waves (MSTR, NVDA, AAPL, SOXL, XAG, NATGAS, ...);
# they then went unpriceable and were flushed by the zombie guard at ~-0.5%
# each. A stock IPO'd as a token has no listing-pop microstructure to snipe —
# it tracks the underlying. Curated set of observed + common tickers; extend
# when a new tokenized section slips through.
TOKENIZED_BASES = {
    # observed in the 2026-07-02 whitebit flood
    "MSTR", "NVDA", "AAPL", "SOXL", "XLE", "XAG", "XPT", "XAU", "XPD",
    "NATGAS", "SAMSUNG", "HOOD", "IREN", "CRWV", "URNM", "EWT", "NOW",
    # common tokenized equities / ETFs likely in the same product lines
    "TSLA", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NFLX", "AMD", "INTC",
    "COIN", "GME", "AMC", "PLTR", "SPY", "QQQ", "GLD", "SLV", "USO", "TLT",
    "VOO", "IWM", "DIA", "ARKK", "MCD", "NKE", "DIS", "BABA", "V", "MA",
    "JPM", "BRK", "PFE", "JNJ", "KO", "PEP", "WMT", "CRCL", "RBLX", "UBER",
    "ABNB", "SHOP", "SQ", "PYPL", "ORCL", "CRM", "AVGO", "QCOM", "MU",
    "SMCI", "ASML", "TSM", "WTI", "BRENT", "COPPER", "WHEAT", "CORN",
    # [2026-07-07] second tokenized wave observed in the ledger (0 wins, ≈-$7:
    # CSCO/DELL/ADBE/GLW/COHR/CRDO/SNDK/ADI/PLAY all bled to max_hold/stop):
    "CSCO", "DELL", "ADBE", "GLW", "COHR", "CRDO", "SNDK", "ADI", "PLAY",
    "LRCX", "KLAC", "TXN", "IBM", "GE", "CAT", "BA", "XOM", "CVX", "UNH",
    "LLY", "ABBV", "MRK", "TMO", "COST", "HD", "PG", "VZ", "T", "CMCSA",
    # [2026-07-08] third wave — every one of these was bought on Jul-7 AFTER
    # the wave-2 blocklist deployed (06:23 UTC) and force-closed `delisted`
    # within hours (48 churn closes, −$11.56 on the day). Equities (RKLB,
    # MRVL, SONY, HYUNDAI, HIMS, ASTS, NBIS…), ETFs (TQQQ, EWZ, SPCX) and
    # tokenized commodities (XCU copper). The curated list keeps leaking a
    # tail of unlisted tickers — if a FOURTH wave appears, stop extending
    # this set and build the structural fix (per-exchange listing-flood
    # quarantine) instead.
    "RKLB", "AXTI", "SONY", "MRVL", "HYUNDAI", "TQQQ", "FLNC", "ONDS",
    "NBIS", "SPCX", "DRAM", "HIMS", "EWZ", "ASTS", "XCU", "BBX", "CBRS",
    "AAOI", "CIEN",
    # [2026-07-15] EWY (iShares South Korea ETF token — EWZ/EWT's sibling) is
    # not a wave, it FLAPS: the venue delists/relists it, each reappearance
    # reads as brand-new, and the sniper re-bought it 9 times 4→13-Jul — every
    # close `delisted` within ~2h, 8/9 red, net −$1.9. EWYG rode the same
    # section. Operator-requested drop.
    "EWY", "EWYG",
}

# Rough global spot-volume ranking of major exchanges (CCXT ids). Anything not
# in this list is appended in CCXT's own order to fill out "topN"/"all".
CURATED = [
    "binance", "bybit", "okx", "upbit", "coinbase", "kraken", "bitget", "gate",
    "mexc", "htx", "kucoin", "cryptocom", "bitmart", "bingx", "bitfinex",
    "gemini", "bitstamp", "binanceus", "poloniex", "bithumb", "bitvavo",
    "whitebit", "coinex", "xt", "lbank", "ascendex", "bitrue", "probit",
    "hitbtc", "digifinex", "latoken", "p2b", "bigone", "bitso", "bitbank",
    "bitflyer", "woo", "phemex", "deribit", "kucoinfutures",
]


def now_utc():
    return datetime.now(timezone.utc)


def ts():
    return now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")


# ----------------------------- exchange universe ----------------------------

def build_universe():
    """Ordered list of CCXT exchange ids: curated majors first, then the rest."""
    seen = []
    for e in CURATED:
        if e in ccxt.exchanges and e not in seen:
            seen.append(e)
    for e in ccxt.exchanges:
        if e not in seen:
            seen.append(e)
    return seen


def resolve_exchanges(spec):
    """Resolve --exchanges into a concrete list of CCXT ids.

    Accepts "topN" (e.g. top100), "all", or a comma-separated list of ids.
    Unknown ids are warned about and dropped.
    """
    universe = build_universe()
    spec = str(spec).strip().lower()
    m = re.fullmatch(r"top\s*(\d+)", spec)
    if m:
        n = max(1, int(m.group(1)))
        return universe[:n]
    if spec in ("all", "*"):
        return universe
    ids, unknown = [], []
    for part in spec.split(","):
        e = part.strip().lower()
        if not e:
            continue
        if e in ccxt.exchanges:
            if e not in ids:
                ids.append(e)
        else:
            unknown.append(e)
    if unknown:
        print(f"[warn] ignoring unknown exchange id(s): {', '.join(unknown)}")
    return ids or universe[:10]


def make_client(exid, cfg):
    klass = getattr(ccxt, exid)
    return klass({
        "enableRateLimit": True,
        "timeout": int(cfg["http_timeout"] * 1000),
    })


def fetch_spot_symbols(client, force=True):
    """Return {symbol: market} for active SPOT markets on this exchange.

    When force=True the market list is fully reloaded so brand-new listings are
    seen; force=False uses CCXT's cached markets (cheap — no network/parse). This
    lets the caller reload on a cadence instead of rebuilding ~100 exchanges
    every cycle, which was the memory spike that OOM-killed the container. Raises
    on failure; the caller treats any exception as "skip this exchange this cycle".
    """
    markets = client.load_markets(force)
    out = {}
    for sym, m in markets.items():
        if not m.get("spot"):
            continue
        if m.get("active") is False:
            continue
        out[sym] = m
    return out


def get_price(client, sym):
    """Return {'ask':float,'last':float} or None if no usable price yet."""
    try:
        t = client.fetch_ticker(sym)
    except Exception:
        return None
    ask = t.get("ask") or t.get("last") or t.get("close")
    last = t.get("last") or t.get("close") or t.get("ask")
    try:
        ask, last = float(ask), float(last)
    except (TypeError, ValueError):
        return None
    if ask <= 0 or last <= 0:
        return None
    return {"ask": ask, "last": last}


# ----------------------------- persistence ----------------------------------

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def ensure_csv_header():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(TRADES_CSV):
        with open(TRADES_CSV, "w", newline="") as f:
            csv.writer(f).writerow([
                "detected_at", "opened_at", "closed_at", "exchange", "pair_id",
                "wsname", "entry", "exit", "stake_quote", "pnl_pct", "pnl_quote",
                "reason", "hold_minutes", "peak_pct", "intel",
            ])


def log_trade(row):
    ensure_csv_header()
    with open(TRADES_CSV, "a", newline="") as f:
        csv.writer(f).writerow(row)


def log_skip(exid, sym, reason, m):
    """Record a pair the research gate rejected, so rejections are auditable
    (did the filter save us from a rug, or skip a winner?)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    new = not os.path.exists(SKIPS_CSV)
    with open(SKIPS_CSV, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["skipped_at", "exchange", "pair", "reason", "last",
                        "quote_vol_24h", "spread_bps", "bid_depth_quote"])
        w.writerow([
            ts(), exid, sym, reason,
            f"{m.get('last'):.10g}" if m.get("last") is not None else "",
            f"{m.get('quote_vol_24h'):.2f}" if m.get("quote_vol_24h") is not None else "",
            f"{m.get('spread_bps'):.1f}" if m.get("spread_bps") is not None else "",
            f"{m.get('bid_depth_quote'):.2f}" if m.get("bid_depth_quote") is not None else "",
        ])
    # [2026-07-15 EVIDENCE] Mirror the skip to Postgres — the false-negative
    # half of the gate only lived in sniper_skips.csv, which a redeploy wipes,
    # so nothing could ever ask "did the gate dodge rugs or skip winners?".
    # SEPARATE bot name because fetch_paper_aggregate counts every row for a
    # bot; side='skip' keeps the rows out of every trade reader. One-shot per
    # pair: both call sites baseline the pair right after logging.
    try:
        with _store_lock:
            store.publish_paper_trade(
                "event-listing-sniper-skips",
                trade_id=f"skip:{exid}:{sym}:{ts()}",
                pnl_abs=None, pair=sym, closed_at=ts(), reason=reason,
                side="skip",
                extra={"exchange": exid, "last": m.get("last"),
                       "quote_vol_24h": m.get("quote_vol_24h"),
                       "spread_bps": m.get("spread_bps"),
                       "bid_depth_quote": m.get("bid_depth_quote")},
            )
    except Exception:
        pass


# ----------------------------- pair filters ---------------------------------

def quote_matches(market, quotes):
    return str(market.get("quote", "")).upper() in quotes


def base_skipped(market):
    b = str(market.get("base", "")).upper()
    if b in SKIP_BASES or b in TOKENIZED_BASES:
        return True
    # Tokenized-stock sections often suffix the underlying ticker (Kraken
    # xStocks style: AAPLX/TSLAX). Catch TICKER+X variants of the known set.
    if b.endswith("X") and b[:-1] in TOKENIZED_BASES:
        return True
    # [2026-07-01] Exclude leveraged / ETF tokens. The sniper bought SOXL3L (a 3x
    # leveraged token) and stopped out -$50; these decay/gap and don't belong in a
    # fresh-listing snipe. Covers e.g. SOXL3L/BTC3L/ETH5S/XRP2L and UP/DOWN/BULL/BEAR.
    if b.endswith(("2L", "2S", "3L", "3S", "4L", "4S", "5L", "5S",
                   "UP", "DOWN", "BULL", "BEAR")):
        return True
    return False


# ----------------------------- pre-trade research ---------------------------
# A brand-new listing has NO price history to backtest, so "research" here means
# inspecting its LIVE microstructure on public endpoints (ticker + order book)
# before committing paper capital. This is what was missing when the sniper went
# 6 losses / 6 trades: it bought the very first print of every new pair, spread
# and liquidity unchecked, and rode the open-candle spike straight back down.
#
# All calls below are PUBLIC (fetch_ticker / fetch_order_book) — no keys, no
# orders, still 100% dry-run.

def research_market(client, sym, cfg):
    """Pull live microstructure for a candidate pair. Returns a metrics dict.

    Keys: ok(bool), reason(str on failure), last, quote_vol_24h, spread_bps,
    best_bid, best_ask, bid_depth_quote, ask_depth_quote. Never raises.
    """
    m = {"ok": False, "reason": "", "last": None, "quote_vol_24h": None,
         "spread_bps": None, "best_bid": None, "best_ask": None,
         "bid_depth_quote": None, "ask_depth_quote": None}

    # --- ticker: last price + 24h volume (volume is a SOFT signal for new pairs,
    #     which legitimately have tiny 24h history right after listing) ---
    try:
        t = client.fetch_ticker(sym)
    except Exception as e:  # noqa: BLE001
        m["reason"] = f"no_ticker:{type(e).__name__}"
        return m
    last = t.get("last") or t.get("close") or t.get("ask")
    try:
        m["last"] = float(last) if last is not None else None
    except (TypeError, ValueError):
        m["last"] = None
    qv = t.get("quoteVolume")
    bv = t.get("baseVolume")
    if qv is None and bv is not None and m["last"]:
        try:
            qv = float(bv) * m["last"]
        except (TypeError, ValueError):
            qv = None
    try:
        m["quote_vol_24h"] = float(qv) if qv is not None else None
    except (TypeError, ValueError):
        m["quote_vol_24h"] = None

    # --- order book: spread + resting depth (the real test of "can I exit?") ---
    try:
        ob = client.fetch_order_book(sym, limit=int(cfg.get("book_levels", 25)))
    except Exception as e:  # noqa: BLE001
        m["reason"] = f"no_book:{type(e).__name__}"
        return m
    bids = ob.get("bids") or []
    asks = ob.get("asks") or []
    if not bids or not asks:
        m["reason"] = "one_sided_book"  # cannot exit a one-sided market
        return m
    try:
        best_bid = float(bids[0][0]); best_ask = float(asks[0][0])
    except (TypeError, ValueError, IndexError):
        m["reason"] = "bad_book"
        return m
    if best_bid <= 0 or best_ask <= 0 or best_ask < best_bid:
        m["reason"] = "bad_book"
        return m
    m["best_bid"], m["best_ask"] = best_bid, best_ask
    mid = (best_bid + best_ask) / 2.0
    m["spread_bps"] = (best_ask - best_bid) / mid * 10_000.0
    band = float(cfg.get("depth_band_pct", 0.05))
    bid_floor = best_bid * (1 - band)
    ask_ceil = best_ask * (1 + band)

    def _depth(levels, keep):
        tot = 0.0
        for lvl in levels:
            try:
                px, amt = float(lvl[0]), float(lvl[1])
            except (TypeError, ValueError, IndexError):
                continue
            if keep(px):
                tot += px * amt  # quote-currency value resting at this level
        return tot

    m["bid_depth_quote"] = _depth(bids, lambda px: px >= bid_floor)
    m["ask_depth_quote"] = _depth(asks, lambda px: px <= ask_ceil)
    m["ok"] = True
    m["reason"] = "ok"
    return m


def research_gate(client, sym, cfg, state):
    """Decide whether a candidate passes the pre-trade research gate.

    `state` is the per-candidate pending dict (carries first-seen time + the
    earliest observed price, so we can enforce an observation window and an
    anti-chase check). Returns (passed: bool, reason: str, metrics: dict).

    Disable the whole gate with cfg['research']=False to restore the old
    buy-the-first-print behaviour.
    """
    if not cfg.get("research", True):
        return True, "research_off", {}

    age = max(0.0, time.time() - state.get("ts", time.time()))

    # 1) OBSERVATION WINDOW — never buy the opening print. Let the launch candle
    #    settle so we're not handed the top tick.
    min_obs = float(cfg.get("min_observe_sec", 0))
    if age < min_obs:
        return False, f"observing({age:.0f}/{min_obs:.0f}s)", {}

    m = research_market(client, sym, cfg)
    if not m.get("ok"):
        return False, m.get("reason", "research_fail"), m

    # Capture the earliest price we ever saw for the anti-chase check.
    if state.get("first_px") is None and m.get("last"):
        state["first_px"] = m["last"]

    fails = []

    # 2) SPREAD — a blown-out spread means you pay the top and sell the bottom.
    sp = m.get("spread_bps")
    max_sp = float(cfg.get("max_spread_bps", 0))
    if max_sp > 0 and sp is not None and sp > max_sp:
        fails.append(f"wide_spread({sp:.0f}>{max_sp:.0f}bps)")

    # 3) EXIT LIQUIDITY — the bid side within `depth_band_pct` of touch must be
    #    able to absorb our stake several times over, or the paper exit is fiction.
    bd = m.get("bid_depth_quote") or 0.0
    need = float(cfg.get("min_depth_mult", 0)) * float(cfg.get("stake", 0))
    if need > 0 and bd < need:
        fails.append(f"thin_book({bd:.0f}<{need:.0f})")

    # 4) VOLUME FLOOR — soft, off by default (new pairs have little 24h history).
    qv = m.get("quote_vol_24h")
    min_qv = float(cfg.get("min_quote_vol", 0))
    if min_qv > 0:
        if qv is None:
            fails.append("vol_unknown")
        elif qv < min_qv:
            fails.append(f"low_vol({qv:.0f}<{min_qv:.0f})")

    # 5) ANTI-CHASE — if it already ran far past where we first saw it, the easy
    #    move is gone and we'd be buying the blow-off top.
    fp = state.get("first_px")
    max_pump = float(cfg.get("max_launch_pump", 0))
    if max_pump > 0 and fp and m.get("last"):
        run = (m["last"] / fp) - 1.0
        if run > max_pump:
            fails.append(f"already_pumped(+{run*100:.0f}%)")

    if fails:
        return False, ";".join(fails), m
    return True, "pass", m


_GHOST_SKIPPED = set()  # [2026-07-07] symbols dropped by the delisting-risk gate (log once)

# ----------------------------- paper trading --------------------------------

def open_position(exid, client, sym, market, cfg, detected_at, research=None):
    px = get_price(client, sym)
    if px is None:
        return None  # no price yet; try again next cycle
    slip = cfg["slippage_bps"] / 10_000.0
    entry = px["ask"] * (1 + slip)  # simulate paying a bit above ask
    quote_ccy = str(market.get("quote", "")).upper() or cfg["quotes"][0]
    research = research or {}
    # [2026-07-04 INTEL] Classify the ticket: pre-announced by a major exchange
    # or CoinGecko-known -> full stake; provably unknown junk -> half stake.
    # Fail-safe neutral (1.0x) on any intel failure.
    intel_tag, intel_mult, intel_detail = ("unknown", 1.0, "intel off")
    if intel is not None:
        try:
            intel_tag, intel_mult, intel_detail = intel.classify(sym)
        except Exception:
            pass
    # [2026-07-07 DELISTING GATE] 80% of lifetime exits were `delisted` (−$47):
    # tickets on tokens that die on the vine. The killable subclass is the
    # "ghost": junk intel (no announcement, no CoinGecko page) AND first seen
    # on a minor venue. Skip those outright; junk on a top-15 venue still gets
    # a quarter ticket so the ANSEM-class tail stays reachable.
    if intel_tag == "junk" and exid not in CURATED[:15]:
        if sym not in _GHOST_SKIPPED:
            _GHOST_SKIPPED.add(sym)
            print(f"[{ts()}] GHOST-SKIP {sym} on {exid}: junk intel + minor venue "
                  f"(delisting-risk gate; {intel_detail})")
        return None
    pos = {
        "exchange": exid,
        "pair_id": sym,
        "wsname": sym,
        "detected_at": detected_at,
        "opened_at": ts(),
        "opened_ts": time.time(),
        "entry": entry,
        "stake_quote": cfg["stake"] * intel_mult,
        "intel": intel_tag,
        "intel_detail": intel_detail,
        "quote": quote_ccy,
        "peak": entry,
        "remaining_frac": 1.0,   # scale-out / trailing-stop state
        "tp1_done": False,
        # snapshot of the microstructure that cleared the research gate, so a
        # post-mortem can ask "what did liquidity look like when we bought?"
        "entry_spread_bps": research.get("spread_bps"),
        "entry_bid_depth_quote": research.get("bid_depth_quote"),
        "entry_quote_vol_24h": research.get("quote_vol_24h"),
    }
    sl_txt = "none" if cfg["sl"] <= 0 else f"-{cfg['sl']*100:.0f}%"
    sp = research.get("spread_bps")
    bd = research.get("bid_depth_quote")
    rtxt = ""
    if sp is not None or bd is not None:
        rtxt = (f"  [spread {sp:.0f}bps, bid-depth "
                f"{(bd or 0):.0f} {quote_ccy}]")
    print(f"  >> PAPER BUY [{exid}] {sym} @ {entry:.8g}  "
          f"(stake {pos['stake_quote']:.0f} {quote_ccy}, tp {cfg['tp_mult']:.0f}x / sl {sl_txt})"
          f"{rtxt}  [intel: {intel_tag} — {intel_detail}]")
    return pos


def _exit_row(pos, exit_price, reason, sold_stake, held_min):
    """Build a CSV row for a (partial or full) exit of `sold_stake` of quote."""
    entry = pos["entry"]
    pnl_pct = (exit_price / entry) - 1.0
    pnl_quote = sold_stake * pnl_pct
    peak_pct = (pos["peak"] / entry) - 1.0
    return [
        pos["detected_at"], pos["opened_at"], ts(), pos["exchange"],
        pos["pair_id"], pos["wsname"],
        f"{entry:.10g}", f"{exit_price:.10g}", f"{sold_stake:.2f}",
        f"{pnl_pct*100:.2f}", f"{pnl_quote:.2f}", reason,
        f"{held_min:.1f}", f"{peak_pct*100:.2f}",
        pos.get("intel", "?"),
    ], pnl_pct, pnl_quote


def maybe_close(pos, client, cfg):
    """Manage an open paper position. Returns (fully_closed_bool, rows_list).

    EXPERT EXIT MODEL (2026-06-21) — replaces the old all-or-nothing "sell at 5x
    or stop at -50%". New listings typically spike then bleed out, so a single
    far take-profit gives the whole gain back. Instead we:
      1. SCALE OUT: sell `tp1_frac` (default 50%) at `tp1_mult` (default 2x = +100%)
         to bank the spike and move the rest to house money.
      2. TRAIL THE RUNNER: once the trade is up `trail_arm` (default +50%) or the
         partial has fired, exit the remainder if price falls `trail_from_peak`
         (default 30%) from its peak — captures the move instead of round-tripping.
      3. Hard stop from entry, a far runner take-profit (`tp_mult`), and max-hold
         all still apply as backstops.
    Tunables read from cfg with safe defaults so existing CLI/config still works.
    """
    px = get_price(client, pos["pair_id"])
    held_min = (time.time() - pos["opened_ts"]) / 60.0
    if px is None:
        # ZOMBIE GUARD (2026-07-02): fresh listings get pulled/delisted often,
        # and "no usable price" used to mean "keep holding forever" — the main
        # way 85 open positions accumulated with zero exits. If the ticker has
        # been continuously unpriceable for `no_price_give_up_min`, close at the
        # last price we ever saw (entry if we never saw one). Last-known is the
        # least-biased estimate available; a true rug reads too rosy, but
        # holding a phantom position forever reads as exactly $0 risk, which
        # is worse.
        first = pos.setdefault("no_price_since", time.time())
        no_px_min = (time.time() - first) / 60.0
        if no_px_min >= cfg.get("no_price_give_up_min", 60):
            exit_px = pos.get("last_px") or pos["entry"]
            remaining_stake = pos["stake_quote"] * pos.get("remaining_frac", 1.0)
            row, pp, pq = _exit_row(pos, exit_px, "delisted", remaining_stake, held_min)
            _print_sell(pos, row[7], pp, pq, "delisted", cfg)
            return True, [row]
        return False, []
    pos.pop("no_price_since", None)  # priceable again — reset the give-up clock
    last = px["last"]
    pos["last_px"] = last  # remembered for zombie exits + unrealized P&L
    entry = pos["entry"]
    pos["peak"] = max(pos["peak"], last)

    # Backward-compatible state for positions opened before this change.
    pos.setdefault("remaining_frac", 1.0)
    pos.setdefault("tp1_done", False)
    full_stake = pos["stake_quote"]
    remaining_stake = full_stake * pos["remaining_frac"]

    tp1_mult = cfg.get("tp1_mult", 2.0)        # first scale-out target (x entry)
    tp1_frac = cfg.get("tp1_frac", 0.5)        # fraction of ORIGINAL to sell there
    trail_arm = cfg.get("trail_arm", 0.5)      # arm trail once +50% from entry
    trail_gap = cfg.get("trail_from_peak", 0.30)  # exit if 30% below peak
    tp_price = entry * cfg["tp_mult"]          # far runner target (full exit)
    peak = pos["peak"]
    rows = []

    # --- 1) Hard stop-loss from entry (close everything still held) ---
    if cfg["sl"] > 0 and last <= entry * (1 - cfg["sl"]):
        row, pp, pq = _exit_row(pos, entry * (1 - cfg["sl"]), "stop_loss",
                                remaining_stake, held_min)
        _print_sell(pos, row[7], pp, pq, "stop_loss", cfg)
        return True, [row]

    # --- 2) Partial take-profit (scale out) — fires once ---
    if (not pos["tp1_done"]) and tp1_frac > 0 and last >= entry * tp1_mult:
        sold = full_stake * tp1_frac
        row, pp, pq = _exit_row(pos, last, "take_profit_partial", sold, held_min)
        _print_sell(pos, row[7], pp, pq, "take_profit_partial", cfg)
        pos["tp1_done"] = True
        pos["remaining_frac"] = max(0.0, pos["remaining_frac"] - tp1_frac)
        rows.append(row)
        remaining_stake = full_stake * pos["remaining_frac"]
        if pos["remaining_frac"] <= 1e-9:
            return True, rows  # nothing left to ride

    # --- 3) Trailing stop on the runner (only once armed) ---
    armed = pos["tp1_done"] or (peak >= entry * (1 + trail_arm))
    if armed and trail_gap > 0 and last <= peak * (1 - trail_gap):
        row, pp, pq = _exit_row(pos, last, "trail_stop", remaining_stake, held_min)
        _print_sell(pos, row[7], pp, pq, "trail_stop", cfg)
        return True, rows + [row]

    # --- 4) Far runner take-profit (full exit of remainder) ---
    if last >= tp_price:
        row, pp, pq = _exit_row(pos, tp_price, "take_profit", remaining_stake, held_min)
        _print_sell(pos, row[7], pp, pq, "take_profit", cfg)
        return True, rows + [row]

    # --- 5) Max hold (full exit of remainder) ---
    if cfg["max_hold"] > 0 and held_min >= cfg["max_hold"]:
        row, pp, pq = _exit_row(pos, last, "max_hold", remaining_stake, held_min)
        _print_sell(pos, row[7], pp, pq, "max_hold", cfg)
        return True, rows + [row]

    return False, rows  # still open (rows may hold a partial fill this cycle)


def _print_sell(pos, exit_price_str, pnl_pct, pnl_quote, reason, cfg):
    emoji = "✅" if pnl_pct >= 0 else "❌"
    quote_ccy = pos.get("quote", cfg["quotes"][0])
    print(f"  << PAPER SELL [{pos['exchange']}] {pos['wsname']} @ {float(exit_price_str):.8g}  "
          f"{emoji} {pnl_pct*100:+.2f}% ({pnl_quote:+.2f} {quote_ccy})  [{reason}]")


# ----------------------------- concurrency helper ---------------------------

def poll_all(clients, cfg, force=True):
    """Concurrently fetch {exid: {symbol: market}} for every client.

    Exchanges are processed in BATCHES of cfg["batch_size"] rather than all at
    once. Reloading ~100 exchanges' full market lists simultaneously spikes
    memory hard (each response parses into thousands of market dicts) and was
    OOM-killing the container; batching bounds the peak to one batch's worth and
    we gc between batches to release the transient parse buffers. `force` is
    passed through to control full-reload vs cached markets.

    Returns (results, skipped) where skipped maps exid -> error string.

    A single exchange whose request hangs past ccxt's own per-request timeout
    must NOT be able to freeze the whole monitor loop. ThreadPoolExecutor's
    context manager waits for *every* worker on exit, and Future.result() blocks
    with no timeout, so one stuck socket would otherwise stall the bot
    indefinitely — the process stays alive (status still "online") but never
    loops or publishes again. That is the one failure mode the Railway
    `restartPolicyType = "always"` policy can NOT recover from, because the
    process never exits to be restarted. So we bound the whole cycle with a
    deadline and abandon any laggards (recorded as "timeout") so the loop always
    makes forward progress.
    """
    results, skipped = {}, {}
    items = list(clients.items())
    batch = max(1, int(cfg.get("batch_size", cfg["workers"])))
    workers = max(1, min(cfg["workers"], batch))
    # Per-batch deadline so one exchange whose request hangs past ccxt's own
    # per-request timeout can't freeze the loop. Each batch runs in at most
    # ceil(batch/workers) concurrent waves; allow that many http_timeouts plus
    # one wave of slack before we declare a hang and abandon the laggards.
    waves = math.ceil(batch / workers)
    deadline = max(60.0, cfg["http_timeout"] * (waves + 1))
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futs = {ex.submit(fetch_spot_symbols, c, force): exid
                    for exid, c in chunk}
            try:
                for fut in as_completed(futs, timeout=deadline):
                    exid = futs[fut]
                    try:
                        results[exid] = fut.result()
                    except Exception as e:
                        skipped[exid] = type(e).__name__
            except FuturesTimeoutError:
                for fut, exid in futs.items():
                    if exid not in results and exid not in skipped:
                        skipped[exid] = "timeout"
                        fut.cancel()
        finally:
            # Never block the loop on stuck workers: abandon them and carry on,
            # then gc to release this batch's transient market-parse buffers.
            ex.shutdown(wait=False, cancel_futures=True)
            gc.collect()
    return results, skipped


# ----------------------------- seed / monitor -------------------------------

STOP = False


def handle_sigint(signum, frame):
    global STOP
    STOP = True
    print("\n[stop] finishing current cycle then exiting…")


def build_clients(exchange_ids, cfg):
    clients = {}
    for exid in exchange_ids:
        try:
            clients[exid] = make_client(exid, cfg)
        except Exception as e:
            print(f"[warn] could not init {exid}: {type(e).__name__} — skipping")
    return clients


def seed_baseline(cfg, exchange_ids):
    clients = build_clients(exchange_ids, cfg)
    print(f"[seed] snapshotting {len(clients)} exchanges (concurrency {cfg['workers']})…")
    results, skipped = poll_all(clients, cfg, force=True)
    per_ex = {exid: sorted(syms.keys()) for exid, syms in results.items()}
    known = {"exchanges": per_ex, "seeded_at": ts()}
    save_json(KNOWN_FILE, known)
    total = sum(len(v) for v in per_ex.values())
    print(f"[seed] baseline saved: {total} spot pairs across {len(per_ex)} exchanges "
          f"as of {known['seeded_at']}")
    if skipped:
        print(f"[seed] skipped {len(skipped)} unreachable/errored: "
              f"{', '.join(sorted(skipped)[:15])}{' …' if len(skipped) > 15 else ''}")
    print(f"[seed] file: {KNOWN_FILE}")
    print("[seed] now run:  python3 listing_sniper.py")


def _load_db_state(retries=3, wait_s=5):
    """Postgres state read with retries: a cold container's FIRST connection can
    flake (observed 2026-07-04: baseline restore missed at boot, the very next
    read 60s later succeeded and restored 25 positions). Never raises."""
    for i in range(retries):
        try:
            st = store.load_state("event-listing-sniper")
            if st:
                return st
        except Exception:
            pass
        if i < retries - 1:
            time.sleep(wait_s)
    return None


def monitor(cfg, exchange_ids):
    known = load_json(KNOWN_FILE, None)
    # [2026-07-03 PERSIST] Local sniper_data/ now lives on a Railway volume, but
    # keep the durable Postgres fallback (mirrored each cycle below) for volume
    # loss / first mounts — the open snipes are where the fat-tail winners live,
    # and re-seeding also blinds us to listings that fired during a rebuild.
    _db_state = None
    if not known or "exchanges" not in known:
        _db_state = _load_db_state()
        if _db_state and (_db_state.get("known") or {}).get("exchanges"):
            known = _db_state["known"]
            print(f"[start] restored baseline from Postgres "
                  f"({len(known['exchanges'])} exchanges, "
                  f"seeded {known.get('seeded_at', '?')}).")
    if not known or "exchanges" not in known:
        print("[!] No baseline found. Seeding now so we don't fire on every existing pair…")
        seed_baseline(cfg, exchange_ids)
        return

    baseline = {exid: set(syms) for exid, syms in known["exchanges"].items()}
    clients = build_clients(exchange_ids, cfg)
    # Make sure every selected exchange has a baseline entry (new ones get seeded
    # on first sight rather than firing on their whole existing pair list).
    newly_tracked = [e for e in clients if e not in baseline]

    sl_txt = "none" if cfg["sl"] <= 0 else f"-{cfg['sl']*100:.0f}%"
    hold_txt = "none" if cfg["max_hold"] <= 0 else f"{cfg['max_hold']}m"
    print(f"[start] DRY-RUN multi-exchange monitor. {len(clients)} exchanges, "
          f"baseline seeded {known.get('seeded_at','?')}.")
    print(f"[start] quotes={','.join(cfg['quotes'])}  interval={cfg['interval']}s  "
          f"workers={cfg['workers']}  tp={cfg['tp_mult']:.0f}x  sl={sl_txt}  "
          f"max_hold={hold_txt}  stake={cfg['stake']}")
    if cfg.get("research", True):
        print(f"[start] research gate ON — observe {cfg['min_observe_sec']:.0f}s, "
              f"max spread {cfg['max_spread_bps']:.0f}bps, "
              f"min bid-depth {cfg['min_depth_mult']:.1f}x stake within "
              f"{cfg['depth_band_pct']*100:.0f}%, "
              f"anti-chase +{cfg['max_launch_pump']*100:.0f}%, "
              f"give up after {cfg['max_pending_min']:.0f}m"
              + (f", min 24h vol {cfg['min_quote_vol']:.0f}" if cfg['min_quote_vol'] > 0 else ""))
    else:
        print("[start] research gate OFF — buying first print (legacy behaviour).")
    if newly_tracked:
        print(f"[start] {len(newly_tracked)} newly-added exchange(s) will be "
              f"baselined on first poll (no fire on existing pairs).")
    print("[start] No real orders are ever placed. Ctrl-C to stop.\n")

    pending = load_json(PENDING_FILE, {})   # "exid|symbol" -> first_seen
    positions = load_json(OPEN_FILE, [])
    # [2026-07-03 PERSIST] Same Postgres fallback for the open book + pending
    # watchlist when the local files were wiped by a redeploy.
    if not positions and not pending:
        if _db_state is None:
            _db_state = _load_db_state()
        if _db_state:
            if _db_state.get("positions"):
                positions = _db_state["positions"]
                print(f"[start] restored {len(positions)} open position(s) from Postgres.")
            if _db_state.get("pending"):
                pending = _db_state["pending"]

    threading.Thread(target=_heartbeat_loop, daemon=True,
                     name="dashboard-heartbeat").start()

    cycle = 0
    while not STOP:
        cycle_start = time.time()
        # Reload full market lists only every `reload_every` cycles; use CCXT's
        # cached markets in between. New listings are rare and the research gate
        # waits 120s+ before acting, so detecting them on a few-minute cadence
        # (instead of rebuilding ~100 exchanges every 60s) costs nothing real but
        # removes the per-cycle memory spike that was OOM-killing the bot.
        force = (cycle % max(1, cfg.get("reload_every", 5)) == 0)
        results, skipped = poll_all(clients, cfg, force=force)
        if not results:
            print(f"[{ts()}] all {len(clients)} exchanges unreachable this cycle — "
                  f"retrying in {cfg['interval']}s")
            time.sleep(cfg["interval"])
            continue

        total_pairs = 0
        new_detected = 0
        for exid, syms in results.items():
            total_pairs += len(syms)
            base = baseline.get(exid)
            if base is None:
                # First time we see this exchange: baseline it, don't fire.
                baseline[exid] = set(syms.keys())
                continue
            for sym in set(syms.keys()) - base:
                market = syms[sym]
                if not quote_matches(market, set(cfg["quotes"])):
                    base.add(sym)  # not our quote; remember and ignore
                    continue
                if base_skipped(market):
                    base.add(sym)
                    continue
                key = f"{exid}|{sym}"
                if key not in pending:
                    pending[key] = {"first_seen": ts(), "ts": time.time(),
                                    "first_px": None, "checks": 0,
                                    "last_reason": ""}
                    new_detected += 1
                    print(f"[{ts()}] 🆕 NEW PAIR: [{exid}] {sym} "
                          f"(status={market.get('active')})")

        # Promote pending -> open paper position, but only after the pre-trade
        # research gate clears (observation window + spread + exit liquidity +
        # anti-chase). Rejected candidates stay pending and are re-checked until
        # they either pass or age out, so a pair that's illiquid at launch can
        # still qualify once a real market forms.
        still_pending = {}
        gate_pass = gate_wait = gate_drop = 0
        max_pending_sec = float(cfg.get("max_pending_min", 0)) * 60.0
        for key, st in pending.items():
            # Back-compat: older pending.json stored a bare timestamp string.
            if not isinstance(st, dict):
                st = {"first_seen": st, "ts": time.time(), "first_px": None,
                      "checks": 0, "last_reason": ""}
            exid, sym = key.split("|", 1)
            syms = results.get(exid)
            client = clients.get(exid)
            if syms is None or client is None:
                still_pending[key] = st  # exchange unreachable this cycle
                continue
            market = syms.get(sym)
            if market is None:
                continue  # vanished; drop it
            tradable = (market.get("active") is not False) or cfg["any_status"]
            if not tradable:
                still_pending[key] = st
                continue

            # INVENTORY CAP (2026-07-02): with max_hold formerly unlimited the
            # book grew monotonically (85 open at the worst). Bound how much
            # paper capital can be tied up at once; a full book means the next
            # listing is skipped and baselined, not queued.
            if cfg.get("max_open", 0) > 0 and len(positions) >= cfg["max_open"]:
                gate_drop += 1
                log_skip(exid, sym, f"inventory_cap:{cfg['max_open']}", {})
                print(f"  SKIP [{exid}] {sym} — open-position cap "
                      f"({cfg['max_open']}) reached")
                baseline.setdefault(exid, set()).add(sym)  # stop re-detecting
                continue

            st["checks"] = st.get("checks", 0) + 1
            passed, reason, metrics = research_gate(client, sym, cfg, st)
            st["last_reason"] = reason
            if not passed:
                age = time.time() - st.get("ts", time.time())
                if max_pending_sec > 0 and age >= max_pending_sec:
                    gate_drop += 1
                    log_skip(exid, sym, f"aged_out:{reason}", metrics)
                    print(f"  SKIP [{exid}] {sym} — gave up after "
                          f"{age/60:.0f}m ({reason})")
                    baseline.setdefault(exid, set()).add(sym)  # stop re-detecting
                    continue
                gate_wait += 1
                still_pending[key] = st  # keep observing / re-checking
                continue

            pos = open_position(exid, client, sym, market, cfg,
                                st.get("first_seen", ts()), metrics)
            if pos:
                gate_pass += 1
                positions.append(pos)
                baseline.setdefault(exid, set()).add(sym)
            else:
                # [2026-07-16 AUDIT FIX] the age-out only covered the
                # gate-FAIL branch: a gate-passing candidate that
                # open_position skips deterministically (GHOST-SKIP: junk
                # intel + minor venue, or persistent no-price) re-pended
                # FOREVER, re-spending API calls every cycle until the venue
                # delisted the pair. Same give-up applies here.
                age = time.time() - st.get("ts", time.time())
                if max_pending_sec > 0 and age >= max_pending_sec:
                    gate_drop += 1
                    log_skip(exid, sym, "aged_out:no_open", metrics)
                    print(f"  SKIP [{exid}] {sym} — gave up after "
                          f"{age/60:.0f}m (gate passed, no open)")
                    baseline.setdefault(exid, set()).add(sym)
                    continue
                still_pending[key] = st  # no fill price yet, keep trying
        pending = still_pending

        # Manage open paper trades
        remaining = []
        for pos in positions:
            client = clients.get(pos["exchange"])
            if client is None:
                remaining.append(pos)  # exchange not in this run; hold position
                continue
            try:
                closed, rows = maybe_close(pos, client, cfg)
            except Exception as e:
                print(f"  ! error managing [{pos.get('exchange')}] "
                      f"{pos.get('wsname')}: {e}")
                remaining.append(pos)
                continue
            for row in rows:          # may include a partial scale-out fill
                log_trade(row)
                # Mirror each closed fill into the durable Postgres ledger so the
                # cumulative P&L survives a Railway redeploy that wipes the local
                # CSV (the cause of the 2026-06-25 reset to $0 / 0 closed).
                try:
                    with _store_lock:
                        store.publish_paper_trade(
                            "event-listing-sniper",
                            # [2026-07-16 AUDIT FIX] reason is part of the id:
                            # a same-cycle partial+final pair (e.g. tp1 +
                            # trail_stop) shared opened/closed to the second,
                            # so ON CONFLICT silently overwrote one leg — CSV
                            # and DB totals diverged, DB (missing a leg) wins
                            # after a redeploy.
                            trade_id=f"{row[3]}:{row[4]}:{row[1]}:{row[2]}:{row[11]}",
                            pnl_abs=float(row[10]),
                            pnl_pct=float(row[9]) / 100.0,
                            pair=row[5], opened_at=row[1], closed_at=row[2],
                            # [2026-07-15 GAP FIX] direction-prefixed so the
                            # brain can bucket this book per-sleeve (its 337
                            # closes were permanently '(untagged)'). Parser
                            # splits at the FIRST underscore ->
                            # enter_tag 'long-listing', exit_reason preserved.
                            reason="long-listing_" + str(row[11]),
                            # [2026-07-15 EVIDENCE] outcome context: the intel
                            # class and the entry-time microstructure snapshot
                            # were captured at open but never reached Postgres,
                            # so post-mortems couldn't ask "what did the book
                            # look like when we bought the losers?" (feeds the
                            # go-live-gate restatement, agenda item 5).
                            entry_price=pos["entry"], exit_price=float(row[7]),
                            size=float(row[8]), side="long",
                            tag=pos.get("intel"),
                            extra={"exchange": pos["exchange"],
                                   "entry_spread_bps": pos.get("entry_spread_bps"),
                                   "entry_bid_depth_quote": pos.get("entry_bid_depth_quote"),
                                   "entry_quote_vol_24h": pos.get("entry_quote_vol_24h"),
                                   "intel_detail": pos.get("intel_detail"),
                                   "peak_pct": float(row[13]) / 100.0,
                                   "hold_minutes": float(row[12])},
                        )
                except Exception:
                    pass
            if not closed:
                remaining.append(pos)  # runner still riding (possibly reduced)
        positions = remaining

        # Persist state every cycle so restarts are safe
        _known_blob = {
            "exchanges": {e: sorted(s) for e, s in baseline.items()},
            "seeded_at": known.get("seeded_at", ts()),
        }
        save_json(KNOWN_FILE, _known_blob)
        save_json(OPEN_FILE, positions)
        save_json(PENDING_FILE, pending)
        # [2026-07-03 PERSIST] Mirror the same three blobs to Postgres so a
        # redeploy restores them (local sniper_data/ does not survive deploys).
        try:
            with _store_lock:
                store.save_state("event-listing-sniper", {
                    "known": _known_blob,
                    "positions": positions,
                    "pending": pending,
                })
        except Exception:
            pass

        # [2026-07-14 L3 SIGNAL BUS] Publish the intel classifications as their
        # own bot_state key. The 07-07 design's Layer 3 called for scanner
        # knowledge on the bus; until now classifications lived only in-process,
        # invisible to the brain/dashboard. `updated` is ISO so consumers can
        # apply the standard freshness contract (fleet_bus.is_fresh).
        try:
            _intel_counts = {}
            for _p in positions:
                _k = _p.get("intel") or "unknown"
                _intel_counts[_k] = _intel_counts.get(_k, 0) + 1
            with _store_lock:
                store.save_state("listing-intel", {
                    "updated": now_utc().isoformat(timespec="seconds"),
                    "ttl_sec": 1800,
                    "open_by_class": _intel_counts,
                    "ghost_skipped_total": len(_GHOST_SKIPPED),
                    "open_detail": [
                        {"sym": _p.get("pair_id"), "class": _p.get("intel"),
                         "detail": _p.get("intel_detail"),
                         "venue": _p.get("exchange")}
                        for _p in positions[:40]
                    ],
                })
        except Exception:
            pass

        # Heartbeat
        ok_n = len(results)
        skip_n = len(skipped)
        print(f"[{ts()}] ok — {ok_n}/{len(clients)} exchanges | "
              f"{total_pairs} pairs | new this cycle: {new_detected} | "
              f"open: {len(positions)} | pending: {len(pending)} | "
              f"gate(passed {gate_pass}/waiting {gate_wait}/dropped {gate_drop}) | "
              f"skipped: {skip_n}", flush=True)

        # Publish a snapshot for the live dashboard (guarded; never raises).
        # Fast path: aggregate the local CSV.
        realized, nclosed, wins = 0.0, 0, 0
        try:
            if os.path.exists(TRADES_CSV):
                with open(TRADES_CSV) as _f:
                    for _r in csv.DictReader(_f):
                        try:
                            _pnl = float(_r.get("pnl_quote") or 0)
                        except (TypeError, ValueError):
                            continue
                        realized += _pnl
                        nclosed += 1
                        wins += 1 if _pnl > 0 else 0
        except Exception:
            pass
        # Reconcile with the durable Postgres ledger. After a redeploy the local
        # CSV is empty, so the DB (which has every closed fill) carries the real
        # cumulative totals — take whichever source has more closed trades so the
        # figures can only move forward, never silently reset to zero.
        try:
            with _store_lock:
                _agg = store.fetch_paper_aggregate("event-listing-sniper")
            if _agg and _agg["closed"] >= nclosed:
                realized, nclosed, wins = _agg["realized"], _agg["closed"], _agg["wins"]
        except Exception:
            pass
        # Mark the open book to market so the dashboard stops hiding it: pnl_abs
        # is realized-only, and 85 quietly bleeding positions used to read as a
        # healthy +$272.89. last_px is refreshed by every maybe_close price hit;
        # positions not yet priced this run are counted separately.
        unrealized, n_priced = 0.0, 0
        for _p in positions:
            _lp = _p.get("last_px")
            if _lp:
                unrealized += ((_lp / _p["entry"]) - 1.0) * _p["stake_quote"] * _p.get("remaining_frac", 1.0)
                n_priced += 1
        _pub_kwargs = dict(status="online",
                           # [2026-07-16] equity = paper start + realized +
                           # open unrealized. Never published before, so this
                           # bot's dd/age go-live gates were permanently blank.
                           # Only equity rows from now on carry a value, so the
                           # age gate honestly counts the equity track record
                           # we actually have (0/30d), not the bot's uptime.
                           equity=round(START_EQUITY + realized + unrealized, 2),
                           pnl_abs=realized, open_trades=len(positions),
                           closed_trades=nclosed, wins=wins, losses=nclosed - wins,
                           extra={"pending": len(pending), "exchanges_ok": ok_n,
                                  "exchanges_skipped": skip_n,
                                  "gate_passed": gate_pass, "gate_waiting": gate_wait,
                                  "gate_dropped": gate_drop,
                                  "unrealized": round(unrealized, 2),
                                  "open_priced": n_priced,
                                  "research": bool(cfg.get("research", True))})
        with _store_lock:
            store.publish("event-listing-sniper", **_pub_kwargs)
        # Hand the snapshot to the heartbeat thread so it can keep the
        # dashboard's updated_at fresh through the next long reload cycle.
        _last_publish["kwargs"] = _pub_kwargs
        _last_publish["ts"] = time.monotonic()

        # Drop this cycle's market maps before sleeping so they don't sit
        # resident across the interval; gc reclaims them promptly.
        del results
        gc.collect()
        cycle += 1

        # Sleep the remainder of the interval
        elapsed = time.time() - cycle_start
        time.sleep(max(1.0, cfg["interval"] - elapsed))

    print("[exit] state saved. Bye.")


def main():
    p = argparse.ArgumentParser(description="DRY-RUN multi-exchange new-listing paper-trader")
    p.add_argument("--seed", action="store_true",
                   help="Snapshot current pairs as baseline, then exit.")
    p.add_argument("--exchanges", default="top100",
                   help='Which exchanges to search: "topN" (default top100), '
                        '"all", or a comma list of CCXT ids.')
    p.add_argument("--workers", type=int, default=12,
                   help="How many exchanges to poll in parallel (default 12).")
    p.add_argument("--batch-size", type=int, default=8,
                   help="Reload markets in batches of this many exchanges to cap "
                        "peak memory (default 8). Lower if the container OOMs.")
    p.add_argument("--reload-every", type=int, default=5,
                   help="Force a full market reload every N cycles; use cached "
                        "markets in between (default 5). New-listing detection "
                        "latency is about N*interval seconds.")
    p.add_argument("--interval", type=float, default=60, help="Seconds between polls.")
    p.add_argument("--http-timeout", type=float, default=20,
                   help="Per-request timeout in seconds (default 20).")
    p.add_argument("--quote", default="USD,USDT,USDC,EUR",
                   help="Comma-separated quote currencies to snipe "
                        "(default USD,USDT,USDC,EUR — wider than USD-only).")
    p.add_argument("--tp-mult", type=float, default=5.0,
                   help="Take-profit as a MULTIPLE of entry (5.0 = sell at 5x). Default 5x.")
    # [2026-07-04 THROTTLE] Live record hit 13W/90L and realized P&L bled from
    # +$263 to +$194 in ~3 days — the drip of small losing tickets was outpacing
    # the occasional winner. Defaults tightened (the Railway service runs with no
    # flags, so these ARE the live settings): smaller stake, tighter stop, fewer
    # concurrent tickets, shorter max hold, and a stricter research gate below.
    p.add_argument("--sl", type=float, default=0.35,
                   help="Stop-loss fraction (0.35=-35%%). Set 0 to disable (ride to 5x or zero).")
    p.add_argument("--max-hold", type=float, default=1440,
                   help="Max hold in minutes; 0 = no limit. Default 1440 (24h): "
                        "listings spike then bleed; anything not working within a "
                        "day is dead capital.")
    p.add_argument("--max-open", type=int, default=10,
                   help="Max concurrent open paper positions; new detections are "
                        "dropped (logged) while at the cap. 0 = no cap. Default 10.")
    p.add_argument("--no-price-give-up-min", type=float, default=60,
                   help="Close a position at its last known price after this many "
                        "minutes of continuously unpriceable ticker (delisted/"
                        "vanished pair). Default 60.")
    p.add_argument("--stake", type=float, default=50, help="Paper stake per trade (quote ccy).")
    p.add_argument("--slippage-bps", type=float, default=30,
                   help="Simulated buy slippage in basis points (30=0.30%%).")
    p.add_argument("--any-status", action="store_true",
                   help="Open paper trade as soon as pair appears (not just when active).")

    # --- pre-trade research gate (Balanced defaults) -----------------------
    # The sniper now inspects each new pair's LIVE order book + ticker before
    # buying, instead of taking the first print blind. Disable with --no-research.
    g = p.add_argument_group("research gate (pre-trade quality checks)")
    g.add_argument("--no-research", dest="research", action="store_false",
                   help="Disable the research gate (revert to buy-the-first-print).")
    p.set_defaults(research=True)
    g.add_argument("--min-observe-sec", type=float, default=120,
                   help="Observation window: wait this long after first sight "
                        "before buying, to skip the opening spike (default 120s).")
    # [2026-07-04 THROTTLE] Gate tightened with the sizing cut above: the skips
    # log showed the 500bps spread + 3x depth gate still let through thin books
    # that drifted straight down. Fewer, better tickets.
    g.add_argument("--max-spread-bps", type=float, default=250,
                   help="Reject if bid/ask spread exceeds this (default 250 = 2.5%%). 0 disables.")
    g.add_argument("--min-depth-mult", type=float, default=5.0,
                   help="Require resting bid-side depth within --depth-band-pct of "
                        "touch to be >= this multiple of --stake (default 5x). 0 disables.")
    g.add_argument("--depth-band-pct", type=float, default=0.05,
                   help="Price band around touch used to measure book depth (default 0.05 = 5%%).")
    g.add_argument("--min-quote-vol", type=float, default=25000,
                   help="24h quote-volume floor (default 25000). Just-listed pairs "
                        "build volume fast when real; set 0 to disable.")
    g.add_argument("--max-launch-pump", type=float, default=1.0,
                   help="Anti-chase: skip if price already ran more than this "
                        "fraction above where we first saw it (default 1.0 = +100%%). 0 disables.")
    g.add_argument("--max-pending-min", type=float, default=30,
                   help="Give up on a candidate that never passes the gate after "
                        "this many minutes (default 30). 0 = wait forever.")
    g.add_argument("--book-levels", type=int, default=25,
                   help="Order-book levels to pull for depth analysis (default 25).")

    args = p.parse_args()

    print("=" * 64)
    print(" MULTI-EXCHANGE LISTING SNIPER — DRY-RUN (no keys, no real orders)")
    print("=" * 64)

    quotes = [q.strip().upper() for q in str(args.quote).split(",") if q.strip()]
    if not quotes:
        quotes = ["USD"]
    cfg = {
        "exchanges": args.exchanges, "workers": max(1, args.workers),
        "batch_size": max(1, args.batch_size),
        "reload_every": max(1, args.reload_every),
        "interval": args.interval, "http_timeout": args.http_timeout,
        "quotes": quotes,
        "tp_mult": args.tp_mult, "sl": args.sl,
        "max_hold": args.max_hold, "stake": args.stake,
        "max_open": max(0, args.max_open),
        "no_price_give_up_min": args.no_price_give_up_min,
        "slippage_bps": args.slippage_bps, "any_status": args.any_status,
        # research gate
        "research": args.research,
        "min_observe_sec": args.min_observe_sec,
        "max_spread_bps": args.max_spread_bps,
        "min_depth_mult": args.min_depth_mult,
        "depth_band_pct": args.depth_band_pct,
        "min_quote_vol": args.min_quote_vol,
        "max_launch_pump": args.max_launch_pump,
        "max_pending_min": args.max_pending_min,
        "book_levels": args.book_levels,
    }

    exchange_ids = resolve_exchanges(args.exchanges)
    print(f"[cfg] searching {len(exchange_ids)} exchanges: "
          f"{', '.join(exchange_ids[:12])}{' …' if len(exchange_ids) > 12 else ''}")

    if args.seed:
        seed_baseline(cfg, exchange_ids)
        return

    signal.signal(signal.SIGINT, handle_sigint)
    monitor(cfg, exchange_ids)


if __name__ == "__main__":
    main()
