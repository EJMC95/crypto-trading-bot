# DayTraderV1Aggro.py
# Freqtrade strategy — BTC/USDT, Binance, 5m candles.
#
# NOTE: Your original file did not come through (the message still had the
# "[PASTE YOUR ...]" placeholder), so this is a clean, runnable rebuild that
# implements every requested change on a standard RSI + EMA day-trading base.
# The class name and overall IStrategy structure are preserved. If your
# original had custom entry/exit signals beyond "RSI > 50", paste it and I'll
# merge these changes into that exact logic instead.
#
# Changes vs. the described original (each tagged [CHANGE n]):
#   1. Volume filter on entry        -> volume > SMA(volume, 20)
#   2. 1h EMA(9) trend filter        -> only long when 1h close > EMA9 and EMA9 rising
#   3. Tighter RSI threshold         -> entry RSI > 55 (was > 50)
#   4. Staged ROI                    -> {"0":0.04,"30":0.025,"60":0.015,"120":0.008}
#   5. Tighter ATR stop              -> custom_stoploss uses 1.5x ATR (was 3.0x)
#   6. Hard backstop kept            -> stoploss = -0.12
#   7. Config / dry_run untouched    -> nothing config-related lives in this file
#
# HYPEROPT: the RSI threshold, EMA periods, ATR multiplier, and the full ROI
# table are exposed as tunable parameters (see the *_space attributes and the
# IntParameter/DecimalParameter/RealParameter declarations below). The values
# from CHANGES 3/4/5 are used as the defaults, so out of the box the strategy
# behaves exactly as specified — but you can now optimise them with:
#
#   freqtrade hyperopt --strategy DayTraderV1Aggro \
#     --hyperopt-loss SharpeHyperOptLoss \
#     --spaces buy roi stoploss trailing \
#     --timeframe 5m --timerange 20250101- -e 300
#
# After a run, freqtrade prints a ready-to-paste block; drop it back in to lock
# the optimised values. Hyperopt only varies parameters whose space is included
# in --spaces, so "buy" tunes the entry params and "roi" tunes the ROI table.

from datetime import datetime
from typing import Optional

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
from freqtrade.strategy import (
    IStrategy,
    merge_informative_pair,
    IntParameter,
    DecimalParameter,
)


class DayTraderV1Aggro(IStrategy):

    INTERFACE_VERSION = 3

    # Base timeframe for entries/exits.
    timeframe = "5m"

    # Higher timeframe used for the trend filter.
    informative_timeframe = "1h"

    # ------------------------------------------------------------------ #
    # HYPEROPT-TUNABLE PARAMETERS                                         #
    # Defaults reproduce the requested CHANGES exactly. Each parameter is #
    # only optimised when its space ("buy" / "sell") is passed to         #
    # `freqtrade hyperopt --spaces ...`; otherwise the default is used.   #
    # ------------------------------------------------------------------ #

    # [CHANGE 3] Entry RSI threshold (default 55, was 50). space="buy".
    buy_rsi = IntParameter(45, 70, default=55, space="buy", optimize=True)

    # Base momentum EMAs. optimize=False keeps these fixed at 9 / 21 so hyperopt
    # does NOT vary indicator periods — that lets freqtrade keep its indicator
    # cache on, which makes optimization runs much faster. Flip optimize=True if
    # you later want to tune the EMA cross (slower, recomputes indicators/epoch).
    buy_ema_fast = IntParameter(5, 15, default=9, space="buy", optimize=False)
    buy_ema_slow = IntParameter(18, 50, default=21, space="buy", optimize=False)

    # Volume confirmation lookback for [CHANGE 1]. Also a period-based indicator,
    # so kept optimize=False to preserve the indicator cache during hyperopt.
    buy_vol_sma = IntParameter(10, 40, default=20, space="buy", optimize=False)

    # [CHANGE 5] ATR multiplier for the trailing stop (default 1.5, was 3.0).
    # Lives in the "sell"/protection space since it governs exits.
    atr_stop_mult = DecimalParameter(
        0.8, 3.0, default=1.5, decimals=1, space="sell", optimize=True
    )

    # ------------------------------------------------------------------ #
    # [CHANGE 4] Staged ROI — now hyperopt-tunable.                       #
    # `minimal_roi` below is the default table (the exact values you      #
    # asked for). Including `roi` in --spaces lets hyperopt search the    #
    # time buckets and ROI levels automatically; the printed result       #
    # replaces this dict.                                                 #
    # Key = minutes since trade open, value = min ROI to trigger exit.    #
    # ------------------------------------------------------------------ #
    minimal_roi = {
        "0": 0.04,    # take 4% immediately if we get it
        "30": 0.025,  # after 30 min, settle for 2.5%
        "60": 0.015,  # after 60 min, settle for 1.5%
        "120": 0.008, # after 120 min, settle for 0.8%
    }

    # [CHANGE 6] Hard catastrophe backstop. The ATR trailing stop below should
    # almost always fire first; this only catches gap/flash-crash scenarios.
    # Included in the "stoploss" hyperopt space if you pass it to --spaces.
    stoploss = -0.12

    # [CHANGE 5] Enable the custom (ATR-based) trailing stop.
    use_custom_stoploss = True

    # Built-in trailing-stop disabled — we manage trailing via custom_stoploss/ATR.
    trailing_stop = False

    # Standard day-trader hygiene.
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    can_short = False

    # Candles of history each pair needs before producing signals.
    # Sized for the widest hyperopt EMA period (slow EMA up to 50).
    startup_candle_count = 60

    # [CHANGE 2] Pull in the 1h timeframe for the higher-timeframe trend filter.
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.informative_timeframe) for pair in pairs]
        return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ---- 5m indicators -------------------------------------------------
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # EMAs use the hyperopt-tunable periods (defaults 9 / 21).
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.buy_ema_fast.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.buy_ema_slow.value)

        # [CHANGE 1] SMA of volume for the volume confirmation filter
        # (lookback is hyperopt-tunable, default 20).
        dataframe["volume_sma"] = ta.SMA(
            dataframe["volume"], timeperiod=self.buy_vol_sma.value
        )

        # ATR for the [CHANGE 5] tighter trailing stop.
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # ---- 1h informative indicators ------------------------------------
        informative = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe=self.informative_timeframe
        )
        # [CHANGE 2] 1h EMA(9) and a "rising" flag (current EMA above prior EMA).
        informative["ema9"] = ta.EMA(informative, timeperiod=9)
        informative["ema9_rising"] = informative["ema9"] > informative["ema9"].shift(1)

        # Merge 1h columns onto the 5m frame (suffixed _1h, no lookahead).
        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, self.informative_timeframe, ffill=True
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Base momentum signal: fast EMA above slow EMA (trend up on 5m).
                (dataframe["ema_fast"] > dataframe["ema_slow"])

                # [CHANGE 3] Tighter RSI threshold — was > 50, default now > 55
                # (hyperopt-tunable via buy_rsi).
                & (dataframe["rsi"] > self.buy_rsi.value)

                # [CHANGE 1] Volume confirmation — only enter when the move has
                # above-average volume behind it (filters chop / false signals).
                & (dataframe["volume"] > dataframe["volume_sma"])

                # [CHANGE 2] Higher-timeframe trend filter — only go long when the
                # 1h close is above its EMA(9) AND that EMA is pointing up.
                & (dataframe["close_1h"] > dataframe["ema9_1h"])
                & (dataframe["ema9_rising_1h"])

                # Never act on a zero-volume candle.
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Momentum-fade exit; ROI table and ATR stop do most of the heavy lifting.
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1

        return dataframe

    # [CHANGE 5] Tighter ATR trailing stop — 1.5x ATR (was 3.0x), so the stop
    # trails closer and cuts losers faster. Returns a stoploss relative to
    # current_rate. The hard -0.12 above always applies as the outer bound.
    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:
        # [CHANGE 5] ATR multiplier — default 1.5 (was 3.0), hyperopt-tunable.
        atr_multiplier = self.atr_stop_mult.value

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return None

        last_atr = dataframe["atr"].iat[-1]
        if last_atr is None or last_atr <= 0 or current_rate <= 0:
            return None

        # Convert the ATR distance into a relative stoploss fraction.
        atr_stop_distance = (atr_multiplier * last_atr) / current_rate

        # Negative fraction below current price; never wider than the hard -0.12.
        return max(-atr_stop_distance, self.stoploss)
