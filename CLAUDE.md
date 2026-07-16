# CLAUDE.md — crypto-trading-bot Fleet

## What This Repo Is
Eamon's crypto trading bot fleet — **LIGHTER-FIRST since 2026-07-14** (user
decision: "all services must run off lighter"). Books are $1,000 paper/shadow
each, no top-ups, except the real-money Lighter live rows. Dashboard:
https://pnl-dashboard-production-858c.up.railway.app/

## Fleet Overview (post 14-Jul Kraken retirement — ~21 live rows)

### The trading fleet (Lighter)
| Row | Name | What it is |
|-----|------|------------|
| freqtrade-{mum,dad,avo-maria,georgia}-lshadow | 👩👨🙏🔮 family | TrendMomo/MomoBreakout/SwingDip/DayTraderV5 on Lighter (gate0 `lighter_family_bot.py`, service `family-lighter-shadow`); closes tagged `long-<tag>_<exit>` + brain stake-mults applied at entry (15-Jul) |
| crypto-{intraday-15m,swing-daily,breakout-4h}-lshadow | spot ports | same service, 29-pair whitelist |
| crypto-trend-daily-lighter / -lshadow | 🌊 Tide Rider | **LIVE real money** + shadow (tide-rider service) |
| perps-funding-lighter-lighter / -lshadow | 💸 Funding Farmer | **LIVE** funding harvester + shadow |
| perps-funding-carry (+ -lshadow) | 🌾 Yield Harvester | HL-data paper origin + Lighter shadow |
| perps-funding-spread-lshadow | ⚖️ Counterweight | funding L/S book |
| lighter-perp-sniper-lshadow | 🎯 Perp Sniper | new-listing sniper |
| lighter-dislocation-lshadow | 🧲 Snap Back | dislocation fader |
| lighter-ticket-taker-lshadow | 🎫 Ticket Taker | **trades Lighter Scout's high-conviction tickets** (breakout/dip/momentum long + divergence long/short); stress veto pauses entries at venue |prem| med ≥15bps; closes tagged `<side>-<lens>_<exit>` so the brain grades each lens |
| equities-regime-lshadow / equities-momentum-lshadow | 📊 Index Rider / 🏆 Stock Leaders | stock-perp ports (IBKR/Alpaca originals RETIRED 14-Jul) |
| event-listing-sniper | 🎯 Launch Sniper | CEX spot listings (legacy, still running) |
| scanner-cross-exchange-arb | 🔀 Gap Scout | CEX dislocation scanner + Lighter premium publisher |

### Intelligence layer (main freqtrade-bots container, run_all.sh loops)
- `lighter_market_scout.py` 🛰️ — ALL ~215 Lighter books: premium stress,
  liquid funding extremes, cross-venue funding divergence, vol/OI moves,
  listings, **per-strategy tickets** → bot_state `lighter-market`
- `bot_learn.py` (brain) — L4 stake multipliers (family bot + strategies
  consume via `fleet_bus.py`), per-bucket DIAGNOSIS (exit/entry/fee/regime/
  venue), venue A/B, scout lens-forward grades (taker veto); generates for
  LIVING bots only (retired set + 7d close recency, 15-Jul). **v3 statistics
  engine (16-Jul, `brain_stats.py`)**: decay-weighted buckets (14d half-life
  forgetting), empirical-Bayes pooling (tag-family → bot → fleet priors),
  Wilson/t evidence bars, regime splits, episode-deduped lens grading (raw
  fields unchanged — consumer contracts held); floors/streaks/reduce-only
  UNCHANGED (authority did not move); validated by `brain_replay.py`
  (ledger no-regression + 6-scenario synthetic discrimination, header has
  the verdict); kill switch `BRAIN_MULT_ENGINE=v2`. **Fast-path (16-Jul
  "no-brainer window")**: EMER_* bars (n≥40, t≤−2.5, post_wr<0.20) skip the
  3-run streak gate on the FIRST qualifying run — latency only, authority
  unchanged; urgent keys surfaced on `brain-vitals`; →
  `learning-brain`, `brain-stake-mults`, `brain-diagnosis`,
  `brain-lens-forward`, `brain-vitals`
- `fleet_risk.py` — traffic light (live > lshadow > paper via
  `authoritative_row`, 65-min staleness filter) + signal bus + **7d fleet
  drawdown governor** (`clip_scale` 1.0/0.5/0.25 — Ticket Taker consumes,
  gate0 advisory) + **exposure view** (`exposure`: effective-bet count via
  1/HHI, per-symbol pileup, crypto/equity split — advisory, 15-Jul);
  long-budget veto ENFORCED in strategies + taker + family bot
  (`FLEET_RISK_MODE=advisory` = kill switch)
- `evidence_board.py` ⚖️ — the evidence organ (15-Jul): scores/corroborates
  fleet-alerts, synthesizes cross-feed items (lens floors, veto flap, venue
  stress, governor proximity), auto-verdicts mechanical items (manual
  `evidence-review` stays senior), phone-notifies warn/action, publishes
  SHADOW restrict-only proposals → `evidence-board` (EVBOARD_MODE=shadow)
  + **GROWTH RAIL (15-Jul user mandate: widening must not need the
  operator)**: EXPAND-direction responses ENACT via `fleet_tuning.py` —
  whitelisted, hard-bounded, TTL'd levers (auto-revert by expiry), lanes in
  `FLEET_TUNING_ENACT_LANES` only (default `paper-scanner`; trading lanes
  stay proposal-only until a review adds them; real money NEVER). First
  loop: Gap Scout census quiet 24/48/96h → widen prefilter/book-budget/
  second-tier venues (kucoin/gateio/mexc), phone-notified per step
- `lighter_scout_tuner.py` 🧠🔧 — the Lighter loop's SELF-TUNING organ
  (15-Jul user mandate: the scanner "needs the freedom, with the brain's
  support, to act"). Hourly, stateless, replay-gated: replays the scout
  tape through the taker's REAL code (`lighter_ticket_replay`), widens
  STARVING lenses' taker bars (not-worse both halves), expands
  brain-graded WINNER lenses (must IMPROVE both halves), auto-runs the
  TP/SL/hold sweep (anti-overfit floors: ≥10 closed, +$2 total, both
  halves), widens starving lenses' SCOUT emission bars (grading diet —
  advisory tickets only). Everything lands as bounded TTL'd
  `fleet-tuning` levers (auto-revert); never widens a brain-vetoed lens;
  fail-safe neutral on a dark brain. → bot_state `scout-tuner`
- `fleet_proprioception.py` 🦾 — PROPRIOCEPTION (16-Jul, "advance the
  autonomous organ"): the autonomy stack's sense of its OWN movements —
  the first RETROSPECTIVE grade on growth-rail enactments (every prior
  gate was prospective/in-sample). Tracks every lever EPISODE (open →
  expire/release/value-change; long stances sliced daily) and grades it
  out-of-sample: taker levers get the TRUE replay counterfactual in $
  (during-episode tape, env defaults vs enacted bars through the taker's
  real code), scout diet levers get grading throughput (lens n4h delta),
  gapscout gets census activity; live/xp episodes are RECORDED only (the
  judge + fade-watch stay the real-money authority). Per-lever verdicts
  helping/hurting/neutral (floors n≥2 episodes, ±$3; HURTING exists only
  on the taker lane — the one lane with a $ counterfactual; joint stances
  share blame, conservative in the restrict direction). CONSUMED
  restrict-only: the scout tuner refuses to re-assert a HURTING lever
  (`apply_proprioception`); the board surfaces 🦾 items (hurting=warn,
  helping=expand evidence for the review); immune scans the payload.
  Fail-safe: a dark organ restricts nothing. Expand-side consumption
  deliberately unwired until the 21-Jul review (agenda item 12). →
  bot_state `fleet-proprioception`
- `experiment_judge.py` 🧪⚖️ — the shadow→live PROMOTION pipeline (15-Jul
  user mandate: shadow wins must "carry across to the real money bots").
  Hourly, ONE candidate at a time on the Funding Farmer's -lshadow twin
  (xp.* levers; while running, the twin is an EXPERIMENT arm, not a
  control arm; every close row stamps extra.bars). Promotion to the live
  arm (live.funding.* — this judge is the ONLY writer) requires the
  PAIRED bar: ≥7d, ≥30 shadow closes, live ≥10, shadow positive in its
  own right AND beats live per-trade by ≥0.5pp on the window AND both
  halves. Fade-watch releases a promotion whose live arm turns negative
  (n≥15). Candidate queue in CANDIDATES (first: enter_apr 0.30 — the
  11-Jul "opt-in, shadow-validate" gate widening). Tide Rider excluded
  (trades too rarely to judge; stays backtest-validated). → bot_state
  `xp-judge`; phase surfaced on the evidence board (🧪)
- `fleet_immune.py` 🛡️ — the IMMUNE + SELF-REPAIR organ (15-Jul, from the
  operator's "what self-repairs / what filters" framing + the same-evening
  incident where a 39h-stale artifact drove a false live down-scale).
  Covers the failure class the death-oriented watchdog misses — ALIVE BUT
  SICK (fresh, in-TTL, trusted, but WRONG). FILTRATION: prunes the
  fleet-alerts bloodstream of age-stale + known-toxic ANTIBODY matches.
  ADAPTIVE IMMUNITY: scans fresh organ payloads for invariant violations,
  QUARANTINES a sick growth-rail lever (`fleet_tuning.get_lever` honors
  `fleet-immune.quarantined_levers` → reverts to operator default), phone-
  pushes NEW sickness. Restrict/clean only; fail-safe (dead immune = no
  quarantine). → bot_state `fleet-immune`; surfaced on the board (🛡️)
- `fleet_regen.py` 🩹 — REGENERATION (self-repair tier 2): restores a
  stateful organ the immune organ flagged SICK to its last-good history
  snapshot (age-bounded) or a safe baseline; content-only, carries the
  snapshot's own age so it never asserts old data as current. → `fleet-regen`
- `strategy_incubator.py` 🧬 — REPRODUCTION: breeds strategy GENOTYPES
  (crossover+mutation). Taker offspring scored instantly by replay
  (shadow-only leaderboard); funding offspring PROPOSED to `xp-queue` for the
  experiment judge's identical paired live bar — no offspring shortcuts the
  gate. Recombines within registry bounds only (invention stays human). →
  `strategy-incubator` + `xp-queue`
- `fleet_clock.py` 🕐 — CIRCADIAN: the fleet's shared sense of time (trading
  session, thin-liquidity, heavy-job window). Advisory. → `fleet-clock`
- `implementation_shortfall.py` 📏 — LIVE-vs-SHADOW execution quality: the
  continuous per-trade return gap (live real fills − shadow mark fills) on
  the SAME coins both arms closed, weighted by paired closes, with ENTRY/
  EXIT-slip decomposition (funding bot records fill prices since 15-Jul).
  Verdict clean/live-ahead/live-slipping/insufficient; sustained slip →
  phone. Answers "is the live book slipping, and on entry or exit?". →
  `impl-shortfall`
- `fleet_respiration.py` 🫁 — RESPIRATION / blood-oxygen: OXYGEN = fresh
  market data; LUNGS = the venue-fetch layer. Measures SpO2 (weighted
  fraction of data feeds breathing fresh) and phone-alerts on a HYPOXIA
  transition — the fleet-wide data-starvation the per-organ watchdog misses.
  → `fleet-respiration`
- `event_sentinel.py` 🗞️⚡ — the EVENT organ (16-Jul user mandate: "be ahead
  of the game" on major world events). market_pulse reads MOOD; the
  sentinel reads discrete typed EVENTS: RSS + GDELT sweep every 10 min →
  keyword taxonomy (monetary tightening/easing, CPI hot/cool, crypto
  crackdown/ETF-adoption, exchange incident, stablecoin stress,
  geopolitical shock, banking stress, AI boom) → severity-gated per-sector
  anticipations from a seeded HISTORICAL PLAYBOOK (COVID, Terra, FTX, SVB
  safe-haven flip, ETF Jan-24, yen-carry Aug-24, tariffs Apr-25) → then
  GRADES its own anticipations at 4h/24h/72h against sector indices
  chained from the scout's marks, and the playbook confidence LEARNS
  (EB blend; a wrong playbook decays toward zero bias — direction never
  auto-flips without review). ADVISORY: zero consumers until a review
  wires one (restrict-only first). Tuning: `evsent.*` levers, lane
  `event-sentinel`. → bot_state `event-sentinel` (+ `-state`)
- `regime_oracle.py`, `market_pulse.py` (history appends every 30 min, 15-Jul),
  `cleanup_legacy_bots.py` (boot prune of retired rows)

### RETIRED (rows hidden + pruned; ledgers kept)
Kraken paper 8 (spot 4 + family 4, 14-Jul user cut — Kraken/laptop
processes are operator-stopped), equities-momentum-alpaca +
equities-regime-ibkr (14-Jul), Trail Blazer, Bounce Catcher, Two-Way Tide,
Loop Scout, trendmomo-4h (12/13-Jul). See RETIRED_ROWS in pnl_dashboard.py.

### Read-only endpoints (no auth)
`/pnl.json` `/trades.json` (`?source=paper` for the paper_trades ledger)
`/bus.json` (risk light + signal bus + brain keys + lighter-market,
`?hours=` history) `/pulse.json` `/disloc.json` `/watchdog.json`

### 15-Jul reconciliation (this repo's git now matches what runs)
The 14-Jul pivot shipped from branch `claude/gapscout-profitable-trades-ebrprj`
via PRs #40-44 to MAIN while the Lighter services deploy from GATE0 — the two
lines are now cross-merged (15 Jul) and `recovery/freqtrade-bots-image-20260715`
snapshots the exact deployed freqtrade-bots image. Operator actions done 15 Jul:
family Kraken Railway services stopped, Alpaca cron (`trading-bot` service,
project trading-bot) torn down. equities-regime-ibkr's publisher runs on an
UNIDENTIFIED host (not this repo, not ~/Claude/Trading, no local process) —
its row is dashboard-retired regardless; stop the process when found.

## Dashboard
- **File:** `pnl_dashboard.py` — Postgres-backed, auto-refreshes every 30s
- **DB:** Each bot publishes to `bot_pnl` table via `bot_pnl_store.py`
- **Auth:** DASH_USER / DASH_PASS env vars on Railway

## Key Files
- `pnl_dashboard.py` — main dashboard server (+ fleet_watchdog_svc.py)
- `bot_pnl_store.py` — shared Postgres publisher (all bots import this)
- `lighter_market_scout.py` / `lighter_ticket_taker.py` — scout + its trader
- `bot_learn.py` + `fleet_bus.py` — brain and the strategies' read client
- `fleet_risk.py` / `regime_oracle.py` / `market_pulse.py` — shared organs
- `lighter_ticket_replay.py` — replay the recorded scout tape through the
  taker's real code (rule changes judged in seconds, not shadow-days)
- `cross_exchange_arb.py` — Gap Scout (CEX dislocation + Lighter premium)
- `funding_carry_bot.py` — Yield Harvester (HL-data paper origin)
- `user_data/` — Freqtrade strategies/configs (dormant post-Kraken; the
  gate0 family bot re-expresses them on Lighter)
- gate0 branch (`claude/lighter-gate0`) — the Lighter runtime (venues/,
  ShadowBroker, lighter_family_bot.py); its services deploy from there

## Cross-Bot Intelligence (bot_state keys — since 2026-07-14 CONSUMED, not just published)
- `brain-stake-mults` — bot_learn's L4 reduce-only per-(bot, enter_tag) stake
  multipliers (floors: n≥30 era trades / 3 consecutive runs; never >1.0).
  Consumers: `lighter_family_bot.py` at entry (keyed `<bot_id>` +
  `long-<tag hyphenated>`, 15-Jul) and the freqtrade strategies'
  `custom_stake_amount` — both via `fleet_bus.py`.
- `fleet-risk` — L2 traffic light, mode **enforce**: strategies veto NEW long
  entries at long-budget (20). Kill switch: `FLEET_RISK_MODE=advisory`.
- `signal-bus`, `regime-oracle`, `market-pulse`, `listing-intel` — published
  context (funding APRs, dislocation, per-major regime, news mood, sniper
  intel classes). Only market-pulse.panic + the two keys above are consumed.
- `fleet-tuning` — the growth rail's lever payload (authors: evidence board
  + scout tuner, MERGED writes with per-lever expiry; `fleet_tuning.py`
  registry clamps; consumers: Gap Scout, Lighter Scout, Ticket Taker).
  Lanes: paper-scanner / lighter-scout / lighter-taker / lighter-xp (zero
  real money) + lighter-live (`live.clip_scale` + the judge's PROMOTED
  `live.funding.*` — see growth rail + experiment judge above). `gapscout-census` — Gap Scout's epoch-2 episode census (board
  reads `quiet_hours`). `scout-tuner` — the tuner's cycle log + enactments.
  `fleet-proprioception` — per-lever enactment outcome grades (episodes +
  helping/hurting verdicts; tuner consumes HURTING restrict-only).
- Every payload carries `updated`+`ttl_sec`; consumers go NEUTRAL on stale
  data (`fleet_bus.is_fresh`). Backtests are inert (no DATABASE_URL).
- Bot identity for multiplier lookup = `bot_name` in each freqtrade config
  (= dashboard bot ID — keep them matching).

## How Bots Publish to Dashboard
Each bot calls `bot_pnl_store.publish(...)` with:
```python
{
  "bot": "freqtrade-mum",          # bot ID — must match CURRENT_BOTS in dashboard
  "status": "running",
  "equity": 1023.50,
  "pnl_abs": 23.50,
  "pnl_pct": 0.0235,
  "closed_trades": 12,
  "open_trades": 2,
  "wins": 8,
  "losses": 4,
  "pnl_daily": 5.20,               # optional — today's P&L
  "pnl_weekly": 18.40,             # optional — 7d P&L
  "pnl_monthly": 23.50,            # optional — 30d P&L
  "max_drawdown": -0.045,          # optional — max drawdown %
  "best_trade": 12.30,             # optional — best single trade $
  "worst_trade": -8.10,            # optional — worst single trade $
}
```

## Freqtrade Bot Configs (new bots)
All new bots:
- `dry_run: true`
- `dry_run_wallet: 1000`
- API server enabled on ports 8080–8083
- Logs to `logs/freqtrade.log`
- SQLite DB at `logs/tradesv3.sqlite`

## Claude Code Instructions
- Ask Claude to backtest any bot: `freqtrade backtesting --config <bot>/config.json --strategy <Name>`
- Ask Claude to tune via Hyperopt: `freqtrade hyperopt --config <bot>/config.json --strategy <Name> --hyperopt-loss SharpeHyperOptLoss`
- Ask Claude to check logs: `tail -f <bot>/logs/freqtrade.log`
- Ask Claude to deploy: push to main branch → Railway auto-deploys

## Railway Setup
- Each bot is a separate Railway service
- All services share the same Postgres plugin via DATABASE_URL
- Deploy trigger: push to main branch
- Dashboard service: `pnl-dashboard`

## Rules
- **Operator timezone: Australia/Sydney — ALWAYS give Eamon Sydney-local
  times** (corrected 15-Jul evening; the earlier "AEST" note was recorded too
  narrowly). Sydney runs AEST (UTC+10) in winter and AEDT (UTC+11) during
  daylight saving (Oct→Apr) — use whichever is in effect and label it, so
  reported times always match his clock. Never hand him a bare UTC time.
  Fleet INTERNALS stay UTC (ledger rows, `updated`+`ttl_sec` freshness
  contracts, cross-service joins) — this is a reporting/display rule.
- **FREEZE LIFTED 15-Jul evening by user** ("this could be a breakthrough" —
  the evidence-board v2 build). The 21-Jul review + its agenda stand;
  restrict-only actuators / backtest-first / shadow-first remain doctrine
  (they were never freeze rules). Freeze-window exceptions stay logged in
  FLEET_REVIEW_AGENDA_2026-07-21.md §8.
- $1,000 starting balance per bot, NO top-ups
- Paper trading only until 30-day win rate > 55% AND max drawdown < 15%
- Never modify bot logic without backtesting first
- **LIVE BOTS ALWAYS IN AUDIT SCOPE (operator rule, 16-Jul).** Every audit,
  bug-scan, code-review, or security-review — WHATEVER its nominal scope —
  MUST also check the LIVE REAL-MONEY bots in the same pass: Funding Farmer
  (`lighter_funding_bot.py` → `perps-funding-lighter-lighter`) and Tide Rider
  (`lighter_trend_bot.py` → `crypto-trend-daily-lighter`), plus their shared
  real-money surface (`venues/` SafetyRails / notional caps / equity guard,
  `order_usd`, and the `live.*` lever consumers). Why: real money lives there,
  and the 15-Jul cap breach proved a change ELSEWHERE (the growth rail) can
  break the live bots even when the audit isn't "about" them. Never let an
  audit exclude the live bots.
