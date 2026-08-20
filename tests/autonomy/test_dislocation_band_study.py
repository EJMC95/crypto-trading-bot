"""nav-cook's founding harness must stay runnable and correct.

`SELFTEST_MODULES` cannot carry this one: the file is
`study_dislocation_band_2026-08-19.py` and the hyphens make it unimportable by
name, so a `"scripts.study_dislocation_band_2026-08-19"` entry there collects
ZERO tests and reports green — which is exactly what happened on the first
attempt ((po): "a check that inspects nothing reports clean"). Loading by PATH
is the form that actually runs it.

Why it is guarded at all: `(sa)` found that this study's harness had never been
committed, so a LIVE book's founding claim was unreproducible and two competent
replays disagreed by 3.2x in n and by sign in mean. The harness is the evidence;
a harness that silently stops running is the same defect returning.
"""
import importlib.util
import os

import pytest

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "scripts",
                     "study_dislocation_band_2026-08-19.py")


def _load():
    spec = importlib.util.spec_from_file_location("_disloc_band_study", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_harness_file_exists():
    assert os.path.exists(_PATH), (
        "nav-cook's founding harness is missing — the (sa) defect returning")


def test_selftest_passes():
    _load()._selftest()


def test_conventions_are_named_and_toggleable():
    """The n=216-vs-697 conflict was a CONVENTION difference. Each one must
    stay explicit and switchable, or the next replay disagrees the same way."""
    m = _load()
    import inspect
    sig = inspect.signature(m.replay).parameters
    for knob in ("confirm_lags", "require_current", "absent_exits",
                 "exclude_classes", "min_vol"):
        assert knob in sig, "convention '%s' must be an explicit knob" % knob


def test_loose_confirm_admits_at_least_as_many_episodes():
    """C2: requiring the band at t-LAGS only cannot admit FEWER episodes than
    requiring it at t-LAGS AND t. This is the relation that explains (sa)."""
    m = _load()
    snaps = []
    for i in range(12):
        snaps.append((i * 300,
                      {"AAA": 50.0 if i < 6 else 5.0},
                      {"AAA": 100.0 * (1.0 + 0.01 * min(i, 6))},
                      {"AAA": 5.0}, {"AAA": 2}))
    strict = len(m.replay(snaps, 45, 60, 7200, require_current=True))
    loose = len(m.replay(snaps, 45, 60, 7200, require_current=False))
    assert loose >= strict


def test_cost_is_charged_and_tiers_are_the_measured_ones():
    """(qq)'s tiers are NOT monotone in liquidity — $1-2M reads a MEAN 5.35bps
    against $0.1-1M's 2.52 (fat tail). Pinned so nobody 'tidies' the table."""
    m = _load()
    assert m.slip_bps(1.5) > m.slip_bps(0.5)
    assert m.slip_bps(20) < m.slip_bps(5) < m.slip_bps(0.5)
    s = m.stats([{"ret": 0.01, "vol": 5.0, "hold_s": 60}] * 10)
    assert s["mean"] < 0.01, "slippage must be charged"
