#!/usr/bin/env python3
"""
fleet_regen.py — 🩹 the fleet's REGENERATION organ (self-repair, tier 2).

WHY (2026-07-15, operator: "what organ self-repairs"). The immune organ
(fleet_immune) RECOGNIZES sickness and QUARANTINES/filters. Regeneration is
the next tier: it RESTORES. When a STATEFUL organ's bot_state gets wedged on
fresh-but-wrong content (a corrupt phase machine, an impossible payload that
would poison every future cycle), regen heals it — restoring the last-good
history snapshot, or resetting to a registered SAFE baseline when no clean
history exists — so the organ's next natural cycle recovers on a clean base.

Biology: the immune system isolates the pathogen; regeneration rebuilds the
damaged tissue. Both are needed — quarantine stops the harm spreading,
regen undoes it.

WHAT IT REPAIRS — only STATEFUL intelligence organs whose corrupt state
COMPOUNDS across cycles (their key is in REPAIRABLE). Stateless-recompute
organs (the scout rebuilds from scratch each run) self-heal on their own
next cycle and are left alone. It NEVER touches live/account state, bot_pnl
rows, or the ledgers — real positions live on the venue, not in a blob regen
could rewrite.

SAFETY: restores are content-only and carry the snapshot's ORIGINAL age +
a `_regen` marker, so a restored payload reads as exactly what it is (an
aged last-good snapshot the fail-safe freshness contract treats as stale
until the organ republishes) — regen never asserts old data as current.
Only acts on organs the immune organ has flagged SICK. Logs + phone-pushes
every repair. Fail-safe: no DB / no history -> does nothing.

Publishes bot_state 'fleet-regen' (repairs done, needs-operator list).
Run-once; run_all.sh loops it. --selftest is offline.
"""
import copy
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import fleet_immune as immune

KEY = "fleet-regen"
TTL_SEC = int(os.environ.get("REGEN_TTL_SEC", "2400"))
NOTIFY_GAP_H = float(os.environ.get("REGEN_NOTIFY_GAP_H", "6"))
MAX_SNAPSHOT_AGE_H = float(os.environ.get("REGEN_MAX_SNAP_AGE_H", "24"))

# Stateful organs whose corrupt state COMPOUNDS -> worth restoring. Each maps
# to a SAFE baseline used only when no clean history snapshot exists. The
# baseline is the organ's "resting state" — the same place it starts cold.
REPAIRABLE = {
    "xp-judge": {"phase": "idle"},          # phase machine -> back to idle
    "scout-tuner": {},                       # stateless-ish; empty restart
    "gapscout-census": {},
}


def now_ts():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or now_ts(), tz=timezone.utc).isoformat(timespec="seconds")


def _snap_ts(snap):
    try:
        u = datetime.fromisoformat(str(snap.get("updated")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        return u.timestamp()
    except Exception:
        return None


def is_clean(key, payload, now):
    """True if this payload violates NONE of the immune organ's invariants
    for its organ. Reuses the immune checks so 'clean' means exactly 'not
    what the immune organ would flag'.

    [2026-07-15 AUDIT FIX] immune.organ_invariants freshness-gates every
    organ (it only inspects payloads whose own `updated` is fresh) — but a
    HISTORY snapshot carries its original (aged) `updated`, so the invariant
    check was being SKIPPED and is_clean returned True for corrupt content in
    the 3–24h window regen is meant to repair. Stamp a fresh `updated` ONLY
    for the content inspection (a shallow copy — the restored snapshot keeps
    its real age)."""
    if not payload:
        return False
    probe = dict(payload)
    probe["updated"] = _iso(now)          # inspect content, not freshness
    probe["ttl_sec"] = max(int(probe.get("ttl_sec") or 0), 3600)
    findings = immune.organ_invariants({key: probe}, now)
    return not any(f["organ"] == key for f in findings)


def pick_last_good(key, history, now, max_age_h=MAX_SNAPSHOT_AGE_H):
    """Newest→oldest history snapshot that is BOTH invariant-clean AND not
    older than max_age_h. Returns (snapshot, age_h) or (None, None). Pure —
    selftested. (Restoring a very old snapshot would trade one problem for
    another, so age-bound it; older than that -> use the SAFE baseline.)"""
    best = None
    for snap in sorted(history or [], key=lambda s: _snap_ts(s) or 0, reverse=True):
        ts = _snap_ts(snap)
        if ts is None:
            continue
        age_h = (now - ts) / 3600.0
        if age_h > max_age_h:
            break                            # everything older is older still
        if is_clean(key, snap, now):
            best = (snap, age_h)
            break
    return best if best else (None, None)


def send_push(title, body):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        req = urllib.request.Request(f"{server}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", "high")
        req.add_header("Tags", "adhesive_bandage")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[fleet-regen] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def restore_payload(snap, baseline, key, now):
    """Build the payload to write: last-good CONTENT if available (carrying
    its ORIGINAL age + _regen marker so it reads as the aged snapshot it is),
    else the SAFE baseline (marked, stamped now — a cold restart is
    legitimately 'current')."""
    if snap is not None:
        out = copy.deepcopy(snap)
        out["_regen"] = {"restored": _iso(now), "source": "last-good-history"}
        return out                            # keeps snap's own `updated`
    out = dict(baseline)
    out["updated"] = _iso(now)
    out["ttl_sec"] = int(baseline.get("ttl_sec") or 600)
    out["_regen"] = {"restored": _iso(now), "source": "safe-baseline"}
    return out


def run_once():
    now = now_ts()
    prior = store.load_state(KEY) or {}
    imm = store.load_state(immune.KEY) or {}
    # only act on organs the immune organ currently flags SICK (fresh check)
    sick_organs = {s.get("organ") for s in (imm.get("sick") or [])
                   if immune._fresh(imm, now)}
    repaired, needs_op = [], []

    for key in REPAIRABLE:
        if key not in sick_organs:
            continue
        history = []
        try:
            if hasattr(store, "fetch_state_history"):
                history = store.fetch_state_history(key, limit=200) or []
                history = [h.get("payload") or {} for h in history]
        except Exception:
            history = []
        snap, age_h = pick_last_good(key, history, now)
        if snap is None and not REPAIRABLE[key]:
            needs_op.append(key)              # no clean history, no baseline
            continue
        payload = restore_payload(snap, REPAIRABLE[key], key, now)
        store.save_state(key, payload)
        src = "last-good" if snap is not None else "safe-baseline"
        repaired.append({"organ": key, "source": src,
                         "age_h": round(age_h, 1) if age_h is not None else None})
        print(f"[fleet-regen] REPAIRED {key} <- {src}"
              + (f" ({age_h:.1f}h old)" if age_h is not None else ""), flush=True)

    payload = {"updated": _iso(now), "ttl_sec": TTL_SEC,
               "repaired": repaired, "needs_operator": needs_op}
    store.save_state(KEY, payload)
    if hasattr(store, "save_history") and (repaired or needs_op):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "repaired": [r["organ"] for r in repaired],
                                     "needs_operator": needs_op})
        except Exception:
            pass
    last_push = float(prior.get("last_push") or 0)
    if (repaired or needs_op) and now - last_push >= NOTIFY_GAP_H * 3600:
        body = ("\n".join(f"repaired {r['organ']} ({r['source']})" for r in repaired)
                + ("\nNEEDS OPERATOR: " + ", ".join(needs_op) if needs_op else ""))
        if send_push(f"🩹 fleet regen: {len(repaired)} repair(s)", body or "—"):
            payload["last_push"] = now
            store.save_state(KEY, payload)
    print(f"[fleet-regen] {_iso(now)} repaired={len(repaired)} "
          f"needs_operator={len(needs_op)}", flush=True)
    return payload


def _selftest():
    now = 1_800_000_000.0

    def snap(ts, phase):
        return {"updated": _iso(ts), "ttl_sec": 10800, "phase": phase}

    # xp-judge history: newest is corrupt (unknown phase), older ones clean
    hist = [snap(now - 600, "haywire"),        # newest, SICK
            snap(now - 4000, "running"),        # clean, ~1.1h
            snap(now - 8000, "idle")]           # clean, older
    good, age = pick_last_good("xp-judge", hist, now)
    assert good is not None and good["phase"] == "running", good
    assert abs(age - 4000 / 3600) < 0.1

    # if the only clean snapshots are too old -> None (fall back to baseline)
    old = [snap(now - 600, "haywire"), snap(now - 200000, "idle")]
    g2, a2 = pick_last_good("xp-judge", old, now)
    assert g2 is None, g2

    # restore from last-good keeps the ORIGINAL updated (reads as aged/stale)
    r = restore_payload(good, REPAIRABLE["xp-judge"], "xp-judge", now)
    assert r["updated"] == good["updated"] and r["_regen"]["source"] == "last-good-history"
    # restore from baseline stamps NOW + marks it (a cold restart is current)
    rb = restore_payload(None, REPAIRABLE["xp-judge"], "xp-judge", now)
    assert rb["phase"] == "idle" and rb["_regen"]["source"] == "safe-baseline"
    assert rb["updated"] == _iso(now)

    # is_clean uses the immune invariants: a good phase is clean, haywire isn't
    assert is_clean("xp-judge", {"updated": _iso(now), "ttl_sec": 10800,
                                 "phase": "idle"}, now)
    assert not is_clean("xp-judge", {"updated": _iso(now), "ttl_sec": 10800,
                                     "phase": "haywire"}, now)

    # empty history -> nothing to restore
    assert pick_last_good("xp-judge", [], now) == (None, None)
    print("fleet_regen selftest OK (last-good pick, age-bound, restore markers, "
          "immune-invariant reuse)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
