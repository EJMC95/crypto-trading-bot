# 🎯 THE SNIPER'S "LOST POTENCY" — MEASURED, AND REFUSED
### 2026-08-20 (ts) · operator ask: *"look back to the days its p n l was biggest in the fleet — strip back whatever has caused it to have 'erectile dysfunction'"*

---

## ⚠️ READ THIS FIRST — THE CALIBRATION GATE FAILED

`scripts/study_sniper_exit_shape_2026-08-20.py` **cannot reproduce this book's own
ledger** and therefore **refuses to emit recommendations** ((gx)): replayed
+0.230%/trade vs matched ledger −0.104%/trade, gap **+0.334pp** against a 0.15pp
tolerance, one-sided (94% of the error mass optimistic), **0 of 6 price/slippage
bases calibrate**. `run_sweep()` returns `{"refused": True, "cells": []}`.

The cause is irreducible from Lighter's public candles, and was diagnosed rather
than assumed: the bot decides on a **60s-polled orderbook mid**, a quantity the
candle API does not carry at any resolution it offers (NZDUSD's print was stale
by 65bps while the book had moved; MRNA's mid at its poll instant sat 1.3% below
that minute's close). A spread-based correction was tested and refuted
(corr = 0.26); no partition calibrates.

**The bias envelope, 0.334pp/trade, is 3.2× the entire magnitude of the book's
own mean.** So no sweep number in this document arms anything. The verdict rests
on the four instruments that need **no** calibration: the exit-free paired rank
test, the matched-random null, the oracle-ceiling-vs-MDE arithmetic, and the
supply census.

---

## 1 · WHAT ACTUALLY EARNED THE MONEY — one coin, and not the mechanism anyone remembers

The 🎯 Launch Sniper (`event-listing-sniper`, retired 17-Jul under LIGHTER-ONLY)
made **+$206.38 over 366 closes**, peaking at **+$275.01 on 29-Jun**.

| population | n | total | mean $/trade | t | win |
|---|---|---|---|---|---|
| ALL closes | 366 | +$206.38 | +0.564 | 0.86 | 11.2% |
| **ANSEM/USDT only** | **3** | **+$325.01** | +108.34 | 2.34 | 100% |
| **EX-ANSEM** | 363 | **−$118.63** | −0.327 | −1.21 | 10.5% |

**One trade is 96.9% of lifetime P&L. Top-3 are 157.5%.** For scale: 🧙 Schwager
was retired 17-Aug (po) as UNDECIDABLE BY TAIL with top-3 at **112%**. This book
is worse, and its three rows are two positions in **one coin**.

### The exit ladder is not the earner — it *cost* money on the one trade that mattered

The predecessor's "EXPERT EXIT MODEL" was genuinely convex: scale out 50% at
**2× (+100%)**, trail the runner **30% off peak** once armed at +50%, far
take-profit at **5× (+400%)**, −50% stop, unlimited hold. ANSEM walked straight
to the 5× gate.

Counterfactual against the all-or-nothing rule it replaced (sell 100% at 5×):

| episode | actual | sell-all-at-tp1 | ladder Δ | runner exit |
|---|---|---|---|---|
| INDEX/lbank | 51.24 | 51.70 | **−0.46** | trail_stop |
| BIBI/lbank | 44.57 | 51.36 | **−6.79** | trail_stop |
| SSS/xt | 34.74 | 56.06 | **−21.32** | trail_stop |
| LEVI/lbank | 24.94 | 29.48 | **−4.54** | trail_stop |
| **ANSEM/lbank** | 273.71 | 147.42 | **+126.29** | **take_profit (+400%)** |

- **The trail fired 4 times and is 0-for-4, −$33.11.**
- **The far TP fired once in 361 episodes and is the entire +$126.29.**
- On ANSEM the ladder **cost −$126.29** versus simply holding to 5×.

So the thing to "restore" is not the scale-out and not the trail. It is *a coin
that goes up 400%*.

### And the book was mostly trading nothing

**321 of 366 closes (87.7%) are baseline-reseed artifacts** — 31 bursts, the
tightest 25 positions in 12 seconds, opening AAPL/QQQ/GME/NEAR/BONK and other
long-listed markets that read as "brand new" whenever the state read flaked.
Burst rows: **−$127.54 at t=−6.33**. 296 closes exit `delisted` at ~the entry
slippage — a pure friction tax on phantom tickets.

**That disease is already cured on the living book**: `lighter_perp_sniper.py`'s
17-Jul SEED GUARD refuses to run on an unreadable state rather than re-seeding.

### What killed it: nothing did, and not the LIGHTER-ONLY guard

The decline began **2-Jul, ~62h before** the 4-Jul throttle commit; the throttle
was the response, not the cause, and it **worked** (2–4 Jul cohort −$117.87 at
t=−2.74 → post-throttle +$51.36 at t=0.72). Between 4-Jul and its last close the
book moved **+$12.31 in 12 days**. The 17-Jul guard stopped a break-even book.

---

## 2 · WHY THE REPLACEMENT CANNOT EARN — and it is the ENTRY, not the bracket

🎯 `lighter-perp-sniper-lshadow`: **33 closes, −$0.79, mean −0.092%, t=−0.12**;
32 of 33 exit `max_hold`; the stop has never fired; the take-profit fired once
(MRNA, 19-Aug, +15.21%). Lifetime peak realised P&L: **+$1.86**. There was never
a good period.

### The +15% take-profit is a near-dead branch — measured

MFE over the 6h window on the book's own 33 entries, Lighter 1m tape, LAG-1:

| | value | | threshold | touched |
|---|---|---|---|---|
| median MFE | **+0.81%** | | ≥ +15% | **1 / 33** |
| p75 | +3.83% | | ≥ +10% | 2 |
| max | +18.10% | | ≥ +2% | 12 |
| mean | +2.77% | | ≥ +1% | 16 |

**17 of 33 never reached even +1%.** A matched-random 6h long touches +15% at
**0.90%**; observed 3.03%; P(≥1 tp | null) = **0.258**. The one firing is not
evidence.

### The entries select VOLATILITY, not DIRECTION

12,400 matched-random 6h longs, same coins, same window, LAG-1:

| | actual (n=33) | random | P(random ≥ actual) |
|---|---|---|---|
| mean 6h RANGE (MFE−MAE) | **4.878%** | 2.845% | **0.009** |
| mean MFE | +2.770% | +1.545% | 0.032 |
| mean MAE | −2.108% | −1.300% | 0.028 |
| **realised return** | — | — | **0.406** |

Exit mix vs the null: `tp` 1 observed / 0.30 expected, `sl` 0 / 0.44,
`max_hold` 32 / **32.26**. **A zero-edge entry produces this ledger exactly.**

**The exit-free paired rank test** (no exit modelled, so the calibration failure
is common-mode and cancels): each real entry ranked against 300 matched-random
minutes on the same coin and window.

| horizon | 0.25h | 1h | 3h | 6h | 12h |
|---|---|---|---|---|---|
| mean percentile | 0.484 | 0.517 | 0.500 | 0.511 | 0.515 |

**The sniper's chosen minute sits at the 50th percentile at every horizon**;
|t vs 0.5| never exceeds 0.61. Per source, `surge` — the only living one — reads
**0.429 at the shipped 6h hold, i.e. worse than random.**

A long-only bracket on a symmetric range expansion is a coin flip paid for in
friction. This is (qu)'s finding on 🙏 avo arriving by a different road, and it
is why bracket tuning cannot work: **there is no entry edge for any exit to
harvest.**

---

## 3 · THE ANSEM SHAPE, REPLAYED HERE — structurally inert, not merely worse

The predecessor's exact constants on this book are **byte-identical to a bare
timer at every horizon**:

| hold | ANSEM shape | content-free timer | Δ |
|---|---|---|---|
| 24h | n=30, +$3.15, +0.531% | n=30, +$3.15, +0.531% | **$0.00** |
| 48h | n=21, +$6.27, +1.488% | n=21, +$6.27, +1.488% | **$0.00** |
| 72h | n=18, +$10.42, +2.890% | n=18, +$10.42, +2.890% | **$0.00** |

Zero ladder / trail / far-TP / −35%-stop fires. The triggers are unreachable on
this book's own 72h max-favourable excursion:

| ≥ +15% | ≥ +30% | ≥ +50% (trail arm) | ≥ +100% (tp1) | ≥ +400% (far TP) |
|---|---|---|---|---|
| 6 / 32 | 2 / 32 | **0** | **0** | **0** |

Against the predecessor: **8 of its 366 closes realised ≥+100%, and one +400%.**
**The supply, not the exit rule, is the whole difference** — I7 in its purest form.

### And the trail family's apparent edge *is* the harness error

Drop the six rows the calibration proved unpriceable (CXMT, MINIMAX, MRNA,
NZDUSD, UNITREE, WHEAT — 94% of error mass):

| cell | all rows | **ex-mispriced (n=25)** | t |
|---|---|---|---|
| best trail | +1.015% | **+0.059%** | +0.04 |
| best ladder | +0.937% | **−0.038%** | −0.03 |
| SHIPPED @24h | +1.018% | −0.180% | −0.12 |

---

## 4 · BOTH DIRECTIONS REFUSED, WITH NUMBERS

**Tightening.** The 1-D take-profit response is a hump, not monotone: every TP
below 5% is **negative** and tp=1% is the worst cell in the sweep. "A +3% TP that
fires often" was tested directly — it fires 9 of 32 times and **loses**. The
interior peak (tp 6–8%) beats shipped by +0.13pp, **inside the 0.334pp bias
envelope**. **Not one cell in the ladder beats matched-random**; best P = 0.560.

**Widening / holding longer.** The only monotone improvement is *hold longer*,
and it is grid-edge unbounded — at 72h the **content-free timer beats every
bracketed rule** (+2.890% vs +2.430%), while refusing 14 of 32 entries at the cap
and dropping return per position-day from 10.25 to 1.11. That is (hl)
denominator shrinkage in the exit direction; I19 forbids banking it.

**Multiplicity.** 367 cells scored through the same walker, BH at FDR 0.05
(`winners_docket.bh_survivors`): smallest p = **0.0478** against a rank-1
critical value of **0.000136**. **0 of 367 survive** — off by 351×. A time-shift
placebo shows the search alone manufactures ~+0.57pp on entries known to have no
edge.

**Mechanically unshippable anyway.** A partial scale-out has no primitive at any
of three broker layers (`paper_broker.close`, `ShadowBroker.close`,
`lighter_client.market_close` all take no size); `trade_id` would UPSERT leg 2
over leg 1 (the exact defect the predecessor already paid to fix);
`entry_ts.pop` destroys the runner's clock. And **the first partial leg sets
`integrity.two_writers = true`** — two ledger rows sharing `opened_at` are
byte-indistinguishable from a duplicate writer — which permanently blocks READY
and starts a false operator page every cycle.

---

## 5 · THE SUPPLY — two of three sources are structurally dead

| source | crypto supply /30d | starved by | verdict |
|---|---|---|---|
| **listing** | **0.0** (CI [0, 1.3]) — **86 days dry** | SUPPLY | crypto births Jun–Aug 2026 = **0**; last were CTR/RAIL 25-May. 5 of the last 7 births are zero-candle ghosts. |
| **surge** | 10.8–12.9 (bus + ledger agree) | nothing | **THESIS**-starved: 6h +0.312%/t=+1.19, 72h −1.355%/t=−2.31, and worse than random on the rank test. |
| **young** | **0.0** — **empty 66 days** | SUPPLY **and** SCREEN **and** FLOOR | 0 admissible today. |

**Loosening the surge bar is measured pure turnover**: two looser triggers give
**5,284/30d** and **8,848/30d** of supply at −0.038% and −0.050%/trade — a
400–800× supply increase collapsing onto the null (−0.058%). Do not ship it.

### The venue has no ANSEM, and the tail it does have cannot be harvested long

Venue-wide, 180d daily, 229 books, **31,744 book-days**: ≥+50%/72h **0.40%**,
≥+100% **0.05%**, **≥+300% ZERO**. Max observed anywhere **+186.8%**; max 24h
debut move across 162 debuts / 400 days **+129.1%**.

The tail that exists lives in the **crypto debut** cohort (≥+50% at 10.4% — a 25×
lift) — and **a long cannot take it**: mean *close* return is −2.66% at 24h,
−8.30% at 168h, and **"let winners run" (no TP, stop only) is strictly worse at
every hold**: 24h −3.82%/t=−4.02, 168h −7.14%/t=−9.47. The 90% that slide pay for
the tail several times over.

### The (lk) screen excludes exactly the cohort that carries the tail — declared, not changed

The screen tests `strategy_index == 2`. **The venue files every memecoin debut
under `strategy_index = 7`.** **ANSEM is listed on Lighter today and is screened
out of both surge and young.** Unblocking class 7 is nonetheless **REFUSED on
current evidence**: surge on class-7 reads **−0.840%/trade @6h** (negative at
every hold), and the debut cell is n=9 with top-1 (CAP) at **132% of the total**
and **−0.42%/trade ex-best** — (po) undecidable-by-tail. It motivates a
hypothesis; it arms nothing.

---

## 6 · THE NUMBER THAT SETTLES IT — UNDECIDABLE BY CEILING

A **perfect-hindsight** exit that sells at the exact 6h high, zero friction,
produces **+2.770%/trade**, of which **+1.80pp** is excess over a matched-random
null. The book's own published `mde80_pct` — the smallest effect it could detect
at 80% power — is **2.114%/trade**.

> **The entire distance between the shipped rule and omniscience is smaller than
> the smallest effect this book could ever prove.**

This is a **new undecidability class**, beside I17's slow clock and (po)'s fat
tail: not too few closes, not too fat a tail, but a **ceiling below the floor**.

Corroborating, on the only living source: at the reconstructed surge cell's own
effect size (+0.312%/trade, t=+1.19 on n=147), reaching t=2.0 needs
`n·(T/t)² = 415 closes` — **2.7–3.2 years** at 10.8–12.9 crypto surge
admissions/30d.

And a longer hold makes it worse: 19 closes instead of 33 in the same 29 days
raises `mde80` to ~2.79%, widening the unbridgeable gap from 0.31pp to **0.99pp**.
**A longer hold buys a bigger unprovable claim.**

---

## 7 · WHAT SHIPPED, AND WHAT DID NOT

### SHIPPED — the per-source census (I18 / (lv))
`extra.sources.{listing,surge,young}` now publishes a per-source funnel — a
`scan` liveness verdict first (I1), then one counter per gate stage — filled **by
the admission functions themselves**, so it cannot drift from the gate the way a
re-implemented census would ((hj)). A reader names the killing gate as the first
zero in gate order, without opening the file.

This is why it matters: two sources had been dead for **86 and 66 days** behind a
payload publishing `watching: 212` and nothing per source. `admitted: 0` was
byte-identical between "quiet" and "structurally impossible" — the condition that
hid 🎸 Barnesy's `extreme` sleeve for 8 days. Publish-only; admission is
byte-identical with `census=None`; 9 mutations verified RED
(`tests/autonomy/test_sniper_source_census.py`).

### REFUSED, each with the number
| refusal | the number |
|---|---|
| restore the scale-out ladder | Δ vs a bare timer = **$0.00** at 24/48/72h; 0 fires; **not implementable** (no partial primitive; sets `two_writers`) |
| restore the trail | 0-for-4 / −$33.11 on the predecessor; ex-mispriced **+0.059%, t=+0.04** here; arm needs +50% vs 0 of 32 reaching it |
| raise / lower the take-profit | 0 of 367 cells survive BH (0.0478 vs 0.000136); every TP <5% negative |
| hold longer | content-free timer **wins** at 72h; grid-edge unbounded; `mde80` 2.114→2.79 |
| raise the clip | I16 lower bound is **0.000**; allocation already at the 25% probe floor |
| loosen the surge bar | 400–800× supply at −0.04 to −0.05%/trade ≈ the null |
| unblock class 7 | surge −0.840%/trade; debut n=9 with top-1 = 132% |
| register the bracket as levers | I18's own refutation: reach with no measured direction to walk in. 0 of 367 cells give a direction. |

### ESCALATED — the I17 keep-or-retire call, for the OPERATOR
Published horizon verdict is already **`unreachable`** ("more of the same closes
cannot flip mean/t/halves"); I16 allocation claim **0.000**, already defunded to
the 25% probe floor; **85% of its ledger was taken under a policy it no longer
runs** (in-era n=5). The measurement recommends **RETIRE**. Retiring a book is an
operator decision in this fleet — every prior retirement ((if), (jh), (lo), (mr),
(nf), (pm), (po)) was — so it is escalated, not taken.

**Do not resolve this by lowering a bar or re-fitting a window.**

### THE REVIVAL TRIPWIRE — what would reopen the question
Free from the scout's own `ages_d`, and now visible in the census:
**≥2 crypto births/month for 2 consecutive months.** Firing it re-opens
**measurement** on the new wave's own listings — never a build off this study.
A second, independent trigger: a class-7 debut cohort reaching **n≥30** with a
positive lower bound, which would make the tail cell decidable for the first time.

---

## 8 · HONESTY LEDGER — nothing below may be quoted as arming evidence
- **Every sweep cell in this document.** The calibration gate FAILED; the bias
  envelope (0.334pp) is 3.2× the book's own mean.
- The surge thesis **+0.312%/trade, t=+1.19** (n=147) — sub-bar, reconstructed at
  1h against a 5-min detector, an upper bound on supply.
- The class-7 debut cell **+1.17%/trade** (n=9) — top-1 is 132% of the total.
- The volatility-selection result **P=0.009** is one test among several reported
  on n=33 and is not multiplicity-adjusted; it is a direction to investigate, not
  a finding to build on.
- The predecessor's **+$200 row** is a *modelled limit fill* with no exit
  slippage and no depth check, on an lbank memecoin at +400%. It is 96.9% of that
  book's lifetime P&L and the least verifiable row in it.
- **No random-entry null is constructible for the predecessor** — its pairs are
  delisted and LIGHTER-ONLY bars substituting another venue's tape. Its record is
  unfalsifiable as a matter of available data.
- The mexc ANSEM runner never closed in the retained ledger; the predecessor's
  +$206.38 excludes an unresolved position of unknown sign.
- `mde80` at a longer hold (2.79%) is the published 2.114% scaled by `1/√n`, not
  re-derived.

---

**Instrument:** `scripts/study_sniper_exit_shape_2026-08-20.py` (registered
`--selftest`; `--calibrate-only`, `--diagnostic-sweep`, `--null N`, `--synthetic`).
It refuses by construction — if someone later widens `SNIPER_CALIB_TOL_PP` to make
it speak, that is the defect, not the fix.
