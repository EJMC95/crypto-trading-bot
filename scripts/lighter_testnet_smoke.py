#!/usr/bin/env python3
"""
scripts/lighter_testnet_smoke.py — Gate-0 testnet order-lifecycle smoke test.

Two layers:
  READ-ONLY (no keys needed — always runs):
    * market list on the testnet base URL
    * candles + funding endpoints answer
    * ws book stream connects, streams, and RECOVERS after a forced drop
  AUTHENTICATED (runs only when env keys exist — no keys in the repo, ever):
        LIGHTER_API_PRIVATE_KEY, LIGHTER_ACCOUNT_INDEX, LIGHTER_API_KEY_INDEX
    * signer check
    * on 2 markets (ETH, BTC): far-from-touch limit place -> modify -> cancel,
      market open ($15 clip) -> reduce-only close
    * nonce recovery: two rapid-fire orders on one key index
    * kill-switch flip: assert SafetyRails blocks a lighter_live start

Usage:
    python3 scripts/lighter_testnet_smoke.py            # one full pass
    python3 scripts/lighter_testnet_smoke.py --burn-in  # repeat hourly forever
                                                        # (compressed 48h loop —
                                                        # any manual intervention
                                                        # = gate-fail, log it)

Every step prints PASS/FAIL/SKIP; exit code 1 if anything FAILED.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS = []


def step(name, fn, skip=None):
    if skip:
        print(f"[SKIP] {name} — {skip}")
        RESULTS.append((name, "SKIP"))
        return None
    try:
        out = fn()
        print(f"[PASS] {name}" + (f" — {out}" if isinstance(out, str) else ""))
        RESULTS.append((name, "PASS"))
        return out if out is not None else True
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name} — {e!r}")
        RESULTS.append((name, "FAIL"))
        return None


def one_pass():
    del RESULTS[:]
    from venues.lighter_client import LighterClient
    from venues.safety import SafetyRails, KILL_ENV

    # ---- read-only layer ----------------------------------------------------
    vc = step("testnet client + market list",
              lambda: LighterClient(net="testnet"))
    if not vc:
        return False
    step("markets active (need >=2 for lifecycle)",
         lambda: f"{[s for s, m in vc.markets.items() if m['status'] == 'active']}")

    now_ms = int(time.time() * 1000)
    step("candles ETH 1h x 24",
         lambda: f"{len(vc.candles('ETH', '1h', now_ms - 24*3600*1000, now_ms))} candles")
    step("funding endpoint answers",
         lambda: f"{len(vc.funding_map())} markets with funding")

    def ws_book_and_reconnect():
        b1 = vc.orderbook("ETH")
        assert b1["bids"] and b1["asks"], "empty book"
        # force-drop the ws; the cache thread must reconnect + resubscribe
        vc._books._wake.set()
        time.sleep(8)
        b2 = vc.orderbook("ETH")
        assert b2["bids"] and b2["asks"], "book not recovered after drop"
        return f"top bid {b2['bids'][0][0]} (recovered after forced drop)"
    step("ws book stream + forced reconnect", ws_book_and_reconnect)

    # ---- kill-switch behaviour (no keys needed) ------------------------------
    def kill_switch_blocks_live():
        os.environ.pop(KILL_ENV, None)  # default = armed
        try:
            SafetyRails("perps-rsi-meanrev", "lighter_live").assert_can_start()
        except SystemExit:
            return "lighter_live refused while armed (correct)"
        raise AssertionError("lighter_live was allowed with the kill switch armed!")
    step("REAL_MONEY_KILL blocks lighter_live start", kill_switch_blocks_live)

    # ---- authenticated layer --------------------------------------------------
    have_keys = bool(os.environ.get("LIGHTER_API_PRIVATE_KEY", "").strip()
                     and os.environ.get("LIGHTER_ACCOUNT_INDEX", "").strip())
    skip = None if have_keys else "no LIGHTER_API_PRIVATE_KEY/LIGHTER_ACCOUNT_INDEX in env"

    if not have_keys:
        for name in ("signer check", "limit place/modify/cancel x2 markets",
                     "market open + reduce-only close x2 markets",
                     "nonce recovery (rapid-fire)"):
            step(name, lambda: None, skip=skip)
    else:
        auth = step("signer check",
                    lambda: LighterClient(net="testnet", with_signer=True))
        if auth:
            sc = auth.signer

            def lifecycle(coin):
                _, _, m = auth._resolve(coin)
                book = auth.orderbook(coin)
                bid = book["bids"][0][0]
                # far-from-touch resting limit (50% below bid, min size)
                px_f = bid * 0.5
                size = max(m["min_base"], round(15.0 / px_f, m["size_decimals"]))
                base, px = auth._scaled(m, size, px_f)
                coi = int(time.time() * 1000) % (2 ** 48)
                import asyncio
                run = lambda coro: asyncio.run_coroutine_threadsafe(
                    coro, auth._loop).result(timeout=30)
                tx, resp, err = run(sc.create_order(
                    m["id"], coi, base, px, is_ask=False,
                    order_type=sc.ORDER_TYPE_LIMIT,
                    time_in_force=sc.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                    order_expiry=sc.DEFAULT_28_DAY_ORDER_EXPIRY,
                    api_key_index=auth.api_key_index))
                assert not err, f"place: {err}"
                base2, px2 = auth._scaled(m, size, px_f * 0.98)
                tx, resp, err = run(sc.modify_order(
                    m["id"], coi, base2, px2, trigger_price=0,
                    api_key_index=auth.api_key_index))
                assert not err, f"modify: {err}"
                tx, resp, err = run(sc.cancel_order(
                    m["id"], coi, api_key_index=auth.api_key_index))
                assert not err, f"cancel: {err}"
                # market open + reduce-only close
                auth.market_open(coin, True, max(m["min_base"],
                                                 round(15.0 / bid, m["size_decimals"])))
                time.sleep(2)
                auth.market_close(coin)
                return f"{coin}: place/modify/cancel + open/close OK"

            for coin in ("ETH", "BTC"):
                step(f"order lifecycle {coin}", lambda c=coin: lifecycle(c))

            def rapid_fire():
                for _ in range(3):
                    auth.market_open("ETH", True, 0.01)
                    auth.market_close("ETH")
                return "3 rapid open/close cycles (nonce manager held)"
            step("nonce recovery (rapid-fire)", rapid_fire)

    fails = [n for n, r in RESULTS if r == "FAIL"]
    print(f"\nSMOKE SUMMARY: {sum(1 for _, r in RESULTS if r == 'PASS')} pass, "
          f"{len(fails)} fail, {sum(1 for _, r in RESULTS if r == 'SKIP')} skip")
    if fails:
        print("FAILED:", fails)
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--burn-in", action="store_true",
                    help="repeat hourly forever (overnight compressed burn-in)")
    args = ap.parse_args()
    ok = one_pass()
    while args.burn_in:
        print(f"\n[burn-in] sleeping 1h; pass so far: {ok}  ({time.ctime()})",
              flush=True)
        time.sleep(3600)
        ok = one_pass() and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
