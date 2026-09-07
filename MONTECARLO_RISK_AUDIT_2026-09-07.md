# Monte Carlo risk audit + benchmark shootout — 2026-09-07

**Instrument:** `scripts/study_montecarlo_risk_2026-09-07.py` (`--all`).
**Basis:** the fleet's own ledger, 4,311 rows, 26-Jun → 7-Sep, quarantine and
phantom filters applied; 14 graded books.
**Calibration:** PASS — 14 of 14 books reproduced field-for-field against the
live `golive-readiness` payload of 2026-09-07T04:02:43Z, with two declared
exemptions (below). Nothing in this report is computed on a sample the fleet's
own grader would not recognise.

**Bottom line.** The fleet's edge is real but thin, and it is **not
distinguishable from a random entry on the same coins** on any of the fourteen
books. The one book the gate calls READY (🎫 the taker) is genuinely the best
of them and is the only one that beat passive holding over the matched window
— but its excess over the random-entry null carries P = 0.145, which is not a
result. **I propose no parameter change.** The two changes at the end are
correctness and risk-visibility fixes; both move zero verdicts today.

---

## 1. The system as it stands

A ~20-book Lighter-only fleet, $1,000 paper per shadow book, two real-money
arms (👩 mum, 🙏 avo). Books publish per-trade closes to a Postgres `paper_trades`
ledger; `scripts/golive_readiness.py` grades each book, era-scoped, against six
bars — ≥30 days, ≥30 closes, mean > 0, t ≥ 2.0, both halves positive, maxDD < 15%.

Live grades at the audit's payload:

| book | n | mean %/trade | t | maxDD | verdict |
|---|---:|---:|---:|---:|---|
| 🎫 lighter-ticket-taker-lshadow | 184 | **+1.203** | **+2.66** | 5.4% | **READY (6/6)** |
| 👩 freqtrade-mum-lshadow | 91 | +0.537 | +2.83 | 1.1% | on_track |
| 👩 freqtrade-mum-**lighter** (real money) | 91 | +0.429 | +2.14 | 7.1% | on_track |
| 🙏 freqtrade-avo-maria-lshadow | 29 | +1.793 | +2.46 | 1.5% | on_track |
| 🙏 freqtrade-avo-maria-**lighter** (real money) | 14 | +2.360 | +1.72 | 5.6% | undecidable |
| 🌾 perps-funding-carry-lshadow | 30 | +0.304 | +2.59 | 2.0% | unprojectable |
| 🔮 freqtrade-georgia-lshadow | 268 | +0.068 | +0.52 | 2.3% | undecidable |
| 🏛️ pm-turnbull-lshadow | 49 | +0.286 | +1.29 | 0.2% | on_track |
| 🏛️ pm-albanese-lshadow | 68 | −0.036 | −0.08 | 0.9% | underpowered |
| 🔮 freqtrade-georgia-v3-lshadow | 91 | −0.080 | −0.72 | 0.8% | underpowered |
| 🎯 lighter-perp-sniper-lshadow | 47 | −0.694 | −0.78 | 0.9% | underpowered |
| 🪁 band-kelly-lshadow | 589 | −0.142 | −1.25 | **28.5%** | unreachable |
| 📚 book-bezos-lshadow | 33 | −0.727 | −1.41 | 3.5% | unreachable |
| ⚖️ perps-funding-spread-lshadow | 155 | −1.534 | −1.80 | 5.1% | unreachable |

---

## 2. Monte Carlo

20,000 paths per book, resampling **decision batches** — legs grouped by the
fleet's own `CLUSTER_WINDOW_S` (60s) — not individual legs. This matters:
resampling legs i.i.d. treats one basket close as ten independent draws and
understates every tail. Measured, p95 drawdown decision-wise vs leg-wise:

| book | legs → decisions | decision-wise | leg-wise | understated |
|---|---|---:|---:|---:|
| 👩 mum LIVE | 91 → 77 | 10.79% | 6.79% | **1.59×** |
| 🙏 avo LIVE | 14 → 8 | 4.44% | 2.95% | 1.51× |
| ⚖️ Counterweight | 155 → 47 | 9.45% | 7.15% | 1.32× |
| 🪁 kelly | 589 → 569 | 46.00% | 40.14% | 1.15× |
| 🎫 taker | 184 → 178 | 3.06% | 3.04% | 1.01× |

The correction is largest on the two real-money arms and the basket book, and
vanishes on the one that closes legs singly.

### Drawdown, streaks, ruin

| book | obs maxDD | sim p50 | p95 | p99 | P(>15% bar) | obs streak | chance p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 🎫 taker | 2.31% | 1.74% | 3.11% | 3.99% | 0.0% | 8 | 10 |
| 👩 mum LIVE | 7.08% | 4.81% | 10.64% | **14.39%** | 0.8% | **7** | **5** |
| 👩 mum shadow | 0.58% | 0.53% | 1.02% | 1.33% | 0.0% | **6** | **5** |
| 🌾 carry | 1.85% | 0.74% | 1.59% | 2.11% | 0.0% | **7** | **6** |
| ⚖️ Counterweight | 5.13% | 4.02% | 9.68% | 12.53% | 0.2% | 8 | 10 |
| 🪁 kelly | 27.91% | 23.60% | 45.99% | 56.23% | **81.9%** | 10 | 16 |

Three things fall out.

**The realised path flatters.** The gate grades one ordering. On the two books
that matter for risk, the p95 is 1.5–1.9× the observed value. 👩 mum's live arm
reads 7.08% against a 15% bar and would look comfortable; her p99 is 14.39%,
inside one point of it.

**Losing streaks run longer than chance predicts** on four books — mum live
(7 vs a p95 of 5), mum shadow (6 vs 5), carry (7 vs 6). Losses cluster more
than an i.i.d. model allows, which is consistent with correlated positions
closing together. This is the honest argument for holding a reserve larger
than the observed drawdown implies.

**Reserve.** To survive the p99 resampled drawdown: 🎫 taker $40 (4.0% of book),
👩 mum live $144 (14.4%), ⚖️ Counterweight $125 (12.5%), 🪁 kelly $562 (56.2%).

### Risk of ruin vs position size

Compounded, `f` = fraction of equity per position, calibrated at the shipped
size against each book's own realised return (🎫 taker sim +12.0% vs book
+15.9%; ⚖️ Counterweight −4.1% vs −3.5%).

| f | 🎫 taker P(−50%) | E[log] | ⚖️ Cw P(−50%) | 🪁 kelly P(−50%) |
|---:|---:|---:|---:|---:|
| 2% | 0.0% | 0.044 | 0.0% | 0.0% |
| 5% | 0.0% | 0.110 | 0.0% | 0.0% |
| 10% | 0.0% | 0.216 | 1.1% | 0.0% |
| 25% | 0.0% | 0.530 | 47.4% | 0.9% |
| 40% | 0.0% | 0.827 | 75.1% | 19.1% |

Shipped: taker 5.2%, Counterweight 1.8%, kelly 25.0%, mum live 25.3%.

**Declared limit:** legs compound sequentially here. These books run up to 8
concurrent positions, so a simultaneous adverse move across open legs is not in
the table — read every ruin figure as a **lower bound**.

### Varied win/loss assumptions

Scaling the mean while holding dispersion (scaling both would leave `t`
invariant and say nothing — I22):

| book | edge ×1.0 | ×0.75 | ×0.5 | ×0.0 | +p90 slip |
|---|---:|---:|---:|---:|---:|
| 🎫 taker P(loss) | 0.0% | 0.8% | 5.9% | 50.2% | 0.2% |
| 👩 mum LIVE P(loss) | 11.3% | 17.2% | 25.3% | 46.0% | 24.0% |
| 🌾 carry P(loss) | 13.7% | 21.0% | 29.9% | 50.0% | **52.9%** |

🌾 carry is the fragile one: at the measured p90 slippage band (10.2 → 25 bps
round trip) its probability of ending below start goes 13.7% → **52.9%**. Its
whole edge is inside the execution-cost uncertainty.

---

## 3. Benchmarks — identical window, assets, costs

Costs are the fleet's own measured friction, not assumed: Lighter's taker and
maker fees are **0.0000** on all active books, so the entire cost is slippage —
median round trip 10.2 bps (🎫 taker, n=67), ~25 bps at p90. Every arm below,
the books included, is charged the same 10.2 bps.

### Matched window (29-Aug → 7-Sep, 8.3 days, 196 coins, regular 5-min bars)

This is the only span with regular bars for every arm.

| arm | return | basis |
|---|---:|---|
| 🎫 lighter-ticket-taker | **+11.54%** | 51 closes, own ledger |
| 🙏 avo LIVE | +9.09% | 3 closes |
| **BENCHMARK buy & hold** | **+7.82%** | equal-weight, 196 coins |
| 👩 mum LIVE | +5.46% | 72 closes |
| **BENCHMARK volatility-only** | +3.08% | inverse-vol weights, no view |
| 🌾 carry | +2.79% | 14 closes |
| 👩 mum shadow | +1.83% | 71 closes |
| ⚖️ Counterweight | +0.64% | 24 closes |
| **BENCHMARK cash / stablecoin** | 0.00% | Lighter pays no yield |
| 🎯 sniper | −0.20% | 7 closes |
| **BENCHMARK SMA 12/48** | **−4.39%** | same coins, 60 median flips |
| 🪁 kelly | −11.14% | 316 closes |

**Exactly one book beat buy-and-hold** over the window, and it is the READY
one. The naive trend rule lost 4.4% to churn — 60 flips × 10.2 bps is 6.1% of
turnover cost alone, which is the fleet's own "turnover is not a win" doctrine
showing up in a benchmark.

The window was strongly rising (+7.82% mean), so this flatters every long-biased
book and is the reason the next test exists.

### Random entry, same holding windows (per book, full window)

For each real trade: hold a **random other coin**, same open and close stamps,
same side, same cost. 400 draws.

| book | book %/trade | random %/trade | excess | **P(random ≥ book)** |
|---|---:|---:|---:|---:|
| 🏛️ turnbull | +0.286 | −0.256 | +0.543 | **0.072** |
| 🎫 taker | +1.203 | +0.750 | +0.453 | **0.145** |
| 🙏 avo LIVE | +2.360 | +1.198 | +1.162 | 0.172 |
| 👩 mum LIVE | +0.429 | +0.336 | +0.092 | 0.355 |
| 👩 mum shadow | +0.537 | +0.509 | +0.028 | 0.445 |
| 🔮 georgia | +0.068 | +0.049 | +0.019 | 0.435 |
| 🌾 carry | +0.304 | +2.923 | −2.619 | 0.885 |
| ⚖️ Counterweight | −1.534 | +0.233 | −1.767 | 0.990 |
| 🎯 sniper | −0.694 | −0.027 | −0.667 | 0.975 |
| 🪁 kelly | −0.142 | −0.131 | −0.011 | 0.625 |

**Not one of the fourteen books clears the null at p ≤ 0.05.** The closest are
turnbull (n=49) and the taker (n=184).

**What this null does and does not test.** It holds the book's *market timing*
fixed and randomises only *which coin*. So it says coin selection is not
demonstrably adding value. It cannot rule out an edge that lives entirely in
*when* the book is in the market — and for 🎫 the taker, whose whole thesis is
timing off the scout's tickets, that is a real gap. Closing it needs a
time-shifted placebo through the book's actual bracket, which needs bar data
this environment cannot reach (`/api/v1/candlesticks` is 403 outside the
container). **Recommended as a pre-registered follow-up, not asserted here.**

**Buy-and-hold is withheld per book** (12 of 14): the fleet's own fills are too
sparse to price most books' coins at both endpoints, and a 2-of-16 subsample is
not a benchmark. The matched-window table above is the honest version.

---

## 4. Out-of-sample: splits and walk-forward

Chronological 50/25/25, then expanding-window walk-forward (no parameters are
fitted — the books are shipped — so this measures **stability**):

| book | train | valid | test | OOS folds positive |
|---|---:|---:|---:|---:|
| 🎫 taker | +0.686% | +0.663% | **+2.775%** | 4/5 |
| 👩 mum LIVE | +0.729% | **−0.825%** | +1.095% | 3/5 |
| 👩 mum shadow | +0.514% | −0.034% | +1.155% | 4/5 |
| 🌾 carry | −0.161% | +1.051% | +0.520% | **5/5** |
| ⚖️ Counterweight | −2.078% | −0.879% | −1.117% | 2/5 |
| 🎯 sniper | −0.818% | +1.383% | −2.533% | 3/5 |

🎫 the taker's test slice is 4× its train slice — its edge is concentrated in
the most recent third. That is *either* a genuinely improving book *or* the
I25 hot-window shape, and the sample cannot yet tell them apart. Its READY
verdict rests on the era's second half.

🌾 carry is the only book positive in every OOS fold, on the smallest sample.

---

## 5. Portfolio correlation and drawdown overlap

- 14 books with a usable daily series; **mean pairwise correlation +0.066**;
  **N_eff 7.55 of 14** — genuine diversification, roughly half the nominal count.
- Most-correlated pair: 👩 mum live ~ mum shadow **+0.843** (by design — same
  policy, live and control arm; it is not independent risk and should not be
  counted as such).
- Worst fleet days: 2-Sep −$82.74 (led by mum −$69.14), 30-Aug −$48.79 (kelly
  −$83.28), 28-Aug −$38.18. The bad days are **single-book events**, not
  fleet-wide correlated drawdowns — which the +0.066 mean correlation predicts.

## 6. Regime

**Per-close regime attribution is not available from the ledger.**
`extra.btc_regime_up` rides the *summary* row, never the *trade* row —
coverage across all 14 books is **0%**. Derived instead from the scout's own
BTC marks (24h direction at the close), covering the 8.3-day tape:

| book | BTC-up | BTC-down |
|---|---|---|
| 👩 mum LIVE | n=17, **+0.842%** | n=47, +0.105% |
| 👩 mum shadow | n=24, +0.336% | n=40, +0.616% |
| 🪁 kelly | n=166, **−0.366%** | n=132, +0.123% |
| 🔮 georgia-v3 | n=30, +0.072% | n=42, −0.225% |
| 📚 bezos | n=21, −1.232% | n=12, +0.155% |

The live and shadow arms of the *same policy* disagree on the sign of the
regime effect, on ~60 closes each — which is what an underpowered split looks
like. No regime conclusion is supportable at this sample.

## 7. Risk-adjusted return

Per-trade first; annualised is derived at each book's own close rate and
therefore rewards turnover — compare the per-trade columns between books.

| book | n | mean% | Sharpe/trade | Sortino/trade | Profit factor |
|---|---:|---:|---:|---:|---:|
| 🌾 carry | 30 | +0.304 | **0.472** | 1.691 | 3.91 |
| 🙏 avo LIVE | 14 | +2.360 | 0.459 | **3.319** | 7.13 |
| 🙏 avo shadow | 29 | +1.793 | 0.458 | 1.619 | 5.17 |
| 👩 mum shadow | 91 | +0.537 | 0.296 | 0.404 | 2.03 |
| 👩 mum LIVE | 91 | +0.429 | 0.225 | 0.298 | 1.72 |
| 🎫 taker | 184 | +1.203 | 0.196 | 0.438 | 1.74 |
| 🏛️ turnbull | 49 | +0.286 | 0.185 | 0.294 | 1.53 |
| ⚖️ Counterweight | 155 | −1.534 | −0.144 | −0.168 | 0.63 |
| 🪁 kelly | 589 | −0.142 | −0.051 | −0.070 | 0.84 |

---

## 8. Findings that did not become code changes

Each is stated with why it was **not** acted on, because a refusal with a
reason is a first-class outcome here.

1. **👩 mum's live arm runs 5× the clip of its own control twin** ($253 vs $50
   median). Per-trade % is clip-invariant so the grade is unaffected, but
   maxDD is **not** — her twin cannot corroborate her drawdown, only her mean.
   **Not acted on:** this is the `mum-live-rho-read-preregistered` carried row,
   graded on days after 7-Sep at n≥30 or 7-Oct. Cutting a real-money clip on
   the window that motivated it is precisely what I25 forbids. This audit is an
   **independent corroboration** of that registration from her own ledger
   rather than the rho ladder, and it should be read at the registered date.

2. **🎫 the taker's exits give back most of the peak** — median capture ratio
   0.275, and 34% of trades that peaked above +0.5% closed at a loss (n=92 with
   excursion telemetry). **Not acted on:** the book reads READY, and `(ye)`'s
   `FROZEN_WHEN_READY` rule — shipped yesterday — drops exactly these bracket
   levers while a book is ready. Changing the bracket a book passed on is the
   thing that rule exists to prevent.

3. **🪁 kelly's P(maxDD > 15%) is 81.9%** and its p99 is 56%. **Not acted on:**
   already under a pre-registered read that returned to Eamon on 7-Sep
   (`kelly-fresh-read-pre-registered`); the decision is his, and its fresh
   upper bound (+0.125%) has not excluded a positive mean, so I17-as-amended
   forbids retiring it.

4. **🌾 carry's edge is inside the slippage band** (P(loss) 13.7% → 52.9% at
   p90 friction). **Not acted on:** n=30 on a 33.8-day era; the sample cannot
   support a gate change, and `MIN_N` exists for this.

5. **No book clears the random-entry null.** **Not acted on as a gate change:**
   making it a bar is a go-live gate re-spec and an operator act, and the null
   I can compute here tests coin selection only. Recommended as a
   pre-registered instrument.

---

## 9. The two changes proposed

Both in `scripts/golive_readiness.py`. Neither touches `SLOW_LOOP`,
`STALE_SECONDS`, `EXPECTED`, `LABELS` or `CURRENT_BOTS` — all of which live in
`pnl_dashboard.py`, which this patch does not open. No bot definition, filter
or entry rule is altered. **Measured: 0 of 14 books change any of the six bars;
the READY set is identical.**

### Change 1 — a deterministic total order over one book's closes

**Hypothesis.** The `halves` bar must not be decided by database row order.

`sorted(..., key=_key)` is stable, so legs sharing a close stamp kept whatever
order Postgres returned, and `stats()` splits at `mid = n // 2`. When that
boundary lands inside a tied batch, re-running the grader over an *unchanged
ledger* can publish a different h1/h2.

**Evidence.** One of 14 graded books sits on such a tie — 🙏 avo's LIVE arm,
whose boundary lands inside a five-leg daily-loss flatten at
2026-08-28T16:22:46.174888. Permuting only that batch moves h1 across
**[+$7.27, +$17.36]**; the live payload reads $17.36 and my independent
recomputation read $9.67, from the same rows. Every ordering leaves both halves
positive, so **no verdict moves**. What makes it worth fixing is the neighbour:
👩 mum's LIVE arm passes this same bar on **h2 = −$0.02**.

**Impact.** Expectancy: none. maxDD: none. Sharpe/Sortino: none. Turnover:
none. It changes no trade — it makes an existing verdict reproducible.

**Failure scenarios.** If a book's true economic ordering differed from
(close, open, pair), the halves split would differ from today's — but today's
is the database's arbitrary order, so this is strictly an improvement in
determinism. It cannot make a bar *less* stable.

### Change 2 — publish the drawdown distribution beside the realised path

**Hypothesis.** A 15% maxDD bar graded over one realised ordering cannot
distinguish a safe book from a lucky sequence.

**Evidence.** Section 2 — 🪁 kelly observed 27.9% / p95 46.0% / P(>bar) 82%;
👩 mum LIVE observed 7.1% / p99 14.4% against a 15% bar; 🎫 taker observed 2.3%
/ p95 3.1% / P(>bar) 0%. The gate today publishes only the first number of each
pair.

**Impact.** Expectancy: none. maxDD: none. Sharpe/Sortino: none. Turnover:
none. **REPORTED, never a bar** — `BAR_NAMES` and `grade()` are byte-unchanged,
pinned by an assertion in the new selftest. Cost: 4,000 resamples per book
inside a 6-hourly publish loop; measured at well under a second for the whole
fleet.

**Failure scenarios.** (a) The bootstrap assumes closes are exchangeable within
a book; a book with strong serial structure beyond the 60s batching would still
be understated — the decision-batching mitigates the dominant case and the
residual is declared. (b) If someone later makes this blocking, it becomes a
gate re-spec, which is an operator act — the selftest asserts it is not in
`bar_map`. (c) Fail-silent: any error returns `None` and the field is absent
rather than zero, because a missing risk number that reads as a low one is
worse than none.

### Rollback

Both changes are in one file and are purely additive.

```bash
# full rollback of both changes
git revert <commit>            # or:
git checkout HEAD~1 -- scripts/golive_readiness.py tests/test_selftests.py

# partial: disable Change 2 without touching code
GOLIVE_DD_DRAWS=0              # resampled_dd returns an empty-quantile dict
                               # -- prefer the revert; this is the panic lever
```
No state migration, no lever, no deploy marker. `golive-readiness` is on the
auto-deploy path for `freqtrade-bots`; the next publish carries it. Reverting
restores the previous payload shape exactly — no consumer reads either new
field today, so removal is safe at any time.

### What was NOT changed, and why the suite went red first

`tests/test_selftests.py` gains two registry entries. Mine is required. The
second, `scripts/study_taker_ready_2026-09-06.py`, was **already unregistered
at HEAD** — verified by stashing this work and re-running — so
`test_no_unregistered_selftest` has been red on main since yesterday. Recorded
here rather than folded in silently.

---

## 10. Verification

- **Calibration gate:** PASS, 14/14 books, against the live payload.
- **Baseline P&L:** recorded before testing (`BASELINE_PNL.json`, sha256
  `afe5aaa5ece2565f`), re-verified after: every baseline book still present, no
  book lost rows, no book with an unchanged close count changed its P&L. The
  only deltas are 4 new closes that arrived naturally while the fleet ran
  (georgia-v3 92→95, taker 326→327).
- **Verdict parity:** 0 of 14 books change any of the six bars; READY set identical.
- **Mutation testing (I3):** 8 mutations, all confirmed RED —
  drawdown-from-zero instead of from-peak; leg-wise instead of decision-wise
  batching; non-deterministic seed; zero-fill instead of fail-silent;
  `halves_tie` always-on; `halves_tie` on the wrong boundary; `dd_resampled`
  promoted into the bars; **denominator switched to the running peak** (the
  (yr) defect — this one survived the first round and its pin was added).
- **Suites:** `golive_readiness --selftest` green; `tests/test_selftests.py`
  green (133 tests); grader-related `tests/autonomy` subset green (124 tests);
  `audit_doctrine_enforcement`, `audit_changelog_letters`,
  `audit_undefined_names`, `audit_venue_purity`, `audit_image_imports` all pass.

## 11. Reproduce

```bash
python3 scripts/study_montecarlo_risk_2026-09-07.py --selftest
python3 scripts/study_montecarlo_risk_2026-09-07.py --calibrate   # exits 2 if it cannot
python3 scripts/study_montecarlo_risk_2026-09-07.py --all --draws 20000
```
The instrument moves nothing — asserted by an AST walk of its own call sites,
not a substring scan.
