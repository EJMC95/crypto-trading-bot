"""Apply on-the-day signals to the model, stringently (Build Spec §5/§7).

The contract, kept deliberately narrow so signals can't inject noise:

1. Confirmed team list  -> REPLACES the squad the tryscorer sim assumes. This is a
   pure correctness fix (score the players actually named), so it feeds props/SGM
   directly. Provisional/absent lists fall back to the last-game proxy and the game
   is tagged lower-confidence.
2. Weather (rain)       -> a BOUNDED, documented multiplier on each team's expected
   try count (wet ball suppresses scoring). Flows to totals and ATS consistently
   because both derive from the same lambda. Capped at -12%; cited as an assumption
   pending a local wet-weather backtest, never a free parameter.
3. Spine changes + news -> FLAGS only. A late spine change genuinely moves a match,
   but its win-prob impact isn't in the validated blend, so we surface a caution
   rather than fabricate a number. News is advisory, never numeric.

Provides helpers consumed by scripts/run_phase4.py (squad override + weather mult)
and build_signal_overlay() which writes outputs/round_signals_applied.json for the
dashboard: per game an info-confidence tag, the flag list, and baseline-vs-adjusted
totals.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
SIGNALS = OUT / "round_signals.json"

# NRL.com position label -> uselessnrlstats code (for the positional-prior fallback
# on players with no try history).
POSITION_CODE = {
    "Fullback": "FB", "Winger": "W", "Centre": "C", "Five-Eighth": "FE",
    "Halfback": "HB", "Hooker": "HK", "Prop": "FR", "2nd Row": "2R",
    "Lock": "L", "Interchange": "B", "Reserve": "B",
}

# Wet-weather scoring suppression. NRL wet-track analyses put total points ~8-12%
# below dry expectation in genuine rain; we scale by rain probability × intensity
# and cap the effect. This is an ASSUMPTION (labelled as such) until a local
# archive-weather backtest replaces it.
MAX_WET_SUPPRESSION = 0.12


def load_signals() -> dict | None:
    if not SIGNALS.exists():
        return None
    return json.loads(SIGNALS.read_text())


def signals_by_pair(sig: dict | None) -> dict:
    if not sig:
        return {}
    return {(g["home_id"], g["away_id"]): g for g in sig["games"]}


def named_squad(entry: dict, side: str) -> pd.DataFrame | None:
    """side: 'home'|'away'. Confirmed named 17 as [player_id, position-code]."""
    if not entry or not entry.get("team_lists_confirmed"):
        return None
    rows = entry[f"{side}_17"]
    df = pd.DataFrame([{"player_id": p["player_id"],
                        "position": POSITION_CODE.get(p["position"], "B")}
                       for p in rows if p.get("player_id")])
    return df if len(df) >= 13 else None


def weather_multiplier(entry: dict) -> tuple[float, str | None]:
    """Bounded try-lambda multiplier from the venue forecast (1.0 = no effect)."""
    w = (entry or {}).get("weather")
    if not w or w.get("precip_prob") is None:
        return 1.0, None
    prob = float(w["precip_prob"]) / 100.0
    mm = float(w.get("precip_mm") or 0.0)
    intensity = min(1.0, mm / 2.0)              # ~2mm/h reads as steady rain
    severity = prob * max(intensity, 0.35 if prob >= 0.6 else 0.0)
    mult = 1.0 - MAX_WET_SUPPRESSION * severity
    if mult >= 0.995:
        return 1.0, None
    return mult, (f"{w['precip_prob']}% rain / {mm:.1f}mm at kickoff → "
                  f"tries ×{mult:.2f} (wet-weather suppression, assumption)")


def _last_starting_spine(hist: pd.DataFrame, team_id: str,
                         asof: pd.Timestamp) -> set[int]:
    from . import player_rates
    sq = player_rates.squad_asof(hist, team_id, asof)
    return set(sq["player_id"].dropna().astype(int))


def game_flags(entry: dict, hist, asof) -> tuple[list[dict], str]:
    """Return (flags, info_confidence) for one fixture."""
    flags: list[dict] = []
    if not entry:
        return flags, "low"

    confirmed = entry.get("team_lists_confirmed")
    conf = "high" if confirmed else ("provisional"
                                     if entry.get("home_17") else "low")

    # spine changes vs who last started
    if confirmed:
        for side, tid in (("home", entry["home_id"]), ("away", entry["away_id"])):
            last = _last_starting_spine(hist, tid, asof)
            for p in entry[f"{side}_17"]:
                if p["is_starter"] and p["is_spine"] and p.get("player_id") \
                        and last and int(p["player_id"]) not in last:
                    flags.append({
                        "severity": "warn", "kind": "spine-change",
                        "text": f"{entry[side]}: {p['player']} named at "
                                f"{p['position']} — a spine change the win-prob "
                                f"model doesn't price; treat with caution."})

    # weather
    _, wtext = weather_multiplier(entry)
    if wtext:
        flags.append({"severity": "info", "kind": "weather", "text": wtext})

    # news (advisory)
    for side in ("home", "away"):
        for n in (entry.get(f"news_{side}") or [])[:3]:
            if {"out", "injury", "suspension"} & set(n["flags"]):
                who = (" — " + ", ".join(n["players"])) if n.get("players") else ""
                flags.append({"severity": "info", "kind": "news",
                              "text": f"{entry[side]} news{who}: {n['headline'][:110]}"})
    return flags, conf


def build_signal_overlay(baseline_pred: pd.DataFrame, adjusted_tries: dict,
                         hist, asof) -> Path:
    """Write outputs/round_signals_applied.json for the dashboard/preview."""
    sig = load_signals()
    by_pair = signals_by_pair(sig)
    games = []
    for r in baseline_pred.itertuples(index=False):
        entry = by_pair.get((r.home_id, r.away_id)) if hasattr(r, "home_id") else None
        flags, conf = game_flags(entry, hist, asof)
        mult, _ = weather_multiplier(entry or {})
        base_total = float(r.exp_total_points)
        games.append({
            "home": r.home, "away": r.away,
            "info_confidence": conf,
            "team_lists_confirmed": bool(entry and entry.get("team_lists_confirmed")),
            "weather": (entry or {}).get("weather"),
            "weather_try_mult": round(mult, 3),
            "baseline_total": round(base_total, 1),
            "adjusted_total": round(base_total * mult, 1),
            "flags": flags,
        })
    payload = {"round": sig.get("round") if sig else None,
               "built_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
               "games": games}
    OUT.mkdir(exist_ok=True)
    (OUT / "round_signals_applied.json").write_text(json.dumps(payload, indent=1, default=str))
    return OUT / "round_signals_applied.json"
