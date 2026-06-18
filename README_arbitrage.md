# Triangular Arbitrage Bot (Kraken) — Depth-Aware Detection + Paper Trading

A safe first arbitrage build: it scans Kraken's **full liquid spot universe**
for 3-leg loops (e.g. USD → BTC → ETH → USD) where the round trip would return
more than you started — **after fees and real order-book slippage at your trade
size**. It places **no real orders** and needs **no API keys**. It only reads
public market data and simulates fills.

## Run it

```bash
pip install ccxt
python triangular_arb.py            # live detection + paper trading
python triangular_arb.py --selftest # offline math check (no network)
```

Run it on your Mac (the sandbox here has no internet to Kraken). Leave it
running; it scans every ~8s and logs to `arb_opportunities.csv`.

## What you'll see

Each scan prints how many cycles passed the prefilter, how many order books it
pulled, and the best **depth-confirmed** loop. Any loop that is
break-even-or-better after fees AND slippage — and that actually fills at your
trade size — is booked to a running virtual balance and tagged `PAPER-FILL`.

## How it works (two-stage, depth-aware)

Pulling an order book for every pair every scan would be thousands of API calls
and minutes per loop (Kraken rate-limits public calls). So the engine splits the
work:

1. **Build the net.** Loads every active Kraken spot pair (filtered to the
   liquid `UNIVERSE_HINT` set, or *all* pairs if you set it to `None`), builds a
   currency graph, and enumerates every triangular loop that starts and ends in
   a currency you hold (`BASE_CURRENCIES`, now incl. BTC/ETH).
2. **Stage 1 — cheap ranking.** One `fetch_tickers` call prices every loop on
   best bid/ask after fees and ranks them.
3. **Stage 2 — depth confirmation.** For the top candidates only (those above
   `PREFILTER_EDGE`), it pulls deduped real order books — capped at
   `MAX_BOOK_FETCHES` per scan for rate-limit safety — and re-prices each loop
   by **walking the book** for `PAPER_TRADE_SIZE`. The reported/logged edge is
   the slippage-included number you'd actually have filled at.
4. **Paper-fill.** Loops that clear break-even depth-aware *and* fill completely
   are booked to the virtual balance.

This is the key upgrade over a naive scanner: a loop can look great on the best
quote and be a **mirage** once you try to move real size through a thin book.
The self-test demonstrates exactly this — a +3.7% top-of-book loop collapses to
unfilled/negative on a thin book while surviving on a deep one.

## The honest part

Kraken's base **taker fee is 0.40% per leg**. Three legs ≈ **1.2% round-trip**,
and arbitrage fills must be taker orders. So a loop has to beat 1.2% in fees
**plus** the bid/ask spread on all three legs **plus** slippage before it nets
anything. On the live snapshot used to test this, the best real loop was
**−1.2%**. Profitable moments exist but are rare and disappear in milliseconds —
faster bots usually take them first.

**Treat this as a measuring instrument, not a money printer.** Let it log for a
few days. If it never books a positive paper trade, that's a real answer: the
edge isn't there at retail fees and latency, and you've learned it for $0.

## Config (top of `triangular_arb.py`)

| Setting | Default | Meaning |
|---|---|---|
| `BASE_CURRENCIES` | USD, USDT, USDC, EUR, BTC, ETH | Currencies you settle a loop into |
| `TAKER_FEE` | 0.0040 | Per-leg taker fee (lower only if your volume tier is lower) |
| `UNIVERSE_HINT` | ~23 liquid coins | Currency set to scan; set `None` for the widest net (all pairs) |
| `PREFILTER_EDGE` | −0.010 | Stage-1 gate: only depth-check loops at/above this top-of-book edge |
| `MAX_BOOK_FETCHES` | 24 | Cap on order books pulled per scan (rate-limit guard) |
| `MIN_NET_EDGE` | −0.006 | Log depth-confirmed loops down to this edge |
| `PAPER_TRADE_SIZE` | 1000.0 | Trade notional; slippage is computed for THIS size |
| `BOOK_LEVELS` | 100 | Order-book depth pulled per pair |
| `POLL_SECONDS` | 8.0 | Seconds between scans |

**Tuning the net vs. rate limits:** widening `UNIVERSE_HINT` (or setting it to
`None`) finds more loops but raises how many clear the prefilter, so raise
`PREFILTER_EDGE` toward 0 or lower `MAX_BOOK_FETCHES` if scans get slow. The
CSV's `top_of_book_net_pct` vs `depth_net_pct` columns show you how much
slippage is eating — if depth is always far below top-of-book, your size is too
big for the book.

## Before you ever go live (don't yet)

Detection → paper-trade for days → only then consider real orders, with: real
API keys in a `.env` (never in code), tiny size, a hard kill-switch and
max-drawdown halt, and atomic/near-simultaneous leg execution (the hardest part
— a half-filled loop is an open directional position, not arbitrage).
