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


def test_every_LIVING_row_on_the_feed_has_a_design():
    """The coverage claim, checked against the feed rather than asserted. A
    book minted tomorrow with no design is the gap this closes, so it must
    fail here rather than be silently skipped."""
    feed = pathlib.Path(
        "/tmp/claude-0/-home-user-crypto-trading-bot/"
        "88638ad8-aca5-5b55-b800-4fdac52e033d/scratchpad/pnl.json")
    if not feed.exists():
        pytest.skip("no captured feed in this environment")
    rows = [b["bot"] for b in json.loads(feed.read_text())["bots"]]
    assert len(rows) > 10, "the feed capture is too thin to prove coverage"
    missing = FM.uncovered(rows)
    assert not missing, f"living rows with no declared design: {missing}"


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
