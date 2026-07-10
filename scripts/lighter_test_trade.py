#!/usr/bin/env python3
"""
scripts/lighter_test_trade.py — user-run LIVE order-path test for Lighter.

YOU run this (not the assistant). It proves the full order pipeline — signing,
nonce, submission, cancel/close — on your real account. Your key comes from env
and is never printed.

DEFAULT (safe, ~$0 risk): places a POST-ONLY resting limit BUY 50% BELOW the
market (cannot fill — it just rests on the book), verifies acceptance, then
CANCELS it. Proves sign+submit+cancel end-to-end without opening a position.

--fill (real trade, ~$10): market-buys the minimum size (~$10 notional), waits
2s, closes it reduce-only. Real position for a few seconds; cost ≈ the spread
(fees are zero). Only run this if you want to see an actual fill.

    export LIGHTER_API_PRIVATE_KEY=<key>          # or use read -rs
    LIGHTER_ACCOUNT_INDEX=733196 LIGHTER_API_KEY_INDEX=4 \
        python3 scripts/lighter_test_trade.py [--coin ETH] [--fill]
    unset LIGHTER_API_PRIVATE_KEY
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="ETH")
    ap.add_argument("--fill", action="store_true",
                    help="REAL ~$10 market round-trip instead of the no-fill test")
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()

    os.environ["VENUE"] = "x"  # not used; we build the client directly
    from venues.lighter_client import LighterClient
    from venues.base import VenueError

    net = "testnet" if args.testnet else "mainnet"
    print(f"[1/4] connecting + authenticating ({net})...")
    try:
        vc = LighterClient(net=net, with_signer=True)
    except VenueError as e:
        print(f"❌ AUTH FAILED: {e}")
        print("    → the key in env doesn't match the one registered on Lighter.")
        return 1
    print("      ✅ authenticated")

    coin = args.coin
    sym, mult, m = vc._resolve(coin)
    book = vc.orderbook(coin)
    if not book["bids"] or not book["asks"]:
        print(f"❌ {coin}: empty book"); return 1
    bid = book["bids"][0][0]
    sc = vc.signer
    run = lambda coro: asyncio.run_coroutine_threadsafe(coro, vc._loop).result(timeout=30)

    if not args.fill:
        # ---- SAFE no-fill test: post-only limit 50% below market, then cancel
        px_f = round(bid * 0.5, m["price_decimals"])
        size = max(m["min_base"], round(10.5 / px_f, m["size_decimals"]))
        base, px = vc._scaled(m, size * mult, px_f)
        coi = int(time.time() * 1000) % (2 ** 48)
        print(f"[2/4] placing POST-ONLY limit BUY {size} {coin} @ {px_f} "
              f"(50% below bid {bid} — cannot fill, will rest)...")
        tx, resp, err = run(sc.create_order(
            m["id"], coi, base, px, is_ask=False,
            order_type=sc.ORDER_TYPE_LIMIT,
            time_in_force=sc.ORDER_TIME_IN_FORCE_POST_ONLY,
            order_expiry=sc.DEFAULT_28_DAY_ORDER_EXPIRY,
            api_key_index=vc.api_key_index))
        if err:
            print(f"❌ PLACE failed: {err}"); return 1
        print("      ✅ order accepted by the exchange (resting on the book)")
        time.sleep(3)
        print("[3/4] cancelling it...")
        tx, resp, err = run(sc.cancel_order(m["id"], coi,
                                            api_key_index=vc.api_key_index))
        if err:
            print(f"❌ CANCEL failed: {err} — check the app and cancel manually!")
            return 1
        print("      ✅ cancelled")
        print("[4/4] RESULT: sign → submit → cancel all work. No position was "
              "opened, no funds spent. The order path is LIVE-READY.")
    else:
        # ---- REAL fill test: min-size market buy, then reduce-only close
        size = max(m["min_base"], round(10.5 / bid, m["size_decimals"]))
        print(f"[2/4] REAL market BUY {size} {coin} (~${size * bid:.2f}) ...")
        vc.market_open(coin, True, size)
        print("      ✅ opened — waiting 2s")
        time.sleep(2)
        pos = vc.positions().get(coin)
        print(f"[3/4] position on exchange: {pos} — closing reduce-only...")
        vc.market_close(coin)
        time.sleep(2)
        left = vc.positions().get(coin)
        print(f"[4/4] RESULT: round-trip complete. remaining position: "
              f"{left or 'NONE (flat)'} — cost ≈ the spread (zero fees).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
