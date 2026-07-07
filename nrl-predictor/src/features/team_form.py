"""Leak-free per-match team-form features (Build Spec §5 Tier 3).

Everything here is computed from matches strictly before the row's own kickoff
(shifted expanding/EWMA state carried per team). Features:

- ewma_pf5/pf10, ewma_pa5/pa10 — EWMA points for/against, half-lives 5 & 10 games
- rest_days                    — days since the team's previous match (capped 21)
- origin_flag                  — May–July mid-season window (rep-round disruption);
  a calendar approximation of the Origin period, good enough until team lists land
  in Phase 5
- gbm feature frame            — home-minus-away differentials + model probabilities

Not yet included (need sources wired in later phases): travel km (no venue coords in
the current data), weather (Open-Meteo lives in Phase 5 automation), named team
lists.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HL5 = np.log(2) / 5
HL10 = np.log(2) / 10


def _team_state_features(matches: pd.DataFrame) -> pd.DataFrame:
    """Per (match, side) EWMA and rest-day state, strictly pre-kickoff."""
    state: dict[str, dict] = {}
    rows = {k: [] for k in
            ("h_pf5", "h_pa5", "h_pf10", "h_pa10", "h_rest",
             "a_pf5", "a_pa5", "a_pf10", "a_pa10", "a_rest")}

    def snapshot(team, date, prefix):
        s = state.get(team)
        if s is None or s["n"] == 0:
            vals = (np.nan,) * 4 + (14.0,)
        else:
            rest = min((date - s["last_date"]).days, 21)
            vals = (s["pf5"], s["pa5"], s["pf10"], s["pa10"], float(rest))
        for key, v in zip(("pf5", "pa5", "pf10", "pa10", "rest"), vals):
            rows[f"{prefix}_{key}"].append(v)

    def update(team, date, pf, pa):
        s = state.setdefault(team, {"pf5": pf, "pa5": pa, "pf10": pf, "pa10": pa,
                                    "n": 0, "last_date": date})
        for key, hl, val in (("pf5", HL5, pf), ("pa5", HL5, pa),
                             ("pf10", HL10, pf), ("pa10", HL10, pa)):
            a = 1 - np.exp(-hl)
            s[key] = (1 - a) * s[key] + a * val
        s["n"] += 1
        s["last_date"] = date

    for r in matches.sort_values("date").itertuples(index=False):
        snapshot(r.home_id, r.date, "h")
        snapshot(r.away_id, r.date, "a")
        update(r.home_id, r.date, r.home_score, r.away_score)
        update(r.away_id, r.date, r.away_score, r.home_score)

    return pd.DataFrame(rows, index=matches.sort_values("date").index).sort_index()


def build_features(matches: pd.DataFrame) -> pd.DataFrame:
    """GBM feature frame aligned to `matches` (which must carry p_home from Elo
    and optionally p_pois from the Poisson walk-forward)."""
    st = _team_state_features(matches)
    f = pd.DataFrame(index=matches.index)
    f["elo_p"] = matches["p_home"]
    if "p_pois" in matches:
        f["pois_p"] = matches["p_pois"]
        f["pois_margin"] = matches["pois_margin"]
        f["pois_total"] = matches["pois_total"]
    f["ewma_pf5_diff"] = st["h_pf5"] - st["a_pf5"]
    f["ewma_pa5_diff"] = st["h_pa5"] - st["a_pa5"]
    f["ewma_pf10_diff"] = st["h_pf10"] - st["a_pf10"]
    f["ewma_pa10_diff"] = st["h_pa10"] - st["a_pa10"]
    f["rest_diff"] = st["h_rest"] - st["a_rest"]
    f["rest_home"] = st["h_rest"]
    month = pd.to_datetime(matches["date"]).dt.month
    f["origin_flag"] = month.isin([5, 6, 7]).astype(int)
    f["is_finals"] = matches["is_finals"].fillna(False).astype(int)
    return f
