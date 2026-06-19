#!/bin/sh
# backtest_softened.sh — download data + backtest v5 (futures, both directions),
# v6 (spot daily long-only) and v7 (spot 4h range/sideways) on the top-20 pairs.
# Run from the freqtrade project root (where user_data/ lives).
#
#   ./backtest_softened.sh                 # default timerange below
#   ./backtest_softened.sh 20240101-       # custom timerange (freqtrade format)
#
# Requires: freqtrade installed + on PATH, exchange network access.
set -eu

TIMERANGE="${1:-20240101-}"

SPOT_PAIRS="BTC/USD ETH/USD SOL/USD XRP/USD ADA/USD DOGE/USD AVAX/USD LINK/USD DOT/USD LTC/USD BCH/USD XLM/USD ATOM/USD UNI/USD APT/USD ARB/USD OP/USD NEAR/USD INJ/USD FIL/USD"
FUT_PAIRS="BTC/USD:USD ETH/USD:USD SOL/USD:USD XRP/USD:USD ADA/USD:USD DOGE/USD:USD AVAX/USD:USD LINK/USD:USD DOT/USD:USD LTC/USD:USD BCH/USD:USD XLM/USD:USD ATOM/USD:USD UNI/USD:USD APT/USD:USD ARB/USD:USD OP/USD:USD NEAR/USD:USD INJ/USD:USD FIL/USD:USD"

echo "=================================================================="
echo " 1/3  Download SPOT data (v6 daily, v7 4h) — top 20 pairs"
echo "=================================================================="
freqtrade download-data --exchange kraken \
  --pairs $SPOT_PAIRS --timeframes 4h 1d --timerange "$TIMERANGE" --dl-trades

echo "=================================================================="
echo " 2/3  Download FUTURES data (v5: 5m + 1h + 1d) — top 20 pairs"
echo "      (unavailable futures markets are skipped automatically)"
echo "=================================================================="
freqtrade download-data --exchange kraken --trading-mode futures \
  --pairs $FUT_PAIRS --timeframes 5m 1h 1d --timerange "$TIMERANGE" || \
  echo "  ! futures download had issues (some pairs may lack Kraken futures markets) — continuing"

echo "=================================================================="
echo " 3/3  Backtest all three"
echo "=================================================================="

echo ""; echo "----- v5 DayTraderV5Gated (FUTURES, long+short, 5m) -----"
freqtrade backtesting --strategy DayTraderV5Gated \
  --config user_data/config_v5_kraken.json --timerange "$TIMERANGE" --cache none || \
  echo "  ! v5 futures backtest failed — likely Kraken futures markets/data unavailable. See note below."

echo ""; echo "----- v6 SwingDipV1 (SPOT, long-only, 1d) -----"
freqtrade backtesting --strategy SwingDipV1 \
  --config user_data/config_v6_swing.json --timerange "$TIMERANGE" --cache none

echo ""; echo "----- v7 MomoBreakoutV1 (SPOT, range/sideways, 4h) -----"
freqtrade backtesting --strategy MomoBreakoutV1 \
  --config user_data/config_v7_momo.json --timerange "$TIMERANGE" --cache none

echo ""
echo "=================================================================="
echo " Done. Check each summary: Total trades, Win%, Max Drawdown, Profit%."
echo " v5 should now show BOTH long and short trades. v7 should show many"
echo " more (range buys). If v5 errored, your account/exchange may not have"
echo " Kraken Futures — set config_v5_kraken.json trading_mode back to 'spot'"
echo " and pairs back to BTC/USD form to run it long-only."
echo "=================================================================="
