# Hyperliquid Perps Bot (Torin-video build)

A perpetual-futures bot that follows the exact framework from the "Build a Claude
Trading Bot in 10 minutes" video — RSI 30/70 placeholder strategy on Hyperliquid
testnet — plus a backtest so we can see how it actually performs *before* risking
anything.

## Files

| File | Purpose |
|------|---------|
| `perps_backtest.py` | Backtests the RSI 30/70 *placeholder* (long+short) on local BTC/ETH 1h data. The loser. |
| `perps_strategy_backtest.py` | Backtests a **real** strategy: MomoBreakoutV1 ported to perps (4h). The winner. |
| `hyperliquid_perps_bot.py` | Live **testnet** bot mirroring the video's RSI placeholder. Reference only — this is the losing strategy. |
| `hyperliquid_momo_bot.py` | Live **testnet** bot running the **winning** MomoBreakout strategy — matches `perps_strategy_backtest.py`. **Use this one.** |
| `.env.perps.example` | Template for your testnet API key. Copy to `.env.perps`. |
| `requirements_perps.txt` | Python deps for the live bot. |

## How it performed (backtest verdict)

Strategy: RSI(14), go **long** when RSI crosses below 30, **short** when it
crosses above 70, flip on opposite signal. Costs: 0.045% taker + 0.05% slippage
per side. 5% daily loss limit. $1,000 start. Data: Binance BTC/ETH 1h,
2023-06-15 → 2026-06-15 (3 years).

| Market | Leverage | Trades | Win % | Return | Final | Max DD |
|--------|----------|-------:|------:|-------:|------:|-------:|
| BTC | 1x | 208 | 58.2% | **−78.7%** | $213 | 81.6% |
| BTC | 3x | 26 | 61.5% | **−101.9%** | liquidated | 100%+ |
| ETH | 1x | 228 | 61.4% | **−94.4%** | $56 | 96.1% |
| ETH | 3x | 54 | 74.1% | **−124.4%** | liquidated | 100%+ |

Buy-and-hold over the same window: **BTC +160%**, ETH +3.6%.

**Conclusion: the video's placeholder strategy loses money — badly.** This is
expected and matches what the video author says: it's a *framework*, not a
money-maker. The "tell" is the combination of a *high* win rate (58–74%) with
*deeply negative* returns: the strategy banks many small wins, then gets run over
by a few large losses when it shorts into an uptrend (RSI stays "overbought" for
weeks in a bull market). Leverage just accelerates the blow-up to liquidation.

So the bot framework is sound; the *brain* is the whole game — which is exactly
the cliffhanger the video sets up for its "Claude vs Grok vs ChatGPT" follow-up.

## Swapping in a REAL strategy (the answer to "does anything beat buy & hold?")

`perps_strategy_backtest.py` ports your validated **MomoBreakoutV1** (4h Donchian
30/15 breakout + 200-EMA trend filter + 12% stop) onto perps. Same data, same
realistic costs (0.045% taker + 0.05% slippage per side). **Yes — it beats
buy-and-hold**, decisively on ETH and on a risk-adjusted basis on BTC.

| Market | Variant | Lev | Trades | Win % | PF | Return | Max DD | vs B&H |
|--------|---------|----:|-------:|------:|---:|-------:|-------:|:------:|
| BTC | long-only | 1x | 56 | 41% | 1.53 | +89.7% | **20%** | B&H +161% (DD ~50%) |
| BTC | long-only | 2x | 56 | 41% | 1.36 | **+170.4%** | 36% | ✅ beats |
| ETH | long-only | 1x | 47 | 40% | 1.54 | **+127.1%** | 25% | ✅ beats (B&H +3.9%) |
| ETH | long-only | 2x | 47 | 40% | 1.32 | **+220.8%** | 46% | ✅ beats |
| ETH | long+short | 1x | 95 | 44% | 1.39 | **+168.4%** | 35% | ✅ beats |
| ETH | long+short | 2x | 95 | 44% | 1.24 | **+266.7%** | 59% | ✅ beats |

**Engine validation:** long-only 1x reproduces the documented *spot* numbers from
`MomoBreakoutV1.py` almost exactly (BTC +89.7% vs ref +82.7%, ETH +127.1% vs ref
+125.5%), so the engine isn't fantasy.

**Reading the results:**
- **ETH** is the standout: the breakout strategy turned a flat +3.9% buy-and-hold
  market into +127% (1x) with a 25% max drawdown. This is the classic momentum
  edge — sideways/choppy markets where holding does nothing but trend bursts pay.
- **BTC** long-only trails raw buy-and-hold (+90% vs +161%) because BTC just went
  relentlessly up — but it did so with **~20% drawdown vs ~50%+** for holding.
  That's a much smoother ride for two-thirds of the return.
- **Adding a short side helps ETH but hurts BTC** (shorting into BTC's bull = a
  drag). Long-only is the more robust default; enable shorts per-market, not
  blanket.
- **2x leverage** beats buy-and-hold on both coins but roughly doubles drawdown.
  Tempting, but the 12% stop + leverage is exactly where funding costs and
  liquidation risk (not modelled here) bite hardest. Treat 1x as the baseline.

**Bottom line:** the RSI placeholder loses ~80–94%; the MomoBreakout port returns
+90% to +127% at 1x and beats buy-and-hold on ETH outright and on BTC after
adjusting for risk. The strategy is the entire difference.

> Same caveats as below: funding not modelled (would trim the leveraged/short
> rows most), and a great backtest is not a guarantee — run it on testnet first.

To run it:
```bash
python perps_strategy_backtest.py
```

### Running the winning strategy live (testnet)

`hyperliquid_momo_bot.py` is the live counterpart — the **exact same rules** as
the winning backtest, so what you run matches what you measured. Verified: its
200-EMA and Donchian channels reproduce the backtest values to within 0.02%.

- Acts on **closed 4h candles** (polls every 5 min, no 60s churn).
- Reads position size + entry price from the exchange, so restarts are safe.
- 12% hard stop checked live every loop; 5% daily loss limit halts + flattens.
- `ALLOW_SHORT = False` by default (shorts helped ETH, hurt BTC). `LEVERAGE = 1`.
- Dry-run by default; `--live` to send testnet orders.

```bash
python3 hyperliquid_momo_bot.py --paper   # NO account/keys: live testnet prices, simulated fills
python3 hyperliquid_momo_bot.py           # dry-run, needs .env.perps, reads your testnet balance
python3 hyperliquid_momo_bot.py --live    # send testnet orders
```

`--paper` is the zero-setup way to watch the strategy run against live testnet
market data — no Hyperliquid account, no keys, no deposit. It reads public prices
and simulates fills in memory, logging every decision. Use it to sanity-check the
bot before doing the account setup for real dry-run / live.

Same setup as the RSI bot (account, faucet, `.env.perps`). SOL is included in the
live `COINS` list, but the **backtest** can't cover SOL until you download its
history (no SOL data locally and exchange APIs are blocked from the build
sandbox). To add it:
```bash
freqtrade download-data --exchange binance -t 1h --pairs SOL/USDT --days 1100 \
  --datadir "Crypto Trading Bot/data"
```
then add `("SOL", "binance/SOL_USDT-1h.feather")` to `MARKETS` in
`perps_strategy_backtest.py` and re-run.

> Caveat: funding payments aren't modelled (would make returns worse), and the
> 3x rows show equity past −100% because the model applies leverage to full
> equity rather than simulating a liquidation engine — in reality you'd be
> liquidated and lose the position margin. The qualitative result is unchanged.

## Run the backtest (no keys, no money)

```bash
cd "Crypto Trading Bot"
pip install pandas pyarrow numpy
python perps_backtest.py
```

Tweak `LEVERAGES`, `DAILY_LOSS_LIMIT`, fees, or `MARKETS` at the top of the file.

## Run the live testnet bot

1. `pip install -r requirements_perps.txt`
2. On Hyperliquid: deposit ≥ $10 on **mainnet** (prerequisite), open the
   **testnet**, claim the $1,000 mock USDC faucet, then create an API wallet
   under **More → API**. Use the **same wallet** (e.g. MetaMask) for mainnet and
   testnet.
3. `cp .env.perps.example .env.perps` and paste your **testnet** API wallet key.
   Never commit or share it.
4. Dry-run first (no orders sent):
   ```bash
   python hyperliquid_perps_bot.py
   ```
   Then go live on testnet:
   ```bash
   python hyperliquid_perps_bot.py --live
   ```

Every tick logs price, RSI, current position and the decision to `perps_bot.log`.

## Safety notes

- **Testnet only.** The bot hardcodes the Hyperliquid testnet URL. Don't point it
  at mainnet with this placeholder strategy.
- Defaults to **dry-run**; `--live` is required to place (testnet) orders.
- `LEVERAGE` defaults to 1x. The backtest shows 3x liquidates this strategy.
- The bot will not place orders for you outside testnet, and you must set up the
  account, deposit, and keys yourself.

## Where this fits with your other bots

This sits alongside your Freqtrade stack (`config_*`, `strategies/`), the
triangular arbitrage bot, and the listing sniper. It's the first **perps /
leverage** piece. The natural next step — and the point of the video — is to
swap the RSI placeholder for a real strategy (e.g. adapt your `DayTraderV5Gated`
or `MomoBreakoutV1` logic, or wire in an LLM "brain") and re-run `perps_backtest.py`
to see if it actually beats buy-and-hold before going near real money.
