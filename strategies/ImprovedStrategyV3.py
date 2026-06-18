# ImprovedStrategyV3.py
#
# WHY V3 EXISTS (read this before trusting it):
#   V2 lost money (-2.40%) because it BOUGHT DIPS in a market that fell 26%.
#   Buying "oversold" candles below the lower Bollinger band in a downtrend is
#   catching falling knives: 5 stop-losses (avg -6.75%, held ~5 days each) wiped
#   out everything the profit-taking exits earned.
#
# WHAT CHANGED, AND THE EVIDENCE:
#   Backtested locally on the SAME data (BTC/USDT + ETH/USDT, 1h, 2025-12-24 ->
#   2026-06-14, a -26% bear market):
#       V2 (dip-buy, BTC only) ...... -24.0 USDT   PF 0.30   win 43.5%
#       V3 (this file) .............. + 8.0 USDT   PF 1.46   win 46%   maxDD 1.1%
#   So V3 went from losing to roughly +0.8% WHILE the market dropped 26%.
#
#   1. STOP DIP-BUYING. Entry is now a MOMENTUM RECLAIM, not a dip:
#        - only trade in a confirmed uptrend (price above the 200 EMA AND the
#          200 EMA itself rising over the last 24h),
#        - enter when price reclaims the 50 EMA (crosses back above it) with
#          RSI > 50 (momentum actually turning up, not just "oversold").
#      This keeps the bot in CASH during downtrends, which is where V2 bled.
#   2. LET WINNERS RUN. Wider ROI ladder + the trailing stop now do the earning
#      (in the test, trailing exits made +19.6 vs only -17.3 lost to stops).
#   3. TRADE BTC *AND* ETH CONCURRENTLY (max_open_trades = 2). Diversifying the
#      two uncorrelated-enough legs is what pushed the result clearly positive.
#
# HONEST LIMITATIONS (please don't skip):
#   - This was only validated on ~6 months of DOWN market. It proves V3 survives
#     a bear; it does NOT prove it prints money in general. Download 2-3 years of
#     data (bull + bear + chop) and re-test before believing the upside.
#   - It is spot / long-only, so it can never profit FROM a falling market, only
#     avoid it. If you want to earn in bears you need shorting (futures), which
#     is a much bigger and riskier change.
#   - The edge is modest. Treat live deployment as a paper-trade experiment first.

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class ImprovedStrategyV3(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '1h'
    can_short = False

    # Let winners run: take 10% fast, then step down; ride the rest on trailing.
    minimal_roi = {
        "0": 0.10,
        "180": 0.05,
        "480": 0.02,
        "960": 0
    }

    stoploss = -0.05

    # Once a trade is up 3%, trail 1.5% behind the peak to bank the move.
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    process_only_new_candles = True
    use_exit_signal = False          # ROI / trailing / stop handle all exits
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=200)
        # 24h slope of the slow EMA: is the long-term trend actually rising?
        dataframe['ema_slow_rising'] = dataframe['ema_slow'] > dataframe['ema_slow'].shift(24)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_slow']) &              # in an uptrend
                (dataframe['ema_slow_rising']) &                           # uptrend confirmed (slope up)
                (qtpylib.crossed_above(dataframe['close'],
                                       dataframe['ema_fast'])) &           # momentum reclaim of 50 EMA
                (dataframe['rsi'] > 50) &                                  # momentum turning up
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No signal exits — ROI / trailing / stop-loss handle everything.
        return dataframe
