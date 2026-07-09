#!/usr/bin/env python3
"""
scripts/lighter_day1.py — Gate-0 day-1 verification probe for Lighter.xyz.

Read-only, unauthenticated, public REST only. Fetches the full market list with
per-market tick/step/decimals + min order sizes, diffs every HL-facing bot's
universe against it, and emits both a JSON snapshot and the markdown tables for
docs/lighter.md. Paced well under the 60 weighted-req/min standard-tier budget.

Usage:
    python3 scripts/lighter_day1.py                # mainnet probe -> stdout JSON
    python3 scripts/lighter_day1.py --testnet      # probe the testnet base URL
    python3 scripts/lighter_day1.py --out FILE     # also write JSON snapshot
"""
import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

MAINNET = "https://mainnet.zklighter.elliot.ai"
TESTNET = "https://testnet.zklighter.elliot.ai"   # candidate; verified by probe

# The universes the fleet actually trades (from the bot sources, 2026-07-09).
PERPS_COINS = [  # hyperliquid_momo_bot.py + hyperliquid_perps_bot.py (identical)
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ARB", "OP",
    "SUI", "SEI", "TIA", "APT", "NEAR", "INJ", "LTC", "BCH", "ATOM", "DOT",
    "ADA", "AAVE", "PEPE", "WIF", "kBONK", "ENA", "ORDI", "JUP", "TON", "kSHIB",
    "HYPE", "ZEC", "TAO",
]
REGIME_COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "LINK", "AVAX", "DOGE",
                "LTC", "ADA", "HYPE", "ZEC"]  # config_regimeswitch.json (freqtrade, wave-2)

PACE_SEC = 1.5  # be polite: well under any public rate budget


def get(base, path, timeout=15):
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, headers={"User-Agent": "gate0-day1-probe"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return {"ok": True, "status": r.status, "ms": int((time.time() - t0) * 1000),
                    "json": json.loads(body)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "ms": int((time.time() - t0) * 1000),
                "error": e.read().decode()[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": None, "ms": int((time.time() - t0) * 1000),
                "error": repr(e)[:300]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testnet", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    base = TESTNET if args.testnet else MAINNET

    snap = {"base": base, "at": datetime.now(timezone.utc).isoformat(), "endpoints": {}}

    # 1) Full market list + per-market metadata.
    r = get(base, "/api/v1/orderBookDetails")
    snap["endpoints"]["orderBookDetails"] = {k: r[k] for k in ("ok", "status", "ms")}
    details = []
    if r["ok"]:
        details = (r["json"].get("order_book_details")
                   or r["json"].get("orderBookDetails") or [])
    time.sleep(PACE_SEC)

    if not details:  # fallback: plain orderBooks list
        r2 = get(base, "/api/v1/orderBooks")
        snap["endpoints"]["orderBooks"] = {k: r2[k] for k in ("ok", "status", "ms")}
        if r2["ok"]:
            details = r2["json"].get("order_books") or []
        time.sleep(PACE_SEC)

    markets = {}
    for d in details:
        sym = d.get("symbol")
        if not sym:
            continue
        markets[sym] = {
            "market_id": d.get("market_id"),
            "status": d.get("status"),
            "price_decimals": d.get("price_decimals"),
            "size_decimals": d.get("size_decimals"),
            "supported_price_decimals": d.get("supported_price_decimals"),
            "supported_size_decimals": d.get("supported_size_decimals"),
            "min_base_amount": d.get("min_base_amount"),
            "min_quote_amount": d.get("min_quote_amount"),
            "taker_fee": d.get("taker_fee"),
            "maker_fee": d.get("maker_fee"),
            "last_trade_price": d.get("last_trade_price"),
            "daily_quote_token_volume": d.get("daily_quote_token_volume"),
        }
    snap["market_count"] = len(markets)
    snap["markets"] = markets

    # 2) Funding-rate endpoint parity check (shape only, one market).
    for path in ("/api/v1/fundings?market_id=0&resolution=1h&limit=2",
                 "/api/v1/funding-rates", "/api/v1/exchangeStats"):
        r = get(base, path)
        snap["endpoints"][path] = {k: r[k] for k in ("ok", "status", "ms")}
        if r["ok"]:
            snap["endpoints"][path]["sample"] = json.dumps(r["json"])[:600]
        time.sleep(PACE_SEC)

    # 3) Universe diff — which HL coins have a Lighter market (incl. 1000x remaps).
    def lighter_symbol_for(hl_coin):
        # HL k-prefixed coins are 1000-denominated; Lighter uses a 1000 prefix.
        if hl_coin in markets:
            return hl_coin, 1.0
        if hl_coin.startswith("k") and ("1000" + hl_coin[1:]) in markets:
            return "1000" + hl_coin[1:], 1.0        # same 1000-unit denomination
        if ("1000" + hl_coin) in markets:
            return "1000" + hl_coin, 0.001          # HL 1 unit = 1/1000 Lighter unit
        return None, None

    diff = {}
    for name, uni in (("perps-pilots+carry", PERPS_COINS), ("regime-switch(wave2)", REGIME_COINS)):
        rows = {}
        for c in uni:
            sym, mult = lighter_symbol_for(c)
            rows[c] = {"lighter": sym, "size_mult": mult}
        diff[name] = rows
        missing = [c for c, v in rows.items() if v["lighter"] is None]
        diff[name + ":missing"] = missing
    snap["universe_diff"] = diff

    out = json.dumps(snap, indent=2, default=str)
    if args.out:
        with open(args.out, "w") as f:
            f.write(out)
    print(out)


if __name__ == "__main__":
    sys.exit(main())
