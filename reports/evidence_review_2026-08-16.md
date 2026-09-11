# Evidence Review — 2026-08-16

_Reviewed 2026-08-16 10:46 AEST (Sydney) · 2026-08-16T00:46:11+00:00 UTC._

## ⚠️ ACTION — needs an operator decision

- 🧬 Avo arms DRIFT: live e49ba8fa7ed2 vs shadow ca1e4c236fc3 (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:0G | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:APEX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:AVAX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:BIO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:CHIP | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:EIGEN | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:GMX | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:KAITO | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:MU | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:NEAR | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:RESOLV | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKHYNIXUSD | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SKY | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:SNDK | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STABLE | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:STBL | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:WTI | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
| disloc:ZORA | stale | dislocation census publisher `lighter-dislocation-lshadow` is 265.6h stale (> 6h) — 🧲 Snap Back was retired 4-Aug (jh), so this alert is frozen history, not a live condition |
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
- 🚦 fleet-risk light green — longs 10/20, shorts 4/12 (gross 14); 7d DD -0.04%, clip_scale 1.0
- 📏 Farmer live-vs-shadow per-trade gap -0.052pp (live -0.158% n=51, shadow -0.107% n=80) — no divergence
- 🧬 Farmer arms AGREE: live daeb0319eb3d vs shadow daeb0319eb3d (n=16)
- 🧬 Avo arms DRIFT: live e49ba8fa7ed2 vs shadow ca1e4c236fc3 (both n=15, so shared-module code differs, not the file set) — whether the arms' own logic differs is `scripts/audit_code_currency.py`'s call (BEHIND-OWN), not this line's; a shared-module-only gap leaves the control sound and is a deploy question
- 🧬 freqtrade-avo-maria-lshadow differs from the repo on FILE SET, not necessarily code: container ca1e4c236fc3 (n=15) vs repo b34116a3cfe4 (n=16) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 freqtrade-avo-maria-lighter differs from the repo on FILE SET, not necessarily code: container e49ba8fa7ed2 (n=15) vs repo 0f7de7db4f89 (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 perps-funding-lighter-lighter differs from the repo on FILE SET, not necessarily code: container daeb0319eb3d (n=16) vs repo a4081a12741a (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy
- 🧬 perps-funding-lighter-lshadow differs from the repo on FILE SET, not necessarily code: container daeb0319eb3d (n=16) vs repo a4081a12741a (n=17) — a different count means a different COPY set ((fd)); check that image's own Dockerfile before calling it a stale deploy

## Summary

22 alert keys reviewed: 2 active, 1 resolved, 19 stale. No divergence and no drawdown-governor trigger. 16 new-evidence items scanned.

_An earlier report for this day was preserved at `evidence_review_2026-08-16.superseded-1021.md`._

---

# FOLLOW-UP PASS — "do all of it" (same day, after the report above)

The operator asked for all four ranked progressions. Outcome below; two shipped
with tests and mutations, one measured-and-escalated, one dated.

## ✅ 1 · SLEEVE-AWARE GRADING — shipped `(nk)`, commit `2d88ada`

The go-live grader had no concept of a retired sleeve, so 🎸 Barnes was scored on
`n=58 / −$10.52` when **49 closes and −$9.07 belonged to the `xsect` sleeve
`(nf)` retired the day before**. The book that exists is `n=9 / −$1.45`.

Implemented as a **precondition in front of the six bars**, the composition twin
of `(hc)`'s era precondition — and it runs *before* `era_rows`, because a dead
sleeve's policy stamps must not choose which of the living sleeve's trades count.
The book declares (`extra.sleeves.<name>.retired`, which 🎸 already publishes),
the grader derives; nothing is listed in code. Fail-open both ways. The daily
review imports the same filter, pinned by **identity**, so review and grader
cannot diverge the way `(hq)` records them diverging. Verified live: Barnes
leaves the graded table for `below floor n9`, every other book byte-identical.

**The prediction that motivated it is REFUTED, and I've recorded that rather
than quietly banking the fix.** I expected the verdict to soften from
`unreachable` to `undecidable`. It hardens: the carry sleeve is a small but
unusually *consistent* loser, so **t goes −2.19 → −4.47**. What the fix actually
buys is the sample and a **7× correction to the magnitude** the operator is
being asked to retire a book over — not a changed decision. Pinned by
`test_the_verdict_does_not_soften` so the fix's existence can't re-seed the wrong
expectation. 29 tests, 5 mutations all red.

## ✅ 2 · THE FUNDING CENSUS — shipped `(nl)`, commit `5499801`

The entry prefilter sits inside `if open_now < max_open`, so **a book at cap does
not scan at all** — `held: {6}` said exactly what a dead book says (I18).

**First contact answered the question that was unanswerable this morning.**
🛢️ Garrett, at its own bar, 210 books scanned:

| | |
|---|---|
| eligible | **27** |
| free slots | **0** |
| capped | **27** |
| top refused | H100 **+1499.7%**, KAITO −161.2%, ROBO −120.9%, CASHCAT +67.5%, ETHFI +28.0% |
| actually held | four coins at ~10.5% |

Caveats stated in the entry because this number will get quoted: `eligible` is
the **cheap** prefilter (spread/slip vetoes run after it), my reconstruction ran
with persistence off so the live figure will be lower, and a four-figure APR on a
$1.24M book is exactly the shape that turns out to be a listing artifact. What
changed is that the question is now **askable from the payload**.

Read-only is the load-bearing property here — this module places **real orders**.
Pinned by AST three ways: no ordering/state calls; never in an `if`/`while` test
(a reporting instrument becoming an actuator is the `(fz)` failure); and never
inside a cap-guarded branch, which would reproduce the bug. Publish-only ⇒
**main-only** under `(mm)`. 14 tests, 5 mutations all red.

**Correcting my own earlier reasoning:** I refused the Garrett cap raise partly
on "the marginal slot is a ~10.5% coin". The census **refutes** that — there is a
real high-APR tail being refused. The refusal now stands on the missing claim
alone (n=6, `claim = 0.0`), and the census is what will settle it at n≥30.

## 📊 3 · THE EMPTY-CELL CONCENTRATION — measured over 33 days, escalated

Not shipped: re-banding a book changes what the operator commissioned and resets
its `(hm)` clock. But the measurement that makes the decision possible now
exists — **4,903 usable scout snapshots, 14-Jul → 16-Aug, crypto only**:

| Cell | Books | Occupied | Median coins |
|---|---|---|---|
| **carry `vol≥$2M, apr≥20%`** | 🌾 · 🎸carry · 🏦 — **three** | **29.8%** | **0** |
| Hull `$2–10M, 7.82–20%` | 🧮 | 99.9% | 3 |
| Farmer `≥$10M, ≥5%` | 💸 | 99.2% | 3 |
| **Garrett `$0.1–2M, ≥5%`** | 🛢️ — **one, capped at 6** | **100.0%** | **31** |
| — of which `apr≥20%` | | 98.6% | 4 |

**The fleet's funding capacity is allocated almost exactly backwards.** Three
books share a cell that is empty ~70% of the time (median 0). One capped book
covers the only tier that is *never* empty and carries a median of 31 candidates.
🏦 Rich Dad has produced 0 closes in 3 days; 🌾 carry holds nothing and has not
closed since 12-Aug — both are behaving correctly for a cell with no supply.

*(Note: CLAUDE.md records this cell at 6.6% of snapshots. On my definition —
crypto, `|TRUE apr| ≥ 20%`, `vol ≥ $2M`, 33 days — it measures 29.8%. Different
definition or window; the qualitative conclusion is the same and stronger.)*

**The option worth the operator's attention, with its trap named.** Splitting the
thin tier by an APR band would give two differentiated books on real supply —
🛢️ Garrett `[5%, 20%)` (median ~27) and 🏦 Rich Dad `[20%, ∞)` (median ~4,
occupied 98.6%), which is exactly the tiling shape 🧮 Hull's birth used.
**The trap:** Rich Dad at `≥20%` *without* narrowing Garrett to `[5%,20%)`
creates a strict SUBSET running second — the I18 failure that killed 🎸's
`extreme` sleeve after 8 dead days. The two edges must move in the same commit or
not at all. Costs: Rich Dad's `(hm)` clock resets (it has 0 closes, so nothing is
lost) and it stops being "Kiyosaki on the validated carry cell", which is what was
commissioned — **your call, not mine.** 🎸 Barnes is birth-frozen to 4-Sep.

## ⏳ 4 · DATED CHECKS

- **🎸 xsect wind-down — still not due.** Now 01:00Z / 11:00 Sydney; the first
  post-retirement rebalance fires **~04:58Z (14:58 Sydney)**. `audit_book_overlap`
  currently attributes **10 open positions** to Barnes — all retired-xsect legs —
  and 5 of its 7 same-side concentration findings (LTC, SEI, TIA, HYPE, LINK)
  are those legs. **If Barnes is not at 0 xsect positions after 05:00Z, the
  wind-down is broken**, and tomorrow's overlap picture should look materially
  different.
- ⚖️ Counterweight ~28-Aug · 🌾 carry late-Aug · `(my)` MTM cohort ~22-Aug ·
  🛢️ Garrett n≥30 ~27-Aug (and with it, the cap question).

## One thing I noticed and did NOT act on

`audit_book_overlap` flags **XAU ×2 same-side "REAL MONEY IN THE STACK"** — but
the two holders are the live Farmer and *its own shadow twin*. A book and its
control arm are not economic concentration, so this looks like a detector
overstating (`(gl)`'s cry-wolf class). Left alone deliberately: I'd already
changed two surfaces this pass, and forward-motion rule 1 is one surface per
pass. Flagging it rather than fixing it silently.

_Times Sydney (AEST, UTC+10). Fleet internals UTC._

---

# ⚠️ FOUND WHILE PUSHING: CI HAS BEEN RED ON MAIN FOR ~24 HOURS

Not mine, and not the other session's `(nj)`/`(nm)` either — but six commits have
landed on top of it, including all three of mine, so nobody's green/red signal
has meant anything since yesterday morning.

**The breach, identical on every run since `(ne)`:**
`lighter_perp_sniper.py: 80.9% < floor 81%` (`Hold the floors`, tests.yml).
The suite itself PASSES; only the coverage gate fails.

**Diagnosis, with the receipt:**

| commit | | sniper Δ | Tests |
|---|---|---|---|
| `15acd05` | `(nc,nd)` | — | ✅ success |
| `2b5ea6e` | `(my)` | +8 lines | ✅ |
| **`71b7f4f`** | **`(ne)`** | **+42 lines, 0 removed** | ❌ **first failure** |
| `d6c5e8f` … `aaa92a0` | `(nf)`→`(nm)` | — | ❌ ×6, same breach |

`(ne)` added 42 statements to the sniper with no accompanying tests. The
numerator did not move, so the ratio fell 83.5% → 80.9% and crossed the floor.
**Five lines of coverage would clear it.**

**Not fixed here, deliberately.** The guard's own message says *"Add tests to
restore the floor; lowering one is an operator decision with a CHANGELOG
entry."* Writing tests for another session's 42-line feature means guessing at
its intent, and that session is still actively editing eight files in this tree.
This is theirs to close (or yours to lower, with an entry). What I can say
precisely is *which commit, how many lines, and how many are needed*.

**Why it matters beyond the number:** a floor exists so the real-money surface
only ratchets up. A floor that has been breached for a day, with six commits
merged over it, has stopped being a ratchet and become noise — the exact
cry-wolf rot `(gl)` names. I could not tell from CI whether my own three commits
were sound; I had to reproduce the coverage run locally to prove the breach
predated them.

**Also worth a look:** every `ci-notify` run in the window reports `skipped`, so
nothing announced the transition. `(P2)` of the polling doctrine says service
state should be pushed, not polled — a red main for 24h suggests that push is
not arriving.

_Verified: my three commits (`ni`, `nk`, `nl`) are on `origin/main`, entries and
code intact, and the full `tests/autonomy` suite is green against the merged
state including `(nj)` and `(nm)`._
