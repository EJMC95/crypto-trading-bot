"""Season-wide predictions for every remaining round (self-updating).

Reuses the fitted blend saved by run_phase3 (outputs/model_artifacts.json) so no
retraining: applies Elo (Platt-calibrated) + Poisson stacked probability, expected
margin and total to EVERY unplayed fixture, plus provisional top tryscorers (the
per-player ATS marginal is analytic — 1-exp(-share·λ) — so covering the whole
season is cheap; the 50k joint sim is only needed for SGM correlation, which stays
on the current round).

On-the-day quality scales with proximity:
- current round : full data merged in (market value, SGM, confirmed team lists,
  weather) from the round_* CSVs the other pipeline steps produce.
- near rounds    : Open-Meteo weather where inside the 16-day forecast horizon.
- far rounds     : self-updating baseline — ratings shift every run as results land.

Output: outputs/season_predictions.json  { rounds:[{round, round_no, actionable,
games:[...]}], current_round, generated }.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features import player_rates, player_value, signal_adjust, xstats_defence
from src.ingest import signals as signals_mod
from src.ingest import teams
from src.models import props_player
from src.models.match_elo import EloModel, EloParams
from src.models.match_poisson import (PoissonParams, TryModel, long_format,
                                      team_scoring_table)

OUT = ROOT / "outputs"
PROCESSED = ROOT / "data" / "processed"
WEATHER_HORIZON_DAYS = 15


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def _logit(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return np.log(p / (1 - p))


def main() -> None:
    art = json.loads((OUT / "model_artifacts.json").read_text())
    elo_params = EloParams(**art["elo_params"])
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    pm = pd.read_parquet(PROCESSED / "player_matches.parquet")
    pm = pm[pm["match_id"].isin(matches["match_id"].dropna())]
    names = teams.id_to_name()
    player_names = dict(pd.read_csv(
        ROOT / "data" / "raw" / "uselessnrlstats" / "player_data.csv",
        low_memory=False)[["player_id", "full_name"]].values)

    # fit Elo (final ratings) + Poisson try model as of now
    elo = EloModel(params=elo_params)
    for r in matches.itertuples(index=False):
        elo.update(r.home_id, r.away_id, r.home_score, r.away_score, int(r.year))
    hist = player_rates.player_history(matches, pm, teams)
    scoring = team_scoring_table(pm, teams)
    long_rows = long_format(matches, scoring)
    asof = matches["date"].max() + pd.Timedelta(days=1)
    tmodel = TryModel(PoissonParams(decay_xi=art["pois_xi"])).fit(long_rows, asof)
    rates = player_rates.rates_asof(hist, asof)

    fixtures = pd.read_parquet(PROCESSED / "fixtures_all.parquet")
    current_round = int(fixtures["round_no"].min())
    sig_by = signal_adjust.signals_by_pair(signal_adjust.load_signals())

    # availability correction (Tier 1b): APM lineup strength moves the win prob
    apm = json.loads((OUT / "apm_values.json").read_text()) if (OUT / "apm_values.json").exists() else None
    apm_vals = {int(k): v for k, v in apm["values"].items()} if apm else {}

    # xStats opponent-defence correction (SGM sharpening): only active when the
    # phase-4 self-gate shipped it. Sharpens each side's expected tries -> every
    # tryscorer price in the match; identity when a team lacks a rating.
    xs = json.loads((OUT / "xstats_defence.json").read_text()) if (OUT / "xstats_defence.json").exists() else None
    xs_active = bool(xs and xs.get("passed"))
    xs_ratings = xstats_defence.build_ratings() if xs_active else None
    xs_norm = xs.get("norm") if xs else None

    def _lineup_ids(entry, side, team_id):
        sq = signal_adjust.named_squad(entry, side) if entry else None
        if sq is not None and len(sq):
            return sq["player_id"].dropna().tolist()
        return player_rates.squad_asof(hist, team_id, asof)["player_id"].dropna().tolist()

    # rich current-round data (already produced by the earlier pipeline steps)
    def _load(name):
        p = OUT / name
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    market, props_cur, sgm_cur = _load("round_market.csv"), _load("round_props.csv"), _load("round_sgm.csv")

    now = pd.Timestamp.now()
    rounds = []
    for rno, grp in fixtures.groupby("round_no"):
        rno = int(rno)
        actionable = rno == current_round
        games = []
        for fx in grp.itertuples(index=False):
            entry = sig_by.get((fx.home_id, fx.away_id))
            # weather: current round from the signal scan; near rounds fetched live
            wmult, _ = signal_adjust.weather_multiplier(entry or {})
            weather = (entry or {}).get("weather")
            if weather is None and (pd.Timestamp(fx.date) - now).days <= WEATHER_HORIZON_DAYS:
                weather = signals_mod.weather_at(fx.venue, None, pd.Timestamp(fx.date))
                if weather:
                    wmult, _ = signal_adjust.weather_multiplier({"weather": weather})

            # blend win prob
            p_elo_raw = elo.p_home(fx.home_id, fx.away_id)
            p_elo_cal = _sig(art["platt_coef"] * _logit(p_elo_raw) + art["platt_intercept"])
            pm_pred = tmodel.predict_match(fx.home_id, fx.away_id)
            mh = ma = 1.0
            if pm_pred:
                p_pois = pm_pred["p_home"]
                p_blend = _sig(art["stack_coef"][0] * _logit(p_elo_cal)
                               + art["stack_coef"][1] * _logit(p_pois)
                               + art["stack_intercept"])
                avail_effect = None
                if apm:
                    avail_raw = (player_value.lineup_value(_lineup_ids(entry, "home", fx.home_id), apm_vals)
                                 - player_value.lineup_value(_lineup_ids(entry, "away", fx.away_id), apm_vals))
                    p_corr = player_value.apply_avail(p_blend, avail_raw, apm["avail_beta"],
                                                      apm["avail_mu"], apm["avail_sd"])
                    avail_effect = {"lineup_diff": round(avail_raw, 1),
                                    "win_shift": round(p_corr - p_blend, 4)}
                    p_blend = p_corr
                if xs_active:
                    mh, ma = xstats_defence.matchup_multipliers(
                        xs_ratings, xs_norm, xs["coef"], fx.home_id, fx.away_id)
                margin = pm_pred["exp_margin"]
                total = pm_pred["exp_total"] * wmult
                lam_h = pm_pred["lam_tries_home"] * wmult * mh
                lam_a = pm_pred["lam_tries_away"] * wmult * ma
                margin_ci = [round(pm_pred["margin_p10"], 0), round(pm_pred["margin_p90"], 0)]
                total_ci = [round(pm_pred["total_p10"] * wmult, 0), round(pm_pred["total_p90"] * wmult, 0)]
                bands = {"home_1_12": round(pm_pred["p_home_1_12"], 3),
                         "home_13": round(pm_pred["p_home_13plus"], 3),
                         "away_1_12": round(pm_pred["p_away_1_12"], 3),
                         "away_13": round(pm_pred["p_away_13plus"], 3)}
            else:
                p_pois = p_blend = p_elo_cal
                margin, total, lam_h, lam_a = 0.0, 44.0, 4.0, 4.0
                margin_ci, total_ci, bands = None, None, None

            # provisional top tryscorers (analytic ATS)
            squad_h = signal_adjust.named_squad(entry, "home") if entry else None
            squad_a = signal_adjust.named_squad(entry, "away") if entry else None
            ph = props_player.match_player_lambdas(hist, rates, fx.home_id, lam_h, asof, squad_h, fx.away_id)
            pa = props_player.match_player_lambdas(hist, rates, fx.away_id, lam_a, asof, squad_a, fx.home_id)
            # top tryscorers from BOTH teams — kept balanced (top 5 per side, home
            # block then away block) so the underdog's scorers are always shown, not
            # buried under a global top-N that skews to the favourite.
            scorers = []
            for side, frame in (("home", ph), ("away", pa)):
                team_id = fx.home_id if side == "home" else fx.away_id
                top = frame.sort_values("p_ats", ascending=False).head(5)
                for t in top.itertuples(index=False):
                    p2 = 1 - np.exp(-t.lam) * (1 + t.lam)  # Poisson P(X>=2)
                    scorers.append({"player": player_names.get(t.player_id, t.player_id),
                                    "team": names[team_id], "side": side,
                                    "position": t.position,
                                    "exp_tries": round(float(t.lam), 2),
                                    "p_ats": round(float(t.p_ats), 3),
                                    "fair": round(1 / t.p_ats, 2) if t.p_ats > 0 else None,
                                    "p_2plus": round(float(p2), 3),
                                    "fair_2plus": round(1 / p2, 1) if p2 > 0.005 else None,
                                    "vs_opp": f"{int(t.h2h_tries)}t/{int(t.h2h_games)}g" if t.h2h_games else "—"})

            g = {
                "home": names[fx.home_id], "away": names[fx.away_id],
                "home_id": fx.home_id, "away_id": fx.away_id,
                "kickoff": pd.Timestamp(fx.date).strftime("%a %d %b, %H:%M"),
                "venue": fx.venue,
                "p": {"elo": round(p_elo_cal, 4), "poisson": round(p_pois, 4),
                      "blend": round(p_blend, 4), "market": None},
                "margin": round(margin, 1), "total": round(total, 1),
                "avail": avail_effect,
                "xstats": ({"home": round(mh, 3), "away": round(ma, 3)}
                           if xs_active and (abs(mh - 1) > 0.02 or abs(ma - 1) > 0.02) else None),
                "margin_ci": margin_ci, "total_ci": total_ci, "bands": bands,
                "tries": {"home": round(float(lam_h), 1), "away": round(float(lam_a), 1),
                          "total": round(float(lam_h + lam_a), 1)},
                "weather": weather, "weather_try_mult": round(wmult, 3),
                "scorers": scorers,  # top 5 each team, both sides always represented
                "team_lists_confirmed": bool(entry and entry.get("team_lists_confirmed")),
            }
            games.append(g)

        # merge the richer current-round outputs
        if actionable:
            _merge_current(games, market, sgm_cur)
        rounds.append({"round": grp["round"].iloc[0], "round_no": rno,
                       "actionable": actionable, "games": games})

    parlays = json.loads((OUT / "round_parlays.json").read_text()) if (OUT / "round_parlays.json").exists() else []
    # Form guide: league table from the scraped advanced stats (xAttack/xDefence/
    # edge leak per team). Built from whatever xStats data exists — empty if none.
    form_ratings = xs_ratings if xs_ratings is not None else xstats_defence.build_ratings()
    form = xstats_defence.latest_form_table(form_ratings, names)
    payload = {"generated": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
               "current_round": current_round,
               "current_round_label": f"Round {current_round}",
               "parlays": parlays,
               "form": form,
               "form_as_of": form[0]["as_of"] if form else None,
               "rounds": rounds}
    OUT.mkdir(exist_ok=True)
    (OUT / "season_predictions.json").write_text(json.dumps(payload, default=str))
    print(f"season predictions: {len(rounds)} rounds, "
          f"{sum(len(r['games']) for r in rounds)} games "
          f"(current = Round {current_round})")


def _merge_current(games, market, sgm) -> None:
    mk = {(r.home, r.away): r for r in market.itertuples(index=False)} if len(market) else {}
    sg = {}
    if len(sgm):
        for m, grp in sgm.groupby("match"):
            # a price LADDER (value -> longshot), de-duplicated, not just the tightest
            grp = grp.drop_duplicates("combo").sort_values("fair_price")
            sg[m] = grp.to_dict(orient="records")
    for g in games:
        m = mk.get((g["home"], g["away"]))
        if m is not None:
            g["p"]["market"] = float(m.market_p_home) if pd.notna(m.market_p_home) else None
            if getattr(m, "value_ev_pct", None) is not None and m.value_ev_pct > 0:
                g["value"] = {"side": m.value_side, "ev": float(m.value_ev_pct)}
        g["multis"] = sg.get(f"{g['home']} v {g['away']}", [])[:12]


if __name__ == "__main__":
    main()
