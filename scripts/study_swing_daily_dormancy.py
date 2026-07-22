#!/usr/bin/env python3
"""
scripts/study_swing_daily_dormancy.py — crypto-swing-daily-lshadow's ZERO
trades ever: data-depth BUG vs genuine regime dormancy, on Lighter's own
1d tape.

THE QUESTION (21-Jul review finding): the SwingDip 1d book has never traded
(equity $1000.00 exact, 0 open / 0 closed since its 13-Jul boot — /pnl.json,
zero rows in /trades.json?source=paper). Is the shipped fetch depth too
shallow for the gate to EVER evaluate (bug), or does the entry condition
genuinely never fire in this regime (dormancy)?

THE SHIPPED NUMBERS (lighter_family_bot.py, read 22-Jul): SwingDip enter =
e50>e200 golden-cross STATE and rsi(14)<42 and close<lower-BB(20,2) and
v>0, min_bars=230; CandleCache.SPAN_BARS["1d"]=240 so the bot fetches a
240-day span (LighterClient.candles count_back=242, API cap 500/call) and
parse_candles drops the forming bar -> the bot evaluates on ~240 closed
bars >= 230. The depth CAN evaluate — 10 bars of slack. This study measures
whether that 240-bar truncation ever changes the answer.

METHOD: full-depth Lighter 1d tape (paged 500 bars/call) for WIDE_COINS
minus unlisted (ATOM/ETC/ALGO/INJ — matches the row's skipped_unlisted);
signals computed by calling the SHIPPED SwingDip.signals (imported, zero
port risk) two ways per closed bar: FULL arm = all history to that bar,
BOT arm = the bot's own 240-bar window. Outcome tally = shipped exits
(stop -10% intra-bar w/ gap-at-open, continuous ROI ladder
{0d:20%,4d:12%,8d:6%,14d:0%}, sell_into_strength at close), single-trade
per signal, per-coin dedup, price-only (no funding/spread — same for both
arms).

RESULTS 2026-07-22 (25 coins, union tape 2025-03-10..2026-07-21 = 498d,
halves split 2025-11-14; BTC full -15.4%, H1 +20.3%, H2 -29.7%):
    arm         signals   H1   H2   since-boot(13-Jul)
    FULL-depth       25   19    6                    0
    BOT 240-bar      25   19    6                    0
    full-only (missed by the bot's window): 0
    bot-only (created by truncation):       0
  -> the two arms agree EXACTLY, signal-for-signal. NOT a depth bug.
  uptrend-leg truncation check: 13/5441 evaluable coin-bars disagree
  (0.24%) and none of them lands on a signal bar.
  Signal dates: a 21-signal cluster 2025-11-03..17 (the November top
  rollover), TRX 2026-06-02/03/05, NEAR 2026-06-26 — the LAST signal
  anywhere is 17d BEFORE the book existed. Zero trades is the shipped
  logic working.
  Outcome tally of the would-be entries (identical both arms): n=12
  deduped trades, 33% win, net -$14.08 at $50 stake (H1 -$20.08 n=10,
  H2 +$6.00 n=2; 7 stop_loss / 5 roi) — the gate's silence PROTECTED
  the book; there is no blocked win to unblock.
  Why it is dormant: the gate requires the golden-cross STATE and the
  falling half has it on only 4.4% of coin-bars (H1: 45.9%); at the last
  close only NEAR and TRX hold e50>e200. XLM (223 bars) is the one coin
  younger than min_bars — first evaluable in ~7d; not a defect.

VERDICT: GENUINE REGIME DORMANCY — DO NOT ENACT ANYTHING. The bot's 240-bar
fetch reproduces the full-depth signal stream exactly (25/25, zero missed);
zero signals have occurred since the book booted, and the ones the tape does
contain lost money net. The regime caveat owns this row: a 1d
dip-in-UPTREND book cannot trade while ~96% of the evaluable falling-half
tape has no uptrend to dip in. REGIME COVERAGE (per the CLAUDE.md caveat):
the tape spans a rising H1 (+20.3%) and a falling H2 (-29.7%), BUT the
EVALUABLE slice is H2-dominated — EMA200+min_bars warmup consumes 229 bars,
so H1 contributes only 318 evaluable coin-bars (~last 3 weeks of H1, the
top rollover itself) vs 5123 in H2. This study's dormancy verdict is
regime-scoped: in a sustained uptrend the gate demonstrably fires (the
Nov-03..17 cluster) and the book would trade.

Usage:
    python3 scripts/study_swing_daily_dormancy.py --selftest  # offline, no net
    python3 scripts/study_swing_daily_dormancy.py             # full run (cached)
    python3 scripts/study_swing_daily_dormancy.py --refresh   # refetch tape
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# repo root importable — the study replays the SHIPPED strategy code
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
os.environ.setdefault("FAMILY_LOG_FILE", os.devnull)   # no side-effect log file

import lighter_family_bot as fam                        # noqa: E402
from venues.symbol_map import to_lighter                # noqa: E402

B = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
CACHE = os.path.join(_HERE, ".swing_daily_dormancy_cache.json")

TF, TF_S = "1d", 86400
DAYS = int(os.environ.get("SDD_DAYS", "500"))           # > tape depth: fetch all
SPAN = fam.CandleCache.SPAN_BARS[TF]                    # the bot's own window: 240
STRAT = fam.SwingDip("study", tf=TF, stoploss=-0.10, max_open=8, style="s")
MIN_BARS = STRAT.min_bars                               # 230
STAKE = 50.0                                            # FAMILY_STAKE_USD default
LIVE_SINCE = "2026-07-13T00:00:00+00:00"                # book's fleet-wide join


def _d(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


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


def fetch_candles_1d(mid, days):
    """1d OHLCV paged backward (500-bar cap/call) -> sorted closed-bar lists."""
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
    return {"t": list(ts_sorted),                        # bar OPEN, seconds
            "o": [out[t][0] for t in ts_sorted],
            "h": [out[t][1] for t in ts_sorted],
            "l": [out[t][2] for t in ts_sorted],
            "c": [out[t][3] for t in ts_sorted],
            "v": [out[t][4] for t in ts_sorted]}


def load_universe(refresh=False):
    """{fleet_coin: bars} for every WIDE_COINS coin listed on Lighter."""
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
            b = fetch_candles_1d(int(m["market_id"]), DAYS)
        except Exception as e:  # noqa: BLE001
            print(f"  {coin}: fetch failed ({e}) — skipped")
            continue
        if not b["t"]:
            print(f"  {coin}: empty tape — skipped")
            continue
        bars[coin] = b
        print(f"  {coin:6s} {len(b['t']):5d} bars "
              f"({_d(b['t'][0])} .. {_d(b['t'][-1])})")
    json.dump({"days": DAYS, "bars": bars}, open(CACHE, "w"))
    return bars


# ---------------------------------------------------------------------------
# the two arms — BOTH call the SHIPPED SwingDip.signals (zero port risk)

def _win(bars, i, depth=None):
    """The candle window the strategy sees at closed bar i.
    depth=None -> FULL venue depth (everything up to i).
    depth=SPAN -> the bot's own CandleCache window (last SPAN closed bars)."""
    lo = 0 if depth is None else max(0, i - depth + 1)
    return {k: bars[k][lo:i + 1] for k in ("t", "o", "h", "l", "c", "v")}


def scan(bars, depth=None):
    """[(i, ts)] of every bar where the shipped enter condition fires."""
    out = []
    for i in range(len(bars["t"])):
        sig = STRAT.signals(_win(bars, i, depth), {})
        if sig and sig.get("enter"):
            out.append((i, bars["t"][i]))
    return out


def legs(bars, i, depth=None):
    """The three entry legs at closed bar i (None if window too short to
    evaluate) — same math as the shipped signals(), decomposed."""
    w = _win(bars, i, depth)
    c, h, l, v = w["c"], w["h"], w["l"], w["v"]
    if len(c) < MIN_BARS:
        return None
    j = len(c) - 1
    rsi = fam.rsi_series(c, 14)
    e50, e200 = fam.ema_series(c, 50), fam.ema_series(c, 200)
    tp = [(h[k] + l[k] + c[k]) / 3.0 for k in range(len(c))]
    if None in (rsi[j], e50[j], e200[j]) or j < 20:
        return None
    bb_lo = (sum(tp[j - 19:j + 1]) / 20.0
             - 2.0 * fam.stdev(tp[j - 19:j + 1]))
    return {"uptrend": e50[j] > e200[j], "rsi42": rsi[j] < 42,
            "bb": c[j] < bb_lo, "vol": v[j] > 0}


# ---------------------------------------------------------------------------
# outcome tally — shipped exits (stop -10% intra-bar, continuous ROI ladder,
# sell_into_strength at signal close), single-trade per signal, one position
# per coin (the bot's own invariant), organs excluded (identical both arms).

def sim_trade(bars, i_entry):
    entry = bars["c"][i_entry]
    stop_px = entry * (1 + STRAT.stoploss)
    n = len(bars["t"])
    for i in range(i_entry + 1, n):
        o, h, l, c = bars["o"][i], bars["h"][i], bars["l"][i], bars["c"][i]
        age_min = (bars["t"][i] - bars["t"][i_entry]) / 60.0
        # stop first (pessimistic when stop+ROI touch the same bar)
        if l <= stop_px:
            px = min(stop_px, o)                     # gap-through fills at open
            return {"i": i, "pnl": px / entry - 1, "reason": "stop_loss"}
        # continuous ROI ladder (the bot checks every ~90s -> intra-bar high)
        rung = max((k for k in STRAT.roi if k <= age_min), default=None)
        if rung is not None:
            tgt = entry * (1 + STRAT.roi[rung])
            if h >= tgt:
                px = max(tgt, o)                     # gap-up fills at open
                return {"i": i, "pnl": px / entry - 1, "reason": "roi"}
        # exit signal at the daily close (full-depth signals)
        sig = STRAT.signals(_win(bars, i), {})
        if sig and sig.get("exit"):
            return {"i": i, "pnl": c / entry - 1,
                    "reason": sig.get("exit_reason", "exit_signal")}
    return {"i": n - 1, "pnl": bars["c"][n - 1] / entry - 1, "reason": "open_marked"}


def tally(bars_by_coin, signals_by_coin):
    """Single-trade sim per signal, per-coin deduped (no re-entry while the
    prior sim trade is open). Returns rows [(coin, ts_entry, res)]."""
    rows = []
    for coin, sigs in signals_by_coin.items():
        busy_until = -1
        for i, ts in sigs:
            if i <= busy_until:
                continue
            res = sim_trade(bars_by_coin[coin], i)
            busy_until = res["i"]
            rows.append((coin, ts, res))
    return rows


def _agg(rows):
    n = len(rows)
    wins = sum(1 for _, _, r in rows if r["pnl"] > 0)
    usd = sum(r["pnl"] * STAKE for _, _, r in rows)
    return n, wins, usd


# ---------------------------------------------------------------------------

def main(refresh=False):
    bars = load_universe(refresh)
    if not bars:
        print("no universe — venue unreachable?")
        return
    live_ts = int(datetime.fromisoformat(LIVE_SINCE).timestamp())
    all_ts = sorted({t for b in bars.values() for t in b["t"]})
    mid_ts = all_ts[len(all_ts) // 2]
    print(f"\nuniverse {len(bars)} coins, union tape {_d(all_ts[0])} .. "
          f"{_d(all_ts[-1])} ({(all_ts[-1] - all_ts[0]) / 86400:.0f}d), "
          f"halves split {_d(mid_ts)}")

    # regime composition (the regime caveat owns the verdict's scope)
    btc = bars.get("BTC")
    if btc:
        cs, ts = btc["c"], btc["t"]
        h2_i = next(k for k, t in enumerate(ts) if t >= mid_ts)
        print(f"BTC regime: full {cs[-1] / cs[0] - 1:+.1%}, "
              f"H1 {cs[h2_i] / cs[0] - 1:+.1%}, "
              f"H2 {cs[-1] / cs[h2_i] - 1:+.1%}")

    # ---- per-coin depth + the two arms -------------------------------------
    full_sigs, bot_sigs = {}, {}
    short_coins, dead_zone = [], 0
    up_disagree = up_both = 0
    up_full_share = {"h1": [0, 0], "h2": [0, 0]}
    legs_last = {}
    for coin, b in sorted(bars.items()):
        nb = len(b["t"])
        if nb < MIN_BARS:
            short_coins.append((coin, nb))
        full_sigs[coin] = scan(b, None)
        bot_sigs[coin] = scan(b, SPAN)
        for i in range(len(b["t"])):
            lf = legs(b, i, None)
            if lf is None:
                continue
            key = "h1" if b["t"][i] < mid_ts else "h2"
            up_full_share[key][0] += 1 if lf["uptrend"] else 0
            up_full_share[key][1] += 1
            lb = legs(b, i, SPAN)
            if lb is not None:
                up_both += 1
                if lb["uptrend"] != lf["uptrend"]:
                    up_disagree += 1
        legs_last[coin] = (legs(b, nb - 1, None), legs(b, nb - 1, SPAN))
        dead_zone += max(0, min(nb, MIN_BARS) - 1)

    print(f"\ncoins that can NEVER evaluate at min_bars={MIN_BARS} "
          f"(venue tape too young): {len(short_coins)}")
    for coin, nb in short_coins:
        print(f"  {coin:6s} {nb} closed bars "
              f"({MIN_BARS - nb} more days until first evaluation)")

    print(f"\nuptrend-leg (e50>e200) truncation check — bot {SPAN}-bar window "
          f"vs full depth, {up_both} evaluable coin-bars: "
          f"{up_disagree} disagree ({up_disagree / max(up_both, 1):.2%})")
    for key in ("h1", "h2"):
        u, n = up_full_share[key]
        print(f"  full-depth uptrend share {key}: {u}/{n} = {u / max(n, 1):.1%}")

    # ---- signal census ------------------------------------------------------
    def census(name, sigs):
        flat = [(c, ts) for c, ss in sigs.items() for _, ts in ss]
        n_h1 = sum(1 for _, ts in flat if ts < mid_ts)
        n_live = sum(1 for _, ts in flat if ts >= live_ts)
        print(f"\n{name}: {len(flat)} entry signals "
              f"(H1 {n_h1}, H2 {len(flat) - n_h1}; "
              f"since book boot {LIVE_SINCE[:10]}: {n_live})")
        for c, ts in sorted(flat, key=lambda x: x[1]):
            print(f"  {_d(ts)}  {c}")
        return flat

    flat_full = census(f"FULL-DEPTH arm (whole venue tape)", full_sigs)
    flat_bot = census(f"BOT-DEPTH arm (the shipped {SPAN}-bar window)", bot_sigs)

    full_set = {(c, ts) for c, ss in full_sigs.items() for _, ts in ss}
    bot_set = {(c, ts) for c, ss in bot_sigs.items() for _, ts in ss}
    missed = sorted(full_set - bot_set, key=lambda x: x[1])
    extra = sorted(bot_set - full_set, key=lambda x: x[1])
    print(f"\nfull-only (missed by the bot's window): {len(missed)} "
          f"{[(c, _d(t)) for c, t in missed]}")
    print(f"bot-only (created by truncation):        {len(extra)} "
          f"{[(c, _d(t)) for c, t in extra]}")

    # ---- outcome tally (eyes-open numbers for any would-be fix) ------------
    for name, sigs in (("FULL", full_sigs), ("BOT", bot_sigs)):
        rows = tally(bars, sigs)
        h1 = [r for r in rows if r[1] < mid_ts]
        h2 = [r for r in rows if r[1] >= mid_ts]
        n, w, usd = _agg(rows)
        n1, w1, u1 = _agg(h1)
        n2, w2, u2 = _agg(h2)
        reasons = {}
        for _, _, r in rows:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
        print(f"\n{name}-arm outcome tally (single-trade, $%.0f stake): "
              % STAKE + f"n={n} win%={100 * w / max(n, 1):.0f}% "
              f"net=${usd:+.2f}  H1 n={n1} ${u1:+.2f}  H2 n={n2} ${u2:+.2f}  "
              f"{reasons}")

    # ---- the wake-up answer -------------------------------------------------
    up_now = [c for c, (lf, _) in legs_last.items() if lf and lf["uptrend"]]
    print(f"\ncoins whose 1d e50>e200 is TRUE at the last close "
          f"(full depth): {len(up_now)} {up_now}")
    last_sig = max((ts for _, ts in flat_full), default=None)
    if last_sig:
        print(f"last full-depth signal anywhere: {_d(last_sig)} "
              f"({(all_ts[-1] - last_sig) / 86400:.0f}d before tape end)")
    print(f"(book exists since {LIVE_SINCE[:10]}; "
          f"row has ZERO trades — see /pnl.json)")


# ---------------------------------------------------------------------------

def _fixture(n=400, dip_at=390, dip_bars=2, dip_pct=0.10):
    """Low-vol uptrend then a sharp dip: e50>e200 stays true, rsi collapses,
    close pierces the lower BB — the shipped enter condition must fire."""
    import math as _m
    c = []
    px = 100.0
    for i in range(n):
        px *= 1.003 + 0.0006 * _m.sin(i / 3.0)
        if dip_at <= i < dip_at + dip_bars:
            px *= (1 - dip_pct)
        c.append(px)
    t = [1_700_000_000 + i * TF_S for i in range(n)]
    return {"t": t, "o": list(c), "h": [x * 1.004 for x in c],
            "l": [x * 0.996 for x in c], "c": list(c),
            "v": [1.0] * n}


def _selftest():
    fx = _fixture()
    # 1) the shipped signal fires on the engineered dip — in BOTH arms
    fs = scan(fx, None)
    bs = scan(fx, SPAN)
    assert fs, "full arm found no signal on the dip fixture"
    assert any(390 <= i <= 394 for i, _ in fs), fs
    assert bs, "bot 240-bar arm found no signal on the dip fixture"
    # 2) a tape shorter than min_bars can never evaluate
    short = {k: v[:200] for k, v in fx.items()}
    assert scan(short, None) == [] and scan(short, SPAN) == []
    assert legs(short, 199) is None
    # 3) legs decomposition agrees with the shipped conjunction at signal bars
    for i, _ in fs:
        lg = legs(fx, i)
        assert lg and lg["uptrend"] and lg["rsi42"] and lg["bb"], (i, lg)
    # 4) exit sim: crafted winner hits the ROI ladder, crafted loser the stop
    win = {k: list(v) for k, v in fx.items()}
    i0 = fs[0][0]
    for j in range(i0 + 1, min(i0 + 3, len(win["c"]))):
        for key in ("o", "h", "l", "c"):
            win[key][j] = win["c"][i0] * 1.30
    r = sim_trade(win, i0)
    assert r["reason"] == "roi" and r["pnl"] >= 0.19, r
    lose = {k: list(v) for k, v in fx.items()}
    for j in range(i0 + 1, len(lose["c"])):
        for key in ("o", "h", "l", "c"):
            lose[key][j] = lose["c"][i0] * 0.80
    r = sim_trade(lose, i0)
    assert r["reason"] == "stop_loss" and r["pnl"] <= -0.10, r
    # 5) per-coin dedup: two signals inside one open trade -> one sim row
    rows = tally({"X": fx}, {"X": [(i0, fx["t"][i0]), (i0 + 1, fx["t"][i0 + 1])]})
    assert len(rows) == 1, rows
    print("study_swing_daily_dormancy selftest OK (dip fires both arms, "
          "short tape never evaluates, legs match, roi/stop sim, dedup)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main("--refresh" in sys.argv)
