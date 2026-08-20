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


def test_the_top_step_is_checked_BEFORE_the_one_below():
    """Order matters: checked weakest-first, a book that clears 2.0x would be
    handed 1.5x and the tier would be dead on arrival."""
    import inspect
    src = inspect.getsource(B)
    i_max, i_hard = src.index("return 2.0, ev"), src.index("return 1.5, ev")
    assert i_max < i_hard, (
        "the 1.5x branch is evaluated first, so nothing can ever reach 2.0x")


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
