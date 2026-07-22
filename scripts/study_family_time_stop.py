#!/usr/bin/env python3
"""
scripts/study_family_time_stop.py — can a TIME-STOP free the long-budget
slots the static family books park on, without hurting them? Lighter-only.

THE PROBLEM IT TESTS (measured 22-Jul, CHANGELOG (bw)): the fleet's 20-slot
long budget is pinned red 55.9% of 48h, and the static holders are the
TrendMomo/MomoBreakout family books — freqtrade-mum-lshadow (TrendMomo 1d)
4/4 slots with ZERO closes since the 14-15-Jul boot, freqtrade-dad-lshadow +
crypto-breakout-4h-lshadow (MomoBreakout 4h) 10 slots with no closes since
17-Jul (ledger + /pnl.json, checked again 22-Jul: mum 4 open / 0 closed
ever, dad 4/4, breakout 6/6). Both strategies' exits are trend-following
(fixed stop + crossing/level breakdown) with NO time dimension — in chop
they hold indefinitely while counting against the fleet budget.

METHOD (harness = study_breakout_boot_entry.py, the accepted pattern):
full Lighter tape (paged 500 bars/call; 4h tape reused from the breakout
study's cache when present), WIDE_COINS/COINS minus unlisted; signals by
calling the SHIPPED `TrendMomo.signals` / `MomoBreakout.signals` (imported
from lighter_family_bot — replay through the real code, zero port risk) on
each bot's own CandleCache window (240 bars 1d / 280 bars 4h). Portfolio
sim per book with shipped exits (stop intra-bar w/ gap-through at open,
signal exit at close), shipped protections (cooldown/slguard/maxdd),
shipped stakes ($50 x MomoBreakout's inverse-vol mult). The TIME-STOP
variant adds ONE rule in the same slot custom_exit occupies in the shipped
manage loop (after the stop check, before the exit signal): close at the
first bar close where age >= N days, reason `max_hold_timeout` — NOT
"time_stop", because record_close's `was_stop = "stop" in reason` would
silently count time exits toward StoplossGuard; `max_hold_timeout` reuses
DayTraderGated's existing custom_exit vocabulary and the brain grades it
separately (`long-<tag>_max_hold_timeout`). Organs excluded (brain mults,
fleet veto, panic — identical for all variants). Price-only P&L: NO funding
accrual, which is CONSERVATIVE for this change — these books are long-only
on Lighter and PAY funding, so shorter holds can only help the variant;
passing without that credit is the stricter test. Anti-overfit: candidates
are graded against the a-priori anchor (winning trades' P90 hold from the
BASELINE sim) — enactment may only pick a candidate >= P90 (the stop must
not truncate the winning cohort's typical run), and among candidates that
pass not-worse-BOTH-halves per book AND >=20% slot-day relief, the
LONGEST (most conservative) wins. The P&L-max of the grid is ignored.

RESULTS 2026-07-22 (4h tape 2025-03-09..2026-07-22 500d 25 coins, half at
2025-11-14, BTC full -22.7% / H1 +15.2% / H2 -32.9%; 1d tape
2025-03-10..2026-07-22 499d 13 coins, half at 2025-11-14, BTC full -15.4%
/ H1 +20.3% / H2 -29.7%. REGIME: one RISING half + one FALLING half —
"both halves" spans two regimes of opposite sign; no third regime exists
in the window. Faithfulness cross-check: the dad/breakout BASELINES
reproduce study_breakout_boot_entry's LEVEL-rule P&L to the cent
(+11.90 / +16.50)):

  WINNER-HOLD ANCHOR (baseline closed winners): mum n=12 P50 42.0d
  P90 77.6d max 90d; dad n=50 P50 9.2d P90 19.3d max 30d; breakout n=77
  P50 8.5d P90 17.6d max 30d -> a-priori valid rungs: TrendMomo >=78d,
  MomoBreakout >=20d. These strategies' winners RUN FOR WEEKS — any
  slot-relieving stop truncates the winning cohort by construction.

  freqtrade-mum (TrendMomo 1d, 4 slots)   net$    H1$    H2$   n  win%  slotD dSlot conc nTS anyway  forf$
    base                                -14.15  +5.12 -19.28  42 35.7%  1118    —   2.24
    max_hold 14d                        +29.79 +33.15  -3.36  94 45.7%  1085 -3.0%  2.18  58  96.6% -147.9
    max_hold 21d                        -16.04 +24.12 -40.16  71 36.6%  1102 -1.4%  2.21  34  97.1%  -80.5
    max_hold 45d                        +31.10 +44.93 -13.84  50 32.0%  1116 -0.2%  2.24   6 100.0%  -69.1
    max_hold 80d                         -9.09  +5.12 -14.22  43 34.9%  1116 -0.2%  2.24   1 100.0%   -9.8

  MomoBreakout 4h                         net$    H1$    H2$   n  win%  slotD dSlot conc nTS anyway  forf$
   freqtrade-dad base                   +11.90 +72.08 -60.18 153 35.3%   876    —   1.75
   freqtrade-dad 7d                     +15.65 +61.06 -45.41 190 38.4%   822 -6.1%  1.65  52 100.0%  +24.0
   freqtrade-dad 10d                    -17.18 +44.91 -62.09 171 35.7%   846 -3.4%  1.69  25 100.0%  +19.7
   freqtrade-dad 14d                     -0.91 +58.27 -59.18 161 36.6%   864 -1.4%  1.73   9 100.0%  +13.1
   freqtrade-dad 21d                     +6.06 +67.18 -61.13 156 34.6%   868 -0.9%  1.74   3 100.0%   -1.8
   crypto-breakout-4h base              +16.50+109.53 -93.03 238 34.9%  1324    —   2.65
   crypto-breakout-4h 7d                +35.64+114.13 -78.49 286 37.1%  1244 -6.1%  2.49  75 100.0%   -2.5
   crypto-breakout-4h 10d               +40.30 +89.16 -48.87 262 36.3%  1284 -3.0%  2.57  37 100.0%   -7.5
   crypto-breakout-4h 14d                -1.26 +95.13 -96.40 249 35.3%  1306 -1.4%  2.61  13 100.0%   +9.2
   crypto-breakout-4h 21d               +11.91+104.94 -93.03 240 34.6%  1317 -0.5%  2.64   2 100.0%   -1.7

VERDICT: DO NOT ENACT — EITHER STRATEGY. The time-stop FAILS the change's
whole point: maximum slot-day relief anywhere on the grid is -6.1% (bar:
-20%), and at the a-priori-valid rungs it is -0.2% (mum 80d) / -0.9% /
-0.5% (momo 21d). MECHANISM (why relief can't happen here): both entries
are LEVEL conditions that persist or promptly recur (TrendMomo fast>slow
holds through the stop; MomoBreakout re-breaks its 20-bar high in any
trend), cooldown is 1 candle, and max_open is unchanged — so a freed slot
is refilled within ~2 bars by the same or another coin. A time stop
changes WHICH positions occupy the slots, never HOW MANY (avg concurrency
2.24 -> 2.18 at best). Second finding, same direction: 96.6-100% of
time-stopped positions would have exited via the shipped exits later
anyway on this tape — "parked forever" is a young-window artifact; these
books are DESIGNED to hold weeks (winner P50 8.5-42d), and the live holds
(5-8d as of 22-Jul) are inside normal range. The P&L-attractive rungs
(mum 14d +$29.79, breakout 7d +$35.64) sit BELOW the winners' P90 anchor
— picking them is mining the grid — and momo rungs are not-worse-both-
halves nowhere except breakout 7d (a-priori invalid) anyway. The real
budget lever is entry-side (max_open / fleet long-budget allocation), not
exit-side time stops. Not-worse deltas at the valid rungs, for the
record: mum 80d H1 +0.00 H2 +5.06 (passes halves, no relief); dad 21d
H1 -4.90 H2 -0.95 (fails); breakout 21d H1 -4.59 H2 +0.00 (fails).

Usage:
    python3 scripts/study_family_time_stop.py --selftest   # offline, no net
    python3 scripts/study_family_time_stop.py              # full run (cached)
    python3 scripts/study_family_time_stop.py --refresh    # refetch tapes
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# repo root importable (the study replays the SHIPPED strategy code)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
os.environ.setdefault("FAMILY_LOG_FILE", os.devnull)   # no side-effect log file

import lighter_family_bot as fam                        # noqa: E402
from venues.symbol_map import to_lighter                # noqa: E402

B = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
CACHE = os.path.join(_HERE, ".family_time_stop_cache.json")
SEED_4H = os.path.join(_HERE, ".breakout_boot_cache.json")  # reuse if present
DAYS = int(os.environ.get("FTS_DAYS", "500"))

# shipped strategy instances (STRATEGIES list parameters, verified in code)
STRATS = {
    "trendmomo": fam.TrendMomo("study", tf="1d", stoploss=-0.15, max_open=4,
                               style="s"),
    "momo": fam.MomoBreakout("study", tf="4h", stoploss=-0.12, max_open=6,
                             style="s"),
}
SPAN = {"trendmomo": fam.CandleCache.SPAN_BARS["1d"],   # 240 — the bot's window
        "momo": fam.CandleCache.SPAN_BARS["4h"]}        # 280
TFS = {"trendmomo": 86400, "momo": 4 * 3600}
STAKE = 50.0                                            # FAMILY_STAKE_USD default

# the three static-holder books exactly as shipped (STRATEGIES list); the
# SwingDip/DayTrader books are out of scope (they already have ROI ladders
# and/or timeouts and are not the parked slots).
BOOKS = {
    "freqtrade-mum": dict(strat="trendmomo", coins=list(fam.COINS),
                          max_open=4, stoploss=-0.15),
    "freqtrade-dad": dict(strat="momo", coins=list(fam.COINS),
                          max_open=4, stoploss=-0.12),
    "crypto-breakout-4h": dict(strat="momo", coins=list(fam.WIDE_COINS),
                               max_open=6, stoploss=-0.12),
}

# time-stop candidate grids (days). The verdict may only pick a candidate
# >= the winning trades' P90 hold (printed by the run) — the a-priori
# anchor; among survivors the LONGEST that still frees >=20% slot-days.
# Grid revised ONCE after the baseline anchor measurement, to include an
# a-priori-VALID rung per strategy (trendmomo 80d >= its 77.6d winner P90,
# momo 21d >= 19.3d/17.6d) — the anchor is only measurable from the
# baseline run; no rung was added or removed based on P&L.
CANDIDATES = {"trendmomo": (14, 21, 45, 80), "momo": (7, 10, 14, 21)}
TS_REASON = "max_hold_timeout"      # NOT 'time_stop': record_close flags
#              was_stop = "stop" in reason -> 'time_stop' would count toward
#              StoplossGuard; this name reuses DayTraderGated's vocabulary.
RELIEF_BAR = 0.20                   # material slot-day reduction


# ---------------------------------------------------------------------------
# data

def _get(path, **q):
    url = B + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def fetch_candles(mid, tf, tf_s, days):
    """OHLCV paged backward (500-bar cap/call) -> sorted closed-bar lists."""
    out = {}
    end = int(time.time())
    cutoff = end - days * 86400
    seen_oldest = None
    while True:
        rows = _get("/api/v1/candles", market_id=mid, resolution=tf,
                    start_timestamp=end - 500 * tf_s, end_timestamp=end,
                    count_back=500).get("c") or []
        if not rows:
            break
        for r in rows:
            ts = int(r["t"]) // 1000
            out[ts] = (float(r["o"]), float(r["h"]), float(r["l"]),
                       float(r["c"]), float(r.get("v") or 0.0))
        oldest = min(int(r["t"]) // 1000 for r in rows)
        if oldest <= cutoff or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - tf_s
    now = time.time()
    ts_sorted = sorted(t for t in out if t >= cutoff and t + tf_s <= now - 5)
    return {"t": [t for t in ts_sorted],                      # bar OPEN, seconds
            "o": [out[t][0] for t in ts_sorted],
            "h": [out[t][1] for t in ts_sorted],
            "l": [out[t][2] for t in ts_sorted],
            "c": [out[t][3] for t in ts_sorted],
            "v": [out[t][4] for t in ts_sorted]}


def load_tapes(refresh=False):
    """{"4h": {coin: bars}, "1d": {coin: bars}} for every listed study coin.
    4h serves both MomoBreakout books (family list is a subset of WIDE);
    1d serves TrendMomo (family COINS only). The 4h tape is seeded from the
    breakout study's cache when present — same fetch code, same format."""
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days", 0) >= DAYS:
            return d["tapes"]
    tapes = {"4h": {}, "1d": {}}
    if os.path.exists(SEED_4H) and not refresh:
        d = json.load(open(SEED_4H))
        if d.get("days", 0) >= DAYS:
            tapes["4h"] = d["bars"]
            print(f"  4h tape seeded from {os.path.basename(SEED_4H)} "
                  f"({len(tapes['4h'])} coins)")
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    by_sym = {o["symbol"]: o for o in obs if o.get("status") == "active"}
    want = {"4h": (fam.WIDE_COINS, STRATS["momo"].min_bars),
            "1d": (fam.COINS, STRATS["trendmomo"].min_bars)}
    for tf, (coins, min_bars) in want.items():
        tf_s = 4 * 3600 if tf == "4h" else 86400
        for coin in coins:
            if coin in tapes[tf]:
                continue
            sym, _ = to_lighter(coin)
            m = by_sym.get(sym)
            if not m:
                print(f"  {coin} {tf}: unlisted on Lighter — skipped "
                      f"(the bot skips it too)")
                continue
            try:
                b = fetch_candles(int(m["market_id"]), tf, tf_s, DAYS)
            except Exception as e:  # noqa: BLE001
                print(f"  {coin} {tf}: fetch failed ({e}) — skipped")
                continue
            if len(b["t"]) < min_bars + 10:
                print(f"  {coin} {tf}: only {len(b['t'])} bars — skipped")
                continue
            tapes[tf][coin] = b
            print(f"  {coin:6s} {tf}: {len(b['t']):5d} bars "
                  f"({(b['t'][-1] - b['t'][0]) / 86400:.0f}d)")
    json.dump({"days": DAYS, "tapes": tapes}, open(CACHE, "w"))
    return tapes


# ---------------------------------------------------------------------------
# signals — through the SHIPPED code, on the bot's own sliding window

def compute_flags(strat_key, b):
    """Per bar i: (enter, exit, atr_pct, valid) by calling the real strategy's
    .signals on the last <=SPAN bars ending at i — exactly the window
    CandleCache serves the bot."""
    strat, span = STRATS[strat_key], SPAN[strat_key]
    n = len(b["t"])
    ent = [False] * n
    exi = [False] * n
    atr = [None] * n
    valid = [False] * n
    for i in range(n):
        lo = max(0, i + 1 - span)
        win = {k: b[k][lo:i + 1] for k in ("t", "o", "h", "l", "c", "v")}
        sig = strat.signals(win, {})
        if sig is None:
            continue
        valid[i] = True
        ent[i] = sig["enter"] is not None
        exi[i] = bool(sig["exit"])
        atr[i] = sig.get("atr_pct")
    return {"enter": ent, "exit": exi, "atr_pct": atr, "valid": valid}


def stake_of(strat_key, atr_pct):
    """Shipped stake: TrendMomo flat 1.0x; MomoBreakout inverse-vol
    (ref 2% ATR, clamp [0.3, 1.0]). Organ-free path (panic excluded —
    identical for all variants)."""
    m = 1.0
    if strat_key == "momo" and atr_pct and atr_pct > 0:
        m *= max(0.3, min(1.0, 0.02 / atr_pct))
    return STAKE * m


# ---------------------------------------------------------------------------
# faithful single-trade exit walk (the forfeit counterfactual)

def walk_exit(b, fl, j_entry, entry_px, stoploss):
    """From an entry at close of bar j_entry, walk forward with the SHIPPED
    exits only: stop (intra-bar, gap-through at open) then the signal exit at
    close. Returns (exit_px, j_exit, reason); marks at last close if unhit."""
    stop_px = entry_px * (1 + stoploss)
    n = len(b["t"])
    for j in range(j_entry + 1, n):
        if b["o"][j] <= stop_px:                 # gap through: fill at open
            return b["o"][j], j, "stop"
        if b["l"][j] <= stop_px:
            return stop_px, j, "stop"
        if fl["exit"][j]:
            return b["c"][j], j, "signal"
    return b["c"][n - 1], n - 1, "open_marked"


# ---------------------------------------------------------------------------
# portfolio sim — one book, shipped protections, optional time-stop

def sim_book(book, data, flags, half_ts, max_hold_days=None):
    strat_key = book["strat"]
    tf_s = TFS[strat_key]
    prot = STRATS[strat_key].protections
    max_hold_s = max_hold_days * 86400 if max_hold_days else None
    coins = [c for c in book["coins"] if c in data]
    max_open, stoploss = book["max_open"], book["stoploss"]
    idx = {c: {t: i for i, t in enumerate(data[c]["t"])} for c in coins}
    grid = sorted({t for c in coins for t in data[c]["t"]})
    pos = {}                       # coin -> dict(entry, stake, j, ts)
    cooldown = {}                  # coin -> release close-ts (ties block)
    closed = []                    # dicts(ts, pnl, stop) for the guards
    trades = []
    guard_until = 0.0

    def locked(now):
        nonlocal guard_until
        if now < guard_until:
            return True
        sg = prot.get("slguard")
        if sg:
            win = [c for c in closed if now - c["ts"] <= sg["lookback"] * tf_s]
            if sum(1 for c in win if c["stop"]) >= sg["trades"]:
                guard_until = now + sg["stop"] * tf_s
                return True
        dd = prot.get("maxdd")
        if dd:
            win = [c for c in closed if now - c["ts"] <= dd["lookback"] * tf_s]
            if len(win) >= dd["trades"]:
                cum = peak = worst = 0.0
                for c in win:
                    cum += c["pnl"]
                    peak = max(peak, cum)
                    worst = max(worst, (peak - cum) / fam.START_EQUITY)
                if worst >= dd["dd"]:
                    guard_until = now + dd["stop"] * tf_s
                    return True
        return False

    def close_at(coin, exit_px, T, reason):
        p = pos[coin]
        pnl = p["stake"] * (exit_px / p["entry"] - 1.0)
        # faithful to record_close: was_stop = "stop" in reason (TS_REASON
        # deliberately avoids the substring — see header)
        closed.append({"ts": T, "pnl": pnl, "stop": "stop" in reason})
        trades.append({"coin": coin, "ts": p["ts"], "ts_exit": T, "pnl": pnl,
                       "stake": p["stake"], "entry": p["entry"], "j": p["j"],
                       "reason": reason})
        cooldown[coin] = T + prot.get("cooldown_candles", 1) * tf_s
        del pos[coin]

    for t_open in grid:
        T = t_open + tf_s                       # decision time = bar close
        # ---- manage helds on the bar that just closed (shipped order:
        #      stop -> [custom_exit slot = the time-stop] -> exit signal) ----
        for coin in list(pos):
            j = idx[coin].get(t_open)
            if j is None:
                continue
            p = pos[coin]
            b = data[coin]
            stop_px = p["entry"] * (1 + stoploss)
            if b["o"][j] <= stop_px:
                close_at(coin, b["o"][j], T, "stop")
            elif b["l"][j] <= stop_px:
                close_at(coin, stop_px, T, "stop")
            elif max_hold_s and T - p["ts"] >= max_hold_s:
                close_at(coin, b["c"][j], T, TS_REASON)
            elif flags[coin]["exit"][j]:
                close_at(coin, b["c"][j], T, "signal")
        # ---- entries (book coin order, shipped gate order) ----
        if locked(T):
            continue
        for coin in coins:
            if coin in pos or len(pos) >= max_open:
                continue
            j = idx[coin].get(t_open)
            if j is None or not flags[coin]["enter"][j]:
                continue
            if T <= cooldown.get(coin, 0.0):
                continue
            st = stake_of(strat_key, flags[coin]["atr_pct"][j])
            pos[coin] = {"entry": data[coin]["c"][j], "stake": st,
                         "j": j, "ts": T}
    # mark whatever is still open at its last close
    for coin, p in pos.items():
        b = data[coin]
        pnl = p["stake"] * (b["c"][-1] / p["entry"] - 1.0)
        trades.append({"coin": coin, "ts": p["ts"], "ts_exit": b["t"][-1] + tf_s,
                       "pnl": pnl, "stake": p["stake"], "entry": p["entry"],
                       "j": p["j"], "reason": "open_marked"})
    net = sum(t["pnl"] for t in trades)
    h1 = sum(t["pnl"] for t in trades if t["ts"] < half_ts)
    h2 = net - h1
    wins = sum(1 for t in trades if t["pnl"] > 0)
    slot_s = sum(t["ts_exit"] - t["ts"] for t in trades)
    span_s = max(1, (grid[-1] + tf_s) - (grid[0] + tf_s))
    return {"net": net, "h1": h1, "h2": h2, "n": len(trades), "wins": wins,
            "slot_days": slot_s / 86400.0, "avg_conc": slot_s / span_s,
            "trades": trades}


def forfeit_stats(res, data, flags, stoploss):
    """For each time-stop exit: would the SHIPPED exits have closed it later
    anyway, and at what P&L? delta = shipped-walk pnl − time-stop pnl
    (positive = the stop cost money on that trade, single-trade view)."""
    ts_trades = [t for t in res["trades"] if t["reason"] == TS_REASON]
    anyway = 0
    delta = 0.0
    for t in ts_trades:
        px, _j, r = walk_exit(data[t["coin"]], flags[t["coin"]], t["j"],
                              t["entry"], stoploss)
        if r != "open_marked":
            anyway += 1
        delta += t["stake"] * (px / t["entry"] - 1.0) - t["pnl"]
    n = len(ts_trades)
    return {"n_ts": n, "anyway_frac": anyway / n if n else 0.0,
            "forfeit_usd": delta}


def pctl(vals, q):
    """Linear-interpolation percentile of a list (q in [0,1])."""
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * q
    f = int(k)
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


# ---------------------------------------------------------------------------

def pct(x):
    return f"{100 * x:.1f}%"


def run():
    refresh = "--refresh" in sys.argv
    print(f"Lighter tape — universe load{' (refresh)' if refresh else ''}:")
    tapes = load_tapes(refresh)
    print(f"4h: {len(tapes['4h'])} coins | 1d: {len(tapes['1d'])} coins")

    def iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    flags = {}
    half = {}
    for tf, strat_key in (("4h", "momo"), ("1d", "trendmomo")):
        data = tapes[tf]
        all_ts = sorted({t for b in data.values() for t in b["t"]})
        tf_s = TFS[strat_key]
        t0, t1 = all_ts[0], all_ts[-1] + tf_s
        half[strat_key] = (t0 + t1) / 2
        print(f"\n{tf} window {iso(t0)} .. {iso(t1)} ({(t1 - t0) / 86400:.0f}d), "
              f"half at {iso(half[strat_key])}")
        if "BTC" in data:
            c, tarr = data["BTC"]["c"], data["BTC"]["t"]
            mid_i = min(range(len(tarr)),
                        key=lambda i: abs(tarr[i] - half[strat_key]))
            print(f"  BTC regime: full {pct(c[-1] / c[0] - 1)} | "
                  f"H1 {pct(c[mid_i] / c[0] - 1)} | H2 {pct(c[-1] / c[mid_i] - 1)}"
                  f" — state the regime; a one-regime pass is a pass in that "
                  f"regime only")
        print(f"  computing signals through the SHIPPED "
              f"{type(STRATS[strat_key]).__name__}.signals "
              f"(window={SPAN[strat_key]} bars)...")
        flags[strat_key] = {coin: compute_flags(strat_key, b)
                            for coin, b in data.items()}

    # ---- per-book: baseline, winner-hold anchor, then the candidate grid ----
    verdicts = {}
    for name, book in BOOKS.items():
        strat_key = book["strat"]
        tf = "1d" if strat_key == "trendmomo" else "4h"
        data, fl, half_ts = tapes[tf], flags[strat_key], half[strat_key]
        base = sim_book(book, data, fl, half_ts)
        closed_winners = [t for t in base["trades"]
                          if t["pnl"] > 0 and t["reason"] != "open_marked"]
        holds = [(t["ts_exit"] - t["ts"]) / 86400.0 for t in closed_winners]
        p50, p75, p90 = pctl(holds, .5), pctl(holds, .75), pctl(holds, .9)
        print(f"\n{'=' * 76}\n{name} ({type(STRATS[strat_key]).__name__} {tf}, "
              f"{book['max_open']} slots, stop {book['stoploss'] * 100:.0f}%)")
        print(f"  winner-hold anchor (baseline closed winners n={len(holds)}): "
              f"P50 {p50:.1f}d  P75 {p75:.1f}d  P90 {p90:.1f}d  "
              f"max {max(holds) if holds else 0:.1f}d"
              f"  -> a-priori candidates must be >= P90")
        hdr = (f"  {'variant':14s} {'net$':>8s} {'H1$':>8s} {'H2$':>8s} "
               f"{'n':>4s} {'win%':>6s} {'slotD':>7s} {'dSlot':>7s} "
               f"{'conc':>5s} {'nTS':>4s} {'anyway':>7s} {'forf$':>7s}")
        print(hdr)

        def row(label, r, f=None):
            ds = (r["slot_days"] / base["slot_days"] - 1.0) \
                if base["slot_days"] else 0.0
            print(f"  {label:14s} {r['net']:8.2f} {r['h1']:8.2f} {r['h2']:8.2f} "
                  f"{r['n']:4d} {pct(r['wins'] / max(1, r['n'])):>6s} "
                  f"{r['slot_days']:7.0f} "
                  f"{'—' if r is base else pct(ds):>7s} {r['avg_conc']:5.2f}"
                  + (f" {f['n_ts']:4d} {pct(f['anyway_frac']):>7s} "
                     f"{f['forfeit_usd']:7.1f}" if f else ""))

        row("base", base)
        verdicts[name] = {"anchor_p90": p90, "base": base, "cands": {}}
        for nd in CANDIDATES[strat_key]:
            r = sim_book(book, data, fl, half_ts, max_hold_days=nd)
            f = forfeit_stats(r, data, fl, book["stoploss"])
            row(f"max_hold {nd}d", r, f)
            ds = (r["slot_days"] / base["slot_days"] - 1.0) \
                if base["slot_days"] else 0.0
            verdicts[name]["cands"][nd] = {
                "r": r, "f": f, "dslot": ds,
                "not_worse": r["h1"] >= base["h1"] - 1e-9
                and r["h2"] >= base["h2"] - 1e-9,
                "apriori": p90 is not None and nd >= p90,
                "relief": -ds >= RELIEF_BAR}

    # ---- verdict per strategy (per-book bar: every book of the strategy) ----
    print(f"\n{'=' * 76}\nVERDICT (bar: candidate >= winner P90, not-worse "
          f"BOTH halves in EVERY book of the strategy, slot-days "
          f"-{RELIEF_BAR * 100:.0f}% or better in every book; pick the "
          f"LONGEST passing candidate — never the P&L max):")
    for strat_key, books in (("trendmomo", ["freqtrade-mum"]),
                             ("momo", ["freqtrade-dad", "crypto-breakout-4h"])):
        passing = []
        for nd in CANDIDATES[strat_key]:
            oks = [verdicts[b]["cands"][nd] for b in books]
            ok = all(c["not_worse"] and c["apriori"] and c["relief"]
                     for c in oks)
            why = "; ".join(
                f"{b}: " + ",".join(k for k, v in (
                    ("apriori", c["apriori"]), ("halves", c["not_worse"]),
                    ("relief", c["relief"])) if not v)
                for b, c in zip(books, oks) if not (
                    c["not_worse"] and c["apriori"] and c["relief"]))
            print(f"  {strat_key:10s} {nd:2d}d: "
                  f"{'PASS' if ok else 'fail (' + (why or '?') + ')'}")
            if ok:
                passing.append(nd)
        if passing:
            print(f"  -> {strat_key}: ENACT max_hold {max(passing)}d "
                  f"(longest passing candidate)")
        else:
            print(f"  -> {strat_key}: DO NOT ENACT (no candidate passes the "
                  f"full bar)")

    print("\nDone. Header table numbers come from this output — re-run with "
          "--refresh rather than re-arguing from prose.")


# ---------------------------------------------------------------------------
# selftest — OFFLINE, fixtures only

def _mk_bars(closes, tf_s, hi_off=0.005, lo_off=0.005, vol=1.0):
    n = len(closes)
    return {"t": [1_700_000_000 + i * tf_s for i in range(n)],
            "o": list(closes),
            "h": [c * (1 + hi_off) for c in closes],
            "l": [c * (1 - lo_off) for c in closes],
            "c": list(closes),
            "v": [vol] * n}


def _selftest():
    tf4 = TFS["momo"]

    # ---- TrendMomo flags through the SHIPPED code: enter is a LEVEL during
    # the uptrend; the death-cross exit is an EVENT that fires exactly once.
    closes = [100.0 + i for i in range(80)] + \
             [180.0 - 3 * i for i in range(40)]
    b1 = _mk_bars(closes, TFS["trendmomo"])
    f1 = compute_flags("trendmomo", b1)
    up_true = [i for i in range(50, 79) if f1["enter"][i]]
    assert len(up_true) >= 20, "uptrend must be enter-true (level)"
    crosses = [i for i in range(len(closes)) if f1["exit"][i]]
    assert len(crosses) == 1, f"death cross must fire exactly once ({crosses})"
    assert not f1["enter"][crosses[0]], "cross bar cannot be enter-true"

    # ---- MomoBreakout fixture: flat, breakout, then a slow +0.05%/bar drift
    # that never breaks down and never stops out -> baseline holds to end.
    closes = [100.0] * 300 + [108.0]
    px = 108.0
    for _ in range(59):
        px *= 1.0005
        closes.append(px)
    b2 = _mk_bars(closes, tf4, lo_off=0.001)
    f2 = compute_flags("momo", b2)
    book = {"strat": "momo", "coins": ["BTC"], "max_open": 1, "stoploss": -0.12}
    data = {"BTC": b2}
    fl = {"BTC": f2}
    half = b2["t"][len(b2["t"]) // 2]
    base = sim_book(book, data, fl, half)
    assert base["trades"][0]["reason"] != TS_REASON
    assert any(t["reason"] == "open_marked" for t in base["trades"]), \
        "baseline must park the position to end of tape"

    # time-stop variant: 2d = 12 bars of 4h -> closes the parked trade
    var = sim_book(book, data, fl, half, max_hold_days=2)
    ts_trades = [t for t in var["trades"] if t["reason"] == TS_REASON]
    assert ts_trades, "variant must time-stop the parked trade"
    t = ts_trades[0]
    assert abs((t["ts_exit"] - t["ts"]) - 2 * 86400) < tf4, \
        "time stop must fire at the first close with age >= max_hold"
    assert var["slot_days"] < base["slot_days"], "slot-days must drop"
    assert var["avg_conc"] < base["avg_conc"]
    # the forfeit walk: shipped exits never fire on this tape -> 0% anyway
    f = forfeit_stats(var, data, fl, book["stoploss"])
    assert f["n_ts"] == len(ts_trades) and f["anyway_frac"] == 0.0

    # ---- exit priority on the SAME bar: stop beats time-stop ----
    closes = [100.0] * 300 + [108.0] + [108.0] * 11 + [80.0]
    b3 = _mk_bars(closes, tf4, lo_off=0.001)
    f3 = compute_flags("momo", b3)
    var3 = sim_book(book, {"BTC": b3}, {"BTC": f3}, half, max_hold_days=2)
    tr3 = [t for t in var3["trades"] if t["j"] == 300]
    assert tr3 and tr3[0]["reason"] == "stop", \
        f"stop must beat time-stop on the same bar ({tr3})"

    # ---- time-stop beats the signal exit on the same bar (reason label) ----
    # breakdown bar exactly at the 2d mark: manage order is stop -> time ->
    # signal, so the close is attributed to the time stop at the same price.
    closes = [100.0] * 300 + [108.0] + [108.0] * 11 + [98.0]
    b4 = _mk_bars(closes, tf4, lo_off=0.001)
    f4 = compute_flags("momo", b4)
    var4 = sim_book(book, {"BTC": b4}, {"BTC": f4}, half, max_hold_days=2)
    tr4 = [t for t in var4["trades"] if t["j"] == 300]
    assert tr4 and tr4[0]["reason"] == TS_REASON, tr4
    base4 = sim_book(book, {"BTC": b4}, {"BTC": f4}, half)
    trb = [t for t in base4["trades"] if t["j"] == 300]
    if trb and trb[0]["reason"] == "signal":
        assert abs(trb[0]["pnl"] - tr4[0]["pnl"]) < 1e-9, \
            "same-bar time-stop and signal exit must price identically"

    # ---- was_stop faithfulness: TS_REASON must NOT read as a stop ----
    assert "stop" not in TS_REASON, \
        "TS_REASON would trip record_close's was_stop substring check"

    # ---- accounting invariants + percentile helper ----
    assert abs((var["h1"] + var["h2"]) - var["net"]) < 1e-9
    assert pctl([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9.1
    assert pctl([], 0.9) is None
    assert stake_of("momo", 0.02) == STAKE
    assert stake_of("momo", 0.20) == STAKE * 0.3
    assert stake_of("trendmomo", 0.20) == STAKE

    print("study_family_time_stop selftest OK (trendmomo level-enter + "
          "one-shot death cross, parked trade time-stopped, slot-days drop, "
          "stop > time > signal priority, was_stop-safe reason, halves add up)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    run()
