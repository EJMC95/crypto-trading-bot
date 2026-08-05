# STUDY: WHERE THE WINS ARE LOST — in-era loss decomposition across the living fleet (2026-08-05)

**Operator question (verbatim intent):** *"where could we further improve, focusing
on win rate of bots"* — decomposed as: where does the fleet's red actually live,
cell by cell, so improvement targets the populations that predictably lose
rather than buying win rate with churn (I15: the tp-0.06 trap).

**Headline verdict:** the fleet's in-era realised red is **stops**: the `sl` exit
family lost **−$90.28 over 260 closes at a 2.3% win rate** (median hold 0.7h) —
more than every other losing exit family combined. **55% of that pool
(−$50.10, 176 stops, ALL at 0% win) is the six Parliament books' ~1% stop**,
the exact rule the (gx) calibrated sweep already measured as realising
reversion losses, and the actuator for it shipped last night ((jj),
gillard-scoped). The next two biggest classes — ⚖️ Counterweight's rebalance
bleed (−$31.31) and 🧲 Snap Back's convergence bleed — were **closed by
tonight's (jg)/(jh) work**, and this study's ledger read verifies both landings.
Win rate itself is the wrong lens, and this tape proves it in one line: **longs
win 43.6% and shorts win 44.1% — near-identical win rates hiding a
0.22pp/trade expectancy gap** (longs −0.227%/t=−2.56 vs shorts −0.008%/t=−0.11).

---

## 1. Method — the production close path, not a parallel harness

Per (ji)'s standing warning (*"any future retrospective over `paper_trades`
that skips `bot_pnl_store.is_quarantined` will re-manufacture this artifact"*)
and the harness-must-mirror-production rule:

- **Rows**: `bot_pnl_store.fetch_paper_trades(limit=60000)` — the brain's own
  ingest. Quarantine applied at source (**44 rows withheld**, the (hm)
  BOT/CXMT episode), tags split by `split_reason`, durations by the same
  tolerant parser production uses. 2,079 admissible rows fetched.
- **Eras**: the published `golive-readiness` payload (5-Aug 00:01Z) where a
  book is graded — including the taker's (jf) stamp-derived boundaries
  (live 30-Jul 11:05Z, shadow 30-Jul 11:09Z) — and
  `golive_readiness.era_epoch_for` for books below the payload floor
  (mum / avo-maria / swing-daily → 17-Jul). Keyed on the **OPEN**, fail-closed
  on an unreadable stamp (0 rows hit that). Books with no era (pm-*, sniper)
  grade all-time, matching the gate.
- **Kept**: **1,091 in-era closes** across 21 living books + 1 retired-tonight
  book (Snap Back, included so the loss table shows what the retirement ended);
  326 pre-era rows dropped.
- **Calibration** (a harness that cannot reproduce what DID happen may not say
  what would have): per-book in-era n / mean% / win% match the published gate
  payload **exactly** on every shared book (e.g. gillard 280/−0.106/47.9;
  georgia 76/+0.096/47.4; farmer-shadow 77/+0.220/49.4). t agrees to ±0.2
  (formula variant). The one divergence is ⚖️ Counterweight — n=68 here vs 56
  in the payload — and it is explained to the trade: **12 closes stamped
  00:37:57Z on 5-Aug, after the payload published**. Those 12 are the (jg)
  revert unwind (§4.2).

Cell floor: n≥8 (or |$|≥5). Every claim below is side-aware and graded against
the standing random-entry null (a random short earns +0.2–1.1%/trade free on
this tape).

## 2. The loss concentration table — where the red actually lives

Top in-era loss cells (book | side | exit family, ranked by total $):

| cell | n | win% | mean%/trade | total $ | t | med hold |
|---|---|---|---|---|---|---|
| ⚖️ CW short·rebalance | 36 | 50.0 | −3.811 | **−26.86** | −1.79 | 71.9h |
| gillard short·sl | 73 | **0.0** | −1.377 | **−19.23** | −28.6 | 0.3h |
| intraday-15m long·sl | 21 | 4.8 | −1.698 | **−11.68** | −6.7 | 6.2h |
| georgia long·sl | 43 | 11.6 | −0.767 | **−10.10** | −9.0 | 1.9h |
| gillard long·sl | 25 | 0.0 | −1.476 | −6.84 | −7.4 | 0.3h |
| farmer-shadow short·sl | 6 | 0.0 | −3.254 | −5.86 | — | 44.0h |
| dad long·donchian_breakdown | 7 | 28.6 | −2.940 | −5.36 | −2.2 | 84.1h |
| abbott short·sl | 25 | 0.0 | −1.035 | −5.18 | −29.5 | 0.2h |
| CW long·rebalance | 32 | 43.8 | −0.701 | −4.45 | −0.9 | 48.0h |
| rudd short·sl | 12 | 0.0 | −2.073 | −4.42 | −17.0 | 0.7h |
| morrison short·sl | 8 | 0.0 | −2.226 | −3.33 | −34.4 | 5.0h |
| abbott long·sl | 14 | 0.0 | −1.007 | −2.95 | −15.8 | 0.7h |
| 🧲 Snap Back long·converged | 53 | 43.4 | −0.397 | −2.10 | −2.4 | 0.1h |
| 🧲 Snap Back short·converged | 125 | 43.2 | −0.160 | −2.00 | −2.0 | 0.1h |

Fleet-level exit families (in-era):

| family | n | win% | mean% | total $ | med hold |
|---|---|---|---|---|---|
| **sl** | **260** | **2.3** | **−1.606** | **−90.28** | 0.7h |
| rebalance (CW only) | 68 | 47.1 | −2.347 | −31.31 | 48.1h |
| donchian_breakdown | 13 | 30.8 | −1.800 | −6.22 | 84.1h |
| converged (Snap Back) | 178 | 43.3 | −0.230 | −4.10 | 0.1h |
| flip | 44 | 47.7 | −0.005 | −0.00 | 3.9h |
| decay | 77 | 51.9 | +0.349 | +6.90 | 5.5h |
| max_hold | 70 | 44.3 | +0.395 | +12.00 | 6.0h |
| roi | 45 | 100.0 | +1.470 | +22.95 | 4.0h |
| **tp** | **130** | **100.0** | **+2.241** | **+62.54** | 0.6h |

The per-book stop pool (`sl` family): 14 books carry one; **12 of the 14 are at
exactly 0% win**. gillard −$26.06 (98), intraday-15m −$11.68 (21), georgia
−$10.10 (43), abbott −$8.12 (39), farmer-shadow −$5.86 (6), taker-shadow
−$5.34 (5), rudd −$5.08 (14), morrison −$4.43 (10), albanese −$4.34 (9),
swing-daily −$2.54 (1), turnbull −$2.07 (6), farmer-live −$2.00 (1),
taker-live −$1.62 (5), Snap Back −$1.03 (2).

## 3. Priors scorecard — confirmed or refuted on current in-era data

| prior | verdict |
|---|---|
| Long side −0.158%/trade, t=−1.78 fleet-wide | **CONFIRMED, now worse**: directional-only longs in-era n=385, **−0.227%/t=−2.56**, −$9.36, win 43.6%. |
| `*_sl` at 0% win on seven books (gq) | **CONFIRMED and widened: 12 books at exactly 0%** (list above; intraday 4.8% and georgia 11.6% are the only stops that ever win). |
| Sided flips lose on 🌾 carry | **NOT MEASURABLE IN-ERA** — carry's era reset 31-Jul ((ii) two-writers) and the book has **n=1** since (venue funding collapsed; the stall is the standing keep-or-retire). On the Farmer, flips are now ~flat (shadow −$0.19/n=22, live +$0.10/n=17). |
| Georgia's `trend_breakout` = 63% of trades and the loss driver | **REFUTED in-era**: the tag is now 72% of trades (55/76) and **positive** (+$5.02, +0.154%/trade). Georgia's red is not a tag — it is the **sl slice** (−$10.10 across tags). Book t=+0.70: the break-even-ceiling memory stands. |
| Random-short null +0.2–1.1%/trade free | **The fleet's shorts run BELOW their null**: directional shorts net −0.008%/trade. The only cells above the null's top: taker short-divergence (shadow +1.854%/n=10/t=1.34; live +1.061%/n=11/t=0.89) — **still t<2, not evidence yet**; freeze the bars and let n accrue ((hm)/(jf)). |

## 4. Fixability, cell by cell

### 4.1 The Parliament stop pool — (b) exit rule firing wrong; actuator already walking
−$50.10 over 176 stops, all 0% win, median holds 0.3–2.2h, across all six PM
books. gillard's bracket makes the mechanism visible: tp +$18.50 (73 wins,
+1.331%) vs sl −$26.06 (98 stops, −1.402%) — a near-symmetric bracket that
fires stops more often than targets at a 43% hit rate is net-negative by
construction. The (gx) calibrated sweep (the ONE book that passed
`calibrate()`) measured the counterfactual: **sl 1%→3% moves the book
−0.158→+0.050%/trade with maxDD FALLING 40.7%→26.0%** — the tight stop was
realising losses that revert. **(jj) shipped the actuator last night**
(sweep acceleration, gillard-scoped, inside `PARAM_BOUNDS`, replay-gated).
- ROUTE: **[already-shipped — let gillard's walk run]**; then
  **[lever-proposal]** extend the accelerated walk to abbott/rudd/morrison/
  albanese/turnbull ONLY after (i) gillard's out-of-sample verdict is in and
  (ii) each book passes its own `calibrate()` gate (post-(gr) they all record
  prices now; their pre-(gr) closes never will).
- Win-rate honesty: this is the rare **both-up** fix — win rate rises (0%-win
  stops become ~50%-win conv/max_hold closes) AND measured expectancy rises,
  with drawdown falling. That combination is exactly what (gx) measured; do
  not assume it generalises — measure per book.

### 4.2 ⚖️ Counterweight rebalance — (d) SOLVED by (jg), landing verified here
−$31.31 through `rebalance` exits, −$26.86 of it short-side at 72h median
hold. The ledger names the mechanism: the 5-Aug 00:37:57Z unwind closed 12
legs in one stamp — **SOXL short −47.08%, SNDK short −41.06%, MU −21.27%,
SKHYNIX −11.27%, SAMSUNG −8.12%** … all from the unvalidated wide-universe
non-crypto set, shorting semiconductors in their bull run (the exact
chronic-losers-are-regime-bound shape, same names as gillard's loss). That
12-leg simultaneous close is the **(jg) revert deploy landing** (universe
60→30 forces every non-hand-list leg out) — the readback (jg) asked for.
- **Expect the next golive payload to read WORSE on this book and do not
  treat that as a regression**: the −$27.6 realised at 00:37Z is the h2 MTM
  red ((jg): −$16.01 MTM and falling) moving from open to realised because
  the fix landed. Realisation is the accounting of the revert, not new damage.
- ROUTE: **[SOLVED-PENDING-EVIDENCE]** — pre-registered ~28-Aug read; MTM
  worse-of-both bar arms ~7-Aug. Nothing further to pull.

### 4.3 🧲 Snap Back converged bleed — (d) SOLVED by (jh)
−$4.10 realised through 178 `converged` closes (plus the book's mean
−0.25%/trade, t=−2.82, n=189 all-time — it added 14 closes on 4-Aug alone
before the guard). Last close **4-Aug 20:46Z**; the retirement merged 23:06Z;
no closes since. ~2h of silence is consistent with the guard landing but not
yet proof (I1) — the definitive readback is the container printing the
retirement line, and the **[operator]** half is still open: stop the
`snap-back-shadow` service (OPERATOR_QUEUE item 3).

### 4.4 Spot/family stops — (b) suspected, UNMEASURED: the sweep is the route
intraday-15m sl −$11.68 (4.8% win, 6.2h holds) and georgia sl −$10.10
(11.6% win, 1.9h holds) are the two biggest non-Parliament stop cells, and
both books are otherwise earners (intraday roi +$9.22 at 100% win; georgia
roi +$13.73). dad's `donchian_breakdown` −$5.36 (n=7, 84h holds) is the same
question in exit-rule clothes. **No counterfactual exists for any of them**
— the (gx) sweep was calibratable only on gillard.
- ROUTE: **[implement-now (measurement)]** — run `scripts/study_exit_sweep.py`
  over their post-(gr) priced closes; the `calibrate()` gate decides whether
  a recommendation is even utterable; anything shipped is backtest-first and
  goes through the replay-gated channel, never a hand edit. Honesty: sign
  unknown until swept — (hl) measured that tightening a stop can raise closes
  and make total P&L WORSE; widening can be the same trap mirrored.
- swing-daily (n=1, one −10.16% stop) and breakout-4h (n=6): too thin to
  slice; nothing to pull.

### 4.5 The long side at admission — (a)-shaped, but the gate already exists
Directional longs: −0.227%/trade, t=−2.56, n=385. This is the standing
long-budget doctrine, not a new finding — and (ji) just measured that NO
additional signal-gate on this tape improves any book once the null is
applied (three of four signals are constants). The recoverable dollars here
are not in a new gate: **78% of the open stop-pool losses above are
long-side cells**, so targets 4.1/4.4 ARE the long-side fix.
- ROUTE: **[nothing-to-pull]** beyond what stands (LONG_BUDGET rationing,
  per-asset regime gate fail-closed). Explicitly do NOT raise LONG_BUDGET.

### 4.6 Small red cells, named so they are not re-found
- Farmer-shadow short·sl: 6 carry-position stops at 44h, −$5.86 — n too small
  to act; watch. Farmer both arms are in-era positive (live +0.337%/t=1.30,
  shadow +0.220%/t=1.04) with the earn in `decay`+`tp`.
- Taker sl cells (both arms 0% win, −$6.96 combined, n=10): the bracket
  working as designed against tp +$12.49 — **do not touch**; the graded era
  just froze ((jf)/(hm)).
- 🌾 carry: n=1 in-era. The book is stalled, not broken — **[operator]**
  keep-or-retire stands; both loosening levers already refused on
  measurement ((it)).

## 5. WIN-RATE HONESTY — the DO-NOT-DO list

Each of these raises reported win rate (or n) and was refused on a number:

1. **Remove/loosen stops without a calibrated sweep** — win rate rises
   mechanically (every 0%-win cell vanishes); the tail is unbounded. The
   fleet already ran it: 🏆 Stock Leaders, 3 closes, ALL catastrophic-stop,
   −$91.90, maxDD 37–44%, retired.
2. **Tight-tp genes (the tp-0.06 shape, I15)** — high win rate, measured
   UNSUPPORTED expectancy (incubator verdict stands). A 100%-win tp family
   (+$62.54 here) says nothing about widening it or tightening it.
3. **Flip books short to harvest the drift** — a random short already earns
   +0.2–1.1%/trade free; our directional shorts net −0.008%. Adding shorts
   buys win rate on regime beta that inverts on the first BTC `dir=+1` bar
   (never yet observed on this tape — (ji)).
4. **Raise LONG_BUDGET** — the budget rations the measured losing side
   (−0.227%/t=−2.56). Refused standing.
5. **carry.enter_apr 20%→10% for turnover** — refused (it): a 29bps round
   trip needs 254h of a 336h max hold to break even at 10% TRUE; the 21-Jul
   sweep measured the direction loss-making. Turnover bought with expectancy
   is a step back in a growth costume.
6. **Grade slow books on daily marks to "find" n** — n×H, SNR÷√H, t
   unchanged ((hp)); it only lowers the bar.
7. **A consensus/ensemble entry gate** — measured and refused in full
   ((ji)): 84 cells, 2 survivors at exactly the luck expectation.

## 6. TOP 5 IMPROVEMENT TARGETS, ranked by recoverable $

| # | target | in-era pool | route |
|---|---|---|---|
| 1 | **Parliament ~1% stops** (6 books, 176 stops, 0% win) | **−$50.10** | [already-shipped (jj)] gillard's accelerated sl-walk runs now; [lever-proposal] extend to the other five PMs after gillard's out-of-sample verdict AND per-book `calibrate()` passes. (gx) gradient on gillard: −0.158→+0.050%/trade with DD falling ≈ +$12 on that book alone. |
| 2 | **⚖️ CW rebalance bleed** | **−$31.31** | [SOLVED-PENDING-EVIDENCE (jg)] — unwind observed 00:37Z 5-Aug (12 legs, SOXL/SNDK/MU); expect the payload to read worse as MTM realises; ~28-Aug pre-registered read. |
| 3 | **Spot/family stops** (intraday-15m + georgia; dad's donchian) | **−$27.14** | [implement-now (measurement)] `study_exit_sweep` on post-(gr) priced closes, `calibrate()` gate decides; ship only through backtest-first + replay. |
| 4 | **🧲 Snap Back bleed** | ~−$1/day (t=−2.82, n=189) | [SOLVED-PENDING-EVIDENCE (jh)] + [operator] stop `snap-back-shadow` (queue item 3). |
| 5 | **Long-side discipline** | −$9.36 direct; delivered via #1/#3 (78% of the stop pool is long-side) | [nothing-to-pull] — keep the budget and fail-closed regime gates; refuse every loosening on the list in §5. Plus [operator]: the carry keep-or-retire. |

**The I15 closing line, for the operator's question as asked:** the fleet's
win rate is not low because winners are scarce — `tp`/`roi` cells run 100%
win by construction and shorts/longs win within 0.5pp of each other. It is
low because **stop populations that never win keep being entered and then
realised at the bottom of their reversion**. The win-rate improvement that
does not cost expectancy is №1 and №3: stop realising reversion losses, per
book, through the calibrated sweep gate — and everything in §5 is the same
number dressed better.

---
*Method artifacts (script + JSON cells) in the session scratchpad; every
number above reproduces from `paper_trades` via the production fetch with the
eras stated in §1. Study is publish-only: no lever was written, no bar moved.*
