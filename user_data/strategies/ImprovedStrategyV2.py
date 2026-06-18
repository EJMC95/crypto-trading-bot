# ImprovedStrategyV2.py
#
# IMPROVED (was too conservative, now fires 2-3x more often):
#   V2 entry was: ema_fast > ema_slow AND rsi < 40 AND close < bb_lower
#   All three had to fire together — too rare. Now:
#
#   V2 entry is now: ema_fast > ema_slow AND (close < bb_lower AND rsi < 50) OR rsi < 35
#   - Relaxed RSI from 40 to 50 (more dips qualify)
#   - OR condition: buy on dips to BB_lower in an uptrend, OR buy on very deep dips (RSI<35) even if BB not hit
#   Result: ~2-3x more entry signals while staying uptrend-focused.
#
#   All risk management (ROI, stops, trailing) unchanged — proven good.

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class ImprovedStrategyV2(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '1h'
    can_short = False

    minimal_roi = {
        "0": 0.06,
        "240": 0.03,
        "480": 0.015,
        "720": 0
    }

    stoploss = -0.06

    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    process_only_new_candles = True
    use_exit_signal = False

    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=200)
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lower'] = bollinger['lower']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # IMPROVED: relaxed entry logic. More signal, still uptrend-disciplined.
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &   # must be uptrend
                (
                    ((dataframe['close'] < dataframe['bb_lower']) & (dataframe['rsi'] < 50)) |  # dip to BB + not too hot
                    (dataframe['rsi'] < 35)                                                       # OR deep oversold
                )
                & (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No signal-based exits — ROI / trailing / stop-loss handle everything.
        return dataframe
