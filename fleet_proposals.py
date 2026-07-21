#!/usr/bin/env python3
"""fleet_proposals.py — the organs' PROPOSAL channel to the tuners (2026-07-21).

WHY (operator mandate, 21-Jul): "the organs need more ability to implement
changes to forward onto the tuners to act on." Until now the actuation graph
had exactly three authors (board, scout tuner, judge) and every other organ's
signal DEAD-ENDED as advisory display: the event sentinel grades a playbook
nobody trades on, implementation-shortfall measures live slip nobody sizes
off, respiration detects hypoxia nothing tightens for. This module is the
sanctioned bridge: any organ may PROPOSE a bounded change to a registered
lever; a TUNER (or the judge) picks the proposal up on its next cycle and
decides with ITS OWN evidence gate — replay both-halves for the scout tuner,
the paired live bar / early-release rule for the judge. The organ supplies
the trigger and the evidence; the tape still decides.

WHAT A PROPOSAL CAN NEVER DO
  - enact anything by itself: nothing reads this key except consumers that
    then apply their own doctrine gate before writing any lever;
  - reference a lever outside fleet_tuning's registry (dropped at write AND
    at read), or carry a value outside the lever's hard bounds (clamped);
  - outlive its TTL: an organ that stops re-asserting sees its proposal
    expire; the resting state is an empty channel;
  - impersonate an enactment: consumers stamp their own set_by when (and
    only when) a proposal survives their gate — proprioception then grades
    the resulting lever episode exactly like any other.

CONTRACT (same fail-safe shape as fleet_tuning / fleet_bus):
  writer:  propose({lever: {"value", "direction", "reason", "evidence"}},
           set_by=<organ>) -> bot_state['tuning-proposals'] merged payload
           (per-proposal expiry; an author's re-propose replaces its own
           prior stance on that lever, never another author's).
  reader:  fresh_proposals() -> [proposal dicts] — only fresh, unexpired,
           registered, clampable entries survive. No DB / stale / junk ->
           []. Backtests are inert (no DATABASE_URL -> []).

direction is the ORGAN'S declared intent ("restrict" | "expand"). Consumers
MUST re-derive the true direction against their own env defaults and treat a
mismatch as disqualifying — an organ cannot smuggle a widening through a
restrict-shaped gate.
"""
import os
import time
from datetime import datetime, timezone

try:
    import bot_pnl_store as store
except Exception:                                    # pragma: no cover
    store = None

import fleet_tuning as tuning

KEY = "tuning-proposals"
TTL_SEC = int(os.environ.get("FLEET_PROPOSALS_TTL_SEC", "7200"))   # 2h re-assert
CACHE_SEC = 60.0
MAX_PROPOSALS = 24            # payload cap: newest survive, oldest dropped
DIRECTIONS = ("restrict", "expand")

_cache = {"ts": 0.0, "payload": None}


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _parse_ts(s):
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def _is_fresh(payload, now_ts):
    try:
        age = now_ts - _parse_ts(payload["updated"])
        return 0 <= age <= float(payload.get("ttl_sec") or 0)
    except Exception:
        return False


def _alive(entry, now_ts):
    try:
        return _parse_ts(entry.get("expires")) > now_ts
    except Exception:
        return False


def _valid(lever, entry):
    """Registry + clamp + direction validation for one proposal entry."""
    if entry.get("direction") not in DIRECTIONS:
        return None
    v = tuning.clamp(lever, entry.get("value"))
    if v is None:
        return None
    return v


def propose(proposals, set_by, now_ts=None, ttl_sec=None):
    """Author proposal entries, MERGED with other authors' live proposals
    (same locked read->merge->write pattern as fleet_tuning.write_levers —
    organs propose on independent timers and must never clobber each other).
    Each entry: {"value", "direction": "restrict"|"expand", "reason",
    "evidence"}. Unknown levers, invalid directions and unclampable values
    are dropped. Returns the payload written, or None when nothing valid
    survived (or no DB / failed durable write). Never raises."""
    now_ts = now_ts if now_ts is not None else time.time()
    ttl = float(ttl_sec or TTL_SEC)
    out = {}
    for lever, entry in (proposals or {}).items():
        entry = entry or {}
        v = _valid(lever, entry)
        if v is None:
            continue
        ettl = ttl
        try:
            e_req = float(entry.get("ttl_sec") or 0)
            if e_req > 0:
                ettl = max(60.0, min(ttl, e_req))    # shorten-only, like the rail
        except (TypeError, ValueError):
            pass
        out[f"{set_by}:{lever}"] = {
            "lever": lever, "value": v,
            "direction": entry["direction"], "set_by": str(set_by),
            "expires": _iso(now_ts + ettl),
            "reason": str(entry.get("reason") or "")[:200],
            "evidence": str(entry.get("evidence") or "")[:300]}
    if not out:
        return None

    def _merge(prev):
        # [2026-07-21, caught by same-day audit] per-LEVER replacement, as
        # the docstring promises: the first cut dropped ALL of the calling
        # author's prior proposals (set_by filter), so an organ making two
        # propose() calls in one cycle silently lost the first. Keys are
        # '<author>:<lever>', so merged.update(out) replaces exactly the
        # re-proposed stances; the author's other levers ride to expiry (or
        # withdraw()).
        merged = {k: v for k, v in ((prev or {}).get("proposals") or {}).items()
                  if isinstance(v, dict) and k not in out
                  and _alive(v, now_ts) and v.get("lever") in tuning.LEVERS}
        merged.update(out)
        if len(merged) > MAX_PROPOSALS:              # newest expiry survives
            keep = sorted(merged.items(),
                          key=lambda kv: str(kv[1].get("expires") or ""),
                          reverse=True)[:MAX_PROPOSALS]
            merged = dict(keep)
        horizon = now_ts
        for v in merged.values():
            try:
                horizon = max(horizon, _parse_ts(v.get("expires")))
            except Exception:
                horizon = max(horizon, now_ts + ttl)
        return {"updated": _iso(now_ts),
                "ttl_sec": int(max(ttl, horizon - now_ts)),
                "proposals": merged}

    try:
        if store is None:
            return None
        payload = None
        if hasattr(store, "locked_state_update"):
            payload = store.locked_state_update(KEY, _merge)
        if payload is None:
            try:
                prev = store.load_state(KEY) or {}
            except Exception:
                prev = {}
            payload = _merge(prev)
            if not store.save_state(KEY, payload):   # landed-signal contract
                return None
        if hasattr(store, "save_history"):
            store.save_history(KEY, {
                "updated": payload["updated"], "set_by": set_by,
                "proposed": {v["lever"]: v["value"] for v in out.values()}})
        _cache.update(ts=now_ts, payload=payload)
        return payload
    except Exception:
        return None


def withdraw(levers, set_by, now_ts=None):
    """Withdraw MY OWN proposals on the named levers NOW (evidence lapsed) —
    the honest twin of propose, mirroring fleet_tuning.release_levers."""
    now_ts = now_ts if now_ts is not None else time.time()
    names = {str(n) for n in (levers or ())}
    if not names:
        return None

    def _drop(prev):
        kept = {k: v for k, v in ((prev or {}).get("proposals") or {}).items()
                if isinstance(v, dict) and _alive(v, now_ts)
                and v.get("lever") in tuning.LEVERS
                and not (v.get("lever") in names and v.get("set_by") == set_by)}
        horizon = now_ts
        for v in kept.values():
            try:
                horizon = max(horizon, _parse_ts(v.get("expires")))
            except Exception:
                pass
        return {"updated": _iso(now_ts),
                "ttl_sec": int(max(60, horizon - now_ts)),
                "proposals": kept}

    try:
        if store is None:
            return None
        payload = None
        if hasattr(store, "locked_state_update"):
            payload = store.locked_state_update(KEY, _drop)
        if payload is None:
            try:
                prev = store.load_state(KEY) or {}
            except Exception:
                prev = {}
            payload = _drop(prev)
            if not store.save_state(KEY, payload):
                return None
        _cache.update(ts=now_ts, payload=payload)
        return payload
    except Exception:
        return None


def _load(now_ts):
    if now_ts - _cache["ts"] < CACHE_SEC:
        return _cache["payload"]
    payload = None
    try:
        if store is not None:
            payload = store.load_state(KEY) or None
    except Exception:
        payload = None
    _cache.update(ts=now_ts, payload=payload)
    return payload


def fresh_proposals(now_ts=None):
    """Every fresh, unexpired, registry-valid proposal — [] on any failure.
    Consumers filter to the levers/lanes they own and re-derive direction
    against their own defaults before gating."""
    now_ts = now_ts if now_ts is not None else time.time()
    try:
        p = _load(now_ts)
        if not p or not _is_fresh(p, now_ts):
            return []
        out = []
        for entry in (p.get("proposals") or {}).values():
            if not isinstance(entry, dict) or not _alive(entry, now_ts):
                continue
            lever = entry.get("lever")
            v = _valid(lever, entry)
            if v is None:
                continue
            out.append({"lever": lever, "value": v,
                        "direction": entry["direction"],
                        "set_by": entry.get("set_by") or "?",
                        "reason": entry.get("reason") or "",
                        "evidence": entry.get("evidence") or "",
                        "expires": entry.get("expires")})
        return out
    except Exception:
        return []


def proposals_for(levers, now_ts=None):
    """{lever: [proposals]} restricted to the given lever names."""
    want = set(levers or ())
    out = {}
    for p in fresh_proposals(now_ts):
        if p["lever"] in want:
            out.setdefault(p["lever"], []).append(p)
    return out


# ---------------------------------------------------------------------------

def _selftest():
    now = time.time()
    fresh_iso = _iso(now)

    # validation: unknown lever / bad direction / junk value all dropped
    assert _valid("taker.momo_chg", {"value": 5.5, "direction": "restrict"}) == 5.5
    assert _valid("taker.momo_chg", {"value": 99, "direction": "restrict"}) == 6.0
    assert _valid("taker.momo_chg", {"value": 5.5, "direction": "sideways"}) is None
    assert _valid("not.a.lever", {"value": 1, "direction": "restrict"}) is None
    assert _valid("taker.momo_chg", {"value": "junk", "direction": "expand"}) is None

    # reader: stale payload -> []; fresh -> validated entries only
    _cache.update(ts=now, payload={
        "updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 7200,
        "proposals": {"o:taker.momo_chg": {
            "lever": "taker.momo_chg", "value": 5.5, "direction": "restrict",
            "set_by": "o", "expires": _iso(now + 3600)}}})
    assert fresh_proposals(now_ts=now) == []
    _cache.update(ts=now, payload={
        "updated": fresh_iso, "ttl_sec": 7200,
        "proposals": {
            "o:taker.momo_chg": {
                "lever": "taker.momo_chg", "value": 5.5, "direction": "restrict",
                "set_by": "o", "expires": _iso(now + 3600)},
            "o:dead.lever": {
                "lever": "dead.lever", "value": 1, "direction": "restrict",
                "set_by": "o", "expires": _iso(now + 3600)},
            "o:taker.tp": {                          # expired -> dropped
                "lever": "taker.tp", "value": 0.05, "direction": "expand",
                "set_by": "o", "expires": "2020-01-01T00:00:00+00:00"}}})
    got = fresh_proposals(now_ts=now)
    assert len(got) == 1 and got[0]["lever"] == "taker.momo_chg", got
    assert proposals_for({"taker.momo_chg"}, now_ts=now)["taker.momo_chg"][0]["value"] == 5.5
    assert proposals_for({"taker.tp"}, now_ts=now) == {}

    # writer merge semantics against a stubbed store (no DB in selftest)
    if store is not None:
        _real_save = getattr(store, "save_state", None)
        _real_locked = getattr(store, "locked_state_update", None)
        _real_load = getattr(store, "load_state", None)
        _prev = {"updated": fresh_iso, "ttl_sec": 7200, "proposals": {
            "other:taker.tp": {"lever": "taker.tp", "value": 0.05,
                               "direction": "expand", "set_by": "other",
                               "expires": _iso(now + 3600)},
            "me:taker.sl": {"lever": "taker.sl", "value": -0.02,
                            "direction": "restrict", "set_by": "me",
                            "expires": _iso(now + 3600)}}}
        store.save_state = lambda k, s: True
        store.locked_state_update = lambda k, fn: None    # force fallback
        store.load_state = lambda k: dict(_prev)
        p = propose({"taker.momo_chg": {"value": 9.9, "direction": "restrict",
                                        "reason": "r", "evidence": "e"},
                     "not.a.lever": {"value": 1, "direction": "restrict"}},
                    set_by="me", now_ts=now)
        assert p is not None
        keys = set(p["proposals"])
        assert "me:taker.momo_chg" in keys, keys           # mine written
        assert "other:taker.tp" in keys, keys              # other author kept
        assert "me:taker.sl" in keys, \
            f"per-LEVER replacement: an un-re-proposed lever survives ({keys})"
        assert p["proposals"]["me:taker.momo_chg"]["value"] == 6.0   # clamped
        # withdraw: my named proposal goes, the other author's survives
        store.load_state = lambda k: dict(p)
        w = withdraw(["taker.momo_chg"], set_by="me", now_ts=now)
        assert w is not None and "me:taker.momo_chg" not in w["proposals"]
        assert "other:taker.tp" in w["proposals"]
        # landed-signal contract: failed durable write -> None
        store.save_state = lambda k, s: False
        assert propose({"taker.momo_chg": {"value": 5.5,
                                           "direction": "restrict"}},
                       set_by="me", now_ts=now) is None
        if _real_save is not None:
            store.save_state = _real_save
        if _real_locked is not None:
            store.locked_state_update = _real_locked
        if _real_load is not None:
            store.load_state = _real_load
    _cache.update(ts=0.0, payload=None)
    print("fleet_proposals selftest OK (validation, freshness, merge, "
          "withdraw, landed-signal contract)")


if __name__ == "__main__":
    _selftest()
