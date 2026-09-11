---
name: crypto-research-review
description: Weekly expansion research — one growth hypothesis, measured on Lighter's own tape, shipped through the designed channel or refuted with numbers
---

EXPANSION RESEARCH: find a way to win. Weekly deep-work session, ONE hypothesis
per run, measured to a verdict. The fleet's ORGANS do continuous observation
24/7; what no organ can do is INVENT — the incubator only recombines within
registry bounds. **This slot is the invention cadence.**

PROJECT_DIR = /Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot

## SLOT SCOPE — tighter than the repo's, deliberately, and say so

* **MEASURE BEFORE BUILDING, on LIGHTER'S OWN TAPE only.** A backtest on
  another venue is a hypothesis, not evidence.
* **A widening is paid for in expectancy (I19).** Turnover is not a win. A
  REFUSAL WITH NUMBERS is a first-class output.
* **Grade directional ideas against a RANDOM-ENTRY null** (a random short
  earns +0.2–1.1%/trade free on this tape), episodes not trades, and check
  execution lag before believing any intrabar edge.
* **This unattended slot does not touch real money and does not deploy**: no
  `live.*` levers, no clips, no `dry_run`/keys, no pushes to live services.
  Real-money findings are escalated with the exact command.
* **On shadow-lane levers this slot ROUTES rather than sets** — through
  `fleet_proposals.py` → the tuner's replay gate, because auto-revert is free
  safety for an unattended run. **THIS IS A SLOT SCOPE, NOT THE REPO'S RULE.**
  CLAUDE.md was amended on 5-Aug (kd) — *"A session may now write a
  shadow-lane lever directly"*, with the replay gate "no longer a
  precondition" — and this prompt has carried the retired sentence since the
  day before that amendment. An interactive session has that authority and
  more ((lm), (pz), (tg), (vc), (vd)); do not read this line as doctrine and
  decline work you are authorised to do.

## 0 · BEFORE YOU START

```
cd "$PROJECT_DIR" && git fetch origin -q
python3 scripts/review_cadence.py --gap      # did last Wednesday's run happen?
python3 scripts/session_state.py             # HANDOFF — carried work (I11)
```

Stamp the report header with the scheduled slot (Wed 09:03 AEST) and the
actual time. This routine is the fleet's most reliable — and it still ran
**4 of 6** scheduled Wednesdays to 10-Sep (5-Aug and 12-Aug produced nothing;
12-Aug sits inside the 7–13 Aug entitlement outage, **5-Aug is undiagnosed**).
Its edge over the daily jobs is real but it is 67% vs ~50%, not "never misses".

Then read, in this order:
1. `reports/expansion_research_log.md` — the **NEXT THREAD** items of the last
   run. Name each one and say: picked up, or deferred-because. **A silently
   dropped thread is the failure this step exists to stop** — measured: 2 of
   3 items from the 2-Sep run were never mentioned again, and one of them
   ("the stop asymmetry, −0.89pp per stop-pair event over 66 events") was the
   largest unmeasured number in that book.
2. The refutation index (below) — **never re-test a refuted idea** without new
   evidence.
3. The CHANGELOG since the last run.

**NEVER ASSERT the state of a HANDOFF/CARRIED row — read it.** Another routine
may have closed it the same hour; one prior run cited a row that had closed
that morning.

## 1 · HARVEST, then PICK ONE

Harvest from what the fleet already measures — the brain's diagnosis buckets,
`fleet-radar` medians, `fleet-allocation` claims vs capital, lens grades and
the scout tape (`lighter_ticket_replay`), `scripts/study_exit_attribution.py`,
starving-lens censuses, and the venue itself.

PICK ONE by expected value of information, favouring: (a) an unmeasured claim
blocking a decision, (b) a candidate new edge or lens for an existing book,
(c) a candidate NEW book, (d) a binding constraint no lever reaches (I18).

**A NEW BOOK IS NOT A NAMING EXERCISE.** Before proposing one, run the two
executable gates in order — `scripts/audit_book_overlap.py --gate --floor`
(I20: name the supply; a supply already spoken for is one bet held twice) and
`scripts/audit_book_spend.py` (I22: publish the spend; >60 days to gate makes
it a STUDY, not a book). A refusal counts as compliance.

## 2 · MEASURE IT TO A VERDICT

Use the repo's own harnesses and respect their calibration gates — a harness
that cannot reproduce what DID happen may not say what WOULD have, and it must
REFUSE rather than caveat.

## 3 · SHIP THE VERDICT — every branch has a destination

* **Supported + shadow-lane** → write the proposal through
  `fleet_proposals.py` and log it.
* **Supported + real money or a new book** → an evidence note in `reports/` +
  a Gmail draft to emcmpg@gmail.com naming the decision.
* **REFUTED** → all three of:
  1. a tagged line in the log, above the prose, in exactly this form —
     `REFUTED[<slug>] <YYYY-MM-DD> — <one-line number that killed it>`;
  2. **COMMIT THE INSTRUMENT.** Measured: 2 of 2 shipped-branch study scripts
     are tracked in git and **0 of 3 refuted-branch ones are** — the harness
     that killed an idea is exactly what the next session needs to refuse to
     re-run it, and it currently dies with the machine;
  3. if the refutation has a consequence for a book, a `CARRIED` row.
* **EVERY branch** → **write back to the sync channel.** A run that changes a
  tracked file gets a CHANGELOG entry, letter picked with
  `python3 scripts/audit_changelog_letters.py --next` (after `git fetch`). A
  run that changes nothing still gets one short entry naming the verdict and
  the log path, so `audit_recurrence` can see the subject. **ONE entry per
  run, not per section** — nine same-week entries on one subject is what that
  guard reddens the build for. Never cite a research-log entry by a CHANGELOG
  letter it does not have.

## 4 · APPEND TO THE LOG, AND HAND OFF

Append a dated section to `reports/expansion_research_log.md` — hypothesis ·
method · numbers · verdict · transferable · NEXT THREAD. Say the path.

**NEXT THREAD is a commitment, not prose.** For each item state whether it is
(a) a thread for the next research run, (b) work with a next-run consequence,
or (c) closed. **Every (b) becomes a `session_state.CARRIED` row with a
`closes_when` predicate in the same session**, and the log cites the row id.
That is the only mechanism that survives a session, and it is the difference
between the one thread that got picked up and the two that vanished.

The log is TRACKED in git as of 11-Sep (`.gitignore` carries the explicit
negation) — so commit it, and a refutation now survives a fresh clone.

One hypothesis, finished, beats three started (I11). Sydney-local times.
Not financial advice; go-live and real-money changes are operator acts.
