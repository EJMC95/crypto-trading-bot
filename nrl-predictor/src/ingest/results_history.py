"""Ingest aussportsbetting.com historical NRL results + odds.

Source file: https://www.aussportsbetting.com/historical_data/nrl.xlsx
(one row per match, 2009→present, with bookmaker open/close head-to-head odds,
lines and totals). The live site sits behind a Cloudflare JS challenge that plain
HTTP clients cannot pass, so `download()` falls back to the most recent Wayback
Machine capture of the same file — identical bytes, just possibly a few weeks stale.
Refresh weekly per the Build Spec; a manual browser download into data/raw/nrl.xlsx
always wins over the fallback.

Output: data/processed/matches_odds.parquet — one row per match with canonical team
IDs and de-vigged closing win probabilities (proportional de-vig on the home/away
closing prices; draws carry no quoted price in this file so the two-way book is
normalised to sum to 1).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

from . import teams

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "nrl.xlsx"
OUT = ROOT / "data" / "processed" / "matches_odds.parquet"

DIRECT_URL = "https://www.aussportsbetting.com/historical_data/nrl.xlsx"
WAYBACK_AVAIL = (
    "https://archive.org/wayback/available"
    "?url=www.aussportsbetting.com/historical_data/nrl.xlsx&timestamp=99999999"
)
XLSX_MAGIC = b"PK\x03\x04"


def download(force: bool = False) -> Path:
    if RAW.exists() and not force:
        return RAW
    RAW.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(DIRECT_URL, timeout=60)
        if r.ok and r.content[:4] == XLSX_MAGIC:
            RAW.write_bytes(r.content)
            return RAW
        print("direct download blocked (Cloudflare); falling back to Wayback", file=sys.stderr)
    except requests.RequestException as e:
        print(f"direct download failed ({e}); falling back to Wayback", file=sys.stderr)
    avail = requests.get(WAYBACK_AVAIL, timeout=60).json()
    snap = avail["archived_snapshots"]["closest"]
    ts = snap["timestamp"]
    url = f"https://web.archive.org/web/{ts}id_/http://www.aussportsbetting.com/historical_data/nrl.xlsx"
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    if r.content[:4] != XLSX_MAGIC:
        raise RuntimeError("Wayback fallback did not return an xlsx file")
    RAW.write_bytes(r.content)
    print(f"downloaded Wayback capture {ts}", file=sys.stderr)
    return RAW


def build() -> pd.DataFrame:
    download()
    df = pd.read_excel(RAW, sheet_name="Data", header=1)
    df = df.rename(
        columns={
            "Date": "date",
            "Home Team": "home_raw",
            "Away Team": "away_raw",
            "Venue": "venue",
            "Home Score": "home_score",
            "Away Score": "away_score",
            "Play Off Game?": "playoff",
            "Home Odds Close": "home_odds_close",
            "Away Odds Close": "away_odds_close",
            "Home Odds": "home_odds_avg",
            "Away Odds": "away_odds_avg",
            "Home Line Close": "home_line_close",
            "Total Score Close": "total_close",
        }
    )
    df = df.dropna(subset=["date", "home_raw", "away_raw"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["home_id"] = teams.to_canonical(df["home_raw"], "aussportsbetting")
    df["away_id"] = teams.to_canonical(df["away_raw"], "aussportsbetting")
    df["playoff"] = df["playoff"].astype(str).str.upper().eq("Y")

    # De-vig the two-way closing book proportionally; fall back to the surveyed
    # average odds where a closing price is missing.
    for side in ("home", "away"):
        df[f"{side}_odds_best"] = df[f"{side}_odds_close"].fillna(df[f"{side}_odds_avg"])
    inv_h = 1.0 / df["home_odds_best"]
    inv_a = 1.0 / df["away_odds_best"]
    overround = inv_h + inv_a
    df["market_p_home"] = inv_h / overround
    df["market_overround"] = overround
    df["odds_is_closing"] = df["home_odds_close"].notna() & df["away_odds_close"].notna()

    cols = [
        "date", "home_id", "away_id", "venue", "home_score", "away_score", "playoff",
        "home_odds_close", "away_odds_close", "home_odds_avg", "away_odds_avg",
        "home_line_close", "total_close", "market_p_home", "market_overround",
        "odds_is_closing",
    ]
    out = df[cols].sort_values("date").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    return out


if __name__ == "__main__":
    built = build()
    print(f"{len(built)} matches -> {OUT}")
    print(built["date"].min(), "->", built["date"].max())
