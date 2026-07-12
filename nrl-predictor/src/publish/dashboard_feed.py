"""Build the nrl.json dashboard feed (Build Spec §8).

Same pattern as the trading fleet's pnl.json: a single static JSON the interactive
dashboard artifact reads. Serve it from a small Railway static service later
(Phase 5); for now the file lands in outputs/ and ships with the repo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"


def build() -> Path:
    preds = pd.read_csv(OUT / "round_predictions.csv")
    ratings = pd.read_csv(OUT / "ratings_2026.csv")
    market_path = OUT / "round_market.csv"
    market = pd.read_csv(market_path).to_dict(orient="records") if market_path.exists() else []
    props_path, sgm_path = OUT / "round_props.csv", OUT / "round_sgm.csv"
    props = pd.read_csv(props_path).to_dict(orient="records") if props_path.exists() else []
    sgm = pd.read_csv(sgm_path).to_dict(orient="records") if sgm_path.exists() else []
    import json as _json
    sig = _json.loads((OUT / "round_signals_applied.json").read_text()).get("games", []) \
        if (OUT / "round_signals_applied.json").exists() else []
    track = _json.loads((OUT / "track_record.json").read_text()) \
        if (OUT / "track_record.json").exists() else None
    feed = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "nrl-predictor",
        "disclaimer": "Paper-track model output. Not betting advice.",
        "round": preds["round"].iloc[0] if len(preds) else None,
        "predictions": preds.to_dict(orient="records"),
        "market": market,
        "props": props,
        "sgm_candidates": sgm,
        "signals": sig,
        "track_record": track,
        "ratings": ratings.to_dict(orient="records"),
        "models": {
            "elo": "tier 1 — K=10 (MOV-scaled), home adv 60, Platt-calibrated",
            "poisson": "tier 2 — DC-decay try Poisson (xi=1.4), MC scores",
            "gbm": "tier 3 — LightGBM stack (experimental, not in blend)",
            "blend": "logistic stack of elo+poisson, weights fit 2010-2014",
        },
        "validation": {
            "window": "walk-forward 2015-2025",
            "brier": {"naive": 0.2456, "elo_cal": 0.2194, "blend": 0.2188,
                      "market_devig_close": 0.2075},
        },
    }
    path = OUT / "nrl.json"
    path.write_text(json.dumps(feed, indent=1, default=str))
    return path


if __name__ == "__main__":
    print(f"feed -> {build()}")
