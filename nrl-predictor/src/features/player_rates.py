"""Per-player try rates — hierarchical Poisson-gamma with positional pooling
(Build Spec §5 "Player props").

rate_i(t) = (alpha_pos + Σ w·tries_i) / (beta_pos + Σ w·games_i)

- Positional Gamma priors fit by method of moments on all player-seasons strictly
  before `asof` — low-sample players shrink to their position's prior.
- Recency weights w = exp(-ξ·age_years) with the same decay the match model tuned
  (ξ=1.4), so player form and team form age consistently.
- No minutes data in the current sources (fantasy feed is the Phase-5 upgrade
  path), so rates are per-game with position implicitly carrying expected-minutes
  differences (a bench prior ≠ a winger prior).

All functions take `asof` and only look backward — walk-forward safe by
construction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DECAY_XI = 1.4
PRIOR_STRENGTH_GAMES = 12.0  # beta: pseudo-games a player must play to escape the prior


def player_history(matches: pd.DataFrame, player_matches: pd.DataFrame,
                   teams_mod) -> pd.DataFrame:
    """One row per player-match with date/team/position/tries, modeling era only."""
    pm = player_matches[player_matches["match_id"].isin(matches["match_id"].dropna())].copy()
    pm["team_id"] = teams_mod.to_canonical(pm["team"], "player_match_data")
    dates = matches[["match_id", "date"]]
    out = pm.merge(dates, on="match_id")
    out["tries_all"] = out["tries"].fillna(0) + out["penalty_tries"].fillna(0)
    return out[["player_id", "match_id", "team_id", "position", "date", "tries_all"]]


def positional_priors(hist: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Gamma(alpha, beta) per position from data strictly before asof."""
    h = hist[hist["date"] < asof]
    g = h.groupby("position").agg(tries=("tries_all", "sum"), games=("tries_all", "size"))
    g["rate"] = g["tries"] / g["games"]
    g["beta"] = PRIOR_STRENGTH_GAMES
    g["alpha"] = g["rate"] * g["beta"]
    return g[["alpha", "beta", "rate"]]


def rates_asof(hist: pd.DataFrame, asof: pd.Timestamp,
               window_years: float = 4.0) -> pd.DataFrame:
    """Posterior try rate per (player, dominant recent position) as of a date."""
    h = hist[hist["date"] < asof].copy()
    age = (asof - h["date"]).dt.days / 365.25
    h = h[age <= window_years]
    age = age.loc[h.index]
    h["w"] = np.exp(-DECAY_XI * age)

    pri = positional_priors(hist, asof)
    # dominant recent position = weighted modal position
    pos = (h.groupby(["player_id", "position"])["w"].sum()
             .reset_index().sort_values("w", ascending=False)
             .drop_duplicates("player_id")[["player_id", "position"]])
    agg = h.groupby("player_id").agg(
        w_tries=("tries_all", lambda s: float(np.sum(s * h.loc[s.index, "w"]))),
        w_games=("w", "sum"), last_team=("team_id", "last"), last_date=("date", "max"))
    agg = agg.merge(pos, on="player_id").merge(pri, on="position", how="left")
    agg["rate"] = (agg["alpha"] + agg["w_tries"]) / (agg["beta"] + agg["w_games"])
    return agg[["player_id", "position", "last_team", "last_date", "w_games", "rate"]]


def squad_asof(hist: pd.DataFrame, team_id: str, asof: pd.Timestamp) -> pd.DataFrame:
    """The 17 named in the team's most recent game before asof — the best lineup
    proxy until Tuesday team lists are ingested (Phase 5)."""
    h = hist[(hist["team_id"] == team_id) & (hist["date"] < asof)]
    if h.empty:
        return pd.DataFrame(columns=["player_id", "position"])
    last = h[h["date"] == h["date"].max()]
    return last[["player_id", "position"]].drop_duplicates("player_id")
