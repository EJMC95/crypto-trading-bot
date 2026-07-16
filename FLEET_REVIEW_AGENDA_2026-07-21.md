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

## 12. 16-Jul fleet-wide bug audit: deferred findings (fixes shipped separately)

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
