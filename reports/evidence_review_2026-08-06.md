# Evidence Review — 2026-08-06

_Reviewed 2026-08-06 12:10 AEST (Sydney) · 2026-08-06T02:10:01+00:00 UTC._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live c68372d7ef06 vs shadow f096db45983b (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 27.0h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:14 | active | joined decision+context dataset at 449 closes (51% win), bucket 14 |
| veto:ADA | resolved | ADA no longer vetoed |
| veto:BOT | resolved | BOT no longer vetoed |
| veto:DOGE,ADA | resolved | DOGE,ADA no longer vetoed |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=98 (≥10): net $+16.80, WR 37%, t=1.32 — noise
- 🎫 shadow lens 'long-breakoutup' at n=22 (≥10): net $+8.30, WR 45%, t=0.74 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=89, net $+8.71 — by lens [('short', 85, 8.2), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=41, net $+0.63 — by lens [('short-divergence', 29, 2.53), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🚦 fleet-risk light yellow — longs 17/20, shorts 2/12 (gross 19); 7d DD -0.17%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.179pp (live +0.285% n=48, shadow +0.105% n=54) — no divergence
- 🧬 Farmer arms AGREE: live 6ff86f4d6b09 vs shadow 6ff86f4d6b09 (n=15)
- 🧬 Taker arms DRIFT: live c68372d7ef06 vs shadow f096db45983b (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question
- 🧬 perps-funding-lighter-lighter stamp differs from the repo tree: container 6ff86f4d6b09 vs repo 2df64c778e08 (both n=15, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 perps-funding-lighter-lshadow stamp differs from the repo tree: container 6ff86f4d6b09 vs repo 2df64c778e08 (both n=15, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale
- 🧬 lighter-ticket-taker-lighter stamp differs from the repo tree: container c68372d7ef06 vs repo f096db45983b (both n=15, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 lighter-ticket-taker-lshadow matches the repo tree: f096db45983b (n=15)

## Summary

23 alert keys reviewed: 1 active, 3 resolved, 19 stale. No divergence and no drawdown-governor trigger. 16 new-evidence items scanned.
