#!/usr/bin/env python3
"""scripts/review_cadence.py — DID THE REVIEW ROUTINES ACTUALLY RUN?

    python3 scripts/review_cadence.py                  # the cadence table
    python3 scripts/review_cadence.py --gap            # the one-line header a report leads with
    python3 scripts/review_cadence.py --json           # machine-readable
    python3 scripts/review_cadence.py --publish        # upsert bot_state 'review-cadence'
    python3 scripts/review_cadence.py --check          # non-zero when a routine is OVERDUE
    python3 scripts/review_cadence.py --selftest

WHY THIS FILE EXISTS (2026-09-11). The fleet instruments everything it runs —
`fleet_immune`, `fleet_watchdog_svc`, `ORGAN_SPECS`, a TTL on every organ key,
`actions-heartbeat` as a dead-man's switch for CI itself. It did **not**
instrument the four jobs that review it, and I1 is the invariant that says why
that matters: a frozen row and a healthy one are byte-identical if you compare
CONTENT — only the timestamp distinguishes them. **A dead reviewer and a quiet
day are byte-identical too, and nothing was reading the timestamp.**

MEASURED the day this shipped, over 4-Aug..10-Sep (38 days):

  * `daily_pnl_*.md`        present 18 of 38 — **20 missing (53%)**
  * `evidence_review_*.md`  present 20 of 38 — **18 missing (47%)**
  * `weekly_verdict_*.md`   missing 2026-08-31 entirely
  * across EVERY project on this machine, **no Claude session ran at all on
    4, 5 or 8 Sep** — so those are the local scheduler not firing (the machine
    asleep), not the tasks failing. 7-13 Aug was a different cause and is
    already recorded: an account entitlement outage that killed 15 consecutive
    runs while `lastRunAt` advanced daily (memory
    `scheduled-tasks-die-silently-on-auth`).
  * and when they DO run they run late without saying so: the 9-Sep brief is
    stamped *"Generated Tue 9 Sep, 15:45 AEST"* against an 08:07 slot, the
    10-Sep brief 11:40. Neither mentions it.

**Not one of those gaps was noticed by anything**, and nothing in the repo even
knows these jobs exist: `grep -rl 'daily-evidence-review\|crypto-daily-pnl'`
over `scripts/` and `.github/` returns the CHANGELOG and one comment. Five
routines, no cadence written down anywhere, no key, no watcher.

WHY THE EXISTING ORGAN ROW DOES NOT COVER IT — and this corrects my own first
reading, which was wrong in the interesting direction. `evidence-review` sits
in `ORGAN_SPECS` with `ttl=None`, so its vitals row can never compute DARK and
`tests/autonomy/test_organ_pageability.py` (which governs only keys where
`ttl is not None`) cannot see it. That LOOKS like I13's "structurally
unpageable" defect. It is not: `ttl=None` is the deliberate **EVENT type**,
shared with `fleet-alerts` and `fleet-tuning`, and `pnl_dashboard` explains why
in its own words — a row that is permanently DARK by design "is how operators
learn to ignore DARK". So the answer is not to re-type an event key; it is that
the LIVENESS question needs a key of its own, which is this one. The
consequence the first reading got right stands unchanged: nothing observed
whether the review ran.

WHAT THIS DOES AND DOES NOT CLAIM:

  * It reports on OUTPUTS, not on runs. A report on disk is the only durable
    evidence a routine finished; `lastRunAt` is documented to advance on a run
    that died on arrival, so it is not evidence and is not read here.
  * FAIL-CLOSED, and the direction is load-bearing: an unreadable or absent
    reports directory is **UNKNOWN**, never `OK`. Swept-dark and swept-clean
    must not be byte-identical ((kw)).
  * It NEVER guesses a cause. A gap is reported as a gap; whether the machine
    was asleep, the entitlement lapsed or the run crashed is for the session
    that reads it (I8 — name the object, don't invent the reason).
  * It moves nothing and proposes nothing. The single write it can perform is
    `bot_state['review-cadence']`, gated the same way `evidence_review.py`
    gates its own single UPSERT.

THE DECLARATION IS SINGLE, deliberately — `fleet_books.py`'s lesson one level
up. The cadence of a routine was written down in exactly zero places before
this; it is now written down in exactly one, and the four task prompts read it
rather than restating it.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = os.path.join(ROOT, "reports")


def reports_dir_resolved(root=ROOT):
    """-> the directory the routines actually WRITE to, from any worktree.

    `reports/` is gitignored, so a session working in one of this repo's
    per-session worktrees (now the default, (oe)) sees an EMPTY `reports/`
    while every real report sits in the main checkout. Measured the hour this
    shipped: run from a worktree, the first version reported all five routines
    "no output of this kind has ever been seen here" — a false alarm on the
    first run, which is precisely how a detector teaches its reader to ignore
    it ((gl)).

    So: prefer a local `reports/` that actually holds reports, else the MAIN
    worktree's (derived from git, never guessed), else fail closed to the
    local path so the caller still gets UNKNOWN rather than a wrong answer.
    """
    local = os.path.join(root, "reports")
    try:
        if os.path.isdir(local) and any(
                n.endswith(".md") for n in os.listdir(local)):
            return local
    except OSError:
        pass
    try:
        import subprocess
        common = subprocess.run(
            ["git", "-C", root, "rev-parse", "--path-format=absolute",
             "--git-common-dir"],
            capture_output=True, text=True, timeout=10).stdout.strip()
        if common.endswith("/.git"):
            main = os.path.join(os.path.dirname(common), "reports")
            if os.path.isdir(main):
                return main
    except Exception:                                             # noqa: BLE001
        pass
    return local

#: The ONE bot_state key this script may write. Same shape as
#: `evidence_review._assert_write_target` — one script, one key, asserted at
#: the call rather than trusted.
CADENCE_KEY = "review-cadence"

#: How long the published key stays meaningful. 26h, so a DAILY routine that
#: skipped exactly one slot already reads LATE on the vitals card, and the
#: watchdog's 3x rule puts DARK at ~78h — three missed days, which is the bar
#: below which a weekend away would cry wolf and above which a real outage
#: (the 7-13 Aug one ran SIX days) is still caught early.
CADENCE_TTL_S = 26 * 3600

#: SYDNEY, because these are the operator's days — a routine that fires at
#: 07:33 Sydney is on the previous UTC day for most of its life, and dating it
#: in UTC is the `(mb)` defect that ate a 31,223-byte report.
TZ = "Australia/Sydney"


class Routine:
    """One scheduled review job: what it is, how often, and what it leaves behind.

    `evidence` is how a completed run is PROVEN, and there are two shapes in
    this fleet, so both are modelled rather than one being forced into the
    other:
      * "file"    — one file per period, named with the period's Sydney date
                    (`reports/daily_pnl_2026-09-10.md`).
      * "section" — a dated section appended to a single append-only log
                    (`reports/expansion_research_log.md`, `## 2026-09-09`).
    """

    def __init__(self, task_id, label, cadence, evidence, target, weekday=None,
                 grace_h=0):
        self.task_id = task_id
        self.label = label
        self.cadence = cadence            # daily | weekly | monthly
        self.evidence = evidence          # file | section
        self.target = target              # filename prefix, or log path
        self.weekday = weekday            # 0=Mon .. 6=Sun, for weekly
        self.grace_h = grace_h            # hours after the slot before LATE


#: THE DECLARATION. Cadences mirror the scheduler's cron expressions (LOCAL
#: Sydney time) as of 2026-09-11; `--check` compares OUTPUT against them, so a
#: schedule changed in the scheduler and not here shows up as a phantom gap
#: rather than silently passing — which is the safe direction.
ROUTINES = (
    Routine("daily-evidence-review", "🧾 daily evidence review",
            "daily", "file", "evidence_review", grace_h=14),
    Routine("crypto-daily-pnl", "📨 daily P&L brief",
            "daily", "file", "daily_pnl", grace_h=14),
    Routine("crypto-weekly-pnl", "🗓️ weekly verdict",
            "weekly", "file", "weekly_verdict", weekday=0, grace_h=36),
    Routine("crypto-research-review", "🔬 expansion research",
            "weekly", "section", "expansion_research_log.md", weekday=2,
            grace_h=36),
    Routine("crypto-monthly-pnl", "📅 monthly go-live board",
            "monthly", "file", "monthly_golive_board", grace_h=48),
)

#: Verdicts, worst last — `--check` fails on OVERDUE, and UNKNOWN is reported
#: loudly but does not fail, because a missing reports directory on some other
#: machine is not evidence that a routine died.
OK, LATE, OVERDUE, UNKNOWN = "OK", "LATE", "OVERDUE", "UNKNOWN"


# ---------------------------------------------------------------------------
# pure date arithmetic — no I/O, so the selftest can drive every branch
# ---------------------------------------------------------------------------
def sydney_now(now_utc=None):
    """-> aware datetime in the operator's zone. Falls back to UTC loudly."""
    t = now_utc or _dt.datetime.now(_dt.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return t.astimezone(ZoneInfo(TZ))
    except Exception:                                         # noqa: BLE001
        return t


def expected_days(routine, now_syd, back=60):
    """-> [date] the routine OWED an output for, most recent first.

    The current period is included only once its grace has passed, so a
    routine read at 08:00 on its own morning is not reported as missing its
    own not-yet-due run — the false alarm that would train the reader to
    ignore this whole table ((gl): a guard nobody acts on is not a guard).
    """
    out = []
    today = now_syd.date()
    if routine.cadence == "daily":
        start = today if now_syd.hour >= routine.grace_h else today - _dt.timedelta(days=1)
        for i in range(back):
            out.append(start - _dt.timedelta(days=i))
    elif routine.cadence == "weekly":
        d = today
        while d.weekday() != routine.weekday:
            d -= _dt.timedelta(days=1)
        if (now_syd - _dt.datetime.combine(
                d, _dt.time(0, 0), tzinfo=now_syd.tzinfo)).total_seconds() < routine.grace_h * 3600:
            d -= _dt.timedelta(days=7)       # this week's slot is not yet due
        for i in range(back // 7):
            out.append(d - _dt.timedelta(days=7 * i))
    elif routine.cadence == "monthly":
        # The run fires on the 1st; the report it writes is labelled with the
        # month that JUST ENDED (the task's own rule). So the period key is one
        # month behind the run date — get this wrong and the detector reports a
        # board that cannot exist yet, which is the cry-wolf trap ((gl)).
        run = today.replace(day=1)
        if (now_syd - _dt.datetime.combine(
                run, _dt.time(0, 0), tzinfo=now_syd.tzinfo)).total_seconds() < routine.grace_h * 3600:
            run = (run - _dt.timedelta(days=1)).replace(day=1)
        d = (run - _dt.timedelta(days=1)).replace(day=1)      # the graded month
        for _ in range(max(1, back // 30)):
            out.append(d)
            d = (d - _dt.timedelta(days=1)).replace(day=1)
    return out


def verdict(missing_recent, produced_any):
    """-> (status, why) from the gap at the FRONT of the expected series.

    Keyed on CONSECUTIVE misses at the head, not on a count over the window: a
    routine that missed three days a fortnight ago and has run every day since
    is healthy now, and reporting it as OVERDUE would be the cry-wolf trap.
    """
    if produced_any is None:
        return UNKNOWN, "reports directory unreadable — cannot say"
    if not produced_any:
        return UNKNOWN, "no output of this kind has ever been seen here"
    n = missing_recent
    if n == 0:
        return OK, "current"
    if n == 1:
        return LATE, "one period missed"
    return OVERDUE, f"{n} consecutive periods missed"


def head_gap(expected, have):
    """-> how many periods at the FRONT of `expected` have no output."""
    n = 0
    for d in expected:
        if d in have:
            break
        n += 1
    return n


# ---------------------------------------------------------------------------
# evidence gathering — the only I/O
# ---------------------------------------------------------------------------
_DAY = re.compile(r"(\d{4}-\d{2}-\d{2})")
_MONTH = re.compile(r"(\d{4}-\d{2})(?!-\d)")


def produced_days(routine, reports_dir=REPORTS):
    """-> set of date objects the routine has evidence for, or None if unknown.

    None is NOT an empty set. An unreadable directory means "cannot say", and
    every caller must keep the two apart — the whole point of this module is
    that silence and health stopped being the same string.
    """
    if not os.path.isdir(reports_dir):
        return None
    try:
        if routine.evidence == "section":
            path = os.path.join(reports_dir, routine.target)
            if not os.path.exists(path):
                return set()
            with open(path, "r", errors="replace") as fh:
                text = fh.read()
            days = set()
            for line in text.splitlines():
                if line.startswith("## "):
                    m = _DAY.search(line)
                    if m:
                        days.add(_dt.date.fromisoformat(m.group(1)))
            return days
        days = set()
        for p in glob.glob(os.path.join(reports_dir, routine.target + "_*.md")):
            base = os.path.basename(p)
            if ".superseded-" in base:
                continue                       # a backup is not a second run
            if routine.cadence == "monthly":
                m = _MONTH.search(base)
                if m:
                    days.add(_dt.date.fromisoformat(m.group(1) + "-01"))
                continue
            m = _DAY.search(base)
            if m:
                days.add(_dt.date.fromisoformat(m.group(1)))
        return days
    except OSError:
        return None


def survey(now_utc=None, reports_dir=None, back=60):
    """-> [row] one per routine, newest-first gap analysis. Never raises."""
    if reports_dir is None:
        reports_dir = reports_dir_resolved()
    now_syd = sydney_now(now_utc)
    rows = []
    for r in ROUTINES:
        have = produced_days(r, reports_dir)
        exp = expected_days(r, now_syd, back=back)
        if have is None:
            status, why = verdict(0, None)
            gap, missing, last = 0, [], None
        else:
            gap = head_gap(exp, have)
            missing = [d.isoformat() for d in exp if d not in have]
            last = max(have).isoformat() if have else None
            status, why = verdict(gap, have)
        rows.append({
            "task_id": r.task_id, "label": r.label, "cadence": r.cadence,
            "status": status, "why": why, "gap_periods": gap,
            "last_output": last,
            "missing_recent": missing[:10],
            "missing_in_window": len(missing),
            "window_periods": len(exp),
        })
    return {
        "generated_syd": now_syd.isoformat(timespec="seconds"),
        "updated": (now_utc or _dt.datetime.now(_dt.timezone.utc)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "ttl_sec": CADENCE_TTL_S,
        "reports_dir_readable": os.path.isdir(reports_dir),
        "routines": rows,
    }


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
_MARK = {OK: "✅", LATE: "⚠️", OVERDUE: "🔴", UNKNOWN: "❔"}


def gap_line(s):
    """-> the ONE line a report leads with. Says 'current' only when it is.

    This exists so a routine can never again publish a report that silently
    compares against a five-day-old baseline while calling it "yesterday".
    """
    bad = [r for r in s["routines"] if r["status"] in (LATE, OVERDUE)]
    unk = [r for r in s["routines"] if r["status"] == UNKNOWN]
    if not bad and not unk:
        return "CADENCE: all review routines current."
    parts = []
    for r in sorted(bad, key=lambda x: -x["gap_periods"]):
        parts.append(f"{r['label']} {r['gap_periods']} {r['cadence'][:-2] if False else 'period'}"
                     f"{'s' if r['gap_periods'] != 1 else ''} behind"
                     f" (last {r['last_output'] or 'never'})")
    for r in unk:
        parts.append(f"{r['label']} UNKNOWN ({r['why']})")
    return "CADENCE GAP — " + "; ".join(parts)


def render(s):
    out = [f"REVIEW CADENCE — {s['generated_syd']} (Sydney)", ""]
    if not s["reports_dir_readable"]:
        out.append("  reports/ not readable here — every row is UNKNOWN, which")
        out.append("  is NOT the same as clean. Run this on the machine that")
        out.append("  writes the reports.")
        out.append("")
    for r in s["routines"]:
        out.append(f"{_MARK[r['status']]} {r['label']:<28} {r['status']:<8} "
                   f"last={r['last_output'] or '—':<12} {r['why']}")
        if r["missing_recent"]:
            out.append(f"     missing: {', '.join(r['missing_recent'])}"
                       f"{' …' if r['missing_in_window'] > len(r['missing_recent']) else ''}"
                       f"   ({r['missing_in_window']} of {r['window_periods']} in window)")
    out.append("")
    out.append(gap_line(s))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# publish — one key, asserted
# ---------------------------------------------------------------------------
def _assert_write_target(key):
    if key != CADENCE_KEY:
        raise RuntimeError(
            f"refusing to write bot_state[{key!r}] — this script may only "
            f"write {CADENCE_KEY!r}")
    return key


def publish(payload):
    """UPSERT bot_state['review-cadence']. Returns True on success.

    Autocommit + a lock timeout, for the reason `evidence_review.connect`
    records at length: a read-only helper holding an uncommitted transaction
    stalled every publisher in the fleet for 26 minutes on 9-Sep.
    """
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        print("no DATABASE_URL/DATABASE_PUBLIC_URL — not published", file=sys.stderr)
        return False
    key = _assert_write_target(CADENCE_KEY)
    import psycopg2
    conn = psycopg2.connect(url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SET lock_timeout = '5s'")
            cur.execute(
                """INSERT INTO bot_state (bot, updated_at, state)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (bot) DO UPDATE
                      SET updated_at=now(), state=EXCLUDED.state""",
                (key, json.dumps(payload)))
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------------------
def _selftest():
    import tempfile
    syd = sydney_now()
    tz = syd.tzinfo

    def at(y, m, d, hh=12):
        return _dt.datetime(y, m, d, hh, tzinfo=tz).astimezone(_dt.timezone.utc)

    daily = ROUTINES[0]        # evidence review
    brief = ROUTINES[1]        # daily P&L brief
    wk = ROUTINES[2]

    # -- expected_days: the current day counts only after its grace ---------
    early = _dt.datetime(2026, 9, 11, 6, tzinfo=tz)
    late = _dt.datetime(2026, 9, 11, 20, tzinfo=tz)
    assert expected_days(daily, early)[0] == _dt.date(2026, 9, 10), \
        "before grace, today is not yet owed"
    assert expected_days(daily, late)[0] == _dt.date(2026, 9, 11), \
        "after grace, today is owed"

    # -- head_gap counts CONSECUTIVE misses at the front, not the window ----
    exp = [_dt.date(2026, 9, d) for d in (10, 9, 8, 7, 6)]
    assert head_gap(exp, {_dt.date(2026, 9, 10)}) == 0
    assert head_gap(exp, {_dt.date(2026, 9, 9)}) == 1
    assert head_gap(exp, {_dt.date(2026, 9, 7)}) == 3
    assert head_gap(exp, set()) == 5
    # an old gap with a healthy head is NOT overdue — the cry-wolf guard
    assert head_gap(exp, {_dt.date(2026, 9, 10), _dt.date(2026, 9, 9)}) == 0

    # -- verdict: UNKNOWN is never OK --------------------------------------
    assert verdict(0, None)[0] == UNKNOWN, "unreadable must not read clean"
    assert verdict(0, set())[0] == UNKNOWN, "never-seen must not read clean"
    # ...and they must SAY WHICH. Both are UNKNOWN, so a status-only assertion
    # is vacuous — a mutation round proved it, surviving the deletion of the
    # whole `is None` branch. "I cannot read the directory" and "this routine
    # has never produced output" are different operator actions (I8).
    assert "unreadable" in verdict(0, None)[1], verdict(0, None)
    assert "ever been seen" in verdict(0, set())[1], verdict(0, set())
    assert verdict(0, None)[1] != verdict(0, set())[1]
    assert verdict(0, {1})[0] == OK
    assert verdict(1, {1})[0] == LATE
    assert verdict(2, {1})[0] == OVERDUE

    # -- produced_days against a real directory ----------------------------
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "daily_pnl_2026-09-10.md"), "w").close()
        open(os.path.join(td, "daily_pnl_2026-09-09.md"), "w").close()
        # a preserved backup is NOT a second run
        # The backup is dated for a day with NO real report: if the skip is
        # removed, 09-08 wrongly reads as produced and a real missed day
        # disappears. (The first version of this fixture put the backup on a
        # day that also had a real file, so it could not discriminate — a
        # mutation round caught it.)
        open(os.path.join(td, "daily_pnl_2026-09-08.superseded-2108.md"), "w").close()
        got = produced_days(brief, td)
        assert got == {_dt.date(2026, 9, 10), _dt.date(2026, 9, 9)}, got
        assert _dt.date(2026, 9, 8) not in got, "a backup is not a second run"

        # the append-only log shape
        rr = ROUTINES[3]
        with open(os.path.join(td, rr.target), "w") as fh:
            fh.write("# log\n\n## 2026-09-09 — a thing\ntext\n"
                     "## 2026-09-02 (Wed, Sydney) — another\n")
        assert produced_days(rr, td) == {_dt.date(2026, 9, 9), _dt.date(2026, 9, 2)}

        # monthly keys on YYYY-MM
        mm = ROUTINES[4]
        open(os.path.join(td, "monthly_golive_board_2026-08.md"), "w").close()
        assert produced_days(mm, td) == {_dt.date(2026, 8, 1)}
        # THE LABEL IS THE MONTH THAT ENDED, NOT THE RUN'S MONTH. The first
        # live run of this tool reported the 1-Sep board MISSING because it
        # expected `2026-09`; the 1-Sep run correctly wrote `2026-08`.
        assert expected_days(mm, _dt.datetime(2026, 9, 11, 12, tzinfo=tz))[0] \
            == _dt.date(2026, 8, 1), expected_days(mm, _dt.datetime(2026, 9, 11, 12, tzinfo=tz))[:2]
        assert _dt.date(2026, 9, 1) not in expected_days(
            mm, _dt.datetime(2026, 9, 11, 12, tzinfo=tz)), "a board for the RUNNING month is not owed"

        # -- survey end to end, and the gap line actually names the gap ----
        s = survey(now_utc=at(2026, 9, 11, 20), reports_dir=td)
        row = [r for r in s["routines"] if r["task_id"] == "crypto-daily-pnl"][0]
        assert row["status"] == LATE and row["gap_periods"] == 1, row
        assert "behind" in gap_line(s), gap_line(s)
        assert s["ttl_sec"] == CADENCE_TTL_S
        assert render(s)

    # -- fail-closed on a missing directory --------------------------------
    s = survey(now_utc=at(2026, 9, 11), reports_dir="/nonexistent/reports")
    assert all(r["status"] == UNKNOWN for r in s["routines"])
    assert "CADENCE GAP" in gap_line(s), "unknown must not render as current"
    assert s["reports_dir_readable"] is False

    # -- the reports dir resolves ACROSS WORKTREES --------------------------
    # A per-session worktree has an EMPTY reports/ while the real reports sit
    # in the main checkout; the first live run reported all five routines
    # "never seen" from one. Both branches are driven here.
    with tempfile.TemporaryDirectory() as wt:
        os.makedirs(os.path.join(wt, "reports"))
        assert reports_dir_resolved(wt) == os.path.join(wt, "reports"), \
            "no git, no reports: fail closed to the local path"
        open(os.path.join(wt, "reports", "daily_pnl_2026-09-10.md"), "w").close()
        assert reports_dir_resolved(wt) == os.path.join(wt, "reports"), \
            "a local dir that HOLDS reports is preferred"

    # -- the write gate ----------------------------------------------------
    try:
        _assert_write_target("bot_pnl")
    except RuntimeError:
        pass
    else:                                                      # pragma: no cover
        raise AssertionError("the write gate let a foreign key through")

    # -- weekly lands on its own weekday -----------------------------------
    e = expected_days(wk, _dt.datetime(2026, 9, 11, 12, tzinfo=tz))
    assert all(d.weekday() == 0 for d in e), e
    assert e[0] == _dt.date(2026, 9, 7), e[0]

    print("review_cadence selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gap", action="store_true",
                    help="print only the one-line cadence header")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="upsert bot_state['review-cadence']")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when any routine is OVERDUE")
    ap.add_argument("--reports", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()

    s = survey(reports_dir=a.reports or reports_dir_resolved())
    if a.json:
        print(json.dumps(s, indent=2))
    elif a.gap:
        print(gap_line(s))
    else:
        print(render(s))

    if a.publish:
        ok = publish(s)
        print(f"published: {ok}", file=sys.stderr)

    if a.check:
        bad = [r for r in s["routines"] if r["status"] == OVERDUE]
        if bad:
            print("\nOVERDUE: " + ", ".join(r["task_id"] for r in bad),
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
