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
  in the blend; revisit with lineup/weather features. CLV tracking is LIVE without
  an API key: `src/ingest/odds_live.py` pulls keyless public JSON feeds from four
  AU books (Ladbrokes/Neds Entain API, Pointsbet, Unibet Kambi CDN — probed
  2026-07-07; TAB geo-blocks non-AU IPs, Sportsbet is Akamai-protected, neither is
  bypassed). `scripts/capture_odds.py` snapshots prices, de-vigs a consensus,
  writes value flags + the paper ledger (`src/eval/ledger.py`,
  `outputs/paper_ledger.csv`). A near-kickoff snapshot proxies the closing line;
  the weekly aussportsbetting Wayback refresh grades CLV properly. A real Odds
  API/Betfair key remains a nice-to-have, not a blocker.
- Phase 4 (player props + SGM simulator) — DONE, see `outputs/phase4_report.md`.
  ATS = hierarchical Poisson-gamma try rates × tier-2 team try expectation
  (Poisson thinning). Gates passed: walk-forward ATS backtest 2022–25 beats
  positional base rates (Brier 0.1401 vs 0.1408 — thin; minutes/lineup data is
  the upgrade path); joint-sim consistency within MC error. SGM = 50k player-level
  joint sims (`src/sgm/`), correlation lifts 1.17–1.49× on R19 candidates.
  Quoted-SGM grading via `data/manual_odds/roundNN.csv` (no public SGM feed).
- On-the-day signals (src/ingest/signals.py) — DONE. NRL.com named-17 team lists
  (matched to canonical player_ids), Open-Meteo venue weather, Google News RSS
  (keyword-flagged, advisory). Stringency rule: only verifiable signals move a
  number — confirmed team lists REPLACE the tryscorer sim's squad (src/features/
  signal_adjust.py + props_player named_squad); a wet forecast applies a bounded
  (<=12%) try-lambda multiplier; spine changes + news are FLAGS only (win-prob
  impact isn't validated, so it's surfaced, not fabricated). Output
  round_signals.json + round_signals_applied.json (info-confidence + flags).
- Prediction track record (src/eval/track_record.py) — DONE. Logs every model call
  (win/margin/total/top-tryscorer) at snapshot, grades after the round from NRL.com
  final scores + per-player tries: win hit-rate + Brier, margin/total MAE + bias,
  tryscorer hit-rate + Brier, per-round trend. SQLite `predictions` table +
  track_record.json. Distinct from the paper *betting* ledger.
- Phase 5 (automation) — CLI + service DONE, deploy + team-list ingest remain.
  `python -m src.cli {refresh,predict,preview,feed,odds,grade}` is the weekly
  rhythm (Cowork owns scheduling). `service/` + `railway.json` serve
  `outputs/nrl.json` (pnl-dashboard pattern) — deploy from the Mac per
  `service/README.md`. Tuesday team-list ingest (nrlR fetch_lineups port) and
  weather now scanned live (signals). Team-list ingest DONE via the
  match-centre endpoint.

## Note on repo location
This is the standalone private repo `github.com/EJMC95/nrl-predictor` (canonical as
of 2026-07-07). The project was originally built on the crypto-trading-bot branch
`claude/nrl-predictor-phases-1-2-vtb133` while repo creation was blocked; history
was migrated here via `git subtree split` (see scripts/migrate_to_standalone.sh).
That branch is now frozen — all new work happens here. Data is not in git: run
`pip install -r requirements.txt && python scripts/run_phase1.py` to re-download
and rebuild data/raw + data/processed.

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
- `python scripts/capture_odds.py` — live 4-book odds snapshot → consensus,
  value flags, paper-ledger entries, market-aware preview + feed.
- `python scripts/run_phase4.py` — props backtest gates + 50k SGM sims + candidates.
- `python -m src.cli signals` — scan team lists + weather + news for the round.
- `python -m src.cli snapshot` — log the round's model calls for later grading.
- `python -m src.cli track` — print/refresh the prediction track record.
- `python -m src.cli grade --round N` — Monday grading: settles ledger + track record,
  prints a Notion-ready block. Ledger lives in `data/ledger.db` (committed;
  mirrors in outputs/paper_ledger.csv + data/processed/ledger.parquet).
