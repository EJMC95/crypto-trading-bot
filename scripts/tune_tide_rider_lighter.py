#!/usr/bin/env python3
"""
scripts/tune_tide_rider_lighter.py — WALK-FORWARD tune of Tide Rider for LIGHTER.

"Tune it on Lighter" done honestly. Naive tuning = pick the in-sample best = the
overfitting the shootout's EMA sweep already exposed (no robust ridge; H2 killed
every re-fit). So this uses WALK-FORWARD out-of-sample validation: pick each family's
best config on TRAIN windows, score it only on the UNSEEN TEST window that follows,
and aggregate the OOS result. A tune only earns its way onto Lighter if it beats the
incumbent 50/200 OUT OF SAMPLE — not in the window it was fit on.

Lighter-specific lever: FUNDING. The Kraken-validated 50/200 ignores it, but a long
perp PAYS funding (the ~-13pp drag). So the principled tune is a funding-aware ENTRY
GATE — don't OPEN a new long while trailing funding APR is punishing; still hold to
the death cross once in (never kicked out of a good trend just for funding). Compared
against base 50/200 and a blind EMA-grid re-fit (the overfitting control).

Reuses the shootout engine (identical funding/fee/accounting) + its majors cache.
Usage:  python scripts/tune_tide_rider_lighter.py
"""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "shoot", os.path.join(os.path.dirname(__file__), "backtest_strategy_shootout.py"))
S = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(S)


def ema_sig(c, t, f, fast, slow, gate_apr=None):
    """Golden-cross long/flat; if gate_apr set, block NEW entries while trailing-7d
    funding APR > gate_apr (still hold to death cross once long). Causal — no look-ahead."""
    ef, es = S.ema(c, fast), S.ema(c, slow)
    out = [False] * len(c); long = False
    for i in range(len(c)):
        if i < slow:
            continue
        golden = ef[i] > es[i]
        if not long and golden:
            if gate_apr is None:
                long = True
            else:
                rf = [f.get(t[k], 0.0) for k in range(max(0, i - 6), i + 1)]
                apr = (sum(rf) / max(1, len(rf))) * 365.0
                long = apr <= gate_apr
        elif long and not golden:
            long = False
        out[i] = long
    return out, slow


def seqs_for(data, fast, slow, gate=None):
    warm = 0; sq = {}
    for c in data:
        s, w = ema_sig(data[c]["c"], data[c]["t"], data[c]["f"], fast, slow, gate)
        sq[c] = s; warm = max(warm, w)
    return sq, warm


def wf_folds(warm, N, k=3):
    """Expanding-train walk-forward: k test windows over [q1..N]; train = everything
    before each test window. Returns list of (train_lo, train_hi, test_lo, test_hi)."""
    start = warm + 1
    span = N - start
    q = [start + span * i // (k + 1) for i in range(k + 2)]
    return [(start, q[i + 1], q[i + 1], q[i + 2]) for i in range(k)]


def eval_family(data, warm_hint, folds, grid, gate=False):
    """For each fold pick the grid config with the best TRAIN perp%, score it on TEST.
    Returns (oos_compound_ret, per_fold[(cfg, test_ret, test_dd)])."""
    per = []; oos_eq = 1.0
    for (trlo, trhi, telo, tehi) in folds:
        best = None
        for cfg in grid:
            fast, slow, g = cfg
            sq, warm = seqs_for(data, fast, slow, g)
            tr = S.basket(data, sq, warm, trlo, trhi)
            if tr and (best is None or tr["ret"] > best[1]):
                best = (cfg, tr["ret"], sq, warm)
        cfg, _, sq, warm = best
        te = S.basket(data, sq, warm, telo, tehi)
        per.append((cfg, te["ret"], te["mdd"]))
        oos_eq *= (1 + te["ret"])
    return oos_eq - 1.0, per


def main():
    data = S.load_majors()
    N = min(len(d["c"]) for d in data.values())
    folds = wf_folds(200, N, k=3)
    print(f"Walk-forward tune on Lighter — 6 majors, 1x long perp, real funding, {N}d")
    print(f"{len(folds)} expanding OOS folds; test windows: "
          f"{[(lo, hi) for _, _, lo, hi in folds]}\n")

    # base incumbent = single fixed config
    base_oos, base_per = eval_family(data, 200, folds, [(50, 200, None)])
    # blind EMA re-fit (overfitting control): grid of pairs, pick train-best each fold
    ema_grid = [(f, s, None) for s in (100, 120, 150, 200) for f in (10, 20, 30, 50) if f < s]
    ema_oos, ema_per = eval_family(data, 200, folds, ema_grid)
    # funding-gated 50/200 (the principled Lighter tune): pick train-best gate each fold
    gate_grid = [(50, 200, g) for g in (0.15, 0.25, 0.40, 0.60, 0.90, None)]
    gate_oos, gate_per = eval_family(data, 200, folds, gate_grid)

    def line(name, oos, per):
        cfgs = ",".join(f"{c[0]}/{c[1]}" + (f"@{c[2]}" if c[2] is not None else "") for c, _, _ in per)
        rets = " ".join(f"{r*100:+6.1f}" for _, r, _ in per)
        print(f"{name:>22} | OOS {oos*100:+7.1f}% | per-fold {rets} | picked {cfgs}")

    print(f"{'family':>22} | {'OOS (compound)':>14} | per-fold test perp%")
    print("-" * 92)
    line("base 50/200 (LIVE)", base_oos, base_per)
    line("blind EMA re-fit", ema_oos, ema_per)
    line("funding-gated 50/200", gate_oos, gate_per)
    print("-" * 92)
    winner = max([("base", base_oos), ("ema-refit", ema_oos), ("fund-gate", gate_oos)],
                 key=lambda x: x[1])
    print(f"\nOOS winner: {winner[0]} ({winner[1]*100:+.1f}%). A tune is only worth shadow-"
          f"testing on Lighter if it beats base 50/200 ({base_oos*100:+.1f}%) OUT OF SAMPLE and "
          f"does so across folds (not one). If the funding-gate picks gate=None most folds, the "
          f"gate isn't helping and the incumbent stands.")


if __name__ == "__main__":
    main()
