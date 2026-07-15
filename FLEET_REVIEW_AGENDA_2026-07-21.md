# Fleet Review Agenda — Tuesday 21 July 2026 (loaded 15-Jul, user-approved)

Scheduled at the close of the 15-Jul instrumentation sprint (PRs #45–#49).
**FREEZE LIFTED same evening by the user** ("take off the freeze as I believe
this could be a breakthrough" — the evidence-board v2 build). This review and
its agenda STAND; the standing doctrine (restrict-only actuators,
backtest-first, shadow-first promotion) was never a freeze rule and binds as
before. §8 remains the log of what shipped during the freeze window.
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
  [15-Jul late: AUTOMATED — `lighter_scout_tuner.py` now runs exactly this
  loop hourly (starving-lens ladder + winner expansion + the TP/SL/hold
  sweep, all replay-gated both-halves, levers via fleet_tuning). At review:
  grade its enactment history (`scout-tuner` + `fleet-tuning` history)
  instead of hand-running the sweep — did the dip diet widen, did n4h reach
  the floor, did any winner expansion fire, did anything auto-revert.]
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
  - 15-Jul (user: "implement your changes even though the freeze is on —
    take data over the week"): salvage part 2, /history window selector
    (?hours=24/168/720/all) + per-cohort max-DD captions. Dashboard-only,
    zero trading surface. NOT salvaged even with the blanket approval:
    the pair-blacklist actuator (strategy logic; design lost to L4 mults
    — review decides if pair-level throttling rides the mult machinery).
  - 15-Jul evening — FREEZE LIFTED by the user; later ships are normal
    doctrine, not exceptions. First post-freeze ship: EVIDENCE BOARD v2
    (`evidence_board.py`: scoring/corroboration/synthesis/auto-verdicts/
    phone notify; proposals SHADOW-mode restrict-only, EVBOARD_MODE).
    NEW REVIEW ITEM: grade the board's week of shadow proposals +
    auto-verdicts; promote EVBOARD_MODE only if the would-act log earns
    it (the L2-light path). Also queued: coin-veto remove-side
    hysteresis (ADA flap, board:veto-flap:ADA) — backtest-first.
  - 15-Jul (post-lift, restrict-only data hygiene): 🎯 Launch Sniper —
    EWY + EWYG added to `TOKENIZED_BASES` on the operator's note
    ("consider dropping EWY/USDT"). Ledger evidence: EWY flap-listed
    on/off 9 times 4→13-Jul, every close `delisted` within ~2h, 8/9 red
    (net −$1.9) — the exact class the 3-Jul filter exists for (EWZ/EWT
    already in the set). No backtest is possible for new listings; the
    ledger is the evidence, per the 7-Jul wave-2 precedent. Main only;
    the sniper service redeploys, gate0 untouched.

## 9. Launch Sniper: 03–05 UTC session sizing (operator note, 15-Jul)
Operator observation: "UTC03-05 is event-listing-sniper's best session — a
future tweak could size up there." Ledger check (15-Jul, 339 closes since
26-Jun) confirms the raw numbers: the 03–05 UTC entry block is **+$350.06 on
39 closes vs −$106.66 on the other 300**, win rate 23% in-block vs 8.7%
outside. Plausible mechanism too (Asian-venue listing windows). BUT the
block's profit is ~4 payoff events — ANSEM +$274 (28-Jun, one position split
TP-partial/TP), INDEX +$51 (15-Jul), BIBI +$45 (8-Jul), DATA +$4 — and the
median in-block trade is still −$0.10. A sniper's P&L is lottery-shaped;
whichever hour bucket caught the biggest ticket is always "the best session"
in hindsight.
- **Decision for the review:** keep recording, DON'T size up yet. Evidence
  bar for a session-size multiplier: materially more in-block payoff events
  (n≥30 winners is the brain's own floor), both-halves hold-up, and rule out
  the confound that 03–05 is really "which exchange" not "which hour"
  (session sizing on 4 events is the Trail Blazer lucky-window lesson).
- Cheap week task: log entry-hour histograms of payoff events (>$5 closes)
  per exchange from `paper_trades` — one query at the review, no code.

## 10. Gap Scout: the +$5k odometer — make it honest, then widen the net
   (operator question, 15-Jul: "how can the gap scanner's +5000 be? are we
   missing things it's picking up on — can we better implement positive
   finds so we don't miss out?")

**Diagnosis (15-Jul forensics).** `pnl_abs +$5,225` (gross +$6,995) is an
odometer, not a book: fills are only booked when the modelled edge ≥ 0 (no
losing trades exist), and each ~19s scan re-books a still-open gap as a
fresh $1,000 clip — a gap that persists one hour is counted ~190 times.
The counter restarted from $0 when the 14-Jul persistence fix first
deployed (the pre-fix container showed +$6,095 at the 14-Jul review), so
the whole +$5,225 accrued in ≲30h — then froze: every retrievable log
window on 15-Jul shows zero PAPER-FILL lines and best depth-confirmed edge
≈ −1%, with the restored balance bit-identical across deployments.
Burst-then-flat is the signature of a few milked stale-book/collision
episodes, not a steady edge. One artifact caught in the act (15-Jul ~20:50
AEST): the bus's "1.0% majors dislocation" on DOT/USDT was Coinbase
Exchange's DEAD DOT/USDT book ($2.8k/day volume, last trade 4½h old)
priced 1% off Kraken's live mid — Stage 1 must use `last` where bulk
tickers carry no bid/ask (CBX, Gemini), so dead books manufacture
persistent gaps; the 14-Jul DISLOC_BASES fix restricted the gauge to major
BASES but not to live BOOKS. Attribution of THIS +$5,225 is unrecoverable
(pre-ledger era: upsert row, ephemeral CSV, purged deploy logs).
**On "missing out": nothing real is being missed on the CEX legs** —
combined base-tier taker fees are 0.66–1.0%, the engine's own docstring
says flat is the honest expected result, and the fleet has no CEX
execution anyway (Lighter-first). The genuinely useful exhaust (Lighter
premium, majors gauge) is already on the bus.

**A. Honesty fixes (booking side — tighten):**
1. ✅ per-fill ledger + W/L counters shipped 15-Jul (j). Verify at review:
   every newly booked dollar has a `paper_trades` row
   (`long-xarb_paper-fill`, route in tag).
2. **Episode dedup** — one booking per (symbol, buy_ex, sell_ex) gap
   episode; re-arm only after the gap closes below threshold. Kills the
   ×190 compounding while keeping every find visible.
3. **Bookable-pair floors** — fresh REAL bid/ask on both venues (never
   `last`), minimum book volume/depth beyond the clip; apply the same
   floor to the published `liquid_top_pct` (major-BASE ≠ liquid-BOOK —
   the DOT/USDT case above).
4. **Balance epoch** — when 2–3 ship, zero the odometer (park the old
   number in extra as `legacy_balance`) so the printed figure is 100%
   ledger-backed from then on.

**B. Widening (detection side — the operator's ask; publish/census-only):**
Principle: widen the funnel's MOUTH, tighten its THROAT. Every widening
below lands only after A — widening a fictional counter just makes bigger
fiction faster.
1. **More venues** — Kraken/CBX/Gemini is the most efficient, least
   dislocation-prone corner of crypto. Real gaps live on second-tier
   venues: KuCoin, Gate, MEXC, Bitget, HTX (all in ccxt; needs a
   Railway-region reachability probe — Binance 451s from there, OKX/Bybit
   likely geo-block).
2. **Cross-quote comparison** — compare USD vs USDT/USDC books through a
   LIVE USDT/USD reference (Kraken lists it) instead of excluding them:
   roughly doubles the comparable universe and upgrades the gauge into a
   real stablecoin-stress detector. The 1:1-par shortcut stays banned.
3. **Capacity census** — walk the already-fetched books at
   $250/$1k/$5k/$25k (pure math, no extra fetches): a per-find capacity
   curve, the one number that could ever justify real execution.
4. **Mine the >5% band instead of silently skipping it** (5–7
   artifacts/scan today): with a base-identity check (ccxt metadata/name
   match; persistent-offset fingerprint ⇒ collision), the residue is
   listings/halts/depegs — Launch/Perp Sniper + listing-intel food, not
   arb.
5. **Budget knobs** — PREFILTER_GAP 0.20→0.10%, MAX_BOOK_FETCHES 30→60,
   IF scan time allows (the loop already runs ~19s against a 10s poll —
   measure first).
**Anti-widenings** (named so nobody re-litigates): bigger clip size alone,
softer haircuts, USDT=USD at par, looser `MIN_NET_EDGE` booking — all
inflate fiction without new information; and no Lighter-side duplication
(`lighter_market_scout` owns the per-book Lighter view).

**Decision shapes:** (a) A only — census organ + cleaned gauge; (b) A + B,
judged on episodes/day by class (stale-book / collision / real) from the
new ledger; (c) retire the CEX legs, keep the Lighter-premium publisher;
(d) a real-execution project — only if the capacity census shows
fee-beating capacity on a venue we'd actually fund (out of doctrine
today).

**IMPLEMENTED 15-Jul evening (user: "implement now" + growth mandate —
"if the scanner just restricts then we eventually will only stay still").**
A2–A4 + B3 + the gauge fix shipped in `cross_exchange_arb.py` (epoch-2:
episode dedup, TOUCH-DEPTH bookable floor from the real books — live
probes killed both bulk-ticker floors: CBX/Gemini `fetch_tickers` carry
neither volume nor bid/ask — balance epoch reset with the odometer parked
in `extra.legacy`, capacity curve per booking, `gapscout-census` bot_state
key, cross-quote gauge via live USDT/USD, `liquid_top_pct` now
depth-confirmed book-mids with `liquid_ref_pct` kept for continuity).
B1/B5 shipped as bounded levers, not defaults. **NEW: the GROWTH RAIL**
(`fleet_tuning.py` + evidence board ENACT tier) — the board autonomously
widens the scanner's net when the census runs quiet (24h → prefilter
0.15%/45 books; 48h → 0.10%/60 books + kucoin,gateio; 96h → +mexc),
every lever whitelisted, hard-bounded, TTL'd (auto-revert), phone-notified
per step; lanes gated by `FLEET_TUNING_ENACT_LANES` (default paper-scanner
ONLY — trading-book lanes stay proposal-only until THIS review adds them).
**Grade at the review:** (i) episodes/day by class + capacity curves from
the ledger; (ii) the growth rail's enactment log (`fleet-tuning` history)
— did widening surface anything real, did auto-revert behave; (iii) whether
any trading-lane lever (e.g. TT dip range, replay-validated) earns a
registry entry; (iv) LIVE lane (shipped 15-Jul late, user mandate):
grade `live.clip_scale`'s enactment log — did the earn-gates (30 closes &
positive on EVERY live row) hold, did any down-scale fire correctly, and
should the ladder/cooldown/bounds move; (v) EXPERIMENT JUDGE: by the
review, candidate 'enter-gate-0.30' will be ~6 days into its shadow run —
inspect `xp-judge` state + verdicts + the stamped extra.bars rows, decide
whether the promotion bar (7d/30 closes/+0.5pp both-halves/live n≥10) is
right BEFORE the first promotion can fire (~22-Jul earliest). B2-full (cross-quote BOOKING) and B4 (>5% identity check)
remain open — the census now records both bands.
