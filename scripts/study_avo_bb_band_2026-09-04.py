#!/usr/bin/env python3
"""🙏 AVO IS TWO CLOSES FROM THE GO-LIVE GATE AND HER ENTRY TERM HAS STOPPED
FIRING. WHAT DOES A BOUNDED RELAXATION COST?

**Eamon, 4-Sep: *"let's run with what works."*** This book is what works, and
it is the fleet's clearest case of I17/I26 decidability: her SHADOW arm passes
**5 of 6** go-live bars era-scoped — mean **+1.802%/trade**, **t=2.39**, both
halves, drawdown, window — and fails only `closes` at **n=28 against a bar of
30**. TWO closes from the gate that governs real money.

**AND SHE CANNOT GET THEM.** Her rule is
`e50>e200 AND rsi<42 AND close < lower-Bollinger AND v>0`. The `(ya)` gauge
made the binding term visible for the first time: live census reads
**`bb_min 1.39 · bb_below 0`** — her closest coin sits 1.39% ABOVE the lower
band and NOT ONE of 43 is below it, while the RSI half is met (`rsi_min 34.4`
against a bar of 42). In a trending tape price rides the UPPER band; the dip
term is structurally starved.

THE QUESTION: her cell requires `c < bb_lo`. What does admitting a BAND above
the line — `c < bb_lo * (1 + k)` — buy in closes, and what does it COST in
expectancy? I26 is explicit that a bounded reversible widening on a book that
cannot be graded defaults to SHIP, and equally explicit that real money still
owes a measured number and an expectancy price (I19). This is that number.

MEASURED, on her own 4h tape, through HER shipped bracket (roi ladder
20%/12%/6% over 14d, -10% stop, max hold) and against a MATCHED RANDOM-ENTRY
NULL on the same coins ((hm): on this venue a random entry earns for free, so
a positive mean is not an edge — only `edge%` may be acted on):

  * k = 0.000  reproduces the SHIPPED rule exactly — the calibration arm. If
               this column does not look like her real ledger, nothing below
               may be believed ((gx): a harness that cannot reproduce what DID
               happen may not say what WOULD have).
  * RECENCY  — daily buckets INCLUDING ZERO DAYS, because the whole problem is
               a cell that stopped; an average cannot see a cliff ((yb)).
  * CONCENTRATION — best coin share, because a widening carried by one coin is
               not a widening.

DECLARED LIMIT: her era sample is n=28. Any k chosen here is a HYPOTHESIS
graded forward on her own ledger (I14: the record decides), never a claim that
the replay settled it.

READ-ONLY. Measures; changes nothing.
"""
import collections
import datetime as dt
import importlib.util
import math
import os
import random
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import tape_cache                                            # noqa: E402
import lighter_family_bot as fam                             # noqa: E402
# the venue-details loader, borrowed the way the reachability study borrows it
# (one owner for order_book_details; no second copy of the fetch)
import importlib.util                                        # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "sse", os.path.join(HERE, "study_sniper_exit_shape_2026-08-20.py"))
_sse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sse)

TF = "4h"
SRC_TF = "1h"          # tape_cache has no 4h; we aggregate (see resample_4h)
DAYS = int(os.environ.get("AVO_DAYS", "180"))
BARS_PER_DAY = 6.0
#: her shipped bracket, read from the carrier where possible
STOP = -0.10
ROI = ((0, 0.20), (5760, 0.12), (11520, 0.06), (20160, 0.0))   # minutes -> roi
MAX_HOLD_MIN = 20160
MIN_BARS = 230


def roi_floor(age_min):
    cur = 0.0
    for mins, r in ROI:
        if age_min >= mins:
            cur = r
    return cur


def universe():
    return list(fam.COINS) + list(fam.NONCRYPTO_UNIVERSE)


def resample_4h(b):
    """1h -> 4h, aligned to the venue's own 00/04/08/12/16/20 UTC boundaries.

    DECLARED: `tape_cache` carries no 4h resolution (STEP = 1m/5m/15m/1h/1d),
    so her 4h tape is AGGREGATED from 1h here rather than fetched. A 4h candle
    IS the aggregate of its four 1h candles — open of the first, close of the
    last, max high, min low, summed volume — so this is exact, not an
    approximation; what it depends on is the ALIGNMENT, pinned to the UTC
    boundary the venue itself uses. A partial group is DROPPED rather than
    emitted as a short bar, because a half-formed candle would hand the rule a
    close that never existed.

    In and out: tape_cache's own {bar_ts: (o, h, l, c, quote_vol)}.
    """
    groups = {}
    for t in sorted(b):
        sec = t / 1000 if t > 1e11 else t
        groups.setdefault(int(sec - (sec % 14400)), []).append(t)
    out = {}
    for start, ks in groups.items():
        if len(ks) != 4:                        # partial group at either end
            continue
        rows = [b[k] for k in ks]
        out[start] = (rows[0][0],
                      max(r[1] for r in rows),
                      min(r[2] for r in rows),
                      rows[-1][3],
                      sum(r[4] for r in rows))
    return out


def load(days=DAYS):
    rows = {r["symbol"]: r for r in _sse.order_book_details()
            if r.get("status") == "active"}
    safe = tape_cache._closed_before(SRC_TF)
    lo = safe - days * 86400
    out, missing = {}, []
    for s in universe():
        if s not in rows:
            missing.append(s)
            continue
        raw = tape_cache.cached_candles(int(rows[s]["market_id"]), lo, safe,
                                        SRC_TF)
        b = resample_4h(raw) if raw else None
        if b and len(b) >= MIN_BARS:
            out[s] = b
        else:
            missing.append(s)
    return out, missing, safe - lo


def series(bars):
    """tape_cache's shape is {bar_ts: (o, h, l, c, quote_vol)} — a dict keyed
    by timestamp, NOT column arrays. Same accessor the reachability study uses,
    so the two instruments read the tape identically."""
    ts = sorted(bars)
    c = [bars[t][3] for t in ts]
    h = [bars[t][1] for t in ts]
    lo = [bars[t][2] for t in ts]
    v = [bars[t][4] for t in ts]
    return ts, c, h, lo, v


def stdev(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def walk(c, h, lo, i, entry):
    """Her bracket, LAG-1 (entry bar excluded — the (ne) convention), stop
    checked BEFORE the target within a bar (conservative)."""
    for j in range(i + 1, len(c)):
        age = (j - i) * (24.0 / BARS_PER_DAY) * 60.0
        if (lo[j] - entry) / entry <= STOP:
            return STOP, "sl", j - i
        tgt = roi_floor(age)
        if tgt > 0 and (h[j] - entry) / entry >= tgt:
            return tgt, "roi", j - i
        if age >= MAX_HOLD_MIN:
            return (c[j] - entry) / entry, "max_hold", j - i
    return None, None, None


def episodes(bars, k):
    """Her SHIPPED cell with the BB line moved to `bb_lo * (1 + k)`.
    k=0 is the shipped rule byte-for-byte."""
    ts, c, h, lo, v = series(bars)
    rsi = fam.rsi_series(c, 14)
    e50, e200 = fam.ema_series(c, 50), fam.ema_series(c, 200)
    tp = [(h[j] + lo[j] + c[j]) / 3.0 for j in range(len(c))]
    out, armed = [], True
    for i in range(len(c)):
        if i < 20 or None in (rsi[i], e50[i], e200[i]):
            continue
        win = tp[i - 19:i + 1]
        bb_mid = sum(win) / 20.0
        bb_lo = bb_mid - 2.0 * stdev(win)
        ok = (e50[i] > e200[i] and rsi[i] < 42.0
              and c[i] < bb_lo * (1.0 + k) and v[i] > 0)
        if not ok:
            armed = True
            continue
        if not armed:
            continue
        armed = False
        r, why, held = walk(c, h, lo, i, c[i])
        if r is not None:
            out.append((ts[i], r, why))
    return out


def null_draws(bars, n, rng):
    ts, c, h, lo, v = series(bars)
    out = []
    for _ in range(n * 3):
        i = rng.randrange(20, max(21, len(c) - 2))
        r, why, held = walk(c, h, lo, i, c[i])
        if r is not None:
            out.append(r)
    return out


def day_of(ts):
    return dt.datetime.utcfromtimestamp(ts / 1000 if ts > 1e11 else ts).date()


def main():
    tape, missing, span = load()
    days = span / 86400.0
    print(f"{DAYS}d of {TF} tape · {len(tape)} coins ({len(missing)} without) "
          f"· shipped cell: e50>e200 AND rsi<42 AND c<bb_lo AND v>0")
    rng = random.Random(20260904)
    print(f"\n{'k (band)':<10}{'eps':>6}{'/30d':>8}{'mean%':>9}{'t':>7}"
          f"{'null%':>8}{'edge%':>8}{'win%':>6}   exits")
    print("-" * 76)
    keep = {}
    for k in (0.000, 0.005, 0.010, 0.015, 0.020, 0.030):
        per_coin, allr, nulls, ex = {}, [], [], collections.Counter()
        for sym, bars in tape.items():
            eps = episodes(bars, k)
            per_coin[sym] = [e[1] for e in eps]
            allr += per_coin[sym]
            for e in eps:
                ex[e[2]] += 1
        if not allr:
            print(f"{k:<10.3f}{0:>6}   — no episodes")
            continue
        for sym, bars in tape.items():
            nulls += null_draws(bars, len(per_coin.get(sym, [])), rng)
        m = st.mean(allr)
        sd = (st.pstdev(allr) * math.sqrt(len(allr) / (len(allr) - 1))
              if len(allr) > 1 else 0.0)
        t = m / (sd / math.sqrt(len(allr))) if sd > 0 else float("nan")
        nm = st.mean(nulls) if nulls else float("nan")
        win = 100.0 * sum(1 for x in allr if x > 0) / len(allr)
        print(f"{k:<10.3f}{len(allr):>6}{30.0*len(allr)/days:>8.1f}{m*100:>9.3f}"
              f"{t:>7.2f}{nm*100:>8.3f}{(m-nm)*100:>8.3f}{win:>6.0f}   "
              + " ".join(f"{a}={b}" for a, b in ex.most_common(3)))
        keep[k] = (per_coin, allr)

    print("\nDAILY EPISODES, ZEROS INCLUDED (last 14d) — does the widening fire "
          "in the tape she has NOW?")
    last = None
    for sym, bars in tape.items():
        d = day_of(series(bars)[0][-1])
        last = d if last is None or d > last else last
    cols = [0.000, 0.010, 0.020]
    buckets = {}
    for k in cols:
        cnt = collections.Counter()
        for sym, bars in tape.items():
            for e in episodes(bars, k):
                cnt[day_of(e[0])] += 1
        buckets[k] = cnt
    print("   date        " + "".join(f"k={k:<8.3f}" for k in cols))
    cur = last - dt.timedelta(days=13)
    tots = collections.Counter()
    while cur <= last:
        row = "".join(f"{buckets[k].get(cur,0):<10}" for k in cols)
        for k in cols:
            tots[k] += buckets[k].get(cur, 0)
        print(f"   {str(cur):<12}{row}")
        cur += dt.timedelta(days=1)
    print(f"   {'14d total':<12}" + "".join(f"{tots[k]:<10}" for k in cols))

    for k in (0.010, 0.020):
        if k not in keep:
            continue
        per_coin, allr = keep[k]
        tot = sum(sum(v) for v in per_coin.values())
        best = max(per_coin.items(), key=lambda kv: sum(kv[1]))
        if tot:
            print(f"\nCONCENTRATION k={k}: best coin {best[0]} = "
                  f"{100.0*sum(best[1])/tot:.1f}% of total over {len(allr)} trades")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
