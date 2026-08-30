# 🔭 Georgia v3 — GO-LIVE PRE-REGISTRATION

_Written 2026-08-28, **before v3 has a single close**. Eamon, 28-Aug:
**"The minute you find its edge and it works deploy to real money."**_

This file exists so that "it works" is a number agreed in advance rather than a
judgement made after seeing the data. I21's whole finding is that a bucket
crowned on the window that generated it is not evidence; the same trap applies
to a book. **Committed before any result exists**, the `(uv)`/`(uy)`/`(vb)`
pattern.

## The trigger — ALL of these, on v3's OWN ledger

The gate is **imported, never restated** — `scripts/golive_readiness.py` is the
only owner, and if the fleet re-specs it this list moves with it:

| # | bar | why it is here |
|---|---|---|
| 1 | window ≥ 30 days | the operator's original |
| 2 | closes ≥ 30 | ditto |
| 3 | mean per-trade > 0 | ditto |
| 4 | **t ≥ 2.0** | the binding bar, and the one v1 could never reach (t=0.27 at n=212) |
| 5 | BOTH chronological halves positive | v3's replay h2 is materially weaker than h1 (+0.237 → +0.066), so this is the bar most likely to catch it |
| 6 | max drawdown < 15% | MTM-aware `(ia)`, not realised-only |
| 7 | ledger `integrity` clean | one book, one writer `(hp)` — a pooled sample is not a record |
| 8 | **beats a matched-random null `(hm)`** | NOT in the six bars, and required anyway: this is a DIRECTIONAL book, and on this venue a random long earns money for free. A positive mean is not an edge. |

**Bar 8 is the one a future session will be tempted to skip.** It is the
difference between "she made money" and "she has an edge", and it is the exact
check that killed `(ux)`'s sleeve finding on the way to building this book.

## What does NOT count

* **The replay.** Every founding number for v3 is a replay
  (`scripts/study_georgia_v3_entry_2026-08-28.py`). This session's own headline
  is that `(ux)`'s replay edge did not survive georgia's real entries. **The
  record decides (I14)** — v3's own closes, nothing else.
* **A hot window.** I25: a hot 15-close window is followed by −1.674pp with or
  without a change. Judge against her MEAN or against v1 as the control arm,
  never against the stretch that made her look ready.
* **Pooling with v1.** Different entry, different era, different row. v1 is the
  CONTROL and stays on paper; pooling the two would destroy the comparison this
  book was built to make.
* **Bars passed.** 5-of-6 is not "nearly there" — 🔮 georgia v1 was 5-of-6 and
  776 days from the gate, while 🙏 avo passed 4 and was 37 days out. Read
  `mde80_pct` against the mean, not the bar count.

## The earliest date this can fire

Supply is **22.2 episodes/day** across 15 crypto majors (the bot's own
`signals()`, driven on the real tape). At 5 slots on a 4h hold she reaches 30
closes in **~2 days**, and the t-bar in **~13**. So **bar 1 — the 30-day window
— is binding, and the earliest possible go-live is ~27-Sep-2026.** Any earlier
date means a bar was skipped.

## What I do when it fires

1. Re-run `golive_readiness.py` and confirm all 8, on v3's row alone.
2. Run the random-entry null and publish the P-value.
3. Bring it to Eamon with the numbers. **Go-live stays his explicit act** — the
   permanent doctrine is that evidence is senior to permission, and this
   pre-registration is what makes the evidence legible, not a pre-approval.
4. On his word: deploy by the marker route, verify by `extra.build` +
   `build_n` stamp readback, never by a green CI run.

## The honest expectation

**This book may well fail, and that is a valid outcome.** Three things argue
against it, all recorded before the fact:

* 🧘 **book-douglas trades a related thesis and is −0.813%/trade at t=−2.77**
  on its own ledger. A living book contradicting a replay is the strongest
  counter-evidence available.
* The replay's **second half is much weaker than its first** (+0.237 → +0.066),
  i.e. the edge is decaying on the tape it was found on.
* No **slot contention, throttle, long budget, coin veto or StoplossGuard** is
  modelled in the replay, and `(uw)` measured exactly that gap on v1: 1,816
  replay entries showed an edge her 212 real ones did not.

If v3 fails these bars it is retired under I17 on a MEASURED exclusion, and the
$1,000 of paper is what the question cost.

## Revert

`RETIRED_BOOKS` in `lighter_family_bot.py` (the `(mo)` row-scoped pattern — the
module runs three other books and must not be idled). v1 is untouched
throughout and needs no revert.
