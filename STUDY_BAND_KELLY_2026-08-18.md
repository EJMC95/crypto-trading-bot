# 🪁 band-kelly founding study — the mirror of the measured losers

**Date:** 2026-08-18 · **Script:** `scripts/study_band_kelly_2026-08-18.py`
(`--fetch` then offline; `--snap-deep` for the robustness pass) ·
**Operator ask:** *"Make a bot that does the exact opposite of all of the
major losing sequences and trends, flipping but also using every enhancement
and knowledge we have to ride an uptrend - expansion is the premise."*

## The construction

"Do the opposite of the losers" is a strategy only when the loser is a
MEASURED loser and the opposite is taken over the SAME windows the loser
would have traded: enter when the ghost enters, hold the other side, exit
when the ghost exits. At mark on a zero-fee venue that mirror's per-trade
return is the EXACT negation of the ghost's, so a loser ledger at t ≤ −2.0
is founding evidence at t ≥ +2.0 for the mirror. The study's job was to
find which of the fleet's losing families survive the four pre-declared
legs: **(1)** pooled-family |t| ≥ 2.0 and n ≥ 30 (era-scoped, quarantined
rows out, entry families pooled across ALL exits per I7 — a `_sl` bucket is
a loser by construction and its inverse is not gradeable by symmetry
either); **(2)** forward signal computable from code this repo already
ships (the ghost's own module, never a re-implementation); **(3)** supply
unowned forward (I20 — inverting a LIVING book would make the fleet hold A
and anti-A at once); **(4)** where a candle replay is possible, the mirror
must beat a duration-matched random-short benchmark and survive a
protective stop. Verdict logic was written into the script header before
any number existed.

## VERDICTS

| family | ghost (era-clean, pooled) | mirror | verdict |
|---|---|---|---|
| **snapfade** — 🧲 Snap Back's whole book, inverted (retired 4-Aug (jh)) | n=189, −0.250%/t, t=−2.82 | **+0.250%/t, t=+2.82; crypto-only n=65, +0.605%/t, t=+5.71, both halves & both sides positive** | **SHIP** — the v1 roster, alone |
| brkfade — MomoBreakout 4h Donchian longs, inverted (breakout-4h (mr) + dad (nf), n=40 ledger) | ledger n=40 ≈ −2.0%/t | replay: every cell NEGATIVE (−$81..−$159), maxDD ~23%, random-short beats it at P=0.78–0.81 | **REFUSED — the calibration control killed it** (below) |
| dipfade — the taker's dip lens, inverted (vetoed, untraded) | n=13, −1.162%/t, t=−2.66 | +1.162%/t, t=+2.66 — **n=13 < 30** | REFUSED at the I16 floor; **day-31 candidate** as the sample accrues |
| impulse-continuation, inverted | n=2919, −$248.65, t=−3.05 | the fade of extreme impulses | **already minted — 🧘 book-douglas owns it (I20)**; the largest measured loser's inversion exists and is not re-taken |
| pm-gillard `long-disloc`, inverted | n=74, −0.315%/t, t=−2.45 | +0.315%/t, t=+2.45 | forward-infeasible (parliament lens internals) — but an **independent second-ledger corroboration of the dislocation-momentum thesis** |
| pm-abbott `long-burst` · pm-rudd · pm-morrison · intraday-15m families | t between −0.02 and −2.26, n mostly < 30 | — | report-only: below bar and/or forward-infeasible |

## Why brkfade died — the calibration control did its job ((nt))

The harness replayed the REAL retired class (`lighter_family_bot.
MomoBreakout.signals`, tide gate included) over 578 days × 17 coins. The
ghost itself — the thing whose 40-close ledger reads −2.0%/trade — does
**not** lose over the full tape: **+$126.44, t=+0.90, top-3 trades = 103%
of the total, h2 negative** (the Schwager tail shape). The retired books'
losses were their 30-day windows, not a property of the entry family — the
(mr)/(nf) retirements stand on their own ledgers, but the family's inverse
is a short position against a fat right tail: mirror-pure −$158.60
(worst single trade −$52.98), every stop cell negative, maxDD 22.9–23.6%
vs the 15% bar, and duration-matched random shorts beat every cell
(P(t≥mirror)=0.78). **Flipping a loser is only evidence when the loss
itself is statistically established at the family level — a 21-close
ledger's inverse is a 21-close bet.** Refusal recorded with its numbers,
per the standing only-growth rule.

## The shipped claim, attacked from every angle (`--snap-deep`)

🧲 Snap Back faded dislocations of Lighter's mid vs its own `index_price`
(long when cheap, short when rich) and lost with the fleet's strongest
loser evidence: t=−2.97 at retirement, 100% of its era exits `converged` —
the dislocations it faded kept going. The mirror rides them instead:
**long when rich, short when cheap**, entering when the ghost enters and
exiting when the ghost exits (converged / ghost-stop / 2h max-hold).

* **Pooled mirror** (n=189, 13-Jul→4-Aug): +$4.85 at the ghost's own $10
  clips, +0.250%/t, t=+2.82, **cluster-robust t=+2.84 (n_eff=191** — these
  closes do not batch, (kw)), h1/h2 +$2.75/+$2.10, top-3 |trade| share 36%.
* **Post-(fz) era** (the adaptive-gate config the forward ghost runs,
  n=174): +0.258%/t, t=+2.76; both sides positive (my long side +0.152%/t
  t=+1.45 n=123; my short side +0.512%/t t=+2.68 n=51).
* **Crypto-only** ((lk) screen — the shipped book's population): **n=65,
  +0.605%/t, t=+5.71, h1/h2 +$2.39/+$1.54, win 82%** (win rate REPORTED,
  never a bar — I15). The screen *concentrates* the edge: the ghost lost
  hardest on crypto.
* **Ex-best-coin**: dropping KAITO entirely (39 of 65) leaves n=26,
  +0.684%/t, **t=+5.08** — the claim is not one coin.
* **Both mirror sides independently positive on crypto**: ghost-short
  mirror = my LONGS (premium-rich ridden UP): +0.464%/t, t=+4.72, n=39.
  Ghost-long mirror = my SHORTS (discount ridden DOWN): +0.816%/t,
  t=+3.77, n=26. The "fly high" arm is the LARGER side — riding premium
  momentum up is the book's majority trade; the glide down is its minority.
* **The claim is alpha, not beta ((hm) in mirror form)**: median hold
  0.09h; the tape's −32.9%/438d drift contributes ±0.0003% per hold —
  **861× below** the measured mean. A random-entry benchmark at this
  horizon is the drift term, and the drift term is nothing.

## Declared limits — named, not absorbed

1. **The replay leg is impossible for this family**: no historical
   index-vs-mark tape exists, so the founding evidence is the exact
   negation of the ghost's own 23-day ledger, and the forward book is
   graded on ITS OWN ledger from close #1 (I14 — the record decides).
   Fresh 30-day clock; nothing inherited.
2. **Fill-model deviation**: the ghost filled $10 clips at book-walked
   VWAPs behind a 30 bps slip gate; the mirror trades $80 clips through
   the same `book_view` and the same gate, crossing the spread the other
   way. Larger clips meet more slip; the census counts slip-refused
   entries so the deviation is visible, not assumed.
3. **One venue regime** (item 18): the ghost's ledger is 23 days of one
   tape. The sided/halves/ex-coin splits above are the strongest
   robustness available at this n; the forward record is the answer.
4. **No regime gate shipped**: at a 5-minute median hold a 4h EMA gate is
   unmeasured and horizon-mismatched; the measured expression of "ride the
   uptrend" is the long side itself (t=+4.72). Shipping an unmeasured
   restrictive gate would be I19 backwards.
5. **Day-31 candidates, declared**: dipfade (n=13 → 30 as the taker's
   vetoed lens keeps grading), and a docket re-derive — any NEW family the
   losers' docket establishes at |t| ≥ 2, n ≥ 30 with an unowned,
   computable forward signal is a candidate sleeve behind the same four
   legs. Expansion is the premise; the legs are the price of admission.
