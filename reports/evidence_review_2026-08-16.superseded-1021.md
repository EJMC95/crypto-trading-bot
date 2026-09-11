# Evidence Review — 2026-08-16

_Reviewed 2026-08-16 10:00 AEST (Sydney) · 2026-08-16T00:00:45+00:00 UTC._

## ⚠️ ACTION — needs an operator decision

- 🧬 Avo arms DRIFT: live e49ba8fa7ed2 vs shadow ca1e4c236fc3 (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 264.8h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
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
- 🔭 gate horizon (computed at trajectory, (ks)): no projectable candidate · undecidable@trend: freqtrade-georgia-lshadow, pm-albanese-lshadow, pm-turnbull-lshadow; unreachable@trend: band-barnes-lshadow, lighter-perp-sniper-lshadow, lighter-ticket-taker-lshadow, perps-funding-carry-lshadow, perps-funding-spread-lshadow
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

_An earlier report for this day was preserved at `evidence_review_2026-08-16.superseded-0936.md`._

---

# HUMAN LAYER — 16-Aug-2026 (added after the script run)

_Covers TWO days: the last report on file is 14-Aug, so this grades CHANGELOG
entries `(mt)`→`(nh)` — the whole 15-Aug push, including the red-stop slate._

## ⚠️ CORRECTION TO THE SCRIPT'S OWN ACTION SECTION

The generated ⚠️ ACTION above (🧬 Avo arms drift) is **NOT an action**. Verified
this run: `audit_code_currency.py --depth 45` returns **exit 0, all 20 stamped
containers accounted for**, with `freqtrade-avo-maria-lighter` classified
`DEFERRED — 23 commit(s) behind, none marked for this marker-gated service —
working as designed`. Nothing in those 23 commits qualifies for a live deploy
under `(mm)`: `(ne)`'s avo cap 4→6 is declared **shadow-only** and `(mi)`'s
`capital_adjusted_day_start` fix was declared **behaviour-preserving, main-only**.
The control arm is sound. No operator action.

**Nothing else needs a decision today.** No book is newly READY, the drawdown
governor is quiet (7d DD −0.03%, clip_scale 1.0), and live-vs-shadow execution
is clean (Farmer gap −0.052pp, n=51/80).

## 1 · FIXED THIS RUN — the review was grading RETIRED books for real money

**`scripts/evidence_review.py` was nominating corpses.** Its `RETIRED` frozenset
was a hand copy frozen at the July cut. Underneath it the fleet retired **twelve
more books** and not one reached the list:

| Retired | Entry | Still being graded? |
|---|---|---|
| 🌊 crypto-trend-daily-lshadow | `(if)` 1-Aug | yes |
| 🧲 lighter-dislocation-lshadow | `(jh)` 4-Aug | yes |
| 📊 equities-regime-lshadow | `(lo)` 13-Aug | yes |
| 🎫 lighter-ticket-taker-**lighter** (live arm) | `(ma)` 13-Aug | yes |
| 🚀 crypto-breakout-4h-lshadow | `(mr)` 14-Aug | yes |
| pm-gillard / abbott / rudd / morrison, intraday-15m, swing-daily, 👨 dad | `(nf)` 15-Aug | yes |

The visible symptom was mild — the 🔭 horizon line named **eight dead books** as
`unreachable`, the `(gl)` overstating-detector shape. The real exposure is the
line above it: that loop's entire job is to announce a book as a **real-money
promotion candidate**, and `pm-gillard-lshadow` — n=304, the largest ledger in
the scanned set — was retired at t=−1.85 the previous day and graded here anyway.
Only its own bad numbers stopped the review nominating a book the operator had
just killed.

**Fix:** `RETIRED` now derives from `cleanup_legacy_bots.LEGACY_BOTS` — the
canonical declaration, the half of CLAUDE.md's two-half retirement rule that
prunes the row, and the list `golive_readiness` already imports for this exact
purpose. Review and grader now agree about which books are dead as they already
agree about the bars `(hj)` and the era `(hq)`. The literal survives only as a
degraded-mode floor (a verified strict subset), because `golive_readiness` fails
**open** here and for this consumer open *is* the bug.

**Verified after the fix:** the horizon line dropped from 17 books (9 dead) to 8,
all living, and now matches the canonical grader's table exactly. No living book
was lost — including the bare-name trap, where `LEGACY_BOTS` carries the
Kraken-era `freqtrade-georgia` / `-mum` / `-avo-maria` whose `-lshadow` twins are
alive (one is the live pair's control arm).

**Guard:** `tests/autonomy/test_review_retired_roster.py` (20 tests) + an
in-script `--selftest` arm. **Mutation-verified, 4 mutations, all red.** Worth
recording that mutation #4 — rewriting the call site to
`any(d in bot for d in RETIRED)` — **survived my first version of the test**: the
set contents are identical and only the matching semantics move, so a
set-contents assertion cannot see it. Closed with an AST test pinning that
`RETIRED` is only ever read as the right-hand side of an `in`. That is I3 doing
its job on my own work.

Full `tests/autonomy` suite green (all 900+). Changelog letter `(ni)` is free
locally and on `origin/main`. **Not committed** — per this job's safety rules.

## 2 · GRADING YESTERDAY'S WORK — `(mt)`→`(nh)`

Every claim below was tested against current data, not read.

| Entry | Claim | Verdict |
|---|---|---|
| `(my)` MTM series for the directional cohort | "6 of 17 books graded" → all | ✅ **LANDED.** 29 books publish `:equity`; the cohort (georgia, mum, avo-shadow, albanese, turnbull, sniper) all start 15-Aug 00:3x. Funding trio pass the maxdd bar on real samples: carry n=4208/14.6d/1.58%, ⚖️ n=4562/15.8d/2.18%, 🎸 n=3064/10.6d/1.36% |
| `(nb)` Garrett clip $7.50→study cell | probe floor leaked into a variant | ✅ **LANDED.** First 5 trades ~$7.50 notional; the 15-Aug BCH trade ~$30. Payload `clip_usd: 30.0` |
| `(nc)` ≈$13 of carry's +$66 is phantom | "the `(lx)` accessor gate already blocks ACTING on pooled claims" | ✅ **VERIFIED BY MEASUREMENT, not taken on trust.** The organ still ranks carry #1 at a **$10,617 target (4.0x)** on `claim=0.001492, n=101` — but `claim_era` is `None`, the `(lx)` era gate declines the expansion, and `fleet_bus.allocation_scale()` returns **1.0**. No consumer acts on the contaminated rank |
| `(nf)` red-stop slate, 7 rows | retired both halves | ✅ all 7 in `LEGACY_BOTS`; `audit_ledger_integrity` labels each `(retired)` |
| `(nf)` 🎸 xsect winds down to flat | "empty targets wind every leg down at the next 24h cycle" | ⏳ **NOT YET DUE — checked the clock before crying wolf.** Sleeve still shows `open: 10, retired: true`. Last rebalance **15-Aug 04:58Z**, slate shipped ~13:00Z, cadence `XSECT_REBALANCE_H = 24.0` ⇒ first post-retirement cycle **~16-Aug 04:58Z (14:58 Sydney today)**. Mechanism is correctly wired (`XSECT_RETIRED` → `([], [])` → every leg closes `rebalance`, open-loop a no-op) |
| `(ng)` judge n=0 is by design | clock restarts on arm re-match | ✅ confirmed in code; not a regression from `(na)` |
| `(nh)` currency guard went blind on 3 rows | fixed | ✅ all 20 rows resolve, exit 0 |

**One dated, falsifiable check for tomorrow:** if 🎸 Barnes still reports
`sleeves.xsect.open > 0` after **16-Aug 05:00Z**, the wind-down is broken and
that is a real finding. Until then it is simply not due.

## 3 · FLEET STATE

- **Go-live: READY none.** No book passes. Nearest are 🙏 avo-shadow (n=8, on_track
  2026-11-06) and 🔮 georgia (n=106, t=0.18, undecidable).
- **Reach is no longer the binding constraint.** Longs **9/20**, shorts 4/12,
  gross 13. The red-stop slate freed roughly a third of the long budget; the L2
  veto is nowhere near refusing entries. Previous reviews flagged 18+ gross as a
  ceiling — that ceiling is gone, and nothing is currently queued to use it.
- **Ledger integrity:** the one failure is 🌾 carry's **permanent, historical**
  two-writer window (7 overlaps, deepest 9.14h, most recent **424h** ago). In-era
  integrity is clean (`same_pair_overlaps: 0`), so the graded sample is sound.
  Known-open, not new.
- **Code currency:** clean, exit 0.
- **Script errors:** `errors: []` — no section failed soft.

## 4 · THE STRUCTURAL FINDING — three books are parked on an empty cell

Measured directly off the scout (`lighter-market`, age 0.02h, 210 books):

| Cell | Books entering | Qualifying coins RIGHT NOW | Held |
|---|---|---|---|
| **20% TRUE / ≥$2M / crypto** | 🌾 carry · 🎸 Barnes carry · 🏦 Rich Dad | **0** | 0 / 0 / 0 |
| 🧮 Hull `[7.82%,20%) × [$2M,$10M)` | 🧮 Hull | 2 (LIT 10.5%, LINK 10.5%) | 1 |
| 💸 Farmer `≥$10M` | 💸 Farmer | 3 (HYPE 8.8%, BTC 5.3%, SOL 5.3%) | 3 |
| 🛢️ Garrett `[$0.1M,$2M) ≥5%` | 🛢️ Garrett | **26** (KAITO 205%, ROBO 124%, APT 46%, ETHFI 24.5%) | **6 = AT CAP** |

This is I20's supply doctrine landing on live data. **Three books hold zero
because their shared cell is empty**, while the one book on the richest cell is
at its position limit. Caveat stated honestly: CLAUDE.md already measures that
cell as populated in only **6.6%** of scout snapshots, so "0 right now" is the
*expected* state ~93% of the time — this is the known venue stall, quantified,
not a new failure. What *is* new is that two of the three books (🎸 Barnes carry,
🏦 Rich Dad) were born into that cell in the last three days, **after** I20 was
written. 🏦 Rich Dad has **0 closes in 3 days**.

### 🌾 carry — the docket item has hardened

Carry is **idle**: `open: 0`, and **no close since 12-Aug** (4 days). Its
admissible in-era record is **n=10, −$15.45, t=−4.48** — a *significantly
negative* book, not merely a stalled one. The raw ledger's cheerful +$55 over 30
days is the pre-era window, and `(nc)` showed ≈$13 of the all-time +$66 is phantom
accrual. Both registered levers were already refused on measurement, and `(mv)`
made `carry.enter_apr` **tighten-only** yesterday. **There is no lever left to
pull.** This is the I17 keep-or-retire call, already docketed for late-Aug.

## 5 · A DECLARED ASYMMETRY, MEASURED AND REFUSED

`lighter_funding_bot.py` — which runs **both 🛢️ Garrett and the LIVE real-money
Funding Farmer** — has **no crypto class screen**, while its three siblings do
(🌾 carry `(lk)`, 🎸 Barnes `(lv)`, 🎯 sniper `(lk)`). The `(lj,lk,ll)` sweep
missed it, exactly as `(lv)` records it missing Barnes.

I checked whether that matters, with a control group (I6) — and **the evidence
refuses the change**:

| Arm | non-crypto | crypto |
|---|---|---|
| 💸 Farmer **LIVE** | n=12, −$1.17, **t=−0.44** (win 75%) | n=111, +$8.60, t=+1.67 |
| 💸 Farmer shadow | n=22, **+$1.78**, t=+0.29 | n=158, +$3.71, t=+0.24 |

The two arms **disagree in sign** and neither is significant. Carry's `(lk)`
screen rested on a far starker signal (−$14.96 over 9 vs −$0.49 over 1). Shipping
a restrict-only screen to a real-money book on a t=−0.44 sample would be a veto
firing on noise — precisely what I15/I19 forbid. **Refused, with the number.**
Re-ask when the live non-crypto sample reaches n≈30. The Farmer currently holds
XAU, so the class is live and will accrue.

## OPTIONS TO OPTIMISE

Ranked. Two are refusals with evidence, which is a valid output — and today the
honest answer is that **no lever move is on offer**.

**1 · Publish a CENSUS on `lighter_funding_bot.py` — the one real gap (do next pass).**
🛢️ Garrett is at **6 of 6** on a cell with **26 qualifying coins**, and it holds
**none of the four highest-APR ones** (KAITO 205%, ROBO 124%, APT 46%, ETHFI
24.5%) — it holds BNB/CTR/TAO/XMR/ZRO/GRAM, four of which sit at 10.5%. That may
be entirely correct (those four are $0.13–0.42M books; the spread/slip vetoes
plausibly reject them, and positions were opened when the ranking differed) — but
**nothing in the payload can say which**. `held: {6 coins}` is byte-identical
between "holding the best 6" and "the top 4 are being silently vetoed", which is
I18's rule verbatim: *a book that cannot open must publish its OWN census at its
OWN bar*. 🎸 Barnes already does this (`sleeves.extreme.scan`); the funding module
publishes only `held`/`max_open`/`hottest_apr`.
*Cost:* none — publish-only, changes no trade, so main-only under `(mm)`.
*Why not this run:* forward-motion rule 1 (ship narrow, one surface per pass) — I
already changed `evidence_review.py` this run, and this one touches the live
Farmer's module.

**2 · Raise Garrett's `FUNDING_MAX_OPEN` (6 → 8/10)? — REFUSED today, re-ask ~29-Aug.**
*The case for:* it is the fleet's fastest-accruing book (6 closes in 2.8d ≈
2.1/day → n=30 around **29-Aug**) and the only one on a populated cell;
decidability is I17's first unit of winning.
*The expectancy price, which kills it:* of the 26 in-band coins exactly **4** are
above 20% APR and **22 sit at ~10.5%**. Slots 7+ therefore fill at ~10.5%, where
a 30bps round trip needs ~250h to repay — the same unit-economics failure `(lv)`
measured on Barnes's carry sleeve ($0.24 RT vs $0.343 accrued over 8 trades). A
ranked selector's marginal slot is its *weakest* candidate, not its best.
*And there is no claim to price it with:* Garrett is n=6, −$0.60, `claim = 0.0`.
Widening capacity on a book with no measured claim is turnover bought on a hunch.
**Re-ask when it has a claim.** Note also: grade Garrett on per-trade **%**, not
$ — its first 5 trades ran at $7.50 and the rest at $30, so dollar sums mix two
scales. Per `(hc)` a clip change is *not* an era reset, so its `(hm)` clock
correctly continues from 13-Aug.

**3 · 🌾 carry — no lever, operator call.** Covered in §4. Both levers refused on
measurement, `enter_apr` tighten-only since `(mv)`. Loosening the gate to reach
supply is the exact move `(it)`/I19 priced and rejected. **Nothing to tune.**

**4 · The freed long budget (9/20) has no claimant.** Reach stopped being the
constraint when the slate retired seven books. But handing slots to books with no
measured claim is I16 inverted, and the only book with headroom *and* supply is
Garrett — refused above. Recording it so a future pass doesn't "discover" the
slack and spend it. **The binding constraint is now SUPPLY and EVIDENCE, not
budget.**

**5 · Reporting hazard on carried priority #5 (allocation re-weight).** If the
operator says yes to the advisory table, note that 🌾 carry's displayed
**$10,617 (57% of pool)** rests on a pooled claim `(nc)` measured as ~20%
inflated, with `claim_era: null`. The *actuator* is already safe (§2 — scale
returns 1.0); it is the **displayed number** that would mislead a yes/no read.

### Checked and found nothing on offer
Capacity across the rest of the fleet (no other book is at cap with a graded
signal — 🧮 Hull 1/4, 🏦 Rich Dad 0/6, 🎸 Barnes carry 0/4, 💸 Farmer shadow 3/6);
the taker's shadow lenses (best is long-breakout n=10 t=1.73, and long-dip is
**significantly negative** at n=13, t=−2.74, already vetoed); the fleet drawdown
governor (quiet); live/shadow execution quality (clean).

## CARRIED PRIORITIES — status

1. **Long-budget Steps 2/3** — still open, and **less urgent than it was**: at
   9/20 the budget no longer binds, so displacement-by-edge has nothing to
   displace. Keep, but it is no longer the fleet's top reach lever.
2. ~~🧲 Snap Back keep-or-retire~~ — **DONE `(jh)`**; seen clean twice (row
   retired, in `LEGACY_BOTS`, labelled `(retired)` by the integrity audit).
   **Recommend dropping this line.**
3. **🌾 carry keep-or-wait** — evidence has hardened *against* the book (§4).
   Operator call, late-Aug. Do not tune.
4. **⚖️ Counterweight post-revert** — accruing: era n=89, mean −1.880%,
   **t=−2.01**, −$31.65, maxdd 4.1% (MTM-folded). Its pre-registered ~28-Aug
   decision is on track and currently pointing at retire.
5. **Allocation re-weight** — operator yes/no still open; read §"Reporting
   hazard" above first.
6. **MTM re-grade** — **effectively DONE for the funding trio.** `(my)` filled
   the cohort; carry/⚖️/🎸 all have 3,000–4,600 samples over 10–16 days and all
   **pass** the drawdown bar. The `(my)` cohort crosses the 200-sample/7-day floor
   ~22-Aug. **Recommend narrowing this line to "re-check the `(my)` cohort
   ~22-Aug".**

_Times Sydney (AEST, UTC+10). Fleet internals stay UTC._
