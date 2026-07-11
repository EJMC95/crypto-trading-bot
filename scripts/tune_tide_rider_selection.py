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

Usage:  python scripts/tune_tide_rider_selection.py            # 3-fold comparison
        python scripts/tune_tide_rider_selection.py --robust   # pre-live robustness gate
"""
import importlib.util
import os
import random
import sys

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


def robust():
    """PRE-LIVE GATE for TREND_RANK_BY_FUNDING. Three hardenings over main():
       (1) 5 independent OOS windows, not 3;
       (2) baseline = a DISTRIBUTION of 20 random admission orders (list-order is
           just one arbitrary ordering — lowfund must beat the population);
       (3) implementation match: the LIVE bot ranks by the INSTANTANEOUS rate, the
           backtest used a 7d average — so re-test with FUND_LOOKBACK=1 (1-day
           funding, the closest daily proxy). PASS requires the 1d variant to hold."""
    K = 2  # the live bot's margin-bound slot count
    rng = random.Random(42)

    def fixed_order_scorer(order):
        rank = {c: i for i, c in enumerate(order)}
        return lambda coin, feat, ctx: -rank.get(coin, 99)

    def run(lookback):
        SC.FUND_LOOKBACK = lookback
        data = SC.load()
        days, coins = SC.build_series(data)
        majors = [c for c in SC.MAJORS if c in coins]
        N = len(days); start = 200; span = N - start
        folds = [(start + span * i // 6, start + span * (i + 1) // 6) for i in range(1, 6)]

        def oos(scorer):
            eq = 1.0; per = []
            for lo, hi in folds:
                m = SC.simulate(days[lo:hi], coins, majors, scorer, max_open=K)
                per.append(m["basket"]); eq *= (1 + m["basket"])
            return eq - 1.0, per

        lf, lf_per = oos(SC.score_lowfund)
        lo_, lo_per = oos(fixed_order_scorer(SC.MAJORS))
        perms = []
        for _ in range(20):
            p = SC.MAJORS[:]; rng.shuffle(p)
            perms.append(oos(fixed_order_scorer(p))[0])
        beaten = sum(1 for x in perms if lf > x)
        fold_wins = sum(1 for a, b in zip(lf_per, lo_per) if a > b + 1e-9)
        fold_ties = sum(1 for a, b in zip(lf_per, lo_per) if abs(a - b) <= 1e-9)
        print(f"\n--- FUND_LOOKBACK={lookback}d | k={K} | 5 OOS windows ---")
        print(f"  lowfund      OOS {lf*100:+7.1f}% | folds {' '.join(f'{r*100:+6.1f}' for r in lf_per)}")
        print(f"  list-order   OOS {lo_*100:+7.1f}% | folds {' '.join(f'{r*100:+6.1f}' for r in lo_per)}")
        print(f"  20 random orders: mean {sum(perms)/len(perms)*100:+.1f}%  "
              f"min {min(perms)*100:+.1f}%  max {max(perms)*100:+.1f}%")
        print(f"  lowfund beats {beaten}/20 permutations; beats list-order in "
              f"{fold_wins} folds, ties {fold_ties} (ties = selection never bound)")
        return lf, lo_, beaten, fold_wins, fold_ties, len(perms), max(perms)

    r7 = run(7)
    r1 = run(1)
    ok = all(lf > lo for lf, lo, *_ in (r7, r1)) and \
        all(beaten >= 18 for _, _, beaten, *_ in (r7, r1)) and \
        all(lf >= mx - 1e-9 or beaten == n for lf, _, beaten, _, _, n, mx in (r7, r1))
    verdict = ("PASS — funding-ranked selection is robust to fold count, baseline "
               "choice, and the 1d (live-implementable) ranking. OK to enable live."
               if ok else
               "FAIL — does not survive hardening. Do NOT enable on the live bot.")
    print(f"\nGATE: {verdict}")
    return ok


if __name__ == "__main__":
    if "--robust" in sys.argv:
        robust()
    else:
        main()
