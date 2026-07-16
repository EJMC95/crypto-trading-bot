#!/usr/bin/env python3
"""fleet_tuning.py — the fleet's bounded GROWTH RAIL (shipped 2026-07-15).

WHY THIS EXISTS (user instruction, 15-Jul): "if the scanner just restricts
then we eventually will only stay still … the scanner needs to be able to
implement opening or altering a strategy or widening something too so growth
can happen fleet wide as I am not going to be able to make fixes and
implement suggestions every occasion in time."

Until now every autonomous actuator in the fleet was RESTRICT-only (vetoes,
clip scales, stake mults ≤ 1.0). Safe — but a fleet that can only say "no"
converges to standing still unless the operator hand-ships every widening.
This module is the sanctioned middle path: a WHITELISTED, HARD-BOUNDED,
TTL'd lever registry through which an authoring organ (the evidence board)
can WIDEN parameters autonomously — but only levers registered here, only
inside their bounds, only on lanes explicitly marked enactable (paper/
scanner lanes today), and only while the author keeps re-asserting the
evidence every cycle: levers EXPIRE back to defaults on their own, so
auto-revert is the resting state, not a feature to remember.

WHAT IT CAN NEVER DO
  - touch a lever that is not in the registry (unknown names are dropped);
  - exceed a lever's hard bounds (values are clamped, never trusted);
  - let the WRONG author touch real money: the `lighter-live` lane (added
    15-Jul by user mandate — live.clip_scale for the board, live.funding.*
    for the experiment judge's promotions, and nothing else) is bound per
    author in AUTHOR_LANES; write_levers() drops any lever outside the
    author's own lanes, anything whose lane isn't in ENACT_LANES, and any
    live.* lever from an unbound author. Go-live and the operator's hard
    caps (SafetyRails) stay operator-only.
  - outlive its TTL: if the author dies or stops re-asserting, every
    consumer is back on its own defaults within TTL_SEC.

CONTRACT (same fail-safe shape as fleet_bus):
  writer:  write_levers({name: {"value", "reason", "evidence"}})
           -> bot_state['fleet-tuning'] with updated+ttl_sec (+ history).
  reader:  get_lever(name, default) -> clamped fresh value, else default.
           No DB / stale / unknown / unparseable -> default. Backtests are
           inert (no DATABASE_URL -> load_state returns None -> defaults).

Adding a lever = one registry line here + one get_lever() call in the
consumer. Trading-book lanes (e.g. Ticket Taker bars) may be REGISTERED
later but stay proposal-only until a review adds their lane to
FLEET_TUNING_ENACT_LANES — the earn-your-wiring path the L2 light walked.
"""
import os
import time
from datetime import datetime, timezone

try:
    import bot_pnl_store as store
except Exception:                                    # pragma: no cover
    store = None

KEY = "fleet-tuning"
TTL_SEC = int(os.environ.get("FLEET_TUNING_TTL_SEC", "7200"))   # 2h re-assert
CACHE_SEC = 60.0

# Lanes the rail may ENACT autonomously. Everything else is proposal-only.
#   paper-scanner — detection/census organs (no trading surface at all)
#   lighter-scout — the scout's ADVISORY ticket emission (widens what gets
#                   GRADED by the brain; the taker's bars still gate fills)
#   lighter-taker — the $1k SHADOW book's bars; enactments on this lane are
#                   REPLAY-GATED by lighter_scout_tuner (both-halves on the
#                   recorded tape) before they are ever written here
#   lighter-live  — (15-Jul user mandate: "i want evidence and scanning for
#                   live bot changes also and for it to implement also")
#                   REAL-MONEY lane, deliberately one lever: a bounded
#                   multiplier on the operator's env clip size. It cannot
#                   raise total live exposure — SafetyRails' notional cap is
#                   operator-only, checked at order time, and divides the
#                   open-position budget by the scaled clip. Evidence bar in
#                   evidence_board.synthesize_live(); every change pushes
#                   URGENT to the phone. Remove the lane from this env to
#                   kill it. Go-live itself (keys, dry_run, caps) remains
#                   operator-only forever.
#   lighter-xp    — the Funding Farmer SHADOW twin's experiment arm (the
#                   judge's candidate parameters; zero real money)
ENACT_LANES = {s.strip() for s in os.environ.get(
    "FLEET_TUNING_ENACT_LANES",
    "paper-scanner,lighter-scout,lighter-taker,lighter-live,lighter-xp"
    ).split(",") if s.strip()}

# [2026-07-16 AUDIT FIX] author -> lanes each author may WRITE. "The judge is
# the ONLY writer of live.funding.*" was pure convention — any author could
# technically have written any enact-lane lever, so one bug in the board's or
# tuner's lever dict could move a real-money bar. Now enforced here, plus a
# name-prefix rule inside the live lane (the board owns live.clip_scale, the
# judge owns live.funding.*). An author absent from this map keeps the old
# behavior for NON-live lanes but can never write live.*.
AUTHOR_LANES = {
    "evidence-board":   {"paper-scanner", "lighter-scout", "lighter-taker",
                         "lighter-live"},
    "scout-tuner":      {"lighter-scout", "lighter-taker"},
    "experiment-judge": {"lighter-xp", "lighter-live"},
}
_LIVE_PREFIX_OWNERS = {"live.clip_scale": "evidence-board",
                       "live.funding.": "experiment-judge"}


def _author_may_write(name, lane, set_by):
    """Lane + live-prefix authorization for one lever write."""
    allowed = AUTHOR_LANES.get(set_by)
    if allowed is not None and lane not in allowed:
        return False
    if lane == "lighter-live":
        for prefix, owner in _LIVE_PREFIX_OWNERS.items():
            if name == prefix or name.startswith(prefix):
                return set_by == owner
        return False          # unknown live lever name: nobody writes it
    if allowed is None and name.startswith("live."):
        return False          # unbound authors never touch real money
    return True

# ---------------------------------------------------------------------------
# THE REGISTRY — every autonomously-tunable lever in the fleet, with hard
# bounds. A lever absent from this dict cannot be moved by any organ.
# ---------------------------------------------------------------------------
LEVERS = {
    # Event Sentinel 🗞️⚡ (event_sentinel.py): ADVISORY news-event organ —
    # nothing trades on it yet, so these levers tune detection sensitivity
    # only (how much corroboration activates an event / freezes a
    # prediction). Bounds keep it between "wire-service confirmation" and
    # "front-page only".
    "evsent.min_sources": {
        "kind": "int", "lo": 2, "hi": 5, "lane": "event-sentinel",
        "note": "distinct headlines to activate an event; default 2"},
    "evsent.severity_bar": {
        "kind": "float", "lo": 0.30, "hi": 0.80, "lane": "event-sentinel",
        "note": "min severity to freeze a sector anticipation; default 0.45"},
    # Gap Scout (scanner-cross-exchange-arb): paper-only census organ.
    "gapscout.prefilter_gap": {
        "kind": "float", "lo": 0.0010, "hi": 0.0030, "lane": "paper-scanner",
        "note": "stage-1 raw-gap bar for book-checking; default 0.0020"},
    "gapscout.max_book_fetches": {
        "kind": "int", "lo": 10, "hi": 60, "lane": "paper-scanner",
        "note": "order books pulled per scan (2/pair); default 30"},
    "gapscout.extra_exchanges": {
        "kind": "csv", "allowed": {"kucoin", "gateio", "mexc", "bitget", "htx"},
        "lane": "paper-scanner",
        "note": "second-tier venues hot-added to the census net"},
    # Lighter Scout 🛰️ — learning-throughput levers: they widen which
    # ADVISORY tickets get emitted (and therefore counterfactually graded by
    # the brain), not what trades. Widening = faster lens learning.
    "scout.ticket_top_n": {
        "kind": "int", "lo": 6, "hi": 15, "lane": "lighter-scout",
        "note": "tickets emitted per lens per scan; default 6"},
    "scout.brk_range_min": {
        "kind": "float", "lo": 0.80, "hi": 0.90, "lane": "lighter-scout",
        "note": "breakout lens: min range_pos to emit; default 0.90"},
    "scout.dip_range_max": {
        "kind": "float", "lo": 0.10, "hi": 0.25, "lane": "lighter-scout",
        "note": "dip lens: max range_pos to emit; default 0.10"},
    "scout.momo_chg_min": {
        "kind": "float", "lo": 2.0, "hi": 3.0, "lane": "lighter-scout",
        "note": "momentum lens: min day change %% to emit; default 3.0"},
    # Ticket Taker 🎫 (SHADOW $1k book) — conviction bars + exit ladder.
    # Bounds = the 21-Jul agenda's own sweep grids. The tuner only writes
    # these after the change beats/matches baseline on BOTH halves of the
    # recorded tape (lighter_ticket_replay through the taker's real code).
    "taker.dip_range": {
        "kind": "float", "lo": 0.05, "hi": 0.15, "lane": "lighter-taker",
        "note": "dip conviction bar (range_pos <=); default 0.05"},
    "taker.brk_range": {
        "kind": "float", "lo": 0.90, "hi": 0.97, "lane": "lighter-taker",
        "note": "breakout conviction bar (range_pos >=); default 0.95"},
    "taker.momo_chg": {
        "kind": "float", "lo": 3.0, "hi": 6.0, "lane": "lighter-taker",
        "note": "momentum conviction bar (day %% >=); default 5.0"},
    "taker.div_gap_pp": {
        "kind": "float", "lo": 300.0, "hi": 700.0, "lane": "lighter-taker",
        "note": "divergence conviction bar (|gap| pp >=); default 500"},
    "taker.tp": {
        "kind": "float", "lo": 0.03, "hi": 0.06, "lane": "lighter-taker",
        "note": "take-profit fraction; default 0.04"},
    "taker.sl": {
        "kind": "float", "lo": -0.04, "hi": -0.02, "lane": "lighter-taker",
        "note": "stop-loss fraction; default -0.03"},
    "taker.max_hold_h": {
        "kind": "float", "lo": 24.0, "hi": 72.0, "lane": "lighter-taker",
        "note": "max hold hours; default 48"},
    # LIVE lane 💰 — one lever, a multiplier on the env clip (LIGHTER_ORDER_USD).
    # SafetyRails' notional cap stays senior at order time: this reshapes
    # clips, it can never raise total live exposure.
    "live.clip_scale": {
        "kind": "float", "lo": 0.5, "hi": 1.5, "lane": "lighter-live",
        "note": "live clip multiplier; 1.0 = the operator's env sizing"},
    # Funding Farmer EXPERIMENT arm 🧪 (the -lshadow twin ONLY — zero real
    # money). The experiment judge runs ONE candidate at a time here; while
    # a candidate runs, the twin is an experiment arm, not a control arm.
    "xp.funding.enter_apr": {
        "kind": "float", "lo": 0.25, "hi": 0.60, "lane": "lighter-xp",
        "note": "shadow twin's funding entry gate; env default 0.40"},
    "xp.funding.take_profit": {
        "kind": "float", "lo": 0.03, "hi": 0.08, "lane": "lighter-xp",
        "note": "shadow twin's TP; env default 0.04"},
    "xp.funding.max_hold_h": {
        "kind": "float", "lo": 24.0, "hi": 96.0, "lane": "lighter-xp",
        "note": "shadow twin's max hold; env default 72"},
    # …and their PROMOTED-to-live counterparts. Written by exactly ONE
    # author — the experiment judge — and only after the paired promotion
    # bar (>=7d, >=30 shadow closes, beats live per-trade on the window AND
    # both halves by the margin). TTL'd: promotion fades back to env
    # defaults when the judge stops re-asserting it.
    "live.funding.enter_apr": {
        "kind": "float", "lo": 0.25, "hi": 0.60, "lane": "lighter-live",
        "note": "PROMOTED funding entry gate; env default 0.40"},
    "live.funding.take_profit": {
        "kind": "float", "lo": 0.03, "hi": 0.08, "lane": "lighter-live",
        "note": "PROMOTED TP; env default 0.04"},
    "live.funding.max_hold_h": {
        "kind": "float", "lo": 24.0, "hi": 96.0, "lane": "lighter-live",
        "note": "PROMOTED max hold; env default 72"},
}


def clamp(name, value):
    """Registry-checked, bounds-clamped value; None if unusable/unknown."""
    spec = LEVERS.get(name)
    if not spec:
        return None
    kind = spec["kind"]
    try:
        if kind == "float":
            return min(spec["hi"], max(spec["lo"], float(value)))
        if kind == "int":
            return int(min(spec["hi"], max(spec["lo"], int(value))))
        if kind == "csv":
            items = value if isinstance(value, (list, tuple)) else str(value).split(",")
            kept = [s.strip() for s in items if s.strip() in spec["allowed"]]
            return ",".join(dict.fromkeys(kept))     # dedup, order-stable
    except (TypeError, ValueError):
        return None
    return None


def _is_fresh(payload, now_ts):
    try:
        u = datetime.fromisoformat(str(payload["updated"]).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        age = now_ts - u.timestamp()
        return 0 <= age <= float(payload.get("ttl_sec") or 0)
    except Exception:
        return False


_cache = {"ts": 0.0, "payload": None}
_immune_cache = {"ts": 0.0, "q": frozenset()}


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


def _quarantined(now_ts):
    """Levers the immune organ ('fleet-immune') has quarantined — get_lever
    returns the caller's default for these, so a sick lever reverts to the
    operator's own value. Fail-safe OPEN: a stale/absent immune payload
    quarantines nothing (a dead immune organ must not paralyze tuning; the
    levers stay bounded + TTL'd regardless)."""
    if now_ts - _immune_cache["ts"] < CACHE_SEC:
        return _immune_cache["q"]
    q = frozenset()
    try:
        if store is not None:
            p = store.load_state("fleet-immune") or {}
            if _is_fresh(p, now_ts):
                q = frozenset((p.get("quarantined_levers") or {}).keys())
    except Exception:
        q = frozenset()
    _immune_cache.update(ts=now_ts, q=q)
    return q


def _lever_alive(entry, now_ts):
    """A lever entry is alive until its own `expires` stamp (falling back to
    never-expired for entries that predate per-lever expiry)."""
    try:
        exp = entry.get("expires")
        if not exp:
            return True
        e = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        if e.tzinfo is None:
            e = e.replace(tzinfo=timezone.utc)
        return e.timestamp() > now_ts
    except Exception:
        return False


def get_lever(name, default, now_ts=None):
    """Fresh, unexpired, un-quarantined, registered, clamped lever value —
    or the caller's default."""
    now_ts = now_ts if now_ts is not None else time.time()
    try:
        if name in _quarantined(now_ts):
            return default                   # immune-quarantined -> operator default
        p = _load(now_ts)
        if not p or not _is_fresh(p, now_ts):
            return default
        entry = (p.get("levers") or {}).get(name)
        if not isinstance(entry, dict) or not _lever_alive(entry, now_ts):
            return default
        v = clamp(name, entry.get("value"))
        return default if v is None else v
    except Exception:
        return default


def active_levers(now_ts=None):
    """{name: entry} of currently-live levers (for display/telemetry)."""
    now_ts = now_ts if now_ts is not None else time.time()
    p = _load(now_ts)
    if not p or not _is_fresh(p, now_ts):
        return {}
    return {k: v for k, v in (p.get("levers") or {}).items()
            if k in LEVERS and isinstance(v, dict) and _lever_alive(v, now_ts)}


def write_levers(levers, set_by="evidence-board", now_ts=None, ttl_sec=None):
    """Author lever entries, MERGED with other authors' live levers (the
    board and the scout tuner share this key — a write must never clobber
    the other author's lane). Drops unknown/out-of-lane levers, clamps every
    value, stamps per-lever `expires` (auto-revert) + payload updated/ttl.
    Returns the payload written, or None when nothing valid survived (or no
    DB). Never raises."""
    now_ts = now_ts if now_ts is not None else time.time()
    ttl = float(ttl_sec or TTL_SEC)

    def _iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")

    out = {}
    for name, entry in (levers or {}).items():
        spec = LEVERS.get(name)
        if not spec or spec["lane"] not in ENACT_LANES:
            continue
        if not _author_may_write(name, spec["lane"], set_by):
            continue
        v = clamp(name, (entry or {}).get("value"))
        if v is None:
            continue
        out[name] = {"value": v, "lane": spec["lane"], "set_by": set_by,
                     "expires": _iso(now_ts + ttl),
                     "reason": str((entry or {}).get("reason") or "")[:200],
                     "evidence": str((entry or {}).get("evidence") or "")[:300]}
    if not out:
        return None
    try:
        if store is None:
            return None
        # merge: keep OTHER authors' still-alive levers; mine replace mine.
        prev = {}
        try:
            prev = store.load_state(KEY) or {}
        except Exception:
            prev = {}
        merged = {k: v for k, v in (prev.get("levers") or {}).items()
                  if k in LEVERS and isinstance(v, dict) and k not in out
                  and v.get("set_by") != set_by and _lever_alive(v, now_ts)}
        merged.update(out)
        # payload ttl covers the longest-lived lever so readers stay fresh
        horizon = now_ts
        for v in merged.values():
            try:
                e = datetime.fromisoformat(str(v.get("expires")).replace("Z", "+00:00"))
                horizon = max(horizon, e.timestamp())
            except Exception:
                horizon = max(horizon, now_ts + ttl)
        payload = {"updated": _iso(now_ts),
                   "ttl_sec": int(max(ttl, horizon - now_ts)),
                   "levers": merged}
        store.save_state(KEY, payload)
        if hasattr(store, "save_history"):
            store.save_history(KEY, {"updated": payload["updated"],
                                     "levers": {k: v["value"] for k, v in out.items()},
                                     "set_by": set_by})
        _cache.update(ts=now_ts, payload=payload)   # readers in-process see it
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------

def _selftest():
    now = time.time()
    # clamping: bounds enforced, unknown dropped, junk rejected
    assert clamp("gapscout.prefilter_gap", 0.0001) == 0.0010     # floor
    assert clamp("gapscout.prefilter_gap", 0.5) == 0.0030        # ceiling
    assert clamp("gapscout.prefilter_gap", 0.0015) == 0.0015
    assert clamp("gapscout.max_book_fetches", 999) == 60
    assert clamp("gapscout.max_book_fetches", "45") == 45
    assert clamp("nonexistent.lever", 1) is None
    assert clamp("gapscout.prefilter_gap", "junk") is None
    # csv: only whitelisted venues survive, deduped
    assert clamp("gapscout.extra_exchanges", "kucoin, binance, gateio,kucoin") == "kucoin,gateio"
    assert clamp("gapscout.extra_exchanges", ["mexc", "evil"]) == "mexc"
    assert clamp("gapscout.extra_exchanges", "binance") == ""
    # reader: stale payload -> default; fresh -> clamped value
    _cache.update(ts=now, payload={"updated": "2020-01-01T00:00:00+00:00",
                                   "ttl_sec": 7200,
                                   "levers": {"gapscout.prefilter_gap": {"value": 0.0015}}})
    assert get_lever("gapscout.prefilter_gap", 0.002, now_ts=now) == 0.002
    fresh_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="seconds")
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {"gapscout.prefilter_gap": {"value": 0.9},
                                              "gapscout.extra_exchanges": {"value": "kucoin"}}})
    assert get_lever("gapscout.prefilter_gap", 0.002, now_ts=now) == 0.0030  # clamped
    assert get_lever("gapscout.extra_exchanges", "", now_ts=now) == "kucoin"
    assert get_lever("unknown.lever", 7, now_ts=now) == 7
    # immune QUARANTINE: a quarantined lever returns the caller's default
    # even with a fresh, in-bounds value present
    _immune_cache.update(ts=now, q=frozenset({"gapscout.prefilter_gap"}))
    assert get_lever("gapscout.prefilter_gap", 0.002, now_ts=now) == 0.002
    assert get_lever("gapscout.extra_exchanges", "", now_ts=now) == "kucoin"  # others fine
    _immune_cache.update(ts=now, q=frozenset())    # clear for later asserts
    assert set(active_levers(now_ts=now)) == {"gapscout.prefilter_gap",
                                              "gapscout.extra_exchanges"}
    # per-lever expiry: a dead lever yields the default even in a fresh payload
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {
                                       "taker.tp": {"value": 0.05,
                                                    "expires": "2020-01-01T00:00:00+00:00"},
                                       "taker.sl": {"value": -0.02}}})   # no expires = alive
    assert get_lever("taker.tp", 0.04, now_ts=now) == 0.04, "expired lever -> default"
    assert get_lever("taker.sl", -0.03, now_ts=now) == -0.02
    assert set(active_levers(now_ts=now)) == {"taker.sl"}
    # writer: unknown/out-of-lane dropped, values clamped, expires stamped,
    # merge keeps OTHER authors' live levers; no-DB -> save is a guarded no-op
    p = write_levers({"gapscout.prefilter_gap": {"value": 0.00001, "reason": "r"},
                      "taker.dip_range": {"value": 0.99},
                      "not.a.lever": {"value": 1}}, set_by="t", now_ts=now)
    if p is not None:                       # store module importable
        assert set(p["levers"]) >= {"gapscout.prefilter_gap", "taker.dip_range"}
        assert p["levers"]["gapscout.prefilter_gap"]["value"] == 0.0010
        assert p["levers"]["taker.dip_range"]["value"] == 0.15       # clamped
        assert p["levers"]["taker.dip_range"]["expires"] > fresh_iso[:10]
    # [2026-07-16 AUDIT] author -> lane binding: only the board may write
    # live.clip_scale, only the judge live.funding.*; nobody else touches
    # the live lane (this was convention only — now enforced)
    assert _author_may_write("live.clip_scale", "lighter-live", "evidence-board")
    assert not _author_may_write("live.clip_scale", "lighter-live", "scout-tuner")
    assert not _author_may_write("live.clip_scale", "lighter-live", "experiment-judge")
    assert _author_may_write("live.funding.enter_apr", "lighter-live", "experiment-judge")
    assert not _author_may_write("live.funding.enter_apr", "lighter-live", "evidence-board")
    assert not _author_may_write("live.clip_scale", "lighter-live", "t")  # unbound
    assert _author_may_write("gapscout.prefilter_gap", "paper-scanner", "t")
    assert not _author_may_write("taker.tp", "lighter-taker", "experiment-judge")
    p_bad = write_levers({"live.clip_scale": {"value": 1.5}}, set_by="scout-tuner",
                         now_ts=now)
    assert p_bad is None or "live.clip_scale" not in p_bad["levers"], \
        "tuner must never write the live lane"
    p_j = write_levers({"xp.funding.enter_apr": {"value": 0.30},
                        "live.funding.enter_apr": {"value": 0.30},
                        "live.clip_scale": {"value": 1.5}},
                       set_by="experiment-judge", now_ts=now)
    if p_j is not None:
        assert "xp.funding.enter_apr" in p_j["levers"]
        assert "live.funding.enter_apr" in p_j["levers"]
        assert p_j["levers"].get("live.clip_scale", {}).get("set_by") != \
            "experiment-judge", "judge must never write the board's clip lever"
    # every registered lever must clamp its own documented default
    for name, spec in LEVERS.items():
        if spec["kind"] in ("float", "int"):
            assert clamp(name, spec["lo"]) == spec["lo"]
            assert clamp(name, spec["hi"]) == spec["hi"]
    print("fleet_tuning selftest OK (incl. author-lane binding)")


if __name__ == "__main__":
    _selftest()
