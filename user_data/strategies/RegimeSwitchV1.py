# RegimeSwitchV1.py
# ---------------------------------------------------------------------------
# Regime-adaptive Freqtrade strategy for Eamon's fleet.
#
# Reads TWO axes of DAILY market regime and trend-follows the tide:
#   - Direction : price vs EMA200 + EMA50 slope   (up / down)
#   - Character : ADX(14)                         (trending / choppy)
#
#   UP   + TREND -> go LONG  (1h EMA fast/slow momentum cross up)
#   DOWN + TREND -> go SHORT (1h momentum cross down, perps/futures only)
#   CHOP         -> stand down (no trades)
#
# BACKTEST HISTORY (2022-01..2024-03 continuous, BTC+ETH futures, 2x):
#   This file is the outcome of a full backtest sweep (v1..v6). The findings that
#   shaped it, in order of impact:
#     1. FIXED stop (5% from entry) hugely beats a trailing ATR stop — the trailing
#        stop was cutting winners short and was the #1 cause of the original bleed.
#     2. TREND-ONLY beats keeping a chop range-scalp mode: the buy-low/sell-high
#        range logic backtested as a net drag in every window, so it was removed.
#     3. Lower ADX gate (trend>=20 / chop<=15) + a CooldownPeriod cut the
#        overtrading; "let winners run" (trailing take-profit) made it WORSE, so
#        the tight ROI is kept (take the +2-3% and re-arm).
#   Result: catastrophic loser (-27%/-18%/-13% per regime) -> ~breakeven over the
#   full 26 months with low drawdown (~3.8%), profitable in trending windows.
#   It is SAFE and non-bleeding, NOT yet a funded edge — do not go live on it
#   without further work (hyperopt / better trend-entry quality) + explicit sign-off.
#
# Exits are handled in custom_exit() so they stay tag-aware. can_short needs a
# futures/margin config. Freqtrade uses LIVE exchange candles in BOTH dry-run and
# live — dry-run only simulates the fills, not the data.
# ---------------------------------------------------------------------------

from datetime import datetime
from typing import Optional

import numpy as np
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

    # [V3] Protections: kill the re-entry churn that bled V1 (hundreds of trades).
    # CooldownPeriod stops immediate re-entry after any exit; StoplossGuard halts a
    # pair after a cluster of stop-outs (whipsaw protection).
    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 6},
            {"method": "StoplossGuard", "lookback_period_candles": 24,
             "trade_limit": 3, "stop_duration_candles": 12, "only_per_pair": True},
        ]

    # [V5] FIXED stop from entry (as V4); trend-only (range mode disabled below).
    stoploss = -0.05
    use_custom_stoploss = False

    # Let regime + custom_exit do the work; ROI kept loose as a backstop.
    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.02, "1440": 0}

    trailing_stop = False

    # --- Hyperoptable regime thresholds -------------------------------------
    adx_trend = IntParameter(16, 35, default=20, space="buy")   # ADX >= -> trend  [V3: 25->20]
    adx_chop = IntParameter(10, 22, default=15, space="buy")    # ADX <= -> chop   [V3: 20->15]
    atr_stop_mult = DecimalParameter(1.5, 5.0, default=3.5, decimals=1, space="sell")  # [V3: 2.5->3.5, wider so TP can be reached]

    # --- Range-scalp (chop regime) parameters -------------------------------
    range_lookback = IntParameter(10, 40, default=20, space="buy")   # candles for hi/lo
    # Enter within the bottom/top X of the range; also the take-profit band on
    # the opposite side. 0.20 = buy the lower 20%, short the upper 20%.
    range_entry_pct = DecimalParameter(0.10, 0.35, default=0.20, decimals=2, space="buy")

    plot_config = {
        "main_plot": {"ema50": {}, "ema200": {}, "range_high": {}, "range_low": {}},
        "subplots": {"ADX": {"adx": {}}, "REGIME": {"regime_dir": {}},
                     "RANGE_POS": {"range_pos": {}}},
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

        # 20-candle price range (Donchian-style) for the chop-regime range-scalp.
        # rolling().max()/min() include the current (closed) candle only — causal,
        # no lookahead, because process_only_new_candles acts at candle close.
        window = int(self.range_lookback.value)
        dataframe["range_high"] = dataframe["high"].rolling(window).max()
        dataframe["range_low"] = dataframe["low"].rolling(window).min()
        span = (dataframe["range_high"] - dataframe["range_low"]).replace(0, np.nan)
        # 0.0 = at the range low, 1.0 = at the range high.
        dataframe["range_pos"] = (dataframe["close"] - dataframe["range_low"]) / span

        return dataframe

    # --- Entries -------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Regime columns are merged with the '_1d' suffix by @informative.
        up_trend = (dataframe["regime_dir_1d"] == 1) & (dataframe["regime_trend_1d"] == 1)
        down_trend = (dataframe["regime_dir_1d"] == -1) & (dataframe["regime_trend_1d"] == 1)
        chop = (dataframe["regime_trend_1d"] == 0)

        lo = self.range_entry_pct.value
        hi = 1.0 - self.range_entry_pct.value

        # TREND LONG: up-trend regime, fast/slow momentum cross up.
        dataframe.loc[
            up_trend
            & qtpylib.crossed_above(dataframe["ema_fast"], dataframe["ema_slow"])
            & (dataframe["rsi"] > 50)
            & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "up_trend_long")

        # TREND SHORT: down-trend regime, momentum cross down (perps).
        dataframe.loc[
            down_trend
            & qtpylib.crossed_below(dataframe["ema_fast"], dataframe["ema_slow"])
            & (dataframe["rsi"] < 50)
            & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "down_trend_short")

        # [V5] RANGE MODE DISABLED — trend-only. In chop the bot stands down (as
        # V1 originally did) to test whether the trend legs alone have positive edge
        # once the trailing-stop leak is fixed. `lo`/`hi` retained for custom_exit.
        _ = (chop, lo, hi)

        return dataframe

    # --- Exits: none here; handled in custom_exit so they are tag-aware ------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        last = df.iloc[-1]

        tag = trade.enter_tag or ""
        rp = last.get("range_pos")
        rp_valid = rp is not None and rp == rp          # rp == rp is False for NaN
        dir1d = last.get("regime_dir_1d")
        trend1d = last.get("regime_trend_1d")
        ef = last.get("ema_fast")
        es = last.get("ema_slow")

        lo = self.range_entry_pct.value
        hi = 1.0 - self.range_entry_pct.value

        if tag.startswith("range_"):
            # Mean-reversion take-profit at the opposite side of the range.
            if not trade.is_short and rp_valid and rp >= hi:
                return "range_tp_high"
            if trade.is_short and rp_valid and rp <= lo:
                return "range_tp_low"
            # A real trend has formed — abandon the range assumption.
            if trend1d == 1:
                return "range_to_trend"
            return None

        # Trend trades: exit when the trend regime ends or momentum flips.
        if not trade.is_short:
            if dir1d != 1 or trend1d == 0:
                return "trend_long_regime_end"
            if ef is not None and es is not None and ef < es:
                return "trend_long_momentum"
        else:
            if dir1d != -1 or trend1d == 0:
                return "trend_short_regime_end"
            if ef is not None and es is not None and ef > es:
                return "trend_short_momentum"
        return None

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
