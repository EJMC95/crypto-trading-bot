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
#
# [2026-07-03 ADAPTIVE DUAL-MODE] BTC-daily 50/200 regime switch. Risk-on = range
# pullback buys; risk-off = half-stake RSI<30 exhaustion bounces with fast exits.
# The bot adapts its playbook to the tide instead of either churning against it
# (155 trades, 14% win rate, -$21 live) or switching off entirely.

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

    # [2026-07-03] 15m -> 1h: FEE VIABILITY. A 14-candle range on 15m majors is
    # typically ~0.3-0.8% — structurally below Kraken's ~0.52% round-trip fee, so
    # NO 15m variant could ever be net-green (live: 155 trades -$21 @14% win;
    # backtests: -19% to -25% every variant). A 14-HOUR range runs 1.5-3%+, so
    # the same logic clears fees with room. Still intraday cadence (holds hours).
    timeframe = "1h"
    informative_timeframe = "1h"      # short-term trend filter (unchanged from Aggro)
    # [2026-07-03] Regime timeframe 1d -> 4h. Same 50/200 EMA concept, but: (a) it
    # warms up in ~33 days instead of ~200, so the regime is defined from day one
    # on any exchange/backtest; (b) it flips in days not months, catching tradable
    # risk-on windows INSIDE a bear (like the current +8-12% 7d bounce) — that's
    # the adaptability this bot is for. 4h 50/200 EMA ≈ 8d/33d in wall time.
    regime_timeframe = "4h"

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
    # [2026-07-03] 1.5 -> 2.0. Live evidence since: 155 trades, 21W/134L (14%),
    # 121 killed by this ATR stop — the stop distance (~1.5*ATR15m ≈ 0.3-0.6%)
    # sat BELOW the first ROI target (1.2%), so trades died to ordinary noise
    # before any winner could mature. The 06-30 "keep it tight" call was made
    # when entries were knife-catches; entries are now regime-gated + up-tick
    # confirmed, so the stop's job is disasters, not noise.
    # [2026-07-03b LEARNED 2.0 -> 2.5] Full 157-trade live dissection: every ROI
    # exit won (13/13); 122 stop exits at 6% win = -$17.68 of the -$20.96 total;
    # the ONLY net-positive holds were 90-240min (50% win) while <30min holds
    # went 2%. Winners need room+time to reach the ladder. Backtest confirm on
    # 1h: win rate 30.4% -> 41.3%, better P&L, lower DD.
    atr_stop_mult = DecimalParameter(0.8, 3.0, default=2.5, decimals=1,
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
    # [2026-07-03] Ladder raised + slowed (keys are minutes: 3h / 6h / 12h) and
    # re-keyed for 1h candles. Winners breathe to 1.8% early, decay with age.
    # (A "let winners run uncapped via 1h breakouts" variant was also tested and
    # was decisively worse: -33% / 16% win — 1h breakouts churn; the 4h V7 keeps
    # that job. This ladder + range exits is the best variant of five tested.)
    minimal_roi = {
        "0": 0.018,
        "180": 0.012,
        "360": 0.008,
        "720": 0.005,
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
        # [CHURN-FIX 2026-06-25, re-scaled 2026-07-03 for 1h candles] Cooldown 4
        # candles (4h): one pair can't be re-bought into the same chop. Stoploss-
        # Guard 3 stops / 48h pauses 12h after a genuine cluster. MaxDrawdown
        # halts 24h if the book bleeds 15% inside 4 days.
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 4},
            {"method": "StoplossGuard", "lookback_period_candles": 48,
             "trade_limit": 3, "stop_duration_candles": 12, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 96, "trade_limit": 10,
             "stop_duration_candles": 24, "max_allowed_drawdown": 0.15},
        ]

    # [2026-07-01 FIX] Base-timeframe warmup only. Was 200 (for the removed 1d
    # regime), which starved the bot of signals. 110 x 1h is well within
    # Kraken's 720-candle OHLC window, so no starvation risk.
    startup_candle_count = 110

    # [2026-07-03 ADAPTIVE REGIME] BTC daily drives the market-wide risk switch
    # for the whole (BTC-correlated) basket. One always-present series, so it
    # avoids the per-pair daily-data starvation that forced removal of the
    # original 24-pair gate on 07-01. Derived from stake_currency so the same
    # strategy works on Kraken (BTC/USD) and Binance backtests (BTC/USDT).
    @property
    def regime_pair(self) -> str:
        return f"BTC/{self.config.get('stake_currency', 'USD')}"

    def informative_pairs(self):
        return [(self.regime_pair, self.regime_timeframe)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # [2026-07-01 FIX] Base-timeframe indicators ONLY. The old 1h/1d
        # informative merges (regime gate + 1h trend) required ~200 daily candles
        # per pair; on the broadened 24-pair basket that data isn't always present,
        # so populate_indicators raised and the bot produced NO signals at all
        # (heartbeat online, 0 trades). The 20-candle range entry never used those
        # columns, so they are removed. Keep ATR (for the custom stop) + the range.
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        # [2026-07-03 ADAPTIVE] RSI drives the risk-off exhaustion-bounce mode.
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # [2026-07-02 DIP-CLUSTER FIX] Own-pair 15m EMA50 trend gate. Live losses
        # arrived in clusters: market-wide dips hit all 24 pairs at once, the bot
        # bought several "separate" dips that were the same dip, and every one
        # stopped out together (11 ATR-stop losses, all in two such windows).
        # When the whole market slides, pairs sit BELOW their EMA50 — requiring
        # close > EMA50 blocks exactly those entries while still allowing normal
        # pullback-buys inside an intact uptrend.
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)

        # [2026-07-01 INTRADAY RETUNE] The 20-candle / bottom-15% range never fired
        # on 15m (5h window, too tight) — the bot took zero trades. Faster + wider
        # for an intraday scalper: 10-candle (2.5h) window, buy in the bottom third
        # of the range, sell in the top third (34% dead zone in the middle so a
        # fresh buy isn't instantly in the sell zone). shift(1) = no look-ahead.
        # [2026-07-01 FEE-BLEED FIX] The prior 10-candle / 0.33-zone range captured
        # only ~0.34*band between entry and exit — below the ~0.52% round-trip fee,
        # so the bot went 0/11 (all tiny fee losses). Three changes:
        #   1) Wider window (14 candles, ~3.5h) for a steadier, larger band.
        #   2) Buy/sell zones tightened to 0.22 -> capture ~0.56*band per round trip.
        #   3) A FEE GATE (rng_band_pct) so we only take trades where the captured
        #      move can realistically clear fees + leave profit.
        # shift(1) = no look-ahead.
        _N = 14
        dataframe["rng_low20"] = dataframe["low"].rolling(_N).min().shift(1)
        dataframe["rng_high20"] = dataframe["high"].rolling(_N).max().shift(1)
        _rng_band = (dataframe["rng_high20"] - dataframe["rng_low20"]).clip(lower=1e-9)
        # [2026-07-05] Buy zone 0.22 -> 0.37: enter higher up the pullback (bottom
        # 37% of the range, not just 22%) for materially more fills. Sell zone kept
        # at 0.22 so captured move = ~0.41*band (entry 0.37 -> exit 0.78); at the
        # 2.0% band floor that's ~0.82% captured vs ~0.52% fee = ~+0.3% net — still
        # fee-positive, but thinner, so win rate matters more (watch it).
        dataframe["rng_buy_zone"] = dataframe["rng_low20"] + 0.37 * _rng_band
        dataframe["rng_sell_zone"] = dataframe["rng_high20"] - 0.22 * _rng_band
        # band width as a fraction of price — used to skip low-vol chop where the
        # captured move (~0.56*band) would be eaten by the ~0.52% round-trip fee.
        dataframe["rng_band_pct"] = _rng_band / dataframe["close"].clip(lower=1e-9)
        # deeper entry band for the risk-off bounce mode (bottom 15% of the range)
        dataframe["rng_bounce_zone"] = dataframe["rng_low20"] + 0.15 * _rng_band

        # [2026-07-03 ADAPTIVE REGIME] BTC 4h 50/200 EMA as the market-wide
        # regime SWITCH (not a gate): 50>200 -> risk-on pullback buys; 50<200 ->
        # half-stake sweep-reclaim bounces. One always-present series, avoiding
        # the per-pair daily-data starvation that killed the original gate on
        # 07-01. FAIL-SAFE: missing/warming-up data -> 0 -> the CONSERVATIVE
        # half-stake bounce mode, never the aggressive one.
        btc = self.dp.get_pair_dataframe(pair=self.regime_pair, timeframe=self.regime_timeframe)
        regime_col = f"btc_regime_up_{self.regime_timeframe}"  # merge suffixes by tf
        if btc is not None and len(btc) > 0:
            btc = btc.copy()
            btc["btc_regime_up"] = (
                ta.EMA(btc, timeperiod=self.regime_ema_fast.value)
                > ta.EMA(btc, timeperiod=self.regime_ema_slow.value)
            ).astype(int)
            dataframe = merge_informative_pair(
                dataframe, btc[["date", "btc_regime_up"]], self.timeframe,
                self.regime_timeframe, ffill=True
            )
        # Timeframe-agnostic alias (a hardcoded suffix here once silently forced
        # permanent bounce-only mode when the regime tf changed — hence this).
        if regime_col in dataframe.columns:
            dataframe["btc_regime_up"] = dataframe[regime_col].fillna(0).astype(int)
        else:
            dataframe["btc_regime_up"] = 0

        return dataframe

    # Minimum band width (fraction of price) to bother trading — the captured move
    # (~0.56*band) must clear the ~0.52% Kraken round-trip fee with margin.
    # [2026-07-03 ADAPTIVE] Two thresholds: risk-on pullbacks may work slightly
    # thinner bands (0.015 -> captured ~0.84%, ~+0.3% net); risk-off bounces demand
    # wide, washed-out bands (0.022 -> captured ~1.2%, ~+0.7% net) because bear
    # rallies fade fast and entry quality is everything there.
    BAND_PCT_ON = 0.015
    # [2026-07-05] 0.022 -> 0.020 to loosen risk-off participation (bear_bounce +
    # bounce_pullback). At 2.0% the captured move (~0.56*band = ~1.12%) still clears
    # the ~0.52% round-trip fee with ~+0.6% net margin, so it stays above the
    # fee-bleed floor the 0/11 scratch run established — just admits more of the
    # current relief-rally pairs that were sitting a hair under the old 2.2% gate.
    BAND_PCT_OFF = 0.020

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # [2026-07-03 ADAPTIVE] Two regime modes instead of one on/off gate — the
        # bot always has a playbook, it just changes WHICH one with BTC's daily
        # trend. Shared quality gates: up-tick confirmation (no knife-catches,
        # the fix that live data demanded) + live volume.
        uptick = dataframe["close"] > dataframe["close"].shift(1)
        live_vol = dataframe["volume"] > 0

        # RISK-ON: buy pullbacks to the range low inside an intact own-pair
        # uptrend (close > EMA50 blocks market-wide slides).
        dataframe.loc[
            (
                (dataframe["btc_regime_up"] == 1)
                & (dataframe["close"] <= dataframe["rng_buy_zone"])
                & (dataframe["rng_band_pct"] >= self.BAND_PCT_ON)
                & (dataframe["close"] > dataframe["ema50"])
                & uptick & live_vol
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "range_on")

        # RISK-OFF (BTC 4h 50<200): SWEEP-AND-RECLAIM bounces only — the candle's
        # low must UNDERCUT the prior 14-candle low (stop-run flush) and the close
        # must RECLAIM it, with RSI<30 and a wide band. A failed breakdown is a
        # far stronger long trigger than "price is near the low" (which was just
        # knife-catching in a waterfall — the -19% backtest lesson). Half stake +
        # tight invalidation + fast exits via the custom_* methods below.
        dataframe.loc[
            (
                (dataframe["btc_regime_up"] == 0)
                & (dataframe["rsi"] < 30)
                # the flush level must have HELD ~6h first (no fresh lower-lows) —
                # separates a capitulation reversal from a rolling waterfall,
                # which was the 7%-win-rate failure of the unstabilized version.
                & (dataframe["rng_low20"] == dataframe["rng_low20"].shift(6))
                & (dataframe["low"] < dataframe["rng_low20"])      # swept the held low
                & (dataframe["close"] > dataframe["rng_low20"])    # ...and reclaimed it
                & (dataframe["rng_band_pct"] >= self.BAND_PCT_OFF)
                & uptick & live_vol
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "bear_bounce")

        # [2026-07-05 BOUNCE PARTICIPATION] Third mode. The two modes above leave a
        # gap: in risk-off the bot ONLY buys the exact capitulation bottom
        # (RSI<30 sweep-reclaim) and never participates in the multi-day RELIEF
        # RALLY that follows — so through a +8-12% bear bounce (exactly now) it
        # sat idle and booked $0. This adds pullback buys DURING a confirmed bounce
        # even while BTC's daily regime is down, but ONLY when the pair's own 1h
        # trend is objectively UP and RISING (close>EMA50 AND EMA50 climbing over
        # ~6h). That own-pair rising-trend requirement is the anti-knife-catch: the
        # -19% failure was buying dips with NO trend confirmation in a waterfall;
        # a rising EMA50 cannot be a waterfall. Half stake (counter-daily-trend) +
        # wide fee-band + fast exits (custom_exit/stop below) bound the downside.
        ema50_rising = dataframe["ema50"] > dataframe["ema50"].shift(6)
        dataframe.loc[
            (
                (dataframe["btc_regime_up"] == 0)
                & (dataframe["close"] <= dataframe["rng_buy_zone"])
                & (dataframe["close"] > dataframe["ema50"])
                & ema50_rising
                & (dataframe["rng_band_pct"] >= self.BAND_PCT_OFF)
                & uptick & live_vol
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "bounce_pullback")
        return dataframe

    # [2026-07-02 DIP-CLUSTER FIX, rebalanced 2026-07-03] Correlated-entry throttle.
    # The 24 pairs are one beta in a dip: on 2026-07-01/02 the bot opened 4 positions
    # inside a single 15m window and all four stopped out together. Cap NEW positions
    # per candle (2) so one market move can't load up the whole book at once, while
    # still allowing a steady flow of entries.
    MAX_ENTRIES_PER_CANDLE = 2
    _entry_throttle_ts = None
    _entry_throttle_n = 0

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        # Bucket entries by 1h candle; reject beyond the per-candle cap.
        bucket = current_time.replace(minute=0, second=0, microsecond=0)
        if self._entry_throttle_ts != bucket:
            self._entry_throttle_ts = bucket
            self._entry_throttle_n = 0
        if self._entry_throttle_n >= self.MAX_ENTRIES_PER_CANDLE:
            return False
        self._entry_throttle_n += 1
        return True

    # [2026-07-03 PULSE] Informed sizing v1: the market_pulse collector (news /
    # social / funding mood, bot_state key 'market-pulse') can HALVE new stakes
    # during a PANIC news cluster (>=3 hack/exploit/regulatory-shock headlines).
    # Entries are deliberately untouched — a signal only earns entry-gate power
    # once the brain (bot_learn) shows a persistent edge. Fail-safe: no DB /
    # import error / stale data -> neutral 1.0x. Cached 15 min per process.
    _pulse_cache = {"ts": None, "panic": False}

    def _pulse_panic(self, current_time: datetime) -> bool:
        c = type(self)._pulse_cache
        try:
            if c["ts"] is not None and (current_time - c["ts"]).total_seconds() < 900:
                return c["panic"]
            import bot_pnl_store as store          # available in the Railway image
            latest = (store.load_state("market-pulse") or {}).get("latest") or {}
            c["ts"], c["panic"] = current_time, bool(latest.get("panic"))
        except Exception:
            c["ts"], c["panic"] = current_time, False
        return c["panic"]

    # [2026-07-03 ADAPTIVE] Half stake on risk-off bounces: counter-trend scalps
    # only earn conviction sizing in the friendly regime.
    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        stake = proposed_stake
        if entry_tag in ("bear_bounce", "bounce_pullback"):
            stake *= 0.5                             # counter-daily-trend scalps size down
        if self._pulse_panic(current_time):
            stake *= 0.5
        if stake < proposed_stake and min_stake is not None and stake < min_stake:
            stake = min_stake                       # never breach exchange minimums
        return stake

    # [2026-07-03 ADAPTIVE] Faster exits = more closes, more re-armed slots.
    # Bounces bank +1.2% (sweep-reclaims either work quickly or not at all) or
    # time out after 12h; ANY trade times out after 24h so a stale position
    # can't squat in a slot for days. ROI ladder / ATR stop still apply on top.
    def custom_exit(self, pair: str, trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        age_min = (current_time - trade.open_date_utc).total_seconds() / 60.0
        if trade.enter_tag in ("bear_bounce", "bounce_pullback"):
            # bank quick relief-rally profit; bear bounces fade fast, don't overstay
            if current_profit >= 0.012:
                return "bounce_take"
            if age_min >= 720:
                return "bounce_timeout"
        if age_min >= 1440:
            return "max_hold_timeout"
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Sell into strength at the top of the range.
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
        # [2026-07-03 ADAPTIVE] Bounce stop 2.0x: tested 1.2x and it was shredded
        # by ordinary 15m noise (7% win rate, avg hold 32min) — reclaims need room
        # to wobble. Half stake keeps the $ risk in line.
        atr_multiplier = 2.0 if trade.enter_tag in ("bear_bounce", "bounce_pullback") else self.atr_stop_mult.value
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return None
        last_atr = dataframe["atr"].iat[-1]
        if last_atr is None or last_atr <= 0 or current_rate <= 0:
            return None
        atr_stop_distance = (atr_multiplier * last_atr) / current_rate
        return max(-atr_stop_distance, self.stoploss)
