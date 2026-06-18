# Deploying the bots to Railway

This repo deploys as **one GitHub repo → four Railway services** (one per bot).
All four share the same Docker image; each service just runs a different command.

> ⚠️ **Money & keys.** These bots default to **paper / testnet / dry-run**. They
> only trade real funds when you pass live flags AND provide real keys. Keys are
> never stored in the repo — you paste them into Railway's **Variables** tab,
> where they're encrypted. Double-check you're on testnet before going live.

---

## Step 1 — Put the code on GitHub

The repo is already initialised and committed locally. Create the remote and push:

```bash
cd "~/Claude/Projects/Crypto Trading Bot"

# Option A: GitHub CLI (easiest) — creates the repo and pushes in one go
gh repo create crypto-trading-bot --private --source=. --push

# Option B: no gh — create an empty PRIVATE repo at github.com/new first, then:
git remote add origin https://github.com/<your-username>/crypto-trading-bot.git
git branch -M main
git push -u origin main
```

Use a **private** repo. Even with `.gitignore` excluding secrets, keep it private.

---

## Step 2 — Create the services in Railway

In the Railway dashboard:

1. **New Project → Deploy from GitHub repo →** pick `crypto-trading-bot`.
   Railway builds the Dockerfile and creates the first service.
2. For each additional bot: **New → GitHub Repo →** same repo again.
   (Same repo can back multiple services.)

Rename the four services and set each one's **Start Command**
(Service → Settings → Deploy → Custom Start Command):

| Service name        | Start Command                              | Notes |
|---------------------|--------------------------------------------|-------|
| `perps-bot`         | `python hyperliquid_perps_bot.py`          | dry-run by default; add `--live` for testnet orders |
| `momo-bot`          | `python hyperliquid_momo_bot.py`           | dry-run by default |
| `triangular-arb`    | `python triangular_arb.py`                 | paper-trading detection engine |
| `listing-sniper`    | `python listing_sniper.py`                 | paper trading; tune flags e.g. `--interval 30` |

---

## Step 3 — Set environment variables (per service that needs them)

Service → **Variables** tab. Only the Hyperliquid bots need keys:

**`perps-bot`**
- `HL_API_PRIVATE_KEY` = your Hyperliquid **testnet** API-wallet private key
- `HL_ACCOUNT_ADDRESS` = your account address

**`momo-bot`**
- `HL_API_PRIVATE_KEY`
- `HL_ACCOUNT_ADDRESS`
- `ZAPIER_WEBHOOK_URL` = (optional) Zapier Catch Hook URL for trade alerts

`triangular-arb` and `listing-sniper` need no keys (they hit public Kraken data).

---

## Step 4 — Deploy & watch logs

Railway auto-deploys on every `git push`. Open each service's **Deployments →
Logs** to confirm the bot started and is looping. If a service crashes on boot,
the log will show the missing variable or dependency.

---

## Notes

- **No web port needed** — these are background workers, not web apps. Railway
  runs them fine without an exposed port.
- **Cost:** the Hobby plan ($5/mo) covers usage-based billing for all four small
  services. Idle bots that mostly sleep are cheap, but four always-on services
  will draw from your monthly credit — watch the usage meter the first week.
- **The dashboards / backtests / freqtrade strategies** in this folder are not
  deployed here; they're local tools. Only the four live bots run on Railway.
- **Going live:** change a service's Start Command to add `--live` only after
  you've confirmed testnet behaviour in the logs.
