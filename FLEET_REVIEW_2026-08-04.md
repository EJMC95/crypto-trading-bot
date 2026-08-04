# Fleet Review — 2026-08-04 (Sydney)

Operator ask: *review of all outstanding matters; doctrine remodel toward how we
make bots win more; works done this week and bug fixes; deep dive on each bot —
nothing running old code, why code gets skipped, ensure every bot (including
ones to come) always gets current upgrades, then optimise each; an inquest into
the pnl dashboard; a deep dive on running operations more efficiently.*

Method: 21 parallel investigation agents (fleet review ×6, per-bot deep dive
×12, dashboard inquest, ops efficiency, stash triage) + live-payload
verification, cross-checked with the live payload senior to every document
(I14). Shipped the same session: **(ix)** the offense-tier doctrine remodel,
**(iy)** the dashboard fixes, **(ja)** the MTM-reader hardening (on top of the
concurrent session's **(iz)**). All verified in the running system.

---

## 1. Where the fleet is (sampled 18:40 AEST, all payloads fresh)

- **Nothing is dead, stale, sick, quarantined or paging.** 22/22 rows fresh,
  watchdog clean, immune quiet, all 27+ bus keys inside TTL.
- **Fleet P&L +$92.31 total; LIVE (real money) +$8.95 on $267.34 equity** (2
  bots). Best book: 🌾 carry +$70.95 (all-time). Worst: ⚖️ Counterweight
  −$16.01 with 16 open (always-in).
- **`ready: []` — no book passes the gate, and every book fails the 30-day
  window bar** because the POLICY_ERA resets (correctly) restarted every clock.
  Nearest: 💸 Farmer pair (4/6 bars, window fills ~16-Aug, needs t≥2), then 🌾
  carry (all-time 5/6, t=2.99, n=87 — but era 31-Jul with **0 in-era closes**:
  the venue's funding distribution has collapsed; one liquid book clears its
  bar and carry already holds it).
- **Code currency: 21/22 rows CURRENT at HEAD**; the live Taker DEFERRED by
  design (nothing in its gap touches its own files). The (io)/(ip) gate0 class
  is closed for real money — both live services verified `source=null`.
- The duplicate-writer saga is **resolved in code and visible in the payload**:
  `funding-carry` runs the book at HEAD, `yield-harvester-shadow` stands by on
  its own key naming the winner. The two containers are a deliberate failover
  pair; stopping one is optional tidiness now.

## 2. The week (28-Jul → 3-Aug, ~105 entries, suite 200 → 840+ tests)

Seven arcs, compressed (full detail in the changelog letters):

1. **Carry double-writer → ONE BOOK, ONE WRITER** ((ho)…(ii)) — two services
   wrote the fleet's only go-live candidate; the guard chain itself failed four
   times before landing; now claim_writer at loop top, `extra.svc` fleet-wide,
   era-scoped integrity, recency-scoped pager.
2. **The gate got preconditions** ((hc)…(ii), (gk)) — POLICY_ERA (101% of
   carry's P&L predated its own accounting fix), ledger integrity, and the gate
   became a publishing organ instead of a command nobody ran.
3. **Exit instrumentation** ((gq)…(gx), (hb)) — exits went from unfalsifiable
   constants to recorded telemetry + a calibration-gated counterfactual sweep;
   first exit lever registered.
4. **The lens-veto breakthrough → I14/I15** ((ij),(ik),(im),(in)) — the veto
   was about to halt the live book's winning lens on a wrong-horizon proxy
   while keeping the significant loser; realised-record-senior veto now live on
   real money, class closed by AST across all three consumers.
5. **Deploy-path hardening** ((gl)…(iw)) — wrong service names, marker-in-body
   deploys, the gate0 60-commit rollback, the 4h post-deploy blackout; ended
   with `audit_code_currency.py`: "which commit is this bot running" is one
   command.
6. **Organ liveness** ((hw),(hx),(ig),(ie),(il)) — the brain died on every run
   for 3 days while publishing fresh vitals; the wrapper built to stop silent
   death caused one; pageability is now a ratcheted, declared property (I13).
7. **Allocation + retirement** ((hv),(if)) — the first organ answering "where
   should the money go" (funding: 3 measured claims; directional: 0 in 867
   closes); Tide Rider retired, freeing a third of the long budget.

**Honest ledger:** ~8–11 of 21 early-Aug entries repaired work shipped the same
day or the day before — flat vs last week. The dominant shape is fixes shipped
without being run once against the live system. The repair-chain lesson is now
enforced by more guards, but the ratio is the number to move.

## 3. Doctrine remodel — THE OFFENSE TIER (shipped, (ix))

Census before: I1–I15 = 5 defense, 8 measurement, 2 process, **0 offense**;
~4–5% of rule text about growth. Every real win-more delivery of the week came
through four repeatable shapes — now invariants, each with grep-verified
executable enforcement:

- **I16 · Capital follows measured claims** — rank on `max(0, mean − 1.28·SE)`,
  never the mean (`fleet_allocation.py::lower_bound` + tests).
- **I17 · Keep every book decidable, or retire it** — a zero-close book is
  undecidable, not slow; probe floor + operator escalation (`PROBE_FLOOR`).
- **I18 · The binding constraint must be a reachable lever** — the (it) class
  (`audit_lever_authority` + registry-subset test).
- **I19 · A widening is paid for in expectancy, through the replay gate** —
  turnover is not a win (`lighter_scout_tuner::MARGIN_HALF`).

Plus five I12 corrections (stale carry stop-order lines, Tide Rider rows,
run_all.sh consumer comments). Doctrine guard: 19 invariants / 18 enforced.

## 4. Per-bot deep dive — currency, parity, optimisation

Full matrix in the deep-dive record; headlines:

- **Currency: every container is CURRENT, deferred-by-design, or shared-only
  behind.** No bot is running old code today. The live Taker's 14-commit gap
  contains zero of its own files.
- **Parity worst offenders:** `claim_writer` exists in exactly 1 of 10 bots
  (doctrine says fleet-wide — the Taker's own docstring names the two-writer
  scenario); unchecked `load_state` seeds-on-failed-read in Counterweight,
  Index Rider, Family; Snap Back's `noconv` embargo doesn't survive a
  redeploy. Best-in-class: 🌾 carry 13/13.
- **The single biggest find: the MTM drawdown bar was dead on arrival** — the
  grader's reader called a store method that never existed, swallowed by a
  blanket except, so all 18 books read "no usable equity series" as if the
  sample floors were the cause. Two sessions found and fixed it independently
  the same evening ((iz) + (ja) hardening; the letter guard caught the
  collision). Floors are real again: first MTM-graded book ~6-Aug, carry
  re-grade ~30-Aug.
- **Why code gets skipped — the taxonomy** (mechanisms a–j, each with guard
  status): no route / wrong name / routing-fix-can't-ship-itself /
  marker-deferral / git-connected second path / per-image file sets / green-run
  ≠ container / billing lockout / restart-wiped state / **shipped-but-inert**
  (the new class j: published detectors nobody reads, registered levers nothing
  can move — the MTM reader was its worst member).
- **Future bots:** stamps, organ routes and two-writer detection are automatic
  by construction. NOT automatic: a deploy route for a new image
  (`AUTO_IMAGES`-only audit) and currency mapping (`ROW_ENTRY` silently skips
  unmapped rows — market-context sits unaudited today). Two small guard fixes
  close both holes (chip spawned).
- **New I12 finding:** five shadow services are git-connected to main with
  Railway auto-deploy active (measured: a genuine second deploy 13 min after
  the workflow's own). Benign while pointed at main — but it is the (io) class
  reloaded. Operator decision: disconnect (consistency) or declare.

**Ranked optimisation plan** (impact ÷ risk; no item contradicts a standing
refusal): ① MTM reader — **done** ((iz)/(ja)); ② snapshot_equity on Farmer+
Taker arms, bundled behind the next marker pushes; ③ Taker era policy-split on
the `policy.sides` stamp (its 38 live closes pool three policies); ④ the two
future-bot guards; ⑤ `load_state_checked` rollout + Index `ref_date` staleness
(its Yahoo feed is 2 sessions stale with zero consumers of the stamp);
⑥ Snap Back: persist `noconv` now, keep-or-retire to operator (t=−2.97, both
halves negative — the strongest retirement case in the fleet); ⑦ gillard
sl-walk expressibility (only candidate with a calibrated counterfactual);
⑧ claim_writer on the Taker; ⑨ sniper source-stamped close tags; ⑩
Counterweight config re-validation (measure-first; its running K=8/45-book
config has no backtest and the book is the fleet's worst).

## 5. Dashboard inquest — verdict and fixes (shipped, (iy))

**No outage.** Service healthy, current, fast server-side. Four confirmed
faults in what the page shows/costs, all fixed and verified by readback:

1. Headline strip asserted the extinct paper fleet ("+0.00 · Trades 0") over
   22 live books → strip now counts the living fleet; eq/P&L split real vs
   modelled.
2. /bus.json was 8.2 MB, uncompressed, history unremovable → gzip (1.1 MB) +
   `?hours=0` (43 KB, verified live).
3. Live station refetched the full 584 KB page every ~13–19s per tab → 30s
   morph floor + gzip.
4. `cap_usd: None` rendered raw → None values dropped.
   Plus: `fleet-allocation` was served NOWHERE — now on /bus.json + the vitals
   roster + declared in `UNPAGEABLE_OK` (the I13 ratchet forced the
   declaration — the guard working as built).

## 6. Operations efficiency — ranked plan

Measured: same-day-repair ratio flat (~40%); deploy-verification labor ~29% of
the week's entries (its tool now exists but is **wired nowhere** —
**[corrected in place 4-Aug per I12: `(jc)` wired it — a `code-currency` job
in the weekly workflow off the public /pnl.json, fail-closed, BEHIND-OWN the
only red; action ① below is DONE on the weekly half, and the daily-review
prompt text is prepared awaiting the operator's paste]**); 26 Railway
services where ~14 are needed (6 retired containers online, `perps-bot`
crash-looping, `nrl-feed` unrelated); 7 of 15 scheduled tasks spent/stale —
four still describe the Kraken fleet retired three weeks ago; CI quota
arithmetic makes the 28-Jul billing lockout recur in any heavy week; CLAUDE.md
carries ~450 lines of compressible archaeology (~5k tokens every session).

Top actions: **①** wire `audit_code_currency` into the daily review + weekly
workflow [implement-now] — **DONE 4-Aug (jc)** (weekly job shipped + guarded;
daily-review line is operator-paste, text prepared); **②** scheduler purge + rewrite the four Kraken-era
prompts [operator — agent prepares texts]; **③** Railway cleanup, one sitting,
guard-first order [operator]; **④** CLAUDE.md archaeology compression pass
[implement-now, separate pass]; **⑤** one-command deploy-and-verify script;
**⑥** merge the three CI test jobs into one runner (~30–40% quota);
**⑦** off-Actions CI-liveness probe in the dashboard watchdog; **⑧** an
`OPERATOR_QUEUE` surface so open operator acts stop scattering.

Already efficient (refusals with evidence): letter discipline (zero collisions
this week until the deliberate cross-session one the guard caught), per-push CI
wall time, run_all.sh cadences, the P1–P6 polling doctrine (holding since
28-Jul).

## 7. Outstanding matters — the verified queue

**Operator decisions (nothing else blocks these):**
1. 🧲 **Snap Back keep-or-retire** — t=−2.97, n=175, both halves negative, and
   the rail structurally cannot restrict it. Strongest retirement case.
2. 🌾 **Carry keep-or-wait** — fresh era × venue stall (0 eligible candidates);
   both levers already refused on measurement. Late-Aug decision.
3. ⚖️ **Counterweight early revert** — its pre-registered "t falling → revert
   widening" criterion is already trending met (t=−0.44 and falling); an early
   revert beats waiting for ~28-Aug. Routes through the board's lever, never
   hand-set.
4. **Allocation re-weight yes/no** — advisory organ says funding $4k→$16k,
   directional $16k→$4k (shadow notionals: changes what the fleet LEARNS).
5. **Railway cleanup** (list in §6; delete order: remove deploy rule → then
   service; `perps-bot` first — it is crash-looping).
6. **Five git-connected shadow services** — disconnect or declare.
7. **Scheduler purge + 4 prompt rewrites** (texts prepared on request; the
   daily-review safety-rules replacement text needs regenerating — the
   original scratchpad is gone).
8. **Stashes: all three fully superseded — safe to drop** (verified file-by-
   file; stash@{0} is exactly the shipped (ca)/(cb) commit and HEAD is
   strictly ahead). One caveat: stash@{2}^3 holds 4 tiny Kraken-era scripts
   existing nowhere else; extract first if zero-loss wanted. Note stash@{0}'s
   settings hunk holds another copy of the un-rotated PG password — **rotation
   remains open and now less theoretical**.
9. **ALPACA zombie publisher** — still writing (measured 22:01 UTC daily ≈
   08:00 Sydney; likely a daily cron near US close on an unidentified host).
10. LuLu `allowInstalled` gap; live Taker/Farmer next marker pushes should
    bundle snapshot_equity + claim_writer (no deploy due on its own).

**Calendar (evidence events, nothing to build):** first MTM-graded book
~6-Aug; Farmer window fills ~16-Aug (needs t≥2); item-18 oracle grades
~mid-Aug (no symbol at n≥20 yet); SPY/QQQ 203-bar graduation ~mid-Aug;
Farnham-Six verdicts ~28-29-Aug; carry gradeable ~30-Aug; Taker ruling needed:
does the (ij) veto change reset its (hm) policy clock? Also: the shadow
Taker's bracket is still being tuned — under (hm) it accrues zero gradeable
closes while the bracket moves; freeze if it is ever to be graded.

**Discharged this week and verified:** live Taker (ij) deploy (landed, stamp
`5e27c751f5b2`); Farmer currency (CURRENT at HEAD); carry unblock (era reset,
(ii)); brain alive (run 379, streaks advancing); dup-writer pager quiet;
`extra.svc` fleet-wide; MTM reader ((iz)/(ja)); dashboard fixes (readback).

---

*Forward metric statement for this pass: no book moved in bars today — what
moved is the instrument panel (MTM bar live again for all 18, dashboard
truthful, allocation visible) and the doctrine now binds future passes to the
offense loop. The next bar that can actually flip is the Farmer's t at
~16-Aug.*
