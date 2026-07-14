# Cross-Bot Advisory Review — 2026-07-14
*The enforcement review the 7-Jul design scheduled (CROSS_BOT_INTELLIGENCE_DESIGN_2026-07-07.md §4, Phase 2/3): after a week of advisory publishing, decide the wiring from evidence.*

## Data access caveat (and the first finding)

The review was supposed to be judged from the historized `bot_state_history`
snapshots. **A review session cannot reach them**: no `DATABASE_URL` off-Railway,
and the dashboard exposes no bus/risk endpoint (only `/pulse.json`,
`/pnl.json`, `/trades.json`). This review therefore *reconstructs* the fleet
timeline from the `/trades.json` ledger (every trade's open/close timestamps →
concurrent exposure at each entry) — which covers the freqtrade cohort
(10 of the 12 directional books; `perps-rsi-meanrev` / `perps-donchian-breakout`
write to `paper_trades`, not served). All concurrency figures below are
therefore a LOWER bound on true fleet exposure.

**Fix shipped with this review:** a read-only `/bus.json` endpoint (same
no-auth, no-secrets pattern as `/pulse.json`) serving the live `fleet-risk` +
`signal-bus` states and their recent history, so the Jul-21 review can be run
from evidence instead of reconstruction.

## Layer 2 — fleet risk light: WIRE THE RED VETO

Ledger: 121 trades, Jul-03 → Jul-13 (the advisory window is fully covered).
For every entry, count the ledger-visible fleet positions open at that instant:

| fleet positions open at entry | n | win% | avg $ | total $ |
|---|---|---|---|---|
| 0–4 | 17 | 29% | −0.04 | −0.62 |
| 5–8 | 22 | 23% | −0.57 | −12.50 |
| 9–12 | 38 | 34% | −0.35 | −13.17 |
| **13+** | **44** | **18%** | **−0.41** | **−18.04** |

Entries taken while the visible fleet already held 13+ positions are the worst
bucket by win rate and total damage. Peak visible concurrency hit **20** on
Jul-08 04:00 — and that's with two perps books invisible to the count, i.e. the
true fleet was deeper into the yellow band (≥14 longs at 34 visible entries)
than these numbers show. The as-spec'd RED line (20 longs) was never crossed by
a *visible-at-entry* count, so a RED veto would have cost ~nothing this week
while capping exactly the tail the 26-position dip scar came from.

Same-base pileup points the same way on a tiny sample (entries where 2+ bots
already held the coin: n=5, 20% win, −$0.61 avg vs −$0.34 baseline) — not
actionable alone, but consistent.

**Verdict:**
- **Wire the RED veto as originally spec'd** — `confirm_trade_entry` (freqtrade)
  / pre-entry check (perps loops): light=RED ⇒ no NEW same-direction entries.
  Keep budgets 20L/12S. YELLOW stays advisory.
- **Not wired in this PR** — entry-gating is bot logic and gets its own change
  per repo rule. This review supplies the go-ahead evidence.
- Tag the light into each entry (poller or strategy) so Jul-21 measures
  enforcement directly instead of reconstructing.
- Honest caveat: concurrency is endogenous (signals cluster in dips); the
  bucket table shows correlation, not proven causation. The veto is still
  cheap insurance at the extreme tail.

## Layer 3 — signal bus: DO NOT WIRE (fix the signals first)

What's actually on the bus right now:

- **`xexchange_dislocation_pct` = 4.64** at review time. That is not market
  stress — it's a thin-pair/symbol-collision artifact sitting just under Gap
  Scout's 5% `MAX_PLAUSIBLE_GAP` ceiling (max over 342 pairs, incl. illiquid
  Gemini books). Corroborating: the scanner's "real"-basis balance stands at
  **+$6,095** paper profit, on an engine whose own docstring says a flat
  balance is the honest expected result — sub-5% fictions are being booked and
  the same fictions dominate the published max. As a stress gauge this field
  is noise.
- **`funding_hottest_apr`** = PURR +251% / CASHCAT +241% — the max-over-tiny-
  coins is permanently extreme; carries no fleet-level information.
- **`pulse_mood`/`pulse_panic`** — the only bus signal with bite this week:
  all 8 entries inside the available pulse window (Jul-12→14) fired during
  `panic=true`; 7 of 8 lost (−$6.66 net) *despite already being half-staked*
  by the existing panic stake-gate. n=8 — keep the stake gate, and per the
  standing doctrine (entry gates need brain-confirmed edge) keep logging
  before any entry veto.

**Verdict:** no trader reads dislocation or hottest-funding as filters until
the signals are rebuilt: publish a liquidity-floored dislocation (or a
majors-median), and a majors-only funding view. Re-review Jul-21 off
`/bus.json` history.

## New in this PR — Layer 3 gets a venue-relevant signal (Lighter premium)

Eamon trades on Lighter; none of the bus signals describe that venue. Gap
Scout now also polls Lighter's public `orderBookDetails` (keyless, one call,
all 215 books) and publishes the **venue premium** — `mark_price/index_price − 1`
in bps, i.e. how rich/cheap Lighter trades vs its own external-index oracle:

- `lighter_prem_bps` — per-book premium for the family-relevant watchlist
  (BTC, ETH, SOL, SPY, QQQ, XAU; env-tunable),
- `lighter_prem_med_bps` / `lighter_prem_max_bps` / `lighter_prem_n` —
  median/max |premium| across all active books ≥ $100k/day volume: the
  fleet-wide venue-stress gauge.

Live probe at review time: majors −5…+9 bps; RKLB (a current Stock Leaders
qualifier) +26 bps; SK Hynix +50 bps. Why it's the right signal for the books
we run: taker entries pay the premium (it mean-reverts to index by
construction), persistent premium is the leading indicator of funding drag
(the momo bot's funding-veto A/B measures the trailing version), and a sudden
fleet-wide |premium| widening is Lighter-specific stress. Same contract as
everything on the bus: guarded fetch (Railway's WAF has blocked other Lighter
REST before — failure just omits the fields), TTL'd, historized, ADVISORY —
no consumer until a review earns it.

## Current state at review time

Full-fleet light (live extras, incl. perps books): **GREEN — 10 long / 0
short** vs budgets 20L/12S.

## Action list

1. ✅ this PR — Lighter premium published by Gap Scout + mirrored to the bus.
2. ✅ this PR — `/bus.json` read-only endpoint (bus + risk state and history).
3. ⏭ separate change — RED-veto enforcement wiring (evidence above; bot logic,
   own PR per repo rule).
4. ⏭ separate change — liquidity-floored dislocation + majors-only funding on
   the bus.
5. ⏭ gate0 — port the 4-line bus mirror to the venue-aware `fleet_risk.py`
   (main's copy predates `authoritative_row()`; whichever branch's service
   runs it needs the mirror).
6. 📅 Jul-21 — re-review from `/bus.json` history: judge the Lighter premium
   + enforcement telemetry.
