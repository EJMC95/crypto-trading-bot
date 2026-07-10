# Lighter.xyz venue — Gate-0 verifications (2026-07-09)

Everything here was probed **live and read-only** against Lighter's public API
(`scripts/lighter_day1.py`, `scripts/lighter_testnet_smoke.py`). No keys, no
orders, no funds. Re-run either script to refresh.

## TL;DR
- **Zero maker/taker fees** confirmed on every market (`taker_fee=0.0000`,
  `maker_fee=0.0000`). This is the whole thesis — residual cost is spread +
  slippage, which shadow mode measures.
- **215 active markets** on mainnet (`/api/v1/orderBookDetails`). Perps only.
- **$10 minimum order** (`min_quote_amount`) on *every* market — our pilot
  $25–35 clips clear it with room. This is the binding constraint at low capital.
- **ETH, ADA, HYPE are listed** (the Cowork day-1 excerpt was wrong on ADA/HYPE —
  its API fetch had truncated). **BLUR, ATOM, INJ, ORDI, TON are NOT listed.**
- **Signer binaries load on both** deploy target (linux/amd64, python:3.11-slim)
  **and** the dev Mac (darwin/arm64) — verified via `ctypes.CDLL` + symbol probe.
- **Funding parity is native**: `/api/v1/funding-rates` returns lighter +
  hyperliquid + binance + bybit rates per market in ONE call — the cross-venue
  carry signal the Yield Harvester wave-2 needed comes for free.

## Base URLs
| Net | Base URL | Verified |
|-----|----------|----------|
| Mainnet | `https://mainnet.zklighter.elliot.ai` | 215 markets, 200 OK |
| Testnet | `https://testnet.zklighter.elliot.ai` | 3 markets (ETH id0 / BTC id1 / SOL id2), 200 OK |

WebSocket: `wss://<host>/stream`, channel `order_book/{market_id}`, `account_all/{account_index}`.

## Rate limits (standard account)
- **60 WEIGHTED requests/min per L1 address**, shared REST+tx. Order txs weigh 6.
  Premium tier = 24k/min but pays fees (defeats the point).
- **Design response (implemented):**
  - Market data is **websocket-first** — `venues/lighter_client.py::_BookCache`
    holds one ws per host, auto-reconnect + resubscribe, book merge mirrors the
    SDK (price-keyed upsert, size-0 removal). ws limits are generous (200
    conns/IP, 500 subs/conn).
  - All REST/tx goes through **`venues/governor.py::TxBudgetGovernor`** — a
    weighted token bucket, per-process share of the 60/min (`LIGHTER_BUDGET_SHARE`,
    default 0.35), hard exponential backoff on 429/405 so one bot's cascade can't
    starve the account family.

## Market map — fleet universe diff
Fleet symbols are HL-style; `venues/symbol_map.py` translates. Verified remaps:

| HL symbol | Lighter symbol | size mult (fleet→Lighter) |
|-----------|----------------|---------------------------|
| kBONK | 1000BONK | 1.0 (both count thousands) |
| kSHIB | 1000SHIB | 1.0 |
| kPEPE | 1000PEPE | 1.0 |
| PEPE (raw) | 1000PEPE | 0.001 |

**Not listed on Lighter** (dropped per-bot, logged once, kept trading elsewhere):
`INJ, ATOM, ORDI, TON` (from the perps pilots' 33-coin universe), plus `BLUR`
(Yield-Harvester interest). The regime-switch wave-2 universe (BTC/ETH/SOL/BNB/
XRP/LINK/AVAX/DOGE/LTC/ADA/HYPE/ZEC) is **100% listed**.

## Per-market specs (pilot + key coins)
`min_quote` is the $ floor per order (all $10). `size_decimals` / `price_decimals`
drive the integer scaling in `LighterClient._scaled`.

| Coin | market_id | price_dec | size_dec | min_base | min_quote | taker | maker |
|------|-----------|-----------|----------|----------|-----------|-------|-------|
| ETH | 0 | 2 | 4 | 0.005 | $10 | 0 | 0 |
| BTC | 1 | 1 | 5 | 0.0002 | $10 | 0 | 0 |
| SOL | 2 | 3 | 3 | 0.05 | $10 | 0 | 0 |
| DOGE | 3 | 6 | 0 | 10 | $10 | 0 | 0 |
| 1000PEPE | 4 | 6 | 0 | 500 | $10 | 0 | 0 |
| LINK | 8 | 5 | 1 | 1.0 | $10 | 0 | 0 |
| AVAX | 9 | 4 | 2 | 0.5 | $10 | 0 | 0 |
| TAO | 13 | 3 | 3 | 0.05 | $10 | 0 | 0 |
| 1000SHIB | 17 | 6 | 0 | 500 | $10 | 0 | 0 |
| 1000BONK | 18 | 6 | 0 | 500 | $10 | 0 | 0 |
| HYPE | 24 | 4 | 2 | 0.5 | $10 | 0 | 0 |
| ADA | 39 | 5 | 1 | 10.0 | $10 | 0 | 0 |
| ZEC | 90 | 3 | 3 | 0.1 | $10 | 0 | 0 |

(Full 215-market dump: re-run `python3 scripts/lighter_day1.py`.)

## API / SDK surface (lighter-sdk 1.1.1, verified)
- Account index: `AccountApi.accounts_by_l1_address(l1_address)` → account_index.
  API key indices **4–254** usable (**0–3 reserved** for Lighter's own desktop/
  mobile UI per docs.lighter.xyz; 255 = query-all). Tradeable keys are registered
  by the wallet (Ledger-signed in the app), or via SDK `change_api_key` which
  needs the raw L1 key — so a Ledger account uses the app, not a script.
- Candles: `CandlestickApi.candles(market_id, resolution, start_ts, end_ts,
  count_back)` → `.c` list of `{t,o,h,l,c,v,V,i}` (t in ms). `resolution` uses
  HL-style strings (`1h`, `4h`, `1d`). **Data-layer parity with HL confirmed
  byte-identical** on BTC/ETH/SOL candle pulls.
- Signer: `SignerClient(url, account_index, api_private_keys={idx: key})`,
  `check_client()` is **sync**; `create_market_order(...)` etc. are async.
- WS: `wss://<host>/stream` — connect 582 ms, snapshot 789 ms, first book
  update 820 ms (measured mainnet). Well inside the 5-min candle loops.

## Season 3 points
Unconfirmed. Ignored for the build (organic-only policy stands). Verify in the
Lighter app rewards tab day-1 of funding.

## What is NOT yet verified (needs the user's testnet keys)
`scripts/lighter_testnet_smoke.py` runs the read-only layer today; the
authenticated layer (place/modify/cancel, market open+reduce-only close, nonce
recovery on 2 markets) is **SKIPPED until `LIGHTER_API_PRIVATE_KEY` /
`LIGHTER_ACCOUNT_INDEX` are set in env** — no keys ever live in the repo.

## Yield Harvester (funding-carry) — shadow execution (2026-07-10)
`funding_carry_bot.py` gained a venue-aware perp-leg execution path,
`_perp_leg_fill(...)`:
- **hl_paper** (default): models the leg with the flat `PERP_FEE` constant —
  zero behaviour change from the pre-Lighter paper bot.
- **lighter_shadow**: MEASURES the real crossed-spread cost by walking the live
  Lighter book (referenced to the book **mid**, adverse-slippage-only /
  conservative) and writes one `venue_orders` evidence row per fill
  (`shadow=true`). Lighter is zero-fee, so this slippage IS the entire perp cost.
- **lighter_testnet / lighter_live** (and any unknown VENUE): **REFUSED at boot**
  via a fail-safe allowlist. Funding-carry is delta-neutral (perp leg + hedge
  leg); a perp-only venue has no automated hedge, so a funded run would place a
  *naked* perp and mis-account its price P&L as neutral. A live harvest needs a
  hedge venue (CEX spot, or a correlated Lighter perp) built + backtested first.

**First live-book slippage read (round-trip @ $300, mid-referenced):** liquid hot
coins are cheap — ZEC 3.0 bps, COIN 4.4 bps, BB 6.9 bps, NBIS 7.0 bps — validating
the backtest's optimistic ~3 bps both-perp assumption. Thin/exotic perps are
traps — HYUNDAIUSD 29 bps, RAIL 23 bps, **WEN 870 bps**. ~120 coins were ≥40% APR
at once (many tokenized-equity perps with 5000%+ funding). **Implication:** a live
Yield Harvester needs a **liquidity / max-slippage gate** on top of the funding
filter (`MIN_DAY_VOLUME=$2M` is not enough). The shadow `venue_orders` ledger is
the evidence to calibrate that gate — accumulate before adding the filter.
