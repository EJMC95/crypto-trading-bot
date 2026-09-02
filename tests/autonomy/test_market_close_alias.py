"""[2026-09-02] THE LIVE HOST'S VENUE-SPELLED MAP MEETING A FLEET-KEYED OWNER.

Two pins, one seam: a 1000-market must be CLOSEABLE, and it must be able to
receive its own coin veto.

`LighterClient.market_close` is the ONE method on that client which finds its
subject by a DICT LOOKUP (`self.positions().get(coin)`) instead of through
`_resolve`, and `positions()` is keyed by the FLEET symbol (`_positions_from`
-> `from_lighter`: 1000PEPE -> kPEPE). The live family host has keyed its
position map by the VENUE spelling since (xa) — right for its meta, wrong for
this call — so `market_close("1000PEPE")` returned **None having placed no
order, read no book and raised nothing**, while `market_open` (which resolves
first) worked with either spelling.

That silent no-op sits under EVERY exit on a real-money book: the stop, the ROI
ladder, `max_hold`, the delist give-up, the daily-loss flatten and the KILL
SWITCH all call `market_close` and read `None` as "there is no such position".

Pinned at both ends, and driven against the real code — the client method is
driven with the real `_positions_from`, never a hand-written position dict.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest                                              # noqa: E402
from venues.lighter_client import LighterClient            # noqa: E402
from venues.symbol_map import from_lighter                 # noqa: E402

ACCT = {"total_asset_value": "541.16", "collateral": "541.16", "positions": [
    {"symbol": "1000PEPE", "sign": 1, "position": "129456",
     "avg_entry_price": "0.00344", "liquidation_price": "0.00068",
     "position_value": "441.32"},
    {"symbol": "XRP", "sign": 1, "position": "100", "avg_entry_price": "1.40",
     "liquidation_price": "0.295", "position_value": "132.0"},
]}


class _Reached(RuntimeError):
    """market_close got past the position lookup to the order path."""


class _Probe:
    """Exactly what `market_close` touches, and nothing else — so the test can
    see WHERE the real method stops. `positions()` is the real parser."""

    def __init__(self):
        self.touched = []

    def positions(self):
        return LighterClient._positions_from(ACCT)

    def _resolve(self, coin):
        self.touched.append(("_resolve", coin))
        raise _Reached(coin)

    def orderbook(self, coin):                      # pragma: no cover
        self.touched.append(("orderbook", coin))
        return {"bids": [], "asks": []}


def _close(coin):
    """(reached_order_path, result, collaborators touched)"""
    p = _Probe()
    try:
        return False, LighterClient.market_close(p, coin), p.touched
    except _Reached:
        return True, None, p.touched


def test_the_position_map_is_fleet_keyed_which_is_why_this_matters():
    assert sorted(_Probe().positions()) == ["XRP", "kPEPE"]
    assert from_lighter("1000PEPE") == ("kPEPE", 1.0)


@pytest.mark.parametrize("coin", ["1000PEPE", "kPEPE", "XRP"])
def test_market_close_reaches_the_order_path_in_either_spelling(coin):
    reached, res, touched = _close(coin)
    assert reached, (
        f"market_close({coin!r}) returned {res!r} without reaching the order "
        f"path (touched={touched}) — a SILENT no-op: no order, no raise. Every "
        f"exit on a real-money book, the kill switch included, reads that None "
        f"as 'there is no such position'.")


def test_a_coin_with_no_position_still_returns_none_without_raising():
    """The widened lookup must not turn 'nothing to close' into an exception —
    an unlisted or already-flat coin keeps its old contract."""
    for coin in ("DOGE", "1000BONK", "not-a-coin"):
        reached, res, touched = _close(coin)
        assert not reached and res is None, (coin, res, touched)
        assert touched == [], (coin, touched)


def test_the_parser_drops_a_flat_leg_before_the_size_guard_ever_sees_it():
    """Two separate facts, stated separately because conflating them makes a
    vacuous test: `_positions_from` filters `if size:`, so a zero-size row is
    absent from the map entirely and `market_close` returns None at the LOOKUP."""
    acct = {"total_asset_value": "1", "collateral": "1", "positions": [
        {"symbol": "1000PEPE", "sign": 1, "position": "0",
         "avg_entry_price": "0.003"}]}
    assert LighterClient._positions_from(acct) == {}, "the parser drops flat legs"

    class _Zero(_Probe):
        def positions(self):
            return LighterClient._positions_from(acct)

    p = _Zero()
    assert LighterClient.market_close(p, "1000PEPE") is None and p.touched == []


def test_the_size_guard_is_load_bearing_for_a_caller_whose_source_is_not_the_parser():
    """...and the `not pos["size"]` guard is the SECOND line, unreachable
    through the parser (above) and therefore unverified unless driven directly.
    `positions()` is a public method any collaborator may implement; one that
    reports a flat leg rather than dropping it must not produce a reduce-only
    order for zero size. Drives the guard through such a source (I3)."""

    class _FlatReported(_Probe):
        def positions(self):
            return {"kPEPE": {"size": 0.0, "entry": 0.003},
                    "XRP": {"size": 0.0, "entry": 1.40}}

    for coin in ("1000PEPE", "kPEPE", "XRP"):
        p = _FlatReported()
        assert LighterClient.market_close(p, coin) is None, coin
        assert p.touched == [], (coin, p.touched)


def test_the_clients_lookup_defers_to_the_alias_owner_not_a_local_copy():
    """A hand-rolled prefix strip agrees with `from_lighter` on every symbol the
    venue lists today, so no behavioural test can separate them — which is
    exactly how a second copy of the rule survives and then drifts ((hj)).
    Pinned structurally instead: the widened lookup must CALL the owner."""
    import inspect
    fn = inspect.getsource(LighterClient.market_close)
    tree = ast.parse(fn.lstrip())
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "from_lighter" in called, (
        "market_close must resolve the fleet spelling through venues.symbol_map, "
        "never a local re-implementation of the 1000X -> kX rule")
    imported = {a.name for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "from_lighter" in imported and "symbol_map" in (
        [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)][0] or "")


def test_every_venue_close_in_the_live_host_goes_through_the_alias_owner():
    """The host's belt, by AST. Its position map is venue-keyed since (xa), so
    a bare `venue.market_close(sym)` is the defect — a grep would pass on the
    comment describing the fix ((hp)), so this reads the call arguments."""
    with open(os.path.join(ROOT, "lighter_avo_live_bot.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "market_close" and n.args]
    assert len(calls) >= 3, f"expected the manage, delist and flatten sites: {len(calls)}"
    for call in calls:
        arg = call.args[0]
        assert isinstance(arg, ast.Call) and getattr(arg.func, "id", None) == "_fleet", \
            ("every venue.market_close in the live host must take _fleet(sym): "
             "its position map is venue-keyed and positions() is fleet-keyed")


def test_the_hosts_helper_is_the_owner_not_a_second_copy():
    import lighter_avo_live_bot as host
    assert host._fleet("1000PEPE") == "kPEPE" == from_lighter("1000PEPE")[0]
    assert host._fleet("XRP") == "XRP" and host._fleet("kPEPE") == "kPEPE"
    with open(os.path.join(ROOT, "lighter_avo_live_bot.py"), encoding="utf-8") as fh:
        src = fh.read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_fleet")
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "from_lighter" in names, "_fleet must defer to venues.symbol_map, not re-implement it"


# ------------------------------------------- the same seam at the coin veto

def test_the_coin_quality_veto_is_looked_up_in_the_spelling_its_publisher_uses():
    """`market_context._fold_coin_quality` canonicalises BOTH evidence arms onto
    the FLEET spelling — its own comment says why (the taker writes '1000BONK',
    the funding books write 'kBONK', and an un-normalised GROUP BY split one
    coin's evidence) — so `coin-vetoes` is keyed kPEPE/kBONK. The live host's
    universe is VENUE-spelled, so an un-normalised lookup misses for every
    1000-market and the fleet's only automated per-coin refusal on the
    real-money entry path cannot refuse them. Driven on the payload the real
    publisher builds, not a hand-written veto map."""
    from market_context import _fold_coin_quality
    q = _fold_coin_quality(
        venue_rows=[("1000PEPE", 9, 180.0, 9, 0.0, 0)],
        paper_rows=[("1000PEPE", 9, 4, 5)])
    assert "kPEPE" in q and "1000PEPE" not in q, (
        f"the publisher keys the fleet spelling: {sorted(q)}")

    with open(os.path.join(ROOT, "lighter_avo_live_bot.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    # find the `in coin_vetoed` test and require the alias owner in it
    tests = [n for n in ast.walk(tree)
             if isinstance(n, ast.Compare)
             and any(isinstance(c, ast.Name) and c.id == "coin_vetoed"
                     for c in n.comparators)]
    assert tests, "the live host must still consult the coin veto"
    names = set()
    for n in tests:
        names |= {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}
    assert "_fleet" in names, (
        "the coin-veto lookup must normalise through the alias owner — "
        "coin-vetoes is fleet-keyed and this host's universe is venue-spelled")
