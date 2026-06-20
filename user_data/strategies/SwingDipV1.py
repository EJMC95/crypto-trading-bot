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

import logging
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter

logger = logging.getLogger(__name__)


class SwingDipV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "4h"                 # [SPED UP] was 1d; 4h = 6x more evaluations
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
        # [LOOSENED v2] macro gate: 50>200 OR price above the 200d.
        trend_ok = (dataframe["ema50"] > dataframe["ema200"]) | (dataframe["close"] > dataframe["ema200"])
        # [LOOSENED v2] dip paths widened (daily = naturally few signals):
        # [LOOSENED] wider dip triggers (still daily timeframe = slow cadence).
        dip_ok = (
            (dataframe["close"] < dataframe["bb_lower"])                               # any BB dip
            | (dataframe["rsi"] < 45)                                                  # oversold-ish
            | ((dataframe["close"] < dataframe["ema50"]) & (dataframe["rsi"] < 55))    # pullback below 50d
        )
        dataframe.loc[
            trend_ok & dip_ok & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        self._entry_diag(dataframe, metadata, {
            "trend_ok": trend_ok, "dip_ok": dip_ok, "rsi": dataframe["rsi"],
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
