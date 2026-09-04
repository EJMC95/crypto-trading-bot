"""[(yd)] A LIVE BOOK CAN STOP TRADING AND NOTHING PAGES.

Eamon asked "bots aren't trading" THREE TIMES on 4-Sep. Both real-money books
had been idle 28h and 41h; every organ read healthy, `n_stale: 0`, the watchdog
`problems: []`. I1 gives the fleet a hard page on a dead WRITER — but a book
whose writer is alive while the BOOK has stopped publishes `open: 0` forever
and is byte-identical to a book that is merely quiet. Publisher liveness was
covered; BOOK liveness was not.

WHAT IS PINNED, in the order it matters:
  1. the bar is DERIVED from each book's own rate, never typed as hours — the
     same constant must alarm a 10/day book in ~11h and leave a 1.35/day book
     alone at 41h, which one hour count cannot do;
  2. the four exclusions, each a condition that LOOKS like a drought and is
     someone else's class already: stale row (I1), halted, at cap (I7), and no
     measured rate (I8);
  3. scope is the row's OWN `extra.venue`, so a shadow book never pages and a
     roster cannot rot (this file's history records that happening 4x);
  4. the trailing-rate trap: a deepening drought must not become HARDER to
     page as it lengthens;
  5. it fires on the REAL payload shape, driven through the shipped function.
"""
import copy

import fleet_immune as fi


def _live(bot="freqtrade-mum-lighter", idle_h=28.1, rate7=10.14, rate_life=7.35,
          open_n=0, cap=12, status="online", shut=None, age=30.0, venue="lighter_live"):
    """A row shaped like the LIVE payload the publisher actually emits."""
    return {
        "bot": bot, "status": status, "open_trades": open_n, "age_sec": age,
        "extra": {
            "venue": venue, "max_open": cap,
            "scan": {"idle_open_h": idle_h},
            "progression": {"close_rate_day_7d": rate7,
                            "close_rate_day_life": rate_life},
            "entry_vetoes": {"shut_now": shut},
        },
    }


def _hits(rows, **kw):
    return {d["organ"] for d in fi.entry_drought_sickness(rows, **kw)}


# --- 1 · the bar is the book's own rate, not an hour count -----------------

def test_a_fast_book_and_a_slow_book_get_different_bars_from_one_constant():
    """THE WHOLE DESIGN. 👩 mum at ~10 closes/day and 🙏 avo at ~1.35 were BOTH
    idle on 4-Sep — 28h and 41h. Only mum's silence is surprising. A typed
    hour count cannot separate them: anything that catches mum at 28h cries
    wolf on avo, and anything that spares avo at 41h sleeps through mum."""
    mum = _live("freqtrade-mum-lighter", idle_h=28.1, rate7=10.14, rate_life=7.35)
    avo = _live("freqtrade-avo-maria-lighter", idle_h=41.2, rate7=1.0,
                rate_life=1.346, open_n=1, cap=5)
    hits = _hits([mum, avo])
    assert "freqtrade-mum-lighter" in hits, "mum's 28h against a ~11h bar must page"
    assert "freqtrade-avo-maria-lighter" not in hits, (
        "avo's 41h is INSIDE her own ~82h cadence — paging her is the cry-wolf "
        "that trains the operator to ignore the real one")


def test_the_same_idle_hours_page_or_not_depending_only_on_the_books_rate():
    """Hold idle constant, move only the rate: the verdict must flip."""
    fast = _live("a", idle_h=30.0, rate7=10.0, rate_life=10.0)
    slow = _live("b", idle_h=30.0, rate7=0.5, rate_life=0.5)
    hits = _hits([fast, slow])
    assert hits == {"a"}, hits


# --- 2 · the four exclusions ----------------------------------------------

def test_a_stale_row_is_not_a_drought():
    """I1: establish that something still WRITES the row before interpreting
    what it says. A dead writer is the watchdog's class, not this one."""
    r = _live(age=fi.STALE_ROW_S + 600)
    assert _hits([r]) == set()


def test_a_halted_book_is_not_a_drought():
    """The halt IS the reason; `flatten_stuck_sickness` owns the halt that
    will not clear. Both spellings must suppress."""
    assert _hits([_live(status="halted")]) == set()
    assert _hits([_live(shut="daily_loss")]) == set()


def test_a_book_at_its_cap_is_full_not_starved():
    """I7: a trigger a book satisfies STRUCTURALLY is not a measurement.
    🧮 hull sat 10/10 with no entry for 19 days and was working correctly."""
    assert _hits([_live(open_n=12, cap=12)]) == set()
    assert _hits([_live(open_n=11, cap=12)]) != set(), (
        "below cap it must still page — the cap test must not swallow the book")


def test_no_measured_rate_degrades_to_silence_never_to_an_alarm():
    """I8: unknown degrades honestly. A book with no demonstrated cadence has
    no expectation to violate, and a fabricated one lands on a phone.

    IDLE IS DELIBERATELY ENORMOUS (500h). A mutation that fabricates a missing
    rate as 1.0/day SURVIVED the first version of this test, because at the
    fixture's 28h idle a fabricated rate puts the bar at ~110h and the row
    stayed silent for the WRONG REASON. The fixture must be far enough past
    any plausible fabricated bar that only the real skip can keep it quiet."""
    for r7, rl in ((None, None), (0.0, 0.0), ("junk", None), (float("nan"), None)):
        r = _live(idle_h=500.0, rate7=r7, rate_life=rl)
        assert _hits([r]) == set(), (r7, rl)


# --- 3 · scope is self-declared, so no roster can rot ----------------------

def test_only_a_book_that_declares_itself_live_is_checked():
    """A list-keyed roster rots on every slot swap — the repo's own audit-scope
    rule has named a retired bot FOUR times. The row declares its own venue."""
    for venue in ("lighter_shadow", "lighter", None, ""):
        r = _live(venue=venue)
        assert _hits([r]) == set(), venue
    assert _hits([_live(venue="lighter_live")]) != set()


def test_an_exemption_is_declared_and_the_default_is_empty():
    """The BORN_DARK_OK idiom: empty today, and that is the point."""
    assert fi.DROUGHT_OK == {}
    assert _hits([_live()], ok={"freqtrade-mum-lighter": "why"}) == set()


# --- 4 · the trailing-rate trap -------------------------------------------

def test_a_deepening_drought_does_not_become_harder_to_page():
    """`close_rate_day_7d` FALLS as a drought lengthens. If the bar were built
    from the trailing rate alone, the alarm would fade out exactly as the
    problem got worse. The DEMONSTRATED rate (the max) is what must govern."""
    fresh = _live(idle_h=28.0, rate7=10.0, rate_life=7.0)
    # same book a week later: trailing rate has collapsed toward zero
    decayed = _live(idle_h=200.0, rate7=0.05, rate_life=7.0)
    assert _hits([fresh]) != set()
    assert _hits([decayed]) != set(), (
        "a longer silence on the same book must still page — the trailing "
        "rate collapsing must not raise the bar out of reach")


# --- 5 · it fires on the shipped payload shape, and is wired --------------

def test_it_is_wired_into_the_sick_list():
    """A detector nobody calls is the registered-but-inert failure (I18).
    On the AST: a call, not a substring."""
    import ast
    import pathlib
    tree = ast.parse(pathlib.Path(fi.__file__).read_text())
    called = {ast.unparse(n.func) for n in ast.walk(tree)
              if isinstance(n, ast.Call)}
    assert "entry_drought_sickness" in called, (
        "the detector exists and run_once never calls it")


def test_the_detail_names_something_the_operator_can_act_on():
    """I8: a guard whose output is an instruction must identify the object the
    operator will open, and rule out what it is NOT."""
    out = fi.entry_drought_sickness([_live()])
    d = out[0]["detail"]
    assert out[0]["organ"] == "freqtrade-mum-lighter"
    for token in ("28.1h", "10.14", "NOT halted", "0/12"):
        assert token in d, (token, d)


def test_it_never_raises_on_junk():
    """A detector must never break the organ loop."""
    junk = [None, {}, {"bot": "x"}, {"bot": "y", "extra": "notadict"},
            {"bot": "z", "extra": {"venue": "lighter_live"}},
            {"bot": "w", "extra": {"venue": "lighter_live", "scan": "bad",
                                   "progression": {"close_rate_day_7d": 5}}}]
    assert isinstance(fi.entry_drought_sickness(junk), list)
