# CEX-spot hedge — scope for a genuinely-profitable Yield Harvester

**Status: SCOPING (not built). 2026-07-10.**

## Why this exists
The two funding bots we built are the wrong ends of a trade-off:
- **Yield Harvester (delta-neutral, `perps-funding-carry`)** — models a hedge, so it
  keeps the full funding, but the hedge is *modelled*, not executed. Shadow-only.
- **Funding Farmer (directional, `perps-funding-lighter`)** — executes on Lighter, but
  with no hedge it carries price risk that the backtest shows ~offsets the funding
  (net break-even; see `scripts/backtest_directional_funding.py`).

The version that is *both* executable *and* profitable is the classic **delta-neutral
funding carry with a REAL spot hedge**: short the Lighter perp to collect funding, and
hedge the delta with a **spot long on a CEX** (spot pays no funding, so you keep the full
perp funding). Backtest evidence: at a ~20bps round-trip CEX-hedge cost this earned
**+$91/180d (+1.9% on deployed capital, ~3.8%/yr, market-neutral)** — real, if modest,
and concentrated in a few chronically-hot coins. (See memory `funding-carry-structural-edge-lighter`.)

## The structure
For a coin with **positive** funding (longs pay shorts — the common hot case):
```
   SHORT  Lighter perp   (collect funding, zero fee)
   LONG   same-coin spot  on a CEX   (delta hedge, no funding paid)
   =>  net delta ~0, P&L = funding collected - CEX spot round-trip fee - basis drift
```
For **negative** funding (shorts pay longs): LONG Lighter perp + SHORT spot on the CEX.
The short-spot leg needs **margin/borrow** on the CEX (borrow the coin to sell) — costlier
and riskier. **Recommendation: ship the positive-funding case FIRST** (long-spot hedge,
no borrow); add the negative-funding case only if the borrow economics work.

## What has to be built
1. **A CEX spot venue client** (`venues/cex_client.py`) mirroring the `VenueClient`
   interface: `funding_map`-equivalent not needed (funding comes from Lighter), but
   `orderbook(coin)`, `account_value()`, `positions()` (spot balances), `market_open`
   (spot buy/sell), `market_close`. This is the bulk of the work — a new exchange
   integration (REST + auth + symbol map + fee model + rate-limit governor).
2. **Dual-venue orchestration + leg reconciliation** (the safety core, same shape as the
   abandoned Lighter+HL design): open the perp leg and the spot leg; if the second leg
   fails, immediately UNWIND the first (never sit naked). On close, close both; on a
   stuck leg, alert + halt new entries. In shadow, model both legs against live books.
3. **Basis / rehedge loop**: as price moves, perp and spot notionals drift apart
   (delta re-opens). Periodically rebalance so |perp_notional - spot_notional| stays
   under a band. Track basis (perp mark - spot mid) — carry can be eroded by adverse
   basis convergence at entry/exit.
4. **Two-venue capital + safety**: separate collateral on Lighter and the CEX; the
   fleet `SafetyRails` (REAL_MONEY_KILL armed-by-default, per-bot notional cap,
   daily-loss halt) extended to gate BOTH venues; kill-check flattens both legs.
5. **Liquidity + coin filter**: reuse the Funding Farmer's spread/vol gates on the
   Lighter leg AND require the coin to be spot-listed + liquid on the CEX (many
   hot-funding Lighter perps — tokenized equities, brand-new listings — have **no CEX
   spot market at all**, so they're unhedgeable and must be excluded).

## CEX choice (user decision)
Needs: spot trading API, the hot-funding alts listed with real depth, non-US
jurisdiction (user is in **Australia**), reasonable taker fees.
- **Bybit** — good API, Australia-available, wide alt coverage, ~10bps taker. Strong default.
- **OKX** — good API + deep books, Australia-available, ~8–10bps taker.
- **Binance** — deepest, but AU access/entity questions; heavier compliance.
- **Kraken** — reputable/AU-friendly, thinner alt coverage (fewer hot-funding coins).
Recommend **Bybit or OKX**. The taker fee is the whole margin story: ~10bps/side = 20bps
round-trip is exactly the backtested break-even-plus case. A maker-rebate/limit-fill
version would materially improve it (add later).

## Effort & risk
- **Effort: LARGE** — a new CEX integration is the single biggest build in the fleet
  (auth, orders, balances, symbol map, fees, governor, reconciliation, rehedge). Estimate
  this as its own multi-session Gate, not a bolt-on.
- **Risks:** CEX custody/counterparty (funds sit on a CEX, not self-custody like Lighter);
  basis risk (perp-spot convergence at bad times); short-spot borrow cost/availability
  (negative-funding case); two-venue withdrawal friction + rebalancing capital; API
  reliability creating naked legs; regulatory/KYC. **Money edge is modest (~4%/yr),
  concentrated, and favourable-case in the backtest** — size and expectations accordingly.

## Recommended path
1. Shadow-first: build the CEX client read-only (books/balances), model the spot hedge
   leg in shadow against the live CEX book, and run the full delta-neutral loop with
   BOTH legs modelled — validate real captured carry vs the +$91/180d backtest before any
   money or keys.
2. Positive-funding case only, one CEX (Bybit/OKX), tiny caps, kill-switch armed by default.
3. Operator supplies CEX keys + Lighter keys + disarms + funds both venues — never me.

## Open decisions for the user
- Which CEX (Bybit / OKX / other)?
- Positive-funding-only to start, or also build the short-spot (borrow) negative case?
- Capital split across Lighter (perp margin) vs CEX (spot) — and total pilot size.
