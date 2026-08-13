# 📐 The Technician (`book-grimes-lshadow`) — The Art and Science of Technical Analysis, translated into a book

**Operator, 13-Aug:** *"Build me 4 bots for each of these books (please read
them and build for lighter exchange as usual) ... The Art and Science of
Technical Analysis — Adam Grimes. Best for building and testing a repeatable
price-action framework."*

This document is the reading: Grimes's framework, mapped to the mechanism his
book actually demands. Bot: `lighter_book_grimes_bot.py`, service
`book-grimes-shadow`, $1,000 shadow, zero keys. BOOKS cohort.

## Why the roster-with-a-gate is the honest translation

Grimes's central claim is NOT any setup — it is: *most price patterns don't
work; the only way to know is to test; trade only with a quantified edge.*
We took him at his word before writing the bot. TWELVE pre-declared variants
of his structural setups were measured on 500d of Lighter's own 4h tape
(`scripts/study_books_cohort_2026-08-13.py`): pullback ×6 (plain, MTF-
aligned, EMA50-depth, 2R/3R targets), failure test ×4 (20- and 55-bar
extremes), the daily-dislocation fade, the Keltner band fade. **None beat
random entries on the full window** — the best (MTF pullback 3R, +$84.07)
loses to random 24% of the time on per-trade mean; the failure test is
refuted outright (−$284, t=−2.2). Shipping a refuted setup is banned
doctrine. Shipping his TESTING DISCIPLINE is the book:

## The framework, as rules

| # | Grimes's lesson | The rule | Evidence status |
|---|---|---|---|
| 1 | The structural setups are the vocabulary. | The ROSTER: `pullback` (with-trend, daily-EMA20>50 aligned), `failtest` (spring/upthrust fade), `keltner` (band fade in a non-trending regime) live in the file as code — ONE owner each, used identically by the live scan and the replay. | Each setup's full-window and trailing record is measured (below); none is trusted on reputation. |
| 2 | *"If you can't quantify your edge, you don't have one."* | THE GATE: every 6h each setup is replayed over the trailing 120d of the venue's own tape through its own signal code (cap-2 sequential portfolio, 5bps/side — the study's exact method). A setup may ENTER only while its trailing record clears: n≥20, net>$0, t≥+0.5. Fail-CLOSED on a missing/stale scorecard. | The gate's bar is deliberately below the go-live bar — it allocates shadow clips, it promotes nothing; the go-live gate is unchanged and senior. |
| 3 | Publish the test, not the opinion. | `extra.scorecard` carries every setup's trailing {n, net, mean, t, open} every loop — `open: 0` is never byte-identical between "quiet" and "nothing currently tests" (I18/(lv)). | Observability; decides nothing. |
| 4 | Match the trade to the market regime. | The gate IS the regime switch, mechanically: when the tape changes, a setup's trailing record opens or closes it — no human in the loop, no hand-flipped env. | **Measured at birth, corrected in place per I12 ((mh))**: under the honest LAG-1 trend convention (day D gated on D−1's close — the first cut's unlagged map was a look-ahead in the replay AND a missing key live), keltner reads n=109, +$31.69, **t=0.49 — knife-edge BELOW the 0.5 bar → closed**; pullback −$36.25 → closed; failtest −$12.05 → closed. **The book is born trading NOTHING, by its own rule** — nothing currently tests, the public scorecard says so, and the gate re-decides every 6h. The first cut's "keltner OPEN at t=0.75" was partly the look-ahead's flattery; the correction is the book's own thesis enforcing itself on its author. |

### The I20 exclusion, stated plainly

`breakout` — Grimes's fourth structural setup — is DELIBERATELY absent from
the roster and selftest-pinned absent: channel breakouts on this universe
are 🧙 `book-schwager-lshadow`'s supply, and the same signal family on the
same coins at the same time is the same bet at a second row id (the (lz)
three-carry-books lesson). One supply, one owner.

### The config

| Gate | Value | Provenance |
|---|---|---|
| Roster | pullback / failtest / keltner | the book's ch. on structural trades; breakout excluded (I20) |
| Gate bar | n≥20, net>0, t≥+0.5 over 120d, retest 6h, scorecard TTL 24h fail-closed | pre-registered; below the go-live bar by design |
| Brackets | pullback sl1.5×ATR/tp3R/20 bars · failtest sl1.0×/tp2R/12 · keltner sl1.5×/tp2.25×ATR/20 | the study's declared parametrizations, unchanged |
| Universe / capacity | crypto ≥$1M top 18 · $80×2, one bet per coin across setups | the study's set and cap |

### Honest about the evidence (the (hm) clock)

The roster MECHANISM is unmeasured as a combination — no historical
scorecard series exists to backtest gate-switching, and that is declared,
not hidden. What is measured: every setup's record (above) and the gate's
arithmetic (selftest-pinned). Fresh 30-day clock from first publish. I17
declared: if no setup clears the gate for long stretches the book is
undecidable and that is a keep-or-retire call, not a reason to lower the
bar — the scorecard makes the starvation visible either way.

## What is deliberately NOT encoded

- **Any setup trading on reputation** — the whole point; the gate decides.
- **Grimes's "Anti" and multi-timeframe momentum divergence** — day-31
  roster candidates; each must pre-declare its parametrization and pass the
  same gate, never slip in tuned.
- **Discretionary trade management** (his ch. on active management) — the
  assistant directs no trades; brackets are fixed at entry.

## Birth checklist (the Barnesy parity list, applied)

- claim_writer at loop top + `:standby` key ((hp)/(ic)) ✅
- price-form (gr) telemetry + `side=` on every close (`PRICE_BOOKS`) ✅
- `snapshot_equity` from day one (`MTM_REQUIRED`) ✅
- census incl. `gated` (signal fired, roster closed) + public scorecard ✅
- registrations: dashboard, `SELFTEST_MODULES`, `ROW_ENTRY`, born-dark ✅
- deploy: `Dockerfile.grimes`, `MANUAL_IMAGES_OK` birth state, (lr)
  provision dispatch, activation gated on the row publishing ✅
