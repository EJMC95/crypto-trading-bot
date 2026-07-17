#!/usr/bin/env python3
"""
scripts/backtest_georgia_short_sleeve.py — "would a SHORT sleeve fix 🔮 Georgia?"

THE QUESTION (operator, 2026-07-17): georgia (DayTraderV5Gated, 15m, long-only)
is the family's day trader. Would adding a short position be the winning factor
it's missing?

╔══════════════════════════════════════════════════════════════════════════════╗
║ THE VERDICT — AND ITS LOAD-BEARING CONSTANT, IN THE SAME SENTENCE.           ║
║                                                                              ║
║ **Whether a short sleeve HELPS or HURTS georgia is decided entirely by       ║
║ LIGHTER'S PER-FILL SLIPPAGE — a number THIS FLEET HAS NEVER MEASURED.**      ║
║ The sleeve is not rejected and not accepted. It is UNDECIDABLE on today's    ║
║ evidence, and the missing evidence is not more tape — it is 57 real fills    ║
║ nobody has read.                                                             ║
║                                                                              ║
║   slip/side    CONTROL long   MIRROR      SHORT only   passive short+hold    ║
║   5.00 bps     -$223.95       -$291.67    - $85.62     +$323.65             ║
║   0.86 bps     - $85.83       - $15.75    + $76.37     +$323.96             ║
║   0.00 bps     - $53.73       + $36.57    +$101.58     +$324.02             ║
║                                                                              ║
║   The sleeve HURTS at 5.00 and HELPS at 0.86. Its P&L crosses ZERO between   ║
║   two numbers, NEITHER of which anyone has measured. That is the finding.    ║
║                                                                              ║
║ 5.00 bps = MY ASSUMPTION (never measured). 0.86 bps = the ShadowBroker's     ║
║ MODEL (also never measured against a real fill). They merely disagree; see   ║
║ [[funding-farmer-carry-cannot-pay]] and [[real-fills-have-never-been-        ║
║ measured]]. The sign of the answer sits between two unmeasured numbers.      ║
║                                                                              ║
║ This banner exists because scripts/backtest_funding_lighter.py had its       ║
║ verdict WITHDRAWN on 2026-07-17 for exactly this: an unqualified conclusion  ║
║ denominated in an assumed 5bps. Its lesson — "if a constant is load-bearing  ║
║ and unmeasured, it belongs in the VERDICT SENTENCE or the verdict is not     ║
║ earned" — is why the caveat is in the headline here, not the small print.    ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT *IS* ROBUST (holds at BOTH slippage assumptions — quote these freely):

 1. **THE LONG SIDE IS BROKEN AT ZERO FRICTION** — the single slippage-proof
    result here. CONTROL loses -$53.73 at 0.00 bps, n=3,656, wr 49.7%. No
    execution improvement can rescue it, because friction is not what is
    killing it. THIS is georgia's actual bug, and it is not direction: a short
    sleeve leaves it untouched. (An earlier draft of this header claimed "no arm
    is profitable" — FALSE, and caught only by running 0.86/0.00 before
    committing. short-only is +$76.37 @0.86 and +$101.58 @0.00.)

 2. DOING NOTHING BEAT EVERY ARM AT EVERY SLIPPAGE. Shorting the same 13 coins
    $50 each and holding the whole 438d earned +$324 — and it is essentially
    SLIPPAGE-INDEPENDENT (+$323.65 @5bps -> +$324.02 @0bps) because it pays the
    spread ONCE, not 3,778 times. The BEST sleeve (+$101.58, short-only,
    frictionless) is still 3.2x worse. georgia's activity destroys 69-126% of a
    bear move that was free to anyone who placed one trade and left.

 3. THE BEAR IS ON A TIMESCALE GEORGIA CANNOT REACH. BTC fell 32.9% over the
    tape — but that is only 0.0157% of drift inside georgia's MEDIAN 248-min
    hold. Round-trip friction is 0.1000% @5bps (6.4x the drift) and 0.0172%
    @0.86bps (1.1x). At every non-zero slippage tested, friction >= drift.
    A 15m bot cannot harvest a 14-month move; it pays more than the move is
    worth at that horizon. THIS IS A FACT ABOUT THE TAPE, not the strategy.

 4. DIRECTION WAS NEVER THE PROBLEM — THE PAYOFF STRUCTURE IS. The long arm is
    RIGHT nearly half the time (wr 49.7% frictionless) and still loses; the
    short tags range_off (62.5% wr) and fade_rally (64.2% wr) are ~flat despite
    winning ~2 of every 3 trades. Winning more often than you lose and still
    bleeding is the signature of an ROI ladder that CAPS winners (1.8% decaying
    to 0.5%) below what the 2.5xATR trailing stop risks. A mirror inherits the
    SAME broken payoff on the other side — which is why direction cannot be the
    "winning factor" being looked for. Fix the payoff before adding sleeves.

 5. FUNDING IS IRRELEVANT AT THIS HOLDING PERIOD. Shorts earned +$5.12 across
    3,773 trades = $0.0014/trade. Flipping long->short swings funding by <3c on
    a $50 clip at the 24h MAX hold (measured, per-coin: SOL 0.0% .. ETH 10.5%).
    Funding is the Funding Farmer's whole edge because it holds for DAYS;
    georgia holds for HOURS. Do not reach for funding to rescue this.

 6. THE TAPE IS SINGLE-REGIME. 438d, BTC -32.9%, risk-off 61.5%, and 0% risk-on
    in Nov-25/Dec-25/Feb-26/Jun-26. "Positive in both halves" is TOOTHLESS here
    — both halves fall. Under the 17-Jul Lighter-only rule EVERY directional
    backtest this fleet can run is a bear-market backtest. That cost is bigger
    than CLAUDE.md prices it (it counts the LENGTH loss, 14mo vs 2.7yr, not the
    REGIME loss). Lighter's equity/commodity books are the only fix that stays
    on-venue: SPY +8.1%, QQQ +12.2%, IWM +13.4%, WTI +23.0%, NVDA +11.8% over
    their listed windows while BTC fell 32.9%. See §NEXT.

THE NULL — is the sleeve's P&L edge, or just the bear market?
    Random-entry shorts (same coins/durations/stakes) LOSE -$147.83.
    The real sleeve's -$85.62 sits at the 92.5th pct (z=+1.39) unrestricted and
    88.2nd (z=+1.21) with entries restricted to RISK-OFF bars (which holds the
    regime gate constant, so only entry TIMING is being tested).
    -> better than random, NOT significant at the 95% bar, and negative anyway.
    Beating a coin flip while losing money is not an edge.

METHOD / FIDELITY (why you may believe the control):
  * LIGHTER ONLY, per the 17-Jul operator rule. Every candle is Lighter's own
    (`venues/lighter_client.candles`); no HL, no Binance. 438d is the whole tape
    (probed: 600d returns 0 bars).
  * The CONTROL IS THE SHIPPED CODE — `DayTraderGated` imported from
    lighter_family_bot.py, not a paraphrase. Its real ATR ratchet, ROI ladder,
    custom_exit timeouts, 4-candle cooldown and 2/hr throttle all apply.
  * WINDOWING IS FIDELITY, NOT A SHORTCUT: the live loop feeds signals() a
    rolling 300-bar window (CandleCache.SPAN_BARS["15m"]=300) and the regime
    gate a 280-bar 4h window. An EMA200 seeded from 280 bars still carries ~45%
    of its seed, so computing the regime over FULL history would produce a
    DIFFERENT gate than the one georgia actually reads. We match the live span.
  * THE MIRROR IS PROVEN EXACT, not asserted. Every rule is linear in price, so
    reflecting a real window about a constant (c'=2P0-c, highs/lows swapped)
    must map each long rule onto its short mirror. --selftest checks 2,258
    real-tape cases: 0 entry mismatches, 0 exit mismatches. It also MUTATES the
    mirror 4 ways (zone, cover, tick, EMA side) and REQUIRES each to be caught
    — a green test that cannot go red is worth nothing.
  * Exit-mix sanity vs the LIVE ledger: replay 67% trailing-stop / 22% roi;
    live georgia (n=12) 67% / 33%.

KNOWN LIMITS — do not launder these away:
  * Slippage is the verdict (see banner). Flat per-side bps; Lighter's real
    slippage is PER-BOOK and unmeasured ([[lighter-slippage-is-per-book-not-
    per-venue]]).
  * Funding uses each coin's CURRENT measured APR held constant across 438d
    (the settled per-hour series was not paginated). Robust here only because
    finding 5 shows funding is ~$0.0014/trade at this horizon; do NOT reuse this
    shortcut for a bot that holds for days.
  * No fleet_long_veto / brain stake-mults (both are live-learned; applying them
    to a backtest is look-ahead). Backtests are inert — no DATABASE_URL.
  * Single-regime tape (finding 6). Says nothing about a bull market.

§NEXT — what would actually settle this, in order:
  1. MEASURE LIGHTER'S SLIPPAGE off the live fills. The Funding Farmer + Ticket
     Taker have real fills on the books RIGHT NOW and 0 of 57 have ever been
     read. That single measurement decides this study's sign — it is worth more
     than any further backtesting. [[real-fills-have-never-been-measured]]
  2. Then re-run this script. If real slippage is nearer 0.86 than 5.00, the
     sleeve HELPS and earns a SHADOW slot (never live off a backtest).
  3. Separately: georgia's payoff structure (finding 4) is the bigger lead than
     direction. Test ROI-ladder vs stop-distance BEFORE testing more sleeves.
  4. The per-asset regime gate: georgia's gate is BTC's 4h EMA50/200. Pointing
     it at SPY/XAU/WTI is incoherent (it reads risk-off 61.5% while SPY rose
     8.1%). Fix the gate BEFORE widening the universe, or every non-crypto trade
     is graded through BTC's mood.

USAGE:
    python3 scripts/backtest_georgia_short_sleeve.py --selftest   # mirror proof
    python3 scripts/backtest_georgia_short_sleeve.py --fetch      # cache tape
    python3 scripts/backtest_georgia_short_sleeve.py --study      # arms + nulls
    python3 scripts/backtest_georgia_short_sleeve.py --sweep      # slippage
"""

import argparse
import bisect
import json
import os
import random
import statistics as st
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lighter_family_bot import (DayTraderGated, ema_series, atr_series,   # noqa: E402
                                adx_series, roll_max, roll_min)

# VENUE PURITY: Lighter only, per the 17-Jul operator rule. The venue we trade
# is the venue we measure. No hyperliquid/binance import exists in this file by
# construction — the tape comes from venues/lighter_client.candles.
CACHE = os.environ.get("GEORGIA_TAPE_CACHE", "/tmp/georgia_tape")

import json, os, sys
sys.path.insert(0, "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot")
from lighter_family_bot import (DayTraderGated, ema_series, atr_series,
                                adx_series, roll_max, roll_min)


COINS = "BTC,ETH,SOL,XRP,ADA,DOT,AVAX,LINK,LTC,NEAR,TRX,DOGE,AAVE".split(",")
STAKE = 50.0
MAX_OPEN = 5
MAX_ENTRIES_PER_HOUR = 2
TF_S = 15 * 60

# live Lighter APR (%) measured 17-Jul from the market scout's lighter-market
FUNDING_APR = {"BTC": 0.9, "ETH": 10.5, "SOL": 0.0, "XRP": 3.5, "ADA": 5.3,
               "DOT": 10.5, "AVAX": 7.0, "LINK": 10.5, "LTC": 10.5,
               "NEAR": 10.5, "TRX": -10.5, "DOGE": 10.5, "AAVE": 10.5}

S = DayTraderGated("freqtrade-georgia", tf="15m", stoploss=-0.05,
                   max_open=MAX_OPEN, style="daytrader-15m")


def load(coin, interval="15m"):
    p = f"{CACHE}/{coin}_{interval}.json"
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


_REG = None         # regime cache — identical across runs
SPAN_15M = 300      # CandleCache.SPAN_BARS["15m"] — what the live loop feeds
SPAN_4H = 280       # CandleCache.SPAN_BARS["4h"]


def regime_series(btc4h):
    """BTC 4h EMA50>EMA200 per bar — the real btc_regime_up, computed the way
    the LIVE loop computes it: over a rolling SPAN_4H window, not full history.
    This is not a shortcut. EMA200 seeded from a 280-bar window still carries
    ~45% of its seed, so a full-history EMA200 would be a DIFFERENT number than
    the one the live gate actually reads."""
    out = []
    for i in range(len(btc4h)):
        w = btc4h[max(0, i - SPAN_4H + 1):i + 1]
        if len(w) < 210:                       # btc_regime_up's own floor
            out.append((btc4h[i][0], False))   # fail-safe 0
            continue
        c = [b[4] for b in w]
        e50, e200 = ema_series(c, 50), ema_series(c, 200)
        out.append((btc4h[i][0],
                    bool(e50[-1] and e200[-1] and e50[-1] > e200[-1])))
    return out


def regime_at(reg, ts):
    """Last CLOSED 4h regime bar at or before ts. Fail-safe False."""
    lo, hi, ans = 0, len(reg) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if reg[mid][0] <= ts:
            ans = reg[mid][1]; lo = mid + 1
        else:
            hi = mid - 1
    return bool(ans) if ans is not None else False


def short_signals(bars, extra):
    """The TRUE MIRROR of DayTraderGated.signals — every rule reflected.
    long buys bottom 37% of the band in an up regime; short sells the top 37%
    in a down regime. Zones, gates, ADX, EMA side, tick and band all mirrored."""
    c, h, l, v = bars["c"], bars["h"], bars["l"], bars["v"]
    if len(c) < S.min_bars:
        return None
    i = len(c) - 1
    e50 = ema_series(c, 50)
    atr = atr_series(h, l, c, 14)
    adx = adx_series(h, l, c, 14)
    if e50[i] is None or atr[i] is None or i < 21:
        return None
    rng_hi = roll_max(h, 14, i - 1)
    rng_lo = roll_min(l, 14, i - 1)
    if rng_hi is None or rng_lo is None:
        return None
    band = max(rng_hi - rng_lo, 1e-9)
    short_zone = rng_hi - 0.37 * band       # mirror of buy_zone
    cover_zone = rng_lo + 0.22 * band       # mirror of sell_zone
    band_pct = band / max(c[i], 1e-9)
    dc20_lo = roll_min(l, 20, i - 1)        # mirror of dc_high20
    downtick = c[i] < c[i - 1]
    live_vol = v[i] > 0
    e50_falling = e50[i - 6] is not None and e50[i] < e50[i - 6]
    regime_up = bool(extra.get("btc_regime_up"))

    tag = None
    if (not regime_up and c[i] >= short_zone and band_pct >= S.BAND_PCT_ON
            and c[i] < e50[i] and downtick and live_vol):
        tag = "range_off"                   # mirror: range_on
    if (regime_up and c[i] >= short_zone and c[i] < e50[i] and e50_falling
            and band_pct >= S.BAND_PCT_OFF and downtick and live_vol):
        tag = "fade_rally"                  # mirror: bounce_pullback
    if (adx[i] is not None and adx[i] >= 25 and c[i] < e50[i]
            and dc20_lo is not None and c[i] < dc20_lo
            and band_pct >= S.BAND_PCT_ON and live_vol):
        tag = "trend_breakdown"             # mirror: trend_breakout
    exit_ = (c[i] <= cover_zone and live_vol)
    return {"enter": tag, "exit": exit_, "exit_reason": "range_bottom",
            "atr": atr[i]}


def short_stake_mult(tag):
    return 0.5 if tag in ("fade_rally",) else 1.0   # mirror of bounce_pullback


def short_stop_dist(tag, atr, px):
    mult = 3.5 if tag in ("fade_rally",) else 2.5   # mirror
    if not atr or not px:
        return -S.stoploss
    return min(mult * atr / px, -S.stoploss)


def short_custom_exit(tag, age_min, profit):
    if tag == "fade_rally":
        if profit >= 0.012:
            return "fade_take"
        if age_min >= 720:
            return "fade_timeout"
    if age_min >= 1440:
        return "max_hold_timeout"
    return None


def run(mode, slip_bps, with_funding=True, coins=None, window=None):
    """mode: 'long' (shipped control) | 'mirror' (long+short) | 'short'.
    Bar-by-bar over the union timeline; entries only on a closed candle, the
    same rule the live loop uses (new_candle)."""
    coins = coins or COINS
    global _REG
    if _REG is None:
        _REG = regime_series(load("BTC", "4h"))
    reg = _REG
    series = {}
    for c in coins:
        s = load(c)
        if s:
            series[c] = s
    if not series:
        raise SystemExit("no tape cached")

    ts_all = sorted({b[0] for s in series.values() for b in s})
    # UNIT GUARD — this file had a ms/s bug that silently made every trade a
    # 1-bar hold (age_min 1000x too big -> instant max_hold_timeout) and
    # disabled both the cooldown and the 2/hr throttle. Never again silently.
    assert ts_all[0] > 1e12, "tape timestamps must be MILLISECONDS"
    assert abs((ts_all[1] - ts_all[0]) / 60000.0 - 15.0) < 1e-6, \
        "one bar must be 15 real minutes under the ms convention"
    if window:
        ts_all = [t for t in ts_all if window[0] <= t < window[1]]
    idx = {c: {b[0]: k for k, b in enumerate(s)} for c, s in series.items()}

    pos, meta, cooldown, closes = {}, {}, {}, []
    entry_times = []
    slip = slip_bps / 10000.0

    for t in ts_all:
        # ---- manage open positions ----
        for coin in list(pos):
            s, k = series[coin], idx[coin].get(t)
            if k is None or k < S.min_bars:
                continue
            px = s[k][4]
            m = meta[coin]
            side = m["side"]
            entry = m["entry"]
            age_min = (t - m["opened_ts"]) / 60000.0      # t is MILLISECONDS
            profit = (px - entry) / entry if side == "long" else (entry - px) / entry
            if with_funding:
                apr = FUNDING_APR.get(coin, 0.0) / 100.0
                hourly = apr / 365.0 / 24.0
                sgn = -1.0 if side == "long" else 1.0
                m["accrued"] += sgn * hourly * m["sz"] * px * (TF_S / 3600.0)

            w = s[max(0, k - SPAN_15M + 1):k + 1]
            bars = {"c": [b[4] for b in w], "h": [b[2] for b in w],
                    "l": [b[3] for b in w], "v": [b[5] for b in w]}
            reason = None
            # trailing ATR ratchet — long ratchets UP, short ratchets DOWN
            if side == "long":
                sig = S.signals(bars, {"btc_regime_up": regime_at(reg, t)})
                dist = S.atr_stop_dist(m["tag"], bars, px)
                m["stop_px"] = max(m.get("stop_px") or 0.0, px * (1 - dist))
                if px <= m["stop_px"]:
                    reason = "trailing_stop_loss"
            else:
                sig = short_signals(bars, {"btc_regime_up": regime_at(reg, t)})
                dist = short_stop_dist(m["tag"], (sig or {}).get("atr"), px)
                cap = m.get("stop_px") or float("inf")
                m["stop_px"] = min(cap, px * (1 + dist))
                if px >= m["stop_px"]:
                    reason = "trailing_stop_loss"
            if not reason and S.roi:
                rung = max((k2 for k2 in S.roi if k2 <= age_min), default=None)
                if rung is not None and profit >= S.roi[rung]:
                    reason = "roi"
            if not reason:
                reason = (S.custom_exit(m["tag"], age_min, profit) if side == "long"
                          else short_custom_exit(m["tag"], age_min, profit))
            if not reason and sig and sig.get("exit") and \
                    m["tag"] not in ("trend_breakout", "trend_breakdown"):
                reason = sig.get("exit_reason", "exit_signal")

            if reason:
                exit_px = px * (1 - slip) if side == "long" else px * (1 + slip)
                gross = ((exit_px - entry) if side == "long" else (entry - exit_px)) * m["sz"]
                pnl = gross + m["accrued"]
                closes.append({"coin": coin, "side": side, "tag": m["tag"],
                               "reason": f"{side}-{m['tag']}_{reason}",
                               "pnl": pnl, "pnl_pct": pnl / (m["sz"] * entry),
                               "funding": m["accrued"], "opened": m["opened_ts"],
                               "closed": t, "age_min": age_min,
                               "sz_stake": m["sz"] * entry})
                cooldown[coin] = t + S.protections["cooldown_candles"] * TF_S * 1000
                del pos[coin], meta[coin]

        # ---- entries (closed candle only) ----
        for coin in coins:
            if coin in pos or coin not in series:
                continue
            s, k = series[coin], idx[coin].get(t)
            if k is None or k < S.min_bars:
                continue
            if len(pos) >= MAX_OPEN or t < cooldown.get(coin, 0):
                continue
            entry_times[:] = [x for x in entry_times if t - x < 3600_000]   # 1h in ms
            if len(entry_times) >= MAX_ENTRIES_PER_HOUR:
                continue
            w = s[max(0, k - SPAN_15M + 1):k + 1]
            bars = {"c": [b[4] for b in w], "h": [b[2] for b in w],
                    "l": [b[3] for b in w], "v": [b[5] for b in w]}
            rup = regime_at(reg, t)
            cand = []
            if mode in ("long", "mirror"):
                sl = S.signals(bars, {"btc_regime_up": rup})
                if sl and sl.get("enter"):
                    cand.append(("long", sl["enter"], sl.get("atr")))
            if mode in ("short", "mirror"):
                ss = short_signals(bars, {"btc_regime_up": rup})
                if ss and ss.get("enter"):
                    cand.append(("short", ss["enter"], ss.get("atr")))
            if not cand:
                continue
            side, tag, atr = cand[0]      # long wins a tie (control-preserving)
            px = s[k][4]
            mult = (S.stake_mult(tag, bars) if side == "long"
                    else short_stake_mult(tag))
            stake = STAKE * mult
            entry_px = px * (1 + slip) if side == "long" else px * (1 - slip)
            sz = stake / entry_px
            dist = (S.atr_stop_dist(tag, bars, entry_px) if side == "long"
                    else short_stop_dist(tag, atr, entry_px))
            stop_px = entry_px * (1 - dist) if side == "long" else entry_px * (1 + dist)
            pos[coin] = True
            meta[coin] = {"side": side, "tag": tag, "entry": entry_px, "sz": sz,
                          "opened_ts": t, "accrued": 0.0, "stop_px": stop_px}
            entry_times.append(t)
    return closes


def grade(closes, label):
    if not closes:
        return {"label": label, "n": 0, "pnl": 0.0, "wr": 0.0, "avg": 0.0}
    n = len(closes)
    pnl = sum(c["pnl"] for c in closes)
    wins = sum(1 for c in closes if c["pnl"] > 0)
    fund = sum(c["funding"] for c in closes)
    return {"label": label, "n": n, "pnl": pnl, "wr": wins / n,
            "avg": pnl / n, "avg_pct": sum(c["pnl_pct"] for c in closes) / n * 100,
            "funding": fund}


def halves(closes):
    if not closes:
        return [], []
    ts = sorted(c["closed"] for c in closes)
    mid = ts[len(ts) // 2]
    return ([c for c in closes if c["closed"] < mid],
            [c for c in closes if c["closed"] >= mid])


def fmt(g):
    if g["n"] == 0:
        return f"  {g['label']:22s}  n=0 (no trades)"
    return (f"  {g['label']:22s}  n={g['n']:>4d}  pnl=${g['pnl']:>9.2f}  "
            f"wr={g['wr']*100:>5.1f}%  avg=${g['avg']:>6.3f} ({g['avg_pct']:>6.3f}%)  "
            f"fund=${g['funding']:>7.2f}")


def maxdd(closes):
    """Max drawdown of the $1,000 book on the closed-trade equity curve."""
    if not closes:
        return 0.0
    eq, peak, dd = 1000.0, 1000.0, 0.0
    for c in sorted(closes, key=lambda x: x["closed"]):
        eq += c["pnl"]
        peak = max(peak, eq)
        dd = min(dd, (eq - peak) / peak)
    return dd


# --------------------------------------------------------------------------
# NULLS — drift vs edge



def passive_short(coins, slip_bps=5.0, stake=50.0, with_funding=True):
    """Short `stake` of each coin at the first bar, cover at the last."""
    slip = slip_bps / 10000.0
    total, rows = 0.0, []
    for c in coins:
        s = load(c)
        if not s:
            continue
        entry = s[0][4] * (1 - slip)
        exit_ = s[-1][4] * (1 + slip)
        sz = stake / entry
        pnl = (entry - exit_) * sz
        if with_funding:
            hours = (s[-1][0] - s[0][0]) / 3600000.0
            pnl += (FUNDING_APR.get(c, 0.0)/100.0)/365.0/24.0 * sz * entry * hours
        rows.append((c, pnl, (s[-1][4]/s[0][4]-1)*100))
        total += pnl
    return total, rows


def null_shorts(real_closes, slip_bps=5.0, iters=400, seed=7):
    """Resample the sleeve's own (coin, duration, stake) at RANDOM entry times."""
    rnd = random.Random(seed)
    slip = slip_bps / 10000.0
    tapes = {}
    for c in {x["coin"] for x in real_closes}:
        s = load(c)
        if s:
            tapes[c] = s
    spec = [(x["coin"], max(1, int(x["age_min"]*60/TF_S)), x["sz_stake"])
            for x in real_closes if x["coin"] in tapes]
    if not spec:
        return []
    out = []
    for _ in range(iters):
        tot = 0.0
        for coin, nbars, stake in spec:
            s = tapes[coin]
            if len(s) <= nbars + 2:
                continue
            k = rnd.randrange(0, len(s) - nbars - 1)
            e = s[k][4] * (1 - slip)
            x = s[k+nbars][4] * (1 + slip)
            sz = stake / e
            pnl = (e - x) * sz
            hours = nbars * TF_S / 3600.0
            pnl += (FUNDING_APR.get(coin, 0.0)/100.0)/365.0/24.0 * sz * e * hours
            tot += pnl
        out.append(tot)
    return out


def pctile(dist, v):
    if not dist:
        return float("nan")
    return 100.0 * sum(1 for d in dist if d < v) / len(dist)


def report_null(real_pnl, dist, label):
    if not dist:
        print(f"  {label}: null unavailable"); return
    mu, sd = st.mean(dist), (st.pstdev(dist) or 1e-9)
    p = pctile(dist, real_pnl)
    z = (real_pnl - mu) / sd
    print(f"  {label}")
    print(f"    real sleeve      ${real_pnl:>9.2f}")
    print(f"    null mean        ${mu:>9.2f}   (random-entry shorts, same "
          f"coins/durations/stakes)")
    print(f"    null sd          ${sd:>9.2f}   5-95%: ${sorted(dist)[len(dist)//20]:.2f} "
          f".. ${sorted(dist)[int(len(dist)*0.95)]:.2f}")
    print(f"    percentile       {p:>9.1f}%   z={z:+.2f}")
    # A HARD p>=95 CUT WOULD MAKE THIS FUNCTION THE AUTHOR OF THE VERDICT.
    # Measured 17-Jul @0.86bps, the SAME sleeve landed at 94.2 (NULL A) and
    # 95.0 (NULL B) — a bare threshold prints "NO EDGE" and "EDGE" for one
    # strategy, and a later reader quotes whichever suits. Two nulls of the
    # same thing straddling the line IS the result: borderline. So say so,
    # and never let a knife-edge read as a clean verdict. (Same disease as
    # the assumed-5bps headline that got backtest_funding_lighter.py's
    # verdict withdrawn: a decision resting on a number nobody pinned.)
    if p >= 97.5:
        verdict = "EDGE: timing beats random"
    elif p >= 90:
        verdict = (f"BORDERLINE ({p:.1f}th pct) — NOT an edge. Straddles the "
                   f"bar; needs the slippage MEASURED, not another replay")
    elif p > 5:
        verdict = "NO EDGE: inside the null — this is DRIFT, not skill"
    else:
        verdict = "WORSE than random entry"
    if real_pnl < 0 and p >= 90:
        verdict += " (and NEGATIVE anyway — beating a coin flip while losing "
        verdict += "money is not an edge)"
    print(f"    verdict          {verdict}")


def null_shorts_regime_matched(real_closes, reg, regime_at, slip_bps=5.0,
                               iters=400, seed=11, want_up=False):
    """Random-entry shorts restricted to bars whose regime matches the sleeve's
    hunting ground (risk-OFF by default).

    WHY THIS ONE DECIDES IT: the unrestricted null lets the sleeve 'win' merely
    by only shorting in downtrends — but that is the REGIME GATE's doing, not
    the range logic's. Matching the regime holds the gate constant, so whatever
    is left is the entry timing the range rules actually contribute."""
    rnd = random.Random(seed)
    slip = slip_bps / 10000.0
    tapes, ok_idx = {}, {}
    for c in {x["coin"] for x in real_closes}:
        s = load(c)
        if not s:
            continue
        tapes[c] = s
        ok_idx[c] = [k for k, b in enumerate(s) if regime_at(reg, b[0]) == want_up]
    spec = [(x["coin"], max(1, int(x["age_min"]*60/TF_S)), x["sz_stake"])
            for x in real_closes if x["coin"] in tapes]
    out = []
    for _ in range(iters):
        tot = 0.0
        for coin, nbars, stake in spec:
            s, cand = tapes[coin], ok_idx.get(coin) or []
            # ok_idx is sorted, so valid k (k+nbars+1 < len) is a PREFIX:
            # bisect once instead of rebuilding the list 120k times.
            hi = bisect.bisect_left(cand, len(s) - nbars - 1)
            if hi <= 0:
                continue
            k = cand[rnd.randrange(hi)]
            e = s[k][4] * (1 - slip)
            x = s[k+nbars][4] * (1 + slip)
            sz = stake / e
            pnl = (e - x) * sz
            pnl += (FUNDING_APR.get(coin, 0.0)/100.0)/365.0/24.0 * sz * e * \
                   (nbars * TF_S / 3600.0)
            tot += pnl
        out.append(tot)
    return out



# ---------------------------------------------------------------------------
# TAPE — Lighter's own candles, cached. 438d is the WHOLE tape (600d -> 0 bars).

def fetch_tape(days=438):
    """Cache Lighter's own 15m tape for georgia's universe + the BTC 4h regime.

    NOTE ON RATE: venues/governor.py gives a process 60*LIGHTER_BUDGET_SHARE
    weighted req/min and the default share is 0.35 (=21/min), which makes a
    ~1,100-call backfill take ~53min. This is READ-ONLY, unauthenticated public
    market data from a laptop (no signer, no account), so it does not spend the
    live bots' account budget; raising the share to 1.0 keeps it inside
    Lighter's own documented 60/min ceiling:
        LIGHTER_BUDGET_SHARE=1.0 python3 scripts/backtest_georgia_short_sleeve.py --fetch
    """
    from venues.lighter_client import LighterClient
    os.makedirs(CACHE, exist_ok=True)
    c = LighterClient()
    try:
        for coin in COINS:
            _fetch_series(c, coin, "15m", days)
        _fetch_series(c, "BTC", "4h", days)
    finally:
        c.close()
    return 0


def _fetch_series(c, coin, interval, days):
    path = f"{CACHE}/{coin}_{interval}.json"
    if os.path.exists(path):
        print(f"{coin:6s} {interval:3s} cached")
        return json.load(open(path))
    ims = {"15m": 15 * 60 * 1000, "4h": 4 * 3600 * 1000}[interval]
    now = int(time.time() * 1000)
    cur, out = now - days * 86400 * 1000, {}
    while cur < now:
        end = min(cur + 500 * ims, now)
        rr = None
        for attempt in range(4):
            try:
                rr = c.candles(coin, interval, cur, end)
                break
            except Exception as e:                              # noqa: BLE001
                if attempt == 3:
                    print(f"  {coin} {interval} @{cur} failed: {e}")
                else:
                    time.sleep(1.5 * (attempt + 1))
        if not rr:
            cur = end
            continue
        for b in rr:
            out[int(b["t"])] = [float(b["o"]), float(b["h"]), float(b["l"]),
                                float(b["c"]), float(b.get("v") or 0.0)]
        nxt = max(out) + ims
        cur = nxt if nxt > cur else end
    ser = [[t] + out[t] for t in sorted(out)]
    json.dump(ser, open(path, "w"))
    d = lambda ms: dt.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
    print(f"{coin:6s} {interval:3s} {len(ser):6d} bars  {d(ser[0][0])} -> {d(ser[-1][0])}")
    return ser


def _have():
    return [c for c in COINS if load(c)]


def study(slip=5.0):
    """The three arms + the drift-vs-edge nulls."""
    global _REG
    have = _have()
    if not have:
        raise SystemExit("no tape cached — run --fetch first")
    _REG = regime_series(load("BTC", "4h"))
    up = sum(1 for _, r in _REG if r)
    b = load("BTC")
    print(f"universe {len(have)}/{len(COINS)}: {','.join(have)}")
    print(f"regime: risk-on {up/len(_REG)*100:.1f}% | risk-off {(len(_REG)-up)/len(_REG)*100:.1f}%")
    print(f"BTC over window: {b[0][4]:.0f} -> {b[-1][4]:.0f} "
          f"({(b[-1][4]/b[0][4]-1)*100:+.1f}%)  <-- SINGLE-REGIME (bear) tape")

    arms = {}
    for mode, label in (("long", "CONTROL long-only"), ("mirror", "MIRROR long+short"),
                        ("short", "SHORT sleeve only")):
        arms[mode] = run(mode, slip, coins=have)
        print(fmt(grade(arms[mode], label)) + f"  maxDD={maxdd(arms[mode])*100:>6.2f}%")
        h1, h2 = halves(arms[mode])
        print("    " + fmt(grade(h1, "1st half")).strip())
        print("    " + fmt(grade(h2, "2nd half")).strip())
        print("    NOTE: both halves FALL on this tape — 'positive in both "
              "halves' proves nothing about direction here.")

    shorts = [c for c in arms["short"] if c["side"] == "short"]
    print("\nSHORT SLEEVE BY TAG")
    by = {}
    for c in shorts:
        by.setdefault(c["tag"], []).append(c)
    for tag, rr in sorted(by.items(), key=lambda x: -sum(c["pnl"] for c in x[1])):
        print(fmt(grade(rr, tag)))

    print("\nIS IT EDGE, OR IS IT JUST THE BEAR MARKET?")
    real = sum(c["pnl"] for c in shorts)
    pas, _ = passive_short(have, slip)
    print(f"  PASSIVE short-and-hold (pays the spread ONCE): ${pas:.2f}")
    print(f"  SHORT sleeve (pays it {len(shorts)} times)   : ${real:.2f}")
    report_null(real, null_shorts(shorts, slip),
                "NULL A - random entry, anywhere on the tape")
    print()
    report_null(real, null_shorts_regime_matched(shorts, _REG, regime_at, slip),
                "NULL B - random entry, RISK-OFF bars only (regime gate held constant)")
    return 0


def sweep():
    """Slippage is the verdict — so sweep it. See the banner."""
    global _REG
    have = _have()
    _REG = regime_series(load("BTC", "4h"))
    print(f"{'slip/side':>10s} | {'CONTROL long':>22s} | {'MIRROR':>22s} | {'SHORT only':>22s} | {'passive':>9s}")
    for slip in (5.0, 2.0, 0.86, 0.0):
        row = f"{slip:>10.2f} |"
        for mode in ("long", "mirror", "short"):
            g = grade(run(mode, slip, coins=have), mode)
            row += f" n={g['n']:>4d} ${g['pnl']:>8.2f} |"
        pas, _ = passive_short(have, slip)
        print(row + f" ${pas:>8.2f}")
    return 0


# ---------------------------------------------------------------------------
# SELFTEST — the mirror invariant + its negative fixture.
# A green test that cannot go red is worth nothing, so every injected mirror
# bug MUST be caught. See [[adversarial-verify-3-lens]] / [[stubs-encode-the-
# assumption-under-test]].

_MAP = {"range_on": "range_off", "bounce_pullback": "fade_rally",
        "trend_breakout": "trend_breakdown"}


def _reflect(bars, P0):
    """Arithmetic reflection about P0. Every rule in the strategy is linear in
    price, so this maps each long rule EXACTLY onto its short mirror: highs and
    lows swap, EMA/ATR/ADX are invariant, and reflecting about P0=c[i] keeps
    band_pct exact too. The match must therefore be PERFECT."""
    return {"c": [2 * P0 - x for x in bars["c"]],
            "h": [2 * P0 - x for x in bars["l"]],
            "l": [2 * P0 - x for x in bars["h"]],
            "v": list(bars["v"])}


def _window(s, k):
    w = s[max(0, k - SPAN_15M + 1):k + 1]
    return {"c": [b[4] for b in w], "h": [b[2] for b in w],
            "l": [b[3] for b in w], "v": [b[5] for b in w]}


def _check_mirror(tape, short_fn, step=37):
    mm = fired = 0
    for k in range(SPAN_15M, len(tape), step):
        bars = _window(tape, k)
        refl = _reflect(bars, bars["c"][-1])
        for rup in (True, False):
            sl = S.signals(bars, {"btc_regime_up": rup})
            ss = short_fn(refl, {"btc_regime_up": not rup})
            if sl is None or ss is None:
                continue
            if sl.get("enter"):
                fired += 1
            if _MAP.get(sl.get("enter")) != ss.get("enter"):
                mm += 1
            if bool(sl.get("exit")) != bool(ss.get("exit")):
                mm += 1
    return mm, fired


def selftest():
    tape = load("BTC")
    if not tape:
        raise SystemExit("selftest needs the BTC tape: run --fetch first")
    mm, fired = _check_mirror(tape, short_signals)
    print(f"mirror invariant on {len(tape)} real bars: mismatches={mm} "
          f"(long entries exercised={fired})")
    ok = (mm == 0 and fired > 0)   # fired>0 => not vacuously green
    print("  mirror EXACT" if ok else "  MIRROR BROKEN or test vacuous")

    # negative fixture: break the mirror 4 ways; each MUST be caught
    def mutant(zone=0.37, cover=0.22, downtick=True, lt=True):
        def f(bars, extra):
            r = short_signals(bars, extra)
            if r is None:
                return None
            c, h, l, v = bars["c"], bars["h"], bars["l"], bars["v"]
            i = len(c) - 1
            rng_hi, rng_lo = roll_max(h, 14, i - 1), roll_min(l, 14, i - 1)
            if rng_hi is None or rng_lo is None:
                return r
            band = max(rng_hi - rng_lo, 1e-9)
            e50 = ema_series(c, 50)
            sz, cz = rng_hi - zone * band, rng_lo + cover * band
            tick = (c[i] < c[i - 1]) if downtick else (c[i] > c[i - 1])
            side = (c[i] < e50[i]) if lt else (c[i] > e50[i])
            tag = r["enter"]
            if tag and not (c[i] >= sz and tick and side):
                tag = None
            return {"enter": tag, "exit": (c[i] <= cz and v[i] > 0),
                    "atr": r["atr"]}
        return f

    print("negative fixture — each injected bug MUST be caught:")
    allok = ok
    for name, fn in (("zone 0.37->0.30", mutant(zone=0.30)),
                     ("cover 0.22->0.30", mutant(cover=0.30)),
                     ("downtick->uptick", mutant(downtick=False)),
                     ("ema side flipped", mutant(lt=False))):
        m, _ = _check_mirror(tape, fn)
        caught = m > 0
        allok &= caught
        print(f"  {name:22s} mismatches={m:>4d}  {'CAUGHT' if caught else 'MISSED — TEST IS BLIND'}")
    print("\nSELFTEST", "PASS" if allok else "FAIL")
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--selftest", action="store_true",
                    help="mirror invariant + negative fixture (no network)")
    ap.add_argument("--fetch", action="store_true", help="cache Lighter's tape")
    ap.add_argument("--study", action="store_true", help="arms + drift-vs-edge nulls")
    ap.add_argument("--sweep", action="store_true", help="slippage sensitivity")
    ap.add_argument("--slip", type=float, default=5.0, help="per-side bps")
    ap.add_argument("--days", type=int, default=438, help="tape depth (whole tape)")
    a = ap.parse_args()

    if a.fetch:
        return fetch_tape(a.days)
    if a.selftest:
        return selftest()
    if a.study:
        return study(a.slip)
    if a.sweep:
        return sweep()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
