# Evidence Review — 2026-08-04

_Reviewed 2026-08-04T23:05:56+00:00._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live 5e27c751f5b2 vs shadow 284d218b71c1 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds
- 🧬 REAL MONEY perps-funding-lighter-lighter is BEHIND THE REPO: container f27e50d805af vs repo eb6fe20c21e2 (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 perps-funding-lighter-lshadow is BEHIND THE REPO: container f27e50d805af vs repo eb6fe20c21e2 (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 REAL MONEY lighter-ticket-taker-lighter is BEHIND THE REPO: container 5e27c751f5b2 vs repo 284d218b71c1 (both n=15, so this is code, not file set) — the running container does not carry what has been merged

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | census now 10640 events across 35 books (threshold 50) |
| disloc:0G | active | census 488 ev / 277bps (alert 487), last event 0.2h ago, 48 entries |
| disloc:APEX | active | census 4048 ev / 313bps (alert 4048), last event 2.2h ago, 461 entries |
| disloc:AVAX | active | census 8 ev / 186bps (alert 8), last event 21.5h ago, 2 entries |
| disloc:BIO | active | census 115 ev / 272bps (alert 115), last event 1.1h ago, 17 entries |
| disloc:CHIP | active | census 219 ev / 160bps (alert 219), last event 3.1h ago, 18 entries |
| disloc:EIGEN | active | census 199 ev / 161bps (alert 199), last event 9.1h ago, 10 entries |
| disloc:GMX | active | census 173 ev / 151bps (alert 173), last event 28.3h ago, 19 entries |
| disloc:KAITO | active | census 1464 ev / 350bps (alert 1463), last event 0.4h ago, 328 entries |
| disloc:MU | active | census 183 ev / 158bps (alert 183), last event 94.9h ago, 87 entries |
| disloc:NEAR | active | census 22 ev / 150bps (alert 22), last event 103.4h ago, 0 entries |
| disloc:RESOLV | active | census 488 ev / 188bps (alert 488), last event 9.3h ago, 16 entries |
| disloc:SKHYNIXUSD | active | census 1245 ev / 414bps (alert 1245), last event 2.2h ago, 968 entries |
| disloc:SKY | active | census 101 ev / 315bps (alert 101), last event 9.8h ago, 6 entries |
| disloc:SNDK | active | census 356 ev / 252bps (alert 356), last event 1.1h ago, 211 entries |
| disloc:STABLE | active | census 359 ev / 396bps (alert 359), last event 2.9h ago, 27 entries |
| disloc:STBL | active | census 271 ev / 343bps (alert 271), last event 6.6h ago, 58 entries |
| disloc:WTI | active | census 82 ev / 230bps (alert 82), last event 9.7h ago, 64 entries |
| disloc:ZORA | active | census 250 ev / 202bps (alert 250), last event 3.5h ago, 18 entries |
| factor-sample:13 | resolved | joined decision+context dataset at 438 closes (51% win), bucket 14 |
| factor-sample:14 | active | joined decision+context dataset at 438 closes (51% win), bucket 14 |
| veto:MINIMAX | active | measured slip 21.45bps > 15 (n=6) |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=94 (≥10): net $+17.20, WR 36%, t=1.37 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-breakoutup' at n=17 (≥10): net $+6.94, WR 47%, t=0.64 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=85, net $+8.83 — by lens [('short', 81, 8.32), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=38, net $+0.90 — by lens [('short-divergence', 26, 2.8), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🚦 fleet-risk light yellow — longs 17/20, shorts 3/12 (gross 20); 7d DD -0.04%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.143pp (live +0.495% n=48, shadow +0.353% n=54) — no divergence
- 🧬 Farmer arms AGREE: live f27e50d805af vs shadow f27e50d805af (n=15)
- 🧬 Taker arms DRIFT: live 5e27c751f5b2 vs shadow 284d218b71c1 (both n=15, so this is code, not file set) — the shadow arm is not a clean control while this holds
- 🧬 REAL MONEY perps-funding-lighter-lighter is BEHIND THE REPO: container f27e50d805af vs repo eb6fe20c21e2 (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 perps-funding-lighter-lshadow is BEHIND THE REPO: container f27e50d805af vs repo eb6fe20c21e2 (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 REAL MONEY lighter-ticket-taker-lighter is BEHIND THE REPO: container 5e27c751f5b2 vs repo 284d218b71c1 (both n=15, so this is code, not file set) — the running container does not carry what has been merged
- 🧬 lighter-ticket-taker-lshadow matches the repo tree: 284d218b71c1 (n=15)

## Summary

22 alert keys reviewed: 21 active, 1 resolved, 0 stale. No divergence and no drawdown-governor trigger. 16 new-evidence items scanned.
