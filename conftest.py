"""Root pytest conftest — shared fixtures + import path for the fleet test suite.

The fleet modules live at the repo root (fleet_risk.py, bot_pnl_store.py, …) and
under venues/. Tests import them directly, so the repo root must be on sys.path.
"""
import os
import sys
import time as _time
import types

# [2026-08-18 (pz)] A TEST RUN MUST NEVER REACH THE FLEET'S DATABASE — stripped
# HERE, at root-conftest import, which pytest performs before importing any
# test module, so no module-level `os.environ.get("DATABASE_URL")` read
# anywhere in the tree can see it. Measured incident, self-inflicted: a session
# ran the suite in a shell carrying `export DATABASE_URL` from study work, and
# a parliament book test walked its real close path — `parliament/strategies.py`
# publishes via bot_pnl_store whenever the env is set — writing a FABRICATED
# trade into the durable ledger (pm-albanese BTC/USD, fixture entry 100.01,
# +$1.27 "tp" in 2.2s, on a book kept alive BECAUSE it was positive; the row is
# quarantined in LEDGER_QUARANTINE). The suite was only ever green in CI
# because CI has no DATABASE_URL — this makes the local regime EQUAL to CI's.
# A test that genuinely needs a live DB does not exist today; if one is ever
# written, run it under TESTS_ALLOW_DB=1 and it owns the consequences.
if os.environ.get("TESTS_ALLOW_DB", "").strip() != "1":
    for _k in ("DATABASE_URL", "DATABASE_PUBLIC_URL"):
        os.environ.pop(_k, None)

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
