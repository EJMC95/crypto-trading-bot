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
#
# [2026-07-14 BTC-TIDE GATE] Live bleed diagnosis: both carriers (crypto-
# breakout-4h and freqtrade-dad) went 2W/9L (~-$8 each) in the 3-13 Jul window
# — 11 different pairs broke above their OWN 200-EMA and died, a market-wide
# fakeout wave in a fear tape (F&G 22, 8/10 majors in a short regime). The
# per-pair EMA filter can't see that; a market-tide filter can. Backtest,
# Kraken 4h, all 30 whitelist pairs, 2026-04-20 -> 07-14, 0.26%/side fees
# (scripts/backtest_momo_tide_gate.py):
#     A as-deployed:            121 trades, 33% win, sum -94.0%, PF 0.79
#     B + BTC>4h-EMA200 gate:    74 trades, 37% win, sum +79.1%, PF 1.43
#     C breadth>=50% gate:       78 trades, 35% win, sum  -9.3%, PF 0.96
#     D half-size off-tide:     121 trades, 33% win, sum -19.1%, PF 0.94
# The baseline faithfully reproduces the live July bleed (27 entries, 22% win)
# and the hard BTC-tide gate flips it positive while cutting -12% catastrophe
# stops 6 -> 1. Variant B shipped: breakout entries additionally require BTC
# above its 4h EMA200. Same idea as the pair-level EMA200 rule, one level up —
# and the same signal the regime oracle (L1) publishes; computed in-strategy
# from the BTC informative pair so `freqtrade backtesting` reproduces it
# deterministically. Honest caveat: one 3-month window, not 3 years — but it
# is the exact regime the bot is bleeding in, and the untouched core edge
# (+$201.59/603 entries on the 2022-26 replay) only ever fired in up-tides.

from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter, merge_informative_pair


class MomoBreakoutV1(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = False

    # [2026-07-14] Market-tide gate source (see header). BTC/USD is in every
    # carrier's whitelist, so the informative data is always warm.
    tide_pair = "BTC/USD"

    def informative_pairs(self):
        return [(self.tide_pair, self.timeframe)]

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

        # [2026-07-14 BTC-TIDE GATE] BTC above its own 4h EMA200 = tide up.
        # FAIL-SAFE CLOSED (0): a breakout with no tide reading is treated as
        # off-tide — backtest says ungated breakouts in this tape are net
        # negative, and BTC/USD informative data is always present in practice.
        btc = self.dp.get_pair_dataframe(pair=self.tide_pair, timeframe=self.timeframe)
        tide_col = f"btc_tide_up_{self.timeframe}"
        if btc is not None and len(btc) > 0:
            btc = btc.copy()
            btc["btc_tide_up"] = (
                btc["close"] > ta.EMA(btc, timeperiod=self.trend_ema.value)
            ).astype(int)
            dataframe = merge_informative_pair(
                dataframe, btc[["date", "btc_tide_up"]], self.timeframe,
                self.timeframe, ffill=True
            )
        if tide_col in dataframe.columns:
            dataframe["btc_tide_up"] = dataframe[tide_col].fillna(0).astype(int)
        else:
            dataframe["btc_tide_up"] = 0
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        live_vol = dataframe["volume"] > 0

        # UPTREND (above 200-EMA): fresh breakout over the 30-bar high — the
        # validated momentum edge (let winners run, Donchian-trail out).
        # [2026-07-14] Plus the market tide: BTC must also be above ITS 4h
        # EMA200 (backtest evidence in the header — PF 0.79 -> 1.43).
        dataframe.loc[
            (
                (dataframe["close"] > dataframe["dc_high"])
                & (dataframe["close"] > dataframe["ema_trend"])
                & (dataframe["btc_tide_up"] == 1)
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
        # [2026-07-14 L4] The brain's reduce-only per-tag multiplier: a tag the
        # ledger has repeatedly scored negative at sample size trades smaller
        # until it earns full stake back. Neutral 1.0 on any doubt (fleet_bus).
        try:
            import fleet_bus
            stake *= fleet_bus.stake_multiplier(
                self.config.get("bot_name"), entry_tag, current_time)
        except Exception:
            pass
        if stake < proposed_stake and min_stake is not None and stake < min_stake:
            stake = min_stake
        return stake

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs):
        # [2026-07-14 L2] Fleet-risk long-budget veto — the 26-position-pileup
        # guard. Enforcement wiring per the 07-07 design's scheduled Jul-14
        # review; fail-safe OPEN (stale/missing state never blocks trading).
        try:
            import fleet_bus
            if fleet_bus.long_entries_blocked(current_time):
                return False
        except Exception:
            pass
        return True


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
