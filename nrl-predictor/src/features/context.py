"""Match-context features (Build Spec §5 GBM features, pulled into the blend).

Three documented NRL edges the pure team-rating model misses, all leak-free
(computed only from data available before kickoff):

- rest days   : days since each team's previous match (short turnarounds hurt,
                especially away). Capped at 14 (a bye+ is "fully rested").
- travel km   : great-circle distance from each team's home city to the venue.
                Big away trips (Warriors trans-Tasman, Cowboys/Titans interstate)
                sap teams. Home side is usually ~0 but not at neutral/Magic Round.
- Origin flag : whether the match falls in a State-of-Origin disruption window
                (rep-round games missing 3-6 stars + the post-Origin backup game),
                detected from the actual Origin match dates.

Output columns are aligned to the `matches` frame; consumed by run_phase3 as extra
stack features (only kept if they beat the current blend on the walk-forward gate).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "data" / "reference"
ORIGIN_MATCHES = ROOT / "data" / "raw" / "uselessnrlstats_origin" / "match_data.csv"

REST_CAP = 14.0
ORIGIN_PAD_DAYS = 4  # a club game within this many days of an Origin match is disrupted


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def rest_days(matches: pd.DataFrame) -> pd.DataFrame:
    """home_rest, away_rest aligned to matches (days since each team's last game)."""
    m = matches.sort_values("date").reset_index()
    last: dict[str, pd.Timestamp] = {}
    hr, ar = np.full(len(m), REST_CAP), np.full(len(m), REST_CAP)
    for i, row in enumerate(m.itertuples(index=False)):
        d = pd.Timestamp(row.date)
        for col, tid, arr in (("h", row.home_id, hr), ("a", row.away_id, ar)):
            if tid in last:
                arr[i] = min((d - last[tid]).days, REST_CAP)
        last[row.home_id] = d
        last[row.away_id] = d
    out = pd.DataFrame({"home_rest": hr, "away_rest": ar}, index=m["index"]).sort_index()
    return out


def travel_km(matches: pd.DataFrame) -> pd.DataFrame:
    homes = pd.read_csv(REF / "team_homes.csv").set_index("canonical_id")
    venues = pd.read_csv(REF / "venue_coords.csv")
    vmap = {v.venue: (v.lat, v.lon) for v in venues.itertuples(index=False)}

    def vloc(venue, home_id):
        # venue coords if known, else the home team's city (home games dominate)
        if venue in vmap:
            return vmap[venue]
        return (homes.loc[home_id, "home_lat"], homes.loc[home_id, "home_lon"]) \
            if home_id in homes.index else (None, None)

    ht, at = np.zeros(len(matches)), np.zeros(len(matches))
    for i, r in enumerate(matches.itertuples(index=False)):
        vlat, vlon = vloc(getattr(r, "venue", None), r.home_id)
        if vlat is None:
            continue
        for tid, arr in ((r.home_id, ht), (r.away_id, at)):
            if tid in homes.index:
                arr[i] = _haversine(homes.loc[tid, "home_lat"], homes.loc[tid, "home_lon"],
                                    vlat, vlon)
    return pd.DataFrame({"home_travel": ht, "away_travel": at}, index=matches.index)


def origin_flag(matches: pd.DataFrame) -> pd.Series:
    """1 if the match is within ORIGIN_PAD_DAYS of a State-of-Origin game."""
    if not ORIGIN_MATCHES.exists():
        # fallback: May–July midweek window heuristic
        mon = pd.to_datetime(matches["date"]).dt.month
        return mon.isin([5, 6, 7]).astype(int)
    od = pd.read_csv(ORIGIN_MATCHES, low_memory=False)
    odates = pd.to_datetime(od["date"], errors="coerce").dropna().dt.normalize().unique()
    odates = pd.DatetimeIndex(odates).sort_values()
    md = pd.to_datetime(matches["date"]).dt.normalize()
    flag = np.zeros(len(matches), dtype=int)
    for i, d in enumerate(md):
        # nearest Origin date within the pad
        pos = odates.searchsorted(d)
        for j in (pos - 1, pos):
            if 0 <= j < len(odates) and abs((odates[j] - d).days) <= ORIGIN_PAD_DAYS:
                flag[i] = 1
                break
    return pd.Series(flag, index=matches.index)


def build(matches: pd.DataFrame) -> pd.DataFrame:
    """Return context features aligned to `matches` (differences are what the model
    uses; home-minus-away framing keeps it symmetric)."""
    rest = rest_days(matches)
    trav = travel_km(matches)
    f = pd.DataFrame(index=matches.index)
    f["rest_diff"] = rest["home_rest"] - rest["away_rest"]
    f["short_turnaround_home"] = (rest["home_rest"] <= 6).astype(int)
    f["short_turnaround_away"] = (rest["away_rest"] <= 6).astype(int)
    f["travel_diff"] = (trav["away_travel"] - trav["home_travel"]) / 1000.0  # Mm, home-favourable
    f["away_long_haul"] = (trav["away_travel"] >= 1500).astype(int)
    f["origin_window"] = origin_flag(matches)
    return f
