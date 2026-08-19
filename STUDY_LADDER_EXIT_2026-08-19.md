# STUDY — the ladder-aware exit replay, and 🔮 georgia's answer (2026-08-19)

Built because `(ql)` DECLARED the family carriers unsweepable and named the
only honest way to answer them: *"a ladder-aware replay — a build, not a
re-run."* Driver: `scripts/study_ladder_exit_sweep.py`, rules C1–C6
pre-registered in its header before any result existed.

## The question

The brain has published `exit_too_tight` on 🔮 georgia in **129 of 129 runs
for 8+ days** — reclaim **1.0** (every losing exit reclaimed its entry within
24h), forward **+1.63%**, trailing-stop path **−$17.14 over 71 era closes**
against an roi path earning **+$17.70**. A measured direction with no
instrument able to test it is the I18 shape, and `study_exit_sweep` cannot
express georgia's rule (time-decaying ROI ladder + ATR ratchet) without
handing `calibrate()` a fiction — the `(ps)` false-pass.

## Verdict: the widening is REFUTED — under BOTH intrabar conventions

**C1 calibration PASSED**, and the exit mix reproduces exactly:

| | replayed | actual |
|---|---|---|
| mean price return | +0.112pp | −0.128pp (delta 0.241pp, tol 0.25) |
| exit mix | `{tsl: 25, roi: 6}` | `{tsl: 25, roi: 6}` — **identical** |

**The sweep, stop width only (roi HELD at shipped, C3):**

| atr_mult | adverse | ratchet_first | worst trade |
|---|---|---|---|
| 2.0× | +0.128pp | −0.077pp | −0.76pp |
| **2.5× (shipped)** | **+0.112pp** | **−0.083pp** | −1.00pp |
| 3.0× | −0.003pp | −0.057pp | −1.18pp |
| 3.5× | −0.131pp | −0.146pp | −1.45pp |
| 4.0× | −0.026pp | −0.050pp | −1.68pp |
| 5.0× | −0.097pp | −0.139pp | −1.79pp |

**No widening cell survives C4 (plateau) or C5 (worst-trade) in either arm.**
Under `adverse` no widening cell beats shipped at all. Under `ratchet_first`
3.0× and 4.0× beat it while **3.5× between them is worse** — a broken
plateau, exactly the lone spike C4 exists to kill. And the worst single trade
degrades **monotonically** with width in both arms (−0.76 → −1.79pp), so C5
fails for every widening cell: a wider stop here defers ruin rather than
avoiding it.

## THE INTRABAR CONVENTION IS AMBIGUOUS, AND BOTH ARMS ARE RUN

This is the load-bearing methodological point, found by mutation-testing the
harness against itself. The live loop is **90s** against a **15m** timeframe,
so the real ratchet samples ~10× per bar:

* **`adverse`** (stop tested on the LOW before the HIGH ratchets) — the classic
  conservative choice. Reproduces the exit MIX **exactly** (81% vs 81%); mean
  is 0.241pp off.
* **`ratchet_first`** (mirrors the 90s loop) — reproduces the MEAN to
  **0.045pp**; overstates stop-outs (90% vs 81%).

**Neither dominates**, so per the `(ne)`/gillard precedent a verdict counts
only if both agree. They do: *no widening is supported.* Recorded because the
tempting move was to pick the convention that calibrated best on the mean and
report its numbers — which would have shipped `3.0×`/`4.0×` as winners off a
broken plateau.

## Incidental finding: georgia's carrier stoploss is INERT

Every `stop_cap` value (5%, 7.5%, 10%) gives a **byte-identical** result at
every multiplier: `min(mult*atr/px, cap)` never reaches the cap, because
2.5×ATR on 15m bars is far tighter than 5%. **`stoploss=-0.05` cannot bind on
this book** — a constant that cannot bind is not a lever (I18). It is not
removed here (it is the carrier's shared declaration and binds on other
books); it is recorded so nobody tunes it expecting an effect.

## Declared limits

* **n=31 scored** of 124 lifetime closes — only rows carrying entry+exit price
  AND side are replayable (prices since `(gr)` 30-Jul, side since `(kn)`
  6-Aug). The sample heals forward.
* **2 of 33 rows excluded**: the `exit_signal`/`range_top` path needs the ENTRY
  strategy re-run, and the sweep doctrine holds entries constant. 6% of the
  replayable set, declared, never scored.
* Calibration passed at **0.241pp against a 0.25pp tolerance** on the `adverse`
  arm — a marginal pass, and the replayed mean differs in SIGN from actual on
  a book whose mean is ~0. So the *direction* is the trustworthy output here;
  no absolute per-trade claim should be quoted from this harness.

## What it buys

The brain's standing proposal on georgia is answered and refused with numbers,
which stops a change that looked obviously right from `reclaim=1.0` alone. And
the instrument generalises: 🙏 **avo maria** — the fleet's best-evidenced book
and its nearest gate candidate — rides the same SwingDip ladder and was
equally untestable until now.
