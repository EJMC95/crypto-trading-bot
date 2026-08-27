"""[(sl)] I11 finally has enforcement: the carried list cannot rot either way.

**Operator, 2026-08-20: "can all of the works done today; every day be recorded
properly so I am starting from where I left off every day rather than doing
circles like an incompetent."**

I11 has said the right thing since 31-Jul — *"State at the end of every pass
what is carried, and start the next pass from that list"* — and it was the one
invariant with no executable enforcement, so it was observed by memory and
therefore not at all. `audit_recurrence` measures circling AFTER it happens; it
never told a session where to START.

The failure mode of every to-do list this repo has tried is rot in one of two
directions: finished items linger until nobody trusts the list, or unfinished
ones quietly vanish. Both are closed the same way — every carried row carries a
`closes_when` PREDICATE evaluated against the repo, so a done item is reported
CLOSE THIS and reddens CI, and an open one cannot be dropped without deleting a
row somebody has to justify deleting.
"""
import pytest

pytestmark = pytest.mark.autonomy

import scripts.session_state as S      # noqa: E402


def test_the_real_carried_list_has_no_stale_row():
    stale = [i["id"] for i, done in S.carried_status() if done]
    assert not stale, (
        f"carried item(s) whose own predicate says they are DONE: {stale}")


def test_every_row_is_falsifiable_and_owned():
    assert S.CARRIED, "the carried list is empty — that is a claim, verify it"
    ids = [i["id"] for i in S.CARRIED]
    assert len(ids) == len(set(ids)), ids
    for it in S.CARRIED:
        assert it["owner"] in ("session", "OPERATOR"), it
        assert len(it["what"]) > 60, f"{it['id']}: too thin to act on"
        assert len(it["why_open"]) > 20, f"{it['id']}: no reason it is open"
        assert isinstance(it["closes_when"](), bool), it["id"]


def test_a_finished_item_reddens_the_check():
    S.CARRIED.append({"id": "_t", "owner": "session", "what": "w" * 70,
                      "why_open": "y" * 30, "closes_when": lambda: True})
    try:
        assert S.main(["--check"]) == 1
        assert "CLOSE THESE" in S.render()
    finally:
        S.CARRIED[:] = [i for i in S.CARRIED if i["id"] != "_t"]


def test_a_BROKEN_predicate_does_not_close_an_item():
    """The dangerous direction. A predicate that raises must degrade to OPEN
    and label itself — a broken check that silently finishes work is worse
    than no check, and it is the (po) inspects-nothing failure aimed at the
    one list that decides what happens next."""
    S.CARRIED.append({"id": "_b", "owner": "session", "what": "w" * 70,
                      "why_open": "y" * 30,
                      "closes_when": lambda: 1 / 0})
    try:
        st = {i["id"]: (i, d) for i, d in S.carried_status()}
        assert st["_b"][1] is False
        assert "predicate error" in st["_b"][0]["why_open"]
        assert S.main(["--check"]) == 0, "a broken predicate must not fail CI"
    finally:
        S.CARRIED[:] = [i for i in S.CARRIED if i["id"] != "_b"]


def test_the_predicates_actually_discriminate():
    """A predicate that can only ever return False is decoration. At least one
    live row must be answerable from the repo, or the list is prose again."""
    assert S._has("lighter_ticket_replay.py", "_up = False if lens") is True
    assert S._has("lighter_ticket_replay.py", "not present anywhere") is False
    assert S._has("no_such_file.py", "x") is False
    answerable = [i["id"] for i in S.CARRIED
                  if i["closes_when"].__code__.co_names]
    assert len(answerable) >= 3, (
        f"only {len(answerable)} carried rows are machine-answerable — the "
        "rest are prose that will rot")


def test_shipped_is_read_from_git_not_typed():
    """Caught by a SURVIVING mutation: asserting only the SHAPE let a
    hard-coded empty list pass, and "nothing shipped" is indistinguishable
    from a quiet day. A wide window must return real commits."""
    rows, letters = S.shipped_today(since="2020-01-01T00:00:00")
    assert rows, "shipped_today returned nothing over a five-year window — it "\
                 "is not reading git"
    for h, subject in rows[:20]:
        assert len(h) >= 7 and subject, (h, subject)
    assert letters, "no changelog letters parsed from any commit subject"
    # …and today's window is a SUBSET of it, which is what makes the daily
    # number meaningful rather than a coincidence
    today, _ = S.shipped_today()
    assert len(today) <= len(rows)


def test_the_render_names_every_open_carried_id():
    """The rendered handoff is what a session actually reads. An item that is
    carried but absent from the render is carried by nobody."""
    txt = S.render()
    for it, done in S.carried_status():
        if not done:
            assert it["id"] in txt, it["id"]
            assert it["owner"] in txt.split(it["id"], 1)[1][:60], (
                f"{it['id']} is rendered without its owner")


def test_the_render_distinguishes_who_can_close_what():
    """An OPERATOR item that reads like session work is how a decision gets
    silently re-litigated instead of made."""
    txt = S.render()
    assert "owner: **OPERATOR**" in txt, "no operator-owned row is labelled"
    assert "owner: **session**" in txt
    assert "Shipped today" in txt and "Carried" in txt


def test_the_handoff_file_is_current():
    """A generated file that nobody regenerates is the rot this replaces."""
    import os
    if not os.path.exists(S.HANDOFF):
        pytest.fail("HANDOFF.md is missing — run session_state.py --write")
    body = open(S.HANDOFF).read()
    for it in S.CARRIED:
        if it["closes_when"]():
            continue
        assert it["id"] in body, (
            f"{it['id']} is carried but absent from HANDOFF.md — regenerate it")


# ---------------------------------------------------------------------------
# [(vg)] A CARRIED ROW WHOSE **SUBJECT** RETIRED UNDER IT
#
# `carried_status` asks "is the work done?". Nothing asked "does the thing this
# row is about still exist?" — so `farmer-cap-collapses-slots-under-conviction`
# demanded attention for 💸 the LIVE Farmer for five days after (ta) retired it,
# behind a predicate that could never fire (it grepped for `max_notional_frac`,
# a string that has never existed in this repo outside that lambda). A second
# row was stale the same way, calling the taker's SHADOW arm a "real-money row"
# a fortnight after its live arm was retired.
#
# I11 makes this file the thing a session STARTS from, so a row aimed at a
# corpse spends the scarcest resource there is: the first hour of the next pass.
# ---------------------------------------------------------------------------

def test_no_carried_row_points_at_a_retired_book():
    """The live list, against the fleet's own two retirement registries."""
    assert S.subject_status() == [], S.subject_status()


def test_the_subject_guard_actually_fires_on_a_dead_row():
    """BOTH DIRECTIONS. A guard that can only ever return empty is decoration
    ((po): a check that inspects nothing reports clean) — and one that flags
    everything is worse than none. Driven with a REAL retired row id and a REAL
    living one, so neither half can pass by accident."""
    dead = S._dead_rows()
    assert dead, "both retirement registries read empty — the guard is blind"
    # BOTH REGISTRY TERMS, PINNED SEPARATELY. `perps-funding-lighter-lighter`
    # is in RETIRED_LIVE_ARMS *and* LEGACY_BOTS, so a test using only it stays
    # green when either term is deleted — measured: dropping LEGACY_BOTS
    # survived the first mutation round. 🎸 band-barnes is in LEGACY_BOTS only
    # and is what makes that term load-bearing here.
    assert "perps-funding-lighter-lighter" in dead, sorted(dead)[:5]
    assert "band-barnes-lshadow" in dead, "the LEGACY_BOTS term is not wired"

    row = {"id": "_probe", "owner": "session", "what": "w" * 70,
           "why_open": "y" * 30, "closes_when": lambda: False,
           "subject": ("perps-funding-lighter-lighter",)}
    S.CARRIED.append(row)
    try:
        flagged = S.subject_status()
        assert [f[0] for f in flagged] == ["_probe"], flagged
        assert S.main(["--check"]) == 1, "a dead subject must fail --check"
        # ...and the LIVING half: same row, a book that still trades
        row["subject"] = ("lighter-ticket-taker-lshadow",)
        assert S.subject_status() == [], S.subject_status()
        assert S.main(["--check"]) == 0
    finally:
        S.CARRIED[:] = [i for i in S.CARRIED if i["id"] != "_probe"]


def test_both_registries_are_read_even_when_todays_data_cannot_tell_them_apart():
    """EACH TERM, ON ITS OWN. Every id in `RETIRED_LIVE_ARMS` today is ALSO in
    `LEGACY_BOTS`, so no live row can distinguish the two terms — measured:
    deleting the `RETIRED_LIVE_ARMS` term left the whole suite green. That is a
    property of today's data, not of the code, and it will silently become
    wrong the first time a live arm is retired without being pruned — which is
    exactly the (ta) deferred-prune window this fleet has already run once.

    So each term is driven against a stub. Not contrived: it asserts the
    function reads the registry it says it reads.
    """
    import fleet_bus as _fb
    import cleanup_legacy_bots as _legacy

    real_arms = getattr(_fb, "RETIRED_LIVE_ARMS", {})
    real_legacy = getattr(_legacy, "LEGACY_BOTS", ())
    try:
        _fb.RETIRED_LIVE_ARMS = {"_only-in-retired-live-arms": {}}
        _legacy.LEGACY_BOTS = ["_only-in-legacy-bots"]
        dead = S._dead_rows()
        assert "_only-in-retired-live-arms" in dead, (
            "the RETIRED_LIVE_ARMS term is not wired", sorted(dead))
        assert "_only-in-legacy-bots" in dead, (
            "the LEGACY_BOTS term is not wired", sorted(dead))
    finally:
        _fb.RETIRED_LIVE_ARMS = real_arms
        _legacy.LEGACY_BOTS = real_legacy
    # and the real registries are back
    assert "perps-funding-lighter-lighter" in S._dead_rows()


def test_a_row_with_no_subject_does_not_explode_the_check():
    """`subject` is OPTIONAL — several rows are about the fleet's machinery
    rather than a book. Reading it with `[...]` instead of `.get(..., ())`
    raises KeyError against every ad-hoc row the other tests here append, which
    is exactly how this guard would have shipped broken."""
    row = {"id": "_nosubj", "owner": "session", "what": "w" * 70,
           "why_open": "y" * 30, "closes_when": lambda: False}
    S.CARRIED.append(row)
    try:
        assert S.subject_status() == []
        assert S.main(["--check"]) == 0
    finally:
        S.CARRIED[:] = [i for i in S.CARRIED if i["id"] != "_nosubj"]


def test_a_dark_registry_reports_nothing_rather_than_flagging_everything():
    """Fail-OPEN, deliberately. A missed stale row costs a session a wrong
    first hour; failing CLOSED would send it to re-point books that are
    trading fine, which is worse and trains the reader to ignore the guard."""
    real = S._dead_rows
    S._dead_rows = lambda: set()
    try:
        row = {"id": "_probe2", "owner": "session", "what": "w" * 70,
               "why_open": "y" * 30, "closes_when": lambda: False,
               "subject": ("perps-funding-lighter-lighter",)}
        S.CARRIED.append(row)
        assert S.subject_status() == []
    finally:
        S._dead_rows = real
        S.CARRIED[:] = [i for i in S.CARRIED if i["id"] != "_probe2"]
