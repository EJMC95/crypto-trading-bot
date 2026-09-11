# Evidence Review — 2026-08-16

_Reviewed 2026-08-16 09:36 AEST (Sydney) · 2026-08-15T23:36:29+00:00 UTC._

## ⚠️ ACTION — needs an operator decision

- 🧬 Avo arms DRIFT: live e49ba8fa7ed2 vs shadow ca1e4c236fc3 (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:18 | active | joined decision+context dataset at 548 closes (51% win), bucket 18 |
| veto:APEX,MINIMAX | resolved | APEX,MINIMAX no longer vetoed |
| veto:NEAR | active | stop rate 15/30 >= 50% (30d) |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=116 (≥10): net $+3.98, WR 35%, t=0.28 — noise
- 🎫 shadow lens 'long-breakoutup' at n=35 (≥10): net $+7.41, WR 40%, t=0.63 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=123, net $+7.43 — by lens [('short', 116, 6.95), ('long', 7, 0.48)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🔭 gate horizon (computed at trajectory, (ks)): no projectable candidate · undecidable@trend: freqtrade-georgia-lshadow, pm-albanese-lshadow, pm-turnbull-lshadow; unreachable@trend: band-barnes-lshadow, crypto-breakout-4h-lshadow, crypto-intraday-15m-lshadow, freqtrade-dad-lshadow, lighter-dislocation-lshadow, lighter-perp-sniper-lshadow, lighter-ticket-taker-lighter, lighter-ticket-taker-lshadow, perps-funding-carry-lshadow, perps-funding-spread-lshadow, pm-abbott-lshadow, pm-gillard-lshadow, pm-morrison-lshadow, pm-rudd-lshadow
- 🚦 fleet-risk light green — longs 9/20, shorts 4/12 (gross 13); 7d DD -0.03%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap -0.052pp (live -0.158% n=51, shadow -0.107% n=80) — no divergence
- 🧬 Farmer arms AGREE: live daeb0319eb3d vs shadow daeb0319eb3d (n=16)
- 🧬 Avo arms DRIFT: live e49ba8fa7ed2 vs shadow ca1e4c236fc3 (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question
- 🧬 freqtrade-avo-maria-lshadow differs from the repo on FILE SET, not necessarily code: container ca1e4c236fc3 (n=15) vs repo b34116a3cfe4 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-avo-maria-lighter differs from the repo on FILE SET, not necessarily code: container e49ba8fa7ed2 (n=15) vs repo 0f7de7db4f89 (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 perps-funding-lighter-lighter differs from the repo on FILE SET, not necessarily code: container daeb0319eb3d (n=16) vs repo a4081a12741a (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 perps-funding-lighter-lshadow differs from the repo on FILE SET, not necessarily code: container daeb0319eb3d (n=16) vs repo a4081a12741a (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy

## Summary

22 alert keys reviewed: 2 active, 1 resolved, 19 stale. No divergence and no drawdown-governor trigger. 16 new-evidence items scanned.
