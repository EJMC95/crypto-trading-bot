"""[2026-08-20 (sd)] THE FLEET COULD NOT SEE LEVERAGE, SO IT NEVER USED ANY.

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


def test_it_is_published_but_consumed_by_no_book_yet():
    """The declared scope: this pass gives the fleet SIGHT of leverage, it does
    not spend it. If a book starts sizing on this, that is a design decision
    that owes its own measured pass — and this test is where it announces
    itself rather than arriving silently."""
    import ast
    consumers = []
    for py in ROOT.glob("lighter_*.py"):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in (
                    "max_leverage", "market_margins"):
                consumers.append(py.name)
            elif isinstance(node, ast.Name) and node.id in (
                    "max_leverage", "market_margins"):
                consumers.append(py.name)
    assert not consumers, (
        f"{sorted(set(consumers))} now size on the margin surface. That is a "
        "book-level design decision: it needs its own measured pass and its own "
        "ruin arithmetic (distance to the 12% maintenance margin), then this "
        "test updates to name the consumer deliberately.")
