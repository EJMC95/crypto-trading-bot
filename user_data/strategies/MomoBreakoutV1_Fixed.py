# MomoBreakoutV1_Fixed.py
#
# WHAT CHANGED FROM V1 AND WHY:
#   V1 only bought on BREAKOUTS (close > 30-bar high). In a sideways/falling market, this never fired.
#
#   V1_Fixed adds PULLBACK entry:
#     - Entry 1 (breakout): close > 30-bar high AND close > 200-EMA (unchanged, the original edge)
#     - Entry 2 (pullback): close < 15-bar low AND close > 200-EMA AND rsi < 50
#       i.e. within an uptrend, if price dips below a 15-bar floor and RSI is not too hot, buy it back.
#   Result: captures both breakouts (the original signal) AND pullbacks within the uptrend (new signal).
#   The original backtest only sees Entry 1, so this is an _augmentation_ that should not break the tested edge.
#
#   Exit logic: unchanged (Donchian breakdown + -12% stop).

from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter


class MomoBreakoutV1Fixed(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = False

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "StoplossGuard", "lookback_period_candles": 42,
             "trade_limit": 3, "stop_duration_candles": 12, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 90, "trade_limit": 8,
             "stop_duration_candles": 18, "max_allowed_drawdown": 0.25},
        ]

    entry_lookback = IntParameter(20, 45, default=30, space="buy",  optimize=False)
    exit_lookback  = IntParameter(8,  25, default=15, space="sell", optimize=False)
    trend_ema      = IntParameter(100, 250, default=200, space="buy", optimize=False)

    minimal_roi = {"0": 100}
    stoploss = -0.12

    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 260

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.trend_ema.value)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        # Donchian channels (shift(1) for no look-ahead).
        dataframe["dc_high"] = dataframe["high"].rolling(self.entry_lookback.value).max().shift(1)
        dataframe["dc_low"]  = dataframe["low"].rolling(self.exit_lookback.value).min().shift(1)
        # FIXED: add a shorter 15-bar low for pullback entry
        dataframe["pullback_low"] = dataframe["low"].rolling(self.exit_lookback.value).min().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FIXED: two entry signals instead of one.
        dataframe.loc[
            (
                (
                    # Entry 1: breakout above 30-bar high (original, unchanged)
                    ((dataframe["close"] > dataframe["dc_high"]) & (dataframe["close"] > dataframe["ema_trend"]))
                    |
                    # Entry 2: pullback below 15-bar low, but STILL above 200-EMA, RSI not too hot (NEW)
                    ((dataframe["close"] < dataframe["pullback_low"]) & (dataframe["close"] > dataframe["ema_trend"]) & (dataframe["rsi"] < 50))
                )
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: unchanged from V1
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["dc_low"])
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
