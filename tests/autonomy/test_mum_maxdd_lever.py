"""👩 mum's drawdown-guard trigger is a CAGED, ENV-TUNABLE level — and the guard
itself is not optional.

[2026-09-11 (abi)] Eamon, 11-Sep: *"Do it"* / *"Deploy her"*. Her `maxdd` guard
locked entries for 12h and kept re-locking. Measured on her own ledger: 40 closes
in the 72h window (the guard needs 8) and a worst in-window drawdown of **17.3%**
of START_EQUITY against a **15%** trigger — so it is neither stale nor wrong.

THAT IS WHY `FAMILY_CLEAR_GUARD` COULD NOT HELP, and the distinction is the
lesson: that switch drops a lock RESTORED from disk at boot, while this one is
RE-DERIVED from live trades every cycle. Measured: it cleared and re-armed within
the same boot, `locked_until` moving 01:18:57Z -> 01:28:19Z. **A rail that
re-creates itself cannot be released — only its level can move.**

So the level moved, 0.15 -> 0.25, which is the value two sibling books in the same
file already run. And it became an env so the next such decision costs a variable
rather than a merge: the whole reason a 12h lock cost a deploy cycle today is that
the number was a literal.

WHAT IS PINNED: the cage, the fail-safe direction, and that the guard still
EXISTS. CLAUDE.md's permanent doctrine is explicit that a rail's VALUES are
delegated and its existence is not.
"""
from __future__ import annotations

import importlib
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _mod(val=None):
    """Reload with MUM_MAXDD_DD set (or cleared) — the value is read at IMPORT
    because `protections` is a class attribute, so a reload is the only honest
    way to test it."""
    if val is None:
        os.environ.pop("MUM_MAXDD_DD", None)
    else:
        os.environ["MUM_MAXDD_DD"] = str(val)
    import lighter_family_bot as m
    return importlib.reload(m)


def _mum_maxdd(m):
    """Her guard as the running roster actually carries it — not the class read
    directly, so a carrier that stopped using the helper is caught."""
    for c in m.live_strategies():
        if c.bot == "freqtrade-mum":
            return c.protections["maxdd"]
    # `raise`, not `pytest.fail(...)`: the latter does raise, but statically this
    # function then mixes an explicit return with an implicit fall-through that
    # would yield None — CodeQL flagged exactly that, and a helper which can
    # silently hand a None to every assertion below is worth the one extra word.
    raise AssertionError("freqtrade-mum is not in the live roster")


def teardown_module(_m):
    os.environ.pop("MUM_MAXDD_DD", None)
    import lighter_family_bot
    importlib.reload(lighter_family_bot)


def test_the_shipped_default_is_the_in_fleet_value():
    m = _mod()
    assert m.MUM_MAXDD_DD_DEFAULT == 0.25
    assert _mum_maxdd(m)["dd"] == 0.25, "the default must reach her carrier"
    # ...and it is the value siblings already run, not a bespoke number
    src = (ROOT / "lighter_family_bot.py").read_text(encoding="utf-8")
    assert src.count('"dd": 0.25') >= 2, (
        "0.25 is justified as the in-fleet value — if the siblings changed, "
        "this entry's reasoning needs re-stating, not silently inheriting")


def test_the_env_moves_the_level_and_reaches_the_running_carrier():
    for v in (0.05, 0.10, 0.18, 0.30, 0.50):
        m = _mod(v)
        assert m._mum_maxdd_dd() == pytest.approx(v), v
        assert _mum_maxdd(m)["dd"] == pytest.approx(v), v


@pytest.mark.parametrize("bad", [
    "abc", "", "None", "0.15.2",          # unparseable
    "nan", "inf", "-inf",                  # non-finite
    0.049, 0.0, -0.10, 0.51, 1.0, 99.0,   # outside the cage
])
def test_a_bad_value_degrades_to_the_shipped_default_never_to_no_guard(bad):
    """Fail-SAFE: the rail's existence is not a tunable. A junk or out-of-cage
    value must never disable the guard, and must never be silently honoured."""
    m = _mod(bad)
    assert m._mum_maxdd_dd() == m.MUM_MAXDD_DD_DEFAULT, bad
    got = _mum_maxdd(m)
    assert got["dd"] == m.MUM_MAXDD_DD_DEFAULT, bad
    assert got["dd"] > 0, "a zero or absent trigger would be no guard at all"


def test_the_cage_is_what_rejects_nan_and_infinity():
    """Pinned because the code has NO separate non-finite branch, on purpose: a
    mutation proved that branch DEAD (the cage rejects both — every comparison
    against NaN is False, and an infinity is outside any finite bound). If the
    cage is ever replaced by something that admits them, this reddens."""
    m = _mod()
    lo, hi = m.MUM_MAXDD_DD_LO, m.MUM_MAXDD_DD_HI
    nan, inf = float("nan"), float("inf")
    assert not (lo <= nan <= hi), "NaN must fail the cage comparison"
    assert not (lo <= inf <= hi) and not (lo <= -inf <= hi)
    for bad in ("nan", "inf", "-inf"):
        assert _mod(bad)._mum_maxdd_dd() == m.MUM_MAXDD_DD_DEFAULT, bad


def test_the_cage_bounds_are_themselves_justified():
    """The cage is not decoration. Below the floor the guard fires on noise;
    above the ceiling it could never fire before a book's own all-slots-stop,
    which is the halt-before-stop mis-ordering (abg) just spent a session on."""
    m = _mod()
    assert m.MUM_MAXDD_DD_LO == 0.05 and m.MUM_MAXDD_DD_HI == 0.50
    assert m.MUM_MAXDD_DD_LO < m.MUM_MAXDD_DD_DEFAULT < m.MUM_MAXDD_DD_HI
    # her all-slots-stop at the leverage Eamon keeps is gross x stop = 9.5 x 4%
    # = 38%, which must sit INSIDE the cage or the ceiling is meaningless
    assert m.MUM_MAXDD_DD_HI > 9.5 * 0.04


def test_the_guard_still_exists_and_still_has_teeth():
    """The level moved; the rail did not go away. Every other field is unchanged,
    and a session may not cite (abi) as licence to remove the guard."""
    m = _mod()
    got = _mum_maxdd(m)
    assert got["lookback"] == 72 and got["trades"] == 8 and got["stop"] == 12
    # and her other protections are untouched by this change
    for c in m.live_strategies():
        if c.bot == "freqtrade-mum":
            assert c.protections["slguard"] == {"lookback": 24, "trades": 3,
                                                "stop": 6}
            assert c.protections["cooldown_candles"] == 2


def test_at_her_measured_drawdown_the_new_level_admits_and_the_old_refused():
    """The whole point, driven rather than asserted: 17.3% measured in her own
    72h window sits above the old 15% trigger and below the new 25% one."""
    m = _mod()
    measured = 0.173
    assert measured >= 0.15, "the old trigger fired — that is why she was locked"
    assert measured < _mum_maxdd(m)["dd"], "the new trigger must admit her"
    # and it is not a blank cheque: a genuinely worse drawdown still locks her
    assert 0.30 >= _mum_maxdd(m)["dd"], "a 30% drawdown must still fire"
