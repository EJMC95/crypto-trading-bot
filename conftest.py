"""Root pytest conftest — shared fixtures + import path for the fleet test suite.

The fleet modules live at the repo root (fleet_risk.py, bot_pnl_store.py, …) and
under venues/. Tests import them directly, so the repo root must be on sys.path.
"""
import os
import sys
import time as _time
import types

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def frozen_time(monkeypatch):
    """Freeze time.time() to a fixed epoch so freshness/TTL math is deterministic.

    Returns a small controller: ``clock.now`` is the current fake epoch and
    ``clock.advance(secs)`` moves it forward. Patches the stdlib ``time.time``
    that every fleet freshness contract reads.
    """
    class _Clock:
        def __init__(self, start):
            self.now = float(start)

        def advance(self, secs):
            self.now += float(secs)
            return self.now

    clock = _Clock(1_700_000_000.0)  # fixed, arbitrary; Date.now() is banned in prod code anyway
    monkeypatch.setattr(_time, "time", lambda: clock.now)
    return clock


class _MemoryBotState:
    """In-memory stand-in for the Postgres-backed bot_state key/value bus.

    bot_pnl_store.set_bot_state / get_bot_state are the real publish/consume
    path for every cross-bot signal (fleet-risk, fleet-tuning, brain-*). In
    tests we swap them for this dict so consumers can be driven without a DB.
    """

    def __init__(self):
        self.store = {}

    def set(self, key, payload, ttl_sec=None):
        rec = dict(payload) if isinstance(payload, dict) else payload
        self.store[key] = rec
        return True

    def get(self, key, default=None):
        return self.store.get(key, default)


@pytest.fixture
def bot_state():
    """A fresh in-memory bot_state store per test."""
    return _MemoryBotState()
