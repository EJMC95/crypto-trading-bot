# WEEKLY REVIEW — 18–25 Aug 2026

**Eamon, 25-Aug:** *"Full review of the last week — improvements, where we can
win more, less focus on risk more on profit, get mum v2 ready to launch under a
sub account, fleet/organ/incubator/everything review."*

Everything below is measured from the 25-Aug 08:07Z payloads, the 3,171-row
paper ledger, and the week's changelog ((pz)→(tb), 174 commits). Mum v2's
launch prep is DONE in this pass — see §4; what remains are the three acts only
you can perform.

---

## 0 · The week in one paragraph

The fleet shipped its second live book: 💸 the Farmer's live arm was retired on
its own grader's verdict and 🔮 georgia took the sub-account in place — the
first real-money retirement that had to FLATTEN, executed first-time with the
`open == 0` receipt read before any key moved. Leverage went from a refused
word to a measured discipline: 10x ceilings on both live books with the
liquidation arithmetic published on every loop, a diversified scan order that
nearly doubled what the same drawdown budget supports for free, and the venue's
whole margin surface on the bus. The brain's range reached 6.7x either way and
now sizes every living book, real money included. 👩 mum v2 was revived as a
redesign with the fleet's first on-row control arm. Cash: the live pair reads
**−$100.32 net of deposits** ($893.67 equity against $993.99 paid in — most of
it open marks at 5x, plus one telemetry gap §7.2 that needs an audit); the 17
shadow books sum **+$30.89**, led by 🌾 carry +$65.29 and 🎫 taker +$58.40
against three bleeders that are all pre-registered decision items rather than
surprises. Zero books pass the go-live gate; 🔮 georgia's shadow is closest at
5 of 6 bars, failing only `t`.

## 1 · Improvements — what the week actually banked

**The georgia chain ((st)–(tb)) — a real-money slot swap that worked first
time.** The Farmer's live arm: horizon `unreachable` on BOTH arms (live n=91,
−0.160%/trade, t=−0.88). The retirement guard latched the halt, flattened four
real shorts, published the receipt, and the swap converted `trail-blazer-live`
in place so **no credential was ever read or moved**. Six breaks were caught in
a dry run before the 15-minute live window, including georgia's clip lever being
registered but unwritable ((tb)). Along the way: her rate limiter was measured
cutting her best trades (75% of her P&L on the entry the cap refused — 2/h → 3/h,
(sv)), and the fix I almost shipped to the live Farmer was withdrawn because it
was measured on a population the book refuses ((su)).

**Leverage became arithmetic instead of argument ((sr),(sx),(sy),(se),(sd)).**
`GROSS_X` ceilings at 10 on both live books; the stop-death ceiling
(`G = 1/(|stop|+mmf)`: Avo 6.25x, georgia 9.09x) published on-row; the live row
had been advertising liquidation 21% further away than truth off a hardcoded
300bps when the venue's measured worst is 600bps — fixed and READ from the bus
now. Diversified scan order took Avo's basket N_eff 1.18 → 2.87 at zero
expectancy cost. First leverage "yes" on a shadow book: 🧭 nav-cook at 3x off a
measured drawdown budget ((sd)).

**The brain reaches everything ((sn),(so),(sp)).** Range 6.7x either way,
wired into all living books via one accessor — and (sp) caught that the safety
sentence "the rails dispose" was FALSE (a boolean cap would have silently
HALTED the live Farmer at high conviction) and made it true: rails TRIM,
restrict-only on Avo, risk-budget on the taker.

**The offense tier grew teeth ((sm),(sl),(sf),(sk),(sg)).** The ceiling became
a measurement (I24) and immediately showed capital sitting in INVERSE
proportion to edge. The never-recorded class closed fleet-wide (I23): 45 of 64
levers had no recorded quantity, 15 steered dead books — now a ratchet.
🌾 carry was unchoked: idle at 0 of 12 slots behind a gate measuring the wrong
thing (turnover ≠ fill cost, (sk)) — now 16 of 18 slots holding +41%..+364%
APR carries at a fleet-high $1,078.76 equity. The growth-rail replay was blind
to 39% of the taker and now isn't ((sg)).

**Books, honestly graded.** 👩 mum v2 revived as a redesign (the disease was
the CLOCK — 24× the decision surface, bracketed exits, and the fleet's first
live control arm publishing her own random-entry null). 🧭 nav-cook born on a
measured plateau (n=216, t=+2.74, both halves at every horizon) and then saved
inside a day from a confirm gate that had shipped 3.3× looser than the one
graded ((sa)). 🪁 band-kelly's founding claim reproduced exactly and took a
34% haircut for double-counted slippage — your dipfade override SURVIVED the
correction ((qw),(rc)).

**Refusals with evidence — the week's largest output class (~30).** Every one
is a loss not taken: the Farmer's gate re-derivation inverted at the honest
universe (prevented a real-money change), leverage rejected where t is
invariant, Hull's floor drop landing in the one tier where the pin is known to
lose, georgia's stop-widening refuted by the calibrated replay.

## 2 · Where we win more — ranked, with numbers

1. **🎫 The taker's breakoutup lens is the fleet's best live signal and it is
   sized like an experiment.** Era n=70 +1.991%/trade t=2.52; the brain's ONLY
   expand (1.25x); this week n=39, +3.13%/trade, +$55.18. It is at 6/6 slots —
   ALL breakoutup — while deploying a **median $21 clip, ~16% of its own
   book**. It is also the only book the allocation organ's claim licenses to
   expand (target $6,208 vs $1,000) and the only book `on_track` for the gate
   (eta ~27d). The clip cage and slot cap are the binding levers; widening
   either is a shadow-lane act with I19 evidence already in hand.
2. **The pre-registered winners are CONFIRMING — one of them.** The (qd)
   winners' docket registered two candidates on 18-Aug. Taker `exit:hold`
   fresh sample: **n=10, +5.86%/trade, t=3.38, +$42.87 — 90% of the taker's
   week** (verified from the ledger, all `long-breakoutup_hold`). Honest
   caveats: n sits exactly at the docket's own MIN_N floor, the bucket's
   composition shifted (registration was mixed-lens), and 9 of 10 cluster in
   18–22 Aug crypto longs — keep accruing to n≥30 and grade cluster-robust
   with the random null before promotion talk. The SECOND candidate — 🙏 avo
   shadow book-level — is going BACKWARDS (fresh n=5, −0.63%/trade), which
   counts against the (qu) 50-close revert criterion, exactly as designed.
   The let-winners-run direction points at two carried items (the replay
   blind to breakoutup, the breakout arm timed by the reversion book's 48h
   clock) with the `taker.max_hold_h` [48,72] cage already registered. Also:
   nothing EXECUTES I21's follow-through — `winners_docket.py` has no
   `--registered-after` mode; carried below.
3. **Both live books are running at 0.75× clips during a profit week.** The
   evidence board's restrict backstop reads lifetime P&L: on georgia that
   number is 2.8 days old and dominated by open marks while her realised
   record since the swap is **+$10.26 on 46 closes (+0.153%/trade,
   ~15 closes/day)**. The board's dial is doing what it was built to do — but
   its input (lifetime `pnl_abs` on a row born mid-drawdown) is worth a
   re-derivation before it costs a quarter of every winning clip.
4. **🌾 carry post-(sk) is the quiet win.** The depth/payback gate is live:
   16 slots filled, ~+$3/day accruing, book at $1,078.76. Its era grade stays
   the honest bar — expansion waits on new-policy closes, and the board has
   already widened `carry.max_positions` to 18 behind the cage.
5. **🔮 georgia's throughput steps.** The pre-registered rank 3→4 step must be
   **REFUSED on its own new data** (rank-3 closes since (sv): n=3, −7.75%
   mean, −$11.63) while rank-2 confirms out-of-sample (+0.83%, n=9). The
   unmeasured half is the hold: median 1.9h against a 1440m cap — the
   let-winners-run question now has a growing dataset. Also: her live arm
   stamps NO `entry_rank` (46/46 None) — one publish-site fix and her live
   ledger becomes gradeable by rank.
6. **Leverage headroom that is actually alive.** georgia live runs 2.38x
   actual against a 3.36x vol target and a 9.09x stop-death ceiling — the only
   live book with stop-alive turns left worth anything IF her mean holds. Avo
   has none (at 5x with stop-death at 6.25x and signal-starved at 0.33
   closes/day) — her lever is the basket, not the multiplier.
7. **Mum v2's clock is the cheapest evidence in the fleet.** ~360
   coin-bars/day of decision surface; the moment her RSI bar prints, closes
   arrive at up to 4/day. Nothing to tune — her census already publishes how
   far the market is from her bar (rsi_med 47.8 vs bar 25 right now).

## 3 · Less risk, more profit — what that means this week

The doctrine already turned this corner ((qj) "risk-eliminating job vs
profit-motivated job", the BUILD IT rule, the OFFENSE tier I16–I24). What this
session DID about it: mum v2's launch is prepped to the last operator act (§4);
the judge's stood-down census was being erased by the fleet's own immune
system — fixed, so the promotion pipeline's state is at least HONEST (§7.3);
and six tests red on main since the swap were fixed, because a red main taxes
every future profit push. What is QUEUED with evidence in hand: the taker
sizing question (#1 above), the board's 0.75 backstop re-derivation (#3), and
the georgia rank/hold steps (#5). Each is one measured, caged change — not a
risk debate.

The number that keeps this honest: the two biggest $ drags this week (⚖️
Counterweight −$39.01 lifetime, keep-or-retire pre-registered ~28-Aug — three
days away; 🛢️ Garrett, on the docket with every knob already refuted (si)) are
DECISION items already scheduled, not new work. Deciding them on their dates is
worth more than any new lever.

## 4 · 👩 Mum v2 — launch prep DONE; three acts remain (yours)

No rebuttal. The bar stated once, as the doctrine requires: **her v2 era has
zero closes** (the 7 lifetime closes are v1 + the `v1_legacy` flattens; window
floor opens 18-Sep) — and she goes live carrying her own control arm, so the
verdict will read from her row either way. Shipped this pass:

* `freqtrade-mum` is a **live-capable variant** of the proven runner
  (`lighter_avo_live_bot._BOOKS`) — identity, sizing, halt, equity guard,
  census, leverage arithmetic all inherited; nothing hand-typed for her.
* **The gap audit found the live host never called `S.custom_exit`** — mum's
  24h cap would have been dead code on her live arm (v1's disease reborn),
  and 🔮 georgia's live arm has been running real money WITHOUT her
  bounce_take/bounce_timeout/max_hold_timeout exits since the swap. Fixed in
  the family's own order (stop → roi → custom_exit → signal), driven by a
  test (an aged position at −1% closes by time cap on both books), mutation
  RED. Sibling fixes: the live payload's `strategy` field was a hardcoded
  "SwingDipV1" (georgia's row publishes that lie today — now derived from
  the variant), and `deploy_live_verify.LIVE_SERVICES` still mapped
  `trail-blazer-live` to the Farmer three days after (tb) — now georgia's.
  One declared drift REPORTED not fixed: her live arm runs the fixed −5%
  stop while her shadow trails an ATR ratchet — a live/shadow policy drift
  that needs its own measured pass, not a rushed rewrite.
* `live.mum.clip_scale` registered AND writable (the (tb) trap closed in one
  commit); `fleet_books.ROW_ENTRY` pre-mapped; the board's arm pre-mapped;
  the `[deploy-live-mum]` rule staged (commented until the service exists).
* Tests: a full `main()` boot smoke AS mum (her cell opens on an oversold
  tape, her row, her state key, her 4-slot geometry), leverage pins, refusal
  pins. Full suite green: 2,408 passed.
* One real defect found by her arithmetic: her −4% stop puts her stop-death
  ceiling at EXACTLY 10.0x, and the float tie published `stop_reachable: true`
  by 1e-17 — the comparison now reads a tie as DEAD (conservative direction).
* `MUM_GOLIVE_RUNBOOK.md` — the full sequence with her table: **3.7x is the
  last setting strictly inside the 15% gate bar; her stop is dead AT 10x.**

Your three acts, in order (details in the runbook): (1) create the
sub-account + fresh API keys in the Lighter UI and deposit; (2) create the
`mum-live` service from `Dockerfile.avolive` with `FAMILY_LIVE_BOOK=freqtrade-mum`,
`MUM_VENUE=lighter_live`, `FREQTRADE_MUM_MAX_NOTIONAL`, `MUM_GROSS_X`;
(3) uncomment the deploy rule in the same commit. The feed-following registries
move only after her row publishes `venue=lighter_live` — that's a session's
job, listed in the runbook.

## 5 · Fleet — book by book

| Book | Verdict | The number | The binding fact |
|---|---|---|---|
| 🎫 taker shadow | **GREEN** | +$58.40, wk +$47.88, era t≈2.5 | only `on_track` book (eta ~27d); sized at ~16% of book |
| 🌾 carry | **GREEN/WATCH** | +$65.29, 16 slots accruing ~$3/d | all-time claim fleet-best; in-era n=11 negative — new-policy closes decide |
| 🔮 georgia shadow | **GREEN** | +$12.86, 5 of 6 bars | fails only t (0.86); rank-2 confirms, rank 3→4 REFUSED on new data |
| 🔮 georgia LIVE | **WATCH** | −$37.53 net of deposits, 2.8d | realised +$10.26/46 closes; drawdown is open marks at 2.4x gross |
| 🙏 avo LIVE | **AUDIT** | −$62.79 net of deposits | ledger says +$0.51 — the gap hides in $0.00-booked halt closes (§7.2) |
| 🙏 avo shadow | WATCH | +$5.60 | control arm; (qu) revert criterion open, n=18 of 50 |
| 👩 mum v2 | **READY-PREP** | v2 era n=0; census live | launch prep done (§4) |
| 🧭 nav-cook | **DOWN** | row frozen 4.4d; loop traded to 23-Aug then stopped | the (ss) class recurring — needs a redeploy/restart (§7.1) |
| 🧘 douglas | BLEEDING | −$34.38, wk −$37.02, t=−2.31 | brain already at 0.75x; edge-vs-random was P=0.005 at birth — docket it |
| 🪁 kelly | BLEEDING | −$25.53 on 204 wk closes | running −0.19%/trade against a corrected +0.397% bar — grade date ~mid-Sep |
| 🛢️ garrett | BLEEDING | −$28.38, t=−2.68 | on docket 9.4d; (si) refuted every knob — decision, not tuning |
| ⚖️ counterweight | DECISION 28-Aug | −$39.01 | pre-registered keep-or-retire is in 3 days |
| 💸 farmer shadow | WATCH | −$4.46 | control arm of a retired live book; judge lane empty (§7.3) |
| 🏦 kiyosaki / 🧮 hull | SLOW-OK | +$1.61 / +$0.89, 6 open each | declared slow clocks; first supply flowing |
| 📐 grimes | SHUT-BY-DESIGN | $0.00, 0 closes ever | gate correctly closed; I17 call on its docket |
| 🎯 sniper | UNDECIDABLE | −$0.87 | oldest docket item (18.7d) |
| 🏛️ albanese / turnbull | UNDECIDABLE | +$1.81 / +$0.56 | close rates below the bar |

## 6 · Organs — 26 of 28 healthy, two defects found and one fixed

Healthy and doing their jobs: brain (v3, run 696, memory persisting, zero
urgent), evidence board + scout tuner + proprioception (8 caged TTL'd levers
open, 0 hurting), fleet risk (yellow, 14/20 longs, effective-n 9.8), immune
(quiet, correct except §7.3), oracle (16/16 crypto + 7/10 non-crypto),
sentinel (its graded playbook has silenced its own sub-coin-flip families —
the learning loop working), golive-readiness (full roster receipt, 0 READY —
honest), allocation (2 claims, funding under-allocated $6k vs $9.8k target),
radar, clock, respiration (SpO2 0.80 "labored" — from the retired lung; fix
in this PR), regen, parliament (2 books, flat).

**Incubator:** breeding but nothing promotable — champion net −$30.72,
elite empty. Honest state, not a defect: its replay grades against the taker's
tape and the taker's own defaults beat every offspring this cycle.

**The promotion pipeline has zero paths to real money** — see §7.3. The
judge's lane was the Farmer's `live.funding.*`; that arm is retired; no lane
exists for avo/georgia/mum — and the judge's best-evidenced candidate EVER
(max-hold-24: +0.19pp pooled, P(delta≤0)=0.0017, realised maxDD 42.0pp →
14.5pp) is stranded at queue head with no live consumer left. The incubator's
funding lane has been sterile since ~29-Jul (`untried: 0, exhausted: true`).
Parliament's 5-model ML reads 0.474–0.556 OOS accuracy — at or below coin
flip on 2 of 5 — feeding an ml-gate on two flat books; albanese has been on
the operator docket 17.6 days. This is the single structural gap between
"shadow book wins" and "real money grows", and it is now visible instead of
erased. The judge's pre-22-Aug done/verdicts memory may have been destroyed
by the regen wipes — recoverability from state history is a carried check.

## 7 · Defects found live this session (all from this review's own sweep)

1. **🧭 nav-cook is down twice over.** Its `bot_pnl` publisher froze 20-Aug
   22:21Z (row still says `online`, 4.4d stale — the (ss) shape recurring),
   the trading loop kept closing until 23-Aug 11:02Z, then stopped entirely.
   The watchdog is paging STALE correctly. It needs a redeploy — its
   auto-deploy rule is ACTIVE, so the next push touching its files
   resurrects it; failing that, a manual `railway up`.
2. **🙏 avo live's ledger disagrees with the venue by ~$63.** Paid-in
   ($62.80 + $317.76) minus equity ($317.77) = **−$62.79 real**, while her
   paper ledger reads +$0.51 — and the gap hides in daily-halt flatten closes
   booked at $0.00 on 23/24-Aug. The venue number is truth; the LEDGER is
   under-recording real losses, which silently flatters every grade computed
   from it. This is the top real-money audit item carried out of this review.
3. **The fleet's immune system was erasing an honest census — FIXED.** The
   judge publishes `phase="stood_down"` since (ta); `fleet_immune`'s phase
   whitelist predated the word, flagged it SICK, and `fleet_regen` clobbered
   it back to `idle` every pass — erasing the (ta) I18 census and feeding
   `impl_shortfall` a stale key. Fixed at the root (whitelist + negative
   control, mutation-verified RED).
4. **Main was red on six tests — FIXED.** The (ta)/(tb) swap's hide+prune
   half landed without five downstream syncs: respiration's `LIVE_BREATHS`,
   market-context's `LIVE_CADENCE_SEC`, proprioception's selftest fixture
   (which exposed that the live-funding grading lane now has ZERO members),
   venue-purity's rotted live-roster pin, and the retirement-consistency
   test's own hardcoded live pair — now DERIVED from `fleet_books` (the
   twelve-places rot, in the test about retirement consistency).

## 8 · Carried forward (beyond HANDOFF.md's standing 15)

* **Avo live ledger audit (§7.2)** — top real-money item.
* **nav-cook restart + postmortem of the second freeze (§7.1).**
* **Taker sizing decision (§2.1)** and **board backstop re-derivation (§2.3)**.
* **⚖️ Counterweight keep-or-retire lands ~28-Aug** — decide it on its date.
* **Judge lane for the current live pair (§6)** — the promotion pipeline's
  revival is a design item: what is the paired bar when the live book's twin
  is a family shadow rather than a funding twin? Its best candidate
  (max-hold-24) can meanwhile be spent on the Farmer SHADOW via the
  shadow-lane grant, so the fleet's strongest measured exit claim stops
  aging in a queue nothing reads.
* **Georgia's live/shadow stop drift (§4)** — fixed −5% live vs trailing ATR
  shadow; measure before touching.
* **`winners_docket --registered-after`** — I21's follow-through is currently
  hand-computed; make it executable and put it on the weekly workflow.
* **Judge memory recovery** — check whether pre-22-Aug done/verdicts survive
  in state history beneath the regen wipes.
* **Control-arm port to the variant host** — pre-activation item for mum's
  live row (runbook §5); until then her null reads from the shadow twin.
* **Mum activation registries** — move with the feed on launch day (runbook
  §4; the (tb) "eleven" measured at thirteen).
