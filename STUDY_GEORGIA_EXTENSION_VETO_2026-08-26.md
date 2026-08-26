# STUDY — 🔮 georgia entry-time parabolic-extension veto (2026-08-26)

**Question (pre-declared):** does refusing a NEW entry when the coin's own
run-up at the moment of entry exceeds a threshold in its OWN volatility units
improve her era book, entries and exits otherwise unchanged?

**VERDICT: REFUTED-AS-OVERFIT.** Every threshold cell on all three metrics
fails the pre-declared bar. The best-looking cell's entire improvement is the
22-Aug flash-crash batch: excised, its effect is zero-to-negative, and the
entries it vetoes are **profitable** (+0.272%/trade, $+15.03 forgone at the
best cell). No lever, no build. This is the (hl)/I19 outcome class — a
refusal with evidence.

Script (verdict logic written into the header BEFORE results):
`scripts/study_georgia_extension_veto_2026-08-26.py` (deterministic, cached in
`scripts/.ext_veto_cache/`; seed 20260826). Re-run: `python3 scripts/study_georgia_extension_veto_2026-08-26.py`.

## Sample & fidelity

* Ledger: `/trades.json?source=paper&bot=freqtrade-georgia-lshadow` → 207
  rows; **era (opens ≥ 2026-07-17) = 195**, all with `opened_at`.
* Metric needs only candles + `opened_at`, so the 46 pre-(gr) rows missing
  `entry_price` (all opened ≤ 29-Jul) **stay in BASE**; `entry_price` was used
  only as a candle-alignment check on the 149 priced rows (median 33.1 bps,
  p90 126.1 bps vs last closed bar's close — the intra-bar move LAG-1
  deliberately forfeits).
* Candles: Lighter `/api/v1/candles`, 15m, all 14 traded coins (incl. XAG),
  3,769 bars each covering the era + warmup; **metric built for 195/195 —
  nothing unbuildable**.
* LAG-1: only bars with open+900s ≤ `opened_at` inform the metric.
* Baselines reproduce the (tm) pass exactly: n=195, mean **+0.102%/t**,
  **t_iid +0.60**, **t_cluster +0.44** (golive `cluster_stats`, 60s window),
  $+12.74 over 38.7d (151 closes/30d). Ex-crash-day baseline: n=179,
  +0.192%, t_iid +1.77.

## Metrics (pre-declared)

* **EXT** = (last_close − min(low, trailing 16 closed 15m bars)) / ATR14 —
  primary. Grid {2.0 … 6.0}.
* **R4** = 4h return / ATR%; **R1** = 1h return / ATR% — secondary. Veto when
  metric ≥ threshold.

The crash entries WERE extended: XRP EXT 6.80 / R4 7.65, NEAR 5.71/6.03,
TRX 7.09/6.00 — top ~8–15% of coin-hours. The premise was real; the veto
still fails, because extension does not predict loss anywhere else on her
tape: the **top-10 EXT entries ever (8.9–11.6 ATR) net roughly flat, several
+1.3…+2.6%**.

## The sweep vs the pre-declared bar (primary metric EXT)

| thr | vetoed k | vetoed mean% | keep n | keep mean% | t_iid | t_clus | Δmean | Δt | halves(Δ1,Δ2) | ex-crash Δmean/Δt | P_rand | verdict |
|----|----|----|----|----|----|----|----|----|----|----|----|----|
| 3.0 | 137 | +0.094 | 58 | +0.122 | +0.74 | +0.61 | +0.020 | +0.14 | (−0.22,+0.20) | −0.15/−1.52 | 0.484 | overfit |
| 4.0 | 125 | +0.005 | 70 | +0.277 | +1.69 | +1.44 | +0.174 | +1.09 | (−0.16,+0.38) | −0.12/−1.30 | 0.235 | overfit |
| **4.5** | **107** | **−0.099** | **88** | **+0.348** | **+2.36** | **+2.01** | **+0.245** | **+1.76** | (−0.16,+0.49) | **+0.00/−0.39** | **0.108** | **overfit** |
| 5.0 | 92 | −0.102 | 103 | +0.285 | +2.11 | +1.82 | +0.182 | +1.51 | (−0.16,+0.41) | −0.03/−0.51 | 0.132 | overfit |
| 6.0 | 55 | −0.035 | 140 | +0.156 | +0.84 | +0.79 | +0.054 | +0.24 | (−0.10,+0.20) | +0.01/−0.15 | 0.290 | overfit |

(Full tables incl. R4/R1, per-tag rows and Δ$ in the script output; R4's best
cell 3.5 reads the same: xc +0.00/−0.45, P=0.103. R1 — the 1h form closest to
the XRP "+7.5% in 50min" story — never even produces a headline: best Δt +0.39.)

**Against the four pre-declared conditions, at the best cell (EXT≥4.5):**

* **(a) FAIL.** Kept mean/t improve and vetoed mean is negative — but the
  chronological halves DISAGREE (H1 Δ −0.16pp, H2 Δ +0.49pp; the crash is in
  H2). No cell on any metric passes halves.
* **(b) FAIL — the disqualifying one.** Drop the 22-Aug crash day: Δmean
  +0.00pp, Δt −0.39. The vetoed set EX-CRASH is **+0.272%/trade, $+15.03**
  (104 rows) — outside the one event, the veto refuses winners. At EXT≥6 the
  vetoed-ex-crash set is +0.330%, $+8.00, and that cell doesn't even catch
  NEAR (5.71 < 6). Headline t_iid +2.36 is three known rows leaving the
  sample: **REFUTED-AS-OVERFIT by the study's own pre-registered rule.**
* **(c) FAIL.** Random-veto null (2,000 draws of equal count): P = 0.108
  (best anywhere 0.103, R4≥3.5). Ranking by extension never beats vetoing
  the same number of entries at random at the 0.05 bar.
* **(d) FAIL in the honest reading.** Raw Δmean is positive across
  3.0–6.0 (neighbours agree), but that profile is the crash rows' shadow:
  the ex-crash dose-response is flat at ~0 (−0.15, −0.12, +0.00, −0.03,
  +0.01) — no dose, no response.

## Tag split (I7) — mandatory, and it bites

trend_breakout enters ON STRENGTH by design. At EXT≥4.5 the veto refuses
**73% of trend-breakout entries** (her best-supplied tag, n=146, +0.147%/t
full-sample) vs 0% of range-on; at EXT≥3.0, 92% vs 4%. Even the "extreme"
EXT≥6 gate refuses **38% of trend-breakout entries** while EXT≥6 covers 8.3%
of venue coin-hours (era, her 14 traded coins, 13,130 hourly samples; ≥4.5 =
18.0%, ≥5 = 14.0%). She samples the extended tail ~4–7× the tape's base rate
because that is what her entry rule is FOR — a veto on extension is a partial
repeal of trend_breakout, not a filter on it. There is no extreme-degree cell
that is both selective on the tape and clean on conditions (b)/(c).

## Rank interaction — extension is NOT the rank mechanism

* corr(rank1 indicator, EXT) = **−0.050**; mean EXT rank1 4.49 vs rank2 4.77
  — rank-1 entries are (if anything) slightly LESS extended.
* The rank1-vs-rank2 gap survives controlling for extension: **+0.74pp** in
  the low-EXT half, **+0.40pp** in the high-EXT half.
* So extension and entry rank are separate variables; the (tm) rank finding
  is not a relabel of extension — and extension itself is refuted as a veto.
  (Rank here: stamped `extra.entry_rank` where present — 35 rows since
  22-Aug — else derived order-of-open within the calendar hour; 4
  stamped-vs-derived mismatches, all same-second batch opens; this
  derivation reads rank1 n=146 +0.083% / rank2 n=45 +0.635%, same direction
  as (tm)'s 127/36 split at slightly different n.)

## Live-ledger corroboration (22-Aug only, NOT graded)

The live arm (different exit policy pre-26-Aug) entered the same run-up:
9 trend-breakout closes 04:29–05:14Z, mostly exited BEFORE the dump via
roi/range_top (+1.9/+3.0/+2.1% XRP), one DOGE −7.17% stop_loss, TRX −1.90%
daily_loss. Corroborates the event reached both arms and that the shadow's
−16/−19% legs are her exit policy's exposure to it, not a ledger artifact.

## Honest limits

* 46/195 era rows lack `entry_price` (pre-(gr)); they are IN the sample via
  candle-derived metrics, with alignment verified only on the priced 149.
* Metric grids and window (16 bars / ATR14) were fixed pre-computation but
  are still choices; no alternative window rescues the verdict direction
  (R4 and R1 agree).
* `bounce-pullback` has n=1 — no per-tag verdict possible.
* The random-veto null tests kept-MEAN; a t-based null was not pre-declared
  and was not substituted after the fact.
* One crash day in one era: this study cannot say extension vetoes never
  work — it says on HER 195-close era ledger the only support is that one
  event, which is exactly what the pre-declared overfit rule exists to catch.

## Bottom line

The 22-Aug batch really was a parabolic entry — and it is the ONLY place on
the ledger where extension predicted loss. A veto tuned to catch it costs
+$15 of real winners ex-crash, kills 38–73% of her best tag's supply, fails
the random-veto null, and fails both halves. **Do not build it.** Her t bar
remains a tail-event problem (73.5% of cluster variance in one batch), not an
entry-filter problem; the (tm) rank finding stands as separate, unexplained
by extension.
