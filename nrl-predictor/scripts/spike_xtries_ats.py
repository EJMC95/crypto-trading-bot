"""Gate: does an xStats opponent-defence correction to lam_team sharpen the
tryscorer (ATS) prices?

Uses the same shared implementation production runs (xstats_defence.fit_and_gate):
replace lam_team with lam_adj = lam_base * multiplier(zdef_opp, zatt_team), where
the correction is an offset fit (log lam_base as a fixed offset) learned on
2022-2023 and evaluated on 2024-2025. Ships only if the corrected model's ATS
Brier beats the base on the holdout — the same discipline used for availability
(shipped) and xForm (gated out).
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
EVAL_YEARS = range(2022, 2026)


def main() -> None:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    pm = pd.read_parquet(PROCESSED / "player_matches.parquet")
    pm = pm[pm["match_id"].isin(matches["match_id"].dropna())]
    hist = player_rates.player_history(matches, pm, teams)
    long_rows = long_format(matches, team_scoring_table(pm, teams))

    print("== walk-forward tier-2 lambdas (2022+) ==")
    wf = walk_forward(matches, long_rows, POIS_PARAMS, start_year=min(EVAL_YEARS))
    lam_map = {}
    for r in wf.dropna(subset=["lam_tries_home"]).itertuples(index=False):
        lam_map[(r.match_id, r.home_id)] = r.lam_tries_home
        lam_map[(r.match_id, r.away_id)] = r.lam_tries_away

    print("== xStats defence/attack ratings + offset gate ==")
    ratings = xstats_defence.build_ratings()
    norm = xstats_defence.league_norm(ratings)
    g = xstats_defence.fit_and_gate(matches, hist, lam_map, ratings, norm)

    print(f"  offset fit: beta_def={g['coef']['beta_def']:+.3f} "
          f"beta_att={g['coef']['beta_att']:+.3f}")
    print(f"\n  holdout player-games (2024-25): {g['n_holdout']}")
    print(f"  base model    Brier {g['brier_base']:.4f}  log loss {g['logloss_base']:.4f}")
    print(f"  + xStats def  Brier {g['brier_x']:.4f}  log loss {g['logloss_x']:.4f}")
    print(f"\n  xStats defence correction {'BEATS' if g['passed'] else 'does NOT beat'} "
          f"the base tryscorer model on the holdout.")


if __name__ == "__main__":
    main()
