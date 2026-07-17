## 11. Fleet clock v2: does the clock get a consumer at all? (added 16-Jul; menu struck 17-Jul)

**What shipped (16-Jul, operator: "when any market opens or closes we are
able to allocate resources"):** the circadian organ (`fleet_clock.py`) went
from zones to EVENTS — real NYSE calendar (zoneinfo DST, 2026-27 holidays,
13:00-ET early closes), `events`/`next_event` (absolute `at_utc` open/close
times for NYSE + the three crypto sessions), `event_window` (±15 min,
env-tunable), `heavy_ok` now also stands aside inside event windows, and
`fleet-clock` history is a transitions-only open/close event log. 5-min
cadence. Still ADVISORY / publish-first per doctrine — no consumer wired.

**⛔ 17-Jul: THIS ITEM'S PREMISE IS FALSE — the equities option is WITHDRAWN,
not deferred. Read this before re-litigating it.**
Attempted under delegated authority, built, adversarially verified, and then
REVERTED on the evidence. The option below said the equities books "idle
while the underlying doesn't print; a frozen index makes their marks noise."
**That describes a bot design this repo does not contain.** Verified by
inspection of the real code (and independently by 3/3 refuter lenses):
- `lighter_index_bot.want_position(symbol, closes)` and
  `lighter_momentum_bot.evaluate(closes)` are PURE functions of `closes`,
  and both `ref_closes()` fetch **Yahoo daily bars of the REAL market**
  (`query1.finance.yahoo.com`, `interval=1d`). Neither signal reads a perp
  mark. `marks.fresh_mid` appears only at fill/mark/seatbelt sites.
- So both books were ALREADY deciding on real prints. An NYSE gate adds
  **zero** signal quality — it is pure latency, and (as built) it deferred
  regime EXITS and `rotated_out` exits by up to **65h** across a weekend
  while the long keeps paying ~28% APR funding, bounded only by the
  −15%-from-entry seatbelt.
- Both books' own labs have already MEASURED that coarsening decision
  cadence HURTS them: Index Rider — "monthly-eval Faber timing REJECTED
  (DD 26-29% vs 20-22%)"; Stock Leaders — "monthly re-widens DD to 46.7%".
  A clock gate is the same family of knob, and it shipped with no backtest.
- The gate would also have corrupted the very evidence these shadow books
  exist to produce (the funding-drag study) and diverged them from their
  named IBKR/Alpaca control arms — a control arm only controls if the venue
  is the only difference.
Also killed en route (recorded so nobody rebuilds it): the first cut wired
`hyperliquid_momo_bot.py`, which is **Trail Blazer's 24/7 CRYPTO book** on
the recycled momo-bot service — not Stock Leaders (names lie; check what a
service RUNS). And `lighter_momentum_bot`'s universe holds BTC/ETH/XAU/XAG/
WTI — 5 of its 25 candidates are NOT NYSE-clocked, so a whole-rotation gate
pins 24/7 legs to the NYSE bell.
**⛔ 17-Jul (later, on review of the withdrawal itself): THE MENU IS
WITHDRAWN TOO — this item no longer offers a pick-list.** The equities gate
was refuted on TWO independent grounds and only the empirical one got
written down. The one that got dropped is the one that generalizes:
- **DOCTRINE — and it does not care which option was picked.** This organ is
  advisory/publish-first, and its own header states the contract: *"nothing
  is FORCED to obey it until a consumer earns the wiring at a review (21-Jul
  agenda item 11)."* Wiring a consumer IS the design decision this item
  exists to make. A session that takes an option off this list and builds it
  has pre-empted the review using the review's own homework as its warrant —
  which is exactly what happened on 17-Jul. That argument applies to
  scanners and heavy-jobs **verbatim**. Nothing here gets wired by a session.
- **THE MENU IS NOT EVIDENCE.** All three options were written by the same
  16-Jul session, in one breath, with the same (zero) verification. The
  operator's mandate was the ORGAN — "when any market opens or closes we are
  able to allocate resources" — not this list; *able to* is what the organ
  already delivers. One of the three was finally checked against the real
  code and turned out to be **fabricated**: it described a bot design this
  repo does not contain. The other two did not survive scrutiny — **they
  were never scrutinised.** They are survivors, not findings. Writing
  "scanners/heavy-jobs remain the honest candidates" (as this item and the
  17-Jul CHANGELOG both did) reproduced the exact unearned confidence that
  produced the fabrication, one line further down the same page. Struck.

**What the review actually decides (real reasoning, not this menu):** first,
whether the clock gets a consumer AT ALL. "We built an organ" is not a
reason to obey it; an advisory organ nobody obeys is a valid resting state,
and the fleet already has one honest use for the clock — a human reading the
dashboard. If a consumer IS wanted, its premise must arrive **stated as a
claim about code that exists**, verified by inspection before anything is
built — the check that took one `grep` on 17-Jul and would have saved the
entire build.

**Both struck options were then MEASURED (17-Jul, operator: "may as well fix
now") — and BOTH found NO SUPPORT.** They are restated below with their
numbers, not as prose to inherit. Every quantity either premise names is flat:
the bell marks no dislocation the scanner would want, and nothing in the
container contends for the heavy-job flag to protect. One re-runnable
read-only script covers both — `clock_consumer_premise_check.py`, verdict and
limitations in its header (repo convention: **don't re-test what a script
header already rejects**). Re-run it before the review; the tape is only 69h.
So the live question is genuinely "does the clock get a consumer at all", with
all three original answers now measured or refuted rather than merely struck.
*Held honestly as NO SUPPORT FOUND, not REFUTED — the tape is thin and each
check names its own blind spot. The scoped survivors are in the bullets.*
- *Scanners* (Lighter Scout / Gap Scout) — the claim was "opens/closes are
  when dislocations and vol moves happen." **MEASURED 17-Jul: NO SUPPORT
  FOUND** (`clock_consumer_premise_check.py`, verdict + limitations in its
  header; re-run it before the review). The premise is a density claim, and
  the fleet already writes the tape to test it: the Lighter Scout publishes a
  premium-stress cross-section every ~5 min and `bot_state_history` keeps 60
  days. Over 827 samples / 69h / 3 NYSE sessions, INSIDE the clock's real
  ±15min window vs outside: `stress.med` **5.62 vs 5.62** (t=+0.06),
  `stress.p90` 15.59 vs 16.28 (t=−1.91), `stress.max` 67.65 vs 74.71
  (t=−1.41), `oi_moves` 0.11 vs 0.06 (t=+0.98), tickets 17.06 vs 17.45
  (t=−0.79). **Not one metric is higher in-window**, and widening to any
  clock event (n=144) doesn't move it. Dislocation intensity at the bell is
  indistinguishable from any other moment. The premise had the burden and
  produced nothing.
  *Honest limits — this is "no support found", NOT "refuted":* only 3 NYSE
  sessions (n=36 in-window), so a real effect under ~1bps wouldn't show yet;
  it measures intensity, not the VALUE of acting in the window (a boost
  catching *better* dislocations is a different, untested hypothesis — and
  not the one the agenda offered). **The scoped next test if the review wants
  this alive:** the equity-perp SUBSET, which is un-tested and where an
  effect would actually live — `stress` is an aggregate over ~94 books and
  the scout's outliers are dominated by equity names, so a real bell effect
  could be washed out by the crypto majority. It would need the right bell
  per name (KRX/HKEX for SAMSUNGUSD/SKHYNIXUSD/ZHIPU, not NYSE).
  **Two of my own claims in this item were wrong — both caught by running the
  check instead of writing more prose, which is the whole lesson:**
  (i) *"cheaply checkable via `gapscout-census`"* — **false.** Epoch 2 has
  written **4 history rows total, spanning 12 minutes on 07-16**: two
  episodes, both CRO/USD on the same kraken→coinbaseexchange route
  (`scanner-cross-exchange-arb` has 2 paper_trades rows fleet-wide). There is
  no density to measure; **the Gap Scout half is NOT ANSWERABLE** and stays
  untested. The answer came from a different tape (`lighter-market`)
  entirely. (ii) *"both are CRYPTO scanners on 24/7 books… keyed to an EQUITY
  bell"* — **false, and it stacked the deck against an option I had already
  struck.** The Lighter Scout's ~215-book universe includes equity perps; its
  premium outliers are mostly equity names. I wrote a confident argument from
  an unverified claim about the scout's universe, inside the document warning
  against exactly that.
  **Also worth the review's attention:** a "cadence boost" for a Gap Scout
  booking 2 episodes in 2 days is aimed at the wrong bottleneck — the census
  is quiet enough that the board's growth rail is already widening its
  prefilter.
- *Heavy jobs* (incubator breeding, big sweeps) — the claim was that heavy
  jobs running inside an event window cost something. **MEASURED 17-Jul: NO
  SUPPORT FOUND** (same script). The premise has a prerequisite nobody stated,
  let alone checked: **something must actually CONTEND.** In `run_all.sh`
  every organ runs in its own `( … ) &` subshell with its own sleep loop —
  independent processes sharing container CPU, not a sequential queue — and
  the canonical heavy job (the incubator) runs hourly in that same container
  as the scout, which loops `run; sleep 300`. If a heavy job stole CPU, the
  scout's cycle would stretch. Over 831 intervals / 69h: **p50 300.6s, p90
  300.7s** against a 300s nominal (p99 344.6s, stdev 20.1s, implied scout
  runtime 0.6s). 90% of cycles land within **0.7s** of nominal — the container
  is idle from the scout's vantage — and the slowest 10% spread FLAT across
  minute-of-hour buckets (worst 10 vs 7.0 expected), so the hourly incubator
  leaves no signature. **Nothing measurably contends, so `heavy_ok` currently
  protects nothing.**
  *Honest limits:* the scout is I/O-bound (0.6s runtime, one bulk API call),
  so this is an INDIRECT probe of CPU pressure — a fair one, since a starved
  container would delay the `sleep 300` wake and p90 says it doesn't, but a
  direct Railway container CPU metric would beat it. The incubator's phase
  drifts (`run; sleep 3600`), so the minute-of-hour test is weak corroboration
  and the interval distribution is the finding. Contention could exist on a
  resource this misses (network, DB pool, RAM) — name the resource first, then
  measure that one.
  **My own claim here was also unverified until this ran:** "no resource has
  been named as scarce; the sweeps contend for CPU with loops that are not on
  a deadline" was an assertion dressed as a finding, in the same breath as the
  scanner ones. It happens to have survived measurement — which is luck, not
  method, and exactly why it got measured.

If equities are ever revisited, the only defensible claim is FILL QUALITY
(don't cross a thin after-hours equity-perp book) — a different hypothesis
on a different evidence bar, and it must clear the existing 15y harness
(`index_enhance_backtest.py`, `momentum_universe_backtest.py`) on both
halves first, scoped per-symbol so non-NYSE legs are exempt.
Also: EVBOARD_MODE=publish was checked and is currently INERT — zero coded
consumers of board proposals exist; that review item is really "design the
proposal consumer", not "flip the env".

**Original options — ALL THREE STRUCK 17-Jul. Kept verbatim as a record of
what the menu claimed, NOT as a pick-list. Nothing below is a live option:**
- ~~**Equities books** (Index Rider 📊 / Stock Leaders 🏆): idle their scan
  loop while `markets.nyse.open` is false (the underlying doesn't print;
  a frozen index makes their marks noise) and wake at `next_open_utc`.
  Cheapest win, clearly correct~~ — **premise FABRICATED, withdrawn 17-Jul.**
  ("Cheapest win, clearly correct" was the most confident line on the page
  and the only one checked against the code. It was false. Calibration note
  for everything else written in that voice, here and elsewhere.)
- ~~**Scanners** (Lighter Scout / Gap Scout): cadence boost inside
  `event_window` — opens/closes are when dislocations and vol moves
  happen.~~ — struck 17-Jul as unverified, then **MEASURED same day: NO
  SUPPORT FOUND** (dislocation intensity flat at the bell). See above.
- ~~**Heavy jobs** (incubator breeding, big sweeps): consume `heavy_ok`
  instead of running whenever — the flag now means "thin AND nothing
  opening/closing".~~ — struck 17-Jul as unverified, then **MEASURED same
  day: NO SUPPORT FOUND** (nothing contends). See above.

**Grade before wiring:** pull `fleet-clock` history — did the NYSE
open/close transitions land at the right instants (DST honest, no holiday
misses), and does `event_window` sample honestly at the 5-min cadence?
- *Pre-graded 17-Jul (first full session, PASS so far):* 16-Jul NYSE open
  logged **13:31:12Z** (true 13:30Z EDT ✓), close logged **20:01:29Z**
  (true 20:00Z ✓) — both within one 5-min tick; DST-honest; history is
  transitions-only as designed. Only ONE full session observed — re-check
  the 17/18-Jul sessions + the weekend gap at the review before wiring.

## 12. Proprioception 🦾: grade the grader's first week (added 16-Jul)

**FLEET CURRENCY VERIFIED 17-Jul 01:30Z (in the RUNNING containers, not from
git) — the "operator-gated" blockers are CLOSED, and the enactment→APPLICATION
question this item was created for can now actually be graded:**
- `tide-rider-lighter-live` (REAL MONEY): has `fleet_tuning` + the notional
  fix. The earlier "frozen at 07-11, clip lever is a silent no-op" note was
  stale — already fixed by the 16-Jul unfreeze round before it was repeated.
- `trail-blazer-live` (the LIVE Funding Farmer): carries the 17-Jul
  live-entry-path fixes (coin-veto freshness gate, L2 long-budget veto).
- `funding-farmer-shadow`: has `fleet_tuning` + `apply_levers` — **the arm
  skew CLEARED**. `xp-judge` is RUNNING `enter-gate-0.30` with the lever
  actually applied and the experiment clock restarted (`skew_notified:false`,
  `arm_skew:null`, honestly at "floors: shadow 0/30" while it accrues).
- All 13 other active services marker-grepped: every one current (16-Jul+).
- Immune reports **0 sick**; the new born-dark detector is live and quiet
  (verified it would page on a v2 relapse).
So: nothing is waiting on an operator restart. Grade the first REAL week of
proprioception + the xp pipeline from here.

**What shipped (16-Jul, operator: "advance, enhance and improve the
autonomous organ"):** `fleet_proprioception.py` — the autonomy stack's
first RETROSPECTIVE sense. Every growth-rail lever episode (open →
expire/release/change; long stances sliced daily) is graded out-of-sample:
taker levers get the replay counterfactual in $ on the tape recorded
DURING the episode (defaults vs enacted bars through the taker's real
code), scout diet levers get grading throughput (n4h delta), gapscout
gets census activity; live/xp episodes are recorded only — the judge and
fade-watch remain the sole real-money authority. Per-lever verdicts
(floors n≥2, ±$3) land in bot_state `fleet-proprioception`. FIRST
CONSUMER, restrict-only: the scout tuner refuses to re-assert a lever
carrying a fresh HURTING verdict (`apply_proprioception`) — the tuner
stops repeating a movement that measured net-negative in reality even
while in-sample replay still likes it. Board surfaces 🦾 items; immune
scans the payload; /vitals + autonomy card render it.

**Grade at the review:**
- *17-Jul day-1 snapshot (organ alive, thin as expected):* 2 episodes
  graded — taker joint stance released neutral (Σ$0.00), gapscout levers
  HELPING (census activity during the widened net); xp episode open;
  verdict expiry/probation (IMB-08) shipped 17-Jul — grade its first
  cycle here too.
- Episode ledger sanity: do episode windows match the fleet-tuning
  history (no phantom opens, releases backdated to lever expiry)?
- Counterfactual honesty: spot-check 2-3 graded taker episodes by
  re-running the replay by hand on the same window.
- Did any HURTING verdict fire, and if so — did the skip change what the
  tuner enacted next cycle (the `scout-tuner` log carries the skip line)?
- Verdict floors: are n≥2 / ±$3 (`PROP_MIN_EPISODES`/`PROP_HURT_USD`)
  the right bar, or does a week of episodes argue for more evidence?

**Expand side (wired 16-Jul evening, operator: "implement the expanding
side of things now so the July 21 can review both sides"):** HELPING now
earns, inside the existing gates — (i) a HELPING taker lever unlocks the
tuner's improve-both-halves expansion walk BEFORE the brain's ruling
floor (brain veto stays senior; every notch still replay-gated); (ii) a
HELPING scout diet lever walks one notch deeper while its lens is under
the floor (advisory tickets only, released at the floor); (iii) a
HELPING gapscout lever discounts the board's widen-ladder quiet-hour
bars ×0.75 (12h hard floor — values unchanged, only the wait). The live
lane earns NOTHING (judge's paired bar stays the only road to real
money). Grade BOTH sides at the review:
- Did any HELPING verdict fire, and did it change an enactment (tuner
  log carries "proprio-helping"; board 🌱 item carries "bars ×0.75")?
- Was every helping-unlocked notch still margin-positive on both halves
  when spot-checked by hand?
- Is ×0.75 / 12h the right ladder discount, and should helping DECAY
  faster than the verdict window's n=10 episodes?
- Symmetry check: over the week, did the restrict side (hurting-skip)
  and the expand side (helping-earn) fire in sane proportion, or is one
  eye still dominant?

**Live lane learning (wired 16-Jul evening, operator: "the live lane
needs to learn"):** live episodes now GRADE instead of merely recording —
per-trade pnl_pct during the episode vs the books' own pre-window AND the
shadow twins over the same window ('bad' only when worse than EVERY
available baseline by ≥0.25pp; per-episode floor n≥5 live closes;
clip_scale and funding bars grade as separate groups so the board's
movement is never blamed on the judge's). Consumption is restrict-first
on real money: a HURTING live.clip_scale RELEASES the board's lever and
blocks every up-step; a HURTING live.funding.* is the judge's EARLIER
fade signal (prop_fade — the judge remains the only writer); and the one
live earn: the clip ladder's TOP step (1.5) now requires a measured
HELPING grade at 1.25, fail-CLOSED (a dark sense caps the ladder at
1.25). Grade at the review:
- Did any live episode reach 'graded' (the trend book may be too slow —
  n≥5 in 24h slices), and were the twin windows honestly matched?
- Is the 0.25pp margin / n≥5 floor right for the funding bot's cadence?
- Did the top-step gate ever bind, and would the old aggregate-only
  ladder have stepped where the measured gate refused?
- prop_fade vs fade_check: which would have fired first on the week's
  data, and did either false-positive?

**Real-money consumer hook (wired 16-Jul late, operator: "and with the
new rule, real money bots too"):** `fleet_tuning.get_lever` now reverts a
lighter-live lever carrying a fresh HURTING verdict to the operator's env
default AT THE CONSUMER — the funding bot's apply_levers and both live
bots' clip read pass through it every loop, closing the latency window
between a verdict landing and the board/judge/TTL catching up. Live-lane
only; fail-safe open; restrict-only by construction (can only hand back
the operator's own default). Grade at the review:
- Did the hook ever fire, and how much earlier did it revert than the
  board release / judge fade would have (compare timestamps)?
- Confirm composition with the immune quarantine (quarantine first, then
  hurting-revert) produced no double-handling surprises in the logs.

## 13. 16-Jul fleet-wide bug audit: deferred findings (fixes shipped separately)

**STATUS UPDATE (16-Jul evening, operator blanket approval "you have my
approval / get around me having to do anything"):** items (i) zombie
positions, (ii) replay mark universe, (iii) per-bot clips (fixed in CODE —
no Railway env change needed), (iv) census double-count, (vi) history
retention, and the (viii) smaller items K-prefix + sniper W/L + Snap Back
max_open are **SHIPPED** (CHANGELOG 2026-07-16 (al)). At this review, grade
their first days instead of deciding them. Still open below: (v) merge
race (bounded, deliberate), (vii) live fill prices (needs the real signer
fill response — the one item touching the live order path), and the
remaining (viii) measurement-grade items.

**SECOND UPDATE (16-Jul, later):** (v) merge race and (vii) live fill
prices ALSO shipped (CHANGELOG (am) — the fill-response shape was verified
against the installed lighter-sdk, and the lock got an unlocked fallback),
plus every remaining (viii) item: sniper ghost-skip age-out, trade_id leg
collision, joint bars+exits replay, env-relative scout ladders,
funding-accrual restart persistence, VENUE setdefaults. NOTHING on this
item waits on a decision anymore — at the review, grade the first days of
all of it (fill_source coverage on live closes, lock behavior under the
three authors, zombie-guard closes, census counts post-fix).

Six parallel adversarial audits (live-money surface, 15-Jul organs, core
intelligence, scanners, shadow bots, dashboard/watchdog) ran 16-Jul on the
operator's "have all bugs been fixed" request. Every finding rated
critical-to-medium on a MONEY or PAGER path was fixed the same day (see
CHANGELOG 2026-07-16 (ak)). The remainder below is deliberately DEFERRED —
each needs either a trading-logic change (backtest/replay first, per
doctrine) or an operator decision. Grade at this review:

- **(i) DELISTED-BOOK ZOMBIE POSITIONS (medium, 6 shadow bots).** Ticket
  Taker, Perp Sniper, Yield Harvester, family bot, Index Rider, Snap Back:
  a position whose book vanishes (delist / dropped from the coin list) is
  never exited — even past max-hold — and holds an open slot forever.
  exit_reason returns None on a missing mark, so the hold clock never
  fires. The sniper solved this class 2-Jul ("zombie guard": close at last
  mark after N missing cycles); Counterweight + Stock Leaders already
  handle it via rebalance-close. DECIDE: port the sniper's give-up to the
  six bots (trading-logic change — needs the replay harness / paper only).
- **(ii) REPLAY MARK UNIVERSE (medium).** lighter_ticket_replay marks from
  LIQUID books only (scout tape) while the live taker marks from ALL
  active books: positions that go illiquid mid-hold never exit in replay
  and are valued at entry — an optimistic bias in closed_net, the exact
  metric the tuner and incubator accept on. Document as a known divergence
  now; fix = record all-book marks on the tape (scout change).
- **(iii) PER-BOT CLIP ENV KNOBS DEAD ON LIGHTER (medium, operator
  action).** VenueContext.order_usd ignores DISLOC_ORDER_USD /
  FUNDSPREAD_ORDER_USD outside hl_paper: Snap Back clips $30 vs its
  documented $10, Counterweight $30/leg vs the backtested $20. Either set
  LIGHTER_ORDER_USD per Railway service (operator, 2 min) or wire the
  per-bot envs through order_usd (code).
- **(iv) GAP SCOUT CENSUS DOUBLE-COUNT (medium).** An eligible gap crowded
  out of the fetch budget for >EPISODE_STALE_S (900s) closes "stale" and
  re-books as a NEW episode on the next confirmation — and every restart
  >15 min sweeps ALL episodes stale then re-books the still-alive ones.
  Inflates census_day.opened/n_booked, which the growth rail reads.
  Fix: refresh last_seen at stage-1 sighting, persist across restart.
- **(v) fleet_tuning WRITE MERGE RACE (low-med).** write_levers is an
  unlocked read-modify-write: two authors writing in the same instant can
  drop each other's just-written levers until re-assert (≤1h; the board
  re-asserts in 10 min). Expired levers can NOT be resurrected
  (_lever_alive filters), so harm is bounded to a transient gap. Fix if
  graded worth it: pg_advisory_xact_lock around the merge.
- **(vi) bot_state_history HAS NO RETENTION (ops).** ~400+ rows/day from
  the new organs alone, zero DELETE anywhere; the shared Railway Postgres
  bloats indefinitely and brain/replay reads slow. DECIDE a retention
  window (e.g. 30-60d) + who prunes (cleanup_legacy_bots boot sweep is
  the natural home).
- **(vii) LIVE FILL PRICES ARE DECISION MIDS (low, measurement).** The
  funding bot's ledger entry/exit "fill" prices are the pre-order mids,
  not venue fills — the implementation-shortfall tracker's live-vs-shadow
  premise is weakened (live slippage structurally invisible). Fix: parse
  the signer response / read back the fill from the venue.
- **(viii) SMALLER ITEMS:** listing_intel K-prefix strip mangles real
  K-symbols (KAVA→AVA, KERNEL→ERNEL → wrong intel class); sniper
  ghost-skipped candidates pend forever (age-out only covers gate-fail);
  same-cycle partial+final sniper exits collide on trade_id (ledger drops
  one leg); tuner lens-bar + exit-sweep levers enacted together but never
  jointly replayed; scout-diet levers are absolute notches (tighten if the
  operator env-widens the scout); funding-accrual gap across restarts
  (small systematic undercount); perp sniper never publishes W/L counts;
  hl_paper VENUE fallback footgun in two Dockerfiles.

## 14. EXPAND↔TIGHTEN balance audit — VERIFY COMPLETE (added 16-Jul)
Full list with fix shapes + per-finding verification status:
`AUDIT_EXPAND_TIGHTEN_2026-07-16.md` (32 consolidated findings; 7 SHIPPED
same day and verify-confirmed — the live-lane gate rework itself shipped in
the same commit: 7d-window anchors both directions, holder/trader role
split, blind-hold, explicit lever release, anti-flap). Adversarial verify
(3 lenses per target, 131 agents): fixes F1-F2/F4-F8 survive 3/3; F3's
landed-guard was refuted and REPAIRED same evening (rail authors now
return None on a failed durable write). 8 findings REFUTED (do-not-build:
IMB-05, -09, -11, -19, -21, -25, -26, -27), 4 contested-low-confidence
(IMB-16, -18, -28, -29). VERIFIED-real open items, by consequence:
- **IMB-02 (verified real)** dd-governor evidence window erased by any
  cohort flap — one Tide Rider stale-flap (hourly publish vs 65-min bar)
  wipes the 7d samples, dd recomputes 0.0, clips snap 0.25→1.0
  mid-drawdown AND dd=0.0 passes the board's fail-closed up-gate leg.
- **IMB-03/-04 (verified)** freshness-contract gaps on consumed keys:
  coin-quality veto (LIVE entry path — publisher stamps no ttl; fossil
  vetoes forever or veto silently dead) and pulse_panic (family bot + 4
  strategies halve stakes on a possibly-fossil panic flag).
- **IMB-06/-07 (survive 2/3)** judge keep-bar degrades with age
  (cumulative-mean fade check) and candidate flow self-exhausts
  (lifetime done-list over a finite universe).
- **17-Jul UPDATE — the verified-real list is now SHIPPED** (IMB-02, -03,
  -04, -06, -07, -10, -12, -17, -22, -23 in commit e657fd6 after a second
  21-refuter verify pass caught+repaired two defects in the tranche
  itself; IMB-08 shipped separately — see below). Still genuinely OPEN
  for this review:
- **IMB-08 — SHIPPED 17-Jul** (upgraded from calibration item to DEADLOCK:
  post-IMB-01 a reverted lever generates no episodes, so a hurting verdict
  could never heal on honest evidence — permanent freeze). Fix: verdict
  EVIDENCE EXPIRY (`PROP_HURT_PROBATION_D` 7d) — a non-neutral verdict
  whose newest episode is older decays to neutral+probation; the author
  probes once, fresh episodes re-grade, still-bad re-freezes within ~1
  day. Symmetric (helping expires too). Grade the first probation cycle.
- **IMB-20 (2/3, doctrine lens dissents)** registry coverage asymmetries —
  a divergence-lens emission lever etc.; adding an expand lever needs this
  review's sanction, not a session's.
- **IMB-24 (2/3)** lens-veto n4h floor counts serially-correlated raw
  emissions — adopt the brain v3 episode fields (eps4h/n_syms) in the
  taker veto + tuner floor; explicitly gated on this review validating
  those fields (replay-gated migration).
  - *17-Jul: the validation attempt found a PRODUCTION BUG, then produced
    the data that CONFIRMS IMB-24 quantitatively.* First, all four lenses
    showed eps4h=None/n_syms=0 against n4h in the thousands, because
    `brain_stats.py` was NEVER COPY'd into Dockerfile.freqtrade — the
    deployed brain import-guarded its way to frozen v2 from the day v3
    "shipped" (16-Jul). Fixed + redeployed + VERIFIED live: brain-vitals
    `engine: v3` at 00:45:39Z, EB priors 23 (v2 computed none).
  - **First real v3 episode data (00:45Z), and it makes IMB-24 concrete:**
    | lens | n4h (raw) | eps4h | n_syms | ehit4h [Wilson] | eavg4h |
    |---|---|---|---|---|---|
    | breakout | 2267 | 227 | 72 | 0.383 [0.343,0.425] | −0.24% |
    | dip | 2200 | 296 | 88 | 0.436 [0.399,0.473] | −0.31% |
    | divergence | 2553 | 235 | 58 | 0.528 [0.486,0.569] | −0.06% |
    | momentum | 1202 | **34** | **15** | 0.294 [0.205,0.402] | −0.95% |
    The serial-correlation factor is **~10x** (breakout/dip/divergence) and
    **~35x for momentum**. So today's `n4h >= 75` veto floor can be met by
    as few as ~2-8 genuinely independent opinions — exactly IMB-24's claim,
    now measured rather than argued. Momentum is the starkest: it clears the
    raw floor 16x over on 34 episodes across 15 symbols.
    **Also note every lens's episode-graded 4h mean is NEGATIVE** — worth its
    own look at the review (is the scout's diet net-negative at 4h, or is the
    4h horizon simply wrong for these lenses?).
    DECIDE: migrate the taker veto + tuner floor to eps4h/n_syms (replay-
    gated per the documented migration), and pick the floor from these
    distributions rather than by re-scaling 75.
- **G1 amendment (review-item, not blocker):** the dd-governor's <=6h
  post-reset abstain window returns scale 1.0 — decide whether it should
  HOLD a prior <1.0 clip (blind-hold pattern) instead; shadow-clip lane
  only.
- Contested (refuter lenses split — re-argue or drop): IMB-16 (governor
  consumers ignore FLEET_RISK_MODE=advisory; at minimum fix the header
  claim), IMB-18 (tuner brain-veto fails open on stale brain while expand
  runs), IMB-28 (immune sickness detection-without-action), IMB-29
  (bot_learn twin-anchor mismatches + silent v2 fallback).
- REFUTED — do not build (recorded per-finding in the audit doc):
  IMB-05, -09, -11, -19, -21, -25, -26, -27.

## 15. 🏆 Stock Leaders: the venue-fit verdict + a LIVE rail residual (added 17-Jul)
The operator flagged the book as "constantly losing" (−$127.79, −12.8%). The
premise was checked before anything was changed, and **the rule survived**:
86% of the loss is PRICE, and the price is a real market-wide crash
(SNDK/MRVL/NBIS/MU printed −18.3/−18.7/−20.7/−10.1% on Yahoo the same window)
on **3 fills in 4 days**, against the strategy's own backtested **44.3% maxDD**.
Nothing was tuned — see the fills-not-hours doctrine. The momentum rule is NOT
on trial here; the VENUE FIT is.

- **DECIDE — can this strategy pay its carry on Lighter at all?** 16 of 25
  names sit at Lighter's 28.0% baseline band, but ranking by 42d return ranks
  by CROWDEDNESS, and crowdedness *is* carry: the rule's picks printed **SNDK
  967%, NBIS 687%, COIN 245%, MU 126%, HOOD 98% apr**, 4 of 5 above baseline.
  The justifying backtest (+43.7% CAGR / 44.3% DD, 15y, 10bps/switch) modelled
  **no funding at all**. Measured drag −$17.53 in 3.7d ≈ 2% of deployed capital.
  Note the asymmetry in what the evidence can carry: the price P&L is 3 fills
  and proves nothing, but the drag is a RATE across 5 names × continuous
  accrual and converges much faster. Options: keep the veto A/B running to a
  verdict / re-run the 15y harness with a flat funding overlay at the measured
  band (no funding history exists for these perps — this is the only
  backtestable form) / park the book.
- **The evidence for that decision now exists — epoch 2 shipped 17-Jul.** The
  A/B that was meant to answer it had been measuring the SEATBELT (it differed
  from the real book in 3 variables and read "veto loses $43" while the veto
  had never fired). It is now seeded FROM the real book, mirrors the seatbelt
  and rail, and vetoes CONTINUOUSLY. **Read `vs_real` + `fund_paid`, and treat
  anything before `extra.ab_funding_veto.epoch` as void.** First production
  loop veto-exited BOTH holdings — HOOD and MU are each already above the 150%
  bar — so the variant sits in cash until the 20-Jul rebalance; that IS the
  test, not a fault.
- **SUPERSEDED 17-Jul (d) — read item 16 first.** Every APR quoted in this item
  is **8x TRUE** (the venue's floor is 3.5%, not 28%). Corrected: the picks paid
  **~7.7% true APR** against a **~52% breakeven** — **funding was never this
  book's problem**, and the "momentum ranks crowding" read here is REFUTED
  (Spearman -0.174, p=0.40; sign-unstable; untestable at n=25 where most names
  tie on the floor). `AB_VETO_APR` 1.5 = **18.75% true**, ~3x TIGHTER than
  breakeven, so the A/B vetoes affordable names and sits in cash — as configured
  it measures the wrong thing.
- **WHAT STANDS, and it needs no funding data at all: the book cannot promote.**
  Four independent harnesses put the rule's maxDD at **37-44% with ZERO funding
  modelled** (its own header says 36.9-44.3%); the go-live gate is **maxDD <
  15%** — 2.5-3x over before a cent of carry, and a one-path maxDD is
  downward-biased. Every alternative fails too: best-of-field (mega-cap
  universe) **+7.2% CAGR / -39.5% DD**, failing both halves; top-3 -67.6%. Zero
  of ~10 designs clear 15%. Carry is time-based (drag 29.5/28.4/29.1pp at
  7/14/28d) so trading less cannot outrun it. Also: `+43.7%/44.3%` is a GRID
  ARTIFACT (union-of-25 grid annualising 15.3y as 19.9, freezing stock legs on
  ~26% of rows; fair NYSE grid +59.5%/41.8%), the REACH WIDENING verdict
  INVERTS its own drawdown half (fair grid: wins CAGR 6/6, LOSES maxDD 6/6),
  and ~38% of the CAGR comes from names unselectable at window start.
- **RECOMMENDATION: PARK.** Not for venue fit — for the drawdown.
- **LIVE RAIL RESIDUAL — real money, deliberately NOT touched.**
  `lighter_funding_bot` and `lighter_trend_bot` restore `day_start_equity` only
  from the saved **halt record**, so a **PRE-halt** restart part-way down a
  losing day re-bases the daily-loss rail to the already-depressed equity and
  the 10% rail can no longer fire on that day's drawdown. The shadow pair got
  the full fix (baseline rides the persisted state, same UTC day); the live
  pair needs the operator's call. Same class as the 16-Jul `last_ts` fix.
- CLEARED in the same pass (don't re-investigate): `venues.symbol_map
  .from_lighter` is identity, so identical funding prints (COIN/XAU 245.3,
  MU/CRCL 126.1) are Lighter's own discrete bands, **not** a symbol collision
  corrupting the live funding read; and the hourly-rate convention matches the
  live bot's `H = 24*365`.

## 16. REAL MONEY: every funding APR the fleet prints is 8x TRUE (added 17-Jul)
Found while adding the scout's carry cross-section (item 15's fix). **Lighter's
`/funding-rates` `rate` is a fraction per 8-HOUR funding period. Every fleet
consumer annualises it as HOURLY (`rate * 24 * 365`).** Correct conversion is
`rate * 3 * 365 * 100` — 3 periods/day.

VERIFIED against the SETTLED series `/api/v1/fundings` (its `rate` is %/hr):
ETH predicted `9.6e-05` -> fleet prints **84.1%**, settled **10.51%**, ratio
**exactly 8.00**. DOGE and SPY also exactly 8.00 (SPY's floor: prints 28.0%,
settled **3.50%**). Arithmetic closes: `9.6e-05*3*365*100 = 10.512`.
(Compare only STABLE names — a spiking predicted rate vs a 48h settled mean
gives noisy ratios, e.g. MU 12.1 / MSTR 26.5, and proves nothing either way.)

- **The 8x is a MONOTONIC rescale.** Rankings, the `funding_extremes` ordering,
  and cross-venue `funding_divergence` (all rows share the basis) are
  **UNAFFECTED**. What is wrong: every ABSOLUTE apr a human reads, and any
  threshold meant to express a TRUE apr. Two different bugs — don't conflate.
- **DECIDE — the live gate.** `lighter_funding_bot.FUNDING_ENTER_APR = 0.40`
  really admits at **~5% true APR**. THE question to settle first: was 0.40
  **FITTED** in these (wrong) units on this venue's data — in which case it
  works as fitted and only the LABEL is wrong, and "fixing" the conversion
  would tighten the live gate 8x and change real-money behaviour — or was it
  set from a TRUE-apr reference (e.g. carried over from the HL-data carry bot,
  a different venue with a possibly different basis), in which case it is
  genuinely mis-set? `funding-carry-structural-edge-lighter` memory says the
  40% gate is backtest-confirmed; check WHICH units that backtest ran in.
  **Backtest-first either way. Do not flip it live on this finding alone.**
- **✅ SETTLED 17-Jul (later) — it is the SECOND horn: GENUINELY MIS-SET, and
  worse than the question assumed.** Checked which units the backtests ran in.
  **Every funding backtest in this repo loads HYPERLIQUID**, not Lighter:
  `backtest_directional_funding.py` (its header: *"tune the Funding Farmer's
  RISK defaults… The Funding Farmer (`lighter_funding_bot.py`)… Funding accrues
  hourly at the live rate"*, `HL = "https://api.hyperliquid.xyz/info"`),
  `backtest_scanner.py` (*"real HL hourly funding + 1h candles"*),
  `backtest_carry_hedged.py`, `backtest_tide_rider_scanner.py` — all `HL = …`,
  all `H = 24 * 365`. **HL funding really IS hourly, so `24*365` is CORRECT
  there and `ENTER_APR = 0.40` was fitted against a TRUE 40% APR.** The number
  was born in `funding_carry_bot.py` (HL data, correct units, *"[2026-07-06]
  raised from 20% to avoid fee bleed"*) and ported to `lighter_funding_bot.py`
  as a bare constant. **The PORT is the bug: it silently multiplied the gate's
  looseness by 8.** So "fixing" the conversion alone does NOT merely re-label —
  it restores the gate that was actually validated. The live bot has been
  admitting at 5% true since the port, on a bar no backtest ever supported.
- **✅ THE LIGHTER-DATA BACKTEST NOW EXISTS AND IT CHANGES THE ANSWER**
  (17-Jul, operator: *"we need everything to run off lighter as thats what we
  run on"*) — `scripts/backtest_funding_lighter.py`, verdict + limits in its
  header. **The "no Lighter history" premise was FALSE**: `/api/v1/fundings`
  pages back to **2025-05-05 (438d+)** of SETTLED HOURLY rates and
  `/api/v1/candles` pages 500 bars at a time arbitrarily far back. The HL
  harnesses fetch 150d. **There was never a data reason to backtest the Lighter
  bot on another venue.** First run: 150d, 25 markets, 2026-02-17→07-17, the
  live bot's real rules, TRUE apr from the settled series only (`/funding-rates`
  is never touched, so the 8x cannot leak in):

  | gate (TRUE apr) | P&L | funding | price | n | 1st half | 2nd half |
  |---|---|---|---|---|---|---|
  | 0.03 | −76.44 | +12.09 | −88.47 | 1074 | −34.58 | −45.13 |
  | **0.05 (LIVE TODAY)** | **−41.95** | +15.95 | −57.88 | 1261 | −21.40 | −11.40 |
  | 0.12 | −10.26 | +21.77 | −32.01 | 1071 | −12.74 | +5.68 |
  | 0.20 | +5.01 | +20.78 | −15.75 | 845 | −8.72 | +13.65 |
  | **0.40 (HL-validated)** | **−10.66** | +18.14 | −28.78 | 475 | −12.68 | +2.86 |

  1. **NO GATE PASSES BOTH HALVES.** Not one row. No validated edge at any gate.
  2. **The live gate is BELOW the FRICTION BREAKEVEN, structurally.** At a 72h
     max hold, carry/trade = `apr × 72/8760`; a 10bps round trip needs
     **apr > 0.122 TRUE** just to pay the slippage. The live bot sits at **0.05
     TRUE**; the venue's floor band is **0.035 TRUE**. Both below, by
     construction — before any price risk.
  3. **Sweep and arithmetic agree INDEPENDENTLY**: P&L flips sign between 0.12
     and 0.20; the one-line breakeven predicts 0.122. A mechanism, not a fit.
  4. **Funding is positive at every gate and too small to matter.** At the live
     gate, slippage (1261 × 10bps × $25 ≈ **$31.5**) costs ~**2×** the entire
     funding earned (**+$15.95**). The bot pays more to trade than it harvests.
  5. So the 8x did not merely mislabel the gate — **it parked the live bot in
     the WORST region of its own gate curve** (0.02–0.08 all lose $30–76).
  **So "fix the conversion, keep 0.40" is ALSO wrong**: a TRUE-40% gate fails
  both halves too (−$10.66). Neither the live gate nor the HL-validated one
  survives on Lighter. **This is a STRATEGY question, not a threshold tweak** —
  at a 72h hold, Lighter's real funding (3.5% floor, ~8% typical) cannot pay a
  10bps round trip plus the 10%-stop/4%-TP asymmetry. The carry is real and
  economically irrelevant at this holding period.
  *Limits (in the header, read them):* this replays the **naive** selector; the
  live bot also runs the multi-factor SCANNER that `funding-farmer-scanner`
  credits with "the durable +52%", plus the 11-Jul slope gate — neither modelled,
  so the live bot may beat these rows. What the scanner cannot change is #2: it
  picks WHICH names clear the gate, not how much carry a 72h hold earns.
  **NEXT: model the scanner's selection before calling the bot unfixable** — but
  do not re-denominate to 0.40 true expecting the HL result; it does not
  reproduce on Lighter.
- **The deeper finding the sweep should carry to the review: ZERO backtests
  ran on Lighter funding data.** The Funding Farmer's entire evidence base is a
  DIFFERENT VENUE's funding series, ported across a basis mismatch nobody
  noticed. So neither 40% true nor 5% true is established *on the venue that
  holds the money* — and Lighter's economics genuinely differ (zero perp fee;
  see `funding-carry-structural-edge-lighter`: *"zero perp fee flips it
  net-positive"*), so the right Lighter gate is probably NOT HL's 40% either.
  The missing artifact is a **Lighter-data funding backtest**; that, not a
  conversion patch, is what unblocks the decision.
- **⚠️ DO NOT GLOBAL-REPLACE `24 * 365` — that breaks four CORRECT call
  sites.** The fleet already knows both conventions and applies them correctly
  everywhere except Lighter: `funding_carry_bot.py` + `market_context.py` read
  **Hyperliquid** (hourly → `24*365` RIGHT), `market_pulse.py` reads **Binance**
  and already does `rate_8h * 3 * 365` (RIGHT), and every `scripts/backtest_*`
  is HL (RIGHT). It is wrong on exactly ONE venue — the one carrying real
  money. The fix is a **per-venue basis constant**, not an arithmetic
  correction.
- **Ship it as TWO commits that never mix** (the [[ab-tests-must-vary-exactly-one-variable]]
  rule, and the same shape as Stock Leaders' epoch 2): **(a) denomination,
  behaviour-NEUTRAL** — correct the Lighter conversion AND divide every
  Lighter-denominated threshold by 8 in the SAME commit (`ENTER_APR`
  0.40→0.05, `AB_VETO_APR` 1.5→0.1875, `DIV_GAP_PP` 300→37.5), asserting entry
  decisions are bit-identical, so ledgers/reports go true while behaviour does
  not move; stamp an epoch (pre-fix drag is void). **(b) re-tune the gate** —
  the real, operator-gated question, backtest-first on Lighter data. Doing (a)
  alone is honest and safe; doing (b) by accident *inside* (a) is how a
  reporting fix silently becomes an 8x live entry change.
- Same question for `AB_VETO_APR` 1.5 (= **18.75% true**, ~3x TIGHTER than
  Stock Leaders' ~52% breakeven, so it vetoes affordable names and holds cash)
  and `DIV_GAP_PP` 300/500.
- **Shadow ledgers over-accrue 8x**: `lighter_momentum_bot` /
  `lighter_index_bot` do `accrued -= rate * size * px * dt_h`, treating the 8h
  rate as hourly. Their measured "drag" is 8x too big (Stock Leaders' −$17.53
  is really ~−$2.19). The LIVE bots are charged by the VENUE, so their realized
  P&L is honest — only their DECISIONS use the inflated number.
- **Mitigation already shipped (17-Jul (d)):** `lighter-market` carries a
  `funding_basis` stamp (`true_apr_divisor: 8.0`), pinned + mutation-tested, so
  the 60-day tape is self-correcting rather than 60 days of false fact.
- Sweep needed: every `24 * 365` on a Lighter funding rate — scout, funding
  bot (`H`), momentum, index, taker/tuner/replay, dashboard.

## 17. 💸 THE FUNDING FARMER HAS NO EDGE ON LIGHTER — and its live record agrees (added 17-Jul)
The fleet's ONLY profitable live bot, measured on the venue it trades for the
first time ever. This is the biggest open real-money question on the agenda.

- **BASIS FIX SHIPPED (commit (a), behaviour-NEUTRAL).** `funding_basis.py` is
  now the fleet's per-venue authority; every Lighter consumer + every
  apr-denominated threshold moved by the same 8 in ONE commit. Verified
  bit-identical on 214/214 live books. The live bot's own log now reads
  `enter |apr|>=5%` where it read 40% — same trades, honest label. Both live
  bots deployed and verified clean (positions/entries/closed-counts unchanged,
  no orders on boot). **Nothing to decide here — this half is done.**
- **THE DECISION: `backtest_funding_lighter.py` (150d, Lighter's OWN settled
  tape) says NO GATE PASSES BOTH HALVES — at any bar.** The mechanism, not a
  curve fit: carry per trade = apr x hold_h/8760, so breakeven =
  round_trip_slip x 8760/hold_h. **63% of trades end because the funding signal
  EVAPORATES (flip/cold), at a MEDIAN 8h hold — the market closes the trade,
  not the 72h cap.** At 8h, breakeven = **~110% TRUE apr**. Lighter's floor band
  is **3.5%**; ETH is **10.5%**. The bot is **10-31x below its own friction
  breakeven**. Raising the gate makes it WORSE (hotter rates mean-revert faster
  -> 3h hold -> 292% breakeven). "Hold longer" REFUTED (72->720h moves funding
  earned by $0.20 and makes P&L worse).
- **THE LIVE RECORD INDEPENDENTLY CONFIRMS THE MECHANISM** (n=22, so it
  confirms the SHAPE, not the size): 12 of 22 trades (55%) ended on
  flip/decay — the backtest predicted 63%. And the entire +$5.32 is **7
  take-profits (+$6.47) against 1 stop (-$2.01)**. It is a TP/stop lottery that
  has drawn well on a tiny sample, not a carry harvester. The backtest prices
  stops at -$2.51/trade at 7.1% frequency; at n=22 you expect ~1.6 and it got 1.
- **The "82% WR" is NOT citable.** The modelled accrual was 8x too generous and
  feeds the win/loss call; these are SHORTS collecting carry, so the credit is
  inflated. The ledger does not store the funding component separately, so it
  CANNOT be de-inflated retroactively — the reason mix above is the honest read.
  (Equity +$4.92 comes from `account_value` and stands.) FIX FORWARD: record the
  funding component on every close so this is recomputable.
- **DECIDE — and note what is NOT being claimed.** The backtest is 150d, n=1
  path, 25 markets, no slippage model beyond a flat 10bps. It does NOT prove the
  bot loses; it proves **no gate has demonstrable support on this venue**, and
  that the structure (8h holds vs 10bps round trip) cannot pay from carry.
  Options: (a) PARK the live book pending a design that clears the friction
  arithmetic; (b) keep it as a TP/stop momentum-reversion bot and re-justify it
  as THAT (it is what the record says it is) — its TP/stop bars then need
  tuning, not its funding gate; (c) shrink and keep measuring. **Real money +
  open positions (ETH/HYPE/SNDK/XAU short) — operator's call, not mine.**
- **THE BOT IS FRICTION-BOUND, NOT EDGELESS — and the deciding number was never
  measured (17-Jul, later).** Driving slip to ZERO isolates a **+6.18 bps/trade
  GROSS edge over 1,911 trades, both halves positive** — config TP 0.04 /
  **STOP 0.10 -> 0.03** / hold 72h at gate 0.05 TRUE. It is the ONLY config that
  survives (TP 0.06 fails h2 at every slip; STOP 0.10 never passes). So a real
  edge exists; it cannot pay its execution. And the round-trip cost has THREE
  estimates **14x apart, none of them measured**: backtest ASSUMED 10bps
  (loses -$18) / shadow MODELS 1.7bps (wins +$20, both halves) / the
  live-vs-shadow gap implies ~25bps (loses badly). **The 5bps/fill that produced
  "no gate has an edge" is an assumption too — that verdict is only as good as
  it is.**
- **WHY IT COULD NOT BE MEASURED, now fixed (17-Jul (g)).** The live bot had
  **never recorded a fill price**: all three `publish_venue_order` calls passed
  `px_fill=px_decision`, so `slippage_bps` was NULL on all 48 live rows (the
  shadow twin reports 0.86bps/fill over n=158). CLAUDE.md claimed since 15-Jul
  that it records fills; it never did. FIXED — both live close paths now publish
  the decision mid and the REAL venue fill, and an echoed decision records NULL
  rather than a fabricated 0.0. **The organ built to measure this was also
  lying**: it compared 7-day AVERAGE entry prices between arms that trade at
  different moments, i.e. price DRIFT (HYPE -363.2bps entry beside +359.3bps
  exit) — withdrawn, and its selftest re-pinned (it had pinned the bug: one
  synthetic trade per arm, where the subtraction trivially IS the slippage).
- **DECIDE: measure first, then tune — do not reverse it.** `STOP 0.10->0.03`
  is cheap and supported, but shipping it while the dominant term is unmeasured
  is tuning the small number. There is also **no `hard_stop` lever** in the
  fleet_tuning registry, so the doctrine-compliant path (shadow twin -> judge)
  needs a registry addition first. Give the fixed telemetry ~a week of live
  closes, read `impl-shortfall.order_slip.live.slip_bps`, and THEN decide
  between: tune the stop / fix execution (post-only/maker, since the edge is
  ~6bps and the spread is ~1.7bps) / park.
- **COMMIT (b) — the gate re-tune — IS WITHDRAWN, not deferred.** There is no
  gate to tune to. Tuning `FUNDING_ENTER_APR` to any value is unsupported by the
  only data that has ever measured this bot on its own venue.
