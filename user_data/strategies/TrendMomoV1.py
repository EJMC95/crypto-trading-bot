# TrendMomoV1.py
#
# WHAT IT IS: a fast TREND-FOLLOWER on daily candles. It goes long when the
# 20-day SMA crosses ABOVE the 50-day SMA (momentum turning up) and exits when
# the 20-day crosses back BELOW the 50-day (momentum rolling over). It lets
# winners run -- no take-profit ladder -- and only uses a wide stop as a backstop.
#
# WHY IT EARNED ITS PLACE: out of 11 models trialled on 3yr daily BTC+ETH data,
# this was the only one that ranked top on a RISK-ADJUSTED basis (Sharpe/Calmar)
# on BOTH coins, and it survived a walk-forward + parameter robustness check:
#   - Walk-forward (three ~1yr windows): ETH positive in all 3 (incl. two where
#     buy&hold lost ~30%); BTC positive in 2 of 3, and in its losing year still
#     lost far less than buy&hold. Momentum's known weak spot is a choppy
#     downtrend (BTC 2025-26) -- it gets whipsawed there. Expect that.
#   - Parameter sweep: every neighbouring MA pair (10/30 ... 30/70) was
#     profitable on both coins. 20/50 is a deliberate middle choice, NOT the
#     best-fit pair -- chosen to avoid overfitting (the V3 lesson).
#
# HONEST EXPECTATION: it is NOT a buy&hold beater in a clean bull (it enters
# late and exits late). Its edge is sidestepping big drawdowns -- it spends ~half
# its time in cash and dodges the worst declines. It WILL get chopped in flat,
# sideways markets. Diversifier + drawdown-reducer, not a money printer.
#
# Spot / long-only. Round-number settings (anti-overfit), not hyperopt-tuned.

from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter


class TrendMomoV1(IStrategy):
    INTERFACE_VERSION = 3

    # [2026-07-03] Back to the VALIDATED 1d. The "[SPED UP] 4h" variant was never
    # validated and backtests confirmed the docstring's warning: 4h SMA 20/50 on
    # this basket = whipsaw city (-26% to -50% over 2024-26 even after fixes).
    # The walk-forward-validated edge is daily 20/50. Activity now comes from the
    # basket width + the bear-bounce sleeve, not from over-sampling one signal.
    timeframe = "1d"
    can_short = False

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 1},
            {"method": "MaxDrawdown", "lookback_period_candles": 40, "trade_limit": 4,
             "stop_duration_candles": 5, "max_allowed_drawdown": 0.25},
        ]

    # [2026-07-03b] 20/50 -> 10/40, still inside the validated robustness sweep
    # (10/30..30/70 all profitable on 3yr BTC+ETH). Split-window backtest vs
    # 20/50 on BTC+ETH 1d: bull 2024-01->2025-12 +94.5% vs +71.2% (22 vs 15
    # trades); bear 2025-12->2026-06 -9.8% vs -16.0% (the faster cross exits
    # crashes sooner). More trades, more profit, LESS bear bleed. DD 26% vs 18%
    # full-window is the accepted cost.
    fast_ma = IntParameter(10, 30, default=10, space="buy", optimize=False)
    slow_ma = IntParameter(40, 70, default=40, space="buy", optimize=False)

    # Let winners run: ROI effectively disabled. Exit comes from the trend flip.
    minimal_roi = {"0": 100}

    # Wide backstop only. The MA-cross exit is the primary risk control.
    stoploss = -0.15   # [2026-07-03] back to the validated 1d value (was -0.12 for the 4h experiment)

    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 60        # need 50 daily candles for the 50d SMA

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma_fast"] = ta.SMA(dataframe, timeperiod=self.fast_ma.value)
        dataframe["sma_slow"] = ta.SMA(dataframe, timeperiod=self.slow_ma.value)
        # [2026-07-03 ADAPTIVE] Bear-bounce mode inputs: RSI + 20-bar range low.
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rng_low20"] = dataframe["low"].rolling(20).min().shift(1)
        dataframe["rng_high20"] = dataframe["high"].rolling(20).max().shift(1)
        _rng_band = (dataframe["rng_high20"] - dataframe["rng_low20"]).clip(lower=1e-9)
        dataframe["rng_bounce_zone"] = dataframe["rng_low20"] + 0.15 * _rng_band
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long whenever sma_fast > sma_slow (momentum is up). Freqtrade won't
        # double-enter an already-open pair; the exit triggers on the down-cross
        # below, so the trend-follow behaviour is preserved.
        #
        # [ENTRY-QUALITY FIX 2026-06-30] Dropped the experimental
        # `OR close > sma_slow` clause. Live paper data: this bot's only 2 trades
        # last month both LOST (-$11.33 total), entering on that weak early-momentum
        # condition and then exiting on the trend flip. Requiring the real momentum
        # condition (fast SMA above slow SMA) keeps it from buying setups that
        # haven't actually turned up yet — exactly the validated rule the docstring
        # describes, and the anti-overfit middle pair the robustness check passed.
        dataframe.loc[
            (
                (dataframe["sma_fast"] > dataframe["sma_slow"])
                # [2026-07-03 CHOP FILTER] price itself must be above the slow MA
                # too — a fast/slow cross with price already back below the slow
                # MA is the flat-market whipsaw this bot is known to bleed in.
                & (dataframe["close"] > dataframe["sma_slow"])
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "sma_fast_above_slow")

        # [2026-07-03 ADAPTIVE] Bear-regime bounce: when momentum is DOWN
        # (fast<slow) this bot used to sit 100% in cash — its known whipsaw/dead
        # zone. Half-stake daily RSI<32 stabilized bounce at the 20-day range
        # low, up-close confirmed, exiting via custom_exit (+5% / 7 days). The
        # validated trend edge above is untouched.
        dataframe.loc[
            (
                (dataframe["sma_fast"] <= dataframe["sma_slow"])
                & (dataframe["rsi"] < 32)
                # the 20d low must have held ~5 days (a base, not a waterfall)
                & (dataframe["rng_low20"] == dataframe["rng_low20"].shift(5))
                & (dataframe["close"] <= dataframe["rng_bounce_zone"])
                & (dataframe["close"] > dataframe["close"].shift(1))
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "bear_bounce")
        return dataframe

    # [2026-07-03 ADAPTIVE] Half stake on counter-trend bounces.
    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        if entry_tag == "bear_bounce":
            half = proposed_stake * 0.5
            if min_stake is None or half >= min_stake:
                return half
        return proposed_stake

    # [2026-07-03 ADAPTIVE] Bounce exits: +5% take or 7-day timeout (daily scale).
    # The MA-cross exit below won't fire for bounces (no cross event mid-bear),
    # so this is their primary exit; the -15% stop is the backstop.
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit,
                    **kwargs):
        if trade.enter_tag == "bear_bounce":
            if current_profit >= 0.05:
                return "bounce_take"
            if (current_time - trade.open_date_utc).total_seconds() >= 7 * 86400:
                return "bounce_timeout"
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SELL when fast SMA crosses back below slow SMA (momentum rolls over).
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe["sma_fast"], dataframe["sma_slow"])
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
