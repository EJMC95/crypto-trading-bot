"""Phase 3 end-to-end: Poisson/Skellam (tier 2) + GBM stack (tier 3) + blend,
walk-forward 2015–2025 against Elo, the naive baseline and the de-vigged closing
line; then live predictions (win/margin/total) for the upcoming round.

Writes to outputs/:
- phase3_report.md      — model comparison + reliability
- round_predictions.csv — upgraded: all model probs + expected margin/total
- model_probs_eval.parquet — per-game walk-forward probabilities (for CLV work)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval import backtest as bt
from src.features.team_form import build_features
from src.ingest import teams
from src.models import match_gbm
from src.models.match_elo import EloModel, EloParams, run_elo
from src.models.match_poisson import (PoissonParams, TryModel, long_format,
                                      team_scoring_table, walk_forward)

OUT = ROOT / "outputs"
PROCESSED = ROOT / "data" / "processed"

ELO_PARAMS = EloParams(k=10.0, home_adv=60.0, regress=0.33, scale=400.0, mov_cap=3.0)
POIS_START = 2008        # early enough that decay/stack choices are made pre-2015
POIS_TUNE_YEARS = range(2010, 2015)  # 2 burn-in years after POIS_START
XI_GRID = [0.7, 1.0, 1.4]


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def inv_logit(z):
    return 1.0 / (1.0 + np.exp(-z))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    odds = pd.read_parquet(PROCESSED / "matches_odds.parquet")
    pm = pd.read_parquet(PROCESSED / "player_matches.parquet")
    pm = pm[pm["match_id"].isin(matches["match_id"].dropna())]

    print("== tier 1: Elo replay ==")
    pred = run_elo(matches, ELO_PARAMS)

    print("== tier 2: Poisson walk-forward (refit per round) ==")
    scoring = team_scoring_table(pm, teams)
    long_rows = long_format(matches, scoring)
    print(f"long rows: {len(long_rows)} team-matches with try detail")

    # Tune the decay rate on pre-2015 predictions only.
    tune_target = matches[matches["year"].isin(POIS_TUNE_YEARS)]
    y_tune = bt.outcome(tune_target)
    best_xi, best_ll = None, np.inf
    for xi in XI_GRID:
        wf = walk_forward(tune_target.assign(p_home=np.nan), long_rows,
                          PoissonParams(decay_xi=xi), start_year=min(POIS_TUNE_YEARS))
        ll = bt.log_loss(wf["p_pois"].to_numpy(), y_tune)
        print(f"  xi={xi}: tune log loss {ll:.4f}")
        if ll < best_ll:
            best_ll, best_xi = ll, xi
    pois_params = PoissonParams(decay_xi=best_xi)
    print(f"decay xi = {best_xi}")

    pred = walk_forward(pred, long_rows, pois_params, start_year=POIS_START)
    cov = pred.loc[pred["year"] >= POIS_START, "p_pois"].notna().mean()
    print(f"poisson coverage {POIS_START}+: {cov:.1%}")

    print("== tier 3: GBM walk-forward by season ==")
    feats = build_features(pred)
    pred = match_gbm.walk_forward(pred, feats, bt.EVAL_YEARS)

    # Elo calibration (tune window), as in Phase 1.
    tune_mask = pred["year"].isin(bt.TUNE_YEARS)
    elo_cal = bt.fit_calibrator(pred.loc[tune_mask, "p_home"].to_numpy(),
                                bt.outcome(pred.loc[tune_mask]))
    pred["p_elo_cal"] = elo_cal.predict(pred["p_home"].to_numpy())

    # Stack: logistic regression on [logit(elo), logit(pois)], weights learned on
    # the pre-2015 tune window (GBM has no pre-2015 out-of-sample output to stack
    # on, so it stays a reported model rather than a blend member for now).
    from sklearn.linear_model import LogisticRegression
    stack_rows = pred["year"].isin(POIS_TUNE_YEARS) & pred["p_pois"].notna()
    y_stack = bt.outcome(pred[stack_rows])
    nd = y_stack != 0.5
    Xs = np.column_stack([logit(pred.loc[stack_rows, "p_elo_cal"]),
                          logit(pred.loc[stack_rows, "p_pois"])])
    stack = LogisticRegression(C=10.0).fit(Xs[nd], y_stack[nd].astype(int))
    print("stack weights (elo, pois):", np.round(stack.coef_[0], 3),
          "intercept:", round(float(stack.intercept_[0]), 3))

    # Persist the fitted blend so the season-wide predictor can apply it to every
    # remaining fixture without retraining (scripts/predict_season.py).
    import json as _json
    (OUT / "model_artifacts.json").write_text(_json.dumps({
        "elo_params": ELO_PARAMS.__dict__,
        "pois_xi": float(best_xi),
        "platt_coef": float(elo_cal.lr.coef_[0][0]),
        "platt_intercept": float(elo_cal.lr.intercept_[0]),
        "stack_coef": [float(c) for c in stack.coef_[0]],
        "stack_intercept": float(stack.intercept_[0]),
    }, indent=1))
    have = pred["p_pois"].notna()
    pred["p_blend"] = pred["p_elo_cal"].copy()
    pred.loc[have, "p_blend"] = stack.predict_proba(
        np.column_stack([logit(pred.loc[have, "p_elo_cal"]),
                         logit(pred.loc[have, "p_pois"])]))[:, 1]

    pred = bt.attach_market(pred, odds)
    pred["p_naive"] = bt.naive_baseline(pred)

    ev = pred[pred["year"].isin(bt.EVAL_YEARS)].copy()
    cols = {"naive": "p_naive", "elo_cal": "p_elo_cal", "poisson": "p_pois",
            "gbm": "p_gbm", "blend": "p_blend", "market": "market_p_home"}
    seasons = bt.season_table(ev, cols)
    y = bt.outcome(ev)
    overall, h2h = {}, {}
    mk = ev[ev["market_p_home"].notna() & ev["p_gbm"].notna()]
    ym = bt.outcome(mk)
    for label, c in cols.items():
        m1 = ev[c].notna()
        overall[label] = (bt.brier(ev.loc[m1, c].to_numpy(), y[m1]),
                          bt.log_loss(ev.loc[m1, c].to_numpy(), y[m1]))
        h2h[label] = (bt.brier(mk[c].to_numpy(), ym), bt.log_loss(mk[c].to_numpy(), ym))

    ev[["date", "year", "round", "home_id", "away_id", "home_score", "away_score",
        "p_naive", "p_elo_cal", "p_pois", "p_gbm", "p_blend", "market_p_home"]].to_parquet(
        OUT / "model_probs_eval.parquet", index=False)

    print("== live predictions: upcoming round ==")
    fixtures = pd.read_parquet(PROCESSED / "fixtures_next.parquet")
    rows = live_round(matches, pred, feats, long_rows, fixtures, elo_cal,
                      pois_params, stack)
    round_df = pd.DataFrame(rows)
    round_df.to_csv(OUT / "round_predictions.csv", index=False)
    print(round_df.to_string(index=False))

    rel = bt.reliability_table(ev.loc[ev["p_blend"].notna(), "p_blend"].to_numpy(),
                               bt.outcome(ev[ev["p_blend"].notna()]))
    write_report(seasons, overall, h2h, rel, round_df, len(mk))
    print(f"report -> {OUT / 'phase3_report.md'}")


def live_round(matches, pred, feats, long_rows, fixtures, elo_cal,
               pois_params, stack) -> list[dict]:
    asof = pd.Timestamp.now()
    # Elo state after all played games
    elo = EloModel(params=ELO_PARAMS)
    for r in matches.itertuples(index=False):
        elo.update(r.home_id, r.away_id, r.home_score, r.away_score, int(r.year))
    pois = TryModel(pois_params).fit(long_rows, asof)
    gbm, gbm_cal = match_gbm.fit_final(pred, feats)

    # Team-form state for fixture features: rebuild on matches + fixture stubs.
    stubs = fixtures.copy()
    stubs["home_score"] = np.nan
    stubs["away_score"] = np.nan
    stubs["is_finals"] = False
    stubs["year"] = stubs["date"].dt.year
    combined = pd.concat([pred, stubs], ignore_index=True)
    fx_feats = build_features(combined).iloc[len(pred):]

    rows = []
    for (idx, fx), (_, ff) in zip(stubs.iterrows(), fx_feats.iterrows()):
        p_elo = float(elo_cal.predict([elo.p_home(fx["home_id"], fx["away_id"])])[0])
        pp = pois.predict_match(fx["home_id"], fx["away_id"])
        feat_row = ff.copy()
        feat_row["elo_p"] = p_elo
        feat_row["pois_p"] = pp["p_home"]
        feat_row["pois_margin"] = pp["exp_margin"]
        feat_row["pois_total"] = pp["exp_total"]
        p_gbm = float(gbm_cal.predict(gbm.predict_proba(
            feat_row[fx_feats.columns].to_frame().T)[:, 1])[0])
        p_blend = float(stack.predict_proba(
            [[float(logit(p_elo)), float(logit(pp["p_home"]))]])[0, 1])
        rows.append({
            "round": fx["round"], "date": fx["date"], "venue": fx["venue"],
            "home": teams.id_to_name()[fx["home_id"]],
            "away": teams.id_to_name()[fx["away_id"]],
            "p_home_elo": round(p_elo, 4), "p_home_poisson": round(pp["p_home"], 4),
            "p_home_gbm": round(p_gbm, 4), "p_home_blend": round(p_blend, 4),
            "exp_margin_home": round(pp["exp_margin"], 1),
            "exp_total_points": round(pp["exp_total"], 1),
        })
    return rows


def write_report(seasons, overall, h2h, rel, round_df, n_h2h) -> None:
    fmt = lambda t: f"{t[0]:.4f} / {t[1]:.4f}"
    lines = [
        "# Phase 3 report — Poisson + GBM vs Elo and the closing line",
        "",
        f"_Generated {pd.Timestamp.now():%Y-%m-%d}. Walk-forward 2015–2025; Poisson "
        "refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains "
        "before every season on strictly-prior matches; stacked probability features "
        "are themselves walk-forward outputs. Draws score 0.5._",
        "",
        "## Overall 2015–2025 (Brier / log loss)",
        "",
        f"| model | all eval games | common subset (n={n_h2h}) |",
        "|---|---|---|",
    ]
    for label in ("naive", "elo_cal", "poisson", "gbm", "blend", "market"):
        lines.append(f"| {label} | {fmt(overall[label])} | {fmt(h2h[label])} |")
    lines += [
        "",
        "## Per-season",
        "",
        seasons.round(4).to_markdown(index=False),
        "",
        "## Reliability (blend, 2015–2025)",
        "",
        rel.round(3).to_markdown(index=False),
        "",
        "## Upcoming round — all models",
        "",
        round_df.to_markdown(index=False),
        "",
        "_Margin/total expectations come from the tier-2 Monte Carlo; the blend is "
        "a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. "
        "GBM is reported but not blended (no pre-2015 out-of-sample output to learn "
        "a weight from) — revisit when lineup/weather features land in Phase 5._",
    ]
    (OUT / "phase3_report.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
