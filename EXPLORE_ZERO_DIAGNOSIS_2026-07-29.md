# EXPLORE-ZERO DIAGNOSIS — 2026-07-29

*Closes the §3d design question from `FLEET_REVIEW_2026-07-28.md` /
`AUDIT_2026-07-29_YESTERDAYS_WORK.md` §6 ("explore samples only below the
deep-scan cut — now the primary hypothesis"). Measured on Lighter's own live
data (venue-pure: `orderBookDetails` + `funding-rates`, the scout's own
endpoints), 2026-07-29 ~02:15Z. Diagnosis only — no entry-logic change here;
the fix options are routed (strategy-surface, backtest-first, operator).*

## Verdict: explore has structurally NEVER had anything to sample. The tail is empty.

The Farmer's explore (Lever 1, `SCAN_EXPLORE_K=2`) coverage-samples from
`ranked_pre[SCAN_DEEP_MAX:]` — i.e. from **below the top-15 of `prelim`**.
But `prelim` is already gated: `|apr| ≥ ENTER_GATE (5% true)` AND
`24h turnover ≥ MIN_VOL ($10M)` AND `hot ≥ PERSIST_H (4h)` AND supported.
Measured funnel, whole venue, one snapshot:

| stage | books |
|---|---|
| active books with funding + stats | 202 |
| `\|apr\| ≥ 5%` (gate only) | 114 |
| `turnover ≥ $10M` (vol floor only) | **11** |
| BOTH (upper bound on `prelim`; persistence shrinks it further) | **3** |
| tail = `prelim[15:]` | **0** |

The tail is empty because **the whole venue has ~11 books above the $10M
turnover floor** — `prelim` can essentially never exceed the deep-scan cut
of 15. Sensitivity: even at `MIN_VOL=$1M` the both-gates count is 11 →
tail still 0. The three current prelim members (SKHYNIXUSD +176%, SNDK
+40%, LIT +30%) are all comfortably inside the top-15.

So: the 24-Jul explore engine shipped sampling an empty set; the 4-day
"cursor never swept" bugs (f7cad49) were real but **irrelevant** — the swept
tail never had a member. The ~40h of post-fix zero-opens is the expected
behavior of the current design, and more waiting will not change it.

## What this means for the growth experiment (important)

- The shadow arm's `SCAN_EXPLORE_K=2` has been an **inert flag** since it
  was set (~25-Jul): the operator's growth A/B (explore+conviction vs live
  defaults) has really been measuring **conviction-only**. Receipts are
  unaffected (they stamp the env lever honestly — `explore_k: 2`), but no
  close has ever been an explore trade (`src=exploit` on every row, which
  is exactly what the ledger shows).
- O6's "watch whether explore's first opens change the [growth-floor]
  arithmetic" will never resolve without a design change — explore cannot
  lift shadow cadence from an empty pool.
- The growth promoter itself is unaffected mechanically (floors are
  cadence-based and honest; the serial-hold from the 29-Jul audit stands).

## Routed fix options (strategy surface — backtest-first, shadow-first, operator's call)

1. **Give explore its own prefilter** (the design intent "coverage-sample
   the universe"): sample from `|apr| ≥ gate` books (114 today) with an
   explore-specific turnover floor (e.g. $1–2M), still through the SAME
   Stage B/C vetoes (candles required, vol/h veto, adverse-trend veto,
   spread + clip-slip gates), the vol-character filter, quality veto and
   caps. Execution quality stays gated; only the *candidate pool* widens.
   This is the option that actually produces explore opens.
2. **Lower `SCAN_DEEP_MAX`** (e.g. 15 → 8) so the existing pool has a tail.
   Cheap, but today that tail would be 0–3 thin-margin books — it mostly
   re-labels exploit's leftovers as explore; coverage barely widens.
3. **Accept explore-zero** and re-scope the growth experiment to
   conviction-only (rename the A/B honestly; drop the explore lever from
   `GROWTH_CAND`/`GROWTH_LIVE` or leave it as a no-op with this doc as the
   record).

Lean: option 1 — it is the only one that delivers the operator's stated
intent ("the scanner needs the freedom … to act"), and every protective
gate stays senior. It changes live/shadow entry candidate selection, so it
takes the doctrine path: backtest on Lighter's tape → shadow first → the
judge's bar. Not shipped here.

*Snapshot caveat: one moment's read. The 11-books-above-$10M figure is the
load-bearing one and moves slowly (turnover is a 24h aggregate); the
`prelim ≤ 15` conclusion held at every sensitivity checked ($1M/$2M/$5M
floors). The ledger corroborates across 5 days: zero `src=explore` closes
ever.*
