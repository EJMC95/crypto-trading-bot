# TrendMomoV1.py
#
# WHAT IT IS: a fast TREND-FOLLOWER on daily candles. It goes long when the
# 20-day SMA crosses ABOVE the 50-day SMA (momentum turning up) and exits when
# the 20-day crosses back BELOW the 50-day (momentum rolling over). It lets
# winners run -- no take-profit ladder -- and only uses a wide stop as a backstop.
#
# WHY IT EARNED ITS PLACE: out of 11 models trialled on 3yr daily BTC+ETH data,
# this was the only one that ranked top on a RISK-ADJUSTED basis (Sharpe/Calmar)
# on BOTH coins, and it survived a walk-forward + parameter robustness check:
#   - Walk-forward (three ~1yr windows): ETH positive in all 3 (incl. two where
#     buy&hold lost ~30%); BTC positive in 2 of 3, and in its losing year still
#     lost far less than buy&hold. Momentum's known weak spot is a choppy
#     downtrend (BTC 2025-26) -- it gets whipsawed there. Expect that.
#   - Parameter sweep: every neighbouring MA pair (10/30 ... 30/70) was
#     profitable on both coins. 20/50 is a deliberate middle choice, NOT the
#     best-fit pair -- chosen to avoid overfitting (the V3 lesson).
#
# HONEST EXPECTATION: it is NOT a buy&hold beater in a clean bull (it enters
# late and exits late). Its edge is sidestepping big drawdowns -- it spends ~half
# its time in cash and dodges the worst declines. It WILL get chopped in flat,
# sideways markets. Diversifier + drawdown-reducer, not a money printer.
#
# Spot / long-only. Round-number settings (anti-overfit), not hyperopt-tuned.

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter


class TrendMomoV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"                 # daily candles -> swing trend-follow
    can_short = False

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 1},
            {"method": "MaxDrawdown", "lookback_period_candles": 40, "trade_limit": 4,
             "stop_duration_candles": 5, "max_allowed_drawdown": 0.25},
        ]

    # Tunable later, but defaults are the robustness-checked middle pair.
    fast_ma = IntParameter(10, 30, default=20, space="buy", optimize=False)
    slow_ma = IntParameter(40, 70, default=50, space="buy", optimize=False)

    # Let winners run: ROI effectively disabled. Exit comes from the trend flip.
    minimal_roi = {"0": 100}

    # Wide backstop only. The MA-cross exit is the primary risk control.
    stoploss = -0.15

    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 60        # need 50 daily candles for the 50d SMA

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma_fast"] = ta.SMA(dataframe, timeperiod=self.fast_ma.value)
        dataframe["sma_slow"] = ta.SMA(dataframe, timeperiod=self.slow_ma.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # BUY when fast SMA crosses up through slow SMA (momentum turns up).
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["sma_fast"], dataframe["sma_slow"])
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SELL when fast SMA crosses back below slow SMA (momentum rolls over).
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe["sma_fast"], dataframe["sma_slow"])
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
