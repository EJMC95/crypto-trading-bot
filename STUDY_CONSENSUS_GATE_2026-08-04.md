# STUDY — Would a consensus gate have improved any book? (S4 measure-first)

**Date of data window: 2026-08-04** (extraction ~10:05 UTC; trades ledger
complete through 08:37 UTC). Study S4 from OPERATOR_QUEUE.md — *"measure
retrospectively (replay: would consensus-gating have improved any existing
book's closes?) before minting anything."* Operator approved 4-Aug.

## VERDICT UP FRONT — REFUSAL WITH EVIDENCE

**No consensus gate, and no single-signal gate, improves any living book's
expectancy once the random-entry null is applied. The S4 consensus-ensemble
book is REFUSED, and no lever-route proposal is filed.** The deep reason is
not that the fleet's signals are wrong — it is that on this tape they are
**constants**: the venue-stress bar never fired once in 6,090 samples, the
sentinel's market bias was risk-off 91.3% of the time and never once
risk-on, and BTC's oracle direction was never LONG in 1,427 readings. A
consensus of signals that never change state has no variance to gate on —
it can only re-discover "be short on a falling tape", which a random short
already earns for free (+0.2–1.1%/trade, memory:
grade-directional-books-against-a-random-entry-null).

| Option | Rank | Ruling |
|---|---|---|
| (iii) Refusal with evidence | **1 ★** | This document. 84 cells graded; the 2 nominal survivors are decorated noise (see §6). |
| (i) Lever-route proposal on an existing book | 2 | None filed. The only nominal candidate (sentinel-gating ⚖️ Counterweight's long legs) fails multiplicity, is not independent of its sibling cell, and breaks the book's hedged construction (§6.2). |
| (ii) Build the S4 consensus-ensemble book | 3 | Refused. Beyond the null results: the oracle grades 5 of the ~30 tradfi symbols the fleet actually trades, so a fail-closed consensus book would be structurally dark on most of the venue's tradfi tape (§4) — the I7 shape, a gate a book fails structurally. |

**What would change this verdict** (re-run cost is one script, §8):
1. **A second regime.** BTC `dir=+1` has never been observed; gates keyed on
   regime direction have never been seen in their permissive-long state.
   This is item 18 verbatim: a one-regime tape cannot grade a directional rule.
2. **Oracle noncrypto graduation** (SPY/QQQ ~mid-Aug; WTI/XCU/IWM later) —
   today gate (a) covers 1.4% of pm-gillard's closes.
3. **A sentinel bias that varies.** Range observed 17-Jul→4-Aug: [−1.00, 0.00].

## 1 · Method

**Trades.** Full `paper_trades` ledger via Postgres (the `/trades.json`
endpoint caps at 500 rows — it truncates gillard and the dislocation book;
do not use it for this). 2,812 rows; 14 living books with ≥20 in-era closes
(eras read from the `golive-readiness` payload's `era.since`, keyed on the
OPEN — a trade's policy is fixed when it is taken). Excluded for n<20:
carry (1 in-era), sniper (10), dad (7), breakout-4h (6), morrison-4/
avo/swing (below floor pre-era). **The fleet's `LEDGER_QUARANTINE`
(`bot_pnl_store.py:1274`) is applied** — the graded ledger is the record,
and §6.1 shows what happens when it is not. In-era closes graded: **1,126**
(1,170 before quarantine; the 44 removed are the (hm) BOT/CXMT episode).

**Signals.** `bot_state_history` covers every book's whole in-era window:
`regime-oracle` n=1,427 (7-Jul→), `event-sentinel` n=2,399 (17-Jul→),
`brain-stake-mults` n=336 (14-Jul→), `lighter-market` n=6,090 (14-Jul→).
Each trade's OPEN is joined to the latest signal row at-or-before it,
within a staleness cap (oracle 2h, sentinel 1h, mults 8h, stress 30min).
**A stale/dark signal makes the trade UNEVALUABLE for that gate — excluded
from that gate's denominator**, so the cells measure signal CONTENT, not
organ uptime. Side is the `reason` prefix (`long-…`/`short-…` — present on
all 14 books); enter-tag is `reason.split('_')[0]`.

**Gates.**
- **(a) Oracle agrees with side.** Crypto symbol → BTC's `dir` (the family
  bot's validated per-asset pattern); tradfi symbol → its OWN `pairs[sym].dir`
  if graded (only XAU/XAG/NVDA/TSLA/MSTR are); unknown class or ungraded →
  unevaluable. Agree = dir sign matches side. A lenient variant (dir=0
  passes) was also run — §7.
- **(b) Sentinel not strongly against.** Blocked iff (long ∧ `market_bias`
  ≤ −0.5) or (short ∧ bias ≥ +0.5).
- **(c) Venue stress** `lighter-market.stress.med` < 15bps (the taker's bar).
- **(d) Brain mult** for (bot, enter_tag) ≥ 1.0, absent = pass.
- **(e)/(f) Consensus:** ≥2-of-4 / ≥3-of-4, over trades where ALL FOUR are
  evaluable (a vote you cannot cast is not a vote).

**Grading per cell:** kept vs evaluable-all mean %/trade, t, total $, plus:
- `perm_p` — P(random same-size subset of the SAME trades ≥ kept mean), 2,000 draws.
- `perm_p_side` — the same, **stratified by side** (random subsets with the
  kept set's exact long/short mix), 5,000 draws. This is the random-entry
  null control: on a one-way tape "keep shorts" beats mixed subsets for free,
  so the unstratified p decorates the tape, not the gate.
- `halves_ok` — kept beats the baseline in BOTH time-halves of the sample.
A cell is a finding only if delta>0 AND perm_p_side<0.05 AND halves_ok,
surviving §7 multiplicity.

## 2 · The headline: three of the four signals are constants on this tape

Measured over the signals' full history (not just at trade opens):

| Signal | Observation | Consequence |
|---|---|---|
| Venue stress `med` | **0 of 6,090** samples ≥ 15bps (p50 6.1, p90 7.8, max 9.9) | Gate (c) **cannot fire**. Every (c) cell is keeps-everything. |
| Sentinel `market_bias` | ≤ −0.5 in **91.3%** of 2,399 samples; ≥ +0.5 in **0.0%** (range −1.00…0.00) | Gate (b) ≡ "cut longs 91% of the time; never cut a short" — the free-short null in a costume. |
| Oracle BTC `dir` | −1 in 89.1%, 0 in 10.9%, **+1 never** (1,427 rows) | Gate (a) on crypto ≡ "keep shorts, cut every long". For the long-only spot books it cuts **everything** (intraday 0/46 kept, georgia 0/74). |
| Brain mults | payload carries 1–2 (bot,tag) entries at a time; ~93% of trades pass by ABSENCE | Gate (d) is near-vacuous; where it did cut (dislocation 40, gillard 31, abbott 10) delta ≈ 0 or **negative** (gillard −0.014pp). |

This is I7 at fleet scale: a trigger a book satisfies (or fails)
structurally is not a measurement. Note gate (d) separately: the brain's
reduce-mults did NOT identify worse-than-average trades at open time in this
window — an honest negative on the one signal that is supposed to be
book-specific.

## 3 · Coverage (evaluable / in-era closes, quarantine applied)

| book | n | a | b | c | d | all4 |
|---|---|---|---|---|---|---|
| crypto-intraday-15m-lshadow | 46 | 46 | 45 | 46 | 46 | 45 |
| freqtrade-georgia-lshadow | 74 | 74 | 73 | 74 | 74 | 73 |
| lighter-dislocation-lshadow | 176 | 64 | 165 | 175 | 171 | 58 |
| lighter-ticket-taker-lighter | 38 | 19 | 34 | 38 | 35 | 17 |
| lighter-ticket-taker-lshadow | 92 | 52 | 88 | 92 | 88 | 50 |
| perps-funding-lighter-lighter | 55 | 53 | 52 | 55 | 54 | 50 |
| perps-funding-lighter-lshadow | 73 | 65 | 68 | 73 | 72 | 60 |
| perps-funding-spread-lshadow | 56 | 44 | 53 | 56 | 53 | 44 |
| pm-abbott-lshadow | 79 | 36 | 79 | 79 | 79 | 36 |
| pm-albanese-lshadow | 21 | 8 | 21 | 21 | 21 | 8 |
| pm-gillard-lshadow | 280 | **4** | 273 | 280 | 274 | **4** |
| pm-morrison-lshadow | 22 | 11 | 22 | 22 | 22 | 11 |
| pm-rudd-lshadow | 94 | 25 | 93 | 94 | 93 | 24 |
| pm-turnbull-lshadow | 20 | 6 | 19 | 20 | 20 | 5 |

Gates (b)/(c)/(d) are joinable at 93–100% — **the join itself is not the
gap**. Gate (a) is the gap, and it is structural: the oracle grades 21
symbols (16 crypto + XAU/XAG/NVDA/TSLA/MSTR) while the tradfi-heavy books
trade SKHYNIX, SAMSUNG, TENCENT, SNDK, MU, WTI, BRENTOIL, SOXL, NBIS,
SPCX, CXMT… — so gillard's oracle coverage is **1.4%** and the consensus
(all4) sample on four PM books is single-digit. A consensus-ensemble book
inheriting the family bot's fail-closed rule would simply not trade most of
the venue's tradfi tape. Verdicts on cells with all4 < 10 are not issued
(sample<10 in the table).

## 4 · Full table

%/trade means; delta = kept − all; `pSide` is the side-stratified null.
Degenerate cells (keeps-everything / cuts-everything) shown collapsed.

```
book                            g    n  kept  meanAll  meanKept   delta  tKept     $all    $kept  perm_p   pSide halves
crypto-intraday-15m-lshadow     a   46     0    0.035      nan      nan    nan    -0.55     0.00     nan     nan   None  cuts-everything
crypto-intraday-15m-lshadow     b   45     1    0.006   -2.691   -2.697    nan    -0.88    -1.35   0.953   0.959  False
crypto-intraday-15m-lshadow     c   46    46  — keeps-everything
crypto-intraday-15m-lshadow     d   46    46  — keeps-everything
crypto-intraday-15m-lshadow     e   45    45  — keeps-everything
crypto-intraday-15m-lshadow     f   45     1    0.006   -2.691   -2.697    nan    -0.88    -1.35   0.953   0.959  False
freqtrade-georgia-lshadow       a   74     0    0.129      nan      nan    nan     6.25     0.00     nan     nan   None  cuts-everything
freqtrade-georgia-lshadow       b   73    13    0.139    0.302    0.163  0.845     6.40     2.26   0.293   0.298  False
freqtrade-georgia-lshadow       c/d/e — keeps-everything
freqtrade-georgia-lshadow       f   73    13    0.139    0.302    0.163  0.845     6.40     2.26   0.293   0.298  False
lighter-dislocation-lshadow     a   64    38   -0.608   -0.466    0.142 -4.614    -3.89    -1.77   0.050   0.817  False
lighter-dislocation-lshadow     b  165   120   -0.289   -0.166    0.123 -1.514    -4.89    -2.12   0.021   0.155   True
lighter-dislocation-lshadow     c  175   175  — keeps-everything
lighter-dislocation-lshadow     d  171   131   -0.283   -0.273    0.009 -2.300    -4.96    -3.70   0.422   0.300  False
lighter-dislocation-lshadow     e   58    55   -0.642   -0.643   -0.001 -5.902    -3.72    -3.54   0.428   0.557  False
lighter-dislocation-lshadow     f   58    36   -0.642   -0.520    0.122 -6.263    -3.72    -1.87   0.089   0.346  False
lighter-ticket-taker-lighter    a   19    13    0.932    1.825    0.894  1.803     2.06     2.73   0.049   0.079  False
lighter-ticket-taker-lighter    b   34    22    0.281    1.297    1.016  1.662     1.39     3.29   0.015   0.788  False
lighter-ticket-taker-lighter    c/d/e — keeps-everything
lighter-ticket-taker-lighter    f   17    14    0.967    1.403    0.436  1.385     1.93     2.25   0.105   0.710  False
lighter-ticket-taker-lshadow    a   52    16    0.376    2.307    1.931  2.509    14.04    13.12   0.012   0.550   True
lighter-ticket-taker-lshadow    b   88    41    0.016    0.586    0.570  0.948    12.44    12.18   0.093   0.772  False
lighter-ticket-taker-lshadow    c/d/e — keeps-everything
lighter-ticket-taker-lshadow    f   50    21    0.352    1.745    1.392  2.074    11.82    14.02   0.016   0.748   True
perps-funding-lighter-lighter   a   53    40    0.436    0.228   -0.208  0.666     4.86     1.86   0.907   0.927  False
perps-funding-lighter-lighter   b   52    50    0.379    0.371   -0.008  1.237     4.30     4.07   0.601   0.815  False
perps-funding-lighter-lighter   c/d/e — keeps-everything
perps-funding-lighter-lighter   f   50    48    0.434    0.428   -0.006  1.401     4.58     4.34   0.595   0.730  False
perps-funding-lighter-lshadow   a   65    53    0.242    0.108   -0.135  0.418     4.81     1.71   0.887   0.901  False
perps-funding-lighter-lshadow   b   68    63    0.277    0.277    0.000  1.078     6.62     5.46   0.484   0.858  False
perps-funding-lighter-lshadow   c/d/e — keeps-everything
perps-funding-lighter-lshadow   f   60    58    0.269    0.275    0.006  1.046     4.92     4.78   0.434   0.352  False
perps-funding-spread-lshadow    a   44    19    0.647    1.816    1.169  1.408     5.95     7.04   0.098   0.597   True
perps-funding-spread-lshadow    b   53    33   -0.470    0.225    0.695  0.169    -4.51     1.89   0.159   0.030   True
perps-funding-spread-lshadow    c/d/e — keeps-everything
perps-funding-spread-lshadow    f   44    27    0.647    2.133    1.486  1.939     5.95    11.66   0.006   0.032   True
pm-abbott-lshadow               a   36     9   -0.140   -0.153   -0.014 -0.731    -1.19    -0.16   0.519   0.622  False
pm-abbott-lshadow               b   79    54   -0.224   -0.146    0.078 -1.054    -3.23    -1.24   0.152   0.673   True
pm-abbott-lshadow               c/e — keeps-everything
pm-abbott-lshadow               d   79    69   -0.224   -0.230   -0.006 -2.012    -3.23    -3.03   0.573   0.453  False
pm-abbott-lshadow               f   36    22   -0.140   -0.096    0.043 -0.619    -1.19    -0.35   0.352   0.903  False
pm-albanese-lshadow             a/e/f — sample<10
pm-albanese-lshadow             b   21    17    0.406    0.630    0.225  0.698     2.03     2.31   0.349   0.535   True
pm-albanese-lshadow             c/d — keeps-everything
pm-gillard-lshadow              a/e/f — sample<10 (oracle covers 4 of 280)
pm-gillard-lshadow              b  273   201   -0.116   -0.048    0.067 -0.572    -6.24    -2.26   0.053   0.191   True
pm-gillard-lshadow              c  280   280  — keeps-everything
pm-gillard-lshadow              d  274   243   -0.116   -0.130   -0.014 -1.648    -6.25    -6.28   0.699   0.817  False
pm-morrison-lshadow             a   11     4   -0.230   -1.111   -0.881 -3.007    -0.28    -0.76   0.806   0.763  False
pm-morrison-lshadow             b   22    18   -0.301   -0.131    0.170 -0.193    -1.37    -0.30   0.317   0.886  False
pm-morrison-lshadow             c/d/e — keeps-everything
pm-morrison-lshadow             f   11    10   -0.230   -0.280   -0.050 -0.405    -0.28    -0.35   0.811   0.849  False
pm-rudd-lshadow                 a   25     2    0.318    0.483    0.164    nan     1.54    -0.07   0.398   0.330  False
pm-rudd-lshadow                 b   93    50   -0.112   -0.165   -0.053 -0.773    -1.10    -0.64   0.674   0.626  False
pm-rudd-lshadow                 c/d/e — keeps-everything
pm-rudd-lshadow                 f   24     7    0.352    0.744    0.392  0.691     1.62     1.00   0.225   0.840   True
pm-turnbull-lshadow             a/e/f — sample<10
pm-turnbull-lshadow             b   19     8    0.042   -0.570   -0.613 -1.204     0.41    -0.69   0.952   0.925  False
pm-turnbull-lshadow             c/d — keeps-everything
```

## 5 · Multiple-comparisons honesty

84 nominal cells → **38 informative** (a computable p; the rest are
keeps-everything, cuts-everything, or sample<10). At p<0.05 the luck
expectation across 38 cells is **~1.9 false positives. Observed survivors of
`pSide`<0.05: exactly 2** — Counterweight (b) 0.030 and (f) 0.032 — and they
are **not independent** (the (f) kept set is largely the (b) kept set on the
same book; a 3-of-4 vote where (c) always passes and (d) almost always
passes is mostly gate (b) again, seconded by (a)). Two correlated hits at
p≈0.03 in 38 draws is the textbook decorated-noise outcome the study
pre-committed to name. Every OTHER raw-p "winner" (dislocation b 0.021,
taker-live b 0.015, taker-shadow a 0.012 / f 0.016, fundspread f raw 0.006)
collapses under side-stratification to 0.15–0.79 — they were all the tape's
short drift, not selection skill.

## 6 · The two autopsies

### 6.1 · Taker-shadow gate (a): the quarantine save (a finding about method, not signal)

Run WITHOUT the fleet's `LEDGER_QUARANTINE`, this was the study's star cell:
kept 18/96, mean +1.99% vs −0.09%, plain perm_p **0.0002 even
side-stratified**. Decomposed: the cut set was **42 rows of the single
BOT/USDC mark-basis-bug episode** (21-Jul 23:19→22-Jul 03:41 — one episode,
not 43 trades, (hm)) plus 4 genuine shorts. Ex-BOT: kept 16 mean +2.31% vs
cut 4 mean **+2.57%** — the cut shorts did BETTER; the oracle had zero
discriminating content. The gate "worked" by happening to time-exclude one
already-quarantined instrumentation bug. With the fleet's own quarantine
applied (as every fleet grader applies it), the cell reads pSide=0.550.
Three doctrines converged on the same catch: episodes-not-trades, the
record decides (I14), and pick-a-test-that-could-detect-the-damage.

### 6.2 · Counterweight (b)/(f): construction-breaking, baseline-selected, luck-sized

The nominal survivor. Gate (b) on ⚖️ Counterweight cut 20 of 27 LONG legs
(bias ≤ −0.5) and kept all 26 shorts. Three refusals:
1. **It un-hedges the book.** Counterweight is top-K/bottom-K funding-rank
   L/S — its trades are LEGS. Cutting 74% of long legs while keeping every
   short converts a market-neutral book into a short-tilted directional one
   on a falling tape, which is the random-short null (+0.2–1.1%/trade free)
   collected by construction, not signal content. The "improved" book is a
   different, unvalidated strategy — the same class of error as grading a
   bracket book on a 4h proxy (I14): the number is real, the object graded
   is not the book.
2. **The (f) baseline is organ-uptime-selected.** Its all4 sample (44/56)
   excludes 12 early-era trades worth **−$9.64** (pre-sentinel-history and
   oracle-dark windows), so meanAll reads +0.647 while the true in-era book
   mean is −0.361. The gate is partly credited with an exclusion the
   signals did not make.
3. **Luck-sized and concentrated.** §5; and the kept longs are n=7 with the
   single best trade (ENA long +13.94%) carrying the half of the delta that
   stratification can see.

For completeness: kept LONG legs +2.34% (n=7) vs cut LONG legs −1.62%
(n=20) hints the sentinel MIGHT time long-leg entry on this one book — but
that is 27 legs, one book, p≈0.03 with 38 cells shopped, on a signal that
is a constant 91% of the time. If it is real it will still be there when
the bias distribution has two states; it is not actionable now.

## 7 · Robustness: the lenient gate (a)

To pre-empt "the strict definition did it": rerun with dir=0 = pass
(neutral does not veto). No book reaches pSide < 0.36. Best deltas
(taker-shadow +1.11pp pSide=0.54, Counterweight +1.11pp pSide=0.36) are
side-mix artifacts. The conclusion does not depend on the strict form.

## 8 · Reproduction

```bash
cd "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot"
export DBURL=$(railway variables --service Postgres --kv | grep ^DATABASE_PUBLIC_URL | cut -d= -f2-)
# 1) trades (the /trades.json endpoint caps at 500 rows — use the DB):
#    SELECT bot, trade_id, pair, side, tag, reason, pnl_abs, pnl_pct,
#           opened_at::text, closed_at, extra::text FROM paper_trades ORDER BY opened_at
# 2) signals from bot_state_history (subfields only — lighter-market payloads are huge):
#    SELECT ts::text, payload->'pairs'                                  WHERE key='regime-oracle'
#    SELECT ts::text, payload->'market_bias', payload->'sector_bias'    WHERE key='event-sentinel'
#    SELECT ts::text, payload->'mults'                                  WHERE key='brain-stake-mults'
#    SELECT ts::text, payload->'stress'                                 WHERE key='lighter-market'
# 3) eras: golive-readiness payload (books[bot].era.since), /bus.json
# 4) filters: era keyed on OPEN; bot_pnl_store.LEDGER_QUARANTINE applied;
#    reason-prefix side; enter_tag = reason.split('_')[0]
# 5) staleness caps: oracle 2h, sentinel 1h, mults 8h, stress 30min;
#    stale/dark => unevaluable => out of that gate's denominator
# 6) gates (a)-(f) as in §1; strict (a) plus the lenient variant
# 7) nulls: perm_p 2000 draws seed 42; perm_p_side 5000 draws seed 7,
#    stratified to the kept set's exact (long, short) counts
# 8) postgres ts::text arrives as '2026-07-07 05:19:47.41441+00' — 5-digit
#    micros + bare '+00'; fromisoformat (py3.9) rejects it. Regex-parse.
```

The analysis script (`consensus_study.py`, ~330 lines implementing exactly
the above) ran in the session scratchpad; every number in this file is from
its 4-Aug run plus the decomposition passes quoted in §6/§7. It is
deliberately not committed — the doc carries the full spec, and a
re-measure should re-derive against the then-current ledger and history
rather than replay a stale extraction.

## 9 · What this study leaves standing

- The one real per-side fact confirmed in passing — **longs lose on this
  tape** (dislocation longs −0.54% vs shorts −0.17%; gillard −0.30% vs
  −0.05%; taker-live −1.58% vs +1.30%) — is already fleet doctrine
  (memory: long-budget-rations-the-losing-side) and already actioned at
  ADMISSION, where it belongs. A consensus gate adds nothing on top of it.
- Gate (d)'s null result (brain reduce-mults did not mark worse trades at
  open, n=3 books with cuts) is worth knowing but is NOT a defect finding:
  the mults are sized for stake reduction, not entry veto, and their
  floors (n≥30, 3-run streak) make them sparse by design.
- Nothing here touches real money, no lever was set, and no code changed.
- **Fleet state moved while this shipped (I12 note):** 🧲 Snap Back
  (`lighter-dislocation-lshadow`) was RETIRED in (jh) and ⚖️ Counterweight's
  widening reverted in (jg), both on 4-Aug after this study's data window
  closed. Their rows in the tables above are the honest 4-Aug retrospective;
  nothing in this study argues for re-tuning either — the dislocation cells
  are a graded corpse, and §6.2's refusal stands independently of the revert.
