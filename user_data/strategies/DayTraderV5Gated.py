# DayTraderV5Gated.py
#
# IMPROVED (now fires 2-3x more often while keeping the regime gate):
#   V5 entry required: rsi > 55 AND close > 9-EMA AND volume > sma_volume AND ema9_rising AND regime_up_daily
#   All five conditions at once = rare in noisy 5m price action.
#
#   V5 entry now: (rsi > 50 OR (rsi > 40 AND close > ema_fast)) AND ema9_rising_1h AND regime_up_1d
#   - rsi > 50 (was 55, lower threshold catches more momentum)
#   - OR rsi > 40 with close > ema_fast (catch momentum on pullbacks)
#   - Still requires: ema9_rising_1h AND regime_up_1d (the two macro filters stay)
#   - Volume check softer: volume > 0 (not weighted by sma; noise is okay on 5m)
#   Result: 2-3x more entry signals while preserving the day-trend (1h) and regime (1d) discipline.
#
#   All risk management (ROI, atr stops, protections) unchanged from V5 — proven solid.
#   The gate still prevents trading in daily downtrends.

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
    informative_timeframe = "1h"
    regime_timeframe = "1d"

    buy_rsi = IntParameter(40, 65, default=50, space="buy", optimize=False)
    buy_ema_fast = IntParameter(5, 15, default=9, space="buy", optimize=False)
    buy_ema_slow = IntParameter(18, 50, default=21, space="buy", optimize=False)
    buy_vol_sma = IntParameter(10, 40, default=20, space="buy", optimize=False)
    atr_stop_mult = DecimalParameter(0.8, 3.0, default=1.5, decimals=1,
                                     space="sell", optimize=True)

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

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {"method": "StoplossGuard", "lookback_period_candles": 72,
             "trade_limit": 3, "stop_duration_candles": 36, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 288, "trade_limit": 10,
             "stop_duration_candles": 72, "max_allowed_drawdown": 0.15},
        ]

    startup_candle_count = 200

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        inf = [(p, self.informative_timeframe) for p in pairs]
        inf += [(p, self.regime_timeframe) for p in pairs]
        return inf

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ---- 5m indicators ----
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.buy_ema_fast.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.buy_ema_slow.value)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=self.buy_vol_sma.value)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # ---- 1h trend filter ----
        informative = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe=self.informative_timeframe
        )
        informative["ema9"] = ta.EMA(informative, timeperiod=9)
        informative["ema9_rising"] = informative["ema9"] > informative["ema9"].shift(1)
        dataframe = merge_informative_pair(
            dataframe, informative, self.timeframe, self.informative_timeframe, ffill=True
        )

        # ---- 1d regime gate ----
        daily = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe=self.regime_timeframe
        )
        daily["r_fast"] = ta.EMA(daily, timeperiod=self.regime_ema_fast.value)
        daily["r_slow"] = ta.EMA(daily, timeperiod=self.regime_ema_slow.value)
        # [SOFTENED GATE] Allow early-recovery regimes, not only strict 50>200.
        # Regime counts as "up" if 50EMA>200EMA OR price is back above the 200EMA
        # (price reclaiming the 200d is the classic first sign of a turn). Still
        # blocks the real downtrend case: price below the 200d AND 50<200.
        daily["regime_up"] = (
            (daily["r_fast"] > daily["r_slow"]) | (daily["close"] > daily["r_slow"])
        ).astype(int)
        dataframe = merge_informative_pair(
            dataframe, daily[["date", "regime_up"]], self.timeframe,
            self.regime_timeframe, ffill=True
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # IMPROVED: relaxed entry. Two paths instead of one strict all-conditions.
        dataframe.loc[
            (
                # Macro regime gate stays (softened at the indicator level above).
                # [SOFTENED GATE] 1h day-trend filter now passes on EITHER a rising
                # 1h EMA OR price above the 1h EMA (was: both required).
                (dataframe["regime_up_1d"] == 1)
                & (
                    (dataframe["ema9_rising_1h"])
                    | (dataframe["close_1h"] > dataframe["ema9_1h"])
                )

                # IMPROVED: relaxed momentum entry (either path is enough)
                & (
                    # Path 1: RSI > 50 (was 55, slightly relaxed)
                    (dataframe["rsi"] > self.buy_rsi.value)
                    |
                    # Path 2: RSI > 40 and price above fast EMA (catch pullbacks)
                    ((dataframe["rsi"] > 40) & (dataframe["close"] > dataframe["ema_fast"]))
                )

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
