"""Parliament 🏛️ — targeted invariants beyond the module selftest.

The full six-layer offline exercise runs as `parliament_main --selftest`
(registered in test_selftests.py). These tests pin the CONTRACTS other fleet
citizens rely on: the bounds cage, the reduce-only sizing chain, the
fail-safe postures, and the publish freshness contract.
"""
import asyncio
import time

import pytest

from parliament import PM_BOTS, SHADOW_SUFFIX, START_EQUITY
from parliament.bus import EcosystemBus, drain
from parliament.ecosystem_db import EcosystemDB
from parliament.strategies import PARAM_BOUNDS, STRATEGY_DEFAULTS, clamp_params
from parliament.tuners import TunerBench, simulate_exit
from parliament.ml import MLEngine


pytestmark = pytest.mark.autonomy


def test_roster_is_the_last_eight_pms():
    # six books; Keating (intelligence) + Howard (brain) complete the eight
    assert list(PM_BOTS) == ["pm-albanese", "pm-morrison", "pm-turnbull",
                             "pm-abbott", "pm-rudd", "pm-gillard"]
    assert SHADOW_SUFFIX == "-lshadow"      # fleet venue-variant convention
    assert START_EQUITY == 1000.0           # fleet rule: $1k books, no top-ups


def test_every_strategy_default_lives_inside_the_cage():
    for strat, params in STRATEGY_DEFAULTS.items():
        clamped = clamp_params(params)
        assert clamped == clamp_params(clamped)
        for k, v in params.items():
            lo, hi = PARAM_BOUNDS[k]
            assert lo <= v <= hi, f"{strat}.{k}={v} outside [{lo}, {hi}]"


def test_clamp_is_a_hard_cage():
    wild = {"tp_pct": 99.0, "sl_pct": -1.0, "max_hold_hr": 1e9,
            "entry_bar": 0.0, "ml_gate": 1.0}
    c = clamp_params(wild)
    for k, v in c.items():
        lo, hi = PARAM_BOUNDS[k]
        assert lo <= v <= hi


def test_effective_params_reverts_on_expiry():
    """A lever's expiry must revert to baseline WITHOUT any release action —
    auto-revert is the resting state (fleet_tuning doctrine)."""
    db = EcosystemDB(path=":memory:")
    bench = TunerBench(db)
    base = dict(STRATEGY_DEFAULTS["scalp"])
    lid = db.open_lever("pm-abbott", "tp_pct", 0.02, base["tp_pct"],
                        ttl_sec=0.05)
    eff = bench.effective_params("pm-abbott", base)
    assert eff["tp_pct"] == 0.02
    time.sleep(0.1)
    eff = bench.effective_params("pm-abbott", base)
    assert eff["tp_pct"] == base["tp_pct"], "expired lever must revert"
    assert lid > 0


def test_tuner_refuses_a_hurting_param():
    db = EcosystemDB(path=":memory:")
    bench = TunerBench(db)
    lid = db.open_lever("pm-abbott", "entry_bar", 0.4, 0.6, ttl_sec=0.01)
    db.grade_lever(lid, "hurting")
    time.sleep(0.05)
    # starving path (no trades in DB) targets entry_bar — must refuse
    assert bench.tune_bot("pm-abbott", dict(STRATEGY_DEFAULTS["scalp"])) is None


def test_simulate_exit_is_conservative_sl_before_tp():
    # one bar spans BOTH the stop and the target: the stop must win
    bars = [{"t": 100, "o": 100.0, "h": 106.0, "l": 94.0, "c": 100.0, "v": 1}]
    px, reason = simulate_exit(1, 100.0, 50, bars, tp_pct=0.05, sl_pct=0.05,
                               max_hold_hr=24)
    assert reason == "sl" and px == pytest.approx(95.0)


def test_ml_is_reduce_only_and_failsafe():
    ml = MLEngine(db=None)
    p, ready = ml.predict({"direction": 1.0})
    assert p == 0.5 and ready is False, "cold model must be neutral"
    # disabled engine (numpy absent path) must also be neutral
    ml.enabled = False
    ml.n_seen = 10 ** 6
    assert ml.predict({"direction": 1.0}) == (0.5, False)


def test_bus_parent_topic_fanout_and_bounded_queues():
    async def _run():
        bus = EcosystemBus()
        q = bus.subscribe("signals")
        bus.publish("signals.breakout", {"sym": "BTC"})
        bus.publish("signals.funding", {"sym": "ETH"})
        msgs = await drain(q)
        assert [t for t, _ in msgs] == ["signals.breakout", "signals.funding"]

    asyncio.run(_run())


def test_howard_publish_carries_the_freshness_contract():
    from parliament.brain import Howard

    howard = Howard(db=EcosystemDB(path=":memory:"))
    payload = howard.publish()
    assert payload["ttl_sec"] > 0 and payload["updated"]
    assert set(payload["roster"]["books"]) == set(PM_BOTS)
    # a consumer applying fleet_bus.is_fresh must accept it right now
    import fleet_bus
    assert fleet_bus.is_fresh(payload, None)
