"""Paper ledger (Build Spec §7) — every hypothetical bet logged.

Mirrors the bot-fleet ledger discipline: one append-only CSV row per (match, model
snapshot), written when a round preview is generated, settled after the round. CLV
is graded against the aussportsbetting closing price when the weekly file refresh
lands (or a near-kickoff snapshot from the live feed, whichever exists).

Columns:
  logged_at, round, date, home_id, away_id, model, p_home_model,
  book, odds_home, odds_away, market_p_home (de-vig),
  pick, pick_p_model, pick_odds, edge (p_model - p_market on the pick),
  result (H/A/D, blank until settled), pick_won, clv_close_odds, clv_pct
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "outputs" / "paper_ledger.csv"

COLS = ["logged_at", "round", "date", "home_id", "away_id", "model", "p_home_model",
        "book", "odds_home", "odds_away", "market_p_home", "pick", "pick_p_model",
        "pick_odds", "edge", "result", "pick_won", "clv_close_odds", "clv_pct"]


_STR_COLS = ["logged_at", "round", "date", "home_id", "away_id", "model", "book",
             "pick", "result"]


def _load() -> pd.DataFrame:
    if LEDGER.exists():
        df = pd.read_csv(LEDGER)
    else:
        df = pd.DataFrame(columns=COLS)
    # all-NaN string columns come back float64 from CSV; keep them assignable
    for c in _STR_COLS:
        df[c] = df[c].astype("object")
    return df


def log_round(preds: pd.DataFrame, odds: pd.DataFrame | None, model: str = "blend") -> pd.DataFrame:
    """preds: round_predictions.csv frame; odds: live snapshot (book, home_id,
    away_id, odds_home, odds_away) or None when no feed was reachable."""
    led = _load()
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    rows = []
    for r in preds.itertuples(index=False):
        p = getattr(r, f"p_home_{model}", np.nan)
        row = {c: np.nan for c in COLS}
        row.update({"logged_at": now, "round": r.round, "date": r.date,
                    "home_id": r.home_id, "away_id": r.away_id,
                    "model": model, "p_home_model": p})
        if odds is not None and len(odds):
            m = odds[(odds["home_id"] == r.home_id) & (odds["away_id"] == r.away_id)]
            if len(m):
                m = m.iloc[0]
                inv = 1 / m["odds_home"] + 1 / m["odds_away"]
                mp = (1 / m["odds_home"]) / inv
                pick_home = p >= mp  # value side, not just favourite
                row.update({
                    "book": m["book"], "odds_home": m["odds_home"],
                    "odds_away": m["odds_away"], "market_p_home": round(mp, 4),
                    "pick": r.home_id if pick_home else r.away_id,
                    "pick_p_model": round(p if pick_home else 1 - p, 4),
                    "pick_odds": m["odds_home"] if pick_home else m["odds_away"],
                    "edge": round((p - mp) if pick_home else (mp - p), 4),
                })
        rows.append(row)
    # Idempotent per (round, match, model): re-logging a round replaces its rows.
    new = pd.DataFrame(rows)
    key = ["round", "home_id", "away_id", "model"]
    led = led[~led.set_index(key).index.isin(new.set_index(key).index)]
    led = pd.concat([led, new], ignore_index=True)[COLS]
    LEDGER.parent.mkdir(exist_ok=True)
    led.to_csv(LEDGER, index=False)
    return new


def settle(results: pd.DataFrame) -> pd.DataFrame:
    """results: (round, home_id, away_id, home_score, away_score). Fills result /
    pick_won for matching unsettled rows."""
    led = _load()
    for r in results.itertuples(index=False):
        mask = ((led["round"] == r.round) & (led["home_id"] == r.home_id)
                & (led["away_id"] == r.away_id) & led["result"].isna())
        outcome = "H" if r.home_score > r.away_score else ("A" if r.away_score > r.home_score else "D")
        led.loc[mask, "result"] = outcome
        winner = {"H": led.loc[mask, "home_id"], "A": led.loc[mask, "away_id"]}.get(outcome)
        if winner is not None:
            led.loc[mask, "pick_won"] = (led.loc[mask, "pick"] == winner).astype(float)
        else:
            led.loc[mask, "pick_won"] = 0.5
    led.to_csv(LEDGER, index=False)
    return led


if __name__ == "__main__":
    print(_load().tail(20).to_string())
