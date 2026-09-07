"""[(yn)] THE FIRST BOOK EVER TO PASS THE GO-LIVE GATE PASSED ON A MIXTURE.

On 2026-09-06 `golive-readiness` returned the fleet's first-ever
`ready: True` — 🎫 lighter-ticket-taker-lshadow, 6 of 6 bars, n=183 in-era,
+1.195%/trade, t=2.63. Split by lens, that sample is two books:

    long-breakoutup    n=138   +1.866%/trade   t=+3.35
    short-divergence   n= 46   -0.788%/trade   t=-1.31

and `divergence` is ALREADY VETOED by the book's own realised-lens rule
(I14/I15) — it publishes `lens_veto: ["dip", "divergence"]` every loop. So a
quarter of the graded sample comes from a lens the book will not trade again.

Here the mixture UNDERSTATES the forward book, which is exactly why this is a
report and not a warning: the number the go-live decision needs is the one for
the configuration the book will actually run. `class_split` established the
rule — *a number a decision depends on must be READABLE, not recomputable* —
and this is that rule on the veto screen instead of the instrument-class one.

THE THREE REFUSALS ARE THE SAFETY, and every one is asserted below: it moves
no sample, no era and no bar. A veto is evidence-reversible, so unlike a
retired sleeve (`drop_retired_sleeves`) nothing is dropped.
"""
import ast
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.autonomy

import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import golive_readiness as G                                   # noqa: E402

T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def row(pct, ab, i, tag, pair="BTC/USDC"):
    return (pct, ab, T0 + timedelta(hours=i), T0 + timedelta(hours=i - 1),
            {}, tag, pair)


def sample():
    """A winner lens and a loser lens, the taker's real shape."""
    live = [row(0.02, 2.0, i, "long-breakoutup") for i in range(10)]
    dead = [row(-0.01, -1.0, 20 + i, "short-divergence") for i in range(6)]
    return live + dead


# --------------------------------------------------------------------------
# the declaration
# --------------------------------------------------------------------------
def test_the_veto_set_is_read_from_the_books_own_publish():
    assert G.published_lens_veto({"lens_veto": ["dip", "divergence"]}) == \
        ("dip", "divergence")
    assert G.published_lens_veto({"caps": {"lens_veto": ["dip"]}}) == ("dip",)


@pytest.mark.parametrize("junk", [{}, None, {"lens_veto": None},
                                  {"lens_veto": "divergence"},
                                  {"lens_veto": [1, 2]},
                                  {"lens_veto": ["ok", 3]},
                                  {"lens_veto": {"a": 1}}])
def test_an_unpublished_or_malformed_veto_set_is_None_not_empty(junk):
    """I6: an unpublished screen may neither manufacture a finding nor erase
    one. `None` must never be read as 'nothing is vetoed'."""
    assert G.published_lens_veto(junk) is None


def test_an_explicitly_empty_veto_set_is_still_a_declaration():
    """A book that publishes `[]` HAS answered — nothing is vetoed — and the
    split then correctly returns None because there is nothing to split on."""
    assert G.published_lens_veto({"lens_veto": []}) == ()
    assert G.veto_split(sample(), ()) is None


# --------------------------------------------------------------------------
# the split
# --------------------------------------------------------------------------
def test_it_separates_the_live_lens_from_the_vetoed_one():
    vs = G.veto_split(sample(), ("divergence",))
    assert vs["still_tradeable"]["n"] == 10
    assert vs["now_vetoed"]["n"] == 6
    assert vs["still_tradeable"]["mean_pct"] > 0 > vs["now_vetoed"]["mean_pct"]
    assert "VETOED" in vs["why"] and "divergence" in vs["why"]


def test_a_book_with_no_graded_rows_from_a_vetoed_lens_says_nothing():
    """`why` is set only when the split is DECISION-RELEVANT — the
    class_split rule. A clean book must not add noise to the docket."""
    clean = [row(0.02, 2.0, i, "long-breakoutup") for i in range(6)]
    vs = G.veto_split(clean, ("divergence",))
    assert vs["now_vetoed"]["n"] == 0 and "why" not in vs


def test_an_unreadable_tag_returns_None_rather_than_a_guess():
    """Fail-SILENT, the direction `class_split` fixed: a wrong split riding on
    a go-live decision is worse than no split. Mutation: classify an
    unparseable tag as still-tradeable => this reddens."""
    bad = sample() + [row(0.01, 1.0, 40, "untagged")]
    assert G.veto_split(bad, ("divergence",)) is None
    assert G.veto_split([(0.01, 1.0, T0, T0, {}, None, "X")], ("d",)) is None
    assert G.veto_split(sample(), None) is None
    assert G.veto_split([], ("divergence",)) is None


def test_the_tag_accessor_is_overridable_like_its_sibling():
    rows = [(0.02, 2.0, T0, T0, {}, None, "BTC", "long-breakoutup")]
    vs = G.veto_split(rows, ("divergence",), tag_of=lambda r: r[7])
    assert vs["still_tradeable"]["n"] == 1


# --------------------------------------------------------------------------
# the three refusals — this is the safety
# --------------------------------------------------------------------------
def test_it_moves_no_bar():
    """Mutation: add `veto_split` to BAR_NAMES or to grade() => red."""
    assert "veto_split" not in G.BAR_NAMES
    rows = sample()
    s = G.stats([(r[0], r[1], r[2]) for r in rows])
    before = (G.grade(s), G.bar_map(s))
    s["veto_split"] = G.veto_split(rows, ("divergence",))
    assert (G.grade(s), G.bar_map(s)) == before


def test_it_moves_no_sample():
    """The rows handed in come back untouched — unlike `drop_retired_sleeves`,
    which drops. A veto lifts on the lens's own next evidence, so subtracting
    here would make the 30-day bar depend on a reversible switch."""
    rows = sample()
    n_before = len(rows)
    vs = G.veto_split(rows, ("divergence",))
    assert len(rows) == n_before
    assert vs["still_tradeable"]["n"] + vs["now_vetoed"]["n"] == n_before


def test_grade_never_sees_it():
    """AST: `grade` must not reference the field at all."""
    src = (ROOT / "scripts" / "golive_readiness.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "grade")
    assert "veto_split" not in (ast.get_source_segment(src, fn) or "")


def test_it_reaches_the_published_payload():
    """DRIVEN, not grepped. The first version of this asserted the STRING was
    present in `book_payload`'s source and a mutation that wrapped the publish
    in `if False:` sailed straight through it — a check that inspects the text
    rather than the behaviour, which is the (po) shape this repo names. Call
    the publisher and read the field back.

    Mutation: gate or delete the publish => red."""
    rows = sample()
    s = G.stats([(r[0], r[1], r[2]) for r in rows])
    s["veto_split"] = G.veto_split(rows, ("divergence",))
    out = G.book_payload(s)
    assert isinstance(out.get("veto_split"), dict), out.get("veto_split")
    assert out["veto_split"]["now_vetoed"]["n"] == 6
    # ...and a book with no split publishes no field at all, rather than a
    # null a consumer has to special-case.
    assert "veto_split" not in G.book_payload(
        G.stats([(r[0], r[1], r[2]) for r in rows]))


def test_it_reaches_the_docket_item():
    """The docket is the surface an operator acts on; `class_split` had to be
    added to BOTH for exactly this reason."""
    src = (ROOT / "scripts" / "golive_readiness.py").read_text()
    assert src.count('"veto_split": ((c.get("veto_split") or {})') == 1, \
        "the docket item no longer carries the split"
