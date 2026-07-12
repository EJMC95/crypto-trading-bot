"""Spike: does an expected-points (xPoints) form rating add to the blend?

xPoints = a team's *deserved* score from underlying process stats (run metres,
line breaks, tackle breaks, offloads, post-contact metres, kick metres, errors) —
NOT from tries/points themselves (that would be circular). A team's xForm is the
leak-free rolling mean of its (xPoints for − against); xForm_diff is the home−away
gap. We gate whether xForm_diff, as an offset correction on the current blend,
improves Brier on a holdout.

This is a feasibility spike on a few recent seasons; a positive result justifies
scraping the full history and wiring it in.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.eval import backtest as bt
from src.features import player_value  # reuse fit_offset_logistic
from src.ingest import champion_stats

OUT = ROOT / "outputs"
PROCESS = ["allRunMetres", "postContactMetres", "lineBreaks", "lineBreakAssists",
           "tackleBreaks", "offloads", "errors", "handlingErrors", "kickMetres"]
XPOINTS_FIT_MAX_YEAR = 2023  # fit the stats->points translation on early seasons


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def team_long(ts: pd.DataFrame) -> pd.DataFrame:
    """One row per team-match with own process stats + points scored."""
    frames = []
    for side, opp in (("home", "away"), ("away", "home")):
        d = pd.DataFrame({"season": ts["season"], "round": ts["round"],
                          "date": ts["date"], "team_id": ts[f"{side}_id"],
                          "opp_id": ts[f"{opp}_id"], "points": ts[f"{side}_score"]})
        for f in PROCESS:
            d[f] = ts[f"{side}_{f}"]
        frames.append(d)
    return pd.concat(frames, ignore_index=True).sort_values(["date"]).reset_index(drop=True)


def main() -> None:
    ts = pd.read_parquet(champion_stats.OUT)
    ts = ts.dropna(subset=["home_id", "away_id", "home_score"]).copy()
    ts["year"] = ts["season"]
    tl = team_long(ts)

    # xPoints: fit points ~ process stats on the early seasons only
    fit = tl[tl["season"] <= XPOINTS_FIT_MAX_YEAR]
    reg = Ridge(alpha=50.0).fit(fit[PROCESS], fit["points"])
    tl["xpoints"] = reg.predict(tl[PROCESS])
    print("xPoints model R^2 (fit years):", round(reg.score(fit[PROCESS], fit["points"]), 3))
    corr = np.corrcoef(tl["xpoints"], tl["points"])[0, 1]
    print("corr(xPoints, actual points):", round(corr, 3))

    # xForm = leak-free expanding mean of (xPoints for - against) per team
    tl["xmargin"] = tl["xpoints"]  # for-team component; against comes via opponent join
    # build per-team rolling xpoints-for and xpoints-against
    tl = tl.sort_values("date")
    tl["xpoints_against"] = np.nan
    xp_by_match = {(r.team_id, r.season, r.round): r.xpoints for r in tl.itertuples(index=False)}
    tl["xpoints_against"] = [xp_by_match.get((r.opp_id, r.season, r.round), np.nan)
                             for r in tl.itertuples(index=False)]
    tl["xdiff"] = tl["xpoints"] - tl["xpoints_against"]
    tl["xform"] = (tl.groupby("team_id")["xdiff"]
                   .transform(lambda s: s.shift().expanding(min_periods=3).mean()))

    xform = {(r.team_id, r.season, r.round): r.xform for r in tl.itertuples(index=False)}
    ts["xform_diff"] = [
        (xform.get((r.home_id, r.season, r.round), np.nan) or np.nan)
        - (xform.get((r.away_id, r.season, r.round), np.nan) or np.nan)
        for r in ts.itertuples(index=False)]

    # join to the blend frame
    bf = pd.read_parquet(OUT / "blend_frame.parquet")
    bf["round_no"] = pd.to_numeric(bf["round"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    j = ts.merge(bf, left_on=["season", "round", "home_id", "away_id"],
                 right_on=["year", "round_no", "home_id", "away_id"], how="inner",
                 suffixes=("", "_bf"))
    j = j.dropna(subset=["xform_diff", "p_blend"])
    j["y"] = bt.outcome(j)
    eval_mask = (j["season"] >= 2024).to_numpy()
    fit_mask = (j["season"] < 2024).to_numpy() & (j["y"].to_numpy() != 0.5)
    print(f"\nmatched games: {len(j)} | fit {fit_mask.sum()} | eval {eval_mask.sum()}")

    x = j["xform_diff"].to_numpy(float)
    mu, sd = x[fit_mask].mean(), x[fit_mask].std() + 1e-9
    xs = (x - mu) / sd
    off = logit(j["p_blend"].to_numpy())
    beta = player_value.fit_offset_logistic(xs[fit_mask], j["y"].to_numpy()[fit_mask], off[fit_mask])
    p_base = 1 / (1 + np.exp(-off[eval_mask]))
    p_x = 1 / (1 + np.exp(-(off[eval_mask] + beta * xs[eval_mask])))
    y_ev = j["y"].to_numpy()[eval_mask]
    print(f"\nxform beta = {beta:+.3f}")
    print(f"blend (base)        Brier {bt.brier(p_base, y_ev):.4f}  logloss {bt.log_loss(p_base, y_ev):.4f}")
    print(f"blend + xForm       Brier {bt.brier(p_x, y_ev):.4f}  logloss {bt.log_loss(p_x, y_ev):.4f}")
    verdict = "BEATS" if bt.brier(p_x, y_ev) < bt.brier(p_base, y_ev) - 0.0002 else "does NOT beat"
    print(f"\nxForm {verdict} the blend on {eval_mask.sum()} holdout games "
          f"(2024-25). corr(xPoints,pts)={corr:.2f}")


if __name__ == "__main__":
    main()
