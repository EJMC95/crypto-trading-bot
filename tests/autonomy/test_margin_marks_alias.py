"""[2026-09-02] A 1000-MARKET MUST NOT GO MARK-BLIND ON A REAL-MONEY BOOK.

👩 mum's live row published `margin.liq_mark_blind: ["kPEPE"]` while the scout
was publishing that market's mark the whole time. The mechanism is an alias
seam, one layer up from the (xa) one:

  * `venue.positions()` returns FLEET symbols (`from_lighter`: 1000PEPE -> kPEPE);
  * (xa) re-keyed the host's live position map to the VENUE spelling so the exit
    reconciler and the host's meta agree on one name;
  * `_margin_block` passed those VENUE-spelled coins to `marks.stop_marks`, whose
    contract says FLEET symbols and which returns the map keyed as passed;
  * `margin_state_from` keys its positions the FLEET way, so the lookup missed
    for every 1000-market and the leg landed in `liq_mark_blind`.

A blind leg is EXCLUDED from `nearest_liq`, so the account-level liquidation
read is taken over the legs it could price and the blind one is not in the
comparison at all — the (rb) fail-OPEN hole, reopened. Measured that day the
blind leg sat at 80.0% while the published nearest read 77.7%, so nothing was
hidden on that loop; the point is that it CANNOT be seen, whatever it is.

Both ends are pinned here, and every consumer is driven on the payload its real
publisher builds ((hj)) — never a hand-written margin dict.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from venues.lighter_client import margin_state_from      # noqa: E402
from venues.symbol_map import from_lighter, to_lighter   # noqa: E402


def _acct(pepe_liq=0.00068, xrp_liq=0.295):
    """The venue's OWN account shape — symbols as Lighter spells them."""
    return {"total_asset_value": "541.16", "collateral": "541.16", "positions": [
        {"symbol": "1000PEPE", "sign": 1, "position": "500000",
         "avg_entry_price": "0.00072", "liquidation_price": str(pepe_liq),
         "position_value": "360.0", "initial_margin_fraction": "1000"},
        {"symbol": "XRP", "sign": 1, "position": "100",
         "avg_entry_price": "1.40", "liquidation_price": str(xrp_liq),
         "position_value": "132.0", "initial_margin_fraction": "1000"},
    ]}


def test_a_venue_spelled_marks_map_prices_the_1000_market_and_says_it_realigned():
    st = margin_state_from(_acct(), marks={"1000PEPE": 0.00069, "XRP": 1.3216615})
    assert st["liq_mark_blind"] == [], st
    assert "kPEPE" in st["positions"] and "dist_frac" in st["positions"]["kPEPE"], st["positions"]
    # the leg is IN the comparison, and here it is the nearest — the whole point
    assert st["nearest_liq"]["coin"] == "kPEPE", st["nearest_liq"]
    # and the caller's wrong spelling is NAMED, not absorbed (I8)
    assert st["marks_realigned"] == ["1000PEPE"], st["marks_realigned"]


def test_the_fleet_spelling_is_unchanged_and_reports_no_realignment():
    st = margin_state_from(_acct(), marks={"kPEPE": 0.00069, "XRP": 1.3216615})
    assert st["liq_mark_blind"] == [] and st["marks_realigned"] == []
    assert st["nearest_liq"]["coin"] == "kPEPE"
    # both spellings must agree EXACTLY — that is what makes the seam closed
    venue = margin_state_from(_acct(), marks={"1000PEPE": 0.00069, "XRP": 1.3216615})
    assert venue["positions"]["kPEPE"] == st["positions"]["kPEPE"]
    assert venue["nearest_liq"] == st["nearest_liq"]


def test_realignment_never_rescales_a_price():
    """`from_lighter` only ever rewrites 1000X -> kX at a 1.0 multiplier, so the
    mark it carries is the same market in the same units. The raw HL spellings
    that DO carry a 0.001 price scale are never produced by it — if they were,
    a realigned mark would be wrong by 1000x on a liquidation read."""
    for venue_sym in ("1000PEPE", "1000BONK", "1000SHIB", "1000FLOKI"):
        fleet, mult = from_lighter(venue_sym)
        assert mult == 1.0 and fleet.startswith("k"), (venue_sym, fleet, mult)
        assert to_lighter(fleet) == (venue_sym, 1.0), (fleet, to_lighter(fleet))
    # a scaled spelling must never be REACHED by realignment
    assert to_lighter("PEPE")[1] == 0.001 and from_lighter("1000PEPE")[0] != "PEPE"
    # the mark that lands on the position is the one that was passed, untouched
    st = margin_state_from(_acct(), marks={"1000PEPE": 0.00069, "XRP": 1.3216615})
    assert st["positions"]["kPEPE"]["mark"] == 0.00069


def test_the_price_scale_guard_is_load_bearing(monkeypatch):
    """The realignment carries a `mult == 1.0` guard. Today `from_lighter` can
    only ever return 1.0, so the guard is UNREACHABLE on the live surface and a
    mutation that deletes it stays green — which is a guard nobody has verified
    (I3). Drive it: make the owner return a SCALED alias, as it would if a
    raw-unit market were ever mapped that way, and the realignment must REFUSE
    rather than move a price by 1000x onto a liquidation comparison. A refusal
    leaves the leg blind, which is the honest, fail-closed answer."""
    import venues.symbol_map as sm

    def scaled(symbol):
        if symbol == "1000PEPE":
            return "kPEPE", 0.001          # a price-scaling alias
        return sm_from_lighter_real(symbol)

    sm_from_lighter_real = sm.from_lighter
    monkeypatch.setattr(sm, "from_lighter", scaled)
    st = margin_state_from(_acct(), marks={"1000PEPE": 0.00069, "XRP": 1.3216615})
    assert st["liq_mark_blind"] == ["kPEPE"], \
        "a scaled alias must NOT be realigned onto a liquidation read"
    assert st["marks_realigned"] == [], st["marks_realigned"]
    assert "dist_frac" not in st["positions"]["kPEPE"]


def test_a_genuinely_unpriced_leg_still_reports_blind():
    """The realignment must not turn a real blind spot into a silent pass."""
    st = margin_state_from(_acct(), marks={"XRP": 1.3216615})
    assert st["liq_mark_blind"] == ["kPEPE"] and st["marks_realigned"] == []
    assert st["nearest_liq"]["coin"] == "XRP"
    assert margin_state_from(_acct(), marks=None)["liq_mark_blind"] == ["XRP", "kPEPE"]
    assert margin_state_from(_acct(), marks={})["marks_realigned"] == []


def test_a_fleet_key_already_present_wins_over_the_venue_spelling():
    """If a caller passes BOTH spellings, the fleet one is the position's key
    and must not be overwritten by the alias — no silent price substitution."""
    st = margin_state_from(_acct(), marks={"kPEPE": 0.00069, "1000PEPE": 0.111,
                                           "XRP": 1.3216615})
    assert st["positions"]["kPEPE"]["mark"] == 0.00069, st["positions"]["kPEPE"]
    assert st["marks_realigned"] == []


def test_the_live_host_asks_for_marks_in_the_fleet_spelling():
    """The call site itself, by AST: `_margin_block` must map its VENUE-keyed
    position dict through `from_lighter` before calling `stop_marks`. A grep
    would pass on the comment that describes the fix ((hp): a page-wide
    substring scan is not a structural claim), so this reads the call."""
    src = open(os.path.join(ROOT, "lighter_avo_live_bot.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "stop_marks"]
    assert calls, "the live host must still read its stop marks from venues.marks"

    def _names(node):
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}

    # a bound argument is followed to its assignment: the coins reaching
    # stop_marks must pass through the alias owner somewhere, inline or one
    # binding back. Anything deeper is out of this test's reach and would be a
    # false green, so it FAILS instead of guessing.
    assigns = {t.id: n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
               for t in n.targets if isinstance(t, ast.Name)}
    for call in calls:
        arg = call.args[1]
        names = _names(arg)
        for bound in list(names):
            if bound in assigns:
                names |= _names(assigns[bound])
        assert "from_lighter" in names, \
            "stop_marks takes FLEET symbols; the host's position map is venue-keyed since (xa)"
