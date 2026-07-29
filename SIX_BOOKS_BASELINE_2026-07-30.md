# The Six Books — measured starting line, 2026-07-30

The growth system built across `(fz)`–`(gg)` exists to help six specific books.
This is their state **before** any of it reaches a container, so that in 30 days
"did it work?" is an answerable question rather than a matter of opinion.

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
of that.*
