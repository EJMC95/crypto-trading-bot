"""Capture a live odds snapshot, compare with model predictions, log the paper
ledger, and refresh the market-aware outputs.

Writes:
- outputs/round_market.csv  — fixture × (blend prob, consensus market prob, edge,
  best prices, EV at best price)
- outputs/paper_ledger.csv  — one blend-model row per fixture (idempotent per round)
Then re-runs the preview + nrl.json builders so both carry market columns.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval import ledger
from src.ingest import odds_live, teams
from src.publish import dashboard_feed, notion_preview

OUT = ROOT / "outputs"
PROCESSED = ROOT / "data" / "processed"


def main() -> None:
    snap = odds_live.snapshot()
    if snap.empty:
        print("no odds available — market columns skipped")
        return
    cons = odds_live.consensus(snap)

    preds = pd.read_csv(OUT / "round_predictions.csv")
    name_to_id = {v: k for k, v in teams.id_to_name().items()}
    preds["home_id"] = preds["home"].map(name_to_id)
    preds["away_id"] = preds["away"].map(name_to_id)

    # persist this snapshot to the odds-history store (line movement / steam)
    odds_live.append_history(cons)
    move = odds_live.line_movement()

    m = preds.merge(cons, on=["home_id", "away_id"], how="left")
    if len(move):
        m = m.merge(move[["home_id", "away_id", "move_home_pp", "steam", "drift_side"]],
                    on=["home_id", "away_id"], how="left")
    m["edge_home"] = m["p_home_blend"] - m["market_p_home"]
    pick_home = m["edge_home"] >= 0
    m["value_side"] = np.where(pick_home, m["home"], m["away"])
    m["value_p_model"] = np.where(pick_home, m["p_home_blend"], 1 - m["p_home_blend"])
    m["value_best_odds"] = np.where(pick_home, m["best_odds_home"], m["best_odds_away"])
    m["value_ev_pct"] = (m["value_p_model"] * m["value_best_odds"] - 1) * 100
    cols = ["round", "date", "home", "away", "p_home_blend", "market_p_home",
            "edge_home", "books", "best_odds_home", "best_odds_away",
            "disp_home", "disp_away", "value_side", "value_ev_pct"]
    for opt in ("move_home_pp", "steam", "drift_side"):
        if opt in m:
            cols.append(opt)
    market = m[[c for c in cols if c in m]].round(4)
    market.to_csv(OUT / "round_market.csv", index=False)
    print(market.to_string(index=False))

    rows = []
    for r in m.itertuples(index=False):
        if pd.isna(r.market_p_home):
            continue
        pick_home = r.edge_home >= 0
        sel = r.home_id if pick_home else r.away_id
        prob = r.p_home_blend if pick_home else 1 - r.p_home_blend
        price = r.median_odds_home if pick_home else r.median_odds_away
        rows.append({
            "round": r.round, "date": str(r.date), "home_id": r.home_id,
            "away_id": r.away_id, "market": "h2h", "selection": sel,
            "model": "blend", "model_prob": round(float(prob), 4),
            "model_fair_price": round(1 / float(prob), 3),
            "market_price_at_log": float(price),
        })
    n = ledger.log_bets(rows)
    print(f"ledger: {n} h2h rows logged -> {ledger.DB}")

    # closing-line capture: stamp the current best price as the rolling close for
    # every open bet this round + recompute CLV. Last run before kickoff = close.
    if len(m):
        rnd_label = str(m["round"].iloc[0])
        nc = ledger.update_closing(rnd_label, cons)
        print(f"ledger: closing line updated on {nc} open bets ({rnd_label})")

    notion_preview.build()
    dashboard_feed.build()
    print("preview + nrl.json refreshed with market columns")


if __name__ == "__main__":
    main()
