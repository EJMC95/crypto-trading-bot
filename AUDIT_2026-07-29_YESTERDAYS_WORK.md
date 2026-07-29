# AUDIT OF YESTERDAY'S WORK (2026-07-28) — conducted 2026-07-29

*Operator ask: "Audit of yesterdays works." Scope: every commit that landed
2026-07-28 UTC (17 commits: 6 PRs #95–#101 + direct commits, CHANGELOG
letters (do)–(ed)), the two documents written that day
(`FLEET_REVIEW_2026-07-28.md`, `FLEET_AUDIT_2026-07-28.md`), and — per the
standing rule — the LIVE real-money bots regardless of nominal scope.
Method: 5 parallel adversarial review agents over the day's diffs
(live-money surface; promotion pipeline; organs/dashboard; workflows/CI;
radar+backtest methodology), consequential claims re-verified independently
against the live endpoints, GitHub Actions history, and local recomputation.
All times UTC unless labelled AEST.*

---

## 1. Executive summary

- **Everything yesterday claimed to ship, shipped — and the deploy claims
  are PROVEN, not assumed.** All four real-money-adjacent rows publish
  `extra.build` hashes that byte-match a local recompute at `633e8a1`
  (yesterday's final merge): Farmer live+shadow `ddd019900bf0`, Taker
  live+shadow `ae41cb479ef1`; the organ container (Parliament
  `2a518beca465`) and funding-carry (`c33038455892`) match too. Zero arm
  drift, twin-for-twin. O1 (live Taker off its 4-day-old build) and O2
  (judge in the container before the 30-Jul cooldown expiry) are **DONE** —
  the 15:07Z dispatch (`trail-blazer-live, tide-rider-lighter-live,
  funding-farmer-shadow`, success, 9m) plus the 14:58Z auto-deploy landed
  everything, and the (dz) live-money hardening is live on real money.
- **The (dy) receipt pipeline works end-to-end on the running build**:
  post-deploy close rows stamp `src`, `extra.build`, `bars_basis: entry`,
  and the growth receipts in `bars` with the correct arm split (shadow
  `explore_k 2 / conviction scaled / hi 2.2 / slope_gate 1`; live
  `0 / off / 1.0 / 1`). `vol_filter: true` heartbeats on both Farmer arms.
- **The adversarial re-review found real defects in yesterday's work — the
  worst on the two newest real-money paths.** Fixed in this audit
  (selftested; judge + guard fixes mutation-tested): a growth promoter
  that could auto-promote `conviction_hi=2.2`/`explore_k=2` to the live
  Farmer from the exact multi-variable confound the operator just released
  the 0.075 candidate over, live from 30-Jul 09:20Z (§4.1); three defects
  in the Farmer's new blind→heal path that quietly resurrected the
  phantom-halt corner it was built to close (§4.2); a deploy-surface gap
  where #100's own marker-grep fix reintroduced the both-lists class it
  was fixing, invisible to a green `audit_deploy_coverage` (§4.3); and an
  unguarded parse that let one sick radar payload dark the whole evidence
  board (§4.4).
- **One evidence problem, not a code problem:** the vol-character filter
  went LIVE on both Farmer arms citing +$2.44→+$44.52 — but the same
  harness printed baseline +$33.47 the day before (the baseline swings by
  the size of the claimed edge between fetches), the study's own
  pre-registered robustness bar FAILED (its script prints `not robust`),
  and the shipped fail-open rule was never measured on the cohort where it
  diverges from the fail-closed rule the study tested. Direction supported;
  magnitude not canon. Correction appended to the evidence doc; restrict-
  only shape + kill switch bound the downside. §4.5.
- **CI was dark for the morning half of the day** (Actions billing lockout
  ~08:30–14:40Z): #95–#98 and the direct (dt)–(dx) commits merged with NO
  CI; local runs stood in and caught one miss ((dw)'s unregistered
  selftest, fixed in (dx)). CI recovered 14:54Z; both afternoon merge
  commits green; full suite green at HEAD locally today (200 passed,
  1 skipped) and again after this audit's fixes. All four repo guards
  green before and after.
- **Watched item crossed its threshold: explore is STILL at zero opens
  ~40h after the f7cad49 cursor fix** (every close through 20:02Z stamps
  `src: exploit`; both arms flat at audit time). Yesterday's "re-check at
  ~24h" has elapsed — the §3d design question (explore samples only below
  the deep-scan cut) is now the primary hypothesis and belongs to the next
  Farmer session. §6.

## 2. What landed yesterday (the map)

| Window (UTC) | Work | CI state |
|---|---|---|
| 08:07–08:10 | Judge growth-promoter core (53c7e8c); deploy-coverage reason fix (do); Farmer `conviction_hi` receipt | no CI (lockout) |
| 08:37 | **PR #95** — radar `slope_t` de-bias + 👓 bifocal; vol-character filter measured AND implemented (default OFF) | no CI |
| 08:40 | **PR #96** — anti-polling doctrine P1–P6; `ci-notify.yml`; `fleet-weekly-assessment.yml` | no CI |
| 08:56–09:00 | (dt) slope-gate REFUTED on Lighter's tape; f7cad49 explore-cursor fix; 28-Jul review + §3d correction | no CI |
| 08:59 | **PR #97** — selftest registration (main red since 24-Jul) | no CI |
| 09:03–09:39 | (dv) Taker up-regime cache; (dw) `xp_judge_release.py`; (dx) its registration | no CI |
| 09:28 | **PR #98** — Actions-minute diet | no CI |
| 14:58 | **PR #100** — the audit implementation (dy)–(ec): growth pipeline armed, live-money hardening, learning loops, Parliament, observability | green |
| 15:05 | **PR #101** — (ed) mid-hold flap fixture (test-only) | green |
| 15:07–15:17 | Live dispatch: both real-money services + shadow Farmer | success, hash-verified |

## 3. Runtime verification (live endpoints, 2026-07-29 00:04–00:10Z)

Everything yesterday's audit claimed about the running fleet re-verified
true today, on newer data:

- **Watchdog** 0 problems / 0 warnings, 23/23 rows fresh (freshest 10s).
  **Immune** zero sick / zero quarantined. **Proprioception** 0 hurting.
  **Board** 20 items, 0 warn/action. **impl-shortfall** verdict `clean`,
  live slip 0.34bps on 46 orders (~5× headroom under the ~2bps kill line).
- **Judge**: `phase: idle`, `cooldown_until` = 30-Jul 09:20:05Z (exactly
  the documented D3a cooldown), `drift_notified` persisted, growth
  promoter LIVE and evaluating honestly (`last_growth`: "floors: shadow
  1/15, live 8/10" — the O6 cadence arithmetic visible in production).
- **(eb)/(ec) publish claims verified**: `parliament_tuning.
  replay_coverage` is a real per-book number (pm-rudd 69-of-79 closes with
  tape — candles-follow-holdings measurably working); `parliament.
  fleet_lens_7d` beside `lens_7d`; `regime-oracle.grades` + the full organ
  roster readable off-Railway on /bus.json. **xp-queue** heartbeat beating
  (age 54m vs TTL 10800), refuted 17-Jul entries stayed retired.
- **Builds not at HEAD** (all $1k shadow, all expected — no deploy route
  ran for them yesterday): perp-sniper, dislocation (own services,
  pre-#100 builds), trend-daily-lshadow (pre-dates build stamping),
  family/spot rows (gate0 branch, unverifiable from main by design). They
  pick up the (du)/(dz) `bot_pnl_store` changes at their next dispatch.

## 4. Adversarial re-review — findings and what this audit did about them

**Fixed in this audit** (all selftested; judge + guard fixes mutation-tested;
full suite 200 green after):

1. **Growth promoter could auto-promote from a serially-contaminated
   window** (CONFIRMED, latent until 30-Jul 09:20Z — `experiment_judge.py`).
   `growth_step` ran every cycle with no mutual exclusion against the
   serial queue, and `ran_candidate` subset-matches only the growth pair's
   own levers — so the moment `tp-0.06` auto-starts on the shadow twin
   (30-Jul 09:20Z), every growth evaluation window becomes a 3-variable
   A/B, and a promotion would write `live.funding.conviction_hi=2.2` +
   `explore_k=2` (live clips up to 2.2×) on borrowed evidence — the same
   confound class the operator released the 0.075 candidate over (D3).
   **Fix: the promote WRITE now HOLDS while `phase == "running"`**
   (evaluation, reassert, fade and organ-release paths all continue;
   fail-safe promote on unknown phase). Also fixed the promote/release
   asymmetry found in the same pass: promote-time now consults
   `proposal_fade` exactly as reassert-time does (an organ restrict
   proposal could release a promotion one cycle after it steered real
   money, but couldn't block it one cycle earlier). Both mutation-tested.
2. **The Farmer's new blind→heal path had three real defects**
   (CONFIRMED — `lighter_funding_bot.py`; the (dz) hardening's main paths
   all verified correct, these are in the recovery corner it added):
   (a) the heal's `meta.setdefault` could never restore position meta —
   the manage pass seeds junk meta (opened_ts=boot, accrued=0, no
   clip/bars/src) for every held coin BEFORE the heal runs, so the seeded
   junk always won and the next save made it durable (max-hold clocks
   reset, carry under-counted, judge receipts degraded). Now persisted
   meta OVERWRITES (entries are blocked while blind, so every entry
   present at heal time is a reseed), with the seed's one real datum —
   funding accrued since boot — folded in.
   (b) the heal adopted the persisted same-day `day_start`
   unconditionally, while its own comment promised "only when the ledger
   stayed quiet" — a capital move folded while blind then re-armed the
   exact phantom-halt (withdrawal) / masked-rail (deposit) pair the (dz)
   fix closed on the main path. Now the persisted anchor is SHIFTED by
   the net folded this run (the same both-sides rule
   `_fold_capital_moves` documents).
   (c) the heal's `capital_adjust` restore was all-or-nothing — one move
   folded while blind discarded the entire persisted lifetime capital
   ledger (lifetime P&L off by the whole prior total, durably). Now
   merged (persisted history + this-run events, same 20-event cap).
3. **#100's marker-grep widening reintroduced the both-lists class it was
   fixing, invisibly** (CONFIRMED — deploy surface). The widened
   `taker_files`/`farmer_files` greps reference `tickettaker_loop.sh`,
   `Dockerfile.tickettaker`, `Dockerfile.fundinglighter` — none of which
   were in `paths:`, and `requirements.txt` (the real-money signer pin
   `lighter-sdk==1.1.2`, COPY'd into every live/funding/market-context
   image) was in NEITHER list. A marker push touching only those files
   fires no workflow at all — the real-money deploy silently skipped. And
   the guard couldn't see it: `audit_deploy_coverage` audits only
   `AUTO_IMAGES`, and #100's move of the greps into shell variables broke
   its parser for the live services entirely. **Fix: all four files added
   to `paths:`; `requirements\.txt$` added to both live greps + the
   funding-carry and market-context greps; `audit_deploy_coverage` gained
   a variable-form grep parser + a MARKER-ORPHANED check** (every file a
   live marker grep can match must be reachable via `paths:`) with
   fixture selftests — removing a `paths:` entry now turns the guard red.
4. **One sick organ payload could dark the whole evidence board**
   (introduced by #100 — `evidence_board.py`). The radar-senior promotion
   watch parsed `float(radar_state.get("ttl_sec"))` unguarded inside
   `synthesize_expand`, which `run_once` calls unwrapped — a non-numeric
   `ttl_sec` (the exact "alive but sick" payload class `fleet_immune`
   exists for) aborted the ENTIRE board cycle silently, every cycle,
   including the `live.clip_scale` re-assert loop. Fixed: plain numeric
   ceiling (`_fresh` already honors the payload's own ttl with a guarded
   parse).
5. **`bot_pnl_store.fetch_trades` was the one reader left off yesterday's
   `is_open IS NOT TRUE` union doctrine** — trade_analyzer silently
   dropped NULL-`is_open` closed rows. Aligned.
6. **ci-notify's dedup read only the first 30 PR comments** (no
   `--paginate`) — on any PR past 30 comments the marker comment was
   off-page and the same transition re-posted on every trigger, turning
   the dedup into a spammer on exactly the long-lived PRs it exists for.
   Fixed (paginated stream, newest across all pages).
7. **Doc rot corrected**: CLAUDE.md's Railway Setup paragraph (the
   auto-surface is FOUR services + the 24/25-Jul live marker path — the
   "ships only when a human runs `railway up`" list was empty; added the
   build-hash verification recipe) and the P2 doctrine line (watchdog is
   hourly since #98, not "~30 min at $0"). `FUNDING_VOL_FILTER_2026-07-24.md`
   gained the §4.5 correction block.

**Verified correct** (the load-bearing claims of the day, independently
re-traced): the (dz) deposit double-count fix on all four capture branches;
the same-loop conviction cap fix (restrict-direction, selftest pins the
$126-vs-$90 shape); W/L truth on all three close paths; the f7cad49
explore-cursor fix (both bugs real, fix complete, no re-scan loop); (dv)
taker up-regime cache (shadow-only in effect, TTL honored both ends, can't
flip bull-mode); (du) `_close_extra` merge semantics + halted-day
`sl_block` fix (which landed in #100, not 9476811 as the review implies);
(ed) flap fixture (test-only, mutation-honest); judge queue-TTL fail-closed
+ drift-HOLD fallback (genuinely hold-only, seniority pinned); D7 slope
lever end-to-end with mode-prefixed consumption; xp-queue heartbeat
(refuted entries retire, nothing resurrected); release tool writes no
levers and created the D3a cooldown as documented; brain STOPPISH/venue-A/B
resurrections (diagnosis-only, fail-soft, selftest-pinned); Parliament
regime-gate consumption fail-open with kill switch; candle tracking bounded
(cap 60, 7d expiry); board authority unchanged (AUTHOR_LANES intact, radar
consumption fail-open); /bus.json widening leaks no secrets, `?hours`
clamped; review-reminder deletion correct per its own header; tests.yml
still runs on every push/PR (cancel-in-progress only drops superseded
same-ref runs); changelog-check untouched with all six guard jobs; the
slope-gate refutation (dt) methodologically sound on the corrected harness
— its no-action conclusion stands (every fidelity gap found biases toward
over-penalizing the gate).

**Routed, not fixed** (each needs an operator/review decision or a design
seam this audit shouldn't move unilaterally — queued for the 04-Aug review):

- **R1 — release-tool lost-update race** (`xp_judge_release.py --execute`
  vs an in-flight judge cycle): the judge's read→compute→save holds no
  lock, so a release committed mid-cycle can be overwritten by the judge's
  stale save — release vanishes after the tool printed RELEASED. A
  tool-side CAS does NOT close this (the tool already holds FOR UPDATE;
  the losing write is the judge's) — the honest fix is a judge-side
  release-request consume or conditioned save. Narrow window (seconds/hour
  vs rare manual releases). Until fixed: run the tool just after a judge
  cycle logs, and re-check `xp-judge.phase` a minute later.
- **R2 — "refuted candidates retire permanently" is not structural**:
  permanence rests on two rolling caps (incubator lifetime memory [-20:],
  judge verdicts [-10:]) and `FUNDING_GENES` still carries the refuted
  `max_hold_h: [48, 96]` alleles — under enough churn the refuted names
  can regenerate into a fresh queue and burn ≥7d serial slots each.
  Options: durable refuted-set consulted by `funding_proposals`, or drop
  the refuted alleles (the 21-Jul review refuted the knob "at ANY hold").
- **R3 — the faster bar has no elapsed-time gate** (rolling 2.5d window +
  close-count floors only; explore is designed to raise the very cadence
  that clears it faster). The floors are the operator's bar (O6) — noted
  as a design fact, not re-derived here.
- **R4 — brain kind-flip releases a standing regime gate in one run**
  (promotion needs PROMOTE_RUNS=3; release-by-reclassification needs 1):
  the (ea) STOPPISH + venue-A/B widenings make higher-priority diagnosis
  kinds reachable for exactly the books whose `regime_timing` finding the
  Parliament consumer was wired for (gillard, 77-run ACTIONABLE). Shadow-
  only, arguably the more precise diagnosis SHOULD win — but the asymmetry
  deserves a streak gate or at least a kind-flip notification.
- **R5 — Farmer blind-boot is log-only** (no page, row still "online");
  the taker's equivalent exits loudly. A one-page-on-transition would
  close it; left routed because it touches the live bot's boot path and
  R6 is the bigger sibling.
- **R6 — the heal path (and main()) remain harness-less**: my §4.2 fixes,
  like the (dz) originals, are reasoned-and-reviewed but not
  fixture-driven — the Farmer's main loop has no test seam. Extracting
  the heal into a pure helper with fixtures is the structural fix.
- **R7 — metered-CI single point of failure**: the lockout proved tests,
  all six guards, watchdog, backups and auto-deploy die together with no
  push-capable signal (the (dw)/(dx) miss was the measured cost). Fix
  direction: the in-service watchdog alerting when the Actions probe's
  last-run goes stale, or a documented post-outage local-suite rule.
- **R8 — smaller watched items**: fleet-weekly's label-delete failure mode
  + no schema assertion (wrong-but-green report class); ci-notify
  name-coupling to "Tests"/"Changelog check" + a narrow premature-green
  window; vol-filter env parse treats junk as OFF (asymmetric with
  SLOPE_GATE's style) and its ~40-candle fetch burst can make it silently
  inert for an hour under throttle (fail-open, cached); radar near/far
  concentration on two different rulers (publish-only); Parliament
  `closed_trades` 2000-row cap now pressured by the fleet ingest;
  `replay_coverage` absent for exactly the starving books it exists to
  expose; (ea)'s "re-publish-proof" is build-only (other receipt keys
  remain clobber-able on re-publish); (ec)'s "all added (+ deeper history
  set)" is 7-of-12 for history; watchdog Actions cadence now hourly →
  worst-case external detection of a dashboard-down ~doubled (in-service
  5-min layer unaffected for bot-level staleness).

## 5. The letters vs the code (truth-in-ledger check)

(dy)–(ed) substantially match what shipped — every claimed mechanism
exists, is wired, and keeps the fail-safe contract. Four bounded
overstatements found (all recorded in §4/R8; the two that could misdirect
a future reader — "FULL COPY set" and the vol-filter magnitude — are
corrected in place). One mis-citation: (dt) claims consistency with "the
Farmer's known both-halves-negative Lighter verdict" — that verdict was
withdrawn 23-Jul (the standing verdict is both-halves POSITIVE at measured
slip); the refutation's conclusion survives without the borrowed support.

## 6. Watched items — status moves

- **Explore zero-opens: threshold crossed** (~40h post-fix, zero
  `src=explore` rows, both arms flat). The cursor fix is running
  (build-verified), so §3d's structural hypothesis — explore samples only
  below the top-15 deep-scan cut — is now primary. Belongs to the next
  Farmer session; nothing in this audit changes scan behavior.
- **O1, O2 — DONE** (verified §1). **O3–O6** unchanged, still routed.
- **Vol-filter re-validation** joins the operator menu (§4.5 / the doc
  correction): leave ON with the magnitude treated as unproven, or re-run
  the study on ≥2 fresh fetches + the 438d tape before the next config
  decision leans on it.
- **fleet-weekly-assessment**: the (ea) fix is committed but unverifiable
  until its next scheduled run (Sun 02-Aug 23:30Z → Mon 09:30 AEST).
- **30-Jul 09:20Z**: the D3a cooldown expires and `tp-0.06` auto-starts on
  the shadow twin. With this audit's F1 fix, the growth promoter now
  correctly holds its write for the duration — expect `last_growth.why` to
  read "promote HELD: serial candidate running" if the bar ever clears
  mid-candidate. That is the fix working, not a fault.

## 7. Verdict

Yesterday was a high-throughput, high-honesty day — 17 commits, six PRs,
two real defect-hunting documents, and a live-money hardening pass whose
three headline fixes all verified real and correctly fixed — and the
fleet's own receipts (build hashes, entry-time bars, heartbeat env reads)
now make "did it actually ship?" answerable from outside the containers,
which this audit used to confirm every deploy claim. The re-review's
findings cluster exactly where yesterday's speed concentrated: the two
newest paths on real money (the growth promoter's missing serial-exclusion,
the blind→heal corner) and the meta-layer that was fixing itself (the
marker-grep both-lists relapse, caught by neither CI — which was dark all
morning — nor the guard it broke the parser of). All of those are now
fixed, selftested, and where the harness allows, mutation-tested; what
could not be fixed without an operator or a design seam is routed with
mechanics stated (R1–R8). The one standing caution is evidential, not
mechanical: the vol filter is live on a magnitude its own study calls
`not robust` — bounded by its restrict-only shape, but it should not be
cited again until it survives a re-fetch.

*Next review (2026-08-04) additions: R1–R8 above; the vol-filter
re-validation decision; explore's design question (now primary); the first
growth-promoter HELD/promote transition after 30-Jul 09:20Z.*
