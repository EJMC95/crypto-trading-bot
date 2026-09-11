# Daily Evidence Review — 2026-07-22

Reviewed 22:27 UTC 21-Jul (**08:27 AEST 22-Jul**) — auto-run of `daily-evidence-review`.
Ground truth = live `bot_state` organs + `bot_pnl` / `paper_trades` / `venue_orders` ledgers.
All organs read fresh (ages 0–8 min).

## ⚠️ ACTION (one item, real money)

**Yesterday's recommended redeploy just landed — and the test of it hasn't run yet.**
The live Funding Farmer's build changed **`d323c0f6fc2a` → `3ec9f015efc6`** inside a 20-minute
window (present at the 22:06 UTC shortfall run, changed by the 22:25 UTC pnl publish). So the
`railway up` this review asked for on 21-Jul appears to have shipped.

**But its effect is untestable right now.** The last live order was 16:33 UTC — *before* the
redeploy — so all **51 live orders with `with_slip=0`** predate the new build. The next live
funding order is the test.

- **If the next order records slip** → telemetry debt cleared; Farmer verdicts finally rest on a
  measured number instead of an assumed one.
- **If it still records nothing** → the diagnosis flips from deploy-lag to **code**, and a second
  redeploy will not help. `implementation_shortfall.py`'s own note names the spot: all three of
  `lighter_funding_bot`'s `publish_venue_order` calls pass `px_fill=px_decision`, so the bot *has*
  the real fill (`venues.lighter_client.last_fill` / `_real_exit`) and never hands it to the ledger.

**`arm-drift` persists — the redeploy did not clear it, it changed which build is drifting**
(live `3ec9f015efc6` vs shadow `d0a671e3329e`, shadow unchanged; taker pair also drifts,
`1f92891a7492` vs `e2d382b771f9`). The −0.279pp live/shadow gap therefore remains **unattributable**,
and the xp-judge's promotion bar — which spends real money — rests on that same comparison.

*Not triggered:* fleet dd_7d **−0.06%** (governor untriggered, `clip_scale` 1.0); **no** bot newly
go-live ready; live/shadow gap well under the 2% bar. RED light is budget crowding (20/20 longs),
2nd day, working as designed.

## Verdicts (10 distinct keys, last 7d)

| Key | Status | Why |
|---|---|---|
| `disloc:APEX` | **active** | Escalating (census 1077→1089, event <15 min ago) — but the sign is **inverted**: 382/394 entry-eligible events and 7 of 8 all-time trades, 6 exiting `max_hold`. Counter-evidence to snap-back, not evidence for it |
| `disloc:RESOLV` | **active** | Live, escalating (318→319, event <15 min ago) — yet 0 entry-eligible events and 0 trades ever |
| `factor-sample:3` | **active** | Re-ran `market_context.py`'s join verbatim: **n=97 exactly** (89 w/ slope ctx, 56 wins). Verified |
| `census:50` | resolved | Reviewed. 2873→2895/29 syms, but it's an odometer — substance already logged in `snap_back_census_log.md` (21-Jul) |
| `factor-sample:2` | stale | Superseded by `factor-sample:3` (n=97) |
| `disloc:NEAR` | stale | Census frozen at 14 since firing, ~19h quiet — yesterday's "cooling" call continued |
| `disloc:ZORA` | stale | Unchanged at 125; 2 entry-eligible events all-time, 0 trades |
| `disloc:0G` | stale | Unchanged at 190; 2 entry-eligible, 0 trades |
| `disloc:EIGEN` | stale | Unchanged at 112 (briefly resumed 107→112 after yesterday's stale call, then ~3h quiet) |
| `disloc:KAITO` | stale | Unchanged at 386; produced the one genuine converged win (+$0.181, 13-Jul), nothing since |

*Criterion for `stale`: the census count has not moved since the alert fired, so the specific claim
is recorded rather than live. `veto:BOT` has aged out of the feed; the vetoes themselves are still on.*

## New evidence

- **Taker lens buckets grew, sign unchanged.** `short-divergence` n=25→**26** (+0.243%/trade, 13W);
  `long-divergence` n=12→**14** (−0.180%/trade, 6W). **D5 caveat:** Lighter's tape is one falling
  regime, so a short beating a long is expected *by construction* — non-diagnostic for edge.
  Note `long-divergence`'s dollar sum is **+$3.27** while its per-trade pct is negative — the winners
  were larger clips. Rank on per-trade, never on $.
- **Brain corroborates divergence-only from independent data:** `divergence` `ehit4h` **0.535
  [0.514, 0.556]** is the only lens whose lower bound clears 0.50 (breakout 0.482, dip 0.495,
  momentum 0.450 all straddle or sit below).
- **Coin-vetoes now corroborated by the taker's own ledger:** BOT + SOXL account for **6 of 14**
  `long-divergence` trades and **4 of its 7** stop-outs. BOT 216.71bps vs SOXL 17.91bps re-confirms
  slippage is **per-book**, not per-venue.
- **LIGHTER-ONLY guards verified holding** (not previously spot-checked here): every retired
  non-Lighter bot's last close is on/before 17-Jul — rsi-meanrev 13-Jul, donchian 15-Jul,
  listing-sniper 16/17-Jul, funding-carry HL arm 17-Jul, xexchange-arb 16-Jul. Every bot with 7d
  activity shows `venue=lighter`.
- **No bot newly passes go-live gates.** Two rows clear n≥20 + WR>55% — `perps-rsi-meanrev` (70.3%)
  and `perps-donchian-breakout` (87.5%) — but both are **retired and dead since 13/15-Jul**;
  non-Lighter history that justifies nothing. Do not mistake them for candidates.
- **Parliament has started trading** (21-Jul): 6 rows online, 12 closes total (gillard 9, abbott 2,
  rudd 1), equity ~flat, morrison/turnbull still at 0. Far too early to grade.
- **xp-judge** running `enter_apr=0.075`; not promotable (floors: shadow 2/30, live 3/10).

## Recommended human action

1. **Check the next live funding order's slip reading** (first order after ~22:20 UTC 21-Jul). That
   single row decides whether the redeploy fixed telemetry or whether the fix is a code change to
   `lighter_funding_bot`'s three `publish_venue_order` calls. 51 orders and counting with zero
   measurements — every Farmer verdict still turns on an assumed slip number.
2. **`arm-drift` is unfixed on both live pairs.** Until the arms share a build, the shortfall number
   and the judge's promotion bar are not attributable to execution. Worth an agenda line: the arms
   live in separate Railway services with separate deploy clocks, so this recurs by default.
3. **Consider re-wording `disloc:APEX`.** It keeps firing as "Snap Back thesis evidence" while the
   census log's own data makes it the opposite. The alert text is now misleading on its face.
4. Nothing else — governor untriggered, no live-money bleed, RED light is the budget veto working.

---
*Organs read: `lighter-dislocation-lshadow`, `fleet-risk`, `coin-vetoes`, `impl-shortfall`, `xp-judge`,
`fleet-proprioception`, `brain-lens-forward`, `parliament`. `evidence-review` upserted 22:27 UTC
(08:27 AEST). Report not committed, per task.*
