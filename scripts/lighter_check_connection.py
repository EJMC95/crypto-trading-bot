#!/usr/bin/env python3
"""
scripts/lighter_check_connection.py — READ-ONLY API-key connection test.

You run this (not the assistant). It proves your bot API key authenticates
against your Lighter account. It places NO orders, moves NO funds — it only
calls the SDK's signer `check_client()` (validates the key is registered) and
reads your account balance. Your private key is read from an env var, used
locally, and NEVER printed, logged, or transmitted anywhere.

    export LIGHTER_API_PRIVATE_KEY=<your index-4 key>   # set locally, then:
    LIGHTER_ACCOUNT_INDEX=733196 LIGHTER_API_KEY_INDEX=4 \
        python3 scripts/lighter_check_connection.py
    unset LIGHTER_API_PRIVATE_KEY                        # clear it afterwards

Add --testnet to point at the testnet base URL instead of mainnet.
"""
import argparse
import asyncio
import os
import sys

MAINNET = "https://mainnet.zklighter.elliot.ai"
TESTNET = "https://testnet.zklighter.elliot.ai"


async def run(base):
    try:
        import lighter
    except ImportError:
        print("pip install lighter-sdk first"); return 1

    key = os.environ.get("LIGHTER_API_PRIVATE_KEY", "").strip()
    acct = os.environ.get("LIGHTER_ACCOUNT_INDEX", "").strip()
    kidx = os.environ.get("LIGHTER_API_KEY_INDEX", "4").strip()
    if not key or not acct:
        print("Set LIGHTER_API_PRIVATE_KEY and LIGHTER_ACCOUNT_INDEX in env first.")
        return 2
    if int(kidx) < 4:
        print(f"WARNING: api key index {kidx} is UI-reserved (0-3). Bots should use 4+.")

    signer = lighter.SignerClient(
        url=base, account_index=int(acct),
        api_private_keys={int(kidx): key})
    err = signer.check_client()   # validates the key is registered — no order, no tx
    if err:
        print(f"❌ NOT CONNECTED: signer check failed — {err}")
        print("   (wrong private key, wrong index, or key not registered on this account)")
        return 1
    print(f"✅ CONNECTED: API key index {kidx} authenticates for account {acct}.")

    # read-only balance confirmation
    api = lighter.ApiClient(configuration=lighter.Configuration(host=base))
    try:
        r = await lighter.AccountApi(api).account(by="index", value=str(acct))
        a = (r.to_dict().get("accounts") or [{}])[0]
        print(f"   account collateral: {a.get('collateral')} USDC  status={a.get('status')}")
        print("   No orders placed, no funds moved. This was a connection test only.")
    finally:
        await api.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(TESTNET if args.testnet else MAINNET)))


if __name__ == "__main__":
    main()
