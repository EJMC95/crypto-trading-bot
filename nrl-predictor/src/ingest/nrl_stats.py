"""Ingest the uselessnrlstats cleaned CSVs + NRL.com draw API.

Deep history (1908→present): github.com/uselessnrlstats/uselessnrlstats cleaned_data/nrl,
cloned into data/raw/uselessnrlstats/. Matches, player_match_data, round ladders, venues.

Current season top-up: the uselessnrlstats dump lags a few weeks, so completed 2026
results and upcoming fixtures come from NRL.com's draw endpoint —
    https://www.nrl.com/draw/data?competition=111&season=<yyyy>&round=<n>
(URL logic ported from the nrlR R package, per Build Spec §3). Responses are cached
under data/raw/nrl_draw/ and refreshed only for rounds that were not yet complete.

Outputs (data/processed/):
- matches.parquet       — all NRL-era matches (>= MODEL_START_YEAR) with canonical IDs,
                          uselessnrlstats history + NRL.com top-up, deduplicated
- fixtures_next.parquet — the next unplayed round's fixtures
- player_matches.parquet, ladder_rounds.parquet — pass-throughs for the season review
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from . import teams

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "uselessnrlstats"
DRAW_CACHE = ROOT / "data" / "raw" / "nrl_draw"
PROCESSED = ROOT / "data" / "processed"

# Elo history starts here: first season of the stable post-contraction competition.
# Every current franchise except the Titans (2007) and Dolphins (2023) exists from 2003,
# which keeps the canonical team table free of defunct-club ambiguity and still gives
# the 2015+ evaluation window a 12-year burn-in.
MODEL_START_YEAR = 2003

NRL_COMP_ID = 111  # NRL Premiership, per nrlR endpoint map
DRAW_URL = "https://www.nrl.com/draw/data"
HEADERS = {"User-Agent": "nrl-predictor research (contact: repo owner)", "Accept": "application/json"}

FINALS_PAT = re.compile(r"final", re.IGNORECASE)


def _round_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.extract(r"Round (\d+)")[0], errors="coerce")


def load_history() -> pd.DataFrame:
    m = pd.read_csv(RAW / "match_data.csv", low_memory=False)
    m["date"] = pd.to_datetime(m["date"])
    m["year"] = m["date"].dt.year
    m = m[(m["year"] >= MODEL_START_YEAR)].copy()
    m = m.dropna(subset=["home_team_score", "away_team_score"])
    m["round_no"] = _round_number(m["round"])
    m["is_finals"] = m["round"].astype(str).str.contains(FINALS_PAT) | m["round_no"].isna()
    m["home_id"] = teams.to_canonical(m["home_team"], "uselessnrlstats")
    m["away_id"] = teams.to_canonical(m["away_team"], "uselessnrlstats")
    out = m[
        ["date", "year", "round", "round_no", "is_finals", "match_id", "venue_id",
         "crowd", "home_id", "away_id", "home_team_score", "away_team_score"]
    ].rename(columns={"home_team_score": "home_score", "away_team_score": "away_score"})
    return out.sort_values("date").reset_index(drop=True)


def fetch_nrl_draw(season: int, round_no: int, refresh: bool = False) -> dict:
    DRAW_CACHE.mkdir(parents=True, exist_ok=True)
    cache = DRAW_CACHE / f"draw_{season}_r{round_no:02d}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
    r = requests.get(
        DRAW_URL,
        params={"competition": NRL_COMP_ID, "season": season, "round": round_no},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    cache.write_text(json.dumps(data))
    time.sleep(1.0)  # polite rate limit
    return data


def _parse_draw_fixtures(data: dict, season: int) -> pd.DataFrame:
    rows = []
    for fx in data.get("fixtures", []):
        if fx.get("type") != "Match":
            continue
        home, away = fx["homeTeam"], fx["awayTeam"]
        kickoff = fx.get("clock", {}).get("kickOffTimeLong")
        kick_local = (
            pd.to_datetime(kickoff, utc=True).tz_convert("Australia/Sydney").tz_localize(None)
            if kickoff else pd.NaT
        )
        rows.append(
            {
                "season": season,
                "round": fx.get("roundTitle"),
                "match_state": fx.get("matchState"),
                "venue": fx.get("venue"),
                "date": kick_local,
                "home_raw": home.get("nickName"),
                "away_raw": away.get("nickName"),
                "home_score": home.get("score"),
                "away_score": away.get("score"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["round_no"] = _round_number(df["round"])
    df["home_id"] = teams.to_canonical(df["home_raw"], "nrl.com draw")
    df["away_id"] = teams.to_canonical(df["away_raw"], "nrl.com draw")
    return df


def fetch_current_season(season: int, max_round: int = 27) -> pd.DataFrame:
    """Walk rounds until the first round with no completed games; cache aggressively."""
    frames = []
    for rnd in range(1, max_round + 1):
        cache = DRAW_CACHE / f"draw_{season}_r{rnd:02d}.json"
        # A cached fully-played round never changes; anything else gets refreshed.
        cached = json.loads(cache.read_text()) if cache.exists() else None
        df = _parse_draw_fixtures(cached, season) if cached else pd.DataFrame()
        fully_played = (not df.empty) and df["match_state"].eq("FullTime").all()
        if not fully_played:
            df = _parse_draw_fixtures(fetch_nrl_draw(season, rnd, refresh=True), season)
        if df.empty:
            break
        frames.append(df)
        if not df["match_state"].eq("FullTime").any():
            break  # first entirely-unplayed round fetched (that's our fixture list); stop
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build(season: int | None = None) -> dict[str, pd.DataFrame]:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    season = season or date.today().year

    hist = load_history()

    draw = fetch_current_season(season)
    played, fixtures = pd.DataFrame(), pd.DataFrame()
    if not draw.empty:
        draw["year"] = season
        played = draw[draw["match_state"].eq("FullTime")].copy()
        played["is_finals"] = ~played["round"].astype(str).str.match(r"Round \d+")
        # Top-up: only rounds/games the history file doesn't already have.
        key = ["year", "round_no", "home_id", "away_id"]
        have = set(map(tuple, hist[hist["year"] == season][key].values))
        mask = [tuple(r) not in have for r in played[key].values]
        topup = played.loc[
            mask, ["date", "year", "round", "round_no", "is_finals", "home_id",
                   "away_id", "home_score", "away_score", "venue"]
        ]
        matches = pd.concat([hist, topup], ignore_index=True).sort_values("date")

        next_round = draw.loc[~draw["match_state"].eq("FullTime"), "round_no"].min()
        fixtures = draw[draw["round_no"].eq(next_round) & ~draw["match_state"].eq("FullTime")]
    else:
        matches = hist

    matches = matches.reset_index(drop=True)
    matches.to_parquet(PROCESSED / "matches.parquet", index=False)
    if not fixtures.empty:
        fixtures.reset_index(drop=True).to_parquet(PROCESSED / "fixtures_next.parquet", index=False)

    pm = pd.read_csv(RAW / "player_match_data.csv", low_memory=False)
    pm.to_parquet(PROCESSED / "player_matches.parquet", index=False)
    ladder = pd.read_csv(RAW / "ladder_round_data.csv", low_memory=False)
    ladder.to_parquet(PROCESSED / "ladder_rounds.parquet", index=False)

    return {"matches": matches, "fixtures_next": fixtures}


if __name__ == "__main__":
    res = build()
    m = res["matches"]
    print(f"{len(m)} matches {m['date'].min().date()} -> {m['date'].max().date()}")
    fx = res["fixtures_next"]
    if not fx.empty:
        print(f"next round: {fx['round'].iloc[0]} — {len(fx)} fixtures")
