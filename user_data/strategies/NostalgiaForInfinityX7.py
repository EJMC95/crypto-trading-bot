"""
NostalgiaForInfinityX7 — Freqtrade strategy for Mum (freqtrade-mum)
Based on the NFI X7 concept: combines trend, RSI, Bollinger Bands, EMA structure
and volume confirmation for 5m entries on Binance spot.

Paper trading only — dry_run: true, $1000 starting wallet.
"""
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame
import talib.abstract as ta


class NostalgiaForInfinityX7(IStrategy):
    """
    NFI X7 — trend-following with multi-timeframe confluence.
    5m candles, Binance spot, paper trading.
    """
    INTERFACE_VERSION = 3
    timeframe = '5m'
    startup_candle_count = 200
    stoploss = -0.10
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True
    use_custom_stoploss = False
    minimal_roi = {
        "0": 0.06,
        "30": 0.04,
        "60": 0.025,
        "120": 0.01,
    }
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Buy hyperspace params
    buy_rsi_fast = IntParameter(20, 45, default=35, space='buy', optimize=True)
    buy_rsi = IntParameter(15, 40, default=30, space='buy', optimize=True)
    buy_bb_factor = DecimalParameter(0.97, 0.999, default=0.986, space='buy', optimize=True)
    buy_ema_cofi = DecimalParameter(0.96, 1.0, default=0.97, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)

        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']
        dataframe['bb_width'] = (dataframe['bb_upperband'] - dataframe['bb_lowerband']) / dataframe['bb_middleband']

        # EMAs
        dataframe['ema_5'] = ta.EMA(dataframe, timeperiod=5)
        dataframe['ema_12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']

        # Volume MA
        dataframe['volume_mean_slow'] = dataframe['volume'].rolling(window=20).mean()

        # Heikin Ashi
        dataframe['ha_open'] = (dataframe['open'].shift(1) + dataframe['close'].shift(1)) / 2
        dataframe['ha_close'] = (dataframe['open'] + dataframe['high'] + dataframe['low'] + dataframe['close']) / 4
        dataframe['ha_high'] = dataframe[['high', 'ha_open', 'ha_close']].max(axis=1)
        dataframe['ha_low'] = dataframe[['low', 'ha_open', 'ha_close']].min(axis=1)

        # CTI (Correlation Trend Indicator)
        dataframe['cti'] = dataframe['close'].rolling(20).corr(pd.Series(range(20), index=dataframe.index[-20:]).reindex(dataframe.index).fillna(method='ffill'))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # Condition 1: RSI oversold with fast bounce
        conditions.append(
            (dataframe['rsi_fast'] < self.buy_rsi_fast.value) &
            (dataframe['rsi'] < self.buy_rsi.value) &
            (dataframe['close'] < dataframe['bb_lowerband'] * self.buy_bb_factor.value) &
            (dataframe['volume'] > 0)
        )

        # Condition 2: EMA structure + MACD cross
        conditions.append(
            (dataframe['ema_5'] > dataframe['ema_12']) &
            (dataframe['ema_12'] > dataframe['ema_20']) &
            (dataframe['macd'] > dataframe['macdsignal']) &
            (dataframe['close'] > dataframe['ema_200'] * self.buy_ema_cofi.value) &
            (dataframe['rsi'] < 55) &
            (dataframe['volume'] > dataframe['volume_mean_slow'] * 0.8)
        )

        if conditions:
            dataframe.loc[
                pd.concat([c.to_frame() for c in conditions], axis=1).any(axis=1),
                'enter_long'
            ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['rsi'] > 75) |
            (dataframe['ema_5'] < dataframe['ema_12']) &
            (dataframe['macd'] < dataframe['macdsignal']),
            'exit_long'
        ] = 1
        return dataframe
