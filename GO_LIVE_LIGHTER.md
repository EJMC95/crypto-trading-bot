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
# The risk knobs below are OPTIONAL — the code defaults ARE the tuned values
# (backtest_directional_funding.py: a 5% stop whipsaws out and LOSES; 10% is the
# least-bad). Only set them to OVERRIDE; do NOT copy the old 5%/50 values.
FUNDING_HARD_STOP=0.10                      # optional (default 0.10 — tuned; don't lower)
FUNDING_TAKE_PROFIT=0.04                    # optional (default 0.04)
FUNDING_MAX_SPREAD_BPS=20                   # optional (default 20 — live hot coins <=3.5bps)
FUNDING_MIN_VOL=10e6                        # optional (default $10M 24h turnover)
# REAL_MONEY_KILL intentionally NOT set yet -> boots ARMED (no orders)
```
Then: watch the shadow row (`perps-funding-lighter-lshadow` on the dashboard) for a
few days of real slippage/behaviour → testnet smoke (`scripts/lighter_testnet_smoke.py`)
→ set `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` on the live service to arm it. Instant
stop: set `REAL_MONEY_KILL=ARMED` (or delete it) + redeploy — it flattens and halts.
Keys/disarm/deposit are yours; I never touch them.

**Shadow readiness (checked 2026-07-11):** the shadow service is deployed and running
live against Lighter mainnet books. Measured perp-leg slippage on the coins it actually
trades is **sub-1bps** (ETH 0.3–0.5bps, SOL 0.13bps, BTC 0.36bps, HYPE 0.92bps) — the
zero-fee + ≤20bps-spread-gate thesis holds and thin traps are excluded. Code + guards
re-validated: `--once` runs clean; `lighter_live` REFUSES to boot without BOTH
`REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` and `PERPS_FUNDING_LIGHTER_MAX_NOTIONAL`.
**Still thin:** only ~2 closed round-trips so far (~net flat) — execution is proven,
the P&L track record is not. Honest expectation stands: directional funding capture is
~break-even (funding is real but price risk ≈ offsets it); size it smallest in the fleet.

**Position SCANNER (added 2026-07-11) — picks the best RISK-ADJUSTED positions, not just
the hottest funder.** Replaces the raw-|APR| sort with: cheap funding prefilter → candle-
scan the top 15 (cached ~50min) with a realized-vol + adverse-trend VETO (skip stop-out
traps) and an |APR|-backbone risk-discounted rank → book-probe only the top 5 (spread +
clip-slippage gate + cross-venue `_bench` tilt). Backtested (`scripts/backtest_scanner.py`,
150d, 6-slot portfolio): at the **default 0.40 gate** the veto lifts net **+52%** and
ret/DD **2.0→5.3** with **lower drawdown and fewer trades** (both halves + OOS). HONEST:
much of the gain is directional mean-reversion (regime-dependent) — the **vol veto** is
the durable piece. On by default; env knobs (all optional):
```
SCAN=off                        # restore legacy raw-|APR| selection (rollback / A-B)
SCAN_ENTER=0.25                 # OPT-IN widen the gate (in-cache +155% but partly a
                                #   slippage artifact + 2x churn — shadow-validate FIRST)
SCAN_VETO_VOL=0.015             # skip 1h realized vol > 1.5%/hr (the durable win)
SCAN_VETO_ADVERSE=0.05          # skip a fresh >5% move into our stop
SCAN_MAX_SLIP_BPS=25            # clip VWAP-slippage gate (thin-trap killer)
```
Every scanned entry logs its scan evidence (vol/adverse/slip/cross-venue/score) to the
`venue_orders` ledger — watch the shadow row to validate the live-only layer (cross-venue
+ book depth) before trusting it, then decide on the opt-in gate widening.

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

**Deploy:** point the service's Config-as-code "Railway Config File" at
`railway.trendlighter.toml` — it selects `Dockerfile.trendlighter` **and** pins
`restartPolicyType="always"`. That auto-restart is safety-critical: every rail
(catastrophic stop, death-cross exit, daily-loss + kill-switch flatten) runs
IN-PROCESS each loop, and a live 1x long perp has **no resting stop on Lighter's
book** — the running process *is* the position manager, so it must come back after
any crash. (Do NOT rely on Railway's default restart policy; it caps retries and can
leave a funded position unmanaged.)

**Env for the live service** (its own Railway service + its own Lighter sub-account):
```
VENUE=lighter_live
LIGHTER_API_PRIVATE_KEY=<trade-only key for THIS sub-account>   # you paste, never me
LIGHTER_ACCOUNT_INDEX=<this bot's sub-account index>
LIGHTER_API_KEY_INDEX=4                     # MUST match the key index you registered (0-3 reserved for Lighter's UI; code default 4)
LIGHTER_ORDER_USD=15                        # $ per clip — the knob live/shadow ACTUALLY read (default 30). $15 clears Lighter's $10/order min. TREND_ORDER_USD is a NO-OP outside the offline hl_paper smoke.
CRYPTO_TREND_DAILY_MAX_NOTIONAL=90         # 6 majors x $15 = $90 -> floor(90/15)=6 slots
LIGHTER_MAX_DAILY_LOSS=15                   # catastrophic daily flatten+halt, $/UTC-day (default 30). At $15 on a $90 book that's ~-17%/day — clear of normal dips, so it won't prematurely flatten this weeks-holding trend follower.
LIGHTER_BUDGET_SHARE=0.25                   # this process's share of the 60/min per-L1 request budget (keep all live Lighter services' shares summing <=1.0)
# REAL_MONEY_KILL intentionally NOT set -> boots ARMED (no orders)
```
Watch `crypto-trend-daily-lshadow` first (the 🌊 Tide Rider card with a blue SHADOW
badge; the live row will be `crypto-trend-daily-lighter` with a red LIVE badge) — it
should mirror the ~+40% perp path incl. funding drag. Then testnet
(`scripts/lighter_testnet_smoke.py`), then set `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND`
on the live service to arm. Instant stop: `REAL_MONEY_KILL=ARMED` + redeploy.
Keys/disarm/deposit are yours.

**Alternative:** the strategy is *stronger* on Kraken spot (no funding drag, keeps the
down-trend protection). If you'd rather the full validated edge, the Freqtrade/Kraken
live path (real Kraken keys + dry_run:false) delivers +52% vs this +40%.

---

## 🎫 Ticket Taker — go-live (added 2026-07-17, divergence-only, Tide Rider's slot)

**Status: BUILT AND INERT.** The code refusal is lifted; every remaining gate is
an env var only you can set. The image trades nothing until you do.

### What was fixed to make this safe (all shipped, all fixture-tested)
- **Symbol namespace** — the taker keys on Lighter-native symbols (`1000BONK`),
  `LighterClient` on fleet symbols (`kBONK`). Unconverted, live would have
  re-opened `1000BONK` every 5 min and silently no-op'd its closes. Converted at
  the venue boundary; `to_lighter` now mirrors `from_lighter` (verified against
  all 218 live markets, 0 round-trip failures — the old hardcoded 4-entry list
  missed `1000NOT`/`1000TOSHI`).
- **`market_close` returning `None` is now a FAILED close**, both call sites. It
  does not raise, so an `except` guard could not see it.
- **Divergence-only allow-list**, fail-CLOSED, reads no bus payload.
- **`TT_VENUE` mandatory** — identity is never inherited.
- **`apply_tuning()` no-ops live** — `taker.*` is the SHADOW lane.
- **Adoption guard** — refuses to trade an account holding a position it has no
  meta for (see the handover step below).
- **Run-once kill semantics** — see the ⚠️ note below.

### ⚠️ Read this before you arm anything
**The kill switch on this bot FLATTENS; it does not refuse-to-boot.** The taker
is a run-once process (one cycle, then exit), so every cycle is a boot. If it
used `assert_can_start()` like the daemons, arming `REAL_MONEY_KILL` would raise
before the flatten could run and would **strand the book** — no stop, no
max-hold, nothing watching it. So the live arm keeps the **cap** as a hard boot
gate and lets the kill switch reach flatten+halt. Arming it stops all trading on
the very first cycle and closes the book on the way out.
*(This is why `crypto-trend-daily-lighter` sits at `status: error` with a
position behind it — that bot refuses to boot when armed. Different semantics;
know which you are looking at.)*

### 🛑 THE IMAGE DECIDES WHICH BOT THE KILL SWITCH IS PROTECTING — read first
**This already went wrong once, at 17:42 Sydney on 17-Jul, with real money.**
The disarm was applied to `tide-rider-lighter-live` in order to take the taker
live. But that service is built from **`Dockerfile.trendlighter`**, whose `CMD`
is `lighter_trend_bot.py` — **the taker's code is not in that image at all**, so
`TT_VENUE` there was inert. `REAL_MONEY_KILL` was the *only* thing holding Tide
Rider down. Disarming it **booted the bot being retired**, and it immediately
re-bought the position the operator had just flattened by hand
(`OPEN TRX long $12 | ema50 0.3278 > ema200 0.3195`, on a $34.67 real book).

The rule that follows, and it is not negotiable:
> **Never disarm a kill switch to change WHICH bot runs.** The env vars of a bot
> that is not in the image are inert; the disarm is the one change that always
> lands. Change the IMAGE, verify the running container is the bot you meant,
> and disarm LAST.

`REAL_MONEY_KILL=ARMED` on a service whose image runs bot X protects **bot X** —
not whatever bot you intend to run there next.

### 🔴 USER-ONLY steps — in this order
1. **Point the service at the taker's IMAGE. Do this BEFORE any env change.**
   Set the service's Config-as-code **Railway Config File** to
   `railway.takerlive.toml` (it selects `Dockerfile.takerlive` and
   `restartPolicyType=always`). Prefer a **NEW service** — repurposing
   `tide-rider-lighter-live` is what produced the incident above, and its
   `CRYPTO_TREND_DAILY_MAX_NOTIONAL` / `VENUE` vars would linger.
   Leave `REAL_MONEY_KILL=ARMED` throughout this step.
2. **VERIFY the running container is the taker — do not trust the deploy.**
   After it redeploys, with the switch still ARMED, the logs must show the
   taker's own marker and nothing of Tide Rider's:
   ```
   railway logs --service <svc> | grep -E "ticket-taker|TT_VENUE|trend|ema50"
   ```
   You want `[ticket-taker] ...` lines (or its `TT_VENUE is unset` refusal).
   If you see `ema50` / `OPEN ... long`, **you are still running Tide Rider —
   STOP.** ("git-connected" and "the push rebuilt it" have both been proven
   false here; the running container is the only evidence.)
3. **FLATTEN THE SUB-ACCOUNT.** If you hand over Tide Rider's sub-account,
   its leftover position must be closed by hand before the taker boots. The
   taker **refuses to trade a dirty account** rather than adopt it (it has no
   entry clip, lens or opened-time for a foreign position, so its ±4% ladder
   would manage a trend position on the wrong bars). Note the dashboard **cannot
   confirm this for you**: `crypto-trend-daily-lighter` shows `held:['TRX']` at
   equity $34.67, but its status is `error` and that write is status-only — those
   numbers are the last good publish, frozen. Only a keyed read or the Lighter
   app can tell you if it is actually flat.
4. **Env for the live service** — only after steps 1–3:
```
TT_VENUE=lighter_live                       # mandatory; the bot refuses without it
LIGHTER_API_PRIVATE_KEY=<trade-only key for THIS sub-account>   # you paste, never me
LIGHTER_ACCOUNT_INDEX=<this bot's sub-account index>
LIGHTER_API_KEY_INDEX=4
LIGHTER_TICKET_TAKER_MAX_NOTIONAL=90        # hard cap on deployed notional; live REFUSES to boot without it
LIGHTER_MAX_DAILY_LOSS=15                   # absolute $/UTC-day flatten+halt
TT_DAILY_LOSS_LIMIT=0.05                    # % daily rail on top (default 0.05)
LIGHTER_BUDGET_SHARE=0.25                   # keep all live services' shares summing <=1.0
TT_LOOP_SECONDS=300                         # match the shadow arm so the arms stay comparable
# TT_CLIP_* / TT_TP / TT_SL / TT_MAX_HOLD_H: the OPERATOR's env is authoritative
#   live (apply_tuning is a no-op there). Defaults: TP +4%, SL -3%, hold 48h,
#   constant-risk clips $20-80. NOTE the shadow arm currently runs growth-rail
#   levers taker.sl=-0.04 / taker.max_hold_h=24 — live will NOT inherit those.
#   If you want the shadow arm's bars, set them explicitly here.
# REAL_MONEY_KILL intentionally NOT set -> boots ARMED -> first cycle flattens
#   (a no-op on a flat account) and halts. Nothing trades.
```
5. **Arm it LAST** — and only once step 2 has *proved* the container is running
   the taker: set `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` **on that service
   only**. If step 2 was skipped, this is the single change that moves money on
   whatever bot the image actually contains. That is the whole incident above.
   **Instant stop:** `REAL_MONEY_KILL=ARMED` + redeploy → next cycle flattens and
   halts (this bot's kill switch closes the book — see the ⚠️ note; Tide Rider's
   refuses to boot instead, which is why its TRX needed closing by hand).

### The evidence, stated plainly (measured 17-Jul ~18:00 Sydney)
This does **not** meet the fleet's own gate (`CLAUDE.md`: 30-day WR>55% AND
maxDD<15%), and you should go in knowing the numbers:
- **1.18 days** of divergence record (n=7 closes), against a **30-day** gate.
- **n=1 real book-walked fill, ever.** All 7 closes were priced by PaperBroker at
  a flat **4bps**; the one measured fill cost **14.59bps** (~3.6x).
- The brain's counterfactual edge is **+25.3bps/4h** (n=2988) vs a measured
  **~29.2bps round trip** → **−3.9bps**. Horizons differ (the taker holds to
  TP/SL/24h, not 4h), so this bounds rather than settles it — but n=1 is the
  entire cost evidence.
- Win rate is **7/7 = 100%** closed-only, **9/13 = 69%** including open positions
  marked to market.
- **`long-divergence` is n=0 realized** and XPD is held long-divergence in shadow
  now. "Divergence only" ≠ "shorts only" and the brain grades divergence as one
  blended lens with no per-side split. Decide this before arming.
Precedent: Trail Blazer went live on ~2 days of shadow and was retired as "a
lucky ~30d window". The shadow arm only started measuring real execution at
06:53 UTC on 17-Jul — a week of real fills costs nothing and would answer the
question the record currently cannot.
