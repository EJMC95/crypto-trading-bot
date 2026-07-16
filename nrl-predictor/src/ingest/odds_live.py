"""Live NRL head-to-head odds — keyless public bookmaker JSON feeds.

Workaround for the missing Odds-API/Betfair key (Build Spec §3 "Live/current
odds"). Four books are reachable keyless from the build environment (probed
2026-07-07; TAB is geo-blocked, Sportsbet sits behind Akamai bot management —
neither is bypassed, per the polite-scraping rule):

- ladbrokes-au / neds-au — Entain platform, one GET each; fractional prices
- pointsbet-au           — featured-events endpoint, decimal prices
- unibet-au              — Kambi CDN listView feed, milli-decimal prices

Each fetcher makes exactly ONE request per snapshot; snapshots are cached to
data/raw/odds/ with a timestamp so repeated runs in the same hour reuse the disk
copy. Any single book failing is fine — the consensus needs ≥1. A near-kickoff
snapshot doubles as the closing-line proxy until the weekly aussportsbetting
refresh grades CLV properly.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from . import teams

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "raw" / "odds"
PROCESSED = ROOT / "data" / "processed"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept": "application/json"}

ENTAIN_RL_CATEGORY = "608a1803-45bc-465a-8471-c89dcb68a27d"
ENTAIN_FIXED_WIN = "940b8704-e497-4a76-b390-00918ff7d282"
POINTSBET_NRL = 7593


def _get_json(url: str, extra_headers: dict | None = None) -> dict:
    headers = {**BASE_HEADERS, **(extra_headers or {})}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def _entain(book: str, host: str) -> list[dict]:
    url = (f"https://{host}/v2/sport/event-request"
           f"?category_ids=%5B%22{ENTAIN_RL_CATEGORY}%22%5D")
    data = _get_json(url, {"Content-Type": "application/json"})
    rows = []
    for ev in (data.get("events") or {}).values():
        if (ev.get("competition") or {}).get("name") != "NRL" or " vs " not in ev.get("name", ""):
            continue
        if not ev.get("main_markets"):
            continue
        market = (data.get("markets") or {}).get(ev["main_markets"][0])
        if not market or len(market.get("entrant_ids", [])) != 2:
            continue
        side = {}
        for eid in market["entrant_ids"]:
            ent = data["entrants"].get(eid, {})
            price = (data.get("prices") or {}).get(f"{eid}:{ENTAIN_FIXED_WIN}:")
            if not price:
                continue
            odds = price["odds"]
            side[ent.get("home_away")] = {
                "name": ent.get("name"),
                "price": 1 + odds["numerator"] / odds["denominator"],
            }
        if {"HOME", "AWAY"} <= side.keys():
            rows.append({
                "book": book, "home_raw": side["HOME"]["name"],
                "away_raw": side["AWAY"]["name"],
                "odds_home": round(side["HOME"]["price"], 3),
                "odds_away": round(side["AWAY"]["price"], 3),
                "kickoff": ev.get("advertised_start"),
            })
    return rows


def fetch_ladbrokes() -> list[dict]:
    return _entain("ladbrokes-au", "api.ladbrokes.com.au")


def fetch_neds() -> list[dict]:
    return _entain("neds-au", "api.neds.com.au")


def fetch_pointsbet() -> list[dict]:
    url = (f"https://api.au.pointsbet.com/api/v2/competitions/{POINTSBET_NRL}"
           "/events/featured?includeLive=false&page=1")
    data = _get_json(url)
    rows = []
    for ev in data.get("events", []):
        h2h = [m for m in ev.get("specialFixedOddsMarkets", [])
               if m.get("eventClass") == "Match Result"]
        if not h2h:
            continue
        prices = {o.get("side"): o.get("price") for o in h2h[0].get("outcomes", [])}
        if prices.get("Home") and prices.get("Away"):
            rows.append({
                "book": "pointsbet-au", "home_raw": ev["homeTeam"],
                "away_raw": ev["awayTeam"], "odds_home": prices["Home"],
                "odds_away": prices["Away"], "kickoff": ev.get("startsAt"),
            })
    return rows


def fetch_unibet() -> list[dict]:
    url = ("https://oc-offering-api.kambicdn.com/offering/v2018/ubau/listView/"
           "rugby_league/nrl/all/all/matches.json?lang=en_AU&market=AU")
    data = _get_json(url)
    rows = []
    for ew in data.get("events", []):
        ev = ew.get("event", {})
        offers = [b for b in ew.get("betOffers", [])
                  if b.get("betOfferType", {}).get("id") == 2 and "MAIN" in b.get("tags", [])]
        if not offers:
            continue
        outs = {o["type"]: o["odds"] / 1000 for o in offers[0].get("outcomes", [])
                if o.get("odds")}
        home = outs.get("OT_ONE") or outs.get("ONE")
        away = outs.get("OT_TWO") or outs.get("TWO")
        if home and away:
            rows.append({
                "book": "unibet-au", "home_raw": ev.get("homeName"),
                "away_raw": ev.get("awayName"), "odds_home": home,
                "odds_away": away, "kickoff": ev.get("start"),
            })
    return rows


FETCHERS = {
    "ladbrokes-au": fetch_ladbrokes,
    "neds-au": fetch_neds,
    "pointsbet-au": fetch_pointsbet,
    "unibet-au": fetch_unibet,
}


def snapshot(max_age_minutes: float = 60) -> pd.DataFrame:
    """One normalized frame across all reachable books; disk-cached by hour."""
    CACHE.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H")
    cache_file = CACHE / f"snapshot_{stamp}.json"
    if cache_file.exists():
        raw = json.loads(cache_file.read_text())
    else:
        raw = {}
        for book, fn in FETCHERS.items():
            try:
                raw[book] = fn()
            except Exception as e:  # any one book failing must not kill the snapshot
                print(f"  {book}: FAILED ({type(e).__name__}: {str(e)[:80]})")
                raw[book] = []
            time.sleep(1.0)
        cache_file.write_text(json.dumps(raw))

    rows = [r for book_rows in raw.values() for r in book_rows]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["home_id"] = teams.to_canonical(df["home_raw"], "odds feeds")
    df["away_id"] = teams.to_canonical(df["away_raw"], "odds feeds")
    df["fetched_at"] = now.isoformat(timespec="seconds")
    df["kickoff"] = pd.to_datetime(df["kickoff"], utc=True, format="mixed")
    PROCESSED.mkdir(exist_ok=True)
    df.to_parquet(PROCESSED / "odds_snapshot.parquet", index=False)
    return df


def consensus(df: pd.DataFrame) -> pd.DataFrame:
    """Per fixture: median de-vigged home prob + best available price each side."""
    if df.empty:
        return df
    inv_h, inv_a = 1 / df["odds_home"], 1 / df["odds_away"]
    df = df.assign(p_home_devig=inv_h / (inv_h + inv_a),
                   overround=inv_h + inv_a)
    g = df.groupby(["home_id", "away_id"], as_index=False).agg(
        books=("book", "nunique"),
        market_p_home=("p_home_devig", "median"),
        best_odds_home=("odds_home", "max"),
        best_odds_away=("odds_away", "max"),
        median_odds_home=("odds_home", "median"),
        median_odds_away=("odds_away", "median"),
        # book dispersion: how far the best price beats the median (a soft/outlier
        # line = the value). Higher = one book is out of step with the market.
        disp_home=("odds_home", lambda s: float(s.max() / s.median() - 1) if s.median() else 0.0),
        disp_away=("odds_away", lambda s: float(s.max() / s.median() - 1) if s.median() else 0.0),
        avg_overround=("overround", "mean"),
        kickoff=("kickoff", "first"),
    )
    return g


HISTORY = PROCESSED / "odds_history.parquet"


def append_history(cons: pd.DataFrame) -> None:
    """Append this consensus snapshot to the odds-history store so line movement
    and steam (rapid, one-directional moves) can be measured over time."""
    if cons is None or cons.empty:
        return
    keep = [c for c in ["home_id", "away_id", "market_p_home", "best_odds_home",
                        "best_odds_away", "median_odds_home", "median_odds_away"] if c in cons]
    snap = cons[keep].copy()
    snap["observed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    PROCESSED.mkdir(exist_ok=True)
    if HISTORY.exists():
        snap = pd.concat([pd.read_parquet(HISTORY), snap], ignore_index=True)
    snap.to_parquet(HISTORY, index=False)


def line_movement() -> pd.DataFrame:
    """Per fixture: opening vs latest de-vigged home prob, the net move in
    percentage points, and a steam flag (a large, one-directional shift)."""
    if not HISTORY.exists():
        return pd.DataFrame()
    h = pd.read_parquet(HISTORY).sort_values("observed_at")
    rows = []
    for (hid, aid), g in h.groupby(["home_id", "away_id"]):
        if len(g) < 2:
            continue
        first, last = g.iloc[0], g.iloc[-1]
        move = float(last["market_p_home"] - first["market_p_home"]) * 100
        rows.append({"home_id": hid, "away_id": aid, "n_obs": int(len(g)),
                     "open_p_home": round(float(first["market_p_home"]), 4),
                     "latest_p_home": round(float(last["market_p_home"]), 4),
                     "move_home_pp": round(move, 1), "steam": abs(move) >= 3.0,
                     "drift_side": "home" if move > 0 else "away"})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    snap = snapshot()
    if snap.empty:
        print("no books reachable")
    else:
        print(f"{len(snap)} book-prices across {snap['book'].nunique()} books")
        print(consensus(snap).to_string(index=False))
