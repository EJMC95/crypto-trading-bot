# Lever-Authority Triage — 2026-07-29

**Source:** `scripts/audit_lever_authority.py` full run at `2229b76` (11
findings, 5 warnings, 88 OK). The census asks two questions the growth rail's
health depends on: *can this lever's bound actually change behaviour?* and
*does a P&L-decisive knob sit outside the rail entirely?* This triage sorts
the 11 into decisions, proposals, and declared-OK candidates — each tagged
with WHO decides. Nothing here is enacted; the two material items are
**04-Aug review agenda items** (operator call).

---

## A. Material — for the 04-Aug review

### A1. `live.funding.enter_apr` hi=0.075 is INERT-PINNED below the venue (+ xp twin)

Measured: 93% of the bound's swing is one step, and the **modal funding
population (10.5% TRUE APR, 42.6% of observations) lies OUTSIDE the bound** —
the decisive value sits at 1.4× the lever's ceiling. Consequence: the judge
(the only `live.funding.*` writer) can never *test* an "enter only above
modal" gate; the growth rail's most important entry lever cannot reach where
the venue actually trades. The 21-Jul carry-gate study already measured that
the richer gate (0.20 TRUE on carry) was the fix for the carry book —
the same question for the Farmer is structurally unaskable today.

**Proposal:** widen `hi` from 0.075 to **0.12** (spans the modal 10.5 with
margin; lo unchanged). Risk profile: a bound widening moves no money by
itself — any value inside it still needs the judge's full paired bar (≥7d,
≥30 shadow closes, both halves) to reach the live arm, and the xp twin's
identical widening is what lets the experiment run first. **Operator
sign-off required** (bounds are the cage; the review governs cage changes).

### A2. `EXIT_APR` and `HARD_STOP` are UNLEVERED — and that may be correct

The census's sharpest numbers: `EXIT_APR` decides decay/flip exits = **67.3%
of all closes and 36.2% of gross loss**; `HARD_STOP` decides stops = only
7.7% of closes but **59.5% of gross loss** (n=8 — rare and huge). Neither has
a lever, so the biggest loss-deciders sit outside the learning system.

BUT: this is a **recorded design decision**, not an omission — the 22-Jul
flap fix says "HARD_STOP / EXIT_APR / flip are env-only, never levers,
unchanged", precisely because exit bars snapping mid-position book phantom
gaps, and because stop bars are safety bars. The census and the doctrine are
both right; the resolution is to make the omission DECLARED:

**Proposal (two halves):**
1. Add both to `LEVER_AUTHORITY_OK` with the flap-fix reasoning — the
   audit's own third path ("DECLARE it with a reason that says why the
   omission is CORRECT"). Mechanical; can ship on operator nod.
2. Separately queue a **backtest-first EXIT_APR study** (decay exits are
   two-thirds of closes; the 21-Jul flip-grace study found the entry gate
   was the lever for carry — the Farmer's decay-exit bar deserves the same
   measured look before anyone argues from prose). Study only; no lever.

## B. Engineering — measurement plumbing (safe to ship without the review)

`conviction_hi`, `explore_k`, `slope_gate` (live + xp): **UNMEASURED** — "no
recorded quantity binding: this guard cannot vouch". These need the levers'
decision-time quantities recorded (the same receipts the (dy)/(ed) work gave
the taker's growth knobs) so the census can measure authority instead of
shrugging. Additive telemetry, restrict-nothing. Candidate for a normal
engineering pass; until then the census stays honest about not knowing.

## C. Watch — no action

* `taker.sl_cooldown_h` DARK (n=11 < 30): more closes heal this on their own.
* Five COARSE warnings (`max_hold_h` ×2, `brk_range`, `dip_range`): width
  without observations; two are CENSORED at the book's own cap so measured
  authority is a lower bound. These become measurable when a tuner actually
  walks them — no pre-emptive bound surgery on unobserved width.

---

## 04-Aug review agenda additions (from this triage + today's campaign)

1. **A1**: widen `live.funding.enter_apr` hi → 0.12 (+ xp twin) — yes/no.
2. **A2**: declare `EXIT_APR`/`HARD_STOP` in `LEVER_AUTHORITY_OK` (flap-fix
   reasoning) + queue the decay-exit backtest — yes/no.
3. **Testing campaign ratification** (2026-07-29, PRs #105–#112): the suite
   is 200→299 with 19 ratchet floors and the publish-without-tests policy;
   the live harness runs on every push; Finding-4 seams proceed weekly
   (exit ladder DONE, flatten path next). Ratify the floor doctrine (only
   ratchets up; lowering = operator + CHANGELOG) and the seam cadence as
   standing practice. The blind-selftest lesson (bot_learn: lines executed,
   semantics unguarded — proven by mutation) is the argument for assertion-
   depth over line-% in future coverage claims.

**Added by the 30-Jul research session (evidence in the named docs; all
three are READ-AND-DECIDE items, no code is waiting on them):**

4. **Vol filter, full-depth run CLOSED** (`FUNDING_VOL_FILTER_2026-07-24.md`
   §30-Jul): 455d/n=1390 — halves positive at both slips, maxDD −16 vs
   baseline −53, reverse control h2-negative; the all-thirds bar is
   UNGRADEABLE at depth (the venue's first ~5 months predate a rankable
   cross-section — n=0, stamped `(n0)`). KEEP stands; magnitude stays
   non-canon. Nothing to decide unless the review wants the bar re-specified
   for full-tape windows.
5. **Explore A/B design — all three options now have numbers on one tape**
   (`EXPLORE_ZERO_DIAGNOSIS_2026-07-29.md` §30-Jul): option 2 (DEEP_MAX
   15→8) REJECTED by measurement (tail occupied 4.1% of hours, n=57/180d,
   h1 empty — a relabel, not coverage); option 1 stands as shipped ($2M
   shadow floor; n=787 on genuinely new books, positive at every slip this
   tape); option 3 is the honest fallback. Decision: confirm option 1's
   shadow activation as THE design (or name the fallback).
6. **Per-asset regime gate — evidence-backed HOLD**
   (`REGIME_GATE_PER_ASSET_2026-07-30.md`): disagreement 19–28%/book at
   depth; damage cell decisively protective on TSLA (−2.60/−7.87pp,
   n=7), mildly costly on metals, and SPY/QQQ (the books that motivated
   D5) still ungraded until ~mid-Aug. Recommendation: hold step-2 wiring
   (unchanged from 28-Jul), re-run at SPY/QQQ graduation; keep fail-closed
   (never BTC's gate) for any future non-crypto entry.
