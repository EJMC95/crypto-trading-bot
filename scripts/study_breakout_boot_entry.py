#!/usr/bin/env python3
"""
scripts/study_breakout_boot_entry.py — the MomoBreakout books' LEVEL-based
entry vs an EVENT-based (crossing) entry, on Lighter's own 4h tape.

THE FINDING IT TESTS (CHANGELOG 2026-07-21, filed-for-review): at container
boot the breakout family MASS-ENTERS — 14-Jul the two MomoBreakout books
opened 10 positions stamped into two single seconds
(crypto-breakout-4h-lshadow: 6 @ 15:56:55Z, freqtrade-dad-lshadow: 4 @
16:04:30Z), 0 wins / 10 losses, -$8.51 total (ledger
/trades.json?source=paper — those 10 trades are the two books' ENTIRE
trade history to date). Hypothesis filed: the LEVEL entry buys stale
breakouts mid-move at boot; an EVENT (crossing) entry would kill it.

THE MECHANISM IS REAL IN CODE (confirmed by reading): `MomoBreakout
.signals` enters on a LEVEL — `c[i] > dc_high` (roll_max(h,20,i-1))
`and c[i] > ema200 and v>0` — true on EVERY bar price sits above the
prior-20 high, not just the crossing bar; the dedup (`last_sig_ts`) is
in-memory only (NOT in Book.persist()/restore()), so a cold boot
evaluates every coin at once and any coin already above its level enters
immediately, capped only by max_open. The freqtrade original
(MomoBreakoutV1.py:150) is level-based too — the port is faithful.

BUT THE 14-JUL INCIDENT WAS NOT A STALE-LEVEL BURST — MEASURED: on the
bar that closed 12:00Z (the only signal a 15:56:55 evaluation could see:
CandleCache drops the forming bar) ZERO coins in EITHER book were
level-true — there was NO signal to mass-enter on at boot. On the bar
that closed 16:00Z (BTC +3.0% in that one candle) the sim admits EXACTLY
the ledger's ten — dad: BTC,ETH,LINK,NEAR (4/4 slots), breakout:
BTC,ETH,LINK,NEAR,SUI,PEPE (6/6) — and ALL TEN are event-true (fresh
crosses on that candle). So the burst was a market-wide FRESH breakout
candle taken on its signal bar (a steady-running bot takes the same ten;
dad's 16:04:30 entry IS the normal next-candle path). The breakout
book's 15:56:55 stamp is a t0 artifact: `opened_ts` records the LOOP
start, while its 26 governed candle fetches (7 books deep in the cycle)
landed after 16:00:20 and served the fresh bar. A crossing entry does
NOT kill this burst (10 -> 10), and 0W/10L was a failed market-wide
breakout in the bear half, not stale mid-move buying.

METHOD: full Lighter 4h tape (paged 500 bars/call), WIDE_COINS/COINS
minus unlisted, signals computed by calling the SHIPPED
`MomoBreakout.signals` (imported from lighter_family_bot — replay
through the real code, zero port risk) on the bot's own 280-bar sliding
window. EVENT entry = the shipped condition true at i AND false at i-1
(freqtrade crossing semantics; unknown prior bar = no signal). Exits
ported faithfully for BOTH arms: stop -12% intra-bar (gap-through at
open), donchian_breakdown at signal close; stake $50 x the shipped
inverse-vol mult; slots/cooldown/slguard/maxdd per the shipped
protections. Organs excluded (brain mults, fleet veto, panic — identical
for both arms). Price-only P&L (no funding accrual, no spread —
identical treatment both arms; the claim is the RELATIVE ordering).
Fixed-horizon (24h/72h/168h) sensitivity for the boot cohorts as the
exit-model robustness check.

RESULTS 2026-07-22 (tape 2025-03-09..2026-07-22, 500d, 25 coins; halves
= calendar halves of the union grid, split 2025-11-14; BTC regime: full
-22.7%, H1 +15.2%, H2 -32.9% — TWO regimes, one rising + one falling):

  PORTFOLIO SIM (shipped exits + protections, cold start, marked at end):
    rule    net$      H1$      H2$      n   win%    dad$   breakout$
    LEVEL  +28.39  +181.61  -153.21   391  35.0%  +11.90    +16.50
    EVENT  +16.12  +175.39  -159.27   392  34.4%   +9.78     +6.34
    -> EVENT is WORSE on the full window and WORSE in BOTH halves
       (-6.22 H1, -6.05 H2) and in BOTH books. The bar FAILS.

  BOOT CENSUS (cold boot at every 4h boundary; uncapped cohorts;
  single-trade shipped exits) — the STALE cohort is the marginal entry
  the level rule adds at a boot:
    cohort   half     n    avg$/e   win%   fwd24h   fwd72h   fwd168h
    STALE    all     637   +0.213  35.3%   +1.20%   +1.90%   +0.31%
    STALE    h1      369   +0.874  39.0%   +2.13%   +3.27%   +2.95%
    STALE    h2      268   -0.697  30.2%   -0.13%   -0.08%   -3.54%
    FRESH    all    1346   -0.155  33.1%   +0.06%   -0.06%   -0.86%
    FRESH    h1      706   +0.203  35.4%   +0.41%   +0.42%   -0.29%
    FRESH    h2      640   -0.551  30.6%   -0.34%   -0.61%   -1.54%
    -> the stale entries are NET POSITIVE on the tape and BEAT the fresh
       crosses in H1 (+0.874 vs +0.203); only in the falling H2 are they
       modestly worse (-0.697 vs -0.551). Mixed halves — no case.
  BURST AT COLD BOOT (first-cycle entries, max_open-capped, both books):
    LEVEL: 2994 boots, mean 0.86, p90 3, max 10, >=2 entries 17.8%.
    EVENT: mean 0.64, p90 2, max 10, >=2 entries 13.8% (the max-10 boot
    is 14-Jul 16:00Z itself — the crossing rule takes the same ten).

VERDICT: MECHANISM CONFIRMED, REMEDY REFUTED, INCIDENT RE-ATTRIBUTED —
DO NOT ENACT. The level entry + un-persisted dedup really does admit
stale mid-move entries at a cold boot (mean 0.86/boot, 17.8% of boots
>=2), but (a) the crossing entry does NOT kill the 14-Jul burst — all
ten incident entries were fresh crosses on one market-wide 16:00Z
breakout candle, reproduced exactly, and (b) the crossing entry is
WORSE in both halves of the window and in both books (-$12.28 full,
-$6.22 H1, -$6.05 H2): the stale re-entries it removes are net-POSITIVE
on this tape (+$0.213/entry; they re-board established trends after
stop-outs/slot-frees). The 0W/10L outcome was the bear-half regime, not
the boot mechanism. What remains true and actionable elsewhere: 10
same-candle entries is a CONCENTRATION event (one BTC-beta bet x10) —
that is the exposure/pileup lane (fleet_risk exposure view + the 21-Jul
in-cycle headroom), not an entry-signal defect. REGIME COVERAGE: this
window contains a rising half AND a falling half (BTC +15.2% / -32.9%);
the level-vs-event ordering holds in both, so this is NOT a
one-regime-only pass — but absolute profitability of the strategy is
H1-regime-dependent and is NOT what this study judges.

Usage:
    python3 scripts/study_breakout_boot_entry.py --selftest   # offline, no net
    python3 scripts/study_breakout_boot_entry.py              # full run (cached)
    python3 scripts/study_breakout_boot_entry.py --refresh    # refetch tape
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
CACHE = os.path.join(_HERE, ".breakout_boot_cache.json")

TF = "4h"
TF_S = 4 * 3600
DAYS = int(os.environ.get("BBE_DAYS", "500"))           # > tape depth: fetch all
SPAN = fam.CandleCache.SPAN_BARS[TF]                    # the bot's own window (280)
STAKE = 50.0                                            # FAMILY_STAKE_USD default
HORIZONS = (6, 18, 42)                                  # bars: 24h / 72h / 168h

# the two MomoBreakout carriers exactly as shipped (STRATEGIES list)
BOOKS = {
    "freqtrade-dad": dict(coins=list(fam.COINS), max_open=4, stoploss=-0.12),
    "crypto-breakout-4h": dict(coins=list(fam.WIDE_COINS), max_open=6,
                               stoploss=-0.12),
}
STRAT = fam.MomoBreakout("study", tf=TF, stoploss=-0.12, max_open=6, style="s")
PROT = STRAT.protections                                # cooldown/slguard/maxdd

# 14-Jul incident ground truth (ledger rows, /trades.json?source=paper).
# Ledger stamps: breakout book 15:56:55Z (loop-start t0 — its governed candle
# fetches landed after 16:00:20), dad 16:04:30Z. The 12:00Z-closed bar is
# what a 15:56 evaluation could have seen; the 16:00Z-closed bar is what both
# books actually acted on (proved below: 12:00Z has ZERO level-true coins).
INCIDENT_BARS = ("2026-07-14T12:00:00+00:00", "2026-07-14T16:00:00+00:00")
INCIDENT_LEDGER = {
    "crypto-breakout-4h": ["BTC", "ETH", "LINK", "NEAR", "SUI", "PEPE"],
    "freqtrade-dad": ["BTC", "ETH", "LINK", "NEAR"],
}


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


def fetch_candles_4h(mid, days):
    """4h OHLCV paged backward (500-bar cap/call) -> sorted closed-bar lists."""
    out = {}
    end = int(time.time())
    cutoff = end - days * 86400
    seen_oldest = None
    while True:
        rows = _get("/api/v1/candles", market_id=mid, resolution=TF,
                    start_timestamp=end - 500 * TF_S, end_timestamp=end,
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
        seen_oldest, end = oldest, oldest - TF_S
    now = time.time()
    ts_sorted = sorted(t for t in out if t >= cutoff and t + TF_S <= now - 5)
    return {"t": [t for t in ts_sorted],                      # bar OPEN, seconds
            "o": [out[t][0] for t in ts_sorted],
            "h": [out[t][1] for t in ts_sorted],
            "l": [out[t][2] for t in ts_sorted],
            "c": [out[t][3] for t in ts_sorted],
            "v": [out[t][4] for t in ts_sorted]}


def load_universe(refresh=False):
    """{fleet_coin: bars} for every study coin listed on Lighter (family list
    is a subset of WIDE_COINS, so one fetch serves both books)."""
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days", 0) >= DAYS:
            return d["bars"]
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    by_sym = {o["symbol"]: o for o in obs if o.get("status") == "active"}
    bars = {}
    for coin in fam.WIDE_COINS:
        sym, _ = to_lighter(coin)
        m = by_sym.get(sym)
        if not m:
            print(f"  {coin}: unlisted on Lighter — skipped (the bot skips it too)")
            continue
        try:
            b = fetch_candles_4h(int(m["market_id"]), DAYS)
        except Exception as e:  # noqa: BLE001
            print(f"  {coin}: fetch failed ({e}) — skipped")
            continue
        if len(b["t"]) < STRAT.min_bars + 10:
            print(f"  {coin}: only {len(b['t'])} bars — skipped")
            continue
        bars[coin] = b
        print(f"  {coin:6s} {len(b['t']):5d} bars "
              f"({(b['t'][-1] - b['t'][0]) / 86400:.0f}d)")
    json.dump({"days": DAYS, "bars": bars}, open(CACHE, "w"))
    return bars


# ---------------------------------------------------------------------------
# signals — through the SHIPPED code, on the bot's own sliding window

def compute_flags(b):
    """Per bar i: (enter_level, exit_flag, atr_pct, valid) by calling the real
    MomoBreakout.signals on the last <=SPAN bars ending at i — exactly the
    window CandleCache serves the bot. Returns dict of aligned lists."""
    n = len(b["t"])
    ent = [False] * n
    exi = [False] * n
    atr = [None] * n
    valid = [False] * n
    for i in range(n):
        lo = max(0, i + 1 - SPAN)
        win = {k: b[k][lo:i + 1] for k in ("t", "o", "h", "l", "c", "v")}
        sig = STRAT.signals(win, {})
        if sig is None:
            continue
        valid[i] = True
        ent[i] = sig["enter"] is not None
        exi[i] = bool(sig["exit"])
        atr[i] = sig.get("atr_pct")
    # EVENT = shipped condition true at i AND (known and false) at i-1
    ev = [bool(ent[i] and i > 0 and valid[i - 1] and not ent[i - 1])
          for i in range(n)]
    return {"enter_level": ent, "enter_event": ev, "exit": exi,
            "atr_pct": atr, "valid": valid}


def stake_of(atr_pct):
    """The shipped inverse-vol stake mult (MomoBreakout.stake_mult, organ-free
    path): ref 2% ATR, clamp [0.3, 1.0]."""
    m = 1.0
    if atr_pct and atr_pct > 0:
        m *= max(0.3, min(1.0, 0.02 / atr_pct))
    return STAKE * m


# ---------------------------------------------------------------------------
# faithful single-trade exit walk (shared by the portfolio sim + boot census)

def walk_exit(b, fl, j_entry, entry_px, stoploss):
    """From an entry at close of bar j_entry, walk forward with the shipped
    exits: stop (intra-bar, gap-through at open) then donchian_breakdown at
    close. Returns (exit_px, j_exit, reason); marks at last close if unhit."""
    stop_px = entry_px * (1 + stoploss)
    n = len(b["t"])
    for j in range(j_entry + 1, n):
        if b["o"][j] <= stop_px:                 # gap through: fill at open
            return b["o"][j], j, "stop"
        if b["l"][j] <= stop_px:
            return stop_px, j, "stop"
        if fl["exit"][j]:
            return b["c"][j], j, "breakdown"
    return b["c"][n - 1], n - 1, "open_marked"


# ---------------------------------------------------------------------------
# portfolio sim — one book, one entry rule, shipped protections

def sim_book(book, data, flags, rule, half_ts):
    coins = [c for c in book["coins"] if c in data]
    max_open, stoploss = book["max_open"], book["stoploss"]
    idx = {c: {t: i for i, t in enumerate(data[c]["t"])} for c in coins}
    grid = sorted({t for c in coins for t in data[c]["t"]})
    pos = {}                       # coin -> dict(entry, stake, j)
    cooldown = {}                  # coin -> release close-ts (strict <)
    closed = []                    # dicts(ts, pnl, stop) for the guards
    trades = []
    guard_until = 0.0

    def locked(now):
        nonlocal guard_until
        if now < guard_until:
            return True
        sg = PROT.get("slguard")
        win = [c for c in closed if now - c["ts"] <= sg["lookback"] * TF_S]
        if sum(1 for c in win if c["stop"]) >= sg["trades"]:
            guard_until = now + sg["stop"] * TF_S
            return True
        dd = PROT.get("maxdd")
        win = [c for c in closed if now - c["ts"] <= dd["lookback"] * TF_S]
        if len(win) >= dd["trades"]:
            cum = peak = worst = 0.0
            for c in win:
                cum += c["pnl"]
                peak = max(peak, cum)
                worst = max(worst, (peak - cum) / fam.START_EQUITY)
            if worst >= dd["dd"]:
                guard_until = now + dd["stop"] * TF_S
                return True
        return False

    for t_open in grid:
        T = t_open + TF_S                       # decision time = bar close
        # ---- manage helds on the bar that just closed ----
        for coin in list(pos):
            j = idx[coin].get(t_open)
            if j is None:
                continue
            p = pos[coin]
            b = data[coin]
            stop_px = p["entry"] * (1 + stoploss)
            exit_px = reason = None
            if b["o"][j] <= stop_px:
                exit_px, reason = b["o"][j], "stop"
            elif b["l"][j] <= stop_px:
                exit_px, reason = stop_px, "stop"
            elif flags[coin]["exit"][j]:
                exit_px, reason = b["c"][j], "breakdown"
            if reason:
                pnl = p["stake"] * (exit_px / p["entry"] - 1.0)
                closed.append({"ts": T, "pnl": pnl, "stop": reason == "stop"})
                trades.append({"coin": coin, "ts": p["ts"], "pnl": pnl,
                               "reason": reason})
                # cooldown_candles=1 from the close; ties block (a real stop
                # fires mid-candle, so its release always covers the next
                # boundary decision) — identical for both arms
                cooldown[coin] = T + PROT.get("cooldown_candles", 1) * TF_S
                del pos[coin]
        # ---- entries (book coin order, shipped gate order) ----
        if locked(T):
            continue
        for coin in coins:
            if coin in pos or len(pos) >= max_open:
                continue
            j = idx[coin].get(t_open)
            if j is None or not flags[coin][rule][j]:
                continue
            if T <= cooldown.get(coin, 0.0):
                continue
            st = stake_of(flags[coin]["atr_pct"][j])
            pos[coin] = {"entry": data[coin]["c"][j], "stake": st,
                         "j": j, "ts": T}
    # mark whatever is still open at its last close
    for coin, p in pos.items():
        b = data[coin]
        pnl = p["stake"] * (b["c"][-1] / p["entry"] - 1.0)
        trades.append({"coin": coin, "ts": p["ts"], "pnl": pnl,
                       "reason": "open_marked"})
    net = sum(t["pnl"] for t in trades)
    h1 = sum(t["pnl"] for t in trades if t["ts"] < half_ts)
    h2 = net - h1
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return {"net": net, "h1": h1, "h2": h2, "n": len(trades), "wins": wins,
            "trades": trades}


# ---------------------------------------------------------------------------
# boot census

def boot_census(data, flags, half_ts):
    """Uncapped signal-quality cohorts at every possible cold-boot boundary:
    STALE = level-only (what a boot buys mid-move), FRESH = the cross bar.
    Single-trade faithful exits; fixed-horizon fwd returns as sensitivity."""
    rows = []
    for coin, b in data.items():
        fl = flags[coin]
        n = len(b["t"])
        for i in range(n - 1):                 # need at least one fwd bar
            if not fl["valid"][i] or not fl["enter_level"][i]:
                continue
            cohort = "fresh" if fl["enter_event"][i] else "stale"
            entry_px = b["c"][i]
            st = stake_of(fl["atr_pct"][i])
            exit_px, _je, reason = walk_exit(b, fl, i, entry_px, -0.12)
            pnl = st * (exit_px / entry_px - 1.0)
            fwd = {h: (b["c"][i + h] / entry_px - 1.0) if i + h < n else None
                   for h in HORIZONS}
            rows.append({"coin": coin, "ts": b["t"][i] + TF_S, "cohort": cohort,
                         "pnl": pnl, "reason": reason, "fwd": fwd})
    out = {}
    for cohort in ("stale", "fresh"):
        rs = [r for r in rows if r["cohort"] == cohort]
        for half, sel in (("all", rs),
                          ("h1", [r for r in rs if r["ts"] < half_ts]),
                          ("h2", [r for r in rs if r["ts"] >= half_ts])):
            n = len(sel)
            out[(cohort, half)] = {
                "n": n,
                "avg": sum(r["pnl"] for r in sel) / n if n else 0.0,
                "win": (sum(1 for r in sel if r["pnl"] > 0) / n) if n else 0.0,
                "fwd": {h: (sum(r["fwd"][h] for r in sel
                                if r["fwd"][h] is not None)
                            / max(1, sum(1 for r in sel
                                         if r["fwd"][h] is not None)))
                        for h in HORIZONS}}
    return out, rows


def burst_sizes(book, data, flags, rule):
    """Entries admitted in the FIRST cycle after a cold boot at each 4h
    boundary (flat book, empty last_sig_ts — the 14-Jul state), capped by
    max_open in the bot's coin order."""
    coins = [c for c in book["coins"] if c in data]
    idx = {c: {t: i for i, t in enumerate(data[c]["t"])} for c in coins}
    grid = sorted({t for c in coins for t in data[c]["t"]})
    sizes, admitted_at = [], {}
    for t_open in grid:
        adm = []
        for coin in coins:
            if len(adm) >= book["max_open"]:
                break
            j = idx[coin].get(t_open)
            if j is not None and flags[coin][rule][j]:
                adm.append(coin)
        sizes.append(len(adm))
        admitted_at[t_open + TF_S] = adm
    return sizes, admitted_at


# ---------------------------------------------------------------------------

def pct(x):
    return f"{100 * x:.1f}%"


def run():
    refresh = "--refresh" in sys.argv
    print(f"Lighter 4h tape — universe load{' (refresh)' if refresh else ''}:")
    data = load_universe(refresh)
    print(f"{len(data)} coins loaded")
    all_ts = sorted({t for b in data.values() for t in b["t"]})
    t0, t1 = all_ts[0], all_ts[-1] + TF_S
    half_ts = (t0 + t1) / 2
    span_d = (t1 - t0) / 86400

    def iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"window {iso(t0)} .. {iso(t1)} ({span_d:.0f}d), half at {iso(half_ts)}")

    # regime statement (the CLAUDE.md regime-coverage caveat)
    if "BTC" in data:
        c = data["BTC"]["c"]
        tarr = data["BTC"]["t"]
        mid_i = min(range(len(tarr)), key=lambda i: abs(tarr[i] - half_ts))
        print(f"BTC over window: {pct(c[-1] / c[0] - 1)} "
              f"(H1 {pct(c[mid_i] / c[0] - 1)}, H2 {pct(c[-1] / c[mid_i] - 1)}) "
              f"— state the regime; a one-regime pass is a pass in that regime only")

    print("\ncomputing signals through the SHIPPED MomoBreakout.signals "
          f"(window={SPAN} bars, the bot's own CandleCache span)...")
    flags = {coin: compute_flags(b) for coin, b in data.items()}
    n_lvl = sum(sum(f["enter_level"]) for f in flags.values())
    n_ev = sum(sum(f["enter_event"]) for f in flags.values())
    print(f"enter-true bars: LEVEL {n_lvl} vs EVENT (cross) {n_ev} "
          f"({n_lvl - n_ev} stale level-true bars)")

    # ---- portfolio sim ----
    print("\nPORTFOLIO SIM (shipped exits/protections, cold start):")
    print(f"{'book':22s} {'rule':6s} {'net$':>9s} {'H1$':>9s} {'H2$':>9s} "
          f"{'n':>5s} {'win%':>6s}")
    totals = {}
    for rule in ("enter_level", "enter_event"):
        tot = {"net": 0.0, "h1": 0.0, "h2": 0.0, "n": 0, "wins": 0}
        for name, book in BOOKS.items():
            r = sim_book(book, data, flags, rule, half_ts)
            print(f"{name:22s} {rule[6:]:6s} {r['net']:9.2f} {r['h1']:9.2f} "
                  f"{r['h2']:9.2f} {r['n']:5d} "
                  f"{pct(r['wins'] / max(1, r['n'])):>6s}")
            for k in ("net", "h1", "h2", "n", "wins"):
                tot[k] += r[k]
        totals[rule] = tot
        print(f"{'BOTH BOOKS':22s} {rule[6:]:6s} {tot['net']:9.2f} "
              f"{tot['h1']:9.2f} {tot['h2']:9.2f} {tot['n']:5d} "
              f"{pct(tot['wins'] / max(1, tot['n'])):>6s}")
    dl, de = totals["enter_level"], totals["enter_event"]
    print(f"EVENT-minus-LEVEL: full {de['net'] - dl['net']:+.2f} | "
          f"H1 {de['h1'] - dl['h1']:+.2f} | H2 {de['h2'] - dl['h2']:+.2f} "
          f"(both halves must be >= 0 for the bar)")

    # ---- boot census ----
    print("\nBOOT CENSUS (cold boot at every boundary; uncapped cohorts; "
          "single-trade shipped exits):")
    cen, _rows = boot_census(data, flags, half_ts)
    print(f"{'cohort':8s} {'half':4s} {'n':>6s} {'avg$/e':>8s} {'win%':>6s} "
          + "".join(f"{'fwd' + str(h * 4) + 'h%':>9s}" for h in HORIZONS))
    for cohort in ("stale", "fresh"):
        for half in ("all", "h1", "h2"):
            s = cen[(cohort, half)]
            print(f"{cohort:8s} {half:4s} {s['n']:6d} {s['avg']:8.3f} "
                  f"{pct(s['win']):>6s}"
                  + "".join(f"{100 * s['fwd'][h]:9.2f}" for h in HORIZONS))

    # ---- burst sizes ----
    print("\nBURST AT COLD BOOT (first-cycle entries, max_open-capped):")
    per_rule_adm = {}
    for rule in ("enter_level", "enter_event"):
        merged = []
        per_book_adm = {}
        for name, book in BOOKS.items():
            sizes, adm = burst_sizes(book, data, flags, rule)
            per_book_adm[name] = adm
            merged = [a + c for a, c in zip(merged, sizes)] if merged else sizes
        per_rule_adm[rule] = per_book_adm
        srt = sorted(merged)
        n = len(srt)
        ge2 = sum(1 for s in srt if s >= 2) / n
        print(f"  {rule[6:]:6s}: boots={n} mean={sum(srt) / n:.2f} "
              f"p50={srt[n // 2]} p90={srt[int(0.9 * n)]} max={srt[-1]} "
              f">=2 entries: {pct(ge2)}")

    # ---- 14-Jul incident reproduction (both candidate bars, both rules) ----
    print("\n14-JUL INCIDENT REPRODUCTION (ledger: breakout book 6 @ "
          "15:56:55Z t0-stamp, dad 4 @ 16:04:30Z):")
    for close_iso in INCIDENT_BARS:
        T = int(datetime.fromisoformat(close_iso).timestamp())
        print(f"  bar closed {close_iso[:16]}Z:")
        for name, actual in INCIDENT_LEDGER.items():
            lvl = per_rule_adm["enter_level"][name].get(T)
            ev = per_rule_adm["enter_event"][name].get(T)
            verdict = ("EXACT ledger match" if lvl == actual
                       else f"no match (ledger {actual})")
            print(f"    {name:20s} LEVEL admits {lvl or 'NONE'} — {verdict}; "
                  f"EVENT admits {ev or 'NONE'}"
                  + (" — the crossing rule takes the SAME entries"
                     if ev == actual else ""))
    print("  -> the 12:00Z bar (the only signal visible to a 15:56:55 "
          "evaluation) admits NOTHING: the incident was the FRESH 16:00Z "
          "cross candle, stamped with the loop-start t0.")

    print("\nDone. Header table numbers come from this output — re-run with "
          "--refresh rather than re-arguing from prose.")


# ---------------------------------------------------------------------------
# selftest — OFFLINE, fixtures only

def _mk_bars(closes, hi_off=0.005, lo_off=0.005, vol=1.0):
    n = len(closes)
    return {"t": [1_700_000_000 + i * TF_S for i in range(n)],
            "o": list(closes),
            "h": [c * (1 + hi_off) for c in closes],
            "l": [c * (1 - lo_off) for c in closes],
            "c": list(closes),
            "v": [vol] * n}


def _selftest():
    # tape: 300 flat bars then a +8% breakout bar, then +1%/bar for 40 bars
    # (steep enough that every bar closes above the prior-20 high -> the
    # LEVEL condition stays true bar after bar), then a collapse.
    closes = [100.0] * 300
    px = 108.0
    for _ in range(41):
        closes.append(px)
        px *= 1.01
    for _ in range(6):
        px *= 0.90
        closes.append(px)
    b = _mk_bars(closes)
    fl = compute_flags(b)

    cross_i = 300                                  # the breakout bar
    assert fl["enter_level"][cross_i], "cross bar must satisfy the level"
    assert fl["enter_event"][cross_i], "cross bar IS the event"
    run_lvl = [i for i in range(cross_i + 1, cross_i + 40)
               if fl["enter_level"][i]]
    run_ev = [i for i in range(cross_i + 1, cross_i + 40)
              if fl["enter_event"][i]]
    assert len(run_lvl) >= 30, f"steep run must stay level-true ({len(run_lvl)})"
    assert run_ev == [], "no second cross -> the event never re-fires"
    # THE BOOT CLAIM in miniature: a cold boot mid-run enters under LEVEL,
    # not under EVENT — the whole finding in two asserts.
    mid = cross_i + 10
    assert fl["enter_level"][mid] and not fl["enter_event"][mid]

    # event needs a KNOWN prior bar: earliest valid bar can't fire the event
    first_valid = next(i for i in range(len(closes)) if fl["valid"][i])
    assert not fl["enter_event"][first_valid]

    # faithful exits: stop -12% intra-bar with gap-through at open
    bb = _mk_bars([100.0] * 240 + [110.0, 95.0, 80.0])
    fbb = compute_flags(bb)
    n = len(bb["t"])
    exit_px, j, reason = walk_exit(bb, fbb, n - 3, 110.0, -0.12)
    assert reason == "stop", reason
    # bar n-2 closes 95: low 95*(1-.005)=94.52 <= stop 96.8, open 95 <= 96.8
    # -> gap-through fills at the OPEN, not the stop print
    assert j == n - 2 and exit_px == bb["o"][n - 2], (exit_px, j)

    # breakdown exit at signal close when the stop is never touched
    down = [100.0] * 240 + [101.0] + [99.5 - 0.4 * k for k in range(8)]
    bd = _mk_bars(down, lo_off=0.001)
    fbd = compute_flags(bd)
    ep, jj, rr = walk_exit(bd, fbd, 240, 101.0, -0.99)   # stop unreachable
    assert rr == "breakdown" and ep == bd["c"][jj], (ep, jj, rr)

    # burst census: LEVEL admits (capped), EVENT admits none mid-run
    data = {"BTC": b, "ETH": b}
    flags = {"BTC": fl, "ETH": fl}
    book = {"coins": ["BTC", "ETH"], "max_open": 1, "stoploss": -0.12}
    sizes_l, adm_l = burst_sizes(book, data, flags, "enter_level")
    sizes_e, _ = burst_sizes(book, data, flags, "enter_event")
    boot_T = b["t"][mid] + TF_S
    assert adm_l[boot_T] == ["BTC"], "max_open=1 caps the burst, coin order"
    assert max(sizes_l) == 1 and sum(sizes_l) > sum(sizes_e), \
        "level boots must admit more than event boots on this tape"

    # portfolio sim smoke: both rules trade the cross once; level nets the
    # same trade (entered at the cross, exited on the collapse) — and the
    # sim runs end-to-end with guards/cooldown engaged
    half = b["t"][len(b["t"]) // 2]
    r_l = sim_book(book, {"BTC": b}, {"BTC": fl}, "enter_level", half)
    r_e = sim_book(book, {"BTC": b}, {"BTC": fl}, "enter_event", half)
    assert r_l["n"] >= 1 and r_e["n"] >= 1
    assert abs((r_l["h1"] + r_l["h2"]) - r_l["net"]) < 1e-9

    # stake mult: the shipped clamp [0.3, 1.0] on 2%/ATR
    assert stake_of(0.02) == STAKE
    assert stake_of(0.20) == STAKE * 0.3
    assert stake_of(None) == STAKE

    print("study_breakout_boot_entry selftest OK (level persists mid-run, "
          "event fires once at the cross, boot admits level-only, exits "
          "faithful, sim halves add up)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    run()
