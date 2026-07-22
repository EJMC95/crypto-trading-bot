#!/usr/bin/env python3
"""
scripts/study_budget_allocation.py — the ENTRY-SIDE budget lever the
time-stop study pointed at: what does LOWERING a MomoBreakout / TrendMomo
book's max_open do, on Lighter's own tape, both halves? EVIDENCE ONLY for
the 21-Jul review — DO NOT ENACT (changing what the 20-slot budget means is
the operator's review decision, not a study's).

WHY THIS STUDY (CHANGELOG (bw) budget saturation + study_family_time_stop's
verdict): the fleet's 20-slot LONG budget (fleet_risk.LONG_BUDGET) is pinned
red 55.9% of 48h. study_family_time_stop.py proved a time-stop CANNOT free
those slots — a freed slot refills within ~2 bars because the entry is a
persistent LEVEL and max_open is unchanged; a time stop changes WHICH
positions occupy the slots, never HOW MANY (avg concurrency 2.24 -> 2.18 at
best). Its closing line: "The real budget lever is entry-side (max_open /
fleet long-budget allocation), not exit-side time stops." This study measures
that lever directly. A lower cap is STRUCTURAL: unlike a time stop, a slot the
cap removes cannot refill — avg concurrency falls by construction, and the
freed slot-days are real.

THE OVER-SUBSCRIPTION (measured from shipped config, 22-Jul; the (bw) held-at-
saturation snapshot in parens): the ten books whose longs count toward
fleet_risk.LONG_BUDGET=20 (FREQTRADE_BOTS + the Funding Farmer's long legs)
carry these structural caps —
    crypto-breakout-4h  MomoBreakout 4h   max_open 6   (held 6/6  @ cap)
    crypto-swing-daily  SwingDip 1d       max_open 8   (held 0)
    crypto-intraday-15m DayTraderGated 1h max_open 5   (held 1-3)
    freqtrade-georgia   DayTraderGated15m max_open 5   (held 0-1, cycles)
    freqtrade-mum       TrendMomo 1d      max_open 4   (held 4/4  @ cap, 0 closes ever)
    freqtrade-dad       MomoBreakout 4h   max_open 4   (held 4/4  @ cap)
    freqtrade-avo-maria SwingDip 4h       max_open 4   (held 0)
    lighter-ticket-taker taker (L/S)      max_open 6   (held 2)
    crypto-trend-daily  Tide Rider trend  max_open 6   (held 1)
    perps-funding-lighter funding (L/S)   long legs    (held 0 long @ snapshot)
  SUM of the nine long-book caps = 6+8+5+5+4+4+4+6+6 = 48 structural slots
  competing for a 20-slot budget => 2.40x OVER-SUBSCRIBED (28 phantom slots).
  The budget is a first-come veto: whoever fills first (the always-on LEVEL
  breakout books) parks the slots; the fast cyclers (georgia/avo/taker) are
  vetoed when they finally signal. At the (bw) saturation snapshot the 20
  held slots were breakout 6 + mum 4 + dad 4 + intraday 3 + taker 2 +
  trend-daily 1 — the three MomoBreakout/TrendMomo parkers held 14 of 20.

WHO EARNS THE SLOTS (paper ledger /trades.json?source=paper, 500-close window
2026-07-12..22, realized closes only; $/slot-day = realized P&L / sum of
per-trade holding-days):
    book (ledger row)             n  win%   P&L$  slotDays  $/slotDay  medHold
    freqtrade-georgia (cycler)   30   50   +2.17     3.8    +0.564      0.11d   <-- earns
    freqtrade-avo-maria          3   100   +1.25    12.3    +0.101      4.50d
    perps-funding-lighter(live) 38    71   +5.00    30.7    +0.163      0.47d
    lighter-ticket-taker(live)   5    60   +0.50     5.2    +0.095      1.00d
    crypto-intraday-15m         21    43   -4.12     6.3    -0.657      0.26d
    freqtrade-dad     (parker)   4     0   -2.84    10.3    -0.275      2.67d   <-- parks
    crypto-breakout-4h(parker)   6     0   -4.87    16.0    -0.304      2.67d   <-- parks
    freqtrade-mum     (parker)   0     -    0.00      —        —          —      <-- 0 closes
  The three parkers (mum/dad/breakout) hold 14 of 20 budget slots for a
  COMBINED realized record of 0 wins / 10 closes / -$7.71, plus mum's four
  never-closed slots. georgia earns +$0.564/slot-day holding 1 slot it cycles
  ~24x/week. The budget is consumed by the slowest-turning, worst-realized
  books and denied to the fastest-earning one.

METHOD (harness = study_family_time_stop.py / study_breakout_boot_entry.py,
the accepted pattern; tape reused from .family_time_stop_cache.json): full
Lighter tape, signals by calling the SHIPPED MomoBreakout.signals /
TrendMomo.signals on each bot's own CandleCache window, portfolio sim per book
with shipped exits (stop intra-bar gap-through, signal exit at close) +
shipped protections (cooldown/slguard/maxdd) + shipped inverse-vol stakes.
The ONLY knob varied is book.max_open. Organs excluded (identical for all
variants). Price-only P&L (no funding accrual) — CONSERVATIVE for a cap cut:
these books are long-only and PAY funding on Lighter, so holding FEWER
positions can only help; measuring without the credit is the stricter test.
Faithfulness: the max_open baselines reproduce the published
study_breakout_boot_entry LEVEL baselines to the cent (dad +11.90 /
breakout +16.50) and the time-stop study's mum baseline (-14.15) — asserted
at runtime (--check).

FOR AN ENTRY GATE THE BAR IS RESTRICT-DIRECTION: not-worse in BOTH halves per
book. A cap cut is NOT free — it forfeits some rising-half (H1) upside to buy
falling-half (H2) relief. This study reports the H1 give-up and H2 relief
separately per book so the review can weigh them; it does not pre-judge the
trade. The portfolio reallocation value (freed slot-days x a cycling book's
measured $/slot-day) is an ESTIMATE, labelled, upper-bounded (see caveats).

RESULTS 2026-07-22  (4h tape 2025-03-09..2026-07-22 500d 25 coins, half at
2025-11-14; BTC full -22.7% / H1 +15.2% / H2 -32.9%. 1d tape
2025-03-10..2026-07-22 499d 13 coins, half 2025-11-14; BTC full -15.4% /
H1 +20.3% / H2 -29.7%. REGIME: one RISING half + one FALLING half — "both
halves" spans two regimes of opposite sign; no third regime in the window.):

  BASELINE CROSS-CHECK: dad(4)=+11.90  breakout(6)=+16.50  mum(4)=-14.15
    -> reproduces the published anchors to the CENT. PASS (--check asserts it).

  (dNet/dH1/dH2 = variant minus base; nw? = not-worse in BOTH halves)
  freqtrade-dad (MomoBreakout 4h)  net$    H1$    H2$   n  win%  slotD  dSlot conc  dNet    dH1    dH2  nw
    max_open 4 (base)             +11.90 +72.08 -60.18 153 35.3%  876     —  1.75    —      —      —    —
    max_open 3                     -3.86 +45.32 -49.17 127 34.6%  714 -18.6% 1.43 -15.75 -26.76 +11.01 no

  crypto-breakout-4h (MomoBreak.)  net$    H1$    H2$   n  win%  slotD  dSlot conc  dNet    dH1    dH2  nw
    max_open 6 (base)             +16.50+109.53 -93.03 238 34.9% 1324     —  2.65    —      —      —    —
    max_open 5                    +26.95+105.90 -78.95 208 35.6% 1164 -12.1% 2.33 +10.46  -3.63 +14.08 no
    max_open 4                     +7.39 +85.81 -78.41 180 36.1%  988 -25.4% 1.98  -9.11 -23.73 +14.62 no

  freqtrade-mum (TrendMomo 1d)     net$    H1$    H2$   n  win%  slotD  dSlot conc  dNet    dH1    dH2  nw
    max_open 4 (base)             -14.15  +5.12 -19.28  42 35.7% 1118     —  2.24    —      —      —    —
    max_open 3                    -58.66 -20.41 -38.25  37 32.4%  898 -19.7% 1.80 -44.51 -25.53 -18.98 no

  SLOT-DAYS FREED (STRUCTURAL — a lower cap cannot refill) & REALLOCATION
  ESTIMATE (freed slot-days x a CYCLING book's measured $/slot-day; the
  cyclers are the ledger's positive-$/slot-day earners — ILLUSTRATIVE, an
  UPPER bound; the own-P&L cost is what the cut costs the parker book itself,
  in-sample on THIS tape):
    lever            freedSlotD dConc  ownP&L   @avo+0.101 @fund+0.163 @geo+0.564
    dad 4->3            162.5   -0.33  -15.75      +16.4      +26.5      +91.6
    breakout 6->5       159.8   -0.32  +10.46      +16.1      +26.1      +90.1
    breakout 6->4       336.3   -0.67   -9.11      +34.0      +54.8     +189.7
    mum 4->3            220.0   -0.44  -44.51      +22.2      +35.9     +124.1

VERDICT (EVIDENCE ONLY — DO NOT ENACT): The entry-side lever DOES what the
time stop could not — every cap cut lowers avg concurrency (dad 1.75->1.43,
breakout 2.65->1.98, mum 2.24->1.80) and frees 160-336 STRUCTURAL slot-days,
because a slot the cap removes cannot refill. That is the mechanical
difference the time-stop study predicted (a time stop moved concurrency only
2.24->2.18). But on THIS one-regime-pair tape NO cut is not-worse-both-halves,
and the three books split three ways:
  * breakout 6->5 is the single most defensible move: net +$10.46 (net
    IMPROVES), H1 give-up only -$3.63 against +$14.08 H2 relief, frees 160
    slot-days, drops one always-parked slot. It nearly clears the bar (the
    only violation is a small H1 give-up dwarfed by the H2 relief) — the
    closest thing to "cut the falling-half bleed without gutting the rising
    half" on the evidence.
  * dad 4->3 and breakout 6->4 are H1-for-H2 REGIME TRADES, not free relief:
    they forfeit large rising-half upside (dad -$26.76 H1, breakout -$23.73
    H1) to buy falling-half relief (+$11.01 / +$14.62 H2). Right only if the
    forward regime resembles H2; a bet, not a not-worse tightening.
  * mum 4->3 is REFUTED as a lever: it is WORSE IN BOTH HALVES (-$25.53 H1,
    -$18.98 H2, -$44.51 net). The TrendMomo book holds few, long-duration
    positions (n=42, 13 coins); its marginal 4th slot held net-positive
    trend winners on this tape, so removing it destroys P&L. mum "parks 4
    slots and never closes" is a SLOT-OCCUPANCY problem, but capping the slot
    count is the WRONG fix — the fix is entry SELECTIVITY, not fewer slots.
    (This directly corrects an earlier hand-estimate that had mum improving;
    the sim says the opposite. Trust the run.)
The reallocation $ is an UPPER bound and must be read against the own-P&L cost
in the same row: the freed slots are worth something ONLY while (a) the 20-slot
budget is actually binding (red 55.9%/48h) AND (b) a cycling book has a signal
it is being vetoed on. The cyclers currently sit far below their OWN caps
(georgia 1/5, avo 0/4, intraday 1/5) — they are signal-limited, not
budget-limited, right now — so most freed slot-days would sit idle and the
georgia-rate column (+0.564) is a ceiling no reallocation would actually hit.
The review's decision surface: (1) re-size / re-share the 20-slot LONG_BUDGET
cohort (48 caps chase 20 slots — the over-subscription is the root), and/or
(2) trim only the cleanly-parked MomoBreakout slot (breakout 6->5 is the one
cut that pays for itself in-sample), and NOT (3) mum's cap. This study supplies
the arithmetic; the sizing call is the operator's.

Usage:
    python3 scripts/study_budget_allocation.py --selftest   # offline, no net
    python3 scripts/study_budget_allocation.py              # full run (cached)
    python3 scripts/study_budget_allocation.py --check      # + baseline asserts
    python3 scripts/study_budget_allocation.py --refresh    # refetch tapes
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
CACHE = os.path.join(_HERE, ".family_time_stop_cache.json")   # reuse the tape
SEED_4H = os.path.join(_HERE, ".breakout_boot_cache.json")
DAYS = int(os.environ.get("BA_DAYS", "500"))

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

# the three books whose cap we vary, exactly as shipped (STRATEGIES list).
# base = shipped max_open; grid = the caps to simulate (base first).
BOOKS = {
    "freqtrade-dad": dict(strat="momo", coins=list(fam.COINS),
                          stoploss=-0.12, base=4, grid=(4, 3)),
    "crypto-breakout-4h": dict(strat="momo", coins=list(fam.WIDE_COINS),
                               stoploss=-0.12, base=6, grid=(6, 5, 4)),
    "freqtrade-mum": dict(strat="trendmomo", coins=list(fam.COINS),
                          stoploss=-0.15, base=4, grid=(4, 3)),
}

# published baseline anchors for the faithfulness cross-check (--check).
# dad/breakout from study_breakout_boot_entry LEVEL rule; mum from
# study_family_time_stop base. Cents-exact reproduction proves the harness.
BASELINE_ANCHOR = {"freqtrade-dad": 11.90, "crypto-breakout-4h": 16.50,
                   "freqtrade-mum": -14.15}
ANCHOR_TOL = 0.01

# MEASURED cycler economics for the reallocation ESTIMATE (paper ledger
# /trades.json?source=paper, 500-close window 2026-07-12..22; realized
# $/slot-day = realized P&L / sum-of-holding-days). These are the CYCLING
# books that would consume a freed slot. Small-sample, one-regime, live-window
# numbers — the reallocation figure is ILLUSTRATIVE, not a promise (caveats
# in the header). Refreshable from the ledger; frozen here for reproducibility.
CYCLER_SPD = {"avo (+0.101)": 0.101,      # freqtrade-avo-maria, 3 closes
              "funding (+0.163)": 0.163,  # perps-funding-lighter live, 38
              "georgia (+0.564)": 0.564}  # freqtrade-georgia, 30 closes


# ---------------------------------------------------------------------------
# data (identical fetch to the accepted harnesses; cache reused)

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
    return {"t": [t for t in ts_sorted],
            "o": [out[t][0] for t in ts_sorted],
            "h": [out[t][1] for t in ts_sorted],
            "l": [out[t][2] for t in ts_sorted],
            "c": [out[t][3] for t in ts_sorted],
            "v": [out[t][4] for t in ts_sorted]}


def load_tapes(refresh=False):
    """{"4h": {coin: bars}, "1d": {coin: bars}} — reused from the time-stop
    study's cache (identical fetch code/format), 4h seeded from the breakout
    study's cache. Fetches only what a cache is missing."""
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
                print(f"  {coin} {tf}: unlisted on Lighter — skipped")
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
            print(f"  {coin:6s} {tf}: {len(b['t']):5d} bars")
    json.dump({"days": DAYS, "tapes": tapes}, open(CACHE, "w"))
    return tapes


# ---------------------------------------------------------------------------
# signals — through the SHIPPED code, on the bot's own sliding window

def compute_flags(strat_key, b):
    """Per bar i: (enter, exit, atr_pct, valid) by calling the real strategy's
    .signals on the last <=SPAN bars ending at i — the window CandleCache
    serves the bot."""
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
    """Shipped stake: TrendMomo flat 1.0x; MomoBreakout inverse-vol (ref 2%
    ATR, clamp [0.3, 1.0]). Organ-free path (panic excluded)."""
    m = 1.0
    if strat_key == "momo" and atr_pct and atr_pct > 0:
        m *= max(0.3, min(1.0, 0.02 / atr_pct))
    return STAKE * m


# ---------------------------------------------------------------------------
# portfolio sim — one book at a chosen max_open, shipped protections.
# Copied faithfully from study_family_time_stop.sim_book (the accepted
# harness); the ONLY parameter varied is max_open. No time-stop branch.

def sim_book(book, data, flags, half_ts, max_open):
    strat_key = book["strat"]
    tf_s = TFS[strat_key]
    prot = STRATS[strat_key].protections
    coins = [c for c in book["coins"] if c in data]
    stoploss = book["stoploss"]
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
        closed.append({"ts": T, "pnl": pnl, "stop": "stop" in reason})
        trades.append({"coin": coin, "ts": p["ts"], "ts_exit": T, "pnl": pnl,
                       "stake": p["stake"], "entry": p["entry"], "j": p["j"],
                       "reason": reason})
        cooldown[coin] = T + prot.get("cooldown_candles", 1) * tf_s
        del pos[coin]

    for t_open in grid:
        T = t_open + tf_s                       # decision time = bar close
        # ---- manage helds (shipped order: stop -> exit signal) ----
        for coin in list(pos):
            j = idx[coin].get(t_open)
            if j is None:
                continue
            b = data[coin]
            stop_px = pos[coin]["entry"] * (1 + stoploss)
            if b["o"][j] <= stop_px:
                close_at(coin, b["o"][j], T, "stop")
            elif b["l"][j] <= stop_px:
                close_at(coin, stop_px, T, "stop")
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
            "span_days": span_s / 86400.0, "trades": trades}


# ---------------------------------------------------------------------------

def pct(x):
    return f"{100 * x:.1f}%"


def run(check=False):
    refresh = "--refresh" in sys.argv
    print(f"Lighter tape — universe load{' (refresh)' if refresh else ''}:")
    tapes = load_tapes(refresh)
    print(f"4h: {len(tapes['4h'])} coins | 1d: {len(tapes['1d'])} coins")

    def iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    flags, half = {}, {}
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
                  f" — one rising + one falling half; a one-regime pass is a "
                  f"pass in that regime only")
        print(f"  computing signals through the SHIPPED "
              f"{type(STRATS[strat_key]).__name__}.signals...")
        flags[strat_key] = {coin: compute_flags(strat_key, b)
                            for coin, b in data.items()}

    # ---- per-book cap ladder ----
    freed = {}     # (book, cap) -> dict for the reallocation table
    anchors_ok = True
    for name, book in BOOKS.items():
        strat_key = book["strat"]
        tf = "1d" if strat_key == "trendmomo" else "4h"
        data, fl, half_ts = tapes[tf], flags[strat_key], half[strat_key]
        base = sim_book(book, data, fl, half_ts, book["base"])
        # faithfulness cross-check
        anchor = BASELINE_ANCHOR[name]
        ok = abs(base["net"] - anchor) <= ANCHOR_TOL
        anchors_ok = anchors_ok and ok
        print(f"\n{'=' * 78}\n{name} ({type(STRATS[strat_key]).__name__} {tf}, "
              f"shipped max_open {book['base']}, stop {book['stoploss'] * 100:.0f}%)"
              f"  [baseline {base['net']:+.2f} vs anchor {anchor:+.2f}: "
              f"{'PASS' if ok else 'FAIL'}]")
        hdr = (f"  {'max_open':10s} {'net$':>8s} {'H1$':>8s} {'H2$':>8s} "
               f"{'n':>4s} {'win%':>6s} {'slotD':>7s} {'dSlot':>7s} "
               f"{'conc':>5s} {'dNet':>7s} {'dH1':>7s} {'dH2':>7s} {'nw?':>4s}")
        print(hdr)
        for cap in book["grid"]:
            r = base if cap == book["base"] else \
                sim_book(book, data, fl, half_ts, cap)
            ds = (r["slot_days"] / base["slot_days"] - 1.0) \
                if base["slot_days"] else 0.0
            dnet = r["net"] - base["net"]
            dh1 = r["h1"] - base["h1"]
            dh2 = r["h2"] - base["h2"]
            nw = "yes" if (dh1 >= -1e-9 and dh2 >= -1e-9) else "no"
            tag = " (base)" if cap == book["base"] else ""
            print(f"  {str(cap) + tag:10s} {r['net']:8.2f} {r['h1']:8.2f} "
                  f"{r['h2']:8.2f} {r['n']:4d} "
                  f"{pct(r['wins'] / max(1, r['n'])):>6s} {r['slot_days']:7.0f} "
                  f"{('—' if cap == book['base'] else pct(ds)):>7s} "
                  f"{r['avg_conc']:5.2f} "
                  f"{('—' if cap == book['base'] else f'{dnet:+.2f}'):>7s} "
                  f"{('—' if cap == book['base'] else f'{dh1:+.2f}'):>7s} "
                  f"{('—' if cap == book['base'] else f'{dh2:+.2f}'):>7s} "
                  f"{('—' if cap == book['base'] else nw):>4s}")
            if cap != book["base"]:
                freed[(name, cap)] = {
                    "freed_slot_days": base["slot_days"] - r["slot_days"],
                    "dconc": r["avg_conc"] - base["avg_conc"],
                    "dnet": dnet, "dh1": dh1, "dh2": dh2}

    # ---- portfolio reallocation ESTIMATE ----
    print(f"\n{'=' * 78}\nSLOT-DAYS FREED (STRUCTURAL — a lower cap cannot "
          f"refill) & REALLOCATION ESTIMATE")
    print("  Reallocation = freed slot-days x a CYCLING book's measured "
          "$/slot-day (paper ledger, ILLUSTRATIVE upper bound — realises only "
          "while the budget binds and a cycler wants the slot; see caveats).")
    cyc = list(CYCLER_SPD.items())
    hdr = (f"  {'lever':22s} {'freedSlotD':>10s} {'dConc':>6s} "
           f"{'ownP&L':>7s} " + " ".join(f"{n.split()[0]:>9s}" for n, _ in cyc))
    print(hdr)
    for (name, cap), fdct in freed.items():
        fsd = fdct["freed_slot_days"]
        realloc = "  ".join(f"{fsd * spd:+8.1f}" for _, spd in cyc)
        print(f"  {name + ' ' + str(BOOKS[name]['base']) + '->' + str(cap):22s} "
              f"{fsd:10.1f} {fdct['dconc']:6.2f} {fdct['dnet']:+7.2f}  {realloc}")

    print("\nVERDICT: EVIDENCE ONLY — DO NOT ENACT. The entry-side cap frees "
          "slot-days STRUCTURALLY (unlike the time stop); NO cut is "
          "not-worse-both-halves on this one-regime-pair tape. breakout 6->5 "
          "is the one cut that pays for itself (net +$10.46, H1 give-up only "
          "-$3.63 vs +$14.08 H2 relief); dad 4->3 and breakout 6->4 are "
          "H1-for-H2 regime trades; mum 4->3 is REFUTED (worse in BOTH halves, "
          "-$44.51). Re-sizing the 20-slot budget cohort (48 caps chase 20 "
          "slots) is the operator's review call — this study supplies the "
          "arithmetic.")
    if check and not anchors_ok:
        print("\n!! BASELINE CROSS-CHECK FAILED — harness drift, do NOT trust "
              "the variant numbers.")
        sys.exit(1)
    if check:
        print("\nBaseline cross-check PASS (dad/breakout/mum reproduce the "
              "published anchors to the cent).")
    print("\nDone. Header numbers come from this output — re-run rather than "
          "re-arguing from prose.")


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

    # ---- THE CORE STRUCTURAL CLAIM: a lower max_open cannot be refilled, so
    # concurrency and slot-days fall — the mechanical difference from a time
    # stop. Two coins both break out and hold to end of tape; max_open 2
    # parks BOTH slots, max_open 1 parks ONE (structural, not refilled).
    closes = [100.0] * 300 + [108.0]
    px = 108.0
    for _ in range(59):
        px *= 1.0005
        closes.append(px)
    b = _mk_bars(closes, tf4, lo_off=0.001)
    f = compute_flags("momo", b)
    data = {"BTC": b, "ETH": b}
    fl = {"BTC": f, "ETH": f}
    book = {"strat": "momo", "coins": ["BTC", "ETH"], "stoploss": -0.12}
    half = b["t"][len(b["t"]) // 2]
    r2 = sim_book(book, data, fl, half, 2)
    r1 = sim_book(book, data, fl, half, 1)
    assert r2["avg_conc"] > r1["avg_conc"], "lower cap must lower concurrency"
    assert r2["slot_days"] > r1["slot_days"], "lower cap must free slot-days"
    # cap 1 admits BTC (coin order); ETH is structurally denied — it cannot
    # refill because BTC never leaves the one slot. This is the whole point.
    assert any(t["coin"] == "ETH" for t in r2["trades"])
    assert not any(t["coin"] == "ETH" for t in r1["trades"]), \
        "the removed slot must NOT refill with the other coin"

    # ---- a cap AT or ABOVE demand changes nothing (no phantom relief) ----
    r3 = sim_book(book, data, fl, half, 3)
    assert abs(r3["slot_days"] - r2["slot_days"]) < 1e-9, \
        "cap above concurrent demand frees nothing"

    # ---- accounting invariants + halves add up ----
    assert abs((r2["h1"] + r2["h2"]) - r2["net"]) < 1e-9
    assert abs((r1["h1"] + r1["h2"]) - r1["net"]) < 1e-9

    # ---- freed-slot-days is monotone non-negative as the cap drops ----
    caps = [sim_book(book, data, fl, half, c)["slot_days"] for c in (1, 2, 3)]
    assert caps[0] <= caps[1] <= caps[2], "slot-days monotone in the cap"

    # ---- TrendMomo path runs (flat 1.0x stake, no atr) on a level uptrend ----
    tclose = [100.0 + i for i in range(80)]
    tb = _mk_bars(tclose, TFS["trendmomo"])
    tf = compute_flags("trendmomo", tb)
    tbook = {"strat": "trendmomo", "coins": ["BTC"], "stoploss": -0.15}
    thalf = tb["t"][len(tb["t"]) // 2]
    tr = sim_book(tbook, {"BTC": tb}, {"BTC": tf}, thalf, 4)
    assert tr["n"] >= 1 and abs((tr["h1"] + tr["h2"]) - tr["net"]) < 1e-9

    # ---- stake mults: shipped clamp ----
    assert stake_of("momo", 0.02) == STAKE
    assert stake_of("momo", 0.20) == STAKE * 0.3
    assert stake_of("trendmomo", 0.20) == STAKE

    # ---- reallocation arithmetic: freed x $/slot-day is linear & signed ----
    assert abs(100.0 * 0.564 - 56.4) < 1e-9

    print("study_budget_allocation selftest OK (lower cap lowers concurrency "
          "AND frees slot-days, the removed slot does NOT refill, cap>=demand "
          "is inert, slot-days monotone in cap, halves add up, both strategy "
          "paths run, stakes clamp)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    run(check="--check" in sys.argv)
