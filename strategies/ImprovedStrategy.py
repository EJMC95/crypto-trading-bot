# ImprovedStrategy.py
#
# A "buy the dip in an uptrend" strategy for Freqtrade.
#
# The idea, in plain English:
#   - Only buy when the overall trend is UP (50-period average above 200-period average).
#     This avoids the #1 mistake of the template strategy: buying into a falling market.
#   - Within an uptrend, wait for a short-term DIP (RSI oversold + price pokes below the
#     lower Bollinger Band) and buy that pullback.
#   - Take profit at modest targets, exit if momentum gets overheated (RSI high),
#     and cut losses quickly with a tight 5% stop + a trailing stop that locks in gains.
#
# This is a SENSIBLE STARTING POINT to learn from and tweak — NOT a guaranteed money-maker.
# Every number below (the "knobs") is something you can change and re-backtest.

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class ImprovedStrategy(IStrategy):
    INTERFACE_VERSION = 3

    # Candle size this strategy runs on.
    timeframe = '5m'

    # We only go long (buy then sell). No short-selling.
    can_short = False

    # ---- RISK MANAGEMENT (the knobs that matter most) ----

    # Take-profit ladder. Read it as: "if a trade is up 4%, take it immediately;
    # after 30 min be happy with 2.5%; after 60 min, 1.5%; after 2 hrs, 1%."
    # Locking in smaller gains the longer a trade drags on.
    minimal_roi = {
        "0": 0.04,
        "30": 0.025,
        "60": 0.015,
        "120": 0.01
    }

    # Hard stop-loss: bail if a trade drops 5%. The template used -10%, which let
    # losers get twice as big as they should. Tighter = smaller individual losses.
    stoploss = -0.05

    # Trailing stop: once a trade is up 2%, start trailing a stop 1% behind the peak.
    # This lets winners run a bit while protecting the gain.
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # ---- HOUSEKEEPING ----
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # We use a 200-period average, so the bot needs 200 candles of history
    # before it can start making decisions.
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate the indicators we base decisions on."""
        # Momentum oscillator (0-100). Low = oversold, high = overbought.
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Trend filter: a faster and a slower moving average.
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=200)

        # Bollinger Bands: a volatility envelope around price.
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lower'] = bollinger['lower']
        dataframe['bb_mid'] = bollinger['mid']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """The BUY rules. All conditions must be true at once."""
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &   # 1. Overall trend is up
                (dataframe['rsi'] < 35) &                           # 2. Short-term oversold
                (dataframe['close'] < dataframe['bb_lower']) &      # 3. Price dipped below lower band
                (dataframe['volume'] > 0)                           # 4. There's actual volume
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """The SELL rule (besides ROI / stop-loss, which are automatic)."""
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) &      # Momentum overheated -> take profit
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1
        return dataframe
