"""Phase 2: 2026 season review — every game, team and player, as a tidy workbook.

Writes:
- outputs/season_review_2026.xlsx  — sheets: Summary, Games, Ladder, Teams, Players,
  Elo Ratings, Round 19 Preview
- outputs/season_review_2026.md    — the Summary sheet as markdown (Notion source)

Player stats come from the uselessnrlstats dump, which trails the live season by a
few weeks; the coverage note on the Summary sheet says exactly which games are in.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval import backtest as bt
from src.ingest import teams
from src.models.match_elo import run_elo

PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "uselessnrlstats"
OUT = ROOT / "outputs"
SEASON = 2026

# Frozen Phase-1 parameters (see outputs/phase1_report.md).
from src.models.match_elo import EloParams
PARAMS = EloParams(k=10.0, home_adv=60.0, regress=0.33, scale=400.0, mov_cap=3.0)


def load() -> dict:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    pred = run_elo(matches, PARAMS)
    season = pred[pred["year"] == SEASON].copy()
    season["margin"] = season["home_score"] - season["away_score"]
    season["total"] = season["home_score"] + season["away_score"]
    names = teams.id_to_name()
    season["home"] = season["home_id"].map(names)
    season["away"] = season["away_id"].map(names)

    venues = pd.read_csv(RAW / "venue_data.csv")
    vmap = dict(venues[["venue_id", "venue_name"]].values)
    season["venue"] = season["venue"].where(
        season["venue"].notna(), season["venue_id"].map(vmap)
    )

    pm = pd.read_parquet(PROCESSED / "player_matches.parquet")
    pm26 = pm[pm["match_id"].isin(season["match_id"].dropna())].copy()
    players = pd.read_csv(RAW / "player_data.csv", low_memory=False)
    pm26 = pm26.merge(players[["player_id", "full_name"]], on="player_id", how="left")
    pm26["team_id"] = teams.to_canonical(pm26["team"], "player_match_data")
    return {"pred": pred, "season": season, "pm26": pm26}


def games_sheet(season: pd.DataFrame) -> pd.DataFrame:
    g = season.sort_values("date")[
        ["round", "date", "home", "away", "home_score", "away_score", "margin",
         "total", "venue", "crowd", "p_home"]
    ].rename(columns={"p_home": "elo_p_home_prematch"})
    g["result"] = np.select(
        [g["margin"] > 0, g["margin"] < 0], ["home win", "away win"], "draw"
    )
    g["upset"] = ((g["elo_p_home_prematch"] >= 0.5) & (g["margin"] < 0)) | (
        (g["elo_p_home_prematch"] < 0.5) & (g["margin"] > 0)
    )
    return g


def ladder_sheet(season: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tid in sorted(set(season["home_id"]) | set(season["away_id"])):
        h = season[season["home_id"] == tid]
        a = season[season["away_id"] == tid]
        pf = h["home_score"].sum() + a["away_score"].sum()
        pa = h["away_score"].sum() + a["home_score"].sum()
        wins = (h["margin"] > 0).sum() + (a["margin"] < 0).sum()
        draws = (season["margin"] == 0) & ((season["home_id"] == tid) | (season["away_id"] == tid))
        played = len(h) + len(a)
        rows.append({
            "team": teams.id_to_name()[tid], "played": played, "wins": int(wins),
            "draws": int(draws.sum()), "losses": int(played - wins - draws.sum()),
            "byes": 18 - played,
            "points_for": int(pf), "points_against": int(pa), "diff": int(pf - pa),
            # NRL awards 2 competition points per win and per bye, 1 per draw
            "comp_points": int(2 * wins + draws.sum() + 2 * (18 - played)),
        })
    lad = pd.DataFrame(rows).sort_values(["comp_points", "diff"], ascending=False)
    lad.insert(0, "pos", range(1, len(lad) + 1))
    return lad.reset_index(drop=True)


def teams_sheet(season: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    # Elo at season start = rating before each team's first 2026 game (regression
    # applied); Elo now = after the last played game.
    from src.models.match_elo import EloModel
    model_start, model_now = {}, {}
    model = EloModel(params=PARAMS)
    for row in pred.itertuples(index=False):
        yr = int(row.year)
        if yr == SEASON:
            for tid in (row.home_id, row.away_id):
                if tid not in model_start:
                    model._preseason(yr)
                    model_start[tid] = model.rating(tid)
        model.update(row.home_id, row.away_id, row.home_score, row.away_score, yr)
    model_now = dict(model.ratings)

    rows = []
    for tid in sorted(set(season["home_id"]) | set(season["away_id"])):
        mine = season[(season["home_id"] == tid) | (season["away_id"] == tid)].sort_values("date")
        is_home = mine["home_id"] == tid
        my_margin = np.where(is_home, mine["margin"], -mine["margin"])
        my_for = np.where(is_home, mine["home_score"], mine["away_score"])
        last5 = "".join("W" if m > 0 else ("D" if m == 0 else "L") for m in my_margin[-5:])
        rows.append({
            "team": teams.id_to_name()[tid],
            "avg_points_for": round(float(np.mean(my_for)), 1),
            "avg_margin": round(float(np.mean(my_margin)), 1),
            "home_record": f"{int((mine.loc[is_home,'margin']>0).sum())}-{int((mine.loc[is_home,'margin']<0).sum())}",
            "away_record": f"{int((mine.loc[~is_home,'margin']<0).sum())}-{int((mine.loc[~is_home,'margin']>0).sum())}",
            "biggest_win": int(my_margin.max()), "biggest_loss": int(my_margin.min()),
            "form_last5": last5,
            "elo_start": round(model_start[tid], 1), "elo_now": round(model_now[tid], 1),
            "elo_change": round(model_now[tid] - model_start[tid], 1),
        })
    return pd.DataFrame(rows).sort_values("elo_now", ascending=False).reset_index(drop=True)


def players_sheet(pm26: pd.DataFrame) -> pd.DataFrame:
    agg = (
        pm26.groupby(["player_id", "full_name", "team_id"], as_index=False)
        .agg(games=("match_id", "nunique"), tries=("tries", "sum"),
             goals=("goals", "sum"), field_goals=("field_goals", "sum"),
             points=("points", "sum"), sin_bins=("sin_bins", "sum"),
             positions=("position", lambda s: "/".join(sorted(set(s.dropna())))))
    )
    agg["team"] = agg["team_id"].map(teams.id_to_name())
    agg["tries_pg"] = (agg["tries"] / agg["games"]).round(2)
    agg["points_pg"] = (agg["points"] / agg["games"]).round(2)
    cols = ["full_name", "team", "positions", "games", "tries", "goals", "field_goals",
            "points", "tries_pg", "points_pg", "sin_bins"]
    return agg.sort_values(["points", "tries"], ascending=False)[cols].reset_index(drop=True)


def summary_lines(season, games, ladder, team_tab, players, pm_games, ratings, preds) -> list[str]:
    hw = (season["margin"] > 0).mean()
    upsets = games["upset"].sum()
    big = games.loc[games["margin"].abs().idxmax()]
    hi = games.loc[games["total"].idxmax()]
    top_try = players.sort_values("tries", ascending=False).iloc[0]
    top_pts = players.iloc[0]
    climb = team_tab.sort_values("elo_change", ascending=False).iloc[0]
    fall = team_tab.sort_values("elo_change").iloc[0]
    leader = ladder.iloc[0]
    return [
        f"# 2026 NRL season review — through Round 18 ({season['date'].max():%d %b %Y})",
        "",
        f"- **Games played:** {len(season)} | home win rate {hw:.1%} | "
        f"{int((season['margin']==0).sum())} draws | avg total {season['total'].mean():.1f} pts",
        f"- **Ladder leader:** {leader['team']} ({leader['comp_points']} pts, "
        f"{leader['wins']}W-{leader['losses']}L, diff {leader['diff']:+d})",
        f"- **Elo #1:** {ratings.iloc[0]['team']} ({ratings.iloc[0]['elo']:.0f})",
        f"- **Biggest riser (Elo):** {climb['team']} {climb['elo_change']:+.0f} | "
        f"**biggest slide:** {fall['team']} {fall['elo_change']:+.0f}",
        f"- **Biggest win:** {big['home']} {big['home_score']:.0f}–{big['away_score']:.0f} "
        f"{big['away']} ({big['round']})",
        f"- **Highest-scoring:** {hi['home']} {hi['home_score']:.0f}–{hi['away_score']:.0f} "
        f"{hi['away']} ({hi['total']:.0f} pts, {hi['round']})",
        f"- **Model upsets:** {upsets} of {len(games)} games went against the pre-match "
        f"Elo favourite ({upsets/len(games):.0%})",
        f"- **Top try scorer:** {top_try['full_name']} ({top_try['team']}) — "
        f"{int(top_try['tries'])} tries in {int(top_try['games'])} games",
        f"- **Top point scorer:** {top_pts['full_name']} ({top_pts['team']}) — "
        f"{int(top_pts['points'])} pts ({int(top_pts['tries'])}T {int(top_pts['goals'])}G)",
        "",
        f"_Player stats cover {pm_games} of {len(season)} played games "
        "(uselessnrlstats dump trails the live season; the game/team/Elo tables are "
        "complete through Round 18 via the NRL.com draw API)._",
    ]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    d = load()
    season, pred, pm26 = d["season"], d["pred"], d["pm26"]

    games = games_sheet(season)
    ladder = ladder_sheet(season)
    team_tab = teams_sheet(season, pred)
    players = players_sheet(pm26)
    ratings = pd.read_csv(OUT / "ratings_2026.csv")
    preds = pd.read_csv(OUT / "round_predictions.csv")

    lines = summary_lines(season, games, ladder, team_tab, players,
                          pm26["match_id"].nunique(), ratings, preds)
    (OUT / "season_review_2026.md").write_text("\n".join(lines))

    xlsx = OUT / "season_review_2026.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        pd.DataFrame({"2026 season review": lines}).to_excel(xw, sheet_name="Summary", index=False)
        games.to_excel(xw, sheet_name="Games", index=False)
        ladder.to_excel(xw, sheet_name="Ladder", index=False)
        team_tab.to_excel(xw, sheet_name="Teams", index=False)
        players.to_excel(xw, sheet_name="Players", index=False)
        ratings.to_excel(xw, sheet_name="Elo Ratings", index=False)
        preds.to_excel(xw, sheet_name="Round 19 Preview", index=False)
        for ws in xw.book.worksheets:  # readable column widths
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 9), 60)
    print(f"workbook -> {xlsx}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
