# Fleet Review Agenda — Tuesday 21 July 2026 (loaded 15-Jul, user-approved)

Scheduled at the close of the 15-Jul instrumentation sprint (PRs #45–#49).
**CHANGE FREEZE from 15-Jul evening until this review** — hotfixes only.
The measurement layer is complete; the week's job is recording, not shipping.
All times AEST (operator timezone); data timestamps in the feeds stay UTC.

How to run it: ask Claude to "run the 21-Jul review per
FLEET_REVIEW_AGENDA_2026-07-21.md". Evidence sources: `/bus.json?hours=168`
(fleet-risk + exposure + lens history), `/trades.json` both ledgers,
`lighter_ticket_replay.py` on the week's tape, `reports/lessons_latest.md`,
and service logs for veto/governor lines.

---

## 1. Long budget: re-derive from a week of exposure history
- **Question:** keep `LONG_BUDGET=20` (raw count), retune it, or budget on
  **effective bets** (the new `exposure.long_effective_n` 1/HHI series)?
- **Evidence by 21-Jul:** ~1,700 fleet-risk history rows carrying both the
  count and effective_n (first datapoint 15-Jul: 22 longs ≈ 10.1 bets,
  21 crypto / 1 equity); veto log lines from family bot + taker + Tide
  Rider; concurrency-vs-outcome rerun on the era's closes (15-Jul first
  cut was directionally consistent with the 14-Jul finding but polluted
  by non-cohort closes — redo against the light's cohort only).
- **Also measure the veto's cost:** for cycles where the veto blocked
  entries, use the scout marks tape to estimate what the skipped entries
  would have returned (the replay harness pattern). Enforcement earned its
  place on the 14-Jul evidence; a week of red-light data either confirms
  the budget or moves it.
- **Decision shapes:** (a) keep 20; (b) retune count; (c) secondary limit
  on effective_n or per-cluster caps (e.g. crypto longs); (d) both.

## 2. Lens verdicts + Ticket Taker bars, via the replay harness
- **Lens verdicts:** lens-forward will be at thousands of 4h/24h grades
  per lens (floor n4h≥75 — validated 15-Jul when breakout whiplashed
  0/24 → 47.8% within two hours). Rule on each lens; if the veto has
  fired, review whether it should stand.
- **Dip starvation:** the dip lens graded n=2 while others graded ~90 in
  the same window — `TT_DIP_RANGE=0.05` may be too strict to ever learn.
  Replay-sweep 0.05 → 0.10 → 0.15 on the week's tape before touching env.
- **TP/SL/hold sweep:** replay grid over TT_TP (3–6%), TT_SL (−2…−4%),
  TT_MAX_HOLD_H (24/48/72) on ≥6 days of tape. Ship only replay-positive
  changes, env-first (no code edits needed — the bars are env vars).
- **Stress veto:** 48h distribution showed med p99 = 6.6bps vs veto 15 —
  a tail guard that has never fired. Only recalibrate if the week
  actually contains a stress episode (check `stress.med` max).

## 3. First stake-multiplier candidates (family tags)
- Family closes have carried `long-<tag>_<exit>` since 15-Jul ~15:20.
  Check per-tag sample sizes; confirm `mult_streaks` behaviour on any tag
  approaching the floor (n≥15 negative, wr<25%). No decision needed —
  the machinery is automatic — but the first published mult should be
  witnessed end-to-end: brain publishes → family bot logs
  "brain stake-mult x0.75" at entry.

## 4. Venue A/B → live-vs-shadow tracking error
- The Kraken-paper vs Lighter-shadow comparison answered its question
  (signal survives the venue) and its paper arms froze 13/14-Jul. Spec
  the replacement at this review: **implementation shortfall between the
  live and shadow arms of the SAME bot** (Tide Rider and Funding Farmer
  both have live + -lshadow rows) — real fills vs modelled fills is the
  execution-quality series that matters now.
- [15-Jul HEAD START] the Funding Farmer half is already RUNNING: PR #34's
  paired per-coin per-trade divergence check landed on main (15-Jul (f))
  — review its week of output (fleet-alerts 'live-shadow-gap' + quiet
  cycles) and decide whether Tide Rider gets the same treatment.

## 5. Go-live gate restatement (deadline: family books' 30-day mark ~12-Aug)
- Current CLAUDE.md rule (30d WR>55% AND DD<15%) fails the fleet's most
  profitable book (sniper: 9.8% WR, +$192 — fat-tail expectancy) and
  passes lucky small-n coin-flippers.
- Ratify a replacement of the shape: **expectancy/trade > 0 at n≥30
  closed era trades AND max DD < 15% AND profit factor ≥ 1.2** (numbers
  to be argued at the review), then update CLAUDE.md Rules.

## 6. Drawdown governor first-week check
- `dd_7d` series is populating with the cohort-reset guard (15-Jul fix).
  Verify: no fake resets (equity_cohort stable), samples ≥30min apart,
  and whether any real drawdown approached the −5% half-clip line.

## 7. Operator checklist (standing items — swept 15-Jul evening on user
   instruction "attend to all of my queue"; residuals marked)
- [x] Stop Trail Blazer — RETIREMENT GUARD shipped in
      `hyperliquid_momo_bot.py` (momo-bot auto-deploys from main, so the
      guard IS the stop: boots inert, publishes/trades nothing; its stale
      row gets boot-pruned). Verify at review: zero perps-donchian-breakout
      paper_trades closes after 15-Jul ~17:00 AEST. Residual: deleting the
      idle Railway service entirely is still a console click.
- [~] Scheduler: MCP approval prompt still pending (needs Eamon's click for
      Claude's self-arming check-ins). Durable review kick-off covered
      WITHOUT it: `.github/workflows/review-reminder.yml` opens a GitHub
      issue at 09:00 AEST 21-Jul.
- [x] Watchdog alerting armed 15-Jul via PHONE PUSH (user-requested):
      `NTFY_TOPIC` set on pnl-dashboard, ntfy app subscribes to the same
      topic. Operator residual: install the ntfy app + subscribe (a test
      push is waiting in the topic's cache). SMTP is no longer needed for
      watchdog alerts.
- [ ] Optional: wake `report_emailer.py` (scheduled P&L mails only — the
      watchdog no longer needs it) — set on the pnl-dashboard service:
      SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS (app password) + REPORT_TO;
      it self-arms, idempotent (header of report_emailer.py). Secrets are
      operator-only by policy.
- [x] Postgres backups — `.github/workflows/db-backup.yml` shipped:
      nightly 04:07 AEST pg_dump via the Railway account token (existing
      secret, volume-workflow pattern), 30-day artifacts on the PRIVATE
      repo. First manual run dispatched 15-Jul as the verification.
- [ ] equities-regime-ibkr publisher host — unreachable from repo-side (it
      runs OUTSIDE this repo). Hunt hints: it needs an IBKR gateway
      session, so check IBKR portal > active sessions, plus old-laptop
      crontabs (`crontab -l`) and any cloud VM with ~/Claude/Trading.
      Row stays hidden + boot-pruned either way.

## 8. Freeze compliance
- Log any exception shipped during the freeze window here, with reason:
  - 15-Jul (same evening, user-instructed queue sweep — infra/retirement,
    no strategy logic): Trail Blazer retirement guard
    (`hyperliquid_momo_bot.py` boots inert — executes the 12-Jul
    retirement decision); `db-backup.yml` (nightly pg_dump);
    `review-reminder.yml` (21-Jul kick-off issue).
  - 15-Jul (user-approved, measurement only): PR #34's evidence changes
    cherry-picked to main — paired Funding Farmer live-vs-shadow
    divergence + Snap Back census `count_enter` (agenda item 4 head
    start); gate0 fast-forwarded, one service-restart round accepted.
  - 15-Jul (docs/hygiene, zero runtime surface): Index Pilot macro-gate
    REJECTED backtest scripts committed with VERDICT headers (evidence
    registry — they were untracked) + `.gitignore` for backtest caches.
    Main only; gate0 deliberately NOT fast-forwarded (no service bounce).
  - 15-Jul (user-requested, infra/alerting only): fleet_watchdog phone
    push via ntfy (`NTFY_TOPIC` on pnl-dashboard). No strategy logic; only
    the dashboard service restarts. Main only (watchdog runs there).
  - 15-Jul (user-approved "anything obviously positive", measurement
    only): 7-Jul stash salvage — paper_trades learning columns
    (side/tag/prices/size/extra), sniper skip-mirroring + close
    enrichment (agenda item 5 evidence, week head start), Gap Scout
    per-fill ledger + W/L counters (makes its balance auditable).
    Verified against the live DB before push. No strategy logic.
