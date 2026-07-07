## 2026-07-07
- **fleet_risk / regime_oracle (day-zero review catches)**: signal-bus snapshots now historized to bot_state_history (Jul-14 review needs them to judge L3); SUI added to the oracle universe (fleet holds it, oracle didn't cover it).
- **dashboard: UNIFORM CARDS** — every bot card now shows the same information set regardless of publisher quality: `Today P&L (UTC)` under Total (equity-curve delta since UTC midnight where a curve exists, else trades-closed-today), Win/Loss from the union ledger when a bot publishes NULLs (the perps bots), detailed `Last close` (pair · P&L · reason · age) for every bot, and open positions for bots whose book lives in bot_state (perps broker pos incl. mark-based uPnL, funding carries with net accrual). One cached ledger pass (`fetch_ledger_enrich`, 20s TTL); `/pnl.json` gains a per-bot `enrich` object for downstream consumers.
- **cross-bot layers 1-3 (ADVISORY)**: NEW `regime_oracle.py` — one shared per-major daily regime (EMA200+slope direction, ADX 17/11 hysteresis character, HL closed daily candles) published to bot_state `regime-oracle` + append-only `bot_state_history`, fail-safe TTL 2h. NEW `fleet_risk.py` — fleet-wide directional position count vs budgets (20L/12S) -> traffic light in `fleet-risk` incl. pair-pileup detection (the 26-position dip scar), plus scanner exhaust mirrored to `signal-bus` (funding APRs, cross-exchange dislocation, tri-arb depth, pulse mood). Wired into run_all.sh (30m/5m loops) + Dockerfile; `bot_pnl_store` gains `fetch_bot_pnl()` + `save_history()`. Publish-only week one; enforcement (entry veto / sizing) wired from the recorded history after ~7 days.
- **config_v7_momo (crypto-breakout-4h)**: max_open_trades 10→6 — held 10 correlated longs in one bounce with no cap (same risk class rsi-meanrev was capped for Jul-5).
- **RegimeSwitchV2**: per-pair per-4h regime diagnostic log (dir/trend/ADX/close/channels → verdict). Idle 6 days through two blind gate cuts; now the logs say why.
- **listing sniper**: DELISTING-RISK GATE — 'ghost' listings (junk intel AND first venue outside the top-15) skipped entirely; junk elsewhere quarter-stake (was half). Targets the 142/177 `delisted` exits (−$47 lifetime) while keeping the lottery tail reachable.
- **funding_carry_bot**: EXIT REBUILD (0W/28L — every close realized ≈ round-trip fees): decay alone no longer closes; closes only on flip persisting ≥1h, decay AFTER fee payback (net ≥ +$0.10), 14d expiry, or a −2%-of-notional bleed stop. NEW 6h persistence entry filter (|APR| must hold ≥ ENTER_APR for 6h — spike-and-revert funding never passes). hot_since persisted to bot_state.
- **Dockerfile.freqtrade**: COPY bot_learn.py — the learning brain has been dead in deploy since Jul-5 (run_all.sh runs it 2-hourly; the file was never in the image: `can't open file '/freqtrade/bot_learn.py'`).
- **OPTION-B ISOLATION**: family bots (mum/dad/avo-maria/georgia) removed from the freqtrade-bots container; each runs ONLY in its dedicated Railway service via run_all.sh `ONLY_BOT` mode (one bot + FT_POLLER_BOTS-scoped poller). Root cause fixed: the 4 services built from Dockerfile.freqtrade were EACH running all nine bots (fresh $1000, no volume) + a 9-name poller — five pollers race-writing bot_pnl (the Jul 5-7 "counter resets"/equity flapping; Jul-6 trade contamination). Poller _DEFAULT_BOTS back to the 5 originals; stale family comments fixed.

## 2026-07-06
- **funding_carry_bot**: raise ENTER_APR 20%→40%, EXIT_APR 8%→15%, lower MIN_DAY_VOLUME $5M→$2M, extend MAX_HOLD 7→14d — fix fee bleed on fast-decaying carries
- **funding_carry_bot**: raise MAX_POSITIONS 5→8, NOTIONAL $200→$300 — expand reach and earning capacity
- **SwingDipV1**: buy_rsi default 35→42 in strategy code (config key was silently ignored)
- **MomoBreakoutV1**: entry_lookback default 30→20 (shorter Donchian for more frequent signals)
- **RegimeSwitchV2**: ADX trend gate 20→17, chop gate 14→11 (admit weaker trends)

# Changelog

Shared log of every change that affects a running bot, the dashboard, or deploy
behaviour. **Multiple Claude sessions work this repo in parallel** — this file is
how they stay in sync. If your diff touches bot code (`*.py`, `*.sh`, a strategy,
a config) you MUST add a dated entry here in the same commit (a CI check enforces
it). Newest first. Keep entries one line; link the commit if useful.

## 2026-07-05 (later)
- ⚡ Range Raider (`DayTraderV5Gated`): DIAGNOSED the "no trades since rework" — not a bug (logs show a clean load, no populate_indicators error); it was OVER-GATED: every mode needed a pullback AND an uptrend on the same 1h candle, a rare confluence, so it sat idle in this choppy market. FIX = two new regime-covering legs so it operates regularly: `trend_breakout` (ADX≥25 + close>EMA50 + break of 20-bar high — trades RISING phases; grounded in V7's Donchian edge; `confirm_trade_exit` vetoes the range-top sell so breakouts run) and `range_meanrev` (ADX<20 chop + buy the range low, no uptrend requirement — the engine for a choppy market; low-ADX gate is the research-backed guard against knife-catching). Both fee-band gated; range_meanrev half-stake + 2.0×ATR stop. Distinct tags so the brain measures each.

## 2026-07-05
- **NEW bot: `RegimeSwitchV2`** (⚖️ Two-Way Tide) — rebuilt `perps-regime-switch` from the fleet's combined lessons + evidenced public practice (AQR trend-following, Hyperliquid docs). The fleet's only dual-direction engine: 4h Donchian breakout LONG in up-regime / SHORT in down-regime (mirrors the proven V7 PF~1.8 edge to finally profit from a downtrend). Per-pair daily regime (EMA200+slope, ADX gate w/ hysteresis), structure-break exits (let winners run — not trailing/ROI cap), wide ATR disaster stop, inverse-vol sizing, low leverage, correlation-aware global cap, pulse half-stake, Postgres persist. UNVALIDATED (no OHLCV to backtest) — dry-run, robust-by-construction, brain-watched.
- `RegimeSwitchV2`: tuned for more frequency — Donchian 20/10→15/8, ADX gate 22/16→20/14, universe 2→10 liquid majors, max_open 3→6 (still <60% of book). Stays on fee-viable 4h (not 1h churn).
- dashboard: **trendy + descriptive bot names** (emoji + plain "what it does") replacing the technical labels.
- ci: deploy path-filter tracks `RegimeSwitchV[0-9]+.py` so future V-bumps auto-deploy the regime service.
- dashboard: **Total P&L on every bot card** — freqtrade bots publish `pnl_abs=None` (gain is `equity−$1000`), so they showed no P&L line; now computed from equity for all paper bots.
- learning: **brain now covers ALL bots** — `bot_learn.py` read only `bot_trades` (freqtrade); added `bot_pnl_store.fetch_paper_trades()` and merged it so perps + sniper closes (in `paper_trades`) are analysed too. The `reason` field splits into long/short enter_tag + exit_reason, giving the brain long-vs-short expectancy.
- day trader (`DayTraderV5Gated`): widen buy zone 0.22 → 0.37 (enter higher up the pullback for materially more fills; captured move thinner ~0.41×band, still fee-positive). Doubled live bounce eligibility 0→2 pairs.
- day trader (`DayTraderV5Gated`): loosen risk-off band gate 2.2% → 2.0% (more relief-rally pairs, still above fee floor).
- day trader: add third entry mode `bounce_pullback` — trades the relief rally in a risk-off regime when the pair's own 1h EMA50 is above price AND rising; half stake, fast exits. Fixes the "idle in a bounce" gap.
- perps `rsi-meanrev`: global position cap (`MAX_OPEN_POSITIONS=6`, `MAX_NEW_PER_LOOP=2`) gated on a live open count — was holding 14 longs (70% of book) in one correlated dip with no cap.
- ops: schedule the learning brain (`bot_learn.py`) every 2h in the freqtrade supervisor (`run_all.sh`) — it was never scheduled, so it never accumulated the 3 runs needed to promote a lesson to actionable.
- ops: add `CHANGELOG.md` + CI enforcement + `CLAUDE.md` session-coordination rules (this change).

## 2026-07-04
- Dashboard v2: health checks, per-mode (enter_tag) W/L/P&L rows, brain card, BTC regime chip, sparklines, pulse strip.
- sniper: throttle — stake 100→50, max-open 25→10, SL 50%→35%, max-hold 48h→24h, spread gate 500→250bps, depth 3×→5×, vol floor 25k, anti-chase 150%→100%.
- sniper intel (`listing_intel.py`): exchange announcement feeds + CoinGecko footprint, half-stake on junk listings.
- pulse: extend panic sizing to V6/V7 bounces; pulse history records funding APRs.
- brain v1.1: era awareness — hypotheses only from current-strategy-era trades.

## 2026-07-03
- Adaptive dual-mode strategies (V5/V6/V7/V8): BTC-4h 50/200 regime switch (risk-on pullbacks / risk-off sweep-reclaim bounces).
- Durable equity across redeploys: `/freqtrade/persist` volume + Postgres state for perps/sniper; freqtrade auto-deploy unfrozen (persistence makes redeploys safe).
- `perps-funding-carry` bot added (dry-run Hyperliquid funding-rate harvester).
- `market_pulse.py` news/social/funding feed → Postgres; `bot_learn.py` brain added.
- `perps-regime-switch` moved to Donchian-style entries; auto-deploys on its own file changes.

## Before 2026-07-03
See git history. Key milestones: fee-bleed + close fixes for perps (07-01), the
persistent-volume saga (07-01), day-trader fee-gate/trend-gate (07-01/02),
unified pnl-dashboard + Postgres publishing (06-19), multi-bot freqtrade
supervisor (06-18).
