# THE LEVERAGE PROGRAM — making every book leverage-able, in measured steps

**Eamon, 25-Aug:** *"the major focus to be on increasing p n l fleet wide —
enhancing the bots so they are leverage-able ... More opportunities, higher
leverage; bigger bets, we have the support to make bigger decisions now ...
Each bot must have its own arms and scanners and abilities that all get help
from organs."*

This is the week's execution plan. The doctrine that makes it safe is already
built and stays senior: leverage is admissible as the OUTPUT of a drawdown
budget on a measured basket (I22), never as an appetite typed into a config —
and the venue's margin surface, `N_eff`, `vol_target_gross_x` and the
stop-death ceiling are all published machinery as of (se)/(sr)/(sy). What was
missing is REACH: only the two live books have the layer. The program extends
it fleet-wide, biggest measured claim first.

## Phase 0 — shipped with this document ((td))

* **Manual-trade attestation** (`<PFX>_MANUAL_PNL_USD`): Eamon's manual fills
  are held out of the bots' published P&L, so the board's restrict backstop
  stops cutting live clips for losses that were never the bots'. Suggested
  values (computed at 25-Aug 08:07Z, replace with known actuals):
  `AVO_MANUAL_PNL_USD≈-66.4`; georgia's residual is consistent with open
  marks — set hers only if manual trades happened on that sub-account.
* **🎫 Taker risk budget 2x** (`TT_RISK_USD` 1.5→3.0, `TT_CLIP_MAX` 80→95):
  the fleet's best measured signal was deploying ~16% of its own book.
  CLIP_MAX is DERIVED from the sizing-safety guard's 1.2x funding bar — a
  first draft at 160 was refused by the guard, which is the system working.

## Phase 1 — measure: the leverage-readiness table (1 session)

Extend the ceiling instrument (I24's `scripts/ceiling.py` + the golive
publisher) so every LIVING book publishes, every loop or every 6h:
`n_eff` (correlation-aware, from its own held/candidate basket) ·
`vol_target_gross_x = 0.15 / (|stop| / sqrt(n_eff))` · `stop_dead_above` at
the venue's live worst mmf · current effective gross · and, for books with a
POSITIVE I16 claim only, the implied $/day at target gross. Books without a
positive claim get DECIDABILITY as their ceiling — scaling a coin flip scales
a coin flip. Output: one ranked table answering "which book can carry bigger
bets, and how much is a notch worth."

## Phase 2 — plumb: per-book gross for shadow books (1–2 sessions)

One owner (`fleet_bus`), one accessor, per-book env (`<BOOK>_GROSS_X`-style),
consumed at each book's sizing site the way the live host consumes `GROSS_X`
— clamped by the book's own vol target from Phase 1, fail-safe 1.0. Wire in
claim order: 🌾 carry (era-gated — new-policy closes decide), 🔮 georgia
shadow, then the rest as claims turn positive. A book with no positive claim
keeps 1x and earns its multiplier the same way every book earns everything
here: on its own ledger.

## Phase 3 — synchronicity: organs ↔ scanners ↔ books (the week's spine)

1. **Revive the promotion pipeline on the family twins.** The judge's lane
   died with the Farmer. The family books have PERFECT experiment pairs (same
   strategy object, live + shadow) — design the successor lane: judge grades
   live-vs-twin per book with its existing paired bar, promotes bounded lever
   changes through the same sole-writer discipline. Its best-evidenced
   candidate ever (max-hold-24) meanwhile gets spent on the Farmer SHADOW via
   the shadow-lane grant so it stops aging in a queue nothing reads.
2. **Fix the board's live backstop input.** Phase 0's attestation fixes the
   contamination; the structural half is that the backstop reads LIFETIME
   `pnl_abs` — re-derive it on era-scoped, attributed P&L so a book born
   mid-drawdown isn't restricted forever by its birthday.
3. **Recalibrate the brain's floors for the 6.7x range** (carried item
   `brain-mults-are-two-opinions-wide`): measure how many buckets qualify at
   each floor and what their realised expectancy was. An organ with a 6.7x
   range and two opinions is a V12 idling.
4. **Allocation consumers beyond the three funding books** — the taker got
   its step in Phase 0; wire `allocation_scale` where era claims license it.
5. **Restart 🧭 nav-cook** (any push touching its files resurrects it) and
   run the (ss)-class postmortem — a scanner the organs can't see is a
   scanner that doesn't exist.

## Phase 4 — live gross, operator-set, arithmetic-published

🔮 georgia runs 5x of a 10x ceiling with her stop alive to **9.09x** — each
notch is one Railway env change, and her row publishes the consequence every
loop. 🙏 Avo's lever is the BASKET, not the multiplier (stop-dead above
6.25x; `diversified_order` is her multiplier). 👩 mum launches at 1.0 and
earns notches on her control arm's own verdict — her stop is the tightest in
the family, so the same gross costs her the least.

## Phase 5 — "each bot has its own arms, scanners, abilities"

The per-book pattern, applied at each book's next earned deploy: `extra.thesis`
on-row (18 of 19 missing — the `books-should-declare-themselves` carried
item), registered levers with QUANTITIES at each env-only book's day-31
graduation (the birth entries already schedule these), and a census that says
WHY nothing opened (most books have this; the gaps are listed in the weekly
review). Organs already serve every book that publishes the contract — the
work is finishing the contract per book, not new organs.

## What this program refuses, once, so it stays refused

Leverage on books with no positive claim (I16/I22); shipping a swept grid's
maximum; raising any bar to make a book pass; and any step that costs
measured expectancy for turnover (I19). Every phase lands with its number or
it doesn't land.
