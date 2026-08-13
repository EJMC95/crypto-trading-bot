# 🧙 The Wizard (`book-schwager-lshadow`) — Market Wizards, translated into a book

**Operator, 13-Aug:** *"Build me 4 bots for each of these books (please read
them and build for lighter exchange as usual) ... Market Wizards — Jack
Schwager. Best for learning how genuinely successful traders think, though
it won't give you a perp strategy."*

The operator's own caveat is the design constraint: the book gives no perp
strategy, it gives the CONSENSUS of people who survived — cut losses, ride
winners, respect the trend, size small. This document maps that consensus to
mechanical rules and to the measurements behind each. Bot:
`lighter_book_schwager_bot.py`, service `book-schwager-shadow`, $1,000
shadow, zero keys. BOOKS cohort.

## Why a trail-riding trend book is the honest translation

The wizards disagree about everything except execution. Seykota: *"Cut
losses. Ride winners. Keep bets small."* Kovner: *"I decide where I'm wrong
before I get in."* Marcus: hold winners in trends. Dennis's students traded
channel breakouts. Measured on 500d of Lighter's own 4h tape
(`scripts/study_books_cohort_2026-08-13.py`), that consensus survives —
and one famous wizard rule does not.

## The interviews, as rules

| # | The wizards' lesson | The rule | Evidence status |
|---|---|---|---|
| 1 | *"Ride winners"* (Seykota) — no target. | The ONLY profit exit is a wide chandelier trail: 3.5×ATR14 from the close-basis high-water mark, ratcheting only (`update_trail` is monotone, selftest-pinned). No TP exists in the file. | **Measured as the whole edge**: trail 3.5× = **+$457.21 (t=1.88, halves +357.90/+99.31, beats random P=0.015)**; trail 2.5× on the SAME entries = −$29.88. The tight trail hands the winners back. 251 of 277 exits are the trail. |
| 2 | *"Cut losses"* (everyone). | Initial stop 2×ATR14, fixed at entry — Kovner's "where I'm wrong" point; superseded by the trail once it ratchets. | The study's declared parametrization; the exit study's standing lesson (tight stops REALISE the losses) is why the trail, not the stop, does the daily work. |
| 3 | *"Trade with the trend"* (Marcus, Kovner). | Entry: 4h Donchian-20 closing-channel breakout confirmed by EMA20>EMA50 (mirrored short). | **Measured**: don=20 beats don=55 (+$457 vs +$156); the DAILY variant measured 2.9 closes/30d — structurally undecidable (the 🌊 Tide Rider shape, I17) and REFUSED. |
| 4 | *"Never add to a loser"* — and the pyramid. | NO PYRAMID AT ALL, structurally: one position per coin, `_open_position` refuses a held coin, and no parameter exists to add units (selftest pins both). | **Measured and REFUTED**: pyramiding to 3 units turned +$457.21 into −$292.83 (trail 3.5) and −$1,103.57 (trail 2.5, t=−5.8). On this tape the pyramid buys chop exposure at the top of every leg. The book's most famous rule, refused with its own numbers. |
| 5 | *"Undertrade"* (Kovner). | $80 × 4 slots, fixed. No leverage stacking, no top-ups. | Fleet law + the simmed cap. |

### The config

| Gate | Value | Provenance |
|---|---|---|
| Entry | Donchian-20 close breakout + EMA20>50, 4h bars | grid winner; don=55 neighbour agrees in sign |
| Stop / trail | 2×ATR14 initial; 3.5×ATR chandelier, close-basis HWM | grid; 2.5× refuted |
| Max hold | 720h (30d) | the simmed recycle bound |
| Universe | crypto ≥$1M top 18 (scout, measured-list fallback, (hk) held union) | the study's set |
| Sides | BOTH | longs +$443.40 / shorts +$13.80 — shorts pay for themselves and are the only regime insurance a one-tape validation has (item 18) |

### Honest about the evidence (the (hm) clock)

t=1.88 is below the go-live t-bar; ~17 closes/30d puts 30 closes at ~54
days — gradeable **~mid-Oct** by the standard gate, the slowest clock of the
four new books and declared as such. h1 +$357.90 vs h2 +$99.31: the edge
decayed across the window and is stated, not smoothed. The brain grades
`long-trend` / `short-trend` separately. Env-only config, NO tuning lane;
levers are a day-31 decision.

## What is deliberately NOT encoded

- **The pyramid** — measured, refuted, structurally excluded (above).
- **Countertrend wizards** (Marty Schwartz's style) — a second signal
  family in one book makes the row ungradeable; 🧘 Douglas and 📐 Grimes
  carry the mean-reversion side of this tape.
- **Fundamental overlays** (Kovner's macro) — no mechanical residue on a
  crypto perp venue.
- **A daily variant** — undecidable at 2.9 closes/30d (I17); refused, not
  deferred.

## Birth checklist (the Barnesy parity list, applied)

- claim_writer at loop top + `:standby` key ((hp)/(ic)) ✅
- price-form (gr) telemetry + `side=` on every close (`PRICE_BOOKS`) ✅
- `snapshot_equity` from day one (`MTM_REQUIRED` — a ~112h-median-hold book
  is exactly I9's blind spot otherwise) ✅
- census + published per-position trail/hwm every loop ✅
- registrations: dashboard, `SELFTEST_MODULES`, `ROW_ENTRY`, born-dark ✅
- deploy: `Dockerfile.schwager`, `MANUAL_IMAGES_OK` birth state, (lr)
  provision dispatch, activation gated on the row publishing ✅
