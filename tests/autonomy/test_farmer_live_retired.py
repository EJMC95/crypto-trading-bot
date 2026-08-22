#!/usr/bin/env python3
"""[2026-08-22 (ta)] 💸 THE FARMER'S LIVE ARM IS RETIRED — 🔮 georgia takes it.

**Eamon, 22-Aug: "just replace farmer with georgia as weve done so many times
before".**

The evidence is the fleet's OWN grader, not an opinion about a bad week: the
live arm reads n=91 / mean −0.160%/trade / t=−0.88 / halves +2.51/−7.65 and its
shadow twin n=161 / −0.195% / t=−0.95 / +5.71/−18.32 — **horizon `unreachable`
on both**, the grader's own verdict that "more of the same closes cannot flip
mean/t/halves".

THREE PROPERTIES THIS FILE EXISTS FOR, in descending order of what they cost if
they break:

1. **ROW-SCOPED, NOT PROCESS-SCOPED.** One module runs both arms. The
   idle-the-whole-process shape used by 🌊/📊/🧙 would silence the SHADOW twin
   too — the control arm, which costs nothing and is still accruing evidence.
   The (mr) rule: declare once, derive the roster.
2. **IT FLATTENS.** Every prior retirement froze PAPER positions. This one held
   four REAL directional legs, and a live position with no manager has no stop
   and no exit. Retiring by freezing would have been strictly worse than
   closing.
3. **ONE OWNER OF THE FACT.** The bot and the 🧪 judge run in different images
   and cannot import each other, so the declaration lives in `fleet_bus` and
   both read it — including the override, parsed identically (the
   `BRAIN_MULT_ENGINE` rule: a detector and its subject disagreeing about one
   env var is how a kill switch goes silent).
"""
import ast
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fleet_bus as fb                                    # noqa: E402

LIVE = "perps-funding-lighter-lighter"
SHADOW = "perps-funding-lighter-lshadow"


# ---- 1  the declaration ----------------------------------------------------

def test_the_live_row_is_declared_retired_with_its_reason():
    spec = fb.RETIRED_LIVE_ARMS[LIVE]
    assert spec["successor"] == "freqtrade-georgia-lighter"
    assert spec["override"] == "FARMER_LIVE_RETIRED_OVERRIDE"
    # the grader's numbers, so the retirement stays falsifiable from the file
    assert "unreachable" in spec["why"]
    assert fb.live_arm_retired(LIVE) is True


def test_the_SHADOW_twin_keeps_trading():
    """The single most costly way to get this wrong. The shadow arm is the
    control and is still accruing; retiring the live row must not touch it."""
    assert fb.live_arm_retired(SHADOW) is False
    assert SHADOW not in fb.RETIRED_LIVE_ARMS


def test_an_unknown_row_is_never_retired():
    """Fail-safe direction is KEEP TRADING: a typo in the table can only fail
    to retire something, never silence a living book."""
    for row in ("band-garrett-lshadow", "freqtrade-georgia-lighter",
                "perps-funding-lighter", "", "perps-funding-lighter-lighterX"):
        assert fb.live_arm_retired(row) is False, row


@pytest.mark.parametrize("val,retired", [
    ("run", False), ("RUN", False), ("1", False), ("true", False),
    ("", True), ("no", True), (" run ", False),
])
def test_the_override_resurrects_and_is_parsed_one_way(monkeypatch, val,
                                                       retired):
    monkeypatch.setenv("FARMER_LIVE_RETIRED_OVERRIDE", val)
    assert fb.live_arm_retired(LIVE) is retired


# ---- 2  the bot's own two process-level guards ------------------------------

def _bot_src():
    return (ROOT / "lighter_funding_bot.py").read_text()


def test_a_shadow_process_never_retires_whatever_the_row_says():
    """`mode` is checked FIRST. A mis-set VENUE on a shadow service must not be
    able to retire anything — real money is the only thing at stake here."""
    src = _bot_src()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "live_arm_retired")
    body = [n for n in fn.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    first = body[0]
    assert isinstance(first, ast.If), "the mode guard must run first"
    assert "lighter_live" in ast.unparse(first.test)
    assert isinstance(first.body[0], ast.Return)
    assert ast.unparse(first.body[0]).endswith("False")


# The tests below IMPORT the real module and CALL the real function. The
# structural checks above are about ORDER inside `main()`, which cannot be
# driven without adding a test-only injection point to a 4,700-line real-money
# file — but the decision function itself has no such excuse, and a source-grep
# standing in for a call is the "a check that inspects nothing" shape.
@pytest.fixture(scope="module")
def bot():
    import lighter_funding_bot as m
    return m


@pytest.mark.parametrize("row,mode,expect", [
    # the retired arm, in the only mode where real money is at stake
    ("perps-funding-lighter-lighter", "lighter_live", True),
    # ...the SAME row in any other mode is NOT retired: the shadow/paper
    # process must keep running whatever the table says
    ("perps-funding-lighter-lighter", "lighter_shadow", False),
    ("perps-funding-lighter-lighter", "hl_paper", False),
    ("perps-funding-lighter-lighter", "", False),
    # the control arm, untouched
    ("perps-funding-lighter-lshadow", "lighter_shadow", False),
    ("perps-funding-lighter-lshadow", "lighter_live", False),
    # 🛢️ Garrett is a VARIANT of this same module. If it were ever funded, it
    # must not inherit the Farmer's retirement — the table is keyed by ROW.
    ("band-garrett-lshadow", "lighter_live", False),
])
def test_the_decision_function_driven(bot, row, mode, expect):
    assert bot.live_arm_retired(row, mode) is expect


def test_a_dark_bus_stands_a_live_arm_DOWN_not_up(bot, monkeypatch):
    """DRIVEN, with the bus actually removed.

    Deliberately the opposite of every other bus read in the fleet: dark ⇒
    neutral elsewhere, because the cost there is a missed shadow trade, while
    here the cost of failing OPEN is a retired REAL-MONEY book resurrecting
    itself on an import error."""
    monkeypatch.setattr(bot, "fleet_bus", None)
    assert bot.live_arm_retired("perps-funding-lighter-lighter",
                                "lighter_live") is True
    # ...and it still cannot touch a shadow arm, because the mode guard runs
    # first — a dark bus must not idle the control arm.
    assert bot.live_arm_retired("perps-funding-lighter-lshadow",
                                "lighter_shadow") is False
    assert bot.live_arm_retired("band-garrett-lshadow",
                                "lighter_shadow") is False


def test_a_THROWING_bus_also_stands_it_down(bot, monkeypatch):
    """Not the same case as a missing one: an installed-but-broken bus raises
    rather than being None, and an unguarded call would crash the live loop —
    which `main()`'s own except would swallow into "keep trading"."""
    class _Broken:
        def live_arm_retired(self, row):
            raise RuntimeError("payload unreadable")
    monkeypatch.setattr(bot, "fleet_bus", _Broken())
    assert bot.live_arm_retired("perps-funding-lighter-lighter",
                                "lighter_live") is True


def test_the_override_reaches_the_bot_with_no_bus_at_all(bot, monkeypatch):
    """The escape hatch must not depend on the thing that is broken. If the
    override only worked through the bus, a dark bus would make a retired
    real-money arm UNRESURRECTABLE."""
    monkeypatch.setattr(bot, "fleet_bus", None)
    monkeypatch.setattr(bot, "FARMER_LIVE_RETIRED_OVERRIDE", "run")
    assert bot.live_arm_retired("perps-funding-lighter-lighter",
                                "lighter_live") is False


# ---- 3  the latch, the flatten and the receipt ------------------------------

def _main_fn():
    tree = ast.parse(_bot_src())
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_the_latch_runs_AFTER_the_day_roll_or_it_is_cleared_once_a_day():
    """`(pr)`: a new UTC day starts unhalted BY CONSTRUCTION, so the roll sets
    `halted_today = False`. A retirement latched before it would be silently
    undone every 24h and the book would trade for a whole day."""
    main = _main_fn()
    roll = [n.lineno for n in ast.walk(main)
            if isinstance(n, ast.Assign)
            and "halted_today" in ast.unparse(n)
            and "now.date()" in ast.unparse(n)]
    latch = [n.lineno for n in ast.walk(main)
             if isinstance(n, ast.If)
             and "live_arm_retired" in ast.unparse(n.test)]
    assert roll and latch, (roll, latch)
    assert min(latch) > max(roll), \
        f"the retirement latch (line {min(latch)}) must follow the day roll " \
        f"(line {max(roll)}) or the roll clears it daily"


def test_the_latch_runs_BEFORE_the_halt_block_that_does_the_flattening():
    """The latch is four lines because the halt block already flattens,
    retries until flat, blocks entries and heartbeats. Ordering is what makes
    that reuse work — a latch after it does nothing until the next cycle."""
    main = _main_fn()
    latch = min(n.lineno for n in ast.walk(main)
                if isinstance(n, ast.If)
                and "live_arm_retired" in ast.unparse(n.test))
    halt = [n.lineno for n in ast.walk(main)
            if isinstance(n, ast.If) and ast.unparse(n.test) == "halted_today"]
    assert halt and latch < min(halt), (latch, halt)


def test_the_flatten_records_RETIRED_not_daily_loss():
    """I23 on the last four trades a real-money book will ever book. Labelling
    a retirement as a daily-loss stop puts phantom rows in the ledger every
    grader and exit-attribution study reads."""
    src = _bot_src()
    assert '_flatten_all("retired"' in src
    i = src.index('_flatten_all("retired"')
    assert "live_arm_retired(bot_id, ctx.mode)" in src[i:i + 200]


def test_the_row_publishes_that_it_is_RETIRED_not_merely_halted():
    """I1/I18: `status='halted'` is byte-identical between "lost 5% today" and
    "retired 22-Aug", and those need different actions. `open` is what says the
    flatten finished, so the retirement is falsifiable from the row rather than
    from a deploy log."""
    src = _bot_src()
    assert '"retired": {' in src
    i = src.index('"retired": {')
    blk = src[i:i + 700]
    for field in ('"since"', '"why"', '"open"', '"override"'):
        assert field in blk, field
    assert "if live_arm_retired(bot_id, ctx.mode) else {}" in blk, \
        "a LIVING arm must not publish a retired block"


# ---- 4  the judge stands down ----------------------------------------------

def test_the_judge_stands_down_rather_than_silently_never_promoting():
    """Its paired bar needs `live >= 10` closes, so a flat arm silences it
    CORRECTLY and INVISIBLY — `promote: false` reading the same for "no
    candidate cleared" and "there is no arm to promote onto" (I18)."""
    src = (ROOT / "experiment_judge.py").read_text()
    assert "_bus.live_arm_retired(LIVE_BOT)" in src
    i = src.index("_bus.live_arm_retired(LIVE_BOT)")
    blk = src[i:i + 900]
    assert 'phase="stood_down"' in blk
    # it must return BEFORE evaluating, not after
    assert "return save(" in blk
    growth = src.index("_g2, _glast = growth_step(")
    assert i < growth, "the stand-down must precede the growth promoter"


def test_the_judge_fails_OPEN_on_a_dark_bus_and_says_why():
    """Opposite of the bot's rule, on purpose: a judge that cannot import the
    bus must keep judging, and the paired bar's own `live >= 10` floor still
    blocks every promotion onto a flat arm. Failing closed here would stop the
    fleet's only path to more real money on an import error."""
    src = (ROOT / "experiment_judge.py").read_text()
    assert "_bus = None" in src
    assert "if _bus is not None and _bus.live_arm_retired(LIVE_BOT):" in src
