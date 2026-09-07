"""[(yk)] THE FLEET RECORDS EVIDENCE IN ONE SPELLING AND LOOKS IT UP IN ANOTHER.

This venue lists thousand-denominated memecoins as `1000BONK` / `1000PEPE` /
`1000SHIB` / `1000FLOKI`; the fleet's own universes and ledgers spell the same
market `kBONK`, and `venues/symbol_map` is the ONE mapping between them.

`market_context.coin_quality_fold` canonicalises to the FLEET form on purpose —
that fold exists so a coin's evidence pools across both writers — so
`coin-quality` and the `coin-vetoes` it feeds are keyed `kBONK`. Every LIVE
consumer then looks the coin up under the spelling it actually scans, which is
the venue's, because `fleet_bus.scout_universe()` returns the venue's list.

**MEASURED 6-Sep on 👩 mum's LIVE, REAL-MONEY 110-name universe: four
1000-markets sit at crypto ranks 37 / 46 / 63 / 86** — inside her scan — and
the coin-quality veto was structurally unable to fire on any of them. The same
miss made `recorded_cost_bps` return "unmeasured" for exactly the four coins
whose slippage is worst, and left the event sentinel's `meme` sector empty on
the only venue the fleet trades.

🎫 the taker had already fixed this AT ITS OWN SITE, with a local
`_fleet(base) or base` test and a comment naming "all six 1000-markets" — the
instance closed, the class left open, which is this repo's own definition of
the circle. One owner now: `fleet_bus.coin_spellings` / `coin_evidence_hit`.

Verified against the live venue the day this shipped: of 216 markets, NO
`1000X` has a bare `X` or `kX` listed beside it, so folding the spellings
cannot pool two different books' evidence.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import fleet_bus                                              # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
THOUSANDS = ("1000BONK", "1000PEPE", "1000SHIB", "1000FLOKI", "1000NOT")


# --------------------------------------------------------------------------
# the owner
# --------------------------------------------------------------------------
@pytest.mark.parametrize("venue_sym", THOUSANDS)
def test_the_venue_spelling_reaches_a_fleet_keyed_payload(venue_sym):
    """Mutation: make `coin_spellings` return `(raw,)` => red."""
    fleet_sym = "k" + venue_sym[4:]
    payload = {fleet_sym: {"slip_bps": 42.0}}
    assert fleet_bus.coin_evidence_hit(payload, venue_sym) == {"slip_bps": 42.0}
    assert fleet_bus.coin_evidence_hit({venue_sym: 1}, fleet_sym) == 1
    assert fleet_bus.coin_evidence_hit({venue_sym[4:]: 2}, venue_sym) == 2


def test_the_exact_spelling_always_wins():
    """A payload already keyed the caller's way must be untouched — this can
    only ever ADD a hit, never redirect one."""
    p = {"1000BONK": "venue", "kBONK": "fleet", "BONK": "bare"}
    assert fleet_bus.coin_evidence_hit(p, "1000BONK") == "venue"
    assert fleet_bus.coin_evidence_hit(p, "kBONK") == "fleet"
    assert fleet_bus.coin_evidence_hit(p, "BONK") == "bare"
    assert fleet_bus.coin_spellings("1000BONK")[0] == "1000BONK"


def test_an_ordinary_coin_is_unaffected():
    """The 200-odd markets with one spelling must behave exactly as before."""
    for c in ("BTC", "ETH", "SOL", "XAU", "SPY", "WTI", "KAITO"):
        assert fleet_bus.coin_spellings(c) == (c,), c
        assert fleet_bus.coin_evidence_hit({"BTC": 1}, c) == (1 if c == "BTC" else None)


def test_it_never_raises_and_never_invents_a_hit():
    for junk in (None, "", "  ", 0, [], {}):
        assert fleet_bus.coin_spellings(junk) in ((), (str(junk).strip(),)), junk
    assert fleet_bus.coin_evidence_hit(None, "BTC") is None
    assert fleet_bus.coin_evidence_hit({}, "BTC") is None
    assert fleet_bus.coin_evidence_hit({"ETH": 1}, "BTC") is None
    assert fleet_bus.coin_evidence_hit("not a dict", "BTC") is None


def test_a_pair_symbol_resolves_to_its_base():
    assert fleet_bus.coin_evidence_hit({"BTC": 1}, "BTC/USDC:USDC") == 1
    assert fleet_bus.coin_evidence_hit({"ETH": 1}, "ETH-PERP") == 1


# --------------------------------------------------------------------------
# every consumer reads the owner
# --------------------------------------------------------------------------
def _calls_owner(path, fn_name=None):
    tree = ast.parse((ROOT / path).read_text())
    scope = tree
    if fn_name:
        scope = next(n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == fn_name)
    names = set()
    for c in ast.walk(scope):
        if isinstance(c, ast.Call):
            names.add(getattr(c.func, "attr", None) or getattr(c.func, "id", None))
    return names


@pytest.mark.parametrize("path", ["lighter_avo_live_bot.py",
                                  "lighter_ticket_taker.py",
                                  "lighter_funding_bot.py"])
def test_every_veto_consumer_reads_the_one_owner(path):
    """Mutation: restore any consumer's `sym in coin_vetoed` => red.

    `lighter_avo_live_bot.py` is 👩 mum's and 🙏 avo's REAL-MONEY host, so this
    is the assertion that matters most."""
    assert "coin_evidence_hit" in _calls_owner(path), \
        f"{path} looks a coin veto up without the namespace owner"


def test_the_real_money_host_has_no_raw_membership_test_left():
    """The specific line: `sym.split('/')[0] in coin_vetoed or sym in
    coin_vetoed` on the live arm. Mutation: put it back => red."""
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    assert "in coin_vetoed" not in src, \
        "a raw membership test against the veto map is back on the live host"


def test_the_funding_hosts_gate_is_still_pure():
    """`entry_admission` is unit-tested offline and must stay a pure function
    of what it is handed — the helper is a dict lookup, not a state read."""
    import lighter_funding_bot as fb
    st = {"open_now": 0, "max_open": 4, "opened_this_loop": 0,
          "max_new_per_loop": 2, "n_explore": 0, "expl_k": 1,
          "vol_veto": set(), "vetoes": {"kBONK": "slip>15bps"},
          "fleet_long_veto": False, "slope_prev": None}
    assert fb.entry_admission("1000BONK", "rank", True, 0.4, st) == \
        ("skip", "quality_veto")
    assert fb.entry_admission("BTC", "rank", True, 0.4, st)[0] != "skip"


# --------------------------------------------------------------------------
# the measured-cost accessor and the sentinel's sectors
# --------------------------------------------------------------------------
def test_recorded_cost_reads_through_the_owner():
    """Mutation: restore `coins.get(str(sym))` => red."""
    fn = next(n for n in ast.walk(ast.parse((ROOT / "fleet_bus.py").read_text()))
              if isinstance(n, ast.FunctionDef) and n.name == "recorded_cost_bps")
    calls = {getattr(c.func, "attr", None) or getattr(c.func, "id", None)
             for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "coin_evidence_hit" in calls


@pytest.mark.parametrize("sym", ["1000BONK", "1000PEPE", "1000SHIB", "1000FLOKI"])
def test_the_sentinels_meme_sector_sees_the_venues_memecoins(sym):
    """Mutation: restore the bare `SYM2SECTOR.get(s, "other")` => red.

    `SECTORS["meme"]` lists BONK/PEPE/SHIB/FLOKI and the venue lists none of
    them under those names, so the sector was empty on the only venue we
    trade."""
    import event_sentinel
    assert event_sentinel._sector_of(sym) == "meme"


def test_an_unknown_symbol_is_still_other():
    import event_sentinel
    assert event_sentinel._sector_of("NOTACOIN") == "other"
    assert event_sentinel._sector_of("1000NOT") == "other"
