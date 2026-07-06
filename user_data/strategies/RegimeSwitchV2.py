# RegimeSwitchV2.py
# ---------------------------------------------------------------------------
# THE FLEET'S DEDICATED DUAL-DIRECTION TREND ENGINE (Hyperliquid perps, 4h).
#
# WHY THIS EXISTS / WHAT'S NEW vs V1:
#   V1 was a 1h regime bot on BTC+ETH only, Donchian-entry, ROI-capped exits —
#   the best of its three tested variants but still net -20% (its own backtest).
#   Every strategy in THIS fleet that actually MADE money is a higher-timeframe
#   trend-follower (V7 MomoBreakout 4h Donchian PF1.79-1.94/+82-125%; V4 daily
#   50/200 majors PF7.26; V6 SwingDip PF1.73). None of them can SHORT. This bot
#   takes that proven 4h-Donchian-breakout edge and MIRRORS it for shorts on
#   perps, so the fleet finally has an engine that profits from a downtrend.
#
# DESIGN = combined fleet lessons + evidenced public practice (AQR "Century of
# Evidence on Trend-Following"; Moskowitz-Ooi-Pedersen time-series momentum;
# Hyperliquid docs). Every choice is grounded, not curve-fit:
#
#   DIRECTION (regime)   Per-pair DAILY trend: price vs EMA200 + EMA50 slope for
#                        direction; ADX(14) with hysteresis as a trade/no-trade
#                        gate. UP+TREND -> longs only; DOWN+TREND -> shorts only;
#                        CHOP (low ADX) -> stand down. [fleet: two-axis regime;
#                        public TIER-A: sign-of-trend direction + ADX chop gate]
#   ENTRY                4h Donchian breakout IN the regime direction (close >
#                        prior 20-bar high long / < prior 20-bar low short). This
#                        is V7's validated pattern (PF1.8), mirrored. [fleet +
#                        public: breakouts are the fee-robust family in trends]
#   EXIT (let winners    STRUCTURE break: opposite 10-bar Donchian. NOT a tight
#   run via structure)   trailing stop (V1's #1 bleed) and NOT an ROI cap (caps
#                        the fat-tail winners trend-following lives on). [fleet:
#                        Momo's winning exit; public: structure trails > ATR >
#                        fixed]. A WIDE ATR disaster stop is the only hard floor.
#   SIZING               Inverse-volatility (position proportional to 1/ATR) so
#                        every position is ~equal risk. [fleet: +56.8->+75.9%;
#                        public TIER-A: vol-targeting is the single highest-ROI
#                        technique]. Half stake on a panic news cluster.
#   RISK RAILS           Low leverage (1x); global concurrent cap via
#                        max_open_trades (correlation-aware: majors are one beta);
#                        StoplossGuard + MaxDrawdown halts; NO averaging down.
#   COST REALISM         4h holds clear Hyperliquid taker (~0.045%/side) with room
#                        (V1's 1h churned). Funding accrues hourly and is netted by
#                        freqtrade; a funding-bias overlay is a documented v2.1 add
#                        (needs a live funding feed the strategy layer lacks today).
#
# HONEST LIMITATIONS — READ BEFORE TRUSTING IT:
#   1. UNVALIDATED. No Hyperliquid/Kraken OHLCV is available to backtest, so this
#      is robust-by-CONSTRUCTION (every proven-good pattern in, every proven-bad
#      one out) but NOT yet walk-forward proven. It ships DRY-RUN and must earn a
#      green live record (the brain watches) before anyone considers real money.
#   2. Shorting a downtrend carries short-squeeze risk the long-only winners never
#      had; the wide ATR stop + low leverage + global cap bound it, not eliminate.
#   3. It is still trend-following: expect ~40% win rate, few big winners, loser
#      strings in chop. That is the correct signature, not a malfunction.
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


class RegimeSwitchV2(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = "4h"                 # fee-viable trend cadence (V1's 1h churned)
    can_short = True                 # the whole point — needs a futures config
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Let winners run via the STRUCTURE exit + ATR disaster stop, NOT an ROI cap
    # (a cap truncates the fat-tail winners trend-following depends on — fleet &
    # public agree). ROI set effectively off; the -12% is a hard backstop only.
    minimal_roi = {"0": 10.0}
    stoploss = -0.12
    use_custom_stoploss = True
    trailing_stop = False            # trailing was V1's documented #1 cause of bleed

    startup_candle_count = 220       # EMA200 on the daily informative

    # --- Donchian windows -----------------------------------------------------
    # [2026-07-05 MORE FREQUENT] 20/10 -> 15/8. MomoBreakout validated robust
    # across 20/10..42/21; 15/8 sits just faster than that band — a 15-bar (2.5d)
    # breakout fires more often and the 8-bar structure exit recycles capital
    # sooner (more re-entries), while staying on the fee-viable 4h core (NOT down
    # to 1h, which churned V1 to -20%). Frequency lever pulled deliberately.
    entry_lookback = IntParameter(10, 30, default=15, space="buy", optimize=False)
    exit_lookback = IntParameter(5, 15, default=8, space="sell", optimize=False)

    # --- Regime thresholds (few knobs, round numbers = anti-overfit) --------
    # [2026-07-05 MORE FREQUENT] Trend gate 22->20, chop 16->14: admit slightly
    # less-strong trends so the bot participates in more windows. ADX stays a real
    # trade/no-trade gate (chop is still skipped — that's what stops fee bleed).
    adx_trend = IntParameter(12, 30, default=17, space="buy", optimize=False)  # >= -> trending
    adx_chop = IntParameter(8, 20, default=11, space="buy", optimize=False)   # <= -> chop, stand down
    regime_ema_fast = IntParameter(30, 80, default=50, space="buy", optimize=False)
    regime_ema_slow = IntParameter(150, 250, default=200, space="buy", optimize=False)

    # --- Disaster stop: WIDE (gap/liquidation floor), not a noise stop ------
    atr_stop_mult = DecimalParameter(2.0, 4.0, default=3.0, decimals=1,
                                     space="sell", optimize=False)

    # --- Inverse-vol sizing target: scale each position toward equal risk ---
    # Position stake *= TARGET_ATR_PCT / pair_atr_pct, clamped so a single
    # calm/wild pair can't dominate or vanish. 0.02 = 2% ATR/price reference.
    TARGET_ATR_PCT = 0.02
    SIZE_MIN_MULT = 0.4
    SIZE_MAX_MULT = 1.5

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "StoplossGuard", "lookback_period_candles": 24,
             "trade_limit": 3, "stop_duration_candles": 8, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 120, "trade_limit": 8,
             "stop_duration_candles": 12, "max_allowed_drawdown": 0.15},
        ]

    # --- Per-pair DAILY regime (each major reads its OWN trend) --------------
    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.regime_ema_fast.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.regime_ema_slow.value)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        ema_fast_slope = dataframe["ema_fast"] - dataframe["ema_fast"].shift(3)
        up = (dataframe["close"] > dataframe["ema_slow"]) & (ema_fast_slope > 0)
        down = (dataframe["close"] < dataframe["ema_slow"]) & (ema_fast_slope < 0)
        dataframe["regime_dir"] = 0
        dataframe.loc[up, "regime_dir"] = 1
        dataframe.loc[down, "regime_dir"] = -1

        # ADX hysteresis: 1 = trending, 0 = chop; hold previous inside the band so
        # it doesn't flip-flop in the 16-22 zone (fleet + public both flag this).
        is_trend = dataframe["adx"] >= self.adx_trend.value
        is_chop = dataframe["adx"] <= self.adx_chop.value
        char, prev = [], 0
        for t, c in zip(is_trend.tolist(), is_chop.tolist()):
            if t:
                prev = 1
            elif c:
                prev = 0
            char.append(prev)
        dataframe["regime_trend"] = char
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 4h Donchian channels (prior-bar, no look-ahead via shift in entries).
        e = int(self.entry_lookback.value)
        x = int(self.exit_lookback.value)
        dataframe["dc_high_entry"] = dataframe["high"].rolling(e).max()
        dataframe["dc_low_entry"] = dataframe["low"].rolling(e).min()
        dataframe["dc_high_exit"] = dataframe["high"].rolling(x).max()
        dataframe["dc_low_exit"] = dataframe["low"].rolling(x).min()
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = (dataframe["atr"] / dataframe["close"].clip(lower=1e-9))
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        up_trend = (dataframe["regime_dir_1d"] == 1) & (dataframe["regime_trend_1d"] == 1)
        down_trend = (dataframe["regime_dir_1d"] == -1) & (dataframe["regime_trend_1d"] == 1)

        # LONG: up-regime + breakout above the prior 20-bar high (V7 pattern).
        dataframe.loc[
            up_trend
            & (dataframe["close"] > dataframe["dc_high_entry"].shift(1))
            & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "trend_break_long")

        # SHORT: down-regime + breakdown below the prior 20-bar low (the mirror —
        # the capability no other bot in the fleet has).
        dataframe.loc[
            down_trend
            & (dataframe["close"] < dataframe["dc_low_entry"].shift(1))
            & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "trend_break_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # STRUCTURE exit: close the long when price breaks the opposite 10-bar
        # channel (trend structure broke). Lets winners run; no ROI cap.
        dataframe.loc[
            dataframe["close"] < dataframe["dc_low_exit"].shift(1),
            "exit_long",
        ] = 1
        dataframe.loc[
            dataframe["close"] > dataframe["dc_high_exit"].shift(1),
            "exit_short",
        ] = 1
        return dataframe

    # --- Inverse-volatility sizing (equal-risk) + panic half-stake ----------
    _pulse_cache = {"ts": None, "panic": False}

    def _pulse_panic(self, current_time: datetime) -> bool:
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

    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        stake = proposed_stake
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is not None and len(df) > 0:
            atr_pct = df["atr_pct"].iat[-1]
            if atr_pct and atr_pct > 0:
                mult = self.TARGET_ATR_PCT / float(atr_pct)
                mult = max(self.SIZE_MIN_MULT, min(self.SIZE_MAX_MULT, mult))
                stake = proposed_stake * mult
        if self._pulse_panic(current_time):
            stake *= 0.5
        if min_stake is not None and stake < min_stake:
            stake = min_stake
        return min(stake, max_stake)

    # --- Wide ATR disaster stop (fixed-from-entry floor, NOT a trailing/noise
    #     stop). Structure exit is the primary exit; this only catches gaps.
    def custom_stoploss(self, pair: str, trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return None
        atr = df["atr"].iat[-1]
        if atr is None or atr <= 0 or trade.open_rate <= 0:
            return None
        stop_frac = (self.atr_stop_mult.value * atr) / trade.open_rate
        return -abs(float(stop_frac))

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: Optional[str], side: str, **kwargs) -> float:
        return 1.0                   # low leverage: 2x doubled DD, 3x+ liquidated fast
