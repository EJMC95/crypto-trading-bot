# Fleet Assessment — 7 July 2026

**Scope:** all 18 Railway services · full history (23 Jun → 7 Jul) · sources: Railway Postgres ledger (352 trades, 285 paper fills, 52,439 equity points), live `pnl.json` feed, `origin/main` code audit (64 commits reviewed), container logs.
**Everything below is dry-run / paper. No live funds. Nothing was changed on Railway during this assessment; no data was deleted.**

---

## 1. Executive summary

The fleet is healthier than it looks and sicker than it looks, in different places. The two perps engines are quietly excellent (rsi-meanrev +$41.47 ledger, 87% win rate; donchian-breakout +$37.96, 25W/1L). The July-1 day-trader rework is **verified working** — win rate 11% → ~45–50%, bleed stopped. The sniper's +$156 is honest arithmetic but dishonest narrative: one ANSEM lottery ticket (+$325) paid for 162 losing tickets.

The real problems are infrastructure, not strategy. The four family bots are **running twice** — once inside `freqtrade-bots`, and again as four volume-less Railway services that boot at $1000 and race-write the shared tables. That single fault explains the "counter resets," the equity flapping, and the polluted family-bot records the previous session fought blind. Separately, the learning brain has been **dead since 5 July** (the Docker image never includes `bot_learn.py`), and funding-carry is **structurally negative** (0W/28L) because its exit logic realizes fees before funding can accrue.

Crypto-fleet closed-trade P&L, ledger-clean (scanners and contaminated rows excluded): **+$181.68** — perps + sniper ledger +$218.19, freqtrade bots −$36.51. Three bots (rsi-meanrev +$41.47, donchian +$37.96, sniper +$155.94) earn it all; funding-carry (−$17.18) and the old day-trader era (−$20.53 of the intraday bot's −$23.19) are the drag. The stock pair sits outside that: +$418 (IBKR) and an unresolved ≈ −$8k (Alpaca, see §4).

---

## 2. Where each bot is winning or losing, and why

### The winners

**perps-rsi-meanrev — +$41.47 closed (54 trades, 87% WR, PF 5.5).**
Why it wins: it buys oversold dips on 30 liquid majors in a fear-dominated market and sells at the range high — mean reversion is the paying trade in chop, and this market has been chop-with-panic for two weeks. 47 of its 48 `long_range_high` exits are green. Why it nearly blew up anyway: before July 5 it could hold 14 correlated longs (70% of book) into one dip — the $51.6 max drawdown scar. The position cap (6 open, 2 new/loop) now bounds that. The feed tile says +$29.32 because three counter resets ate $12 of displayed history — the paper ledger is the truth (this is why the logbook matters, §5).

**perps-donchian-breakout — +$37.96 closed (26 trades, 25W/1L), plus ≈ +$22 open.**
Why it wins: the July-1 revert to Donchian 15/8 long-only put it back on the profile that suited it (fleet's proven PF ~1.8 edge family). It banks small channel exits (avg +$1.65). The caveat worth teaching: a 96% win rate with avg loss (−$3.20) ≈ 2× avg win is a scalper's ledger — it looks brilliant until a regime flip hands it several max-losses in a row. Its equity curve already shows a 6.2% max DD. Healthy, not miraculous.

**equities-regime-ibkr — +$418 from first record on $250k.**
SPY/QQQ regime-following doing its low-volatility job (max DD 0.63%). Nothing to fix.

### The lottery ticket

**event-listing-sniper — +$155.94 (177 trades, 8.5% WR).**
The entire profit is ANSEM: +$200 take-profit +$125 partials = +$325. Everything else nets −$169. The dominant loss mode is not stops — it's **delisting**: 142 of 177 exits (80%) are `delisted`, −$47.47, i.e. it buys tokens that die on the vine. `max_hold` adds −$50.67. The July-1 leveraged-token fix is verified (SOXL3L −$50 was the only leveraged buy ever; zero in 172 trades since). The July-4 throttle shrank ticket bleed. Strategically this is a tail-hunting machine, and tails DID pay — but the junk tax is 80% of activity. Options in §6.

### The broken one

**perps-funding-carry — −$17.18 (28 trades, 0 wins — every single close negative).**
This is arithmetic, not luck. Round-trip friction is 29 bps of notional ($0.58 on $200, $0.87 on $300 — charged half at open, half at close). At the 40% APR entry threshold, funding accrues ~0.0046%/hour — **fee payback needs ~64 hours**. But the bot exits on `decay` (APR < 15%) or `flip`, and spiky alt funding (VVV, LIT, TRUMP…) mean-reverts within hours. So it systematically enters hot, watches the rate decay, exits before payback, and realizes ≈ −fees. All 28 closes sit in a −$0.43…−$0.87 band = the fee bill. The July-6 tune (enter 40%, exit 15%, hold 14d, $300×8) raised the bars but kept the decay exit — the six post-tune closes are still −$0.76…−$0.87. Even its current open book shows the pattern (JTO: accrued $0.15 vs fees already $0.43). Fix options in §6 — or retire the concept honestly.

### Fixed and now marginal

**crypto-intraday-15m (Range Raider / DayTraderV5Gated) — lifetime −$23.19, but read it in eras.**
Pre-fix (≤ Jul 1): 142 trades, 11% WR, −$20.53 — killed by the tight ATR trail (124 trailing-stop exits, −$19.96 lifetime; when it held to ROI it was 16/16) and a junk-alt universe. Post-fix: 25 trades at ~44–50% WR, P&L ≈ flat. The regime legs added July 5 fire as designed (`bounce_pullback`, `range_meanrev`). Verdict: the rework verifiably repaired the process; the remaining question is whether a 15m scalper has any edge in a bear — flat is an acceptable answer while the regime is hostile. The brain's dying words (hypothesis `stop_too_tight`, seen 3×) point at the trail as the next dial.

### Correctly idle / too early

**crypto-trend-daily** (+$2.56; the one +$6.44 ROI win pays for 12 small exit-signal losses — discipline in a 2/15 golden-cross market), **crypto-swing-daily** (zero closes ever; regime gate holds cash by design), **crypto-trendmomo-4h** (two June losses predate the symmetry fix; +$4.40 equity now), **crypto-breakout-4h** (nearly idle, but currently probing this bounce with **10 correlated longs** — it's the one spot bot without a position cap and it wants one), **perps-regime-switch** (deployed and publishing, but **zero trades in 6 days across two gate-lowering rounds** — stop guessing and make it log per-pair ADX/EMA verdicts each loop so the binding constraint becomes visible), and the four **family bots** (mum/dad/avo-maria/georgia — 0–12 closes each, all data polluted by the dual-running fault; judge after two clean weeks).

**equities-momentum-alpaca** is a special case — see §4. **scanner-triangular-arb** finding nothing profitable in 848 cycles is a *correct negative result* (Kraken single-venue loops don't beat fees). **scanner-cross-exchange-arb**'s +$1,291 assumes top-of-book fills on both venues with 10 bps latency cost — treat as a signal generator, never as bankable P&L.

---

## 3. Bug-fix audit (what previous sessions shipped vs what's true today)

| Fix | Status | Evidence |
|---|---|---|
| Day trader 5m→15m Donchian + universe/ROI (Jul 1) | ✅ **Verified** | WR 11%→44–50%, bleed −$20.53→−$2.66, cadence 24/d→4/d |
| Sniper leveraged/ETF-token exclusion (Jul 1) | ✅ **Verified** | 0 leveraged buys in 172 post-fix trades (SOXL3L was the last, pre-fix) |
| hl-momo revert to Donchian 15/8 long-only (Jul 1) | ✅ **Verified** | 25W/1L, +$37.96 since |
| TrendMomoV1 symmetry + stop −0.12 (Jul 1) | ⚪ In code, ungraded | only 2 closed trades, both pre-fix |
| Range Raider regime legs (Jul 5) | ✅ Firing / thin edge | modes trade as designed; P&L ≈ flat |
| RegimeSwitchV2 + two ADX gate cuts (Jul 5–6) | ⚠️ Deployed, idle 6 days | publishing fine; needs diagnostics, not more loosening |
| Persist volume + drop `dry_run_wallet` (Jul 3–6) | ⚠️ **Partial — regressed by new fault** | volume holds for the main container; 51 reset events traced to duplicate services |
| `bot_pnl_store` PK (bot, open_ts, pair) (Jul 6) | ⚠️ Works, insufficient | stopped overwrites; 142 contaminated rows remain from the shared-SQLite era |
| Family bots: dedicated SQLite + proven strategies (Jul 6) | ✅ Verified in container | duplication stopped 07:31 UTC Jul 6 |
| Learning brain scheduled 2-hourly (Jul 5) | ❌ **Broken in deploy** | `bot_learn.py` never COPY'd into Dockerfile.freqtrade; brain stale since Jul-5 06:19 |
| funding-carry tune (Jul 6) | ❌ Insufficient | post-tune closes still ≈ −fees; structural exit flaw |
| Port 8089 "collision" (mum vs regime-switch) | ✅ Benign as deployed | separate containers, 127.0.0.1 scope; rename mum → 8093 for hygiene anyway |

**New faults found today:** (1) dual-running family bots — four standalone Railway services (`freqtrade-mum/dad/avo-maria/georgia`, no volumes) duplicate the same four bots inside `freqtrade-bots`; two parallel sessions shipped competing architectures and both are live; (2) `bot_learn.py` missing from the freqtrade image; (3) Alpaca's July-2 −$19.9k + misleading post-crash baseline; (4) your local Mac clone is 64 commits behind origin with 1 unpushed commit (`b82c5aa`) that edits `bot_pnl_store.py` and will conflict with the PK fix — reconcile or discard (its "reader API" idea is good and worth re-applying cleanly).

---

## 4. Data storage audit — how trades are recorded, and whether you can trust it

**The layers, from most to least durable:**

1. **Per-bot SQLite** (`/freqtrade/persist/*.sqlite`, Railway volume) — each freqtrade bot's own source of truth; survives redeploys since Jul 3.
2. **Railway Postgres** — the fleet ledger, 6 tables: `bot_trades` (closed freqtrade trades via poller), `paper_trades` (perps/sniper/funding fills, written directly by each bot), `bot_pnl` (live snapshot, last-write-wins), `bot_equity_history` (5-min samples), `bot_state` (brain/pulse/open-position persistence), `bot_trade_analysis`. **This is the layer that saved this assessment** — it held the truth through every SQLite reset.
3. **`pnl.json` feed** — ephemeral view of `bot_pnl`; resets whenever the writer resets. Never use it for history.
4. **`reports/` dailies + CHANGELOG/SESSION_LOG in the repo** — the narrative layer; well maintained.

**Integrity findings:** 0 feed gaps > 45 min across 52,439 points (plumbing is healthy); 51 counter-reset events (Jul-1 mass deploy wipe; Jul 5–7 rogue-service flapping; 3 real resets on rsi-meanrev); 142 contaminated `bot_trades` rows (one 35-trade set recorded under 5 bot names during the shared-SQLite window, closes 05:05–05:17 Jul 6 — duplication stopped once dedicated DBs shipped); Alpaca `pnl_abs` measured from a post-crash baseline (feed says +$3,215; reality from first record ≈ −$8.0k, including an unexplained one-day −$19.9k on Jul 2 that then froze for 3 days).

**Why Postgres was "blocked" and how it's solved:** claude.ai sessions run in an HTTPS-only container, so direct TCP to Railway's Postgres proxy fails there. Your Mac has no such restriction — this session pulled `DATABASE_URL` via your logged-in Railway CLI (nothing pasted into chat) and queried through a throwaway Dockerised psql. Long-term options: (a) this Mac-bridge pattern via Cowork whenever needed; (b) finish the **reader API** idea from your unpushed commit — a read-only `/ledger.json` endpoint on pnl-dashboard would let every Claude surface query history over HTTPS; (c) the GitHub-Actions deep-query workflow with the URL as a secret. Recommend (b) as the durable fix. And rotate the Postgres password when convenient — it has appeared in past chat history.

---

## 5. The logbook going forward

You asked for "a clear logbook to assess over time." The pieces now exist:

- **Canonical record:** Postgres `bot_trades` + `paper_trades` (after the quarantine purge in §6). Rule: *ledger for history, feed for liveness* — every report should quote ledger P&L, never tile P&L.
- **Assessment snapshots:** `analysis_YYYY-MM-DD/` in the repo (established 07-01, repeated today) — raw CSV extracts + the Excel workbook, so each assessment is reproducible and comparable. Today's is `analysis_2026-07-07/`.
- **Live view:** the **bot-fleet-status artifact** (in your sidebar) — reopens with fresh feed data, verdicts pinned from this audit.
- **Recommended additions** (small, high value): a `baselines` table (bot, inception_ts, inception_equity) so `pnl_abs` can never lie after a reset; an `instance_id` stamp on every publish so a rogue writer is instantly visible; a weekly automated snapshot appending one row per bot to an `assessment_log` table — that becomes your longitudinal P&L series regardless of any future reset.

---

## 6. Recommended changes — options with reasoning

**Priority 1 — kill the dual-running (before any other change, because it corrupts the evidence for every other decision):**
- **Option A — consolidate (simplest, $0):** delete the four standalone family services; the main container already runs all nine with the persist volume. Risk: nine bots + dashboard + pulse in one box is a real OOM/CPU concern — watch restarts.
- **Option B — isolate (cleanest):** keep the four services, give each a volume + `FT_POLLER_BOTS` override, and remove the four from `run_all.sh` + `_DEFAULT_BOTS` in the main container. Per-bot isolation, no resource contagion; costs a few dollars more.
- Either way: afterwards purge family-bot rows written since Jul-5 17:06 and quarantine the 142 duplicated trades (SQL in the workbook's Data Integrity tab). **I changed nothing — your call, and it's a two-command deploy either way.**

**Priority 2 — one-line brain fix:** add `COPY bot_learn.py /freqtrade/bot_learn.py` to `Dockerfile.freqtrade`, redeploy. The whole learning layer is waiting on this.

**Priority 3 — funding-carry:** (a) exit on **flip or fee-payback only** — while funding sign favours you, decay merely slows earnings, it never costs; exiting on decay is the bug; (b) add a persistence filter (enter only if funding has stayed hot ≥ 6h — spikes that mean-revert in an hour never pass); (c) majors-only universe (BTC/ETH/SOL funding persists; VVV doesn't); (d) retire it and bank the lesson. Honest counsel: (a)+(b) is a real strategy; as built it cannot win.

**Priority 4 — sniper junk tax:** raise the intel gate to skip tokens with no CoinGecko footprint / listed on < 2 real exchanges (the delisted cohort). Keeps the tail-hunting, cuts the 80% junk churn. Counter-argument worth weighing: ANSEM-class winners may correlate with junk-class listings — if you tighten too far you may filter the tail you're hunting. Middle path: half-stake junk (already exists) → quarter-stake, rather than exclusion.

**Priority 5 — small guards:** max-open cap on crypto-breakout-4h (mirror rsi-meanrev's); diagnostic logging in RegimeSwitchV2 before any further gate cuts; mum → port 8093; reconcile the local clone (`git stash && git pull --rebase`, keep origin's `bot_pnl_store.py`, re-apply the reader-API as a fresh commit); update stale `run_all.sh` comments.

**Leave alone:** rsi-meanrev, donchian-breakout, trend-daily, swing-daily, IBKR. Winners and disciplined idlers need supervision, not surgery.

---

*Assessment run from Cowork on 7 Jul 2026, ~13:30–14:30 AEST. Access path: Desktop Commander → Mac → Railway CLI (npx) → Dockerised psql → Postgres; feed via HTTPS; code via `git fetch origin` (local tree untouched). No Railway services, configs, or data were modified.*
