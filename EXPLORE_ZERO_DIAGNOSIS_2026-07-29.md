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

## [2026-07-29 PROCEEDED — mechanism shipped + the slice MEASURED on Lighter's tape]

Operator: "proceed with 1." Shipped: `FUNDING_EXPLORE_MIN_VOL` (inert unless
set below the $10M main floor) widens the EXPLORE pool only — same gate,
persistence, Stage-B/C vetoes, vol filter, quality veto, slope gate,
spread/slip and caps; exploit sizing untouched. Measured
(`scripts/study_explore_slice.py`, 180d top-60, slices by today's turnover,
live rules, both halves, 0.5/2/**5**bps — the pool books are thin, so 5bps
is the honest row):

| slice (n books) | 0.5bps | 2bps | 5bps | both halves? |
|---|---|---|---|---|
| EXPLOIT ≥$10M (11) | +$10.91 | +$2.13 | −$15.43 | no (h2 neg) |
| **POOL $2–10M (9)** | +$20.02 | +$14.24 | +$2.67 | no (h1 −0.3/−3.5/−9.9) |
| POOL $1–10M (22, sensitivity) | +$34.56 | +$25.70 | +$7.99 | **yes, at all three slips** |

- The widened pool measures BETTER than the exploit set on this tape (which
  is itself h2-negative this snapshot — consistent with the harness's known
  day-to-day swing). The $1M sensitivity slice passes both-halves at every
  slip tested, n=1181.
- **Activation recommendation: the pre-registered $2M floor, SHADOW arm
  only** — `FUNDING_EXPLORE_MIN_VOL=2000000` on `funding-farmer-shadow`
  (one env; the code is already in the image after the next dispatch).
  $1M scored better but was the sensitivity run — picking it post hoc is
  the winner's-curse pattern; widening 2M→1M can follow the tuner/judge
  evidence path once explore closes accrue.
- Limits restated: one snapshot, today's-turnover slice membership, and
  real thin-book slip is unmeasured (the 5bps row + the spread/clip-slip
  entry gates + $1k shadow book bound the exposure). The growth promoter's
  bar — not this study — remains the only path to `live.funding.explore_k`.

## [2026-07-30 ALL THREE OPTIONS MEASURED ON ONE TAPE — the design decision has numbers]

The handoff asked for numbers on all three §3d options, not just option 1's
pool. `scripts/study_explore_options.py` (fresh 180d/top-60 fetch, 30-Jul):
option 2 modelled DYNAMICALLY — per-hour |apr| rank within the gated ≥$10M
set (the live Stage-A sort, `lighter_funding_bot.py:2053`; `cross_venue_mult`
is live-only by its own docstring), tail = ranks 9+; option 3 is the
unfiltered ≥$10M book (= the conviction-only status quo, and the baseline).

| row | 0.5bps | 2bps | 5bps | n | halves note |
|---|---|---|---|---|---|
| OPT3 = BASE ≥$10M (11 books) | +$23.86 | +$15.04 | −$2.60 | 1176 | h2 negative at all slips this tape |
| OPT2 TAIL9+ (dynamic) | +$4.18 | +$3.76 | +$2.90 | **57** | **h1 = $0.00 (n=0)** — tail empty all half 1 |
| OPT2 KEPT8 (exploit keeps) | +$24.32 | +$15.54 | −$2.03 | 1171 | ≈ BASE — removing the tail costs exploit ~nothing |
| OPT1 POOL@2M (10 books) | +$21.64 | +$15.73 | +$3.93 | **787** | h1 −1.60/−7.96 at 2/5bps (yes-both at 0.5) |

**Option-2 occupancy (the cadence read, measured over the whole window):**
the gated ≥$10M set averages **5.4 books/h** (max 11); the rank-9+ tail is
nonempty **4.1% of hours**, mean **0.05 books**. 57 harness trades in 180
days is the UPPER bound of what DEEP_MAX=8 could ever feed explore (the
harness enters greedily; live samples K=2) — and its first half is literally
empty.

**Readout, option by option:**
- **Option 2 is REJECTED by measurement**: it manufactures a ~once-per-3-days
  trickle of exploit's weakest-|apr| leftovers (not new coverage — the same
  ≥$10M books), cannot lift shadow cadence (h1 empty), and its only mercy is
  that it also costs nothing (KEPT8 ≈ BASE). The diagnosis's prose
  ("re-labels exploit's leftovers; coverage barely widens") now has numbers.
- **Option 1 stands as shipped** (operator's "proceed with 1", the PROCEEDED
  block above): the only option whose candidates are NEW books — n=787 on a
  disjoint pool, positive headline at every slip on this tape. The halves
  swing with the snapshot (h1 negative at honest slip here; the 29-Jul fetch
  had the same shape — the known day-to-day harness variance), which is
  exactly why activation is SHADOW-arm-only at the pre-registered $2M floor
  and why `live.funding.explore_k` stays behind the growth promoter's bar.
- **Option 3 needs no code**: BASE is its row. Choosing it means renaming
  the A/B honestly (conviction-only) and abandoning the coverage intent —
  the fallback if the shadow probe disappoints, not the default.

*Same limits as the PROCEEDED block (today's-turnover membership, one tape,
greedy-entry rows measure slice quality not live cadence; occupancy is the
cadence-honest number). Decision-grade: the three options now sit in one
table on one tape.*
