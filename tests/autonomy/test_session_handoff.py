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
