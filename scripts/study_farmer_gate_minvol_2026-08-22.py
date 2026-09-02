#!/usr/bin/env python3
"""study_farmer_gate_minvol_2026-08-22.py — 💸 the LIVE Funding Farmer's entry
gate, replayed for the first time on the population the book can actually trade.

WHY (2026-08-22). Eamon: *"fix farmers entry and exits as it's made poor
decisions, recently to be specific"*. The book turned over in August — live
July +$9.05 (mean +0.62%/trade) -> August **-$7.58** (mean -0.39%), with the
second half of August at **-1.53%/trade over 13 closes**; the shadow arm reads
Jul +$17.84 -> Aug **-$19.34**, Aug-b -2.18%/trade at t=-2.61.

THREE THINGS WERE MEASURED FIRST, and two of them refuse the obvious fixes.

1. THE FUNDING LEG IS A ROUNDING ERROR. Decomposing every close with recorded
   prices into price and residual: August live mean **-0.390% = price -0.408%
   + funding +0.018%**. Real settled accruals on live trades run $0.0015-$0.018
   on a $30 clip. At ENTER_APR 0.05 and the measured ~6h median hold the
   maximum collectable is 5% x 6/8760 = **0.0034%**. This is a directional
   short book with a rounding-error funding kicker, and nothing said so.

2. THE GATE SITS BELOW THE VENUE'S RESTING DEFAULT. Measured over 147,879
   hourly settled rows x 212 markets x 30d: **37.78% of all coin-hours sit at
   exactly 0.0012%/hr = 10.512% TRUE APR** (the resting default) and 36.76% at
   3.504% — **74.5% of the venue rests on two constants**. A 5% bar admits
   **55.24% of every coin-hour on the venue**. Reconstructing each live trade's
   entry APR from the venue's own settled tape: **77.2% of the live book's
   entries fired at EXACTLY 10.512%**, the idle rate. A book whose thesis is
   "extreme funding marks crowded positioning" takes 9 of 10 trades at or below
   the venue's do-nothing rate. `lighter_funding_bot.py` has said so in a
   comment since 17-Jul and the constant never moved.

3. THE FLIP-GRACE FIX ITS THREE SIBLINGS SHIP DOES NOT TRANSFER — REFUTED, with
   evidence. 🌾 carry, 🏦 Rich Dad and 🧮 Hull all added a flip grace (6h/6h/24h)
   on measured evidence; the Farmer has none (`flipped` fires the instant apr
   crosses zero). But on THIS book the young flips are the profitable ones:
   flips under 12h read **+0.19%/trade** (n=36 live, n=45 shadow) and the entire
   burn sits in flips held >12h (live n=11, -22.9 points). A grace would delay
   exactly the good ones. Same shape as I14: a fix graded at the wrong horizon
   inverts.

WHAT THIS SCRIPT EXISTS FOR — AND THE DEFECT IT FIXES IN THE INSTRUMENT.

`backtest_funding_lighter` selects its universe as the **top N markets by
volume**. The live bot selects by an **absolute floor**, `MIN_VOL = $10M/day`.
Measured on the venue 22-Aug: **only 11 of 212 active markets clear $10M**, the
25th-ranked market trades $2.59M, and markets 26-50 are ALL between $1.1M and
$2.5M. So **14 of the canonical top-25 and 39 of the top-50 sit below the live
book's own floor**, and every gate verdict this harness has printed — including
the table quoted at ENTER_APR in the live bot's source — was measured on a
population the live book mostly refuses.

That is not a quibble; it is the whole disagreement. Sweeping the gate at
universe 25 makes 0.40 the best value tested (+$14.95, both halves positive, at
the measured 0.13bps friction) and at universe 50 makes it -$10.95 while the
live 0.05 turns positive. **A knob whose sign depends on the universe is a coin
the tape cannot call** — this harness's own words, about a different knob.

So the fix is to replay the population the book trades. `vol24()` reconstructs
trailing 24h QUOTE volume per market per hour off the candle tape, which pages
back 438 days — the point-in-time volume `(ny)` recorded as "not
reconstructable" (true of the orderBookDetails snapshot, not of the tape).

THE CALIBRATION GATE IS SENIOR ((gx)). A harness that cannot reproduce what DID
happen may not say what WOULD have, so this refuses to recommend anything
unless the min-vol replay at the SHIPPED gate lands within tolerance of the
live book's own realised mean over the same window. Fail-CLOSED: no baseline,
no recommendation.

Read-only. Touches no bot, no lever, no ledger.

Usage:
  python3 scripts/study_farmer_gate_minvol_2026-08-22.py
  python3 scripts/study_farmer_gate_minvol_2026-08-22.py --days 250 --universe 60
  python3 scripts/study_farmer_gate_minvol_2026-08-22.py --selftest
"""
import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import backtest_funding_lighter as H            # noqa: E402

MIN_VOL = float(os.environ.get("FUNDING_MIN_VOL", "10e6"))
SWEEP = [0.05, 0.08, 0.12, 0.20, 0.30, 0.40, 0.60]
#: the live book's own realised mean %/trade, for the calibration gate. Read
#: from /trades.json, never typed in — see `--live-mean`.
CALIB_TOL_PP = 0.60      # percentage points of mean-per-trade


def coverage(mk, t0, t1, floor):
    """Census FIRST: how much of the tape clears the floor at all. `n=0` must
    never be byte-identical between "the gate is tight" and "no market in this
    universe was ever eligible" (I18)."""
    hrs = ok = unknown = 0
    syms = set()
    for sym, m in mk.items():
        for t in m["fund"]:
            if not (t0 <= t < t1):
                continue
            hrs += 1
            v = H.vol24(m, t)
            if v is None:
                unknown += 1
            elif v >= floor:
                ok += 1
                syms.add(sym)
    return {"coin_hours": hrs, "above_floor": ok, "unknown": unknown,
            "markets_seen_above": len(syms),
            "pct": (100.0 * ok / hrs) if hrs else 0.0}


# [2026-09-02] moved to the LOADER (backtest_funding_lighter.minvol_entry_ok)
# so every study reusing it gets the honest-population predicate from ONE
# owner — a second copy of a rule is a second rule ((hj)). Import by IDENTITY
# so this study's citations keep resolving and cannot drift from the owner.
minvol_entry_ok = H.minvol_entry_ok


def sweep(mk, t0, t1, floor=None):
    rows = []
    ok = None if floor is None else minvol_entry_ok(mk, floor)
    for g in SWEEP:
        half = t0 + (t1 - t0) // 2
        r = H.run(mk, g, t0, t1, entry_ok=ok)
        h1 = H.run(mk, g, t0, half, entry_ok=ok)
        h2 = H.run(mk, g, half, t1, entry_ok=ok)
        r["h1"], r["h2"] = h1["pnl"], h2["pnl"]
        r["mean_pct"] = (100.0 * r["pnl"] / (r["n"] * H.ORDER_USD)) if r["n"] else 0.0
        rows.append(r)
    return rows


def show(title, rows):
    print(f"\n{title}")
    print(f"  {'gate':>6} {'P&L $':>9} {'fund $':>8} {'price $':>9} {'n':>6} "
          f"{'win%':>6} {'mean%/t':>8} {'maxDD $':>9} {'h1':>8} {'h2':>8}  both")
    for r in rows:
        both = "YES" if (r["h1"] > 0 and r["h2"] > 0) else "no"
        print(f"  {r['enter']:6.2f} {r['pnl']:9.2f} {r['fund']:8.2f} "
              f"{r['price']:9.2f} {r['n']:6d} {r['win']:6.1f} "
              f"{r['mean_pct']:8.3f} {r['maxdd']:9.2f} {r['h1']:8.2f} "
              f"{r['h2']:8.2f}  {both}")


def exit_sweep(mk, t0, t1, floor, gate):
    """THE OTHER HALF OF THE ASK: the exits, on the same honest population.

    Eamon asked about "entry and exits". The knobs are module constants the
    harness mirrors from the bot (`MAX_HOLD_H` 72, `TAKE_PROFIT` 0.04,
    `HARD_STOP` 0.10), so they are swept by rebinding them on the harness and
    RESTORED after — a study may not leave a global moved for the next caller.

    The ledger motivates the hold sweep specifically: on the live book every
    exit family past ~12h loses (`short_max_hold` at 72h reads -3.10%/trade
    live and -1.81% shadow), while the take-profit family — the only
    100%-win-by-construction one — has a median hold of 18h."""
    ok = minvol_entry_ok(mk, floor)
    saved = (H.MAX_HOLD_H, H.TAKE_PROFIT, H.HARD_STOP)
    rows = []
    try:
        for label, mh, tp, sl in [
                ("SHIPPED  72h / tp 4% / sl 10%", 72, 0.04, 0.10),
                ("hold 48h", 48, 0.04, 0.10),
                ("hold 24h", 24, 0.04, 0.10),
                ("hold 12h", 12, 0.04, 0.10),
                ("hold  8h", 8, 0.04, 0.10),
                ("tp 2%", 72, 0.02, 0.10),
                ("tp 3%", 72, 0.03, 0.10),
                ("tp 6%", 72, 0.06, 0.10),
                ("sl 5%", 72, 0.04, 0.05),
                ("sl 7%", 72, 0.04, 0.07),
                ("sl 15%", 72, 0.04, 0.15),
                ("hold 24h + sl 5%", 24, 0.04, 0.05)]:
            H.MAX_HOLD_H, H.TAKE_PROFIT, H.HARD_STOP = mh, tp, sl
            half = t0 + (t1 - t0) // 2
            r = H.run(mk, gate, t0, t1, entry_ok=ok)
            r["h1"] = H.run(mk, gate, t0, half, entry_ok=ok)["pnl"]
            r["h2"] = H.run(mk, gate, half, t1, entry_ok=ok)["pnl"]
            r["label"] = label
            r["mean_pct"] = (100.0 * r["pnl"] / (r["n"] * H.ORDER_USD)) if r["n"] else 0.0
            rows.append(r)
    finally:
        H.MAX_HOLD_H, H.TAKE_PROFIT, H.HARD_STOP = saved
    return rows


def show_exits(title, rows):
    print(f"\n{title}")
    print(f"  {'variant':<30} {'P&L $':>9} {'n':>6} {'win%':>6} {'mean%/t':>8} "
          f"{'maxDD $':>9} {'medHold':>8} {'h1':>8} {'h2':>8}  both")
    base = rows[0]["pnl"] if rows else 0.0
    for r in rows:
        both = "YES" if (r["h1"] > 0 and r["h2"] > 0) else "no"
        d = "" if r is rows[0] else f"  ({r['pnl'] - base:+.2f})"
        print(f"  {r['label']:<30} {r['pnl']:9.2f} {r['n']:6d} {r['win']:6.1f} "
              f"{r['mean_pct']:8.3f} {r['maxdd']:9.2f} {r['hold_med']:8.1f} "
              f"{r['h1']:8.2f} {r['h2']:8.2f}  {both}{d}")


def conc_sweep(mk, t0, t1, floor, gate):
    """[(su)] THE CONCENTRATION CAP — the one costly thing (su) measured and did
    NOT refute.

    The live book holds BTC/ETH/SOL/XAU **all short** at N_eff 1.389 (crypto leg
    1.11, rho +0.851): one bet wearing four names. That is structural, not bad
    luck — positive funding is far more common than negative, so the book shorts
    the payer every time and ends up net-short crypto beta by construction.
    August is the bill: SOL -$2.69, BTC -$2.00, XAU -$1.97, ETH -$1.30, every
    leg losing in the same fortnight.

    The cap costs NO expectancy per trade — it turns away nothing the gate
    admitted, it declines the Nth copy of a bet already held (the (sr) logic at
    🙏 Avo, where the same reasoning was worth N_eff 1.18 -> 2.87 for free)."""
    ok = minvol_entry_ok(mk, floor)
    rows = []
    for cap in (None, 4, 3, 2, 1):
        half = t0 + (t1 - t0) // 2
        r = H.run(mk, gate, t0, t1, entry_ok=ok, max_same_side=cap)
        r["h1"] = H.run(mk, gate, t0, half, entry_ok=ok, max_same_side=cap)["pnl"]
        r["h2"] = H.run(mk, gate, half, t1, entry_ok=ok, max_same_side=cap)["pnl"]
        r["label"] = "SHIPPED (no cap)" if cap is None else f"max {cap} per side"
        r["mean_pct"] = (100.0 * r["pnl"] / (r["n"] * H.ORDER_USD)) if r["n"] else 0.0
        rows.append(r)
    return rows


def _selftest():
    """The harness's own hooks, driven — never a hand-written fixture ((hj))."""
    # vol24: sums the trailing 24 hourly bars, UNKNOWN below the coverage floor
    m = {"vol": {h * 3600: 1.0 for h in range(100)}}
    assert H.vol24(m, 50 * 3600) == 24.0, H.vol24(m, 50 * 3600)
    sparse = {"vol": {h * 3600: 1.0 for h in range(0, 100, 3)}}   # ~8 of 24
    assert H.vol24(sparse, 50 * 3600) is None, "a data gap must read UNKNOWN"
    assert H.vol24({"vol": {}}, 0) is None and H.vol24({}, 0) is None
    # the predicate refuses UNKNOWN rather than passing it
    mk = {"A": {"vol": {}}, "B": {"vol": {h * 3600: 1e6 for h in range(100)}}}
    ok = minvol_entry_ok(mk, 10e6)
    assert ok("A", 50 * 3600) is False, "unknown volume must REFUSE"
    assert ok("B", 50 * 3600) is True, "24 x 1e6 = 24e6 clears a 10e6 floor"
    assert minvol_entry_ok(mk, 30e6)("B", 50 * 3600) is False
    # fetch_candles keeps its ORIGINAL shape unless volume is asked for — the
    # seven importers that unpack it directly depend on this
    import inspect
    sig = inspect.signature(H.fetch_candles)
    assert sig.parameters["with_volume"].default is False, \
        "volume must be opt-in or seven callers bind a tuple to `cand`"
    src = inspect.getsource(H.fetch_candles)
    assert "if not with_volume:\n        return ohlc" in src
    # the cache schema gate exists, or a pre-volume cache answers silently
    assert H.CACHE_SCHEMA >= 2
    # the exit sweep rebinds harness globals — it must put them back, or every
    # later caller in the same process silently replays a different bot
    _before = (H.MAX_HOLD_H, H.TAKE_PROFIT, H.HARD_STOP)
    try:
        exit_sweep({}, 0, 1, 10e6, 0.05)
    except Exception:                      # empty tape is fine; the finally is the point
        pass
    assert (H.MAX_HOLD_H, H.TAKE_PROFIT, H.HARD_STOP) == _before, \
        "exit_sweep left a harness global moved"
    import inspect as _i
    _src = _i.getsource(H.run)
    assert "max_same_side=None" in _src, "the cap must default to OFF"
    assert 'q["short"] == _want_short' in _src, \
        "the cap must count SAME-DIRECTION holds, not all holds"
    assert 'd.get("schema") != CACHE_SCHEMA' in inspect.getsource(H.load)
    print("study_farmer_gate_minvol self-test: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=250)
    ap.add_argument("--universe", type=int, default=60)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--min-vol", type=float, default=MIN_VOL)
    ap.add_argument("--live-mean", type=float, default=None,
                    help="the live book's realised mean %%/trade over the same "
                         "window; the calibration gate is SKIPPED (and every "
                         "recommendation withheld) without it")
    ap.add_argument("--exits", action="store_true",
                    help="sweep the EXIT knobs at the shipped gate instead")
    ap.add_argument("--gate", type=float, default=0.05)
    ap.add_argument("--conc", action="store_true",
                    help="sweep the same-side concentration cap")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    mk = H.load(a.days, a.universe, a.refresh)
    t1 = int(time.time())
    t0 = t1 - a.days * 86400
    print(f"\n{len(mk)} markets | {a.days}d | clip ${H.ORDER_USD} x "
          f"{H.MAX_OPEN} slots | slip {H.SLIP*1e4:.2f}bps | "
          f"exit = enter x {H.EXIT_RATIO}")

    cov = coverage(mk, t0, t1, a.min_vol)
    print(f"\nMIN_VOL ${a.min_vol/1e6:.0f}M/day COVERAGE — the census first, so "
          f"a thin result is never mistaken for a tight gate:")
    print(f"  coin-hours in window      {cov['coin_hours']:>9,d}")
    print(f"  clearing the floor        {cov['above_floor']:>9,d}  "
          f"({cov['pct']:.2f}%)")
    print(f"  volume UNKNOWN (data gap) {cov['unknown']:>9,d}")
    print(f"  markets ever above floor  {cov['markets_seen_above']:>9,d} "
          f"of {len(mk)}")
    if cov["above_floor"] < 500:
        print("\n  ** REFUSING to sweep: fewer than 500 eligible coin-hours. "
              "Widen --universe or --days; a sweep on this is noise. **")
        return

    if a.conc:
        show_exits(f"SAME-SIDE CONCENTRATION CAP at gate {a.gate:.2f}, MIN_VOL "
                   f"${a.min_vol/1e6:.0f}M, {a.days}d — deltas vs SHIPPED",
                   conc_sweep(mk, t0, t1, a.min_vol, a.gate))
        return
    if a.exits:
        show_exits(f"EXIT KNOBS at the shipped gate {a.gate:.2f}, MIN_VOL "
                   f"${a.min_vol/1e6:.0f}M, {a.days}d — deltas vs SHIPPED",
                   exit_sweep(mk, t0, t1, a.min_vol, a.gate))
        return
    wide = sweep(mk, t0, t1, floor=None)
    show(f"WITHOUT the floor — the population this harness has always replayed "
         f"({len(mk)} markets by rank)", wide)
    tight = sweep(mk, t0, t1, floor=a.min_vol)
    show(f"WITH the live book's MIN_VOL ${a.min_vol/1e6:.0f}M — the population "
         f"it can actually trade", tight)

    live_row = [r for r in tight if abs(r["enter"] - 0.05) < 1e-9]
    print("\nCALIBRATION GATE ((gx)) — a harness that cannot reproduce what DID "
          "happen may not say what WOULD have:")
    if a.live_mean is None or not live_row:
        print("  NO BASELINE SUPPLIED -> every recommendation WITHHELD. Pass "
              "--live-mean <realised %/trade> read from /trades.json.")
        return
    gap = abs(live_row[0]["mean_pct"] - a.live_mean)
    print(f"  replayed mean at the shipped gate 0.05 : {live_row[0]['mean_pct']:+.3f}%/trade")
    print(f"  the live book's own realised mean      : {a.live_mean:+.3f}%/trade")
    print(f"  gap {gap:.3f}pp against a {CALIB_TOL_PP:.2f}pp tolerance -> "
          f"{'PASS' if gap <= CALIB_TOL_PP else 'FAIL'}")
    if gap > CALIB_TOL_PP:
        print("  ** RECOMMENDATIONS WITHHELD — the replay does not reproduce "
              "the book. Fix the harness before believing any row above. **")
        return
    best = max(tight, key=lambda r: r["pnl"])
    both = [r for r in tight if r["h1"] > 0 and r["h2"] > 0]
    print(f"\n  best by P&L: gate {best['enter']:.2f} (${best['pnl']:.2f}, "
          f"n={best['n']}, maxDD ${best['maxdd']:.2f})")
    names = ", ".join("%.2f" % r["enter"] for r in both) if both else "NONE"
    print(f"  both halves positive: {names}")
    if not both:
        print("  -> NO gate clears both halves. That is a refusal, not a "
              "recommendation (I19).")


if __name__ == "__main__":
    main()
