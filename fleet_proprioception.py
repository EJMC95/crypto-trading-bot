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
         the only writer). AND — 'real money bots too' (16-Jul late) —
         the REAL-MONEY BOTS THEMSELVES consume the verdicts every loop:
         fleet_tuning.get_lever reverts a HURTING live-lane lever to the
         operator's env default AT THE CONSUMER (funding bot apply_levers
         + both bots' clip via venues), closing the latency window between
         a verdict landing and the board/judge/TTL catching up — same
         central-hook pattern as the immune quarantine, restrict-only by
         construction. The single live earn: the clip ladder's TOP step
         (1.5) now requires a measured HELPING grade at 1.25 —
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
# [2026-07-17] the floor that actually bites: closed TRADES in the episode's
# replay window. Time and snapshots measure the tape, not the evidence — see
# grade_taker for the live 3.13h/37-snap episode that graded on zero trades.
MIN_EP_CLOSES = int(os.environ.get("PROP_MIN_EP_CLOSES", "4"))
SLICE_H = float(os.environ.get("PROP_SLICE_H", "24"))        # long-stance cut
# [2026-07-21 review item 12] same-stance rejoin grace: a stance that lapses
# by TTL between an author's re-asserts continues its episode if re-asserted
# identically within this window (pooling), instead of fragmenting into
# sub-floor slivers. 0 disables (pre-review behaviour).
REJOIN_H = float(os.environ.get("PROP_REJOIN_GRACE_H", "3.0"))
VERDICT_WINDOW = int(os.environ.get("PROP_VERDICT_WINDOW", "10"))
MIN_EPISODES = int(os.environ.get("PROP_MIN_EPISODES", "2"))
HURT_USD = float(os.environ.get("PROP_HURT_USD", "3.0"))
# [2026-07-17 IMB-08] verdict EVIDENCE EXPIRY — the missing heal path. The
# IMB-01 fix (observed_active) correctly stops a reverted lever generating
# episodes, but verdicts recompute from the stored ledger, so a HURTING
# verdict could never clear on honest evidence again: first hurting = a
# PERMANENT freeze (the old "heal" was the contaminated default-arm
# episodes we removed). Now any non-neutral verdict whose NEWEST
# contributing episode is older than this window decays to neutral
# (evidence too stale to steer). For hurting that is a bounded PROBATION:
# the author may re-assert once, fresh episodes re-grade it, and a
# still-bad lever re-freezes within an episode (~1 day). For helping it is
# plain staleness fail-safe: an expand unlock must not ride week-old
# evidence. Symmetric, and both directions decay toward NEUTRAL.
HURT_PROBATION_SEC = float(os.environ.get("PROP_HURT_PROBATION_D", "7")) * 86400
HELP_USD = float(os.environ.get("PROP_HELP_USD", "3.0"))
GRADES_MIN = int(os.environ.get("PROP_GRADES_MIN", "10"))
# live-lane grading floors (16-Jul evening, operator: "the live lane needs
# to learn") — real money gets HIGHER evidence bars than the shadow lanes
LIVE_EP_MIN_N = int(os.environ.get("PROP_LIVE_EP_MIN_N", "5"))
LIVE_BASE_MIN_N = int(os.environ.get("PROP_LIVE_BASE_MIN_N", "3"))
LIVE_MARGIN_PP = float(os.environ.get("PROP_LIVE_MARGIN_PP", "0.25"))
# [2026-07-17 AUDIT] Retired row REMOVED — the third copy of the same rot (see
# evidence_board.LIVE_ROWS and fleet_respiration.LIVE_BREATHS). Tide Rider left
# the live slot on 17-Jul and its bot_pnl row is DELETED at boot
# (cleanup_legacy_bots.py:53), so it can contribute no trades to any baseline;
# it could only ever dilute a live cohort with a book that structurally cannot
# appear. Shares EVBOARD_LIVE_ROWS with the board deliberately, so the two
# organs can never disagree about who is live. The Ticket Taker took that slot
# but is NOT added: it never calls venue_context (lighter_ticket_taker.py:523),
# so it does not consume live.clip_scale — grading a lever on a book the lever
# cannot move is exactly the defect fixed in grade_live below.
LIVE_ROWS = {s.strip() for s in os.environ.get(
    "EVBOARD_LIVE_ROWS",
    "perps-funding-lighter-lighter").split(",")
    if s.strip()}

# [2026-07-30 THE SHADOW BOOKS LEARN — operator: "grow into what works"]
# Six books gained growth-rail levers and their episodes fell through to
# `other:*`, i.e. RECORDED and never graded — so the tuner's hurting-refusal
# and the board's helping-walk could never fire for them. The rail could move
# their knobs and never find out whether it helped. These maps close that.
#
# lever prefix -> the bot_pnl row the lever actually steers. A lever graded
# against a book it cannot move is precisely the defect grade_live documents
# for live.clip_scale, so this mapping is the load-bearing part.
BOOK_LEVER_BOTS = {
    "carry": "perps-funding-carry-lshadow",
    "fundspread": "perps-funding-spread-lshadow",
    "disloc": "lighter-dislocation-lshadow",
    "index": "equities-regime-lshadow",
    "trend": "crypto-trend-daily-lshadow",
    "sniper": "lighter-perp-sniper-lshadow",
}
# SELECTION vs CAPACITY, and the distinction is not cosmetic — it decides
# which QUESTION the evidence can answer.
#
#   SELECTION levers change WHICH trades are taken (a gate, a ranking, a
#   universe). Per-trade return moves with them, so "did the mean improve?"
#   is a well-posed question.
#
#   CAPACITY levers change HOW MANY concurrent positions the book may hold.
#   grade_live's hard-won lesson applies but does NOT transfer wholesale:
#   `live.clip_scale` is MATHEMATICALLY invariant to per-trade pnl_pct (the
#   clip cancels top and bottom — measured, one distinct value across the
#   whole range), so it fails closed. A capacity lever is different: carry
#   prices every trade against a per-position NOTIONAL constant
#   (funding_carry_bot.py:467 `pnl_pct = pnl / pos["notional"]`), so the
#   metric does not mechanically cancel — but the COMPOSITION changes,
#   because slots 9..12 are filled with the 9th..12th best candidates.
#   The honest question for capacity is therefore NOT "did the mean rise"
#   (it should not; a ranked selector reaching deeper takes worse names) but
#   "did quality HOLD while throughput rose?" — dilution is the real failure
#   mode of widening a ranked book, and it IS detectable.
BOOK_CAPACITY_LEVERS = {"carry.max_positions", "fundspread.k", "index.max_open"}
BOOK_EP_MIN_N = int(os.environ.get("PROP_BOOK_EP_MIN_N", "5"))
BOOK_BASE_MIN_N = int(os.environ.get("PROP_BOOK_BASE_MIN_N", "5"))
BOOK_MARGIN_PP = float(os.environ.get("PROP_BOOK_MARGIN_PP", "0.30"))

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
    # [2026-07-30 THE SHADOW BOOKS LEARN] Each book lever stands alone: they
    # steer six SEPARATE books, so lumping them (as `other:carry` did) would
    # blame one book's movement on another's lever. Grouping per-lever also
    # keeps the counterfactual honest — the baseline is that ONE book's own
    # pre-episode window.
    if name.split(".")[0] in BOOK_LEVER_BOTS:
        return f"book:{name}"
    return f"other:{name.split('.')[0]}"


def observed_active(active, quarantined, live_hurting):
    """[2026-07-16 IMB-01] The stance set consumers actually FOLLOW. While a
    consumer-side revert is in force — immune QUARANTINE on any lane, or a
    HURTING grade on a lighter-live lever — get_lever hands every consumer
    the operator default, so an episode opened/held over that span would
    measure the DEFAULT and bill the verdict to the stance (self-poisoning:
    a hurting verdict could never clear on honest evidence). Dropping the
    reverted lever from the observed set closes its episode honestly
    ('released'/'changed') and opens no new one until the revert lifts.
    Mirrors get_lever's own scoping exactly. Pure — selftested."""
    out = {}
    for k, v in (active or {}).items():
        if k in (quarantined or ()):
            continue
        if k in (live_hurting or ()) and \
                (tuning.LEVERS.get(k) or {}).get("lane") == "lighter-live":
            continue
        out[k] = v
    return out


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


def track(open_eps, stances_now, now, slice_h=SLICE_H, rejoin_h=None):
    """One tracking step. Returns (open_next, closed) where closed carries
    {group, stance, set_by, start, end, reason, start_metrics}. Reasons:
    'changed' (stance moved), 'released' (gone — end backdated to the last
    seen expiry so a dead author doesn't inflate the window), 'slice'
    (long-running stance cut so grades accrue). start_metrics for newly
    opened groups is left None — the caller stamps it (feed reads are
    impure).

    [2026-07-21 review item 12 — EPISODE POOLING] The first real week graded
    almost nothing: 16/17 taker episodes ended too-few-trades because the
    tuner's levers EXPIRE between its hourly re-asserts, fragmenting one
    continuous stance into 2-4h slivers each too short for the trade floor
    (the week's one repeated stance had 10 closes POOLED — a verdict's
    worth). A stance that vanished by NATURAL EXPIRY (last_expires <= now)
    now waits in a rejoin grace (PROP_REJOIN_GRACE_H): the SAME stance
    re-asserted inside it CONTINUES the episode (gone_since cleared); a
    DIFFERENT stance or a lapsed grace closes it with the end backdated to
    the expiry, exactly as before. A stance removed MID-TTL (quarantine /
    IMB-01 hurting-revert — last_expires still in the future) closes
    IMMEDIATELY: pooling across a revert would bill default-behaviour tape
    to the stance, the self-poisoning observed_active exists to prevent.
    The replay counterfactual is gap-safe by construction — both arms
    (stance bars vs env defaults) replay the SAME tape, gaps included."""
    grace = (REJOIN_H if rejoin_h is None else rejoin_h) * 3600.0
    open_next, closed = {}, []
    for group, cur in (open_eps or {}).items():
        now_g = stances_now.get(group)
        exp = cur.get("last_expires")
        expn = exp if isinstance(exp, (int, float)) and exp else None
        gone = cur.get("gone_since")
        if now_g is None:
            lapsed = expn is not None and expn <= now
            if lapsed and gone is None:
                gone = expn                    # the gap starts at the expiry
            if lapsed and grace > 0 and now - gone <= grace:
                open_next[group] = dict(cur, gone_since=gone)  # await re-assert
                continue
            end = min(now, expn) if expn is not None else now
            closed.append(dict(cur, group=group, end=max(end, cur["start"]),
                               reason="released"))
        elif now_g["stance"] != cur.get("stance"):
            # a different stance arriving mid-grace ends the old episode at
            # its expiry (the stance was genuinely dead through the gap)
            end = gone if gone is not None else now
            closed.append(dict(cur, group=group, end=max(end, cur["start"]),
                               reason="changed"))
        elif now - cur["start"] >= slice_h * 3600:
            closed.append(dict(cur, group=group, end=now, reason="slice"))
            open_next[group] = {"stance": dict(now_g["stance"]),
                                "set_by": now_g["set_by"], "start": now,
                                "last_expires": now_g["expires_max"],
                                "start_metrics": None}
        else:
            nxt = dict(cur, last_expires=now_g["expires_max"],
                       set_by=now_g["set_by"])
            nxt.pop("gone_since", None)        # re-asserted — the gap closed
            open_next[group] = nxt
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


def _marked(rep):
    """[2026-07-17 IMB-10 parity — mirrors lighter_scout_tuner/_incubator]
    closed_net + end-of-tape unrealized. closed_net alone is blind to
    DEFERRAL: an arm 'wins' by pushing losses past the window's end, where
    open positions are valued at entry and invisible to the gate. Both other
    replay consumers score marked; this one was missed."""
    return float(rep["closed_net"]) + float(rep.get("unrealized") or 0.0)


def _closes(rep):
    return sum(int(s.get("closed") or 0)
               for s in (rep.get("lenses") or {}).values())


def grade_taker(ep, tape):
    """The counterfactual: during-episode tape, env defaults vs the stance's
    bars. delta_usd > 0 = the enactment beat doing nothing.

    [2026-07-17] Two floors, because HOURS AND SNAPSHOTS ARE NOT EVIDENCE.
    Observed live: a 3.13h/37-snapshot taker episode returned
    stance_net 0.0 / default_net 0.0 / delta_usd 0.0 and was stamped
    "graded" — ZERO trades closed on either arm, recorded as a measurement.
    The old floors (MIN_EP_H=0.75 → 45 minutes, MIN_EP_SNAPS=8) count time
    and ticks against a strategy whose median position lives for hours, so
    an episode could clear both while resolving nothing. An empty sample is
    UNGRADEABLE, not neutral — and 'neutral' is not free: it spends an
    episode toward MIN_EPISODES and lets a verdict form out of nothing.

    The floor is denominated in CLOSED TRADES (the fleet's quantum of
    evidence: one fill swings ~$3.50 at clip $50/TP+4%/SL-3%, which is
    larger than HURT_USD/HELP_USD — so a single trade can carry a verdict).
    Taken on the better-evidenced arm: the two arms trade different sets by
    construction, and the question is whether EITHER resolved enough to
    speak. Restrict-only and fail-safe by the organ's own contract — an
    ungraded episode restricts nothing AND earns nothing."""
    start, end = ep["start"], ep["end"]
    window = [(dt, p) for dt, p in (tape or [])
              if start <= dt.timestamp() <= end]
    if (end - start) < MIN_EP_H * 3600 or len(window) < MIN_EP_SNAPS:
        return {"status": "too-short", "n_snaps": len(window)}
    bars = {TAKER_ATTR[k]: v for k, v in ep["stance"].items()
            if k in TAKER_ATTR}
    if not bars:
        return {"status": "ungraded"}
    base_rep = _replay_with(window, DEFAULTS)
    var_rep = _replay_with(window, dict(DEFAULTS, **bars))
    n_closed = max(_closes(base_rep), _closes(var_rep))
    if n_closed < MIN_EP_CLOSES:
        return {"status": "too-few-trades", "n_snaps": len(window),
                "n_closed": n_closed}
    return {"status": "graded", "n_snaps": len(window), "n_closed": n_closed,
            "default_net": _marked(base_rep), "stance_net": _marked(var_rep),
            "delta_usd": round(_marked(var_rep) - _marked(base_rep), 2)}


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

    # [2026-07-17 AUDIT] live.clip_scale is RECORDED, never GRADED — the metric
    # above is EXACTLY invariant to it, so any verdict is other-causes + noise.
    #
    # The lever's only effect is `order_usd` (venues/__init__.py:92). The
    # recorder computes pnl_pct = (price_pnl + fund_pnl) / order_usd
    # (lighter_funding_bot.py:477), and BOTH terms are proportional to the clip
    # (price_pnl = |held|*(px-entry) with held = clip/entry; fund_pnl scales
    # with notional). The clip therefore cancels top and bottom. Measured
    # across the whole lever range 0.5 -> 1.5: profit_ratio 0.0108080000 at
    # EVERY step — ONE distinct value.
    #
    # This is not a metric bug to swap out; it is the docstring above being
    # right for the wrong lever. Per-trade pnl_pct is size-invariant BY DESIGN
    # (the judge's lesson: equity comparisons across different-sized books
    # lie), which is correct for live.funding.* — those bars change the EDGE,
    # so the per-trade return really does move — and structurally blind for a
    # lever that changes only SIZE. Nor is there a legitimate substitute: the
    # size-dependent alternative (pnl_abs) would say "bigger clips earn more
    # while winning", which is a martingale, not evidence. A RISK choice on a
    # <$100 real book is not gradeable by outcome at this n.
    #
    # So it fails CLOSED, which is what its own consumers already expect of a
    # dark sense: the board's top step (1.5) requires a MEASURED helping at
    # 1.25 and now stays out of reach, and no noise-driven `hurting` reverts a
    # real clip at get_lever. Restrict-only — this removes an actuator input
    # and adds none. The board's DOWN reflex and the lever TTL are unaffected
    # and remain the real protection. The episode RECORD is kept: the numbers
    # are still true, it is the causal claim that was never supportable.
    if group == "live-clip":
        return {"status": "recorded", "reason": "metric-invariant-to-lever",
                **rec}

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


def grade_book(ep, trades):
    """Grade ONE shadow-book lever episode against that book's own pre-episode
    window. Two questions, chosen by lever kind — see BOOK_CAPACITY_LEVERS.

    SELECTION (a gate / ranking / universe): did per-trade return improve?
      good  -> mean_during > mean_before + margin
      bad   -> mean_during < mean_before - margin

    CAPACITY (more concurrent slots): did QUALITY HOLD while throughput rose?
      A ranked book reaching deeper takes worse names by construction, so
      demanding a higher mean would reject every capacity widening that ever
      worked. The failure mode worth catching is DILUTION.
      good  -> throughput rose AND mean held within the margin
      bad   -> mean fell by more than the margin (the extra slots are being
               filled with materially worse candidates)

    Thin data -> 'recorded' (no signal, no verdict), same contract as every
    other lane. Shadow books, so the floors sit below the live lane's.
    """
    # THE EPISODE CARRIES `stance` (a {lever: value} dict), NOT `lever` — see
    # the tracker at :368/:379 and grade_scout's own `next(iter(ep["stance"]))`
    # at :458. An earlier cut of this read ep["lever"], which is absent on every
    # real episode, so `bot` was always None and this grader would have returned
    # "unmapped-lever" forever — born inert, exactly the class it exists to fix.
    # Its selftest passed because the fixture invented an episode shape the
    # tracker never produces. Derive it the way the sibling graders do.
    lever = next(iter(ep.get("stance") or ()), "") or (ep.get("lever") or "")
    bot = BOOK_LEVER_BOTS.get(lever.split(".")[0])
    start, end = ep["start"], ep["end"]
    span = max(1.0, float(end - start))

    def stats(a, b):
        pcts = [float(r["profit_ratio"]) for r in trades or []
                if str(r.get("bot")) == bot
                and r.get("profit_ratio") is not None
                and a <= (_parse_ts(r.get("close_ts")) or -1) < b]
        return (len(pcts),
                round(100.0 * sum(pcts) / len(pcts), 3) if pcts else None)

    n_in, m_in = stats(start, end)
    n_pre, m_pre = stats(start - span, start)
    rec = {"bot": bot, "n_during": n_in, "mean_pct_during": m_in,
           "n_before": n_pre, "mean_pct_before": m_pre}
    if not bot:
        # an unmapped lever must never be graded against SOME book — that is
        # the grade_live defect (grading a lever on a book it cannot move).
        return {"status": "recorded", "reason": "unmapped-lever", **rec}
    if (n_in < BOOK_EP_MIN_N or n_pre < BOOK_BASE_MIN_N
            or m_in is None or m_pre is None or span < MIN_EP_H * 3600):
        return {"status": "recorded", **rec}

    if lever in BOOK_CAPACITY_LEVERS:
        # throughput per unit time, so a longer episode cannot fake a rise
        rate_in, rate_pre = n_in / span, n_pre / span
        rec["rate_during"], rec["rate_before"] = rate_in, rate_pre
        if m_in < m_pre - BOOK_MARGIN_PP:
            sig = "bad"                      # diluted: deeper = materially worse
        elif rate_in > rate_pre and m_in >= m_pre - BOOK_MARGIN_PP:
            sig = "good"                     # more bets, quality held
        else:
            sig = "flat"
    else:
        if m_in > m_pre + BOOK_MARGIN_PP:
            sig = "good"
        elif m_in < m_pre - BOOK_MARGIN_PP:
            sig = "bad"
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
    if g.startswith("book:"):
        return grade_book(ep, feeds.get("trades"))
    if g == "xp":
        return {"status": "recorded"}   # the judge's paired arms grade xp
    return {"status": "recorded"}


# ---------------------------------------------------------------------------
# pure: per-lever verdicts (selftested offline)
# ---------------------------------------------------------------------------

def lever_verdicts(episodes, now=None):
    """{lever: {verdict, n, ...}} over the newest VERDICT_WINDOW graded
    episodes per lever. HURTING exists on the two lanes with a real paired
    measure: taker (the $ replay counterfactual) and live (per-trade vs
    pre-window + shadow twin — 16-Jul evening, 'the live lane needs to
    learn'). Joint stances share blame — conservative in the restrict
    direction. Diet/detection levers can only help or sit neutral; xp never
    verdicts here (the judge's paired arms own it).
    [2026-07-17 IMB-08] pass `now` to apply EVIDENCE EXPIRY: a non-neutral
    verdict whose newest contributing episode is older than
    HURT_PROBATION_SEC decays to neutral (probation flag kept for display)
    — every consumer hook (tuner skip, get_lever live revert, board
    release/top-step gate, judge prop_fade) keys on the verdict string, so
    the probe re-arms everywhere at once. now=None skips expiry (offline
    analysis of a historical ledger)."""
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
            # [2026-07-17] MIN_EPISODES applies HERE TOO. This was the only lane
            # that graded off a bare any() with no episode floor, while the taker
            # (n>=MIN_EPISODES + $ bars), scout-lens (GRADES_MIN) and live lanes
            # all gated theirs — and the module docstring advertises "floors n>=2
            # episodes" for all of them. MEASURED 17-Jul: it published n=1
            # HELPING for gapscout.prefilter_gap AND .max_book_fetches, off ONE
            # 9.3h episode, and the board carried both into the 21-Jul review as
            # "the widening is paying". One episode of "the census moved" is not
            # evidence that the widening moved it; `any()` over a single sample
            # is just that sample. A HELPING here also discounts the board's
            # widen-ladder bars (x0.75) — an expand-direction consumer fed by an
            # unfloored grader.
            # Gap Scout was RETIRED on 17-Jul (census stale forever -> census_ok
            # False -> grade_gapscout never runs), so this lane grades nothing
            # new and the floor is inert TODAY. It is still the right code: the
            # floor is what the docstring promises, and a dead lane that would
            # publish an unfloored verdict the moment a census returned is a
            # loaded gun, not a non-issue.
            n_found = sum(1 for e in eps if e.get("found_activity"))
            v = "helping" if (n >= MIN_EPISODES and n_found >= MIN_EPISODES) \
                else "neutral"
            out[lever] = {"verdict": v, "n": n, "n_found": n_found,
                          "basis": "census-activity"}
        elif lever.split(".")[0] in BOOK_LEVER_BOTS:
            # [2026-07-30] Without this branch a book episode could be graded
            # perfectly and still yield NO verdict, so no consumer hook — the
            # board's hurting-refusal, the tuner's skip — could ever fire.
            # Same good/bad episode-vote shape as the live lane (grade_book
            # emits the same `signal` field), at the shadow-lane floor.
            goods = sum(1 for e in eps if e.get("signal") == "good")
            bads = sum(1 for e in eps if e.get("signal") == "bad")
            v = "neutral"
            if bads >= MIN_EPISODES and bads > goods:
                v = "hurting"
            elif goods >= MIN_EPISODES and goods > bads:
                v = "helping"
            out[lever] = {"verdict": v, "n": n, "good": goods, "bad": bads,
                          "basis": "book-paired"}
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
        # [2026-07-17 IMB-08] evidence expiry (see module constant): stale
        # evidence steers nothing, in EITHER direction. Verdict fields are
        # kept so the dashboard still shows what the evidence said.
        if now is not None and out.get(lever, {}).get("verdict") in (
                "hurting", "helping"):
            newest = max((float(e.get("end") or 0) for e in eps), default=0.0)
            if newest and (now - newest) >= HURT_PROBATION_SEC:
                out[lever]["expired_verdict"] = out[lever]["verdict"]
                out[lever]["verdict"] = "neutral"
                out[lever]["probation"] = True
                out[lever]["evidence_age_d"] = round((now - newest) / 86400, 1)
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
    # [2026-07-17 AUDIT] A FAILED READ IS NOT AN EMPTY LEDGER. Same trap as the
    # judge: `load_state` collapses "no row" and "read failed" into None, this
    # function seeds from `or {}`, and run_once writes the payload back
    # UNCONDITIONALLY — so one transient read error published `episodes: []`,
    # `verdicts: {}` over the real ledger, permanently (up to EP_CAP=120
    # episodes plus every open one). load_state_checked exists precisely for
    # "any caller that SEEDS durable state on an empty read"; this is one.
    #
    # It reaches real money: the wiped verdicts include live-lane rulings, so a
    # HURTING live lever that get_lever was reverting to the operator's default
    # every loop silently STOPS being reverted — the protection evaporates with
    # the evidence for it, and the fresh-and-empty payload looks perfectly
    # healthy to every consumer. An hourly organ loses one hour by skipping;
    # seeding loses the out-of-sample record the whole growth rail is graded on.
    _ok, prior = store.load_state_checked(KEY)
    if not _ok:
        print("[fleet-proprioception] state READ FAILED — skipping this cycle "
              "rather than publishing an empty ledger over the real one "
              "(a blind organ must not look healthy). Retries next hour.",
              flush=True)
        return
    prior = prior or {}
    episodes = list(prior.get("episodes") or [])
    open_eps = {}
    for g, cur in (prior.get("open") or {}).items():
        if isinstance(cur, dict) and isinstance(cur.get("stance"), dict) \
                and isinstance(cur.get("start"), (int, float)):
            open_eps[g] = cur

    active = tuning.active_levers(now_ts=now)
    # observe only what consumers FOLLOW (quarantined / live-hurting levers
    # are being reverted at get_lever — measuring them would poison the
    # verdicts). Fail-safe: a hook error observes the unfiltered set.
    try:
        active = observed_active(active, tuning._quarantined(now),
                                 tuning._live_hurting(now))
    except Exception:  # noqa: BLE001
        pass
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
    # [2026-07-30] `book:*` MUST be in this predicate. The grader reads
    # feeds["trades"], and without this the fetch never fires for a book
    # episode, so grade_book would return "recorded" forever — a grader that
    # is wired, tested, and structurally incapable of ever grading anything.
    # That is the same registered-but-inert class this whole pass exists to
    # remove, and it would have shipped silently.
    if any(c["group"] in ("live-clip", "live-funding", "live", "xp")
           or str(c["group"]).startswith("book:")
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
    # [2026-07-30] EP_CAP was a GLOBAL FIFO: a burst of ungradeable
    # ("recorded") episodes could evict GRADED ones, and graded episodes are
    # the only rows lever_verdicts can use — including the live-lane rows
    # whose verdicts revert a real-money lever. Six new book lanes make that
    # burst likely rather than theoretical. Graded rows now hold the budget
    # first; recorded rows fill what is left. Chronological order restored so
    # every downstream "newest episode" read is unchanged.
    _graded = [e for e in episodes if e.get("status") == "graded"][-EP_CAP:]
    _rest = [e for e in episodes if e.get("status") != "graded"]
    _room = max(0, EP_CAP - len(_graded))
    episodes = sorted(_graded + _rest[-_room:] if _room else _graded,
                      key=lambda e: float(e.get("end") or 0))

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

    verdicts = lever_verdicts(episodes, now)
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

    # observed_active: a quarantined lever (any lane) and a HURTING
    # lighter-live lever vanish from the observed stance set; a hurting
    # verdict on a SHADOW-lane lever does NOT (get_lever ignores it there —
    # the author-side skip owns that lane)
    oa = observed_active(active, {"scout.dip_range_max"},
                         {"live.clip_scale", "taker.tp"})
    assert set(oa) == {"taker.dip_range", "taker.tp"}, oa
    assert observed_active(active, set(), set()) == active
    assert observed_active({}, {"x"}, {"y"}) == {}

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

    # [2026-07-21 item 12] EPISODE POOLING — the rejoin grace.
    # (a) a stance that lapsed by TTL (expires now+7800) observed gone at
    # now+8000 stays OPEN awaiting re-assert (gap stamped at the expiry)…
    gp, cp = track(o2, gone, now + 8000)
    assert "taker" in gp and not [c for c in cp if c["group"] == "taker"], (gp, cp)
    assert gp["taker"]["gone_since"] == now + 7800, gp["taker"]
    # (b) …the SAME stance re-asserted inside the grace CONTINUES the episode:
    # original start, gap cleared, nothing closed
    gp2, cp2 = track(gp, st, now + 9000)
    assert cp2 == [] and gp2["taker"]["start"] == now, (gp2, cp2)
    assert "gone_since" not in gp2["taker"], gp2["taker"]
    # (c) …a DIFFERENT stance inside the grace closes at the EXPIRY (the old
    # stance was dead through the gap), then the new one opens
    gp3, cp3 = track(gp, st_moved, now + 9000)
    ch = [c for c in cp3 if c["group"] == "taker"]
    assert ch and ch[0]["reason"] == "changed" and ch[0]["end"] == now + 7800, cp3
    assert gp3["taker"]["start"] == now + 9000
    # (d) …the grace lapsing closes 'released', still backdated to the expiry
    gp4, cp4 = track(gp, gone, now + 7800 + int(REJOIN_H * 3600) + 61)
    rel4 = [c for c in cp4 if c["group"] == "taker"]
    assert rel4 and rel4[0]["reason"] == "released" and rel4[0]["end"] == now + 7800, cp4
    # (e) a stance removed MID-TTL (quarantine / hurting-revert: expiry still
    # in the future) gets NO grace — closes immediately (IMB-01 stays intact)
    o2f = {k: dict(v, last_expires=now + 99999) for k, v in o2.items()}
    gp5, cp5 = track(o2f, gone, now + 8000)
    rel5 = [c for c in cp5 if c["group"] == "taker"]
    assert rel5 and rel5[0]["reason"] == "released", cp5
    assert "taker" not in gp5, gp5
    # (f) grace 0 = pre-review behaviour (kill switch)
    gp6, cp6 = track(o2, gone, now + 8000, rejoin_h=0.0)
    assert [c for c in cp6 if c["group"] == "taker"], cp6

    # taker grading: the replay counterfactual. Tape where dip tickets sit at
    # range_pos 0.07 — defaults (0.05) take nothing; the stance (0.08) takes
    # them. Rising marks -> positive delta; dumping marks -> negative.
    def dt(h, mi=0):
        return datetime(2026, 7, 16, h, mi, tzinfo=timezone.utc)

    def snap(h, marks, tickets=None, mi=0):
        return (dt(h, mi), {"marks": marks, "tickets": tickets or {}})

    # [2026-07-17] the fixture must RESOLVE trades, not just span time: one
    # dip symbol opens and closes per 2 snapshots (one new position per lens
    # per cycle), so N symbols => N closed trades on the stance arm. The
    # default arm (DIP_RANGE=0.05) takes none of them — range_pos 0.07 fails
    # its bar — which is the whole counterfactual.
    def mk_tape(end_px, n_syms=MIN_EP_CLOSES):
        syms = [f"S{i}" for i in range(n_syms)]
        tape = []
        for i, s in enumerate(syms):
            tape.append(snap(2 * i, {s: 100.0},
                             {"dip": [{"sym": s, "range_pos": 0.07}]}))
            tape.append(snap(2 * i + 1, {s: end_px}))
        tape += [snap(2 * len(syms), {}, mi=m) for m in (0, 10, 20, 30, 40)]
        return tape

    win_tape = mk_tape(105.0)
    t0 = dt(0).timestamp()
    ep = {"group": "taker", "start": t0, "end": dt(23).timestamp(),
          "stance": {"taker.dip_range": 0.08}}
    g = grade_taker(ep, win_tape)
    assert g["status"] == "graded" and g["delta_usd"] > 0, g
    assert g["n_closed"] >= MIN_EP_CLOSES, g
    g_bad = grade_taker(ep, mk_tape(90.0))
    assert g_bad["status"] == "graded" and g_bad["delta_usd"] < 0, g_bad
    # too-short episodes refuse to grade (anti-noise floor)
    g_short = grade_taker(dict(ep, end=t0 + 600), win_tape)
    assert g_short["status"] == "too-short", g_short
    # [2026-07-17] HOURS AND SNAPSHOTS ARE NOT EVIDENCE. This is the live
    # 16-Jul episode's shape: long enough, tick-rich enough, and it resolved
    # NOTHING. It must refuse to grade rather than report delta 0.0 =
    # "neutral" and spend an episode toward a verdict.
    empty = [snap(0, {"ZZZ": 100.0})] + [snap(1, {"ZZZ": 100.0}, mi=m)
                                         for m in range(0, 60, 5)]
    g_empty = grade_taker(ep, empty)
    assert g_empty["status"] == "too-few-trades", g_empty
    assert g_empty["n_closed"] == 0, g_empty
    # a thin-but-nonzero sample is still refused (one fill ~= $3.50 > HURT_USD)
    g_thin = grade_taker(ep, mk_tape(105.0, n_syms=MIN_EP_CLOSES - 1))
    assert g_thin["status"] == "too-few-trades", g_thin
    # and lever_verdicts must ignore every non-graded status
    assert lever_verdicts([dict(ep, status="too-few-trades",
                                levers=["taker.dip_range"])]) == {}
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

    # [2026-07-17] the gapscout lane obeys MIN_EPISODES like every other lane.
    # NEGATIVE FIXTURE FIRST: this is the shape that shipped — ONE episode that
    # found activity, which the old bare `any()` graded HELPING (measured live:
    # gapscout.prefilter_gap n=1 helping). Synthetic, so it asserts the FLOOR
    # rather than today's data: it keeps passing after Gap Scout's retirement
    # empties the real lane, and it fails if anyone re-widens the gate.
    def _gs_ep(found):
        return {"group": "gapscout", "status": "graded",
                "levers": ["gapscout.prefilter_gap"], "found_activity": found}
    v1 = lever_verdicts([_gs_ep(True)])["gapscout.prefilter_gap"]
    assert v1["verdict"] == "neutral" and v1["n"] == 1, \
        f"one episode must not earn a verdict (MIN_EPISODES={MIN_EPISODES}): {v1}"
    v2 = lever_verdicts([_gs_ep(True), _gs_ep(True)])["gapscout.prefilter_gap"]
    assert v2["verdict"] == "helping" and v2["n_found"] == 2, v2
    # episodes present but activity thin: the floor is on FINDINGS, not cycles —
    # 5 episodes of silence plus one hit is not a working detection net.
    v3 = lever_verdicts([_gs_ep(True)] + [_gs_ep(False)] * 4)["gapscout.prefilter_gap"]
    assert v3["verdict"] == "neutral", f"n_found=1 must not earn helping: {v3}"
    # and the lane still cannot invent a HURTING (no $ counterfactual exists)
    assert lever_verdicts([_gs_ep(False)] * 3)["gapscout.prefilter_gap"]["verdict"] \
        == "neutral"

    # LIVE lane learning: per-trade during vs BOTH baselines (pre-window +
    # shadow twin). Thin data records; clear divergence signals.
    # [2026-07-17 AUDIT] These baseline-logic fixtures moved from "live-clip"
    # to "live-funding" — the lane where this metric is actually VALID. The
    # funding bars change the EDGE, so per-trade return really does move under
    # them; the clip lever changes only SIZE, and the metric cancels it exactly
    # (see grade_live). The logic under test (during vs BOTH baselines, 'bad'
    # only when worse than every one) is unchanged and still needs covering —
    # only its lane was wrong. The rows are also the REAL funding pair now: the
    # old fixture drove `crypto-trend-daily-lighter`, retired 17-Jul, whose
    # bot_pnl row is pruned at boot — a fixture no production data can produce.
    # [2026-07-17 AUDIT] THE PRODUCTION-ROSTER GUARD — third copy of the same
    # guard (evidence_board, fleet_respiration), because this was the third
    # copy of the same stale roster. A retired row's bot_pnl is pruned at boot,
    # so it can contribute no trade to any baseline; it can only dilute.
    try:
        from cleanup_legacy_bots import LEGACY_BOTS as _retired
        _rot = LIVE_ROWS & set(_retired)
        assert not _rot, (
            f"LIVE_ROWS names RETIRED row(s) {sorted(_rot)} — pruned at boot, "
            f"so they can never appear in `trades`. Remove them; add the live "
            f"slot's new occupant ONLY if it consumes the lever being graded.")
    except ImportError:      # not in this image — the guard is best-effort
        pass

    LIVE = "perps-funding-lighter-lighter"
    TWIN = "perps-funding-lighter-lshadow"

    def lt(bot, off_h, pct):
        return {"bot": bot, "profit_ratio": pct, "close_ts": _iso(t0 + off_h * 3600)}

    ep_lv = {"group": "live-funding", "start": t0, "end": t0 + 6 * 3600,
             "stance": {"live.funding.enter_apr": 0.0375}}

    def gl(trades):
        return grade_live(ep_lv, trades, group="live-funding")

    # during: live 6 trades @ +0.2%; before: 6 @ +1.5%; twin during: 6 @ +1.2%
    tr_bad = ([lt(LIVE, 1 + i * 0.5, 0.002) for i in range(6)]
              + [lt(LIVE, -6 + i * 0.5, 0.015) for i in range(6)]
              + [lt(TWIN, 1 + i * 0.5, 0.012) for i in range(6)]
              + [lt("not-live", 2, 9.9)])
    glb = gl(tr_bad)
    assert glb["status"] == "graded" and glb["signal"] == "bad", glb
    assert glb["n_during"] == 6 and glb["mean_pct_during"] == 0.2, glb
    # worse than pre-window but BETTER than the twin -> flat (never 'bad'
    # unless worse than EVERY baseline — real money isn't blamed on noise)
    tr_flat = ([lt(LIVE, 1 + i * 0.5, 0.002) for i in range(6)]
               + [lt(LIVE, -6 + i * 0.5, 0.015) for i in range(6)]
               + [lt(TWIN, 1 + i * 0.5, -0.02) for i in range(6)])
    assert gl(tr_flat)["signal"] == "flat"
    # better than both -> good
    tr_good = ([lt(LIVE, 1 + i * 0.5, 0.02) for i in range(6)]
               + [lt(LIVE, -6 + i * 0.5, 0.002) for i in range(6)]
               + [lt(TWIN, 1 + i * 0.5, 0.001) for i in range(6)])
    assert gl(tr_good)["signal"] == "good"
    # thin during-window or no usable baseline -> recorded (no signal)
    assert gl(tr_bad[:3])["status"] == "recorded"
    assert gl([lt(LIVE, 1 + i * 0.5, 0.002)
               for i in range(6)])["status"] == "recorded"

    # [2026-07-17 AUDIT] live-clip is RECORDED-ONLY, whatever the data says.
    # The metric is EXACTLY invariant to clip_scale (the lever scales pnl AND
    # the divisor), so the very same rows that legitimately signal 'bad'/'good'
    # on the funding lane must yield NO clip verdict — they are evidence about
    # something else. The record survives; only the causal claim is withdrawn.
    ep_clip = {"group": "live-clip", "start": t0, "end": t0 + 6 * 3600,
               "stance": {"live.clip_scale": 1.25}}
    for _rows in (tr_bad, tr_good, tr_flat):
        _g = grade_live(ep_clip, _rows, group="live-clip")
        assert _g["status"] == "recorded" and "signal" not in _g, _g
        assert _g["reason"] == "metric-invariant-to-lever", _g
    assert grade_live(ep_clip, tr_bad, group="live-clip")["n_during"] == 6, \
        "the episode RECORD is kept — the numbers are true, the verdict wasn't"
    # ...so no clip verdict can reach an actuator: no noise-driven revert at
    # get_lever, and the board's 1.5 top step stays fail-CLOSED.
    _clip_eps = [{"group": "live-clip", "status": "recorded",
                  "levers": ["live.clip_scale"], "signal": None}] * 4
    _clip_state = {"updated": _iso(t0), "ttl_sec": 2700,
                   "verdicts": lever_verdicts(_clip_eps, t0)}
    assert "live.clip_scale" not in hurting_levers(_clip_state, t0), \
        "a recorded-only lane must never produce a HURTING verdict"
    assert "live.clip_scale" not in helping_levers(_clip_state, t0), \
        "...and must never EARN the top step either — fail-CLOSED both ways"

    # live-funding group grades only the funding rows: a non-funding row in
    # LIVE_ROWS contributes nothing to it
    glf = grade_live(dict(ep_lv, group="live-funding"),
                     [lt("not-live", 2, 9.9)], group="live-funding")
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
    # gapscout: found_activity -> helping, but ONLY past the episode floor.
    # [2026-07-17] This fixture used to assert n=1 -> "helping" and so PINNED
    # the missing floor as the contract: the one lane that skipped MIN_EPISODES
    # had a test demanding it keep skipping it. It sat one line above the live
    # lane's own "a single episode never verdicts (floor)" — the same file
    # asserting opposite rules for the same question. A test that encodes the
    # bug is worse than no test: it makes the fix look like the regression.
    # Full floor coverage lives with the grade_gapscout fixtures above.
    v8 = lever_verdicts([{"group": "gapscout", "status": "graded",
                          "levers": ["gapscout.prefilter_gap"],
                          "found_activity": True}] * 2)
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

    # [2026-07-17 IMB-08] EVIDENCE EXPIRY / probation: post-IMB-01 a reverted
    # lever generates no new episodes, so without expiry a hurting verdict
    # could NEVER heal on honest evidence (permanent freeze). A verdict whose
    # newest episode is older than HURT_PROBATION_SEC decays to neutral
    # (probation flag kept) — the author probes once, fresh episodes
    # re-grade. Fresh evidence keeps its verdict; helping expires the same
    # way (an expand unlock must not ride week-old evidence); now=None
    # (offline analysis) applies no expiry.
    _tnow = 1_800_000_000.0
    _old = _tnow - HURT_PROBATION_SEC - 3600
    _fr = _tnow - 3600
    vex = lever_verdicts([dict(lv_ep("bad"), end=_old),
                          dict(lv_ep("bad"), end=_old)], _tnow)
    assert vex["live.clip_scale"]["verdict"] == "neutral" \
        and vex["live.clip_scale"]["probation"] is True \
        and vex["live.clip_scale"]["expired_verdict"] == "hurting", vex
    vfr = lever_verdicts([dict(lv_ep("bad"), end=_old),
                          dict(lv_ep("bad"), end=_fr)], _tnow)
    assert vfr["live.clip_scale"]["verdict"] == "hurting", \
        "one fresh episode keeps the verdict alive"
    vhe = lever_verdicts([dict(lv_ep("good"), end=_old),
                          dict(lv_ep("good"), end=_old)], _tnow)
    assert vhe["live.clip_scale"]["verdict"] == "neutral" \
        and vhe["live.clip_scale"]["expired_verdict"] == "helping", vhe
    vtk = lever_verdicts([dict(tk_ep(-5.0), end=_old),
                          dict(tk_ep(-5.0), end=_old)], _tnow)
    assert vtk["taker.dip_range"]["verdict"] == "neutral" \
        and vtk["taker.dip_range"]["probation"] is True, vtk
    assert lever_verdicts([dict(lv_ep("bad"), end=_old),
                           dict(lv_ep("bad"), end=_old)]
                          )["live.clip_scale"]["verdict"] == "hurting", \
        "now=None (offline) applies no expiry"

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

    # ---- [2026-07-30] THE SHADOW BOOKS LEARN ------------------------------
    # grouping: each book lever stands alone, mapped to the book it steers.
    assert group_of("carry.enter_apr") == "book:carry.enter_apr"
    assert group_of("sniper.surge_mult") == "book:sniper.surge_mult"
    assert group_of("taker.tp") == "taker", "existing lanes unchanged"
    # every book lever is registry-known AND maps to a bot — a rename in
    # either place must break HERE rather than silently stop grading.
    for _lv, _spec in tuning.LEVERS.items():
        if _spec.get("lane") == "lighter-books":
            assert _lv.split(".")[0] in BOOK_LEVER_BOTS, _lv
            assert group_of(_lv).startswith("book:"), _lv

    def _bk(lever, start, end, rows):
        # the REAL tracker shape: `stance` is a {lever: value} dict and there
        # is NO "lever" key. Building the fixture any other way proves nothing.
        return grade_book({"start": start, "end": end,
                           "stance": {lever: 1}, "group": f"book:{lever}"}, rows)

    # real ledger rows carry ISO close_ts (that is what _parse_ts accepts) —
    # an epoch-int fixture would make every assertion below read "recorded"
    # and quietly prove nothing.
    _S = datetime(2026, 7, 20, tzinfo=timezone.utc).timestamp()
    _E = _S + 6 * 3600

    def _tr(bot, ts, pct):
        return {"bot": bot,
                "close_ts": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
                "profit_ratio": pct}
    _CB = BOOK_LEVER_BOTS["carry"]

    # SELECTION lever: the question is "did per-trade return improve?"
    _before = [_tr(_CB, _S - 6 * 3600 + i * 60, 0.001) for i in range(6)]
    _better = [_tr(_CB, _S + i * 60, 0.02) for i in range(6)]
    _worse = [_tr(_CB, _S + i * 60, -0.02) for i in range(6)]
    assert _bk("carry.enter_apr", _S, _E, _before + _better)["signal"] == "good"
    assert _bk("carry.enter_apr", _S, _E, _before + _worse)["signal"] == "bad"

    # CAPACITY lever: the question is "did QUALITY HOLD while throughput rose?"
    # More trades at the SAME quality is the win condition — demanding a higher
    # mean would reject every capacity widening that ever worked, because a
    # ranked book reaching deeper takes worse names by construction.
    _more_same = [_tr(_CB, _S + i * 60, 0.001) for i in range(12)]
    _g = _bk("carry.max_positions", _S, _E, _before + _more_same)
    assert _g["signal"] == "good", _g
    assert _g["rate_during"] > _g["rate_before"]
    # ...and the same rise in throughput with DILUTED quality is the failure
    # mode capacity grading exists to catch.
    _more_worse = [_tr(_CB, _S + i * 60, -0.02) for i in range(12)]
    assert _bk("carry.max_positions", _S, _E,
               _before + _more_worse)["signal"] == "bad"
    # FEWER trades at the same quality is not a win (the lever bought nothing)
    _fewer_same = [_tr(_CB, _S + i * 60, 0.001) for i in range(5)]
    assert _bk("carry.max_positions", _S, _E,
               _before + _fewer_same)["signal"] == "flat"

    # THE SHAPE ITSELF: a real episode has no "lever" key at all, and the
    # grader must still find its book. This is the assertion that turns red
    # if grade_book ever goes back to reading ep["lever"].
    _real_ep = {"start": _S, "end": _E, "stance": {"carry.enter_apr": 1.4},
                "group": "book:carry.enter_apr"}
    assert "lever" not in _real_ep
    assert grade_book(_real_ep, _before + _better)["signal"] == "good", \
        "grade_book must derive its lever from `stance`, not a `lever` key"

    # thin data and an unmapped lever both REFUSE to grade
    assert _bk("carry.enter_apr", _S, _E, _before)["status"] == "recorded"
    assert _bk("nosuch.lever", _S, _E, _before + _better) == {
        "status": "recorded", "reason": "unmapped-lever", "bot": None,
        "n_during": 0, "mean_pct_during": None,
        "n_before": 0, "mean_pct_before": None}
    # a book lever must never be graded on ANOTHER book's trades
    assert _bk("sniper.surge_mult", _S, _E,
               _before + _better)["status"] == "recorded", \
        "carry's rows must not grade the sniper's lever"

    # THE VERDICT BRANCH. A perfectly graded book episode must yield a
    # verdict, or no consumer hook (the board's hurting-refusal, the tuner's
    # skip) can ever fire — the grader would be a dead end.
    # the REAL record shape lever_verdicts consumes: status="graded" plus a
    # `levers` LIST (see run_once's rec assembly), not a singular "lever".
    _beps = [{"status": "graded", "levers": ["carry.max_positions"],
              "signal": "bad", "end": _E} for _ in range(2)]
    _v = lever_verdicts(_beps, now=_E + 60)
    assert _v["carry.max_positions"]["verdict"] == "hurting", _v
    assert _v["carry.max_positions"]["basis"] == "book-paired"
    _geps = [{"status": "graded", "levers": ["carry.enter_apr"],
              "signal": "good", "end": _E} for _ in range(2)]
    assert lever_verdicts(_geps, now=_E + 60)["carry.enter_apr"]["verdict"] \
        == "helping"
    # and it must reach the CONSUMER hook the board reads
    _state = {"updated": _iso(_E + 60), "ttl_sec": 3600,
              "verdicts": lever_verdicts(_beps, now=_E + 60)}
    assert "carry.max_positions" in hurting_levers(_state, _E + 60), \
        "a hurting book lever must reach hurting_levers() or nothing refuses it"

    # THE FEED GATE. grade_book reads feeds["trades"]; if run_once does not
    # fetch them for a book episode the grader is structurally incapable of
    # ever grading. Assert the predicate names book groups.
    import inspect as _insp
    _src = _insp.getsource(run_once)
    assert 'startswith("book:")' in _src, \
        "run_once must fetch trades for book episodes or grade_book is inert"

    print("fleet_proprioception selftest OK (grouping, episode lifecycle "
          "incl. backdated release + daily slice, replay counterfactual "
          "win/lose/too-short/too-few-trades (marked), scout throughput, "
          "gapscout activity, live "
          "paired-learning (bad/flat/good vs pre-window+twin, funding split), "
          "verdict floors + joint blame, fail-safe hurting+helping hooks, "
          "BOOK selection-vs-capacity grading + feed gate)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(store.organ_main('fleet-proprioception', run_once))
