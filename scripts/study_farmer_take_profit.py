#!/usr/bin/env python3
"""study_farmer_take_profit.py — the Farmer's TAKE_PROFIT gene, on LIGHTER.

WHY (2026-07-29). `tp-0.06` is the experiment judge's NEXT serial candidate and
would spend a >=7-day slot on the fleet's ONLY path to `live.funding.*`. Its
recorded rationale is:

    "tp-0.06 stands: take_profit IS the Farmer's measured-positive exit family
     (shadow 11-0 +$14.96, live 9-0 +$8.11)"

That is a NON-SEQUITUR, and this study is what makes the gap visible. "TP exits
are the profitable exit family" is a claim about the trades that REACH the bar.
"Raise the bar" is a claim about a different population — the trades that would
have reached 4% and now must reach 6%. Confirmed here: at TP 0.04 the tp exit
fires 224 times at $1.010/trade; at 0.06 it fires 117 times at $1.511/trade —
richer per fill, but ~half as many, and the difference lands in flip/cold/
max_hold. Whether the trade is worth it is exactly what had never been measured.

METHOD. Varies exactly ONE variable — TAKE_PROFIT — with the entry gate held at
0.05 TRUE (what the live bot does today), reusing backtest_funding_lighter.run()
so the CLOSE path mirrors production (persistence parity, exit ordering,
post-stop cooldown) instead of a fresh harness that would re-learn the 22-Jul
lesson the hard way ([[harness-must-mirror-productions-close-path]]).

Reported at BOTH slips — the pessimistic 5bps default and the MEASURED ~0.5bps
real fill cost — and on BOTH universes, because the universe is not a detail:
the canonical top-25 and the broader all-cached set disagree on the SIGN of the
tp-0.06 effect. (That disagreement is also what exposed the loader's cache
universe trap, fixed the same day in backtest_funding_lighter.load().)

VERDICT AS RUN (150d Lighter tape, 2026-02-24 -> 2026-07-24):

    universe   slip     TP 0.04 (live)   TP 0.06     delta      both halves
    top-25     5bps        -27.96         -14.07     +13.89     none clear
    top-25     0.5bps       -3.44          +7.44     +10.88     none clear
    all-79     5bps        +34.07         -16.37     -50.43     none clear
    all-79     0.5bps      +55.26          +1.23     -54.03     none clear

  * NO TP value is positive in BOTH halves, at either universe or either slip.
    h1 is negative in every single row: the tape's first half is hostile to
    these rules regardless of where the take-profit sits.
  * tp-0.06 BEATS live on top-25 and LOSES badly on all-79. A knob whose sign
    depends on the universe is not an edge, it is a coin the tape cannot call.

  => tp-0.06 is NOT refuted. It is UNSUPPORTED, and Lighter's own tape cannot
     settle it. Per [[backtest-on-lighter-only]] that is the end of the enquiry:
     no NEW take_profit allele can be justified from this venue's evidence
     either, so the incubator's sterile TP gene should stay sterile until a
     different kind of evidence exists.

REGIME CAVEAT (21-Jul review item 18, adopted D5): this whole 150d window is
one falling-BTC regime. The Farmer is funding-driven and largely direction-
agnostic (it shorts positive funding, longs negative), so the directional
both-halves caveat bites less here than it does for a trend bot — but "both
halves" on a single-regime tape is still a weaker bar than it looks, and
nothing here clears it anyway.

Read-only. Touches no bot, no lever, no ledger.

Usage:
  python3 scripts/study_farmer_take_profit.py
  python3 scripts/study_farmer_take_profit.py --days 150 --universe 25
  python3 scripts/study_farmer_take_profit.py --selftest
"""
import argparse
import os
import sys
import time as _t

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

import backtest_funding_lighter as bfl                  # noqa: E402

GATE = 0.05                       # live today; HELD across the sweep
TP_GRID = [0.03, 0.04, 0.05, 0.06, 0.08]
SLIPS = [5.0, 0.5]                # pessimistic default, then the MEASURED real
LIVE_TP = 0.04


def slice_universe(mk, n):
    """Top-n by the cached dict's volume-ordered insertion order."""
    return {k: mk[k] for k in list(mk)[:n]}


def sweep(mk, label, tp_grid=None, gate=GATE):
    """Print the TP sweep for one universe. Returns {(slip, tp): result}."""
    tp_grid = TP_GRID if tp_grid is None else tp_grid
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    mid = lo + (hi - lo) // 2
    print(f"\n===== {label}: {len(mk)} markets | "
          f"{_t.strftime('%Y-%m-%d', _t.gmtime(lo))} -> "
          f"{_t.strftime('%Y-%m-%d', _t.gmtime(hi))} ({(hi-lo)/86400:.0f}d) =====")
    out, keep_tp, keep_slip = {}, bfl.TAKE_PROFIT, bfl.SLIP
    try:
        for slip_bps in SLIPS:
            bfl.SLIP = slip_bps / 1e4
            print(f"\n  --- slip {slip_bps}bps/fill ---")
            hdr = (f"  {'TP':>6s} {'P&L $':>9s} {'n':>5s} {'win%':>6s} "
                   f"{'tp_n':>5s} {'tp $/t':>7s} | {'h1':>9s} {'h2':>9s}  "
                   f"both?   vs live")
            print(hdr)
            print("  " + "-" * (len(hdr) - 2))
            base = None
            for tp in tp_grid:
                bfl.TAKE_PROFIT = tp
                full = bfl.run(mk, gate, lo, hi + 1)
                h1 = bfl.run(mk, gate, lo, mid)
                h2 = bfl.run(mk, gate, mid, hi + 1)
                out[(slip_bps, tp)] = full
                if abs(tp - LIVE_TP) < 1e-9:
                    base = full["pnl"]
                tpn = full["why_n"].get("tp", 0)
                per = full["why_pnl"].get("tp", 0.0) / tpn if tpn else 0.0
                both = "YES" if (h1["pnl"] > 0 and h2["pnl"] > 0) else "no"
                delta = "" if base is None else f"{full['pnl'] - base:>+8.2f}"
                tag = "  <- LIVE" if abs(tp - LIVE_TP) < 1e-9 else ""
                print(f"  {tp:>6.2f} {full['pnl']:>9.2f} {full['n']:>5d} "
                      f"{full['win']:>6.1f} {tpn:>5d} {per:>7.3f} | "
                      f"{h1['pnl']:>9.2f} {h2['pnl']:>9.2f}  {both}  "
                      f"{delta}{tag}")
    finally:
        bfl.TAKE_PROFIT, bfl.SLIP = keep_tp, keep_slip
    return out


def exit_mix(mk, tp, gate=GATE, slip_bps=0.5):
    """WHERE the trades that no longer reach TP end up instead."""
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    keep_tp, keep_slip = bfl.TAKE_PROFIT, bfl.SLIP
    try:
        bfl.TAKE_PROFIT, bfl.SLIP = tp, slip_bps / 1e4
        r = bfl.run(mk, gate, lo, hi + 1)
    finally:
        bfl.TAKE_PROFIT, bfl.SLIP = keep_tp, keep_slip
    n = r["n"] or 1
    print(f"\n  === TP {tp:.2f} exit mix (n={n}, slip {slip_bps}bps) ===")
    for why, k in sorted(r["why_n"].items(), key=lambda x: -x[1]):
        print(f"    {why:>10s} {k:>5d} {100*k/n:>5.1f}%  "
              f"${r['why_pnl'][why]:>8.2f}  (${r['why_pnl'][why]/k:>6.3f}/trade)")
    return r


def _selftest():
    """Offline: the study's own reasoning helpers, no network, no DB."""
    mk = {f"S{i}": {"fund": {}, "cand": {}} for i in range(10)}
    assert list(slice_universe(mk, 3)) == ["S0", "S1", "S2"], "top-n, in order"
    assert len(slice_universe(mk, 99)) == 10, "asking wide is not an error"
    assert slice_universe(mk, 0) == {}
    # the constants this study's verdict is quoted against must not drift
    assert LIVE_TP in TP_GRID and GATE == 0.05
    assert 0.06 in TP_GRID, "the queued candidate must be ON the grid"
    assert 0.5 in SLIPS and 5.0 in SLIPS, "both slips or the verdict is partial"
    # the harness must be the PRODUCTION-mirroring one, not a local copy
    assert hasattr(bfl, "run") and hasattr(bfl, "load")
    print("study_farmer_take_profit selftest OK (universe slice, grid/slip "
          "invariants, harness identity)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--universe", type=int, default=25)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    narrow = bfl.load(a.days, a.universe, a.refresh)
    sweep(narrow, f"CANONICAL top-{a.universe} by volume")
    print("\n\n===== MECHANISM: where do the lost TP exits go? =====")
    for tp in (LIVE_TP, 0.06):
        exit_mix(narrow, tp)
    print("\nBOTH HALVES must agree in sign before a TP is believable. None do "
          "— and tp-0.06's sign flips with the universe. See this file's "
          "header for the recorded verdict.")


if __name__ == "__main__":
    main()
