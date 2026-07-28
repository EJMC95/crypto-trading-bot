# FLEET REVIEW — 2026-07-28

*Conducted Monday 28-Jul evening AEST (data pulled 18:00–18:25 AEST / 08:00–08:25 UTC;
Sydney is on AEST, UTC+10, no DST in July). Successor to FLEET_REVIEW_2026-07-21.md.
All ledger timestamps below are UTC per fleet convention; times for Eamon are AEST.*

*A concurrent session was actively committing the Farmer growth-lever judge pipeline
while this review ran (53c7e8c, 40263d5, 5bef0f0 landed mid-review, and it pushed the
previously-stranded (dn)). This review reads the tree as of 5bef0f0.*

---

## 0. Executive summary

- **D4 (the pre-committed Farmer decision) resolves in the `<6bps` band — measured
  round-trip slip 0.38bps — but the pre-committed ACTION (STOP 0.10→0.03) is VOID:**
  its evidential basis was withdrawn 22-Jul as a harness artifact (corrected read:
  −$11.57, both halves negative). The superseding 23-Jul evidence on the corrected
  harness at measured cost says the live config already earns. **Verdict: keep the
  live Farmer exactly as configured; no stop tune; no gate widen.** §1.
- **Item-18 step 2 (per-asset regime gate consumes oracle calls) stays REVIEW-GATED:**
  the oracle's self-grades are accruing as designed but are too thin to wire
  (n=2–7/symbol; d1 ≈ coin-flip; ZEC anti-predictive). Re-read next review. §2.
- **Live pair, week 2:** Farmer +$2.06/7d (all-time +$8.08, n=60, t=1.65 — positive,
  not yet significant; radar: `plausible`, ~9.4d to verdict). Taker −$1.26/7d, but
  ~flat (+$0.43/10) since the 24-Jul bull-mode flip to short-divergence-crypto ×4
  slots. Combined live book +$6.07. §4.
- **The radar's honest knife:** the fleet's biggest earner (Yield Harvester shadow,
  +$58.62) is classed **`artifact`** — three single closes (SOXL +12.71, SNDK +10.31,
  ARB +9.67) are $32.69 of the total. The only `real_edge` book in the fleet is the
  **Farmer shadow** — with a "fading" caveat. §5.
- **Organ health is the cleanest it has been:** watchdog 0 problems / 0 warnings,
  immune zero sick/quarantined, respiration SpO2 1.0, proprioception 17 graded /
  3 helping / 0 hurting. The event sentinel measured its own playbook 24% accurate
  (n=178) and self-restricted its detection bars — the self-grading loop closing in
  the restrict direction, unprompted. §6.
- **Three defects found on the promotion pipeline, all fixed this session
  (restrict-/observable-only, mutation-tested, all guards green):** the judge's
  arm-drift HOLD was dark from birth (0/143 ledger rows carried a build stamp —
  the running 0.075 candidate, a confirmed 3-variable A/B past its day floor,
  had nothing but its own close-count floor standing before a misattributed
  real-money promotion); the judge consumed an 11-day-stale xp-queue whose
  refuted candidates would have burned ~a month of serial judge slots; and the
  bull engine's `brk_quality` capture never reached the close row, so the
  winning-criteria analysis would have read zero rows forever. §3, §5.
- **The fleet moved under the review (a good sign):** while this review ran,
  the concurrent session + operator landed (dp)–(ds) — the slope-gate premise
  refuted on Lighter's tape, radar upgrades, and the **vol-character filter
  taken LIVE on both Farmer arms by explicit operator decision** via the (dn)
  marker path. That deploy **converged the Farmer builds at ~18:50 AEST**
  (both arms now `f7044072157f`), resolving the arm-drift and delivering the
  live arm the phantom-close fix + brakes it had been missing (§3e). The
  repaired drift guard now stands watch for the NEXT divergence instead of
  holding this one. Operator decisions: §8.

---

## 1. D4 — the pre-committed Farmer decision (the mechanical item)

The 21-Jul review fixed thresholds BEFORE the number was read. Honouring that:

**The number: live round-trip slip = 0.38 bps** (`impl-shortfall.order_slip.live`,
7-day window: 50 orders, 41 with measured slip, fill source overwhelmingly
`trades(tx)` — the tx-hash tier; shadow model reads 0.56bps, so live executes
tighter than its model, again). Precondition audit: ≥~20 measured exit fills — met
in substance (41 measured fills; the pace forecast said ~30 by today). Build
convergence — NOT met (`arm-drift`: live `a5336fda3e84` vs shadow `9e4982f47f62`),
but that precondition guards the paired live-vs-shadow GAP read; the slip number is
computed from the live bot's own fills only and is unaffected.

**Band: `<6bps` — decisively.** The pre-committed action for this band was "proceed
with the queued STOP 0.10→0.03 via the doctrine path." **That action is VOID and
this review formally closes it** ([[withdrawing-a-verdict-is-a-sweep]]):

- The band's basis — "+6.18bps/trade gross, 1,911 replay trades, TP 0.04/STOP 0.03"
  — was **withdrawn 22-Jul** as a harness artifact: `backtest_funding_lighter.py`
  never cleared `hot` on close while production pops `hot_since` every close, so
  32–44% of those trades were instant re-entries the real bot refuses. Corrected:
  **STOP 0.03 is −$11.57, both halves negative.** Tightening the stop is not a
  supported fix.
- The superseding evidence (23-Jul, corrected harness, measured cost): the live
  config (gate 0.05, stop 0.10) is **+$33.47/180d, both halves positive at 0.5bps**,
  and stays both-halves-positive out to ~2bps. Widening the gate up loses at every
  slip level. `FUNDING_GATE_LIGHTER_2026-07-23.md`.

**Verdict: keep the gate and the stop exactly as configured.** The one thing that
kills the arm is slip drifting past ~2bps — the fill-telemetry organ watches that
continuously (current 0.38bps has ~5× headroom). Residue check done:
`FUNDING_HARD_STOP` is **confirmed NOT set** on the shadow service (the 17-Jul env
set on the withdrawn number is gone; the judge's arm is clean of it).

*Config note, same evening:* after this verdict was drafted, the operator took
the **vol-character filter live on both Farmer arms** ((dq)–(ds): calm-half rule,
+$2.44→+$44.52 @0.5bps on the corrected harness, maxDD −54→−18; judge's shadow
lap deliberately skipped on operator authority). That is a separate, additive
change with its residual risks recorded in (ds) — it does not touch the
gate/stop verdict above, and the D4 pre-commitment closure stands.

Radar's independent read agrees with patience over action: live arm `plausible`
(n=60, needs ~35 more closes ≈ 9.4 days for a verdict), shadow arm `real_edge` —
the fleet's only one — with a **"fading" caveat** (effect shrinking on trajectory).
All-time live: n=60, +$8.08, avg +$0.135/t, **t=1.65** — the standing verdict
holds: positive, unproven, keep feeding it volume.

**The (do) open risk RESOLVED mid-review, by the concurrent session's (dp):** the
slope-gate fail-open (~11 restarts/day × ~1h) was suspected unmeasured loss;
the Lighter backtest refuted the premise — the slope gate is HL-validated but
**Lighter-negative** (live gate 0.05: durable-history −$14.90 vs gate-off
+$34.07 @5bps; the restart fail-open has been *accidentally* giving money
back). No bot edit; Phase 2's durable-history plan is dead. The constructive
residue: **a slope-gate-off experiment is the natural next judge candidate**
after tp-0.06 (needs an `xp.funding.*` slope lever registered first — the
doctrine path, not an env flip; see §8).

---

## 2. Item-18 step 2 — the oracle's self-grades (review-gated: do we wire the per-asset gate?)

The four evidence pipelines started 22-Jul all accrued as designed. Reading them:

**Oracle self-grades** (`regime-oracle.grades`, per-asset d1/d3, signed into the call):

| sym | d1 n | d1 hit | d1 avg_pp | d3 n | d3 hit | d3 avg_pp |
|-----|-----|--------|-----------|-----|--------|-----------|
| ADA | 7 | 0.429 | +1.24 | 5 | 1.00 | +3.78 |
| DOT | 7 | 0.571 | +1.28 | 5 | 0.80 | +2.62 |
| XRP | 6 | 0.500 | −0.01 | 5 | 0.80 | +2.13 |
| TAO | 7 | 0.571 | +0.54 | 5 | 0.80 | +1.54 |
| BTC | 4 | 0.250 | −0.36 | 2 | 1.00 | +0.42 |
| XAU | 7 | 0.286 | −0.23 | 5 | 0.40 | −0.03 |
| XAG | 7 | 0.286 | −0.55 | 5 | 0.40 | −0.56 |
| ZEC | 7 | **0.143** | **−1.82** | 5 | 0.20 | −4.59 |

(20 pairs published; 16-symbol crypto universe complete, coverage.missing empty.)

**Decision: DO NOT wire the gate yet — the accrual is working, the n is not there.**
d1 hit rates sit at or below coin-flip in aggregate; d3 looks genuinely promising on
the liquid alts (DOT/XRP/TAO/ADA 0.8–1.0 hit at n=5) but n≤5 is exactly the
"still thin; judge n honestly" the 22-Jul memory pre-committed us to. Two symbols
are *anti*-predictive (ZEC d1 0.143/−1.82pp; metals negative both horizons) — which
is itself an argument FOR eventually gating per-asset (a global gate would launder
ZEC's wrongness into every symbol) and AGAINST wiring now (a gate consuming today's
ZEC call would be worse than no gate). **Re-read at each weekly review; the
wiring decision waits for n≥20/sym d1 (≈mid-August at ~1 call/day/sym).**
Steps 2–3 of the item-18 build order remain review-gated; nothing consumes
`grades` today.

Note: the TAKER path did not wait — (dd) built `up_read` (its own candle-EMA
per-asset up-regime read, ~100% coverage) precisely because the oracle stamps only
~8% of breakout symbols. That is the build order honoured, not bypassed: oracle
scope for the STRATEGIES' gate, a local read for the taker's bull arm.

**Non-crypto coverage** (item-18 prerequisite): the oracle now publishes per-asset
non-crypto calls — 3 short (XAG, XAU, NVDA/TSLA class), 6 missing on
`short-history` (SPY/QQQ 187<203 bars, IWM 147, WTI 160, XCU 169, MSTR 202).
Self-heals as Lighter's tape accrues — SPY crosses the 203-bar floor in ~16 days.
No action; the "never BTC's EMA for SPY" rule stands.

**Ticket regime stamps:** 3/16 current tickets stamped (dip 3/6; breakout,
momentum, divergence 0) — sparse by construction (the oracle grades 20 syms).
Regime-conditioned taker rules remain un-replayable for weeks. Keep accruing.

**Brain episode basis (`n_ep`):** live and sane — the fleet's ONE active mult
(pm-abbott `short-burst` 0.75×, n=44, streak 8) carries n_ep=37 vs n=44; no
basis-flip anomalies. The expand side has promoted nothing (nothing clears the
mirror bars) — with the brakes validated (cq), that silence is evidence of
discipline, not absence of function.

**Incubator prospect register:** populated (64 prospects + 8 funding_prospects)
— but it surfaced a real problem, §3.

---

## 3. The experiment pipeline — one contamination, one stale queue, one dormant promoter

*(verdicts verified by parallel adversarial investigation this session)*

**3a. The running 0.075 candidate is a 3-variable A/B — and the guard that should
have held it was dark from birth. FIXED this session.** The judge has been
evaluating `enter-gate-0.30@enter_apr=0.075` on the shadow twin since 21-Jul
03:56Z (shadow 24/30 closes, live 26; shadow leads +0.479 vs +0.358 %/t — under
the +0.5pp margin). Since ~25-Jul the SAME shadow arm also runs the operator's
growth levers (`SCAN_EXPLORE_K=2`, `FUNDING_CONVICTION=scaled`) — so shadow now
differs from live by gate AND explore AND conviction, with 9–11 of the 26
in-window closes post-dating the flip. Adversarially verified findings:

- The receipt gate is **proof-of-application only** (`ran_candidate` subset-
  matches the candidate's levers; it never excludes closes carrying extra
  levers) — and today the confound is invisible in receipts anyway, because the
  running shadow build predates the lever-stamping commits.
- **The arm-drift HOLD structurally could not fire**: `paired_eval`'s drift
  check reads builds off `paper_trades` rows, but `publish_paper_trade` never
  stamped `extra.build` — **0 of 143 all-time Farmer ledger rows carry a
  build** — so `arm_drift` fail-safed to None on every eval while
  impl-shortfall (reading `bot_pnl`) simultaneously reported the arms on
  different code. A dead sensor scoring a hit, on the fleet's only path to
  `live.funding.*`.
- MIN_DAYS=7 already elapsed: the shadow floor (24/30) and the sub-margin gap
  (0.121pp < 0.5pp) were literally the ONLY gates left before `run_once` would
  assert `live.funding.enter_apr=0.075` from the contaminated comparison —
  misattributing whatever explore/conviction contributed.

**Shipped this session (restrict-only, mutation-tested):** `publish_paper_trade`
now stamps `extra.build` on every close row (the sensor's feed, forward-only),
and the judge's drift read gained a HOLD-ONLY fallback to the arms' current
`bot_pnl` builds while ledger rows are unstamped (row verdict stays senior once
both arms stamp; a dark fetch claims nothing).

**Overtaken mid-review, in the right direction:** the (ds) marker deploy
converged both Farmer builds (~18:50 AEST) BEFORE these fixes even reach the
judge's container — so the fallback will correctly stay quiet (current builds
match) rather than holding this candidate. What the fixes buy from here: the
NEXT build divergence gets a working HOLD instead of a dark sensor, and every
new close row is self-evidently attributable to its build. **The attribution
problem on the 0.075 candidate itself remains open** — its window still mixes
pre/post-flip closes and the shadow still runs explore+conviction the live arm
doesn't — see D3: the honest resolutions are an operator release (spend the
slot on the growth-lever pair the confound actually belongs to) or accepting
the joint-config read with eyes open. The post-deploy receipts (now stamping
`explore_k`/`conviction_hi`) at least make the mix auditable from here on.

**3b. The judge was consuming an 11-day-stale queue with tape-refuted candidates
in it. FIXED this session.** `xp-queue` (updated 17-Jul, `ttl_sec` 3h — ~90×
past its own TTL) still lists `xp-enter_apr-0.3/-0.5` and the withdrawn
`xp-max_hold_h-48/-96`, and `candidate_pool` consumed it with **no freshness
check** — a bus-contract violation the judge itself honors three functions away
(`prop_fade` does the payload-self-TTL read). Measured consequence had it run:
the enter_apr pair clamps to 0.075 at the registry (never literally 0.3/0.5)
but raw-signature dedup happens PRE-clamp, so each would have burned a ≥7-day
serial slot re-running the identical 0.075 experiment, plus two slots on the
refuted-inert hold knob — **~4 wasted slots ≈ a month** on the fleet's only
path to `live.funding.*`. The static CANDIDATES list was correctly swept at the
21-Jul review; the side-channel queue was not — [[withdrawing-a-verdict-is-a-
sweep]] applies to QUEUES, not just docs. Shipped: `candidate_pool` now honors
the queue's own `updated`+`ttl_sec`, fail-closed on a missing stamp
(restrict-only: a stale queue contributes zero candidates; statics untouched;
mutation-tested both ways). The stale row never refreshes (the incubator only
rewrites on NEW proposals and all 8 names sit in its lifetime memory), so the
refuted entries retire permanently. **Publisher-side residual flagged:** an
incubator that stamps `ttl_sec=10800` but only republishes on new proposals
will now have legitimate future proposals expire unseen if the judge is
mid-candidate — it should republish its still-endorsed queue each cycle
(heartbeat semantics). Left to the incubator's next session; consumer-side
fail-closed is correct regardless.

**3c. The growth-lever fast-bar promoter is committed and confirmed dormant.**
53c7e8c adds `paired_eval(both_halves=False)` (the operator's 25-Jul ~2–3d bar
for the explore/conviction pair: positive + beats-live + receipts, no per-half
gate; fade-revert is the backstop) and `growth_promoter()` — fail-closed on
arm-drift and missing receipts, judge stays sole writer of `live.funding.*`.
Verified: its only callers are its own selftest; `run_once` never references
it. The full arming chain (all still ahead): run_once wiring + state
persistence → a SHADOW Farmer redeploy so close receipts actually stamp
`explore_k`/`conviction_hi` (today 0/26 do — without them `growth_promoter`
fail-closes forever) → a LIVE Farmer redeploy that consumes
`live.funding.explore_k/conviction_hi` (the live build predates the lever
consume) → a freqtrade-bots deploy of the wired judge. Safe-by-construction at
every step; nothing to undo.

**3d. Explore is ON but has opened ZERO trades in ~3 days — two stacked causes,
adversarially verified.** (1) **Zero explore entries ever opened** (`explore_seen`
is empty; all 9 scanned opens since 24-Jul stamp `src='exploit'`, all on
BTC/ETH/SOL/HYPE). Most likely mechanism: explore samples only the tail BELOW
the top-15 deep-scan cut, but the prelim gates (|apr| ≥ the 7.5% xp-levered
gate + $10M turnover + 4h persistence) rarely leave more than 15 coins on
Lighter — **the explore tail is usually empty by construction**; survivors then
face the same Stage-B/C vetoes and entry-loop gates. Container logs would split
those sub-causes. Design question for the growth-lever session: explore that
samples only below the exploit cut can't explore when the cut swallows the
whole qualifying pool. (2) **`src=explore` never lands on the paper_trades
close row on ANY build including HEAD** — it lives on position meta and the
venue_orders OPEN leg only. The design intent "stamped on meta + close for
brain/radar/judge grading of the explore slice" is half-built: even when
explore trades DO close, the graded ledger can't identify them. Flagged to the
growth-lever session (it owns the receipt pipeline; same file, same seam as
5bef0f0). Not fixed here — that file was the concurrent session's active WIP.

**3e. Arm drift, precisely dated — and RESOLVED mid-review.** At review time the
live Farmer ran the build of `ab97ddf` (cq refactor, 24-Jul 00:16 AEST) —
predating the (ct) phantom-close fix, the (cr/cs) brakes, and the growth-lever
consume (i.e. the live arm could still book phantom closes into the judge's own
evidence); the shadow ran exactly `23b321d` (explore engine, no lever-consume,
no receipts). The recommended fix was one deliberate deploy of both arms —
**and the (ds) vol-filter go-live delivered exactly that at ~18:50 AEST: both
arms now run `f7044072157f`** (verified in `bot_pnl` extra.build, both rows).
Live now carries the phantom-close fix + brakes + lever consume; shadow now
stamps `explore_k`/`conviction_hi` receipts. What remains from this item: the
first post-deploy closes should be spot-checked for the receipt keys (and,
once this review's ledger stamp deploys with the arms' NEXT redeploy, for
`extra.build` on rows).

---

## 4. The live pair, week 2

**Funding Farmer (live, `perps-funding-lighter-lighter`)** — equity $100.67
(capital-adjusted; +$6.99 P&L headline, +$8.08 ledger all-time), n=60 39W/21L.
This week: **+$2.06 on 26 closes** (13W), all short-side harvesting (16
`short_decay` +$1.93, 3 `short_take_profit` +$2.46, one −$2.00 `short_stop`, one
−$0.55 `short_max_hold`). Holding SOL long at review time. Slip 0.38bps. §1's
verdict: unchanged config, feed it volume, radar verdict in ~9.4 days.

**Ticket Taker (live, `lighter-ticket-taker-lighter`)** — equity $65.95, all-time
−$0.77 ledger on 24 closes (10W/14L). This week: **−$1.26 on 19 closes** — but the
week splits cleanly at the operator's 24-Jul bull-mode flip (short-divergence-
crypto only, 4 slots, $40 cap, verified in the heartbeat: `bull=true, max_open=4,
cap_usd=40`): since the flip, **+$0.43 on 10 closes (5W/5L)** — tp's (+0.39..0.50)
now outnumber sl's. n=10 is nothing; the arm was flagged unvalidated when flipped
and remains so. The 20bps spread gate era continues (taker live slip 7.76bps vs
44.8bps on the ungated shadow — the gate is visibly doing its job on execution).
Radar: `noise`, correctly. Keep, small, let n accrue.

**The shared caution:** both live books remain far under any go-live scale bar;
the DD governor protects paper, not this ~$167. SafetyRails caps and the daily-loss
halt (now durable through restarts) are the real rails.

---

## 5. Shadow fleet — the week in one table, and the radar's knife

7-day closed P&L (paper_trades, 21→28 Jul):

| Book | 7d | n | Radar class |
|---|---|---|---|
| 🌾 perps-funding-carry-lshadow | **+15.64** | 29 | **artifact** (concentration) |
| ⚖️ perps-funding-spread-lshadow | +4.79 | 15 | noise |
| 💸 perps-funding-lighter-lshadow | +4.03 | 25 | **real_edge** (fading caveat) |
| 🔮 freqtrade-georgia-lshadow | +2.75 | 25 | noise |
| spot intraday-15m | +2.53 | 22 | noise |
| 🏛️ pm-albanese | +2.15 | 10 | starved |
| 🏛️ pm-turnbull | +1.63 | 13 | starved |
| 🎫 taker-lshadow | +1.55 | 84 | noise |
| 🏛️ pm-rudd | +1.44 | 77 | noise |
| … | | | |
| 🏛️ pm-abbott | −2.64 | 68 | weak (brain reduced short-burst 0.75×) |
| 🏛️ pm-gillard | **−4.18** | 158 | **losing** |

- **The Yield Harvester's +$58.62 all-time is an artifact of three trades:** SOXL
  +12.71, SNDK +10.31, ARB +9.67 — single closes each, $32.69 of the total. The
  radar's median/jackknife (built to catch exactly this) classes it `artifact`
  while the evidence board's simpler expectancy screen still lists it as a
  promotion-watch. **The radar is senior here by construction** — do not promote
  the carry book on its headline; the median trade tells the truth.
- **Gillard** is the fleet's confirmed `losing` book (−$4.46 all-time, n=157,
  ~22 closes/day of churn). This week's damage was LONGS (−$3.80 on 71) with
  shorts ~flat. The standing diagnosis holds: regime-bound, not knob-broken —
  its fix is the item-18 per-asset gate, which is review-gated (§2). The right
  move remains patience, not tuning; its churn is at least cheap shadow evidence.
- **Bull engine (the week's big shadow build):** first-ever `breakoutup` closes
  landed — 6 all-time, net **−$3.66** (2W/4L: XMR +0.84, VVV +0.70; SHIB/PEPE/BTC
  ≈−1.07 each, ENA −2.01), one more OPEN (ETH) at review time. n=6 is far below
  every floor (the (dj) analysis wants ≥12/tercile; Increment B's self-veto arms
  at n≥30 brain-graded closes and cannot bite yet). Exits verified per design:
  the trend exit governs (trail 6% off peak, wide −7% SL, no TP cap; the
  tuner's `taker.sl/tp` reach only divergence's fixed bracket). **But the
  measurement pipeline was broken, not slow:** the (di) `brk_quality`/
  `up_strength` capture stopped at position meta — 0 of the 6 close rows carry
  the features (the currently-open ETH position's meta has them, proving entry
  capture works), so `analyze_breakout_quality.py`'s `extra ? 'brk_quality'`
  filter would have matched zero rows FOREVER, no matter how long we collected.
  **Fixed this session** (`_close_extra` merges the entry evidence into the
  close row; setdefault-shaped so the bars stamp can't be clobbered;
  mutation-tested at both selftest entry points). Forward-only — the first 6
  closes' features are unrecoverable from the ledger. Verdict on −$3.66/6:
  keep collecting; nothing actionable at this n.
- Scout tuner enacted a full TP/SL/hold re-sweep on the shadow taker
  (`tp 0.06 / sl −0.04 / hold 72h`, +$28.13 on tape, both halves) plus the
  sentinel's risk-off restricts (`momo_chg 6.0`, `brk_range 0.97`); it REJECTED
  the sentinel's max-hold restrict ("worse on a half") — the replay gate
  discriminating within a single proposal batch, as designed.
- **One sign disagreement worth an eyebrow:** the board banners divergence
  "POSITIVE at the ruling floor" on the raw read (+0.01%/4h), while the
  episode-deduped read is −0.075%/4h. Episodes are the honest denominator
  ([[episodes-not-trades-for-mechanism-claims]]); treat the banner as unproven.

---

## 6. Organ health — clean, and one organ ate its own dog food

- **Watchdog:** 0 problems, 0 warnings, 23/23 fresh. **Immune:** zero sick, zero
  quarantined. **Respiration:** SpO2 1.00. **Regen:** idle (nothing to repair).
- **Proprioception:** 120 episodes, 17 graded — 3 helping (`scout.dip_range_max`,
  `scout.brk_range_min`, `scout.momo_chg_min`), **0 hurting**. Both consumption
  directions live; nothing being refused, nothing earning the clip top-step.
- **Event sentinel — the standout:** its self-grading measured the historical
  playbook at **24% hit over n=178 anticipations**, and it responded by
  RESTRICTING its own detection bars (`min_sources→3`, `severity_bar→0.55`,
  reason: "playbook measured inaccurate"). An organ discovering it is a poor
  forecaster and volunteering to speak less is the autonomy stack behaving
  exactly as specified (restrict-only, evidence-first). Separately it holds a
  full risk-off crouch: market bias −1.0, every sector negative (defi/meme −1.0,
  majors −0.87, equities −0.79) on ai_boom/exchange_incident/geopolitical_shock/
  regulation_crackdown events — its taker restricts are enacted via the tuner's
  replay gate and expire on TTL.
- **Parliament:** healthy (beats flowing, nothing stalled); its books span
  −4.25..+3.75 with gillard/abbott the graded problems (§5).
- **Venue stress:** median 8.3bps, p90 16.7, max 81 (n=107 books) — the taker's
  15bps stress veto is OFF at median but the p90 tail is real; no action.

---

## 7. Process & repo notes

- **(dn) sat unpushed for 3 days.** The live-Farmer deploy-marker work (committed
  25-Jul 00:32 AEST) existed only on this Mac until the concurrent session pushed
  it mid-review today. A commit that exists nowhere but one laptop is one disk
  failure from not existing — and this one carried the CI marker-guard for
  real-money deploys. Suggested habit: end any session that commits with a push,
  or say in the commit why not ([[git-discipline-in-a-shared-tree]]).
- **Concurrent-session coordination MOSTLY worked — with one sweep, survived.**
  This review and the growth-lever session interleaved on the same tree; their
  (dp)–(ds) landed mid-review and the affected sections were updated rather
  than shipping stale verdicts. But their PR flow (a tree reset while preparing
  #95/#96) **reverted this session's three uncommitted fix files** — the exact
  [[git-discipline-in-a-shared-tree]] hazard, this time inbound. The work
  survived only because full-file backups had been taken for the mutation runs;
  restored, all suites re-verified green, base files confirmed byte-identical
  to the edit base. Standing lesson sharpened: in this tree, COMMIT within
  minutes of green, and take a backup before any long gap — an uncommitted
  file is one concurrent `git reset` from gone.
- **Shipped by this review session** (the 21-Jul "paper-lane changes sanctioned
  by the review" class; every fix restrict- or observable-only):
  1. `experiment_judge.py` — `candidate_pool` honors `xp-queue`'s own
     `updated`+`ttl_sec`, fail-closed (§3b);
  2. `experiment_judge.py` — `_arm_drift_snapshot`: hold-only bot_pnl fallback
     while ledger rows are unstamped; row verdict senior once both arms stamp
     (§3a);
  3. `bot_pnl_store.py` — `publish_paper_trade` stamps `extra.build` on every
     close row (the drift sensor's feed, forward-only) (§3a);
  4. `lighter_ticket_taker.py` — `_close_extra` carries the (di) entry evidence
     onto the close row (§5).
  All mutation-verified (including a caught near-miss: the first build-stamp
  source-pin matched its own comment — the mutation run exposed it and the pin
  now matches the exact call). Judge selftest, both taker entry points,
  bot_pnl_store, replay, born-dark, venue-purity, deploy-coverage: green.
- **Verification method note:** the five load-bearing questions (§3a–e, §5)
  were each investigated by an independent read-only agent with DB access, and
  the two consequential verdicts adversarially re-verified before any fix was
  written; file:line citations in the workflow transcript.
- **Stale advisory docs swept this review:** the [[farmer-breadth-conviction-
  levers]] memory's "stamped src=explore on meta + close" claim corrected (close
  half was never built, §3d); the 22-Jul stop-verdict memory's outstanding
  `FUNDING_HARD_STOP` check marked resolved-clean (§1).

---

## 8. Operator decision menu

- **D1 — Farmer config: no action.** The pre-committed D4 resolves to "keep
  as-is"; the STOP-tune path is closed on withdrawn evidence (§1).
- **D2 — ✅ DONE MID-REVIEW.** The recommended both-arms Farmer redeploy
  happened via the (ds) vol-filter go-live (~18:50 AEST): builds converged at
  `f7044072157f`, live gained the phantom-close fix + brakes + lever consume,
  shadow now stamps growth-lever receipts (§3e). Residual: spot-check the
  first post-deploy closes for the receipt keys; the review's new ledger
  build-stamp rides the arms' NEXT redeploy.
- **D3 — the 0.075 candidate's attribution (now the operator's genuine
  choice).** With builds converged, no guard holds it: the window mixes
  pre/post-flip closes and the shadow runs explore+conviction the live arm
  doesn't, so a promotion would credit `enter_apr=0.075` with whatever the
  growth levers contributed. Options: (a) release it and give the slot to the
  growth-lever pair (the confound's rightful owner — the fast-bar promoter
  exists for exactly this); (b) let it run, reading any promotion as "the
  shadow CONFIG beat live", not "the gate did" — defensible, since the fade
  backstops don't care why, but it writes only the gate to live. Lean: (a),
  because the (cu) tape already leans against 0.075 on its own merits.
- **D4 — item-18 step 2:** formally deferred — re-read weekly, wire only at
  n≥20/sym d1 (≈mid-August). No operator action; nothing consumes the grades
  today.
- **D5 — carry book:** no promotion consideration despite the +$58 headline
  (radar `artifact` — three single closes are $32.69 of it, §5). Listed so the
  headline never argues by itself.
- **D6 — taker live:** continue the short-divergence-crypto ×4 arm to ~n=30
  closes before any read; it was flagged unvalidated at flip and n=10 changes
  nothing.
- **D7 — new growth candidate worth queueing (from (dp)):** a slope-gate-off
  experiment on the Farmer — the gate is HL-validated, Lighter-negative
  (gate-off +$34.07 vs durable −$14.90 at the live gate). Doctrine path:
  register an `xp.funding.*` slope lever → shadow candidate → the judge's
  paired bar. Build work, not an env flip; flag to the growth-lever session.

*Next review: Monday 2026-08-04 (AEST). Accruals to read then: oracle grades at
~n=20 d1 per symbol (§2); breakoutup approaching the ≥12 analysis floor WITH
features on the rows (§5); the Farmer radar verdict (~9.4d) landing; the drift
HOLD released and the 0.075 window rerunning clean (D2/D3); explore's first
opens or the tail-starvation diagnosis confirmed from container logs (§3d);
the incubator queue-heartbeat residual (§3b).*
