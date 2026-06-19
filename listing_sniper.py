#!/usr/bin/env python3
"""
listing_sniper.py — DRY-RUN Kraken new-listing sniper / paper-trader.

What it does
------------
1. Snapshots every tradable pair on Kraken (public AssetPairs endpoint).
2. Polls on an interval and detects pairs that did NOT exist in the snapshot
   (i.e. brand-new listings) and become tradable ("online").
3. On detection it opens a *paper* position at the current ask price and then
   tracks the price, closing the paper trade on take-profit, stop-loss, or a
   max-hold timeout. Every simulated trade is logged to a CSV.

SAFETY
------
This script is 100% DRY-RUN. It only ever calls Kraken PUBLIC endpoints
(AssetPairs, Ticker). It NEVER reads an API key, NEVER authenticates, and
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
    --interval 30        seconds between polls (default 30; be polite to the API)
    --quote USD          only snipe pairs quoted in this currency (default USD)
    --tp-mult 10         take-profit as a MULTIPLE of entry; 10 = sell at 10x (default 10)
    --sl 0.50            stop-loss, -50% (default); set 0 to disable and ride to 10x or zero
    --max-hold 0         max minutes to hold; 0 = no time limit (default), so a 10x can run
    --stake 100          paper stake per trade in quote currency (default 100)
    --slippage-bps 30    simulated buy slippage in basis points (default 30)
    --any-status         open a paper trade as soon as the pair appears, even
                         before Kraken flips it to "online" (more aggressive,
                         less realistic).

Files written (in ./sniper_data/):
    known_pairs.json     baseline + every pair ever seen (so it never re-fires)
    open_positions.json  currently-open paper trades (survives restarts)
    sniper_trades.csv    closed paper-trade log (your results)
"""

import argparse
import csv
import json
import os
import signal
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)

KRAKEN_BASE = "https://api.kraken.com/0/public"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sniper_data")
KNOWN_FILE = os.path.join(DATA_DIR, "known_pairs.json")
OPEN_FILE = os.path.join(DATA_DIR, "open_positions.json")
TRADES_CSV = os.path.join(DATA_DIR, "sniper_trades.csv")

# Bases we never want to "snipe" (stablecoins / wrapped fiat — not real launches)
SKIP_BASES = {
    "USDT", "USDC", "DAI", "PYUSD", "USD", "EUR", "GBP", "AUD", "CAD", "CHF",
    "JPY", "ZUSD", "ZEUR", "ZGBP", "ZAUD", "ZCAD", "ZJPY", "USDG", "RLUSD",
}


def now_utc():
    return datetime.now(timezone.utc)


def ts():
    return now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")


def http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "listing-sniper-dryrun/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def kraken_asset_pairs():
    """Return {pair_id: info_dict}. Raises on API error."""
    d = http_get_json(f"{KRAKEN_BASE}/AssetPairs")
    if d.get("error"):
        raise RuntimeError(f"Kraken AssetPairs error: {d['error']}")
    return d.get("result", {})


def kraken_ticker(pair_id):
    """Return ask/last as floats, or None if unavailable."""
    url = f"{KRAKEN_BASE}/Ticker?pair={urllib.parse.quote(pair_id)}"
    try:
        d = http_get_json(url)
    except Exception as e:
        print(f"  ! ticker fetch failed for {pair_id}: {e}")
        return None
    if d.get("error"):
        # New pairs sometimes 404 from Ticker for a few seconds; treat as "no data yet"
        return None
    res = d.get("result", {})
    if not res:
        return None
    info = next(iter(res.values()))
    try:
        ask = float(info["a"][0])
        last = float(info["c"][0])
        return {"ask": ask, "last": last}
    except (KeyError, IndexError, ValueError, TypeError):
        return None


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
                "detected_at", "opened_at", "closed_at", "pair_id", "wsname",
                "entry", "exit", "stake_quote", "pnl_pct", "pnl_quote",
                "reason", "hold_minutes", "peak_pct",
            ])


def log_trade(row):
    ensure_csv_header()
    with open(TRADES_CSV, "a", newline="") as f:
        csv.writer(f).writerow(row)


def pair_matches_quote(info, quote):
    """Kraken quotes USD as 'ZUSD' (legacy) or 'USD' (newer). Match via wsname too."""
    q = quote.upper()
    quote_field = str(info.get("quote", "")).upper()
    wsname = str(info.get("wsname", "")).upper()
    altname = str(info.get("altname", "")).upper()
    if quote_field in (q, "Z" + q):
        return True
    if wsname.endswith("/" + q):
        return True
    if altname.endswith(q):
        return True
    return False


def base_symbol(info):
    ws = str(info.get("wsname", ""))
    if "/" in ws:
        return ws.split("/")[0].upper()
    base = str(info.get("base", "")).upper()
    # strip Kraken's legacy X/Z prefix on 4-char codes like XXBT, ZUSD
    if len(base) == 4 and base[0] in ("X", "Z"):
        return base[1:]
    return base


# ----------------------------- core loop ------------------------------------

STOP = False


def handle_sigint(signum, frame):
    global STOP
    STOP = True
    print("\n[stop] finishing current cycle then exiting…")


def seed_baseline():
    pairs = kraken_asset_pairs()
    known = {"ids": sorted(pairs.keys()), "seeded_at": ts()}
    save_json(KNOWN_FILE, known)
    print(f"[seed] baseline saved: {len(pairs)} pairs known as of {known['seeded_at']}")
    print(f"[seed] file: {KNOWN_FILE}")
    print("[seed] now run:  python3 listing_sniper.py")


def open_position(pair_id, info, cfg, detected_at):
    tk = kraken_ticker(pair_id)
    if tk is None or tk["ask"] <= 0:
        return None  # no price yet; try again next cycle
    slip = cfg["slippage_bps"] / 10_000.0
    entry = tk["ask"] * (1 + slip)  # simulate paying a bit above ask
    pos = {
        "pair_id": pair_id,
        "wsname": info.get("wsname", pair_id),
        "detected_at": detected_at,
        "opened_at": ts(),
        "opened_ts": time.time(),
        "entry": entry,
        "stake_quote": cfg["stake"],
        "peak": entry,
    }
    sl_txt = "none" if cfg["sl"] <= 0 else f"-{cfg['sl']*100:.0f}%"
    print(f"  >> PAPER BUY {pos['wsname']} @ {entry:.8g}  "
          f"(stake {cfg['stake']} {cfg['quote']}, tp {cfg['tp_mult']:.0f}x / sl {sl_txt})")
    return pos


def maybe_close(pos, cfg):
    """Return (closed_bool, row_or_None)."""
    tk = kraken_ticker(pos["pair_id"])
    if tk is None:
        return False, None
    last = tk["last"]
    entry = pos["entry"]
    pos["peak"] = max(pos["peak"], last)
    held_min = (time.time() - pos["opened_ts"]) / 60.0

    tp_price = entry * cfg["tp_mult"]  # e.g. 10x = sell at entry * 10
    reason = None
    exit_price = last
    if last >= tp_price:
        reason, exit_price = "take_profit", tp_price
    elif cfg["sl"] > 0 and last <= entry * (1 - cfg["sl"]):
        reason, exit_price = "stop_loss", entry * (1 - cfg["sl"])
    elif cfg["max_hold"] > 0 and held_min >= cfg["max_hold"]:
        reason, exit_price = "max_hold", last

    if reason is None:
        return False, None

    pnl_pct = (exit_price / entry) - 1.0
    pnl_quote = pos["stake_quote"] * pnl_pct
    peak_pct = (pos["peak"] / entry) - 1.0
    row = [
        pos["detected_at"], pos["opened_at"], ts(), pos["pair_id"], pos["wsname"],
        f"{entry:.10g}", f"{exit_price:.10g}", f"{pos['stake_quote']:.2f}",
        f"{pnl_pct*100:.2f}", f"{pnl_quote:.2f}", reason,
        f"{held_min:.1f}", f"{peak_pct*100:.2f}",
    ]
    emoji = "✅" if pnl_pct >= 0 else "❌"
    print(f"  << PAPER SELL {pos['wsname']} @ {exit_price:.8g}  "
          f"{emoji} {pnl_pct*100:+.2f}% ({pnl_quote:+.2f} {cfg['quote']})  [{reason}]")
    return True, row


def monitor(cfg):
    known = load_json(KNOWN_FILE, None)
    if not known or "ids" not in known:
        print("[!] No baseline found. Seeding now so we don't fire on every existing pair…")
        seed_baseline()
        return
    known_ids = set(known["ids"])
    print(f"[start] DRY-RUN monitor. {len(known_ids)} pairs in baseline "
          f"(seeded {known.get('seeded_at','?')}).")
    sl_txt = "none" if cfg["sl"] <= 0 else f"-{cfg['sl']*100:.0f}%"
    hold_txt = "none" if cfg["max_hold"] <= 0 else f"{cfg['max_hold']}m"
    print(f"[start] quote={cfg['quote']}  interval={cfg['interval']}s  "
          f"tp={cfg['tp_mult']:.0f}x  sl={sl_txt}  "
          f"max_hold={hold_txt}  stake={cfg['stake']}")
    print("[start] No real orders are ever placed. Ctrl-C to stop.\n")

    pending = load_json(os.path.join(DATA_DIR, "pending.json"), {})  # id -> first_seen
    positions = load_json(OPEN_FILE, [])

    while not STOP:
        cycle_start = time.time()
        try:
            pairs = kraken_asset_pairs()
        except Exception as e:
            print(f"[{ts()}] AssetPairs fetch failed: {e} — retrying next cycle")
            time.sleep(cfg["interval"])
            continue

        current_ids = set(pairs.keys())
        new_ids = current_ids - known_ids

        for pid in sorted(new_ids):
            info = pairs[pid]
            ws = info.get("wsname", pid)
            if not pair_matches_quote(info, cfg["quote"]):
                known_ids.add(pid)  # not our quote; remember and ignore
                continue
            if base_symbol(info) in SKIP_BASES:
                known_ids.add(pid)
                continue
            if pid not in pending:
                pending[pid] = ts()
                print(f"[{ts()}] 🆕 NEW PAIR DETECTED: {ws} "
                      f"(status={info.get('status','?')})")

        # Promote pending -> open paper position when tradable
        still_pending = {}
        for pid, first_seen in pending.items():
            info = pairs.get(pid)
            if info is None:
                continue  # vanished; drop it
            status = str(info.get("status", "")).lower()
            tradable = status == "online" or cfg["any_status"]
            if tradable:
                pos = open_position(pid, info, cfg, first_seen)
                if pos:
                    positions.append(pos)
                    known_ids.add(pid)  # done with detection for this pair
                else:
                    still_pending[pid] = first_seen  # no price yet, keep trying
            else:
                still_pending[pid] = first_seen
        pending = still_pending

        # Manage open paper trades
        remaining = []
        for pos in positions:
            try:
                closed, row = maybe_close(pos, cfg)
            except Exception as e:
                print(f"  ! error managing {pos.get('wsname')}: {e}")
                remaining.append(pos)
                continue
            if closed:
                log_trade(row)
            else:
                remaining.append(pos)
        positions = remaining

        # Persist state every cycle so restarts are safe
        save_json(KNOWN_FILE, {"ids": sorted(known_ids),
                               "seeded_at": known.get("seeded_at", ts())})
        save_json(OPEN_FILE, positions)
        save_json(os.path.join(DATA_DIR, "pending.json"), pending)

        # Heartbeat
        open_n = len(positions)
        pend_n = len(pending)
        print(f"[{ts()}] ok — {len(current_ids)} pairs | "
              f"open paper trades: {open_n} | pending: {pend_n}", flush=True)

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
                      pnl_abs=realized, open_trades=open_n,
                      closed_trades=nclosed, wins=wins, losses=nclosed - wins,
                      extra={"pending": pend_n})

        # Sleep the remainder of the interval
        elapsed = time.time() - cycle_start
        time.sleep(max(1.0, cfg["interval"] - elapsed))

    print("[exit] state saved. Bye.")


def main():
    p = argparse.ArgumentParser(description="DRY-RUN Kraken new-listing paper-trader")
    p.add_argument("--seed", action="store_true",
                   help="Snapshot current pairs as baseline, then exit.")
    p.add_argument("--interval", type=float, default=30, help="Seconds between polls.")
    p.add_argument("--quote", default="USD", help="Quote currency to snipe (default USD).")
    p.add_argument("--tp-mult", type=float, default=10.0,
                   help="Take-profit as a MULTIPLE of entry (10.0 = sell at 10x). Default 10x.")
    p.add_argument("--sl", type=float, default=0.50,
                   help="Stop-loss fraction (0.50=-50%%). Set 0 to disable (ride to 10x or zero).")
    p.add_argument("--max-hold", type=float, default=0,
                   help="Max hold in minutes; 0 = no time limit (default), so a 10x can run.")
    p.add_argument("--stake", type=float, default=100, help="Paper stake per trade (quote ccy).")
    p.add_argument("--slippage-bps", type=float, default=30,
                   help="Simulated buy slippage in basis points (30=0.30%%).")
    p.add_argument("--any-status", action="store_true",
                   help="Open paper trade as soon as pair appears (not just when 'online').")
    args = p.parse_args()

    print("=" * 64)
    print(" KRAKEN LISTING SNIPER — DRY-RUN (no keys, no real orders)")
    print("=" * 64)

    if args.seed:
        seed_baseline()
        return

    cfg = {
        "interval": args.interval, "quote": args.quote,
        "tp_mult": args.tp_mult, "sl": args.sl,
        "max_hold": args.max_hold, "stake": args.stake,
        "slippage_bps": args.slippage_bps, "any_status": args.any_status,
    }
    signal.signal(signal.SIGINT, handle_sigint)
    monitor(cfg)


if __name__ == "__main__":
    main()
