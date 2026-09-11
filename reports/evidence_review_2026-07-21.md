# Daily Evidence Review — 2026-07-21

Reviewed 10:33 UTC (20:33 AEST) — auto-run of `daily-evidence-review`. Ground truth = live `bot_state` organs + `bot_pnl` / `paper_trades` ledgers.

## ⚠️ ACTION (one item)

**impl-shortfall flags ARM-DRIFT on the live Funding Farmer** — live build `d323c0f6` ≠ shadow `d0a671e3`, and live fill slippage is **still unmeasurable: 48 live orders, 0 with slip** (the shadow arm measures fine: 0.95 bps on 74 orders). This is the known frozen-container pattern — the live container predates the fill-telemetry code. A `railway up` of the live funding service (from a clean worktree, per doctrine) would land it. P&L itself is fine (paired-close gap −0.015 pp, no slip streak), so this is telemetry debt, not money bleeding.

Also visible but **not** a fault: the fleet light is **RED** — long book saturated 20/20 (gross 24, effective bets ≈9.5), red ~30% of the last 48 h since crowding began 20-Jul. The long-budget veto is enforcing as designed; dd_7d is 0.0% and clip_scale 1.0 (governor untriggered). The board already surfaced it as `budget-crowding` → agenda item 1 for today's review.

## Verdicts (11 distinct alert keys, last 7d)

| Key | Sev | Status | Why |
|---|---|---|---|
| veto:BOT | action | active | Vetoes still exactly ADA/BOT/SOXL; BOT slip 216.7bps (n=5) — justified |
| disloc:APEX | info | active | Last event <0.1h ago, census 750→770, 313bps, 382 entered |
| disloc:KAITO | info | active | Last 0.5h ago, census 373, 350bps |
| disloc:0G | info | active | Last 0.8h ago, census 173, 258bps |
| disloc:RESOLV | info | active | Last 1.3h ago, census 311, 188bps |
| disloc:ZORA | info | active | Last 3.2h ago, census 124, 202bps |
| disloc:NEAR | info | active | Cooling: 7.2h quiet, census stuck at 14 (thin) — stale if quiet continues |
| disloc:EIGEN | info | **stale** | 17.8h quiet, census unchanged at 107 — not currently live |
| census:50 | info | resolved | Milestone at 2464; census now 2487, healthy — reviewed, no anomaly |
| factor-sample:2 | info | resolved | Superseded by factor-sample:3 |
| factor-sample:3 | info | resolved | Capability milestone at 92 joined closes — acknowledged, sample only grows |

## New evidence surfaced

- **Taker shadow lens `long-divergence` crossed n≥10:** n=12, WR 41.7%, avg −0.44%/trade — weak, consistent with the divergence-**short**-only live doctrine. `short-divergence` shadow n=25, +$1.60, WR 52%.
- **Funding Farmer live healthy:** 34 closed / 76.5% WR / +$6.02 (30d ledger); per-trade $0.177 vs shadow's $0.182 — no live-shadow divergence.
- **No Proving bot newly passes go-live gates.** Best is `perps-funding-lighter-lshadow` (n=59, WR 59.3%) but the book is only ~11d old (fails the 30d age gate) and its live arm already trades. Yield Harvester shadow leads P&L (+$39.58/46) but WR 39% — not a candidate.
- **Immune organ clean:** no sick payloads, no quarantined levers.

## Recommended human action

1. Redeploy the live funding service so fill telemetry finally measures real slippage (48 orders and counting with zero measurements — every Farmer verdict still turns on an assumed slip number).
2. Nothing else — the RED light is the budget veto doing its job; today's 21-Jul review already has budget-crowding on the agenda.

---
*Organs read fresh (ages 1–8 min): `lighter-dislocation-lshadow`, `fleet-risk`, `coin-vetoes`, `impl-shortfall`, `evidence-board`, `fleet-immune`. `evidence-review` upserted 10:33 UTC.*
