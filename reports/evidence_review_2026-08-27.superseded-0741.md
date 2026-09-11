# Evidence Review — 2026-08-27

_Reviewed 2026-08-27 07:41 AEST (Sydney) · 2026-08-26T21:41:06+00:00 UTC._

## ⚠️ Sections that failed (review still published)

- `verify live-shadow-gap: TypeError: live_shadow_gap() missing 1 required positional argument: 'live'`

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 526.5h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:21 | active | joined decision+context dataset at 650 closes (49% win), bucket 21 |
| live-shadow-gap | active | verification failed: TypeError |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=131 (≥10): net $-8.13, WR 34%, t=-0.48 — noise
- 🎫 shadow lens 'long-breakoutup' at n=86 (≥10): net $+58.99, WR 52%, t=2.33 — significant
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE freqtrade-avo-maria-lighter: n=4, net $+0.51 — by lens [('long-dip-in-uptrend', 4, 0.51)]
- 💰 LIVE freqtrade-georgia-lighter: n=49, net $-26.66 — by lens [('long-trend-breakout', 32, -0.79), ('long-range-on', 16, -25.03), ('long', 1, -0.84)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🔭 gate horizon (computed at trajectory, (ks)): lighter-ticket-taker-lshadow → 2026-10-16 (t) FLOOR:halves · undecidable@trend: pm-albanese-lshadow, pm-turnbull-lshadow; unreachable@trend: band-garrett-lshadow, book-douglas-lshadow, nav-cook-lshadow, perps-funding-carry-lshadow, perps-funding-lighter-lshadow, perps-funding-spread-lshadow
- 🚦 fleet-risk light green — longs 12/20, shorts 5/12 (gross 17); 7d DD -0.56%, clip_scale 1.0
- 📏 freqtrade-avo-maria-lighter live-vs-shadow per-trade gap +0.546pp (live +0.822% n=4, shadow +0.276% n=10) — no divergence
- 📏 freqtrade-georgia-lighter live-vs-shadow per-trade gap -0.295pp (live -0.143% n=49, shadow +0.152% n=102) — no divergence
- 📏 freqtrade-mum-lighter live-vs-shadow: insufficient paired closes (live n=0, shadow n=6) — no verdict
- 🧬 freqtrade-avo-maria-lighter arms differ on FILE SET, not necessarily code: live 689f8958926d (n=17) vs shadow 3e7696f0dc39 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-georgia-lighter arms differ on FILE SET, not necessarily code: live 689f8958926d (n=17) vs shadow 3e7696f0dc39 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-mum-lighter arms differ on FILE SET, not necessarily code: live 9c832edeb302 (n=17) vs shadow 3e7696f0dc39 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-avo-maria-lshadow differs from the repo on FILE SET, not necessarily code: container 3e7696f0dc39 (n=15) vs repo d70aea547a86 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-georgia-lshadow differs from the repo on FILE SET, not necessarily code: container 3e7696f0dc39 (n=15) vs repo d70aea547a86 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-mum-lshadow differs from the repo on FILE SET, not necessarily code: container 3e7696f0dc39 (n=15) vs repo d70aea547a86 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-avo-maria-lighter stamp differs from the repo tree: container 689f8958926d vs repo b7046114f4b8 (both n=17, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 freqtrade-georgia-lighter stamp differs from the repo tree: container 689f8958926d vs repo b7046114f4b8 (both n=17, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 freqtrade-mum-lighter stamp differs from the repo tree: container 9c832edeb302 vs repo b7046114f4b8 (both n=17, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]

## Summary

21 alert keys reviewed: 2 active, 0 resolved, 19 stale. No divergence and no drawdown-governor trigger. 22 new-evidence items scanned.
