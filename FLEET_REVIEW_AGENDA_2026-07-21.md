## 11. Fleet clock v2: first consumers for market open/close events (added 16-Jul)

**What shipped (16-Jul, operator: "when any market opens or closes we are
able to allocate resources"):** the circadian organ (`fleet_clock.py`) went
from zones to EVENTS — real NYSE calendar (zoneinfo DST, 2026-27 holidays,
13:00-ET early closes), `events`/`next_event` (absolute `at_utc` open/close
times for NYSE + the three crypto sessions), `event_window` (±15 min,
env-tunable), `heavy_ok` now also stands aside inside event windows, and
`fleet-clock` history is a transitions-only open/close event log. 5-min
cadence. Still ADVISORY / publish-first per doctrine — no consumer wired.

**Decide at the review — who gets wired FIRST (pick one, earn the rest):**
- **Equities books** (Index Rider 📊 / Stock Leaders 🏆): idle their scan
  loop while `markets.nyse.open` is false (the underlying doesn't print;
  a frozen index makes their marks noise) and wake at `next_open_utc`.
  Cheapest win, clearly correct — but backtest-first per house rules.
- **Scanners** (Lighter Scout / Gap Scout): cadence boost inside
  `event_window` — opens/closes are when dislocations and vol moves happen.
- **Heavy jobs** (incubator breeding, big sweeps): consume `heavy_ok`
  instead of running whenever — the flag now means "thin AND nothing
  opening/closing".

**Grade before wiring:** pull `fleet-clock` history — did the NYSE
open/close transitions land at the right instants (DST honest, no holiday
misses), and does `event_window` sample honestly at the 5-min cadence?

<<<<<<< HEAD
## 12. 16-Jul fleet-wide bug audit: deferred findings (fixes shipped separately)

**STATUS UPDATE (16-Jul evening, operator blanket approval "you have my
approval / get around me having to do anything"):** items (i) zombie
positions, (ii) replay mark universe, (iii) per-bot clips (fixed in CODE —
no Railway env change needed), (iv) census double-count, (vi) history
retention, and the (viii) smaller items K-prefix + sniper W/L + Snap Back
max_open are **SHIPPED** (CHANGELOG 2026-07-16 (ag)). At this review, grade
their first days instead of deciding them. Still open below: (v) merge
race (bounded, deliberate), (vii) live fill prices (needs the real signer
fill response — the one item touching the live order path), and the
remaining (viii) measurement-grade items.

Six parallel adversarial audits (live-money surface, 15-Jul organs, core
intelligence, scanners, shadow bots, dashboard/watchdog) ran 16-Jul on the
operator's "have all bugs been fixed" request. Every finding rated
critical-to-medium on a MONEY or PAGER path was fixed the same day (see
CHANGELOG 2026-07-16 (ad)). The remainder below is deliberately DEFERRED —
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
=======
## 12. Proprioception 🦾: grade the grader's first week (added 16-Jul)

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
>>>>>>> origin/main
