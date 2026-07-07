# 🏉 nrl-predictor

NRL match predictor + SGM analyser. **Paper-track only.**

Spec and phase plan live in the Notion page "🏉 NRL Predictor — Build Spec v1"
(Claude Context Hub); repo conventions in [CLAUDE.md](CLAUDE.md).

## Quick start

```bash
pip install -r requirements.txt
python scripts/run_phase1.py          # ingest → Elo → backtest → round predictions
python scripts/build_season_review.py # 2026 season review workbook
```

## Phase 1 result (2026-07-07)

Walk-forward 2015–2025, Brier / log loss (draws = 0.5):

| model | Brier | log loss |
|---|---|---|
| naive home-rate baseline | 0.2456 | 0.6859 |
| **Elo (tier 1)** | **0.2186** | **0.6287** |
| de-vigged closing line | 0.2075 | 0.6036 |

Elo beats the naive baseline in every season 2015–2025 → phase-1 gate **passed**.
The closing line stays ahead of Elo (as it should) — that gap is what tiers 2–3
(Poisson/Skellam, GBM) go after. See `outputs/phase1_report.md`.
