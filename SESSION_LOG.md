# Session Log

Durable record of major bot-work sessions. Newest first. For the line-by-line
change list see `CHANGELOG.md`; this file captures the *narrative* + what to
watch for next. Everything here is DRY-RUN / paper unless explicitly stated.

---

## 2026-07-09 — Lighter.xyz venue layer (Gate 0) + go-live-on-Lighter prep

### What shipped (all still paper/shadow — no real money moved)
Built the `venues/` abstraction from the Cowork "Lighter Gate-0 kickoff v2":
`VenueClient` interface + `HyperliquidClient` (exact passthrough of the old
inline HL calls) + `LighterClient` (lighter-sdk 1.1.1, ws-first book cache,
weighted tx-budget governor for the 60/min standard tier, symbol-map for
kBONK↔1000BONK / PEPE↔1000PEPE). `VENUE` env picks
hl_paper|lighter_shadow|lighter_testnet|lighter_live. Trail Blazer, Bounce
Catcher, Yield Harvester refactored onto it; the other 3 HL-facing bots
(regime-switch is freqtrade, sniper is spot-CCXT, cross-arb needs 2 venues) are
NOT directional-perps live candidates and were left for later.

### Proven
- **Data parity**: HL candles byte-identical old-vs-new; funding map 231/231.
- **Decision parity**: one-cycle diff = 0 for Bounce Catcher; Trail Blazer diff =
  exactly the 2 intended cap-clips (HYPE/JUP OPEN_LONG→CAP_SKIP) from its new
  global position cap (the pre-live blocker — it was running 15 open alone).
- **Shadow**: both pilots ran a clean cycle on LIVE Lighter mainnet books;
  ShadowBroker crosses the real spread and logs to the new `venue_orders` ledger.
- **Day-1** (`docs/lighter.md`): 215 markets, ZERO fees, $10/order min (clips fine
  at $25-35), ETH/ADA/HYPE listed, BLUR/ATOM/INJ/ORDI/TON not; signer binaries
  load on linux/amd64 AND Mac arm64; native cross-venue funding endpoint.
- **Testnet smoke** read-only layer 6/6 pass (market list, candles, funding, ws
  forced-reconnect, kill-switch-blocks-live); auth layer skips w/o env keys.

### Go-live-on-Lighter (Eamon's call, this session): top perps bots live, each on
its OWN Lighter sub-account (isolated margin). Dashboard now distinguishes live
bots (red LIVE badge, `<bot>-lighter` rows) and carries a separate **🔴 LIVE ·
Lighter** P&L total line + `/pnl.json meta.live_fleet`. `GO_LIVE_LIGHTER.md`
written = the user-only checklist (Ledger acct, N sub-accounts, 1 trade-key each,
fund, per-service Railway env, PG-password rotation, one-at-a-time kill-switch
disarm). Ledger ranking of Lighter-capable directional perps: 🧭 Trail Blazer
+$173 (89% WR) and 🪃 Bounce Catcher +$64 (75% WR) are the confirmed live-ready pair, sized $50–100/bot with
$15–25 clips (his call). **Sniper resolution:** the spot Launch Sniper can't run
on a perps DEX, so Eamon chose to build a NEW Lighter-native sniper —
`lighter_perp_sniper.py` (🎯 Perp Sniper) snipes freshly-*listed Lighter perp
markets* (active-set diff vs a seeded baseline; AnnouncementApi as context). It's
UNVALIDATED so it runs **shadow-first** and is not in the funded set. **I did not
create the account, touch keys, fund, or disarm anything — those stay with Eamon
(`REAL_MONEY_KILL` ARMED).**

### Watchlist
- Testnet smoke's AUTHENTICATED layer + overnight burn-in still need Eamon's
  testnet keys (env only).
- Bots 3–4 selection + capital are the open go-live decisions.
- Rotate the Postgres password BEFORE any real key lands in Railway.

---

## 2026-07-07 — Full-fleet audit → Option-B isolation, brain revival, exit rebuilds

### What the audit found (live Postgres, 352 trades + 285 fills + 52k equity pts, plus code audit)
- **Winners:** perps-rsi-meanrev +$41.47 closed (87% WR, PF 5.5; the Jul-5 cap contains its correlated-dip risk) and perps-donchian-breakout +$37.96 (25W/1L). Day-trader 15m rework **VERIFIED** (11% → ~45-50% WR, bleed stopped). Crypto fleet ledger-clean: **+$181.68**.
- **Sniper truth:** +$155.94 = ANSEM +$325 minus a −$169 junk tax; **80% of exits were `delisted`**.
- **ROOT CAUSE of the Jul 5-7 "balance resets":** the four family-bot services pointed at Dockerfile.freqtrade → each ran ALL NINE bots (fresh $1000, no volume) + a 9-name poller; five pollers race-wrote bot_pnl. 51 reset events; 142 contaminated bot_trades rows (Jul-6 05:05-05:17 shared-SQLite window). Their FREQTRADE_* env vars were inert.
- **Brain dead since Jul-5 06:19:** bot_learn.py was never COPY'd into the image (`can't open file`).
- **funding-carry 0W/28L structural:** decay-exits realize 29bps round-trip fees hours before the ~64h@40%APR payback point. Jul-6 tune didn't touch the exit logic.
- **Alpaca (NOT yet fixed, separate repo):** unexplained −$19.9k on Jul-2 then a 3-day freeze; feed pnl_abs measures from the post-crash baseline (true ≈ −$8k from first record).

### What shipped today (one push, commits per fix, changelog per commit)
Option-B isolation (run_all `ONLY_BOT` mode; poller back to 5; family services each get a /freqtrade/persist volume + ONLY_BOT env and run exactly one bot); Dockerfile COPY bot_learn.py; funding-carry exit rebuild (flip-grace ≥1h / decay-only-after-fee-payback / 14d expiry / −2% bleed stop) + 6h funding-persistence entry filter; sniper ghost-gate (junk intel + minor venue = skip; junk elsewhere quarter-stake); V7 max_open 10→6; RegimeSwitchV2 per-loop diagnostics. Family Postgres rows quarantined + purged post-cutover (see analysis_2026-07-07/).

### Evening — cross-bot intelligence build (Phases 1-3, publish-side)
Built and deployed the first three layers of the cross-bot design, advisory mode:
`regime_oracle.py` (L1: one shared regime read, 12 majors, published + historized),
`fleet_risk.py` (L2: fleet-wide exposure traffic light with pair-pileup detection;
L3: signal bus mirroring funding/dislocation/pulse into bot_state). Nothing
consumes these yet by design — after ~7 days of `bot_state_history` we compare
oracle calls + risk lights against what bots actually did, then wire enforcement
(confirm_trade_entry veto on RED, oracle-gated sizing) from evidence. A scheduled
review task exists for this.

### Watchlist
- Family bots restart at $1000 era-zero in isolated services — judge after 2 clean weeks, not before.
- funding-carry: expect FAR fewer closes; first `decay_paid` win = the rebuild working. All-`flip` closes = universe still too spiky → tighten to majors.
- Sniper: `delisted` share should collapse from 80%; ticket count drops (ghost class skipped).
- RegimeSwitchV2: read `[regime-diag]` lines before touching gates again.
- Local Mac clone reconciled: WIP stashed (`pre-OptionB WIP 2026-07-07`), reader-api commit preserved on `stash/reader-api-b82c5aa` — re-apply later as the HTTPS ledger endpoint (the right cross-surface DB access fix).

---

## 2026-07-05 — Persistence, participation, the brain, and a new short engine

### What we achieved
**Foundation / persistence**
- Ended the "balance resets to $1000" problem for the whole fleet (freqtrade →
  `/freqtrade/persist` volume; perps/sniper → Postgres state). Proven empirically:
  bots kept their P&L through multiple redeploys.
- Confirmed a solid durable data store: 5 Postgres tables, 160+ trades, growing.

**Trading fixes**
- ⚡ Range Raider (day trader): was 0W/11L fee-bleed → fee-viable timeframe, added
  a bounce-participation mode, widened buy-zone (0.37) so it trades relief rallies.
- 🪃 Bounce Catcher (perps): added a global position cap (was 70% of book in one
  correlated direction with no limit).
- Perps close-bug fixed earlier in the week (entry-relative TP + time stops).
- 🎯 Launch Sniper: throttled the drip-bleed (smaller tickets, tighter gate).

**New bot: ⚖️ Two-Way Tide (RegimeSwitchV2)**
- Rebuilt the idle regime-switch bot into the fleet's ONLY dual-direction engine:
  longs breakouts in up-regimes, SHORTS breakdowns in down-regimes. Grounded in the
  combined lessons of every fleet bot + evidenced public trend-following research
  (AQR, Moskowitz-Ooi-Pedersen, Hyperliquid docs). 4h Donchian, structure-break
  exits, wide ATR stop, inverse-vol sizing, correlation-aware cap. 10 majors.
  UNVALIDATED (no OHLCV to backtest) — robust-by-construction, brain-watched.

**Learning**
- Root-caused "no traction": the brain was never scheduled → never accumulated the
  runs needed to promote a lesson. Now runs every 2h in the cloud.
- Extended the brain to ALL bots (was freqtrade-only; now ingests perps/sniper too).

**Dashboard**
- Total P&L on every bot card; trendy + descriptive bot names.

**Coordination (why this is the main channel)**
- `CHANGELOG.md` + `CLAUDE.md` + a CI check that fails any push touching bot code
  without a changelog entry. Stops parallel sessions clobbering each other.

### What to expect next (watchlist)
Grounded expectations, not promises. Horizon in brackets.

- ⚡ **Range Raider** — MORE opens/closes (it was idle; now trades the bounce). Net
  P&L is the open question: wider buy-zone = thinner capture, so win-rate matters
  more. Watch that added frequency stays fee-positive. [hours–days]
- 🪃 **Bounce Catcher** — FEWER concurrent positions (≤6 vs 14). Smoother equity,
  less give-back on correlated dips; should protect gains rather than round-trip
  them. New entries log `CAP_SKIP` when the cap binds — expected, not a fault. [days]
- ⚖️ **Two-Way Tide** — the big one. In the current down-regime it should start
  taking SHORTS as majors break their 15-bar lows (fires when the bounce fades).
  Trend signature: ~40% win rate, few big winners, loser strings in chop — normal,
  not a malfunction. HONEST: unvalidated; could lose like V1 (−20%). This is the
  live experiment that decides if the fleet can profit FROM a bear. [days–weeks]
- 🎯 **Launch Sniper** — fewer, smaller ($50) tickets; the +263→+157 drip should
  slow. Fewer trades overall (stricter gate). [days]
- 🌊🩸🚀🏄 **Trend bots (Tide Rider / Dip Buyer / Breakout Hunter / Momentum
  Surfer)** — deliberately untouched (they're the validated winners). Expect them
  mostly cautious/in-cash in a downtrend, few closes. Steady, low activity. [weeks]
- 🌾 **Yield Harvester** — unchanged; 0/7 so far is fee friction, no fix indicated
  yet. Judge after ~10–15 more closes. [weeks]
- 🧠 **The brain** — over the coming days it accumulates runs and starts promoting
  actionable lessons (needs ≥3 runs + ≥8 trades/pattern). Watch `reports/
  lessons_latest.md` / the dashboard brain card go from empty to populated. [days–weeks]
- 📊 **Fleet-wide** — more activity from the two previously-idle bots; better risk
  control → smoother curves; and because nothing resets anymore, the numbers finally
  ACCUMULATE meaningfully — which is what makes the brain and dashboard useful. Net
  P&L outlook: cautious; the real upside lever is Two-Way Tide catching the bear.

### Still blocked on the user
- **OHLCV export** (Kraken/exchange) → the only way to backtest-validate anything,
  especially Two-Way Tide. Until then everything is live-proven only.
- **SMTP env vars** on pnl-dashboard → activates the dormant email reports.
- **Alpaca −$19.9k** equities anomaly → its source is off-repo (your Mac); can't
  review it from here.
