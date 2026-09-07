# SYSTEM INVENTORY — 2026-09-07

**Phase 1 of the risk-adjusted-return audit. Read-only: this pass changed no code,
no lever, no env and no position.**

Sources, all captured 2026-09-07 ~04:0xZ and kept in the audit scratch:
`/pnl.json` (16 living rows), `/trades.json?source=paper` (4,311 closes, **not**
truncated — the 5,000 cap was checked per the `(qz)` rule), `/bus.json` (organ
payloads incl. the published `golive-readiness` grade), plus the repo at
`69ed911`. Where a number exists both in code and on the live row, **the row
wins and the divergence is called out** — a constant in a file is a claim about
a container, not a measurement of one.

---

## 0. What this system actually is

Not "a trading bot". It is a **fleet of 16 independently-graded books** on ONE
venue (Lighter, zero-fee perps), wrapped in ~20 always-on "organ" processes that
grade, size, veto, tune and page. Two books hold **real money** (~$994 combined);
the other 14 are $1,000 paper/shadow with no top-ups.

The system's own centre of gravity is not the strategies — it is the
**grading pipeline**. `scripts/golive_readiness.py` is the single authority for
which sample describes a book (`POLICY_ERA`), whether that sample is one book's
record (`integrity`), and whether it passes six bars. Every other instrument
imports it rather than re-deriving. That is the single most valuable structural
property in the repo and the audit should protect it.

---

## 1. Living books — purpose, venue, timeframe, entry, exit, sizing

All 16 trade **Lighter perpetuals** (`mainnet.zklighter.elliot.ai`). Venue fee is
**zero** (measured: all active books report `taker_fee 0.0000`); the real cost is
the crossed spread. No other venue is traded — four non-Lighter bots
(`listing_sniper`, `cross_exchange_arb`, `triangular_arb`,
`hyperliquid_perps_bot`) exist in-tree but are **code-guarded off** since 17-Jul.

### 1.1 Real money (2 rows, one shared carrier)

Both live rows run the **same file** — `lighter_avo_live_bot.py`, a variant host
selected by `FAMILY_LIVE_BOOK`, importing its strategy classes from
`lighter_family_bot.py`. That is the entire real-money code surface, plus
`venues/` (SafetyRails, equity guard, fills) and the `live.*` lever consumers.

| | 🙏 **avo maria** `freqtrade-avo-maria-lighter` | 👩 **mum** `freqtrade-mum-lighter` |
|---|---|---|
| Purpose | RSI/Bollinger **dip inside an uptrend** | **deep-oversold rebound outside** an uptrend |
| Carrier | `SwingDip` | `OversoldRebound` (v2, 19-Aug redesign) |
| Timeframe | 4h | 1h |
| Entry | `EMA50 > EMA200` **and** `RSI(14) < 42` **and** `close < BB_lower(20, 2σ)` **and** volume > 0 | `RSI(14) < 36` **and NOT** `EMA50 > EMA200` **and** volume > 0 |
| Exit | ROI ladder `{0h: +20%, 96h: +12%, 192h: +6%, 336h: 0}`; signal exit `RSI > 65` or price ≥ sell-zone | ROI ladder `{0m:+2%, 240m:+1.6%, 480m:+1.2%, 720m:+0.8%, 1080m:+0.4%, 1440m:0}`; **max_hold 1440m (24h)** |
| Stop | **−10%** | **−4%** |
| Slots | 6 (raised 5→6 on 6-Sep, pre-registered revert 6-Oct) | 12 |
| Sizing | `clip = equity × gross_x / max_open`, `gross_x` **2.0** (cap `AVO_GROSS_X_MAX` 5.0) | same formula, `gross_x` **5.0** |
| Live geometry (row) | equity $416.78, n_eff 1.725, basket ρ 0.159, leverage_now 0.81×, all-slots-stop 20% | equity $577.22, n_eff 1.831, basket ρ 0.319, leverage_now 1.24×, all-slots-stop 20% |
| Universe scanned | 49 markets | 104 markets |
| Scan order | `diversified_order` — offers the candidate that most lowers basket correlation first | same |

**Divergence found (code vs container):** `OversoldRebound.RSI_MAX` defaults to
`38.0` in `lighter_family_bot.py`; both mum rows publish `rsi_bar 36.0`. That is
**correct and deliberate** — Eamon reverted the `(ya)` widening on 4-Sep by
setting `MUM_RSI_MAX=36` as a Railway env on `mum-live` **and**
`family-lighter-shadow` (both arms, so the twin stays a control). Recording it
because the file alone would mislead the next reader.

### 1.2 Shadow / paper books (14 rows)

| Row | Name | Thesis | TF | Entry | Exit | Clip × slots |
|---|---|---|---|---|---|---|
| `lighter-ticket-taker-lshadow` | 🎫 Ticket Taker | trades the market scout's high-conviction **tickets** across 4 lenses (breakout / dip / momentum / divergence) | ticket-driven | scout ticket + taker's own bars; stress veto pauses entries at venue \|prem\| ≥ 15bps | tp +4% / sl −3% / trail 6% on breakout / **max_hold 48h** / sl_cooldown 2h | — (cap 8) |
| `perps-funding-carry-lshadow` | 🌾 Yield Harvester | delta-neutral **funding carry**, modelled | continuous | TRUE APR ≥ **20%**, vol ≥ $1M, **persist 12h**, crypto-only, payback ≤48h | `decay_paid` (after payback+margin), `liability_flip` after **6h grace** | $80 × 12 |
| `perps-funding-spread-lshadow` | ⚖️ Counterweight | cross-sectional **funding long/short**, dollar-neutral | 24h rebalance | top/bottom **K=5** of a 35-name universe | rebalance only (no per-leg stop, by design) | 10 legs |
| `band-kelly-lshadow` | 🪁 the Mirror | holds the **opposite side** of measured losers (`snapfade` = retired 🧲 dislocation inverted; `dipfade` probe) | 90s loop | ghost's adaptive p98 gate, floored 60bps, 2-loop confirm, 30bps slip gate | ghost's exit; own **5% hard stop**; max_hold 2h | $80 × 4 (+ $40 × 2 dip probe) |
| `lighter-perp-sniper-lshadow` | 🎯 Perp Sniper | new-listing / volume-surge / young-book **debut** trades | event | 3 sources w/ per-source census; surge ≥3× 24h vol | per-source side + hold (`listing`/`young` SHORT@24h, `surge` 6h) | cap 4 |
| `book-hull-lshadow` | 🧮 The Professor | Hull cost-of-carry on the **untaken funding band** | continuous | TRUE \|APR\| ∈ **[7.82%, 20%)** × vol **[$1M, $10M)**, persist 24h | `decay_paid`; flip grace 24h; max_hold 504h; basis veto >10bps | $80 × 10 |
| `book-kiyosaki-lshadow` | 🏦 Rich Dad | funding-**receiving only** ("assets"), liability sold | continuous | TRUE APR ≥20%, persist 6h, **payback ≤120h** ⇒ effective bar ~21.9% | `decay_paid`; `liability_flip` after 6h | $80 × 6 |
| `book-bezos-lshadow` | 🚀 Day-1 Flywheel | **impulse fade** on the Douglas engine, faster/liquid profile | 1h-ish | impulse > **2.2 × ATR24**, vol ≥ $2M, top-24 crypto | bracket at entry: **sl 0.9×ATR / tp 1.8×ATR / 8h** | $100 × 5 (gross 0.5×) |
| `freqtrade-mum-lshadow` | 👩 mum twin | **control arm** for the live book | 1h | identical to live (`rsi_bar 36`), plus `vel_band [12,20]` experiment via judge | identical | 12 slots |
| `freqtrade-avo-maria-lshadow` | 🙏 avo twin | **control arm** for the live book | 4h | identical to live | identical | 6 slots |
| `freqtrade-georgia-lshadow` | 🔮 georgia v1 | gated 15m day-trader | 15m | `DayTraderGated` — ROI `{0:1.8%,180m:1.2%,360m:0.8%,720m:0.5%}`, ATR trailing stop capped by carrier stop | ROI / trail / timeout | 5 slots, stop −5% |
| `freqtrade-georgia-v3-lshadow` | 🔮 georgia v3 | **impulse fade**, the successor entry | 15m | drop ≥ **3.0 × ATR14** over 4 bars, crypto-only | ROI `{0: +2%}`, max_hold 240m | 5 slots, stop −1.5% |
| `pm-albanese-lshadow` / `pm-turnbull-lshadow` | 🏛️ Parliament | 2 survivors of a 6-book self-evolving ML fleet | mixed | Keating scanners + 5-model prequential ML ensemble gate | per-lens | in-process |

**Retired but in-tree** (guards, not deletions; each reversible by env):
🌊 Tide Rider, 📊 Index Rider, 🧲 Snap Back, 🎸 Barnesy, 🛢️ Garrett,
🧙 Schwager, 🧘 Douglas, 📐 Grimes, 🧭 Cook, 💸 Funding Farmer (both arms),
🔮 georgia's live arm, 👨 dad, 4 PM books, 3 spot ports.

---

## 2. Position sizing — the one formula, and the six things that modify it

Base: **`clip = equity × gross_x / max_open`** (live books). Shadow books use a
fixed clip per the table above. On top of that, in order:

1. **`fleet_bus.brain_clip(bot, tag, base_usd)`** — the brain's per-(bot, tag)
   multiplier, range **[1/6.7, 6.7]**, two-way, gated on a 3-run streak.
2. **Drawdown scale** — 1.0 up to the 15% gate bar, falling linearly to 0.25 at
   30%. Read from the gate's own `max_dd_pct`. Fail-open.
3. **Never-lever-a-weak-edge** — a multiplier >1.0 is refused when
   `fleet_allocation` has measured the book's era lower bound ≤ 0 on ≥10 closes.
4. **`fleet_allocation.allocation_scale`** — `target_usd / book_usd`, clamped
   **[0.25, 4.0]**. Consumed by three funding shadow books; **advisory
   everywhere else** and structurally never read by real money (AST-pinned).
5. **`fleet_risk.clip_scale`** — 7-day fleet drawdown governor (1.0 / 0.5 / 0.25).
   Currently **1.0**.
6. **SafetyRails** — `notional_ok` against `<BOT>_MAX_NOTIONAL`, and the live
   Farmer's rail *trims* rather than rejecting (never below the pre-brain clip).

Fleet-wide **long budget = 20**, now split per cohort: live 20 (5 used),
shadow 26 (16 used). Traffic light: **pooled yellow, both cohorts green.**

---

## 3. Fees, spread and slippage — what is assumed vs what is measured

| Quantity | Value | Status |
|---|---|---|
| Venue taker/maker fee | **0.0** | **MEASURED** — all 203 active books report zero. `is_taker_fee_enabled` is TRUE with the rate at zero, so it *can* change; the scout publishes the live schedule and `bot_learn.fee_rt_for()` is the single reader. |
| Shadow fill model | crossed spread, walked against the **live order book** (`ShadowBroker._shadow_fill`) | **MEASURED per fill.** Since 2026-09-07 an unfillable order publishes **NULL** slippage + a named reason, never a fabricated 0.0. |
| Fleet round-trip cost basis | **17.49 bps mean**, p90 **398 bps** below $0.1M/day volume | **MEASURED** `(qq)`. `edge_audit.MEASURED_RT_BPS`. |
| Funding books' modelled friction | carry 15bps RT/leg-pair; Kiyosaki/Hull `RT_COST_FRAC = 0.003` (30bps) | **MODELLED, flat-conservative, declared** |
| Brain's fee basis for non-Lighter rows | `FEE_RT_DEFAULT 0.0052` (Kraken spot) | **LEGACY** — reachable only by a non-Lighter row; Lighter rows take `BRAIN_LIGHTER_FEE_RT = 0.0002` |
| Live-vs-shadow execution gap | measured continuously by `implementation_shortfall` | live arm verdict today: **`arm-drift`** (see §6) |

Measured execution gap today, live arm vs its own twin on the same coins:
mum **−0.185pp**, avo **+0.607pp**, georgia (retired arm) **−0.094pp**.

---

## 4. Data sources and update frequency

| Source | Used for | Cadence |
|---|---|---|
| `mainnet.zklighter.elliot.ai/api/v1/orderBookDetails` | universe, 24h volume, funding, market age, **margin fractions** | every scout loop (~5 min) |
| `/api/v1/candles` | all price bars | per-bot loop |
| `/api/v1/fundings` (settled) | realised funding — **quotes %/hour, not per-8h** | funding books |
| `/api/v1/orderBookOrders` | shadow fill walk + live fills | per order |
| Yahoo `query1.finance.yahoo.com` | equity dailies (retired 📊 Index Rider only) | daily |
| Hyperliquid `api.hyperliquid.xyz/info` | cross-venue funding divergence signal only | scout |
| Binance / CoinGecko / Kraken | **dashboard display only** (`compile_market_data.py`) — not a trader | 30 min |

Organ cadences from `run_all.sh`: bot loops 10–15s · scout 5 min · market pulse
30 min · evidence board 10 min · scout tuner 60 min · proprioception 15 min ·
experiment judge 60 min · immune 15 min · **golive-readiness 6 hourly** ·
allocation 30 min. Boot is deliberately staggered.

Every payload carries `updated` + `ttl_sec`; consumers go neutral on stale data
(`fleet_bus.is_fresh`).

---

## 5. Capital allocation (live, from `fleet_allocation`)

Book unit $1,000; total $16,000 nominal. Ranked on
`max(0, mean − t_crit(n)·SE)` — a **lower bound**, not a mean.

| Book | target $ | scale | era claim | n_era |
|---|---|---|---|---|
| avo shadow | 1,517 | 1.52× | 0.00821 | 29 |
| ticket taker | 1,217 | 1.22× | 0.00614 | 185 |
| mum shadow | 1,200 | 1.20× | 0.00291 | 91 |
| avo **live** | 1,197 | 1.20× | 0.00436 | 14 |
| carry | 1,031 | 1.03× | 0.00147 | 30 |
| mum **live** | 1,005 | 1.01× | 0.00169 | 91 |
| *the other 10* | 883 | 0.88× | 0.0 | — |

**Nothing is at the 0.25 probe floor** (the `(tz)` tilt fix holds) and nothing is
near the 4.0 ceiling — max scale in the fleet is 1.52×.

---

## 6. Known dependencies and failure points

**Structural dependencies**
- **Postgres** (`bot_pnl`, `bot_state`, `bot_state_history`) — every book, every
  organ, the dashboard. Single point of failure. `DATABASE_URL` must be a Railway
  **reference**, never a pasted literal (13 services went dark on one rotation).
- **The Lighter REST API** — one venue, one API, no fallback for price.
- **`golive_readiness`** — imported by ~everything. A defect here is fleet-wide.
- **`fleet_bus`** — the read client every strategy uses; contract is
  fail-safe-empty, and *every caller must read empty as "keep my configured
  list", never as "trade nothing"*.

**Live failure modes the fleet has actually paid for (all now guarded)**
1. **Deploy ≠ push.** Only `.github/workflows/railway-redeploy.yml` deploys, on a
   hardcoded path list. Real-money services need a `[deploy-live*]` marker **in
   the commit subject AND the PR title** (a squash merge drops branch subjects —
   measured on `(xe)`, which never reached avo's live arm). Verified only by the
   `extra.build` + `extra.build_n` stamp, never by a green run.
2. **Two writers on one row** — pooled two books' closes into one `n`. Guarded by
   `claim_writer` at the top of the loop + `integrity.two_writers` as a
   precondition in front of the six bars.
3. **Stale reader** — a green "Deployed" with the old container still serving,
   filtering exactly the new rows. Probe: `railway status --json` activeDeployments.
4. **Dead subshell** — a `( while true; ... ) &` organ that stops runs no handler
   and leaves every key looking healthy. Only an out-of-process age check sees it.
5. **Silent persistence failure** — `save_state` returned False for 3 days and the
   brain published fresh vitals off a frozen state.
6. **Non-finite floats** — `NaN`/`Infinity` make Postgres reject the whole `jsonb`
   write. Sanitised at the boundary.
7. **Concurrent sessions sharing a worktree** — a shared git index silently swept
   another session's edits into a commit and once destroyed a 90-line entry.
   Mitigated by `scripts/new_session_worktree.sh` + `scripts/session_commit.py`.

**Open risk flags visible on today's payload**
- `impl_shortfall` verdict **`arm-drift`** — the live/shadow pair is not on
  identical code, which weakens every paired comparison until resolved.
- 👩 mum live: `stop_reachable: **false**` (`stop_dead_above 4.17×`) and
  `headroom.reason: "liq_unpriced"` — her −4% stop is **not reachable** on the
  worst-margin book in her 104-market universe before liquidation maths bites.
  `overshoot_n: 7`, `overshoot_p90 51.7bps`.
- 🪁 kelly: **28.5% mark-to-market drawdown** against a 15% bar, and a
  pre-registered keep-or-retire read that has **already returned to Eamon** and
  is awaiting his decision.
- `fleet_immune.sick` is empty and `respiration.spo2` is 1.0 — the fleet is
  healthy in the liveness sense.

---

## 7. Audit note on method

The fleet already owns most of what a Phase-1 audit would normally have to
build: an era owner, a phantom/quarantine filter, a cluster-robust `t`, a single
critical value, a BH-FDR referee and a calibration-gated edge auditor. **This
audit imports those rather than re-deriving them.** Two independent
implementations of one rule is how this repo previously graded the same book at
`n=84/t=2.77` and `n=59/t=0.33` on the same day.
