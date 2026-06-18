# DayTraderV1.py
#
# WHAT THIS IS:
#   The OPPOSITE of ImprovedStrategyV4. V4 is a slow trend-follower that trades
#   2-3 times a YEAR and mostly sits still. This one is an intraday "day trader":
#   it works on the 5-minute chart and tries to take many small trades per day,
#   getting in and out within minutes-to-hours, holding nothing for long.
#
#   Same coin as your other bots (BTC/USDT). Same exchanges (Kraken + Binance).
#   STILL DRY-RUN (fake money) — this is a side-by-side experiment, not real money.
#
# HOW IT DECIDES (plain English):
#   - It only buys when the short-term tide is still up (price above the 200-period
#     EMA on the 5m chart), so it isn't catching a knife in a falling market.
#   - Inside that, it waits for a brief dip: RSI dropping under 35 (oversold) and
#     then ticking back up — a small bounce to ride.
#   - It takes profit FAST (about +1.2% to +1.5%), or trails a stop once it's a
#     bit in the green, or bails if RSI gets hot (>72). If none of that happens it
#     gives up on the trade within ~90 minutes (the ROI table decays to 0).
#   - Hard stop-loss at -2% per trade so no single trade runs away.
#
# HONEST WARNING (please read):
#   Your own V4 notes already found that simple short-timeframe signals "churn,
#   pay fees, and underperform simply HOLDING." That is the well-documented reality
#   of day trading — most fast bots lose to fees and noise over time, and this one
#   may well do the same. The whole point of running it in DRY-RUN is to SEE that
#   for yourself on your own data, safely, with no money at risk. Treat it as a
#   learning experiment, not a money-maker. Nothing here is financial advice.
#
# NEEDS 5-MINUTE DATA. Download it before backtesting (see chat for the command).

from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import IStrategy


class DayTraderV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '5m'                 # intraday — this is what makes it "day trading"
    can_short = False

    # Take small profits quickly, then demand less the longer a trade drags on.
    # By ~90 minutes it will exit at break-even rather than hold overnight.
    minimal_roi = {
        "0": 0.015,
        "30": 0.008,
        "60": 0.004,
        "90": 0.0
    }

    # Per-trade seatbelt: never let one trade lose more than 2%.
    stoploss = -0.02

    # Lock in gains: once a trade is +1.2% up, trail a stop 0.5% behind the high.
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = True

    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True

    # 200 five-minute candles needed to form the slow EMA before trading.
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        # Gentler trend filter: a 50-period EMA instead of 200. It sits closer to
        # price, so the bot isn't locked out for hours whenever price dips slightly
        # below a slow line. More of the day qualifies as "OK to buy".
        dataframe['ema_trend'] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MORE ACTIVE: buy on milder dips. Previously it waited for RSI to climb
        # back up through 35 (deep oversold) only while above a 200-EMA — rare.
        # Now it buys when RSI ticks back up through 45 (a much more common pullback)
        # while price is above the gentler 50-EMA. Expect several trades on a normal
        # day instead of a handful. (More trades = more fees/churn — that's the
        # trade-off we're deliberately testing. Still dry-run / fake money.)
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_trend']) &       # short-term trend OK
                (dataframe['rsi'] > 45) &                             # bouncing back up...
                (dataframe['rsi'].shift(1) <= 45) &                   # ...from a mild dip
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Take the bounce a little sooner (RSI 65 instead of 72) so it cycles out
        # and frees up to trade again. ROI / trailing stop usually fire first.
        dataframe.loc[
            (
                (dataframe['rsi'] > 65) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1
        return dataframe
