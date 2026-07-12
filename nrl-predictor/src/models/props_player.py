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


H2H_PRIOR_GAMES = 6.0  # shrinkage strength for the player-vs-opponent nudge


def match_player_lambdas(hist: pd.DataFrame, rates: pd.DataFrame,
                         team_id: str, lam_team: float, asof: pd.Timestamp,
                         named_squad: pd.DataFrame | None = None,
                         opp_id: str | None = None) -> pd.DataFrame:
    """Per-player expected tries for one side of one match.

    named_squad: optional confirmed team list [player_id, position] — REPLACES the
    last-game squad proxy (on-the-day signal doing real work).
    opp_id: when given, each player's try rate is nudged toward his record against
    THIS opponent via an empirical-Bayes update (career rate as a prior of strength
    H2H_PRIOR_GAMES, updated by the head-to-head games). Small samples stay close to
    the career rate; a strong/weak record vs the opponent shifts the try-share.
    """
    squad = (named_squad[["player_id", "position"]].dropna(subset=["player_id"]).copy()
             if named_squad is not None and len(named_squad)
             else player_rates.squad_asof(hist, team_id, asof))
    if squad.empty or not np.isfinite(lam_team):
        return pd.DataFrame(columns=["player_id", "position", "share", "lam", "p_ats",
                                     "h2h_games", "h2h_tries"])
    sq = squad.merge(rates[["player_id", "rate"]], on="player_id", how="left")
    pri = player_rates.positional_priors(hist, asof)["rate"]
    sq["rate"] = sq["rate"].fillna(sq["position"].map(pri)).fillna(pri.mean())

    sq["h2h_games"], sq["h2h_tries"] = 0, 0
    if opp_id is not None:
        h2h = player_rates.vs_opponent(hist, sq["player_id"].dropna(), opp_id, asof)
        adj, hg, ht = [], [], []
        for pid, base in zip(sq["player_id"], sq["rate"]):
            rec = h2h.get(int(pid)) if pd.notna(pid) else None
            if rec and rec["games"]:
                r = (H2H_PRIOR_GAMES * base + rec["tries"]) / (H2H_PRIOR_GAMES + rec["games"])
                adj.append(r); hg.append(rec["games"]); ht.append(rec["tries"])
            else:
                adj.append(base); hg.append(0); ht.append(0)
        sq["rate"], sq["h2h_games"], sq["h2h_tries"] = adj, hg, ht

    sq["share"] = sq["rate"] / sq["rate"].sum()
    sq["lam"] = sq["share"] * lam_team
    sq["p_ats"] = 1 - np.exp(-sq["lam"])
    return sq[["player_id", "position", "share", "lam", "p_ats", "h2h_games", "h2h_tries"]]
