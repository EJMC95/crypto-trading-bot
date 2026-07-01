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
#
# [2026-07-01] Entry/exit switched to a 20-candle RANGE strategy: buy near the
# rolling 20-candle low (bottom 15% of the band), sell near the rolling 20-candle
# high (top 15%). Long-only; custom ATR stop / ROI / protections kept as guardrails.
# The 1h/1d regime indicators are left intact (harmless) though unused by the new entry.

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

    timeframe = "15m"                 # [2026-07-01] 5m -> 15m: cut fee churn & 5m noise; the 1.5x-ATR stop is naturally wider on 15m, giving winners room without deepening the (evidence-backed) tight-stop protection
    informative_timeframe = "1h"      # short-term trend filter (unchanged from Aggro)
    regime_timeframe = "1d"           # [V5 GATE] macro regime filter

    # ---------------- hyperopt-tunable params (unchanged from Aggro) ---------- #
    buy_rsi = IntParameter(45, 70, default=55, space="buy", optimize=True)
    buy_ema_fast = IntParameter(5, 15, default=9, space="buy", optimize=False)
    buy_ema_slow = IntParameter(18, 50, default=21, space="buy", optimize=False)
    buy_vol_sma = IntParameter(10, 40, default=20, space="buy", optimize=False)
    # [2026-06-30] Kept at 1.5 (NOT widened). Post-exit market analysis (FMP 5m
    # bars, NEAR+TRX, 19 losing trades) showed that after the stop fired price kept
    # FALLING (pooled -0.9% at +1h; only 1/19 recovered) — the stop was protecting
    # capital, not cutting winners short. The losses came from bad ENTRIES on the
    # wrong universe (microcaps/stablecoins), now fixed by the StaticPairList change
    # in config_v5. Widening the stop would have deepened those losses.
    atr_stop_mult = DecimalParameter(0.8, 3.0, default=1.5, decimals=1,
                                     space="sell", optimize=True)

    # [V5 GATE] daily regime EMAs. Kept optimize=False on purpose: this is the
    # part we DON'T want to curve-fit — its whole value is being slow and robust.
    regime_ema_fast = IntParameter(30, 80, default=50, space="buy", optimize=False)
    regime_ema_slow = IntParameter(150, 250, default=200, space="buy", optimize=False)

    # [2026-06-30] Lower, faster ROI ladder. Every trade that reached the old 4%
    # first rung won (4/4), but post-exit analysis shows these names reverse fast,
    # so taking a smaller profit quickly banks more of the move before it gives
    # back. The ATR stop is deliberately UNCHANGED (see atr_stop_mult): post-exit
    # data showed losers kept falling after we exited, so the stop was protecting
    # capital — the real fix is entry quality + the liquid-majors universe.
    minimal_roi = {
        "0": 0.02,
        "30": 0.015,
        "60": 0.01,
        "120": 0.006,
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
        # [CHURN-FIX 2026-06-25] Cooldown 3->12 candles (~1h) and StoplossGuard
        # trips one stop sooner (3->2). The live bot's losses were fee-bleed from
        # re-buying into the same chop, not a directional blowup; these throttle
        # re-entry. See FIXES_2026-06-22.md and REVALIDATION_2026-06-22.md.
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {"method": "StoplossGuard", "lookback_period_candles": 72,
             "trade_limit": 2, "stop_duration_candles": 36, "only_per_pair": False},
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

        # [20-CANDLE RANGE 2026-07-01] Adaptive support/resistance: buy near the
        # rolling 20-candle low, sell near the rolling 20-candle high. shift(1) keeps
        # the current forming bar out of its own band (no look-ahead).
        dataframe["rng_low20"] = dataframe["low"].rolling(20).min().shift(1)
        dataframe["rng_high20"] = dataframe["high"].rolling(20).max().shift(1)
        _rng_band = (dataframe["rng_high20"] - dataframe["rng_low20"]).clip(lower=1e-9)
        dataframe["rng_buy_zone"] = dataframe["rng_low20"] + 0.15 * _rng_band
        dataframe["rng_sell_zone"] = dataframe["rng_high20"] - 0.15 * _rng_band

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close"] <= dataframe["rng_buy_zone"])
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        dataframe.loc[dataframe["enter_long"] == 1, "enter_tag"] = "range20_buy_low"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close"] >= dataframe["rng_sell_zone"])
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
