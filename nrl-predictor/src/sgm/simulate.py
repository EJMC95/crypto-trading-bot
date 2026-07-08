"""Monte Carlo joint match simulation (Build Spec §6).

Simulates each match at PLAYER level so every leg is evaluated on the same
simulated worlds:

1. Player tries X_i ~ Poisson(s_i · λ_team) independently (Poisson thinning of the
   tier-2 team try rate — the sum ΣX_i is exactly Poisson(λ_team), so the team
   total in every world is consistent with its players).
2. Team score assembled the way the game scores: 4·T + 2·Binomial(T, p_conv)
   + 2·Poisson(penalty goals) + field goals — identical machinery to the tier-2
   match model.
3. Arrays persisted to data/processed/sgm/ so pricing re-runs are free.

Result: joint distributions over (result, margin, total, team tries, every named
player's try count) — positively-correlated SGM legs price correctly because they
are evaluated on the same worlds, not multiplied as if independent.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = ROOT / "data" / "processed" / "sgm"

N_SIMS = 50_000


def simulate_match(try_model, home_players: pd.DataFrame, away_players: pd.DataFrame,
                   home_id: str, away_id: str, n_sims: int = N_SIMS,
                   seed: int = 1408) -> dict:
    """home/away_players: frames from props_player.match_player_lambdas
    (player_id, lam). try_model: a fitted TryModel (for the score-assembly rates).
    Returns dict of arrays, all length n_sims."""
    rng = np.random.default_rng(seed)
    sims: dict = {"home_id": home_id, "away_id": away_id, "n_sims": n_sims}
    for side, players in (("home", home_players), ("away", away_players)):
        lam = players["lam"].to_numpy(dtype=float)
        x = rng.poisson(lam[None, :].repeat(n_sims, axis=0))  # (n_sims, n_players)
        tries = x.sum(axis=1)
        conv = rng.binomial(tries, try_model.p_conv_)
        pg = rng.poisson(try_model.lam_pg_, n_sims)
        fg1 = rng.poisson(try_model.lam_fg1_, n_sims)
        fg2 = rng.poisson(try_model.lam_fg2_, n_sims)
        sims[f"{side}_tries"] = tries
        sims[f"{side}_score"] = 4 * tries + 2 * conv + 2 * pg + fg1 + 2 * fg2
        sims[f"{side}_player_ids"] = players["player_id"].to_numpy()
        sims[f"{side}_player_tries"] = x
    sims["margin"] = sims["home_score"] - sims["away_score"]
    sims["total"] = sims["home_score"] + sims["away_score"]
    return sims


def save(sims: dict, season: int, round_no: int) -> Path:
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    path = SIM_DIR / f"{season}_r{round_no:02d}_{sims['home_id']}_{sims['away_id']}.npz"
    np.savez_compressed(path, **{k: v for k, v in sims.items() if not isinstance(v, str)},
                        home_id=sims["home_id"], away_id=sims["away_id"])
    return path


def load(season: int, round_no: int, home_id: str, away_id: str) -> dict:
    path = SIM_DIR / f"{season}_r{round_no:02d}_{home_id}_{away_id}.npz"
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}
