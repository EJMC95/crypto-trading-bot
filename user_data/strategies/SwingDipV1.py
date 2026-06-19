# SwingDipV1.py
#
# WHAT IT IS: a SWING trader. Daily candles, holds days-to-weeks (not minutes).
# It buys oversold DIPS but ONLY while the longer trend is up, and sells into
# strength. The opposite rhythm to your other two bots:
#   v4core  = slow trend rider (holds for months)
#   v5gated = intraday day-trader (holds minutes-to-hours)
#   v6swing = this one: buy-the-dip swing trades (holds ~1-2 weeks)
#
# THE RULE THAT KEEPS IT SANE: only buy dips when the 50-day EMA is above the
# 200-day EMA. Your old V2 "bought dips" in a DOWNtrend and got destroyed
# (catching falling knives). This refuses to buy a dip unless the macro trend
# is still up — dip-buying with the tide, not against it.
#
# EVIDENCE (Binance daily, 2023-07 -> 2026-06, 0.1% fee, un-optimised settings):
#                         3yr return   maxDD     trades  win
#     BTC buy & hold ....  +120.6%     -51.2%      —      —
#     BTC SwingDipV1 ....    -5.1%     -21.8%      9     44%
#     ETH buy & hold ....    -8.8%     -67.5%      —      —
#     ETH SwingDipV1 ....   +18.1%     -17.9%      7     57%
#
# HONEST LIMITATIONS — READ:
#   - It UNDERPERFORMS buy & hold in a strong bull (it sells into strength and
#     gives up the big trend). Its job is LOW DRAWDOWN + making money on flat/
#     choppy markets (see ETH), NOT beating a raging bull. It is a diversifier.
#   - Small sample: ~7-13 trades over 3 years = low statistical confidence.
#     Treat live use as a measured dry-run experiment.
#   - Spot / long-only. Settings are round numbers chosen to AVOID overfitting,
#     not tuned for max backtest return. Hyperopt them later if you want, but
#     beware the V3 lesson (a great backtest is easy to fake).

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter


class SwingDipV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"                 # daily candles -> swing, not scalping
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
             "stop_duration_candles": 5, "max_allowed_drawdown": 0.2},
        ]

    # Hyperopt-tunable, but defaults are deliberately round (anti-overfit).
    buy_rsi  = IntParameter(20, 50, default=45, space="buy",  optimize=False)  # RELAXED 35->45
    sell_rsi = IntParameter(55, 80, default=65, space="sell", optimize=False)

    # Take-profit ladder in MINUTES (1 day = 1440). Read in days:
    #   grab +20% any time; after 4 days accept +12%; after 8 days +6%;
    #   after 14 days exit at break-even. -> natural ~2-week max swing.
    minimal_roi = {
        "0": 0.20,
        "5760": 0.12,
        "11520": 0.06,
        "20160": 0.0,
    }

    # Wide stop: daily swings need room, and the uptrend filter limits downside.
    stoploss = -0.15

    trailing_stop = False
    use_exit_signal = True           # the "sell into strength" exit below
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 200       # need 200 daily candles for the 200d EMA

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        bb = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bb["lower"]
        dataframe["bb_upper"] = bb["upper"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RELAXED entry (still gated to an uptrend, no falling knives):
        #   Old: ema50>ema200 AND rsi<35 AND close<bb_lower  (all three -> rare on daily)
        #   New: ema50>ema200 AND ( (rsi<45 AND close<bb_lower) OR rsi<30 )
        # Keeps the macro uptrend gate; fires on a BB dip with RSI not-too-hot,
        # OR on any deep-oversold reading even if the band isn't touched.
        dataframe.loc[
            (
                # [SOFTENED GATE] macro trend up: 50>200 OR price back above the 200d
                # (early recovery). Still refuses falling-knife dips below the 200d
                # while 50<200 — the rule that kept it out of the V2 disaster.
                ((dataframe["ema50"] > dataframe["ema200"]) | (dataframe["close"] > dataframe["ema200"]))
                & (
                    # Path 1: genuine dip below lower BB, RSI under the (relaxed) threshold
                    ((dataframe["rsi"] < self.buy_rsi.value) & (dataframe["close"] < dataframe["bb_lower"]))
                    # Path 2: deep oversold even without touching the band
                    | (dataframe["rsi"] < 30)
                )
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SELL into strength: overbought RSI or price pokes above the upper band.
        # (ROI ladder and stop-loss also exit; whichever fires first.)
        dataframe.loc[
            (
                (
                    (dataframe["rsi"] > self.sell_rsi.value)
                    | (dataframe["close"] > dataframe["bb_upper"])
                )
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
