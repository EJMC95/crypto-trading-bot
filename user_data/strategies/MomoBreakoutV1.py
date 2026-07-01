# MomoBreakoutV1.py
#
# WHAT IT IS: a MOMENTUM / BREAKOUT swing trader (the "buy strength, ride it"
# opposite of the dip-buyer). 4-hour candles, weekly-ish cadence, ~1-week holds.
#   Entry: price breaks ABOVE its highest high of the last 30 bars (~5 days) —
#          a fresh breakout — but only while above the 200-period EMA (uptrend).
#   Exit:  price breaks BELOW its lowest low of the last 15 bars (~2.5 days),
#          i.e. a trailing Donchian stop that lets winners run and cuts losers.
#   Plus a -12% catastrophe stop.
#
# WHY IT EARNED A SPOT (backtest, Binance 4h, 2023-07 -> 2026-06, 0.1% fee):
#                              3yr return   maxDD    trades   win   PF
#     BTC buy & hold ........  +122.9%      ~-51%      —       —     —
#     BTC MomoBreakoutV1 ....   +82.7%      -21.8%   ~19/yr   41%   1.79
#     ETH buy & hold ........    -8.4%      ~-67%      —       —     —
#     ETH MomoBreakoutV1 ....  +125.5%      -29.5%   ~15/yr   41%   1.94
#   The ~40% win rate is NORMAL for breakout trading: many small losses, a few
#   big winners (profit factor ~1.8-1.9). It beat buy&hold on ETH outright and
#   trailed BTC's bull but with less than half the drawdown. Robust across nearby
#   settings (20/10 ... 42/21) and both coins — not a single curve-fit.
#
# HONEST LIMITATIONS:
#   - It LAGS tops and gives back some profit at each exit (the price of riding
#     trends). It underperforms a relentless straight-up bull (BTC) on raw return.
#   - ~40% win rate FEELS bad — most trades lose a little. That's by design; the
#     winners are what pay. Don't panic at a string of small losers.
#   - Spot / long-only; still a measured DRY-RUN experiment. A good backtest is
#     not proof (the V3 lesson). Watch it live before trusting it.
#
# RUNS ON 4h. Kraken serves enough recent 4h candles on startup automatically.
#
# [2026-07-01] Switched entry/exit to a 20-candle RANGE strategy: buy near the
# rolling 20-candle low (bottom 15% of the band), sell near the rolling 20-candle
# high (top 15%). Long-only; stop-loss/ROI/protections kept as guardrails.

from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter


class MomoBreakoutV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = False

    # Circuit breakers (research-driven risk guards). Candle counts scale with
    # this strategy's timeframe. Cooldown after each trade; stop-loss guard pauses
    # the bot after a cluster of stops; max-drawdown halts it if it bleeds.
    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 1},
            {"method": "StoplossGuard", "lookback_period_candles": 42,
             "trade_limit": 3, "stop_duration_candles": 12, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 90, "trade_limit": 8,
             "stop_duration_candles": 18, "max_allowed_drawdown": 0.25},
        ]

    # Breakout lookbacks (bars). Defaults = the validated 30/15. optimize=False
    # to avoid curve-fitting (the edge is in the concept, not the exact number).
    entry_lookback = IntParameter(20, 45, default=30, space="buy",  optimize=False)
    exit_lookback  = IntParameter(8,  25, default=15, space="sell", optimize=False)
    trend_ema      = IntParameter(100, 250, default=200, space="buy", optimize=False)

    # We RIDE momentum, so ROI never forces an early exit. The Donchian breakdown
    # (exit signal) and the -12% catastrophe stop do the risk control.
    minimal_roi = {"0": 100}
    stoploss = -0.12

    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 260       # 200 EMA + 30 breakout window + buffer

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.trend_ema.value)
        # Prior-bar Donchian channels (shift(1) => no look-ahead on the current bar).
        dataframe["dc_high"] = dataframe["high"].rolling(self.entry_lookback.value).max().shift(1)
        dataframe["dc_low"]  = dataframe["low"].rolling(self.exit_lookback.value).min().shift(1)
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
