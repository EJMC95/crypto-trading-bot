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

    # [2026-07-17 BORN-DARK DETECTOR] an organ silently running a DEGRADED
    # FALLBACK nobody asked for. The brain shipped its v3 engine on 16-Jul
    # and ran FROZEN v2 in production for a day: brain_stats.py was never
    # COPY'd into the image, so bot_learn's `try: import brain_stats /
    # except: bstats = None` guard swallowed it. Nothing crashed — the
    # import guard is what made it silent, which is exactly the alive-but-
    # sick class this organ exists for. The env is the operator's INTENT;
    # the payload is the REALITY; a mismatch is sickness.
    # (Repo-side prevention: scripts/audit_image_imports.py.)
    bv = states.get("brain-vitals") or {}
    if _fresh(bv, now):
        eng = bv.get("engine")
        # Same normalization bot_learn uses for _ENGINE_INTENT — the two MUST
        # agree, or a case-typo'd kill switch ("V2") makes the brain warn
        # "not deliberate" while this detector stays silent. Premise: both
        # modules run in the SAME container (Dockerfile.freqtrade/run_all.sh),
        # so this env IS the brain's env. If fleet_immune ever moves to
        # another service, that premise breaks and this rule must move too.
        want = os.environ.get("BRAIN_MULT_ENGINE", "").strip().lower()
        # Expected transient: after REMOVING a deliberate BRAIN_MULT_ENGINE=v2
        # and redeploying, the last v2 payload stays fresh (ttl 26000s) until
        # the brain's next run (~2h), so one deduped page is normal and
        # self-heals. A page that persists past a brain cycle is real.
        if eng == "v2" and want != "v2":
            sick("brain-vitals",
                 "engine=v2 but BRAIN_MULT_ENGINE was not set to v2 — the "
                 "brain is silently running its FROZEN fallback (brain_stats "
                 "missing/unimportable in the image?). Stake mults, lens "
                 "grades and priors are NOT the v3 engine the fleet assumes")
        if eng is not None and eng not in ("v2", "v3"):
            sick("brain-vitals", f"unknown engine {eng!r}")

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


def notify_ledger(prior_sick, sick_ids, delivered=()):
    """[2026-07-17 AUDIT] The `notified` ledger — what has been DELIVERED, not
    what has been SEEN. Pure, so the selftest drives THIS, not a copy of it.

    Carries forward the prior ids that are STILL sick, plus whatever this cycle
    actually pushed. Dropping a healed id is deliberate: a recurrence should
    page afresh rather than be suppressed forever by an old delivery.

    The bug this replaces: `notified` was set to every sick_id and saved BEFORE
    the push decision, so a finding the gap limiter vetoed (NOTIFY_GAP_H=6h) or
    whose push FAILED (send_push returns False when NTFY_TOPIC is unset or ntfy
    is down) was recorded as already-notified. `new_sick = sick_ids -
    prior_sick` was then empty forever: the edge was CONSUMED, not deferred.
    Measured — 21h continuously sick after one failed push: 0 pages; born-dark
    sickness appearing 1h after any unrelated page: 0 pages, for 12h. Both now
    page. That silence defeated the runtime backstop CLAUDE.md names for the
    BORN-DARK class, a class that caused three incidents in three days.

    Errs toward re-paging over swallowing — the right direction for a detector
    of last resort."""
    return sorted((set(prior_sick) & set(sick_ids)) | set(delivered))[:50]


def run_once():
    now = now_ts()
    prior = store.load_state(KEY) or {}
    prior_sick = set(prior.get("notified") or [])

    # one batched beat instead of five round-trips (fail-safe: batch {} on
    # DB failure -> every organ reads as absent, same as load_state failing)
    _keys = ("lighter-market", "brain-lens-forward", "gapscout-census",
             "xp-judge", "fleet-tuning", "fleet-proprioception",
             "brain-vitals")     # [2026-07-17] born-dark detector, see above
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
        cur_raw = store.load_state("fleet-alerts") or {}
        cur = cur_raw.get("alerts") or alerts
        keep2, _ = alert_fossils(cur, now)
        # [2026-07-17] PRESERVE the producer's bus stamp, never re-mint it.
        # fleet-alerts carries `updated`/`ttl_sec` from market_context.save_alerts
        # (17-Jul), and the evidence board now gates on it. Two ways to get this
        # wrong, and this organ sits exactly where both would land:
        #   * dropping the keys (a bare {"alerts": ...} write, which is what this
        #     line did) silently un-stamps the feed — the board's gate reads no
        #     `updated`, fails closed, and a PRUNE blinds the board;
        #   * refreshing `updated` to now() is worse: this organ runs on its own
        #     loop, so a dead market_context would keep looking alive for as long
        #     as the immune organ kept tidying its corpse — the freshness gate
        #     would report on the JANITOR, not the producer.
        # Filtration is content-only; the age belongs to whoever wrote the data.
        # Same rule fleet_regen follows for its snapshots.
        store.save_state("fleet-alerts", {**cur_raw, "alerts": keep2})

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
        # (the ledger is built by notify_ledger() — see the note on it below)
        "quarantined_levers": q,
        "pruned_alerts": len(pruned),
        "pruned_detail": pruned[:10],
        "antibodies": [a[0] for a in ANTIBODIES],
        # [2026-07-16] first-seen map for the application invariant — the
        # organ's own memory of when each (lever, value) appeared.
        "app_seen": app_seen,
        # [2026-07-17 AUDIT] `notified` records what was DELIVERED, not what was
        # SEEN. It used to be set to every sick_id and saved BELOW, before the
        # push decision — so a finding the gap limiter vetoed (NOTIFY_GAP_H=6h)
        # or whose push FAILED (send_push returns False when NTFY_TOPIC is unset
        # or ntfy is down) was recorded as "already notified". `new_sick =
        # sick_ids - prior_sick` was then empty on every later cycle: the edge
        # was CONSUMED, not deferred, and the page never came.
        #
        # Measured: sick continuously for 72h -> 0 pages, because one unrelated
        # finding had paged an hour earlier. And 21h of continuous sickness with
        # a failing push -> 1 attempt, never retried — the limiter would have
        # ALLOWED it; new_sick was simply empty.
        #
        # That defeats the runtime backstop CLAUDE.md names for the BORN-DARK
        # class ("fleet_immune pages when brain-vitals reports engine=v2..."),
        # for a bug class that caused three incidents in three days — silenced
        # by any other sickness in the prior 6h.
        #
        # So: carry the PRIOR set forward here, and only add the ids we actually
        # pushed (below, on send_push success). Undelivered sickness stays NEW
        # and pages on the next cycle the limiter allows.
        "notified": notify_ledger(prior_sick, sick_ids),
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
            # [2026-07-17 AUDIT] commit the delivered ids ONLY on a successful
            # push — this is the single place that may mark sickness "notified".
            # The body is capped at 8 findings, so only those are recorded as
            # delivered; the rest stay NEW and page next cycle rather than being
            # silently dropped by the cap.
            payload["notified"] = notify_ledger(prior_sick, sick_ids,
                                                sorted(new_sick)[:8])
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

    # [2026-07-17 BORN-DARK DETECTOR] engine=v2 without the operator asking
    # for v2 is sickness (the 17-Jul brain_stats postmortem: a missing COPY
    # + a guarded import ran the frozen engine silently for a day). The env
    # is INTENT; the payload is REALITY; a mismatch pages.
    _saved_eng = os.environ.pop("BRAIN_MULT_ENGINE", None)
    try:
        _bv = {"brain-vitals": {"updated": _iso(now), "ttl_sec": 26000,
                                "engine": "v2"}}
        _f = organ_invariants(_bv, now)
        assert len(_f) == 1 and _f[0]["organ"] == "brain-vitals" \
            and "FROZEN fallback" in _f[0]["detail"], _f
        # v3 is healthy; an unknown engine is its own sickness
        assert organ_invariants(
            {"brain-vitals": dict(_bv["brain-vitals"], engine="v3")}, now) == []
        _u = organ_invariants(
            {"brain-vitals": dict(_bv["brain-vitals"], engine="v9")}, now)
        assert len(_u) == 1 and "unknown engine" in _u[0]["detail"], _u
        # a DELIBERATE v2 (operator threw the kill switch) is NOT sickness
        os.environ["BRAIN_MULT_ENGINE"] = "v2"
        assert organ_invariants(_bv, now) == [], "deliberate v2 must not page"
        # a STALE vitals payload is the watchdog's job, not sickness
        os.environ.pop("BRAIN_MULT_ENGINE", None)
        assert organ_invariants(
            {"brain-vitals": {"updated": "2020-01-01T00:00:00+00:00",
                              "ttl_sec": 900, "engine": "v2"}}, now) == []
    finally:
        os.environ.pop("BRAIN_MULT_ENGINE", None)
        if _saved_eng is not None:
            os.environ["BRAIN_MULT_ENGINE"] = _saved_eng
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
    # [2026-07-17 AUDIT] THE NOTIFY LEDGER: `notified` must mean DELIVERED, not
    # SEEN. It was committed with every sick_id before the push decision, so a
    # gap-vetoed or FAILED push consumed the edge and the finding never paged
    # again. This silently defeated the runtime backstop CLAUDE.md names for the
    # born-dark class. Mirrors run_once's real merge; `old=True` is the shipped
    # bug, kept as the negative control so the fixture proves the DIFFERENCE.
    def _notify_cycle(prior_notified, prior_last_push, sick_ids, now,
                      push_ok, old=False):
        # drives the REAL notify_ledger() — only the gap/push plumbing around
        # it is mirrored here. `old=True` re-creates the shipped bug (seen ==
        # notified) as the negative control.
        prior_sick = set(prior_notified)
        new_sick = sick_ids - prior_sick
        notified = (sorted(sick_ids)[:50] if old
                    else notify_ledger(prior_sick, sick_ids))
        last_push, pushed = prior_last_push, False
        if new_sick and now - last_push >= NOTIFY_GAP_H * 3600:
            if push_ok:
                last_push, pushed = now, True
                if not old:
                    notified = notify_ledger(prior_sick, sick_ids,
                                             sorted(new_sick)[:8])
        return notified, last_push, pushed

    _T = 1_784_000_000.0        # a REAL unix ts: `now - last_push` must be huge
    for _old, _want in ((True, 0), (False, 1)):
        # a FAILED push (ntfy down / NTFY_TOPIC unset), then 21h sick + healthy
        _n, _lp, _ = _notify_cycle([], 0, {"BORN_DARK"}, _T, False, _old)
        _pages = 0
        for _h in range(1, 22):
            _n, _lp, _p = _notify_cycle(_n, _lp, {"BORN_DARK"},
                                        _T + _h * 3600, True, _old)
            _pages += 1 if _p else 0
        assert _pages == _want, (f"failed-push retry: old={_old} "
                                 f"pages={_pages} want={_want}")
        # RATE-LIMITED: an unrelated finding pages, then born-dark appears 1h on
        _n, _lp, _ = _notify_cycle([], 0, {"A"}, _T, True, _old)
        _pages = 0
        for _h in range(1, 13):
            _n, _lp, _p = _notify_cycle(_n, _lp, {"A", "B"},
                                        _T + _h * 3600, True, _old)
            _pages += 1 if _p else 0
        assert _pages == _want, (f"gap-vetoed retry: old={_old} "
                                 f"pages={_pages} want={_want}")
    # a DELIVERED finding must not re-page every cycle (the limiter still works)
    _n, _lp, _ = _notify_cycle([], 0, {"A"}, _T, True)
    assert _n == ["A"], _n
    _n2, _, _p2 = _notify_cycle(_n, _lp, {"A"}, _T + 7 * 3600, True)
    assert _p2 is False and _n2 == ["A"], "delivered sickness must stay quiet"
    # a HEALED finding drops out of the ledger, so a recurrence pages afresh
    assert _notify_cycle(["A"], _T, set(), _T + 8 * 3600, True)[0] == []

    print("fleet_immune selftest OK (notify ledger delivered!=seen, filtration age+antibody, lever sickness, "
          "organ invariants, bot-row sickness, death!=sickness, "
          "application invariant)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
