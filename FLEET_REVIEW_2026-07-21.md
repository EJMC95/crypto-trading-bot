# Fleet Review — 2026-07-21

Conducted 21-Jul, data pulled 08:45–09:15 UTC (18:45–19:15 AEST, Monday
evening). Sources: the no-auth dashboard feeds (`/pnl.json`, `/bus.json`
+ 168h history, `/vitals.json`, `/trades.json` both sources, `/periods.json`,
`/alerts.json`, `/watchdog.json`) and the repo at `e13ac86`. This session has
no DATABASE_URL and no dashboard login, so anything that lives only in
bot_state (fleet-clock transitions, xp-judge full state, impl-shortfall
`order_slip`, evidence-board items) was graded from `/vitals.json` one-liners
plus code inspection — each such residual is named in §R at the end.
Agenda: `FLEET_REVIEW_AGENDA_2026-07-21.md` items 11–19. (Items 1–10 predate
the file in this history and CLAUDE.md's "§8 freeze exceptions" pointer no
longer resolves — recorded as doc-rot in §N6.)

---

## 0. TL;DR

**Fleet health: the best it has ever been.** 17/17 rows fresh, 0 stale;
immune 0 sick / 0 quarantined; respiration SpO2 100%; brain on v3 with EB
priors; every organ FRESH at read time. The 18-Jul pytest suite + CI (148
tests) and the born-dark/venue-purity guards are in CI and green.

**Three headline findings this review adds:**

1. **N1 — the dashboard's live P&L is deposit-contaminated (~$64.8 of the
   +$68.46 is the operator's own money).** The 18-Jul deposits that caused
   the (ao) equity=None incident were healed for *equity continuity* but
   nothing bumps the persisted `initial_equity` baseline, so both live rows
   print the deposit as profit. True live trading P&L ≈ **+$3.7**, not
   +$68.46. Reporting bug, not a trading bug — but it is the fleet's
   headline number and it is wrong. Fix shape in §N1.
2. **N2 — the experiment judge's running candidate silently inverted.** The
   arm still named `enter-gate-0.30` (a gate *widening*) is actually running
   `xp.funding.enter_apr = 0.075` — the old 0.30 write clamped by the
   re-denominated registry bound (hi = 0.075). The experiment became a gate
   *tightening* (0.075 TRUE vs live 0.05) without anyone deciding that.
   Directionally it is the more interesting experiment (the Lighter backtest
   says higher gates lose less), but its name lies and its promotion target
   must be re-specified before the judge can act on it.
3. **Proprioception's first week produced almost no evidence — by
   starvation, not failure.** 16 of 17 taker episodes ended `too-few-trades`
   (2–4h windows catch 0–3 closes), every verdict is neutral at n=1, no
   hurting/helping ever fired, and zero live-lane episodes exist because no
   live lever was enacted all week. The organ's plumbing is correct; its
   episode windows are shorter than its subject's trade cadence. Fix shape
   in item 12.

**The big real-money decision (item 17) is NOT closed this week** — the
fill telemetry shipped 17-Jul has 4 days of closes and the impl-shortfall
organ is withholding its live-vs-shadow verdict (`arm-drift`), so the
dominant unmeasured term (real round-trip cost) is still unmeasured from
this seat. Recommendation stands: measure ~1 more week, do not re-tune,
then decide park / fix-execution / re-justify. The live record since the
basis fix (+$0.71 realized over 4 days, 10 of 12 closes ending on signal
evaporation) continues to match the backtest's mechanism.

---

## 1. Scoreboard (deposit-corrected)

| Book | Equity | Printed P&L | Honest P&L | Closed | Note |
|---|---|---|---|---|---|
| 💸 Funding Farmer LIVE | $96.95 | +$35.82 | **≈ +$3.3** | 34 (26W/8L) | +$32.55 deposit 18-Jul 02:33Z in the print |
| 🎫 Ticket Taker LIVE | $67.29 | +$32.64 | **≈ +$0.4** | 5 (3W/2L) | +$32.22 deposit 18-Jul 07:37Z in the print |
| Funding Farmer -lshadow | $1,009.62 | +$9.62 | +$9.62 | 58 | experiment arm (see N2) |
| Ticket Taker -lshadow | $1,005.53 | +$5.53 | +$5.53 | 48 | all-lens shadow book |
| 🌾 Yield Harvester -lshadow | $1,061.89 | +$46.06 | +$46.06 | 38 | fleet's best book; post-basis-fix epoch only partially (scar noted 17-Jul (w)) |
| family 4 + spot 3 + others | ~$1,000 ea | −$4.3 … +$11.3 | same | — | all fresh, all Lighter |

Watchdog: 1 warning — 22 directional positions vs the 20 budget (§N3).
The paper flows are healthy: 47 paper closes in 24h, 5,312 equity samples.

---

## 2. Agenda items, graded

### Item 11 — fleet clock: does it get a consumer at all? → **NO. Rest as advisory.**

The agenda asked for a re-run of `clock_consumer_premise_check.py` before
deciding. That script needs the DB, but its scanner half measures the
`lighter-market` tape — which `/bus.json?hours=168` serves. **Re-ran the
premise on 168h / 2,009 samples / 10 NYSE bell windows (5 sessions, vs 3 on
17-Jul):**

| metric | in bell ±15m | outside | t | verdict |
|---|---|---|---|---|
| stress.med | 5.94 | 5.54 | +3.83 | 0.4bps bump — see below |
| stress.p90 | 15.81 | 15.83 | −0.07 | flat |
| stress.max | 62.93 | 58.95 | +0.95 | flat |
| oi_moves | 0.07 | 0.03 | +1.00 | flat |
| tickets | 15.95 | 15.83 | +0.26 | flat |

n_in=60, n_out=1,949. The med's t=+3.83 is the one change from 17-Jul's
flat read — reported honestly, then discounted for what it is: adjacent
5-min samples of a slow-moving median are serially correlated (the t is
inflated), and the effect size is **0.4bps against a 150bps entry gate**.
Nothing a scanner boost could harvest lives in a 7% relative bump of a
6bps median; the tail metrics a dislocation trader actually eats (p90,
max) are flat to negative in-window.

**Heavy-jobs premise re-run, same tape:** scout cadence over 2,008
intervals — p50 **300.6s**, p90 **300.7s**, p99 307.0s against a 300s
nominal. One 20-min gap (18-Jul 10:58Z — the deploy window). The container
is still idle from the scout's vantage; `heavy_ok` still protects nothing.

**Clock precision:** could not re-grade the transitions log from this seat
(DB-gated; §R). The 17-Jul pre-grade (both 16-Jul transitions within one
5-min tick, DST-honest) stands unrefuted, and the live payload was sane at
read time ("NYSE closed · us-session open in 4.2h" at 08:48Z = correct).

**DECIDED (recommendation): wire NOTHING.** An advisory organ nobody obeys
is a valid resting state; the fleet's one honest clock consumer remains a
human reading the dashboard. The only scoped survivor — the equity-perp
subset with per-name bells (KRX/HKEX for the Korean names) — stays on
record as the next test IF anyone ever wants this alive, and it must
arrive as a verified claim about code that exists, per the 17-Jul lesson.

### Item 12 — proprioception 🦾: grade the grader's first week → **alive, correct, starved**

The real week, from the full episode ledger (23 episodes, 16→21 Jul):

- **Statuses: 2 graded / 5 recorded (xp) / 16 too-few-trades (taker).**
  The two graded episodes: the 16-Jul gapscout pair (found_activity=True,
  → neutral) and one 3h taker joint stance (37 snaps, Σ$0.00 → neutral).
- **All 4 verdicts are `neutral` at n=1.** No hurting verdict ever fired
  (so the tuner's hurting-skip, the board's release, the live hurting-revert
  hook and IMB-08's probation cycle are all UNTESTED — not failed). No
  helping verdict ever fired (so the expand side never unlocked, and the
  live clip ladder's top step stayed correctly fail-closed all week).
- **Zero live-lane episodes** — `fleet-tuning` shows 0 lighter-live levers
  enacted all week (the board never moved clip off 1.0; the judge promoted
  nothing). Live-lane learning is untested for lack of a subject, which is
  the system behaving lawfully.
- **Episode-ledger sanity: PASS.** Windows are contiguous, same-stance,
  releases align with lever expiry; no phantom opens in the 495 history
  rows.
- **Counterfactual honesty: PASS on the one graded taker episode**
  (stance_net = default_net = 0.0 over 37 snaps with no closes in-window —
  a trivially correct $0 delta).

**The calibration question the agenda asked ("are n≥2 / ±$3 right?") has
an answer, and it isn't the floors — it's the windows.** The taker closes
~1–3 trades per 2–4h episode; the per-episode close floor filters 16/17
episodes before the verdict floor ever sees them. Summing the week's
same-stance taker episodes: **10 closes across 15 episodes of the SAME
`taker.sl=-0.04/taker.tp=0.06` stance** — pooled, that clears any sane
floor and would have produced the fleet's first real verdict.

**RECOMMEND (code change, shadow-lane only, needs no operator gate):
pool contiguous same-stance episodes** (or equivalently, slice long
stances at 24h instead of on every re-assert) so episode length matches
the subject's trade cadence. Keep n≥2/±$3 unchanged. Grade the pooling's
first week at the next review.

### Item 13 — 16-Jul bug-audit deferred findings → **7 of 8 closed; one decision left**

Verified in code this session:

- **(i) zombie positions — ~~STILL OPEN~~ CORRECTION (same day, caught at
  implementation): SHIPPED 16-Jul, everywhere.** All four "port targets"
  already carry the guard under `DELIST_GIVEUP_H` naming (Harvester
  `funding_carry_bot.py:378`, family-bot orphan close `:989`, Index Rider
  `:98/:355/:448`, Snap Back `:81/:476`), the taker has its delist
  give-up, the sniper the original. This review graded the item off a
  grep for the sniper's word ("zombie") instead of the agenda's own
  STATUS UPDATE, which listed (i) as shipped in (al). Same lesson as the
  G1 correction, second occurrence: **grep the fix's NAME, not your
  name for it — and read the status update you are grading against.**
- **(ii) replay mark universe — ~~remains queued~~ CORRECTION: also
  SHIPPED 16-Jul per the same status update** (the scout records marks on
  the tape; the `lighter-market` payload carries `marks`).
- **(iii) per-bot clips** — shipped in code ✓. **(iv) census
  double-count** — shipped, then mooted by Gap Scout's retirement ✓.
  **(v) merge race** — shipped (am); no lock incidents visible in a week
  of three-author writes ✓. **(vi) retention** — shipped: 60d window,
  `prune_bot_state_history` + boot sweep in `cleanup_legacy_bots` ✓ (the
  "who prunes / what window" decision this item carried is thereby made).
  **(vii) live fill prices** — shipped (g)/(w); grading the actual
  slip needs the venue_orders read (§R). **(viii) smaller items** — all
  shipped per the 16-Jul second update ✓.

### Item 14 — EXPAND↔TIGHTEN audit residue → four calls

- **IMB-08 (verdict probation): UNTESTED** — shipped 17-Jul but no
  non-neutral verdict ever existed for it to expire. Keep as-is; grades
  itself the first time a verdict fires.
- **IMB-24 (episode-based lens floors): the data now exists — MIGRATE.**
  Four more days of v3 episode grading gives: breakout eps4h **850** /
  n_syms 113, dip **760**/110, divergence **845**/88, momentum **117**/29
  (raw:episode serial-correlation ratio ~8–11x, momentum 31x). The taker
  veto still floors on raw `n4h` (`lighter_ticket_taker.py:347`).
  **RECOMMEND: migrate taker veto + tuner floor to `eps4h ≥ 25 AND
  n_syms ≥ 10`** (replay-gated migration, as the item specifies). Every
  current lens passes; a thin new lens cannot ride serial correlation
  through the floor.
  Also from the same table, worth its own line: **divergence is now the
  only lens positive at every horizon** (eavg 1h/4h/24h = +0.051/+0.018/
  +0.152%, ehit4h Wilson **[0.509, 0.553]** — the first lens whose
  episode-graded hit rate clears coin-flip at 95%). The 17-Jul "every
  lens is negative at 4h" concern resolved itself for exactly the lens
  the live taker trades. The momentum lens remains the worst on every
  measure (eavg24h −1.47%).
- **IMB-20 (registry coverage asymmetry): SANCTION the divergence
  emission lever** — the winner lens (above) is the one without a scout
  emission lever; adding it is advisory-tickets-only, bounded, TTL'd, and
  this review's sanction is what the item said it needed.
- **G1 amendment (dd-governor ≤6h post-reset abstain returns 1.0):
  RECOMMEND blind-hold** — hold the prior <1.0 clip through the abstain
  window; shadow-clip lane only; consistent with the blind-hold pattern
  the live-lane gates already use. Note the governor spent the entire
  week at clip 1.0 / dd 0.00% (2,018/2,018 samples), so this is
  future-proofing, not a live fix.
  **CORRECTION (same day, while implementing): ALREADY SHIPPED 17-Jul**
  under delegated review authority (`fleet_risk.py:492`, verify-corrected
  scope note included) — this review graded an item a prior session had
  closed. Nothing to build; the stamp above stands as written evidence
  the reviewer should grep before recommending.
- Contested four: **IMB-16 — resolved at the publisher** (advisory mode now
  releases both actuators per the 17-Jul CLAUDE.md change) — DROP.
  **IMB-28 — restrict-only detection is the immune organ's design** — DROP.
  **IMB-29 — the born-dark detector + CI guard closed the silent-v2 half;**
  the twin-anchor half stays on the watchlist unproven. **IMB-18 — keep
  open honestly:** whether the tuner's brain-veto fails open on a stale
  brain while an expansion walk is mid-flight is a 10-line code read this
  session did not spend; it is the only contested item touching an actuator,
  so it gets the next session's first look rather than a drop.

### Item 15 — 🏆 Stock Leaders → **PARK CONFIRMED; ship the rail fix to the live pair**

The book was retired 17-Jul (e) on the drawdown arithmetic (37–44% maxDD
vs the 15% gate, zero funding modelled, no variant clears). Nothing in
this week's data reopens it; the park stands.

**The LIVE RAIL RESIDUAL is confirmed still open in current code**
(`lighter_funding_bot.py` boot path): `day_start_equity =
account_value()` at boot, restored only from the *halt* record — so a
PRE-halt restart part-way down a losing day re-bases the 10% daily-loss
rail to the depressed equity. The shadow pair carries the full fix; the
live pair (Funding Farmer + Ticket Taker, since Tide Rider's retirement)
does not. **RECOMMEND: ship the same persisted same-UTC-day baseline to
the live pair.** Small, protective, same class as the 16-Jul `last_ts`
fix — but it touches the real-money loop, so it is on the operator menu
(§4, D3) rather than done unilaterally here.

### Item 16 — the 8x funding basis → **sweep complete; nothing left to decide**

Verified in code: the only remaining `24*365` sites outside `scripts/`
are Hyperliquid-correct (`funding_carry_bot` HL arm, documented) or
basis-guarded (`market_context` — with a mutation test that fails if
anyone "simplifies" `funding_basis` away). The seventh self-modelled
accrual site (the taker's inline drag) was caught 17-Jul; the real-money
call site is pinned by tests (`H == 1095`). The scout stamps
`funding_basis` on every payload (self-describing tape ✓). The shadow
equity books' 8x over-accrual is fixed forward with the scar documented.
Closed.

### Item 17 — 💸 Funding Farmer → **measure one more week; do not re-tune; fix N1 first**

What this week added:

- **Live record since the basis fix (17→21 Jul): 12 closes, +$0.71
  realized.** 10 of 12 ended on signal evaporation (decay/flip) — the
  backtest's mechanism (63% predicted) continues to hold live (83% on
  this small window). Two TPs (+$0.83, +$0.81), one flip loss (−$1.62).
  The book remains a near-flat TP/decay process, exactly what the
  friction-bound diagnosis predicts.
- **The gate question is closed** (agenda: commit (b) withdrawn — no gate
  to tune to). The live arm trades at 0.05 TRUE; the only running
  experiment on the twin is the accidentally-inverted 0.075 arm (§N2) —
  which, once re-specified honestly, is the *right* direction per the
  breakeven arithmetic (0.122 TRUE at 72h holds).
- **The deciding number — real round-trip cost — is still unread from this
  seat.** The telemetry shipped 17-Jul and live closes have accrued, but
  `impl-shortfall` currently verdicts **`arm-drift` (gap 0.03pp)** — the
  arms hold different books, so it is correctly refusing the live-vs-shadow
  comparison. The `order_slip` block (per-fill decision-vs-fill bps from
  venue_orders) exists in its payload but is DB/auth-gated (§R).

**RECOMMEND:** (a) hold the course one more week — no gate changes, no
stop changes (`STOP 0.10→0.03` stays queued behind the slip read; the
`hard_stop` lever still does not exist in the registry, so the
doctrine-compliant path needs that registry addition first); (b) read
`order_slip.live.slip_bps` next session (or from the dashboard /learning
page); (c) decide park / post-only execution / re-justify as the TP-stop
bot it behaves as, WITH the slip number on the table. The book is $97;
the cost of one more week of measurement is trivially small against
deciding blind.

### Item 18 — single-regime doctrine → three recommendations

1. **Adopt the regime-coverage caveat**: "positive in both halves" is
   necessary but NOT sufficient for directional strategies on a
   single-regime tape; a directional validation must state which regimes
   the window contains, and a one-regime pass is a pass *in that regime
   only*. (Doctrine amendment — operator sign-off, §4 D5.)
2. **Do not stand up a new non-crypto bot.** The venue's non-crypto books
   (SPY/QQQ/IWM/WTI/NVDA…) are the regime-diverse test-bed, but both
   existing candidates already reach them: the scout reads all ~215 books
   and the Ticket Taker trades its tickets (its live closes this week
   include MSTR, TSLA, SOXL, STRC). The vacant niche (intraday range on
   non-crypto perps) stays vacant until someone owns the prerequisite.
3. **The prerequisite is the per-asset regime gate, and the brain just
   independently corroborated it**: this week's diagnosis for Georgia —
   "100% of matched losses opened during oracle risk-off" — is the same
   finding as the agenda's SPY-vs-btc_regime_up incoherence, from a
   different organ on different data. **RECOMMEND: extend `regime_oracle`
   (it already tracks 16 majors) to publish per-asset regime for the
   non-crypto reference legs, and gate any future non-crypto directional
   entry on ITS OWN asset's regime, never BTC's.** Build order: oracle
   coverage → family-bot gate consumes it → only then any universe
   widening.
   **✅ STEP 1 SHIPPED same day (operator: "do the oracle per-asset build
   next") — CHANGELOG (az):** 10 non-crypto books tracked per-asset,
   publish-only, `fleet.read` pinned crypto-only (bot_learn's risk_off
   join protected); 4/10 grade at ship, the rest graduate with the tape.
   Steps 2 (gate consumes) and 3 (universe) remain review-gated.

### Item 19 — "Filter" → **auth verified fixed; two operator actions remain**

Verified this session: the committed default credentials are **out of the
code**, `_auth_ok` **fails closed** (`if not DASH_PASS: deny everyone`),
and the live service returns **401 anonymously** on `/` while the
documented no-auth JSON feeds stay open (by design; they carry no
secrets). The (ap) fix is real and deployed.

Remaining, both operator-only (§4, D6): (1) **confirm** a strong
`DASH_PASS` is actually set on the Railway service (fail-closed means an
unset var locks the UI for everyone including you — you'd know, but the
review wants it on record); (2) the **custom domain** (one DNS record,
Railway-native) — recommended, low effort; (3) framework rewrite stays
NOT recommended, unchanged.

---

## 3. New findings (this review)

### N1 — Live P&L prints operator deposits as profit 💰 (top priority)

Measured from the 168h `fleet_equity` series: two step-jumps —
**+$32.55 at 18-Jul 02:33–02:38Z** (12:33pm AEST) and **+$32.22 at
07:37–07:42Z** (5:37pm AEST) — the same deposits that triggered the (ao)
equity=None incident. Mechanics: both live bots publish `pnl_abs = equity
− initial_equity` where `initial_equity` is the persisted first-boot
baseline; the EquityGuard's collateral-stable rebase healed *continuity*
but nothing adjusts the *baseline* for a deposit. Arithmetic closes on
both books (Farmer 96.95 − 61.13 = +35.82 printed vs ≈ +3.3 real; Taker
67.29 − 34.65 = +32.64 printed vs ≈ +0.4 real; the taker's baseline IS
the $34.67 go-live figure from CLAUDE.md).

**Fix shape (reporting-only, two-commit discipline):** when the
collateral-stable rebase fires, bump `initial_equity` by the accepted
collateral delta and stamp the event in state (a deposit is capital, not
P&L); backfill the two known 18-Jul deposits; assert non-deposit paths
bit-identical. Until it ships, read the dashboard's live P&L minus
~$64.77.

### N2 — The judge's candidate inverted under the registry clamp

`experiment_judge` still runs the pre-basis-fix candidate (name
`enter-gate-0.30`, intent: *widen* the gate, old-units 0.30 ≡ 0.0375
TRUE). The re-denominated registry (`xp.funding.enter_apr` bounds
[0.03125, **0.075**]) clamps its 0.30 write to **0.075 TRUE** — so since
17-Jul the twin has been running a *tightened* gate, 1.5× the live arm,
under a name that says the opposite. The code's CANDIDATES list was
correctly re-denominated to `enter-gate-0.0375`; the *running* state
wasn't. **RECOMMEND: re-specify the running candidate honestly as
`enter-gate-0.075` with a fresh window** (it has been value-stable since
17-Jul, so the clock can arguably stand — but the promotion mapping to
`live.funding.enter_apr` must carry 0.075, and the paired-bar stats must
not straddle 17-Jul), and drop `enter-gate-0.0375` from the queue — the
Lighter backtest already measured the 0.03–0.08 region as the worst on
the gate curve; spending a 7-day judge slot re-testing it contradicts the
evidence. The judge's own arm-skew guard ((ah)) plus impl-shortfall's
`arm-drift` verdict are both behaving correctly around this.

### N3 — The fleet lived at the long-budget ceiling ~40% of the week

Light distribution over 2,018 samples: green 835 / yellow 364 / **red
819 (40.6%)**; currently 22 gross vs the 20 budget (the watchdog
warning). Concentration: 18 longs across only 10 symbols, effective bets
**8.1** (1/HHI), pileups ETH 3 / LTC 3 / TRX 3. The veto is working as
designed (red = new-long suppression), but the fleet spent much of the
week entry-throttled by budget rather than by signal. No change
recommended this week — the exposure organ is advisory by design — but
the operator should know the budget, not the strategies, was the binding
constraint, and a per-symbol pileup cap is the natural next lever if this
persists (§4 D7).

### N4 — `funding_source: "hyperliquid"` on a Lighter-only bus

The signal bus's funding block currently comes from the fresh
`perps-funding-carry-lshadow` row but is labelled `hyperliquid` — the
consumer-side default that fires when the row's `extra.venue` stamp is
missing. Current code stamps the venue (funding_carry 17-Jul) and
`_venue_of` raises rather than defaulting — so **a running container
predates its half of the label contract** (the classic frozen-service
signature). Action: marker-grep the funding-carry and freqtrade-bots
containers ([[railway-cli-frozen-services]]) and redeploy whichever is
stale. Cosmetic on an advisory key, but it is the exact failure class the
repo already named, caught by its own tell.

### N5 — The 14–15 Jul fleet-equity sawtooth (closed, recorded)

The equity series shows a ±$965–1,000 sawtooth every 30 minutes from
14-Jul ~09:00Z to 15-Jul ~04:26Z — a cohort-flap artifact (one ~$1k row
entering/leaving the summed cohort), the same family as IMB-02. It
predates the 17-Jul IMB-02 fix and the series is clean after it — kept
here so nobody later reads that window's history as real drawdown.

### N6 — Doc rot, minor

CLAUDE.md still points freeze-window exceptions at
`FLEET_REVIEW_AGENDA_2026-07-21.md §8`, but the agenda file (in this
history) has always started at §11 — items 1–10/§8 predate the squashed
history. With this review closing the agenda, the pointer should move or
the exception log should be restated wherever the next agenda lives.

---

## 4. Operator decision menu

Recommendations above; these need Eamon's call. Everything else in this
review is either done, code-change-recommended on paper lanes (no real
money), or explicitly deferred with a date.

- **D1 (real money, reporting): fix N1** — deposit-aware baseline bump +
  backfill the two 18-Jul deposits. Until then the live P&L headline
  over-reports by ~$64.77. *Recommended: yes, this week.*
  **✅ SHIPPED same day (operator: "do D1-D3 now") — CHANGELOG (as).**
  While shipping it the D2 finding got WORSE: the judge's clamp-inverted
  candidate wasn't just mislabeled, it was DEADLOCKED — its own skew gate
  excluded every receipt-stamped close since 17-Jul (20 closes, zero
  accrued). Deploy: `railway up` Farmer + Taker + freqtrade-bots.
- **D2 (real money, judge): re-specify the running candidate per N2**
  (rename to 0.075, fix the promotion mapping, drop 0.0375 from the
  queue). *Recommended: yes.* **✅ SHIPPED same day — CHANGELOG (as).**
- **D3 (real money, rails): ship the day-start-equity persisted baseline
  to the live pair** (item 15 residual). *Recommended: yes.*
  **✅ SHIPPED same day — CHANGELOG (as)** (the Taker already carried the
  pattern; the Farmer now matches).
- **D4 (real money, farmer): one more week of slip measurement before the
  park/fix/re-justify call** (item 17). *Recommended: measure, then
  decide at the 28-Jul review.*
- **D5 (doctrine): adopt the regime-coverage caveat** (item 18.1) and the
  per-asset-regime build order (18.3). *Recommended: yes.*
- **D6 (ops, 2 min each): confirm `DASH_PASS` is set on Railway; add the
  custom domain DNS record if wanted; flip nothing else on item 19.**
  **✅ DASH_PASS DONE same day — by the operator's own hand** ("I've got the
  dash password I like set"). `dashboard-auth-rotate.yml` ships as the
  standing rotation tool (never dispatched; dispatching OVERWRITES the
  password with a random one). The domain half waits on the one fact only
  the operator holds — the hostname.
- **D7 (informational): the long-budget saturation (N3)** — no action
  recommended this week; flag if you want the pileup cap designed.
- **Paper-lane code changes sanctioned by this review** (no operator
  action needed unless vetoed): proprioception episode pooling (item 12),
  zombie-guard port to the six shadow bots (13-i, replay-gated), IMB-24
  eps4h/n_syms floor migration (replay-gated), IMB-20 divergence emission
  lever, G1 blind-hold.
  **✅ BATCH SHIPPED same day (operator: "continue with other items") —
  CHANGELOG (au):** pooling (rejoin grace, IMB-01-safe), IMB-24 migration
  (episode basis with raw fallback; measured consequence: dip flips
  allowed→vetoed on the dedup'd grade — shadow book only), IMB-20
  `scout.div_gap_pp` lever + tuner ladder. G1 was found ALREADY SHIPPED
  17-Jul (correction above).
  **✅ SECOND PASS (ax):** the zombie "port" dissolved on inspection —
  all four targets already carried the guard since 16-Jul (correction in
  item 13 above); **IMB-18 RESOLVED and shipped** (a dark brain now
  suppresses the lens-keyed taker-bar walks — the veto set is unknowable
  when dark, so a dark brain earns nothing; exit sweep and the already-
  guarded diet walk unchanged); **N4 self-healed** (`funding_source:
  lighter` on the bus after run 187's funding-carry redeploy — the stale
  container was the cause, as diagnosed).

## R. Residuals this session could not reach (no DB / no dashboard login)

- `impl-shortfall.order_slip.live.slip_bps` — the item-17 deciding number.
  Read via the /learning page or a DB query next session.
- fleet-clock transitions log for 17/18-Jul + the weekend gap (the 17-Jul
  pre-grade PASS stands unrefuted; the live payload was sane at read time).
- xp-judge full state (phase details beyond the vitals one-liner) — needed
  when executing D2.
- Evidence-board item detail (19 items / 6 proposals — one-liner only).
- Marker-grep of the funding-carry + freqtrade-bots containers (N4).
- `clock_consumer_premise_check.py` verbatim re-run (its scanner half was
  re-measured here from the bus tape instead; the Gap Scout half remains
  unanswerable — the bot is retired).

*Times for Eamon: data pulled Monday evening 18:45–19:15 AEST; the two
deposits landed 12:33pm and 5:37pm AEST Saturday 18-Jul. Sydney is on
AEST (UTC+10) — no DST in July.*
