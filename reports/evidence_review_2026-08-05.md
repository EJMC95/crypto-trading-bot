# Evidence Review — 2026-08-05

_Reviewed 2026-08-06 08:53 AEST (Sydney) · 2026-08-05T22:53:41+00:00 UTC._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live c68372d7ef06 vs shadow fdcfdd13d458 (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 23.7h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| factor-sample:14 | active | joined decision+context dataset at 447 closes (51% win), bucket 14 |
| veto:ADA | active | stop rate 22/44 >= 50% (30d) |
| veto:BOT | resolved | BOT no longer vetoed |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=98 (≥10): net $+16.80, WR 37%, t=1.32 — noise
- 🎫 shadow lens 'long-breakoutup' at n=21 (≥10): net $+8.61, WR 48%, t=0.77 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=88, net $+8.35 — by lens [('short', 84, 7.84), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=41, net $+0.63 — by lens [('short-divergence', 29, 2.53), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🚦 fleet-risk light yellow — longs 17/20, shorts 3/12 (gross 20); 7d DD -0.14%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.181pp (live +0.265% n=47, shadow +0.084% n=53) — no divergence
- 🧬 Farmer arms AGREE: live 6ff86f4d6b09 vs shadow 6ff86f4d6b09 (n=15)
- 🧬 Taker arms DRIFT: live c68372d7ef06 vs shadow fdcfdd13d458 (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question
- 🧬 perps-funding-lighter-lighter stamp differs from the repo tree: container 6ff86f4d6b09 vs repo 9bf4eb8cf6cd (both n=15, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 perps-funding-lighter-lshadow stamp differs from the repo tree: container 6ff86f4d6b09 vs repo 9bf4eb8cf6cd (both n=15, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale
- 🧬 lighter-ticket-taker-lighter stamp differs from the repo tree: container c68372d7ef06 vs repo fdcfdd13d458 (both n=15, so not a file-set difference) — UNCLASSIFIED. A shared-module change moves every image's stamp without changing any bot's logic, so this is NOT yet a finding: run `scripts/audit_code_currency.py`, whose own-entry-file verdict is the only one that means the container is stale [REAL MONEY row]
- 🧬 lighter-ticket-taker-lshadow matches the repo tree: fdcfdd13d458 (n=15)

## Summary

22 alert keys reviewed: 2 active, 1 resolved, 19 stale. No divergence and no drawdown-governor trigger. 16 new-evidence items scanned.

---

# Human layer — reviewed Thu 6 Aug 2026, ~09:20 AEST (Sydney)

_Run against HEAD `d3c0a25` (kj). A concurrent session committed (kj) **during**
this run and had in-flight edits to `fleet_bus.py` and
`tests/autonomy/test_venue_instrument_class.py`; neither was touched here._

## ⚠️ ACTION — the one real-money decision

**💸/🎫 the two LIVE containers are 2 and 9 commits behind, and the gap now
contains the (kh) I5 fix.** `audit_code_currency --depth 45` classifies both
**DEFERRED** — marker-gated, working as designed — and neither is BEHIND-OWN,
so no live *trading logic* is stale. But the gap includes `bot_pnl_store.py`'s
(kh) repair, which stopped `publish_paper_trade` dumping `extra` with a bare
`json.dumps`: a non-finite float makes Postgres reject the whole statement and
**both writers swallow the exception, so a real close leaves no ledger row.**
Both live rows publish ratios and APRs in `extra`. The evidence base for real
money is the thing at risk, not the trades.

Deploy is an operator act (CLAUDE.md routing) and this task may not do it:

```bash
.venv/bin/python3 scripts/deploy_live_verify.py --services trail-blazer-live,tide-rider-lighter-live
```

Marker `[deploy-live-farmer]` / `[deploy-live-taker]` in the commit **subject**,
from a clean worktree; confirm by `extra.build` + `extra.build_n` readback.

## Assessment of yesterday's work — (ji)…(kj), ~21 entries

| Entry | Claim | Verdict against current data |
|---|---|---|
| (ki) | Barnesy's xsect filtered to crypto; ⚖️ guard inert | **Half-landed, and correctly so.** ⚖️ Counterweight holds 10 legs, **all crypto** (APT/BNB/DOT/JUP/LTC/TIA/AAVE/AVAX/DOGE/LINK) — verified in the live payload. 🎸 Barnesy **still holds AAPL, AMD, PAXG, US100, US500**: its xsect rebalance is 24-hourly and last ran 04:08 UTC, *before* the deploy. The rebalance closes legs that leave the target set, so this self-heals ~**14:08 AEST today** — no action, but worth confirming. |
| (kh) | MDE published beside every null | **Landed and already changing readings.** The `MDE80%` column renders; ⚖️'s t=−1.98 sits at MDE 3.37 / power 0.071, so it is correctly *not* evidence. |
| (kg) | money published at the gate | **Landed** — `net$`/`$/day` render. |
| (ke) | review stops crying wolf on real money | **Landed for `head_drift_line`**; the sibling `arm_drift_line` still over-claimed — fixed today (below). |
| (kd) | grader fail-closed on a dead ledger read | **Landed** — the run errored loudly on an unset URL rather than printing "READY: none". |
| (jh) | 🧲 Snap Back retired | **Holds** — hidden + pruned, both halves. But its *alerts* did not retire; see below. |
| (jg) | ⚖️ K 8→5, universe 60→30 | **Holds** — live caps read `k=5, legs=10, universe=25`. |

## Fixed this run (correctness → shipped, mutation-verified)

1. **The review was certifying a dead book's alerts as live — an I1 violation,
   19 distinct keys** (18 `disloc:` + 1 `census:`). 🧲 Snap Back retired 4-Aug,
   so `bot_state['lighter-dislocation-lshadow']` froze. The disloc verifier read
   that frozen payload's *content* — per-symbol `last_iso` still inside the
   7-day window — and published them **"active"**. The
   smoking gun was one character: `st, _ = load_state(...)` **discarded the
   publisher's own `updated_at`**. Publisher measured **23.5h stale**.
   **CORRECTED from this report's own first cut:** I wrote "33 of 37 items …
   each morning". 33/37 was the raw append-only FEED at one instant (25/29
   hours later — `fleet_immune` prunes it), not what the review publishes, which
   is one verdict per distinct key = 19. And "each morning" is false: the
   previous review ran **2026-08-04 23:05:56Z**, the publisher's last write was
   **23:10:59Z — five minutes later**, so that run's verdicts read "last event
   0.2h ago" and were CORRECT. The defect was **latent, not historic**; the
   first and only wrong publication was **this morning's run, mine**, fixed and
   republished an hour later in the same session.
   Fixed with a liveness gate (`CENSUS_STALE_H = 6.0`, derived: 240× the
   publisher's 90s loop, 6× its retired-idle sleep), fail-SAFE on an unknown
   age. **Effect: 21 active → 2 active, 19 stale**; the banner drops 19
   unactionable items and keeps the 2 live ones (`factor-sample:14`,
   `veto:ADA`). 4 mutations red.
2. **`arm_drift_line` asserted a verdict its inputs cannot support** — the same
   category error (ke) fixed one function up and explicitly left open here. It
   said *"the shadow arm is not a clean control"* from two build stamps.
   Measured: the Taker arms differ by (kh)+(ki), **neither of which touches
   `lighter_ticket_taker.py`** — the diff is `bot_pnl_store.py` and an additive
   `fleet_bus` helper, so the control was sound. Now states the fact, names
   `audit_code_currency` as the authority, and still surfaces. 3 mutations red,
   including the (ke) `BEHIND-OWN:` disclaimer-collision trap.
3. **The report handed Eamon a bare UTC time**, against the standing Sydney
   rule. Header now reads Sydney-local **and** UTC (ledgers join on UTC). The
   filename stays UTC-dated deliberately — it is the series key. My first cut
   pinned only the helper and a mutation reverting the *header* survived; the
   wiring is now pinned through the real `write_report`.

Full suite green on the settled tree; `audit_image_imports` /
`audit_deploy_coverage` / `audit_venue_purity` / `audit_lever_bounds` /
`audit_changelog_letters` / `audit_doctrine_enforcement` all exit 0.
**Changes are UNCOMMITTED** (this task may not push; a concurrent session is
active in the tree). Backup: `scratchpad/backup/`.

## ⛔ A refusal that matters — do NOT extend (ki)'s crypto filter to 🌾 carry

The obvious next move after (ki) is "close the class — filter non-crypto out of
every funding book." **On carry's own ledger that would remove the population
producing most of its money.** Measured at HEAD:

| Population | n | mean/trade | t | win | net | share of book |
|---|---|---|---|---|---|---|
| CRYPTO | 69 | +0.156% | +1.96 | 39% | +$32.38 | 43% |
| **NON-CRYPTO** | **20** | **+0.724%** | **+2.54** | 60% | **+$43.43** | **57%** |

22% of the trades, 57% of the money, **4.6× the per-trade return** — and the
non-crypto half clears the gate's own `t ≥ 2` bar while the crypto half does
not. Robust, not one symbol: 7 distinct bases, 6 of 7 profitable; leave-one-out
holds t at 1.97–2.36 and net at +$28.62–31.54.

**Why it differs from ⚖️'s −9.209%:** ⚖️/xsect is a *dollar-neutral pair* whose
`pnl_pct` is **price-only**, so pairing AAPL against a crypto name imports
unhedged equity variance. 🌾 carry *harvests the funding* and exits
`decay_paid`. Same instruments, opposite mechanism. I14 — the book's own record
beats the cross-book proxy. `crypto_only` is currently scoped to exactly the
two cross-sectional books (`lighter_funding_spread_bot:366`,
`lighter_band_barnes_bot:730`); **that scoping is correct — leave it.**

## Fleet state

- **All 23 rows fresh** (< 0.15h), every one `extra.svc`-stamped.
- **Go-live: NO new candidate.** 🌾 carry is `ungradeable in era` — **1 of 89
  closes** since the 31-Jul era. Nothing is near the gate.
- **Ledger integrity:** one failure, `perps-funding-carry-lshadow` — 7
  historical same-pair overlaps, deepest 9.14h, most recent **182h ago**.
  Pre-era, permanent, nothing to stop. Known, not new.
- **Risk light yellow**, longs **17/20**, 7d DD −0.14%, `clip_scale` 1.0.
- **Live money:** 💸 Farmer n=88 **+$8.35**; 🎫 Taker n=41 **+$0.63**
  (short-divergence 29 / +$2.53, long-divergence 12 / −$1.90 — pre-gate, frozen).
- **Farmer live-vs-shadow gap +0.181pp** (live +0.265% n=47 vs shadow +0.084%
  n=53) — live ahead, no divergence.
- `payload.errors` **empty**.

## OPTIONS TO OPTIMISE

**1. `carry.min_vol` 2e6 → 1e6 — the only reachable lever on the stalled
go-live candidate. Do not set it today; re-measure first.**
Carry's census: 218 scanned, 197 cold, **16 thin**, 4 held, **0 eligible**. So
16 books pass its 20% TRUE apr bar and are excluded *solely* by the $2M volume
floor. Cage is `[1e6, 2e6]`, default 2e6, consumed via `apply_tuning`.
**Priced exactly:** of the venue's 204 books only **10** sit in `[1M,2M)`, and
at this moment only **US500** (36.8% apr, $1.03M) also clears the 20% gate —
US100 was 20.1% an hour ago and is 19.3% now. So the honest unlock is
**1–2 books, both equity indices** — i.e. the population carry does *best* on.
*Why this is newly live:* (it) refused this lever on the measurement that
walking it "unlocks zero books". **That refutation has expired** — the band is
no longer empty. *Why not today:* carried priority #3 bars re-tuning carry
(late-Aug operator call, I17), (ka)'s favourable thin-tier numbers are the
**Farmer's** tape and exit ladder, not carry's, and I19 requires the expectancy
price through a replay. **Cost if wrong: thin-book slippage, unmeasured for
carry.** Recommend: re-run (ka)'s thin-tier study against *carry's* ladder
before the late-Aug decision.

**2. The venue is thinner than the fleet's config assumes — a structural fact
worth one operator glance.** Only **18 of 204** books trade ≥$2M/24h and only
**8** trade ≥$10M; **120 are under $100k**. Every funding book's stall
(🌾 carry `eligible 0`, 🎸 Barnesy `eligible 0`) is the same constraint. This
is not a tuning problem — it is the venue. It is the strongest argument that
carry's late-Aug call is *keep-or-retire*, not *tune*.

**3. 🎸 Barnesy: two of three sleeves have never opened.** `carry 0/4`,
`extreme 0/4`, `xsect 10/10`; scan `eligible 0`. Its mid-Sep grade will be an
**xsect-only** grade of a book sold as a three-sleeve super-book. Named by (ki)
as open; unchanged. Config is birth-frozen to 4-Sep, so this is an *observation
to carry*, not a lever — but the September expectation should be set now.

**4. Long budget 17/20 — 3 longs from the veto refusing new entries.** Carried
item #1 (Steps 2/3) remains the fleet's only fleet-wide reach lever, and
`long_effective_n` 13.4 from 22 positions says the concentration argument is
still live. Unchanged today; needs replay evidence, never shipped bare.

**Checked and found nothing on offer:** no capacity headroom (⚖️ at its
intended 10 legs post-revert; 🌾 4 of 12 with *zero* eligible candidates, so
raising `max_positions` moves nothing); no book near the go-live gate; no
governor trigger; no live/shadow divergence.

## Carried priorities — status

1. **Long-budget Steps 2/3** — OPEN, unchanged (see option 4).
2. **🧲 Snap Back retirement** — verified clean a **second** time (hidden +
   pruned + guard). Per its own terms this line can now be **dropped**. Its
   *alerts* were the loose end, closed today.
3. **🌾 carry keep-or-wait** — OPEN and sharper: 1 close in era, 0 eligible,
   and the venue (option 2) is the reason. One lever refusal has expired
   (option 1). Still a late-Aug operator call.
4. **⚖️ post-revert watch** — holding: `k=5`, 10 all-crypto legs, `ff_overlap
   0/10`. Its t=−1.98 is **not** evidence (MDE 3.37, power 0.071). Sample still
   accruing; keep the line one more cycle.
5. **Allocation re-weight** — awaiting operator yes/no. Organ still advisory;
   `undecided_why` now published ((kc)) — every directional book reads
   `bound<=0`, 🎸 Barnesy `no-bound`.
6. **MTM re-grade** — floors (200 samples/7d) still filling; no book graded on
   the (ia)/(iz) bar yet. Re-check ~7-Aug.

---

# Addendum — "let them thrive" pass (~10:40 AEST)

Operator directive: *"let them thrive."* Acted on the starvation rather than
reporting it. Two candidate actions were worked to a decision; one is a
refusal with evidence, and one alarm I raised was **wrong and is withdrawn**.

## WITHDRAWN — there is no Parliament incident

I flagged 🏛️ the Parliament as dark: `data.cycles 0`, `data.books 0`, all six
PM books at `closed: 0`, and `stalled: []` while every heartbeat read `0`.
**That was a misreading and the alarm is withdrawn.** `beats: {"keating.ml": 0}`
is *seconds since the last beat*, not a beat count — those organs were beating
at that instant. The payload publishes every **5 minutes**, so my two reads
150s apart hit the same boot-time snapshot twice.

Tested properly over 7.5 min across 3 distinct publishes:

| t | cycles | books | beats |
|---|---|---|---|
| 0 | 0 | 0 | 3 organs |
| +5m | **3** | **204** | all six `bot.*` at 59s, `data.market` live |
| +10m | **5** | 204 | + `data.candles.15m`, `tuner.pm-morrison` |

The Parliament was mid-startup and is healthy. Recorded rather than quietly
dropped, because I2's lesson is that the counter which *diverges* decides —
and here the diverging counter (`cycles`) exonerated the organ.

**What survives, from the durable ledger and independent of any payload:** the
six PM books are running and **not entering** — pm-morrison silent **181h**,
pm-rudd **113h**, pm-gillard **112h**, pm-turnbull **80h**, pm-albanese **45h**,
all with 0 open. Alive, gated shut. Not a liveness bug; a gate question, and
the right owner is the Parliament's own replay-gated tuners.

## REFUSED with evidence — `carry.min_vol` 2e6 → 1e6, today

I intended to ship this and the arithmetic stopped me.

**What it would buy:** exactly **one** book. Of 204 venue books only 10 sit in
`[1M,2M)`, and only **US500** (36.8% apr, $1.03M) also clears the 20% gate;
US100 drifted 20.1% → 19.3% during this run.

**Why that one book is not a win:**

- **It is out-of-sample for this book's entire record.** The lowest entry APR
  🌾 carry has *ever actually taken* is **84.1%** — 4.2× its own gate. The 20%
  gate is not what selects its trades; the 6h persistence plus the venue's
  APR distribution is. US500 at 36.8% is below everything carry has ever done.
- **Break-even is genuinely close.** carry charges **29bps round trip**
  (`OPEN_COST` ×2) — *more* conservative than the thin tier's measured p90
  (29.5bps, (js) n=158), so thin books add no unmodelled cost. But at 29bps,
  break-even hold at 36.8% apr is **69h**, against a measured p25 hold of
  59.5h. It clears only if held past the first quartile.
- **The evidence to price it does not exist yet.** (gr) is not retroactive, so
  only **5 of 89** closes carry `entry_apr`/`held_h`. An expectancy claim about
  a new liquidity tier cannot rest on n=5.
- **(ka)'s favourable thin-tier numbers are the *Farmer's* instrument** —
  PERSIST_H 4, exit ratio 0.375, 6 slots, $25 clips, 72h cap. carry runs $300
  notional, 6h persistence, 336h cap. The transfer is not free.

Under the standing rule this is turnover, not expectancy. **Not set.**

**But the reframe is worth keeping**, because it is the strongest growth thread
on this book: every member of the `[1M,2M)` band except BNB/PUMP/XRP is
non-crypto (AMD, BRENTOIL, GOOGL, INTC, PLTR, US100, US500) — so carry's $2M
volume floor is a proxy that **systematically screens out the exact population
carry does best on** (n=20, +0.724%/trade, t=+2.54, 57% of its money). That is
a real hypothesis with a real mechanism, and it deserves the measurement rather
than a lever set on a hunch.

**The precise next step** (not run here — it needs carry's ladder, not the
Farmer's): re-run `scripts/backtest_funding_lighter.py::run()` parameterised to
carry's rule — PERSIST_H 6, $300 notional, 336h cap, 12 slots, `OPEN_COST`
29bps — over the `[0.1M, 2M)` band, and split the result crypto vs non-crypto.
If the non-crypto half of the thin tier is positive at tier-median friction and
both halves hold, the floor comes down on evidence. Ready to run when carry's
post-(gr) telemetry passes ~30 closes.

## Why nothing was hand-set

This task's hard safety rules permit exactly one DB write — `bot_state`
`'evidence-review'`. Setting a lever writes `fleet-tuning`; the proposal route
writes `tuning-proposals`. Both are outside that permission, and the operator
is not present to widen it. The (kd) amendment grants a *session* direct
shadow-lever authority; it does not override this task's write restriction.
So: measured, priced, and handed over rather than enacted.

---

# Addendum 2 — the min_vol question, SETTLED against the widening (~11:15 AEST)

Operator: *"Proceed."* I ran the measurement rather than the deploy (see the
end of this section). **The result reverses the reframe I published one message
earlier, so it is reported as refuted rather than quietly dropped.**

## The instrument choice, first

`scripts/backtest_funding_lighter.py::run()` is hardwired to the **Farmer's**
ladder — `PERSIST_H 4`, `MAX_HOLD_H 72`, `TAKE_PROFIT 0.04`, `HARD_STOP 0.10`,
`MAX_OPEN 6`, $25 clips. 🌾 carry's close path is different in kind: decay-paid
exit, a −2%-of-notional bleed stop, 336h cap, $300 notional, 6h persistence.
Monkeypatching the constants would have produced a Farmer-shaped replay wearing
carry's numbers — the documented way to get a wrong sign. **Used carry's own
record instead (I14).**

## The measurement — carry's realised return by book liquidity

Every book carry has traded, bucketed by current 24h volume:

| tier | n | mean/trade | t | net |
|---|---|---|---|---|
| **≥ $2M** (admitted today) | 55 | **+0.382%** | **+2.95** | **+$63.09** |
| **< $2M** (would be admitted by the widening) | 28 | +0.095% | +0.75 | +$8.00 |

**And the thin tier is one trade.** Leave-one-out:

| thin tier | n | mean/trade | t | net |
|---|---|---|---|---|
| all | 28 | +0.095% | +0.75 | +$8.00 |
| **drop ARB** (a single close, +3.225% / +$9.67) | 27 | **−0.021%** | **−0.38** | **−$1.68** |
| drop AAVE | 27 | +0.069% | +0.54 | +$5.62 |
| drop BNB | 14 | +0.219% | +0.89 | +$9.21 |

The thin tier's entire positive net is **one lucky trade**. Remove it and the
tier is negative. Same shape as (hl)'s "ZEC+PAXG carry 91% of the delta".

## The reframe was wrong, and here is exactly how

I wrote that carry's $2M floor *"systematically screens out the exact
population carry does best on"*, reasoning that its non-crypto edge plus the
non-crypto composition of the `[1M,2M)` band implied an unlocked win. Split
properly, the two facts do not connect:

| non-crypto | n | mean/trade | t | net |
|---|---|---|---|---|
| **AND ≥ $2M** | 19 | **+0.743%** | **+2.48** | **+$42.34** |
| AND < $2M | 1 (BRENTOIL) | — | — | +$1.09 |

**Carry's entire non-crypto edge lives in LIQUID non-crypto** — SNDK $24.66M,
SKHYNIXUSD $11.55M, SOXL $5.46M, XAU $69.10M, MU $6.86M, WTI $7.68M. Every one
of them is already far above the floor; the floor screens out **none** of them.
What lowering it would actually buy is AMD/GOOGL/INTC/PLTR/US100/US500 at
$1.0–1.8M — thin books, which carry's record prices at **−0.021%/trade**.

Non-crypto and thin are two different populations. I collapsed them.

**VERDICT: `carry.min_vol` stays at 2e6.** Not deferred for want of evidence —
**refused on carry's own record**, robust to leave-one-out.

*Honest caveat:* current volumes applied to historical trades is a proxy; a
book's liquidity at entry may have differed (the floor is checked at entry, so
the thin group is largely "books that have since thinned"). The direction is
strong and the liquid-vs-thin non-crypto split (19 vs 1) is unambiguous about
where the edge sits, but this is not a clean at-entry split.

## One thing this hands forward

💸 the Farmer has **`min-vol-1e5` queued fourth** in the judge's static queue
(~mid-Sep, (ka)), on a proper replay of the Farmer's own ladder — this result
does not refute it. But it is a **prior worth watching**: the fleet's other
funding book, on its own realised record, finds thin books worth
−0.021%/trade. When that experiment reaches the judge's paired bar, this is the
number to read it against. Recorded, not acted on — the judge is the arbiter.

## What was not done, and why

The live deploy (`deploy_live_verify.py`) and any push were **not** run. This
task's hard rules bar deploys, pushes and Railway changes, and CLAUDE.md marks
the real-money row operator-only and explicitly not amendable by editing
doctrine. That remains a one-command operator act, unchanged from the top of
this report.

---

# Addendum 3 — corrections to my own numbers (~12:30 AEST)

Operator: *"Correct anything further."* Three found, all against claims I made
earlier in this report.

## 1. I overstated the disloc defect's history

The report and `(ko)` said *"33 of 37 items … each morning"*. Both wrong:

- **33/37 was the raw append-only FEED at one instant** (it reads 25/29 hours
  later — `fleet_immune` prunes it). The review publishes **one verdict per
  distinct key**: 18 `disloc:` + 1 `census:` = **19**.
- **"each morning" is false.** The previous review ran **2026-08-04
  23:05:56Z**; the publisher's last write was **23:10:59Z — five minutes
  later**. That run's verdicts read *"last event 0.2h ago"* and were **CORRECT**.

So the defect was **latent, not historic**. The first and only wrong
publication was **this morning's run, mine** — 21 active over a 22.6h-stale
census — fixed and republished an hour later in the same session. A guard that
has never yet fired wrong is a smaller claim than one lying for days, and I
should not have borrowed the severity.

## 2. The non-crypto claim is MARGINAL, not `t=+2.54`

`(kl)` had reached the same refusal on a 7-day window (n=3) and named exactly
what would settle it: *"carry's full n=89 ledger under (ki)'s own block
permutation."* I ran the full ledger this morning but used an **iid t-stat**.
Corrected:

| test | result |
|---|---|
| clustering check | **87 distinct close-minutes / 89 closes**, largest batch 2 — carry does NOT batch like ⚖️ |
| block permutation over close-minutes ((ki)'s method) | **P = 0.0088** |
| **symbol-level permutation (7 of 20 symbols)** | **P = 0.046** |

The symbol test is the right one: the label is a property of the **instrument**,
and 13 of the 20 non-crypto closes are one symbol (SKHYNIXUSD). Those are not 13
independent observations of "non-crypto".

**Defensible claim: +0.567pp/trade, symbol-permuted P = 0.046 on 7 symbols** —
suggestive, barely inside 5%. `t=+2.54` read as settled and was not.

**Both practical verdicts are UNCHANGED**, because neither depends on this
claim being strong: don't push `crypto_only` into carry (rests on the *absence*
of harm), and don't lower `min_vol` (rests on the thin-tier result, which is a
different and cleaner measurement).

## 3. Units checked on everything else

After finding a percent-vs-fraction error in my lens harness, I re-derived the
carry figures from first principles: `0.156% × $300 × 69 = $32.29` vs `$32.38`
actual, and `0.724% × $300 × 20 = $43.44` vs `$43.43`. Those hold.

---

# Addendum 4 — (kq): the lens veto was grading 78% of its ledger (~13:40 AEST)

Chasing the last loose end — *"the review says `long-dip` n=13, the taker's veto
input says n=4"* — found the largest defect of the day, in a live-money
actuator's evidence base.

**`realised_lens_evidence` skipped every `exit_reason == "hold"` row**, on the
premise that those are open positions. False of this ledger, three ways:
`fetch_paper_trades` reads only the CLOSED table, hardcodes `is_open: False`,
and the shadow arm's **165 rows carry 165 distinct `trade_id`s with zero
duplicate `(pair, opened_at)` groups**. `hold` is just what `exit_reason()`
returns when no bracket fired. **37 of 165 rows (22%) discarded by exit path.**

It was losing money in **both directions at once**:

| lens | shipped | corrected | effect |
|---|---|---|---|
| `dip` | n=4, −2.485%, t=−2.97 | **n=13, −1.162%, t=−2.66** | **now VETOED** — escaped by falling below the sample floor |
| `breakoutup` | n=13, −1.856% → VETOED | **n=22, −0.242%, t=−0.22** | **un-vetoed** — not a loser |
| `momentum` | absent entirely | n=2 | was invisible |
| `divergence` (live) | 61 / 37 | 74 / 41 | verdict unchanged, evidence 18% short |

**The corroboration was already in the repo.** I14 cites `dip` at
**−1.162%/trade, t=−2.66** — the hold-inclusive number. And the taker's own
selftest asserted *both* tuples without noticing they are the same lens:
`(13, -1.162, -2.66)` → vetoes, `(4, -2.485, -2.97)` → "below the sample floor".
The shipped code produced the second. Doctrine written from the full record;
code drifted; the test encoded the drift as a feature.

**The failing test improved the fix.** My first cut (`if r.get("is_open")`)
reddened `test_open_positions_never_reach_the_realised_grade`, whose middle row
carries no `is_open` key at all — pinning a fail-safe the old clause was really
reaching for. Final rule: **`r.get("is_open", True)`** — absent defaults to
open. Costs nothing in production, keeps the guard, never infers "open" from an
exit label. 3 mutations red; both taker selftest entry points green.

**Shipped and VERIFIED LANDED**: shadow taker CURRENT at HEAD, stamp
`432bd885836d` read back from the running container 165s *after* the workflow
went green — the green run alone would have been a false positive.

**⚠️ The live Taker is now BEHIND-OWN in substance.** It stays DEFERRED behind
its marker gate by design, but the deferral's *content* has changed: it was
shared modules only, and now includes this book's own veto logic. Live trading
is unaffected today (`divergence` is its only lens, verdict unchanged at n=41).
Still an operator act:

    .venv/bin/python3 scripts/deploy_live_verify.py tide-rider-lighter-live
