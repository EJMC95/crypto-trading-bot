# Installing Freqtrade on your Mac (Docker method)

This is the official recommended path for Apple Silicon Macs (M1/M2/M3/M4) and works on Intel Macs too. Docker bundles Python and every dependency inside a container, so you don't install Python yourself or fight version conflicts.

Everything below runs in **Terminal** (open it from Applications > Utilities, or Spotlight: `Cmd+Space`, type "Terminal").

---

## Step 0 — Check your chip (optional, just curiosity)

Apple menu  > About This Mac. If it says "Apple M…" you're on Apple Silicon (Docker is required). If it says "Intel" you could install natively, but Docker is still the easier route.

---

## Step 1 — Install Docker Desktop

1. Go to https://www.docker.com/products/docker-desktop/
2. Download **Docker Desktop for Mac** — pick the **Apple Silicon** build or **Intel** build to match your chip.
3. Open the downloaded `.dmg`, drag Docker into Applications, then launch it.
4. Let it finish starting — you'll see a whale icon in your top menu bar. Wait until it stops animating ("Docker Desktop is running").

Verify it works. In Terminal:

```bash
docker --version
```

You should see a version number. If "command not found", make sure Docker Desktop is actually open.

---

## Step 2 — Create a project folder

```bash
mkdir -p ~/freqtrade
cd ~/freqtrade
```

This makes a folder called `freqtrade` in your home directory and moves into it. Everything lives here.

---

## Step 3 — Download Freqtrade's Docker setup

```bash
curl https://raw.githubusercontent.com/freqtrade/freqtrade/stable/docker-compose.yml -o docker-compose.yml
```

This grabs the official compose file (the recipe Docker uses to run the bot).

Now pull the Freqtrade image:

```bash
docker compose pull
```

This downloads the prebuilt bot. First time takes a few minutes.

---

## Step 4 — Create your config and user folder

```bash
docker compose run --rm freqtrade create-userdir --userdir user_data
```

Then create a config file interactively:

```bash
docker compose run --rm freqtrade new-config --config user_data/config.json
```

It will ask you a series of questions. Safe answers to start:

- **Max open trades:** 3 (or whatever you like)
- **Stake currency:** USDT
- **Stake amount:** 100 (this is per-trade size in dry-run — fake money, so it doesn't matter yet)
- **Fiat display currency:** USD
- **Exchange:** binance (or kraken / coinbase)
- **Telegram / API:** you can say No to both for now

**IMPORTANT:** The config defaults to `"dry_run": true`. Leave it that way. Dry-run = paper trading with fake money. Do NOT switch to live trading until you've tested for weeks.

---

## Step 5 — Download some historical price data

```bash
docker compose run --rm freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT --timeframes 5m 1h --days 180
```

This pulls 180 days of price history so you can backtest.

---

## Step 6 — Run a backtest with the sample strategy

Freqtrade ships with example strategies. To use one, download the strategy templates:

```bash
docker compose run --rm freqtrade list-strategies
```

If no strategies show, create the sample set:

```bash
docker compose run --rm freqtrade new-strategy --strategy MyFirstStrategy --template advanced
```

Then backtest it against your downloaded data:

```bash
docker compose run --rm freqtrade backtesting --strategy MyFirstStrategy --timeframe 5m --timerange 20251201-
```

You'll get a results table: number of trades, win rate, total profit/loss. **This is where you learn whether a strategy actually works before risking money.** Most don't.

---

## Step 7 — Run the bot in dry-run (paper trading)

```bash
docker compose up -d
```

The `-d` runs it in the background. It now trades with fake money in real time using your strategy.

Check on it:

```bash
docker compose logs -f
```

(Press `Ctrl+C` to stop watching the logs — the bot keeps running.)

Stop the bot entirely:

```bash
docker compose down
```

---

## Step 8 — Optional: the web dashboard (freqUI)

You can watch the bot in your browser. Edit `user_data/config.json` and set `api_server` -> `enabled` to `true`, pick a username/password, then run `docker compose up -d` again and visit http://127.0.0.1:8080

---

## Updating Freqtrade later

```bash
cd ~/freqtrade
docker compose pull
docker compose up -d
```

---

## Reality check before you ever go live

1. A green backtest is NOT proof. Strategies that look great on past data routinely lose in live markets (overfitting).
2. Run dry-run for **at least several weeks** and compare it to what actually happened in the market.
3. When/if you go live: use money you can afford to lose entirely, start with the smallest amount possible, and keep stop-losses on.
4. You'll need real exchange API keys (created in your exchange account settings) — and you should restrict those keys to "trade only", never "withdraw".

Nothing here is financial advice. Bots can and do lose money, including through bugs.

---

## If you get stuck

- "command not found: docker" -> Docker Desktop isn't running. Open it.
- "Cannot connect to the Docker daemon" -> same thing, wait for the whale icon to settle.
- Official docs: https://www.freqtrade.io/en/stable/docker_quickstart/
