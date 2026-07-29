#!/usr/bin/env python3
"""EXPLORE A/B DESIGN OPTIONS — the three routed options of
EXPLORE_ZERO_DIAGNOSIS_2026-07-29.md §3d, measured on ONE tape so the design
decision compares evidence with evidence, not one measured option with prose.
(#104 measured option 1's pool slices; options 2 and 3 had only prose.)

  Option 1 — explore-specific prefilter (SHIPPED inert 29-Jul as
             FUNDING_EXPLORE_MIN_VOL): pool = 24h turnover in [$2M, $10M),
             membership by TODAY's turnover — the #104 method, re-measured
             here so all three options share a tape.
  Option 2 — SCAN_DEEP_MAX 15->8: explore samples prelim ranks 9+, i.e. the
             WEAKEST-|apr| members of the SAME gated >=$10M set. Modelled
             DYNAMICALLY: at each hour the prelim proxy = {books with today's
             turnover >= $10M and |apr(t)| >= gate}, ranked by |apr(t)| desc
             (the live Stage-A sort, lighter_funding_bot.py:2053;
             cross_venue_mult re-orders survivors live but is LIVE-ONLY by
             its own docstring — no bench history exists to model). TAIL9+
             admits entries only in hours where the book's rank index >= 8;
             KEPT8 is the complement (what exploit still deep-scans).
  Option 3 — accept explore-zero: the unfiltered >=$10M book IS this option
             (conviction-only status quo). Its row doubles as the baseline
             for the other two.

LIMITS (stated, the #104 class plus option 2's own):
  * slice membership uses TODAY's turnover for the whole window; the prelim
    proxy ignores held/cooling exclusions and the persistence clock (the
    harness applies persistence at entry, but the RANK is computed on the
    raw gated set) — rank indices are approximate near the boundary;
  * one tape snapshot — magnitudes are tape-local (the baseline has printed
    +$33/+$2/+$11 on three fetches); signs, ordering and OCCUPANCY are the
    signal;
  * the harness enters any admitted book greedily (first-come, MAX_OPEN
    slots) — live explore samples K=2 round-robin, so these rows measure the
    SLICE's tape quality, not live cadence. Occupancy is the cadence read:
    an empty tail cannot produce opens at any K.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_funding_lighter as bt   # noqa: E402

GATE = 0.05
MAIN_FLOOR = 10e6
DEEP8 = 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--universe", type=int, default=60)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    print(f"Loading {a.days}d, top {a.universe} by today's turnover "
          f"(cache-or-fetch)")
    mk = bt.load(a.days, a.universe, refresh=a.refresh)
    obs = bt._get("/api/v1/orderBookDetails").get("order_book_details") or []
    qvol = {o["symbol"]: float(o.get("daily_quote_token_volume") or 0.0)
            for o in obs if o.get("symbol")}
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    mid = lo + (hi - lo) // 2

    exploit = {s: m for s, m in mk.items() if qvol.get(s, 0) >= MAIN_FLOOR}
    pool2 = {s: m for s, m in mk.items()
             if 2e6 <= qvol.get(s, 0) < MAIN_FLOOR}

    # ---- option 2: per-hour |apr| rank within the gated >=$10M set ----------
    rank = {}                             # (sym, hour) -> 0-based rank index
    tail_sizes = []                       # per-hour size of ranks 9+
    gated_sizes = []
    for t in hours:
        gated = [(s, abs(m["fund"][t])) for s, m in exploit.items()
                 if t in m["fund"] and abs(m["fund"][t]) >= GATE]
        gated.sort(key=lambda kv: -kv[1])
        for i, (s, _) in enumerate(gated):
            rank[(s, t)] = i
        gated_sizes.append(len(gated))
        tail_sizes.append(max(0, len(gated) - DEEP8))

    def tail_ok(sym, t):
        r = rank.get((sym, t))
        return r is not None and r >= DEEP8

    def kept_ok(sym, t):
        r = rank.get((sym, t))
        return r is not None and r < DEEP8

    occ = 100.0 * sum(1 for x in tail_sizes if x > 0) / len(tail_sizes)
    print(f"\nwindow {(hi - lo) / 86400:.0f}d | exploit>=10M n={len(exploit)} "
          f"{sorted(exploit)}")
    print(f"pool $2-10M n={len(pool2)} {sorted(pool2)}")
    print(f"\nOPTION-2 OCCUPANCY (the cadence read): gated >=$10M set mean "
          f"{sum(gated_sizes)/len(gated_sizes):.1f} books/h, max "
          f"{max(gated_sizes)}; tail (ranks 9+) nonempty {occ:.1f}% of hours, "
          f"mean {sum(tail_sizes)/len(tail_sizes):.2f} books")

    rows = [
        ("OPT3=BASE >=10M", exploit, None),
        ("OPT2 TAIL9+", exploit, tail_ok),
        ("OPT2 KEPT8", exploit, kept_ok),
        ("OPT1 POOL@2M", pool2, None),
    ]
    hdr = (f"{'row':>16s} {'slip':>5s} {'P&L $':>9s} {'fund$':>8s} "
           f"{'price$':>9s} {'n':>5s} {'win%':>6s} {'maxDD':>8s} | "
           f"{'h1':>8s} {'h2':>8s} {'both+':>6s}")
    print("\n" + hdr)
    print("-" * len(hdr))
    res = {}
    for name, sl, pred in rows:
        if not sl:
            print(f"{name:>16s}   (empty slice)")
            continue
        for slip_bps in (0.5, 2.0, 5.0):
            bt.SLIP = slip_bps / 1e4
            full = bt.run(sl, GATE, lo, hi + 1, entry_ok=pred)
            h1 = bt.run(sl, GATE, lo, mid, entry_ok=pred)
            h2 = bt.run(sl, GATE, mid, hi + 1, entry_ok=pred)
            both = (full["pnl"] > 0 and h1["pnl"] > 0 and h2["pnl"] > 0)
            print(f"{name:>16s} {slip_bps:>5.1f} {full['pnl']:>9.2f} "
                  f"{full['fund']:>8.2f} {full['price']:>9.2f} "
                  f"{full['n']:>5d} {full['win']:>6.1f} "
                  f"{full['maxdd']:>8.2f} | {h1['pnl']:>8.2f} "
                  f"{h2['pnl']:>8.2f} {'yes' if both else 'no':>6s}")
            res[(name, slip_bps)] = (full, h1, h2)
        print()

    print("READOUT — one tape, three options:")
    t_n = res.get(("OPT2 TAIL9+", 2.0), ({"n": 0},))[0]["n"]
    print(f"  opt2: tail occupancy {occ:.1f}% of hours "
          f"(mean {sum(tail_sizes)/len(tail_sizes):.2f} books) and n={t_n} "
          f"harness trades over the window — a relabel of exploit's weakest-"
          f"|apr| leftovers, not new coverage; opt2 also REMOVES those hours "
          f"from deep-scan (KEPT8 vs BASE is the cost side).")
    print("  opt1: the only option whose candidates are NEW books (disjoint "
          "pool below the main floor); judged on its own #104 bar — 'not "
          "catastrophic at honest thin-book slip', promotion stays the "
          "judge's.")
    print("  opt3: the BASE row is the status-quo A/B (conviction-only) — "
          "rename honestly if chosen.")


if __name__ == "__main__":
    main()
