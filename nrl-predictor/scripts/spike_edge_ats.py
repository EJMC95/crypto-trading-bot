"""Gate: does a per-edge share redistribution sharpen edge-attacker (W/C/FB)
tryscorer prices?

Against a leaky-edge defence (high conceded line breaks + tackle breaks), shift
try-share toward the outside backs and away from middle forwards, renormalised so
the team total lambda — and therefore the match winner and SGM consistency — is
untouched. Ships only if it beats the base edge-attacker Brier on 2024-25 without
hurting the rest of the field.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features import player_rates, xstats_defence
from src.ingest import teams
from src.models.match_poisson import (PoissonParams, long_format,
                                      team_scoring_table, walk_forward)

PROCESSED = ROOT / "data" / "processed"
POIS_PARAMS = PoissonParams(decay_xi=1.4)


def main() -> None:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    pm = pd.read_parquet(PROCESSED / "player_matches.parquet")
    pm = pm[pm["match_id"].isin(matches["match_id"].dropna())]
    hist = player_rates.player_history(matches, pm, teams)
    long_rows = long_format(matches, team_scoring_table(pm, teams))

    print("== walk-forward tier-2 lambdas (2022+) ==")
    wf = walk_forward(matches, long_rows, POIS_PARAMS, start_year=2022)
    lam_map = {}
    for r in wf.dropna(subset=["lam_tries_home"]).itertuples(index=False):
        lam_map[(r.match_id, r.home_id)] = r.lam_tries_home
        lam_map[(r.match_id, r.away_id)] = r.lam_tries_away

    print("== edge-leak ratings + gamma gate ==")
    ratings = xstats_defence.build_ratings()
    norm = xstats_defence.league_norm(ratings)
    g = xstats_defence.fit_and_gate_edge(matches, hist, lam_map, ratings, norm)

    print(f"  fitted gamma = {g['gamma']:+.3f}")
    print(f"  edge-attacker holdout player-games: {g['n_edge_holdout']}")
    print(f"  base   edge Brier {g['brier_edge_base']:.4f}")
    print(f"  + edge      Brier {g['brier_edge_x']:.4f}")
    print(f"\n  edge redistribution {'BEATS' if g['passed'] else 'does NOT beat'} "
          f"the base on edge-attacker prices (field not hurt).")


if __name__ == "__main__":
    main()
