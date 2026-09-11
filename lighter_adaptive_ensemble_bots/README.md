# lighter_adaptive_ensemble_bots

A **backtest-first**, long *and* short perpetual-futures trading system for the
**Lighter** exchange. Modular, paper- and shadow-capable, and gated so that live
trading requires several deliberate acts by a human.

**No claim of profitability is made anywhere in this repository.** The system is
optimised for measured edge, explainability, execution quality and protection
against strategy decay. The evidence that shaped it is deliberately mixed: two of
the three cells it started from were **refuted** — see
[`../STUDY_SHORT_MIRRORS_2026-09-10.md`](../STUDY_SHORT_MIRRORS_2026-09-10.md).

---

## Why this exists

It began as a narrower request: *two short books that mirror the fleet's
long-only 👩 mum and 🙏 avo.* Both mirrors were measured on Lighter's own tape
before a line of bot code was written, and **both failed their own gates**:

* **the mum mirror** (short an overbought coin outside a downtrend, 1h) —
  −0.102%/trade at t=−2.08 over 2,744 trades, an excess over matched-random
  entries of **+0.037%/trade at P=0.187**, and the entire loss is friction
  (0 bps/side → −0.002%). It wins 69% of its trades and loses money.
* **the avo mirror** (short a rip into the upper band inside a downtrend, 4h) —
  a genuine **+0.319%/trade excess over random** and a plateau across RSI bars,
  but t=+0.93, a negative second half, and **days-to-gate 2,092** against a
  60-day bar.

The second result is the interesting one. It is not a bad idea; it is **one
construct**, and with `t = S_d·√T` a single sleeve earns a *decision* more slowly
by the square. That is what this system is: several independent setups scored
together, both directions, across a venue-wide universe, with the decidability
arithmetic in the reporting instead of discovered a year later.

The refutation is enforced in code, not just recorded: `momentum_component`
caps RSI at 15 of 100 points and scores an RSI extreme at **zero** for a short,
so "overbought" can never by itself be a reason to sell.

---

## Quick start

```bash
cd lighter_adaptive_ensemble_bots
pip install -e ".[dev]"          # or: pip install lighter-sdk pandas numpy PyYAML pytest

python -m lighter_bots capabilities                                  # what the SDK can do
python -m lighter_bots discover-markets --config config/paper.yaml   # live metadata
python -m lighter_bots validate-config  --config config/backtest.yaml
python -m lighter_bots backtest         --config config/backtest.yaml
python -m lighter_bots walk-forward     --config config/backtest.yaml --sensitivity
python -m lighter_bots paper            --config config/paper.yaml --cycles 3
python -m lighter_bots shadow           --config config/paper.yaml --cycles 3
python -m lighter_bots health           --config config/paper.yaml
python -m lighter_bots report           --date 2026-09-10
python -m lighter_bots kill-switch      --config config/paper.yaml --reason "manual halt"
python -m lighter_bots live             --config config/live.yaml   # refuses unless everything agrees
python -m lighter_bots flatten          --config config/live.yaml   # needs FLATTEN_CONFIRMATION
pytest -q
```

`--offline` on any data command uses the cached metadata snapshot instead of
querying the venue.

---

## Lighter integration

Everything is read from the **installed SDK and the live API** — no invented REST
paths, no invented method names, no CCXT assumptions. Regenerate the capability
report at any time with `python -m lighter_bots capabilities`; the copy in
[`docs/CAPABILITY_REPORT.txt`](docs/CAPABILITY_REPORT.txt) was produced on
this machine.

* `lighter-sdk` **1.1.2** (the package's own `lighter.__version__` still reads
  `1.0.0`; both are reported, because quoting either alone is misleading)
* base URL `https://mainnet.zklighter.elliot.ai`, chain id **304** (testnet 300)
* **33 of 33** probed capabilities available, **0 problems**

Order types `limit=0 market=1 stop_loss=2 stop_loss_limit=3 take_profit=4
take_profit_limit=5 twap=6` · time-in-force `ioc=0 gtt=1 post_only=2` ·
grouping `oto=1 oco=2 **otoco=3**`.

`otoco` is load-bearing: it lets the **entry and its protective stop go as one
transaction**, so there is no window in which a filled position has no stop.
Where grouping is unavailable the stop is placed immediately after the fill, and
if that placement fails the entry is cancelled and new entries halt.

### Two unit traps, both encoded and pinned by tests

1. **Margin fractions are BASIS POINTS.** `maintenance_margin_fraction: 120`
   means **1.20%**, and `min_initial_margin_fraction: 200` means 2.00% ⇒ a
   **50x** market maximum. Maintenance margin is *read*, never derived from the
   initial fraction. Misreading this scales every liquidation estimate by ~100x.
2. **The settled funding series is PERCENT PER HOUR**, not a per-8h fraction.

### Credentials

Environment only, never source, never logged:

```
LIGHTER_BASE_URL  LIGHTER_CHAIN_ID  LIGHTER_ACCOUNT_INDEX
LIGHTER_API_KEY_INDEX  LIGHTER_API_PRIVATE_KEY
```

Use a **dedicated bot key**, not a wallet key with broader permissions. The JSON
log formatter redacts secrets at the *handler*, below every call site, and
scrubs any 40+ character hex run — so a careless f-string in a strategy module
still cannot leak a key, a signature or a signed transaction body.

### Nonce custody

A Lighter API key carries its own nonce sequence. `nonce_manager.py`:

* one lock per `(account, api_key)` — signing is serialised, never concurrent;
* the nonce is **persisted before it is handed out**, so a crash can burn one
  (cheap) and can never re-issue one (not cheap);
* on restart the local high-water mark is reconciled against the venue and the
  **higher** of the two wins — a stale venue read cannot walk us backwards;
* a failed transaction is recorded **UNKNOWN**, never rolled back, because a
  request that timed out may still have landed. The system then refuses to sign
  until an operator reconciles.

Tested with six concurrent threads taking 150 nonces: zero collisions.

---

## Architecture

```
src/lighter_bots/
  config.py           hard ceilings + THE live gate (one function, fails closed)
  models.py           typed domain objects; side is "long"/"short" in our code
  logging_setup.py    structured JSON + handler-level secret redaction
  market_metadata.py  discovery, versioned snapshots, tick/step/leverage/margin
  lighter_adapter.py  capability report, native adapter, mock adapter
  nonce_manager.py    durable, serialised nonce allocation
  websocket_client.py reconnect/backoff/resubscribe/sequence/staleness
  data.py             candles, caching, THE incomplete-bar rule, retry+backoff
  indicators.py       causal indicators + assert_causal
  regime.py           six-state engine with hysteresis
  signals.py          the ensemble: setups, 0-100 scoring, both sides
  strategy_health.py  ACTIVE/THROTTLED/PAUSED/RECOVERY + overtrading budgets
  portfolio.py        exposure, correlation groups, effective bets
  risk.py             sizing from the STOP; every cap; every refusal has a reason
  liquidation.py      closed-form isolated liq; refuses cross without context
  execution.py        our vocabulary -> Lighter's, in exactly one place
  backtester.py       event-driven, no look-ahead, gaps/fees/funding/partials
  walk_forward.py     rolling folds, sensitivity, selection premium, robustness
  paper_trader.py     PAPER + SHADOW runners (no signing, same decision code)
  live_trader.py      the only module that can sign; refuses by default
  reporting.py        reports + local terminal dashboard
  health.py           system health, fails closed
  dashboard_patch.py  append-only safety for the EXISTING fleet dashboard
```

### The signal ensemble

Score **0–100**, weights summing to 100 by construction (pinned by a test):

| component | weight | what it measures |
|---|---|---|
| regime | 25 | does the market state agree with this direction |
| trend | 20 | EMA alignment (12) + measured ADX strength (8) |
| structure | 20 | the setup's own quality |
| momentum | **15** | RSI *band*, MACD histogram, ROC — **capped on purpose** |
| volume | 10 | participation vs the 20-bar mean |
| derivatives | 5 | funding paying our side, OI confirming |
| liquidity | 5 | spread inside limits; unknown scores **zero** |

Setups (each available long and short): **trend continuation**, **pullback
continuation**, **breakout/retest** (and its breakdown mirror). A long wants RSI
40–68 and a short 35–60 — *bands*, not extremes.

### Regime states and permissions

`BULLISH · BEARISH · NEUTRAL · HIGH_VOLATILITY · PANIC · DATA_UNRELIABLE`

Transitions need **two closed-candle confirmations**, with one asymmetry that is
the whole design: the three "something is wrong" states **arm immediately** and
still need confirmations to clear. Fast to protect, slow to relax.

| regime | long | short |
|---|---|---|
| BULLISH | 1.00 | 0.25 |
| NEUTRAL | 0.75 | 0.75 |
| BEARISH | 0.25 (tactical, score ≥ 75) | 1.00 |
| HIGH_VOLATILITY | 0.50 | 0.50 |
| PANIC / DATA_UNRELIABLE | **0.00** | **0.00** |

`DATA_UNRELIABLE` is a first-class state rather than an exception: a stale feed
or a failed reconciliation produces a *regime the system already knows how to
refuse to trade in*, not a traceback inside a loop that then continues.

### Risk, leverage and liquidation

```
risk_amount = equity × risk_per_trade × regime_mult × health_mult
quantity    = risk_amount / |entry − stop|
```

**Leverage is not a reason to take more risk.** It only decides whether the
already-sized position fits in the available margin, and it is capped at
`min(config, account, market)`. If liquidation would sit inside the stop, the
leverage is **walked down** until the stop clears it by ≥ 2 ATR — and if no
admissible leverage exists, the trade is **refused** rather than silently
falling back to 1x. Measured example: an $8.75-wide stop on a $77,000 entry
takes leverage from 10x to 8x automatically.

Isolated liquidation is closed-form and derived in the module:
`P_liq = E(1 − 1/L)/(1 − mmf)` long, `E(1 + 1/L)/(1 + mmf)` short.
**Cross margin has no per-position answer**, so `estimate()` refuses unless
account equity and total maintenance are supplied.

### Strategy health

Per `(strategy, symbol, direction, regime, version)`. **Degradation is fast,
promotion is slow.** `PAUSED` never returns straight to `ACTIVE`; it goes through
`RECOVERY` at 25% risk with the highest bar and an explicit, recorded validation.

Overtrading is separate and binds even a healthy strategy: deterministic signal
IDs (so a restart cannot double-enter), per-market and per-strategy daily caps,
a portfolio hourly cap, cooldowns keyed on the **symbol** rather than the
strategy — after a loss, the *market* is what just proved hostile — and a global
lockout after four losses in a day.

---

## Two real bugs the tests caught

Recorded because they are the reason to write tests that can fail:

1. **A single losing trade paused every strategy.** Drawdown was normalised by
   the strategy's own cumulative P&L, which starts at zero — so one −$1 trade
   read as a 100% drawdown. Now measured against a **reference account equity**
   captured once; when no reference is available the drawdown condition is
   **skipped and declared**, never fired.
2. **Every overtrading budget silently did nothing in a backtest.** Entry
   pruning ran against `time.time()`, so historical timestamps were deleted the
   moment they were written. A backtest would have reported a trade rate the
   live system could never take, and nothing would have said so.
3. **A backtest overwrote live strategy health and the trade budget.** Same
   `state/` directory, and `record()` writes — so a replayed losing streak
   would have arrived as a PAUSED live strategy.
4. **Walk-forward measured its span across all timeframes**, so a fold landed
   where the execution tape did not exist and reported *"0 trades"* — which
   reads as a strategy declining to trade and is actually "there is no tape
   here".

And two found by CodeQL on the pull request, both fixed with mutation-verified
tests (6 of 6 mutations killed):

5. **Venue-supplied symbols reached a filesystem path.** Market symbols come
   from Lighter's own `orderBookDetails` response and were interpolated
   straight into cache filenames (`f"{symbol}_{tf}.json"`). A venue listing a
   market with an unusual name could therefore choose a path outside the data
   directory — reachable in BACKTEST mode with no credentials configured at
   all. `models.safe_filename` (allowlist, not denylist) plus
   `models.contained_path` (sanitise, then resolve and verify) are now the one
   owner for every path this package writes.
6. **The live gate copied the entire process environment**, private key
   included, onto a long-lived object that `preflight` partially renders. It
   now keeps exactly the six names it reads, declared in `_GATE_ENV_KEYS`.

All six have tests that fail if they return.

---

## What is modelled, and what is not

**Modelled:** venue tick/step precision · maker/taker fees from config · funding
per holding hour · spread · slippage · latency · partial fills · order expiry ·
**stop gaps** (a stop that gapped fills at the bar's *open*, not the stop price)
· leverage and margin · liquidation · rejected orders · regime transitions ·
strategy throttling and pausing.

**Not modelled, stated rather than hidden:** queue position for post-only fills
(approximated by requiring the limit to be touched plus a configurable miss
rate) and cross-market margin contagion.

**No look-ahead, structurally.** Higher-timeframe series are sliced with
`ts + tf_seconds <= clock`; a decision at bar *i* fills at bar *i+1*'s open. The
indicator precomputation that makes the backtester fast is licensed by
`assert_causal` — every indicator's value at bar *i* is byte-identical whether
computed over `[0..i]` or `[0..N]`. A test plants a spike in the **future** and
requires the result to be unchanged.

---

## Existing fleet dashboard (spec section 17)

**This package modifies no existing dashboard entry and no existing bot
configuration.** `SLOW_LOOP`, `STALE_SECONDS`, `CURRENT_BOTS`, `EXPECTED`,
`LABELS` and the existing filters are untouched.

What it *does* ship is the verifier that would make such a patch provable:
`dashboard_patch.py` snapshots `/pnl.json`, refuses any diff touching a
protected name, enforces append-only merges, and verifies every pre-existing bot
row afterwards — treating an **unreadable feed as a failure**, never as "nothing
changed". A baseline read of the live feed (15 bot rows) is in
`docs/pnl_baseline.json`.

---

## Measured results, and what they say

**Run on Lighter's own tape, reported exactly as they came out.** None of this
is a claim of profitability; two of the three readings are negative.

### 1. An 8-market, 31-day backtest — and the robustness gate refuses it

`+0.851%` total return, Sharpe `0.748`, max drawdown `5.33%`, 162 trades,
`1` liquidation violation (a gap through a stop *and* through the estimated
liquidation price — counted, not hidden).

```
ROBUSTNESS: REFUSED
  - SOL carries 145% of P&L (> 60%)
  - ZEC carries 176% of P&L (> 60%)
  - top 3 trades are 261% of P&L (> 80%): tail-dependent
  - halves disagree (h1 +246.02 / h2 -160.90)
```

A positive number that the system's own gate declines to accept is the whole
point of having the gate.

### 2. A real 180/60/60 walk-forward — and the universe flips the sign

On 354 days of 1h tape: **+0.27% on six markets, −1.56% on four.** Same rule,
same window, same split; only the traded universe differs. Universe choice is
not a detail, and a single walk-forward number quoted without it is not a
result.

### 3. The parameter sweep — every cell is negative

21 cells over the full 354-day, 4-market tape. Returns span **−2.9% to −11.4%**
and Sharpe **−0.27 to −1.34**. **There is no configuration in this sweep that
makes money on this tape.** The selection premium is **+0.66 Sharpe units** —
that is what picking the best cell buys before any out-of-sample tape is seen,
and it is larger than the spread most people would call an edge.

Read together, the three readings say: the machinery works, the risk controls
bind, and **the edge is not established.** That is the honest state of it.

### Two knobs the sweep proved INERT

The sweep is also a lever audit, and it found two settings that change nothing:

* **`strategy.minimum_reward_risk` is structurally inert.** 1.2 / 1.4 / 1.8 give
  byte-identical results, because `signals.evaluate` places TP2 at a fixed
  multiple of the stop (`tp2_r`), so reward/risk is ~2.0 for *every* signal by
  construction. The bar can never bind. Fixing it means deriving targets from
  **structure** (the next swing or range boundary) rather than from R — a design
  change that needs its own measurement, so it is DECLARED here rather than
  quietly patched. `test_signals.py::test_reward_risk_is_currently_structurally_constant`
  pins the current behaviour so the next session cannot miss it.
* **`risk.max_leverage` above ~5 is inert on this tape.** 5 / 8 / 10 are
  identical, because sizing comes from the stop and the notional caps bind
  first. Raising the leverage ceiling does nothing here — which is exactly what
  the design intends and worth seeing measured rather than assumed.

---

## What must be verified before live trading on Lighter

Read this section before risking money. Every line is a real failure mode.

* **Backtest performance is not a guarantee.** Past tape, modelled fills, and a
  universe chosen with hindsight. The robustness gate in this package exists
  because a good-looking backtest is the normal case, not the exceptional one.
* **Markets can gap through stops.** A stop is an instruction, not a price. This
  system models gap fills at the bar's open and still cannot promise the fill
  you assumed.
* **10x leverage can cause rapid losses and liquidation.** At 10x a 10% adverse
  move is the entire position. The stop-to-liquidation buffer reduces the chance
  the exchange closes you before your own rule does; it does not remove it.
* **Funding, fees, slippage and maintenance margin matter**, and on a
  high-turnover strategy they dominate. The mum-mirror cell above is a worked
  example: profitable at zero friction, losing at the real number.
* **Lighter's API and order semantics may change.** Market IDs, tick sizes,
  minimum sizes, leverage limits, margin fractions and fees are read live and
  snapshotted with a version hash *because* they change.
* **Exchange-native protective orders must be verified before live use** —
  actually placed and actually cancelled on a real account. A capability report
  says the SDK exposes the method; it does not prove the venue accepts your
  order today.
* **A strategy can stop working when conditions change.** That is what the
  health state machine is for, and it is a mitigation, not a cure.
* **This system must be independently reviewed** before meaningful capital is
  risked. It has not been.
* **Start with a small, predefined allocation and hard loss limits**, and treat
  the first live weeks as a continuation of the soak.

### Live safeguards currently in force

`live` refuses to start unless **all** of the following hold:

`ENABLE_LIVE_TRADING=true` · `LIVE_CONFIRMATION=I_UNDERSTAND_THE_RISK` · an
interactive confirmation typed at the prompt · account index, API key index and
private key configured · no `runtime/KILL_SWITCH` · valid cached market metadata
· account reconciled with the venue · native protective-order capability
verified · nonce manager healthy · risk inside `HARD_CEILINGS` · **30 days and
100 valid paper/shadow signals** of soak.

Additionally, and by design in this build: **`NativeLighterAdapter` is
constructed with `allow_signing=False` everywhere in the CLI.** It builds,
validates and reports every transaction and sends none. Enabling signing is a
deliberate code change, not a configuration flag — which is the last safeguard
still in place after every other one is satisfied.
