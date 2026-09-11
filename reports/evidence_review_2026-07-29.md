# Evidence Review — 2026-07-29

_Reviewed 2026-07-29T23:54:02+00:00._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live 453186044772 vs shadow 2b7193562587 — the shadow arm is not a clean control while this holds

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | census now 7523 events across 33 books (threshold 50) |
| disloc:0G | active | census 398 ev / 277bps (alert 394), last event 0.4h ago, 10 entries |
| disloc:APEX | active | census 3833 ev / 313bps (alert 3833), last event 3.5h ago, 382 entries |
| disloc:BIO | active | census 86 ev / 272bps (alert 86), last event 3.9h ago, 1 entries |
| disloc:CHIP | active | census 170 ev / 160bps (alert 169), last event 1.5h ago, 2 entries |
| disloc:EIGEN | active | census 178 ev / 161bps (alert 178), last event 3.5h ago, 1 entries |
| disloc:GMX | active | census 137 ev / 151bps (alert 137), last event 5.4h ago, 1 entries |
| disloc:KAITO | active | census 916 ev / 350bps (alert 911), last event 0.2h ago, 17 entries |
| disloc:NEAR | active | census 20 ev / 150bps (alert 20), last event 5.8h ago, 0 entries |
| disloc:RESOLV | active | census 439 ev / 188bps (alert 439), last event 3.0h ago, 0 entries |
| disloc:SKY | active | census 91 ev / 315bps (alert 91), last event 2.6h ago, 2 entries |
| disloc:STABLE | active | census 299 ev / 396bps (alert 299), last event 2.7h ago, 4 entries |
| disloc:STBL | active | census 187 ev / 245bps (alert 187), last event 3.3h ago, 3 entries |
| disloc:ZORA | active | census 223 ev / 202bps (alert 223), last event 3.9h ago, 3 entries |
| factor-sample:4 | resolved | joined decision+context dataset at 157 closes (58% win), bucket 5 |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=82 (≥10): net $+9.96, WR 34%, t=0.9 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=62, net $+7.94 — by lens [('short', 58, 7.43), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=25, net $-0.18 — by lens [('short-divergence', 13, 1.72), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness.grade — >=30d, >=30 closes, mean>0, t>=2, both halves +, maxDD<15%; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded; drawdown derived from the LEDGER since bot_pnl.extra.max_drawdown is unpopulated): NO new candidate
- ⏳ waiting only on the 30-day window: perps-funding-carry-lshadow (t=2.60, n=82, 18.3d — evidence bars ALL clear, ~11.7d from the window)
- 🚦 fleet-risk light yellow — 15 gross vs long budget 20; 7d DD -0.25%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.094pp (live +0.560% n=48, shadow +0.466% n=56) — no divergence
- 🧬 Farmer arms AGREE: live 128995c2fd76 vs shadow 128995c2fd76
- 🧬 Taker arms DRIFT: live 453186044772 vs shadow 2b7193562587 — the shadow arm is not a clean control while this holds

## Summary

15 alert keys reviewed: 14 active, 1 resolved, 0 stale. No divergence and no drawdown-governor trigger. 12 new-evidence items scanned.
