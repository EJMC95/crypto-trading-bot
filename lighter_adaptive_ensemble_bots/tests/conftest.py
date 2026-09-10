import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from lighter_bots.models import Candle, MarketMeta   # noqa: E402


def make_market(symbol="BTC", market_id=1, **kw):
    base = dict(symbol=symbol, market_id=market_id, tick_size=0.1,
                qty_step=0.00001, min_base_amount=0.0001,
                min_quote_amount=10.0, max_leverage=50.0,
                maintenance_margin_frac=0.012, initial_margin_frac=0.02,
                taker_fee=0.0, maker_fee=0.0, daily_quote_volume=7.0e8,
                status="active", price_decimals=1, size_decimals=5)
    base.update(kw)
    return MarketMeta(**base)


def ramp(n=400, start=100.0, drift=0.002, wiggle=0.0, tf_sec=3600,
         t0=1_700_000_000, vol=1.0):
    """Deterministic tape. Bar opens chain to the previous close, exactly as a
    real candle series does -- a synthetic series that breaks that chain makes
    every gap test meaningless."""
    out, px = [], start
    for i in range(n):
        w = wiggle * ((i % 7) - 3) / 3.0
        nxt = px * (1.0 + drift + w)
        out.append(Candle(t0 + i * tf_sec, px, max(px, nxt) * 1.001,
                          min(px, nxt) * 0.999, nxt, vol))
        px = nxt
    return out


@pytest.fixture
def market():
    return make_market()


@pytest.fixture
def registry():
    from lighter_bots.market_metadata import MarketRegistry
    return MarketRegistry([make_market("BTC", 1),
                           make_market("ETH", 0, tick_size=0.01,
                                       qty_step=0.0001,
                                       min_base_amount=0.005,
                                       daily_quote_volume=3.3e8),
                           make_market("SOL", 2, tick_size=0.001,
                                       qty_step=0.001, min_base_amount=0.1,
                                       max_leverage=25.0,
                                       maintenance_margin_frac=0.024,
                                       initial_margin_frac=0.04,
                                       daily_quote_volume=5.7e7)], "test")


@pytest.fixture
def cfg(tmp_path):
    from lighter_bots.config import AppConfig
    c = AppConfig()
    c.state_dir = str(tmp_path / "state")
    c.runtime_dir = str(tmp_path / "runtime")
    c.reports_dir = str(tmp_path / "reports")
    c.data_dir = str(tmp_path / "data")
    for d in (c.state_dir, c.runtime_dir, c.reports_dir, c.data_dir):
        os.makedirs(d, exist_ok=True)
    return c
