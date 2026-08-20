"""🎯 The young source's supply: the screen must ask the RIGHT question.

[2026-08-20 (sg)] `(lk)` put ONE instrument-class screen on the sniper's surge
AND young sources, justified on evidence that was almost entirely surge's:
non-crypto surge −$5.01 over 13 closes versus non-crypto **young −$1.19 over
TWO**. The young leg rested on n=2.

That screen asks `is_crypto`, i.e. `strategy_index == 2`. **The venue files
crypto-native memecoin debuts under class 7** — the same grab-bag that holds
tokenised pre-IPO equity (ANTHROPIC, OPENAI, SPCX) and a bond yield (US10Y).
So the screen refused precisely the cohort a debut sniper exists to trade.

MEASURED COST, 20-Aug: the young source published `admitted: 0` for 66
consecutive days. Its live supply that day was 7 books — 5 zero-volume ghosts
and exactly 2 with real turnover, CASHCAT and UNITREE, both class 7, both
refused. And the supply was never dead: on the venue-priced axis births run
1.67–2.00/30d and did not stop in any month measured (CAP Jun, ANSEM Jul,
CASHCAT Aug). The "86 days dry" figure in `(qi)`/`(sf)` is true of class 2 and
false of this book's cohort.

WHAT THESE TESTS PIN, in the order they matter:
1. The two sources ask DIFFERENT questions, and neither silently becomes the
   other. Surge stays crypto-only — its evidence is untouched and `(sf)`
   measured class-7 surge at −0.840%/trade, negative at every hold.
2. `venue_priced` admits crypto-native class-7 debuts and still refuses
   tokenised equity/FX/commodity/pre-IPO — the half of (lk) the tape supports
   (shorting an externally-priced debut measures t=−2.04).
3. The dark-scout fallback does NOT silently re-impose the old screen.
4. Both screens fail OPEN, and each reverts independently.
"""
import pathlib

import pytest

import fleet_bus
import lighter_perp_sniper as sniper

SRC = pathlib.Path(sniper.__file__).read_text()

# The venue's own classes, as published in `lighter-market.classes`.
CRYPTO, COMMODITY, FX, US_EQ, ASIA_EQ, EXOTIC = 2, 3, 4, 5, 6, 7


# ---------------------------------------------------------------- classifier
def test_venue_priced_admits_the_crypto_native_class_7_debuts():
    """The whole point: ANSEM and CASHCAT are class 7 and must be admitted."""
    for sym in ("ANSEM", "CASHCAT", "CAP"):
        assert fleet_bus.venue_priced(sym) is True, sym
        # ...and `is_crypto` still refuses them, correctly, for ITS question.
        assert fleet_bus.is_crypto(sym) is False, sym


def test_venue_priced_still_refuses_everything_priced_elsewhere():
    """The half of (lk) the tape supports — now at t=-2.04, not n=2."""
    for sym in ("ANTHROPIC", "OPENAI", "SPCX", "UNITREE", "US10Y", "MRNA"):
        assert fleet_bus.venue_priced(sym) is False, sym
    for sym in ("SPY", "QQQ", "USDKRW", "NZDUSD", "WHEAT", "XAU", "BOTZ"):
        assert fleet_bus.venue_priced(sym) is False, sym
    # the fleet's declared override outranks the venue here too: PAXG is a
    # metal price, and a metal is priced a long way from this book.
    assert fleet_bus.venue_priced("PAXG") is False


def test_venue_priced_with_a_LIVE_scout_splits_class_7_correctly(monkeypatch):
    """The live path, which the dark-scout fallback silently masks.

    Caught by mutation M7: removing ANTHROPIC from `EXOTIC_EXTERNALLY_PRICED`
    left every other test GREEN, because with no scout the fallback refuses it
    anyway via `NONCRYPTO_BASES`. In production the scout IS up, `_venue_class`
    returns 7, and 7 is not in `EXTERNALLY_PRICED_CLASSES` — so the name would
    be admitted. A guard that only ever runs the fallback cannot see that.
    """
    VENUE = {"ANSEM": 7, "CASHCAT": 7, "CAP": 7,          # crypto-native
             "ANTHROPIC": 7, "OPENAI": 7, "SPCX": 7,      # pre-IPO
             "UNITREE": 7, "CXMT": 7, "US10Y": 7, "MRNA": 7,
             "BTC": 2, "KAITO": 2, "NEWCOIN": 2,
             "SPY": 5, "BYD": 6, "WHEAT": 3, "USDKRW": 4}
    monkeypatch.setattr(fleet_bus, "_venue_class",
                        lambda sym, current_time=None: VENUE.get(sym))
    for sym in ("ANSEM", "CASHCAT", "CAP", "BTC", "KAITO", "NEWCOIN"):
        assert fleet_bus.venue_priced(sym) is True, f"{sym} should be admitted"
    for sym in ("ANTHROPIC", "OPENAI", "SPCX", "UNITREE", "CXMT", "US10Y",
                "MRNA", "SPY", "BYD", "WHEAT", "USDKRW"):
        assert fleet_bus.venue_priced(sym) is False, f"{sym} should be refused"
    # a class-7 name the fleet has never seen is admitted — the declared,
    # deliberate direction: starving the debut source is the worse error.
    monkeypatch.setattr(fleet_bus, "_venue_class",
                        lambda sym, current_time=None: 7)
    assert fleet_bus.venue_priced("BRANDNEWMEME") is True


def test_venue_priced_admits_ordinary_crypto():
    for sym in ("BTC", "ETH", "KAITO", "SOL"):
        assert fleet_bus.venue_priced(sym) is True, sym


def test_the_two_exotic_lists_cannot_drift_apart():
    """A name in both lists, or in neither, silently breaks the fallback.

    `_VENUE_PRICED_EXOTICS` is the dark-scout complement of
    `EXOTIC_EXTERNALLY_PRICED` inside class 7. If a future memecoin is added to
    one and forgotten in the other, `venue_priced` starts disagreeing with
    itself depending on whether the scout is up — the worst kind of bug,
    because it only appears during an outage.
    """
    overlap = fleet_bus._VENUE_PRICED_EXOTICS & fleet_bus.EXOTIC_EXTERNALLY_PRICED
    assert not overlap, f"a name is in BOTH exotic lists: {sorted(overlap)}"
    orphan = fleet_bus._VENUE_PRICED_EXOTICS - fleet_bus.NONCRYPTO_BASES
    assert not orphan, (
        f"{sorted(orphan)} is listed as a venue-priced exotic but is absent "
        f"from NONCRYPTO_BASES, so the subtraction that keeps the dark-scout "
        f"fallback from re-imposing the old screen does nothing for it")


def test_the_dark_scout_fallback_does_not_reimpose_the_old_screen():
    """With no scout, `venue_priced` must still admit the memecoins.

    This is the failure that would be invisible in normal running: the venue's
    `classes` map answers correctly while the scout is up, so a fallback that
    quietly reverts to `is_crypto` only starves the book during an outage.
    """
    assert fleet_bus._venue_class("CASHCAT") is None, (
        "this test is only meaningful with a dark scout; it is not dark")
    for sym in ("ANSEM", "CASHCAT", "CAP"):
        assert fleet_bus.venue_priced(sym) is True, sym
    for sym in ("ANTHROPIC", "UNITREE", "SPY"):
        assert fleet_bus.venue_priced(sym) is False, sym


@pytest.mark.parametrize("sym", ["", None, "  ", "UNKNOWNTOKEN", "X/USDC"])
def test_venue_priced_fails_open_and_never_raises(sym):
    """A classification outage must never be what stops a debut scan."""
    assert fleet_bus.venue_priced(sym) in (True, False)
    assert fleet_bus.venue_priced("ANSEM/USDC") is True   # quote split, as is_crypto
    assert fleet_bus.venue_priced("SPY/USDC") is False


# ------------------------------------------------------------- the two gates
def test_the_two_sources_ask_different_questions():
    """Surge and young must not share a screen — that WAS the defect."""
    assert sniper._class_ok is not sniper._young_class_ok
    # surge: crypto-only, unchanged, and still refusing the class-7 cohort
    # whose surge (sf) measured at -0.840%/trade
    assert sniper._class_ok("CASHCAT") is False
    assert sniper._class_ok("BTC") is True
    # young: priced-here, and therefore admitting it
    assert sniper._young_class_ok("CASHCAT") is True
    assert sniper._young_class_ok("BTC") is True
    assert sniper._young_class_ok("SPY") is False


def test_young_candidates_defaults_to_the_young_screen():
    """The default matters: the loop calls it with no `class_ok=`."""
    ages = {"CASHCAT": 3, "BTC": 3, "SPY": 3, "ANTHROPIC": 3}
    vols = {k: 9.0 for k in ages}
    got = sniper.young_candidates(ages, 21, vols, 0.25, set(), 9)
    assert "CASHCAT" in got, (
        "the young source is still refusing the class-7 debut cohort — the "
        "screen is not on the venue-priced axis")
    assert "BTC" in got
    assert "SPY" not in got and "ANTHROPIC" not in got


def test_surge_candidates_still_defaults_to_the_crypto_screen():
    """The surge screen's evidence is untouched; it must not widen with young."""
    surges = [{"sym": "CASHCAT", "ratio": 9.0}, {"sym": "BTC", "ratio": 9.0}]
    got = sniper.surge_candidates(surges, 3.0, set(), limit=9)
    assert got == ["BTC"], (
        f"the surge source admitted {got} — class-7 surge measures "
        f"-0.840%/trade at 6h and must stay refused")


def test_the_census_shows_where_the_young_source_now_dies():
    """The (sf) funnel and this fix are one mechanism: the census must move.

    Before the fix the live funnel read `class_ok=0` — the screen was the
    killing gate. After it, the screen passes and the volume floor becomes the
    binding one. A reader must be able to see that from the payload.
    """
    ages = {"CASHCAT": 3, "GHOST": 3, "SPY": 3}
    vols = {"CASHCAT": 0.45, "GHOST": 0.0, "SPY": 99.0}
    cen = {}
    got = sniper.young_candidates(ages, 21, vols, 0.25, set(), 9, census=cen)
    assert got == ["CASHCAT"], got
    assert cen["scanned"] == 3 and cen["age_ok"] == 3
    assert cen["class_ok"] == 2, cen      # CASHCAT + GHOST pass, SPY refused
    assert cen["vol_ok"] == 1, cen        # GHOST dies on the floor, not the screen


# ------------------------------------------------------------------ reverts
def test_each_screen_reverts_independently(monkeypatch):
    """Two switches, because they are two decisions.

    `SNIPER_ALLOW_NONCRYPTO` was the (lk) revert and still opens BOTH.
    `SNIPER_YOUNG_ALLOW_ANY` opens only the young source, so a future session
    can widen or close one without touching the other's evidence.
    """
    import importlib
    monkeypatch.setenv("SNIPER_YOUNG_ALLOW_ANY", "1")
    m = importlib.reload(sniper)
    try:
        assert m._young_class_ok("SPY") is True     # young opened
        assert m._class_ok("SPY") is False          # surge untouched
    finally:
        monkeypatch.delenv("SNIPER_YOUNG_ALLOW_ANY", raising=False)
        importlib.reload(sniper)

    monkeypatch.setenv("SNIPER_ALLOW_NONCRYPTO", "1")
    m = importlib.reload(sniper)
    try:
        assert m._class_ok("SPY") is True and m._young_class_ok("SPY") is True
    finally:
        monkeypatch.delenv("SNIPER_ALLOW_NONCRYPTO", raising=False)
        importlib.reload(sniper)
    assert sniper._class_ok("SPY") is False         # restored


def test_the_screen_change_is_declared_in_the_published_caps():
    """A gate the payload misdescribes is a gate nobody can audit ((go))."""
    assert '"class_screen"' in SRC
    # Match the KEY as published, not a bare substring: mutation M8 renamed the
    # key to `young_axis_hidden`, which CONTAINS "young_axis" and left a
    # substring check green — the "a page-wide substring scan is not a
    # structural claim" defect this repo has already paid for.
    import re
    for key in ("young_axis", "surge_axis"):
        assert re.search(rf'"{key}":\s*\(', SRC), (
            f"the payload no longer publishes `{key}` as a caps key; a reader "
            f"cannot tell which question that gate is asking")
    assert '"young_axis_hidden"' not in SRC
    # and the values must be the two axes, not a bare boolean
    assert '"venue_priced"' in SRC and '"is_crypto"' in SRC
