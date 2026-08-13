# 📖 Trading and Exchanges (Larry Harris) — read against the fleet, not into a new row

**Operator, 13-Aug:** *"Can you implement any knowledge from Trading and
Exchanges: Market Microstructure for Practitioners — Larry Harris also this
could be helpful."*

Harris is different from the other four books: he describes the MACHINERY of
markets, not a strategy — and this fleet has been paying his tuition for
weeks. So this reading is an audit first and an implementation second: what
of Harris already exists (verified, not rebuilt — I11), what this pass adds,
and what is refused with reasons. **No new row is minted** — a
microstructure book's lessons land inside every book that trades, or they
land nowhere.

## What the fleet already runs, chapter by chapter

| Harris | The fleet's existing implementation | Where |
|---|---|---|
| Transaction-cost analysis / implementation shortfall (ch. 21) | The 📏 organ: continuous live-vs-shadow per-trade return gap on paired coins, with ENTRY/EXIT slip decomposition, phone on sustained slip | `implementation_shortfall.py` — it is literally named after the concept his text popularized |
| Effective spread ≠ quoted spread; measure at YOUR size (ch. 21) | The (js) tx-hash fill study — REAL fills by volume tier: ≥$10M 0.27/0.97bps, $1–10M 1.93bps, <$1M 5.12/14.77bps; 🛢️ Garrett's tier friction comes from it, and 💸 the Farmer's `book_metrics` walks the live book to clip size (VWAP slip both sides) before every real entry | `lighter_funding_bot.py::book_metrics`, STUDY archives |
| Don't trade when price discovery is broken (ch. on volatility/circuit breakers) | The stress veto: venue-wide \|premium\| median ≥15bps pauses NEW entries, exits keep running | `lighter_ticket_taker.py` stress veto; `fleet_bus.venue_stress_bps` |
| The zero-sum frame: know whose money you are winning, or you are the utilitarian trader (ch. 8-9) | The (hm) random-entry benchmark doctrine — every directional grade is against random entries on the same coins/bracket/window, never against zero; the wave-2 books were all born through it | CLAUDE.md (hm); `scripts/study_books_cohort_2026-08-13.py` |
| Adverse selection: standing orders get picked off by informed flow (ch. 4-6) | The dip lens — catching falling knives — is the fleet's only statistically significant taker loser (t=−2.66) and is structurally vetoed by its own realised record; 🧲 Snap Back (fading dislocations) retired at t=−2.97 | I14/I15, `realised_lens_evidence`; (jh) |
| Bid-ask bounce contaminates measurement (ch. 21) | The (hm) two-price-bases lesson: a `_tp` booked off a different basis than the exit label poisoned 45 of 98 rows; ledger writes now assert basis consistency | `lighter_ticket_taker` basis invariant |
| Liquidity is tiered; size against depth (ch. 14-15) | The volume tiling — 🛢️[0.1M,2M) \| 🧮[2M,10M) \| 💸[10M,∞) — plus the Barnes-extreme retirement (a $10M floor against a supply that never existed) and `venues/safety.open_notional` | I20, (ly) |

That table is the point: Harris's book is why these mechanisms exist in ANY
serious shop, and the fleet grew each one by paying for its absence.

## What this pass adds — the falsifiable-slip telemetry ((mg))

The one genuine gap: the four wave-2 shadow books charge **flat modelled
slip constants** (5bps/side price books; 15bps/side modelled pairs) that
nothing could falsify — Harris's cardinal sin, an ASSERTED transaction cost.
Now every wave-2 book records the venue's **quoted spread at entry and at
exit** (`spread_bps_entry`/`spread_bps_exit` on every close row, one
orderbook fetch per event, telemetry only — fail-open, never a gate):

- After ~30 closes each book has a measured spread distribution to hold
  against its constant; the (js) tier table says the constants are likely
  CONSERVATIVE (the $1–10M tier measured 1.93bps/side vs the 5bps modelled)
  — now the books' own rows will say so, or say otherwise.
- 🧮 Hull's case is the sharpest: its payback-velocity floor (7.82% TRUE) is
  DERIVED from the 30bps RT assertion. If its [2M,10M) coins quote wider,
  the floor is too low and the spread rows will show it before the ledger
  pays for it.
- The `spread_bps` arithmetic inherits the Farmer's two measured refusal
  shapes, selftest-pinned in all four books: non-positive levels are
  FILTERED (a negative level sorts first and fabricates a garbage mid — the
  30-Jul live-path fix), and a crossed book returns None (not a price, no
  claim).

## Deliberately NOT implemented, with reasons

- **Market-making / limit-order books** (ch. 13-14, dealers earning the
  spread): the shadow broker fills at mark by declared model — a maker book
  needs a queue-position fill simulator, and a modelled maker without one
  fabricates exactly the fills Harris says are hardest to earn (adverse
  selection means resting orders fill WHEN YOU ARE WRONG). A day-31+
  candidate only with a real fill model; never by assertion.
- **A spread ENTRY VETO on the wave-2 books**: the funding family has one
  (`MAX_SPREAD_BPS`, measured lane); adding an unsimmed gate to the four
  newborn books would drift them from the evidence they were born on (the
  same reason Douglas refused an unsimmed stress veto). The telemetry comes
  first; a veto is a day-31 decision made on the books' own spread rows.
- **Order-anticipation / front-running defenses** (ch. 11): shadow books
  print no orders to front-run; the live path's protections (SafetyRails,
  slip vetoes) already exist.
- **Payment-for-order-flow / venue-choice economics**: one venue is
  doctrine (LIGHTER-ONLY); there is no routing decision to optimize.
