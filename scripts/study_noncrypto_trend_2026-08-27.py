#!/usr/bin/env python3
"""Does a simple TREND/MOMENTUM rule have any edge on Lighter's UNCLAIMED
non-crypto markets?  (27-Aug-2026)

MEASUREMENT ONLY.  This script builds no book, moves no lever, touches no bot.
It answers one question with numbers: on the 21 non-crypto markets >=$0.5M/day
that no living directional book scans, does a textbook cross-sectional
momentum / time-series trend / short-horizon reversal rule beat a coin flip?

THE METHODOLOGY RULES THIS FILE OBEYS (they are the whole value of it):

* **NON-OVERLAPPING HOLDS.**  Every trade in a candidate is disjoint in time
  from the next trade of the same name.  Overlapping windows make `t` a
  function of the SAMPLING STRIDE rather than of edge -- `(uf)` measured a
  pooled t going 3.98 -> 0.36 by sweeping only the stride while by-coin t held
  at ~0.6.  So: pooled t is COMPUTED but printed as a diagnostic only, always
  beside the by-coin and by-period numbers that are the real ones.

* **CLUSTERED `t`, TWO WAYS.**  `by-coin` clusters on the symbol (does the rule
  work across NAMES, or is it one name?).  `by-period` clusters on the
  rebalance period (is the portfolio's period return reliably positive, given
  that names inside one period are correlated?).  For a cross-sectional
  long/short book, by-period is the honest headline; by-coin is the
  concentration check.  BOTH must be reported.

* **A RANDOM-ENTRY NULL, ALWAYS.**  This venue's tape is one regime, so a
  positive mean is not an edge ((hm)).  Two nulls:
    - TIMING null: same names, same sides, same hold lengths, entry dates
      shuffled.  Asks "does WHEN we enter carry information?"
    - SELECTION null: same dates, same long/short counts, names drawn at
      random from that day's eligible set.  Asks "does the RANKING carry
      information?"  This is the pointed null for a ranking rule and a
      cross-sectional rule can pass the timing null purely on its net beta.
  P = fraction of draws whose mean >= observed.

* **CONCENTRATION.**  top-1 and top-3 share of total P&L.  top-3 > 50% ==>
  UNDECIDABLE BY TAIL ((po) on book-schwager: top 3 of 298 were 112%).

* **BOTH HALVES**, split at the median entry date.

* **GRID EDGE IS UNBOUNDED, NEVER A VALUE.**  The sensitivity sweep reports a
  best cell that pins a swept parameter at the edge of its grid as UNBOUNDED.

* **I22 ARITHMETIC.**  daily Sharpe S_d of the strategy's own daily P&L series;
  days-to-gate = (2/S_d)^2 CALENDAR days.  >60 ==> a STUDY, not a book.

THE ONE HAZARD THIS TAPE HAS, MEASURED NOT ASSUMED: these are perps on
underlyings whose own markets CLOSE.  A daily bar whose close is byte-identical
to the previous close is a FROZEN mark, not a quiet day.  `panel_report()`
measures the frozen fraction per name, and every candidate is re-run on
weekday-only entries so a result that lives entirely on stale weekend marks
cannot hide (the (lk)/I7 stale-reference signature that 🧭 nav-cook had to test
for directly).

Run:  .venv/bin/python3 scripts/study_noncrypto_trend_2026-08-27.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import pathlib
import random
import statistics as st
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "sse", ROOT / "scripts" / "study_sniper_exit_shape_2026-08-20.py")
_sse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sse)

fetch_candles = _sse.fetch_candles
order_book_details = _sse.order_book_details

# ------------------------------------------------------------------ universe
#: The 21 non-crypto Lighter markets >= $0.5M/day that no living DIRECTIONAL
#: book scans.  Handed in as the study's population; membership is not
#: re-derived here (that is `audit_book_overlap`'s job, not a study's).
UNIVERSE = [
    "SNDK", "SKHYNIXUSD", "SAMSUNGUSD", "SPCX", "MU", "BRENTOIL", "NBIS",
    "DRAM", "CBRS", "SOXL", "US100", "CASHCAT", "INTC", "STRC", "COIN",
    "META", "SMIC", "CRCL", "MRNA", "US500", "AAPL",
]

WINDOW_D = 400          # cap; the venue has far less on most of these
HOLD_D = 5              # non-overlapping hold, in daily bars
MOM_LOOKBACK = 20
REV_LOOKBACK = 5
SMA_N = 50
TOP_K = 3
MIN_ELIGIBLE = 8        # names needed on a rebalance date for a x-sect leg
MIN_TRADES_PER_COIN = 3  # a coin needs this many to contribute a cluster mean
NDRAWS = 400            # random-null draws (task floor is 200)

CACHE = pathlib.Path(
    os.environ.get("NCT_CACHE", "/private/tmp/claude-501/"
                   "-Users-eamonjuaomartins-carrick-Claude-Projects-"
                   "Crypto-Trading-Bot/052c7975-4dbe-47ea-b07e-2c313172e87c/"
                   "scratchpad/nct_panel.json"))


# ============================================================ the price panel
def build_panel(force=False):
    """{symbol: [(day_ts, close, quote_vol), ...]} sorted, daily bars.

    Cached on disk: the venue throttles ~21 req/min and a re-run of the stats
    must never depend on re-fetching the tape (a study whose numbers move
    between runs cannot be checked).
    """
    if CACHE.exists() and not force:
        raw = json.loads(CACHE.read_text())
        return {s: [tuple(x) for x in v] for s, v in raw.items()}

    rows = order_book_details()
    ids = {str(r.get("symbol")): r.get("market_id") for r in rows
           if r.get("symbol") is not None and r.get("market_id") is not None}
    now = int(time.time())
    start = now - WINDOW_D * 86400
    panel = {}
    for i, sym in enumerate(UNIVERSE):
        mid = ids.get(sym)
        if mid is None:
            print(f"  {sym}: NOT ON VENUE -- excluded", file=sys.stderr)
            continue
        cs = fetch_candles(mid, start, now, "1d")
        panel[sym] = [(t, cs[t][3], cs[t][4]) for t in sorted(cs)]
        print(f"  fetched {sym:12s} {len(panel[sym]):4d} bars", file=sys.stderr)
        if i < len(UNIVERSE) - 1:
            time.sleep(3.0)          # ~20/min, inside the venue throttle
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(panel))
    return panel


def _d(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def panel_report(panel):
    """Bars, span, and the FROZEN-MARK fraction per name.

    A frozen bar (close identical to the previous close) is the signature of an
    underlying whose own market is shut.  It is not a quiet day and it is not
    tradeable information; a rule whose whole result sits on frozen entries is
    measuring a stale reference, not an edge.
    """
    print("\n=== PANEL ===")
    print(f"{'symbol':12s} {'bars':>5s} {'first':>11s} {'last':>11s} "
          f"{'frozen%':>8s} {'zero-vol%':>10s}")
    out = {}
    for sym in UNIVERSE:
        s = panel.get(sym) or []
        if len(s) < 2:
            print(f"{sym:12s} {len(s):5d}   (too short)")
            out[sym] = 0.0
            continue
        froz = sum(1 for i in range(1, len(s)) if s[i][1] == s[i - 1][1])
        zv = sum(1 for x in s if not x[2])
        out[sym] = froz / (len(s) - 1)
        print(f"{sym:12s} {len(s):5d} {_d(s[0][0]):%Y-%m-%d} "
              f"{_d(s[-1][0]):%Y-%m-%d} {100*out[sym]:7.1f}% "
              f"{100*zv/len(s):9.1f}%")
    return out


def align(panel, min_bars):
    """-> (days, closes) where days is the sorted union calendar and
    closes[sym][i] is that name's close on days[i] or None."""
    keep = [s for s in UNIVERSE if len(panel.get(s) or []) >= min_bars]
    days = sorted({t for s in keep for t, _, _ in panel[s]})
    closes = {}
    for s in keep:
        m = {t: c for t, c, _ in panel[s]}
        closes[s] = [m.get(t) for t in days]
    return days, closes


# ================================================================= statistics
def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def _t(xs):
    """One-sample t of a list of INDEPENDENT observations."""
    xs = [x for x in xs if x == x]
    if len(xs) < 2:
        return float("nan")
    sd = st.stdev(xs)
    if sd == 0:
        return float("nan")
    return _mean(xs) / (sd / math.sqrt(len(xs)))


def by_coin_t(trades):
    """Cluster on the symbol: one observation per name that has enough trades."""
    g = defaultdict(list)
    for tr in trades:
        g[tr["sym"]].append(tr["ret"])
    means = [_mean(v) for v in g.values() if len(v) >= MIN_TRADES_PER_COIN]
    return _t(means), len(means)


def by_period_t(trades):
    """Cluster on the rebalance period: the portfolio's own return per period.

    Periods are non-overlapping by construction, so these ARE independent
    draws -- this is the number a pooled t over overlapping windows fakes.
    """
    g = defaultdict(list)
    for tr in trades:
        g[tr["entry_i"]].append(tr["ret"])
    per = [_mean(v) for _, v in sorted(g.items())]
    return _t(per), len(per), per


def concentration(trades):
    """(top1_share, top3_share, defined?) of TOTAL P&L, equal notional."""
    rets = sorted((tr["ret"] for tr in trades), reverse=True)
    tot = sum(rets)
    if tot <= 0 or not rets:
        return float("nan"), float("nan"), False
    return rets[0] / tot, sum(rets[:3]) / tot, True


def halves(trades):
    o = sorted(trades, key=lambda tr: tr["entry_i"])
    h = len(o) // 2
    a, b = o[:h], o[h:]
    return (_mean([t["ret"] for t in a]), len(a),
            _mean([t["ret"] for t in b]), len(b))


def daily_sharpe(trades, days, closes):
    """S_d of the strategy's OWN daily P&L series.

    Equal weight, gross 1.0: on each calendar day the book's return is the mean
    of the signed daily returns of whatever it holds.  Days with nothing open
    contribute 0.0 -- they are real calendar days the book must survive, and
    days-to-gate is denominated in calendar days.
    """
    per_day = defaultdict(list)
    for tr in trades:
        s, side = tr["sym"], tr["side"]
        for i in range(tr["entry_i"] + 1, tr["exit_i"] + 1):
            p0, p1 = closes[s][i - 1], closes[s][i]
            if p0 and p1:
                per_day[i].append(side * (p1 / p0 - 1.0))
    if not per_day:
        return float("nan"), float("nan")
    lo, hi = min(per_day), max(per_day)
    series = [_mean(per_day[i]) if per_day.get(i) else 0.0
              for i in range(lo, hi + 1)]
    if len(series) < 3:
        return float("nan"), float("nan")
    sd = st.stdev(series)
    if sd == 0:
        return float("nan"), float("nan")
    s_d = _mean(series) / sd
    return s_d, len(series)


def days_to_gate(s_d):
    """I22: t = S_d*sqrt(T) so T = (2/S_d)^2 calendar days to t=2."""
    if not (s_d == s_d) or s_d <= 0:
        return float("inf")
    return (2.0 / s_d) ** 2


# ================================================================= candidates
# Every candidate returns a list of trades:
#   {sym, side (+1/-1), entry_i, exit_i, ret}
# `ret` is the SIGNED simple return over the hold, i.e. what the book books at
# equal notional.  Lighter is zero-fee (verified below), so no fee term.

def _ret(closes, sym, i, j, side):
    p0, p1 = closes[sym][i], closes[sym][j]
    if not p0 or not p1:
        return None
    return side * (p1 / p0 - 1.0)


def _eligible(closes, i, lookback):
    """Names with a close now AND `lookback` bars ago (so the signal exists)."""
    out = []
    for s, ser in closes.items():
        if i - lookback >= 0 and ser[i] and ser[i - lookback]:
            out.append(s)
    return out


def xsect(closes, days, lookback, hold, k, reverse, lag=0):
    """Cross-sectional rank on trailing `lookback` return.

    reverse=False -> MOMENTUM  (long the top k, short the bottom k)
    reverse=True  -> REVERSAL  (long the bottom k, short the top k)
    Rebalance every `hold` bars: holds are non-overlapping by construction.

    `lag` is the EXECUTION-LAG control and it is load-bearing for the reversal
    arm.  At lag=0 the rule ranks on close[i] and enters at close[i] -- the
    SAME print.  On a book doing $0.5-2M/day that print carries bid-ask bounce
    and thin-book noise, so "the biggest 5d loser" partly means "the name whose
    last print landed low", and the next bar mechanically un-bounces.  That is
    microstructure, not edge, and it is not buyable: you cannot fill at the low
    print you just used to select the name.  lag=1 enters at the NEXT close.
    An edge that dies at lag=1 was never there ((ne): two calibrating
    conventions with opposite verdicts ==> the intrabar edge is REFUTED).
    """
    trades = []
    n = len(days)
    for i in range(lookback, n - hold - lag, hold):
        elig = _eligible(closes, i, lookback)
        if len(elig) < MIN_ELIGIBLE:
            continue
        scored = sorted(
            ((closes[s][i] / closes[s][i - lookback] - 1.0, s) for s in elig),
            reverse=True)
        winners = [s for _, s in scored[:k]]
        losers = [s for _, s in scored[-k:]]
        longs, shorts = (losers, winners) if reverse else (winners, losers)
        e = i + lag
        for s in longs:
            r = _ret(closes, s, e, e + hold, +1)
            if r is not None:
                trades.append(dict(sym=s, side=+1, entry_i=e,
                                   exit_i=e + hold, ret=r))
        for s in shorts:
            r = _ret(closes, s, e, e + hold, -1)
            if r is not None:
                trades.append(dict(sym=s, side=-1, entry_i=e,
                                   exit_i=e + hold, ret=r))
    return trades


def ts_trend(closes, days, sma_n, hold, lag=0):
    """Per name: long while close > SMA(sma_n), short while below.

    Evaluated as non-overlapping `hold`-bar holds so each name's observations
    are disjoint -- the same rule as an always-in trend book, sampled in a way
    that does not manufacture `n`.
    """
    trades = []
    n = len(days)
    for s, ser in closes.items():
        for i in range(sma_n, n - hold - lag, hold):
            win = [ser[j] for j in range(i - sma_n + 1, i + 1) if ser[j]]
            if len(win) < sma_n or not ser[i]:
                continue
            side = +1 if ser[i] > _mean(win) else -1
            e = i + lag
            r = _ret(closes, s, e, e + hold, side)
            if r is not None:
                trades.append(dict(sym=s, side=side, entry_i=e,
                                   exit_i=e + hold, ret=r))
    return trades


def charge_slip(trades, bps_per_side):
    """Round-trip slippage on a THIN book, charged in return space.

    Lighter is zero-FEE (measured), which is not the same as zero-COST: (qq)
    measured the fleet's own fills at a mean 17.49bps and p90 398bps below
    $0.1M/day.  Every name here clears $0.5M so the tier is kinder, but a
    5-day reversal on a $0.7M book pays the spread twice and a result that
    only survives at zero cost is not a result.
    """
    c = 2.0 * bps_per_side / 1e4
    return [dict(t, ret=t["ret"] - c) for t in trades]


# ===================================================================== nulls
def null_timing(trades, closes, days, hold, draws=NDRAWS, seed=7):
    """Same names, same sides, same hold; ENTRY DATES SHUFFLED.

    Asks whether WHEN the rule enters carries information.  A rule that only
    harvests a name's own drift passes nothing here.
    """
    rnd = random.Random(seed)
    obs = _mean([t["ret"] for t in trades])
    valid = {}
    for s, ser in closes.items():
        valid[s] = [i for i in range(len(days) - hold)
                    if ser[i] and ser[i + hold]]
    hits = 0
    for _ in range(draws):
        acc = []
        for tr in trades:
            v = valid.get(tr["sym"]) or []
            if not v:
                continue
            i = rnd.choice(v)
            r = _ret(closes, tr["sym"], i, i + hold, tr["side"])
            if r is not None:
                acc.append(r)
        if acc and _mean(acc) >= obs:
            hits += 1
    return hits / draws


def null_selection(trades, closes, days, lookback, hold, k,
                   draws=NDRAWS, seed=11):
    """Same dates, same long/short counts; NAMES DRAWN AT RANDOM.

    The pointed null for a RANKING rule: it holds the calendar and the net
    exposure fixed and destroys only the ranking.  A cross-sectional book can
    beat the timing null on beta alone and still fail this one.
    """
    rnd = random.Random(seed)
    obs = _mean([t["ret"] for t in trades])
    periods = defaultdict(lambda: [0, 0])
    for tr in trades:
        periods[tr["entry_i"]][0 if tr["side"] > 0 else 1] += 1
    hits = 0
    for _ in range(draws):
        acc = []
        for i, (nl, ns) in periods.items():
            elig = _eligible(closes, i, lookback)
            if len(elig) < nl + ns:
                continue
            pick = rnd.sample(elig, nl + ns)
            for s in pick[:nl]:
                r = _ret(closes, s, i, i + hold, +1)
                if r is not None:
                    acc.append(r)
            for s in pick[nl:]:
                r = _ret(closes, s, i, i + hold, -1)
                if r is not None:
                    acc.append(r)
        if acc and _mean(acc) >= obs:
            hits += 1
    return hits / draws


# ==================================================================== report
def grade(name, trades, closes, days, hold, lookback=None, k=None,
          frozen_entry=None):
    if len(trades) < 5:
        print(f"\n--- {name}: only {len(trades)} trades -- NOT GRADEABLE")
        return None
    rets = [t["ret"] for t in trades]
    mean = _mean(rets)
    bc_t, n_coins = by_coin_t(trades)
    bp_t, n_per, _ = by_period_t(trades)
    pooled = _t(rets)
    c1, c3, cdef = concentration(trades)
    h1, n1, h2, n2 = halves(trades)
    s_d, n_days = daily_sharpe(trades, days, closes)
    dtg = days_to_gate(s_d)
    p_time = null_timing(trades, closes, days, hold)
    p_sel = (null_selection(trades, closes, days, lookback, hold, k)
             if lookback is not None and k is not None else float("nan"))

    print(f"\n--- {name}")
    print(f"    n trades            {len(trades)}  "
          f"({n_coins} coins w/ >={MIN_TRADES_PER_COIN} trades, "
          f"{n_per} non-overlapping periods)")
    print(f"    mean %/trade        {100*mean:+.3f}%")
    print(f"    t BY COIN           {bc_t:+.2f}   <- clusters on the name")
    print(f"    t BY PERIOD         {bp_t:+.2f}   <- clusters on the period")
    print(f"    t pooled            {pooled:+.2f}   "
          f"(DIAGNOSTIC ONLY -- never the verdict)")
    print(f"    random-null P(time) {p_time:.3f}   "
          f"(P(random entry dates >= observed))")
    if p_sel == p_sel:
        print(f"    random-null P(sel)  {p_sel:.3f}   "
              f"(P(random name choice >= observed))")
    if cdef:
        print(f"    concentration       top1 {100*c1:.1f}%  top3 {100*c3:.1f}%"
              f"{'   <- UNDECIDABLE BY TAIL' if c3 > 0.5 else ''}")
    else:
        print("    concentration       n/a (total P&L <= 0)")
    print(f"    halves              h1 {100*h1:+.3f}% (n={n1})   "
          f"h2 {100*h2:+.3f}% (n={n2})"
          f"{'   SAME SIGN' if h1*h2 > 0 else '   OPPOSITE SIGNS'}")
    print(f"    daily Sharpe S_d    {s_d:+.4f}  over {n_days} calendar days")
    print(f"    days-to-gate        "
          f"{'INF' if dtg == float('inf') else f'{dtg:,.0f}'} calendar days"
          f"{'   <- STUDY, NOT A BOOK' if dtg > 60 else ''}")
    if frozen_entry is not None:
        print(f"    frozen-mark entries {100*frozen_entry:.1f}% of trades "
              f"entered on a bar whose close == the previous close")
    return dict(name=name, n=len(trades), mean=mean, bc_t=bc_t, bp_t=bp_t,
                pooled=pooled, p_time=p_time, p_sel=p_sel, c1=c1, c3=c3,
                cdef=cdef, h1=h1, h2=h2, s_d=s_d, dtg=dtg,
                n_coins=n_coins, n_per=n_per)


def frozen_entry_frac(trades, closes):
    tot = fro = 0
    for tr in trades:
        i, s = tr["entry_i"], tr["sym"]
        if i > 0 and closes[s][i] and closes[s][i - 1]:
            tot += 1
            if closes[s][i] == closes[s][i - 1]:
                fro += 1
    return fro / tot if tot else float("nan")


def verdict(res):
    """The pre-declared bar.  Every clause must pass."""
    if res is None:
        return False, ["not gradeable"]
    fails = []
    if not (res["bc_t"] >= 2.0):
        fails.append(f"by-coin t {res['bc_t']:+.2f} < 2.0")
    if not (res["bp_t"] >= 2.0):
        fails.append(f"by-period t {res['bp_t']:+.2f} < 2.0")
    if not (res["p_time"] <= 0.05):
        fails.append(f"timing-null P {res['p_time']:.3f} > 0.05")
    if res["p_sel"] == res["p_sel"] and not (res["p_sel"] <= 0.05):
        fails.append(f"selection-null P {res['p_sel']:.3f} > 0.05")
    if not res["cdef"]:
        fails.append("concentration undefined (total P&L <= 0)")
    elif res["c3"] >= 0.5:
        fails.append(f"top-3 concentration {100*res['c3']:.0f}% >= 50%")
    if not (res["h1"] * res["h2"] > 0):
        fails.append("halves disagree in sign")
    if not (res["dtg"] <= 60):
        d = res["dtg"]
        shown = "INF" if d == float("inf") else f"{d:,.0f}"
        fails.append(f"days-to-gate {shown} > 60")
    return (not fails), fails


# ================================================================ deep dive
def deep_dive(name, trades, closes, days, lookback, hold, k, seed=23):
    """Stress the ONE candidate that looked like something.

    Exists because this run produced a specific disagreement worth resolving:
    the random nulls read P=0.010 while the CLUSTERED t reads ~1.4.  Both
    cannot be describing the same uncertainty, and the reason is structural --
    the TIMING null draws each trade's entry date independently, which DESTROYS
    the within-period cross-sectional correlation the observed statistic
    carries.  A null built that way is too TIGHT, so its P is anti-conservative
    against a portfolio whose names move together.  The period bootstrap below
    resamples WHOLE PERIODS and so keeps that correlation; it is the number to
    believe, and it should land near the by-period t rather than near the null.
    """
    rnd = random.Random(seed)
    print(f"\n=== DEEP DIVE: {name} ===")

    _, _, per = by_period_t(trades)
    n_per = len(per)

    # -- period bootstrap: resample WHOLE periods, so within-period
    #    correlation survives the resample (unlike either random null).
    means = []
    for _ in range(4000):
        s = [per[rnd.randrange(n_per)] for _ in range(n_per)]
        means.append(_mean(s))
    means.sort()
    lo = means[int(0.025 * len(means))]
    hi = means[int(0.975 * len(means))]
    p_le0 = sum(1 for m in means if m <= 0) / len(means)
    print(f"  period bootstrap ({n_per} periods, 4000 draws)")
    print(f"    95% CI on mean %/period  [{100*lo:+.3f}%, {100*hi:+.3f}%]")
    print(f"    P(mean <= 0)             {p_le0:.3f}"
          f"{'   <- CI CONTAINS ZERO' if lo <= 0 else ''}")

    # -- leave-one-COIN-out: is this one name?
    coins = sorted({t["sym"] for t in trades})
    jl = []
    for c in coins:
        sub = [t for t in trades if t["sym"] != c]
        tt, _, _ = by_period_t(sub)
        jl.append((tt, c, _mean([t["ret"] for t in sub])))
    jl.sort()
    print(f"  leave-one-COIN-out by-period t over {len(coins)} names: "
          f"{jl[0][0]:+.2f} .. {jl[-1][0]:+.2f}")
    print(f"    worst (drop {jl[0][1]}): t {jl[0][0]:+.2f}, "
          f"mean {100*jl[0][2]:+.3f}%")

    # -- leave-one-PERIOD-out: is this one week?
    jp = []
    for i in range(n_per):
        sub = per[:i] + per[i + 1:]
        jp.append((_t(sub), i, _mean(sub)))
    jp.sort()
    print(f"  leave-one-PERIOD-out t: {jp[0][0]:+.2f} .. {jp[-1][0]:+.2f}")
    print(f"    dropping the single best period -> t {jp[0][0]:+.2f}, "
          f"mean/period {100*jp[0][2]:+.3f}%")

    # -- where in time does the P&L live?
    bymo = defaultdict(list)
    for t in trades:
        bymo[_d(days[t["entry_i"]]).strftime("%Y-%m")].append(t["ret"])
    print("  by calendar month of ENTRY:")
    for mo in sorted(bymo):
        v = bymo[mo]
        print(f"    {mo}  n={len(v):4d}  mean {100*_mean(v):+7.3f}%  "
              f"sum {100*sum(v):+8.2f}pp")

    # -- top-k trades, named
    top = sorted(trades, key=lambda t: -t["ret"])[:5]
    print("  top 5 trades:")
    for t in top:
        print(f"    {t['sym']:12s} {'LONG ' if t['side']>0 else 'SHORT'} "
              f"{_d(days[t['entry_i']]):%Y-%m-%d} -> "
              f"{_d(days[t['exit_i']]):%Y-%m-%d}  {100*t['ret']:+7.2f}%")


# ==================================================================== sweep
def sweep(closes, days):
    """SENSITIVITY, NOT A RESULT.

    A grid's best cell is an ARTIFACT until it survives the same nulls the
    headline candidates faced, and this grid applies no multiplicity control.
    Printed so a future session can see the SHAPE of the surface (is the
    headline cell a plateau or a spike?) and to catch a grid edge.
    """
    print("\n=== SENSITIVITY SWEEP (not a result -- no multiplicity control) ===")
    lbs, holds, ks = [10, 20, 40], [3, 5, 10], [2, 3, 5]
    rows = []
    for lb in lbs:
        for h in holds:
            for k in ks:
                tr = xsect(closes, days, lb, h, k, reverse=False)
                if len(tr) < 20:
                    continue
                bp, _, _ = by_period_t(tr)
                bc, _ = by_coin_t(tr)
                rows.append((bp, bc, _mean([t["ret"] for t in tr]),
                             len(tr), lb, h, k))
    rows.sort(reverse=True)
    print(f"  {'by-per t':>9s} {'by-coin t':>10s} {'mean%':>8s} {'n':>5s}  "
          f"lookback hold topk")
    for r in rows[:6]:
        print(f"  {r[0]:+9.2f} {r[1]:+10.2f} {100*r[2]:+7.3f}% {r[3]:5d}  "
              f"{r[4]:8d} {r[5]:4d} {r[6]:4d}")
    if rows:
        _, _, _, _, lb, h, k = rows[0]
        edges = []
        if lb in (lbs[0], lbs[-1]):
            edges.append(f"lookback={lb} at grid edge")
        if h in (holds[0], holds[-1]):
            edges.append(f"hold={h} at grid edge")
        if k in (ks[0], ks[-1]):
            edges.append(f"topk={k} at grid edge")
        if edges:
            print(f"  BEST CELL IS GRID-EDGE -> report as UNBOUNDED, never as "
                  f"a value: {'; '.join(edges)}")
    return rows


# ====================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--weekday-only", action="store_true",
                    help="restrict entries to non-frozen bars (the stale-"
                         "reference control)")
    a = ap.parse_args()

    print("STUDY: trend/momentum on Lighter's UNCLAIMED non-crypto markets")
    print(f"       {len(UNIVERSE)} names, daily bars, window cap {WINDOW_D}d")
    print(f"       run {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z")

    ok, tk, mk, nact = _sse.verify_zero_fee()
    print(f"\nvenue fees MEASURED: taker {tk} maker {mk} over {nact} active "
          f"books -> {'zero-fee, no fee term' if ok else 'NOT ZERO -- fees matter'}")

    panel = build_panel(force=a.refetch)
    panel_report(panel)

    days, closes = align(panel, min_bars=SMA_N + 2 * HOLD_D)
    print(f"\naligned: {len(closes)} names carry >= {SMA_N + 2*HOLD_D} bars; "
          f"calendar {len(days)} days "
          f"({_d(days[0]):%Y-%m-%d} -> {_d(days[-1]):%Y-%m-%d})")
    dropped = [s for s in UNIVERSE if s not in closes]
    if dropped:
        print(f"dropped (too short to carry a {SMA_N}d SMA): "
              f"{', '.join(dropped)}")

    results = []

    tr = xsect(closes, days, MOM_LOOKBACK, HOLD_D, TOP_K, reverse=False)
    results.append(("1. cross-sectional MOMENTUM "
                    f"({MOM_LOOKBACK}d rank, long top{TOP_K}/short bot{TOP_K}, "
                    f"{HOLD_D}d hold)",
                    grade("1. CROSS-SECTIONAL MOMENTUM", tr, closes, days,
                          HOLD_D, MOM_LOOKBACK, TOP_K,
                          frozen_entry_frac(tr, closes))))

    tr2 = ts_trend(closes, days, SMA_N, HOLD_D)
    results.append((f"2. time-series TREND ({SMA_N}d SMA, {HOLD_D}d hold)",
                    grade("2. TIME-SERIES TREND", tr2, closes, days, HOLD_D,
                          frozen_entry=frozen_entry_frac(tr2, closes))))

    tr3 = xsect(closes, days, REV_LOOKBACK, HOLD_D, TOP_K, reverse=True)
    results.append(("3. short-horizon REVERSAL "
                    f"({REV_LOOKBACK}d rank, long bot{TOP_K}/short top{TOP_K}, "
                    f"{HOLD_D}d hold)",
                    grade("3. SHORT-HORIZON REVERSAL", tr3, closes, days,
                          HOLD_D, REV_LOOKBACK, TOP_K,
                          frozen_entry_frac(tr3, closes))))

    print("\n=== VERDICT (pre-declared bar: by-coin t>=2 AND by-period t>=2 "
          "AND both nulls P<=0.05\n    AND top-3 concentration <50% AND both "
          "halves same sign AND days-to-gate<=60) ===")
    any_pass = False
    for label, res in results:
        p, fails = verdict(res)
        any_pass = any_pass or p
        print(f"\n  {label}")
        print(f"    -> {'CLEARS' if p else 'REFUSED'}")
        for f in fails:
            print(f"       - {f}")
    if not any_pass:
        print("\n  NOTHING CLEARS. A refusal with numbers is the result.")

    deep_dive("3. SHORT-HORIZON REVERSAL", tr3, closes, days,
              REV_LOOKBACK, HOLD_D, TOP_K)

    # ---- EXECUTION-LAG CONTROL.  The decisive test for the reversal arm.
    print("\n=== EXECUTION-LAG CONTROL (lag0 = rank and enter on the SAME "
          "close) ===")
    print("    A reversal that selects on close[i] and fills at close[i] can "
          "be harvesting\n    bid-ask bounce on a $0.5-2M/day book -- an "
          "unbuyable print, not an edge.\n    lag1 enters at the NEXT close. "
          "Opposite verdicts ==> the edge is REFUTED ((ne)).")
    print(f"\n  {'candidate':24s} {'lag':>3s} {'n':>5s} {'mean%':>9s} "
          f"{'by-coin t':>10s} {'by-per t':>9s}")
    for nm, fn in (
        ("1. x-sect MOMENTUM",
         lambda L: xsect(closes, days, MOM_LOOKBACK, HOLD_D, TOP_K, False, L)),
        ("2. ts TREND",
         lambda L: ts_trend(closes, days, SMA_N, HOLD_D, L)),
        ("3. x-sect REVERSAL",
         lambda L: xsect(closes, days, REV_LOOKBACK, HOLD_D, TOP_K, True, L)),
    ):
        for L in (0, 1):
            t_ = fn(L)
            if len(t_) < 5:
                continue
            bc, _ = by_coin_t(t_)
            bp, _, _ = by_period_t(t_)
            print(f"  {nm:24s} {L:3d} {len(t_):5d} "
                  f"{100*_mean([x['ret'] for x in t_]):+8.3f}% "
                  f"{bc:+10.2f} {bp:+9.2f}")

    # ---- COST CONTROL on the only arm with a positive mean.
    print("\n=== COST CONTROL: reversal at lag1, with round-trip slippage ===")
    r_lag1 = xsect(closes, days, REV_LOOKBACK, HOLD_D, TOP_K, True, 1)
    for bps in (0, 10, 25, 50):
        cc = charge_slip(r_lag1, bps)
        bc, _ = by_coin_t(cc)
        bp, _, _ = by_period_t(cc)
        print(f"  {bps:3d} bps/side -> mean "
              f"{100*_mean([x['ret'] for x in cc]):+7.3f}%  "
              f"by-coin t {bc:+.2f}  by-period t {bp:+.2f}")

    # ---- THE DELIVERABLE TABLE.
    print("\n=== SUMMARY TABLE ===")
    print(f"  {'candidate':22s} {'lag':>3s} {'n':>4s} {'mean%':>8s} "
          f"{'bycoin_t':>8s} {'byper_t':>8s} {'P_time':>7s} {'P_sel':>6s} "
          f"{'top3':>6s} {'h1%':>7s} {'h2%':>7s} {'S_d':>7s} {'d2gate':>8s}")
    specs = (
        ("1. xsect MOMENTUM", MOM_LOOKBACK, TOP_K,
         lambda L: xsect(closes, days, MOM_LOOKBACK, HOLD_D, TOP_K, False, L)),
        ("2. ts TREND", None, None,
         lambda L: ts_trend(closes, days, SMA_N, HOLD_D, L)),
        ("3. xsect REVERSAL", REV_LOOKBACK, TOP_K,
         lambda L: xsect(closes, days, REV_LOOKBACK, HOLD_D, TOP_K, True, L)),
    )
    for nm, lb, kk, fn in specs:
        for L in (0, 1):
            t_ = fn(L)
            if len(t_) < 5:
                continue
            bc, _ = by_coin_t(t_)
            bp, _, _ = by_period_t(t_)
            _, c3, cd = concentration(t_)
            h1, _, h2, _ = halves(t_)
            sd_, _ = daily_sharpe(t_, days, closes)
            dtg = days_to_gate(sd_)
            pt = null_timing(t_, closes, days, HOLD_D)
            ps = (null_selection(t_, closes, days, lb, HOLD_D, kk)
                  if lb else float("nan"))
            ps_s = f"{ps:.3f}" if ps == ps else "n/a"
            c3_s = f"{100*c3:.0f}%" if cd else "n/a"
            dtg_s = "INF" if dtg == float("inf") else f"{dtg:,.0f}"
            print(f"  {nm:22s} {L:3d} {len(t_):4d} "
                  f"{100*_mean([x['ret'] for x in t_]):+7.3f}% "
                  f"{bc:+8.2f} {bp:+8.2f} {pt:7.3f} {ps_s:>6s} "
                  f"{c3_s:>6s} {100*h1:+6.2f}% {100*h2:+6.2f}% "
                  f"{sd_:+7.4f} {dtg_s:>8s}")

    sweep(closes, days)

    print("\n=== STALE-REFERENCE CONTROL: entries on NON-FROZEN bars only ===")
    print("    (a rule whose result lives on stale weekend marks is measuring "
          "a closed\n     underlying, not an edge -- the (lk)/I7 signature)")
    for nm, t_all, lb, kk in (("1. x-sect MOMENTUM", tr, MOM_LOOKBACK, TOP_K),
                              ("2. ts TREND", tr2, None, None),
                              ("3. x-sect REVERSAL", tr3, REV_LOOKBACK, TOP_K)):
        live = [t for t in t_all
                if t["entry_i"] > 0 and closes[t["sym"]][t["entry_i"] - 1]
                and closes[t["sym"]][t["entry_i"]]
                != closes[t["sym"]][t["entry_i"] - 1]]
        if len(live) < 5:
            print(f"  {nm:22s} only {len(live)} non-frozen entries")
            continue
        bc, _ = by_coin_t(live)
        bp, _, _ = by_period_t(live)
        print(f"  {nm:22s} n={len(live):4d}  mean "
              f"{100*_mean([x['ret'] for x in live]):+.3f}%  "
              f"by-coin t {bc:+.2f}  by-period t {bp:+.2f}")


if __name__ == "__main__":
    main()
