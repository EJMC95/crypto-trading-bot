# Improvement audit — 9-Sep-2026 (branch `claude/audit-9sep`, not pushed, not deployed)

**Eamon's brief:** identify and implement improvements that increase risk-adjusted performance, reliability and maintainability without damaging existing bots — inspect first, no deploy / push / restart / trade, protected constants and existing bot definitions byte-for-byte unchanged unless approved, new bots appended only, backtest profit is not a verdict.

**How the work was done.** Baseline captured (`/pnl.json`, `/bus.json`, the clean suite on `origin/main`), an isolated worktree, ten read-only subsystem readers (each returned a structured map with file:line evidence), the findings de-duplicated and the ones that matter re-verified by hand against the code, then the smallest isolated changes with tests and mutation rounds. The adversarial-verification and proposal-panel stages of the audit workflow were refused by a session usage limit and re-queued; everything marked **CONFIRMED** below was verified by me in the code or on the live payload, everything marked **REPORTED** is a reader's finding I did not independently reproduce.

**Bottom line.** No strategy-parameter change is proposed: every performance-shaped candidate in the brief has already been measured and refused on this fleet's own tape (§G). What the audit found instead are three concrete gaps around the real-money path — an exit path with no external watcher, a duplicate-position view that pools paper into real money, and a hold clock that the running book and the replay that tunes it disagree about — plus one infrastructure gap (the mum-live service has no restart policy). Two of them ship in this branch as advisory/monitoring organ changes with no bot touched; one edits a bot definition and was exported as a patch, then approved by Eamon and applied in the same branch; one is an operator action.

---

## 0. Baseline and safety receipts

| item | value |
|---|---|
| audit base | `origin/main` 2faa3a1 at start → rebased onto e81b74e (other sessions pushed (zn)/(zo) mid-audit) |
| branch | `claude/audit-9sep`, one commit carrying the code, tests, the approved P1 patch, changelog entry, toml and this report; **pushed as a branch on Eamon's instruction, not merged to main** |
| `/pnl.json` before | 2026-09-09 06:03:45Z (16:03 AEST), 16 rows, live_pnl +190.07, live_equity 1,024.65 |
| `/pnl.json` after | 2026-09-09 12:59:34Z (22:59 AEST), 15 rows, live_pnl +196.56, live_equity 1,031.14 |
| clean suite on `origin/main` (2faa3a1) | 4,106 passed · 5 skipped · **2 failed**, both `audit_test_imports` on Python 3.9 (`sys.stdlib_module_names` is 3.10+); another session fixed this on main the same evening |
| suite on this branch (rebased on e81b74e) | **4,187 passed · 3 skipped · 0 failed** (135.9s) |
| offline CI guards on this branch | 14 of 14 `audit_*.py` scans green, `session_state --check` green (15 carried items, none stale) |
| protected constants | `pnl_dashboard.py` byte-identical to `origin/main`, so `SLOW_LOOP`, `STALE_SECONDS`, `EXPECTED`, `LABELS`, `CURRENT_BOTS` are untouched |
| existing bot definitions | every bot, venue, rail and grader file byte-identical to `origin/main` EXCEPT `lighter_ticket_taker.py`, changed only by the P1 patch Eamon approved (list in §"Existing bots confirmed unchanged") |

**P&L before/after (per row).** Every delta is live trading — a `closed` or `open` count moved or open positions were marked to market — and no row shows an accounting-only change. The one structural difference, `freqtrade-georgia-lshadow` missing from the after-read, is another session's deploy: commit bdb2733 ((zo), on `origin/main`, deployed by its own `pnl-dashboard` path) added the row to `RETIRED_ROWS` at pnl_dashboard.py:229; it was absent from `RETIRED_ROWS` at my audit base 2faa3a1. This branch touches neither the dashboard nor any publisher, so it cannot have moved a row.

| row | Δ equity | Δ pnl_abs | Δ closed | Δ open | verdict |
|---|---:|---:|---:|---:|---|
| band-kelly-lshadow | −1.32 | −1.32 | +29 | −1 | trading |
| book-bezos-lshadow | −3.43 | −3.43 | +1 | −1 | trading |
| book-hull-lshadow | +0.12 | +0.12 | 0 | 0 | MTM (10 open) |
| book-kiyosaki-lshadow | +0.10 | +0.10 | 0 | 0 | MTM (5 open) |
| freqtrade-avo-maria-lighter | +2.87 | +2.87 | 0 | 0 | MTM (6 open) |
| freqtrade-avo-maria-lshadow | −1.03 | −1.03 | 0 | 0 | MTM (5 open) |
| freqtrade-georgia-v3-lshadow | +1.13 | +1.13 | +4 | +2 | trading |
| freqtrade-mum-lighter | +3.62 | +3.62 | +3 | −2 | trading |
| freqtrade-mum-lshadow | +0.06 | +0.06 | +1 | 0 | trading |
| lighter-perp-sniper-lshadow | 0.00 | 0.00 | 0 | 0 | unchanged |
| lighter-ticket-taker-lshadow | +10.33 | +10.33 | +1 | 0 | trading |
| perps-funding-carry-lshadow | +1.99 | 0.00 | 0 | 0 | MTM (10 open; pnl_abs is realised-only on this book) |
| perps-funding-spread-lshadow | −2.76 | −2.76 | 0 | 0 | MTM (10 open) |
| pm-albanese-lshadow | −0.07 | −0.07 | +1 | 0 | trading |
| pm-turnbull-lshadow | 0.00 | 0.00 | 0 | 0 | unchanged |
| freqtrade-georgia-lshadow | — | — | — | — | removed by (zo) on main, see above |

---

## A. Current architecture

- **Venue.** Lighter-only perps, zero fees measured (`lighter-market.fees` 0/0 on 216 books). Every book is $1,000 paper except the two real-money rows.
- **Real money** = one file, `lighter_avo_live_bot.py`, a variant host selected by `FAMILY_LIVE_BOOK`, running 👩 mum (`mum-live` service) and 🙏 avo (`tide-rider-lighter-live`). Strategy objects are the family registry instances by identity (`lighter_family_bot.STRATEGIES`): mum = OversoldRebound 1h, −4% stop, 12 slots; avo = SwingDip 4h, −10% stop, 6 slots. Both long-only. A trading pass every 300s; a telemetry republish every 60s between passes (publish-only). Sizing `clip = equity × gross_x / max_open` (mum gross 5.0×, avo 2.0×, env ceiling `GROSS_X_MAX` = 20 on both), then restrict-only scalers (live clip lever, brain multiplier refused above 1.0, per-coin mmf factor, $5 floor) and caps (SafetyRails notional, halt-room gate, live-cohort long budget, per-symbol cap, coin veto). Exits in-process only — Lighter holds no resting stop — priced off live order-book mids; close = reduce-only market order bounded 2% through the book.
- **Shadow books** (14 rows) each in its own service/image (`Dockerfile.*`), publishing to Postgres `bot_pnl` + `paper_trades` via `bot_pnl_store`.
- **Organs** (main `freqtrade-bots` image, `run_all.sh` loops): scout → taker → tuner (replay-gated levers), brain (stake multipliers, 6.7× either way), fleet_risk (per-cohort long budgets, symbol cap, 7-day drawdown governor, exposure view), fleet_allocation (advisory), fleet_immune (alive-but-sick detectors, phone pages), evidence board, judge (sole writer of `live.*`), proprioception, golive_readiness (the go-live grader: era, integrity, six bars, MTM drawdown fold, horizon), claims ledger, winners' docket.
- **Deploy.** `railway-redeploy.yml` is the only automated path; real money is opt-in by commit-subject marker; verification is by build stamp read-back.
- **Source of truth for P&L.** `bot_pnl` rows (equity, pnl_abs) and the `paper_trades` ledger, graded by `scripts/golive_readiness.py`; the public feeds are `/pnl.json`, `/trades.json`, `/bus.json`.

## B. Bot inventory (from the 06:03Z capture and the live go-live grades)

| row | equity | pnl_abs | closed / open | W/L | sizing | gate n / mean% / t / maxDD | verdict |
|---|---:|---:|---:|---:|---|---|---|
| 👩 freqtrade-mum-lighter (REAL) | 580.85 | +60.43 | 102 / 4 | 75/27 | clip $242, 12 slots, gross 5.0× (cap 20×), n_eff 1.92, ρ 0.36 | 101 / +0.396 / 2.06 / 12.0% | on_track (window 11.5d < 30d) |
| 🙏 freqtrade-avo-maria-lighter (REAL) | 443.80 | +129.64 | 18 / 6 | 13/5 | clip $148, 6 slots, gross 2.0× (cap 20×), n_eff 2.45, ρ 0.29 | 18 / +3.275 / 2.65 / 12.3% | on_track (n 18 < 30) |
| 👩 freqtrade-mum-lshadow | 1,047.18 | +47.18 | 104 / 1 | 78/26 | 12 slots | 95 / +0.565 / 3.07 / 1.0% | on_track |
| 🙏 freqtrade-avo-maria-lshadow | 1,046.13 | +46.13 | 37 / 5 | 28/9 | 6 slots | 34 / +2.592 / 3.42 / 1.4% | **READY** |
| 🎫 lighter-ticket-taker-lshadow | 1,163.02 | +163.02 | 340 / 8 | 154/186 | 8 slots, vol_clip | 198 / +1.068 / 2.44 / 4.6% | **READY** |
| 🌾 perps-funding-carry-lshadow | 1,118.01 | +106.43 | 125 / 10 | 63/62 | 12 slots | 34 / +0.400 / 3.14 / 1.8% | unprojectable (halves −13.19/+37.96) |
| ⚖️ perps-funding-spread-lshadow | 945.48 | −54.52 | 178 / 10 | 89/89 | K=5 ×2 legs | 158 / −1.328 / −1.57 / 5.2% | unreachable (pre-registered read 1-Oct) |
| 🔮 freqtrade-georgia-lshadow | 1,011.91 | +11.91 | 289 / 0 | 151/138 | 5 slots | 277 / +0.064 / 0.50 / 2.2% | undecidable → retired by (zo) today |
| 🔭 freqtrade-georgia-v3-lshadow | 998.55 | −1.45 | 125 / 3 | 61/64 | 5 slots | 125 / −0.023 / −0.23 / 0.8% | underpowered |
| 🏗️ pm-albanese-lshadow | 995.61 | −4.39 | 75 / 1 | 22/53 | $25 × 3 | 74 / −0.241 / −0.60 / 0.9% | underpowered |
| 💼 pm-turnbull-lshadow | 1,004.20 | +4.20 | 53 / 0 | 32/21 | $25 × 3 | 52 / +0.275 / 1.31 / 0.2% | on_track |
| 🪁 band-kelly-lshadow | 863.78 | −136.22 | 648 / 3 | 260/388 | $80 × 4, 90s loop | 633 / −0.145 / −1.36 / **26.0%** | unreachable (decision with Eamon) |
| 🚀 book-bezos-lshadow | 977.00 | −23.00 | 38 / 1 | 12/26 | $100 × 5 | 38 / −0.649 / −1.32 / 4.0% | unreachable (docket day pending) |
| 🎯 lighter-perp-sniper-lshadow | 991.68 | −8.32 | 49 / 0 | 19/30 | 4 slots | 49 / −0.832 / −0.97 / 1.0% | underpowered |
| 🧮 book-hull-lshadow | 1,003.04 | +3.04 | 5 / 10 | 5/0 | $80 × 4(10 held) | below floor | — |
| 🏦 book-kiyosaki-lshadow | 1,024.88 | +24.88 | 8 / 5 | 6/2 | $80 × 6 | below floor | — |

Fleet risk at capture: pooled light **red** (21 longs vs 20 budget) while both cohorts read green (live 10/20, shadow 17/26); `pair_concentration` BTC 2 / SPY 2 / XAU 2; symbol cap 3, nothing at cap; 7-day governor `clip_scale` 1.0.

## C. Likely weaknesses (ranked; status = my verification)

1. **CONFIRMED — A refused EXIT on a real-money leg is invisible to every monitor.** `lighter_avo_live_bot.py` ~3070-3075 catches `market_close` failures, prints, `continue`s; the only reject telemetry is in the entry branch; `status` stays `online`. Nothing pages until the daily-loss halt fires and `flatten_stuck_sickness` sees a halted row. **Shipped: `fleet_immune.stop_stuck_sickness` (§H-1).**
2. **CONFIRMED — The (wr) breakout clock split holds only in the replay.** `entry_bars()` (~1521) stamps `MAX_HOLD_H` on every lens; the manager (~2566) grafts that stamp over `bull_exit`'s `BRK_MAX_HOLD_H`; the replay does not graft. With `taker.max_hold_h`=24 and `BRK_MAX_HOLD_H`=48 a 30h-old breakout exits in the book and runs in the replay. Neutral today (both 48, no lever open, ready-freeze holds it). **Proposed patch P1 (§H-3).**
3. **CONFIRMED — `mum-live` has no restart policy.** Railway service config read-only at 23:0x AEST: `mum-live` deploy config carries `runtime V2, numReplicas 1` and **no `restartPolicyType`**; `tide-rider-lighter-live` gets `always` from `railway.tickettaker.toml` (`configFile` set). Railway's default is on-failure with a retry cap; with 4 real legs held and no resting stops on the venue, a crash loop abandons the positions. **Operator action (§H-4).** Also observed: both live services show a `STAGED` patch (patchId a622602b…, 15/31 changes, `config: {}`) — contents not readable here; worth a deliberate accept-or-discard.
4. **CONFIRMED — Both real-money books held the same bases (SPY, XAU) and the only view of it pooled paper.** **Shipped: `fleet_risk.cohort_overlap` (§H-2).**
5. **CONFIRMED — `GROSS_X_MAX` is env-set to 20× on both live rows, above `stop_dead_above` (mum 4.17× universe-worst, 10.6× on the held basket; avo 3.33× / 6.7×)**, and `gross_x()` clamps only to the env. This is Eamon's on-record (yl) setting; the consequences are published every loop (`stop_reachable`, `liq_gap_held_pct`, `all_slots_stop_pct` 0.20 on both = 5pp over the 15% gate bar). Reported, no change — see §F.
6. **REPORTED — Real-money per-trade P&L is booked at the decision price when the fill is unmeasured** (63 of 151 live orders carried a measured fill per the store's own note) and with modelled funding, so the gate's mean/t on the live rows omit part of the cost the book paid; the equity series knows it, the per-trade sample does not.
7. **REPORTED — Liquidation distance is structurally unpriced under cross margin** (`headroom.ok=false, reason liq_unpriced` on both rows, allow-listed by the immune organ) and the only liquidation-aware gate is verdict-only on this host.
8. **REPORTED — Stops are evaluated once per 300s and the order path can block up to 120s per call on the request governor**; a rate-limit storm during a crash serialises a 12-leg book's stops.
9. **CONFIRMED, and SHIPPED 10-Sep — The MTM equity series read is capped at 20,000 samples with no truncation flag** (`golive_readiness.equity_series(limit=20000)`); the reader counts three books at exactly n=20000, whose MTM drawdown half then sees ~14.5 trailing days.
10. **REPORTED — Six different slippage/fee owners across the harnesses** (replay 8bps flat on a zero-fee venue, exit sweep 0bps, Monte Carlo 10.2/25bps, the (qq) tiers inside a dated study file); a candidate can get two verdicts from two harnesses.
11. **REPORTED — An unregistered publisher is invisible to every monitor at once** (the `CURRENT_BOTS` filter drops it from `/pnl.json`, which both watchdogs, the live audit and the roster audit read).
12. **REPORTED — Proprioception replays taker levers without the up-resolver**, so breakout/breakoutup — 61% of the READY book's closes — are structurally absent from its $-counterfactual.
13. **REPORTED — The three delta-neutral funding books grade a P&L with no price term, basis or hedge cost**; realisable only with an off-venue hedge that the model does not carry.
14. **REPORTED — 🪁 kelly's own hold-watch reads the price moving against it after every exit (t −3.37 at +120m)** while the book runs ~30 closes/day at a 26% drawdown; decision is with Eamon (pre-registered read returned "to Eamon" 7-Sep).

## D. Data-quality risks
- `CandleCache` serves the last good bars on repeated fetch failure with no age bound (family ~867): a stale BTC regime read or a stale avo exit signal can persist for hours (entries cannot re-fire on an old bar, exits can). REPORTED.
- Equity is guarded (`EquityGuard` cross-checks marks, continuity, capital moves) and a rejected print shuts entries; but the live host runs the guard in persist-reject-streak mode, which its own contract says a daemon should not, so a blind state can persist until the collateral-stable rebase. REPORTED.
- A withdrawal from a live sub-account reads as a mark-to-market drawdown in the equity series (`capital_adjust` corrects `pnl_abs` only), and that series feeds a real-money sizing rail via the DD scale. REPORTED.
- Ledger `closed_at` is TEXT in several formats; both shipped graders read the newest 20,000 / 8,000 rows with no cap check. REPORTED.
- Two suite tests read the production `/trades.json` over the network and skip when unreachable. REPORTED.

## E. Execution and slippage risks
- Entries are booked at requested size and decision price the moment the venue accepts the transaction; a partial or non-fill is reconciled only on the next pass. CONFIRMED in code (`market_open` returns on acceptance; no fill size read).
- Measured live slippage exists only on measured fills (`fill_measured`, `slippage_bps` NULL otherwise); the coin-quality veto refuses coins whose measured slip exceeds 15bps (SHEIN 20.25, USELESS 18.69 at capture). CONFIRMED on the payload.
- No ex-ante impact model in sizing; market orders bounded 2% through a book that may be a ≤20s REST snapshot. CONFIRMED in code.
- The shadow fill model (25-level book walk, decision-price fallback) is calibrated against live fills on a different lens than the one the taker's READY grade rests on. REPORTED.
- Stop overshoot on mum: p90 51.7bps, worst 62.4bps, n=7 — used below as the detector's allowance basis.

## F. Risk-management weaknesses
- **Exit-path liveness had no external watcher** (C-1). Closed in this branch.
- **Correlation across real-money books is unmeasured**: `long_effective_n` is 1/HHI over distinct symbols (17.6 at capture, which its own docstring calls an overstatement); the live cohort has no correlation-aware N_eff and no cross-book duplicate view. The duplicate view is closed in this branch; the correlation-aware measure is §H-5.
- **Daily-loss rail vs the gate bar**: the abs rails ($105 mum / $80 avo ≈ 18% of equity, pct leash 20%) permit a one-day loss larger than the 15% go-live drawdown bar on books already at 12.0% / 12.3% MTM. Config, not code; reported.
- **Leverage ceiling above the stop-alive ceiling** (C-5). Eamon's decision on the record; the arithmetic is published every loop and the immune organ pages when the HELD basket's stop goes dead.
- **Restart policy on mum-live** (C-3). Operator action.
- **The 7-day drawdown governor's `clip_scale` is consumed by paper books only** (live clips ride `live.clip_scale`), and its cohort is 68% paper by equity. REPORTED.

## G. Strategy-overfitting risks — and why no parameter change ships
- The whole Lighter tape is one regime (BTC falling 438d; the live books' ledgers are one bull window since 21-Aug). "Both halves positive" is toothless for directional books here; the 7-Sep regime study showed both live cells earn in bull and lose otherwise, and a regime filter **failed its out-of-sample test** (rotated-label null P 0.115–0.331; an off-switch in 6 of 13 OOS months).
- Already measured and refused on this tape, so not re-proposed: per-trade inverse-vol sizing (6-Sep: mum −0.131pp, avo −0.349pp), leverage as edge (six studies, `t` invariant), cooldown/revenge guards (Douglas: +$27 → −$11), sniper TP retunes (0 of 367 cells survive BH), the Monte Carlo audit's own "no parameter change" (7-Sep).
- Live overfitting hazards that remain: the tuner's exit sweep is an in-sample best-of-N with "both halves" drawn from the same tape; the READY sample of the taker is one regime and one correlated bet; the realised lens veto is a one-way latch. All REPORTED, none actionable without a measurement that does not yet exist.

## H. Proposals, ranked by expected benefit × (1 − risk)

### H-1 · SHIPPED — `fleet_immune.stop_stuck_sickness`: a real-money leg through its own stop pages
- **Hypothesis.** A stop that the venue refuses is silent between "should have fired" and the daily halt; the row already carries what is needed to see it (venue-truth `margin.positions` + `policy.stoploss`).
- **Why it helps.** Converts the largest unwatched real-money failure class (8.2h dark in the recorded incident) into a page naming service, coin and numbers within ~15 min. No expectancy price: it moves nothing.
- **Change.** `fleet_immune.py` +169: `STOP_STUCK_S`=900 (three 300s passes), `STOP_OVERSHOOT_PP`=1.0 (~2× mum's worst measured overshoot), `STOP_STUCK_OK={}` (declared exemptions, empty), `_leg_return`, `stop_stuck_sickness`, wired into `run_once` with its own persisted `stop_seen` memory; selftest arm.
- **Tests.** `tests/autonomy/test_immune_stop_stuck.py` — 23 tests on the real published shapes (finding, control group, I8 detail, overshoot allowance, short-side reading, stale/halted/unreadable/paper/mixed-side fail-safes, forgetting, exemption dict empty, AST wiring pin, memory pin, publisher-key pin across the three files that emit the keys). Mutation rounds via `scripts/mutate.py`: **7 of 7 killed** (one round re-targeted after it landed on the flatten detector's identical text).
- **Validation on history.** Replayed over both captured payloads: 0 findings, 0 clocks started — all ten live legs sat between −2.55% and +8.16% against −4%/−10% stops. Synthetic: SPY at −6.1% pages after 900s, at −4.5% never starts a clock.
- **Risk / reversibility.** Page-only, restrict-nothing; env-tunable thresholds; `IMMUNE_STOP_STUCK_S` / `IMMUNE_STOP_OVERSHOOT_PP`. Deploys with the `freqtrade-bots` image on a push to main (no live-bot restart).
- **Recommendation: Ready for human review.**

### H-2 · SHIPPED — `fleet_risk.cohort_overlap`: duplicate positions per cohort
- **Hypothesis.** "One bet held twice on real money" is invisible when the only duplicate view pools paper.
- **Change.** `fleet_risk.py` +61: pure `cohort_overlap(expo, venues)` → `cohorts.{live,shadow}.{overlap, overlap_n, long_distinct}`, merged into the published `cohorts` map; `cohort_view` unchanged; selftest arm.
- **Tests.** `tests/autonomy/test_fleet_risk_cohort_overlap.py` (7 tests incl. an AST pin that the map is what gets published) + the existing cohort tests; **4 of 4 mutations killed**.
- **Validation on history.** Replayed the way `fleet_risk.main()` resolves rows: before → live `{SPY: 2, XAU: 2}`, after → live `{SPY: 2}`; paper twins of live bases never lift a live count. Declared limit inherited from the exposure view: a live base's paper twin is not in `expo`, so the SHADOW cohort's overlap undercounts twins.
- **Risk.** Advisory (I16); no consumer; reversible by deleting the merge.
- **Recommendation: Keep in shadow mode (advisory) — ready for human review.** Consumer step (a cohort-scoped symbol cap) is §H-5.

### H-3 · APPROVED AND APPLIED (Eamon, 9-Sep 23:10 AEST) — P1 `lighter_ticket_taker.entry_bars(lens)`
- **Hypothesis.** The running manager and the replay that tunes `taker.max_hold_h` clock breakouts differently; making the entry stamp carry the lens-appropriate hold aligns them and preserves the (dg) invariant.
- **Change** (`proposed_patches/P1-zp-taker-breakout-clock-stamp.patch`, 226 lines): `entry_bars(lens=None)` stamps `BRK_MAX_HOLD_H` for breakout lenses under `BULL_MODE`; the one position-open call site passes `lens`; selftest arm; new `tests/autonomy/test_taker_breakout_clock_stamp.py` (6 tests: stamp per lens, bull-off parity, manager-vs-replay parity at 30h and 49h, divergence still on the lever, (dg) survives, AST pin on the call site).
- **Evidence.** Test file reddens on the unpatched taker (4 of 6 fail); with the patch 6/6 green, taker selftest green, **3 of 3 mutations killed**, cage tests green.
- **Baseline vs improved.** Zero trades change at today's constants (48/48, no lever open, ready-freeze active). The change removes a latent path for the (sk)-measured +0.22..0.57pp harm on 156 of 198 era closes of the fleet's only READY book.
- **Approval.** It edits an existing bot definition, so it was first exported as a patch with the taker byte-identical; Eamon approved it and it is applied in this branch. It deploys with `freqtrade-bots` on the merge to main (shadow taker; the live taker arm is retired, so no real-money container restarts).
- **Recommendation: Ready for human review (merge).**

### H-4 · OPERATOR ACTION — restart policy on `mum-live`
- Set `restartPolicyType = always` (no retry cap) on `mum-live`, as `tide-rider-lighter-live` already has via `railway.tickettaker.toml`; or point the service's config file at a repo toml. Reason: every exit of a live perp runs in-process and Lighter holds no resting stop, so an exit-then-no-restart abandons funded legs. I did not change any Railway setting.
- **Recommendation: Ready for human review (operator act).**

### H-5 · PROPOSAL WITH A MEASUREMENT PLAN — correlation-aware live-cohort exposure and a cohort-scoped symbol cap
- **Hypothesis.** The live cohort behaves as fewer independent bets than its symbol count; refusing a second live book from a base the other live book already holds would lower drawdown at no expectancy cost.
- **Needs data first (I19/I26).** From the ledger: the per-trade return of live closes opened while the sibling live book held the same base vs the rest, era-scoped, day-clustered; and the union-basket N_eff series (the live host already computes `held_n_eff` for its own basket at ~3162 via `fleet_bus.basket_n_eff`; a union read needs the sibling's `held` — a telemetry-only edit to the live host, hence a patch for approval). Ship the cap only if the duplicate trades measure worse than the non-duplicates at the fleet's critical value, and never in the window that motivated it (I25).
- **Recommendation: Needs more data.** Not implemented.

### Also reported, no code (measurement plans in §C)
- Friction: one owner for slippage/fee constants across replay/exit-sweep/Monte Carlo, derived from `venue_orders`, with a drift audit in ratchet mode.
- ~~Grader: publish an `mtm_truncated` flag when `equity_series` returns exactly its cap~~ — **DONE 10-Sep**, see the addendum.
- Real-money mean/t with fill provenance folded in (report the measured-fill subset beside the pooled one).

---

## Deliverables

**1. Files inspected** (by the readers and by me): `lighter_avo_live_bot.py`, `lighter_family_bot.py`, `venues/` (safety, lighter_client, equity_guard, fills, governor, marks), `lighter_ticket_taker.py`, `lighter_ticket_replay.py`, `lighter_market_scout.py`, `lighter_scout_tuner.py`, `paper_broker.py`, `funding_carry_bot.py`, `lighter_funding_spread_bot.py`, `lighter_book_hull_bot.py`, `lighter_book_kiyosaki_bot.py`, `lighter_funding_bot.py`, `funding_basis.py`, `lighter_band_kelly_bot.py`, `lighter_perp_sniper.py`, `lighter_book_bezos_bot.py`, `lighter_book_douglas_bot.py`, `parliament_main.py`, `fleet_risk.py`, `fleet_bus.py`, `fleet_allocation.py`, `fleet_tuning.py`, `fleet_immune.py`, `fleet_proprioception.py`, `experiment_judge.py`, `evidence_board.py`, `bot_learn.py`, `brain_stats.py`, `scripts/golive_readiness.py`, `bot_pnl_store.py`, `scripts/claims_ledger.py`, `scripts/winners_docket.py`, `scripts/edge_audit.py`, `scripts/ceiling.py`, `pnl_dashboard.py`, `fleet_watchdog_svc.py`, `cleanup_legacy_bots.py`, `run_all.sh`, `.github/workflows/*`, `Dockerfile.*`, `railway.tickettaker.toml`, `tests/` (registry, policies, fixtures), `scripts/mutate.py`, `scripts/audit_*.py`, plus `HANDOFF.md`, `CLAUDE.md`, the last week of `CHANGELOG.md`, `EDGE_AUDIT_2026-09-02.md`, `MONTECARLO_RISK_AUDIT_2026-09-07.md`, the untracked `STUDY_REGIME_SPLIT_2026-09-07.md`.

**2. Files changed on the branch:** `fleet_immune.py`, `fleet_risk.py`, `lighter_ticket_taker.py` (P1, approved), `tests/autonomy/test_immune_stop_stuck.py` (new), `tests/autonomy/test_fleet_risk_cohort_overlap.py` (new), `tests/autonomy/test_taker_breakout_clock_stamp.py` (new), `railway.mumlive.toml` (new, inert), `CHANGELOG.md` (entry (zv)), this report.

**3. Exact changes:** see §H-1..H-3; full diffs in `git diff origin/main` and the patch file.

**4. Existing bots confirmed unchanged:** byte-identical to `origin/main` — `pnl_dashboard.py`, `lighter_avo_live_bot.py`, `lighter_family_bot.py`, `lighter_market_scout.py`, `lighter_scout_tuner.py`, `funding_carry_bot.py`, `lighter_funding_spread_bot.py`, `lighter_book_hull_bot.py`, `lighter_book_kiyosaki_bot.py`, `lighter_band_kelly_bot.py`, `lighter_perp_sniper.py`, `lighter_book_bezos_bot.py`, `parliament_main.py`, `venues/safety.py`, `venues/lighter_client.py`, `bot_pnl_store.py`, `fleet_bus.py`, `fleet_tuning.py`, `fleet_allocation.py`, `scripts/golive_readiness.py`. The single exception is `lighter_ticket_taker.py`, changed only by the approved P1 patch; `git diff --name-only origin/main` lists exactly the files in item 2.

**5. `/pnl.json` before/after:** §0 table; no accounting change on any existing row; one row removed by another session's deploy ((zo)).

**6. Tests run.** Baseline on `origin/main` 2faa3a1: 4,106 passed / 5 skipped / 2 failed (py3.9 stdlib gap, fixed upstream since). Final branch: **4,187 passed / 3 skipped / 0 failed**. Targeted: 30 new tests green; immune + fleet-risk sets 151 green; taker patch 6/6 green with the patch and 4/6 red without it; three module selftests green; 14 offline CI guards green; mutation rounds 7/7, 4/4, 3/3 killed.

**7. Backtest methodology.** None of the shipped or proposed changes alters an entry, exit, size or filter at today's constants, so a P&L backtest would return the baseline by construction. Validation instead was: replay of the detectors over the captured live payloads (before and after), synthetic mutation of the real published shapes, manager-vs-replay parity for the taker clock (the replay is the harness the tuner uses), and mutation testing of every guard. No historical-data backtest was run and none is claimed.

**8. Baseline vs improved metrics.** Identical: net return, maxDD, Sharpe/Sortino, win rate, profit factor, average trade, turnover, exposure, slippage/fees and regime splits are unchanged for every book because no trade changes. What changes is coverage: the exit path of both real-money books is now watched from outside; a real-money duplicate position is now a published number.

**9. Drawdown / turnover / slippage / fee comparison.** Unchanged (see 8).

**10. Signs of overfitting.** None: the two detector thresholds are derived from the loop cadence (3 × 300s) and a measured overshoot distribution (2 × worst of n=7), not fitted to outcomes; the taker patch has no free parameter.

**11. Remaining risks.** §C 5–14; the panel's adversarial verification did not run, so the REPORTED items carry reader confidence only; the detector cannot see a failed ROI/max-hold exit (no opened-time in the margin block) — stops only; the shadow-cohort overlap undercounts live bases' twins; two other sessions are pushing to main concurrently, so the branch must be rebased again before any merge.

**12. Recommendations.** H-1 ready for human review (merge → auto-deploys the organ image). H-2 keep in advisory/shadow mode, ready for human review. H-3 approved by Eamon and applied; merge with the rest. H-4 operator action on Railway. H-5 needs more data. Everything else: reject for now (evidence weak or measured negative), recorded above with the number that refused it.

---

## Addendum — the adversarial verification stage, 10-Sep

The audit's verification stage (two independent lenses per finding: a
code-reachability lens and a history/doctrine lens) was cut short twice by
usage limits on 9-Sep and completed **22 of 44 verdicts** before running out of
credits on 10-Sep. The proposal panel and the completeness critic never ran.
What follows is what the verdicts that DID complete say, including where they
correct this report. Findings with no verdict keep the status they had.

**CONFIRMED by both lenses — the three items this branch acts on:**

| finding | verdicts | note |
|---|---|---|
| The (wr) breakout clock split holds in the replay, not in the manager (P1) | high + medium, neither refuted | "CONFIRMED by control-flow trace and a read-only reproduction"; the history lens adds that the record "asserts the opposite of what the code does" |
| A refused exit is invisible on the row | high + medium, neither refuted | one lens trimmed high → medium because the damage window is bounded by the equity-triggered halt; both agree nothing sees a refused close before it |
| `mum-live` has no restart policy | high + high, neither refuted | the history lens notes the claim **overstates scope**: the record is silent on `trail-blazer-live` too, and that service's inclusion rests on an inference the record's own precedent cuts against |

**REFUTED — two items this report listed as REPORTED are withdrawn:**

- **The three delta-neutral funding books' modelled P&L.** Three verdicts,
  all refuting. The measurements reproduce, but the omission is a *declared,
  pinned* modelling choice with a documented go-live prerequisite, and every
  funded mode is refused by a hard allowlist at process start in all three
  books — so the failure scenario has no code path. C-13 in this report is
  withdrawn.
- **🪁 kelly's hold-watch refutes its own thesis.** Refuted: the claim
  misreads the instrument (the hold-watch grades the EXIT horizon, not the
  entry side), and "nothing acts on it" is contradicted by
  `golive_readiness.DECIDED_UNTIL['band-kelly']`, which is selftest-pinned.
  C-14 is withdrawn as stated; the pre-registered read with Eamon stands
  unchanged.

**CONTESTED:** boot-time venue construction on the live host (two lenses
confirm the unguarded constructor and the re-raise; a third refutes on the
grounds that the avo slot's `restartPolicyType = "always"` makes it a restart
rather than an outage). It sharpens H-4 rather than replacing it — the
service without that policy is the one exposed.

**NEW, CONFIRMED, and not in the body of this report:** `scripts/audit_coverage_floors.py`
does not floor the files that ARE the real-money surface. Its `FLOORS` table
(27 entries) contains neither `lighter_avo_live_bot.py` nor
`lighter_family_bot.py`, and line 32 still heads the taker and the Farmer as
"the two live real-money bots" — both retired from live duty (13-Aug and
22-Aug). Three verdicts, none refuting; the record is silent on it. The
existing `test_coverage_policy.py` checks that a test surface EXISTS, not how
deep it goes. This is a maintainability finding with no trade consequence.

**SHIPPED in this branch (10-Sep).** Both live-host files now carry floors,
measured the way CI measures: `lighter_avo_live_bot.py` 83.4% → floor 80,
`lighter_family_bot.py` 60.7% → floor 57. The measurement basis is calibrated,
not trusted — the same local run reproduces all 27 pre-existing floors with
zero breaches and a minimum slack of +1.4pp — and since it runs on Python 3.9
where CI runs 3.11 the two enter ~3pp under measured rather than the table's
usual ~2, with the extra point declared in the table. Both are
mutation-verified (dropping either file's coverage trips the guard and names
it; the untouched report stays green), and the heading that called two retired
arms "the two live real-money bots" is corrected in place per I12.

**Also shipped 10-Sep, after verifying it myself against the live payload
(C-9).** The grader's MTM window truncates silently: `fetch_state_history` is
`ORDER BY ts DESC LIMIT`, so the 20,000 cap is a trailing window, and three
books sit at exactly it today (sniper, albanese, turnbull — 14.2-14.7 days
each) with kelly at 16,762 and climbing. Truncation can only understate the
drawdown, which is the permissive direction on the one bar that is not
clip-invariant, and it shrinks the peak-equity denominator that bar has used
since (yz). Neither live book is at the cap today and no verdict moves; at
~288 snapshots/day both arrive there in about ten weeks. The fix publishes a
read receipt and a `truncated` / `window_limit` pair through a single composer
(`book_mtm`); it gates nothing, because making truncation refuse a verdict is
a gate re-spec and therefore yours. 13 tests, 7 of 7 mutations red.
