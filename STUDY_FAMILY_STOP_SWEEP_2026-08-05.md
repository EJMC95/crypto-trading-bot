# STUDY: THE SPOT/FAMILY STOP CELLS UNDER THE CALIBRATED EXIT COUNTERFACTUAL (2026-08-05)

**The ask (decomp target #3):** `STUDY_WIN_LOSS_DECOMP_2026-08-05.md` §4.4 / TOP-5
№3 — the three biggest non-Parliament stop cells (**−$27.14 in-era pool**:
crypto-intraday-15m sl −$11.68 at 4.8% win, freqtrade-georgia sl −$10.10 at
11.6% win, freqtrade-dad donchian −$5.36) — run through the existing calibrated
instrument, `scripts/study_exit_sweep.py`, on post-(gr) PRICED closes. The
calibration gate decides whether a recommendation is even utterable.

**Headline verdicts:**

| book | verdict |
|---|---|
| 🔮 freqtrade-georgia-lshadow | **CALIBRATED (gap −0.001pp)** — the shipped 5% stop cap is the **INTERIOR OPTIMUM** of the sl walk: **KEEP SHIPPED**. One expand-direction signal (longer max-hold) is **UNBOUNDED at the grid edge**, not a value. |
| ⚡ crypto-intraday-15m-lshadow | **REFUSED TWICE OVER** — population-matched sample is 9 covered priced closes < the 10 floor (BONK/PEPE unreplayable), and the replay misses calibration tol anyway. Re-run **~7-Aug**. |
| 👨 freqtrade-dad-lshadow | **REFUSED — wrong instrument, declared**: 1 priced close (n=10 ~**20-Aug**), and `donchian_breakdown` is a SIGNAL exit outside the harness vocabulary — calibration predictably refuses even at n. Needs a signal-exit arm. |

**Nothing was changed**: no bot logic, no lever, no param. Study + changelog only.

---

## 1. Method — the existing instrument, driven honestly

- **Instrument**: `scripts/study_exit_sweep.py` UNCHANGED (selftest green under
  `.venv/bin/python3` before the run). Hourly Lighter candles, adverse-first
  intra-bar, entries held constant, throughput modelled at each book's real
  `max_open`. A scratchpad driver supplied what its `main()` does not pass:
  the shipped rule, the actual ledger mean, and the cap.
- **Rows**: `study_exit_attribution.fetch_trades` (the sweep's own production
  fetch), then `bot_pnl_store.is_quarantined` applied at source per the (ji)
  standing warning — **44 rows withheld, all ticket-taker BOT/CXMT; zero on
  these three books**.
- **Shipped rules READ FROM THE MODULE, not guessed** ((gx)'s named blocker):
  `lighter_family_bot.STRATEGIES` gives georgia `DayTraderGated(stoploss=−0.05,
  max_open=5)`, intraday `DayTraderGated(stoploss=−0.12, max_open=5)`, dad
  `MomoBreakout(stoploss=−0.12, max_open=4)`. Static mapping into the harness
  vocabulary: `sl_pct` = the config stoploss (the CAP on the ATR trail),
  `tp_pct` = ROI ladder rung 0 (0.018), `max_hold_h` = 24 (the
  `max_hold_timeout` at 1440 min).
- **DECLARED OMISSIONS** (not expressible in {tp, sl, max_hold, trail}): the
  2.5x/3.5x ATR ratcheting trail (`atr_stop_dist` — per-trade, ATR-dependent),
  the ROI ladder's time decay (180/360/720-min rungs), the `range_top` signal
  exit, the bounce timeouts, and dad's `donchian_breakdown` entirely.
  **`calibrate()` is the judge of whether these omissions matter per book** —
  that is its whole job, and it ruled differently on the two DayTraderGated
  books, which is the instrument working.
- **Baseline**: the actual ledger mean over the SAME priced rows the replay
  covers. Population-matching matters and changed one verdict (§3).
- All three books' priced rows are in-era by construction (priced telemetry
  began at (gr) 30-Jul; family eras are ≥17-Jul).

## 2. 🔮 georgia — calibrated; the stop cap is already at the optimum

**Calibration PASSES**: 30 priced closes (29 replayed — 1 entry skipped by the
cap model, a genuine throughput effect), all 9 symbols candle-covered. Replayed
shipped mean **+0.255%/trade vs actual +0.256%** (gap −0.001pp, tol 0.25).
Honesty: this is a MEAN-level gate, and the mechanism mix differs underneath it
(replay closes tp 14 / max_hold 10 / sl 1 / horizon 4; the real ledger closes
trailing_stop 14 / roi 11 / range_top 7) — the static bracket reproduces the
book's aggregate arithmetic, not its exit labels. A −0.001pp agreement on n=29
is partly luck; the gate's claim is only "within 0.25pp".

**The sl walk** (tp 1.8% and hold 24h pinned at shipped; cap 5):

| sl | n | mean%/t | total% | maxDD% | win% | med hold | exit mix |
|---|---|---|---|---|---|---|---|
| 1% | 30 | −0.625 | −18.74 | 18.74 | 13.3 | 1.2h | sl 23 / tp 3 / hold 4 |
| 1.5% | 29 | −0.535 | −15.52 | 16.12 | 27.6 | 4.7h | sl 16 / tp 6 / hold 6 |
| 2% | 29 | −0.399 | −11.58 | 14.98 | 37.9 | 7.2h | sl 12 / tp 9 / hold 7 |
| 3% | 29 | +0.141 | +4.10 | 7.33 | 55.2 | 13.3h | sl 4 / tp 13 / hold 9 |
| **5% = SHIPPED** | 29 | **+0.255** | **+7.39** | 8.74 | 58.6 | 14.0h | sl 1 / tp 14 / hold 10 |
| 8% | 29 | +0.192 | +5.55 | 10.58 | 58.6 | 14.0h | tp 14 / hold 11 |
| 12% | 29 | +0.192 | +5.55 | 10.58 | 58.6 | 14.0h | tp 14 / hold 11 |

- **Direction/monotonicity**: mean rises MONOTONICALLY from 1% to the shipped
  5%, then gives back beyond it. Drawdown falls 18.7% → 7.3% across the same
  tightening-to-3% stretch and stays benign at 5%. **The winner is INTERIOR
  and it is the shipped value** — verdict `keep_shipped`.
- **This is the gillard mechanism read from the other side.** (gx) measured
  gillard's 1% stop realising reversion losses (sl 1→3% moved her
  −0.158→+0.050%/trade with DD FALLING 40.7→26.0%). Georgia at a
  Parliament-style 1% would be −0.625%/t at 18.7% DD — the same defect
  recreated — but her cap already sits where the gradient peaks. The decomp's
  №1 mechanism (stops realising reversion) is hereby confirmed on a second
  book, from the tight side, calibrated.
- **What this does NOT clear**: her era sl slice (−$10.10 at 11.6% win) is not
  recoverable by moving the CAP — no sl value beats shipped. The un-swept knob
  is the **ATR multiplier** (2.5x, 3.5x counter-trend), which fires the actual
  trailing stops and is NOT representable per-trade in this instrument today
  (needs a per-trade trail arm computing ATR from candles at entry). That is an
  instrument extension, deliberately not built tonight (I11 — one surface per
  pass), and it may yet find the slice unfixable: the trail's aggregate cost is
  already inside a book that nets +0.256%/trade.

**The hold walk** (sl 5% pinned):

| max_hold | n | mean%/t | total% | maxDD% | h1 / h2 | skipped |
|---|---|---|---|---|---|---|
| 4h | 30 | +0.110 | +3.30 | 5.08 | +4.96 / −1.65 | 0 |
| 12h | 30 | −0.001 | −0.03 | 8.61 | +6.03 / −6.05 | 0 |
| **24h = SHIPPED** | 29 | +0.255 | +7.39 | 8.74 | +7.46 / −0.07 | 1 |
| 48h | 26 | +0.458 | +11.90 | 10.00 | +6.79 / +5.12 | 4 |
| 96h | 25 | +0.613 | +15.32 | 10.00 | +8.00 / +7.32 | 5 |

- Non-monotone at the short end (4h beats 12h); consistently rising 24→96h.
  The full grid's one candidate to clear EVERY floor is {hold 96h, sl 8%}:
  +0.29pp edge, both halves up, DD 8.0 ≤ shipped 8.74, throughput paid (6
  entries skipped, n 24). The two better-total rules were correctly refused —
  {96h, 5%} on drawdown (10.0 > 8.74), {96h, 3%} on h2.
- **96 is the GRID EDGE → the finding is UNBOUNDED**, per (gx): "widen the
  grid", never "ship 96". Reported as a direction only.
- **The (hm)/era price of ever acting on it, stated now**: a max-hold rewrite
  24h→96h on a 15-minute day-trading book is an exit rule DIFFERENT IN KIND —
  it restarts the 30-day single-policy clock and plausibly resets POLICY_ERA,
  discarding the 30-close priced sample georgia is currently accruing at
  +0.256%/trade. **Keep-shipped costs nothing and keeps her clock running.**
  Route if it ever survives a widened grid: backtest-first (the widened sweep
  IS the backtest) → review → a deliberate param change with the clock cost
  priced in — never a hand edit, never mid-pass.

## 3. ⚡ intraday-15m — refused twice over; the honest date is ~7-Aug

- 12 priced closes, but **BONK and PEPE carry no Lighter market id today**
  (absent from `orderBookDetails`), so 3 of the 12 are unreplayable — no
  candles exist to walk. The **population-matched** run (baseline and replay
  over the same 9 covered trades) is **9 < the 10-close floor: the sweep
  refuses before replaying**. This is the sound framing; the earlier
  12-row-baseline/9-trade-replay comparison was apples-to-oranges and is
  reported only as corroboration below.
- **Calibration misses anyway**: the replayed shipped rule ({sl 12%, tp 1.8%,
  hold 24h}) scores **−0.780%/trade** against actual −0.435% on the covered
  rows (−0.377% on all 12) — a gap of −0.345/−0.402pp against a 0.25pp tol.
  On THIS book the ATR-trail omission is material where it was not on
  georgia's sample: the real trail cut UNI at −4.66% and AAVE at −3.59% while
  the static 12% cap replay rides losers to max_hold/horizon. Per the gate:
  **RECOMMENDATIONS WITHHELD** — no sl direction table is published here,
  because quoting an uncalibrated walk invites believing it.
- **Feasibility**: priced closes accrue ~2.6/day (12 in 4.6 days), covered
  ~2/day — the n floor clears within days; **re-run ~7-Aug**. Whether
  calibration then passes is the gate's call, not a promise: georgia proves
  the static mapping CAN calibrate a DayTraderGated book; if intraday keeps
  missing, the per-trade ATR-trail arm is the route for it too.
- Honesty about the target cell: the decomp's −$11.68/21-stop cell is mostly
  PRE-(gr) — only 6 of the 12 priced closes are trailing stops. The 43
  unpriced closes (13→29 Jul) never become sweepable; the counterfactual can
  only ever speak to the priced window.

## 4. 👨 dad — n=1, and the wrong instrument even at n

- **1 priced close** (SOL −8.48%, `donchian_breakdown`, closed 1-Aug). Floor
  is 10. At his measured rate (11 closes over 19.2 days ≈ 0.57/day), n=10
  priced arrives **~20/21-Aug**.
- **The structural blocker outranks the date**: `donchian_breakdown` is a
  SIGNAL exit — price crossing a rolling channel — which the harness
  vocabulary {tp, sl, max_hold, trail} cannot express. A `{sl 12%}` baseline
  omits the exit that produced 12 of the 13 era donchian-family closes (dad 7
  + crypto-breakout-4h 6, per (gq)), so `calibrate()` will predictably refuse
  even once n arrives. This is the FUNDING_BOOKS class — wrong instrument,
  refused rather than caveated — and it applies equally to breakout-4h.
- **Route to feasibility**: a signal-exit arm that replays
  `MomoBreakout.signals` (the book's own function) over Lighter candles to
  locate the counterfactual breakdown bar. A different instrument arm; filed,
  not built tonight.

## 5. DO-NOT-DO check — what separates this from Stock Leaders

🏆 Stock Leaders is the precedent: stops effectively loosened without a
calibrated counterfactual, 3 closes ALL catastrophic-stop, **−$91.90**, maxDD
37–44%, retired. Tonight: **zero stops moved**. The calibrated book's answer is
KEEP; the two uncalibrated books produce refusals with dates instead of
numbers; the one expand-direction signal is explicitly UNBOUNDED and unshipped,
with its era cost stated. A refusal with evidence satisfies ONLY GROWTH — a
silent omission does not, which is why §3 states exactly what was checked
before refusing.

Live-bots-in-scope: nothing here reaches the live pair. Their stop cells were
graded in the decomp (§4.6: the taker's bracket sl working as designed against
tp +$12.49, era frozen (jf) — do-not-touch; farmer sl n too small to act).
This study moves nothing.

## 6. Carried forward (I11)

1. **~7-Aug**: re-run intraday-15m when the 10th covered priced close lands —
   the gate decides.
2. **~20-Aug**: dad's n arrives; useless without (3).
3. **Instrument extension, one job**: a per-trade ATR-trail arm (georgia's
   un-swept knob + intraday's likely calibration fix) and/or the signal-exit
   arm (dad + breakout-4h). Measurement work; no bot logic.
4. Georgia's hold direction: widen the grid (48→192h+) BEFORE any belief —
   and re-read §2's era cost first.

**Forward metric**: 🔮 georgia is the book that moved — she keeps accruing
toward the gate (30 priced closes at +0.256%/trade) with the calibrated
assurance that her stop cap is not the leak, at zero clock cost.

---
*Method artifacts (driver + full JSON) in the session scratchpad; every number
reproduces from the production fetch + `study_exit_sweep` at HEAD with the
shipped rules read from `lighter_family_bot.STRATEGIES`. Publish-only.*
