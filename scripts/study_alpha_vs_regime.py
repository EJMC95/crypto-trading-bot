#!/usr/bin/env python3
"""ALPHA vs REGIME — the missing instrument for CLAUDE.md item 18.

THE PROBLEM item 18 STATES BUT NEVER MEASURES. Lighter's whole tape is one
falling-BTC regime, so "a DIRECTIONAL short passes both halves BY CONSTRUCTION
— the bar is satisfied by the drift, not the edge". The repo has carried that
caveat as an ASSERTION since 21-Jul and gated real decisions on it, but nothing
in the tree actually separates the two. This does.

THE TEST. For every closed trade, subtract the MEDIAN return of taking the same
DIRECTION in every liquid Lighter book over the SAME window. What remains is
excess return over the regime. Then:

    vs-market t collapses toward 0   ->  the "edge" IS the drift
    vs-market t holds or RISES       ->  genuine skill, regime-independent

MEASURED 2026-07-29, and it discriminates in both directions on real ledgers:

    inverted long-dip        raw +1.082% t=+2.48  ->  vs-market +0.098% t=+0.14
    short-divergence (era)   raw +2.122% t=+2.79  ->  vs-market +2.086% t=+3.01

The first is the whole falling market wearing a strategy's name — it was a
serious candidate on its raw number and this is what killed it. The second is
the live Taker's actual policy, and subtracting the drift makes it STRONGER,
which is the signature of real cross-sectional selection.

WHY THE BENCHMARK IS THE MEDIAN, not the mean: a handful of 1000-scaled meme
books move tens of percent and would otherwise set the bar by themselves.

WHY IT IS DIRECTION-MATCHED: benchmarking a short against a long-only market
return would credit the strategy with the entire drift instead of removing it.

HONEST LIMITS, because this instrument can mislead too:
  - It prices DIRECTION and TIMING, not sizing, fees beyond the flat round trip,
    funding, or fills. A book can beat the benchmark and still lose money.
  - The benchmark uses the same marks the strategy traded on, so shared mark
    error cancels — that is a feature for direction, a blind spot for execution.
  - n is n. A t on 10 trades is a t on 10 trades whatever you subtract.

    python3 scripts/study_alpha_vs_regime.py                # all taker lenses
    python3 scripts/study_alpha_vs_regime.py --bot <name>   # one book
    python3 scripts/study_alpha_vs_regime.py --selftest     # offline fixtures
"""
import argparse
import bisect
import json
import math
import os
import statistics
import sys
import urllib.request
from datetime import datetime

DASH = os.environ.get(
    "PNL_DASHBOARD_URL",
    "https://pnl-dashboard-production-858c.up.railway.app")
FEE_ROUND_TRIP = float(os.environ.get("ALPHA_FEE_RT", "0.0008"))   # 4bps each way
MIN_BOOKS = 20      # a benchmark on fewer quoted books is not a market
MIN_N = 3


def _t(xs):
    """Sample-stdev t (ddof=1). Population stdev inflates every t at small n —
    that error is recorded in CHANGELOG (fs)."""
    n = len(xs)
    if n < 2:
        return 0.0
    sd = statistics.stdev(xs)
    return (statistics.mean(xs) / (sd / math.sqrt(n))) if sd else 0.0


def benchmark(marks_at_open, marks_at_close, is_short, fee=FEE_ROUND_TRIP,
              min_books=MIN_BOOKS):
    """Median same-direction return across every book quoted at BOTH ends.
    None when the cross-section is too thin to be a market. Pure — selftested."""
    sign = -1.0 if is_short else 1.0
    rets = [sign * (marks_at_close[k] / marks_at_open[k] - 1.0) - fee
            for k in marks_at_open
            if k in marks_at_close and marks_at_open[k] and marks_at_close[k]]
    if len(rets) < min_books:
        return None
    return statistics.median(rets)


def grade(raw, excess):
    """(verdict, raw_t, excess_t). ALPHA only when the excess itself clears the
    fleet's t>=2.0 bar — beating the benchmark on the point estimate is not
    enough, that is how the dip candidate nearly survived."""
    rt, et = _t(raw), _t(excess)
    if len(excess) < MIN_N:
        return "insufficient", rt, et
    if et >= 2.0:
        return "ALPHA", rt, et
    if et <= -2.0:
        return "NEGATIVE-ALPHA", rt, et
    return "no alpha (regime or noise)", rt, et


def _load_tape(path):
    import pickle
    with open(path, "rb") as fh:
        tape = pickle.load(fh)
    return ([dt for dt, _ in tape],
            [(dt, (p.get("marks") or {})) for dt, p in tape])


def _iso(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bot", help="grade one book (substring match)")
    ap.add_argument("--tape", default=os.environ.get("ALPHA_TAPE", ""),
                    help="pickled [(datetime, payload)] scout tape with marks")
    ap.add_argument("--since", help="ISO date — grade only trades opened after")
    args = ap.parse_args(argv)
    if not args.tape or not os.path.isfile(args.tape):
        print("alpha_vs_regime: need --tape (a pickled scout tape with marks); "
              "the dashboard bus history can build one.", file=sys.stderr)
        return 2
    times, marks = _load_tape(args.tape)

    url = f"{DASH}/trades.json?source=paper&limit=5000"
    rows = (json.load(urllib.request.urlopen(url, timeout=90)).get("trades") or [])
    rows = [r for r in rows if r.get("closed_at") and r.get("pnl_pct") is not None]
    if args.bot:
        rows = [r for r in rows if args.bot in str(r.get("bot"))]
    if args.since:
        rows = [r for r in rows if str(r.get("opened_at", "")) >= args.since]

    groups = {}
    for r in rows:
        tag = str(r.get("reason") or "?").rsplit("_", 1)[0]
        groups.setdefault((str(r.get("bot")), tag), []).append(r)

    print(f"ALPHA vs REGIME — median same-direction market return subtracted "
          f"(fee {1e4*FEE_ROUND_TRIP:.0f}bps round trip)")
    print(f"{'book / lens':56s} {'n':>4s} {'raw%':>8s} {'t':>6s} "
          f"{'vs-mkt%':>8s} {'t':>6s}  verdict")
    out = []
    for (bot, tag), trs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        is_short = tag.startswith("short")
        raw, exc = [], []
        for t in trs:
            i0 = bisect.bisect_left(times, _iso(t["opened_at"]))
            i1 = bisect.bisect_left(times, _iso(t["closed_at"]))
            if not (0 <= i0 < len(marks) and 0 <= i1 < len(marks)):
                continue
            b = benchmark(marks[i0][1], marks[i1][1], is_short)
            if b is None:
                continue
            r = float(t["pnl_pct"])
            raw.append(r)
            exc.append(r - b)
        if len(exc) < MIN_N:
            continue
        verdict, rt, et = grade(raw, exc)
        print(f"{bot + ' / ' + tag:56s} {len(exc):4d} "
              f"{100*statistics.mean(raw):+8.3f} {rt:+6.2f} "
              f"{100*statistics.mean(exc):+8.3f} {et:+6.2f}  {verdict}")
        out.append((bot, tag, len(exc), et, verdict))
    alpha = [o for o in out if o[4] == "ALPHA"]
    print(f"\n{len(out)} graded; {len(alpha)} clear t>=2.0 on EXCESS over the regime.")
    print("A book that is positive raw but ~0 vs-market is collecting the drift — "
          "item 18, measured rather than asserted.")
    return 0


def _selftest():
    """Both directions must be caught: a pure-drift strategy and a real one.
    A detector that only ever says 'no alpha' is not a detector."""
    # a market where everything fell 5% -> shorting anything earns ~+5%
    o = {f"S{i}": 100.0 for i in range(30)}
    c = {f"S{i}": 95.0 for i in range(30)}
    b = benchmark(o, c, is_short=True)
    assert b is not None and abs(b - (0.05 - FEE_ROUND_TRIP)) < 1e-9, b
    # the same market benchmarked LONG must be symmetric-negative
    bl = benchmark(o, c, is_short=False)
    assert abs(bl - (-0.05 - FEE_ROUND_TRIP)) < 1e-9, bl
    # thin cross-section -> refuse rather than invent a market
    assert benchmark({"A": 1.0}, {"A": 0.9}, True) is None
    # median, not mean: one 500% meme book must not set the bar
    o2 = dict(o); c2 = dict(c); o2["MEME"] = 1.0; c2["MEME"] = 6.0
    assert abs(benchmark(o2, c2, True) - b) < 1e-9, "median must resist an outlier"

    # DRIFT: a strategy that tracks the market has a big RAW t and ~zero excess.
    # This is the dip case, and it is the whole reason this script exists.
    drift_raw = [0.05 + 0.0005 * (1 if i % 2 else -1) for i in range(12)]
    drift_exc = [0.0005 * (1 if i % 2 else -1) for i in range(12)]
    v, rt, et = grade(drift_raw, drift_exc)
    assert rt > 100, f"fixture must have a LARGE raw t, got {rt}"
    assert v.startswith("no alpha") and abs(et) < 1.0, (v, rt, et)
    # SKILL: consistent excess over the same market clears the bar
    skill_raw = [0.08] * 12
    skill_exc = [0.03 + (0.001 if i % 2 else -0.001) for i in range(12)]
    v2, _rt2, et2 = grade(skill_raw, skill_exc)
    assert v2 == "ALPHA" and et2 >= 2.0, (v2, et2)
    # NEGATIVE alpha is caught too — a book losing to its own regime
    v3, _r3, et3 = grade([0.01]*12, [-0.03 + (0.001 if i % 2 else -0.001)
                                     for i in range(12)])
    assert v3 == "NEGATIVE-ALPHA" and et3 <= -2.0, (v3, et3)
    # too few trades -> insufficient, never a verdict
    assert grade([0.1, 0.2], [0.1, 0.2])[0] == "insufficient"

    print("study_alpha_vs_regime selftest OK (direction-matched benchmark, "
          "median resists outliers, thin cross-section refused; drift, skill, "
          "negative-alpha and the high-raw-t/zero-excess trap all discriminated)")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main(sys.argv[1:]))
