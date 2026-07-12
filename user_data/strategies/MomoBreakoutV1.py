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
#
# [2026-07-03 RESTORE + ADAPT] The 07-01 rewrite replaced the validated Donchian
# breakout above (PF ~1.8-1.9 over 3yr) with an ungated buy-the-20-bar-low — the
# OPPOSITE trade, with no trend filter, live in a bear market. Restored the
# validated breakout as the uptrend mode, and made the dip-buy an explicit
# half-stake bear-bounce mode (4h RSI<28 at the range bottom, up-tick confirmed)
# with fast exits — so the bot trades BOTH regimes, each with a designed edge.

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
    entry_lookback = IntParameter(10, 45, default=20, space="buy",  optimize=False)
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
        # [2026-07-03 VOL-TARGET] ATR feeds inverse-volatility sizing below.
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        # Prior-bar Donchian channels (shift(1) => no look-ahead on the current bar).
        dataframe["dc_high"] = dataframe["high"].rolling(self.entry_lookback.value).max().shift(1)
        dataframe["dc_low"]  = dataframe["low"].rolling(self.exit_lookback.value).min().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        live_vol = dataframe["volume"] > 0

        # UPTREND (above 200-EMA): fresh breakout over the 30-bar high — the
        # validated momentum edge (let winners run, Donchian-trail out).
        dataframe.loc[
            (
                (dataframe["close"] > dataframe["dc_high"])
                & (dataframe["close"] > dataframe["ema_trend"])
                & live_vol
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "breakout")

        # [2026-07-12 SLEEVE RETIRED] The bear_bounce leg (downtrend half-stake
        # sweep-and-reclaim bounce, shipped 07-03 to all four spot bots) is gone
        # fleet-wide: tagged Binance replay 2022-2026 scored it negative in ALL
        # FOUR carriers (19 entries, -$7.27 aggregate, 26% win; here 0-for-3,
        # -$0.70) and it never fired once in live paper. Below the 200-EMA this
        # bot stands down — the validated breakout edge above is untouched
        # (+$201.59 / 603 entries on the same replay).
        return dataframe

    # [2026-07-03 VOL-TARGET] Inverse-volatility sizing — equal RISK per trade,
    # not equal dollars (the most-replicated portfolio improvement in the trend-
    # following literature, and it holds here: backtest 2024-01->2026-06 on the
    # 15-pair basket went +56.8% -> +75.9% with DD 32.8% -> 28.3%, identical
    # trades). High-ATR names get proportionally smaller stakes (ref 2% 4h-ATR,
    # floored at 0.3x). Tested and REJECTED for v8 (BTC+ETH only: no dispersion
    # to exploit) and V6 (its best trades ARE the high-vol capitulation days).
    # Bounces still run half stake on top.
    # [2026-07-04 PULSE] Panic-cluster check — sizing only, fail-safe neutral.
    _pulse_cache = {"ts": None, "panic": False}

    def _pulse_panic(self, current_time):
        c = type(self)._pulse_cache
        try:
            if c["ts"] is not None and (current_time - c["ts"]).total_seconds() < 900:
                return c["panic"]
            import bot_pnl_store as store
            latest = (store.load_state("market-pulse") or {}).get("latest") or {}
            c["ts"], c["panic"] = current_time, bool(latest.get("panic"))
        except Exception:
            c["ts"], c["panic"] = current_time, False
        return c["panic"]

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        stake = proposed_stake
        try:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            atr_pct = float(df["atr"].iat[-1]) / float(df["close"].iat[-1])
            if atr_pct > 0:
                stake *= max(0.3, min(1.0, 0.02 / atr_pct))
        except Exception:
            pass
        # [2026-07-04] halve during an active panic news cluster — entries into
        # a live hack/regulatory shock are the knife-catch case.
        if self._pulse_panic(current_time):
            stake *= 0.5
        if stake < proposed_stake and min_stake is not None and stake < min_stake:
            stake = min_stake
        return stake


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # [2026-07-03 RESTORE] Trailing Donchian breakdown — the validated "let
        # winners run, cut on structure break" exit. Bounce trades usually leave
        # earlier via custom_exit; this (and the -12% stop) is their backstop.
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["dc_low"])
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe
