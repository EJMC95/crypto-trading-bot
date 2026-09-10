"""Metadata parsing, the BPS trap, and the refusal to default."""
import pytest

from lighter_bots.market_metadata import (BPS, MarketRegistry, MetadataStore,
                                          parse_market)
from conftest import make_market

ROW = {"symbol": "BTC", "market_id": 1, "price_decimals": 1, "size_decimals": 5,
       "min_base_amount": "0.00010", "min_quote_amount": "10.000000",
       "maintenance_margin_fraction": 120, "min_initial_margin_fraction": 200,
       "default_initial_margin_fraction": 500, "taker_fee": "0.0000",
       "maker_fee": "0.0000", "is_taker_fee_enabled": True,
       "is_maker_fee_enabled": True, "daily_quote_token_volume": 713372212.09,
       "status": "active", "market_type": "perp"}


def test_margin_fractions_are_basis_points_not_percent():
    m = parse_market(ROW)
    assert m.maintenance_margin_frac == pytest.approx(120 / BPS)   # 1.20%
    assert m.initial_margin_frac == pytest.approx(200 / BPS)       # 2.00%
    # Reading 120 as a PERCENT would make maintenance 120% and every
    # liquidation estimate nonsense; reading it as a FRACTION would make it
    # 12000%. The unit is basis points and this pins it.
    assert 0.001 < m.maintenance_margin_frac < 0.05


def test_max_leverage_is_the_reciprocal_of_min_initial_margin():
    assert parse_market(ROW).max_leverage == pytest.approx(50.0)


def test_maintenance_is_read_never_derived_from_initial():
    row = dict(ROW, maintenance_margin_fraction=300)
    m = parse_market(row)
    assert m.maintenance_margin_frac == pytest.approx(0.03)
    assert m.initial_margin_frac == pytest.approx(0.02)
    assert m.maintenance_margin_frac != m.initial_margin_frac / 2


def test_tick_and_step_come_from_decimals():
    m = parse_market(ROW)
    assert m.tick_size == pytest.approx(0.1)
    assert m.qty_step == pytest.approx(1e-5)


def test_incomplete_metadata_is_refused_not_defaulted():
    for missing in ("price_decimals", "size_decimals", "min_base_amount",
                    "min_initial_margin_fraction",
                    "maintenance_margin_fraction"):
        row = {k: v for k, v in ROW.items() if k != missing}
        m = parse_market(row)
        assert not m.complete, f"{missing} missing should refuse the market"
        assert m.missing(), "an incomplete market must say what is missing"


def test_inactive_market_is_incomplete():
    assert not parse_market(dict(ROW, status="inactive")).complete


def test_disabled_fee_flag_zeroes_the_fee():
    m = parse_market(dict(ROW, taker_fee="0.0004",
                          is_taker_fee_enabled=False))
    assert m.taker_fee == 0.0


def test_symbol_and_id_map_both_ways(registry):
    assert registry.market_id("BTC") == 1
    assert registry.symbol(1) == "BTC"
    assert registry.market_id("NOPE") is None


def test_rounding_never_tightens_a_protective_stop(registry):
    # A long's stop rounds DOWN (further away), a short's rounds UP.
    assert registry.round_price("BTC", 77052.57, side="long") == 77052.5
    assert registry.round_price("BTC", 77052.51, side="short") == 77052.6


def test_quantity_always_rounds_down(registry):
    assert registry.round_qty("BTC", 0.0123456789) == 0.01234


def test_order_below_minimum_is_refused(registry):
    ok, why = registry.order_ok("BTC", 0.00001, 77000)
    assert not ok and "min_base_amount" in why
    ok, why = registry.order_ok("BTC", 0.0001, 1.0)
    assert not ok and "min_quote_amount" in why


def test_effective_leverage_takes_the_lowest_cap(registry):
    assert registry.effective_leverage("SOL", 10.0, 20.0) == 10.0
    assert registry.effective_leverage("SOL", 40.0, 30.0) == 25.0   # market
    assert registry.effective_leverage("SOL", 40.0, 5.0) == 5.0     # account


def test_tradable_refuses_leverage_above_the_market_max(registry):
    ok, why = registry.tradable("SOL", 30.0)
    assert not ok and "exceeds the market maximum" in why[0]


def test_metadata_version_is_a_content_hash_of_risk_fields():
    a = [make_market("BTC")]
    b = [make_market("BTC", daily_quote_volume=1.0)]     # volume is not risk
    c = [make_market("BTC", tick_size=0.5)]              # tick IS risk
    assert MetadataStore.version(a) == MetadataStore.version(b)
    assert MetadataStore.version(a) != MetadataStore.version(c)


def test_snapshot_round_trips(tmp_path):
    store = MetadataStore(str(tmp_path))
    ver, _path = store.save([make_market("BTC"), make_market("ETH", 0)])
    got_ver, markets, ts = store.load_latest()
    assert got_ver == ver and len(markets) == 2 and ts > 0
    assert MarketRegistry(markets).get("BTC").complete
