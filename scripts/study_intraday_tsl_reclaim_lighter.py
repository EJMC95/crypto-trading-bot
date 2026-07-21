#!/usr/bin/env python3
"""
scripts/study_intraday_tsl_reclaim_lighter.py — does the crypto-intraday-15m
book's trailing ATR stop fire on NOISE (the Kraken-era 'stop_too_tight'
signature), measured on LIGHTER'S OWN 1h tape?

Re-run to reproduce:
    python3 scripts/study_intraday_tsl_reclaim_lighter.py            # full study
    python3 scripts/study_intraday_tsl_reclaim_lighter.py --refresh  # refetch tape
    python3 scripts/study_intraday_tsl_reclaim_lighter.py --selftest # no network

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT (2026-07-21 run: 180d of Lighter 1h tape, 2026-01-22 ->           ║
║ 2026-07-21, 25 books; BTC -26% over the window, DOWN in BOTH halves       ║
║ (h1 -13%, h2 -15%), btc_regime_up on 37% of hours — a BEAR-TAPE result    ║
║ that says nothing about an up-tape).                                      ║
║                                                                           ║
║ 1. THE KRAKEN-ERA 'stop_too_tight' SIGNATURE DOES NOT REPRODUCE AT THE    ║
║    BRAIN'S BAR ON LIGHTER. Baseline sim (2.5x trend / 3.5x counter-       ║
║    trend, the shipped atr_stop_dist): 546 closed trades, 191 TSL exits,   ║
║    24h entry-reclaim 54% — UNDER the brain's 60% stop-too-tight bar and   ║
║    ABOVE its 35% stop-is-fine bar: the ambiguous zone, not the 77-89%     ║
║    the Kraken-era replay found. By tag: trend_breakout 57% (n=152),       ║
║    range_on 36% (n=25), bounce_pullback 64% (n=14). Halves: 48% / 61%.   ║
║ 2. THE 9 REAL LEDGER STOP-OUTS ARE UNDECIDABLE AT THE 24h BAR. With the   ║
║    entry-bar OPEN as the entry estimate 4/9 reclaimed within 24h; with    ║
║    the bar LOW it is 7/9 (the ledger stores NO entry price, so the fill   ║
║    was somewhere in that bar). The honest answer is a bracket             ║
║    [44%..78%] that STRADDLES the 60% bar. Every open-estimate miss did    ║
║    reclaim eventually (45-70h) — buying dips too early, not wrong-        ║
║    direction — but "eventually" is not the 24h contract.                  ║
║ 3. THE COUNTERFACTUAL FAILS THE BOTH-HALVES BAR AT BOTH WIDTHS.           ║
║      trend mult   full P&L      h1        h2     (fresh book per half)    ║
║        2.5x       -$50.24    -$26.05   -$24.56   <- shipped               ║
║        3.0x       -$42.41    -$32.59   -$10.20   h2 better, h1 WORSE      ║
║        3.5x       -$55.47    -$40.40   -$16.29   h2 better, h1 WORSE      ║
║    Wider stops convert stop-outs into DEEPER stop-outs (TSL P&L           ║
║    -$199.64 -> -$237.85) faster than they convert them into wins, and     ║
║    the improvement lives entirely in one half. Not one width improves     ║
║    both halves.                                                           ║
║ 4. THEREFORE: **NO CHANGE.** Keep atr_stop_dist at 2.5x/3.5x. And read    ║
║    what the sweep actually says: the book is net NEGATIVE at EVERY stop   ║
║    width tested (-$50/-$42/-$55 over 180d). The stop does not decide      ║
║    this book's sign — on a tape that is regime-up only 37% of hours,      ║
║    trend_breakout supplies 80% of the stop-outs and the bleed is ENTRY-   ║
║    side. That (and the missing entry_price telemetry that made item 2     ║
║    a bracket instead of a number) is the 21-Jul review item, not a        ║
║    wider ratchet.                                                         ║
╚══════════════════════════════════════════════════════════════════════════╝

PRECEDENT (grep 'reclaim' / 'stop_too_tight' / 'ratchet'):
  * 13-Jul manual post-exit replay (DayTraderV5Gated.py custom_stoploss note,
    lighter_family_bot.py atr_stop_dist note): 40 stop-outs, both carriers,
    77-89% reclaimed ENTRY within 24h, avg fwd drift POSITIVE -> the 2.0x
    counter-trend stop was widened to 3.5x. FLEET_REVIEW_2026-07-14.md: the
    mechanized re-derivation agreed (79-100%).
  * bot_learn.py `_post_exit_drift` / hypothesis 'stop_too_tight': the
    brain's rule fires at reclaim >= 0.6 (n >= 5), "stop is fine" at
    reclaim <= 0.35. Window = 24 x 1h bars after the exit, >= 6-bar floor,
    long semantics any(high >= entry). This study uses the SAME contract.

WHAT THIS RUNS. The crypto-intraday-15m carrier exactly as shipped in
lighter_family_bot.py (STRATEGIES row: DayTraderGated, tf=1h, stoploss=-0.12,
max_open=5, coins=WIDE_COINS): the real DayTraderGated class is IMPORTED and
its `signals` / `atr_stop_dist` are the source of truth — the vectorized sim
is cross-checked against those real methods on live tape every run (sampled
(coin, bar) prefixes must agree exactly; the run aborts if they don't).
Simulated per 1h bar over the Lighter tape: BTC-4h 50/200 EMA regime gate
(computed the live way, on a <=280-bar window like CandleCache), tag
assignment in .loc order (range_on / bounce_pullback / trend_breakout,
last match wins), entry at the NEXT bar's open, the trailing ATR ratchet
(stop_px = max(stop_px, px*(1-dist)), dist = min(mult*ATR14/px, 0.12),
mult 2.5 trend / 3.5 counter-trend), ROI ladder {0:1.8%,180:1.2%,360:0.8%,
720:0.5%}, bounce_take/bounce_timeout/max_hold_timeout, range_top exit
signal (vetoed for trend_breakout), cooldown 4 bars, StoplossGuard
(3 stops/48 bars -> 12 bars off), MaxDrawdown (10 trades/96 bars, 15% of
$1000 -> 24 bars off), 2-entries-per-hour book throttle, $50 stake
(0.5x for bounce_pullback).

VENUE PURITY: every price in this file is Lighter's own /api/v1/candles
(paged 500 bars/call, polite sleeps). No HL, no Binance, no Kraken.

LIMITATIONS — read before believing anything above:
  * SINGLE-REGIME TAPE. The 180d window is a bear tape (BTC down full-window
    and in both halves — the run prints the exact numbers). 'Both halves'
    here means two halves of ONE regime; a wider stop on an up-tape is
    untested and this file makes no claim about it.
  * 1h-BAR APPROXIMATION of a ~90s live loop. Intrabar convention, applied
    identically to every stop variant: trigger against the stop carried into
    the bar using the bar LOW; then ratchet on the bar HIGH; then exit if the
    CLOSE crossed back under the ratcheted stop (high-before-close is the
    only intrabar ordering that is certain). A same-bar low-after-high
    stop-out below the ratcheted level is seen one bar late; live would see
    it within 90s. ROI fills at the rung target when the bar high reaches it
    (rung chosen at bar-start age = conservative); stop beats ROI on a
    same-bar collision (live check order; same convention as
    backtest_funding_lighter.py).
  * FILLS/FEES: entries/exits at candle prices; the live ShadowBroker
    crosses the spread (bps-scale on these books). Funding drag is omitted:
    long-only $50 clips at even 20% APR cost <2c/day held — an order of
    magnitude under the per-trade deltas measured here. Both frictions hit
    every stop variant alike.
  * SIZING organs not reconstructable historically (market-pulse panic
    halving, brain stake mults, fleet drawdown governor) are omitted —
    sizing-only, variant-neutral. Daily-loss rail omitted (needs -$100/day
    on <= 5 x $50 positions; never plausible on this tape).
  * INDICATORS are computed from the tape start (prefix), while live
    computes on a rolling 380-bar fetch window. Seed influence on EMA50/
    ATR14/ADX14 after 300+ bars is ~e^-13 — negligible; the BTC-4h regime
    IS computed the live way (280-bar window, >=210-bar floor) because
    EMA200's seed does matter at that window length.
  * THE 9 REAL LEDGER STOP-OUTS carry no entry/exit price (ledger nulls), so
    entry is estimated as the candle OPEN of the hour nearest opened_at and
    the exit reference is the close of the hour containing closed_at. The
    reclaim verdict compares candle highs to that estimate — robust to
    within-bar noise, but it is an estimate, and it is labelled one.
  * The sim book starts flat at each window edge; half-window runs are
    independent fresh books (funding-backtest convention).
"""
import argparse
import bisect
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
# lighter_family_bot's import-time logging opens FAMILY_LOG_FILE — send the
# study's import to /dev/null instead of littering a bot log in the repo.
os.environ.setdefault("FAMILY_LOG_FILE", os.devnull)

from lighter_family_bot import (  # noqa: E402 — the REAL carrier code
    DayTraderGated, WIDE_COINS, ema_series, atr_series, adx_series,
    roll_max, roll_min)
from venues.symbol_map import to_lighter  # noqa: E402

B = "https://mainnet.zklighter.elliot.ai"
CACHE = os.path.join(_HERE, ".intraday_tsl_cache.json")
PAGE_SLEEP = 0.3          # polite paging
STAKE = 50.0              # FAMILY_STAKE_USD default
START_EQUITY = 1000.0

# The exact STRATEGIES row for this book (lighter_family_bot.py) — the class
# instance below is the source of truth for roi/protections/stop mechanics.
CARRIER = DayTraderGated("crypto-intraday-15m", tf="1h", stoploss=-0.12,
                         max_open=5, style="daytrader-1h",
                         coins=list(WIDE_COINS))
BASELINE_TREND_MULT = 2.5       # atr_stop_dist: 2.5x trend, 3.5x counter-trend
COUNTER_MULT = 3.5              # bounce_pullback/range_meanrev — never varied
SWEEP_TREND_MULTS = [2.5, 3.0, 3.5]

# The 9 realized trailing_stop_loss LOSSES on crypto-intraday-15m-lshadow as
# of 2026-07-21 (frozen from the paper ledger; opened epoch is embedded in
# each trade_id, so these are the bot's own timestamps, not re-typed ones).
REAL_TSL = [
    # (pair, opened_epoch, closed_at_iso, pnl_abs, tag-or-None)
    ("AVAX", 1783936787.378, "2026-07-13T16:22:03.511790+00:00", -0.535, None),
    ("BONK", 1784037618.801, "2026-07-14T18:19:12.085298+00:00", -0.851, None),
    ("ADA",  1784045070.252, "2026-07-14T18:30:29.220856+00:00", -0.463, None),
    ("APT",  1784041118.801, "2026-07-14T22:13:09.436778+00:00", -0.588, None),
    ("LINK", 1784228549.560, "2026-07-17T00:38:08.887995+00:00", -0.839, "range_on"),
    ("DOT",  1784271484.361, "2026-07-17T13:10:24.738250+00:00", -0.715, "range_on"),
    ("APT",  1784361509.023, "2026-07-18T12:27:33.730474+00:00", -0.437, "range_on"),
    ("ADA",  1784343484.951, "2026-07-18T13:19:10.875117+00:00", -0.647, "trend_breakout"),
    ("ARB",  1784365089.026, "2026-07-18T18:56:50.884711+00:00", -0.551, "range_on"),
]


# ---------------------------------------------------------------------------
# Lighter tape (venue-pure fetch, paged, cached)

def _get(path, **q):
    url = B + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def fetch_candles(mid, resolution, sec, days):
    """OHLCV paged backward (500-bar API cap) -> {open_ts_sec: (o,h,l,c,v)}."""
    out, end = {}, int(time.time())
    cutoff = end - days * 86400
    seen_oldest = None
    while True:
        rows = _get("/api/v1/candles", market_id=mid, resolution=resolution,
                    start_timestamp=end - 500 * sec, end_timestamp=end,
                    count_back=500).get("c") or []
        if not rows:
            break
        for c in rows:
            out[int(c["t"]) // 1000] = (
                float(c["o"]), float(c["h"]), float(c["l"]), float(c["c"]),
                float(c.get("v") or 0.0))
        oldest = min(int(c["t"]) // 1000 for c in rows)
        if oldest <= cutoff or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - sec
        time.sleep(PAGE_SLEEP)
    return {t: v for t, v in out.items() if t >= cutoff}


def load_tape(days, refresh):
    """-> (coins: {fleet_coin: {ts:(o,h,l,c,v)}}, btc4h: {ts:(o,h,l,c,v)},
    skipped: [coin]). BTC-4h gets +50d warmup for the 280-bar regime window."""
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days", 0) >= days:
            return ({s: {int(k): tuple(v) for k, v in m.items()}
                     for s, m in d["coins"].items()},
                    {int(k): tuple(v) for k, v in d["btc4h"].items()},
                    d.get("skipped", []))
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    ids = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol") is not None}
    coins, skipped = {}, []
    for coin in CARRIER.coins:
        sym, _ = to_lighter(coin)
        mid = ids.get(sym)
        if mid is None:
            skipped.append(coin)
            print(f"  {coin}: not listed on Lighter ({sym}) — skipped "
                  f"(live book skips it too)")
            continue
        bars = fetch_candles(mid, "1h", 3600, days)
        if len(bars) < CARRIER.min_bars + 48:
            skipped.append(coin)
            print(f"  {coin}: only {len(bars)} 1h bars — skipped")
            continue
        coins[coin] = bars
        span = (max(bars) - min(bars)) / 86400
        print(f"  {coin:6s} {len(bars):5d} 1h bars ({span:.0f}d)")
        time.sleep(PAGE_SLEEP)
    btc4h = fetch_candles(ids["BTC"], "4h", 14400, days + 50)
    print(f"  BTC-4h regime series: {len(btc4h)} bars")
    json.dump({"days": days, "fetched": int(time.time()),
               "coins": {s: {str(k): list(v) for k, v in m.items()}
                         for s, m in coins.items()},
               "btc4h": {str(k): list(v) for k, v in btc4h.items()},
               "skipped": skipped},
              open(CACHE, "w"))
    return coins, btc4h, skipped


# ---------------------------------------------------------------------------
# Series prep + the vectorized signal (cross-checked against CARRIER.signals)

class Series:
    def __init__(self, bars):
        ts = sorted(bars)
        self.t = ts
        self.o = [bars[k][0] for k in ts]
        self.h = [bars[k][1] for k in ts]
        self.l = [bars[k][2] for k in ts]
        self.c = [bars[k][3] for k in ts]
        self.v = [bars[k][4] for k in ts]
        self.idx = {k: i for i, k in enumerate(ts)}
        self.e50 = ema_series(self.c, 50)
        self.atr = atr_series(self.h, self.l, self.c, 14)
        self.adx = adx_series(self.h, self.l, self.c, 14)

    def prefix_bars(self, i):
        """bars dict exactly as CandleCache hands CARRIER.signals, ending at i."""
        return {"t": self.t[:i + 1], "o": self.o[:i + 1], "h": self.h[:i + 1],
                "l": self.l[:i + 1], "c": self.c[:i + 1], "v": self.v[:i + 1]}


def signal_at(sr, i, regime_up):
    """DayTraderGated.signals, verbatim logic, on precomputed causal series
    (EMA/ATR/ADX recursions are identical on a prefix and on the full series,
    so indexing at i == computing on bars[:i+1] — asserted by cross_check)."""
    c, h, l, v = sr.c, sr.h, sr.l, sr.v
    if i + 1 < CARRIER.min_bars:
        return None
    if sr.e50[i] is None or sr.atr[i] is None or i < 21:
        return None
    rng_hi = roll_max(h, 14, i - 1)
    rng_lo = roll_min(l, 14, i - 1)
    if rng_hi is None or rng_lo is None:
        return None
    band = max(rng_hi - rng_lo, 1e-9)
    buy_zone = rng_lo + 0.37 * band
    sell_zone = rng_hi - 0.22 * band
    band_pct = band / max(c[i], 1e-9)
    dc20 = roll_max(h, 20, i - 1)
    uptick = c[i] > c[i - 1]
    live_vol = v[i] > 0
    e50_rising = sr.e50[i - 6] is not None and sr.e50[i] > sr.e50[i - 6]
    tag = None
    if (regime_up and c[i] <= buy_zone and band_pct >= CARRIER.BAND_PCT_ON
            and c[i] > sr.e50[i] and uptick and live_vol):
        tag = "range_on"
    if (not regime_up and c[i] <= buy_zone and c[i] > sr.e50[i] and e50_rising
            and band_pct >= CARRIER.BAND_PCT_OFF and uptick and live_vol):
        tag = "bounce_pullback"
    if (sr.adx[i] is not None and sr.adx[i] >= 25 and c[i] > sr.e50[i]
            and dc20 is not None and c[i] > dc20
            and band_pct >= CARRIER.BAND_PCT_ON and live_vol):
        tag = "trend_breakout"
    exit_ = (c[i] >= sell_zone and live_vol)
    return {"enter": tag, "exit": exit_, "atr": sr.atr[i]}


def stop_dist(tag, atr_val, px, trend_mult):
    """CARRIER.atr_stop_dist with the trend multiple parameterized. The 0.12
    fallback/cap is -CARRIER.stoploss, exactly as shipped."""
    cap = -CARRIER.stoploss
    if not atr_val or not px:
        return cap
    mult = COUNTER_MULT if tag in ("bounce_pullback", "range_meanrev") else trend_mult
    return min(mult * atr_val / px, cap)


def cross_check(data, regimes, n_samples=40, seed=7):
    """Sampled (coin, bar) prefixes through the REAL CARRIER.signals /
    atr_stop_dist must agree with the vectorized sim exactly. Abort if not."""
    rng = random.Random(seed)
    pool = [(coin, i) for coin, sr in data.items()
            for i in range(CARRIER.min_bars + 5, len(sr.t))]
    checked = 0
    for coin, i in rng.sample(pool, min(n_samples, len(pool))):
        sr = data[coin]
        reg = regimes(sr.t[i])
        mine = signal_at(sr, i, reg)
        real = CARRIER.signals(sr.prefix_bars(i), {"btc_regime_up": reg})
        assert (mine is None) == (real is None), (coin, i)
        if real is None:
            continue
        assert mine["enter"] == real["enter"], (coin, i, mine, real)
        assert mine["exit"] == real["exit"], (coin, i, mine, real)
        assert abs(mine["atr"] - real["atr"]) < 1e-9, (coin, i)
        for tag in ("range_on", "trend_breakout", "bounce_pullback"):
            px = sr.c[i]
            assert abs(stop_dist(tag, mine["atr"], px, BASELINE_TREND_MULT)
                       - CARRIER.atr_stop_dist(tag, sr.prefix_bars(i), px)) < 1e-12
        checked += 1
    return checked


# ---------------------------------------------------------------------------
# BTC-4h regime, computed the live way (btc_regime_up + CandleCache window)

def build_regime(btc4h):
    ts = sorted(btc4h)
    closes4 = [k + 14400 for k in ts]
    cl = [btc4h[k][3] for k in ts]
    flags = []
    for k in range(len(ts)):
        win = cl[max(0, k - 279):k + 1]          # SPAN_BARS['4h'] = 280
        if len(win) < 210:                        # live floor before comparing
            flags.append(False)
            continue
        e50 = ema_series(win, 50)[-1]
        e200 = ema_series(win, 200)[-1]
        flags.append(bool(e50 and e200 and e50 > e200))

    def regime_at(hour_ts):
        i = bisect.bisect_right(closes4, hour_ts) - 1
        return flags[i] if i >= 0 else False
    return regime_at


# ---------------------------------------------------------------------------
# The book simulation (one Book worth of state, per lighter_family_bot.Book)

def _roi_rung(age_min):
    rung = max((k for k in CARRIER.roi if k <= age_min), default=None)
    return None if rung is None else CARRIER.roi[rung]


def run_sim(data, regime_at, trend_mult, t_lo, t_hi):
    """Replay the carrier over [t_lo, t_hi). Fresh flat book. Returns dict."""
    pos = {}          # coin -> {entry, t0, tag, stop, stake}
    cooldown = {}     # coin -> release wall-ts
    closed = []       # {'ts','pnl','stop'} for protections
    trades = []       # full per-trade rows
    guard_until = 0.0
    p = CARRIER.protections
    tf_s = 3600.0

    def locked(now):
        nonlocal guard_until
        if now < guard_until:
            return True
        sg = p.get("slguard")
        if sg:
            win = [c for c in closed if now - c["ts"] <= sg["lookback"] * tf_s]
            if sum(1 for c in win if c["stop"]) >= sg["trades"]:
                guard_until = now + sg["stop"] * tf_s
                return True
        dd = p.get("maxdd")
        if dd:
            win = [c for c in closed if now - c["ts"] <= dd["lookback"] * tf_s]
            if len(win) >= dd["trades"]:
                cum = peak = worst = 0.0
                for c in win:
                    cum += c["pnl"]
                    peak = max(peak, cum)
                    worst = max(worst, (peak - cum) / START_EQUITY)
                if worst >= dd["dd"]:
                    guard_until = now + dd["stop"] * tf_s
                    return True
        return False

    def close_out(coin, exit_px, exit_ts, reason):
        m = pos.pop(coin)
        pnl = m["stake"] * (exit_px / m["entry"] - 1.0)
        was_stop = "stop" in reason
        closed.append({"ts": exit_ts, "pnl": pnl, "stop": was_stop})
        cooldown[coin] = exit_ts + p.get("cooldown_candles", 1) * tf_s
        trades.append({"coin": coin, "tag": m["tag"], "t0": m["t0"],
                       "entry": m["entry"], "t1": exit_ts, "exit": exit_px,
                       "reason": reason, "pnl": pnl})

    def manage_intrabar(coin, sr, j, allow_open_checks):
        """One held coin through bar j (open ts sr.t[j]). Convention in the
        header LIMITATIONS. Returns True if the position closed."""
        m = pos[coin]
        t = sr.t[j]
        o, hi, lo, cl = sr.o[j], sr.h[j], sr.l[j], sr.c[j]
        atr_ref = sr.atr[j - 1] if j >= 1 else None
        age0 = (t - m["t0"]) / 60.0

        if allow_open_checks:
            # live per-tick order at the first ~tick of the bar (px = open):
            # ratchet -> stop -> roi -> custom_exit -> exit signal. Live's
            # trigger (px <= max(prev, px*(1-dist))) is equivalent to
            # px <= prev because px*(1-dist) < px always.
            m["stop"] = max(m["stop"], o * (1 - stop_dist(m["tag"], atr_ref, o,
                                                          trend_mult)))
            if o <= m["prev_stop"]:
                close_out(coin, o, t, "trailing_stop_loss")
                return True
            rung = _roi_rung(age0)
            if rung is not None and (o / m["entry"] - 1.0) >= rung:
                close_out(coin, o, t, "roi")
                return True
            ce = CARRIER.custom_exit(m["tag"], age0, o / m["entry"] - 1.0)
            if ce:
                close_out(coin, o, t, ce)
                return True
            jm1 = j - 1
            sig = signal_at(sr, jm1, regime_at(t)) if jm1 >= 0 else None
            if (sig and sig.get("exit") and m["tag"] != "trend_breakout"
                    and sr.t[jm1] == t - 3600):
                close_out(coin, o, t, "range_top")
                return True

        # intrabar: stop vs the level carried into the bar (post open-ratchet)
        if lo <= m["stop"]:
            close_out(coin, min(m["stop"], o), t + 3600, "trailing_stop_loss")
            return True
        # profit targets on the way up — the LOWER target is touched first
        targets = []
        rung = _roi_rung(age0)
        if rung is not None and rung > 0:
            targets.append((m["entry"] * (1 + rung), "roi"))
        if m["tag"] == "bounce_pullback":
            targets.append((m["entry"] * 1.012, "bounce_take"))
        targets.sort()
        for px_t, why in targets:
            if hi >= px_t and px_t > o:
                close_out(coin, px_t, t + 3600, why)
                return True
        # ratchet on the bar high, then the only certain intrabar ordering:
        # the close comes after the high — a close back under the ratcheted
        # stop is a cross live's 90s loop would have caught.
        m["stop"] = max(m["stop"], hi * (1 - stop_dist(m["tag"], atr_ref, hi,
                                                       trend_mult)))
        if cl <= m["stop"]:
            close_out(coin, m["stop"], t + 3600, "trailing_stop_loss")
            return True
        m["prev_stop"] = m["stop"]
        return False

    hours = range(int(t_lo), int(t_hi), 3600)
    for t in hours:
        # ---- phase A: manage held positions through the bar opening at t ----
        for coin in [c for c in CARRIER.coins if c in pos]:
            sr = data.get(coin)
            j = sr.idx.get(t) if sr else None
            if j is None:
                continue          # tape gap: no mark this hour (live: stale px)
            manage_intrabar(coin, sr, j, allow_open_checks=True)

        # ---- phase B: entries on the bar CLOSED at t (acted at ~t+20s) ----
        if locked(t):
            continue
        entries_this_hour = 0
        for coin in CARRIER.coins:
            if coin in pos or coin not in data:
                continue
            sr = data[coin]
            j = sr.idx.get(t)
            if j is None or j < 1 or sr.t[j - 1] != t - 3600:
                continue          # need the just-closed bar AND a live price
            if len(pos) >= CARRIER.max_open:
                break
            if t < cooldown.get(coin, 0.0):
                continue
            sig = signal_at(sr, j - 1, regime_at(t))
            tag = sig.get("enter") if sig else None
            if not tag:
                continue
            if entries_this_hour >= CARRIER.MAX_ENTRIES_PER_HOUR:
                continue
            entries_this_hour += 1
            entry_px = sr.o[j]
            stake = STAKE * CARRIER.stake_mult(tag, None)  # 0.5x counter-trend
            dist0 = stop_dist(tag, sr.atr[j - 1], entry_px, trend_mult)
            pos[coin] = {"entry": entry_px, "t0": t, "tag": tag, "stake": stake,
                         "stop": entry_px * (1 - dist0),
                         "prev_stop": entry_px * (1 - dist0)}
            # phase C: the rest of the entry bar can already manage it
            manage_intrabar(coin, data[coin], j, allow_open_checks=False)

    # mark open positions at the window edge (kept OUT of exit-mix/reclaim)
    for coin in list(pos):
        sr = data[coin]
        j = max(i for i in range(len(sr.t)) if sr.t[i] < t_hi)
        close_out(coin, sr.c[j], sr.t[j] + 3600, "end_of_window")

    real = [tr for tr in trades if tr["reason"] != "end_of_window"]
    return {"trades": trades, "n": len(real),
            "pnl": sum(tr["pnl"] for tr in trades),
            "wins": sum(1 for tr in real if tr["pnl"] > 0),
            "tsl": [tr for tr in real if tr["reason"] == "trailing_stop_loss"]}


# NOTE on CARRIER.stake_mult: it consults pulse_panic() (bot_state), which is
# inert here (no DATABASE_URL -> fail-safe False), so only the 0.5x
# counter-trend factor is active — exactly what a backtest should see.


# ---------------------------------------------------------------------------
# Reclaim grading — bot_learn._post_exit_drift contract (long side): 24 x 1h
# bars after the exit, >= 6-bar floor, reclaimed = any(high >= entry).

def grade_reclaim(sr, entry_px, exit_ts, exit_px):
    lo_i = bisect.bisect_right(sr.t, exit_ts)
    win = [i for i in range(lo_i, len(sr.t)) if sr.t[i] <= exit_ts + 24 * 3600]
    if len(win) < 6:
        return None
    reclaimed, hrs = False, None
    for i in win:
        if sr.h[i] >= entry_px:
            reclaimed = True
            hrs = (sr.t[i] + 3600 - exit_ts) / 3600.0
            break
    fwd = sr.c[win[-1]] / exit_px - 1.0 if exit_px else None
    return {"reclaimed": reclaimed, "hrs": hrs, "fwd": fwd}


def reclaim_table(data, tsl_trades, t_mid):
    rows = []
    for tr in tsl_trades:
        g = grade_reclaim(data[tr["coin"]], tr["entry"], tr["t1"], tr["exit"])
        if g is None:
            continue
        rows.append({**tr, **g, "half": 1 if tr["t1"] < t_mid else 2})
    def agg(sel):
        n = len(sel)
        r = sum(1 for x in sel if x["reclaimed"])
        fw = [x["fwd"] for x in sel if x["fwd"] is not None]
        return (n, (100.0 * r / n) if n else None,
                (sum(fw) / len(fw)) if fw else None)
    out = {"overall": agg(rows)}
    for tag in sorted({x["tag"] for x in rows}):
        out[f"tag:{tag}"] = agg([x for x in rows if x["tag"] == tag])
    for h in (1, 2):
        out[f"half{h}"] = agg([x for x in rows if x["half"] == h])
    return out, rows


# ---------------------------------------------------------------------------
# The 9 REAL ledger stop-outs, graded off the same tape

def grade_real(data):
    out = []
    for pair, opened, closed_iso, pnl, tag in REAL_TSL:
        exit_ts = datetime.fromisoformat(closed_iso).timestamp()
        sr = data.get(pair)
        if sr is None:
            out.append((pair, closed_iso, pnl, tag, None))
            continue
        hr = round(opened / 3600.0) * 3600
        j = sr.idx.get(hr)
        at_hr = j is not None
        if j is None:
            j = sr.idx.get(hr - 3600)
            if j is None:
                j = sr.idx.get(hr + 3600)
        if j is None:
            out.append((pair, closed_iso, pnl, tag, None))
            continue
        entry_est = sr.o[j] if at_hr else sr.c[j]
        ex_bar = sr.idx.get(int(exit_ts // 3600) * 3600)
        exit_est = sr.c[ex_bar] if ex_bar is not None else None
        g = grade_reclaim(sr, entry_est, exit_ts, exit_est)
        if g is not None:
            # the fill was SOMEWHERE inside the entry bar — bracket the verdict
            # with the bar's low (easiest reclaim) and high (hardest)
            g_lo = grade_reclaim(sr, sr.l[j], exit_ts, exit_est)
            g_hi = grade_reclaim(sr, sr.h[j], exit_ts, exit_est)
            g["rec_lo"] = g_lo["reclaimed"] if g_lo else None
            g["rec_hi"] = g_hi["reclaimed"] if g_hi else None
        if g is not None and not g["reclaimed"]:
            # honesty extra: how long DID it take? (scan past the 24h window)
            for i in range(bisect.bisect_right(sr.t, exit_ts), len(sr.t)):
                if sr.h[i] >= entry_est:
                    g["late_hrs"] = (sr.t[i] + 3600 - exit_ts) / 3600.0
                    break
        out.append((pair, closed_iso, pnl, tag, g))
    return out


# ---------------------------------------------------------------------------

def fmt_pct(x):
    return "  n/a" if x is None else f"{x:5.0f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=int(os.environ.get("STUDY_DAYS", 180)))
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    print(f"Fetching LIGHTER 1h tape — {a.days}d, the crypto-intraday-15m "
          f"universe ({len(CARRIER.coins)} fleet coins)")
    coins, btc4h, skipped = load_tape(a.days, a.refresh)
    if not coins:
        raise SystemExit("no Lighter candle history — nothing to study")
    data = {c: Series(b) for c, b in coins.items()}
    regime_at = build_regime(btc4h)

    all_ts = sorted({t for sr in data.values() for t in sr.t})
    t_lo = all_ts[0]
    t_hi = all_ts[-1] + 3600
    t_mid = t_lo + ((t_hi - t_lo) // 2 // 3600) * 3600
    span_d = (t_hi - t_lo) / 86400.0
    d0 = time.strftime("%Y-%m-%d", time.gmtime(t_lo))
    d1 = time.strftime("%Y-%m-%d", time.gmtime(t_hi))
    print(f"\nTape: {d0} -> {d1} ({span_d:.0f}d) | {len(data)} books | "
          f"skipped (unlisted/short): {', '.join(skipped) or 'none'}")

    nchk = cross_check(data, regime_at)
    print(f"Faithfulness cross-check vs the REAL DayTraderGated.signals/"
          f"atr_stop_dist: {nchk} sampled prefixes agree exactly.")

    # regime honesty label
    btc = data.get("BTC")
    def btc_ret(a_ts, b_ts):
        ia = bisect.bisect_left(btc.t, a_ts)
        ib = bisect.bisect_right(btc.t, b_ts) - 1
        return btc.c[ib] / btc.c[ia] - 1.0
    r_full, r_h1, r_h2 = btc_ret(t_lo, t_hi), btc_ret(t_lo, t_mid), btc_ret(t_mid, t_hi)
    reg_hours = [t for t in range(int(t_lo), int(t_hi), 3600)]
    reg_up_pct = 100.0 * sum(1 for t in reg_hours if regime_at(t)) / len(reg_hours)
    print(f"REGIME LABEL: BTC {r_full:+.0%} over the window "
          f"(h1 {r_h1:+.0%}, h2 {r_h2:+.0%}); btc_regime_up on {reg_up_pct:.0f}% "
          f"of hours. {'BEAR-TAPE RESULT — label it as such.' if r_full < 0 else 'Up-tape.'}")

    # ---- 1+2: baseline sim + reclaim table ---------------------------------
    base = run_sim(data, regime_at, BASELINE_TREND_MULT, t_lo, t_hi)
    rt, rrows = reclaim_table(data, base["tsl"], t_mid)
    print(f"\n=== BASELINE SIM (trend stop {BASELINE_TREND_MULT}x, counter-trend "
          f"{COUNTER_MULT}x — as shipped) ===")
    print(f"closed trades n={base['n']} | net P&L ${base['pnl']:+.2f} | "
          f"wins {base['wins']} | TSL exits {len(base['tsl'])} "
          f"(graded {len(rrows)})")
    mix = {}
    for tr in base["trades"]:
        if tr["reason"] != "end_of_window":
            mix.setdefault(tr["reason"], [0, 0.0])
            mix[tr["reason"]][0] += 1
            mix[tr["reason"]][1] += tr["pnl"]
    for why, (k, s) in sorted(mix.items(), key=lambda x: -x[1][0]):
        print(f"    {why:>20s} {k:>4d}  ${s:+8.2f}")

    print("\n=== RECLAIM TABLE — sim TSL exits, reclaim of ENTRY within 24h "
          "(bot_learn contract) ===")
    print(f"{'bucket':>22s} {'n':>5s} {'reclaim%':>9s} {'avg fwd24':>10s}")
    for k, (n, r, f) in rt.items():
        print(f"{k:>22s} {n:>5d} {fmt_pct(r):>9s} "
              f"{('   n/a' if f is None else f'{f:+8.2%}'):>10s}")
    print("  (brain bars: stop_too_tight fires at reclaim >= 60%; "
          "'stop is fine' needs <= 35%)")

    # ---- 3: counterfactual sweep, both halves (fresh books per half) -------
    print(f"\n=== COUNTERFACTUAL — trend-tag stop multiple (counter-trend "
          f"fixed at {COUNTER_MULT}x) ===")
    hdr = (f"{'trend mult':>10s} {'net P&L $':>10s} {'n':>5s} {'win%':>6s} "
           f"{'TSL n':>6s} {'TSL $':>9s} | {'h1 $':>8s} {'h2 $':>8s} "
           f"{'both improve?':>14s}")
    print(hdr)
    print("-" * len(hdr))
    results = {}
    for m in SWEEP_TREND_MULTS:
        full = run_sim(data, regime_at, m, t_lo, t_hi)
        h1 = run_sim(data, regime_at, m, t_lo, t_mid)
        h2 = run_sim(data, regime_at, m, t_mid, t_hi)
        results[m] = (full, h1, h2)
    b_full, b_h1, b_h2 = results[BASELINE_TREND_MULT]
    for m in SWEEP_TREND_MULTS:
        full, h1, h2 = results[m]
        if m == BASELINE_TREND_MULT:
            verdict = "(baseline)"
        else:
            both = (h1["pnl"] > b_h1["pnl"]) and (h2["pnl"] > b_h2["pnl"])
            verdict = "YES" if both else "NO"
        wr = 100.0 * full["wins"] / full["n"] if full["n"] else 0.0
        print(f"{m:>10.1f} {full['pnl']:>10.2f} {full['n']:>5d} {wr:>6.1f} "
              f"{len(full['tsl']):>6d} {sum(t['pnl'] for t in full['tsl']):>9.2f} | "
              f"{h1['pnl']:>8.2f} {h2['pnl']:>8.2f} {verdict:>14s}")

    # ---- 4: the 9 REAL ledger stop-outs ------------------------------------
    print("\n=== THE 9 REAL LEDGER trailing_stop_loss LOSSES "
          "(crypto-intraday-15m-lshadow) ===")
    print(f"{'pair':>5s} {'exit (UTC)':>17s} {'pnl $':>7s} {'tag':>15s} "
          f"{'reclaimed<=24h':>14s} {'in (h)':>7s} {'fwd24':>8s}")
    n_g = n_r = n_easy = n_hard = 0
    for pair, closed_iso, pnl, tag, g in grade_real(data):
        if g is None:
            row = ("ungraded (no tape)", "", "")
        else:
            n_g += 1
            n_r += 1 if g["reclaimed"] else 0
            n_easy += 1 if g.get("rec_lo") else 0
            n_hard += 1 if g.get("rec_hi") else 0
            late = f" (in {g.get('late_hrs', 0):.0f}h)" if (not g["reclaimed"]
                    and g.get("late_hrs")) else ""
            row = ("YES" if g["reclaimed"] else "NO" + late,
                   f"{g['hrs']:.0f}" if g["hrs"] else "-",
                   f"{g['fwd']:+.1%}" if g["fwd"] is not None else "n/a")
        print(f"{pair:>5s} {closed_iso[5:16]:>17s} {pnl:>7.2f} "
              f"{(tag or '(pre-tag)'):>15s} {row[0]:>14s} {row[1]:>7s} {row[2]:>8s}")
    if n_g:
        print(f"  -> {n_r}/{n_g} reclaimed entry within 24h of the exit "
              f"({100.0 * n_r / n_g:.0f}%) using the entry-bar OPEN as the "
              f"entry estimate.")
        print(f"  -> ESTIMATE SENSITIVITY (the ledger stores no entry price; "
              f"the fill was somewhere in the entry bar): bracket "
              f"[{min(n_hard, n_easy)}/{n_g} .. {max(n_hard, n_easy)}/{n_g}] "
              f"(bar-high vs bar-low entry). A bracket that straddles the 60% "
              f"bar is UNDECIDABLE, not evidence.")

    # ---- verdict, printed from the numbers ---------------------------------
    print("\n=== VERDICT (mechanical, from this run) ===")
    n, r, _ = rt["overall"]
    sig = (r is not None and n >= 5 and r >= 60.0)
    print(f"  stop_too_tight signature: reclaim {fmt_pct(r).strip()} on n={n} "
          f"-> {'REPRODUCES on Lighter' if sig else 'does NOT clear the 60% bar'}")
    winners = []
    for m in SWEEP_TREND_MULTS:
        if m == BASELINE_TREND_MULT:
            continue
        full, h1, h2 = results[m]
        if h1["pnl"] > b_h1["pnl"] and h2["pnl"] > b_h2["pnl"]:
            winners.append(m)
    if winners and len(winners) == len(SWEEP_TREND_MULTS) - 1:
        print(f"  counterfactual: EVERY wider stop improves BOTH halves "
              f"({winners}) — candidate for the review, on a "
              f"{'bear' if r_full < 0 else 'up'}-tape only.")
    elif winners:
        print(f"  counterfactual: {winners} improve both halves but "
              f"{[m for m in SWEEP_TREND_MULTS if m != BASELINE_TREND_MULT and m not in winners]} "
              f"do NOT — the improvement is not robust across the stop axis. "
              f"Doctrine verdict: NO CHANGE (single-regime tape, fragile axis).")
    else:
        print("  counterfactual: NO wider stop improves both halves. "
              "Doctrine verdict: NO CHANGE.")
    print("  (Whatever the axis says, the book is net "
          f"{'NEGATIVE' if b_full['pnl'] < 0 else 'positive'} at every multiple "
          "tested on this tape — the stop is not what decides its sign.)")


# ---------------------------------------------------------------------------

def _selftest():
    """No network. Synthetic tape -> vectorized signals must equal the REAL
    CARRIER.signals on prefixes; sim invariants hold."""
    rng = random.Random(42)
    t0 = 1_700_000_000 - (1_700_000_000 % 3600)
    bars = {}
    px = 100.0
    for i in range(420):
        drift = rng.gauss(0, 0.01)
        o = px
        cl = px * (1 + drift)
        hi = max(o, cl) * (1 + abs(rng.gauss(0, 0.004)))
        lo = min(o, cl) * (1 - abs(rng.gauss(0, 0.004)))
        bars[t0 + i * 3600] = (o, hi, lo, cl, 1.0 + rng.random())
        px = cl
    sr = Series(bars)
    data = {"SYN": sr}
    old_coins = CARRIER.coins
    CARRIER.coins = ["SYN"]
    try:
        for reg in (False, True):
            for i in (75, 120, 200, 419):
                mine = signal_at(sr, i, reg)
                real = CARRIER.signals(sr.prefix_bars(i), {"btc_regime_up": reg})
                assert (mine is None) == (real is None)
                if real:
                    assert mine["enter"] == real["enter"] and mine["exit"] == real["exit"]
                    assert abs(mine["atr"] - real["atr"]) < 1e-9
                    for tag in ("range_on", "bounce_pullback"):
                        assert abs(stop_dist(tag, mine["atr"], sr.c[i], 2.5)
                                   - CARRIER.atr_stop_dist(tag, sr.prefix_bars(i),
                                                           sr.c[i])) < 1e-12
        res = run_sim(data, lambda t: True, 2.5, sr.t[0], sr.t[-1] + 3600)
        for tr in res["trades"]:
            assert tr["t1"] > tr["t0"] and tr["entry"] > 0
            if tr["reason"] == "trailing_stop_loss":
                assert tr["exit"] <= tr["entry"] * 1.2      # sane fill
        g = grade_reclaim(sr, sr.o[100], sr.t[100], sr.c[100])
        assert g is None or isinstance(g["reclaimed"], bool)
    finally:
        CARRIER.coins = old_coins
    print("study_intraday_tsl_reclaim_lighter self-test: OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
