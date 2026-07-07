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
The closing line stays ahead of Elo (as it should). See `outputs/phase1_report.md`.

## Phase 3 result (2026-07-07)

Tier 2 (Dixon–Coles-decayed try Poisson → Monte Carlo scores, margins, totals) and
tier 3 (LightGBM stack) added, walk-forward with all choices made pre-2015:

| model | Brier | log loss |
|---|---|---|
| Elo (calibrated) | 0.2194 | 0.6304 |
| Poisson (tier 2) | 0.2287 | 0.6514 |
| GBM (tier 3, experimental) | 0.2287 | 0.6510 |
| **blend (Elo+Poisson stack)** | **0.2188** | **0.6293** |
| de-vigged closing line | 0.2075 | 0.6036 |

The blend is the new champion and adds margin/total distributions. GBM does not
beat Elo yet (features mostly re-encode Elo) and stays out of the blend until
lineup/weather features arrive. See `outputs/phase3_report.md`.
