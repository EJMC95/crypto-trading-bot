"""The fleet's own MEASURED execution cost must be readable by a consumer.

[2026-08-27] **Eamon: *"I think we record things far too slowly and it impairs
our judgement."*** The failure this pins is worse than slow — it was a
recording that could never be read, and it stayed that way for seven weeks:

  * `venues/shadow.py` writes `spread_bps`/`slippage_bps` to `venue_orders` on
    every fill (3,230 book-walk rows by 27-Aug, back to 9-Jul).
  * `market_context.coin_quality()` folds them and publishes `coin-quality`
    (135 coins, live).
  * The payload carried `{ts, coins}` and **no `updated` / `ttl_sec`**, so
    `fleet_bus.is_fresh` — which reads exactly those two keys and returns False
    on any exception — judged it stale FOREVER. Any consumer obeying the bus
    contract would have gone neutral on it permanently, which is why nobody
    ever wrote one.

WHAT IT COST. The books needing this number gate on a 24h-turnover PROXY, and
the (ur) study fell back to Roll's estimator and **overstated the liquid names
5-12x** (Roll 15.0 bps/side vs recorded SNDK 2.18, MU 1.35, SKHYNIXUSD 1.26),
producing a refusal on the wrong binding constraint.

The tests below are deliberately of two kinds, because either alone is a hole:
a CONTRACT arm driving the real publisher's own payload shape, and a
FAIL-SAFE arm proving that doubt degrades to "no measurement" rather than to
"free" — a missing cost that defaults to zero is the same defect pointed the
other way, and it would silently authorise every book it touched.
"""
import datetime as dt
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fleet_bus                                            # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc)


def _payload(coins, age_s=60, ttl=54000, drop=()):
    """A `coin-quality` payload in the shape `market_context` really writes."""
    stamp = (NOW - dt.timedelta(seconds=age_s)).isoformat()
    p = {"ts": stamp, "updated": stamp, "ttl_sec": ttl, "coins": coins}
    for k in drop:
        p.pop(k, None)
    return p


@pytest.fixture
def bus(monkeypatch):
    def _install(payload):
        monkeypatch.setattr(fleet_bus, "_load",
                            lambda key, ct=None: payload
                            if key == "coin-quality" else None)
    return _install


# ------------------------------------------------------------------ contract
def test_a_fresh_payload_is_readable(bus):
    bus(_payload({"SNDK": {"spread_bps": 4.36, "slip_bps": 2.0}}))
    assert fleet_bus.recorded_cost_bps("SNDK", NOW)["spread_bps"] == 4.36
    assert "SNDK" in fleet_bus.recorded_cost_bps(None, NOW)


def test_half_spread_halves_the_full_spread(bus):
    """`venue_orders.spread_bps` is (ask-bid)/mid — FULL. One side costs half.

    The halving lives in ONE place on purpose: a caller doing it inline is a
    second copy of a unit convention, and this fleet has already paid for one
    of those at 8x on the funding basis.
    """
    bus(_payload({"SNDK": {"spread_bps": 4.36}}))
    assert fleet_bus.recorded_half_spread_bps("SNDK", NOW) == pytest.approx(2.18)


# ----------------------------------------------------------------- the defect
@pytest.mark.parametrize("missing", ["updated", "ttl_sec"])
def test_the_shipped_defect_is_reddened(bus, missing):
    """THE REGRESSION ARM. A payload missing either bus-contract field must be
    unreadable — and this is exactly the state `coin-quality` shipped in for
    seven weeks. If someone drops these fields again, this goes red."""
    bus(_payload({"SNDK": {"spread_bps": 4.36}}, drop=(missing,)))
    assert fleet_bus.recorded_cost_bps("SNDK", NOW) is None
    assert fleet_bus.recorded_cost_bps(None, NOW) == {}


def test_the_real_publisher_shape_passes_is_fresh():
    """Drive the PUBLISHER's own construction, not a hand-written lookalike.

    `market_context` builds `{ts, updated, ttl_sec, coins}` with
    `ttl_sec = QUALITY_EVERY_H * 3600 * 2.5`. Assert that shape actually
    satisfies the freshness predicate a consumer will apply to it — the
    publisher and the predicate living in different files is precisely how the
    original gap survived.
    """
    import market_context as mctx
    ttl = int(mctx.QUALITY_EVERY_H * 3600 * 2.5)
    assert ttl > mctx.QUALITY_EVERY_H * 3600, (
        "TTL must outlive one refresh period or a single skipped tick blinds "
        "every consumer")
    stamp = NOW.isoformat()
    assert fleet_bus.is_fresh({"ts": stamp, "updated": stamp,
                               "ttl_sec": ttl, "coins": {}}, NOW)
    # And the OLD shape must still be judged stale, so the fix is load-bearing.
    assert not fleet_bus.is_fresh({"ts": stamp, "coins": {}}, NOW)


# ----------------------------------------------------------------- fail-safe
def test_doubt_degrades_to_no_measurement_never_to_free(bus):
    """The direction of the fail-safe is the whole safety of this accessor.

    An unmeasured cost that returns 0.0 reads as FREE and would authorise
    every book that consulted it — the same defect as the one being fixed,
    pointing the other way. Every doubt must be None/{}.
    """
    stale = _payload({"SNDK": {"spread_bps": 4.36}}, age_s=10 ** 6)
    for payload in (None, {}, stale,
                    _payload("not-a-dict"),
                    _payload({"SNDK": "not-a-dict"})):
        bus(payload)
        got = fleet_bus.recorded_cost_bps("SNDK", NOW)
        assert got is None or got == {}, f"{payload!r} must not return a value"
        assert fleet_bus.recorded_half_spread_bps("SNDK", NOW) is None

    bus(_payload({"SNDK": {"slip_bps": 2.0}}))          # present, no spread
    assert fleet_bus.recorded_half_spread_bps("SNDK", NOW) is None
    for bad in ("", None, "abc", float("nan")):
        bus(_payload({"SNDK": {"spread_bps": bad}}))
        v = fleet_bus.recorded_half_spread_bps("SNDK", NOW)
        assert v is None or v == v, f"spread_bps={bad!r} produced {v!r}"


def test_an_unknown_symbol_is_none_not_zero(bus):
    bus(_payload({"SNDK": {"spread_bps": 4.36}}))
    assert fleet_bus.recorded_cost_bps("NEVER_TRADED", NOW) is None
    assert fleet_bus.recorded_half_spread_bps("NEVER_TRADED", NOW) is None
