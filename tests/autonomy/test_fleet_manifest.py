"""[(sm)] Nineteen designs, one way of judging them — until now.

**Operator: "we are tasked to create multiple strategy bots, who get
complimented and enhanced by instruments that let them fly to the ceiling if
they wish to... so they can achieve their designated different designs. We need
synergy."**

Measured 20-Aug: of nineteen living rows, **exactly one** published what it is
FOR. Every other book's design sat in 1,400 lines of `CLAUDE.md` — which no
organ can read, no grader can score against, and no instrument can use to tell
one book's "better" from another's. That is the missing synergy, precisely: the
fleet had nineteen different designs and one notion of good.

The `flies_when` field is the divergent half and it is the reason this is not
decoration. One fleet-wide rule cannot say that 🌾 carry flies by holding MORE,
🔮 georgia by becoming GRADEABLE, 🧮 Hull by simply SURVIVING to thirty closes,
and 🪁 the Mirror by its ghosts continuing to be wrong.
"""
import json
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import fleet_manifest as FM      # noqa: E402


def test_every_declared_book_says_three_different_things():
    """`design` (what it is for), `flies_when` (its ceiling) and `floor` (what
    it must never trade away). A ceiling printed without a floor beside it is
    how "go higher" becomes reckless."""
    for row, d in FM.DESIGN.items():
        assert d["emoji"] and d["name"], row
        for k in ("design", "flies_when", "floor"):
            assert len(d[k]) > 40, (row, k, d[k])
        assert d["design"] != d["flies_when"] != d["floor"], row


def test_no_two_books_share_a_ceiling():
    """The whole point. If two books' `flies_when` were the same sentence, the
    manifest would be one fleet-wide rule wearing nineteen names."""
    flies = [d["flies_when"] for d in FM.DESIGN.values()]
    assert len(set(flies)) == len(flies)
    designs = [d["design"] for d in FM.DESIGN.values()]
    assert len(set(designs)) == len(designs)


def test_the_books_own_publication_wins_over_this_table():
    """This file is a BRIDGE, not a second source of truth. As each book learns
    to declare itself (🧭 nav-cook's pattern) its entry here goes quiet on its
    own, and the two can never drift into disagreeing."""
    own = FM.design_for("nav-cook-lshadow",
                        {"thesis": {"cell": "residual band [45,60)"}})
    assert own["cell"] == "residual band [45,60)"
    assert own["source"] == "the book's own payload"
    fb = FM.design_for("perps-funding-carry-lshadow", {})
    assert fb["emoji"] == "🌾" and "does not publish" in fb["source"]


@pytest.mark.parametrize("junk", [{}, {"thesis": {}}, {"thesis": "words"},
                                  {"thesis": None}, {"thesis": []}])
def test_a_junk_thesis_falls_back_rather_than_erasing_the_design(junk):
    """Three-valued, like every other declaration in this fleet: a malformed
    payload must not leave a book with NO design — that would make an organ
    that reads designs go quiet exactly when a book's own publishing broke."""
    assert FM.design_for("perps-funding-carry-lshadow", junk)["emoji"] == "🌾"


def test_an_unknown_book_gets_nothing_rather_than_an_invented_purpose():
    assert FM.design_for("no-such-book") is None
    assert FM.uncovered(["no-such-book"]) == ["no-such-book"]


#: [(yj)] the committed living roster — see the module docstring's second half
SNAPSHOT = (pathlib.Path(__file__).resolve().parents[1]
            / "fixtures" / "living_rows.json")


def _feed_rows():
    """The live feed's rows if this environment has one, else None.

    Order: an explicit `PNL_JSON` path, then any `scratchpad/pnl.json` under
    this session's own tree — never another session's absolute path, which is
    what made this guard skip on every CI run for weeks."""
    import os
    cand = []
    if os.environ.get("PNL_JSON"):
        cand.append(pathlib.Path(os.environ["PNL_JSON"]))
    for base in (os.environ.get("CLAUDE_SCRATCHPAD"), "/tmp/claude-0"):
        if base:
            cand += sorted(pathlib.Path(base).glob("**/scratchpad/pnl.json"))
    for p in cand:
        try:
            rows = [b["bot"] for b in json.loads(p.read_text())["bots"]]
        except Exception:                                        # noqa: BLE001
            continue
        if len(rows) > 10:
            return rows
    return None


def test_every_LIVING_row_has_a_design():
    """The coverage claim, checked against a COMMITTED roster so it can never
    be skipped.

    [(yj)] It used to read a hard-coded absolute path inside ANOTHER session's
    scratchpad and `pytest.skip` when it was missing — which it always was, in
    CI and in every later session. So the test whose own docstring said a book
    with no design "must fail here rather than be silently skipped" was
    silently skipped, on every run, since it was written. It was covering two
    real gaps when this was found: 🔭 georgia v3 and 👩 mum's LIVE arm, i.e.
    a real-money book with no declared design. This repo's own rule: **empty
    output is not a negative result**, and a check that inspects nothing
    reports clean."""
    snap = json.loads(SNAPSHOT.read_text())
    rows = snap["rows"]
    assert len(rows) > 10, "the committed roster is too thin to prove coverage"
    missing = FM.uncovered(rows)
    assert not missing, f"living rows with no declared design: {missing}"


def test_the_committed_roster_has_not_fallen_behind_a_feed_we_can_read():
    """The snapshot's own freshness arm. Where a feed IS readable, a row on it
    that the snapshot lacks means a book was minted or retired and nobody
    refreshed the fixture — the way this guard would otherwise rot a second
    time, one book at a time."""
    rows = _feed_rows()
    if rows is None:
        pytest.skip("no live feed readable here — the committed arm above "
                    "still ran and is the guard")
    snap = set(json.loads(SNAPSHOT.read_text())["rows"])
    assert not (set(rows) - snap), (
        f"the feed carries rows the committed roster does not: "
        f"{sorted(set(rows) - snap)} — refresh tests/fixtures/living_rows.json")
    assert not FM.uncovered(rows), FM.uncovered(rows)


def test_it_decides_nothing():
    """A manifest that grew an actuator would be a new authority nobody
    reviewed. It is read by the ceiling renderer and the coverage guard, and
    that is all."""
    src = pathlib.Path(FM.__file__).read_text()
    for forbidden in ("write_levers", "get_lever", "market_open", "publish(",
                      "save_state"):
        assert forbidden not in src, forbidden


def test_the_ceiling_renderer_prints_design_ceiling_AND_floor():
    import scripts.ceiling as C
    txt = C.render_designs(
        {"perps-funding-carry-lshadow": {"verdict": "PROVEN",
                                         "binding": "SLOTS — 5.9 of 12"}},
        [{"bot": "perps-funding-carry-lshadow", "extra": {}}])
    for needle in ("is for", "flies when", "never", "measured", "🌾", "SLOTS"):
        assert needle in txt, (needle, txt)


def test_a_book_with_no_design_is_NAMED_by_the_renderer_not_skipped():
    import scripts.ceiling as C
    txt = C.render_designs({"mystery": {"verdict": "PROVEN"}},
                           [{"bot": "mystery", "extra": {}}])
    assert "NO DECLARED DESIGN" in txt
