# STUDY: entry/exit advancement, fleet-wide — census, calibration-gated sweeps, throughput mechanics, conformance
**2026-08-15 · six analysts + five adversarial referees over the shared 62-coin tape and the full paper ledger. Companion to `STUDY_FUNDING_LIFECYCLE_2026-08-15.md`.**

## The census (X1) — where exits earn and burn today, era-scoped, quarantine applied
- EARN: tp/roi family **+$112.35** (n=220); time/hold +$7.65. BURN: the **stop
  family −$128.05 (n=317, 12 books)** — the fleet's dominant loss mechanism,
  unchanged since 30-Jul and larger; flips −$33.04; rebalance −$40.15.
- `decay_paid` — the 30-Jul headline earner — is nearly SILENT in-era: +$1.76
  on n=2 (vs +$86 all-time, of which ≈$6 is (nc) phantom). The earn engine has
  fired once since carry's era reset.
- The `*_sl` 0%-win class GREW: 14 (book,exit) cells across 10 living books,
  −$97.32. The actionable path runs through the (gx) harness — which is why
  the look-ahead fix below matters more than any single cell.
- 🎫 taker era (n=57): the divergence sleeve's problem is the **sl** (−$23.86,
  0% win) not the tp (+$14.46, 100%); era earnings come from breakout HOLDS.
  Actuation stays with the era-scoped realised lens veto (I14/I15).
- 🙏 avo shadow: **all 11 closes are one exit family** (sell_into_strength).
  No stop/ROI/time exit has ever closed a trade — the live arm's downside
  path is UNEXERCISED by shadow evidence. Flagged into live-audit scope.

## The instrument finding (X2, referee-confirmed) — the canonical exit sweeper had an entry-bar look-ahead
`walk_exit` credited the ENTRY bar's full range (pre-entry prices included)
to tp/sl/trail and seeded the trail peak from it. Decision-flipping size on
pm-gillard (the only book that calibrates, n=304): the same candidate rule
reads **+0.319%/trade with the entry bar and −0.396%/trade at LAG-1**. Two
calibrating conventions, opposite verdicts ⇒ the (gx) "widen gillard's sl"
direction is **REFUTED** under the execution-lag doctrine, and CLAUDE.md is
corrected in place. **Fixed**: the walk starts at the first bar opening at/
after entry; mutation-verified; the parliament's own tuner replay already
used the honest convention. Calibration census: **1 of 8 directional books
calibrates** (gillard); the other 7 get no recommendation of any kind.

## The growth step shipped (X3, two referees) — 🙏 avo shadow's cap was binding
- Cap-4 binding **39% of its era at 4/4** (occupancy reproduced exactly;
  at cap at measurement time), with real SwingDip signals firing during
  measured full windows (AAVE 24–25-Jul, LTC 25-Jul). The closes bar — not
  edge — is what holds the fleet's nearest candidate at 4/6 bars (t=2.17
  already passes; horizon was receding at 0.28 closes/day).
- **Shipped: shadow cap 4 → 6** via `FAMILY_SHADOW_MAX_OPEN_OVERRIDES`
  (main()-path env, shadow container only) — ~+25% close rate, closes-bar
  ETA ~64d vs 80d, **no era reset** ((hc) capacity class). Cap 8 was NOT
  supported (one marginal add contradicted by the real timeline; LINK
  pileup) and is not shipped. Marginal expectancy at confidence: UNMEASURED
  (n=2 recovered signals, one-regime tape) — a throughput step on the
  book's own signal, stated as such.
- **The kill-class the referee caught, now pinned by test:** the live Avo
  bot binds the SAME SwingDip instance and sizes its real-money clip as
  equity/max_open — the STRATEGIES literal is LIVE surface and stays 4;
  `tests/autonomy/test_family_shadow_capacity.py` reddens on a casual edit.
- **HELD, with evidence: the FAMILY_COINS widening.** In-sim it DILUTES
  (widened mean 0.54%/trade at cap 4 vs the book's actual 1.64%; outside
  coins stop at 41% vs 12% in-list), it is a 4-book blast radius, and the
  env reaches the live universe if mis-scoped. Revisit only with the cap-6
  sample in hand and a random-entry null on the outside coins.

## Refused and report-only (the referees' knife)
- **Sniper surge cage-tighten: REFUTED** — pooled t=−1.43 misses the bar and
  the clearing sample (t=−2.01) is the non-crypto class (lk) already
  screened: citing it double-counts a closed class. Shipped instead: surge
  admission telemetry (`surge_ratio` + `surge_mult` in force, durable,
  published at close) so the question is measurable at all next time.
- **CXMT quarantine mis-date (X1, confirmed):** the quarantine entry's own
  row (+$0.4242 phantom _sl) closed 28-Jul; the 21–22 window contained ZERO
  rows and admitted the defect into every graded taker sample for 18 days.
  Window corrected to the row it always meant.
- **Barnes for the 4-Sep docket (X6):** quote the cluster-robust t (−1.78 /
  −1.96 $-basis), not the naive −2.52 (legs close in batches; effective
  n≈18). The burn is **xsect crypto LONGS** (era n=22, −1.136%/trade, win
  4.5%, cluster t=−2.20) while shorts are flat — and the parent ⚖️ rode the
  SAME window near-flat on its longs (−0.191%/trade), so regime alone does
  not force it. The class screens do NOT repair the sleeve (crypto-only
  recut loses more). The carry sleeve arrives at 4-Sep with ~0 post-screen
  closes (I17-undecidable, the retired-extreme shape). Any xsect fix is an
  entry-policy change → fresh clock; retiring resets nothing.
- **Books-cohort conformance (X5): PASS across all four** — zero
  validated-vs-shipped drift in douglas/schwager/hull/kiyosaki exit
  geometry; schwager's trail state is restart-durable (loud-crash on a
  failed read). Two hardenings shipped: schwager's trail catch-up now
  replays missed closed bars in order (an outage >4h used to leave the
  trail silently looser than the validated every-bar ratchet), and
  kiyosaki publishes `flip_grace_h` beside its other caps.

## The bundling rule this study surfaces
Any real sl/tp change on a book resets that book's 30-day era. The census
names ~$97 of 0%-win stops across 10 books, but only ONE book calibrates —
so the right sequence is: harness first (done: the look-ahead fix), per-book
calibration second, and exit changes BUNDLED per book (one reset, not many),
each through its own replay gate. Exit changes are not dripped.
