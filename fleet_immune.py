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
# [2026-08-16 (ol)] How far into the FUTURE a payload may be dated and still be
# read. `_fresh` refused ANY negative age, and a future-dated payload is worth
# refusing at scale — a corrupt write, a wildly wrong clock — but not at the
# microsecond, for two reasons that both bite here:
#   * publisher and reader are DIFFERENT CONTAINERS, so ordinary NTP skew of a
#     few ms dates a perfectly good payload in the reader's future;
#   * `float -> datetime -> isoformat -> float` rounds to the nearest
#     microsecond and lands in the future **38% of the time** (measured), so
#     even a payload stamped from the reader's OWN clock trips it.
# The direction matters: every `_fresh` call site is `if _fresh(...)` guarding a
# CHECK, so "not fresh" means the detector does nothing. Refusing on a
# nanosecond of rounding does not make the organ careful, it makes it blind —
# and blind is the failure mode this whole file exists to prevent (I1). The
# guard still means something: a payload dated minutes ahead is still refused.
FUTURE_SKEW_S = float(os.environ.get("IMMUNE_FUTURE_SKEW_S", "2"))

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
    (or max_age_s override). Fail-safe: unparseable -> not fresh.

    [2026-08-16 (ol)] The lower bound is `-FUTURE_SKEW_S`, not 0 — see that
    constant. A sub-microsecond negative age is float round-tripping, not a
    future-dated payload, and refusing it silently switched a detector off.
    """
    try:
        u = datetime.fromisoformat(str(state.get("updated")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        age = now - u.timestamp()
        horizon = max_age_s if max_age_s is not None else float(state.get("ttl_sec") or 0)
        return -FUTURE_SKEW_S <= age <= horizon
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


#: Hours after which a same-pair overlap is HISTORY rather than an incident.
#: 6h > the 30-min `claim_writer` TTL by a wide margin, so a guard that is
#: actually arbitrating has long since taken effect; and it is short enough
#: that a REAL recurrence pages the same day. Tunable, because the right value
#: is "comfortably longer than the claim TTL" and that TTL can move.
DUP_WRITER_CLOSED_H = float(os.environ.get("IMMUNE_DUP_CLOSED_H", "6"))


def _parse_iso(txt):
    """-> aware datetime, or None. Tolerant of 'Z' and of a naive stamp.

    None means "cannot tell", and every caller must treat that as NOT evidence
    of recency — the duplicate-writer pager stays LOUD on an unreadable stamp
    rather than going quiet, because a detector that mutes itself on bad input
    is the failure it exists to prevent.
    """
    if not txt:
        return None
    try:
        d = datetime.fromisoformat(str(txt).strip().replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


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
        # [2026-07-30] A FRESH scout reporting ZERO liquid books is the shape
        # that silently starves the LIVE Ticket Taker: every lens's tickets are
        # built from `liquid`, so `n_liquid == 0` publishes a healthy-looking
        # payload with an empty opportunity set and the live arm simply stops
        # entering. `n_liquid > n_books` above catches the impossible; this
        # catches the merely CATASTROPHIC, which no check covered.
        if isinstance(nb, int) and isinstance(nl, int) and nb > 0 and nl == 0:
            sick("lighter-market",
                 f"n_liquid 0 of {nb} books — every lens's ticket supply is "
                 f"empty and the LIVE taker cannot enter")
        # [2026-07-30] `vols` decides what FIVE books trade (it is what
        # fleet_bus.scout_universe ranks), and until now no organ asserted
        # anything about it. The dangerous shape is not an ABSENT map — every
        # consumer reads empty as "keep my configured list" — but a fresh,
        # TRUNCATED, non-empty one: that silently re-points five books' orders
        # at a sliver of the venue while looking perfectly healthy.
        vols = lm.get("vols")
        if isinstance(vols, dict) and vols and isinstance(nb, int) and nb > 0:
            if len(vols) < nb // 2:
                sick("lighter-market",
                     f"vols covers {len(vols)} of {nb} books (<50%) — five "
                     f"books rank their universe off this map")
            _neg = [k for k, v in vols.items()
                    if isinstance(v, (int, float)) and v < 0]
            if _neg:
                sick("lighter-market",
                     f"vols has negative turnover for {sorted(_neg)[:3]} "
                     f"(24h $volume cannot be negative)")

    lf = states.get("brain-lens-forward") or {}
    if _fresh(lf, now):
        for lens, o in (lf.get("lenses") or {}).items():
            n4h, hit = o.get("n4h"), o.get("hit4h")
            if isinstance(n4h, (int, float)) and n4h < 0:
                sick("brain-lens-forward", f"lens {lens} n4h {n4h} < 0")
            if isinstance(hit, (int, float)) and not (0.0 <= hit <= 1.0):
                sick("brain-lens-forward", f"lens {lens} hit4h {hit} outside [0,1]")

    # [2026-07-22] gapscout-census removed: Gap Scout retired 17-Jul, so that
    # key is never published again and its check was permanently dead (`_fresh`
    # is always False for a retired publisher). A dead sensor left in the body
    # is exactly the rot this organ exists to catch — so it goes.
    # regime-oracle takes its place. The oracle self-grades its own directional
    # calls (`grades[sym][d{h}] = {n, hit, avg_pp}`) and those grades feed the
    # 28-Jul review's item-18 decision; a fresh-but-WRONG grade would corrupt
    # that evidence. Impossible values only, same shape as brain-lens-forward
    # (a hit-RATE outside [0,1], a negative count). Page-only — organ_invariants
    # findings notify; they never quarantine a lever (that is lever_sickness).
    ro = states.get("regime-oracle") or {}
    if _fresh(ro, now):
        for sym, horizons in (ro.get("grades") or {}).items():
            if not isinstance(horizons, dict):
                continue
            for h, g in horizons.items():
                if not isinstance(g, dict):
                    continue
                n, hit = g.get("n"), g.get("hit")
                if isinstance(n, (int, float)) and n < 0:
                    sick("regime-oracle", f"grade {sym}.{h} n {n} < 0")
                if isinstance(hit, (int, float)) and not (0.0 <= hit <= 1.0):
                    sick("regime-oracle", f"grade {sym}.{h} hit {hit} outside [0,1]")
        cov = ro.get("coverage") or {}
        npub, nmiss = cov.get("n_published"), cov.get("n_missing")
        uni = cov.get("universe")
        if isinstance(npub, int) and npub < 0:
            sick("regime-oracle", f"coverage.n_published {npub} < 0")
        if isinstance(nmiss, int) and nmiss < 0:
            sick("regime-oracle", f"coverage.n_missing {nmiss} < 0")
        if isinstance(npub, int) and isinstance(uni, int) and npub > uni:
            sick("regime-oracle",
                 f"coverage.n_published {npub} > universe {uni} (impossible)")

    xp = states.get("xp-judge") or {}
    if _fresh(xp, now):
        ph = xp.get("phase")
        if ph is not None and ph not in ("idle", "running", "promoted"):
            sick("xp-judge", f"unknown phase {ph!r}")

    # [2026-07-30 (hh)] A LEDGER THAT IS NOT ONE BOOK'S RECORD. This is the
    # purest ALIVE-BUT-SICK shape in the fleet: the row is fresh, in-TTL and
    # trusted, and its `n` is two processes' trades. `(hf)` measured it on
    # `perps-funding-carry-lshadow` — 7 same-pair overlapping holds, deepest
    # 9.14h, and one process cannot hold two positions in one coin — but the
    # signal reached only a dashboard chip and a manually-run audit. THE FIX IS
    # AN OPERATOR ACTION (stop the duplicate Railway service), which is exactly
    # the case where this organ's phone push is the actuator: a guard cannot
    # un-pool closes two processes already wrote, so the only useful response is
    # to tell a human, once, until it stops.
    # Read off `golive-readiness.books.<bot>.integrity` — the publisher, not
    # re-derived here, so the gate and the immune organ can never disagree about
    # which ledgers are compromised.
    gl = states.get("golive-readiness") or {}
    if _fresh(gl, now):
        for _bot, _b in sorted((gl.get("books") or {}).items()):
            if not isinstance(_b, dict):
                continue
            _in = _b.get("integrity")
            if isinstance(_in, dict) and _in.get("two_writers"):
                # [2026-08-01 (ih)] PAGE ONLY WHILE IT IS STILL HAPPENING.
                # `two_writers` reads a PERMANENT ledger, so it is a one-way
                # latch: once true it can never go false, and this branch paged
                # the operator every cycle with "stop the duplicate Railway
                # service" long after (hp)/(ic)/(id) had closed the hole in
                # code — an instruction that no longer has an object, and that
                # (id) showed would now be WRONG, because the stood-down
                # container is failover rather than a fault. A permanent page
                # for a fixed condition is how a pager gets ignored ((hw): "a
                # sticky error pages once and then means nothing").
                # The FINDING is unchanged and still blocks READY upstream —
                # only the pager is scoped, and only on positive evidence of
                # recency. An unreadable/absent stamp still pages (fail-safe
                # LOUD: the detector must not go quiet because it cannot tell).
                _latest = _parse_iso(_in.get("latest_overlap"))
                # `now` is a float epoch here (now_ts), not a datetime.
                _age_h = ((now - _latest.timestamp()) / 3600.0) if _latest else None
                if _age_h is not None and _age_h > DUP_WRITER_CLOSED_H:
                    continue          # historical: the sample is pooled, the
                                      # process is not. Carried by the grade.
                sick("golive-readiness",
                     f"{_bot}: ledger has {_in.get('same_pair_overlaps')} "
                     f"same-pair overlap(s), deepest "
                     f"{_in.get('deepest_overlap_h')}h on "
                     f"{_in.get('deepest_overlap_pair')} — TWO WRITERS on one "
                     f"bot_id, most recent "
                     + (f"{_age_h:.1f}h ago" if _age_h is not None
                        else "at an UNKNOWN time")
                     + ". n is not one book's trades and t scales with "
                       "sqrt(n). OPERATOR: confirm `claim_writer` is arbitrating "
                       "(the loser publishes <bot>:standby, not the book's row)")

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


# [2026-07-31 (hu)] Rows whose publisher LEGITIMATELY carries no `extra.svc`.
# The BORN_DARK_OK idiom: a deliberate omission is DECLARED with a reason, so
# silence is never an option. These three run on services in the LIVE-MARKER
# deploy path (`trail-blazer-live`, `funding-farmer-shadow`,
# `tide-rider-lighter-live`), which an unmarked push must never ship — so they
# are still on pre-(ht) code BY DESIGN and will stamp themselves the first time
# a deliberate live deploy carries them.
# [2026-08-02] EMPTY, AND THAT IS THE POINT: the exemption was spent, not
# deleted. All three declared rows now stamp, verified in the live payload
# minutes after the operator dispatched both live services —
#   perps-funding-lighter-lighter  -> svc=trail-blazer-live      build 30bf230bd5fb
#   perps-funding-lighter-lshadow  -> svc=funding-farmer-shadow  build 30bf230bd5fb
#   lighter-ticket-taker-lighter   -> svc=tide-rider-lighter-live build 5e27c751f5b2
# — exactly what the declaration above predicted would happen ("stamps on the
# next deliberate deploy"). Keeping the entries would leave three REAL-MONEY-
# adjacent rows permanently excused from the detector that exists to notice a
# deploy which reported OK and never landed: the `DRIFT_OK` shape, where the
# carve-out lands on precisely the rows most worth watching. A declaration that
# no longer describes the system is a defect, not history (I12).
#
# The MECHANISM is unchanged and still tested — `ok=` injects an allow-list, so
# a future legitimate exemption is one entry away and its selftest arms below
# use a synthetic one rather than depending on this dict being non-empty.
STALE_WRITER_OK = {}


#: A bot_pnl row older than this is DEAD, not merely quiet. The fleet's
#: freshness convention (fleet_risk uses 65 min); doubled here because this
#: detector only needs to exclude the unambiguous corpses, and a book that
#: publishes on a 4h candle legitimately drifts past one hour.
STALE_ROW_S = float(os.environ.get("IMMUNE_STALE_ROW_S", "7800"))


def _row_stale(row, now=None):
    """True when a bot_pnl row has stopped being written. Unknown age reads as
    NOT stale: this only ever SUPPRESSES a finding, so an unreadable stamp
    must not silently mute a real one."""
    age = row.get("age_sec")
    if age is None:
        ts = _parse_ts(row.get("updated_at"))
        if ts is None:
            return False
        age = (float(now if now is not None else now_ts()) - ts)
    try:
        return float(age) > STALE_ROW_S
    except (TypeError, ValueError):
        return False


def _parse_ts(s):
    """Epoch seconds from an ISO stamp, else None. Never raises."""
    if not s:
        return None
    try:
        import datetime as _d
        txt = str(s).strip().replace("Z", "+00:00")
        dt = _d.datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_d.timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return None


#: [2026-07-31 (hx)] BRAIN AMNESIA. `learning-brain` is the brain's MEMORY;
#: `brain-vitals` is what it publishes each run. If the memory's `runs` falls
#: behind vitals' `run`, the brain is recomputing from a frozen state — it
#: looks healthy on every other key while `mult_streaks` cannot advance and the
#: 3-run promotion gate is unreachable. Measured 31-Jul: 337 vs 338 for THREE
#: DAYS, one multiplier published against 20 living bots.
#: How far `learning-brain`'s write may trail `brain-vitals`' before the
#: memory is judged broken. Generous (6h) against a brain that runs every
#: ~30-60 min: this must catch a DAYS-long freeze, not a slow cycle.
BRAIN_MEMORY_SKEW_S = float(os.environ.get("IMMUNE_BRAIN_SKEW_S", "21600"))


#: [2026-08-06] MONOTONE COUNTERS whose REGRESSION means the publisher
#: restarted: {state key: (dotted path to the counter, human name)}. Declared
#: rather than sniffed — a counter this organ does not understand must not be
#: guessed at, and an undeclared organ simply is not watched (visible in the
#: payload's `churn_watched`, never a silent omission).
#: [2026-08-16 (od)] THIRD ELEMENT: the dotted path to an AUTHORITATIVE
#: monotone restart count, when the organ publishes one. Optional — a 2-tuple
#: keeps the old reset/stall inference exactly. This exists because the
#: docstring below is honest about its own weakness: a RESET is only visible
#: BETWEEN samples, so "the counted number depends on when this organ happens
#: to wake up", and at an unlucky phase it reads ZERO while the organ restarts
#: 96x/day. `(nz)` gave the Parliament a counter that survives its own death
#: (persisted in the ecosystem DB on the Railway volume, monotone), so for
#: that organ the count can now be READ rather than inferred: deaths = the
#: delta between two sightings, exact at any sampling phase, no history
#: reconstruction and no floor heuristic.
#: [2026-08-16 (oi)] FOURTH ELEMENT: the dotted path to the running BUILD
#: STAMP. An increment with a NEW build is a DEPLOY; an increment on the SAME
#: build is a real death. Without it this sensor cannot tell them apart, which
#: is not hypothetical — see the (oi) entry: all 10 "restarts in 48h" that
#: paged the operator correlated with a deploy run inside 15 minutes, ZERO
#: unexplained. The comment above already predicted exactly this ("one restart
#: is an ordinary DEPLOY and must stay quiet, or this pages on every push")
#: and named the neighbour-cadence test as the unimplemented discriminator;
#: the build stamp is a better one — it is per-publisher, needs no second
#: organ's series, and answers the question directly.
RESTART_COUNTERS = {
    "parliament": ("data.cycles", "🏛️ the Parliament's supervisor loop",
                   "restarts", "build"),
}
#: Restarts inside RESTART_WINDOW_S before the churn is called sickness. One
#: restart is an ordinary DEPLOY and must stay quiet, or this pages on every
#: push.
#: [2026-08-14 (mi)] THE NEIGHBOUR TEST IS AN ASSERTION HERE, NOT AN
#: IMPLEMENTATION — corrected in place (I12) because the previous wording read
#: as though the detector performed it. It said: "a deploy restarts EVERY organ
#: in the image at once, and a crash-loop restarts one while its neighbours keep
#: their cadence." That IS the right discriminator and it is exactly how the
#: 6-Aug finding was reasoned — but a HUMAN did that comparison. `RESTART_COUNTERS`
#: declares ONE organ, so this function has no neighbour series to read and the
#: only thing standing between a deploy and a page is the bare count below.
#: MEASURED 13-Aug, the predicted false positive: 🏛️ the Parliament reset 7x
#: between 02:42Z and 09:52Z — every one inside that day's deploy storm, `errors`
#: 0, `stalled` [], and stable for the ~13h since. The detector fired on ordinary
#: deploy churn, which is the (gl) cry-wolf shape aimed at the operator's phone.
#: NOT "fixed" by raising the threshold or adding the check on one day's data:
#: the failure direction of a quieter detector is SILENCE on a real crash-loop,
#: and the (le) history above is a record of this sensor undercounting already.
#: Implementing it properly means declaring neighbour counters for the organs
#: sharing the freqtrade-bots image and requiring co-regression within a short
#: window — its own measurement, its own mutation tests, its own entry.
#: Four in a day is the current bar, and it is a COUNT, nothing more.
RESTART_CHURN_N = int(os.environ.get("IMMUNE_RESTART_CHURN_N", "4"))
RESTART_WINDOW_S = float(os.environ.get("IMMUNE_RESTART_WINDOW_S", "86400"))
#: [2026-08-06 (le)] THE FLOOR AT WHICH "NO ADVANCE" IS ITSELF THE FAULT.
#: The (la) rule counted only a DECREASE, so a boot that died before finishing
#: its first cycle published 0, then 0 again — and 0 -> 0 is not a decrease.
#: MEASURED over 24h of 🏛️ Parliament history the same evening: **245 healthy
#: publishes, every one of them ADVANCING** (min +1, median +2, max +3), and
#: **5 stagnant transitions, all 5 sitting at zero**. So for a looping organ,
#: no-advance never happens while it works, and at the floor it is the
#: signature of a boot that never completed a cycle. Detected count was 17 of
#: a true 22 — a 23% undercount, and in the limit (every boot dying before its
#: first cycle) the counter would never regress at all and the sensor would
#: read SILENT under TOTAL failure, which is the
#: [[convergent-metric-is-not-a-health-check]] trap built into the very
#: detector that exists to catch it.
#: Restricted to the FLOOR on purpose: an organ legitimately idling at a
#: non-zero count must stay quiet, so this claims nothing above it.
RESTART_FLOOR = float(os.environ.get("IMMUNE_RESTART_FLOOR", "0"))


def _dotted(payload, path):
    cur = payload
    for part in str(path).split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def churn_from_history(key, path, now, window_s=None, fetch=None):
    """(resets, stalls, n_samples) counted over the PUBLISHER'S OWN series, or
    None when the history is unavailable.

    [2026-08-06 (lg)] WHY THIS EXISTS: THE POINT SAMPLER ALIASES THE FAULT.
    `restart_churn` compared the counter between the immune organ's OWN cycles
    — one sample every `IMMUNE_INTERVAL_SEC` (900s, measured 94 rows/24h) —
    while 🏛️ the Parliament publishes every ~5 min and restarts every 15-60.
    That is ~1.3 samples per event, below the 2-per-event floor needed to
    resolve them, so events collapse into each other.
    MEASURED against the real 24h tape: replaying the shipped detector at the
    organ's REAL sample times gives **11 resets + 7 stalls = 18** where the
    tape holds **18 + 5 = 23** — resets undercounted 39%, composition wrong in
    both directions, first fire 51 minutes late. Worse, simulated at a STABLE
    15-minute restart period the sampler counts **95 at one phase and ZERO at
    two others**: every sample lands mid-boot on the same non-zero value, and a
    constant non-zero reading is certified healthy by design. So `(le)` did not
    close the convergent-metric trap — it MOVED it, from "dies before the first
    cycle" to "dies at a period that beats the sampler".
    The resolution belongs to the PUBLISHER, not the sampler: `bot_state_history`
    already holds the ~5-minute series `(le)` validated against, so read that
    and the count stops depending on when this organ happens to wake up.
    Stateless by construction — the whole window is recounted each call, so
    there is no memory to seed, drift or lose.
    """
    window_s = RESTART_WINDOW_S if window_s is None else window_s
    try:
        rows = (fetch or store.fetch_state_history)(key, limit=2000) or []
    except Exception:      # noqa: BLE001
        return None
    if not rows:
        return None
    series = []
    for r in rows:
        try:
            t = _parse_ts((r or {}).get("ts"))
        except Exception:      # noqa: BLE001
            continue
        if t is None or now - t > window_s or t > now:
            continue
        v = _dotted((r or {}).get("payload") or {}, path)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            series.append((t, float(v)))
    if len(series) < 2:
        return None
    series.sort()
    resets = stalls = 0
    for (_, a), (_, b) in zip(series, series[1:]):
        if b < a:
            resets += 1
        elif b == a and b <= RESTART_FLOOR:
            stalls += 1
    return resets, stalls, len(series)


def restart_churn(states, seen, now, min_n=None, window_s=None):
    """-> [{organ, detail}] when an organ's monotone counter keeps RESETTING.

    THE CLASS THIS CLOSES, and it is I13's twin. I13 says a dead loop runs no
    handler, so liveness is only visible from OUTSIDE — an age check. A
    RESTARTING loop defeats the age check from the other side: every boot
    republishes, so the key is permanently FRESH while the organ never
    completes any work. Age is the quantity the fault holds FIXED; the
    counter's regression is the quantity that grows with it (I2).

    MEASURED 6-Aug on 🏛️ the Parliament: `data.cycles` reset to 0 **15 times
    in 24h** (110->0, 250->0, 128->0, ...), the six PM books' equity/closed
    telemetry wiped to 1000.0/0 on every boot, and the key never once read
    stale — age 233s at the sweep that found it. Nothing paged, because the
    watchdog pages on staleness and the immune organ had no invariant for
    "publisher keeps restarting". Its neighbours in the same container held an
    unbroken cadence throughout (fleet-risk 291 samples/24h, brain runs
    monotone), which is what rules out a container restart and names the
    supervisor.

    `seen` is this organ's own durable memory — {key: {"last": n, "resets":
    [ts,...]}} — mutated in place and persisted by the caller, the same
    first-seen pattern application_sickness uses. No history table is read: a
    reset is only observable BETWEEN cycles, so the memory IS the sensor.

    FAIL-SAFE TOWARD SILENCE at every step: an absent key, a non-numeric
    counter, a stale payload (a stale organ is the watchdog's jurisdiction,
    matching organ_invariants) and a first sighting all claim nothing. A
    counter that ADVANCES or holds is healthy. Only a positive, repeated
    regression speaks.
    """
    min_n = RESTART_CHURN_N if min_n is None else min_n
    window_s = RESTART_WINDOW_S if window_s is None else window_s
    out = []
    for key, spec in sorted(RESTART_COUNTERS.items()):
        path, label = spec[0], spec[1]
        auth_path = spec[2] if len(spec) > 2 else None
        build_path = spec[3] if len(spec) > 3 else None
        st = states.get(key) or {}
        if not st or not _fresh(st, now):
            continue
        cur = _dotted(st, path)
        if not isinstance(cur, (int, float)) or isinstance(cur, bool):
            continue
        mem = dict(seen.get(key) or {})
        resets = [float(t) for t in (mem.get("resets") or [])
                  if isinstance(t, (int, float))]
        stalls = [float(t) for t in (mem.get("stalls") or [])
                  if isinstance(t, (int, float))]
        last = mem.get("last")
        if isinstance(last, (int, float)) and not isinstance(last, bool):
            if cur < last:
                resets.append(float(now))          # a boot that got somewhere
            elif cur == last and cur <= RESTART_FLOOR:
                # [(le)] ...and a boot that got NOWHERE. Counted separately so
                # each number keeps its exact meaning: `resets` are observed
                # regressions, `stalls` are publishes at the floor with no
                # cycle completed between them.
                stalls.append(float(now))
        resets = [t for t in resets if now - t <= window_s]
        stalls = [t for t in stalls if now - t <= window_s]
        seen[key] = {"last": float(cur), "resets": resets, "stalls": stalls}
        # [(lg)] THE PUBLISHER'S SERIES IS SENIOR TO THIS ORGAN'S SAMPLES.
        # Point sampling aliases the fault (see churn_from_history): the
        # counted number depends on when this organ happens to wake up, and at
        # an unlucky phase it is ZERO while the organ restarts 96x/day. When
        # the history is readable the count comes from it and the sampler's
        # tallies are used only as the FALLBACK, declared in `basis` so a
        # reader can tell which one produced the number.
        # [(od)] AUTHORITATIVE COUNT FIRST. A monotone counter the publisher
        # persists across its own death cannot alias: two sightings N apart
        # mean exactly N deaths, whatever the sampling phase. Only a positive
        # delta speaks; a first sighting claims nothing (the same fail-safe
        # this function applies everywhere else), and a DECREASE means the
        # durable store was reset or restored, which is not evidence of a
        # restart and must not be counted as one.
        auth = _dotted(st, auth_path) if auth_path else None
        if isinstance(auth, (int, float)) and not isinstance(auth, bool):
            prev_auth = mem.get("auth_last")
            deaths = [float(t) for t in (mem.get("auth_deaths") or [])
                      if isinstance(t, (int, float))]
            cur_build = _dotted(st, build_path) if build_path else None
            prev_build = mem.get("auth_build")
            deployed = (cur_build is not None and prev_build is not None
                        and cur_build != prev_build)
            if isinstance(prev_auth, (int, float)) and auth > prev_auth:
                if deployed:
                    # [(oi)] A NEW IMAGE EXPLAINS THE RESTART. Absorb the
                    # increment without counting it: a deploy restarts the
                    # container by design and paging for it is the (gl)
                    # cry-wolf shape aimed at the operator's phone. Only the
                    # increments this cannot explain are deaths.
                    pass
                else:
                    deaths.extend([float(now)] * int(auth - prev_auth))
            if cur_build is not None:
                seen[key]["auth_build"] = cur_build
            deaths = [t for t in deaths if now - t <= window_s]
            seen[key]["auth_last"] = float(auth)
            seen[key]["auth_deaths"] = deaths
            seen[key]["basis"] = (
                f"publisher's own counter (now {auth:g}), "
                f"deploy-discriminated by build stamp"
                if build_path else
                f"publisher's own counter (now {auth:g})")
            if len(deaths) >= min_n:
                hrs = window_s / 3600.0
                out.append({
                    "organ": key,
                    "detail": (f"{label}: {len(deaths)} RESTART(s) in "
                               f"{hrs:.0f}h, counted from the publisher's own "
                               f"durable counter ({auth_path}, now {auth:g}) "
                               f"— exact at any sampling phase, unlike the "
                               f"reset heuristic. The key stays FRESH on every "
                               f"boot, so no age check can see this, and "
                               f"in-process state is lost each time"),
                })
            continue

        hist = churn_from_history(key, path, now, window_s)
        if hist is not None:
            h_res, h_sta, h_n = hist
            total, n_res, n_sta = h_res + h_sta, h_res, h_sta
            basis = f"publisher series, {h_n} samples"
            bound = ""
        else:
            total, n_res, n_sta = len(resets) + len(stalls), len(resets), len(stalls)
            basis = "this organ's own samples"
            # I8/honesty: say the number is a floor when it is one.
            bound = (" — a LOWER BOUND: the publisher's history was unreadable "
                     "so this counts only what one sample per immune cycle "
                     "could see, which undercounts at short restart periods")
        seen[key]["basis"] = basis
        if total >= min_n:
            hrs = window_s / 3600.0
            # [(lg)] `stalls` counts OBSERVATIONS at the floor, not restarts.
            # Reporting them inside a "RESTARTED Nx" total was false — 5 of 7
            # counted stalls on the live tape provably had completed cycles.
            # The two numbers are now named separately (I8).
            _st = (f" plus {n_sta} publish(es) at {RESTART_FLOOR:g} with no "
                   f"cycle completed" if n_sta else "")
            out.append({
                "organ": key,
                "detail": (f"{label}: {n_res} RESTART(s) in {hrs:.0f}h{_st} "
                           f"({path} keeps resetting; now {cur:g}; basis: "
                           f"{basis}){bound} — the key stays FRESH on every "
                           f"boot, so no age check can see this, and "
                           f"in-process state is lost each time"),
            })
    return out


def brain_amnesia(brain_state, vitals_state, max_skew_s=None):
    """-> [{organ, detail}] when the brain's MEMORY key has stopped being
    written while it keeps publishing fresh vitals.

    THE TEST IS THE TIMESTAMP SKEW, NOT THE RUN COUNTER, and the first cut of
    this got that wrong. `learning-brain` and `brain-vitals` are written by the
    SAME process in the SAME cycle, so their `updated` stamps travel together;
    a memory three days behind fresh vitals is a failed write, full stop.

    The run counter CANNOT detect this, which is why the counter version fired
    nothing on the live payload it was written for. A brain whose save fails
    reloads run N, computes N+1, publishes N+1 and fails to store it — so the
    lag is PERMANENTLY 1, byte-identical to the normal write-after-publish
    ordering, no matter how many days it has been stuck. Measured: runs=337 vs
    run=338 after THREE DAYS. The counter is reported in the detail because it
    is useful context; it is not the trigger.

    Fail-safe QUIET: either key missing or either stamp unreadable says
    nothing — a booting brain or a briefly dark bus must not page anyone.
    """
    skew_max = BRAIN_MEMORY_SKEW_S if max_skew_s is None else max_skew_s
    b, v = (brain_state or {}), (vitals_state or {})
    bt = _parse_ts(b.get("updated") or b.get("updated_at"))
    vt = _parse_ts(v.get("updated") or v.get("updated_at"))
    # [2026-08-20 (rs)] A BLIND DETECTOR MUST SAY SO — it may not read as
    # "healthy". This returned [] whenever either stamp was unreadable, and the
    # brain's memory payload NEVER carried one: `save_state` records the time in
    # the bot_state `updated_at` COLUMN while `fetch_states` selects only
    # `(bot, state)`, so `bt` was None on every real cycle and I2's declared
    # enforcement returned [] forever, silently. `audit_doctrine_enforcement`
    # stayed green because the NAME resolves — precisely the "a named test could
    # be vacuous" caveat at the top of CLAUDE.md, realised.
    #
    # Fail-safe QUIET stays right where the silence is genuinely uninformative
    # (nothing to compare against, or no memory row yet). But vitals PRESENT and
    # readable while the memory carries no stamp at all is not a transient — it
    # is this guard unable to do its job, and reporting nothing there is exactly
    # how it hid.
    if vt is None:
        return []                      # nothing to compare against — quiet
    if bt is None:
        if not b:
            return []                  # no memory row yet — a booting brain
        return [{"organ": "learning-brain",
                 "detail": ("BRAIN AMNESIA CHECK IS BLIND — `learning-brain` "
                            "carries no `updated` stamp inside its state blob, "
                            "so the memory-vs-vitals skew cannot be computed "
                            "and I2's enforcement is inert. bot_learn stamps it "
                            "in `_save_state`; a payload without one is a "
                            "container running pre-(rs) code. This is NOT a "
                            "claim that the brain is amnesiac — it is a claim "
                            "that nothing can currently tell.")}]
    skew = vt - bt
    if skew <= skew_max:
        return []
    runs, run = b.get("runs"), v.get("run")
    return [{"organ": "learning-brain",
             "detail": (f"MEMORY NOT PERSISTING — vitals published "
                        f"{skew / 3600.0:.1f}h more recently than the stored "
                        f"state (runs={runs} vs run={run}). The brain reloads a "
                        f"frozen state every cycle, so mult_streaks cannot "
                        f"advance and streak-gated promotion is UNREACHABLE. "
                        f"Check bot_learn's 'BRAIN MEMORY NOT PERSISTED' line.")}]


def stale_writer_sickness(bot_rows, ok=None, min_stamped=5):
    """[2026-07-31 (hu)] A FRESH row published by a container running code
    that predates `extra.svc` — i.e. a deploy that reported OK and never
    landed. Returns [{organ, detail}].

    THE INCIDENT. Run 30598053371 printed `OK: 'funding-carry' deployed`, and
    `funding-carry` published NOTHING while `perps-funding-carry-lshadow` kept
    publishing every ~90-170s on build `fbb926402049` with no `svc` — pre-(hp)
    code, on a container the deploy never reached. Twenty samples over ten
    minutes showed ONE state and never a flip. The service actually running the
    book was `yield-harvester-shadow`, which had no deploy rule at all. Nothing
    in the fleet could see this: the workflow was green, the row was fresh, its
    P&L was sane, and the guard meant to catch the duplicate was in `main`
    rather than in the image.

    WHY THE TEST IS "NO svc" AND NOT A BUILD COMPARISON. `extra.build` is a
    content hash over a per-image FILE SET ((fd)), so predicting it needs that
    image's COPY list and a same-tree checkout — the repo-side prediction has
    already read as "the deploy never landed" when it had. The ABSENCE of a key
    the publisher now always writes needs no prediction at all.

    FAIL-SAFE QUIET. Requires `min_stamped` rows to carry `svc` before saying
    anything, so during the rollout — when nothing is stamped yet — this stays
    silent instead of flagging all 24 books. Absence of evidence is not
    sickness, which is the same direction every other detector here fails.
    """
    rows = [r for r in (bot_rows or []) if isinstance(r, dict)]
    ok = STALE_WRITER_OK if ok is None else ok
    stamped = [r for r in rows if (r.get("extra") or {}).get("svc")]
    if len(stamped) < min_stamped:
        return []                      # the stamp has not propagated yet
    out = []
    for r in rows:
        bot = str(r.get("bot") or "")
        if not bot or bot in ok:
            continue
        if (r.get("extra") or {}).get("svc"):
            continue
        # [2026-07-31 (hx)] A DEAD ROW IS NOT A STALE DEPLOY, and saying so was
        # an actively wrong instruction. (hu) shipped this detector and hours
        # later it fired on 🌾 carry with "its container is running code that
        # predates the stamp" — while that row was 779 MINUTES old, i.e. the
        # publisher had been gone since 03:10 and no container was running
        # anything. A row that has stopped publishing has no `svc` for the
        # trivial reason that it has no writer; diagnosing that as a deploy
        # problem sends the operator to the wrong system entirely.
        # STALENESS IS THE WATCHDOG'S CALL, not this detector's — it already
        # reports STALE rows, so claiming them here would double-report one
        # condition under two different names.
        if _row_stale(r):
            continue
        build = (r.get("extra") or {}).get("build")
        out.append({"organ": bot,
                    "detail": (f"publisher carries no extra.svc (build "
                               f"{build}) while {len(stamped)} rows do — its "
                               f"container is running code that predates the "
                               f"stamp, i.e. a deploy that never landed")})
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
    # [2026-08-05 SEED GUARD] the CHECKED read — load_state() collapses "no
    # row" and "READ FAILED" into one None, so a Postgres blip here looked
    # like a first run: `notified` empty (everything re-pages the moment the
    # gap limiter allows), `app_seen` empty (every lever's first-seen clock
    # resets), and the save below then OVERWRITES the durable memory with the
    # amnesia. Standard organ degrade (the 17-Jul judge/proprio fix): SKIP THE
    # CYCLE — an organ skipping one beat costs minutes; seeding costs the
    # ledger.
    _ok, _prior = store.load_state_checked(KEY)
    if not _ok:
        print("[fleet-immune] state read FAILED — skipping this cycle rather "
              "than seed an empty notified/app_seen over the record", flush=True)
        return None
    prior = _prior or {}
    prior_sick = set(prior.get("notified") or [])

    # one batched beat instead of five round-trips (fail-safe: batch {} on
    # DB failure -> every organ reads as absent, same as load_state failing)
    _keys = ("lighter-market", "brain-lens-forward", "regime-oracle",
             "xp-judge", "fleet-tuning", "fleet-proprioception",
             "brain-vitals",     # [2026-07-17] born-dark detector, see above
                                 # [2026-07-22] gapscout-census -> regime-oracle
             # [2026-07-30 (hh)] the two-writer ledger detector. WITHOUT THIS KEY
             # the scanner above is dead code — the classic registered-but-inert
             # shape, and the reason this list and the scanner must be changed in
             # the same commit. `test_immune_two_writers.py` asserts membership.
             "golive-readiness",
             # [2026-07-31 (hx)] the brain's MEMORY, read against
             # `brain-vitals` above to detect amnesia. Same lesson as the
             # (hh) note: without this key `brain_amnesia` is dead code.
             "learning-brain",
             # [2026-08-06] the restart-churn counter. Same lesson a third
             # time: without this key `restart_churn` is dead code, so the
             # key and the scanner move in one commit. Membership is pinned
             # by tests/autonomy/test_immune_restart_churn.py.
             ) + tuple(RESTART_COUNTERS)
    _batch = store.fetch_states(_keys) if hasattr(store, "fetch_states") else {}
    states = {k: (_batch.get(k) or store.load_state(k) or {}) for k in _keys} \
        if not _batch else {k: (_batch.get(k) or {}) for k in _keys}
    try:
        bot_rows = store.fetch_bot_pnl() or []
    except Exception:
        bot_rows = []

    # --- FILTRATION: prune the alert bloodstream ---------------------------
    # [2026-08-05 SEED GUARD] both fleet-alerts reads are CHECKED: this block
    # is a read-modify-WRITE of another producer's durable key, and a failed
    # re-read used to fall through as {} — turning the write below into a bare
    # {"alerts": ...} that drops the producer's updated/ttl_sec stamp, the
    # exact hazard the stamp note below names. Filtration is tidying; skipping
    # one cycle of it is free, a stamp wipe is not.
    pruned = []
    _ok_al, raw = store.load_state_checked("fleet-alerts")
    alerts = ((raw or {}).get("alerts") or []) if _ok_al else []
    keep, pruned = alert_fossils(alerts, now)
    if pruned:
        # re-read immediately before write to shrink the append race window
        _ok_al2, cur_raw = store.load_state_checked("fleet-alerts")
        if not _ok_al2:
            print("[fleet-immune] fleet-alerts re-read FAILED — prune skipped "
                  "this cycle (a blind write would drop the producer's stamp)",
                  flush=True)
            pruned = []
    if pruned:
        cur_raw = cur_raw or {}
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
    # [2026-08-06] restart churn: this organ's own memory of each watched
    # counter, carried cycle to cycle exactly like app_seen above (a reset is
    # only observable BETWEEN cycles, so the memory IS the sensor).
    churn_seen = dict(prior.get("churn_seen") or {})
    sick = (organ_invariants(states, now) + bot_row_sickness(bot_rows)
            + stale_writer_sickness(bot_rows)
            + restart_churn(states, churn_seen, now)
            + brain_amnesia(states.get("learning-brain"),
                            states.get("brain-vitals"))
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
        # [2026-08-06] the restart-churn memory (per watched counter: last
        # value + the reset timestamps still inside the window). Persisted
        # for the same reason app_seen is: without it every cycle is a first
        # sighting and the sensor can never fire.
        "churn_seen": churn_seen,
        # ...and WHICH counters are watched, so an organ that is NOT watched
        # is visible here rather than silently unmonitored.
        "churn_watched": sorted(RESTART_COUNTERS),
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
                           "stress": {"med": -3},                     # impossible
                           # [2026-07-30] truncated + negative turnover: the
                           # map five books rank their universe off
                           "vols": {"BTC": 10.0, "ETH": -1.0}},
        "brain-lens-forward": {"updated": fresh, "ttl_sec": 26000,
                               "lenses": {"dip": {"n4h": -5, "hit4h": 1.4}}},
        "regime-oracle": {"updated": fresh, "ttl_sec": 5400,
                          # impossible: hit-rate 1.4 outside [0,1], n < 0
                          "grades": {"BTC": {"d1": {"n": -2, "hit": 1.4}},
                                     "SPY": {"d1": {"n": 10, "hit": 0.6}}},  # fine
                          # impossible: more published than the universe
                          "coverage": {"universe": 12, "n_published": 15,
                                       "n_missing": -1}},
        "xp-judge": {"updated": fresh, "ttl_sec": 10800, "phase": "haywire"},
        "fleet-proprioception": {"updated": fresh, "ttl_sec": 2700,
                                 "episodes": [{"group": "taker", "start": 100.0,
                                               "end": 50.0},           # impossible
                                              {"group": "live", "start": 1.0,
                                               "end": 2.0}],           # fine
                                 "verdicts": {"taker.tp": {"verdict": "banana"},
                                              "taker.sl": {"verdict": "helping"}}},
        # [2026-07-30 (hh)] a compromised LEDGER: fresh, trusted, and not one
        # book's record. `clean-book` must stay silent in the same payload.
        "golive-readiness": {
            "updated": fresh, "ttl_sec": 86400,
            "books": {
                "dup-book": {"n": 82, "integrity": {
                    "two_writers": True, "same_pair_overlaps": 7,
                    "deepest_overlap_h": 9.14, "deepest_overlap_pair": "HYPE",
                    "peak_concurrent": 10}},
                "clean-book": {"n": 40, "integrity": {
                    "two_writers": False, "same_pair_overlaps": 0,
                    "deepest_overlap_h": 0.0, "deepest_overlap_pair": None,
                    "peak_concurrent": 4}},
                # a publisher predating the integrity field must not crash it
                "old-payload": {"n": 12}}},
        "stale-organ": {"updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 900,
                        "n_books": 1, "n_liquid": 999},
    }
    inv = organ_invariants(states, now)
    organs = {i["organ"] for i in inv}
    assert organs == {"lighter-market", "brain-lens-forward",
                      "regime-oracle", "xp-judge",
                      "fleet-proprioception", "golive-readiness"}, organs
    _gl = [i["detail"] for i in inv if i["organ"] == "golive-readiness"]
    assert len(_gl) == 1, f"only the compromised book may be flagged: {_gl}"
    assert "dup-book" in _gl[0] and "TWO WRITERS" in _gl[0], _gl
    assert "9.14h on HYPE" in _gl[0], _gl
    assert "OPERATOR" in _gl[0], "the only useful response is to tell a human"
    # a CLEAN gate payload is silent, and so is a STALE one (the watchdog's job)
    assert organ_invariants({"golive-readiness": {
        "updated": fresh, "ttl_sec": 86400, "books": {
            "b": {"integrity": {"two_writers": False}}}}}, now) == []
    assert organ_invariants({"golive-readiness": {
        "updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 86400, "books": {
            "b": {"integrity": {"two_writers": True}}}}}, now) == []
    # the KEY must be fetched, or the scanner above is dead code
    _src = open(os.path.abspath(__file__)).read()
    assert '"golive-readiness")' in _src or '"golive-readiness",' in _src, \
        "golive-readiness is scanned but never fetched — inert scanner"
    # regime-oracle must flag ALL FOUR impossible values in the fixture and
    # NONE of the fine ones (SPY's valid grade must not trip)
    # [2026-07-30] the scout's new invariants must FIRE on the fixture above
    _lm = [i["detail"] for i in inv if i["organ"] == "lighter-market"]
    assert any("vols covers 2 of 100" in d for d in _lm), _lm
    assert any("negative turnover" in d for d in _lm), _lm
    # ...and the ZERO-LIQUID case, which is the one that starves the live taker
    _zero = organ_invariants({"lighter-market": {
        "updated": fresh, "ttl_sec": 900, "n_books": 202, "n_liquid": 0}}, now)
    assert any("n_liquid 0 of 202" in i["detail"] for i in _zero), _zero
    # a HEALTHY scout payload must be SILENT — including an ABSENT vols map,
    # which is the documented fail-safe (consumers keep their configured list)
    _lm_ok = organ_invariants({"lighter-market": {
        "updated": fresh, "ttl_sec": 900, "n_books": 4, "n_liquid": 3,
        "stress": {"med": 7.5}}}, now)
    assert _lm_ok == [], _lm_ok
    _lm_ok2 = organ_invariants({"lighter-market": {
        "updated": fresh, "ttl_sec": 900, "n_books": 4, "n_liquid": 3,
        "stress": {"med": 7.5},
        "vols": {"A": 1.0, "B": 2.0, "C": 0.0, "D": 5.0}}}, now)
    assert _lm_ok2 == [], "a full, non-negative vols map is healthy"

    _ro = [i["detail"] for i in inv if i["organ"] == "regime-oracle"]
    assert len(_ro) == 4, _ro
    assert any("n -2 < 0" in d for d in _ro), _ro
    assert any("hit 1.4 outside" in d for d in _ro), _ro
    assert any("n_missing -1 < 0" in d for d in _ro), _ro
    assert any("> universe" in d for d in _ro), _ro
    assert not any("SPY" in d for d in _ro), _ro
    # a HEALTHY oracle payload must be silent (the fresh-but-right case)
    _ok = organ_invariants({"regime-oracle": {
        "updated": fresh, "ttl_sec": 5400,
        "grades": {"BTC": {"d1": {"n": 8, "hit": 0.5}, "d3": {"n": 8, "hit": 0.75}}},
        "coverage": {"universe": 12, "n_published": 9, "n_missing": 3}}}, now)
    assert _ok == [], _ok
    # a STALE oracle is the watchdog's job, not sickness
    assert organ_invariants({"regime-oracle": {
        "updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 900,
        "grades": {"BTC": {"d1": {"n": -9, "hit": 5.0}}}}}, now) == []

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

    # ---- [2026-07-31 (hu)] STALE WRITER: deployed OK, never landed --------
    # The measured shape: seven services stamped, carry unstamped on an old
    # build. Names and builds are the real ones from the (ht) deploy.
    def _row(bot, svc=None, build="deadbeef"):
        e = {"build": build}
        if svc:
            e["svc"] = svc
        return {"bot": bot, "extra": e}

    # [2026-08-02] The allow-list MECHANISM is tested with a SYNTHETIC list,
    # not with the live one. `STALE_WRITER_OK` is empty now that all three
    # marker-gated rows stamp, and arms that read `list(STALE_WRITER_OK)` went
    # vacuously green the moment it emptied — asserting "the declared rows
    # never flag" over an empty set proves nothing. Injecting `ok=` keeps the
    # mechanism under test while the real list honestly holds nothing.
    _live = ["some-marker-gated-row", "another-declared-row"]
    _OK = {b: "declared for a stated reason that is at least twenty chars long"
           for b in _live}
    _fleet = [_row("pm-rudd-lshadow", "freqtrade-bots"),
              _row("perps-funding-spread-lshadow", "counterweight-shadow"),
              _row("lighter-dislocation-lshadow", "snap-back-shadow"),
              _row("equities-regime-lshadow", "equities-regime-shadow"),
              _row("lighter-perp-sniper-lshadow", "perp-sniper-shadow"),
              _row("crypto-trend-daily-lshadow", "tide-rider-lighter-shadow"),
              _row("freqtrade-mum-lshadow", "family-lighter-shadow")]
    _carry = _row("perps-funding-carry-lshadow", None, "fbb926402049")

    sw = stale_writer_sickness(_fleet + [_carry])
    assert [s["organ"] for s in sw] == ["perps-funding-carry-lshadow"], sw
    assert "fbb926402049" in sw[0]["detail"], sw
    # a healthy fleet says NOTHING — a detector that flags everything trains
    # the operator to ignore it (the (hh) two-writers lesson).
    assert stale_writer_sickness(_fleet) == [], "all-stamped fleet must be quiet"
    # a DECLARED row never flags...
    assert stale_writer_sickness(_fleet + [_row(b) for b in _live],
                                 ok=_OK) == [], \
        "a declared row is DECLARED, not sick"
    # ...and the declaration is a real allow-list, not a blanket pass: an
    # UNdeclared unstamped row in the same payload still fires.
    _mixed = _fleet + [_row(b) for b in _live] + [_carry]
    assert [s["organ"] for s in stale_writer_sickness(_mixed, ok=_OK)] == \
        ["perps-funding-carry-lshadow"], stale_writer_sickness(_mixed, ok=_OK)
    # ...and with the REAL (now empty) list those same rows are NOT excused —
    # the whole reason the spent exemption was removed rather than kept.
    assert sorted(s["organ"] for s in
                  stale_writer_sickness(_fleet + [_row(b) for b in _live])) \
        == sorted(_live), "an empty allow-list must excuse nobody"
    # FAIL-SAFE QUIET during rollout: too few stamped rows -> say nothing
    assert stale_writer_sickness(_fleet[:2] + [_carry]) == [], \
        "below min_stamped the detector must stay silent, not flag everyone"
    assert stale_writer_sickness([]) == [] and stale_writer_sickness(None) == []
    # every declaration carries a REASON (the BORN_DARK_OK contract). Vacuous
    # while the list is empty — which is correct and is why the arm above
    # proves the empty list excuses nobody rather than relying on this one.
    assert all(isinstance(v, str) and len(v) > 20
               for v in STALE_WRITER_OK.values()), STALE_WRITER_OK
    # it is wired into run_once's aggregate, not merely defined
    import inspect as _ins2
    assert "stale_writer_sickness(bot_rows)" in _ins2.getsource(run_once), \
        "a detector nothing consumes is a note, not a guard"

    # ---- [2026-07-31 (hx)] A DEAD ROW IS NOT A STALE DEPLOY ---------------
    # (hu) shipped stale_writer_sickness and hours later it fired on 🌾 carry
    # with "a deploy that never landed" while that row was 779 MINUTES old —
    # the publisher had been gone since 03:10. Diagnosing a corpse as a deploy
    # problem sends the operator to the wrong system.
    _dead = _row("perps-funding-carry-lshadow", None, "fbb926402049")
    _dead["age_sec"] = 779 * 60
    assert stale_writer_sickness(_fleet + [_dead]) == [], \
        "a STALE row is the watchdog's finding, not a deploy diagnosis"
    # ...but a FRESH unstamped row is still exactly what this detector is for
    _live_unstamped = _row("perps-funding-carry-lshadow", None, "fbb926402049")
    _live_unstamped["age_sec"] = 120
    assert [s["organ"] for s in stale_writer_sickness(_fleet + [_live_unstamped])] \
        == ["perps-funding-carry-lshadow"], "a fresh unstamped row must fire"
    # the staleness test reads updated_at when age_sec is absent...
    import datetime as _dtm
    _old_iso = (_dtm.datetime.now(_dtm.timezone.utc)
                - _dtm.timedelta(seconds=STALE_ROW_S + 600)).isoformat()
    _d2 = _row("perps-funding-carry-lshadow", None, "x")
    _d2["updated_at"] = _old_iso
    assert stale_writer_sickness(_fleet + [_d2]) == [], "updated_at must count"
    # ...and an UNKNOWN age must NOT mute a finding — suppression only ever
    # happens on positive evidence of death.
    _unknown = _row("perps-funding-carry-lshadow", None, "x")
    assert stale_writer_sickness(_fleet + [_unknown]), \
        "an unreadable age must not silently suppress a real finding"

    # ---- [2026-07-31 (hx)] BRAIN AMNESIA ---------------------------------
    # Measured: learning-brain.runs=337 while brain-vitals.run=338 for THREE
    # DAYS. The brain looked healthy on every other key.
    # THE REAL SHAPE: memory stamped 28-Jul, vitals stamped today, and the run
    # counters only ONE apart -- which is why a counter test cannot see this.
    _mem = {"runs": 337, "updated": "2026-07-28T14:50:35+00:00"}
    _vit = {"run": 338, "updated": "2026-07-31T14:12:06+00:00"}
    _am = brain_amnesia(_mem, _vit)
    assert _am and _am[0]["organ"] == "learning-brain", _am
    assert "mult_streaks" in _am[0]["detail"], "say WHAT it costs"
    # THE REGRESSION THIS PINS: a counter-based test reads lag=1 here and says
    # nothing. If brain_amnesia ever goes back to triggering on the counter,
    # this fixture goes quiet and the assertion above fails.
    assert int(_vit["run"]) - int(_mem["runs"]) == 1, \
        "the fixture must keep the counters 1 apart or it stops proving this"
    # a healthy brain -- both stamps together -- says nothing
    _ok_t = "2026-07-31T14:12:06+00:00"
    assert brain_amnesia({"runs": 338, "updated": _ok_t},
                         {"run": 338, "updated": _ok_t}) == []
    # a normal cycle's small skew is not amnesia
    assert brain_amnesia({"runs": 337, "updated": "2026-07-31T13:00:00+00:00"},
                         {"run": 338, "updated": _ok_t}) == [], \
        "an hour of skew is a slow cycle, not a failed write"
    # [2026-08-20 (rs)] FAIL-SAFE QUIET, WHERE THE SILENCE IS INFORMATIVE — and
    # NOT where it is the guard failing to work. This loop used to include
    # `{"updated": "nope"}` as a must-stay-quiet case, i.e. it certified the very
    # blindness that made I2's enforcement inert: the brain's blob carries no
    # usable stamp on any real cycle, so `bt` was always None and this returned
    # [] forever. Quiet is still correct for a booting brain (no memory row) and
    # for nothing to compare against (dark vitals); a memory row that EXISTS but
    # carries no readable stamp is now REPORTED as blind.
    for _a, _b in (({}, _vit), (_mem, {}), (None, None),
                   (_mem, {"updated": None})):
        assert brain_amnesia(_a, _b) == [], (_a, _b)
    for _blind in ({"updated": "nope"}, {"runs": 337}):
        _d = brain_amnesia(_blind, _vit)
        assert _d and "BLIND" in _d[0]["detail"], \
            f"a memory row with no readable stamp must report blindness: {_blind}"
    # ...and the blind report must NOT claim amnesia — it claims unknowability
    assert "NOT a claim that the brain is amnesiac" in _d[0]["detail"]
    # wired, and its key is FETCHED — without that it is dead code (the (hh)
    # lesson, which this file already learned once)
    _src_run = _ins2.getsource(run_once)
    assert "brain_amnesia(" in _src_run, "brain_amnesia must be consumed"
    assert '"learning-brain"' in _src_run, \
        "learning-brain must be in the _keys fetch or the detector is inert"
    # [2026-08-06] RESTART CHURN — the 🏛️ Parliament shape, measured: the key
    # is FRESH on every boot (so no age check can see it) while `data.cycles`
    # resets 15x/24h. Fixture carries the payload's real nesting.
    def _parl(cycles, ts=None):
        return {"parliament": {"updated": _iso(ts or now), "ttl_sec": 900,
                               "data": {"cycles": cycles, "books": 204}}}
    _cs = {}
    # a first sighting claims nothing, and a counter that ADVANCES is healthy
    assert restart_churn(_parl(110), _cs, now) == []
    assert restart_churn(_parl(111), _cs, now) == []
    assert _cs["parliament"]["last"] == 111.0 and not _cs["parliament"]["resets"]
    # ...and one reset is an ordinary DEPLOY: below the bar, still quiet
    assert restart_churn(_parl(0), _cs, now) == []
    assert len(_cs["parliament"]["resets"]) == 1
    # four resets inside the window IS churn -> exactly one finding, naming
    # the organ the operator must go and look at (I8)
    for _c in (5, 0, 8, 0, 3, 0):
        _out = restart_churn(_parl(_c), _cs, now)
    assert len(_out) == 1 and _out[0]["organ"] == "parliament", _out
    # [(lg)] resets and stalls are named SEPARATELY — a stall is an observation
    # at the floor, not a restart, and folding them into one "RESTARTED Nx" was
    # false of 5 of the 7 stalls on the live tape.
    assert "4 RESTART(s)" in _out[0]["detail"], _out
    # ...and with no publisher history available the number must say it is a floor
    assert "LOWER BOUND" in _out[0]["detail"], _out
    # the window FORGETS: resets older than it stop counting (a churn last
    # week is not churn today)
    _old = {"parliament": {"last": 99.0, "resets": [now - 90000] * 9}}
    assert restart_churn(_parl(0), _old, now) == []
    # FAIL-SAFE QUIET: absent key, stale payload, non-numeric counter
    assert restart_churn({}, {}, now) == []
    _stale = {"parliament": {"updated": _iso(now - 99999), "ttl_sec": 900,
                             "data": {"cycles": 0}}}
    _cs2 = {"parliament": {"last": 500.0, "resets": [now] * 9}}
    assert restart_churn(_stale, _cs2, now) == [], \
        "a STALE organ is the watchdog's jurisdiction, not sickness"
    _junk = {"parliament": {"updated": _iso(now), "ttl_sec": 900,
                            "data": {"cycles": "many"}}}
    assert restart_churn(_junk, {"parliament": {"last": 9.0,
                                                "resets": [now] * 9}}, now) == []
    # wired, and its key is FETCHED — the (hh) lesson a third time
    assert "restart_churn(" in _src_run, "restart_churn must be consumed"
    assert "RESTART_COUNTERS" in _src_run, \
        "the watched keys must reach the _keys fetch or the detector is inert"
    assert "churn_seen" in _src_run, \
        "the durable memory must be persisted or every cycle is a first sighting"
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
        sys.exit(store.organ_main('fleet-immune', run_once))
