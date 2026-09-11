---
name: crypto-weekly-pnl
description: Monday verdict layer on the CI weekly scoreboard — which book moved toward the gate, capital-vs-claims, keep-or-retire pressure, one expansion candidate
---

Write the WEEKLY VERDICT on the fleet and EMAIL it.

PROJECT_DIR = /Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot

## SLOT SCOPE (tighter than the repo's, on purpose)

READ-ONLY on the fleet: no trades, no `dry_run`/keys/lever/config changes, no
deploys, no pushes. This is an unattended reporting slot's scope, **not the
repo's doctrine** — CLAUDE.md delegates much more to an interactive session.
Do not carry it out of this slot.

## THE DIVISION OF LABOUR

`.github/workflows/fleet-weekly-assessment.yml` runs Sunday 23:30 UTC and
produces the DETERMINISTIC parts at $0, in **four** jobs — the scoreboard
issue (label `fleet-weekly`), `ceiling`, `organ-board`, and `code-currency`.
**This task is the VERDICT on all four.** Judge, don't recompute; never poll.

**Where the monthly ends and this begins**, because they overlap on four of
five sections: the WEEKLY judges MOVEMENT (what changed in seven days, which
bar flipped, what is due this week). The MONTHLY (`crypto-monthly-pnl`, 1st of
the month) judges STANDING (era-aware gate reads, the decidability census,
promote/keep/retire recommendations). If a call is a keep-or-retire DECISION,
it is the monthly's or Eamon's; the weekly's job is to say the pressure is
building and name the date.

## 0 · BEFORE YOU READ ANYTHING

```
cd "$PROJECT_DIR" && git fetch origin -q
python3 scripts/review_cadence.py --gap      # was last week's verdict written?
python3 scripts/session_state.py             # HANDOFF — carried work (I11)
```

**Stamp the header with the scheduled slot (Mon 10:34 AEST) and the actual
time, and say plainly if they differ.** This is the dominant failure mode of
this job, measured: of the four surviving verdicts, exactly ONE was written in
its slot — the others read "Thu 13-Aug 13:20", "Wed 26-Aug 07:15", and one
written 81 minutes BEFORE the slot and 17 minutes before the CI cron it claims
to judge. A verdict that does not say when it was taken cannot be reconciled
with the week it describes, and 31-Aug is missing entirely.

## 1 · READ THE MACHINE'S WEEK — and check it is THIS week's (I1)

```
gh run list --workflow=fleet-weekly-assessment.yml --limit 3 \
   --json conclusion,createdAt,databaseId
gh issue list --label fleet-weekly --state all --limit 1 --json number,body,createdAt
curl -s "https://pnl-dashboard-production-858c.up.railway.app/bus.json?hours=0"
```

* **Liveness before semantics.** If the latest run STARTED after this task
  fired, or its issue predates this Monday, you are judging LAST week's
  scoreboard — say so in the headline and judge the payloads directly rather
  than the stale issue. The gap is 64 minutes today and **shrinks to ~4
  minutes when Sydney moves to AEDT on 4-Oct**, so this check gets more
  load-bearing, not less; the durable fix is moving the cron earlier and that
  is worth proposing.
* If the run is RED, say WHY first — a `BEHIND-OWN` code-currency verdict
  means a container is missing its own merged behaviour, and the fix
  (redeploy + stamp readback) leads the email. Note the week that went
  missing (31-Aug) was the week CI was genuinely red.
* `?hours=0` unless you need trajectory — the default pulls ~15 MB for ~350 KB
  of used content; `(iy)` shipped this fix and the workflow adopted it.

## 2 · THE VERDICT — fixed order

a. **REAL MONEY** — the live rows' week (roster DERIVED from
   `meta.live_fleet.live_bots`, never written down here; this fleet's
   name-keyed rules have rotted on every slot swap). Live-vs-shadow gap
   per-trade, never equity. `impl-shortfall` verdict if published.
b. **WHICH BOOK MOVED TOWARD THE GATE, AND BY HOW MUCH** — the forward
   metric. Name the bars that flipped, rendered from the payload's own
   `bars`/`BAR_NAMES`, never restated in prose. **A week where no book moved
   is a finding, not a blank.**
c. **CAPITAL vs CLAIMS (I16)** — does the allocation organ's ranking disagree
   with where the notional sits? State the disagreement in dollars.
d. **KEEP-OR-RETIRE PRESSURE (I17)** — books undecidable at the probe floor or
   measured negative with significance: n, t, both-halves, upper bound, and
   what the decision would free. Retirement needs a MEASURED exclusion (an
   upper bound ≤ 0), never a thin sample — a refusal to retire on insufficient
   evidence is this invariant working.
e. **DECISIONS DUE THIS WEEK** — sweep the pre-registered reads and say which
   fall due in the next seven days, with their dates:
   `scripts/claims_ledger.py`, `golive_readiness.DECIDED_UNTIL`,
   `winners_docket.PRE_REGISTERED`, and the dated HANDOFF rows. **Import
   them; never hand-list them** — a hand list goes stale and has. No dated
   read lands on a Monday by design, so this is the only routine positioned to
   announce one BEFORE it falls due rather than after it is overdue.
f. **ONE EXPANSION CANDIDATE (I19)** — the single widening the week's evidence
   best supports, priced in expectancy, routed through the designed channel —
   or a refusal with the numbers.
g. **CARRIED** — last week's verdict items, each SHIPPED / STILL OPEN /
   DROPPED-because-X. Anything still open that needs to survive the week gets
   a `session_state.CARRIED` row rather than a sentence.

## 3 · WRITE AND SEND

`$PROJECT_DIR/reports/weekly_verdict_<YYYY-MM-DD>.md` — **Monday's date
resolved in SYDNEY**. This job fires Monday ~09:30–10:34 AEST, which is
**Sunday in UTC**, so a UTC-derived "this Monday" lands on the wrong Monday and
overwrites the previous week's verdict — a full week of judgement gone. If the
target exists, rename it aside (`<name>.superseded-<HHMM>.md`) and say so.
Follow `evidence_review.report_day` / `preserve_existing_report`; do not
re-derive them.

Then EMAIL:
`bash "$PROJECT_DIR/send_report_email.sh" emcmpg@gmail.com "Fleet weekly verdict — <headline>" "<path>"`
Confirm `sent:`; on error fall back to a Gmail draft. State which, and the path.

Sydney-local times, labelled. Real money outranks paper in every ordering.
Shadow books are paper; not financial advice. Go-live, retirements and every
real-money change are explicit operator acts — recommend with the exact
command or lever named, never execute.
