"""🔭 Keating's ensemble: the arming rule, and the census that explains it — (aag).

MEASURED 10-Sep on the live bus, and every number below is from that payload:
the ensemble published `ready: false` with `n_seen` frozen at **85** and
`oos_acc` byte-identical at **0.5082 for 22.5h across 5 boots**. It was not
warming up. `n_seen` resets to 0 on every boot and is rebuilt only from the
trades still in the ecosystem DB, and `prune` was DELETING closed trades at 30
days — so the ceiling on what the bench could ever learn was the pool, which
held 90 trainable closes against a 200 bar. The best 7-day close rate the
Parliament has ever run (5.86/day) projects to 176, still short.

Two things follow, and these tests pin both:

  1. FEED IT — the training horizon is the pruner's retention BY IDENTITY, so
     the query and the deleter cannot drift apart ((hj): a second copy of a
     rule is a second rule).
  2. DON'T ARM ON NOISE — `ready` gained an evidence bar beside the count.
     Driven on pure noise the bench reaches ~0.538 decayed accuracy by luck,
     and under the count-only rule that ARMED `ml_gate` on two shadow books.
     A count is not evidence (I15/I16 in an actuator).

The positive control is load-bearing: a gate that never opens is trivially
stable and useless ((om)), so `test_a_planted_edge_still_arms` must stay green.
"""
import ast
import random
import time
from pathlib import Path

import pytest

from parliament import ml as _ml_mod
from parliament.ecosystem_db import TRADE_KEEP_DAYS, EcosystemDB
from parliament.ml import (ACC_Z_BAR, FEATURES, MIN_READY_SAMPLES, TRAIN_DAYS,
                           MLEngine)

pytestmark = pytest.mark.autonomy

np = pytest.importorskip("numpy", reason="the bench is neutral without numpy")


def _drive(seed, n, edge):
    """Learn `n` labels. edge=True plants a real signal; False is a coin flip."""
    m, rng = MLEngine(), random.Random(seed)
    for _ in range(n):
        f = {k: rng.uniform(-1, 1) for k in FEATURES}
        won = ((f["trend"] + 0.5 * f["ret4"] + 0.2 * rng.gauss(0, 1)) > 0
               if edge else rng.random() > 0.5)
        m.learn(f, won)
    return m


# -- the arming rule ---------------------------------------------------------

def test_a_planted_edge_still_arms():
    """POSITIVE CONTROL. The evidence bar must not be a bar nothing can clear —
    that is 'stable because it never opens', which (om) measured and refused."""
    m = _drive(7, MIN_READY_SAMPLES + 200, edge=True)
    r = m.readiness()
    assert r["verdict"] == "ready", r
    assert r["acc_z"] >= ACC_Z_BAR
    p, ready = m.predict({k: 0.0 for k in FEATURES} | {"trend": 0.9, "ret4": 0.5})
    assert ready and p > 0.6, (p, ready)


def test_a_count_is_not_evidence_pure_noise_never_arms():
    """THE DEFECT THIS CLOSES. Labels independent of the features, well past the
    200 bar: the old rule (`n_seen >= MIN`) armed here at ~0.538 accuracy and
    `ml_gate` began refusing entries on nothing."""
    m = _drive(11, MIN_READY_SAMPLES + 200, edge=False)
    assert m.n_seen >= MIN_READY_SAMPLES, "the COUNT bar must be satisfied"
    r = m.readiness()
    assert r["verdict"] == "edgeless", r
    assert m.predict({k: 0.0 for k in FEATURES}) == (0.5, False)
    assert "not evidence" in r["blocked_by"]


def test_is_ready_is_the_one_owner_so_predict_and_snapshot_cannot_disagree():
    """A payload may not claim a readiness that inference does not have — the
    `bar_map`-bound-to-`grade` discipline, applied here."""
    for seed, n, edge in ((7, MIN_READY_SAMPLES + 200, True),
                          (11, MIN_READY_SAMPLES + 200, False),
                          (3, 20, True)):
        m = _drive(seed, n, edge)
        assert m.snapshot()["ready"] is m.predict({k: 0.0 for k in FEATURES})[1]
        assert m.snapshot()["ready"] is (m.readiness()["verdict"] == "ready")


# -- the census: cold vs structurally impossible ------------------------------

def test_a_pool_that_cannot_hold_the_bar_reads_unreachable_and_names_it():
    """`ready: false` was byte-identical between 'ready Tuesday' and 'never'
    ((lv)). Replays the live 10-Sep state exactly."""
    m = MLEngine()
    m.n_seen, m._pool = 85, 90
    m.acc = {"nb": 0.4961, "knn": 0.507, "logit": 0.5082,
             "ridge": 0.5039, "stumps": 0.4944}
    r = m.readiness()
    assert r["verdict"] == "unreachable", r
    assert "RETENTION binds" in r["blocked_by"]
    assert str(int(TRAIN_DAYS)) in r["blocked_by"] and "90" in r["blocked_by"]


def test_a_pool_that_can_hold_the_bar_is_a_countdown_not_a_block():
    m = MLEngine()
    m.n_seen, m._pool = 85, 270
    r = m.readiness()
    assert r["verdict"] == "cold" and r["n_short"] == MIN_READY_SAMPLES - 85, r


def test_an_unknown_pool_never_reads_unreachable():
    """I6: an absence is evidence only against a control group. A dark DB has
    not run a training pass, so `_pool` is None — and None must never publish a
    confident 'structurally impossible'."""
    m = MLEngine()
    m.n_seen = 85
    assert m._pool is None, "a fresh engine must not claim a pool it never read"
    assert m.readiness()["verdict"] == "cold"


def test_the_census_survives_an_empty_bench():
    """`readiness()` runs inside `snapshot()` inside `publish()`; a raise here
    takes the whole howard cycle down, not just this block."""
    m = MLEngine()
    m.n_seen, m._pool, m.acc = MIN_READY_SAMPLES + 1, 500, {}
    r = m.readiness()
    assert r["verdict"] == "edgeless" and "unknown" in r["blocked_by"], r


# -- one owner for the horizon -----------------------------------------------

def test_the_training_window_is_the_pruners_retention_by_identity():
    """Not 'both happen to say 90' — the query must READ the constant, or the
    next edit to one silently starves the other."""
    assert TRAIN_DAYS == TRADE_KEEP_DAYS
    src = ast.parse(Path(_ml_mod.__file__).read_text())
    fn = next(n for n in ast.walk(src)
              if isinstance(n, ast.FunctionDef) and n.name == "train_from_db")
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)
             and getattr(c.func, "attr", None) == "closed_trades"]
    assert len(calls) == 1, calls
    days = next((k.value for k in calls[0].keywords if k.arg == "days"), None)
    assert isinstance(days, ast.Name) and days.id == "TRAIN_DAYS", \
        "train_from_db must read TRAIN_DAYS, never a retyped literal"


def test_prune_keeps_trades_longer_than_candles():
    """The split is the point: candles are the bulky table and the ML does not
    read them; a closed trade is the ML's only food."""
    db = EcosystemDB(path=":memory:")
    now = time.time()
    old = now - 45 * 86400          # inside 90d retention, outside 30d
    ancient = now - 200 * 86400     # outside both
    db.record_trade("keep", "pm-x", "parliament", "BTC", "long", "t",
                    old - 3600, old, 1.0, 1.1, 1.0, 0.5, "tp", {"rsi": 70})
    db.record_trade("drop", "pm-x", "parliament", "BTC", "long", "t",
                    ancient - 3600, ancient, 1.0, 1.1, 1.0, 0.5, "tp", {"rsi": 70})
    db.store_candles("BTC", "1h", [{"ts": int(old), "o": 1, "h": 1,
                                    "l": 1, "c": 1, "v": 1}])
    db.prune()
    ids = {r["trade_id"] for r in db.closed_trades(days=365.0)}
    assert "keep" in ids, "a 45d-old trade must survive the 90d trade retention"
    assert "drop" not in ids, "a 200d-old trade must still be pruned"
    assert db.get_candles("BTC", "1h") == [], \
        "candles keep the 30d retention — the disk cost stays bounded"


def test_the_retention_clears_the_bar_at_the_measured_close_rate():
    """DERIVED, not picked. 90 closes in the trailing 30d on 10-Sep = 3.0/day;
    200 / 3.0 = 66.7d is the bare minimum, and the shipped horizon must carry
    real margin over it or a quiet fortnight disarms the ensemble."""
    measured_per_day = 90 / 30.0
    need_days = MIN_READY_SAMPLES / measured_per_day
    assert TRAIN_DAYS >= need_days * 1.25, (TRAIN_DAYS, need_days)


def test_the_bar_is_the_fleets_own_critical_value():
    """Pinned by identity to the fleet's one-sided 90% value rather than
    imported at runtime — the Parliament keeps its self-contained import graph
    (born-dark rule), so the drift guard has to live here."""
    import fleet_allocation
    assert ACC_Z_BAR == fleet_allocation.Z_LOWER, (ACC_Z_BAR,
                                                   fleet_allocation.Z_LOWER)
