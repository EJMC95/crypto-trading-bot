"""Gate new blend features against the current champion (walk-forward 2015–2025).

Loads the per-match Elo/Poisson blend inputs saved by run_phase3 (blend_frame),
adds candidate features (rest/travel/Origin context; ridge-APM availability),
fits a logistic stack on the 2010–2014 tune window for each feature set, and
reports Brier / log loss on 2015–2025. A feature set only earns a place if it
beats the base 2-feature blend out-of-sample.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval import backtest as bt
from src.features import context, player_value
from src.ingest import teams

OUT = ROOT / "outputs"
PROCESSED = ROOT / "data" / "processed"
TUNE = range(2007, 2015)   # wider fit window than the 2-feature base needed
EVAL = range(2015, 2026)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_offset_logistic(X, y, offset, l2=8.0, iters=60):
    """p = sigmoid(offset + Xβ); fit β by Newton steps with L2. The offset (the
    proven blend's logit) is held fixed, so the extra features can only correct it
    — they can help but never disturb the base. Strong L2 shrinks weak features to
    ~0, guaranteeing 'no worse' out-of-sample when a feature carries no signal."""
    X = np.asarray(X, float)
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(offset + X @ beta)))
        W = np.clip(p * (1 - p), 1e-6, None)
        grad = X.T @ (p - y) + l2 * beta
        H = (X * W[:, None]).T @ X + l2 * np.eye(X.shape[1])
        beta -= np.linalg.solve(H, grad)
    return beta


def predict_offset(X, beta, offset):
    return 1 / (1 + np.exp(-(offset + np.asarray(X, float) @ beta)))


def main() -> None:
    bf = pd.read_parquet(OUT / "blend_frame.parquet")
    bf = bf[bf["p_pois"].notna() & bf["home_score"].notna()].copy()
    bf["date"] = pd.to_datetime(bf["date"])
    bf["y"] = bt.outcome(bf)

    print("== context features ==")
    ctx = context.build(bf)
    for c in ctx.columns:
        bf[c] = ctx[c].values

    print("== ridge-APM availability (expanding refit per season) ==")
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    matches["date"] = pd.to_datetime(matches["date"])
    pm = pd.read_parquet(PROCESSED / "player_matches.parquet")
    app = player_value.player_appearances(pm, matches, teams)
    bf["avail_diff"] = 0.0
    for yr in list(TUNE) + list(EVAL):
        asof = pd.Timestamp(f"{yr}-01-01")
        vals = player_value.fit_apm(app, matches, asof)
        if not vals:
            continue
        mask = bf["year"] == yr
        bf.loc[mask, "avail_diff"] = player_value.avail_diff(
            bf.loc[mask], app, vals).values
    # standardise scale for the logistic fit
    bf["avail_diff"] = bf["avail_diff"] / (bf["avail_diff"].std() or 1.0)

    # offset = the proven blend's logit; standardise extra features on the tune window
    offset_all = logit(bf["p_blend"].to_numpy())
    ctx_cols = list(ctx.columns)
    lean_ctx = ["short_turnaround_away", "away_long_haul", "origin_window"]
    extra_sets = {
        "base blend (offset only)": [],
        "+ context (full 6)": ctx_cols,
        "+ context (lean 3)": lean_ctx,
        "+ availability (APM)": ["avail_diff"],
        "+ availability + lean context": ["avail_diff"] + lean_ctx,
        "+ everything": ctx_cols + ["avail_diff"],
    }
    tune_mask = bf["year"].isin(TUNE).to_numpy()
    eval_mask = bf["year"].isin(EVAL).to_numpy()
    y = bf["y"].to_numpy()
    y_tune, y_eval = y[tune_mask], y[eval_mask]

    rows = []
    for name, cols in extra_sets.items():
        if not cols:
            p_eval = 1 / (1 + np.exp(-offset_all[eval_mask]))
        else:
            Xr = bf[cols].to_numpy(float)
            mu, sd = Xr[tune_mask].mean(0), Xr[tune_mask].std(0) + 1e-9
            Xs = (Xr - mu) / sd
            beta = fit_offset_logistic(Xs[tune_mask], y_tune, offset_all[tune_mask])
            p_eval = predict_offset(Xs[eval_mask], beta, offset_all[eval_mask])
            if "avail" in name and "context" in name:
                for c, w in zip(cols, beta):
                    print(f"    correction weight {c:>26}: {w:+.3f}")
        rows.append({"feature set": name, "n_extra": len(cols),
                     "brier": round(bt.brier(p_eval, y_eval), 4),
                     "log_loss": round(bt.log_loss(p_eval, y_eval), 4)})
    tbl = pd.DataFrame(rows)
    base_brier = tbl.iloc[0]["brier"]
    tbl["vs base"] = (tbl["brier"] - base_brier).round(4)
    print()
    print(tbl.to_string(index=False))
    print("\nmarket benchmark (2015–2025): Brier 0.2075")
    best = tbl.sort_values("brier").iloc[0]
    print(f"\nBEST: {best['feature set']} — Brier {best['brier']} "
          f"({'BEATS' if best['brier'] < base_brier - 0.0002 else 'ties/does NOT beat'} "
          f"base {base_brier})")


if __name__ == "__main__":
    main()
