"""[(xr)] The adopted purge — Eamon, 2-Sep: *"get rid of anything adopted from
mum or avo"*.

An adopted leg (`(xa)`) is one the book found on the venue with no bracket of
its own. It is not the book's evidence ((xq)); on 🙏 avo it was also holding
2 of her 5 slots while her only exits are a −10% stop and an ROI ladder that
reaches 0% at 14 days — no time stop — so such a leg occupies a slot
indefinitely. Her last close was 28-Aug with all 5 slots full.

DEFAULT OFF, and that is the load-bearing property: a container that loses its
meta re-adopts its OWN positions, which is the case `(xa)` exists for, so
switching this on during a state incident liquidates a live book at market.
"""
import os
import sys

import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, _ROOT)
os.environ.setdefault("FAMILY_LIVE_BOOK", "freqtrade-avo-maria")

import lighter_avo_live_bot as L  # noqa: E402


class _Strat:
    stoploss = -0.10
    roi = {0: 0.20, 20160: 0.0}


def _reason(meta, profit=0.0, age_min=60.0, flatten=None, strategy=None):
    old = L.FLATTEN_ADOPTED
    if flatten is not None:
        L.FLATTEN_ADOPTED = flatten
    try:
        return L.manage_exit_reason(strategy or _Strat(), meta, px=100.0,
                                    profit=profit, age_min=age_min,
                                    sig=None, bars=None)
    finally:
        L.FLATTEN_ADOPTED = old


def test_it_is_off_by_default():
    """A live book must not liquidate itself because a state read failed."""
    assert L.FLATTEN_ADOPTED is False


def test_off_leaves_an_adopted_leg_exactly_as_it_was():
    assert _reason({"tag": L.ADOPTED_TAG}, profit=-0.02, flatten=False) is None


def test_on_purges_an_adopted_leg():
    assert _reason({"tag": L.ADOPTED_TAG}, profit=-0.02,
                   flatten=True) == "adopted_purge"


def test_on_never_touches_a_leg_the_book_opened():
    assert _reason({"tag": "dip_in_uptrend"}, profit=-0.02,
                   flatten=True) is None


def test_a_genuine_stop_still_books_as_a_stop_not_a_purge():
    """The risk record is what a stop is FOR. A purge must not paper over one."""
    assert _reason({"tag": L.ADOPTED_TAG}, profit=-0.50,
                   flatten=True) == "stop_loss"


def test_the_purge_pre_empts_the_roi_ladder():
    """Her ladder reaches 0% at 14 days; an adopted leg must not wait it out."""
    got = _reason({"tag": L.ADOPTED_TAG}, profit=0.001, age_min=10.0,
                  flatten=True)
    assert got == "adopted_purge"


@pytest.mark.parametrize("raw,want", [("1", True), ("true", True),
                                      ("YES", True), ("on", True),
                                      ("0", False), ("", False),
                                      ("off", False), ("banana", False)])
def test_the_switch_parses_conservatively(raw, want, monkeypatch):
    """Junk reads OFF. A misspelled switch must never liquidate a book."""
    monkeypatch.setenv(L._PFX + "_FLATTEN_ADOPTED", raw)
    val = str(L._env("FLATTEN_ADOPTED", "0")).strip().lower() in (
        "1", "true", "yes", "on")
    assert val is want


def test_the_switch_is_read_from_env_only_never_from_an_organ():
    """It is an OPERATOR assertion ('these are not mine'), so no lever, no bus,
    no brain may set it — the blast radius is a live book at market."""
    import ast
    src = open(L.__file__).read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "FLATTEN_ADOPTED":
                    call = node.value
                    # str(_env(...)).strip().lower() in (...)
                    assert "_env" in ast.dump(call), ast.dump(call)[:200]
                    assert "get_lever" not in ast.dump(call)
                    assert "fleet_bus" not in ast.dump(call)
                    return
    raise AssertionError("FLATTEN_ADOPTED is not assigned at module level")


def test_it_cannot_reach_the_entry_path():
    """Exits only: a purge switch must never gate, size or admit an entry."""
    import ast
    tree = ast.parse(open(L.__file__).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "clip_usd", "gross_x", "cap_slots", "vol_target_gross_x"):
            assert "FLATTEN_ADOPTED" not in ast.dump(node), node.name
