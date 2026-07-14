#!/usr/bin/env python3
"""fleet_bus.py — READ-side client for the fleet's shared bot_state keys.

[2026-07-14 CONSUMPTION WIRING] The intelligence organs (bot_learn brain,
fleet_risk light, regime oracle, market pulse) have been publishing since
7 Jul with ZERO consumers — the Jul-14 enforcement review found every layer
built and nobody reading it. This module is the one place strategies import
to consume the bus, so the fail-safe contract lives in exactly one file:

  FAIL-SAFE CONTRACT (same as the publishers'):
    - no DATABASE_URL / import error / DB down  -> neutral (1.0x, no veto)
    - payload missing or STALE (updated+ttl_sec) -> neutral
    - anything unparseable                       -> neutral
  In `freqtrade backtesting` DATABASE_URL is unset, so every helper here
  returns neutral and backtests exercise pure strategy logic — live-only
  inputs can never contaminate a backtest.

Reads are cached per-process for CACHE_SEC so 4 bots x N pairs don't hammer
Postgres. Shipped in Dockerfile.freqtrade next to bot_pnl_store.py (CWD
/freqtrade), so strategies use the same `import` mechanics that already
work for the market-pulse reads.
"""
from datetime import datetime, timedelta, timezone

CACHE_SEC = 300
_cache = {}   # key -> {"ts": datetime, "payload": dict|None}

# Reduce-only guardrails for the brain's L4 stake multipliers: whatever the
# brain publishes, a strategy will never size below half stake and never
# above full stake. Boosting (>1.0x) must earn its way in with more ledger
# evidence — see bot_learn.py MULT rules.
MULT_FLOOR = 0.5
MULT_CEIL = 1.0


def _now_utc(current_time):
    if current_time is None:
        return datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=timezone.utc)
    return current_time


def _load(key, current_time):
    """Cached bot_state read; None on any failure."""
    now = _now_utc(current_time)
    c = _cache.get(key)
    if c is not None and abs((now - c["ts"]).total_seconds()) < CACHE_SEC:
        return c["payload"]
    payload = None
    try:
        import bot_pnl_store as store
        payload = store.load_state(key) or None
    except Exception:
        payload = None
    _cache[key] = {"ts": now, "payload": payload}
    return payload


def is_fresh(payload, current_time):
    """True only when the payload self-reports as current (updated + ttl_sec)."""
    try:
        updated = datetime.fromisoformat(str(payload["updated"]).replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        ttl = float(payload.get("ttl_sec") or 0)
        return timedelta(0) <= (_now_utc(current_time) - updated) <= timedelta(seconds=ttl)
    except Exception:
        return False


def stake_multiplier(bot, entry_tag, current_time=None):
    """The brain's L4 per-(bot, enter_tag) stake multiplier, clamped reduce-only.

    Published by bot_learn.py to bot_state 'brain-stake-mults' only after a
    tag's negative expectancy clears the trade-count floor AND persists across
    >= PROMOTE_RUNS consecutive brain runs. Neutral 1.0 on any doubt.
    """
    try:
        p = _load("brain-stake-mults", current_time)
        if not p or not is_fresh(p, current_time):
            return 1.0
        m = ((p.get("mults") or {}).get(str(bot)) or {}).get(str(entry_tag))
        if m is None:
            return 1.0
        return max(MULT_FLOOR, min(MULT_CEIL, float(m.get("mult", 1.0))))
    except Exception:
        return 1.0


def long_entries_blocked(current_time=None):
    """L2 fleet-risk veto: True when the fleet's LONG book is at/over budget.

    Uses the side-specific count (long_positions vs long_budget), NOT the
    blended light, so a blown SHORT budget can't freeze long-only spot bots.
    Only enforces when fleet_risk publishes mode='enforce' — flipping the
    service's FLEET_RISK_MODE env to 'advisory' is the central kill switch,
    no strategy redeploy needed. Stale/missing payload -> False (never
    dead-man-switch the whole fleet on a publisher outage).
    """
    try:
        p = _load("fleet-risk", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        if str(p.get("mode")) != "enforce":
            return False
        return int(p.get("long_positions", 0)) >= int(p.get("long_budget", 10**9))
    except Exception:
        return False
