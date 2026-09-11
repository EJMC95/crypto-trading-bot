# downtrend_ensemble_bot

A short-biased, multi-timeframe, ensemble-scored crypto perpetuals system.
Exchange-agnostic behind an adapter. **Backtest by default; live trading is
refused until seven independent locks are open.**

This is research and engineering infrastructure. **No claim is made here that
it is profitable.** The only numbers in this repository come from synthetic
data or from a backtest, and both are described as what they are.

---

## What must be verified before live trading

Read this section before anything else. Each line is a thing the code cannot
check for you.

1. **The adapter has been verified against the real venue.** `CcxtAdapter`
   ships with `allow_submit=False` and a `TODO(exchange)` checklist. Symbol
   format, tick and step sizes, reduce-only semantics, stop-order types,
   leverage/margin-mode calls and the exact error the venue returns on a
   rejected order all differ per exchange, and every one of them can turn a
   protective order into a naked one. **Verify each on a testnet or with the
   smallest possible size before trusting any of them.**
2. **A reduce-only protective stop actually rests at the venue** after an
   entry fills — confirmed by reading the venue's own open-order list, not by
   the absence of an error.
3. **The 30-day paper soak was run on THIS configuration.** The gate compares
   a fingerprint of the rules (risk, strategy, regime, execution, symbols). A
   soak on different settings does not certify these ones, and the gate says
   so rather than quietly accepting it.
4. **Reconciliation is clean.** Positions at the venue and positions in the
   local store agree, and every one carries a stop. Reconciliation REPORTS;
   it never repairs, because a repair that guesses wrong writes a real order.
5. **The account is one you can afford to lose entirely.** Use a dedicated
   sub-account and a dedicated API key with the narrowest permissions the
   venue offers — trade only, **no withdrawal**.
6. **`runtime/KILL_SWITCH` works.** Create the file and watch entries halt.
   Test the thing that stops it before you need it.
7. **`FLATTEN_CONFIRMATION=CLOSE_ALL_POSITIONS downtrend flatten` works**, on
   a position you opened deliberately for the purpose.
8. **Funding, fees and slippage have been measured on the venue you will
   trade**, not assumed from `config/*.yaml`. The backtest's defaults are
   plausible, not measured.
9. **Someone is watching.** Nothing here pages a human. There are no external
   notifications by design (spec 16) — the terminal dashboard is the whole
   monitoring surface.

**What the paper soak cannot tell you.** Paper fills a limit order on a touch;
a real one may sit behind a queue and never fill. It does not simulate venue
downtime, rate limits, rejected signed payloads, funding settled at the mark,
or a partial fill beyond the configured rate. **Every one of those makes paper
look better than live.** A paper report is an upper bound on the same rules run
for real.

---

## Install and first run

```bash
cd downtrend_ensemble_bot
pip install -e .            # or: pip install pyyaml
export PYTHONPATH=src

python -m downtrend_bot.cli --config config/backtest.yaml validate-config
python -m downtrend_bot.cli --config config/backtest.yaml backtest
```

With no `--data` directory the backtest runs on **synthetic** data and says so
on stderr. A synthetic result measures the machinery, not a market.

The example tapes are generated rather than committed — shipping megabytes of
regenerable JSON buys nothing, and the same seed gives byte-identical tapes:

```bash
python -m downtrend_bot.cli --config config/backtest.yaml make-examples
```

```bash
# on any tapes: <dir>/<SYMBOL>_<tf>.json, rows of [ts, o, h, l, c, v]
python -m downtrend_bot.cli --config config/backtest.yaml backtest --data data/examples
python -m downtrend_bot.cli --config config/backtest.yaml walk-forward --data data/examples
python -m downtrend_bot.cli --config config/backtest.yaml sensitivity --data data/examples
```

`backtest` exits **2** when the robustness gate refuses the configuration, so a
CI job cannot go green on a result the gate rejected.

---

## Commands

| command | what it does |
|---|---|
| `backtest` | event-driven replay, full metrics, Monte Carlo, robustness gate |
| `walk-forward` | rolling train/validate/test folds, graded on the test slice only |
| `sensitivity` | one-parameter-at-a-time sweep; reports the CURVE, never a winner |
| `paper` | the 30-day soak; identical code path to live, `submit=False` |
| `live` | **refused by default.** Seven locks, one of them a human at a terminal |
| `report` | what the store recorded: positions, trades, recent decisions |
| `health` | strategy states, kill-switch status |
| `flatten` | close everything; needs `FLATTEN_CONFIRMATION=CLOSE_ALL_POSITIONS` |
| `validate-config` | check a config against every hard ceiling |
| `make-examples` | write the reproducible synthetic example tapes |
| `check-dashboard` | certify a dashboard patch as append-only (spec 28) |

---

## The seven locks on live trading

All of them, together, and they are deliberately of **different kinds** — a
file, two environment variables, a human, an artefact, a venue read, a
capability probe. Locks of the same kind fail together; three environment
variables would all be defeated by one careless `export`.

1. `mode: live` in the config file
2. `ENABLE_LIVE_TRADING=true`
3. `LIVE_CONFIRMATION=I_UNDERSTAND_THE_RISK`
4. an interactive phrase typed at the terminal (`START LIVE TRADING`)
5. a completed 30-day paper soak report **from this configuration**
6. a clean reconciliation against the venue
7. an adapter that can place a reduce-only protective stop

Plus: no `runtime/KILL_SWITCH`, and a configuration inside every hard ceiling.

There is **no `--yes` flag**, and adding one would defeat lock 4. The only
bypass in the package is `PAPER_SOAK_OVERRIDE`, which relaxes lock 5 alone, is
recorded in the gate's own check map, and is printed in the banner — so a
bypassed soak can never look like a passed one.

---

## Credentials

Environment only. **Never in source, never in a config file, never in a log.**

```bash
cp .env.example .env     # then fill it in, and never commit it
```

Redaction happens at the logging **handler**, below every call site, so a
module that logs the wrong thing is still safe — plus a filter that redacts any
32+ character token wherever it appears, because the realistic accident is a key
interpolated into a message, not one passed as a structured field.

---

## Architecture

```
src/downtrend_bot/
  models.py           domain objects; the filesystem boundary (safe_filename)
  config.py           dataclasses, HARD_CEILINGS, validate(), LiveGate
  logging_setup.py    JSON logs with handler-level secret redaction
  indicators.py       pure, CAUSAL indicators (+ assert_causal)
  regime.py           6-state market regime with asymmetric hysteresis
  signals.py          the 100-point ensemble; SeriesCache
  risk.py             position sizing, caps, lockouts
  portfolio.py        book, correlation/effective-bets, trade budgets
  health.py           per-strategy health states, system checks, kill switch
  changepoint.py      z-score + CUSUM detector with hysteresis
  execution.py        order construction, reduce-only exits, the trail
  exchange_adapter.py the ABC, a MockExchange, a disabled ccxt adapter
  store.py            SQLite record of intent + reconciliation
  backtester.py       event-driven engine, metrics, Monte Carlo, robustness
  walk_forward.py     rolling validation + the sensitivity sweep
  trader.py           ONE loop, shared by paper and live
  paper_trader.py     the soak and its report
  live_trader.py      the gate; everything here is a way to say no
  reporting.py        terminal renders; no external notifications
  dashboard_safety.py spec 28: a VERIFIER, never an editor
  synthetic.py        deterministic tapes for tests and the offline demo
  cli.py              the command line
```

### The scoring ensemble (100 points)

| component | weight | what earns it |
|---|---|---|
| regime | 25 | market regime AND the symbol's own 4h regime agree with the side |
| trend | 20 | EMA alignment (12) + measured ADX strength (8) |
| breakdown | 20 | a closed break of structure, then a retest that **rejects** |
| momentum | 15 | RSI **band** (7.5) + MACD (4.5) + ROC (3) |
| volume | 10 | breakdown volume above its rolling average |
| derivatives | 5 | funding/OI, and crowding scores **nothing** on its own |
| quality | 5 | spread, volatility percentile, stop width |

Two of these are worth stating plainly because they are where a short-biased
system usually goes wrong:

* **RSI is a band, not an extreme.** An RSI of 12 means the fall already
  happened. It earns zero from the band limb — "oversold" is a reason a short
  is LATE, not a reason to take one.
* **The breakdown score decays with extension** and reaches zero past
  `max_entry_distance_atr`. The rule is "break, then retest" and never "enter
  after it has already moved".

---

## Things this package refuses to do

* **Emit an unrestricted market order.** The most aggressive thing it builds is
  a marketable limit with an explicit slippage cap, and only when spread and
  liquidity are inside their limits. An unknown spread is never marketable —
  that is exactly when crossing is most expensive.
* **Widen a stop.** The trail is monotone toward the position, on both sides.
  A regime change can tighten a stop or close a position; it can never make an
  open trade riskier than it was when it was sized.
* **Carry an unprotected position.** Entry, then stop, then targets. If the
  stop cannot be attached, the position is closed immediately.
* **Retry a signed order blindly.** An order whose response we did not see may
  have reached the venue; resending it can double the position.
* **Emulate a missing venue feature.** A missing reduce-only or stop capability
  raises `NotSupported` rather than substituting something unsafe.
* **Clamp an out-of-range setting.** `validate()` REJECTS. Clamping is the
  dangerous choice: the operator asked for 10x, got 3x, and was told nothing.
* **Modify an existing dashboard.** `dashboard_safety` certifies a patch as
  append-only against a verified `/pnl.json`, and contains no writer at all.
* **Average, martingale, or add to a loser.** There is no add-to-position path.

---

## Known limitations

* **The only data this repository ships is synthetic.** Every number produced
  by `backtest`, `walk-forward` and `sensitivity` out of the box describes a
  generated tape. A generated downtrend is a tape whose regime was chosen here;
  running a short-biased system on it and reporting a profit measures the
  generator.
* **No edge is claimed or demonstrated.** The robustness gate exists to refuse
  results, and on the shipped synthetic data it does.
* **The ccxt adapter is a scaffold.** It is disabled, unverified against any
  real venue, and carries a checklist rather than an endorsement.
* **Correlation is measured on close-to-close returns over the signal
  timeframe.** It is a fair estimate in calm conditions and understates
  co-movement in a crash, which is when it matters most.
* **Funding in the backtest is a constant rate**, not the venue's realised
  8-hourly settlements. A short book earns funding, so this is the direction
  that flatters — treat the funding line as an estimate, not a receipt.
* **Paper trading does not model queue position.** See above.
* **The change-point detector is calibrated on synthetic data.** Its thresholds
  are plausible defaults, not measured ones.
* **Nothing pages a human.** By design (spec 16), and it means an unattended
  run is exactly as unattended as it sounds.

## Tests

```bash
python -m pytest tests/ -q
```

The suite is written to fail on the mistakes this package has actually made,
not on its happy paths. Several tests carry the incident that motivated them in
their docstring — including a scoring component that was **structurally
unreachable** (proved: 0 hits in 400,000 random bar-sets), a stop that could
land on the wrong side of its own entry, and a metrics function whose CAGR
calculation could kill the report that called it.
