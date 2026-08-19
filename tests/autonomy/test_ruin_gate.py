"""[2026-08-19 (qz)] THE FLEET COULD WATCH ITSELF APPROACH LIQUIDATION AND HAD
NOTHING THAT WOULD DECLINE.

`(no)` wired the venue's OWN margining truth into the live path — per-position
`liquidation_price`, the distance to the nearest one, and a census of
positions the venue will not price — and both live bots publish it.
`scripts/lighter_margin_model` then modelled the same thing for hypothetical
positions and validated it forward to **0.001%** against the venue, carrying a
`headroom_x` helper whose docstring names the refusal bar (K=4). And nothing
refused: `headroom_x`'s only declared consumer was ⚡ High Voltage, a book that
was REFUTED and never built, so the criterion shipped orphaned. `SafetyRails` —
the one gate real money passes through — knew a notional cap and a daily-loss
cap, neither of which can see liquidation. That is I18's registered-but-inert
shape landing on the single number a leverage decision depends on.

WHY STOP-WIDTHS. A stop is the loss the book has already accepted; liquidation
is the loss it cannot survive. Measured on the validated model, for 💸 the
Farmer's shipped 10% HARD_STOP:

    L=2  -> 4.94x headroom (it runs here)   L=3  -> 3.25x  refused
    L=5  -> 1.90x refused                   L=10 -> 0.89x  LIQUIDATES FIRST

The live book sits one notch under its own ceiling — reached by luck, since
nothing computed this — and five notches from the regime where the stop is
decorative because liquidation fires first. Leverage capacity is a property of
STOP DISTANCE, not appetite.

EVERY FIXTURE HERE IS BUILT BY THE PUBLISHER (`margin_state_from`) from a
venue-shaped account payload with STRING numerics, never hand-written — the
rule that caught four consumer/publisher mismatches in one session ((hj)).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from venues.lighter_client import margin_state_from            # noqa: E402
from venues.safety import SafetyRails, LIQ_HEADROOM_K          # noqa: E402

pytestmark = pytest.mark.autonomy


def _pos(symbol="XAU", **kw):
    """The venue's own shape — every numeric a STRING, as AccountPosition
    declares. A float fixture would quietly pass a parser that mishandles
    strings, which is the failure `(no)` exists to prevent."""
    row = {"symbol": symbol, "sign": 1, "position": "1.0",
           "avg_entry_price": "100.0", "position_value": "100.0",
           "unrealized_pnl": "0.0", "liquidation_price": "50.0",
           "initial_margin_fraction": "0.1", "allocated_margin": "10.0",
           "margin_mode": 0}
    row.update(kw)
    return row


def _state(positions, marks, equity="197.52"):
    """PUBLISHER-BUILT margin state — never a hand-written dict."""
    return margin_state_from(
        {"total_asset_value": equity, "collateral": equity,
         "positions": positions}, marks=marks)


def _rails(live=True):
    return SafetyRails("perps-funding-lighter",
                       "lighter_live" if live else "lighter_shadow")


# ---------------------------------------------------------------------------
# the arithmetic the gate exists to enforce
# ---------------------------------------------------------------------------

def test_a_comfortable_distance_is_allowed():
    """liq at 50 against a mark of 100 = 50% away; a 10% stop needs 40%."""
    st = _state([_pos(liquidation_price="50.0")], {"XAU": 100.0})
    assert st["nearest_liq"]["dist_frac"] == pytest.approx(0.5)
    assert _rails().headroom_check(st, 0.10)[0] is True


def test_inside_the_bar_is_refused():
    """liq at 70 = 30% away; a 10% stop needs 40%. This is the L=3 cell."""
    st = _state([_pos(liquidation_price="70.0")], {"XAU": 100.0})
    assert st["nearest_liq"]["dist_frac"] == pytest.approx(0.30)
    assert _rails().headroom_check(st, 0.10)[0] is False


def test_the_boundary_is_inclusive_and_is_K_stop_widths():
    """Exactly K stop-widths passes; a hair under does not — and the bar is
    K itself, so changing the constant moves the gate rather than a literal."""
    st = _state([_pos(liquidation_price="60.0")], {"XAU": 100.0})
    assert st["nearest_liq"]["dist_frac"] == pytest.approx(0.40)
    assert _rails().headroom_check(st, 0.40 / LIQ_HEADROOM_K)[0] is True
    assert _rails().headroom_check(st, (0.40 / LIQ_HEADROOM_K) * 1.001)[0] is False


def test_a_tighter_stop_buys_leverage():
    """The finding, as a test: the SAME dangerous distance that refuses a 10%
    stop is fine for a 3% one. Leverage capacity follows stop distance."""
    st = _state([_pos(liquidation_price="80.0")], {"XAU": 100.0})   # 20% away
    assert _rails().headroom_check(st, 0.10)[0] is False
    assert _rails().headroom_check(st, 0.03)[0] is True


def test_the_nearest_position_governs_not_the_average():
    """Two positions, one safe and one nearly dead: the gate must read the
    NEAREST. An average would let a comfortable leg mask a dying one."""
    st = _state([_pos("XAU", liquidation_price="50.0"),
                 _pos("BTC", liquidation_price="97.0")],
                {"XAU": 100.0, "BTC": 100.0})
    assert st["nearest_liq"]["coin"] == "BTC"
    assert _rails().headroom_check(st, 0.10)[0] is False


# ---------------------------------------------------------------------------
# fail-CLOSED — the direction that is the opposite of every other rail here
# ---------------------------------------------------------------------------

def test_a_position_the_venue_will_not_price_refuses():
    """`liq_unknown` is the census `(no)` publishes precisely so 'measured and
    safe' is never byte-identical to 'not measured'. Holding a position whose
    death price is unpublished must REFUSE, not shrug."""
    st = _state([_pos("XAU", liquidation_price="50.0"),
                 _pos("BTC", sign=-1, liquidation_price=None)],
                {"XAU": 100.0, "BTC": 100.0})
    assert st["liq_unknown"] == ["BTC"]
    # A SHORT is never bounded — its loss grows without limit as price rises —
    # so it stays in the refusing set. [(rb)] made this fixture a short on
    # purpose: as a LONG at 1.0 x 100 against 197.52 of collateral it is
    # PROVABLY unliquidatable and the refusal would be the I7 failure, which is
    # the defect this file's `liq_none` tests now pin from the other side.
    ok, why = _rails().headroom_check(st, 0.10)
    assert ok is False and why == "liq_unpriced", why


def test_positions_held_but_none_priced_refuses():
    """No marks supplied -> no `dist_frac` anywhere -> nothing measured. The
    account is NOT flat, so this is ignorance, not safety."""
    st = _state([_pos(liquidation_price="50.0")], marks=None)
    assert st["n"] == 1 and st["nearest_liq"] is None
    assert _rails().headroom_check(st, 0.10)[0] is False


def test_an_unreadable_margin_state_refuses():
    for bad in (None, {}, [], "nope", 0):
        assert _rails().headroom_check(bad, 0.10)[0] is False, bad


def test_an_unknown_stop_refuses():
    """Headroom is undefined without a stop, and undefined must not read as
    permitted — the I8 unknown-degrading-to-a-guess failure, on a risk number."""
    st = _state([_pos(liquidation_price="50.0")], {"XAU": 100.0})
    for bad in (None, 0, 0.0, -0.10, "wide", float("nan"), float("inf")):
        assert _rails().headroom_check(st, bad)[0] is False, bad


def test_a_flat_book_is_allowed():
    """Nothing open cannot be liquidated — the one permissive case, and it
    must be reachable or the book could never take its FIRST position."""
    st = _state([], {"XAU": 100.0})
    assert st["n"] == 0
    assert _rails().headroom_check(st, 0.10)[0] is True


def test_a_shadow_arm_is_unaffected():
    """A paper book holds no venue account, so there is nothing to liquidate.
    Same live-only scoping as `daily_loss_hit` — and a shadow book must never
    be idled by a rail about real money."""
    assert _rails(live=False).headroom_check(None, None)[0] is True
    assert _rails(live=False).headroom_check({}, 0.10)[0] is True


# ---------------------------------------------------------------------------
# THE WIRING. A gate nobody calls is the registered-but-inert failure this
# whole file exists to close — one level up. The first mutation round proved
# it: `if RUIN_GATE and not dry_run:` -> `if False:` SURVIVED, because
# everything above tests the PREDICATE and nothing tested the CALL.
#
# AST for the call site, and stated honestly: AST sees identifiers in shapes,
# not values or bindings ((qy) drove seven survivors through exactly that), so
# the env contract below is driven behaviourally instead.
# ---------------------------------------------------------------------------

import ast          # noqa: E402
import importlib    # noqa: E402
import pathlib      # noqa: E402

import lighter_funding_bot as farmer                      # noqa: E402


def _farmer_main():
    tree = ast.parse(pathlib.Path(farmer.__file__).read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_the_live_farmer_actually_consults_the_gate():
    """Mutation that reddens this: `if RUIN_GATE and not dry_run:` -> `if
    False:`, or deleting the call. Both leave the money ungated."""
    calls = {c.func.attr for c in ast.walk(_farmer_main())
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
    assert "headroom_check" in calls, (
        "the Farmer's entry site no longer consults the ruin gate — the "
        "venue's liquidation price is read and published, and nothing "
        "refuses on it again")


def test_the_gate_is_guarded_by_its_kill_switch_and_skips_the_entry():
    """The refusal must `continue` past the open, not merely log. A gate that
    warns and then opens the position is the (gl) warning-is-not-a-guard
    failure with real money behind it."""
    for node in ast.walk(_farmer_main()):
        if not isinstance(node, ast.If):
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if "RUIN_GATE" not in names:
            continue
        assert any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                   and c.func.attr == "headroom_check" for c in ast.walk(node)), (
            "the RUIN_GATE branch does not call headroom_check")
        assert any(isinstance(n, ast.Continue) for n in ast.walk(node)), (
            "the ruin gate warns without skipping the entry")
        return
    raise AssertionError("no `if RUIN_GATE ...:` branch in the Farmer's main()")


def test_the_kill_switch_is_real(monkeypatch):
    """Behavioural, not structural: the env must actually reach the flag, and
    `on` must be the default. Every gate in this fleet ships with a way out."""
    try:
        monkeypatch.setenv("LIGHTER_RUIN_GATE", "off")
        importlib.reload(farmer)
        assert farmer.RUIN_GATE is False
    finally:
        monkeypatch.delenv("LIGHTER_RUIN_GATE", raising=False)
        importlib.reload(farmer)
    assert farmer.RUIN_GATE is True, "the ruin gate must default to ON"


def test_the_row_publishes_the_gate_s_bite():
    """`ruin_skips` on the row every loop, `0` included — an omitted key is
    byte-identical between 'never fired' and 'not running' ((lv)), and a gate
    silently declining every entry would look exactly like a quiet market."""
    src = pathlib.Path(farmer.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    published = any(
        isinstance(n, ast.Dict)
        and any(isinstance(k, ast.Constant) and k.value == "ruin_skips"
                for k in n.keys)
        for n in ast.walk(tree))
    assert published, (
        "the row no longer publishes ruin_skips — the gate's bite would be "
        "visible only in container logs")


# ---------------------------------------------------------------------------
# [2026-08-19 (rb)] THE TWO DEFECTS THE LIVE PAYLOAD EXPOSED, pinned from both
# sides. Neither was hypothetical: 🙏 Avo LIVE was measured holding 4 positions
# with `liq_unknown: [ADA, NVDA, QQQ, SPY]` and `nearest_liq: null`, and a
# venue-wide control group (443 open positions across 110 accounts) put the
# rule beyond doubt — cross SHORTS publish a liq 145/145, while 0 of 140 cross
# longs below 0.30x of collateral do.
# ---------------------------------------------------------------------------

def test_a_provably_unliquidatable_long_does_not_refuse():
    """I7: a trigger a book satisfies STRUCTURALLY is not a measurement.

    A long whose entry notional does not exceed its collateral cannot be
    liquidated — at a price of zero the account still stands — so the venue
    publishes no liq price. The FIRST cut of this gate read that, the safest
    position class in the fleet, as the most dangerous state it could see, and
    would have refused every entry on 🙏 Avo forever."""
    st = _state([_pos("ADA", position="1.0", avg_entry_price="100.0",
                      liquidation_price=None)],
                {"ADA": 100.0})
    assert st["liq_unknown"] == ["ADA"]
    assert st["liq_none"] == ["ADA"], "the block must PROVE it, not assume it"
    ok, why = _rails().headroom_check(st, 0.10)
    assert ok is True and why == "unliquidatable", why


def test_an_over_leveraged_long_with_no_liq_still_refuses():
    """The bounded proof is a DERIVATION, not a blanket long exemption: past 1x
    of collateral a long CAN be liquidated, so an absent liq there is a real
    unknown and must keep refusing."""
    st = _state([_pos("ADA", position="10.0", avg_entry_price="100.0",
                      liquidation_price=None)],
                {"ADA": 100.0})
    assert st["liq_unknown"] == ["ADA"]
    assert st["liq_none"] == [], "1000 of notional against 197.52 is not bounded"
    ok, why = _rails().headroom_check(st, 0.10)
    assert ok is False and why == "liq_unpriced", why


def test_a_bounded_long_beside_a_close_short_still_measures_the_short():
    """The exemption must not swallow the book. A proven-safe long sitting
    beside a genuinely endangered position must not stop the gate seeing it."""
    st = _state([_pos("ADA", position="1.0", avg_entry_price="100.0",
                      liquidation_price=None),
                 _pos("XAU", sign=-1, liquidation_price="103.0")],
                {"ADA": 100.0, "XAU": 100.0})
    # The SHORT makes the account unbounded, so nothing earns the exemption —
    # the conservative direction, and the reason the derivation is account-level
    # rather than per-position: under cross margin the legs share collateral.
    assert st["liq_none"] == []
    ok, why = _rails().headroom_check(st, 0.10)     # 3% away, bar is 40%
    assert ok is False and why == "too_close", (
        "a MEASURED position inside the bar must outrank a bookkeeping refusal "
        "— the operator's next action differs completely")


def test_a_priced_position_with_a_blind_mark_refuses():
    """THE FAIL-OPEN HOLE, reproduced before it was closed.

    A position the venue DID price whose order book is unreadable matched
    neither arm of the publisher's branch: absent from `liq_unknown` AND absent
    from `priced`, so it dropped silently out of `min(priced)`. The gate then
    reported the safest REMAINING position and allowed more notional while that
    one sat 3% from its liquidation. Measured before the fix: XAU liq 50 (50%
    away, mark readable) + BTC liq 97 (3% away, mark blind) returned True."""
    st = _state([_pos("XAU", liquidation_price="50.0"),
                 _pos("BTC", liquidation_price="97.0")],
                {"XAU": 100.0})                     # BTC mark deliberately absent
    assert st["liq_unknown"] == [], "BTC IS priced — this is not that class"
    assert st["liq_mark_blind"] == ["BTC"], "the blind position must be named"
    ok, why = _rails().headroom_check(st, 0.10)
    assert ok is False and why == "mark_blind", why


def test_every_refusal_names_a_distinct_reason():
    """I18: the operator cannot act on a bare count. `liq_unpriced` means
    investigate the venue read; `too_close` means de-lever NOW. Seven branches
    collapsing to one False is the (lv) `{open: 0}` shape."""
    seen = {}
    seen["state_unreadable"] = _rails().headroom_check(None, 0.10)
    seen["stop_unreadable"] = _rails().headroom_check(
        _state([_pos()], {"XAU": 100.0}), None)
    seen["liq_unpriced"] = _rails().headroom_check(
        _state([_pos("BTC", sign=-1, liquidation_price=None)], {"BTC": 100.0}), 0.10)
    seen["mark_blind"] = _rails().headroom_check(
        _state([_pos("BTC", liquidation_price="97.0")], {}), 0.10)
    seen["too_close"] = _rails().headroom_check(
        _state([_pos(liquidation_price="97.0")], {"XAU": 100.0}), 0.10)
    for want, (ok, why) in seen.items():
        assert ok is False, (want, why)
        assert why == want, f"expected reason {want!r}, got {why!r}"
    assert len(set(seen)) == len(seen)


def test_the_allowing_reasons_are_distinct_too():
    """`flat`, `unliquidatable`, `ok` and `not_live` all allow — for entirely
    different reasons, and a row that cannot tell them apart cannot tell a
    healthy book from one the gate is structurally blind to."""
    assert _rails(live=False).headroom_check({}, 0.10) == (True, "not_live")
    assert _rails().headroom_check(_state([], {}), 0.10) == (True, "flat")
    assert _rails().headroom_check(
        _state([_pos(liquidation_price="50.0")], {"XAU": 100.0}), 0.10) == (True, "ok")
