"""[2026-09-02 (xo)] THE HALT COULD NOT FLATTEN A 1000-MARKET, AND SAID SO IN
A MESSAGE THAT READS LIKE SAFETY.

MEASURED ON REAL MONEY. 👩 mum hit her daily-loss halt at 2026-09-02T17:19Z
(`today_pnl -58.86` against a $57.00 limit). Her row then published:

    flatten_incomplete : true
    held               : {"1000PEPE": "adopted"}
    margin.positions   : {"kPEPE": {size 129456, value 440.02}}
    equity             : 521.77

$440 of a $522 book — 84% — that the halt could not close, on a book whose
halted loop `continue`s past the trading pass, so the position had no roi, no
stop and no max_hold either. Only a flatten retry that could never succeed.

THE CHAIN, each link correct in isolation:
  1  `positions()` keys by the FLEET symbol   -> "kPEPE"
  2  `(xa)` normalises the bot's map to the VENUE spelling (fixing a real
     bracket bug) -> "1000PEPE"
  3  `_flatten_all` iterates that map and calls market_close("1000PEPE")
  4  the lookup was `positions().get(coin)` -> MISS -> None
  5  None is the documented "no position" answer, so the caller logged
     "venue reports NO position — leaving meta; retry next cycle (not booking
     a phantom close)" and repeated it every 90s

This is the THIRD arm of one confusion — (xa) the bracket, (xe) the mark, now
the flatten — which is why the fix is at the OWNER (`position_of`) and not at
the call site: patching a third instance leaves the fourth.
"""
import sys
from pathlib import Path

import pytest

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from venues.symbol_map import from_lighter, to_lighter   # noqa: E402

pytestmark = pytest.mark.autonomy


class _Venue:
    """The real `position_of` / `market_close` bound to a fake account map."""

    def __init__(self, positions):
        self._p = dict(positions)
        self.closed = []

    def positions(self):
        return dict(self._p)

    # the methods under test, taken from the real class
    def position_of(self, coin):
        import venues.lighter_client as lc
        return lc.LighterClient.position_of(self, coin)


def _venue_with_a_1000_market():
    """Her actual shape: the venue holds 1000PEPE, `positions()` files it
    under the FLEET name, and the caller holds the VENUE name."""
    fleet, _ = from_lighter("1000PEPE")
    assert fleet == "kPEPE", fleet
    return _Venue({"kPEPE": {"size": 129456.0, "entry": 0.00344}}), fleet


def test_the_alias_map_is_the_shape_this_bug_needs():
    assert to_lighter("kPEPE")[0] == "1000PEPE"
    assert from_lighter("1000PEPE")[0] == "kPEPE"
    assert to_lighter("1000PEPE")[0] == "1000PEPE", (
        "to_lighter must be idempotent on the venue spelling, or (xa)'s "
        "normalisation would not be stable")


def test_a_position_is_found_under_the_venue_spelling():
    """THE BUG. `_flatten_all` holds "1000PEPE"; the map is keyed "kPEPE"."""
    v, _ = _venue_with_a_1000_market()
    got = v.position_of("1000PEPE")
    assert got is not None and got["size"] == 129456.0, (
        "the venue spelling still misses — a halt cannot flatten a "
        "1000-market and will retry forever while reporting 'no position'")


def test_a_position_is_still_found_under_the_fleet_spelling():
    """The fix must be purely additive — every existing caller holds the
    fleet name and must be byte-identical."""
    v, fleet = _venue_with_a_1000_market()
    assert v.position_of(fleet)["size"] == 129456.0


def test_an_absent_coin_is_still_None():
    """`None` must keep meaning 'no position' — the caller books nothing on
    it, and a fabricated hit here would close a position that is not there."""
    v, _ = _venue_with_a_1000_market()
    assert v.position_of("NOTACOIN") is None
    assert v.position_of("BTC") is None


def test_an_empty_or_unreadable_map_is_None_not_a_crash():
    assert _Venue({}).position_of("1000PEPE") is None


def test_market_close_reads_through_the_owner_not_a_second_lookup():
    """A second copy of the lookup is a second rule — and it is the copy that
    would keep the old blindness."""
    import ast
    src = Path(ROOT, "venues", "lighter_client.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "market_close")
    body = ast.get_source_segment(src, fn) or ""
    assert "position_of(" in body, "market_close no longer uses the owner"
    assert "positions().get(" not in body, (
        "market_close re-introduced a raw positions() lookup — the alias "
        "blindness is back")
