# Non-crypto regime study — the funding-rank factor on Lighter's non-crypto books (2026-07-23)

The fleet's whole 438d crypto tape is one falling-BTC regime, so every directional
lens is graded in one weather. This tests the **on-venue path to a different
regime**: Counterweight's VALIDATED, market-neutral funding-rank factor (long the
books that pay / short the books that charge) applied to Lighter's **non-crypto**
books. Market-neutral → **no regime beta to launder**, so "both halves positive"
keeps its meaning (a long-only lens on rising equities would pass by construction —
that trap is deliberately avoided).

Runs (Lighter's own API, in doctrine):
- `scripts/backtest_xsect_funding_noncrypto.py --days 150 --refresh` (🏹 TAMERLANE)
- `scripts/backtest_xsect_funding_merged.py --days 150` (crypto vs non-crypto vs merged)

## The three arms (142d shared window, factor 48/5/48 = the merged decision cell)

| arm | full | h1 | h2 | maxDD | pass rate |
|---|---|---|---|---|---|
| crypto-only (live ⚖️ Counterweight) | +8.2% | +0.2% | +1.4% | 13.2% | 10/12 |
| **non-crypto only** | **+17.9%** | +15.8% | **+11.7%** | **7.6%** | 4/12 |
| **MERGED (51 books)** | **+18.5%** | +11.9% | +3.1% | **9.0%** | 4/12 |

## What passes and what doesn't (pre-registered decision rule)

- **D7 — diversification: PASS.** Merging non-crypto into the factor universe lifts
  the return from **+8.2% → +18.5%** (more than double) AND cuts drawdown from
  **13.2% → 9.0%** vs crypto-only, at the same cell. Merged beats crypto-only on
  full AND h2. This is the textbook diversification payoff — uncorrelated books
  smooth the factor. **The non-crypto edge is real and diversifying.**
- **D5 — cost: cost-sensitive.** Green at 5bps (+18.5%) and 10bps (+14.5%), but h2
  goes **negative at 15bps**. Like the funding arm, it lives on execution quality.
- **D6 — durability: FAIL.** Quarterly on the chosen cell: q1 +5.3, q2 +11.4,
  **q3 −7.4**, q4 +3.8 — the worst quarter (−7.4%) breaches the −5% bar. Not a
  monotone decay (it's not dying), but there IS a losing quarter. So this is **not
  a clean pass of the full rule.**

## Friction is heterogeneous — the tradeable universe is the DEEP books only

Median half-spread 2.91bps (where the factor earns **+13%**), but 6/26 books are
far wider: **URA 102bps, ASML 27bps**, XPD/IWM ~8bps, AMD 5.3, AMZN 5.1. Those
illiquid books drag the result and belong excluded or liquidity-weighted. The
deep core is genuinely tight: **XAU 0.3bps, WTI 0.5bps, SNDK 0.9bps, SPY 1.1bps,
AAPL 1.0bps**.

## Honest verdict + disposition

**Yes — the non-crypto books show real, diversifying, market-neutral numbers**
(D7 pass: the merge more than doubles return and cuts drawdown). But the factor
does **not cleanly pass the full pre-registered rule** — D6 (worst quarter −7.4%)
and D5 (dies at 15bps) are real caveats. So this is a **shadow-validate candidate,
not a ship-it**: stand it up as a $0-real-money shadow book on the deep-liquidity
non-crypto core (exclude the >5bps tail) and let it earn its own forward track
record, with eyes on the durability wobble.

**Concrete refinement worth doing next:** re-run with a liquidity filter (drop
books wider than ~5bps). The median-spread number was already +13% vs +11.2% flat,
and the illiquid tail is a plausible driver of the −7.4% quarter — filtering it
may turn the mixed verdict into a clean one. That's the highest-value follow-up,
and it's pure research (no real money).

Standing this up as a shadow book is an operator decision (a new book on the
fleet) — surfaced, not taken.

## REFINEMENT (2026-07-23): the liquidity filter did NOT clean it up — it HUMBLED the headline

Added `--max-spread-bps` and re-ran dropping the 6 illiquid books (URA 101.8,
ASML 26.8, XPD 7.9, IWM 7.9, AMD 5.3, AMZN 5.1). The hypothesis was that the
illiquid tail drove the −7.4% quarter. **It did not — and the result cuts the
other way:**

| universe | shipped-config full | h2 | dies at |
|---|---|---|---|
| full 26 books (flat 5bps) | +11.2% | +2.9% | 15bps |
| **deep 20 books (≤5bps)** | **+7.6%** | +1.3% | **10bps** |

Dropping the wide books LOWERED the return (+11.2% → +7.6%) and made it MORE
cost-sensitive (now negative at 10bps, not 15). Why: the flat-5bps assumption was
**under-charging** the illiquid books (URA was charged 5bps when it really costs
102bps), so the +11.2% headline **credited alpha the fleet could never actually
capture at those spreads.** The deep-universe +7.6% (fairly charged, since all
remaining books are ≤5bps; +9.9% at the median 2.26bps) is the **honest tradeable
number** — and it is thinner and more fragile than the first read implied.

**Corrected verdict:** the non-crypto factor IS a real, diversifying, both-halves-
positive market-neutral edge — but on the honestly-tradeable universe it is
**modest (+7.6% to +9.9%) and cost-sensitive (dies ~10bps)**, not the +11–18%
the flat-slip headline suggested. The −7.4% quarter is a genuine factor drawdown,
not a friction artifact. Still a **shadow-validate candidate** — but stood up on
the honest numbers, with no expectation it doubles the crypto arm. The real
next step before any shadow go-live is a **per-book-spread backtest** (charge each
book its measured half-spread, not a flat 5bps) so the number is trustworthy end
to end.

## PER-BOOK COST — the honest end-to-end number (2026-07-23)

Added `--per-book-slip`: `simulate()` now accepts a `{book: half_spread}` dict
(backward-compatible — a scalar behaves exactly as before; the flat-5bps run still
reproduces +11.2% to the decimal). Each leg is charged its OWN measured spread.

| universe · cost | shipped-config full | h2 | maxDD | pass |
|---|---|---|---|---|
| full 26 · flat 5bps | +11.2% | +2.9% | 7.6% | 4/12 — **inflated** (illiquid tail billed 5bps) |
| deep 20 · flat 5bps | +7.6% | +1.3% | 8.6% | 5/12 — **deflated** (deep books over-billed at 5) |
| full 26 · per-book | +8.7% | +1.8% | 9.0% | 4/12 — honest; illiquid tail correctly drags |
| **deep 20 · per-book** | **+10.1%** | **+2.5%** | **8.5%** | **5/12 — THE HONEST TRADEABLE NUMBER** |

**Final verdict.** Charging each book its real spread RECOVERS most of the edge the
flat-5bps filter had wrongly discarded — because flat-5bps was *over*-charging the
deep core (real median 2.26bps). The honest, trustworthy result on the tradeable
deep-liquidity universe is **+10.1% / 142d, both halves positive (h2 +2.5%),
maxDD 8.5%, market-neutral** — a genuine diversifying edge, comparable to the
crypto arm (+13.6%) at LOWER drawdown (8.5% vs 10.1%) and on an uncorrelated
universe. This is a solid **shadow-validate candidate** at an honest number.

Remaining before shadow go-live: re-check the D6 quarterly durability under the
per-book cost on the deep universe (the −7.4% quarter was a flat-slip/full-universe
figure), and — for a fully fair head-to-head — re-run the merged crypto-vs-non-crypto
with per-book slip on BOTH arms (the +13.6% crypto number here is still flat-5bps).
Both are pure research. Standing up the book is an operator decision — surfaced, not taken.
