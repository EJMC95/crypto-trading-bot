"""xStats opponent-defence correction for the try model (SGM sharpening).

The tier-2 Poisson model gives each side an expected try count λ_team from tries
scored/conceded. Tries are a *noisy, low-count* outcome; the underlying process
stats (line breaks, tackle breaks, line-break assists conceded — and missed
tackles made) are a higher-signal, faster-responding read of how leaky a defence
actually is. This module turns those process stats into a leak-free rolling
"defensive leakiness" rating per team and exposes a multiplicative correction to
the opponent's attacking λ.

Discipline: the correction is an *offset* on the existing λ (Poisson regression
with log λ_base as a fixed offset), so xStats can only add signal that is
orthogonal to what the try model already knows. It ships to production only if it
improves the walk-forward ATS (tryscorer) Brier — see scripts/spike_xtries_ats.py.

Design notes
------------
- xTries-conceded: fit `tries ~ attacking process stats` (line breaks, tackle
  breaks, line-break assists, offloads, run metres, post-contact metres) on early
  seasons; the opponent's attacking stats in a match give the tries a team
  "deserved" to concede. A team's rolling mean of xTries-conceded (shifted, so it
  never sees the current game) is its `xdef` rating.
- Standardised vs the league, `xdef` becomes `zdef`; a leaky defence (high zdef)
  lifts the opponent's λ, a staunch one (low zdef) trims it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[2]
TEAM_STATS = ROOT / "data" / "processed" / "team_stats.parquet"

# attacking process inputs -> tries "deserved" (the defence conceded these)
ATTACK_STATS = ["lineBreaks", "lineBreakAssists", "tackleBreaks", "offloads",
                "allRunMetres", "postContactMetres"]
XTRIES_FIT_MAX_SEASON = 2023   # learn the stats->tries map on early seasons only
ROLL_MIN_GAMES = 4            # a defence needs a few games before its rating counts
LEAK_FREE_HALFLIFE = 8        # recent form weighted, but slow enough to be stable


def _team_long(ts: pd.DataFrame) -> pd.DataFrame:
    """One row per team-match: the team's own attacking stats + tries it scored,
    and (via the opponent columns) the tries/stats it conceded."""
    frames = []
    for side, opp in (("home", "away"), ("away", "home")):
        d = pd.DataFrame({
            "season": ts["season"], "round": ts["round"], "date": ts["date"],
            "team_id": ts[f"{side}_id"], "opp_id": ts[f"{opp}_id"],
            "tries_for": ts[f"{side}_tries"], "tries_against": ts[f"{opp}_tries"],
        })
        for f in ATTACK_STATS:                 # team's OWN attacking process
            d[f] = ts[f"{side}_{f}"]
        for f in ATTACK_STATS:                 # what the OPPONENT generated (conceded)
            d[f"opp_{f}"] = ts[f"{opp}_{f}"]
        frames.append(d)
    return (pd.concat(frames, ignore_index=True)
            .dropna(subset=["tries_for", "tries_against"])
            .sort_values("date").reset_index(drop=True))


def build_ratings(ts: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return per team-match rolling attack/defence xStats ratings (leak-free).

    Columns: season, round, team_id, opp_id, xatt, xdef (both shifted rolling
    means, NaN until ROLL_MIN_GAMES of history exist for the team).
    """
    if ts is None:
        if not TEAM_STATS.exists():
            # no scraped xStats available -> caller degrades to the plain try model
            return pd.DataFrame(columns=["season", "round", "date", "team_id",
                                         "opp_id", "xatt", "xdef", "xedge"])
        ts = pd.read_parquet(TEAM_STATS)
    ts = ts.dropna(subset=["home_id", "away_id", "home_tries", "away_tries"]).copy()
    tl = _team_long(ts)

    # stats -> tries map, fit on early seasons only (attacking process => tries)
    fit = tl[tl["season"] <= XTRIES_FIT_MAX_SEASON]
    reg = Ridge(alpha=50.0).fit(fit[ATTACK_STATS], fit["tries_for"])
    # xTries a team deserved to SCORE (own attack) and to CONCEDE (opp attack)
    tl["xtries_for"] = reg.predict(tl[ATTACK_STATS]).clip(min=0)
    opp_cols = [f"opp_{f}" for f in ATTACK_STATS]
    tl["xtries_against"] = reg.predict(tl[opp_cols].rename(
        columns={f"opp_{f}": f for f in ATTACK_STATS})).clip(min=0)

    # edge leakiness: line breaks + tackle breaks CONCEDED are edge-heavy events
    # (most happen out wide), so this is a proxy for how leaky a team's edge is.
    tl["edge_conceded"] = tl["opp_lineBreaks"] + tl["opp_tackleBreaks"]

    # leak-free rolling ratings: shift() so the current game is never in the mean
    def _roll(s):
        return s.shift().ewm(halflife=LEAK_FREE_HALFLIFE, min_periods=ROLL_MIN_GAMES).mean()
    tl["xatt"] = tl.groupby("team_id")["xtries_for"].transform(_roll)
    tl["xdef"] = tl.groupby("team_id")["xtries_against"].transform(_roll)
    tl["xedge"] = tl.groupby("team_id")["edge_conceded"].transform(_roll)
    return tl[["season", "round", "date", "team_id", "opp_id", "xatt", "xdef", "xedge"]]


# edge tryscorers gain share against a leaky edge; middle forwards give it up.
EDGE_POS = {"W", "C", "FB"}      # outside backs — the beneficiaries of edge leaks
MID_POS = {"FR", "L", "HK"}      # middle forwards — tries flow away from them
EDGE_CAP = 0.35                  # max |log-shift| to any player's share


def edge_indicator(position: str) -> float:
    if position in EDGE_POS:
        return 1.0
    if position in MID_POS:
        return -1.0
    return 0.0                    # halves / 2nd row / bench: neutral


def _standardise(ratings: pd.DataFrame) -> dict:
    """League mean/sd for xdef, xatt and xedge, so a rating becomes a z-score."""
    return {
        "def_mu": float(ratings["xdef"].mean()), "def_sd": float(ratings["xdef"].std() + 1e-9),
        "att_mu": float(ratings["xatt"].mean()), "att_sd": float(ratings["xatt"].std() + 1e-9),
        "edge_mu": float(ratings["xedge"].mean()), "edge_sd": float(ratings["xedge"].std() + 1e-9),
    }


def edge_redistribute(shares: np.ndarray, positions, zedge_opp: float,
                      gamma: float, cap: float = EDGE_CAP) -> np.ndarray:
    """Shift try-share toward edge attackers (and away from middle forwards) when
    the opponent's edge is leaky (zedge_opp high). Renormalised to sum to 1 so the
    TEAM total lambda is unchanged — only WHO scores moves. gamma=0 or a flat edge
    is a no-op. Preserves SGM sim consistency and the match winner by construction.
    """
    if not np.isfinite(zedge_opp) or gamma == 0.0:
        return shares
    e = np.array([edge_indicator(p) for p in positions], dtype=float)
    logshift = np.clip(gamma * zedge_opp * e, -cap, cap)
    w = shares * np.exp(logshift)
    tot = w.sum()
    return w / tot if tot > 0 else shares


def fit_offset_correction(ratings: pd.DataFrame, lam_base: pd.Series,
                          tries_actual: pd.Series, fit_mask: np.ndarray,
                          zdef_opp: pd.Series, zatt_team: pd.Series) -> dict:
    """Poisson-style offset fit: log E[tries] = log(lam_base) + b_def*zdef_opp
    + b_att*zatt_team. Returned as {beta_def, beta_att, ...norm...}. A tiny ridge
    (via least squares on the log-residual, tries+0.5 smoothed) keeps it stable on
    the ~600 fit games; gating decides whether it actually helps."""
    lam = np.clip(lam_base.to_numpy(float), 1e-3, None)
    y = np.log((tries_actual.to_numpy(float) + 0.5) / lam)   # log-residual vs base
    X = np.column_stack([zdef_opp.to_numpy(float), zatt_team.to_numpy(float),
                         np.ones(len(y))])
    m = fit_mask & np.isfinite(y) & np.isfinite(X).all(axis=1)
    # ridge least squares (alpha keeps betas modest; intercept absorbs bias)
    a = 5.0
    XtX = X[m].T @ X[m] + a * np.eye(3)
    XtX[2, 2] -= a  # don't penalise the intercept
    beta = np.linalg.solve(XtX, X[m].T @ y[m])
    return {"beta_def": float(beta[0]), "beta_att": float(beta[1]),
            "intercept": float(beta[2])}


def lam_multiplier(coef: dict, zdef_opp: float, zatt_team: float,
                   cap: float = 0.30) -> float:
    """Multiplicative correction to a team's attacking λ. Capped at ±cap in log
    space (~±35%) so a single extreme rating can't blow up a price."""
    if not np.isfinite(zdef_opp):
        zdef_opp = 0.0
    if not np.isfinite(zatt_team):
        zatt_team = 0.0
    z = coef["beta_def"] * zdef_opp + coef["beta_att"] * zatt_team
    z = float(np.clip(z, -cap, cap))
    return float(np.exp(z))


def fit_and_gate(matches: pd.DataFrame, hist: pd.DataFrame, lam_map: dict,
                 ratings: pd.DataFrame, norm: dict, eval_years=range(2022, 2026),
                 fit_max_season: int = 2023) -> dict:
    """Assemble the walk-forward ATS table, fit the offset correction on early
    seasons, and grade it on the 2024+ holdout. Returns a dict with the fitted
    coef, the league norm, and whether it BEAT the base tryscorer model — the
    caller ships the correction only if `passed`.

    Kept here (not in a script) so production (run_phase4) and the spike share one
    implementation and can never drift apart.
    """
    from ..eval import backtest as bt
    from . import player_rates

    if ratings.empty or ratings["xdef"].dropna().empty:
        return {"coef": {"beta_def": 0.0, "beta_att": 0.0, "intercept": 0.0},
                "norm": norm, "passed": False, "brier_base": None, "brier_x": None,
                "logloss_base": None, "logloss_x": None, "n_holdout": 0}

    rat = {(int(r.season), int(r.round), r.team_id): (r.xatt, r.xdef)
           for r in ratings.itertuples(index=False)}

    def _z(team_id, season, rnd):
        v = rat.get((int(season), int(rnd), team_id))
        if v is None or not np.isfinite(v[0]):
            return np.nan, np.nan
        return ((v[0] - norm["att_mu"]) / norm["att_sd"],
                (v[1] - norm["def_mu"]) / norm["def_sd"])

    ev = matches[matches["year"].isin(eval_years)].copy()
    ev["round_no"] = pd.to_numeric(
        ev["round"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    rows = []
    for (yr, rnd), grp in ev.dropna(subset=["round_no"]).groupby(["year", "round_no"], sort=False):
        rnd = int(rnd)
        asof = grp["date"].min()
        rates = player_rates.rates_asof(hist, asof)
        rate_map = dict(zip(rates["player_id"], rates["rate"]))
        pri = player_rates.positional_priors(hist, asof)["rate"]
        mids = grp["match_id"].tolist()
        players = hist[hist["match_id"].isin(mids)].copy()
        players["rate"] = (players["player_id"].map(rate_map)
                           .fillna(players["position"].map(pri)))
        players["lam_base"] = [lam_map.get((m, t), np.nan) for m, t in
                               zip(players["match_id"], players["team_id"])]
        opp = {}
        for r in grp.itertuples(index=False):
            opp[r.home_id], opp[r.away_id] = r.away_id, r.home_id
        players["opp_id"] = players["team_id"].map(opp)
        players["zatt_team"] = [_z(t, yr, rnd)[0] for t in players["team_id"]]
        players["zdef_opp"] = [_z(o, yr, rnd)[1] for o in players["opp_id"]]
        players["y"] = (players["tries_all"] > 0).astype(float)
        players["year"] = yr
        rows.append(players.dropna(subset=["lam_base", "rate"]))
    tab = pd.concat(rows, ignore_index=True)

    tm = (tab.groupby(["match_id", "team_id"])
          .agg(lam_base=("lam_base", "first"), tries=("tries_all", "sum"),
               zatt_team=("zatt_team", "first"), zdef_opp=("zdef_opp", "first"),
               year=("year", "first")).reset_index()
          .dropna(subset=["zatt_team", "zdef_opp"]))
    fit_mask = (tm["year"] <= fit_max_season).to_numpy()
    coef = fit_offset_correction(ratings, tm["lam_base"], tm["tries"], fit_mask,
                                 tm["zdef_opp"], tm["zatt_team"])

    tab["mult"] = [lam_multiplier(coef, zd, za)
                   for zd, za in zip(tab["zdef_opp"], tab["zatt_team"])]
    share = tab.groupby(["match_id", "team_id"])["rate"].transform("sum")
    tab["p_base"] = 1 - np.exp(-tab["rate"] / share * tab["lam_base"])
    tab["p_x"] = 1 - np.exp(-tab["rate"] / share * tab["lam_base"] * tab["mult"])
    ho = tab[tab["year"] >= 2024].dropna(subset=["p_base", "p_x", "zdef_opp"])
    y = ho["y"].to_numpy()
    b_base, b_x = bt.brier(ho["p_base"].to_numpy(), y), bt.brier(ho["p_x"].to_numpy(), y)
    ll_base = bt.log_loss(ho["p_base"].to_numpy(), y)
    ll_x = bt.log_loss(ho["p_x"].to_numpy(), y)
    passed = (b_x < b_base - 0.0001) and (ll_x <= ll_base + 1e-4)
    return {"coef": coef, "norm": norm, "passed": bool(passed),
            "brier_base": round(b_base, 4), "brier_x": round(b_x, 4),
            "logloss_base": round(ll_base, 4), "logloss_x": round(ll_x, 4),
            "n_holdout": int(len(ho))}


def fit_and_gate_edge(matches: pd.DataFrame, hist: pd.DataFrame, lam_map: dict,
                      ratings: pd.DataFrame, norm: dict, eval_years=range(2022, 2026),
                      fit_max_season: int = 2023) -> dict:
    """Fit the edge share-redistribution strength `gamma` and gate it on the
    EDGE-attacker (W/C/FB) tryscorer Brier over the 2024-25 holdout. Ships only if
    it sharpens edge-attacker prices without hurting the rest of the field.

    gamma is fit by a coarse Poisson-likelihood grid on player try counts (the
    renormalisation is ~1 for the small shifts involved, so the fit ignores it; the
    holdout eval applies the exact renormalised redistribution)."""
    from ..eval import backtest as bt
    from . import player_rates

    if ratings.empty or ratings["xedge"].dropna().empty:
        return {"gamma": 0.0, "passed": False, "brier_edge_base": None,
                "brier_edge_x": None, "n_edge_holdout": 0}

    zedge = {(int(r.season), int(r.round), r.team_id):
             (r.xedge - norm["edge_mu"]) / norm["edge_sd"] for r in ratings.itertuples(index=False)}

    ev = matches[matches["year"].isin(eval_years)].copy()
    ev["round_no"] = pd.to_numeric(ev["round"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    rows = []
    for (yr, rnd), grp in ev.dropna(subset=["round_no"]).groupby(["year", "round_no"], sort=False):
        rnd = int(rnd)
        asof = grp["date"].min()
        rates = player_rates.rates_asof(hist, asof)
        rate_map = dict(zip(rates["player_id"], rates["rate"]))
        pri = player_rates.positional_priors(hist, asof)["rate"]
        players = hist[hist["match_id"].isin(grp["match_id"].tolist())].copy()
        players["rate"] = players["player_id"].map(rate_map).fillna(players["position"].map(pri))
        players["lam_team"] = [lam_map.get((m, t), np.nan) for m, t in
                               zip(players["match_id"], players["team_id"])]
        opp = {}
        for r in grp.itertuples(index=False):
            opp[r.home_id], opp[r.away_id] = r.away_id, r.home_id
        players["opp_id"] = players["team_id"].map(opp)
        players["zedge_opp"] = [zedge.get((yr, rnd, o), np.nan) for o in players["opp_id"]]
        players["y"] = (players["tries_all"] > 0).astype(float)
        players["year"] = yr
        rows.append(players.dropna(subset=["lam_team", "rate", "zedge_opp"]))
    tab = pd.concat(rows, ignore_index=True)
    share = tab.groupby(["match_id", "team_id"])["rate"].transform("sum")
    tab["share"] = tab["rate"] / share
    tab["lam_base"] = tab["share"] * tab["lam_team"]
    tab["e"] = [edge_indicator(p) for p in tab["position"]]
    tab["x"] = tab["zedge_opp"] * tab["e"]

    # fit gamma by Poisson-likelihood grid on the training seasons
    tr = tab[tab["year"] <= fit_max_season]
    lam0, xt, yt = tr["lam_base"].to_numpy(), tr["x"].to_numpy(), tr["tries_all"].to_numpy(float)
    best_g, best_ll = 0.0, -np.inf
    for g in np.linspace(-0.6, 0.6, 25):
        lam = np.clip(lam0 * np.exp(g * xt), 1e-6, None)
        ll = float(np.sum(yt * np.log(lam) - lam))
        if ll > best_ll:
            best_ll, best_g = ll, float(g)

    # holdout eval with the EXACT renormalised redistribution, per match-team
    ho = tab[tab["year"] >= 2024].copy()
    ho["p_base"] = 1 - np.exp(-ho["lam_base"])
    padj = np.zeros(len(ho))
    ho = ho.reset_index(drop=True)
    for _, idx in ho.groupby(["match_id", "team_id"]).groups.items():
        idx = list(idx)
        sh = ho.loc[idx, "share"].to_numpy()
        pos = ho.loc[idx, "position"].tolist()
        ze = ho.loc[idx[0], "zedge_opp"]
        lt = ho.loc[idx[0], "lam_team"]
        sh_adj = edge_redistribute(sh, pos, ze, best_g)
        padj[idx] = 1 - np.exp(-sh_adj * lt)
    ho["p_x"] = padj

    edge = ho[ho["e"] > 0]
    ye = edge["y"].to_numpy()
    b_base = bt.brier(edge["p_base"].to_numpy(), ye)
    b_x = bt.brier(edge["p_x"].to_numpy(), ye)
    # guard: must not hurt the whole field either
    yall = ho["y"].to_numpy()
    all_ok = bt.brier(ho["p_x"].to_numpy(), yall) <= bt.brier(ho["p_base"].to_numpy(), yall) + 1e-4
    passed = (b_x < b_base - 0.0001) and all_ok
    return {"gamma": round(best_g, 3), "passed": bool(passed),
            "brier_edge_base": round(b_base, 4), "brier_edge_x": round(b_x, 4),
            "n_edge_holdout": int(len(edge))}


def matchup_multipliers(ratings: pd.DataFrame, norm: dict, coef: dict,
                        home_id: str, away_id: str, cap: float = 0.30) -> tuple[float, float]:
    """Live λ-multipliers (home, away) for one fixture from the latest ratings.

    Home attack is lifted/trimmed by the AWAY defence's leakiness (and its own
    attacking form); symmetrically for away. Returns (1.0, 1.0) when either side
    lacks a rating (early season / newly-scraped), so the correction degrades
    gracefully to the plain try model.
    """
    h, a = ratings_asof(ratings, home_id), ratings_asof(ratings, away_id)
    if h is None or a is None:
        return 1.0, 1.0
    zatt_h = (h["xatt"] - norm["att_mu"]) / norm["att_sd"]
    zdef_a = (a["xdef"] - norm["def_mu"]) / norm["def_sd"]
    zatt_a = (a["xatt"] - norm["att_mu"]) / norm["att_sd"]
    zdef_h = (h["xdef"] - norm["def_mu"]) / norm["def_sd"]
    return (lam_multiplier(coef, zdef_a, zatt_h, cap),
            lam_multiplier(coef, zdef_h, zatt_a, cap))


def ratings_asof(ratings: pd.DataFrame, team_id: str) -> dict | None:
    """Most recent (xatt, xdef, xedge) for a team — live/current-round pricing."""
    r = ratings[ratings["team_id"] == team_id].dropna(subset=["xdef"])
    if r.empty:
        return None
    last = r.iloc[-1]
    return {"xatt": float(last["xatt"]), "xdef": float(last["xdef"]),
            "xedge": float(last["xedge"]) if pd.notna(last.get("xedge")) else None}


def latest_form_table(ratings: pd.DataFrame, names: dict | None = None) -> list[dict]:
    """League form guide from the newest rating per team: expected tries scored
    (xatt) and conceded (xdef) per game, edge leakiness (xedge), net xDiff, and a
    last-5-game trend on xDiff. Ranked best net first. Powered entirely by the
    scraped advanced stats — surfaces WHY the try model rates each side."""
    if ratings.empty:
        return []
    r = ratings.dropna(subset=["xatt", "xdef"]).copy()
    rows = []
    for tid, g in r.groupby("team_id"):
        g = g.sort_values("date")
        last = g.iloc[-1]
        xdiff_series = (g["xatt"] - g["xdef"]).dropna()
        recent = xdiff_series.tail(5)
        prev = xdiff_series.tail(10).head(5)
        trend = (float(recent.mean()) - float(prev.mean())) if len(prev) else 0.0
        rows.append({
            "team_id": tid,
            "team": (names or {}).get(tid, tid),
            "xatt": round(float(last["xatt"]), 2),
            "xdef": round(float(last["xdef"]), 2),
            "xedge": round(float(last["xedge"]), 1) if pd.notna(last.get("xedge")) else None,
            "xdiff": round(float(last["xatt"] - last["xdef"]), 2),
            "trend": round(trend, 2),
            "games": int(len(g)),
            "as_of": str(last["date"])[:10],
        })
    rows.sort(key=lambda x: -x["xdiff"])
    # league ranks (1 = best) for attack (high good), defence (low conceded good)
    for key, rev in (("xatt", True), ("xdef", False), ("xedge", False)):
        vals = [x for x in rows if x[key] is not None]
        vals.sort(key=lambda x: -x[key] if rev else x[key])
        for i, x in enumerate(vals, 1):
            x[f"{key}_rank"] = i
    for i, x in enumerate(rows, 1):
        x["rank"] = i
    return rows


def league_norm(ratings: pd.DataFrame) -> dict:
    return _standardise(ratings.dropna(subset=["xdef", "xatt"]))
