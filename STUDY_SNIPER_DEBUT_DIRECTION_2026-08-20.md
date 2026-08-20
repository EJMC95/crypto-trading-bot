# 🎯 THE SNIPER'S SUPPLY WAS NEVER DEAD — IT WAS SCREENED OUT
### 2026-08-20 (sg) · operator: *"bring the sniper back to life and make it do its intended job"* / *"don't continue if it's going to be negative, restrictive and choking of the bot"*

---

## THE HEADLINE

`(qi)` and `(sf)` both reported the sniper's debut supply as **dead — "ZERO
crypto births for 86 days"**. That is true of `strategy_index == 2` and **false
of the cohort this book trades.**

**Venue-priced births have not stopped in any month measured: 1.67–2.00 per
30 days.** CAP (Jun), ANSEM (Jul), CASHCAT (Aug). Every one of them is
`strategy_index 7`, and every one was refused by a screen that asks
`is_crypto`. The young source published `admitted: 0` for **66 consecutive
days** while its own cohort arrived on schedule.

**Corrected in place per I12.** The supply figure was not wrong arithmetic — it
was the wrong question, and it sent two prior passes looking for a fix in the
exit rule.

---

## 1 · WHAT THE SCREEN WAS ACTUALLY DOING

`(lk)` put ONE instrument-class screen on **both** the surge and young sources.
Its evidence was almost entirely surge's:

| source | (lk)'s evidence for screening it |
|---|---|
| surge | non-crypto **−$5.01 over 13 closes** |
| **young** | non-crypto **−$1.19 over TWO closes** |

The young leg rested on **n=2**.

And the question it asks is `strategy_index == 2`. The venue files **crypto-native
memecoin debuts under class 7** — the same grab-bag holding tokenised pre-IPO
equity (ANTHROPIC, OPENAI, SPCX), listed equities it happens to file oddly
(MRNA, ADI), and a bond yield (US10Y). Class 7 has **12 members** and they do
not share an answer.

**Live supply on the day this shipped — the young cohort was 7 books:**

| book | age | 24h vol | verdict under the old screen |
|---|---|---|---|
| AXTI, WDC, SOXS | 6.6d | **$0.000M** | refused (class 5) — and zero-volume ghosts anyway |
| KORU, KIOXIA | 6.6d | **$0.000M** | refused (class 6) — ghosts |
| **CASHCAT** | 13.6d | **$0.453M** | **refused (class 7)** |
| **UNITREE** | 14.6d | **$0.840M** | refused (class 7) |

**The only two books with real turnover were the only two the screen refused.**
The source was not quiet. It was structurally unable to admit anything.

---

## 2 · THE AXIS THE (lk) ARGUMENT WAS REALLY MAKING

(lk)'s own words: *"a surge-long on USDKRW/BOTZ is a timer-held drift bet on an
instrument whose venue volume surge is its UNDERLYING's market event, **already
priced where the underlying trades**"*.

That turns on whether a **deep primary market exists elsewhere** — not on
`strategy_index`. A crypto-native token's only market IS this book, so its
debut is genuine price discovery. A tokenised equity is a wrapper around a price
set somewhere far deeper.

`fleet_bus.venue_priced` measures that axis directly. **And the half of (lk) it
keeps is now far better evidenced than the half it replaces:**

| cell (young window, shipped bracket) | n | mean %/trade | t |
|---|---|---|---|
| SHORT **externally-priced**, 6h | 108 | **−0.457%** | **−2.38** |
| SHORT externally-priced, 72h | 100 | −0.760% | −1.16 |
| SHORT externally-priced, 168h | 97 | −0.968% | −1.08 |

**t=−2.38 is the only significant cell in the entire study**, and it says
excluding externally-priced instruments is right. The screen was half-correct;
the correction keeps the correct half and drops the part that rested on n=2.

---

## 3 · THE DIRECTION QUESTION — MEASURED, AND REFUSED

Four independent prior measurements say debuts bleed ((qi) day-7 −13.4%;
(qi) wait-then-short +6.23%/episode; (sf) supply census −8.30% at 168h; this
study's debut-bar cells). The young-window cells agree:

| cell (venue-priced) | 6h | 24h | 72h | 168h |
|---|---|---|---|---|
| **LONG** mean %/t | −0.174 | −0.012 | −0.276 | −0.622 |
| **SHORT** mean %/t | +0.041 | +0.147 | **+1.369** | **+1.513** |
| SHORT t / cluster-t | 0.12 | 0.21 | 1.33 / 0.96 | 1.31 / 0.98 |
| SHORT top-1 share | 225% | 125% | **16%** | **15%** |

The 72h/168h short cells are the best-behaved anything in this investigation:
both halves positive, concentration 15–16%, and the edge **survives dropping the
best trade** (ex-top1 +1.160 / +1.304, i.e. *higher* than the mean).

**AND THE (hm) NULL REFUTES IT ANYWAY.** Random entry minutes inside the same
21-day window, on the same books, same direction, same bracket:

| hold | observed | null p50 | null p90 | **P(random ≥ observed)** |
|---|---|---|---|---|
| 72h | +1.369% | **+1.687%** | +3.361% | **0.573** |
| 168h | +1.513% | **+1.856%** | +4.016% | **0.577** |

**A random minute beats the sniper's entry.** The +1.4%/+1.5% is the *drift of
shorting young venue-priced books for 3–7 days*; the entry timing contributes
nothing, and slightly less than nothing. This is `(sf)`'s finding — the entry
carries no directional information — reproduced on the young cohort specifically
and in both directions.

**The (hl) control agrees:** at 168h the content-free timer (+2.430%) beats the
bracketed rule (+1.513%). The bracket is not earning either.

**So: no direction flip, and no longer hold.** Recorded here with the numbers so
no future session re-proposes them from the +1.5% alone.

---

## 4 · THE VOLUME FLOOR — REFUSED, AND THE REASON IS THE MODEL'S LIMIT

| floor | n | mean %/trade | t |
|---|---|---|---|
| $0.00M | 302 | **−0.451%** | −1.56 |
| $0.05M | 212 | −0.179% | −0.55 |
| **$0.10M** | 175 | **−0.049%** | −0.16 |
| **$0.25M (shipped)** | 115 | −0.174% | −0.52 |
| $0.50M | 80 | −0.481% | −1.14 |

Lowering the floor to $0.10M looks like a free 1.5× in supply. **It is not, and
the reason is a limit of the instrument rather than a property of the tape:** the
harness's slippage tiers are a step function at **$0.1M** (17.49bps below,
2.52bps above), so a $0.11M book is charged the same as a $10M one. The extra
books the lower floor admits sit exactly in the band the model cannot price.
At (qq)'s measured thin-book cost the round trip on those books is ~30–95bps —
**larger than the 0.125pp apparent gain.** The floor stays at $0.25M.

Dropping it to zero is separately refused: −0.451%/trade, because that is where
the zero-volume ghosts live.

---

## 5 · WHAT SHIPPED

**The young source's screen moves from `is_crypto` to `venue_priced`.**
Measured effect on the live gate, run end-to-end against the venue:

```
OLD  is_crypto      scanned=210  age_ok=8  fresh=8  class_ok=0  vol_ok=0  -> []
NEW  venue_priced   scanned=210  age_ok=8  fresh=8  class_ok=2  vol_ok=1  -> ['CASHCAT']
```

The surge source is **untouched** — its evidence is real and `(sf)` measured
class-7 surge at −0.840%/trade, negative at every hold.

**THE EXPECTANCY PRICE, STATED (I19).** The admitted cell measures
**−0.174%/trade at t=−0.52** on the shipped 6h bracket — indistinguishable from
zero, and on a $20 clip that is **−3.5 cents per trade**, roughly **−$0.17 a
month** at the measured birth rate. **This is bought as DECIDABILITY, not as
edge, and the entry says so:** a source at zero admissions produces zero
evidence and can never be graded or retired on its own record. I17 makes the
same argument for capital ("a book cannot earn evidence with no capital"); this
is the supply form of it.

**Also shipped:** `fleet_bus.NONCRYPTO_BASES` had drifted by **8 of 101** active
non-crypto books (AXTI, CASHCAT, KIOXIA, KORU, MRNA, SOXS, US10Y, WDC — all
recent listings), so with a dark scout every crypto-screened book in the fleet
failed OPEN on them. The same 8 were missing from 🎫 the Taker's local
`TRADFI_BASES`, which its own parity test caught the moment fleet_bus was fixed.
`scripts/audit_noncrypto_fallback.py` now measures that drift against the venue
in both directions, and **fails rather than passing when it cannot reach the
venue** — a guard that no-ops offline would report clean.

---

## 6 · HONESTY LEDGER
- Every direction cell is **hypothesis-grade and refuted by its own null**
  (P=0.573/0.577). Nothing here arms a direction change.
- The admitted long cell is **negative** (−0.174%, t=−0.52). It is shipped for
  decidability, not expectancy, and is not a claim of edge.
- The `venue_priced` class-7 split is a **declared list**, not a venue field.
  It is biased to admit an unknown class-7 name, because starving the debut
  source is the worse error — and that bias is pinned by a test.
- **Survivorship:** `orderBookDetails` lists only books alive today, so a book
  born and delisted inside the window is invisible. Every number here is
  optimistic by an unmeasured amount, worst on the thin debut cohort.
- 1h resolution against a 60s decision loop; per `(sf)` that gap is real and
  one-sided. **Rank and direction are what this study is for, never levels.**
- `created_at` is epoch-0 on MRNA and US10Y; both are excluded rather than
  coerced.

**Instrument:** `scripts/study_sniper_debut_direction_2026-08-20.py`
(registered `--selftest`; reuses the `(sf)` harness's exit walker, slippage
tiers and scorer rather than growing a second copy of the rule).
