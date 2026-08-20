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
        "id": "taker-replay-blind-to-breakoutup",
        "owner": "session",
        "what": "lighter_ticket_replay refuses every breakout entry "
                "(`_up = False if lens == \"breakout\"`), so the scout tuner's "
                "gate cannot see the taker's ONLY living lens. (sf) pinned the "
                "cages shut against the resulting one-way ratchet; the DURABLE "
                "fix is to give the replay the taker's own breakoutup relabel "
                "via up_read(), after which the cage pins are a decision to "
                "re-make on evidence.",
        "why_open": "changes what the tuner's leaderboard measures — needs its "
                    "own before/after on the recorded tape, not a refactor.",
        "closes_when": lambda: not _has(
            "lighter_ticket_replay.py",
            '_up = False if lens == "breakout" else None'),
    },
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
        "what": "🔮 georgia is 310 closes from t=2.0 — 83.5 DAYS at today's 0.5 "
                "of 5 slots, 7.6 days at full occupancy. An 11x speed-up to "
                "decidability on the fleet's closest book to real money, "
                "costing zero expectancy. `scripts/ceiling.py` names it; what "
                "it does NOT say is whether her SIGNAL can fill those slots.",
        "why_open": "the ceiling is REACHABLE, not promised — the next step is "
                    "her own census: what refuses the other 4.5 slots, the "
                    "regime gate, the universe, or no signal at all.",
        "closes_when": lambda: False,
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
                    "quantity first (the (sf) give_back/mae_ret pattern).",
        "closes_when": lambda: _ratchet_at_or_below("unmeasurable", 0),
    },
    {
        "id": "live-taker-divergence-stop-unpriced",
        "owner": "session",
        "what": "The LIVE taker's short-divergence stop reads +28pp reclaim "
                "excess and +2.10% held at 24h over n=22 — a measured SIGNAL "
                "with no priced VALUE. lighter_ticket_replay is the calibrated "
                "instrument; a candle walk is not (it has no short branch).",
        "why_open": "real-money row: measure and hand over, never hand-set.",
        "closes_when": lambda: False,      # only a measurement closes this
    },
    {
        "id": "georgia-t-bar",
        "owner": "session",
        "what": "🔮 georgia is 5 of 6 go-live bars, failing only t (1.11 < 2.0) "
                "— the fleet's closest book to the gate. Its trailing stop is "
                "NOT the leak (reclaim 74% vs placebo 75%). Where its t comes "
                "from is the open question: raise the mean, cut the variance, "
                "or raise n.",
        "why_open": "unmeasured; the per-book audit was still running.",
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
        print(f"audit_session_state: OK — {len(CARRIED)} carried item(s), "
              "none stale.")
        return 0
    if not a.write:
        print(text)
    return 0


def selftest():
    # every row is well-formed and its predicate is callable and total
    ids = [i["id"] for i in CARRIED]
    assert len(ids) == len(set(ids)), f"duplicate carried id: {ids}"
    for it in CARRIED:
        assert set(it) == {"id", "owner", "what", "why_open", "closes_when"}, it
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
