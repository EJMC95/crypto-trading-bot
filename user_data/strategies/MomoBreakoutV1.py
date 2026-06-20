# MomoBreakoutV1.py
#
# IMPROVED (now fires in ranging/pullback markets, not just breakouts):
#   V1 only bought on BREAKOUTS (close > 30-bar high). In a sideways/falling market, this never fired.
#
#   V1 now adds PULLBACK entry:
#     - Entry 1 (breakout): close > 30-bar high AND close > 200-EMA (unchanged, the original edge)
#     - Entry 2 (pullback): close < 15-bar low AND close > 200-EMA AND rsi < 50
#       i.e. within an uptrend, if price dips below a 15-bar floor and RSI is not too hot, buy it back.
#   Result: captures both breakouts (the original signal) AND pullbacks within the uptrend (new signal).
#   The original backtest only sees Entry 1, so this is an _augmentation_ that should not break the tested edge.
#
#   Exit logic: unchanged (Donchian breakdown + -12% stop).

import logging
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter

logger = logging.getLogger(__name__)


class MomoBreakoutV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = False

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "StoplossGuard", "lookback_period_candles": 42,
             "trade_limit": 3, "stop_duration_candles": 12, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 90, "trade_limit": 8,
             "stop_duration_candles": 18, "max_allowed_drawdown": 0.25},
        ]

    entry_lookback = IntParameter(20, 45, default=30, space="buy",  optimize=False)
    exit_lookback  = IntParameter(8,  25, default=15, space="sell", optimize=False)
    trend_ema      = IntParameter(100, 250, default=200, space="buy", optimize=False)

    # [SIDEWAYS v2] loose ROI ladder so range trades actually BANK profit while
    # breakouts still get room to run: take 15% any time, easing to break-even
    # after ~1 week.
    minimal_roi = {"0": 0.15, "1440": 0.08, "4320": 0.03, "10080": 0.0}
    stoploss = -0.12

    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 260

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.trend_ema.value)
        # [SOFTENED GATE] is the long-term trend turning up? (200-EMA higher than
        # 5 bars ago). Lets entries fire as a trend forms, not only once price is
        # already extended above the EMA.
        dataframe["ema_trend_rising"] = dataframe["ema_trend"] > dataframe["ema_trend"].shift(5)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        # Donchian channels (shift(1) for no look-ahead).
        dataframe["dc_high"] = dataframe["high"].rolling(self.entry_lookback.value).max().shift(1)
        dataframe["dc_low"]  = dataframe["low"].rolling(self.exit_lookback.value).min().shift(1)
        # IMPROVED: add a shorter 15-bar low for pullback entry
        dataframe["pullback_low"] = dataframe["low"].rolling(self.exit_lookback.value).min().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # [LOOSENED v2] trend filter: price above 200-EMA OR 200-EMA rising.
        trend_ok = (dataframe["close"] > dataframe["ema_trend"]) | (dataframe["ema_trend_rising"])
        # [LOOSENED v2] three entry paths (breakout / pullback / momentum-continuation).
        setup_ok = (
            (dataframe["close"] > dataframe["dc_high"])                                      # breakout
            | ((dataframe["close"] < dataframe["pullback_low"]) & (dataframe["rsi"] < 55))   # pullback
            | ((dataframe["close"] > dataframe["ema_trend"]) & (dataframe["rsi"] > 52))      # momentum continuation
        )
        # [SIDEWAYS v2] range mean-reversion path: buy oversold REGARDLESS of trend,
        # so the bot works choppy/sideways markets (buy the dip, sell the rip below).
        range_buy = (dataframe["rsi"] < 45)   # RELAXED 40->45: more oversold dips qualify
        dataframe.loc[
            ((trend_ok & setup_ok) | range_buy) & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        self._entry_diag(dataframe, metadata, {
            "trend_ok": trend_ok, "setup_ok": setup_ok,
            "range_buy": range_buy, "rsi": dataframe["rsi"],
        })
        return dataframe

    def _entry_diag(self, dataframe, metadata, gates):
        """Log latest-candle gate states so live logs reveal why we (don't) enter."""
        try:
            if dataframe is None or len(dataframe) == 0:
                return
            sig = int(dataframe["enter_long"].tail(50).sum()) if "enter_long" in dataframe else 0
            parts = []
            for k, col in gates.items():
                try:
                    parts.append(f"{k}={col.iloc[-1]}")
                except Exception:
                    pass
            logger.info("ENTRY-DIAG %s enter_long_last50=%d %s",
                        metadata.get("pair"), sig, " ".join(parts))
        except Exception as e:
            logger.info("ENTRY-DIAG error %s: %s", metadata.get("pair"), e)

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # [SIDEWAYS v2] exit on Donchian breakdown OR overbought (sell the rip).
        dataframe.loc[
            (
                ((dataframe["close"] < dataframe["dc_low"]) | (dataframe["rsi"] > 65))
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
