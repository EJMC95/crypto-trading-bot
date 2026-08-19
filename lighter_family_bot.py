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
import random
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis

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
# [2026-07-30 STEP 3 — operator: "run step 3 too".] The item-18/D5 build
# order completes: the FOUR family books' universe now carries the venue's
# non-crypto books, governed by the per-asset gate (regime_inputs_for +
# the entry-site rule below): an UNGRADED book (SPY/QQQ/IWM/WTI/XCU/MSTR
# until the oracle's 203-bar floor) admits NOTHING — it sits listed and
# idle until the tape graduates it — and a graded book admits longs only
# in its OWN LONG-window (at ship: NVDA 30% of bars, TSLA 2%, XAU 4%,
# XAG 12% — the gate is mostly closed, by the evidence's own shape).
# Spot ports keep WIDE_COINS untouched (their s.coins override pins them).
# Empty FAMILY_NONCRYPTO_COINS reverts the universe to crypto-only.
NONCRYPTO_UNIVERSE = [c.strip() for c in os.environ.get(
    "FAMILY_NONCRYPTO_COINS",
    "SPY,QQQ,IWM,NVDA,TSLA,MSTR,WTI,XAU,XAG,XCU").split(",") if c.strip()]
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
    """The brain's TWO-WAY per-(bot, tag) stake multiplier for an entry
    (reduce-only until 21-Jul), looked up under EXACTLY the identity this
    book's ledger rows carry (bot_id row name + ledger_tag). fleet_bus owns
    the fail-safe contract (fresh payload only, clamp [0.5, 1.5], neutral
    1.0 on any doubt); the guard here only covers an image built without
    fleet_bus.py."""
    try:
        import fleet_bus
        return float(fleet_bus.stake_multiplier(bot_id, ledger_tag(tag)))
    except Exception:  # noqa: BLE001
        return 1.0


def brain_entry_gated(bot_id, tag):
    """[2026-07-21 BRAIN ACTS — operator mandate] True when the brain's
    streak-hardened regime_timing finding for THIS (bot, tag) is active AND
    the regime oracle currently reads risk-off — the measured condition under
    which the tag's losses clustered (e.g. georgia|long-trend-breakout: 100%
    of matched losses opened counter-regime). Restrict-only: it can only
    SKIP a new entry; exits, sizing and every other tag are untouched, and
    the gate lifts on its own when the regime turns or the finding retires.
    Same keying as the mults (bot_id + ledger_tag); fleet_bus owns freshness
    + the BRAIN_ACTIONS_MODE kill switch; fail-safe OPEN (dark bus = no
    gate), incl. an image built without fleet_bus.py."""
    try:
        import fleet_bus
        return bool(fleet_bus.entry_regime_gated(bot_id, ledger_tag(tag)))
    except Exception:  # noqa: BLE001
        return False


def symcap_state(fr):
    """[2026-07-22 SYMBOL CAP ENFORCED — operator: "can we fix the budget
    saturation"] Parse the already-loaded fleet-risk payload's per-symbol
    pileup cap into (cap, {base: fleet-wide long count}) — or None when the
    cap does not enforce (advisory/disabled/absent/junk), which every caller
    must treat as OPEN. The caller owns freshness (this bot's fleet-risk
    read already gates on updated+ttl_sec); this stays pure so the selftest
    can pin the whole contract offline. Counts below fleet_risk's noise
    filter (min(2, cap)) are absent from the payload and read as 0 — at
    cap>=2 that can never mask a bind."""
    try:
        sc = (fr or {}).get("symbol_cap") or {}
        if str(sc.get("mode")) != "enforce":
            return None
        cap = int(sc.get("cap") or 0)
        if cap <= 0:
            return None
        held = {str(k): int(v) for k, v in
                (sc.get("long_by_symbol") or {}).items()}
        return cap, held
    except Exception:  # noqa: BLE001
        return None


def symcap_blocked(state, coin, cycle_sym):
    """True when opening ANOTHER long on `coin` would stack past the fleet's
    per-symbol cap, counting BOTH the published fleet-wide holds and the
    longs THIS process already admitted this cycle (`cycle_sym` — the same
    in-cycle race the 21-Jul budget-headroom fix bounds: seven books share
    one payload read, so without the local count one cycle could stack a
    symbol straight past the cap). Restrict-only, fail-safe OPEN on any
    parse error or state=None."""
    try:
        if state is None:
            return False
        cap, held = state
        base = str(coin).split("/")[0]
        return (int(held.get(base, 0))
                + int((cycle_sym or {}).get(base, 0))) >= cap
    except Exception:  # noqa: BLE001
        return False


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
        st = store.load_state("market-pulse") or {}
        latest = st.get("latest") or {}
        # [2026-07-17 IMB-04] gate on the payload's OWN updated+ttl_sec — a
        # fossil panic=true from a dead market_pulse kept halving every new
        # entry forever (the 'alive but sick' class the immune organ doesn't
        # scan). Stale/unstamped/future-dated -> False; parity with every
        # other consumed bus key.
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(
            str(st.get("updated")).replace("Z", "+00:00"))).total_seconds()
        fresh = 0 <= age <= float(st.get("ttl_sec") or 0)
        _pulse.update(ts=time.time(), panic=bool(latest.get("panic")) and fresh)
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


class OversoldRebound(Carrier):
    """👩 mum v2 — DEEP-OVERSOLD REBOUND, 1h, bracketed, OUTSIDE the uptrend.

    [2026-08-19 (ro)] THE REVIVAL. mum v1 (TrendMomo, above) was retired hours
    earlier by `(rd)` on an I17 `no_rate` call. The operator reversed it:
    "unretire mum and bring her back to life... give her the attention she
    needs to succeed." This class is that attention, and it is a REDESIGN
    rather than a reprieve — reviving v1's shape would re-run the failure.

    WHAT ACTUALLY KILLED HER — measured on her own record, not inferred:
      * THE CLOCK, and it is the whole story. Her entry was a STATE
        (`fast > slow`), so at boot every qualifying coin filled in the same
        second — all three of her lifetime closes opened 2026-07-12T21:41:49Z.
        Her ONLY exit was the SMA death CROSS, a roughly-monthly event, with
        `roi` disabled and no time stop. Holds: 33.1 / 29.1 / 25.1 days.
        Realised rate ~2.4 closes/30d against a 30-closes-in-30-days go-live
        bar — ~12 MONTHS to decidability. She was never losing; she was
        UNGRADEABLE, which is I17's whole point.
      * THE FUNDING DRAG WAS REAL BUT SMALL — and `(rd)` overstated it, which
        is corrected here per I12. Summing the venue's OWN settled hourly
        series (`/api/v1/fundings`) across her exact hold windows at her $50
        clip: BTC -$0.220, LINK -$0.058, LTC +$0.032 => **-$0.246 total**, not
        the -$2.15 that entry claimed (that figure must have pooled the four
        still-open positions and/or the bot's modelled accrual). Her gross
        price P&L was +$1.985 and her ledger net +$0.679. The retirement's
        DECISIVE ground — the clock — is untouched by the correction.
      * NOTE THE UNIT TRAP, recorded because it inverts a number by 12.5x:
        `/funding-rates` quotes per 8h as a FRACTION, but the SETTLED series
        `/api/v1/fundings` quotes **percent per HOUR**. Verified empirically —
        the median non-zero settled rate is exactly 0.0012 on BTC/ETH/HYPE,
        which is the venue's documented resting default (9.6e-05 per 8h =>
        1.2e-05/hr => 0.0012 %/hr). Hourly fraction is `rate/100`, never
        `rate/8`. funding_basis.py's header states it; it is easy to miss.

    THE TWO NUMBERS THAT SHAPE V2, both measured on Lighter's own data:
      1. CARRY: MEASURED across 478 days x 20 coins, a long on the majors pays
         a median **+0.0171%/day** of notional — so v1's 29-day median hold
         starts **~0.50% behind** while v2's 12h cap starts 0.009% behind.
         (The venue's RESTING-rate arithmetic gives 0.0288%/day; the realised
         median is lower, and quoting the resting figure as the average was a
         first-draft error corrected here.) The spread is wide and matters:
         HYPE +0.0445%/day (1.33%/30d) and AAVE +0.0342 at one end, DOT and
         SPY slightly NEGATIVE (longs are PAID) at the other; 65-95% of hours
         are long-pays depending on the coin. Carry punishes DURATION, and v1
         was built from the maximum-duration end of that table.
      2. EXECUTION IS NEARLY FREE: across **~400 short-hold closes** in the
         fleet's own paper ledger the exit-side gap between the decision mark
         and the realised fill has a median of **-0.8 bps** (p90 5 bps) — the
         venue is zero-fee and these are majors, so the cost model is the
         crossed spread alone. Round trip ~1-2 bps.
      TOGETHER THEY ARE THE INDICTMENT: this venue charges almost nothing to
      trade OFTEN and a real amount to hold LONG, and v1 was configured at
      precisely the wrong corner of both. Turnover was free and she refused it.

    THE FIX IS THE CLOCK, EXPRESSED AS ARITHMETIC. Moving from 1d to 1h bars
    multiplies the decision surface by 24: ~15 coins x 24 bars/day = ~360
    coin-bars/day against v1's ~15. A deep-oversold tail fires on a few
    percent of coin-bars, so signals arrive several times a day, and with 4
    slots and a 12h cap the book is bounded at 8 closes/day. **30 closes
    arrives in about a week instead of about a year.** The `scan` census
    publishes the realised rate from the first loop, so this claim is
    falsifiable from the row itself rather than taken on faith (I18).

    THE ENTRY, AND WHY IT IS THIS ONE. It is NOT a new invention — it is the
    one cell this fleet has already MEASURED as carrying information, and
    nobody expresses. `(qu)`'s exit-free decomposition of 🙏 avo's SwingDip
    (1,156 signals, 475d, 23 coins) found: only **`rsi < 42` carries
    information**, and the **`e50 > e200` trend filter is ACTIVELY DESTRUCTIVE
    — adding it LOWERED the mean of every base** (R +0.208 -> +0.025,
    B +0.346 -> +0.187, R&B +0.349 -> +0.124). The `rsi < 25` dose-response
    was the strongest term in the study (+2.32%/trade at h=12, 19/23 coins
    positive). So v2 takes the deep tail and REFUSES the filter that was
    hurting it.

    HONESTY, because this is the part a good result must not paper over: that
    dose-response has **DECAYED through zero** on rolling 120d windows
    (+4.97 -> +2.05 -> -0.31 -> -0.41). This entry is therefore
    **HYPOTHESIS-GRADE, stated as such** — it is not a proven edge and must
    never be quoted as one. What v2 changes is that the question becomes
    ANSWERABLE in a week rather than a year, and answered against a control
    rather than against zero.

    THE CONTROL ARM — the thing that makes her worth reviving. `(hm)` requires
    a directional book to be graded against a RANDOM-ENTRY null, never against
    zero, because a random long/short on this tape earns a non-zero amount for
    free. That rule is honoured in studies and has never been carried by a
    LIVE book. mum v2 carries her own: at every entry she records the mark of a
    randomly chosen OTHER coin from her own universe, and at exit the same
    coin's mark — a matched-window, unmatched-signal placebo that costs no
    capital and controls for drift and regime. `extra.control` publishes
    {n, mean_pct, null_pct, edge_pct} every loop, so at day 30 the verdict is
    her mean against her OWN null on the same clock, readable from the payload.

    I20 — SHE TILES, AND THE CLAIM IS STATED AT ITS REAL STRENGTH. The entry
    requires **NOT (e50 > e200)** while 🙏 avo's SwingDip requires
    `e50 > e200`, so on the SAME timeframe the two predicates are disjoint by
    construction and the `(lv)` subset-starvation trap — a consumer starved by
    a superset running first in the same process — is unreachable between
    them. avo takes dips INSIDE an uptrend on 4h holding ~3.5 days; mum takes
    the deep tail OUTSIDE one on 1h capped at 12h.

    **THE HONEST LIMIT, declared rather than glossed: the two books read trend
    on DIFFERENT timeframes** (mum 1h, avo 4h), so a coin in a 4h uptrend that
    is simultaneously in a 1h downtrend can satisfy BOTH — the predicates are
    disjoint per-timeframe, not across timeframes, and a simultaneous long in
    both books is therefore possible. That is I20's "one bet held twice" in its
    weak form. It is NOT closed by a new gate here, because closing it would
    mean shrinking mum's supply on no measurement; it is bounded by machinery
    that already exists and binds fleet-wide — `fleet_risk`'s per-symbol cap
    and the enforced 20-long budget, both checked at this loop's entry site.
    Monitorable from the payload: mum's `held` map beside avo's. If the pair
    is measured to co-hold materially, the cheap fix is a 4h-trend screen on
    mum, and it should be made on that measurement rather than pre-emptively.

    DELIBERATELY NOT ENCODED, so nobody re-proposes them as oversights: no
    trend filter (measured destructive), no pyramiding, no ROI widening, no
    leverage, and no exit SIGNAL — the bracket is predefined at entry and never
    moved, which is 🧘 Douglas's discipline and the reason his book is
    gradeable. The clip is a constant $50 (`stake_mult` returns 1.0 and takes
    no streak, outcome or equity input) so consistency is structural.
    """
    # take profit early, then decay to breakeven by the 12h cap: the carry
    # measurement says duration is the tax, so the ladder pays for patience
    # only while patience is cheap.
    roi = {0: 0.020, 240: 0.012, 480: 0.006, 720: 0.0}
    protections = {"cooldown_candles": 2,
                   "slguard": {"lookback": 24, "trades": 3, "stop": 6},
                   "maxdd": {"lookback": 72, "trades": 8, "dd": 0.15, "stop": 12}}
    min_bars = 210                      # e200 on 1h needs >200 closed bars
    RSI_MAX = 25.0                      # (qu)'s measured dose cell
    MAX_HOLD_MIN = 720                  # 12h — the carry-bounded cap
    control_arm = True                  # publishes its own random-entry null
    census = True                       # publishes why nothing opened (I18)
    #: v1 positions (opened 2026-07-12) are flattened on the first v2 loop —
    #: they are v1-policy artifacts holding all four slots, and a book that
    #: cannot enter cannot be graded. Their closes are tagged `v1_legacy` and
    #: they opened BEFORE the era boundary, so `golive_readiness.era_rows`
    #: (which keys on the OPEN) excludes them from v2's grade by construction.
    #: 2026-08-19T21:45:00Z. MUST be in the PAST at deploy: a boundary in the
    #: future flattens v2's OWN entries on sight — caught by
    #: test_the_frozen_v1_positions_are_released before this shipped, which is
    #: exactly what that arm is for.
    FLATTEN_BEFORE_TS = 1787175900.0

    def signals(self, bars, extra):
        c, h, l, v = bars["c"], bars["h"], bars["l"], bars["v"]
        if len(c) < self.min_bars:
            return None
        i = len(c) - 1
        rsi = rsi_series(c, 14)
        e50, e200 = ema_series(c, 50), ema_series(c, 200)
        if None in (rsi[i], e50[i], e200[i]):
            return None
        # NOT an uptrend: the cell 🙏 avo structurally cannot take (I20), and
        # the half (qu) measured the trend filter was destroying.
        outside_uptrend = not (e50[i] > e200[i])
        enter = (rsi[i] < self.RSI_MAX and outside_uptrend and v[i] > 0)
        # No exit SIGNAL by design — the bracket predefined at entry is the
        # whole exit rule (stop / roi ladder / max hold). Douglas's discipline.
        return {"enter": "oversold-rebound" if enter else None,
                "exit": False, "exit_reason": "bracket",
                "rsi": rsi[i], "uptrend": not outside_uptrend}

    def stake_mult(self, tag, bars):
        return 1.0                      # constant clip — consistency is structural

    def custom_exit(self, tag, age_min, profit):
        """The carry-bounded time cap. At the measured +0.0171%/day majors
        median a 12h hold pays 0.009% of notional; v1's 29-day median hold
        paid ~0.50% before it earned anything. That tax is refused here."""
        if age_min >= self.MAX_HOLD_MIN:
            return "max_hold"
        return None


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
        # [2026-07-22 PARITY 14-Jul] MomoBreakoutV1's BTC-tide gate: block a
        # breakout while BTC is under its OWN 4h EMA200 (the market-wide
        # fakeout filter the freqtrade original gained 14-Jul but the port
        # never received — 3-13 Jul both carriers went 2W/9L as 11 pairs broke
        # above their own 200-EMA and died in a market fakeout). Present key
        # GATES (fail-safe closed on a falsey tide); absent key (stake_mult's
        # signals(bars, None) and the replay/study harnesses) leaves it
        # ungated, so no baseline regresses. Operator-approved 22-Jul on the
        # falling-half evidence; kill switch MOMO_TIDE_GATE=off omits the key.
        if extra and "btc_tide_up" in extra:
            enter = enter and bool(extra["btc_tide_up"])
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
    # [2026-08-19 (ro)] 👩 mum v2 — the operator's revival, redesigned rather
    # than reprieved. 1d -> 1h is the clock fix (24x the decision surface);
    # -15% -> -4% is a stop sized for a 12h hold instead of a month-long one.
    # TrendMomo (v1's class) is KEPT above: the replay/study tools import it
    # and her v1 ledger is history, not archaeology.
    OversoldRebound("freqtrade-mum", tf="1h", stoploss=-0.04, max_open=4,
                    style="oversold-1h"),
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


# [2026-08-14 (mr)] 🚀 crypto-breakout-4h RETIRED — the I17 keep-or-retire call,
# made by the operator on a measurement rather than escalated again.
#
# WHY THIS BOOK AND NOT THE OTHER EIGHT ON THE DOCKET. The decision docket fired
# 14-Aug with NINE books. Testing nine at once is exactly where `(li)` had to
# correct this fleet's record — it had called three 🏛️ books "measured losers"
# when none survived multiple-comparison correction. Under Benjamini-Hochberg at
# FDR 0.05 across all nine, **exactly one survives: this one** (p=0.0036 against
# a 0.0056 critical value; the next-closest, pm-abbott, reads 0.0430 against
# 0.0111 and is NOT evidence).
#
# ITS OWN RECORD, and the two samples agree in direction AND significance —
# which is what separates a positive finding of harm from an underpowered null:
#   in-era   n=15  mean -1.745%/trade  t=-3.50  halves -2.56/-4.94  win 20.0%
#   all-time n=21  mean -2.236%/trade  t=-5.48  halves -5.63/-6.74  win 14.3%
#   -$12.37 realised, ~-$0.48/day, horizon verdict `unreachable` (mean <= 0, so
#   more of the same closes CANNOT flip mean/t/halves — not a slow winner).
#
# WHAT IT FREES, and the dollars are the least of it: TWO enforced long-budget
# slots (`fleet_risk` is in `enforce` mode on a shared 20-long budget) held by
# TRX and LINK, on the one book the fleet can prove is losing money — and TRX is
# the fleet's largest single-symbol long share. It also stops dragging the
# family cohort's empirical-Bayes priors, which size the OTHER family books'
# stakes.
#
# IT COSTS NO THESIS COVERAGE: 4h breakout survives in 🧙 book-schwager
# (Donchian-20 + EMA confirm, n=277, +$457.21, t=1.88, both halves positive).
# A losing EXPRESSION is retired; the idea is not.
#
# ROW-SCOPED BY CONSTRUCTION, because this is the fleet's first retirement of a
# book that SHARES ITS MODULE. 🌊 Tide Rider and 📊 Index Rider each owned their
# file and could idle the whole process (`while True: sleep`); doing that here
# would silence the other six family books. So the declaration is a SET and the
# running roster is DERIVED from it ((mo)'s one-declaration-one-derivation) —
# `STRATEGIES` stays whole so the venue/universe assertions and the history keep
# covering it, and `live_strategies()` is the only thing the loop builds from.
#
# The two open paper positions FREEZE, which is the precedent both prior row
# retirements set (Tide Rider's 6 and Index Rider's +$13.93 were abandoned as
# marks-not-evidence). This is $1k paper with no real money; there is nothing to
# unwind. Ledgers (`paper_trades`, `venue_orders`) and history are KEPT.
# Reversible: BREAKOUT4H_RETIRED_OVERRIDE=run.
RETIRED_BOOKS = {
    "crypto-breakout-4h": "BREAKOUT4H_RETIRED_OVERRIDE",
    # [2026-08-15 (nf)] THE I17 CALLS, MADE — operator decision on the
    # decision docket's own verdicts (asks open since 6-Aug):
    #   crypto-intraday-15m  horizon=unreachable (era n=72, mean −0.082%/t;
    #                        −$6.88 realised) — 3 open paper positions freeze,
    #                        the (mr) precedent
    #   crypto-swing-daily   horizon=no_rate — n=3 in six weeks, the I17
    #                        UNDECIDABLE shape (🌊's 9-buys-zero-sells class)
    #   freqtrade-dad        horizon=unreachable (era n=15, mean −1.317%/t) —
    #                        3 open paper positions freeze
    # mum (green, slow) / avo (the gate candidate) / georgia (+$4.43) stay.
    "crypto-intraday-15m": "INTRADAY15M_RETIRED_OVERRIDE",
    "crypto-swing-daily":  "SWINGDAILY_RETIRED_OVERRIDE",
    "freqtrade-dad":       "DAD_RETIRED_OVERRIDE",
    # [2026-08-19 (ro)] 👩 mum's (rd) retirement was REVERSED by the operator
    # ("unretire mum and bring her back to life") and she is deliberately NOT
    # listed here. She returns as v2 — a different strategy (OversoldRebound,
    # 1h, bracketed) — because reviving v1's shape would re-run v1's failure:
    # her disease was the CLOCK (~2.4 closes/30d => ~12 months to the bar),
    # not a loss. The (rd) evidence stands as history except its funding-drag
    # figure, corrected in place at the class: settled funding on her three
    # closes was -$0.246, not -$2.15.

}


def live_strategies():
    """`STRATEGIES` minus the retired books whose override is not set.

    DERIVED, never a second hand-maintained list — the retirement is declared
    once in `RETIRED_BOOKS` and every consumer reads it through here, so a book
    cannot be retired in one loop and alive in another. Fail-OPEN on a set
    override: an operator who says `run` gets the book back with no redeploy.
    """
    out = []
    for s in STRATEGIES:
        env = RETIRED_BOOKS.get(s.bot)
        if env and os.environ.get(env, "").strip().lower() \
                not in ("run", "1", "true"):
            continue
        out.append(s)
    return out


# ---------------------------------------------------------------------------
# Per-book runtime (one ShadowBroker + protections + ledger per family bot)

def _control_extra(b):
    """[(ro)] 👩 mum v2's own random-entry null, published every loop.

    ALWAYS PRESENT for a control-arm book, including at n=0 — an omitted key
    is byte-identical between "no closes yet" and "the arm is not running"
    ((lv)/I18), and this is the number her whole revival will be judged on.
    `edge_pct` is the only figure that matters at day 30: her mean per trade
    MINUS what a coin flip on the same clock earned.
    """
    if not getattr(b.s, "control_arm", False):
        return {}
    c = b.ctrl
    mean = (c["sum"] / c["n"] * 100.0) if c["n"] else None
    null = (c["null_sum"] / c["null_n"] * 100.0) if c["null_n"] else None
    return {"control": {
        "n": c["n"], "null_n": c["null_n"],
        "mean_pct": round(mean, 4) if mean is not None else None,
        "null_pct": round(null, 4) if null is not None else None,
        "edge_pct": (round(mean - null, 4)
                     if (mean is not None and null is not None) else None),
        "basis": "matched-window random-coin placebo, same open/close instants "
                 "((hm): a directional book is graded against a random-entry "
                 "null, never against zero)"}}


def _census_extra(b):
    """[(ro)] WHY DID NOTHING OPEN? — the I18/(lv) rule: `opened: 0` must never
    be byte-identical between "quiet market" and "structurally impossible".
    v1's whole failure was invisible for five weeks because her row could not
    say that her exit simply never fired."""
    if not getattr(b.s, "census", False):
        return {}
    out = dict(b.scan)
    # [2026-08-19 (rq)] IS THE GATE EVEN REACHABLE? The census says WHY nothing
    # opened; this says HOW FAR AWAY the market is from opening something —
    # which is the difference between "quiet today" and "this threshold will
    # never fire", and 👩 mum v1 died of the second while every reading on her
    # row looked like the first. `no_signal: 23` alone cannot tell them apart.
    # Reported, never a gate: nothing here decides a trade.
    try:
        bar = getattr(b.s, "RSI_MAX", None)
        if bar is not None and b.last_rsi:
            vals = sorted(b.last_rsi.values())
            out["rsi_bar"] = bar
            out["rsi_min"] = round(vals[0], 1)          # closest coin to the bar
            out["rsi_med"] = round(vals[len(vals) // 2], 1)
            out["rsi_read"] = len(vals)                 # coins with a reading
            # how many sit within 8 points of the bar — the leading indicator
            # of supply, visible hours before an entry rather than days after
            out["near_bar"] = sum(1 for v in vals if v < bar + 8)
    except Exception:  # noqa: BLE001
        pass
    return {"scan": out}


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
        # [2026-08-19 (ro)] 👩 mum v2's CONTROL ARM and census. Present on every
        # Book (cheap, additive) but only POPULATED for a carrier that declares
        # `control_arm` / `census`, so no other book's payload shape moves.
        self.last_mark = {}      # coin -> most recent mark seen this cycle
        self.last_rsi = {}       # coin -> last computed RSI (gate reachability)
        self.ctrl = {"n": 0, "sum": 0.0, "null_sum": 0.0, "null_n": 0}
        self.scan = {}           # per-cycle census counters
        self.halted_today = False
        self.day_start_equity = None
        self.last_accrue = time.time()
        # [2026-08-04 SEED GUARD] False until a CLEAN state read. While False
        # the book neither trades nor persists — see restore()/persist().
        self._restored = False

    # -- persistence ----------------------------------------------------------
    def restore(self):
        try:
            agg = store.fetch_paper_aggregate(self.bot_id)
            if agg:
                self.n_closed, self.n_wins = agg["closed"], agg["wins"]
        except Exception:  # noqa: BLE001
            pass
        # [2026-08-04 SEED GUARD] the CHECKED read — load_state() collapses
        # "no row" and "READ FAILED" into one None, so a Postgres blip at boot
        # started a fresh $1000 book whose persist() then OVERWROTE the durable
        # record (georgia's graded sample rides this state). Parliament's
        # 21-Jul pattern for a multi-book container: on a failed read stay
        # un-restored — the main loop skips this book's cycle and retries next
        # loop; persist() refuses until a clean read. sys.exit is wrong here:
        # one shared connection failing would kill all seven books for one
        # book's blip. No DATABASE_URL = fresh book (old behavior): with no DB
        # the write path cannot overwrite anything either.
        if not os.environ.get("DATABASE_URL", "").strip():
            self._restored = True
            saved = None
        else:
            ok, saved = store.load_state_checked(self.bot_id)
            if not ok:
                log.warning("%s state read FAILED — NOT seeding a fresh book "
                            "over a blip; this book skips trading until a "
                            "clean read (retry next cycle)", self.bot_id)
                return
            self._restored = True
        if saved and self.broker.restore_state(saved.get("broker") or {}):
            self.meta = {str(k): v for k, v in (saved.get("meta") or {}).items()}
            self.closed = list(saved.get("closed") or [])
            self.fund_realized = float(saved.get("fund_realized") or 0.0)
            self.guard_until = float(saved.get("guard_until") or 0.0)
            self.cooldown = {str(k): float(v) for k, v in
                             (saved.get("cooldown") or {}).items()}
            # [2026-07-16 AUDIT FIX] restore the accrual clock — it reset to
            # boot time each redeploy, so funding across the gap was never
            # accrued (systematic undercount). Gap bounded to 48h.
            try:
                _lt = float(saved.get("last_accrue") or 0)
                if _lt:
                    self.last_accrue = max(_lt, time.time() - 48 * 3600)
            except Exception:  # noqa: BLE001
                pass
            # [(rp)] restore the control arm's accumulated pairs, shape-checked
            # so a malformed blob degrades to a fresh arm rather than raising
            # inside the boot path.
            try:
                _c = saved.get("ctrl") or {}
                if isinstance(_c, dict):
                    self.ctrl = {k: (float(_c[k]) if k in ("sum", "null_sum")
                                     else int(_c[k]))
                                 for k in ("n", "sum", "null_sum", "null_n")
                                 if k in _c} or self.ctrl
                    for k, d in (("n", 0), ("sum", 0.0),
                                 ("null_sum", 0.0), ("null_n", 0)):
                        self.ctrl.setdefault(k, d)
            except Exception:  # noqa: BLE001
                self.ctrl = {"n": 0, "sum": 0.0, "null_sum": 0.0, "null_n": 0}
            log.info("%s restored: $%.2f, %d open", self.bot_id,
                     self.broker.equity(), self.broker.open_count())
        if store.load_daily_halt(self.bot_id,
                                 datetime.now(timezone.utc).date().isoformat()):
            self.halted_today = True
            log.warning("%s daily-loss halt restored — halted for today.", self.bot_id)

    def persist(self):
        # [2026-08-04 SEED GUARD] never overwrite durable state we could not
        # read (parliament's rule, verbatim). Without this gate the guard in
        # restore() protects nothing — the first loop's persist() would write
        # the fresh book over the record anyway.
        if not self._restored:
            return
        try:
            store.save_state(self.bot_id, {
                "broker": self.broker.to_state(), "meta": self.meta,
                "closed": self.closed[-200:], "fund_realized": self.fund_realized,
                "guard_until": self.guard_until, "cooldown": self.cooldown,
                "last_accrue": self.last_accrue,
                # [(rp)] the control arm is a THIRTY-DAY instrument living in a
                # container that redeploys whenever any shared organ changes.
                # In-memory it reset to zero on every deploy and could never
                # reach its own sample — an instrument that silently loses its
                # evidence is worse than none (I4: never discard a persistence
                # result, and never let a long-run measurement depend on
                # uptime).
                "ctrl": self.ctrl})
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
        # [2026-08-19 (ro)] THE CONTROL ARM settles here, on the same clock as
        # the real trade. (hm) requires a directional book to be graded against
        # a RANDOM-ENTRY null rather than against zero — a random long on this
        # tape earns a non-zero amount for free — and until now that rule lived
        # only in studies. This is a matched-WINDOW, unmatched-SIGNAL placebo:
        # same open and close instants, a coin picked at random from the book's
        # own universe, no capital. Never raises: a control arm that can break
        # a trading loop is worse than no control arm.
        # THE PAIR ACCUMULATES ATOMICALLY OR NOT AT ALL, and that is a
        # correctness rule rather than tidiness. [2026-08-19 (rp)] The first
        # live payload counted mum's FOUR v1 legacy flattens into this arm —
        # `n: 4, mean_pct: 7.81` — because the real leg was recorded whenever a
        # trade closed while the placebo leg needed a partner. Those closes are
        # v1-policy marks being realised, not v2's edge, and they had no
        # placebo (they opened before v2 existed), so the arm's headline
        # started at +7.81% on a sample that is not this book's record: the
        # exact contamination `POLICY_ERA` exists to prevent, one instrument
        # over. Requiring BOTH legs makes `n == null_n` true by construction,
        # excludes every legacy close for free, and keeps the comparison
        # PAIRED — an unpaired observation cannot be differenced against
        # anything, so dropping it is the honest statistic, not a loss.
        try:
            _np, _ne = m.get("null_pair"), m.get("null_entry")
            _npx = self.last_mark.get(_np) if _np else None
            if (getattr(self.s, "control_arm", False) and notional
                    and _np and _ne and _npx and float(_ne) > 0):
                self.ctrl["n"] += 1
                self.ctrl["sum"] += total / notional
                self.ctrl["null_n"] += 1
                self.ctrl["null_sum"] += (float(_npx) - float(_ne)) / float(_ne)
        except Exception:  # noqa: BLE001
            pass
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
                # [2026-07-30 (gr)] EXIT TELEMETRY — `px` (the exit mark) and
                # m["entry"] were both in scope and neither reached the row, so
                # no exit rule on these four books could be counterfactually
                # tested. Telemetry only; no gate moves.
                entry_price=m.get("entry"), exit_price=px,
                # [2026-08-06 (kn)] SIDE, and it is a CONSTANT here. These
                # seven rows are LONG-ONLY — the only two mentions of "short"
                # in this module are a selftest asserting that a short verdict
                # CLOSES a position — so the value is knowable with certainty
                # and was still absent. `(kf)` stamped the taker, sniper and
                # Counterweight, and this book was SKIPPED by its guard on the
                # heuristic "no `is_long` in source ⇒ no direction concept",
                # which is exactly backwards: a long-only book is the case
                # where the side is least in doubt.
                # Measured cost: the exit sweep discarded 53 priced closes
                # across 🔮 georgia (33), intraday (14), avo-maria (5) and
                # dad (1) — georgia being one of only three books sitting at
                # 4/6 on the go-live gate, so the exit question could not be
                # asked of a book near real money. Telemetry only; no gate,
                # entry, exit or size moves.
                side="long",
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


# [2026-07-22] MomoBreakout's BTC-TIDE gate kill switch (MOMO_TIDE_GATE=off
# reverts to the pre-parity, ungated port).
MOMO_TIDE_GATE = os.environ.get("MOMO_TIDE_GATE", "on").strip().lower() \
    not in ("off", "0", "no", "false", "disabled")


def btc_tide_up(cache):
    """BTC 4h close > EMA200 on the last closed bar — MomoBreakoutV1's 14-Jul
    market-tide gate, ported EXACTLY (this is close>EMA200, deliberately NOT
    btc_regime_up's EMA50>EMA200). Fail-safe False (off-tide), the original's
    documented conservative default when the series is missing."""
    bars = cache.get("BTC", "4h")
    if not bars or len(bars["c"]) < 210:
        return False
    e200 = ema_series(bars["c"], 200)
    return bool(e200[-1] and bars["c"][-1] > e200[-1])


# [2026-07-30 PER-ASSET REGIME — item-18 step 2, operator call.] The family
# gate now CONSUMES the oracle's per-asset coverage, honouring the declared
# build order (oracle coverage → the gate consumes it → only then the
# universe). STATIC classification, deliberately: if this set were read from
# the oracle's payload, a dark oracle would silently re-classify SPY as
# crypto and hand it BTC's gate — the exact state D5 forbids. Mirrors
# regime_oracle.NONCRYPTO; the selftest drift-guards the two sets.
# INERT TODAY: no family universe lists a non-crypto symbol — the universe
# widening (step 3) stays a review decision (evidence:
# REGIME_GATE_PER_ASSET_2026-07-30.md; re-runs at SPY/QQQ graduation).
NONCRYPTO_SYMS = frozenset({
    "SPY", "QQQ", "IWM", "NVDA", "TSLA", "MSTR", "WTI", "XAU", "XAG", "XCU"})

# [2026-07-30 (fd) FAIL-CLOSED CLASSIFICATION] The gate keys on the KNOWN set
# above, but the UNIVERSE is env-driven (FAMILY_NONCRYPTO_COINS). Those two
# could disagree: an operator adding a book the frozenset does not know — say
# `FAMILY_NONCRYPTO_COINS=SPY,ARKK` — would have routed ARKK down the CRYPTO
# path and handed it BTC's 4h gate. That is precisely the D5 violation this
# whole build order exists to prevent, re-entering through a config edit.
# So the EFFECTIVE non-crypto set is the union: anything the operator lists as
# non-crypto IS treated as non-crypto, and since the oracle will not grade an
# unknown book, the per-asset gate then fails CLOSED (no entries) instead of
# silently substituting crypto's regime. Adding an unknown symbol can only
# ever cost entries, never mis-gate one.
NONCRYPTO_EFFECTIVE = NONCRYPTO_SYMS | set(NONCRYPTO_UNIVERSE)

# Kill switch: 'off' closes non-crypto entries entirely (both gates False).
# There is deliberately NO value that routes a non-crypto book to BTC's
# gates — the switch chooses between "asset's own regime" and "no entries",
# never the incoherent third option.
FAMILY_PER_ASSET_REGIME = os.environ.get(
    "FAMILY_PER_ASSET_REGIME", "oracle").strip().lower()


def regime_inputs_for(coin, btc_regime, btc_tide, oracle_verdicts):
    """(regime_up, tide_up) a coin's strategy signals should see.

    CRYPTO (everything outside NONCRYPTO_EFFECTIVE): the validated BTC gates,
    passed through untouched — this function is a no-op for today's whole
    universe, and the selftest pins that.

    NON-CRYPTO: the asset's OWN oracle verdict (fleet_bus.
    oracle_asset_regimes) — LONG-window ⇒ both gates up; any other verdict,
    an ungraded book, or a dark/stale oracle ⇒ fail-CLOSED (False, False).
    Both gates ride one verdict deliberately: the oracle's LONG-window
    already requires trend + direction, and inventing a second per-asset
    tide flavour nothing trades yet would be an untested gate. The strategy
    `extra` keys keep their btc_* names for port compatibility; for a
    non-crypto coin they carry the asset's own read.
    """
    if coin not in NONCRYPTO_EFFECTIVE:
        return btc_regime, btc_tide
    if FAMILY_PER_ASSET_REGIME == "off":
        return False, False
    up = (oracle_verdicts or {}).get(coin) == "LONG-window"
    return up, up


def noncrypto_regimes():
    """Per-asset verdict map for the gate above, fetched once per cycle —
    {} on any doubt (which regime_inputs_for treats as fail-closed for
    non-crypto). Same image-safety guard as the other fleet_bus wrappers."""
    try:
        import fleet_bus
        return fleet_bus.oracle_asset_regimes()
    except Exception:  # noqa: BLE001
        return {}


def noncrypto_entry_blocked(coin, regime_up):
    """[2026-07-30 STEP 3] The uniform entry-site rule for non-crypto pairs:
    a long entry on a NONCRYPTO_EFFECTIVE book requires its OWN gate up.

    WHY it lives at the ENTRY SITE and not only in the strategy extras:
    TrendMomo and SwingDip never read the regime keys — through the extras
    alone they would buy SPY dips with NO gate at all (not the forbidden
    BTC-gate, but bare of any gate; the Georgia diagnosis — 100% of losses
    opened counter-regime — is the measured cost of exactly that shape).
    This rule makes the per-asset gate binding for every strategy
    uniformly. Restrict-only (it can only skip an entry), crypto pairs are
    never touched, and exits/holds are never gated — an open position is
    always managed."""
    return coin in NONCRYPTO_EFFECTIVE and not regime_up


def shadow_max_open_overrides(raw=None):
    """[(ne)] {bot_id: max_open} — the SHADOW runner's capacity overrides,
    parsed from FAMILY_SHADOW_MAX_OPEN_OVERRIDES ("bot:slots,bot:slots").
    Called from main() ONLY, never at import: the live Avo bot binds the same
    STRATEGIES instance by identity and sizes its real-money clip as
    equity/max_open, so the declared literals are live surface. Values clamp
    to [1, 12]; junk tokens are dropped, never guessed. Default carries the
    measured avo step (X3, adversarially confirmed: cap-4 binding 39% of its
    era, cap 6 ≈ +25% close rate, no era reset per (hc)); "" reverts."""
    if raw is None:
        raw = os.environ.get("FAMILY_SHADOW_MAX_OPEN_OVERRIDES",
                             "freqtrade-avo-maria:6")
    out = {}
    for tok in str(raw).split(","):
        tok = tok.strip()
        if not tok or ":" not in tok:
            continue
        bid, v = tok.rsplit(":", 1)
        try:
            out[bid.strip()] = max(1, min(12, int(v)))
        except ValueError:
            continue
    return out


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
    # [2026-08-15 (ne)] SHADOW-ONLY capacity overrides, applied in main() and
    # NEVER at import — lighter_avo_live_bot binds the SAME STRATEGIES
    # instance by identity and sizes its REAL-MONEY clip as equity/max_open,
    # so the declared literal is live surface and must not move (the referee's
    # kill-class finding). This env is read only by THIS runner, in the shadow
    # container. Measured basis (X3, adversarially confirmed): avo shadow's
    # cap-4 is BINDING — 39% of its era at 4/4, at cap at measurement time,
    # AAVE 24-25-Jul + LTC 25-Jul signals fired during measured full windows;
    # cap 6 recovers ~+2 closes/21d (~+25% close rate, closes-bar ETA ~64d vs
    # 80d) with NO era reset (capacity is (hc) ordinary tuning; precedents
    # carry 8->12, Counterweight K 5->8). Cap 8 was NOT supported (one
    # marginal add contradicted by the real timeline, LINK pileup) and is not
    # shipped. Marginal expectancy at confidence: UNMEASURED (n=2 recovered
    # signals, one-regime tape) — a throughput step on the book's own signal,
    # not an expectancy claim. Revert: FAMILY_SHADOW_MAX_OPEN_OVERRIDES="".
    _mo_overrides = shadow_max_open_overrides()
    for s in live_strategies():
        if s.bot in _mo_overrides and _mo_overrides[s.bot] != s.max_open:
            log.info("%s: SHADOW max_open %d -> %d ((ne) capacity override; "
                     "live literal untouched)", s.bot, s.max_open,
                     _mo_overrides[s.bot])
            s.max_open = _mo_overrides[s.bot]
        # [2026-07-30 STEP 3] the four family books (no s.coins override)
        # carry the non-crypto universe; spot ports pin their own lists
        src = list(s.coins) if s.coins else list(COINS) + NONCRYPTO_UNIVERSE
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

    # [2026-07-30 PER-ASSET REGIME] one boot-time read of the universe: the
    # oracle fetch below runs only when some book actually lists a
    # non-crypto symbol — today none does, so the wiring adds ZERO reads
    # until the universe decision (step 3) lands.
    has_noncrypto = any(c in NONCRYPTO_EFFECTIVE for b in books for c in b.coins)

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
        tide = btc_tide_up(cache)     # [2026-07-22 PARITY] MomoBreakout gate
        # [2026-07-30 PER-ASSET REGIME] verdicts for any non-crypto pairs,
        # once per cycle; {} when none listed (today) or the oracle is dark
        nc_verdicts = noncrypto_regimes() if has_noncrypto else {}

        # [2026-07-15 AUDIT FIX] L2 fleet long-budget veto, checked once per
        # cycle. The 14-Jul enforcement was wired only into the retired Kraken
        # strategies, leaving the RUNNING Lighter fleet unenforced. Contract
        # matches fleet_bus: fresh payload + mode=enforce + budget full ->
        # skip NEW entries; anything missing/stale fails OPEN (never blocks).
        fleet_long_veto = False
        fleet_gov = 1.0
        # [2026-07-21 AUDIT FIX] in-cycle HEADROOM: one veto read covers all
        # seven books' entries, so a single green check could admit up to 7
        # longs in one cycle and push the fleet past the budget (measured
        # live: 22 longs against the 20 budget — the overshoot mechanism
        # behind the watchdog's standing warning). Track the remaining slots
        # from the same read and stop admitting when THIS CYCLE has used
        # them; the cross-process race with other consumers stays (only the
        # publisher can close it) but the single biggest overshoot source —
        # this process's own batch — is bounded. None = fail-open unlimited
        # (advisory mode / stale state), exactly the old contract.
        fleet_long_headroom = None
        cycle_admitted = 0
        # [2026-07-22 SYMBOL CAP] per-symbol pileup cap (fleet_risk publishes,
        # enforced by default since today — operator call with saturation
        # re-measured worse). None = open; cycle_sym counts THIS cycle's own
        # admits per base so seven books can't stack one symbol past the cap
        # on a single payload read.
        fleet_symcap = None
        cycle_sym = {}
        try:
            _fr = store.load_state("fleet-risk") or {}
            _upd = datetime.fromisoformat(
                str(_fr.get("updated")).replace("Z", "+00:00"))
            _age = (now - _upd).total_seconds()
            _lb = _fr.get("long_budget")
            _lb = 10**9 if _lb is None else int(_lb)   # 0 is a REAL budget
            if _age <= float(_fr.get("ttl_sec") or 900):
                if _fr.get("mode") == "enforce":
                    fleet_long_headroom = max(
                        0, _lb - int(_fr.get("long_positions") or 0))
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
                # [2026-07-22 SYMBOL CAP] same fresh payload, same fail-open
                # contract; symcap_state returns None unless the published
                # mode enforces.
                fleet_symcap = symcap_state(_fr)
        except Exception:  # noqa: BLE001 — fail-safe open
            fleet_long_veto = False
            fleet_long_headroom = None
            fleet_gov = 1.0
            fleet_symcap = None

        for b in books:
            store.heartbeat(b.bot_id)
            # [2026-08-04 SEED GUARD] a book whose durable state could not be
            # read does NOT trade this cycle — trading un-restored means a
            # fresh $1000 book opening positions the record says are already
            # held. Retry the read each loop; on a late success re-anchor the
            # daily rail (boot anchored it on the fresh book's equity, and a
            # wrong anchor could false-trip the -10% halt the moment the real
            # equity appears). persist() is refusing meanwhile, so nothing
            # durable is at risk while we wait.
            if not b._restored:
                b.restore()
                if not b._restored:
                    log.warning("%s still un-restored — skipping cycle "
                                "(no trade, no persist)", b.bot_id)
                    continue
                b.day_start_equity = b.equity()
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
            # [(ro)] census: mutually-exclusive per-coin outcomes for THIS
            # cycle, so a quiet row can name its own binding constraint.
            b.scan = {"scanned": 0, "held": 0, "no_bars": 0, "no_px": 0,
                      "no_signal": 0, "locked": 0, "capped": 0, "cooldown": 0,
                      "vetoed": 0, "opened": 0}

            for coin in b.coins:
                bars = cache.get(coin, b.s.tf)
                b.scan["scanned"] += 1
                if not bars or not bars["t"]:
                    b.scan["no_bars"] += 1
                    continue
                sig_ts = bars["t"][-1]
                new_candle = b.last_sig_ts.get(coin) != sig_ts
                # [2026-07-22 PARITY] pass the BTC tide only when the gate is
                # ON — MOMO_TIDE_GATE=off omits the key so MomoBreakout runs
                # ungated (pre-parity behavior); the other three strategies
                # ignore the key regardless.
                # [2026-07-30 PER-ASSET REGIME] inputs resolved per coin:
                # crypto = the BTC values above, byte-identical; a non-crypto
                # coin gets its OWN oracle verdict, fail-closed (key names
                # kept for the strategy ports).
                _r_up, _t_up = regime_inputs_for(coin, regime, tide,
                                                 nc_verdicts)
                _extra = {"btc_regime_up": _r_up}
                if MOMO_TIDE_GATE:
                    _extra["btc_tide_up"] = _t_up
                sig = b.s.signals(bars, _extra) if new_candle else None
                if new_candle:
                    b.last_sig_ts[coin] = sig_ts
                # [(rq)] gate REACHABILITY: keep the last reading per coin so
                # the row can say how far the market is from the entry bar.
                if sig and isinstance(sig.get("rsi"), (int, float)):
                    b.last_rsi[coin] = float(sig["rsi"])

                held = coin in b.broker.pos
                px = marks.fresh_mid(venue, coin)
                if px:
                    b.last_mark[coin] = px      # (ro) control-arm draw pool

                # ---- manage an open long ----
                if held:
                    b.scan["held"] += 1
                    m = b.meta.get(coin) or {}
                    entry = m.get("entry") or 0.0
                    if px:
                        m.pop("no_px_since", None)   # priceable — reset clock
                        m["last_px"] = px
                        b.broker.mark(coin, px)
                        rate = (fund.get(coin) or {}).get("rate")
                        if rate is not None:
                            sz = abs(b.broker.pos[coin][0])
                            # [2026-07-17 BASIS FIX ii] `rate` is per 8h, not
                            # hourly. These books are long-only and PAY, so the
                            # 8x over-accrual made them look WORSE than real —
                            # the opposite sign to Counterweight's, same bug.
                            m["accrued"] = m.get("accrued", 0.0) - (
                                funding_basis.to_hourly(rate, "lighter")
                                * sz * px * dt_h)
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

                    # [2026-08-19 (ro)] LEGACY FLATTEN — a position opened
                    # under a RETIRED policy is not this book's record and it
                    # holds a slot the new policy needs. 👩 mum's four v1
                    # positions (opened 2026-07-12) would otherwise occupy
                    # every slot forever, and a book that cannot enter cannot
                    # be graded. They close once, tagged, and they opened
                    # BEFORE the era boundary so `era_rows` (which keys on the
                    # OPEN) excludes them from v2's grade by construction.
                    _fb = getattr(b.s, "FLATTEN_BEFORE_TS", 0.0)
                    if _fb and (m.get("opened_ts") or 0) < _fb:
                        reason = "v1_legacy"

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
                    # custom_exit timeouts (georgia's bounce/max-hold, and
                    # 👩 mum v2's carry-bounded 12h cap). [2026-08-19 (ro)]
                    # DUCK-TYPED rather than isinstance-gated: the old form
                    # silently ignored a custom_exit on any new carrier, which
                    # is the registered-but-inert shape (I18) — a time stop
                    # that never fires is exactly how v1 held for a month.
                    if not reason and hasattr(b.s, "custom_exit"):
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
                if not px:
                    b.scan["no_px"] += 1
                    continue
                if not sig or not sig.get("enter"):
                    b.scan["no_signal"] += 1
                    continue
                if locked:
                    b.scan["locked"] += 1
                    continue
                # [2026-07-30 STEP 3] non-crypto books enter ONLY inside
                # their own LONG-window — binding for every strategy,
                # including the ones that never read the regime extras
                if noncrypto_entry_blocked(coin, _r_up):
                    log.info("%s %s entry SKIPPED — non-crypto book outside "
                             "its own LONG-window (per-asset gate, D5)",
                             b.bot_id, coin)
                    continue
                if fleet_long_veto:
                    b.scan["vetoed"] += 1
                    continue      # L2: fleet directional-long budget is full
                if (fleet_long_headroom is not None
                        and cycle_admitted >= fleet_long_headroom):
                    log.info("%s %s entry SKIPPED — in-cycle budget headroom "
                             "used (%d admitted this cycle)", b.bot_id, coin,
                             cycle_admitted)
                    continue      # L2: this cycle already used the free slots
                if b.broker.open_count() >= b.s.max_open:
                    b.scan["capped"] += 1
                    continue
                if symcap_blocked(fleet_symcap, coin, cycle_sym):
                    log.info("%s %s entry SKIPPED — fleet per-symbol cap %d "
                             "reached on %s (fleet-wide incl. this cycle)",
                             b.bot_id, coin, fleet_symcap[0], coin)
                    continue      # L2: de-pileup — cap longs per symbol
                if t0 < b.cooldown.get(coin, 0.0):
                    b.scan["cooldown"] += 1
                    continue
                if not b.throttle_ok(t0):
                    log.info("%s %s entry throttled (max %d/h)", b.bot_id, coin,
                             DayTraderGated.MAX_ENTRIES_PER_HOUR)
                    continue
                tag = sig["enter"]
                # [2026-07-21 BRAIN ACTS] the brain's regime_timing finding
                # now IMPLEMENTS itself: skip this NEW entry while the
                # oracle reads risk-off and the finding stands. Everything
                # else (exits, other tags, sizing) untouched; fail-safe open.
                if brain_entry_gated(b.bot_id, tag):
                    log.info("%s %s entry SKIPPED — brain regime_gate on %s "
                             "(risk-off now; lifts when regime turns or the "
                             "finding retires)",
                             b.bot_id, coin, ledger_tag(tag))
                    continue
                # [2026-07-15 L4 CONSUMER; 2026-07-21 TWO-WAY] apply the
                # brain's per-tag multiplier — reduce (0.5/0.75) since
                # 15-Jul, and since 21-Jul also EXPAND (1.25/1.5) for tags
                # proving out on the v3 mirror bars (operator: "brain needs
                # to be able to widen too"). fleet_bus clamps [0.5, 1.5].
                bm = brain_stake_mult(b.bot_id, tag)
                if bm != 1.0:
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
                _meta = {"entry": entry_px, "opened_ts": t0, "tag": tag,
                         "accrued": 0.0, "stop_px": stop_px}
                # [2026-08-19 (ro)] draw this trade's PLACEBO: a random OTHER
                # coin from the same universe, marked at this same instant.
                # Drawn from marks already fetched this cycle, so it costs no
                # extra venue call.
                if getattr(b.s, "control_arm", False):
                    try:
                        _pool = [c for c in b.last_mark if c != coin]
                        if _pool:
                            _nc = random.choice(_pool)
                            _meta["null_pair"] = _nc
                            _meta["null_entry"] = b.last_mark[_nc]
                    except Exception:  # noqa: BLE001
                        pass
                b.meta[coin] = _meta
                b.scan["opened"] += 1
                cycle_admitted += 1
                _base = str(coin).split("/")[0]
                cycle_sym[_base] = cycle_sym.get(_base, 0) + 1
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
                           # [(ne)] the EFFECTIVE cap (the (go) rule: publish
                           # the gate in force, so the row is a receipt)
                           "max_open": b.s.max_open,
                           "held": {c: (m or {}).get("tag") for c, m in b.meta.items()},
                           "fund_realized": round(b.fund_realized, 4),
                           "fund_open": round(open_accr, 4),
                           "btc_regime_up": regime,
                           "skipped_unlisted": b.s.skipped,
                           **_control_extra(b), **_census_extra(b)})
            except Exception:  # noqa: BLE001
                pass
            # [2026-08-15 (my)] I9: the MTM equity series for the six family/
            # spot books. The MTM_PENDING exemption ("short holds, |unreal|
            # <= $5.31") was written before 🙏 avo-maria-lshadow became the
            # fleet's CLOSEST book to the go-live gate (4/6 bars) — the (ia)
            # drawdown bar reads this series or reads realised-only, and a
            # book must not walk to the gate with the stricter definition
            # dark. Same per-loop cadence as every wired funding book.
            try:
                store.snapshot_equity(b.bot_id, b.equity(),
                                      b.broker.open_count())
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
    # [2026-07-22 PARITY] MomoBreakout BTC-tide gate: present key gates,
    # absent key leaves it ungated (harness/stake_mult safety).
    mb = MomoBreakout("t", tf="4h", stoploss=-0.12, max_open=6, style="s")
    _n = mb.min_bars + 5
    # a clean breakout bar: last close above the prior-20 high and above EMA200
    _c = [100.0] * (_n - 1) + [130.0]
    _h = [101.0] * (_n - 1) + [130.0]
    _l = [99.0] * _n
    _v = [1.0] * _n
    _bars = {"c": _c, "h": _h, "l": _l, "v": _v, "t": list(range(_n))}
    assert mb.signals(_bars, {"btc_tide_up": True})["enter"] == "breakout", \
        "tide up -> breakout admitted"
    assert mb.signals(_bars, {"btc_tide_up": False})["enter"] is None, \
        "tide down -> breakout blocked (fail-safe closed on falsey tide)"
    assert mb.signals(_bars, {"btc_regime_up": 1})["enter"] == "breakout", \
        "absent tide key -> ungated (harness/replay contract)"
    assert mb.signals(_bars, None)["enter"] == "breakout", \
        "extra=None (stake_mult path) -> ungated, no crash"
    # [2026-07-22] per-symbol cap consumer contract (pure, offline).
    _enf = {"symbol_cap": {"mode": "enforce", "cap": 3,
                           "long_by_symbol": {"ETH": 3, "LTC": 2}}}
    st = symcap_state(_enf)
    assert st == (3, {"ETH": 3, "LTC": 2}), st
    assert symcap_blocked(st, "ETH", {}) is True, "at cap -> blocked"
    assert symcap_blocked(st, "ETH/USDT", {}) is True, "base-normalizes"
    assert symcap_blocked(st, "LTC", {}) is False, "under cap -> open"
    assert symcap_blocked(st, "LTC", {"LTC": 1}) is True, \
        "fleet 2 + this cycle 1 = 3 -> blocked (in-cycle stacking counted)"
    assert symcap_blocked(st, "BTC", {"BTC": 2}) is False, \
        "unheld fleet-wide, 2 this cycle -> still under cap"
    assert symcap_blocked(st, "BTC", {"BTC": 3}) is True, \
        "a single cycle alone can reach the cap"
    # fail-open: advisory mode, disabled cap, junk payloads, None state.
    assert symcap_state({"symbol_cap": {"mode": "advisory", "cap": 3,
                                        "long_by_symbol": {"ETH": 9}}}) is None
    assert symcap_state({"symbol_cap": {"mode": "enforce", "cap": 0}}) is None
    assert symcap_state({}) is None and symcap_state(None) is None
    assert symcap_state({"symbol_cap": {"mode": "enforce", "cap": "x"}}) is None
    assert symcap_blocked(None, "ETH", {"ETH": 99}) is False, \
        "no enforcing state -> always open"
    # [2026-07-30 PER-ASSET REGIME — item-18 step 2] regime_inputs_for:
    # crypto is a byte-identical passthrough; non-crypto rides its OWN
    # verdict, fail-CLOSED everywhere else; BTC's gates NEVER leak in.
    global FAMILY_PER_ASSET_REGIME, NONCRYPTO_UNIVERSE, NONCRYPTO_EFFECTIVE
    assert regime_inputs_for("BTC", True, False, {}) == (True, False), \
        "crypto passthrough keeps regime and tide independent"
    assert regime_inputs_for("ETH", False, True,
                             {"ETH": "LONG-window"}) == (False, True), \
        "a crypto symbol NEVER reads the oracle map — BTC gates rule"
    assert regime_inputs_for("SPY", False, False,
                             {"SPY": "LONG-window"}) == (True, True), \
        "non-crypto LONG-window opens BOTH gates off its own verdict"
    for _v in ("SHORT-window", "dir-flat", "chop-gated"):
        assert regime_inputs_for("SPY", True, True, {"SPY": _v}) == \
            (False, False), f"non-directional/short verdict closes ({_v})"
    assert regime_inputs_for("SPY", True, True, {}) == (False, False), \
        "ungraded book fails CLOSED — never BTC's regime for SPY (D5)"
    assert regime_inputs_for("XAU", True, True, None) == (False, False), \
        "dark oracle (None map) fails CLOSED"
    _saved_par = FAMILY_PER_ASSET_REGIME
    try:
        FAMILY_PER_ASSET_REGIME = "off"
        assert regime_inputs_for("SPY", True, True,
                                 {"SPY": "LONG-window"}) == (False, False), \
            "kill switch closes non-crypto entirely — never re-routes to BTC"
        assert regime_inputs_for("BTC", True, True, {}) == (True, True), \
            "kill switch never touches crypto"
    finally:
        FAMILY_PER_ASSET_REGIME = _saved_par
    # [2026-07-30 STEP 3 — the inertness tripwire FLIPS, on the operator's
    # "run step 3 too"] the FAMILY universe (no-override strategies) now
    # carries the non-crypto books; the spot ports' pinned lists stay crypto.
    assert set(NONCRYPTO_UNIVERSE) <= NONCRYPTO_EFFECTIVE, \
        "the effective set must cover the configured universe by construction"
    assert not any(set(s.coins or []) & NONCRYPTO_EFFECTIVE
                   for s in STRATEGIES), \
        "spot ports' pinned lists must stay crypto-only (step 3 scope = " \
        "the four family books)"
    # [2026-07-30 (fd)] AN ENV-ADDED SYMBOL THE FROZENSET DOES NOT KNOW MUST
    # FAIL CLOSED, never fall through to BTC's gate. Before the union, the
    # classification was a hardcoded set while the universe was env-driven, so
    # `FAMILY_NONCRYPTO_COINS=SPY,ARKK` routed ARKK down the CRYPTO path and
    # handed it BTC's 4h regime — the D5 violation re-entering through config.
    _saved_u = (NONCRYPTO_UNIVERSE, NONCRYPTO_EFFECTIVE)
    try:
        NONCRYPTO_UNIVERSE = ["SPY", "ARKK"]
        NONCRYPTO_EFFECTIVE = NONCRYPTO_SYMS | set(NONCRYPTO_UNIVERSE)
        assert "ARKK" not in NONCRYPTO_SYMS, "fixture must use an UNKNOWN book"
        # unknown + ungraded by the oracle => no entry, and NEVER BTC's read
        assert regime_inputs_for("ARKK", True, True, {}) == (False, False), \
            "an unknown non-crypto book must fail CLOSED, not inherit BTC"
        assert noncrypto_entry_blocked("ARKK", False) is True, \
            "the entry-site rule must bind on an env-added book too"
        # and it still rides its OWN verdict if the oracle ever grades it
        assert regime_inputs_for("ARKK", False, False,
                                 {"ARKK": "LONG-window"}) == (True, True)
    finally:
        NONCRYPTO_UNIVERSE, NONCRYPTO_EFFECTIVE = _saved_u
    # the uniform entry-site rule: non-crypto blocked outside its own
    # LONG-window, for EVERY strategy; crypto never touched
    assert noncrypto_entry_blocked("SPY", False) is True
    assert noncrypto_entry_blocked("SPY", True) is False
    assert noncrypto_entry_blocked("BTC", False) is False, \
        "the entry-site rule must never gate a crypto pair"
    assert noncrypto_entry_blocked("XAU", False) is True
    # drift guard: the static classification mirrors the oracle's set
    try:
        import regime_oracle as _ro
        assert NONCRYPTO_SYMS == frozenset(_ro.NONCRYPTO), \
            "NONCRYPTO_SYMS drifted from regime_oracle.NONCRYPTO"
    except ImportError:
        pass  # oracle module absent from this image — the static set stands
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
            # live_strategies(), not STRATEGIES: marking a RETIRED row `error`
            # would re-publish it and undo the prune on the next cleanup pass.
            for s in live_strategies():
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
