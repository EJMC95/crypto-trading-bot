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

    m = preds.merge(cons, on=["home_id", "away_id"], how="left")
    m["edge_home"] = m["p_home_blend"] - m["market_p_home"]
    pick_home = m["edge_home"] >= 0
    m["value_side"] = np.where(pick_home, m["home"], m["away"])
    m["value_p_model"] = np.where(pick_home, m["p_home_blend"], 1 - m["p_home_blend"])
    m["value_best_odds"] = np.where(pick_home, m["best_odds_home"], m["best_odds_away"])
    m["value_ev_pct"] = (m["value_p_model"] * m["value_best_odds"] - 1) * 100
    cols = ["round", "date", "home", "away", "p_home_blend", "market_p_home",
            "edge_home", "books", "best_odds_home", "best_odds_away",
            "value_side", "value_ev_pct"]
    market = m[cols].round(4)
    market.to_csv(OUT / "round_market.csv", index=False)
    print(market.to_string(index=False))

    led_odds = cons.rename(columns={"median_odds_home": "odds_home",
                                    "median_odds_away": "odds_away"})
    led_odds["book"] = "consensus(" + led_odds["books"].astype(str) + ")"
    entries = ledger.log_round(
        preds.rename(columns={"p_home_blend": "p_home_blend"}), led_odds, model="blend")
    print(f"ledger: {len(entries)} rows logged -> {ledger.LEDGER}")

    notion_preview.build()
    dashboard_feed.build()
    print("preview + nrl.json refreshed with market columns")


if __name__ == "__main__":
    main()
