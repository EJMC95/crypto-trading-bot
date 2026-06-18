# Crypto Trading Bot — Complete Getting Started Checklist (Mac)

Everything you need, in order. Work top to bottom. Don't skip the dry-run phase.

---

## The big picture (read this first)

You are building a bot that:
1. Connects to a crypto exchange via API keys.
2. Runs a strategy (rules for when to buy/sell).
3. Trades **fake money first** (dry-run) until you trust it, then optionally real money.

The install is the easy part. Whether it makes money is unproven until you've tested for weeks. Most strategies lose. Treat this as "build a safe lab to test ideas," not "turn on a money machine."

---

## PART 1 — Accounts you need to create

### 1a. An exchange account
You're in **Australia**, so you have more options than a US user (the US blocks Binance's main platform — you don't have that restriction). All three below are Freqtrade-supported and available to Australian residents:

| Exchange | Why | Notes |
|----------|-----|-------|
| **Kraken** (recommended to start) | Well-supported by Freqtrade, clean API, strong security reputation, AUD deposits via PayID/bank | Simple and reliable for a beginner |
| **Binance** | Largest, deepest liquidity, lowest fees, excellent Freqtrade support | Available in Australia; most liquid pairs are vs **USDT**, not AUD |
| **Coinbase** (Advanced Trade) | Easy signup | Use "Advanced Trade", not the simple buy/sell screen |

> Recommendation: start on **Kraken** for simplicity. If you later want the deepest liquidity and lowest fees, **Binance** is the power-user choice and is fully usable from Australia.

**Action:** Sign up (e.g. https://www.kraken.com), complete identity verification (required to trade), and enable **two-factor authentication (2FA)** immediately. Australian exchanges must verify your ID to comply with AUSTRAC regulations.

You do NOT need to deposit money yet. Dry-run trading uses fake money and live exchange prices.

### 1b. That's the only account required to start
Telegram (for phone notifications) and a few others are optional add-ons for later.

---

## PART 2 — Programs to install on your Mac

You only need **two** things. Docker handles Python and every other dependency for you, so you don't install Python manually.

### 2a. Docker Desktop (required)
This runs the bot in a self-contained container.

1. Download from https://www.docker.com/products/docker-desktop/ — pick **Apple Silicon** or **Intel** to match your Mac (Apple menu  > About This Mac tells you which).
2. Open the `.dmg`, drag Docker to Applications, launch it.
3. Wait for the whale icon in the menu bar to stop animating.

Verify in Terminal (Applications > Utilities > Terminal, or Cmd+Space and type "Terminal"):
```bash
docker --version
```

### 2b. Terminal (already on your Mac)
Built in. That's where you'll type commands.

### 2c. (Optional) A code/text editor
To view and edit your strategy and config files comfortably, **VS Code** (free) is the standard: https://code.visualstudio.com — but TextEdit works in a pinch.

That's it. No manual Python, no pip, no compilers — Docker contains all of it.

---

## PART 3 — Install Freqtrade

In Terminal, run these one at a time:

```bash
# 1. Make a project folder and enter it
mkdir -p ~/freqtrade && cd ~/freqtrade

# 2. Download Freqtrade's Docker recipe
curl https://raw.githubusercontent.com/freqtrade/freqtrade/stable/docker-compose.yml -o docker-compose.yml

# 3. Download the bot (takes a few minutes the first time)
docker compose pull

# 4. Create your data folder
docker compose run --rm freqtrade create-userdir --userdir user_data

# 5. Create your config (answers an interactive questionnaire)
docker compose run --rm freqtrade new-config --config user_data/config.json
```

**Config questionnaire — safe starter answers:**
- Max open trades: `3`
- Stake currency: `USDT` (most liquid pairs on both Kraken and Binance)
- Stake amount: `100` (per-trade size — fake money in dry-run)
- Fiat display: `AUD`
- Exchange: `kraken` (or `binance`)
- Telegram: `No` (for now)
- REST API: `No` (for now)

The config defaults to `"dry_run": true`. **Leave it true.** That's paper trading.

---

## PART 4 — Get data and test a strategy

```bash
# Download 180 days of price history (use the same exchange you chose above)
docker compose run --rm freqtrade download-data --exchange kraken --pairs BTC/USDT ETH/USDT --timeframes 5m 1h --days 180

# Create a starter strategy file
docker compose run --rm freqtrade new-strategy --strategy MyFirstStrategy --template advanced

# Backtest it on the data you downloaded
docker compose run --rm freqtrade backtesting --strategy MyFirstStrategy --timeframe 5m --timerange 20251201-
```

The backtest prints a results table — trades, win rate, profit/loss. **This is the moment of truth.** If it loses money on history, it'll almost certainly lose live. Iterate on the strategy here, where it's free.

---

## PART 5 — Run it in dry-run (paper trading)

```bash
# Start the bot in the background, trading fake money in real time
docker compose up -d

# Watch what it's doing (Ctrl+C stops watching, bot keeps running)
docker compose logs -f

# Stop the bot completely
docker compose down
```

Let this run for **several weeks**. Compare its paper results to the real market.

---

## PART 6 — Only after weeks of successful dry-run: going live

Do NOT do this until Part 5 has proven itself. When/if you do:

1. **Deposit a small amount** you can afford to lose entirely.
2. In your exchange account, create **API keys** with **trade permission only** — never enable withdrawals.
3. Put those keys in `user_data/config.json`.
4. Change `"dry_run": true` to `"dry_run": false`.
5. Start with the smallest stake amount possible and keep stop-losses on.

---

## Order-of-operations summary

```
Create Kraken (or Binance) account + 2FA
        ↓
Install Docker Desktop
        ↓
Install Freqtrade (docker compose pull)
        ↓
Create config (dry_run = true)
        ↓
Download data → Backtest strategies  ← iterate here, it's free
        ↓
Dry-run for several weeks            ← real-time, fake money
        ↓
(Optional) Go live, tiny amount, trade-only API keys
```

---

## Honest reality check

- A profitable backtest is **not** proof. Overfitting to past data is the #1 way bots fool their owners.
- Fees and slippage quietly eat returns — your backtest must account for them (Freqtrade does by default if configured).
- Never give a bot API keys with withdrawal permission.
- Money you put in, you can lose — all of it, including via bugs.
- This is not financial advice.

---

## Help

- Freqtrade Docker quickstart: https://www.freqtrade.io/en/stable/docker_quickstart/
- Configuration guide: https://www.freqtrade.io/en/stable/configuration/
- Strategy basics: https://www.freqtrade.io/en/stable/strategy-101/
- Kraken: https://www.kraken.com

If a command errors, copy what Terminal shows and I'll help you fix it.
