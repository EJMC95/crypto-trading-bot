#!/usr/bin/env python3
"""EXPLORE-POOL SLICE study on Lighter's own tape — what would the widened
explore pool (EXPLORE_ZERO_DIAGNOSIS_2026-07-29.md, operator "proceed")
actually trade like under the live Farmer's rules?

Slices, by TODAY'S 24h quote turnover (the same ranking the live prelim uses):
  EXPLOIT  — qvol >= $10M   (the live MIN_VOL floor; ~11 books)
  POOL@2M  — $2M <= qvol < $10M  (the proposed FUNDING_EXPLORE_MIN_VOL=2e6)
  POOL@1M  — $1M <= qvol < $10M  (sensitivity)
Each slice runs the UNMODIFIED live rules (gate 0.05 TRUE, TP/STOP/hold as
shipped) through the corrected harness, both halves, at 0.5 / 2 / 5 bps —
the pool books are THIN, so the 0.5bps measured-on-liquid-books slip is a
lower bound there; 5bps is the honest thin-book row.

LIMITS (stated, same class as the harness's own):
  * slice membership uses TODAY's turnover for the whole window
    (survivorship flavor — the harness's top-N has the same);
  * one tape snapshot (the 23/24-Jul fetches proved the baseline swings
    between days — treat magnitudes as tape-local, signs/ordering as the
    signal);
  * the purpose of explore is COVERAGE/measurement (a shadow probe, per the
    Lever-1 design note): the bar here is "not catastrophic at honest
    slip", not "proven earner" — promotion to live keeps the judge's bar.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_funding_lighter as bt   # noqa: E402

DAYS, UNIVERSE = 180, 60
MAIN_FLOOR = 10e6


def main():
    print(f"Loading {DAYS}d, top {UNIVERSE} by today's turnover "
          f"(cache-or-fetch)")
    mk = bt.load(DAYS, UNIVERSE, refresh=False)
    obs = bt._get("/api/v1/orderBookDetails").get("order_book_details") or []
    qvol = {o["symbol"]: float(o.get("daily_quote_token_volume") or 0.0)
            for o in obs if o.get("symbol")}
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    mid = lo + (hi - lo) // 2

    slices = {
        "EXPLOIT>=10M": {s: m for s, m in mk.items()
                         if qvol.get(s, 0) >= MAIN_FLOOR},
        "POOL@2M": {s: m for s, m in mk.items()
                    if 2e6 <= qvol.get(s, 0) < MAIN_FLOOR},
        "POOL@1M": {s: m for s, m in mk.items()
                    if 1e6 <= qvol.get(s, 0) < MAIN_FLOOR},
    }
    print(f"\nwindow {(hi - lo) / 86400:.0f}d | slice sizes: " +
          ", ".join(f"{k}={len(v)}" for k, v in slices.items()))
    for name, sl in slices.items():
        print(f"  {name}: {sorted(sl)}")

    hdr = (f"{'slice':>14s} {'slip':>5s} {'P&L $':>9s} {'fund$':>8s} "
           f"{'price$':>9s} {'n':>5s} {'win%':>6s} {'maxDD':>8s} | "
           f"{'h1':>8s} {'h2':>8s} {'both+':>6s}")
    print("\n" + hdr)
    print("-" * len(hdr))
    verdict = {}
    for name, sl in slices.items():
        if not sl:
            print(f"{name:>14s}   (empty slice — no paired-history books)")
            continue
        for slip_bps in (0.5, 2.0, 5.0):
            bt.SLIP = slip_bps / 1e4
            full = bt.run(sl, 0.05, lo, hi + 1)
            h1 = bt.run(sl, 0.05, lo, mid)
            h2 = bt.run(sl, 0.05, mid, hi + 1)
            both = (full["pnl"] > 0 and h1["pnl"] > 0 and h2["pnl"] > 0)
            print(f"{name:>14s} {slip_bps:>5.1f} {full['pnl']:>9.2f} "
                  f"{full['fund']:>8.2f} {full['price']:>9.2f} "
                  f"{full['n']:>5d} {full['win']:>6.1f} "
                  f"{full['maxdd']:>8.2f} | {h1['pnl']:>8.2f} "
                  f"{h2['pnl']:>8.2f} {'yes' if both else 'no':>6s}")
            verdict[(name, slip_bps)] = full["pnl"]
        print()

    print("READOUT — the activation question is measurement-shaped:")
    p2 = verdict.get(("POOL@2M", 2.0))
    p5 = verdict.get(("POOL@2M", 5.0))
    if p2 is None:
        print("  POOL@2M produced no tradable history — widening buys nothing;")
        print("  do not activate until the venue's mid-turnover tier fills in.")
    elif p5 is not None and p5 > -10 and p2 > -10:
        print(f"  POOL@2M holds at honest thin-book slip (2bps {p2:+.2f} / "
              f"5bps {p5:+.2f}) — a shadow probe is affordable:")
        print("  set FUNDING_EXPLORE_MIN_VOL=2000000 on the SHADOW arm only.")
    else:
        print(f"  POOL@2M is materially negative at honest slip (2bps "
              f"{p2:+.2f} / 5bps {p5:+.2f}) — the widened pool eats carry;")
        print("  recommend NOT activating; explore stays a design question.")


if __name__ == "__main__":
    main()
