#!/usr/bin/env python3
"""
fleet_proprioception.py — 🦾 PROPRIOCEPTION: the autonomy stack's sense of
its OWN movements (shipped 2026-07-16, "advance the autonomous organ").

THE GAP THIS CLOSES
Every autonomous actuator in the fleet is gated PROSPECTIVELY: the scout
tuner replays the tape that motivated a widening, the board widens on census
quiet-hours, the judge runs a paired bar. But once a lever is ENACTED,
nothing ever looks back — no organ measures whether the fleet actually did
better during the hours a lever was in force than it would have on the
operator's defaults. The growth rail could act; it could not FEEL the
consequence of its own action. (The 15-Jul cap-breach postmortem made the
cost concrete: an enactment's downstream effect was only discovered by a
human audit.) Proprioception is the body sense that closes that loop:
act → sense the movement's outcome → adjust the next movement.

WHAT IT DOES (hourly-ish, run-once, looped by run_all.sh)
  1. EPISODES. Watches bot_state 'fleet-tuning' and tracks lever STANCES per
     lane-group (all taker.* bars form one joint stance — they replay
     together so they are graded together; each scout.* diet lever is its
     own; gapscout.* one; live.*/xp.* record-only). A stance change, expiry
     or release CLOSES the episode; long-running stances are SLICED daily so
     grades accrue while a lever is still held.
  2. GRADES (out-of-sample by construction — the deciding organ tuned on
     tape BEFORE the episode; the grade uses the tape recorded DURING it):
       taker    — the true counterfactual: replay the during-episode tape
                  through the taker's REAL code with env DEFAULTS vs the
                  episode's bars -> delta_usd (the $ the enactment made or
                  cost the shadow book vs doing nothing).
       scout    — learning throughput: the lens's brain-graded n4h count at
                  close minus at open (the diet levers exist to buy grades).
       gapscout — did the widened detection net actually find anything
                  (census quiet_hours reset inside the window)?
       live     — THE LIVE LANE LEARNS (16-Jul evening, operator: "the live
                  lane needs to learn"): per-trade pnl_pct during the
                  episode vs TWO baselines — the books' own pre-episode
                  window AND the shadow twins over the same window. 'bad'
                  only when worse than EVERY available baseline by the
                  margin (real money is never blamed on one noisy
                  comparison); higher floors than the shadow lanes.
                  clip_scale and funding bars grade as separate groups so
                  the board's movement is never blamed on the judge's.
       xp       — RECORDED ONLY: the judge's paired arms already grade it.
  3. VERDICTS. Per-lever, floors-gated (n episodes + $ margin): helping /
     hurting / neutral / insufficient. HURTING exists only on the taker
     lane — the one lane with a real $ counterfactual. Joint stances share
     blame across their levers (conservative in the restrict direction).
  4. CONSUMPTION — both directions since 16-Jul evening (operator:
     "implement the expanding side ... so the July 21 [review] can review
     both sides"):
       RESTRICT: lighter_scout_tuner drops any would-be enactment whose
         lever carries a fresh HURTING verdict — the tuner stops repeating
         a movement that measured net-negative in reality, even when
         in-sample replay still likes it.
       EXPAND (every consumer stays inside its own gates — registry
         clamps, TTL, per-notch replay margins, brain veto senior):
         a HELPING taker lever unlocks the tuner's improve-both-halves
         expansion walk BEFORE the brain's ruling floor (the episode
         counterfactual is an independent evidence bar); a HELPING scout
         diet lever walks one notch DEEPER while its lens is under the
         floor; a HELPING gapscout lever discounts the board's
         widen-ladder quiet-hour bars (x0.75, 12h floor) so a net that
         has measurably found things re-widens sooner.
       LIVE (restrict-first — the lane's learning loop): a HURTING
         live.clip_scale verdict BLOCKS the board's up-ladder and releases
         the lever back to operator sizing; a HURTING live.funding.*
         verdict is an EARLIER fade signal for the judge (the judge stays
         the only writer). The single live earn: the clip ladder's TOP
         step (1.5) now requires a measured HELPING grade at 1.25 —
         fail-CLOSED, a dark sense keeps the top out of reach. New live
         levers and promotions still have exactly one road: the judge.
     The evidence board surfaces helping (expand evidence) and hurting
     (warn) items. Fail-safe BOTH WAYS: a dark/stale proprioception
     restricts nothing and earns nothing (levers stay bounded + TTL'd
     regardless; a dead sense must not paralyze — or embolden — the body).

WHAT IT NEVER DOES
  Open positions, write or widen any lever, touch real money, or override
  the judge/immune organs. It publishes grades; its only actuation is that
  an AUTHOR may decline to re-assert — a pure restriction. Backtests inert
  (no DATABASE_URL -> store no-ops -> nothing tracked).

Publishes bot_state 'fleet-proprioception' (+ lean history):
  {updated, ttl_sec, open:{group:...}, episodes:[...], verdicts:{lever:...},
   counts:{...}}
Consumers: lighter_scout_tuner (hurting-skip), evidence_board, dashboard,
the 21-Jul review. --selftest is offline.
"""
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
import fleet_tuning as tuning
import lighter_ticket_taker as tt
import lighter_ticket_replay as rp

KEY = "fleet-proprioception"
INTERVAL = int(os.environ.get("PROPRIO_INTERVAL_SEC", "900"))
TTL_SEC = 3 * INTERVAL
EP_CAP = int(os.environ.get("PROP_EP_CAP", "120"))           # episode ledger
MIN_EP_H = float(os.environ.get("PROP_MIN_EP_H", "0.75"))    # gradeable floor
MIN_EP_SNAPS = int(os.environ.get("PROP_MIN_EP_SNAPS", "8"))  # taker replay
SLICE_H = float(os.environ.get("PROP_SLICE_H", "24"))        # long-stance cut
VERDICT_WINDOW = int(os.environ.get("PROP_VERDICT_WINDOW", "10"))
MIN_EPISODES = int(os.environ.get("PROP_MIN_EPISODES", "2"))
HURT_USD = float(os.environ.get("PROP_HURT_USD", "3.0"))
HELP_USD = float(os.environ.get("PROP_HELP_USD", "3.0"))
GRADES_MIN = int(os.environ.get("PROP_GRADES_MIN", "10"))
# live-lane grading floors (16-Jul evening, operator: "the live lane needs
# to learn") — real money gets HIGHER evidence bars than the shadow lanes
LIVE_EP_MIN_N = int(os.environ.get("PROP_LIVE_EP_MIN_N", "5"))
LIVE_BASE_MIN_N = int(os.environ.get("PROP_LIVE_BASE_MIN_N", "3"))
LIVE_MARGIN_PP = float(os.environ.get("PROP_LIVE_MARGIN_PP", "0.25"))
LIVE_ROWS = {s.strip() for s in os.environ.get(
    "EVBOARD_LIVE_ROWS",
    "crypto-trend-daily-lighter,perps-funding-lighter-lighter").split(",")
    if s.strip()}

# taker lever -> the tt module attr the replay patches (same map the tuner uses)
TAKER_ATTR = {"taker.dip_range": "DIP_RANGE", "taker.brk_range": "BRK_RANGE",
              "taker.momo_chg": "MOMO_CHG", "taker.div_gap_pp": "DIV_GAP_PP",
              "taker.tp": "TAKE_PROFIT", "taker.sl": "STOP_LOSS",
              "taker.max_hold_h": "MAX_HOLD_H"}
# scout diet lever -> the lens whose grading throughput it buys
SCOUT_LENS = {"scout.dip_range_max": "dip", "scout.brk_range_min": "breakout",
              "scout.momo_chg_min": "momentum", "scout.ticket_top_n": None}
# env defaults captured at import — the counterfactual's "do nothing" arm
DEFAULTS = {attr: getattr(tt, attr) for attr in TAKER_ATTR.values()}


def _now():
    return time.time()


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _parse_ts(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def _fresh(state, now, fallback_ttl=None):
    try:
        u = _parse_ts(state.get("updated"))
        ttl = float(state.get("ttl_sec") or fallback_ttl or 0)
        return u is not None and 0 <= now - u <= ttl
    except Exception:
        return False


# ---------------------------------------------------------------------------
# pure: stance grouping + episode tracking (selftested offline)
# ---------------------------------------------------------------------------

def group_of(name):
    """The attribution unit a lever belongs to. All taker bars replay as one
    joint bar set, so they form ONE stance; each scout diet lever stands
    alone. The live lane splits by ACTUATOR so attribution is clean:
    clip_scale reshapes BOTH live books' clips (board-authored) while the
    funding bars steer only the Funding Farmer (judge-authored) — lumping
    them would blame one author's movement on the other. xp is record-only
    (the judge's own paired arms already grade it)."""
    if name.startswith("taker."):
        return "taker"
    if name.startswith("scout."):
        return f"scout:{name}"
    if name.startswith("gapscout."):
        return "gapscout"
    if name == "live.clip_scale":
        return "live-clip"
    if name.startswith("live.funding."):
        return "live-funding"
    if name.startswith("live."):
        return "live"
    if name.startswith("xp."):
        return "xp"
    return f"other:{name.split('.')[0]}"


def build_stances(active):
    """{group: {stance:{lever:value}, set_by:[...], expires_max:ts|None}}
    from fleet_tuning.active_levers()' {name: entry}."""
    out = {}
    for name, entry in (active or {}).items():
        if not isinstance(entry, dict):
            continue
        g = out.setdefault(group_of(name),
                           {"stance": {}, "set_by": set(), "expires_max": None})
        g["stance"][name] = entry.get("value")
        if entry.get("set_by"):
            g["set_by"].add(str(entry["set_by"]))
        e = _parse_ts(entry.get("expires"))
        if e is not None:
            g["expires_max"] = max(g["expires_max"] or 0, e)
    for g in out.values():
        g["set_by"] = sorted(g["set_by"])
    return out


def track(open_eps, stances_now, now, slice_h=SLICE_H):
    """One tracking step. Returns (open_next, closed) where closed carries
    {group, stance, set_by, start, end, reason, start_metrics}. Reasons:
    'changed' (stance moved), 'released' (gone — end backdated to the last
    seen expiry so a dead author doesn't inflate the window), 'slice'
    (long-running stance cut so grades accrue). start_metrics for newly
    opened groups is left None — the caller stamps it (feed reads are
    impure)."""
    open_next, closed = {}, []
    for group, cur in (open_eps or {}).items():
        now_g = stances_now.get(group)
        if now_g is None or now_g["stance"] != cur.get("stance"):
            exp = cur.get("last_expires")
            end = now if now_g is not None else min(
                now, exp if isinstance(exp, (int, float)) and exp else now)
            closed.append(dict(cur, group=group, end=max(end, cur["start"]),
                               reason="changed" if now_g is not None else "released"))
        elif now - cur["start"] >= slice_h * 3600:
            closed.append(dict(cur, group=group, end=now, reason="slice"))
            open_next[group] = {"stance": dict(now_g["stance"]),
                                "set_by": now_g["set_by"], "start": now,
                                "last_expires": now_g["expires_max"],
                                "start_metrics": None}
        else:
            open_next[group] = dict(cur, last_expires=now_g["expires_max"],
                                    set_by=now_g["set_by"])
    for group, g in stances_now.items():
        if group not in open_next:
            open_next[group] = {"stance": dict(g["stance"]), "set_by": g["set_by"],
                                "start": now, "last_expires": g["expires_max"],
                                "start_metrics": None}
    return open_next, closed


# ---------------------------------------------------------------------------
# pure: grading (feeds injected — selftested offline)
# ---------------------------------------------------------------------------

def _replay_with(tape, bars):
    saved = {k: getattr(tt, k) for k in bars}
    try:
        for k, v in bars.items():
            setattr(tt, k, v)
        return rp.replay(tape)
    finally:
        for k, v in saved.items():
            setattr(tt, k, v)


def grade_taker(ep, tape):
    """The counterfactual: during-episode tape, env defaults vs the stance's
    bars. delta_usd > 0 = the enactment beat doing nothing."""
    start, end = ep["start"], ep["end"]
    window = [(dt, p) for dt, p in (tape or [])
              if start <= dt.timestamp() <= end]
    if (end - start) < MIN_EP_H * 3600 or len(window) < MIN_EP_SNAPS:
        return {"status": "too-short", "n_snaps": len(window)}
    bars = {TAKER_ATTR[k]: v for k, v in ep["stance"].items()
            if k in TAKER_ATTR}
    if not bars:
        return {"status": "ungraded"}
    base = _replay_with(window, DEFAULTS)["closed_net"]
    var = _replay_with(window, dict(DEFAULTS, **bars))["closed_net"]
    return {"status": "graded", "n_snaps": len(window),
            "default_net": base, "stance_net": var,
            "delta_usd": round(var - base, 2)}


def grade_scout(ep, lens_fwd_end):
    """Learning throughput: brain-graded n4h at close minus at open for the
    lens this diet lever feeds (ticket_top_n counts every lens)."""
    lever = next(iter(ep["stance"]), None)
    lens = SCOUT_LENS.get(lever, None)

    def count(lf):
        lenses = (lf or {}).get("lenses") or {}
        if lens is None:
            return sum(int((o or {}).get("n4h") or 0) for o in lenses.values()) \
                if lenses else None
        o = lenses.get(lens)
        return int(o.get("n4h") or 0) if isinstance(o, dict) else None

    a = count((ep.get("start_metrics") or {}).get("lens_fwd"))
    b = count(lens_fwd_end)
    if a is None or b is None or (ep["end"] - ep["start"]) < MIN_EP_H * 3600:
        return {"status": "ungraded"}
    return {"status": "graded", "n4h_start": a, "n4h_end": b,
            "delta_grades": b - a}


def grade_gapscout(ep, census_end):
    """Did the widened net find anything: census quiet_hours resetting inside
    the episode window means an episode closed while the net was wide."""
    q = (census_end or {}).get("quiet_hours")
    hours = (ep["end"] - ep["start"]) / 3600.0
    if q is None or hours < MIN_EP_H:
        return {"status": "ungraded"}
    return {"status": "graded",
            "quiet_start": (ep.get("start_metrics") or {}).get("quiet_hours"),
            "quiet_end": q, "found_activity": bool(float(q) < hours)}


def _twin(bot):
    """A live row's shadow twin: same signals, mark fills, $1k paper book —
    the natural control arm for a live-lane episode."""
    return bot[:-len("-lighter")] + "-lshadow" if bot.endswith("-lighter") else None


def grade_live(ep, trades, group="live-clip"):
    """The live lane LEARNS (16-Jul evening, operator mandate): an episode
    under live levers is graded per-trade against TWO baselines — the same
    books' own pre-episode window AND the shadow twins over the SAME window
    (identical signals; the only difference is the lever + real fills).
    'bad' requires being worse than EVERY available baseline by the margin
    (conservative — real money is never blamed on one noisy comparison);
    'good' is symmetric; anything mixed is 'flat'. The metric is per-trade
    pnl_pct — size-invariant by design (the judge's own lesson: equity
    comparisons across different-sized books lie). Thin data -> 'recorded'
    (no signal, no verdict). What consumes the verdicts stays restrict-
    first: the board blocks clip UP-steps and releases on hurting, the
    judge fades a promotion early; HELPING earns exactly one thing — the
    clip ladder's TOP step, fail-closed."""
    start, end = ep["start"], ep["end"]
    bots = ({b for b in LIVE_ROWS if "funding" in b} if group == "live-funding"
            else set(LIVE_ROWS))
    twins = {t for t in (_twin(b) for b in bots) if t}

    def stats(names, a, b):
        pcts = [float(r["profit_ratio"]) for r in trades or []
                if str(r.get("bot")) in names
                and r.get("profit_ratio") is not None
                and a <= (_parse_ts(r.get("close_ts")) or -1) < b]
        return (len(pcts),
                round(100.0 * sum(pcts) / len(pcts), 3) if pcts else None)

    n_in, m_in = stats(bots, start, end)
    n_pre, m_pre = stats(bots, start - (end - start), start)
    n_tw, m_tw = stats(twins, start, end)
    rec = {"n_during": n_in, "mean_pct_during": m_in,
           "n_before": n_pre, "mean_pct_before": m_pre,
           "n_twin": n_tw, "mean_pct_twin": m_tw}
    baselines = [m for n, m in ((n_pre, m_pre), (n_tw, m_tw))
                 if n >= LIVE_BASE_MIN_N and m is not None]
    if (n_in < LIVE_EP_MIN_N or m_in is None or not baselines
            or (end - start) < MIN_EP_H * 3600):
        return {"status": "recorded", **rec}
    if all(m_in < b - LIVE_MARGIN_PP for b in baselines):
        sig = "bad"
    elif all(m_in > b + LIVE_MARGIN_PP for b in baselines):
        sig = "good"
    else:
        sig = "flat"
    return {"status": "graded", "signal": sig, **rec}


def grade_episode(ep, feeds):
    g = ep["group"]
    if g == "taker":
        return grade_taker(ep, feeds.get("tape"))
    if g.startswith("scout:"):
        return grade_scout(ep, feeds.get("lens_fwd"))
    if g == "gapscout":
        return grade_gapscout(ep, feeds.get("census"))
    if g in ("live-clip", "live-funding", "live"):
        return grade_live(ep, feeds.get("trades"), group=g)
    if g == "xp":
        return {"status": "recorded"}   # the judge's paired arms grade xp
    return {"status": "recorded"}


# ---------------------------------------------------------------------------
# pure: per-lever verdicts (selftested offline)
# ---------------------------------------------------------------------------

def lever_verdicts(episodes):
    """{lever: {verdict, n, ...}} over the newest VERDICT_WINDOW graded
    episodes per lever. HURTING exists on the two lanes with a real paired
    measure: taker (the $ replay counterfactual) and live (per-trade vs
    pre-window + shadow twin — 16-Jul evening, 'the live lane needs to
    learn'). Joint stances share blame — conservative in the restrict
    direction. Diet/detection levers can only help or sit neutral; xp never
    verdicts here (the judge's paired arms own it)."""
    per = {}
    for ep in episodes or []:
        if ep.get("status") != "graded":
            continue
        for lever in (ep.get("levers") or []):
            per.setdefault(lever, []).append(ep)
    out = {}
    for lever, eps in per.items():
        eps = eps[-VERDICT_WINDOW:]
        n = len(eps)
        if lever in TAKER_ATTR:
            deltas = [float(e.get("delta_usd") or 0) for e in eps]
            total = round(sum(deltas), 2)
            neg = sum(1 for d in deltas if d < 0)
            pos = sum(1 for d in deltas if d > 0)
            joint = any(len(e.get("levers") or []) > 1 for e in eps)
            v = "neutral"
            if n >= MIN_EPISODES and total <= -HURT_USD and neg > pos:
                v = "hurting"
            elif n >= MIN_EPISODES and total >= HELP_USD and pos > neg:
                v = "helping"
            elif n < 1:
                v = "insufficient"
            out[lever] = {"verdict": v, "n": n, "sum_delta_usd": total,
                          "joint": joint, "basis": "replay-counterfactual"}
        elif lever in SCOUT_LENS:
            total = sum(int(e.get("delta_grades") or 0) for e in eps)
            v = "helping" if total >= GRADES_MIN else "neutral"
            out[lever] = {"verdict": v, "n": n, "sum_delta_grades": total,
                          "basis": "grading-throughput"}
        elif lever.startswith("gapscout."):
            found = any(e.get("found_activity") for e in eps)
            out[lever] = {"verdict": "helping" if found else "neutral", "n": n,
                          "basis": "census-activity"}
        elif lever.startswith("live."):
            goods = sum(1 for e in eps if e.get("signal") == "good")
            bads = sum(1 for e in eps if e.get("signal") == "bad")
            v = "neutral"
            if bads >= MIN_EPISODES and bads > goods:
                v = "hurting"
            elif goods >= MIN_EPISODES and goods > bads:
                v = "helping"
            out[lever] = {"verdict": v, "n": n, "good": goods, "bad": bads,
                          "basis": "live-paired"}
    return out


def _verdict_levers(state, now, verdict, fallback_ttl):
    try:
        if not state or not _fresh(state, now, fallback_ttl):
            return {}
        return {k: v for k, v in (state.get("verdicts") or {}).items()
                if isinstance(v, dict) and v.get("verdict") == verdict}
    except Exception:
        return {}


def hurting_levers(state, now, fallback_ttl=TTL_SEC):
    """The restrict-side consumer hook: fresh HURTING lever names. Fail-safe
    empty — a dark/stale/absent proprioception restricts nothing."""
    return _verdict_levers(state, now, "hurting", fallback_ttl)


def helping_levers(state, now, fallback_ttl=TTL_SEC):
    """[2026-07-16 later, operator: 'implement the expanding side'] The
    expand-side consumer hook: fresh HELPING lever names. Fail-safe empty —
    a dark organ EARNS nothing either (symmetry with hurting: no verdict, no
    effect in either direction). Every consumer of this stays bounded by its
    own gates: the tuner's per-notch replay improvement rule, the board's
    ladder values, fleet_tuning's registry clamps + TTL."""
    return _verdict_levers(state, now, "helping", fallback_ttl)


# ---------------------------------------------------------------------------

def run_once():
    now = _now()
    prior = store.load_state(KEY) or {}
    episodes = list(prior.get("episodes") or [])
    open_eps = {}
    for g, cur in (prior.get("open") or {}).items():
        if isinstance(cur, dict) and isinstance(cur.get("stance"), dict) \
                and isinstance(cur.get("start"), (int, float)):
            open_eps[g] = cur

    active = tuning.active_levers(now_ts=now)
    stances_now = build_stances(active)
    open_next, closed = track(open_eps, stances_now, now)

    # feeds — read once, only what the cycle needs (fail-safe: absent feed
    # -> the episode grades 'ungraded'/'recorded', never a crash)
    batch = store.fetch_states(["brain-lens-forward", "gapscout-census"]) \
        if hasattr(store, "fetch_states") else {}
    lf = batch.get("brain-lens-forward") or store.load_state("brain-lens-forward") or {}
    census = batch.get("gapscout-census") or store.load_state("gapscout-census") or {}
    lf_ok = _fresh(lf, now, 26000)
    census_ok = _fresh(census, now, 3600)
    feeds = {"lens_fwd": lf if lf_ok else None,
             "census": census if census_ok else None,
             "tape": None, "trades": None}
    if any(c["group"] == "taker" for c in closed):
        try:
            feeds["tape"], _src = rp.load_tape(source="auto")
        except Exception as e:  # noqa: BLE001
            print(f"[proprioception] tape load failed: {type(e).__name__}: {e}",
                  flush=True)
    if any(c["group"] in ("live-clip", "live-funding", "live", "xp")
           for c in closed):
        try:
            feeds["trades"] = store.fetch_paper_trades(limit=4000)
        except Exception:
            feeds["trades"] = None

    for c in closed:
        grade = grade_episode(c, feeds)
        rec = {"group": c["group"], "levers": sorted(c["stance"]),
               "stance": c["stance"], "set_by": c.get("set_by") or [],
               "start": c["start"], "end": c["end"],
               "start_iso": _iso(c["start"]), "end_iso": _iso(c["end"]),
               "hours": round((c["end"] - c["start"]) / 3600.0, 2),
               "reason": c["reason"], **grade}
        episodes.append(rec)
        print(f"[proprioception] episode CLOSED {rec['group']} "
              f"({rec['reason']}, {rec['hours']}h) {rec['stance']} -> "
              f"{grade}", flush=True)
    episodes = episodes[-EP_CAP:]

    # stamp start metrics on newly opened groups (feed reads done above)
    for g, cur in open_next.items():
        if cur.get("start_metrics") is None:
            sm = {}
            if g.startswith("scout:") and lf_ok:
                sm["lens_fwd"] = {"lenses": {
                    l: {"n4h": (o or {}).get("n4h")}
                    for l, o in ((lf.get("lenses") or {}).items())}}
            if g == "gapscout" and census_ok:
                sm["quiet_hours"] = census.get("quiet_hours")
            cur["start_metrics"] = sm

    verdicts = lever_verdicts(episodes)
    prior_hurt = set(hurting_levers(prior, _parse_ts(prior.get("updated")) or 0,
                                    fallback_ttl=10**12))
    now_hurt = {k for k, v in verdicts.items() if v.get("verdict") == "hurting"}
    counts = {"open": len(open_next),
              "episodes": len(episodes),
              "graded": sum(1 for e in episodes if e.get("status") == "graded"),
              "helping": sum(1 for v in verdicts.values()
                             if v.get("verdict") == "helping"),
              "hurting": len(now_hurt)}
    payload = {"updated": _iso(now), "ttl_sec": TTL_SEC,
               "open": open_next, "episodes": episodes,
               "verdicts": verdicts, "counts": counts}
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {
                "updated": payload["updated"], "counts": counts,
                "closed": [{"group": c["group"], "reason": c["reason"]}
                           for c in closed],
                "verdicts": {k: v.get("verdict") for k, v in verdicts.items()}})
        except Exception:
            pass
    for k in sorted(now_hurt - prior_hurt):
        print(f"[proprioception] VERDICT HURTING {k}: {verdicts[k]}", flush=True)
    for k in sorted(prior_hurt - now_hurt):
        print(f"[proprioception] hurting CLEARED {k}", flush=True)
    print(f"[proprioception] {_iso(now)} open={counts['open']} "
          f"episodes={counts['episodes']} graded={counts['graded']} "
          f"helping={counts['helping']} hurting={counts['hurting']}", flush=True)
    return payload


# ---------------------------------------------------------------------------

def _selftest():
    now = 1_800_000_000.0

    # grouping: taker bars are ONE joint stance; each scout lever its own;
    # the live lane splits by ACTUATOR (board's clip vs judge's bars)
    assert group_of("taker.tp") == "taker" == group_of("taker.dip_range")
    assert group_of("scout.dip_range_max") == "scout:scout.dip_range_max"
    assert group_of("gapscout.prefilter_gap") == "gapscout"
    assert group_of("live.clip_scale") == "live-clip"
    assert group_of("live.funding.enter_apr") == "live-funding"
    assert group_of("xp.funding.enter_apr") == "xp"
    assert _twin("crypto-trend-daily-lighter") == "crypto-trend-daily-lshadow"
    assert _twin("perps-funding-lighter-lighter") == "perps-funding-lighter-lshadow"

    exp = _iso(now + 7800)
    active = {
        "taker.dip_range": {"value": 0.08, "set_by": "scout-tuner", "expires": exp},
        "taker.tp": {"value": 0.05, "set_by": "scout-tuner", "expires": exp},
        "scout.dip_range_max": {"value": 0.15, "set_by": "scout-tuner", "expires": exp},
        "live.clip_scale": {"value": 1.25, "set_by": "evidence-board", "expires": exp},
    }
    st = build_stances(active)
    assert set(st) == {"taker", "scout:scout.dip_range_max", "live-clip"}, st
    assert st["taker"]["stance"] == {"taker.dip_range": 0.08, "taker.tp": 0.05}
    assert st["taker"]["set_by"] == ["scout-tuner"]

    # tracking: open new; hold same; value change closes+reopens; release
    # backdates end to the last seen expiry; long stances slice
    o1, c1 = track({}, st, now)
    assert set(o1) == set(st) and c1 == [], (o1, c1)
    assert o1["taker"]["start"] == now
    o2, c2 = track(o1, st, now + 3600)
    assert c2 == [] and o2["taker"]["start"] == now
    st_moved = {k: dict(v, stance=dict(v["stance"])) for k, v in st.items()}
    st_moved["taker"]["stance"]["taker.tp"] = 0.06
    o3, c3 = track(o2, st_moved, now + 7200)
    assert [c["group"] for c in c3] == ["taker"] and c3[0]["reason"] == "changed"
    assert c3[0]["end"] == now + 7200 and o3["taker"]["start"] == now + 7200
    gone = {k: v for k, v in st.items() if k != "taker"}
    o4, c4 = track(o2, gone, now + 20000)
    rel = [c for c in c4 if c["group"] == "taker"]
    assert rel and rel[0]["reason"] == "released"
    assert rel[0]["end"] == now + 7800, rel   # backdated to expires, not now
    o5, c5 = track(o2, st, now + SLICE_H * 3600 + 60)
    assert all(c["reason"] == "slice" for c in c5) and len(c5) == len(st), c5
    assert o5["taker"]["start"] == now + SLICE_H * 3600 + 60

    # taker grading: the replay counterfactual. Tape where dip tickets sit at
    # range_pos 0.07 — defaults (0.05) take nothing; the stance (0.08) takes
    # them. Rising marks -> positive delta; dumping marks -> negative.
    def dt(h, mi=0):
        return datetime(2026, 7, 16, h, mi, tzinfo=timezone.utc)

    def snap(h, marks, tickets=None, mi=0):
        return (dt(h, mi), {"marks": marks, "tickets": tickets or {}})

    dipt = {"sym": "DDD", "range_pos": 0.07}
    dipt2 = {"sym": "EEE", "range_pos": 0.07}

    def mk_tape(end_px):
        tape = [snap(0, {"DDD": 100.0}, {"dip": [dipt]}),
                snap(1, {"DDD": end_px}),
                snap(2, {"EEE": 100.0}, {"dip": [dipt2]}),
                snap(3, {"EEE": end_px})]
        tape += [snap(4, {}, mi=m) for m in (0, 10, 20, 30, 40)]
        return tape

    win_tape = mk_tape(105.0)
    t0 = dt(0).timestamp()
    ep = {"group": "taker", "start": t0, "end": dt(5).timestamp(),
          "stance": {"taker.dip_range": 0.08}}
    g = grade_taker(ep, win_tape)
    assert g["status"] == "graded" and g["delta_usd"] > 0, g
    g_bad = grade_taker(ep, mk_tape(90.0))
    assert g_bad["status"] == "graded" and g_bad["delta_usd"] < 0, g_bad
    # too-short episodes refuse to grade (anti-noise floor)
    g_short = grade_taker(dict(ep, end=t0 + 600), win_tape)
    assert g_short["status"] == "too-short", g_short
    # replay patching restored the module bars
    assert tt.DIP_RANGE == DEFAULTS["DIP_RANGE"]

    # scout grading: n4h delta for the mapped lens; top_n counts every lens
    sm = {"lens_fwd": {"lenses": {"dip": {"n4h": 25}, "momentum": {"n4h": 200}}}}
    ep_s = {"group": "scout:scout.dip_range_max", "start": t0,
            "end": t0 + 4 * 3600, "stance": {"scout.dip_range_max": 0.15},
            "start_metrics": sm}
    lf_end = {"lenses": {"dip": {"n4h": 60}, "momentum": {"n4h": 210}}}
    gs = grade_scout(ep_s, lf_end)
    assert gs == {"status": "graded", "n4h_start": 25, "n4h_end": 60,
                  "delta_grades": 35}, gs
    ep_t = dict(ep_s, group="scout:scout.ticket_top_n",
                stance={"scout.ticket_top_n": 9}, start_metrics=sm)
    gt = grade_scout(ep_t, lf_end)
    assert gt["delta_grades"] == 45, gt
    assert grade_scout(dict(ep_s, start_metrics={}), lf_end)["status"] == "ungraded"

    # gapscout grading: quiet reset inside the window = found activity
    ep_g = {"group": "gapscout", "start": t0, "end": t0 + 10 * 3600,
            "stance": {"gapscout.prefilter_gap": 0.0015},
            "start_metrics": {"quiet_hours": 30.0}}
    gg = grade_gapscout(ep_g, {"quiet_hours": 2.0})
    assert gg["status"] == "graded" and gg["found_activity"] is True, gg
    gg2 = grade_gapscout(ep_g, {"quiet_hours": 40.0})
    assert gg2["found_activity"] is False, gg2
    assert grade_gapscout(ep_g, {})["status"] == "ungraded"

    # LIVE lane learning: per-trade during vs BOTH baselines (pre-window +
    # shadow twin). Thin data records; clear divergence signals.
    LIVE = "crypto-trend-daily-lighter"
    TWIN = "crypto-trend-daily-lshadow"

    def lt(bot, off_h, pct):
        return {"bot": bot, "profit_ratio": pct, "close_ts": _iso(t0 + off_h * 3600)}

    ep_lv = {"group": "live-clip", "start": t0, "end": t0 + 6 * 3600,
             "stance": {"live.clip_scale": 1.25}}
    # during: live 6 trades @ +0.2%; before: 6 @ +1.5%; twin during: 6 @ +1.2%
    tr_bad = ([lt(LIVE, 1 + i * 0.5, 0.002) for i in range(6)]
              + [lt(LIVE, -6 + i * 0.5, 0.015) for i in range(6)]
              + [lt(TWIN, 1 + i * 0.5, 0.012) for i in range(6)]
              + [lt("not-live", 2, 9.9)])
    glb = grade_live(ep_lv, tr_bad)
    assert glb["status"] == "graded" and glb["signal"] == "bad", glb
    assert glb["n_during"] == 6 and glb["mean_pct_during"] == 0.2, glb
    # worse than pre-window but BETTER than the twin -> flat (never 'bad'
    # unless worse than EVERY baseline — real money isn't blamed on noise)
    tr_flat = ([lt(LIVE, 1 + i * 0.5, 0.002) for i in range(6)]
               + [lt(LIVE, -6 + i * 0.5, 0.015) for i in range(6)]
               + [lt(TWIN, 1 + i * 0.5, -0.02) for i in range(6)])
    assert grade_live(ep_lv, tr_flat)["signal"] == "flat"
    # better than both -> good
    tr_good = ([lt(LIVE, 1 + i * 0.5, 0.02) for i in range(6)]
               + [lt(LIVE, -6 + i * 0.5, 0.002) for i in range(6)]
               + [lt(TWIN, 1 + i * 0.5, 0.001) for i in range(6)])
    assert grade_live(ep_lv, tr_good)["signal"] == "good"
    # thin during-window or no usable baseline -> recorded (no signal)
    assert grade_live(ep_lv, tr_bad[:3])["status"] == "recorded"
    assert grade_live(ep_lv, [lt(LIVE, 1 + i * 0.5, 0.002)
                              for i in range(6)])["status"] == "recorded"
    # live-funding group grades only the funding rows
    ep_fund = dict(ep_lv, group="live-funding",
                   stance={"live.funding.enter_apr": 0.30})
    glf = grade_live(ep_fund, tr_bad, group="live-funding")
    assert glf["status"] == "recorded" and glf["n_during"] == 0, glf

    # verdicts: floors + directions. Two negative taker episodes past the $
    # bar -> HURTING; two positive -> HELPING; one -> neutral (floor).
    def tk_ep(delta, levers=("taker.dip_range",)):
        return {"group": "taker", "status": "graded", "levers": list(levers),
                "delta_usd": delta}

    v = lever_verdicts([tk_ep(-2.5), tk_ep(-1.5)])
    assert v["taker.dip_range"]["verdict"] == "hurting", v
    assert v["taker.dip_range"]["sum_delta_usd"] == -4.0
    v2 = lever_verdicts([tk_ep(+2.5), tk_ep(+1.5)])
    assert v2["taker.dip_range"]["verdict"] == "helping", v2
    v3 = lever_verdicts([tk_ep(-9.9)])
    assert v3["taker.dip_range"]["verdict"] == "neutral", v3   # n floor holds
    # mixed joint stance: blame shared across both levers, conservative
    v4 = lever_verdicts([tk_ep(-2.0, ("taker.dip_range", "taker.tp")),
                         tk_ep(-2.0, ("taker.dip_range", "taker.tp"))])
    assert v4["taker.dip_range"]["verdict"] == "hurting" \
        and v4["taker.tp"]["verdict"] == "hurting" \
        and v4["taker.tp"]["joint"] is True, v4
    # offsetting episodes stay neutral (no majority + no margin)
    v5 = lever_verdicts([tk_ep(-3.5), tk_ep(+3.5)])
    assert v5["taker.dip_range"]["verdict"] == "neutral", v5
    # scout levers can only help or sit neutral — never hurt
    sc = [{"group": "scout:scout.dip_range_max", "status": "graded",
           "levers": ["scout.dip_range_max"], "delta_grades": 8},
          {"group": "scout:scout.dip_range_max", "status": "graded",
           "levers": ["scout.dip_range_max"], "delta_grades": 7}]
    v6 = lever_verdicts(sc)
    assert v6["scout.dip_range_max"]["verdict"] == "helping", v6
    v7 = lever_verdicts(sc[:1])
    assert v7["scout.dip_range_max"]["verdict"] == "neutral", v7
    # gapscout: found_activity -> helping
    v8 = lever_verdicts([{"group": "gapscout", "status": "graded",
                          "levers": ["gapscout.prefilter_gap"],
                          "found_activity": True}])
    assert v8["gapscout.prefilter_gap"]["verdict"] == "helping", v8
    # live verdicts: two 'bad' paired episodes -> HURTING; two 'good' ->
    # HELPING; mixed -> neutral; a single episode never verdicts (floor)
    def lv_ep(sig, lever="live.clip_scale"):
        return {"group": "live-clip", "status": "graded", "levers": [lever],
                "signal": sig}

    v9 = lever_verdicts([lv_ep("bad"), lv_ep("bad")])
    assert v9["live.clip_scale"]["verdict"] == "hurting" \
        and v9["live.clip_scale"]["basis"] == "live-paired", v9
    v10 = lever_verdicts([lv_ep("good"), lv_ep("good"), lv_ep("flat")])
    assert v10["live.clip_scale"]["verdict"] == "helping", v10
    v11 = lever_verdicts([lv_ep("bad"), lv_ep("good")])
    assert v11["live.clip_scale"]["verdict"] == "neutral", v11
    assert lever_verdicts([lv_ep("bad")])["live.clip_scale"]["verdict"] == "neutral"
    # xp episodes still produce NO verdict (the judge's arms grade xp)
    assert lever_verdicts([{"group": "xp", "status": "graded",
                            "levers": ["xp.funding.enter_apr"]}]) == {}
    # non-graded episodes contribute nothing
    assert lever_verdicts([dict(tk_ep(-9), status="too-short")]) == {}

    # the consumer hooks: fresh verdicts surface on their own side ONLY;
    # stale/absent restricts nothing AND earns nothing (symmetry)
    fresh_state = {"updated": _iso(now), "ttl_sec": TTL_SEC,
                   "verdicts": {"taker.dip_range": {"verdict": "hurting"},
                                "taker.tp": {"verdict": "helping"}}}
    assert set(hurting_levers(fresh_state, now)) == {"taker.dip_range"}
    assert set(helping_levers(fresh_state, now)) == {"taker.tp"}
    stale = dict(fresh_state, updated="2020-01-01T00:00:00+00:00")
    assert hurting_levers(stale, now) == {} and helping_levers(stale, now) == {}
    assert hurting_levers({}, now) == {} and hurting_levers(None, now) == {}
    assert helping_levers({}, now) == {} and helping_levers(None, now) == {}

    # every graded lane's levers are registry-known (a rename there must
    # break HERE, not silently stop grading)
    for lever in list(TAKER_ATTR) + [k for k in SCOUT_LENS]:
        assert lever in tuning.LEVERS, lever

    print("fleet_proprioception selftest OK (grouping, episode lifecycle "
          "incl. backdated release + daily slice, replay counterfactual "
          "win/lose/too-short, scout throughput, gapscout activity, live "
          "paired-learning (bad/flat/good vs pre-window+twin, funding split), "
          "verdict floors + joint blame, fail-safe hurting+helping hooks)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
