# Auto-retrainer — "learn from live data" for the Freqtrade bots

`freqtrade_retrain.py` runs as its **own isolated Railway service** (`freqtrade-trainer`,
built from `Dockerfile.trainer`) so heavy hyperopt never competes with the live
`freqtrade-bots` container.

## What it does, every cycle (default every 48h)
For each tunable strategy:
1. Downloads the latest Kraken data (the same live market the bots trade) — via the
   trades path, because Kraken serves no historical OHLCV.
2. Runs a bounded **hyperopt** over a TRAIN window to find candidate parameters.
3. **Backtests both** the candidate and the current ("incumbent") params on a
   held-out RECENT window the optimiser never saw.
4. **Promotes only if the candidate beats the incumbent out-of-sample** — more
   profit, drawdown not materially worse, and enough trades to be meaningful.

Everything stays dry-run / paper. The script never places an order or moves money.

## Strategies trained
- `SwingDipV1` (4h) and `MomoBreakoutV1` (4h) — entry/exit params are `optimize=True`.
- **Not** trained: `ImprovedStrategyV4` (no tunable params) and `DayTraderV5Gated`
  (its 1d EMA200 regime filter needs ~200 days of daily candles; on Kraken that
  means downloading ~200 days of raw trades — not feasible). These keep trading on
  their current rules.
- Regime/trend **safety** parameters are deliberately left `optimize=False` so
  optimisation can never loosen the core risk controls.

## Safety: SHADOW mode by default
With no `GITHUB_TOKEN` (or `RETRAIN_PROMOTE` not `true`) the trainer runs in
**SHADOW** mode: it computes and logs what it *would* promote but changes nothing
live. Watch the Railway logs for `decision=PROMOTE` / `SHADOW ... would promote`
lines for a couple of cycles before trusting it.

### To enable autonomous promotion
1. Create a GitHub fine-grained PAT with **Contents: read/write** on
   `EJMC95/crypto-trading-bot`.
2. On the `freqtrade-trainer` service → Variables, set:
   - `GITHUB_TOKEN = <the PAT>`
   - `RETRAIN_PROMOTE = true`

When enabled, a promoted `user_data/strategies/<Strategy>.json` is committed and
pushed to GitHub, which auto-redeploys `freqtrade-bots` with the new params.

## Key env vars (all optional)
| var | default | meaning |
|-----|---------|---------|
| `RETRAIN_INTERVAL_HOURS` | 48 | hours between cycles |
| `RETRAIN_EPOCHS` | 60 | hyperopt epochs |
| `RETRAIN_PAIRS` | `BTC/USD ETH/USD` | pairs to optimise on |
| `RETRAIN_TRAIN_DAYS` | 35 | optimisation window |
| `RETRAIN_HOLDOUT_DAYS` | 10 | out-of-sample validation window |
| `RETRAIN_STARTUP_DAYS` | 50 | extra history for long-EMA startup candles |
| `RETRAIN_DATADIR` | (unset) | persistent volume path, e.g. `/data`, so downloads are incremental |
| `RETRAIN_MIN_TRADES` | 4 | min holdout trades to consider a candidate |
| `RETRAIN_DD_TOLERANCE` | 0.03 | how much worse drawdown may be (3pp) |
| `RETRAIN_ONLY` | (all) | comma-list to restrict strategies |
| `RETRAIN_ONCE` | false | run one cycle and exit (for testing) |

## Note on the first cycle
With a fresh data volume the first cycle downloads ~95 days of Kraken trades per
pair and can take an hour or more (Kraken rate-limits trade history). Attach a
Railway **volume** at `/data` and set `RETRAIN_DATADIR=/data` so later cycles only
fetch the small daily delta.
