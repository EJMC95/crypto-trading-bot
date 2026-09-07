# PER-BOOK EXECUTION COST — 2026-09-07 06:36

_Round trip via `funding_carry_bot.rt_cost_bps` (the fleet's declared one owner), walking each book at each book's own **deployed** clip. Calibrated against the spreads 🪁 kelly and 🧘 douglas record on their own fills — this refuses if it cannot reproduce them._

## The correction this makes to the Phase-2 baseline

The baseline charged every book the fleet-wide **17.49bps** mean and reported that it flipped 🌾 carry and 🔮 georgia negative. That reading does not survive two facts:

1. **17.49 is a MEAN over a right-skewed distribution.** Measured on 711 recorded spreads across 40 coins: the median full quoted spread runs **17.1bps in the thinnest volume band down to 2.5bps in the thickest** — a 6.8x span, fitting `spread ~ vol^-0.485` (the square-root liquidity law). One mean charged to every book overcharges the liquid ones and **undercharges the thin ones**, which is the dangerous direction.
2. **The books already pay.** Every living book's P&L is already net of execution by one of two mechanisms (below). Charging the fleet mean on top is a **double charge**, not a stress. 🌾 carry is the clearest case: its P&L is literally `accrued - fees`, so the baseline deducted a round trip it had already deducted.

**So the question worth asking is headroom, not cost.** Every book's `breakeven_cost_bps` is what it could pay before its edge is gone; `cost_now` is what it pays. The ratio is the answer.

## Per book

| book | fill basis | deployed clip | cost now (RT bps) | worst coin | break-even (RT bps) | headroom | coverage | verdict |
|---|---|---|---|---|---|---|---|---|
| `freqtrade-avo-maria-lshadow` | book_walked | $50 | **3.25** | ADA 8bps | 179.34 | **55.18x** | 100% | comfortable |
| `freqtrade-avo-maria-lighter` | real_fills | $236 | **4.96** | XCU 13bps | 235.98 | **47.58x** | 100% | comfortable |
| `pm-turnbull-lshadow` | unknown | $25 | **1.29** | PUMP 5bps | 28.62 | **22.18x** | 94% | comfortable |
| `lighter-ticket-taker-lshadow` | book_walked | $52 | **6.80** | CTR 64bps | 118.67 | **17.45x** | 95% | comfortable |
| `freqtrade-mum-lshadow` | book_walked | $50 | **7.22** | CC 15bps | 53.74 | **7.44x** | 99% | comfortable |
| `perps-funding-carry-lshadow` | book_walked | $300 | **4.19** | KAITO 12bps | 30.35 | **7.24x** | 60% | comfortable |
| `freqtrade-mum-lighter` | real_fills | $253 | **7.83** | CC 15bps | 43.36 | **5.54x** | 95% | comfortable |
| `freqtrade-georgia-lshadow` | book_walked | $50 | **5.36** | NEAR 11bps | 6.79 | **1.27x** | 100% | thin |
| `band-kelly-lshadow` | book_walked | $250 | **8.93** | USELESS 20bps | 0.00 | **—** | 100% | no edge to price |
| `book-bezos-lshadow` | book_walked | $100 | **3.81** | USELESS 20bps | 0.00 | **—** | 100% | no edge to price |
| `freqtrade-georgia-v3-lshadow` | book_walked | $50 | **5.22** | NEAR 11bps | 0.00 | **—** | 100% | no edge to price |
| `lighter-perp-sniper-lshadow` | book_walked | $20 | **6.62** | CC 15bps | 0.00 | **—** | 21% | no edge to price |
| `perps-funding-spread-lshadow` | book_walked | $18 | **5.20** | KAITO 12bps | 0.00 | **—** | 89% | no edge to price |
| `pm-albanese-lshadow` | unknown | $25 | **1.46** | PUMP 5bps | 0.00 | **—** | 98% | no edge to price |

`headroom` = break-even cost / cost now. **Below 1.0x the book does not survive its own execution**; 1-2x is thin. A losing book has no edge to erase, so its break-even is 0.00 and headroom reads `—` — cost is not what is wrong with it, and pricing it more precisely would not change that. Coverage is the share of the book's trades whose coin had a live book to price; a book priced on part of its basket says so rather than reporting the part as the whole.

## Fill basis — how each book already accounts for cost

| basis | books | what it means |
|---|---|---|
| **book_walked** | 10 — `band-kelly-lshadow`, `book-bezos-lshadow`, `freqtrade-avo-maria-lshadow`, `freqtrade-georgia-lshadow`, `freqtrade-georgia-v3-lshadow`, `freqtrade-mum-lshadow`, `lighter-perp-sniper-lshadow`, `lighter-ticket-taker-lshadow`, `perps-funding-carry-lshadow`, `perps-funding-spread-lshadow` | fills walk the LIVE order book (`ShadowBroker`), so the crossed spread is inside `entry_price`/`exit_price` and therefore already inside `pnl_abs` |
| **real_fills** | 2 — `freqtrade-avo-maria-lighter`, `freqtrade-mum-lighter` | a REAL-MONEY row — the ledger prices are actual exchange fills, so cost was PAID rather than modelled; the live-vs-twin execution gap is `impl_shortfall`'s job |
| **unknown** | 2 — `pm-albanese-lshadow`, `pm-turnbull-lshadow` | could not be derived — DECLARED, never guessed |

## Calibration

- `band-kelly-lshadow` — fetched median 5.96bps vs recorded 7.41bps (n=33 coins), delta 1.45, tol 8.0
- `book-bezos-lshadow` — fetched median 2.66bps vs recorded 2.72bps (n=15 coins), delta 0.06, tol 8.0
- `book-douglas-lshadow` — fetched median 4.99bps vs recorded 8.36bps (n=26 coins), delta 3.37, tol 8.0
- `book-hull-lshadow` — fetched median 1.37bps vs recorded 4.05bps (n=5 coins), delta 2.68, tol 8.0

_Only **4 of 14** living books record the venue's quoted spread on their own fills. That is the gap behind all of this: the fleet measures its own execution on an eighth of itself, so every other book's cost has to be inferred from the venue rather than read from its record (I14 — the record outranks the proxy, where a record exists)._
