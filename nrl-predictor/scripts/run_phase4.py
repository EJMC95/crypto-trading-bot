"""Phase 4 end-to-end: player try rates -> ATS model -> validation gates ->
50k joint SGM simulation + candidate pricing for the upcoming round.

Gates (Build Spec §7, non-negotiable):
1. Walk-forward ATS backtest 2022-2025: Brier/log-loss must beat naive positional
   base rates (both recomputed per round, leak-free).
2. Reliability curve for ATS probabilities.
3. Joint-sim consistency: match win prob reconstructed from the player-level
   simulation must agree with the tier-2 model's own Monte Carlo within MC error.

Writes: outputs/phase4_report.md, outputs/round_props.csv, outputs/round_sgm.csv,
persisted sim arrays in data/processed/sgm/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval import backtest as bt
from src.features import player_rates
from src.ingest import teams
from src.models import props_player
from src.models.match_poisson import (PoissonParams, TryModel, long_format,
                                      team_scoring_table, walk_forward)
from src.sgm import price as sgm_price
from src.sgm import simulate as sgm_sim

OUT = ROOT / "outputs"
PROCESSED = ROOT / "data" / "processed"
POIS_PARAMS = PoissonParams(decay_xi=1.4)
EVAL_YEARS = range(2022, 2026)


def ats_backtest(matches, hist, wf):
    """Walk-forward ATS backtest over EVAL_YEARS. Squads are the actual 17 who
    played (Tuesday-list proxy; late changes make this mildly optimistic for both
    model AND baseline, so the comparison stays fair)."""
    lam_map = {}
    for r in wf.dropna(subset=["lam_tries_home"]).itertuples(index=False):
        lam_map[(r.match_id, r.home_id)] = r.lam_tries_home
        lam_map[(r.match_id, r.away_id)] = r.lam_tries_away

    frames = []
    ev_matches = matches[matches["year"].isin(EVAL_YEARS)]
    for (yr, rnd), grp in ev_matches.groupby(["year", "round"], sort=False):
        asof = grp["date"].min()
        rates = player_rates.rates_asof(hist, asof)
        rate_map = dict(zip(rates["player_id"], rates["rate"]))
        pri = player_rates.positional_priors(hist, asof)["rate"]
        base_ats = (hist[hist["date"] < asof].groupby("position")["tries_all"]
                    .apply(lambda s: (s > 0).mean()))
        mids = grp["match_id"].tolist()
        players = hist[hist["match_id"].isin(mids)].copy()
        players["rate"] = (players["player_id"].map(rate_map)
                           .fillna(players["position"].map(pri)))
        players["lam_team"] = [lam_map.get((m, t), np.nan) for m, t in
                               zip(players["match_id"], players["team_id"])]
        share = players.groupby(["match_id", "team_id"])["rate"].transform("sum")
        players["p_ats"] = 1 - np.exp(-players["rate"] / share * players["lam_team"])
        players["p_base"] = players["position"].map(base_ats)
        players["y"] = (players["tries_all"] > 0).astype(float)
        players["year"] = yr
        frames.append(players.dropna(subset=["p_ats", "p_base"]))
    return pd.concat(frames, ignore_index=True)


def candidate_combos(sims, fx, props_h, props_a, names, player_names):
    """Three story combos per match, built from the sim itself."""
    fav_home = float(np.mean(sims["margin"] > 0)) >= 0.5
    fav_id = fx.home_id if fav_home else fx.away_id
    fav_win = "home_win" if fav_home else "away_win"
    fav_props = (props_h if fav_home else props_a).sort_values("p_ats", ascending=False)
    dog_props = (props_a if fav_home else props_h).sort_values("p_ats", ascending=False)
    backs = fav_props[fav_props["position"].isin(["W", "FB", "C"])]
    top_back = backs.iloc[0] if len(backs) else fav_props.iloc[0]
    dog_backs = dog_props[dog_props["position"].isin(["W", "FB", "C"])]
    dog_back = dog_backs.iloc[0] if len(dog_backs) else (dog_props.iloc[0] if len(dog_props) else None)
    med_margin = abs(float(np.median(sims["margin"])))
    med_total = float(np.median(sims["total"]))
    med_tries = float(np.median(sims["home_tries"] + sims["away_tries"]))
    line = -(np.floor(med_margin) + 0.5)
    over = np.floor(med_total - 4) + 0.5
    tries_over = np.floor(med_tries) - 0.5
    tid = int(top_back.player_id)
    big_over = np.floor(med_total + 4) + 0.5      # a longer total line
    big_tries = np.floor(med_tries) + 1.5
    combos = [
        # value tier (~$3-6)
        [fav_win, f"ats {tid}", f"total over {over}"],
        [f"line {fav_id} {line}", f"ats {tid}"],
        [fav_win, f"ats {tid}", f"tries_total over {tries_over}"],
        # big tier (~$6-15)
        [f"margin_band {fav_id} 13 60", f"ats {tid}"],
        [fav_win, f"tries2+ {tid}"],
        [fav_win, f"ats {tid}", f"total over {big_over}"],
    ]
    if len(backs) >= 2:
        b0, b1 = int(backs.iloc[0].player_id), int(backs.iloc[1].player_id)
        combos += [
            [fav_win, f"ats {b0}", f"ats {b1}"],
            # 4-leg big day out
            [fav_win, f"ats {b0}", f"ats {b1}", f"total over {over}"],
            # longshot tier (~$15-60): 5-leg, big margin + two scorers + over
            [f"margin_band {fav_id} 13 60", f"ats {b0}", f"ats {b1}", f"total over {over}"],
            [fav_win, f"tries2+ {b0}", f"ats {b1}", f"total over {big_over}"],
        ]
        if len(backs) >= 3:
            b2 = int(backs.iloc[2].player_id)
            # 6-leg "sweep": win × three scorers × over × plenty of tries
            combos.append([fav_win, f"ats {b0}", f"ats {b1}", f"ats {b2}",
                           f"total over {over}", f"tries_total over {big_tries}"])
    # both-teams builders: pair the favourite's top back with the underdog's — a
    # tryscorer from each side. Longer odds (an underdog back scoring is a real
    # uplift) and gives the multis a scorer from BOTH teams, not just the fav.
    if dog_back is not None:
        d0 = int(dog_back.player_id)
        combos += [
            [f"ats {tid}", f"ats {d0}"],                                  # a scorer each way
            [fav_win, f"ats {tid}", f"ats {d0}", f"total over {over}"],   # win + both scorers + over
        ]
    rows = []
    for legs in combos:
        res = sgm_price.price_combo(sims, legs)
        pretty = []
        for leg in legs:
            parts = leg.split()
            if parts[0] == "ats":
                pretty.append(f"ATS {player_names.get(int(parts[1]), parts[1])}")
            elif parts[0] == "tries2+":
                pretty.append(f"{player_names.get(int(parts[1]), parts[1])} 2+ tries")
            elif parts[0] == "tries_total":
                pretty.append(f"match tries {parts[1]} {parts[2]}")
            elif parts[0] == "team_tries":
                pretty.append(f"{names[parts[1].upper()]} tries {parts[2]} {parts[3]}")
            elif parts[0] == "margin_band":
                lo = int(float(parts[2]))
                pretty.append(f"{names[parts[1].upper()]} by "
                              + (f"{lo}+" if float(parts[3]) >= 60 else f"{lo}-{int(float(parts[3]))}"))
            elif parts[0] == "line":
                pretty.append(f"{names[parts[1].upper()]} {float(parts[2]):+g}")
            elif parts[0] in ("home_win", "away_win"):
                pretty.append(f"{names[fx.home_id if parts[0]=='home_win' else fx.away_id]} win")
            else:
                pretty.append(leg)
        fp = res["fair_price"]
        tier = "value" if fp < 6 else ("big" if fp < 15 else "longshot")
        rows.append({"match": f"{names[fx.home_id]} v {names[fx.away_id]}",
                     "combo": " × ".join(pretty), "n_legs": len(legs),
                     "tier": tier, **res})
    return rows


def main() -> None:
    OUT.mkdir(exist_ok=True)
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    pm = pd.read_parquet(PROCESSED / "player_matches.parquet")
    pm = pm[pm["match_id"].isin(matches["match_id"].dropna())]
    pdata = pd.read_csv(ROOT / "data" / "raw" / "uselessnrlstats" / "player_data.csv",
                        low_memory=False)
    player_names = dict(pdata[["player_id", "full_name"]].values)
    names = teams.id_to_name()
    hist = player_rates.player_history(matches, pm, teams)
    scoring = team_scoring_table(pm, teams)
    long_rows = long_format(matches, scoring)

    print("== tier-2 walk-forward with lambdas (2022+) ==")
    wf = walk_forward(matches, long_rows, POIS_PARAMS, start_year=min(EVAL_YEARS))

    print("== gate 1: ATS backtest 2022-2025 ==")
    back = ats_backtest(matches, hist, wf)
    y = back["y"].to_numpy()
    res = {}
    for label, col in (("model", "p_ats"), ("positional_base", "p_base")):
        p = back[col].to_numpy()
        res[label] = (bt.brier(p, y), bt.log_loss(p, y))
        print(f"  {label}: Brier {res[label][0]:.4f} | log loss {res[label][1]:.4f}")
    gate1 = res["model"][0] < res["positional_base"][0] and res["model"][1] < res["positional_base"][1]
    print(f"  GATE {'PASSED' if gate1 else 'FAILED'} on {len(back)} player-games")
    per_season = back.groupby("year").apply(
        lambda g: pd.Series({
            "n": len(g),
            "brier_model": bt.brier(g["p_ats"].to_numpy(), g["y"].to_numpy()),
            "brier_base": bt.brier(g["p_base"].to_numpy(), g["y"].to_numpy())}),
        include_groups=False).round(4)
    rel = bt.reliability_table(back["p_ats"].to_numpy(), y)

    print("== live: fit current model, simulate upcoming round ==")
    asof = matches["date"].max() + pd.Timedelta(days=1)
    model = TryModel(POIS_PARAMS).fit(long_rows, asof)
    rates = player_rates.rates_asof(hist, asof)
    fixtures = pd.read_parquet(PROCESSED / "fixtures_next.parquet")
    season = int(fixtures["date"].dt.year.iloc[0])
    round_no = int(fixtures["round_no"].iloc[0])

    # On-the-day signals (if scanned): confirmed team lists replace the squad the
    # sim assumes; a wet forecast scales each team's expected tries. Absent -> the
    # last-game proxy and no weather effect, exactly as before.
    from src.features import signal_adjust
    sig_by_pair = signal_adjust.signals_by_pair(signal_adjust.load_signals())

    consistency, props_rows, sgm_rows, tries_rows, parlay_anchors = [], [], [], [], []
    for fx in fixtures.itertuples(index=False):
        entry = sig_by_pair.get((fx.home_id, fx.away_id))
        wmult, _ = signal_adjust.weather_multiplier(entry or {})
        lam_h = model.try_rate(fx.home_id, fx.away_id, True) * wmult
        lam_a = model.try_rate(fx.away_id, fx.home_id, False) * wmult
        squad_h = signal_adjust.named_squad(entry, "home") if entry else None
        squad_a = signal_adjust.named_squad(entry, "away") if entry else None
        ph = props_player.match_player_lambdas(hist, rates, fx.home_id, lam_h, asof, squad_h, fx.away_id)
        pa = props_player.match_player_lambdas(hist, rates, fx.away_id, lam_a, asof, squad_a, fx.home_id)
        sims = sgm_sim.simulate_match(model, ph, pa, fx.home_id, fx.away_id)
        sgm_sim.save(sims, season, round_no)

        p_sim = float(np.mean(sims["margin"] > 0) + 0.5 * np.mean(sims["margin"] == 0))
        # consistency reference uses the SAME (xStats-corrected) try rates the player
        # sim was built from, so the gate still verifies the thinning/score assembly
        # — not merely that xStats moved tries (which is by design). The DISPLAYED
        # match winner remains the champion blend; xStats only sharpens tries/props.
        p_model = model.p_home_from_lambdas(lam_h, lam_a)
        consistency.append({"match": f"{names[fx.home_id]} v {names[fx.away_id]}",
                            "p_home_sim": round(p_sim, 4), "p_home_tier2": round(p_model, 4),
                            "diff": round(p_sim - p_model, 4)})

        for side, frame in (("home", ph), ("away", pa)):
            top = frame.sort_values("p_ats", ascending=False).head(3)
            for t in top.itertuples(index=False):
                p2 = 1 - np.exp(-t.lam) * (1 + t.lam)  # Poisson P(X>=2)
                opp = names[fx.away_id if side == "home" else fx.home_id]
                props_rows.append({
                    "match": f"{names[fx.home_id]} v {names[fx.away_id]}",
                    "team": names[fx.home_id if side == "home" else fx.away_id],
                    "player": player_names.get(t.player_id, t.player_id),
                    "position": t.position,
                    "exp_tries": round(float(t.lam), 2),
                    "p_ats": round(t.p_ats, 3),
                    "fair_price": round(1 / t.p_ats, 2),
                    "p_2plus": round(float(p2), 3),
                    "fair_2plus": round(1 / p2, 1) if p2 > 0.005 else None,
                    "vs_opp": f"{int(t.h2h_tries)}t/{int(t.h2h_games)}g" if t.h2h_games else "—"})
        sgm_rows += candidate_combos(sims, fx, ph, pa, names, player_names)
        # anchor legs for the cross-game parlay of the round
        fav_home = p_sim >= 0.5
        fav_id = fx.home_id if fav_home else fx.away_id
        fav_props = (ph if fav_home else pa).sort_values("p_ats", ascending=False)
        top_sc = fav_props.iloc[0] if len(fav_props) else None
        parlay_anchors.append({
            "match": f"{names[fx.home_id]} v {names[fx.away_id]}",
            "fav": names[fav_id], "p_win": max(p_sim, 1 - p_sim),
            "scorer": player_names.get(int(top_sc.player_id), "") if top_sc is not None else "",
            "p_scorer": float(top_sc.p_ats) if top_sc is not None else None})
        tt = sims["home_tries"] + sims["away_tries"]
        tries_rows.append({
            "match": f"{names[fx.home_id]} v {names[fx.away_id]}",
            "exp_tries_home": round(float(sims["home_tries"].mean()), 2),
            "exp_tries_away": round(float(sims["away_tries"].mean()), 2),
            "exp_tries_total": round(float(tt.mean()), 2),
            "median_tries_total": float(np.median(tt)),
            "p_over_line": round(float((tt > np.floor(np.median(tt)) - 0.5).mean()), 3),
            "tries_line": float(np.floor(np.median(tt)) - 0.5)})

    cons = pd.DataFrame(consistency)
    max_diff = cons["diff"].abs().max()
    mc_3sigma = 3 * np.sqrt(0.25 / sgm_sim.N_SIMS) + 3 * np.sqrt(0.25 / 20000)
    gate3 = max_diff <= mc_3sigma
    print(f"== gate 3: sim consistency max |diff| {max_diff:.4f} "
          f"(3sigma MC ≈ {mc_3sigma:.4f}) -> {'PASSED' if gate3 else 'FAILED'}")

    props = pd.DataFrame(props_rows)
    sgm = pd.DataFrame(sgm_rows).sort_values("correlation_lift", ascending=False)
    props.to_csv(OUT / "round_props.csv", index=False)
    sgm.to_csv(OUT / "round_sgm.csv", index=False)
    pd.DataFrame(tries_rows).to_csv(OUT / "round_tries.csv", index=False)

    # Cross-game "parlay of the round" — legs from different matches are independent,
    # so the accumulator price is the product (no correlation edge, but a big-payout
    # ticket). Two builds: safest game winners, and a win×tryscorer value builder.
    import json as _json
    pa_sorted = sorted(parlay_anchors, key=lambda a: -a["p_win"])
    parlays = []
    if len(pa_sorted) >= 4:
        legs = pa_sorted[:4]
        p = float(np.prod([l["p_win"] for l in legs]))
        parlays.append({"name": "4-leg winners parlay", "p_joint": round(p, 4),
                        "fair_price": round(1 / p, 2),
                        "legs": [f"{l['fav']} to win" for l in legs]})
    builder = [a for a in pa_sorted if a["p_scorer"]][:3]
    if len(builder) >= 3:
        p = float(np.prod([l["p_win"] * l["p_scorer"] for l in builder]))
        parlays.append({"name": "3-game win + tryscorer builder", "p_joint": round(p, 4),
                        "fair_price": round(1 / p, 2),
                        "legs": [f"{l['fav']} win & {l['scorer']} try" for l in builder]})
    (OUT / "round_parlays.json").write_text(_json.dumps(parlays, indent=1))

    # Signal overlay (flags + info-confidence + weather-adjusted totals) for display.
    if (OUT / "round_predictions.csv").exists():
        base = pd.read_csv(OUT / "round_predictions.csv")
        name_to_id = {v: k for k, v in names.items()}
        base["home_id"] = base["home"].map(name_to_id)
        base["away_id"] = base["away"].map(name_to_id)
        signal_adjust.build_signal_overlay(base, {}, hist, asof)
        n_conf = sum(1 for g in sig_by_pair.values() if g.get("team_lists_confirmed"))
        print(f"signal overlay: {n_conf}/{len(sig_by_pair)} team lists confirmed")

    quotes = sgm_price.evaluate_quotes({}, round_no)  # populated via manual CSV later

    lines = [
        "# Phase 4 report — player props + SGM simulator",
        "",
        f"_Generated {pd.Timestamp.now():%Y-%m-%d}. ATS model: hierarchical "
        "Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try "
        "expectation via Poisson thinning. Squads in backtest = the 17 who played "
        "(Tuesday-list proxy — applies equally to model and baseline)._",
        "",
        "## Gate 1 — walk-forward ATS backtest 2022–2025 (Brier / log loss)",
        "",
        "| model | Brier | log loss |",
        "|---|---|---|",
        f"| positional base rates | {res['positional_base'][0]:.4f} | {res['positional_base'][1]:.4f} |",
        f"| **ATS model** | **{res['model'][0]:.4f}** | **{res['model'][1]:.4f}** |",
        "",
        f"**GATE {'PASSED' if gate1 else 'FAILED'}** on {len(back):,} player-games.",
        "",
        "### Per-season", "",
        per_season.to_markdown(),
        "",
        "### Reliability (ATS probabilities)", "",
        rel.round(3).to_markdown(index=False),
        "",
        "## Gate 3 — joint-sim consistency (player-level sim vs tier-2 MC)", "",
        cons.to_markdown(index=False),
        "",
        f"Max |diff| = {max_diff:.4f} vs 3σ MC bound {mc_3sigma:.4f} → "
        f"**{'PASSED' if gate3 else 'FAILED'}**.",
        "",
        f"## Round {round_no} — top ATS props (model fair prices)", "",
        props.to_markdown(index=False),
        "",
        f"## Round {round_no} — SGM candidates (fair vs independence pricing)", "",
        sgm[["match", "combo", "p_joint", "fair_price", "p_independent",
             "correlation_lift"]].to_markdown(index=False),
        "",
        "_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 "
        "means the legs help each other — a bookmaker pricing them independently "
        "(then stacking 20–40% margin) undervalues the combo. No quoted SGM prices "
        "yet: paste bookie quotes into data/manual_odds/round{:02d}.csv and re-run "
        "to get EV columns._".format(round_no),
        "",
        "_Paper only. Fair prices are model outputs with uncertainty, not betting "
        "advice._",
    ]
    if len(quotes):
        lines += ["", "## Quoted SGMs evaluated", "", quotes.to_markdown(index=False)]
    (OUT / "phase4_report.md").write_text("\n".join(lines))
    print(f"report -> {OUT / 'phase4_report.md'}")


if __name__ == "__main__":
    main()
