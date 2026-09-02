#!/usr/bin/env python3
"""START HERE. What shipped, what is carried, what is stuck — DERIVED, not remembered.

**Operator, 2026-08-20: "can all of the works done today; every day be recorded
properly so I am starting from where I left off every day rather than doing
circles like an incompetent."**

The fleet already had a record: `CHANGELOG.md`, 9,000+ lines of prose. It is an
excellent history and a terrible handoff — nothing in it answers "what do I pick
up first?" without reading a day's worth of entries, and `audit_recurrence`
exists precisely because that failure is measurable: the changelog keeps
returning to subjects nobody closed.

I11 already says the right thing — *"State at the end of every pass what is
carried, and start the next pass from that list"* — and it is the one invariant
with no executable enforcement, which is why it has been observed by memory and
therefore not at all.

WHAT MAKES THIS DIFFERENT FROM ANOTHER DOCUMENT THAT ROTS: almost nothing here
is typed by hand.

  * **SHIPPED** is read from git — commits since local midnight, and the
    changelog letters they carry.
  * **STUCK** is read from the live fleet — books with no closes, levers pinned
    at a cage end, organs past their own TTL.
  * **CARRIED** is the one hand-written part, and every entry carries a
    `closes_when` PREDICATE that this script evaluates against the repo. An
    item whose predicate says DONE is reported as **CLOSE THIS** and fails
    `--check`. **You cannot carry work that is already finished, and the list
    cannot quietly become a museum** — which is the exact failure mode of every
    to-do list this repo has tried.

Times are Australia/Sydney, because the operator reads them (CLAUDE.md's
reporting rule); everything internal stays UTC.

    python3 scripts/session_state.py            # print it
    python3 scripts/session_state.py --write    # regenerate HANDOFF.md
    python3 scripts/session_state.py --check    # CI: no stale carried item
    python3 scripts/session_state.py --selftest
"""
import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HANDOFF = os.path.join(ROOT, "HANDOFF.md")
SYD = _dt.timezone(_dt.timedelta(hours=10))     # AEST; AEDT Oct-Apr is +11


def _sh(*args):
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception:                                            # noqa: BLE001
        return ""


def _has(path, needle):
    try:
        with open(os.path.join(ROOT, path)) as fh:
            return needle in fh.read()
    except OSError:
        return False


# ---------------------------------------------------------------------------
# CARRIED — the one hand-written list, and every row must be falsifiable.
#
# `closes_when` returns True when the item is DONE. A row whose predicate is
# True is reported CLOSE THIS and fails --check, so the list cannot rot in
# either direction: a finished item cannot linger, and an unfinished one cannot
# be dropped without deleting a row somebody has to justify deleting.
#
# `owner` is who can close it. "session" = the next session may just do it;
# "OPERATOR" = it needs a decision this repo may not make.
# ---------------------------------------------------------------------------
CARRIED = [
    {
        "id": "counterweight-preregistered-fresh-read",
        "owner": "session",
        "what": "⚖️ Counterweight was KEPT 1-Sep under I17-as-amended with a "
                "PRE-REGISTERED read (I21, recorded in CLAUDE.md's "
                "acknowledged-recurrence line for perps-funding-spread): "
                "grade the FRESH on-class closes (class_split, closes AFTER "
                "1-Sep only — never the window that motivated the keep) at "
                "n>=60 or on 1-Oct, whichever first. RETIRE without further "
                "debate if the fresh on-class upper bound (m+1.28*SE) <= 0; "
                "keep grading if the fresh mean > 0; anything else returns "
                "to Eamon with both numbers.",
        "why_open": "the read date has not arrived. This row is the tripwire "
                    "the registration lacked: its predicate fires on 1-Oct, "
                    "so CI reds until a session actually PERFORMS the read "
                    "and closes this row with the verdict in the CHANGELOG. "
                    "If fresh on-class n reaches 60 EARLIER, do the read "
                    "then — the date is the backstop, not the trigger.",
        # Deliberately date-only: the predicate firing means the read is DUE,
        # and the honest way to close the row is to run the read and record
        # the verdict — deleting it without the verdict is the thing the
        # preamble says somebody has to justify.
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 10, 1),
    },
    # [2026-08-25 (tc)] `farmer-live-swap-operator-steps` DELETED — spent, and
    # its closes_when could never fire: it watched for a `georgia-live` service
    # while the (tb) plan change converted `trail-blazer-live` IN PLACE (so no
    # credential was ever read), and the swap EXECUTED 22-Aug with the flatten
    # receipt read (`open == 0`), the row hidden + pruned, and the registries
    # synced ((tb) + the (tc) sweep that caught the three it missed:
    # deploy_live_verify's service->row map, respiration's LIVE_BREATHS,
    # market_context's LIVE_CADENCE_SEC). The row's own text also named two
    # registries that never existed (`fleet_books.LIVE_DEPLOY`,
    # `PROP_LIVE_ROWS`) — corrected in MUM_GOLIVE_RUNBOOK.md's activation list.
    # [2026-09-02] `funding-studies-inherit-the-rank-universe` DELETED —
    # CLOSED by its own predicate: study_farmer_take_profit now applies the
    # live $10M/day floor by DEFAULT via the loader-owned minvol_entry_ok
    # (moved into backtest_funding_lighter, one owner; the gate study
    # imports it by identity). breadth + persistence stay header-recorded
    # refusals: (vj) measured their floored populations at n=0 / all-zero
    # arms, so wiring the floor there yields an instrument that measures
    # nothing; xsect never used the rank loader.
    {
        "id": "allocation-clamp-is-a-per-position-bound-doing-per-book-duty",
        "owner": "OPERATOR",
        "what": "💰 fleet_allocation's [0.25, 4.0] clamp is a per-POSITION "
                "slippage bound being asked to do a per-BOOK job. **[(vj)] THE "
                "4.0 ALARM THIS ROW USED TO CARRY IS WITHDRAWN — it was "
                "measured stale.** It read '💰 sits AT its 4.0 ceiling on 🌾 "
                "carry right now, delta_usd +13,500, $14,400 of gross on a "
                "$1,000 book'. Measured on the live payload 27-Aug: the MAXIMUM "
                "scale anywhere in the fleet is **1.594** (🙏 avo shadow) and "
                "carry sits at **1.272** ($1,271.75 target on a $1,000 book). "
                "(tz) replaced the winner-take-all split with a tilted flat "
                "prior, which made 4.0 structurally unreachable — so the row "
                "described the organ as it behaved BEFORE the fix that had "
                "already shipped. What survives is LATENT, not live: the "
                "ceiling still PERMITS a scale that breaches the 15% go-live "
                "drawdown bar, because maxDD is the one bar that is NOT "
                "clip-invariant ((hl) measured per-trade % invariance for the "
                "other five) — ⚖️ Counterweight breaches at 3.06x, inside the "
                "4.0 ceiling.",
        "why_open": "the clamp is a capital-allocation policy and moving it "
                    "moves money between books — an operator call (I16), not a "
                    "session one. It is NOT urgent: nothing is near the "
                    "ceiling today. What a session CAN do first is derive the "
                    "per-book bound the drawdown bar implies (the "
                    "`GROSS_X_MAX = 0.15/|stop|` shape (sr) used on avo) and "
                    "publish it beside the claim, so the ceiling stops being a "
                    "single number shared by books with different stops.",
        # closes when the clamp is re-decided (either bound moves) or carry's
        # slot count and clip stop multiplying out past its own equity.
        "closes_when": lambda: not _has("fleet_bus.py",
                                        "ALLOC_SCALE_CEIL = 4.0"),
    },
    {
        "id": "brain-mult-transition-oscillation",
        "owner": "session",
        "what": "The brain's `t` is computed on DOLLARS "
                "(`brain_stats.weighted_bucket` reads `profit_abs`), so a "
                "bucket MID-TRANSITION is a mixture of two clip scales: sd "
                "inflates against mean and `t` falls on a book whose edge has "
                "not moved. Predicted shape: a bucket that clears a rung steps "
                "back down a rung within ~10 closes, then climbs again. A "
                "uniform scale is invariant, so there is no runaway — this is "
                "a transient limit cycle, damped by the 14d decay and the "
                "3-run streak gate.",
        "why_open": "the fix is hysteresis in the PUBLISHER (`qualify_v3` is "
                    "stateless; the held rung lives in bot_learn's "
                    "`mult_streaks`), and rewriting the brain's ladder on the "
                    "same day 13 consumers were wired to it is the untested-"
                    "rewrite-of-an-authority the doctrine forbids. It is now "
                    "MEASURABLE for the first time — every close carries its "
                    "`brain_mult` — so the next pass tests the prediction "
                    "against real closes instead of a model.",
        "closes_when": lambda: _has("brain_stats.py", "HYSTERESIS"),
    },
    {
        "id": "brain-mults-are-two-opinions-wide",
        "owner": "session",
        "what": "(so) wired every living book to the brain's stake multiplier, "
                "including both real-money rows — and on the day it shipped the "
                "brain had exactly TWO published opinions across twenty books "
                "(taker short-divergence 0.75, Counterweight long 0.75). The "
                "plumbing is done; the ORGAN is nearly silent, because a mult "
                "needs >=30 era closes AND >=3 consecutive runs and most books "
                "never reach the first. The open question is whether those "
                "floors are right now that the range is 6.7x either way: a "
                "floor calibrated for a 1.5x ceiling is not obviously the floor "
                "for a 6.7x one.",
        "why_open": "moving a brain floor changes what sizes EVERY book, real "
                    "money included — it needs its own measurement (how many "
                    "buckets would qualify at each floor, and what their "
                    "realised expectancy was), not a judgement call.",
        # closes when the floors stop being the shipped constants, i.e. someone
        # has actually re-decided them rather than inherited them.
        "closes_when": lambda: not _has("bot_learn.py", "PROMOTE_RUNS = 3"),
    },
    # [2026-09-02] `taker-replay-blind-to-breakoutup` DELETED — BOTH halves
    # done. The blindness half was fixed 20-Aug (daily_up_resolver + the
    # relabel, forwarded by the tuner and incubator, selftest-pinned) and
    # this row never fired because its predicate watched a string that
    # legitimately survives as the no-resolver fallback. The cage half was
    # re-decided 2-Sep on LIVE evidence (tuner baseline breakoutup
    # taken=26 closed=23): brk_range/max_hold_h two-way again, coupled to
    # sight by test_breakoutup_ratchet.test_the_unpin_is_coupled_to_the_
    # gates_sight; brk_trail/brk_sl stay pinned (walked by nothing,
    # widenings measured-and-withheld).
    {
        "id": "breakout-arm-inherits-reversion-clock",
        "owner": "session",
        "what": "bull_exit() hands the breakout TREND exit the reversion arm's "
                "MAX_HOLD_H. A rule built to let a winner run (no TP cap, wide "
                "stop, trailing give-back) is timed by a mean-reversion book's "
                "clock; 23-32 of 37 replayed exits are that clock, not the trail.",
        "why_open": "splitting it decouples the arm from a lever the rail "
                    "actively moves, and the only evidence for 48h->96h died "
                    "to leave-one-symbol-out (+0.78pp -> +0.07pp ex-HYPE).",
        "closes_when": lambda: _has("lighter_ticket_taker.py",
                                    "BRK_MAX_HOLD_H"),
    },
    {
        "id": "ceiling-slots-georgia",
        "owner": "session",
        "what": "**(sv) ANSWERED THE CENSUS QUESTION AND THE ANSWER RETIRES THE "
                "HEADLINE.** This row read '83.5 DAYS at 0.5 of 5 slots, 7.6 "
                "days at full occupancy — an 11x speed-up'. Measured: her mean "
                "hold is **2.6h**, so occupancy = closes/day x 2.6/24 and FIVE "
                "slots need ~46 opens/day. Her signal supplies 40.9/day at "
                "best. **Full occupancy is unreachable by construction, and it "
                "was never the lever — CLOSES are.** She is flat 68.4% of the "
                "time not because something refuses her but because she exits "
                "in under 3 hours. (sv) took the one gate that cut closes for "
                "no quality reason (the 2/h throttle, +0.633pp in favour of the "
                "entry it refused, six splits) from 2 -> 3.",
        "why_open": "the step is DELIBERATELY one notch: rank 3 has n=1 in her "
                    "whole life because the cap was 2, so everything above it "
                    "is extrapolation. `entry_rank` now rides every close, so "
                    "the next step is graded from a query — re-run "
                    "`scripts/study_georgia_entry_rank_2026-08-22.py` once "
                    "rank-3 rows exist and take 3 -> 4 only if it holds. "
                    "[26-Aug (tm) pass]: rank-3 today reads n=3, 0% win, "
                    "crash-dominated — decides NOTHING either way; 3 of the "
                    "six (sv) controls have flipped negative, so the 3->4 "
                    "step is REFUSED on current data and 3->2 reversion "
                    "equally unsupported. The OTHER half is now MEASURED AND "
                    "CLOSED: the calibrated LAG-1 hold/roi sweep (n=100 "
                    "paired, both intrabar conventions) put every widening "
                    "below the harness's own +0.246pp calibration error, "
                    "roi-x2's gain is h2-NEGATIVE, trail-only sign-disagrees "
                    "between conventions, and the 1440m max_hold fired 0 of "
                    "207 closes ever — exits are a dead dial on this book; "
                    "the mean lever is ENTRY quality (rank1 +0.023% vs rank2 "
                    "+0.656% on her own ledger).",
        # closes when the next throttle decision has been taken on rank-3 data
        "closes_when": lambda: _has(
            "lighter_family_bot.py", 'GEORGIA_MAX_ENTRIES_PER_HOUR", "4"'),
    },
    {
        "id": "ceiling-capital-inversion",
        "owner": "OPERATOR",
        "what": "Capital sits in INVERSE proportion to measured edge: the two "
                "worst books run at 88-102% of capacity (⚖️ Counterweight "
                "-1.433%, 🛢️ Garrett -1.460%) while 👩 mum at +4.658%/trade is "
                "capped at FOUR slots and 🙏 avo at +1.085% uses 40% of six. "
                "`fleet_allocation` computes the right answer and is ADVISORY "
                "with consumers on three funding books only.",
        "why_open": "moving capital between books is an operator call, not a "
                    "session one — the organ already ranks it honestly (I16).",
        "closes_when": lambda: False,
    },
    {
        "id": "books-should-declare-themselves",
        "owner": "session",
        "what": "18 of 19 living books do not publish `extra.thesis` — their "
                "design lives in `fleet_manifest`'s bridge table instead of on "
                "the row. `design_for` already prefers a book's own "
                "publication, so each migration is one publish-site edit and "
                "the manifest entry goes quiet on its own.",
        "why_open": "18 bot edits and 18 deploys; do it a book at a time on "
                    "the next deploy each one earns for another reason.",
        "closes_when": lambda: _thesis_coverage_complete(),
    },
    {
        "id": "unmeasurable-lever-backlog",
        "owner": "session",
        "what": "30 registered levers still have no QUANTITIES spec — no "
                "recorded quantity to profile them against. The ratchet in "
                "audit_lever_measurability stops the pile GROWING; draining it "
                "is per-lever work: record what the knob cuts, then spec it.",
        "why_open": "each one needs the bot to stamp its own governing "
                    "quantity first (the (sk) give_back/mae_ret pattern).",
        "closes_when": lambda: _ratchet_at_or_below("unmeasurable", 0),
    },
    # [2026-09-02] `taker-divergence-stop-unpriced` DELETED — THE MEASUREMENT
    # WAS RUN (scripts/study_taker_divergence_stop_2026-09-02.py, 503.7h of
    # recorded tape through the taker's own replay) and the verdict is a
    # REFUSAL WITH EVIDENCE: (1) the study's own calibration gate refuses —
    # the book's last REAL divergence close is 20-Aug and the lens is vetoed
    # by its own realised record, so the instrument cannot be calibrated
    # against a live sample it can no longer produce; (2) descriptively, the
    # only cage-reachable move (taker.sl -0.03 -> -0.04) measured NEGATIVE
    # (-$2.80 full-tape) — the apparent gains live beyond the cage (-0.05:
    # +$16.45, -0.06: +$29.96) on div n of 9-20 with unstable halves, i.e.
    # slot-reallocation noise as much as exit value. Pricing a stop for a
    # lens the book refuses to trade is not a candidate; if the veto ever
    # lifts on fresh evidence, re-run the study THEN, on the closes that
    # lifted it.
    {
        "id": "georgia-t-bar",
        "owner": "session",
        "what": "🔮 georgia is 5 of 6 go-live bars, failing only t. "
                "[MEASURED 26-Aug (tm) pass]: the weak t is ONE real 3-leg "
                "flash-crash batch (22-Aug 05:11Z: XRP -16.4/NEAR -19.5/TRX "
                "-3.0) = 73.5% of cluster variance — drop those 3 rows and "
                "t_cluster reads +2.51. Tail CONTROL cannot clear the bar "
                "honestly (at the live arm's own measured -7.17% crash fill "
                "for a -5% stop, t_cluster caps at ~1.40), and the "
                "stress-metric entry pause is REFUTED on the fleet's own "
                "instrument (scout stress read 8.6bps at the 05:00:33 entry "
                "vs the taker's 15bps bar; the 11.8 peak came 13 MINUTES "
                "after the dump started). Exits are a dead dial (see "
                "ceiling-slots-georgia). What remains is ENTRY QUALITY: the "
                "crash entry rode a +7.5%-in-50-min parabolic spike, and "
                "rank1 entries earn +0.023% vs rank2's +0.656%.",
        "why_open": "[26-Aug (tp)]: the parabolic-extension veto was RUN and "
                    "REFUTED-AS-OVERFIT, adversarially confirmed — the best "
                    "cell's whole effect is the three crash rows; ex-crash it "
                    "forgoes $+10.17 of winners and refuses 73% of "
                    "trend_breakout's supply (I7); random-veto null P~0.10, "
                    "forced-kept P=0.0002 / conditional P=0.37. BOTH her "
                    "dials are now measured dead (exits at (tm), the entry "
                    "filter at (tp)). What remains: (1) the rank1-vs-rank2 "
                    "gap (+0.55pp, NOT explained by extension — corr −0.050) "
                    "gets its own pre-registered study on fresh closes once "
                    "rank-3 stamps accrue; (2) her live arm accrues under "
                    "the (tm)-fixed policy — time, not tuning.",
        "closes_when": lambda: False,
    },
    {
        "id": "carry-garrett-ranking-collision",
        "owner": "OPERATOR",
        "what": "🌾 carry's measured-depth gate now reaches the whole of 🛢️ "
                "Garrett's [0.1M, 2M) band, and Garrett's own (pl) measurement "
                "found 6 of 6 of its top-ranked candidates are >=20% APR — so "
                "carry is a rival for exactly the supply Garrett ranks first. "
                "A RANKING collision; audit_book_overlap's axes (apr x vol x "
                "class) cannot express it.",
        "why_open": "declared in KNOWN_CELL_COLLISIONS; the call is the same "
                    "~12-Sep decision point as the rest of that component.",
        "closes_when": lambda: False,
    },
]


def _thesis_coverage_complete():
    """True once every living row publishes its OWN design and the bridge
    table is empty — the state this carried item is waiting for."""
    try:
        import fleet_manifest
        return not fleet_manifest.DESIGN
    except Exception:                                            # noqa: BLE001
        return False


def _ratchet_at_or_below(key, n):
    try:
        import audit_lever_measurability as alm
        ok, _lines, counts = alm.check()
        return counts.get({"unmeasurable": "UNMEASURABLE",
                           "dead": "DEAD"}[key], 99) <= n
    except Exception:                                            # noqa: BLE001
        return False


# ---------------------------------------------------------------------------

def shipped_today(now=None, since=None):
    """Commits since local midnight, with the changelog letters they carry.

    `since` is injectable so a test can prove this READS GIT rather than
    returning a plausible empty list — a function that always answers "nothing
    shipped" is indistinguishable from a quiet day, and that is precisely the
    silence the operator asked to be rid of.
    """
    now = now or _dt.datetime.now(SYD)
    if since is None:
        since = (now.replace(hour=0, minute=0, second=0, microsecond=0)
                 .astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    elif not isinstance(since, str):
        since = since.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    out = _sh("git", "log", "--since", since, "--format=%h\t%s")
    rows = [ln.split("\t", 1) for ln in out.splitlines() if "\t" in ln]
    letters = sorted({m.group(1) for _h, s in rows
                      for m in [re.search(r"\(([a-z]{1,2})\)\s*$", s)] if m})
    return rows, letters


def _dead_rows():
    """Row ids the fleet has retired, from the two registries that declare it.

    Fail-OPEN (empty set on any import trouble): a dark registry must not start
    reporting live rows as dead. The cost of failing open is a missed stale
    row; the cost of failing closed is a session sent to re-point a book that
    is trading fine."""
    try:
        import cleanup_legacy_bots as _legacy
        import fleet_bus as _fb
        return set(getattr(_fb, "RETIRED_LIVE_ARMS", {}) or {}) | \
            set(getattr(_legacy, "LEGACY_BOTS", ()) or ())
    except Exception:                                        # noqa: BLE001
        return set()


def subject_status():
    """-> [(id, row, why)] for every CARRIED row whose SUBJECT has been retired.

    [(vj)] A HANDOFF ROW OUTLIVED THE BOOK IT WAS ABOUT. `carried_status`
    answers "is the work done?" and nothing answered "does the thing still
    exist?" — so `farmer-cap-collapses-slots-under-conviction` kept demanding
    attention for 💸 the LIVE Farmer five days after (ta) retired it, with a
    predicate that could never fire. I11 makes this file the thing a session
    STARTS from, so a row pointed at a corpse spends the scarcest resource
    there is: the first hour of the next pass.

    Deliberately NOT folded into `closes_when`. A dead subject does not mean
    the work is DONE — it means the row must be re-pointed at a living book or
    retired with a reason, and those are different acts with different owners.
    """
    dead = _dead_rows()
    if not dead:
        return []
    return [(it["id"], row,
             "subject retired — re-point this row at a living book or close it")
            for it in CARRIED for row in it.get("subject", ()) if row in dead]


def carried_status():
    """-> [(item, done)]. A predicate that RAISES counts as not-done, and says
    so: a broken predicate must not silently close an item."""
    out = []
    for it in CARRIED:
        try:
            done = bool(it["closes_when"]())
        except Exception as e:                                   # noqa: BLE001
            done = False
            it = dict(it, why_open=f"[predicate error: {type(e).__name__}] "
                                   + it["why_open"])
        out.append((it, done))
    return out


def render(now=None):
    now = now or _dt.datetime.now(SYD)
    rows, letters = shipped_today(now)
    status = carried_status()
    L = []
    L.append("# HANDOFF — start here\n")
    L.append(f"_Generated {now.strftime('%Y-%m-%d %H:%M')} Sydney "
             f"({now.astimezone(_dt.timezone.utc).strftime('%H:%M')}Z) by "
             "`scripts/session_state.py`. Do not hand-edit: regenerate it._\n")
    L.append("## Carried — pick these up FIRST (I11)\n")
    open_items = [(i, d) for i, d in status if not d]
    done_items = [(i, d) for i, d in status if d]
    if done_items:
        L.append("**CLOSE THESE — their own predicate says they are done:**\n")
        for it, _ in done_items:
            L.append(f"- ~~`{it['id']}`~~ — DONE, delete the row.")
        L.append("")
    if not open_items:
        L.append("_Nothing carried._\n")
    for it, _ in open_items:
        L.append(f"### `{it['id']}`  ·  owner: **{it['owner']}**")
        L.append(f"{it['what']}\n")
        L.append(f"_Still open because:_ {it['why_open']}\n")
    L.append(f"## Shipped today ({len(rows)} commit(s)"
             + (f", entries {', '.join('(' + x + ')' for x in letters)}"
                if letters else "") + ")\n")
    if not rows:
        L.append("_Nothing yet today._\n")
    for h, s in rows:
        L.append(f"- `{h}` {s}")
    L.append("")
    L.append("## How this file stays honest\n")
    L.append("Every carried row above carries a `closes_when` predicate that "
             "`--check` evaluates against the repo. A finished item cannot "
             "linger (it is reported CLOSE THIS and reddens CI) and an "
             "unfinished one cannot be dropped without deleting a row somebody "
             "has to justify. The shipped list is read from git, not typed.\n")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    text = render()
    if a.write:
        with open(HANDOFF, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {HANDOFF}")
    if a.check:
        stale = [i["id"] for i, d in carried_status() if d]
        if stale:
            print("audit_session_state: FAIL — carried item(s) whose own "
                  f"predicate says they are DONE: {', '.join(stale)}. "
                  "Delete the row (and say so in the changelog).")
            return 1
        # [(vj)] ...and a SECOND way a row goes stale: its subject retires
        # under it. Reported separately from `stale` because the remedy
        # differs — a done row is DELETED, a dead-subject row is RE-POINTED at
        # a living book or closed with a reason.
        orphan = subject_status()
        if orphan:
            print("audit_session_state: FAIL — carried item(s) pointed at a "
                  "RETIRED row:")
            for _id, _row, _why in orphan:
                print(f"  {_id}: {_row} — {_why}")
            return 1
        print(f"audit_session_state: OK — {len(CARRIED)} carried item(s), "
              "none stale, none orphaned.")
        return 0
    if not a.write:
        print(text)
    return 0


def selftest():
    # every row is well-formed and its predicate is callable and total
    ids = [i["id"] for i in CARRIED]
    assert len(ids) == len(set(ids)), f"duplicate carried id: {ids}"
    for it in CARRIED:
        # `subject` is OPTIONAL on purpose: several rows are about the fleet's
        # machinery rather than a book, and forcing a row id on those would
        # invite a made-up one. Where it IS given it must be a tuple of row
        # ids, so `subject_status` can never be handed a bare string and
        # iterate its characters.
        assert set(it) <= {"id", "owner", "what", "why_open", "subject",
                           "closes_when"}, it
        assert {"id", "owner", "what", "why_open", "closes_when"} <= set(it), it
        assert isinstance(it.get("subject", ()), tuple), it["id"]
        assert it["owner"] in ("session", "OPERATOR"), it
        assert it["what"].strip() and it["why_open"].strip(), it
        assert isinstance(it["closes_when"](), bool), it["id"]

    # a RAISING predicate must not close an item — it degrades to open and
    # labels itself, because a broken check that silently finishes work is the
    # worst outcome this file can produce
    boom = {"id": "x", "owner": "session", "what": "w", "why_open": "y",
            "closes_when": lambda: (_ for _ in ()).throw(RuntimeError("nope"))}
    CARRIED.append(boom)
    try:
        st = dict((i["id"], (i, d)) for i, d in carried_status())
        assert st["x"][1] is False
        assert "predicate error: RuntimeError" in st["x"][0]["why_open"]
    finally:
        CARRIED.remove(boom)

    # a predicate that reads TRUE is surfaced as CLOSE THIS and fails --check
    done = {"id": "already-done", "owner": "session", "what": "w",
            "why_open": "y", "closes_when": lambda: True}
    CARRIED.append(done)
    try:
        assert main(["--check"]) == 1
        assert "CLOSE THESE" in render() and "already-done" in render()
    finally:
        CARRIED.remove(done)
    assert main(["--check"]) == 0, "the real list has a stale row"

    # the live predicates actually discriminate — a check that can only ever
    # return False is decoration (the (po) inspects-nothing rule)
    assert _has("lighter_ticket_replay.py", "_up = False if lens") is True
    assert _has("lighter_ticket_replay.py", "a string that is not there") is False
    assert _has("no_such_file.py", "x") is False

    # the render names the owner, so an OPERATOR item cannot look like session
    # work a future pass will just pick up
    txt = render()
    assert "owner: **OPERATOR**" in txt and "owner: **session**" in txt, txt[:400]
    assert "Shipped today" in txt and "Carried" in txt
    print("session_state selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
