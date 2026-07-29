#!/usr/bin/env python3
"""DECAY-EXIT study — the A2 agenda item's queued backtest, on Lighter's own
tape (LEVER_AUTHORITY_TRIAGE_2026-07-29.md §A2: decay/flip exits decide 67.3%
of all Farmer closes and 36.2% of gross loss, and EXIT_APR is env-only BY
DESIGN — the flap fix. This study measures whether the CURRENT decay bar is
defensible before the 04-Aug review argues from prose. Study only; no lever,
no code change to the bot.)

Two pre-registered questions, eight variants total (multiplicity stated):
  1. EXIT_RATIO sweep {0.0, 0.2, 0.375*, 0.5, 0.75, 1.0} — exit_apr =
     enter_apr x ratio; 0.375 is the LIVE ratio (0.15/0.40); 0.0 disables
     the decay exit entirely (hold to flip/stop/tp/max_hold); 1.0 exits the
     moment the rate is below the entry gate.
  2. DECAY PERSISTENCE {2h, 4h} at the live ratio — the funding_carry
     exit-rebuild pattern (a spike-and-revert rate must stay decayed before
     it closes), via the harness's new decay_persist_h hook (0 = shipped
     behaviour, byte-identical).

Bar: both halves positive at BOTH 0.5 and 2.0 bps. Windows: the FULL 455d
tape (cache from the 30-Jul vol-filter run) AND its trailing-180d subwindow
(comparability with the gate/filter studies). Verdict feeds agenda item A2;
the flap-fix "env-only, never a lever" design is NOT in question here —
only whether 0.375 is the right constant.

    python3 scripts/study_decay_exit.py --cache <path-to-455d-cache>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_funding_lighter as bt   # noqa: E402

GATE = 0.05
RATIOS = (0.0, 0.2, 0.375, 0.5, 0.75, 1.0)
PERSISTS = (2, 4)


def sweep(mk, lo, hi, label):
    mid = lo + (hi - lo) // 2
    hdr = (f"{'variant':>16s} {'slip':>5s} {'P&L $':>9s} {'fund$':>8s} "
           f"{'n':>5s} {'win%':>6s} {'maxDD':>8s} {'cold%':>6s} | "
           f"{'h1':>8s} {'h2':>8s} {'both+':>6s}")
    print(f"\n=== {label}: {(hi - lo) / 86400:.0f}d ===")
    print(hdr)
    print("-" * len(hdr))
    verdicts = {}
    for ratio in RATIOS:
        bt.EXIT_RATIO = ratio
        for slip in (0.5, 2.0):
            bt.SLIP = slip / 1e4
            f = bt.run(mk, GATE, lo, hi + 1)
            h1 = bt.run(mk, GATE, lo, mid)
            h2 = bt.run(mk, GATE, mid, hi + 1)
            both = f["pnl"] > 0 and h1["pnl"] > 0 and h2["pnl"] > 0
            cold = 100.0 * f["why_n"].get("cold", 0) / max(f["n"], 1)
            tag = f"ratio {ratio:.3f}" + (" *LIVE*" if ratio == 0.375 else "")
            print(f"{tag:>16s} {slip:>5.1f} {f['pnl']:>9.2f} {f['fund']:>8.2f} "
                  f"{f['n']:>5d} {f['win']:>6.1f} {f['maxdd']:>8.2f} "
                  f"{cold:>6.1f} | {h1['pnl']:>8.2f} {h2['pnl']:>8.2f} "
                  f"{'yes' if both else 'no':>6s}")
            verdicts[(label, f"ratio{ratio}", slip)] = (f["pnl"], both)
        print()
    bt.EXIT_RATIO = 0.375
    for per in PERSISTS:
        for slip in (0.5, 2.0):
            bt.SLIP = slip / 1e4
            f = bt.run(mk, GATE, lo, hi + 1, decay_persist_h=per)
            h1 = bt.run(mk, GATE, lo, mid, decay_persist_h=per)
            h2 = bt.run(mk, GATE, mid, hi + 1, decay_persist_h=per)
            both = f["pnl"] > 0 and h1["pnl"] > 0 and h2["pnl"] > 0
            cold = 100.0 * f["why_n"].get("cold", 0) / max(f["n"], 1)
            tag = f"live+persist{per}h"
            print(f"{tag:>16s} {slip:>5.1f} {f['pnl']:>9.2f} {f['fund']:>8.2f} "
                  f"{f['n']:>5d} {f['win']:>6.1f} {f['maxdd']:>8.2f} "
                  f"{cold:>6.1f} | {h1['pnl']:>8.2f} {h2['pnl']:>8.2f} "
                  f"{'yes' if both else 'no':>6s}")
            verdicts[(label, f"persist{per}", slip)] = (f["pnl"], both)
        print()
    return verdicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None,
                    help="reuse a deep cache (e.g. the 455d fetch); default "
                         "shared cache")
    ap.add_argument("--days", type=int, default=455)
    ap.add_argument("--universe", type=int, default=25)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.cache:
        bt.CACHE = a.cache

    mk = bt.load(a.days, a.universe, refresh=a.refresh)
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    print(f"tape: {len(mk)} markets {(hi - lo) / 86400:.0f}d | gate {GATE} "
          f"TRUE | 6 ratios + 2 persistence variants (multiplicity: 8)")

    # parity: ratio 0.375 / persist 0 must reproduce the unmodified harness
    bt.SLIP = 0.5 / 1e4
    bt.EXIT_RATIO = 0.375
    base = bt.run(mk, GATE, lo, hi + 1)
    para = bt.run(mk, GATE, lo, hi + 1, decay_persist_h=0)
    assert (base["pnl"], base["n"]) == (para["pnl"], para["n"]), \
        "persist-0 must be byte-identical to the shipped ladder"
    print(f"parity: persist-0 == shipped ladder OK "
          f"(pnl {base['pnl']:+.2f}, n {base['n']})")

    sweep(mk, lo, hi, "FULL tape")
    lo180 = hi - 180 * 86400
    sweep(mk, lo180, hi, "trailing 180d")

    print("READOUT: the live column is ratio 0.375. If no variant beats it "
          "on BOTH windows'\nboth-halves bar, A2's answer is 'the constant "
          "stands — declare env-only and move on'.\nA winner here still "
          "ships nothing: exit bars are env-only by the flap-fix design;\n"
          "any change is an operator env decision at the review.")


if __name__ == "__main__":
    main()
