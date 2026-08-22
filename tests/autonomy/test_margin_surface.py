"""[2026-08-20 (se)] THE FLEET COULD NOT SEE LEVERAGE, SO IT NEVER USED ANY.

Operator mandate, 2026-08-20: *"you have not set the bots up in any way that we
could ever really even use leverage ... we should be running this mandate and
doctrine on building bots that can utilize every aspect of the ecosystem we are
currently working on."*

He is right, and the cause was mechanical rather than philosophical. The venue
publishes `default_initial_margin_fraction` and `maintenance_margin_fraction` on
every row of `/api/v1/orderBookDetails` — an endpoint the scout ALREADY fetches
every cycle — and nothing in this tree read either one. Measured across the 212
active books the day this shipped: 20x available on 21 markets (BTC ETH WTI
US100), 15x on 24 (SOL XAU NVDA AAPL), 10x on 88, while every Lighter book sizes
a flat dollar clip at 1x. The only `LEVERAGE` constant in the repo belonged to a
RETIRED Hyperliquid bot.

Third time this exact story has run on this endpoint, after `created_at` (the
sniper burning candle probes to approximate a timestamp already on the row) and
`strategy_index` (five hand-typed non-crypto lists, wrong on 41 of 204 books).

PUBLISHED, NOT CONSUMED: no book's sizing changes here. A sizing model is a
book-level design decision that earns its own measured pass. This is the
instrument that makes such a design possible at all.
"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fleet_bus as fb  # noqa: E402
import lighter_market_scout as sc  # noqa: E402


def _rows():
    """Two markets at opposite ends of the venue's real margin range."""
    base = dict(status="active", mark_price=100.0, index_price=100.0,
                open_interest=10.0, last_trade_price=100.0,
                daily_price_high=101.0, daily_price_low=99.0,
                daily_price_change=1.0, created_at=1e12,
                taker_fee=0.0, maker_fee=0.0, strategy_index=2)
    return [
        dict(base, symbol="BTC", daily_quote_token_volume=1e9,
             default_initial_margin_fraction=500,     # 5% imf  -> 20x
             maintenance_margin_fraction=300),
        dict(base, symbol="TINY", daily_quote_token_volume=1e5,
             default_initial_margin_fraction=3333,    # 33% imf -> 3x
             maintenance_margin_fraction=2000),
    ]


def _publish(rows=None, ttl=3600, age_s=0):
    """Build the payload through the REAL publisher — `sc.build_snapshot` — not
    a hand-rolled copy of it.

    The first draft of this file rebuilt the `margins` map inline, and a
    mutation round caught it: deleting the scout's own `imf > 0` filter left
    every test GREEN, because the test was grading its own arithmetic instead of
    the publisher's. That is (hj) exactly — a consumer tested against a fixture
    its publisher did not build certifies whatever the consumer already does."""
    stats = sc.book_stats(rows or _rows(), 0.0)
    snap = sc.build_snapshot(stats, {}, {}, {})
    snap["ttl_sec"] = ttl
    snap["updated"] = (datetime.now(timezone.utc)
                       - timedelta(seconds=age_s)).isoformat()
    return snap


def test_the_scout_captures_the_margin_fractions():
    stats = sc.book_stats(_rows(), 0.0)
    assert stats["BTC"]["imf"] == 500.0 and stats["BTC"]["mmf"] == 300.0
    assert stats["TINY"]["imf"] == 3333.0


def test_max_leverage_is_derived_not_guessed(monkeypatch):
    monkeypatch.setattr(fb, "_load", lambda k, t=None: _publish())
    assert fb.max_leverage("BTC") == 20.0, "10000/500bps = 20x"
    assert fb.max_leverage("TINY") == 3.0, "10000/3333bps = 3x"
    row = fb.market_margins("BTC")
    assert row["mmf_bps"] == 300.0, (
        "the maintenance margin must be published beside the leverage — it is "
        "the RUIN number a leverage design has to quote its distance to")


def test_absence_degrades_to_UNLEVERED_never_to_a_guess(monkeypatch):
    """This accessor's contract is the OPPOSITE of the rest of fleet_bus. Every
    other reader degrades to 'keep your configured default' because the cost of
    being wrong is a missed shadow trade. Here the cost of a wrong default is a
    LIQUIDATION — an unrecoverable loss of the whole book — so unknown means 1x.
    A default above 1.0 would turn a dark bus into leverage nobody chose."""
    monkeypatch.setattr(fb, "_load", lambda k, t=None: _publish())
    assert fb.max_leverage("GHOST") == 1.0, "unlisted market -> unlevered"

    monkeypatch.setattr(fb, "_load", lambda k, t=None: None)
    assert fb.max_leverage("BTC") == 1.0, "dark bus -> unlevered"
    assert fb.market_margins() == {}
    assert fb.market_margins("BTC") is None

    monkeypatch.setattr(fb, "_load", lambda k, t=None: _publish(ttl=60, age_s=9999))
    assert fb.max_leverage("BTC") == 1.0, "STALE bus -> unlevered"


def test_a_zero_or_junk_margin_is_dropped_not_published(monkeypatch):
    """imf=0 would compute an infinite leverage. It must be absent, and absence
    reads as unlevered — never as 'no limit'."""
    rows = _rows()
    rows[0]["default_initial_margin_fraction"] = 0
    monkeypatch.setattr(fb, "_load", lambda k, t=None: _publish(rows))
    assert fb.market_margins("BTC") is None
    assert fb.max_leverage("BTC") == 1.0
    assert fb.max_leverage("TINY") == 3.0, "the healthy market is unaffected"


#: [2026-08-22 (sy)/(ta)] BOOKS THAT MAY READ THE MARGIN SURFACE, and why.
#:
#: This test used to forbid EVERY reader, and that was right while the surface
#: was sight-only. `(sy)` is the design decision its own message asked for: 🙏
#: Avo and 🔮 georgia run levered on the shared live runner, so the distance to
#: liquidation stopped being a curiosity and became a rail — `(sr)` had been
#: publishing `liq_gap_pct` off a HARDCODED 300bps while the venue's real worst
#: across those books' own universes is 600bps, i.e. the row advertised a
#: liquidation twice as far away as it was.
#:
#: THE BAN THAT SURVIVES IS THE ONE THAT MATTERED. Reading the margin to
#: PUBLISH ruin distance is the opposite of sizing on it: the second test below
#: pins that neither `clip_usd` nor `gross_x` — the two functions that decide
#: how many dollars go on the venue — can see the margin at all. So a book may
#: know how close the cliff is; it may not use the cliff to choose the clip.
#: An undeclared reader still fails, exactly as before.
DECLARED_MARGIN_READERS = {
    "lighter_avo_live_bot.py":
        "(sy) publishes liq_gap_pct / stop_reachable / stop_dead_above off the "
        "venue's real mmf for 🙏 Avo and 🔮 georgia. READ-ONLY: it reports the "
        "consequences of a leverage setting, it never chooses one.",
}


def _margin_readers():
    import ast
    found = {}
    for py in sorted(ROOT.glob("lighter_*.py")):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            hit = ((isinstance(node, ast.Attribute)
                    and node.attr in ("max_leverage", "market_margins"))
                   or (isinstance(node, ast.Name)
                       and node.id in ("max_leverage", "market_margins")))
            if hit:
                found.setdefault(py.name, 0)
                found[py.name] += 1
    return found


def test_only_declared_books_read_the_margin_surface():
    """The announce-itself property, unchanged in force. A NEW reader is a
    book-level design decision that owes its own measured pass and its own ruin
    arithmetic, and it has to say so here rather than arrive silently."""
    undeclared = sorted(set(_margin_readers()) - set(DECLARED_MARGIN_READERS))
    assert not undeclared, (
        f"{undeclared} now read the margin surface. Declare each in "
        "DECLARED_MARGIN_READERS with what it does with the number — and if it "
        "SIZES on it, that needs its own measured pass first (distance to the "
        "maintenance margin is an unrecoverable loss, not a drawdown).")
    # ...and the declaration is not decorative: a book that stops reading it
    # should lose its entry rather than leave a stale permission standing.
    stale = sorted(set(DECLARED_MARGIN_READERS) - set(_margin_readers()))
    assert not stale, f"{stale} no longer read it — drop the declaration"


def test_a_declared_reader_still_may_not_SIZE_on_the_margin():
    """The real safety property. `clip_usd` and `gross_x` are the two functions
    that decide how many dollars reach the venue; neither may see the margin.

    Why this is the line and not "no reading at all": a margin-derived CLIP
    would let a thin market's generous leverage buy a bigger bet, which is
    precisely backwards — the venue's willingness to lend is not evidence, and
    (sy)'s ceiling is derived from the STOP and the drawdown bar instead. The
    margin's only job is to say how far the cliff is."""
    import ast
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    tree = ast.parse(src)
    banned = {"market_margins", "max_leverage", "worst_mmf"}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name not in (
                "clip_usd", "gross_x", "vol_target_gross_x"):
            continue
        for node in ast.walk(fn):
            name = (node.attr if isinstance(node, ast.Attribute)
                    else node.id if isinstance(node, ast.Name) else None)
            assert name not in banned, (
                f"{fn.name}() now sizes off {name} — a margin-derived clip "
                "lets the venue's lending appetite pick the bet size. The "
                "leverage ceiling is derived from the STOP and the 15% "
                "drawdown bar ((sy)); the margin only reports ruin distance.")
