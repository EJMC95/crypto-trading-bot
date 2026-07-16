#!/usr/bin/env python3
"""
lighter_family_bot.py — 👨‍👩‍👧‍👦 the four FAMILY bots as Lighter SHADOW books.

WHAT / WHY (2026-07-13)
  Eamon asked for the family bots to run as shadow bots on Lighter — not a
  mirror of the Kraken paper rows, the strategies themselves: signals computed
  from LIGHTER's own candles, fills modelled by crossing the LIVE Lighter book
  (ShadowBroker), funding drag accrued hourly, one -lshadow row per bot. The
  Kraken paper originals keep running untouched — they are the control arm the
  validation doctrine compares against (same logic, spot+fees vs perp+funding).

  Ports match what the carriers ACTUALLY run (config-resolved; mum/dad reflect
  the 13-Jul reverts to their validated variants). [2026-07-13 FLEET-WIDE] the
  original spot bots joined as three more books — the user asked for ALL bots
  on Lighter, and they run these same strategies:
    👩 Mum        freqtrade-mum        TrendMomoV1      1d   stop -15%  4 slots
    👨 Dad        freqtrade-dad        MomoBreakoutV1   4h   stop -12%  4 slots
    🙏 Avo Maria  freqtrade-avo-maria  SwingDipV1       4h   stop -10%  4 slots
    🔮 Georgia    freqtrade-georgia    DayTraderV5Gated 15m  ATR≤5%     5 slots
    ⚡ RangeRaider crypto-intraday-15m  DayTraderV5Gated 1h   ATR≤12%    5 slots
    🩸 Dip Buyer  crypto-swing-daily   SwingDipV1       1d   stop -10%  8 slots
    🚀 Breakout   crypto-breakout-4h   MomoBreakoutV1   4h   stop -12%  6 slots
  (crypto-trend-daily's Lighter books live in the tide-rider service; the
  perps/scanner bots have their own Lighter services or closed concepts.)
  Stake $50/trade (FAMILY_STAKE_USD), $1,000 start per book, long-only 1x —
  a long perp PAYS funding; that drag is the point of the experiment.

  UNVALIDATED on this venue. Shadow evidence first, like every bot before it
  (Tide Rider -> live only after the perp-drag backtest; Snap Back/Counterweight
  still shadow). VENUE=lighter_live REFUSES to start. Universe = the family
  whitelist minus coins Lighter doesn't list (ATOM, ALGO — logged, skipped).

KNOWN PORT DIVERGENCES (honest list, for the go/no-go review):
  * Fills cross the spread (taker VWAP for the $50 clip) — the freqtrade twins
    quote top-of-book same-side (maker-ish) and pay Kraken fees. Zero fee here.
  * Stops/ROI check every loop (~90s) against the live mid, not tick-by-tick;
    gap-throughs fill at the live book, not at the stop price (pessimistic).
  * Freqtrade protections are re-implemented (cooldown / stoploss-guard /
    max-drawdown as documented per strategy) — same shape, not the same code.
  * market-pulse panic halving and Georgia's 2-entries-per-hour throttle ARE
    ported; Kraken min-order-size quirks are not (Lighter mins are tiny).

Usage:
    VENUE=lighter_shadow python lighter_family_bot.py            # daemon
    VENUE=lighter_shadow python lighter_family_bot.py --once     # smoke
    python lighter_family_bot.py --selftest                      # indicator math
"""
import argparse
import logging
import math
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store

START_EQUITY = 1000.0
STAKE_USD = float(os.environ.get("FAMILY_STAKE_USD", "50"))
# [2026-07-16 ZOMBIE GUARD] close a held coin the manage loop can't see or
# price — dropped from the book's coin list (env change / unsupported at
# boot) or continuously unpriceable — after this many hours, at the last
# known mark. Without it such positions froze forever (no stop, no ROI,
# no exit) while still counting toward the slot cap.
DELIST_GIVEUP_H = float(os.environ.get("FAMILY_DELIST_GIVEUP_H", "6"))
LOOP_SECONDS = int(os.environ.get("FAMILY_LOOP_SECONDS", "90"))
DAILY_LOSS_LIMIT = float(os.environ.get("FAMILY_DAILY_LOSS", "0.10"))
COINS = os.environ.get(
    "FAMILY_COINS",
    "BTC,ETH,SOL,XRP,ADA,DOT,AVAX,LINK,LTC,ATOM,NEAR,TRX,DOGE,ALGO,AAVE"
).split(",")
CANDLE_LAG_S = 20          # wait this long after a boundary before refetching


# ---------------------------------------------------------------------------
# [2026-07-15 LEARNING-LOOP WIRING] Ledger tag contract + brain stake input.
# bot_pnl_store.fetch_paper_trades splits a close's `reason` into
# (enter_tag, exit_reason) at the FIRST underscore (the Ticket Taker's
# '<side>-<lens>_<exit>' pattern), so the strategy tag must ride
# underscore-free: 'bounce_pullback' -> 'long-bounce-pullback_<exit>'.
# Before this every close published as 'long_<exit>' and the brain bucketed
# all seven books under enter_tag 'long' — per-tag learning (and therefore
# the L4 stake multipliers) was structurally impossible for the running
# fleet. See EVIDENCE_AND_LEARNING_REVIEW_2026-07-15.md items 1-2.

def ledger_tag(tag):
    """The enter_tag the brain sees for this book's closes (and the key the
    stake-multiplier lookup must use — same function, so they can't drift)."""
    return "long-" + str(tag).replace("_", "-") if tag else "long"


def ledger_reason(tag, exit_reason):
    """Compose record_close's published reason: '<ledger_tag>_<exit>'.
    No tag -> legacy 'long_<exit>' (enter_tag 'long'), exactly as before."""
    return f"{ledger_tag(tag)}_{exit_reason}"


def brain_stake_mult(bot_id, tag):
    """The brain's reduce-only per-(bot, tag) stake multiplier for an entry,
    looked up under EXACTLY the identity this book's ledger rows carry
    (bot_id row name + ledger_tag). fleet_bus owns the fail-safe contract
    (fresh payload only, clamp [0.5, 1.0], neutral 1.0 on any doubt); the
    guard here only covers an image built without fleet_bus.py."""
    try:
        import fleet_bus
        return float(fleet_bus.stake_multiplier(bot_id, ledger_tag(tag)))
    except Exception:  # noqa: BLE001
        return 1.0


LOG_FILE = os.environ.get("FAMILY_LOG_FILE", "lighter_family_bot.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("family-lighter")


# ---------------------------------------------------------------------------
# Indicators — pure python, talib-compatible (Wilder smoothing, SMA-seeded
# EMA) so signals match the freqtrade twins as closely as data allows.
# Each returns a full series aligned to the input (None while warming up).

def sma_series(vals, p):
    out = [None] * len(vals)
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= p:
            s -= vals[i - p]
        if i >= p - 1:
            out[i] = s / p
    return out


def ema_series(vals, p):
    out = [None] * len(vals)
    if len(vals) < p:
        return out
    k = 2.0 / (p + 1.0)
    e = sum(vals[:p]) / p          # talib seeds with the SMA of the first p
    out[p - 1] = e
    for i in range(p, len(vals)):
        e = vals[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi_series(closes, p=14):
    out = [None] * len(closes)
    if len(closes) < p + 1:
        return out
    gains = losses = 0.0
    for i in range(1, p + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / p, losses / p
    out[p] = 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)
    for i in range(p + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (p - 1) + max(d, 0.0)) / p       # Wilder
        al = (al * (p - 1) + max(-d, 0.0)) / p
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)
    return out


def _tr(h, l, c_prev):
    return max(h - l, abs(h - c_prev), abs(l - c_prev))


def atr_series(highs, lows, closes, p=14):
    n = len(closes)
    out = [None] * n
    if n < p + 1:
        return out
    trs = [_tr(highs[i], lows[i], closes[i - 1]) for i in range(1, n)]
    a = sum(trs[:p]) / p
    out[p] = a
    for i in range(p + 1, n):
        a = (a * (p - 1) + trs[i - 1]) / p          # Wilder
        out[i] = a
    return out


def adx_series(highs, lows, closes, p=14):
    """talib-style Wilder ADX. None while warming up (needs ~2p bars)."""
    n = len(closes)
    out = [None] * n
    if n < 2 * p + 1:
        return out
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(_tr(highs[i], lows[i], closes[i - 1]))
    # Wilder-smoothed sums (seed = plain sum of first p)
    sp, sm, st = sum(plus_dm[:p]), sum(minus_dm[:p]), sum(trs[:p])
    dxs = []
    for i in range(p, len(trs)):
        if i > p:
            sp = sp - sp / p + plus_dm[i - 1]
            sm = sm - sm / p + minus_dm[i - 1]
            st = st - st / p + trs[i - 1]
        pdi = 100.0 * sp / st if st else 0.0
        mdi = 100.0 * sm / st if st else 0.0
        dxs.append(100.0 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0.0)
        if len(dxs) >= p:
            if len(dxs) == p:
                adx = sum(dxs) / p
            else:
                adx = (adx * (p - 1) + dxs[-1]) / p
            out[i + 1] = adx
    return out


def stdev(vals, ddof=1):
    n = len(vals)
    if n <= ddof:
        return 0.0
    m = sum(vals) / n
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (n - ddof))


def roll_max(vals, p, i):
    """max of vals over the p bars ENDING at i (inclusive), or None."""
    if i + 1 < p:
        return None
    return max(vals[i - p + 1:i + 1])


def roll_min(vals, p, i):
    if i + 1 < p:
        return None
    return min(vals[i - p + 1:i + 1])


# ---------------------------------------------------------------------------
# Candle plumbing

def parse_candles(raw, interval_ms, now_ms):
    """Venue candles -> dict of float lists, forming bar dropped."""
    t, o, h, l, c, v = [], [], [], [], [], []
    for row in raw or []:
        if not isinstance(row, dict):
            continue
        try:
            ts = float(row.get("t") or row.get("timestamp"))
            if ts < 1e12:               # seconds -> ms
                ts *= 1000.0
            t.append(int(ts))
            o.append(float(row.get("o", row.get("open"))))
            h.append(float(row.get("h", row.get("high"))))
            l.append(float(row.get("l", row.get("low"))))
            c.append(float(row.get("c", row.get("close"))))
            v.append(float(row.get("v", row.get("volume", 0)) or 0))
        except (TypeError, ValueError):
            continue
    # sort by time, drop the still-forming bar (t = open time)
    order = sorted(range(len(t)), key=lambda i: t[i])
    t = [t[i] for i in order]
    o = [o[i] for i in order]
    h = [h[i] for i in order]
    l = [l[i] for i in order]
    c = [c[i] for i in order]
    v = [v[i] for i in order]
    while t and t[-1] + interval_ms > now_ms - 5000:
        t.pop(), o.pop(), h.pop(), l.pop(), c.pop(), v.pop()
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


class CandleCache:
    """One governed fetch per (coin, timeframe) per closed candle, shared by
    every book that needs it (dad + avo + breakout + georgia's regime all ride
    one 4h fetch), so the REST budget stays far inside the governor."""

    SPAN_BARS = {"15m": 300, "1h": 380, "4h": 280, "1d": 240}

    def __init__(self, venue):
        self.venue = venue
        self.data = {}       # (coin, tf) -> {"bars":…, "next_due": ms}

    def get(self, coin, tf):
        key = (coin, tf)
        now_ms = int(time.time() * 1000)
        hit = self.data.get(key)
        if hit and now_ms < hit["next_due"]:
            return hit["bars"]
        ims = _interval_ms(tf)
        span = self.SPAN_BARS.get(tf, 300) * ims
        try:
            raw = self.venue.candles(coin, tf, now_ms - span, now_ms)
        except Exception as e:  # noqa: BLE001 — budget/venue hiccup: stale ok
            if hit:
                return hit["bars"]
            log.warning("%s %s candles unavailable: %s", coin, tf, e)
            return None
        bars = parse_candles(raw, ims, now_ms)
        if not bars["t"]:
            return hit["bars"] if hit else None
        nxt = bars["t"][-1] + 2 * ims + CANDLE_LAG_S * 1000
        self.data[key] = {"bars": bars, "next_due": nxt}
        return bars


def _interval_ms(tf):
    unit = tf[-1]
    return int(tf[:-1]) * {"m": 60, "h": 3600, "d": 86400}[unit] * 1000


# ---------------------------------------------------------------------------
# Market-pulse panic (news shock) — sizing only, fail-safe neutral, 15-min
# cache. Same contract as the freqtrade strategies' _pulse_panic.
_pulse = {"ts": 0.0, "panic": False}


def pulse_panic():
    if time.time() - _pulse["ts"] < 900:
        return _pulse["panic"]
    try:
        latest = (store.load_state("market-pulse") or {}).get("latest") or {}
        _pulse.update(ts=time.time(), panic=bool(latest.get("panic")))
    except Exception:  # noqa: BLE001
        _pulse.update(ts=time.time(), panic=False)
    return _pulse["panic"]


# ---------------------------------------------------------------------------
# Strategy ports. Each carrier instance exposes:
#   bot, tf, stoploss, max_open, coins (config-resolved per carrier), roi,
#   protections, signals(bars, extra) -> {"enter": tag|None, "exit": bool, ...}
# computed on the LAST CLOSED bar, exactly the columns the freqtrade twin uses.
# [2026-07-13 FLEET-WIDE] Parameterized so ONE strategy class serves every
# carrier of that strategy (family + original spot bots) — the user asked for
# ALL bots to run on Lighter, and the spot bots run these same four strategies
# at their own timeframes/stops (config-resolved, verified 13 Jul).

# The original spot bots' shared 29-pair whitelist (config_v5/v6/v7). Unlisted
# coins are skipped per book at boot (logged + published in extra).
WIDE_COINS = ("BTC,ETH,SOL,XRP,ADA,DOGE,AVAX,LINK,DOT,LTC,BCH,ATOM,XLM,TRX,"
              "UNI,ETC,FIL,AAVE,ALGO,NEAR,APT,SUI,INJ,OP,TIA,ARB,WIF,BONK,"
              "PEPE").split(",")


class Carrier:
    coins = None                        # None -> the family COINS list

    def __init__(self, bot, tf, stoploss, max_open, style, coins=None):
        self.bot = bot
        self.tf = tf
        self.stoploss = stoploss
        self.max_open = max_open
        self.style = style
        if coins is not None:
            self.coins = coins


class TrendMomo(Carrier):
    """TrendMomoV1 — SMA 10/40 trend follower (validated on 1d)."""
    roi = {}                            # {"0": 100} = disabled
    protections = {"cooldown_candles": 1,
                   "maxdd": {"lookback": 40, "trades": 4, "dd": 0.25, "stop": 5}}
    min_bars = 45

    def signals(self, bars, extra):
        c, v = bars["c"], bars["v"]
        if len(c) < self.min_bars:
            return None
        fast = sma_series(c, 10)        # IntParameter defaults 10/40
        slow = sma_series(c, 40)
        i = len(c) - 1
        if fast[i] is None or slow[i] is None or fast[i - 1] is None:
            return None
        enter = (fast[i] > slow[i] and c[i] > slow[i] and v[i] > 0)
        exit_ = (fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]
                 and v[i] > 0)          # qtpylib.crossed_below
        return {"enter": "sma_fast_above_slow" if enter else None,
                "exit": exit_, "exit_reason": "death_cross"}

    def stake_mult(self, tag, bars):
        return 1.0


class MomoBreakout(Carrier):
    """MomoBreakoutV1 — Donchian breakout above the 200-EMA (validated on 4h)."""
    roi = {}
    protections = {"cooldown_candles": 1,
                   "slguard": {"lookback": 42, "trades": 3, "stop": 12},
                   "maxdd": {"lookback": 90, "trades": 8, "dd": 0.25, "stop": 18}}
    min_bars = 230

    def signals(self, bars, extra):
        c, h, l, v = bars["c"], bars["h"], bars["l"], bars["v"]
        if len(c) < self.min_bars:
            return None
        ema_t = ema_series(c, 200)
        i = len(c) - 1
        dc_high = roll_max(h, 20, i - 1)     # .rolling(20).max().shift(1)
        dc_low = roll_min(l, 15, i - 1)
        if ema_t[i] is None or dc_high is None or dc_low is None:
            return None
        enter = (c[i] > dc_high and c[i] > ema_t[i] and v[i] > 0)
        exit_ = (c[i] < dc_low and v[i] > 0)
        atr = atr_series(h, l, c, 14)
        return {"enter": "breakout" if enter else None,
                "exit": exit_, "exit_reason": "donchian_breakdown",
                "atr_pct": (atr[i] / c[i]) if (atr[i] and c[i]) else None}

    def stake_mult(self, tag, bars):
        # inverse-volatility sizing (custom_stake_amount): ref 2% ATR, floor 0.3x
        m = 1.0
        sig = self.signals(bars, None) or {}
        ap = sig.get("atr_pct")
        if ap and ap > 0:
            m *= max(0.3, min(1.0, 0.02 / ap))
        if pulse_panic():
            m *= 0.5
        return m


class SwingDip(Carrier):
    """SwingDipV1 — RSI/BB dip-in-uptrend (validated on 1d)."""
    roi = {0: 0.20, 5760: 0.12, 11520: 0.06, 20160: 0.0}
    protections = {"cooldown_candles": 1,
                   "slguard": {"lookback": 20, "trades": 2, "stop": 5},
                   "maxdd": {"lookback": 40, "trades": 4, "dd": 0.20, "stop": 5}}
    min_bars = 230

    def signals(self, bars, extra):
        c, h, l, v = bars["c"], bars["h"], bars["l"], bars["v"]
        if len(c) < self.min_bars:
            return None
        i = len(c) - 1
        rsi = rsi_series(c, 14)
        e50, e200 = ema_series(c, 50), ema_series(c, 200)
        tp = [(h[j] + l[j] + c[j]) / 3.0 for j in range(len(c))]   # typical px
        if None in (rsi[i], e50[i], e200[i]) or i < 20:
            return None
        bb_mid = sum(tp[i - 19:i + 1]) / 20.0
        bb_lo = bb_mid - 2.0 * stdev(tp[i - 19:i + 1])
        rng_hi = roll_max(h, 20, i - 1)      # shift(1)
        rng_lo = roll_min(l, 20, i - 1)
        if rng_hi is None or rng_lo is None:
            return None
        band = max(rng_hi - rng_lo, 1e-9)
        sell_zone = rng_hi - 0.15 * band
        enter = (e50[i] > e200[i] and rsi[i] < 42 and c[i] < bb_lo and v[i] > 0)
        exit_ = ((rsi[i] > 65 or c[i] >= sell_zone) and v[i] > 0)
        return {"enter": "dip_in_uptrend" if enter else None,
                "exit": exit_, "exit_reason": "sell_into_strength"}

    def stake_mult(self, tag, bars):
        return 0.5 if pulse_panic() else 1.0


class DayTraderGated(Carrier):
    """DayTraderV5Gated — entry modes switched by BTC's 4h 50/200 EMA regime;
    trailing ATR stop capped by the carrier stoploss; ROI ladder; timeouts."""
    roi = {0: 0.018, 180: 0.012, 360: 0.008, 720: 0.005}
    protections = {"cooldown_candles": 4,
                   "slguard": {"lookback": 48, "trades": 3, "stop": 12},
                   "maxdd": {"lookback": 96, "trades": 10, "dd": 0.15, "stop": 24}}
    min_bars = 70
    BAND_PCT_ON = 0.015
    BAND_PCT_OFF = 0.020
    MAX_ENTRIES_PER_HOUR = 2            # confirm_trade_entry throttle

    def signals(self, bars, extra):
        c, h, l, v = bars["c"], bars["h"], bars["l"], bars["v"]
        if len(c) < self.min_bars:
            return None
        i = len(c) - 1
        e50 = ema_series(c, 50)
        atr = atr_series(h, l, c, 14)
        adx = adx_series(h, l, c, 14)
        if e50[i] is None or atr[i] is None or i < 21:
            return None
        rng_hi = roll_max(h, 14, i - 1)      # _N=14, shift(1)
        rng_lo = roll_min(l, 14, i - 1)
        if rng_hi is None or rng_lo is None:
            return None
        band = max(rng_hi - rng_lo, 1e-9)
        buy_zone = rng_lo + 0.37 * band
        sell_zone = rng_hi - 0.22 * band
        band_pct = band / max(c[i], 1e-9)
        dc20 = roll_max(h, 20, i - 1)        # dc_high20.shift(1)
        uptick = c[i] > c[i - 1]
        live_vol = v[i] > 0
        e50_rising = e50[i - 6] is not None and e50[i] > e50[i - 6]
        regime_up = bool(extra.get("btc_regime_up"))   # fail-safe 0

        # freqtrade .loc order — LAST matching assignment wins the tag
        tag = None
        if (regime_up and c[i] <= buy_zone and band_pct >= self.BAND_PCT_ON
                and c[i] > e50[i] and uptick and live_vol):
            tag = "range_on"
        if (not regime_up and c[i] <= buy_zone and c[i] > e50[i] and e50_rising
                and band_pct >= self.BAND_PCT_OFF and uptick and live_vol):
            tag = "bounce_pullback"
        if (adx[i] is not None and adx[i] >= 25 and c[i] > e50[i]
                and dc20 is not None and c[i] > dc20
                and band_pct >= self.BAND_PCT_ON and live_vol):
            tag = "trend_breakout"
        # [2026-07-13 SLEEVE RETIRED with the freqtrade twin] range_meanrev —
        # 7d live in both Kraken carriers: 52 entries, -$13.94, negative in
        # every band bucket and under every stop variant. Twin parity: see
        # DayTraderV5Gated.py for the full evidence note.

        exit_ = (c[i] >= sell_zone and live_vol)
        return {"enter": tag, "exit": exit_, "exit_reason": "range_top",
                "atr": atr[i]}

    def stake_mult(self, tag, bars):
        m = 1.0
        if tag in ("bounce_pullback", "range_meanrev"):
            m *= 0.5                    # counter-daily-trend scalps size down
        if pulse_panic():
            m *= 0.5
        return m

    def atr_stop_dist(self, tag, bars, px):
        """custom_stoploss: 2.5x ATR (2.0x for the counter-trend tags) as a
        fraction of price, capped at the config stoploss — RATCHETS up only."""
        sig = self.signals(bars, {"btc_regime_up": 0}) if bars else None
        atr = (sig or {}).get("atr")
        if not atr or not px:
            return -self.stoploss
        # [2026-07-13] counter-trend stop 2.0x -> 3.5x, matching the freqtrade
        # twin (post-exit replay: the 2.0x stop fired on noise, 77-89% of
        # stop-outs reclaimed entry within 24h).
        mult = 3.5 if tag in ("bounce_pullback", "range_meanrev") else 2.5
        return min(mult * atr / px, -self.stoploss)

    def custom_exit(self, tag, age_min, profit):
        if tag == "bounce_pullback":
            if profit >= 0.012:
                return "bounce_take"
            if age_min >= 720:
                return "bounce_timeout"
        if age_min >= 1440:
            return "max_hold_timeout"
        return None


# One book per carrier — family four + the original spot bots (config-resolved
# timeframes/stops; mum/dad reflect the 13-Jul reverts to validated variants).
# crypto-trend-daily is NOT here: its Lighter shadow/live books already run in
# the tide-rider service (one bot, one home, one writer).
STRATEGIES = [
    TrendMomo("freqtrade-mum", tf="1d", stoploss=-0.15, max_open=4,
              style="trendmomo-1d"),
    MomoBreakout("freqtrade-dad", tf="4h", stoploss=-0.12, max_open=4,
                 style="momo-breakout-4h"),
    SwingDip("freqtrade-avo-maria", tf="4h", stoploss=-0.10, max_open=4,
             style="swing-dip-4h"),
    DayTraderGated("freqtrade-georgia", tf="15m", stoploss=-0.05, max_open=5,
                   style="daytrader-15m"),
    DayTraderGated("crypto-intraday-15m", tf="1h", stoploss=-0.12, max_open=5,
                   style="daytrader-1h", coins=WIDE_COINS),
    SwingDip("crypto-swing-daily", tf="1d", stoploss=-0.10, max_open=8,
             style="swing-dip-1d", coins=WIDE_COINS),
    MomoBreakout("crypto-breakout-4h", tf="4h", stoploss=-0.12, max_open=6,
                 style="momo-breakout-4h", coins=WIDE_COINS),
]


# ---------------------------------------------------------------------------
# Per-book runtime (one ShadowBroker + protections + ledger per family bot)

class Book:
    def __init__(self, strat, venue, coins):
        from venues.safety import SafetyRails
        from venues.shadow import ShadowBroker
        self.s = strat
        self.bot_id = strat.bot + "-lshadow"
        self.broker = ShadowBroker(self.bot_id, venue, START_EQUITY)
        self.rails = SafetyRails(strat.bot, "lighter_shadow")
        self.coins = coins
        self.meta = {}            # coin -> {entry, opened_ts, tag, accrued, stop_px}
        self.closed = []          # [{ts, pnl, pct, stop, pair}] for protections
        self.cooldown = {}        # pair -> release_ts
        self.guard_until = 0.0    # StoplossGuard / MaxDrawdown book-wide lock
        self.fund_realized = 0.0
        self.last_sig_ts = {}     # coin -> last closed-candle ts acted on
        self.throttle = {"bucket": None, "n": 0}
        self.n_closed = self.n_wins = 0
        self.halted_today = False
        self.day_start_equity = None
        self.last_accrue = time.time()

    # -- persistence ----------------------------------------------------------
    def restore(self):
        try:
            agg = store.fetch_paper_aggregate(self.bot_id)
            if agg:
                self.n_closed, self.n_wins = agg["closed"], agg["wins"]
        except Exception:  # noqa: BLE001
            pass
        saved = store.load_state(self.bot_id)
        if saved and self.broker.restore_state(saved.get("broker") or {}):
            self.meta = {str(k): v for k, v in (saved.get("meta") or {}).items()}
            self.closed = list(saved.get("closed") or [])
            self.fund_realized = float(saved.get("fund_realized") or 0.0)
            self.guard_until = float(saved.get("guard_until") or 0.0)
            self.cooldown = {str(k): float(v) for k, v in
                             (saved.get("cooldown") or {}).items()}
            log.info("%s restored: $%.2f, %d open", self.bot_id,
                     self.broker.equity(), self.broker.open_count())
        if store.load_daily_halt(self.bot_id,
                                 datetime.now(timezone.utc).date().isoformat()):
            self.halted_today = True
            log.warning("%s daily-loss halt restored — halted for today.", self.bot_id)

    def persist(self):
        try:
            store.save_state(self.bot_id, {
                "broker": self.broker.to_state(), "meta": self.meta,
                "closed": self.closed[-200:], "fund_realized": self.fund_realized,
                "guard_until": self.guard_until, "cooldown": self.cooldown})
        except Exception:  # noqa: BLE001
            pass

    # -- accounting -----------------------------------------------------------
    def equity(self):
        open_accr = sum((m or {}).get("accrued", 0.0) for m in self.meta.values())
        return self.broker.equity() + self.fund_realized + open_accr

    # -- protections (freqtrade-shaped, per strategy config) -------------------
    def entries_locked(self, now, tf_s):
        if now < self.guard_until:
            return True
        p = self.s.protections
        win = [c for c in self.closed
               if now - c["ts"] <= p.get("slguard", {}).get("lookback", 0) * tf_s]
        sg = p.get("slguard")
        if sg and sum(1 for c in win if c["stop"]) >= sg["trades"]:
            self.guard_until = now + sg["stop"] * tf_s
            log.warning("%s StoplossGuard: %d stops in window — entries off %.0fmin",
                        self.bot_id, sg["trades"], sg["stop"] * tf_s / 60)
            return True
        dd = p.get("maxdd")
        if dd:
            win = [c for c in self.closed if now - c["ts"] <= dd["lookback"] * tf_s]
            if len(win) >= dd["trades"]:
                cum = peak = trough = 0.0
                worst = 0.0
                for c in win:
                    cum += c["pnl"]
                    peak = max(peak, cum)
                    worst = max(worst, (peak - cum) / START_EQUITY)
                if worst >= dd["dd"]:
                    self.guard_until = now + dd["stop"] * tf_s
                    log.warning("%s MaxDrawdown %.0f%% in window — entries off %.0fmin",
                                self.bot_id, worst * 100, dd["stop"] * tf_s / 60)
                    return True
        return False

    def throttle_ok(self, now):
        if not isinstance(self.s, DayTraderGated):
            return True
        bucket = int(now // 3600)
        if self.throttle["bucket"] != bucket:
            self.throttle.update(bucket=bucket, n=0)
        if self.throttle["n"] >= self.s.MAX_ENTRIES_PER_HOUR:
            return False
        self.throttle["n"] += 1
        return True

    # -- trade lifecycle --------------------------------------------------------
    def record_close(self, coin, px, price_pnl, reason, notional=None, shadow=True):
        m = self.meta.get(coin) or {}
        fund_pnl = m.get("accrued", 0.0)
        self.fund_realized += fund_pnl
        total = price_pnl + fund_pnl
        pct = total / notional if notional else total / STAKE_USD
        self.n_closed += 1
        self.n_wins += 1 if total > 0 else 0
        was_stop = "stop" in reason
        self.closed.append({"ts": time.time(), "pnl": total,
                            "pct": pct, "stop": was_stop,
                            "pair": coin})
        tf_s = _interval_ms(self.s.tf) / 1000
        self.cooldown[coin] = time.time() + \
            self.s.protections.get("cooldown_candles", 1) * tf_s
        log.info("%s CLOSE %s | price %+.2f funding %+.2f [%s]",
                 self.bot_id, coin, price_pnl, fund_pnl, reason)
        try:
            store.publish_paper_trade(
                self.bot_id, trade_id=f"{coin}:{m.get('opened_ts')}",
                pnl_abs=float(total), pnl_pct=pct, pair=coin,
                opened_at=datetime.fromtimestamp(
                    m.get("opened_ts") or time.time(), tz=timezone.utc).isoformat(),
                closed_at=datetime.now(timezone.utc).isoformat(),
                reason=ledger_reason(m.get("tag"), reason),
                venue="lighter", shadow=shadow)
        except Exception:  # noqa: BLE001
            pass
        self.meta.pop(coin, None)


# ---------------------------------------------------------------------------

def btc_regime_up(cache):
    """BTC 4h EMA50>EMA200 on the last closed bar. Fail-safe 0 (the strategy's
    documented conservative default when the regime series is missing)."""
    bars = cache.get("BTC", "4h")
    if not bars or len(bars["c"]) < 210:
        return False
    e50 = ema_series(bars["c"], 50)
    e200 = ema_series(bars["c"], 200)
    return bool(e50[-1] and e200[-1] and e50[-1] > e200[-1])


def main():
    p = argparse.ArgumentParser(description="Family bots — Lighter shadow books")
    p.add_argument("--once", action="store_true", help="Single loop then exit.")
    args = p.parse_args()

    mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    # [v1 GATE] UNVALIDATED on this venue — shadow only, like Snap Back and
    # Counterweight before it. Going live is a separate decision on the record.
    if mode != "lighter_shadow":
        raise SystemExit("lighter_family_bot runs VENUE=lighter_shadow ONLY in "
                         "v1 — the family ports are unvalidated on Lighter; "
                         "the shadow record earns (or kills) any go-live.")

    from venues.lighter_client import LighterClient
    from venues import marks
    venue = LighterClient(net="mainnet", with_signer=False)

    cache = CandleCache(venue)
    books = []
    for s in STRATEGIES:
        src = s.coins or COINS
        listed = [c for c in src if venue.supports(c)]
        s.skipped = [c for c in src if c not in listed]
        books.append(Book(s, venue, listed))
    for b in books:
        b.restore()

    log.info("=" * 64)
    log.info("FAMILY + SPOT bots on LIGHTER (shadow) | %d books", len(books))
    for b in books:
        log.info("  %s | %s | tf=%s stop=%.0f%% slots=%d coins=%d (skip: %s) roi=%s",
                 b.bot_id, b.s.style, b.s.tf, b.s.stoploss * 100,
                 b.s.max_open, len(b.coins),
                 ", ".join(b.s.skipped) or "none", b.s.roi or "off")
    log.info("$%.0f/trade | long-only 1x (pays funding — drag modelled) | "
             "fills cross the live book | loop=%ds", STAKE_USD, LOOP_SECONDS)
    log.info("EVIDENCE-FIRST: Kraken paper twins keep running as the control "
             "arm. lighter_live REFUSED in v1.")
    log.info("=" * 64)

    cur_day = datetime.now(timezone.utc).date()
    for b in books:
        b.day_start_equity = b.equity()

    while True:
        t0 = time.time()
        now = datetime.now(timezone.utc)
        if now.date() != cur_day:
            cur_day = now.date()
            for b in books:
                b.halted_today = False
                b.day_start_equity = b.equity()

        try:
            fund = venue.funding_map()
        except Exception as e:  # noqa: BLE001
            log.warning("funding fetch failed (%s); accrual paused this loop", e)
            fund = {}
        regime = btc_regime_up(cache)

        # [2026-07-15 AUDIT FIX] L2 fleet long-budget veto, checked once per
        # cycle. The 14-Jul enforcement was wired only into the retired Kraken
        # strategies, leaving the RUNNING Lighter fleet unenforced. Contract
        # matches fleet_bus: fresh payload + mode=enforce + budget full ->
        # skip NEW entries; anything missing/stale fails OPEN (never blocks).
        fleet_long_veto = False
        fleet_gov = 1.0
        try:
            _fr = store.load_state("fleet-risk") or {}
            _upd = datetime.fromisoformat(
                str(_fr.get("updated")).replace("Z", "+00:00"))
            _age = (now - _upd).total_seconds()
            _lb = _fr.get("long_budget")
            _lb = 10**9 if _lb is None else int(_lb)   # 0 is a REAL budget
            if _age <= float(_fr.get("ttl_sec") or 900):
                if (_fr.get("mode") == "enforce"
                        and (_fr.get("long_positions") or 0) >= _lb):
                    fleet_long_veto = True
                    log.info("FLEET LONG-BUDGET VETO — %s/%s directional longs; "
                             "no new entries this cycle (exits unaffected)",
                             _fr.get("long_positions"), _fr.get("long_budget"))
                # [2026-07-15 GAP FIX] fleet drawdown governor — the taker
                # consumed clip_scale since 14-Jul, the gate0 books stayed
                # "advisory until ported". Ported: new-entry stakes scale by
                # clip_scale (1.0/0.5/0.25), clamped like the taker; stale/
                # missing state stays neutral 1.0 (fail-open).
                fleet_gov = max(0.25, min(1.0, float(_fr.get("clip_scale") or 1.0)))
                if fleet_gov < 1.0:
                    log.info("FLEET DRAWDOWN GOVERNOR — new-entry stakes x%.2f",
                             fleet_gov)
        except Exception:  # noqa: BLE001 — fail-safe open
            fleet_long_veto = False
            fleet_gov = 1.0

        for b in books:
            store.heartbeat(b.bot_id)
            tf_s = _interval_ms(b.s.tf) / 1000.0

            # ---- daily-loss rail (durable halt, debounced) ----
            eq = b.equity()
            if b.day_start_equity is None:
                b.day_start_equity = eq
            if (not b.halted_today and b.day_start_equity
                    and eq <= b.day_start_equity * (1 - DAILY_LOSS_LIMIT)):
                confirmed, eq = b.rails.confirm_daily_loss(
                    b.day_start_equity, eq, DAILY_LOSS_LIMIT, b.equity)
                if confirmed:
                    log.warning("%s DAILY LOSS LIMIT (%.2f <= %.2f) — flatten + halt.",
                                b.bot_id, eq, b.day_start_equity)
                    b.halted_today = True
                    store.save_daily_halt(b.bot_id, cur_day.isoformat(),
                                          b.day_start_equity)
                    for coin in list(b.meta):
                        px = marks.fresh_mid(venue, coin) or b.meta[coin]["entry"]
                        sz, ent = b.broker.pos.get(coin, (0.0, 0.0))
                        pnl = b.broker.close(coin, px)
                        b.record_close(coin, px, pnl, "rail_flatten",
                                       notional=abs(sz) * ent)

            dt_h = (t0 - b.last_accrue) / 3600.0
            b.last_accrue = t0

            if b.halted_today:
                try:
                    store.publish(b.bot_id, status="halted", equity=b.equity(),
                                  pnl_abs=b.equity() - START_EQUITY,
                                  closed_trades=b.n_closed, wins=b.n_wins,
                                  losses=b.n_closed - b.n_wins,
                                  extra={"mode": mode, "venue": mode,
                                         "style": b.s.style, "family": True})
                except Exception:  # noqa: BLE001
                    pass
                continue

            locked = b.entries_locked(t0, tf_s)

            for coin in b.coins:
                bars = cache.get(coin, b.s.tf)
                if not bars or not bars["t"]:
                    continue
                sig_ts = bars["t"][-1]
                new_candle = b.last_sig_ts.get(coin) != sig_ts
                sig = b.s.signals(bars, {"btc_regime_up": regime}) \
                    if new_candle else None
                if new_candle:
                    b.last_sig_ts[coin] = sig_ts

                held = coin in b.broker.pos
                px = marks.fresh_mid(venue, coin)

                # ---- manage an open long ----
                if held:
                    m = b.meta.get(coin) or {}
                    entry = m.get("entry") or 0.0
                    if px:
                        m.pop("no_px_since", None)   # priceable — reset clock
                        m["last_px"] = px
                        b.broker.mark(coin, px)
                        rate = (fund.get(coin) or {}).get("rate")
                        if rate is not None:
                            sz = abs(b.broker.pos[coin][0])
                            m["accrued"] = m.get("accrued", 0.0) - rate * sz * px * dt_h
                        b.meta[coin] = m
                    if not px or not entry:
                        # [2026-07-16 ZOMBIE GUARD] unpriceable in-list coin
                        if not px:
                            first = m.get("no_px_since")
                            if not isinstance(first, (int, float)):
                                m["no_px_since"] = t0
                                b.meta[coin] = m
                            elif (t0 - first) / 3600.0 >= DELIST_GIVEUP_H:
                                sz, ent = b.broker.pos.get(coin, (0.0, 0.0))
                                zpx = float(m.get("last_px") or ent or 0.0)
                                if zpx:
                                    pnl = b.broker.close(coin, zpx)
                                    b.record_close(coin, zpx, pnl, "delisted",
                                                   notional=abs(sz) * ent)
                        continue
                    profit = (px - entry) / entry
                    age_min = (t0 - (m.get("opened_ts") or t0)) / 60.0
                    reason = None

                    # stop (georgia: trailing ATR ratchet; others: fixed)
                    if isinstance(b.s, DayTraderGated):
                        dist = b.s.atr_stop_dist(m.get("tag"), bars, px)
                        m["stop_px"] = max(m.get("stop_px") or 0.0, px * (1 - dist))
                        if px <= m["stop_px"]:
                            reason = "trailing_stop_loss"
                    elif profit <= b.s.stoploss:
                        reason = "stop_loss"

                    # ROI ladder (continuous, like freqtrade)
                    if not reason and b.s.roi:
                        rung = max((k for k in b.s.roi if k <= age_min), default=None)
                        if rung is not None and profit >= b.s.roi[rung]:
                            reason = "roi"
                    # custom_exit timeouts (georgia)
                    if not reason and isinstance(b.s, DayTraderGated):
                        reason = b.s.custom_exit(m.get("tag"), age_min, profit)
                    # exit signal on a fresh candle (trend_breakout vetoes it)
                    if not reason and sig and sig.get("exit") and \
                            m.get("tag") != "trend_breakout":
                        reason = sig.get("exit_reason", "exit_signal")

                    if reason:
                        sz, ent = b.broker.pos.get(coin, (0.0, 0.0))
                        pnl = b.broker.close(coin, px)
                        b.record_close(coin, px, pnl, reason,
                                       notional=abs(sz) * ent)
                    continue

                # ---- flat: consider an entry (new candle only) ----
                if not sig or not sig.get("enter") or locked or not px:
                    continue
                if fleet_long_veto:
                    continue      # L2: fleet directional-long budget is full
                if b.broker.open_count() >= b.s.max_open:
                    continue
                if t0 < b.cooldown.get(coin, 0.0):
                    continue
                if not b.throttle_ok(t0):
                    log.info("%s %s entry throttled (max %d/h)", b.bot_id, coin,
                             DayTraderGated.MAX_ENTRIES_PER_HOUR)
                    continue
                tag = sig["enter"]
                # [2026-07-15 L4 CONSUMER] apply the brain's reduce-only
                # multiplier — restores the loop the Kraken retirement cut
                # (the only prior consumers were the stopped freqtrade
                # strategies). No-op until a tag earns a throttle at n>=15.
                bm = brain_stake_mult(b.bot_id, tag)
                if bm < 1.0:
                    log.info("%s %s brain stake-mult x%.2f (%s)",
                             b.bot_id, coin, bm, ledger_tag(tag))
                stake = STAKE_USD * b.s.stake_mult(tag, bars) * bm * fleet_gov
                size = stake / px
                b.broker.open(coin, True, size, px)
                ent = b.broker.pos.get(coin)
                entry_px = ent[1] if ent else px
                stop_px = None
                if isinstance(b.s, DayTraderGated):
                    dist = b.s.atr_stop_dist(tag, bars, entry_px)
                    stop_px = entry_px * (1 - dist)
                b.meta[coin] = {"entry": entry_px, "opened_ts": t0, "tag": tag,
                                "accrued": 0.0, "stop_px": stop_px}
                log.info("%s OPEN %s long $%.0f @ %.6g [%s]",
                         b.bot_id, coin, stake, entry_px, tag)

            # [2026-07-16 ZOMBIE GUARD] ORPHANS: a restored position whose
            # coin is no longer in b.coins never enters the loop above at all
            # (no mark, no accrual, no stop). Try to price it directly; give
            # up at the last known mark after DELIST_GIVEUP_H.
            for coin in [c for c in list(b.broker.pos) if c not in b.coins]:
                m = b.meta.get(coin) or {}
                try:
                    opx = marks.fresh_mid(venue, coin)
                except Exception:  # noqa: BLE001
                    opx = None
                if opx:
                    m.pop("no_px_since", None)
                    m["last_px"] = opx
                    b.meta[coin] = m
                    b.broker.mark(coin, opx)
                first = m.get("no_px_since")
                if opx is None and not isinstance(first, (int, float)):
                    m["no_px_since"] = t0
                    b.meta[coin] = m
                    continue
                # orphaned-but-priceable closes immediately (nothing manages
                # it); unpriceable waits out the give-up clock first
                if opx is None and (t0 - first) / 3600.0 < DELIST_GIVEUP_H:
                    continue
                sz, ent = b.broker.pos.get(coin, (0.0, 0.0))
                zpx = float(opx or m.get("last_px") or ent or 0.0)
                if not zpx:
                    continue
                pnl = b.broker.close(coin, zpx)
                b.record_close(coin, zpx, pnl, "delisted", notional=abs(sz) * ent)
                log.info("%s ORPHAN CLOSE %s @ %.6g (coin left the book's "
                         "universe)", b.bot_id, coin, zpx)

            # ---- publish + persist ----
            open_accr = sum((m or {}).get("accrued", 0.0) for m in b.meta.values())
            try:
                store.publish(
                    b.bot_id, status="online", equity=b.equity(),
                    pnl_abs=b.equity() - START_EQUITY,
                    open_trades=b.broker.open_count(),
                    closed_trades=b.n_closed, wins=b.n_wins,
                    losses=b.n_closed - b.n_wins,
                    extra={"mode": mode, "venue": mode, "style": b.s.style,
                           "family": True,
                           "held": {c: (m or {}).get("tag") for c, m in b.meta.items()},
                           "fund_realized": round(b.fund_realized, 4),
                           "fund_open": round(open_accr, 4),
                           "btc_regime_up": regime,
                           "skipped_unlisted": b.s.skipped})
            except Exception:  # noqa: BLE001
                pass
            b.persist()

        log.info("loop ok | %s | regime_up=%s",
                 " | ".join(f"{b.bot_id.split('-')[1]}: ${b.equity():.2f} "
                            f"{b.broker.open_count()} open" for b in books),
                 regime)
        if args.once:
            log.info("--once complete.")
            break
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _selftest():
    # EMA: talib seeds with SMA of first p. Series 1..5, p=3 -> seed 2, then
    # 2+ (4-2)*0.5 = 3, 3 + (5-3)*0.5 = 4.
    assert ema_series([1, 2, 3, 4, 5], 3)[-3:] == [2.0, 3.0, 4.0]
    # SMA plain.
    assert sma_series([1, 2, 3, 4], 2)[-1] == 3.5
    # RSI: all-up series -> 100; all-down -> 0.
    up = list(range(1, 40))
    assert abs(rsi_series(up, 14)[-1] - 100.0) < 1e-9
    dn = list(range(40, 1, -1))
    assert rsi_series(dn, 14)[-1] < 1e-9
    # ATR of a constant series -> 0.
    flat = [10.0] * 40
    assert abs(atr_series(flat, flat, flat, 14)[-1]) < 1e-12
    # ADX warms up and is bounded 0..100 on a trending series.
    h = [i + 1.0 for i in range(80)]
    l = [i + 0.5 for i in range(80)]
    c = [i + 0.8 for i in range(80)]
    a = adx_series(h, l, c, 14)[-1]
    assert a is not None and 0.0 <= a <= 100.0 and a > 50.0, a
    # stdev sample (ddof=1) matches the pandas default used by qtpylib BBs.
    assert abs(stdev([1, 2, 3, 4]) - 1.2909944487358056) < 1e-12
    # rolling window helpers honour shift semantics.
    assert roll_max([1, 5, 3, 2], 2, 2) == 5 and roll_min([1, 5, 3, 2], 2, 2) == 3
    # ROI rung selection: age 200min on the DayTrader ladder -> 0.012.
    g = DayTraderGated("t", tf="15m", stoploss=-0.05, max_open=5, style="t")
    rung = max((k for k in g.roi if k <= 200), default=None)
    assert g.roi[rung] == 0.012
    print("lighter_family_bot self-test: OK")


def _supervised():
    """[GO-GREEN pattern] unhandled exception -> log, mark rows ERROR,
    restart in 60s (state re-hydrates). SystemExit/Ctrl-C pass through."""
    while True:
        try:
            main()
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            log.exception("unhandled exception — marking rows ERROR, restart in 60s")
            for s in STRATEGIES:
                try:
                    store.set_status(s.bot + "-lshadow", "error")
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(60)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    try:
        _supervised()
    except KeyboardInterrupt:
        log.info("stopped by user.")
