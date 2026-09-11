# Evidence Review — 2026-07-24

_Reviewed 2026-07-23T22:15Z (≈ 2026-07-24 08:15 AEST). No ⚠️ action required._

Fleet is quiet and green. All 13 distinct alert keys in the last-7-day
`fleet-alerts` feed verify **ACTIVE** against current data — the feed is fresh
(every dislocation event is <24h old), so nothing has resolved or gone stale.

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | Snap Back census now **4573** events (alert said 4503); organ still shadow-only, no live consumer — review milestone stands |
| factor-sample:3 | active | Scanner decision+context dataset milestone (~115 closes); append-only, only grows |
| disloc:0G | active | census 231, max 258bps — matches alert; last event <24h |
| disloc:APEX | active | census 2369 (grew from 2313), max 313bps — current |
| disloc:EIGEN | active | census 120, max 161bps — current |
| disloc:KAITO | active | census 468, max 350bps — current |
| disloc:STABLE | active | census 243, max 170bps — current |
| disloc:NEAR | active | census 16, max 150bps — thin but current |
| disloc:ZORA | active | census 145, max 202bps — current |
| disloc:RESOLV | active | census 347, max 188bps — current |
| disloc:CHIP | active | census 93, max 160bps — current (newest, 23-Jul) |
| disloc:BIO | active | census 39, max 272bps — current |
| disloc:STBL | active | census 121, max 228bps — current |

All `disloc:*` items are 🧲 Snap Back **thesis evidence** on a shadow-only organ
(broker realized −$0.24, no live consumer) — they accrue census, they do not
demand action.

## New evidence

- **Funding Farmer LIVE** (`perps-funding-lighter-lighter`) at n=46 closes,
  WR **74%** — the real-money book is healthy. Already live, so not a new
  candidate; noted as a positive.
- **Taker short-divergence (the LIVE lens)** now n=71, net **−$4.50** (up from
  −$5.67 yesterday but still net-negative). The SL bucket (n=12 @ −$16.74)
  dominates a +$11.86 TP bucket; taker overall WR 35% on n=110 shadow closes.
- **Taker long-breakout** newly crossed n=10, net +$7.72 — but long lenses
  regress to noise as n grows (`taker-long-lenses-no-forward-edge`); small n,
  do not act.
- **No new go-live candidate.** The only bots clearing ≥20 closed / WR>55% are
  the already-LIVE Farmer and its shadow twin (n=72, WR 60%). Caveat:
  `bot_pnl.extra.max_drawdown` reads 0.0% fleet-wide (unpopulated), so the
  <15% dd gate can't be confirmed from that field — win-rate/count only.
- **Fleet 7d DD −0.11%** (`fleet-risk`), light GREEN, governor untriggered.
  Fleet equity $8,165.

## Recommended human action

None. Watch item (not urgent): the taker's LIVE short-divergence lens stays
net-negative on shadow, driven by a 0%-WR stop tail — consistent with the
standing read that the taker's live edge is unproven (t<2). No gate crossed
either way.
