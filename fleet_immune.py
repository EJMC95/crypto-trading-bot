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


# [2026-07-16] ENACTED-IS-NOT-APPLIED — the application invariant.
# Every growth-rail gate validated the DECISION to write a lever; none
# validated that a bot ever READ it. That skew bit the same day: the judge
# asserted xp.funding.enter_apr=0.30 at a frozen arm with no lever code (30
# closes, 0 receipts) — fresh, in-TTL, trusted, and WRONG: exactly this
# organ's remit. Only lanes with a receipt channel are checked: the funding
# arms stamp extra.bars from inside apply_levers(), so an image without lever
# code structurally cannot forge one — a missing receipt is DISPROOF.
# Deliberately NOT a quarantine: quarantining a lever the consumer provably
# ignores reverts nothing (that IS the sickness) and would create a feedback
# loop on a healthy arm (quarantine -> consumer runs defaults -> receipts stop
# matching -> sickness persists forever). Sick-list + phone only; the judge's
# own ARM-SKEW hold is the measurement guard.
APP_RECEIPT_BOTS = {
    "xp.funding.": os.environ.get("XPJ_SHADOW_BOT",
                                  "perps-funding-lighter-lshadow"),
    "live.funding.": os.environ.get("XPJ_LIVE_BOT",
                                    "perps-funding-lighter-lighter"),
}
APP_SICK_MIN_CLOSES = int(os.environ.get("IMMUNE_APP_MIN_CLOSES", "2"))
APP_GRACE_S = float(os.environ.get("IMMUNE_APP_GRACE_S", "900"))  # arm loop lag


def _close_ts(row):
    """Tolerant close-time parse for a fetch_paper_trades row; None on any
    failure (an unparseable row is no evidence, not sickness)."""
    s = str(row.get("close_ts") or "").strip().replace("Z", "+00:00")
    if s.endswith(" UTC"):
        s = s[:-4] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except Exception:  # noqa: BLE001
        return None


def application_sickness(levers, paper_rows, now, seen):
    """{lever: why} for receipt-lane levers whose consumer has closed
    >= APP_SICK_MIN_CLOSES trades since the lever appeared (plus grace for the
    arm's loop) with NONE carrying a matching extra.bars receipt.

    `seen` is the organ's own first-seen map {name: {value, since}} — the
    tuning payload carries no set-time, and the judge re-asserts hourly, so
    the immune organ tracks when it first saw each (name, value) itself.
    Mutated in place; persisted by the caller. Fail-safe: zero closes = no
    evidence = healthy; dark tuning/ledger = nothing flagged. Pure given its
    inputs — selftested."""
    out = {}
    if tuning is None:
        return out
    live_names = set()
    for name, entry in (levers or {}).items():
        bot = next((b for p, b in APP_RECEIPT_BOTS.items()
                    if name.startswith(p)), None)
        if bot is None or not isinstance(entry, dict):
            continue
        try:
            if not tuning._lever_alive(entry, now):
                continue
        except Exception:  # noqa: BLE001
            continue
        live_names.add(name)
        want = entry.get("value")
        rec = seen.get(name)
        if not isinstance(rec, dict) or rec.get("value") != want:
            seen[name] = {"value": want, "since": now}
            continue                       # first sighting — start the clock
        since = float(rec.get("since") or now)
        bar = name.rsplit(".", 1)[-1]
        n_closes, n_hits = 0, 0
        for r in paper_rows or []:
            if str(r.get("bot")) != bot:
                continue
            ts = _close_ts(r)
            if ts is None or ts < since + APP_GRACE_S or ts > now:
                continue
            n_closes += 1
            bars = (r.get("extra") or {}).get("bars")
            try:
                if isinstance(bars, dict) and \
                        abs(float(bars.get(bar)) - float(want)) <= 1e-9:
                    n_hits += 1
            except (TypeError, ValueError):
                pass
        if n_closes >= APP_SICK_MIN_CLOSES and n_hits == 0:
            # digits normalize out of the sick-id, so the episode pages once
            out[name] = (f"enacted but not applied: {bot} closes since "
                         f"assert carry no receipt for {bar}={want}")
    # forget levers no longer in force so a re-assert starts a fresh episode
    for gone in set(seen) - live_names:
        seen.pop(gone, None)
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

    # [2026-07-16] 🦾 proprioception: impossible episodes / unknown verdicts
    # would mislead the tuner's hurting-skip and the board's outcome items
    pr = states.get("fleet-proprioception") or {}
    if _fresh(pr, now):
        for ep in (pr.get("episodes") or [])[-30:]:
            s, e = ep.get("start"), ep.get("end")
            if isinstance(s, (int, float)) and isinstance(e, (int, float)) and e < s:
                sick("fleet-proprioception",
                     f"episode {ep.get('group')} end < start (impossible)")
        for lever, v in (pr.get("verdicts") or {}).items():
            vd = v.get("verdict") if isinstance(v, dict) else None
            if vd is not None and vd not in ("helping", "hurting", "neutral",
                                             "insufficient"):
                sick("fleet-proprioception", f"{lever} unknown verdict {vd!r}")

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
             "xp-judge", "fleet-tuning", "fleet-proprioception")
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
    levers = (states["fleet-tuning"] or {}).get("levers") or {}
    q = lever_sickness(levers, now)
    # [2026-07-16] enacted-is-not-applied: consumer closes with no matching
    # receipt. Sick-list only, never quarantine (see application_sickness).
    app_seen = dict(prior.get("app_seen") or {})
    try:
        _papers = store.fetch_paper_trades(limit=1500)
    except Exception:  # noqa: BLE001
        _papers = []
    app = application_sickness(levers, _papers, now, app_seen)
    sick = (organ_invariants(states, now) + bot_row_sickness(bot_rows)
            + [{"organ": "fleet-tuning", "detail": f"{n}: {w}"} for n, w in q.items()]
            + [{"organ": "lever-application", "detail": f"{n}: {w}"}
               for n, w in app.items()])

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
        # [2026-07-16] first-seen map for the application invariant — the
        # organ's own memory of when each (lever, value) appeared.
        "app_seen": app_seen,
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
        "fleet-proprioception": {"updated": fresh, "ttl_sec": 2700,
                                 "episodes": [{"group": "taker", "start": 100.0,
                                               "end": 50.0},           # impossible
                                              {"group": "live", "start": 1.0,
                                               "end": 2.0}],           # fine
                                 "verdicts": {"taker.tp": {"verdict": "banana"},
                                              "taker.sl": {"verdict": "helping"}}},
        "stale-organ": {"updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 900,
                        "n_books": 1, "n_liquid": 999},
    }
    inv = organ_invariants(states, now)
    organs = {i["organ"] for i in inv}
    assert organs == {"lighter-market", "brain-lens-forward",
                      "gapscout-census", "xp-judge",
                      "fleet-proprioception"}, organs
    prio = [i["detail"] for i in inv if i["organ"] == "fleet-proprioception"]
    assert len(prio) == 2 and any("end < start" in d for d in prio) \
        and any("banana" in d for d in prio), prio
    # the stale organ's impossible content is NOT flagged (death != sickness)
    assert not any(i["organ"] == "stale-organ" for i in inv)

    # BOT ROW SICKNESS: NaN, inf, absurd pnl_pct
    rows = [{"bot": "a", "pnl_pct": float("nan")},
            {"bot": "b", "equity": float("inf")},
            {"bot": "c", "pnl_pct": 123.0},          # 12300%
            {"bot": "d", "pnl_pct": 0.05, "equity": 1000.0}]   # fine
    bs = bot_row_sickness(rows)
    assert {b["organ"] for b in bs} == {"a", "b", "c"}, bs

    # APPLICATION SICKNESS: enacted-is-not-applied (receipt lanes only)
    if tuning is not None:
        _sb = APP_RECEIPT_BOTS["xp.funding."]
        _lv = {"xp.funding.enter_apr": {"value": 0.3, "expires": _iso(now + 3600)}}

        def _prow(off, bars):
            r = {"bot": _sb, "close_ts": _iso(now - off), "extra": {}}
            if bars is not None:
                r["extra"] = {"bars": bars}
            return r

        # first sighting only starts the clock — never sick on sight
        seen = {}
        assert application_sickness(_lv, [_prow(60, None)] * 3, now, seen) == {}
        assert seen["xp.funding.enter_apr"]["value"] == 0.3
        # clock running, 3 receiptless closes after grace -> SICK
        seen = {"xp.funding.enter_apr": {"value": 0.3, "since": now - 7200}}
        app = application_sickness(_lv, [_prow(600, None), _prow(1200, None),
                                         _prow(1800, None)], now, dict(seen))
        assert set(app) == {"xp.funding.enter_apr"}, app
        # matching receipts -> healthy
        ok_bars = {"arm": "lighter_shadow", "enter_apr": 0.3}
        assert application_sickness(_lv, [_prow(600, ok_bars),
                                          _prow(1200, ok_bars)], now,
                                    dict(seen)) == {}
        # WRONG-value receipts are not proof -> sick (the deaf-arm signature:
        # the arm stamps its env default, not the enacted value)
        bad_bars = {"arm": "lighter_shadow", "enter_apr": 0.4}
        assert set(application_sickness(_lv, [_prow(600, bad_bars),
                                              _prow(1200, bad_bars)], now,
                                        dict(seen))) == {"xp.funding.enter_apr"}
        # below the floor (1 close) -> no verdict
        assert application_sickness(_lv, [_prow(600, None)], now,
                                    dict(seen)) == {}
        # closes inside the grace window AFTER first-seen (since=now-7200,
        # grace 900 -> anything closed now-7200..now-6300) are the arm's
        # loop lag, not evidence — ignored
        assert application_sickness(_lv, [_prow(7000, None), _prow(6500, None)],
                                    now, dict(seen)) == {}
        # non-receipt lanes are never judged; expired levers drop from `seen`
        assert application_sickness(
            {"live.clip_scale": {"value": 0.5, "expires": _iso(now + 3600)}},
            [_prow(600, None)] * 5, now, dict(seen)) == {}
        gone = dict(seen)
        application_sickness({}, [], now, gone)
        assert gone == {}, gone

    # empty / healthy fleet -> nothing
    assert alert_fossils([], now) == ([], [])
    assert organ_invariants({}, now) == []
    assert bot_row_sickness([]) == []
    assert application_sickness({}, [], now, {}) == {}
    print("fleet_immune selftest OK (filtration age+antibody, lever sickness, "
          "organ invariants, bot-row sickness, death!=sickness, "
          "application invariant)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
