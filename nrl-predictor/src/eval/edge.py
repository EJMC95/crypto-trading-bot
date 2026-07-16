"""Professional edge layer — the value/staking/CLV machinery a real desk runs on.

Nothing here invents new predictions; it turns the model probabilities and the
de-vigged market into the outputs that actually decide (and grade) a bet:

- expected value (EV) of taking the best available price,
- fractional-Kelly stake sizing with a hard cap (bankroll growth without ruin),
- a value board ranking every side of every fixture by EV, line-shopped to the
  best of the four books,
- closing-line-value (CLV) and yield/ROI performance from the paper ledger — CLV
  being the single most honest measure that an edge is real, independent of
  short-run variance.

Paper-track only. A positive EV here is a model opinion, never a betting
instruction; the dashboard keeps the responsible-gambling framing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# quarter-Kelly is the desk-standard compromise: most of the growth, a fraction
# of the variance and drawdown. Capped so a single fat edge can't over-concentrate.
KELLY_FRACTION = 0.25
KELLY_CAP = 0.05          # never stake more than 5% of bankroll on one bet
MIN_EDGE = 0.0            # value board shows EV>0; tighten per taste


def ev(model_p: float, price: float) -> float:
    """Expected value per unit staked at decimal `price` given the model prob."""
    if price is None or not np.isfinite(price) or price <= 1:
        return float("nan")
    return float(model_p * price - 1.0)


def kelly_fraction(model_p: float, price: float, frac: float = KELLY_FRACTION,
                   cap: float = KELLY_CAP) -> float:
    """Fractional-Kelly stake as a share of bankroll. 0 when there is no edge."""
    if price is None or not np.isfinite(price) or price <= 1:
        return 0.0
    b = price - 1.0
    p = min(max(float(model_p), 0.0), 1.0)
    full = (b * p - (1 - p)) / b        # classic Kelly
    if full <= 0:
        return 0.0
    return float(min(cap, frac * full))


def value_board(market: pd.DataFrame, min_ev: float = MIN_EDGE) -> list[dict]:
    """Rank every side of every fixture by EV at the best available book price.

    Expects the round_market.csv columns: home, away, p_home_blend,
    market_p_home, best_odds_home, best_odds_away, books. Returns positive-EV
    selections, richest edge first, each with the model/market prob gap, the
    best price + implied, EV, and a quarter-Kelly suggested stake."""
    if market is None or not len(market):
        return []
    rows = []
    for r in market.itertuples(index=False):
        p_home = getattr(r, "p_home_blend", None)
        if p_home is None or not np.isfinite(p_home):
            continue
        mk_home = getattr(r, "market_p_home", np.nan)
        move_pp = pd.to_numeric(getattr(r, "move_home_pp", None), errors="coerce")  # +ve = to home
        _steam = getattr(r, "steam", False)
        steam = bool(_steam) if isinstance(_steam, (bool, int, float, np.bool_)) and pd.notna(_steam) else False
        for side, team, opp, mp, mk, price, disp in (
            ("home", r.home, r.away, p_home, mk_home, getattr(r, "best_odds_home", np.nan),
             getattr(r, "disp_home", np.nan)),
            ("away", r.away, r.home, 1 - p_home, 1 - mk_home if np.isfinite(mk_home) else np.nan,
             getattr(r, "best_odds_away", np.nan), getattr(r, "disp_away", np.nan))):
            e = ev(mp, price)
            if not np.isfinite(e) or e <= min_ev:
                continue
            # is the market moving toward (confirming) or away from our pick?
            side_move = (move_pp if side == "home" else -move_pp) if np.isfinite(move_pp) else None
            rows.append({
                "match": f"{r.home} v {r.away}", "selection": team, "opponent": opp,
                "side": side, "model_p": round(float(mp), 4),
                "market_p": round(float(mk), 4) if np.isfinite(mk) else None,
                "edge_pp": round(float(mp - mk) * 100, 1) if np.isfinite(mk) else None,
                "best_price": round(float(price), 2),
                "implied": round(1 / float(price), 4),
                "ev_pct": round(e * 100, 1),
                "kelly_pct": round(kelly_fraction(mp, price) * 100, 2),
                "books": int(getattr(r, "books", 0) or 0),
                "disp_pct": round(float(disp) * 100, 1) if np.isfinite(disp) else None,
                "move_pp": round(float(side_move), 1) if side_move is not None else None,
                "steam": steam,
                "fair_price": round(1 / float(mp), 2) if mp > 0 else None,
            })
    rows.sort(key=lambda x: -x["ev_pct"])
    return rows


def performance(ledger: pd.DataFrame) -> dict:
    """Professional betting scorecard from the paper ledger: record, staked, P&L,
    ROI/yield, average CLV, a running bankroll curve, and settled-bet Brier."""
    if ledger is None or not len(ledger):
        return {}
    led = ledger.copy()
    settled = led[led["result"].isin(["W", "L", "P"])].copy() if "result" in led else led.iloc[0:0]
    out: dict = {"n_logged": int(len(led)), "n_settled": int(len(settled))}
    if len(settled):
        settled = settled.sort_values("logged_at")
        staked = float(settled["stake_units"].sum())
        pnl = float(settled["pnl_units"].fillna(0).sum())
        w = int((settled["result"] == "W").sum())
        l = int((settled["result"] == "L").sum())
        p = int((settled["result"] == "P").sum())
        out.update({
            "record": f"{w}-{l}-{p}", "wins": w, "losses": l, "pushes": p,
            "staked_units": round(staked, 1), "pnl_units": round(pnl, 2),
            "roi_pct": round(100 * pnl / staked, 1) if staked else None,
            "bankroll_curve": [round(float(x), 2) for x in settled["pnl_units"].fillna(0).cumsum()],
        })
        # settled-bet Brier (were the logged model probs calibrated on what we bet?)
        if "model_prob" in settled:
            y = (settled["result"] == "W").astype(float).to_numpy()
            pm = settled["model_prob"].to_numpy(float)
            m = np.isfinite(pm)
            if m.any():
                out["bet_brier"] = round(float(np.mean((pm[m] - y[m]) ** 2)), 4)
    # CLV: did we beat the closing line? (price taken vs closing)
    if "clv" in led:
        clv = pd.to_numeric(led["clv"], errors="coerce").dropna()
        if len(clv):
            out["clv_avg_pct"] = round(100 * float(clv.mean()), 2)
            out["clv_beat_rate"] = round(float((clv > 0).mean()), 3)
            out["clv_n"] = int(len(clv))
    return out


def calibration(probs: np.ndarray, outcomes: np.ndarray, bins: int = 5) -> list[dict]:
    """Reliability table: predicted vs realised frequency in probability buckets.
    Honest calibration is the difference between a model and a hunch."""
    probs, outcomes = np.asarray(probs, float), np.asarray(outcomes, float)
    m = np.isfinite(probs) & np.isfinite(outcomes)
    probs, outcomes = probs[m], outcomes[m]
    if not len(probs):
        return []
    edges = np.linspace(0, 1, bins + 1)
    table = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (probs >= lo) & (probs < hi if hi < 1 else probs <= hi)
        if sel.sum() == 0:
            continue
        table.append({"bucket": f"{int(lo*100)}-{int(hi*100)}%",
                      "n": int(sel.sum()),
                      "predicted": round(float(probs[sel].mean()), 3),
                      "actual": round(float(outcomes[sel].mean()), 3)})
    return table
