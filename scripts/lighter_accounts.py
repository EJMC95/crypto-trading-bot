#!/usr/bin/env python3
"""
scripts/lighter_accounts.py — READ-ONLY Lighter sub-account + API-key mapper.

You run this (not the assistant). It takes your PUBLIC L1 address — the wallet
address, never a private key — and prints every sub-account under it, each
sub-account's collateral, and the API-key indices registered to it. Use it to
map each live bot to its own sub-account before setting the Railway env vars.

    python3 scripts/lighter_accounts.py 0xYOURL1ADDRESS
    python3 scripts/lighter_accounts.py 0xYOURL1ADDRESS --testnet

Nothing here signs, trades, or needs a key. It only reads public account state.
"""
import argparse
import asyncio
import sys

MAINNET = "https://mainnet.zklighter.elliot.ai"
TESTNET = "https://testnet.zklighter.elliot.ai"


async def run(l1_address, base):
    try:
        import lighter
    except ImportError:
        print("pip install lighter-sdk first"); return 1
    cfg = lighter.Configuration(host=base)
    api = lighter.ApiClient(configuration=cfg)
    aa = lighter.AccountApi(api)
    try:
        r = await aa.accounts_by_l1_address(l1_address=l1_address)
        subs = r.to_dict().get("sub_accounts") or []
        if not subs:
            print(f"No sub-accounts found for {l1_address} on {base}.")
            print("Create them in the Lighter app (Account -> sub-accounts) first.")
            return 0
        print(f"L1 {l1_address} on {base}: {len(subs)} sub-account(s)\n")
        print(f"{'index':>6} {'type':>5} {'status':>7} {'collateral':>14} {'orders':>7}")
        for s in sorted(subs, key=lambda x: x.get("index", 0)):
            idx = s.get("index")
            print(f"{idx:>6} {s.get('account_type'):>5} {s.get('status'):>7} "
                  f"{str(s.get('collateral')):>14} {s.get('total_order_count'):>7}")
            # API keys registered to this sub-account (indices 2-254 are usable)
            try:
                ak = await aa.apikeys(account_index=int(idx), api_key_index=255)
                keys = ak.to_dict().get("api_keys") or []
                live_keys = [k.get("api_key_index") for k in keys
                             if str(k.get("public_key") or "").strip("0")]
                print(f"       └─ registered API-key indices: "
                      f"{live_keys or '(none — register one in the app)'}")
            except Exception as e:  # noqa: BLE001
                print(f"       └─ (couldn't read API keys: {e!r})")
        print("\nMap each live bot to ONE sub-account index + ONE API-key index,")
        print("then set per Railway service: LIGHTER_ACCOUNT_INDEX / "
              "LIGHTER_API_KEY_INDEX / LIGHTER_API_PRIVATE_KEY.")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"Lookup failed: {e!r}")
        return 1
    finally:
        await api.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("l1_address", help="your PUBLIC Lighter L1 wallet address (0x...)")
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()
    if not args.l1_address.startswith("0x"):
        print("Pass your public 0x… L1 address (never a private key).")
        sys.exit(2)
    sys.exit(asyncio.run(run(args.l1_address, TESTNET if args.testnet else MAINNET)))


if __name__ == "__main__":
    main()
