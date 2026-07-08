"""Paper ledger v2 (Build Spec §7) — every hypothetical bet logged, SQLite-backed.

Mirrors the trading-fleet ledger discipline. One row per (round, match, market,
selection, model). Flat 1-unit paper stakes. `closing_price` stays NULL until a
closing source exists for that market (near-kickoff snapshot from the live feed,
or the weekly aussportsbetting refresh for h2h).

Storage: SQLite at data/ledger.db (durable) with a parquet mirror at
data/processed/ledger.parquet and a CSV mirror at outputs/paper_ledger.csv so the
ledger stays readable in the repo.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "ledger.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round TEXT NOT NULL,
    date TEXT,
    home_id TEXT NOT NULL,
    away_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'h2h',      -- h2h | line | total | prop | sgm
    selection TEXT NOT NULL,                 -- team_id, player name, 'over 44.5', ...
    model TEXT NOT NULL,
    model_prob REAL,
    model_fair_price REAL,
    market_price_at_log REAL,
    closing_price REAL,
    stake_units REAL NOT NULL DEFAULT 1.0,
    result TEXT,                             -- W | L | P (push/draw-refund)
    pnl_units REAL,
    clv REAL,                                -- market_price_at_log/closing_price - 1
    logged_at TEXT NOT NULL,
    settled_at TEXT,
    UNIQUE(round, home_id, away_id, market, selection, model)
);
"""


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(SCHEMA)
    return con


def _mirror(con: sqlite3.Connection) -> None:
    df = pd.read_sql("SELECT * FROM bets ORDER BY logged_at, id", con)
    (ROOT / "data" / "processed").mkdir(parents=True, exist_ok=True)
    df.to_parquet(ROOT / "data" / "processed" / "ledger.parquet", index=False)
    (ROOT / "outputs").mkdir(exist_ok=True)
    df.to_csv(ROOT / "outputs" / "paper_ledger.csv", index=False)


def log_bets(rows: list[dict]) -> int:
    """Upsert unsettled bets; settled rows are never overwritten."""
    con = _conn()
    n = 0
    with con:
        for r in rows:
            r.setdefault("market", "h2h")
            r.setdefault("stake_units", 1.0)
            r.setdefault("logged_at", pd.Timestamp.now().isoformat(timespec="seconds"))
            existing = con.execute(
                "SELECT settled_at FROM bets WHERE round=? AND home_id=? AND away_id=? "
                "AND market=? AND selection=? AND model=?",
                (r["round"], r["home_id"], r["away_id"], r["market"], r["selection"], r["model"]),
            ).fetchone()
            if existing and existing[0]:
                continue
            cols = ["round", "date", "home_id", "away_id", "market", "selection", "model",
                    "model_prob", "model_fair_price", "market_price_at_log",
                    "closing_price", "stake_units", "logged_at"]
            con.execute(
                f"INSERT INTO bets ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
                "ON CONFLICT(round, home_id, away_id, market, selection, model) DO UPDATE SET "
                "model_prob=excluded.model_prob, model_fair_price=excluded.model_fair_price, "
                "market_price_at_log=excluded.market_price_at_log, logged_at=excluded.logged_at",
                [r.get(c) for c in cols],
            )
            n += 1
    _mirror(con)
    return n


def settle_h2h(round_label: str, results: pd.DataFrame) -> pd.DataFrame:
    """results: home_id, away_id, home_score, away_score. Settles the round's h2h
    rows; returns the round's frame."""
    con = _conn()
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    with con:
        for r in results.itertuples(index=False):
            winner = (r.home_id if r.home_score > r.away_score
                      else (r.away_id if r.away_score > r.home_score else None))
            rows = con.execute(
                "SELECT id, selection, market_price_at_log, stake_units FROM bets "
                "WHERE round=? AND home_id=? AND away_id=? AND market='h2h' "
                "AND settled_at IS NULL",
                (round_label, r.home_id, r.away_id),
            ).fetchall()
            for bid, sel, price, stake in rows:
                if winner is None:
                    res, pnl = "P", 0.0
                elif sel == winner:
                    res, pnl = "W", stake * ((price or 1) - 1)
                else:
                    res, pnl = "L", -stake
                con.execute("UPDATE bets SET result=?, pnl_units=?, settled_at=? WHERE id=?",
                            (res, round(pnl, 3), now, bid))
    _mirror(con)
    return pd.read_sql("SELECT * FROM bets WHERE round=? AND market='h2h'",
                       con, params=(round_label,))


def load() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM bets ORDER BY logged_at, id", _conn())


def summary(round_label: str | None = None) -> str:
    df = load()
    if round_label:
        df = df[df["round"] == round_label]
    settled = df[df["settled_at"].notna()]
    lines = [f"Paper ledger — {round_label or 'all rounds'}: "
             f"{len(df)} bets, {len(settled)} settled"]
    if len(settled):
        w = int((settled["result"] == "W").sum())
        l = int((settled["result"] == "L").sum())
        p = int((settled["result"] == "P").sum())
        rec = f"{w}-{l}" + (f"-{p}P" if p else "")
        staked = settled["stake_units"].sum()
        pnl = settled["pnl_units"].sum()
        lines.append(f"Record {rec} | P&L {pnl:+.2f}u on {staked:.0f}u staked "
                     f"({pnl / max(staked, 1):+.1%} ROI)")
    return "\n".join(lines)
