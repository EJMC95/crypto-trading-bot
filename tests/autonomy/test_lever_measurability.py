"""[(sg)] The never-recorded class, closed fleet-wide rather than one at a time.

**Operator, 2026-08-20: "Fix this never recorded issue across the fleet, I am
so tired of going over the same trivial problem."**

One problem in four costumes, all four found in a single session — a lever whose
governing quantity is never recorded; a floor standing in for a cost nobody
measured; an actuator steering a lens its own gate cannot fill; a paired bar
comparing two different entry policies. **The thing that decides is not
measuring the thing it decides about.** Fixing instances is the circle.

MEASURED the day this shipped, on the real registry:
    64 registered levers
    19 with a QUANTITIES spec        <- can be profiled
    30 with none, and not declared   <- the backlog, ratcheted
    15 steering a RETIRED book       <- worse than unmeasurable: pure noise

Both arms are RATCHETS. A guard that reddens the build on a pre-existing
backlog gets a blanket exemption within a day and then guards nothing ((mz) is
the precedent, on the venue-purity backtest arm). A ratchet is the version that
survives contact with the backlog: the pile may only shrink, and a NEW instance
fails on the push that adds it.
"""
import pytest

pytestmark = pytest.mark.autonomy

import fleet_tuning as FT                            # noqa: E402
import scripts.audit_lever_measurability as M       # noqa: E402


def test_the_guard_is_green_on_the_real_registry():
    ok, lines, counts = M.check()
    assert ok, lines
    assert counts["MEASURABLE"] + counts["UNMEASURABLE"] \
        + counts["UNMEASURABLE-OK"] + counts["DEAD"] + counts["DEAD-OK"] \
        == len(FT.LEVERS), counts


def test_the_ratchet_is_not_slack():
    """A ratchet set above the real count is a ratchet that permits growth —
    the one way this guard could be green and useless."""
    _ok, _lines, counts = M.check()
    assert M.RATCHET["unmeasurable"] == counts["UNMEASURABLE"], (
        f"ratchet {M.RATCHET['unmeasurable']} vs actual "
        f"{counts['UNMEASURABLE']} — tighten it")
    assert M.RATCHET["dead"] == counts["DEAD"], (
        f"ratchet {M.RATCHET['dead']} vs actual {counts['DEAD']}")


def test_a_new_unmeasurable_lever_fails_the_build():
    """The whole point: the backlog is allowed, growing it is not."""
    lv = dict(FT.LEVERS)
    lv["carry.brand_new_knob"] = {"kind": "float", "lo": 0, "hi": 1,
                                  "lane": "lighter-books", "env_default": 0.5}
    ok, lines, _ = M.check(lv)
    assert not ok and any("UNMEASURABLE levers" in x for x in lines), lines


def test_a_new_lever_on_a_RETIRED_book_fails_too():
    lv = dict(FT.LEVERS)
    lv["trend.brand_new_knob"] = {"kind": "int", "lo": 1, "hi": 9,
                                  "lane": "lighter-books", "env_default": 3}
    ok, lines, _ = M.check(lv)
    assert not ok and any("DEAD levers" in x for x in lines), lines


def test_every_dead_lever_names_the_env_that_would_revive_its_book():
    """A declaration is a decision, not a snooze. These are KEPT rather than
    deleted only because a single env var brings each book back the same day —
    so each row must name that env, or the reason for keeping it is fiction."""
    assert M.DEAD_LEVER_OK, "the dead-lever declaration is empty"
    for lever, why in M.DEAD_LEVER_OK.items():
        assert "RETIRED_OVERRIDE" in why, (lever, why)
        assert lever in FT.LEVERS, f"{lever} is declared but not registered"


def test_the_declared_dead_levers_really_are_dead():
    """A declaration must not be able to hide a LIVING lever from the
    measurability arm — that would turn the exception list into a bypass."""
    retired = M.retired_rows()
    for lever in M.DEAD_LEVER_OK:
        books = M.LEVER_BOOK[lever.split(".", 1)[0]]
        assert books and all(b in retired for b in books), (
            f"{lever} is declared DEAD but its book is not in RETIRED_ROWS — "
            "this declaration is hiding a live lever from the ratchet")


def test_an_UNMAPPED_prefix_fails_check_rather_than_being_skipped():
    """Caught by a SURVIVING mutation: `test_every_registered_prefix_is_
    classified` proves the map covers TODAY's prefixes and says nothing about
    what `check()` does when one is missing. Treating an unmapped lever as
    "no book, therefore alive and unmeasured" would quietly admit a whole new
    book's levers into the backlog under the ratchet."""
    ok, lines, counts = M.check({"brandnewbook.knob": {"lane": "x"}},
                                {}, {"some-retired-row"},
                                {"unmeasurable": 99, "dead": 99})
    assert not ok, lines
    assert counts["UNMAPPED"] == 1, counts
    assert any("LEVER_BOOK" in x for x in lines), lines


def test_every_registered_prefix_is_classified():
    """A new book's levers cannot arrive unclassified and be silently skipped
    — the guard fails on an unmapped prefix rather than ignoring it."""
    unmapped = sorted({k.split(".", 1)[0] for k in FT.LEVERS} - set(M.LEVER_BOOK))
    assert not unmapped, unmapped


def test_it_fails_CLOSED_when_the_retired_roster_cannot_be_read():
    """Reporting every dead lever as ALIVE is the one wrong answer that is
    wrong in the dangerous direction — it would silently un-declare fifteen."""
    ok, lines, _ = M.check(retired=set())
    assert not ok and "RETIRED_ROWS parsed EMPTY" in lines[0], lines


def test_the_roster_parse_is_not_vacuous():
    """The (po) rule: empty output is not a negative result until the check has
    been seen to produce a positive one."""
    rows = M.retired_rows()
    assert len(rows) > 10, rows
    assert "band-barnes-lshadow" in rows
    assert "perps-funding-carry-lshadow" not in rows, "a LIVING book read retired"


def test_the_spec_table_is_the_profilers_own():
    """Imported, never re-listed: two copies would let this guard and
    `audit_lever_authority` disagree about which levers are measurable, which
    is the second-copy-of-a-rule trap on a guard about measurement."""
    import scripts.audit_lever_authority as A
    assert M._quantities() == dict(A.QUANTITIES)
