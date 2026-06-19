#!/bin/sh
# backtest_softened.sh
# One-shot: download the data the softened v5/v6/v7 strategies need, then
# backtest all three. Run from your freqtrade project root (where user_data/ lives).
#
#   ./backtest_softened.sh                 # uses default timerange below
#   ./backtest_softened.sh 20240101-       # custom timerange (freqtrade format)
#
# Requires: freqtrade installed and on PATH, exchange network access.
set -eu

TIMERANGE="${1:-20240101-}"
PAIRS="BTC/USD ETH/USD SOL/USD XRP/USD ADA/USD DOGE/USD AVAX/USD LINK/USD DOT/USD LTC/USD BCH/USD XLM/USD ATOM/USD UNI/USD APT/USD ARB/USD OP/USD NEAR/USD INJ/USD FIL/USD"

echo "=================================================================="
echo " 1/2  Downloading Kraken data (5m/1h/1d, full history via trades)"
echo "      pairs: top-20 USD   timerange: ${TIMERANGE}"
echo "=================================================================="
freqtrade download-data --exchange kraken \
  --pairs $PAIRS \
  --timeframes 5m 1h 1d \
  --timerange "$TIMERANGE" \
  --dl-trades

echo ""
echo "=================================================================="
echo " 2/2  Backtesting the three softened-gate strategies"
echo "=================================================================="

run_bt() {
  strat="$1"; cfg="$2"
  echo ""
  echo "------------------------------------------------------------------"
  echo " Backtest: ${strat}   (${cfg})"
  echo "------------------------------------------------------------------"
  freqtrade backtesting \
    --strategy "$strat" \
    --config "user_data/$cfg" \
    --timerange "$TIMERANGE" \
    --cache none
}

run_bt DayTraderV5Gated config_v5_kraken.json   # 5m  day-trader
run_bt SwingDipV1        config_v6_swing.json    # 1d  swing dip-buyer
run_bt MomoBreakoutV1    config_v7_momo.json     # 4h  momentum/breakout

echo ""
echo "=================================================================="
echo " Done. Check each summary's: Total trades, Win%, Max Drawdown,"
echo " and Total profit %. Want more trades? lower the RSI thresholds."
echo " Drawdown too high? tighten stops before going live."
echo "=================================================================="
