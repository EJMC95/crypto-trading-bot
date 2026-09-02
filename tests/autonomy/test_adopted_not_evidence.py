"""[(xq)] An ADOPTED leg is not the book's evidence.

`(xa)` adopts a position the book finds on the venue with no bracket of its
own, starting the clock at the takeover instant because the true open is
unknown to the record. That makes the row's entry basis and holding period
fictions of that instant: the P&L it books is whatever happened before this
book ever saw the position.

`(xa)` kept it out of the BRAIN's per-tag bucket and nothing kept it out of the
book-level mean, t, halves or drawdown — the sample the go-live gate reads.

Eamon, 2-Sep: *"It was a manual trade please disregard it ... drop it from her
trades"* — 👩 mum adopted a 1000PEPE leg he opened by hand, on a REAL-MONEY
book. Same shape as a container that loses its meta and re-adopts its own
position at the next boot.
"""
import os
import sys

import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import golive_readiness as gr  # noqa: E402


def _src(path):
    """Read a source file. A helper because CodeQL is right that a bare
    `open(...).read()` leaks the handle, and three of them in one file is a
    habit rather than a slip."""
    with open(path) as fh:
        return fh.read()


ADOPTED = [
    {"enter_tag": "long-adopted"},                 # fetch_paper_trades shape
    {"reason": "long-adopted_daily_loss"},         # raw /trades.json shape
    {"tag": "long-adopted"},                       # raw, tag column stamped
    {"reason": "short-adopted_stop_loss"},         # the short side too
]
KEPT = [
    {"enter_tag": "long-oversold-rebound"},
    {"reason": "long-oversold-rebound_roi"},
    {"enter_tag": "long-my-adopted"},              # 3 segments: not the tag
    {"reason": "long_stop_loss"},
    {"enter_tag": "long-funding"},
]


@pytest.mark.parametrize("row", ADOPTED)
def test_an_adopted_close_is_recognised_in_either_ledger_shape(row):
    assert gr.is_adopted_close(row) is True


@pytest.mark.parametrize("row", KEPT)
def test_a_real_close_is_never_called_adopted(row):
    assert gr.is_adopted_close(row) is False


@pytest.mark.parametrize("row", [None, {}, {"enter_tag": None}, {"tag": 7},
                                {"reason": ""}, {"enter_tag": ["long-adopted"]}])
def test_unparseable_stays_in_the_sample_and_never_raises(row):
    """`is_phantom_close`'s contract verbatim: a filter over a graded sample
    must never shrink it beyond its exact signature."""
    assert gr.is_adopted_close(row or {}) is False


def test_the_tag_matches_what_the_bot_actually_stamps():
    """Driven against the real publisher, never a hand-written fixture: the
    live host sets `m["tag"] = "adopted"` and the ledger key is built from it
    through `split_reason`, which is the owner of that split."""
    from bot_pnl_store import split_reason
    direction, exit_reason = split_reason("long-adopted_daily_loss")
    assert direction == "long-" + gr.ADOPTED_TAG
    assert exit_reason == "daily_loss"
    assert gr.is_adopted_close({"enter_tag": direction}) is True


def test_the_live_host_still_stamps_the_tag_this_filter_keys_on():
    """A drift pin. If `(xa)`'s adoption tag is ever renamed, this filter goes
    silently inert — the registered-but-inert shape (I18)."""
    src = _src(os.path.join(_ROOT, "lighter_avo_live_bot.py"))
    assert 'm["tag"] = m.get("tag") or "%s"' % gr.ADOPTED_TAG in src


@pytest.mark.parametrize("mod,attr", [
    ("edge_audit", None), ("ceiling", None), ("fleet_allocation", None)])
def test_every_grader_consumes_the_filter(mod, attr):
    """Four consumers import the ONE owner (hj). A grader that filters phantoms
    and not adopted legs grades a sample the gate refuses."""
    path = os.path.join(_ROOT, "scripts", mod + ".py")
    if not os.path.exists(path):
        path = os.path.join(_ROOT, mod + ".py")
    src = _src(path)
    assert "is_phantom_close" in src, mod
    assert "is_adopted_close" in src, (
        mod + " filters phantom closes but not adopted ones")


def test_golive_readiness_filters_its_own_rows():
    src = _src(os.path.join(_ROOT, "scripts", "golive_readiness.py"))
    assert "if not is_adopted_close(r)" in src


def test_the_allocation_organ_counts_the_two_exclusions_separately():
    """[(xq)] `n_phantom` and `n_adopted` are different reasons — a halt event
    wearing a close's shape, versus a leg the book never opened. Folding both
    into one published counter makes the number mean two things at once, which
    is how a reader stops being able to act on it (I8/I18)."""
    src = _src(os.path.join(_ROOT, "fleet_allocation.py"))
    assert 'payload["n_adopted"] = n_adopted' in src
    assert "n_phantom = sum(1 for t in trades if is_phantom_close(t))" in src
    # and a dark filter blanks BOTH, never leaves one reading 0 (I4/(vd)):
    # a zero that means "unknown" is the byte-identical trap.
    assert "n_adopted = None" in src
