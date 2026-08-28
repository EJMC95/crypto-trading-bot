"""👩 mum's supply fix: the CAP was the constraint, and it must stay scoped.

[2026-08-28 (vd)] **Eamon: *"fix mums supply"* / *"increase to optimum slots
immediately and universe"* / *"allow her to see non crypto also just in
case"*.** mum went live 25-Aug and took ZERO trades in three days.

WHAT WAS MEASURED, 180d of her own rule at her own bracket, replayed at her
REAL cap (one position per coin, sequential, LAG-1):

    universe 13, slots  4  (as shipped)   t=1.14   1.58 trades/day
    universe 40, slots  4                 t=1.18   3.51/day   <- width alone: NOTHING
    universe 13, slots 12                 t=2.31   2.23/day
    universe 40, slots 12                 t=3.20   6.38/day   <- both

and the test that killed the PREVIOUS widening now passes: resampling WHICH
coins are graded (rule and slots fixed, 24 draws), 4 slots reaches t>=2.0 in
**2 of 24** draws and 12 slots in **24 of 24**, with the volume-ranked cell
INSIDE the spread. The slots carry it; slots are not a selected quantity.

THE THREE THINGS THIS FILE EXISTS TO STOP, each a real defect caught while
building it:

  1. **A SECOND COPY OF THE UNIVERSE RULE.** The shadow runner and the live
     variant host each built `COINS + NONCRYPTO_UNIVERSE` inline. Widening one
     would have left the other narrow — and for mum those two are the
     REAL-MONEY arm and the SHADOW twin that controls for it, so the arms
     would have silently stopped being comparable.

  2. **BLAST RADIUS.** The first cut widened the SHARED `NONCRYPTO_UNIVERSE`
     and took 🙏 avo from 25 names to 45 — a live book, the fleet's only
     profitable real-money arm, for which none of this was measured. Both
     widenings are per-carrier now, and this pins that.

  3. **A FAIL-SAFE POINTING THE WRONG WAY.** A dark or short scout read must
     never SHRINK a book's universe below its configured list — the
     `scout_universe` contract's own rule, and here the configured list is the
     set every prior measurement of this rule was made on.
"""
import ast
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_family_bot as fam                            # noqa: E402
import regime_oracle as ro                                  # noqa: E402

MUM = "freqtrade-mum"


def _s(bot):
    for s in fam.STRATEGIES:
        if s.bot == bot:
            return s
    raise AssertionError(f"{bot} not in STRATEGIES")


# ------------------------------------------------------------------- the cap
def test_mum_has_the_measured_slot_count():
    """12, not 4. The cap was the binding constraint (367 of 651 signals
    refused on her own coins), and 12 is the interior optimum inside the
    fleet's own long budget — NOT the unconstrained 30."""
    assert _s(MUM).max_open == 12


def test_more_slots_did_not_change_gross_exposure():
    """The (sr) arithmetic: `clip = equity * gross_x / max_open`, so slots
    SLICE a fixed gross rather than adding to it. Worst case is unchanged,
    which is the whole reason this is shippable on a live book."""
    equity, gross_x, stop = 300.0, 10.0, 0.04
    before = equity * gross_x / 4
    after = equity * gross_x / _s(MUM).max_open
    assert before * 4 == pytest.approx(after * _s(MUM).max_open)
    assert after * _s(MUM).max_open * stop == pytest.approx(before * 4 * stop)
    # And every slot must still be fundable under her declared notional cap.
    assert after * _s(MUM).max_open <= 3150.0


# --------------------------------------------------------------- one owner
def _names(node):
    """Every bare Name and `list(Name)` identifier inside an expression."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
    return out


def _rebuilds_universe(tree, owner="carrier_universe"):
    """AST: a `COINS + NONCRYPTO_UNIVERSE` concatenation OUTSIDE the owner.

    STRUCTURAL, not a substring — the first version of this test asserted the
    text was absent and failed on its own DOCSTRING, which is precisely the
    'a page-wide substring scan is not a structural claim' defect this repo
    already records three instances of. The prose describing the old code is
    supposed to survive; only the EXPRESSION must not.
    """
    owner_nodes = {id(x) for fn in ast.walk(tree)
                   if isinstance(fn, ast.FunctionDef) and fn.name == owner
                   for x in ast.walk(fn)}
    for n in ast.walk(tree):
        if not isinstance(n, ast.BinOp) or not isinstance(n.op, ast.Add):
            continue
        if id(n) in owner_nodes:
            continue                       # the one place allowed to build it
        ids = _names(n)
        if "COINS" in ids and "NONCRYPTO_UNIVERSE" in ids:
            return n.lineno
    return None


def test_both_hosts_resolve_the_universe_through_one_owner():
    """Each host must CALL `carrier_universe`, and neither may rebuild the
    concatenation inline again."""
    for mod in ("lighter_family_bot.py", "lighter_avo_live_bot.py"):
        tree = ast.parse((ROOT / mod).read_text())
        called = any(
            isinstance(n, ast.Call)
            and ((isinstance(n.func, ast.Name) and n.func.id == "carrier_universe")
                 or (isinstance(n.func, ast.Attribute)
                     and n.func.attr == "carrier_universe"))
            for n in ast.walk(tree))
        assert called, f"{mod} does not call carrier_universe()"
        line = _rebuilds_universe(tree)
        assert line is None, (
            f"{mod}:{line} rebuilds COINS + NONCRYPTO_UNIVERSE inline — "
            f"a second copy of the universe rule")


# ------------------------------------------------------------- blast radius
@pytest.mark.parametrize("bot", ["freqtrade-georgia"])
def test_the_widening_never_leaks_to_an_unmeasured_book(bot):
    """THE REGRESSION ARM. A supply fix for one book must not re-aim another —
    the first cut of this change silently widened 🙏 avo, who is live.

    [2026-08-28 (vd)] RE-AIMED, not relaxed. 🙏 avo is now widened ON PURPOSE
    (Eamon: *"widen what we know works"*) at her own stricter $0.5M floor, so
    she leaves this list. 🔮 georgia STAYS: (ux) measured `trend_breakout` —
    154 of her 212 real entries — DEAD against matched-random, and (uw) found
    no exit configuration rescues it. Widening a book whose dominant sleeve has
    no measured entry edge buys more no-edge trades (I19).

    The property this arm defends is unchanged: a widening reaches exactly the
    books somebody measured, and never leaks by default.
    """
    other, mum = _s(bot), _s(MUM)
    assert fam.crypto_width(bot) == 0, f"{bot} gained a crypto widening"
    assert fam.noncrypto_extra(bot) == [], f"{bot} gained non-crypto names"
    assert len(fam.carrier_universe(other)) < len(fam.carrier_universe(mum))


def test_mum_is_the_one_that_widened():
    # [2026-08-28 (vd)] 40 -> 200. The rank cap is no longer the SELECTOR — a
    # measured $0.1M/day volume floor is (see `crypto_min_vol_m`). This value
    # survives only as a safety bound on a scout glitch, so it is asserted as a
    # RANGE: pinning it to a literal again would re-impose the limit the floor
    # exists to replace.
    assert 120 <= fam.crypto_width(MUM) <= 400
    assert len(fam.noncrypto_extra(MUM)) >= 15
    u = fam.carrier_universe(_s(MUM))
    assert len(u) > len(fam.COINS) + len(fam.NONCRYPTO_UNIVERSE)


# ---------------------------------------------------------------- fail-safe
@pytest.mark.parametrize("scout", [[], None, ["BTC"], "junk", ["SPY", "QQQ"]])
def test_a_dark_or_short_scout_never_shrinks_the_universe(monkeypatch, scout):
    """Doubt keeps the CONFIGURED list. A universe that shrinks on an organ
    outage is the one direction this must never fail in."""
    import fleet_bus
    monkeypatch.setattr(fleet_bus, "scout_universe",
                        lambda *a, **k: scout, raising=False)
    u = fam.carrier_universe(_s(MUM))
    for c in fam.COINS:
        assert c in u, f"{c} dropped from mum's universe on a degraded scout"


def test_an_exception_in_the_scout_is_not_fatal(monkeypatch):
    import fleet_bus

    def boom(*a, **k):
        raise RuntimeError("scout down")
    monkeypatch.setattr(fleet_bus, "scout_universe", boom, raising=False)
    u = fam.carrier_universe(_s(MUM))
    assert all(c in u for c in fam.COINS)


def test_a_carrier_with_its_own_coins_is_untouched():
    """`s.coins` is an explicit pin (the spot ports use it) and must win."""
    class _Pinned:
        bot, coins = MUM, ["BTC", "ETH"]
    assert fam.carrier_universe(_Pinned()) == ["BTC", "ETH"]


# ------------------------------------------------- classification integrity
def test_the_two_noncrypto_sets_have_not_drifted():
    """`lighter_family_bot.NONCRYPTO_SYMS` and `regime_oracle.NONCRYPTO` gate
    and grade the same books. If they disagree, a name the classifier does not
    know is routed down the CRYPTO path and handed BTC's gate — the D5
    violation the whole per-asset build order exists to prevent."""
    assert fam.NONCRYPTO_SYMS == frozenset(ro.NONCRYPTO)


def test_every_added_name_is_classified_so_none_can_be_gated_as_crypto():
    unknown = [c for c in fam.noncrypto_extra(MUM)
               if c not in fam.NONCRYPTO_SYMS]
    assert unknown == [], (
        f"unclassified non-crypto would take BTC's regime gate: {unknown}")
    assert set(fam.noncrypto_extra(MUM)) <= fam.NONCRYPTO_EFFECTIVE


def test_seeing_is_not_trading_every_added_name_needs_its_own_grade():
    """The safety of the non-crypto half. The measured, UNGATED expectancy on
    the added set is negative (-0.179%/trade, by-coin t=-1.81), so what makes
    this shippable is that an ungraded book admits NOTHING. Assert the oracle
    would have to grade each name before any of them can trade."""
    for c in fam.noncrypto_extra(MUM):
        assert c in ro.NONCRYPTO, (
            f"{c} is scannable but the oracle will never grade it — it would "
            f"be permanently inert rather than gated")


# --------------------------------------------------------------- parsing
@pytest.mark.parametrize("raw,bot,want", [
    ("freqtrade-mum:40", MUM, 40),
    ("freqtrade-mum:40", "freqtrade-avo-maria", 0),
    ("", MUM, 0),
    ("freqtrade-mum:notanumber", MUM, 0),
    ("a:1,freqtrade-mum:25", MUM, 25),
    ("freqtrade-mum:-5", MUM, 0),
])
def test_crypto_width_parsing(raw, bot, want):
    assert fam.crypto_width(bot, raw) == want


@pytest.mark.parametrize("raw,bot,want", [
    ("freqtrade-mum:SPY,QQQ", MUM, ["SPY", "QQQ"]),
    ("freqtrade-mum:SPY,QQQ", "freqtrade-georgia", []),
    ("", MUM, []),
    ("freqtrade-georgia:IWM;freqtrade-mum:SPY", MUM, ["SPY"]),
])
def test_noncrypto_extra_parsing(raw, bot, want):
    assert fam.noncrypto_extra(bot, raw) == want


# ------------------------------------------- the rank cap becomes a vol floor
def test_the_crypto_floor_is_per_carrier_and_defaults_off():
    """[2026-08-28 (vd)] A floor that leaked onto another carrier would NARROW
    a book that never asked for one — the one direction a universe change must
    never move ((hk): a dark organ must not shrink a book's universe)."""
    assert fam.crypto_min_vol_m("freqtrade-mum") == pytest.approx(0.1)
    # avo carries her OWN floor (0.5) since (vd) and is asserted separately in
    # `test_avo_widened_at_a_stricter_floor_and_georgia_is_untouched`.
    for other in ("freqtrade-georgia",
                  "crypto-intraday-15m", "NEVER_SEEN", ""):
        assert fam.crypto_min_vol_m(other) == 0.0, (
            f"{other} must be unaffected — 0.0 means no floor")


@pytest.mark.parametrize("raw,expected", [
    ("freqtrade-mum:0.1", 0.1), ("freqtrade-mum:0", 0.0),
    ("a:1,freqtrade-mum:0.25,b:2", 0.25),
    ("freqtrade-mum:junk", 0.0), ("freqtrade-mum:-5", 0.0),
    ("", 0.0),
    # NOT (None, 0.0): `raw=None` means "read the module default", which is
    # 0.1 for mum. My first cut asserted 0.0 here and was simply wrong about
    # the function's own contract — the parametrisation caught it.
    (None, 0.1),
])
def test_the_floor_parses_junk_to_no_floor(raw, expected):
    """Fail OPEN: an unparseable env must mean NO floor, never a floor that
    silently deletes the universe."""
    assert fam.crypto_min_vol_m("freqtrade-mum", raw) == pytest.approx(expected)


def test_the_floor_actually_reaches_the_scout():
    """THE WIRING, not the constant. A floor computed and never passed is the
    registered-but-inert failure (I18) — and it is invisible, because the
    universe still looks plausible."""
    import ast
    src = (ROOT / "lighter_family_bot.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "carrier_universe")
    passed = False
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "scout_universe"):
            for kw in node.keywords:
                if kw.arg == "min_vol_m":
                    passed = True
    assert passed, (
        "carrier_universe calls scout_universe WITHOUT min_vol_m — the floor "
        "is computed and never applied")


def test_a_dark_scout_still_cannot_narrow_her():
    """The fail-safe the floor must not break: an empty/dark read returns the
    CONFIGURED list, never a shrunken one."""
    s = next(x for x in fam.live_strategies() if x.bot == "freqtrade-mum")
    uni = fam.carrier_universe(s)
    for major in ("BTC", "ETH", "SOL", "XRP", "ADA"):
        assert major in uni, f"{major} dropped from mum's universe"
    assert len(uni) >= len(fam.COINS)


def test_the_rank_bound_survives_as_a_safety_cap():
    """`FAMILY_CRYPTO_N` is no longer the selector but must still bound a
    scout glitch — 200 lets the floor bind while capping a runaway read."""
    n = fam.crypto_width("freqtrade-mum")
    assert n >= 120, "the rank bound must not re-impose the old limit"
    assert n <= 400, "an unbounded rank is a scout glitch with no ceiling"


def test_avo_widened_at_a_stricter_floor_and_georgia_is_untouched():
    """[2026-08-28 (vd)] Eamon: *"widen what we know works"*.

    🙏 avo joins the widening at $0.5M, not mum's $0.1M: she holds 3.5 DAYS
    against mum's 12h and clips $684 against $250, so a thinner book costs her
    more. WHAT IT BUYS IS DECIDABILITY, NOT EDGE — (qu) measured her entry's
    excess over matched-random as ~zero at 5d, where her hold lands — and her
    own pre-registered 50-close criterion is ~116 days away at 0.43 closes/day
    while she sits idle 38.7h with 2 of 5 slots free.

    🔮 georgia is deliberately NOT widened: (ux) measured `trend_breakout` —
    154 of her 212 real entries — DEAD against random, and (uw) found no exit
    configuration rescues it. Widening a book whose dominant sleeve has no
    measured entry edge buys more no-edge trades, which is the I19 trap.
    """
    assert fam.crypto_min_vol_m("freqtrade-avo-maria") == pytest.approx(0.5)
    assert fam.crypto_width("freqtrade-avo-maria") >= 120
    assert fam.crypto_min_vol_m("freqtrade-mum") == pytest.approx(0.1)
    assert fam.crypto_min_vol_m("freqtrade-georgia") == 0.0, (
        "georgia must stay unwidened — her dominant sleeve is measured DEAD")
    assert fam.crypto_width("freqtrade-georgia") == 0


def test_avos_floor_is_stricter_than_mums():
    """The ordering IS the argument — a longer hold at a bigger clip needs a
    deeper book. If these ever equalise, one of them was set without reason."""
    assert (fam.crypto_min_vol_m("freqtrade-avo-maria")
            > fam.crypto_min_vol_m("freqtrade-mum")), (
        "avo holds 7x longer at 2.7x the clip and must not sit on a thinner "
        "floor than mum")
