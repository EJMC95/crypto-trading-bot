"""[2026-09-02] ONE POSITION, TWO SPELLINGS, ON OPPOSITE SIDES OF ONE CALL.

`venues.marks.stop_marks` keys its output by whatever spelling its CALLER
handed it; `LighterClient._positions_from` keys the margin block by the FLEET
symbol (`from_lighter`: 1000PEPE -> kPEPE). Those two met in
`margin_state_from`'s mark lookup, and until (xa) they happened to agree —
the variant host passed `venue.positions()` straight through, so both sides
were fleet-spelled.

(xa) fixed a REAL and separate defect the other way: the host's universe,
`meta` and `held` map carry the VENUE's spelling (the scout's `vols` keys), so
a 1000-market was two names in one loop and the reconciler dropped its
bracket. It normalised the position map to the venue spelling — and in doing
so handed `stop_marks` venue-spelled coins, which is what a mark map is now
keyed by.

MEASURED on 👩 mum's REAL-MONEY row, 2-Sep, every field agreeing:

    held             {..., "1000PEPE": "adopted"}      <- venue spelling
    margin.positions [..., "kPEPE"]                    <- fleet spelling
    liq_mark_blind   ["kPEPE"]                         <- the one 1000-market
    mark_blind       ABSENT                            <- the book read FINE
    headroom  {"ok": false, "reason": "mark_blind", "gap_stop_widths": 18.66}

So a position the venue HAD priced, whose order book read fine, was filed as
unmeasurable. Two costs, both real, neither a loss:

  * `nearest_liq` — the published liquidation distance — was computed over
    9 of 10 real-money legs, and a 1000-market can never BE the nearest, so
    `too_close` (the one refusal that means the money is in danger) is
    unreachable for such a leg;
  * `mark_blind` is not in this book's `fleet_immune.HEADROOM_OK` allowlist,
    so a SPELLING paged the operator every loop — the (gl) failure exactly.

The verdict was never unsafe: `mark_blind` is itself a refusal, so the rail
declined in the right direction throughout. What was wrong was the NUMBER and
the REASON.

Fixed at the OWNER (`_mark_for`), not at the call site, because
`lighter_avo_live_bot` and `lighter_funding_bot` carry byte-identical
`_margin_block` helpers and a third caller would inherit the same trap.
"""
import ast
import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from venues import marks as vmarks                            # noqa: E402
from venues.lighter_client import (                           # noqa: E402
    _mark_for, margin_state_from)
from venues.safety import SafetyRails                         # noqa: E402
from venues.symbol_map import from_lighter, to_lighter        # noqa: E402

pytestmark = pytest.mark.autonomy

MUM = "freqtrade-mum-lighter"
STOP = 0.04                       # 👩 mum's own stoploss, as a fraction


def _pos(symbol, liq="50.0", **kw):
    """A position in the VENUE's own shape — every numeric field a STRING,
    which is what `AccountPosition` declares and what a hand-written float
    fixture would quietly get wrong (the sibling `test_margin_truth` fixture,
    same shape, same reason)."""
    row = {"symbol": symbol, "sign": 1, "position": "1.0",
           "avg_entry_price": "100.0", "position_value": "100.0",
           "unrealized_pnl": "0.0", "liquidation_price": liq,
           "initial_margin_fraction": "10.0", "allocated_margin": "10.0",
           "margin_mode": 0}
    row.update(kw)
    return row


def _acct(positions, equity="3300.0"):
    return {"total_asset_value": equity, "collateral": equity,
            "positions": positions}


class _Venue:
    """Quotes order books under the VENUE's own spelling.

    That is not a convenience of the fixture — it is what the real client
    does: `LighterClient.orderbook` resolves through `to_lighter`, and
    `to_lighter("1000PEPE")` returns itself (an unknown coin maps 1:1), so a
    venue-spelled coin reads its book fine. Which is precisely why the live
    row published `mark_blind` ABSENT while `liq_mark_blind` named the coin:
    the price was there, under the other name.
    """

    def __init__(self, books, acct):
        self._books, self._acct = books, acct

    def orderbook(self, coin):
        return self._books.get(coin)

    def margin_state(self, marks=None):
        return margin_state_from(self._acct, marks=marks)


def _book(px):
    return {"bids": [(px * 0.999, 10.0)], "asks": [(px * 1.001, 10.0)]}


# 👩 mum's real-money holding, reduced to the two legs that matter: the
# 1000-market (two spellings) and a plain one (one spelling).
#
# THE GEOMETRY HERE IS CONSTRUCTED, NOT TODAY'S — and saying so is the point.
# On the live row the blind leg is the SECOND-nearest (kPEPE liq 0.00061214
# against an entry of 0.00344, so ~0.82 of mark, behind XRP's measured
# 0.79664), which is why the published `gap_stop_widths` happened to be
# correct while the leg was invisible. This fixture puts the 1000-market
# NEAREST on purpose, because that is the day the defect stops being a near
# miss: the row would publish the comfortable leg's distance and `too_close`
# could not fire on the dangerous one. A test that only reproduced today's
# safe geometry would pass on the pre-fix code.
LIVE_ACCT = _acct([_pos("1000PEPE", liq="0.0090"),
                   _pos("XRP", liq="0.3335")])
LIVE_BOOKS = {"1000PEPE": _book(0.0100), "XRP": _book(1.3154)}


def _drive(coins, books=None, acct=None):
    """The whole seam, in the order the live host runs it."""
    venue = _Venue(books if books is not None else LIVE_BOOKS,
                   acct if acct is not None else LIVE_ACCT)
    live, blind = vmarks.stop_marks(venue, list(coins))
    st = venue.margin_state(marks=live or None)
    return st, live, blind


# ── the premise, read from the source rather than retyped ────────────────────

def test_the_two_sides_of_the_seam_really_do_disagree():
    """`to_lighter` and `from_lighter` are inverses on a 1000-market, so the
    two spellings are genuinely different strings for one market. If this ever
    stopped being true the whole class would be gone and this file inert."""
    assert to_lighter("kPEPE")[0] == "1000PEPE"
    assert from_lighter("1000PEPE")[0] == "kPEPE"
    assert to_lighter("XRP")[0] == "XRP" == from_lighter("XRP")[0]


def test_the_live_host_hands_the_venue_spelling_to_the_margin_block():
    """(xa)'s normalisation is what makes the caller venue-spelled. Read from
    `lighter_avo_live_bot` by AST so a rewrite of that line cannot leave this
    file asserting a premise the host no longer has."""
    src = Path(ROOT, "lighter_avo_live_bot.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "to_lighter"]
    assert calls, ("the host no longer normalises its position map through "
                   "to_lighter — re-read (xa) before deleting this file")


def test_the_margin_block_is_keyed_by_the_fleet_spelling():
    """The other side: `_positions_from` runs every venue symbol through
    `from_lighter`, so the block's own keys are fleet-spelled."""
    st = margin_state_from(LIVE_ACCT)
    assert sorted(st["positions"]) == ["XRP", "kPEPE"]


# ── the incident, driven end to end ──────────────────────────────────────────

def test_a_venue_spelled_mark_prices_the_position_it_names():
    """THE INCIDENT. Before the fix this left `liq_mark_blind: ['kPEPE']` with
    the caller's own `blind` EMPTY — a priced, readable position reported as
    unmeasurable."""
    st, live, blind = _drive(["1000PEPE", "XRP"])
    assert blind == [], "premise: both books read fine"
    assert sorted(live) == ["1000PEPE", "XRP"], "marks are venue-spelled"
    assert st["liq_mark_blind"] == [], st["liq_mark_blind"]
    assert "dist_frac" in st["positions"]["kPEPE"]


def test_the_nearest_liquidation_can_be_the_leg_the_row_could_not_see():
    """The consequential half: the published risk number is computed over a
    SUBSET, so on the day the 1000-market IS the closest, the row publishes
    the comfortable leg's distance instead and `too_close` cannot fire on the
    dangerous one. Constructed geometry — see the fixture note above."""
    st, _, _ = _drive(["1000PEPE", "XRP"])
    assert st["nearest_liq"]["coin"] == "kPEPE"
    assert st["nearest_liq"]["dist_frac"] < 0.2


def test_the_page_the_spelling_caused_is_gone_and_it_was_never_allowlisted():
    """`fleet_immune.HEADROOM_OK` is read, never retyped: `mark_blind` is not
    among mum's declared-structural reasons, which is why this paged every
    loop. After the fix the verdict falls through to a reason that IS declared."""
    import fleet_immune
    allowed = fleet_immune.HEADROOM_OK.get(MUM, set())
    assert "mark_blind" not in allowed, (
        "if this ever becomes allowlisted, the page below stops being the "
        "cost this fix is justified by — re-read the entry")
    st, _, _ = _drive(["1000PEPE", "XRP"])
    rails = SafetyRails(MUM, "lighter_live")
    ok, why = rails.headroom_check(st, STOP)
    assert why != "mark_blind", why
    assert ok or why in allowed, (ok, why)


# ── no regression, and the teeth are kept ────────────────────────────────────

def test_a_fleet_spelled_mark_still_prices_it():
    """Every caller that was correct before must stay correct: the fleet
    spelling is tried FIRST and the alias is only a fallback."""
    st = margin_state_from(LIVE_ACCT, marks={"kPEPE": 0.0100, "XRP": 1.3154})
    assert st["liq_mark_blind"] == []
    assert st["nearest_liq"]["coin"] == "kPEPE"


def test_a_genuinely_unreadable_mark_is_still_reported_blind():
    """The guard must keep its teeth. A position the venue PRICED whose book
    cannot be read stays in `liq_mark_blind`, and the rail still refuses."""
    st, _, blind = _drive(["1000PEPE", "XRP"],
                          books={"XRP": _book(1.3154)})
    assert blind == ["1000PEPE"], blind
    assert st["liq_mark_blind"] == ["kPEPE"], st["liq_mark_blind"]
    ok, why = SafetyRails(MUM, "lighter_live").headroom_check(st, STOP)
    assert (ok, why) == (False, "mark_blind")


def test_the_alias_can_never_resolve_to_another_markets_price():
    """The one way an alias-tolerant lookup could be worse than the bug: a
    mark for a DIFFERENT market answering. `to_lighter` is definitional, so
    it cannot — pinned, because this is a real-money price."""
    assert _mark_for({"1000BONK": 9.0}, "kPEPE") is None
    assert _mark_for({"1000PEPE": 0.01}, "kPEPE") == 0.01
    assert _mark_for({}, "kPEPE") is None
    assert _mark_for(None, "kPEPE") is None
    assert _mark_for({"XRP": 1.3}, "XRP") == 1.3


def test_the_alias_rule_has_exactly_one_owner():
    """`venues.symbol_map` owns the 1000-market alias. A second copy of that
    rule inside the lookup would be a second rule ((hj)) — and this one sits
    on the path that prices real money."""
    src = Path(ROOT, "venues", "lighter_client.py").read_text(encoding="utf-8")
    body = src[src.index("def _mark_for("):]
    body = body[:body.index("\ndef ", 1)]
    assert "to_lighter(" in body, "the lookup must go through the one owner"
    for spelled in ("1000", 'startswith("k")', "kPEPE"):
        assert spelled not in body.split('"""')[-1], (
            f"{spelled!r} in the executable body is a second alias table")
