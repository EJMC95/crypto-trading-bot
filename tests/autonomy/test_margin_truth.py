"""[2026-08-16 (no)] THE VENUE PUBLISHES ITS MARGIN STATE AND THIS FLEET READ
NONE OF IT — so "what leverage is the real money at?" had no answer.

THE INCIDENT. `AccountPosition` has carried `margin_mode`,
`initial_margin_fraction`, `liquidation_price`, `position_value` and
`allocated_margin` for as long as the SDK has been pinned.
`LighterClient._positions_from` kept `size`, `entry` and `upnl` and dropped
every one of them. The gap was not cosmetic: the 16-Aug leverage audit could
establish the two live books' sizing CEILINGS from clip arithmetic (Farmer
0.76x, Avo 1.00x) but could not state what either book was actually margined
at, or how far the open positions sat from liquidation, because no published
field carried it.

WHY THE PARSING IS THE DANGEROUS PART, and why most of this file is about it.
The venue sends these as STRINGS, and it sends `0` for a liquidation price it
is not currently tracking. The obvious `float(p.get(k) or 0)` therefore turns
two different unknowns into confident, catastrophic readings:

    liquidation_price 0      -> "this short can never be liquidated"
    initial_margin_fraction 0 -> "this position uses infinite leverage"

Both are the I8 failure — unknown degrading to a guess — in the one place the
guess is a risk number. Every parse here must fail to None, and the census
(`liq_unknown`) must publish even when EMPTY, so "all positions measured and
safe" is never byte-identical to "nothing was measured" ((lv), I18).
"""
import ast
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from venues.base import VenueClient                      # noqa: E402
from venues.lighter_client import (                      # noqa: E402
    _liq_price, _margin_mode, _num, margin_state_from)

LIVE_PUBLISHERS = ("lighter_funding_bot.py", "lighter_avo_live_bot.py")


def _acct(positions, equity="197.52"):
    return {"total_asset_value": equity, "collateral": equity,
            "positions": positions}


def _pos(symbol="XAU", **kw):
    """A position in the venue's OWN shape — every numeric field a STRING,
    which is what `AccountPosition` declares (StrictStr) and what a
    hand-written float fixture would quietly get wrong."""
    row = {"symbol": symbol, "sign": 1, "position": "1.0",
           "avg_entry_price": "100.0", "position_value": "100.0",
           "unrealized_pnl": "0.0", "liquidation_price": "50.0",
           "initial_margin_fraction": "0.1", "allocated_margin": "10.0",
           "margin_mode": 0}
    row.update(kw)
    return row


# --------------------------------------------------------------------------
# the parse guards — an absent field must never read as zero
# --------------------------------------------------------------------------
@pytest.mark.parametrize("raw", [None, "", "  ", "n/a", "nan", "inf", "-inf",
                                 [], {}])
def test_unparseable_numbers_are_unknown_not_zero(raw):
    assert _num(raw) is None, (
        f"{raw!r} parsed to a number; an unreadable venue field must be "
        f"UNKNOWN, because 0.0 is a legitimate-looking risk reading")


@pytest.mark.parametrize("raw", ["0", "0.0", 0, "-5", "-0.01", None, "", "nan"])
def test_a_nonpositive_liquidation_price_is_not_a_price(raw):
    """Lighter sends 0 for a position it is not margining toward liquidation.
    Published as 0.0 that means 'this long is already liquidated' / 'this short
    is infinitely safe' — the direction a risk read must never get wrong."""
    assert _liq_price(raw) is None


def test_a_real_liquidation_price_survives():
    assert _liq_price("4100.5") == 4100.5


def test_margin_mode_names_come_from_the_sdk_not_from_here():
    """A retyped constant is a constant that drifts, and this one decides how
    real money is margined. The names must match the SDK's own values."""
    lighter = pytest.importorskip("lighter")
    sc = lighter.SignerClient
    assert _margin_mode(sc.CROSS_MARGIN_MODE) == "cross"
    assert _margin_mode(sc.ISOLATED_MARGIN_MODE) == "isolated"


def test_an_unrecognised_margin_mode_degrades_to_the_raw_code():
    """I8: unknown degrades to the honest raw value, never to a guess. A new
    venue mode must appear as an unhandled integer, not be silently bucketed
    into one of the two names we happen to know."""
    assert _margin_mode(7) == 7
    assert _margin_mode(None) is None
    assert _margin_mode("junk") is None


# --------------------------------------------------------------------------
# the account view
# --------------------------------------------------------------------------
def test_leverage_is_gross_over_equity():
    st = margin_state_from(_acct([_pos("XAU", position_value="165.0"),
                                  _pos("BTC", position_value="60.0")],
                                 equity="197.52"))
    assert st["gross"] == 225.0
    assert st["leverage"] == pytest.approx(225.0 / 197.52, rel=1e-4)
    assert st["mode"] == "cross"
    assert st["n"] == 2


def test_a_short_leg_adds_to_gross_rather_than_cancelling():
    """Gross exposure, not net: two opposite legs are TWO positions that can
    each be liquidated. Netting them would report a delta-neutral book — ⚖️
    Counterweight's entire shape — as carrying no margin risk at all.

    The short leg's `position_value` is NEGATIVE here on purpose. Today's
    venue sends it unsigned and carries direction in `sign`, so a fixture
    with two positive values passes whether the code sums or nets, and the
    mutation that removes `abs()` survives it (it did). This pins the
    DEFENSIVE property: if the venue ever signs that field, gross must still
    be gross."""
    st = margin_state_from(_acct([_pos("XAU", sign=1, position_value="100.0"),
                                  _pos("BTC", sign=-1, position_value="-100.0")]))
    assert st["gross"] == 200.0, (
        "opposite legs cancelled — a hedged book would publish zero exposure")


def test_unknown_equity_yields_unknown_leverage_never_zero():
    acct = {"positions": [_pos()]}          # no equity field at all
    st = margin_state_from(acct)
    assert st["equity"] is None
    assert st["leverage"] is None, "a dark equity read must not publish a ratio"


def test_no_position_values_means_unknown_gross_not_zero():
    st = margin_state_from(_acct([_pos(position_value="")]))
    assert st["gross"] is None and st["leverage"] is None


def test_positions_without_a_liq_price_are_CENSUSED_not_silently_dropped():
    """The (lv) rule: `{}` must not be byte-identical between 'all safe' and
    'nothing measured'."""
    st = margin_state_from(_acct([_pos("XAU", liquidation_price="4100"),
                                  _pos("BTC", liquidation_price="0")]))
    assert st["liq_unknown"] == ["BTC"]
    assert "liq" not in st["positions"]["BTC"]
    assert st["positions"]["XAU"]["liq"] == 4100.0


def test_the_liq_census_key_is_present_even_when_empty():
    st = margin_state_from(_acct([_pos("XAU", liquidation_price="4100")]))
    assert st["liq_unknown"] == [], "the key must publish empty, not vanish"


def test_distance_to_liquidation_needs_a_mark_and_is_never_invented():
    pos = [_pos("XAU", liquidation_price="4100.0")]
    without = margin_state_from(_acct(pos))
    assert "dist_pct" not in without["positions"]["XAU"]
    assert without["nearest_liq"] is None, "no mark -> no distance, no guess"

    with_mark = margin_state_from(_acct(pos), marks={"XAU": 3500.0})
    assert with_mark["positions"]["XAU"]["dist_pct"] == pytest.approx(
        abs(3500.0 - 4100.0) / 3500.0)
    assert with_mark["nearest_liq"]["coin"] == "XAU"


@pytest.mark.parametrize("junk", ["junk", "nan", "inf", [], {}, True])
def test_an_UNUSABLE_mark_yields_no_distance_rather_than_a_fake_one(junk):
    """The sharp version of the test above, and the one that catches the real
    bug. Passing NO marks skips the distance branch entirely, so it cannot
    detect a fallback INSIDE that branch — the mutation `m = _num(mark) or liq`
    survived the no-marks test and published `dist_pct: 0.0`, i.e. "this
    position is AT its liquidation price", from nothing but a junk mark.

    A mark we cannot parse must produce no distance at all."""
    st = margin_state_from(_acct([_pos("XAU", liquidation_price="4100.0")]),
                           marks={"XAU": junk})
    assert "dist_pct" not in st["positions"]["XAU"], (
        f"mark {junk!r} produced a distance; an unparseable mark must not "
        f"manufacture a liquidation reading")
    assert st["nearest_liq"] is None


def test_nearest_liq_picks_the_closest_position():
    st = margin_state_from(
        _acct([_pos("XAU", liquidation_price="110.0"),
               _pos("BTC", liquidation_price="200.0")]),
        marks={"XAU": 100.0, "BTC": 100.0})
    assert st["nearest_liq"]["coin"] == "XAU"          # 10% vs 100%


def test_mixed_margin_modes_are_reported_as_mixed():
    """Two modes on one account is a real state and must not collapse to
    whichever position happened to sort first."""
    st = margin_state_from(_acct([_pos("XAU", margin_mode=0),
                                  _pos("BTC", margin_mode=1)]))
    assert st["mode"] == "mixed"


def test_a_venue_that_cannot_answer_returns_None_not_a_default():
    """Shadow and paper arms hold no venue account. `None` is the honest
    answer; a base class returning 1.0 would publish a fabricated leverage on
    every shadow row."""
    assert VenueClient().margin_state() is None


# --------------------------------------------------------------------------
# the wiring — a read nobody publishes is a read nobody has
# --------------------------------------------------------------------------
def _calls_margin_block(path):
    """AST: does this module CALL _margin_block, and is the result placed in
    the published payload? A substring scan would match the explaining
    comment, which is how a wiring test passes against a bot that publishes
    nothing (CLAUDE.md; and it bit this session once already)."""
    tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    defined = any(isinstance(n, ast.FunctionDef) and n.name == "_margin_block"
                  for n in ast.walk(tree))
    called = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "_margin_block" for n in ast.walk(tree))
    # the call's value must land under a "margin" key of a dict literal
    published = False
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if (isinstance(k, ast.Constant) and k.value == "margin"
                    and isinstance(v, ast.Call)
                    and isinstance(v.func, ast.Name)
                    and v.func.id == "_margin_block"):
                published = True
    return defined, called, published


@pytest.mark.parametrize("path", LIVE_PUBLISHERS)
def test_every_live_book_publishes_the_venue_margin_state(path):
    defined, called, published = _calls_margin_block(path)
    assert defined, f"{path} has no _margin_block helper"
    assert called, f"{path} defines _margin_block but never calls it"
    assert published, (
        f"{path} calls _margin_block but its result never reaches the row's "
        f"'margin' key — an unpublished read answers nobody's question")


@pytest.mark.parametrize("path", LIVE_PUBLISHERS)
def test_the_margin_read_cannot_raise_into_a_trading_loop(path):
    """Telemetry that can stop a live loop is worse than the blind spot it
    closes. `_margin_block` must swallow everything."""
    tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_margin_block")
    handlers = [h for n in ast.walk(fn) if isinstance(n, ast.Try)
                for h in n.handlers]
    assert any(h.type is None
               or (isinstance(h.type, ast.Name) and h.type.id == "Exception")
               for h in handlers), (
        f"{path}:_margin_block does not catch broadly — a venue hiccup in a "
        f"telemetry read would propagate into the live trading loop")


# --------------------------------------------------------------------------
# the UNIT — confirmed against the venue's own margin tiers, not inferred
# --------------------------------------------------------------------------
# Measured 16-Aug from mainnet `orderBookDetails`, which publishes the margin
# tiers as INTEGER BASIS POINTS. Across 210 active books the nesting
# closeout <= maintenance <= min_imf <= default_imf held with ZERO violations,
# and the bps reading yields sane 3x-50x max-leverage tiers where a percent
# reading would imply 0.03x-0.2x. The position field is that value / 100, i.e.
# PERCENT — matched on 5 of 5 live positions across both real-money books
# (XAU 666->6.66, BTC 500->5.0, ADA/LTC/TRX 1000->10.0), 0 of 5 matching the
# min tier (so both books sit at the venue DEFAULT, which is what a fleet that
# never calls update_leverage should look like).
VENUE_DEFAULT_IMF_BPS = {"XAU": 666, "BTC": 500, "ADA": 1000, "LTC": 1000,
                         "TRX": 1000}


@pytest.mark.parametrize("coin,bps", sorted(VENUE_DEFAULT_IMF_BPS.items()))
def test_imf_is_published_as_PERCENT_matching_the_venue_tier(coin, bps):
    """The position field is the venue's basis-point tier / 100.

    Read as a 0-1 fraction it is wrong by 100x — the same unit class that gave
    this fleet an 8x-overstated funding APR. The name carries the unit so a
    consumer cannot make that mistake silently."""
    st = margin_state_from(_acct([_pos(coin, initial_margin_fraction=str(bps / 100))]))
    row = st["positions"][coin]
    assert row["imf_pct"] == pytest.approx(bps / 100)
    assert "imf" not in row, "the unit-free name is back; it reads as a fraction"
    # a 0-1 fraction would be <= 1 for every book on the venue; percent is not
    assert row["imf_pct"] > 1.0


@pytest.mark.parametrize("coin,bps", sorted(VENUE_DEFAULT_IMF_BPS.items()))
def test_max_leverage_is_derived_from_the_percent_tier(coin, bps):
    st = margin_state_from(_acct([_pos(coin, initial_margin_fraction=str(bps / 100))]))
    assert st["positions"][coin]["max_lev"] == pytest.approx(10000.0 / bps,
                                                             rel=1e-3)


def test_a_missing_or_zero_margin_tier_yields_no_max_leverage():
    """0 would divide-by-zero into an infinite 'leverage'; absent must stay
    absent rather than become unbounded."""
    for raw in ("0", "", "junk", None):
        st = margin_state_from(_acct([_pos("XAU", initial_margin_fraction=raw)]))
        assert "max_lev" not in st["positions"]["XAU"]


def test_an_accountless_client_makes_NO_venue_call_at_all():
    """A shadow arm builds LighterClient with with_signer=False, which leaves
    account_index None. Without an early refusal the read fires a real request
    with value="None" on every loop of every shadow book — governor budget and
    a warning line, forever, for an account that does not exist. `None` here
    must cost zero network calls, not one failed one."""
    import venues.lighter_client as lc

    called = []

    class _Accountless(lc.LighterClient):
        def __init__(self):                       # no venue, no signer, no net
            self.account_index = None

        def _account_payload(self):
            called.append(1)
            raise AssertionError("a venue call was made without an account")

    assert _Accountless().margin_state(marks={"XAU": 1.0}) is None
    assert called == [], "margin_state hit the venue with no account_index"


def test_the_client_read_costs_no_extra_market_calls():
    """One account payload in, everything derived from it. If this ever grows
    a per-symbol fetch it stops being free and starts competing with orders
    for the tx-budget governor."""
    import venues.lighter_client as lc
    src = open(os.path.join(ROOT, "venues/lighter_client.py"),
               encoding="utf-8").read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "margin_state_from")
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in ("orderbook", "candles", "mid",
                                          "funding_map", "_account_payload"), (
                f"margin_state_from calls {node.func.attr} — the derivation "
                f"must stay pure over the payload it is handed")
    assert callable(lc.margin_state_from)
