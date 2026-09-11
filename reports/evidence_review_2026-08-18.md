# Evidence Review — 2026-08-18

_Reviewed 2026-08-18 07:38 AEST (Sydney) · 2026-08-17T21:38:04+00:00 UTC._

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 310.4h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:18 | resolved | joined decision+context dataset at 570 closes (50% win), bucket 19 |
| veto:NEAR | active | stop rate 14/27 >= 50% (30d) |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=122 (≥10): net $-0.83, WR 35%, t=-0.05 — noise
- 🎫 shadow lens 'long-breakoutup' at n=39 (≥10): net $+11.62, WR 46%, t=0.97 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=129, net $+6.68 — by lens [('short', 122, 6.2), ('long', 7, 0.48)]
- 💰 LIVE freqtrade-avo-maria-lighter: n=2, net $+0.08 — by lens [('long-dip-in-uptrend', 2, 0.08)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🔭 gate horizon (computed at trajectory, (ks)): no projectable candidate · undecidable@trend: freqtrade-georgia-lshadow, pm-albanese-lshadow, pm-turnbull-lshadow; unreachable@trend: band-garrett-lshadow, lighter-perp-sniper-lshadow, lighter-ticket-taker-lshadow, perps-funding-carry-lshadow, perps-funding-spread-lshadow
- 🚦 fleet-risk light green — longs 9/20, shorts 3/12 (gross 12); 7d DD -0.13%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.039pp (live -0.153% n=51, shadow -0.193% n=79) — no divergence
- 🧬 Farmer arms AGREE: live e981e11820fc vs shadow e981e11820fc (n=16)
- 🧬 Avo arms differ on FILE SET, not necessarily code: live 4d5c491c01ef (n=17) vs shadow 082797c61510 (n=15) — a different count means different COPY sets ((fd)); compare against each image's own Dockerfile before calling it drift
- 🧬 freqtrade-avo-maria-lshadow differs from the repo on FILE SET, not necessarily code: container 082797c61510 (n=15) vs repo 39f464133444 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-avo-maria-lighter stamp differs from the repo tree: container 4d5c491c01ef vs repo 6ad858544386 (both n=17, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 perps-funding-lighter-lighter differs from the repo on FILE SET, not necessarily code: container e981e11820fc (n=16) vs repo aeac69a20b30 (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 perps-funding-lighter-lshadow differs from the repo on FILE SET, not necessarily code: container e981e11820fc (n=16) vs repo aeac69a20b30 (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy

## Summary

21 alert keys reviewed: 1 active, 1 resolved, 19 stale. No divergence and no drawdown-governor trigger. 17 new-evidence items scanned.

---

# HUMAN LAYER — 18-Aug, 09:20 AEST (Sydney)

Mechanical run **clean**: `payload.errors` empty, all 21 alert keys verified,
`tests/test_review_currency.py` green (34), and **all 23 organ keys fresh
against their own TTL** — the `(os)`/`(ou)` boot-stagger work is holding.
`audit_code_currency`: every container `CURRENT` or deliberately `DEFERRED`;
**no `BEHIND-OWN`**. Fleet moved **−$1.09 over 24h** across 33 closes. Nothing
here needs waking up for.

## ⚠️ ACTION — one decision, and it is not urgent

**Nothing requires a decision today.** No book is newly READY, the drawdown
governor is idle (7d DD −0.13%, `clip_scale` 1.0), the Farmer's live-vs-shadow
gap is **+0.039pp** (live ahead — no divergence), and both live rows are
marker-gated `DEFERRED` by design.

The one thing to know: **`(pr)` is committed but NOT pushed** — this job may not
push. It is on branch `claude/review-quarantine`, full suite green, 7 enforced
audits green, 8 of 8 mutations red. To publish:

```bash
cd "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot/.claude/worktrees/review-quarantine" && git fetch origin && git rebase origin/main && git push origin HEAD:main
```

Re-check the `(pr)` letter after the rebase — two other sessions shipped during
this run (`(pp)`, `(pq)`), which is exactly the collision `audit_changelog_letters`
catches.

## What I found, and fixed — `(pr)`

🧘 **Douglas published `−$23.84` over 6 closes while its last 4 netted `+$2.64`.**
The whole book was two rows, and both were already known to be wrong:

| row | recorded | own stop | overshoot |
|---|---|---|---|
| ROBO long, 15-Aug | **−23.16%** | 7.035% | **3.29×** |
| LINK short, 15-Aug | −3.31% | 0.888% | **3.73×** |

`(nm)` measured both against the venue's own 1h bars — ROBO's entry sat **21%
above the whole hour's high** — proved the loss was a frozen-boot-mark artefact
(its real move was **−6.7%, inside its own stop**), and ruled the pair *"void
rather than a −3.5R signal"*. **Then wired that into nothing.** `LEDGER_QUARANTINE`
exists for precisely this class and did not carry them, so `fetch_paper_trades`
kept serving both to the grader, the brain, `fleet_allocation` and the exit
studies. This file's own rule: *a finding no gate consumes is a note.*

It mattered because Douglas is gradeable **~12-Sep on its own ledger** (I14) at
~92 closes/30d, so two void rows carrying **97% of its record** were on track to
sit inside the window that decides the book. Now quarantined: **n=6/−$23.84 →
n=4/+$2.64**, withheld rows 45 → 47. Scoped to the two measured rows only —
`(nm)`'s own correction refuted the generalisation (the frozen mark's error grows
with container **uptime**; 🧙 Schwager's four legs all priced inside their bars).

## Yesterday's 11 entries, graded against live data — all holding

| entry | verified how | verdict |
|---|---|---|
| `(pm)` 🎸 Barnes retired | row **pruned** from `bot_pnl`; gone from grader, horizon, allocation | ✅ both halves |
| `(po)` 🧙 Schwager retired | row **pruned**; absent from `audit_code_currency` | ✅ both halves |
| `(pf)`/`(pj)`/`(pk)` class screens | 🌾 carry `crypto_only: true`; 4 born-with books `true`; 🎯 sniper `false` (partial, declared); 🛢️ Garrett `false` **top-level** | ✅ |
| `(pj)` Farmer pair still `UNPUBLISHED` | `<ABSENT>` on both arms — **as predicted**, marker gate `DEFERRED` | ✅ working as designed |
| `(pl)` cell-collision detector | runs; carry cell correctly reads **2 books** (was 3 pre-`(pm)`) | ✅ |
| `(pg)`/`(pi)` boot stagger | 23/23 organs fresh vs own TTL | ✅ |
| `(pp)` weekly scoreboard | exposure now off `fleet_risk.long_positions` (9/20) | ✅ |

**A correction to my own first read:** I initially scored 🛢️ Garrett as missing
its `crypto_only` declaration. It was not — I queried `extra.caps` while this
fleet has **two publish shapes** and `lighter_funding_bot.py` publishes
**top-level**, exactly as `(pj)` documented. Caught by re-checking rather than
reporting. That is the `(po)` trap, and it nearly produced a false finding about
a guard shipped yesterday.

## Carried-over priorities

1. **Long-budget Steps 2/3** — untouched. Not binding: longs **9/20**, shorts
   3/12. No reach pressure today.
2. ~~🧲 Snap Back~~ — retired, verified pruned twice. **Dropping this line.**
3. **🌾 carry keep-or-wait** — still stalled: **0 open of 12**, era n=10,
   t=−4.48. Late-Aug operator call (I17). Do not tune.
4. **⚖️ Counterweight post-revert** — 93 in-era closes, mean −1.678%, t=−1.85,
   −$31.08, horizon `unreachable`. Pre-registered operator decision **~28-Aug**.
5. **Allocation re-weight** — organ says funding $14.5k / directional $2.5k.
   Note **`n_with_era_claim: 0` in BOTH classes**: not one book has a positive
   era-scoped claim. 🌾 carry's `expansion_gated: true` correctly pins
   `scale_effective` at 1.0 despite a $12.4k ranking wish — the `(lx)` gate
   working.
6. **MTM re-grade** — series live and moving on every holding book (verified
   raw: taker eq range $10.79/24h, Garrett $5.16). Douglas's 15-Aug flat series
   was the pre-`(nm)` bug and is **fixed**.

## OPTIONS TO OPTIMISE — ranked

**1. 🛢️ Garrett is at its structural cap and turning away 23 candidates —
and widening it is REFUSED.** Census: `max_open 6 / held 6 / free_slots 0 /
eligible 23 / capped 23`. This is the capacity shape that has actually paid
before. **But `(hs)`/I7 binds: a capacity widening reads `pnl_abs` and fails
CLOSED.** Garrett is **−$6.12 MTM, n=14, mean −0.507%, t=−0.53, horizon
`unreachable`, allocation claim 0.000** at 4.1 days old. Widening a negative
book's exposure to buy sample is the ⚖️ Counterweight ratchet again
(5→8→12 while down $27.75). **Expectancy cost: unpriced and negative-leaning —
refused.** Re-ask at ~30 days, when it has a claim rather than a census.

**2. 🌾 carry: nothing to tune, and that is the finding.** 0 open of 12 with
`enter_apr 0.20` and `min_vol 2e6`. Both levers were already measured and
REFUSED — `enter_apr` 20%→10% needs the rate to hold 254 of 336h to break even
`(I19)`, and `carry.min_vol` to its floor unlocked **zero** books `(it)`. The
binding constraint is **venue supply**: the carry cell is occupied **5.93% of
9,662 snapshots**, 3 coins all window. This is a keep-or-retire call, not a
tuning pass.

**3. Concentration, reported not actioned: LINK is held SHORT by three books**
(💸 Farmer shadow, ⚖️ Counterweight, 🛢️ Garrett). `fleet_allocation` ranks those
as three independent claims; `audit_book_overlap` puts effective bets at **19
distinct (coin, side) across 21 positions**. No rule is breached — worth
watching, not fixing.

**4. `veto:NEAR` went active** (stop rate 14/27 ≥ 50% over 30d), joining XLM
(4/5) and DOGE (4/6). The veto organ is doing its job; no action.

**Checked and found nothing on offer:** long-budget reach (9/20 — slack),
clip scaling (governor idle at 1.0), lens bars (the only significant shadow lens
is `long-dip` at **t=−2.74**, already vetoed), and any `live.*` lever (no
current-policy claim supports a move on either live row; the judge remains the
sole writer of `live.funding.*`).

**Honest summary: the one real optimisation available today was a correctness
fix, not a widening** — and the fleet's own rules refused the single capacity
opportunity on the board. That is `(hl)`'s pattern holding: 25 of 30 throughput
candidates died in refutation, and a refusal with evidence is the output.
