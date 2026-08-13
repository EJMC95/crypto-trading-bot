# 🧮 The Professor (`book-hull-lshadow`) — Options, Futures, and Other Derivatives, translated into a book

**Operator, 13-Aug:** *"Build me 4 bots for each of these books (please read
them and build for lighter exchange as usual) ... Options, Futures, and
Other Derivatives — John Hull. Best technical reference for futures,
leverage, margin and derivatives mechanics."*

This document is the reading: Hull's futures-pricing machinery, each piece
mapped to a mechanical rule, each rule to its measurement. Bot:
`lighter_book_hull_bot.py`, service `book-hull-shadow`, $1,000 shadow, zero
keys. BOOKS cohort.

## Why a cost-of-carry book is the honest translation

Hull's textbook is the arithmetic of how derivatives are TIED to their
underlyings. On a perp venue, the funding rate IS the financing rate of his
cost-of-carry model (ch. 5): a perp persistently paying above fair carry is
mispriced, and the textbook trade is cash-and-carry — take the receiving
side, delta-neutral, collect the carry. That is also this fleet's best-
evidenced trade class (funding +$72.89 over 297 closes vs directional
−$9.21 over 867, the 1-Aug allocation census). What Hull adds beyond the
existing carry books is WHERE and HOW: the no-arbitrage cost band, basis-
noise tolerance, and the convergence veto.

## The textbook, as rules

| # | Hull's machinery | The rule | Evidence status |
|---|---|---|---|
| 1 | Cost of carry (ch. 5): funding ties the perp to its index. | Delta-neutral MODELLED funding receiver: P&L = accrued − fees, NO price term — `position_pnl` takes no mark (structural, the 🏦 Rich Dad pin, selftest-enforced). | The carry thesis — the fleet's validated shape. |
| 2 | The no-arbitrage band (ch. 5): transaction costs put a band around fair value; inside it there is no trade. | PAYBACK VELOCITY floor: funding must repay the declared 30bps RT within 336h ⇒ effective floor **~7.82% TRUE apr**, DERIVED from the declared friction, not hand-picked. Band ceiling **20%** (half-open) — everything above is the carry cohort's supply. | **Measured**: the shipped band cell earns +$4.92 (below, #3); the floor arithmetic is selftest-pinned. |
| 3 | Basis risk (ch. 3): short-horizon basis oscillation is noise around carry, not a signal to unwind. | 24h persistence before entry AND 24h flip grace before a liability sale — a paying spell shorter than a day is basis noise. | **Measured as the difference between this book existing and not**: grace 1h (the parent cohort's flip exit) in this band = **−$16.84, t=−6.65, 136/158 exits paying the RT on a sign wobble**. Persist 24h/grace 24h = **n=45, +$4.92, t=+3.27, halves +$0.75/+$4.17, random-timing control P=0.000**. The grid is a plateau: every persist≥24h × grace≥6h × floor {7.8%,10%} cell positive; every grace=1h cell negative. |
| 4 | Convergence (ch. 5): entering against the basis pays convergence away. | Adverse-basis veto: refuse an entry whose mark-vs-index premium opposes it by >10bps (short below fair value / long above it). Restrict-only, fail-OPEN on a dark feed. | UNMEASURED (no historical premium series exists) and declared as such (I19): the measured baseline above is the floor; the veto can only restrict it further. |
| 5 | Margin prudence (ch. 2). | $80 × 4 fixed; no leverage stacking. | Fleet law. |

## The supply, named (I20) — the tiling completed

| Tier (24h vol) | Book | apr gate |
|---|---|---|
| [$0.1M, $2M) | 🛢️ Garrett | ≥5% TRUE |
| **[$2M, $10M)** | **🧮 Hull (this book)** | **[7.8%, 20%) TRUE** |
| [$10M, ∞) | 💸 Farmer | ≥5% TRUE |
| ≥20% TRUE at ≥$2M | 🌾 carry / 🎸 Barnesy / 🏦 Rich Dad | the carry cohort's cell — the 20% CEILING hands it off, half-open |

**Zero living rivals admit this cell** (both edges published in `extra.caps`
— floor AND ceiling, apr AND volume, per the (gl) lesson that an unpublished
ceiling manufactures phantom rivals). Live occupancy at authoring: LIT, ZEC,
PUMP — the venue's ~10.5% base-rate coins in the mid tier; band supply was
present in ~100% of the 219d of measured hours (vs 6.6% for the carry cell).
The adjacent measured claim: the thin-tier study's BAND2 cell ([2M,10M) @
gate 0.05) independently measured +$1.76/30d — same tier, weaker gate,
consistent sign. The Farmer's xp lane carries a `min-vol-2e6` judge
candidate (~4-Sep verdict); if the judge ever promotes it, the Farmer's band
would overlap this one and that collision is NAMED here in advance — the
judge's paired bar, not this book, decides that day.

### Honest about the evidence (the (hm) clock)

219d of Lighter's own settled funding series, 18-coin liquid universe
(survivorship declared: historical tier membership is not reconstructable).
Tier-restricted to today's [2M,10M) members: n=30, +$4.17, t=+2.76, halves
+$0.55/+$3.62, **~4 closes/30d — the I17 clock is SLOW (30 closes in ~5-7
months) and declared at birth**, comparable to its cohort sibling Rich Dad's
supply reality. Unit economics are modest and stated: ~$0.11/trade mean on
$80 clips — a cash-flow book, not a growth rocket. Fresh 30-day clock from
first publish. Env-only config, NO tuning lane; levers are a day-31
decision.

## The payback arithmetic, shown

Hourly income on notional N at TRUE apr A = `N·A/8760`; round trip cost =
`0.003·N`. Payback hours `P(A) = 26.28/A`:

| TRUE apr | payback | verdict at the 336h bar |
|---|---|---|
| 5.0% | 525.6h | refused — inside the cost band (Garrett's gate, not ours) |
| 7.82% | 336.0h | the floor, exactly — the band's edge is the friction's edge |
| 10.5% (venue base rate) | 250.3h | admitted — the cell's daily bread |
| 20.0% | 131.4h | NOT ours — the ceiling hands it to the carry cohort (half-open) |

A copy of this arithmetic is pinned in the bot's selftest so the effective
floor cannot drift from this table.

## What is deliberately NOT encoded

- **Options machinery** (Black-Scholes, greeks) — the venue lists no
  options; encoding it would be cosplay.
- **Leverage as a tool** (ch. 2's margin math is used as a BOUND only) —
  $1,000 no-top-ups is fleet law.
- **Booking convergence P&L** — the basis affects entry only; booking a
  price term would break the delta-neutral accounting and cannot be
  backtested (no premium history). Restrict-only veto instead.
- **Cross-venue basis arb** — LIGHTER-ONLY is doctrine; one venue's basis
  is the only honest one.

## Birth checklist (the Barnesy parity list, applied)

- claim_writer at loop top + `:standby` key ((hp)/(ic)) ✅
- funding-form (gr) telemetry, no prices (delta-neutral modelled) +
  `entry_prem_bps` per close ✅
- `snapshot_equity` from day one (`MTM_REQUIRED`) ✅
- census incl. `above_band` (the hand-off, visible) / `deep` (the Farmer's
  tier) / `adverse_basis` ✅ · the full band published in `caps` ✅
- registrations: dashboard, `SELFTEST_MODULES`, `ROW_ENTRY`,
  `fleet_allocation.FUNDING_BOOKS`, `audit_book_overlap.FUNDING_BOOKS`,
  `study_exit_sweep` refusal, born-dark ✅
- deploy: `Dockerfile.hull`, `MANUAL_IMAGES_OK` birth state, (lr) provision
  dispatch, activation gated on the row publishing ✅
