"""Tier-1 Elo match model (Build Spec §5).

- Update: R' = R + K * mov_mult(margin, elo_diff) * (result - expected)
- MOV multiplier: FiveThirtyEight-style ln(1 + margin) damped when the winner was
  already the Elo favourite, capped so blowouts don't distort.
- Home advantage: additive Elo offset, fitted (not assumed) on the tuning window.
- Pre-season regression: each team pulled `regress` of the way back to the 1500 mean.
- Win probability: logistic in the adjusted Elo difference; the logistic scale is a
  fitted parameter (calibration knob) rather than the chess-default 400.

Draws (rare post golden point) score as 0.5.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MEAN_RATING = 1500.0
NEW_TEAM_RATING = 1440.0  # expansion sides start below the pack


@dataclass
class EloParams:
    k: float = 34.0
    home_adv: float = 50.0     # Elo points added to the home side
    regress: float = 0.30      # pre-season pull toward the mean
    scale: float = 400.0       # logistic denominator
    mov_cap: float = 2.5       # cap on the MOV multiplier


@dataclass
class EloModel:
    params: EloParams = field(default_factory=EloParams)
    ratings: dict[str, float] = field(default_factory=dict)
    last_year: int | None = None

    def rating(self, team: str) -> float:
        if team not in self.ratings:
            self.ratings[team] = NEW_TEAM_RATING
        return self.ratings[team]

    def _preseason(self, year: int) -> None:
        if self.last_year is not None and year != self.last_year:
            r, p = self.ratings, self.params
            for t in r:
                r[t] = r[t] + p.regress * (MEAN_RATING - r[t])
        self.last_year = year

    def p_home(self, home: str, away: str, neutral: bool = False) -> float:
        p = self.params
        diff = self.rating(home) - self.rating(away) + (0 if neutral else p.home_adv)
        return 1.0 / (1.0 + 10.0 ** (-diff / p.scale))

    def _mov_mult(self, margin: float, winner_elo_diff: float) -> float:
        # winner_elo_diff: (winner - loser) adjusted Elo diff; damps K when the
        # favourite piles on (autocorrelation guard), boosts upsets slightly.
        mult = np.log1p(abs(margin)) * (2.2 / (winner_elo_diff * 0.001 + 2.2))
        return float(min(mult, self.params.mov_cap))

    def update(self, home: str, away: str, home_score: float, away_score: float,
               year: int, neutral: bool = False) -> float:
        """Process one match chronologically; returns the pre-match p_home."""
        self._preseason(year)
        p = self.params
        p_h = self.p_home(home, away, neutral)
        margin = home_score - away_score
        result = 0.5 if margin == 0 else (1.0 if margin > 0 else 0.0)

        adj_diff = self.rating(home) - self.rating(away) + (0 if neutral else p.home_adv)
        winner_elo_diff = adj_diff if margin > 0 else -adj_diff
        mult = 1.0 if margin == 0 else self._mov_mult(margin, winner_elo_diff)

        delta = p.k * mult * (result - p_h)
        self.ratings[home] = self.rating(home) + delta
        self.ratings[away] = self.rating(away) - delta
        return p_h


def run_elo(matches: pd.DataFrame, params: EloParams) -> pd.DataFrame:
    """Replay matches chronologically; return the frame with pre-match p_home."""
    model = EloModel(params=params)
    preds = np.empty(len(matches))
    it = matches[["home_id", "away_id", "home_score", "away_score", "year"]].itertuples(index=False)
    for i, (h, a, hs, as_, yr) in enumerate(it):
        preds[i] = model.update(h, a, hs, as_, int(yr))
    out = matches.copy()
    out["p_home"] = preds
    return out


def final_ratings(matches: pd.DataFrame, params: EloParams) -> tuple[EloModel, pd.DataFrame]:
    model = EloModel(params=params)
    for h, a, hs, as_, yr in matches[
        ["home_id", "away_id", "home_score", "away_score", "year"]
    ].itertuples(index=False):
        model.update(h, a, hs, as_, int(yr))
    table = (
        pd.DataFrame(sorted(model.ratings.items(), key=lambda kv: -kv[1]),
                     columns=["team_id", "elo"])
    )
    return model, table
