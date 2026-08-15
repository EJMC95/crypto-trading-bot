# STUDY: the funding lifecycle, end to end — entry timing, exit policy, decay predictors, seasonality, cross-sectional momentum
**2026-08-15 · pre-registered, calibration-gated, adversarially refereed. Ten agents (2 data + 5 analysts + 3 referees), 62-coin tape (~205d settled hourly fundings, ~121d 1h candles, 280,238 + 173,878 rows), the full 2,487-close paper ledger, and the live arms' records. Every referee reproduced its analyst's numbers exactly.**

The operator's framing: *"thinking outside the box for a positive pnl with an
edge slowly accruing."* The study's honest shape: **one contamination finding
that corrects the fleet's beliefs about its best number, four refutations that
prevent bad moves, one parked hypothesis, and no enactable new edge today.**
Per I19, the refusals are deliverables: each one is a widening someone would
otherwise eventually ship unmeasured.

---

## 1 · THE HEADLINE — the fleet's best-evidenced number is partly phantom (E1's calibration refusal, run to ground)

E1's pre-registered calibration gate REFUSED (sim −0.199% vs realised +0.043%
on carry's 69 replayable era entries, gap 0.242pp > 0.20pp tolerance) — and
the refusal decomposed, with per-row receipts, into a measured ledger defect:

- Rows whose entry-hour tape reads |TRUE| ≥ 15% reconcile at **0.83–0.97×**
  (ledger ≈ venue truth).
- Rows entered at RESTING rates over-accrue **2.5–6.7×**: ZEC 4.6×, XAU 6.7×,
  LIT 2.9×, BNB 2.5×, SPCX 4.0× — with resting `entry_apr` stamps at exactly
  **84.1% = 8× the 10.512% resting TRUE apr**, while hot stamps match tape.

**Root cause, established by date clustering + a live endpoint measurement
(not the analyst's mixed-basis-feed hypothesis, which is REFUTED):** every
8×-stamped row was opened **17–28 July** — precisely the (hu) window in which
`yield-harvester-shadow` (the container with no deploy rule) kept running the
pre-17-Jul-basis-fix build. Entries stamped 8× APRs into durable position
state; accruals straddled both bases across the eventual deploy. The venue
endpoint measures CLEAN today (per-8h convention, ratio 8.00 on every pinned
resting coin), and every ledger row opened ≥ 30-Jul stamps true. **No live
code path is wrong.**

**Quantified phantom (accrued × (1 − 1/ratio), tape-receipted rows):**
ZEC ≈ $4.34 · XAU ≈ $2.96 · LIT ≈ $2.27 · SPCX ≈ $1.39 · BNB ≈ $0.76 ·
kBONK ≈ $1.5 (no tape; class-typical ratio) — **≈ $13 of 🌾 carry's +$66.21
all-time is bookkeeping, not venue truth (~20%)**, concentrated in the
`decay_paid` family: the "+$85.9, 100% win" story carries ≈ $6 of it.

**What is and is not affected:**
- CLEAN: every era-scoped grade (carry's 31-Jul era boundary — declared for
  the two-writer reason — happens to also be the basis boundary), Barnesy
  (born 5-Aug), Garrett (13-Aug), Hull/Kiyosaki (n=0), both Farmer arms
  (live P&L is venue-settled reality, not modelled accrual).
- CONTAMINATED: every POOLED all-time quote — the allocation organ's #1 rank
  for carry (57% of target capital, computed on 91/101 pre-era closes), the
  +$66.21 headline, the +$85.9 decay_paid figure. The (lx) accessor gate
  already stops consumers ACTING on pooled claims; (mz)'s
  `n_with_era_claim=0` already flags the headline; this study says the pooled
  number is not merely stale-policy but part-phantom.
- The carry keep-or-retire docket item (matures 15-Aug) should read: era
  n=10 at −$15.45 (venue stall), pooled record inflated ≈ $13.

## 2 · E2 — the Farmer's exit geometry, measured on its own cell for the first time: INERT (a refusal with evidence)

Calibration **PASSED** both ways (sim vs the live arm's own 95 era entries;
per-trade corr 0.77). The pre-registered 48-cell grid (EXIT_APR × HARD_STOP ×
flip-grace): **zero cells beat shipped on both halves at t ≥ 1.5.**

- The stop axis is nearly inert in-era: exactly ONE stop event in 95 trades;
  hs=0.15 is worth +$0.56 total from that single trade (grid-edge, UNBOUNDED,
  not bankable).
- The EXIT_APR axis is structurally quantized: 0% of |apr| mass lies in the
  0.5×/1.25× bands — the knob cannot express fine motion on this venue's tape.
- Flip-grace 6h/24h is **REFUTED on the Farmer's cell in all 16 (xa,hs)
  pairs** (−0.45pp/trade at shipped) — the OPPOSITE of the Rich Dad (mf) and
  Hull carry-cell results. Grace is a cell property, not a doctrine.
- Controls: the entry signal beats blind timing only at P=0.06; the realised
  record is indistinguishable from exposure-matched drift (P=0.155) —
  consistent with era t≈0.5: **the stall is edge, and exit tuning cannot
  manufacture it.** The (na) lever plumbing stays as REACH (the (it)
  precedent: registration is reach, not payoff); no judge candidate is filed.

## 3 · E5 — cross-sectional funding momentum: REFUTED, and the incumbent re-read

On ⚖️ Counterweight's exact validated frame (calibration PASS — the harness
reproduces the repo's own validated script to 2dp):
- **delta24h momentum rank: −19.4% of gross, both halves negative, 3.6× the
  turnover, perm P=0.72.** Refuted in both windows.
- **level × momentum agreement blend: the worst book tested** (−36.7%, worse
  than 94.8% of random books). Its consistently positive MIRROR (+22.8%) is
  noted as an unmeasured fade-the-agreement hypothesis, nothing more.
- Review-relevant for 28-Aug: the VALIDATED level signal itself reads ~zero
  on the trailing 121d (+0.95%, t=0.08, maxDD 15.1%) — directionally
  consistent with the live book's in-era t=−0.44. The Feb→Jul edge is not
  visible in the recent window.

## 4 · E4 — seasonality and supply windows: no clock edge; the persistence gate re-derived

- Hour-of-day |apr| structure passes full-tape (z=3.43) and **fails the
  second half** (z=−1.24) → reported null. Day-of-week, weekend, 8h-boundary:
  all null. There is no clock-based entry timing edge on the liquid set.
- Supply arrivals: 1,286 qualifying windows/205d, **median duration 2h, 91%
  of windows ≤ 6h; the 6h persistence gate consumes 81% of qualifying
  window-hours and misses 91% of windows entirely.** "The gate is a low-cost
  filter" is refuted — it is a very expensive filter…
- …and it earns its cost: **P=1 (enter immediately) LOSES −21.8% (t=−5.9)**;
  the per-episode net is MONOTONE INCREASING in persistence: P=1 −0.064% →
  P=6 +0.016% → **P=12 +0.161% (t=1.80, both halves positive, lb=0.046)** →
  P=24 +0.269% (n=8). Referee: reproduced exactly, LAG-1 clean, NOT
  denominator shrinkage (total net also peaks at P=12: +4.2% vs P=6 +1.5%).
  **HYPOTHESIS-GRADE (n=26, t below the 2.0 bar): candidate `PERSIST 6h→12h`
  parked for the replay gate** — consistent with Hull's independently
  measured 24h persist on its own band. NOT enacted: carry (the would-be
  consumer) is venue-stalled awaiting its I17 docket call, and tuning a book
  on the docket is the exact behaviour I17 forbids.

## 5 · E1/E3 — entry timing and decay predictors: NULL, with useful shape

- Onset (rising-apr) vs level entry: **never significant** (Welch p 0.42–0.60
  across k ∈ {3,6}, both cells) despite directional consistency on every
  metric (accrual/hour +30%, fewer flips, better both halves). Best secondary
  split p=0.15. k=12 is structurally VACUOUS after a 6h persistence gate at a
  20% bar (46/46 entries satisfy it — the I7 class, caught pre-ship).
- Decay predictors: at n=103 funding closes, **nothing survives
  Benjamini-Hochberg** (16 pre-registered tests; best t=2.81 vs shuffle
  family-wise p95=2.90). Coherent suggestive directions, one phenomenon:
  entries at a coin's own apr EXTREME / during venue-wide spike breadth
  reach decay_paid less and earn less — spike-chasing is adverse selection.
  Undecidable at this n, not absent; detection floor ~22pp.
- The random-timing control itself: entering the cell's coins at RANDOM hours
  with production exits is profitable on this tape (+0.22–0.28%/trade) — the
  cell's expectancy is coin/regime membership, not hour-level timing. Bank
  nothing that doesn't beat this null.

## 6 · What was implemented, what was parked, what was refused

| Item | Route |
|---|---|
| Ledger contamination finding | CHANGELOG (nc); CLAUDE.md exit-instruments numbers corrected in place (I12); carry docket evidence updated (OPERATOR_QUEUE) |
| Farmer exit-grid: zero winners | (na) plumbing stays as reach; **no judge candidate — refusal with evidence** |
| PERSIST 6h→12h (t=1.80) | PARKED as replay-gate hypothesis; blocked on carry's I17 docket call |
| Momentum/blend ranks | REFUTED — do not re-run without a new mechanism |
| Flip-grace on the Farmer cell | REFUTED — grace is a cell property; do not port (mf)/Hull grace here |
| Onset entry, clock edges, decay predictors | NULL at current n — re-examine only when n roughly doubles |

Artifacts: `scratchpad/edge/` (tape, per-analyst code, results JSON, PREREG
docstrings, calibration_rows.csv). Referees: 3/3 reproduced exactly
(1 confirmed-census, 2 unclear = hypothesis-grade as reported).
