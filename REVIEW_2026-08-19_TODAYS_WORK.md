# REVIEW — 19-Aug-2026 (Sydney day) · entries (qe) → (rm)

Written ~21:00 AEST 19-Aug. Scope: everything that landed between Sydney
midnight (14:00Z 18-Aug) and now — **88 commits, ~12,100 insertions across 76
files, 8 PRs merged, 28 changelog entries.** Every load-bearing claim below was
re-verified against the live payloads at review time, not carried from the
entries ((rl)'s own lesson: a green PR proves the code is sound; only the
payload proves it is running).

**Fleet state at close of review: 18 rows on /pnl.json, all fresh (worst age
252s); `main` green (Tests / Changelog check / Railway Redeploy all passing on
the (rl) merge); `audit_code_currency` clean — every container CURRENT,
BEHIND-SHARED-only, or DEFERRED behind its marker gate as designed; watchdog
`problems: []`.** Real money: Farmer live $197.31 (+$5.79, 1 open XAU short,
liq 6.4 stop-widths away), Avo live $62.60 (−$0.20, 4 cross longs at 0.62×,
correctly unliquidatable). Real-money config: **unchanged all day** — every
proposal that reached it was measured and refused.

---

## 1 · What shipped, by theme

### Births and growth
- **🧭 nav-cook BORN and (at this review) ACTIVATED** ((re)/(ri)/(rj)/(rm)).
  The [45,60)bps dislocation band strictly below 🪁 band-kelly's floor — the
  two tile, so the (lv) subset-starvation trap is structurally unreachable.
  Measured FIRST to a plateau (t=+2.69..+2.97 at all five horizons, both
  halves positive at every one, ghost-direction control loses at t=−3.53),
  shipped at the plateau interior (4h) for decidability, deep tail refused as
  measured-negative. Birth parity complete in one commit; three sessions
  cooperated correctly on it ((rj) even discarded its own convergent
  `nav-flinders` build as an I20 duplicate — the right call, at real cost).
- **🪁 band-kelly activated, risk-upped, and re-priced in one day**
  ((qh)/(qj)/(qw)/(rc)/(rf)/(qr)). Stamp-verified alive; the operator's
  risk-up ($250×4 clips, dipfade probe at $40×2 under an on-the-record I16
  override, 60bps my-side slip) landed inside the pre-first-close window so
  the whole 30-day sample is single-policy — a week later it would have
  fractured the era. The founding claim was then independently re-derived: it
  **reproduces exactly and survives jackknife** (the first books-cohort
  founding number to do so) but naive negation double-counts execution —
  corrected **+0.605% → +0.397%/trade (t=+3.58)**, the dipfade override
  survives correction (+1.061%, CI lo +0.20%), and (rf) put the corrected bar
  on the surfaces the mid-Sep grader will actually read. **First close landed
  today: n=1, −$3.49** — one close means nothing, but it is now graded against
  the honest bar.

### The retirement
- **👩 mum retired** ((rd)) — I17 `no_rate`: 3 closes lifetime, all three
  opened 12-Jul so ZERO in-era, ~12 months to the 30-close bar, funding drag
  exceeding realised. Deliberately overturns the (nf) "green, slow" hold,
  whose green was **open marks** — the (lo) precedent applied to our own prior
  decision. The retirement exposed five tests that encoded "mum is alive" as a
  fixture premise; all are now roster-derived, which is the durable half.

### Real-money proposals: measured, and all refused (this is the day's spine)
- **(qp)** "adjust the real bot too" → NO: the same resting-rate pin is 96% of
  Garrett's LOSS and 127% of the Farmer's PROFIT. The tier is part of the
  hypothesis. This one refusal likely saved the only profitable real-money arm.
- **(qv)** Hull's floor drop → NO: the drop lands in the exact tier the pin is
  measured to lose in — and the "record" being protected turned out to be a
  replay, not a ledger (Hull has zero realised closes).
- **(qq)** four surfaces priced to ~zero: the Farmer is a directional book
  whose price term never beats random (86.5% of its return is price;
  crossover with funding ~51 years); rank-1 selection nets +0.0003%/trade;
  the allocation claim does not rank forward returns (Spearman ≈ 0); the
  illiquid tail's real signal (P=0.01 gross) is exactly consumed by its own
  measured cost; passive execution inverts under any queue risk.
- **(qn)** the "phantom fee" rescue → the fee is real and already measured
  per-fill; the only genuine defect was a Hyperliquid constant on a Lighter
  book, fixed venue-scoped. No fee-based rescue for carry exists.
- **(qt)** the brain's 8-day `exit_too_tight` on 🔮 georgia → REFUTED by the
  new ladder-aware replay, on the book's own ledger, under both intrabar
  conventions. A wider stop defers ruin rather than avoiding it.
- **(qu)** 🙏 Avo Maria's entry predicts nothing, measured exit-free (random
  beats it at the short end; the one positive cell dies on every
  structure-respecting test) — **operator kept the book, on the record, with
  three falsifiable revert criteria.** A fourth undecidability class named:
  undecidable by flatness (4.9 years to |t|=2).

### Shadow gate moves (operator's "do what makes more money")
- 🛢️ Garrett `FUNDING_ENTER_APR` 0.05 → 0.1095 — a tightening, reproduced from
  its own ledger, live and biting (`gate_apr 0.1095`, cold 191 — verified).
- 🏦 Rich Dad class screen dropped — shipped honestly as UNCONFIRMED with a
  ~7-day tripwire (verified live: `crypto_only: false`, and `noncrypto` still
  0, so the screen has not yet been the binding gate).
- 🌾 carry `PERSIST` 6h → 12h ((qx)) — the parked (px) half, shipped at a
  clean boundary (book empty), era untouched, caps publish it (verified:
  `persist_h: 12.0` live). The ~30-Aug keep-or-retire call rides on nothing.

### Defence for real money, built and deliberately not yet enforced
- **The ruin gate** ((qz)/(rb)): SafetyRails can now refuse an entry that
  would sit within 4 stop-widths of liquidation — the fleet's first instrument
  that can decline on ruin distance. The measured headline: the Farmer at 2×
  and a 10% stop sits **one notch under its own ceiling**; more leverage runs
  through a tighter stop, which is a different book. (rb)'s adversarial pass
  before any live deploy found three real defects in (qz)'s "verified" gate —
  I7 starvation on unliquidatable cross longs (fixed by account-level
  `liq_none` derivation), a fail-OPEN hole on mark-blind priced positions
  (closed at the publisher via `liq_mark_blind`), and seven refusals sharing
  one counter (now `(ok, reason)` over ten codes, renamed `headroom_check` so
  stale callers break loudly). **Correctly still not on the live container**
  — the enforced deploy waits on a real Farmer long observed through the
  publisher classifying as `liq_none`.

### Instruments and guards born today (the compounding layer)
`scripts/mutate.py` (closes the 6-instance stale-bytecode/vacuous-round class,
plus the dirty-target refusal that its own first run needed);
`audit_conflict_markers.py` (mid-line markers — the anchored guard was blind
to a marker at column 43 that shipped through green CI);
`test_workflow_shell_syntax.py` (bash -n on every workflow — the (rl) class);
the pnl-dashboard **reader-verify step** in the redeploy workflow (the (ml)
class, finally executable); `session_commit` verdict-line fix (a correct
refusal was invisible under `| tail`); the letters guard now checks short-form
citations (22 were unverified, 7 predating the session) and tolerates
corrected-in-place titles; carry census `waiting_admissible`; douglas
`sample20` made quarantine-askable; Parliament publish guard (a read blip no
longer writes constructor state into the MTM series the go-live bar reads);
the quarantine now reaches the boot seed path; funding closes now record
`entry_apr`/`accrued` so entry quality is testable at all.

---

## 2 · Incidents — the honest column

1. **GitHub Actions billing lockout** (18-Aug 23:28Z → 19-Aug 04:37Z):
   CI *and the only deploy path* dark for ~5h. The fleet's own watchdog
   diagnosed it before the session did. Operator raised the limit; the burn is
   measured (~7,500–11,000 job-min/mo vs a 2,000–3,000 allowance, dominated by
   changelog-check's 12 × 1-min-rounded jobs) — **it will recur on the current
   structure**; options are priced in (ql), decision recorded.
2. **The fleet froze for 3h and CI said nothing useful** ((rl)): nav-cook's
   commented deploy rule left a stray `fi`; the decide step died at parse time
   and `railway up` ran for NO service from 07:54Z to 10:20Z. Found by stamp
   readback, not by any guard. Now guarded (bash -n test, mutation-verified).
3. **The (rl) residue this review found and closed** ((rm)): the unfreeze
   never caught up the missed **pnl-dashboard** deploy, so the serving reader
   (booted 06:27Z) predated (rj)'s nav-cook registration — the born row was
   publishing invisibly for ~1h+ and, once visible, paged NOT-ONLINE off a
   wrong status string that came from CLAUDE.md's own publish example. Both
   fixed; reader flip verified (started 10:48:29Z, 18 rows, row CURRENT at
   HEAD).
4. **Shared-worktree concurrency tax**: seven-plus letter collisions (every
   one caught by the cross-branch guard pre-main), one entry's text swept into
   a foreign commit (recorded inline, correctly not history-rewritten), one
   committed mid-line conflict marker, and a `head -40` that silently dropped
   the real-money half of a letter renumber (seven citations in
   `lighter_funding_bot.py`/`venues/safety.py` pointing at the wrong entry
   through green CI). Each got a guard or a doctrine rule; the class fix —
   per-session worktrees — is already prescribed and still not the norm.
5. **(qc) follow-through**: the pytest-fabricated ledger row was DELETED
   19-Aug on operator instruction, readback-verified, backup kept.
6. **Session limits ate parts of two audit fan-outs** ((qk): 2 of 8 agents +
   the verify pass; (qe): the final referee wave) — both recorded what was NOT
   swept rather than reporting coverage they didn't have, and (ql) discharged
   the missed organ sweep by hand the same day.

## 3 · Scorecard against the repo's own doctrine

- **Forward metric (rule 4 — which book moved toward the gate?):** 🙏 avo
  shadow remains the only above-bar book (era t≈+2.3–2.4, on_track, window
  pre-registered and hands-off). 🪁 kelly and 🧭 nav-cook both now accrue
  single-policy samples against honest, corrected bars — that is real forward
  motion of the "gradeable books" kind. Nothing moved real dollars today, and
  the day's own audits say why: the measured constraint is **capital**
  ($259.84 at ≈$0/day; 62:1 paper:real), not code.
- **Measure-before-build:** exemplary. Ten-plus substantive refusals with
  numbers; three (qa) growth leads run to closure (all negative — the most
  valuable outcome, per I19: they stay closed); two independent sessions
  measured the same three leads and agreed.
- **Repair ratio:** of 28 entries, roughly 9 are same-day repairs of same-day
  work ((rb)→(qz), (qy)→(qx)-F5 plus its own regression, (rk)→(qk),
  (ra)→own merge, (rg) fallout, (rm)→(rl)/(ri) residues). Better than the
  30-Jul baseline (16 of 40), and the repairs were found by the sessions' own
  adversarial passes rather than by the operator — but most of the residue
  traces to one cause: **parallel sessions in one worktree plus a deploy
  pipeline whose failures don't self-heal.**
- **I12 (doctrine live):** heavily exercised — (qu)/(qw)/(rc)/(rf) corrected
  founding numbers where graders read them; the queue was swept twice; stale
  rows corrected in place with the stale text quoted.

## 4 · Improvements list (ranked, with the evidence for each)

**Now / cheap:**
1. **Per-session worktrees as the actual default** — today's collision count
   is the measured cost (7 renumbers, 1 swept entry, 1 committed marker). The
   script exists (`scripts/new_session_worktree.sh`); the gap is habit. A
   session-start line in CLAUDE.md's own header (or the session brief) that
   *refuses* shared-tree work for new sessions would close it culturally.
2. **Merge or close the five open PRs.** #192 is real work (citation-drift
   guard + the shadow Taker's boot-ladder fix — the Taker currently *stops
   trading entirely during merge storms*; (rg) waived the proxy but only #192
   fixes the mechanism) and its entry letter now collides with main's (rf) —
   it needs a renumber + rebase before merge. #153/#167/#168/#174 are 2–12
   days old with mutation-verified fixes aging out (e.g. #167's Parliament
   boots counter, #168's docket consumer); either land them or close them with
   a reason — five half-houses is exactly the I11 shape.
3. **Deploy catch-up after a red redeploy run** — the class behind today's
   invisible nav-cook: (rl) fixed the parser, the (gm) rule caught up the six
   shadow books by accident, and pnl-dashboard stayed stale until this review
   dispatched it. Cheapest structural fix: the decide step diffs against the
   **last GREEN deploy's SHA per service** (or: a red Railway-Redeploy run
   fails ci-notify with the exact catch-up dispatch command in the message).
   Until then it is a runbook line: *after any red redeploy run, re-dispatch
   the services whose files were in the frozen pushes.*
4. **`sample20` self-description** ((rk) residue) — **SHIPPED same evening
   ((rn))**: `sample20` now publishes `unstamped: N` (always present, incl. 0),
   so the visible n=9-vs-closed=7 disagreement carries its own explanation for
   the ~4 days it persists.

**Structural / this week:**
5. **CI billing structure** — decided-not-done, but the measurement says the
   lockout recurs. When it does, option (a) (12 jobs → 1 job with 12 named
   steps, ~40% burn cut) is priced and loses only the per-guard red/green
   matrix on the PR page.
6. **Ruin gate follow-through** ((qz)/(rb) declared): (a) the path-breach
   backtest (how often would history have breached K=4?); (b) the
   delta-neutral books' REAL single-leg exposure question — the highest-value
   open risk question in the fleet, since a genuinely hedged book's capacity
   is basis-risk-governed; (c) the **mixed book** case (venue short + sub-1×
   long) is unobserved — `_bounded_longs` correctly refuses to certify when
   any short exists, so on a mixed Farmer book an unpriced long would refuse
   all entries again (the exact starvation (rb) measured at 14.3% of shadow
   holding time). The declared enforce-precondition (a real Farmer long
   observed through the publisher) should explicitly include one mixed-book
   observation; and decide `LIGHTER_RUIN_GATE`'s default *before* the next
   marker deploy, because the gate rides along with it.
7. **Reader-currency as a standing check** — **SHIPPED same evening ((rn))**:
   the hourly fleet-watchdog run now asserts `/watchdog.json started` ≥ the
   newest main commit touching the dashboard image's files (30-min grace,
   visible SKIPs, drift-pinned copy of the decide grep's file set) and pages
   through the existing single-issue channel. Verified against today's own
   timestamps: 06:27 reader vs 08:08 commit → STALE; post-catch-up → OK.
   Detection worst case ~2 hourly cycles, vs the ~4.5h this one ran.

**Operator decisions pending (the queue, kept current today):**
8. ⚖️ Counterweight — **~28-Aug pre-registration stands; today's read is
   RETIRE** (no achievable data flips it; even 20 straight +1% closes reach
   only t=+0.70). Do not pre-empt; decide on the date with the number in hand.
9. 💸 LIVE Farmer — the I17 call on real capital ($197): 1,332 days to
   decidability, every exit-tuning escape already refuted, direction never
   beats random ((qq)). Explicitly not a tuning question. If KEEP, record the
   rationale against the P=0.06/0.155 controls.
10. 🙏 Avo LIVE cap ($200 vs $62.60 equity) — restrict-only, zero expectancy
    price, operator-only by doctrine; the one-line command is in the queue.
11. **The capital decision** — restated because every audit today landed on
    it: real money is $259.84 at ≈$0/day, the nearest genuine event is avo's
    gate run (early-Sep, t already passing), and no lever in the codebase is
    worth two orders of magnitude. A deposit-sizing decision (even
    conditional: "if avo passes the gate on date X, fund $Y") would convert
    the fleet's best evidence into its first meaningful real-money position
    with the gate, the judge, and SafetyRails all already in place.

**Watch items (no action, just eyes):**
- 🪁 kelly n=1 (−$3.49) — graded against **+0.397%**, ~mid-Sep; ignore
  single-close noise in both directions ((qu)'s 18.5% lesson).
- 🏦 Rich Dad tripwire: `noncrypto` still 0 → if unchanged through ~26-Aug the
  class screen was never the constraint; revert the env.
- 🛢️ Garrett: pre-registered read pending first closes under the 0.1095 gate
  (5 held / 1 free slot at review).
- 🧭 nav-cook: first census baseline lands with the activation deploy; the
  book pages nothing now that the status string matches the watchdog contract.
- 🎫 taker `exit:hold` and 🙏 avo book-level — the two pre-registered
  winners'-docket windows: **hands off** stays the single highest-leverage
  policy in the fleet.

## 5 · What this review changed (so the record is complete)

Dispatched the pnl-dashboard catch-up (reader-flip verified), activated
nav-cook (decide rule live, AUTO_IMAGES, provisioner deleted), fixed its
status string and the CLAUDE.md publish example that taught it, swept the
three executed items out of the operator queue, and wrote this document.
Entry: (rm) — merged as PR #196, nav-cook redeploy verified by stamp readback
(`ddc83aa0120e`, status `online`, watchdog problems `[]`). A second pass on
the operator's "fix anything remaining" then shipped improvements #4 and #7
above plus the watchdog status-set drift fix — entry (rn). Everything else
above is assessment, not change.
