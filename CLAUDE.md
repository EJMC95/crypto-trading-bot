# CLAUDE.md — crypto-trading-bot Fleet

## What This Repo Is
Eamon's crypto trading bot fleet — **LIGHTER-FIRST since 2026-07-14** (user
decision: "all services must run off lighter"). Books are $1,000 paper/shadow
each, no top-ups, except the real-money Lighter live rows. Dashboard:
https://pnl-dashboard-production-858c.up.railway.app/

## Fleet Overview (post 14-Jul Kraken retirement; post 17-Jul LIGHTER-ONLY cut)
Every TRADING row below is on Lighter. Four non-Lighter services were code-
guarded off on 17-Jul — see the LIGHTER-ONLY table after the fleet table.

### The trading fleet (Lighter)
| Row | Name | What it is |
|-----|------|------------|
| freqtrade-{mum,dad,avo-maria,georgia}-lshadow | 👩👨🙏🔮 family | TrendMomo/MomoBreakout/SwingDip/DayTraderV5 on Lighter (gate0 `lighter_family_bot.py`, service `family-lighter-shadow`); closes tagged `long-<tag>_<exit>` + brain stake-mults applied at entry (15-Jul) |
| crypto-{intraday-15m,swing-daily,breakout-4h}-lshadow | spot ports | same service, 29-pair whitelist |
| crypto-trend-daily-lshadow | 🌊 Tide Rider | shadow only. Its LIVE row `crypto-trend-daily-lighter` was RETIRED 17-Jul — 🎫 Ticket Taker took the slot on the SAME service/keys/sub-account, so leaving both rows would DOUBLE-COUNT the same $34.67 of real money |
| perps-funding-lighter-lighter / -lshadow | 💸 Funding Farmer | **LIVE** funding harvester + shadow |
| perps-funding-carry-lshadow | 🌾 Yield Harvester | Lighter shadow. Its HL-data arm (`perps-funding-carry`) is RETIRED 17-Jul — see LIGHTER-ONLY below |
| perps-funding-spread-lshadow | ⚖️ Counterweight | funding L/S book |
| lighter-perp-sniper-lshadow | 🎯 Perp Sniper | new-listing sniper |
| lighter-dislocation-lshadow | 🧲 Snap Back | dislocation fader — reference is LIGHTER'S OWN `index_price` since 17-Jul (was Hyperliquid mids) |
| lighter-ticket-taker-lshadow | 🎫 Ticket Taker | **trades Lighter Scout's high-conviction tickets** (breakout/dip/momentum long + divergence long/short); stress veto pauses entries at venue |prem| med ≥15bps; closes tagged `<side>-<lens>_<exit>` so the brain grades each lens |
| equities-regime-lshadow | 📊 Index Rider | stock-perp port (IBKR original RETIRED 14-Jul). 🏆 Stock Leaders (`equities-momentum{,-lshadow}`) RETIRED 17-Jul — maxDD 37-44% vs the 15% go-live gate |
| pm-{albanese,morrison,turnbull,abbott,rudd,gillard}-lshadow | 🏛️ the Parliament | six-layer self-evolving shadow fleet (21-Jul, operator ask; named for the last 8 Australian PMs — the other two are its organs: Keating 🔭 scanners+ML, Howard 🧠 ecosystem brain). `parliament_main.py` in the freqtrade-bots container; SQLite ecosystem DB on the persist volume; consumes scout stress + L2 veto + brain mults; closes tagged per lens; `PARLIAMENT_ENABLED=0` idles it |

### LIGHTER-ONLY (17-Jul, operator: "i only want things running on lighter")
LIGHTER-FIRST governed SERVICES since 14-Jul, but five rows were still TRADING
elsewhere. All stops are CODE GUARDS, not `railway down` (auto-deploy
resurrects stopped services on every git push). Guards print WHY, keep every
ledger, don't break `--selftest`, and are reversible by env var. Rows are in
BOTH `RETIRED_ROWS` (hides) and `LEGACY_BOTS` (prunes).

**Two different mechanisms — don't conflate them:**
- The four BOTS **IDLE** at boot (`while True: sleep`), never `sys.exit`, because
  `restartPolicy=always` turns an exit into a permanent crash-loop (the Trail
  Blazer pattern, `hyperliquid_momo_bot.py` 15-Jul).
- **funding-carry does NOT idle**: it `raise SystemExit`s unless
  `VENUE=lighter_shadow`. It was pinned `VENUE=hl_paper`, exit-looping LOUD (by
  design — not a silent row that just stops moving) until the operator flipped
  the env var. **[22-Jul (ci): DONE — `railway variables --service
  funding-carry` now reads `VENUE=lighter_shadow`; the row runs its Lighter
  shadow arm and no longer exit-loops. No operator action outstanding.]**

| Row (retired) | File | Was trading | Resurrect with |
|---|---|---|---|
| event-listing-sniper 🎯 Launch Sniper | `listing_sniper.py` | spot on ~100 CCXT exchanges | `LISTING_SNIPER_OVERRIDE=run` |
| scanner-cross-exchange-arb 🔀 Gap Scout | `cross_exchange_arb.py` | arb BETWEEN Kraken/Binance/Coinbase | `GAPSCOUT_RETIRED_OVERRIDE=run` |
| scanner-triangular-arb | `triangular_arb.py` | Kraken | `ARB_RETIRED_OVERRIDE=run` |
| perps-rsi-meanrev 🪃 Bounce Catcher | `hyperliquid_perps_bot.py` | Hyperliquid | `PERPS_RETIRED_OVERRIDE=run` |
| perps-funding-carry 🌾 (HL arm only) | `funding_carry_bot.py` | `VENUE=hl_paper` | ✅ DONE 22-Jul — service now `VENUE=lighter_shadow` |

- **The Launch Sniper was the one nobody switched off.** `lighter_perp_sniper.py`
  was built 9-Jul *"to replace the spot sniper (which can't run on a fixed-market
  perps venue)"* — the replacement shipped, the predecessor kept trading ~100
  CEXes for 8 more days behind a row that was never even hidden.
- **Gap Scout could not be MOVED, only stopped** — its trade was CEX↔CEX arb and
  you cannot arb one venue against itself (its own source: "The CEX legs above
  say nothing about Lighter"). Its Lighter-premium job moved to
  `lighter_market_scout` (every liquid book vs its 6-symbol `LIGHTER_WATCH`);
  `fleet_risk` now mirrors the bus premium from bot_state `lighter-market`.
- **Snap Back COULD be moved and was**: `hl_mids()` → Lighter's own
  `index_price`. Measured 17-Jul: the two agree to a median 3.8 bps (vs a 150 bps
  entry gate) but the index residual is systematically tighter — `book/hl_mid − 1`
  was charging Lighter for Hyperliquid's basis.
- Still non-Lighter and DELIBERATELY kept: `compile_market_data.py` (Binance/
  CoinGecko/Kraken prices for the DASHBOARD's display — not a trader).
- Guards bite on each service's NEXT DEPLOY. `hyperliquid_momo_bot.py`
  (Trail Blazer) was already guarded 15-Jul.

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
  fields unchanged — consumer contracts held); floors/streaks UNCHANGED;
  reduce-only until 21-Jul, then TWO-WAY (see `brain-stake-mults` below —
  operator-mandated expand, v3-only, mirror bars); validated by `brain_replay.py`
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
  `FLEET_TUNING_ENACT_LANES` only (shipped default: paper-scanner +
  lighter-scout/-taker/-xp + **lighter-live**, the 15-Jul user-mandated
  live lane; 16-Jul `AUTHOR_LANES` binds each author — board →
  `live.clip_scale` only, judge → `live.funding.*` only; go-live/keys/
  SafetyRails caps stay operator-only forever). Its first
  loop (Gap Scout census quiet 24/48/96h → widen prefilter/book-budget/
  second-tier venues kucoin/gateio/mexc) is INERT since 17-Jul: Gap Scout is
  retired, so `gapscout-census` never refreshes and the ladder fails safe on
  staleness. That loop widened toward MORE CEXes, so under LIGHTER-ONLY it
  SHOULD be inert — the growth rail now has no active author on that lane.
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
  gapscout GOT census activity — DEAD since 17-Jul: Gap Scout is retired, so
  the census never refreshes, `census_ok` is False (`fleet_proprioception.py`
  :595) and `grade_gapscout` never runs; that lane grades nothing;
  live/xp episodes are RECORDED only (the
  judge + fade-watch stay the real-money authority). Per-lever verdicts
  helping/hurting/neutral (floors n≥2 episodes, ±$3; HURTING exists only
  on the taker lane — the one lane with a $ counterfactual; joint stances
  share blame, conservative in the restrict direction). CONSUMED BOTH
  WAYS (16-Jul evening, operator: "implement the expanding side ... so
  the July 21 can review both sides"): RESTRICT — the scout tuner refuses
  to re-assert a HURTING lever (`apply_proprioception`); EXPAND — a
  HELPING taker lever unlocks the tuner's improve-both-halves expansion
  walk before the brain's ruling floor (brain veto stays senior), a
  HELPING diet lever walks one notch deeper, a HELPING gapscout lever
  discounts the board's widen-ladder bars (×0.75, 12h floor). **LIVE LANE
  LEARNS (16-Jul evening, operator mandate)**: live episodes graded
  per-trade vs TWO baselines (the books' own pre-window AND the shadow
  twins, same window; clip vs funding split by author so the board's
  movement is never blamed on the judge's; 'bad' only when worse than
  EVERY baseline by the margin; floors higher than shadow lanes) —
  consumed restrict-first: HURTING live.clip_scale releases the board's
  lever + blocks up-steps; HURTING live.funding.* is the judge's EARLIER
  fade signal (`prop_fade`; the judge stays the only writer); the single
  live earn is the clip ladder's TOP step (1.5) now REQUIRING a measured
  HELPING at 1.25 — fail-CLOSED (dark sense = top out of reach). Board
  surfaces 🦾 items (hurting=warn, helping=expand); immune scans the
  payload. Fail-safe both ways on shadow lanes: a dark organ restricts
  nothing AND earns nothing. **CONSUMER SUPPORT (16-Jul late)**: verdicts
  are a first-class bus signal — `fleet_bus.lever_outcome(lever)` is the
  supported accessor for any strategy/bot (standard fail-safe contract),
  `/bus.json` serves the payload + history off-Railway, and the incubator
  consumes it (skips proposing a funding gene whose live lever is
  currently graded hurting — a 7-day judge slot isn't spent re-testing a
  knob the live lane just measured bad). **REAL-MONEY BOTS CONSUME TOO
  (16-Jul late)**: `fleet_tuning.get_lever` reverts a HURTING live-lane
  lever to the operator's env default AT THE CONSUMER, every loop (the
  immune-quarantine central-hook pattern; covers the funding bot's
  `apply_levers` + both live bots' clip via venues) — a measured-bad
  lever stops steering real money immediately instead of waiting out the
  board/judge cycle or the lever TTL; live-lane only (shadow lanes keep
  TTL semantics), fail-safe open, restrict-only by construction. **[23-Jul
  audit CORRECTION: the clip HOOK is wired at the consumer, but
  `live.clip_scale` can NEVER actually receive a `hurting` verdict —
  `fleet_proprioception.grade_live` returns `recorded` for the `live-clip`
  group because the per-trade metric is invariant to clip size — so this
  auto-revert only ever FIRES for `live.funding.*`. The clip's real
  protections are the board's DOWN reflex + lever TTL + the SafetyRails cap.
  "covers ... both live bots' clip" describes the plumbing, not a revert
  that can fire.]** Review grades both sides — agenda item 12.
  → bot_state `fleet-proprioception`
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
  auto-flips without review). ~~ADVISORY: zero consumers~~ **[22-Jul: THE
  "ZERO CONSUMERS" CLAIM IS STALE — but it steers a SHADOW book, NOT real
  money.** `fleet-tuning` carries `taker.momo_chg=6.0` and `taker.brk_range=0.97`
  on the `lighter-taker` lane, both stamped
  `reason: "organ-proposal:event-sentinel (replay-gated at this tuner)"`. The
  sentinel proposes; the scout tuner replay-gates and enacts. That is a real
  consumer path — so "advisory, zero consumers" was stale. BUT `lighter-taker`
  is the **$1k SHADOW** lane (`lighter_ticket_taker.py:272` "NOT ON REAL
  MONEY"; only `live.*` levers may steer the live book), so an earlier
  "steering the LIVE taker" note here over-corrected — verified 22-Jul (ci).
  The sentinel has actuator reach into a shadow book; it does not touch real
  money.] Tuning: `evsent.*` levers, lane
  `event-sentinel`. → bot_state `event-sentinel` (+ `-state`)
- `parliament_main.py` 🏛️ — the Parliament's supervisor (21-Jul): six asyncio
  layers in one process — `parliament/` data (Lighter REST+ws ONLY),
  Keating's 10 scanners + 5-model prequential ML ensemble, the six PM shadow
  books, six replay-gated auto-reverting tuners (the scout-tuner doctrine:
  bounds cage, TTL, both-halves floors, hurting-refusal), Howard's brain →
  bot_state `parliament` + `parliament-tuning`. Redis mirror optional
  (`REDIS_URL`); in-process bus is primary. Shadow-only forever until the
  standard go-live gate.
- `fleet_proposals.py` 🗳️ — the organs' PROPOSAL channel to the tuners
  (21-Jul, operator: "the organs need more ability to implement changes to
  forward onto the tuners to act on"). Any organ proposes a bounded change
  to a REGISTERED lever → `tuning-proposals` (locked multi-author merge,
  per-proposal expiry, clamped at write AND read, declared
  direction restrict|expand). Proposals NEVER enact: the scout tuner gates
  each through ITS OWN replay (restrict = not-worse both halves; expand =
  the full winner bar, brain veto senior, ≤3/cycle, provenance
  `organ-proposal:<author>`), and the judge treats a fresh restrict proposal
  on a promoted live lever as a third release path (`proposal_fade`,
  restrict-only; judge stays the only live.funding.* writer). First
  proposers: event sentinel (risk-off crouch / graded-playbook expand),
  impl-shortfall (sustained slip → live.funding.enter_apr restrict),
  respiration (confirmed hypoxia → crouch). The sentinel's own
  `event-sentinel` lane is now enactable + author-bound (detection
  sensitivity only — it was registered but UNREACHABLE since 16-Jul).
  Fail-safe: dark channel proposes nothing, consumers ignore stale/junk.
  → bot_state `tuning-proposals` (+ /bus.json, 🗳️ Autonomy-card row)
- `regime_oracle.py`, `market_pulse.py` (history appends every 30 min, 15-Jul),
  `cleanup_legacy_bots.py` (boot prune of retired rows)

### RETIRED (rows hidden + pruned; ledgers kept)
Kraken paper 8 (spot 4 + family 4, 14-Jul user cut — Kraken/laptop
processes are operator-stopped), equities-momentum-alpaca +
equities-regime-ibkr (14-Jul), Trail Blazer, Bounce Catcher, Two-Way Tide,
Loop Scout, trendmomo-4h (12/13-Jul).

**17-Jul LIGHTER-ONLY cut** (operator: "i only want things running on lighter"):
`event-listing-sniper` (🎯 Launch Sniper), `scanner-cross-exchange-arb`
(🔀 Gap Scout), `perps-funding-carry` (🌾 Yield Harvester's HL-DATA arm — its
`-lshadow` twin CONTINUES and is deliberately NOT retired). `scanner-triangular-arb`
and `perps-rsi-meanrev` were already-hidden rows whose SERVICES kept running;
they now have guards too. Per-row stop mechanism + resurrect switch: see the
LIGHTER-ONLY table above — not restated here.

**Also 17-Jul**: `crypto-trend-daily-lighter` (🌊 Tide Rider's LIVE row — 🎫
Ticket Taker took the same service/keys/sub-account; retiring it is REQUIRED,
not cosmetic: both rows reported the same $34.67 and the fleet total
double-counted real money), `equities-momentum{,-lshadow}` (🏆 Stock Leaders —
maxDD 37-44% vs the 15% go-live gate).

A retirement needs BOTH halves: `RETIRED_ROWS` in pnl_dashboard.py (hides the
card) AND `LEGACY_BOTS` in cleanup_legacy_bots.py (prunes the frozen row).
Doing one hides your own omission.

### Read-only endpoints (no auth)
`/pnl.json` `/trades.json` (`?source=paper` for the paper_trades ledger)
`/bus.json` (risk light + signal bus + brain keys + lighter-market +
fleet-proprioception, `?hours=` history) `/pulse.json` `/disloc.json`
`/watchdog.json`

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
- `parliament_main.py` + `parliament/` — 🏛️ the six-layer PM shadow fleet
  (see intelligence layer); ecosystem DB at `/freqtrade/persist/parliament.db`
- `venues/safety.py` — SafetyRails (kill switch, notional caps, daily-loss halt)
  **+ `open_notional()`**: the fleet's ONE answer to "how much is really
  deployed?" — sum each held position at ITS OWN entry clip, never
  `count * current_clip` (that estimate breaches the cap when the growth rail
  moves the clip). Imported by BOTH live bots + the taker + the sniper.
- `cross_exchange_arb.py` — Gap Scout, **RETIRED 17-Jul** (CEX↔CEX arb, no
  Lighter leg); idles at boot
- `funding_carry_bot.py` — Yield Harvester; `lighter_shadow` ONLY since 17-Jul
  (the HL-data arm is retired; the hedge-less refusal is unchanged and senior)
- `user_data/` — Freqtrade strategies/configs (dormant post-Kraken; the
  gate0 family bot re-expresses them on Lighter)
- gate0 branch (`claude/lighter-gate0`) — the Lighter runtime (venues/,
  ShadowBroker, lighter_family_bot.py); its services deploy from there

## Cross-Bot Intelligence (bot_state keys — since 2026-07-14 CONSUMED, not just published)
- `brain-stake-mults` — bot_learn's L4 per-(bot, enter_tag) stake
  multipliers. **TWO-WAY since 21-Jul (operator: "brain needs to be able to
  widen too")** — reduce (0.5/0.75, floors n≥30 era trades / 3 consecutive
  runs, unchanged since 14-Jul) AND expand (1.25/1.5 on the v3 MIRROR bars:
  Wilson LOWER bound, t ≥ +2.0/+2.5, full n floor only, no family-praise
  inheritance, no urgent fast-path — `brain_stats.EXP_*`; same 3-run streak
  gate). Expand is v3-ONLY (`BRAIN_MULT_ENGINE=v2` zeroes it) with its own
  kill switch `BRAIN_MULT_EXPAND=off`; consumers clamp [0.5, **1.5**]
  (`fleet_bus.MULT_CEIL` — was 1.0; deliberate documented-contract scope
  expansion, CHANGELOG (bh)). Payload stamps `mode: two-way|reduce-only`.
  Consumers: `lighter_family_bot.py` at entry (keyed `<bot_id>` +
  `long-<tag hyphenated>`, 15-Jul) and the freqtrade strategies'
  `custom_stake_amount` — both via `fleet_bus.py`; SHADOW books only, no
  live bot reads mults.
- `fleet-risk` — L2 traffic light, mode **enforce**: strategies veto NEW long
  entries at long-budget (20). Kill switch: `FLEET_RISK_MODE=advisory`.
- `signal-bus`, `regime-oracle`, `market-pulse` — published context (funding
  APRs, venue premium, per-major regime, news mood). Only market-pulse.panic +
  the two keys above are consumed.
  **`listing-intel` is DARK since 17-Jul**: its ONLY publisher was
  `listing_sniper.py:1148`, which now idles behind the LIGHTER-ONLY guard
  (`listing_intel.py` is a pure library and publishes nothing). The key will
  simply go stale — consumers fail-safe on absence, per the bus contract.
  [17-Jul] The bus's Lighter premium (`lighter_prem_bps`,
  `lighter_venue_stress_bps`) now comes from the market scout's
  `lighter-market` — every liquid book, and the SAME number the Ticket Taker's
  stress veto reads — instead of retired Gap Scout's 6-symbol watchlist.
  DROPPED with their scanners: `xexchange_dislocation_pct`,
  `tri_arb_best_depth_pct` (CEX gauges; nothing outside fleet_risk read them).
  `fleet_risk.state_fresh()` honours a bot_state payload's own `updated`+
  `ttl_sec` and fails CLOSED (`row_fresh()` is for bot_pnl rows only).
- `fleet-tuning` — the growth rail's lever payload (authors: evidence board
  + scout tuner, MERGED writes with per-lever expiry; `fleet_tuning.py`
  registry clamps; consumers: Lighter Scout, Ticket Taker — Gap Scout was one
  until it retired 17-Jul, so the `paper-scanner` lane now has no consumer).
  Lanes: paper-scanner (INERT — Gap Scout retired) / lighter-scout /
  lighter-taker / lighter-xp (zero
  real money) + lighter-live (`live.clip_scale` + the judge's PROMOTED
  `live.funding.*` — see growth rail + experiment judge above).
  `gapscout-census` — Gap Scout's epoch-2 episode census; STALE FOREVER since
  17-Jul (bot retired), board's `quiet_hours` ladder fails safe on it. `scout-tuner` — the tuner's cycle log + enactments.
  `fleet-proprioception` — per-lever enactment outcome grades (episodes +
  helping/hurting verdicts). Consumers: scout tuner (hurting-skip +
  helping-walk), board (🦾 items + live clip gates + gapscout ladder
  discount), judge (early fade), incubator (hurting-gene skip), anything
  else via `fleet_bus.lever_outcome` / `/bus.json`.
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
  "extra": {...},                  # optional — JSON-able context dict
}
```
**[2026-07-28 doc-truth]** That is the COMPLETE accepted set — `publish()`
takes exactly `(bot, status, equity, pnl_abs, pnl_pct, open_trades,
closed_trades, wins, losses, extra, pnl_daily)` and has no `**kwargs`. This
block used to also list `pnl_weekly/pnl_monthly/max_drawdown/best_trade/
worst_trade`; a bot following that doc raised `TypeError` AT THE CALL SITE
in its trading loop (outside publish's never-raise guard). If those fields
are ever wanted, extend `publish()` + `ALTER TABLE` first, then this doc.

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
- Ask Claude to deploy: **a push is NOT a deploy** — see Railway Setup below.

## Railway Setup
- Each bot is a separate Railway service
- All services share the same Postgres plugin via DATABASE_URL
- **DEPLOY TRIGGER — "push to main → Railway auto-deploys" is FALSE, and was
  false for both real-money bots (MEASURED 17-Jul, commit 259e3b4: not one
  of the 12 services is git-connected — `railway variables` returns zero
  `RAILWAY_GIT_*` keys on every one).** The ONLY automated path is
  `.github/workflows/railway-redeploy.yml`, which runs `railway up` for a
  **hardcoded `paths:` list** covering exactly three services:
  freqtrade-bots (`user_data/**`, `Dockerfile.freqtrade`, `run_all.sh`),
  pnl-dashboard (`pnl_dashboard.py`, `report_emailer.py`,
  `compile_market_data.py`, `Dockerfile.dashboard`), funding-carry
  (`funding_carry_bot.py`, `Dockerfile.funding`), plus shared
  `bot_pnl_store.py` / `freqtrade_pnl_poller.py` / `market_pulse.py`.
  **Anything not on that list ships only when a human runs `railway up`** —
  `fleet_tuning`, `funding_basis`, and the LIVE Funding Farmer
  (`lighter_funding_bot.py`). The RETIRED HL funding-carry arm auto-deploys;
  the LIVE Funding Farmer does not.
  **[2026-07-22 CORRECTION — this paragraph was WRONG about two of them.]** The
  `paths:` filter DOES carry `lighter_ticket_taker.py`, `lighter_ticket_replay.py`,
  `venues/**` and most of the intelligence layer (`lighter_market_scout`,
  `lighter_scout_tuner`, `fleet_*`, `bot_learn`, `brain_stats`, `evidence_board`,
  `experiment_judge`, `strategy_incubator`, `event_sentinel`, `regime_oracle`,
  `implementation_shortfall`, `parliament/`) — verified against the workflow file,
  not inferred. What is manual is the *service*, not the *file*: those paths
  deploy **freqtrade-bots** (where the SHADOW taker and the organs run), while the
  two REAL-MONEY services — `trail-blazer-live` (= the Farmer; service names lie)
  and `tide-rider-lighter-live` (= the Ticket Taker) — are on NO auto path and
  need an explicit dispatch:
  `gh workflow run 305025607 -f services="trail-blazer-live,tide-rider-lighter-live"`
  (address it by workflow ID — the filename form did not resolve in this repo).
  Then MARKER-GREP both containers; a green run has never implied a container took it.
  **[2026-07-29 CORRECTION — the auto-deploy surface has since GROWN in three
  ways this paragraph pre-dates; verified against the workflow at HEAD.]**
  (1) The workflow auto-deploys **FOUR** services, not three — `market-context`
  gained a deploy rule 17-Jul — and the pnl-dashboard path list also carries
  `fleet_watchdog_svc.py`. (2) `fleet_tuning.py`, `funding_basis.py` and
  `lighter_funding_bot.py` are ALL on `paths:` now — the "ships only when a
  human runs `railway up`" list above is empty today. (3) The two REAL-MONEY
  services are no longer dispatch-only: since 24/25-Jul a push whose commit
  message carries **`[deploy-live-taker]` / `[deploy-live-farmer]` /
  `[deploy-live]`** AND touches that live image's own files auto-deploys that
  live service from clean main (no marker → shadow only, exactly as before).
  The dispatch command above still works and remains the no-marker route.
  Verify a live deploy landed by the bot_pnl `extra.build` stamp: it is a
  content hash — recompute locally with
  `python3 -c "import bot_pnl_store as b; print(b.build_compute('<entry>.py'))"`
  and compare to the row (how the 29-Jul audit proved both live containers
  ran 633e8a1 without container access). `audit_deploy_coverage` now also
  cross-checks the live marker greps against `paths:` (the 28-Jul grep
  widening added files the paths: block didn't carry — a marker push touching
  only those deployed nothing, invisibly to the then-guard).
  **What it cost:** six fill-telemetry commits landed 04:27→10:52 UTC 17-Jul;
  the funding container booted 04:34 and picked up NONE of them — 58 real
  orders, 0 measured fills. The code was right and was never running. This is
  the mechanism behind every "frozen service" incident.
  Check before you claim a fix is live: `scripts/audit_deploy_coverage.py`
  (does a path have ANY deploy route?), then marker-grep the RUNNING
  container — the only proof a deploy landed ([[railway-cli-frozen-services]]).
  Deploy live from a CLEAN worktree: `railway up` uploads your DESK, WIP and
  all ([[deploy-live-from-a-clean-worktree]]).
- Dashboard service: `pnl-dashboard`

## Rules
- **BORN-DARK GUARD (17-Jul, after THREE incidents: `fleet_bus` 15-Jul,
  `event_sentinel` 16-Jul, `brain_stats` 17-Jul).** Adding a module, an
  import to shipped code, or a COPY means running
  `python3 scripts/audit_image_imports.py` before you ship. It reconstructs
  each image's real file set (multi-source COPY, `COPY venues/`, `COPY . .`)
  and walks the imports of every python file in it — **including inside
  COPY'd packages** (`venues/`, `user_data/strategies/`, where the
  real-money surface lives) — plus every run path (CMD, any COPY'd `*.sh`,
  and railway*.toml `startCommand`). Verified against all three incidents.
  Why it matters: each was SILENT, because a `try/except ImportError` guard
  — correct for optional organs — turns a missing file into a degraded
  fallback instead of a crash. **A deliberate omission is DECLARED in
  `BORN_DARK_OK` with a reason; silence is not an option.** Runtime
  backstop: `fleet_immune` pages when `brain-vitals` reports engine=v2
  without a deliberate `BRAIN_MULT_ENGINE=v2` (both parse that env
  identically — they must, or a typo'd kill switch silences the detector).
  **IN CI since `ce446c7`** — the guard and its `--selftest` run on every
  push/PR from `changelog-check.yml`, alongside `audit_sdk_pin`. (This line
  said "NOT wired into CI, the PAT lacks workflow scope — standing
  follow-up" for a day AFTER it was wired; verified 17-Jul (ad). A doc that
  tells the next reader to go re-do a done job is the same rot the guard
  exists to catch.) Still run it locally before you ship: CI tells you after
  the push, and the push is not what deploys anyway (see Railway Setup).
  **Verify a NEW module by its OWN published output, never by "it shipped"**
  — and never from git (see [[railway-cli-frozen-services]]: marker-grep the
  RUNNING container).
- **FLEET_RISK_MODE=advisory is SENIOR and now releases BOTH actuators
  (17-Jul).** It was documented as "every consumer goes neutral" but only the
  long-budget veto consumers ever checked mode — the 7d drawdown governor's
  `clip_scale` kept biting through a thrown kill switch. `fleet_risk` now
  publishes `clip_scale=1.0` in advisory mode (raw value kept as
  `clip_scale_raw`). Deliberate scope expansion of a documented contract:
  throwing the switch to stop the veto ALSO restores full clip size. Inert by
  default (mode=enforce) and it reaches only shadow consumers (family/taker);
  the live bots size off the separate `live.clip_scale` lever.
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
- **BACKTEST ON LIGHTER ONLY — the venue we trade is the venue we measure
  (operator rule, 17-Jul: "Lighter needs to be the only exchange backtests run
  on as we run on lighter").** LIGHTER-FIRST governed SERVICES since 14-Jul;
  this extends it to EVIDENCE. A backtest on another venue's data is not
  validation of a Lighter bot — it is a hypothesis about Lighter.
  WHY, measured 17-Jul: **every funding backtest in this repo loads
  HYPERLIQUID** (`backtest_directional_funding` / `_scanner` / `_carry_hedged` /
  `_funding` / `_regime` / `_leverage` / `_persistence` / `study_funding_settlement`),
  and the Tide Rider set loads HL **+ Binance** (`backtest_tide_rider` /
  `_perp` / `_scanner`). **Both LIVE bots' go-live justifications are on that
  list**, and it has already cost real money twice:
    * Funding Farmer — `FUNDING_ENTER_APR=0.40` was fitted on HL (hourly, so
      `24*365` is CORRECT there) and ported to Lighter as a bare constant.
      Lighter quotes per 8h, so the LIVE gate silently admitted at **5% TRUE**
      for as long as it has run, on a bar no backtest ever supported.
    * Tide Rider — its header's "~13pp funding drag / +52% spot -> +40% perp"
      is **Hyperliquid's funding**, from a script whose own line 16 claims it
      shows "what Lighter would actually deliver".
  THE RULE: a Lighter bot's evidence comes from Lighter's own tape. If a study
  must be cross-venue (e.g. the HL-vs-Lighter equivalence study), that is a
  DECLARED exception with a reason — the same pattern as `BORN_DARK_OK` /
  `VENUE_PURITY_OK`. `scripts/audit_venue_purity.py` currently SKIPS `scripts/`
  (`_SKIP_DIRS`, "research tools") — extending it to backtests is what makes
  this rule enforced rather than merely written; an unenforced rule rots.
  THE COST, state it honestly: **Lighter's tape is ~438d** (settled hourly
  funding pages backward via `/api/v1/fundings` with `end_timestamp=oldest-3600`;
  candles page 500 bars). So Lighter-only means **~14 months, not 2.7 years** —
  Tide Rider's 2.7yr window is NOT reproducible on Lighter and never will be.
  That is a real loss of window, and it is the price of measuring the venue that
  holds the money. Short-and-honest beats long-and-borrowed: a 438d Lighter
  result is evidence; a 2.7yr HL result about a Lighter bot is an assumption
  wearing a number. Retired-bot backtests (Kraken originals) are HISTORY — do
  not re-run them; they justify nothing that still trades.
- **REGIME-COVERAGE CAVEAT (21-Jul review, item 18 — adopted D5): "positive in
  both halves" is necessary but NOT SUFFICIENT for DIRECTIONAL strategies.**
  Lighter's whole 438d tape is one falling regime (BTC −32.9%; the family
  regime gate reads risk-off 61.5% of bars; BOTH halves fall), so a
  directional short passes both halves BY CONSTRUCTION — the bar is satisfied
  by the drift, not the edge. A directional validation must STATE which
  regimes its window contains, and a one-regime pass is a pass in that regime
  only. More Lighter tape does not fix this; only a different regime does —
  the venue's ~27 non-crypto books (SPY +8.1%, QQQ +12.2%, WTI +23.0% over
  the same falling-BTC window) are the on-venue source. PREREQUISITE before
  any non-crypto directional widening: a PER-ASSET regime gate — never BTC's
  EMA for SPY/XAU/WTI (measured: btc_regime_up read risk-off 61.5% through
  SPY's bull run; the brain's Georgia diagnosis — 100% of losses opened in
  oracle risk-off — corroborates from independent data). Build order: oracle
  per-asset coverage → the gate consumes it → only then the universe.
  **[2026-07-30: step 2 WIRED (operator call, "per asset have consumer").**
  `fleet_bus.oracle_asset_regimes()` → `lighter_family_bot.regime_inputs_for()`:
  crypto pairs byte-identical on the validated BTC gates; a NON-CRYPTO pair
  rides its OWN oracle verdict, fail-CLOSED (ungraded book / dark-or-stale
  oracle ⇒ no entry — never BTC's gate; classification is STATIC so a dark
  oracle cannot re-route SPY to BTC; kill switch `FAMILY_PER_ASSET_REGIME=off`
  closes non-crypto entirely, never re-routes). INERT until step 3: no family
  universe lists a non-crypto symbol, and the selftest asserts exactly that.
  The universe widening stays a review decision — evidence in
  `REGIME_GATE_PER_ASSET_2026-07-30.md` (TSLA-protective / metals-mildly-costly
  / SPY-QQQ ungraded to ~mid-Aug), which re-runs at SPY/QQQ graduation.]
- **LIVE BOTS ALWAYS IN AUDIT SCOPE (operator rule, 16-Jul).** Every audit,
  bug-scan, code-review, or security-review — WHATEVER its nominal scope —
  MUST also check the LIVE REAL-MONEY bots in the same pass: Funding Farmer
  (`lighter_funding_bot.py` → `perps-funding-lighter-lighter`) and the **Ticket
  Taker** (`lighter_ticket_taker.py` → `lighter-ticket-taker-lighter`), plus
  their shared real-money surface (`venues/` SafetyRails / notional caps /
  equity guard, `order_usd`, and the `live.*` lever consumers). Why: real money
  lives there, and the 15-Jul cap breach proved a change ELSEWHERE (the growth
  rail) can break the live bots even when the audit isn't "about" them. Never
  let an audit exclude the live bots. **[22-Jul (ci) CORRECTION: this rule
  named the RETIRED Tide Rider (`lighter_trend_bot.py` →
  `crypto-trend-daily-lighter`) — which the 🎫 Ticket Taker replaced on the
  same slot 17-Jul. A standing audit rule that names a retired bot sends every
  future audit to check the wrong file; the live pair is Farmer + Ticket
  Taker.]**


## Doctrine: Claude is the judgment layer, never the polling layer (added 28-Jul-2026)

Context: 14–24 Jul 2026, Code sessions armed 48 `send_later` self-check-in
wakeups (27 on 23-Jul alone; one PR-#91 chain re-arming ~hourly into a
persistent session). Each firing replayed a full transcript to ask a yes/no
question GitHub answers for free. Est. ~1.35M tokens in one day — ~40x the
entire weekly admin load. All 48 spent triggers were deleted 28-Jul.

**P1 — Never arm a wakeup chain to watch external state.** No `send_later`,
`ScheduleWakeup`, or self-re-arming reminder to poll CI status, PR
mergeability, deploy receipts, `/bus.json` / `/pnl.json` field changes, or
container health. These are push-capable sources; wire the push instead.

**P2 — The replacement is an Action, not a shorter interval.** CI/PR state →
`ci-notify.yml` (posts transitions on the PR). Service state → extend
`fleet-watchdog.yml` (probing pnl.json; HOURLY since 28-Jul — the billing
lockout retired both the old ~30-min cadence and the "$0" claim; the
dashboard's in-service 5-min watchdog is the fine-grained layer).
If it cannot be pushed, it is not important enough to poll.

**P3 — A check-in chain may re-arm at most TWICE, then it must stop.** If a
genuine wait is unavoidable (a human decision, a venue with no webhook), arm
at most two check-ins, then report last known state and stop. Never re-arm
silently. Never re-arm "until merged". Three firings = should have been an
Action.

**P4 — Never poll into a persistent session.** A persistent-session wakeup
replays the whole transcript first, so cost grows with session age. If a
wakeup is truly required, start a fresh session with a self-contained prompt.

**P5 — Clean up after yourself.** Spent one-shot triggers inflate every later
`list_triggers` read (28-Jul: one call returned 252,507 chars ≈ 63k tokens
because 48 dead triggers still carried full prompt payloads). Delete a
chain's triggers when the chain ends. The Weekly Admin task now self-audits
the scheduler weekly and deletes >10 leftovers.

**P6 — Escalate to the operator instead of waiting.** When blocked on Eamon's
decision, say so once and stop. He would rather answer in the morning than
pay for the wait.
