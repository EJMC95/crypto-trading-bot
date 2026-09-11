#!/usr/bin/env python3
"""
scripts/study_short_mirrors_2026-09-10.py — "two books like Avo and mum that
SHORT the down days" (Eamon, 10-Sep-2026).

WHAT IT ASKS.  👩 mum and 🙏 avo are both LONG-ONLY.  Their entry cells have an
exact mirror on the short side:

  mum   (OversoldRebound, 1h):  rsi<38  AND NOT (e50>e200)   -> LONG
  MIRROR ("overbought fade"):   rsi>62  AND NOT (e50<e200)   -> SHORT

  avo   (SwingDip, 4h):  e50>e200 AND rsi<42 AND close<BB_lo -> LONG
  MIRROR ("rip in a downtrend"): e50<e200 AND rsi>58 AND close>BB_hi -> SHORT

The brackets are mirrored in MAGNITUDE, not invented: mum's roi ladder / -4%
stop / 24h max hold, avo's roi ladder / -10% stop / exit-on-rsi-reversal.

WHAT IT REFUSES TO DO.  Report a positive mean as an edge.  On this venue
`(hm)` measured that a random short earns +0.2%..+1.1%/trade for free, and
item 18 says a directional book that passes "both halves" on a one-regime tape
has passed on the DRIFT, not the edge.  So every cell here is graded against
MATCHED-RANDOM entries on the same coin, same window, same bracket, same side,
and the headline number is the EXCESS over that null.

CALIBRATION (the (gx) rule: a harness that cannot reproduce what DID happen may
not say what WOULD have).  Two gates, both must pass or the verdict is withheld:
  * POSITIVE CONTROL — plant a +/-2%/24h drift in synthetic bars and require the
    walker to recover it with the right sign and rough size.
  * LONG REPRODUCTION — run mum's and avo's OWN shipped cells through the same
    walker; report their means beside the books' published ones.

CONVENTIONS.  LAG-1 entry (signal on bar i's close, fill at bar i+1's OPEN) —
the (ne) look-ahead fix.  Bracket is tested against every bar from the entry bar
onward including its own post-open range ((ml) ON).  Stop wins a same-bar tie.
Friction is charged per side and REPORTED at three levels because it is the
constant that decided the last short study this fleet ran
(backtest_georgia_short_sleeve.py).  Funding is modelled at ZERO for the short
side and reported separately — a short RECEIVES the +0.0171%/day carry (ro)
measured, so zero is the conservative direction here.
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lighter_family_bot as fam          # noqa: E402  ONE owner for the maths
import fleet_bus                          # noqa: E402

API = "https://mainnet.zklighter.elliot.ai"
CACHE = os.environ.get(
    "SHORT_MIRROR_CACHE",
    "/tmp/claude-0/-home-user-crypto-trading-bot/"
    "0fef6e2b-63cd-5a62-8d4a-011500773ed7/scratchpad/tape")
UNIVERSE_N = int(os.environ.get("SHORT_MIRROR_UNIVERSE_N", "30"))
MIN_VOL_M = float(os.environ.get("SHORT_MIRROR_MIN_VOL_M", "1.0"))
NULL_DRAWS = int(os.environ.get("SHORT_MIRROR_NULL_DRAWS", "300"))
SEED = 20260910


# ---------------------------------------------------------------- tape ------
def _get(url, tries=3):
    for k in range(tries):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": "lucy/1.0"})
            return json.loads(urllib.request.urlopen(r, timeout=30).read())
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(1.5 * (k + 1))


def venue_books():
    d = _get(API + "/api/v1/orderBookDetails")
    out = []
    for b in (d.get("order_book_details") or []):
        sym = b.get("symbol")
        try:
            vol = float(b.get("daily_quote_token_volume") or 0.0) / 1e6
        except Exception:
            vol = 0.0
        if not sym:
            continue
        out.append({"sym": sym, "id": int(b["market_id"]), "vol_m": vol,
                    "idx": b.get("strategy_index")})
    return out


def universe():
    books = venue_books()
    crypto = [b for b in books
              if fleet_bus.is_crypto(b["sym"])
              and b["vol_m"] >= MIN_VOL_M]
    crypto.sort(key=lambda b: -b["vol_m"])
    return crypto[:UNIVERSE_N]


def fetch(sym, mid, res, res_sec, pages):
    path = os.path.join(CACHE, f"{sym}_{res}.json")
    if os.path.exists(path):
        return json.load(open(path))
    rows, end = {}, int(time.time())
    for _ in range(pages):
        url = (f"{API}/api/v1/candles?market_id={mid}&resolution={res}"
               f"&start_timestamp={end - 500 * res_sec}"
               f"&end_timestamp={end}&count_back=500")
        page = (_get(url) or {}).get("c") or []
        if not page:
            break
        for c in page:
            t = int(c["t"]) // 1000
            rows[t] = [t, float(c["o"]), float(c["h"]), float(c["l"]),
                       float(c["c"]), float(c.get("v") or 0.0)]
        oldest = min(int(c["t"]) // 1000 for c in page)
        if len(page) < 400:
            break
        end = oldest - 1
        time.sleep(0.2)
    out = [rows[t] for t in sorted(rows)]
    os.makedirs(CACHE, exist_ok=True)
    json.dump(out, open(path, "w"))
    return out


def as_bars(rows):
    return {"t": [r[0] for r in rows], "o": [r[1] for r in rows],
            "h": [r[2] for r in rows], "l": [r[3] for r in rows],
            "c": [r[4] for r in rows], "v": [r[5] for r in rows]}


# --------------------------------------------------------------- cells ------
class Cell:
    """A (side, entry-rule, bracket) triple. Entry rules are computed on the
    SHARED series helpers imported from lighter_family_bot — never retyped."""

    def __init__(self, name, side, tf, res_sec, roi, stop, max_hold_min,
                 rule, exit_rule=None, min_bars=210, max_open=6):
        self.name, self.side, self.tf, self.res_sec = name, side, tf, res_sec
        self.roi, self.stop, self.max_hold_min = roi, stop, max_hold_min
        self.rule, self.exit_rule = rule, exit_rule
        self.min_bars, self.max_open = min_bars, max_open

    def roi_bar(self, age_min):
        best = None
        for k in sorted(self.roi):
            if age_min >= k:
                best = self.roi[k]
        return best


def _series(bars):
    c = bars["c"]
    rsi = fam.rsi_series(c, 14)
    e50 = fam.ema_series(c, 50)
    e200 = fam.ema_series(c, 200)
    return rsi, e50, e200


def _bb(bars, i, n=20, k=2.0):
    h, l, c = bars["h"], bars["l"], bars["c"]
    if i < n - 1:
        return None, None
    tp = [(h[j] + l[j] + c[j]) / 3.0 for j in range(i - n + 1, i + 1)]
    mid = sum(tp) / n
    sd = fam.stdev(tp)
    return mid - k * sd, mid + k * sd


def mum_long(bars, i, s):
    rsi, e50, e200 = s
    if None in (rsi[i], e50[i], e200[i]):
        return False
    return rsi[i] < 38.0 and not (e50[i] > e200[i]) and bars["v"][i] > 0


def mum_short(bars, i, s, bar=62.0):
    """MIRROR of mum: overbought, and NOT inside a downtrend."""
    rsi, e50, e200 = s
    if None in (rsi[i], e50[i], e200[i]):
        return False
    return rsi[i] > bar and not (e50[i] < e200[i]) and bars["v"][i] > 0


def avo_long(bars, i, s):
    rsi, e50, e200 = s
    if None in (rsi[i], e50[i], e200[i]) or i < 20:
        return False
    lo, _hi = _bb(bars, i)
    if lo is None:
        return False
    return (e50[i] > e200[i] and rsi[i] < 42.0 and bars["c"][i] < lo
            and bars["v"][i] > 0)


def avo_short(bars, i, s, bar=58.0):
    """MIRROR of avo: a rip into the upper band, inside a DOWNTREND."""
    rsi, e50, e200 = s
    if None in (rsi[i], e50[i], e200[i]) or i < 20:
        return False
    _lo, hi = _bb(bars, i)
    if hi is None:
        return False
    return (e50[i] < e200[i] and rsi[i] > bar and bars["c"][i] > hi
            and bars["v"][i] > 0)


def avo_short_exit(bars, i, s):
    rsi, _e50, _e200 = s
    if rsi[i] is None or i < 20:
        return False
    h, l = bars["h"], bars["l"]
    rng_hi = fam.roll_max(h, 20, i - 1)
    rng_lo = fam.roll_min(l, 20, i - 1)
    if rng_hi is None or rng_lo is None:
        return False
    band = max(rng_hi - rng_lo, 1e-9)
    buy_zone = rng_lo + 0.15 * band
    return (rsi[i] < 35.0 or bars["c"][i] <= buy_zone) and bars["v"][i] > 0


# --------------------------------------------------------------- walker -----
def walk(cell, bars, s, entry_i, slip_bps):
    """LAG-1: signal at bar entry_i's close, fill at entry_i+1's OPEN.
    Returns (pnl_pct, exit_reason, held_min, exit_i) or None."""
    o, h, l, c, t = bars["o"], bars["h"], bars["l"], bars["c"], bars["t"]
    j0 = entry_i + 1
    if j0 >= len(c):
        return None
    px_in = o[j0]
    if px_in <= 0:
        return None
    sgn = 1.0 if cell.side == "long" else -1.0
    fric = slip_bps / 10000.0
    for j in range(j0, len(c)):
        age_min = (t[j] - t[j0]) // 60 + int(cell.res_sec // 60)
        # adverse first (a stop wins a same-bar tie -- conservative)
        adverse = (l[j] / px_in - 1.0) if sgn > 0 else (px_in / h[j] - 1.0)
        if adverse <= cell.stop:
            gross = cell.stop
            return (gross - 2 * fric, "sl", age_min, j)
        bar = cell.roi_bar(age_min)
        if bar is not None and bar > 0:
            fav = (h[j] / px_in - 1.0) if sgn > 0 else (px_in / l[j] - 1.0)
            if fav >= bar:
                return (bar - 2 * fric, "roi", age_min, j)
        if cell.exit_rule is not None and j > j0 and cell.exit_rule(bars, j, s):
            gross = sgn * (c[j] / px_in - 1.0)
            return (gross - 2 * fric, "signal", age_min, j)
        if age_min >= cell.max_hold_min:
            gross = sgn * (c[j] / px_in - 1.0)
            return (gross - 2 * fric, "max_hold", age_min, j)
    return None


def portfolio(cell, tape, series, slip_bps, rule=None, entries_by_coin=None):
    """Sequential, capped, one position per coin -- what the book will do."""
    rule = rule or cell.rule
    syms = sorted(tape)
    n_bars = {sy: len(tape[sy]["c"]) for sy in syms}
    # a shared clock over the union of timestamps
    stamps = sorted({t for sy in syms for t in tape[sy]["t"]})
    idx = {sy: {t: k for k, t in enumerate(tape[sy]["t"])} for sy in syms}
    open_pos, closes = {}, []
    forced = entries_by_coin or {}
    for ts in stamps:
        for sy in list(open_pos):
            if open_pos[sy]["exit_ts"] <= ts:
                closes.append(open_pos.pop(sy))
        for sy in syms:
            if sy in open_pos or len(open_pos) >= cell.max_open:
                continue
            i = idx[sy].get(ts)
            if i is None or i < cell.min_bars or i + 1 >= n_bars[sy]:
                continue
            fire = (i in forced[sy]) if forced else rule(tape[sy], i, series[sy])
            if not fire:
                continue
            r = walk(cell, tape[sy], series[sy], i, slip_bps)
            if r is None:
                continue
            pnl, why, held, ex_j = r
            open_pos[sy] = {"sym": sy, "pnl": pnl, "why": why, "held": held,
                            "open_ts": tape[sy]["t"][i + 1],
                            "exit_ts": tape[sy]["t"][ex_j]}
    closes.extend(open_pos.values())
    closes.sort(key=lambda d: d["open_ts"])
    return closes


def stats(closes):
    if not closes:
        return {"n": 0}
    r = [d["pnl"] for d in closes]
    n = len(r)
    m = statistics.fmean(r)
    sd = statistics.pstdev(r) if n < 2 else statistics.stdev(r)
    se = sd / math.sqrt(n) if n and sd else 0.0
    t = (m / se) if se else 0.0
    half = n // 2
    h1 = statistics.fmean(r[:half]) if half else 0.0
    h2 = statistics.fmean(r[half:]) if n - half else 0.0
    eq, peak, dd = 0.0, 0.0, 0.0
    for x in r:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    span_d = ((closes[-1]["open_ts"] - closes[0]["open_ts"]) / 86400.0) or 1.0
    n_req = n * (2.0 / t) ** 2 if t > 0 else None
    return {"n": n, "mean_pct": 100 * m, "t": t, "h1_pct": 100 * h1,
            "h2_pct": 100 * h2, "maxdd_pct": 100 * dd, "span_d": span_d,
            "rate_30d": 30.0 * n / span_d,
            "win_pct": 100 * sum(1 for x in r if x > 0) / n,
            "days_to_gate": (n_req / (n / span_d)) if n_req else None,
            "med_hold_h": statistics.median(d["held"] for d in closes) / 60.0}


def matched_null(cell, tape, series, slip_bps, real, draws=NULL_DRAWS):
    """(hm): same coins, same counts, same window, same bracket, same SIDE --
    only the entry MINUTE is drawn at random."""
    per_coin = {}
    for d in real:
        per_coin.setdefault(d["sym"], 0)
        per_coin[d["sym"]] += 1
    if not per_coin:
        return None
    rng = random.Random(SEED)
    means = []
    for _ in range(draws):
        picks = {}
        for sy, k in per_coin.items():
            hi = len(tape[sy]["c"]) - 2
            lo = cell.min_bars
            if hi <= lo:
                picks[sy] = set()
                continue
            picks[sy] = set(rng.sample(range(lo, hi), min(k, hi - lo)))
        for sy in tape:
            picks.setdefault(sy, set())
        cl = portfolio(cell, tape, series, slip_bps, entries_by_coin=picks)
        if cl:
            means.append(statistics.fmean(d["pnl"] for d in cl))
    if not means:
        return None
    rm = statistics.fmean(d["pnl"] for d in real)
    ge = sum(1 for x in means if x >= rm) / len(means)
    return {"null_mean_pct": 100 * statistics.fmean(means),
            "null_sd_pct": 100 * statistics.pstdev(means),
            "excess_pct": 100 * (rm - statistics.fmean(means)),
            "p_random_ge": ge, "draws": len(means)}


# ---------------------------------------------------- calibration gates -----
def _ramp(drift_day, n=600):
    """A synthetic tape with a known compounding drift; bar opens chain to the
    previous close, exactly as a real candle series does."""
    bars = {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    px, t0 = 100.0, 1_700_000_000
    step = (1.0 + drift_day) ** (1.0 / 24.0)
    for k in range(n):
        nxt = px * step
        bars["t"].append(t0 + k * 3600)
        bars["o"].append(px)
        bars["h"].append(max(px, nxt))
        bars["l"].append(min(px, nxt))
        bars["c"].append(nxt)
        bars["v"].append(1.0)
        px = nxt
    return bars


def positive_control(slip_bps=0.0):
    """Plant KNOWN drifts and require the walker to recover each of its three
    exit branches, on BOTH sides, at the right size.  A walker that cannot see
    a 2%/day drift cannot be trusted to see 0.2%, and one whose short side is
    sign-flipped would read every short cell backwards.

    Three arms, because a single arm exercises a single branch:
      max_hold  drift +/-2%/day  -> mean must be ~ +2.00% after a 24h hold
      roi       drift +/-40%/day -> must exit `roi` AT the ladder bar (2.0%)
      sl        drift -/+40%/day -> must exit `sl` AT the stop (-4.0%)
    """
    cell_for = lambda side: Cell(                       # noqa: E731
        "control", side, "1h", 3600, {0: 0.02, 1440: 0.0}, -0.04, 1440,
        lambda b, i, s: True, min_bars=1, max_open=1)
    out, ok = {}, True
    for side, sgn in (("long", +1.0), ("short", -1.0)):
        cell = cell_for(side)
        for arm, drift, want_why, want_pct in (
                ("max_hold", sgn * 0.02, "max_hold", 2.0),
                ("roi", sgn * 0.40, "roi", 2.0),
                ("sl", -sgn * 0.40, "sl", -4.0)):
            bars = _ramp(drift)
            s = _series(bars)
            r = [x for x in (walk(cell, bars, s, i, slip_bps)
                             for i in range(1, 500, 24)) if x]
            if not r:
                out[f"{side}/{arm}"] = {"n": 0}
                ok = False
                continue
            mean = 100 * statistics.fmean(x[0] for x in r)
            share = sum(1 for x in r if x[1] == want_why) / len(r)
            hit = abs(mean - want_pct) <= 0.05 and share >= 0.95
            ok = ok and hit
            out[f"{side}/{arm}"] = {"n": len(r), "mean_pct": mean,
                                    "why_share": share, "want": want_pct,
                                    "ok": hit}
    return ok, out


def long_reproduction(tape1h, s1h, tape4h, s4h, slip_bps):
    """Run the SHIPPED long cells through this walker. Reported, not a bar --
    the books trade different universes and real fills, so an exact match is
    not expected; a WRONG SIGN would be."""
    mum = Cell("mum-long(repro)", "long", "1h", 3600, fam.OversoldRebound.roi,
               -0.04, fam.OversoldRebound.MAX_HOLD_MIN, mum_long,
               min_bars=210, max_open=12)
    avo = Cell("avo-long(repro)", "long", "4h", 14400, fam.SwingDip.roi,
               -0.10, 20160, avo_long, exit_rule=None, min_bars=230, max_open=6)
    return {"mum": stats(portfolio(mum, tape1h, s1h, slip_bps)),
            "avo": stats(portfolio(avo, tape4h, s4h, slip_bps))}


# ------------------------------------------------ dose-response / selection --
def dose(cell_factory, tape, series, slip_bps, bars_list):
    rows = []
    for b in bars_list:
        cell = cell_factory(b)
        cl = portfolio(cell, tape, series, slip_bps)
        st = stats(cl)
        st["bar"] = b
        rows.append(st)
    return rows


def selection_premium(rows):
    """(uz): picking the best of N cells inflates its t by roughly the spread
    of the unselected distribution. Report the gap, never hide it."""
    ts = [r["t"] for r in rows if r.get("n", 0) >= 10]
    if len(ts) < 3:
        return None
    return {"best_t": max(ts), "median_t": statistics.median(ts),
            "premium_t": max(ts) - statistics.median(ts), "cells": len(ts)}


# ------------------------------------------------------ I20: the supply ------
def overlap_report(tape1h, s1h):
    """I20 — before a row is minted, name the coins the gate yields and every
    LIVING book whose gate already admits them.  The only living book that
    could take S1's supply is 🚀 bezos: it fades an extreme up-impulse on the
    same 1h crypto tape, which IS a short on a coin that just ran.  A count
    cannot answer this (concentration is a property of the COIN), so the
    triggers are driven bar-by-bar and the JOINT rate is measured.

    Driven, never re-typed: `impulse_signal` is imported from the engine 🚀
    bezos actually runs, at bezos's own IMPULSE_K (a second copy of a rule is
    a second rule, (hj))."""
    import lighter_book_douglas_bot as dou
    k_bezos = 2.2                       # book-bezos's DOUGLAS_IMPULSE_K
    n_s1 = n_bez = n_both = 0
    coins_s1, coins_both = set(), set()
    for sy, bars in tape1h.items():
        s = s1h[sy]
        rows = list(zip(bars["t"], bars["o"], bars["h"], bars["l"], bars["c"]))
        for i in range(max(210, dou.ATR_N + 3), len(bars["c"]) - 1):
            a = mum_short(bars, i, s)
            sig = dou.impulse_signal(rows[:i + 1], k=k_bezos)
            b = bool(sig and sig[0] == "short")
            n_s1 += a
            n_bez += b
            if a:
                coins_s1.add(sy)
            if a and b:
                n_both += 1
                coins_both.add(sy)
    return {"s1_fires": n_s1, "bezos_short_fires": n_bez, "both": n_both,
            "share_of_s1_taken": (n_both / n_s1) if n_s1 else None,
            "coins_s1": len(coins_s1), "coins_both": sorted(coins_both)}


# ----------------------------------------------------------------- main -----
def main():
    slip = float(os.environ.get("SHORT_MIRROR_SLIP_BPS", "5.0"))
    print("=" * 78)
    print("SHORT MIRRORS OF 👩 mum AND 🙏 avo — Lighter's own tape")
    print("=" * 78)

    ok, ctl = positive_control()
    print(f"\n[calibration] positive control: {'PASS' if ok else 'FAIL'}")
    for k, v in ctl.items():
        print(f"   {k:<16} n={v.get('n', 0):>3}"
              f" mean={v.get('mean_pct', 0):+.3f}% (want"
              f" {v.get('want', 0):+.2f}) branch={v.get('why_share', 0):.2f}"
              f" {'ok' if v.get('ok') else 'MISS'}")
    if not ok:
        print("REFUSING: the walker cannot recover a planted drift.")
        return 2

    uni = universe()
    print(f"\n[tape] {len(uni)} crypto books >= ${MIN_VOL_M}M, top {UNIVERSE_N}"
          f" by 24h volume: {', '.join(b['sym'] for b in uni[:12])}...")
    tape1h, tape4h = {}, {}
    for b in uni:
        r1 = fetch(b["sym"], b["id"], "1h", 3600, 10)
        r4 = fetch(b["sym"], b["id"], "4h", 14400, 6)
        if len(r1) >= 260:
            tape1h[b["sym"]] = as_bars(r1)
        if len(r4) >= 260:
            tape4h[b["sym"]] = as_bars(r4)
    s1h = {sy: _series(tape1h[sy]) for sy in tape1h}
    s4h = {sy: _series(tape4h[sy]) for sy in tape4h}
    d1 = (max(max(t["t"]) for t in tape1h.values())
          - min(min(t["t"]) for t in tape1h.values())) / 86400.0
    d4 = (max(max(t["t"]) for t in tape4h.values())
          - min(min(t["t"]) for t in tape4h.values())) / 86400.0
    print(f"   1h: {len(tape1h)} coins, {d1:.0f}d   "
          f"4h: {len(tape4h)} coins, {d4:.0f}d")

    rep = long_reproduction(tape1h, s1h, tape4h, s4h, slip)
    print("\n[calibration] the SHIPPED long cells through this same walker")
    for k, st in rep.items():
        if st.get("n"):
            print(f"   {k}-long n={st['n']:>4} mean={st['mean_pct']:+.3f}%"
                  f" t={st['t']:+.2f} rate={st['rate_30d']:.1f}/30d")

    cells = [
        ("S1 mum-mirror (overbought fade, 1h SHORT)",
         lambda b: Cell("S1", "short", "1h", 3600, fam.OversoldRebound.roi,
                        -0.04, fam.OversoldRebound.MAX_HOLD_MIN,
                        lambda bb, i, s, _b=b: mum_short(bb, i, s, _b),
                        min_bars=210, max_open=12),
         tape1h, s1h, [58.0, 60.0, 62.0, 64.0, 66.0, 70.0], 62.0),
        ("S2 avo-mirror (rip in a downtrend, 4h SHORT)",
         lambda b: Cell("S2", "short", "4h", 14400, fam.SwingDip.roi,
                        -0.10, 20160,
                        lambda bb, i, s, _b=b: avo_short(bb, i, s, _b),
                        exit_rule=avo_short_exit, min_bars=230, max_open=6),
         tape4h, s4h, [52.0, 55.0, 58.0, 61.0, 64.0, 68.0], 58.0),
    ]

    verdicts = {}
    for title, factory, tape, series, grid, shipped in cells:
        print("\n" + "-" * 78)
        print(title)
        print("-" * 78)
        rows = dose(factory, tape, series, slip, grid)
        print(f"  {'rsi bar':>8} {'n':>5} {'mean%':>8} {'t':>7} {'h1%':>7}"
              f" {'h2%':>7} {'maxdd%':>7} {'/30d':>6} {'hold_h':>7}")
        for r in rows:
            if not r.get("n"):
                print(f"  {r['bar']:>8.0f}     0")
                continue
            print(f"  {r['bar']:>8.0f} {r['n']:>5} {r['mean_pct']:>+8.3f}"
                  f" {r['t']:>+7.2f} {r['h1_pct']:>+7.3f} {r['h2_pct']:>+7.3f}"
                  f" {r['maxdd_pct']:>7.2f} {r['rate_30d']:>6.1f}"
                  f" {r['med_hold_h']:>7.1f}")
        sel = selection_premium(rows)
        if sel:
            print(f"  selection premium: best t={sel['best_t']:+.2f} vs median"
                  f" {sel['median_t']:+.2f} over {sel['cells']} cells"
                  f"  => +{sel['premium_t']:.2f} t-units of picking")

        cell = factory(shipped)
        real = portfolio(cell, tape, series, slip)
        st = stats(real)
        print(f"\n  SHIPPED BAR ({shipped:.0f}) @ {slip:.1f}bps/side:"
              f" n={st.get('n', 0)}")
        if st.get("n", 0) >= 10:
            print(f"    mean {st['mean_pct']:+.3f}%/trade  t={st['t']:+.2f}"
                  f"  halves {st['h1_pct']:+.3f}/{st['h2_pct']:+.3f}"
                  f"  win {st['win_pct']:.1f}%  maxDD {st['maxdd_pct']:.2f}%")
            print(f"    rate {st['rate_30d']:.1f} closes/30d over"
                  f" {st['span_d']:.0f}d  =>  days-to-gate"
                  f" {st['days_to_gate']:.0f}" if st.get("days_to_gate")
                  else f"    rate {st['rate_30d']:.1f} closes/30d")
            nul = matched_null(cell, tape, series, slip, real)
            if nul:
                print(f"    RANDOM-ENTRY NULL (hm): null mean"
                      f" {nul['null_mean_pct']:+.3f}%  EXCESS"
                      f" {nul['excess_pct']:+.3f}%/trade"
                      f"  P(random >= signal) = {nul['p_random_ge']:.3f}"
                      f"  [{nul['draws']} draws]")
                st["null"] = nul
            for bps in (0.0, 2.0, 10.0):
                s2 = stats(portfolio(cell, tape, series, bps))
                print(f"    friction {bps:>4.1f}bps/side ->"
                      f" mean {s2['mean_pct']:+.3f}%  t={s2['t']:+.2f}")
            byreason = {}
            for d in real:
                byreason.setdefault(d["why"], []).append(d["pnl"])
            print("    exits: " + "  ".join(
                f"{k} n={len(v)} {100*statistics.fmean(v):+.2f}%"
                for k, v in sorted(byreason.items())))
        verdicts[title] = st
    print("\n" + "-" * 78)
    print("I20 SUPPLY CHECK — does S1's cell already belong to a living book?")
    print("-" * 78)
    ov = overlap_report(tape1h, s1h)
    print(f"  S1 (overbought fade) fires on {ov['s1_fires']} coin-bars across"
          f" {ov['coins_s1']} coins")
    print(f"  🚀 bezos (impulse fade, SHORT leg, k=2.2) fires on"
          f" {ov['bezos_short_fires']} coin-bars")
    print(f"  BOTH in the same coin-bar: {ov['both']}"
          + (f"  =>  {100*ov['share_of_s1_taken']:.2f}% of S1's supply is"
             f" already bezos's" if ov['share_of_s1_taken'] is not None else ""))
    if ov["coins_both"]:
        print(f"  coins where they coincide: {', '.join(ov['coins_both'][:12])}")

    print("\n" + "=" * 78)
    json.dump({k: {kk: vv for kk, vv in v.items()}
               for k, v in verdicts.items()},
              open(os.path.join(CACHE, "verdicts.json"), "w"), indent=1,
              default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
