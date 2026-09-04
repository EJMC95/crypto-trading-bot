#!/usr/bin/env python3
"""👩 MUM'S CELL WENT TO ZERO WHEN THE REGIME TURNED. IS THERE A COUNTERPART
CELL THAT FIRES IN THE TAPE SHE NOW HAS?

**Eamon, 4-Sep: *"Bots are still not trading."*** He was right twice, and the
second time the answer was not the one I gave first.

WHAT IS ESTABLISHED BEFORE THIS SCRIPT RUNS (`(ya)`, and the daily bucket that
closed it): her cell fired **19 times on 2026-09-02 and exactly ZERO on 09-03
and 09-04** — a cliff, not a dry spell, matching her live idle to the hour. Her
config is already the measured optimum of everything reachable: bar 38 returns
2.78 %-units/day against 2.31 at bar 32, 1.19 at bar 42, and 1.43 with the
trend term dropped. **There is no setting of the existing cell that trades
today**, because the cell is `rsi < BAR and NOT uptrend` and the venue is in a
broad uptrend (regime_oracle: risk-on, 9 long / 0 short, BTC +12.6% over its
ema200).

THE QUESTION THIS ANSWERS: her rule refuses the one thing the tape is offering
— a coin that is oversold *inside* an uptrend (her live census reads
`uptrend_blocked: 1` against `rsi_min 36.5 < bar 38.0`). Is that counterpart
cell an EDGE, or just the nearest available trade?

WHY IT IS NOT OBVIOUS, and why this must be measured rather than assumed:
`(qu)` measured the `e50>e200` filter as **ACTIVELY DESTRUCTIVE** on 🙏 avo —
adding it lowered every base's mean. That is a real prior against this cell.
But it was measured on avo's 4h SwingDip with a Bollinger conjunct, not on
mum's 1h oversold cell, so it transfers as a WARNING and not as a verdict —
applying one book's evidence to another's cell is the `(lk)` error this fleet
has already paid for.

WHAT IS MEASURED, all through the SHIPPED bracket (roi ladder / -4% stop /
max hold) via the reachability study's own `walk`, so this script owns no
second copy of the exit rule ((hj)):
  * RATE      — entry EPISODES per day (runs collapse to one entry: what the
                bot does is open once and hold)
  * EXPECTANCY— mean %/trade through that bracket
  * THE NULL  — matched random entries on the SAME coins ((hm): on this venue
                a random entry earns for free, so a positive mean is not an
                edge). `edge%` is the only column that may be acted on.
  * RECENCY   — a DAILY bucket including ZERO days. The whole point is whether
                the cell fires in the tape she has NOW; an average over 60d
                hides exactly the cliff that started this. My own first cut of
                this used a Counter and silently dropped the zero days, which
                reads as "accelerating" when the truth is "stopped".
  * CONCENTRATION — best coin / best day share, because a cell carried by one
                coin is not a cell (the (po) tail lesson).

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

_spec = importlib.util.spec_from_file_location(
    "mr", os.path.join(HERE, "study_mum_reachability_2026-08-27.py"))
mr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mr)
from lighter_family_bot import ema_series, rsi_series      # noqa: E402

DAYS = int(os.environ.get("SLEEVE_DAYS", "60"))


def episodes_trend(bars, bar_max, want_uptrend):
    """Mum's cell with the TREND TERM SET BY THE CALLER.

    `want_uptrend=False` reproduces the shipped rule exactly (`not uptrend`);
    `True` is the proposed counterpart sleeve. Same bracket walk, same episode
    collapsing, same `v>0` guard — only the trend conjunct differs, so the two
    columns are comparable by construction.
    """
    ts, c, h, lo, v = mr.series(bars)
    rsi = rsi_series(c, 14)
    e50, e200 = ema_series(c, 50), ema_series(c, 200)
    out, armed = [], True
    for i in range(len(c)):
        if None in (rsi[i], e50[i], e200[i]):
            continue
        up = e50[i] > e200[i]
        ok = (rsi[i] < bar_max) and (up if want_uptrend else (not up))
        if not ok:
            armed = True
            continue
        if not armed or v[i] <= 0:
            continue
        armed = False
        r, why, held = mr.walk(c, h, lo, i, c[i])
        if r is not None:
            out.append((ts[i], r, why, held, rsi[i]))
    return out


def day_of(ts):
    return dt.datetime.utcfromtimestamp(ts / 1000 if ts > 1e11 else ts).date()


def main():
    tape, missing, span = mr.load(DAYS)
    days = span / 86400.0
    print(f"{DAYS}d of 1h tape · {len(tape)} coins with usable tape "
          f"({len(missing)} without) · shipped bar {mr.live_bar():g}")
    rng = random.Random(20260904)

    print(f"\n{'cell':<22}{'bar':>5}{'eps':>6}{'/day':>7}{'mean%':>8}{'t':>7}"
          f"{'null%':>8}{'edge%':>8}{'win%':>6}")
    print("-" * 78)
    results = {}
    for label, want_up in (("SHIPPED not-uptrend", False),
                           ("PROPOSED uptrend", True)):
        for bar in (32.0, 35.0, 38.0, 42.0):
            per_coin, allr, nulls = {}, [], []
            for sym, bars in tape.items():
                eps = episodes_trend(bars, bar, want_up)
                per_coin[sym] = [e[1] for e in eps]
                allr += per_coin[sym]
            if not allr:
                print(f"{label:<22}{bar:>5.0f}{0:>6}{0.0:>7.2f}   — none")
                continue
            for sym, bars in tape.items():
                nulls += mr.null_draws(bars, len(per_coin.get(sym, [])), rng)
            m = st.mean(allr)
            sd = (st.pstdev(allr) * math.sqrt(len(allr) / (len(allr) - 1))
                  if len(allr) > 1 else 0.0)
            t = m / (sd / math.sqrt(len(allr))) if sd > 0 else float("nan")
            nm = st.mean(nulls) if nulls else float("nan")
            win = 100.0 * sum(1 for x in allr if x > 0) / len(allr)
            print(f"{label:<22}{bar:>5.0f}{len(allr):>6}{len(allr)/days:>7.2f}"
                  f"{m*100:>8.3f}{t:>7.2f}{nm*100:>8.3f}{(m-nm)*100:>8.3f}"
                  f"{win:>6.0f}")
            results[(label, bar)] = (per_coin, allr, m, nm, t)

    # --- RECENCY: does the proposed cell fire in the tape she has NOW? ------
    BAR = mr.live_bar()
    print(f"\nDAILY EPISODES at the shipped bar ({BAR:g}), ZEROS INCLUDED — the "
          f"question an average cannot answer:")
    buckets, last_day = {}, None
    for label, want_up in (("shipped", False), ("proposed", True)):
        cnt = collections.Counter()
        for sym, bars in tape.items():
            for e in episodes_trend(bars, BAR, want_up):
                cnt[day_of(e[0])] += 1
        buckets[label] = cnt
    for sym, bars in tape.items():
        ts_all = mr.series(bars)[0]
        d = day_of(ts_all[-1])
        last_day = d if last_day is None or d > last_day else last_day
    cur = last_day - dt.timedelta(days=13)
    print(f"   {'date':<12}{'shipped':>9}{'proposed':>10}")
    tot_s = tot_p = 0
    while cur <= last_day:
        s, p = buckets["shipped"].get(cur, 0), buckets["proposed"].get(cur, 0)
        tot_s += s
        tot_p += p
        print(f"   {str(cur):<12}{s:>9}{p:>10}   {'#' * min(p, 30)}")
        cur += dt.timedelta(days=1)
    print(f"   {'14d total':<12}{tot_s:>9}{tot_p:>10}")

    # --- CONCENTRATION: is the cell carried by one coin or one day? --------
    key = ("PROPOSED uptrend", BAR)
    if key in results:
        per_coin, allr, m, nm, t = results[key]
        tot = sum(sum(v) for v in per_coin.values())
        best = max(per_coin.items(), key=lambda kv: sum(kv[1]))
        n_pos = sum(1 for v in per_coin.values() if sum(v) > 0)
        print(f"\nCONCENTRATION at bar {BAR:g}: {len(allr)} trades over "
              f"{len(per_coin)} coins, {n_pos} with positive total.")
        print(f"   best coin {best[0]} = {100.0*sum(best[1])/tot:.1f}% of total"
              if tot else "   total is zero")
        ex = [r for s, v in per_coin.items() if s != best[0] for r in v]
        if ex:
            print(f"   ex-best-coin: n={len(ex)} mean={st.mean(ex)*100:.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
