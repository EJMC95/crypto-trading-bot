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
import json
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
    # [2026-08-25] SDK-aware, like its sibling test above: without the
    # `lighter` SDK the name map is deliberately EMPTY and the mode degrades
    # to the raw code (I8) — asserting "cross" unconditionally made this test
    # red in any container without the SDK while the code behaved exactly as
    # designed.
    try:
        import lighter  # noqa: F401
        assert st["mode"] == "cross"
    except ImportError:
        assert st["mode"] == 0, st
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
    assert "dist_frac" not in without["positions"]["XAU"]
    assert without["nearest_liq"] is None, "no mark -> no distance, no guess"

    with_mark = margin_state_from(_acct(pos), marks={"XAU": 3500.0})
    assert with_mark["positions"]["XAU"]["dist_frac"] == pytest.approx(
        abs(3500.0 - 4100.0) / 3500.0)
    assert with_mark["nearest_liq"]["coin"] == "XAU"


@pytest.mark.parametrize("junk", ["junk", "nan", "inf", [], {}, True])
def test_an_UNUSABLE_mark_yields_no_distance_rather_than_a_fake_one(junk):
    """The sharp version of the test above, and the one that catches the real
    bug. Passing NO marks skips the distance branch entirely, so it cannot
    detect a fallback INSIDE that branch — the mutation `m = _num(mark) or liq`
    survived the no-marks test and published `dist_frac: 0.0`, i.e. "this
    position is AT its liquidation price", from nothing but a junk mark.

    A mark we cannot parse must produce no distance at all."""
    st = margin_state_from(_acct([_pos("XAU", liquidation_price="4100.0")]),
                           marks={"XAU": junk})
    assert "dist_frac" not in st["positions"]["XAU"], (
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
    # the call's value must land under a "margin" key of a dict literal —
    # either directly, or [(th)] through a name assigned from the call (the
    # variant host hoists the read to `_mstate` so the SAME venue state feeds
    # both the `margin` block and the headroom verdict; two reads could
    # disagree about one account). The name set is built first so a "margin"
    # key holding an unrelated name still fails.
    assigned = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "_margin_block"):
            assigned.update(t.id for t in n.targets
                            if isinstance(t, ast.Name))
    published = False
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if not (isinstance(k, ast.Constant) and k.value == "margin"):
                continue
            if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name)
                    and v.func.id == "_margin_block"):
                published = True
            if isinstance(v, ast.Name) and v.id in assigned:
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


# --------------------------------------------------------------------------
# the PRICE SOURCE — a risk number may not be computed off a frozen price
# --------------------------------------------------------------------------
@pytest.mark.parametrize("path", LIVE_PUBLISHERS)
def test_margin_marks_come_from_the_live_book_not_the_funding_map(path):
    """`dist_frac` / `nearest_liq` are RISK numbers.

    `funding_map()[coin]["mark"]` is `LighterClient.markets[sym]["last"]`,
    captured by `_load_markets()` at CLIENT CONSTRUCTION and refreshed only by
    `refresh_markets()` — which only lighter_perp_sniper calls. Both live bots
    build their venue context once outside the loop, so that mark is frozen
    for the container's lifetime and its error GROWS WITH UPTIME. The first
    cut of `_margin_block` used it anyway, against venues/marks.py's own
    header. The sanctioned source is marks.stop_marks / fresh_mid.
    """
    tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_margin_block")

    uses_sanctioned = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("stop_marks", "fresh_mid", "mid_map")
        for n in ast.walk(fn))
    assert uses_sanctioned, (
        f"{path}:_margin_block does not source marks from venues.marks — a "
        f"liquidation distance off a stale price is a silent risk defect")

    # and it must not reach for the frozen sources at all
    for n in ast.walk(fn):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            assert n.value not in ("mark", "last", "last_px"), (
                f"{path}:_margin_block still reads a {n.value!r} field — that "
                f"is the boot-frozen funding/last price, not a live mid")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            assert n.func.attr != "funding_map", (
                f"{path}:_margin_block calls funding_map for prices")


def test_the_venue_entry_price_is_published_so_the_model_can_be_CHECKED():
    """Without the venue's own avg_entry_price the published block cannot be
    verified against any margin model — and an unverifiable risk read invites
    exactly the circular 'calibration' that shipped in this file's first
    version (invert liq_price, feed the result back through liq_price, marvel
    at 0.000000%)."""
    st = margin_state_from(_acct([_pos("XAU", avg_entry_price="4385.65")]))
    assert st["positions"]["XAU"]["entry"] == pytest.approx(4385.65)


def test_a_real_calibration_can_FAIL(monkeypatch):
    """The check the circular one should have been: take the venue's OWN entry
    and its OWN liq, run the model forward, compare. Independent inputs, so a
    wrong leverage or a wrong mmf moves the answer."""
    mm = pytest.importorskip("importlib").import_module
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    M = mm("lighter_margin_model")

    entry, L, mmf = 4385.65, 0.1532, 0.0240
    liq = M.liq_price(entry, is_long=False, leverage=L, mmf=mmf)
    # forward agreement with an independent entry is meaningful...
    assert M.liq_price(entry, False, L, mmf) == pytest.approx(liq)
    # ...and unlike the circular form, wrong inputs now MOVE the answer
    assert M.liq_price(entry, False, 9.9, mmf) != pytest.approx(liq, rel=1e-6)
    assert M.liq_price(entry, False, L, 0.9) != pytest.approx(liq, rel=1e-6)
    # the structural claim that DID survive: a <=1x long has no liq price
    assert M.liq_price(entry, True, 0.999, mmf) == 0.0
    assert M.liq_price(entry, True, 2.0, mmf) > 0.0


def test_the_liquidation_distance_names_its_own_unit():
    """`dist_frac` is a FRACTION (XAU reads 6.35, i.e. 635%). It shipped one
    commit as `dist_pct` — in the very payload where `imf` had just become
    `imf_pct` to stop this. A `_pct` name on a ratio is the same 100x class."""
    st = margin_state_from(
        _acct([_pos("XAU", liquidation_price="200.0")]), marks={"XAU": 100.0})
    row = st["positions"]["XAU"]
    assert row["dist_frac"] == pytest.approx(1.0)      # 200 vs 100 = 1.0, not 100
    assert "dist_pct" not in row, "a ratio is published under a _pct name again"
    assert "dist_pct" not in (st["nearest_liq"] or {})
    assert st["nearest_liq"]["dist_frac"] == pytest.approx(1.0)


def test_avo_reads_ONLY_its_own_clip_arm_no_shared_fallback():
    """THE BRIDGE IS CLOSED. `_clip_scale_now` shipped with a fallback to the
    shared `live.clip_scale` so the (nj) rollout had no protection gap. That
    was right for the deploy window and wrong after it: in the steady state
    the own arm is ABSENT on every read, so the fallback fires and the
    Farmer's dial steers Avo again the moment the board restricts it — the
    exact coupling (nj) removed. A bridge with no expiry is the old behaviour
    with extra steps.

    Serve ONLY the shared lever and Avo must ignore it."""
    import lighter_avo_live_bot as avo
    import fleet_tuning as tuning

    served = {}

    def fake_get_lever(name, default, *a, **k):
        return served.get(name, default)

    orig = tuning.get_lever
    try:
        tuning.get_lever = fake_get_lever
        served.clear()
        served["live.clip_scale"] = 0.5          # the FARMER's arm, restricted
        assert avo._clip_scale_now() == 1.0, (
            "Avo followed the shared lever — it is still steered by the other "
            "book's evidence, which is the defect (nj) exists to remove")
        served["live.avo.clip_scale"] = 0.75     # its OWN arm
        assert avo._clip_scale_now() == 0.75, "Avo ignored its own arm"
    finally:
        tuning.get_lever = orig


def test_size_is_published_SIGNED_so_the_block_carries_direction():
    """`size` closes two gaps at once.

    MAGNITUDE: the forward-verified leverage basis is (|size| x entry) /
    collateral — an ENTRY-based notional. `value` is the venue's MARK-based
    number, so it is the wrong input, and deriving size as value/mark fails
    exactly when the mark is blind.

    DIRECTION: `liq_price` takes `is_long` and its branches differ, yet before
    this the margin block could not say whether a position was long or short.
    A consumer had to leave the block for a per-bot field (the Farmer's
    `held: {"XAU": "S"}`) to run the model at all."""
    st = margin_state_from(_acct([_pos("XAU", sign=-1, position="0.0069"),
                                  _pos("BTC", sign=1, position="0.5")]))
    assert st["positions"]["XAU"]["size"] == pytest.approx(-0.0069), \
        "a short must publish a NEGATIVE size — the block lost direction"
    assert st["positions"]["BTC"]["size"] == pytest.approx(0.5)


def test_the_forward_venue_calibration_holds_on_observed_inputs():
    """The real venue calibration, on 💸 the Farmer's XAU short, 16-Aug.

    Every input was MEASURED, none derived from the target — which is the
    whole difference from the circular version this replaces.

    IT IS NOT A PAYLOAD-SUFFICIENCY CLAIM, and the first draft of this test
    was named as though it were ("...the published block alone..."). Four of
    the five inputs come from the block — `entry`, `size`, `liq` (the target)
    and account-level `collateral`. The fifth, `mmf`, is the MARKET-level
    `maintenance_margin_fraction` from /api/v1/orderBookDetails and is NOT in
    the block. It is also NOT derivable from what is: the block's `imf_pct` is
    the INITIAL margin fraction (XAU 6.66), and the tempting `0.6 × imf_pct`
    gives 0.0400 against a true 0.0240 — wrong by 66%, which feeds through to
    a −1.540% liq error, larger than the entire error this calibration exists
    to have fixed. Read `mmf` per book; never derive it.

    The forward inputs stay literal on purpose: routing them through a fixture
    would replace observed venue numbers with derived ones and reintroduce the
    exact circularity the retraction in lighter_margin_model.py exists to
    prevent."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    M = pytest.importorskip("lighter_margin_model")

    entry, collateral, mmf = 4339.72, 197.843218, 0.024
    size = -0.00690010                      # SHORT: the sign is the direction
    venue_liq = 32238.9162

    # couple it to the projection, so dropping `size`/`entry`/`liq` from the
    # row reddens THIS test too rather than only its sibling
    st = margin_state_from(_acct([_pos("XAU", sign=-1, position="0.00690010",
                                       avg_entry_price=str(entry),
                                       liquidation_price=str(venue_liq))],
                                 equity=str(collateral)))
    row = st["positions"]["XAU"]
    assert row["size"] == pytest.approx(size)
    assert row["entry"] == pytest.approx(entry)
    assert row["liq"] == pytest.approx(venue_liq)

    lev = abs(size) * entry / collateral    # the verified basis
    pred = M.liq_price(entry, is_long=size > 0, leverage=lev, mmf=mmf)
    assert abs(pred - venue_liq) / venue_liq < 1e-4, (
        f"predicted {pred:.2f} vs venue {venue_liq:.2f}")

    # the two substitutions this finding rests on must each still MATTER,
    # or the pin has stopped defending the result and only guards the algebra
    mark_based = M.liq_price(entry, size > 0, 30.2703 / collateral, mmf)
    assert abs(mark_based - venue_liq) / venue_liq > 5e-3, \
        "mark-based notional no longer diverges — the pin went vacuous"


def test_mmf_is_absent_from_the_block_and_not_derivable_from_imf():
    """Pin the GAP so nobody advertises the block as self-sufficient.

    A consumer needs `mmf` to run liq_price, and it is not here. The failure
    mode is not noticing — it is deriving it from `imf_pct`, which is a
    different tier and plausible enough to ship."""
    st = margin_state_from(_acct([_pos("XAU")]))
    assert "mmf" not in json.dumps(st), \
        "mmf now publishes — update the docs that say the block lacks it"
    row = st["positions"]["XAU"]
    assert "imf_pct" in row and "max_lev" in row
    # the trap, with the venue's real XAU numbers
    true_mmf, derived = 0.0240, 0.6 * 0.0666
    assert abs(derived - true_mmf) / true_mmf > 0.5, \
        "0.6 x imf is no longer badly wrong — re-check the tier relationship"


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
