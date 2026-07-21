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

# TWO-WAY guardrails for the brain's L4 stake multipliers (reduce-only
# until 21-Jul): whatever the brain publishes, a strategy sizes inside
# [0.5, 1.5] — reductions as before, boosts only on the v3 mirror bars
# (Wilson LOWER bound + t, full n floor, 3-run streak — bot_learn/
# brain_stats EXP_*). Neutral 1.0 on any doubt.
MULT_FLOOR = 0.5
# [2026-07-21 TWO-WAY MULTS — operator: "brain needs to be able to widen
# too"] Ceiling raised 1.0 -> 1.5: the brain may now publish EXPAND mults
# (1.25/1.5) for tags proving out on the v3 mirror bars (Wilson LOWER
# bound, t >= +2, full n floor, streak-gated, no urgent path — brain_stats
# EXP_*). The clamp still bounds whatever arrives; only SHADOW books read
# mults. Deliberate scope expansion of the documented reduce-only
# contract, recorded in CLAUDE.md the same day.
MULT_CEIL = 1.5


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


def lever_outcome(lever, current_time=None):
    """🦾 fleet_proprioception's per-lever OUTCOME verdict: 'helping' |
    'hurting' | 'neutral' | 'insufficient' | None.

    [2026-07-16 CONSUMER SUPPORT] The proprioception organ grades every
    growth-rail lever episode retrospectively (taker = replay counterfactual
    $, scout = grading throughput, gapscout = census activity, live =
    per-trade vs pre-window + shadow twin). This accessor is the ONE
    supported way for any strategy/bot to consume those grades — same
    fail-safe contract as every helper here: dark/stale/absent organ or
    unknown lever -> None, and a None consumer MUST treat it as 'no
    evidence' (restrict nothing, earn nothing). First-party consumers
    (scout tuner, evidence board, experiment judge, incubator) read the
    payload directly on their own cadences; this is the client for
    everyone else.
    """
    try:
        p = _load("fleet-proprioception", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        v = (p.get("verdicts") or {}).get(str(lever))
        vd = v.get("verdict") if isinstance(v, dict) else None
        return vd if vd in ("helping", "hurting", "neutral", "insufficient") \
            else None
    except Exception:
        return None


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


def entry_regime_gated(bot, entry_tag, current_time=None):
    """[2026-07-21 BRAIN ACTS] True when the brain has an ACTIONABLE
    regime_timing finding for (bot, entry_tag) AND the regime oracle
    currently reads risk-off — i.e. the exact condition under which this
    tag's losses were measured to cluster (counter_share >= 0.7, streak-
    hardened across PROMOTE_RUNS brain runs before it ever acts).

    Restrict-only (can only SKIP a new entry, never take one), and the gate
    lifts by itself two ways: the oracle turns risk-on (condition ends), or
    the finding retires from the hypothesis ledger (evidence faded). Uses
    the SAME oracle signal the diagnosis measured (`fleet.read` risk-off) —
    never a different regime proxy (the SPY-vs-btc_regime_up lesson).

    Fail-safe OPEN everywhere: stale/missing brain payload, actions_mode !=
    'enforce' (BRAIN_ACTIONS_MODE=advisory is the central kill switch), no
    action for the pair, stale/missing oracle, or any parse error -> False.
    """
    try:
        p = _load("brain-diagnosis", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        if str(p.get("actions_mode")) != "enforce":
            return False
        act = ((p.get("actions") or {}).get(str(bot)) or {}).get(str(entry_tag))
        if not act or act.get("action") != "regime_gate":
            return False
        o = _load("regime-oracle", current_time)
        if not o or not is_fresh(o, current_time):
            return False
        return str((o.get("fleet") or {}).get("read") or "").startswith("risk-off")
    except Exception:
        return False


def long_symbol_blocked(base, current_time=None):
    """[2026-07-21 PER-SYMBOL PILEUP CAP] True when opening ANOTHER long on
    `base` would stack past the fleet's per-symbol cap.

    Companion to long_entries_blocked with the identical contract: enforces
    ONLY when fleet_risk publishes symbol_cap.mode='enforce' (env
    FLEET_SYMBOL_CAP_MODE on the fleet-risk service; shipped default
    'advisory' = this function is inert fleet-wide), restrict-only, and
    fail-safe OPEN — stale/missing payload, absent block, cap<=0, or any
    parse error all return False. Rationale measured over 168h: 20 long
    slots behaving as ~7.7 independent bets; true LONG-side 4-stacks in
    ~8.7% of samples (the first-draft 37.1% was side-blind — corrected same
    day; see fleet_risk.py) — de-pileup frees budget without raising gross.
    NO consumer is wired by this commit: strategies/bots adopt it when a
    review sanctions the wiring (the fleet-clock lesson). Review caution,
    on record from the verify pass: do NOT wire the shadow TAKER to this
    cap — its book is the lens-grading instrument, and crowding-capped
    entries would starve the episode floors and skew the live-vs-shadow
    baselines that steer real money. Family/strategy lanes only.
    """
    try:
        p = _load("fleet-risk", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        sc = p.get("symbol_cap") or {}
        if str(sc.get("mode")) != "enforce":
            return False
        cap = int(sc.get("cap") or 0)
        if cap <= 0:
            return False
        held = (sc.get("long_by_symbol") or {}).get(str(base).split("/")[0], 0)
        return int(held) >= cap
    except Exception:
        return False


if __name__ == "__main__":
    # offline selftest: prime the cache directly, exercise the fail-safe
    # contract (no DB touched)
    _now = datetime.now(timezone.utc)
    _fresh_p = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 2700,
                "verdicts": {"taker.dip_range": {"verdict": "hurting"},
                             "scout.dip_range_max": {"verdict": "helping"},
                             "weird": {"verdict": "banana"}}}
    _cache["fleet-proprioception"] = {"ts": _now, "payload": _fresh_p}
    assert lever_outcome("taker.dip_range", _now) == "hurting"
    assert lever_outcome("scout.dip_range_max", _now) == "helping"
    assert lever_outcome("taker.tp", _now) is None, "unknown lever -> None"
    assert lever_outcome("weird", _now) is None, "unknown verdict value -> None"
    _cache["fleet-proprioception"] = {"ts": _now, "payload": dict(
        _fresh_p, updated="2020-01-01T00:00:00+00:00")}
    assert lever_outcome("taker.dip_range", _now) is None, "stale -> None"
    _cache["fleet-proprioception"] = {"ts": _now, "payload": None}
    assert lever_outcome("taker.dip_range", _now) is None, "absent -> None"

    # [2026-07-21] per-symbol pileup cap accessor: fail-safe open everywhere
    _risk = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 900,
             "symbol_cap": {"cap": 3, "mode": "enforce",
                            "long_by_symbol": {"ETH": 3, "LTC": 2}}}
    _cache["fleet-risk"] = {"ts": _now, "payload": _risk}
    assert long_symbol_blocked("ETH", _now) is True, "at cap + enforce -> True"
    assert long_symbol_blocked("ETH/USDT", _now) is True, "base-normalizes"
    assert long_symbol_blocked("LTC", _now) is False, "under cap -> False"
    assert long_symbol_blocked("BTC", _now) is False, "unheld -> False"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, symbol_cap=dict(_risk["symbol_cap"], mode="advisory"))}
    assert long_symbol_blocked("ETH", _now) is False, "advisory -> inert"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, symbol_cap=dict(_risk["symbol_cap"], cap=0))}
    assert long_symbol_blocked("ETH", _now) is False, "cap 0 -> disabled"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, updated="2020-01-01T00:00:00+00:00")}
    assert long_symbol_blocked("ETH", _now) is False, "stale -> open"
    _cache["fleet-risk"] = {"ts": _now, "payload": None}
    assert long_symbol_blocked("ETH", _now) is False, "absent -> open"

    # [2026-07-21 BRAIN ACTS] entry_regime_gated: gates ONLY when the brain's
    # streak-hardened action exists AND the oracle reads risk-off right now
    _diag = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
             "actions_mode": "enforce",
             "actions": {"freqtrade-georgia-lshadow":
                         {"long-trend-breakout": {"action": "regime_gate"}}}}
    _orc_off = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 14400,
                "fleet": {"read": "risk-off downtrend"}}
    _orc_on = dict(_orc_off, fleet={"read": "risk-on uptrend"})
    _cache["brain-diagnosis"] = {"ts": _now, "payload": _diag}
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is True, "action + risk-off -> gated"
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-range-on",
                              _now) is False, "no action for tag -> open"
    assert entry_regime_gated("freqtrade-mum-lshadow", "long-trend-breakout",
                              _now) is False, "no action for bot -> open"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_on}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "risk-on -> gate lifts"
    _cache["regime-oracle"] = {"ts": _now, "payload": dict(
        _orc_off, updated="2020-01-01T00:00:00+00:00")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "stale oracle -> open"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    _cache["brain-diagnosis"] = {"ts": _now, "payload": dict(
        _diag, actions_mode="advisory")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "advisory kill switch -> open"
    _cache["brain-diagnosis"] = {"ts": _now, "payload": dict(
        _diag, updated="2020-01-01T00:00:00+00:00")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "stale brain -> open"
    _cache["brain-diagnosis"] = {"ts": _now, "payload": None}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "absent brain -> open"

    # [2026-07-21 TWO-WAY MULTS] the clamp passes expand values and still
    # bounds both directions
    _mults = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
              "mults": {"freqtrade-avo-maria-lshadow":
                        {"long-swing-dip": {"mult": 1.25},
                         "long-big": {"mult": 2.0},
                         "long-bad": {"mult": 0.25}}}}
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _mults}
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-swing-dip",
                            _now) == 1.25, "expand mult passes the clamp"
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-big",
                            _now) == 1.5, "over-ceiling clamps to 1.5"
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-bad",
                            _now) == 0.5, "under-floor clamps to 0.5"
    print("fleet_bus selftest OK (lever_outcome fresh/unknown/stale/absent; "
          "long_symbol_blocked enforce/advisory/cap0/stale/absent; "
          "entry_regime_gated act+off/no-tag/no-bot/risk-on/stale-oracle/"
          "advisory/stale-brain/absent)")
