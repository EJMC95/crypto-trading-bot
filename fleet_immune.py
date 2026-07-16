#!/usr/bin/env python3
"""
fleet_immune.py — 🛡️ the fleet's IMMUNE + SELF-REPAIR organ.

WHY (2026-07-15, from the operator's own framing: "what organ self-repairs…
what organ filters"). The watchdog is a PAIN receptor — it screams when an
organ goes DARK. But the fleet's entire safety model assumes failure ==
DEATH: every fail-safe contract says "stale/silent -> ignore, go neutral."
That leaves a whole failure class uncovered — an organ that is ALIVE BUT
SICK: publishing FRESH, in-TTL, trusted data that is WRONG. That class bit
real money on 15-Jul: a 39h-stale artifact alert (retired whole-book check)
sat in the feed and drove a false live down-scale, because a count-capped
feed never prunes by AGE and the freshness contract only catches death.

This organ covers the two missing biological functions:

  FILTRATION (kidney/liver) — actively clean the shared bloodstream. Prune
    the fleet-alerts feed of AGE-stale fossils and known-toxic antibody
    matches so a dead signal cannot keep circulating. This is the concrete
    SELF-REPAIR action, and it is safe by construction: it only REMOVES
    stale data, never adds.

  ADAPTIVE IMMUNITY (recognize + neutralize) — scan every key organ's FRESH
    payload for invariant violations (fresh-but-wrong), publish the sick
    list to bot_state 'fleet-immune', push NEW sickness to the phone (the
    gap the watchdog leaves), and QUARANTINE a sick growth-rail lever:
    fleet_tuning.get_lever honors 'fleet-immune'.quarantined_levers and
    returns the operator default for a quarantined lever. Quarantine =
    revert to the operator's own value = the safe direction, so a false
    positive is low-harm and self-consistent with restrict-only doctrine.

WHAT IT NEVER DOES: open positions, widen anything, or take any expand-
direction action. It only cleans, flags, and reverts-to-default. It is
fail-safe by the same contract as everything else — a dead immune organ
lifts its quarantines (the body isn't paralyzed by a dead immune system;
the underlying levers stay bounded + TTL'd regardless).

Publishes bot_state 'fleet-immune' {updated, ttl_sec, sick:[...],
quarantined_levers:{name: why}, pruned_alerts, antibodies:[...]}.
Consumers: fleet_tuning.get_lever (quarantine), dashboard, the operator's
phone. Run-once; run_all.sh loops it. --selftest is offline.
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store

try:
    import fleet_tuning as tuning     # for the lever registry bounds
except Exception:  # noqa: BLE001
    tuning = None

KEY = "fleet-immune"
TTL_SEC = int(os.environ.get("IMMUNE_TTL_SEC", "2400"))       # 40 min
MAX_ALERT_AGE_H = float(os.environ.get("IMMUNE_MAX_ALERT_AGE_H", "24"))
NOTIFY_GAP_H = float(os.environ.get("IMMUNE_NOTIFY_GAP_H", "6"))

# Known-toxic ANTIBODIES — specific retired/artefact patterns to neutralize
# on sight regardless of age. Each is (substring, why). The 15-Jul incident
# seeds the first: the retired whole-book live-vs-shadow ratio printed
# "P&L gap +X%" fossils that the paired per-coin check replaced.
ANTIBODIES = [
    ("live vs shadow P&L gap", "retired whole-book divergence artifact "
                               "(replaced 15-Jul by the paired per-coin check)"),
]


def now_ts():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or now_ts(), tz=timezone.utc).isoformat(timespec="seconds")


def _fresh(state, now, max_age_s=None):
    """A payload is usable only if its own `updated` is younger than its ttl
    (or max_age_s override). Fail-safe: unparseable -> not fresh."""
    try:
        u = datetime.fromisoformat(str(state.get("updated")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        age = now - u.timestamp()
        horizon = max_age_s if max_age_s is not None else float(state.get("ttl_sec") or 0)
        return 0 <= age <= horizon
    except Exception:
        return False


# ---------------------------------------------------------------------------
# PURE antibody + invariant checks (selftested offline)
# ---------------------------------------------------------------------------

def alert_fossils(alerts, now, max_age_h=MAX_ALERT_AGE_H):
    """Indices of alerts to PRUNE: older than max_age_h (age-stale fossils),
    OR matching a known-toxic antibody at any age. Returns (keep, pruned)
    where pruned is [{key, why}] for the log/telemetry."""
    keep, pruned = [], []
    for a in alerts or []:
        why = None
        # a persisting condition refreshes last_seen on every dedup-hit
        # (market_context 16-Jul) — age off the latest confirmation, not the
        # first firing, so a still-live alert isn't pruned as a fossil.
        ts = max(a.get("ts") or 0, a.get("last_seen") or 0)
        if now - ts > max_age_h * 3600:
            why = f"age-stale ({(now - ts) / 3600:.0f}h > {max_age_h:g}h)"
        else:
            msg = str(a.get("msg") or "")
            for sub, reason in ANTIBODIES:
                if sub in msg:
                    why = f"antibody: {reason}"
                    break
        if why:
            pruned.append({"key": a.get("key"), "why": why})
        else:
            keep.append(a)
    return keep, pruned


def lever_sickness(levers, now):
    """Registered levers whose current value is OUTSIDE the registry bounds —
    should be impossible (fleet_tuning clamps on write), so a hit means a
    corrupt/legacy blob or a bug. Returns {name: why}. Skips expired levers."""
    out = {}
    if tuning is None:
        return out
    for name, entry in (levers or {}).items():
        if name not in tuning.LEVERS or not isinstance(entry, dict):
            continue
        try:
            if not tuning._lever_alive(entry, now):
                continue
        except Exception:
            pass
        v = entry.get("value")
        clamped = tuning.clamp(name, v)
        if clamped is None:
            out[name] = f"value {v!r} unusable for {name}"
        elif isinstance(v, (int, float)) and isinstance(clamped, (int, float)) \
                and abs(float(v) - float(clamped)) > 1e-9:
            out[name] = f"value {v} outside registry bounds (clamps to {clamped})"
    return out


def organ_invariants(states, now):
    """Fresh-but-WRONG content in the key organs. Each finding is
    {organ, detail}. Only checks organs whose payload is FRESH (a stale
    organ is the watchdog's job, not sickness)."""
    out = []

    def sick(organ, detail):
        out.append({"organ": organ, "detail": detail})

    lm = states.get("lighter-market") or {}
    if _fresh(lm, now):
        nb, nl = lm.get("n_books"), lm.get("n_liquid")
        if isinstance(nb, int) and isinstance(nl, int) and nl > nb:
            sick("lighter-market", f"n_liquid {nl} > n_books {nb} (impossible)")
        med = ((lm.get("stress") or {}).get("med"))
        if isinstance(med, (int, float)) and med < 0:
            sick("lighter-market", f"stress.med {med} < 0 (|premium| can't be negative)")

    lf = states.get("brain-lens-forward") or {}
    if _fresh(lf, now):
        for lens, o in (lf.get("lenses") or {}).items():
            n4h, hit = o.get("n4h"), o.get("hit4h")
            if isinstance(n4h, (int, float)) and n4h < 0:
                sick("brain-lens-forward", f"lens {lens} n4h {n4h} < 0")
            if isinstance(hit, (int, float)) and not (0.0 <= hit <= 1.0):
                sick("brain-lens-forward", f"lens {lens} hit4h {hit} outside [0,1]")

    cen = states.get("gapscout-census") or {}
    if _fresh(cen, now):
        eo = cen.get("episodes_open")
        if isinstance(eo, int) and eo < 0:
            sick("gapscout-census", f"episodes_open {eo} < 0")

    xp = states.get("xp-judge") or {}
    if _fresh(xp, now):
        ph = xp.get("phase")
        if ph is not None and ph not in ("idle", "running", "promoted"):
            sick("xp-judge", f"unknown phase {ph!r}")

    return out


def bot_row_sickness(bot_rows):
    """Impossible values in fresh bot_pnl rows (a NaN or absurd pnl_pct
    poisons the brain's grading). Returns [{organ, detail}]."""
    out = []
    for r in bot_rows or []:
        bot = str(r.get("bot") or "")
        for f in ("pnl_abs", "equity", "pnl_pct"):
            v = r.get(f)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                out.append({"organ": bot, "detail": f"{f}={v!r} not numeric"})
                continue
            if fv != fv or fv in (float("inf"), float("-inf")):   # NaN/inf
                out.append({"organ": bot, "detail": f"{f} is NaN/inf"})
        pp = r.get("pnl_pct")
        try:
            if pp is not None and abs(float(pp)) > 50:            # >5000%
                out.append({"organ": bot, "detail": f"pnl_pct {pp} absurd (>5000%)"})
        except (TypeError, ValueError):
            pass
    return out


# ---------------------------------------------------------------------------

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send_push(title, body, priority="high"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", "shield")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[fleet-immune] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def run_once():
    now = now_ts()
    prior = store.load_state(KEY) or {}
    prior_sick = set(prior.get("notified") or [])

    # one batched beat instead of five round-trips (fail-safe: batch {} on
    # DB failure -> every organ reads as absent, same as load_state failing)
    _keys = ("lighter-market", "brain-lens-forward", "gapscout-census",
             "xp-judge", "fleet-tuning")
    _batch = store.fetch_states(_keys) if hasattr(store, "fetch_states") else {}
    states = {k: (_batch.get(k) or store.load_state(k) or {}) for k in _keys} \
        if not _batch else {k: (_batch.get(k) or {}) for k in _keys}
    try:
        bot_rows = store.fetch_bot_pnl() or []
    except Exception:
        bot_rows = []

    # --- FILTRATION: prune the alert bloodstream ---------------------------
    pruned = []
    raw = store.load_state("fleet-alerts") or {}
    alerts = raw.get("alerts") or []
    keep, pruned = alert_fossils(alerts, now)
    if pruned:
        # re-read immediately before write to shrink the append race window
        cur = (store.load_state("fleet-alerts") or {}).get("alerts") or alerts
        keep2, _ = alert_fossils(cur, now)
        store.save_state("fleet-alerts", {"alerts": keep2})

    # --- ADAPTIVE IMMUNITY: recognize sickness -----------------------------
    q = lever_sickness((states["fleet-tuning"] or {}).get("levers") or {}, now)
    sick = (organ_invariants(states, now) + bot_row_sickness(bot_rows)
            + [{"organ": "fleet-tuning", "detail": f"{n}: {w}"} for n, w in q.items()])

    # [2026-07-16 AUDIT FIX] sick-ids must be VALUE-STABLE: detail strings
    # embed live numbers ("n_liquid 151 > n_books 100"), so a persistently
    # sick organ minted a NEW id every cycle and re-paged the phone forever.
    # Normalize digits out of the identity; the full detail stays in `sick`.
    _norm = lambda d: re.sub(r"[-+]?\d[\d.,]*", "#", str(d))  # noqa: E731
    sick_ids = {f"{s['organ']}:{_norm(s['detail'])}" for s in sick}
    new_sick = sick_ids - prior_sick

    last_push = float(prior.get("last_push") or 0)
    payload = {
        "updated": _iso(now), "ttl_sec": TTL_SEC,
        "sick": sick[:30],
        "quarantined_levers": q,
        "pruned_alerts": len(pruned),
        "pruned_detail": pruned[:10],
        "antibodies": [a[0] for a in ANTIBODIES],
        "notified": sorted(sick_ids)[:50],
        # [2026-07-16 AUDIT FIX] last_push must be IN the saved payload — the
        # first save dropped it, so the stored gap survived exactly one cycle
        # and NOTIFY_GAP_H was effectively ~2 cycles.
        "last_push": last_push,
    }
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "n_sick": len(sick),
                                     "quarantined": sorted(q),
                                     "pruned_alerts": len(pruned)})
        except Exception:
            pass

    if pruned:
        print(f"[fleet-immune] filtered {len(pruned)} toxic/stale alert(s): "
              + "; ".join(f"{p['key']} ({p['why']})" for p in pruned[:5]), flush=True)
    for s in sick:
        print(f"[fleet-immune] SICK {s['organ']}: {s['detail']}", flush=True)
    if q:
        print(f"[fleet-immune] QUARANTINED levers: {sorted(q)}", flush=True)
    # push only genuinely NEW sickness (dedup vs prior), min gap per organ
    if new_sick and now - last_push >= NOTIFY_GAP_H * 3600:
        body = "\n".join(sorted(new_sick)[:8]) + (
            f"\n\nquarantined: {sorted(q)}" if q else "")
        if send_push(f"🛡️ fleet immune: {len(new_sick)} new sickness finding(s)", body):
            payload["last_push"] = now
            store.save_state(KEY, payload)

    print(f"[fleet-immune] {_iso(now)} sick={len(sick)} quarantined={len(q)} "
          f"pruned={len(pruned)} new={len(new_sick)}", flush=True)
    return payload


# ---------------------------------------------------------------------------

def _selftest():
    now = 1_800_000_000.0
    fresh = _iso(now)

    # FILTRATION: age-stale + antibody pruned; recent kept
    alerts = [
        {"key": "live-shadow-gap", "ts": now - 39 * 3600,
         "msg": "⚠️ Funding Farmer live vs shadow P&L gap +5.4%"},   # BOTH stale+antibody
        {"key": "stale-live:x", "ts": now - 30 * 3600, "msg": "old"},  # age-stale
        {"key": "fresh-real", "ts": now - 3600, "msg": "recent legit"},  # keep
        {"key": "antibody-fresh", "ts": now - 60,
         "msg": "live vs shadow P&L gap +9%"},                        # fresh BUT toxic
    ]
    keep, pruned = alert_fossils(alerts, now)
    assert [a["key"] for a in keep] == ["fresh-real"], keep
    assert len(pruned) == 3
    assert any("antibody" in p["why"] for p in pruned)
    assert any("age-stale" in p["why"] for p in pruned)
    # [2026-07-16 AUDIT] a persisting alert (old ts, fresh last_seen from the
    # dedup-hit refresh) is NOT a fossil — must be kept
    keep2, _ = alert_fossils(
        [{"key": "persisting", "ts": now - 30 * 3600,
          "last_seen": now - 3600, "msg": "still confirmed"}], now)
    assert [a["key"] for a in keep2] == ["persisting"], keep2

    # LEVER SICKNESS: an out-of-bounds value on a real lever is caught;
    # in-bounds and expired are not
    if tuning is not None:
        good = _iso(now + 3600)
        levers = {
            "live.clip_scale": {"value": 9.0, "expires": good},       # >1.5 ceiling
            "gapscout.prefilter_gap": {"value": 0.002, "expires": good},  # ok
            "taker.tp": {"value": 99.0, "expires": "2000-01-01T00:00:00+00:00"},  # expired
        }
        q = lever_sickness(levers, now)
        assert set(q) == {"live.clip_scale"}, q

    # ORGAN INVARIANTS: impossible fresh content flagged; stale ignored
    states = {
        "lighter-market": {"updated": fresh, "ttl_sec": 900,
                           "n_books": 100, "n_liquid": 150,           # impossible
                           "stress": {"med": -3}},                    # impossible
        "brain-lens-forward": {"updated": fresh, "ttl_sec": 26000,
                               "lenses": {"dip": {"n4h": -5, "hit4h": 1.4}}},
        "gapscout-census": {"updated": fresh, "ttl_sec": 3600, "episodes_open": -1},
        "xp-judge": {"updated": fresh, "ttl_sec": 10800, "phase": "haywire"},
        "stale-organ": {"updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 900,
                        "n_books": 1, "n_liquid": 999},
    }
    inv = organ_invariants(states, now)
    organs = {i["organ"] for i in inv}
    assert organs == {"lighter-market", "brain-lens-forward",
                      "gapscout-census", "xp-judge"}, organs
    # the stale organ's impossible content is NOT flagged (death != sickness)
    assert not any(i["organ"] == "stale-organ" for i in inv)

    # BOT ROW SICKNESS: NaN, inf, absurd pnl_pct
    rows = [{"bot": "a", "pnl_pct": float("nan")},
            {"bot": "b", "equity": float("inf")},
            {"bot": "c", "pnl_pct": 123.0},          # 12300%
            {"bot": "d", "pnl_pct": 0.05, "equity": 1000.0}]   # fine
    bs = bot_row_sickness(rows)
    assert {b["organ"] for b in bs} == {"a", "b", "c"}, bs

    # empty / healthy fleet -> nothing
    assert alert_fossils([], now) == ([], [])
    assert organ_invariants({}, now) == []
    assert bot_row_sickness([]) == []
    print("fleet_immune selftest OK (filtration age+antibody, lever sickness, "
          "organ invariants, bot-row sickness, death!=sickness)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
