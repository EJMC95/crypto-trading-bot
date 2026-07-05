"""
GeorgiaFreqAI — Freqtrade FreqAI strategy for Georgia (freqtrade-georgia)
Uses LightGBM classifier to predict price direction over next 1H candle.
Features: RSI, BB, EMA ratios, volume, momentum, ATR-normalized returns.
Trains on 30-day rolling window, retrains every 24h.

Paper trading only — dry_run: true, $1000 starting wallet.
"""
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.freqai.base_models.FreqaiMultiOutputClassifier import FreqaiMultiOutputClassifier


class GeorgiaFreqAI(IStrategy):
    """
    Georgia — ML-driven adaptive strategy using FreqAI LightGBM.
    1H candles, Binance spot, paper trading.
    """
    INTERFACE_VERSION = 3
    timeframe = '1h'
    startup_candle_count = 300
    stoploss = -0.12
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.06
    trailing_only_offset_is_reached = True
    use_custom_stoploss = False
    minimal_roi = {
        "0": 0.10,
        "120": 0.06,
        "240": 0.03,
        "480": 0.01,
    }
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False

    # FreqAI config (merged with config.json freqai block)
    freqai = {
        "enabled": True,
        "purge_old_models": True,
        "train_period_days": 30,
        "backtest_period_days": 7,
        "live_retrain_hours": 24,
        "identifier": "georgia-lgbm-v1",
        "feature_parameters": {
            "include_timeframes": ["1h", "4h"],
            "include_corr_pairlist": ["BTC/USDT", "ETH/USDT"],
            "label_period_candles": 24,
            "include_shifted_candles": 2,
            "DI_threshold": 0.9,
            "weight_factor": 0.9,
            "principal_component_analysis": False,
            "use_SVM_to_remove_outliers": True,
            "indicator_periods_candles": [10, 20, 50],
        },
        "data_split_parameters": {
            "test_size": 0.25,
            "random_state": 42,
        },
        "model_training_parameters": {
            "n_estimators": 200,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": -1,
        },
    }

    # Entry threshold
    entry_threshold = DecimalParameter(0.55, 0.80, default=0.65, space='buy', optimize=True)
    exit_threshold = DecimalParameter(0.55, 0.80, default=0.65, space='sell', optimize=True)

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                        metadata: dict, **kwargs) -> DataFrame:
        dataframe[f'%-rsi-period_{period}'] = ta.RSI(dataframe, timeperiod=period)
        dataframe[f'%-mfi-period_{period}'] = ta.MFI(dataframe, timeperiod=period)
        dataframe[f'%-adx-period_{period}'] = ta.ADX(dataframe, timeperiod=period)
        dataframe[f'%-cci-period_{period}'] = ta.CCI(dataframe, timeperiod=period)
        bollinger = ta.BBANDS(dataframe, timeperiod=period)
        dataframe[f'%-bb_width-period_{period}'] = (
            bollinger['upperband'] - bollinger['lowerband']
        ) / bollinger['middleband']
        dataframe[f'%-bb_percent-period_{period}'] = (
            (dataframe['close'] - bollinger['lowerband']) /
            (bollinger['upperband'] - bollinger['lowerband'])
        )
        dataframe[f'%-atr-period_{period}'] = ta.ATR(dataframe, timeperiod=period)
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame,
                                      metadata: dict, **kwargs) -> DataFrame:
        dataframe['%-day_of_week'] = dataframe['date'].dt.dayofweek
        dataframe['%-hour_of_day'] = dataframe['date'].dt.hour
        dataframe['%-raw_close'] = dataframe['close']
        dataframe['%-raw_volume'] = dataframe['volume']
        dataframe['%-raw_price_change'] = dataframe['close'].pct_change()
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame,
                           metadata: dict, **kwargs) -> DataFrame:
        # Target: will price be higher 24 candles (24h) from now?
        dataframe['&-up_or_down'] = np.where(
            dataframe['close'].shift(-24) > dataframe['close'] * 1.01,
            'up',
            np.where(
                dataframe['close'].shift(-24) < dataframe['close'] * 0.99,
                'down',
                'neutral'
            )
        )
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['&-up_or_down_up_probability'] > self.entry_threshold.value) &
                (dataframe['do_predict'] == 1) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['&-up_or_down_down_probability'] > self.exit_threshold.value) |
                (dataframe['do_predict'] != 1)
            ),
            'exit_long'
        ] = 1
        return dataframe
