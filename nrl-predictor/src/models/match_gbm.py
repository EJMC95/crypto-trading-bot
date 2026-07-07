"""Tier-3 gradient boosting on top of the Elo/Poisson stack (Build Spec §5).

LightGBM binary classifier (draws excluded from training, scored 0.5 at eval like
everywhere else). Walk-forward by season: for each evaluation season, train only on
matches that finished before its first kickoff. The Elo and Poisson probability
features are themselves walk-forward outputs, so the stacking stays leak-free.
Calibration: Platt on 5-fold out-of-fold training predictions.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

from ..eval.backtest import PlattCalibrator, outcome

LGB_PARAMS = dict(
    objective="binary", n_estimators=400, learning_rate=0.03, num_leaves=15,
    min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
    reg_lambda=1.0, verbose=-1,
)


def _fit_calibrated(X: pd.DataFrame, y: np.ndarray) -> tuple[lgb.LGBMClassifier, PlattCalibrator]:
    oof = np.full(len(y), np.nan)
    for tr, va in KFold(5, shuffle=True, random_state=7).split(X):
        m = lgb.LGBMClassifier(**LGB_PARAMS)
        m.fit(X.iloc[tr], y[tr])
        oof[va] = m.predict_proba(X.iloc[va])[:, 1]
    cal = PlattCalibrator().fit(oof, y.astype(float))
    model = lgb.LGBMClassifier(**LGB_PARAMS)
    model.fit(X, y)
    return model, cal


def walk_forward(matches: pd.DataFrame, features: pd.DataFrame,
                 eval_years: range) -> pd.DataFrame:
    """Adds p_gbm to matches for every season in eval_years."""
    out = matches.copy()
    out["p_gbm"] = np.nan
    y_all = outcome(matches)
    usable = features.notna().all(axis=1).to_numpy()
    for year in eval_years:
        season_start = matches.loc[matches["year"] == year, "date"].min()
        tr = (matches["date"] < season_start).to_numpy() & usable & (y_all != 0.5)
        te = (matches["year"] == year).to_numpy() & usable
        if tr.sum() < 500 or te.sum() == 0:
            continue
        model, cal = _fit_calibrated(features[tr], y_all[tr].astype(int))
        out.loc[te, "p_gbm"] = cal.predict(model.predict_proba(features[te])[:, 1])
    return out


def fit_final(matches: pd.DataFrame, features: pd.DataFrame):
    """Fit on everything (for live prediction of the next round)."""
    y_all = outcome(matches)
    usable = features.notna().all(axis=1).to_numpy() & (y_all != 0.5)
    return _fit_calibrated(features[usable], y_all[usable].astype(int))
