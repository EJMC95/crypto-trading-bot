# Session Log

Durable record of major bot-work sessions. Newest first. For the line-by-line
change list see `CHANGELOG.md`; this file captures the *narrative* + what to
watch for next. Everything here is DRY-RUN / paper unless explicitly stated.

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
