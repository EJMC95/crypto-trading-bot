"""[2026-09-02 (wp)] THE EXECUTION-QUALITY ORGAN STOOD DOWN FOR 11 DAYS
BECAUSE ITS DEFAULT PAIR WAS A LITERAL naming a retired live arm. The default
is now derived from JUDGED_PAIRS + RETIRED_LIVE_ARMS, so a slot swap moves it.

Mutations: include a pair whose live arm is retired; include the parked pair
with `live_service` None; return registry order when the feed says another
pair has more closes.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import fleet_bus as fb  # noqa: E402

pytestmark = pytest.mark.autonomy


def test_active_pairs_exclude_retired_and_parked_arms():
    pairs = fb.active_price_pairs()
    ids = [p[0] for p in pairs]
    assert "farmer" not in ids            # live_service None (parked)
    assert "georgia" not in ids           # retired at (wg)
    assert "mum" in ids and "avo" in ids
    for _pid, live, shadow, _form in pairs:
        assert not fb.live_arm_retired(live)
        assert live.endswith("-lighter") and shadow.endswith("-lshadow")


def test_the_default_pair_is_the_living_arm_with_the_most_live_closes(monkeypatch):
    import bot_pnl_store as store
    monkeypatch.setattr(store, "fetch_bot_pnl", lambda: [
        {"bot": "freqtrade-mum-lighter", "closed_trades": 53},
        {"bot": "freqtrade-avo-maria-lighter", "closed_trades": 11},
    ])
    assert fb.shortfall_default_pair() == ("freqtrade-mum-lighter",
                                           "freqtrade-mum-lshadow")
    monkeypatch.setattr(store, "fetch_bot_pnl", lambda: [
        {"bot": "freqtrade-avo-maria-lighter", "closed_trades": 99},
    ])
    assert fb.shortfall_default_pair()[0] == "freqtrade-avo-maria-lighter"


def test_a_dark_feed_keeps_registry_order_never_the_retired_literal(monkeypatch):
    import bot_pnl_store as store
    monkeypatch.setattr(store, "fetch_bot_pnl", lambda: None)
    live, shadow = fb.shortfall_default_pair()
    assert not fb.live_arm_retired(live)
    assert live != "perps-funding-lighter-lighter"


def test_no_active_pair_degrades_to_the_farmer_literal_which_reads_stood_down(monkeypatch):
    monkeypatch.setattr(fb, "active_price_pairs", lambda: [])
    live, _ = fb.shortfall_default_pair()
    assert live == "perps-funding-lighter-lighter" and fb.live_arm_retired(live)


def test_the_organ_reads_the_derived_default_when_the_env_is_unset(monkeypatch):
    monkeypatch.delenv("SHORTFALL_LIVE", raising=False)
    monkeypatch.delenv("SHORTFALL_SHADOW", raising=False)
    import importlib
    import implementation_shortfall as ish
    ish = importlib.reload(ish)
    assert not fb.live_arm_retired(ish.LIVE), ish.LIVE
    assert ish.SHADOW.endswith("-lshadow")
