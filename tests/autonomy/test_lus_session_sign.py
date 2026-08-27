"""The LUS session study's SIDE LABELS must mean what they say.

[27-Aug] WHY THIS TEST EXISTS. `scripts/study_lus_session_2026-08-27.py` shipped
with its two side labels SWAPPED by a double negation:

    for side, sgn in (("fade", -1.0), ("follow", +1.0)):
        r = [sgn * (-1.0 if dr > 0 else 1.0) * fw for ...]

`(-1.0 if dr > 0 else 1.0)` is already `-sign(drift)` — the fade position — so
multiplying by `sgn = -1.0` on the row labelled "fade" produced `+sign(drift)*fwd`,
which is CONTINUATION. The published headline ("8h fade, +0.352%/trade, t=+2.78")
was therefore the continuation number wearing the fade's name, and the rule as
literally specified was a significant LOSER of exactly that size.

What makes it worth a permanent guard rather than a one-line fix is HOW it
survived. The module carried an explicit symmetry defence in its own docstring —
*"BOTH DIRECTIONS. Fade AND follow are reported. A rule that must be flipped to
win was not a finding in the first place"* — and that defence was useless,
because both directions WERE computed and both were printed under the wrong
name. Every derived statistic (n, pooled t, by-coin t, concentration, the null)
reconciled to the digit, so nothing downstream could notice.

THE TRANSFERABLE RULE, and it belongs beside I3: **printing both directions is
not a control unless the sign convention is itself asserted against a
hand-computed case.** A symmetric sweep is symmetric about the wrong axis just
as happily as the right one.

So these tests do not check that a `sgn` variable is absent — a name check stays
green against any hand-rolled re-inversion ((hj): pin by identity/behaviour, not
by asserting a constant is missing). They drive the real function with numbers
whose correct answer is known by inspection.
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_PATH = ROOT / "scripts" / "study_lus_session_2026-08-27.py"


def _mod():
    spec = importlib.util.spec_from_file_location("lus_session", _PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def lus():
    return _mod()


# ------------------------------------------------------------------ the sign
@pytest.mark.parametrize("drift,fwd,fade,follow", [
    # Drift UP overnight, price keeps rising after the open.
    #   fade   = short a riser that kept rising  -> LOSS
    #   follow = long  a riser that kept rising  -> GAIN
    (+0.01, +0.01, -0.01, +0.01),
    # Drift UP overnight, price falls back after the open.
    #   fade   = short a riser that reverted     -> GAIN
    (+0.01, -0.01, +0.01, -0.01),
    # Drift DOWN overnight, price keeps falling.
    #   fade   = long  a faller that kept falling -> LOSS
    #   follow = SHORT a faller that kept falling -> GAIN
    (-0.01, -0.01, -0.01, +0.01),
    # Drift DOWN overnight, price rebounds.
    #   fade   = long  a faller that rebounded    -> GAIN
    #   follow = SHORT a faller that rebounded    -> LOSS
    (-0.01, +0.01, +0.01, -0.01),
])
def test_side_labels_mean_what_they_say(lus, drift, fwd, fade, follow):
    """Hand-computed truth table. This is the arm that reddens on the swap."""
    assert lus.trade_return(drift, fwd, "fade") == pytest.approx(fade), (
        f"'fade' must take the OPPOSITE side of a {drift:+.2%} drift")
    assert lus.trade_return(drift, fwd, "follow") == pytest.approx(follow), (
        f"'follow' must take the SAME side as a {drift:+.2%} drift")


def test_fade_and_follow_are_exact_opposites(lus):
    """Structural: whatever the convention, the two sides must negate."""
    for drift in (+0.03, -0.03, +1e-9, -1e-9):
        for fwd in (+0.02, -0.02, 0.0):
            assert lus.trade_return(drift, fwd, "fade") == pytest.approx(
                -lus.trade_return(drift, fwd, "follow"))


def test_fade_profits_exactly_when_the_move_reverses(lus):
    """The NAME's own semantics, stated as a property rather than a table.

    Fading is betting on reversal, so its return is positive precisely when
    drift and forward move in OPPOSITE directions. A double negation flips
    this and the assertion fails — which is the whole point.
    """
    for drift in (+0.05, +0.001, -0.001, -0.05):
        for fwd in (+0.04, +0.002, -0.002, -0.04):
            reversed_ = (drift > 0) != (fwd > 0)
            got = lus.trade_return(drift, fwd, "fade")
            assert (got > 0) == reversed_, (
                f"fade(drift={drift:+}, fwd={fwd:+}) = {got:+} but the move "
                f"{'reversed' if reversed_ else 'continued'}")


# ------------------------------------------------------------- the halves bug
def test_the_module_does_not_split_halves_by_coin_order(lus):
    """The second defect: `h1`/`h2` were the first/second half of the COIN LIST.

    The published "+0.553/+0.044, both halves positive" was a NAME split, so it
    said nothing about stability over time — and 'both halves positive' is one
    of the six go-live bars. The fix sorts trades by day before splitting; this
    pins that the sort key is present and is the DAY.
    """
    src = _PATH.read_text()
    assert "dated.sort(key=lambda x: x[0])" in src, (
        "halves must be computed on a TIME-ordered trade list")
    # And the old shape must not come back: a flat per-coin concatenation with
    # no day attached cannot be time-split at all.
    assert "allr += r" not in src, (
        "per-coin concatenation without a day key reintroduces the name split")


def test_us_session_hours_are_dst_aware(lus):
    """The declared (20,14) UTC pair is EDT-only; ~4 months of tape are EST."""
    est = lus.session_hours("AAPL", lus.US_DST_2026[0] - 86400)
    edt = lus.session_hours("AAPL", lus.US_DST_2026[0] + 86400)
    assert est != edt, "US hours must shift across the DST boundary"
    assert edt == (20, 14) and est == (21, 15)
    # A non-US bucket must be untouched by the US rule.
    assert lus.session_hours("SKHYNIXUSD", lus.US_DST_2026[0] + 86400) == (7, 0)


def test_the_truth_table_is_internally_consistent():
    """The table above was WRONG on two rows when first written, and this is
    the arm that would have caught it without running the module at all.

    Both drift-DOWN rows listed `fade` and `follow` with the SAME sign — which
    is impossible, since the two sides are by definition opposites. The lesson
    is the one this whole file records, turned on the test itself: a fixture
    written by whoever wrote the thing under test encodes the same confusion.
    Assert the fixture's own invariants, not just the code's.
    """
    import re
    src = pathlib.Path(__file__).read_text()
    block = re.search(r"@pytest\.mark\.parametrize\([^)]*?\[(.*?)\]\)",
                      src, re.S)
    assert block, "parametrize table not found"
    rows = re.findall(r"\(\s*([+-][\d.]+),\s*([+-][\d.]+),\s*"
                      r"([+-][\d.]+),\s*([+-][\d.]+)\)", block.group(1))
    assert len(rows) == 4, f"expected 4 hand-computed rows, found {len(rows)}"
    for drift, fwd, fade, follow in rows:
        d, f, fa, fo = map(float, (drift, fwd, fade, follow))
        assert fa == -fo, (
            f"row (drift={d:+}, fwd={f:+}) lists fade={fa:+} and follow={fo:+} "
            f"— the two sides must be exact opposites")
        assert (fa > 0) == ((d > 0) != (f > 0)), (
            f"row (drift={d:+}, fwd={f:+}) claims fade={fa:+}, but fading "
            f"profits exactly when the move REVERSES")
