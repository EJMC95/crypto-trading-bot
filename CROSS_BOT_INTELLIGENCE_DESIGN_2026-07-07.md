# Cross-Bot Intelligence — Design for 18 Bots That Teach Each Other
*7 July 2026 · dry-run fleet · design doc, nothing deployed*

Your question: **given 18 bots all doing different things, can they help one another trade better using their trade data?** Yes — and the fleet has quietly grown most of the organs it needs. What's missing is the wiring. One boundary first: "help make live trades" here means *better decisions on the paper fleet*; nothing goes live and no funds move without your explicit go-live, per your standing rule.

---

## 1. What already exists (you're closer than you think)

The fleet already has four shared organs: **market-pulse** (news/social/funding mood → `bot_state`, bots already half-stake on panic), the **learning brain** (reads every ledger, promotes lessons after 3 confirmations — dead since Jul-5, revived today), the **durable ledger** (352 trades + 285 fills + equity history — the raw material), and **bot_state** (a key-value bus every bot can read/write). The regime-oracle spec you commissioned on Jul-1 (`regime-oracle-spec.md`) designed the fifth organ but it was never built.

## 2. The five layers, cheapest first

**L1 — Shared regime oracle (one truth about the tape).**
One small service computes, per pair per day: direction (EMA200 + EMA50 slope), character (ADX trending/chop), and publishes `regime.json` to `bot_state`. Every bot conditions on it: spot bots size down in down-regimes (they already gate themselves, but each computes its own view — 9 private regime opinions where one shared one would do), perps engines get direction permission, funding-carry gets a "risk-on/off" context. *Evidence:* time-series momentum (Moskowitz–Ooi–Pedersen 2012) and a century of trend data (AQR) say regime direction is the single most portable signal; today's live readings (8/10 majors in a short regime) show exactly what the fleet should all agree on. *Failure mode:* oracle goes stale → bots must fail-safe to their own gates (the spec already mandates CASH/FLAT fallback).

**L2 — Fleet risk manager (stop the correlated pileup).**
The scar: on one July dip, rsi-meanrev held 14 longs, breakout-4h 10, trendmomo 2 — 26 positions, one beta. Each bot was inside its own rules; the *fleet* was massively concentrated. A tiny risk service reads open positions from `bot_pnl` every minute and publishes `risk_state`: total long/short beta-weighted exposure vs a fleet budget, plus a traffic light. Bots honor it in `confirm_trade_entry` (freqtrade) or before entry loops (perps bots): red = no NEW same-direction entries. *Evidence:* this is portfolio-level vol targeting / "effective number of bets" (López de Prado) — the highest-value risk control institutions run and individual bots cannot see. *Failure mode:* over-throttling the winners; start advisory (log-only) for a week, then enforce.

**L3 — Signal bus (scanners feed traders).**
The scanners already produce tradeable context nobody consumes: funding APRs (pulse has them), cross-exchange dislocation width (a volatility/stress signal), listing-sniper's intel classifications, triangular-arb's spread/depth telemetry. Publish each as a `bot_state` key with a timestamp; traders read them as *filters*: perps bots skip entries when funding is extreme against them (paying 100%+ APR to hold a long is a measurable headwind), breakout bots treat sudden arb-spread widening as a vol-regime warning. *Evidence:* funding as a positioning/sentiment signal is one of the best-documented effects in perp markets. *Cost:* trivial — the data already exists in-process.

**L4 — Meta-labeling (the brain sizes what strategies signal).**
This is the highest-leverage idea in the literature for exactly your setup. Keep every bot's entry logic; add a second layer that decides *how much* (or whether) to stake each signal, learned from the ledger: per `enter_tag` expectancy, win rate, regime interaction. The brain already computes per-mode W/L/P&L; the step up is writing per-tag stake multipliers (0.25×–1.5×) to `bot_state` that strategies read at entry. Promote a multiplier only after ≥30 trades on that tag or 3 independent brain runs agree (the brain's existing rule). *Evidence:* meta-labeling, López de Prado, "Advances in Financial Machine Learning" — separating signal generation from bet sizing measurably improves precision without touching the underlying strategy. *Failure mode:* tiny samples masquerading as edge — the trade-count floor is non-negotiable.

**L5 — Meta-allocator (capital rotates toward live edge).**
Weekly, reweight each bot's paper stake by rolling ledger performance (PF/Sharpe with decay), floor 0.5× / cap 1.5×, ±20% max step, never to zero (a benched bot stops learning). This is the "fleet as one app" step — the portfolio becomes the product. *Evidence:* online portfolio selection / bandit allocation (Cover's universal portfolios; EXP3), but the honest caveat dominates: with 10–50 trades per bot, allocation noise can exceed signal — hence slow steps, floors, and shrinkage toward equal weight. *This layer last, only after L1–L4 have months of data.*

## 3. What could go wrong (read before building)

Double-counting: if the oracle, the risk manager, and meta-labeling all penalize the same bear regime, a bot gets triple-punished for one condition — assign each layer ONE job (L1 direction, L2 concentration, L4 per-signal quality) and keep them orthogonal. Overfitting the meta-layer: 18 bots × small samples = a noise farm; every promotion needs the trade-count floor. Staleness: every shared key carries a timestamp and consumers fail-safe to local behavior. And the governance rule stays absolute: dry-run only; the meta-layers reallocate paper, never real funds.

## 4. Build path (each phase measurable from the ledger)

- **Phase 0 — now (done today):** brain revived; its lessons accumulate again. Watch `learning-brain` in `bot_state`.
- **Phase 1 — regime oracle** (~1 session): build from the Jul-1 spec; publish-only for a week (bots log what they *would* have done differently), then wire spot-bot sizing to it.
- **Phase 2 — fleet risk manager** (~1 session): advisory traffic-light for a week → then `confirm_trade_entry` enforcement. This one prevents repeat of the 26-position dip pileup.
- **Phase 3 — signal bus** (small): funding + dislocation filters into perps/breakout entries, tagged so the brain grades the filter itself.
- **Phase 4 — meta-labeling multipliers** (after ≥30 trades/tag accumulate): brain writes, strategies read, floors enforced.
- **Phase 5 — weekly meta-allocator** (months out): only once L1–L4 have a track record to allocate on.

The through-line: **shared context first, shared risk second, shared learning third, shared capital last** — each layer earns the next with ledger evidence.
