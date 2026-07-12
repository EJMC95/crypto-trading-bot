"""Player value via ridge adjusted-plus-minus (APM), for availability signals.

Standard adjusted plus-minus: regress each match's home margin on a sparse
player-indicator design (+1 for every home player, −1 for every away player) plus a
home-advantage intercept, with L2 regularisation. The fitted coefficient for a
player is his margin value in points, *controlled for teammates and opponents* —
which is why it beats the naive "team margin when he plays" (that's confounded by
the quality of the rest of the side).

Used to build an `avail_diff` feature: Σ(home lineup values) − Σ(away lineup
values). The logistic blend stack decides how much weight this earns *beyond* the
team rating — if a named side is weaker than usual (a star rested/injured), its
lineup value drops and the win prob shifts. Refit on an expanding window at each
evaluation boundary so it is strictly leak-free.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import Ridge

MARGIN_CAP = 40.0     # cap home margin so blowouts don't dominate the fit
RIDGE_ALPHA = 120.0   # strong shrinkage — most players near 0, stars separate


def player_appearances(player_matches: pd.DataFrame, matches: pd.DataFrame,
                       teams_mod) -> pd.DataFrame:
    """One row per (match, player, side). side = +1 home, −1 away."""
    m = matches[["match_id", "home_id", "away_id", "date"]]
    pm = player_matches[player_matches["match_id"].isin(m["match_id"])].copy()
    pm["team_id"] = teams_mod.to_canonical(pm["team"], "player_match_data")
    j = pm.merge(m, on="match_id", how="inner")
    j["side"] = np.where(j["team_id"] == j["home_id"], 1,
                         np.where(j["team_id"] == j["away_id"], -1, 0))
    return j.loc[j["side"] != 0, ["match_id", "player_id", "side", "date"]]


def fit_apm(appearances: pd.DataFrame, matches: pd.DataFrame,
            asof: pd.Timestamp) -> dict:
    """Fit APM on matches strictly before `asof`. Returns {player_id: value}."""
    m = matches[(matches["date"] < asof) & matches["home_score"].notna()].copy()
    if len(m) < 500:
        return {}
    app = appearances[appearances["match_id"].isin(m["match_id"])]
    players = np.sort(app["player_id"].unique())
    pidx = {p: i for i, p in enumerate(players)}
    midx = {mid: i for i, mid in enumerate(m["match_id"].values)}

    rows, cols, vals = [], [], []
    for a in app.itertuples(index=False):
        if a.match_id in midx and a.player_id in pidx:
            rows.append(midx[a.match_id]); cols.append(pidx[a.player_id]); vals.append(a.side)
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(len(m), len(players)))
    home_adv = np.ones((len(m), 1))
    X = sparse.hstack([X, sparse.csr_matrix(home_adv)]).tocsr()
    y = np.clip(m["home_score"].to_numpy() - m["away_score"].to_numpy(),
                -MARGIN_CAP, MARGIN_CAP)
    reg = Ridge(alpha=RIDGE_ALPHA, fit_intercept=False)
    reg.fit(X, y)
    coefs = reg.coef_[:len(players)]
    return {int(p): float(c) for p, c in zip(players, coefs)}


def avail_diff(matches: pd.DataFrame, appearances: pd.DataFrame,
               values: dict, restrict_ids=None) -> pd.Series:
    """Σ(home lineup value) − Σ(away lineup value) per match, from the players who
    appeared (a leak-safe proxy for the named 17 in the backtest)."""
    app = appearances
    if restrict_ids is not None:
        app = app[app["match_id"].isin(restrict_ids)]
    app = app.assign(val=app["player_id"].map(values).fillna(0.0))
    signed = app.groupby("match_id").apply(
        lambda g: float((g["side"] * g["val"]).sum()), include_groups=False)
    return matches["match_id"].map(signed).fillna(0.0)


def walk_forward_avail(matches: pd.DataFrame, appearances: pd.DataFrame,
                       seasons) -> pd.Series:
    """avail_diff for each match in `seasons`, APM refit on an expanding window at
    each season boundary (strictly leak-free)."""
    out = pd.Series(0.0, index=matches.index)
    for yr in seasons:
        vals = fit_apm(appearances, matches, pd.Timestamp(f"{yr}-01-01"))
        if not vals:
            continue
        mask = matches["year"] == yr
        if mask.any():
            out.loc[mask] = avail_diff(matches.loc[mask], appearances, vals).values
    return out


def lineup_value(player_ids, values: dict) -> float:
    return float(sum(values.get(int(p), 0.0) for p in player_ids if pd.notna(p)))


def apply_avail(p_blend: float, avail_raw: float, beta: float,
                mu: float, sd: float) -> float:
    """Correct a base blend prob by the lineup-strength difference."""
    p = min(max(float(p_blend), 1e-6), 1 - 1e-6)
    z = np.log(p / (1 - p)) + beta * ((avail_raw - mu) / (sd or 1.0))
    return float(1 / (1 + np.exp(-z)))


def fit_offset_logistic(x: np.ndarray, y: np.ndarray, offset: np.ndarray,
                        l2: float = 8.0, iters: int = 60) -> float:
    """1-D offset logistic: p = sigmoid(offset + beta*x). Returns beta. Holds the
    base-blend offset fixed so availability can only correct it, never disturb it."""
    x = np.asarray(x, float); beta = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(offset + beta * x)))
        w = np.clip(p * (1 - p), 1e-6, None)
        grad = float(x @ (p - y)) + l2 * beta
        hess = float((x * w) @ x) + l2
        beta -= grad / hess
    return beta
