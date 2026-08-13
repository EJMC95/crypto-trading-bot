# 🧘 The Zone (`book-douglas-lshadow`) — Trading in the Zone, translated into a book

**Operator, 13-Aug:** *"Build me 4 bots for each of these books (please read
them and build for lighter exchange as usual) ... Trading in the Zone — Mark
Douglas. Best for discipline, position sizing and avoiding revenge trading."*

This document is the reading: Douglas's execution doctrine, each element
mapped to a mechanical rule, each rule mapped to the measurement behind it.
Bot: `lighter_book_douglas_bot.py`, service `book-douglas-shadow`, $1,000
shadow, zero keys. BOOKS cohort (`book-<surname>-lshadow`, named for the
AUTHOR).

## Why a fade book is the honest translation

Douglas supplies no entries — his own words: *"an edge is nothing more than
an indication of a higher probability of one thing happening over another."*
The book is about EXECUTING an edge without emotion. So the honest build is:
find the edge this venue's tape actually supports (measured, before writing
the bot), then wrap it in Douglas's execution doctrine. Measured on 208d of
Lighter's own 1h tape (`scripts/study_books_cohort_2026-08-13.py`): chasing
extreme impulses — the emotional crowd's trade — loses **−$210.59 at
t=−2.81 (n=2,480)**; FADING extreme impulses (>2.5×ATR24) with a tight
asymmetric bracket earns **+$27.01, both halves positive (+$8.80/+$18.21),
beating 199 of 200 random-entry draws on both total and per-trade mean
(P=0.005)**. The disciplined trader is the casino taking the other side of
overreaction — Douglas's own casino analogy, executed literally.

## The doctrine, as rules

| # | Douglas's lesson | The rule | Evidence status |
|---|---|---|---|
| 1 | *"Predefine the risk of every trade."* | The bracket (stop 1.0×ATR, target 1.5×ATR, 12h expiry) is fixed AT ENTRY from the entry bar's ATR and never recomputed — `bracket_exit` reads stored fractions; no code path widens a stop. | **Measured**: the reverse bracket (sl 1.5/tp 1.0) loses −$96.68 to −$499.17 in every grid cell — the asymmetry IS load-bearing. |
| 2 | *"Anything can happen"* — think in probabilities. | Fade extreme 1h impulses (>2.5×ATR24), direction always OPPOSES the impulse (`impulse_signal`, selftest-pinned). | **Measured**: +$27.01, t=0.84, halves +8.80/+18.21, random benchmark P=0.005. At 1.5×ATR the fade is ~flat (−$27.60) — only the EXTREME tail pays. |
| 3 | *"The market doesn't know about your last trade"* — consistency. | Same clip every trade ($100×4). STRUCTURAL: `_open_position` has no streak/outcome/equity parameter (selftest pins the signature), so a martingale cannot be added silently. | **Measured, the refutation that shaped this book**: a naive revenge-guard (4h per-coin cooldown after a loss + 3-loss pause) flipped the book NEGATIVE: +$27.01 → −$11.32. Skipping entries after losses is itself emotional deviation. NOT shipped; reported. |
| 4 | *"Trade in sample sizes"* — the 20-trade exercise. | `extra.sample20` publishes the rolling 20-trade sample every loop: expectancy in R-multiples (return ÷ predefined stop), win rate REPORTED never a bar (I15). | Observability; decides nothing. |

### The config (all measured cells, none hand-picked)

| Gate | Value | Provenance |
|---|---|---|
| Impulse threshold | 2.5×ATR24, 1h bars | grid winner; 1.5× fade ~flat, continuation refuted at both |
| Bracket | sl 1.0×ATR / tp 1.5×ATR / 12h expiry | grid; neighbour (24h expiry) agrees in sign (+$22.75) |
| Universe | crypto, ≥$1M 24h vol, top 18 (`scout_universe`, falls back to the measured list) | the study's own set; (hk) held-coin union |
| Capacity | $100 × 4 slots | the simmed cap |
| Friction | 5bps/side, fills at mark | the Barnesy mark-sleeve declared model |

### Honest about the evidence (the (hm) clock)

t=0.84 is BELOW the go-live t-bar — this book exists to earn that evidence
in shadow at ~83 closes/30d. Fresh 30-day clock from first publish,
gradeable **~12-Sep at the earliest** by the standard gate (≥30 closes,
mean>0, t≥2.0, both halves, maxDD<15%, ≥30d). Regime caveat (item 18): one
tape, and its recent half is where the fade earns most — the brain grades
`long-impulse` / `short-impulse` separately. Env-only config, NO tuning lane
(the Garrett choice); levers are a day-31 decision.

## What is deliberately NOT encoded

Stated so no future session "finishes" it:
- **The revenge-guard cooldown** — measured HARMFUL (−$38.33 net effect).
  Douglas's actual rule is that outcomes must not alter execution, and the
  measurement agrees with the book against my first draft of it.
- **A daily-loss halt** — (hl): in shadow a halt skips the whole scan and
  removes the exits with it; the bracket + fixed clip bound the risk.
- **Stress/regime entry vetoes** — unsimmed gates on a simmed rule drift
  the book from its own evidence; the bracket is the risk control.
- **"Beliefs" / visualisation chapters** — no mechanical residue.

## Birth checklist (the Barnesy parity list, applied)

- claim_writer at loop top + `:standby` key ((hp)/(ic)) ✅
- price-form (gr) exit telemetry: `entry_price`/`exit_price` from position
  records + `side=` on every close (`test_exit_telemetry.PRICE_BOOKS`) ✅
- `snapshot_equity` from day one (`MTM_REQUIRED`) ✅
- census every loop (held/no_bars/quiet/signal + opened/capped/unpriceable) ✅
- registrations: dashboard `VARIANT_ONLY`/`LABELS`/`DESCRIPTIONS`/
  `OVERTRADE_LIMIT`, `SELFTEST_MODULES`, `ROW_ENTRY`, born-dark declaration ✅
- deploy: `Dockerfile.douglas`, `MANUAL_IMAGES_OK` birth state, the (lr)
  provision dispatch pattern (`books-provision.yml`), activation gated on
  the row publishing with a build stamp ✅
