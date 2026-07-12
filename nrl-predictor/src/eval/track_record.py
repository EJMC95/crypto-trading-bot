"""Prediction track record — which calls were right, which were wrong (Build Spec §7).

Distinct from the paper ledger (which logs *value bets* vs the market): this logs
every *model call* and grades it, so we can see accuracy over time regardless of
whether a bet was placed.

Markets tracked per game:
- win        : the side the blend favoured (hit/miss + Brier on the home prob)
- margin     : expected home margin (signed error, MAE, bias)
- total      : expected total points (signed error, MAE, bias)
- tryscorer  : the game's top ATS pick (did they score? + Brier on p_ats)

Storage: SQLite table `predictions` in data/ledger.db (alongside the bet ledger),
mirrored to outputs/predictions_log.csv; the accuracy summary is written to
outputs/track_record.json for the dashboard.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from ..ingest import nrl_stats, teams

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "ledger.db"
OUT = ROOT / "outputs"

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round TEXT NOT NULL,
    home_id TEXT NOT NULL,
    away_id TEXT NOT NULL,
    market TEXT NOT NULL,           -- win | margin | total | tryscorer
    selection TEXT,                 -- team_id / player name
    player_id INTEGER,              -- tryscorer only
    prob REAL,                      -- win: p_home ; tryscorer: p_ats
    point REAL,                     -- margin/total: expected value
    logged_at TEXT NOT NULL,
    actual REAL,
    correct INTEGER,                -- 1/0 for win & tryscorer
    error REAL,                     -- signed (predicted - actual) for margin/total
    brier REAL,
    settled_at TEXT,
    UNIQUE(round, home_id, away_id, market, selection)
);
"""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(SCHEMA)
    return con


def _mirror(con):
    df = pd.read_sql("SELECT * FROM predictions ORDER BY round, home_id", con)
    OUT.mkdir(exist_ok=True)
    df.to_csv(OUT / "predictions_log.csv", index=False)


def snapshot() -> int:
    """Log the current round's model calls (idempotent; never touches settled rows)."""
    preds = pd.read_csv(OUT / "round_predictions.csv")
    props = pd.read_csv(OUT / "round_props.csv") if (OUT / "round_props.csv").exists() else pd.DataFrame()
    name_to_id = {v: k for k, v in teams.id_to_name().items()}
    con = _conn()
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    rows = []
    for r in preds.itertuples(index=False):
        hid, aid = name_to_id.get(r.home), name_to_id.get(r.away)
        pick = hid if r.p_home_blend >= 0.5 else aid
        rows += [
            {"market": "win", "selection": pick, "prob": r.p_home_blend, "point": None,
             "player_id": None, "home_id": hid, "away_id": aid, "round": r.round},
            {"market": "margin", "selection": "home_margin", "prob": None,
             "point": r.exp_margin_home, "player_id": None, "home_id": hid,
             "away_id": aid, "round": r.round},
            {"market": "total", "selection": "total_points", "prob": None,
             "point": r.exp_total_points, "player_id": None, "home_id": hid,
             "away_id": aid, "round": r.round},
        ]
        g_props = props[props["match"] == f"{r.home} v {r.away}"] if len(props) else pd.DataFrame()
        if len(g_props):
            top = g_props.sort_values("p_ats", ascending=False).iloc[0]
            rows.append({"market": "tryscorer", "selection": top["player"],
                         "prob": float(top["p_ats"]), "point": None,
                         "player_id": int(top["player_id"]) if "player_id" in top and pd.notna(top.get("player_id")) else None,
                         "home_id": hid, "away_id": aid, "round": r.round})
    n = 0
    with con:
        for row in rows:
            exists = con.execute(
                "SELECT settled_at FROM predictions WHERE round=? AND home_id=? AND "
                "away_id=? AND market=? AND selection=?",
                (row["round"], row["home_id"], row["away_id"], row["market"], row["selection"])
            ).fetchone()
            if exists and exists[0]:
                continue
            con.execute(
                "INSERT INTO predictions (round,home_id,away_id,market,selection,player_id,"
                "prob,point,logged_at) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(round,home_id,away_id,market,selection) DO UPDATE SET "
                "prob=excluded.prob, point=excluded.point, logged_at=excluded.logged_at",
                (row["round"], row["home_id"], row["away_id"], row["market"],
                 row["selection"], row["player_id"], row["prob"], row["point"], now))
            n += 1
    _mirror(con)
    return n


def _results_and_scorers(season: int, round_no: int):
    """From NRL.com match-centre: final scores + set of canonical player_ids who
    scored a try, per completed fixture of the round."""
    draw = nrl_stats.fetch_nrl_draw(season, round_no, refresh=True)
    pdata = pd.read_csv(ROOT / "data" / "raw" / "uselessnrlstats" / "player_data.csv",
                        low_memory=False)
    name_to_pid = {_norm(n): int(p) for n, p in zip(pdata["full_name"], pdata["player_id"])}
    alias = teams.alias_to_id()
    results, scorers = [], {}
    for fx in draw.get("fixtures", []):
        if fx.get("type") != "Match" or fx.get("matchState") != "FullTime":
            continue
        hid = alias.get(fx["homeTeam"]["nickName"].strip())
        aid = alias.get(fx["awayTeam"]["nickName"].strip())
        results.append({"home_id": hid, "away_id": aid,
                        "home_score": fx["homeTeam"]["score"],
                        "away_score": fx["awayTeam"]["score"]})
        try:
            md = requests.get(
                f"https://www.nrl.com{fx['matchCentreUrl'].rstrip('/')}/data",
                headers=nrl_stats.HEADERS, timeout=30).json()
        except Exception:
            scorers[(hid, aid)] = None
            continue
        roster = {}
        for side in ("homeTeam", "awayTeam"):
            for p in md[side].get("players", []):
                roster[p["playerId"]] = f"{p['firstName']} {p['lastName']}"
        scored = set()
        for side in ("homeTeam", "awayTeam"):
            for s in md.get("stats", {}).get("players", {}).get(side, []):
                if s.get("tries"):
                    nm = roster.get(s["playerId"])
                    pid = name_to_pid.get(_norm(nm)) if nm else None
                    if pid:
                        scored.add(pid)
        scorers[(hid, aid)] = scored
    return pd.DataFrame(results), scorers


def grade(round_no: int, season: int) -> pd.DataFrame:
    """Settle the round's predictions against final scores + tryscorers."""
    label = f"Round {round_no}"
    res, scorers = _results_and_scorers(season, round_no)
    if res.empty:
        print(f"{label}: no completed games to grade")
        return pd.DataFrame()
    con = _conn()
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    rmap = {(r.home_id, r.away_id): r for r in res.itertuples(index=False)}
    with con:
        preds = pd.read_sql("SELECT * FROM predictions WHERE round=? AND settled_at IS NULL",
                            con, params=(label,))
        for p in preds.itertuples(index=False):
            r = rmap.get((p.home_id, p.away_id))
            if r is None:
                continue
            margin = r.home_score - r.away_score
            actual = correct = error = brier = None
            if p.market == "win":
                winner = p.home_id if margin > 0 else (p.away_id if margin < 0 else None)
                y_home = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
                actual = 1.0 if p.selection == winner else (0.5 if winner is None else 0.0)
                correct = int(p.selection == winner) if winner else None
                brier = (p.prob - y_home) ** 2 if p.prob is not None else None
            elif p.market == "margin":
                actual = margin
                error = p.point - margin
            elif p.market == "total":
                actual = r.home_score + r.away_score
                error = p.point - actual
            elif p.market == "tryscorer":
                sc = scorers.get((p.home_id, p.away_id))
                if sc is None:
                    continue  # scorers unavailable; leave unsettled for a re-grade
                hit = 1 if (p.player_id and int(p.player_id) in sc) else 0
                actual, correct = float(hit), hit
                brier = (p.prob - hit) ** 2 if p.prob is not None else None
            con.execute("UPDATE predictions SET actual=?, correct=?, error=?, brier=?, "
                        "settled_at=? WHERE id=?",
                        (actual, correct,
                         None if error is None else round(float(error), 2),
                         None if brier is None else round(float(brier), 4), now, p.id))
    _mirror(con)
    write_summary()
    return pd.read_sql("SELECT * FROM predictions WHERE round=?", con, params=(label,))


def summary() -> dict:
    df = pd.read_sql("SELECT * FROM predictions", _conn())
    s = df[df["settled_at"].notna()]

    def block(market):
        m = s[s["market"] == market]
        if m.empty:
            return {"n": 0}
        out = {"n": int(len(m))}
        if market in ("win", "tryscorer"):
            gr = m.dropna(subset=["correct"])
            out["hits"] = int(gr["correct"].sum())
            out["hit_rate"] = round(gr["correct"].mean(), 3) if len(gr) else None
            out["brier"] = round(m["brier"].dropna().mean(), 4) if m["brier"].notna().any() else None
        else:
            out["mae"] = round(m["error"].abs().mean(), 2)
            out["bias"] = round(m["error"].mean(), 2)  # + => model over-predicts
        return out

    per_round = []
    for rnd, g in s.groupby("round"):
        w = g[g["market"] == "win"].dropna(subset=["correct"])
        ts = g[g["market"] == "tryscorer"].dropna(subset=["correct"])
        tot = g[g["market"] == "total"]
        per_round.append({
            "round": rnd,
            "win_hits": f"{int(w['correct'].sum())}/{len(w)}" if len(w) else "—",
            "win_brier": round(w["brier"].mean(), 3) if len(w) and w["brier"].notna().any() else None,
            "tryscorer_hits": f"{int(ts['correct'].sum())}/{len(ts)}" if len(ts) else "—",
            "total_mae": round(tot["error"].abs().mean(), 1) if len(tot) else None,
        })
    return {"win": block("win"), "margin": block("margin"),
            "total": block("total"), "tryscorer": block("tryscorer"),
            "per_round": per_round,
            "updated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")}


def write_summary() -> Path:
    OUT.mkdir(exist_ok=True)
    (OUT / "track_record.json").write_text(json.dumps(summary(), indent=1, default=str))
    return OUT / "track_record.json"


def print_summary() -> None:
    s = summary()
    w, ts = s["win"], s["tryscorer"]
    print("== Prediction track record ==")
    if w["n"]:
        print(f"  Win:       {w.get('hits')}/{w['n']} correct ({w.get('hit_rate'):.0%}), "
              f"Brier {w.get('brier')}")
    if ts["n"]:
        print(f"  Tryscorer: {ts.get('hits')}/{ts['n']} top-pick hit ({ts.get('hit_rate'):.0%}), "
              f"Brier {ts.get('brier')}")
    if s["margin"]["n"]:
        print(f"  Margin:    MAE {s['margin']['mae']} pts (bias {s['margin']['bias']:+})")
    if s["total"]["n"]:
        print(f"  Total:     MAE {s['total']['mae']} pts (bias {s['total']['bias']:+})")
    if not w["n"]:
        print("  (nothing settled yet — snapshot a round, then grade after it's played)")


if __name__ == "__main__":
    print_summary()
