---
name: crypto-daily-pnl
description: Daily fleet P&L + growth brief to email — live money first, claims-ranked books, gate distance, ONE growth item carried forward
---

Generate the DAILY fleet P&L + growth brief and EMAIL it.

PROJECT_DIR = /Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot

This brief answers, on Eamon's phone: **is the real money safe, and where is
today's win?** The deep judgement pass is `daily-evidence-review` (07:33) —
this is the 5-minute read with the growth headline.

## SLOT SCOPE (tighter than the repo's, on purpose)

READ-ONLY on the fleet: no trades, no `dry_run`/keys/lever/config changes, no
deploys, no pushes EXCEPT the one that commits this run's own report
(see the last section). **This is a scope for an unattended reporting slot, NOT the
repo's doctrine** — CLAUDE.md delegates far more to an interactive session
((kd) levers, (lm) real money, (vd) ship-it-now). Do not carry this restriction
out of this slot, and do not read it as "Lucy may not do that."

## 0 · BEFORE YOU READ ANYTHING

```
cd "$PROJECT_DIR" && git fetch origin -q
python3 scripts/review_cadence.py --gap      # did yesterday's brief exist?
python3 scripts/session_state.py             # HANDOFF — what is carried (I11)
```

* **The cadence line is the first thing in the report when it is not
  "current".** This job produced 18 briefs in 38 days to 10-Sep; "since
  yesterday" has silently meant "since some day last week" about half the time,
  and no brief ever said so. If there is a gap, say so in the header and widen
  the window you review — do not narrate one day and call it continuity.
* **Read the CHANGELOG since the last brief.** Concurrent sessions ship all
  day. Never propose a growth item without checking it has not already landed —
  this brief's first run recommended a revert that had shipped the night before.
* **Read `reports/evidence_review_<today>.md` if it exists.** The 07:33 review
  ran 34 minutes earlier over the same organs. Consume its verdicts and its
  OPTIONS list; do not re-derive them and do not contradict it silently.

## 1 · FETCH

```
curl -s https://pnl-dashboard-production-858c.up.railway.app/pnl.json
curl -s https://pnl-dashboard-production-858c.up.railway.app/periods.json
curl -s "https://pnl-dashboard-production-858c.up.railway.app/bus.json?hours=0"
```

`?hours=0` is deliberate — the default pulls ~15 MB of history for ~70 KB of
used content. Read `age_sec`/`stale` BEFORE interpreting any row (I1). A failed
fetch is reported, never invented.

**THE LIVE ROSTER IS DERIVED, NEVER WRITTEN DOWN HERE.** Take it from
`meta.live_fleet.live_bots` (or `scripts/fleet_books.live_rows_from_feed`).
This rule has one reason and it is measured: an audit-scope list keyed to bot
NAMES has rotted on every slot swap — four times in CLAUDE.md's own rule, and
in this very file, which named the Funding Farmer's live arm for 20 days after
it was retired on 22-Aug. No bot name belongs in this prompt.

## 2 · THE REPORT — fixed section order, always this order

**Stamp the header**: scheduled slot (08:07 AEST), actual generation time, and
the cadence line. Reports have been arriving at 11:40 and 15:45 without saying
they were late; a brief that claims to be the morning brief and lands after
lunch is a different artifact and should say so.

1. **REAL MONEY** — equity, day P&L, open positions, staleness, drawdown vs
   the 15% bar, for the live rows the feed declares. Any live row stale,
   halted, or with an outsized single-day loss leads the email SUBJECT.
   `.github/workflows/live-pnl-audit.yml` runs `scripts/live_pnl_audit.py`
   daily and nothing reads it — read its latest run and say what it found.
2. **FLEET** — total and today's realised per book (`periods.json` "daily"),
   ranked, retired rows excluded.
3. **CLAIMS** — from `fleet-allocation`: who holds a measured lower bound > 0
   and who is undecidable. A big day on a zero-claim book is luck until the
   organ says otherwise (I16 — rank on the bound, never the mean).
4. **GATE DISTANCE** — from `golive-readiness`: the one or two books nearest
   the gate, which bars bind, and whether yesterday moved them. **Do not
   restate the bar list in prose** — render it from the payload's own `bars` /
   `BAR_NAMES`; prose is what drifts, which is exactly why `bar_map` exists.
   Read `mde80` beside the mean: bars-passed is not distance to the gate.
5. **TODAY'S ONE GROWTH ITEM** — a single ranked item the data shows TODAY:
   a graded book at its cap (capacity), a bar on the wrong basis
   (correctness), a starving book whose binding gate is named (reach), or an
   undecidable book burning its window. Name the lever, the bound, the
   evidence and the OWNER. If nothing is on offer, say so and say what you
   checked — a refusal with evidence beats an invented option.
6. **YESTERDAY'S GROWTH ITEM — STATUS.** One line: SHIPPED / STILL OPEN /
   DROPPED-because-X. An item that appears three days running without moving
   is itself a finding (I11). **A growth item owned by Eamon gets a
   `session_state.CARRIED` row** so it cannot fall off the next brief, which
   is how the 7-Sep item disappeared.

Per-book ledger reads go through `scripts/ceiling.py::graded_sample` (or the
grader's own reader) — the public `/trades.json` does NOT apply the quarantine
and phantom filters, so a hand-rolled read grades a sample the gate refuses.

## 3 · WRITE AND SEND

Write to `$PROJECT_DIR/reports/daily_pnl_<YYYY-MM-DD>.md` — the **SYDNEY**
date. A UTC-dated filename labels the brief with yesterday and collides with
any afternoon run of the same UTC day; that defect ate a 31,223-byte report
once already. If the path exists, rename the existing file aside
(`<name>.superseded-<HHMM>.md`) and say so in the new report. The canonical
implementations are `evidence_review.report_day` and
`evidence_review.preserve_existing_report` — follow them, do not re-derive.

Then EMAIL:
`bash "$PROJECT_DIR/send_report_email.sh" emcmpg@gmail.com "Fleet daily — <headline>" "<path>"`
Confirm `sent:`; on error fall back to a Gmail draft. State SENT-or-draft and
the path.

Sydney-local times, labelled. Tables small, prose short. Shadow books are
paper; the live rows are real money; not financial advice. Go-live and every
real-money change stay explicit operator acts — this brief proposes, never
executes.

**THE REPORT IS A TRACKED FILE NOW — COMMIT IT.** `reports/*.md` went into git
on 11-Sep (Eamon: *"track the rest too"*), so a report left sitting
uncommitted is a DIRTY TRACKED FILE in a checkout other sessions share, and
the next `git commit` anywhere near it sweeps your report into their commit
under their subject — the (nx) class this repo has already paid for. Commit
yours, by explicit path, and push only that:

```
python3 scripts/session_commit.py reports/daily_pnl_<date>.md -m "daily brief — <date>"
git fetch origin && git rebase origin/main && git push origin HEAD:main
```

This is the ONE push this slot makes: it publishes your own artifact and
touches nothing else. If the rebase conflicts, another routine wrote the same
day — keep BOTH files, never resolve by dropping one.
