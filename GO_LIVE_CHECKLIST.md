# Go-Live Checklist — prepared 22 June 2026

Everything below the line marked **🔴 USER-ONLY** moves real money or handles
secrets and must be done by you, by hand. I (the assistant) will not flip
`dry_run`, add API keys, or move funds.

---

## ✅ Done (code/config ready, validated, deployed — all still DRY-RUN)

| Bot | Strategy | Universe | Validation (basket, by regime) | Live-candidate? |
|-----|----------|----------|--------------------------------|-----------------|
| v4core | ImprovedStrategyV4 (1d trend) | StaticPairList — 6 majors | +33% full / chop DD 4.6% / PF 7.26 | ✅ yes |
| v6swing | SwingDipV1 (dip-buyer) | StaticPairList — 15 basket | +3.1% full, PF 1.73, 0.7% DD, +ve every regime | ✅ yes (lowest risk — start here) |
| v7momo | MomoBreakoutV1 (original breakout) | StaticPairList — 15 basket | +20% full, +10% bull (loses chop/crash) | ✅ yes (trend-only) |
| v5gated | DayTraderV5Gated (5m, crash-safe) | (unchanged) | −38% full, 9% win — **confirmed loser** | ❌ keep paper only |
| perps-bot | RSI mean-reversion | — | −90%+, 0/15 coins — **confirmed loser** | ❌ keep paper only |
| triangular-arb | single-exchange | — | can't clear ~1.2% fee — **structurally dead** | ❌ keep paper only |

- All configs switched from `VolumePairList(100)` (which ignored the whitelist and
  silently traded ~100 untested coins) to `StaticPairList` over the validated set.
- Pushed to GitHub `main` → Railway redeployed all repo-connected services (verified
  RUNNING on the new commit).
- Repo `user_data/strategies` now matches the validated local code (single truth).

---

## 🔴 USER-ONLY — required before flipping to real money

Do these per freqtrade service (v4core / v6swing / v7momo). Recommended order:
**start with v6swing only**, small size, watch for a week, then add the others.

### 1. Capital & position sizing (decide deliberately)
- Set how much real capital each bot gets. Today each is a $1000 paper wallet.
- Review per config: `tradable_balance_ratio`, `stake_amount` (currently
  `"unlimited"`), `max_open_trades`. Start conservative.

### 2. Exchange API keys — via env, NEVER commit
- Create **trade-only** Kraken API keys (NO withdrawal permission).
- Inject on Railway as service variables (freqtrade reads `FREQTRADE__` overrides):
  - `FREQTRADE__EXCHANGE__KEY`, `FREQTRADE__EXCHANGE__SECRET`
- Leave the `"key"/"secret"` fields in the JSON empty. Never paste keys into a
  committed file.

### 3. Rotate / override the api-server secrets
The committed configs contain `jwt_secret_key`, `ws_token`, and a placeholder
`password` ("CHANGE_ME..."). They are internal-only today (no public domain — I
checked), so risk is low, but before live:
- Override via env: `FREQTRADE__API_SERVER__PASSWORD`,
  `FREQTRADE__API_SERVER__JWT_SECRET_KEY`, `FREQTRADE__API_SERVER__WS_TOKEN`.
- Do **not** attach a public domain to the freqtrade services (keep the API
  internal). The pnl-dashboard is the only thing that should be public.

### 4. Outage alerting (this bit you before — 4-day silent outage)
- Set a real Telegram bot token + chat id via env:
  `FREQTRADE__TELEGRAM__TOKEN`, `FREQTRADE__TELEGRAM__CHAT_ID`, and
  `FREQTRADE__TELEGRAM__ENABLED=true`. Then you get fill + outage alerts.

### 5. The actual switch
- Flip `dry_run: false` in the chosen service's config (or
  `FREQTRADE__DRY_RUN=false`). **This is the point of no return — real orders.**
- Redeploy. Confirm the first few fills look right before walking away.

### 6. Housekeeping
- Make `EJMC95/crypto-trading-bot` **private** (configs are tracked in git).
- Permanently resolve the `~/freqtrade` ↔ repo split so local and cloud can't
  drift again (see `live-bots-run-from-home-freqtrade` memory).

---

## Reality check
The validated edges are **modest and backtest-only**. V4-majors and V7 lean on
trending markets; V6 is low-return/low-risk. None is a money printer. Treat live
as a small-capital experiment, scale only after live results match the paper
behaviour, and keep V5 / perps / triangular-arb on paper — they are confirmed
losers, not unfinished ideas.
