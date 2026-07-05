"""
CombinedBinHAndClucV8 — Freqtrade strategy for Avo Maria (freqtrade-avo-maria)
Combines BinH (Bollinger Band + Heiken Ashi) with ClucMay08 (volume mean reversion).
Two entry systems, one exit — high trade frequency on 5m.

Paper trading only — dry_run: true, $1000 starting wallet.
"""
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame
import talib.abstract as ta


class CombinedBinHAndClucV8(IStrategy):
    """
    CombinedBinHAndCluc — mean reversion with dual entry logic.
    5m candles, Binance/Kraken spot, paper trading.
    """
    INTERFACE_VERSION = 3
    timeframe = '5m'
    startup_candle_count = 200
    stoploss = -0.07
    trailing_stop = False
    use_custom_stoploss = False
    minimal_roi = {
        "0": 0.04,
        "20": 0.02,
        "40": 0.01,
        "80": 0.005,
    }
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True  # let it run past ROI if signal is still valid

    # BinH params
    binh_closedelta = DecimalParameter(12.0, 18.0, default=15.0, space='buy', optimize=True)
    binh_cdi = DecimalParameter(0.4, 0.8, default=0.6, space='buy', optimize=True)

    # Cluc params
    cluc_volume_factor = DecimalParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=40, nbdevup=2.0, nbdevdn=2.0, matype=0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_upper'] = bollinger['upperband']

        # Tight BB for Cluc
        bollinger2 = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
        dataframe['bb_lower_20'] = bollinger2['lowerband']
        dataframe['bb_middle_20'] = bollinger2['middleband']

        # EMAs
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Volume
        dataframe['volume_mean'] = dataframe['volume'].rolling(30).mean()

        # Close delta (for BinH)
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
        dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs()

        # Heiken Ashi candles
        dataframe['ha_close'] = (dataframe['open'] + dataframe['high'] + dataframe['low'] + dataframe['close']) / 4
        dataframe['ha_open'] = (dataframe['open'].shift(1) + dataframe['close'].shift(1)) / 2
        dataframe['ha_open'] = dataframe['ha_open'].fillna((dataframe['open'] + dataframe['close']) / 2)
        dataframe['ha_high'] = dataframe[['high', 'ha_open', 'ha_close']].max(axis=1)
        dataframe['ha_low'] = dataframe[['low', 'ha_open', 'ha_close']].min(axis=1)

        # CDI (close delta indicator for BinH)
        dataframe['cdi'] = abs(dataframe['ha_open'] - dataframe['ha_close']) / (dataframe['ha_high'] - dataframe['ha_low'] + 0.0001)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # BinH entry: BB lower touch + HA doji-like candle
        binh_cond = (
            (dataframe['close'] < dataframe['bb_lower']) &
            (dataframe['closedelta'] > dataframe['close'] * self.binh_closedelta.value / 1000) &
            (dataframe['tail'] < dataframe['closedelta'] * self.binh_cdi.value) &
            (dataframe['volume'] > 0)
        )

        # Cluc entry: volume surge + close below tight BB
        cluc_cond = (
            (dataframe['close'] < dataframe['bb_lower_20']) &
            (dataframe['volume'] < dataframe['volume_mean'] * self.cluc_volume_factor.value) &
            (dataframe['rsi'] < 45) &
            (dataframe['volume'] > 0)
        )

        dataframe.loc[binh_cond | cluc_cond, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['bb_middle']) &
                (dataframe['close'] > dataframe['bb_middle_20']) &
                (dataframe['rsi'] > 60)
            ),
            'exit_long'
        ] = 1
        return dataframe
