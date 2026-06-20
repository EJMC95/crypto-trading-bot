# Multi-Exchange Listing Sniper (DRY-RUN)

A standalone paper-trader that watches the **top ~100 exchanges** (via CCXT) for
**brand-new coin listings** and simulates buying them, to find out whether a
"buy the new listing" strategy would make or lose money. It is **100% dry-run**:
public endpoints only, no API keys, no real orders. You cannot lose money running
it.

Exchanges are polled **concurrently** and on a **best-effort** basis — any
exchange that is unreachable, geo-blocked, or rate-limited is logged and skipped
for that cycle rather than crashing the run. Requires `ccxt` (already in
`requirements.txt`).

> **Geo note:** several top-volume exchanges (Binance, Bybit, OKX, MEXC, HTX)
> block US IPs on their main domains. Run from a non-US region for full coverage,
> or pass a custom `--exchanges` list of ones reachable from your location. Blocked
> exchanges simply get skipped — they won't break the run.

## Why this isn't a Freqtrade strategy

Freqtrade trades a whitelist of pairs using indicators on **historical candles**.
A new listing has *no history* — the interesting moment is the first few minutes
of a pair that has never traded before. There's nothing for a backtester to
replay, and Freqtrade's own listing filters don't run in backtest mode. So the
only honest way to test this idea is to watch **live future listings** and paper-
trade them as they happen. That's what this script does.

## Quick start (on your Mac)

```bash
cd "~/Claude/Projects/Crypto Trading Bot"

# 1. Snapshot everything currently listed across all selected exchanges (run
#    once). Without this it would "detect" every existing pair as new and fire
#    thousands of paper trades.
python3 listing_sniper.py --seed

# 2. Leave the monitor running. New listings are rare per-exchange, but across
#    ~100 exchanges they show up more often. This is a long-running watch.
python3 listing_sniper.py
```

Stop anytime with Ctrl-C — state is saved each cycle, so you can restart and it
picks up where it left off.

## What it does each cycle

1. Pulls the full spot-pair list from each selected exchange **in parallel**
   (via CCXT `load_markets`), skipping any exchange that errors this cycle.
2. Flags any pair not in that exchange's baseline as a **new listing**.
3. Waits until the exchange marks it tradable (`active`), then records a
   **paper buy** at the current ask (+ simulated slippage).
4. Tracks the price and closes the paper trade on:
   - **take-profit: sells automatically at 5x entry** (default `--tp-mult 5`)
   - **stop-loss** (default −50%; set `--sl 0` to ride all the way to 5x or zero)
   - **max-hold** timeout (default **off** — no time limit, so a 5x can run)
5. Logs every closed trade (with its source exchange) to
   `sniper_data/sniper_trades.csv`.

## Tuning

```bash
python3 listing_sniper.py \
  --exchanges top100 \ # topN, "all", or a comma list of CCXT ids
  --workers 12 \       # exchanges polled in parallel
  --interval 60 \      # seconds between polls
  --quote USD,USDT,USDC,EUR \  # quote currencies to snipe
  --tp-mult 5 \        # SELL AT 5x entry (default)
  --sl 0.50 \          # -50% stop-loss; use 0 to disable
  --max-hold 0 \       # 0 = no time limit (let a 5x run); set minutes to cap
  --stake 100 \        # paper money per trade
  --slippage-bps 30    # assume you pay 0.30% above ask
```

Narrow to specific exchanges with e.g. `--exchanges binance,coinbase,kraken`.
`--any-status` opens the paper trade the instant a pair appears, before the
exchange flips it to active — more aggressive, less realistic. Leave it off to
start.

### About the 5x target — read this

Selling at 5x is still a **lottery-ticket / venture strategy**, not a steady one.
The overwhelming majority of new listings never 5x; many fade or go to near-
zero. The whole bet is that one rare 5x pays for many losers. That only works
if you *let losers run* somewhat (hence the wide −50% default stop and no time
limit) **and** if 5x's actually happen often enough — which is exactly the
unknown this paper-trader exists to measure. Concretely: at a −50% stop and a
100-unit stake, one 5x (+400) covers ~8 full losers (−50 each). If fewer than
~1 in 8 of your detected listings 5x, this loses money. A 5x target should hit
more often than the old 10x, banking gains sooner. Watch the CSV before
believing in it. Want fewer-but-bigger or more-but-smaller exits? Raise
`--tp-mult` (e.g. 10 = sell at 10x) for rarer/bigger wins, or lower it (e.g. 3 =
sell at 3x) to bank gains more often.

## Reading your results

`sniper_data/sniper_trades.csv` columns:

| column | meaning |
|---|---|
| `pnl_pct` / `pnl_quote` | profit/loss of that paper trade |
| `reason` | how it closed: `take_profit`, `stop_loss`, `max_hold` |
| `peak_pct` | best unrealised gain reached (tune your TP against this) |
| `hold_minutes` | how long it was held |

After a handful of real listings have gone by, sum `pnl_quote` to see if the
edge is positive. If `peak_pct` is routinely far above your `tp`, you're exiting
too early; if most trades hit `stop_loss`, the idea likely has no edge.

## Honest limitations — read before trusting this

- **Latency.** This polls public REST endpoints every ~60s. Real listing
  snipers use websockets, pre-listing announcement scraping, and co-located
  servers, and still get front-run. By the time REST shows the pair, the first
  move may be over. Treat the paper fills as **optimistic**.
- **Slippage & liquidity.** A brand-new pair has a thin book. Real fills on a
  market buy can be far worse than the ask shown. The `--slippage-bps` knob is a
  crude stand-in, not reality.
- **The edge is unproven.** "New listings pump" is folklore. Many fade
  immediately. Let the CSV tell you, over many listings, not a hunch.
- **Dry-run results ≠ live results.** Paper trading can't model the order book
  pressure your own (and others') buying creates. A positive paper record is
  necessary but *not sufficient* before risking real money.

## Files

```
listing_sniper.py            the script
README_sniper.md             this file
sniper_data/
  known_pairs.json           baseline + every pair seen
  open_positions.json        live paper trades (survives restarts)
  pending.json               detected-but-not-yet-online pairs
  sniper_trades.csv          your closed-trade results
```
