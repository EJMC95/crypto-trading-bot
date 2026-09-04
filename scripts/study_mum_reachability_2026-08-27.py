#!/usr/bin/env python3
"""👩 MUM IS LIVE WITH $300 AND HAS TAKEN ZERO TRADES. IS SHE STUCK OR SLOW?

**Eamon, 27-Aug: *"Let's grow this PnL."*** Real money reads **-$14.95** across
three books, and the cheapest thing in that number is a book producing NOTHING:
👩 mum went live 25-Aug on a fresh sub-account and has **0 closes, 0 open**.

HER OWN ROW NAMES THE BLOCKING TERM, which is what `census` was built for (I18):

    scan: rsi_bar 32.0 · rsi_min 36.3 · near_bar 3 · universe 23
          verdicts {no_signal: 23}

**The LOWEST RSI across all 23 of her coins is 36.3 against a bar of 32.0.**
Nothing is close. So she is not broken and she is not refusing fills — her
entry cell is simply not occurring.

THE QUESTION THIS ANSWERS, and it is I17's: *is that a slow week, or a bar the
tape does not reach?* Those look identical from one snapshot and are opposite
diagnoses — one says wait, the other says feed. The discriminator is the
historical RATE of her exact entry cell over her exact universe.

WHAT IS MEASURED, at each candidate bar:

  * **RATE** — qualifying entry EPISODES per day (runs of consecutive
    qualifying bars collapse to ONE entry, because that is what the bot does:
    it opens once and holds). Counting BARS instead would inflate the rate by
    the length of every dip.
  * **EXPECTANCY through her REAL bracket** — the live roi ladder
    (2.0% -> 0 over 24h), -4% stop, 1440-min cap. The stop is checked BEFORE
    the target within a bar, the conservative convention. A rate without an
    expectancy is how a book gets fed garbage (I19).
  * **A RANDOM-ENTRY NULL** at the same count on the same coins ((hm): on this
    venue a random entry earns for free, so a positive mean is not an edge).
  * **WHICH TERM BINDS** — `rsi < BAR` vs `not (e50 > e200)`. If the trend
    filter is the binding term, moving the RSI bar cannot help at all, and
    every RSI sweep would be measuring the wrong knob.

HER OWN DOCSTRING ALREADY CARRIES A SWEEP (30 -> 32, +0.062%/trade, "trailing
NEGATIVE") and warns that sub-cells do not sum to the union because a wider bar
MERGES adjacent runs and moves the entry earlier. That warning is honoured here
by measuring EPISODES at each bar independently, never by differencing cells.

READ-ONLY. Measures; changes nothing. Uses `tape_cache`, so a re-run is free.
"""
import argparse
import datetime as dt
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import tape_cache                                           # noqa: E402
import lighter_family_bot as fam                            # noqa: E402
from lighter_family_bot import ema_series, rsi_series       # noqa: E402

import importlib.util                                       # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "sse", os.path.join(HERE, "study_sniper_exit_shape_2026-08-20.py"))
_sse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sse)

DAYS = 180

#: THE BAR THE BOOK ACTUALLY RUNS — read from the carrier, never retyped.
#:
#: [28-Aug (vd)] This file hardcoded `32.0` at every call site, and on 27-Aug a
#: concurrent session moved mum's bar to `MUM_RSI_MAX` defaulting to **36.0**
#: ((ve), Eamon's call, shipped knowing 36 is past the measured peak). Every
#: number this study produced for a day therefore described a book the fleet
#: was no longer running — and the gap is not cosmetic: at 12 slots over the
#: top-40, bar 32 reads +0.202%/trade (t=3.21) and bar 36 reads **+0.026%
#: (t=0.47)**. A retyped constant is a constant that drifts, and this one
#: drifted under a live real-money book inside 24 hours.
def live_bar():
    try:
        import lighter_family_bot as _fam
        for s in _fam.STRATEGIES:
            if s.bot == "freqtrade-mum":
                return float(s.RSI_MAX)
    except Exception:                                       # noqa: BLE001
        pass
    return 36.0                     # the shipped default, not a guess
#: Her LIVE bracket, read off the published row rather than retyped from prose:
#: policy.roi {0:0.02, 240:0.016, 480:0.012, 720:0.008, 1080:0.004, 1440:0.0},
#: policy.stoploss -0.04. The ladder is (minutes_held, min_profit_to_exit).
ROI = [(0, 0.02), (240, 0.016), (480, 0.012), (720, 0.008),
       (1080, 0.004), (1440, 0.0)]
STOP = -0.04
BARS = (25.0, 28.0, 30.0, 32.0, 35.0, 38.0, 42.0)


def roi_floor(age_min):
    got = 0.0
    for mins, thr in ROI:
        if age_min >= mins:
            got = thr
    return got


def universe():
    return list(fam.COINS) + list(fam.NONCRYPTO_UNIVERSE)


def load(days=DAYS):
    rows = {r["symbol"]: r for r in _sse.order_book_details()
            if r.get("status") == "active"}
    safe = tape_cache._closed_before("1h")
    lo = safe - days * 86400
    out, missing = {}, []
    for s in universe():
        if s not in rows:
            missing.append(s)
            continue
        b = tape_cache.cached_candles(int(rows[s]["market_id"]), lo, safe, "1h")
        if len(b) >= 250:
            out[s] = b
        else:
            missing.append(s)
    return out, missing, safe - lo


def series(bars):
    ts = sorted(bars)
    c = [bars[t][3] for t in ts]
    h = [bars[t][1] for t in ts]
    lo = [bars[t][2] for t in ts]
    v = [bars[t][4] for t in ts]
    return ts, c, h, lo, v


def walk(c, h, lo, i, entry):
    """Her real bracket from bar i+1. -> (return_frac, exit_reason, bars_held).

    LAG-1: the entry bar itself is never walked. Two conventions disagreeing on
    the entry bar is how this fleet has produced opposite verdicts before, and
    the honest one excludes it.
    """
    for j in range(i + 1, len(c)):
        age = (j - i) * 60
        if (lo[j] - entry) / entry <= STOP:                 # stop first
            return STOP, "sl", j - i
        thr = roi_floor(age)
        if thr > 0 and (h[j] - entry) / entry >= thr:
            return thr, "roi", j - i
        if age >= 1440:
            return (c[j] - entry) / entry, "max_hold", j - i
    return None, None, None


def episodes(bars, bar_max, require_downtrend=True):
    """Entry EPISODES: runs of consecutive qualifying bars collapse to one."""
    ts, c, h, lo, v = series(bars)
    rsi = rsi_series(c, 14)
    e50, e200 = ema_series(c, 50), ema_series(c, 200)
    out, armed = [], True
    binding = {"rsi": 0, "trend": 0, "both": 0}
    for i in range(len(c)):
        if None in (rsi[i], e50[i], e200[i]):
            continue
        rsi_ok = rsi[i] < bar_max
        trend_ok = (not (e50[i] > e200[i])) if require_downtrend else True
        if not (rsi_ok and trend_ok):
            if not rsi_ok and not trend_ok:
                binding["both"] += 1
            elif not rsi_ok:
                binding["rsi"] += 1
            else:
                binding["trend"] += 1
            armed = True
            continue
        if not armed or v[i] <= 0:
            continue
        armed = False
        r, why, held = walk(c, h, lo, i, c[i])
        if r is not None:
            out.append((ts[i], r, why, held, rsi[i]))
    return out, binding


def null_draws(bars, n, rng):
    """Random entries on the SAME coin, same bracket — (hm)'s benchmark."""
    ts, c, h, lo, v = series(bars)
    if len(c) < 60 or n <= 0:
        return []
    out = []
    for _ in range(n):
        i = rng.randrange(30, len(c) - 2)
        r, _w, _hd = walk(c, h, lo, i, c[i])
        if r is not None:
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--no-trend-filter", action="store_true",
                    help="measure the RSI term alone, to see which binds")
    a = ap.parse_args()

    import random
    print(f"loading {a.days}d of 1h tape for mum's universe "
          f"({len(universe())} names) via tape_cache ...")
    tape_cache.reset_stats()
    tape, missing, span = load(a.days)
    s = tape_cache.stats()
    print(f"  {len(tape)} names with usable tape; {len(missing)} without "
          f"({', '.join(missing) if missing else '—'})")
    print(f"  cache: {s['hits']:,} bars from disk, {s['fetched']:,} fetched, "
          f"{s['requests']} venue requests")
    days = span / 86400.0

    rng = random.Random(20260827)
    print(f"\n{'RSI bar':>8}{'episodes':>10}{'per day':>9}{'mean%':>9}"
          f"{'t':>7}{'null%':>8}{'edge%':>8}{'win%':>7}  exits")
    for bar in BARS:
        allr, per_coin, exits = [], {}, {}
        for sym, bars in tape.items():
            eps, _b = episodes(bars, bar, not a.no_trend_filter)
            if not eps:
                continue
            r = [e[1] for e in eps]
            per_coin[sym] = r
            allr += r
            for e in eps:
                exits[e[2]] = exits.get(e[2], 0) + 1
        if not allr:
            print(f"{bar:>8.0f}{0:>10}{0.0:>9.2f}   — no episodes at this bar")
            continue
        nulls = []
        for sym, bars in tape.items():
            nulls += null_draws(bars, len(per_coin.get(sym, [])), rng)
        m = st.mean(allr)
        sd = st.pstdev(allr) * math.sqrt(len(allr) / (len(allr) - 1)) \
            if len(allr) > 1 else 0.0
        t = m / (sd / math.sqrt(len(allr))) if sd > 0 else float("nan")
        nm = st.mean(nulls) if nulls else float("nan")
        win = 100.0 * sum(1 for x in allr if x > 0) / len(allr)
        top = sorted(exits.items(), key=lambda kv: -kv[1])
        print(f"{bar:>8.0f}{len(allr):>10}{len(allr)/days:>9.2f}"
              f"{m*100:>9.3f}{t:>7.2f}{nm*100:>8.3f}{(m-nm)*100:>8.3f}"
              f"{win:>7.0f}  " + " ".join(f"{k}={v}" for k, v in top))

    # WHICH TERM BINDS — the question an RSI sweep cannot answer about itself.
    print(f"\nWHICH TERM BLOCKS ENTRY (bar-level, at the SHIPPED "
          f"RSI_MAX={live_bar():g} — read from the carrier, not retyped):")
    tot = {"rsi": 0, "trend": 0, "both": 0}
    for sym, bars in tape.items():
        _e, b = episodes(bars, live_bar(), True)
        for k in tot:
            tot[k] += b[k]
    n = sum(tot.values()) or 1
    # [(ya)] DERIVED, not retyped. This label read "RSI >= 32" while the row
    # beside it was computed at `live_bar()` — 36 since (ve) — under a header
    # that says "read from the carrier, not retyped". A stale label on a
    # correct number is how the wrong knob gets moved.
    for k, lbl in (("rsi", f"RSI >= {live_bar():g} only"),
                   ("trend", "in an UPTREND only (e50>e200)"),
                   ("both", "both terms fail")):
        print(f"  {lbl:<34}{tot[k]:>9,} bars {100.0*tot[k]/n:>6.1f}%")
    print("\n  If the TREND term dominates, moving the RSI bar cannot unstick "
          "her —\n  the sweep above would be measuring the wrong knob, and "
          "widening it would\n  buy nothing but a looser gate on the days she "
          "can already trade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
