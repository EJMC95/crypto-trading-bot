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
