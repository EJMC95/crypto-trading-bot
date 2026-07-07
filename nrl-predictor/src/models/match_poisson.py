"""Tier-2 Poisson scoring model (Build Spec §5).

Tries per team ~ Poisson with log-linear attack_i + defence_j + home effects, fitted
by L2-regularised Poisson regression with Dixon–Coles exponential time-decay weights
(recent form dominates). NRL points are then assembled the way the game actually
scores them — 4·tries + 2·conversions + 2·penalty goals + 1·field goal — with
conversions Binomial(tries, p_conv) and penalty/field goals small Poissons, all
estimated on the same weighted window. Monte Carlo over that generative model gives
the full joint (home_score, away_score) distribution → win prob, margin (Skellam-
style), and totals from one object.

Try counts come from aggregating player_match_data (validated: scores reconstruct
exactly). The handful of very recent games without player data still contribute to
nothing here — they are simply absent from the fit window, which the decay makes
immaterial.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

RNG = np.random.default_rng(140281)


@dataclass
class PoissonParams:
    decay_xi: float = 1.0      # per-year decay rate for match weights
    window_years: float = 5.0  # only fit on matches this recent
    alpha: float = 0.5         # L2 strength for attack/defence effects
    n_sims: int = 20000


class TryModel:
    """One fitted snapshot: predicts any pairing as of its fit date."""

    def __init__(self, params: PoissonParams):
        self.params = params

    def fit(self, rows: pd.DataFrame, asof: pd.Timestamp) -> "TryModel | None":
        """rows: long format, one row per team-match with columns
        date, team_id, opp_id, is_home, tries, goals, fg1, fg2."""
        p = self.params
        age = (asof - rows["date"]).dt.days / 365.25
        keep = (age >= 0) & (age <= p.window_years)
        rows, age = rows[keep], age[keep]
        if len(rows) < 200:
            return None
        w = np.exp(-p.decay_xi * age.to_numpy())

        self.teams_ = sorted(set(rows["team_id"]) | set(rows["opp_id"]))
        tidx = {t: i for i, t in enumerate(self.teams_)}
        n, nt = len(rows), len(self.teams_)
        X = np.zeros((n, 2 * nt + 1))
        X[np.arange(n), rows["team_id"].map(tidx)] = 1.0            # attack
        X[np.arange(n), nt + rows["opp_id"].map(tidx).to_numpy()] = 1.0  # defence
        X[:, -1] = rows["is_home"].to_numpy(dtype=float)             # home boost
        self.reg_ = PoissonRegressor(alpha=p.alpha, max_iter=300)
        self.reg_.fit(X, rows["tries"].to_numpy(), sample_weight=w)
        self._tidx = tidx

        # Score-assembly nuisance rates from the same weighted window.
        tries_sum = float(np.sum(w * rows["tries"]))
        goals_sum = float(np.sum(w * rows["goals"]))
        self.lam_pg_ = 0.25  # penalty goals per team-game (stable across eras)
        self.p_conv_ = float(np.clip((goals_sum - self.lam_pg_ * w.sum()) / max(tries_sum, 1e-9), 0.5, 0.85))
        self.lam_fg1_ = float(np.sum(w * rows["fg1"]) / w.sum())
        self.lam_fg2_ = float(np.sum(w * rows["fg2"]) / w.sum())
        return self

    def try_rate(self, team: str, opp: str, home: bool) -> float:
        nt = len(self.teams_)
        x = np.zeros((1, 2 * nt + 1))
        if team not in self._tidx or opp not in self._tidx:
            return np.nan
        x[0, self._tidx[team]] = 1.0
        x[0, nt + self._tidx[opp]] = 1.0
        x[0, -1] = float(home)
        return float(self.reg_.predict(x)[0])

    def _sim_scores(self, lam: float, size: int) -> np.ndarray:
        t = RNG.poisson(lam, size)
        conv = RNG.binomial(t, self.p_conv_)
        pg = RNG.poisson(self.lam_pg_, size)
        fg1 = RNG.poisson(self.lam_fg1_, size)
        fg2 = RNG.poisson(self.lam_fg2_, size)
        return 4 * t + 2 * conv + 2 * pg + fg1 + 2 * fg2

    def predict_match(self, home: str, away: str) -> dict | None:
        lam_h = self.try_rate(home, away, True)
        lam_a = self.try_rate(away, home, False)
        if np.isnan(lam_h) or np.isnan(lam_a):
            return None
        hs = self._sim_scores(lam_h, self.params.n_sims)
        as_ = self._sim_scores(lam_a, self.params.n_sims)
        margin = hs - as_
        return {
            "p_home": float(np.mean(margin > 0) + 0.5 * np.mean(margin == 0)),
            "exp_margin": float(np.mean(margin)),
            "median_margin": float(np.median(margin)),
            "exp_total": float(np.mean(hs + as_)),
            "lam_tries_home": lam_h, "lam_tries_away": lam_a,
        }


def long_format(matches: pd.DataFrame, team_scoring: pd.DataFrame) -> pd.DataFrame:
    """matches + per-team scoring detail -> one row per team-match."""
    sides = []
    for side, opp in (("home", "away"), ("away", "home")):
        s = matches.merge(
            team_scoring.rename(columns={"team_id": f"{side}_id"}),
            on=["match_id", f"{side}_id"], how="inner",
        )
        sides.append(pd.DataFrame({
            "date": s["date"], "match_id": s["match_id"],
            "team_id": s[f"{side}_id"], "opp_id": s[f"{opp}_id"],
            "is_home": side == "home",
            "tries": s["tries"] + s["pen_tries"], "goals": s["goals"],
            "fg1": s["fg1"], "fg2": s["fg2"],
        }))
    return pd.concat(sides, ignore_index=True).sort_values("date").reset_index(drop=True)


def team_scoring_table(player_matches: pd.DataFrame, teams_mod) -> pd.DataFrame:
    pm = player_matches.copy()
    pm["team_id"] = teams_mod.to_canonical(pm["team"], "player_match_data")
    return pm.groupby(["match_id", "team_id"], as_index=False).agg(
        tries=("tries", "sum"), pen_tries=("penalty_tries", "sum"),
        goals=("goals", "sum"), fg1=("field_goals", "sum"), fg2=("field_goals2", "sum"),
    )


def walk_forward(matches: pd.DataFrame, long_rows: pd.DataFrame,
                 params: PoissonParams, start_year: int) -> pd.DataFrame:
    """Refit before every round from start_year on; predict that round's games.

    Returns matches with p_pois / exp_margin / exp_total columns (NaN pre-start).
    """
    out = matches.copy()
    for col in ("p_pois", "pois_margin", "pois_total"):
        out[col] = np.nan
    target = out[out["year"] >= start_year]
    for (yr, rnd), grp in target.groupby(["year", "round"], sort=False):
        asof = grp["date"].min()
        model = TryModel(params).fit(long_rows[long_rows["date"] < asof], asof)
        if model is None:
            continue
        for idx, row in grp.iterrows():
            pred = model.predict_match(row["home_id"], row["away_id"])
            if pred:
                out.loc[idx, ["p_pois", "pois_margin", "pois_total"]] = (
                    pred["p_home"], pred["exp_margin"], pred["exp_total"])
    return out
