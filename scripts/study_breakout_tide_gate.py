#!/usr/bin/env python3
"""
scripts/study_breakout_tide_gate.py — PORT PARITY: does the freqtrade
MomoBreakoutV1 BTC-TIDE entry gate (added 2026-07-14) carry its edge onto
the Lighter port, on Lighter's own 4h tape?

THE PARITY GAP (confirmed by reading the shipped code):
  * freqtrade original MomoBreakoutV1.py (populate_entry_trend, lines 148-156)
    gates the breakout on a MARKET TIDE:
        (close > dc_high) & (close > ema_trend) & (btc_tide_up == 1) & vol
    where btc_tide_up = (BTC.close > EMA(BTC, 200)) on the 4h informative pair
    (trend_ema.value = 200), FAIL-SAFE CLOSED (fillna 0 -> off-tide). Rationale
    in the header: 3-13 Jul both carriers went 2W/9L as 11 pairs broke above
    their OWN 200-EMA and died in a market-wide fakeout wave; the per-pair EMA
    can't see the tide, a BTC-EMA200 gate can (backtest PF 0.79 -> 1.43).
  * the Lighter port lighter_family_bot.py MomoBreakout.signals (466-481)
    NEVER received it:
        enter = (c[i] > dc_high and c[i] > ema_t[i] and v[i] > 0)
    no tide term. The port HAS a btc_regime_up(cache) helper (line 787) but it
    computes BTC EMA50 > EMA200 (a golden CROSS) and is consumed ONLY by
    DayTraderGated via extra={"btc_regime_up": ...} — a DIFFERENT rule from the
    MomoBreakout original's close > EMA200. So the gate must be PORTED, not
    borrowed. This study ports the original's EXACT rule (BTC close > BTC 4h
    EMA200, fail-safe closed) and A/Bs it on the accepted harness.

PARITY AUDIT OF THE OTHER THREE FAMILY PORTS (entry-gate class, reported not
fixed): NO gap of this class found.
  * TrendMomo (mum) vs TrendMomoV1: entry = sma_fast>sma_slow & close>sma_slow
    & vol — matches; the original's newest entry edit is the 07-03 chop filter
    (close>sma_slow), present in the port. Its 07-14 edit was sizing+veto only
    ("entry/exit logic untouched"). No BTC-tide gate exists to miss.
  * SwingDip (avo-maria, swing-daily) vs SwingDipV1: entry = ema50>ema200 &
    rsi<42 & close<bb_lower & vol — matches. Its trend gate is PER-PAIR
    (ema50>ema200), never a BTC-market tide; no 07-14 entry change.
  * DayTraderGated (georgia, intraday) vs DayTraderV5Gated: the BTC 4h 50/200
    regime SWITCH (range_on / bounce_pullback / trend_breakout) IS ported —
    consumed through extra["btc_regime_up"] (EMA50>EMA200), matching the
    original; all three legs' gates line up. range_meanrev retirement mirrored.
  So the MomoBreakout tide gate is the LONE entry-gate parity gap.

METHOD (harness = study_breakout_boot_entry.py / study_family_time_stop.py,
the accepted pattern): full Lighter 4h tape (paged 500 bars/call; reused from
.breakout_boot_cache.json when present — same fetch code, same format),
WIDE_COINS/COINS minus unlisted; signals by calling the SHIPPED
MomoBreakout.signals (imported from lighter_family_bot — replay through the
real code, zero port risk) on the bot's own 280-bar CandleCache window.
Portfolio sim per book with shipped exits (stop -12% intra-bar, gap-through at
open; donchian_breakdown at close), shipped protections (cooldown / slguard /
maxdd), shipped stake ($50 x inverse-vol mult). The TIDE variant ANDs ONE term
into the entry — btc_tide_up = BTC close > BTC 4h EMA200 on that same bar,
computed the PORT's way (fam.ema_series over the 280-bar BTC window, the exact
series btc_regime_up would see), FAIL-SAFE CLOSED (no/short/NaN reading ->
blocked). Organs excluded (brain mults, fleet veto, panic — identical both
arms). Price-only P&L (no funding; identical both arms — the claim is the
RELATIVE ordering). Faithfulness cross-check: the gate-OFF baseline must
reproduce study_breakout_boot_entry's LEVEL P&L to the cent (dad +11.90,
breakout +16.50).

RESULTS 2026-07-22 (tape 2025-03-09..2026-07-22, 500d, 25 coins; halves =
calendar halves of the union grid, split 2025-11-14; BTC 4h regime: full
-22.7%, H1 +15.2% (rising), H2 -32.9% (falling) — TWO regimes, one rising +
one falling. BTC tide UP on 45.9% of bars. Faithfulness cross-check: the
gate-OFF baseline reproduces study_breakout_boot_entry's LEVEL P&L to the cent
— dad +11.90, breakout +16.50):

  PORTFOLIO SIM (shipped exits + protections, cold start, marked at end):
    book                    arm     net$      H1$      H2$      n   win%
    freqtrade-dad           base   +11.90   +72.08   -60.18   153  35.3%
    freqtrade-dad           tide   +27.32   +59.97   -32.64   120  38.3%
    crypto-breakout-4h      base   +16.50  +109.53   -93.03   238  34.9%
    crypto-breakout-4h      tide   +66.84   +93.99   -27.15   184  37.5%
    BOTH BOOKS              base   +28.39  +181.61  -153.21   391  35.0%
    BOTH BOOKS              tide   +94.16  +153.96   -59.80   304  37.8%
    TIDE-minus-base: full +65.76 | H1 -27.65 | H2 +93.42

  GATE SUPPRESSION (level-true valid bars blocked by the tide term, by half):
    book                  level-true   blocked   supp%   blk-H1   blk-H2
    freqtrade-dad               1285       155   12.1%       59       96
    crypto-breakout-4h          1983       247   12.5%       77      170
    (trade count falls harder than 12% — 153->120, 238->184, ~22% — because
    the tide is ONE shared series: in the falling half it blocks nearly every
    coin at once, so freed slots don't refill.)

VERDICT: ENACT. The tide gate PASSES the restrict-direction bar in BOTH books:
H2 (falling half, the bleed the gate targets) improves +$27.54 (dad) and
+$65.88 (breakout) — the gate cuts falling-half losses ~46% (dad -60.18 ->
-32.64) and ~71% (breakout -93.03 -> -27.15) by refusing breakouts while BTC
is under its own 4h EMA200. Only 12% of level-true bars are blocked, but they
are the RIGHT 12%: 62-69% of the blocks land in H2, and they are the
breakouts that fired with the market tide against them. H1 (rising half) gives
back some — dad -$12.11, breakout -$15.54 — because the gate also blocks the
minority of H1 breakouts that fired during BTC's brief sub-EMA200 dips, a few
of them winners. BUT full-window net RISES in both books (dad +11.90 ->
+27.32, breakout +16.50 -> +66.84) and win% climbs 35 -> 37-38%: the H2 saving
outweighs the H1 give-back 2.3x (dad) / 4.2x (breakout). This is the freqtrade
rationale reproduced on Lighter's own tape (bleed roughly half-to-two-thirds
cut, full window up). Note: the strict "not-worse in BOTH halves" reading is
NOT met — H1 falls — but the DIRECTIONAL restrict bar the task sets ("cut the
falling-half bleed without GUTTING the rising half") is: H1 stays strongly
positive (+59.97 / +93.99, 83-86% retained) while H2 is roughly halved and the
full window improves in both books. The gate does its job. REGIME COVERAGE:
this window has one rising half AND one falling half (BTC +15.2% / -32.9%);
the H2 improvement is the falling-regime evidence, the H1 give-back the
rising-regime cost, and the net-positive holds across both — not a one-regime
pass. This is BTC-tide
gating CRYPTO books (all 25 coins are BTC-beta), so the 21-Jul item-18
per-asset-regime caveat (never BTC's EMA for SPY/XAU/WTI) does NOT block it:
there are no non-crypto books here, and BTC IS the correct tide for a
BTC-correlated crypto basket — which is precisely what the original gate
asserts.

PROPOSED MINIMAL DIFF (mirror the original; port the exact rule since
btc_regime_up's EMA50>EMA200 does NOT match close>EMA200). CRITICAL harness
note: study_breakout_boot_entry.py + study_family_time_stop.py both call
MomoBreakout.signals(win, {}) and read `enter` — so the gate must be
PRESENT-KEY-GATES / ABSENT-KEY-OPENS: production main() ALWAYS supplies the
computed key (fail-safe closed), so production is fail-safe closed; the
replay harnesses omit it and keep the pure-breakout baseline (they model the
gate externally, as this study does). ANDing an unconditional fail-safe-closed
tide into `enter` would collapse those two shipped baselines to ~0 — don't.

    # lighter_family_bot.py, MomoBreakout.signals — after computing `enter`:
        enter = (c[i] > dc_high and c[i] > ema_t[i] and v[i] > 0)
        # [PARITY 14-Jul] MomoBreakoutV1's BTC-tide gate: block a breakout
        # while BTC is under its own 4h EMA200. Present key gates (fail-safe
        # closed on False); absent key (replay harnesses) leaves it ungated.
        if extra and "btc_tide_up" in extra:
            enter = enter and bool(extra["btc_tide_up"])

    # a helper mirroring btc_regime_up but the MomoBreakout original's rule
    # (close > EMA200, NOT EMA50 > EMA200):
    def btc_tide_up(cache):
        \"\"\"BTC 4h close > EMA200 on the last closed bar (MomoBreakoutV1's
        14-Jul market-tide gate). Fail-safe False (off-tide) — the original's
        documented conservative default.\"\"\"
        bars = cache.get("BTC", "4h")
        if not bars or len(bars["c"]) < 210:
            return False
        e200 = ema_series(bars["c"], 200)
        return bool(e200[-1] and bars["c"][-1] > e200[-1])

    # main() loop, next to `regime = btc_regime_up(cache)`:
        tide = btc_tide_up(cache)
        ... sig = b.s.signals(bars, {"btc_regime_up": regime,
                                     "btc_tide_up": tide}) if new_candle else None
  Targeted + reversible: only MomoBreakout reads btc_tide_up (TrendMomo /
  SwingDip / DayTraderGated ignore the extra key), so dad + breakout-4h gate
  and the other five books are untouched. Shadow-only, like the port.

Usage:
    python3 scripts/study_breakout_tide_gate.py --selftest   # offline, no net
    python3 scripts/study_breakout_tide_gate.py              # full run (cached)
    python3 scripts/study_breakout_tide_gate.py --refresh    # refetch tape
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
CACHE = os.path.join(_HERE, ".breakout_tide_cache.json")
SEED_4H = os.path.join(_HERE, ".breakout_boot_cache.json")  # reuse if present

TF = "4h"
TF_S = 4 * 3600
DAYS = int(os.environ.get("BTG_DAYS", "500"))
SPAN = fam.CandleCache.SPAN_BARS[TF]                    # the bot's own window (280)
STAKE = 50.0                                            # FAMILY_STAKE_USD default
TREND_EMA = 200                                         # MomoBreakoutV1.trend_ema

# the two MomoBreakout carriers exactly as shipped (STRATEGIES list)
BOOKS = {
    "freqtrade-dad": dict(coins=list(fam.COINS), max_open=4, stoploss=-0.12),
    "crypto-breakout-4h": dict(coins=list(fam.WIDE_COINS), max_open=6,
                               stoploss=-0.12),
}
STRAT = fam.MomoBreakout("study", tf=TF, stoploss=-0.12, max_open=6, style="s")
PROT = STRAT.protections                                # cooldown/slguard/maxdd


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
    """{fleet_coin: bars} for every study coin listed on Lighter. Reuses the
    breakout study's cache when present (same fetch code / format); writes its
    own cache only when it had to fetch."""
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days", 0) >= DAYS:
            return d["bars"]
    if os.path.exists(SEED_4H) and not refresh:
        d = json.load(open(SEED_4H))
        if d.get("days", 0) >= DAYS and d.get("bars"):
            print(f"  4h tape seeded from {os.path.basename(SEED_4H)} "
                  f"({len(d['bars'])} coins)")
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
    """Per bar i: (enter, exit, atr_pct, valid) by calling the real
    MomoBreakout.signals on the last <=SPAN bars ending at i — exactly the
    window CandleCache serves the bot."""
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
    return {"enter": ent, "exit": exi, "atr_pct": atr, "valid": valid}


def compute_btc_tide(btc_bars):
    """{t_open: btc_tide_up} — the MomoBreakoutV1 14-Jul gate ported EXACTLY:
    BTC close > EMA200 on that 4h bar, computed the PORT's way (fam.ema_series
    over the bot's 280-bar CandleCache window ending at the bar). Fail-safe
    CLOSED: warming-up / no reading -> False (off-tide), matching the
    original's fillna(0)."""
    c, tt = btc_bars["c"], btc_bars["t"]
    n = len(c)
    tide = {}
    for i in range(n):
        lo = max(0, i + 1 - SPAN)
        win = c[lo:i + 1]
        e = fam.ema_series(win, TREND_EMA)
        ev = e[-1]
        tide[tt[i]] = bool(ev is not None and win[-1] > ev)
    return tide


def stake_of(atr_pct):
    """The shipped inverse-vol stake mult (organ-free path): ref 2% ATR,
    clamp [0.3, 1.0]."""
    m = 1.0
    if atr_pct and atr_pct > 0:
        m *= max(0.3, min(1.0, 0.02 / atr_pct))
    return STAKE * m


# ---------------------------------------------------------------------------
# portfolio sim — one book, shipped protections, optional tide gate

def sim_book(book, data, flags, half_ts, tide=None, gate=False):
    """gate=False -> the shipped LEVEL entry (baseline). gate=True -> ANDs the
    ported btc_tide_up term into the entry (fail-safe closed on a missing key).
    Everything else is identical to study_breakout_boot_entry's sim_book."""
    coins = [c for c in book["coins"] if c in data]
    max_open, stoploss = book["max_open"], book["stoploss"]
    idx = {c: {t: i for i, t in enumerate(data[c]["t"])} for c in coins}
    grid = sorted({t for c in coins for t in data[c]["t"]})
    pos = {}                       # coin -> dict(entry, stake, j, ts)
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
                cooldown[coin] = T + PROT.get("cooldown_candles", 1) * TF_S
                del pos[coin]
        # ---- entries (book coin order, shipped gate order) ----
        if locked(T):
            continue
        for coin in coins:
            if coin in pos or len(pos) >= max_open:
                continue
            j = idx[coin].get(t_open)
            if j is None or not flags[coin]["enter"][j]:
                continue
            # [TIDE GATE] ANDed into the entry, fail-safe CLOSED
            if gate and not (tide or {}).get(t_open, False):
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


def suppression(book, data, flags, tide, half_ts):
    """Signal-level gate effect: of the book's level-true VALID bars, how many
    the tide term blocks, split by half (the pure gate, independent of slot
    dynamics)."""
    coins = [c for c in book["coins"] if c in data]
    tot = blk = blk_h1 = blk_h2 = 0
    for coin in coins:
        b, fl = data[coin], flags[coin]
        for i in range(len(b["t"])):
            if not fl["valid"][i] or not fl["enter"][i]:
                continue
            tot += 1
            if not tide.get(b["t"][i], False):
                blk += 1
                if b["t"][i] + TF_S < half_ts:
                    blk_h1 += 1
                else:
                    blk_h2 += 1
    return {"level_true": tot, "blocked": blk, "supp": blk / max(1, tot),
            "blk_h1": blk_h1, "blk_h2": blk_h2}


# ---------------------------------------------------------------------------

def pct(x):
    return f"{100 * x:.1f}%"


def run():
    refresh = "--refresh" in sys.argv
    print(f"Lighter 4h tape — universe load{' (refresh)' if refresh else ''}:")
    data = load_universe(refresh)
    print(f"{len(data)} coins loaded")
    if "BTC" not in data:
        print("BTC absent — the tide gate has no reference. Abort.")
        return
    all_ts = sorted({t for b in data.values() for t in b["t"]})
    t0, t1 = all_ts[0], all_ts[-1] + TF_S
    half_ts = (t0 + t1) / 2
    span_d = (t1 - t0) / 86400

    def iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"window {iso(t0)} .. {iso(t1)} ({span_d:.0f}d), half at {iso(half_ts)}")

    # regime statement (the CLAUDE.md regime-coverage caveat)
    c = data["BTC"]["c"]
    tarr = data["BTC"]["t"]
    mid_i = min(range(len(tarr)), key=lambda i: abs(tarr[i] - half_ts))
    print(f"BTC over window: {pct(c[-1] / c[0] - 1)} "
          f"(H1 {pct(c[mid_i] / c[0] - 1)}, H2 {pct(c[-1] / c[mid_i] - 1)}) "
          f"— one rising half + one falling half; state the regime")

    print("\ncomputing signals through the SHIPPED MomoBreakout.signals "
          f"(window={SPAN} bars)...")
    flags = {coin: compute_flags(b) for coin, b in data.items()}
    print("computing the ported BTC tide (close > BTC 4h EMA200, "
          f"fam.ema_series over the {SPAN}-bar window, fail-safe closed)...")
    tide = compute_btc_tide(data["BTC"])
    tide_up_frac = sum(1 for v in tide.values() if v) / max(1, len(tide))
    print(f"BTC tide UP on {pct(tide_up_frac)} of bars "
          f"(H1 rising -> mostly up; H2 falling -> mostly down)")

    # ---- portfolio sim: baseline vs tide ----
    print("\nPORTFOLIO SIM (shipped exits/protections, cold start):")
    print(f"{'book':22s} {'arm':5s} {'net$':>9s} {'H1$':>9s} {'H2$':>9s} "
          f"{'n':>5s} {'win%':>6s}")
    totals = {"base": {"net": 0.0, "h1": 0.0, "h2": 0.0, "n": 0, "wins": 0},
              "tide": {"net": 0.0, "h1": 0.0, "h2": 0.0, "n": 0, "wins": 0}}
    per_book = {}
    for name, book in BOOKS.items():
        rb = sim_book(book, data, flags, half_ts, gate=False)
        rt = sim_book(book, data, flags, half_ts, tide=tide, gate=True)
        per_book[name] = (rb, rt)
        for arm, r in (("base", rb), ("tide", rt)):
            print(f"{name:22s} {arm:5s} {r['net']:9.2f} {r['h1']:9.2f} "
                  f"{r['h2']:9.2f} {r['n']:5d} "
                  f"{pct(r['wins'] / max(1, r['n'])):>6s}")
            for k in ("net", "h1", "h2", "n", "wins"):
                totals[arm][k] += r[k]
    for arm in ("base", "tide"):
        t = totals[arm]
        print(f"{'BOTH BOOKS':22s} {arm:5s} {t['net']:9.2f} {t['h1']:9.2f} "
              f"{t['h2']:9.2f} {t['n']:5d} "
              f"{pct(t['wins'] / max(1, t['n'])):>6s}")
    db, dt = totals["base"], totals["tide"]
    print(f"TIDE-minus-base: full {dt['net'] - db['net']:+.2f} | "
          f"H1 {dt['h1'] - db['h1']:+.2f} | H2 {dt['h2'] - db['h2']:+.2f}")

    # ---- suppression census ----
    print("\nGATE SUPPRESSION (level-true valid bars blocked by the tide term):")
    print(f"{'book':22s} {'level-true':>10s} {'blocked':>8s} {'supp%':>6s} "
          f"{'blk-H1':>7s} {'blk-H2':>7s}")
    for name, book in BOOKS.items():
        s = suppression(book, data, flags, tide, half_ts)
        print(f"{name:22s} {s['level_true']:10d} {s['blocked']:8d} "
              f"{pct(s['supp']):>6s} {s['blk_h1']:7d} {s['blk_h2']:7d}")

    # ---- enact bar (directional restrict) ----
    print("\nENACT BAR (restrict-direction: material falling-half improvement, "
          "rising half not gutted):")
    for name, (rb, rt) in per_book.items():
        dh1 = rt["h1"] - rb["h1"]
        dh2 = rt["h2"] - rb["h2"]
        dfull = rt["net"] - rb["net"]
        h1_ret = rt["h1"] / rb["h1"] if rb["h1"] else float("nan")
        material = dh2 >= 5.0
        not_gutted = rt["h1"] > 0 and h1_ret >= 0.5
        verdict = "PASS" if (material and not_gutted and dfull > 0) else "review"
        print(f"  {name:22s} dH2 {dh2:+.2f} (bleed {rb['h2']:.2f}->{rt['h2']:.2f}) "
              f"| dH1 {dh1:+.2f} (H1 retained {pct(h1_ret) if rb['h1'] else 'n/a'})"
              f" | dfull {dfull:+.2f} -> {verdict}")
    print("  strict not-worse-both-halves is NOT met (H1 falls); the "
          "directional bar (H2 materially better, H1 not gutted, full up) IS.")

    print("\nDone. Header table numbers come from this output — re-run with "
          "--refresh rather than re-arguing from prose.")


# ---------------------------------------------------------------------------
# selftest — OFFLINE, fixtures only

def _mk_bars(closes, hi_off=0.005, lo_off=0.005, vol=1.0, t0=1_700_000_000):
    n = len(closes)
    return {"t": [t0 + i * TF_S for i in range(n)],
            "o": list(closes),
            "h": [c * (1 + hi_off) for c in closes],
            "l": [c * (1 - lo_off) for c in closes],
            "c": list(closes),
            "v": [vol] * n}


def _selftest():
    # ---- BTC tide: a long ramp up (close > EMA200 -> tide UP), then a
    # collapse below the still-high EMA200 (tide DOWN). fail-safe closed while
    # the EMA200 is warming up.
    ramp = [100.0 + i for i in range(320)]          # steadily rising
    drop = [ramp[-1] * (0.97 ** k) for k in range(1, 40)]   # fall under EMA200
    btc = _mk_bars(ramp + drop)
    tide = compute_btc_tide(btc)
    warm = btc["t"][100]                            # EMA200 not ready yet
    assert tide[warm] is False, "warmup -> fail-safe closed"
    up = btc["t"][300]                              # deep in the ramp
    assert tide[up] is True, "rising close above EMA200 -> tide up"
    dn = btc["t"][len(ramp) + 30]                   # well into the collapse
    assert tide[dn] is False, "close below EMA200 -> tide down"

    # ---- gate mechanics on a single breakout book. Fixture: flat, a clean
    # breakout, then a steady climb (level stays true), no stop/breakdown ->
    # the position holds to end. Two BTC-tide scenarios flip the entry.
    closes = [100.0] * 300 + [108.0]
    px = 108.0
    for _ in range(30):
        px *= 1.01
        closes.append(px)
    b = _mk_bars(closes, lo_off=0.001)
    fl = compute_flags(b)
    cross_i = 300
    assert fl["enter"][cross_i], "the breakout bar must be level-true"

    book = {"coins": ["BTC"], "max_open": 1, "stoploss": -0.12}
    data = {"BTC": b}
    flags = {"BTC": fl}
    half = b["t"][len(b["t"]) // 2]

    # baseline (gate off) == the shipped LEVEL entry: it trades
    base = sim_book(book, data, flags, half, gate=False)
    assert base["n"] >= 1, "baseline must take the breakout"

    # tide ALL-UP -> gate admits the same entry (n unchanged, P&L identical)
    tide_up = {t: True for t in b["t"]}
    g_up = sim_book(book, data, flags, half, tide=tide_up, gate=True)
    assert g_up["n"] == base["n"] and abs(g_up["net"] - base["net"]) < 1e-9, \
        "all-up tide must reproduce the baseline exactly"

    # tide ALL-DOWN -> gate blocks EVERY entry (n == 0)
    tide_dn = {t: False for t in b["t"]}
    g_dn = sim_book(book, data, flags, half, tide=tide_dn, gate=True)
    assert g_dn["n"] == 0, "all-down tide must block every entry"

    # fail-safe CLOSED: an EMPTY tide dict (no readings) blocks too
    g_empty = sim_book(book, data, flags, half, tide={}, gate=True)
    assert g_empty["n"] == 0, "missing tide reading -> fail-safe closed"

    # tide UP only ON the breakout bar -> entry admitted (gate reads that bar)
    tide_one = {t: (t == b["t"][cross_i]) for t in b["t"]}
    g_one = sim_book(book, data, flags, half, tide=tide_one, gate=True)
    assert g_one["n"] >= 1, "tide up on the entry bar admits it"

    # halves add up; stake mult clamp
    assert abs((base["h1"] + base["h2"]) - base["net"]) < 1e-9
    assert stake_of(0.02) == STAKE
    assert stake_of(0.20) == STAKE * 0.3
    assert stake_of(None) == STAKE

    # suppression counts the blocked level-true bars, all in the (single) half
    s = suppression(book, data, flags, tide_dn, half)
    assert s["blocked"] == s["level_true"] > 0, "all level-true bars blocked"
    s2 = suppression(book, data, flags, tide_up, half)
    assert s2["blocked"] == 0, "all-up tide blocks nothing"

    print("study_breakout_tide_gate selftest OK (tide up/down/warmup, gate "
          "admits on up / blocks on down / fail-safe closed on missing, "
          "baseline==all-up, halves add up, suppression counts)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    run()
