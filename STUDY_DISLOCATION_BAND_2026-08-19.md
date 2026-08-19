# The dislocation surface: the edge is in the band 🪁 band-kelly REFUSES

**2026-08-19 · the [45,60) bps band, measured · a book candidate for the
navigator cohort**

## Why look here

`(qq)` closed four surfaces; the dislocation family was the only one left with a
positive claim. `(qw)`/`(rc)` corrected its expectation. Nothing had tested
whether the surface supports **more than one book** — and 🪁 band-kelly occupies
exactly one cell of it: gate **≥60bps**, exit 40, max hold 2h, **crypto-only**.

## Method

Mirror direction (LONG the premium-rich, SHORT the discounts) replayed on the
scout's own `lighter-market` snapshots — **10,052 snapshots, 5-min cadence,
15-Jul → 19-Aug** — using `prem_outliers` for the signal and `marks` for prices.
Entry lagged 2 snapshots (the ghost's 2-loop confirm). Episodes, not ticks.
Exit: converged below `0.667 × gate`, max hold, or 5% stop. **One round trip of
the book's OWN slippage** charged per coin tier — this is a forward replay, not
a negated realised P&L, so the `(qw)` double-slippage error does not apply.

**Truncation checked first:** `prem_outliers` is hard-capped at 8 entries. The
8th-ranked outlier sits at a median **16.9 bps** (p99 33.5), so a gate of 45 bps
is hidden in only **0.2%** of snapshots. Gates ≥45 bps are safe; 30 bps is
marginal (2.1%) and is reported but not proposed.

## The sweep — net %/trade (t) [n], all instruments

| gate band | 30m | 1h | 2h | 4h | 8h |
|---|---|---|---|---|---|
| [30,45) | −0.003 (−0.07) | +0.008 (+0.14) | +0.048 (+0.64) | +0.071 (+0.90) | +0.074 (+0.87) |
| **[45,60)** | **+0.185 (+2.74)** | **+0.274 (+2.97)** | **+0.320 (+2.69)** | **+0.367 (+2.74)** | **+0.405 (+2.95)** |
| [60,90) | +0.070 (+0.74) | +0.076 (+0.67) | +0.064 (+0.46) | +0.205 (+1.31) | +0.172 (+0.93) |
| [90,150) | −0.030 (−0.30) | −0.022 (−0.18) | −0.037 (−0.22) | +0.032 (+0.17) | +0.033 (+0.15) |
| [150,inf) | −0.179 (−1.34) | −0.359 (−1.57) | −0.311 (−1.11) | −0.407 (−1.08) | −0.497 (−1.23) |
| **[60,inf) = band-kelly's own set** | −0.056 (−0.80) | +0.006 (+0.07) | **+0.073 (+0.61)** | +0.088 (+0.65) | +0.110 (+0.72) |

**[45,60) is a PLATEAU, not a lucky cell** — positive at all five horizons,
t=+2.69..+2.97, monotone increasing in hold. **The deep tail [150,inf) is
NEGATIVE**: the most extreme dislocations do not mean-revert, they break.

## Scrutiny — it survives all of it

| test | result |
|---|---|
| **both halves, all 5 horizons** | H1 t=+1.83..+2.12, H2 t=+1.85..+2.34 — every cell positive in both |
| **jackknife by coin** (4h) | drop H100 (23% of trades) → +0.284%, t=+1.94; every other drop t=+2.16..+3.01 |
| **block bootstrap** (block=8, 4h) | 95% CI **[+0.072%, +0.644%]**, P(>0)=**0.991** |
| **ghost-direction control** | −0.474%, t=**−3.53** — the asymmetry is real, not a sign convention |

## The mechanism, decomposed — and the hazard tested

| class | n | net %/trade | t |
|---|---:|---:|---:|
| commodity | 57 | **+0.566%** | +2.06 |
| Asian equity | 32 | +0.131% | +1.33 |
| **pre-IPO** | 45 | **−0.165%** | −0.49 |
| crypto | 4 | — | — |

**The band is non-crypto by nature** — which is why band-kelly (crypto-only)
cannot reach it, and why this is a genuine I20 tiling rather than the same bet
at a new row id.

**The edge concentrates when the underlying market is CLOSED**: +0.409%
(t=+2.34, n=106) vs **+0.007% (t=+0.02, n=35)** when open. That is the exact
signature of a stale-reference artifact — and the shape `(lk)` was burned by,
where *"a closed underlying market satisfies `PERSIST_H` structurally"* (I7). So
it was tested directly:

**IS THE INDEX FROZEN WHEN THE UNDERLYING IS CLOSED? — NO.** If it were,
`d(premium)` would track `d(mark)` one-for-one. Measured per symbol:

| symbol | regime | corr(dPrem, dMark) | slope | verdict |
|---|---|---:|---:|---|
| BRENTOIL | closed | 0.624 | 0.41 | index moves |
| WTI | closed | 0.773 | 0.64 | index moves |
| SKHYNIXUSD | closed | 0.401 | 0.16 | index moves |
| H100 | closed | 0.056 | 0.00 | index moves |
| UNITREE | closed | 0.687 | 0.48 | index moves |

**No symbol reaches the frozen signature (corr>0.9 AND slope>0.85).** The
premium is a genuine mark-vs-index divergence. *Declared caveat:* oil's index is
**partially sticky** out of hours (slope 0.41–0.64), so some of the closed-hours
premium is index lag rather than mark dislocation — real, but a weaker anchor
than the in-hours case.

## The book this specifies

**Cell:** premium band **[45, 60) bps** — strictly BELOW band-kelly's floor, so
the two tile the surface and neither starves the other (the `(lv)` subset trap
is structurally avoided: this book's admissions are ones band-kelly *refuses*).

**Horizon:** max hold **4h** (the plateau is flat from 2h to 8h; 4h is the
interior, chosen for decidability at ~1.5 closes/day rather than for the maximum).

**Class screen:** exclude **pre-IPO** (measured −0.165% on n=45, the band's only
negative class). Restrict-only, declared as fitted on a small sample, revertible.

**NOT encoded, declared:** the 30 bps band (truncation-marginal and flat), the
[150,inf) tail (measured negative), and any crypto expression (n=4 — band-kelly
owns crypto by I20).

**Honesty gates:** one 35-day window, one regime; `prem_outliers` gives the top-8
only, so the replay sees the extremes of each snapshot; slippage is charged from
the fleet's own tier means, and thin non-crypto books are the fat-tail end of
that distribution (`(qq)`: <$0.1M mean 17.49 bps, p90 398) — this book's
min-volume floor is therefore load-bearing, not cosmetic.
