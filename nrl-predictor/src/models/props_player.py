"""Anytime-tryscorer (ATS) probabilities linked to the match model (Build Spec §5).

The link that makes SGM correlation modelling possible: the team's expected try
count λ_team comes from the tier-2 match model, and each named player takes a
share s_i = rate_i / Σ_squad rate_j of it. Player tries are then
Poisson(s_i · λ_team) (thinning), so

    P(anytime try) = 1 - exp(-s_i · λ_team)

which moves with the matchup: the same winger has a higher ATS at home to a leaky
defence than away to the champions — exactly the correlation the SGM simulator
exploits.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import player_rates


def match_player_lambdas(hist: pd.DataFrame, rates: pd.DataFrame,
                         team_id: str, lam_team: float,
                         asof: pd.Timestamp) -> pd.DataFrame:
    """Per-player expected tries for one side of one match."""
    squad = player_rates.squad_asof(hist, team_id, asof)
    if squad.empty or not np.isfinite(lam_team):
        return pd.DataFrame(columns=["player_id", "position", "share", "lam", "p_ats"])
    sq = squad.merge(rates[["player_id", "rate"]], on="player_id", how="left")
    # players with no rate row (debutants inside the window) get the positional prior
    pri = player_rates.positional_priors(hist, asof)["rate"]
    sq["rate"] = sq["rate"].fillna(sq["position"].map(pri)).fillna(pri.mean())
    sq["share"] = sq["rate"] / sq["rate"].sum()
    sq["lam"] = sq["share"] * lam_team
    sq["p_ats"] = 1 - np.exp(-sq["lam"])
    return sq[["player_id", "position", "share", "lam", "p_ats"]]
