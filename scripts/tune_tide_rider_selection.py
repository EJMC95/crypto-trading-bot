#!/usr/bin/env python3
"""
scripts/tune_tide_rider_selection.py — when Tide Rider can't afford ALL the golden
majors (margin-constrained), does RANKING which ones to hold beat first-come order?

Newly relevant: the live bot has ~$35 collateral at $15 clips -> ~2 positions. When
3+ majors are golden it currently opens them in COINS list order (BTC,ETH,SOL,...
first-come). This asks whether a smarter pick — LOWEST funding (cheapest to carry a
long) or STRONGEST trend — beats that, OUT OF SAMPLE. Universe stays the 6 majors
(widening was already rejected); only the SELECTION among golden majors changes.

Reuses the scanner engine (SC.simulate: slot-constrained portfolio, real funding).
Walk-forward: the scorers are parameter-free RULES (nothing to fit), so OOS validity =
does a rule beat first-come CONSISTENTLY across independent test windows, not once.
A rule earns a live change only if it beats list-order in ALL folds at the live slot
count (k=2), robustly. (7th check in this line — prior 6 "wins" all evaporated OOS.)

Usage:  python scripts/tune_tide_rider_selection.py
"""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "sc", os.path.join(os.path.dirname(__file__), "backtest_tide_rider_scanner.py"))
SC = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(SC)

RANK = {c: i for i, c in enumerate(SC.MAJORS)}          # BTC=0 ... TRX=5


def score_listorder(coin, feat, ctx):
    return -RANK.get(coin, 99)                          # BTC first = the live bot's order


SCORERS = {"list-order (LIVE)": score_listorder,
           "lowfund": SC.score_lowfund,
           "trend": SC.score_trend}


def main():
    data = SC.load()
    days, coins = SC.build_series(data)
    majors = [c for c in SC.MAJORS if c in coins]
    N = len(days)
    start = 200
    span = N - start
    folds = [(start + span * i // 4, start + span * (i + 1) // 4) for i in range(1, 4)]
    print(f"Selection among the 6 majors under a slot cap — walk-forward OOS, {N}d")
    print(f"majors={majors}\nOOS windows (day idx): {folds}\n")

    for k in (2, 3):
        print(f"=== {k} slots (k={k}) — the live bot holds ~2 at $35 collateral ===")
        print(f"{'scorer':>18} | {'OOS%':>7} | per-fold perp%")
        print("-" * 60)
        base_fold = None
        for name, sc in SCORERS.items():
            rets = []
            eq = 1.0
            for (lo, hi) in folds:
                m = SC.simulate(days[lo:hi], coins, majors, sc, max_open=k)
                rets.append(m["basket"]); eq *= (1 + m["basket"])
            if name.startswith("list"):
                base_fold = rets
            beats = ""
            if base_fold and not name.startswith("list"):
                wins = sum(1 for a, b in zip(rets, base_fold) if a > b)
                beats = f"  beats list-order {wins}/{len(rets)} folds"
            print(f"{name:>18} | {(eq-1)*100:>7.1f} | "
                  f"{' '.join(f'{r*100:+6.1f}' for r in rets)}{beats}")
        print("-" * 60 + "\n")
    print("VERDICT: a scorer earns a LIVE change only if it beats list-order in ALL folds "
          "at k=2 (the live slot count), robustly across k. If it wins in one fold and loses "
          "another, it's regime noise — keep first-come. NB selection only BINDS when 3+ majors "
          "are golden at once (broad uptrend); in today's 1-golden regime it changes nothing.")


if __name__ == "__main__":
    main()
