"""[(lj)] I15 is expectancy-only in BOTH directions — including back-a-winner.

I15 reads, in full:

    WIN RATE IS NOT EXPECTANCY — AND CHECK THE ACTUATORS, NOT JUST THE REPORTS
    A rule that requires a LOW hit rate before it will act on a loser cannot
    see a loser that wins often, and one that requires a HIGH hit rate before
    it will back a winner **cannot see the carry shape — lose often, win big**.
    ... The fix is expectancy-only **in both directions**; win rate stays
    REPORTED, demoted rather than deleted.
      ENFORCED BY: lighter_ticket_taker.py::lens_loses, ...::LEGACY_HIT_GATE

`(ij)` swept the VETO direction — `lens_loses` dropped its `hit < 0.5`
conjunct. The BACK-A-WINNER direction lives in `lighter_scout_tuner`, and both
of its expand paths kept requiring `hit >= 0.5`:

    positive = floor_met and avg > 0 and hit >= 0.5          # taker-bar walk
    elif _avg is not None and _avg > 0 and (_hit or 0) >= 0.5:   # scout diet

MEASURED, from the fleet's own recorded `brain-lens-forward` table (reproduced
in `lens_loses`'s docstring): **`breakout` reads eavg4h +0.026% at ehit4h
0.480** — positive expectancy, sub-50% hit — and was therefore excluded from
the winner walk entirely. 🌾 carry, the fleet's best-evidenced book, wins 38.8%.
That is the shape the bar cannot see.

THIS IS NOT A WIDENING BOUGHT WITHOUT EVIDENCE (I19). `lens_wins` only decides
whether a lens ENTERS the tuner's walk; every notch inside that walk must still
improve BOTH halves by `MARGIN_HALF` through the real replay, and the brain veto
stays senior ahead of both. What was removed is a filter with no evidentiary
basis, not the price. The tests below pin that the price is still charged.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import lighter_ticket_taker as TT        # noqa: E402
import lighter_scout_tuner as ST         # noqa: E402

TUNER = pathlib.Path(ST.__file__)


# ---------------------------------------------------------------------------
# the authority
# ---------------------------------------------------------------------------

def test_a_carry_shaped_winner_is_backed():
    """Positive expectancy, sub-50% hit — the measured `breakout` case."""
    assert TT.lens_wins(+0.026, 0.480) is True
    assert TT.lens_wins(+2.0, 0.388) is True      # 🌾 carry's own hit rate


def test_a_loser_that_wins_often_is_not_backed():
    """The mirror non-sequitur: a high hit rate must not buy a widening."""
    assert TT.lens_wins(-0.027, 0.526) is False
    assert TT.lens_wins(-0.155, 0.99) is False


def test_zero_expectancy_is_not_a_winner():
    assert TT.lens_wins(0.0, 0.9) is False


def test_it_fails_CLOSED_on_a_missing_grade():
    """Opposite fail-safe to `lens_loses`, and deliberately so: this
    AUTHORISES a widening, so no grade must mean no widening."""
    assert TT.lens_wins(None, 0.9) is False
    assert TT.lens_wins(None, None) is False


def test_the_two_directions_are_consistent():
    """A grade may not be both a winner and a loser, and a positive-expectancy
    lens must never be vetoed by the twin."""
    for avg in (-2.0, -0.1, -0.001, 0.0, 0.001, 0.1, 2.0):
        for hit in (0.0, 0.3, 0.5, 0.7, 1.0):
            assert not (TT.lens_wins(avg, hit) and TT.lens_loses(avg, hit)), \
                (avg, hit)


def test_the_legacy_switch_restores_both_directions_together(monkeypatch):
    """One env var must put BOTH halves back without a deploy — otherwise a
    revert leaves the fleet in a state neither ruling describes."""
    monkeypatch.setattr(TT, "LEGACY_HIT_GATE", True)
    assert TT.lens_wins(+0.026, 0.480) is False   # blocked again
    assert TT.lens_wins(+0.026, 0.510) is True
    assert TT.lens_loses(-0.027, 0.526) is False  # unvetoable again
    monkeypatch.setattr(TT, "LEGACY_HIT_GATE", False)
    assert TT.lens_wins(+0.026, 0.480) is True
    assert TT.lens_loses(-0.027, 0.526) is True


# ---------------------------------------------------------------------------
# the consumers — one owner, no second copy
# ---------------------------------------------------------------------------

def _hit_comparisons_in(path):
    """Every `hit >= <number>` / `hit > <number>` comparison in the module.

    A bare hit-rate threshold is the thing I15 bans in an actuator. Finding one
    by AST rather than by substring, because `hit` also appears in log strings
    and in `ehit4h` field names.
    """
    tree = ast.parse(path.read_text())
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        src = ast.unparse(node)
        if not any(op in src for op in (">=", ">", "<=", "<")):
            continue
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        if not (names & {"hit", "_hit"}):
            continue
        out.append((node.lineno, src))
    return out


def test_the_tuner_has_no_bare_hit_rate_gate_left():
    """The regression: re-adding `hit >= 0.5` anywhere in the tuner restores
    exactly the bar I15 removed."""
    bad = _hit_comparisons_in(TUNER)
    assert not bad, (
        "a bare hit-rate threshold is back in the scout tuner — I15 bans win "
        f"rate as a BAR in an actuator, in both directions: {bad}")


def test_the_scanner_is_not_vacuous():
    """If the AST matcher stops matching, the test above passes over a tuner
    full of hit gates. Prove it on a file that deliberately has one."""
    found = _hit_comparisons_in(pathlib.Path(TT.__file__))
    assert found, (
        "the hit-comparison matcher found nothing even in lighter_ticket_taker, "
        "which keeps the legacy conjunction behind LEGACY_HIT_GATE — it is blind")


def test_the_tuner_uses_the_defining_modules_authority():
    """One owner. A second copy of the rule is a second rule — the (hj) class,
    which this fleet has already paid for with the go-live gate."""
    src = TUNER.read_text()
    assert "tt.lens_wins(" in src, "the tuner must call the shared authority"
    tree = ast.parse(src)
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "lens_wins" not in defined, (
        "the tuner has its own copy of lens_wins — it must import the one in "
        "lighter_ticket_taker so the two directions cannot drift apart")


# ---------------------------------------------------------------------------
# I19: the expectancy price is still charged
# ---------------------------------------------------------------------------

def test_entering_the_walk_is_not_the_same_as_widening():
    """`lens_wins` gates ENTRY to the walk. Every notch inside it must still
    improve BOTH halves through the real replay, and the brain veto stays
    senior — otherwise this change would be a widening bought without the
    evidence to pay for it (I19)."""
    src = TUNER.read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "desired_taker_bars")
    # NOT `"MARGIN_HALF" in body` — that is a presence check, and it passed
    # against a mutation that removed the margin from the comparison while the
    # name survived elsewhere in the function. Assert the RELATIONSHIP: every
    # replay comparison in the earned walk must carry the margin.
    body = ast.unparse(fn)
    replay_cmps = [ast.unparse(n) for n in ast.walk(fn)
                   if isinstance(n, ast.Compare)
                   and "replay_with" in ast.unparse(n)
                   and any(isinstance(o, (ast.GtE, ast.Gt))
                           for o in n.ops)]
    assert replay_cmps, "the walk no longer replays anything"
    assert all("MARGIN_HALF" in c for c in replay_cmps), (
        "a replay comparison in the earned walk has lost its improve-by-margin "
        f"bar — the widening no longer pays for itself (I19): {replay_cmps}")
    # the brain veto must still short-circuit ahead of everything
    assert "vetoed_lenses" in body and "continue" in body


def test_a_brain_vetoed_lens_is_never_widened_however_positive():
    """Brain veto senior, unchanged by this edit."""
    src = ast.unparse(ast.parse(TUNER.read_text()))
    i = src.index("def desired_taker_bars")
    seg = src[i:i + 3000]
    assert "if lens in veto" in seg and seg.index("if lens in veto") < seg.index("lens_wins")
