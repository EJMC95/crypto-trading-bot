# Forward steps — 2026-08-01

Written at the operator's ask: *"make sure what we have learned today is saved
and we can start making forward steps. i would like these bots to grow."*

This is the carried list for the next pass (**I11: finish the house**). Every
item states its measurement, its owner, and what it costs. Delete an item only
when it is DONE or measured obsolete, and say which.

---

## Where the fleet actually is, measured today

| | books | closes | net | books with a measured claim |
|---|---:|---:|---:|---:|
| **FUNDING** | 4 | 297 | **+$72.89** | **3** |
| **DIRECTIONAL** | 16 | 867 | **−$9.21** | **0** |

Per-trade, living books, in-era (opened ≥17-Jul, retired rows excluded):

    side     n     mean%       t     net$
    long   648   -0.158%   -1.78   -3.38
    short  444   +0.062%   +0.78   +8.60

Live real money only: long n=32 **−0.233%**, short n=42 **+0.472%**.

**The honest diagnosis: the fleet has ONE working idea and sixteen books that
have demonstrated nothing across 867 closes.** No book has ever passed the
go-live gate. `READY: none`, and has always been none.

Two things this is NOT:
- **Not a tuning problem.** `(hl)` swept 30 throughput candidates and killed 25;
  the 5 survivors produced zero extra round trips. Nearly every "faster exit" is
  turnover bought with per-bar-day return.
- **Not a capacity problem.** Every book's `extra.caps` was checked today: after
  🌊 Tide Rider's retirement, no book with a graded signal is being denied a
  slot. The long budget sits at 12/20, green.

---

## 1. ~~UNBLOCK 🌾 CARRY~~ — **DONE (ii)**, and it is now REACHABLE

**The fleet's only book with a measured claim can never be READY, ever.**
`golive_readiness` computes `integrity` (`same_pair_overlaps`) over the **WHOLE
ledger** while the six bars are computed over the **POLICY ERA**. A ledger is
permanent, so that check is a one-way latch: 7 overlaps between 17-Jul and
**29-Jul 07:39Z** veto the book forever, against a `claim_writer` guard that
merged **31-Jul 00:52Z**. Zero overlaps since.

The `(hf)` reasoning for the all-time scope was deliberate — *"a second writer is
a property of the book's record, not of the era being graded"* — and it is right
about detection and wrong about **blocking**: a precondition should be evaluated
over the same sample the bars are, or the rule and the data describe different
books (the `(hq)` defect, one layer down).

**Two routes, both a real-money judgement and therefore yours:**

- **(a) Declare the sole-writer guard an ERA RESET for carry** — `POLICY_ERA
  ["perps-funding-carry"] = 2026-07-31`. A pooled window means the earlier sample
  *is not this book's record*, which is at least as invalidating as the
  accrual-basis fix that set the current era. **Cost: a fresh 30-day clock
  (~30-Aug).** Cleanest, uses the mechanism that already exists, and makes the
  eventual grade real rather than argued.
- **(b) Scope the blocking check to the graded era**, keeping the all-time count
  published and printed. Faster, but does not help carry *today* — its overlaps
  fall inside the current era — so it only pays off once the era moves anyway.

**BOTH SHIPPED (ii), on the operator's explicit "full permission".**

- **(b) the correctness half:** the blocking check now runs over the GRADED
  sample; the all-time count is still computed, published as
  `same_pair_overlaps_alltime`, and printed on the book's line, so a historical
  pooling stays visible forever — it just no longer vetoes forever. An ONGOING
  duplicate writes recent trades, and recent trades ARE the era, so detection is
  not weakened. With no declared era the two samples are identical, so it is a
  no-op for every book but the ones that have one.
- **(a) the judgement half:** `POLICY_ERA["perps-funding-carry"] = 2026-07-31`,
  the `claim_writer` merge, with the two-writer measurement in the declaration
  and the superseded accrual reason preserved (an era is the LATEST of every
  invalidating change).

**Live result:** `era 2026-07-31 · 0 of 85 closes count · [ledger: 7 historical
overlap(s) predate this era]`, and **no `TWO WRITERS` block**. Carry restarts its
30-day clock, so its earliest gradeable date is **~30-Aug**. That is the point:
the gate went from *impossible* to *reachable*, and reaching it now costs 30 days
of single-writer evidence. Nothing was promoted; `READY: none` is unchanged.

---

## 2. POINT THE CAPITAL AT THE EVIDENCE *(operator)*

`fleet_allocation` (advisory, moves nothing) measures **3 of 4 funding books with
a positive claim and 0 of 16 directional books with any**, against a split that
is **80% directional**. Its evidence-weighted target inverts the current
allocation: funding $4k → $16k, directional $16k → $4k, with a 25% probe floor
on every living book so nothing is starved to zero.

These are **$1,000 notional shadow books**, so re-weighting changes **what the
fleet LEARNS next, not what it earns**. That is precisely why it matters: most of
the fleet's evidence-gathering capacity is pointed at the class that has produced
none in 867 closes.

---

## 3. THE DIRECTIONAL CEILING IS REGIME, NOT PARAMETERS *(scheduled, ~mid-Aug)*

Lighter's whole 438d tape is **one falling-BTC regime** (BTC −32.9%; the family
regime gate reads risk-off 61.5% of bars). A directional book passing "both
halves positive" passes **by construction** — the drift satisfies the bar, not
the edge (item 18). More Lighter tape cannot fix this; only a different regime
can.

The build order is already **complete**: per-asset oracle → the gate consumes it
→ the family universe carries the venue's 10 non-crypto books. The gate is mostly
closed today by the evidence's own shape, and **SPY/QQQ graduate at the 203-bar
floor around mid-Aug**. That is the next genuine evidence event in the fleet, and
it arrives on books that are already listed and waiting.

**Action: nothing to build. Re-run `REGIME_GATE_PER_ASSET_2026-07-30.md`'s study
at graduation.**

---

## 4. THE STRUCTURAL ASYMMETRY — 4 funding books against 16 directional

If funding is the only class with a measured claim, and it replicates across
arms (the Farmer's shadow carries the strongest claim in the fleet at n=98, and
its LIVE arm carries one too), then the growth move is **more funding surface**,
not more directional tuning.

**This is a BUILD, and it follows the Parliament pattern** — a deliberate new
book, named for an Australian musician per the naming rule, minted only when a
thesis has cleared its bar. The incubator cannot do it: it breeds genotypes
replayed against an existing book's tape and can never create a row.

**Not started. Proposed as the next substantive build**, after item 1 proves the
promotion pipeline works end to end on a book that already exists. Building a
fifth funding book before any book has ever passed the gate would be adding
surface to an unproven pipeline.

---

## 4b. 🎫 THE TAKER HAS A PATH FORWARD — and one step is outstanding *(operator)*

**`(ij)` removed the two things that would have stopped it.** The lens veto was
about to halt the live book on a 4h forward proxy while that lens's own closes
were positive, and simultaneously keep `dip`, the fleet's only statistically
significant loser. Both fixed; doctrine **I14/I15**.

~~The LIVE arm is still on `fd4663d27fb5`~~ — **DISCHARGED (4-Aug review,
I11/I12): the deploy LANDED.** The live row publishes `extra.build =
5e27c751f5b2`, `build_n = 15` — verified by stamp readback in the 4-Aug
per-bot dive and by `audit_code_currency` (verdict: DEFERRED-by-design on
later shared-module commits, zero of its own files in the gap). The (ij)
realised-senior veto protects the live book's lens on real money today.

**Honest limit, carried forward:** +0.176%/trade over n=104 is still inside the
random-short null of +0.2–1.1% `(hm)`. Not a demonstrated edge — a fair chance at
one. The next real evidence is simply more closes under one frozen policy.

---

## 5. Carried, unchanged

- **MTM drawdown re-grade** — `(ia)` folded `mtm_drawdown` into the gate
  (strictly restrictive: takes the worse of realised and MTM), gated behind 200
  samples / 7 days of `bot_state_history '<bot>:equity'`. Series started 30-Jul,
  **window closes ≈10–11 Aug**. Re-grade 🌾 carry first — it is nearest the gate,
  so a stricter drawdown definition lands on it before anyone else.
- ~~🎫 Live Ticket Taker drift~~ — **DISCHARGED (4-Aug review): the live arm
  runs `5e27c751f5b2` (the (ij) build), currency verdict DEFERRED-by-design.**
  Next `[deploy-live-taker]` marker push should bundle `snapshot_equity` +
  `claim_writer` (chips queued 4-Aug); no deploy is due on its own.
- **L2 admission by edge** — reframed by measurement rather than deferred. Longs
  are the measurably negative side, so the fix is *what holds the budget*, not a
  bigger number. With Tide Rider retired the pressure is off (12/20, green), so
  this is no longer urgent. `LONG_BUDGET`/`SHORT_BUDGET` remain bare literals at
  `fleet_risk.py:165` and so cannot be moved by the growth rail — inert to
  register, and worth doing whenever that lane next has an author.
- **The daily review's own SAFETY RULES** need an operator edit — replacement
  text is in the session scratchpad. The harness path classifier blocks an agent
  writing `~/.claude/scheduled-tasks/**`.

---

## What "growth" means here, stated once

The forward metric is **books that can be graded, then go live** — not commits,
not entries, not tests. By that metric the fleet has never moved: `ready: []` on
every run it has ever made.

Today moved three things toward it: the brain can learn again (it had been
amnesiac for 3 days and dead for 14h), a book that consumed a third of the long
budget while producing nothing is gone, and the gate's own instruments stopped
lying in two places. **Item 1 is the one that would make the number change.**
