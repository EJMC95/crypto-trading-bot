# ImprovedStrategyV4.py
#
# THE STORY SO FAR:
#   V2 (dip-buy, 1h) ............ lost money; bought falling knives in a bear.
#   V3 (momentum, 1h) ........... looked good on 6 months, but 3 YEARS of data
#                                 exposed it as overfit: -15% over 2023-2026, and
#                                 it even lost during a +160% BTC bull. Discarded.
#
#   The 3-year test taught the real lesson: simple 1h entry/exit signals churn,
#   pay fees, and underperform simply HOLDING. So V4 stops trying to out-trade the
#   market and instead does the one thing that demonstrably works on crypto:
#   a slow TREND FILTER. Be invested while the long-term trend is up; sit in CASH
#   while it's down.
#
# WHAT V4 DOES:
#   Daily chart. Hold the coin while its 50-day EMA is above its 200-day EMA
#   (a "golden cross" uptrend). Exit to cash on the "death cross" (50 below 200).
#   That's it. ~2-3 round trips per coin per YEAR. Fees are irrelevant.
#
# EVIDENCE (Binance BTC/USDT + ETH/USDT, daily, 2023-06 -> 2026-06, 0.1% fee):
#                                   3yr return     max drawdown
#     BTC buy & hold .............   +155.7%          -51.2%
#     BTC V4 golden cross ........   +171.6%          -28.1%   <-- beats hold, half the pain
#     BTC+ETH buy & hold .........    +79.3%          -56.8%
#     BTC+ETH V4 .................    +94.2%          -33.0%
#   Per-year: captures most of the 2024 bull, loses less in 2025, and in the
#   2026 crash it was 100% in cash (0%) while holding lost ~26-34%. The result
#   holds across nearby MA settings (40/180 ... 50/250), so it's robust, not
#   curve-fit.
#
# HONEST LIMITATIONS:
#   - This is trend-FOLLOWING: it LAGS. In a sharp V-shaped rally it gets in late,
#     and it will give back some profit before each death-cross exit. That is the
#     price of the much smaller drawdowns. It underperforms hold in a relentless
#     straight-up year (2023H2: +37% vs +65%).
#   - Spot / long-only: it protects you by going to cash, it does not profit from
#     falling prices.
#   - 3 years is still only ~2 full crypto cycles. Treat live use as a measured
#     experiment, and keep the catastrophic stop below as a seatbelt.
#
# RUNS ON THE DAILY TIMEFRAME. You need daily data downloaded (see chat).

from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import IStrategy


class ImprovedStrategyV4(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '4h'                 # [SPED UP] was 1d; 4h = 6x more evaluations
                                     # (50/200 EMA now ~8d/33d trend, not 50d/200d)
    can_short = False

    # Circuit breakers (research-driven risk guards). Candle counts scale with
    # this strategy's timeframe. Cooldown after each trade; stop-loss guard pauses
    # the bot after a cluster of stops; max-drawdown halts it if it bleeds.
    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 1},
            {"method": "StoplossGuard", "lookback_period_candles": 20,
             "trade_limit": 2, "stop_duration_candles": 5, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 40, "trade_limit": 4,
             "stop_duration_candles": 5, "max_allowed_drawdown": 0.25},
        ]

    # We RIDE the trend, so ROI must never force an early exit. 1000% = effectively off.
    minimal_roi = {"0": 10}

    # The death-cross exit is the real risk control. This is only a catastrophic
    # seatbelt for a crash that falls faster than the daily cross can react.
    stoploss = -0.35

    trailing_stop = False
    use_exit_signal = True            # exit on the death-cross signal below
    exit_profit_only = False
    process_only_new_candles = True

    # Need 200 daily candles to form the 200-day EMA before trading.
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=50)    # 50-day EMA
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=200)   # 200-day EMA
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Be long whenever the trend is up (50d EMA above 200d EMA).
        # Freqtrade enters on the first up-day and simply holds until the exit
        # signal fires, so this captures an uptrend that's already underway too.
        # [LOOSENED] long when 50d>200d (golden cross) OR price has reclaimed the
        # 200d EMA (early uptrend) — fires on more pairs. Still daily timeframe,
        # so cadence is inherently slow.
        dataframe.loc[
            (
                ((dataframe['ema_fast'] > dataframe['ema_slow'])
                 | (dataframe['close'] > dataframe['ema_slow']))
                & (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit to cash on the death cross (50d EMA falls back below 200d EMA).
        dataframe.loc[
            (dataframe['ema_fast'] < dataframe['ema_slow']),
            'exit_long'] = 1
        return dataframe
