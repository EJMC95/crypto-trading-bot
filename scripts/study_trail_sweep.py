#!/usr/bin/env python3
"""What does 🎫 the Ticket Taker's breakout TREND EXIT cost at each trail width?

THE FINDING THIS PRICES. `scripts/study_stop_reclaim.py` measured every
stop-shaped exit in the fleet against Lighter's own tape and a same-coin
placebo. One result dominates:

    long-breakoutup_trail   n=13   -$9.59   reclaim 77%  placebo 41%  (+36pp)
                                            regret +8.11%   held +3.81% @24h

i.e. the trail fires, and 24 hours later the position it closed is up **+3.81%**
on average in its own direction — not a best-case excursion, the actual close.
The same lens held to its clock (`long-breakoutup_hold`, n=27) earns
**+1.412%/trade**. Two independent lines say the same thing: the 6% give-back is
banking the pop and forfeiting the trend the exit was built to ride.

`BRK_TRAIL` is the knob, and until now it was a **bare env literal with no
registry entry** — the exit that binds the taker's best long lens could not be
reached by the growth rail at all (I18). Registering it without pricing it would
be the registered-but-inert failure in reverse, so this is the price.

METHOD. Entries are held CONSTANT — every position replays from its own real
entry price and timestamp, with its own recorded `max_hold_h`, against the
venue's hourly candles. Only the exit rule varies.

  * WITHIN-BAR ORDER IS PESSIMISTIC. Hourly bars cannot say whether the high or
    the low came first, so each bar is walked adverse-extreme FIRST: hard stop,
    then trail against the peak set by EARLIER bars, and only then is the peak
    updated with this bar's high. A trail can never be rescued by a peak made in
    the same bar as the give-back. This convention makes a WIDENING harder to
    justify, which is the direction it should be hard in.
  * THE CALIBRATION GATE IS THE POINT (gx). The shipped rule is replayed first
    and compared to the book's own realised mean on the same positions. Beyond
    tolerance, every candidate is WITHHELD — a harness that cannot reproduce
    what DID happen may not say what WOULD have.
  * THROUGHPUT IS REPORTED, NOT ASSUMED AWAY. A wider trail holds longer and the
    taker's slots are shared across lenses, so median hold is printed beside
    every candidate. A candidate that wins only by holding is named as such.

    python3 scripts/study_trail_sweep.py
    python3 scripts/study_trail_sweep.py --lens breakoutup --tol 0.4
    python3 scripts/study_trail_sweep.py --selftest
"""
import argparse
import json
import os
import statistics
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from study_stop_reclaim import (DASH, fetch_candles, market_ids,  # noqa: E402
                                ts)

TRAIL_GRID = [0.06, 0.08, 0.10, 0.12, 0.15, 0.20, None]   # None = trail OFF
#: The clock. `taker.max_hold_h` IS a registered lever (cage [24, 72], default
#: 48) — unlike the trail — so a finding here is enactable the day it lands.
#: The grid runs past the cage on purpose: a candidate outside the cage is a
#: cage finding, and hiding it inside the bounds is how a cage stops being
#: questioned.
HOLD_GRID = [24.0, 48.0, 72.0, 96.0, 120.0, 168.0]


def walk(candles, entry_ts, entry_px, sl, trail, max_hold_h, tp=None,
         peak_src="high"):
    """-> (ret, reason, hold_h) for ONE long position under a trend exit.

    Long-only: every lens that routes to the trend exit is a long arm
    (`BULL_LENS_SIDES` breakout/breakoutup), and inventing a short branch that
    nothing exercises is how an untested path ships.
    """
    times = sorted(t for t in candles if t > entry_ts)
    if not times:
        return None, None, None
    peak = 0.0
    for t in times:
        _o, hi, lo, cl = candles[t]
        hold = (t - entry_ts) / 3600.0
        low_ret = lo / entry_px - 1.0
        # 1 · hard stop, on the adverse extreme
        if sl is not None and low_ret <= sl:
            return sl, "sl", hold
        # 2 · trail, against a peak made in an EARLIER bar
        if trail is not None and peak > 0 and low_ret <= peak - trail:
            return peak - trail, "trail", hold
        # 3 · only now does this bar's extreme count toward the peak.
        #     `peak_src` is the ROBUSTNESS knob, not a tuning one: the real bot
        #     samples a mark each loop and cannot see an intrabar spike, so
        #     "close" is the conservative reading of what it could have known
        #     and "high" the generous one. A finding that survives both is
        #     independent of a convention this harness cannot resolve.
        peak = max(peak, (hi if peak_src == "high" else cl) / entry_px - 1.0)
        if tp is not None and peak >= tp:
            return tp, "tp", hold
        if hold >= max_hold_h:
            return cl / entry_px - 1.0, "hold", hold
    t = times[-1]
    return candles[t][3] / entry_px - 1.0, "eod", (t - entry_ts) / 3600.0


def replay(rows, candles_by_sym, sl, trail, tp=None, force_hold=None,
           peak_src="high"):
    out = []
    for r in rows:
        sym = str(r.get("pair") or "").split("/")[0].split("-")[0]
        cs = candles_by_sym.get(sym) or {}
        ent, t0 = r.get("entry_price"), ts(r.get("opened_at"))
        mh = float(force_hold if force_hold is not None
                   else (((r.get("extra") or {}).get("bars") or {}).get(
                       "max_hold_h") or 48.0))
        if not (cs and ent and t0) or ent <= 0:
            continue
        ret, why, hold = walk(cs, t0, float(ent), sl, trail, mh, tp,
                              peak_src=peak_src)
        if ret is None:
            continue
        out.append({"sym": sym, "ret": ret, "why": why, "hold": hold,
                    "actual": r.get("pnl_pct")})
    return out


def summarise(res):
    if not res:
        return None
    rets = [x["ret"] for x in res]
    return {"n": len(rets), "mean": statistics.fmean(rets),
            "total": sum(rets), "hold": statistics.median(
                [x["hold"] for x in res]),
            "win": sum(1 for r in rets if r > 0) / len(rets),
            "why": {w: sum(1 for x in res if x["why"] == w)
                    for w in sorted({x["why"] for x in res})}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", default="lighter-ticket-taker-lshadow")
    ap.add_argument("--lens", default="breakoutup")
    ap.add_argument("--sl", type=float, default=-0.07)
    ap.add_argument("--shipped-trail", type=float, default=0.06)
    ap.add_argument("--shipped-hold", type=float, default=48.0)
    ap.add_argument("--sweep", choices=("trail", "hold"), default="trail")
    ap.add_argument("--peak", choices=("high", "close", "both"), default="both")
    ap.add_argument("--jackknife", action="store_true",
                    help="also report leave-one-symbol-out worst case")
    ap.add_argument("--tol", type=float, default=0.5,
                    help="calibration tolerance, pp of mean per trade")
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    if a.ledger:
        rows = json.load(open(a.ledger))["trades"]
    else:
        with urllib.request.urlopen(
                f"{DASH}/trades.json?source=paper&limit=5000", timeout=180) as r:
            rows = json.loads(r.read().decode())["trades"]
    rows = [r for r in rows if r.get("bot") == a.bot
            and a.lens in str(r.get("reason") or "")
            and r.get("entry_price") and r.get("opened_at")]
    if not rows:
        print(f"no {a.lens} closes for {a.bot}", file=sys.stderr)
        return 1

    ids = market_ids()
    lo = min(ts(r["opened_at"]) for r in rows)
    hi = max(ts(r["closed_at"]) or ts(r["opened_at"]) for r in rows)
    candles, missing = {}, []
    for s in sorted({str(r["pair"]).split("/")[0].split("-")[0] for r in rows}):
        mid = ids.get(s)
        c = fetch_candles(mid, int(lo) - 3600, int(hi) + 96 * 3600) if mid else {}
        (candles.setdefault(s, c) if c else missing.append(s))
    print(f"{a.bot} / {a.lens}: {len(rows)} closes, "
          f"{len(candles)} symbols with candles"
          + (f", {len(missing)} without ({', '.join(missing[:8])})"
             if missing else ""))

    # ---- calibration: reproduce the SHIPPED rule before saying anything else
    cals = {}
    for cv in (("high", "close") if a.peak == "both" else (a.peak,)):
        b = replay(rows, candles, a.sl, a.shipped_trail, peak_src=cv)
        pr = [x for x in b if isinstance(x["actual"], (int, float))]
        if pr:
            cals[cv] = (statistics.fmean(x["ret"] for x in pr) * 100,
                        statistics.fmean(x["actual"] for x in pr) * 100,
                        len(pr))
    for cv, (rm, am, nn) in cals.items():
        print(f"calibration [{cv}-peak] n={nn}: replayed {rm:+.3f}%/trade vs "
              f"ledger {am:+.3f}%/trade -> drift {rm - am:+.3f}pp")
    base = replay(rows, candles, a.sl, a.shipped_trail,
                  peak_src=("high" if a.peak == "both" else a.peak))
    paired = [x for x in base if isinstance(x["actual"], (int, float))]
    if not paired:
        print("CALIBRATION WITHHELD: no paired actuals", file=sys.stderr)
        return 2
    rep_m = statistics.fmean(x["ret"] for x in paired) * 100
    act_m = statistics.fmean(x["actual"] for x in paired) * 100
    drift = rep_m - act_m
    print(f"\ncalibration on n={len(paired)}: replayed shipped rule "
          f"{rep_m:+.3f}%/trade vs ledger {act_m:+.3f}%/trade "
          f"→ drift {drift:+.3f}pp (tolerance ±{a.tol}pp)")
    ok = abs(drift) <= a.tol
    print("CALIBRATED — candidates below are reportable" if ok else
          "CALIBRATION FAILED — every candidate below is WITHHELD "
          "(a harness that cannot reproduce what DID happen may not say "
          "what WOULD have)")

    hold_mode = a.sweep == "hold"
    grid = HOLD_GRID if hold_mode else TRAIL_GRID
    shipped = a.shipped_hold if hold_mode else a.shipped_trail
    print(f"\n  {('max_hold' if hold_mode else 'trail'):>9}{'n':>5}"
          f"{'mean%':>9}{'total%':>9}{'win%':>7}{'medHold':>9}  exits")
    rows_out = []
    convs = ["high", "close"] if a.peak == "both" else [a.peak]
    for g in grid:
        per = {}
        for cv in convs:
            per[cv] = summarise(replay(
                rows, candles, a.sl, a.shipped_trail if hold_mode else g,
                force_hold=g if hold_mode else None, peak_src=cv))
        s = per[convs[0]]
        if not s:
            continue
        rows_out.append((g, s))
        if len(convs) > 1 and per["close"]:
            s = dict(s, alt=per["close"]["mean"])
        lab = (f"{g:.0f}h" if hold_mode
               else ("OFF" if g is None else f"{g * 100:.0f}%"))
        star = " <- shipped" if g == shipped else ""
        print(f"  {lab:>9}{s['n']:>5}{s['mean'] * 100:>9.3f}"
              f"{s['total'] * 100:>9.2f}{s['win'] * 100:>7.0f}"
              f"{s['hold']:>9.1f}  {s['why']}{star}"
              + (f"   [close-peak {s['alt'] * 100:+.3f}%]"
                 if s.get("alt") is not None else ""))
    if not ok:
        print("\n(candidates above are DIAGNOSTIC only — the verdict below is "
              "withheld)")
    if a.jackknife:
        syms = sorted({str(r["pair"]).split("/")[0].split("-")[0]
                       for r in rows})
        print(f"\n  leave-one-symbol-out (worst cell over {len(syms)} drops) "
              "— is the shape one coin?")
        for g in grid:
            worst = None
            for drop in syms:
                keep = [r for r in rows
                        if str(r["pair"]).split("/")[0].split("-")[0] != drop]
                st = summarise(replay(
                    keep, candles, a.sl, a.shipped_trail if hold_mode else g,
                    force_hold=g if hold_mode else None))
                if st and (worst is None or st["mean"] < worst[1]):
                    worst = (drop, st["mean"])
            if worst:
                lab = (f"{g:.0f}h" if hold_mode
                       else ("OFF" if g is None else f"{g * 100:.0f}%"))
                print(f"  {lab:>9}  worst {worst[1] * 100:+.3f}%/trade "
                      f"(without {worst[0]})")
    if not ok:
        return 2
    best = max(rows_out, key=lambda kv: kv[1]["mean"])
    ship = dict(rows_out).get(shipped)
    if best[0] == shipped:
        print("\nthe shipped trail is the grid optimum — no widening indicated")
    elif best[0] is None or best[0] >= max(t for t in grid if t):
        print(f"\nGRID EDGE at {best[0]}: reported UNBOUNDED, not as a value — "
              "widen the grid rather than shipping the edge")
    else:
        d = (best[1]["mean"] - ship["mean"]) * 100 if ship else None
        lab = (f"max_hold={best[0]:.0f}h" if hold_mode
               else f"trail={best[0] * 100:.0f}%")
        print(f"\ninterior optimum {lab}: "
              f"{best[1]['mean'] * 100:+.3f}%/trade vs shipped "
              f"{ship['mean'] * 100:+.3f}% ({d:+.3f}pp), median hold "
              f"{ship['hold']:.1f}h → {best[1]['hold']:.1f}h "
              "(shared slots — the hold is the throughput price)")
    return 0


def selftest():
    # a clean up-trend: price climbs 2%/bar for 20 bars then stalls flat.
    cs = {}
    px = 100.0
    for i in range(40):
        px = px * 1.02 if i < 20 else px
        cs[1_800_000_000 + i * 3600] = (px, px, px * 0.995, px)
    # a 6% trail can never fire on a 0.5%-per-bar give-back...
    ret, why, _h = walk(cs, 1_800_000_000, 100.0, -0.07, 0.06, 100.0)
    assert why == "eod", (ret, why)
    # ...but a 0.4% trail fires immediately, and BELOW the peak by construction
    ret2, why2, _ = walk(cs, 1_800_000_000, 100.0, -0.07, 0.004, 100.0)
    assert why2 == "trail" and ret2 < 1.02 ** 20 - 1, (ret2, why2)

    # the pessimistic within-bar rule: one bar that both peaks and craters must
    # NOT be allowed to trail off its own high.
    spike = {1_800_000_000 + 3600: (100.0, 130.0, 95.0, 96.0),
             1_800_000_000 + 7200: (96.0, 96.0, 94.0, 95.0)}
    r3, w3, _ = walk(spike, 1_800_000_000, 100.0, -0.50, 0.06, 100.0)
    assert w3 == "trail" and abs(r3 - 0.24) < 1e-9, (r3, w3)

    # the hard stop is checked BEFORE the trail, on the same adverse extreme
    crash = {1_800_000_000 + 3600: (100.0, 101.0, 50.0, 55.0)}
    r4, w4, _ = walk(crash, 1_800_000_000, 100.0, -0.07, 0.06, 100.0)
    assert w4 == "sl" and r4 == -0.07, (r4, w4)

    # max_hold exits at the CLOSE, not an extreme
    flat = {1_800_000_000 + i * 3600: (100.0, 108.0, 99.0, 101.0)
            for i in range(1, 6)}
    r5, w5, h5 = walk(flat, 1_800_000_000, 100.0, -0.50, None, 2.0)
    assert w5 == "hold" and abs(r5 - 0.01) < 1e-9 and h5 == 2.0, (r5, w5, h5)

    # trail OFF must never produce a trail exit
    assert walk(cs, 1_800_000_000, 100.0, -0.07, None, 100.0)[1] == "eod"

    # force_hold overrides the row's own recorded clock (the hold sweep's
    # whole mechanism — without it every candidate replays identically)
    row = {"pair": "X/USDC", "entry_price": 100.0, "pnl_pct": 0.0,
           "opened_at": "2027-01-15T08:00:00+00:00",
           "extra": {"bars": {"max_hold_h": 2.0}}}
    long_run = {1_800_000_000 + i * 3600: (100.0 + i, 100.0 + i, 99.0 + i,
                                           100.0 + i) for i in range(1, 30)}
    a1 = replay([row], {"X": long_run}, -0.50, None)
    a2 = replay([row], {"X": long_run}, -0.50, None, force_hold=20.0)
    assert a1 and a2 and a2[0]["ret"] > a1[0]["ret"], (a1, a2)
    assert a1[0]["hold"] == 2.0 and a2[0]["hold"] == 20.0, (a1, a2)
    assert a1[0]["why"] == a2[0]["why"] == "hold", (a1, a2)
    print("study_trail_sweep selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
