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
#
# [2026-07-01] Switched entry/exit to a 20-candle RANGE strategy: buy near the
# rolling 20-candle low (bottom 15% of the band), sell near the rolling 20-candle
# high (top 15%). Long-only; stop-loss/ROI/protections kept as guardrails.
#
# [2026-07-03 ADAPTIVE DUAL-MODE] The 07-01 rewrite silently DROPPED the 50/200
# uptrend gate this bot was validated with — it was buying every 20d-low approach
# in a bear market (the exact V2 knife-catch failure the docstring warns about).
# Restored the gate for normal dip-buys, and added an explicit half-stake
# capitulation-bounce mode (daily RSI<30 at the range bottom, up-close confirmed)
# so the bot still trades the bear regime — deliberately, at reduced size, with
# fast exits — instead of either churning or sitting dead.

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter


class SwingDipV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"                 # daily candles -> swing, not scalping
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
    buy_rsi  = IntParameter(20, 45, default=35, space="buy",  optimize=False)
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

    # Stop: daily swings need room, and the uptrend filter limits downside.
    # [2026-07-03] -0.15 -> -0.10. Backtest 2024-01->2025-12 (15-pair basket):
    # 58% win rate yet -29% net — winners exit at the range top (~+5-8%) while
    # losers rode all the way to -15%, an unbeatable ratio. -10% keeps the
    # asymmetry survivable without clipping ordinary daily noise.
    stoploss = -0.10

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
        # [20-CANDLE RANGE 2026-07-01] Adaptive support/resistance: buy near the
        # rolling 20-candle low, sell near the rolling 20-candle high. shift(1) keeps
        # the current forming bar out of its own band (no look-ahead).
        dataframe["rng_low20"] = dataframe["low"].rolling(20).min().shift(1)
        dataframe["rng_high20"] = dataframe["high"].rolling(20).max().shift(1)
        _rng_band = (dataframe["rng_high20"] - dataframe["rng_low20"]).clip(lower=1e-9)
        # [2026-07-03 ADAPTIVE] Buy zone widened 0.15 -> 0.20 (more dip entries in
        # the friendly regime); bounce zone is deeper (bottom 10%) for bear use.
        dataframe["rng_buy_zone"] = dataframe["rng_low20"] + 0.20 * _rng_band
        dataframe["rng_sell_zone"] = dataframe["rng_high20"] - 0.15 * _rng_band
        dataframe["rng_bounce_zone"] = dataframe["rng_low20"] + 0.10 * _rng_band
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # [2026-07-03 ADAPTIVE] Two regime modes (own-pair daily 50/200 EMA):
        uptick = dataframe["close"] > dataframe["close"].shift(1)
        live_vol = dataframe["volume"] > 0

        # UPTREND: the ORIGINAL VALIDATED entry — a genuine oversold dip (RSI<35
        # AND close under the lower Bollinger) inside an uptrend. [2026-07-03]
        # Backtests showed the 07-01 "buy near the 20d range low" replacement lost
        # -29% even in the 2024-25 up-window; the Bollinger dip demands real
        # capitulation, not every drift to the bottom of a drifting range.
        dataframe.loc[
            (
                (dataframe["ema50"] > dataframe["ema200"])
                & (dataframe["rsi"] < self.buy_rsi.value)
                & (dataframe["close"] < dataframe["bb_lower"])
                & live_vol
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "dip_in_uptrend")

        # DOWNTREND: capitulation bounce only — daily RSI<30 at the very bottom
        # of the 20d range, AFTER the low has held ~5 days (a stabilized base,
        # not a rolling waterfall), confirmed by an up-close. Half stake, fast
        # exit via the custom_* methods below.
        dataframe.loc[
            (
                (dataframe["ema50"] <= dataframe["ema200"])
                & (dataframe["rsi"] < 30)
                & (dataframe["rng_low20"] == dataframe["rng_low20"].shift(5))
                & (dataframe["close"] <= dataframe["rng_bounce_zone"])
                & uptick & live_vol
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "bear_bounce")
        return dataframe

    # [2026-07-03 ADAPTIVE] Bear bounces run half stake — counter-trend swings
    # don't earn full conviction sizing.
    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        if entry_tag == "bear_bounce":
            half = proposed_stake * 0.5
            if min_stake is None or half >= min_stake:
                return half
        return proposed_stake

    # [2026-07-03 ADAPTIVE] Bear bounces bank +6% into the first rally or time out
    # after 10 days — they must not become hopeful bear-market bagholds. Uptrend
    # dips keep the normal ROI ladder / range-high exit.
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit,
                    **kwargs):
        if trade.enter_tag == "bear_bounce":
            if current_profit >= 0.06:
                return "bounce_take"
            if (current_time - trade.open_date_utc).total_seconds() >= 10 * 86400:
                return "bounce_timeout"
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # [2026-07-03] Sell into strength, two ways: the validated RSI>65 exit OR
        # price reaching the top of the 20d range — whichever comes first. More
        # closes, and winners are banked into rallies instead of round-tripping.
        dataframe.loc[
            (
                (
                    (dataframe["rsi"] > self.sell_rsi.value)
                    | (dataframe["close"] >= dataframe["rng_sell_zone"])
                )
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
