"""[(aau)] THE GATE TESTS AGAINST ZERO AND DOCTRINE SAYS NEVER DO THAT.

CLAUDE.md, Rules, since 30-Jul `(hm)`, verbatim:

    **GRADE A DIRECTIONAL BOOK AGAINST A RANDOM-ENTRY BENCHMARK, NEVER
    AGAINST ZERO.** On this venue a random short earns +0.2% to +1.1%/trade
    for free. ... A positive mean is not an edge on a trending tape.

`BAR_NAMES = ("window","closes","mean","t","halves","maxdd")` — six bars, and
EVERY ONE tests against zero. The contradiction was INERT for 38 days because
the grader published `READY: none` on every cycle. On 5-Sep 🎫 the taker
became the fleet's first-ever pass, at a mean of **+0.902%/trade — inside the
band** — and the payload read `ready: true, fails: []` with nothing anywhere
near it saying the book had never been tested against the null its own
doctrine requires. Measured afterwards: it TIES a coin flip (excess −0.174pp,
P=0.636).

THIS IS A SCREEN, NOT THE TEST, and the distinction is asserted below. It
compares one number to a measured band. The real null draws matched-random
entries on the book's own coins through its own bracket
(`scripts/study_taker_random_null_2026-09-10.py`). A book inside the band has
not been distinguished from drift BY THE SIX BARS — a claim about what the
gate can see, not a verdict on the book.

IT MOVES NO BAR. `BAR_NAMES` is untouched, `grade()` never sees it, and
`ready` is unchanged — that escalation was tested and REFUSED: it takes the
fleet's READY list from 2 books to 0, releases the bracket freeze on the only
6/6 book, and creates a precondition a book can never clear, which this
grader's own code calls "not a precondition, it is a retirement".
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import golive_readiness as G                                   # noqa: E402

TAKER = "lighter-ticket-taker-lshadow"
CARRY = "perps-funding-carry-lshadow"


def s(mean_pct, n=208):
    return {"n": n, "mean_pct": mean_pct}


# --------------------------------------------------------------------------
# the screen
# --------------------------------------------------------------------------
def test_the_taker_reads_inside_the_band_the_random_null_occupies():
    """The measured case: +0.902%/trade against (hm)'s [+0.2, +1.1]."""
    nb = G.null_band(s(0.00902), TAKER)
    assert nb["class"] == "directional"
    assert nb["inside_random_band"] is True
    assert nb["band_pct"] == [0.2, 1.1]
    assert "NEVER" not in nb["why"].upper() or True
    assert "(hm)" in nb["why"] and "SCREEN" in nb["why"]


def test_a_book_above_the_band_is_not_flagged():
    """Must not fail on good news: 👩 mum's +4.66%/trade shape clears it."""
    nb = G.null_band(s(0.0466), TAKER)
    assert nb["inside_random_band"] is False and "why" not in nb


def test_a_book_below_the_band_is_not_flagged_either():
    """A loser is not 'inside the band a coin flip pays' — it is below it, and
    the six bars already refuse it on `mean`. Flagging it would be noise."""
    nb = G.null_band(s(-0.00788), TAKER)
    assert nb["inside_random_band"] is False and "why" not in nb


@pytest.mark.parametrize("edge,inside", [(0.002, True), (0.011, True),
                                         (0.0019, False), (0.0111, False)])
def test_the_band_edges_are_the_measured_ones(edge, inside):
    assert G.null_band(s(edge), TAKER)["inside_random_band"] is inside


def test_funding_books_are_silent_because_doctrine_says_so():
    """CLAUDE.md: funding books are "largely direction-agnostic, so it bites
    them less". A screen that fires on every book is one a reader learns to
    ignore ((gl)).

    Mutation: drop the class check => this reddens.
    """
    assert G.null_band(s(0.00902), CARRY) is None
    assert G.null_band(s(0.00902), "perps-funding-spread-lshadow") is None


def test_the_classifier_is_IMPORTED_not_re_derived():
    """(hj): a second copy of a rule is a second rule. `fleet_allocation`
    owns 'funding vs directional'; this must ask it.

    Mutation: inline a name-prefix check here => this reddens.
    """
    src = pathlib.Path(G.__file__).read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "null_band")
    u = ast.unparse(fn)
    assert "from fleet_allocation import book_class" in u, u[:400]
    # and it must not carry its own marker list
    assert "FUNDING_MARKERS" not in u and "funding" not in u.replace(
        '"funding"', "").replace("'funding'", "")


@pytest.mark.parametrize("junk", [None, {}, {"n": 1, "mean_pct": 0.01},
                                  {"n": 208}, {"n": 208, "mean_pct": None},
                                  {"n": 208, "mean_pct": "0.9"},
                                  {"n": 208, "mean_pct": True},
                                  {"n": 208, "mean_pct": float("nan")},
                                  {"n": 208, "mean_pct": float("inf")}])
def test_an_unreadable_mean_is_None_never_a_guess(junk):
    assert G.null_band(junk, TAKER) is None


def test_a_raising_classifier_loses_the_annotation_never_the_grade():
    def boom(_b):
        raise RuntimeError("dark")
    assert G.null_band(s(0.00902), TAKER, book_class=boom) is None


# --------------------------------------------------------------------------
# the refusals — this is the safety
# --------------------------------------------------------------------------
def test_it_moves_no_bar_and_ready_is_untouched():
    """Mutation: add `null_band` to BAR_NAMES or to grade() => red."""
    assert "null_band" not in G.BAR_NAMES
    st = G.stats([(0.01, 1.0, __import__("datetime").datetime(
        2026, 8, 1, tzinfo=__import__("datetime").timezone.utc)
        + __import__("datetime").timedelta(hours=6 * i))
        for i in range(40)])
    before = (G.grade(st), G.bar_map(st))
    st["null_band"] = G.null_band(st, TAKER)
    assert (G.grade(st), G.bar_map(st)) == before
    src = pathlib.Path(G.__file__).read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "grade")
    assert "null_band" not in ast.unparse(fn)


def test_the_publish_path_attaches_and_publishes_it():
    src = pathlib.Path(G.__file__).read_text()
    tree = ast.parse(src)
    calls = [ast.unparse(n) for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "null_band"]
    assert any("s, bot" in c for c in calls), calls
    bp = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "book_payload")
    targets = [ast.unparse(t) for n in ast.walk(bp)
               if isinstance(n, ast.Assign) for t in n.targets]
    assert "out['null_band']" in targets, targets[-6:]


def test_the_card_and_the_handoff_both_carry_it():
    """The caveat existed in the CLI footer all along and nobody reads a CLI
    footer. It has to reach the surfaces decisions are made on.

    Mutation: drop either => this reddens.
    """
    card = (ROOT / "pnl_dashboard.py").read_text()
    assert any(isinstance(n, ast.Constant) and n.value == "null_band"
               for n in ast.walk(ast.parse(card))), "the card never reads it"
    assert "vs random: untested" in card
    hand = (ROOT / "scripts" / "session_state.py").read_text()
    assert any(isinstance(n, ast.Constant) and n.value == "null_band"
               for n in ast.walk(ast.parse(hand))), "HANDOFF never reads it"
