# CLAUDE.md — nrl-predictor

**Source of truth:** the Notion page "🏉 NRL Predictor — Build Spec v1" under Eamon's
Claude Context Hub. Read it before any work. This file only covers repo conventions.

## What this is
NRL match predictor + SGM analyser. Calibrated win/margin/total probabilities per match,
fair prices for SGM leg combos. **Paper-track only** — never suggest staking real money.

## Status
- Phase 1 (Elo + walk-forward backtest) — DONE, see `outputs/phase1_report.md`
- Phase 2 (2026 season review) — DONE, see `outputs/season_review_2026.xlsx`
- Phase 3 (Poisson/Skellam + GBM) — DONE, see `outputs/phase3_report.md`.
  Champion = Elo+Poisson logistic stack ("blend", Brier 0.2188 vs Elo 0.2194,
  market 0.2075). GBM is experimental only — it does not beat Elo yet and is NOT
  in the blend; revisit with lineup/weather features. CLV tracking blocked on an
  odds API key in `.env`.
- Phase 4 (player props + SGM simulator) — not started
- Phase 5 (automation: Tue team lists, Thu previews; Railway nrl.json service) —
  not started; `src/publish/` already emits `outputs/nrl.json` + `round_preview.md`

## Note on repo location
This project was specced as its own private repo `nrl-predictor`. The Claude Code
GitHub App cannot create repositories (403), so it currently lives as a top-level
directory on a branch of `crypto-trading-bot`. Once the private repo exists, move this
directory there wholesale — nothing in here imports from the trading fleet.

## Conventions
- Python 3.11, deps in `requirements.txt`.
- `data/raw/` is gitignored (downloads land there); `data/processed/` holds tidy
  parquet, also gitignored; `data/reference/` (committed) holds hand-maintained tables,
  most importantly `team_names.csv` — the canonical team-name mapping. **Every join
  between data sources goes through `src/ingest/teams.py`. Never join on raw names.**
- All scrapes polite: cached to `data/raw/`, rate-limited, ToS-aware. Keys in `.env`
  (never committed).
- Walk-forward validation is a gate, not an afterthought: no model output ships
  without a leakage-free backtest against the naive baseline and the de-vigged
  closing line.

## Data sources (see Build Spec §3)
- `data/raw/nrl.xlsx` — aussportsbetting.com results + odds 2009→2025.
  The live site is behind Cloudflare; the ingest falls back to the latest
  Wayback Machine capture (see `src/ingest/results_history.py`).
- `data/raw/uselessnrlstats/` — cleaned CSVs from github.com/uselessnrlstats
  (1908→present matches, player_match_data, ladders, venues).
- NRL.com draw API (`src/ingest/nrl_stats.py::fetch_nrl_draw`) — current-season
  results + upcoming fixtures, endpoint logic ported from the nrlR R package.

## Entry points
- `python scripts/run_phase1.py` — ingest → Elo fit → 2015–2025 walk-forward
  backtest → current ratings + upcoming-round probabilities → `outputs/`.
- `python scripts/build_season_review.py` — Phase 2: 2026 season review workbook.
- `python scripts/run_phase3.py` — Poisson + GBM walk-forward, blend, upgraded
  round predictions (win/margin/total). Run phase 1 first (needs its parquets).
- `python -m src.publish.dashboard_feed` / `python -m src.publish.notion_preview`
  — regenerate `outputs/nrl.json` and `outputs/round_preview.md`.
