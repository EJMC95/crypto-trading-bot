# Daily Evidence Review — 2026-07-18

Reviewed (UTC): auto-run of `daily-evidence-review`. Ground truth = live `bot_state` organs + `bot_pnl` / `paper_trades` ledgers.

**No ⚠️ ACTION items.** Fleet is green, live real money is positive, no divergence or drawdown-governor concern.

## Verdicts (9 distinct alert keys, last 7d — all `info` severity)

| Key | Status | Why |
|---|---|---|
| disloc:KAITO | active | Still dislocating: last event 0.7h ago, census 233→237, max 350bps holds |
| disloc:0G | active | Still dislocating: last 0.2h ago, census 113→119, 258bps |
| disloc:RESOLV | active | Still dislocating: last 0.2h ago, census 188→192, 188bps |
| disloc:ZORA | active | Still dislocating: last 0.2h ago, census 67→69, 202bps |
| disloc:APEX | active | Cooling but recent: last 4.2h ago, census 84→85 (barely moved), 313bps |
| disloc:EIGEN | **stale** | No recurrence in 9.1h, census unchanged at 94 — not currently live |
| disloc:NEAR | **stale** | Last event 26h ago, census stuck at n=11 — dislocation gone, sample thin |
| census:50 | resolved | Review milestone; census now 1215 (>1186) and healthy. Reviewed, no anomaly |
| factor-sample:1 | resolved | Capability milestone (decision+context join at 57 closes). Acknowledged; sample only grows |

All dislocation alerts are Snap Back **thesis-evidence** info items (shadow-only, census-first). The two `stale` verdicts (EIGEN, NEAR) drop from the banner; the five `active` keep corroborating the harvester's premise.

## New evidence surfaced

- **Ticket Taker LIVE lens `short-divergence` crossed n≥10:** tp n=10 (+$12.31) / sl n=4 (−$3.91) = **net +$8.40, WR 71%**. Corroborates the divergence-only live decision. Long lenses remain thin/mixed (breakout/dip/momentum all small n), consistent with "long lenses no forward edge."
- **Funding Farmer LIVE (real money) healthy:** 24 closed, **79% WR, +$3.63** on a ~$65 book, fresh. Per-trade +$0.15 vs shadow twin +$0.26 — both positive, live slightly behind shadow, **no divergence** (live-shadow gap not a concern).
- **Yield Harvester shadow** (`perps-funding-carry-lshadow`) leads P&L at **+$25.64 / 21 closed / 57% WR** — worth watching. But its live (HL-data) arm is retired under Lighter-only; **not** a go-live candidate without proper 30d validation. No action.
- **Fleet 7d drawdown −0.02%**, light **GREEN**, `clip_scale` 1.0 (raw 1.0), long_budget 20 / short 12 — governor untriggered.

## Recommended human action

None. Continue monitoring the Ticket Taker live divergence lens (now n=14) and the tiny live Funding Farmer book; both are net-positive and fresh.

---
*Organs read fresh (ages 1–4 min): `lighter-dislocation-lshadow`, `lighter-market`, `fleet-risk`; `learning-brain` 36 min. `evidence-review` upserted.*
