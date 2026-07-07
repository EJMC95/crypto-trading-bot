"""Phase 1 end-to-end: ingest -> tune -> walk-forward backtest -> current ratings
and calibrated probabilities for the upcoming round.

Writes to outputs/:
- phase1_report.md        — backtest vs naive baseline + de-vigged closing line
- elo_tuning.csv          — full grid-search table (tune window 2006–2014 only)
- ratings_2026.csv        — current team Elo ratings
- round_predictions.csv   — upcoming-round calibrated probabilities
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval import backtest as bt
from src.ingest import nrl_stats, results_history, teams
from src.models.match_elo import EloModel, final_ratings, run_elo

OUT = ROOT / "outputs"


def main() -> None:
    OUT.mkdir(exist_ok=True)

    print("== ingest ==")
    odds = results_history.build()
    print(f"aussportsbetting: {len(odds)} matches {odds['date'].min()} -> {odds['date'].max()}")
    res = nrl_stats.build()
    matches, fixtures = res["matches"], res["fixtures_next"]
    print(f"matches: {len(matches)} {matches['date'].min().date()} -> {matches['date'].max().date()}")
    if not fixtures.empty:
        print(f"next round: {fixtures['round'].iloc[0]} ({len(fixtures)} games)")

    print("== tune (2006–2014 only) ==")
    params, grid = bt.tune(matches)
    grid.to_csv(OUT / "elo_tuning.csv", index=False)
    print("best params:", params)

    print("== walk-forward eval 2015–2025 ==")
    pred = run_elo(matches, params)
    pred = bt.attach_market(pred, odds)
    pred["p_naive"] = bt.naive_baseline(pred)

    # Calibrate Elo probs on the tune window only, apply out-of-sample.
    tune_mask = pred["year"].isin(bt.TUNE_YEARS)
    iso = bt.fit_calibrator(pred.loc[tune_mask, "p_home"].to_numpy(),
                            bt.outcome(pred.loc[tune_mask]))
    pred["p_elo_cal"] = iso.predict(pred["p_home"].to_numpy())

    ev = pred[pred["year"].isin(bt.EVAL_YEARS)].copy()
    cols = {"elo": "p_home", "elo_cal": "p_elo_cal", "naive": "p_naive",
            "market": "market_p_home"}
    seasons = bt.season_table(ev, cols)

    y = bt.outcome(ev)
    overall = {label: (bt.brier(ev[c].dropna().to_numpy(), y[ev[c].notna()]),
                       bt.log_loss(ev[c].dropna().to_numpy(), y[ev[c].notna()]))
               for label, c in cols.items()}
    market_cov = ev["market_p_home"].notna().mean()

    # Head-to-head on the subset where the market prob exists.
    mk = ev[ev["market_p_home"].notna()]
    ym = bt.outcome(mk)
    h2h = {label: (bt.brier(mk[c].to_numpy(), ym), bt.log_loss(mk[c].to_numpy(), ym))
           for label, c in cols.items()}

    rel = bt.reliability_table(ev["p_elo_cal"].to_numpy(), y)

    print("== current ratings + upcoming round ==")
    model, ratings = final_ratings(matches, params)
    ratings["team"] = ratings["team_id"].map(teams.id_to_name())
    # Drop sides that no longer exist in the current comp (relegated to history).
    current_ids = set(matches[matches["year"] >= matches["year"].max() - 1]["home_id"])
    ratings = ratings[ratings["team_id"].isin(current_ids)].reset_index(drop=True)
    ratings.index += 1
    ratings.to_csv(OUT / "ratings_2026.csv", index_label="rank")
    print(ratings.to_string())

    preds_rows = []
    if not fixtures.empty:
        for fx in fixtures.itertuples(index=False):
            p_raw = model.p_home(fx.home_id, fx.away_id)
            preds_rows.append({
                "round": fx.round, "date": fx.date, "venue": fx.venue,
                "home": teams.id_to_name()[fx.home_id],
                "away": teams.id_to_name()[fx.away_id],
                "elo_home": round(model.rating(fx.home_id), 1),
                "elo_away": round(model.rating(fx.away_id), 1),
                "p_home_raw": round(p_raw, 4),
                "p_home_cal": round(float(iso.predict([p_raw])[0]), 4),
            })
        pd.DataFrame(preds_rows).to_csv(OUT / "round_predictions.csv", index=False)

    write_report(params, seasons, overall, h2h, market_cov, rel, ratings,
                 pd.DataFrame(preds_rows), matches)
    print(f"report -> {OUT / 'phase1_report.md'}")


def write_report(params, seasons, overall, h2h, market_cov, rel, ratings,
                 round_preds, matches) -> None:
    fmt = lambda t: f"{t[0]:.4f} / {t[1]:.4f}"
    lines = [
        "# Phase 1 report — Elo walk-forward backtest",
        "",
        f"_Generated {pd.Timestamp.now():%Y-%m-%d}. Matches replayed: "
        f"{len(matches)} ({matches['date'].min().date()} → {matches['date'].max().date()}). "
        "Draws score 0.5; log loss uses half-credit form._",
        "",
        "## Fitted parameters (grid-searched on 2006–2014 predictions only)",
        "",
        f"- K = {params.k}, home advantage = {params.home_adv} Elo "
        f"(≈ {params.home_adv / 25:.1f} points), pre-season regression = {params.regress:.0%}, "
        f"logistic scale = {params.scale}, MOV cap = {params.mov_cap}",
        "",
        "## Overall 2015–2025 (Brier / log loss)",
        "",
        "| model | all eval games | odds-matched subset |",
        "|---|---|---|",
    ]
    for label in ("naive", "elo", "elo_cal", "market"):
        lines.append(f"| {label} | {fmt(overall[label])} | {fmt(h2h[label])} |")
    lines += [
        "",
        f"_Market coverage: {market_cov:.1%} of eval games have a de-vigged closing/avg "
        "price (aussportsbetting file ends 2025-08 in the current capture)._",
        "",
        "## Per-season",
        "",
        seasons.round(4).to_markdown(index=False),
        "",
        "## Reliability (calibrated Elo, 2015–2025)",
        "",
        rel.round(3).to_markdown(index=False),
        "",
        "## Current ratings",
        "",
        ratings.round(1).to_markdown(),
    ]
    if not round_preds.empty:
        lines += ["", "## Upcoming round", "", round_preds.to_markdown(index=False)]
    (OUT / "phase1_report.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
