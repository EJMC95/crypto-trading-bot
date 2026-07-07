"""Compose the weekly round-preview markdown (Build Spec §8).

Produces outputs/round_preview.md — fixtures with model probabilities, expected
margins/totals, confidence tiers and value-flag placeholders (live quoted odds land
with the Odds API key in Phase 5; until then the market column is blank). The
markdown is the source for the Notion child page under the Build Spec, created by
whichever surface runs the publish (Claude Code session or the Phase 5 Cowork task).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"


def confidence(p: float) -> str:
    d = abs(p - 0.5)
    return "strong" if d >= 0.2 else ("lean" if d >= 0.08 else "coin flip")


def build() -> Path:
    preds = pd.read_csv(OUT / "round_predictions.csv")
    rnd = preds["round"].iloc[0]
    lines = [
        f"# 🏉 {rnd} preview — model probabilities",
        "",
        f"_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs "
        "market 0.2075). Margins/totals from the tier-2 Monte Carlo. Paper only — "
        "no quoted-odds comparison until the odds API key lands (Phase 5)._",
        "",
        "| fixture | kickoff | blend P(home) | margin | total | call |",
        "|---|---|---|---|---|---|",
    ]
    for r in preds.itertuples(index=False):
        p = r.p_home_blend
        pick = r.home if p >= 0.5 else r.away
        pp = p if p >= 0.5 else 1 - p
        lines.append(
            f"| {r.home} v {r.away} | {pd.Timestamp(r.date):%a %d %b %H:%M} "
            f"| {p:.1%} | {r.exp_margin_home:+.1f} | {r.exp_total_points:.0f} "
            f"| {pick} ({pp:.0%}, {confidence(pp)}) |"
        )
    lines += [
        "",
        "**Model spread this round:** games where the tiers disagree by >10% are the "
        "ones to watch for team-list news — that disagreement is usually roster "
        "signal one model has and the other hasn't.",
    ]
    disagree = preds[(preds["p_home_elo"] - preds["p_home_gbm"]).abs() > 0.10]
    for r in disagree.itertuples(index=False):
        lines.append(f"- {r.home} v {r.away}: Elo {r.p_home_elo:.0%} vs GBM {r.p_home_gbm:.0%}")
    path = OUT / "round_preview.md"
    path.write_text("\n".join(lines))
    return path


if __name__ == "__main__":
    print(f"preview -> {build()}")
