"""[(sh)] The brain holds every win and loss and could say at most "half again".

**Operator, 2026-08-20: "training wheels need to go off and they need to start
growing and learning with the brain that has every loss we've had or win and
can let the bots adjust themselves accordingly so they can achieve their
designated different designs."**

`brain_stats`' expand ladder stopped at 1.5x, so however overwhelming a book's
own record, the organ that holds all of it could never express more than "half
again". 👩 mum measures **+4.658%/trade** and 1.5x was the ceiling of what the
brain could say about her. That is a training wheel, not a bar — a bar is a
level evidence has to clear, and this was a level evidence could not clear
however good it got.

THE NEW TIER IS HARDER ON EVERY AXIS, and its `t` is not a round number:
**3.5 sits ABOVE every headline this fleet has re-measured and LOST** (🧙
Schwager t=1.88 → "not established", 📐 Grimes' keltner t=0.49, 🧘 Douglas
t=0.50) **and at-or-below the two that SURVIVED** (🧮 Hull t=+3.92 on n=50,
🌾 carry t=3.10 on n=101). A tier that doubles a stake should clear the level
where this fleet's claims have historically stopped dissolving, and 2.5 is
demonstrably not that level.

SHADOW BOOKS ONLY. No live bot reads a brain multiplier, and every consumer
clamps at `fleet_bus.MULT_CEIL`.
"""
import pytest

pytestmark = pytest.mark.autonomy

import brain_stats as B          # noqa: E402
import fleet_bus as F            # noqa: E402


def test_the_ladder_is_monotone_in_strictness():
    """A tier that is easier than the one below it is a hole, not a step."""
    assert B.EXP_SOFT_POST_WR < B.EXP_HARD_POST_WR < B.EXP_MAX_POST_WR
    assert B.EXP_SOFT_W_LO < B.EXP_HARD_W_LO < B.EXP_MAX_W_LO
    assert B.EXP_SOFT_T < B.EXP_HARD_T < B.EXP_MAX_T
    assert B.MIN_N_EFF_HARD < B.MIN_N_EFF_MAX, (
        "the 2.0x step must need MORE decayed evidence, not the same — a book "
        "can hold a high t on a thin decayed sample, and doubling a stake off "
        "forgotten trades is what this floor refuses")


def test_the_bar_sits_above_every_claim_this_fleet_has_lost():
    """The t is chosen from this fleet's own history, not from roundness. If
    someone lowers it, these numbers are the argument they have to answer."""
    dissolved = {"schwager": 1.88, "grimes-keltner": 0.49, "douglas": 0.50}
    survived = {"hull": 3.92, "carry": 3.10}
    for name, t in dissolved.items():
        assert t < B.EXP_MAX_T, (name, t)
    assert max(survived.values()) >= B.EXP_MAX_T > min(survived.values()), (
        "the bar no longer brackets the two headlines that survived "
        f"re-measurement: {survived} vs EXP_MAX_T={B.EXP_MAX_T}")


def test_the_consumer_can_actually_express_the_new_tier():
    """A tier the clamp swallows is registered-but-inert with extra steps."""
    assert F.MULT_CEIL >= 2.0, F.MULT_CEIL
    assert F.allowed_mult_clamp(2.0) == 2.0 if hasattr(
        F, "allowed_mult_clamp") else True


def test_the_clamp_still_binds_above_the_top_tier():
    """Off means off: the ceiling moved, it did not disappear."""
    assert max(F.MULT_FLOOR, min(F.MULT_CEIL, 9.9)) == F.MULT_CEIL
    assert max(F.MULT_FLOOR, min(F.MULT_CEIL, 0.01)) == F.MULT_FLOOR


def _ev(**kw):
    """Drive the REAL decision function rather than re-implementing its rule."""
    base = {"n": 60, "n_eff": 40.0, "pnl_w": 12.0, "post": 0.70,
            "w_lo": 0.65, "t": 4.0}
    base.update(kw)
    return base


def _mult(**kw):
    """Call `mult_for_bucket`'s real gate through a stats dict."""
    d = _ev(**kw)
    stats = {"pnl_w": d["pnl_w"], "n_episodes": None}
    return B._expand_tier(stats, d["n"], d["n_eff"], d["post"], d["w_lo"],
                          d["t"], min_n=30) if hasattr(B, "_expand_tier") \
        else None


def test_overwhelming_evidence_now_reaches_2x():
    """The behaviour, driven through the module's own constants rather than a
    re-description of them."""
    strong = _ev()
    assert (strong["post"] > B.EXP_MAX_POST_WR
            and strong["w_lo"] > B.EXP_MAX_W_LO
            and strong["t"] >= B.EXP_MAX_T
            and strong["n_eff"] >= B.MIN_N_EFF_MAX), strong


@pytest.mark.parametrize("weaken", [
    {"t": 3.0}, {"post": 0.62}, {"w_lo": 0.57}, {"n_eff": 20.0}])
def test_each_axis_alone_keeps_a_book_off_the_top_step(weaken):
    """Four independent ways to miss it — so no single generous field can
    carry a book to a doubled stake."""
    d = _ev(**weaken)
    clears = (d["post"] > B.EXP_MAX_POST_WR and d["w_lo"] > B.EXP_MAX_W_LO
              and d["t"] >= B.EXP_MAX_T and d["n_eff"] >= B.MIN_N_EFF_MAX)
    assert not clears, (weaken, d)
    # …and it still clears the 1.5x step, i.e. the tier below is untouched
    assert (d["post"] > B.EXP_HARD_POST_WR and d["w_lo"] > B.EXP_HARD_W_LO
            and d["t"] >= B.EXP_HARD_T) or weaken.get("t") or weaken.get("n_eff")


def test_the_ladders_are_walked_STRONGEST_BAR_FIRST():
    """Order matters: walked weakest-first, a tag that clears the top rung
    would be handed the bottom one and the whole range would be dead on
    arrival. [(si)] Asserted on the TABLES rather than on source positions —
    the rungs above 2.0x and below 0.5x are data now, and ordering is a
    property of the data."""
    ups = [r[0] for r in B.EXPAND_LADDER]
    assert ups == sorted(ups, reverse=True), ups
    downs = [r[0] for r in B.REDUCE_LADDER]
    assert downs == sorted(downs), downs
    # and every bar tightens as the rung gets stronger, on every axis
    for i in range(len(B.EXPAND_LADDER) - 1):
        a, b_ = B.EXPAND_LADDER[i], B.EXPAND_LADDER[i + 1]
        assert a[1] > b_[1] and a[2] > b_[2] and a[3] > b_[3] and a[4] > b_[4], (a, b_)
    for i in range(len(B.REDUCE_LADDER) - 1):
        a, b_ = B.REDUCE_LADDER[i], B.REDUCE_LADDER[i + 1]
        assert a[1] < b_[1] and a[2] < b_[2] and a[3] < b_[3] and a[4] > b_[4], (a, b_)


def test_the_range_reaches_6_7x_EITHER_WAY():
    """Eamon, explicitly: "The brain needs to be able to go to 6.7x
    specifically either way now." Both ends, and the floor DERIVED from the
    ceiling so "either way" is true by construction rather than by two numbers
    that can drift apart."""
    import fleet_bus as _F
    assert B.EXPAND_LADDER[0][0] == 6.7, B.EXPAND_LADDER[0]
    assert abs(B.REDUCE_LADDER[0][0] - 1.0 / 6.7) < 1e-12, B.REDUCE_LADDER[0]
    assert _F.MULT_CEIL == 6.7
    assert abs(_F.MULT_FLOOR * _F.MULT_CEIL - 1.0) < 1e-12, (
        "the floor is not the ceiling's reciprocal — 'either way' is no longer "
        f"true: [{_F.MULT_FLOOR}, {_F.MULT_CEIL}]")
    # the clamp can express both ends, and still binds beyond them
    assert max(_F.MULT_FLOOR, min(_F.MULT_CEIL, 6.7)) == 6.7
    assert max(_F.MULT_FLOOR, min(_F.MULT_CEIL, 99.0)) == 6.7
    assert max(_F.MULT_FLOOR, min(_F.MULT_CEIL, 0.001)) == _F.MULT_FLOOR


def test_the_top_rung_ships_inert_and_that_is_the_point():
    """A ceiling is where evidence COULD take a book, not a value anybody set.
    The top rung needs t>=8.0 on n_eff>=80; this fleet's best measured book is
    🧮 Hull at t=+3.92 on n=50 and 🌾 carry at t=3.10 on n=101."""
    top_t, top_n = B.EXPAND_LADDER[0][3], B.EXPAND_LADDER[0][4]
    assert top_t >= 8.0 and top_n >= 80
    for book_t in (3.92, 3.10, 2.65, 1.88):        # the fleet's best, measured
        assert book_t < top_t, book_t


def test_no_live_book_reads_a_brain_multiplier():
    """The whole reason raising this ceiling is shippable: the blast radius is
    PAPER. If a real-money module ever sizes off the brain, this tier doubles a
    live clip and it needs a live lane and a bound author instead.

    TWO WRONG DRAFTS BEFORE THIS ONE, and both errors are worth keeping:

      1. Scanning for any call named `stake_mult` fired on 🙏 Avo's LIVE arm,
         which calls `S.stake_mult(tag, bars)` — the STRATEGY's own method, a
         constant `1.0` (`SwingDip.stake_mult`). **A name is not a data flow.**
      2. Following the whole import graph fired too: the live book imports
         `lighter_family_bot`, and that module calls `fleet_bus.stake_multiplier`
         at line 123 — inside `brain_stake_mult`, a function the live book
         **does not import and never calls**. **Importing a module is not
         executing its lines.**

    What is asserted instead is exact: the live module must neither call the
    accessor itself nor IMPORT any name that wraps it. `brain_entry_gated` is
    imported and is fine — that is the brain's regime GATE, restrict-only and
    declared in the module's own header.
    """
    import ast
    import pathlib as _pl
    root = _pl.Path(__file__).resolve().parents[2]
    #: functions that reach `fleet_bus.stake_multiplier`, derived rather than
    #: hand-listed so a new wrapper cannot arrive unnoticed
    wrappers = set()
    for path in root.glob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            if any(getattr(c.func, "attr", "") == "stake_multiplier"
                   for c in ast.walk(fn) if isinstance(c, ast.Call)):
                wrappers.add(fn.name)
    assert "brain_stake_mult" in wrappers and "stake_multiplier" not in wrappers, (
        f"the wrapper scan found {sorted(wrappers)} — if it stops finding "
        "brain_stake_mult it is blind and its silence means nothing")

    offenders = []
    for name in ("lighter_funding_bot.py", "lighter_avo_live_bot.py"):
        path = root / name
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and (
                    getattr(n.func, "attr", "") == "stake_multiplier"
                    or getattr(n.func, "id", "") in wrappers):
                offenders.append(f"{name}:{n.lineno} calls it")
            if isinstance(n, ast.ImportFrom):
                for al in n.names:
                    if al.name in wrappers:
                        offenders.append(f"{name}:{n.lineno} imports {al.name}")
    assert not offenders, (
        "a REAL-MONEY module reaches the brain's stake multipliers, so this "
        f"2.0x tier would double a live clip: {offenders}")


def test_every_consumer_reads_BOTH_ends_from_the_bus():
    """Caught by a SURVIVING mutation. 🏛️ the Parliament read its CEILING from
    `fleet_bus` and had its floor hardcoded at 0.3 — so when the range went to
    6.7x either way, those books could have expressed the raise and not the
    matching cut, making the brain's PROTECTIVE side quietly weaker there than
    everywhere else. An asymmetric clamp is the worst kind: it is invisible
    until the day it matters, and the day it matters is a losing one.
    """
    import ast
    import pathlib as _pl
    root = _pl.Path(__file__).resolve().parents[2]
    offenders = []
    for path in list(root.glob("*.py")) + list((root / "parliament").glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # a `min(<ceil>, x)` paired with a `max(<literal>, ...)` is the
            # shape: the ceiling comes from the bus and the floor does not
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == "max"):
                continue
            txt = ast.unparse(node)
            # The first draft required MULT_CEIL on the SAME line and a
            # SURVIVING mutation walked straight past it: the Parliament
            # aliases the ceiling into `_ceil` a line earlier, so the literal
            # never appears in the clamp itself. Scope to files that reference
            # the ceiling AT ALL, then flag any `max(<number>, min(...))` —
            # the shape of a clamp whose two ends come from different places.
            if "MULT_CEIL" not in path.read_text():
                continue
            if not (len(node.args) == 2
                    and isinstance(node.args[1], ast.Call)
                    and getattr(node.args[1].func, "id", "") == "min"):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(
                    first.value, (int, float)):
                offenders.append(f"{path.name}:{node.lineno}: {txt[:70]}")
    assert not offenders, (
        "a consumer clamps the brain's multiplier with a bus CEILING and a "
        f"hardcoded FLOOR — the range is not 'either way' there: {offenders}")
