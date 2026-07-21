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
#   event-sentinel — [2026-07-21 operator mandate: organs must be able to
#                   implement changes] the sentinel's OWN detection bars
#                   (evsent.min_sources / evsent.severity_bar): sensitivity
#                   of an ADVISORY news organ, zero trading surface — the
#                   same class as paper-scanner. Until today this lane was
#                   registered but unreachable: not enactable AND no author
#                   bound, so the levers could never move at all.
ENACT_LANES = {s.strip() for s in os.environ.get(
    "FLEET_TUNING_ENACT_LANES",
    "paper-scanner,lighter-scout,lighter-taker,lighter-live,lighter-xp,"
    "event-sentinel"
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
    # [2026-07-21] the sentinel tunes ONLY its own detection lane
    "event-sentinel":   {"event-sentinel"},
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
    # [2026-07-21 IMB-20, review-sanctioned] divergence-ticket emission gap
    # (TRUE pp since the basis fix). The winner lens (only one positive at
    # every horizon, ehit4h Wilson lo 0.509) had no diet lever — the one
    # registry expand-asymmetry the audit flagged. Lower = more advisory
    # tickets; fills stay gated by the taker's bars.
    "scout.div_gap_pp": {
        "kind": "float", "lo": 20.0, "hi": 75.0, "lane": "lighter-scout",
        "note": "divergence-ticket emission gap (TRUE pp); env default 37.5"},
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
        # [2026-07-17] bounds /8 with the fleet-wide funding BASIS FIX: the
        # apr these pp are measured against was 8x TRUE. Same bar, true units.
        "kind": "float", "lo": 37.5, "hi": 87.5, "lane": "lighter-taker",
        "note": "divergence conviction bar (|gap| pp >=); default 62.5"},
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
        # [2026-07-17] bounds /8 with the BASIS FIX — TRUE apr now.
        "kind": "float", "lo": 0.03125, "hi": 0.075, "lane": "lighter-xp",
        "note": "shadow twin's funding entry gate (TRUE apr); env default 0.05"},
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
        # [2026-07-17] bounds /8 with the BASIS FIX — TRUE apr now. 💰
        "kind": "float", "lo": 0.03125, "hi": 0.075, "lane": "lighter-live",
        "note": "PROMOTED funding entry gate (TRUE apr); env default 0.05"},
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
_prop_cache = {"ts": 0.0, "h": frozenset()}


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


def _live_hurting(now_ts):
    """[2026-07-16 late, operator: 'and with the new rule, real money bots
    too'] LIVE-lane levers whose fleet_proprioception verdict is HURTING —
    get_lever returns the caller's env default for these, so a measured-bad
    lever stops steering REAL MONEY at the consumer, every loop, without
    waiting out the board's 10-min cycle, the judge's hourly cycle, or the
    lever's TTL. Same one-hook-protects-every-consumer pattern as the
    immune quarantine above: the funding bot's apply_levers and both live
    bots' clip read (venues VenueContext.order_usd) all pass through here.
    LIVE LANE ONLY: shadow lanes keep TTL semantics — their authors already
    stop re-asserting on hurting, and an instant consumer-side revert there
    would distort the learning dynamics the 21-Jul review grades. Fail-safe
    OPEN: a dark/stale organ reverts nothing (a dead sense must not steer;
    levers stay bounded + TTL'd regardless). Restrict-only by construction:
    the hook can only ever hand back the operator's own default."""
    if now_ts - _prop_cache["ts"] < CACHE_SEC:
        return _prop_cache["h"]
    h = frozenset()
    try:
        if store is not None:
            p = store.load_state("fleet-proprioception") or {}
            if _is_fresh(p, now_ts):
                h = frozenset(
                    k for k, v in (p.get("verdicts") or {}).items()
                    if isinstance(v, dict) and v.get("verdict") == "hurting")
    except Exception:
        h = frozenset()
    _prop_cache.update(ts=now_ts, h=h)
    return h


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
    """Fresh, unexpired, un-quarantined, not-hurting-on-live, registered,
    clamped lever value — or the caller's default."""
    now_ts = now_ts if now_ts is not None else time.time()
    try:
        spec = LEVERS.get(name)
        # [2026-07-17 AUDIT] THE LANE GATE, at the CONSUMER. FLEET_TUNING_ENACT_LANES
        # is documented as the per-lane kill switch — "Remove the lane from this
        # env to kill it" (:74) — but the check lived ONLY in write_levers
        # (:385). get_lever tested quarantine, live-hurting, freshness, expiry
        # and clamp, and never the lane. Measured with the live lane removed:
        #   get_lever('live.clip_scale', 1.0)         -> 1.5     (should be 1.0)
        #   get_lever('live.funding.enter_apr', 0.05) -> 0.075   (should be 0.05)
        # i.e. throwing the documented switch changed nothing a bot reads; an
        # already-written lever kept steering REAL MONEY until its TTL lapsed —
        # and only if the AUTHOR's service also got the env and was redeployed.
        # This is the exact shape of the 17-Jul FLEET_RISK_MODE finding (a kill
        # switch only some consumers honoured), which is now a CLAUDE.md rule:
        # a switch that does not reach the consumer is not a switch. Checked
        # FIRST, so a killed lane short-circuits every other read. `not spec`
        # keeps the old behaviour for unregistered names (they fell through to
        # clamp() -> None -> default anyway). Inert by default: the shipped
        # ENACT_LANES contains all five lanes.
        if not spec or spec.get("lane") not in ENACT_LANES:
            return default                   # lane switched off -> operator default
        if name in _quarantined(now_ts):
            return default                   # immune-quarantined -> operator default
        if (spec.get("lane") == "lighter-live"
                and name in _live_hurting(now_ts)):
            return default                   # measured-bad LIVE lever -> operator default
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
    """{name: entry} of currently-live levers (for display/telemetry).

    [2026-07-17 AUDIT] Honours ENACT_LANES too, so this cannot report a lever
    as ACTIVE that get_lever now ignores — the dashboard's 🎚️ count and the
    Autonomy card read this, and a switched-off lane still listed here would
    tell the operator the switch had not worked. Display must agree with the
    consumer; a telemetry view that disagrees with the actuator is how you get
    talked out of a correct kill."""
    now_ts = now_ts if now_ts is not None else time.time()
    p = _load(now_ts)
    if not p or not _is_fresh(p, now_ts):
        return {}
    return {k: v for k, v in (p.get("levers") or {}).items()
            if k in LEVERS and isinstance(v, dict) and _lever_alive(v, now_ts)
            and LEVERS[k].get("lane") in ENACT_LANES}


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
        # [2026-07-16] optional per-entry ttl_sec — may only SHORTEN the
        # call-level TTL (floor 60s), never extend it: faster auto-revert is
        # always allowed, a longer-lived lever never is. The board uses this
        # to give its real-money live.clip_scale a 30-min leash while the
        # scanner levers keep the 2h default.
        ettl = ttl
        try:
            e_req = float((entry or {}).get("ttl_sec") or 0)
            if e_req > 0:
                ettl = max(60.0, min(ttl, e_req))
        except (TypeError, ValueError):
            pass
        out[name] = {"value": v, "lane": spec["lane"], "set_by": set_by,
                     "expires": _iso(now_ts + ettl),
                     "reason": str((entry or {}).get("reason") or "")[:200],
                     "evidence": str((entry or {}).get("evidence") or "")[:300]}
    if not out:
        return None

    def _merge_payload(prev):
        """Merge MY levers over the other authors' still-alive levers. Pure —
        runs under the store's advisory lock when available."""
        merged = {k: v for k, v in ((prev or {}).get("levers") or {}).items()
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
        return {"updated": _iso(now_ts),
                "ttl_sec": int(max(ttl, horizon - now_ts)),
                "levers": merged}

    try:
        if store is None:
            return None
        # [2026-07-16 MERGE-RACE FIX] three authors write this key on
        # independent timers; a merge off a stale read silently dropped the
        # other author's just-written levers. The advisory-locked update
        # serializes read->merge->write; the unlocked path stays as the
        # fallback so a lock failure degrades to exactly today's behavior.
        payload = None
        if hasattr(store, "locked_state_update"):
            payload = store.locked_state_update(KEY, _merge_payload)
        if payload is None:
            prev = {}
            try:
                prev = store.load_state(KEY) or {}
            except Exception:
                prev = {}
            payload = _merge_payload(prev)
            # [2026-07-16 F3 REPAIR — adversarial-verify finding] save_state
            # returns False on a failed write and NEVER raises; ignoring it
            # returned a truthy payload that never persisted (reads-OK/
            # writes-failing DB — e.g. Postgres flipped read-only), which
            # false-positived every "landed" check downstream, including the
            # board's live_write_ok guard on the real-money push. None on a
            # failed durable write is the documented contract — honor it.
            if not store.save_state(KEY, payload):
                return None
        if hasattr(store, "save_history"):
            store.save_history(KEY, {"updated": payload["updated"],
                                     "levers": {k: v["value"] for k, v in out.items()},
                                     "set_by": set_by})
        _cache.update(ts=now_ts, payload=payload)   # readers in-process see it
        return payload
    except Exception:
        return None


def _released_payload(prev, names, set_by, now_ts):
    """Pure: `prev` minus MY named levers — other authors' levers and my
    unnamed levers survive, dead entries are pruned, updated/ttl recomputed.
    Selftested offline; runs under the store's advisory lock when available."""
    def _iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
    levers = {k: v for k, v in ((prev or {}).get("levers") or {}).items()
              if k in LEVERS and isinstance(v, dict) and _lever_alive(v, now_ts)
              and not (k in names and v.get("set_by") == set_by)}
    horizon = now_ts
    for v in levers.values():
        try:
            e = datetime.fromisoformat(str(v.get("expires")).replace("Z", "+00:00"))
            horizon = max(horizon, e.timestamp())
        except Exception:
            horizon = max(horizon, now_ts + TTL_SEC)
    return {"updated": _iso(now_ts),
            "ttl_sec": int(max(60, horizon - now_ts)),
            "levers": levers}


def release_levers(names, set_by, now_ts=None):
    """[2026-07-16] Withdraw MY OWN named levers NOW — auto-revert without
    the TTL wait. The honest twin of write_levers for the moment an author's
    evidence LAPSES: the lever disappears from the rail (consumers fall back
    to operator defaults immediately) instead of lingering to expiry or
    being overwritten with a no-op value that downstream graders would
    treat as a real stance. An author can never release another author's
    lever. Returns the payload written; None only when no lever names were
    given or the DB path is unavailable (callers retry). Never raises."""
    now_ts = now_ts if now_ts is not None else time.time()
    names = {str(n) for n in (names or ())}
    if not names:
        return None
    try:
        if store is None:
            return None
        payload = None
        if hasattr(store, "locked_state_update"):
            payload = store.locked_state_update(
                KEY, lambda prev: _released_payload(prev, names, set_by, now_ts))
        if payload is None:
            prev = {}
            try:
                prev = store.load_state(KEY) or {}
            except Exception:
                prev = {}
            payload = _released_payload(prev, names, set_by, now_ts)
            # [2026-07-16 F3 REPAIR] same landed-signal contract as
            # write_levers: a failed durable write must return None.
            if not store.save_state(KEY, payload):
                return None
        if hasattr(store, "save_history"):
            store.save_history(KEY, {"updated": payload["updated"],
                                     "released": sorted(names),
                                     "set_by": set_by})
        _cache.update(ts=now_ts, payload=payload)
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
    # 🦾 LIVE hurting-revert (the real-money consumer hook): a fresh HURTING
    # verdict on a lighter-live lever returns the caller's env default at
    # the consumer; SHADOW lanes keep their TTL semantics (lane-scoped)
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {"live.clip_scale": {"value": 1.25},
                                              "live.funding.enter_apr": {"value": 0.0375},
                                              "taker.tp": {"value": 0.05}}})
    _prop_cache.update(ts=now, h=frozenset({"live.clip_scale",
                                            "live.funding.enter_apr",
                                            "taker.tp"}))
    assert get_lever("live.clip_scale", 1.0, now_ts=now) == 1.0, \
        "hurting LIVE lever -> operator default"
    assert get_lever("live.funding.enter_apr", 0.05, now_ts=now) == 0.05
    assert get_lever("taker.tp", 0.04, now_ts=now) == 0.05, \
        "shadow lane keeps TTL semantics (author-side skip owns it)"
    _prop_cache.update(ts=now, h=frozenset())
    assert get_lever("live.clip_scale", 1.0, now_ts=now) == 1.25, \
        "verdict cleared -> the asserted lever applies again"
    assert get_lever("live.funding.enter_apr", 0.05, now_ts=now) == 0.0375
    _cache.update(ts=now, payload={"updated": fresh_iso, "ttl_sec": 7200,
                                   "levers": {"gapscout.prefilter_gap": {"value": 0.9},
                                              "gapscout.extra_exchanges": {"value": "kucoin"}}})
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
    # merge keeps OTHER authors' live levers. Writer tests run against a
    # stubbed ALWAYS-SUCCEEDS store (no local DB) so the merge/clamp logic
    # executes; the failed-write landed-signal contract is pinned right
    # after with the opposite stub.
    _real_save = getattr(store, "save_state", None) if store else None
    _real_locked = getattr(store, "locked_state_update", None) if store else None
    if store is not None:
        store.save_state = lambda k, s: True
        store.locked_state_update = lambda k, fn: None    # force the fallback
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
                        "live.funding.enter_apr": {"value": 0.0375},
                        "live.clip_scale": {"value": 1.5}},
                       set_by="experiment-judge", now_ts=now)
    if p_j is not None:
        assert "xp.funding.enter_apr" in p_j["levers"]
        assert "live.funding.enter_apr" in p_j["levers"]
        assert p_j["levers"].get("live.clip_scale", {}).get("set_by") != \
            "experiment-judge", "judge must never write the board's clip lever"
    # per-entry ttl_sec: shortens the leash, can never extend it
    p_ttl = write_levers({"live.clip_scale": {"value": 1.25, "ttl_sec": 1800},
                          "gapscout.prefilter_gap": {"value": 0.0015},
                          "gapscout.max_book_fetches": {"value": 45,
                                                        "ttl_sec": 999999}},
                         set_by="evidence-board", now_ts=now)
    if p_ttl is not None:
        from datetime import timedelta
        _short = datetime.fromtimestamp(now + 1800, tz=timezone.utc).isoformat(timespec="seconds")
        _full = datetime.fromtimestamp(now + TTL_SEC, tz=timezone.utc).isoformat(timespec="seconds")
        assert p_ttl["levers"]["live.clip_scale"]["expires"] == _short, \
            "per-entry ttl must shorten expiry"
        assert p_ttl["levers"]["gapscout.prefilter_gap"]["expires"] == _full
        assert p_ttl["levers"]["gapscout.max_book_fetches"]["expires"] == _full, \
            "per-entry ttl must never EXTEND the call-level TTL"
    # release: an author withdraws its OWN lever instantly; other authors'
    # levers and its own unnamed levers survive; dead entries are pruned
    _far = datetime.fromtimestamp(now + 3600, tz=timezone.utc).isoformat(timespec="seconds")
    _prev = {"levers": {
        "live.clip_scale": {"value": 1.25, "set_by": "evidence-board",
                            "expires": _far},
        "gapscout.prefilter_gap": {"value": 0.0015, "set_by": "evidence-board",
                                   "expires": _far},
        "live.funding.enter_apr": {"value": 0.0375, "set_by": "experiment-judge",
                                   "expires": _far},
        "taker.tp": {"value": 0.05, "set_by": "scout-tuner",
                     "expires": "2020-01-01T00:00:00+00:00"}}}
    rp = _released_payload(_prev, {"live.clip_scale", "live.funding.enter_apr"},
                           "evidence-board", now)
    assert "live.clip_scale" not in rp["levers"], "own named lever released"
    assert "live.funding.enter_apr" in rp["levers"], \
        "another author's lever must survive my release"
    assert "gapscout.prefilter_gap" in rp["levers"], "my unnamed lever survives"
    assert "taker.tp" not in rp["levers"], "dead entries pruned in passing"
    assert rp["ttl_sec"] >= 60
    assert release_levers([], "evidence-board", now_ts=now) is None
    # [F3 REPAIR] the landed-signal contract: a reads-OK/writes-FAILING
    # store (save_state -> False, locked path unavailable) must yield None
    # from BOTH authors — a payload that never persisted must never read
    # as a landed real-money write (the board's live_write_ok depends on it)
    if store is not None:
        store.save_state = lambda k, s: False
        assert write_levers({"live.clip_scale": {"value": 0.75}},
                            set_by="evidence-board", now_ts=now) is None, \
            "failed durable write must not report as landed"
        assert release_levers(["live.clip_scale"], "evidence-board",
                              now_ts=now) is None, \
            "failed durable release must not report as landed"
        if _real_save is not None:
            store.save_state = _real_save
        if _real_locked is not None:
            store.locked_state_update = _real_locked
    # every registered lever must clamp its own documented default
    for name, spec in LEVERS.items():
        if spec["kind"] in ("float", "int"):
            assert clamp(name, spec["lo"]) == spec["lo"]
            assert clamp(name, spec["hi"]) == spec["hi"]

    # [2026-07-17 AUDIT] THE LANE KILL SWITCH, ASSERTED AT THE CONSUMER.
    # ENACT_LANES only ever gated write_levers, so a lever ALREADY WRITTEN kept
    # steering real money through a thrown switch. The old suite tested the
    # write side and called it covered — but the operator throws this switch to
    # stop a lever that is already in force, which is precisely the case nothing
    # tested. Drive get_lever/active_levers directly with the live lane removed.
    _saved_lanes = ENACT_LANES
    _saved_load, _saved_q, _saved_h = _load, _quarantined, _live_hurting
    try:
        _t = 1_800_000_000.0

        def _ts(ts):
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        _p = {"updated": _ts(_t), "ttl_sec": 3600, "levers": {
            "live.clip_scale": {"value": 1.5, "expires": _ts(_t + 3600),
                                "set_by": "evidence-board"},
            "taker.dip_range": {"value": 0.11, "expires": _ts(_t + 3600),
                                "set_by": "scout-tuner"}}}
        globals()["_load"] = lambda now_ts=None: _p
        globals()["_quarantined"] = lambda now_ts=None: set()
        globals()["_live_hurting"] = lambda now_ts=None: set()

        globals()["ENACT_LANES"] = {"paper-scanner", "lighter-scout",
                                    "lighter-taker", "lighter-live", "lighter-xp"}
        assert get_lever("live.clip_scale", 1.0, _t) == 1.5, "shipped lanes: enacted"
        assert get_lever("taker.dip_range", 0.08, _t) == 0.11
        assert set(active_levers(_t)) == {"live.clip_scale", "taker.dip_range"}

        # the operator kills ONLY the live lane
        globals()["ENACT_LANES"] = {"paper-scanner", "lighter-scout",
                                    "lighter-taker", "lighter-xp"}
        assert get_lever("live.clip_scale", 1.0, _t) == 1.0, \
            "REGRESSION: a killed lane still steers REAL MONEY at the consumer"
        assert get_lever("taker.dip_range", 0.08, _t) == 0.11, \
            "killing one lane must not disturb another"
        assert set(active_levers(_t)) == {"taker.dip_range"}, \
            "display must not report a killed lane as active"

        # kill everything -> every consumer reads the operator's env default
        globals()["ENACT_LANES"] = set()
        assert get_lever("live.clip_scale", 1.0, _t) == 1.0
        assert get_lever("taker.dip_range", 0.08, _t) == 0.08
        assert active_levers(_t) == {}
        # an UNREGISTERED name keeps its old behaviour (default), not a crash
        assert get_lever("nope.not.a.lever", 7.0, _t) == 7.0
    finally:
        globals()["ENACT_LANES"] = _saved_lanes
        globals()["_load"] = _saved_load
        globals()["_quarantined"] = _saved_q
        globals()["_live_hurting"] = _saved_h

    print("fleet_tuning selftest OK (incl. author-lane binding + per-entry ttl "
          "+ the ENACT_LANES kill switch at the CONSUMER)")


if __name__ == "__main__":
    _selftest()
