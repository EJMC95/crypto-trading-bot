# Fleet Review — 2026-07-14: metrics, scope, strategy + the consumption wiring

*Data: live `/pnl.json` + `/trades.json` (121 closed ledger trades, 3–13 Jul),
the trainer's analyzer cards, `/watchdog.json`, `/pulse.json`, and the
review docs since 19 Jun. Tape context tonight: Fear & Greed 22, pulse mood
−0.21, 8/10 majors in a short regime (7-Jul oracle read), panic flag off.*

---

## 1. Scoreboard — W/L is the wrong lens for two of the "losers"

The question asked was "a number of them have significant loss over win."
True on raw counts for seven bots — but two of those are **positive
expectancy by design** and should not be touched:

| Bot | W/L | P&L | Verdict |
|---|---|---|---|
| event-listing-sniper | 31W/296L (9.5%) | **+$205.70** | KEEP — lottery-ticket profile: small delisting losses, rare huge wins (ANSEM +$325). The 07-07 ghost-gate already cut the junk tax. |
| perps-funding-carry | 4W/30L (11.8%) | **+$7.25** | KEEP — income is funding decay; "losses" are small flips. Lighter shadow twin: 5W/3L, +$8.92 — the edge is realer on the zero-fee venue. |
| crypto-trend-daily | 1W/12L (7.7%) | **+$2.56** | KEEP (CONTROL) — one +$6.44 ROI winner paid for all 12 probe losses. That is how trend-following looks. |
| crypto-breakout-4h | 2W/9L (18%) | −$8.69 | **FIXED this session** (BTC-tide gate, §3) |
| freqtrade-dad | 2W/9L (18%) | −$7.44 | **FIXED this session** (same carrier) |
| crypto-intraday-15m | 11W/26L (30%) | −$15.23 | Fixed 13-Jul (range_meanrev retired, counter-trend stop 2.0→3.5x); PROBATION continues — brain multipliers now armed over it (§4) |
| freqtrade-georgia | 14W/24L (37%) | −$4.34 | Same 13-Jul fix; watch the new era |
| freqtrade-mum | 0W/4L | −$5.83 | **FIXED this session** (whitelist curation, §3) |
| equities-momentum-alpaca | — | −$3.2k, −$1.8k today | Separate mandate/repo — flagged, not touched here |

Mechanics behind the spot bleed (ledger, per exit reason):
- **intraday-15m**: 20 trailing-stop exits, 0 wins, −34.9% cumulative, while
  ALL 9 ROI exits won — the ATR ratchet was the killer. The 13-Jul stop
  widening addresses exactly this; its replay predicted stop bleed
  −$15.57→−$9.62.
- **breakout (both carriers)**: 11 different pairs broke above their own
  200-EMA and died by exit_signal — a market-wide fakeout wave the per-pair
  filter cannot see (PF 0.073 in the window).
- **mum**: 4 whipsaw losses in chop; the strategy was only ever validated on
  BTC+ETH daily, yet traded 15 alts.

## 2. "Has new data been collected that can improve them?" — yes, three sets

1. **The unfrozen bot_trades ledger** (dollar-quote bug fixed 12-Jul): 121
   tagged closed trades over the exact bleed window. This is what powered the
   per-tag diagnosis above and the two backtests below.
2. **The Lighter shadow books** (7 books live since 13-Jul): first venue A/B
   data. Early signal: funding-carry paper 4W/30L vs Lighter shadow 5W/3L —
   same signal, radically better fills/funding on the zero-fee venue. Also
   the live-vs-shadow +5.4% gap alert on Funding Farmer (13-Jul) — execution
   divergence, now visible. The brain now reports this table every run (§4).
3. **The shared-organ history** (`bot_state_history`, collecting since
   7-Jul): regime oracle, fleet-risk light, signal bus — published for a
   week with zero consumers, which was the design's plan ("advisory week
   one") and today was its scheduled enforcement review.

## 3. Evidence-gated bot fixes shipped (backtest first, per repo rule)

**MomoBreakoutV1 — BTC-tide gate** (`scripts/backtest_momo_tide_gate.py`,
Kraken 4h, all 30 whitelist pairs, 20-Apr→14-Jul, 0.26%/side):

| Variant | n | win | Σ per-trade ret | PF |
|---|---|---|---|---|
| A as-deployed | 121 | 33% | −94.0% | 0.79 |
| **B + BTC>4h-EMA200 gate** | **74** | **37%** | **+79.1%** | **1.43** |
| C breadth≥50% gate | 78 | 35% | −9.3% | 0.96 |
| D half-size off-tide | 121 | 33% | −19.1% | 0.94 |

Baseline reproduces the live July bleed (27 entries, 22% win). Variant B
shipped: breakout entries now also require BTC above its own 4h EMA200 —
the same idea as the pair-level EMA200 rule, one level up, computed from the
BTC informative pair so `freqtrade backtesting` reproduces it exactly.
Honest caveat: one 3-month window — but it is precisely the regime the bot
bleeds in, and the validated core (+$201.59/603 entries, 2022-26 replay)
earned all of it in up-tides. Covers **crypto-breakout-4h + freqtrade-dad**.

**TrendMomoV1 (mum) — whitelist curation**
(`scripts/backtest_trendmomo_pairs.py`, Kraken 1d, 2 years, exact strategy
rules): 10 of 15 pairs positive (BTC PF 1.79, ETH 3.03, XRP 3.75, DOGE 3.40
…); five structurally negative — DOT (PF 0.31), ATOM (0.08), NEAR (0.49),
LTC (0.71), AVAX (0.56), Σ −313% vs +863% for the kept ten. Same precedent
as V4's majors curation (which took it from +19.7% to +33.3%, PF 7.26).
Dropped the five from `config_mum.json`. Note this replay also softens the
12-Jul "core leg −29%/4.5y" flag: over the recent 2 years the core is
strongly positive — the 4.5y number was dominated by the 2022 bear and the
trendless five.

**Deliberately NOT touched:** DayTraderV5Gated's remaining sleeves (13-Jul
fix needs its own era of data first — brain multipliers now watch it);
SwingDipV1 entries (barely fires in this tape — that is the design working);
funding-carry and sniper (positive expectancy); L5 meta-allocator (design
says months out).

## 4. The brain: capability, capacity, involvement, reach — all four advanced

The audit found every intelligence organ **built and publishing, and
consumed by nobody**: the oracle/risk/bus had zero readers; the brain's
per-tag W/L analysis ended as prose. What shipped today:

- **Capability (L4 meta-labeling, the design's highest-leverage layer):**
  `bot_learn.py` now computes NUMERIC, REDUCE-ONLY per-(bot, enter_tag)
  stake multipliers from the ledger — 0.5× (n≥30 era trades, negative P&L,
  win rate <25%), 0.75× (n≥30, wr<40%; or 15≤n<30, wr<25%) — streak-gated:
  the reduction must recur on 3 consecutive runs before publishing, and a
  recovered tag un-throttles immediately. Published to bot_state
  `brain-stake-mults` with the standard `updated`+`ttl_sec` freshness
  contract. v1 never sizes UP.
- **Involvement (the first brain output bots trade on):** all four active
  freqtrade strategies apply the multiplier in `custom_stake_amount` via the
  new shared client `fleet_bus.py` (clamped [0.5, 1.0], neutral on any
  doubt, inert in backtests because DATABASE_URL is unset there). The
  in-code contract written on 03-Jul — "a signal only earns entry-gate power
  once the brain shows a persistent edge" — is now mechanized instead of
  aspirational.
- **Reach:** the brain now runs a **venue A/B report** every cycle (paper vs
  -lshadow vs -lighter rows) in lessons + state key `venue_ab` — the shadow
  books stop being dashboard-only. ERA_START updated for the 13/14-Jul
  changes so it never prosecutes new code for old crimes.
- **Capacity:** unchanged runtime (2-hourly in the freqtrade container) but
  the state now carries multiplier streaks + venue tables; today's live-data
  dry run: 121 trades in, 9 A/B pairs out, 0 multipliers published — correct,
  nothing currently clears the floor. The machinery is armed for when
  something does.

## 5. Scanner results + fleet risk: from advisory to implemented

- **L2 fleet-risk veto (ENFORCED):** all four strategies now veto NEW long
  entries in `confirm_trade_entry` when the fleet's directional long book is
  at budget (20). Side-specific (long count, not the blended light), never
  touches exits/open positions, fail-safe OPEN on stale data, and
  `FLEET_RISK_MODE=advisory` on the service is the central kill switch.
  This is the 26-position-pileup guard, enforced exactly on the review date
  the 07-07 design scheduled. Current book: 10/20 longs — green, veto idle.
  (Also folded gate0's venue-aware counting into main's `fleet_risk.py`,
  which the 09-Jul changelog described but main never received.)
- **L3 sniper intel on the bus:** the sniper now publishes its intel
  classifications (open book by class, ghost-skip tally, per-position
  class/venue detail) to bot_state `listing-intel` every cycle — scanner
  knowledge visible to the brain/dashboard instead of dying in-process.
- **Also fixed:** `bot_name` in all 8 configs was stale copy-paste
  ("trend_golden_cross" on four different bots); now set to the real bot IDs
  — this is the identity `fleet_bus` uses for multiplier lookups.
- **Watchdog's "64 open positions" warning:** counts every row including
  shadows/stocks; the risk layer's scoped count is 10/20 directional paper
  longs. Not an emergency — but the pair-pileup readout (TRX×3, AAVE×2
  tonight) is the thing the L2 layer now actually guards.

## 6. Kill switches / rollback

| Change | Rollback |
|---|---|
| Fleet-risk veto | `FLEET_RISK_MODE=advisory` env on freqtrade-bots service (no redeploy of strategies) |
| Brain multipliers | stale-out automatically if the brain stops (ttl 26000s); or delete bot_state `brain-stake-mults` |
| BTC-tide gate | revert one condition in `MomoBreakoutV1.populate_entry_trend` |
| Mum whitelist | restore 5 pairs in `config_mum.json` |

## 6b. Addendum (same day): the diagnosis layer

The brain-card review of its four "tighten the X entry gates" proposals
exposed the next gap: the brain had one prose template for every negative
bucket and couldn't tell an entry problem from an exit problem from a
fee/venue problem (two of the four proposals were exit reasons mislabeled
as entry modes — plumbing fixed the same day). Shipped in response:
`diagnose()` classifies every negative (bot, tag) bucket at n≥10 into
**exit_too_tight / venue_execution / fee_bleed / regime_timing /
entry_quality / mixed_unclear**, evidenced by exit-path splits, post-exit
drift from public 1h candles (the mechanized 13-Jul stop replay), fee-scale
tests, a regime-oracle-history join, and the venue A/B table — published to
bot_state `brain-diagnosis`. Ground-truth validation on the July ledger:
it re-derived the trailing-stop verdict (79–100% reclaim vs the manual
replay's 77–89%), confirmed the breakout bleed as entry-side (22% reclaim),
and declined to call dad's murkier 11-trade sample. Advisory-only.

## 7. What to watch this week

1. Breakout carriers: entries should go quiet until BTC reclaims its 4h
   EMA200 — silence is the gate working, not a bug.
2. `brain-stake-mults` staying empty is healthy; the first published 0.75×
   will name the next problem tag with evidence attached.
3. Funding-carry venue gap (paper vs shadow vs live) in the brain's A/B
   table — if Lighter keeps winning, the go-live case writes itself.
4. georgia/intraday new-era stats after the 13-Jul stop change — the
   analyzer's next cards are era-clean.
