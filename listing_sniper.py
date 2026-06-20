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
    --max-hold 0         max minutes to hold; 0 = no time limit (default), so a 5x can run
    --stake 100          paper stake per trade in quote currency (default 100)
    --slippage-bps 30    simulated buy slippage in basis points (default 30)
    --any-status         open a paper trade as soon as the pair appears, even
                         before the exchange flips it to "active" (more
                         aggressive, less realistic).

Files written (in ./sniper_data/):
    known_pairs.json     per-exchange baseline + every pair ever seen
    open_positions.json  currently-open paper trades (survives restarts)
    sniper_trades.csv     closed paper-trade log (your results)
"""

import argparse
import csv
import os
import re
import json
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import ccxt  # unified multi-exchange public API

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sniper_data")
KNOWN_FILE = os.path.join(DATA_DIR, "known_pairs.json")
OPEN_FILE = os.path.join(DATA_DIR, "open_positions.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending.json")
TRADES_CSV = os.path.join(DATA_DIR, "sniper_trades.csv")

# Bases we never want to "snipe" (stablecoins / wrapped fiat — not real launches)
SKIP_BASES = {
    "USDT", "USDC", "DAI", "PYUSD", "USD", "EUR", "GBP", "AUD", "CAD", "CHF",
    "JPY", "ZUSD", "ZEUR", "ZGBP", "ZAUD", "ZCAD", "ZJPY", "USDG", "RLUSD",
    "TUSD", "FDUSD", "USDD", "USDP", "GUSD", "EURT", "EURS", "BUSD",
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


def fetch_spot_symbols(client):
    """Return {symbol: market} for active SPOT markets on this exchange.

    Forces a market reload so brand-new listings are seen. Raises on failure;
    the caller treats any exception as "skip this exchange this cycle".
    """
    markets = client.load_markets(True)
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
                "reason", "hold_minutes", "peak_pct",
            ])


def log_trade(row):
    ensure_csv_header()
    with open(TRADES_CSV, "a", newline="") as f:
        csv.writer(f).writerow(row)


# ----------------------------- pair filters ---------------------------------

def quote_matches(market, quotes):
    return str(market.get("quote", "")).upper() in quotes


def base_skipped(market):
    return str(market.get("base", "")).upper() in SKIP_BASES


# ----------------------------- paper trading --------------------------------

def open_position(exid, client, sym, market, cfg, detected_at):
    px = get_price(client, sym)
    if px is None:
        return None  # no price yet; try again next cycle
    slip = cfg["slippage_bps"] / 10_000.0
    entry = px["ask"] * (1 + slip)  # simulate paying a bit above ask
    quote_ccy = str(market.get("quote", "")).upper() or cfg["quotes"][0]
    pos = {
        "exchange": exid,
        "pair_id": sym,
        "wsname": sym,
        "detected_at": detected_at,
        "opened_at": ts(),
        "opened_ts": time.time(),
        "entry": entry,
        "stake_quote": cfg["stake"],
        "quote": quote_ccy,
        "peak": entry,
        "remaining_frac": 1.0,   # scale-out / trailing-stop state
        "tp1_done": False,
    }
    sl_txt = "none" if cfg["sl"] <= 0 else f"-{cfg['sl']*100:.0f}%"
    print(f"  >> PAPER BUY [{exid}] {sym} @ {entry:.8g}  "
          f"(stake {cfg['stake']} {quote_ccy}, tp {cfg['tp_mult']:.0f}x / sl {sl_txt})")
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
    if px is None:
        return False, []
    last = px["last"]
    entry = pos["entry"]
    pos["peak"] = max(pos["peak"], last)
    held_min = (time.time() - pos["opened_ts"]) / 60.0

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

def poll_all(clients, cfg):
    """Concurrently fetch {exid: {symbol: market}} for every client.

    Returns (results, skipped) where skipped maps exid -> error string.
    """
    results, skipped = {}, {}
    with ThreadPoolExecutor(max_workers=cfg["workers"]) as ex:
        futs = {ex.submit(fetch_spot_symbols, c): exid for exid, c in clients.items()}
        for fut in as_completed(futs):
            exid = futs[fut]
            try:
                results[exid] = fut.result()
            except Exception as e:
                skipped[exid] = type(e).__name__
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
    results, skipped = poll_all(clients, cfg)
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


def monitor(cfg, exchange_ids):
    known = load_json(KNOWN_FILE, None)
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
    if newly_tracked:
        print(f"[start] {len(newly_tracked)} newly-added exchange(s) will be "
              f"baselined on first poll (no fire on existing pairs).")
    print("[start] No real orders are ever placed. Ctrl-C to stop.\n")

    pending = load_json(PENDING_FILE, {})   # "exid|symbol" -> first_seen
    positions = load_json(OPEN_FILE, [])

    while not STOP:
        cycle_start = time.time()
        results, skipped = poll_all(clients, cfg)
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
                    pending[key] = ts()
                    new_detected += 1
                    print(f"[{ts()}] 🆕 NEW PAIR: [{exid}] {sym} "
                          f"(status={market.get('active')})")

        # Promote pending -> open paper position when tradable
        still_pending = {}
        for key, first_seen in pending.items():
            exid, sym = key.split("|", 1)
            syms = results.get(exid)
            client = clients.get(exid)
            if syms is None or client is None:
                # exchange unreachable this cycle; keep pending for later
                still_pending[key] = first_seen
                continue
            market = syms.get(sym)
            if market is None:
                continue  # vanished; drop it
            tradable = (market.get("active") is not False) or cfg["any_status"]
            if not tradable:
                still_pending[key] = first_seen
                continue
            pos = open_position(exid, client, sym, market, cfg, first_seen)
            if pos:
                positions.append(pos)
                baseline.setdefault(exid, set()).add(sym)  # done detecting this pair
            else:
                still_pending[key] = first_seen  # no price yet, keep trying
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
            if not closed:
                remaining.append(pos)  # runner still riding (possibly reduced)
        positions = remaining

        # Persist state every cycle so restarts are safe
        save_json(KNOWN_FILE, {
            "exchanges": {e: sorted(s) for e, s in baseline.items()},
            "seeded_at": known.get("seeded_at", ts()),
        })
        save_json(OPEN_FILE, positions)
        save_json(PENDING_FILE, pending)

        # Heartbeat
        ok_n = len(results)
        skip_n = len(skipped)
        print(f"[{ts()}] ok — {ok_n}/{len(clients)} exchanges | "
              f"{total_pairs} pairs | new this cycle: {new_detected} | "
              f"open: {len(positions)} | pending: {len(pending)} | "
              f"skipped: {skip_n}", flush=True)

        # Publish a snapshot for the live dashboard (guarded; never raises).
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
        store.publish("listing-sniper", status="online",
                      pnl_abs=realized, open_trades=len(positions),
                      closed_trades=nclosed, wins=wins, losses=nclosed - wins,
                      extra={"pending": len(pending), "exchanges_ok": ok_n,
                             "exchanges_skipped": skip_n})

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
    p.add_argument("--interval", type=float, default=60, help="Seconds between polls.")
    p.add_argument("--http-timeout", type=float, default=20,
                   help="Per-request timeout in seconds (default 20).")
    p.add_argument("--quote", default="USD,USDT,USDC,EUR",
                   help="Comma-separated quote currencies to snipe "
                        "(default USD,USDT,USDC,EUR — wider than USD-only).")
    p.add_argument("--tp-mult", type=float, default=5.0,
                   help="Take-profit as a MULTIPLE of entry (5.0 = sell at 5x). Default 5x.")
    p.add_argument("--sl", type=float, default=0.50,
                   help="Stop-loss fraction (0.50=-50%%). Set 0 to disable (ride to 5x or zero).")
    p.add_argument("--max-hold", type=float, default=0,
                   help="Max hold in minutes; 0 = no time limit (default), so a 5x can run.")
    p.add_argument("--stake", type=float, default=100, help="Paper stake per trade (quote ccy).")
    p.add_argument("--slippage-bps", type=float, default=30,
                   help="Simulated buy slippage in basis points (30=0.30%%).")
    p.add_argument("--any-status", action="store_true",
                   help="Open paper trade as soon as pair appears (not just when active).")
    args = p.parse_args()

    print("=" * 64)
    print(" MULTI-EXCHANGE LISTING SNIPER — DRY-RUN (no keys, no real orders)")
    print("=" * 64)

    quotes = [q.strip().upper() for q in str(args.quote).split(",") if q.strip()]
    if not quotes:
        quotes = ["USD"]
    cfg = {
        "exchanges": args.exchanges, "workers": max(1, args.workers),
        "interval": args.interval, "http_timeout": args.http_timeout,
        "quotes": quotes,
        "tp_mult": args.tp_mult, "sl": args.sl,
        "max_hold": args.max_hold, "stake": args.stake,
        "slippage_bps": args.slippage_bps, "any_status": args.any_status,
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
