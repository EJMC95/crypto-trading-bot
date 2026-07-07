"""Walk-forward backtest + calibration (Build Spec §7).

Design
------
Elo is inherently sequential: every prediction only uses matches strictly before
kickoff, so replaying the history in date order IS the walk-forward. The only place
leakage could sneak in is parameter choice, so hyper-parameters are grid-searched on
predictions made in TUNE_YEARS only, then frozen for the EVAL_YEARS evaluation.

Benchmarks
----------
- naive: expanding home-win rate over all prior matches (the "always back the home
  side at the base rate" strawman the phase-1 gate is measured against).
- market: de-vigged bookmaker closing line from the aussportsbetting file, joined on
  (date±1day, home_id, away_id). The join tolerance covers timezone/day-of-listing
  drift between the two sources.

Draws score as 0.5 (both Brier and log loss use the half-credit form).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from ..models.match_elo import EloParams, run_elo

BURN_IN_YEARS = 3          # first seasons after MODEL_START_YEAR excluded from scoring
TUNE_YEARS = range(2006, 2015)
EVAL_YEARS = range(2015, 2026)

# scale is pinned at the conventional 400: it is redundant with K (both shrink
# confidence), so tuning both lets the optimizer wander a flat ridge to the grid
# edge. Residual mis-confidence is handled by the Platt calibrator.
# Note the raw K looks small next to the spec's "K≈30–40" because the MOV
# multiplier (ln(1+margin), avg ≈ 2.5) scales it per game: effective K ≈ k × MOV.
# The tuning surface is very flat (top candidates within ~0.001 log loss), so the
# argmax alone chases noise to the grid edge; see the one-SE-style rule in tune().
GRID = {
    "k": [10.0, 13.0, 16.0, 20.0, 24.0],
    "home_adv": [50.0, 60.0, 70.0, 80.0],
    "regress": [0.25, 0.33, 0.40, 0.50],
    "scale": [400.0],
    "mov_cap": [2.0, 2.5, 3.0],
}
TUNE_TOLERANCE = 0.0015  # log-loss band treated as a tie


def outcome(df: pd.DataFrame) -> np.ndarray:
    margin = df["home_score"].to_numpy() - df["away_score"].to_numpy()
    return np.where(margin > 0, 1.0, np.where(margin < 0, 0.0, 0.5))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def naive_baseline(matches: pd.DataFrame) -> np.ndarray:
    """Expanding pre-match home-win rate (draws count half); leak-free by shift."""
    y = outcome(matches)
    wins = pd.Series(y).shift().expanding().mean()
    return wins.fillna(0.55).to_numpy()


def tune(matches: pd.DataFrame) -> tuple[EloParams, pd.DataFrame]:
    tune_mask = matches["year"].isin(TUNE_YEARS).to_numpy()
    y = outcome(matches)[tune_mask]
    rows = []
    for k, ha, rg, sc, cap in itertools.product(*GRID.values()):
        params = EloParams(k=k, home_adv=ha, regress=rg, scale=sc, mov_cap=cap)
        p = run_elo(matches, params)["p_home"].to_numpy()[tune_mask]
        rows.append({"k": k, "home_adv": ha, "regress": rg, "scale": sc,
                     "mov_cap": cap, "log_loss": log_loss(p, y), "brier": brier(p, y)})
    grid = pd.DataFrame(rows).sort_values("log_loss").reset_index(drop=True)
    # One-SE-style rule: everything within TUNE_TOLERANCE of the best log loss is a
    # tie; break ties toward the most conservative model (least regression, least
    # MOV amplification, least reactive K) so noise can't drag us to a grid edge.
    tied = grid[grid["log_loss"] <= grid["log_loss"].iloc[0] + TUNE_TOLERANCE]
    pick = tied.sort_values(["regress", "mov_cap", "k"]).iloc[0]
    best = EloParams(k=float(pick["k"]), home_adv=float(pick["home_adv"]),
                     regress=float(pick["regress"]), scale=float(pick["scale"]),
                     mov_cap=float(pick["mov_cap"]))
    return best, grid


def attach_market(matches: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    """Left-join de-vigged market probs onto matches with a ±1 day tolerance."""
    m = matches.copy()
    m["date_d"] = pd.to_datetime(m["date"]).dt.normalize()
    o = odds[["date", "home_id", "away_id", "market_p_home", "odds_is_closing"]].copy()
    o["date_d"] = pd.to_datetime(o["date"]).dt.normalize()
    o = o.drop(columns=["date"]).drop_duplicates(["date_d", "home_id", "away_id"])
    merged = m.merge(o, on=["date_d", "home_id", "away_id"], how="left")
    for shift in (1, -1):
        missing = merged["market_p_home"].isna()
        if not missing.any():
            break
        o2 = o.copy()
        o2["date_d"] = o2["date_d"] + pd.Timedelta(days=shift)
        fill = (
            m.loc[missing.to_numpy()]
            .merge(o2, on=["date_d", "home_id", "away_id"], how="left")
        )
        merged.loc[missing, ["market_p_home", "odds_is_closing"]] = fill[
            ["market_p_home", "odds_is_closing"]
        ].to_numpy()
    return merged.drop(columns=["date_d"])


class PlattCalibrator:
    """Logistic (Platt) recalibration on logit(p) — smooth and low-variance, unlike
    isotonic which overfits step functions on ~1,800 tuning games. Draw outcomes
    (0.5) are split into one win and one loss observation with half weight each.
    """

    def __init__(self) -> None:
        self.lr = LogisticRegression(C=1e6)

    @staticmethod
    def _logit(p: np.ndarray) -> np.ndarray:
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p)).reshape(-1, 1)

    def fit(self, p: np.ndarray, y: np.ndarray) -> "PlattCalibrator":
        x = self._logit(p)
        draws = y == 0.5
        x_fit = np.vstack([x[~draws], x[draws], x[draws]])
        y_fit = np.concatenate([y[~draws], np.ones(draws.sum()), np.zeros(draws.sum())])
        w = np.concatenate([np.ones((~draws).sum()), np.full(2 * draws.sum(), 0.5)])
        self.lr.fit(x_fit, y_fit, sample_weight=w)
        return self

    def predict(self, p) -> np.ndarray:
        return self.lr.predict_proba(self._logit(np.asarray(p, dtype=float)))[:, 1]


def fit_calibrator(p: np.ndarray, y: np.ndarray) -> PlattCalibrator:
    return PlattCalibrator().fit(p, y)


def season_table(df: pd.DataFrame, prob_cols: dict[str, str]) -> pd.DataFrame:
    """Per-season Brier/log-loss for each named probability column."""
    y_all = outcome(df)
    rows = []
    for year, grp in df.assign(_y=y_all).groupby("year"):
        row = {"year": int(year), "games": len(grp)}
        for label, col in prob_cols.items():
            mask = grp[col].notna()
            p, y = grp.loc[mask, col].to_numpy(), grp.loc[mask, "_y"].to_numpy()
            row[f"brier_{label}"] = brier(p, y) if len(p) else np.nan
            row[f"logloss_{label}"] = log_loss(p, y) if len(p) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def reliability_table(p: np.ndarray, y: np.ndarray, bins: int = 10) -> pd.DataFrame:
    cut = pd.cut(p, np.linspace(0, 1, bins + 1), include_lowest=True)
    df = pd.DataFrame({"bin": cut, "p": p, "y": y})
    out = df.groupby("bin", observed=True).agg(n=("y", "size"), mean_pred=("p", "mean"),
                                               mean_obs=("y", "mean"))
    return out.reset_index()
