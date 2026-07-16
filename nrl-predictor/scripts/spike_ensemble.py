"""Gate: does adding model diversity (a gradient-boosted learner) beat the
champion logistic blend?

The champion is a logistic stack of the Elo and Poisson probabilities. A pro shop
runs an ENSEMBLE of diverse learners, not one. We test whether a
HistGradientBoosting classifier — a fundamentally different, non-linear model
class — on the same base signals (plus the availability lineup delta when present)
improves out-of-sample Brier when blended with the champion. Walk-forward: fit on
<=2019, evaluate 2020-2026. Ships only if it beats.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.eval import backtest as bt

OUT = ROOT / "outputs"
FIT_MAX = 2019
EVAL = range(2020, 2027)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def main() -> None:
    bf = pd.read_parquet(OUT / "blend_frame.parquet").dropna(subset=["p_elo_cal", "p_pois"]).copy()
    bf["y"] = bt.outcome(bf)
    bf = bf[bf["y"] != 0.5]                       # drop draws for a clean 0/1 target
    feats = ["p_elo_cal", "p_pois"]
    X = np.column_stack([logit(bf["p_elo_cal"]), logit(bf["p_pois"])])
    y = bf["y"].to_numpy()
    yr = bf["year"].to_numpy()

    fit = yr <= FIT_MAX
    ev = np.isin(yr, list(EVAL))
    gb = HistGradientBoostingClassifier(max_depth=3, max_iter=200,
                                        learning_rate=0.05, l2_regularization=1.0)
    gb.fit(X[fit], y[fit])
    p_gb = gb.predict_proba(X[ev])[:, 1]
    p_champ = bf["p_blend"].to_numpy()[ev]
    y_ev = y[ev]

    # blend champion with the GB learner at a few mixing weights
    print(f"eval games {ev.sum()} (2020-26), fit {fit.sum()} (<= {FIT_MAX})")
    print(f"champion blend      Brier {bt.brier(p_champ, y_ev):.4f}  logloss {bt.log_loss(p_champ, y_ev):.4f}")
    print(f"GB alone            Brier {bt.brier(p_gb, y_ev):.4f}  logloss {bt.log_loss(p_gb, y_ev):.4f}")
    best = None
    for w in (0.2, 0.3, 0.5):
        mix = (1 - w) * p_champ + w * p_gb
        b = bt.brier(mix, y_ev)
        print(f"champion + {w:.0%} GB     Brier {b:.4f}  logloss {bt.log_loss(mix, y_ev):.4f}")
        if best is None or b < best[1]:
            best = (w, b)
    champ_b = bt.brier(p_champ, y_ev)
    beats = best[1] < champ_b - 0.0002
    print(f"\nbest mix: +{best[0]:.0%} GB -> Brier {best[1]:.4f} vs champion {champ_b:.4f}")
    print(f"ensemble {'BEATS' if beats else 'does NOT beat'} the champion blend.")


if __name__ == "__main__":
    main()
