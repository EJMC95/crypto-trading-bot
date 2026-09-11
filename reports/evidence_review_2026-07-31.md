# Evidence Review — 2026-07-31

_Reviewed 2026-07-31T00:59:12+00:00._

## ⚠️ ACTION — needs an operator decision

- 🧬 Taker arms DRIFT: live 0b30b0a79211 vs shadow 6fcb483afaea — the shadow arm is not a clean control while this holds

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| disloc:0G | active | census 414 ev / 277bps (alert 407), last event 0.3h ago, 17 entries |
| disloc:APEX | active | census 3837 ev / 313bps (alert 3837), last event 10.0h ago, 385 entries |
| disloc:BIO | active | census 87 ev / 272bps (alert 87), last event 10.7h ago, 2 entries |
| disloc:CHIP | active | census 179 ev / 160bps (alert 177), last event 0.8h ago, 4 entries |
| disloc:EIGEN | active | census 181 ev / 161bps (alert 179), last event 5.5h ago, 3 entries |
| disloc:GMX | active | census 153 ev / 151bps (alert 152), last event 0.4h ago, 9 entries |
| disloc:KAITO | active | census 1049 ev / 350bps (alert 1033), last event 0.2h ago, 91 entries |
| disloc:NEAR | active | census 20 ev / 150bps (alert 20), last event 30.9h ago, 0 entries |
| disloc:RESOLV | active | census 449 ev / 188bps (alert 447), last event 1.3h ago, 3 entries |
| disloc:SKHYNIXUSD | active | census 644 ev / 414bps (alert 542), last event 0.1h ago, 536 entries |
| disloc:SKY | active | census 92 ev / 315bps (alert 92), last event 9.0h ago, 2 entries |
| disloc:SNDK | active | census 186 ev / 252bps (alert 156), last event 0.5h ago, 102 entries |
| disloc:STABLE | active | census 309 ev / 396bps (alert 309), last event 10.7h ago, 6 entries |
| disloc:STBL | active | census 198 ev / 245bps (alert 198), last event 7.3h ago, 8 entries |
| disloc:ZORA | active | census 223 ev / 202bps (alert 223), last event 29.0h ago, 3 entries |
| factor-sample:6 | resolved | joined decision+context dataset at 260 closes (54% win), bucket 8 |
| factor-sample:7 | resolved | joined decision+context dataset at 260 closes (54% win), bucket 8 |
| veto:CXMT,SKHY | resolved | CXMT,SKHY no longer vetoed |

## New evidence

- 🎫 shadow lens 'short-divergence' at n=84 (≥10): net $+8.85, WR 33%, t=0.8 — noise
- 🎫 shadow lens 'long-divergence' at n=20 (≥10): net $+2.44, WR 45%, t=0.31 — noise
- 🎫 shadow lens 'long-dip' at n=13 (≥10): net $-9.15, WR 15%, t=-2.74 — significant
- 🎫 shadow lens 'long-breakout' at n=10 (≥10): net $+7.72, WR 80%, t=1.73 — noise
- 💰 LIVE perps-funding-lighter-lighter: n=63, net $+7.89 — by lens [('short', 59, 7.38), ('long', 4, 0.51)]
- 💰 LIVE lighter-ticket-taker-lighter: n=26, net $-0.49 — by lens [('short-divergence', 14, 1.41), ('long-divergence', 12, -1.9)]
- 🚦 go-live gates (CANONICAL grader golive_readiness — bars: window, closes, mean, t, halves, maxdd; win rate reported, NOT a bar; retired, already-live and live-twin rows excluded): NO new candidate
- 🚦 fleet-risk light yellow — 21 gross vs long budget 20; 7d DD -0.15%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap +0.025pp (live +0.291% n=41, shadow +0.266% n=51) — no divergence
- 🧬 Farmer arms AGREE: live 705425a83422 vs shadow 705425a83422
- 🧬 Taker arms DRIFT: live 0b30b0a79211 vs shadow 6fcb483afaea — the shadow arm is not a clean control while this holds

## Summary

18 alert keys reviewed: 15 active, 3 resolved, 0 stale. No divergence and no drawdown-governor trigger. 11 new-evidence items scanned.

---

# Human layer — daily review, Fri 31 Jul 2026, 11:09 AEST (Sydney)

*(Times below are Sydney. Fleet internals stay UTC.)*

## ⚠️ ACTION — the operator's calls

**1. 🌾 carry's duplicate writer is STILL LIVE. The guard shipped; the container did not take it.**
`(hp)` (a concurrent session, last night) shipped the sole-writer guard in
`funding_carry_bot.py`. It is **not running**: repo HEAD computes
`c3ca24732445`/15, the live row publishes `fbb926402049`/15 — the **same file
count**, so the same file set, and a different content hash. Per `(fd)`'s own
rule that is a code difference, not a file-set artifact.
`audit_ledger_integrity` still reads **TWO-WRITERS** (7 same-pair overlaps,
deepest 9.14h on HYPE).
- **The decision:** stop ONE of `funding-carry` / `yield-harvester-shadow` in
  Railway. A guard in `main` protects nothing, and a deploy of the guard would
  only make one container stand down — the same outcome, later.
- Until then **no promotion may rest on this book's n or t.** Carried priority
  #2 stays open.

**2. A RETIRED, NON-LIGHTER BOT IS STILL TRADING AND STILL PUBLISHING — 17 days after the cut.**
`equities-momentum-alpaca` updated its `bot_pnl` row **3.0h ago** with **6 open
positions** (ABBV, AMGN, …) on an $86,926 Alpaca **paper** account. Retirement
was done correctly on our side — it is in both `RETIRED_ROWS` and
`LEGACY_BOTS`, so the card is hidden and the row is pruned — which is precisely
why nobody noticed the *process* is alive. The 15-Jul note records that cron as
torn down; it demonstrably is not.
- No fleet capital is at risk and no Lighter book is affected. But it is a live
  non-Lighter trader under a LIGHTER-ONLY mandate, and it is outside this repo
  (project `trading-bot`). **Find and stop the publisher.**

**3. 🎫 Taker arms drift — the control arm is not clean.** live `0b30b0a79211`
vs shadow `6fcb483afaea`, both at `build_n=15`. Same file set, different code.
While this holds, the shadow arm is not a control for the live arm, and
`(hm)`'s live-vs-shadow comparisons inherit it. Redeploying the shadow
(`freqtrade-bots`) is the fix; that is a deploy, so it is yours.

---

## 1. What shipped since yesterday's review — graded against today's data

| Entry | Claim | Verdict today |
|---|---|---|
| `(ho)` sole-writer detector | catches the carry duplicate | **Right, and already superseded** — `(hp)` found it ran in the *publish* block, i.e. after the trading pass. Correctly moved to the top of the loop. |
| `(hp)` guard at loop top | duplicate cannot trade | **Correct in code, INERT in production** — build stamps prove the container is on older code (Action 1). |
| `(hp)` "14 overlaps" → 7 | self-correction | **Confirmed.** `audit_ledger_integrity` independently reads 7, deepest 9.14h. Their retraction of the build-stamp argument is also right: 16 books show multiple stamps from redeploys alone. |
| `(hn)` review imports the gate | review can't drift from the rule | **Half-true, and the half that was missing governed real money — fixed this run.** See below. |
| `(hl)` `snapshot_equity` | MTM clock started 30-Jul | **False for the book it was started for — fixed this run.** Only the two riders were wired. |
| `(hk)` Tide Rider widened | 6 → 16 books | **Landed and then some**: live caps read `universe: 22` of `universe_n: 24`. Still **0 closes**. |
| `(hl)` Index Rider clip $100→$65 | clears the 15% bar | Live caps read `max_open: 9, universe: 9`. Note `max_open == universe`, so **the cap still cannot bind** — `(hl)` made it a literal so the drift guard can see it, which was the stated point, but it remains non-binding in effect. |

### The defect I found and fixed: the review imported the RULE but not the SAMPLE

`(hn)` stopped the review carrying its own copy of the go-live gate. It kept
selecting its own rows — with **no policy-era filter**, which `(hc)` had made a
precondition sitting *in front of* the six bars. Measured this morning, same
database, same minute:

| | review said | canonical grader said |
|---|---|---|
| 🌾 `perps-funding-carry-lshadow` | t=**2.77**, n=**84**, 19.5d, **5/6 bars, ~10.5d away** | n=**59**, t=**0.33**, 13.3d, **three bars short** |

That is the review's single highest-stakes sentence — "ten days from a
real-money decision" — and it was false, in the **promotional** direction, on
the one book nearest real money. Exactly `(hn)`'s own incident one layer down.

**Fixed:** `golive_readiness.era_rows()` is now the single owner of *which
trades count*, and both the grader's loop and the review route through it. The
grader's full live output is **byte-identical** before and after the
extraction. **Verified in the live payload, not just the suite:** the false
near-miss line is gone and the review now agrees — **NO new candidate**.

Five tests name the incident, three mutations verified red. One existing test
(`test_the_era_is_read_off_open_ts_in_the_grading_loop`) was pinning a
*spelling* rather than the wiring and was rewritten to the invariant: a trade
**opened before the boundary and closed inside it must be excluded**.

> **Tooling hazard worth knowing:** `sys.pycache_prefix` on this Mac points at
> `~/Library/Caches/com.apple.python`, **outside the repo**, so
> `find . -name __pycache__` shows nothing and a *restored* source file kept
> running the **mutant's** bytecode. A restored tree ran red and looked like a
> real bug for several minutes. Purge that path between mutation steps.

> **The tree was contested throughout.** My edits were reverted twice by a
> concurrent session's `git reset` — reasonably, since from their side they
> looked like stale autostash (they wrote it up in `(hp)`). What made it cheap
> was keeping a **re-appliable patch script in the scratchpad**: after the
> second wipe the whole change went back in one command.

---

## 2. Fleet state

- **Suite 698 green; `audit_image_imports`, `audit_venue_purity`,
  `audit_lever_bounds`, `audit_deploy_coverage`, `audit_changelog_letters` all
  OK.** `audit_lever_authority` exits non-zero on **26 pre-existing UNMEASURED
  lever declarations** — confirmed unrelated to anything changed today (zero
  references to the touched files). `audit_coverage_floors` only runs where a
  coverage job produced a file; not a substantive failure.
- **`payload.errors` was EMPTY** on both runs — no section failed soft.
- **Go-live: READY none.** Nothing is close once the era is applied. The
  nearest books on evidence are ⚖️ Counterweight (in-era n=28, mean +1.080%,
  t=1.23) and 💸 Farmer live (n=37, +0.412%, t=1.05) — both short of `t>=2`
  **and** the 30-day window.
- **Fleet risk YELLOW** — light yellow, 7d DD −0.15% (governor untriggered),
  `clip_scale` 1.0.
- **Lens grades (shadow taker):** `long-dip` n=13, −$9.15, **t=−2.74,
  significant-negative**; everything else noise. Consistent with the standing
  finding that no long lens has forward edge.
- **Farmer live-vs-shadow gap +0.025pp** (live +0.291% n=41 vs shadow +0.266%
  n=51) — no divergence; arms agree at `705425a83422`.

### Carried priorities — status

| # | Item | Status |
|---|---|---|
| 1 | L2 long-budget veto → growth | **OPEN.** `LONG_BUDGET=20`/`SHORT_BUDGET=12` still bare literals. See Option A. |
| 2 | 🌾 carry duplicate writer | **OPEN — and the guard is not deployed.** Action 1. |
| 3 | Re-grade carry under MTM | **Premise was FALSE; fixed this run.** carry's series never started. Now wired (needs a deploy). Clock starts on next deploy, so the ~30d target slips from ~10 Aug to ~30 days after it lands. |
| 4 | Reconcile three position counters | **OPEN, and today it is decision-relevant.** `long_positions=17` (what the veto reads), exposure `long_n=20`, `gross=21`. One counter says 3 slots free, the other says at budget. Note the counters are cohort-scoped (9 books in `FREQTRADE_BOTS`), which is correct by design — the disagreement is *within* that cohort. |

---

## 3. OPTIONS TO OPTIMISE

Ranked. Two were **implemented this run** (correctness/observability, per the
routing rule); the rest are named with the lever and the evidence.

**A. [DONE this run — CORRECTNESS] Era-scope the review's go-live sample.**
Cost: none. Delivered as better evidence, not a bigger position: the fleet's
only "near-miss" was an artifact, and a real-money conversation that would have
opened in ~10 days now correctly has no trigger.

**B. [DONE this run — OBSERVABILITY] Start the MTM equity series on 🌾 carry and ⚖️ Counterweight.**
Evidence: `bot_state_history` held `:equity` for only the two riders.
Counterweight is the sharpest case in the fleet — **+$7.29 realised over 48
closes vs a published −$27.47, a −$34.76 open loss across 24 legs**, while the
grader scores its maxDD at **0.2%**. Expectancy cost: **none** (publish-only, no
trade behaviour changes). *Takes effect on the next deploy of `funding-carry`
and `counterweight-shadow`; both are on `paths:` auto-deploy, but verify by the
`extra.build`/`build_n` stamp — a green run has never implied a container took
it.*

**C. [PROPOSE — REACH/UNBLOCKING] L2 veto Step 1: env-default and register `LONG_BUDGET`/`SHORT_BUDGET`.**
Current: bare literals `20`/`12` at `fleet_risk.py:165` — the only bounds in
that file not `os.environ.get`-backed, so **the growth rail cannot move them at
all**. Step 1 is `env_default` + registry entry at today's values: **inert on
ship, zero behaviour change**, and it unblocks the lane.
*Not done this run on purpose* — `fleet_risk` governs entries for six books, I
have already shipped one behavioural surface today, and doctrine rule 1 is ship
narrow and verify in the live payload first. Steps 2–3 (edge-ranked admission,
inverse-vol weighting) need replay evidence and **priority #4 resolved first**:
with `long_positions=17` and `long_n=20` disagreeing, an admission policy would
be built on a count nobody has reconciled.

**D. [PROPOSE — CORRECTNESS, prerequisite for C] Reconcile the three counters.**
17 / 20 / 21 from one payload. Cheap to settle and it gates C's Step 3.

**E. [REFUSE — with evidence] More reach for 🌊 Tide Rider.**
It now sees `universe: 22` of 24 and still has **0 closes**. Widening further
is contraindicated for the reason `(gy)` already recorded: a book that cannot
*exit* (35% catastrophic stop as its only price exit) should not be given more
to *enter*. The fleet ran that configuration once — 🏆 Stock Leaders, 3 closes,
all catastrophic stops, −$91.90, retired. **Fix the exit first.** Same verdict
for 📊 Index Rider, whose `max_open: 9` still equals its 9-sleeve universe and
so cannot bind.

**F. [REFUSE — with evidence] Capacity for 🌾 carry.**
Yesterday's concern is stale: live caps read **8 open of 12**, not full. There
is no capacity win here. ⚖️ Counterweight *is* at its structural cap (k=10 → 20
legs, 24 open), but it is carrying a −$34.76 open loss — widening a book while
its open book is the largest unmeasured drawdown in the fleet would be buying
reach with exactly the expectancy the mandate says not to spend. **Wait for the
MTM series (B) to say what that book actually costs.**

**What I checked and found nothing on:** per-book `caps` open-vs-cap for all
six reporting books (only Counterweight is at cap, and it is disqualified by
F); the fleet drawdown governor (untriggered, −0.15%); lens grades (no lens
newly positive); `payload.errors` (empty). No further capacity or reach win is
on offer today that does not cost expectancy.

---

## Which book moved, and by how much

**Honest answer: none moved toward the gate — and one moved *away*, correctly.**
🌾 carry's published position went from a false "5/6 bars, ~10.5 days away" to
its true "three bars short, on a ledger two processes wrote". That is the
forward metric working: the fleet's nearest real-money decision is now measured
on the right sample, and the two things blocking it (a duplicate writer, an
absent MTM series) are both now visible and one is now instrumented.
