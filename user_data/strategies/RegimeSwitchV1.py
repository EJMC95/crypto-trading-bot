# RegimeSwitchV1.py
# ---------------------------------------------------------------------------
# Prototype regime-adaptive Freqtrade strategy for Eamon's fleet.
#
# Idea: read TWO axes of market regime and switch behaviour:
#   - Direction  : price vs EMA200 + EMA50 slope        (up / down)
#   - Character  : ADX(14)                              (trending / choppy)
#
#   UP + TREND   -> go LONG  (trend follow)
#   DOWN + TREND -> go SHORT (perps/futures only)
#   *_ CHOP      -> stand down (no new trend trades)
#
# Regime is computed on the DAILY informative timeframe (the "tide") and used
# to gate entries on the trading timeframe. Hysteresis on ADX (enter >=25,
# only allow chop <=20) reduces whipsaw at transitions.
#
# STATUS: dry-run backtest prototype. Requires a futures/margin config for the
# short side (can_short). Backtest locally in ~/freqtrade over a window that
# contains BOTH an uptrend and a downtrend before trusting it. Do NOT ship to
# Railway or go live without explicit sign-off.
# ---------------------------------------------------------------------------

from datetime import datetime
from typing import Optional

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    informative,
)
import freqtrade.vendor.qtpylib.indicators as qtpylib


class RegimeSwitchV1(IStrategy):

    INTERFACE_VERSION = 3

    # --- Core config ---------------------------------------------------------
    timeframe = "1h"
    informative_timeframe = "1d"

    can_short = True                 # requires futures/margin trading config
    process_only_new_candles = True
    startup_candle_count = 220       # enough for EMA200 on the daily

    # Wide backstop stop; real risk control is the ATR logic in custom_stoploss.
    stoploss = -0.20
    use_custom_stoploss = True

    # Let regime + exit signals do the work; ROI kept loose.
    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.02, "1440": 0}

    trailing_stop = False

    # --- Hyperoptable regime thresholds -------------------------------------
    adx_trend = IntParameter(20, 35, default=25, space="buy")   # ADX >= -> trend
    adx_chop = IntParameter(12, 22, default=20, space="buy")    # ADX <= -> chop
    atr_stop_mult = DecimalParameter(1.5, 4.0, default=2.5, decimals=1, space="sell")

    plot_config = {
        "main_plot": {"ema50": {}, "ema200": {}},
        "subplots": {"ADX": {"adx": {}}, "REGIME": {"regime_dir": {}}},
    }

    # --- Daily informative: compute the fleet "regime" ----------------------
    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # Direction: +1 up, -1 down, 0 mixed
        ema50_slope = dataframe["ema50"] - dataframe["ema50"].shift(3)
        up = (dataframe["close"] > dataframe["ema200"]) & (ema50_slope > 0)
        down = (dataframe["close"] < dataframe["ema200"]) & (ema50_slope < 0)
        dataframe["regime_dir"] = 0
        dataframe.loc[up, "regime_dir"] = 1
        dataframe.loc[down, "regime_dir"] = -1

        # Character: trending vs choppy, with hysteresis so it doesn't flip-flop
        # in the 20-25 band. 1 = trend, 0 = chop; carry previous value between.
        is_trend = dataframe["adx"] >= self.adx_trend.value
        is_chop = dataframe["adx"] <= self.adx_chop.value
        char = []
        prev = 0
        for t, c in zip(is_trend.tolist(), is_chop.tolist()):
            if t:
                prev = 1
            elif c:
                prev = 0
            # else: hold previous (hysteresis band)
            char.append(prev)
        dataframe["regime_trend"] = char

        return dataframe

    # --- Trading timeframe indicators ---------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    # --- Entries -------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Regime columns are merged with the '_1d' suffix by @informative.
        up_trend = (dataframe["regime_dir_1d"] == 1) & (dataframe["regime_trend_1d"] == 1)
        down_trend = (dataframe["regime_dir_1d"] == -1) & (dataframe["regime_trend_1d"] == 1)

        # LONG: only in an up-trend regime, on a fast/slow momentum cross up.
        dataframe.loc[
            up_trend
            & qtpylib.crossed_above(dataframe["ema_fast"], dataframe["ema_slow"])
            & (dataframe["rsi"] > 50)
            & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "up_trend_long")

        # SHORT: only in a down-trend regime, on a momentum cross down (perps).
        dataframe.loc[
            down_trend
            & qtpylib.crossed_below(dataframe["ema_fast"], dataframe["ema_slow"])
            & (dataframe["rsi"] < 50)
            & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "down_trend_short")

        return dataframe

    # --- Exits ---------------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit long when regime leaves up-trend OR momentum crosses back down.
        left_up = (dataframe["regime_dir_1d"] != 1) | (dataframe["regime_trend_1d"] == 0)
        dataframe.loc[
            left_up | qtpylib.crossed_below(dataframe["ema_fast"], dataframe["ema_slow"]),
            ["exit_long", "exit_tag"],
        ] = (1, "exit_long_regime")

        # Exit short when regime leaves down-trend OR momentum crosses back up.
        left_down = (dataframe["regime_dir_1d"] != -1) | (dataframe["regime_trend_1d"] == 0)
        dataframe.loc[
            left_down | qtpylib.crossed_above(dataframe["ema_fast"], dataframe["ema_slow"]),
            ["exit_short", "exit_tag"],
        ] = (1, "exit_short_regime")

        return dataframe

    # --- ATR-based dynamic stop ---------------------------------------------
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
        # Stop distance = atr_stop_mult * ATR as a fraction of entry price.
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        atr = df["atr"].iat[-1]
        if atr is None or atr <= 0:
            return None
        stop_frac = (self.atr_stop_mult.value * atr) / trade.open_rate
        # Return as a negative relative stop (Freqtrade convention).
        return -abs(float(stop_frac))

    # --- Leverage (perps): keep modest for dry-run ---------------------------
    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        return min(2.0, max_leverage)
