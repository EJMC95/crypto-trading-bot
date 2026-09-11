# PRE-REGISTRATION — 🎫 the taker's OFFERED set, 11-Sep-2026

Written BEFORE any outcome was computed. Eamon's ask: *"widen metrics and
parameters until you find an edge for it."*

## Why the offered set, and not the taken set

The ledger holds only entries the book TOOK, and it selected them on the very
features a threshold sweep would search. Measured 11-Sep on the same feature
vocabulary: offered `vol_m` p50 **0.49** vs taken **2.67**; offered
`range_pos` spans **[0.84, 1.13]** vs taken **[0.94, 1.01]**. Conditioning on
a variable removes the information in it — which is why `brk_quality` measured
*inversely* related to excess on the taken set. The unconditioned population
is the scout's OFFERED tickets.

## Population

`bot_state_history` key `lighter-market`, via the public `/bus.json?hours=720`
(server caps at **200h**): 2,351 snapshots, 2026-09-02T16:19Z ->
2026-09-11T00:15Z. An EPISODE is a run of consecutive appearances of one
`(lens, sym)`; a gap > **2h** starts a new episode (episodes, not
observations — the fleet's own rule). Measured: **2,768 episodes** —
breakout 1031, divergence 770, dip 693, momentum 274.

## Outcome

Entry at the first 1h venue close at-or-after the episode's first appearance;
exit via `lighter_ticket_taker.exit_reason` IMPORTED, routed by the module's
own `bull_exit(lens)`, bars = the SHIPPED config for that lens, `peak_ret`
tracked bar by bar. Side from the lens's own rule. **DECLARED DIVERGENCE:** 1h
resolution against a ~5-min offer cadence, so entry lags by up to 60 min; the
convention is IDENTICAL across every arm of every contrast below, so it
cancels in the comparison and is bounded by the calibration gate.

## The two questions, both pre-declared

**Q1 — ADMISSION VALUE.** Does the taker's admission decision beat the offered
population? Mean return of episodes it TOOK vs (a) episodes it REFUSED, and
(b) a random draw of the same count from the same lens's offered set.

**Q2 — IS THERE ANY EDGE AT ALL, ANYWHERE IN THE OFFERED SET.** Per lens,
cells at **p25/p50/p75** of each of `vol_m`, `apr_pct`, `chg_pct`,
`prem_bps`, `range_pos`, in BOTH directions, plus crypto/non-crypto, plus 4
UTC-hour buckets. Thresholds come from the offered population's OWN
quantiles, never round numbers chosen by eye.

## The bar — stated before the run

A cell counts as an EDGE only if it clears ALL of:
1. survives **Benjamini-Hochberg at FDR 0.05** across every admissible cell
   tested (m = the full pre-declared count, not the survivors);
2. beats the **permutation max-statistic** — the distribution of the BEST
   cell a pure-noise search of the same shape would have produced;
3. survives **drop-worst-3**, **leave-one-coin-out** and **leave-one-UTC-day-out**;
4. n >= **10** (I21's floor), and its **mde80** is reported beside it so a
   null reads as *"could not detect an edge below X"*, never *"no edge"*.

A cell failing any of these is REPORTED and REFUSED. **Every cell is printed,
survivor or not** — a sweep that prints only its winner is the artifact.

## Refusals declared in advance

Outcome-conditioned quantities (`mae_ret`, `give_back`, `peak_ret`, realised
hold, `exit_reason`) are NOT admissible as cells — I21's trap. They may be
reported.

## Calibration gate — REFUSES, never reports

The harness must reproduce the taker's OWN realised closes over the same
window when restricted to the taken set. Beyond tolerance it prints NO verdict
and exits 2 ((gx)).

## Honest power statement, computed before the run

At the taken set's sd (6.442%/trade) and 80% power one-sided: n=2,768 detects
**0.30%/trade**; n=500 -> 0.71; n=200 -> 1.13; n=80 -> 1.79. So the offered
population can resolve effects roughly 4x smaller than the 167-close taken
set could — which is the entire reason for running this rather than sweeping
the ledger harder.
