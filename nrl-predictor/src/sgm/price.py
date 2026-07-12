"""SGM pricing on the joint simulation (Build Spec §6).

Legs are boolean masks over the same simulated worlds; a combo's joint probability
is the mean of the AND of its masks. Fair price = 1/p_joint. The "independence
price" multiplies the marginal leg probabilities — the gap between the two is the
correlation the bookmaker's engine mostly ignores (the edge thesis).

Quoted prices: no odds API key is needed for h2h, but bookie SGM quotes aren't on
any public feed — paste them into data/manual_odds/round{NN}.csv with columns
    home_id,away_id,legs,quoted_price
where `legs` is ';'-joined leg specs (below). The Odds API path is stubbed behind
ODDS_API_KEY in .env for whenever a key exists.

Leg spec grammar (case-insensitive):
    home_win | away_win
    line <team_id> <handicap>          e.g.  line MEL -6.5
    total over|under <points>          e.g.  total over 44.5
    tries_total over|under <n>         match tries, e.g. tries_total over 6.5
    team_tries <team_id> over|under <n>  e.g. team_tries MEL over 3.5
    ats <player_id>                    anytime tryscorer
    tries2+ <player_id>                2+ tries
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MANUAL_DIR = ROOT / "data" / "manual_odds"


def leg_mask(sims: dict, spec: str) -> np.ndarray:
    parts = spec.strip().lower().split()
    margin = sims["margin"]
    if parts[0] == "home_win":
        return margin > 0
    if parts[0] == "away_win":
        return margin < 0
    if parts[0] == "line":
        team, hcap = parts[1].upper(), float(parts[2])
        side_margin = margin if team == str(sims["home_id"]) else -margin
        return side_margin + hcap > 0
    if parts[0] == "margin_band":
        # margin_band <team> <lo> <hi>  — team wins by lo..hi inclusive
        team, lo, hi = parts[1].upper(), float(parts[2]), float(parts[3])
        side_margin = margin if team == str(sims["home_id"]) else -margin
        return (side_margin >= lo) & (side_margin <= hi)
    if parts[0] == "total":
        pts = float(parts[2])
        return sims["total"] > pts if parts[1] == "over" else sims["total"] < pts
    if parts[0] == "tries_total":
        n = float(parts[2])
        tt = sims["home_tries"] + sims["away_tries"]
        return tt > n if parts[1] == "over" else tt < n
    if parts[0] == "team_tries":
        team, direction, n = parts[1].upper(), parts[2], float(parts[3])
        side = "home" if team == str(sims["home_id"]) else "away"
        tt = sims[f"{side}_tries"]
        return tt > n if direction == "over" else tt < n
    if parts[0] in ("ats", "tries2+"):
        pid = int(parts[1])
        thresh = 1 if parts[0] == "ats" else 2
        for side in ("home", "away"):
            ids = sims[f"{side}_player_ids"]
            hit = np.where(ids == pid)[0]
            if len(hit):
                return sims[f"{side}_player_tries"][:, hit[0]] >= thresh
        raise KeyError(f"player {pid} not in this match's squads")
    raise ValueError(f"unknown leg spec: {spec}")


def price_combo(sims: dict, legs: list[str]) -> dict:
    masks = [leg_mask(sims, l) for l in legs]
    marginals = [float(m.mean()) for m in masks]
    joint = float(np.logical_and.reduce(masks).mean())
    independent = float(np.prod(marginals))
    return {
        "legs": legs,
        "leg_probs": [round(p, 4) for p in marginals],
        "p_joint": round(joint, 4),
        "fair_price": round(1 / joint, 2) if joint > 0 else np.inf,
        "p_independent": round(independent, 4),
        "correlation_lift": round(joint / independent, 3) if independent > 0 else np.nan,
    }


def manual_quotes(round_no: int) -> pd.DataFrame:
    path = MANUAL_DIR / f"round{round_no:02d}.csv"
    if not path.exists():
        return pd.DataFrame(columns=["home_id", "away_id", "legs", "quoted_price"])
    return pd.read_csv(path)


def evaluate_quotes(sims_by_match: dict, round_no: int) -> pd.DataFrame:
    """Price every manually-pasted SGM quote for the round; EV after margin."""
    rows = []
    for q in manual_quotes(round_no).itertuples(index=False):
        sims = sims_by_match.get((q.home_id, q.away_id))
        if sims is None:
            continue
        res = price_combo(sims, q.legs.split(";"))
        rows.append({**res, "home_id": q.home_id, "away_id": q.away_id,
                     "quoted_price": q.quoted_price,
                     "ev_pct": round((res["p_joint"] * q.quoted_price - 1) * 100, 1)})
    return pd.DataFrame(rows)


def odds_api_quotes(*_args, **_kwargs):
    """Stub: live SGM quotes via The Odds API once a key exists in .env."""
    if not os.environ.get("ODDS_API_KEY"):
        raise RuntimeError("ODDS_API_KEY not set — use the manual-quotes CSV path")
    raise NotImplementedError("wire when a key exists (Phase 5)")
