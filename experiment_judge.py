#!/usr/bin/env python3
"""
experiment_judge.py — 🧪⚖️ the shadow→live PROMOTION JUDGE.

WHY (2026-07-15, user): "positive changes made to shadow bots and new
implementations get carried across to the real money bots … so that they
also carry the edge to a win" — with the bar that separates EDGE from LUCK
(the Trail Blazer lesson: a +$197 paper month evaporated under scrutiny).
Nothing reaches real money on a hot streak; it reaches real money by
beating the live arm, per trade, over a real window, on both halves.

THE ARMS (Funding Farmer — the only live bot that trades often enough to
judge; Tide Rider trades ~weekly and stays backtest-validated):
  live arm    perps-funding-lighter-lighter  — env-default bars (until a
              promotion is in force via live.funding.* levers)
  shadow arm  perps-funding-lighter-lshadow  — the EXPERIMENT arm: runs the
              current candidate's bars via xp.* levers (zero real money)

LIFECYCLE (bot_state 'xp-judge'; hourly; one candidate at a time so
attribution is never confounded):
  IDLE      start the next CANDIDATE: assert its xp.* levers on the shadow
            arm, stamp started_ts. (Every close row carries extra.bars, so
            the ledger records which params produced what.)
  RUNNING   re-assert the xp levers each cycle. Once MIN_DAYS have passed
            and the floors are met (shadow >= MIN_CLOSES closes in-window,
            live >= LIVE_MIN_CLOSES for a fair pair), run the PAIRED
            evaluation: promote only if the shadow arm's mean per-trade
            pnl_pct is positive AND beats the live arm's by MARGIN_PP on
            the full window AND on both halves. Abandon at MAX_DAYS
            without clearing (verdict logged, cooldown, next candidate).
  PROMOTED  assert the live.funding.* counterpart(s) — this judge is the
            ONLY writer of that prefix — and keep the xp levers, so both
            arms run the same bars again (the control arm is restored).
            FADE WATCH: if the live arm's mean pnl_pct since promotion
            goes negative at n >= FADE_N, stop asserting; every lever
            expires back to env defaults on its own. Cooldown, then the
            queue continues. [16-Jul evening] prop_fade is the EARLIER
            signal: fleet_proprioception grades the promotion's episodes
            per-trade vs the live arm's own pre-window AND the shadow
            twin — a fresh HURTING verdict releases before the absolute
            fade bar is reached. The judge stays the only writer;
            proprioception is evidence in, never a hand on the lever.

Every transition pushes to the phone (urgent for PROMOTE and FADE — real
money changed). Fail-safe: no DB / short ledger -> nothing is asserted and
whatever was live expires back to env defaults within the lever TTL.

Run-once process; run_all.sh loops it hourly. --selftest is offline.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
import fleet_tuning as tuning

KEY = "xp-judge"
TTL_SEC = int(os.environ.get("XPJ_TTL_SEC", "10800"))
LEVER_TTL = int(os.environ.get("XPJ_LEVER_TTL", "7800"))      # ~2h re-assert
SHADOW_BOT = os.environ.get("XPJ_SHADOW_BOT", "perps-funding-lighter-lshadow")
LIVE_BOT = os.environ.get("XPJ_LIVE_BOT", "perps-funding-lighter-lighter")
MIN_DAYS = float(os.environ.get("XPJ_MIN_DAYS", "7"))
MAX_DAYS = float(os.environ.get("XPJ_MAX_DAYS", "14"))
# [2026-07-17 IMB-07] the done-list AGES: a finite candidate universe (3
# statics + <=6 incubator lever-sets) with a lifetime done-list permanently
# self-exhausted the pipeline — an ABANDONED/FADED candidate becomes
# retry-eligible after this many days. Retry is FALLBACK-only (see
# pick_candidate): untried candidates always come first.
DONE_RETRY_D = float(os.environ.get("XPJ_DONE_RETRY_D", "28"))
MIN_CLOSES = int(os.environ.get("XPJ_MIN_CLOSES", "30"))      # shadow arm
LIVE_MIN_CLOSES = int(os.environ.get("XPJ_LIVE_MIN_CLOSES", "10"))
MARGIN_PP = float(os.environ.get("XPJ_MARGIN_PP", "0.5"))     # per-trade pp
FADE_N = int(os.environ.get("XPJ_FADE_N", "15"))
COOLDOWN_H = float(os.environ.get("XPJ_COOLDOWN_H", "48"))
# [2026-07-16 AUDIT] promoted-phase ledger blackout tolerance: keep re-asserting
# live levers through a SHORT ledger outage (a DB blip shouldn't release a
# 7d-earned promotion), but past this many consecutive blind cycles stop
# asserting — fade-watch is blind, so the fail-safe direction (levers expire
# back to env defaults) must win over an indefinitely-blind promotion.
BLIND_MAX = int(os.environ.get("XPJ_BLIND_MAX_CYCLES", "24"))

# One candidate at a time, in order. First: the gate widening the 11-Jul
# scanner review explicitly queued as "opt-in, shadow-validate first".
CANDIDATES = [
    # [2026-07-17 BASIS FIX] /8 with the fleet funding basis. This candidate
    # is the 11-Jul "opt-in, shadow-validate" gate WIDENING: 0.30 old units
    # == 0.0375 TRUE apr, still a widening vs the 0.05 TRUE env default.
    # The experiment is unchanged; only its denomination is.
    {"name": "enter-gate-0.0375", "levers": {"xp.funding.enter_apr": 0.0375}},
    {"name": "tp-0.06",         "levers": {"xp.funding.take_profit": 0.06}},
    {"name": "hold-48",         "levers": {"xp.funding.max_hold_h": 48.0}},
]
XP_TO_LIVE = {"xp.funding.enter_apr": "live.funding.enter_apr",
              "xp.funding.take_profit": "live.funding.take_profit",
              "xp.funding.max_hold_h": "live.funding.max_hold_h"}


def now_ts():
    return datetime.now(timezone.utc).timestamp()


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def parse_ts(s):
    s = str(s).strip().replace("Z", "+00:00")
    if s.endswith(" UTC"):
        s = s[:-4] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


# ---------------------------------------------------------------------------
# pure evaluation (selftested offline)
# ---------------------------------------------------------------------------

def ran_candidate(row, levers):
    """PROOF the arm actually APPLIED these levers on this close.

    [2026-07-16 SKEW GATE] `extra.bars` is stamped by the ARM, and only from
    inside its apply_levers() — an image with no lever-reading code
    structurally CANNOT emit it. That makes a missing receipt DISPROOF, not
    silence, which is the whole point: this gate must fail CLOSED.

    Why it exists: the judge asserted xp.funding.enter_apr=0.30 for hours at a
    frozen shadow arm carrying zero lever code (30 closes, 0 receipts). It runs
    the env default 0.40 — the SAME gate live runs — so the paired bar was
    scoring 07-11-code vs 07-16-code and calling the difference the candidate's
    edge, on a path that promotes to live.funding.* (REAL MONEY).
    """
    bars = (row.get("extra") or {}).get("bars")
    if not isinstance(bars, dict):
        return False
    for name, want in (levers or {}).items():
        # xp.funding.enter_apr -> enter_apr (the arm stamps the bare bar name)
        got = bars.get(str(name).split(".")[-1])
        try:
            if got is None or abs(float(got) - float(want)) > 1e-9:
                return False
        except (TypeError, ValueError):
            return False
    return True


def arm_trades(rows, bot, start_ts, end_ts=None, levers=None):
    """[(close_ts, pnl_pct)] for one arm inside the window, oldest first.

    levers=None keeps the historical behaviour (time-window attribution only) —
    correct for the LIVE control arm, which runs env defaults and whose rows
    predate the receipt. Pass levers to count ONLY closes the arm PROVED it ran
    them on (see ran_candidate).
    """
    out = []
    for r in rows or []:
        if str(r.get("bot")) != bot or r.get("profit_ratio") is None:
            continue
        if levers is not None and not ran_candidate(r, levers):
            continue
        try:
            ts = parse_ts(r.get("close_ts"))
        except Exception:
            continue
        if ts >= start_ts and (end_ts is None or ts < end_ts):
            out.append((ts, float(r["profit_ratio"])))
    out.sort()
    return out


def _mean_pct(trades):
    return 100.0 * sum(p for _, p in trades) / len(trades) if trades else None


def paired_eval(rows, start_ts, end_ts, shadow_bot=None, live_bot=None,
                min_closes=None, live_min=None, margin_pp=None,
                cand_levers=None):
    """The promotion bar. Returns a verdict dict; verdict['promote'] is True
    only when the shadow arm is positive AND beats the live arm per-trade by
    margin_pp on the FULL window AND on BOTH halves (the doctrine's
    both-halves rule — a candidate that won one lucky week doesn't clear).

    [2026-07-16] cand_levers gates the SHADOW arm on proof-of-application: a
    close counts only if its receipt shows the arm ran the candidate's bars.
    The LIVE arm is deliberately NOT gated — it is the control running env
    defaults, and its rows predate the receipt (1 of 14 stamped), so gating it
    would starve the baseline and freeze the pipeline for good.
    """
    shadow_bot = shadow_bot or SHADOW_BOT
    live_bot = live_bot or LIVE_BOT
    min_closes = min_closes or MIN_CLOSES
    live_min = live_min or LIVE_MIN_CLOSES
    margin_pp = MARGIN_PP if margin_pp is None else margin_pp
    sh = arm_trades(rows, shadow_bot, start_ts, end_ts, levers=cand_levers)
    lv = arm_trades(rows, live_bot, start_ts, end_ts)
    v = {"promote": False, "n_shadow": len(sh), "n_live": len(lv),
         "shadow_mean_pct": _mean_pct(sh), "live_mean_pct": _mean_pct(lv)}
    if cand_levers:
        # ARM SKEW: the arm closed trades in-window but proved NONE of them ran
        # the candidate. Distinct from "not enough data yet" — the experiment
        # is not running at all, so no window will ever make it valid. Caller
        # must NOT age this toward ABANDONED (that would retire a possibly-good
        # candidate on a verdict about an experiment that never happened).
        n_all = len(arm_trades(rows, shadow_bot, start_ts, end_ts))
        v["n_shadow_closes"] = n_all
        if n_all and not sh:
            v["arm_skew"] = True
            v["why"] = (f"ARM NOT APPLYING: 0/{n_all} shadow closes carry a "
                        f"receipt for {json.dumps(cand_levers)} — the arm is "
                        f"not running this experiment")
            return v
    if len(sh) < min_closes or len(lv) < live_min:
        v["why"] = f"floors: shadow {len(sh)}/{min_closes}, live {len(lv)}/{live_min}"
        return v
    mid = start_ts + (end_ts - start_ts) / 2.0
    # [2026-07-16] per-half sample floors. The full-window floors said nothing
    # about the halves, so ONE live trade in a half set that half's entire
    # baseline and the both-halves rule — the doctrine's central noise filter —
    # degenerated into a noise amplifier on the exact comparison that moves
    # real money. Floors derive from the effective window floors (env-tunable
    # via the same XPJ_* knobs), so an even split of exactly-at-floor data
    # still clears; a lopsided one holds until the thin half fills in.
    half_sh_min = max(2, min_closes // 2)
    half_lv_min = max(3, live_min // 2)
    for a, b, label in ((start_ts, mid, "h1"), (mid, end_ts, "h2")):
        sh_h = arm_trades(rows, shadow_bot, a, b, levers=cand_levers)
        lv_h = arm_trades(rows, live_bot, a, b)
        if len(sh_h) < half_sh_min or len(lv_h) < half_lv_min:
            v[label] = {"shadow_n": len(sh_h), "live_n": len(lv_h)}
            v["why"] = (f"{label} under-powered: shadow {len(sh_h)}/"
                        f"{half_sh_min}, live {len(lv_h)}/{half_lv_min}")
            return v
        shm = _mean_pct(sh_h)
        lvm = _mean_pct(lv_h)
        v[label] = {"shadow": shm, "live": lvm}
        # [2026-07-16 AUDIT FIX] each half must clear the SAME margin as the
        # full window — `shm > lvm` by any amount let one half's edge be pure
        # noise (+0.01pp), which is the lucky-half pattern this bar exists to
        # reject before real money moves.
        if shm is None or lvm is None or (shm - lvm) < margin_pp:
            v["why"] = (f"{label}: shadow {shm} vs live {lvm} — edge < margin "
                        f"{margin_pp}pp on this half")
            return v
    full_gap = v["shadow_mean_pct"] - v["live_mean_pct"]
    v["gap_pp"] = round(full_gap, 3)
    if v["shadow_mean_pct"] <= 0:
        v["why"] = "shadow arm not positive in its own right"
        return v
    if full_gap < margin_pp:
        v["why"] = f"gap {full_gap:.2f}pp < margin {margin_pp}pp"
        return v
    v["promote"] = True
    v["why"] = (f"shadow beats live by {full_gap:.2f}pp/trade over the window "
                f"AND both halves (n={len(sh)} vs {len(lv)})")
    return v


def fade_check(rows, promoted_ts, now, live_bot=None, fade_n=None,
               baseline_pct=None, margin_pp=None):
    """True when the promoted lever is measured HURTING the live arm.

    [2026-07-16] Two release bars; either trips (restrict-only — an extra
    release path can only ever pull a lever OFF real money, never keep one on):

      ABSOLUTE — recent live mean < 0 (the original bar).
      RELATIVE — recent live mean has fallen >= margin_pp below the arm's own
        PRE-promotion baseline (the paired window's live mean, stamped into
        state at PROMOTE). The old bar was absolute-only: a lever that cut
        live from +0.80%%/trade to +0.10%% destroyed the promoted edge without
        inverting the sign and could stay in force forever. The promotion bar
        is relative (+margin vs live); the release bar must be too.

    Both bars run on the ROLLING last fade_n closes, not the cumulative mean
    since promotion — the cumulative mean converges toward its early value as
    n grows, so a LATE fade became mathematically unreachable.

    Fail-safe: fewer than fade_n closes -> no release signal here (the lever
    TTL + the blind-cycle guard remain the backstop); missing/invalid baseline
    -> absolute bar only, exactly the historical behaviour.
    """
    lv = arm_trades(rows, live_bot or LIVE_BOT, promoted_ts, now)
    k = int(fade_n or FADE_N)
    if len(lv) < k:
        return False, len(lv), _mean_pct(lv)
    m = _mean_pct(lv[-k:])
    if m is None:
        return False, len(lv), m
    if m < 0:
        return True, len(lv), m
    mp = MARGIN_PP if margin_pp is None else float(margin_pp)
    try:
        if baseline_pct is not None and m < float(baseline_pct) - mp:
            return True, len(lv), m
    except (TypeError, ValueError):
        pass
    return False, len(lv), m


def prop_fade(prop_state, live_levers, now):
    """[2026-07-16 evening, operator: 'the live lane needs to learn'] The
    EARLIER fade signal: fleet_proprioception grades every live.funding.*
    episode per-trade against the live arm's own pre-window AND the shadow
    twin; a fresh HURTING verdict on a promoted lever means the promotion
    is measurably underperforming BOTH baselines — release it before the
    absolute fade bar (live mean < 0 at n>=FADE_N) is even reached. The
    judge stays the ONLY writer of live.funding.*; proprioception is
    evidence in, never a hand on the lever. Fail-safe False on a dark/
    stale/absent organ. Returns (fading, why). Pure — selftested."""
    try:
        upd = parse_ts((prop_state or {}).get("updated"))
        if now - upd > float(prop_state.get("ttl_sec") or 0):
            return False, None
        for k in sorted(live_levers or ()):
            v = (prop_state.get("verdicts") or {}).get(k)
            if isinstance(v, dict) and v.get("verdict") == "hurting":
                return True, (f"proprioception: {k} graded HURTING "
                              f"(bad {v.get('bad')}/{v.get('n')} episodes vs "
                              f"pre-window + shadow twin)")
    except Exception:
        return False, None
    return False, None


# ---------------------------------------------------------------------------

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send_push(title, body, priority="default"):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", "test_tube")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[xp-judge] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def _assert_levers(levers, reason, evidence):
    return tuning.write_levers(
        {k: {"value": v, "reason": reason[:180], "evidence": evidence[:280]}
         for k, v in levers.items()},
        set_by="experiment-judge", ttl_sec=LEVER_TTL)


def _asserted(rc, levers):
    """[2026-07-16] Did the rail write actually LAND? write_levers returns the
    payload written, or None when nothing valid survived (unknown lever,
    out-of-lane, clamp reject, no DB) — documented as never raising. Every
    call site used to discard that return, so a silently-dropped write left
    the judge counting days toward promotion on an experiment it never
    asserted, and could stamp phase=promoted while no live lever was in
    force. Pure — selftested."""
    got = (rc or {}).get("levers") or {}
    return bool(levers) and all(k in got for k in levers)


def _lever_sig(levers):
    """A candidate's IDENTITY: the experiment it actually runs, not its name.
    Values are floated so 48 and 48.0 are one experiment. Never raises — a
    non-numeric value keeps its raw form rather than sinking the whole pool."""
    out = []
    for k in sorted(levers or {}):
        v = levers[k]
        try:
            v = float(v)
        except (TypeError, ValueError):
            pass
        out.append((k, v))
    return tuple(out)


def candidate_pool(queue):
    """The static CANDIDATES followed by fresh incubator proposals from
    'xp-queue', deduped by name AND by LEVER SIGNATURE (static wins). Only
    proposals whose levers are all registered xp.funding.* are admitted — an
    offspring can't smuggle an unknown lever past the judge. Pure — selftested.

    [2026-07-17 AUDIT] Signature dedup added. Name dedup ALONE was vacuous
    here: the incubator mints its own namespace (`xp-<gene>-<allele>`,
    strategy_incubator.py:517) which can never collide with a static name, so
    three of its six cycle-1 proposals were byte-identical experiments to the
    three statics wearing different names — and `done`/`next_candidate` are
    name-based, so each one bought a SECOND >=7d slot on a SERIAL pipeline
    that is the fleet's only path to live.funding.*. Measured: pool of 9 =
    6 distinct experiments + 3 duplicates = >=21 wasted judge-days.
    The old selftest missed it because its dup fixture re-used a static NAME
    — the one shape the incubator never emits (see the negative fixture in
    _selftest). Dedup on identity, not on label. Restrict-only: this can only
    REMOVE a candidate that some earlier pool entry already tests."""
    pool, seen, sigs = [], set(), set()
    for c in CANDIDATES:
        pool.append(c)
        seen.add(c["name"])
        sigs.add(_lever_sig(c["levers"]))
    for c in (queue or {}).get("candidates", []):
        nm, lv = c.get("name"), c.get("levers") or {}
        if not nm or nm in seen:
            continue
        if lv and all(k in XP_TO_LIVE for k in lv):
            sig = _lever_sig(lv)
            if sig in sigs:
                continue          # same experiment, different label
            pool.append({"name": nm, "levers": lv})
            seen.add(nm)
            sigs.add(sig)
    return pool


def next_candidate(pool, done, current):
    """First pool candidate not already completed and not the current one.
    Name-based so the pool may GROW (incubator appends) without reindexing.
    Pure — selftested."""
    done = set(done or [])
    for c in pool:
        if c["name"] not in done and c["name"] != current:
            return c
    return None


def pick_candidate(pool, done, done_at, current, now, retry_sec):
    """[2026-07-17 IMB-07] (candidate, retried) — untried candidates FIRST,
    always; a done entry aged past retry_sec is retry-eligible ONLY when
    nothing untried remains. Plain aging was verify-refuted: the statics
    sit ahead of offspring in pool order and rotate (~16d per failed slot)
    slower than the retry window, so an aged static would be re-selected
    ahead of every NEVER-tried offspring, forever — the fallback shape
    starves nothing. Pure — selftested."""
    cand = next_candidate(pool, done, current)
    if cand is not None:
        return cand, False
    aged = {n for n in (done or [])
            if now - (done_at or {}).get(n, now) >= retry_sec}
    if not aged:
        return None, False
    cand = next_candidate(pool, [n for n in done if n not in aged], current)
    return cand, cand is not None


def _num(x, d=0.0):
    """Corrupt/legacy state fields must reset the judge, never crash-loop it."""
    try:
        return float(x)
    except Exception:
        return d


def _needs_reset(phase, current, spec):
    """True when the judge is mid-experiment (running/promoted) but the stored
    spec is missing or mismatched — e.g. state written by the old index-based
    code before the 16-Jul name-based refactor. `levers` must be a non-empty
    dict ({"levers": None} passed the old `in` check and crashed downstream).
    Pure — selftested."""
    if phase not in ("running", "promoted"):
        return False
    if not (current and isinstance(spec, dict) and spec.get("name") == current
            and isinstance(spec.get("levers"), dict) and spec.get("levers")):
        return True
    # a persisted spec whose lever was dropped from XP_TO_LIVE would KeyError
    # at promotion time — treat it as invalid state, not a crash-loop
    return any(k not in XP_TO_LIVE for k in spec["levers"])


def run_once():
    now = now_ts()
    st = store.load_state(KEY) or {}
    phase = st.get("phase") or "idle"
    done = list(st.get("done") or [])
    # [2026-07-17 IMB-07] done_at stamps make the done-list AGEABLE. Legacy
    # names with no stamp (pre-aging state) are stamped NOW — a fresh retry
    # clock, never an instant flood-back.
    done_at = {k: _num(v, now) for k, v in (st.get("done_at") or {}).items()}
    for _n in done:
        done_at.setdefault(_n, now)
    done_at = {k: v for k, v in done_at.items() if k in done}
    current = st.get("current")
    spec = st.get("spec") or {}                 # full {name, levers} of current
    verdicts = st.get("verdicts") or []
    rows = store.fetch_paper_trades(limit=4000)
    have_ledger = bool(rows)

    def save(**kw):
        payload = {"updated": iso(now), "ttl_sec": TTL_SEC,
                   "phase": kw.get("phase", phase),
                   "current": kw.get("current", current),
                   "spec": kw.get("spec", spec),
                   "candidate": (kw.get("current", current)
                                 if kw.get("phase", phase) in ("running", "promoted")
                                 else None),
                   "done": kw.get("done", done),
                   "done_at": kw.get("done_at", done_at),
                   "started_ts": kw.get("started_ts", st.get("started_ts")),
                   "promoted_ts": kw.get("promoted_ts", st.get("promoted_ts")),
                   "cooldown_until": kw.get("cooldown_until", st.get("cooldown_until")),
                   "blind_cycles": kw.get("blind_cycles", st.get("blind_cycles") or 0),
                   # [2026-07-16] sticky across cycles so the urgent ARM-SKEW
                   # push fires once per episode, not every 30 min forever.
                   "skew_notified": bool(kw.get("skew_notified",
                                                st.get("skew_notified"))),
                   # [2026-07-16] same once-per-episode contract for failed
                   # rail writes (idle-start / re-assert / promote).
                   "assert_fail_notified": bool(kw.get("assert_fail_notified",
                                                       st.get("assert_fail_notified"))),
                   # [2026-07-16] the live arm's pre-promotion mean, stamped at
                   # PROMOTE — the relative fade bar's anchor. None for
                   # promotions predating the stamp (absolute bar only).
                   "promote_baseline": kw.get("promote_baseline",
                                              st.get("promote_baseline")),
                   "verdicts": verdicts[-10:], "last_eval": kw.get("last_eval")}
        store.save_state(KEY, payload)
        if hasattr(store, "save_history"):
            try:
                # [2026-07-16 AUDIT FIX] snapshot the FULL state, not a
                # {phase, candidate} summary — fleet_regen restores the judge
                # from these rows, and a summary "repair" wiped done/verdicts/
                # spec (total memory loss, promotion dropped).
                store.save_history(KEY, payload)
            except Exception:
                pass
        print(f"[xp-judge] {iso(now)} phase={payload['phase']} "
              f"candidate={payload['candidate']} "
              f"{kw.get('note') or ''}", flush=True)
        return payload

    if phase == "idle":
        if _num(st.get("cooldown_until")) > now:
            return save(note=f"cooldown until {iso(_num(st['cooldown_until']))}")
        if not have_ledger:
            return save(note="no ledger visible — asserting nothing (fail-safe)")
        pool = candidate_pool(store.load_state("xp-queue") or {})
        cand, _retried = pick_candidate(pool, done, done_at, current, now,
                                        DONE_RETRY_D * 86400)
        if cand is None:
            return save(note="queue exhausted — awaiting new incubator "
                             "proposals (or a done entry aging past "
                             f"{DONE_RETRY_D:g}d)")
        if _retried:
            done = [n for n in done if n != cand["name"]]
            done_at.pop(cand["name"], None)
            print(f"[xp-judge] RETRYING aged-out candidate {cand['name']} "
                  f"(done {DONE_RETRY_D:g}d+ ago; no untried candidates "
                  f"remain)", flush=True)
        # [2026-07-16] a candidate the registry can NEVER accept (unknown
        # lever / unclampable value) must not retry forever — mark INVALID and
        # move on, spending no judge slot. Distinct from a transient write
        # failure below, which retries.
        bad = [k for k, v in cand["levers"].items()
               if k not in tuning.LEVERS or tuning.clamp(k, v) is None]
        if bad:
            verdicts.append({"name": cand["name"], "verdict": "INVALID",
                             "ts": iso(now),
                             "why": f"registry rejected levers: {bad}"})
            send_push(f"experiment INVALID: {cand['name']}",
                      f"registry rejected {bad} — skipped, no judge slot spent")
            return save(done=done + [cand["name"]],
                        done_at={**done_at, cand["name"]: now},
                        note=f"INVALID {cand['name']}: registry rejected {bad}")
        rc = _assert_levers(cand["levers"], f"experiment {cand['name']} started",
                            f"shadow arm {SHADOW_BOT}; judge bar: {MIN_DAYS}d/"
                            f"{MIN_CLOSES} closes/+{MARGIN_PP}pp both-halves")
        if not _asserted(rc, cand["levers"]):
            # [2026-07-16] the write did not land (no DB / lock lost) — the
            # experiment did NOT start. Without this the judge stamped
            # started_ts and counted days on an arm running env defaults.
            return save(note=f"lever write did not land for {cand['name']} — "
                             f"experiment NOT started, retrying next cycle")
        send_push(f"experiment started: {cand['name']}",
                  f"shadow arm now runs {json.dumps(cand['levers'])}; "
                  f"promotion bar {MIN_DAYS:g}d / {MIN_CLOSES} closes / "
                  f"+{MARGIN_PP}pp vs live on both halves")
        return save(phase="running", current=cand["name"], spec=cand,
                    started_ts=now, note=f"STARTED {cand['name']}")

    # running / promoted use the stored spec. [2026-07-16 FIX] Guard the
    # migration from the OLD index-based state (cand_idx, no 'current'/'spec'):
    # a running/promoted phase with no valid spec used to KeyError on
    # cand['levers'] every cycle (the judge was dead ~9h). Reset to idle and
    # re-select from the pool cleanly instead.
    if _needs_reset(phase, current, spec):
        return save(phase="idle", current=None, spec={},
                    note="legacy/partial judge state (no valid spec) — reset to idle")
    cand = spec

    if phase == "running":
        started = _num(st.get("started_ts"), now)
        rc = _assert_levers(cand["levers"], f"experiment {cand['name']} running",
                            f"started {iso(started)}")
        assert_ok = _asserted(rc, cand["levers"])
        days = (now - started) / 86400.0
        ev = (paired_eval(rows, started, now, cand_levers=cand.get("levers"))
              if have_ledger else {"promote": False, "why": "no ledger"})
        # [2026-07-16] ARM SKEW -> HOLD. The arm is closing trades but proving
        # none of them ran the candidate, so every number here is about a
        # different experiment. Do not promote (real money) and do not age
        # toward ABANDONED (a false negative retires the candidate for good).
        # Stay running and stay LOUD until the arm is fixed — fail-closed:
        # a stuck, noisy queue beats a phantom promotion.
        if ev.get("arm_skew"):
            if not st.get("skew_notified"):
                send_push(f"experiment ARM NOT APPLYING: {cand['name']}",
                          f"{ev['why']}\nthe judge is holding — no promotion "
                          f"can clear until the arm runs the candidate's bars",
                          priority="urgent")
            return save(last_eval=ev, skew_notified=True,
                        note=f"ARM SKEW {cand['name']}: {ev['why']}")
        if st.get("skew_notified"):
            # Arm recovered. Restart the clock: `days` accrued while the arm
            # was NOT applying, so without this the first good cycle could land
            # past MAX_DAYS and instantly ABANDON an experiment that had never
            # actually run. The window must cover only the applied period.
            return save(last_eval=ev, skew_notified=False, started_ts=now,
                        note=f"arm applying again: {cand['name']} — "
                             f"experiment clock restarted")
        # [2026-07-16] the re-assert did not land: the lever will TTL-expire
        # and the arm reverts to env defaults — data from here on measures the
        # wrong experiment. Same HOLD semantics as ARM SKEW (which the receipt
        # gate would eventually raise anyway once unstamped closes arrive —
        # this just refuses to promote/abandon in the gap before that).
        if not assert_ok:
            if not st.get("assert_fail_notified"):
                send_push(f"experiment lever write FAILING: {cand['name']}",
                          "the judge could not re-assert the xp levers — "
                          "holding (not promoting, not aging); the arm reverts "
                          "to env defaults when the TTL lapses",
                          priority="urgent")
            return save(assert_fail_notified=True, last_eval=ev,
                        note=f"lever re-assert did not land — holding "
                             f"{cand['name']}")
        if st.get("assert_fail_notified"):
            # writes recovered — restart the clock for the same reason as the
            # skew recovery above: days accrued while the arm ran defaults.
            return save(assert_fail_notified=False, started_ts=now,
                        last_eval=ev,
                        note=f"lever writes recovered: {cand['name']} — "
                             f"experiment clock restarted")
        if days >= MIN_DAYS and ev["promote"]:
            live_levers = {XP_TO_LIVE[k]: v for k, v in cand["levers"].items()}
            rc = _assert_levers({**cand["levers"], **live_levers},
                                f"PROMOTED {cand['name']}", ev["why"])
            # [2026-07-16] the promotion IS the write. If it did not land,
            # nothing reached real money — do not stamp phase=promoted (the
            # fade-watch would grade a lever that is not in force) and do not
            # push PROMOTED. Stay running; the bar stays cleared, retry next
            # cycle. ABANDON at MAX_DAYS cannot fire meanwhile because that
            # branch is unreachable while ev['promote'] holds (this return).
            if not _asserted(rc, {**cand["levers"], **live_levers}):
                if not st.get("assert_fail_notified"):
                    send_push(f"PROMOTION WRITE FAILED: {cand['name']}",
                              "the paired bar cleared but the live lever write "
                              "did not land — staying RUNNING and retrying; "
                              "nothing reached real money",
                              priority="urgent")
                return save(assert_fail_notified=True, last_eval=ev,
                            note=f"promotion write did not land for "
                                 f"{cand['name']} — staying running")
            verdicts.append({"name": cand["name"], "verdict": "PROMOTED",
                             "ts": iso(now), "eval": ev})
            send_push(f"PROMOTED to LIVE: {cand['name']}",
                      f"{ev['why']}\nlive levers: {json.dumps(live_levers)} "
                      f"(TTL'd; fades back to env if the live arm turns)",
                      priority="urgent")
            # [2026-07-16] stamp the live arm's PRE-promotion baseline (the
            # paired window's live mean) — the relative fade bar releases the
            # lever when the post-promotion live mean falls margin_pp below
            # this. Absent/None -> fade_check falls back to the absolute bar.
            return save(phase="promoted", promoted_ts=now, last_eval=ev,
                        assert_fail_notified=False,
                        promote_baseline={"live_mean_pct": ev.get("live_mean_pct"),
                                          "n_live": ev.get("n_live")},
                        note=f"PROMOTED {cand['name']}")
        if days >= MAX_DAYS:
            verdicts.append({"name": cand["name"], "verdict": "ABANDONED",
                             "ts": iso(now), "eval": ev})
            send_push(f"experiment abandoned: {cand['name']}",
                      f"{MAX_DAYS:g}d without clearing the bar — {ev.get('why')}")
            return save(phase="idle", done=done + [cand["name"]],
                        done_at={**done_at, cand["name"]: now}, current=None,
                        spec={}, started_ts=None,
                        cooldown_until=now + COOLDOWN_H * 3600, last_eval=ev,
                        note=f"ABANDONED {cand['name']}")
        return save(last_eval=ev, note=f"day {days:.1f}/{MIN_DAYS:g}: {ev.get('why')}")

    if phase == "promoted":
        promoted = _num(st.get("promoted_ts"), now)
        # [2026-07-16 AUDIT FIX] ledger blackout used to be fail-OPEN here:
        # fade_check was skipped but the live levers kept re-asserting every
        # cycle, so a fading promotion could never release while the judge was
        # blind. Tolerate a short outage, then stop asserting (levers expire
        # to env defaults — the safe direction). Ledger back = counter resets.
        blind = int(_num(st.get("blind_cycles")))
        if not have_ledger:
            blind += 1
            if blind > BLIND_MAX:
                return save(blind_cycles=blind,
                            note=f"ledger dark {blind} cycles (> {BLIND_MAX}) — "
                                 f"NOT re-asserting live levers; env defaults "
                                 f"return within the TTL")
        else:
            blind = 0
        # [2026-07-16] the relative fade bar measures against the live arm's
        # own pre-promotion baseline, stamped at PROMOTE. Old promotions (or a
        # regen restore predating the stamp) have none -> absolute bar only.
        baseline = (st.get("promote_baseline") or {}).get("live_mean_pct")
        fading, n, m = (fade_check(rows, promoted, now, baseline_pct=baseline)
                        if have_ledger else (False, 0, None))
        live_levers = {XP_TO_LIVE[k]: v for k, v in cand["levers"].items()}
        # 🦾 the earlier fade signal: the live lane's own paired grades
        pfading, pwhy = prop_fade(store.load_state("fleet-proprioception") or {},
                                  set(live_levers), now)
        if fading or pfading:
            why = (f"live arm {m:+.2f}%/trade on the recent window (n={n} "
                   f"since promotion"
                   + (f"; pre-promotion baseline {baseline:+.2f}%"
                      if isinstance(baseline, (int, float)) else "") + ")"
                   if fading else pwhy)
            verdicts.append({"name": cand["name"], "verdict": "FADED",
                             "ts": iso(now), "live_n": n, "live_mean_pct": m,
                             "why": why})
            send_push(f"promotion FADED: {cand['name']}",
                      f"{why} — levers released, env defaults return within "
                      f"the TTL",
                      priority="urgent")
            return save(phase="idle", done=done + [cand["name"]],
                        done_at={**done_at, cand["name"]: now}, current=None,
                        spec={}, started_ts=None, promoted_ts=None,
                        promote_baseline=None,
                        cooldown_until=now + COOLDOWN_H * 3600,
                        note=f"FADED {cand['name']} ({why})")
        rc = _assert_levers({**cand["levers"], **live_levers},
                            f"promotion {cand['name']} in force",
                            f"promoted {iso(promoted)}; live n={n} mean "
                            f"{m if m is None else round(m, 3)}%/trade")
        # [2026-07-16] re-assert failure here is inherently fail-safe (the
        # lever TTL-expires and real money reverts to env defaults) but must
        # not be SILENT: the judge would keep reporting "promotion in force"
        # while nothing was. One warn per episode; fade-watch keeps running on
        # live data either way.
        if not _asserted(rc, live_levers):
            if not st.get("assert_fail_notified"):
                send_push(f"promotion re-assert FAILING: {cand['name']}",
                          "the live lever write is not landing — it will "
                          "TTL-expire back to env defaults (fail-safe); "
                          "fade-watch continues on live data",
                          priority="urgent")
            return save(blind_cycles=blind, assert_fail_notified=True,
                        note=f"promotion re-assert did not land — lever "
                             f"expires to env defaults within the TTL")
        return save(blind_cycles=blind, assert_fail_notified=False,
                    note=f"promotion in force (live n={n}, mean "
                         f"{m if m is None else round(m, 2)}%"
                         f"{', ledger dark ' + str(blind) + ' cycles' if blind else ''})")

    return save(phase="idle", current=None, spec={},
                note=f"unknown phase {phase!r} reset")


# ---------------------------------------------------------------------------

def _selftest():
    def row(bot, ts, pct):
        return {"bot": bot, "profit_ratio": pct, "close_ts": iso(ts)}

    t0 = 1_800_000_000.0
    day = 86400.0
    end = t0 + 8 * day
    # shadow beats live steadily on both halves: 32 shadow closes @ +1%,
    # 12 live closes @ +0.2%
    rows = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01) for i in range(32)]
            + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev = paired_eval(rows, t0, end)
    assert ev["promote"], ev
    assert abs(ev["gap_pp"] - 0.8) < 0.01, ev

    # one lucky half must NOT clear: shadow's edge only in h1
    rows2 = ([row(SHADOW_BOT, t0 + i * (4 * day / 16), 0.02) for i in range(16)]
             + [row(SHADOW_BOT, t0 + 4 * day + i * (4 * day / 16), -0.001)
                for i in range(16)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev2 = paired_eval(rows2, t0, end)
    assert not ev2["promote"] and "h2" in ev2["why"], ev2

    # margin gate: a 0.1pp edge is noise, not promotion
    rows3 = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), 0.003) for i in range(32)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev3 = paired_eval(rows3, t0, end)
    assert not ev3["promote"] and "margin" in ev3["why"], ev3

    # [2026-07-16 AUDIT] the margin must hold on EACH half: h1 +1.8pp but h2
    # only +0.01pp (full-window gap comfortably > 0.5pp) must NOT promote —
    # the old `shm > lvm` any-amount check let this lucky-half case through
    rows3b = ([row(SHADOW_BOT, t0 + i * (4 * day / 16), 0.02) for i in range(16)]
              + [row(SHADOW_BOT, t0 + 4 * day + i * (4 * day / 16), 0.0021)
                 for i in range(16)]
              + [row(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    ev3b = paired_eval(rows3b, t0, end)
    assert not ev3b["promote"] and "h2" in ev3b["why"], ev3b

    # floors: not enough closes -> not ready
    ev4 = paired_eval(rows[:10], t0, end)
    assert not ev4["promote"] and "floors" in ev4["why"], ev4

    # shadow must be positive in its own right (beating a very negative live
    # arm with a less-negative one is damage control, not edge)
    rows5 = ([row(SHADOW_BOT, t0 + i * (8 * day / 32), -0.001) for i in range(32)]
             + [row(LIVE_BOT, t0 + i * (8 * day / 12), -0.02) for i in range(12)])
    ev5 = paired_eval(rows5, t0, end)
    assert not ev5["promote"] and "own right" in ev5["why"], ev5

    # fade: live negative at n>=FADE_N since promotion -> release
    rows6 = [row(LIVE_BOT, t0 + i * 3600, -0.005) for i in range(20)]
    fading, n, m = fade_check(rows6, t0, t0 + 2 * day)
    assert fading and n == 20 and m < 0
    fading2, n2, _ = fade_check(rows6[:5], t0, t0 + 2 * day)
    assert not fading2 and n2 == 5, "below FADE_N: keep the promotion"

    # 🦾 prop_fade: the earlier fade signal — a fresh HURTING verdict on a
    # promoted lever releases; helping/unrelated/stale/absent do nothing
    fresh_p = {"updated": iso(t0), "ttl_sec": 2700, "verdicts": {
        "live.funding.enter_apr": {"verdict": "hurting", "n": 3, "bad": 2}}}
    okp, whyp = prop_fade(fresh_p, {"live.funding.enter_apr"}, t0 + 60)
    assert okp and "HURTING" in whyp, (okp, whyp)
    assert not prop_fade(fresh_p, {"live.funding.take_profit"}, t0 + 60)[0], \
        "unrelated lever must not fade"
    assert not prop_fade({"updated": iso(t0), "ttl_sec": 2700, "verdicts": {
        "live.funding.enter_apr": {"verdict": "helping"}}},
        {"live.funding.enter_apr"}, t0 + 60)[0]
    assert not prop_fade(fresh_p, {"live.funding.enter_apr"}, t0 + 99999)[0], \
        "stale organ must not fade"
    assert prop_fade({}, {"live.funding.enter_apr"}, t0) == (False, None)
    assert prop_fade(None, {"live.funding.enter_apr"}, t0) == (False, None)

    # every candidate's levers are registered, in-bounds, and map to a live twin
    for c in CANDIDATES:
        for k, v in c["levers"].items():
            assert tuning.clamp(k, v) == v, (k, v)
            lk = XP_TO_LIVE[k]
            assert tuning.clamp(lk, v) == v, (lk, v)

    # candidate_pool: static first, then admitted incubator proposals; an
    # offspring with an UNKNOWN lever is rejected (can't smuggle a lever past)
    q = {"candidates": [
        {"name": "enter-gate-0.0375", "levers": {"xp.funding.enter_apr": 0.0375}},  # dup static
        {"name": "xp-tp-0.05", "levers": {"xp.funding.take_profit": 0.05}},     # ok
        {"name": "evil", "levers": {"xp.funding.enter_apr": 0.3, "bad.lever": 1}},  # reject
    ]}
    pool = candidate_pool(q)
    names = [c["name"] for c in pool]
    assert names[:3] == ["enter-gate-0.0375", "tp-0.06", "hold-48"], names  # static order
    assert "xp-tp-0.05" in names and "evil" not in names, names
    assert names.count("enter-gate-0.0375") == 1, "dup name deduped"

    # [2026-07-17 AUDIT] NEGATIVE FIXTURE for the signature dedup — the shape
    # the incubator ACTUALLY emits: same experiment, name it can never share
    # with a static. The fixture above (dup NAME) passed throughout the bug's
    # life, so it proved nothing about the real failure. 48 vs 48.0 pins the
    # float normalisation; the last row proves a genuinely NEW experiment
    # still gets in (dedup must not become a wall).
    q2 = {"candidates": [
        {"name": "xp-enter_apr-0.0375", "levers": {"xp.funding.enter_apr": 0.0375}},
        {"name": "xp-take_profit-0.06", "levers": {"xp.funding.take_profit": 0.06}},
        {"name": "xp-max_hold_h-48", "levers": {"xp.funding.max_hold_h": 48}},  # int vs 48.0
        {"name": "xp-enter_apr-0.0625", "levers": {"xp.funding.enter_apr": 0.0625}},
    ]}
    n2 = [c["name"] for c in candidate_pool(q2)]
    assert n2 == ["enter-gate-0.0375", "tp-0.06", "hold-48",
                  "xp-enter_apr-0.0625"], n2
    # two offspring proposing the SAME novel experiment: first wins, no dup slot
    q3 = {"candidates": [
        {"name": "child-a", "levers": {"xp.funding.enter_apr": 0.0625}},
        {"name": "child-b", "levers": {"xp.funding.enter_apr": 0.0625}},
    ]}
    assert [c["name"] for c in candidate_pool(q3)][-1] == "child-a"
    assert len(candidate_pool(q3)) == len(CANDIDATES) + 1
    assert _lever_sig({"a": 1}) == _lever_sig({"a": 1.0})
    assert _lever_sig({"a": "x"}) == (("a", "x"),)      # non-numeric survives
    # next_candidate: skips done + current, name-based (pool may grow)
    assert next_candidate(pool, [], None)["name"] == "enter-gate-0.0375"
    assert next_candidate(pool, ["enter-gate-0.0375"], "tp-0.06")["name"] == "hold-48"
    assert next_candidate(pool, [c["name"] for c in pool], None) is None  # exhausted

    # migration guard: OLD index-based state (running phase, no current/spec)
    # must trigger a reset instead of KeyError on cand['levers']
    assert _needs_reset("running", None, {}) is True          # the 16-Jul crash
    assert _needs_reset("promoted", None, {}) is True
    assert _needs_reset("running", "x", {"name": "y", "levers": {}}) is True  # mismatch
    assert _needs_reset("running", "x", {"name": "x"}) is True  # spec lacks 'levers'
    _ok_lever = next(iter(XP_TO_LIVE))
    assert _needs_reset("running", "x", {"name": "x", "levers": {_ok_lever: 1}}) is False
    assert _needs_reset("idle", None, {}) is False             # idle never resets here
    # [2026-07-16 AUDIT] shapes that passed the old guard but crashed downstream
    assert _needs_reset("running", "x", {"name": "x", "levers": None}) is True
    assert _needs_reset("running", "x", {"name": "x", "levers": {}}) is True
    assert _needs_reset("promoted", "x", {"name": "x", "levers": {"gone.lever": 1}}) is True
    # corrupt numeric state fields must degrade, not crash-loop
    assert _num("not-a-ts") == 0.0 and _num(None, 5.0) == 5.0 and _num("7") == 7.0

    # ---- [2026-07-16] ARM-SKEW gate: enactment is not application ---------
    # Regression guard for the live defect: the judge asserted xp.* levers at a
    # frozen shadow arm with no lever code (30 closes, 0 receipts), so the bar
    # scored version skew and would have promoted an untested value to REAL
    # MONEY. A receipt is stamped only inside the arm's apply_levers(), so a
    # missing one is disproof. This gate must stay fail-CLOSED.
    def rowb(bot, ts, pct, bars=None):
        r = {"bot": bot, "profit_ratio": pct, "close_ts": iso(ts), "extra": {}}
        if bars is not None:
            r["extra"] = {"bars": bars}
        return r

    _cand = {"xp.funding.enter_apr": 0.3}
    _applied = {"arm": "lighter_shadow", "enter_apr": 0.3}
    _default = {"arm": "lighter_shadow", "enter_apr": 0.4}   # what a deaf arm runs

    assert ran_candidate(rowb(SHADOW_BOT, t0, 0.01, _applied), _cand) is True
    assert ran_candidate(rowb(SHADOW_BOT, t0, 0.01), _cand) is False      # no receipt
    assert ran_candidate(rowb(SHADOW_BOT, t0, 0.01, _default), _cand) is False
    assert ran_candidate({"bot": SHADOW_BOT}, _cand) is False             # no extra

    # shadow crushes live, but proves nothing: must NOT promote
    _sk = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.05) for i in range(32)]
           + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    assert paired_eval(_sk, t0, end)["promote"] is True          # old bar: promotes
    _skv = paired_eval(_sk, t0, end, cand_levers=_cand)          # gated: blocked
    assert _skv["promote"] is False and _skv["arm_skew"] is True, _skv
    assert _skv["n_shadow_closes"] == 32, _skv

    # the gate is not a brick wall — an APPLYING arm still clears
    _ap = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01, _applied) for i in range(32)]
           + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    _apv = paired_eval(_ap, t0, end, cand_levers=_cand)
    assert _apv["promote"] is True and not _apv.get("arm_skew"), _apv

    # rows carrying the WRONG bars are excluded from n and the mean
    _mx = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01, _applied) for i in range(32)]
           + [rowb(SHADOW_BOT, t0 + i * (8 * day / 8), -0.99, _default) for i in range(8)]
           + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    _mxv = paired_eval(_mx, t0, end, cand_levers=_cand)
    assert _mxv["n_shadow"] == 32 and _mxv["shadow_mean_pct"] > 0, _mxv

    # cand_levers=None must be byte-identical to the historical bar
    assert paired_eval(_sk, t0, end) == paired_eval(_sk, t0, end, cand_levers=None)

    # ---- [2026-07-16] per-half sample floors -------------------------------
    # Full-window floors said nothing about the halves: 25 shadow closes in h1
    # and 5 in h2 clears 30 overall, but h2's "both-halves" verdict rides on 5
    # trades. Must hold as under-powered, not promote.
    _lop = ([rowb(SHADOW_BOT, t0 + i * (4 * day / 25), 0.01, _applied) for i in range(25)]
            + [rowb(SHADOW_BOT, t0 + 4 * day + i * (4 * day / 5), 0.01, _applied)
               for i in range(5)]
            + [rowb(LIVE_BOT, t0 + i * (8 * day / 12), 0.002) for i in range(12)])
    _lv2 = paired_eval(_lop, t0, end, cand_levers=_cand)
    assert _lv2["promote"] is False and "under-powered" in _lv2["why"], _lv2
    # one live trade per half must never carry a promotion: 10 live closes all
    # in h1, h2 has 1 — the exact noise-amplifier shape
    _one = ([rowb(SHADOW_BOT, t0 + i * (8 * day / 32), 0.01, _applied) for i in range(32)]
            + [rowb(LIVE_BOT, t0 + i * (4 * day / 10), 0.002) for i in range(10)]
            + [rowb(LIVE_BOT, t0 + 5 * day, 0.002)])
    _ov = paired_eval(_one, t0, end, cand_levers=_cand)
    assert _ov["promote"] is False and "under-powered" in _ov["why"], _ov
    # the original promote case still clears (16/16 + 6/6 split >= 15/5 floors)
    assert paired_eval(rows, t0, end)["promote"], "per-half floors broke the base case"

    # ---- [2026-07-16] relative + rolling fade bar --------------------------
    # edge destroyed but not inverted: baseline +0.8, post-promotion +0.1 —
    # the old absolute bar (m<0) never released this. n=20 @ FADE_N=15.
    _fade_rows = [rowb(LIVE_BOT, t0 + i * 3600, 0.001) for i in range(20)]
    f, n, m = fade_check(_fade_rows, t0 - 1, end, fade_n=15, baseline_pct=0.8,
                         margin_pp=0.5)
    assert f is True and n == 20, (f, n, m)
    # same data, no baseline (old promotion) -> absolute bar only -> no release
    f2, _, _ = fade_check(_fade_rows, t0 - 1, end, fade_n=15)
    assert f2 is False, "missing baseline must fall back to the absolute bar"
    # healthy: post-promotion holds near baseline -> no release
    _ok_rows = [rowb(LIVE_BOT, t0 + i * 3600, 0.007) for i in range(20)]
    f3, _, _ = fade_check(_ok_rows, t0 - 1, end, fade_n=15, baseline_pct=0.8,
                          margin_pp=0.5)
    assert f3 is False, "a healthy promotion must not release"
    # ROLLING beats cumulative: 30 early wins then 15 recent losses — the
    # cumulative mean stays positive (the old unreachable-release bug), the
    # rolling window sees the fade
    _late = ([rowb(LIVE_BOT, t0 + i * 3600, 0.02) for i in range(30)]
             + [rowb(LIVE_BOT, t0 + (40 + i) * 3600, -0.005) for i in range(15)])
    f4, _, m4 = fade_check(_late, t0 - 1, end, fade_n=15)
    assert f4 is True and m4 < 0, (f4, m4)
    assert 100.0 * (30 * 0.02 - 15 * 0.005) / 45 > 0  # cumulative would miss it
    # under FADE_N closes -> no signal (fail-safe unchanged)
    assert fade_check(_fade_rows[:5], t0 - 1, end, fade_n=15,
                      baseline_pct=9.9)[0] is False

    # ---- [2026-07-16] _asserted: a dropped rail write is not an assert -----
    assert _asserted({"levers": {"a": {}, "b": {}}}, {"a": 1, "b": 2}) is True
    assert _asserted(None, {"a": 1}) is False                # write_levers None
    assert _asserted({"levers": {"a": {}}}, {"a": 1, "b": 2}) is False  # partial
    assert _asserted({}, {"a": 1}) is False
    assert _asserted({"levers": {"a": {}}}, {}) is False     # nothing wanted

    # [2026-07-17 IMB-07] fallback-only retry: untried candidates ALWAYS
    # beat an aged-out done entry; a retry happens only when nothing
    # untried remains (plain aging was verify-refuted — pool-order statics
    # rotate slower than the retry window and would starve offspring)
    _pool = [{"name": "s1", "levers": {}}, {"name": "s2", "levers": {}},
             {"name": "off1", "levers": {}}]
    c, r = pick_candidate(_pool, ["s1"], {"s1": t0 - 40 * day}, None, t0,
                          28 * day)
    assert c["name"] == "s2" and not r, "untried static beats aged retry"
    c, r = pick_candidate(_pool, ["s1", "s2"], {"s1": t0 - 40 * day,
                                                "s2": t0 - day}, None, t0,
                          28 * day)
    assert c["name"] == "off1" and not r, \
        "NEVER-tried offspring beats an aged static (the starving case)"
    c, r = pick_candidate(_pool, ["s1", "s2", "off1"],
                          {"s1": t0 - 40 * day, "s2": t0 - day,
                           "off1": t0 - day}, None, t0, 28 * day)
    assert c["name"] == "s1" and r, "nothing untried -> retry the aged one"
    c, r = pick_candidate(_pool, ["s1", "s2", "off1"],
                          {k: t0 - day for k in ("s1", "s2", "off1")},
                          None, t0, 28 * day)
    assert c is None and not r, "nothing untried, nothing aged -> exhausted"

    print("experiment_judge selftest OK (promote, lucky-half reject, margin, "
          "floors, own-right, fade, proprioception early-fade, registry mapping, "
          "arm-skew receipt gate, per-half floors, relative+rolling fade, "
          "asserted-write guard)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
