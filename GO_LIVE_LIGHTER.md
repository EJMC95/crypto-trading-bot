# Go-Live on Lighter — sub-account-per-bot (prepared 2026-07-09)

This is the **compressed** go-live path for taking your top perps bots live on
Lighter.xyz, **each on its own sub-account**. The code is built and proven in
paper + shadow; everything below the 🔴 line moves real money or handles secrets
and is **yours to do by hand**. I (the assistant) will not create your account,
generate or paste API keys, deposit USDC, or disarm the kill switch — those are
exactly the steps that must stay with you.

Lighter account: **e.j.m.c@icloud.com** · app already installed on the Mac.

---

## Why sub-account-per-bot (your instinct is right)
On Lighter a master L1 account (your fresh Ledger) holds many **sub-accounts**,
each with its **own isolated collateral and positions**. One bot per sub-account
means a blow-up in one bot **cannot drain another's margin** — the cleanest
possible isolation, and each key is individually revocable. The code already
supports it: each bot's Railway service reads its own `LIGHTER_ACCOUNT_INDEX`
(the sub-account) + `LIGHTER_API_PRIVATE_KEY` (that sub-account's trade key).

## What the code already guarantees (paper/shadow-proven)
- `VENUE=lighter_live` **refuses to start** unless `REAL_MONEY_KILL` is set to
  the exact string `DISARMED_I_UNDERSTAND`. Default = **ARMED** = no live orders.
  Re-checked **every loop** — flipping it back to armed mid-run flattens + halts.
- Per-bot **notional caps** are read from env (no code default that could grow),
  and the live open-position cap is derived from `floor(cap / clip)`.
- **Max-daily-loss** flatten-and-halt (`LIGHTER_MAX_DAILY_LOSS`, $/day).
- Every live order is logged to the `venue_orders` Postgres ledger with the raw
  exchange response; live closes to `paper_trades` with `venue='lighter'`.
- The live bot publishes as `<bot>-lighter` — a **separate dashboard row** with a
  red **LIVE** badge and its own **🔴 LIVE · Lighter** total line, so paper and
  live never blend.

## Pilot caps — YOUR chosen sizing (2026-07-09): $50–100/bot, $15–25 clips
Small first pass. $15–25 clips still clear Lighter's $10/order minimum. Live set
= **🧭 Trail Blazer + 🪃 Bounce Catcher** (the two proven Lighter-capable top
perps). Edit freely — it's your money.

| Env var | Suggested | Meaning |
|---------|-----------|---------|
| `LIGHTER_ORDER_USD` | `20` | $ per position (clip; clears the $10 min) |
| `TRAIL_BLAZER_MAX_NOTIONAL` | `100` | 🧭 cap → ~5 slots ($50–100 range) |
| `BOUNCE_CATCHER_MAX_NOTIONAL` | `80` | 🪃 cap → ~4 slots |
| `LIGHTER_MAX_DAILY_LOSS` | `15` | fleet-wide $/day → flatten+halt |

> **The spot Launch Sniper is NOT in the live set** — it snipes brand-new *spot*
> listings across CCXT exchanges, and Lighter is a fixed-market perps DEX with no
> such events. Decision (2026-07-09): instead of forcing it, a **new Lighter-native
> perp sniper** (`lighter_perp_sniper.py`, 🎯 Perp Sniper) was built — it snipes
> freshly-*listed Lighter perp markets*. It is **UNVALIDATED** and runs
> **shadow-first** (`VENUE=lighter_shadow`, modelled fills, no real money) to
> gather evidence; it becomes a real-money candidate only after a shadow track
> record and a separate explicit go-live, on its **own sub-account**, like the
> others. Deploy shadow now via `railway.lightersniper.toml`; do NOT fund it yet.

---

# 🔴 USER-ONLY — required before any real order

### 0. Rotate the Postgres password FIRST
Before any real API key lands in Railway env, rotate `DATABASE_URL`'s password
(Railway Postgres → rotate) and update the reference on every service. (Your own
pre-live rule; a leaked shared DB creds is the one thing that spans all bots.)

### 1. Fresh Ledger account + Lighter account (in the app)
- Use a **fresh, dedicated Ledger account** for Lighter. The **L1 key never
  leaves the Ledger / the Mac** — it only creates sub-accounts and registers/
  revokes API keys. It goes on **no** cloud/Railway/repo, ever.
- Sign in to the Lighter app with **e.j.m.c@icloud.com** and connect that Ledger.

### 2. Create one sub-account per live bot (in the app)
- Create **N sub-accounts** (one per bot you're taking live). Note each
  sub-account's **index**.
- Verify from the Mac (read-only, no keys):
  `python3 scripts/lighter_accounts.py 0xYOUR_L1_ADDRESS`
  → lists every sub-account index + collateral + registered API-key indices.

### 3. Register one trade-only API key per sub-account (in the app — Ledger-signed)
- Tradeable keys are **created in the Lighter app / app.lighter.xyz/apikeys with
  your wallet connected** — the Ledger signs the registration. They are NOT made
  in a script for a Ledger account (the SDK's `change_api_key` needs a raw L1 key,
  which a Ledger won't give up — that's by design, and why the app is the path).
- For each sub-account, create an **API key at index 4–254** (0–3 are reserved for
  Lighter's own desktop/mobile UI — don't use them). The key's **private key is
  shown ONCE** — copy it straight into that bot's Railway `LIGHTER_API_PRIVATE_KEY`
  (step 5). Never into a file, a chat, or the repo.
- Lighter API keys can trade but can only secure-withdraw to the **originating L1
  address** — a leaked key can grief, not steal.
- Verify it registered (read-only, public address only):
  `python3 scripts/lighter_accounts.py 0xYOUR_L1_ADDRESS` → shows each
  sub-account's registered API-key indices.

### 4. Fund each sub-account with USDC
- On-ramp USDC (Arbitrum/Base) and deposit into **each** sub-account per your
  chosen caps. Keep it to the pilot amount — this is a live experiment, not a
  reallocation.

### 5. Set per-bot Railway env (one live service per bot)
Recommended: run each live bot as a **separate Railway service** so its paper
twin keeps running as the control (the dashboard shows both). Per live service:
```
VENUE=lighter_live
LIGHTER_ACCOUNT_INDEX=<that bot's sub-account index>
LIGHTER_API_KEY_INDEX=4                # 0-3 reserved for Lighter's UI; bots use 4+
LIGHTER_API_PRIVATE_KEY=<that sub-account's API key private key>   # secret
LIGHTER_ORDER_USD=30
<BOT>_MAX_NOTIONAL=<cap>              # e.g. TRAIL_BLAZER_MAX_NOTIONAL=200
LIGHTER_MAX_DAILY_LOSS=30
LIGHTER_BUDGET_SHARE=0.25             # split the 60/min budget across live bots
DATABASE_URL=<reference, post-rotation>
# REAL_MONEY_KILL is intentionally NOT set yet — the bot boots ARMED (no orders)
```
Start command stays the bot's own (e.g. `python hyperliquid_momo_bot.py`).

### 6. Testnet smoke FIRST (strongly recommended before mainnet money)
With a testnet key set (`LIGHTER_API_PRIVATE_KEY` etc. pointed at testnet):
`python3 scripts/lighter_testnet_smoke.py`
→ full order lifecycle (place/modify/cancel, open + reduce-only close, nonce
recovery) on 2 markets. All PASS before you fund mainnet.

### 7. The actual switch (per bot, one at a time)
- Add `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` to the chosen live service and
  redeploy. **This is the point of no return — real orders.**
- Watch the first fills on the dashboard's 🔴 LIVE line + `venue_orders` ledger.
  Confirm size, market, and fill price look right before walking away.
- Bring bots live **one at a time**, smallest/safest first.

### 8. Kill / rollback
- Instant stop: set `REAL_MONEY_KILL=ARMED` (or delete the var) and redeploy —
  the bot flattens and halts on the next loop.
- Full revoke: revoke that sub-account's API key in the app.

---

## Reality check (read this)
Going straight to live **compresses your own gate ladder** — it skips the
multi-day testnet burn-in (Gate 2), the 1–2 week shadow evidence window (Gate 3),
and the staged micro-live sign-off (Gate 4) that the migration plan defined. The
paper edges are real but modest and on **simulated** fills; Lighter's zero fees
help, but live spread/slippage/latency are only truly known once real orders go
in. Mitigations baked in: tiny clips, hard per-bot notional caps, a $30/day
flatten-and-halt, isolated sub-account margin, and one-at-a-time rollout. Treat
it as a small-capital live experiment and scale only after live P&L matches the
paper behaviour. Keep the paper twins running as the control.

---

## 💸 Funding Farmer (Lighter directional funding) — go-live (added 2026-07-10)
`lighter_funding_bot.py` / bot id `perps-funding-lighter`. **Read this first:** unlike
the other bots this one is **DIRECTIONAL, not delta-neutral** — a single perp-only
venue has no same-coin hedge, so it takes the funding-receiving side and carries
real PRICE RISK bounded by a hard stop, *not* a hedge. Treat it as the highest-risk
bot in the fleet and size it smallest.

**What the code guarantees (proven in shadow):**
- `VENUE=lighter_live` refuses to boot unless `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND`
  AND `PERPS_FUNDING_LIGHTER_MAX_NOTIONAL` are both set (venues/safety.py).
- Every position has a hard price stop evaluated against a FRESH live-book mid
  (never a stale mark); if the book is unreadable it will NOT guess — it fail-safe
  flattens after a few blind loops. Post-stop cooldown prevents trend churn. A
  book-spread gate keeps thin traps (WEN ~870bps) out.

**Env for the live service** (its own Railway service + Lighter sub-account):
```
VENUE=lighter_live
LIGHTER_API_PRIVATE_KEY=<trade-only key for THIS sub-account>   # you paste, never me
LIGHTER_ACCOUNT_INDEX=<sub-account index>
PERPS_FUNDING_LIGHTER_MAX_NOTIONAL=60      # small — directional; ~2-3 slots at $25
FUNDING_ORDER_USD=25                        # optional (default 25)
FUNDING_HARD_STOP=0.05                      # optional 5% stop
FUNDING_MAX_SPREAD_BPS=50                   # optional liquidity gate
# REAL_MONEY_KILL intentionally NOT set yet -> boots ARMED (no orders)
```
Then: watch `funding-farmer-shadow` for a few days of real slippage/behaviour →
testnet smoke → set `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` on the live service to
arm it. Instant stop: set `REAL_MONEY_KILL=ARMED` (or delete it) + redeploy — it
flattens and halts. Keys/disarm/deposit are yours; I never touch them.

---

## 🌊 Tide Rider on Lighter (crypto-trend-daily, 1x long perp) — go-live (added 2026-07-10)
`lighter_trend_bot.py`. The daily 50/200 golden-cross trend follower, validated
long-only on **Kraken SPOT** (+52% basket / 2.7yr), re-expressed as a **1x LONG
PERP** on Lighter. **Honest trade-off:** a long perp PAYS funding, and this bot
holds for weeks in uptrends — re-validation (`scripts/backtest_tide_rider_perp.py`)
shows **+52% spot → +40% perp** over 2.7yr (funding drag −13pp), and the drag
**erases the down-trend protection** (ETH perp ≈ buy-and-hold). It is viable on
Lighter but weaker than the Kraken original; the drag is modelled in shadow so the
P&L you watch is honest.

**What the code guarantees:** `lighter_live` refuses to boot unless
`REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` and `CRYPTO_TREND_DAILY_MAX_NOTIONAL` are
set; 1x only (no leverage); death-cross exit + 35% catastrophic seatbelt (fires
even if candles fail); signal on closed daily bars only.

**Env for the live service** (own Railway service + Lighter sub-account):
```
VENUE=lighter_live
LIGHTER_API_PRIVATE_KEY=<trade-only key for THIS sub-account>   # you paste, never me
LIGHTER_ACCOUNT_INDEX=<sub-account index>
CRYPTO_TREND_DAILY_MAX_NOTIONAL=300        # 6 majors x ~$50 clips
TREND_ORDER_USD=50                          # optional (default 50)
# REAL_MONEY_KILL intentionally NOT set -> boots ARMED (no orders)
```
Watch `tide-rider-lighter-shadow` first (it should mirror the ~+40% perp path incl.
funding drag), then testnet, then set `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` to arm.
Instant stop: `REAL_MONEY_KILL=ARMED` + redeploy. Keys/disarm/deposit are yours.

**Alternative:** the strategy is *stronger* on Kraken spot (no funding drag, keeps the
down-trend protection). If you'd rather the full validated edge, the Freqtrade/Kraken
live path (real Kraken keys + dry_run:false) delivers +52% vs this +40%.
