# ImprovedStrategyV2.py
#
# What changed from V1 and WHY:
#   1. Runs on the 1-HOUR chart instead of 5-minute. V1 made 186 trades and paid
#      ~0.8% round-trip in fees on every one — death by a thousand cuts. Trading on
#      1h produces far fewer, higher-conviction trades, so fees stop dominating.
#   2. NO MORE early exit signal. V1 dumped 168 trades at tiny losses the moment RSI
#      ticked up. V2 holds each trade until it hits the profit target, the trailing
#      stop, or the stop-loss. We let winners actually develop.
#   3. Slightly wider profit targets and stop, appropriate for the slower 1h chart.
#
# Still NOT a guaranteed winner — especially in a falling market, since this only
# ever buys. It's the next experiment, not the finish line.

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class ImprovedStrategyV2(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '1h'            # <-- key change: hourly candles, far fewer trades
    can_short = False

    # Take-profit ladder (bigger targets because 1h moves are bigger):
    #   take 6% immediately; after 4h be happy with 3%; after 8h, 1.5%; after 12h, anything green.
    minimal_roi = {
        "0": 0.06,
        "240": 0.03,
        "480": 0.015,
        "720": 0
    }

    stoploss = -0.06           # cut a loser at -6%

    # Trailing stop: once up 3%, trail 1.5% behind the peak to lock in gains.
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    process_only_new_candles = True

    # <-- key change: turn OFF the early exit signal. Exits happen only via
    #     the profit target, trailing stop, or stop-loss above.
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
        # Buy a dip, but only inside an uptrend.
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &   # overall trend up
                (dataframe['rsi'] < 40) &                           # pulled back / oversold
                (dataframe['close'] < dataframe['bb_lower']) &      # dipped below lower band
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No signal-based exits — ROI / trailing / stop-loss handle everything.
        return dataframe
