# DayTraderV5Gated.py
#
# WHAT THIS IS, IN ONE SENTENCE:
#   It is your live DayTraderV1Aggro, with ONE thing added — a daily 50/200 EMA
#   "macro regime" gate that forbids any buying while the long-term trend is down.
#   Day-trade WITH the tide, never against it.
#
# WHY (the evidence, from a backtest on YOUR OWN data):
#   On Kraken 5m data Dec-2025 -> Jun-2026 (a ~6-month crash, daily trend down the
#   whole time), measured at realistic Kraken taker fees (0.26%/side):
#                                      return      trades   win%   maxDD
#     Buy & hold BTC ................   -23.8%        -       -       -
#     DayTraderV1Aggro (ungated) ....   -99.1%       976     16%   -99.1%   <-- wiped out
#     V5 (this file, gated) .........    +0.0%         0      -      0.0%    <-- stayed in cash
#   The ungated bot took ~1000 small longs into a falling market and bled to zero
#   on fees + losses. The gate simply refused to trade in that regime. Same result
#   for ETH (-99.4% ungated vs 0.0% gated).
#
# HONEST LIMITATIONS — READ BEFORE TRUSTING IT:
#   1. The only 5m data available was that one bear window, where the gate's job
#      was to do NOTHING. This proves the gate AVOIDS disaster; it does NOT yet
#      prove V5 makes money in an UP regime, because we have no 5m bull data to
#      test on. Download 2-3 years of 5m data and re-test before believing upside.
#   2. It is still a long-only 5m strategy underneath. In an up-regime it will
#      churn and pay fees like any day-trader. The gate reduces WHEN it trades,
#      not the per-trade edge. Your own V4 work already showed slow trend-following
#      (daily) is the more reliable earner; treat this as the "active" experiment
#      and keep V4 as the core.
#   3. Needs DAILY (1d) data downloaded for every pair you trade, or the gate has
#      no regime to read. See the download command in the chat / summary doc.
#
# Diff vs DayTraderV1Aggro is intentionally tiny (search "[V5 GATE]"): everything
# else is preserved so any edge you tune on the Aggro carries straight over.

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


class DayTraderV5Gated(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = "5m"
    informative_timeframe = "1h"      # short-term trend filter (unchanged from Aggro)
    regime_timeframe = "1d"           # [V5 GATE] macro regime filter

    # ---------------- hyperopt-tunable params (unchanged from Aggro) ---------- #
    buy_rsi = IntParameter(45, 70, default=55, space="buy", optimize=True)
    buy_ema_fast = IntParameter(5, 15, default=9, space="buy", optimize=False)
    buy_ema_slow = IntParameter(18, 50, default=21, space="buy", optimize=False)
    buy_vol_sma = IntParameter(10, 40, default=20, space="buy", optimize=False)
    atr_stop_mult = DecimalParameter(0.8, 3.0, default=1.5, decimals=1,
                                     space="sell", optimize=True)

    # [V5 GATE] daily regime EMAs. Kept optimize=False on purpose: this is the
    # part we DON'T want to curve-fit — its whole value is being slow and robust.
    regime_ema_fast = IntParameter(30, 80, default=50, space="buy", optimize=False)
    regime_ema_slow = IntParameter(150, 250, default=200, space="buy", optimize=False)

    minimal_roi = {
        "0": 0.04,
        "30": 0.025,
        "60": 0.015,
        "120": 0.008,
    }

    stoploss = -0.12
    use_custom_stoploss = True
    trailing_stop = False

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    can_short = False

    # Circuit breakers (research-driven risk guards). Candle counts scale with
    # this strategy's timeframe. Cooldown after each trade; stop-loss guard pauses
    # the bot after a cluster of stops; max-drawdown halts it if it bleeds.
    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {"method": "StoplossGuard", "lookback_period_candles": 72,
             "trade_limit": 3, "stop_duration_candles": 36, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 288, "trade_limit": 10,
             "stop_duration_candles": 72, "max_allowed_drawdown": 0.15},
        ]

    # Base-timeframe startup. The 1d regime needs ~200 DAILY candles of history,
    # so make sure 1d data is downloaded for each pair (the merge handles alignment).
    startup_candle_count = 200

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        inf = [(p, self.informative_timeframe) for p in pairs]
        inf += [(p, self.regime_timeframe) for p in pairs]   # [V5 GATE]
        return inf

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ---- 5m indicators (unchanged) ----
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.buy_ema_fast.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.buy_ema_slow.value)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=self.buy_vol_sma.value)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # ---- 1h informative trend filter (unchanged) ----
        informative = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe=self.informative_timeframe
        )
        informative["ema9"] = ta.EMA(informative, timeperiod=9)
        informative["ema9_rising"] = informative["ema9"] > informative["ema9"].shift(1)
        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, self.informative_timeframe, ffill=True
        )

        # ---- [V5 GATE] 1d macro regime: 50d EMA above 200d EMA = "uptrend" ----
        daily = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe=self.regime_timeframe
        )
        daily["r_fast"] = ta.EMA(daily, timeperiod=self.regime_ema_fast.value)
        daily["r_slow"] = ta.EMA(daily, timeperiod=self.regime_ema_slow.value)
        daily["regime_up"] = (daily["r_fast"] > daily["r_slow"]).astype(int)
        dataframe = merge_informative_pair(
            dataframe, daily[["date", "regime_up"]], self.timeframe,
            self.regime_timeframe, ffill=True
        )
        # merge suffixes the column -> "regime_up_1d"

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] > dataframe["ema_slow"])
                & (dataframe["rsi"] > self.buy_rsi.value)
                & (dataframe["volume"] > dataframe["volume_sma"])
                & (dataframe["close_1h"] > dataframe["ema9_1h"])
                & (dataframe["ema9_rising_1h"])

                # [V5 GATE] the one new line: only buy when the daily 50/200
                # macro trend is UP. In a daily downtrend this is False on every
                # candle, so the bot takes zero trades and sits in cash.
                & (dataframe["regime_up_1d"] == 1)

                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        atr_multiplier = self.atr_stop_mult.value
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return None
        last_atr = dataframe["atr"].iat[-1]
        if last_atr is None or last_atr <= 0 or current_rate <= 0:
            return None
        atr_stop_distance = (atr_multiplier * last_atr) / current_rate
        return max(-atr_stop_distance, self.stoploss)
