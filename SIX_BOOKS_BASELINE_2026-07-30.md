# The Farnham Six — measured starting line, 2026-07-30

> Named 30-Jul at the operator's request, after John Farnham: national champion
> of the farewell tour that isn't. Two of these six have **zero closed trades**
> and are standing retirement candidates that keep not retiring; carry is a real
> comeback sitting five of six bars from go-live. *The Last Time* was not, in
> fact, the last time. Cohort label only — nothing is renamed.

The growth system built across `(fz)`–`(gg)` exists to help six specific books.
This is their state **before** any of it reaches a container, so that in 30 days
"did it work?" is an answerable question rather than a matter of opinion.

> **[RETRACTION, 2026-07-30 — read before using any number below.]** This
> document cites shadow short-divergence at **+3.035%/trade vs regime,
> t=+4.04** as "the fleet's only measured alpha", and uses it to justify the
> ticket-supply widening. **That figure is retracted.** `(gi)` found a THIRD
> era-pooling error one level above the first two: the shadow arm's 10 closes
> span **FOUR distinct bar-sets**, so pooling them was never legitimate. The
> only clean single-policy sample that exists is the LIVE arm's own 11 closes —
> **+0.883%/trade, t=+0.73, 95% CI [-1.81%, +3.57%], straddling zero.**
>
> What survives: the cap-binding observation (dip and divergence each returned
> exactly 6 tickets) is a fact about the SCOUT, not about the edge. So the
> `TICKET_TOP_N` 6 → 12 widening still stands — on the weaker, honest rationale
> of **more sample for an UNDECIDED lens**, not feeding a proven winner. Every
> other finding here was measured independently and is unaffected.

> **[T0 CORRECTION, 2026-07-30 (gl) — read this before running the 30-day
> review.]** The numbers below are the right starting line, but the DATE this
> document implies is wrong for **four of the six books.** `(gl)` measured that
> deploy run `30492918936` resolved only two of the six Railway service names,
> so 🧲 Snap Back, ⚖️ Counterweight, 🎯 Perp Sniper and 🌊 Tide Rider ran the
> OLD code after the merge that was supposed to change them. Their clock starts
> at the **verified deploy**, not at this document's date:
>
> | book | T0 | why |
> |---|---|---|
> | 🌾 Yield Harvester | 2026-07-29 (merge `39e57d15`) | `funding-carry` resolved and deployed |
> | 📊 Index Rider | 2026-07-29 (merge `39e57d15`) | `equities-regime-shadow` resolved and deployed |
> | 🧲 Snap Back | **merge `ed5cce0`** | name was `lighter-dislocation`; real name `snap-back-shadow` |
> | ⚖️ Counterweight | **merge `ed5cce0`** | name was `perps-funding-spread`; real name `counterweight-shadow` |
> | 🎯 Perp Sniper | **merge `ed5cce0`** | name was `lighter-perp-sniper`; real name `perp-sniper-shadow` |
> | 🌊 Tide Rider | **merge `ed5cce0`** | name was `crypto-trend-daily-shadow`; real name `tide-rider-lighter-shadow` |
>
> **Why this matters for the verdict, not just the bookkeeping.** Item 2 below
> says of Counterweight: *"if n rises and t falls, the wider cross-section is
> worse than the hand list and the widening should be reverted."* Grading that
> from the wrong T0 pools old-config trades into the new-config window and can
> manufacture exactly that signal. The four books' windows start at `ed5cce0`.
>
> **The receipt, per book, not per merge:** `extra.caps` present on the row.
> That field exists (`(gd)`) so saturation is observable, and its absence on all
> six is what proved nothing had deployed the first time. A book with no `caps`
> has not started its window, whatever the git log says. The 🚦 go-live card
> (`(gk)`) now publishes each book's per-bar map 6-hourly, so `days` is readable
> without recomputing it by hand — but the card measures the TAPE, not the
> config, so this table stays the authority on which window is which.

**Provenance.** Aggregates from `/pnl.json`; per-trade metrics computed from
`/trades.json?source=paper&limit=5000` (1,677 rows — the full tape; the default
500-row page truncates carry to 27 of its 82 closes, and a baseline computed on
a truncated tape would be worthless). Bars are the `(fk)` go-live gate verbatim:
**≥30 closes, ≥30 days, mean per-trade > 0, t ≥ 2.0, both halves positive,
maxDD < 15%.** Win rate is reported, not a bar.

## The starting line

| Book | n | days | mean% | t | win% | h1 $ | h2 $ | bars | open/cap |
|---|---:|---:|---:|---:|---:|---:|---:|:--|:--|
| 🌾 Yield Harvester | 82 | 18.3 | **+0.248** | **2.58** | 40.2 | +41.42 | +19.70 | **5/6** | **8/8 FULL** |
| ⚖️ Counterweight | 41 | 16.0 | **+0.417** | 0.65 | 51.2 | +0.49 | +4.11 | 4/6 | 10/10 FULL |
| 🧲 Snap Back | 10 | 13.0 | −0.324 | −1.13 | 30.0 | −0.11 | −0.21 | 0/6 | 0/3 |
| 📊 Index Rider | **0** | — | — | — | — | — | — | 0/6 | 2/3 |
| 🌊 Tide Rider | **0** | — | — | — | — | — | — | 0/6 | 1/6 |
| 🎯 Perp Sniper | 1 | 0.0 | +0.289 | — | 100 | 0.00 | −0.03 | 1/6 | 0/4 |

## What this says, book by book

**🌾 Yield Harvester is 12 days from the go-live bar and cannot take another
trade.** It passes five of six bars — n=82, t=**2.58**, both halves positive —
and the only one it fails is the 30-day window (18.3 days elapsed). It is
simultaneously at **8 open of 8**, i.e. completely saturated, turning away every
candidate it grades. On a 40.2% win rate: that is the carry shape `(fk)` rebuilt
the gate to admit, and the reason win rate is not a bar.

> This single row is the strongest case in the fleet for the `(fz)` capacity
> widening (8 → 12). The book does not need a better signal; it needs somewhere
> to put the trades it has already found. Note h1 (+41.42) > h2 (+19.70) — the
> edge is decaying, not accelerating, which is a reason to act now rather than
> a reason to relax.

**⚖️ Counterweight also sits at its structural cap** (10 legs = K=5 × 2) with a
positive mean (+0.417%) that is **not yet significant** (t=0.65). It needs
sample, and sample is exactly what K 5→8 plus a real cross-section buys.

**🧲 Snap Back is negative on n=10** — and n=10 in 13 days is the symptom, not
the disease: a gate set at ~40× its own median residual barely fires. The
`(fz)` re-base (150bps → an adaptive percentile, ~60bps in practice) and the
universe widening (16 → 40) are aimed at making it *gradeable*. It may well
still be a losing book; the point is that right now we cannot tell.

**📊 Index Rider and 🌊 Tide Rider have ZERO closes.** They are not slow
winners or slow losers — they are **undecidable**, and no amount of waiting on
the current configuration changes that. Index Rider's universe went 3 → 10 and
its clip $250 → $100; Tide Rider now ranks by funding. If they still produce
nothing in 30 days, the honest conclusion is retirement, not patience.

**🎯 Perp Sniper has n=1** because its trigger was a one-loop market-set diff.
`(ga)`/`(gf)` gave it two more candidate sources and an exact venue-sourced
listing age. This is the book where the *mechanism* changed most.

## The measurement that is NOT yet possible

`maxDD%` is absent above: the drawdown bar needs the equity path, which the
in-container `scripts/golive_readiness.py` computes with `DATABASE_URL`. It runs
on the fleet's own schedule. Nothing here should be read as a go-live
recommendation — **go-live remains an explicit operator act**, and this document
grades nothing; it records a starting position.

## Regime caveat, which applies to three of the six

Lighter's whole tape is one falling-BTC regime (item 18). Snap Back, Index Rider
and Tide Rider are DIRECTIONAL, so anything they prove here is proven in that
regime only. The funding books (carry, Counterweight) are largely
direction-agnostic and the caveat bites them least — which is consistent with
them being the two that are actually earning.

## What "it worked" would look like in 30 days

Stated in advance so it cannot be rationalised afterwards:

1. **Carry**: ≥30 days elapsed with t still ≥ 2.0 and both halves positive, at
   a cap above 8 — i.e. the widening added trades **without** diluting the mean
   (`grade_book`'s capacity test: quality held while throughput rose).
2. **Counterweight**: n materially above 41 and t moving toward 2.0. If n rises
   and t *falls*, the wider cross-section is worse than the hand list and the
   widening should be reverted — that is a real possible outcome.
3. **Snap Back**: enough closes to be gradeable at all (≥30). Sign unknown and
   that is fine; decidability is the goal.
4. **Index Rider / Tide Rider**: any closes. Zero after 30 days on the widened
   config is a retirement finding.
5. **Perp Sniper**: n > 5 from the surge/young sources, tagged so the two
   sources can be graded separately from listings.

**The honest null result** to watch for: every book trades more and every mean
gets worse. That is what widening looks like when the ranked selector was
already picking correctly, and `grade_book` plus the board's hurting-refusal
exist precisely to catch it and stop.

*Baseline pulled 2026-07-30 from the live endpoints, at branch
`claude/test-coverage-analysis-efv3hp` (`1ad7a22`), BEFORE any of `(fz)`–`(gg)`
reached a container — `extra.caps` is absent on all six rows, which is the proof
of that. That absence stayed true for FOUR of the six through the first merge as
well; see the T0 correction at the top, which is the honest answer to "when did
the 30 days start?".*
