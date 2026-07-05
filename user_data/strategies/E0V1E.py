"""
E0V1E — Freqtrade strategy for Dad (freqtrade-dad)
Based on E0V1E concept: entry on volume spike + EMA expansion breakout.
Targets strong momentum bursts on 5m timeframe.

Paper trading only — dry_run: true, $1000 starting wallet.
"""
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame
import talib.abstract as ta


class E0V1E(IStrategy):
    """
    E0V1E — Breakout / momentum strategy.
    5m candles, Binance/Kraken spot, paper trading.
    """
    INTERFACE_VERSION = 3
    timeframe = '5m'
    startup_candle_count = 200
    stoploss = -0.09
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True
    use_custom_stoploss = False
    minimal_roi = {
        "0": 0.05,
        "20": 0.03,
        "50": 0.02,
        "100": 0.008,
    }
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Buy params
    buy_ema_fast = IntParameter(8, 20, default=12, space='buy', optimize=True)
    buy_ema_slow = IntParameter(20, 50, default=26, space='buy', optimize=True)
    buy_rsi_limit = IntParameter(30, 55, default=50, space='buy', optimize=True)
    buy_volume_mult = DecimalParameter(1.0, 2.5, default=1.5, space='buy', optimize=True)

    # Sell params
    sell_rsi = IntParameter(60, 85, default=75, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)

        # EMAs
        for period in [8, 12, 20, 26, 50, 100, 200]:
            dataframe[f'ema_{period}'] = ta.EMA(dataframe, timeperiod=period)

        # MACD
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # Bollinger
        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])

        # ATR for volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # Volume
        dataframe['volume_mean'] = dataframe['volume'].rolling(20).mean()
        dataframe['volume_spike'] = dataframe['volume'] / dataframe['volume_mean']

        # Stoch RSI
        stochrsi = ta.STOCHRSI(dataframe, timeperiod=14, fastk_period=3, fastd_period=3)
        dataframe['stochrsi_k'] = stochrsi['fastk']
        dataframe['stochrsi_d'] = stochrsi['fastd']

        # ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['dm_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['dm_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = f'ema_{self.buy_ema_fast.value}'
        ema_slow = f'ema_{self.buy_ema_slow.value}'

        dataframe.loc[
            (
                # EMA fast crossed above slow (momentum breakout)
                (dataframe[ema_fast] > dataframe[ema_slow]) &
                (dataframe[ema_fast].shift(1) <= dataframe[ema_slow].shift(1)) &
                # RSI in acceptable range (not overbought)
                (dataframe['rsi'] < self.buy_rsi_limit.value) &
                # Volume confirmation
                (dataframe['volume_spike'] > self.buy_volume_mult.value) &
                # Above 200 EMA (trend filter)
                (dataframe['close'] > dataframe['ema_200']) &
                # ADX confirms trend strength
                (dataframe['adx'] > 20) &
                (dataframe['dm_plus'] > dataframe['dm_minus']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = f'ema_{self.buy_ema_fast.value}'
        ema_slow = f'ema_{self.buy_ema_slow.value}'

        dataframe.loc[
            (
                (dataframe['rsi'] > self.sell_rsi.value) |
                (
                    (dataframe[ema_fast] < dataframe[ema_slow]) &
                    (dataframe['macdhist'] < 0)
                )
            ),
            'exit_long'
        ] = 1
        return dataframe
