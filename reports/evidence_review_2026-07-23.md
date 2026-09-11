# Daily Evidence Review — 2026-07-23

**Reviewed:** 2026-07-22 23:24 UTC (= Thu 23 Jul 09:24 AEST, Sydney)
**Alerts considered:** 11 distinct keys, all fired within the last ~2 days (feed
window 16-Jul → 22-Jul UTC).

No ⚠️ ACTION item. Fleet 7d drawdown is −0.03%, no live-money divergence, no new
go-live candidate. One watch item below.

## Verdicts

| Key | Status | Why |
|-----|--------|-----|
| census:50 | active | Snap Back census now **3748** events (alert said 3544); organ still shadow-only, no live consumer — review milestone stands. |
| disloc:0G | active | census 205, max 258bps — matches alert. |
| disloc:APEX | active | max 313bps unchanged, census grew 1620→**1799**. |
| disloc:EIGEN | active | census 113, max 156bps — matches; last event 22-Jul 09:00 UTC. |
| disloc:KAITO | active | census 418→**420**, max 350bps — matches. |
| disloc:NEAR | active | census 14→**15**, max 150bps — matches. |
| disloc:ZORA | active | census 135→**136**, max 202bps — matches. |
| disloc:RESOLV | active | census 332→**333**, max 188bps — matches. |
| disloc:BIO | active | census 36, max 272bps — matches. |
| factor-sample:3 | active | scanner decision+context dataset milestone at 106 closes; append-only — flag stands. |
| veto:DOT | active | coin-vetoes still exactly `[ADA, BOT, DOT, SOXL]`; DOT vetoed on stop rate 4/8 ≥ 50% (30d) — list matches alert. |

Every recent alert verifies against current data. Because the feed is fresh
(nothing older than ~2 days), **no key resolved or went stale** this cycle — the
banner will stay populated but the `reviewed Nh ago` stamp refreshes.

The 8 `disloc:*` items are info-severity **thesis evidence** for Snap Back, a
shadow-only census organ with no trading consumer. Their `max_bps` is a running
max (never decreases), so "matches current" is guaranteed by construction — they
are accurate but low-value banner items, not live signals.

## New evidence

- **⚑ Watch — taker LIVE lens is net-negative on the shadow.** The Ticket
  Taker's live lens is **short-divergence**. On the shadow twin
  (`lighter-ticket-taker-lshadow`) that lens is now mature (n=70) and **net
  ≈ −$5.67**: `tp` +$10.68 (n=56, 30% WR), `sl` −$16.74 (n=12, 0% WR), `hold`
  +$0.39 (n=2). The 0%-WR stop bucket dominates. Consistent with the standing
  memory that the taker went live on a thin −3.9bps edge; worth watching the
  live divergence book against this.
- Taker **long-divergence** n=18, net +$4.55 (tp +$13.04/n5, hold +$0.75/n6,
  sl −$9.24/n7) — small sample; long lenses have no proven forward edge.
- **Funding Farmer live vs shadow: clean, live ahead.** LIVE
  (`perps-funding-lighter-lighter`) +$4.52 @ 73% WR (41 closed) vs shadow
  +$11.72 @ 57% WR (68 closed). Both positive, no adverse divergence.
- **Fleet 7d drawdown −0.03%** (`fleet-risk.fleet_dd_7d = −0.0003`). DD governor
  idle, `clip_scale = 1.0`, mode `enforce`, light `yellow`.
- **No new go-live candidate.** The only rows at WR>55% with ≥20 closes are the
  already-LIVE Funding Farmer (73%/41) and its shadow twin (57%/68) — neither is
  a new Proving bot clearing the gate.

## Recommended human action

None required. Optional: eyeball the live Ticket Taker's short-divergence stop
frequency — the shadow twin's SL bucket (0% WR, n=12) is what turns that lens
net-negative, so if the live book is taking the same stops it is trading a lens
the shadow currently grades unprofitable.
