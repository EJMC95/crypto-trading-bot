# STUDY: 👩 mum v2 — the bar at 32, and the hold
**2026-08-27.** Eamon: *"Widen mum to 32, maximise her optics metrics and parameters."*

Script: `scripts/study_mum_params_2026-08-27.py` (bars PRE-REGISTERED, committed
`6f04ca2` before any number existed). Tape: Lighter's own 1h candles, her actual
23-symbol resolved universe, median 460d coverage. Indicators are the bot's own
`rsi_series`/`ema_series`. LAG-1 throughout. Episodes, not ticks.

---

## CALIBRATION FIRST — the harness reproduces (tr) before it is allowed to speak

`(gx)`: a harness that cannot reproduce what DID happen may not say what WOULD
have. Control cell = (tr)'s ADMITTED C3 (`rsi 25-30 & NOT-uptrend`):

| quantity | (tr) published | this harness |
|---|---|---|
| episodes | 2,296 | **2,297** |
| bracket %/trade | +0.104% | **+0.110%** |
| both halves | positive | **+0.106 / +0.113** |
| exit-free h12 excess | +0.156% | **+0.165%** |
| exit-free h12 t_cl | +2.25 | **+2.40** |

**PASS.** Everything below is reported on that basis.

---

## Q1 — THE BAR

### The pre-registered cells (isolated slivers)

| cell | n | bracket %/trade | h12 excess | h12 t_cl | trailing-120d | verdict |
|---|---|---|---|---|---|---|
| D0 `rsi 25-30` (control) | 2297 | **+0.110%** | +0.165% | +2.40 | +0.129% | ADMIT (reproduces) |
| D1 `rsi 30-32` **(the ask)** | 2099 | +0.062% | +0.003% | +0.04 | **−0.175%** | HYPOTHESIS |
| D2 `rsi 32-34` | 2526 | −0.038% | −0.026% | −0.40 | −0.173% | REFUSE |
| D3 `rsi 30-42` (control) | 7465 | −0.081% | +0.045% | +1.16 | −0.122% | REFUSE (reproduces (tr)'s C4) |

### THE PRE-REGISTRATION TESTED THE WRONG OBJECT — and the counts prove it

I decomposed "widen the bar" into an isolated sliver `[30,32)`. **That is not
what widening a threshold does.** Episodes are runs of consecutive qualifying
bars, so widening MERGES adjacent runs and moves the entry earlier:

```
rsi<30  episodes 2110      rsi<32  episodes 2784
[30,32) episodes 2099      2110 + 2099 = 4209  !=  2784
median entry RSI: 28.2 (rsi<30)  ->  30.2 (rsi<32)
```

`[30,32)` **in isolation** means "RSI entered 30–32 and did NOT continue below
30" — i.e. the dips that failed. That is an adversely-selected subset, and it
is why D1 looks weak. Under a widened threshold those same bars are the ENTRY
POINT of dips that do continue.

### The real candidate, measured

| cell | n | %/trade | t_cl | halves | trailing-120d | eps/day |
|---|---|---|---|---|---|---|
| `rsi<30` **(shipped)** | 2110 | +0.075% | +1.47 | +0.062/+0.087 | +0.143% | 4.59 |
| **`rsi<32` (the ask)** | 2784 | **+0.111%** | **+2.44** | **+0.114/+0.108** | **+0.172%** | **6.05** |
| `rsi 22-32` (band) | 3135 | +0.127% | +2.82 | +0.139/+0.115 | +0.163% | 6.82 |
| `rsi 25-32` (band) | 3181 | +0.123% | +2.65 | +0.138/+0.107 | +0.146% | 6.92 |

**`rsi<32` beats the shipped bar on every axis: +48% per trade, cluster-t over
2.0, both halves positive, better trailing-120d, and +32% more trades.**

Robustness (same bars (tr) used):
* **coin jackknife**: worst drop (DOT) → +0.088%/trade, **t_cl +1.86** — better
  than the +1.68 of the cell (tr) shipped yesterday. Not carried by one coin.
* **months**: 11/15 positive; recent 2026-07 +0.335, 2026-08 +0.612; worst
  2026-01 −0.849.
* **exit mix**: roi 1944 (70%), stop 457 (16%), max_hold 383 (14%) — the roi
  ladder banks 70%, matching (tr)'s own note.

**HONEST STATUS: `rsi<32` is measured, robust, and NOT what I pre-registered.**
The pre-registration is what failed, not the measurement — and the failure is
now understood and written down. Before shipping to a real-money book it wants
the referee pass (tr) ran: independent code, regime-conditional null,
coin-week clustering.

**The bands are BETTER STILL but are post-hoc** (I chose 22 after seeing the
gradient). They are the next pre-registered candidate, not tonight's change.

---

## Q2 — THE HOLD: (tr)'s watch item resolved, and the answer is KEEP 24h

(tr) flagged "max_hold exits −1.11%/trade; the surviving edge lives ≤12h" as
the next candidate. Swept on her shipped cell, entries CONSTANT, only the exit
moving:

| hold | n | %/trade | t_cl | halves | mean hold | **%/bar-day** | roi/stop/hold |
|---|---|---|---|---|---|---|---|
| 8h | 2110 | +0.065% | +1.56 | +0.087/+0.042 | 5.9h | **+0.265** | 721/201/1188 |
| 12h | 2110 | +0.038% | +0.82 | +0.026/+0.051 | 7.6h | +0.120 | 989/267/854 |
| 16h | 2110 | +0.054% | +1.11 | +0.058/+0.051 | 8.9h | +0.147 | 1220/314/576 |
| 20h | 2110 | +0.071% | +1.42 | +0.066/+0.076 | 9.8h | +0.174 | 1375/342/393 |
| **24h (shipped)** | 2110 | **+0.075%** | **+1.47** | +0.062/+0.087 | 10.4h | +0.172 | 1455/365/290 |

**ALL FOUR SHORTER HOLDS REFUSED.** 24h is the best on per-trade return and
statistically strongest. `hold=8` earns 54% more **per bar-day** (+0.265 vs
+0.172) — but that is the `(hl)` denominator-shrinkage signature, and the
pre-declared bar (a) caught it: mum has **4 slots and is currently flat**, so
she is NOT capital-constrained and per-trade is the metric that matters. If she
were ever slot-bound, `hold=8` becomes the right answer — that condition is
worth watching, not acting on today.

**(tr)'s worry was unfounded and the shipped 24h stands.** A refusal with
numbers is a first-class outcome.

---

## What this changes

* **RECOMMEND** `MUM_RSI_MAX` 30 → **32** (`mum-live`), after the referee pass.
  Real money → Eamon's act.
* **KEEP** `max_hold` at 24h. Measured, refused, closed.
* **NEXT pre-registered candidate:** the band `rsi 22-32` (drops the decayed
  deep-oversold tail `(qu)` already measured through zero: +4.97 → +2.05 →
  −0.31 → −0.41). Reads +0.127%/trade, t_cl +2.82, 6.82 eps/day — but post-hoc,
  so it earns its own study, not a same-day ship.
