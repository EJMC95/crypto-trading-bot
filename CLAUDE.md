# CLAUDE.md — crypto-trading-bot Fleet

## What This Repo Is
Eamon's crypto trading bot fleet — **LIGHTER-FIRST since 2026-07-14** (user
decision: "all services must run off lighter"). Books are $1,000 paper/shadow
each, no top-ups, except the real-money Lighter live rows. Dashboard:
https://pnl-dashboard-production-858c.up.railway.app/

## Fleet Overview (post 14-Jul Kraken retirement; post 17-Jul LIGHTER-ONLY cut)
Every TRADING row below is on Lighter. Four non-Lighter services were code-
guarded off on 17-Jul — see the LIGHTER-ONLY table after the fleet table.

### The trading fleet (Lighter)
| Row | Name | What it is |
|-----|------|------------|
| freqtrade-{mum,dad,avo-maria,georgia}-lshadow | 👩👨🙏🔮 family | TrendMomo/MomoBreakout/SwingDip/DayTraderV5 on Lighter (gate0 `lighter_family_bot.py`, service `family-lighter-shadow`); closes tagged `long-<tag>_<exit>` + brain stake-mults applied at entry (15-Jul) |
| crypto-{intraday-15m,swing-daily,breakout-4h}-lshadow | spot ports | same service, 29-pair whitelist |
| crypto-trend-daily-lshadow | 🌊 Tide Rider | shadow only. Its LIVE row `crypto-trend-daily-lighter` was RETIRED 17-Jul — 🎫 Ticket Taker took the slot on the SAME service/keys/sub-account, so leaving both rows would DOUBLE-COUNT the same $34.67 of real money. **[30-Jul (hk)] ZERO closes in 20 days was CORRECT, not broken** — 1 buy / 0 sells ever in `venue_orders`, and its universe produced no signal flip of any kind in that time. What WAS broken: `(fz)` claimed this book was widened off the scout and it had no `fleet_bus` import and no COPY. Now wired: **6 → 16 books measured on the live bus**, additive (empty ⇒ keep the configured six, never shrink). **The prerequisite shipped with it:** `scan_universe()` scans the resolved universe ∪ every HELD coin, and `supports()` no longer skips a held position — without both, a coin leaving the list kept its position with no exit, no stop and no seatbelt (this book's only sweeper is `not dry_run`-gated, so shadow had none). Nine of the ten added books are TRADFI, so this is now a venue-wide trend follower despite the row name; kept ON (the EMA50/200 signal is per-coin, so it is per-asset by construction and cannot breach item 18) and reversible via `TREND_ALLOW_TRADFI=0`. Its 2.7yr +52% validation is SIX CRYPTO MAJORS and says nothing about XAU/SOXL — those sleeves are unvalidated and are there to be graded. Levers that can actually move its rate: `trend.universe_n` / `trend.min_vol_m` / `trend.max_open` (`trend.rank_by_funding` is inert while candidates ≤ slots — measured max simultaneously-golden coins = 1 vs 6 slots). Author: evidence board, gate lever = the universe. **[30-Jul (hl)] NO THROUGHPUT IS AVAILABLE WITHOUT PAYING EXPECTANCY** — 25 of 30 candidates died in refutation. `close<EMA20` gives 6.4x the closes and improves per-trade 5.1x, but **per bar-day held only 1.04x**: the gain is denominator shrinkage (median hold 58.5d -> 4d), a content-free 3-day time stop reproduces 78%% of it, and the exposure-matched null BEATS it. Tightening the catastrophic stop raises closes and makes total P&L WORSE. `min_vol_m` 5.0 -> **3.0** (ZEC+PAXG carry 91%% of the delta; 2.0 lowers the mean). `trend.max_open` cage hi 12 -> **9 as a SAFETY bound**: at >=10 the -10%% daily-loss halt becomes reachable before the -35%% stop, and in shadow that halt skips the whole scan — no death cross, no seatbelt, for the rest of the UTC day. `extra.caps` now carries a SKIP CENSUS: the row said `universe: 16` while 6 of the 16 are structurally mute (<202 bars), overstating the actionable universe by 60%%. 50/200 -> 10/20 is real throughput (0.38 -> 3.06 closes/30d) with UNESTABLISHED expectancy (beats only 84%% of 3000 placebo draws) — if ever shipped it is a SEPARATE ROW with the 50/200 control left running, never a re-parameterisation |
| perps-funding-lighter-lighter / -lshadow | 💸 Funding Farmer | **LIVE** funding harvester + shadow |
| perps-funding-carry-lshadow | 🌾 Yield Harvester | Lighter shadow. **[30-Jul] `MAX_POSITIONS` 8 -> 12: measured at 7 of 8, i.e. the fleet's BIGGEST EARNER was one slot from full and turning away carries it had already graded. Its 38.8% win rate is not a defect — carry's return lives in the tail.** Its HL-data arm (`perps-funding-carry`) is RETIRED 17-Jul — see LIGHTER-ONLY below |
| perps-funding-spread-lshadow | ⚖️ Counterweight | funding L/S book. **[30-Jul] K 5 -> 8 and the universe 30 -> up to 60 via `fleet_bus.scout_universe()`: measured AT its structural cap (10 open = exactly K=5 x 2 legs) while ranking 15% of the venue. Widening the candidate set does not loosen the rule — it still takes exactly top-K/bottom-K, from a real cross-section.**
| lighter-perp-sniper-lshadow | 🎯 Perp Sniper | new-listing sniper **+ volume-surge AND young-book candidates (30-Jul)** — SCOPE FIX: `new_listings` is a market-set DIFF, so a symbol qualifies for exactly the ONE loop in which it first appears, and only if the process is running with a warm baseline at that moment. That unobservable trigger, not the thesis, is why the book has n=1 in weeks. `young_candidates()` adds every book in its debut regime. **[30-Jul] the age source is now the venue's OWN `created_at`** — it was on every `orderBookDetails` row all along, in a response the scout already fetches, while the sniper burned 4 candle REST probes/loop to approximate it (measured: majors 558.6d, exactly 4 books under 21d). Scout publishes `ages_d`; the candle probe is the fallback for a dark scout and stops entirely once `ages_d` flows. An unparseable timestamp is ABSENT from `ages_d`, never 0 — "age unknown" must not read as "brand new". **The offered-ledger (`surge_done`) is a COOLDOWN map, not a tombstone**: it was a monotone set, so every book offered once was excluded forever and both new sources decayed to silence over weeks — the same starvation on a longer fuse. `not_young` stays permanent, correctly: books only age — the same phenomenon, observable for WEEKS. Candle probe is GOVERNED (`YOUNG_PROBE_BUDGET`/loop) and MONOTONE (`not_young` is permanent — books only age), so probe cost decays to zero. Plus volume-surge candidates — its event was too rare to grade (n=1 in weeks), so `surge_candidates()` adds books surging >=`SNIPER_SURGE_MULT`x 24h volume. They need their OWN dedup ledger (`surge_done`, persisted): every surging book is already in `baseline`, so baseline cannot dedup this source |
| lighter-dislocation-lshadow | 🧲 Snap Back | dislocation fader — reference is LIGHTER'S OWN `index_price` since 17-Jul (was Hyperliquid mids). **[30-Jul] the entry gate is now a PERCENTILE of the live residual distribution (`adaptive_enter_bps`), not a fixed 150bps — that constant was ~40x its own median residual (3.8bps) and predates the switch off Hyperliquid's mid. FLOORED at `EXIT_BPS * 1.5` and CAPPED at the operator constant: on today's tape the floor usually binds, so the practical effect is 150 -> ~60bps, not "the gate follows the median down". Universe 16 -> up to 40.**
| lighter-ticket-taker-lshadow | 🎫 Ticket Taker | **trades Lighter Scout's high-conviction tickets** (breakout/dip/momentum long + divergence long/short); stress veto pauses entries at venue |prem| med ≥15bps; closes tagged `<side>-<lens>_<exit>` so the brain grades each lens. **[30-Jul (hj)] THE SHADOW ARM TAKING LONGS IS CORRECT — the LIVE arm is now divergence-SHORT-only by HARD GATE.** `allowed_lenses` (live = divergence only, since 17-Jul) was only half the real-money rule: the SIDE restriction lived solely inside `if BULL_MODE:`, and `TT_BULL_MODE` defaults to **off**. Measured: the live row has 25 closes and **12 are `long-divergence`** (last 24-Jul); what stopped them was that env var being flipped on, not a gate. `LIVE_SIDES`/`allowed_sides(mode, lens)` is the fail-CLOSED twin — reads no env, no bus, independent of BULL_MODE; belt in the entry loop, braces at `market_open` checked against `is_long`. A lens with no `LIVE_SIDES` entry fills NOTHING live, so real money on a new lens is two explicit edits. Shadow keeps BOTH sides — that grade is what justifies the live rule. `policy.sides` is stamped on every close so graders can era-split the change |
| equities-regime-lshadow | 📊 Index Rider | stock-perp port (IBKR original RETIRED 14-Jul). **[30-Jul] universe 3 -> 10 (the venue's full non-crypto set, same books the family per-asset gate grades) and clip $250 -> $100 — it carried the LARGEST clip in the fleet on a book with ZERO closed trades. These are the fleet's only source of a regime that is not falling-BTC (SPY +8.1%, QQQ +12.2%, WTI +23.0% over the same window), which is what item 18 needs.** **[30-Jul (hk)] TWO CORRECTIONS TO THAT WIDENING.** (1) **XAG REMOVED** — `(fz)` shipped it under `sma_cross` while this file's own reject list, 25 lines above `SLEEVES`, said *"don't re-test: XAG (+1.2% regime / 55% DD cross)"*, naming the very rule it shipped under; an independent 2y measure corroborates 38.7% maxDD. WTI/XCU STAY but are now DECLARED in `SLEEVE_EXEMPT` (their notes quote regime200; they ship as `sma_cross`, untested by that sweep) and owe a Lighter-tape backtest. The list is machine-readable now (`REJECTED_SLEEVES`) and `_selftest_sleeves()` fails the build on an undeclared re-add. (2) **A short series returned a false FLAT** — `sma()` gives None and every rule mapped it to 0, so "no data" was byte-identical to "downtrend" across 7 of 10 sleeves. `want_position` now returns **None** (no entry AND no exit — the catastrophic stop runs ahead of it), and the row publishes `bars` per sleeve. Zero closes here is CORRECT: 3 buys / 0 sells ever, SPY 5.1% from its exit band, and the rule measures 17.2 closes/yr. **[30-Jul (hl)] THE (fz) WIDENING BROKE THE 15% DRAWDOWN BAR AND NOBODY GRADED IT.** Measured through `golive_readiness.stats()` itself, 10y, both lags: 9 sleeves x $100 = maxDD **21.60%/23.88%**, `bar_map` maxdd=False; the pre-(fz) 3-sleeve book passed at 3.45%/4.24%. Fixed by the CLIP (**$100 -> $65**, the largest clearing 15%), because per-trade %% is INVARIANT to clip so it costs zero expectancy — capping concurrency instead would reach 14.85%% only by giving up 79 closes, 58%% of realised P&L and 2.3pp of mean per trade, and because the entry loop iterates SYMBOLS in order with incumbents holding slots it would starve the LAST-listed diversifiers and RAISE correlation. `MAX_OPEN` is now a LITERAL (9): as `len(SYMBOLS)` it could never bind AND it was the one lever `audit_lever_bounds` had to blind itself to via `DRIFT_OK` — where it had already drifted (registry 10 vs code 9). That exemption is deleted. **The single-name class is machine-readable now** (54 symbols in `REJECTED_SLEEVES`) after shipping through the prose three times; NVDA/TSLA/MSTR are GRANDFATHERED in `SLEEVE_EXEMPT`, named FIRST TO DROP, and a fourth turns the build red. Publishes `ref_date` per sleeve — `bars` reads 501-504 whether Yahoo advanced today or froze a fortnight ago. NOT wired to `scout_universe` — its signal is Yahoo equity dailies, so a scout-added book without a verified `YAHOO_REF` publishes nulls. 🏆 Stock Leaders (`equities-momentum{,-lshadow}`) RETIRED 17-Jul — maxDD 37-44% vs the 15% go-live gate |
| pm-{albanese,morrison,turnbull,abbott,rudd,gillard}-lshadow | 🏛️ the Parliament | six-layer self-evolving shadow fleet (21-Jul, operator ask; named for the last 8 Australian PMs — the other two are its organs: Keating 🔭 scanners+ML, Howard 🧠 ecosystem brain). `parliament_main.py` in the freqtrade-bots container; SQLite ecosystem DB on the persist volume; consumes scout stress + L2 veto + brain mults; closes tagged per lens; `PARLIAMENT_ENABLED=0` idles it |

### LIGHTER-ONLY (17-Jul, operator: "i only want things running on lighter")
LIGHTER-FIRST governed SERVICES since 14-Jul, but five rows were still TRADING
elsewhere. All stops are CODE GUARDS, not `railway down` (auto-deploy
resurrects stopped services on every git push). Guards print WHY, keep every
ledger, don't break `--selftest`, and are reversible by env var. Rows are in
BOTH `RETIRED_ROWS` (hides) and `LEGACY_BOTS` (prunes).

**Two different mechanisms — don't conflate them:**
- The four BOTS **IDLE** at boot (`while True: sleep`), never `sys.exit`, because
  `restartPolicy=always` turns an exit into a permanent crash-loop (the Trail
  Blazer pattern, `hyperliquid_momo_bot.py` 15-Jul).
- **funding-carry does NOT idle**: it `raise SystemExit`s unless
  `VENUE=lighter_shadow`. It was pinned `VENUE=hl_paper`, exit-looping LOUD (by
  design — not a silent row that just stops moving) until the operator flipped
  the env var. **[22-Jul (ci): DONE — `railway variables --service
  funding-carry` now reads `VENUE=lighter_shadow`; the row runs its Lighter
  shadow arm and no longer exit-loops. No operator action outstanding.]**

| Row (retired) | File | Was trading | Resurrect with |
|---|---|---|---|
| event-listing-sniper 🎯 Launch Sniper | `listing_sniper.py` | spot on ~100 CCXT exchanges | `LISTING_SNIPER_OVERRIDE=run` |
| scanner-cross-exchange-arb 🔀 Gap Scout | `cross_exchange_arb.py` | arb BETWEEN Kraken/Binance/Coinbase | `GAPSCOUT_RETIRED_OVERRIDE=run` |
| scanner-triangular-arb | `triangular_arb.py` | Kraken | `ARB_RETIRED_OVERRIDE=run` |
| perps-rsi-meanrev 🪃 Bounce Catcher | `hyperliquid_perps_bot.py` | Hyperliquid | `PERPS_RETIRED_OVERRIDE=run` |
| perps-funding-carry 🌾 (HL arm only) | `funding_carry_bot.py` | `VENUE=hl_paper` | ✅ DONE 22-Jul — service now `VENUE=lighter_shadow` |

- **The Launch Sniper was the one nobody switched off.** `lighter_perp_sniper.py`
  was built 9-Jul *"to replace the spot sniper (which can't run on a fixed-market
  perps venue)"* — the replacement shipped, the predecessor kept trading ~100
  CEXes for 8 more days behind a row that was never even hidden.
- **Gap Scout could not be MOVED, only stopped** — its trade was CEX↔CEX arb and
  you cannot arb one venue against itself (its own source: "The CEX legs above
  say nothing about Lighter"). Its Lighter-premium job moved to
  `lighter_market_scout` (every liquid book vs its 6-symbol `LIGHTER_WATCH`);
  `fleet_risk` now mirrors the bus premium from bot_state `lighter-market`.
- **Snap Back COULD be moved and was**: `hl_mids()` → Lighter's own
  `index_price`. Measured 17-Jul: the two agree to a median 3.8 bps (vs a 150 bps
  entry gate) but the index residual is systematically tighter — `book/hl_mid − 1`
  was charging Lighter for Hyperliquid's basis.
- Still non-Lighter and DELIBERATELY kept: `compile_market_data.py` (Binance/
  CoinGecko/Kraken prices for the DASHBOARD's display — not a trader).
- Guards bite on each service's NEXT DEPLOY. `hyperliquid_momo_bot.py`
  (Trail Blazer) was already guarded 15-Jul.

### Intelligence layer (main freqtrade-bots container, run_all.sh loops)
- `lighter_market_scout.py` 🛰️ — ALL ~215 Lighter books: premium stress,
  liquid funding extremes, cross-venue funding divergence, vol/OI moves,
  listings, **per-strategy tickets** → bot_state `lighter-market`.
  **[30-Jul] `TICKET_TOP_N` 6 → 12** — `strategy_tickets` truncates EVERY lens
  to this number, and on the live bus `dip` and `divergence` both returned
  EXACTLY 6 (breakout/momentum returned 5); a lens returning exactly its cap
  is a lens whose cap binds. The lens behind it is the fleet's only measured
  alpha — **RETRACTED: (gi) found a THIRD era-pooling error; the shadow arm's
  10 closes span FOUR bar-sets, and the only clean single-policy sample is the
  LIVE arm's 11 closes at +0.883%/trade, t=+0.73, 95% CI straddling zero. The
  cap-binding fact stands and the widening stands, but the rationale is now
  MORE SAMPLE FOR AN UNDECIDED LENS, not feeding a proven winner** — and
  it was being handed a 6-wide list from which to fill 4 slots. Every "closed
  question" on the Taker (`TT_MAX_OPEN`, `TT_DIV_GAP`, lens on/off, clip size,
  symbol eligibility) was about ALLOCATING that fixed supply; **none was about
  ENLARGING it.** Widening changes no entry bar — the taker's gates still judge
  every ticket. Also publishes **`vols`** (public per-symbol 24h $M), the field
  behind `fleet_bus.scout_universe()`
- **[2026-07-30 THE BRAIN'S FEE BASIS WAS CORRUPTING ITS DIAGNOSES — read
  before touching `FEE_RT`.]** Three defects compounded: (1) `FEE_RT.get(bot,
  ...)` was called with the SUFFIXED row name while every key is a BARE base,
  so not one entry ever matched and every bot took the default — the identical
  defect the 23-Jul audit fixed for `ERA_START`, five lines away in the same
  function; (2) that default, `0.0052`, is **Kraken SPOT** taker round trip,
  and Kraken retired 14-Jul; (3) **Lighter is zero-fee, MEASURED** — all 203
  active books report `taker_fee 0.0000`/`maker_fee 0.0000`. So the phantom
  cost was the whole estimate. **The damage was not a mis-report:**
  `diagnose()` rule 3 fires at `fee_rt/med_loser >= 0.5` with
  `med_loser <= 0.012` and RETURNS, so at 0.0052 ANY bucket whose median loser
  is ≤1.04% was called `fee_bleed` — pre-empting rule 4 `regime_timing`, the
  ONLY diagnosis kind carrying an actuator (`regime_gate`). The brain could
  not recommend the one thing it can act on. **Fixed so it cannot recur:** the
  fee is MEASURED, not asserted — the scout publishes the venue's own schedule
  (`lighter-market.fees`, max across active books) and `bot_learn.fee_rt_for()`
  is the single owner that prefers it. Note `is_taker_fee_enabled` is TRUE on
  every book with the rate at zero, so the rate CAN change and a hardcoded 0.0
  would be this same mistake mirrored; a dark scout falls back to a declared
  per-venue constant, never another venue's. `tests/autonomy/
  test_brain_fee_basis.py` pins the key form, the no-foreign-default rule, the
  rule-3-shadows-rule-4 mechanism, that a REAL fee still earns `fee_bleed`,
  and that a venue fee hike reaches the diagnosis with no code change.
- `bot_learn.py` (brain) — L4 stake multipliers (family bot + strategies
  consume via `fleet_bus.py`), per-bucket DIAGNOSIS (exit/entry/fee/regime/
  venue), venue A/B, scout lens-forward grades (taker veto); generates for
  LIVING bots only (retired set + 7d close recency, 15-Jul).
  **[2026-07-30 (hd)/(hg)/(hh)] `ERA_START` was pooling the 17-Jul accrual-basis
  fix on ELEVEN books, including a REAL-MONEY row.** Its header rule — "hypotheses
  must come from trades taken by the CURRENT code" — is exactly about this, and
  it had no entry for the two funding books and six family/spot books, while the
  six it *did* have were dated 13/14-Jul for STRATEGY changes and so still sat
  BELOW the accrual fix. All are now ≥17-Jul (an era is the LATEST of every
  invalidating change; moving a date forward preserves the earlier reason).
  Also fixed here: `era_epoch_for`'s **THIRD** bug — the double `rsplit` mangles
  `perps-funding-lighter-lshadow` to `perps-funding` because 💸 Farmer is itself
  named after the venue suffix, so a single declaration would have scoped the
  live row and MISSED its shadow twin. Exact-match first, then strip ONE suffix.
  The gate's sample may never be wider than the brain's, and both tables must
  cover the same living accruing set — pinned in both directions. **v3 statistics
  engine (16-Jul, `brain_stats.py`)**: decay-weighted buckets (14d half-life
  forgetting), empirical-Bayes pooling (tag-family → bot → fleet priors),
  Wilson/t evidence bars, regime splits, episode-deduped lens grading (raw
  fields unchanged — consumer contracts held); floors/streaks UNCHANGED;
  reduce-only until 21-Jul, then TWO-WAY (see `brain-stake-mults` below —
  operator-mandated expand, v3-only, mirror bars); validated by `brain_replay.py`
  (ledger no-regression + 6-scenario synthetic discrimination, header has
  the verdict); kill switch `BRAIN_MULT_ENGINE=v2`. **Fast-path (16-Jul
  "no-brainer window")**: EMER_* bars (n≥40, t≤−2.5, post_wr<0.20) skip the
  3-run streak gate on the FIRST qualifying run — latency only, authority
  unchanged; urgent keys surfaced on `brain-vitals`; →
  `learning-brain`, `brain-stake-mults`, `brain-diagnosis`,
  `brain-lens-forward`, `brain-vitals`
- `fleet_risk.py` — traffic light (live > lshadow > paper via
  `authoritative_row`, 65-min staleness filter) + signal bus + **7d fleet
  drawdown governor** (`clip_scale` 1.0/0.5/0.25 — Ticket Taker consumes,
  gate0 advisory) + **exposure view** (`exposure`: effective-bet count via
  1/HHI, per-symbol pileup, crypto/equity split — advisory, 15-Jul);
  long-budget veto ENFORCED in strategies + taker + family bot
  (`FLEET_RISK_MODE=advisory` = kill switch)
- `evidence_board.py` ⚖️ — the evidence organ (15-Jul): scores/corroborates
  fleet-alerts, synthesizes cross-feed items (lens floors, veto flap, venue
  stress, governor proximity), auto-verdicts mechanical items (manual
  `evidence-review` stays senior), phone-notifies warn/action, publishes
  SHADOW restrict-only proposals → `evidence-board` (EVBOARD_MODE=shadow)
  + **GROWTH RAIL (15-Jul user mandate: widening must not need the
  operator)**: EXPAND-direction responses ENACT via `fleet_tuning.py` —
  whitelisted, hard-bounded, TTL'd levers (auto-revert by expiry), lanes in
  `FLEET_TUNING_ENACT_LANES` only (shipped default: paper-scanner +
  lighter-scout/-taker/-xp + **lighter-live**, the 15-Jul user-mandated
  live lane; 16-Jul `AUTHOR_LANES` binds each author — board →
  `live.clip_scale` only, judge → `live.funding.*` only; go-live/keys/
  SafetyRails caps stay operator-only forever). Its first
  loop (Gap Scout census quiet 24/48/96h → widen prefilter/book-budget/
  second-tier venues kucoin/gateio/mexc) is INERT since 17-Jul: Gap Scout is
  retired, so `gapscout-census` never refreshes and the ladder fails safe on
  staleness. That loop widened toward MORE CEXes, so under LIGHTER-ONLY it
  SHOULD be inert — the growth rail now has no active author on that lane.
- `lighter_scout_tuner.py` 🧠🔧 — the Lighter loop's SELF-TUNING organ
  (15-Jul user mandate: the scanner "needs the freedom, with the brain's
  support, to act"). Hourly, stateless, replay-gated: replays the scout
  tape through the taker's REAL code (`lighter_ticket_replay`), widens
  STARVING lenses' taker bars (not-worse both halves), expands
  brain-graded WINNER lenses (must IMPROVE both halves), auto-runs the
  TP/SL/hold sweep (anti-overfit floors: ≥10 closed, +$2 total, both
  halves), widens starving lenses' SCOUT emission bars (grading diet —
  advisory tickets only). Everything lands as bounded TTL'd
  `fleet-tuning` levers (auto-revert); never widens a brain-vetoed lens;
  fail-safe neutral on a dark brain. → bot_state `scout-tuner`
- `fleet_proprioception.py` 🦾 — PROPRIOCEPTION (16-Jul, "advance the
  autonomous organ"): the autonomy stack's sense of its OWN movements —
  the first RETROSPECTIVE grade on growth-rail enactments (every prior
  gate was prospective/in-sample). Tracks every lever EPISODE (open →
  expire/release/value-change; long stances sliced daily) and grades it
  out-of-sample: taker levers get the TRUE replay counterfactual in $
  (during-episode tape, env defaults vs enacted bars through the taker's
  real code), scout diet levers get grading throughput (lens n4h delta),
  gapscout GOT census activity — DEAD since 17-Jul: Gap Scout is retired, so
  the census never refreshes, `census_ok` is False (`fleet_proprioception.py`
  :595) and `grade_gapscout` never runs; that lane grades nothing;
  live/xp episodes are RECORDED only (the
  judge + fade-watch stay the real-money authority). Per-lever verdicts
  helping/hurting/neutral (floors n≥2 episodes, ±$3; HURTING exists only
  on the taker lane — the one lane with a $ counterfactual; joint stances
  share blame, conservative in the restrict direction). CONSUMED BOTH
  WAYS (16-Jul evening, operator: "implement the expanding side ... so
  the July 21 can review both sides"): RESTRICT — the scout tuner refuses
  to re-assert a HURTING lever (`apply_proprioception`); EXPAND — a
  HELPING taker lever unlocks the tuner's improve-both-halves expansion
  walk before the brain's ruling floor (brain veto stays senior), a
  HELPING diet lever walks one notch deeper, a HELPING gapscout lever
  discounts the board's widen-ladder bars (×0.75, 12h floor). **LIVE LANE
  LEARNS (16-Jul evening, operator mandate)**: live episodes graded
  per-trade vs TWO baselines (the books' own pre-window AND the shadow
  twins, same window; clip vs funding split by author so the board's
  movement is never blamed on the judge's; 'bad' only when worse than
  EVERY baseline by the margin; floors higher than shadow lanes) —
  consumed restrict-first: HURTING live.clip_scale releases the board's
  lever + blocks up-steps; HURTING live.funding.* is the judge's EARLIER
  fade signal (`prop_fade`; the judge stays the only writer); the single
  live earn is the clip ladder's TOP step (1.5) now REQUIRING a measured
  HELPING at 1.25 — fail-CLOSED (dark sense = top out of reach). Board
  surfaces 🦾 items (hurting=warn, helping=expand); immune scans the
  payload. Fail-safe both ways on shadow lanes: a dark organ restricts
  nothing AND earns nothing. **CONSUMER SUPPORT (16-Jul late)**: verdicts
  are a first-class bus signal — `fleet_bus.lever_outcome(lever)` is the
  supported accessor for any strategy/bot (standard fail-safe contract),
  `/bus.json` serves the payload + history off-Railway, and the incubator
  consumes it (skips proposing a funding gene whose live lever is
  currently graded hurting — a 7-day judge slot isn't spent re-testing a
  knob the live lane just measured bad). **REAL-MONEY BOTS CONSUME TOO
  (16-Jul late)**: `fleet_tuning.get_lever` reverts a HURTING live-lane
  lever to the operator's env default AT THE CONSUMER, every loop (the
  immune-quarantine central-hook pattern; covers the funding bot's
  `apply_levers` + both live bots' clip via venues) — a measured-bad
  lever stops steering real money immediately instead of waiting out the
  board/judge cycle or the lever TTL; live-lane only (shadow lanes keep
  TTL semantics), fail-safe open, restrict-only by construction. **[23-Jul
  audit CORRECTION: the clip HOOK is wired at the consumer, but
  `live.clip_scale` can NEVER actually receive a `hurting` verdict —
  `fleet_proprioception.grade_live` returns `recorded` for the `live-clip`
  group because the per-trade metric is invariant to clip size — so this
  auto-revert only ever FIRES for `live.funding.*`. The clip's real
  protections are the board's DOWN reflex + lever TTL + the SafetyRails cap.
  "covers ... both live bots' clip" describes the plumbing, not a revert
  that can fire.]** Review grades both sides — agenda item 12.
  → bot_state `fleet-proprioception`
- `experiment_judge.py` 🧪⚖️ — the shadow→live PROMOTION pipeline (15-Jul
  user mandate: shadow wins must "carry across to the real money bots").
  Hourly, ONE candidate at a time on the Funding Farmer's -lshadow twin
  (xp.* levers; while running, the twin is an EXPERIMENT arm, not a
  control arm; every close row stamps extra.bars). Promotion to the live
  arm (live.funding.* — this judge is the ONLY writer) requires the
  PAIRED bar: ≥7d, ≥30 shadow closes, live ≥10, shadow positive in its
  own right AND beats live per-trade by ≥0.5pp on the window AND both
  halves. Fade-watch releases a promotion whose live arm turns negative
  (n≥15). Candidate queue in CANDIDATES (first: enter_apr 0.30 — the
  11-Jul "opt-in, shadow-validate" gate widening). Tide Rider excluded
  (trades too rarely to judge; stays backtest-validated). → bot_state
  `xp-judge`; phase surfaced on the evidence board (🧪)
- `fleet_immune.py` 🛡️ — the IMMUNE + SELF-REPAIR organ (15-Jul, from the
  operator's "what self-repairs / what filters" framing + the same-evening
  incident where a 39h-stale artifact drove a false live down-scale).
  Covers the failure class the death-oriented watchdog misses — ALIVE BUT
  SICK (fresh, in-TTL, trusted, but WRONG). FILTRATION: prunes the
  fleet-alerts bloodstream of age-stale + known-toxic ANTIBODY matches.
  ADAPTIVE IMMUNITY: scans fresh organ payloads for invariant violations,
  QUARANTINES a sick growth-rail lever (`fleet_tuning.get_lever` honors
  `fleet-immune.quarantined_levers` → reverts to operator default), phone-
  pushes NEW sickness. Restrict/clean only; fail-safe (dead immune = no
  quarantine). → bot_state `fleet-immune`; surfaced on the board (🛡️)
  **[2026-07-30 (hh)] IT NOW WATCHES FOR A COMPROMISED LEDGER** — the purest
  alive-but-sick shape there is: a row that is fresh, in-TTL and trusted while
  its `n` is two processes' trades. Reads `golive-readiness.books.<bot>.
  integrity.two_writers` (the PUBLISHER's verdict, never re-derived) and pages
  the operator, because the fix is an OPERATOR action — stop the duplicate
  Railway service — and no guard can un-pool closes two processes already
  wrote. `golive-readiness` had to join the organ's `_keys` fetch list in the
  same commit or the scanner would be inert; `tests/autonomy/
  test_immune_two_writers.py` pins that, and pins that a clean book in the
  SAME payload stays silent (a detector that flags everything trains the
  operator to ignore it).
- `fleet_regen.py` 🩹 — REGENERATION (self-repair tier 2): restores a
  stateful organ the immune organ flagged SICK to its last-good history
  snapshot (age-bounded) or a safe baseline; content-only, carries the
  snapshot's own age so it never asserts old data as current. → `fleet-regen`
- `strategy_incubator.py` 🧬 — REPRODUCTION: breeds strategy GENOTYPES
  (crossover+mutation). Taker offspring scored instantly by replay
  (shadow-only leaderboard); funding offspring PROPOSED to `xp-queue` for the
  experiment judge's identical paired live bar — no offspring shortcuts the
  gate. Recombines within registry bounds only (invention stays human). →
  `strategy-incubator` + `xp-queue`
- `fleet_clock.py` 🕐 — CIRCADIAN: the fleet's shared sense of time (trading
  session, thin-liquidity, heavy-job window). Advisory. → `fleet-clock`
- `implementation_shortfall.py` 📏 — LIVE-vs-SHADOW execution quality: the
  continuous per-trade return gap (live real fills − shadow mark fills) on
  the SAME coins both arms closed, weighted by paired closes, with ENTRY/
  EXIT-slip decomposition (funding bot records fill prices since 15-Jul).
  Verdict clean/live-ahead/live-slipping/insufficient; sustained slip →
  phone. Answers "is the live book slipping, and on entry or exit?". →
  `impl-shortfall`
- **THE EXIT INSTRUMENTS (2026-07-30, (gq)/(gt)/(gx)) — read these before
  touching any TP, SL or max-hold in this fleet.** Entries here have levers, a
  scout, a tuner and a brain; exits had constants, and until (gr) the ledger did
  not even record what an exit did.
  * `scripts/study_exit_attribution.py` — per (book, exit_reason): n, total $,
    mean %, win %, **median hold**. The hold column is the diagnosis: two exits
    on one book with a 6x hold gap are one rule firing before the other can.
    Measured: 🌾 carry earns **+$71.42 on `*_decay_paid`** (hold 65-70h) and
    loses **−$17.32 on the sided `*_flip`s** (hold 6-10h) — and a THIRD unsided
    `flip` bucket is +$7.02, so "flip loses" is true only of the sided ones.
    `*_sl` at a 0% win rate appears on SEVEN living books. RETIRED rows are
    excluded by default: the ledger is history and a Kraken-era book measures
    +$272.09, the largest line in it.
  * `scripts/study_exit_sweep.py` — the counterfactual: replays a book's OWN
    trades under alternative exits against **Lighter's own candles**. Entries
    held CONSTANT (never fitted), THROUGHPUT modelled (sequential, with the
    book's position cap, so a rule that holds longer pays for the entries it
    blocks — carry and Counterweight are both AT their caps, so for them that
    is the whole question). `shipped_rule(book)` reads each book's REAL exit
    from its module — absorbing three hazards that corrupt silently: the taker
    stores `TT_SL` **negative**, Snap Back's exit is in **bps** and the
    sniper's hold in **seconds**, and the sniper's exits are **bare literals no
    lever can reach** (`HARDCODED_EXITS`).
  * **THE CALIBRATION GATE IS THE POINT.** A harness that cannot reproduce what
    DID happen may not say what WOULD have. `calibrate()` compares the replayed
    shipped rule to the book's real ledger mean and **withholds every
    recommendation** beyond tolerance — fail-CLOSED, so no baseline supplied
    means nothing recommended. It passes today only for `pm-gillard-lshadow`
    (replayed −0.158%/trade vs actual −0.110%), because that is the one book
    whose every close carried a price before (gr).
  * **A grid-edge winner is reported UNBOUNDED, never as a value.** On gillard
    every top candidate pins `sl` at whatever maximum the grid allows, so the
    honest output is "widen the grid", not "ship 8%". Widening until a number
    appears is chasing the artifact. The direction IS robust and monotone (sl
    1.0% → −0.158, 1.5% → −0.098, 2.0% → −0.034, 3.0% → +0.050, with drawdown
    FALLING 40.7% → 26.0% because the tight stop was realising the losses), and
    the actor already exists: the Parliament's tuners walk tp/sl/hold
    replay-gated inside `PARAM_BOUNDS`. Two review notes from (gx):
    `PARAM_BOUNDS["sl_pct"]` caps at 0.05 so the sweep's winner is outside what
    the system can express, and the ×1.25 step needs **7.2 consecutive accepted
    widenings** to reach that ceiling while the gain only becomes clear near 3%.
- **EXIT TELEMETRY IS A CONTRACT NOW ((gr), guarded by
  `tests/autonomy/test_exit_telemetry.py`).** `publish_paper_trade` accepted
  `entry_price`/`exit_price` from 17-Jul and **8 of 9 bots never passed them** —
  computed two lines above the call for `pnl_pct`, then dropped. Every exit
  constant in the fleet was unfalsifiable. All nine now record, and the guard
  refuses any bot that holds prices in scope and omits them. **Book-appropriate,
  not uniform**: 🌾 carry is a FUNDING book (P&L is `accrued − fees`), so it
  records `entry_apr`/`exit_apr`/`accrued`/`fees`/`held_h` instead — a price
  sweep measures the wrong thing for it, and `study_exit_sweep` REFUSES funding
  books outright rather than caveating them. **Not retroactive**: the 1,687
  closes that predate (gr) have no prices and never will.
- **A STOP MUST BE RECONCILABLE WITH THE GATE THAT JUDGES IT ((gv),
  `tests/autonomy/test_stop_vs_gate.py`).** The stop is chosen in the bot; the
  15% drawdown bar lives in `golive_readiness.py`; nobody had read them against
  each other. 🌊 Tide Rider 35% = **2.3x the bar**; 📊 Index Rider 15% =
  **exactly at it**, so it is stopped out at the same instant it becomes
  ineligible. Any stop at-or-beyond the bar must be DECLARED with a reason
  (the `BORN_DARK_OK` idiom) — none was moved, because Index Rider has zero
  closes and there is no evidence to set a number against.
- `scripts/golive_readiness.py` 🚦 — the GO-LIVE GRADER, an ORGAN since
  2026-07-30 (gk). Grades every LIVING book against the `(fk)` bar and
  publishes → `golive-readiness` (6-hourly `--publish` loop in `run_all.sh`;
  the ONLY file under `scripts/` that ships in an image). **It had no
  publisher and no schedule until (gk)** — the rule governing real money ran
  only when a human typed the command, so nobody could see that 🌾 carry was
  five of six bars from the gate. Publishes a machine-readable per-bar map
  (`bars` / `BAR_NAMES` = window/closes/mean/t/halves/maxdd) so no consumer
  string-matches prose; `bar_map` is selftest-BOUND to be exactly equivalent
  to `grade` (a `maxDD` that cannot be computed FAILS — fail-closed).
  Rendered as the 🚦 dashboard card (✦ = passes the new bar where the retired
  win-rate rule would have rejected it). PUBLISH-ONLY: promotes nothing,
  writes no lever; go-live stays an explicit operator act.
  **[2026-07-30 (hc)–(hh)] IT NOW OWNS TWO PRECONDITIONS in front of the six
  bars** — `POLICY_ERA` (which sample describes the book) and ledger
  `integrity` (is the sample one book at all). See the GO-LIVE GATE rule below
  for both, including what may and may not reset an era. It is also the ONE
  OWNER of `parse_stamp` / `same_pair_overlaps` / `peak_concurrency`:
  `scripts/audit_ledger_integrity.py` imports THEM, deliberately in that
  direction — the reverse would drag a non-shipped script into the freqtrade
  image's import graph (the born-dark class), and a second copy would let the
  audit and the gate disagree about the same ledger. Payload gained `era`,
  `alltime` (the pooled reading it replaced, so nothing is hidden) and
  `integrity`; `--min-closes` filters on the ALL-TIME count so a demoted book
  shows dark bars instead of vanishing.
- `fleet_respiration.py` 🫁 — RESPIRATION / blood-oxygen: OXYGEN = fresh
  market data; LUNGS = the venue-fetch layer. Measures SpO2 (weighted
  fraction of data feeds breathing fresh) and phone-alerts on a HYPOXIA
  transition — the fleet-wide data-starvation the per-organ watchdog misses.
  → `fleet-respiration`
- `event_sentinel.py` 🗞️⚡ — the EVENT organ (16-Jul user mandate: "be ahead
  of the game" on major world events). market_pulse reads MOOD; the
  sentinel reads discrete typed EVENTS: RSS + GDELT sweep every 10 min →
  keyword taxonomy (monetary tightening/easing, CPI hot/cool, crypto
  crackdown/ETF-adoption, exchange incident, stablecoin stress,
  geopolitical shock, banking stress, AI boom) → severity-gated per-sector
  anticipations from a seeded HISTORICAL PLAYBOOK (COVID, Terra, FTX, SVB
  safe-haven flip, ETF Jan-24, yen-carry Aug-24, tariffs Apr-25) → then
  GRADES its own anticipations at 4h/24h/72h against sector indices
  chained from the scout's marks, and the playbook confidence LEARNS
  (EB blend; a wrong playbook decays toward zero bias — direction never
  auto-flips without review). ~~ADVISORY: zero consumers~~ **[22-Jul: THE
  "ZERO CONSUMERS" CLAIM IS STALE — but it steers a SHADOW book, NOT real
  money.** `fleet-tuning` carries `taker.momo_chg=6.0` and `taker.brk_range=0.97`
  on the `lighter-taker` lane, both stamped
  `reason: "organ-proposal:event-sentinel (replay-gated at this tuner)"`. The
  sentinel proposes; the scout tuner replay-gates and enacts. That is a real
  consumer path — so "advisory, zero consumers" was stale. BUT `lighter-taker`
  is the **$1k SHADOW** lane (`lighter_ticket_taker.py:272` "NOT ON REAL
  MONEY"; only `live.*` levers may steer the live book), so an earlier
  "steering the LIVE taker" note here over-corrected — verified 22-Jul (ci).
  The sentinel has actuator reach into a shadow book; it does not touch real
  money.] Tuning: `evsent.*` levers, lane
  `event-sentinel`. → bot_state `event-sentinel` (+ `-state`)
- `parliament_main.py` 🏛️ — the Parliament's supervisor (21-Jul): six asyncio
  layers in one process — `parliament/` data (Lighter REST+ws ONLY),
  Keating's 10 scanners + 5-model prequential ML ensemble, the six PM shadow
  books, six replay-gated auto-reverting tuners (the scout-tuner doctrine:
  bounds cage, TTL, both-halves floors, hurting-refusal), Howard's brain →
  bot_state `parliament` + `parliament-tuning`. Redis mirror optional
  (`REDIS_URL`); in-process bus is primary. Shadow-only forever until the
  standard go-live gate.
- `fleet_proposals.py` 🗳️ — the organs' PROPOSAL channel to the tuners
  (21-Jul, operator: "the organs need more ability to implement changes to
  forward onto the tuners to act on"). Any organ proposes a bounded change
  to a REGISTERED lever → `tuning-proposals` (locked multi-author merge,
  per-proposal expiry, clamped at write AND read, declared
  direction restrict|expand). Proposals NEVER enact: the scout tuner gates
  each through ITS OWN replay (restrict = not-worse both halves; expand =
  the full winner bar, brain veto senior, ≤3/cycle, provenance
  `organ-proposal:<author>`), and the judge treats a fresh restrict proposal
  on a promoted live lever as a third release path (`proposal_fade`,
  restrict-only; judge stays the only live.funding.* writer). First
  proposers: event sentinel (risk-off crouch / graded-playbook expand),
  impl-shortfall (sustained slip → live.funding.enter_apr restrict),
  respiration (confirmed hypoxia → crouch). The sentinel's own
  `event-sentinel` lane is now enactable + author-bound (detection
  sensitivity only — it was registered but UNREACHABLE since 16-Jul).
  Fail-safe: dark channel proposes nothing, consumers ignore stale/junk.
  → bot_state `tuning-proposals` (+ /bus.json, 🗳️ Autonomy-card row)
- `regime_oracle.py`, `market_pulse.py` (history appends every 30 min, 15-Jul),
  `cleanup_legacy_bots.py` (boot prune of retired rows)

### RETIRED (rows hidden + pruned; ledgers kept)
Kraken paper 8 (spot 4 + family 4, 14-Jul user cut — Kraken/laptop
processes are operator-stopped), equities-momentum-alpaca +
equities-regime-ibkr (14-Jul), Trail Blazer, Bounce Catcher, Two-Way Tide,
Loop Scout, trendmomo-4h (12/13-Jul).

**17-Jul LIGHTER-ONLY cut** (operator: "i only want things running on lighter"):
`event-listing-sniper` (🎯 Launch Sniper), `scanner-cross-exchange-arb`
(🔀 Gap Scout), `perps-funding-carry` (🌾 Yield Harvester's HL-DATA arm — its
`-lshadow` twin CONTINUES and is deliberately NOT retired). `scanner-triangular-arb`
and `perps-rsi-meanrev` were already-hidden rows whose SERVICES kept running;
they now have guards too. Per-row stop mechanism + resurrect switch: see the
LIGHTER-ONLY table above — not restated here.

**Also 17-Jul**: `crypto-trend-daily-lighter` (🌊 Tide Rider's LIVE row — 🎫
Ticket Taker took the same service/keys/sub-account; retiring it is REQUIRED,
not cosmetic: both rows reported the same $34.67 and the fleet total
double-counted real money), `equities-momentum{,-lshadow}` (🏆 Stock Leaders —
maxDD 37-44% vs the 15% go-live gate).

A retirement needs BOTH halves: `RETIRED_ROWS` in pnl_dashboard.py (hides the
card) AND `LEGACY_BOTS` in cleanup_legacy_bots.py (prunes the frozen row).
Doing one hides your own omission.

### Read-only endpoints (no auth)
`/pnl.json` `/trades.json` (`?source=paper` for the paper_trades ledger)
`/bus.json` (risk light + signal bus + brain keys + lighter-market +
fleet-proprioception + **golive-readiness** (30-Jul (gk) — the go-live bars
per book, live AND `?hours=` history, so a review seat with no Railway login
can read the gate that governs real money), `?hours=` history)
`/pulse.json` `/disloc.json` `/watchdog.json`

### 15-Jul reconciliation (this repo's git now matches what runs)
The 14-Jul pivot shipped from branch `claude/gapscout-profitable-trades-ebrprj`
via PRs #40-44 to MAIN while the Lighter services deploy from GATE0 — the two
lines are now cross-merged (15 Jul) and `recovery/freqtrade-bots-image-20260715`
snapshots the exact deployed freqtrade-bots image. Operator actions done 15 Jul:
family Kraken Railway services stopped, Alpaca cron (`trading-bot` service,
project trading-bot) torn down. equities-regime-ibkr's publisher runs on an
UNIDENTIFIED host (not this repo, not ~/Claude/Trading, no local process) —
its row is dashboard-retired regardless; stop the process when found.

## Dashboard
- **File:** `pnl_dashboard.py` — Postgres-backed, auto-refreshes every 30s
- **DB:** Each bot publishes to `bot_pnl` table via `bot_pnl_store.py`
- **Auth:** DASH_USER / DASH_PASS env vars on Railway

## Key Files
- `pnl_dashboard.py` — main dashboard server (+ fleet_watchdog_svc.py)
- `bot_pnl_store.py` — shared Postgres publisher (all bots import this)
- `lighter_market_scout.py` / `lighter_ticket_taker.py` — scout + its trader
- `bot_learn.py` + `fleet_bus.py` — brain and the strategies' read client
- `fleet_risk.py` / `regime_oracle.py` / `market_pulse.py` — shared organs
- `lighter_ticket_replay.py` — replay the recorded scout tape through the
  taker's real code (rule changes judged in seconds, not shadow-days)
- `parliament_main.py` + `parliament/` — 🏛️ the six-layer PM shadow fleet
  (see intelligence layer); ecosystem DB at `/freqtrade/persist/parliament.db`
- `venues/safety.py` — SafetyRails (kill switch, notional caps, daily-loss halt)
  **+ `open_notional()`**: the fleet's ONE answer to "how much is really
  deployed?" — sum each held position at ITS OWN entry clip, never
  `count * current_clip` (that estimate breaches the cap when the growth rail
  moves the clip). Imported by BOTH live bots + the taker + the sniper.
- `cross_exchange_arb.py` — Gap Scout, **RETIRED 17-Jul** (CEX↔CEX arb, no
  Lighter leg); idles at boot
- `funding_carry_bot.py` — Yield Harvester; `lighter_shadow` ONLY since 17-Jul
  (the HL-data arm is retired; the hedge-less refusal is unchanged and senior)
- `user_data/` — Freqtrade strategies/configs (dormant post-Kraken; the
  gate0 family bot re-expresses them on Lighter)
- gate0 branch (`claude/lighter-gate0`) — the Lighter runtime (venues/,
  ShadowBroker, lighter_family_bot.py); its services deploy from there

## Cross-Bot Intelligence (bot_state keys — since 2026-07-14 CONSUMED, not just published)
- `brain-stake-mults` — bot_learn's L4 per-(bot, enter_tag) stake
  multipliers. **TWO-WAY since 21-Jul (operator: "brain needs to be able to
  widen too")** — reduce (0.5/0.75, floors n≥30 era trades / 3 consecutive
  runs, unchanged since 14-Jul) AND expand (1.25/1.5 on the v3 MIRROR bars:
  Wilson LOWER bound, t ≥ +2.0/+2.5, full n floor only, no family-praise
  inheritance, no urgent fast-path — `brain_stats.EXP_*`; same 3-run streak
  gate). Expand is v3-ONLY (`BRAIN_MULT_ENGINE=v2` zeroes it) with its own
  kill switch `BRAIN_MULT_EXPAND=off`; consumers clamp [0.5, **1.5**]
  (`fleet_bus.MULT_CEIL` — was 1.0; deliberate documented-contract scope
  expansion, CHANGELOG (bh)). Payload stamps `mode: two-way|reduce-only`.
  Consumers: `lighter_family_bot.py` at entry (keyed `<bot_id>` +
  `long-<tag hyphenated>`, 15-Jul) and the freqtrade strategies'
  `custom_stake_amount` — both via `fleet_bus.py`; SHADOW books only, no
  live bot reads mults.
- `fleet-risk` — L2 traffic light, mode **enforce**: strategies veto NEW long
  entries at long-budget (20). Kill switch: `FLEET_RISK_MODE=advisory`.
- `signal-bus`, `regime-oracle`, `market-pulse` — published context (funding
  APRs, venue premium, per-major regime, news mood). Only market-pulse.panic +
  the two keys above are consumed.
  **`listing-intel` is DARK since 17-Jul**: its ONLY publisher was
  `listing_sniper.py:1148`, which now idles behind the LIGHTER-ONLY guard
  (`listing_intel.py` is a pure library and publishes nothing). The key will
  simply go stale — consumers fail-safe on absence, per the bus contract.
  [17-Jul] The bus's Lighter premium (`lighter_prem_bps`,
  `lighter_venue_stress_bps`) now comes from the market scout's
  `lighter-market` — every liquid book, and the SAME number the Ticket Taker's
  stress veto reads — instead of retired Gap Scout's 6-symbol watchlist.
  DROPPED with their scanners: `xexchange_dislocation_pct`,
  `tri_arb_best_depth_pct` (CEX gauges; nothing outside fleet_risk read them).
  `fleet_risk.state_fresh()` honours a bot_state payload's own `updated`+
  `ttl_sec` and fails CLOSED (`row_fresh()` is for bot_pnl rows only).
- `fleet-tuning` — the growth rail's lever payload (authors: evidence board
  + scout tuner, MERGED writes with per-lever expiry; `fleet_tuning.py`
  registry clamps; consumers: Lighter Scout, Ticket Taker — Gap Scout was one
  until it retired 17-Jul, so the `paper-scanner` lane now has no consumer).
  Lanes: paper-scanner (INERT — Gap Scout retired) / lighter-scout /
  lighter-taker / lighter-xp (zero
  real money) + lighter-live (`live.clip_scale` + the judge's PROMOTED
  `live.funding.*` — see growth rail + experiment judge above)
  + **lighter-books (2026-07-30)**.
  **[2026-07-30 THE SHADOW BOOKS GOT LEVERS — operator: "every bot needs every
  tool at its disposal and every bot needs the ability to grow".** Six books
  had ZERO registered levers, so the growth rail could not move a single knob
  on any of them — including `carry.enter_apr`, the best-performing gate in
  the fleet (+$56.20, n=80, t=2.42). "The ability to grow" is registry
  membership PLUS a consumer that reads it; they had neither. New lane
  `lighter-books` (author: evidence board only; the board gains NO new reach
  into real money): `carry.enter_apr` / `carry.max_positions` /
  `fundspread.k` / `fundspread.universe_n` / `disloc.enter_pct` /
  `disloc.universe_n` / `index.max_open` / `trend.rank_by_funding` /
  `sniper.surge_mult`. Every one is consumed by an `apply_tuning()` in its
  bot, called each loop, tested in `tests/autonomy/test_book_levers.py` —
  the registered-but-inert lever is the failure mode that tier exists to
  prevent.
  **[2026-07-30 (gu)] `disloc.exit_bps` — THE FLEET'S FIRST EXIT LEVER.** All
  nine above are ENTRY or CAPACITY: the rail could move what every book OPENS
  and nothing about what it CLOSES. Chosen first for a measured reason — Snap
  Back's exit target THROTTLES ITS OWN ENTRY, because (fz)'s adaptive entry gate
  is floored at `EXIT_BPS * ENTER_FLOOR_MULT` = 40 × 1.5 = **60bps**, above the
  **p90 (21.8bps)** of the residual distribution it adapts to (median 7.9, max
  50.1 across 90 liquid books). So the adaptation could only descend to a bound
  set by a stale exit constant. Cage **[8.0, 40.0]** is DERIVED from that
  measurement — `lo` ≈ the live median, `hi` = the operator's current default,
  so the rail may only loosen the exit TOWARD the tape and never tighten past
  today's setting. Default UNCHANGED at 40.0: registering a lever moves nothing.
  Consumed in `apply_tuning` **and** present in `_ENV_DEFAULTS` — the second is
  load-bearing, because `_ENV_DEFAULTS[attr]` raises a KeyError that the loop's
  own `except` swallows, leaving a lever that looks consumed and never moves. Kill switch: drop `lighter-books` from `FLEET_TUNING_ENACT_LANES`
  and every consumer reverts to its env default on the next read. Also new:
  `xp.funding.min_vol` / `live.funding.min_vol` (the Farmer's liquidity floor,
  judge-promotable — the $10M floor excluded 5 of the venue's 8 most extreme
  funding books).]
  `gapscout-census` — Gap Scout's epoch-2 episode census; STALE FOREVER since
  17-Jul (bot retired), board's `quiet_hours` ladder fails safe on it. `scout-tuner` — the tuner's cycle log + enactments.
  `fleet-proprioception` — per-lever enactment outcome grades (episodes +
  helping/hurting verdicts). Consumers: scout tuner (hurting-skip +
  helping-walk), board (🦾 items + live clip gates + gapscout ladder
  discount), judge (early fade), incubator (hurting-gene skip), anything
  else via `fleet_bus.lever_outcome` / `/bus.json`.
- **`fleet_bus.scout_universe()` / `.scout_funding()` / `.venue_stress_bps()`
  (2026-07-30)** — the ONE supported read of the venue's live universe, its
  funding map and its premium stress, off the scout's `lighter-market` key.
  Built because **four LIVING books** carried hand-typed watchlists written when
  Lighter was much smaller: Counterweight ranked **30 of 202 books**, Snap Back
  16, Tide Rider 6, Index Rider 3. (This said "five" and named four — the fifth
  was retired Gap Scout's 6-symbol `LIGHTER_WATCH` in `cross_exchange_arb.py`,
  which cannot be widened because the bot idles behind the LIGHTER-ONLY guard.
  Corrected (gz): a count that does not match its own list sends the next reader
  hunting a book that is not there.)
  **[2026-07-30 (hk) — THE COUNT WAS THE SMALLER ERROR. Only TWO of the four
  named books ever had a CONSUMER.** `lighter_dislocation_bot` and
  `lighter_funding_spread_bot` shipped; `lighter_trend_bot` had no `fleet_bus`
  import and `Dockerfile.trendlighter` did not COPY it, and `lighter_index_bot`
  reads Yahoo equity dailies rather than the scout. So the two books this claim
  was supposed to help were exactly the two it skipped — and they are the fleet's
  only two with ZERO closed trades. (hk) wires Tide Rider (measured 6 -> 16 on
  the live bus, plus `scan_universe`'s held-coin orphan rule as its
  prerequisite). Index Rider is still NOT wired: a scout-added book with no
  verified `YAHOO_REF` mapping publishes nulls behind a log warning, so its
  widening is a separate job.]**
  A ranked selector cannot pick a winner it never sees. `scout_universe` reads the scout's new public `vols` map and falls back
  to its private `_marks` diff base, so a consumer shipped ahead of the scout's
  next deploy is not dark in the meantime. CONTRACT: any doubt returns
  `[]`/`{}`/`None`, and **every caller must read empty as "keep my configured
  list", never as "trade nothing"** — the widening is an enhancement, never a
  dependency, and no organ outage may shrink a book's universe.
  **[2026-07-30 (gy) MEASURED: only TWO of the four books named above actually
  call it.** ⚖️ Counterweight and 🧲 Snap Back do (live caps confirm universe 51
  and 39). 📊 Index Rider does NOT — its 3 → 10 came from a deliberate static
  list of the venue's non-crypto set, which is correct for it. **🌊 Tide Rider
  does NOT, and its live caps still read `universe: 6`** — the hardcoded
  `TREND_COINS` default. It gained `rank_by_funding` and nothing else, so this
  paragraph overstated the coverage.
  **AND WIDENING IT IS CONTRAINDICATED, not a to-do.** Tide Rider has ZERO
  closed trades, no time bound, and a 35% catastrophic stop as its only price
  exit ((gv)). Handing a book that cannot EXIT more positions to ENTER is
  strictly worse — the fleet already ran that configuration once: 🏆 Stock
  Leaders, 3 closes all via `long_catastrophic_stop`, −$91.90, retired at maxDD
  37-44%. Fix the exit first; the universe is not the binding constraint.]**
- Every payload carries `updated`+`ttl_sec`; consumers go NEUTRAL on stale
  data (`fleet_bus.is_fresh`). Backtests are inert (no DATABASE_URL).
- Bot identity for multiplier lookup = `bot_name` in each freqtrade config
  (= dashboard bot ID — keep them matching).

## How Bots Publish to Dashboard
Each bot calls `bot_pnl_store.publish(...)` with:
```python
{
  "bot": "freqtrade-mum",          # bot ID — must match CURRENT_BOTS in dashboard
  "status": "running",
  "equity": 1023.50,
  "pnl_abs": 23.50,
  "pnl_pct": 0.0235,
  "closed_trades": 12,
  "open_trades": 2,
  "wins": 8,
  "losses": 4,
  "pnl_daily": 5.20,               # optional — today's P&L
  "extra": {...},                  # optional — JSON-able context dict
}
```
**[2026-07-28 doc-truth]** That is the COMPLETE accepted set — `publish()`
takes exactly `(bot, status, equity, pnl_abs, pnl_pct, open_trades,
closed_trades, wins, losses, extra, pnl_daily)` and has no `**kwargs`. This
block used to also list `pnl_weekly/pnl_monthly/max_drawdown/best_trade/
worst_trade`; a bot following that doc raised `TypeError` AT THE CALL SITE
in its trading loop (outside publish's never-raise guard). If those fields
are ever wanted, extend `publish()` + `ALTER TABLE` first, then this doc.

## Freqtrade Bot Configs (new bots)
All new bots:
- `dry_run: true`
- `dry_run_wallet: 1000`
- API server enabled on ports 8080–8083
- Logs to `logs/freqtrade.log`
- SQLite DB at `logs/tradesv3.sqlite`

## Claude Code Instructions
- Ask Claude to backtest any bot: `freqtrade backtesting --config <bot>/config.json --strategy <Name>`
- Ask Claude to tune via Hyperopt: `freqtrade hyperopt --config <bot>/config.json --strategy <Name> --hyperopt-loss SharpeHyperOptLoss`
- Ask Claude to check logs: `tail -f <bot>/logs/freqtrade.log`
- Ask Claude to deploy: **a push is NOT a deploy** — see Railway Setup below.

## Railway Setup
- Each bot is a separate Railway service
- All services share the same Postgres plugin via DATABASE_URL
- **DEPLOY TRIGGER — "push to main → Railway auto-deploys" is FALSE, and was
  false for both real-money bots (MEASURED 17-Jul, commit 259e3b4: not one
  of the 12 services is git-connected — `railway variables` returns zero
  `RAILWAY_GIT_*` keys on every one).** The ONLY automated path is
  `.github/workflows/railway-redeploy.yml`, which runs `railway up` for a
  **hardcoded `paths:` list** covering exactly three services:
  freqtrade-bots (`user_data/**`, `Dockerfile.freqtrade`, `run_all.sh`),
  pnl-dashboard (`pnl_dashboard.py`, `report_emailer.py`,
  `compile_market_data.py`, `Dockerfile.dashboard`), funding-carry
  (`funding_carry_bot.py`, `Dockerfile.funding`), plus shared
  `bot_pnl_store.py` / `freqtrade_pnl_poller.py` / `market_pulse.py`.
  **Anything not on that list ships only when a human runs `railway up`** —
  `fleet_tuning`, `funding_basis`, and the LIVE Funding Farmer
  (`lighter_funding_bot.py`). The RETIRED HL funding-carry arm auto-deploys;
  the LIVE Funding Farmer does not.
  **[2026-07-30 THE SHADOW BOTS GET AUTO-DEPLOY — operator: "find and implement
  whatever auto deploys necessary so that changes can be implemented in real
  time".** Six services had NO deploy rule at all — `lighter_dislocation_bot`,
  `lighter_funding_spread_bot`, `lighter_index_bot`, `lighter_perp_sniper`,
  `lighter_trend_bot`, `lighter_family_bot` — so every change to them shipped
  only when a human remembered `railway up`. That silently applied to the (fz)
  offense pass itself: its levers, widened universes and adaptive gate would
  have sat in main, green, and reached no container. They now have `paths:`
  entries AND service greps, including the SHARED modules each image carries
  (`bot_pnl_store`, `paper_broker`, `venues/`, `fleet_tuning`, `fleet_bus`,
  `funding_basis`). **Their exact Railway service names could NOT be verified
  from this repo** (the only names recorded anywhere are funding-carry,
  pnl-dashboard, market-context and the two live bots), so the deploy step now
  RESOLVES each target against `railway service list` and reports an
  unresolvable name as a loud ::warning:: instead of red-failing the build.
  **[2026-07-30 (gl) — CHECKED, and FOUR of the six names were WRONG.** Run
  `30492918936` deployed only `equities-regime-shadow` + `family-lighter-shadow`
  and warned UNRESOLVED on the rest, so the levers `(fz)` registered for those
  four books reached NO container. Railway's names follow the **emoji
  nickname**, not the dashboard row id: `snap-back-shadow` 🧲,
  `counterweight-shadow` ⚖️, `perp-sniper-shadow` 🎯,
  `tide-rider-lighter-shadow` 🌊. Fixed, and `audit_deploy_coverage.py` now
  carries all six in `AUTO_IMAGES` (it was green throughout because it checked
  no rule for any of them, and because its parser could not read a
  `$_shared`-interpolating grep at all — both fixed). LESSON: **a guard whose
  only output is a ::warning:: on a passing run is not a guard** — a green
  build with a warning is indistinguishable from a green build. STILL
  **[2026-07-30 (gn) — "deploy both" was WRONG and is REVERTED.** A
  `yield-harvester-shadow` service exists beside `funding-carry` and this repo
  cannot tell which publishes `perps-funding-carry-lshadow`. `(gl)` deployed
  BOTH on the argument that "neither has a volume, so a redundant redeploy is
  cheap". **The volume was never the risk: both publish the SAME bot_pnl row**,
  so they are two writers of one key and the row is whoever published last.
  Measured six minutes after the dispatch woke the second: n=82 with
  `extra.caps` → **n=71, caps=None, build=None**. `funding_carry_bot.py` emits
  `caps` unconditionally, so caps=None proves the winner is not running HEAD.
  ~~The paper LEDGER is CLEAN (82 closes, zero duplicate trade_ids) so the
  go-live grade and the baseline are intact — the casualty is the summary row.~~
  **[2026-07-30 (hf) — THAT SENTENCE WAS WRONG, and the check behind it could
  not have shown what it was used to show.** Two independent processes open at
  different moments, so their `trade_id`s (`{coin}:{opened_ts}`) never collide —
  a duplicate-id scan is blind to duplicate WRITERS by construction. The
  detector that works: a carry process keys `positions` by coin and enters only
  `if c not in positions`, so **one process cannot hold two positions in the
  same coin**. Measured across all 28 books / 1,706 episodes, same-pair
  overlapping holds appear in exactly TWO — `perps-funding-carry-lshadow`
  (7 overlaps, deepest **9.14h** on HYPE) and retired `event-listing-sniper`
  (a pair-naming collision across ~100 CEXes, declared). Every other book reads
  zero. Second, independent line: that ledger reaches **10 concurrent positions
  on 27 occasions** while its own `MAX_POSITIONS` was **8** until 30-Jul. And
  the STATE key is shared too — the bot persists `positions` to
  `bot_state[bot_id]` and restores at boot, so two processes clobber one
  position map and a single logical position can be closed by both. **So the
  casualty is not just the summary row: the graded LEDGER is not one book's
  record, and `t` scales with sqrt(n).** Guarded by
  `scripts/audit_ledger_integrity.py` (registered selftest; exits non-zero on a
  LIVING two-writer book).]**
  **OPERATOR ACTION OUTSTANDING — now more than cosmetic: one of the two
  services must be STOPPED in Railway**; a deploy rule cannot fix a duplicate
  that is already running, a guard cannot un-pool closes two processes already
  wrote, and every grade over this window inherits the pooling. Lesson: a
  duplicate PUBLISHER is not a duplicate DEPLOY — ask "do they share a key?",
  not "is redeploying cheap?" — and when you check whether a shared key did
  damage, pick a test that COULD detect the damage.]**
  **[2026-07-22 CORRECTION — this paragraph was WRONG about two of them.]** The
  `paths:` filter DOES carry `lighter_ticket_taker.py`, `lighter_ticket_replay.py`,
  `venues/**` and most of the intelligence layer (`lighter_market_scout`,
  `lighter_scout_tuner`, `fleet_*`, `bot_learn`, `brain_stats`, `evidence_board`,
  `experiment_judge`, `strategy_incubator`, `event_sentinel`, `regime_oracle`,
  `implementation_shortfall`, `parliament/`) — verified against the workflow file,
  not inferred. What is manual is the *service*, not the *file*: those paths
  deploy **freqtrade-bots** (where the SHADOW taker and the organs run), while the
  two REAL-MONEY services — `trail-blazer-live` (= the Farmer; service names lie)
  and `tide-rider-lighter-live` (= the Ticket Taker) — are on NO auto path and
  need an explicit dispatch:
  `gh workflow run 305025607 -f services="trail-blazer-live,tide-rider-lighter-live"`
  (address it by workflow ID — the filename form did not resolve in this repo).
  Then MARKER-GREP both containers; a green run has never implied a container took it.
  **[2026-07-29 CORRECTION — the auto-deploy surface has since GROWN in three
  ways this paragraph pre-dates; verified against the workflow at HEAD.]**
  (1) The workflow auto-deploys **FOUR** services, not three — `market-context`
  gained a deploy rule 17-Jul — and the pnl-dashboard path list also carries
  `fleet_watchdog_svc.py`. (2) `fleet_tuning.py`, `funding_basis.py` and
  `lighter_funding_bot.py` are ALL on `paths:` now — the "ships only when a
  human runs `railway up`" list above is empty today. (3) The two REAL-MONEY
  services are no longer dispatch-only: since 24/25-Jul a push whose commit
  message carries **`[deploy-live-taker]` / `[deploy-live-farmer]` /
  `[deploy-live]`** AND touches that live image's own files auto-deploys that
  live service from clean main (no marker → shadow only, exactly as before).
  The dispatch command above still works and remains the no-marker route.
  Verify a live deploy landed by the bot_pnl `extra.build` stamp: it is a
  content hash — recompute locally with
  `python3 -c "import bot_pnl_store as b; print(b.build_compute('<entry>.py'))"`
  and compare to the row (how the 29-Jul audit proved both live containers
  ran 633e8a1 without container access).
  **[2026-07-29 (fd) — READ THE COUNT, NOT JUST THE DIGEST.** `build_compute`
  returns `(id, n_files)` and hashes only the `_BUILD_SHARED` names that
  EXIST, so the SAME tree stamps different ids in images carrying different
  subsets. Measured the day `fleet_tuning.py` joined the set: the family
  image never COPYs it (deliberate — the clip lever must not size a shadow
  book), so a converged `family-lighter-shadow` published `74d3b3178fa8`
  over 14 files while the repo computed `6de64508c304` over 15 — and the
  repo-side prediction read as "the deploy never landed". Rows now publish
  `extra.build_n` beside `extra.build`: **compare BOTH**, and when they
  disagree check `n` first — a different count means a different FILE SET,
  not drifted code. To predict an image's id, compute against that image's
  own COPY set (see its `Dockerfile.*`), not the repo tree. The born-dark
  guard cannot catch this class: these are DATA dependencies of the stamp,
  not imports.] `audit_deploy_coverage` now also
  cross-checks the live marker greps against `paths:` (the 28-Jul grep
  widening added files the paths: block didn't carry — a marker push touching
  only those deployed nothing, invisibly to the then-guard).
  **What it cost:** six fill-telemetry commits landed 04:27→10:52 UTC 17-Jul;
  the funding container booted 04:34 and picked up NONE of them — 58 real
  orders, 0 measured fills. The code was right and was never running. This is
  the mechanism behind every "frozen service" incident.
  **[2026-07-30 (gm) A ROUTING FIX CANNOT DEPLOY ITSELF.** `(gl)` corrected
  four service names; the merge run reported `Deployed: freqtrade-bots,
  pnl-dashboard` and the four corrected rules stayed SILENT, because the decide
  step fires on CHANGED FILES and that commit touched no bot file and nothing in
  `$_shared`. The rule was right and nothing rang the bell — a distinct failure
  from a wrong name. This workflow file is now part of the SIX shadow books' own
  trigger set (both `paths:` and their decide greps), so a routing fix redeploys
  the services it routes to. Scoped to those six on purpose: no volumes, nothing
  to lose, and they are the ones whose names were unverified. `freqtrade-bots`
  and the two LIVE services are EXCLUDED — the live pair stays marker-gated,
  because an unmarked WIP push must never ship real money. After ANY routing
  change to a service outside those six, dispatch it explicitly; the structural
  fix only helps the NEXT one.]**
  Check before you claim a fix is live: `scripts/audit_deploy_coverage.py`
  (does a path have ANY deploy route?), then marker-grep the RUNNING
  container — the only proof a deploy landed ([[railway-cli-frozen-services]]).
  Deploy live from a CLEAN worktree: `railway up` uploads your DESK, WIP and
  all ([[deploy-live-from-a-clean-worktree]]).
- Dashboard service: `pnl-dashboard`

## Rules
- **GROWTH FINDINGS ARE IMPLEMENTED, NOT FILED (operator rule, 30-Jul (hn)).**
  *"A new rule must be implemented that if we find something that moves us
  forward in progression and growth, it can implement."* Context: *"the whole
  premise upon the fleet's inception is GROWTH, not staleness and circles"* and
  *"otherwise we are just reverting every day and wasting time and money."*
  So a finding that moves the fleet forward is **acted on in the same session**,
  not recorded as a follow-up for a later pass. This is a standing
  authorisation, and it is deliberately routed by WHAT the finding is — the
  routing is what keeps "implement immediately" from ever meaning "an
  autonomous run changed a live bot":
  | Finding | Action |
  |---|---|
  | **Correctness / measurement** — a bar on the wrong basis, a stale copy of a rule, a grader reading the wrong field, a guard that cannot fire, a counter that disagrees with itself | **Implement now**, with a test that names the incident, mutation-verified. This is where essentially every real-money benefit has actually come from. |
  | **Tooling, review, guard, observability** | **Implement now**, same standard. |
  | **A bounded lever on a shadow lane** the evidence supports | Route through the designed channel — `fleet_proposals.py` → the scout tuner's replay gate (bounded, TTL'd, auto-reverting, brain veto senior). Never hand-set a lever. |
  | **Real money** — `live.*` levers, clips, `dry_run`, keys, go-live, a Railway service | **Do NOT apply.** Escalate with the exact command/lever and the decision named. Unchanged: go-live is an explicit operator act, and *never modify bot logic without backtesting first*. |
  **A correctness fix that changes which book gets real money IS a real-money
  benefit delivered** — it arrives as better evidence rather than a bigger
  position. Two corollaries learned the same day: a **refusal with evidence is a
  valid output** ((hl) killed 25 of 30 throughput candidates because the gain was
  turnover bought with expectancy), and **never add anything that inhibits the
  fleet** — an untested rewrite of an enforcement authority is not growth, so a
  change that alters which trades books take still earns its replay evidence
  first. Growth is not a licence to skip measurement; it is a ban on sitting on
  a measured win.
- **THE LIVE-DEPLOY MARKER LIVES IN THE COMMIT SUBJECT, AND MENTIONING IT IN A
  BODY USED TO DEPLOY REAL MONEY (30-Jul (hj)).** The gate read `git log
  --format='%B'`, so a commit whose body said *"NOT deployed to the live taker:
  no `[deploy-live-taker]` marker"* matched and redeployed
  `tide-rider-lighter-live`. It now reads `--format='%s'` (subjects only), and
  `audit_deploy_coverage.marker_source_ok()` fails the build if that ever
  reverts. **Never write a marker string in a commit body, even to negate it** —
  a subject mention still fires, by design (a subject is a deliberate
  statement, not prose). Verify a live deploy by the `extra.build` +
  `extra.build_n` stamp, never by the green run.
- **GRADE A DIRECTIONAL BOOK AGAINST A RANDOM-ENTRY BENCHMARK, NEVER AGAINST
  ZERO (30-Jul (hm)).** On this venue a random short earns +0.2% to +1.1%/trade
  for free. Measured on the Ticket Taker: random entries on the LENS'S OWN
  COINS, same window, same bracket, through the taker's own `exit_reason` over
  real tape, BEAT the lens — six independent runs put P(coin flip >= taker) at
  0.55–0.84. A positive mean is not an edge on a trending tape. The
  cross-section is already in the scout's `marks`; publish a beta-stripped
  excess beside every lens grade.
- **A `_tp` THAT BOOKS A LOSS IS A PRICE-BASIS BUG, NOT A ROUNDING ERROR
  (30-Jul (hm)).** `exit_reason(entry, mark)` was fed `entry` = the broker's
  book-WALKED fill and `mark` = the venue's `mark_price`, while the P&L booked
  off a re-walk of the book. On BOT/USDC the mark sat 747.6 bps from its own
  book top, so a short was born +7.5% in profit ON THE MARK BASIS, tripped `tp`
  next cycle, and closed at a loss — 43 times in 4.5 hours, 42 of them with
  `close[i] == open[i+1]` to the second. **One episode, not 43 trades**, and it
  poisoned 45 of 98 rows in every pooled grade for nine days.
  `lighter_ticket_taker` now asserts the invariant at the ledger write and
  stamps `extra.basis_contradiction`. **When an exit label and the P&L sign
  disagree, suspect two price bases before you suspect funding.**
- **THE 30-DAY GO-LIVE CLOCK RESTARTS ON EVERY POLICY CHANGE (30-Jul (hm)).**
  The Ticket Taker changed policy on 24-Jul, 29-Jul and 30-Jul, so despite
  n=30 arriving ~7-Aug its earliest gradeable date is **~29-Aug**. A book whose
  bracket is being tuned cannot accumulate a single-policy sample: 137 shadow
  closes produced ZERO gradeable ones because the scout tuner moved the bracket
  ~20 times in a fortnight. If a book needs grading, FREEZE ITS BARS FIRST.
- **THE GO-LIVE DRAWDOWN BAR READS REALISED P&L ONLY — IT CANNOT SEE AN OPEN
  DRAWDOWN (30-Jul (hl)).** `golive_readiness.stats()` accumulates closed
  trades, so for a book that HOLDS most of the time most of its drawdown is
  invisible to the rule that governs real money. Measured on 📊 Index Rider
  (long 64% of days): all four stop x lag cells PASS on realised DD 9.9-10.7%
  while true MTM DD is 15.6-17.4% — the two definitions disagree about the
  VERDICT. `bot_pnl_store.snapshot_equity()` now appends an MTM sample to
  `bot_state_history` under `<bot>:equity` (both riders wired). **The grader is
  DELIBERATELY unchanged** — there is no history yet, and grading against an
  empty series fails open or closed, both wrong. After ~30 days: publish the
  MTM number BESIDE the realised one, and **re-grade 🌾 carry first** — it is
  five of six bars from go-live, so a stricter drawdown definition lands on it
  before anyone else.
- **AN ENTRY IN `DRIFT_OK` IS A HOLE IN THE GUARD (30-Jul (hl)).** `index.max_open`
  was carved out because its consumer default was `str(len(SYMBOLS))` — computed,
  not literal — so the drift arm was blind to precisely the lever most able to
  drift, and it HAD drifted (registry 10 vs code 9). Prefer making the consumer
  a LITERAL over declaring the exemption.
- **A GUARD WHOSE ONLY OUTPUT IS A WARNING ON A PASSING RUN IS NOT A GUARD
  (30-Jul (gl)/(hj), operator: "no more hiccups preventing situations such as
  those found today").** A green build carrying a `::warning::` is
  indistinguishable from a green build. `(fz)` chose warn-don't-fail on
  unverified Railway names *because* they were unverified, and wrote "check
  that warning after the first run" — it warned, four of six services never
  deployed, and their levers reached no container for a day. If a condition
  means the change did not land, it is an `::error::` and the run FAILS. If it
  is genuinely tolerable, it does not need to be surfaced at all. The only
  legitimate warning is one nobody has to act on.
- **A CONSUMER IS TESTED AGAINST A PAYLOAD ITS PUBLISHER BUILT (30-Jul (hj)).**
  Never hand-write a fixture that "looks like" the payload. Four defects in one
  session were a consumer reading a key its publisher does not emit, each with
  a GREEN selftest, because the fixture was written by whoever wrote the
  consumer: `marks[sym]["vol_m"]` against a map of floats, `stress["med_bps"]`
  vs `med`, `hurting_levers` vs `verdicts`, `ep["lever"]` vs `stance`. Call the
  publisher (`scout.build_snapshot`, `prop.build_stances`→`track`) and assert
  the consumer returns something **non-degenerate** — every one of those bugs
  produced an empty/None a value-free test calls "fine".
  `tests/autonomy/test_payload_contracts.py` is where these live. And when a
  shape surprises you, CHECK THE ACCESSOR before calling it a bug: that file
  records one tolerance (`venue_stress_bps` accepts a bare number + four key
  aliases) that was deliberate and nearly "fixed".
- **A SECOND COPY OF A RULE IS A SECOND RULE (30-Jul (hj)).** The go-live gate
  lives in `scripts/golive_readiness.py` and is IMPORTED, never re-implemented
  — `scripts/evidence_review.py` kept its own copy through the 29-Jul `(fk)`
  re-spec and, one day later, admitted a t=0.65 book and rejected the fleet's
  best-evidenced one on the retired win-rate bar. Pin re-use by **identity**
  (`grade is golive_readiness.grade`), not by asserting constant names are
  absent: a name check stays green against a hand-rolled copy. Same class as
  the brain's `FEE_RT` key defect `(gg)`.
- **PICK THE CHANGELOG LETTER AT PUSH TIME — now enforced across branches
  (30-Jul (hj)).** `audit_changelog_letters` compares this branch against
  `origin/main` and fails on a letter both used for a DIFFERENT title. Same
  letter + same title is a rebase and stays quiet. Fail-safe open (no git / no
  `origin/main` / on `main` ⇒ arm disabled).
- **CHANGELOG ENTRY LETTERS — the convention, finally written down (29-Jul (fd)).**
  Entries are tagged `## <date> (<letter>)` and cite each other BY LETTER
  ("the (co) paths fix"), including from TRACKED CODE
  (`railway-redeploy.yml` cites `(ff)`; `tests/test_selftests.py` cites
  `(ex)`), so a duplicated letter silently makes every such reference
  ambiguous. The rules:
  1. **The sequence is CONTINUOUS, not per-day** — it runs straight through
     date boundaries (it restarted once, at (a) on 17-Jul; that day carries
     both sequences deliberately).
  2. **Pick your letter at PUSH time, not at write time.** Parallel sessions
     both pick "next free" from a stale snapshot — that is the whole failure
     mode, and it has bitten at least SEVEN times (21-Jul (av)→(aw)→(ax),
     (bn) ×2, (br) ×2, 22-Jul (ca)/(cb), the 23-Jul (co)-(cr) quadruple, and
     29-Jul twice in one afternoon).
  3. **On a collision the CITED entry keeps the letter**; the other moves to
     the next free one. Decide by grepping the tree, not by who pushed first.
  4. **A renumber is recorded INLINE** in the moved entry — and note that
     `git log` subjects keep the OLD letter, so **the commit log is not a
     reliable letter index**; grep the CHANGELOG headers.
  5. Date an entry by **git's clock, not by the handoff you are executing**
     (29-Jul: five entries were dated 30-Jul because the session was running
     `NEXT_SESSION_2026-07-30.md`; git said 29-Jul in both UTC and Sydney).
  Enforced by `scripts/audit_changelog_letters.py` on every push/PR (scoped
  to ≥18-Jul so the deliberate restart cannot fail the build).
- **THE FARNHAM SIX (operator, 30-Jul: "name them something hilarious").** The
  six books that received the growth system in `(fz)`–`(gh)` — 🌾 Yield
  Harvester, ⚖️ Counterweight, 🧲 Snap Back, 📊 Index Rider, 🌊 Tide Rider,
  🎯 Perp Sniper — are collectively **The Farnham Six**, after John Farnham,
  undisputed national champion of the farewell tour that isn't. The joke earns
  its place: two of them (Index Rider, Tide Rider) have **zero closed trades**
  and are standing retirement candidates that keep not retiring, and 🌾 carry
  is a genuine comeback story sitting five of six bars from go-live. *The Last
  Time* was not, in fact, the last time. Respects the Australian-musician
  convention below WITHOUT renaming anything: these are existing books with
  existing emoji identities, so this is a COHORT label for referring to the six
  as a group (see `SIX_BOOKS_BASELINE_2026-07-30.md`), not a rename and not a
  licence to mint rows.
- **NAMING THE NEXT COHORT: famous AUSTRALIAN MUSICIANS (operator, 29-Jul).**
  The 🏛️ Parliament took the last Australian PMs; the NEXT cohort of books
  that earns its own dashboard rows is named for Australian musicians
  (`band-<surname>-lshadow` style, mirroring `pm-<surname>-lshadow`). This is
  a naming rule, NOT a licence to mint books: a row is minted only when a
  genotype/strategy has actually cleared its bar, and minting one is a BUILD
  (the Parliament pattern), not something the incubator does on its own — it
  breeds genotypes replayed against an EXISTING book's tape and can never
  create a row. See [[incubator-cannot-mint-books]].
- **THE CAGE MUST FIT THE VALUE (30-Jul, operator: "if the bounds don't
  correlate properly then recalibrate individually").** A lever is THREE
  things that must agree: the registry cage (`LEVERS[name]["lo"/"hi"]`), the
  declared default (`env_default`), and the `os.environ.get` default the
  consumer ACTUALLY runs. Until 30-Jul only the cage was machine-readable —
  the default lived in PROSE inside each lever's `note` and the real value
  lived in another file, so the three could not be compared and had already
  drifted (`scout.ticket_top_n` moved 6 → 12 in code with its note still
  saying 6, the same afternoon). EVERY lever now carries `env_default` (43 of them at (gu); the count is deliberately not load-bearing here because it drifts — `audit_lever_bounds` FAILS if any lever lacks one, so the guard is the claim and this sentence is only a pointer);
  `scripts/audit_lever_bounds.py` enforces on every push that each default is
  INSIDE its cage, that no cage is degenerate, that every book lever's `step`
  moves and terminates, and — the drift arm, mutation-verified — that the
  registry default MATCHES the consumer's code. A registry that misdescribes
  the running value is worse than none: every organ reasoning about headroom
  reasons from the wrong number. One-sided cages (default pinned at a bound)
  are REPORTED, not failed — an emission bar at its most restrictive end has
  all its room in the growth direction, which is usually correct.
- **BORN-DARK GUARD (17-Jul, after THREE incidents: `fleet_bus` 15-Jul,
  `event_sentinel` 16-Jul, `brain_stats` 17-Jul).** Adding a module, an
  import to shipped code, or a COPY means running
  `python3 scripts/audit_image_imports.py` before you ship. It reconstructs
  each image's real file set (multi-source COPY, `COPY venues/`, `COPY . .`)
  and walks the imports of every python file in it — **including inside
  COPY'd packages** (`venues/`, `user_data/strategies/`, where the
  real-money surface lives) — plus every run path (CMD, any COPY'd `*.sh`,
  and railway*.toml `startCommand`). Verified against all three incidents.
  Why it matters: each was SILENT, because a `try/except ImportError` guard
  — correct for optional organs — turns a missing file into a degraded
  fallback instead of a crash. **A deliberate omission is DECLARED in
  `BORN_DARK_OK` with a reason; silence is not an option.** Runtime
  backstop: `fleet_immune` pages when `brain-vitals` reports engine=v2
  without a deliberate `BRAIN_MULT_ENGINE=v2` (both parse that env
  identically — they must, or a typo'd kill switch silences the detector).
  **IN CI since `ce446c7`** — the guard and its `--selftest` run on every
  push/PR from `changelog-check.yml`, alongside `audit_sdk_pin`. (This line
  said "NOT wired into CI, the PAT lacks workflow scope — standing
  follow-up" for a day AFTER it was wired; verified 17-Jul (ad). A doc that
  tells the next reader to go re-do a done job is the same rot the guard
  exists to catch.) Still run it locally before you ship: CI tells you after
  the push, and the push is not what deploys anyway (see Railway Setup).
  **Verify a NEW module by its OWN published output, never by "it shipped"**
  — and never from git (see [[railway-cli-frozen-services]]: marker-grep the
  RUNNING container).
- **FLEET_RISK_MODE=advisory is SENIOR and now releases BOTH actuators
  (17-Jul).** It was documented as "every consumer goes neutral" but only the
  long-budget veto consumers ever checked mode — the 7d drawdown governor's
  `clip_scale` kept biting through a thrown kill switch. `fleet_risk` now
  publishes `clip_scale=1.0` in advisory mode (raw value kept as
  `clip_scale_raw`). Deliberate scope expansion of a documented contract:
  throwing the switch to stop the veto ALSO restores full clip size. Inert by
  default (mode=enforce) and it reaches only shadow consumers (family/taker);
  the live bots size off the separate `live.clip_scale` lever.
- **Operator timezone: Australia/Sydney — ALWAYS give Eamon Sydney-local
  times** (corrected 15-Jul evening; the earlier "AEST" note was recorded too
  narrowly). Sydney runs AEST (UTC+10) in winter and AEDT (UTC+11) during
  daylight saving (Oct→Apr) — use whichever is in effect and label it, so
  reported times always match his clock. Never hand him a bare UTC time.
  Fleet INTERNALS stay UTC (ledger rows, `updated`+`ttl_sec` freshness
  contracts, cross-service joins) — this is a reporting/display rule.
- **FREEZE LIFTED 15-Jul evening by user** ("this could be a breakthrough" —
  the evidence-board v2 build). The 21-Jul review + its agenda stand;
  restrict-only actuators / backtest-first / shadow-first remain doctrine
  (they were never freeze rules). Freeze-window exceptions stay logged in
  FLEET_REVIEW_AGENDA_2026-07-21.md §8.
- $1,000 starting balance per bot, NO top-ups
- **GO-LIVE GATE (re-specified 29-Jul at operator request — "fix the gate that
  would reject it"). A book stays on paper until, over >=30 days: >=30 closes,
  mean per-trade > 0, t >= 2.0, BOTH halves positive, and max drawdown < 15%.**
  Graded by `scripts/golive_readiness.py`; go-live remains an explicit
  operator act, never an automatic consequence of passing.
  - The rule this replaces was *"30-day win rate > 55% AND max drawdown <
    15%"*. **Win rate is orthogonal to expectancy**, and the fleet's
    best-evidenced book proved it: 🌾 `perps-funding-carry-lshadow` measured
    t=2.42 on n=80, both halves positive (+42.42/+13.78), realised +$56.20 —
    while winning **38.8%** of its trades. A win-rate bar would reject it
    forever, and would equally admit a high-win-rate book that loses money on
    the tails. Same non-sequitur shape as the tp-0.06 rationale, sitting in
    the rule that governs real money.
  - **NOT uniformly stricter, and that is stated rather than buried**: it
    drops a bar carry fails and adds two the old rule never had (significance,
    both-halves). Stricter for a high-win-rate loser; a real loosening for
    carry, which is what makes go-live reachable for it at all.
  - Win rate is still REPORTED — informative, just not a bar. The 30d window
    and the 15% drawdown cap are the operator's originals, unchanged.
  - REGIME CAVEAT applies (item 18): Lighter's tape is ONE falling-BTC regime,
    so a DIRECTIONAL book passing this has passed in that regime only. Funding
    books are largely direction-agnostic, so it bites them less.
  - **[2026-07-30 (hc)–(hh)] TWO PRECONDITIONS NOW SIT IN FRONT OF THE SIX BARS,
    because a bar computed over the wrong sample means nothing. Both are
    fail-CLOSED and neither promotes anything.**
    1. **THE SAMPLE MUST BE THE BOOK'S CURRENT SELF — `POLICY_ERA`.** The gate
       used to grade a book's WHOLE retained ledger, so a change that made the
       earlier record *wrong* kept counting toward the 30-day bar. Measured on
       the two books nearest real money: 🌾 carry had **101% of its P&L**
       (+$62.03 of +$61.12) opened before the 17-Jul accrual-basis fix and is
       −$0.91 over the 57 closes since (5/6 bars → 2/6); 💸 Farmer's shadow twin
       read **5/6 at t=+2.09** all-time and **3/6 at t=+0.74 with h1 NEGATIVE**
       in-era, and **no post-fix boundary passes the t bar at all**.
       - **WHAT RESETS AN ERA**: a change that makes earlier P&L *wrong* (an
         accounting/accrual-basis fix) or the strategy *different in kind*.
       - **WHAT DOES NOT**: ordinary tuning — a lever step, a widened universe, a
         clip change. The growth rail moves levers daily BY DESIGN; resetting the
         clock each time makes the 30-day bar unreachable forever. Carry's own
         21-Jul `ENTER_APR` 0.40→1.60 is the worked example of what does *not*
         reset it, even though splitting there would restrict the book further.
       - **AN ERA IS THE LATEST OF EVERY INVALIDATING CHANGE.** Two eras do not
         compose into a range: a sample must exclude BOTH the old strategy and
         the old accounting, so moving a date FORWARD preserves the earlier
         reason rather than discarding it.
       - **Keyed on the OPEN** (a trade's policy is fixed when it is taken; a
         straddler accrued in both bases and belongs to neither), **fail-closed**
         on an unreadable stamp, and **keyed BARE with a ONE-AT-A-TIME suffix
         strip** — `perps-funding-lighter` is itself named after the venue
         suffix, so the obvious double-`rsplit` scopes the live row and silently
         MISSES its shadow twin. Both `POLICY_ERA` and `bot_learn.ERA_START` had
         that bug; both are fixed and mutation-pinned.
       - **THE GATE'S SAMPLE MAY NEVER BE WIDER THAN THE BRAIN'S**, and every
         living accruing book must appear in BOTH tables. Membership is
         RULE-DRIVEN — *the publisher accrues funding AND the book has pre-fix
         closes* — not a curated list. **It is not uniformly restrictive**: four
         of the six family/spot books read BETTER in-era, and ⚖️ Counterweight
         goes from mean +0.709%/win 56% to **+1.263%/win 68%** — pooling was
         HIDING the fleet's best expectancy. Books whose publisher does not
         accrue (🧲 Snap Back, 🎯 Perp Sniper) are excluded on purpose; an era
         declared "for symmetry" on a price book discards real evidence.
    2. **THE LEDGER MUST BE ONE BOOK'S RECORD — integrity.** A book with a
       same-pair overlapping hold can never be `READY`, and the reason prints
       FIRST in `fails` (behind `fails[:2]` it was invisible in exactly the run
       that needed it). Deliberately NOT a seventh bar: `BAR_NAMES` is the
       published contract, and this invalidates the other six rather than
       joining them. Published as `integrity`, rendered as a red `2 writers`
       chip, and `fleet_immune` pages the operator on it — because the fix is an
       OPERATOR action and a guard cannot un-pool closes two processes already
       wrote. Detector + rationale: `scripts/audit_ledger_integrity.py`.
- **DOCTRINE (2026-07-30) — WHEN YOU CHECK WHETHER SOMETHING WAS DAMAGED, PICK A
  TEST THAT COULD DETECT THE DAMAGE.** This cost most of a session and it keeps
  recurring in different clothes:
  - `(gn)` scanned the carry ledger for duplicate `trade_id`s, found none, and
    concluded the grade was intact. Two processes open at different moments, so
    their ids (`{coin}:{opened_ts}`) **never collide** — the scan was blind to
    duplicate WRITERS by construction. The test that works is STRUCTURAL: a
    carry process keys `positions` by coin and enters only `if c not in
    positions`, so a same-coin overlap is *impossible* for one process. 7 of
    them, deepest 9.14h.
  - A **page-wide substring scan is not a structural claim.** Three tests in one
    session failed on the very sentence promising the property they checked
    (`dry_run` appears in "flips no dry_run"; `era` appears in "operator"). Use
    AST for call sites and a chip's own markup for rendering.
  - **Do not assert a convention the fleet does not have.** A test requiring the
    marker `"BASIS FIX"` failed on `funding_carry_bot`, which labels the same fix
    `"THE SIXTH 8x BOT"`. Match the invariant (a date + a real rate conversion),
    not one house phrase.
  - **A retyped constant is a constant that drifts.** `backtest_carry_gate_
    lighter.py` pinned `MAX_POSITIONS = 8` while the bot shipped 12, so a re-run
    would have measured a book the fleet does not run. Read from the bot, or add
    a drift arm that fails when they disagree.
  - **A finding no gate consumes is a note.** Integrity became a precondition
    plus a phone push; the era became the published sample. Otherwise the
    measurement sits on a card and the pipeline keeps using the old number.
  - **A "sanity anchor" that nothing gates on is decoration.** `study_carry_flip_
    grace_lighter` printed its sim-vs-ledger drift from day one; gating on it
    revealed the shipped-rule replay overstates its own losses by 2.3x, which
    invalidates every variant in the table. Generalise `(gx)`: a harness that
    cannot reproduce what DID happen may not say what WOULD have — and the
    reproduction check must REFUSE, not report.
- Never modify bot logic without backtesting first
- **BACKTEST ON LIGHTER ONLY — the venue we trade is the venue we measure
  (operator rule, 17-Jul: "Lighter needs to be the only exchange backtests run
  on as we run on lighter").** LIGHTER-FIRST governed SERVICES since 14-Jul;
  this extends it to EVIDENCE. A backtest on another venue's data is not
  validation of a Lighter bot — it is a hypothesis about Lighter.
  WHY, measured 17-Jul: **every funding backtest in this repo loads
  HYPERLIQUID** (`backtest_directional_funding` / `_scanner` / `_carry_hedged` /
  `_funding` / `_regime` / `_leverage` / `_persistence` / `study_funding_settlement`),
  and the Tide Rider set loads HL **+ Binance** (`backtest_tide_rider` /
  `_perp` / `_scanner`). **Both LIVE bots' go-live justifications are on that
  list**, and it has already cost real money twice:
    * Funding Farmer — `FUNDING_ENTER_APR=0.40` was fitted on HL (hourly, so
      `24*365` is CORRECT there) and ported to Lighter as a bare constant.
      Lighter quotes per 8h, so the LIVE gate silently admitted at **5% TRUE**
      for as long as it has run, on a bar no backtest ever supported.
    * Tide Rider — its header's "~13pp funding drag / +52% spot -> +40% perp"
      is **Hyperliquid's funding**, from a script whose own line 16 claims it
      shows "what Lighter would actually deliver".
  THE RULE: a Lighter bot's evidence comes from Lighter's own tape. If a study
  must be cross-venue (e.g. the HL-vs-Lighter equivalence study), that is a
  DECLARED exception with a reason — the same pattern as `BORN_DARK_OK` /
  `VENUE_PURITY_OK`. `scripts/audit_venue_purity.py` currently SKIPS `scripts/`
  (`_SKIP_DIRS`, "research tools") — extending it to backtests is what makes
  this rule enforced rather than merely written; an unenforced rule rots.
  THE COST, state it honestly: **Lighter's tape is ~438d** (settled hourly
  funding pages backward via `/api/v1/fundings` with `end_timestamp=oldest-3600`;
  candles page 500 bars). So Lighter-only means **~14 months, not 2.7 years** —
  Tide Rider's 2.7yr window is NOT reproducible on Lighter and never will be.
  That is a real loss of window, and it is the price of measuring the venue that
  holds the money. Short-and-honest beats long-and-borrowed: a 438d Lighter
  result is evidence; a 2.7yr HL result about a Lighter bot is an assumption
  wearing a number. Retired-bot backtests (Kraken originals) are HISTORY — do
  not re-run them; they justify nothing that still trades.
- **REGIME-COVERAGE CAVEAT (21-Jul review, item 18 — adopted D5): "positive in
  both halves" is necessary but NOT SUFFICIENT for DIRECTIONAL strategies.**
  Lighter's whole 438d tape is one falling regime (BTC −32.9%; the family
  regime gate reads risk-off 61.5% of bars; BOTH halves fall), so a
  directional short passes both halves BY CONSTRUCTION — the bar is satisfied
  by the drift, not the edge. A directional validation must STATE which
  regimes its window contains, and a one-regime pass is a pass in that regime
  only. More Lighter tape does not fix this; only a different regime does —
  the venue's ~27 non-crypto books (SPY +8.1%, QQQ +12.2%, WTI +23.0% over
  the same falling-BTC window) are the on-venue source. PREREQUISITE before
  any non-crypto directional widening: a PER-ASSET regime gate — never BTC's
  EMA for SPY/XAU/WTI (measured: btc_regime_up read risk-off 61.5% through
  SPY's bull run; the brain's Georgia diagnosis — 100% of losses opened in
  oracle risk-off — corroborates from independent data). Build order: oracle
  per-asset coverage → the gate consumes it → only then the universe.
  **[2026-07-30: step 2 WIRED (operator call, "per asset have consumer").**
  `fleet_bus.oracle_asset_regimes()` → `lighter_family_bot.regime_inputs_for()`:
  crypto pairs byte-identical on the validated BTC gates; a NON-CRYPTO pair
  rides its OWN oracle verdict, fail-CLOSED (ungraded book / dark-or-stale
  oracle ⇒ no entry — never BTC's gate; classification is STATIC so a dark
  oracle cannot re-route SPY to BTC; kill switch `FAMILY_PER_ASSET_REGIME=off`
  closes non-crypto entirely, never re-routes).
  **[2026-07-30 later: STEP 3 RUN (operator, "run step 3 too") — the build
  order is COMPLETE.** The four FAMILY books' universe now carries the
  oracle's 10 non-crypto books (`FAMILY_NONCRYPTO_COINS`, empty = revert);
  spot ports stay pinned crypto-only. The gate governs: an ungraded book
  (SPY/QQQ/IWM/WTI/XCU/MSTR until the 203-bar floor) admits NOTHING, a
  graded book admits longs only in its OWN LONG-window, and the rule binds
  at the ENTRY SITE (`noncrypto_entry_blocked`) so strategies that never
  read the regime extras (TrendMomo/SwingDip) cannot buy SPY ungated. At
  ship the gate is mostly closed by the evidence's own shape (NVDA
  LONG-window 30% of bars, TSLA 2%, XAU 4%, XAG 12%). Evidence:
  `REGIME_GATE_PER_ASSET_2026-07-30.md` — its study re-runs at SPY/QQQ
  graduation (~mid-Aug), which now grades books that are LISTED and
  waiting rather than hypothetical.]
- **LIVE BOTS ALWAYS IN AUDIT SCOPE (operator rule, 16-Jul).** Every audit,
  bug-scan, code-review, or security-review — WHATEVER its nominal scope —
  MUST also check the LIVE REAL-MONEY bots in the same pass: Funding Farmer
  (`lighter_funding_bot.py` → `perps-funding-lighter-lighter`) and the **Ticket
  Taker** (`lighter_ticket_taker.py` → `lighter-ticket-taker-lighter`), plus
  their shared real-money surface (`venues/` SafetyRails / notional caps /
  equity guard, `order_usd`, and the `live.*` lever consumers). Why: real money
  lives there, and the 15-Jul cap breach proved a change ELSEWHERE (the growth
  rail) can break the live bots even when the audit isn't "about" them. Never
  let an audit exclude the live bots. **[22-Jul (ci) CORRECTION: this rule
  named the RETIRED Tide Rider (`lighter_trend_bot.py` →
  `crypto-trend-daily-lighter`) — which the 🎫 Ticket Taker replaced on the
  same slot 17-Jul. A standing audit rule that names a retired bot sends every
  future audit to check the wrong file; the live pair is Farmer + Ticket
  Taker.]**


## Doctrine: Claude is the judgment layer, never the polling layer (added 28-Jul-2026)

Context: 14–24 Jul 2026, Code sessions armed 48 `send_later` self-check-in
wakeups (27 on 23-Jul alone; one PR-#91 chain re-arming ~hourly into a
persistent session). Each firing replayed a full transcript to ask a yes/no
question GitHub answers for free. Est. ~1.35M tokens in one day — ~40x the
entire weekly admin load. All 48 spent triggers were deleted 28-Jul.

**P1 — Never arm a wakeup chain to watch external state.** No `send_later`,
`ScheduleWakeup`, or self-re-arming reminder to poll CI status, PR
mergeability, deploy receipts, `/bus.json` / `/pnl.json` field changes, or
container health. These are push-capable sources; wire the push instead.

**P2 — The replacement is an Action, not a shorter interval.** CI/PR state →
`ci-notify.yml` (posts transitions on the PR). Service state → extend
`fleet-watchdog.yml` (probing pnl.json; HOURLY since 28-Jul — the billing
lockout retired both the old ~30-min cadence and the "$0" claim; the
dashboard's in-service 5-min watchdog is the fine-grained layer).
If it cannot be pushed, it is not important enough to poll.

**P3 — A check-in chain may re-arm at most TWICE, then it must stop.** If a
genuine wait is unavoidable (a human decision, a venue with no webhook), arm
at most two check-ins, then report last known state and stop. Never re-arm
silently. Never re-arm "until merged". Three firings = should have been an
Action.

**P4 — Never poll into a persistent session.** A persistent-session wakeup
replays the whole transcript first, so cost grows with session age. If a
wakeup is truly required, start a fresh session with a self-contained prompt.

**P5 — Clean up after yourself.** Spent one-shot triggers inflate every later
`list_triggers` read (28-Jul: one call returned 252,507 chars ≈ 63k tokens
because 48 dead triggers still carried full prompt payloads). Delete a
chain's triggers when the chain ends. The Weekly Admin task now self-audits
the scheduler weekly and deletes >10 leftovers.

**P6 — Escalate to the operator instead of waiting.** When blocked on Eamon's
decision, say so once and stop. He would rather answer in the morning than
pay for the wait.
