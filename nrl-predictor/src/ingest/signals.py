"""On-the-day signal scanner (Build Spec §3 "Team lists" + "Weather").

Stringency principle: only *verifiable structured* signals are allowed to move a
number downstream — the named team list (biggest weekly information event) and the
venue weather forecast. News/social headlines are keyword-flagged and surfaced as
ADVISORY notes only; they never silently alter a probability. See
src/features/signal_adjust.py for how each signal is (or isn't) applied.

Sources (all keyless):
- NRL.com match-centre `/data` endpoint — the named 1-17 per team (positions, so
  the spine is identifiable), matched to our canonical player_ids by name.
- Open-Meteo forecast — rain / precip probability / wind at each venue at kickoff
  hour. Venue coordinates from data/reference/venue_coords.csv, backfilled by
  Open-Meteo geocoding on the venue city and cached.
- Google News RSS — recent headlines per club, flagged for injury/suspension/
  late-change keywords. Advisory only.

Output: outputs/round_signals.json — one entry per fixture.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests

from . import nrl_stats, teams

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
REF = ROOT / "data" / "reference"
VENUE_COORDS = REF / "venue_coords.csv"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/json"}

# Named-position -> role bucket. The spine (FB/HB/FE/HK) is where a late change
# most moves a match; the back three + centres drive tryscoring.
SPINE = {"Fullback", "Halfback", "Five-Eighth", "Hooker"}
STARTER_NUMBERS = set(range(1, 14))

NEWS_FLAGS = {
    "out": r"\b(ruled out|withdrawn|out with|misses|sidelined|won't play|will not play)\b",
    "injury": r"\b(injur|hamstring|concussion|acl|knee|ankle|shoulder|calf|hia)\b",
    "suspension": r"\b(suspend|banned|charged|judiciary)\b",
    "return": r"\b(returns|recalled|named to start|back from|cleared to play)\b",
    "debut": r"\b(debut|first-grade call-up)\b",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


# ---------------------------------------------------------------------------
# Team lists
# ---------------------------------------------------------------------------
def _player_name_index() -> dict[str, int]:
    pdata = pd.read_csv(ROOT / "data" / "raw" / "uselessnrlstats" / "player_data.csv",
                        low_memory=False)
    return {_norm(n): int(pid) for n, pid in zip(pdata["full_name"], pdata["player_id"])}


def _match_data(match_url: str) -> dict:
    url = f"https://www.nrl.com{match_url.rstrip('/')}/data"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    time.sleep(0.5)
    return r.json()


def team_list(md: dict, side: str, name_idx: dict[str, int]) -> list[dict]:
    out = []
    for p in md[side]["players"]:
        num = p.get("number")
        if num is None or num > 17:
            continue
        full = f"{p['firstName']} {p['lastName']}"
        out.append({
            "number": num, "position": p.get("position"),
            "player": full, "player_id": name_idx.get(_norm(full)),
            "is_starter": num in STARTER_NUMBERS,
            "is_spine": p.get("position") in SPINE,
            "status": p.get("status"),
        })
    return sorted(out, key=lambda d: d["number"])


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
def _venue_latlon(venue: str, city: str | None) -> tuple[float, float] | None:
    coords = pd.read_csv(VENUE_COORDS) if VENUE_COORDS.exists() else pd.DataFrame(
        columns=["venue", "lat", "lon"])
    key = _norm(venue)
    hit = coords[coords["venue"].map(_norm) == key]
    if len(hit):
        return float(hit.iloc[0]["lat"]), float(hit.iloc[0]["lon"])
    # geocode the venue, fall back to the city
    for q in (venue, city):
        if not q:
            continue
        try:
            g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                             params={"name": q, "count": 1, "country": "AU"},
                             headers=UA, timeout=20).json()
            res = (g.get("results") or [None])[0]
            if res:
                lat, lon = res["latitude"], res["longitude"]
                coords = pd.concat([coords, pd.DataFrame([{"venue": venue, "lat": lat,
                                    "lon": lon}])], ignore_index=True)
                REF.mkdir(parents=True, exist_ok=True)
                coords.drop_duplicates("venue", keep="last").to_csv(VENUE_COORDS, index=False)
                return lat, lon
        except Exception:
            continue
    return None


def weather_at(venue: str, city: str | None, kickoff: pd.Timestamp) -> dict | None:
    ll = _venue_latlon(venue, city)
    if ll is None:
        return None
    lat, lon = ll
    try:
        d = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon,
            "hourly": "precipitation,precipitation_probability,wind_speed_10m,temperature_2m",
            "timezone": "auto", "forecast_days": 16}, headers=UA, timeout=25).json()
    except Exception:
        return None
    h = d.get("hourly", {})
    times = h.get("time", [])
    if not times:
        return None
    target = kickoff.strftime("%Y-%m-%dT%H:00")
    idx = min(range(len(times)), key=lambda i: abs(
        (datetime.fromisoformat(times[i]) - datetime.fromisoformat(target)).total_seconds()))
    return {
        "precip_mm": h["precipitation"][idx],
        "precip_prob": h["precipitation_probability"][idx],
        "wind_kmh": h["wind_speed_10m"][idx],
        "temp_c": h["temperature_2m"][idx],
        "forecast_hour": times[idx],
    }


# ---------------------------------------------------------------------------
# News (advisory only)
# ---------------------------------------------------------------------------
def scan_news(team_name: str, players: set[str], max_items: int = 12) -> list[dict]:
    try:
        r = requests.get("https://news.google.com/rss/search",
                         params={"q": f"{team_name} NRL team news",
                                 "hl": "en-AU", "gl": "AU", "ceid": "AU:en"},
                         headers={"User-Agent": UA["User-Agent"]}, timeout=20)
        root = ET.fromstring(r.content)
    except Exception:
        return []
    flagged = []
    pnorms = {_norm(p): p for p in players}
    for item in list(root.iter("item"))[:max_items]:
        title = (item.findtext("title") or "")
        low = title.lower()
        tags = [name for name, pat in NEWS_FLAGS.items() if re.search(pat, low)]
        if not tags:
            continue
        who = [orig for n, orig in pnorms.items() if n and n in _norm(title)]
        flagged.append({"headline": title, "flags": tags, "players": who,
                        "link": item.findtext("link"),
                        "published": item.findtext("pubDate")})
    return flagged[:6]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def scan_round(with_news: bool = True) -> dict:
    fixtures = pd.read_parquet(ROOT / "data" / "processed" / "fixtures_next.parquet")
    season = int(fixtures["date"].dt.year.iloc[0])
    round_no = int(fixtures["round_no"].iloc[0])
    name_idx = _player_name_index()
    names = teams.id_to_name()

    # match-centre URLs come from the season draw (already cached by nrl_stats)
    draw = nrl_stats.fetch_nrl_draw(season, round_no, refresh=True)
    url_by_pair = {}
    for fx in draw.get("fixtures", []):
        if fx.get("type") != "Match":
            continue
        h = teams.alias_to_id().get(fx["homeTeam"]["nickName"].strip())
        a = teams.alias_to_id().get(fx["awayTeam"]["nickName"].strip())
        url_by_pair[(h, a)] = (fx.get("matchCentreUrl"), fx.get("venue"), fx.get("venueCity"))

    games = []
    for fx in fixtures.itertuples(index=False):
        info = url_by_pair.get((fx.home_id, fx.away_id))
        entry = {"home": names[fx.home_id], "away": names[fx.away_id],
                 "home_id": fx.home_id, "away_id": fx.away_id,
                 "kickoff": str(fx.date), "team_lists_confirmed": False,
                 "home_17": [], "away_17": [], "weather": None, "news": []}
        if info:
            match_url, venue, city = info
            try:
                md = _match_data(match_url)
                h17 = team_list(md, "homeTeam", name_idx)
                a17 = team_list(md, "awayTeam", name_idx)
                entry["home_17"], entry["away_17"] = h17, a17
                entry["team_lists_confirmed"] = len(h17) >= 17 and len(a17) >= 17
            except Exception as e:
                entry["team_list_error"] = str(e)[:120]
            entry["weather"] = weather_at(venue or fx.venue, city, pd.Timestamp(fx.date))
            if with_news:
                names_pool = {p["player"] for p in entry["home_17"]}
                entry["news_home"] = scan_news(names[fx.home_id], names_pool)
                away_pool = {p["player"] for p in entry["away_17"]}
                entry["news_away"] = scan_news(names[fx.away_id], away_pool)
        games.append(entry)

    payload = {"season": season, "round": round_no,
               "scanned_at": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
               "games": games}
    OUT.mkdir(exist_ok=True)
    (OUT / "round_signals.json").write_text(json.dumps(payload, indent=1, default=str))
    return payload


if __name__ == "__main__":
    p = scan_round(with_news=True)
    for g in p["games"]:
        w = g["weather"]
        wx = f"{w['precip_prob']}% rain, {w['precip_mm']}mm, {w['wind_kmh']}km/h" if w else "n/a"
        print(f"{g['home']} v {g['away']}: lists={'✓' if g['team_lists_confirmed'] else '✗'} | wx={wx}")
