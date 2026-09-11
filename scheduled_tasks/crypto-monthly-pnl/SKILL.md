---
name: crypto-monthly-pnl
description: Monthly go-live board — era-aware gate reads, decidability census, capital-vs-claims, retirement/promotion recommendations
---

Generate the MONTHLY GO-LIVE BOARD (runs on the 1st for the prior month).
READ-ONLY on the fleet: no trades, no dry_run/keys/lever/config changes, no
deploys. (Rewritten 2026-08-04 — the old text graded V4–V8 Kraken paper bots
against a checklist retired 14-Jul. The gate now lives in code:
`scripts/golive_readiness.py`, spec in CLAUDE.md "GO-LIVE GATE".)

PROJECT_DIR = /Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot

This is the month's capital-allocation sitting: which books EARNED a decision
this month — go live, keep accruing, or retire. Import the standard, never
restate it: bars come from `golive_readiness` (`bar_map`/`BAR_NAMES`), eras
from `POLICY_ERA`, integrity from the payload. Prose is what drifts.

Steps:
1. cd "$PROJECT_DIR" && git fetch origin -q. Then:
   export DATABASE_PUBLIC_URL="$(railway variables --service Postgres --kv | grep '^DATABASE_PUBLIC_URL=' | cut -d= -f2-)"
   DATABASE_URL="$DATABASE_PUBLIC_URL" .venv/bin/python3 scripts/golive_readiness.py
   DATABASE_URL="$DATABASE_PUBLIC_URL" .venv/bin/python3 scripts/audit_ledger_integrity.py
   (golive_readiness on an unset URL prints a confident "READY: none" over
   zero rows — verify the table had rows before believing any verdict.)
   Plus /pnl.json, /periods.json "monthly", /bus.json `fleet-allocation`.
2. THE BOARD, per living book: gate verdict with WHICH bars bind (era-aware —
   an all-time pass over a stale era is not a pass), MTM-vs-realised drawdown
   (worse-of-both is the bar since (ia)/(iz)), and the allocation organ's
   claim (lower bound). Real-money rows first.
3. DECIDABILITY CENSUS (I17): every book's in-era closes vs its window. A
   book that cannot reach 30 closes at the probe floor inside its window is
   NOT a slow winner — it is undecidable, and it goes on the keep-or-retire
   list with what retiring frees (budget, slots, attention). Decidability is
   the first unit of winning.
4. REGIME COVERAGE: for any directional book near the gate, state which
   regimes its window actually contains (Lighter's tape is one falling-BTC
   regime — a one-regime pass is a pass in that regime only).
5. RECOMMENDATIONS, ranked, each with evidence and the exact next act:
   promote (operator go-live steps named — never executed), keep (what must
   accrue and by when), retire (what it frees, the reversibility switch), or
   re-grade (which basis was wrong). One EXPANSION note if the month's
   evidence supports one, expectancy-priced (I19).
6. Write to "$PROJECT_DIR/reports/monthly_golive_board_<YYYY-MM>.md" (the
   month just ended, resolved in **SYDNEY** local, never UTC).
   **[14-Aug, the `(mb)` class swept into this job:** it fires on the 1st in
   the Sydney morning, which is still the **last day of the ending month in
   UTC** — so "prior month" read off UTC-now names the month BEFORE the one
   being graded, filing every board a month early under a label that already
   has a report. Resolve the month from the Sydney date and, if the target
   exists, rename it aside (`<name>.superseded-<HHMM>.md`) rather than
   overwriting.]
   No email — say the file path in the run output, and if a book is
   genuinely READY or a live row degraded, ALSO create a Gmail draft to
   emcmpg@gmail.com flagging the decision (draft only).

Sydney-local times, labeled. Not financial advice. Go-live is an explicit
operator act — passing the gate is a precondition, never a trigger.