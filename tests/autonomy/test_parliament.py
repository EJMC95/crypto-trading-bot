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
from parliament.data import RES_FAST
from parliament.ecosystem_db import EcosystemDB
from parliament.strategies import PARAM_BOUNDS, STRATEGY_DEFAULTS, clamp_params
from parliament.tuners import (ACCEL_MAX_POWER, LEVER_TTL_SEC, SWEEP,
                               TunerBench, simulate_exit)
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
    # [(nz)] the published roster is the LIVING set, not the raw declaration —
    # (nf) retired four PM books and this key is a claim about what the
    # Parliament is RUNNING. Pinned against the derivation so a future
    # retirement cannot leave the payload advertising a dead book.
    from parliament import live_pm_bots
    assert set(payload["roster"]["books"]) == set(live_pm_bots())
    assert set(payload["roster"]["books"]) <= set(PM_BOTS)
    # a consumer applying fleet_bus.is_fresh must accept it right now
    import fleet_bus
    assert fleet_bus.is_fresh(payload, None)


# -- sweep acceleration (the (gx) gillard sl-walk expressibility fix) ---------
#
# The un-accelerated walk multiplies the STATIC base and expiry reverts, so
# its reachable set is ONE x1.25 step forever — while the fleet's only
# calibrated exit counterfactual (gillard, (gx)) measures sl monotone
# improving far past that. The acceleration offers a larger SWEEP-derived
# step when N consecutive replay-accepted walks agree in direction; the cage
# and the replay gate are unchanged and senior; scope is BY BOOK.

def _streak_db(bot, n=2, direction=1, param="sl_pct"):
    """A DB whose lever history holds n expired replay-accepted walks on
    (bot, param), all in one direction, none graded hurting."""
    db = EcosystemDB(path=":memory:")
    base = 0.01
    for _ in range(n):
        val = base * (1.25 if direction > 0 else 0.75)
        db.open_lever(bot, param, val, base, ttl_sec=0.001)
        time.sleep(0.002)      # distinct applied_ts so history order is stable
    time.sleep(0.01)           # all expired: no active lever blocks the sweep
    return db


def test_accel_scope_guard_is_by_book():
    """Only ACCEL_BOOKS (gillard) may receive an accelerated candidate —
    albanese/turnbull with an IDENTICAL streak structurally cannot."""
    for bot in ("pm-albanese", "pm-turnbull"):
        bench = TunerBench(_streak_db(bot))
        assert bench._sweep_candidates(bot) == list(SWEEP), \
            f"{bot} must never see an accelerated step"
    bench = TunerBench(_streak_db("pm-gillard"))
    extra = [c for c in bench._sweep_candidates("pm-gillard")
             if c not in SWEEP]
    assert extra == [("sl_pct", 1.25 ** 3)], \
        "gillard with a streak of 2 gets exactly one accelerated widen"


def test_accel_counter_needs_n_consecutive_agreeing_walks():
    # streak of 1: below ACCEL_CONSEC_N — no acceleration
    bench = TunerBench(_streak_db("pm-gillard", n=1))
    assert bench._sweep_candidates("pm-gillard") == list(SWEEP)
    # a direction FLIP breaks the streak (newest tightens, older widens)
    db = EcosystemDB(path=":memory:")
    db.open_lever("pm-gillard", "sl_pct", 0.0125, 0.01, ttl_sec=0.001)
    time.sleep(0.002)
    db.open_lever("pm-gillard", "sl_pct", 0.0075, 0.01, ttl_sec=0.001)
    time.sleep(0.01)
    assert TunerBench(db)._sweep_candidates("pm-gillard") == list(SWEEP)
    # a HURTING grade on the newest walk kills the streak entirely
    db = _streak_db("pm-gillard")
    newest = db.lever_history("pm-gillard", "sl_pct", limit=1)[0]
    db.grade_lever(newest["id"], "hurting")
    assert TunerBench(db)._accel_streak("pm-gillard", "sl_pct") == (0, 0)
    # dark DB: fail-safe, no streak, no acceleration
    bench = TunerBench(None)
    assert bench._sweep_candidates("pm-gillard") == list(SWEEP)


def test_accel_power_is_capped():
    """A long streak may not mint an unbounded multiplier — the power caps at
    ACCEL_MAX_POWER (and the value clamp to PARAM_BOUNDS is the hard cage)."""
    bench = TunerBench(_streak_db("pm-gillard", n=12))
    extra = [m for p, m in bench._sweep_candidates("pm-gillard")
             if (p, m) not in SWEEP and p == "sl_pct"]
    assert extra == [pytest.approx(1.25 ** ACCEL_MAX_POWER)]


def _accel_e2e_db(bot, now, dip_low):
    """A replayable book: 12 identical longs whose dip stops out sl<=1.25%
    variants; whether the ACCELERATED stop (1.953%) escapes is set by
    dip_low. Streak of 2 accepted sl widenings already in history."""
    db = EcosystemDB(path=":memory:")
    db.open_lever(bot, "sl_pct", 0.0125, 0.01, ttl_sec=0.001)
    time.sleep(0.002)
    db.open_lever(bot, "sl_pct", 0.0125, 0.01, ttl_sec=0.001)
    # int on purpose: store_candles casts ts to int, so a float `opened`
    # would truncate bar0 BELOW opened_ts and drop the dip bar from replay
    opened = int(now) - 6 * 3600
    bars = [{"t": opened, "o": 100.0, "h": 100.6, "l": dip_low, "c": 100.4,
             "v": 1}]
    bars += [{"t": opened + i * 3600, "o": 100.4, "h": 100.6, "l": 100.2,
              "c": 100.5, "v": 1} for i in range(1, 26)]
    db.store_candles("TEST", RES_FAST, bars)
    for i in range(12):
        # opened_ts identical on purpose: simulate_exit keeps bars with
        # t >= opened_ts, so a stagger would drop the dip bar for later trades
        db.record_trade(f"TEST:{i}", bot, "parliament", "TEST", "long-trend",
                        "trend", opened, now - 3600 + i, 100.0, 99.0, 1.0,
                        -1.0, "sl")
    time.sleep(0.01)
    return db


_ACCEL_BASE = {"tp_pct": 0.04, "sl_pct": 0.01, "max_hold_hr": 24.0,
               "entry_bar": 0.30, "ml_gate": 0.45}


def test_accel_enacts_past_one_step_for_gillard_caged_and_ttld():
    """End-to-end: with a qualifying streak and a tape where only the wide
    stop escapes the dip, gillard's bench enacts sl at base*1.25**3 — past
    the one-step ceiling of the old walk — inside PARAM_BOUNDS, with the
    standard TTL (auto-revert preserved), through the normal replay gate."""
    now = time.time()
    db = _accel_e2e_db("pm-gillard", now, dip_low=98.1)   # 98.1 > 98.047: escapes
    out = TunerBench(db).tune_bot("pm-gillard", dict(_ACCEL_BASE))
    assert out is not None and out["param"] == "sl_pct"
    # the payload rounds to 5dp; the DB lever carries the exact value
    assert out["value"] == pytest.approx(0.01 * 1.25 ** 3, abs=1e-5)
    assert "[accel]" in out["note"]
    lever = db.active_levers("pm-gillard")[0]
    assert lever["value"] == pytest.approx(0.01 * 1.25 ** 3)
    lo, hi = PARAM_BOUNDS["sl_pct"]
    assert lo <= lever["value"] <= hi, "the cage is unchanged and binding"
    assert lever["expires_ts"] - time.time() > LEVER_TTL_SEC - 60, \
        "an accelerated lever keeps the standard TTL (auto-revert)"


def test_accel_candidate_still_faces_the_replay_gate():
    """Seniority: when the tape refutes the accelerated stop (dip deeper than
    it), the gate refuses it and the bench falls back to the best ORDINARY
    candidate — acceleration widens what the gate may look at, never what it
    must accept."""
    now = time.time()
    db = _accel_e2e_db("pm-gillard", now, dip_low=97.0)   # 97.0 < 98.047: stopped
    out = TunerBench(db).tune_bot("pm-gillard", dict(_ACCEL_BASE))
    assert out is not None and out["param"] == "sl_pct"
    assert out["value"] == pytest.approx(0.0075), \
        "refuted accel must lose to the ordinary tighten that replays better"
    assert "[accel]" not in out["note"]


def test_accel_scope_guard_holds_end_to_end():
    """albanese with the IDENTICAL streak + tape must NOT enact the
    accelerated value — its best reachable candidate is the ordinary walk."""
    now = time.time()
    db = _accel_e2e_db("pm-albanese", now, dip_low=98.1)
    out = TunerBench(db).tune_bot("pm-albanese", dict(_ACCEL_BASE))
    assert out is not None and out["param"] == "sl_pct"
    assert out["value"] == pytest.approx(0.0075)
    assert "[accel]" not in out["note"]


def test_dashboard_parliament_card_renders(monkeypatch):
    """The main-page 🏛️ card: fresh chamber renders Howard + full bench with
    quiet rows visible; dark chamber hides the card; stale renders dimmed."""
    import datetime as _dt
    import pnl_dashboard as pd

    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    fixture = {
        "parliament": {
            "updated": now, "ttl_sec": 900,
            "health": {"stalled": []},
            "stress": {"med_bps": 6.1, "pause": False},
            "data": {"books": 201},
            "books": {"pm-abbott": {"closed": 3}},
            "ml": {"enabled": True, "ready": False, "n_seen": 42,
                   "oos_acc": {"logit": 0.52}},
            "scanners": {"bench": {
                "dislocation": {"n": 2, "runs": 9, "last_sym": "BTC",
                                "last_age_sec": 300},
                "breakout": {"n": 0, "runs": 9}}}},
        "parliament-tuning": {"updated": now, "ttl_sec": 900,
                              "active": {"pm-gillard": [
                                  {"param": "entry_bar", "value": 0.425}]}},
    }
    monkeypatch.setattr(pd, "fetch_states",
                        lambda keys: {k: fixture.get(k) for k in keys})
    card = pd.parliament_card()
    assert "🏛️ Parliament" in card and "🧠 Howard" in card
    assert "quiet" in card, "a quiet scanner must be a visible row"
    assert "gillard:entry_bar=0.425" in card
    monkeypatch.setattr(pd, "fetch_states", lambda keys: {})
    assert pd.parliament_card() == ""
