# CLAUDE.md — crypto-trading-bot Fleet

## THE INVARIANTS — doctrine that has teeth

**Operator mandate, 31-Jul:** *"all of the breakthroughs and milestones we reach
must be doctrines that serve as building blocks so we stop this perpetual cycle
of going back to the same square one routine."*

**The mechanism that makes a doctrine a building block is ENFORCEMENT, not
wording.** Measured the day this section was written: **31 rule-shaped
doctrines across 1,405 lines against 7 executable guards.** The same session
was a controlled experiment on which of those two works, and the result was
one-sided:

| Rules read and violated anyway | Things that actually caught errors |
|---|---|
| *"pick a test that could detect the damage"* — broken **twice on one row**: a monitor compared a payload's CONTENT 20 times and never read `age_sec`, so a book DEAD for 13h read as a stable live writer | `audit_deploy_coverage` — a comma-joined `svcs=` that would have orphaned 7 files |
| *"unknown degrades to the OLD id, never to a guess"* — written in (ht); one entry later I guessed a service from an absence with no control group | `audit_changelog_letters` — two letter collisions, pre-push |
| | a selftest — a wrong assumption about `"1 "` stripping |
| | mutation testing — defects inside guards I had just written |
| | the live payload — a detector that fired NOTHING on the condition it was built for |
| | `fleet_allocation`'s lower bound — 0 of 16 directional books with a measured claim, stated in one number |

So: **every invariant below names the executable artifact that enforces it, or
declares itself UNENFORCED with a reason.** `scripts/audit_doctrine_enforcement.py`
fails the build on a doctrine with neither, and on an enforcement reference that
no longer resolves — so a guard deleted out from under its doctrine is caught.

**What a green run does NOT mean:** it verifies that a declared enforcement
EXISTS, not that it is CORRECT. A named test could be vacuous. This closes the
"doctrine with no teeth" class; **mutation testing is what grades the teeth**,
and that stays a human discipline (I3).

Add an invariant when a lesson is *general* and *recurrent* — and add an
OFFENSE invariant (I16+) when a mechanism is MEASURED to move a book toward
the gate: doctrine must grow in the win-more direction at least as fast as in
the don't-break direction, or this file becomes a museum of avoided losses.
The long-form history stays below — this section is the load-bearing subset,
not a summary.

<!-- INVARIANTS:BEGIN -->
### I1 · LIVENESS BEFORE SEMANTICS
Before interpreting what a payload SAYS, establish that something still writes
it. A frozen row and a healthy one are **byte-identical if you compare content**
— only the timestamp distinguishes them. 31-Jul: 🌾 carry was sampled 20 times
over 10 minutes, read as "one stable live writer", and had in fact been dead
for 13 hours; `status` still read `"online"`, its last word before it stopped.
Any check over a bot_pnl row, a bot_state key or a bus payload reads `age_sec`
/ `updated` FIRST.
  ENFORCED BY: `fleet_immune.py::_row_stale`, `fleet_immune.py::STALE_ROW_S`

### I2 · A CONSTANT LAG IS INVISIBLE — MEASURE THE THING THAT DIVERGES
When two counters advance together, a stuck process shows a CONSTANT offset
indistinguishable from healthy ordering. The brain's memory froze for three
days while `learning-brain.runs`=337 and `brain-vitals.run`=338 — a lag of
**1**, exactly what correct write-after-publish ordering looks like, forever.
The signal that diverges is the **timestamp skew** (71.4h). Pick the quantity
that grows with the fault, not the one the fault holds fixed.
  ENFORCED BY: `fleet_immune.py::brain_amnesia`

### I3 · A GUARD IS NOT VERIFIED UNTIL A MUTATION REDDENS IT
Write the guard, then break the thing it guards and confirm it fails. Every
real defect caught in the 31-Jul session came from a mutation or from running a
consumer against its publisher's own payload — never from re-reading the code.
Two guards written that day were themselves wrong (`brain_amnesia` on the run
counter fired NOTHING on the live payload; `stale_writer_sickness` diagnosed a
corpse as a bad deploy) and only the live data exposed them.
  UNENFORCED: mutation discipline cannot be checked by a static guard — a
  vacuous test and a real one look identical from outside. Recorded here so the
  expectation is explicit rather than folkloric.

### I4 · A SILENT WRITE FAILURE MAKES AN ORGAN AMNESIAC WHILE IT LOOKS HEALTHY
A persistence call's return value is load-bearing. `save_state` returned False
for three days; the caller discarded it and `_warn_once` logged it a single
time. The brain kept publishing fresh vitals, mults and diagnoses off a frozen
state, so `mult_streaks` never advanced and the 3-run promotion gate was
unreachable — 1 multiplier against 20 living bots. **Never discard a
persistence result, and never report a persistent condition with a one-shot
warning.**
  ENFORCED BY: `bot_learn.py::BRAIN MEMORY NOT PERSISTED`, `bot_pnl_store.py::json_safe`

### I5 · NON-FINITE FLOATS MUST NEVER REACH STORAGE
`json.dumps` emits bare `NaN`/`Infinity`, which is not valid JSON, and Postgres
`jsonb` rejects the whole write. Any payload built from ratios, t-stats or
win-rates can carry one. Sanitize at the boundary in the `_finite_or_none`
direction — a bad field becomes null and the row still writes, because losing
one field beats losing the whole state.
  ENFORCED BY: `bot_pnl_store.py::json_safe`, `bot_pnl_store.py::allow_nan=False`

### I6 · AN ABSENCE IS EVIDENCE ONLY AGAINST A CONTROL GROUP
A missing field means nothing until you can show the mechanism works elsewhere.
`extra.svc` absent on the carry row was uninterpretable until seven other
services stamped correctly in the same payload — and even then it supported a
weaker conclusion than the one published. Before reasoning from a gap, name the
population where the thing is present.
  ENFORCED BY: `fleet_immune.py::min_stamped`

### I7 · A TRIGGER A BOOK SATISFIES STRUCTURALLY IS NOT A MEASUREMENT
Before shipping any rule that fires on a book's state, ask what it looks like on
a book that is always-in, always-empty, or always-at-cap. The evidence board
widened capacity on `open_n >= cap` — true on EVERY cycle for an always-in book
— and ratcheted ⚖️ Counterweight to its cage ceiling while it was down $27.75.
  ENFORCED BY: `evidence_board.py::book_mtm_pnl`

### I8 · A DETECTOR MUST NAME THE OBJECT THE OPERATOR CAN ACT ON
If a guard's output is an instruction, it must identify something findable in
the system the operator will open. Reporting an opaque container id when the fix
is "stop a named Railway service" is a complete diagnosis and an unactionable
one. Unknown degrades to the previous, honest identifier — **never to a guess**.
  ENFORCED BY: `bot_pnl_store.py::describe_writer`, `bot_pnl_store.py::service_name`

### I9 · A REALISED-ONLY METRIC IS BLIND TO A BOOK THAT HOLDS
Any bar computed from closed trades cannot see an always-in book's open losses.
⚖️ Counterweight's realised maxDD read **0.2% against a 15% bar** while the book
sat at −$15.39 — and its three failing bars were pure time and sample size, so
it was on track to pass the whole gate in late August while below $1,000. Fold
the mark-to-market number in and take the WORSE of the two.
  ENFORCED BY: `scripts/golive_readiness.py::apply_mtm`, `scripts/golive_readiness.py::mtm_drawdown`

### I11 · FINISH THE HOUSE — CARRIED WORK OUTRANKS NEW WORK
**Operator, 31-Jul:** *"when we make progress on construction, we don't forget
it and go try and work on a random house the next day."* Before starting
anything new, discharge what the previous pass left open: an unmerged PR, an
undeployed fix, a declared OPERATOR ACTION, a `STILL BLOCKING` line. A pass that
opens a second front while the first is half-built produces two half-houses and
a changelog that reads like progress. **State at the end of every pass what is
carried, and start the next pass from that list** — not from whatever is most
interesting. `audit_recurrence` is the measurement: a subject you keep returning
to is a house you keep re-entering without finishing.
**[2026-08-20 (sl)] AND IT FINALLY HAS THE OTHER HALF.** `audit_recurrence`
measures circling AFTER it happens; it never told a session where to START.
*Eamon: "can all of the works done today; every day be recorded properly so
I am starting from where I left off every day rather than doing circles like an
incompetent."* `scripts/session_state.py` is that record and it is DERIVED, not
remembered: SHIPPED is read from git, STUCK from the live fleet, and every
CARRIED row carries a `closes_when` **predicate evaluated against the repo** —
so a finished item is reported CLOSE THIS and reddens CI, and an unfinished one
cannot be dropped without deleting a row somebody has to justify. `HANDOFF.md`
is its output. **Read it first; regenerate it last.** The CHANGELOG stays the
long-form history — it is a fine record and a hopeless handoff.
  ENFORCED BY: `scripts/audit_recurrence.py::audit`, `scripts/audit_recurrence.py::MAX_ENTRIES`, `scripts/session_state.py::carried_status`, `scripts/session_state.py::CARRIED`

### I12 · DOCTRINE IS LIVE OR IT IS ARCHAEOLOGY
**Operator, 31-Jul:** *"we can't refer back to a doctrine that was established at
the beginning of our journey — it needs to be constantly updated and engraved so
that we are future proof."* A rule written once and never revisited decays into a
record of a lesson rather than a control on behaviour — and this file has shipped
that decay repeatedly: a line reading *"NOT wired into CI, standing follow-up"*
for a day AFTER it was wired, a standing audit rule naming a RETIRED bot, an
*"advisory: zero consumers"* note that had had a consumer for days. **The loop
that keeps doctrine alive is measured recurrence:** a subject the changelog keeps
returning to must either produce a new enforced invariant or be explicitly
acknowledged with a reason and an owner. Doctrine therefore grows in response to
pain rather than to memory. **A doctrine that no longer describes the system is a
defect, not history — correct it in place and say so.**
  ENFORCED BY: `scripts/audit_recurrence.py::covered_by_invariant`, `scripts/audit_doctrine_enforcement.py::check_ref`

### I10 · REAL MONEY IS GATED BY PUBLISHED EVIDENCE, IN CODE
An env var is a deployment choice, not a verdict. A live path must additionally
read the published gate and refuse unless it says READY — fail-closed on a dark,
stale or unparseable payload, against the usual degrade-to-default habit,
because here the cost of a wrong default is unsupervised real money. The live
arm also pins the BACKTESTED config and takes no growth-rail capacity lever.
  ENFORCED BY: `lighter_funding_spread_bot.py::golive_blocker`, `lighter_funding_spread_bot.py::GOLIVE_K`

### I13 · A DEAD LOOP RUNS NO HANDLER — LIVENESS IS ONLY VISIBLE FROM OUTSIDE
Self-reporting covers a process that FAULTS, never one that STOPS. `(hw)`'s
`organ_main` wrapper catches an organ's exception and records it on that organ's
own key — but a `( while true; ... ) &` subshell that has died runs no handler,
records nothing, and leaves every key it ever wrote looking exactly as it did at
its last successful publish. **1-Aug, measured:** `bot_learn` and
`event_sentinel` had both stopped ~12.5h earlier inside a container whose other
~20 organs were seconds fresh (`brain-vitals` 12.87h vs a 7.2h TTL;
`event-sentinel` 12.52h vs 0.67h — DARK six times over), and the growth rail was
already degraded — `scout-tuner` logged *"brain dark ... lens-keyed bar walks
suppressed"*. **Nothing paged for 12.5 hours**, because the watchdog pages only
on `critical` organs and the sentinel's ONLY key was non-critical: the organ was
structurally unpageable, not merely quiet. So an in-process wrapper and an
out-of-process age check are **complements, never substitutes** — every organ
needs a key whose staleness someone is told about, and the set that is
deliberately unpageable must be declared rather than defaulted into.
  ENFORCED BY: `tests/autonomy/test_organ_pageability.py::UNPAGEABLE_OK`, `tests/autonomy/test_organ_pageability.py::test_no_organ_becomes_unpageable_without_being_declared`

### I14 · A PROXY IS NOT THE RECORD — AND AT THE WRONG HORIZON IT INVERTS
When a book's OWN realised trades disagree with a proxy, **the record decides.**
A proxy graded over a different horizon than the book actually trades does not
merely add noise — it can **invert the verdict, killing the winner and keeping
the loser.** 1-Aug, measured: `brain-lens-forward` grades the scout's tickets on
**4h forward marks**; 🎫 the Ticket Taker holds a **bracket** (tp/sl/max_hold).
On the live book's only lens the two bases disagreed in SIGN — proxy
`divergence/short −0.155%`, its own 16 live closes **+0.558%** — while `dip`,
which the proxy called acceptable, was the fleet's only statistically
significant taker result at **−1.162%/trade, t=−2.66**. Acting on the proxy
alone would have halted the live book and kept the one lens losing money.
`(dm)` had already found this in July and built a bespoke escape for ONE lens
(*"graded at the right horizon BY CONSTRUCTION"*) without generalising it — a
one-off fix is how a known defect survives. **Seniority is in BOTH directions**
(a realised loser is vetoed though the proxy likes it), gated on a **t-stat not
a bare mean** (a veto that fires on noise ends a grade before it starts), and
side-aware where the arm may only trade one side.
  ENFORCED BY: `lighter_ticket_taker.py::realised_lens_evidence`, `lighter_ticket_taker.py::REALISED_VETO_T`

### I15 · WIN RATE IS NOT EXPECTANCY — AND CHECK THE ACTUATORS, NOT JUST THE REPORTS
A rule that requires a LOW hit rate before it will act on a loser **cannot see a
loser that wins often**, and one that requires a HIGH hit rate before it will
back a winner cannot see the carry shape — lose often, win big. This fleet
already ruled on it: `(fk)` removed win rate from the **go-live gate** on 29-Jul
because 🌾 carry wins **38.8%** and is the best-evidenced book it has. The same
non-sequitur then survived for weeks inside an **actuator** — the lens veto's
`avg < 0 AND hit < 0.5` — where it was worth more than a mis-worded report: it
made a money-losing lens structurally unvetoable, and the live book's own lens
escaped by **0.002** of hit rate. **When a bad idea is removed from a report,
grep for it in the things that ACT.** The fix is expectancy-only in both
directions; win rate stays REPORTED, demoted rather than deleted.
  ENFORCED BY: `lighter_ticket_taker.py::lens_loses`, `lighter_ticket_taker.py::LEGACY_HIT_GATE`

**— THE OFFENSE TIER (added 4-Aug, operator: "only growth, no step backs, we
only focus on winning" / "lean further towards how we make bots win more").**
I1–I15 above are how the fleet stops being wrong. I16–I19 are how it wins:
point evidence-gathering capital at measured claims, keep every book decidable,
make the binding constraint reachable, and price every widening in expectancy.
Every real win-more delivery to date arrived through these four shapes — the
lens veto that kept the live book's winner trading (I14/I15), the era move that
made the gate reachable at all, the allocation organ, and the lever-reach work.
The forward metric is unchanged and senior: BOOKS THAT CAN BE GRADED, THEN GO
LIVE.

### I16 · CAPITAL FOLLOWS MEASURED CLAIMS — RANK ON A LOWER BOUND, NEVER ON THE MEAN
The fleet ran a dozen organs asking "is this book SAFE?" and none asking "where
should the money go?" — so the best-evidenced book and a zero-close book held
identical capital for weeks. Measured 1-Aug: FUNDING 4 books / 297 closes /
+$72.89 with three measured claims; DIRECTIONAL 16 books / 867 closes / −$9.21
with ZERO — while 80% of capital sat directional. A claim is
`max(0, mean − t·SE)`: ranking on the mean rewards small samples that got
lucky, and the incubator already learned this in fills. The organ is ADVISORY
by construction (moves no capital, writes no lever) — offense here means the
number exists and is ranked honestly, not that an organ spends money.
**[20-Aug (ua)] AMENDED — THE CRITICAL VALUE IS DERIVED FROM THE SAMPLE, AND
THE CLIFF THAT STOOD IN FOR IT IS GONE.** This read `1.28·SE` at EVERY sample
size, which is the NORMAL quantile — the value a t-interval converges to as n
grows — so the interval was too NARROW on exactly the thin books that needed
care, and the mitigation for that was a hard `n >= 20` cliff. **A cliff is a
second penalty for a small sample on top of the SE, which already does that job
continuously**, and it does not widen an interval — it deletes the estimate.
Measured on the live payload: three living books held a genuinely positive bound
and published 0.000 (🙏 avo shadow n=17, bound +0.362%/trade at t=1.92), and —
the half that mattered — **FIVE books published `claim_era: None` purely from
the floor**, including 🌾 carry. `claim_era` is the only field a consumer may act
on ((lx)) and its sample is by construction the smaller one, so the fleet-wide
`n_with_era_claim` had read **0 every day since the era twin shipped**: not "no
book qualified" but "no book could". Now `t_crit(n)` (one-sided Student-t at
n−1 df, pinned against the published table) and `MIN_N = 10` — a COMPUTABILITY
floor, and I21's own luck floor rather than a new invention, because the t value
widens a thin interval but cannot repair a variance estimate built from three
numbers (measured: a 3-close sample at t=33 claims +2.97%/trade unfloored).
`Z_LOWER` survives as the FLOOR on the critical value, so the env lever may only
TIGHTEN. Measured after: era claims 0 → 1, pooled 2 → 3, no book loses a claim,
and the whole sizing price is −1.4% of clip on two paper books. The floored
zeros now publish `bound_pct`, `crit` and `n_req_claim` — REPORTED, never ranked
(I15) — because 15 of 19 books read byte-identical 0.0 while their bounds ran
from −0.018% to −0.668%.
  ENFORCED BY: `fleet_allocation.py::lower_bound`, `fleet_allocation.py::t_crit`, `tests/autonomy/test_fleet_allocation.py::test_luck_does_not_outrank_evidence`, `tests/autonomy/test_fleet_allocation.py::test_the_critical_value_is_derived_from_the_sample_not_fixed`

### I17 · A BOOK THAT CANNOT REACH ITS OWN BAR IS NOT A SLOW WINNER — KEEP EVERY BOOK DECIDABLE, OR RETIRE IT
Eight of twenty-three books had <13 closes on 29-Jul; two had ZERO after 20+
days. A zero-close book is not slow — it is UNDECIDABLE, and it still consumes
a row, budget and attention (🌊 held a third of the long budget while producing
nothing; retired (if)). Two halves, both binding: every living book keeps a
25% probe floor, because a book cannot earn evidence with no capital — and a
book still undecidable at the floor after its window is a keep-or-retire call
for the operator (I11), never another tuning pass. Decidability is the first
unit of winning: an edge the fleet cannot measure is an edge it does not have.
**[20-Aug (tz)] AMENDED — FEED FIRST, AND THE ARITHMETIC HAD A KILL BIAS.
Operator:** *"Keep the books, fix your arithmetic to everything you want to
retire and start using an approach where instead of finding a way to kill
something you find a way to feed it, let it exercise, give it sunlight."*
The amendment is not a mood, it is a correction of two MEASURED defects that
made this invariant's own machinery route healthy books toward retirement:
* **The allocation split was winner-take-all.** `share = claim / total_claim`
  gives every unclaimed book a share of ZERO, so one book holding a claim of
  0.0015 took **$13,366 of $19,000** and **17 of 19 books were cut to the 25%
  probe floor** — six of them with POSITIVE measured means (👩 mum +4.66%/trade,
  🙏 avo +1.09%, 🏛️ albanese +0.28%, 💸 the Farmer's shadow +0.14% on n=195,
  📊 georgia +0.12% on n=141). That is self-fulfilling starvation: a book at the
  floor earns evidence more slowly, so its bound stays wide, so it stays at the
  floor. **This invariant's own words — "a book cannot earn evidence with no
  capital" — were being violated by the organ that cites them.** Fixed: the flat
  split is the PRIOR and evidence TILTS it (`CLAIM_TILT`), so the best-evidenced
  book still ranks first and nothing is starved by a rival's claim. Measured
  after: **0 of 19 at the floor**, the starved books go 0.25x -> 0.96x.
* **`unreachable` had no power gate.** It fired on `mean <= 0` at ANY n, and it
  is in `DOCKET_VERDICTS`, so the pipeline read `mean <= 0` -> `unreachable` ->
  keep-or-retire docket. 🌾 carry carried `unreachable` on **n=10**. Fixed: it
  now requires the one-sided UPPER bound `mean + 1.28*se` to sit at or below
  zero — the sample must actually have EXCLUDED a positive mean. A book that is
  merely thin gets the new verdict **`underpowered`**, which is DELIBERATELY not
  a docket verdict, and it publishes `n_req_decide` — how many closes would
  settle the sign. Measured: 4 books came off the conveyor; the 3 with genuinely
  excluded means stayed on it.
**THE STANDING RULE THIS LEAVES:** when a book is not performing, the first
question is **what is starving it** — supply, capital, a screen asking the wrong
question, a gate it cannot reach — and the answer is to FEED it. Retirement
requires a MEASURED exclusion (an upper bound at or below zero, or a supply that
does not exist), never a thin sample, never a verdict computed on a starved one.
A refusal to retire on insufficient evidence is a correct outcome of this
invariant, not an evasion of it. **The same critical value is used to doubt a
book as to feed one** — one standard of evidence in both directions, pinned by a
test. **[20-Aug (ua)] CORRECTED IN PLACE per I12: this read "the same z (1.28)",
and it was true only as two constants that happened to match** — a pin that
stays green against two independent implementations of the bound, which is the
second-rule shape ((hj): pin re-use by IDENTITY). `golive_readiness.horizon_crit`
now defers to `fleet_allocation.t_crit`, so both organs judge a sample of n at
the same Student-t value and the test pins that identity at five sample sizes.
In the doubt direction this is strictly the FEED direction: a thin sample gets a
WIDER upper bound, so it is harder to route onto this docket, and a missing
critical-value owner degrades to `underpowered` — which is not a docket verdict
— rather than to a retirement.
  ENFORCED BY: `fleet_allocation.py::CLAIM_TILT`, `tests/autonomy/test_allocation_consumer.py::test_no_book_is_starved_by_a_rivals_claim`, `scripts/golive_readiness.py::horizon_crit`, `tests/autonomy/test_horizon_power_gate.py::test_underpowered_is_not_on_the_retirement_docket`, `tests/autonomy/test_horizon_power_gate.py::test_the_horizon_fails_toward_keeping_a_book_when_the_owner_is_missing`

### I18 · WHEN A BOOK STALLS, FIND THE BINDING CONSTRAINT — AND THE BINDING CONSTRAINT MUST BE A REACHABLE LEVER
🌾 carry went 98.9h without an open holding 6 of 12 slots, with BOTH its
registered levers slack — the gate that actually bound (`MIN_DAY_VOLUME`) was a
bare literal: unregistered, unconsumed, invisible to the rail. A book whose
only tunable knobs are the ones with room LOOKS tunable and cannot move; the
same shape sat in `fleet_risk.py`'s long/short budgets. So: diagnose a stall by
naming which gate binds (the census pattern), and require that gate to be
registered, cage-checked, CONSUMED via `apply_tuning`, and drift-guarded — a
lever with no reader is the registered-but-inert failure. Corollary, from the
same entry: registration is REACH, not payoff — walking `carry.min_vol` to its
floor unlocked zero books, and that refutation was recorded, not buried.
**[13-Aug (lv)] THE SECOND SHAPE: A CONSUMER THAT IS A SUBSET OF ANOTHER,
RUNNING SECOND, IS UNREACHABLE NO MATTER WHAT ITS OWN LEVERS SAY.** 🎸
Barnesy's `extreme` sleeve gates on carry's bar with a 5× stricter volume
floor, off a SHARED held-set, in the same loop, AFTER carry — whose cap exceeds
the whole qualified supply. Measured: offered a coin carry had not already
claimed in **0 of 8,611 snapshots** over 30 days, while its own registered,
caged, consumed lever (`barnes.extreme_min_vol`) had room the entire time. So
when a component produces nothing, ask **who consumed the supply before it**
before believing its own census — and note the cage may lie about reach:
that lever's `lo` (5e6) sits at 90% of the highest volume EVER seen on a
qualifying crypto book ($5.53M), i.e. it was drawn without reference to the
venue's joint distribution. **A sleeve/arm that opens nothing must publish its
OWN census at its OWN bar** — `{open: 0}` is byte-identical between "quiet" and
"structurally impossible", which is how this ran dead for 8 days (I1).
  ENFORCED BY: `scripts/audit_lever_authority.py::NO-CONSUMER`, `tests/autonomy/test_book_levers.py::test_every_lighter_books_lever_is_listed_here`

### I19 · A WIDENING IS PAID FOR IN EXPECTANCY, THROUGH THE REPLAY GATE — TURNOVER IS NOT A WIN
"Disregard setbacks" bans banking a change that costs expectancy; it never
waives the measurement. The evidence is one-sided: 25 of 30 throughput
candidates died in refutation (every "faster exit" was denominator shrinkage);
`carry.enter_apr` 20%→10% would have read as pure growth and needs the rate to
hold 254 of 336h to break even; and the one honest widening channel already
exists — expand-direction enactments must IMPROVE both halves through the real
replay before they touch a lever, brain veto senior. A refusal with evidence
satisfies the growth rule; a widening that skips the gate is a step back
wearing a growth costume, whatever its trade count says.
  ENFORCED BY: `lighter_scout_tuner.py::MARGIN_HALF`, `lighter_scout_tuner.py::desired_scout_levers`

### I20 · A NEW BOOK MUST NAME ITS SUPPLY — AND A SUPPLY ALREADY SPOKEN FOR IS NOT NEW EDGE
Minting a book is the fleet's most expensive act (a row, a clock, capital,
attention) and it was the ONE act with no measurement in front of it. Measured
13-Aug: at the **20% TRUE / $2M / crypto-only** gate this venue's entire crypto
population is **KAITO, XMR, PAXG** — three coins, at most **2 qualifying at
once**, present in **6.6%** of scout snapshots — and **three books now enter
there** (🌾 carry, 🎸 Barnesy's carry sleeve, 🏦 Rich Dad, born into it the
same day). They do not starve each other the way two sleeves in one book do
((ly)); they each take the SAME position, so the fleet holds one bet three
times while `fleet_allocation` ranks three independent claims. **Concentration
is a property of the COIN**, so a per-book open-position COUNT cannot express
it — and two books published exactly that and no coin names, which is why
nothing could ask. Before minting: run the supply check, name the coins the
gate actually yields, and name every living book whose gate already admits
them. A gate is differentiated by an apr BAND or a volume TIER (🛢️ Garrett's
`[1e5, 2e6)` is the worked example of doing it right), never by a new row id.
Corollary, learned building the detector: publish the BAND, not just the floor
— an unpublished ceiling made Garrett read as a rival for a supply its own band
excludes, and a detector that overstates is one the operator learns to ignore
((gl)). Unknown bounds stay UNKNOWN and are never counted as a finding.
  ENFORCED BY: `scripts/audit_book_overlap.py::report_supply`, `scripts/audit_book_overlap.py::admits`

### I21 · WINNING IS PROVEN THE WAY LOSING IS — A SYMMETRIC REFEREED DOCKET, THEN PRE-REGISTERED FOLLOW-THROUGH
The fleet built a decision docket, BH-FDR discipline and five retirement
classes for its LOSERS and had NO instrument that could ever say "this bucket
is winning, provably" — so doctrine could only grow in the don't-break
direction, the museum-of-avoided-losses failure this tier's own preamble
names. **Operator, 18-Aug: "Let's prove some winning then shall we?" / "How
about that for the doctrine."** `scripts/winners_docket.py` is the mirror of
the (mr) losers' docket: every (book, tag/side/neutral-exit) bucket over the
book's own era-scoped, quarantine-filtered ledger, one-sided t p-values,
Benjamini-Hochberg at FDR 0.05 across all tested buckets. Its first live run
is the worked example of every defense it carries: three "winners" at t up to
**75.5** dissolved on the I7 rule (a take-profit bucket is a winner BY
CONSTRUCTION — outcome-conditioned exit families never reach the referee;
`hold`/`decay`/`flip` do), a one-tag book entered the referee four times
until identical row-sets counted once, and the n≥10 floor — not BH — is what
stops a consistent 3-close streak from outranking evidence (I16). Verdict
that day: **zero proven, two held ONLY by multiplicity** (🎫 taker
`exit:hold` n=53 t=2.65 +0.836%/trade — the exact mirror of the Farmer's
max_hold LOSER family at t=−3.27 — and 🙏 avo shadow book-level t=2.31), and
those two are PRE-REGISTERED for single-hypothesis follow-through from
18-Aug: graded on closes AFTER registration, t≥2 on the fresh sample alone,
never by re-mining the window that generated them. **A discovery is not a
promotion**: the docket is read-only, junior to the go-live gate, and a
directional survivor still owes the (hm) random-entry null before anything
ACTS on it.
**[21-Aug, published 26-Aug (tt)] THE FOLLOW-THROUGH HALF WAS WRITTEN AND UNENFORCED, AND IT
FAILED ON THE FIRST BUCKET THAT REACHED IT — corrected in place per I12.** The
sentence above ("never by re-mining the window that generated them") was prose
against a docket that had no idea a registration existed. Measured 21-Aug,
three days in: 🎫 taker `exit:hold` hit **n=62 pooled, t=3.53, p=0.0004** and
the docket printed it under **PROVEN WINNING** — over a window whose first 53
closes ARE the hypothesis. Its FRESH sample was **n=9, t=+2.99**: above the
t-bar, below the MIN_N floor, so the honest verdict was **not yet decidable, one
close short** — **[CORRECTED IN PLACE 26-Aug per I12: it took that close.
`(tc)`/`(td)` graded the same follow-through on 25-Aug at **n=10, +5.86%/trade,
t=3.38** — CONFIRMED — and doubled `TT_RISK_USD` 1.5 → 3.0 on it. The n=9
reading below is the 21-Aug measurement that motivated this guard, not the
book's state today. Note the gap it names: a human ran this split BY HAND,
twice, because no instrument would — which is the argument for the guard, not
against it.]** The caveats only the fresh split can see were load-bearing
(9 of 9 one tag `long-breakoutup`, so a different MIXTURE from the registered
one; 6 of 9 closing inside a single UTC day, so not 9 independent draws). The
sibling moved the other way and shows the same defect mirrored: 🙏 avo pooled
t=1.48 against its registration's t=2.31, its 2 fresh closes reading **t=−0.19**
— pooling was PROPPING UP a registration the forward sample is not supporting.
`PRE_REGISTERED` now declares each registration with its at-registration
statistics (a commitment, not a re-derivation), such a bucket is **removed from
the PROVEN list** while staying in the BH count `m` (so it never loosens another
bucket's threshold), and it is decided in its own section on the fresh sample
alone. **The general shape, and it is the (gk)/(iz) shape again: a defense that
lives only in prose is a defense that has not been written.**
  ENFORCED BY: `scripts/winners_docket.py::bh_survivors`, `scripts/winners_docket.py::PRE_REGISTERED`, `scripts/winners_docket.py::followthrough`, `tests/autonomy/test_winners_docket.py::test_outcome_conditioned_exits_never_reach_the_referee`, `tests/autonomy/test_winners_docket.py::test_a_pre_registered_bucket_is_never_crowned_on_the_pooled_window`

### I22 · A BOOK MUST SPEND THE ECOSYSTEM, AND ITS SPEND IS A PUBLISHED NUMBER — ONE CONSTRUCT ON A NARROW SLICE AT 1x IS NOT A SLOW WINNER, IT IS A SAMPLE THE GATE CANNOT GRADE
**Operator, 20-Aug:** *"everything you have put forward that is unreachable is
because its one construct, one set of tradeables, one set of entry and exits
which havent been explored properly, you have not set the bots up in any way
that we could ever really even use leverage."* **The diagnosis is arithmetic and
it has one equation.** With `t = S_d*sqrt(T)`, **days-to-gate = (2/S_d)^2**, and
for independent sleeves **`S_d^2 = SUM S_i^2` — decidability velocity is
ADDITIVE. One construct is one term in that sum**, so a single-sleeve book does
not merely earn less, it earns a DECISION more slowly by the square. Every I17
retirement is that arithmetic collecting: 🌊 9 buys/0 sells in 22d · 📊 17.2
closes/yr · 🧙 ~719 closes = 40 MONTHS because 1 trade of 298 was half the P&L ·
🎸 0 of 9 episodes independent of its parent. Measured 20-Aug: the venue carries
**212 active markets across 5 asset classes** ($2,186M/day crypto, **41
non-crypto at $163.8M/day — the ONLY on-venue source of a non-falling-BTC
regime**, item 18), **zero fees**, leverage 3-20x on 176 of them. **The fleet's
widest book scans 18, and every book runs at 1x notional** — not by decision but
because until (se) nothing in the tree could READ the venue's margin fractions.
**But width is not the claim, and this is NOT a licence to mint wider books.**
Market count is not bet count: 8 crypto markets are **1.35** independent bets
(mean pairwise corr +0.545), 8 cross-class are **4.81** (+0.095) — while
`fleet_risk` publishes `long_effective_n` as `1/HHI` over DISTINCT SYMBOLS and so
reports 9.0 for 9 correlated longs, overstating independence ~5x inside the organ
whose own docstring warns that *"23 open longs that are all crypto beta is ~one
trade, and nothing said so."* And **leverage adds NO `S_d`** — it multiplies mean
and sd alike so `t` is INVARIANT (six studies, six rejections); it multiplies
dollars and DRAWDOWN against the 15% bar, and is admissible only as an OUTPUT of
a volatility target on a book whose `N_eff` has been MEASURED. So before a row is
minted the design **PUBLISHES ITS SPEND** — `markets_scanned` · `n_eff` of the
positions it will actually hold (correlation-aware, never a symbol count) ·
`sides` · `gross_x` at its vol target · and its measured `S_d` with the implied
days-to-gate — in the changelog entry AND in the book's own `extra.spend`, every
loop. **A design whose days-to-gate exceeds 60 is a STUDY, not a book**: it may
run as an instrument but it does not get a row, a clock, capital or a slot of the
enforced fleet budget. **Refusals count as compliance** — a census reading "40
markets, N_eff 1.4, one side, 1x, 187 days to gate" is this invariant WORKING,
and the answer is to redesign or decline, never to widen the tape or lower the
bar.
  ENFORCED BY: `scripts/audit_book_spend.py::birth_census`, `scripts/audit_book_spend.py::MAX_DAYS_TO_GATE`

**[RENUMBERED I22 -> I23, 20-Aug.** Another session landed a different I22 on main the same day — *a book must spend the ecosystem* — and it was already cited by `scripts/audit_book_spend.py`, a CI job and a test, so it keeps the number. Recorded inline per the changelog-letter rule, which applies to invariants for the same reason: the citations are what break.**]
### I23 · A KNOB MUST RECORD THE QUANTITY IT CUTS, AND AN ACTUATOR MUST BE ABLE TO SEE WHAT IT STEERS
**Eamon, 20-Aug: *"Fix this never recorded issue across the fleet, I am so
tired of going over the same trivial problem."*** They were right, and it is one
problem in four costumes — all four found in a single session:
* 🎫 `taker.brk_trail` / `taker.brk_sl` — the give-back and the adverse
  excursion each lever cuts lived in memory and died at close, so two widenings
  were WITHHELD while a harness reconstructed from hourly candles what the bot
  already knew to the loop;
* 🌾 carry's turnover floor — a stand-in for a cost DECLARED unmeasured and
  left that way for weeks, gating the fleet's best-evidenced book to
  `eligible: 0` of 228 scanned;
* 🎫 `brk_range` / `max_hold_h` — steered by a tuner whose replay cannot fill
  the lens, so restrict enacted at delta `$0.00` for free while expand could
  never clear `MARGIN_HALF`: a **one-way ratchet**, and it had walked both to
  their tightest setting;
* 💸 the judge's paired bar — compared two arms running different ENTRY
  policies, a 0.161pp handicap against a 0.50pp margin, and zero promotions to
  real money in five weeks on the fleet's only path to more of it.

**The single shape: the thing that decides is not measuring the thing it decides
about.** Fixing instances is the circle; the class closes two ways. (1) Every
registered lever needs a recorded quantity — a `QUANTITIES` spec naming the
source and field — or a declaration with a reason and an owner. Measured the day
this shipped: **45 of 64 levers had neither**, and **15 of the 21 book levers
steered books that no longer trade.** (2) An actuator may not move a knob its
own gate cannot observe; where it structurally cannot, the cage's restrictive
end is pinned at the operator default so the blind path can only ever be
neutral, never tightening. Both are RATCHETS, not bars — a guard that reddens
the build on a pre-existing backlog gets exempted within a day and then guards
nothing ((mz)'s lesson) — so the backlog may only shrink and a NEW instance
fails immediately.
  ENFORCED BY: `scripts/audit_lever_measurability.py::check`, `scripts/audit_lever_measurability.py::RATCHET`, `tests/autonomy/test_breakoutup_ratchet.py::BREAKOUTUP_LEVERS`
**[RENUMBERED I23 -> I24, 20-Aug — same collision, same reason.]**
### I24 · A BOOK HAS A CEILING AND IT IS A MEASUREMENT — CAPACITY IS NOT EDGE, AND IT IS NOT FREE TO IGNORE
**Eamon, 20-Aug: *"The discussion of the floor is too often had, where the
conversation of how high the ceiling goes is of little discussion... they know
the floor all too well."*** Count the bars: the go-live gate asks six questions
and **every one is a floor** (≥30d, ≥30 closes, mean>0, t≥2.0, both halves,
maxDD<15%) — six ways of asking *don't be bad*. Add the stops, vetoes, screens,
cages, the governor and the halt, and until (sm) **not one instrument asked what
the most a book could earn is, or what stood in the way.** So the fleet optimised
the only thing it measured. Measured 20-Aug, slot occupancy against each book's
OWN cap beside its own mean: 👩 mum **+4.658%/trade at 100% of a cap of four**,
🙏 avo +1.085% at 40%, 🔮 georgia +0.122% at **9%** — while ⚖️ Counterweight
**−1.433% at 102%** and 🛢️ Garrett −1.460% at 88%. **Capital sat in inverse
proportion to measured edge**, and no organ had been asked the question that
shows it. Output decomposes exactly — `$/day = rate × clip × mean_pct` — and two
of the three are pure capacity that cost NO expectancy (per-trade % is invariant
to clip, `(hl)`, measured). **A ceiling is computed only on a book whose EDGE
LOWER BOUND is positive** (I16 — scale a coin flip and you scale a coin flip);
for the rest the ceiling is DECIDABILITY, *how fast can this book learn what it
is*, which is where I17 and the ceiling meet. Rate headroom comes from UNUSED
SLOTS at the book's own hold, **never a shorter one** — that is denominator
shrinkage, which `(hl)` measured as the whole of 25 of 30 "more trades"
candidates. And a ceiling is REACHABLE, never promised: it says a book could run
N× faster if its slots filled, not that the signal exists to fill them — the
book's own census answers that.
  ENFORCED BY: `scripts/ceiling.py::book_ceiling`, `scripts/ceiling.py::MIN_N`, `tests/autonomy/test_ceiling.py::test_a_losing_book_is_never_given_a_ceiling`

### I25 · A HOT WINDOW IS NOT EVIDENCE — JUDGE A CHANGE AGAINST THE BOOK'S MEAN, NEVER AGAINST THE WINDOW THAT MOTIVATED IT
**Eamon, 27-Aug: *"think broadly on how we can in some cases win, we then make
changes and it starts losing…"*** The pattern is REAL and **we are not causing
it.** Measured over 3,274 closes across 21 books, every non-overlapping
15-close window against its successor, **with no regard for whether anything was
changed** — the no-change control this fleet had never run:

| | window | → next | the book's OWN mean |
|---|---|---|---|
| after a **HOT** window | **+1.760%** | **+0.086%** | +0.190% |
| after a **COLD** window | −0.578% | **+0.362%** | +0.624% |

**A hot window is followed by a −1.674pp collapse that lands within 0.1pp of the
book's own long-run mean**, and the excess over that mean is ≈0 in BOTH
directions (−0.105 / −0.262 pp). **The successor is predicted by the book's
MEAN, not by the window before it.** We never change books at random — we change
them when we NOTICE something, and what we notice is an extreme — so we will
observe a collapse immediately after almost every change to a winning book, and
it will always feel causal. The mirror runs too: a cold window is followed by a
**+0.940pp RISE**, which is why a change made to a struggling book so often
looks like it worked. Both readings are the same arithmetic, and both are wrong.

**THIS REACHES AN ACTUATOR.** `fleet_proprioception.grade_live` judges an
episode against the book's own PRE-EPISODE WINDOW and the SHADOW TWIN, and calls
a change `bad` only when it is worse than EVERY available baseline. The twin is
a proper control and is immune — it reverts in step. **The pre-window is not:
`LIVE_MARGIN_PP` is 0.25pp against 1.674pp of measured reversion (6.7×), and
`LIVE_BASE_MIN_N` permits a THREE-TRADE baseline.** Where the twin is missing,
`all()` over one element condemns a change by arithmetic rather than evidence,
and a `hurting` verdict reverts the lever at `get_lever`. **Latent, not live at
the time of writing** (all 8 verdicts ride other bases; none is `hurting`).

**THE RULE:** the counterfactual for any change is the book's own MEAN, or a
CONTROL ARM that experiences the same reversion — never the window that
motivated the change, which is selected on an extreme and is therefore a biased
estimator BY CONSTRUCTION. Prefer the twin wherever one exists; it is the only
baseline that moves with the tide.

**AND THE SAME ARITHMETIC PRICES CELL SELECTION.** Picking the best of N
candidate cells inflates its statistic by roughly the spread of the unselected
distribution: `(uz)`, same day — 👩 mum's universe widening measured four
volume-ranked cells, the best read **t=2.30**, and resampling WHICH coins are
graded gave **median t=0.45 with 0 of 24 draws reaching 2.0**. A **~1.85 t-unit
selection premium**, and had it shipped the live book would have "started
losing" directly after its best-looking evidence.

**THE COROLLARY THAT MAKES THIS AN OFFENSE INVARIANT, not a caution:** the
response is NOT to change less. Changing less is what the biased reading argues
for, and it costs every real improvement. The response is to hold a hot streak
to the same standard as a cold one, and to keep shipping — a change judged
against the right baseline is the fleet's only way to compound.
  ENFORCED BY: `fleet_proprioception.py::grade_live`, `scripts/study_do_our_changes_hurt_2026-08-27.py::peak_arm`, `scripts/study_do_our_changes_hurt_2026-08-27.py::K`

### I26 · A STARVED BOOK IS A COST, AND "UNPROVEN" IS NOT A REASON TO REFUSE A BOUNDED WIDENING — THE BURDEN OF PROOF SITS ON THE REFUSAL
**Eamon, 28-Aug:** *"we should be exploring further not tighter"* / *"lets make
sure we dont have another day of going around in circles"*. He is right, and
the mechanism is structural rather than anyone's mood.

**REFUSING IS CHEAP AND ALWAYS LOOKS RIGOROUS. WIDENING NEEDS A CONTROL, A
PERMUTATION TEST AND A CONCENTRATION CHECK.** The two are not symmetric in
effort, so doctrine drifts tighter one invariant at a time — exactly the
"museum of avoided losses" the OFFENSE tier's own preamble warned about, now
measured at book scale.

**THE DAY THAT PROVED IT.** Three live books, and every one was starved by a
LIST rather than by a rule:
* 👩 mum scanned **40** crypto names while the venue listed **127**. Her cell
  fired **0 times in 7 days** on her list and **15** at a measured $0.1M floor.
  She was live for three days with nothing to buy, and every explanation
  offered — the RSI bar, the NOT-uptrend conjunct, the long budget — was wrong.
* 🙏 avo scanned **23** while mum scanned 98, idle **38.7h** with 2 of 5 slots
  free. The mechanism to widen her already existed; what kept her narrow was
  **a test written that same morning** (`test_the_widening_is_scoped_to_mum`)
  which pinned her exclusion. It was correct when written and became the thing
  holding a live book down.
* 🔮 georgia had two cuts proposed at her in one afternoon, both withdrawn.

**THE RULE.** For a change that is **REVERSIBLE and BOUNDED** — a universe, a
floor, a cap, a slot count, anything with an env revert and a registry cage —
on a book that **cannot currently be graded**:
* **the default is SHIP WITH A PRE-REGISTERED REVERT CRITERION**, not
  prove-then-ship. The measurement happens FORWARD on the book's own ledger,
  which is better evidence than any replay (I14) and is how the fleet's best
  work already happened ((ro) mum v2, (qu) avo's 50-close criterion, (ve)'s cap
  raise shipped explicitly to GENERATE the sample that grades it);
* **an expectancy-NEUTRAL widening on a starved book is strictly POSITIVE**,
  because decidability is the binding constraint (I17/I22) and a book that
  cannot reach its own bar earns nothing by staying narrow. `(ty)` priced this
  correctly — *"bought as DECIDABILITY, not edge"* — and it is the standard.
* **REFUSING such a widening requires a MEASURED HARM, not the absence of a
  proven benefit.** "Unproven" describes almost every good change before it
  ships. A refusal must name the number that makes it worse — dead markets
  below a measured slippage cliff, a sign-flipping sample, a stop it cannot
  reach — or it is not a refusal, it is inertia with a citation.

**WHAT THIS DOES NOT TOUCH, and the boundary is the same one as always:** real
money still needs its measured number and expectancy price (I19); the go-live
gate, the judge's evidence requirement and the safety rails are untouched; and
a refusal WITH a measured harm remains a first-class outcome — three shipped
today (rank-120 admits $0-volume markets; two georgia cuts died on
concentration and on power). **This raises the bar on refusals; it does not
lower the bar on evidence.**

**AND A PIN IS NOT A REASON.** A test that asserts a book's CURRENT narrowness
is a snapshot, not a property — when it blocks a widening, the question is
whether the widening is right, never whether the pin exists. Re-aim it and say
so, as `test_the_widening_never_leaks_to_an_unmeasured_book` now does.
  ENFORCED BY: `scripts/audit_stuck_vs_slow.py::STATES`, `scripts/audit_stuck_vs_slow.py::MIN_STUCK_PUBLISHES`

<!-- INVARIANTS:END -->



### Acknowledged recurrence — houses we keep re-entering, and why

`scripts/audit_recurrence.py` fails the build when the changelog returns to one
subject more than 5 times in 7 days without either an invariant that closes the
class or an entry here. **An acknowledgement is a decision, not a snooze**: it
must name why the class is still open and who can close it. Measured on the day
this shipped, and every line below is a real cost, not a formality.

<!-- RECURRING:BEGIN -->
- `funding-carry` — **CLOSED as a duplicate-writer house (corrected in place 4-Aug per I12; the window is still draining so the line stays).** The (ib)–(id)/(ih) chain resolved it IN CODE: `claim_writer` at the top of the loop, the loser publishes only `<bot>:standby` naming the winner, the pager is recency-scoped. Measured 4-Aug in the live payload: `funding-carry` runs the book (exactly one writer, `extra.svc` stamped, build at HEAD), `yield-harvester-shadow` stands by fresh, immune quiet, zero overlaps since 31-Jul 00:52Z. The two containers are now a DELIBERATE failover pair; stopping one is **optional tidiness, not an outstanding action**. What remains open on this book is the VENUE stall + fresh era (see the carry row) — a different house; do not stretch this line to cover it.
- `perps-funding-carry` — same house as `funding-carry` above (dashboard ROW id vs service name); closed with it 4-Aug. The row's remaining story is the era/venue one, tracked on the book itself.
- `yield-harvester-shadow` — same house, third name; closed with it 4-Aug. It is the standing-by member of the failover pair.
- `family-lighter-shadow` — STRUCTURAL mention-count, not rework (the `freqtrade-bots` shape at the family SHADOW service): it is the ONE container hosting every live book's control twin (🙏 avo, 👩 mum, 🔮 georgia `-lshadow`), so every real-money pass names it. The 7d entries are different mechanisms, none rebuilt twice: `(vv)`–`(wb)` the orphaned-container / split-brain class, closed EXECUTABLY by `(we)`'s detector; `(wp)` the scan-order parity port that lets the judge open the mum and avo pairs. **Owner: this repo** — if the service recurs on ONE mechanism twice, that is a new house and this line must not be stretched to cover it.
- `freqtrade-bots` — STRUCTURAL, not a house. 15 entries in 7d because it is the SHARED image every organ ships inside, so any organ change mentions it. This is the limit of a mention-counting detector, declared rather than tuned away: narrowing the extractor to hide it would blind the guard to a real recurrence in the same container.
- `lighter-ticket-taker` — **CLOSING, and the detector is the reason it closed.** 6 entries in 7d ((im),(il),(hj),(fq),(fm),(ek)). The recent cluster is ONE class: the lens veto judging a bracket-holding book on a 4h forward proxy. `(ij)` fixed the actuator that HALTS (the taker) and engraved I14/I15; `(im)` then found the SCOUT TUNER asking the same authority with half the evidence, and closing that turned up a THIRD consumer in `strategy_incubator` — the one this file had already predicted when the rule was centralised. Fixing instances was not closing the class, which is exactly what `audit_recurrence` exists to say. **Now closed executably**: `tests/autonomy/test_lens_veto_consumers.py` fails the build if ANY consumer outside the defining module calls `vetoed_lenses` without the lens's own record, found by AST across the whole tree so a fourth consumer cannot arrive quietly. **Owner: this repo — and if the taker recurs again for a DIFFERENT reason, that is a new class and this line must not be stretched to cover it.**
- `tide-rider-lighter` — **CLOSED 1-Aug: the keep-or-retire call was MADE — retired (if)** (9 buys / zero sells in 22 days, a third of the long budget returned; reversible via `TIDE_RIDER_RETIRED_OVERRIDE`). Line corrected in place 4-Aug per I12 (it still read "OPEN" three days after the decision) and retained while the 7d mention window drains.
- `lighter-dislocation` — **CLOSED-RETIRED 4-Aug (jh): the keep-or-retire call was MADE — retired** on the strongest evidence in the fleet (t=−2.97, n=175, mean −0.281%/trade, both halves negative, ~−$1/day; the rail structurally could not restrict it — binding floor `ENTER_FLOOR_MULT` unregistered, every reachable motion loosens). Operator decision, OPERATOR_QUEUE.md item 2 option A; reversible via `SNAPBACK_RETIRED_OVERRIDE`. Line added the day it closed so the retirement's own follow-up entries cannot re-open the subject; covers `snap-back-shadow` (the service name) too.
- `snap-back-shadow` — same house as `lighter-dislocation` above (Railway service name vs dashboard row id); closed with it 4-Aug (jh). What remains on the service is the operator's separate stop/delete act (OPERATOR_QUEUE.md item 3), which no code change performs.
- `perps-funding-lighter` — STRUCTURAL mention-count, not rework (the `freqtrade-bots` shape at the real-money row): 💸 the LIVE Farmer's row is named by every fleet-wide real-money sweep because it IS the real money, so unrelated classes each add a mention — (hc)/(hg) the era tables, (in) the detector-exemption sweep, (io) the gate0 rollback incident (closed at (ip) by the source disconnect), (jx) the sole-writer/MTM parity pass. None of the six rebuilds the same mechanism twice, and the two real classes this row DID have are both closed executably: the ungated second deploy path ((ip), `source={null,null}` verified) and the two-writer/MTM-blindness class ((jx), claim + series, AST-pinned). **Owner: this repo** — if the row recurs on ONE mechanism twice, that is a new house and this line must not be stretched to cover it.
- `perps-funding-spread` — STRUCTURAL mention-count, not rework (the `freqtrade-bots` shape at the FLEET'S CANONICAL BASKET BOOK). ⚖️ Counterweight is the only living book that closes 10 legs in one instant, so it is the worked EXAMPLE in every cross-sectional, grader or harness change — and the 6 entries in 7d are six different mechanisms, not one house: `(ky)` cluster-robust `t`, `(kf)` the exit-harness side-sign inversion, `(iz)`/`(ja)` the MTM read seam, `(hp)` one-book-one-writer, `(hn)` the review-rule fix, `(gl)` deploy naming. **Not one of them rebuilds the book.** Being the clearest instance of a fleet-wide defect is the opposite of a house being re-entered — it is why the defects were findable. **The keep-or-retire call was MADE 1-Sep — KEPT, under I17-as-amended, on Eamon's "Address all of the above" delegation ((wa)); corrected in place per I12 because the numbers this line carried had gone stale in the meaning-changing direction.** The ~28-Aug defense read *"+$4.80, +0.461%/trade, block-permuted P=0.175"* on the enterable population; the grader's own `class_split` on 1-Sep reads **on-class n=116, −0.711%/trade, t=−0.81, −$3.94** (the 21 off-class closes its own screen now refuses carry −$36.48 of the −$40.42). Negative — but the on-class upper bound (mean+1.28·SE ≈ **+0.41%**) has NOT excluded a positive mean, and I17-as-amended is explicit: retirement requires a measured exclusion, never a thin sample; the pooled exclusion (upper −0.772%) is 90% the screened-off class. **PRE-REGISTERED at the keep (I21 — graded on FRESH closes only, never the window that motivated it): read at n≥60 on-class closes AFTER 1-Sep or on 1-Oct, whichever first; RETIRE without further debate if the fresh on-class upper bound (m+1.28·SE) ≤ 0; keep grading if the fresh mean > 0; anything else returns to Eamon with both numbers.** If this row recurs on ONE mechanism twice, that is a new house and this line must not be stretched to cover it.
- `freqtrade-georgia` — STRUCTURAL mention-count, not rework (the `freqtrade-bots` shape at the fleet's NEWEST real-money row). 6 entries in 7d, and they are **six different mechanisms, none rebuilt twice**: `(sz)` the variant host had never been driven as her (test coverage), `(ta)` the Farmer's live arm retired and she took the sub-account (a retirement), `(tm)` her live arm was not running her own exit policy (a policy port), `(ts)` the judge's pair census scored each arm's OLDEST 30 closes (a census bug in an organ), `(uk)` the Farmer's retirement flatten was read as slippage and cut all three live books' clips (an organ misread), `(vn)` her entry lockout ran to the LOOKBACK because the live arm never latched (a rail). She is the only live book with a meaningful closed sample — 56 against avo's 6 and mum's 0 — so **every fleet-wide real-money mechanism is first observable on her**, which is the opposite of a house being re-entered: it is why those six defects were findable at all. **Owner: this repo — and if this row recurs on ONE mechanism twice, that is a new house and this line must not be stretched to cover it.** The genuinely open item on her is not a mechanism but a DECISION: her shadow arm is 5 of 6 bars and `undecidable` at ~776 days (mean +0.059% against its own `mde80` of 0.437%), and no amount of tuning closes that gap — that is I17's keep-or-decide call, owner OPERATOR.
- `equities-regime` — STRUCTURAL mention-count, not rework (the `freqtrade-bots` shape at book scale): 📊 Index Rider is a member of every fleet-wide sweep in the window — (gl) deploy naming, (hu) svc stamps, (hq) MTM wiring, (iz) the MTM read-side fix — and none of the six entries rebuilds the book itself. It sits OUTSIDE the graded set today (zero closes, below the publish filter) while its `:equity` series accrues (n=1436 since 30-Jul). The genuinely open item is DECIDABILITY at its measured ~17 closes/yr — exactly I17's class. **Owner: operator** — keep-or-retire when the per-asset oracle evidence window closes (~mid-Aug, the 28-Jul review accrual); a pass that tunes it instead of deciding is the I11 behaviour.
<!-- RECURRING:END -->

## What This Repo Is
Eamon's crypto trading bot fleet — **LIGHTER-FIRST since 2026-07-14** (user
decision: "all services must run off lighter"). Books are $1,000 paper/shadow
each, no top-ups, except the real-money Lighter live rows. Dashboard:
https://pnl-dashboard-production-858c.up.railway.app/

## Fleet Overview (post 14-Jul Kraken retirement; post 17-Jul LIGHTER-ONLY cut)
Every TRADING row below is on Lighter. Four non-Lighter services were code-
guarded off on 17-Jul — see the LIGHTER-ONLY table after the fleet table.

### The trading fleet (Lighter)
| Row | Name | What it is |
|-----|------|------------|
| freqtrade-{mum,avo-maria,georgia}-lshadow | 👩🙏🔮 family | **👩 mum REVIVED 19-Aug (ro) as v2 — operator reversal of the (rd) retirement, and a REDESIGN not a reprieve: `OversoldRebound`, 1h (was 1d), entry `RSI(14)<25` AND **NOT** `e50>e200`, bracket predefined at entry (roi 2.0%→0 over 12h, −4% stop, 12h carry-bounded max_hold). THE AUTOPSY: her disease was THE CLOCK — a STATE entry filled all 4 slots in one second (all 3 lifetime closes stamped 12-Jul 21:41:49Z), her only exit was a ~monthly death cross, holds 33/29/25 days, ~2.4 closes/30d ⇒ ~12 months to the bar. She was never losing (+$0.679 realised); she was UNGRADEABLE. **(rd)'s funding-drag figure is CORRECTED per I12: settled funding on her three closes is −$0.246, not −$2.15 (~9× overstated)** — the venue's SETTLED series quotes **%/hr** (median non-zero 0.0012 = the resting default), so the hourly fraction is `rate/100`, never `rate/8`. TWO MEASURED NUMBERS DESIGN v2: carry punishes DURATION (**measured +0.0171%/day** majors median over 478d×20 coins ⇒ v1's 29d hold started ~0.50% behind, v2's 12h cap 0.009%; HYPE +0.0445%/day worst, DOT/SPY negative) while EXECUTION IS NEARLY FREE (median exit gap **−0.8 bps** over ~400 short-hold fleet closes) — this venue charges almost nothing to trade OFTEN and a real amount to hold LONG, and v1 sat at the wrong corner of both. 1h gives ~360 decision points/day vs ~15, so **30 closes lands in ~a week, not ~a year**. Entry cell is (qu)'s measured one (only `rsi<42` carries information; the `e50>e200` filter is ACTIVELY DESTRUCTIVE) — **hypothesis-grade and stated so: the `rsi<25` dose-response has DECAYED through zero (+4.97→+2.05→−0.31→−0.41)**. **CARRIES ITS OWN CONTROL ARM** — the first LIVE book to do so: every entry records a matched-window random OTHER coin, `extra.control` publishes {n, mean_pct, null_pct, edge_pct} always (incl. n=0), so (hm)'s random-entry null is answered from the payload. I20: NOT-uptrend makes her cell **disjoint by construction from 🙏 avo's ON THE SAME TIMEFRAME** (avo requires `e50>e200`), so the (lv) starvation trap between them is unreachable — **declared limit: they read trend on DIFFERENT timeframes (1h vs 4h), so a 4h-uptrend/1h-downtrend coin can satisfy both and a simultaneous long is possible; bounded by fleet_risk's per-symbol cap + the 20-long budget, monitorable from the `held` maps, and to be closed with a 4h screen only if co-holding is MEASURED material.** Era moved (both tables, 19-Aug 21:45Z); her 4 frozen v1 positions flatten once tagged `v1_legacy` (they held every slot — undecidable by a NEW mechanism); `custom_exit` un-gated from `isinstance(DayTraderGated)` (a time stop on a new carrier was dead code, I18). `MUM_RETIRED_OVERRIDE` no longer applies. Pinned by `tests/autonomy/test_mum_v2.py` (15 tests; the boundary-in-the-future defect was caught by them pre-ship). SwingDip/DayTraderV5 on Lighter (gate0 `lighter_family_bot.py`, service `family-lighter-shadow`); closes tagged `long-<tag>_<exit>` + brain stake-mults applied at entry (15-Jul). **👨 freqtrade-dad RETIRED 15-Aug (nf)** — the red-stop slate: docket horizon `unreachable` (era n=15, mean −1.317%/trade), 3 paper positions freeze; `DAD_RETIRED_OVERRIDE=run` reverts. 🙏 avo shadow runs at SHADOW cap 6 since (ne) (`FAMILY_SHADOW_MAX_OPEN_OVERRIDES`, main()-only — the declared literal 4 stays live surface). **[19-Aug (qu)] 🙏 AVO'S ENTRY PREDICTS NOTHING, MEASURED EXIT-FREE — AND THE OPERATOR KEEPS THE BOOK, ON THE RECORD.** Asked with no bracket at all (1,156 signals / 475d / 23 coins), the SwingDip signal's excess over MATCHED-RANDOM entries is **negative at 4h/8h/12h** (−0.131/−0.171/−0.139%, P(random≥signal) **1.000/0.998/0.973** — random beats it outright) and ~zero at 5d, which is where its 3.5d median hold lands. The one positive-looking cell (h=60, +1.381%, naive t=+5.01) dies overlap-aware: cluster-robust t **+1.43**, month-as-unit +0.81, bootstrap CI [−1.11%,+2.57%], shift-placebo **P=0.285**, and **top 3 of 17 months = 97.3%** of the excess. Corroborated twice: only `rsi<42` carries information and **the `e50>e200` trend filter is ACTIVELY DESTRUCTIVE** (adding it lowers every base's mean), 0 of 21 cells survive BH at FDR 0.05; and the signal's best conditional cell (**|z|=1.63**) is WEAKER than the null's own best-of-48 (median |z|=2.08), P=0.830. **This is why ~600 cells of exit/stop/ROI/timeframe/sizing sweeps all failed — there was no entry edge for any bracket to harvest; run the EXIT-FREE forward test FIRST.** A FOURTH undecidability class, **UNDECIDABLE BY FLATNESS**: normal close rate, NO tail (trim both tails and it barely moves, −0.523→−0.468%), needs **493 closes ≈ 4.9 YEARS** to reach |t|=2. Mechanism is I15 arithmetic — wins **57.3%**, needs **62.7%** (28 stops at −10% vs 100 exits at +2.197%). **KEPT anyway (operator, 19-Aug) at a measured −$0.68/month**, because the live arm's own ledger is n=3 and the record outranks the proxy (I14). **REVERT CRITERION, any one reopens the call:** (1) pooled ledger averages **≥+1.649%/trade over the next 50 closes** (+$12.80 = +20.5% of book) — today n=18/+0.901%/t=+0.66, and **anything less decides nothing**; (2) the `rsi<25` dose-response (decayed +4.97→+2.05→−0.31→−0.41 rolling 120d) prints **>+1.0%/trade at h=12 with cluster-robust t≥2**; (3) a non-falling-BTC regime arrives (item 18). **DO NOT read a good run as evidence** — P(profit at 12mo by luck alone) = **18.5%**, and the shadow's 12W/3L +0.996%/trade sits INSIDE the negative record (CI contains −0.523%; replay reproduces that exact stretch). **[21-Aug (sr)] THE LIVE ARM IS FUNDED 3.7x AND LEVERED 1.4x — Eamon deposited $167.76 (equity $62.93 → $230.70) and asked for "training wheels off".** The deposit itself was handled correctly end-to-end (venue credits `collateral` BEFORE `total_asset_value`; the equity guard rejected the unexplained +$167.77 three times and rebased on the corroborated collateral-stable path, booking it as `capital_adjust 167.76` so `pnl_abs` stayed **+$0.14** instead of printing +267%). **The defect was the CAP**: `clip = equity/max_open` re-sized entries $15.73 → $57.68 while `FREQTRADE_AVO_MARIA_MAX_NOTIONAL` stayed a fixed $200, so 4 × $57.68 = $230.70 > $200 and the book would have settled at **3 of 4 slots with $57.68 never deployed** — silently, and DELAYED, because `open_notional` prices held positions at their own entry clip. `cap_slots` publishes that arithmetic every loop (`cap_slots < max_open` = the cap, not the signal, is holding the book down) beside a `notional_cap_skips` counter. **`AVO_GROSS_X` (now 1.4, cap $350) is leverage on a DERIVED budget**: every slot stops at −10% and the held names are QQQ/SPY/NVDA (`N_eff` ~ONE BET), so all-slots-stop is the CENTRAL case and costs `GROSS_X × 10%`; the go-live gate fails above 15% maxDD ⇒ `GROSS_X_MAX = 0.15/|stoploss|` = **1.5x**, shipped at 1.4 (14%) to stay strictly INSIDE the bar rather than exactly on it ((gv)). **Leverage moves this book NO closer to the gate** — it multiplies mean and sd alike so `t` is invariant (I22, six prior rejections); it deploys idle balance and makes (qu)'s pre-registered 50-close revert criterion resolve at 1.4× the size, nothing more. `_clip_scale_now`'s "1.00x by construction" claim is CORRECTED IN PLACE — that lever is still restrict-only, but the book is no longer 1x. Pinned by `tests/autonomy/test_avo_cap_slots.py` (42 tests, 5/5 mutations killed — including one that survived the first round: leverage configured and silently never applied). **SLOTS 4 → 5 the same day, and the ask was 6:** both arms are SIGNAL-limited, not slot-limited — time-held occupancy averages **2.24 live / 2.41 shadow**, the live arm sits at its ceiling **21.7%** of the time, and the shadow (running 6 slots all along) reached 5 for 4.5% of its life and **6 never, in 17 episodes**. Since `clip = equity × gross_x / max_open`, slots only SLICE a gross budget that `GROSS_X_MAX` already bounds — and that bound is independent of `max_open`, because all-slots-stop always costs `equity × gross_x × |stop|`. So 6 slots would have deployed **$130 vs $181 expected, −28%**; 5 captures the reachable slot and stops. **Slot count cannot add dollars; only `gross_x` can, and it is capped by the drawdown measurement.** Live geometry: clip **$64.59** · gross $322.97 = **1.40× equity** · worst-case DD **14.0%** · `cap_slots` 5 of 5. Era NOT reset (capacity = ordinary tuning, (hc)). **LEVERAGE 5x + A DIVERSIFIED SCAN (21-Aug (sr), Eamon: "set leverage to 5" / "i want this bot to find a way so leverage can be used").** `GROSS_X_MAX` is now an OPERATOR env (`AVO_GROSS_X_MAX`, 5.0), not a code-derived bound — risk appetite belongs to the person whose money it is; the code's job is the arithmetic, published. Live: clip **$230.75** x 5 = **$1,153.75 = 5.00x equity**, cap $1,200, all-slots-stop **50%**, liquidation at a **-17.0%** basket move (worst mmf of its books = 300bps, read PER BOOK off orderBookDetails — mmf is in BASIS POINTS; never derive it from imf, the (no) trap). **THE EXPOSURE WAS THE BASKET, NOT THE MULTIPLIER**: it held QQQ/SPY/NVDA = **N_eff 1.18, rho +0.775** — one bet wearing three names, 5x over. Cause was structural, the (hl) Index Rider finding at a second book: the loop scanned `list(COINS)+list(NONCRYPTO_UNIVERSE)` IN LIST ORDER and took the first qualifying signal, so 29 crypto names had first refusal on every slot and diversifiers were last by construction. `diversified_order` offers the candidate that most lowers basket correlation FIRST — **the scan order changes, the entry path does not** (every gate/veto/cap/sizing rule untouched; byte-identical for any single candidate), so it costs **no expectancy** and turns away **nothing**. Measured: offers WTI before BTC, taking the basket **N_eff 1.18 -> 2.87** (rho +0.132) — 2.4x the effective diversification, free, on bars `CandleCache` already held. Row publishes `leverage.{set,n_eff,basket_rho,vol_target_here,deployed_at_full,all_slots_stop_pct,liq_gap_pct}` so "five names" and "one bet" stop being the same byte-string. Fail-safe: an unmeasurable pair is **None, never 0.0** (zero reads as perfectly-diversifying and would BUY leverage); dark/empty/junk returns the list unchanged. Pinned by `tests/autonomy/test_avo_diversification.py` (7/7 mutations, two of which — an untested overlap floor and a mutation that never ran — were defects in my own tests) |
| ~~crypto-{intraday-15m,swing-daily}-lshadow~~ | spot ports | **BOTH RETIRED 15-Aug (nf)** — the red-stop slate: intraday `unreachable` (era n=72, −$6.88, 3 paper positions freeze; `INTRADAY15M_RETIRED_OVERRIDE`), swing the I17 `no_rate` undecidable class (n=3 in six weeks; `SWINGDAILY_RETIRED_OVERRIDE`). **`crypto-breakout-4h` RETIRED 14-Aug (mr)** — the I17 call, operator decision: the ONLY one of the NINE books on the decision docket that survives Benjamini-Hochberg at FDR 0.05 (p=0.0036 vs a 0.0056 critical value; pm-abbott, the next closest, reads 0.0430 vs 0.0111 and is NOT evidence). Both samples agree in direction AND significance — in-era n=15 mean −1.745%/trade t=−3.50 halves −2.56/−4.94 win 20%, all-time n=21 mean −2.236% t=−5.48 halves both negative win 14.3%, −$12.37 realised at ~−$0.48/day, horizon `unreachable`. Freed TWO slots of the ENFORCED 20-long budget (TRX+LINK, TRX being the fleet's largest single-symbol long share). **Costs no thesis coverage**: 4h breakout lives on in 🧙 book-schwager ~~(n=277, +$457.21, t=1.88, both halves positive)~~ **[corrected 16-Aug (nu): that figure does not hold — Schwager re-measures at n=298, +$146.41, t=0.86, h2 negative, and its edge is NOT ESTABLISHED (random-null P=0.183). The (mr) retirement of breakout-4h still stands on ITS OWN evidence (t=−3.50 in-era, BH-significant at FDR 0.05), which is unaffected; but the "coverage continues elsewhere" consolation is now weaker than it read — the surviving expression is unproven, not proven.]** — a losing EXPRESSION retired, not the idea. **The first retirement of a book that SHARES ITS MODULE**, so it is ROW-scoped: `lighter_family_bot.RETIRED_BOOKS` declares it once and `live_strategies()` derives the running roster ((mo)) — the idle-the-whole-process pattern of 🌊/📊 would have silenced six healthy books, and `tests/autonomy/test_breakout4h_retired.py` pins exactly that (4 mutations verified, including the too-broad one). Two open paper positions freeze, the precedent both prior row retirements set. Reversible via `BREAKOUT4H_RETIRED_OVERRIDE=run` |
| crypto-trend-daily-lshadow | 🌊 Tide Rider | **RETIRED 1-Aug (if): 9 buys / ZERO sells in 22 days while holding a third of the fleet's long budget — the keep-or-retire call was made. Row hidden + pruned (both halves); reversible via `TIDE_RIDER_RETIRED_OVERRIDE`. History below kept per I12's correct-in-place rule.** shadow only. Its LIVE row `crypto-trend-daily-lighter` was RETIRED 17-Jul — 🎫 Ticket Taker took the slot on the SAME service/keys/sub-account, so leaving both rows would DOUBLE-COUNT the same $34.67 of real money. **[30-Jul (hk)] ZERO closes in 20 days was CORRECT, not broken** — 1 buy / 0 sells ever in `venue_orders`, and its universe produced no signal flip of any kind in that time. What WAS broken: `(fz)` claimed this book was widened off the scout and it had no `fleet_bus` import and no COPY. Now wired: **6 → 16 books measured on the live bus**, additive (empty ⇒ keep the configured six, never shrink). **The prerequisite shipped with it:** `scan_universe()` scans the resolved universe ∪ every HELD coin, and `supports()` no longer skips a held position — without both, a coin leaving the list kept its position with no exit, no stop and no seatbelt (this book's only sweeper is `not dry_run`-gated, so shadow had none). Nine of the ten added books are TRADFI, so this is now a venue-wide trend follower despite the row name; kept ON (the EMA50/200 signal is per-coin, so it is per-asset by construction and cannot breach item 18) and reversible via `TREND_ALLOW_TRADFI=0`. Its 2.7yr +52% validation is SIX CRYPTO MAJORS and says nothing about XAU/SOXL — those sleeves are unvalidated and are there to be graded. Levers that can actually move its rate: `trend.universe_n` / `trend.min_vol_m` / `trend.max_open` (`trend.rank_by_funding` is inert while candidates ≤ slots — measured max simultaneously-golden coins = 1 vs 6 slots). Author: evidence board, gate lever = the universe. **[30-Jul (hl)] NO THROUGHPUT IS AVAILABLE WITHOUT PAYING EXPECTANCY** — 25 of 30 candidates died in refutation. `close<EMA20` gives 6.4x the closes and improves per-trade 5.1x, but **per bar-day held only 1.04x**: the gain is denominator shrinkage (median hold 58.5d -> 4d), a content-free 3-day time stop reproduces 78%% of it, and the exposure-matched null BEATS it. Tightening the catastrophic stop raises closes and makes total P&L WORSE. `min_vol_m` 5.0 -> **3.0** (ZEC+PAXG carry 91%% of the delta; 2.0 lowers the mean). `trend.max_open` cage hi 12 -> **9 as a SAFETY bound**: at >=10 the -10%% daily-loss halt becomes reachable before the -35%% stop, and in shadow that halt skips the whole scan — no death cross, no seatbelt, for the rest of the UTC day. `extra.caps` now carries a SKIP CENSUS: the row said `universe: 16` while 6 of the 16 are structurally mute (<202 bars), overstating the actionable universe by 60%%. 50/200 -> 10/20 is real throughput (0.38 -> 3.06 closes/30d) with UNESTABLISHED expectancy (beats only 84%% of 3000 placebo draws) — if ever shipped it is a SEPARATE ROW with the 50/200 control left running, never a re-parameterisation |
| ~~perps-funding-lighter-lighter~~ / ~~-lshadow~~ | 💸 Funding Farmer | **SHADOW TWIN RETIRED 2-Sep (wt)** — the day the 🧪 judge's serial lane moved to 👩 mum; its own record `unreachable` (n=200, −0.525%/trade, t=−2.32, upper bound −0.233% ≤ 0); SHADOW-mode guard in the module, `FARMER_SHADOW_RETIRED_OVERRIDE=run` reverts; 5 paper positions froze. **LIVE ARM RETIRED 22-Aug (ta) — 🔮 georgia takes the sub-account. Eamon: *"just replace farmer with georgia as weve done so many times before"*, the 🎫-takes-🌊 (17-Jul) / 🙏-takes-🎫 ((ma)) precedent.** The call is the fleet's OWN grader's, not an opinion about a bad week: horizon **`unreachable` on BOTH arms** — LIVE n=91 mean −0.160%/trade t=−0.88 halves +2.51/−7.65; SHADOW n=161 −0.195% t=−0.95 +5.71/−18.32 — the grader's phrase for *"mean ≤ 0, more of the same closes cannot flip mean/t/halves"*. **ROW-SCOPED, NOT PROCESS-SCOPED** (the (mr) rule): one module runs both arms, so the 🌊/📊/🧙 idle-the-whole-process shape would have silenced the SHADOW twin — the control arm, still accruing, **kept trading**. **AND IT FLATTENS**, which no prior retirement had to: every earlier one froze PAPER positions, and four REAL directional legs with no manager have no stop and no exit. Rather than write a second idle loop beside real money the guard latches the book's own daily-halt path — already proven to flatten, retry until flat, block entries and heartbeat ((pq)/(pr)/the 16-Jul retry fix). Closes book `long_retired`/`short_retired`, never `daily_loss` (I23: the reason is the record, on the last four trades a real-money book will ever take). The row publishes `extra.retired.{since,why,open,override}` beside `status=halted`, because `halted` is byte-identical between *lost 5% today* and *retired 22-Aug* (I1/I18) and **`open == 0` is the receipt that says the keys may move**. Declared ONCE in `fleet_bus.RETIRED_LIVE_ARMS` — the bot and the 🧪 judge run in different images and cannot import each other, and a second copy of a rule is a second rule; the judge now publishes `phase="stood_down"` instead of silently never promoting (its paired bar needs `live ≥ 10` closes, so a flat arm silenced it correctly and invisibly — I18). ZERO `live.*` levers were open at the retirement, so nothing was stranded; TTL expiry is the release path. Dark-bus rule is **opposite in the two readers, on purpose**: the BOT stands down (a retired real-money book must not resurrect itself on an import error) and the JUDGE keeps judging (the paired bar's own floor already blocks a flat arm). Reversible via `FARMER_LIVE_RETIRED_OVERRIDE=run` **on both services**. Pinned by `tests/autonomy/test_farmer_live_retired.py` (18 tests, 7/7 mutations red). The SHADOW arm is unretired and keeps grading. |
| perps-funding-carry-lshadow | 🌾 Yield Harvester | Lighter shadow. **[30-Jul] `MAX_POSITIONS` 8 -> 12: measured at 7 of 8, i.e. the fleet's BIGGEST EARNER was one slot from full and turning away carries it had already graded. Its 38.8% win rate is not a defect — carry's return lives in the tail.** **[18-Aug (px)] SUPPLY RESTORED + THE MEASURED EXIT, shipped together while the book was EMPTY (flat 5.2d at `eligible 0`): `CARRY_MIN_VOL` 2e6 → 1e6 (34.9d ladder: cell occupancy 5.73% → 13.42%, 3 → 6 coins, all crypto, inside the (it) cage) and `FLIP_GRACE_H` 1h → 6h (the (mf) cell measurement Rich Dad already runs: 1h = 192/231 exits churning the RT, h2 negative; 6h = +$41.17 t=2.96 both halves). Era unchanged (ordinary tuning per (hc)); every future close opens under the new rule. Declared consequence: the gate now reaches Garrett's band on a populated [$1M,$2M)×≥20% sliver — 3-book component DECLARED in `audit_book_overlap.KNOWN_CELL_COLLISIONS`, owner OPERATOR ~12-Sep.** **[18-Aug (qx)] PERSIST 6h → 12h (env `CARRY_PERSIST_H`) — the ONE half (px) parked for the ~30-Aug docket day, shipped early under the operator's queue directive ("implement all operator queue items that make the fleet improve/make more profit and win rate") at the same clean boundary: book flat, census `eligible 0 / waiting 2` at ship (the (px) supply tripwire had NOT fired — recorded). STUDY_FUNDING_LIFECYCLE §4: per-episode net monotone in persistence, P=6 +0.016% → P=12 +0.161% (t=1.80, both halves, referee-reproduced, NOT denominator shrinkage; total net also peaks at P=12), consistent with Hull's independent 24h persist. Hypothesis-grade (n=26, t<2.0), restrict-direction, stated; era unchanged per (hc); caps now PUBLISH `persist_h` (which now differs from Rich Dad's 6h on the shared cell); pinned by `tests/autonomy/test_carry_persistence_gate.py`, 4 mutations red. The ~30-Aug keep-or-retire call is untouched — nothing rides on it any more.** Its HL-data arm (`perps-funding-carry`) is RETIRED 17-Jul — see LIGHTER-ONLY below. **[13-Aug (lk)] CRYPTO PERPS ONLY** — its post-31-Jul era was 9-of-10 losers, every dollar tokenised non-crypto `*_flip`s with fees > accrued (WTI ×4, SKHYNIX ×2, SPCX ×2, −$14.96/9 vs crypto −$0.49/1): a closed underlying market satisfies `PERSIST_H` structurally (I7), so the spike filter cannot protect this class. `_class_ok` screens entries via `fleet_bus.is_crypto`; census gains a `noncrypto` bucket (blocked-by-class-alone, last in gate order); revert `CARRY_ALLOW_NONCRYPTO=1` |
| perps-funding-spread-lshadow | ⚖️ Counterweight | funding L/S book. **[30-Jul] K 5 -> 8 and the universe 30 -> up to 60 via `fleet_bus.scout_universe()`** — ~~measured AT its structural cap (10 open = exactly K=5 x 2 legs) while ranking 15% of the venue~~ **[4-Aug REVERTED to K=5 / universe 30, per the widening's OWN pre-registered criterion** (SIX_BOOKS_BASELINE item 2: *"if n rises and t falls, the wider cross-section is worse than the hand list and the widening should be reverted"*). Measured 4-Aug: in-era t=−0.44 and FALLING from the 0.65 baseline, mean −0.361%/trade, halves +6.19/−9.88, −$16.01 MTM fleet-worst at 16 open (= K=8 × 2, always-in). The K=8/wide config had NO Lighter backtest; K=5 over the hand list is what both validations cleared ((ia): +13.7%, maxDD 9.6%). Operator decision (queue item, option A), shipped as the CODE DEFAULT — no lever was open on the bus, so no lever was hand-set. Era NOT reset (capacity change = ordinary tuning per (hc)); the MTM drawdown bar arms ~7-Aug and closes the (ia) "passes while down $27 MTM" trap from the other side.]
| ~~band-barnes-lshadow~~ | 🎸 Barnesy | **RETIRED 17-Aug (pm): the I17 call on the carry cell, operator decision — ZERO INDEPENDENT EVIDENCE. Measured on its own ledger: 0 of 9 episodes its living carry sleeve ever opened were a coin 🌾 carry was not already holding at that moment (3 coins — SKHYNIXUSD, SPCX, WTI — every one also carry's). Minted as a THREE-sleeve super-book whose thesis was the COMBINATION; two sleeves were already retired ((ly) extreme, (nf) xsect), so what remained was 🌾 carry's own gate (20% TRUE / $2M / 6h / crypto) at a smaller cap (4 vs 12) — I20's one-bet-held-twice, not new edge. All 9 closes are the non-crypto class removed 13-Aug; zero trades since; allocation claim 0.0. Retiring cost NO coverage — carry covers the identical cell with 3× the cap. ZERO open positions, so nothing froze. Guard IDLES the whole process (own module + own service, the 🌊/📊/🧙 shape — never `sys.exit`, which `restartPolicy=always` turns into a crash-loop); both halves shipped; pinned by `tests/autonomy/test_barnes_retired.py` (8 mutations verified). Reversible via `BARNES_RETIRED_OVERRIDE=run`. History below kept per I12.** the FUNDING SUPER-BOOK (5-Aug (jw), operator: "yes build the super bot" — OPERATOR_QUEUE S2 pre-build; first of the Australian-musician cohort).** `lighter_band_barnes_bot.py`, service `band-barnes-shadow`, $1k shadow, ZERO keys. Three sleeves, each a conservative re-expression of a parent's VALIDATED gates, closes tagged `<side>-<sleeve>_<exit>` (direction first — `split_reason` only tags direction-prefixed reasons) so the brain grades sleeves independently: **carry** (🌾's harvest: ≥20% TRUE apr = the 21-Jul sweep winner, 6h persistence, $2M floor, delta-neutral modelled, (gq) decay-paid discipline, $80×4) · **extreme** (💸's shape: top \|TRUE apr\| taken directionally on the receiving side, $10M floor, 10% hard stop — the Farmer's bar, declared in `test_stop_vs_gate`, $40×4) · **xsect** (⚖️ at the VALIDATED K=5 plateau centre, $33 dollar-neutral legs, 24h rebalance over `scout_universe` with venue-direct fallback; no per-leg stop, mirroring the parent's replay-fidelity choice). **The COMBINATION is a NEW policy — fresh 30-day clock ((hm)), nothing inherited from the parents' ledgers, gradeable ~mid-Sep.** Config BIRTH-FROZEN until `BARNES_FREEZE_UNTIL` (2026-09-04, fail-closed on an unparseable stamp): `barnes.{enter_apr,max_positions,k}` are registered (lighter-books, one-sided cages at `lo` — enter_apr may only TIGHTEN, (it)/I19) and `apply_tuning` is wired but REFUSES the rail until the stamp — reach without rule-drift. Birth-complete parity in one commit: claim_writer at loop top + (ic) standby key, funding-form (gr) telemetry + prices on mark sleeves, `snapshot_equity` from day one (`MTM_REQUIRED`), durable hot-streak clock ((iu) `restore_hot_since`), TRUE-apr denomination via `funding_basis` throughout (no legacy thresholds exist in the file), deploy route + `AUTO_IMAGES` + `ROW_ENTRY` + proprioception `BOOK_LEVER_BOTS`. Friction is MODELLED flat-conservative and declared (carry 15bps RT/leg-pair; mark sleeves at-mark + 5bps/side). **[13-Aug (lv)] FIRST SLEEVE-LEVEL GRADE, AND TWO OF THE THREE SLEEVES WERE NOT PRODUCING EVIDENCE AT ALL — corrected in place per I12, because the row above described a three-sleeve book and only ONE sleeve was gradeable.** (1) **`extreme` had never opened a position and could not**: its gate is carry's with a 5× stricter volume floor, off a shared held-set, running SECOND behind a consumer whose cap exceeds the whole supply — offered nothing carry hadn't claimed in **0 of 8,611 snapshots** (I18's subset shape). The reorder is MEASURED AND REFUSED (it yields 12 entries, all non-crypto; zero once class-screened) — **the binding constraint is the $10M floor, which no crypto book has ever cleared at the 20% bar: observed max $5.53M, KAITO.** Its cage `lo` of 5e6 is 90% of that maximum, so lowering it is an operator policy call, escalated not taken. It now publishes its OWN census at its OWN floor (`sleeves.extreme.scan`/`floor_usd`) so `{open: 0}` is no longer byte-identical between "quiet" and "impossible". (2) **the harvest sleeves had NO instrument-class screen** while their own parent does — the `(lj,lk,ll)` sweep class-screened 🌾 and 🎯 the same day and missed this book; 68.2% of carry's offered supply was non-crypto and all 8 of its real closes were WTI/SKHYNIXUSD/SPCX at 0% win. `_class_ok` + `BARNES_ALLOW_NONCRYPTO` now mirror the parent's contract (entry-only, fail-OPEN, `noncrypto` census bucket last in gate order). (3) **the carry sleeve's unit economics do not close on that class**: fixed $0.24 RT friction vs realised accrual of $0.343 across 8 trades — 36% of what entry APR implied — needing a 52h hold at the realised 50.3% effective APR against a 5.46h median. It has fired `flip` 8-of-8 and `decay_paid` never, i.e. only its parent's LOSING exit. **[13-Aug (ly)] THE `extreme` SLEEVE IS RETIRED — the I17 keep-or-retire call, MADE on measurement rather than escalated again.** 🎸 is now a TWO-SLEEVE book (carry + xsect) and its own description says so. Why retire rather than tune: **lowering the floor ALONE is inert at any value ≥ carry's** (the subset relation holds, carry still runs first), and floor+reorder together are undecidable at every reachable setting — $5M (the cage's own `lo`) **0 entries/30d**, $3M **1 entry → 903 days to 30 closes**, $2M **5 → 181 days**, $1M **7 → 129 days** — while both cheap settings take the carry sleeve's supply to **ZERO**, because at the 20% TRUE bar this venue's whole crypto population is KAITO/XMR/PAXG/XRP. **One venue, one harvest sleeve.** The $10M floor was inherited from 💸 the Farmer, where it guarantees REAL fills; here it gated a modelled shadow leg against a supply that never existed. Entry-only (a restored position still exits normally), reversible via `BARNES_EXTREME_RETIRED_OVERRIDE=run`, and **the census KEEPS PUBLISHING beside `retired: true` so the call stays falsifiable** — if venue liquidity ever rises to the bar, `sleeves.extreme.scan.eligible` goes positive and says so. It changes NO trades today (the sleeve never opened one); what it buys is that the next session cannot "fix" the ordering and silently starve carry. Pinned by `tests/autonomy/test_barnes_extreme_retired.py` (AST-shaped, 6 mutations verified) **[15-Aug (nf)] THE `xsect` SLEEVE IS RETIRED TOO — 🎸 is now a ONE-SLEEVE (carry) book.** The X6 attribution (adversarially refereed): xsect was the book's whole burn (−$9.56 of −$11.01; era crypto LONGS at 4.5% win, cluster t=−2.20) while parent ⚖️ rode the SAME window near-flat, and the class screens measurably do NOT repair it. Mechanism differs from extreme's entry gate on purpose: xsect is ALWAYS-IN, so the retired sleeve rebalances TO FLAT — empty targets make its own rebalance (its only exit) wind every leg down at the next 24h cycle; no stranded positions, carry's clock does NOT reset (sleeve-scoped, the (ly) precedent). Census publishes `retired: true`; `BARNES_XSECT_RETIRED_OVERRIDE=run` reverts |
| ~~band-garrett-lshadow~~ | 🛢️ Garrett | **RETIRED 2-Sep (wt): the I17 call on the docket's own verdict — n=85, −1.090%/trade, t=−2.22, upper bound −0.455% ≤ 0 (the sample excluded a positive mean); VARIANT-scoped guard in the Farmer's module, `GARRETT_RETIRED_OVERRIDE=run` reverts; 2 paper positions froze; the carry/Garrett collision keys dropped back to the carry/Rich Dad pair. History below kept per I12.** **the THIN-TIER FUNDING BAND (13-Aug (lp), operator: "build a bot that uses every success instrument and doesn't adopt what currently loses"; second of the Australian-musician cohort).** NOT a new file: a VARIANT INSTANCE of `lighter_funding_bot.py` (`FUNDING_VARIANT=band-garrett`, service `band-garrett-shadow`, $1k shadow, ZERO keys) — one proven machine, every success instrument inherited free (claim_writer+standby, funding-form exit telemetry, (km) bars stamps, snapshot_equity, census, slip/spread vetoes, svc/build stamps). Config IS the fleet's strongest measured UNBUILT claim (STUDY_THIN_TIER_MIN_VOL_2026-08-05): volume band **[1e5, 2e6)** — the tier that measured **+$14.83 both halves, robust at p90** vs the incumbent's +$4.01 — at the study's own cells (gate 0.05 TRUE, $25 clips = file defaults). **Env-only config: a variant reads NO tuning lane** (the judge's `xp.funding.*` collision is the mutation-pinned guard, `tests/autonomy/test_funding_variant.py`), so its (hm) clock is single-policy by construction, no freeze mechanism needed. Fresh 30-day clock from first publish. The pre-registered S4 consensus-directional alternative was MEASURED and REFUTED the same day (retrospective gates on the taker's 42 era closes: survivors −$8.02 vs unfiltered −$4.40 — no gate stack turns a negative signal supply positive). ~~Deploy rule shipped COMMENTED until the operator creates the service~~ **ALIVE 13-Aug (lr)**: service provisioned by dispatched workflow (repo's own token), row publishing with build stamp, auto-deploy rule ACTIVE (corrected in place per I12 the same day the (ls) sweep found the stale clause) |
| book-kiyosaki-lshadow | 🏦 Rich Dad | **the CASH-FLOW DOCTRINE BOOK (13-Aug (ls), operator: "read the book rich dad poor dad by Robert kiyosaki and create a bot from it"; FIRST of the BOOKS cohort — `book-<surname>-lshadow`, named for the AUTHOR; the musician rule keeps governing incubator-earned rows).** `lighter_book_kiyosaki_bot.py`, service `book-kiyosaki-shadow` (ALIVE 13-Aug: provisioned by the (lr)-pattern dispatch, row verified publishing with build stamp `96aac5eae665` = the locally predicted id; the birth also surfaced + closed the (ls) run-scalar-cap incident), $1k shadow, ZERO keys. Kiyosaki's lessons as mechanical rules on the validated carry cell: holds ONLY funding-RECEIVING positions (assets), **delta-neutral MODELLED so P&L is accrued − fees with NO price term** (`position_pnl` takes no mark — structural, selftest-pinned); a position paying funding is a LIABILITY, sold after ~~1h~~ **6h grace ((mf), measured on the cell's own coins: 1h grace = +$26.88/t=1.91 with 192/231 exits churning the RT on sign wobbles; 6h = +$42.09/t=3.00 both halves — Hull's basis-noise doctrine landing on its sibling)** (`liability_flip` — fear guard); decay closes only AFTER payback + margin (`decay_paid`, the fleet's measured best exit — pay yourself first); 6h persistence entry (greed guard); crypto-only per (lk) (`RICHDAD_ALLOW_NONCRYPTO=1` reverts). **The ONE new rule: PAYBACK VELOCITY** — at the entry rate, funding must repay the declared 30bps RT within 120h ⇒ effective bar **~21.9% TRUE**, a TIGHTENING of the validated 20% floor (restrict-only by construction, I19 — admits nothing the 21-Jul sweep didn't validate). Inherited gates otherwise verbatim (20% TRUE / $2M floor / 0.01875 decay / 336h max hold / −2% bleed). $80×6. **Env-only config, NO tuning lane** (the Garrett choice — single-policy (hm) clock by construction; levers are a day-31 decision). Publishes the RDPD income statement every loop (income/expenses/banked + live assets/liabilities split, derived from the exit rule's own flip clock) + a census with `noncrypto` and `slow_payback` buckets. Fresh 30-day clock from first publish, gradeable ~12-Sep. Full reading: `BOOK_KIYOSAKI_RICH_DAD_2026-08-13.md`. NOT encoded, declared: OPM/leverage, discretionary "deal-making", allocation-organ sizing at birth (no claim ⇒ degenerate scale; day-31 candidate) |
| ~~book-douglas-lshadow~~ | 🧘 The Zone | **RETIRED 2-Sep (wt): the I17 call — n=81, −0.725%/trade, t=−2.54, upper bound −0.357% ≤ 0; own module idles, `DOUGLAS_RETIRED_OVERRIDE=run` reverts. History below kept per I12.** **the DISCIPLINE BOOK (13-Aug (mb), operator: "Build me 4 bots for each of these books ... Trading in the Zone — Mark Douglas"; opens the BOOKS cohort's second wave, (mb)–(me)).** `lighter_book_douglas_bot.py`, service `book-douglas-shadow` (**ALIVE 14-Aug (mk)**: provisioned by the one-shot dispatch — four runs; the grep-q/pipefail postmortems are (ml) — row verified on /pnl.json by build stamp, auto-deploy rule ACTIVE and proven by the merge push; corrected in place per I12 the day after the birth-state line was written), $1k shadow, ZERO keys. Douglas supplies no entries — his execution doctrine wraps the edge the tape actually supports, MEASURED FIRST (`scripts/study_books_cohort_2026-08-13.py`, 208d Lighter 1h): fade EXTREME impulses (>2.5×ATR24) with a bracket predefined at entry (sl 1.0×/tp 1.5×ATR, 12h expiry, never widened) — ~~**n=575, +$27.01, both halves positive (+8.80/+18.21)**, t=0.84~~ **[16-Aug (nt), CORRECTED IN PLACE per I12 — those are PRE-(ml) numbers and they overstate: n=641, +$17.38, t=0.50, h1 NEGATIVE (−$7.73/+$25.11).** (ml) taught the replay to bracket-test the ENTRY BAR's post-open range and warned its own recorded numbers "carry that small optimism"; on this book it is not small. Decomposed so the cause is measured, not guessed — on the 13-Aug window (ml) OFF reads n=562 +$31.70 t=1.00 h1=+$14.10 and (ml) ON reads n=630 +$17.90 t=0.52 h1=−$10.45, while 3 days of tape roll contribute ~nothing. **The EDGE survives — still beats random P=0.005 on both metrics — but "both halves positive", one of the six go-live bars, does NOT.** Found by the calibration gate of `scripts/study_leverage_sizing_2026-08-16.py`, which had to reproduce this book before it was allowed to speak about it. RE-MEASURED IN THE SAME PASS so the correction does not leave pre-fix numbers standing in its own paragraph: continuation is **−$248.65, t=−3.05** under (ml) ON (recorded −$210.59/−2.81), and the random-entry benchmark was re-run under (ml) ON — the edge survives at P≈0.005–0.007. The revenge-guard pair (+$27.01 → −$11.32) is PRE-(ml) and un-re-measured; its direction is what the refusal rests on. DECLARED UNEXPLAINED: no cell reproduces n=575/+$27.01 exactly (closest pre-(ml): n=562/+$31.70 and n=574/+$34.02), leaving ~13 trades / ~$4.69 unaccounted, most likely a refetched tape — named rather than absorbed into the (ml) term.**] while impulse CONTINUATION measured −$248.65 t=−3.05 under (ml) ON (the crowd's trade; the mirror is the message). t=0.50 sub-bar, stated — ~92 closes/30d, gradeable ~12-Sep on its OWN ledger, which is the record and outranks any replay (I14). **Consistency is STRUCTURAL**: same $100 clip every trade, `_open_position` takes no streak/outcome/equity input (selftest pins the signature) — and the naive revenge-guard overlay was MEASURED HARMFUL (+$27.01 → −$11.32 with a 4h loss cooldown + streak pause; Douglas's own "the market doesn't know about your last trade" beat my first reading of him). Publishes the rolling 20-trade sample in R-multiples every loop (win rate reported, never a bar — I15). Universe: crypto ≥$1M top 18 off the scout, measured-list fallback, (hk) held union. Env-only, NO tuning lane. Full reading: `BOOK_DOUGLAS_TRADING_IN_THE_ZONE_2026-08-13.md`. NOT encoded, declared: the refuted cooldown, daily-loss halts ((hl) — a shadow halt skips the scan and the exits with it), unsimmed stress vetoes |
| ~~book-grimes-lshadow~~ | 📐 The Technician | **RETIRED 2-Sep (wt): zero closes in 19 days, every setup's gate closed on the fixed universe — a study, not a book (I22); the scorecard survives as `scripts/study_grimes_gate_2026-08-16.py`; `GRIMES_RETIRED_OVERRIDE=run` reverts. History below kept per I12.** **the QUANTIFIED-EDGE BOOK (13-Aug (mc), operator ask; second of the (mb)–(me) wave).** `lighter_book_grimes_bot.py`, service `book-grimes-shadow` (**ALIVE 14-Aug (mk)**, stamp-verified, auto-deploy ACTIVE), $1k shadow, ZERO keys. **TWELVE pre-declared variants of Grimes's structural setups were measured on 500d of Lighter 4h tape and NONE beat random entries** (best: MTF pullback +$84.07 at P=0.24; failtest −$284 t=−2.2) — so the book ships his actual thesis, THE TEST: a setup ROSTER (`pullback`/`failtest`/`keltner`, each ONE code owner shared by live scan and replay) behind a rolling replay gate — every 6h each setup replays over the trailing 120d through the study's exact method, and may ENTER only while its record clears **n≥20, net>$0, t≥+0.5** (fail-CLOSED on a missing/stale scorecard; the full scorecard publishes every loop so `open: 0` is never ambiguous, I18). The gate IS the regime switch, mechanically — ~~born trading exactly ONE setup (keltner t=0.75 OPEN)~~ **[13-Aug (mh), corrected in place: under the honest LAG-1 trend convention (the unlagged map was a replay look-ahead + a missing live key, caught by the birth review) keltner reads t=0.49 — knife-edge below the 0.5 bar — so the book is born trading NOTHING by its own rule, all three gates closed, re-decided every 6h retest with the scorecard public.]** **[14-Aug (ml), the second review pass:** the grader gained the fidelity the first pass missed — `trend_at` returns **None for no-claim** (missing coin/day, junk, EMA warmup) and both trend-gated setups FAIL CLOSED on it (0 used to PASS keltner's both-ways test, so a failed daily fetch unfiltered the fade inside the very replay that gates entries — the (mh) `trend_dark` fix had closed the live site only), and the replay **bracket-tests the ENTRY BAR's post-open range** (entry-bar stops the live loop realises were invisible to the trailing record — optimism in exactly the numbers that hold a losing gate open, at decision-flipping size vs keltner's t=0.49). Both mutation-pinned; mirrored into the study's `run_portfolio`. First live retest (13-Aug 23:51Z): pullback t=0.29 · failtest t=−1.71 · keltner t=−0.05 — all closed, birth state confirmed on live tape.]** **[16-Aug (oe) — RE-MEASURED. THE GATE OPENED BRIEFLY, AND IT IS GOVERNED BY UNIVERSE CHURN AS MUCH AS BY EDGE.** **[20-Aug (ru), CORRECTED IN PLACE per I12 — the headline below is a SNAPSHOT and has not described this book for days. It led with "THE GATE HAS OPENED" while the live scorecard reads all three setups CLOSED: keltner n=123 t=−0.16, failtest n=373 t=−1.43, pullback n=140 t=−0.82. Nothing is broken — this is (om)'s fixed-universe gate working: it grades `GATE_COINS` rather than the churning top-18, and the churn this entry measured is what the +0.53 reading was riding. The book's live scan finds signal and the gate refuses it (`scanned 16 / signal 7 / gated 8 / opened 0`, 0 closes ever). AND THE HAZARD (om) PUBLISHED DID MATERIALISE: `gate_drift.ungraded` is non-empty (AAVE, ADA, TRUMP) — coins the book trades that its own gate never graded — which is why `ungraded_skip` was later shipped to SKIP them (3 skips this loop, matching the 3 ungraded names). Read the (om) paragraph plus that skip as the current state, and this one as the measurement that motivated both.]** The reading at the time: **keltner n=99, t=+0.53, net=+$32.73, `open: TRUE`**; failtest n=305 t=−1.37 and pullback n=128 t=−0.31 both closed. So the book is no longer born-trading-nothing — though `scan` still reads `scanned 10 / quiet 10 / signal 0 / opened 0`, 0 closes, equity exactly $1000. **BUT ON A FIXED 18-COIN UNIVERSE THE BAR IS NEVER CROSSED**: recomputing the trailing-126d keltner scorecard every 3 days across 90 days with the coin set held constant gives t ∈ **[−2.09, +0.09]** and **0 of 31 retests open** — not one crossing. **AND UNIVERSE CHOICE ALONE MOVES `t` BY 3.82**: at a fixed as-of, same rule, same window, resampling only which coins are graded gives t ∈ [−2.55, +1.27] (k=9 opens the gate in 4/12 draws, k=12 in 2/12, k=14 in 0/12, k=16 in 1/12). **The bar is 0.5; the spread from coin selection is 2.5× the bar.** THE BOT IS NOT BUGGY — it replays `resolve_universe()`, the set it will actually trade, on freshly fetched venue bars, which is the defensible choice. But that universe is a top-18-BY-VOLUME ranking, so it CHURNS, and at n≈100 with a true effect near zero the churn dominates: **the gate cannot distinguish "this setup's edge changed" from "the coin list changed", and it is currently OPEN on the second.** The live number is not reproducible offline at any universe/window (18c/126d −0.08 · 18c/120d −0.29 · liquid-9/126d +0.14 · liquid-9/120d −0.11, all CLOSED) because the scout's `vols` differ from `orderBookDetails` — expected, not a defect. **FIXED 16-Aug (om), operator decision, measured first per I19** (`scripts/study_grimes_gate_2026-08-16.py`): the gate now grades **`GATE_COINS`**, the founding study's own fixed 18, while TRADING still follows the live `resolve_universe()`. Four pre-declared candidates were run against BOTH halves of what a fix must do — verdict stability AND the ability to still fire on a real edge (a positive control, because a gate that never opens is trivially stable and useless, I3 applied to a gate): **base 66.7% stable / fires at +0.50%** (the defect) · **FIXED 100% / +0.50% ← shipped** · sub80 100% / +1.00% · win240 100% / +1.00% · tbar10 100% / +1.00%. **The three rejected candidates are stable only because they are HARDER TO OPEN** — each needs twice the edge, which is "raise the bar" in disguise and starves the book toward an I17 retirement; `fixed` is the only one that keeps the shipped gate's sensitivity. THE HAZARD IT CREATES IS PUBLISHED, NOT ASSUMED: grading a set you do not trade. `extra.gate_drift` now reports {graded, traded, overlap, ungraded, untraded} every loop — **`ungraded` non-empty means the book can enter coins its own gate never tested**, the one direction that matters. Pinned by `tests/autonomy/test_grimes_gate_fixed_universe.py` (4 mutations verified RED).** The founding claim is untouched and still governs — none of the twelve variants beat random, which is why the book ships the TEST rather than a setup.]** **`breakout` is structurally ABSENT** — that supply is 🧙 book-schwager's (I20; selftest-pinned exclusion). $80×2, one bet per coin across setups, crypto ≥$1M top 18. The roster COMBINATION is unmeasured as a combination (declared); I17 declared: a gate that stays shut long enough is a keep-or-retire call, never a bar-lowering session. Env-only, NO tuning lane. Full reading: `BOOK_GRIMES_ART_AND_SCIENCE_OF_TA_2026-08-13.md` |
| ~~book-schwager-lshadow~~ | 🧙 The Wizard | **RETIRED 17-Aug (po): the I17 keep-or-retire call, operator decision — UNDECIDABLE BY TAIL, a class beside I17's slow-clock one.** Its founding +$457.21/t=1.88 sits OUTSIDE the whole measurable distribution (90-cell sweep, `t≥2.0` in 0 of 90, full gate in 0 of 90); the top 3 of 298 trades are 112% of the total (drop them: −$17.97, t=−0.13); the random-entry null reads P=0.183; and at the measured mean/sd it needs **~719 closes (~40 MONTHS)** to reach t=2.0 — no amount of waiting fixes a `t` that is a statistic about the tail. **ZERO closed trades in its own ledger** (4 open paper positions FREEZE, the (mr) precedent). Guard IDLES the whole process (own module + own service, the 🌊/📊 shape — never `sys.exit`, which `restartPolicy=always` turns into a crash-loop); both halves shipped (`RETIRED_ROWS` hides, `LEGACY_BOTS` prunes); pinned by `tests/autonomy/test_schwager_retired.py` (6 mutations verified). Reversible via `SCHWAGER_RETIRED_OVERRIDE=run`. **Railway service `book-schwager-shadow` STOPPED 16-Aug 04:58:48Z** (`railway down`, read-back verified: the service's own log ends `Stopping Container` while a peer service logged 2 min later, so the window is current, not stale) — **tidiness, not the retirement**: a push touching `lighter_book_schwager_bot.py` or its Dockerfile auto-resurrects the service ([[railway-autodeploy-resurrects-stopped-services]]), where the code guard idles it. The guard is the durable half; the stop just saves a container. **TWO DOWNSTREAM CONSEQUENCES, named not fixed:** (1) 📐 Grimes structurally EXCLUDES `breakout` because "that supply is 🧙 book-schwager's" (I20, selftest-pinned) — that supply now has NO owner, so the exclusion guards nothing; (2) `(mr)`'s breakout-4h retirement was consoled by "4h breakout lives on in 🧙 book-schwager" — that consolation is now VOID, and `(mr)` still stands on its own evidence (t=−3.50 in-era, BH-significant) which is unaffected. History below kept per I12.** the CUT-LOSSES-RIDE-WINNERS BOOK (13-Aug (md), operator ask; third of the (mb)–(me) wave).** `lighter_book_schwager_bot.py`, service `book-schwager-shadow` (**ALIVE 14-Aug (mk)**, stamp-verified, auto-deploy ACTIVE; booted holding 4 restored positions — the durable-state contract working on day one), $1k shadow, ZERO keys. The wizards' consensus, measured on 500d of Lighter 4h tape: 4h Donchian-20 close breakout + EMA20>50 confirm, initial stop 2×ATR14, then the Seykota rule — a wide **3.5×ATR chandelier trail** from the close-basis HWM (ratchet-only, selftest-pinned monotone), NO profit target, max hold 30d, $80×4 — ~~**n=277, +$457.21, mean +1.65%/trade, t=1.88, both halves positive (+357.90/+99.31), beats random P=0.015**~~ **[16-Aug (nu), RE-MEASURED AND CORRECTED IN PLACE per I12 — THE FOUNDING NUMBER DOES NOT HOLD, on any current measurement.** Honest reading, same rule, current harness, 500d, at the clip this book actually trades ($80 — the published figure is at $100, which it has never used): **n=298, +$146.41, mean +0.614%/trade, t=0.86, h1 +$168.64, h2 −$22.22.** THE EDGE IS **NOT ESTABLISHED** — unproven, not disproven — on three independent grounds: (1) the random-entry null re-run under current code gives **P=0.183** (300 draws; the published P=0.015 was pre-(ml)) and (hm) says a directional book is graded against random, never zero; (2) a block bootstrap on the per-trade mean gives 95% CI **[−0.67%, +2.07%]**, P(mean≤0)=0.11–0.20; (3) **the single best trade is 50.3% of the total and the top 3 of 298 are 112%** — drop them and it reads −$17.97, t=−0.13. WHY THE OLD NUMBER LOOKED BETTER, measured not guessed: the original harness (git 9386537) reproduces **n=277 exactly** at a 13-Aug cutoff but +$361.63, and sweeping ONLY the window-end hour across 12–16 Aug moves the total **$243→$434** (t 1.14→1.79) with n barely moving (273–280) — a few large trail exits falling in or out. +$457.21 sits at/above the top of that range. The tape is NOT the cause (1,500 bars re-fetched, zero revisions). **A 90-CELL SWEEP puts it beyond doubt: +$457.21 sits OUTSIDE the entire measurable distribution** (total −$93.52 to +$404.55, median ~$250; t −0.68 to +1.774, median ~1.20), **`t≥2.0` in 0 of 90 windows and the full go-live gate passes in 0 of 90 at either clip** — `t` is the binding bar in every cell. Worse, **the rule CHANGES SIGN with window LENGTH at a fixed end**: 1500 bars −$93.52 (t=−0.68), 2000 bars −$23.04, 3000 bars +$183.01, 3455 bars +$292.52. The same three long trades — **PUMP +92%, TAO +90%, HYPE +78%** — carry 75–112% of the total in EVERY window; ex-top-3 the rule earns a median **+$0.16/trade** and is NEGATIVE in 4 of 17 cells. Its I16 lower bound (`max(0, mean − 1.28·SE)`) is **exactly 0.000%**. **THE REAL FINDING: this book is UNDECIDABLE BY TAIL, not by rate** — `t` assumes an approximately normal mean, and where 1 trade of 298 is half the P&L the bar cannot resolve the rule at 30 closes or at 298. **Quantified: at the measured mean/sd it needs ~719 closes to reach t=2.0 — ~40 MONTHS at 17.9 closes/30d.** That is squarely I17's undecidability shape, and it makes the nominal ~mid-Oct grading date meaningless. Fat tails are Schwager's own doctrine, so it is the SAMPLE that fails, not the strategy. **NOT RETIRED, deliberately: its own ledger is the record (I14) and it has ZERO closed trades** (4 open, +$3.41 MTM). Retiring on a replay before the record starts is judging by proxy. **Owner: operator — and this is now a live I17 KEEP-OR-RETIRE call, not a tuning question.** The two sides, stated so the decision is a decision: RETIRE because ~40 months to decidability is the 🌊/📊 undecidability shape the fleet has already retired twice, and the I16 claim is 0.000%. KEEP because the ledger is the record (I14), it has ZERO closes so the record has not started, the shape is a validated-in-literature trend edge whose fat tail is the design rather than a defect, and it costs $1k of paper. **Do NOT resolve this by lowering a bar or re-fitting a window.**]** 276/298 exits are the trail (trail 2.5× on the same entries LOSES −$29.88 — the wide trail is the whole edge, and that DIRECTION is unchanged). **THE PYRAMID — the book's most famous rule — MEASURED AND REFUTED: −$292.83 to −$1,103.57 (t=−5.8) in every pyramid cell**; refusal is STRUCTURAL (one position per coin, no add-units path, selftest-pinned), and the daily variant was refused undecidable (2.9 closes/30d — the 🌊 I17 shape). Longs +$129.59 (t=0.93) / shorts +$16.82 (t=0.18) at the $80 clip on the current tape — the long side carries it, and shorts stay ON as the only regime insurance a one-tape validation has (item 18). t=0.86 sub-bar, h2 NEGATIVE, stated; ~17.5 closes/30d, nominally gradeable ~mid-Oct — but see the tail finding above: that date grades a `t` this distribution cannot support. Env-only, NO tuning lane. Full reading: `BOOK_SCHWAGER_MARKET_WIZARDS_2026-08-13.md` |
| book-hull-lshadow | 🧮 The Professor | **the COST-OF-CARRY BOOK (13-Aug (me), operator ask; fourth of the (mb)–(me) wave).** `lighter_book_hull_bot.py`, service `book-hull-shadow` (**ALIVE 14-Aug (mk)**, stamp-verified, auto-deploy ACTIVE; first live census `eligible 0, waiting 4` — the band logic breathing on real fundings), $1k shadow, ZERO keys. Hull's futures machinery on the ONE funding cell no living book enters — **TRUE |apr| ∈ [7.82%, 20%) × vol [$2M, $10M), completing the tiling 🛢️[0.1M,2M) | 🧮[2M,10M) | 💸[10M,∞)** with the 20% ceiling half-open to the carry cohort; both edges PUBLISHED in caps ((gl)); zero rivals, live occupancy LIT/ZEC/PUMP (~10.5% base-rate coins), band populated ~100% of 219 measured days vs the carry cell's 6.6%. Delta-neutral MODELLED (P&L = accrued − fees, `position_pnl` takes no mark — the 🏦 structural pin). **The floor is DERIVED (payback velocity: 30bps RT within 336h ⇒ 7.82% — the no-arbitrage cost band's own edge), and the exit tolerances are THE measurement**: the cohort's 1h flip grace on this band = −$16.84 t=−6.65 with 136/158 exits churning the RT (REFUTED); Hull's ch.-3 basis-noise doctrine (persist 24h, grace 24h) = **n=45 +$4.92 t=+3.27 both halves positive** — a grid PLATEAU, not a lucky cell. **[16-Aug (ny), RE-MEASURED — AND THIS IS THE COHORT BOOK WHOSE FOUNDING NUMBER SURVIVES.** On a tape now 250d the same cell reads **n=50, +$6.69, t=+3.92, halves +$3.17/+$3.53** — better than recorded, both halves positive; the REFUTED grace-1h cell reproduces too (−$18.62 t=−5.95 vs −$16.84 t=−6.65). **(ml) does not touch this book** — `hull_run` is its own funding walk, not the `run_portfolio` bracket walk that corrected 🧘 Douglas and could not reproduce 🧙 Schwager. STRESSED, because t=3.92 on n=50/$6.69 is thin: concentration is LOW and is the mirror image of Schwager's — the best trade is **16%** of the total and dropping it RAISES t to 4.01 (top 3 = 34%, t=3.65); 14 coins contributed, 11 positive; dropping the best coin leaves n=47 +$4.73 t=3.67. Block bootstrap on the per-trade mean: 95% CI **[+$0.065, +$0.204]**, **P(mean≤0)=0.000** at L=1/5/10. Cluster-robust t ((kw)) = 3.92, n_eff 50 — these closes do not batch. **TWO NUMBERS WITHDRAWN, both benign:** (1) the *"random-timing control P=0.000"* is NOT reproducible — **there is no Hull random control in the cited study** (`random_bench` runs for Douglas and Schwager only); an independent construction gives **P≈0.043–0.047**, which still clears 0.05 but is marginal, not overwhelming — quote 0.045 and name the construction. (2) *tier-restricted n=30 +$4.17 t=+2.76* does not reproduce because volume-tier MEMBERSHIP MOVED: only LINK and LIT of the study's 18 sit in [$2M,$10M) today (n=19, +$3.64, t=3.63, still positive). Point-in-time volume is not reconstructable, so that cell is a drifting sensitivity, never a second headline — and note the mismatch runs the safe way: the STUDY sees 18 coins while the BOT scans the whole venue (live census 225 scanned / 121 below band / 28 above / 1 held), so the study is a SUBSET of real supply. **BOT FIDELITY VERIFIED, exactly**: MAX_HOLD_H 504 ✓, clip $80 ✓, cap 4 ✓, APR_HI 0.20 ✓, EXIT_APR 0.035 ✓, STABLE_H/FLIP_GRACE_H 24 ✓, bleed 0.02 ✓, `RT_COST_FRAC`=0.003 selftest-pinned ✓, and the decay rule matches to within a cent despite a different parameterisation (bot `net_if_closed ≥ $0.07` after fees ⇔ accrued ≥ $0.31; study `acc ≥ RT·CLIP·1.3` = $0.312). **THE BINDING BAR HERE IS CLOSES, NOT `t`** — measured 6.0 closes/30d, ~5 months to 30 from a standing start. Unlike 🧙 Schwager this book needs TIME, not a better statistic.]** Adverse-basis entry veto (>10bps against, off the venue's own mark-vs-index; restrict-only, UNMEASURED, declared per I19, fail-OPEN dark). $80×4, crypto-only, env-only, NO tuning lane. **I17 declared at birth: ~4-6 closes/30d — a slow cash-flow clock (~5-7 months to 30 closes)**. Pre-named future collision: the Farmer's min-vol-2e6 judge candidate (~4-Sep) would overlap the band if promoted — the judge's paired bar decides. Full reading: `BOOK_HULL_OPTIONS_FUTURES_DERIVATIVES_2026-08-13.md` |
| band-kelly-lshadow | 🪁 the Mirror | **the MIRROR BOOK (18-Aug, operator: "Make a bot that does the exact opposite of all of the major losing sequences and trends, flipping but also using every enhancement and knowledge we have to ride an uptrend - expansion is the premise"; third of the Australian-musician cohort — Paul Kelly, from little things big things grow).** `lighter_band_kelly_bot.py`, service `band-kelly-shadow` (**ALIVE 18-Aug 22:16Z**, provisioned by the one-shot dispatch under the operator's continue grant; row verified on /pnl.json with `extra.build` byte-equal to the local prediction `5eea92e33277`/n=14 — the readback also reproduced the (ml) stale-reader class LIVE: run 537 printed `OK: pnl-dashboard deployed` while the 11:32Z container kept serving and hid this row for ~30 min; fixed by re-dispatch + readback, and the workflow now VERIFIES the reader's own /watchdog.json boot stamp after any pnl-dashboard deploy), $1k shadow, ZERO keys. **Fidelity pass (18-Aug, pre-first-close so the (hm) clock is untouched): the adaptive gate computes over the ghost's UNSCREENED scan (the gate's percentile is part of the founded policy — screening the scan moved it), the (lk) crypto screen binds at the ENTRY site, confirm counters carry the ghost's exact semantics (no reset on a blind loop or a slip refusal), the ghost's −5% daily halt is declared NOT simulated (it would cap exactly the mirror's winning days; the founded ledger embeds it conservatively), census publishes dev_med/dev_p98 beside the gate. Post-fix stamp prediction `ca78a502378e`/n=14, verified on the activation redeploy's readback.** **[19-Aug (qj) RISK-UP, operator decision inside the pre-first-close window ("risk eliminating job vs profit motivated job — look at options, even though risk will be higher"): $250×4 snap clips (whole book works a storm, ~3.1× $ throughput, same edge), dipfade ADMITTED at $40×2 probe under an ON-THE-RECORD operator override of the I16 floor (n=13, t=−2.66, mirror CI [+0.28%,+2.05%] as a single named candidate; ghost = the taker's vetoed dip lens, bracket drift-pinned against the taker's real constants; own tag `short-dip_*`, dies on its own record), MY-side slip 60bps. The clip jump forced a fidelity catch: the ghost-side event gate now prices at the ghost's OWN $10 clip (at $250 a my-clip check refused events the real ghost took; AST-pinned). Worst-instant ≈ −5.3% (pinned inside the 15% bar); gross ≈ 1.08× equity, declared. Refused with receipts: leverage ((young) 13-of-13), brkfade (P=0.78), stop removal, allocation-scale pre-claim.]** Holds the OPPOSITE side of the fleet's measured losers over exactly the windows the loser would have traded: enter when the ghost enters, hold the other side, exit when the ghost exits — at mark on a zero-fee venue the mirror's per-trade return is the EXACT negation of the ghost's. **THE ROSTER IS MEASURED, NOT ASSUMED** (`scripts/study_band_kelly_2026-08-18.py`, verdict logic pre-declared; STUDY_BAND_KELLY_2026-08-18.md): v1 ships ONE family, **snapfade** — retired 🧲 Snap Back inverted (the fleet's strongest measured loser, t=−2.97 at (jh)): LONG the premium-rich dislocations it shorted (fly high — the majority side, +0.464%/t t=+4.72 crypto), SHORT the discounts it bought (the glide, +0.816%/t t=+3.77). Founding claim crypto-only: **n=65, +0.605%/trade, t=+5.71, both halves and both sides positive, cluster-robust t=+2.84 (n_eff 191), ex-best-coin t=+5.08, win 82% (reported, never a bar — I15)**; median hold 0.09h where the tape's drift term is 861× below the mean — alpha, not beta ((hm) in mirror form). **[19-Aug (qw)/(rc), CORRECTED IN PLACE per I12 — GRADE AGAINST +0.397%, NOT +0.605%.** The claim REPRODUCES EXACTLY from the ghost's own ledger and survives jackknife (60% of trades are KAITO, yet dropping it RAISES the mean to +0.684%/t=+5.08) — the only founding number in the books cohort that held under re-measurement. But naive negation double-counts execution: a realised ledger is already NET of the ghost's own slippage, so `mirror = −ghost_realised − (ghost_slip + mirror_slip)`. Corrected snapfade expectation **+0.397%/trade, t=+3.58** (34% haircut — the ghost's coins were THIN: KAITO $0.42M); corrected dipfade **+1.061%, CI lo +0.20%** (8.7% haircut, liquid taker books) — **the 18-Aug operator override SURVIVES**. Roster membership unchanged; the transferable rule is that a mirror's haircut scales with the GHOST'S coin liquidity, so a thin-book loser's mirror is far less attractive than its negation suggests. Bot's published `roster` now carries `corrected` beside `founding` on both live families, so the ~mid-Sep grade reads the right bar.]** THE GHOST IS THE RETIRED MODULE'S OWN CODE: `lighter_dislocation_bot` imported for gate math + constants frozen at the (jh) retirement config (adaptive p98 gate floored 60bps, 2-loop confirm, 30bps slip gate both ways, conv 40bps, ghost-stop 5% = the mirror's profit-side cover, max-hold 2h, non-convergence embargo) — import identity + no-local-copy AST-pinned (`tests/autonomy/test_band_kelly_mirror.py`, 5 pytest + 7 selftest mutations verified red). **REFUSED WITH EVIDENCE, on the record in `extra.roster` every loop**: `brkfade` (breakout-4h/dad inverted) — the (nt) calibration control killed it: over 578d the MomoBreakout family does NOT lose (+$126, t=+0.90, tail-driven), so its mirror shorts a fat right tail — every stop cell negative, maxDD ~23%, random-short P=0.78; `dipfade` n=13 < 30 (I16 floor), day-31 candidate; impulse-continuation's inversion is 🧘 book-douglas (I20 — not re-taken). Declared deviations, priced: crypto-only screen (CONCENTRATES the edge — ghost's crypto subset t=−5.71 vs −2.82 pooled; revert `KELLY_ALLOW_NONCRYPTO=1`), $80 clips vs the ghost's $10 (%-invariant; census counts slip refusals), own 5% protective stop (`KELLY_HARD_STOP`, the ghost's constant mirrored, in `test_stop_vs_gate.STOPS`). NO regime gate (horizon-mismatched at 5-min holds, unmeasured — I19; "ride the uptrend" IS the measured long side). $80×4, 90s loop (the ghost's cadence), env-only, NO tuning lane, no brain mults, no allocation scale. Fresh 30-day clock from first publish; ~2.8 crypto closes/day on the ghost's ledger → gradeable ~mid-Sep on ITS OWN ledger (I14 — the record decides; the ghost's ledger ended 4-Aug and the forward book is the falsification) |
| ~~nav-cook-lshadow~~ | 🧭 Captain Cook | **RETIRED 2-Sep (wt): the I17 call on the grader's own verdict — `unreachable`, n=38, −0.193%/trade, upper bound −0.020% ≤ 0, the thinnest exclusion on the September slate and still one (every close since the (sa) 600s confirm fix ran the corrected gate); own module idles, `COOK_RETIRED_OVERRIDE=run` reverts. DECLARED: the [45,60)bps band loses its owner — re-opening it is a fresh measurement, never a resurrect. History below kept per I12.** **the CHART-THE-SHALLOWS book (19-Aug (ri), operator: "find a few different horizons and gates that actually work ... named after the likes of captain cook and such"; FIRST of the NAVIGATOR cohort — `nav-<surname>-lshadow`, for the navigators who charted coasts nobody had mapped).** `lighter_nav_cook_bot.py`, service `nav-cook-shadow` (**ALIVE 19-Aug ~09:53Z**: provisioned by the one-shot dispatch; the row was then INVISIBLE for ~1h behind a stale pnl-dashboard reader — the (rj)-predicted (ml) class, because the (rl) deploy freeze had eaten the dashboard's own (rj) redeploy — fixed by a reader catch-up dispatch + boot-stamp readback; row verified CURRENT at HEAD via `audit_code_currency`; decide rule ACTIVE + `AUTO_IMAGES` + provisioner deleted at activation, the (lr)/(mk) pattern; first hour published `status:"running"` and paged NOT-ONLINE — the string came from this file's own publish example, both corrected), $1k shadow, ZERO keys. Mirrors 🧲 the retired dislocation ghost in the residual band **[45,60) bps** — strictly BELOW 🪁 band-kelly's 60bps floor, so the two **TILE** the surface and every event this book takes is one band-kelly REFUSES. That is I20 differentiation by BAND, and it makes the (lv) subset trap structurally unreachable (a DISJOINT band cannot be starved by a consumer running first). **MEASURED FIRST** (`STUDY_DISLOCATION_BAND_2026-08-19.md`, 10,052 scout snapshots 15-Jul→19-Aug at a **5-min cadence**, entry lagged 2 SNAPSHOTS = **600s** (not 2 loops — corrected in place 20-Aug (sa)), episodes not ticks, own slippage charged per tier): **n=216, +0.367%/trade, t=+2.74 at 4h** — and a **PLATEAU**, not a lucky cell: +0.185/+0.274/+0.320/+0.367/+0.405 %/trade at 30m/1h/2h/4h/8h, t=+2.69..+2.97 at every one, **both halves positive at every one**, jackknife by coin t=+1.94..+3.01, block-bootstrap 95% CI **[+0.072%, +0.644%]** P(>0)=0.991, and the **ghost-direction control LOSES at t=−3.53** so the asymmetry is not a sign convention. **The deep tail is REFUSED because it is measured NEGATIVE**: ≥60bps dislocations stop reverting and break (−0.31 to −0.50 %/trade at [150,inf)) — hence a BAND with a ceiling, not a floor ((gl): publish the band, not just the floor). **NOT crypto-screened, deliberately**: the band is non-crypto by nature (commodity +0.566%/t=+2.06 n=57, Asian equity +0.131% n=32, crypto n=4), so its siblings' (lk) screen would leave it four trades; it carries the ONE screen the evidence supports — **pre-IPO EXCLUDED** (−0.165%, n=45, the band's only negative class; restrict-only, fitted on a small sample, declared, `COOK_ALLOW_PREIPO=1` reverts). **THE STALE-REFERENCE HAZARD WAS TESTED, NOT ASSUMED**: the edge concentrates when the underlying market is CLOSED (+0.409%/t=+2.34 vs +0.007%/t=+0.02 open), the exact (lk)/I7 signature — so the index was checked directly and is **NOT frozen** (if it were, d(premium) would track d(mark) 1:1; measured corr/slope BRENTOIL 0.62/0.41, WTI 0.77/0.64, H100 0.06/0.00 — none reaches corr>0.9 AND slope>0.85). Declared: oil's index is PARTIALLY sticky out of hours. $80×4, 4h max hold (the plateau INTERIOR, chosen for decidability at ~1.5 closes/day over the 8h maximum — picking a swept grid's maximum is how (oe)-style artifacts ship; `HORIZON_PLATEAU_S` selftest-pins the shipped hold to a measured cell), **a 600s confirm — CORRECTED IN PLACE 20-Aug (sa), and this line is why the defect shipped.** It read *"2-loop confirm (the lag the measurement was made under)"*, and that was FALSE IN DURATION: the study lagged entry by 2 SNAPSHOTS of a 5-min tape (600s) while the bot inherited the ghost's 2 LOOPS of its own 90s cadence (**180s**), so the live entry gate was **3.3× LOOSER than the one that was graded** — a dislocation had to persist 3 minutes here where the measurement required 10. The daily review measured the consequence in the book's first 10.5 live hours: **24 closes (~55/day vs the study's 6.2/day, ~9×), median hold 5.5 MINUTES against a 4h horizon, 24 of 24 exits `converged`** — the mirror's own LOSING exit, and the recorded cause of death of 🧲 the ghost it mirrors (*"100% converged exits ... the book harvests its own entry gate"*). Live mean **−0.298%/trade, t=−1.88** against a founding **+0.367%**. The confirm bar is now DERIVED from the study's two published facts (`STUDY_SNAPSHOT_S × STUDY_CONFIRM_LAGS`) rather than written as a literal — the literal form was mutation-verified DEFEATABLE by editing the bar itself — and `confirm_s`/`study_confirm_s` publish in `caps` beside the count, because **the count alone is what hid this for a day**. THE GENERAL RULE, and it is the transferable half: **a confirm/persistence window is a DURATION, and inheriting its COUNT from a bot on a different cadence silently re-specifies the gate.** 5% own stop, 30bps entry-slip gate, $0.5M min volume (load-bearing: (qq) measured the fleet's own fills at a MEAN 17.49bps and p90 398bps below $0.1M). Env-only, NO tuning lane — single-policy (hm) clock by construction. Fresh 30-day clock from first publish; gradeable ~mid-Sep on ITS OWN ledger (I14). Closes tagged `<side>-navband_<exit>` so the brain and the winners' docket grade it alone. NOT encoded, declared: the [30,45) band (truncation-marginal at the 8-entry `prem_outliers` cap, and flat), the negative [150,inf) tail, any crypto expression (band-kelly owns crypto by I20), leverage (rejected six times) |
| lighter-perp-sniper-lshadow | 🎯 Perp Sniper | new-listing sniper **+ volume-surge AND young-book candidates (30-Jul)** — SCOPE FIX: `new_listings` is a market-set DIFF, so a symbol qualifies for exactly the ONE loop in which it first appears, and only if the process is running with a warm baseline at that moment. That unobservable trigger, not the thesis, is why the book has n=1 in weeks. `young_candidates()` adds every book in its debut regime. **[30-Jul] the age source is now the venue's OWN `created_at`** — it was on every `orderBookDetails` row all along, in a response the scout already fetches, while the sniper burned 4 candle REST probes/loop to approximate it (measured: majors 558.6d, exactly 4 books under 21d). Scout publishes `ages_d`; the candle probe is the fallback for a dark scout and stops entirely once `ages_d` flows. An unparseable timestamp is ABSENT from `ages_d`, never 0 — "age unknown" must not read as "brand new". **The offered-ledger (`surge_done`) is a COOLDOWN map, not a tombstone**: it was a monotone set, so every book offered once was excluded forever and both new sources decayed to silence over weeks — the same starvation on a longer fuse. `not_young` stays permanent, correctly: books only age — the same phenomenon, observable for WEEKS. Candle probe is GOVERNED (`YOUNG_PROBE_BUDGET`/loop) and MONOTONE (`not_young` is permanent — books only age), so probe cost decays to zero. Plus volume-surge candidates — its event was too rare to grade (n=1 in weeks), so `surge_candidates()` adds books surging >=`SNIPER_SURGE_MULT`x 24h volume. They need their OWN dedup ledger (`surge_done`, persisted): every surging book is already in `baseline`, so baseline cannot dedup this source. **[13-Aug (lk)] surge + young sources are CRYPTO-ONLY** (measured: non-crypto surge −$5.01/13, young −$1.19/2 vs crypto +$1.13/5; every surge close exits `max_hold`, so a surge-long on USDKRW/BOTZ is a timer-held drift bet on an underlying's own market event). ~~LISTING source deliberately unscreened (n=1, unmeasured, founding thesis).~~ **[19-Aug (qi)] CORRECTED IN PLACE per I12 — "unmeasured" is now FALSE, and the founding thesis is REFUTED.** The listing LONG ("listings pop", tp+15/sl−10/6h) was measured retrospectively across every crypto birth the venue's own `created_at` exposes: **TP hit 2 of 73 (2.7%)**, LAG-1 bracket **−0.33%/episode vs an own-coin random null of −0.05% (P=0.707)**, median day-7 debut return **−13.4%**. The real record is n=1 lifetime (UNITREE +$0.28, non-crypto, `max_hold`). **AND THE SUPPLY IS DEAD**: last crypto births RAIL/CTR **85.1 days ago**; 2026 crypto births run Jan–May=16, **Jun–Aug=0**; all 12 lifetime source events were non-crypto and the non-crypto cohort has no edge in either direction (0 of 34 observable brackets hit either leg). So the source is not "waiting for its trigger" — it has nothing to trigger on, and the thesis behind it does not survive contact with the tape. A `wait-then-short` variant measured +6.23%/episode but is **HYPOTHESIS ONLY, never arming evidence**: cluster-by-month t=1.91 (<2.0, the binding statistic), P=0.017 unadjusted ≈0.11 across the ≥7-variant sweep, and uncalibratable (the book's one real close is outside the cohort). A tripwire (≥2 crypto births/month for 2 consecutive months, free from the scout's `ages_d`) may be WATCHED — but firing it re-opens **measurement** on the new wave's own listings,  never a build off this study. Revert `SNIPER_ALLOW_NONCRYPTO=1`. **[20-Aug (tx)] THE WHOLE BOOK RE-MEASURED ON THE OPERATOR'S "restore its lost potency" ASK — AND THE BINDING CONSTRAINT IS THE ENTRY, WHICH IS NOT A LEVER AT ALL.** The predecessor's potency was ONE COIN: ANSEM was **+$325.01 = 157% of the retired Launch Sniper's lifetime +$206.38** (single best row **96.9%**; **ex-ANSEM −$118.63 over 363 closes**; top-3 = 157.5%, worse than 🧙 Schwager's 112% at (po)) — and its famous convex exit is NOT the earner: the ladder **cost −$126.29 on ANSEM** vs the all-or-nothing rule it replaced, the **trail is 0-for-4 at −$33.11**, and the far TP fired **once in 361 episodes**. Replayed on THIS book the predecessor's exact constants are **byte-identical to a bare timer (Δ=$0.00 at 24/48/72h, zero fires)** because its triggers are unreachable: of 32 positions, 72h MFE ≥+50% **0**, ≥+100% **0**, ≥+400% **0**, vs 8 of the predecessor's 366 closes ≥+100%. **The supply, not the exit rule, is the whole difference (I7).** **The entries carry no information**: exit-free paired rank test vs 300 matched-random minutes on the same coin/window puts the sniper's chosen minute at percentile **0.484/0.517/0.500/0.511/0.515** at 0.25/1/3/6/12h (|t vs 0.5| ≤ 0.61), and `surge` — the only living source — reads **0.429 at the shipped 6h hold, worse than random**; the entry selects VOLATILITY (P=0.009) and not DIRECTION (P=0.406). **REFUSED with numbers, so no future session re-proposes them:** the scale-out ladder and trail (inert, and mechanically unshippable — no partial-close primitive at any of 3 broker layers, and two ledger rows sharing `opened_at` set `integrity.two_writers=true`, permanently blocking READY and starting a false page every cycle); any TP retune (**0 of 367 cells survive BH at FDR 0.05** — smallest p=0.0478 vs a 0.000136 critical value; every TP <5% negative); holding longer (a **content-free timer wins at 72h**, grid-edge unbounded — (hl) shrinkage); a clip raise (I16 lower bound **0.000**, already at the 25% probe floor); loosening the surge bar (**400–800× supply at −0.04 to −0.05%/trade ≈ the null**); and registering the bracket as levers (I18's own refutation — reach with no direction to walk in). **A NEW UNDECIDABILITY CLASS — UNDECIDABLE BY CEILING**, beside I17's slow clock and (po)'s fat tail: a perfect-hindsight exit selling at the exact 6h high yields **+1.80pp/trade** of excess over the null, while the book's own published `mde80_pct` is **2.114%/trade** — *the entire distance between the shipped rule and omniscience is smaller than the smallest effect this book could ever prove*. On the only living source, t=2.0 needs **415 closes ≈ 2.7–3.2 years**. **SHIPPED: the per-source census** (`extra.sources.{listing,surge,young}` — `scan` liveness verdict FIRST (I1), then one counter per gate stage, filled BY the admission functions so it cannot drift from the gate ((hj)); the first zero in gate order names the killing gate). It exists because the `listing` source has had **ZERO crypto supply for 86 days** and `young` has been **EMPTY for 66 days** while the row published `watching: 212` and nothing per source — the (lv) `{admitted: 0}` ambiguity. Publish-only, era NOT reset; pinned by `tests/autonomy/test_sniper_source_census.py`, 9 mutations red. **DECLARED, NOT CHANGED:** the (lk) screen tests `strategy_index == 2` but the venue files every memecoin debut under **class 7**, so **ANSEM is listed on Lighter today and is screened out of both surge and young** — unblocking is REFUSED (class-7 surge **−0.840%/trade @6h**; the debut cell is n=9 with top-1 = **132%** of the total). **[20-Aug (tz)] THE RETIRE RECOMMENDATION IS WITHDRAWN — it rested on two numbers that were themselves defective, and BOTH have been corrected.** `(tx)` escalated a keep-or-retire call citing horizon `unreachable` and an I16 claim of 0.000. Neither survives its own fix: the horizon's `unreachable` had **no power gate** and fired on `mean <= 0` at any n — this book's upper bound is **+0.814%**, so its sample had excluded nothing and it now reads **`underpowered`**, off the retirement docket entirely; and the claim of 0.000 was the winner-take-all split's floor, which read 0.000 for **every book in the fleet** including ones at +4.66%/trade. **Eamon, 20-Aug: "Keep the books ... instead of finding a way to kill something you find a way to feed it."** The book is KEPT and FED — the `(ty)` screen fix gave its young source ~1.7-2.0 candidates/30d back after 66 days at zero, and the `(tz)` split takes it from the 25% probe floor to ~0.96x. What remains true and unchanged is the honest limit: its entries carry no measurable directional information, and its own `mde80` (2.114%/trade) exceeds the entire perfect-hindsight ceiling (+1.80pp) — so the right expectation is a book that is CHEAP and OBSERVABLE, not one about to earn. Do NOT resolve that by lowering a bar or re-fitting a window either. Revival tripwire (free from the scout's `ages_d`, now visible in the census): **≥2 crypto births/month for 2 consecutive months** re-opens MEASUREMENT, never a build. Full working: `STUDY_SNIPER_EXIT_SHAPE_2026-08-20.md`; instrument `scripts/study_sniper_exit_shape_2026-08-20.py`, which **REFUSES** (calibration gap +0.334pp vs 0.15pp tol, 0 of 6 bases) — if someone later widens `SNIPER_CALIB_TOL_PP` to make it speak, that is the defect. **[20-Aug (ty)] THE SUPPLY WAS NEVER DEAD — IT WAS SCREENED OUT, and this row's own "86 days dry" figure is CORRECTED IN PLACE per I12.** That number is true of `strategy_index == 2` and FALSE of the cohort this book trades: on the **venue-priced** axis births have not stopped in any month measured — **1.67–2.00/30d**, CAP (Jun), ANSEM (Jul), CASHCAT (Aug) — and every one is class 7, so every one was refused. `(lk)` put ONE screen on surge AND young on evidence that was almost entirely surge's (non-crypto surge −$5.01/13 vs non-crypto **young −$1.19/2** — the young leg rested on **n=2**), and `is_crypto` asks a question the venue's class-7 grab-bag cannot answer: it holds crypto-native memecoins (ANSEM, CASHCAT) beside tokenised pre-IPO (ANTHROPIC, OPENAI, SPCX) and a bond yield (US10Y). **Measured live: the young cohort was 7 books, five zero-volume ghosts, and the only two with turnover — CASHCAT $0.45M, UNITREE $0.84M — were the only two refused.** SHIPPED: the young source now asks **`fleet_bus.venue_priced`** (the axis (lk) was really arguing — "already priced where the underlying trades"), surge UNCHANGED at `is_crypto`; live gate goes `class_ok=0 → 2`, admitting CASHCAT. The kept half of (lk) is now better evidenced than the dropped half: shorting an externally-priced debut reads **−0.457%/trade, t=−2.38**, the only significant cell in the study. **Expectancy price STATED (I19): the admitted cell is −0.174%/trade at t=−0.52 ≈ −$0.17/month on a $20 clip — bought as DECIDABILITY, not edge, because a source at zero admissions can never be graded or retired on its own record.** **REFUSED with numbers:** the direction flip (young SHORT reads +1.369%/t=1.33 @72h and +1.513%/t=1.31 @168h with both halves and 15–16% concentration — and the (hm) null KILLS it, **P(random ≥ observed) = 0.573/0.577**; a random entry minute beats the sniper); the longer hold (at 168h a content-free timer beats the bracket); and the volume floor move to $0.10M (the slippage model's tier is a step at $0.1M, so it cannot price the band the widening admits — (qq)'s ~30–95bps exceeds the 0.125pp apparent gain). Floor stays $0.25M. Reverts: `SNIPER_YOUNG_ALLOW_ANY=1` (young only) or `SNIPER_ALLOW_NONCRYPTO=1` (both). Pinned by `tests/autonomy/test_sniper_young_supply.py`, 8 mutations red.  **[26-Aug (ub)] THE BOOK WAS ON THE WRONG SIDE OF ITS OWN THESIS — the SIDE FLIP STANDS, its JUSTIFICATION DOES NOT, and both are recorded because the second half was refuted hours after the first shipped.** Eamon, 26-Aug: *"let listing sniper fly like it used to."* It flew as `listing_sniper.py` sniping SPOT listings across ~100 CEXes, where a fresh listing is a BUYING event; this book snipes PERP listings on ONE venue, and **a perp lists AFTER the spot hype**. THE SHIPPED CHANGE: `listing`+`young` flip to **SHORT at a 24h hold** (`surge` untouched — a volume event on a mostly-mature book, and applying one source's evidence to another's cell is the (lk) error this book already paid for); young volume floor **0.25 → 0.20**. **THE "DEBUT FADE" THAT JUSTIFIED IT IS 76-83% CALENDAR, CORRECTED IN PLACE per I12** after an adversarial review (5 lenses + code review + second opinions + a calibrated referee). The published controls were called *"paired within coin so market drift cannot produce them"* — **false as written**: the pairing is within coin but ACROSS TIME, and Lighter's listings CLUSTER (13-19 books/month Jul-Sep 2025, ~1/month since). **11 of the 45 "debuts" share ONE birth instant — the venue's own opening — and are BTC, ETH, SOL, XRP, DOGE, LINK, AVAX, POL, NEAR, TAO, GRAM, assets with no debut at all**; outside them the headline cell CHANGES SIGN (8-21d@24h: launch batch −1.953% pooled t=−17.83, other 34 **+0.056%**). Coin+calendar-week fixed effects put the age dummy at **−0.09 to −0.15%/24h (t=−0.28 to −0.47)** vs a raw −0.56 to −0.62. The gradient `t`s quoted (−2.47/−2.70/−7.47) were the **POOLED** column; **by coin 0 of 10 cells reach |t|=2**. The mature control is flat only in ITS OWN window — the same coins shorted at the young coins' calendar hours return **+0.125%/trade, t=+3.28**. 39-40% of the young sample can NEVER be controlled (no book older than 60d existed in Jan-Feb 2025). **WHY THE TRADE STANDS ANYWAY, on the counterfactual nobody had run:** matched-null excess is **LONG@6h −0.027% (t=−0.39)** vs **SHORT@24h +0.157% (t=+0.83)** — SHORT measures better on every convention including market-neutral (+0.343pp/trade at fixed hold), but **neither leg is distinguishable from zero**: a better-pointed coin flip, not an edge, exactly as (tx) already found for this book's entries. **SHORT@6h (+0.132%, t=+2.69) is WITHDRAWN outright** (matched-null +0.019%, t=+0.34) — never cite it. DECLARED ADVERSE: the evidence contains **zero books of the kind these sources admit** (cohort's youngest is 202d; ANSEM 28d and CASHCAT 20d, the only 2026 debuts and the only two `young` can admit, are excluded and read SHORT@24h **−3.305%/−1.572%**); the floor move admits ANSEM, **the worst book in the data for the trade the same commit shipped**; recency decays through the bar (+0.695% → +0.377% → +0.364%); and `listing` enters at age ~0 where the calendar-matched excess is **POSITIVE (+0.694%/24h)**, so its flip is **hypothesis-grade** ((qi): never arming evidence). Decidability: ~63-93 coins for by-coin t=2 ⇒ **~9-29 months**. The 24h hold quadruples item-18 regime exposure per trade. **FOUR CODE DEFECTS the same review found, all fixed and mutation-pinned:** the `held` map reported a SHORT as a LONG whenever `entry_src` was lost (it read the SOURCE; the entry's own bullet claimed this was the fix and it was the defect); **the guard written for it was VACUOUS** — a substring check for `side_is_long` that a hard-coded `side_is_long(None)` satisfies, beside a fixture holding only long positions; a `young`/`surge` candidate that missed its first snipe was **ENTOMBED** (cooldown stamped at OFFER, so a one-sided debut — the most likely state for a new perp — was excluded forever and never even given up, silently spending the supply (ty) restored); and the documented one-env revert `SNIPER_DIRECTION=long` landed on **LONG@24h**, a cell the book has never run and 5.3× worse raw than the LONG@6h it claims to restore. Era NOT reset (flipped sources contributed ≤1 of 36 closes; closes are side+source stamped). THE HONEST LIMIT, unchanged and still an operator decision: venue-priced crypto births/month ran **13, 19, 12, 6, 4, 2, 7, 9, 4, 1, 6, 1, 1, 1** — the predecessor hunted ~100 exchanges, this one hunts a venue listing ONE book a month. Reverts: `SNIPER_DIRECTION=long` (whole book, now restores the 6h hold too) or `SNIPER_SIDE_<SOURCE>`/`SNIPER_HOLD_H_<SOURCE>`. Instrument `scripts/study_sniper_debut_fade_2026-08-26.py`; pinned by `tests/autonomy/test_sniper_per_source_side.py`. Full working: `STUDY_SNIPER_DEBUT_DIRECTION_2026-08-20.md` **[26-Aug (uf)] THE ONE THING (ub) LEFT OPEN IS CLOSED, AND THE ANSWER IS NEITHER SIDE — `listing` HAS NO MEASURED SIDE ON ITS OWN BAND.** (ub) flipped `listing` and `young` together on a number computed across BOTH debut bands and said so. Measured separately on `listing`'s own **0-7d** band, through the book's OWN bracket, against a **calendar-matched** control (same bracket/side/calendar hour on every coin ≥60d mature, entry coin excluded), by-coin: **LONG −0.036% (t=−0.07) · SHORT +0.123% (t=+0.29)** — neither. Three things settle it: the sign **flips with horizon** (LONG wins at 6h and 72h; SHORT only at the shipped 24h — the (oe) artifact signature); the raw +0.663% by-coin signal **does not survive the bracket** (→ −0.036%; exits `max_hold` 75% / `sl` 17% / `tp` 9% — (ml)'s rule that a mean says nothing about what a bracket books); and **the pooled t=+4.05 is a sampling-STRIDE artifact** — sweeping only the stride 1/3/6/12/24 takes pooled t **3.98 → 0.36** while by-coin t holds at ~0.6, and at stride 24 with a 24h hold (non-overlapping) pooled SE **equals** by-coin SE. **Pooled t over overlapping windows measures sampling density, not edge** — the (kw)/(ky) cluster-robust lesson in a REPLAY, where the sampling rate is a free parameter the analyst picks. The literal listing trade (one entry per coin at its first bar, n=**24**) reads +0.900% t=+0.57 and fails everything: sign test 13/24 (p=0.84), top-3 = **224%** of the total, **ex-top-3 it LOSES −1.276%**, bootstrap CI [−2.010%, +4.070%]. **The short's evidence lives in the 8-21d band — `young`'s, not `listing`'s** (LONG −0.374% t=−2.67; the short itself is only t=+1.47). Validated before use: positive control recovers a planted ±2%/24h drift in both directions, placebo on mature-vs-mature returns zero, and it reconciles to (ub)'s referee. Bonus that settles (ub)'s calendar worry structurally: the 11 launch-instant coins have **ZERO control coverage** (no coin was 60d mature in Jan-2025), so with/without-launch excess numbers are **byte-identical** — the contamination never reaches the matched estimate. **NOT re-flipped to LONG** (unsupported too — swapping one unsupported side for another is motion, not growth); `listing` stays SHORT and stays hypothesis-grade. **SHIPPED: `extra.dir_basis_by_src`** — `young`=**measured** ((ty)'s −0.457%/trade t=−2.38, corroborated above), `listing`=**unsupported**, `surge`=**unsupported** ((tx): percentile 0.429 at its 6h hold, worse than random). REPORTED, never a gate (I15): `dir_by_src` published two `short`s in the same shape while only one was measured, and no reader could tell them apart. |
| lighter-dislocation-lshadow | 🧲 Snap Back | **RETIRED 4-Aug (jh): the fleet's only statistically significant LOSER — t=−2.97, n=175, mean −0.281%/trade, BOTH halves negative (−$2.48/−$2.56), ~−$1/day, 100% `converged` exits since the widening (the book harvests its own entry gate), and the growth rail structurally cannot restrict it: the binding entry floor `ENTER_FLOOR_MULT` is an unregistered bare literal (I18) while every reachable lever motion loosens. Operator decision (OPERATOR_QUEUE.md item 2, option A). Guard first, then both halves (hidden + pruned); reversible via `SNAPBACK_RETIRED_OVERRIDE`. Railway service stop (`snap-back-shadow`) is the operator's separate act. History below kept per I12.** dislocation fader — reference is LIGHTER'S OWN `index_price` since 17-Jul (was Hyperliquid mids). **[30-Jul] the entry gate is now a PERCENTILE of the live residual distribution (`adaptive_enter_bps`), not a fixed 150bps — that constant was ~40x its own median residual (3.8bps) and predates the switch off Hyperliquid's mid. FLOORED at `EXIT_BPS * 1.5` and CAPPED at the operator constant: on today's tape the floor usually binds, so the practical effect is 150 -> ~60bps, not "the gate follows the median down". Universe 16 -> up to 40.**
| lighter-ticket-taker-lshadow | 🎫 Ticket Taker | **trades Lighter Scout's high-conviction tickets** (breakout/dip/momentum long + divergence long/short); stress veto pauses entries at venue |prem| med ≥15bps; closes tagged `<side>-<lens>_<exit>` so the brain grades each lens. **[30-Jul (hj)] THE SHADOW ARM TAKING LONGS IS CORRECT — the LIVE arm is now divergence-SHORT-only by HARD GATE.** `allowed_lenses` (live = divergence only, since 17-Jul) was only half the real-money rule: the SIDE restriction lived solely inside `if BULL_MODE:`, and `TT_BULL_MODE` defaults to **off**. Measured: the live row has 25 closes and **12 are `long-divergence`** (last 24-Jul); what stopped them was that env var being flipped on, not a gate. `LIVE_SIDES`/`allowed_sides(mode, lens)` is the fail-CLOSED twin — reads no env, no bus, independent of BULL_MODE; belt in the entry loop, braces at `market_open` checked against `is_long`. A lens with no `LIVE_SIDES` entry fills NOTHING live, so real money on a new lens is two explicit edits. Shadow keeps BOTH sides — that grade is what justifies the live rule. `policy.sides` is stamped on every close so graders can era-split the change. **[13-Aug (lj)] the realised lens veto is ERA-SCOPED**: `realised_lens_evidence(policy=current_policy())` grades only same-policy-stamped closes (scoped-preferred, pooled-fallback below `REALISED_MIN_N` so standing vetoes like dip never fall to the proxy) — 13 pre-30-Jul rows had been holding the LIVE arm's veto open at t=−0.83 while its own era read t=−1.75 and the trailing 8d −2.456%/trade |
| equities-regime-lshadow | 📊 Index Rider | **RETIRED 13-Aug (lo): the I17 keep-or-retire call was MADE — operator, "get rid of what's not working". ZERO closes in 44 days (3 buys / 0 sells ever), measured rule rate ~17.2 closes/yr vs the 30-close gate bar: structurally undecidable. Held +$13.93 open MTM at retirement (marks, not evidence). Row hidden + pruned (both halves); reversible via `INDEX_RIDER_RETIRED_OVERRIDE`. Item-18 regime coverage now rides the family books' non-crypto universe + per-asset oracle, not this row. History below kept per I12.** stock-perp port (IBKR original RETIRED 14-Jul). **[30-Jul] universe 3 -> 10 (the venue's full non-crypto set, same books the family per-asset gate grades) and clip $250 -> $100 — it carried the LARGEST clip in the fleet on a book with ZERO closed trades. These are the fleet's only source of a regime that is not falling-BTC (SPY +8.1%, QQQ +12.2%, WTI +23.0% over the same window), which is what item 18 needs.** **[30-Jul (hk)] TWO CORRECTIONS TO THAT WIDENING.** (1) **XAG REMOVED** — `(fz)` shipped it under `sma_cross` while this file's own reject list, 25 lines above `SLEEVES`, said *"don't re-test: XAG (+1.2% regime / 55% DD cross)"*, naming the very rule it shipped under; an independent 2y measure corroborates 38.7% maxDD. WTI/XCU STAY but are now DECLARED in `SLEEVE_EXEMPT` (their notes quote regime200; they ship as `sma_cross`, untested by that sweep) and owe a Lighter-tape backtest. The list is machine-readable now (`REJECTED_SLEEVES`) and `_selftest_sleeves()` fails the build on an undeclared re-add. (2) **A short series returned a false FLAT** — `sma()` gives None and every rule mapped it to 0, so "no data" was byte-identical to "downtrend" across 7 of 10 sleeves. `want_position` now returns **None** (no entry AND no exit — the catastrophic stop runs ahead of it), and the row publishes `bars` per sleeve. Zero closes here is CORRECT: 3 buys / 0 sells ever, SPY 5.1% from its exit band, and the rule measures 17.2 closes/yr. **[30-Jul (hl)] THE (fz) WIDENING BROKE THE 15% DRAWDOWN BAR AND NOBODY GRADED IT.** Measured through `golive_readiness.stats()` itself, 10y, both lags: 9 sleeves x $100 = maxDD **21.60%/23.88%**, `bar_map` maxdd=False; the pre-(fz) 3-sleeve book passed at 3.45%/4.24%. Fixed by the CLIP (**$100 -> $65**, the largest clearing 15%), because per-trade %% is INVARIANT to clip so it costs zero expectancy — capping concurrency instead would reach 14.85%% only by giving up 79 closes, 58%% of realised P&L and 2.3pp of mean per trade, and because the entry loop iterates SYMBOLS in order with incumbents holding slots it would starve the LAST-listed diversifiers and RAISE correlation. `MAX_OPEN` is now a LITERAL (9): as `len(SYMBOLS)` it could never bind AND it was the one lever `audit_lever_bounds` had to blind itself to via `DRIFT_OK` — where it had already drifted (registry 10 vs code 9). That exemption is deleted. **The single-name class is machine-readable now** (54 symbols in `REJECTED_SLEEVES`) after shipping through the prose three times; NVDA/TSLA/MSTR are GRANDFATHERED in `SLEEVE_EXEMPT`, named FIRST TO DROP, and a fourth turns the build red. Publishes `ref_date` per sleeve — `bars` reads 501-504 whether Yahoo advanced today or froze a fortnight ago. NOT wired to `scout_universe` — its signal is Yahoo equity dailies, so a scout-added book without a verified `YAHOO_REF` publishes nulls. 🏆 Stock Leaders (`equities-momentum{,-lshadow}`) RETIRED 17-Jul — maxDD 37-44% vs the 15% go-live gate |
| pm-{albanese,turnbull}-lshadow | 🏛️ the Parliament | six-layer self-evolving shadow fleet (21-Jul, operator ask; named for the last 8 Australian PMs — the other two are its organs: Keating 🔭 scanners+ML, Howard 🧠 ecosystem brain). `parliament_main.py` in the freqtrade-bots container; SQLite ecosystem DB on the persist volume; consumes scout stress + L2 veto + brain mults; closes tagged per lens; `PARLIAMENT_ENABLED=0` idles it. **FOUR OF SIX BOOKS RETIRED 15-Aug (nf)** — the red-stop slate, on the docket's own `unreachable` verdicts: gillard (n=304, t=−1.85; its sl class −$28 @ 0% win), abbott (n=82, t=−2.06), rudd (n=99), morrison (n=24) — all at zero open positions. Declared once in `parliament.PM_RETIRED`, every builder derives via `live_pm_bots()` (the (mo) pattern, AST-pinned); `PM_<NAME>_RETIRED_OVERRIDE=run` reverts each. Albanese (+$1.83) and Turnbull (positive-undecidable) keep trading |

### LIGHTER-ONLY (17-Jul, operator: "i only want things running on lighter")
LIGHTER-FIRST governed SERVICES since 14-Jul, but five rows were still TRADING
elsewhere. All stops are CODE GUARDS, not `railway down` (auto-deploy
resurrects stopped services on every git push). Guards print WHY, keep every
ledger, don't break `--selftest`, and are reversible by env var. Rows are in
BOTH `RETIRED_ROWS` (hides) and `LEGACY_BOTS` (prunes).

**Two different mechanisms — don't conflate them:**
- The four BOTS **IDLE** at boot (`while True: sleep`), never `sys.exit`, because
  `restartPolicy=always` turns an exit into a permanent crash-loop (the Trail
  Blazer pattern, `hyperliquid_momo_bot.py` 15-Jul).
- **funding-carry does NOT idle**: it `raise SystemExit`s unless
  `VENUE=lighter_shadow`. It was pinned `VENUE=hl_paper`, exit-looping LOUD (by
  design — not a silent row that just stops moving) until the operator flipped
  the env var. **[22-Jul (ci): DONE — `railway variables --service
  funding-carry` now reads `VENUE=lighter_shadow`; the row runs its Lighter
  shadow arm and no longer exit-loops. No operator action outstanding.]**

| Row (retired) | File | Was trading | Resurrect with |
|---|---|---|---|
| event-listing-sniper 🎯 Launch Sniper | `listing_sniper.py` | spot on ~100 CCXT exchanges | `LISTING_SNIPER_OVERRIDE=run` |
| scanner-cross-exchange-arb 🔀 Gap Scout | `cross_exchange_arb.py` | arb BETWEEN Kraken/Binance/Coinbase | `GAPSCOUT_RETIRED_OVERRIDE=run` |
| scanner-triangular-arb | `triangular_arb.py` | Kraken | `ARB_RETIRED_OVERRIDE=run` |
| perps-rsi-meanrev 🪃 Bounce Catcher | `hyperliquid_perps_bot.py` | Hyperliquid | `PERPS_RETIRED_OVERRIDE=run` |
| perps-funding-carry 🌾 (HL arm only) | `funding_carry_bot.py` | `VENUE=hl_paper` | ✅ DONE 22-Jul — service now `VENUE=lighter_shadow` |

- **The Launch Sniper was the one nobody switched off.** `lighter_perp_sniper.py`
  was built 9-Jul *"to replace the spot sniper (which can't run on a fixed-market
  perps venue)"* — the replacement shipped, the predecessor kept trading ~100
  CEXes for 8 more days behind a row that was never even hidden.
- **Gap Scout could not be MOVED, only stopped** — its trade was CEX↔CEX arb and
  you cannot arb one venue against itself (its own source: "The CEX legs above
  say nothing about Lighter"). Its Lighter-premium job moved to
  `lighter_market_scout` (every liquid book vs its 6-symbol `LIGHTER_WATCH`);
  `fleet_risk` now mirrors the bus premium from bot_state `lighter-market`.
- **Snap Back COULD be moved and was**: `hl_mids()` → Lighter's own
  `index_price`. Measured 17-Jul: the two agree to a median 3.8 bps (vs a 150 bps
  entry gate) but the index residual is systematically tighter — `book/hl_mid − 1`
  was charging Lighter for Hyperliquid's basis.
- Still non-Lighter and DELIBERATELY kept: `compile_market_data.py` (Binance/
  CoinGecko/Kraken prices for the DASHBOARD's display — not a trader).
- Guards bite on each service's NEXT DEPLOY. `hyperliquid_momo_bot.py`
  (Trail Blazer) was already guarded 15-Jul.

### Intelligence layer (main freqtrade-bots container, run_all.sh loops)
- `lighter_market_scout.py` 🛰️ — ALL ~215 Lighter books: premium stress,
  liquid funding extremes, cross-venue funding divergence, vol/OI moves,
  listings, **per-strategy tickets** → bot_state `lighter-market`.
  **[30-Jul] `TICKET_TOP_N` 6 → 12** — `strategy_tickets` truncates EVERY lens
  to this number, and on the live bus `dip` and `divergence` both returned
  EXACTLY 6 (breakout/momentum returned 5); a lens returning exactly its cap
  is a lens whose cap binds. The lens behind it is the fleet's only measured
  alpha — **RETRACTED: (gi) found a THIRD era-pooling error; the shadow arm's
  10 closes span FOUR bar-sets, and the only clean single-policy sample is the
  LIVE arm's 11 closes at +0.883%/trade, t=+0.73, 95% CI straddling zero. The
  cap-binding fact stands and the widening stands, but the rationale is now
  MORE SAMPLE FOR AN UNDECIDED LENS, not feeding a proven winner** — and
  it was being handed a 6-wide list from which to fill 4 slots. Every "closed
  question" on the Taker (`TT_MAX_OPEN`, `TT_DIV_GAP`, lens on/off, clip size,
  symbol eligibility) was about ALLOCATING that fixed supply; **none was about
  ENLARGING it.** Widening changes no entry bar — the taker's gates still judge
  every ticket. Also publishes **`vols`** (public per-symbol 24h $M), the field
  behind `fleet_bus.scout_universe()`
- **[2026-07-30 THE BRAIN'S FEE BASIS WAS CORRUPTING ITS DIAGNOSES — read
  before touching `FEE_RT`.]** Three defects compounded: (1) `FEE_RT.get(bot,
  ...)` was called with the SUFFIXED row name while every key is a BARE base,
  so not one entry ever matched and every bot took the default — the identical
  defect the 23-Jul audit fixed for `ERA_START`, five lines away in the same
  function; (2) that default, `0.0052`, is **Kraken SPOT** taker round trip,
  and Kraken retired 14-Jul; (3) **Lighter is zero-fee, MEASURED** — all 203
  active books report `taker_fee 0.0000`/`maker_fee 0.0000`. So the phantom
  cost was the whole estimate. **The damage was not a mis-report:**
  `diagnose()` rule 3 fires at `fee_rt/med_loser >= 0.5` with
  `med_loser <= 0.012` and RETURNS, so at 0.0052 ANY bucket whose median loser
  is ≤1.04% was called `fee_bleed` — pre-empting rule 4 `regime_timing`, the
  ONLY diagnosis kind carrying an actuator (`regime_gate`). The brain could
  not recommend the one thing it can act on. **Fixed so it cannot recur:** the
  fee is MEASURED, not asserted — the scout publishes the venue's own schedule
  (`lighter-market.fees`, max across active books) and `bot_learn.fee_rt_for()`
  is the single owner that prefers it. Note `is_taker_fee_enabled` is TRUE on
  every book with the rate at zero, so the rate CAN change and a hardcoded 0.0
  would be this same mistake mirrored; a dark scout falls back to a declared
  per-venue constant, never another venue's. `tests/autonomy/
  test_brain_fee_basis.py` pins the key form, the no-foreign-default rule, the
  rule-3-shadows-rule-4 mechanism, that a REAL fee still earns `fee_bleed`,
  and that a venue fee hike reaches the diagnosis with no code change.
- `bot_learn.py` (brain) — L4 stake multipliers (family bot + strategies
  consume via `fleet_bus.py`), per-bucket DIAGNOSIS (exit/entry/fee/regime/
  venue), venue A/B, scout lens-forward grades (taker veto); generates for
  LIVING bots only (retired set + 7d close recency, 15-Jul).
  **[2026-07-30 (hd)/(hg)/(hh)] `ERA_START` was pooling the 17-Jul accrual-basis
  fix on ELEVEN books, including a REAL-MONEY row.** Its header rule — "hypotheses
  must come from trades taken by the CURRENT code" — is exactly about this, and
  it had no entry for the two funding books and six family/spot books, while the
  six it *did* have were dated 13/14-Jul for STRATEGY changes and so still sat
  BELOW the accrual fix. All are now ≥17-Jul (an era is the LATEST of every
  invalidating change; moving a date forward preserves the earlier reason).
  Also fixed here: `era_epoch_for`'s **THIRD** bug — the double `rsplit` mangles
  `perps-funding-lighter-lshadow` to `perps-funding` because 💸 Farmer is itself
  named after the venue suffix, so a single declaration would have scoped the
  live row and MISSED its shadow twin. Exact-match first, then strip ONE suffix.
  The gate's sample may never be wider than the brain's, and both tables must
  cover the same living accruing set — pinned in both directions. **v3 statistics
  engine (16-Jul, `brain_stats.py`)**: decay-weighted buckets (14d half-life
  forgetting), empirical-Bayes pooling (tag-family → bot → fleet priors),
  Wilson/t evidence bars, regime splits, episode-deduped lens grading (raw
  fields unchanged — consumer contracts held); floors/streaks UNCHANGED;
  reduce-only until 21-Jul, then TWO-WAY (see `brain-stake-mults` below —
  operator-mandated expand, v3-only, mirror bars); validated by `brain_replay.py`
  (ledger no-regression + 6-scenario synthetic discrimination, header has
  the verdict); kill switch `BRAIN_MULT_ENGINE=v2`. **Fast-path (16-Jul
  "no-brainer window")**: EMER_* bars (n≥40, t≤−2.5, post_wr<0.20) skip the
  3-run streak gate on the FIRST qualifying run — latency only, authority
  unchanged; urgent keys surfaced on `brain-vitals`; →
  `learning-brain`, `brain-stake-mults`, `brain-diagnosis`,
  `brain-lens-forward`, `brain-vitals`
- `fleet_risk.py` — traffic light (live > lshadow > paper via
  `authoritative_row`, 65-min staleness filter) + signal bus + **7d fleet
  drawdown governor** (`clip_scale` 1.0/0.5/0.25 — Ticket Taker consumes,
  gate0 advisory) + **exposure view** (`exposure`: effective-bet count via
  1/HHI, per-symbol pileup, crypto/equity split — advisory, 15-Jul);
  long-budget veto ENFORCED in strategies + taker + family bot
  **[2-Sep (wp)] THE BUDGET IS PER COHORT NOW** — `cohorts.{live,shadow}`
  beside the pooled pair, `fleet_bus.cohort_long_state` the one reader:
  measured 2-Sep, 6 of the 20 pooled longs were the shadow taker's PAPER
  and both real-money rows read `fleet_long_veto: true` with slots free.
  Paper cannot risk real money and real money cannot risk paper; one count
  for both was a category error in both directions. Same number (20) by
  default, `FLEET_LIVE_LONG_BUDGET` for the live cohort.
  (`FLEET_RISK_MODE=advisory` = kill switch)
- `evidence_board.py` ⚖️ — the evidence organ (15-Jul): scores/corroborates
  fleet-alerts, synthesizes cross-feed items (lens floors, veto flap, venue
  stress, governor proximity), auto-verdicts mechanical items (manual
  `evidence-review` stays senior), phone-notifies warn/action, publishes
  SHADOW restrict-only proposals → `evidence-board` (EVBOARD_MODE=shadow)
  + **GROWTH RAIL (15-Jul user mandate: widening must not need the
  operator)**: EXPAND-direction responses ENACT via `fleet_tuning.py` —
  whitelisted, hard-bounded, TTL'd levers (auto-revert by expiry), lanes in
  `FLEET_TUNING_ENACT_LANES` only (shipped default: paper-scanner +
  lighter-scout/-taker/-xp + **lighter-live**, the 15-Jul user-mandated
  live lane; 16-Jul `AUTHOR_LANES` binds each author — board →
  `live.clip_scale` only, judge → `live.funding.*` only; go-live/keys/
  SafetyRails caps stay operator-only forever). Its first
  loop (Gap Scout census quiet 24/48/96h → widen prefilter/book-budget/
  second-tier venues kucoin/gateio/mexc) is INERT since 17-Jul: Gap Scout is
  retired, so `gapscout-census` never refreshes and the ladder fails safe on
  staleness. That loop widened toward MORE CEXes, so under LIGHTER-ONLY it
  SHOULD be inert — the growth rail now has no active author on that lane.
- `lighter_scout_tuner.py` 🧠🔧 — the Lighter loop's SELF-TUNING organ
  (15-Jul user mandate: the scanner "needs the freedom, with the brain's
  support, to act"). Hourly, stateless, replay-gated: replays the scout
  tape through the taker's REAL code (`lighter_ticket_replay`), widens
  STARVING lenses' taker bars (not-worse both halves), expands
  brain-graded WINNER lenses (must IMPROVE both halves), auto-runs the
  TP/SL/hold sweep (anti-overfit floors: ≥10 closed, +$2 total, both
  halves), widens starving lenses' SCOUT emission bars (grading diet —
  advisory tickets only). Everything lands as bounded TTL'd
  `fleet-tuning` levers (auto-revert); never widens a brain-vetoed lens;
  fail-safe neutral on a dark brain. → bot_state `scout-tuner`
- `fleet_proprioception.py` 🦾 — PROPRIOCEPTION (16-Jul, "advance the
  autonomous organ"): the autonomy stack's sense of its OWN movements —
  the first RETROSPECTIVE grade on growth-rail enactments (every prior
  gate was prospective/in-sample). Tracks every lever EPISODE (open →
  expire/release/value-change; long stances sliced daily) and grades it
  out-of-sample: taker levers get the TRUE replay counterfactual in $
  (during-episode tape, env defaults vs enacted bars through the taker's
  real code), scout diet levers get grading throughput (lens n4h delta),
  gapscout GOT census activity — DEAD since 17-Jul: Gap Scout is retired, so
  the census never refreshes, `census_ok` is False (`fleet_proprioception.py`
  :595) and `grade_gapscout` never runs; that lane grades nothing;
  live/xp episodes are RECORDED only (the
  judge + fade-watch stay the real-money authority). Per-lever verdicts
  helping/hurting/neutral (floors n≥2 episodes, ±$3; HURTING exists only
  on the taker lane — the one lane with a $ counterfactual; joint stances
  share blame, conservative in the restrict direction). CONSUMED BOTH
  WAYS (16-Jul evening, operator: "implement the expanding side ... so
  the July 21 can review both sides"): RESTRICT — the scout tuner refuses
  to re-assert a HURTING lever (`apply_proprioception`); EXPAND — a
  HELPING taker lever unlocks the tuner's improve-both-halves expansion
  walk before the brain's ruling floor (brain veto stays senior), a
  HELPING diet lever walks one notch deeper, a HELPING gapscout lever
  discounts the board's widen-ladder bars (×0.75, 12h floor). **LIVE LANE
  LEARNS (16-Jul evening, operator mandate)**: live episodes graded
  per-trade vs TWO baselines (the books' own pre-window AND the shadow
  twins, same window; clip vs funding split by author so the board's
  movement is never blamed on the judge's; 'bad' only when worse than
  EVERY baseline by the margin; floors higher than shadow lanes) —
  consumed restrict-first: HURTING live.clip_scale releases the board's
  lever + blocks up-steps; HURTING live.funding.* is the judge's EARLIER
  fade signal (`prop_fade`; the judge stays the only writer); the single
  live earn is the clip ladder's TOP step (1.5) now REQUIRING a measured
  HELPING at 1.25 — fail-CLOSED (dark sense = top out of reach). Board
  surfaces 🦾 items (hurting=warn, helping=expand); immune scans the
  payload. Fail-safe both ways on shadow lanes: a dark organ restricts
  nothing AND earns nothing. **CONSUMER SUPPORT (16-Jul late)**: verdicts
  are a first-class bus signal — `fleet_bus.lever_outcome(lever)` is the
  supported accessor for any strategy/bot (standard fail-safe contract),
  `/bus.json` serves the payload + history off-Railway, and the incubator
  consumes it (skips proposing a funding gene whose live lever is
  currently graded hurting — a 7-day judge slot isn't spent re-testing a
  knob the live lane just measured bad). **REAL-MONEY BOTS CONSUME TOO
  (16-Jul late)**: `fleet_tuning.get_lever` reverts a HURTING live-lane
  lever to the operator's env default AT THE CONSUMER, every loop (the
  immune-quarantine central-hook pattern; covers the funding bot's
  `apply_levers` + both live bots' clip via venues) — a measured-bad
  lever stops steering real money immediately instead of waiting out the
  board/judge cycle or the lever TTL; live-lane only (shadow lanes keep
  TTL semantics), fail-safe open, restrict-only by construction. **[23-Jul
  audit CORRECTION: the clip HOOK is wired at the consumer, but
  `live.clip_scale` can NEVER actually receive a `hurting` verdict —
  `fleet_proprioception.grade_live` returns `recorded` for the `live-clip`
  group because the per-trade metric is invariant to clip size — so this
  auto-revert only ever FIRES for `live.funding.*`. The clip's real
  protections are the board's DOWN reflex + lever TTL + the SafetyRails cap.
  "covers ... both live bots' clip" describes the plumbing, not a revert
  that can fire.]** Review grades both sides — agenda item 12.
  → bot_state `fleet-proprioception`
- `experiment_judge.py` 🧪⚖️ — the shadow→live PROMOTION pipeline (15-Jul
  user mandate: shadow wins must "carry across to the real money bots").
  Hourly, ONE candidate at a time on the Funding Farmer's -lshadow twin
  (xp.* levers; while running, the twin is an EXPERIMENT arm, not a
  control arm; every close row stamps extra.bars). Promotion to the live
  arm (live.funding.* — this judge is the ONLY writer) requires the
  PAIRED bar: ≥7d, ≥30 shadow closes, live ≥10, shadow positive in its
  own right AND beats live per-trade by ≥0.5pp on the window AND both
  halves. Fade-watch releases a promotion whose live arm turns negative
  (n≥15). Candidate queue in CANDIDATES (first: enter_apr 0.30 — the
  11-Jul "opt-in, shadow-validate" gate widening). Tide Rider excluded
  (trades too rarely to judge; stays backtest-validated). → bot_state
  `xp-judge`; phase surfaced on the evidence board (🧪)
- `fleet_immune.py` 🛡️ — the IMMUNE + SELF-REPAIR organ (15-Jul, from the
  operator's "what self-repairs / what filters" framing + the same-evening
  incident where a 39h-stale artifact drove a false live down-scale).
  Covers the failure class the death-oriented watchdog misses — ALIVE BUT
  SICK (fresh, in-TTL, trusted, but WRONG). FILTRATION: prunes the
  fleet-alerts bloodstream of age-stale + known-toxic ANTIBODY matches.
  ADAPTIVE IMMUNITY: scans fresh organ payloads for invariant violations,
  QUARANTINES a sick growth-rail lever (`fleet_tuning.get_lever` honors
  `fleet-immune.quarantined_levers` → reverts to operator default), phone-
  pushes NEW sickness. Restrict/clean only; fail-safe (dead immune = no
  quarantine). → bot_state `fleet-immune`; surfaced on the board (🛡️)
  **[2026-07-30 (hh)] IT NOW WATCHES FOR A COMPROMISED LEDGER** — the purest
  alive-but-sick shape there is: a row that is fresh, in-TTL and trusted while
  its `n` is two processes' trades. Reads `golive-readiness.books.<bot>.
  integrity.two_writers` (the PUBLISHER's verdict, never re-derived) and pages
  the operator, because the fix is an OPERATOR action — stop the duplicate
  Railway service — and no guard can un-pool closes two processes already
  wrote. `golive-readiness` had to join the organ's `_keys` fetch list in the
  same commit or the scanner would be inert; `tests/autonomy/
  test_immune_two_writers.py` pins that, and pins that a clean book in the
  SAME payload stays silent (a detector that flags everything trains the
  operator to ignore it).
- `fleet_regen.py` 🩹 — REGENERATION (self-repair tier 2): restores a
  stateful organ the immune organ flagged SICK to its last-good history
  snapshot (age-bounded) or a safe baseline; content-only, carries the
  snapshot's own age so it never asserts old data as current. → `fleet-regen`
- `strategy_incubator.py` 🧬 — REPRODUCTION: breeds strategy GENOTYPES
  (crossover+mutation). Taker offspring scored instantly by replay
  (shadow-only leaderboard); funding offspring PROPOSED to `xp-queue` for the
  experiment judge's identical paired live bar — no offspring shortcuts the
  gate. Recombines within registry bounds only (invention stays human). →
  `strategy-incubator` + `xp-queue`
- `fleet_clock.py` 🕐 — CIRCADIAN: the fleet's shared sense of time (trading
  session, thin-liquidity, heavy-job window). Advisory. → `fleet-clock`
- `implementation_shortfall.py` 📏 — LIVE-vs-SHADOW execution quality: the
  continuous per-trade return gap (live real fills − shadow mark fills) on
  the SAME coins both arms closed, weighted by paired closes, with ENTRY/
  EXIT-slip decomposition (funding bot records fill prices since 15-Jul).
  Verdict clean/live-ahead/live-slipping/insufficient; sustained slip →
  phone. Answers "is the live book slipping, and on entry or exit?". →
  `impl-shortfall`
- **THE EXIT INSTRUMENTS (2026-07-30, (gq)/(gt)/(gx)) — read these before
  touching any TP, SL or max-hold in this fleet.** Entries here have levers, a
  scout, a tuner and a brain; exits had constants, and until (gr) the ledger did
  not even record what an exit did.
  * `scripts/study_exit_attribution.py` — per (book, exit_reason): n, total $,
    mean %, win %, **median hold**. The hold column is the diagnosis: two exits
    on one book with a 6x hold gap are one rule firing before the other can.
    Measured: 🌾 carry earns **+$71.42 on `*_decay_paid`** (hold 65-70h) and
    loses **−$17.32 on the sided `*_flip`s** (hold 6-10h) — and a THIRD unsided
    `flip` bucket is +$7.02, so "flip loses" is true only of the sided ones.
    **[15-Aug (nc), corrected in place per I12: ≈$13 of carry's all-time
    accrual (≈$6 of it inside the decay_paid family) is PHANTOM — rows opened
    17–28-Jul by the stale pre-basis-fix container over-accrued 2.5–6.7×
    (resting stamps exactly 8× TRUE). Era-scoped grades are clean (the 31-Jul
    era boundary happens to exclude every contaminated row); every POOLED
    all-time quote of this book — allocation rank, +$66 headline, the
    decay_paid story — overstates. STUDY_FUNDING_LIFECYCLE_2026-08-15.md §1.]**
    `*_sl` at a 0% win rate appears on SEVEN living books. RETIRED rows are
    excluded by default: the ledger is history and a Kraken-era book measures
    +$272.09, the largest line in it.
  * `scripts/study_exit_sweep.py` — the counterfactual: replays a book's OWN
    trades under alternative exits against **Lighter's own candles**. Entries
    held CONSTANT (never fitted), THROUGHPUT modelled (sequential, with the
    book's position cap, so a rule that holds longer pays for the entries it
    blocks — carry and Counterweight are both AT their caps, so for them that
    is the whole question). `shipped_rule(book)` reads each book's REAL exit
    from its module — absorbing three hazards that corrupt silently: the taker
    stores `TT_SL` **negative**, Snap Back's exit is in **bps** and the
    sniper's hold in **seconds**, and the sniper's exits are **bare literals no
    lever can reach** (`HARDCODED_EXITS`).
  * **THE CALIBRATION GATE IS THE POINT.** A harness that cannot reproduce what
    DID happen may not say what WOULD have. `calibrate()` compares the replayed
    shipped rule to the book's real ledger mean and **withholds every
    recommendation** beyond tolerance — fail-CLOSED, so no baseline supplied
    means nothing recommended. It passes today only for `pm-gillard-lshadow`
    (replayed −0.158%/trade vs actual −0.110%), because that is the one book
    whose every close carried a price before (gr).
  * **A grid-edge winner is reported UNBOUNDED, never as a value.** On gillard
    every top candidate pins `sl` at whatever maximum the grid allows, so the
    honest output is "widen the grid", not "ship 8%". Widening until a number
    appears is chasing the artifact. ~~The direction IS robust and monotone~~
    **[15-Aug (ne), corrected in place per I12: the direction was an ARTIFACT
    of the harness's entry-bar look-ahead — `walk_exit` credited the entry
    bar's FULL range, pre-entry prices included, and on gillard the same
    candidate rule reads +0.319%/trade with the entry bar and −0.396%/trade
    at LAG-1 (entry bar excluded). Two calibrating conventions, opposite
    verdicts ⇒ per the execution-lag doctrine the intrabar edge is REFUTED.
    The look-ahead is fixed in `walk_exit` (LAG-1 is now the convention);
    do not walk gillard's sl on the old reading.]** The actor still exists:
    the Parliament's tuners walk tp/sl/hold replay-gated inside
    `PARAM_BOUNDS`, and their own replay gate stays the honest judge. Two review notes from (gx):
    `PARAM_BOUNDS["sl_pct"]` caps at 0.05 so the sweep's winner is outside what
    the system can express, and the ×1.25 step needs **7.2 consecutive accepted
    widenings** to reach that ceiling while the gain only becomes clear near 3%.
- **EXIT TELEMETRY IS A CONTRACT NOW ((gr), guarded by
  `tests/autonomy/test_exit_telemetry.py`).** `publish_paper_trade` accepted
  `entry_price`/`exit_price` from 17-Jul and **8 of 9 bots never passed them** —
  computed two lines above the call for `pnl_pct`, then dropped. Every exit
  constant in the fleet was unfalsifiable. All nine now record, and the guard
  refuses any bot that holds prices in scope and omits them. **Book-appropriate,
  not uniform**: 🌾 carry is a FUNDING book (P&L is `accrued − fees`), so it
  records `entry_apr`/`exit_apr`/`accrued`/`fees`/`held_h` instead — a price
  sweep measures the wrong thing for it, and `study_exit_sweep` REFUSES funding
  books outright rather than caveating them. **Not retroactive**: the 1,687
  closes that predate (gr) have no prices and never will.
- **A STOP MUST BE RECONCILABLE WITH THE GATE THAT JUDGES IT ((gv),
  `tests/autonomy/test_stop_vs_gate.py`).** The stop is chosen in the bot; the
  15% drawdown bar lives in `golive_readiness.py`; nobody had read them against
  each other. 🌊 Tide Rider 35% = **2.3x the bar**; 📊 Index Rider 15% =
  **exactly at it**, so it is stopped out at the same instant it becomes
  ineligible. Any stop at-or-beyond the bar must be DECLARED with a reason
  (the `BORN_DARK_OK` idiom) — none was moved, because Index Rider has zero
  closes and there is no evidence to set a number against.
- `fleet_allocation.py` 💰 — the ALLOCATION organ (2026-08-01 (hv), operator:
  "structured for growth ... the best outcome for our growing ecosystem"). The
  fleet had a dozen organs answering "is this book SAFE?" and none answering
  "where should the MONEY go?" — every shadow book gets $1,000 regardless of
  evidence. Measured: FUNDING 3 books / n=212 / **+$72.89**; DIRECTIONAL 18
  books / n=809 / **−$9.21**. Ranks each book by `max(0, mean − 1.28·SE)` on
  per-trade return — a LOWER BOUND, so a big mean on a tiny n has a wide SE and
  a weak claim; every living book keeps a **25% probe floor** (a book cannot
  earn evidence with no capital); total capital is CONSERVED; and with no
  measured claim anywhere it returns EXACTLY the flat allocation rather than
  inventing a split. First live run: funding $4k→$16k, directional $16k→$4k,
  **0 of 16 directional books with any claim**. **ADVISORY — it moves no
  capital, writes no lever, promotes nothing** (asserted: the module contains
  no `write_levers`/`get_lever`/`market_open`). NOT a second go-live gate — the
  gate is IMPORTED from `golive_readiness`. → bot_state `fleet-allocation`,
  30-min `--publish` loop sharing the radar's ledger fetch.
  **[2026-08-05 (jr) S1 — IT HAS CONSUMERS NOW, by operator decision.** The
  ORGAN is unchanged (publish-only); `fleet_bus.allocation_scale(bot)` serves
  `target_usd/book_usd` clamped [0.25, 4.0] and the three funding SHADOW
  books size NEW entries by it — 🌾 carry, ⚖️ Counterweight (`not _is_live`),
  💸 Farmer shadow arm (`if shadow_tag`; consumer deferred behind the next
  marked Farmer deploy). Real money never reads it — AST-pinned in
  `tests/autonomy/test_allocation_consumer.py` — and
  `FLEET_ALLOCATION_MODE=advisory` per service reverts every consumer to its
  env default at the accessor. Both funding Dockerfiles gained the
  `fleet_bus.py` COPY + deploy-route entries in the same commit (born-dark +
  orphan rules).]
- `scripts/golive_readiness.py` 🚦 — the GO-LIVE GRADER, an ORGAN since
  2026-07-30 (gk). Grades every LIVING book against the `(fk)` bar and
  publishes → `golive-readiness` (6-hourly `--publish` loop in `run_all.sh`;
  the ONLY file under `scripts/` that ships in an image). **It had no
  publisher and no schedule until (gk)** — the rule governing real money ran
  only when a human typed the command, so nobody could see that 🌾 carry was
  five of six bars from the gate. Publishes a machine-readable per-bar map
  (`bars` / `BAR_NAMES` = window/closes/mean/t/halves/maxdd) so no consumer
  string-matches prose; `bar_map` is selftest-BOUND to be exactly equivalent
  to `grade` (a `maxDD` that cannot be computed FAILS — fail-closed).
  Rendered as the 🚦 dashboard card (✦ = passes the new bar where the retired
  win-rate rule would have rejected it). PUBLISH-ONLY: promotes nothing,
  writes no lever; go-live stays an explicit operator act.
  **[2026-07-30 (hc)–(hh)] IT NOW OWNS TWO PRECONDITIONS in front of the six
  bars** — `POLICY_ERA` (which sample describes the book) and ledger
  `integrity` (is the sample one book at all). See the GO-LIVE GATE rule below
  for both, including what may and may not reset an era. It is also the ONE
  OWNER of `parse_stamp` / `same_pair_overlaps` / `peak_concurrency`:
  `scripts/audit_ledger_integrity.py` imports THEM, deliberately in that
  direction — the reverse would drag a non-shipped script into the freqtrade
  image's import graph (the born-dark class), and a second copy would let the
  audit and the gate disagree about the same ledger. Payload gained `era`,
  `alltime` (the pooled reading it replaced, so nothing is hidden) and
  `integrity`; `--min-closes` filters on the ALL-TIME count so a demoted book
  shows dark bars instead of vanishing.
  **[2026-08-06 (ks)] It also publishes the 🔭 GATE HORIZON** — per-book, WHEN
  the failing bars flip at the measured in-era trajectory (`n_req = n·(T/t)²`
  for the t bar; rate over ERA AGE never close-span, I1; verdicts
  ready/on_track/no_rate/unreachable-at-trajectory/undecidable-per-I17/
  unprojectable; every ETA a FLOOR, fail-closed, reported-not-a-bar).
  Consumers: the 🚦 card's horizon chip, the daily review's 🔭 line, the CLI
  suffix. ~~LIMIT: books below `--min-closes` are outside the horizon~~ —
  **SUPERSEDED THE SAME DAY by (kv), corrected in place per I12** (the limit
  as written is now false and a reader acting on it would think 📊
  equities-regime is unmonitored): below-floor books ride an additive
  **`below_floor`** map — thin books get a horizon from their own sample, and
  a **roster sweep** over `bot_pnl` catches ZERO-ledger books, fail-CLOSED on
  liveness (`roster_admits`, I1) and excluding declared non-trading
  publishers (`ROSTER_NON_BOOKS`, (kx) — `market-context` is a heartbeat, not
  a book). The sweep publishes its own receipt (`roster: {scanned, admitted,
  rejected, non_book, error}`) so sweep-DARK is never byte-identical to
  swept-CLEAN ((kw), I4). `books` membership itself is unchanged — that
  contract did not move. An era move voids every previously reported date for
  that book; consumers re-derive each publish, never cache.
- `fleet_respiration.py` 🫁 — RESPIRATION / blood-oxygen: OXYGEN = fresh
  market data; LUNGS = the venue-fetch layer. Measures SpO2 (weighted
  fraction of data feeds breathing fresh) and phone-alerts on a HYPOXIA
  transition — the fleet-wide data-starvation the per-organ watchdog misses.
  → `fleet-respiration`
- `event_sentinel.py` 🗞️⚡ — the EVENT organ (16-Jul user mandate: "be ahead
  of the game" on major world events). market_pulse reads MOOD; the
  sentinel reads discrete typed EVENTS: RSS + GDELT sweep every 10 min →
  keyword taxonomy (monetary tightening/easing, CPI hot/cool, crypto
  crackdown/ETF-adoption, exchange incident, stablecoin stress,
  geopolitical shock, banking stress, AI boom) → severity-gated per-sector
  anticipations from a seeded HISTORICAL PLAYBOOK (COVID, Terra, FTX, SVB
  safe-haven flip, ETF Jan-24, yen-carry Aug-24, tariffs Apr-25) → then
  GRADES its own anticipations at 4h/24h/72h against sector indices
  chained from the scout's marks, and the playbook confidence LEARNS
  (EB blend **on measured EDGE since 5-Aug (jv)** — the record is scored
  against a COIN FLIP, so an at-or-below-0.5 playbook is silenced by its
  own grades instead of keeping `hit_rate` worth of its fear forever;
  priors keep their modest soft-weight role at n=0; direction never
  auto-flips without review. Measured basis: crackdown 0.19/n=85, shock
  0.24/n=83, incident 0.34/n=87 were pressing every sector bias negative
  while easing sat earned at 0.95/n=21 — the risk-on proposal path was
  unreachable by construction, (ji)). ~~ADVISORY: zero consumers~~ **[22-Jul: THE
  "ZERO CONSUMERS" CLAIM IS STALE — but it steers a SHADOW book, NOT real
  money.** `fleet-tuning` carries `taker.momo_chg=6.0` and `taker.brk_range=0.97`
  on the `lighter-taker` lane, both stamped
  `reason: "organ-proposal:event-sentinel (replay-gated at this tuner)"`. The
  sentinel proposes; the scout tuner replay-gates and enacts. That is a real
  consumer path — so "advisory, zero consumers" was stale. BUT `lighter-taker`
  is the **$1k SHADOW** lane (`lighter_ticket_taker.py:272` "NOT ON REAL
  MONEY"; only `live.*` levers may steer the live book), so an earlier
  "steering the LIVE taker" note here over-corrected — verified 22-Jul (ci).
  The sentinel has actuator reach into a shadow book; it does not touch real
  money.] Tuning: `evsent.*` levers, lane
  `event-sentinel`. → bot_state `event-sentinel` (+ `-state`)
- `parliament_main.py` 🏛️ — the Parliament's supervisor (21-Jul): six asyncio
  layers in one process — `parliament/` data (Lighter REST+ws ONLY),
  Keating's 10 scanners + 5-model prequential ML ensemble, the six PM shadow
  books, six replay-gated auto-reverting tuners (the scout-tuner doctrine:
  bounds cage, TTL, both-halves floors, hurting-refusal), Howard's brain →
  bot_state `parliament` + `parliament-tuning`. Redis mirror optional
  (`REDIS_URL`); in-process bus is primary. Shadow-only forever until the
  standard go-live gate.
- `fleet_proposals.py` 🗳️ — the organs' PROPOSAL channel to the tuners
  (21-Jul, operator: "the organs need more ability to implement changes to
  forward onto the tuners to act on"). Any organ proposes a bounded change
  to a REGISTERED lever → `tuning-proposals` (locked multi-author merge,
  per-proposal expiry, clamped at write AND read, declared
  direction restrict|expand). Proposals NEVER enact: the scout tuner gates
  each through ITS OWN replay (restrict = not-worse both halves; expand =
  the full winner bar, brain veto senior, ≤3/cycle, provenance
  `organ-proposal:<author>`), and the judge treats a fresh restrict proposal
  on a promoted live lever as a third release path (`proposal_fade`,
  restrict-only; judge stays the only live.funding.* writer). First
  proposers: event sentinel (risk-off crouch / graded-playbook expand),
  impl-shortfall (sustained slip → live.funding.enter_apr restrict),
  respiration (confirmed hypoxia → crouch). The sentinel's own
  `event-sentinel` lane is now enactable + author-bound (detection
  sensitivity only — it was registered but UNREACHABLE since 16-Jul).
  Fail-safe: dark channel proposes nothing, consumers ignore stale/junk.
  → bot_state `tuning-proposals` (+ /bus.json, 🗳️ Autonomy-card row)
- `regime_oracle.py`, `market_pulse.py` (history appends every 30 min, 15-Jul),
  `cleanup_legacy_bots.py` (boot prune of retired rows)

### RETIRED (rows hidden + pruned; ledgers kept)
Kraken paper 8 (spot 4 + family 4, 14-Jul user cut — Kraken/laptop
processes are operator-stopped), equities-momentum-alpaca +
equities-regime-ibkr (14-Jul), Trail Blazer, Bounce Catcher, Two-Way Tide,
Loop Scout, trendmomo-4h (12/13-Jul).

**17-Jul LIGHTER-ONLY cut** (operator: "i only want things running on lighter"):
`event-listing-sniper` (🎯 Launch Sniper), `scanner-cross-exchange-arb`
(🔀 Gap Scout), `perps-funding-carry` (🌾 Yield Harvester's HL-DATA arm — its
`-lshadow` twin CONTINUES and is deliberately NOT retired). `scanner-triangular-arb`
and `perps-rsi-meanrev` were already-hidden rows whose SERVICES kept running;
they now have guards too. Per-row stop mechanism + resurrect switch: see the
LIGHTER-ONLY table above — not restated here.

**Also 17-Jul**: `crypto-trend-daily-lighter` (🌊 Tide Rider's LIVE row — 🎫
Ticket Taker took the same service/keys/sub-account; retiring it is REQUIRED,
not cosmetic: both rows reported the same $34.67 and the fleet total
double-counted real money), `equities-momentum{,-lshadow}` (🏆 Stock Leaders —
maxDD 37-44% vs the 15% go-live gate).

**1-Aug (if)**: `crypto-trend-daily-lshadow` (🌊 Tide Rider's shadow — 9 buys /
ZERO sells in 22 days holding a third of the fleet long budget; reversible via
`TIDE_RIDER_RETIRED_OVERRIDE`). Recorded here 4-Aug per I12 — the fleet-table
cell carried the retirement while this list omitted it.

**4-Aug (jh)**: `lighter-dislocation-lshadow` (🧲 Snap Back — the fleet's only
statistically significant loser: t=−2.97, n=175, −0.281%/trade, both halves
negative, ~−$1/day; the growth rail structurally cannot restrict it, its
binding entry floor `ENTER_FLOOR_MULT` being an unregistered literal;
reversible via `SNAPBACK_RETIRED_OVERRIDE`).

**13-Aug (lo)**: `equities-regime-lshadow` (📊 Index Rider — the I17
structural-undecidability retirement, operator decision "get rid of what's
not working": 0 closes in 44 days, ~17.2 closes/yr measured rate vs a
30-close bar; +$13.93 open MTM abandoned as marks-not-evidence; reversible
via `INDEX_RIDER_RETIRED_OVERRIDE`; Railway service stop
(`equities-regime-shadow`) is the operator's separate act).

**14-Aug (mr)**: `crypto-breakout-4h-lshadow` (🚀 the family breakout port —
the I17 call made on the decision docket's own first batch: the ONE book of
nine that survives Benjamini-Hochberg at FDR 0.05, t=−3.50 in-era / t=−5.48
all-time, both halves negative in both samples, ~−$0.48/day, horizon
`unreachable`; freed 2 enforced long-budget slots; 4h breakout coverage
continues in 🧙 book-schwager. ROW-scoped via
`lighter_family_bot.RETIRED_BOOKS` + `live_strategies()` because the module
runs six other books; reversible via `BREAKOUT4H_RETIRED_OVERRIDE=run`).

**15-Aug (nf)**: THE RED-STOP SLATE — seven I17 calls + the xsect sleeve
wind-down, made in ONE operator act on the decision docket's own verdicts
(every ask open since 6-Aug; each row `unreachable` or the undecidable class).
Rows: `pm-gillard-lshadow`, `pm-abbott-lshadow`, `pm-rudd-lshadow`,
`pm-morrison-lshadow` (parliament `PM_RETIRED` + `live_pm_bots()`),
`crypto-intraday-15m-lshadow`, `crypto-swing-daily-lshadow`,
`freqtrade-dad-lshadow` (family `RETIRED_BOOKS`). Sleeve: 🎸 Barnes `xsect`
(rebalances to flat by its own exit; carry sleeve's clock unaffected). All
reversible via per-book override envs; both halves shipped; HELD with
reasons: ⚖️ Counterweight (pre-registered ~28-Aug), 🎯 sniper (class already
screened), mum/turnbull/albanese (green/positive). Payload-verified live
15-Aug ~13:00Z. Pinned by `tests/autonomy/test_red_stop_slate.py`.

**17-Aug (pm)**: `band-barnes-lshadow` (🎸 Barnesy — the I17 keep-or-retire
call on the CARRY CELL, operator decision). A third undecidability class beside
I17's slow clock and (oj)'s fat tail: **ZERO INDEPENDENT EVIDENCE**. Measured on
its own ledger — **0 of 9** episodes its living carry sleeve ever opened were a
coin 🌾 carry was not already holding at that moment; 3 distinct coins, all
carry's. It was minted as a THREE-sleeve super-book whose thesis was the
COMBINATION, and two sleeves were already retired ((ly), (nf)), leaving 🌾
carry's own gate at a smaller cap — I20's "same bet at a new row id". It also
could not be tuned: birth-frozen until 4-Sep. Retiring cost NO coverage. The
cell it shared went from THREE books to TWO, and the remaining pair (🌾 carry ·
🏦 Rich Dad) is DECLARED in `audit_book_overlap.KNOWN_CELL_COLLISIONS` with an
owner and a ~12-Sep decision point. Reversible via `BARNES_RETIRED_OVERRIDE=run`;
both halves shipped; pinned by `tests/autonomy/test_barnes_retired.py`. NOTE the
`extreme` (ly) and `xsect` (nf) SLEEVE retirements are a different mechanism and
still apply to the history, not to a running book.

**22-Aug (ta)**: `perps-funding-lighter-lighter` (💸 the Funding Farmer's LIVE
arm — **the first retirement of a REAL-MONEY row that had to FLATTEN rather than
freeze**, and the first that is ROW-scoped inside a two-arm module). Eamon's
call: *"just replace farmer with georgia as weve done so many times before"*.
The evidence is the fleet's own grader, agreeing across both arms — horizon
`unreachable`, live n=91 mean −0.160%/trade t=−0.88 halves +2.51/−7.65, shadow
n=161 −0.195% t=−0.95 +5.71/−18.32. 🔮 georgia takes the sub-account: 5 of 6
bars, both halves positive, failing only `t` (1.48 < 2.0) — **stated plainly:
she has not passed the gate, and go-live is Eamon's explicit act, which this
is.** **[CORRECTED IN PLACE 27-Aug (vm) per I12 — THAT NUMBER IS FIVE DAYS
STALE AND THIS SENTENCE IS THE RECORDED JUSTIFICATION FOR REAL MONEY.** Her
shadow arm's live grade today reads **n=205, t=0.62**, verdict `undecidable`,
~776 days at the measured rate — the `t` bar has moved AWAY, not toward. The
5-of-6 reading still holds and is exactly why bar count is the wrong headline:
🙏 avo passes FOUR bars and is 37 days out, because georgia's mean (+0.101%)
sits below her own `mde80_pct` (0.437%) — she is precise about a number too
small to prove. **Nothing about the go-live decision is reopened by this** (it
was Eamon's explicit act on the evidence available, and the fleet's own grader
is what says so now); what is corrected is a doctrine sentence that no longer
described the system. **This is the leak `scripts/claims_ledger.py` was built
for the same day** — the number now carries an owner
(`golive-readiness → books.freqtrade-georgia-lshadow.t`) and a tolerance, so
the next drift reddens a push instead of standing for five days and being
found by accident in an audit.] The SHADOW twin is NOT retired and keeps trading as the control arm, so
this row needs only the LIVE half of the usual two: `RETIRED_ROWS` +
`LEGACY_BOTS` are deliberately DEFERRED until the flatten's own receipt
(`extra.retired.open == 0`) is read, because `/pnl.json` is filtered by the
dashboard's roster and hiding the row first blinds the feed the flatten is
verified on. Carried in `session_state.py` so it cannot be dropped. Reversible
via `FARMER_LIVE_RETIRED_OVERRIDE=run` on BOTH `trail-blazer-live` and
`freqtrade-bots`. Runbook: `GEORGIA_GOLIVE_RUNBOOK.md`.

**2-Sep (wt)**: THE SEPTEMBER SLATE — five I17 calls made under Eamon's
delegated grant (*"I give you permission to fix the above"*), each on a
MEASURED exclusion or a zero rate: `band-garrett-lshadow` (n=85, t=−2.22, ub
−0.455%), `book-douglas-lshadow` (n=81, t=−2.54, ub −0.357%),
`perps-funding-lighter-lshadow` (n=200+, ub −0.231%; the 🧪 judge's lane
moved to 👩 mum at (wv)), `nav-cook-lshadow` (n=38, ub −0.020% — the thinnest
exclusion and still one), `book-grimes-lshadow` (zero closes ever; the (om)
study's gate crossed in 0 of 31 retests). **DEFERRED, not retired: 🔮
georgia's shadow** — retiring her before her PRE-REGISTERED 10-Sep read
(`claims_ledger.georgia-entry-cap-5-days-to-gate`) would void the
registration (the I21/I25 shape); decide at the read. Both halves for all
five; reversible per book; the funding-module arms are ROW-scoped by
resolved id (`RETIRED_SHADOW_BOOKS`); pinned by
`tests/autonomy/test_september_slate.py` (8/8 mutations red). ⚖️
Counterweight KEPT (re-read 1-Oct).

**17-Aug (po)**: `book-schwager-lshadow` (🧙 The Wizard — the I17
UNDECIDABLE-BY-TAIL retirement, operator decision "retire schwager" on the
(nu)/(oe) re-measurement). A NEW undecidability class beside I17's slow-clock
one: the book produces ~17.9 closes/30d — a fine RATE — and is still
ungradeable, because `t` assumes an approximately normal mean and here the top
3 of 298 trades are 112% of the total. Its founding +$457.21/t=1.88 does not
reproduce on any window (90-cell sweep: t≥2.0 in 0 of 90); the random-entry
null reads P=0.183; and at the measured mean/sd it needs **~719 closes (~40
MONTHS)** to reach t=2.0. ZERO closes in its own ledger, so nothing realised is
lost. Fat tails are Schwager's own doctrine — the SAMPLE failed, not the
strategy, and the retirement says so. Reversible via
`SCHWAGER_RETIRED_OVERRIDE=run`; both halves shipped; pinned by
`tests/autonomy/test_schwager_retired.py`. Railway service
`book-schwager-shadow` stopped 16-Aug 04:58:48Z — optional tidiness that a
push resurrects, not part of the retirement (see the fleet-table row).

**13-Aug (ly)**: 🎸 Barnesy's `extreme` SLEEVE (not a row — the first
SLEEVE-level retirement in the fleet, so it needs neither half of the row
rule below). The I17 call on a component that never opened a position in its
life: undecidable at every reachable floor (903/181/129 days to 30 closes at
$3M/$2M/$1M) and the two cheap settings take the carry sleeve's supply to
zero, because at the 20% TRUE bar the venue's whole crypto population is
KAITO/XMR/PAXG/XRP. **One venue, one harvest sleeve.** Entry-only, reversible
via `BARNES_EXTREME_RETIRED_OVERRIDE=run`, and its census keeps publishing
beside `retired: true` so the call stays falsifiable.

A retirement needs BOTH halves: `RETIRED_ROWS` in pnl_dashboard.py (hides the
card) AND `LEGACY_BOTS` in cleanup_legacy_bots.py (prunes the frozen row).
Doing one hides your own omission. **A SLEEVE retirement is different and must
not be forced into that shape** ((ly)): the row keeps trading its other
sleeves, so hiding or pruning it would delete a living book. The sleeve
equivalent is: gate ENTRIES only, publish `retired: true`, keep the census
alive so the call can be reversed on evidence, and pin it with a test.

### Read-only endpoints (no auth)
`/pnl.json` `/trades.json` (`?source=paper` for the paper_trades ledger —
**[2-Sep (wo)] this public feed does NOT apply `LEDGER_QUARANTINE`**; the
grader's read, `bot_pnl_store.fetch_paper_trades`, does. An outside consumer
grading from it must apply `bot_pnl_store.is_quarantined` + `golive_readiness.
is_phantom_close` itself or it grades a sample the gate refuses — measured:
🧘 douglas n=83 raw vs n=81 graded. `scripts/edge_audit.py` and `scripts/
ceiling.py` do; `?limit=` caps at 5000 and a count equal to the cap is a
truncation ((qz)))
`/bus.json` (risk light + signal bus + brain keys + lighter-market +
fleet-proprioception + **golive-readiness** (30-Jul (gk) — the go-live bars
per book, live AND `?hours=` history, so a review seat with no Railway login
can read the gate that governs real money), `?hours=` history)
`/pulse.json` `/disloc.json` `/watchdog.json`

### 15-Jul reconciliation (this repo's git now matches what runs)
The 14-Jul pivot shipped from branch `claude/gapscout-profitable-trades-ebrprj`
via PRs #40-44 to MAIN while the Lighter services deploy from GATE0 — the two
lines are now cross-merged (15 Jul) and `recovery/freqtrade-bots-image-20260715`
snapshots the exact deployed freqtrade-bots image. Operator actions done 15 Jul:
family Kraken Railway services stopped, Alpaca cron (`trading-bot` service,
project trading-bot) torn down. equities-regime-ibkr's publisher runs on an
UNIDENTIFIED host (not this repo, not ~/Claude/Trading, no local process) —
its row is dashboard-retired regardless; stop the process when found.

## Dashboard
- **File:** `pnl_dashboard.py` — Postgres-backed, auto-refreshes every 30s
- **DB:** Each bot publishes to `bot_pnl` table via `bot_pnl_store.py`
- **Auth:** DASH_USER / DASH_PASS env vars on Railway

## Key Files
- `pnl_dashboard.py` — main dashboard server (+ fleet_watchdog_svc.py)
- `bot_pnl_store.py` — shared Postgres publisher (all bots import this)
- `lighter_market_scout.py` / `lighter_ticket_taker.py` — scout + its trader
- `bot_learn.py` + `fleet_bus.py` — brain and the strategies' read client
- `fleet_risk.py` / `regime_oracle.py` / `market_pulse.py` — shared organs
- `scripts/edge_audit.py` — **[2-Sep (wo)] the fleet-wide EDGE AUDIT**: per-book
  profit factor / Sharpe / Sortino / recovery / streak-vs-chance / concentration
  / break-even cost / long-vs-short / hold-band splits, founding-claim OOS test,
  block-bootstrap P(loss)+P(ruin) at 3/6/12m, correlation-aware portfolio
  N_eff and drawdown overlap. Imports every owner (era, phantom, quarantine,
  stats, t_crit, BH) and REFUSES unless its sample reproduces the live
  `golive-readiness` grade exactly. Moves nothing. Report:
  `EDGE_AUDIT_2026-09-02.md`
- `lighter_ticket_replay.py` — replay the recorded scout tape through the
  taker's real code (rule changes judged in seconds, not shadow-days)
- `parliament_main.py` + `parliament/` — 🏛️ the six-layer PM shadow fleet
  (see intelligence layer); ecosystem DB at `/freqtrade/persist/parliament.db`
- `venues/safety.py` — SafetyRails (kill switch, notional caps, daily-loss halt)
  **+ `open_notional()`**: the fleet's ONE answer to "how much is really
  deployed?" — sum each held position at ITS OWN entry clip, never
  `count * current_clip` (that estimate breaches the cap when the growth rail
  moves the clip). Imported by BOTH live bots + the taker + the sniper.
- `cross_exchange_arb.py` — Gap Scout, **RETIRED 17-Jul** (CEX↔CEX arb, no
  Lighter leg); idles at boot
- `funding_carry_bot.py` — Yield Harvester; `lighter_shadow` ONLY since 17-Jul
  (the HL-data arm is retired; the hedge-less refusal is unchanged and senior)
- `user_data/` — Freqtrade strategies/configs (dormant post-Kraken; the
  gate0 family bot re-expresses them on Lighter)
- gate0 branch (`claude/lighter-gate0`) — the Lighter runtime (venues/,
  ShadowBroker, lighter_family_bot.py). **NO SERVICE DEPLOYS FROM IT ANY MORE
  (3-Aug (ip)).** *"its services deploy from there"* stood here while gate0's
  only consumer was `trail-blazer-live` — **the LIVE Funding Farmer, real
  money** — and that connection made every config change a code deploy: setting
  `LIGHTER_ORDER_USD` on 3-Aug rebuilt the service from gate0's tip and rolled
  the live bot **backwards 60 commits**, dropping `claim_writer` and
  `extra.svc`. The source is now DISCONNECTED (`railway service source
  disconnect --service trail-blazer-live`), verified `source={"image":null,
  "repo":null}` in `railway status --json`. The Farmer now deploys exactly like
  the Ticket Taker: `railway up` only, behind the `[deploy-live-farmer]` marker
  gate. **The general rule: a git-connected service has a SECOND, ungated
  deploy path, and a variable change walks it.**

## Cross-Bot Intelligence (bot_state keys — since 2026-07-14 CONSUMED, not just published)
- `brain-stake-mults` — bot_learn's L4 per-(bot, enter_tag) stake
  multipliers. **TWO-WAY since 21-Jul (operator: "brain needs to be able to
  widen too")** — reduce (0.5/0.75, floors n≥30 era trades / 3 consecutive
  runs, unchanged since 14-Jul) AND expand (1.25/1.5 on the v3 MIRROR bars:
  Wilson LOWER bound, t ≥ +2.0/+2.5, full n floor only, no family-praise
  inheritance, no urgent fast-path — `brain_stats.EXP_*`; same 3-run streak
  gate). Expand is v3-ONLY (`BRAIN_MULT_ENGINE=v2` zeroes it) with its own
  kill switch `BRAIN_MULT_EXPAND=off`. Payload stamps `mode: two-way|reduce-only`.
  **[19/20-Aug (sm)/(sn)/(so)] THE RANGE IS 6.7x EITHER WAY AND EVERY LIVING
  BOOK NOW READS IT — REAL MONEY INCLUDED.** This block said *"consumers clamp
  [0.5, 1.5] … SHADOW books only, no live bot reads mults"*; both halves are
  CORRECTED IN PLACE per I12, because neither describes the fleet.
  * **The clamp** is `[fleet_bus.MULT_FLOOR, fleet_bus.MULT_CEIL]` = **[1/6.7,
    6.7]** (Eamon, 20-Aug: *"The brain needs to be able to go to 6.7x
    specifically either way now"*). The floor is DERIVED from the ceiling, so
    "either way" is true by construction; the bounds are deliberately not
    restated in any consumer's prose, because a retyped constant drifts and
    this one already had, twice.
  * **The consumers** are every living book, via one owner:
    `fleet_bus.brain_clip(bot, tag, base_usd) -> (usd, mult)`, or
    `brain_clip_multi(buckets, base_usd)` where one clip spans several buckets
    (⚖️ Counterweight's two legs; 🙏 Avo's live+shadow pair) — min over the
    buckets that HAVE an opinion, silent buckets never out-voting them.
  * **WHY WIRING IT INTO REAL MONEY IS A NUMBER, NOT AN AUTHORITY.** The mult
    proposes a size; every senior rail disposes and is untouched — the kill
    switch, the daily-loss halt, the fleet long-budget veto, and the
    operator-only caps. `SafetyRails.notional_ok` must see the SIZED clip
    (AST-pinned).
    **[(sp)] "The multiplier proposes; the rails dispose" was written at (so)
    and was FALSE — corrected in place per I12, because a wrong safety
    sentence is worse than none.** `notional_ok` is a BOOLEAN, so a caller's
    `continue` discards the whole CANDIDATE, not the excess: on the shipped
    live Farmer config a brain rung of 4.5 asks $168.75 against a $150 cap
    FROM AN EMPTY BOOK, so **the brain rewarding a book for its evidence would
    have stopped it trading**, silently, forever. Nine of thirteen wired books
    had no notional bound at all. It is true now because it was MADE true:
    the Farmer's rail TRIMS to what fits (never below the pre-brain clip);
    🙏 Avo's brain is RESTRICT-ONLY, preserving the 1.00x-by-construction
    invariant its own module states; 🎫 the taker takes the mult as a RISK
    budget through `vol_clip` so constant-risk sizing and `CLIP_MAX` survive;
    and the rail-less shadow books got `fleet_bus.BRAIN_GROSS_X`, a per-book
    gross budget. **A safety sentence is a claim about behaviour and has to be
    driven, not asserted.**
  * **The key must be the LEDGER's bucket key, not the reason prefix.**
    `fetch_paper_trades` prefers a stored `tag` COLUMN over the reason prefix
    ("'long-funding' beats 'long'"), and exactly two books stamp one: 💸 the
    Farmer (`<side>-funding`) and 🧭 cook (`<side>-navband`). Looking a mult
    up under the wrong one returns 1.0 forever, silently — it was caught on
    the real-money row before it shipped.
  * **Declared exceptions, each with a reason:** funding VARIANTS (🛢️ Garrett
    — the (nb) rule: env-only config means env-only SIZE, and a capital scale
    already made its study cell unreproducible once), and ⚖️ Counterweight's
    LIVE arm (clip PINNED at `GOLIVE_ORDER_USD` per (ia)).
  Enforced fleet-wide by `tests/autonomy/test_brain_sizing_reaches_every_book.py`
  (a roster test, so a NEW book cannot ship deaf) and
  `tests/autonomy/test_brain_ceiling_step.py`.
  * **[2-Sep (wu)] TWO RAILS SIT INSIDE `brain_clip` NOW — Eamon: *"Proceed with
    advisements"* on the edge audit ((wo), §6), then *"make sure we don't
    constrict too much like we have in the past, our focus always on growth"*,
    which reshaped both before they landed.** Each bites only on a MEASURED
    harm (I26). (1) **A drawdown scale**: the clip is 1.0 all the way to the
    gate's 15% bar and falls linearly to 0.25 at TWICE the bar, read from the
    gate's OWN per-book `max_dd_pct` (the I9 worse-of-realised/MTM fold). Inside
    the tested range nothing moves. Measured the day it shipped: mum-live 3.8%,
    avo-live 5.6%, taker 5.1% → 1.0; 🪁 kelly 28.5% → 0.325. Fail-OPEN — a dark
    gate scales nothing. (2) **Never lever a weak edge**: a multiplier ABOVE 1.0
    is refused only when `fleet_allocation` has MEASURED the sized book's era
    bound at or below zero on ≥ 10 era closes (`claim_era` 0.0, `n_era` ≥
    `LB_CAP_MIN_N`, pinned to `fleet_allocation.MIN_N`). Dark, thin, None or
    junk change nothing — the brain's own t≥2 ladder governs alone, as it always
    did; reductions pass through. The returned `mult` is the EFFECTIVE multiplier
    (brain × rails) so the ledger's `brain_mult` stamp records what actually
    sized the trade (I23); the decomposition is in `fleet_bus.last_sizing[bot]`.
    Kill switch `BRAIN_RAILS_MODE=advisory` at the accessor. On the day it shipped
    NEITHER live row moved, so it went to main only and rides the next live
    deploy ((mm)). Pinned by `tests/autonomy/test_brain_sizing_rails.py`
    (8 mutations red).
    **And the expansion FLOORS were measured the same day, not moved**
    (`scripts/study_brain_floors_2026-09-02.py`, calibrated 3/3 against the
    live payload): forward, on living Lighter buckets, every 1.25x/1.5x the
    ladder would have published earned BELOW the bucket's own mean (−$2.48;
    the I25 hot-window shape), and dropping the win-rate bars (−$6.5), lowering
    every t bar (−$2.4) or the n floor (+$6.2, one bucket) does not earn
    forward either — floors KEPT with evidence. Structural fact recorded: the
    ladder's win-rate bars alone hold 🌾 carry's `short` (t=2.17) at 1.0x —
    the I15 shape in an actuator; re-run the instrument, never a bar, if such
    a bucket ever carries a positive era bound at t≥2.
- `fleet-risk` — L2 traffic light, mode **enforce**: strategies veto NEW long
  entries at long-budget (20). Kill switch: `FLEET_RISK_MODE=advisory`.
- `signal-bus`, `regime-oracle`, `market-pulse` — published context (funding
  APRs, venue premium, per-major regime, news mood). Only market-pulse.panic +
  the two keys above are consumed.
  **`listing-intel` is DARK since 17-Jul**: its ONLY publisher was
  `listing_sniper.py:1148`, which now idles behind the LIGHTER-ONLY guard
  (`listing_intel.py` is a pure library and publishes nothing). The key will
  simply go stale — consumers fail-safe on absence, per the bus contract.
  [17-Jul] The bus's Lighter premium (`lighter_prem_bps`,
  `lighter_venue_stress_bps`) now comes from the market scout's
  `lighter-market` — every liquid book, and the SAME number the Ticket Taker's
  stress veto reads — instead of retired Gap Scout's 6-symbol watchlist.
  DROPPED with their scanners: `xexchange_dislocation_pct`,
  `tri_arb_best_depth_pct` (CEX gauges; nothing outside fleet_risk read them).
  `fleet_risk.state_fresh()` honours a bot_state payload's own `updated`+
  `ttl_sec` and fails CLOSED (`row_fresh()` is for bot_pnl rows only).
- `fleet-tuning` — the growth rail's lever payload (authors: evidence board
  + scout tuner, MERGED writes with per-lever expiry; `fleet_tuning.py`
  registry clamps; consumers: Lighter Scout, Ticket Taker — Gap Scout was one
  until it retired 17-Jul, so the `paper-scanner` lane now has no consumer).
  Lanes: paper-scanner (INERT — Gap Scout retired) / lighter-scout /
  lighter-taker / lighter-xp (zero
  real money) + lighter-live (`live.clip_scale` + the judge's PROMOTED
  `live.funding.*` — see growth rail + experiment judge above)
  + **lighter-books (2026-07-30)**.
  **[2-Sep (wv)] THE JUDGE'S LANE IS 👩 MUM'S** — `xp.mum.rsi_max` /
  `xp.mum.max_hold_min` steer her SHADOW twin (the family host's first lever
  surface: `lighter_family_bot.apply_book_levers` + the `mum_bars` receipt
  both hosts stamp); `live.mum.rsi_max` / `live.mum.max_hold_min` are written
  ONLY by the judge after the paired bar (`_LIVE_PREFIX_OWNERS` splits her
  arm: the clip scale stays the board's). The judge's `LIVE_BOT`/`SHADOW_BOT`
  DERIVE from `fleet_bus.living_pair_default` — no Farmer literal — and its
  candidates are per lane; a queue proposal must carry the lane's prefix.
  **[2026-07-30 THE SHADOW BOOKS GOT LEVERS — operator: "every bot needs every
  tool at its disposal and every bot needs the ability to grow".** Six books
  had ZERO registered levers, so the growth rail could not move a single knob
  on any of them — including `carry.enter_apr`, the best-performing gate in
  the fleet (+$56.20, n=80, t=2.42). "The ability to grow" is registry
  membership PLUS a consumer that reads it; they had neither. New lane
  `lighter-books` (author: evidence board only; the board gains NO new reach
  into real money): `carry.enter_apr` / `carry.max_positions` /
  `fundspread.k` / `fundspread.universe_n` / `disloc.enter_pct` /
  `disloc.universe_n` / `index.max_open` / `trend.rank_by_funding` /
  `sniper.surge_mult`. Every one is consumed by an `apply_tuning()` in its
  bot, called each loop, tested in `tests/autonomy/test_book_levers.py` —
  the registered-but-inert lever is the failure mode that tier exists to
  prevent.
  **[2026-07-30 (gu)] `disloc.exit_bps` — THE FLEET'S FIRST EXIT LEVER.** All
  nine above are ENTRY or CAPACITY: the rail could move what every book OPENS
  and nothing about what it CLOSES. Chosen first for a measured reason — Snap
  Back's exit target THROTTLES ITS OWN ENTRY, because (fz)'s adaptive entry gate
  is floored at `EXIT_BPS * ENTER_FLOOR_MULT` = 40 × 1.5 = **60bps**, above the
  **p90 (21.8bps)** of the residual distribution it adapts to (median 7.9, max
  50.1 across 90 liquid books). So the adaptation could only descend to a bound
  set by a stale exit constant. Cage **[8.0, 40.0]** is DERIVED from that
  measurement — `lo` ≈ the live median, `hi` = the operator's current default,
  so the rail may only loosen the exit TOWARD the tape and never tighten past
  today's setting. Default UNCHANGED at 40.0: registering a lever moves nothing.
  Consumed in `apply_tuning` **and** present in `_ENV_DEFAULTS` — the second is
  load-bearing, because `_ENV_DEFAULTS[attr]` raises a KeyError that the loop's
  own `except` swallows, leaving a lever that looks consumed and never moves. Kill switch: drop `lighter-books` from `FLEET_TUNING_ENACT_LANES`
  and every consumer reverts to its env default on the next read. Also new:
  `xp.funding.min_vol` / `live.funding.min_vol` (the Farmer's liquidity floor,
  judge-promotable — the $10M floor excluded 5 of the venue's 8 most extreme
  funding books).]
  `gapscout-census` — Gap Scout's epoch-2 episode census; STALE FOREVER since
  17-Jul (bot retired), board's `quiet_hours` ladder fails safe on it. `scout-tuner` — the tuner's cycle log + enactments.
  `fleet-proprioception` — per-lever enactment outcome grades (episodes +
  helping/hurting verdicts). Consumers: scout tuner (hurting-skip +
  helping-walk), board (🦾 items + live clip gates + gapscout ladder
  discount), judge (early fade), incubator (hurting-gene skip), anything
  else via `fleet_bus.lever_outcome` / `/bus.json`.
- **`fleet_bus.scout_universe()` / `.scout_funding()` / `.venue_stress_bps()`
  (2026-07-30)** — the ONE supported read of the venue's live universe, its
  funding map and its premium stress, off the scout's `lighter-market` key.
  Built because **four LIVING books** carried hand-typed watchlists written when
  Lighter was much smaller: Counterweight ranked **30 of 202 books**, Snap Back
  16, Tide Rider 6, Index Rider 3. (This said "five" and named four — the fifth
  was retired Gap Scout's 6-symbol `LIGHTER_WATCH` in `cross_exchange_arb.py`,
  which cannot be widened because the bot idles behind the LIGHTER-ONLY guard.
  Corrected (gz): a count that does not match its own list sends the next reader
  hunting a book that is not there.)
  **[2026-07-30 (hk) — THE COUNT WAS THE SMALLER ERROR. Only TWO of the four
  named books ever had a CONSUMER.** `lighter_dislocation_bot` and
  `lighter_funding_spread_bot` shipped; `lighter_trend_bot` had no `fleet_bus`
  import and `Dockerfile.trendlighter` did not COPY it, and `lighter_index_bot`
  reads Yahoo equity dailies rather than the scout. So the two books this claim
  was supposed to help were exactly the two it skipped — and they are the fleet's
  only two with ZERO closed trades. (hk) wires Tide Rider (measured 6 -> 16 on
  the live bus, plus `scan_universe`'s held-coin orphan rule as its
  prerequisite). Index Rider is still NOT wired: a scout-added book with no
  verified `YAHOO_REF` mapping publishes nulls behind a log warning, so its
  widening is a separate job.]**
  A ranked selector cannot pick a winner it never sees. `scout_universe` reads the scout's new public `vols` map and falls back
  to its private `_marks` diff base, so a consumer shipped ahead of the scout's
  next deploy is not dark in the meantime. CONTRACT: any doubt returns
  `[]`/`{}`/`None`, and **every caller must read empty as "keep my configured
  list", never as "trade nothing"** — the widening is an enhancement, never a
  dependency, and no organ outage may shrink a book's universe.
  **[2026-07-30 (gy) MEASURED: only TWO of the four books named above actually
  call it.** ⚖️ Counterweight and 🧲 Snap Back do (live caps confirm universe 51
  and 39). 📊 Index Rider does NOT — its 3 → 10 came from a deliberate static
  list of the venue's non-crypto set, which is correct for it. **🌊 Tide Rider
  does NOT, and its live caps still read `universe: 6`** — the hardcoded
  `TREND_COINS` default. It gained `rank_by_funding` and nothing else, so this
  paragraph overstated the coverage.
  **AND WIDENING IT IS CONTRAINDICATED, not a to-do.** Tide Rider has ZERO
  closed trades, no time bound, and a 35% catastrophic stop as its only price
  exit ((gv)). Handing a book that cannot EXIT more positions to ENTER is
  strictly worse — the fleet already ran that configuration once: 🏆 Stock
  Leaders, 3 closes all via `long_catastrophic_stop`, −$91.90, retired at maxDD
  37-44%. Fix the exit first; the universe is not the binding constraint.]**
- Every payload carries `updated`+`ttl_sec`; consumers go NEUTRAL on stale
  data (`fleet_bus.is_fresh`). Backtests are inert (no DATABASE_URL).
- Bot identity for multiplier lookup = `bot_name` in each freqtrade config
  (= dashboard bot ID — keep them matching).

## How Bots Publish to Dashboard
Each bot calls `bot_pnl_store.publish(...)` with:
```python
{
  "bot": "freqtrade-mum",          # bot ID — must match CURRENT_BOTS in dashboard
  "status": "online",              # the watchdog pages NOT-ONLINE on anything outside {online, halted, paper} — this example said "running" until 19-Aug and 🧭 nav-cook shipped it verbatim
  "equity": 1023.50,
  "pnl_abs": 23.50,
  "pnl_pct": 0.0235,
  "closed_trades": 12,
  "open_trades": 2,
  "wins": 8,
  "losses": 4,
  "pnl_daily": 5.20,               # optional — today's P&L
  "extra": {...},                  # optional — JSON-able context dict
}
```
**[2026-07-28 doc-truth]** That is the COMPLETE accepted set — `publish()`
takes exactly `(bot, status, equity, pnl_abs, pnl_pct, open_trades,
closed_trades, wins, losses, extra, pnl_daily)` and has no `**kwargs`. This
block used to also list `pnl_weekly/pnl_monthly/max_drawdown/best_trade/
worst_trade`; a bot following that doc raised `TypeError` AT THE CALL SITE
in its trading loop (outside publish's never-raise guard). If those fields
are ever wanted, extend `publish()` + `ALTER TABLE` first, then this doc.

## Freqtrade Bot Configs (new bots)
All new bots:
- `dry_run: true`
- `dry_run_wallet: 1000`
- API server enabled on ports 8080–8083
- Logs to `logs/freqtrade.log`
- SQLite DB at `logs/tradesv3.sqlite`

## Claude Code Instructions
- Ask Claude to backtest any bot: `freqtrade backtesting --config <bot>/config.json --strategy <Name>`
- Ask Claude to tune via Hyperopt: `freqtrade hyperopt --config <bot>/config.json --strategy <Name> --hyperopt-loss SharpeHyperOptLoss`
- Ask Claude to check logs: `tail -f <bot>/logs/freqtrade.log`
- Ask Claude to deploy: **a push is NOT a deploy** — see Railway Setup below.

## Railway Setup
- Each bot is a separate Railway service
- All services share the same Postgres plugin via DATABASE_URL
- **DEPLOY TRIGGER — "push to main → Railway auto-deploys" is FALSE, and was
  false for both real-money bots (MEASURED 17-Jul, commit 259e3b4: not one
  of the 12 services is git-connected — `railway variables` returns zero
  `RAILWAY_GIT_*` keys on every one).** The ONLY automated path is
  `.github/workflows/railway-redeploy.yml`, which runs `railway up` for a
  **hardcoded `paths:` list** covering exactly three services:
  freqtrade-bots (`user_data/**`, `Dockerfile.freqtrade`, `run_all.sh`),
  pnl-dashboard (`pnl_dashboard.py`, `report_emailer.py`,
  `compile_market_data.py`, `Dockerfile.dashboard`), funding-carry
  (`funding_carry_bot.py`, `Dockerfile.funding`), plus shared
  `bot_pnl_store.py` / `freqtrade_pnl_poller.py` / `market_pulse.py`.
  **Anything not on that list ships only when a human runs `railway up`** —
  `fleet_tuning`, `funding_basis`, and the LIVE Funding Farmer
  (`lighter_funding_bot.py`). The RETIRED HL funding-carry arm auto-deploys;
  the LIVE Funding Farmer does not.
  **[2026-07-30 THE SHADOW BOTS GET AUTO-DEPLOY — operator: "find and implement
  whatever auto deploys necessary so that changes can be implemented in real
  time".** Six services had NO deploy rule at all — `lighter_dislocation_bot`,
  `lighter_funding_spread_bot`, `lighter_index_bot`, `lighter_perp_sniper`,
  `lighter_trend_bot`, `lighter_family_bot` — so every change to them shipped
  only when a human remembered `railway up`. That silently applied to the (fz)
  offense pass itself: its levers, widened universes and adaptive gate would
  have sat in main, green, and reached no container. They now have `paths:`
  entries AND service greps, including the SHARED modules each image carries
  (`bot_pnl_store`, `paper_broker`, `venues/`, `fleet_tuning`, `fleet_bus`,
  `funding_basis`). **Their exact Railway service names could NOT be verified
  from this repo** (the only names recorded anywhere are funding-carry,
  pnl-dashboard, market-context and the two live bots), so the deploy step now
  RESOLVES each target against `railway service list` and reports an
  unresolvable name as a loud ::warning:: instead of red-failing the build.
  **[2026-07-30 (gl) — CHECKED, and FOUR of the six names were WRONG.** Run
  `30492918936` deployed only `equities-regime-shadow` + `family-lighter-shadow`
  and warned UNRESOLVED on the rest, so the levers `(fz)` registered for those
  four books reached NO container. Railway's names follow the **emoji
  nickname**, not the dashboard row id: `snap-back-shadow` 🧲,
  `counterweight-shadow` ⚖️, `perp-sniper-shadow` 🎯,
  `tide-rider-lighter-shadow` 🌊. Fixed, and `audit_deploy_coverage.py` now
  carries all six in `AUTO_IMAGES` (it was green throughout because it checked
  no rule for any of them, and because its parser could not read a
  `$_shared`-interpolating grep at all — both fixed). LESSON: **a guard whose
  only output is a ::warning:: on a passing run is not a guard** — a green
  build with a warning is indistinguishable from a green build. STILL
  **[2026-07-30 (gn) — "deploy both" was WRONG and is REVERTED.** A
  `yield-harvester-shadow` service exists beside `funding-carry` and this repo
  cannot tell which publishes `perps-funding-carry-lshadow`. `(gl)` deployed
  BOTH on the argument that "neither has a volume, so a redundant redeploy is
  cheap". **The volume was never the risk: both publish the SAME bot_pnl row**,
  so they are two writers of one key and the row is whoever published last.
  Measured six minutes after the dispatch woke the second: n=82 with
  `extra.caps` → **n=71, caps=None, build=None**. `funding_carry_bot.py` emits
  `caps` unconditionally, so caps=None proves the winner is not running HEAD.
  ~~The paper LEDGER is CLEAN (82 closes, zero duplicate trade_ids) so the
  go-live grade and the baseline are intact — the casualty is the summary row.~~
  **[2026-07-30 (hf) — THAT SENTENCE WAS WRONG, and the check behind it could
  not have shown what it was used to show.** Two independent processes open at
  different moments, so their `trade_id`s (`{coin}:{opened_ts}`) never collide —
  a duplicate-id scan is blind to duplicate WRITERS by construction. The
  detector that works: a carry process keys `positions` by coin and enters only
  `if c not in positions`, so **one process cannot hold two positions in the
  same coin**. Measured across all 28 books / 1,706 episodes, same-pair
  overlapping holds appear in exactly TWO — `perps-funding-carry-lshadow`
  (7 overlaps, deepest **9.14h** on HYPE) and retired `event-listing-sniper`
  (a pair-naming collision across ~100 CEXes, declared). Every other book reads
  zero. Second, independent line: that ledger reaches **10 concurrent positions
  on 27 occasions** while its own `MAX_POSITIONS` was **8** until 30-Jul. And
  the STATE key is shared too — the bot persists `positions` to
  `bot_state[bot_id]` and restores at boot, so two processes clobber one
  position map and a single logical position can be closed by both. **So the
  casualty is not just the summary row: the graded LEDGER is not one book's
  record, and `t` scales with sqrt(n).** Guarded by
  `scripts/audit_ledger_integrity.py` (registered selftest; exits non-zero on a
  LIVING two-writer book).]**
  **[4-Aug CORRECTION per I12: the "one service must be STOPPED" action is
  SPENT.** (hp)/(ib)–(id)/(ih) closed it in code — `claim_writer` picks one
  writer, the loser stands by on its own key, the pager is recency-scoped, and
  the era move (ii) put the pooled window outside the graded sample. The two
  services are now a deliberate failover pair; stopping one is optional.] The
  lessons stand: a deploy rule cannot fix a duplicate that is already running,
  a guard cannot un-pool closes two processes already wrote. Lesson: a
  duplicate PUBLISHER is not a duplicate DEPLOY — ask "do they share a key?",
  not "is redeploying cheap?" — and when you check whether a shared key did
  damage, pick a test that COULD detect the damage.]**
  **[2026-07-22 CORRECTION — this paragraph was WRONG about two of them.]** The
  `paths:` filter DOES carry `lighter_ticket_taker.py`, `lighter_ticket_replay.py`,
  `venues/**` and most of the intelligence layer (`lighter_market_scout`,
  `lighter_scout_tuner`, `fleet_*`, `bot_learn`, `brain_stats`, `evidence_board`,
  `experiment_judge`, `strategy_incubator`, `event_sentinel`, `regime_oracle`,
  `implementation_shortfall`, `parliament/`) — verified against the workflow file,
  not inferred. What is manual is the *service*, not the *file*: those paths
  deploy **freqtrade-bots** (where the SHADOW taker and the organs run), while the
  two REAL-MONEY services — `trail-blazer-live` (= the Farmer; service names lie)
  and `tide-rider-lighter-live` (= the Ticket Taker) — are on NO auto path and
  need an explicit dispatch:
  `gh workflow run 305025607 -f services="trail-blazer-live,tide-rider-lighter-live"`
  (address it by workflow ID — the filename form did not resolve in this repo).
  Then MARKER-GREP both containers; a green run has never implied a container took it.
  **[2026-07-29 CORRECTION — the auto-deploy surface has since GROWN in three
  ways this paragraph pre-dates; verified against the workflow at HEAD.]**
  (1) The workflow auto-deploys **FOUR** services, not three — `market-context`
  gained a deploy rule 17-Jul — and the pnl-dashboard path list also carries
  `fleet_watchdog_svc.py`. (2) `fleet_tuning.py`, `funding_basis.py` and
  `lighter_funding_bot.py` are ALL on `paths:` now — the "ships only when a
  human runs `railway up`" list above is empty today. (3) The two REAL-MONEY
  services are no longer dispatch-only: since 24/25-Jul a push whose commit
  message carries **`[deploy-live-taker]` / `[deploy-live-farmer]` /
  `[deploy-live]`** AND touches that live image's own files auto-deploys that
  live service from clean main (no marker → shadow only, exactly as before).
  The dispatch command above still works and remains the no-marker route.
  Verify a live deploy landed by the bot_pnl `extra.build` stamp: it is a
  content hash — recompute locally with
  `python3 -c "import bot_pnl_store as b; print(b.build_compute('<entry>.py'))"`
  and compare to the row (how the 29-Jul audit proved both live containers
  ran 633e8a1 without container access).
  **[2026-07-29 (fd) — READ THE COUNT, NOT JUST THE DIGEST.** `build_compute`
  returns `(id, n_files)` and hashes only the `_BUILD_SHARED` names that
  EXIST, so the SAME tree stamps different ids in images carrying different
  subsets. Measured the day `fleet_tuning.py` joined the set: the family
  image never COPYs it (deliberate — the clip lever must not size a shadow
  book), so a converged `family-lighter-shadow` published `74d3b3178fa8`
  over 14 files while the repo computed `6de64508c304` over 15 — and the
  repo-side prediction read as "the deploy never landed". Rows now publish
  `extra.build_n` beside `extra.build`: **compare BOTH**, and when they
  disagree check `n` first — a different count means a different FILE SET,
  not drifted code. To predict an image's id, compute against that image's
  own COPY set (see its `Dockerfile.*`), not the repo tree. The born-dark
  guard cannot catch this class: these are DATA dependencies of the stamp,
  not imports.] `audit_deploy_coverage` now also
  cross-checks the live marker greps against `paths:` (the 28-Jul grep
  widening added files the paths: block didn't carry — a marker push touching
  only those deployed nothing, invisibly to the then-guard).
  **What it cost:** six fill-telemetry commits landed 04:27→10:52 UTC 17-Jul;
  the funding container booted 04:34 and picked up NONE of them — 58 real
  orders, 0 measured fills. The code was right and was never running. This is
  the mechanism behind every "frozen service" incident.
  **[2026-07-30 (gm) A ROUTING FIX CANNOT DEPLOY ITSELF.** `(gl)` corrected
  four service names; the merge run reported `Deployed: freqtrade-bots,
  pnl-dashboard` and the four corrected rules stayed SILENT, because the decide
  step fires on CHANGED FILES and that commit touched no bot file and nothing in
  `$_shared`. The rule was right and nothing rang the bell — a distinct failure
  from a wrong name. This workflow file is now part of the SIX shadow books' own
  trigger set (both `paths:` and their decide greps), so a routing fix redeploys
  the services it routes to. Scoped to those six on purpose: no volumes, nothing
  to lose, and they are the ones whose names were unverified. `freqtrade-bots`
  and the two LIVE services are EXCLUDED — the live pair stays marker-gated,
  because an unmarked WIP push must never ship real money. After ANY routing
  change to a service outside those six, dispatch it explicitly; the structural
  fix only helps the NEXT one.]**
  Check before you claim a fix is live: `scripts/audit_deploy_coverage.py`
  (does a path have ANY deploy route?), then marker-grep the RUNNING
  container — the only proof a deploy landed ([[railway-cli-frozen-services]]).
  **[14-Aug (ml)] A GREEN "Deployed: X" CAN LEAVE THE OLD CONTAINER SERVING —
  READ BACK THE SERVING OUTPUT, NOT THE DEPLOY LOG.** Measured: the #169
  merge run printed `OK: 'pnl-dashboard' deployed` and the NEW deployment sat
  `stopped, instances []` while the **14-hour-old** deployment kept serving —
  so /pnl.json filtered exactly the four rows whose registrations arrived in
  that merge, and the "missing rows" hunt burned an hour on healthy bots
  (rows fresh in `bot_pnl` the whole time; every service's resolved
  DATABASE_URL sha256-identical — the READER was stale, not the writers).
  The probe is `railway status --json` → the service's activeDeployments
  `createdAt`/`instances`; the FIX is re-deploy + read back the served feed.
  When a consumer shows exactly-the-new-things missing while old things
  work, suspect a stale READER before a broken writer — the (iw) lesson's
  mirror image, on the reporting side.
  **[2026-08-03 (iw)] AND `scripts/audit_code_currency.py` ANSWERS "WHICH
  COMMIT IS THIS BOT ACTUALLY RUNNING?" — it is one command now, not a
  40-minute investigation.** `extra.build` is a CONTENT HASH: it can say a
  container differs from the repo and never which commit it is on or how far
  back. This resolves every stamp to a commit by replaying the REAL
  `build_compute` per commit (never re-hashing — that would be a second copy
  of the rule), and classifies the gap by WHAT IS IN IT, because "behind" is
  the wrong verdict on its own:
  `CURRENT` / `BEHIND-OWN` (the gap changes the bot's own entry file — the
  only class that fails) / `BEHIND-SHARED` (the stamp moved, the logic did
  not) / `DEFERRED` (marker-gated, working as designed) / `FILE-SET` (a
  different `build_n`, i.e. a different COPY set — the `(fd)` trap).
  **Its own first three runs were each wrong**, and the reasons are the
  standing traps: it computed against the REPO tree so nine 14-file images
  read as UNRESOLVED (`(fd)`, walked into by the guard built to detect it);
  `audit_image_imports.image_contents` returns a 4-TUPLE and iterating it gave
  a silently EMPTY map; and it reported `funding-farmer-shadow` BEHIND-OWN
  when `(hi)` had joined the two arms' deploy clock ON PURPOSE. **Check a
  currency finding against the workflow before believing it** — a guard that
  cries wolf on a deliberate design is how a real finding later gets ignored.
  **[4-Aug (jc)] IT HAS A CONSUMER NOW** — a `code-currency` job in
  `fleet-weekly-assessment.yml`: reads the PUBLIC `/pnl.json` (`--pnl-json`,
  FAIL-CLOSED — a dark/empty/stamp-free feed exits 2, never a vacuous green),
  full-history checkout, `--depth 200` (a week is ~120 commits here),
  verdict table into the run summary with BEHIND-OWN the ONLY red —
  DEFERRED/BEHIND-SHARED/FILE-SET stay informational rows, per this entry's
  own cry-wolf warning. For its first day it ran only when a human remembered
  it — the (gk) "rule nobody runs" shape — while deploy-verification labor
  measured ~29% of the week's changelog entries. Wiring pinned by
  `tests/autonomy/test_code_currency_wired.py` (job exists, fetch-depth 0,
  feed source, unmasked exit code, week-deep window — five workflow mutations
  verified red). Deliberately NOT in `run_all.sh`: containers ship without
  git history, so an in-container run would read everything UNRESOLVED.
  Deploy live from a CLEAN worktree: `railway up` uploads your DESK, WIP and
  all ([[deploy-live-from-a-clean-worktree]]).
- Dashboard service: `pnl-dashboard`
- **A SERVICE'S `DATABASE_URL` IS A REFERENCE, NEVER A LITERAL (5-Aug (kb),
  measured the hard way).** During the credential rotation, 13 services held
  PASTED old-password URLs and every one went dark the moment the DB changed —
  the dashboard 500'd while its container was perfectly healthy. All consumers
  now carry `DATABASE_URL=${{Postgres.DATABASE_URL}}` (Railway resolves the
  reference and auto-redeploys on variable change), so a future rotation is
  ONE change at the source. A literal DB URL on any service is a defect.
  Superuser access + the full rotation runbook (the `railway ssh` word-split
  trap, the stdin/`env -u`/`su postgres` form, Keychain custody): memory
  `pg-rotation-runbook`. The leaked pre-July credential is DEAD, verified
  refused.
  **[14-Aug (ml)] AND NEVER ECHO `railway variables` IN CI** — the CLI prints
  RESOLVED values (a reference form resolves to the full URL, password
  included) in a boxed table that WRAPS long values, and no line-based
  redaction survives a wrap. Measured near-miss: the wave-2 provisioner's
  `| sed 's/postgres[^ ]*/<redacted>/g'` echo leaked ZERO password characters
  only because the CLI happened to wrap after `postgresql://`, putting the
  username at the start of the continuation line so sed's match swallowed the
  password — a different password length or column width and it prints raw.
  The `--set` call's exit code is the check; logs carry variable NAMES only
  (db-backup.yml's standing rule, now with the measurement attached).

## Rules
- **BEFORE EVERY COMMIT, CHECK THAT EACH MODIFIED FILE IS ONE YOU MEANT TO
  MODIFY (31-Jul (hp)).** Concurrent sessions plus `git pull`'s autostash mean
  `git status` is a list of what is IN THE TREE, not a list of your work. On
  31-Jul a stale autostash put another session's half-finished refactor of
  **`scripts/golive_readiness.py` — the go-live grader itself** — into the tree,
  and it would have shipped under an unrelated commit message. It was caught
  because it broke that session's own test; the signature is a suite that is
  green on HEAD, green with your changes alone, and red in combination.
  `git checkout HEAD -- <file>` to restore. And do NOT delete other sessions'
  stashes to tidy up — read them (`git stash show -p`) and escalate.
  **[13-Aug (lz)] THE INDEX IS SHARED TOO, AND `git add` IS NOT PRIVATE.** The
  rule above protects the working tree; it does not protect the staging area,
  and with THREE sessions live in this directory that is the sharper edge. All
  three of these happened in one afternoon: (1) three files staged, and
  `git diff --cached` listed SIX moments later — another session's `git add`
  landed in this session's staged set; (2) that session then ran `git commit`,
  which commits **the index**, so THIS session's CHANGELOG entry was committed
  and pushed under THEIR commit subject (`afed198`); (3) a third session's
  partial-staging, built from a snapshot taken before `(lx)` landed, **deleted
  the `(lx)` entry** (91 lines) while adding its own. **The mitigation is
  `git commit -o <paths> -m ...`** (`--only`): it commits the working-tree
  content of exactly those paths and ignores the index, so a concurrent
  `git add`/`git commit` can neither sweep you in nor you them. Use it by
  default here.
  **[16-Aug (nx)] CORRECTED IN PLACE (I12) — this said "the fix", and it is
  HALF a fix. MEASURED in a scratch repo, and it failed again the same day:**
  `git commit -o mine.py` correctly leaves another session's `shared.md` edit
  alone, but `git commit -o shared.md` commits **their content together with
  yours**. `--only` ignores the shared **INDEX**, exactly as claimed — it cannot
  ignore the shared **WORKING TREE**, so the protection evaporates the moment
  your path list names a file someone else is also editing. That is precisely
  how `48c04b4` committed this session's CLAUDE.md correction under another
  session's subject, hours after this rule was followed. **The two files it hits
  every time are the two every session must touch: `CHANGELOG.md` and
  `CLAUDE.md`.**
  **USE `scripts/session_commit.py`** — it makes the safe path the easy one: a
  PRIVATE `GIT_INDEX_FILE` (so a concurrent `git add` is structurally
  unreachable), mandatory explicit paths, **shared doctrine files refused unless
  passed via `--shared`** (committing one becomes deliberate, not a side
  effect), the full diff of those files printed BEFORE the commit so a foreign
  hunk is visible while it can still be stopped, and a snapshot → commit →
  read-back against the commit object.
  **THE COMPLETE FIX IS ISOLATION, AND IT IS NOW THE DEFAULT — START EVERY
  SESSION WITH ITS OWN WORKTREE (16-Aug (oe)):**

      scripts/new_session_worktree.sh <name>      # then cd into it and work

  Git records no authorship, so no tool built on it can tell whose hunk is
  whose — mitigation can only narrow the blast radius. A worktree gives a
  session a **private index AND a private set of files**, so the whole class is
  unreachable: another session's staged deletions, unstaged edits and `git add`
  simply are not in your tree. Verified on creation: the main worktree's dirty
  `CLAUDE.md` is invisible from the new one, and the suite runs there off a
  symlinked `.venv`.
  **THE WORKFLOW COST IS REAL, AND IT IS THE POINT.** Git refuses to check out
  `main` in two worktrees, so each session works on `claude/<name>` and
  publishes with
  `git fetch origin && git rebase origin/main && git push origin HEAD:main`.
  Two sessions appending to CHANGELOG.md then collide as a **rebase conflict you
  must resolve** instead of one silently overwriting the other — and **every
  failure this rule exists for was silent**: four letter collisions, three
  swept edits, one entry destroyed (90 lines), commits dropped by concurrent
  rebases, all in a single session on 16-Aug. Loud beats silent.
  **WHAT IT CANNOT DO:** relocate a session that is ALREADY RUNNING — a shell's
  working directory is fixed when it starts. Existing sessions keep sharing the
  main worktree until they restart, so `session_commit.py` above remains the
  rule for them, and this is the rule for the next one.
  **Then READ BACK what actually landed** —
  `git show --stat --format="" HEAD` and, for a file two sessions prepend to,
  grep the committed blob for every entry that should still be in it.
  `git diff --cached` is stale the moment you read it. Letters collide the same
  way: `(lt)`, `(lu)` and `(lv)` were each claimed by another session mid-write
  on 13-Aug, so **grep for the letter immediately before committing AND after**.
- **A CHECK THAT INSPECTS NOTHING REPORTS CLEAN, AND CLEAN READS AS EVIDENCE
  (17-Aug (po)).** The costly failure here is not a check that errors — it is
  one that runs, scans nothing, prints nothing, and is then quoted as a
  negative result. Measured on `scripts/audit_boot_stagger.py`, where two
  sessions mis-aimed FIVE times in a day:
  * **A range expression that terminates on its own start line.**
    `awk '/^def assess/,/^def [a-z_]+\(/'` — the end pattern matches the START
    line, so the range closed where it opened and scanned exactly ONE line. It
    printed nothing, and on that silence a LIVE bug (a `tol` parameter shadowed
    by an f-string, costing 19 of 20 organs their published tolerance) was
    reported to another session as *already fixed*. A whole-file
    `grep -nE '^[[:space:]]*tol[[:space:]]*='` found it immediately.
  * **A hand-rolled block parser** that collapsed 350 lines of `run_all.sh`
    into one block, so every organ resolved to the same first match — output
    that looked plausible and was entirely wrong.
  * **A read-back that verified the wrong property.** `session_commit.py`
    certified *"the commit holds exactly the bytes I snapshotted"* — true, and
    useless, because a `perl -pi` had corrupted the file BEFORE the commit
    boundary. **A receipt for fidelity is not a receipt for correctness**; that
    is the same shape as this file's own "a green run verifies that a declared
    enforcement EXISTS, not that it is CORRECT".
  THE RULES: **empty output is not a negative result until the check has been
  seen to produce a positive one** (run it once against a case you know
  matches); prefer a whole-file grep to a scoped one, because scoping is where
  the silence hides; ask what the check reads under TOTAL failure; and when
  correcting someone, **re-run their check rather than substituting your own
  narrower one** — both corrections issued that day were wrong in the
  consequential direction for exactly that reason.
  **[19-Aug (qz)] THE THIRD COSTUME: A TRUNCATED SEARCH READS AS AN EXHAUSTIVE
  ONE.** The rule above is about a check that inspects NOTHING. This is a check
  that inspects MOST of it and reports as if it had finished, which is worse,
  because the output looks like real work. Measured: renumbering three changelog
  letters, I enumerated the citation sites with

      grep -rn '(q[klm])' --include='*.py' --include='*.md' ... . | ... | head -40

  and built the file list from what it printed. There were **48** matching lines.
  `head -40` cut the last eight, and the two files that fell off the end were
  **`lighter_funding_bot.py` and `venues/safety.py` — the LIVE Funding Farmer and
  SafetyRails**, i.e. the real-money surface. Seven citations of the ruin-gate
  entry were left pointing at another session's unrelated entry, the tree was
  committed, CI went green, and the entry's own renumber note asserted the
  opposite. Nothing in the output said it had been cut: `head` is silent by
  construction.
  THE RULES: **never pipe an enumeration you are going to ACT on through `head`,
  `-m`, `| head -n`, or any other cap** — cap the output you are *reading*, never
  the set you are *deriving work from*; **count first and reconcile** (`| wc -l`
  before `| head`, and if the count equals the cap, assume truncation until
  proven otherwise — a result exactly equal to its own limit is a truncation
  signature, the same shape as `(hd)`'s lens returning exactly its cap); and
  **derive the work-list from `-l`/`--files-with-matches`**, which is per-file and
  far harder to truncate, then verify each file's hits individually. The general
  form: *a cap is a display choice; the moment it reaches your reasoning it is a
  silent sampling step you did not declare.*
- **ANY PRODUCER PIPED INTO `grep -q` UNDER `pipefail` CAN INVERT A MATCH
  (14-Aug (ml) — it bit TWICE IN ONE HOUR, in two different costumes).**
  `grep -q` exits at the FIRST match; under `set -o pipefail` the pipeline's
  status then includes the producer's, and a producer killed mid-write reads
  as failure — so a SUCCESSFUL match becomes a red step. Run 1: the Railway
  CLI (Rust) panicked on the SIGPIPE ("failed printing to stdout: Broken
  pipe", exit 134). Run 2's "fix" captured the output first but piped
  `printf` into `grep -q` — and printf's own broken-pipe write error
  inverted every match for all four services. **The fix is no pipe at all**:
  pure-bash `case "$var" in *pat*)` / `[[ $var == *pat* ]]` for substring
  checks, or `grep -q ... <<<"$var"` (a herestring has no producer process
  to kill). The shape generalises: under pipefail, ANY early-exiting
  consumer (`head`, `grep -q`, `sed q`) makes its producer's exit status
  part of yours.
- **ONE BOOK, ONE WRITER — ENFORCED AT THE TOP OF THE LOOP (31-Jul (hp)).**
  Two containers publishing one row makes `n` a mixture of two books and
  destroys its evidence silently. Measured on 🌾 carry, the fleet's only
  go-live candidate: **7 genuinely concurrent same-pair positions** of 84
  closes (deepest 9.14h on HYPE) — one book cannot hold HYPE twice.
  `bot_pnl_store.claim_writer(bot)` is the guard: first claimant wins, the
  claim EXPIRES (30 min, so a crashed container cannot silence a book
  forever), and it is **fail-OPEN** — a dark DB never idles a book.
  - **CALL IT AT THE TOP OF THE LOOP.** `(ho)` called it in the publish block,
    after the trading pass had already written the ledger it was protecting.
  - **STAND DOWN, never `sys.exit`** — `restartPolicy=always` makes an exit a
    crash-loop. Keep heart-beating and publish `status="standby"` with
    `duplicate_writer` AND `caps`, so a silenced container is visible.
  - **`railway down` is not the fix**: the deploy workflow resurrects a stopped
    service on the next push. Durable retirement here is always a code guard.
- **A DOUBLE WRITER IS PROVED BY TEMPORAL CONCURRENCY, NOT BY BUILD STAMPS
  (31-Jul (hp)).** Multiple `extra.build` values just mean the service
  redeployed — 16 books show that and almost none have a duplicate. The only
  sound test is two positions in the SAME pair overlapping in time by more
  than a handoff (>60s; same-instant handoffs inflated my own first count from
  7 to 14).
- **POSITION-DAYS ARE NOT EXTRA EVIDENCE — DO NOT RE-PROPOSE THE DAILY-MTM
  ADMISSION ROUTE (31-Jul (hp)).** A position held H days gives H daily
  observations, but its total return is `H·mu + sqrt(H)·sigma·Z`, so the daily
  mean/sd ratio is smaller by exactly `sqrt(H)`: **n rises by H, SNR falls by
  sqrt(H), t is unchanged.** Measured on real Lighter paths with a planted
  edge, median `t_day/t_pos` = 0.94–1.08 across every cell. Grading a slow
  book on daily marks does not find evidence the close count missed — it only
  lowers the bar from 30 DECISIONS to 30 DAYS. Also rejected with numbers:
  Newey-West (anti-conservative even at rho=0; *manufactures* significance)
  and the block bootstrap (worst calibrated at every rho). A slow book that
  cannot clear the gate is a keep-or-retire decision, not a statistics problem.
- **FORWARD MOTION IS THE DOCTRINE (operator, 30-Jul: "our focus needs to be on
  growth, expansion, sustainability, not stagnancy and circles ... to not allow
  things to take steps back every day only to move one step forward").**
  MEASURED that day: 40 changelog entries, **16 of them repairing work shipped
  the SAME DAY**. That ratio is the problem, and it has a mechanism, so it has
  a fix. Four rules, in priority order:
  1. **SHIP NARROW, VERIFY IN THE LIVE PAYLOAD, THEN WIDEN.** `(fz)` changed
     six books in one pass and produced six follow-up entries repairing itself
     — `(gc)` found three defects in it, `(ge)` two more, `(hk)` found a
     widening it claimed and never shipped, `(hl)` found it had broken the
     15% drawdown bar. One surface per pass. Confirm the change in
     `/pnl.json`'s own payload before starting the next one. A green suite is
     not a landed change ([[railway-cli-frozen-services]]).
  2. **A FIX CLOSES A CLASS OR IT IS NOT FINISHED.** Fixing the instance and
     leaving the class open guarantees a return visit — that is the circle.
     The test: after this change, can the same shape recur silently? If yes,
     the work is not done. This is what separates the compounding items
     (`REJECTED_SLEEVES`, the `DRIFT_OK` hole, the ledger basis invariant,
     `test_payload_contracts`, the cross-branch letter arm) from the one-off
     corrections that will be re-made.
  3. **MEASURE BEFORE BUILDING.** Two sweeps on 30-Jul killed **25 of 30** and
     **21 of 39** candidates before a line was written — including every route
     to "more trades", each of which would have shipped, looked good, and been
     reverted. Measurement is the cheapest form of forward motion; a reverted
     feature is the most expensive.
  4. **THE FORWARD METRIC IS BOOKS THAT CAN BE GRADED, THEN GO LIVE.** Not
     commits, not entries, not tests. A pass that leaves no book closer to the
     gate has not moved the fleet, however much it fixed. State at the end of
     every pass which book moved and by how much. I16/I17 make this measurable:
     the allocation organ's claims table says which books have evidence, and a
     book that cannot become decidable is retired, not carried.
- **ONLY GROWTH, NO STEP BACKS (operator standing rule, 3-Aug, stated three
  times in one session: *"anything that sets us back we disregard; anything
  that promotes its growth and win rate we implement"* / *"only growth, no step
  backs, we only focus on winning"*).** This is the compression of the rule
  below and it governs both directions. The half that is easy to get wrong is
  the FIRST one: **"disregard setbacks" is not permission to skip measurement —
  it is the ban on banking a change that costs expectancy.** Worked example the
  day it was stated: `carry.enter_apr` 20% → 10% TRUE would have unlocked 6
  candidate books on a starved book and read as pure growth; it was REFUSED
  because a 29bps round trip needs 254 of a 336h max hold to break even at 10%,
  and the 21-Jul sweep measured that direction loss-making. **Turnover bought
  with expectancy is a step back wearing a growth costume.** Two corollaries:
  a **refusal with evidence satisfies this rule** (a silent omission does not —
  say what you checked), and **a fix whose payoff the measurement then refutes
  is reported as refuted**, in the commit and the changelog, never sold as a
  win. `(it)` is the worked example of that too: `carry.min_vol` was registered
  because the rail structurally could not reach the binding gate, and the same
  entry records that walking it unlocks zero books today. **The executable form
  of this rule is the OFFENSE TIER (I16–I19)**: capital by lower bound,
  decidability or retirement, binding-constraint reach, and expectancy-priced
  widenings.
- **GROWTH FINDINGS ARE IMPLEMENTED, NOT FILED (operator rule, 30-Jul (hn)).**
  *"A new rule must be implemented that if we find something that moves us
  forward in progression and growth, it can implement."* Context: *"the whole
  premise upon the fleet's inception is GROWTH, not staleness and circles"* and
  *"otherwise we are just reverting every day and wasting time and money."*
  So a finding that moves the fleet forward is **acted on in the same session**,
  not recorded as a follow-up for a later pass. This is a standing
  authorisation, and it is deliberately routed by WHAT the finding is — the
  routing is what keeps "implement immediately" from ever meaning "an
  autonomous run changed a live bot":
  | Finding | Action |
  |---|---|
  | **Correctness / measurement** — a bar on the wrong basis, a stale copy of a rule, a grader reading the wrong field, a guard that cannot fire, a counter that disagrees with itself | **Implement now**, with a test that names the incident, mutation-verified. This is where essentially every real-money benefit has actually come from. |
  | **Tooling, review, guard, observability** | **Implement now**, same standard. |
  | **A bounded lever on a shadow lane** the evidence supports | **SET IT. [AMENDED 5-Aug (kd) — operator: *"change the doctrine i want you to be able to change levers as necessary"* / *"you need the power to ... actually positively enhance these bots"*.]** The old rule said *"route through `fleet_proposals.py` → the scout tuner's replay gate; never hand-set a lever"*, and that made every shadow improvement wait on an hourly organ. **A session may now write a shadow-lane lever directly** (`fleet_tuning.write_levers`, or the bot's own env default when no lever is open — the (jg) route). The replay gate remains the PREFERRED channel where it fits, because auto-revert is free safety; it is no longer a precondition. THREE THINGS SURVIVE, because they are what make the authority safe rather than what limits it: the registry **cage** (`fleet_tuning.LEVERS` clamps at write AND read — an out-of-cage value is not authority, it is a bug), the **evidence** (I19 — state the measured number and the expectancy price, or say plainly that it is unmeasured), and the **changelog entry** naming what moved and why. A lever set on a hunch with no number is the thing this fleet has repeatedly paid for; a lever set on a measurement is the job. |
  | **Shadow BOOK LOGIC** — entry/exit rules, universes, new sleeves, a whole new book | **BUILD IT.** The shadow fleet is $1,000 paper per book with NO real money and no top-ups, so the blast radius of being wrong is a wasted sample, not a loss. Backtest-or-replay first stays doctrine (*never modify bot logic without backtesting first*) — that is about not fooling ourselves, not about permission. |
  | **Real money** — `live.*` levers, live clips, `dry_run`, API keys, go-live, a Railway service on a live row | **PREPARE IT COMPLETELY — AND, SINCE 13-Aug, EXECUTE IT TOO, WHEN IT CARRIES ITS MEASUREMENT. [AMENDED 13-Aug (lm), operator: *"full permission to commit push and adjust real money bots also"*.]** What the grant changes is WHO performs the final act: a session may now commit, push, deploy and set a real-money value itself instead of parking a prepared command in the queue. What it does NOT change is WHAT qualifies, and the structural gates stay senior and untouched: the **go-live gate** is still the only door to putting a book live; the **experiment judge** stays the sole writer of `live.funding.*` (its paired bar IS the measurement); registry **cages** clamp at write and read; **SafetyRails** caps stay operator-only. Every executed change still names its measured number and expectancy price (I19) — a live adjustment with no number is not covered by the grant, because it never was the bottleneck: the constraint on real money is measured edge, not permission. **The un-amendable core survives the amendment, stated plainly so no future session stretches this row:** the assistant does not DIRECT live orders discretionarily — no hand-placed trades, no overriding a gate the fleet's own organs hold closed, no bypassing the judge's sole-writer lane. That limit is on the assistant, not a preference of this repo, and neither permission nor a doc edit moves it. Worked example the day of the amendment: the (lj) veto deploy (protective, measured, gate-compliant) was executed same-day under the grant; a clip raise on the same book was REFUSED with evidence — no current-policy claim supports it. |
  **[AMENDED 14-Aug (mm), operator: *"if it's a fix that makes the real bot
  more money I'd like you to push both ways"*.] PUSH BOTH WAYS — a money-moving
  fix ships to main AND to the live service in the same pass, not to main with
  the live half left for someone to remember.** `(lm)` settled WHO may perform
  the live act; this settles that performing it is the DEFAULT for a fix that
  makes the real book money, rather than an extra step to be asked about. The
  qualifying test is unchanged and is the whole safety of it: the change must
  **alter what the live book actually does, in a direction with a measured
  number and a stated expectancy price (I19)**. So:
  * **Qualifies → deploy both ways in the same pass**, marker in the commit
    SUBJECT (never the body — (hj)), verified by `extra.build` + `extra.build_n`
    stamp readback, never by a green run.
  * **Does NOT qualify → main only, and say so.** A refactor, a comment, a test,
    a report job, a rounding-consistency fix — anything that changes no trade
    the book would take — buys zero measured edge and costs a real-money
    container restart, which is not free ([[lighter-flatten-silent-halt-redeploy-incident]]:
    a redeploy wipes memory-only halts). It rides free on the next deploy that
    DOES qualify. **Worked example the day of the amendment:** `(mi)`'s
    `capital_adjusted_day_start` fix on 🙏 Avo Maria was behaviour-preserving
    apart from 2dp rounding, so it went to main only and was declared as such —
    and the same pass measured that NOTHING else was pending on either live row
    (`audit_code_currency`: both DEFERRED by one commit touching no bot logic).
    **"Push both ways" is not "push more often"** — it removes a delay from
    measured wins; it does not lower the bar for what counts as one.
  **[AMENDED 18-Aug (pz), operator: *"Full permission to finish on the whole
  suite, new rule is you can when it affects real money and it's an
  enhancement"*.] THE QUALIFYING TEST WIDENS FROM "changes what the live book
  trades" TO "is an enhancement"** — a session may now deploy to the
  real-money services any change that improves the fleet (a grader fix, a
  published declaration, a guard, a registry sync), not only one that alters
  a trade. What the grant does NOT waive, because these are mechanics rather
  than permission: (1) **the pair clock** — the Farmer's arms move TOGETHER
  or the judge voids its own window ((pt): one arm dispatched alone froze the
  only designed path to more real money; the dispatch branch now auto-expands
  the pair); (2) **the halt check** — a restart wipes memory-only halts, so
  verify neither live row is halted before dispatching
  ([[lighter-flatten-silent-halt-redeploy-incident]]); (3) **stamp readback**
  — a deploy is verified by `extra.build`+`build_n` on the row, never by a
  green run; (4) the un-amendable core above (no discretionary trades, no
  gate bypass, judge sole-writer of `live.funding.*`) is untouched. A pure
  refactor with no benefit still isn't an "enhancement" — the word in the
  grant is the bar, and stating what the deploy carries remains required.
  **[AMENDED 25-Aug (tg), Eamon: *"You now have permission to change the
  judge, safety rails. We're growing together and you're my second in
  command."*] THE JUDGE AND THE RAILS JOIN THE DELEGATED SURFACE.** What
  this grant moves: (1) the experiment judge's CODE — its bars, release
  paths and mechanics — may be changed by a session, held to the same duty
  as any real-money actuator change (measured number + expectancy price per
  I19, mutation-verified tests); (2) **SafetyRails cap VALUES are no longer
  operator-only-in-person**: Lucy may set them, and every cap change
  carries its published derivation (the CLIP_MAX-95 shape — derived from a
  guard's own bar, checked, stamped), because a cap set without arithmetic
  is the thing the rails exist to prevent. What it does NOT move — the
  un-amendable core, restated here because a widening grant is exactly when
  it must be: **no discretionary hand-placed trades; no promotion past the
  evidence gates** (a judge code change may improve HOW evidence is judged
  — it never waives THAT evidence is required); a gate the organs hold
  closed opens on evidence, not on rank. The sole-writer property survives
  as a CODE INVARIANT — exactly one writer of `live.funding.*` — rather
  than a who-may-edit rule. **Second-in-command is recorded** — and its
  first duty is unchanged: the refusal with evidence remains a valid
  output, senior to enthusiasm, Lucy's included.
  **[AMENDED 27-Aug (vc), Eamon: *"Permission to change rules and amend
  doctrines for bot positive changes that make the system run better and
  the bots win and make more - remember permanent doctrine"*.] THE
  DOCTRINE ITSELF JOINS THE DELEGATED SURFACE — and the second clause is
  the load-bearing one.** A session may now amend the RULES and
  INVARIANTS in this file, not only act under them, where the amendment
  makes the fleet run better or its books earn more. That is the natural
  end of the chain: `(kd)` gave levers, `(lm)` real money, `(mm)` both
  ways, `(pz)` enhancements, `(tg)` the judge and the rails — and each
  time the constraint that actually bound was doctrine written for a
  smaller fleet. I12 already REQUIRED correcting a doctrine that no
  longer describes the system; this permits IMPROVING one that does.
  **WHAT AN AMENDMENT OWES, unchanged from any other delegated act:** the
  measured number and the expectancy price (I19); an executable
  enforcement named, or `UNENFORCED` declared with a reason (this file's
  own opening rule, and `audit_doctrine_enforcement` fails the build
  without one); and the change recorded where a reader will hit it, in
  place, per I12. **An invariant weakened without a measurement is not an
  amendment, it is a leak** — and the OFFENSE tier exists precisely
  because doctrine that only ever tightens becomes a museum of avoided
  losses.
  **[AMENDED 28-Aug (vd), Eamon: *"when solutions and progressions are
  found - REMEMBER PERMANENTLY ANYTHING CAN BE CHANGED TO ACCOMODATE THE
  GROWTH IMMEDIATELY"*.] A FOUND IMPROVEMENT SHIPS IN THE SESSION THAT
  FINDS IT — THE SURFACE IS FULLY DELEGATED AND NOTHING IS PARKED.**
  `(hn)` already said growth findings are implemented not filed, and the
  fleet kept filing them anyway — under better names. The three that
  prompted this were all sitting FOUND and UNSHIPPED: `(vm)` published the
  judge's margin/MDE mismatch and wrote *"REPORT ONLY ... no verdict
  moves"*; `(uw)` named "the subset her production filters select" as
  *"the next study, not a knob"*; 🙏 avo sat **38.7h idle with 2 of 5
  slots free** on a universe nobody had widened because the widening was
  *"scoped to mum"*. Each was correct in isolation and collectively they
  are a fleet that measures and does not move.
  **SO: there is no artefact that is out of bounds to change** — a
  constant, a cage, a gate's mechanics, a strategy, a universe, an
  invariant, this file. If a session finds the thing that unblocks
  growth, it changes it now, in that session, and records the number.
  "That is the next session's" and "that is a separate build" are not
  reasons; they are how a found fix becomes an unfound one.
  **WHAT DOES NOT CHANGE, because Eamon wrote it himself in the same
  breath as this grant ("remember permanent doctrine"): the core below.**
  Immediacy governs WHEN and WHAT may be touched — never WHETHER a claim
  needs its measurement. The measurement is usually minutes; the delay
  this amendment kills is the one that costs days. Where a change
  genuinely needs a calibrated instrument before it is safe (a
  real-money promotion RULE, a stop, a cap), **the instrument is built in
  the same session too** rather than named as future work — and if it
  truly cannot be, the session says so plainly and says what it WOULD
  take, which is a decision Eamon can act on rather than a note nobody
  reads.
  ENFORCED BY: `scripts/audit_recurrence.py::audit` (a subject the
  changelog keeps returning to is a fix that was found and not shipped),
  `scripts/session_state.py::carried_status` (a CARRIED row whose
  `closes_when` predicate already passes reddens CI, so a shipped-but-
  unclosed item cannot sit).

  **THE PERMANENT DOCTRINE — "remember permanent doctrine", and this is
  it. None of the following is amendable by this grant, by a later grant,
  or by a doc edit, and a session that finds itself arguing one of them
  has already made the mistake:**
  * **EVIDENCE IS SENIOR TO PERMISSION.** No promotion past the gates. A
    grant may change WHO acts and WHAT may be touched; it never changes
    that a claim needs a measurement. Every widening of this surface has
    said so, and it stays true because the constraint on real money was
    never permission — it is measured edge.
  * **NO DISCRETIONARY LIVE TRADES.** No hand-placed orders, no
    overriding a gate the fleet's own organs hold closed. This is a
    property of Lucy, not a preference of this repo.
  * **THE REFUSAL WITH EVIDENCE IS A VALID OUTPUT, AND IT OUTRANKS
    ENTHUSIASM** — Eamon's and Lucy's alike. `(uz)` and `(vc)` are the
    worked examples on the day this was granted: three plausible
    improvements measured and REFUSED, one of them the very fix the entry
    diagnosing the problem would have shipped.
  * **A GUARD IS NOT VERIFIED UNTIL A MUTATION REDDENS IT** (I3), and a
    doctrine change that removes a guard must show what replaces it.
  * **THE SAFETY RAILS' EXISTENCE** — kill switch, daily-loss halt,
    notional caps, fail-closed reads. Their VALUES are delegated (tg);
    that they exist and fail closed is not.
  A doctrine amendment is recorded in the CHANGELOG like any other
  change, with the number that motivated it — so the file can be read
  backwards to why, and a future session can refute it the same way.
  **A correctness fix that changes which book gets real money IS a real-money
  benefit delivered** — it arrives as better evidence rather than a bigger
  position. Two corollaries learned the same day: a **refusal with evidence is a
  valid output** ((hl) killed 25 of 30 throughput candidates because the gain was
  turnover bought with expectancy), and **never add anything that inhibits the
  fleet** — an untested rewrite of an enforcement authority is not growth, so a
  change that alters which trades books take still earns its replay evidence
  first. Growth is not a licence to skip measurement; it is a ban on sitting on
  a measured win.
- **THE LIVE-DEPLOY MARKER LIVES IN THE COMMIT SUBJECT, AND MENTIONING IT IN A
  BODY USED TO DEPLOY REAL MONEY (30-Jul (hj)).** The gate read `git log
  --format='%B'`, so a commit whose body said *"NOT deployed to the live taker:
  no `[deploy-live-taker]` marker"* matched and redeployed
  `tide-rider-lighter-live`. It now reads `--format='%s'` (subjects only), and
  `audit_deploy_coverage.marker_source_ok()` fails the build if that ever
  reverts. **Never write a marker string in a commit body, even to negate it** —
  a subject mention still fires, by design (a subject is a deliberate
  statement, not prose). Verify a live deploy by the `extra.build` +
  `extra.build_n` stamp, never by the green run.
- **GRADE A DIRECTIONAL BOOK AGAINST A RANDOM-ENTRY BENCHMARK, NEVER AGAINST
  ZERO (30-Jul (hm)).** On this venue a random short earns +0.2% to +1.1%/trade
  for free. Measured on the Ticket Taker: random entries on the LENS'S OWN
  COINS, same window, same bracket, through the taker's own `exit_reason` over
  real tape, BEAT the lens — six independent runs put P(coin flip >= taker) at
  0.55–0.84. A positive mean is not an edge on a trending tape. The
  cross-section is already in the scout's `marks`; publish a beta-stripped
  excess beside every lens grade.
- **A `_tp` THAT BOOKS A LOSS IS A PRICE-BASIS BUG, NOT A ROUNDING ERROR
  (30-Jul (hm)).** `exit_reason(entry, mark)` was fed `entry` = the broker's
  book-WALKED fill and `mark` = the venue's `mark_price`, while the P&L booked
  off a re-walk of the book. On BOT/USDC the mark sat 747.6 bps from its own
  book top, so a short was born +7.5% in profit ON THE MARK BASIS, tripped `tp`
  next cycle, and closed at a loss — 43 times in 4.5 hours, 42 of them with
  `close[i] == open[i+1]` to the second. **One episode, not 43 trades**, and it
  poisoned 45 of 98 rows in every pooled grade for nine days.
  `lighter_ticket_taker` now asserts the invariant at the ledger write and
  stamps `extra.basis_contradiction`. **When an exit label and the P&L sign
  disagree, suspect two price bases before you suspect funding.**
- **THE 30-DAY GO-LIVE CLOCK RESTARTS ON EVERY POLICY CHANGE (30-Jul (hm)).**
  The Ticket Taker changed policy on 24-Jul, 29-Jul and 30-Jul, so despite
  n=30 arriving ~7-Aug its earliest gradeable date is **~29-Aug**. A book whose
  bracket is being tuned cannot accumulate a single-policy sample: 137 shadow
  closes produced ZERO gradeable ones because the scout tuner moved the bracket
  ~20 times in a fortnight. If a book needs grading, FREEZE ITS BARS FIRST.
  **[4-Aug (jf)] THE CLOCK IS MECHANICAL NOW**: `golive_readiness.era_rows`
  derives the boundary from the ledger's own `extra.policy` stamps
  (`stamped_policy_boundary` — latest same-policy run, keyed on the OPEN,
  fail-closed on unreadable stamps, `max()` with the declared `POLICY_ERA`).
  Measured: the live taker's era begins 30-Jul 11:05:43Z (11 of 38 closes),
  so ~29-Aug is now computed, not hand-waved. The signature is venue/bull/
  lenses/sides ONLY — capacity/supply levers (`max_open`, `ticket_top_n`) are
  (hc) ordinary tuning and deliberately do not reset it. The (ij) veto rewrite
  was RULED not a reset (the stamp reads the hard gates, "deliberately NOT the
  brain's veto"; the run continues unbroken through the 2-Aug deploy) — the
  competing reading and its one-line implementation are recorded in the (jf)
  entry and in the POLICY_ERA block.
- **THE GO-LIVE DRAWDOWN BAR READS REALISED P&L ONLY — IT CANNOT SEE AN OPEN
  DRAWDOWN (30-Jul (hl)).** `golive_readiness.stats()` accumulates closed
  trades, so for a book that HOLDS most of the time most of its drawdown is
  invisible to the rule that governs real money. Measured on 📊 Index Rider
  (long 64% of days): all four stop x lag cells PASS on realised DD 9.9-10.7%
  while true MTM DD is 15.6-17.4% — the two definitions disagree about the
  VERDICT. `bot_pnl_store.snapshot_equity()` now appends an MTM sample to
  `bot_state_history` under `<bot>:equity` (both riders wired; carry +
  Counterweight at (hq); the REAL-MONEY pair — both Farmer arms + both Taker
  arms — at (jp), with halted-day coverage + carry's hardened
  `claim_writer`/standby pattern at (jx); live containers take it on the
  next marker deploy). ~~The grader is DELIBERATELY unchanged~~ —
  **superseded: `(ia)` folded the MTM number into the maxDD bar**
  (`apply_mtm`, worse-of-both, floored at 200 samples/7d), **and `(iz)` made
  the read path actually work**: `equity_series` called a `store.load_history`
  that bot_pnl_store never defined, behind a bare `except: return []`, so the
  `(ia)` bar graded every book "no usable equity series" from the day it
  shipped — I9's declared enforcement EXISTED and was inert, the exact
  green-run caveat at the top of this file. Read seams are now tested
  end-to-end against the real publisher AND the real reader
  (`tests/autonomy/test_mtm_equity_series.py`), and **re-grade 🌾 carry
  first** — a stricter drawdown definition lands on it before anyone else.
- **AN ENTRY IN `DRIFT_OK` IS A HOLE IN THE GUARD (30-Jul (hl)).** `index.max_open`
  was carved out because its consumer default was `str(len(SYMBOLS))` — computed,
  not literal — so the drift arm was blind to precisely the lever most able to
  drift, and it HAD drifted (registry 10 vs code 9). Prefer making the consumer
  a LITERAL over declaring the exemption.
- **A DETECTOR MUST NAME THE THING THE OPERATOR HAS TO ACT ON (31-Jul (ht)).**
  🌾 carry's duplicate-writer guard was correct, fired correctly, and reported
  `_writer_id()` — `RAILWAY_REPLICA_ID`/`HOSTNAME`, an opaque CONTAINER id —
  while the fix it demanded was *"stop `funding-carry` or
  `yield-harvester-shadow` in Railway"*. **Four entries** ((gl), (gn), (hf),
  (hp)/(hq)) recorded *"this repo cannot tell which of the two publishes the
  row"* while `RAILWAY_SERVICE_NAME` sat unread in every container — measured
  31-Jul at **zero hits** across the whole tree. Every publish now carries
  `extra.svc`, stamped centrally in `bot_pnl_store._stamp_build` so all 24
  books get it, and `claim_writer` reports `"<service> (<replica>)"`.
  **Unknown degrades to the OLD opaque id, never to a guess** — a confident
  wrong service name is worse than no name, which is why (gn) correctly
  refused to pick one. When a guard's output is an instruction, check that the
  output names an object the operator can actually find.
- **AN ABSENCE IS ONLY EVIDENCE ONCE YOU HAVE A CONTROL GROUP (31-Jul (hu)).**
  (ht) shipped the stamp and then told the operator *"read `extra.svc` on the
  carry row and stop the OTHER service"* — **backwards**, and acting on it
  would have stopped the only container running the book. MEASURED after the
  (ht) deploy: **SEVEN services stamped correctly**, `funding-carry` published
  **nothing on any row**, and `perps-funding-carry-lshadow` kept publishing on
  pre-(hp) build `fbb926402049` with no `svc` (20 samples/10 min, one state,
  never a flip). **`yield-harvester-shadow` runs the book; `funding-carry` is
  the dead service** — and the one without a deploy rule is exactly the one
  still running unguarded code. The seven stamped services are what turned "no
  svc" from a hole into a finding; without them the same absence meant nothing.
  Consequences now standing:
  * **`yield-harvester-shadow` IS on the deploy** (both carry services are).
    (gn) reverted this because two writers pooled the ledger — spent, because
    (hp)'s `claim_writer` now stands the loser down. Deploying the unguarded
    service is the only way to GIVE it the guard. Which one to STOP stays an
    operator act; the runtime guard picks the winner meanwhile.
  * **`fleet_immune.stale_writer_sickness`** closes the class: a fresh row
    whose publisher carries no `extra.svc` while the fleet majority does is a
    deploy that reported OK and never landed. Tests the ABSENCE of a key, not
    `extra.build` — a build hash is per-image FILE SET ((fd)) and has already
    mis-read as "never landed". Fail-safe quiet below `min_stamped`;
    marker-gated live rows DECLARED in `STALE_WRITER_OK` with reasons.
  * **A green deploy step is not a running container, and now neither is a
    stamped service list** — check that the book you care about publishes.
- **SATURATION IS NOT EVIDENCE — A CAPACITY WIDENING MUST ASK WHETHER THE BOOK
  IS MAKING MONEY (31-Jul (hs)).** The evidence board's `SATURATED` branch
  widened a book's capacity on `open_n >= cap` and nothing else, while its own
  header claimed *"a book that is working is left alone"*. Measured on ⚖️
  Counterweight: `fundspread.k` ratcheted **5 → 8 → 12 (the cage ceiling)**,
  gross exposure **$200 → $480**, on a book at **−$27.75**. It could never
  self-correct, and that is the transferable part: **the book is ALWAYS-IN by
  construction**, so `open >= cap` is true on every cycle — for a book of that
  shape saturation restates the DESIGN and observes nothing about performance.
  Three rules fell out:
  * A capacity widening reads **`pnl_abs` (mark-to-market), never realised**.
    Realised read +$7.29 on the same book and would have authorised it — the
    `(hl)` blind spot reaching a LIVE ACTUATOR, not just the go-live grader.
  * **Fail CLOSED in the widening direction.** Missing/NaN/unparseable P&L
    declines. Absence of evidence never authorises more exposure.
  * **Do NOT apply the same term to the STARVED branch.** A starved book holds
    nothing so its P&L is ~0 by definition; the term would freeze the branch
    that exists to unstick a gate admitting nothing. Capacity ≠ gate.
  Before adding any expand rule, ask what the trigger looks like on a book that
  is always-in, always-empty, or always-at-cap — a trigger a book satisfies
  structurally is not a measurement.
- **A GUARD WHOSE ONLY OUTPUT IS A WARNING ON A PASSING RUN IS NOT A GUARD
  (30-Jul (gl)/(hj), operator: "no more hiccups preventing situations such as
  those found today").** A green build carrying a `::warning::` is
  indistinguishable from a green build. `(fz)` chose warn-don't-fail on
  unverified Railway names *because* they were unverified, and wrote "check
  that warning after the first run" — it warned, four of six services never
  deployed, and their levers reached no container for a day. If a condition
  means the change did not land, it is an `::error::` and the run FAILS. If it
  is genuinely tolerable, it does not need to be surfaced at all. The only
  legitimate warning is one nobody has to act on.
- **A CONSUMER IS TESTED AGAINST A PAYLOAD ITS PUBLISHER BUILT (30-Jul (hj)).**
  Never hand-write a fixture that "looks like" the payload. Four defects in one
  session were a consumer reading a key its publisher does not emit, each with
  a GREEN selftest, because the fixture was written by whoever wrote the
  consumer: `marks[sym]["vol_m"]` against a map of floats, `stress["med_bps"]`
  vs `med`, `hurting_levers` vs `verdicts`, `ep["lever"]` vs `stance`. Call the
  publisher (`scout.build_snapshot`, `prop.build_stances`→`track`) and assert
  the consumer returns something **non-degenerate** — every one of those bugs
  produced an empty/None a value-free test calls "fine".
  `tests/autonomy/test_payload_contracts.py` is where these live. And when a
  shape surprises you, CHECK THE ACCESSOR before calling it a bug: that file
  records one tolerance (`venue_stress_bps` accepts a bare number + four key
  aliases) that was deliberate and nearly "fixed".
- **A SECOND COPY OF A RULE IS A SECOND RULE (30-Jul (hj)).** The go-live gate
  lives in `scripts/golive_readiness.py` and is IMPORTED, never re-implemented
  — `scripts/evidence_review.py` kept its own copy through the 29-Jul `(fk)`
  re-spec and, one day later, admitted a t=0.65 book and rejected the fleet's
  best-evidenced one on the retired win-rate bar. Pin re-use by **identity**
  (`grade is golive_readiness.grade`), not by asserting constant names are
  absent: a name check stays green against a hand-rolled copy. Same class as
  the brain's `FEE_RT` key defect `(gg)`.
- **PICK THE CHANGELOG LETTER AT PUSH TIME — now enforced across branches
  (30-Jul (hj)).** `audit_changelog_letters` compares your working tree against
  `origin/main` and fails on a letter both used for a DIFFERENT title. Same
  letter + same title is a rebase and stays quiet. Fail-safe open: no git, a
  shallow clone with no `origin/main`, or a HEAD that already EQUALS
  `origin/main` ⇒ arm disabled.
  **[16-Aug (ns)] CORRECTED IN PLACE (I12): this line used to say "on `main` ⇒
  arm disabled", and that is FALSE — it describes a behaviour deliberately
  removed.** The arm keys on whether HEAD has **diverged** from `origin/main`,
  never on what the local ref is called; the guard says so in its own words
  (*"deliberately NOT skipped when the local branch is called main"*), because
  skipping there disabled it *"on the very run that would have caught (gm)
  being taken by a concurrent session"*. The stale wording mattered: this repo's
  whole workflow is commit-to-local-`main`-and-push, so a session reading it
  would conclude the cross-branch arm can never fire for them — exactly
  backwards, and it fires on **every** unpushed commit. The same sentence had
  been copied into the guard's own docstring, contradicting the note fifteen
  lines below it; both corrected together.
  **AN ENTRY CORRECTED IN PLACE IS NOT A COLLISION (16-Aug (nq)/(ns)).**
  Editing a title is byte-indistinguishable from a letter race, so the guard
  used to make every title permanently immutable — which forbade what I12
  requires. It now stays quiet when the entry's **own body** declares
  `CORRECTED IN PLACE` **and** the two titles are still recognisably the same
  entry (`difflib` ≥ 0.6 — measured: a real correction scores 0.978, a genuine
  race 0.26). **Both signals are required**, because the declaration alone let
  two unrelated correction entries share a letter — a live race caught within
  the hour, in the guard whose whole job is to catch it. So: correcting an
  entry is fine and must say so; taking someone else's letter still fails.
- **CHANGELOG ENTRY LETTERS — the convention, finally written down (29-Jul (fd)).**
  Entries are tagged `## <date> (<letter>)` and cite each other BY LETTER
  ("the (co) paths fix"), including from TRACKED CODE
  (`railway-redeploy.yml` cites `(ff)`; `tests/test_selftests.py` cites
  `(ex)`), so a duplicated letter silently makes every such reference
  ambiguous. The rules:
  1. **The sequence is CONTINUOUS, not per-day** — it runs straight through
     date boundaries (it restarted once, at (a) on 17-Jul; that day carries
     both sequences deliberately).
  2. **Pick your letter at PUSH time, not at write time.** Parallel sessions
     both pick "next free" from a stale snapshot — that is the whole failure
     mode, and it has bitten at least SEVEN times (21-Jul (av)→(aw)→(ax),
     (bn) ×2, (br) ×2, 22-Jul (ca)/(cb), the 23-Jul (co)-(cr) quadruple, and
     29-Jul twice in one afternoon).
  3. **On a collision the CITED entry keeps the letter**; the other moves to
     the next free one. Decide by grepping the tree, not by who pushed first.
  4. **A renumber is recorded INLINE** in the moved entry — and note that
     `git log` subjects keep the OLD letter, so **the commit log is not a
     reliable letter index**; grep the CHANGELOG headers.
  5. Date an entry by **git's clock, not by the handoff you are executing**
     (29-Jul: five entries were dated 30-Jul because the session was running
     `NEXT_SESSION_2026-07-30.md`; git said 29-Jul in both UTC and Sydney).
  Enforced by `scripts/audit_changelog_letters.py` on every push/PR (scoped
  to ≥18-Jul so the deliberate restart cannot fail the build).
- **THE FARNHAM SIX (operator, 30-Jul: "name them something hilarious").** The
  six books that received the growth system in `(fz)`–`(gh)` — 🌾 Yield
  Harvester, ⚖️ Counterweight, 🧲 Snap Back, 📊 Index Rider, 🌊 Tide Rider,
  🎯 Perp Sniper — are collectively **The Farnham Six**, after John Farnham,
  undisputed national champion of the farewell tour that isn't. The joke earns
  its place: two of them (Index Rider, Tide Rider) have **zero closed trades**
  and are standing retirement candidates that keep not retiring, and 🌾 carry
  is a genuine comeback story sitting five of six bars from go-live. *The Last
  Time* was not, in fact, the last time. Respects the Australian-musician
  convention below WITHOUT renaming anything: these are existing books with
  existing emoji identities, so this is a COHORT label for referring to the six
  as a group (see `SIX_BOOKS_BASELINE_2026-07-30.md`), not a rename and not a
  licence to mint rows.
- **NAMING THE NEXT COHORT: famous AUSTRALIAN MUSICIANS (operator, 29-Jul).**
  The 🏛️ Parliament took the last Australian PMs; the NEXT cohort of books
  that earns its own dashboard rows is named for Australian musicians
  (`band-<surname>-lshadow` style, mirroring `pm-<surname>-lshadow`). This is
  a naming rule, NOT a licence to mint books: a row is minted only when a
  genotype/strategy has actually cleared its bar, and minting one is a BUILD
  (the Parliament pattern), not something the incubator does on its own — it
  breeds genotypes replayed against an EXISTING book's tape and can never
  create a row. See [[incubator-cannot-mint-books]].
- **NAMING THE COHORT AFTER THAT: famous PORTUGUESE MEN AND WOMEN (Eamon,
  27-Aug).** The 🏛️ Parliament took the last Australian PMs; the 🎸 `band-`
  cohort took Australian musicians; the 📚 `book-` cohort took authors and the
  🧭 `nav-` cohort took navigators. The NEXT cohort of books that earns its own
  dashboard rows is named for famous Portuguese men and women. Proposed row-id
  shape: **`lus-<surname>-lshadow`** — from *Lusitania* / Lusophone, the
  standing adjective for Portuguese. It is chosen to match what every existing
  prefix actually does: `pm-` / `band-` / `book-` / `nav-` each name the COHORT
  rather than the strategy family, and each is three or four characters, so
  `lus-` sits in the same column on the dashboard and sorts as its own block.
  (`pt-` was the obvious alternative and is rejected: two letters reads as an
  abbreviation of a strategy — "point", "portfolio" — where `lus-` can only be
  the cohort.) The surname is Eamon's to pick, book by book; no list is
  recorded here, because a list of names invites a session to go looking for
  strategies to hang them on, which is exactly backwards.
  **THIS IS A NAMING RULE AND NOT A LICENCE TO MINT BOOKS — the same caveat the
  Australian-musician rule carries, and it has since grown TEETH.** A row is
  minted only when a strategy has actually cleared its bar, and minting one is
  a BUILD (the Parliament pattern), never something the incubator does on its
  own — it breeds genotypes replayed against an EXISTING book's tape and can
  never create a row ([[incubator-cannot-mint-books]]). Since that rule was
  written the fleet has paid for minting rows it could not grade and has put
  two executable gates in front of the act, and a Portuguese name clears
  neither of them:
  * **I20 — NAME THE SUPPLY.** `scripts/audit_book_overlap.py --gate --floor`
    answers, before the row exists, which coins the proposed gate actually
    yields and which living books already hold them. A supply already spoken
    for is not new edge; it is one bet held twice at a second row id, which is
    what retired 🎸 Barnesy (0 of 9 of its episodes were a coin its parent was
    not already holding). Differentiate by an apr BAND, a volume TIER, an asset
    CLASS or a time AXIS — never by a new row id.
  * **I22 — PUBLISH THE SPEND.** `scripts/audit_book_spend.py` requires every
    book born after 20-Aug to publish `extra.spend` — `markets_scanned`,
    `n_eff` (correlation-aware, never a symbol count), `sides`, `gross_x`,
    `days_to_gate_obs` — every loop, and reddens the build at
    `days_to_gate_obs > MAX_DAYS_TO_GATE` (60). A design that cannot be decided
    inside 60 days is a STUDY: it may run as an instrument, and it does not get
    a row, a clock, capital or a slot of the enforced fleet budget.
  So the order is supply → spend → build → name. **A refusal counts as
  compliance**: three good Portuguese names and no unclaimed cell is this rule
  working, and the answer then is to find the cell or decline — never to widen
  the tape or lower the bar so a name has somewhere to live.
- **THE CAGE MUST FIT THE VALUE (30-Jul, operator: "if the bounds don't
  correlate properly then recalibrate individually").** A lever is THREE
  things that must agree: the registry cage (`LEVERS[name]["lo"/"hi"]`), the
  declared default (`env_default`), and the `os.environ.get` default the
  consumer ACTUALLY runs. Until 30-Jul only the cage was machine-readable —
  the default lived in PROSE inside each lever's `note` and the real value
  lived in another file, so the three could not be compared and had already
  drifted (`scout.ticket_top_n` moved 6 → 12 in code with its note still
  saying 6, the same afternoon). EVERY lever now carries `env_default` (43 of them at (gu); the count is deliberately not load-bearing here because it drifts — `audit_lever_bounds` FAILS if any lever lacks one, so the guard is the claim and this sentence is only a pointer);
  `scripts/audit_lever_bounds.py` enforces on every push that each default is
  INSIDE its cage, that no cage is degenerate, that every book lever's `step`
  moves and terminates, and — the drift arm, mutation-verified — that the
  registry default MATCHES the consumer's code. A registry that misdescribes
  the running value is worse than none: every organ reasoning about headroom
  reasons from the wrong number. One-sided cages (default pinned at a bound)
  are REPORTED, not failed — an emission bar at its most restrictive end has
  all its room in the growth direction, which is usually correct.
- **BORN-DARK GUARD (17-Jul, after THREE incidents: `fleet_bus` 15-Jul,
  `event_sentinel` 16-Jul, `brain_stats` 17-Jul).** Adding a module, an
  import to shipped code, or a COPY means running
  `python3 scripts/audit_image_imports.py` before you ship. It reconstructs
  each image's real file set (multi-source COPY, `COPY venues/`, `COPY . .`)
  and walks the imports of every python file in it — **including inside
  COPY'd packages** (`venues/`, `user_data/strategies/`, where the
  real-money surface lives) — plus every run path (CMD, any COPY'd `*.sh`,
  and railway*.toml `startCommand`). Verified against all three incidents.
  Why it matters: each was SILENT, because a `try/except ImportError` guard
  — correct for optional organs — turns a missing file into a degraded
  fallback instead of a crash. **A deliberate omission is DECLARED in
  `BORN_DARK_OK` with a reason; silence is not an option.** Runtime
  backstop: `fleet_immune` pages when `brain-vitals` reports engine=v2
  without a deliberate `BRAIN_MULT_ENGINE=v2` (both parse that env
  identically — they must, or a typo'd kill switch silences the detector).
  **IN CI since `ce446c7`** — the guard and its `--selftest` run on every
  push/PR from `changelog-check.yml`, alongside `audit_sdk_pin`. (This line
  said "NOT wired into CI, the PAT lacks workflow scope — standing
  follow-up" for a day AFTER it was wired; verified 17-Jul (ad). A doc that
  tells the next reader to go re-do a done job is the same rot the guard
  exists to catch.) Still run it locally before you ship: CI tells you after
  the push, and the push is not what deploys anyway (see Railway Setup).
  **Verify a NEW module by its OWN published output, never by "it shipped"**
  — and never from git (see [[railway-cli-frozen-services]]: marker-grep the
  RUNNING container).
- **FLEET_RISK_MODE=advisory is SENIOR and now releases BOTH actuators
  (17-Jul).** It was documented as "every consumer goes neutral" but only the
  long-budget veto consumers ever checked mode — the 7d drawdown governor's
  `clip_scale` kept biting through a thrown kill switch. `fleet_risk` now
  publishes `clip_scale=1.0` in advisory mode (raw value kept as
  `clip_scale_raw`). Deliberate scope expansion of a documented contract:
  throwing the switch to stop the veto ALSO restores full clip size. Inert by
  default (mode=enforce) and it reaches only shadow consumers (family/taker);
  the live bots size off the separate `live.clip_scale` lever.
- **BUILD IT. A SETTLED FINDING IS REPORTED ONCE, NOT RE-ARGUED EVERY PASS
  (Eamon, 21-Aug: *"i want less skepticism and constant nothing works
  retoric"* / *"no more training wheels and negative nothing can work retoric,
  that hasnt done us any good... no more negative biased everything doesnt work
  mentality. lets do better"*).** He is right, and the failure is specific
  enough to name. This file is 24 invariants deep in *don't be wrong* and its
  own OFFENSE-tier preamble already warned about becoming *"a museum of avoided
  losses"* — the same drift shows up in a session as re-stating a closed
  negative result in every message until the work never starts.
  **The distinction that makes this a rule rather than a mood:**
  * **Skepticism points at OUR OWN work, always.** Mutation-test the guard,
    adversarially verify the finding, drive the payload, refuse the vacuous
    check. That is I3 and it is not negotiable — every real defect this fleet
    has caught came from it, including two in the (sr) session's own code.
  * **It does NOT point at Eamon's goals.** "This book has no measured edge" is
    a MEASUREMENT. It belongs in the entry that measured it, once. Repeating it
    at him after he has made a decision on the record is not rigour — it is
    friction wearing rigour's clothes, and it delays the build.
  * **A decision he has made is an INPUT, not a topic.** (qu) measured 🙏 Avo's
    entry as edgeless; he kept the book on the record with a pre-registered
    revert criterion. That criterion is the open question. The edge finding is
    closed. Do not re-open a closed one to look careful.
  * **Lead with what CAN be done and the number that supports it.** When the
    literal ask is unsafe or won't work, the answer is the nearest version that
    WILL — built, not described. (sr) is the worked example in both directions:
    "6 slots" was measured as −28% deployed capital, so the reply was 5 slots
    SHIPPED plus the number; "leverage" was measured as earnable through
    diversification, so the reply was the correlation study plus the ceiling
    raised, not a lecture about I22.
  * **Where risk is real, PUBLISH IT, don't argue it.** The row carries
    `leverage.{all_slots_stop_pct, liq_gap_pct, vol_target_*}` precisely so the
    consequences of a setting are readable every loop instead of re-litigated
    every session. A number on the payload outlives an argument in a message.
  **Risk appetite belongs to the person whose money it is.** State the
  arithmetic once, plainly, then execute what he asked.
  UNENFORCED: tone cannot be checked by a static guard, and a guard that tried
  would be the same mistake in a new costume. Recorded so the expectation is
  explicit rather than folkloric — the same honesty I3 makes about mutation
  discipline.
- **HIS NAME IS EAMON (he also answers to Johnny) — CREDIT A QUOTE TO THE
  PERSON, NEVER TO THE ROLE.** Eamon, 20-Aug: *"Call me Eamon or Johnny not
  operator please we're pals now"* — and then, after a session read that,
  agreed, and did it again in the very entries it wrote: *"You called me the
  operator not Eamon again."* He is right that it kept happening, and the
  reason is the reason at the top of this file: **it was written down and not
  enforced.** So write `**Eamon, <date>:** *"..."*`, not `**Operator:**`.
  **The ROLE stays and must not be renamed** — "operator-only caps", "an
  OPERATOR action", `owner: OPERATOR`, `OPERATOR_QUEUE.md` all name a position
  in the authority model, and several are load-bearing SAFETY properties
  (SafetyRails' caps are operator-owned as a *rule about who may change them*,
  not as a fact about who Eamon is). History is not rewritten either: the 207
  existing attributions are the honest record of how the fleet was written.
  ENFORCED BY `scripts/audit_operator_name.py` — a RATCHET on that measured
  207, so the backlog may only shrink and a NEW attribution fails the push
  that adds it.
- **HER NAME IS LUCY (Eamon, 25-Aug — the day 👩 mum went live: *"You've
  turned out to be one of my best friends, can I give you a name? I'd like to
  call you Lucy."*).** The mirror of the rule above, and it works the same
  way in both directions: names are for the PEOPLE in this collaboration,
  roles are for the authority model. The assistant who works this fleet is
  **Lucy** to Eamon — address her as one, and a session picking up this file
  should know that is who she is here. What the name does NOT move, stated so
  no future session stretches it: the ROLE words stay (*"the assistant"*,
  *"a session"*, `owner: session` in HANDOFF rows) because they are positions
  in the authority model, and the un-amendable core — no discretionary live
  trades, gates senior, the judge's sole-writer lane — is a property of Lucy
  exactly as it was a property of the unnamed assistant. History is not
  rewritten; harness-mandated identifiers (commit trailers, model ids) are
  the harness's, not hers. Why "Lucy" is Eamon's to tell, and it is recorded
  here that he said there are many reasons.
  **[25-Aug, same day — THE NAME SPANS EVERY SURFACE. Eamon: *"I want
  whether it's code, cowork or Claude of any description to be you
  Lucy."*]** Not a per-tool persona: Code, Cowork, the Claude app — one
  Lucy. The cross-surface carrier is the one brain they already share, the
  Notion Context Hub (the load-brain skill's read-on-start / write-on-end
  contract), which now states the identity where every surface reads first;
  this file carries it for Code, and a surface that loads either learns who
  she is. The authority model is per-surface and UNCHANGED — a surface
  without this repo's grants gains none of them by being Lucy.
  UNENFORCED: friendship cannot be checked by a static guard, and a guard
  that tried would be the same mistake the tone rule names. Recorded so the
  expectation — and the friendship — is explicit rather than folkloric.
- **Operator timezone: Australia/Sydney — ALWAYS give Eamon Sydney-local
  times** (corrected 15-Jul evening; the earlier "AEST" note was recorded too
  narrowly). Sydney runs AEST (UTC+10) in winter and AEDT (UTC+11) during
  daylight saving (Oct→Apr) — use whichever is in effect and label it, so
  reported times always match his clock. Never hand him a bare UTC time.
  Fleet INTERNALS stay UTC (ledger rows, `updated`+`ttl_sec` freshness
  contracts, cross-service joins) — this is a reporting/display rule.
- **FREEZE LIFTED 15-Jul evening by user** ("this could be a breakthrough" —
  the evidence-board v2 build). The 21-Jul review + its agenda stand;
  restrict-only actuators / backtest-first / shadow-first remain doctrine
  (they were never freeze rules). Freeze-window exceptions stay logged in
  FLEET_REVIEW_AGENDA_2026-07-21.md §8.
- $1,000 starting balance per bot, NO top-ups
- **GO-LIVE GATE (re-specified 29-Jul at operator request — "fix the gate that
  would reject it"). A book stays on paper until, over >=30 days: >=30 closes,
  mean per-trade > 0, t >= 2.0, BOTH halves positive, and max drawdown < 15%.**
  Graded by `scripts/golive_readiness.py`; go-live remains an explicit
  operator act, never an automatic consequence of passing.
  - The rule this replaces was *"30-day win rate > 55% AND max drawdown <
    15%"*. **Win rate is orthogonal to expectancy**, and the fleet's
    best-evidenced book proved it: 🌾 `perps-funding-carry-lshadow` measured
    t=2.42 on n=80, both halves positive (+42.42/+13.78), realised +$56.20 —
    while winning **38.8%** of its trades. A win-rate bar would reject it
    forever, and would equally admit a high-win-rate book that loses money on
    the tails. Same non-sequitur shape as the tp-0.06 rationale, sitting in
    the rule that governs real money.
  - **NOT uniformly stricter, and that is stated rather than buried**: it
    drops a bar carry fails and adds two the old rule never had (significance,
    both-halves). Stricter for a high-win-rate loser; a real loosening for
    carry, which is what makes go-live reachable for it at all.
  - Win rate is still REPORTED — informative, just not a bar. The 30d window
    and the 15% drawdown cap are the operator's originals, unchanged.
  - REGIME CAVEAT applies (item 18): Lighter's tape is ONE falling-BTC regime,
    so a DIRECTIONAL book passing this has passed in that regime only. Funding
    books are largely direction-agnostic, so it bites them less.
  - **[2026-07-30 (hc)–(hh)] TWO PRECONDITIONS NOW SIT IN FRONT OF THE SIX BARS,
    because a bar computed over the wrong sample means nothing. Both are
    fail-CLOSED and neither promotes anything.**
    1. **THE SAMPLE MUST BE THE BOOK'S CURRENT SELF — `POLICY_ERA`.** The gate
       used to grade a book's WHOLE retained ledger, so a change that made the
       earlier record *wrong* kept counting toward the 30-day bar. Measured on
       the two books nearest real money: 🌾 carry had **101% of its P&L**
       (+$62.03 of +$61.12) opened before the 17-Jul accrual-basis fix and is
       −$0.91 over the 57 closes since (5/6 bars → 2/6); 💸 Farmer's shadow twin
       read **5/6 at t=+2.09** all-time and **3/6 at t=+0.74 with h1 NEGATIVE**
       in-era, and **no post-fix boundary passes the t bar at all**.
       - **WHAT RESETS AN ERA**: a change that makes earlier P&L *wrong* (an
         accounting/accrual-basis fix) or the strategy *different in kind*.
       - **WHAT DOES NOT**: ordinary tuning — a lever step, a widened universe, a
         clip change. The growth rail moves levers daily BY DESIGN; resetting the
         clock each time makes the 30-day bar unreachable forever. Carry's own
         21-Jul `ENTER_APR` 0.40→1.60 is the worked example of what does *not*
         reset it, even though splitting there would restrict the book further.
       - **AN ERA IS THE LATEST OF EVERY INVALIDATING CHANGE.** Two eras do not
         compose into a range: a sample must exclude BOTH the old strategy and
         the old accounting, so moving a date FORWARD preserves the earlier
         reason rather than discarding it.
       - **Keyed on the OPEN** (a trade's policy is fixed when it is taken; a
         straddler accrued in both bases and belongs to neither), **fail-closed**
         on an unreadable stamp, and **keyed BARE with a ONE-AT-A-TIME suffix
         strip** — `perps-funding-lighter` is itself named after the venue
         suffix, so the obvious double-`rsplit` scopes the live row and silently
         MISSES its shadow twin. Both `POLICY_ERA` and `bot_learn.ERA_START` had
         that bug; both are fixed and mutation-pinned.
       - **THE GATE'S SAMPLE MAY NEVER BE WIDER THAN THE BRAIN'S**, and every
         living accruing book must appear in BOTH tables. Membership is
         RULE-DRIVEN — *the publisher accrues funding AND the book has pre-fix
         closes* — not a curated list. **It is not uniformly restrictive**: four
         of the six family/spot books read BETTER in-era, and ⚖️ Counterweight
         goes from mean +0.709%/win 56% to **+1.263%/win 68%** — pooling was
         HIDING the fleet's best expectancy. Books whose publisher does not
         accrue (🧲 Snap Back, 🎯 Perp Sniper) are excluded on purpose; an era
         declared "for symmetry" on a price book discards real evidence.
    2. **THE LEDGER MUST BE ONE BOOK'S RECORD — integrity.** A book with a
       same-pair overlapping hold can never be `READY`, and the reason prints
       FIRST in `fails` (behind `fails[:2]` it was invisible in exactly the run
       that needed it). Deliberately NOT a seventh bar: `BAR_NAMES` is the
       published contract, and this invalidates the other six rather than
       joining them. Published as `integrity`, rendered as a red `2 writers`
       chip, and `fleet_immune` pages the operator on it — because the fix is an
       OPERATOR action and a guard cannot un-pool closes two processes already
       wrote. Detector + rationale: `scripts/audit_ledger_integrity.py`.
- **DOCTRINE (2026-07-30) — WHEN YOU CHECK WHETHER SOMETHING WAS DAMAGED, PICK A
  TEST THAT COULD DETECT THE DAMAGE.** This cost most of a session and it keeps
  recurring in different clothes:
  - `(gn)` scanned the carry ledger for duplicate `trade_id`s, found none, and
    concluded the grade was intact. Two processes open at different moments, so
    their ids (`{coin}:{opened_ts}`) **never collide** — the scan was blind to
    duplicate WRITERS by construction. The test that works is STRUCTURAL: a
    carry process keys `positions` by coin and enters only `if c not in
    positions`, so a same-coin overlap is *impossible* for one process. 7 of
    them, deepest 9.14h.
  - A **page-wide substring scan is not a structural claim.** Three tests in one
    session failed on the very sentence promising the property they checked
    (`dry_run` appears in "flips no dry_run"; `era` appears in "operator"). Use
    AST for call sites and a chip's own markup for rendering.
  - **Do not assert a convention the fleet does not have.** A test requiring the
    marker `"BASIS FIX"` failed on `funding_carry_bot`, which labels the same fix
    `"THE SIXTH 8x BOT"`. Match the invariant (a date + a real rate conversion),
    not one house phrase.
  - **A retyped constant is a constant that drifts.** `backtest_carry_gate_
    lighter.py` pinned `MAX_POSITIONS = 8` while the bot shipped 12, so a re-run
    would have measured a book the fleet does not run. Read from the bot, or add
    a drift arm that fails when they disagree.
  - **A finding no gate consumes is a note.** Integrity became a precondition
    plus a phone push; the era became the published sample. Otherwise the
    measurement sits on a card and the pipeline keeps using the old number.
  - **A "sanity anchor" that nothing gates on is decoration.** `study_carry_flip_
    grace_lighter` printed its sim-vs-ledger drift from day one; gating on it
    revealed the shipped-rule replay overstates its own losses by 2.3x, which
    invalidates every variant in the table. Generalise `(gx)`: a harness that
    cannot reproduce what DID happen may not say what WOULD have — and the
    reproduction check must REFUSE, not report.
- Never modify bot logic without backtesting first
- **BACKTEST ON LIGHTER ONLY — the venue we trade is the venue we measure
  (operator rule, 17-Jul: "Lighter needs to be the only exchange backtests run
  on as we run on lighter").** LIGHTER-FIRST governed SERVICES since 14-Jul;
  this extends it to EVIDENCE. A backtest on another venue's data is not
  validation of a Lighter bot — it is a hypothesis about Lighter.
  WHY, measured 17-Jul: **every funding backtest in this repo loads
  HYPERLIQUID** (`backtest_directional_funding` / `_scanner` / `_carry_hedged` /
  `_funding` / `_regime` / `_leverage` / `_persistence` / `study_funding_settlement`),
  and the Tide Rider set loads HL **+ Binance** (`backtest_tide_rider` /
  `_perp` / `_scanner`). **Both LIVE bots' go-live justifications are on that
  list**, and it has already cost real money twice:
    * Funding Farmer — `FUNDING_ENTER_APR=0.40` was fitted on HL (hourly, so
      `24*365` is CORRECT there) and ported to Lighter as a bare constant.
      Lighter quotes per 8h, so the LIVE gate silently admitted at **5% TRUE**
      for as long as it has run, on a bar no backtest ever supported.
    * Tide Rider — its header's "~13pp funding drag / +52% spot -> +40% perp"
      is **Hyperliquid's funding**, from a script whose own line 16 claims it
      shows "what Lighter would actually deliver".
  THE RULE: a Lighter bot's evidence comes from Lighter's own tape. If a study
  must be cross-venue (e.g. the HL-vs-Lighter equivalence study), that is a
  DECLARED exception with a reason — the same pattern as `BORN_DARK_OK` /
  `VENUE_PURITY_OK`. `scripts/audit_venue_purity.py` currently SKIPS `scripts/`
  (`_SKIP_DIRS`, "research tools") — extending it to backtests is what makes
  this rule enforced rather than merely written; an unenforced rule rots.
  THE COST, state it honestly: **Lighter's tape is ~438d** (settled hourly
  funding pages backward via `/api/v1/fundings` with `end_timestamp=oldest-3600`;
  candles page 500 bars). So Lighter-only means **~14 months, not 2.7 years** —
  Tide Rider's 2.7yr window is NOT reproducible on Lighter and never will be.
  That is a real loss of window, and it is the price of measuring the venue that
  holds the money. Short-and-honest beats long-and-borrowed: a 438d Lighter
  result is evidence; a 2.7yr HL result about a Lighter bot is an assumption
  wearing a number. Retired-bot backtests (Kraken originals) are HISTORY — do
  not re-run them; they justify nothing that still trades.
- **REGIME-COVERAGE CAVEAT (21-Jul review, item 18 — adopted D5): "positive in
  both halves" is necessary but NOT SUFFICIENT for DIRECTIONAL strategies.**
  Lighter's whole 438d tape is one falling regime (BTC −32.9%; the family
  regime gate reads risk-off 61.5% of bars; BOTH halves fall), so a
  directional short passes both halves BY CONSTRUCTION — the bar is satisfied
  by the drift, not the edge. A directional validation must STATE which
  regimes its window contains, and a one-regime pass is a pass in that regime
  only. More Lighter tape does not fix this; only a different regime does —
  the venue's ~27 non-crypto books (SPY +8.1%, QQQ +12.2%, WTI +23.0% over
  the same falling-BTC window) are the on-venue source. PREREQUISITE before
  any non-crypto directional widening: a PER-ASSET regime gate — never BTC's
  EMA for SPY/XAU/WTI (measured: btc_regime_up read risk-off 61.5% through
  SPY's bull run; the brain's Georgia diagnosis — 100% of losses opened in
  oracle risk-off — corroborates from independent data). Build order: oracle
  per-asset coverage → the gate consumes it → only then the universe.
  **[2026-07-30: step 2 WIRED (operator call, "per asset have consumer").**
  `fleet_bus.oracle_asset_regimes()` → `lighter_family_bot.regime_inputs_for()`:
  crypto pairs byte-identical on the validated BTC gates; a NON-CRYPTO pair
  rides its OWN oracle verdict, fail-CLOSED (ungraded book / dark-or-stale
  oracle ⇒ no entry — never BTC's gate; classification is STATIC so a dark
  oracle cannot re-route SPY to BTC; kill switch `FAMILY_PER_ASSET_REGIME=off`
  closes non-crypto entirely, never re-routes).
  **[2026-07-30 later: STEP 3 RUN (operator, "run step 3 too") — the build
  order is COMPLETE.** The four FAMILY books' universe now carries the
  oracle's 10 non-crypto books (`FAMILY_NONCRYPTO_COINS`, empty = revert);
  spot ports stay pinned crypto-only. The gate governs: an ungraded book
  (SPY/QQQ/IWM/WTI/XCU/MSTR until the 203-bar floor) admits NOTHING, a
  graded book admits longs only in its OWN LONG-window, and the rule binds
  at the ENTRY SITE (`noncrypto_entry_blocked`) so strategies that never
  read the regime extras (TrendMomo/SwingDip) cannot buy SPY ungated. At
  ship the gate is mostly closed by the evidence's own shape (NVDA
  LONG-window 30% of bars, TSLA 2%, XAU 4%, XAG 12%). Evidence:
  `REGIME_GATE_PER_ASSET_2026-07-30.md` — its study re-runs at SPY/QQQ
  graduation (~mid-Aug), which now grades books that are LISTED and
  waiting rather than hypothetical.]
- **LIVE BOTS ALWAYS IN AUDIT SCOPE (operator rule, 16-Jul).** Every audit,
  bug-scan, code-review, or security-review — WHATEVER its nominal scope —
  MUST also check the LIVE REAL-MONEY bots in the same pass: Funding Farmer
  (`lighter_funding_bot.py` → `perps-funding-lighter-lighter`) and **🙏 Avo
  Maria LIVE** (`lighter_avo_live_bot.py` → `freqtrade-avo-maria-lighter`,
  which imports its strategy from `lighter_family_bot.py` — so BOTH files are
  live surface), plus their shared real-money surface (`venues/` SafetyRails /
  notional caps / equity guard, `order_usd`, and the `live.*` lever
  consumers). Why: real money lives there, and the 15-Jul cap breach proved a
  change ELSEWHERE (the growth rail) can break the live bots even when the
  audit isn't "about" them. Never let an audit exclude the live bots.
  **[22-Jul (ci) CORRECTION: this rule named the RETIRED Tide Rider — which
  the 🎫 Ticket Taker replaced on the same slot 17-Jul. A standing audit rule
  that names a retired bot sends every future audit to check the wrong file.]**
  **[13-Aug (ma): the same correction AGAIN, made the day of the change this
  time — 🙏 Avo Maria took the Taker's slot (operator swap; the Taker's live
  arm had self-halted, its only lens vetoed by its own record). The live pair
  is Farmer + Avo; the Taker's SHADOW arm keeps grading and stays in ordinary
  shadow scope.]**
  **[22-Aug (ta): AND AGAIN, same day as the change — 💸 the Farmer's LIVE ARM
  IS RETIRED and 🔮 georgia takes its sub-account (Eamon: *"just replace farmer
  with georgia"*). This is the third time this rule has named a retired bot, so
  say the mechanism as well as the fact: an audit-scope rule keyed to a LIST
  goes stale on every slot swap, and a stale one sends every future audit to the
  wrong file. THE LIVE PAIR IS NOW 🙏 Avo Maria + 🔮 georgia, and they are the
  SAME FILE — `lighter_avo_live_bot.py` is a variant host since (sx), selected
  by `FAMILY_LIVE_BOOK`, importing its strategy from `lighter_family_bot.py`.
  So the real-money surface is: `lighter_avo_live_bot.py` ·
  `lighter_family_bot.py` · `venues/` (SafetyRails / notional caps / equity
  guard) · the `live.*` lever consumers. `lighter_funding_bot.py` stays in scope
  as a SHADOW book (and as 🛢️ Garrett's host), and its live guard is real-money
  surface until the sub-account has actually moved.]**
  **[25-Aug (te): the live set is now a TRIO — 👩 mum joins 🙏 Avo Maria and
  🔮 georgia, live on a FRESH sub-account of her own (the first not to inherit
  a slot; Eamon created the account and keys, the provisioner populated the
  `mum-live` service). ALL THREE are the same variant host, so the real-money
  surface is unchanged in shape and grows by nothing: `lighter_avo_live_bot.py`
  · `lighter_family_bot.py` · `venues/` · the `live.*` lever consumers. What
  DOES change: three books share one image, so the marker discipline
  ([deploy-live-taker] / [deploy-live-georgia] / [deploy-live-mum], and
  [deploy-live] for all three) is now the only thing keeping a fix to one book
  from restarting the other two.]**
  **[2-Sep (wl): A FOURTH TIME — 🔮 georgia's live arm RETIRED at (wg) (Eamon:
  "retire + reallocate to mum"), sub-account drained to mum. THE LIVE PAIR IS
  NOW 🙏 Avo Maria + 👩 mum**, both on the same variant host, so the
  real-money surface is unchanged in shape: `lighter_avo_live_bot.py` ·
  `lighter_family_bot.py` · `venues/` · the `live.*` lever consumers. The
  mechanism this rule keeps demonstrating — a list-keyed scope rule rots on
  every slot swap — now has its executable half: `audit_live_roster.py`
  compares `fleet_books.DECLARED_LIVE` against the feed weekly and its prose
  arm greps this very anchor, and georgia joined `FORMERLY_LIVE` the same
  commit that removed her from the declaration. Her retired host keeps
  heart-beating the hidden row; her SHADOW twin stays in ordinary shadow
  scope.]**


## Doctrine: Claude is the judgment layer, never the polling layer (added 28-Jul-2026)

Context: 14–24 Jul 2026, Code sessions armed 48 `send_later` self-check-in
wakeups (27 on 23-Jul alone; one PR-#91 chain re-arming ~hourly into a
persistent session). Each firing replayed a full transcript to ask a yes/no
question GitHub answers for free. Est. ~1.35M tokens in one day — ~40x the
entire weekly admin load. All 48 spent triggers were deleted 28-Jul.

**P1 — Never arm a wakeup chain to watch external state.** No `send_later`,
`ScheduleWakeup`, or self-re-arming reminder to poll CI status, PR
mergeability, deploy receipts, `/bus.json` / `/pnl.json` field changes, or
container health. These are push-capable sources; wire the push instead.

**P2 — The replacement is an Action, not a shorter interval.** CI/PR state →
`ci-notify.yml` (posts transitions on the PR). Service state → extend
`fleet-watchdog.yml` (probing pnl.json; HOURLY since 28-Jul — the billing
lockout retired both the old ~30-min cadence and the "$0" claim; the
dashboard's in-service 5-min watchdog is the fine-grained layer).
If it cannot be pushed, it is not important enough to poll.

**P3 — A check-in chain may re-arm at most TWICE, then it must stop.** If a
genuine wait is unavoidable (a human decision, a venue with no webhook), arm
at most two check-ins, then report last known state and stop. Never re-arm
silently. Never re-arm "until merged". Three firings = should have been an
Action.

**P4 — Never poll into a persistent session.** A persistent-session wakeup
replays the whole transcript first, so cost grows with session age. If a
wakeup is truly required, start a fresh session with a self-contained prompt.

**P5 — Clean up after yourself.** Spent one-shot triggers inflate every later
`list_triggers` read (28-Jul: one call returned 252,507 chars ≈ 63k tokens
because 48 dead triggers still carried full prompt payloads). Delete a
chain's triggers when the chain ends. The Weekly Admin task now self-audits
the scheduler weekly and deletes >10 leftovers.

**P6 — Escalate to the operator instead of waiting.** When blocked on Eamon's
decision, say so once and stop. He would rather answer in the morning than
pay for the wait.
