"""Advanced team match stats from NRL.com (Build Spec §3 "Advanced stats").

Aggregates the per-player StatsPerform/Champion-Data fields in the match-centre
`/data` endpoint to team-match totals — run metres, line breaks, tackle breaks,
offloads, post-contact metres, errors, missed tackles, kick metres — the
underlying "deserved performance" inputs an expected-points model needs.

Polite: one request per completed match, cached to data/raw/champion_stats/ so a
re-run only fetches new games. Output: data/processed/team_stats.parquet.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

from . import nrl_stats, teams

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "champion_stats"
OUT = ROOT / "data" / "processed" / "team_stats.parquet"

FIELDS = ["allRunMetres", "postContactMetres", "lineBreaks", "lineBreakAssists",
          "tackleBreaks", "offloads", "errors", "handlingErrors", "missedTackles",
          "kickMetres", "passes", "tries", "tryAssists", "penalties",
          "playTheBallTotal"]


def _team_totals(players: list[dict]) -> dict:
    t = {f: 0.0 for f in FIELDS}
    for p in players:
        for f in FIELDS:
            v = p.get(f)
            if isinstance(v, (int, float)):
                t[f] += v
    return t


def scrape(seasons, max_round: int = 27, have: set | None = None) -> pd.DataFrame:
    """Scrape team-match advanced stats. `have`: a set of (season, round, home_id,
    away_id) already present — those matches are skipped so an in-season refresh
    only fetches newly-completed games (polite + fast)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    alias = teams.alias_to_id()
    have = have or set()
    rows = []
    for season in seasons:
        for rnd in range(1, max_round + 1):
            try:
                draw = nrl_stats.fetch_nrl_draw(season, rnd)
            except Exception:
                break
            fixtures = [f for f in draw.get("fixtures", [])
                        if f.get("type") == "Match" and f.get("matchState") == "FullTime"]
            if not fixtures:
                # no completed games this round; later rounds unlikely complete either
                if rnd > 1:
                    break
                continue
            for fx in fixtures:
                hid0 = alias.get(fx["homeTeam"]["nickName"].strip())
                aid0 = alias.get(fx["awayTeam"]["nickName"].strip())
                if (season, rnd, hid0, aid0) in have:
                    continue   # already scraped in a prior run
                cache = CACHE / f"{season}_r{rnd:02d}_{fx['homeTeam']['nickName']}_{fx['awayTeam']['nickName']}.json".replace(" ", "")
                if cache.exists():
                    md = json.loads(cache.read_text())
                else:
                    try:
                        md = requests.get(
                            f"https://www.nrl.com{fx['matchCentreUrl'].rstrip('/')}/data",
                            headers=nrl_stats.HEADERS, timeout=30).json()
                        cache.write_text(json.dumps(md.get("stats", {}).get("players", {})))
                        md = json.loads(cache.read_text())
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"  skip {season} r{rnd} ({str(e)[:50]})")
                        continue
                if not md.get("homeTeam") or not md.get("awayTeam"):
                    continue
                h = _team_totals(md["homeTeam"]); a = _team_totals(md["awayTeam"])
                hid = alias.get(fx["homeTeam"]["nickName"].strip())
                aid = alias.get(fx["awayTeam"]["nickName"].strip())
                row = {"season": season, "round": rnd, "home_id": hid, "away_id": aid,
                       "home_score": fx["homeTeam"]["score"], "away_score": fx["awayTeam"]["score"],
                       "date": pd.to_datetime(fx.get("clock", {}).get("kickOffTimeLong")).tz_localize(None)
                       if fx.get("clock", {}).get("kickOffTimeLong") else pd.NaT}
                for f in FIELDS:
                    row[f"home_{f}"], row[f"away_{f}"] = h[f], a[f]
                rows.append(row)
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if len(df):
        df.to_parquet(OUT, index=False)
    return df


def refresh(seasons) -> pd.DataFrame:
    """Incremental in-season update: keep the committed parquet, fetch only the
    matches it does not yet have, append, and re-save. Safe to run every pipeline
    tick — a fully-scraped season is a no-op (a couple of draw fetches)."""
    existing = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame()
    have = set()
    if len(existing):
        have = {(int(r.season), int(r.round), r.home_id, r.away_id)
                for r in existing.itertuples(index=False)}
    fresh = scrape(seasons, have=have)
    if len(fresh) and len(existing):
        merged = (pd.concat([existing, fresh], ignore_index=True)
                  .drop_duplicates(subset=["season", "round", "home_id", "away_id"], keep="last")
                  .sort_values(["season", "round"]).reset_index(drop=True))
    else:
        merged = fresh if len(fresh) else existing
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if len(merged):
        merged.to_parquet(OUT, index=False)
    return merged


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    incremental = "--refresh" in args
    yrs = [int(x) for x in args if x.isdigit()] or [2023, 2024, 2025]
    d = refresh(yrs) if incremental else scrape(yrs)   # both persist to OUT
    print(f"{'refreshed' if incremental else 'scraped'} -> {len(d)} team-match rows -> {OUT}")
